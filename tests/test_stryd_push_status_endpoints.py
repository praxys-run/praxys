"""Endpoint-level tests for durable Stryd delivery-state isolation."""
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    """TestClient with a temp DATA_DIR and overridable 'current user'."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY", "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o="
    )
    monkeypatch.setenv("PRAXYS_JWT_SECRET", "test-secret-endpoint-push-status")

    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    # Point the plan module's _STRYD_PUSH_STATUS_DIR into the scratch dir too.
    from api.routes import plan as plan_mod
    scratch_root = os.path.join(tmpdir.name, "ai", "stryd_push_status")
    monkeypatch.setattr(plan_mod, "_DATA_DIR", tmpdir.name)
    monkeypatch.setattr(plan_mod, "_STRYD_PUSH_STATUS_DIR", scratch_root)

    from api.main import app
    from api.auth import get_current_user_id, get_data_user_id, require_write_access
    from db.session import get_db

    current_user_id = {"value": "alice"}
    ensured_users: set[str] = set()

    def _override_current_user():
        user_id = current_user_id["value"]
        if user_id not in ensured_users:
            from db.crypto import get_vault
            from db.models import User, UserConnection

            db = db_session.SessionLocal()
            try:
                if db.get(User, user_id) is None:
                    db.add(User(
                        id=user_id,
                        email=f"{user_id}@example.test",
                        hashed_password="test",
                    ))
                if db.query(UserConnection).filter_by(
                    user_id=user_id,
                    platform="stryd",
                ).first() is None:
                    encrypted, wrapped_dek = get_vault().encrypt(json.dumps({
                        "email": f"{user_id}@stryd.test",
                        "password": f"password-{user_id}",
                    }))
                    db.add(UserConnection(
                        user_id=user_id,
                        platform="stryd",
                        encrypted_credentials=encrypted,
                        wrapped_dek=wrapped_dek,
                        status="connected",
                    ))
                    db.commit()
                ensured_users.add(user_id)
            finally:
                db.close()
        return user_id

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = _override_current_user
    app.dependency_overrides[get_data_user_id] = _override_current_user
    app.dependency_overrides[require_write_access] = _override_current_user
    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app)
    try:
        yield {"client": client, "current": current_user_id}
    finally:
        app.dependency_overrides.clear()
        if db_session.engine is not None:
            db_session.engine.dispose()
        if db_session.async_engine is not None:
            import asyncio
            try:
                asyncio.run(db_session.async_engine.dispose())
            except RuntimeError:
                pass
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _store_stryd_credentials(
    user_id: str,
    *,
    email: str,
    password: str,
) -> None:
    from db import session as db_session
    from db.crypto import get_vault
    from db.models import UserConnection

    db = db_session.SessionLocal()
    try:
        encrypted, wrapped_dek = get_vault().encrypt(json.dumps({
            "email": email,
            "password": password,
        }))
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="stryd",
        ).one()
        connection.encrypted_credentials = encrypted
        connection.wrapped_dek = wrapped_dek
        connection.status = "connected"
        db.commit()
    finally:
        db.close()


def _delete_stryd_credentials(user_id: str) -> None:
    from db import session as db_session
    from db.models import UserConnection

    db = db_session.SessionLocal()
    try:
        db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="stryd",
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _corrupt_stryd_credentials(user_id: str) -> None:
    from db import session as db_session
    from db.models import UserConnection

    db = db_session.SessionLocal()
    try:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="stryd",
        ).one()
        connection.encrypted_credentials = b"not-a-fernet-token"
        db.commit()
    finally:
        db.close()


def _seed_synced_delivery(
    user_id: str,
    workout_date: str,
    external_id: str,
    *,
    workout_type: str = "easy_run",
    provider_account_id: str | None = None,
) -> None:
    from db import session as db_session
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
    )

    db = db_session.SessionLocal()
    try:
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="stryd",
            snapshot={
                "date": workout_date,
                "source": "ai",
                "workout_type": workout_type,
                "workout_description": "",
            },
        )
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="deliver",
        )
        assert disposition == "started"
        assert attempt is not None
        complete_delivery_attempt(
            db,
            user_id=user_id,
            delivery_id=delivery.id,
            attempt_id=attempt.id,
            attempt_state="synced",
            external_id=external_id,
            provider_account_id=provider_account_id,
        )
        db.commit()
    finally:
        db.close()


def _delivery_rows(user_id: str) -> list[dict]:
    from db import session as db_session
    from db.models import PlanDelivery

    db = db_session.SessionLocal()
    try:
        rows = db.query(PlanDelivery).filter(
            PlanDelivery.user_id == user_id,
        ).order_by(PlanDelivery.created_at).all()
        return [
            {
                "external_id": row.external_id,
                "state": row.state,
                "date": row.workout_date.isoformat(),
            }
            for row in rows
        ]
    finally:
        db.close()


def _attempt_rows(user_id: str) -> list[dict]:
    from db import session as db_session
    from db.models import PlanDelivery, PlanDeliveryAttempt

    db = db_session.SessionLocal()
    try:
        rows = db.query(PlanDeliveryAttempt).join(
            PlanDelivery,
            PlanDelivery.id == PlanDeliveryAttempt.delivery_id,
        ).filter(
            PlanDelivery.user_id == user_id,
        ).order_by(PlanDeliveryAttempt.attempt_number).all()
        return [
            {
                "number": row.attempt_number,
                "operation": row.operation,
                "state": row.state,
            }
            for row in rows
        ]
    finally:
        db.close()


def test_plan_stryd_status_returns_only_current_users_data(api_client):
    """User B's /plan GET must not surface user A's push status writes via
    the embedded `stryd_status` field. (This used to be its own
    /plan/stryd-status route; the isolation invariant must survive the
    merge into /plan.)
    """
    _seed_synced_delivery("alice", "2026-05-01", "alice-only")
    _seed_synced_delivery("bob", "2026-06-15", "bob-only")

    # No need to stub the data layer — the test DB is fresh, so the L1 plan
    # pack naturally returns an empty workouts list. The legacy stub on
    # ``api.routes.plan.get_dashboard_data`` is no longer required because
    # the GET path uses ``RequestContext`` instead of the monolithic
    # dashboard recompute.

    api_client["current"]["value"] = "bob"
    res = api_client["client"].get("/api/plan")
    assert res.status_code == 200, res.text
    assert res.json()["stryd_status"]["2026-06-15"]["workout_id"] == "bob-only"

    api_client["current"]["value"] = "alice"
    # Bypass the cache by sending an If-None-Match the server doesn't have —
    # ETag is keyed on (user_id, plans-rev, date) and Bob's earlier 200
    # populated the browser-side ETag for Bob, not Alice. Both 200s are
    # fresh, so this is a sanity check that user-id is in the ETag salt.
    res = api_client["client"].get(
        "/api/plan", headers={"If-None-Match": '"never-matches"'},
    )
    assert res.json()["stryd_status"]["2026-05-01"]["workout_id"] == "alice-only"


def test_plan_get_does_not_call_get_dashboard_data(api_client, monkeypatch):
    """Regression guard: GET /api/plan used to recompute the entire dashboard
    just to extract the upcoming-workouts list, and was perceptibly slower
    than the cached /api/today and /api/training surfaces. After the L1
    plan-pack rewrite, the GET path must not touch ``get_dashboard_data``.

    A future regression that re-introduces the call (e.g. someone pulls
    ``latest_cp`` from there to fix a downstream bug) would silently
    re-inflate cold-load latency — this test fails fast in that case.
    """
    sentinel: dict[str, int] = {"calls": 0}

    def _explode(user_id, db):
        sentinel["calls"] += 1
        raise AssertionError(
            "GET /api/plan called get_dashboard_data — perf regression. "
            "Use the L1 plan pack via RequestContext instead."
        )

    monkeypatch.setattr("api.routes.plan.get_dashboard_data", _explode)

    api_client["current"]["value"] = "alice"
    res = api_client["client"].get("/api/plan")
    assert res.status_code == 200, res.text
    assert sentinel["calls"] == 0


def test_plan_get_returns_304_on_warm_revalidation(api_client):
    """GET /api/plan honors If-None-Match so warm visits skip re-serving the
    body. This piggybacks on the ENDPOINT_SCOPES["plan"] = ("plans",) entry;
    a future change that drops the ETag guard from the route would replay
    the full body on every page load.
    """
    api_client["current"]["value"] = "dora"
    cold = api_client["client"].get("/api/plan")
    assert cold.status_code == 200, cold.text
    etag = cold.headers.get("etag")
    assert etag, "cold response must carry an ETag"

    warm = api_client["client"].get("/api/plan", headers={"If-None-Match": etag})
    assert warm.status_code == 304
    assert warm.content == b""


def test_plan_get_etag_flips_after_stryd_push(api_client, monkeypatch):
    """A Stryd push changes delivery state outside the plan rows, so the push
    handler must bump the ``plans`` scope and avoid serving a stale 304.
    """
    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api", lambda e, p: ("sid", "tok"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks", lambda workout, cp: [],
    )
    monkeypatch.setattr(
        "sync.stryd_sync.create_workout_api",
        lambda **kw: {"id": f"new-{kw.get('workout_date')}"},
    )

    plan_df = pd.DataFrame([{
        "date": "2026-05-07", "workout_type": "easy_run",
        "planned_duration_min": 45, "workout_description": "easy",
        "target_power_min": 200, "target_power_max": 230, "source": "ai",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df, "all_plans": plan_df, "latest_cp": 260.0, "activities": pd.DataFrame(),
            "signal": {}, "training_base": "power",
        },
    )

    api_client["current"]["value"] = "erin"
    cold = api_client["client"].get("/api/plan")
    pre_etag = cold.headers["etag"]
    assert cold.json()["stryd_status"] == {}

    push_res = api_client["client"].post(
        "/api/plan/push-stryd", json={"workout_dates": ["2026-05-07"]},
    )
    assert push_res.status_code == 200, push_res.text

    after = api_client["client"].get(
        "/api/plan", headers={"If-None-Match": pre_etag},
    )
    # The pre-push ETag must NOT match — otherwise the user would see a 304
    # and miss the push status they just created.
    assert after.status_code == 200, (
        "ETag did not flip after Stryd push — stryd_status served stale via 304"
    )
    assert "2026-05-07" in after.json()["stryd_status"]


def test_push_uses_calling_users_encrypted_stryd_credentials(
    api_client,
    monkeypatch,
):
    workout_date = "2026-05-07"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "workout_type": "easy",
        "planned_duration_min": 45,
        "workout_description": "easy",
        "target_power_min": 200,
        "target_power_max": 230,
        "source": "ai",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [],
    )
    logins: list[tuple[str, str]] = []

    def _login(email: str, password: str) -> tuple[str, str]:
        logins.append((email, password))
        return f"provider-{email}", f"token-{email}"

    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    monkeypatch.setattr(
        "sync.stryd_sync.create_workout_api",
        lambda **kwargs: {"id": f"id-{kwargs['user_id']}"},
    )
    monkeypatch.setenv("STRYD_EMAIL", "global@example.test")
    monkeypatch.setenv("STRYD_PASSWORD", "global-password")

    for user_id, email, password in (
        ("credential-alice", "alice@stryd.test", "alice-secret"),
        ("credential-bob", "bob@stryd.test", "bob-secret"),
    ):
        api_client["current"]["value"] = user_id
        assert api_client["client"].get("/api/plan").status_code == 200
        _store_stryd_credentials(
            user_id,
            email=email,
            password=password,
        )
        response = api_client["client"].post(
            "/api/plan/push-stryd",
            json={"workout_dates": [workout_date]},
        )
        assert response.status_code == 200, response.text

    assert logins == [
        ("alice@stryd.test", "alice-secret"),
        ("bob@stryd.test", "bob-secret"),
    ]


def test_unpinned_global_stryd_credentials_are_not_used(
    api_client,
    monkeypatch,
):
    user_id = "no-stryd-credentials"
    api_client["current"]["value"] = user_id
    assert api_client["client"].get("/api/plan").status_code == 200
    _delete_stryd_credentials(user_id)

    monkeypatch.setenv("PRAXYS_ENV", "development")
    monkeypatch.delenv("PRAXYS_STRYD_ENV_USER_ID", raising=False)
    monkeypatch.setenv("STRYD_EMAIL", "global@example.test")
    monkeypatch.setenv("STRYD_PASSWORD", "global-password")
    monkeypatch.setattr(
        "api.plan_delivery.credentials.dotenv_values",
        lambda path: {},
    )
    calls = {"login": 0}

    def _login(email: str, password: str) -> tuple[str, str]:
        calls["login"] += 1
        return "provider-user", "token"

    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": ["2026-05-07"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No Stryd credentials. Connect Stryd in Settings first."
    )
    assert calls["login"] == 0


def test_unreadable_stored_stryd_credentials_require_reconnect(
    api_client,
    monkeypatch,
):
    user_id = "corrupt-stryd-credentials"
    api_client["current"]["value"] = user_id
    assert api_client["client"].get("/api/plan").status_code == 200
    _corrupt_stryd_credentials(user_id)
    calls = {"login": 0}

    def _login(email: str, password: str) -> tuple[str, str]:
        calls["login"] += 1
        return "provider-user", "token"

    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": ["2026-05-07"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Stored Stryd credentials are unavailable. Reconnect Stryd."
    )
    assert calls["login"] == 0


def test_key_vault_credential_failure_requires_reconnect(
    api_client,
    monkeypatch,
):
    from azure.core.exceptions import AzureError

    user_id = "key-vault-failure-user"
    api_client["current"]["value"] = user_id
    assert api_client["client"].get("/api/plan").status_code == 200

    class FailingVault:
        def decrypt(self, encrypted_data, wrapped_dek):
            raise AzureError("key vault unavailable")

    monkeypatch.setattr(
        "db.connection_credentials.get_vault",
        lambda: FailingVault(),
    )
    calls = {"login": 0}

    def _login(email: str, password: str) -> tuple[str, str]:
        calls["login"] += 1
        return "provider-user", "token"

    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": ["2026-05-07"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Stored Stryd credentials are unavailable. Reconnect Stryd."
    )
    assert calls["login"] == 0


def test_pinned_development_user_can_use_legacy_stryd_environment(
    api_client,
    monkeypatch,
):
    user_id = "legacy-local-user"
    workout_date = "2026-05-07"
    api_client["current"]["value"] = user_id
    assert api_client["client"].get("/api/plan").status_code == 200
    _delete_stryd_credentials(user_id)

    monkeypatch.setenv("PRAXYS_ENV", "development")
    monkeypatch.setenv("PRAXYS_STRYD_ENV_USER_ID", user_id)
    monkeypatch.setenv("STRYD_EMAIL", "local@example.test")
    monkeypatch.setenv("STRYD_PASSWORD", "local-password")
    monkeypatch.setattr(
        "api.plan_delivery.credentials.dotenv_values",
        lambda path: {},
    )
    captured: dict[str, str] = {}

    def _login(email: str, password: str) -> tuple[str, str]:
        captured.update(email=email, password=password)
        return "local-provider-user", "local-token"

    plan_df = pd.DataFrame([{
        "date": workout_date,
        "workout_type": "easy",
        "planned_duration_min": 45,
        "workout_description": "easy",
        "source": "ai",
    }])
    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [],
    )
    monkeypatch.setattr(
        "sync.stryd_sync.create_workout_api",
        lambda **kwargs: {"id": "legacy-local-id"},
    )
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["workout_id"] == "legacy-local-id"
    assert captured == {
        "email": "local@example.test",
        "password": "local-password",
    }


def test_push_endpoint_persists_under_calling_user(api_client, monkeypatch):
    """POST writes the caller's ledger and rolling-deploy compatibility file."""
    from api.routes import plan as plan_mod

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api", lambda e, p: ("stryd-user-id", "fake-token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks", lambda workout, cp: [],
    )
    monkeypatch.setattr(
        "sync.stryd_sync.create_workout_api",
        lambda **kwargs: {"id": f"new-workout-for-{kwargs.get('workout_date')}"},
    )

    plan_df = pd.DataFrame([
        {
            "date": "2026-05-07",
            "workout_type": "easy_run",
            "planned_duration_min": 45,
            "workout_description": "Aerobic easy effort",
            "target_power_min": 200, "target_power_max": 230, "source": "ai",
        },
    ])
    # plan.py imported get_dashboard_data by name, so patch the local binding.
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df, "all_plans": plan_df, "latest_cp": 260.0, "activities": pd.DataFrame(),
            "signal": {}, "training_base": "power",
        },
    )

    api_client["current"]["value"] = "carol"
    res = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": ["2026-05-07"]},
    )
    assert res.status_code == 200, res.text

    assert _delivery_rows("carol") == [{
        "external_id": "new-workout-for-2026-05-07",
        "state": "synced",
        "date": "2026-05-07",
    }]
    assert _delivery_rows("alice") == []
    with open(
        plan_mod._stryd_push_status_path("carol"),
        encoding="utf-8",
    ) as handle:
        compatibility_status = json.load(handle)
    assert compatibility_status["2026-05-07"]["workout_id"] == (
        "new-workout-for-2026-05-07"
    )


def test_push_selects_ai_row_from_all_plan_sources(api_client, monkeypatch):
    """A preferred Stryd analytical row must never be pushed back to Stryd."""
    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api", lambda email, password: ("sid", "token"),
    )
    captured: dict = {}

    def _capture_blocks(workout, cp):
        captured.update(workout)
        return []

    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", _capture_blocks)
    monkeypatch.setattr(
        "sync.stryd_sync.create_workout_api",
        lambda **kwargs: {"id": "new-ai-workout"},
    )

    workout_date = "2026-05-08"
    all_plans = pd.DataFrame([
        {
            "date": "2026-05-09",
            "source": "stryd",
            "workout_type": "tempo_stryd",
            "planned_duration_min": 40,
            "workout_description": "Imported Stryd workout",
        },
        {
            "date": workout_date,
            "source": "ai",
            "workout_type": "threshold",
            "planned_duration_min": 45,
            "workout_description": "AI-authored threshold workout",
        },
    ])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": all_plans.iloc[[0]].copy(),
            "all_plans": all_plans,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = "source-safe-user"
    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert response.status_code == 200, response.text
    assert captured["source"] == "ai"
    assert captured["workout_type"] == "threshold"


def test_push_rereads_current_plan_before_starting_delivery(api_client, monkeypatch):
    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    captured: dict = {}

    def _capture_blocks(workout, cp):
        captured.update(workout)
        return []

    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", _capture_blocks)
    monkeypatch.setattr(
        "sync.stryd_sync.create_workout_api",
        lambda **kwargs: {"id": "fresh-version-id"},
    )
    workout_date = "2026-05-09"
    calls = {"dashboard": 0}

    def _dashboard(user_id, db):
        calls["dashboard"] += 1
        description = (
            "Stale pre-lock version"
            if calls["dashboard"] == 1
            else "Current locked version"
        )
        plan_df = pd.DataFrame([{
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": description,
        }])
        return {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        }

    monkeypatch.setattr("api.routes.plan.get_dashboard_data", _dashboard)
    api_client["current"]["value"] = "locked-plan-user"

    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["status"] == "success"
    assert calls["dashboard"] >= 2
    assert captured["workout_description"] == "Current locked version"


def test_successful_delivery_is_idempotent_for_same_workout_version(
    api_client,
    monkeypatch,
):
    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "stable-stryd-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-04"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Version one",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = "idempotent-user"
    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert first.json()["results"][0]["status"] == "success"
    assert second.json()["results"][0] == {
        "date": workout_date,
        "status": "success",
        "workout_id": "stable-stryd-id",
    }
    assert calls["create"] == 1
    assert len(_delivery_rows("idempotent-user")) == 1
    assert _attempt_rows("idempotent-user") == [{
        "number": 1,
        "operation": "deliver",
        "state": "synced",
    }]


def test_changed_threshold_requires_owned_workout_replacement(
    api_client,
    monkeypatch,
):
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("threshold-account", "token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [{"target_power": cp}],
    )
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "threshold-version-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-04"
    cp = {"value": 260.0}
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Threshold-sensitive payload",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": cp["value"],
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = "threshold-version-user"
    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    cp["value"] = 270.0
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert first.json()["results"][0]["status"] == "success"
    assert "removed before replacement" in (
        second.json()["results"][0]["error"]
    )
    assert calls["create"] == 1
    assert len(_delivery_rows("threshold-version-user")) == 1


def test_synced_delivery_ignores_unowned_same_date_workout(
    api_client,
    monkeypatch,
):
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("exact-id-account", "token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [],
    )
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "owned-external-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-04"
    provider_id = {"value": None}

    def _dashboard(user_id, db):
        rows = [{
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Exact identity",
        }]
        if provider_id["value"] is not None:
            rows.append({
                "date": workout_date,
                "source": "stryd",
                "workout_type": "easy",
                "external_id": provider_id["value"],
            })
        plan_df = pd.DataFrame(rows)
        return {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        }

    monkeypatch.setattr("api.routes.plan.get_dashboard_data", _dashboard)
    api_client["current"]["value"] = "exact-id-user"

    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    provider_id["value"] = "different-external-id"
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert first.json()["results"][0]["status"] == "success"
    assert second.json()["results"][0] == {
        "date": workout_date,
        "status": "success",
        "workout_id": "owned-external-id",
    }
    assert calls["create"] == 1


def test_synced_delivery_preserves_extra_unowned_calendar_id(
    api_client,
    monkeypatch,
):
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("extra-id-account", "token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [],
    )
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "owned-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-04"
    include_calendar = {"value": False}

    def _dashboard(user_id, db):
        rows = [{
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Extra identity",
        }]
        if include_calendar["value"]:
            rows.extend([
                {
                    "date": workout_date,
                    "source": "stryd",
                    "workout_type": "easy",
                    "external_id": "owned-id",
                },
                {
                    "date": workout_date,
                    "source": "stryd",
                    "workout_type": "easy",
                    "external_id": "unowned-id",
                },
            ])
        plan_df = pd.DataFrame(rows)
        return {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        }

    monkeypatch.setattr("api.routes.plan.get_dashboard_data", _dashboard)
    api_client["current"]["value"] = "extra-id-user"

    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    include_calendar["value"] = True
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert first.json()["results"][0]["status"] == "success"
    assert second.json()["results"][0] == {
        "date": workout_date,
        "status": "success",
        "workout_id": "owned-id",
    }
    assert calls["create"] == 1


def test_calendar_id_owned_on_other_date_does_not_block_new_delivery(
    api_client,
    monkeypatch,
):
    user_id = "moved-calendar-id-user"
    moved_id = "moved-owned-id"
    _seed_synced_delivery(
        user_id,
        "2026-08-03",
        moved_id,
        provider_account_id="moved-id-account",
    )
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("moved-id-account", "token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [],
    )
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "duplicate-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-04"
    plan_df = pd.DataFrame([
        {
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Moved provider row",
        },
        {
            "date": workout_date,
            "source": "stryd",
            "workout_type": "easy",
            "external_id": moved_id,
        },
    ])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )
    api_client["current"]["value"] = user_id

    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert response.json()["results"][0] == {
        "date": workout_date,
        "status": "success",
        "workout_id": "duplicate-id",
    }
    assert calls["create"] == 1


def test_identical_push_rejects_reconnected_provider_account(
    api_client,
    monkeypatch,
):
    account_id = {"value": "original-provider-account"}
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: (account_id["value"], "token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.build_workout_blocks",
        lambda workout, cp: [],
    )
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "old-account-workout"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-04"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Account fenced",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )
    api_client["current"]["value"] = "account-fenced-push-user"

    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    account_id["value"] = "different-provider-account"
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert first.json()["results"][0]["status"] == "success"
    assert "different Stryd account" in second.json()["results"][0]["error"]
    assert calls["create"] == 1


def test_failed_retry_reuses_delivery_and_appends_attempt(api_client, monkeypatch):
    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        if calls["create"] == 1:
            import requests

            response = requests.Response()
            response.status_code = 400
            response._content = b'{"message":"invalid workout"}'
            raise requests.HTTPError("invalid workout", response=response)
        return {"id": "retry-stryd-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-05"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Retry me",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = "retry-user"
    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    third = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert first.json()["results"][0]["status"] == "error"
    assert second.json()["results"][0]["status"] == "success"
    assert third.json()["results"][0]["status"] == "success"
    assert calls["create"] == 2
    assert len(_delivery_rows("retry-user")) == 1
    assert _attempt_rows("retry-user") == [
        {"number": 1, "operation": "deliver", "state": "failed"},
        {"number": 2, "operation": "deliver", "state": "synced"},
    ]


def test_ambiguous_failure_requires_reconciliation_before_retry(
    api_client,
    monkeypatch,
):
    import requests

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    calls = {"create": 0}

    def _timeout(**kwargs):
        calls["create"] += 1
        raise requests.Timeout("response timed out")

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _timeout)
    workout_date = "2026-08-06"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Ambiguous result",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = "ambiguous-user"
    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert "uncertain" in first.json()["results"][0]["error"]
    assert "uncertain" in second.json()["results"][0]["error"]
    assert calls["create"] == 1
    assert _delivery_rows("ambiguous-user")[0]["state"] == "conflict"
    assert _attempt_rows("ambiguous-user") == [{
        "number": 1,
        "operation": "deliver",
        "state": "conflict",
    }]


@pytest.mark.parametrize(
    "provider_outcome",
    [
        "gateway_error",
        "missing_id",
        "object_id",
        "reserved_id",
        "oversized_integer_id",
    ],
)
def test_post_send_uncertainty_is_not_retried(
    api_client,
    monkeypatch,
    provider_outcome,
):
    import requests

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        if provider_outcome == "missing_id":
            return {"status": "created"}
        if provider_outcome == "object_id":
            return {"id": {"unexpected": "object"}}
        if provider_outcome == "reserved_id":
            return {"id": "abc?target=other"}
        if provider_outcome == "oversized_integer_id":
            return {"id": 10 ** 200}
        response = requests.Response()
        response.status_code = 503
        response._content = b'{"message":"gateway unavailable"}'
        raise requests.HTTPError("gateway unavailable", response=response)

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    workout_date = "2026-08-08"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Uncertain response",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = f"uncertain-{provider_outcome}"
    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert "uncertain" in first.json()["results"][0]["error"]
    assert "uncertain" in second.json()["results"][0]["error"]
    assert calls["create"] == 1
    assert _delivery_rows(f"uncertain-{provider_outcome}")[0]["state"] == "conflict"


def test_delete_rejects_unsafe_provider_id_before_external_call(api_client):
    api_client["current"]["value"] = "unsafe-delete-user"
    response = api_client["client"].delete(
        "/api/plan/stryd-workout/abc%25target",
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Stryd workout id"


def test_delete_requires_callers_delivery_before_external_call(
    api_client,
    monkeypatch,
):
    calls = {"login": 0, "delete": 0}

    def _login(email, password):
        calls["login"] += 1
        return "sid", "token"

    def _delete(*args):
        calls["delete"] += 1

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr("sync.stryd_sync._login_api", _login)
    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", _delete)
    api_client["current"]["value"] = "no-delivery-user"

    response = api_client["client"].delete(
        "/api/plan/stryd-workout/not-owned",
    )

    assert response.status_code == 404
    assert calls == {"login": 0, "delete": 0}


def test_existing_unowned_stryd_row_does_not_block_praxys_delivery(
    api_client,
    monkeypatch,
):
    workout_date = "2026-08-09"
    all_plans = pd.DataFrame([
        {
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Canonical workout",
        },
        {
            "date": workout_date,
            "source": "stryd",
            "workout_type": "easy",
            "workout_description": "Existing provider workout",
            "external_id": "existing-provider-id",
        },
    ])
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "duplicate-id"}

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": all_plans[all_plans["source"] == "ai"],
            "all_plans": all_plans,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )
    api_client["current"]["value"] = "provider-row-user"

    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert response.json()["results"][0] == {
        "date": workout_date,
        "status": "success",
        "workout_id": "duplicate-id",
    }
    assert calls["create"] == 1
    assert _delivery_rows("provider-row-user") == [{
        "date": workout_date,
        "external_id": "duplicate-id",
        "state": "synced",
    }]


@pytest.mark.parametrize(
    ("selected_id", "expected_ids"),
    [
        (
            None,
            [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ],
        ),
        (
            "22222222-2222-2222-2222-222222222222",
            ["22222222-2222-2222-2222-222222222222"],
        ),
    ],
)
def test_push_delivers_selected_praxys_workouts_on_same_date(
    api_client,
    monkeypatch,
    selected_id,
    expected_ids,
):
    workout_date = "2026-08-09"
    all_plans = pd.DataFrame([
        {
            "canonical_id": "11111111-1111-1111-1111-111111111111",
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Morning",
        },
        {
            "canonical_id": "22222222-2222-2222-2222-222222222222",
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": "Evening",
        },
    ])
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": f"same-day-{calls['create']}"}

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": all_plans,
            "all_plans": all_plans,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )
    api_client["current"]["value"] = "same-day-praxys-user"

    request = {"workout_dates": [workout_date]}
    if selected_id is not None:
        request["canonical_ids"] = [selected_id]
    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json=request,
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert {
        result["canonical_id"] for result in results
    } == set(expected_ids)
    assert calls["create"] == len(expected_ids)
    assert _delivery_rows("same-day-praxys-user") == [
        {
            "date": workout_date,
            "external_id": f"same-day-{index}",
            "state": "synced",
        }
        for index in range(1, len(expected_ids) + 1)
    ]


def test_conflict_blocks_delivery_of_edited_version(api_client, monkeypatch):
    import requests

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    calls = {"create": 0}

    def _timeout(**kwargs):
        calls["create"] += 1
        raise requests.Timeout("response timed out")

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _timeout)
    workout_date = "2026-08-09"
    description = {"value": "Version one"}

    def _dashboard(user_id, db):
        plan_df = pd.DataFrame([{
            "date": workout_date,
            "source": "ai",
            "workout_type": "easy",
            "workout_description": description["value"],
        }])
        return {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        }

    monkeypatch.setattr("api.routes.plan.get_dashboard_data", _dashboard)
    api_client["current"]["value"] = "edited-conflict-user"

    first = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )
    description["value"] = "Version two"
    second = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert "uncertain" in first.json()["results"][0]["error"]
    assert "uncertain" in second.json()["results"][0]["error"]
    assert calls["create"] == 1
    assert _delivery_rows("edited-conflict-user") == [{
        "external_id": None,
        "state": "conflict",
        "date": workout_date,
    }]


def test_synced_prior_version_must_be_removed_before_replacement(
    api_client,
    monkeypatch,
):
    workout_date = "2026-08-10"
    user_id = "edited-synced-user"
    _seed_synced_delivery(
        user_id,
        workout_date,
        "prior-version-id",
        workout_type="easy",
    )
    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "duplicate-id"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Edited content",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )
    api_client["current"]["value"] = user_id

    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert "removed before replacement" in response.json()["results"][0]["error"]
    assert calls["create"] == 0
    assert _delivery_rows(user_id) == [{
        "external_id": "prior-version-id",
        "state": "synced",
        "date": workout_date,
    }]


def test_push_imports_legacy_status_before_external_call(api_client, monkeypatch):
    from api.routes import plan as plan_mod

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    calls = {"create": 0}

    def _create(**kwargs):
        calls["create"] += 1
        return {"id": "should-not-run"}

    monkeypatch.setattr("sync.stryd_sync.create_workout_api", _create)
    monkeypatch.setattr("sync.stryd_sync.build_workout_blocks", lambda workout, cp: [])
    workout_date = "2026-08-07"
    plan_df = pd.DataFrame([{
        "date": workout_date,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Legacy status",
    }])
    monkeypatch.setattr(
        "api.routes.plan.get_dashboard_data",
        lambda user_id, db: {
            "plan": plan_df,
            "all_plans": plan_df,
            "latest_cp": 260.0,
            "activities": pd.DataFrame(),
        },
    )

    api_client["current"]["value"] = "legacy-before-push"
    path = plan_mod._stryd_push_status_path("legacy-before-push")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({
            workout_date: {
                "workout_id": "legacy-existing-id",
                "status": "pushed",
            }
        }, handle)

    response = api_client["client"].post(
        "/api/plan/push-stryd",
        json={"workout_dates": [workout_date]},
    )

    assert "uncertain" in response.json()["results"][0]["error"]
    assert calls["create"] == 0
    assert _delivery_rows("legacy-before-push")[0]["state"] == "synced"


def test_delete_endpoint_touches_only_calling_users_status(api_client, monkeypatch):
    """DELETE /plan/stryd-workout/{id} must not remove entries from another user's status."""
    from api.routes import plan as plan_mod
    from db import session as db_session
    from db.models import TrainingPlan, User

    _seed_synced_delivery(
        "alice",
        "2026-05-01",
        "shared-id",
        provider_account_id="stryd-user-id",
    )
    _seed_synced_delivery(
        "bob",
        "2026-05-01",
        "shared-id",
        provider_account_id="stryd-user-id",
    )
    db = db_session.SessionLocal()
    try:
        for user_id in ("alice", "bob"):
            if db.get(User, user_id) is None:
                db.add(User(
                    id=user_id,
                    email=f"{user_id}@example.test",
                    hashed_password="test",
                ))
            db.add(TrainingPlan(
                user_id=user_id,
                date=datetime(2026, 5, 1).date(),
                source="stryd",
                workout_type="easy",
                external_id="shared-id",
            ))
        db.commit()
    finally:
        db.close()
    for user_id in ("alice", "bob"):
        path = plan_mod._stryd_push_status_path(user_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({
                "2026-05-01": {
                    "workout_id": "shared-id",
                    "status": "pushed",
                }
            }, handle)

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api", lambda e, p: ("stryd-user-id", "fake-token"),
    )
    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", lambda *a, **kw: None)

    api_client["current"]["value"] = "bob"
    res = api_client["client"].delete("/api/plan/stryd-workout/shared-id")
    assert res.status_code == 200

    assert _delivery_rows("bob")[0]["state"] == "removed"
    assert _delivery_rows("alice")[0]["state"] == "synced"
    db = db_session.SessionLocal()
    try:
        assert db.query(TrainingPlan).filter_by(user_id="bob").count() == 0
        assert db.query(TrainingPlan).filter_by(user_id="alice").count() == 1
    finally:
        db.close()
    with open(
        plan_mod._stryd_push_status_path("bob"),
        encoding="utf-8",
    ) as handle:
        assert json.load(handle) == {}
    assert os.path.exists(plan_mod._stryd_push_status_path("alice"))


def test_delete_rejects_reconnected_different_provider_account(
    api_client,
    monkeypatch,
):
    user_id = "provider-account-fence-user"
    external_id = "provider-account-workout"
    _seed_synced_delivery(
        user_id,
        "2026-05-03",
        external_id,
        provider_account_id="original-provider-account",
    )
    calls = {"delete": 0}

    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("different-provider-account", "token"),
    )

    def _delete(*args):
        calls["delete"] += 1

    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", _delete)
    api_client["current"]["value"] = user_id

    response = api_client["client"].delete(
        f"/api/plan/stryd-workout/{external_id}",
    )

    assert response.status_code == 409
    assert "different Stryd account" in response.json()["detail"]
    assert calls["delete"] == 0
    assert _delivery_rows(user_id)[0]["state"] == "synced"
    assert _attempt_rows(user_id) == [{
        "number": 1,
        "operation": "deliver",
        "state": "synced",
    }]


def test_delete_verifies_migrated_delivery_on_current_calendar(
    api_client,
    monkeypatch,
):
    from db import session as db_session
    from db.models import PlanDelivery

    user_id = "migrated-removal-user"
    external_id = "migrated-removal-id"
    workout_date = (date.today() + timedelta(days=2)).isoformat()
    _seed_synced_delivery(user_id, workout_date, external_id)
    calls = {"calendar": 0, "delete": 0}

    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("verified-current-account", "token"),
    )

    def _calendar(
        provider_user_id,
        token,
        *,
        cp_watts,
        days_ahead,
        days_back,
        tz_name,
    ):
        calls["calendar"] += 1
        assert days_ahead >= 14
        assert days_back == 3
        shifted_date = (
            date.fromisoformat(workout_date) - timedelta(days=1)
        ).isoformat()
        return [{"date": shifted_date, "external_id": external_id}]

    def _delete(*args):
        calls["delete"] += 1

    monkeypatch.setattr(
        "sync.stryd_sync.fetch_training_plan_api",
        _calendar,
    )
    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", _delete)
    api_client["current"]["value"] = user_id

    response = api_client["client"].delete(
        f"/api/plan/stryd-workout/{external_id}",
    )

    assert response.status_code == 200, response.text
    assert calls == {"calendar": 1, "delete": 1}
    db = db_session.SessionLocal()
    try:
        delivery = db.query(PlanDelivery).filter_by(user_id=user_id).one()
        assert delivery.state == "removed"
        assert delivery.provider_account_id == "verified-current-account"
    finally:
        db.close()


def test_delete_rejects_unverified_migrated_delivery(
    api_client,
    monkeypatch,
):
    user_id = "unverified-migrated-removal-user"
    external_id = "unverified-migrated-id"
    workout_date = (date.today() + timedelta(days=2)).isoformat()
    _seed_synced_delivery(user_id, workout_date, external_id)
    calls = {"delete": 0}

    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("different-current-account", "token"),
    )
    monkeypatch.setattr(
        "sync.stryd_sync.fetch_training_plan_api",
        lambda *args, **kwargs: [],
    )

    def _delete(*args):
        calls["delete"] += 1

    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", _delete)
    api_client["current"]["value"] = user_id

    response = api_client["client"].delete(
        f"/api/plan/stryd-workout/{external_id}",
    )

    assert response.status_code == 409
    assert "could not be verified" in response.json()["detail"]
    assert calls["delete"] == 0
    assert _delivery_rows(user_id)[0]["state"] == "synced"
    assert _attempt_rows(user_id) == [{
        "number": 1,
        "operation": "deliver",
        "state": "synced",
    }]


def test_stale_removal_attempt_can_be_retried(api_client, monkeypatch):
    from db import session as db_session
    from db.models import PlanDelivery
    from db.plan_ledger import DELIVERY_ATTEMPT_LEASE, begin_delivery_attempt

    user_id = "stale-remove-user"
    _seed_synced_delivery(
        user_id,
        "2026-05-02",
        "stale-remove-id",
        provider_account_id="sid",
    )
    db = db_session.SessionLocal()
    try:
        delivery = db.query(PlanDelivery).filter_by(user_id=user_id).one()
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="remove",
        )
        assert disposition == "started"
        assert attempt is not None
        attempt.started_at = (
            datetime.utcnow() - DELIVERY_ATTEMPT_LEASE - timedelta(seconds=1)
        )
        db.commit()
    finally:
        db.close()

    monkeypatch.setenv("STRYD_EMAIL", "stub@example.com")
    monkeypatch.setenv("STRYD_PASSWORD", "stub")
    monkeypatch.setattr(
        "sync.stryd_sync._login_api",
        lambda email, password: ("sid", "token"),
    )
    monkeypatch.setattr("sync.stryd_sync.delete_workout_api", lambda *args: None)
    api_client["current"]["value"] = user_id

    response = api_client["client"].delete(
        "/api/plan/stryd-workout/stale-remove-id",
    )

    assert response.status_code == 200, response.text
    assert _delivery_rows(user_id)[0]["state"] == "removed"
    assert _attempt_rows(user_id) == [
        {"number": 1, "operation": "deliver", "state": "synced"},
        {"number": 2, "operation": "remove", "state": "failed"},
        {"number": 3, "operation": "remove", "state": "removed"},
    ]
