"""Regression coverage for consent-bound feedback publication v2."""
from __future__ import annotations

import tempfile
import threading
import time
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import Request
from sqlalchemy import create_engine


@pytest.fixture
def publication_db(monkeypatch):
    """Fresh synthetic SQLite database with one current active user."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "1")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", "synthetic-key")

    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db import session as db_session
    from db.models import User

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()
    db = db_session.SessionLocal()
    user = User(
        id="publication-user",
        email="publication@example.test",
        hashed_password="x",
        is_active=True,
        terms_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST,
    )
    admin = User(
        id="publication-admin",
        email="publication-admin@example.test",
        hashed_password="x",
        is_active=True,
        is_superuser=True,
        terms_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST,
    )
    db.add_all((user, admin))
    db.commit()
    try:
        yield db, user.id
    finally:
        db.close()
        if db_session.engine is not None:
            db_session.engine.dispose()
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _triaged_feedback(db, user_id: str, *, message: str = "Calendar clips text"):
    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from db.models import Feedback

    now = datetime.utcnow()
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message=message,
        status="triaged",
        publication_status="queued",
        publication_consent_version=FEEDBACK_PUBLICATION_CONSENT_VERSION,
        publication_consented_at=now,
        ai_title="Calendar clips text",
        ai_body="The calendar clips a long training label.",
        ai_labels=["bug", "feedback"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _approve_action(row):
    from api.feedback_publication import publication_review_token
    from api.routes.feedback import FeedbackAction

    token = publication_review_token(row)
    assert token is not None
    return FeedbackAction(action="approve", review_token=token)


def test_publication_v2_consent_is_the_only_current_grant() -> None:
    """Legacy v1 grants must never become publication candidates."""
    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION

    assert (
        FEEDBACK_PUBLICATION_CONSENT_VERSION
        == "feedback-publication-v2-public-github"
    )


def test_outbox_models_are_metadata_only() -> None:
    """Durable delivery state must not duplicate private feedback content."""
    from db.models import FeedbackPublicationAttempt, FeedbackPublicationOutbox

    outbox_columns = set(FeedbackPublicationOutbox.__table__.columns.keys())
    attempt_columns = set(FeedbackPublicationAttempt.__table__.columns.keys())
    forbidden = {
        "message",
        "body",
        "title",
        "context",
        "context_json",
        "image_description",
        "image_keys",
        "user_id",
        "response_body",
        "token",
        "secret",
    }

    assert outbox_columns.isdisjoint(forbidden)
    assert attempt_columns.isdisjoint(forbidden)
    assert {
        "feedback_id",
        "public_id",
        "payload_sha256",
        "public_content_sha256",
        "delivery_evidence",
        "state",
    } <= outbox_columns
    assert {"outbox_id", "attempt_no", "outcome", "lease_token"} <= attempt_columns
    assert FeedbackPublicationOutbox.public_id.default is not None
    assert FeedbackPublicationOutbox.feedback_id.nullable is True
    assert (
        next(iter(FeedbackPublicationOutbox.feedback_id.foreign_keys)).ondelete
        == "SET NULL"
    )


def test_migration_refuses_to_drop_publication_evidence(monkeypatch) -> None:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "f2a3b4c5d6e7_add_feedback_publication_outbox.py"
    )
    spec = importlib.util.spec_from_file_location(
        "feedback_publication_migration", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE feedback ("
            "image_keys JSON, image_storage_provenance JSON)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE feedback_publication_outbox (id TEXT PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE feedback_publication_attempts (id TEXT PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "INSERT INTO feedback_publication_outbox (id) VALUES ('outbox-1')"
        )
        monkeypatch.setattr(
            migration, "op", SimpleNamespace(get_bind=lambda: connection)
        )
        with pytest.raises(RuntimeError, match="preserve every ledger"):
            migration.downgrade()


@pytest.mark.parametrize(
    "values_sql",
    (
        "('[\"feedback/1/0.png\"]', NULL)",
        "(NULL, '{\"version\":1,\"backend\":\"local\","
        "\"scope_sha256\":\"sha256:"
        + "0" * 64
        + "\"}')",
    ),
)
def test_migration_refuses_to_drop_screenshot_storage_evidence(
    monkeypatch,
    values_sql: str,
) -> None:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "f2a3b4c5d6e7_add_feedback_publication_outbox.py"
    )
    spec = importlib.util.spec_from_file_location(
        "feedback_screenshot_downgrade_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE feedback ("
            "image_keys JSON, image_storage_provenance JSON)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE feedback_publication_outbox (id TEXT PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE feedback_publication_attempts (id TEXT PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "INSERT INTO feedback (image_keys, image_storage_provenance) "
            f"VALUES {values_sql}"
        )
        monkeypatch.setattr(
            migration,
            "op",
            SimpleNamespace(get_bind=lambda: connection),
        )

        with pytest.raises(RuntimeError, match="screenshot storage evidence"):
            migration.downgrade()


def test_alembic_legacy_backfill_is_tracking_only_and_idempotent() -> None:
    from db.models import Base

    migration_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "f2a3b4c5d6e7_add_feedback_publication_outbox.py"
    )
    spec = importlib.util.spec_from_file_location(
        "feedback_publication_legacy_backfill",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO feedback ("
            "id, kind, message, status, publication_status, "
            "publication_consent_version, publication_consented_at, "
            "github_issue_number, github_issue_url, created_at, updated_at"
            ") VALUES ("
            "1, 'bug', 'legacy public', 'resolved', 'private', "
            "'feedback-publication-v1', '2026-01-01 00:00:00', 42, "
            "'https://github.com/legacy-owner/legacy-repo/issues/42', "
            "'2026-01-01 00:00:00', '2026-01-02 00:00:00')"
        )
        connection.exec_driver_sql(
            "INSERT INTO feedback ("
            "id, kind, message, status, publication_status, "
            "publication_consent_version, publication_consented_at, "
            "github_issue_number, github_issue_url, created_at, updated_at"
            ") VALUES ("
            "2, 'bug', 'legacy private', 'needs_review', 'private', "
            "'feedback-publication-v1', '2026-01-01 00:00:00', NULL, NULL, "
            "'2026-01-01 00:00:00', '2026-01-02 00:00:00')"
        )
        migration._backfill_legacy_publications(connection)
        migration._backfill_legacy_publications(connection)
        rows = connection.exec_driver_sql(
            "SELECT feedback_id, marker_version, consent_version, "
            "payload_sha256, public_content_sha256, state, "
            "delivery_evidence, github_issue_number "
            "FROM feedback_publication_outbox"
        ).all()
        statuses = connection.exec_driver_sql(
            "SELECT id, publication_status, publication_consent_version "
            "FROM feedback ORDER BY id"
        ).all()

    assert rows == [
        (1, "legacy", None, None, None, "published", "published", 42)
    ]
    assert statuses == [
        (1, "published", "feedback-publication-v1"),
        (2, "private", "feedback-publication-v1"),
    ]


def test_payload_has_only_opaque_marker_and_stable_digest(publication_db) -> None:
    from api.feedback_publication import build_publication_payload

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    public_id = "57f8b441-3fac-4b52-bcef-6fbe91438690"

    first = build_publication_payload(row, public_id)
    second = build_publication_payload(row, public_id)

    assert first == second
    assert first.digest.startswith("sha256:") and len(first.digest) == 71
    assert (
        first.public_content_sha256.startswith("sha256:")
        and len(first.public_content_sha256) == 71
    )
    assert first.body.endswith(
        "<!-- praxys-feedback-publication:v2 "
        f"id={public_id} payload={first.digest} -->"
    )
    assert row.user_id not in first.body
    assert f"feedback id {row.id}" not in first.body
    assert f"(id `{row.id}`" not in first.body
    assert "reporter" not in first.body


@pytest.mark.parametrize(
    "heading",
    (
        "## Screenshot",
        "## screenshot context",
        "  ##   SCREENSHOT   CONTEXT  \r",
        "#### Screenshot context",
    ),
)
def test_payload_rejects_legacy_screenshot_derived_sections(
    publication_db,
    heading: str,
) -> None:
    from api.feedback_publication import (
        PublicationPayloadBlocked,
        build_publication_payload,
    )

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    row.image_keys = [f"feedback/{row.id}/0.png"]
    row.image_description = "Private image description"
    row.image_sensitive = False
    row.ai_body = f"A safe text report.\n\n{heading}\nPrivate image description"

    with pytest.raises(
        PublicationPayloadBlocked,
        match="screenshot_derived_text_present",
    ):
        build_publication_payload(row, "57f8b441-3fac-4b52-bcef-6fbe91438690")


def test_image_free_feedback_may_use_a_screenshot_heading(publication_db) -> None:
    from api.feedback_publication import build_publication_payload

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    row.ai_body = "## Screenshot\nThe screenshot button itself is misaligned."

    payload = build_publication_payload(
        row,
        "57f8b441-3fac-4b52-bcef-6fbe91438690",
    )

    assert "## Screenshot" in payload.body


def test_privacy_policy_change_fences_pre_policy_pending_payload(
    publication_db,
    monkeypatch,
) -> None:
    from api import feedback_prompt, github_issues
    from api.feedback_publication import (
        claim_next_send,
        enqueue_publication,
        send_claim,
    )

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    enqueue_publication(db, row.id)
    db.commit()
    monkeypatch.setattr(
        feedback_prompt,
        "publication_privacy_review_prompt",
        lambda: "changed privacy policy",
    )
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("policy-drifted payload must not send"),
    )

    claim = claim_next_send(db)
    assert claim is not None
    assert send_claim(db, *claim) == "manual_required"
    db.refresh(row)
    assert row.publication_status == "manual_required"


def test_admin_review_supersedes_never_sent_policy_drift_outbox(
    publication_db,
    monkeypatch,
) -> None:
    from fastapi import BackgroundTasks

    from api import feedback_prompt, github_issues
    from api.feedback_publication import claim_next_send, enqueue_publication, send_claim
    from api.routes.feedback import update_feedback
    from db.models import FeedbackPublicationAttempt, FeedbackPublicationOutbox

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    original = enqueue_publication(db, row.id)
    db.commit()
    monkeypatch.setattr(
        feedback_prompt,
        "publication_privacy_review_prompt",
        lambda: "changed privacy policy",
    )
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("policy-drifted payload must not send"),
    )
    claim = claim_next_send(db)
    assert claim is not None
    assert send_claim(db, *claim) == "manual_required"
    db.refresh(row)
    approval = _approve_action(row)

    response = update_feedback(
        row.id,
        approval,
        BackgroundTasks(),
        user_id="publication-admin",
        db=db,
    )

    rows = db.query(FeedbackPublicationOutbox).order_by(
        FeedbackPublicationOutbox.created_at.asc(),
        FeedbackPublicationOutbox.id.asc(),
    ).all()
    assert response["status"] == "triaged"
    assert len(rows) == 2
    assert rows[0].id == original.id
    assert rows[0].state == "cancelled"
    assert rows[0].feedback_id is None
    assert rows[0].last_error_code == "superseded_after_human_review"
    assert rows[1].state == "pending"
    assert rows[1].feedback_id == row.id
    assert rows[1].public_id != rows[0].public_id
    attempts = db.query(FeedbackPublicationAttempt).filter(
        FeedbackPublicationAttempt.outbox_id == rows[0].id
    ).all()
    assert [attempt.outcome for attempt in attempts] == ["not_sent"]


def test_public_marker_id_has_at_least_128_random_bits() -> None:
    from api.feedback_publication import generate_publication_id

    source = (
        Path(__file__).resolve().parent.parent / "api" / "feedback_publication.py"
    ).read_text()
    generated = {generate_publication_id() for _ in range(64)}

    assert "secrets.token_hex(16)" in source
    assert len(generated) == 64
    assert all(len(value) == 32 for value in generated)
    assert all(len(bytes.fromhex(value)) == 16 for value in generated)


@pytest.mark.parametrize(
    "marker",
    (
        "[redacted]",
        "[redacted-key]",
        "[redacted-token]",
        "[redacted-private-key]",
        "[redacted-email]",
    ),
)
def test_payload_with_any_redaction_marker_requires_review(
    publication_db, marker: str
) -> None:
    from api.feedback_publication import (
        PublicationPayloadBlocked,
        build_publication_payload,
    )

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    row.ai_body = f"Failure output: {marker}"
    with pytest.raises(PublicationPayloadBlocked) as exc:
        build_publication_payload(row, "57f8b441-3fac-4b52-bcef-6fbe91438690")
    assert exc.value.code == "redaction_marker_present"


def test_enqueue_is_unique_and_allows_only_one_active_candidate_per_user(
    publication_db,
) -> None:
    from api.feedback_publication import enqueue_publication
    from db.models import FeedbackPublicationOutbox

    db, user_id = publication_db
    first = _triaged_feedback(db, user_id)
    first_outbox = enqueue_publication(db, first.id)
    db.commit()
    assert first_outbox is not None
    assert enqueue_publication(db, first.id).id == first_outbox.id
    db.commit()

    second = _triaged_feedback(db, user_id, message="Another report")
    second.ai_title = "Another report"
    second.ai_body = "Another safe report"
    db.commit()
    assert enqueue_publication(db, second.id) is None
    db.commit()
    db.refresh(second)
    assert second.publication_status == "manual_required"
    assert second.status == "needs_review"
    assert db.query(FeedbackPublicationOutbox).count() == 1


def test_legacy_v1_row_never_enqueues(publication_db) -> None:
    from api.feedback_publication import enqueue_publication
    from db.models import FeedbackPublicationOutbox

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    row.publication_consent_version = "feedback-publication-v1"
    db.commit()

    assert enqueue_publication(db, row.id) is None
    db.commit()
    db.refresh(row)
    assert row.publication_status == "private"
    assert db.query(FeedbackPublicationOutbox).count() == 0


class _Response:
    def __init__(self, status_code: int, payload: object):
        self.status_code = status_code
        self._payload = payload
        self.reason_phrase = "synthetic"

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    ("response", "expected"),
    (
        (_Response(422, {}), "rejected"),
        (_Response(503, {}), "unknown"),
        (_Response(201, {}), "unknown"),
        (
            _Response(
                201,
                {
                    "number": 42,
                    "html_url": "https://github.com/praxys-run/praxys/issues/42",
                },
            ),
            "created",
        ),
    ),
)
def test_github_create_returns_typed_outcomes(
    monkeypatch, response: _Response, expected: str
) -> None:
    from api import github_issues

    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setattr(github_issues, "_bearer_token", lambda: "synthetic")
    monkeypatch.setattr(github_issues.httpx, "post", lambda *a, **k: response)

    result = github_issues.create_issue_outcome(
        title="Synthetic",
        body="Synthetic",
        publication_authorized=True,
    )
    assert result["outcome"] == expected


def test_github_timeout_is_unknown_not_retryable_failure(monkeypatch) -> None:
    from api import github_issues

    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setattr(github_issues, "_bearer_token", lambda: "synthetic")

    def timeout(*_args, **_kwargs):
        raise httpx.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(github_issues.httpx, "post", timeout)
    result = github_issues.create_issue_outcome(
        title="Synthetic",
        body="Synthetic",
        publication_authorized=True,
    )
    assert result["outcome"] == "unknown"
    assert result["error_code"] == "network_unknown"


def test_unknown_send_reconciles_without_a_second_post(
    publication_db, monkeypatch
) -> None:
    from api import github_issues
    from api.feedback_publication import (
        claim_next_reconciliation,
        claim_next_send,
        enqueue_publication,
        reconcile_claim,
        send_claim,
    )
    from db.models import FeedbackPublicationAttempt, FeedbackPublicationOutbox

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    calls = {"post": 0, "reconcile": 0}

    def reconcile(_marker: str, **_kwargs):
        calls["reconcile"] += 1
        if calls["reconcile"] < 2:
            return {
                "outcome": "unknown",
                "number": None,
                "url": None,
                "http_status": 200,
                "error_code": "not_indexed_or_absent",
            }
        return {
            "outcome": "reconciled",
            "number": 42,
            "url": "https://github.com/praxys-run/praxys/issues/42",
            "http_status": 200,
            "error_code": None,
        }

    def create(**_kwargs):
        calls["post"] += 1
        return {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "network_unknown",
        }

    monkeypatch.setattr(github_issues, "reconcile_issue_marker", reconcile)
    monkeypatch.setattr(github_issues, "create_issue_outcome", create)
    claim = claim_next_send(db)
    assert claim is not None
    assert send_claim(db, *claim) == "unknown"
    assert calls["post"] == 1
    db.refresh(outbox)
    outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    reconciliation = claim_next_reconciliation(db)
    assert reconciliation is not None
    assert reconcile_claim(db, *reconciliation) == "published"
    assert calls["post"] == 1
    db.refresh(outbox)
    db.refresh(row)
    assert outbox.state == "published"
    assert row.publication_status == "published"
    assert row.github_issue_number == 42
    attempt = db.query(FeedbackPublicationAttempt).one()
    assert attempt.outcome == "reconciled"


def test_stale_lease_cannot_finalize(publication_db, monkeypatch) -> None:
    from api import github_issues
    from api.feedback_publication import claim_next_send, enqueue_publication, send_claim

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    claim = claim_next_send(db)
    assert claim is not None
    outbox.lease_token = "new-owner"
    db.commit()
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("stale worker must not call GitHub"),
    )
    assert send_claim(db, *claim) == "stale"
    db.refresh(row)
    assert row.github_issue_number is None


def test_admin_reject_and_worker_claim_never_cancel_in_flight(
    publication_db, monkeypatch
) -> None:
    """Both legal orderings avoid a cancelled row with an active attempt."""
    from fastapi import BackgroundTasks, HTTPException
    from sqlalchemy.orm import sessionmaker

    from api import github_issues
    from api.feedback_publication import (
        claim_next_send,
        enqueue_publication,
        recover_expired_leases,
    )
    from api.routes.feedback import FeedbackAction, update_feedback
    from db import session as db_session
    from db.models import (
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
    )

    db, user_id = publication_db
    posts = {"count": 0}

    def unexpected_post(**_kwargs):
        posts["count"] += 1
        pytest.fail("claim/reject serialization must not POST")

    monkeypatch.setattr(github_issues, "create_issue_outcome", unexpected_post)

    # Admin wins: cancellation commits before a worker can claim the row.
    rejected = _triaged_feedback(db, user_id, message="Reject first")
    rejected_outbox = enqueue_publication(db, rejected.id)
    db.commit()
    update_feedback(
        rejected.id,
        FeedbackAction(action="reject"),
        BackgroundTasks(),
        user_id="publication-admin",
        db=db,
    )
    db.refresh(rejected_outbox)
    assert rejected_outbox.state == "cancelled"
    assert claim_next_send(db) is None
    assert (
        db.query(FeedbackPublicationAttempt)
        .filter(FeedbackPublicationAttempt.outbox_id == rejected_outbox.id)
        .count()
        == 0
    )

    # Worker wins: retain a deliberately stale pending object in the admin
    # identity map, then commit the worker claim before admin rejection. The
    # PostgreSQL path must lock and refresh this exact outbox row.
    active = _triaged_feedback(db, user_id, message="Claim first")
    active_outbox = enqueue_publication(db, active.id)
    db.commit()
    AdminSession = sessionmaker(
        bind=db_session.engine,
        autoflush=False,
        expire_on_commit=False,
    )
    with AdminSession() as admin_db:
        cached = admin_db.get(FeedbackPublicationOutbox, active_outbox.id)
        assert cached is not None and cached.state == "pending"
        admin_db.commit()

        with db_session.SessionLocal() as worker_db:
            claim = claim_next_send(worker_db)
        assert claim is not None and claim[0] == active_outbox.id

        dialect = db_session.engine.dialect
        original_name = dialect.name
        dialect.name = "postgresql"
        try:
            with pytest.raises(HTTPException) as exc:
                update_feedback(
                    active.id,
                    FeedbackAction(action="reject"),
                    BackgroundTasks(),
                    user_id="publication-admin",
                    db=admin_db,
                )
            assert exc.value.status_code == 409
        finally:
            admin_db.rollback()
            dialect.name = original_name

    db.expire_all()
    claimed_outbox = db.get(FeedbackPublicationOutbox, active_outbox.id)
    attempt = (
        db.query(FeedbackPublicationAttempt)
        .filter(FeedbackPublicationAttempt.outbox_id == active_outbox.id)
        .one()
    )
    assert claimed_outbox is not None and claimed_outbox.state == "sending"
    assert attempt.outcome == "in_flight"
    assert posts["count"] == 0
    assert (
        db.query(FeedbackPublicationOutbox)
        .join(
            FeedbackPublicationAttempt,
            FeedbackPublicationAttempt.outbox_id
            == FeedbackPublicationOutbox.id,
        )
        .filter(
            FeedbackPublicationOutbox.state == "cancelled",
            FeedbackPublicationAttempt.outcome == "in_flight",
        )
        .count()
        == 0
    )

    claimed_outbox.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert recover_expired_leases(db) == 1
    db.refresh(claimed_outbox)
    db.refresh(attempt)
    assert claimed_outbox.state == "reconciling"
    assert attempt.outcome == "unknown"


def test_admin_retry_revives_cancelled_current_outbox(publication_db) -> None:
    """Retry may revive only the same currently-authorized cancelled grant."""
    from fastapi import BackgroundTasks

    from api.feedback_publication import claim_next_send, enqueue_publication
    from api.routes.feedback import FeedbackAction, update_feedback

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Reject then retry")
    outbox = enqueue_publication(db, row.id)
    db.commit()
    assert outbox is not None

    update_feedback(
        row.id,
        FeedbackAction(action="reject"),
        BackgroundTasks(),
        user_id="publication-admin",
        db=db,
    )
    db.refresh(outbox)
    assert outbox.state == "cancelled"

    update_feedback(
        row.id,
        FeedbackAction(action="retry"),
        BackgroundTasks(),
        user_id="publication-admin",
        db=db,
    )
    revived = enqueue_publication(db, row.id)
    db.commit()

    assert revived is outbox
    assert outbox.state == "pending"
    assert outbox.lease_token is None
    assert outbox.lease_expires_at is None
    assert row.publication_status == "queued"
    claim = claim_next_send(db)
    assert claim is not None and claim[0] == outbox.id


def test_worker_admin_race_keeps_one_active_candidate(
    publication_db, monkeypatch
) -> None:
    """An admin cannot enqueue a second row while the worker owns the first."""
    from fastapi import BackgroundTasks, HTTPException

    from api import github_issues
    from api.feedback_publication import claim_next_send, enqueue_publication, send_claim
    from api.routes.feedback import FeedbackAction, update_feedback
    from db import session as db_session
    from db.models import FeedbackPublicationOutbox

    db, user_id = publication_db
    first = _triaged_feedback(db, user_id)
    first_outbox = enqueue_publication(db, first.id)
    db.commit()
    second = _triaged_feedback(db, user_id, message="Second safe report")
    second.ai_title = "Second safe report"
    second.ai_body = "Second safe report body"
    second.status = "needs_review"
    db.commit()

    claim = claim_next_send(db)
    assert claim is not None
    entered_preflight = threading.Event()
    release_preflight = threading.Event()

    def reconcile(_marker: str, **_kwargs):
        entered_preflight.set()
        assert release_preflight.wait(5)
        return {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": 200,
            "error_code": "not_indexed_or_absent",
        }

    monkeypatch.setattr(github_issues, "reconcile_issue_marker", reconcile)
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: {
            "outcome": "created",
            "number": 77,
            "url": "https://github.com/praxys-run/praxys/issues/77",
            "http_status": 201,
            "error_code": None,
        },
    )
    worker_result: list[str] = []

    def run_worker() -> None:
        with db_session.SessionLocal() as worker_db:
            worker_result.append(send_claim(worker_db, *claim))

    worker = threading.Thread(target=run_worker)
    worker.start()
    assert entered_preflight.wait(5)
    try:
        with db_session.SessionLocal() as admin_db:
            with pytest.raises(HTTPException) as exc:
                update_feedback(
                    second.id,
                    _approve_action(second),
                    BackgroundTasks(),
                    user_id="publication-admin",
                    db=admin_db,
                )
            assert exc.value.status_code == 409
    finally:
        release_preflight.set()
        worker.join(timeout=5)
    assert worker_result == ["published"]
    db.expire_all()
    assert db.query(FeedbackPublicationOutbox).count() == 1
    assert db.get(FeedbackPublicationOutbox, first_outbox.id).state == "published"


def test_reconciler_start_does_not_block_api_startup(monkeypatch) -> None:
    from api import feedback_publication as publication

    publication.stop_publication_reconciler()
    entered = threading.Event()
    release = threading.Event()

    def blocked_pass(**_kwargs):
        entered.set()
        release.wait(5)
        return {"recovered": 0, "reconciled": 0, "sent": 0}

    monkeypatch.setattr(publication, "process_publication_queue", blocked_pass)
    started = time.monotonic()
    publication.start_publication_reconciler()
    elapsed = time.monotonic() - started
    try:
        assert elapsed < 0.5
        assert entered.wait(2)
    finally:
        release.set()
        publication.stop_publication_reconciler()


def test_reconciler_loop_failure_log_omits_sensitive_exception(
    monkeypatch,
    caplog,
) -> None:
    from api import feedback_publication as publication

    sensitive = (
        "feedback-id=918273645;user-id=private-user;"
        "key=feedback/918273645/0.png;path=/tmp/private-user/file;"
        f"hash={'ab' * 32};url=https://storage.invalid/private;"
        "content=private feedback content;"
        "consent=feedback-publication-v2-public-github"
    )

    class StopAfterFailure:
        def is_set(self):
            return False

        def wait(self, _timeout):
            return True

    caplog.set_level("ERROR", logger="api.feedback_publication")
    monkeypatch.setattr(publication, "_stop_event", StopAfterFailure())
    monkeypatch.setattr(
        publication,
        "process_publication_queue",
        lambda: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )

    publication._reconciler_loop()

    assert "feedback publication wake failed" in caplog.text
    for sentinel in sensitive.split(";"):
        assert sentinel not in caplog.text


def test_safe_publication_wake_returns_zero_counts_and_bounded_telemetry(
    monkeypatch,
    caplog,
) -> None:
    from api import feedback_publication as publication

    sensitive = "private-publication-wake-exception-sentinel"
    telemetry_calls: list[tuple[str, str]] = []
    caplog.set_level("ERROR", logger="api.feedback_publication")
    monkeypatch.setattr(
        publication,
        "process_publication_queue",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )
    monkeypatch.setattr(
        publication.telemetry,
        "record_feedback_publication",
        lambda *, status, reason: telemetry_calls.append((status, reason)),
    )

    result = publication.safe_wake_publication_queue(limit=1)

    assert result == {"recovered": 0, "reconciled": 0, "sent": 0}
    assert telemetry_calls == [("provider_failure", "provider_failure")]
    assert "feedback publication wake failed" in caplog.text
    assert sensitive not in caplog.text


def test_triage_background_wake_preserves_result_when_worker_fails(
    monkeypatch,
    caplog,
) -> None:
    from api import feedback_publication, feedback_triage

    sensitive = "private-triage-wake-exception-sentinel"
    expected = {"status": "triaged", "kind": "bug", "used_llm": False}
    telemetry_calls: list[tuple[str, str]] = []
    caplog.set_level("ERROR", logger="api.feedback_publication")
    monkeypatch.setattr(
        feedback_triage,
        "triage_and_publish",
        lambda _feedback_id: expected,
    )
    monkeypatch.setattr(
        feedback_publication,
        "process_publication_queue",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )
    monkeypatch.setattr(
        feedback_publication.telemetry,
        "record_feedback_publication",
        lambda *, status, reason: telemetry_calls.append((status, reason)),
    )

    result = feedback_triage.triage_and_wake_publication(918273645)

    assert result == expected
    assert telemetry_calls == [("provider_failure", "provider_failure")]
    assert sensitive not in caplog.text


def test_admin_background_wake_failure_preserves_response_and_outbox(
    publication_db,
    monkeypatch,
    caplog,
) -> None:
    import asyncio

    from fastapi import BackgroundTasks

    from api import feedback_publication
    from api.routes.feedback import FeedbackAction, update_feedback
    from db.models import FeedbackPublicationOutbox

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Admin background wake")
    row.status = "needs_review"
    row.publication_status = "manual_required"
    db.commit()
    sensitive = "private-admin-wake-exception-sentinel"
    telemetry_calls: list[tuple[str, str]] = []
    caplog.set_level("ERROR", logger="api.feedback_publication")
    monkeypatch.setattr(
        feedback_publication,
        "process_publication_queue",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )
    monkeypatch.setattr(
        feedback_publication.telemetry,
        "record_feedback_publication",
        lambda *, status, reason: telemetry_calls.append((status, reason)),
    )
    background = BackgroundTasks()

    response = update_feedback(
        row.id,
        _approve_action(row),
        background,
        user_id="publication-admin",
        db=db,
    )
    asyncio.run(background())

    assert response["status"] == "triaged"
    assert response["publication_status"] == "queued"
    outbox = db.query(FeedbackPublicationOutbox).one()
    assert outbox.feedback_id == row.id
    assert outbox.state == "pending"
    assert telemetry_calls == [("provider_failure", "provider_failure")]
    assert sensitive not in caplog.text


def test_main_feedback_reconciler_stop_log_omits_sensitive_exception(
    monkeypatch,
    caplog,
) -> None:
    import asyncio

    from api import (
        auth_secrets,
        channel_processing_authority,
        feedback_publication,
        labs_dispatch,
        labs_environment,
        main,
        optional_processing,
        personal_context,
        statsig_client,
    )
    from api.routes import sync as sync_route
    from db import session as db_session

    sensitive = (
        "feedback-id=918273645;user-id=private-user;"
        "key=feedback/918273645/0.png;path=/tmp/private-user/file;"
        f"hash={'ab' * 32};url=https://storage.invalid/private;"
        "content=private feedback content;"
        "consent=feedback-publication-v2-public-github"
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    async def noop_async(*_args, **_kwargs):
        return None

    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setattr(optional_processing, "validate_optional_processing_config", lambda: None)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(db_session, "SessionLocal", FakeSession)
    monkeypatch.setattr(channel_processing_authority, "reconcile_channel_processing_authority", lambda _db: None)
    monkeypatch.setattr(personal_context, "replay_deletion_manifests", lambda _db: None)
    monkeypatch.setattr(personal_context, "run_retention", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(labs_environment, "replay_deletion_tombstones", lambda _db: None)
    monkeypatch.setattr(labs_environment, "recover_interrupted_jobs", lambda _db: None)
    monkeypatch.setattr(sync_route, "migrate_legacy_garmin_tokenstores", lambda: None)
    monkeypatch.setattr(auth_secrets, "get_jwt_secret", lambda: "synthetic")
    monkeypatch.setattr(statsig_client, "init_statsig", noop_async)
    monkeypatch.setattr(statsig_client, "shutdown_statsig", noop_async)
    monkeypatch.setattr(labs_dispatch, "start_dispatcher", lambda: None)
    monkeypatch.setattr(labs_dispatch, "stop_dispatcher", lambda: None)
    monkeypatch.setattr(feedback_publication, "start_publication_reconciler", lambda: None)
    monkeypatch.setattr(
        feedback_publication,
        "stop_publication_reconciler",
        lambda: (_ for _ in ()).throw(RuntimeError(sensitive)),
    )
    monkeypatch.setattr(db_session, "dispose_engines_async", noop_async)
    caplog.set_level("ERROR", logger="api.main")

    async def exercise_lifespan():
        async with main.lifespan(main.app):
            pass

    asyncio.run(exercise_lifespan())

    assert "Failed to stop feedback publication reconciler cleanly" in caplog.text
    for sentinel in sensitive.split(";"):
        assert sentinel not in caplog.text


def test_submit_returns_server_authoritative_private_and_queued_results(
    publication_db, monkeypatch
) -> None:
    from fastapi import BackgroundTasks

    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from api.routes.feedback import FeedbackRequest, submit_feedback

    db, user_id = publication_db
    private = submit_feedback(
        FeedbackRequest(kind="bug", message="Private report"),
        BackgroundTasks(),
        user_id=user_id,
        db=db,
    )
    assert private["publication"] == {"status": "private", "issue_url": None}

    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    queued = submit_feedback(
        FeedbackRequest(
            kind="bug",
            message="Public candidate",
            external_publication_consent=True,
            external_publication_consent_version=(
                FEEDBACK_PUBLICATION_CONSENT_VERSION
            ),
        ),
        BackgroundTasks(),
        user_id=user_id,
        db=db,
    )
    assert queued["publication"] == {"status": "queued", "issue_url": None}


def test_malformed_or_killed_switches_return_unavailable(
    publication_db, monkeypatch
) -> None:
    from fastapi import BackgroundTasks

    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from api.routes.feedback import FeedbackRequest, submit_feedback

    db, user_id = publication_db
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "definitely")
    response = submit_feedback(
        FeedbackRequest(
            kind="bug",
            message="Fail closed",
            external_publication_consent=True,
            external_publication_consent_version=(
                FEEDBACK_PUBLICATION_CONSENT_VERSION
            ),
        ),
        BackgroundTasks(),
        user_id=user_id,
        db=db,
    )
    assert response["publication"]["status"] == "unavailable"


def test_kill_switch_blocks_send_claim_mutation_but_not_reconciliation(
    publication_db,
    monkeypatch,
) -> None:
    from api.feedback_publication import (
        claim_next_reconciliation,
        claim_next_send,
        enqueue_publication,
    )
    from db.models import FeedbackPublicationAttempt

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Queued before emergency stop")
    outbox = enqueue_publication(db, row.id)
    db.commit()
    assert outbox is not None

    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "true")
    assert claim_next_send(db) is None
    db.refresh(outbox)
    assert outbox.state == "pending"
    assert outbox.attempt_count == 0
    assert outbox.lease_token is None
    assert db.query(FeedbackPublicationAttempt).count() == 0

    outbox.state = "reconciling"
    outbox.delivery_evidence = "ambiguous"
    outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert claim_next_reconciliation(db) is not None


def test_demo_queued_send_is_denied_after_source_account_deletion(
    publication_db,
    monkeypatch,
) -> None:
    """A legacy demo grant cannot POST, while marker reconciliation survives."""
    from api import github_issues
    from api.feedback_publication import (
        claim_next_reconciliation,
        claim_next_send,
        enqueue_publication,
        reconcile_claim,
        send_claim,
    )
    from db.models import User

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Legacy queued demo feedback")
    outbox = enqueue_publication(db, row.id)
    db.commit()
    assert outbox is not None
    claim = claim_next_send(db)
    assert claim is not None

    demo = db.get(User, user_id)
    source = db.get(User, "publication-admin")
    demo.is_demo = True
    demo.demo_of = source.id
    db.commit()
    db.delete(source)
    db.commit()
    db.refresh(demo)
    assert demo.is_demo is True

    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("demo feedback must never POST"),
    )
    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda _marker, **_kwargs: pytest.fail(
            "a new demo send must stop before provider I/O"
        ),
    )
    assert send_claim(db, *claim) == "unavailable"
    db.refresh(outbox)
    db.refresh(row)
    assert outbox.state == "held"
    assert row.publication_status == "unavailable"

    outbox.state = "reconciling"
    outbox.delivery_evidence = "ambiguous"
    outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
    outbox.lease_token = None
    outbox.lease_expires_at = None
    row.publication_status = "unknown"
    db.commit()
    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda _marker, **_kwargs: {
            "outcome": "reconciled",
            "number": 73,
            "url": "https://github.com/praxys-run/praxys/issues/73",
            "http_status": 200,
            "error_code": None,
        },
    )
    reconciliation = claim_next_reconciliation(db)
    assert reconciliation is not None
    assert reconcile_claim(db, *reconciliation) == "published"


def test_status_endpoint_drops_non_allowlisted_link(publication_db) -> None:
    from fastapi import Response

    from api.routes.feedback import FeedbackStatusRequest, get_own_feedback_status

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    row.publication_status = "published"
    row.github_issue_number = 9
    row.github_issue_url = "https://example.test/issues/9"
    db.commit()
    response = Response()

    result = get_own_feedback_status(
        FeedbackStatusRequest(feedback_id=row.id),
        response,
        user_id=user_id,
        db=db,
    )

    assert result["publication"] == {"status": "unknown", "issue_url": None}
    assert response.headers["Cache-Control"] == "private, no-store"


def test_expired_send_lease_becomes_unknown_reconciliation(
    publication_db, monkeypatch
) -> None:
    from api import github_issues
    from api.feedback_publication import (
        claim_next_send,
        enqueue_publication,
        recover_expired_leases,
    )
    from db.models import FeedbackPublicationAttempt

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    assert claim_next_send(db) is not None
    db.refresh(outbox)
    outbox.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("expired lease must not send"),
    )

    assert recover_expired_leases(db) == 1
    db.refresh(outbox)
    db.refresh(row)
    assert outbox.state == "reconciling"
    assert row.publication_status == "unknown"
    assert db.query(FeedbackPublicationAttempt).one().outcome == "unknown"


def test_committed_reconciliation_lease_blocks_until_expired_takeover(
    publication_db, monkeypatch
) -> None:
    """A second session may replace a reconciliation lease only at expiry."""
    from api import github_issues
    from api.feedback_publication import (
        LEASE_SECONDS,
        claim_next_reconciliation,
        enqueue_publication,
        reconcile_claim,
    )
    from db import session as db_session
    from db.models import FeedbackPublicationOutbox

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    now = datetime.utcnow()
    outbox.state = "reconciling"
    outbox.delivery_evidence = "ambiguous"
    outbox.available_at = now
    db.commit()

    first = claim_next_reconciliation(db, now=now)
    assert first is not None
    first_expiry = now + timedelta(seconds=LEASE_SECONDS)

    with db_session.SessionLocal() as second_db:
        assert (
            claim_next_reconciliation(
                second_db,
                now=first_expiry - timedelta(microseconds=1),
            )
            is None
        )
        takeover = claim_next_reconciliation(second_db, now=first_expiry)
        assert takeover is not None
        assert takeover[0] == first[0]
        assert takeover[1] != first[1]

    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda _marker, **_kwargs: pytest.fail(
            "a stale lease must not call GitHub"
        ),
    )
    db.expire_all()
    assert reconcile_claim(db, *first) == "stale"
    current = db.get(FeedbackPublicationOutbox, outbox.id)
    assert current is not None
    assert current.state == "reconciling"
    assert current.lease_token == takeover[1]
    assert current.reconcile_count == 2


@pytest.mark.parametrize(
    ("reconcile_outcome", "expected_result", "expected_state"),
    (("unknown", "unknown", "reconciling"), ("multiple", "manual_required", "manual_review")),
)
def test_reconciliation_zero_or_many_never_resends(
    publication_db,
    monkeypatch,
    reconcile_outcome: str,
    expected_result: str,
    expected_state: str,
) -> None:
    from api import github_issues
    from api.feedback_publication import (
        claim_next_reconciliation,
        claim_next_send,
        enqueue_publication,
        reconcile_claim,
        send_claim,
    )

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    posts = {"count": 0}
    reconciliations = [{
        "outcome": "unknown",
        "number": None,
        "url": None,
        "http_status": 200,
        "error_code": "not_indexed_or_absent",
    }]

    def reconcile(_marker: str, **_kwargs):
        if reconciliations:
            return reconciliations.pop(0)
        return {
            "outcome": reconcile_outcome,
            "number": None,
            "url": None,
            "http_status": 200,
            "error_code": (
                "multiple_matches"
                if reconcile_outcome == "multiple"
                else "not_indexed_or_absent"
            ),
        }

    def create(**_kwargs):
        posts["count"] += 1
        return {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": None,
            "error_code": "network_unknown",
        }

    monkeypatch.setattr(github_issues, "reconcile_issue_marker", reconcile)
    monkeypatch.setattr(github_issues, "create_issue_outcome", create)
    send = claim_next_send(db)
    assert send is not None
    assert send_claim(db, *send) == "unknown"
    outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    claim = claim_next_reconciliation(db)
    assert claim is not None
    assert reconcile_claim(db, *claim) == expected_result
    db.refresh(outbox)
    assert outbox.state == expected_state
    assert posts["count"] == 1
    if reconcile_outcome == "multiple":
        from fastapi import BackgroundTasks, HTTPException

        from api.routes.feedback import update_feedback

        with pytest.raises(HTTPException) as exc:
            update_feedback(
                row.id,
                _approve_action(row),
                BackgroundTasks(),
                user_id="publication-admin",
                db=db,
            )
        assert exc.value.status_code == 409
        db.refresh(outbox)
        assert outbox.state == "manual_review"
        assert outbox.feedback_id == row.id


def _drive_preflight_multiple(publication_db, monkeypatch):
    from api import github_issues
    from api.feedback_publication import claim_next_send, enqueue_publication, send_claim
    from db.models import FeedbackPublicationAttempt

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Preflight multiple marker matches")
    outbox = enqueue_publication(db, row.id)
    db.commit()
    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda _marker, **_kwargs: {
            "outcome": "multiple",
            "number": None,
            "url": None,
            "http_status": 200,
            "error_code": "multiple_matches",
        },
    )
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("multiple preflight must never POST"),
    )
    claim = claim_next_send(db)
    assert claim is not None
    assert send_claim(db, *claim) == "manual_required"
    db.refresh(outbox)
    attempt = db.query(FeedbackPublicationAttempt).filter(
        FeedbackPublicationAttempt.outbox_id == outbox.id
    ).one()
    assert attempt.outcome == "not_sent"
    assert attempt.error_code == "multiple_marker_matches"
    assert outbox.state == "manual_review"
    assert outbox.delivery_evidence == "ambiguous"
    return db, row, outbox


def test_preflight_multiple_cannot_be_superseded_or_republished(
    publication_db,
    monkeypatch,
) -> None:
    from fastapi import BackgroundTasks, HTTPException

    from api.routes.feedback import update_feedback
    from db.models import FeedbackPublicationOutbox

    db, row, outbox = _drive_preflight_multiple(publication_db, monkeypatch)

    with pytest.raises(HTTPException) as exc:
        update_feedback(
            row.id,
            _approve_action(row),
            BackgroundTasks(),
            user_id="publication-admin",
            db=db,
        )

    assert exc.value.status_code == 409
    db.refresh(outbox)
    assert outbox.state == "manual_review"
    assert outbox.feedback_id == row.id
    assert outbox.delivery_evidence == "ambiguous"
    assert db.query(FeedbackPublicationOutbox).count() == 1


def test_admin_reject_preserves_preflight_multiple_evidence(
    publication_db,
    monkeypatch,
) -> None:
    from fastapi import BackgroundTasks, HTTPException

    from api.routes.feedback import FeedbackAction, update_feedback

    db, row, outbox = _drive_preflight_multiple(publication_db, monkeypatch)

    with pytest.raises(HTTPException) as exc:
        update_feedback(
            row.id,
            FeedbackAction(action="reject"),
            BackgroundTasks(),
            user_id="publication-admin",
            db=db,
        )

    assert exc.value.status_code == 409
    db.refresh(row)
    db.refresh(outbox)
    assert row.status == "needs_review"
    assert row.publication_status == "manual_required"
    assert outbox.state == "manual_review"
    assert outbox.delivery_evidence == "ambiguous"
    assert outbox.last_error_code == "multiple_marker_matches"


def test_known_rejection_retries_are_bounded(publication_db, monkeypatch) -> None:
    from api import github_issues
    from api.feedback_publication import claim_next_send, enqueue_publication, send_claim

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    posts = {"count": 0}
    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda _marker, **_kwargs: {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": 200,
            "error_code": "not_indexed_or_absent",
        },
    )

    def rejected(**_kwargs):
        posts["count"] += 1
        return {
            "outcome": "rejected",
            "number": None,
            "url": None,
            "http_status": 422,
            "error_code": "provider_rejected",
        }

    monkeypatch.setattr(github_issues, "create_issue_outcome", rejected)
    results = []
    for _ in range(3):
        outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        claim = claim_next_send(db)
        assert claim is not None
        results.append(send_claim(db, *claim))
        db.refresh(outbox)
    assert results == ["retry_wait", "retry_wait", "unavailable"]
    assert posts["count"] == 3
    assert outbox.state == "held"


@pytest.mark.parametrize("error_code", ("provider_failure", "auth_missing"))
def test_preflight_failures_are_bounded_without_post(
    publication_db, monkeypatch, error_code: str
) -> None:
    from api import github_issues
    from api.feedback_publication import (
        MAX_SEND_ATTEMPTS,
        claim_next_send,
        enqueue_publication,
        send_claim,
    )
    from db.models import FeedbackPublicationAttempt

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda _marker, **_kwargs: {
            "outcome": "provider_failure",
            "number": None,
            "url": None,
            "http_status": 503 if error_code == "provider_failure" else None,
            "error_code": error_code,
        },
    )
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("preflight failure must never POST"),
    )

    results = []
    for _ in range(MAX_SEND_ATTEMPTS):
        outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        claim = claim_next_send(db)
        assert claim is not None
        results.append(send_claim(db, *claim))
        db.refresh(outbox)

    assert results == ["retry_wait"] * (MAX_SEND_ATTEMPTS - 1) + [
        "unavailable"
    ]
    assert outbox.state == "held"
    assert outbox.attempt_count == MAX_SEND_ATTEMPTS
    assert (
        db.query(FeedbackPublicationAttempt)
        .filter(FeedbackPublicationAttempt.outbox_id == outbox.id)
        .count()
        == MAX_SEND_ATTEMPTS
    )
    outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert claim_next_send(db) is None


def test_outbox_feedback_binding_allows_detach_only(publication_db) -> None:
    from api.feedback_publication import enqueue_publication

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    other = _triaged_feedback(db, user_id, message="Other feedback")

    outbox.feedback_id = other.id
    with pytest.raises(Exception, match="immutable"):
        db.commit()
    db.rollback()

    db.refresh(outbox)
    outbox.feedback_id = None
    db.commit()
    assert outbox.feedback_id is None

    outbox.feedback_id = row.id
    with pytest.raises(Exception, match="immutable"):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(
    "field",
    ("payload_sha256", "public_content_sha256", "target_repo"),
)
def test_outbox_publication_binding_is_immutable(
    publication_db, field: str
) -> None:
    from api.feedback_publication import enqueue_publication

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    setattr(
        outbox,
        field,
        (
            "other/repo"
            if field == "target_repo"
            else "sha256:" + "0" * 64
        ),
    )
    with pytest.raises(Exception, match="immutable"):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("mutation", ("digest", "repo", "consent"))
def test_send_rechecks_payload_digest_repo_and_consent_gates(
    publication_db, monkeypatch, mutation: str
) -> None:
    from dataclasses import replace

    from api import github_issues
    from api import feedback_publication as publication
    from api.feedback_publication import claim_next_send, enqueue_publication, send_claim

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    if mutation == "digest":
        original = publication.build_publication_payload
        monkeypatch.setattr(
            publication,
            "build_publication_payload",
            lambda feedback, public_id: replace(
                original(feedback, public_id),
                digest="sha256:" + "0" * 64,
            ),
        )
    elif mutation == "repo":
        monkeypatch.setattr(github_issues, "FEEDBACK_REPOSITORY", "other/repo")
    else:
        row.publication_consent_version = "feedback-publication-v1"
        db.commit()
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("failed gate must not send"),
    )
    claim = claim_next_send(db)
    if mutation == "repo":
        assert claim is None
        db.refresh(outbox)
        assert outbox.state == "pending"
        assert outbox.attempt_count == 0
        assert row.github_issue_number is None
        return
    assert claim is not None
    result = send_claim(db, *claim)
    assert result == ("manual_required" if mutation == "digest" else "unavailable")
    db.refresh(row)
    assert row.github_issue_number is None


def test_created_response_lost_before_commit_reconciles_without_resend(
    publication_db, monkeypatch
) -> None:
    from api import feedback_publication as publication, github_issues
    from api.feedback_publication import (
        claim_next_reconciliation,
        claim_next_send,
        enqueue_publication,
        reconcile_claim,
        recover_expired_leases,
        send_claim,
    )

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    outbox = enqueue_publication(db, row.id)
    db.commit()
    calls = {"post": 0, "reconcile": 0}

    def reconcile(_marker: str, **_kwargs):
        calls["reconcile"] += 1
        if calls["reconcile"] == 1:
            return {
                "outcome": "unknown",
                "number": None,
                "url": None,
                "http_status": 200,
                "error_code": "not_indexed_or_absent",
            }
        return {
            "outcome": "reconciled",
            "number": 88,
            "url": "https://github.com/praxys-run/praxys/issues/88",
            "http_status": 200,
            "error_code": None,
        }

    def created(**_kwargs):
        calls["post"] += 1
        return {
            "outcome": "created",
            "number": 88,
            "url": "https://github.com/praxys-run/praxys/issues/88",
            "http_status": 201,
            "error_code": None,
        }

    monkeypatch.setattr(github_issues, "reconcile_issue_marker", reconcile)
    monkeypatch.setattr(github_issues, "create_issue_outcome", created)
    original_mark_published = publication._mark_published
    monkeypatch.setattr(
        publication,
        "_mark_published",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic finalization crash")
        ),
    )
    claim = claim_next_send(db)
    assert claim is not None
    with pytest.raises(RuntimeError, match="finalization crash"):
        send_claim(db, *claim)
    db.rollback()
    db.refresh(outbox)
    assert outbox.state == "sending"
    outbox.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert recover_expired_leases(db) == 1
    db.refresh(outbox)
    outbox.available_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(publication, "_mark_published", original_mark_published)
    monkeypatch.setattr(github_issues, "reconcile_issue_marker", reconcile)
    monkeypatch.setattr(
        github_issues,
        "create_issue_outcome",
        lambda **_kwargs: pytest.fail("recovery must not send a second POST"),
    )
    reconciliation = claim_next_reconciliation(db)
    assert reconciliation is not None
    assert reconcile_claim(db, *reconciliation) == "published"
    assert calls["post"] == 1
    db.refresh(row)
    assert row.github_issue_number == 88


def test_admin_publication_queue_is_metadata_only_and_no_store(
    publication_db,
) -> None:
    import json

    from fastapi import Response

    from api.feedback_publication import enqueue_publication
    from api.routes.feedback import feedback_publication_queue

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="private sentinel body")
    enqueue_publication(db, row.id)
    db.commit()
    response = Response()

    payload = feedback_publication_queue(
        response,
        user_id="publication-admin",
        db=db,
    )
    serialized = json.dumps(payload)
    assert response.headers["Cache-Control"] == "private, no-store"
    for forbidden in (
        "private sentinel body",
        user_id,
        row.ai_title,
        row.ai_body,
        "public_id",
        "payload_sha256",
        "image_description",
    ):
        assert forbidden not in serialized


def test_postgres_claim_path_is_skip_locked() -> None:
    from sqlalchemy import create_mock_engine
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Session

    from api.feedback_publication import _claim_query

    engine = create_mock_engine("postgresql+psycopg://", lambda *_args, **_kw: None)
    with Session(bind=engine) as db:
        query = _claim_query(
            db,
            states=("pending", "retry_wait"),
            now=datetime(2026, 9, 4),
            attached_only=True,
        )
        sql = " ".join(
            str(
                query.statement.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).split()
        )

    assert "ORDER BY feedback_publication_outbox.available_at ASC" in sql
    assert "feedback_publication_outbox.created_at ASC" in sql
    assert "feedback_publication_outbox.id ASC" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_direct_enqueue_locks_user_before_feedback(
    publication_db, monkeypatch
) -> None:
    """Even direct callers enter the shared U->F order before creating O."""
    from sqlalchemy.orm import Query

    from api.feedback_publication import enqueue_publication
    from db.models import Feedback, User

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    lock_events: list[str] = []
    original_with_for_update = Query.with_for_update

    def _record_lock(query, *args, **kwargs):
        entities = {
            description.get("entity") for description in query.column_descriptions
        }
        if User in entities:
            lock_events.append("user")
        elif Feedback in entities:
            lock_events.append("feedback")
        return original_with_for_update(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", _record_lock)
    assert enqueue_publication(db, row.id) is not None
    db.commit()

    assert lock_events[:2] == ["user", "feedback"]


def test_inactive_enqueue_locks_user_by_pk_and_stops_before_feedback(
    publication_db, monkeypatch
) -> None:
    """An inactive predicate cannot make U disappear before activity validation."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Query

    from api.feedback_publication import enqueue_publication
    from db.models import Feedback, User

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id)
    user = db.get(User, user_id)
    user.is_active = False
    db.commit()
    lock_events: list[str] = []
    lock_sql: dict[str, str] = {}
    original_with_for_update = Query.with_for_update

    def _record_lock(query, *args, **kwargs):
        entities = {
            description.get("entity") for description in query.column_descriptions
        }
        name = None
        if User in entities:
            name = "user"
        elif Feedback in entities:
            name = "feedback"
        locked = original_with_for_update(query, *args, **kwargs)
        if name is not None:
            lock_events.append(name)
            lock_sql[name] = " ".join(
                str(locked.statement.compile(dialect=postgresql.dialect())).split()
            )
        return locked

    monkeypatch.setattr(Query, "with_for_update", _record_lock)
    dialect = db.get_bind().dialect
    original_name = dialect.name
    dialect.name = "postgresql"
    try:
        assert enqueue_publication(db, row.id) is None
    finally:
        db.rollback()
        dialect.name = original_name

    assert lock_events == ["user"]
    assert "WHERE users.id =" in lock_sql["user"]
    user_where = lock_sql["user"].split(" WHERE ", 1)[1].split(" ORDER BY ", 1)[0]
    assert "users.is_active" not in user_where
    assert "ORDER BY users.id ASC" in lock_sql["user"]
    assert "FOR UPDATE OF users" in lock_sql["user"]


def test_triage_locks_user_before_feedback(publication_db, monkeypatch) -> None:
    """Background triage cannot hold F while waiting behind deletion's U."""
    from sqlalchemy.orm import Query

    from api.feedback_triage import triage_and_publish
    from db.models import Feedback, User

    db, user_id = publication_db
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="Lock the owner before private feedback",
        status="new",
        publication_status="private",
    )
    db.add(row)
    db.commit()
    lock_events: list[str] = []
    original_with_for_update = Query.with_for_update

    def _record_lock(query, *args, **kwargs):
        entities = {
            description.get("entity") for description in query.column_descriptions
        }
        if User in entities:
            lock_events.append("user")
        elif Feedback in entities:
            lock_events.append("feedback")
        return original_with_for_update(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", _record_lock)
    result = triage_and_publish(row.id, _session=db)

    assert result["status"] == "triaged"
    assert lock_events[:2] == ["user", "feedback"]


@pytest.mark.parametrize(
    ("action", "expected_prefix"),
    (
        ("retry", ["user", "feedback"]),
        ("approve", ["user", "feedback"]),
        ("reject", ["user", "outbox", "feedback"]),
    ),
)
def test_admin_actions_follow_user_first_lock_order(
    publication_db,
    monkeypatch,
    action: str,
    expected_prefix: list[str],
) -> None:
    """Every admin mutation owns U before F; reject owns O before F."""
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Query

    from api.feedback_publication import enqueue_publication
    from api.routes.feedback import FeedbackAction, update_feedback
    from db.models import Feedback, FeedbackPublicationOutbox, User

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message=f"Admin {action} lock order")
    if action == "approve":
        row.status = "needs_review"
        row.publication_status = "manual_required"
        db.commit()
    elif action == "reject":
        assert enqueue_publication(db, row.id) is not None
        db.commit()

    lock_events: list[str] = []
    original_with_for_update = Query.with_for_update

    def _record_lock(query, *args, **kwargs):
        entities = {
            description.get("entity") for description in query.column_descriptions
        }
        if User in entities:
            lock_events.append("user")
        elif FeedbackPublicationOutbox in entities:
            lock_events.append("outbox")
        elif Feedback in entities:
            lock_events.append("feedback")
        return original_with_for_update(query, *args, **kwargs)

    monkeypatch.setattr(Query, "with_for_update", _record_lock)
    dialect = db.get_bind().dialect
    original_name = dialect.name
    dialect.name = "postgresql"
    try:
        payload = _approve_action(row) if action == "approve" else FeedbackAction(action=action)
        update_feedback(
            row.id,
            payload,
            BackgroundTasks(),
            user_id="publication-admin",
            db=db,
        )
    finally:
        dialect.name = original_name

    assert lock_events[: len(expected_prefix)] == expected_prefix
    if action == "reject":
        assert lock_events.count("outbox") == 1


def test_expired_recovery_locks_outbox_attempt_feedback_in_order(
    publication_db, monkeypatch
) -> None:
    """Batch recovery uses exact, stable O->A->F PostgreSQL row locks."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Query

    from api.feedback_publication import (
        claim_next_send,
        enqueue_publication,
        recover_expired_leases,
    )
    from db.models import (
        Feedback,
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
    )

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Expired recovery lock order")
    outbox = enqueue_publication(db, row.id)
    db.commit()
    assert outbox is not None
    assert claim_next_send(db) is not None
    db.refresh(outbox)
    outbox.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    lock_events: list[str] = []
    lock_sql: dict[str, str] = {}
    original_with_for_update = Query.with_for_update

    def _record_lock(query, *args, **kwargs):
        entities = {
            description.get("entity") for description in query.column_descriptions
        }
        name = None
        if FeedbackPublicationOutbox in entities:
            name = "outbox"
        elif FeedbackPublicationAttempt in entities:
            name = "attempt"
        elif Feedback in entities:
            name = "feedback"
        locked = original_with_for_update(query, *args, **kwargs)
        if name is not None:
            lock_events.append(name)
            lock_sql[name] = " ".join(
                str(locked.statement.compile(dialect=postgresql.dialect())).split()
            )
        return locked

    monkeypatch.setattr(Query, "with_for_update", _record_lock)
    dialect = db.get_bind().dialect
    original_name = dialect.name
    dialect.name = "postgresql"
    try:
        assert recover_expired_leases(db) == 1
    finally:
        dialect.name = original_name

    assert lock_events == ["outbox", "attempt", "feedback"]
    assert "ORDER BY feedback_publication_outbox.id ASC" in lock_sql["outbox"]
    assert "FOR UPDATE OF feedback_publication_outbox" in lock_sql["outbox"]
    assert "ORDER BY feedback_publication_attempts.id ASC" in lock_sql["attempt"]
    assert "FOR UPDATE OF feedback_publication_attempts" in lock_sql["attempt"]
    assert "ORDER BY feedback.id ASC" in lock_sql["feedback"]
    assert "FOR UPDATE OF feedback" in lock_sql["feedback"]


def test_owner_status_http_contract_is_private_and_indistinguishable(
    publication_db,
    monkeypatch,
    caplog,
) -> None:
    """Owner status is minimal; absent and cross-owner reads fail alike."""
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from api.auth import get_current_user_id
    from api.main import (
        FeedbackOwnerStatusPrivacyMiddleware,
        _is_feedback_owner_status_path,
    )
    from api.routes.feedback import router
    from db import session as db_session
    from db.session import get_db

    db, user_id = publication_db
    row = _triaged_feedback(db, user_id, message="Private owner status")
    row.id = 8765432101234
    row.publication_status = "private"
    row.github_issue_number = None
    row.github_issue_url = None
    db.commit()

    app = FastAPI()
    app.add_middleware(FeedbackOwnerStatusPrivacyMiddleware)
    app.include_router(router, prefix="/api")
    current_user: dict[str, str | None] = {"id": user_id}
    observed_dependency_paths: list[str] = []
    status_path = "/api/me/feedback/status"
    caplog.set_level("INFO", logger="api.routes.feedback")
    monkeypatch.setattr(
        "api.routes.feedback.telemetry.record_feedback",
        lambda **_kwargs: pytest.fail("status lookup must not emit telemetry"),
    )

    def _current_user(request: Request) -> str:
        observed_dependency_paths.append(request.url.path)
        value = current_user["id"]
        if value is None:
            raise HTTPException(401, "Not authenticated")
        if value == "forbidden":
            raise HTTPException(403, "Forbidden")
        return value

    def _db():
        request_db = db_session.SessionLocal()
        try:
            yield request_db
        finally:
            request_db.close()

    app.dependency_overrides[get_current_user_id] = _current_user
    app.dependency_overrides[get_db] = _db

    with TestClient(app) as client:
        owner = client.post(status_path, json={"feedback_id": row.id})
        wrong_method = client.get(status_path)
        old_dynamic_get = client.get(f"/api/me/feedback/{row.id}")
        current_user["id"] = "publication-admin"
        outsider = client.post(status_path, json={"feedback_id": row.id})
        nonexistent = client.post(
            status_path,
            json={"feedback_id": 8765432101235},
        )
        safe_max_nonexistent = client.post(
            status_path,
            json={"feedback_id": 9007199254740991},
        )
        invalid = [
            client.post(status_path, json={"feedback_id": value})
            for value in (
                False,
                1.5,
                0,
                -1,
                9007199254740992,
                "8765432101234",
                None,
            )
        ]
        current_user["id"] = "forbidden"
        forbidden = client.post(status_path, json={"feedback_id": row.id})
        current_user["id"] = None
        unauthenticated = client.post(status_path, json={"feedback_id": row.id})

    assert owner.status_code == 200
    assert owner.json() == {
        "id": row.id,
        "publication": {"status": "private", "issue_url": None},
    }
    assert owner.headers["Cache-Control"] == "private, no-store"
    assert outsider.status_code == nonexistent.status_code == 404
    assert outsider.json() == nonexistent.json()
    assert outsider.headers["Cache-Control"] == "private, no-store"
    assert nonexistent.headers["Cache-Control"] == "private, no-store"
    assert safe_max_nonexistent.status_code == 404
    assert safe_max_nonexistent.headers["Cache-Control"] == "private, no-store"
    assert all(response.status_code == 422 for response in invalid)
    assert all(
        response.headers["Cache-Control"] == "private, no-store"
        for response in invalid
    )
    assert forbidden.status_code == 403
    assert forbidden.headers["Cache-Control"] == "private, no-store"
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["Cache-Control"] == "private, no-store"
    assert wrong_method.status_code == 405
    assert wrong_method.headers["Cache-Control"] == "private, no-store"
    assert old_dynamic_get.status_code == 404
    assert _is_feedback_owner_status_path(status_path) is True
    assert _is_feedback_owner_status_path(f"/api/me/feedback/{row.id}") is False
    assert _is_feedback_owner_status_path(
        f"/api/me/feedback/{row.id}/image/0"
    ) is False
    assert _is_feedback_owner_status_path("/api/admin/feedback/1") is False
    assert observed_dependency_paths
    assert set(observed_dependency_paths) == {status_path}
    assert str(row.id) not in "\n".join(observed_dependency_paths)
    assert str(row.id) not in caplog.text


def test_production_app_registers_feedback_owner_status_privacy_middleware(
) -> None:
    from api.main import FeedbackOwnerStatusPrivacyMiddleware, app

    assert sum(
        middleware.cls is FeedbackOwnerStatusPrivacyMiddleware
        for middleware in app.user_middleware
    ) == 1
