"""Integration tests for the post-sync LLM insight hook.

The runner has its own unit tests; here we verify the *wiring* — that
``_run_sync`` (api/routes/sync.py) and ``_sync_connection`` (db/sync_scheduler.py)
both invoke ``run_insights_for_user`` with the correct ``counts`` and that a
runner failure can never break the surrounding sync.

We mock the platform fetch + DB writer at the function level so this stays
self-contained: the test is about hook wiring, not actual sync data.
"""
from __future__ import annotations

import tempfile
from datetime import date, datetime, timedelta, timezone

import pytest


@pytest.fixture
def sync_setup(monkeypatch):
    """Init DB + seed a user for the sync hook tests."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )

    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db.models import User

    user_id = "post-sync-hook-user"
    db = db_session.SessionLocal()
    try:
        db.add(User(
            id=user_id,
            email="hook@example.com",
            hashed_password="x",
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
        ))
        db.commit()
    finally:
        db.close()

    yield user_id, tmpdir


def test_run_sync_invokes_insight_runner_with_counts(sync_setup, monkeypatch):
    """When sync writes new rows, the post-sync hook fires with those counts."""
    user_id, _ = sync_setup
    captured: dict = {}

    def _fake_sync_garmin(user_id, creds, from_date, db):
        return {"activities": 3, "splits": 12}

    def _fake_run_insights(uid, db, counts):
        captured["user_id"] = uid
        captured["counts"] = dict(counts)
        return {"daily_brief": "generated"}

    from api.routes import sync as sync_module
    monkeypatch.setattr(sync_module, "_sync_garmin", _fake_sync_garmin)
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user", _fake_run_insights
    )

    sync_module._run_sync(user_id, "garmin", {"email": "e", "password": "p"})

    assert captured["user_id"] == user_id
    assert captured["counts"] == {"activities": 3, "splits": 12}


def test_run_sync_completes_when_insight_runner_raises(sync_setup, monkeypatch):
    """A runner exception must not break the surrounding sync — status stays
    'done', the connection's last_sync still updates, no insight rows leak."""
    user_id, _ = sync_setup

    def _fake_sync_garmin(user_id, creds, from_date, db):
        return {"activities": 1, "splits": 4}

    def _exploding_runner(*args, **kwargs):
        raise RuntimeError("simulated LLM tier failure")

    from api.routes import sync as sync_module
    from db.models import AiInsight, UserConnection
    from db.session import SessionLocal

    # Pre-create a connection so _run_sync's last_sync update has a target.
    db = SessionLocal()
    try:
        db.add(UserConnection(
            user_id=user_id, platform="garmin",
            encrypted_credentials=b"x", wrapped_dek=b"x",
            status="syncing",
        ))
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(sync_module, "_sync_garmin", _fake_sync_garmin)
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user", _exploding_runner
    )

    # Should NOT raise.
    sync_module._run_sync(user_id, "garmin", {"email": "e", "password": "p"})

    # Sync state must reflect a successful sync despite the hook explosion.
    db = SessionLocal()
    try:
        conn = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).one()
        assert conn.status == "connected"
        assert conn.last_sync is not None

        # Runner exploded -> no AiInsight rows written.
        assert db.query(AiInsight).filter_by(user_id=user_id).count() == 0
    finally:
        db.close()


def test_manual_sync_runs_adjustment_before_insights(sync_setup, monkeypatch):
    user_id, _ = sync_setup
    calls: list[str] = []

    from api.routes import sync as sync_module

    monkeypatch.setattr(
        sync_module,
        "_sync_garmin",
        lambda user_id, creds, from_date, db, **kwargs: {
            "activities": 1
        },
    )
    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda user_id, *, trigger: (
            calls.append(f"adjust:{trigger}") or {"status": "no_change"}
        ),
    )
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user",
        lambda user_id, db, counts: (
            calls.append("insights") or {"daily_brief": "generated"}
        ),
    )

    sync_module._run_sync(user_id, "garmin", {"email": "e", "password": "p"})

    assert calls == ["adjust:manual_sync:garmin", "insights"]


def test_manual_sync_cancels_if_authorization_is_lost_before_commit(
    sync_setup,
    monkeypatch,
) -> None:
    user_id, _ = sync_setup
    from api.china_client_boundary import (
        CN_WEB_CLIENT,
        DISABLE_CN_PROCESSING_ENV,
    )
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from api.legal_receipts import TERMS_ACCEPTANCE_ACTION
    from api.routes import sync as sync_module
    from db.connection_credentials import connection_credentials_generation
    from db.models import (
        Activity,
        TermsAcceptanceReceipt,
        UserConnection,
    )
    from db.session import SessionLocal

    with SessionLocal() as db:
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            encrypted_credentials=b"x",
            wrapped_dek=b"x",
            status="connected",
        )
        db.add(connection)
        db.add(TermsAcceptanceReceipt(
            user_id=user_id,
            action=TERMS_ACCEPTANCE_ACTION,
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
            channel=CN_WEB_CLIENT,
            accepted_at=datetime.now(timezone.utc),
        ))
        db.commit()
        generation = connection_credentials_generation(connection)

    post_sync_calls: list[str] = []
    token_publications: list[str] = []

    def disable_after_staging(
        called_user_id,
        creds,
        from_date,
        db,
        **kwargs,
    ):
        del creds, from_date, kwargs
        db.add(Activity(
            user_id=called_user_id,
            activity_id="authorization-race",
            date=date(2026, 8, 29),
        ))
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
        return {"activities": 1}

    monkeypatch.setattr(sync_module, "_sync_garmin", disable_after_staging)
    monkeypatch.setattr(
        sync_module,
        "_persist_garmin_token_state_after_rollback",
        lambda *_args, **_kwargs: (
            token_publications.append("published") or True
        ),
    )
    monkeypatch.setattr(
        sync_module,
        "_run_post_sync_plan_adjustment",
        lambda *_args, **_kwargs: post_sync_calls.append("adjustment"),
    )
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user",
        lambda *_args, **_kwargs: post_sync_calls.append("insights"),
    )

    sync_module._run_sync(
        user_id,
        "garmin",
        {"email": "e", "password": "p"},
        expected_connection_generation=generation,
    )

    with SessionLocal() as db:
        assert db.query(Activity).filter_by(
            user_id=user_id,
            activity_id="authorization-race",
        ).count() == 0
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        assert connection.last_sync is None
        assert connection.status == "connected"
    assert sync_module._get_user_status(user_id)["garmin"] == {
        "status": "idle",
        "last_sync": None,
        "error": None,
    }
    assert token_publications == []
    assert post_sync_calls == []


def test_manual_sync_failure_bookkeeping_cancels_on_authorization_loss(
    sync_setup,
    monkeypatch,
) -> None:
    user_id, _ = sync_setup
    from api.china_client_boundary import (
        CN_WEB_CLIENT,
        DISABLE_CN_PROCESSING_ENV,
    )
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from api.legal_receipts import TERMS_ACCEPTANCE_ACTION
    from api.routes import sync as sync_module
    from db.models import TermsAcceptanceReceipt, UserConnection
    from db.session import SessionLocal

    with SessionLocal() as db:
        db.add(UserConnection(
            user_id=user_id,
            platform="oura",
            encrypted_credentials=b"x",
            wrapped_dek=b"x",
            status="connected",
            consecutive_failures=0,
        ))
        db.add(TermsAcceptanceReceipt(
            user_id=user_id,
            action=TERMS_ACCEPTANCE_ACTION,
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
            channel=CN_WEB_CLIENT,
            accepted_at=datetime.now(timezone.utc),
        ))
        db.commit()

    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")

    def disable_during_provider_failure(*_args, **_kwargs):
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
        raise RuntimeError("provider failed")

    monkeypatch.setattr(
        sync_module,
        "_sync_oura",
        disable_during_provider_failure,
    )
    telemetry_calls: list[str] = []
    monkeypatch.setattr(
        "api.telemetry.record_sync",
        lambda **_kwargs: telemetry_calls.append("failure"),
    )

    sync_module._run_sync(user_id, "oura", {"token": "secret"})

    with SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="oura",
        ).one()
        assert connection.status == "connected"
        assert connection.consecutive_failures == 0
        assert connection.last_error is None
        assert connection.next_retry_at is None
    assert sync_module._get_user_status(user_id)["oura"] == {
        "status": "idle",
        "last_sync": None,
        "error": None,
    }
    assert telemetry_calls == []


def test_scheduled_sync_runs_adjustment_before_insights(
    sync_setup,
    monkeypatch,
):
    user_id, _ = sync_setup
    calls: list[str] = []

    from api.routes import sync as sync_module
    from db import sync_scheduler
    from db.models import UserConnection
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        db.add(UserConnection(
            user_id=user_id,
            platform="garmin",
            encrypted_credentials=b"x",
            wrapped_dek=b"x",
            status="connected",
        ))
        db.commit()
        monkeypatch.setattr(
            "db.connection_credentials.load_connection_credentials",
            lambda db, *, user_id, platform: {
                "email": "e",
                "password": "p",
            },
        )
        monkeypatch.setattr(
            sync_module,
            "_sync_garmin",
            lambda user_id, creds, from_date, db, **kwargs: {
                "activities": 1
            },
        )
        monkeypatch.setattr(
            "api.plan_adjustments.run_plan_adjustment_for_user",
            lambda user_id, *, trigger: (
                calls.append(f"adjust:{trigger}") or {"status": "no_change"}
            ),
        )
        monkeypatch.setattr(
            "api.insights_runner.run_insights_for_user",
            lambda user_id, db, counts: (
                calls.append("insights") or {"daily_brief": "generated"}
            ),
        )

        sync_scheduler._sync_connection(user_id, "garmin", db)
    finally:
        db.close()

    assert calls == ["adjust:scheduled_sync:garmin", "insights"]


def test_scheduled_sync_cancels_staged_data_after_authorization_loss(
    sync_setup,
    monkeypatch,
) -> None:
    user_id, _ = sync_setup
    from api.china_client_boundary import (
        CN_WEB_CLIENT,
        DISABLE_CN_PROCESSING_ENV,
    )
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from api.legal_receipts import TERMS_ACCEPTANCE_ACTION
    from api.routes import sync as sync_module
    from db import sync_scheduler
    from db.models import (
        TermsAcceptanceReceipt,
        UserConfig,
        UserConnection,
    )
    from db.session import SessionLocal

    with SessionLocal() as db:
        db.add_all([
            UserConnection(
                user_id=user_id,
                platform="oura",
                encrypted_credentials=b"x",
                wrapped_dek=b"x",
                status="connected",
            ),
            TermsAcceptanceReceipt(
                user_id=user_id,
                action=TERMS_ACCEPTANCE_ACTION,
                terms_version=TERMS_VERSION,
                terms_digest=TERMS_CONTENT_DIGEST,
                channel=CN_WEB_CLIENT,
                accepted_at=datetime.now(timezone.utc),
            ),
        ])
        db.commit()

    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")
    monkeypatch.setattr(
        "db.connection_credentials.load_connection_credentials",
        lambda *_args, **_kwargs: {"token": "secret"},
    )
    post_sync_calls: list[str] = []

    def stage_then_disable(called_user_id, _creds, _from_date, db):
        db.add(UserConfig(
            user_id=called_user_id,
            display_name="must roll back",
        ))
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
        return {"recovery": 1}

    monkeypatch.setattr(sync_module, "_sync_oura", stage_then_disable)
    monkeypatch.setattr(
        "api.telemetry.record_sync",
        lambda **_kwargs: post_sync_calls.append("telemetry"),
    )
    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda *_args, **_kwargs: post_sync_calls.append("adjustment"),
    )
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user",
        lambda *_args, **_kwargs: post_sync_calls.append("insights"),
    )

    with SessionLocal() as db:
        sync_scheduler._sync_connection(user_id, "oura", db)

    with SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="oura",
        ).one()
        assert db.get(UserConfig, user_id) is None
        assert connection.last_sync is None
        assert connection.status == "connected"
        assert connection.consecutive_failures == 0
        assert connection.next_retry_at is None
        assert connection.last_error is None
    assert post_sync_calls == []


def test_scheduled_sync_cancels_cp_last_sync_and_post_work(
    sync_setup,
    monkeypatch,
) -> None:
    user_id, _ = sync_setup
    from api.china_client_boundary import (
        CN_WEB_CLIENT,
        DISABLE_CN_PROCESSING_ENV,
    )
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from api.legal_receipts import TERMS_ACCEPTANCE_ACTION
    from api.routes import sync as sync_module
    from db import sync_scheduler
    from db.models import (
        Activity,
        TermsAcceptanceReceipt,
        UserConfig,
        UserConnection,
    )
    from db.session import SessionLocal

    with SessionLocal() as db:
        db.add_all([
            UserConnection(
                user_id=user_id,
                platform="strava",
                encrypted_credentials=b"x",
                wrapped_dek=b"x",
                status="connected",
            ),
            TermsAcceptanceReceipt(
                user_id=user_id,
                action=TERMS_ACCEPTANCE_ACTION,
                terms_version=TERMS_VERSION,
                terms_digest=TERMS_CONTENT_DIGEST,
                channel=CN_WEB_CLIENT,
                accepted_at=datetime.now(timezone.utc),
            ),
        ])
        db.commit()

    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")
    monkeypatch.setattr(
        "db.connection_credentials.load_connection_credentials",
        lambda *_args, **_kwargs: {"access_token": "secret"},
    )

    def stage_provider_data(called_user_id, _creds, _from_date, db):
        db.add(Activity(
            user_id=called_user_id,
            activity_id="scheduled-provider-commit",
            date=date(2026, 8, 29),
        ))
        return {"activities": 1}

    def stage_cp_then_disable(called_user_id, db):
        db.add(UserConfig(
            user_id=called_user_id,
            display_name="cp must roll back",
        ))
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
        return {
            "cp_watts": 250.0,
            "r_squared": 0.9,
            "point_count": 10,
        }

    post_sync_calls: list[str] = []
    monkeypatch.setattr(sync_module, "_sync_strava", stage_provider_data)
    monkeypatch.setattr(
        "db.sync_writer.update_cp_from_activities",
        stage_cp_then_disable,
    )
    monkeypatch.setattr(
        "api.telemetry.record_sync",
        lambda **_kwargs: post_sync_calls.append("telemetry"),
    )
    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda *_args, **_kwargs: post_sync_calls.append("adjustment"),
    )
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user",
        lambda *_args, **_kwargs: post_sync_calls.append("insights"),
    )

    with SessionLocal() as db:
        sync_scheduler._sync_connection(user_id, "strava", db)

    with SessionLocal() as db:
        assert db.query(Activity).filter_by(
            user_id=user_id,
            activity_id="scheduled-provider-commit",
        ).count() == 1
        assert db.get(UserConfig, user_id) is None
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="strava",
        ).one()
        assert connection.last_sync is None
        assert connection.status == "connected"
        assert connection.consecutive_failures == 0
    assert post_sync_calls == []
