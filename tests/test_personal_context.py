"""Privacy and lifecycle tests for encrypted adaptive-plan context."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def context_db(monkeypatch):
    """Yield isolated sessions with durable local envelope encryption."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", raising=False)
    monkeypatch.delenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        raising=False,
    )
    monkeypatch.delenv(
        "PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL",
        raising=False,
    )
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")

    from db import crypto, session as db_session

    crypto._vault = None
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db.models import User

    with db_session.SessionLocal() as db:
        db.add_all([
            User(
                id="context-owner",
                email="owner@example.test",
                hashed_password="x",
                terms_version=TERMS_VERSION,
                terms_digest=TERMS_CONTENT_DIGEST,
            ),
            User(id="context-other", email="other@example.test", hashed_password="x"),
        ])
        db.commit()
    try:
        yield db_session
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        crypto._vault = None
        tmpdir.cleanup()


def _create_context(
    db,
    *,
    user_id: str = "context-owner",
    now: datetime,
    expires_at: datetime | None = None,
    purge_after: datetime | None = None,
    narrative: str | None = "Synthetic private context",
):
    from api.personal_context import create_context_item

    payload = {
        "category": "caregiving",
        "fields": {
            "maximum_available_minutes": 30,
            "affected_days": ["monday", "wednesday"],
        },
    }
    if narrative is not None:
        payload["narrative"] = narrative
    return create_context_item(
        db,
        user_id=user_id,
        kind="temporary_constraint",
        purpose="plan_adjustment",
        payload=payload,
        source_actor_type="first_party_web",
        starts_at=now,
        expires_at=expires_at or now + timedelta(days=14),
        purge_after=purge_after or now + timedelta(days=44),
        now=now,
    )


def test_payload_is_encrypted_and_reads_are_owner_isolated(context_db) -> None:
    from api.personal_context import (
        PersonalContextUnavailable,
        append_purpose_receipt,
        load_active_contexts,
        record_context_use,
    )
    from db.models import PersonalContextItem

    now = datetime(2026, 8, 1, 9, 0)
    with context_db.SessionLocal() as db:
        item = _create_context(db, now=now)
        item_id = item.id
        db.commit()

        stored = db.get(PersonalContextItem, item_id)
        assert stored is not None
        ciphertext = bytes(stored.encrypted_payload)
        assert b"caregiving" not in ciphertext
        assert b"Synthetic private context" not in ciphertext
        assert "category" not in PersonalContextItem.__table__.columns
        assert "narrative" not in PersonalContextItem.__table__.columns

        structured = load_active_contexts(
            db,
            user_id="context-owner",
            purpose="plan_adjustment",
            now=now,
        )
        private = load_active_contexts(
            db,
            user_id="context-owner",
            purpose="plan_adjustment",
            include_narrative=True,
            now=now,
        )
        other = load_active_contexts(
            db,
            user_id="context-other",
            purpose="plan_adjustment",
            include_narrative=True,
            now=now,
        )
        assert structured[0].category == "caregiving"
        assert structured[0].narrative is None
        assert private[0].narrative == "Synthetic private context"
        assert other == []

        with pytest.raises(PersonalContextUnavailable):
            append_purpose_receipt(
                db,
                user_id="context-other",
                item_id=item_id,
                expected_version=1,
                consent_text_version="personal-context-purpose-v1",
                client="web",
                idempotency_key="other-user-purpose-confirmation",
                now=now,
            )
        db.rollback()

        consent = append_purpose_receipt(
            db,
            user_id="context-owner",
            item_id=item_id,
            expected_version=1,
            consent_text_version="personal-context-purpose-v1",
            client="web",
            idempotency_key="owner-purpose-confirmation",
            now=now,
        )
        use = record_context_use(
            db,
            user_id="context-owner",
            item_id=item_id,
            purpose="plan_adjustment",
            consumer_type="planning_ai",
            consumer_name="adaptive-plan-v1",
            disclosed_fields=["category"],
            prompt_version="adaptive-plan-v1",
            now=now,
        )
        db.commit()
        assert use.consent_receipt_id == consent.id
        assert use.context_item_id == item_id
        assert use.context_version == 1
        assert use.purpose == "plan_adjustment"
        assert use.disclosed_fields == ["category"]
        assert consent.consent_scope == "purpose_confirmation"


def test_ephemeral_encryption_key_refuses_durable_context(
    context_db,
    monkeypatch,
) -> None:
    from api.personal_context import PersonalContextAccessError
    from db import crypto

    monkeypatch.delenv("PRAXYS_LOCAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("LOCAL_ENCRYPTION_KEY", raising=False)
    crypto._vault = None
    now = datetime(2026, 8, 1, 9, 0)
    with context_db.SessionLocal() as db:
        with pytest.raises(PersonalContextAccessError):
            _create_context(db, now=now)
        db.rollback()


def test_expiry_is_enforced_before_retention_purge(context_db) -> None:
    from api.personal_context import load_active_contexts, run_retention
    from db.models import PersonalContextItem

    captured_at = datetime(2026, 8, 1, 9, 0)
    expired_at = captured_at + timedelta(days=1)
    with context_db.SessionLocal() as db:
        item = _create_context(
            db,
            now=captured_at,
            expires_at=expired_at,
            purge_after=expired_at + timedelta(days=30),
            narrative=None,
        )
        item_id = item.id
        db.commit()

        assert load_active_contexts(
            db,
            user_id="context-owner",
            purpose="plan_adjustment",
            now=expired_at,
        ) == []
        assert db.get(PersonalContextItem, item_id).state == "active"

        result = run_retention(db, now=expired_at)
        assert result.expired == 1
        assert db.get(PersonalContextItem, item_id).state == "expired"


def test_correction_appends_version_and_does_not_carry_ai_consent(
    context_db,
) -> None:
    from api.personal_context import (
        PersonalContextUnavailable,
        append_consent_receipt,
        correct_context_item,
        load_active_contexts,
    )
    from db.models import PersonalContextItem

    now = datetime(2026, 8, 1, 9, 0)
    corrected_at = now + timedelta(hours=1)
    with context_db.SessionLocal() as db:
        item = _create_context(db, now=now)
        append_consent_receipt(
            db,
            user_id="context-owner",
            item_id=item.id,
            expected_version=1,
            decision="granted",
            provider="azure_openai",
            disclosed_fields=["category"],
            consent_text_version="context-ai-v1",
            client="web",
            now=now,
        )
        db.commit()

        successor = correct_context_item(
            db,
            user_id="context-owner",
            item_id=item.id,
            expected_version=1,
            payload={
                "category": "less_time",
                "fields": {"maximum_available_minutes": 45},
            },
            source_actor_type="first_party_web",
            starts_at=corrected_at,
            expires_at=corrected_at + timedelta(days=7),
            purge_after=corrected_at + timedelta(days=37),
            now=corrected_at,
        )
        successor_id = successor.id
        db.commit()

        rows = (
            db.query(PersonalContextItem)
            .filter(PersonalContextItem.lineage_id == item.lineage_id)
            .order_by(PersonalContextItem.version)
            .all()
        )
        assert [(row.version, row.state) for row in rows] == [
            (1, "expired"),
            (2, "active"),
        ]
        assert rows[1].supersedes_id == rows[0].id
        assert rows[1].processing_mode == "deterministic_only"
        assert rows[1].consent_receipt_id is None
        loaded = load_active_contexts(
            db,
            user_id="context-owner",
            purpose="plan_adjustment",
            now=corrected_at,
        )
        assert [entry.item_id for entry in loaded] == [successor_id]
        assert loaded[0].category == "less_time"

        with pytest.raises(PersonalContextUnavailable):
            correct_context_item(
                db,
                user_id="context-owner",
                item_id=item.id,
                expected_version=1,
                payload={"category": "other", "fields": {}},
                source_actor_type="first_party_web",
                starts_at=corrected_at,
                expires_at=corrected_at + timedelta(days=7),
                purge_after=corrected_at + timedelta(days=37),
                now=corrected_at,
            )
        db.rollback()


def test_narrative_purge_rewrites_ciphertext_and_manifest_is_payload_free(
    context_db,
) -> None:
    from api import personal_context_deletion_storage
    from api.personal_context import load_active_contexts, run_retention
    from db.crypto import get_vault
    from db.models import (
        PersonalContextDeletionJob,
        PersonalContextItem,
        PlanRevision,
    )

    captured_at = datetime(2026, 8, 1, 9, 0)
    purge_time = captured_at + timedelta(days=31)
    before = [{"date": "2026-08-02", "workout_type": "long"}]
    after = [{"date": "2026-08-02", "workout_type": "easy"}]
    with context_db.SessionLocal() as db:
        item = _create_context(
            db,
            now=captured_at,
            expires_at=captured_at + timedelta(days=60),
            purge_after=captured_at + timedelta(days=90),
        )
        item_id = item.id
        original_ciphertext = bytes(item.encrypted_payload)
        revision = PlanRevision(
            user_id="context-owner",
            operation="upsert",
            actor_type="user",
            actor_id="context-owner",
            origin="test",
            before_snapshot=before,
            after_snapshot=after,
            details={
                "context_item_ids": [item.id],
                "private_context_rationale": "Synthetic private context",
                "rationale": "Synthetic private context",
                "rationale_is_private": True,
                "personal_context": {
                    "item_ids": [item.id],
                    "category": "caregiving",
                },
            },
        )
        db.add(revision)
        db.commit()

        result = run_retention(db, now=purge_time)
        assert result.narratives_purged == 1
        stored = db.get(PersonalContextItem, item_id)
        assert stored is not None
        assert stored.has_narrative is False
        assert stored.narrative_purged_at == purge_time
        assert bytes(stored.encrypted_payload) != original_ciphertext
        decrypted = json.loads(get_vault().decrypt(
            stored.encrypted_payload,
            stored.wrapped_dek,
        ))
        assert "narrative" not in decrypted
        assert load_active_contexts(
            db,
            user_id="context-owner",
            purpose="plan_adjustment",
            include_narrative=True,
            now=purge_time,
        )[0].narrative is None
        preserved = db.get(PlanRevision, revision.id)
        assert preserved.before_snapshot == before
        assert preserved.after_snapshot == after
        assert preserved.details["context_item_ids"] == [item_id]
        assert preserved.details["personal_context"]["category"] == "caregiving"
        assert preserved.details["rationale"] == (
            "Personal context removed by athlete"
        )
        assert "private_context_rationale" not in preserved.details
        assert "rationale_is_private" not in preserved.details
        assert "Synthetic private context" not in json.dumps(
            preserved.details
        )
        job = db.query(PersonalContextDeletionJob).one()
        assert job.status == "completed"
        assert job.operation == "purge_narrative"

    manifests = list(
        personal_context_deletion_storage.iter_active(now=purge_time)
    )
    assert len(manifests) == 1
    serialized = json.dumps(manifests[0], default=str)
    assert "caregiving" not in serialized
    assert "Synthetic private context" not in serialized
    assert manifests[0]["status"] == "completed"


def test_startup_retention_fails_closed_when_narrative_cannot_be_purged(
    context_db,
) -> None:
    from api.personal_context import (
        PersonalContextDeletionError,
        run_retention,
    )
    from db.models import PersonalContextDeletionJob, PersonalContextItem

    captured_at = datetime(2026, 8, 1, 9, 0)
    purge_time = captured_at + timedelta(days=31)
    with context_db.SessionLocal() as db:
        item = _create_context(
            db,
            now=captured_at,
            expires_at=captured_at + timedelta(days=60),
            purge_after=captured_at + timedelta(days=90),
        )
        item_id = item.id
        db.commit()
        stored = db.get(PersonalContextItem, item_id)
        stored.encrypted_payload = b"corrupt"
        db.commit()

        with pytest.raises(PersonalContextDeletionError):
            run_retention(
                db,
                now=purge_time,
                raise_on_failure=True,
            )
        db.expire_all()
        assert db.get(PersonalContextItem, item_id).has_narrative is True
        job = db.query(PersonalContextDeletionJob).one()
        assert job.status == "failed"


def test_withdrawal_deletes_private_derivatives_but_keeps_workout_facts(
    context_db,
) -> None:
    from api.personal_context import (
        append_purpose_receipt,
        record_context_use,
        withdraw_context,
    )
    from db.models import (
        PersonalContextConsentReceipt,
        PersonalContextDeletionJob,
        PersonalContextItem,
        PersonalContextUseReceipt,
        PlanRevision,
    )

    now = datetime(2026, 8, 1, 9, 0)
    before = [{"date": "2026-08-02", "workout_type": "long"}]
    after = [{"date": "2026-08-02", "workout_type": "easy"}]
    with context_db.SessionLocal() as db:
        item = _create_context(db, now=now)
        consent = append_purpose_receipt(
            db,
            user_id="context-owner",
            item_id=item.id,
            expected_version=1,
            consent_text_version="personal-context-purpose-v1",
            client="web",
            idempotency_key="withdrawal-purpose-confirmation",
            now=now,
        )
        use = record_context_use(
            db,
            user_id="context-owner",
            item_id=item.id,
            purpose="plan_adjustment",
            consumer_type="planning_ai",
            consumer_name="adaptive-plan-v1",
            disclosed_fields=["category"],
            now=now,
        )
        revision = PlanRevision(
            user_id="context-owner",
            operation="upsert",
            actor_type="user",
            actor_id="context-owner",
            origin="test",
            before_snapshot=before,
            after_snapshot=after,
            details={
                "context_item_ids": [item.id],
                "context_use_receipt_ids": [use.id],
                "private_context_rationale": "Synthetic private context",
                "rationale": "Synthetic private context",
                "rationale_is_private": True,
                "personal_context": {
                    "item_ids": [item.id],
                    "category": "caregiving",
                },
            },
        )
        db.add(revision)
        item_id = item.id
        consent_id = consent.id
        use_id = use.id
        db.commit()

        assert withdraw_context(
            db,
            user_id="context-owner",
            item_id=item_id,
            now=now + timedelta(minutes=1),
        )
        assert db.get(PersonalContextItem, item_id) is None
        assert db.get(PersonalContextConsentReceipt, consent_id) is None
        assert db.get(PersonalContextUseReceipt, use_id) is None
        job = db.query(PersonalContextDeletionJob).one()
        assert job.status == "completed"

        preserved = db.get(PlanRevision, revision.id)
        assert preserved.before_snapshot == before
        assert preserved.after_snapshot == after
        assert preserved.details["rationale"] == (
            "Personal context removed by athlete"
        )
        assert preserved.details["personal_context_status"] == (
            "removed_by_athlete"
        )
        serialized = json.dumps(preserved.details)
        assert "Synthetic private context" not in serialized
        assert "caregiving" not in serialized
        assert item_id not in serialized


def test_failed_cleanup_stays_unusable_and_retries(context_db, monkeypatch) -> None:
    from api import personal_context
    from api.personal_context import (
        PersonalContextDeletionError,
        load_active_contexts,
        retry_deletion_jobs,
        withdraw_context,
    )
    from db.models import PersonalContextDeletionJob, PersonalContextItem

    now = datetime(2026, 8, 1, 9, 0)
    with context_db.SessionLocal() as db:
        item = _create_context(db, now=now)
        item_id = item.id
        db.commit()

        original = personal_context._apply_deletion_job

        def fail_cleanup(*_args, **_kwargs):
            raise RuntimeError("synthetic cleanup failure")

        monkeypatch.setattr(
            personal_context,
            "_apply_deletion_job",
            fail_cleanup,
        )
        with pytest.raises(PersonalContextDeletionError):
            withdraw_context(
                db,
                user_id="context-owner",
                item_id=item_id,
                now=now + timedelta(minutes=1),
            )
        db.expire_all()
        assert db.get(PersonalContextItem, item_id).state == "deleting"
        job = db.query(PersonalContextDeletionJob).one()
        assert job.status == "failed"
        assert load_active_contexts(
            db,
            user_id="context-owner",
            purpose="plan_adjustment",
            include_narrative=True,
            now=now + timedelta(minutes=2),
        ) == []

        monkeypatch.setattr(
            personal_context,
            "_apply_deletion_job",
            original,
        )
        completed, failed = retry_deletion_jobs(
            db,
            now=now + timedelta(minutes=2),
        )
        assert (completed, failed) == (1, 0)
        assert db.get(PersonalContextItem, item_id) is None
        assert db.get(PersonalContextDeletionJob, job.id).status == "completed"


def test_withdrawal_fails_closed_when_manifest_storage_is_unavailable(
    context_db,
    monkeypatch,
) -> None:
    from api import personal_context_deletion_storage
    from api.personal_context import (
        PersonalContextDeletionError,
        withdraw_context,
    )
    from db.models import PersonalContextDeletionJob, PersonalContextItem

    now = datetime(2026, 8, 1, 9, 0)
    with context_db.SessionLocal() as db:
        item = _create_context(db, now=now)
        item_id = item.id
        db.commit()

        monkeypatch.setattr(
            personal_context_deletion_storage,
            "store_requested",
            lambda **_kwargs: (_ for _ in ()).throw(
                personal_context_deletion_storage.DeletionManifestStorageError(
                    "unavailable"
                )
            ),
        )
        with pytest.raises(PersonalContextDeletionError):
            withdraw_context(
                db,
                user_id="context-owner",
                item_id=item_id,
                now=now + timedelta(minutes=1),
            )
        db.expire_all()
        assert db.get(PersonalContextItem, item_id).state == "active"
        assert db.query(PersonalContextDeletionJob).count() == 0


def test_external_manifest_replays_after_database_restore(context_db) -> None:
    from api import personal_context_deletion_storage
    from api.personal_context import replay_deletion_manifests
    from db.models import PersonalContextItem

    now = datetime(2026, 8, 1, 9, 0)
    with context_db.SessionLocal() as db:
        item = _create_context(db, now=now)
        item_id = item.id
        lineage_id = item.lineage_id
        db.commit()

        personal_context_deletion_storage.store_requested(
            job_id=str(uuid4()),
            user_id="context-owner",
            operation="delete_lineage",
            reason="withdrawal",
            lineage_id=lineage_id,
            requested_at=now + timedelta(minutes=1),
        )
        assert replay_deletion_manifests(
            db,
            now=now + timedelta(minutes=2),
        ) == 1
        assert db.get(PersonalContextItem, item_id) is None


def test_account_manifest_replay_removes_context_created_after_request(
    context_db,
) -> None:
    from api import personal_context_deletion_storage
    from api.personal_context import replay_deletion_manifests
    from db.models import PersonalContextItem

    now = datetime(2026, 8, 1, 9, 0)
    with context_db.SessionLocal() as db:
        first = _create_context(db, now=now)
        db.commit()
        personal_context_deletion_storage.store_requested(
            job_id=str(uuid4()),
            user_id="context-owner",
            operation="delete_owner_context",
            reason="account_deletion",
            requested_at=now + timedelta(minutes=1),
        )
        second = _create_context(
            db,
            now=now + timedelta(minutes=2),
        )
        first_id = first.id
        second_id = second.id
        db.commit()

        assert replay_deletion_manifests(
            db,
            now=now + timedelta(minutes=3),
        ) == 2
        assert db.get(PersonalContextItem, first_id) is None
        assert db.get(PersonalContextItem, second_id) is None


def test_owner_constraints_cascade_and_reject_cross_owner_receipts() -> None:
    from db.crypto import CredentialVault
    from db.models import (
        Base,
        PersonalContextConsentReceipt,
        PersonalContextItem,
        PersonalContextUseReceipt,
        User,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enforce_fks(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    vault = CredentialVault()
    encrypted, wrapped = vault.encrypt(json.dumps({
        "category": "other",
        "fields": {},
    }))
    item_id = str(uuid4())
    db = Session()
    try:
        db.add_all([
            User(id="owner-a", email="a@example.test", hashed_password="x"),
            User(id="owner-b", email="b@example.test", hashed_password="x"),
        ])
        db.commit()
        db.add(PersonalContextItem(
            id=item_id,
            lineage_id=str(uuid4()),
            user_id="owner-a",
            version=1,
            kind="temporary_constraint",
            purpose="plan_adjustment",
            state="active",
            encrypted_payload=encrypted,
            wrapped_dek=wrapped,
            payload_schema_version=1,
            has_narrative=False,
            source_actor_type="first_party_web",
            processing_mode="deterministic_only",
            starts_at=datetime(2026, 8, 1),
            expires_at=datetime(2026, 8, 2),
            purge_after=datetime(2026, 9, 1),
        ))
        db.commit()

        db.add(PersonalContextConsentReceipt(
            id=str(uuid4()),
            user_id="owner-b",
            context_item_id=item_id,
            context_version=1,
            purpose="plan_adjustment",
            disclosed_fields=[],
            consent_text_version="v1",
            decision="denied",
            client="web",
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        consent = PersonalContextConsentReceipt(
            id=str(uuid4()),
            user_id="owner-a",
            context_item_id=item_id,
            context_version=1,
            purpose="plan_adjustment",
            disclosed_fields=[],
            consent_text_version="v1",
            decision="denied",
            client="web",
        )
        db.add(consent)
        db.commit()
        db.add(PersonalContextUseReceipt(
            id=str(uuid4()),
            user_id="owner-a",
            context_item_id=item_id,
            context_version=1,
            purpose="plan_adjustment",
            consumer_type="deterministic_policy",
            consumer_name="test-policy",
            disclosed_fields=["category"],
        ))
        db.commit()

        db.query(User).filter(User.id == "owner-a").delete(
            synchronize_session=False
        )
        db.commit()
        assert db.query(PersonalContextItem).count() == 0
        assert db.query(PersonalContextConsentReceipt).count() == 0
        assert db.query(PersonalContextUseReceipt).count() == 0
    finally:
        db.close()
        engine.dispose()
