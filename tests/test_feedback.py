"""Tests for the in-app feedback feature.

Covers the deterministic PII scrub, the submit endpoint (persist + schedule +
rate-limit), the background triage pipeline (scrub-before-publish + the
no-GitHub "triaged" terminal state), and the admin list / retry / reject
actions. Route functions are called directly (passing user_id + db) — the same
dependency-bypass pattern as tests/test_announcements.py.
"""
from __future__ import annotations

import base64
import json
import tempfile
from datetime import datetime

import pytest
from fastapi import BackgroundTasks, HTTPException

@pytest.fixture(autouse=True)
def enable_optional_feedback_processing(monkeypatch):
    """Feedback tests opt into AI/publication unless a test kills a path."""
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")



# ---------------------------------------------------------------------------
# Pure scrub unit tests (no DB)
# ---------------------------------------------------------------------------


def test_scrub_text_redacts_pii_but_keeps_training_numbers():
    from api.feedback_scrub import scrub_text

    raw = (
        "Contact jane.doe@example.com or call 13800138000. "
        "Bearer token=ghp_abcdefghijklmnopqrstuvwx12345 from 192.168.1.42, "
        "log at C:\\Users\\jane\\AppData. My avg power was 285 and HR 165."
    )
    out = scrub_text(raw)
    assert "jane.doe@example.com" not in out
    assert "ghp_abcdefghijklmnopqrstuvwx12345" not in out
    assert "192.168.1.42" not in out
    assert "13800138000" not in out
    assert "\\Users\\jane" not in out
    # Training-relevant short numbers must survive.
    assert "285" in out
    assert "165" in out


def test_scrub_redacts_modern_api_keys():
    """Modern hyphenated keys (OpenAI sk-proj-/sk-svcacct-, GitHub fine-grained
    PAT) must be redacted whole — a regression guard for the older pattern that
    stopped at the first hyphen and leaked sk-proj- keys."""
    from api.feedback_scrub import scrub_text

    secrets = [
        "sk-proj-abcdEFGH1234567890ijklMNOP_qrst-uvwx",
        "sk-svcacct-AbC0123456789defGHIjklMNopQR",
        "github_pat_11ABCDEFG0aBcDeFgHiJ_KLmnopQRstuvWXyz123",
        "sk-ABCDEFGHIJKLMNOPqrstuvwx0123456789",
    ]
    for secret in secrets:
        out = scrub_text(f"my key is {secret} thanks")
        assert secret not in out, f"leaked: {secret}"
        assert "[redacted-key]" in out
    # A normal hyphenated phrase that merely starts with "sk-" must survive.
    assert "sk-based" in scrub_text("we use sk-based zones")


def test_scrub_redacts_formatted_phone_and_account_numbers():
    from api.feedback_scrub import scrub_text

    raw = (
        "Call 138-0013-8000 or (555) 123-4567. "
        "Card 4111 1111 1111 1111. Training date 2026-07-12, power 285."
    )
    out = scrub_text(raw)

    assert "138-0013-8000" not in out
    assert "(555) 123-4567" not in out
    assert "4111 1111 1111 1111" not in out
    assert out.count("[redacted-number]") == 3
    assert "2026-07-12" in out
    assert "285" in out


def test_scrub_redacts_credential_labels_with_common_phrasing():
    from api.feedback_scrub import scrub_text

    secrets = ("hunter2", "abc123", "token-value", "quoted secret")
    raw = (
        "my password is hunter2; API key: abc123; "
        "Authorization: Bearer token-value; secret = 'quoted secret'"
    )
    out = scrub_text(raw)

    for secret in secrets:
        assert secret not in out
    assert out.count("[redacted]") == 4

def test_scrub_redacts_quoted_json_credentials_without_corrupting_json():
    import json

    from api.feedback_scrub import scrub_text

    raw = json.dumps({
        "password": "hunter2",
        "access_token": "oauthCredential987654321",
        "nested": {"client_secret": "clientCredential987654321"},
        "power": 285,
    })
    out = scrub_text(raw)
    parsed = json.loads(out)

    assert parsed["password"] == "[redacted]"
    assert parsed["access_token"] == "[redacted]"
    assert parsed["nested"]["client_secret"] == "[redacted]"
    assert parsed["power"] == 285


def test_scrub_redacts_nested_json_credentials_without_leaking_array_values():
    import json

    from api.feedback_scrub import scrub_text

    raw = json.dumps({
        "tokens": ["firstsecret", "secondsecret"],
        "nested": {
            "OPENAI_API_KEY": {"primary": "thirdsecret"},
            "connectionString": {"primary": "fourthsecret"},
            "proxy_authorization": "fifthsecret",
            "headers": [
                {"Name": "Proxy-Authorization", "Value": "sixthsecret"},
            ],
            "note": "Contact jane@example.com after a 250 W workout",
        },
        "phone": 15551234567,
        "ok": 1,
    })

    out = scrub_text(raw)
    parsed = json.loads(out)

    assert parsed["tokens"] == "[redacted]"
    assert parsed["nested"]["OPENAI_API_KEY"] == "[redacted]"
    assert parsed["nested"]["connectionString"] == "[redacted]"
    assert parsed["nested"]["proxy_authorization"] == "[redacted]"
    assert parsed["nested"]["headers"][0]["Value"] == "[redacted]"
    assert parsed["nested"]["note"] == (
        "Contact [redacted-email] after a 250 W workout"
    )
    assert parsed["phone"] == "[redacted-number]"
    assert parsed["ok"] == 1
    for secret in (
        "firstsecret", "secondsecret", "thirdsecret", "fourthsecret",
        "fifthsecret", "sixthsecret",
    ):
        assert secret not in out


def test_scrub_redacts_compound_oauth_credential_labels():
    from api.feedback_scrub import scrub_text

    credentials = {
        "access_token": "ZXhhbXBsZU9BdXRoVmFsdWU987654",
        "refresh-token": "refreshCredential987654321",
        "client_secret": "clientCredential987654321",
    }
    raw = "; ".join(f"{label}={value}" for label, value in credentials.items())
    out = scrub_text(raw)

    for value in credentials.values():
        assert value not in out
    assert out.count("[redacted]") == 3

def test_scrub_redacts_complete_authorization_header_value():
    from api.feedback_scrub import scrub_text

    credential = "dXNlcjpwYXNzd29yZA=="
    out = scrub_text(f"Authorization: Basic {credential}\nrequest failed")

    assert credential not in out
    assert "Authorization [redacted]" in out
    assert "request failed" in out


def test_scrub_redacts_connection_credentials_cookies_and_private_keys():
    from api.feedback_scrub import scrub_text

    secrets = {
        "aws": "aws-secret-value-123",
        "account": "azure-storage-account-key-456",
        "database": "database-credential-value-789",
        "cookie": "session=private-cookie-value",
        "private_key": "private-key-material",
        "servicebus": "servicebus-shared-key-890",
        "uri_password": "uri-password-value-321",
        "lowercase_key": "lowercase-private-key-654",
    }
    raw = (
        f"AWS_SECRET_ACCESS_KEY={secrets['aws']}\n"
        f"DefaultEndpointsProtocol=https;AccountKey={secrets['account']};EndpointSuffix=core.windows.net\n"
        f"DATABASE_URL={secrets['database']}\n"
        f"PRAXYS_DATABASE_URL=postgresql://runner:{secrets['uri_password']}@db.example.test/praxys\n"
        f"AZURE_SERVICEBUS_CONNECTION_STRING=Endpoint=sb://bus.example.test;"
        f"SharedAccessKeyName=Root;SharedAccessKey={secrets['servicebus']}\n"
        f"Connection failed for postgresql://runner:{secrets['uri_password']}@db.example.test/praxys\n"
        f"aws_secret_access_key={secrets['lowercase_key']}\n"
        f"Cookie: {secrets['cookie']}\n"
        "-----BEGIN PRIVATE KEY-----\n"
        f"{secrets['private_key']}\n"
        "-----END PRIVATE KEY-----"
    )

    out = scrub_text(raw)

    for secret in secrets.values():
        assert secret not in out
    assert "AWS_SECRET_ACCESS_KEY=[redacted]" in out
    assert "AccountKey=[redacted]" in out
    assert "PRAXYS_DATABASE_URL=[redacted]" in out
    assert "SharedAccessKey=[redacted]" in out
    assert "aws_secret_access_key=[redacted]" in out
    assert "postgresql://[redacted]@db.example.test/praxys" in out
    assert "Cookie: [redacted]" in out
    assert "[redacted-private-key]" in out

def test_scrub_context_drops_unknown_keys_and_scrubs_values():
    from api.feedback_scrub import scrub_context

    cleaned = scrub_context(
        {
            "page": "/today",
            "app_version": "2026.06.1",
            "user_agent": "Mozilla contact me@x.com",
            "secret_field": "should-be-dropped",
        }
    )
    assert cleaned["page"] == "/today"
    assert cleaned["app_version"] == "2026.06.1"
    assert "me@x.com" not in cleaned["user_agent"]
    assert "secret_field" not in cleaned


def test_scrub_context_preserves_valid_ci_build_versions():
    from api.feedback_scrub import scrub_context

    valid = scrub_context({
        "app_version": "2026.07.04.1234-abc1234",
        "api_version": "2026.07.1",
    })
    assert valid == {
        "app_version": "2026.07.04.1234-abc1234",
        "api_version": "2026.07.1",
    }

    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    unsafe = scrub_context({
        "app_version": "2026.07.4111111111111111",
        "api_version": secret,
    })
    assert unsafe["app_version"] != "2026.07.4111111111111111"
    assert secret not in unsafe["api_version"]


def test_scrub_text_preserves_valid_ci_build_version():
    from api.feedback_scrub import scrub_text

    build_version = "2026.07.13.12345678-deadbee"
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    cleaned = scrub_text(f"app_version={build_version}\napi_key={secret}")

    assert build_version in cleaned
    assert secret not in cleaned


def test_scrub_text_redacts_invalid_build_like_long_value():
    from api.feedback_scrub import scrub_text

    invalid_value = "2026.07.13.12345678-deadbeeX"
    cleaned = scrub_text(f"app_version={invalid_value}")

    assert invalid_value not in cleaned
    assert "[redacted-number]" in cleaned


# ---------------------------------------------------------------------------
# DB-backed fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def db_with_users(monkeypatch):
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_LOCAL_ENCRYPTION_KEY", "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=")
    # Triage must run in its fully-unconfigured mode: no LLM, no GitHub.
    monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
    monkeypatch.delenv("PRAXYS_GITHUB_APP_ID", raising=False)
    monkeypatch.delenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", raising=False)
    monkeypatch.delenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("PRAXYS_FEEDBACK_GITHUB_REPO", raising=False)
    monkeypatch.delenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    # get_client is process-memoised — clear so a prior test that set an
    # endpoint can't leak an enabled client into this unconfigured run.
    from api import llm

    llm.get_client.cache_clear()

    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db.models import User

    db = db_session.SessionLocal()
    admin_id, user_id = "admin-fb", "user-fb"
    db.add(User(
        id=admin_id,
        email="admin@fb.test",
        hashed_password="x",
        is_superuser=True,
        terms_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST,
    ))
    db.add(User(
        id=user_id,
        email="user@fb.test",
        hashed_password="x",
        is_superuser=False,
        terms_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST,
    ))
    db.commit()
    try:
        yield db, db_session, admin_id, user_id
    finally:
        db.close()
        if db_session.engine is not None:
            db_session.engine.dispose()
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


# ---------------------------------------------------------------------------
# Submit endpoint
# ---------------------------------------------------------------------------

_PRIVACY_LOG_SENTINELS = (
    "feedback-id=918273645",
    "user-id=private-user-564738291",
    "key=feedback/918273645/0.png",
    "path=/tmp/private-user-564738291/feedback.png",
    f"hash={'ab' * 32}",
    "url=https://storage.invalid/private/feedback/918273645/0.png",
    "content=private feedback content sentinel",
    "consent=feedback-publication-v2-public-github",
)


def _privacy_log_exception_text() -> str:
    return ";".join(_PRIVACY_LOG_SENTINELS)


def _assert_privacy_sentinels_absent(rendered_log: str) -> None:
    for sentinel in _PRIVACY_LOG_SENTINELS:
        assert sentinel not in rendered_log


def test_submit_save_exception_log_omits_exception_privacy_data(
    db_with_users,
    monkeypatch,
    caplog,
):
    from api.routes.feedback import FeedbackRequest, submit_feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("ERROR", logger="api.routes.feedback")
    monkeypatch.setattr(
        db,
        "commit",
        lambda: (_ for _ in ()).throw(
            RuntimeError(_privacy_log_exception_text())
        ),
    )

    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(kind="bug", message="private feedback content sentinel"),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )

    assert exc.value.status_code == 500
    assert "feedback save failed" in caplog.text
    _assert_privacy_sentinels_absent(caplog.text)


def test_submit_stores_row_and_schedules_triage(db_with_users, caplog):
    from api.routes.feedback import submit_feedback, FeedbackRequest
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("INFO", logger="api.routes.feedback")
    bg = BackgroundTasks()
    resp = submit_feedback(
        FeedbackRequest(kind="bug", message="Charts fail to load", context={"page": "/training"}),
        background_tasks=bg,
        user_id=user_id,
        db=db,
    )
    assert resp["ok"] is True
    assert resp["status"] == "received"
    assert len(bg.tasks) == 1  # triage scheduled

    row = db.query(Feedback).filter(Feedback.id == resp["id"]).first()
    assert row.status == "new"
    assert row.kind == "bug"
    assert row.user_id == user_id
    assert row.publication_consent_version is None
    assert row.publication_consented_at is None
    route_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "api.routes.feedback"
    ]
    assert any("feedback submitted" in message for message in route_messages)
    assert all(str(resp["id"]) not in message for message in route_messages)
    assert all(user_id not in message for message in route_messages)


def test_submit_persists_explicit_publication_consent(db_with_users):
    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from api.routes.feedback import FeedbackRequest, submit_feedback
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    response = submit_feedback(
        FeedbackRequest(
            kind="bug",
            message="Charts fail to load",
            external_publication_consent=True,
            external_publication_consent_version=(
                FEEDBACK_PUBLICATION_CONSENT_VERSION
            ),
        ),
        background_tasks=BackgroundTasks(),
        user_id=user_id,
        db=db,
    )

    row = db.get(Feedback, response["id"])
    assert (
        row.publication_consent_version
        == FEEDBACK_PUBLICATION_CONSENT_VERSION
    )
    assert row.publication_consented_at is not None


@pytest.mark.parametrize(
    "invalid_consent",
    ["true", "false", 1, 0, None, [], {}],
    ids=["true-string", "false-string", "one", "zero", "null", "array", "object"],
)
def test_feedback_http_rejects_non_boolean_publication_consent(invalid_consent):
    """The HTTP contract must not coerce JSON scalars or containers to bool."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.auth import get_current_user_id
    from api.routes.feedback import router
    from db.session import get_db

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user_id] = lambda: "strict-bool-user"
    app.dependency_overrides[get_db] = lambda: None

    response = TestClient(app).post(
        "/api/feedback",
        json={
            "kind": "bug",
            "message": "Strict consent boundary",
            "external_publication_consent": invalid_consent,
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "external_publication_consent"
        for error in response.json()["detail"]
    )


def test_demo_feedback_stays_private_across_readiness_enqueue_and_admin(
    db_with_users,
    monkeypatch,
):
    from fastapi import Response

    from api.feedback_publication import enqueue_publication
    from api.feedback_triage import triage_and_publish
    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from api.routes.feedback import (
        FeedbackAction,
        FeedbackRequest,
        feedback_publication_readiness,
        submit_feedback,
        update_feedback,
    )
    from db.models import FeedbackPublicationOutbox, User

    db, _, admin_id, user_id = db_with_users
    demo = db.get(User, user_id)
    demo.is_demo = True
    demo.demo_of = admin_id
    db.commit()
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "1")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", "synthetic-key")

    readiness = feedback_publication_readiness(
        Response(), user_id=user_id, db=db
    )
    assert readiness["available"] is False

    submitted = submit_feedback(
        FeedbackRequest(
            kind="bug",
            message="Demo feedback remains private",
            external_publication_consent=True,
            external_publication_consent_version=(
                FEEDBACK_PUBLICATION_CONSENT_VERSION
            ),
        ),
        BackgroundTasks(),
        user_id=user_id,
        db=db,
    )
    row = db.get(__import__("db.models", fromlist=["Feedback"]).Feedback, submitted["id"])
    assert submitted["publication"]["status"] == "unavailable"
    assert row.publication_consent_version is None
    assert row.publication_consented_at is None

    triage_and_publish(row.id, _session=db)
    db.refresh(row)
    assert row.publication_status == "unavailable"

    row.publication_consent_version = FEEDBACK_PUBLICATION_CONSENT_VERSION
    row.publication_consented_at = datetime.utcnow()
    row.publication_status = "manual_required"
    row.status = "needs_review"
    row.ai_title = "Reviewed demo feedback"
    row.ai_body = "A scrubbed demo report."
    row.ai_labels = ["bug"]
    db.commit()

    assert enqueue_publication(db, row.id) is None
    assert row.publication_status == "unavailable"
    assert db.query(FeedbackPublicationOutbox).count() == 0

    with pytest.raises(HTTPException) as exc:
        update_feedback(
            row.id,
            _approve_action(row),
            BackgroundTasks(),
            user_id=admin_id,
            db=db,
        )
    assert exc.value.status_code == 400
    assert db.query(FeedbackPublicationOutbox).count() == 0


@pytest.mark.parametrize(
    ("publication_consent", "expected_status"),
    [(True, "unavailable"), (False, "private")],
)
def test_demo_triage_exception_recovery_never_requires_publication_review(
    db_with_users,
    monkeypatch,
    publication_consent,
    expected_status,
):
    from api import feedback_triage
    from api.feedback_triage import triage_and_publish
    from db.models import User

    db, _, admin_id, user_id = db_with_users
    demo = db.get(User, user_id)
    demo.is_demo = True
    demo.demo_of = admin_id
    row = _new_row(
        db,
        user_id,
        "Demo triage exception",
        publication_consent=publication_consent,
    )
    monkeypatch.setattr(
        feedback_triage,
        "_rule_based",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert triage_and_publish(row.id, _session=db)["status"] == "failed"
    db.refresh(row)
    assert row.publication_status == expected_status


def test_submit_rejects_stale_publication_consent_version(db_with_users):
    from api.routes.feedback import FeedbackRequest, submit_feedback
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(
                kind="bug",
                message="Charts fail to load",
                external_publication_consent=True,
                external_publication_consent_version="feedback-publication-old",
            ),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "FEEDBACK_PUBLICATION_CONSENT_MISMATCH"
    assert db.query(Feedback).count() == 0


@pytest.mark.parametrize(
    "consent_version",
    ["", "feedback-publication-v1"],
)
def test_submit_rejects_publication_version_without_consent(
    db_with_users,
    consent_version,
):
    from api.routes.feedback import FeedbackRequest, submit_feedback
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(
                kind="bug",
                message="Charts fail to load",
                external_publication_consent=False,
                external_publication_consent_version=consent_version,
            ),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "FEEDBACK_PUBLICATION_CONSENT_MISMATCH"
    assert db.query(Feedback).count() == 0


def test_submit_rate_limited(db_with_users):
    from api.routes.feedback import submit_feedback, FeedbackRequest, _MAX_PER_WINDOW

    db, _, _, user_id = db_with_users
    for _ in range(_MAX_PER_WINDOW):
        submit_feedback(
            FeedbackRequest(kind="other", message="x"),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )
    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(kind="other", message="one too many"),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )
    assert exc.value.status_code == 429


# ---------------------------------------------------------------------------
# Background triage
# ---------------------------------------------------------------------------


def test_triage_without_github_marks_triaged_and_scrubs(db_with_users, caplog):
    from api.feedback_triage import triage_and_publish
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("INFO", logger="api.feedback_triage")
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="App crashed, email me at runner@example.com",
        status="new",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"  # no GitHub configured
    assert result["used_llm"] is False  # no Azure endpoint

    db.refresh(row)
    assert row.status == "triaged"
    assert row.ai_title
    assert row.ai_body
    # The scrubbed body that would be published must not leak the raw email.
    assert "runner@example.com" not in row.ai_body
    assert "[redacted-email]" in row.ai_body
    assert "bug" in (row.ai_labels or [])
    assert "feedback" in (row.ai_labels or [])
    triage_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "api.feedback_triage"
    ]
    assert any("agent-ready decision" in message for message in triage_messages)
    assert all(str(row.id) not in message for message in triage_messages)


def test_triage_not_found_log_omits_requested_feedback_id(
    db_with_users,
    caplog,
):
    from api.feedback_triage import triage_and_publish

    db, _, _, _ = db_with_users
    missing_id = 987_654_321
    caplog.set_level("WARNING", logger="api.feedback_triage")

    result = triage_and_publish(missing_id, _session=db)

    assert result == {"status": "error", "reason": "not_found"}
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "api.feedback_triage"
    ]
    assert any("not found" in message for message in messages)
    assert all(str(missing_id) not in message for message in messages)


def test_triage_is_idempotent_on_published_row(db_with_users):
    from api.feedback_triage import triage_and_publish
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    row = Feedback(user_id=user_id, kind="other", message="done", status="issue_created")
    db.add(row)
    db.commit()
    db.refresh(row)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# Sensitivity gate (same public repo + AI gate)
# ---------------------------------------------------------------------------


def _stub_github(monkeypatch, calls):
    from api import feedback_triage as ft, github_issues

    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "1")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", "synthetic")
    monkeypatch.setattr(ft.github_issues, "is_configured", lambda: True)
    monkeypatch.setattr(
        github_issues,
        "reconcile_issue_marker",
        lambda marker, **_kwargs: {
            "outcome": "unknown",
            "number": None,
            "url": None,
            "http_status": 200,
            "error_code": "not_indexed_or_absent",
        },
    )

    def _create(**kwargs):
        calls.append(kwargs)
        return {
            "outcome": "created",
            "number": 101,
            "url": "https://github.com/praxys-run/praxys/issues/101",
            "http_status": 201,
            "error_code": None,
        }

    monkeypatch.setattr(github_issues, "create_issue_outcome", _create)


def _publish_queued(db):
    """Run the separately owned durable worker for one queued test row."""
    from api.feedback_publication import claim_next_send, send_claim

    claim = claim_next_send(db)
    assert claim is not None
    return send_claim(db, *claim)


def _stub_llm(
    monkeypatch,
    *,
    sensitive,
    priority=None,
    kind="bug",
    agent_eligible=True,
    privacy_safe=True,
):
    from api import feedback_triage as ft

    payload = {
        "kind": kind,
        "title": "Charts crash on Training",
        "body": "The training charts fail to render.",
        "contains_sensitive": sensitive,
        "agent_eligible": agent_eligible,
    }
    if priority is not None:
        payload["priority"] = priority

    def _chat_json(*_args, **kwargs):
        if kwargs.get("insight_type") == "feedback_publication_privacy_review":
            return {"safe_to_publish": privacy_safe}
        return payload

    monkeypatch.setattr(ft.llm, "get_client", lambda: object())
    monkeypatch.setattr(ft.llm, "chat_json", _chat_json)
    monkeypatch.setattr(
        ft,
        "background_ai_authorized",
        lambda *_args, **_kwargs: True,
    )


def _new_row(
    db,
    user_id,
    message,
    kind="bug",
    *,
    publication_consent=True,
):
    from api.optional_processing import FEEDBACK_PUBLICATION_CONSENT_VERSION
    from db.models import Feedback

    row = Feedback(
        user_id=user_id,
        kind=kind,
        message=message,
        status="new",
        publication_consent_version=(
            FEEDBACK_PUBLICATION_CONSENT_VERSION
            if publication_consent
            else None
        ),
        publication_consented_at=(
            datetime.utcnow() if publication_consent else None
        ),
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


def test_gate_holds_when_no_ai_and_public_repo(db_with_users, monkeypatch):
    """GitHub configured but no AI to judge sensitivity → park for admin."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(db, user_id, "The goal page is confusing.")

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert calls == []  # nothing published


def test_gate_autofiles_without_ai_when_opted_in(db_with_users, monkeypatch):
    """A global scrub-only switch cannot authorize public publication."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI", "true")
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(
        db,
        user_id,
        "The goal page is confusing.",
        publication_consent=False,
    )

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    db.refresh(row)
    assert row.publication_status == "private"
    assert calls == []


def test_gate_holds_when_secret_present_even_if_opted_in(db_with_users, monkeypatch):
    """A scrubbed key/token always parks the row, overriding the opt-in."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI", "true")
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(db, user_id, "My key sk-proj-abcdEFGH1234567890ijklMNOP_qrst leaked")

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert calls == []


def test_pre_model_redaction_cannot_be_erased_by_clean_llm_output(
    db_with_users, monkeypatch
):
    """A model omitting the scrub marker cannot reopen the public gate."""
    from api.feedback_triage import triage_and_publish
    from db.models import FeedbackPublicationOutbox

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    row = _new_row(
        db,
        user_id,
        "Token ghp_abcdefghijklmnopqrstuvwx1234567890 broke sync",
    )

    result = triage_and_publish(row.id, _session=db)

    assert result["status"] == "needs_review"
    assert calls == []
    assert (
        db.query(FeedbackPublicationOutbox)
        .filter(FeedbackPublicationOutbox.feedback_id == row.id)
        .count()
        == 0
    )


def test_gate_holds_when_llm_flags_sensitive(db_with_users, monkeypatch):
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=True)
    row = _new_row(db, user_id, "Something about my health data")

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert result["used_llm"] is True
    assert calls == []


@pytest.mark.parametrize("malformed", (0, "", None, [], {}))
def test_text_malformed_falsy_sensitivity_never_enqueues_or_posts(
    db_with_users,
    monkeypatch,
    malformed,
):
    from api.feedback_publication import claim_next_send, send_claim
    from api.feedback_triage import triage_and_publish
    from db.models import FeedbackPublicationOutbox

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=malformed)
    row = _new_row(db, user_id, "Charts fail to load on the training page")

    result = triage_and_publish(row.id, _session=db)
    claim = claim_next_send(db)
    if claim is not None:
        send_claim(db, *claim)

    assert result["status"] == "needs_review"
    assert result["used_llm"] is False
    assert claim is None
    assert calls == []
    assert (
        db.query(FeedbackPublicationOutbox)
        .filter(FeedbackPublicationOutbox.feedback_id == row.id)
        .count()
        == 0
    )


def test_background_ai_kill_switch_uses_rule_based_review(
    db_with_users, monkeypatch
):
    from api import feedback_triage as ft
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")
    monkeypatch.setattr(
        ft.llm,
        "get_client",
        lambda: (_ for _ in ()).throw(
            AssertionError("background AI client must remain unused")
        ),
    )
    row = _new_row(db, user_id, "Charts fail to load on the training page")

    result = triage_and_publish(row.id, _session=db)

    assert result["status"] == "needs_review"
    assert result["used_llm"] is False
    db.refresh(row)
    assert row.publication_status == "manual_required"


def test_gate_publishes_when_llm_says_clean(db_with_users, monkeypatch):
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    row = _new_row(db, user_id, "Charts fail to load on the training page")

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    assert calls == []
    assert _publish_queued(db) == "published"
    assert len(calls) == 1
    db.refresh(row)
    assert row.github_issue_number == 101


def test_admin_approve_publishes_parked_row(db_with_users, monkeypatch):
    from api.routes.feedback import FeedbackAction, list_feedback, update_feedback
    from api.feedback_triage import triage_and_publish

    db, _, admin_id, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(db, user_id, "Parked report awaiting review")

    # No AI → parked.
    triage_and_publish(row.id, _session=db)
    db.refresh(row)
    assert row.status == "needs_review"
    listed = next(
        item
        for item in list_feedback(user_id=admin_id, db=db)
        if item["id"] == row.id
    )
    assert listed["external_publication_consent"] is True
    assert listed["publication_review_token"] == _approve_action(row).review_token

    bg = BackgroundTasks()
    out = update_feedback(
        row.id,
        _approve_action(row),
        bg,
        user_id=admin_id,
        db=db,
    )
    assert out["status"] == "triaged"
    assert out["publication_status"] == "queued"
    assert out["github_issue_number"] is None
    assert len(bg.tasks) == 1
    assert calls == []
    assert _publish_queued(db) == "published"
    assert len(calls) == 1


def test_admin_approve_cannot_substitute_for_submitter_consent(
    db_with_users,
    monkeypatch,
):
    from api.feedback_triage import triage_and_publish
    from api.routes.feedback import FeedbackAction, list_feedback, update_feedback

    db, _, admin_id, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(
        db,
        user_id,
        "Private report awaiting review",
        publication_consent=False,
    )
    triage_and_publish(row.id, _session=db)
    listed = next(
        item
        for item in list_feedback(user_id=admin_id, db=db)
        if item["id"] == row.id
    )
    assert listed["external_publication_consent"] is False

    with pytest.raises(HTTPException) as exc:
        update_feedback(
            row.id,
            _approve_action(row),
            BackgroundTasks(),
            user_id=admin_id,
            db=db,
        )

    assert exc.value.status_code == 400
    assert calls == []


def test_admin_approve_rejects_legacy_or_stale_publication_consent(
    db_with_users,
    monkeypatch,
):
    from api.feedback_triage import triage_and_publish
    from api.routes.feedback import FeedbackAction, update_feedback

    db, _, admin_id, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(
        db,
        user_id,
        "Legacy private report",
        publication_consent=False,
    )
    triage_and_publish(row.id, _session=db)

    for version, consented_at in (
        (None, None),
        ("feedback-publication-old", datetime.utcnow()),
    ):
        row.publication_consent_version = version
        row.publication_consented_at = consented_at
        row.status = "needs_review"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            update_feedback(
                row.id,
                _approve_action(row),
                BackgroundTasks(),
                user_id=admin_id,
                db=db,
            )
        assert exc.value.status_code == 400

    assert calls == []


def test_admin_approve_cannot_publish_after_submitter_terms_go_stale(
    db_with_users,
    monkeypatch,
):
    from api.feedback_triage import triage_and_publish
    from api.routes.feedback import FeedbackAction, update_feedback
    from db.models import User

    db, _, admin_id, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(db, user_id, "Parked report awaiting review")
    triage_and_publish(row.id, _session=db)
    submitter = db.get(User, user_id)
    submitter.terms_version = "old"
    db.commit()

    with pytest.raises(HTTPException) as exc:
        update_feedback(
            row.id,
            _approve_action(row),
            BackgroundTasks(),
            user_id=admin_id,
            db=db,
        )

    assert exc.value.status_code == 400
    assert calls == []


def test_admin_approve_is_bound_to_the_reviewed_public_draft(
    db_with_users,
    monkeypatch,
):
    from api.feedback_triage import triage_and_publish
    from api.routes.feedback import update_feedback
    from db.models import FeedbackPublicationOutbox

    db, _, admin_id, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(db, user_id, "Calendar text clips its card")
    triage_and_publish(row.id, _session=db)
    db.refresh(row)
    stale_approval = _approve_action(row)

    row.ai_body = "Alice Chen's resting heart rate is 42 bpm."
    db.commit()

    with pytest.raises(HTTPException) as exc:
        update_feedback(
            row.id,
            stale_approval,
            BackgroundTasks(),
            user_id=admin_id,
            db=db,
        )

    assert exc.value.status_code == 409
    assert "review the current public draft" in str(exc.value.detail)
    assert db.query(FeedbackPublicationOutbox).count() == 0
    assert calls == []


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


def test_admin_list_requires_admin(db_with_users):
    from api.routes.feedback import list_feedback

    db, _, admin_id, user_id = db_with_users
    with pytest.raises(HTTPException) as exc:
        list_feedback(user_id=user_id, db=db)
    assert exc.value.status_code == 403

    # Admin can list.
    out = list_feedback(user_id=admin_id, db=db)
    assert isinstance(out, list)


def test_admin_reject_and_retry(db_with_users):
    from api.routes.feedback import submit_feedback, update_feedback, FeedbackRequest, FeedbackAction
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    submitted = submit_feedback(
        FeedbackRequest(kind="feature", message="add dark mode toggle"),
        background_tasks=BackgroundTasks(),
        user_id=user_id,
        db=db,
    )
    fid = submitted["id"]

    rejected = update_feedback(fid, FeedbackAction(action="reject"), BackgroundTasks(), user_id=admin_id, db=db)
    assert rejected["status"] == "rejected"

    bg = BackgroundTasks()
    retried = update_feedback(fid, FeedbackAction(action="retry"), bg, user_id=admin_id, db=db)
    assert retried["status"] == "new"
    assert len(bg.tasks) == 1

    # Retrying an already-published row (linked to a GitHub issue) is a conflict.
    row = db.query(Feedback).filter(Feedback.id == fid).first()
    row.status = "issue_created"
    row.github_issue_number = 101
    db.commit()
    with pytest.raises(HTTPException) as exc:
        update_feedback(fid, FeedbackAction(action="retry"), BackgroundTasks(), user_id=admin_id, db=db)
    assert exc.value.status_code == 409


def test_admin_action_on_missing_row_404(db_with_users):
    from api.routes.feedback import update_feedback, FeedbackAction

    db, _, admin_id, _ = db_with_users
    with pytest.raises(HTTPException) as exc:
        update_feedback(999999, FeedbackAction(action="reject"), BackgroundTasks(), user_id=admin_id, db=db)
    assert exc.value.status_code == 404


def test_admin_feedback_summary(db_with_users):
    """Summary counts power the admin sidebar badge; non-admins get 403."""
    from api.routes.feedback import feedback_summary
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    for status in ("needs_review", "failed", "new", "issue_created"):
        db.add(Feedback(user_id=user_id, kind="bug", message="x", status=status))
    db.commit()

    summary = feedback_summary(user_id=admin_id, db=db)
    assert summary["needs_review"] == 1
    assert summary["failed"] == 1
    assert summary["actionable"] == 2
    assert summary["total"] == 4

    with pytest.raises(HTTPException) as exc:
        feedback_summary(user_id=user_id, db=db)
    assert exc.value.status_code == 403


def test_admin_adjudication_records_ground_truth_and_syncs_label(
    db_with_users,
    monkeypatch,
):
    from api import github_issues
    from api.routes.feedback import (
        AgentReadyAdjudication,
        adjudicate_agent_readiness,
        list_feedback,
    )
    from db.agent_loop import record_decision
    from db.models import AgentOutcome, Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="Calendar text overflows its day card.",
        status="issue_created",
        priority="low",
        github_issue_number=542,
        github_issue_url="https://github.com/praxys-run/praxys/issues/542",
    )
    db.add(row)
    db.flush()
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version="02885290c95ddf28",
        model="gpt-5.4",
        mode="active",
        input_data={"detail_word_count": 7, "detail_alnum_count": 35},
        output_data={
            "kind": "bug",
            "agent_eligible": False,
            "gate_blocked": False,
            "agent_ready_candidate": False,
            "agent_ready_applied": False,
            "agent_ready_reason": "not_actionable",
            "active_prompt_version": "v1",
            "challenger": {
                "prompt_version": "v2",
                "prompt_hash": "candidate",
                "model": "gpt-5.4",
                "available": True,
                "kind": "bug",
                "agent_eligible": True,
                "agent_ready_candidate": True,
                "agent_ready_reason": "eligible",
            },
        },
    )
    db.commit()

    calls: list[tuple[int, str, bool]] = []
    monkeypatch.setattr(github_issues, "is_configured", lambda: True)
    monkeypatch.setattr(
        github_issues,
        "issue_matches_configured_repo",
        lambda number, url: True,
    )
    monkeypatch.setattr(
        github_issues,
        "get_issue_state",
        lambda number: {"state": "open"},
    )
    monkeypatch.setattr(
        github_issues,
        "set_issue_label",
        lambda number, label, *, present: (
            calls.append((number, label, present)) or True
        ),
    )

    result = adjudicate_agent_readiness(
        row.id,
        AgentReadyAdjudication(
            decision_id=decision.id,
            expected=True,
            reason="bounded_actionable_defect",
        ),
        user_id=admin_id,
        db=db,
    )
    assert result["recorded"] is True
    assert result["label_sync"] == "synced"
    assert calls == [(542, "agent-ready", True)]

    outcome = (
        db.query(AgentOutcome)
        .filter(AgentOutcome.decision_id == decision.id)
        .one()
    )
    assert outcome.outcome_type == "agent_ready_adjudicated"
    assert outcome.payload_json["expected"] is True
    assert outcome.payload_json["active_candidate"] is False
    assert outcome.payload_json["challenger_candidate"] is True

    monkeypatch.setattr(
        github_issues,
        "get_issue_state",
        lambda number: {"state": "closed"},
    )
    closed_result = adjudicate_agent_readiness(
        row.id,
        AgentReadyAdjudication(
            decision_id=decision.id,
            expected=True,
            reason="bounded_actionable_defect",
        ),
        user_id=admin_id,
        db=db,
    )
    assert closed_result["label_sync"] == "issue_not_open"
    assert calls == [(542, "agent-ready", True)]

    row.status = "resolved"
    db.commit()
    monkeypatch.setattr(
        github_issues,
        "get_issue_state",
        lambda number: {"state": "open"},
    )
    reopened_result = adjudicate_agent_readiness(
        row.id,
        AgentReadyAdjudication(
            decision_id=decision.id,
            expected=True,
            reason="bounded_actionable_defect",
        ),
        user_id=admin_id,
        db=db,
    )
    assert reopened_result["label_sync"] == "synced"
    assert calls == [
        (542, "agent-ready", True),
        (542, "agent-ready", True),
    ]

    monkeypatch.setattr(
        github_issues,
        "issue_matches_configured_repo",
        lambda number, url: False,
    )
    mismatch_result = adjudicate_agent_readiness(
        row.id,
        AgentReadyAdjudication(
            decision_id=decision.id,
            expected=True,
            reason="bounded_actionable_defect",
        ),
        user_id=admin_id,
        db=db,
    )
    assert mismatch_result["label_sync"] == "repository_mismatch"
    assert len(calls) == 2

    serialized = list_feedback(
        status="resolved",
        user_id=admin_id,
        db=db,
    )[0]
    readiness = serialized["agent_readiness"]
    assert readiness["reason"] == "not_actionable"
    assert readiness["challenger"]["candidate"] is True
    assert readiness["adjudication"]["expected"] is True
    assert readiness["adjudication"]["label_sync"] == "repository_mismatch"


def test_admin_adjudication_persists_when_label_sync_fails(
    db_with_users,
    monkeypatch,
):
    from api import github_issues
    from api.routes.feedback import (
        AgentReadyAdjudication,
        adjudicate_agent_readiness,
    )
    from db.agent_loop import record_decision
    from db.models import AgentOutcome, Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="The report is not reproducible.",
        status="issue_created",
        github_issue_number=100,
        github_issue_url="https://github.com/praxys-run/praxys/issues/100",
    )
    db.add(row)
    db.flush()
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version="prompt",
        model="test",
        mode="active",
        input_data={"detail_word_count": 5, "detail_alnum_count": 30},
        output_data={
            "kind": "bug",
            "gate_blocked": False,
            "agent_ready_candidate": True,
            "agent_ready_applied": True,
        },
    )
    db.commit()
    monkeypatch.setattr(github_issues, "is_configured", lambda: True)
    monkeypatch.setattr(
        github_issues,
        "issue_matches_configured_repo",
        lambda number, url: True,
    )
    monkeypatch.setattr(github_issues, "set_issue_label", lambda *a, **k: False)

    result = adjudicate_agent_readiness(
        row.id,
        AgentReadyAdjudication(
            decision_id=decision.id,
            expected=False,
            reason="not_a_defect",
        ),
        user_id=admin_id,
        db=db,
    )
    assert result["label_sync"] == "failed"
    outcome = (
        db.query(AgentOutcome)
        .filter(AgentOutcome.decision_id == decision.id)
        .one()
    )
    assert outcome.payload_json["expected"] is False
    assert outcome.payload_json["label_sync"] == "failed"


def test_admin_adjudication_validates_reason_and_auth(db_with_users):
    from api.routes.feedback import (
        AgentReadyAdjudication,
        adjudicate_agent_readiness,
    )
    from db.agent_loop import record_decision
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(user_id=user_id, kind="bug", message="x", status="triaged")
    db.add(row)
    db.flush()
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version=None,
        model="test",
        mode="active",
        input_data={},
        output_data={"agent_ready_candidate": False},
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        adjudicate_agent_readiness(
            row.id,
            AgentReadyAdjudication(
                decision_id=decision.id,
                expected=True,
                reason="not_a_defect",
            ),
            user_id=admin_id,
            db=db,
        )
    assert exc.value.status_code == 422

    newer_decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version=None,
        model="test",
        mode="active",
        input_data={},
        output_data={"agent_ready_candidate": False},
    )
    db.commit()
    with pytest.raises(HTTPException) as exc:
        adjudicate_agent_readiness(
            row.id,
            AgentReadyAdjudication(
                decision_id=decision.id,
                expected=False,
                reason="not_a_defect",
            ),
            user_id=admin_id,
            db=db,
        )
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        adjudicate_agent_readiness(
            row.id,
            AgentReadyAdjudication(
                decision_id=newer_decision.id,
                expected=False,
                reason="insufficient_detail",
            ),
            user_id=user_id,
            db=db,
        )
    assert exc.value.status_code == 403


def test_empty_llm_output_does_not_drop_user_report(db_with_users, monkeypatch):
    """An empty LLM title/body must fall back to the rule-based body (which
    carries the real message) instead of publishing a contentless issue."""
    from api import feedback_triage as ft
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI", "true")
    calls: list = []
    _stub_github(monkeypatch, calls)
    monkeypatch.setattr(ft.llm, "get_client", lambda: object())
    monkeypatch.setattr(
        ft.llm,
        "chat_json",
        lambda *a, **k: {"kind": "bug", "title": "", "body": "", "contains_sensitive": False},
    )
    row = _new_row(db, user_id, "Charts crash when I open Training")

    result = triage_and_publish(row.id, _session=db)
    # Empty model output is not trusted; the real message survives privately.
    assert result["used_llm"] is False
    assert result["status"] == "needs_review"
    assert calls == []
    db.refresh(row)
    assert "Charts crash" in row.ai_body
    assert row.publication_status == "manual_required"


def test_triage_commit_failure_cannot_reach_external_publication(
    db_with_users,
    monkeypatch,
    caplog,
):
    """A failed atomic enqueue commit must happen before any external POST."""
    from api.feedback_triage import triage_and_publish
    from db.agent_loop import record_decision
    from db.models import AgentDecision, AgentOutcome, Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("ERROR", logger="api.feedback_triage")
    monkeypatch.setenv("PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI", "true")
    calls: list = []
    _stub_github(monkeypatch, calls)
    row = _new_row(db, user_id, "A clean bug report")
    fid = row.id
    older = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(fid),
        policy_name="previous-policy",
        policy_version="v0",
        prompt_version=None,
        model=None,
        mode="active",
        input_data={"message_sha256": "older"},
        output_data={"status": "failed"},
    )
    older_id = older.id
    db.commit()

    real_commit = db.commit
    state = {"n": 0}

    def flaky_commit():
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError(_privacy_log_exception_text())
        return real_commit()

    monkeypatch.setattr(db, "commit", flaky_commit)
    result = triage_and_publish(fid, _session=db)

    assert result["status"] == "failed"
    assert calls == []
    fresh = db.query(Feedback).filter(Feedback.id == fid).first()
    assert fresh.status == "failed"
    assert fresh.github_issue_number is None
    from db.models import FeedbackPublicationOutbox

    assert db.query(FeedbackPublicationOutbox).count() == 0
    decisions = (
        db.query(AgentDecision)
        .filter(
            AgentDecision.subject_type == "feedback",
            AgentDecision.subject_ref == str(fid),
        )
        .all()
    )
    assert len(decisions) == 2
    current = next(item for item in decisions if item.id != older_id)
    outcome = db.query(AgentOutcome).one()
    assert outcome.decision_id == current.id
    assert "triage_and_publish failed" in caplog.text
    _assert_privacy_sentinels_absent(caplog.text)


def test_triage_storage_exception_log_omits_exception_privacy_data(
    db_with_users,
    monkeypatch,
    caplog,
):
    from api import feedback_triage
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("ERROR", logger="api.feedback_triage")
    row = _new_row(db, user_id, "private feedback content sentinel")
    row.image_keys = ["feedback/918273645/0.png"]
    db.commit()
    feedback_id = row.id
    monkeypatch.setattr(
        feedback_triage.feedback_storage,
        "load_image",
        lambda _key, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(_privacy_log_exception_text())
        ),
    )

    result = feedback_triage.triage_and_publish(feedback_id, _session=db)

    assert result["status"] == "failed"
    recovered = db.get(Feedback, feedback_id)
    assert recovered is not None and recovered.status == "failed"
    assert "triage_and_publish failed" in caplog.text
    _assert_privacy_sentinels_absent(caplog.text)


def test_feedback_privacy_loggers_never_emit_exception_tracebacks():
    import ast
    import inspect

    from api import (
        account_deletion,
        feedback_publication,
        feedback_storage,
        feedback_triage,
        github_issues,
        main,
        telemetry,
    )
    from api.routes import feedback as feedback_routes

    for module in (
        feedback_routes,
        feedback_triage,
        feedback_storage,
        account_deletion,
        feedback_publication,
        github_issues,
    ):
        tree = ast.parse(inspect.getsource(module))
        logger_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ]
        assert logger_calls, module.__name__
        assert all(call.func.attr != "exception" for call in logger_calls), (
            module.__name__
        )
        assert all(
            not any(
                keyword.arg == "exc_info"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in call.keywords
            )
            for call in logger_calls
        ), module.__name__

    github_tree = ast.parse(inspect.getsource(github_issues))
    github_logger_calls = [
        node
        for node in ast.walk(github_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
    ]
    assert all(len(call.args) == 1 for call in github_logger_calls)
    assert all(
        isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
        for call in github_logger_calls
    )
    assert all(
        not any(
            isinstance(node, ast.Name) and node.id in {"exc", "exception"}
            for node in ast.walk(call)
        )
        for call in github_logger_calls
    )

    main_tree = ast.parse(inspect.getsource(main))
    main_feedback_stop_calls = [
        node
        for node in ast.walk(main_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "logger"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and "feedback publication reconciler" in str(node.args[0].value)
    ]
    assert len(main_feedback_stop_calls) == 1
    assert main_feedback_stop_calls[0].func.attr == "error"
    assert len(main_feedback_stop_calls[0].args) == 1
    assert not main_feedback_stop_calls[0].keywords

    telemetry_tree = ast.parse(inspect.getsource(telemetry))
    telemetry_functions = {
        node.name: node
        for node in telemetry_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for function_name in ("_emit_event_or_count",):
        function = telemetry_functions[function_name]
        calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "logger"
        ]
        assert calls, function_name
        assert all(call.func.attr != "exception" for call in calls)
        assert all(len(call.args) == 1 for call in calls)
        assert all(
            isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
            for call in calls
        )
        assert all(
            not any(
                keyword.arg == "exc_info"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in call.keywords
            )
            for call in calls
        )

    record_feedback_source = inspect.getsource(telemetry.record_feedback)
    assert "_emit_event_or_count(" in record_feedback_source
    assert "_track_event(" not in record_feedback_source
    assert "_counter(" not in record_feedback_source

    triage_wake_source = inspect.getsource(
        feedback_triage.triage_and_wake_publication
    )
    reconciler_source = inspect.getsource(feedback_publication._reconciler_loop)
    update_source = inspect.getsource(feedback_routes.update_feedback)
    for source in (triage_wake_source, reconciler_source):
        assert "safe_wake_publication_queue" in source
        assert "process_publication_queue(" not in source
    assert "feedback_publication.safe_wake_publication_queue" in update_source
    assert "feedback_publication.process_publication_queue" not in update_source

# ---------------------------------------------------------------------------
# GitHub App auth (no-rotation alternative to the PAT)
# ---------------------------------------------------------------------------


def _rsa_pem():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


class _FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.reason_phrase = "OK"

    def json(self):
        return self._p


def test_github_app_mints_and_caches_installation_token(monkeypatch):
    from api import github_issues as gi

    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", "456")
    # single-line PEM with literal \n — the App Service storage shape
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", _rsa_pem().replace("\n", "\\n"))
    gi._install_token.update({"token": None, "exp": 0.0})

    calls = {"mint": 0, "issue": 0}

    def fake_post(url, **kw):
        if url.endswith("/access_tokens"):
            calls["mint"] += 1
            assert kw["headers"]["Authorization"].startswith("Bearer ")
            return _FakeResp(201, {"token": "ghs_tok", "expires_at": "2999-01-01T00:00:00Z"})
        calls["issue"] += 1
        return _FakeResp(
            201,
            {
                "number": 9,
                "html_url": "https://github.com/praxys-run/praxys/issues/9",
            },
        )

    monkeypatch.setattr(gi.httpx, "post", fake_post)

    assert gi.is_configured() is True
    assert gi._bearer_token() == "ghs_tok"
    gi._bearer_token()  # cached — must not re-mint
    assert calls["mint"] == 1
    assert gi.create_issue(
        title="t",
        body="b",
        labels=["bug"],
        publication_authorized=True,
    ) == {
        "number": 9,
        "url": "https://github.com/praxys-run/praxys/issues/9",
    }


@pytest.mark.parametrize(
    ("performed_via", "expected"),
    (
        ({"id": 123}, "reconciled"),
        (None, "unknown"),
        ({"id": "123"}, "unknown"),
        ({"id": True}, "unknown"),
        ({"id": 124}, "unknown"),
    ),
)
def test_marker_reconciliation_requires_exact_github_app_provenance(
    monkeypatch,
    performed_via,
    expected,
):
    from api import github_issues as gi

    marker = "<!-- praxys-feedback-publication:v2 id=opaque payload=sha256:x -->"
    title = "Public issue"
    body = f"Public issue\n\n{marker}"
    content_digest = gi.public_issue_content_sha256(title=title, body=body)
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setattr(gi, "_bearer_token", lambda: "ghs_token")
    monkeypatch.setattr(
        gi.httpx,
        "get",
        lambda *_args, **_kwargs: _FakeResp(
            200,
            {
                "items": [
                        {
                            "number": 9,
                        "html_url": (
                            "https://github.com/praxys-run/praxys/issues/9"
                        ),
                            "title": title,
                            "body": body,
                        "performed_via_github_app": performed_via,
                    }
                ]
            },
        ),
    )

    assert (
        gi.reconcile_issue_marker(
            marker,
            public_content_sha256=content_digest,
        )["outcome"]
        == expected
    )


@pytest.mark.parametrize(
    ("candidate_kind", "expected", "expected_number"),
    (
        ("replay_only", "unknown", None),
        ("original_and_replay", "reconciled", 9),
        ("modified_terminal", "unknown", None),
    ),
)
def test_marker_reconciliation_rejects_copied_or_modified_content(
    monkeypatch,
    candidate_kind,
    expected,
    expected_number,
):
    from api import github_issues as gi

    marker = (
        "<!-- praxys-feedback-publication:v2 id=original "
        f"payload=sha256:{'a' * 64} -->"
    )
    own_marker = (
        "<!-- praxys-feedback-publication:v2 id=replay "
        f"payload=sha256:{'b' * 64} -->"
    )
    title = "Original public title"
    body = f"Original public body\n\n{marker}"
    expected_digest = gi.public_issue_content_sha256(title=title, body=body)
    original = {
        "number": 9,
        "html_url": "https://github.com/praxys-run/praxys/issues/9",
        "title": title,
        "body": body,
        "performed_via_github_app": {"id": 123},
    }
    replay = {
        "number": 10,
        "html_url": "https://github.com/praxys-run/praxys/issues/10",
        "title": "Copied marker",
        "body": f"Copied marker payload\n\n{marker}\n\n{own_marker}",
        "performed_via_github_app": {"id": 123},
    }
    modified_terminal = {
        "number": 11,
        "html_url": "https://github.com/praxys-run/praxys/issues/11",
        "title": title,
        "body": f"Modified public body\n\n{marker}",
        "performed_via_github_app": {"id": 123},
    }
    items = {
        "replay_only": [replay],
        "original_and_replay": [replay, original],
        "modified_terminal": [modified_terminal],
    }[candidate_kind]
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setattr(gi, "_bearer_token", lambda: "ghs_token")
    monkeypatch.setattr(
        gi.httpx,
        "get",
        lambda *_args, **_kwargs: _FakeResp(200, {"items": items}),
    )

    outcome = gi.reconcile_issue_marker(
        marker,
        public_content_sha256=expected_digest,
    )

    assert outcome["outcome"] == expected
    assert outcome["number"] == expected_number


@pytest.mark.parametrize(
    ("completeness", "expected"),
    (
        ({"incomplete_results": True, "total_count": 1}, "provider_failure"),
        ({"incomplete_results": False, "total_count": 2}, "provider_failure"),
        ({"incomplete_results": False, "total_count": 1}, "reconciled"),
    ),
)
def test_marker_reconciliation_requires_complete_search_results(
    monkeypatch,
    completeness,
    expected,
):
    from api import github_issues as gi

    marker = (
        "<!-- praxys-feedback-publication:v2 id=complete "
        f"payload=sha256:{'c' * 64} -->"
    )
    title = "Complete search"
    body = f"Complete search body\n\n{marker}"
    content_digest = gi.public_issue_content_sha256(title=title, body=body)
    search_params: dict = {}

    def _search(*_args, **kwargs):
        search_params.update(kwargs["params"])
        return _FakeResp(
            200,
            {
                **completeness,
                "items": [
                    {
                        "number": 12,
                        "html_url": (
                            "https://github.com/praxys-run/praxys/issues/12"
                        ),
                        "title": title,
                        "body": body,
                        "performed_via_github_app": {"id": 123},
                    }
                ],
            },
        )

    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setattr(gi, "_bearer_token", lambda: "ghs_token")
    monkeypatch.setattr(gi.httpx, "get", _search)

    outcome = gi.reconcile_issue_marker(
        marker,
        public_content_sha256=content_digest,
    )

    assert outcome["outcome"] == expected
    assert search_params["per_page"] == 100
    if expected == "provider_failure":
        assert outcome["error_code"] == "incomplete_search_results"


@pytest.mark.parametrize("app_id", ("", "0", "01", "-1", " 123", "true"))
def test_github_app_id_must_be_canonical_positive_decimal(
    monkeypatch,
    app_id,
):
    from api import github_issues as gi

    if app_id:
        monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", app_id)
    else:
        monkeypatch.delenv("PRAXYS_GITHUB_APP_ID", raising=False)
    assert gi._configured_app_id() is None


def test_github_jwt_failure_log_omits_sensitive_exception(
    monkeypatch,
    caplog,
):
    import sys
    from types import SimpleNamespace

    from api import github_issues as gi

    caplog.set_level("WARNING", logger="api.github_issues")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", "private-key-sentinel")
    monkeypatch.setitem(
        sys.modules,
        "jwt",
        SimpleNamespace(
            encode=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError(_privacy_log_exception_text())
            )
        ),
    )

    assert gi._app_jwt() is None
    assert "JWT signing failed" in caplog.text
    _assert_privacy_sentinels_absent(caplog.text)


@pytest.mark.parametrize(
    ("operation", "expected"),
    (
        ("mint", None),
        ("create", "unknown"),
        ("reconcile", "provider_failure"),
        ("label", False),
        ("state", None),
        ("outcome", None),
    ),
)
def test_github_network_logs_omit_sensitive_exception(
    monkeypatch,
    caplog,
    operation,
    expected,
):
    import httpx

    from api import github_issues as gi

    caplog.set_level("WARNING", logger="api.github_issues")
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "praxys-run/praxys")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setattr(gi, "_bearer_token", lambda: "synthetic-token")
    monkeypatch.setattr(gi, "_repo", lambda: "praxys-run/praxys")

    def network_failure(*_args, **_kwargs):
        raise httpx.ConnectError(_privacy_log_exception_text())

    if operation == "mint":
        monkeypatch.setattr(gi, "_app_jwt", lambda: "synthetic-jwt")
        monkeypatch.setattr(gi, "_app_installation_id", lambda: "123")
        monkeypatch.setattr(gi.httpx, "post", network_failure)
        result = gi._mint_installation_token()
    elif operation == "create":
        monkeypatch.setattr(gi.httpx, "post", network_failure)
        result = gi.create_issue_outcome(
            title="private feedback content sentinel",
            body="private feedback content sentinel",
            publication_authorized=True,
        )["outcome"]
    elif operation == "reconcile":
        monkeypatch.setattr(gi.httpx, "get", network_failure)
        result = gi.reconcile_issue_marker(
            "ab" * 32,
            public_content_sha256="sha256:" + "0" * 64,
        )["outcome"]
    elif operation == "label":
        monkeypatch.setattr(gi.httpx, "post", network_failure)
        result = gi.set_issue_label(918273645, "private-label", present=True)
    elif operation == "state":
        monkeypatch.setattr(gi.httpx, "get", network_failure)
        result = gi.get_issue_state(918273645)
    else:
        monkeypatch.setattr(gi.httpx, "post", network_failure)
        monkeypatch.setattr(gi, "_state_only_outcome", lambda _number: None)
        result = gi.get_issue_outcome(918273645)

    assert result == expected
    assert "failed" in caplog.text or "unknown" in caplog.text
    _assert_privacy_sentinels_absent(caplog.text)


def test_feedback_publication_kill_switch_overrides_github_configuration(
    monkeypatch,
):
    from api import github_issues as gi

    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "123")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", "456")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", "configured")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setattr(
        gi,
        "_bearer_token",
        lambda: pytest.fail("disabled publication must not mint a token"),
    )

    assert gi.is_configured() is False
    assert gi.create_issue(title="t", body="b") is None


def test_github_issue_label_sync_adds_and_removes(monkeypatch):
    from api import github_issues as gi

    monkeypatch.setattr(gi, "_bearer_token", lambda: "ghs_token")
    monkeypatch.setattr(gi, "_repo", lambda: "owner/repo")
    calls: list[tuple[str, str]] = []

    def fake_post(url, **kwargs):
        calls.append(("post", url))
        assert kwargs["json"] == {"labels": ["agent-ready"]}
        assert kwargs["headers"]["Authorization"] == "Bearer ghs_token"
        return _FakeResp(200, {})

    def fake_delete(url, **kwargs):
        calls.append(("delete", url))
        assert kwargs["headers"]["Authorization"] == "Bearer ghs_token"
        return _FakeResp(404, {})

    monkeypatch.setattr(gi.httpx, "post", fake_post)
    monkeypatch.setattr(gi.httpx, "delete", fake_delete)

    assert gi.set_issue_label(42, "agent-ready", present=True) is True
    assert gi.set_issue_label(42, "agent-ready", present=False) is True
    assert calls == [
        ("post", "https://api.github.com/repos/owner/repo/issues/42/labels"),
        (
            "delete",
            "https://api.github.com/repos/owner/repo/issues/42/labels/agent-ready",
        ),
    ]


def test_github_issue_repo_identity_is_bound_to_stored_url(monkeypatch):
    from api import github_issues as gi

    monkeypatch.setattr(gi, "_repo", lambda: "praxys-run/praxys")
    assert gi.issue_matches_configured_repo(
        42,
        "https://github.com/praxys-run/praxys/issues/42",
    )
    assert not gi.issue_matches_configured_repo(
        42,
        "https://github.com/other/repo/issues/42",
    )
    assert not gi.issue_matches_configured_repo(
        42,
        "https://github.com/praxys-run/praxys/issues/41",
    )
    assert not gi.issue_matches_configured_repo(
        42,
        "http://github.com/owner/repo/issues/42",
    )


def test_not_configured_without_creds(monkeypatch):
    from api import github_issues as gi

    for v in (
        "PRAXYS_GITHUB_APP_ID", "PRAXYS_GITHUB_APP_INSTALLATION_ID",
        "PRAXYS_GITHUB_APP_PRIVATE_KEY",
    ):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "owner/repo")
    assert gi.is_configured() is False

def test_github_app_malformed_mint_response_returns_none(monkeypatch):
    """A 201 with a non-JSON body must degrade to None, not raise out of
    _bearer_token (the admin approve route calls create_issue unguarded)."""
    from api import github_issues as gi

    monkeypatch.setenv("PRAXYS_FEEDBACK_GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_ID", "1")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_INSTALLATION_ID", "2")
    monkeypatch.setenv("PRAXYS_GITHUB_APP_PRIVATE_KEY", _rsa_pem())
    gi._install_token.update({"token": None, "exp": 0.0})

    class _BadResp:
        status_code = 201
        reason_phrase = "Created"

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(gi.httpx, "post", lambda url, **kw: _BadResp())
    assert gi._bearer_token() is None  # must not raise


def test_github_issue_outcome_fetches_only_structured_state(monkeypatch):
    """Reconciliation reads labels and closing PR state without issue/PR text."""
    from api import github_issues as gi

    monkeypatch.setattr(gi, "_bearer_token", lambda: "ghs_token")
    monkeypatch.setattr(gi, "_repo", lambda: "owner/repo")
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs["json"])
        captured["authorization"] = kwargs["headers"]["Authorization"]
        return _FakeResp(
            200,
            {
                "data": {
                    "repository": {
                        "issue": {
                            "state": "CLOSED",
                            "stateReason": "COMPLETED",
                            "closedAt": "2026-07-20T01:00:00Z",
                            "updatedAt": "2026-07-20T01:00:00Z",
                            "labels": {"nodes": [{"name": "agent-ready"}]},
                            "closedByPullRequestsReferences": {
                                "nodes": [
                                    {
                                        "number": 42,
                                        "state": "MERGED",
                                        "isDraft": False,
                                        "merged": True,
                                        "updatedAt": "2026-07-20T00:59:00Z",
                                        "mergedAt": "2026-07-20T00:59:00Z",
                                        "closedAt": "2026-07-20T00:59:00Z",
                                        "url": "https://github.com/owner/repo/pull/42",
                                    }
                                ]
                            },
                        }
                    }
                }
            },
        )

    monkeypatch.setattr(gi.httpx, "post", fake_post)
    outcome = gi.get_issue_outcome(9)
    assert captured["authorization"] == "Bearer ghs_token"
    assert captured["variables"]["number"] == 9
    assert outcome == {
        "state": "closed",
        "state_reason": "completed",
        "closed_at": "2026-07-20T01:00:00Z",
        "updated_at": "2026-07-20T01:00:00Z",
        "agent_ready": True,
        "closing_pull_requests": [
            {
                "number": 42,
                "state": "merged",
                "is_draft": False,
                "merged": True,
                "updated_at": "2026-07-20T00:59:00Z",
                "merged_at": "2026-07-20T00:59:00Z",
                "closed_at": "2026-07-20T00:59:00Z",
                "url": "https://github.com/owner/repo/pull/42",
            }
        ],
    }
    query = captured["query"]
    for forbidden in ("title", "body", "comments", "commits", "reviews", "author"):
        assert forbidden not in query


def test_github_issue_outcome_falls_back_without_pull_permission(monkeypatch):
    """Existing issue-only App grants still reconcile close/reopen state."""
    from api import github_issues as gi

    monkeypatch.setattr(gi, "_bearer_token", lambda: "ghs_token")
    monkeypatch.setattr(gi, "_repo", lambda: "owner/repo")
    monkeypatch.setattr(
        gi.httpx,
        "post",
        lambda *args, **kwargs: _FakeResp(
            200,
            {"errors": [{"type": "FORBIDDEN"}]},
        ),
    )
    monkeypatch.setattr(
        gi,
        "get_issue_state",
        lambda number: {
            "state": "closed",
            "state_reason": "completed",
            "closed_at": "2026-07-20T01:00:00Z",
            "updated_at": "2026-07-20T01:00:00Z",
        },
    )

    assert gi.get_issue_outcome(9) == {
        "state": "closed",
        "state_reason": "completed",
        "closed_at": "2026-07-20T01:00:00Z",
        "updated_at": "2026-07-20T01:00:00Z",
        "agent_ready": False,
        "closing_pull_requests": [],
    }


# ---------------------------------------------------------------------------
# Sensitivity-gate calibration (over-flagging fix)
# ---------------------------------------------------------------------------


def test_system_prompt_defaults_sensitive_to_false():
    """The triage prompt must not bias the model toward flagging benign reports
    (regression for the 'when unsure, prefer true' over-flagging)."""
    from api.feedback_triage import _system_prompt

    p = _system_prompt()
    assert "prefer true" not in p.lower()
    assert "default to false" in p.lower()
    assert "always include the contains_sensitive" in p.lower()


def test_final_privacy_review_blocks_sensitive_model_output(
    db_with_users,
    monkeypatch,
):
    """The authoring model cannot approve the public prose it generated."""
    from api import feedback_triage as ft
    from api.feedback_triage import triage_and_publish
    from db.models import AgentDecision, FeedbackPublicationOutbox

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    monkeypatch.setattr(ft.llm, "get_client", lambda: object())
    monkeypatch.setattr(
        ft,
        "background_ai_authorized",
        lambda *_args, **_kwargs: True,
    )

    def fake_chat_json(_client, **kwargs):
        if kwargs["insight_type"] == "feedback_publication_privacy_review":
            return {"safe_to_publish": False}
        return {
            "kind": "bug",
            "title": "Alice Chen's recovery chart is wrong",
            "body": "Alice Chen's resting heart rate is 42 bpm.",
            "contains_sensitive": False,
            "priority": "medium",
            "agent_eligible": True,
        }

    monkeypatch.setattr(ft.llm, "chat_json", fake_chat_json)
    row = _new_row(db, user_id, "The recovery chart is wrong")

    result = triage_and_publish(row.id, _session=db)

    assert result["status"] == "needs_review"
    assert calls == []
    assert db.query(FeedbackPublicationOutbox).count() == 0
    decision = db.query(AgentDecision).filter(
        AgentDecision.subject_ref == str(row.id)
    ).one()
    assert decision.output_json["publication_privacy_review_attempted"] is True
    assert decision.output_json["publication_privacy_review_safe"] is False
    assert "Alice" not in json.dumps(decision.output_json)


@pytest.mark.parametrize("malformed", (None, 0, "true", [], {}))
def test_malformed_final_privacy_review_fails_closed(
    db_with_users,
    monkeypatch,
    malformed,
):
    from api.feedback_triage import triage_and_publish
    from db.models import FeedbackPublicationOutbox

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False, privacy_safe=malformed)
    row = _new_row(db, user_id, "The calendar status clips its card")

    result = triage_and_publish(row.id, _session=db)

    assert result["status"] == "needs_review"
    assert calls == []
    assert db.query(FeedbackPublicationOutbox).count() == 0


def test_triage_uses_deterministic_temperature(db_with_users, monkeypatch):
    """Triage must call the model at temperature 0 so the sensitivity verdict
    doesn't vary run-to-run and rarely flip a benign report to sensitive."""
    from api import feedback_triage as ft
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    captured: dict = {}

    monkeypatch.setattr(ft.llm, "get_client", lambda: object())
    monkeypatch.setattr(
        ft,
        "background_ai_authorized",
        lambda *_args, **_kwargs: True,
    )

    def fake_chat_json(client, **kwargs):
        captured.update(kwargs)
        return {"kind": "bug", "title": "T", "body": "B", "contains_sensitive": False}

    monkeypatch.setattr(ft.llm, "chat_json", fake_chat_json)
    row = _new_row(db, user_id, "charts render slowly on the training page")
    triage_and_publish(row.id, _session=db)
    assert captured.get("temperature") == 0.0


# ---------------------------------------------------------------------------
# Screenshot attachment: storage, vision triage, gate, admin serve (issue #337)
# ---------------------------------------------------------------------------

# A minimal valid 1x1 PNG — the magic bytes make sniff() detect image/png.
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)
_TEST_BLOB_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=https;AccountName=syntheticstorage;"
    "AccountKey=private-test-key;EndpointSuffix=core.windows.net"
)


def test_storage_sniff_validate_decode():
    from api import feedback_storage as fs

    assert fs.sniff(_PNG_1PX) == "image/png"
    assert fs.sniff(b"just some plain text, not an image at all") is None
    assert fs.validate_image(_PNG_1PX) == "image/png"
    # Oversize is rejected even though the magic bytes are valid.
    assert fs.validate_image(_PNG_1PX + b"\x00" * (fs.MAX_IMAGE_BYTES + 1)) is None
    # Both a data-URL and raw base64 decode to the same bytes.
    raw = base64.b64encode(_PNG_1PX).decode()
    assert fs.decode_base64_image(raw) == _PNG_1PX
    assert fs.decode_base64_image("data:image/png;base64," + raw) == _PNG_1PX
    assert fs.decode_base64_image("not!!valid!!base64") is None


def test_storage_roundtrip_and_key_safety(db_with_users):
    # db_with_users sets DATA_DIR to a temp dir → local filesystem backend.
    from api import feedback_storage as fs

    assert fs.image_storage_key(
        _PNG_1PX,
        feedback_id=42,
        index=0,
    ) == "feedback/42/0.png"
    with pytest.raises(ValueError):
        fs.image_storage_key(
            b"not an image",
            feedback_id=42,
            index=0,
        )

    provenance = fs.current_storage_provenance()
    assert provenance is not None
    key = fs.store_image(
        _PNG_1PX,
        feedback_id=42,
        index=0,
        provenance=provenance,
    )
    assert key == "feedback/42/0.png"
    got = fs.load_image(key, provenance=provenance)
    assert got is not None and got[0] == _PNG_1PX and got[1] == "image/png"
    # A tampered / traversal key is rejected outright.
    assert fs.load_image("feedback/../../secret", provenance=provenance) is None
    assert fs.load_image("feedback/42/0.exe", provenance=provenance) is None
    # Non-image bytes are never stored.
    assert (
        fs.store_image(
            b"not an image",
            feedback_id=42,
            index=1,
            provenance=provenance,
        )
        is None
    )


def test_storage_failure_logs_omit_screenshot_key_and_local_path(
    monkeypatch,
    caplog,
):
    import errno

    from api import feedback_storage as fs

    feedback_id = 987654321
    key = f"feedback/{feedback_id}/0.png"
    local_root = "/tmp/private-athlete-feedback-path-sentinel"
    storage_url = f"https://storage.invalid/private/{key}"
    caplog.set_level("INFO", logger="api.feedback_storage")
    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )
    blob_provenance = fs.current_storage_provenance()
    assert blob_provenance is not None
    monkeypatch.setattr(fs, "_blob_container_client", lambda: None)

    assert (
        fs.store_image(
            _PNG_1PX,
            feedback_id=feedback_id,
            index=0,
            provenance=blob_provenance,
        )
        is None
    )

    class BrokenUploadClient:
        def upload_blob(self, **_kwargs):
            raise OSError(errno.EIO, "upload unavailable", storage_url)

    monkeypatch.setattr(fs, "_blob_container_client", lambda: BrokenUploadClient())
    assert (
        fs.store_image(
            _PNG_1PX,
            feedback_id=feedback_id,
            index=0,
            provenance=blob_provenance,
        )
        is None
    )

    class BrokenDownload:
        def readall(self):
            raise OSError(errno.EIO, "download unavailable", storage_url)

    class BrokenBlobClient:
        def download_blob(self, _key):
            return BrokenDownload()

    monkeypatch.setattr(fs, "_blob_container_client", lambda: BrokenBlobClient())
    monkeypatch.setattr(fs, "_local_dir", lambda: local_root)
    assert fs.load_image(key, provenance=blob_provenance) is None

    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONTAINER")
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING")
    monkeypatch.setattr(
        fs.os,
        "makedirs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError(errno.EACCES, "directory unavailable", local_root)
        ),
    )
    monkeypatch.setattr(fs, "_local_warned", False)
    local_provenance = fs.current_storage_provenance()
    assert local_provenance is not None
    assert (
        fs.store_image(
            _PNG_1PX,
            feedback_id=feedback_id,
            index=0,
            provenance=local_provenance,
        )
        is None
    )

    rendered = caplog.text
    assert key not in rendered
    assert str(feedback_id) not in rendered
    assert local_root not in rendered
    assert storage_url not in rendered


def test_storage_delete_is_idempotent_exact_and_row_bound(db_with_users):
    from api import feedback_storage as fs

    provenance = fs.current_storage_provenance()
    assert provenance is not None
    key = fs.store_image(
        _PNG_1PX,
        feedback_id=42,
        index=0,
        provenance=provenance,
    )
    assert key == "feedback/42/0.png"

    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(key, feedback_id=43, provenance=provenance)
    assert fs.load_image(key, provenance=provenance) is not None

    fs.delete_image(key, feedback_id=42, provenance=provenance)
    assert fs.load_image(key, provenance=provenance) is None
    fs.delete_image(key, feedback_id=42, provenance=provenance)

    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(
            "feedback/../../secret",
            feedback_id=42,
            provenance=provenance,
        )
    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(
            "feedback/42/0.png\n",
            feedback_id=42,
            provenance=provenance,
        )


def test_storage_delete_uses_only_the_recorded_blob_namespace(
    monkeypatch, tmp_path
):
    from azure.core.exceptions import ResourceNotFoundError
    from api import feedback_storage as fs

    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL", raising=False)

    class MissingBlobClient:
        def __init__(self):
            self.deleted: list[str] = []

        def delete_blob(self, name: str) -> None:
            self.deleted.append(name)
            error = ResourceNotFoundError("missing")
            error.error_code = "BlobNotFound"
            raise error

    client = MissingBlobClient()
    monkeypatch.setattr(fs, "_blob_container_client", lambda: client)
    monkeypatch.setattr(fs, "_local_dir", lambda: str(tmp_path))
    local_path = tmp_path / "feedback" / "42" / "0.png"
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(_PNG_1PX)

    provenance = fs.current_storage_provenance()
    assert provenance is not None
    fs.delete_image(
        "feedback/42/0.png",
        feedback_id=42,
        provenance=provenance,
    )

    assert client.deleted == ["feedback/42/0.png"]
    assert local_path.exists()


def test_storage_delete_rejects_missing_container(monkeypatch, tmp_path):
    from azure.core.exceptions import ResourceNotFoundError
    from api import feedback_storage as fs

    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )
    monkeypatch.setattr(fs, "_local_dir", lambda: str(tmp_path))

    class MissingContainerClient:
        def delete_blob(self, name: str) -> None:
            error = ResourceNotFoundError(f"missing container for {name}")
            error.error_code = "ContainerNotFound"
            raise error

    monkeypatch.setattr(
        fs,
        "_blob_container_client",
        lambda: MissingContainerClient(),
    )
    provenance = fs.current_storage_provenance()
    assert provenance is not None
    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(
            "feedback/42/0.png",
            feedback_id=42,
            provenance=provenance,
        )


def test_storage_delete_fails_closed_when_configured_blob_is_unavailable(
    monkeypatch, tmp_path
):
    from api import feedback_storage as fs

    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )
    monkeypatch.setattr(fs, "_blob_container_client", lambda: None)
    monkeypatch.setattr(
        fs,
        "_local_dir",
        lambda: pytest.fail("configured Azure deletion must not use local storage"),
    )
    provenance = fs.current_storage_provenance()
    assert provenance is not None
    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(
            "feedback/42/0.png",
            feedback_id=42,
            provenance=provenance,
        )


def test_storage_delete_wraps_non_not_found_blob_failure(monkeypatch):
    from api import feedback_storage as fs

    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )

    class FailingBlobClient:
        def delete_blob(self, name: str) -> None:
            raise RuntimeError(f"failed to delete {name}")

    monkeypatch.setattr(fs, "_blob_container_client", lambda: FailingBlobClient())
    provenance = fs.current_storage_provenance()
    assert provenance is not None
    with pytest.raises(fs.FeedbackStorageDeletionError) as exc:
        fs.delete_image(
            "feedback/42/0.png",
            feedback_id=42,
            provenance=provenance,
        )
    assert isinstance(exc.value.__cause__, RuntimeError)


def test_storage_delete_wraps_local_io_failure(monkeypatch, tmp_path):
    from api import feedback_storage as fs

    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", raising=False)
    monkeypatch.delenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        raising=False,
    )
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL", raising=False)
    monkeypatch.setattr(fs, "_local_dir", lambda: str(tmp_path))
    monkeypatch.setattr(
        fs.os,
        "unlink",
        lambda _path: (_ for _ in ()).throw(PermissionError("denied")),
    )
    provenance = fs.current_storage_provenance()
    assert provenance is not None

    with pytest.raises(fs.FeedbackStorageDeletionError) as exc:
        fs.delete_image(
            "feedback/42/0.png",
            feedback_id=42,
            provenance=provenance,
        )
    assert isinstance(exc.value.__cause__, PermissionError)


def test_storage_provenance_fails_closed_after_local_root_drift(
    monkeypatch,
    tmp_path,
):
    from api import feedback_storage as fs

    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", raising=False)
    monkeypatch.delenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        raising=False,
    )
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL", raising=False)
    roots = [tmp_path / "first"]
    monkeypatch.setattr(fs, "_local_dir", lambda: str(roots[0]))
    provenance = fs.current_storage_provenance()
    assert provenance is not None
    key = fs.store_image(
        _PNG_1PX,
        feedback_id=42,
        index=0,
        provenance=provenance,
    )
    assert key is not None
    original_path = roots[0] / "feedback" / "42" / "0.png"
    assert original_path.exists()

    roots[0] = tmp_path / "second"
    assert fs.load_image(key, provenance=provenance) is None
    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(key, feedback_id=42, provenance=provenance)
    assert original_path.exists()


def test_blob_provenance_allows_key_rotation_but_rejects_scope_drift(
    monkeypatch,
):
    import json

    from api import feedback_storage as fs

    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )
    provenance = fs.current_storage_provenance()
    assert provenance is not None
    assert "private-test-key" not in json.dumps(provenance)
    rotated = _TEST_BLOB_CONNECTION_STRING.replace(
        "private-test-key",
        "rotated-private-test-key",
    )
    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING", rotated)
    assert fs.current_storage_provenance() == provenance

    deleted: list[str] = []

    class BlobClient:
        def delete_blob(self, key: str) -> None:
            deleted.append(key)

    monkeypatch.setattr(fs, "_blob_container_client", lambda: BlobClient())
    fs.delete_image(
        "feedback/42/0.png",
        feedback_id=42,
        provenance=provenance,
    )
    assert deleted == ["feedback/42/0.png"]

    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        rotated.replace("syntheticstorage", "differentstorage"),
    )
    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(
            "feedback/42/0.png",
            feedback_id=42,
            provenance=provenance,
        )
    assert deleted == ["feedback/42/0.png"]


@pytest.mark.parametrize("provenance", (None, {}, {"version": 1}))
def test_storage_delete_rejects_missing_or_malformed_provenance(
    db_with_users,
    provenance,
):
    from api import feedback_storage as fs

    with pytest.raises(fs.FeedbackStorageDeletionError):
        fs.delete_image(
            "feedback/42/0.png",
            feedback_id=42,
            provenance=provenance,
        )


def test_configured_blob_upload_never_falls_back_to_local(
    monkeypatch, tmp_path
):
    from api import feedback_storage as fs

    monkeypatch.setenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", "private")
    monkeypatch.setenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        _TEST_BLOB_CONNECTION_STRING,
    )
    monkeypatch.setattr(fs, "_blob_container_client", lambda: None)
    monkeypatch.setattr(
        fs,
        "_local_dir",
        lambda: pytest.fail("configured Blob upload must not write locally"),
    )

    provenance = fs.current_storage_provenance()
    assert provenance is not None
    assert (
        fs.store_image(
            _PNG_1PX,
            feedback_id=42,
            index=0,
            provenance=provenance,
        )
        is None
    )
    assert (
        fs.load_image(
            "feedback/42/0.png",
            provenance=provenance,
        )
        is None
    )


def _row_with_image(db, user_id, message="broken chart on training page"):
    """Persist a feedback row with one real stored screenshot."""
    from api import feedback_storage as fs

    row = _new_row(db, user_id, message)
    provenance = fs.current_storage_provenance()
    assert provenance is not None
    key = fs.store_image(
        _PNG_1PX,
        feedback_id=row.id,
        index=0,
        provenance=provenance,
    )
    row.image_keys = [key]
    row.image_storage_provenance = provenance
    db.commit()
    db.refresh(row)
    return row


def test_feedback_image_is_available_only_to_its_owner(db_with_users):
    from api.routes.feedback import get_own_feedback_image

    db, _, admin_id, user_id = db_with_users
    row = _row_with_image(db, user_id)

    response = get_own_feedback_image(row.id, 0, user_id=user_id, db=db)
    assert response.body == _PNG_1PX
    assert response.media_type == "image/png"
    assert response.headers["cache-control"] == "private, no-store"

    with pytest.raises(HTTPException) as exc:
        get_own_feedback_image(row.id, 0, user_id=admin_id, db=db)
    assert exc.value.status_code == 404


def _stub_vision(monkeypatch, *, description, sensitive):
    from api import feedback_triage as ft

    monkeypatch.setattr(
        ft.feedback_vision,
        "analyze_images",
        lambda images: {"description": description, "sensitive": sensitive},
    )


# --- Submit endpoint: validation + storage ---------------------------------


def test_submit_stores_image_and_sets_keys(db_with_users):
    from api.routes.feedback import submit_feedback, FeedbackRequest
    from api import feedback_storage as fs
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    b64 = base64.b64encode(_PNG_1PX).decode()
    resp = submit_feedback(
        FeedbackRequest(kind="bug", message="broken chart", images=[b64]),
        background_tasks=BackgroundTasks(),
        user_id=user_id,
        db=db,
    )
    row = db.query(Feedback).filter(Feedback.id == resp["id"]).first()
    assert row.image_keys == ["feedback/%d/0.png" % row.id]
    got = fs.load_image(
        row.image_keys[0],
        provenance=row.image_storage_provenance,
    )
    assert got is not None and got[0] == _PNG_1PX


def test_submit_retains_durable_locator_when_storage_is_unavailable(
    db_with_users,
    monkeypatch,
    caplog,
):
    from api.routes.feedback import submit_feedback, FeedbackRequest
    from api import feedback_storage as fs
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("ERROR", logger="api.routes.feedback")
    monkeypatch.setattr(fs, "store_image", lambda *_args, **_kwargs: None)
    b64 = base64.b64encode(_PNG_1PX).decode()

    resp = submit_feedback(
        FeedbackRequest(kind="bug", message="broken chart", images=[b64]),
        background_tasks=BackgroundTasks(),
        user_id=user_id,
        db=db,
    )

    row = db.get(Feedback, resp["id"])
    assert row is not None
    assert row.image_keys == [f"feedback/{row.id}/0.png"]
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "api.routes.feedback"
    ]
    assert any("image upload" in message for message in messages)
    assert all(str(row.id) not in message for message in messages)
    assert all(row.image_keys[0] not in message for message in messages)


def test_submit_skips_unwritable_locator_without_storage_provenance(
    db_with_users,
    monkeypatch,
    caplog,
):
    from api.routes.feedback import FeedbackRequest, submit_feedback
    from api import feedback_storage as fs
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("WARNING", logger="api.routes.feedback")
    monkeypatch.setattr(fs, "current_storage_provenance", lambda: None)
    monkeypatch.setattr(
        fs,
        "store_image",
        lambda *_args, **_kwargs: pytest.fail(
            "an unidentified storage namespace must never be written"
        ),
    )
    b64 = base64.b64encode(_PNG_1PX).decode()

    resp = submit_feedback(
        FeedbackRequest(kind="bug", message="broken chart", images=[b64]),
        background_tasks=BackgroundTasks(),
        user_id=user_id,
        db=db,
    )

    row = db.get(Feedback, resp["id"])
    assert row is not None
    assert row.message == "broken chart"
    assert row.image_keys is None
    assert row.image_storage_provenance is None
    assert "storage provenance is unavailable" in caplog.text
    assert str(row.id) not in caplog.text


def test_image_finalization_exception_log_omits_feedback_locator(
    db_with_users,
    monkeypatch,
    caplog,
):
    from api.routes.feedback import FeedbackRequest, submit_feedback
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    caplog.set_level("ERROR", logger="api.routes.feedback")
    real_commit = db.commit
    commit_calls = 0

    def fail_finalization_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise RuntimeError(_privacy_log_exception_text())
        return real_commit()

    monkeypatch.setattr(db, "commit", fail_finalization_commit)
    b64 = base64.b64encode(_PNG_1PX).decode()

    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(kind="bug", message="broken chart", images=[b64]),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )

    assert exc.value.status_code == 503
    row = db.query(Feedback).order_by(Feedback.id.desc()).first()
    assert row is not None
    assert row.image_keys
    assert "finalization failed" in caplog.text
    _assert_privacy_sentinels_absent(caplog.text)


def test_submit_rejects_non_image_before_persisting(db_with_users):
    from api.routes.feedback import submit_feedback, FeedbackRequest
    from db.models import Feedback

    db, _, _, user_id = db_with_users
    bad = base64.b64encode(b"definitely not an image file").decode()
    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(kind="bug", message="x", images=[bad]),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )
    assert exc.value.status_code == 415
    # Nothing was persisted — validation runs before the row is created.
    assert db.query(Feedback).count() == 0


def test_submit_rejects_oversize_image(db_with_users):
    from api.routes.feedback import submit_feedback, FeedbackRequest
    from api import feedback_storage as fs

    db, _, _, user_id = db_with_users
    big = base64.b64encode(_PNG_1PX + b"\x00" * (fs.MAX_IMAGE_BYTES + 1)).decode()
    with pytest.raises(HTTPException) as exc:
        submit_feedback(
            FeedbackRequest(kind="bug", message="x", images=[big]),
            background_tasks=BackgroundTasks(),
            user_id=user_id,
            db=db,
        )
    assert exc.value.status_code == 413


def test_feedback_request_caps_image_count():
    """Pydantic caps the image count at the schema level (max_length)."""
    from api.routes.feedback import FeedbackRequest
    from pydantic import ValidationError

    b64 = base64.b64encode(_PNG_1PX).decode()
    with pytest.raises(ValidationError):
        FeedbackRequest(kind="bug", message="x", images=[b64, b64, b64, b64])


# --- Triage: vision fold + gate --------------------------------------------


def test_triage_keeps_vision_description_out_of_public_payload(
    db_with_users,
    monkeypatch,
):
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)  # text path is clean
    _stub_vision(
        monkeypatch,
        description="Mara Qin's resting heart rate is 42 bpm beside a broken chart.",
        sensitive=False,
    )
    row = _row_with_image(db, user_id)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    assert result["used_vision"] is True
    db.refresh(row)
    assert row.image_sensitive is False
    assert "Mara Qin" in (row.image_description or "")
    assert "Mara Qin" not in (row.ai_body or "")
    assert "screenshot" in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert len(calls) == 1
    assert "Mara Qin" not in calls[0]["body"]
    assert "42 bpm" not in calls[0]["body"]
    assert "Screenshot context" not in calls[0]["body"]


def test_triage_gate_holds_on_sensitive_image(db_with_users, monkeypatch):
    """Text may be clean, but a vision-flagged sensitive image parks the row."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    _stub_vision(
        monkeypatch,
        description="A dashboard showing the user's face and heart-rate history",
        sensitive=True,
    )
    row = _row_with_image(db, user_id)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert calls == []  # the image is never published to a public issue
    db.refresh(row)
    assert row.image_sensitive is True


@pytest.mark.parametrize("malformed", (0, "", None, [], {}))
def test_vision_malformed_falsy_sensitivity_never_enqueues_or_posts(
    db_with_users,
    monkeypatch,
    malformed,
):
    from api import feedback_triage as ft
    from api.feedback_publication import claim_next_send, send_claim
    from api.feedback_triage import triage_and_publish
    from db.models import FeedbackPublicationOutbox

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    monkeypatch.setattr(ft.llm, "get_client", lambda: object())
    monkeypatch.setattr(
        ft,
        "background_ai_authorized",
        lambda *_args, **_kwargs: True,
    )

    def _model_result(*_args, **kwargs):
        if kwargs.get("images"):
            return {
                "description": "The Training page shows a generic broken chart.",
                "contains_sensitive": malformed,
            }
        return {
            "kind": "bug",
            "title": "Charts crash on Training",
            "body": "The training charts fail to render.",
            "contains_sensitive": False,
            "agent_eligible": True,
        }

    monkeypatch.setattr(ft.llm, "chat_json", _model_result)
    row = _row_with_image(db, user_id)

    result = triage_and_publish(row.id, _session=db)
    claim = claim_next_send(db)
    if claim is not None:
        send_claim(db, *claim)

    db.refresh(row)
    assert result["status"] == "needs_review"
    assert result["used_vision"] is False
    assert row.image_sensitive is None
    assert claim is None
    assert calls == []
    assert (
        db.query(FeedbackPublicationOutbox)
        .filter(FeedbackPublicationOutbox.feedback_id == row.id)
        .count()
        == 0
    )


def test_triage_gate_holds_on_unverified_image_even_with_autofile(db_with_users, monkeypatch):
    """A screenshot present but not vision-verified (no model configured) parks
    the row, overriding the scrub-only autofile opt-in — an unread image is
    unsafe to auto-publish."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI", "true")
    calls: list = []
    _stub_github(monkeypatch, calls)
    # db_with_users clears AZURE_AI_ENDPOINT, so analyze_images returns None.
    row = _row_with_image(db, user_id)
    row.image_description = "stale description from a prior attempt"
    db.commit()

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert calls == []
    db.refresh(row)
    assert row.image_sensitive is None
    assert row.image_description is None


# --- Admin image serve ------------------------------------------------------


def test_admin_image_serve_and_404_and_authz(db_with_users):
    from api.routes.feedback import submit_feedback, get_feedback_image, FeedbackRequest
    from fastapi import Response

    db, _, admin_id, user_id = db_with_users
    b64 = base64.b64encode(_PNG_1PX).decode()
    fid = submit_feedback(
        FeedbackRequest(kind="bug", message="x", images=[b64]),
        background_tasks=BackgroundTasks(),
        user_id=user_id,
        db=db,
    )["id"]

    out = get_feedback_image(fid, 0, user_id=admin_id, db=db)
    assert isinstance(out, Response)
    assert out.body == _PNG_1PX
    assert out.media_type == "image/png"

    # Out-of-range index → 404.
    with pytest.raises(HTTPException) as exc:
        get_feedback_image(fid, 5, user_id=admin_id, db=db)
    assert exc.value.status_code == 404

    # A non-admin is refused before any image is served.
    with pytest.raises(HTTPException) as exc:
        get_feedback_image(fid, 0, user_id=user_id, db=db)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Priority auto-suggestion (issue #359)
# ---------------------------------------------------------------------------


def test_triage_assigns_priority_from_llm(db_with_users, monkeypatch):
    """The LLM's suggested priority lands on the row and a mirroring label."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False, priority="high")
    row = _new_row(db, user_id, "Charts fail to load on the training page")

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    db.refresh(row)
    assert row.priority == "high"
    assert "priority: high" in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "priority: high" in calls[0]["labels"]


def test_triage_ignores_invalid_priority(db_with_users, monkeypatch):
    """A priority outside the allowed set is dropped (no label, NULL column)."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False, priority="urgent")  # not a valid bucket
    row = _new_row(db, user_id, "Charts fail to load on the training page")

    triage_and_publish(row.id, _session=db)
    db.refresh(row)
    assert row.priority is None
    assert not any(str(lbl).startswith("priority:") for lbl in (row.ai_labels or []))


def test_triage_priority_none_without_llm(db_with_users):
    """No LLM configured → rule-based triage leaves priority unset."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    row = _new_row(db, user_id, "Some report with no AI available")

    triage_and_publish(row.id, _session=db)
    db.refresh(row)
    assert row.priority is None


# ---------------------------------------------------------------------------
# Change loop: agent-ready gating for the Copilot coding agent (issue #362)
# ---------------------------------------------------------------------------

_DETAILED_BUG = "The training charts fail to render after a sync completes"
_DETAILED_CJK_BUG = "今日页面状态建议休息，但 Praxys 教练建议完成长距离训练，两条建议相互矛盾"


def test_triage_tags_agent_ready_for_qualifying_bug(db_with_users, monkeypatch):
    """A clean, detailed bug earns agent-ready -- on the row and the filed issue."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    row = _new_row(db, user_id, _DETAILED_BUG)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    assert result["agent_ready"] is False
    db.refresh(row)
    assert "agent-ready" in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" in calls[0]["labels"]
    from db.models import AgentDecision

    decision = db.query(AgentDecision).filter(
        AgentDecision.subject_ref == str(row.id)
    ).one()
    assert decision.output_json["agent_ready_applied"] is True


def test_triage_persists_privacy_minimized_decision_and_outcome(
    db_with_users,
    monkeypatch,
):
    """The durable trace stores structured facts, never feedback text."""
    from api.feedback_triage import triage_and_publish
    from db.models import AgentDecision, AgentOutcome

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    message = (
        "The training charts fail after sync; contact jane@example.com for details"
    )
    row = _new_row(db, user_id, message)
    row.locale = "a@b.co"
    db.commit()

    triage_and_publish(row.id, _session=db)
    decision = (
        db.query(AgentDecision)
        .filter(AgentDecision.subject_ref == str(row.id))
        .one()
    )
    serialized_input = json.dumps(decision.input_json)
    assert message not in serialized_input
    assert "jane@example.com" not in serialized_input
    assert "a@b.co" not in serialized_input
    assert decision.input_json["locale"] == "other"
    assert decision.policy_name == "change.agent_ready"
    assert decision.mode == "active"
    assert decision.output_json["agent_ready_candidate"] is False
    assert decision.output_json["agent_ready_applied"] is False
    outcomes = (
        db.query(AgentOutcome)
        .filter(AgentOutcome.decision_id == decision.id)
        .all()
    )
    assert [outcome.outcome_type for outcome in outcomes] == [
        "held_for_review"
    ]


def test_agent_ready_applied_requires_successful_github_publish(
    db_with_users,
    monkeypatch,
):
    """Policy intent is not counted as an applied label without a filed issue."""
    from api import feedback_triage as ft
    from api.feedback_triage import triage_and_publish
    from db.models import AgentDecision

    db, _, _, user_id = db_with_users
    _stub_llm(monkeypatch, sensitive=False)
    monkeypatch.setattr(ft.github_issues, "is_configured", lambda: False)
    row = _new_row(
        db,
        user_id,
        "Training charts fail after every sync with the same rendering error",
    )

    result = triage_and_publish(row.id, _session=db)
    decision = (
        db.query(AgentDecision)
        .filter(AgentDecision.subject_ref == str(row.id))
        .one()
    )

    assert result["status"] == "triaged"
    assert result["agent_ready"] is False
    assert decision.output_json["agent_ready_candidate"] is True
    assert decision.output_json["agent_ready_requested"] is True
    assert decision.output_json["agent_ready_applied"] is False


def test_outcome_deduplication_preserves_outer_transaction(db_with_users):
    """A duplicate snapshot is ignored without poisoning surrounding writes."""
    from db.agent_loop import record_decision, record_outcome
    from db.models import AgentOutcome

    db, _, _, user_id = db_with_users
    feedback = _new_row(db, user_id, "A detailed reproducible report")
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(feedback.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version=None,
        model="rule-based",
        mode="active",
        input_data={"message_sha256": "a" * 64},
        output_data={"agent_ready_candidate": True},
    )
    first = record_outcome(
        db,
        decision_id=decision.id,
        outcome_type="github_issue_closed",
        source="github",
        payload={"state": "closed"},
        dedupe_key="issue:101:closed:2026-07-20T01:00:00Z",
    )
    db.commit()

    feedback.status = "resolved"
    duplicate = record_outcome(
        db,
        decision_id=decision.id,
        outcome_type="github_issue_closed",
        source="github",
        payload={"state": "closed"},
        dedupe_key="issue:101:closed:2026-07-20T01:00:00Z",
    )
    db.commit()

    assert first is not None
    assert duplicate is None
    db.refresh(feedback)
    assert feedback.status == "resolved"
    assert db.query(AgentOutcome).count() == 1


def test_triage_tags_agent_ready_for_detailed_cjk_bug(db_with_users, monkeypatch):
    """Detailed feedback without whitespace word boundaries still qualifies."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    row = _new_row(db, user_id, _DETAILED_CJK_BUG)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    assert result["agent_ready"] is False
    db.refresh(row)
    assert "agent-ready" in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" in calls[0]["labels"]


def test_triage_no_agent_ready_for_feature(db_with_users, monkeypatch):
    """Features are assist-not-act: published, but never auto-assigned."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False, kind="feature", agent_eligible=False)
    row = _new_row(
        db, user_id, "Please add a weekly mileage target to the goal page", kind="feature"
    )

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" not in calls[0]["labels"]


def test_triage_no_agent_ready_when_sensitive(db_with_users, monkeypatch):
    """A gated (sensitive) report is parked and never tagged agent-ready. The
    label never even lands in ai_labels, so a later admin approve can't assign."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=True)
    row = _new_row(db, user_id, _DETAILED_BUG)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert calls == []  # nothing published
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])


@pytest.mark.parametrize("message", ["totally broken", "页面坏了"])
def test_triage_no_agent_ready_for_low_detail_bug(db_with_users, monkeypatch, message):
    """A terse bug is published but too thin to hand to the coding agent."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)
    row = _new_row(db, user_id, message)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" not in calls[0]["labels"]


def test_triage_no_agent_ready_without_ai_gate(db_with_users, monkeypatch):
    """No AI to judge sensitivity -> the report is parked, not agent-tagged."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)  # GitHub configured, but no LLM stub
    row = _new_row(db, user_id, _DETAILED_BUG)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "needs_review"
    assert calls == []
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])


def test_triage_no_agent_ready_when_not_actionable_bug(db_with_users, monkeypatch):
    """A bug-shaped report the model judges not actionable (works-as-intended, a
    support question, too vague) is published but never handed to the agent."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False, agent_eligible=False)
    row = _new_row(db, user_id, _DETAILED_BUG)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    assert result["agent_ready"] is False
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" not in calls[0]["labels"]


def test_triage_shadow_mode_withholds_agent_ready(db_with_users, monkeypatch):
    """Shadow mode computes the decision but never applies the label, so a
    qualifying bug is filed without auto-assigning the coding agent."""
    from api.feedback_triage import triage_and_publish

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_AGENT_READY_SHADOW", "true")
    calls: list = []
    _stub_github(monkeypatch, calls)
    _stub_llm(monkeypatch, sensitive=False)  # would otherwise qualify
    row = _new_row(db, user_id, _DETAILED_BUG)

    result = triage_and_publish(row.id, _session=db)
    assert result["status"] == "triaged"
    assert result["agent_ready"] is False
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" not in calls[0]["labels"]
    from db.models import AgentDecision

    decision = (
        db.query(AgentDecision)
        .filter(AgentDecision.subject_ref == str(row.id))
        .one()
    )
    assert decision.mode == "shadow"
    assert decision.output_json["agent_ready_candidate"] is True
    assert decision.output_json["agent_ready_applied"] is False


def test_challenger_prompt_is_recorded_but_never_acts(
    db_with_users,
    monkeypatch,
):
    from api import feedback_triage as ft
    from api.feedback_triage import triage_and_publish
    from db.models import AgentDecision

    db, _, _, user_id = db_with_users
    monkeypatch.setenv("PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION", "v2")
    calls: list = []
    _stub_github(monkeypatch, calls)
    monkeypatch.setattr(ft.llm, "get_client", lambda: object())
    monkeypatch.setattr(
        ft,
        "background_ai_authorized",
        lambda *_args, **_kwargs: True,
    )

    def fake_chat_json(client, **kwargs):
        if kwargs["insight_type"] == "feedback_publication_privacy_review":
            return {"safe_to_publish": True}
        eligible = kwargs["insight_type"] == "feedback_triage_challenger"
        return {
            "kind": "bug",
            "title": "Calendar text overflows",
            "body": "The calendar status leaves its day card.",
            "contains_sensitive": False,
            "priority": "low",
            "agent_eligible": eligible,
        }

    monkeypatch.setattr(ft.llm, "chat_json", fake_chat_json)
    row = _new_row(db, user_id, _DETAILED_BUG)
    result = triage_and_publish(row.id, _session=db)

    assert result["agent_ready"] is False
    db.refresh(row)
    assert "agent-ready" not in (row.ai_labels or [])
    assert _publish_queued(db) == "published"
    assert "agent-ready" not in calls[0]["labels"]
    decision = db.query(AgentDecision).filter(
        AgentDecision.subject_ref == str(row.id)
    ).one()
    assert decision.output_json["agent_ready_candidate"] is False
    assert decision.output_json["challenger"] == {
        "prompt_version": "v2",
        "prompt_hash": decision.output_json["challenger"]["prompt_hash"],
        "model": "gpt-5.4",
        "available": True,
        "kind": "bug",
        "agent_eligible": True,
        "agent_ready_candidate": True,
        "agent_ready_reason": "eligible",
    }


# ---------------------------------------------------------------------------
# GitHub issue status sync (issue #359)
# ---------------------------------------------------------------------------


def _stub_issue_state(monkeypatch, mapping):
    """Stub structured GitHub issue/closing-PR outcome reconciliation."""
    from api import github_issues

    monkeypatch.setattr(github_issues, "is_configured", lambda: True)
    monkeypatch.setattr(
        github_issues,
        "issue_matches_configured_repo",
        lambda number, url: True,
    )

    def _state(number):
        st = mapping.get(number)
        if not st:
            return None
        if isinstance(st, dict):
            return st
        return {
            "state": st,
            "state_reason": None,
            "closed_at": None,
            "updated_at": None,
            "agent_ready": False,
            "closing_pull_requests": [],
        }

    monkeypatch.setattr(github_issues, "get_issue_outcome", _state)


def test_sync_marks_resolved_when_issue_closed(db_with_users, monkeypatch):
    from api.routes.feedback import sync_feedback_status
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(user_id=user_id, kind="bug", message="x", status="issue_created", github_issue_number=101)
    db.add(row)
    db.commit()
    db.refresh(row)

    _stub_issue_state(monkeypatch, {101: "closed"})
    out = sync_feedback_status(user_id=admin_id, db=db)
    assert out == {
        "configured": True,
        "checked": 1,
        "updated": 1,
        "repository_mismatches": 0,
    }
    db.refresh(row)
    assert row.status == "resolved"


def test_sync_skips_issue_from_different_configured_repo(
    db_with_users,
    monkeypatch,
    caplog,
):
    from api import github_issues
    from api.routes.feedback import sync_feedback_status
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    issue_number = 908172635
    issue_url = f"https://github.com/old/repo/issues/{issue_number}"
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="x",
        status="issue_created",
        github_issue_number=issue_number,
        github_issue_url=issue_url,
    )
    db.add(row)
    db.commit()
    monkeypatch.setattr(github_issues, "is_configured", lambda: True)
    monkeypatch.setattr(
        github_issues,
        "issue_matches_configured_repo",
        lambda number, url: False,
    )
    monkeypatch.setattr(
        github_issues,
        "get_issue_outcome",
        lambda number: pytest.fail("mismatched issue must not be read"),
    )
    caplog.set_level("WARNING", logger="api.routes.feedback")

    assert sync_feedback_status(user_id=admin_id, db=db) == {
        "configured": True,
        "checked": 0,
        "updated": 0,
        "repository_mismatches": 1,
    }
    assert str(issue_number) not in caplog.text
    assert issue_url not in caplog.text


def test_sync_records_external_label_and_merged_pull_outcomes(
    db_with_users,
    monkeypatch,
):
    from api.routes.feedback import sync_feedback_status
    from db.agent_loop import record_decision
    from db.models import AgentOutcome, Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="x",
        status="issue_created",
        github_issue_number=101,
    )
    db.add(row)
    db.flush()
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version=None,
        model="test",
        mode="active",
        input_data={"detail_word_count": 1, "detail_alnum_count": 20},
        output_data={
            "agent_ready_candidate": False,
            "agent_ready_applied": False,
        },
    )
    db.commit()

    _stub_issue_state(
        monkeypatch,
        {
            101: {
                "state": "closed",
                "state_reason": "completed",
                "closed_at": "2026-07-20T01:00:00Z",
                "updated_at": "2026-07-20T01:00:00Z",
                "agent_ready": True,
                "closing_pull_requests": [
                    {
                        "number": 42,
                        "state": "merged",
                        "is_draft": False,
                        "merged": True,
                        "updated_at": "2026-07-20T00:59:00Z",
                        "merged_at": "2026-07-20T00:59:00Z",
                        "closed_at": "2026-07-20T00:59:00Z",
                        "url": "https://github.com/owner/repo/pull/42",
                    }
                ],
            }
        },
    )
    out = sync_feedback_status(user_id=admin_id, db=db)
    assert out == {
        "configured": True,
        "checked": 1,
        "updated": 1,
        "repository_mismatches": 0,
    }
    outcome_types = {
        row.outcome_type
        for row in db.query(AgentOutcome)
        .filter(AgentOutcome.decision_id == decision.id)
        .all()
    }
    assert outcome_types == {
        "github_issue_closed",
        "github_pull_merged",
        "external_agent_ready",
    }
    merged = (
        db.query(AgentOutcome)
        .filter(
            AgentOutcome.decision_id == decision.id,
            AgentOutcome.outcome_type == "github_pull_merged",
        )
        .one()
    )
    assert merged.observed_at == datetime(2026, 7, 20, 0, 59)

    _stub_issue_state(
        monkeypatch,
        {
            101: {
                "state": "closed",
                "state_reason": "completed",
                "closed_at": "2026-07-20T01:00:00Z",
                "updated_at": "2026-07-20T02:00:00Z",
                "agent_ready": True,
                "closing_pull_requests": [
                    {
                        "number": 42,
                        "state": "merged",
                        "is_draft": False,
                        "merged": True,
                        "updated_at": "2026-07-20T02:00:00Z",
                        "merged_at": "2026-07-20T00:59:00Z",
                        "closed_at": "2026-07-20T00:59:00Z",
                        "url": "https://github.com/owner/repo/pull/42",
                    }
                ],
            }
        },
    )
    sync_feedback_status(user_id=admin_id, db=db)
    assert (
        db.query(AgentOutcome)
        .filter(
            AgentOutcome.decision_id == decision.id,
            AgentOutcome.outcome_type == "github_pull_merged",
        )
        .count()
        == 1
    )


def test_sync_records_pull_draft_to_ready_transition(db_with_users, monkeypatch):
    """A ready-for-review handoff remains visible as a distinct PR outcome."""
    from api import github_issues
    from api.routes.feedback import sync_feedback_status
    from db.agent_loop import record_decision
    from db.models import AgentOutcome, Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="x",
        status="issue_created",
        github_issue_number=101,
    )
    db.add(row)
    db.flush()
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version=None,
        model="test",
        mode="active",
        input_data={"detail_word_count": 1, "detail_alnum_count": 20},
        output_data={
            "agent_ready_candidate": True,
            "agent_ready_applied": True,
        },
    )
    db.commit()

    outcomes = [
        {
            "state": "open",
            "state_reason": None,
            "closed_at": None,
            "updated_at": "2026-07-20T00:10:00Z",
            "agent_ready": True,
            "closing_pull_requests": [
                {
                    "number": 42,
                    "state": "open",
                    "is_draft": True,
                    "merged": False,
                    "updated_at": "2026-07-20T00:10:00Z",
                    "merged_at": None,
                    "closed_at": None,
                    "url": "https://github.com/owner/repo/pull/42",
                }
            ],
        },
        {
            "state": "open",
            "state_reason": None,
            "closed_at": None,
            "updated_at": "2026-07-20T00:20:00Z",
            "agent_ready": True,
            "closing_pull_requests": [
                {
                    "number": 42,
                    "state": "open",
                    "is_draft": False,
                    "merged": False,
                    "updated_at": "2026-07-20T00:20:00Z",
                    "merged_at": None,
                    "closed_at": None,
                    "url": "https://github.com/owner/repo/pull/42",
                }
            ],
        },
    ]
    monkeypatch.setattr(github_issues, "is_configured", lambda: True)
    monkeypatch.setattr(
        github_issues,
        "issue_matches_configured_repo",
        lambda number, url: True,
    )
    monkeypatch.setattr(
        github_issues,
        "get_issue_outcome",
        lambda number: outcomes.pop(0),
    )

    sync_feedback_status(user_id=admin_id, db=db)
    sync_feedback_status(user_id=admin_id, db=db)

    pull_outcomes = (
        db.query(AgentOutcome)
        .filter(
            AgentOutcome.decision_id == decision.id,
            AgentOutcome.outcome_type == "github_pull_open",
        )
        .order_by(AgentOutcome.id.asc())
        .all()
    )
    assert [item.payload_json["is_draft"] for item in pull_outcomes] == [
        True,
        False,
    ]


def test_sync_reopens_resolved_when_issue_open(db_with_users, monkeypatch):
    from api.routes.feedback import sync_feedback_status
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(user_id=user_id, kind="bug", message="x", status="resolved", github_issue_number=55)
    db.add(row)
    db.commit()
    db.refresh(row)

    _stub_issue_state(monkeypatch, {55: "open"})
    out = sync_feedback_status(user_id=admin_id, db=db)
    assert out["updated"] == 1
    db.refresh(row)
    assert row.status == "issue_created"


def test_sync_only_touches_linked_in_flight_rows(db_with_users, monkeypatch):
    """Triage-side and unlinked rows are never queried or mutated."""
    from api.routes.feedback import sync_feedback_status
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    linked = Feedback(user_id=user_id, kind="bug", message="x", status="issue_created", github_issue_number=101)
    pending = Feedback(user_id=user_id, kind="bug", message="y", status="needs_review")
    fresh = Feedback(user_id=user_id, kind="bug", message="z", status="new")
    declined = Feedback(user_id=user_id, kind="bug", message="w", status="rejected", github_issue_number=9)
    db.add_all([linked, pending, fresh, declined])
    db.commit()

    _stub_issue_state(monkeypatch, {101: "closed"})
    out = sync_feedback_status(user_id=admin_id, db=db)
    assert out == {
        "configured": True,
        "checked": 1,
        "updated": 1,
        "repository_mismatches": 0,
    }
    for r in (linked, pending, fresh, declined):
        db.refresh(r)
    assert linked.status == "resolved"
    assert pending.status == "needs_review"
    assert fresh.status == "new"
    assert declined.status == "rejected"


def test_sync_noop_when_github_not_configured(db_with_users, monkeypatch):
    from api.routes.feedback import sync_feedback_status
    from api import github_issues
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    db.add(Feedback(user_id=user_id, kind="bug", message="x", status="issue_created", github_issue_number=7))
    db.commit()

    monkeypatch.setattr(github_issues, "is_configured", lambda: False)
    out = sync_feedback_status(user_id=admin_id, db=db)
    assert out == {
        "configured": False,
        "checked": 0,
        "updated": 0,
        "repository_mismatches": 0,
    }


def test_sync_requires_admin(db_with_users):
    from api.routes.feedback import sync_feedback_status

    db, _, _, user_id = db_with_users
    with pytest.raises(HTTPException) as exc:
        sync_feedback_status(user_id=user_id, db=db)
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# Status filtering (issue #359)
# ---------------------------------------------------------------------------


def test_list_active_filter_excludes_terminal(db_with_users):
    from api.routes.feedback import list_feedback
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    for st in ("new", "issue_created", "resolved", "rejected", "needs_review", "failed"):
        db.add(Feedback(user_id=user_id, kind="bug", message="x", status=st))
    db.commit()

    active = list_feedback(status="active", user_id=admin_id, db=db)
    statuses = {r["status"] for r in active}
    assert "resolved" not in statuses
    assert "rejected" not in statuses
    assert {"new", "issue_created", "needs_review", "failed"} <= statuses
    # priority is exposed in the serialized row.
    assert "priority" in active[0]

    # An exact status still filters precisely, including the new resolved value.
    only_resolved = list_feedback(status="resolved", user_id=admin_id, db=db)
    assert len(only_resolved) == 1
    assert only_resolved[0]["status"] == "resolved"


def test_retry_and_approve_blocked_on_linked_resolved_row(db_with_users):
    """A resolved ticket still owns a live GitHub issue — retry/approve must be
    refused so we never file a duplicate on the public tracker (issue #359)."""
    from api.routes.feedback import update_feedback, FeedbackAction
    from db.models import Feedback

    db, _, admin_id, user_id = db_with_users
    row = Feedback(
        user_id=user_id,
        kind="bug",
        message="x",
        status="resolved",
        github_issue_number=101,
        github_issue_url="https://github.com/x/y/issues/101",
        ai_title="t",
        ai_body="b",
        ai_labels=["bug", "feedback"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    for action in ("retry", "approve"):
        bg = BackgroundTasks()
        with pytest.raises(HTTPException) as exc:
            update_feedback(row.id, FeedbackAction(action=action), bg, user_id=admin_id, db=db)
        assert exc.value.status_code == 409, action
        assert len(bg.tasks) == 0, action

    # Untouched: still resolved and linked to the original issue (no duplicate).
    db.refresh(row)
    assert row.status == "resolved"
    assert row.github_issue_number == 101
