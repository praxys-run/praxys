"""Integration tests for the /api/settings PUT endpoint validation.

Covers the scheduler-interval validation wired in api/routes/settings.py:
the unit-level normalize is tested in test_sync_scheduler.py; this file
proves the API translates a ValueError into a structured 400 response and
that the settings GET surfaces the allowed-options contract the UI depends on.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import tempfile
import threading

import pytest


@pytest.fixture
def api_client(monkeypatch):
    """Yield a FastAPI TestClient pointing at a fresh, isolated SQLite DB."""
    from fastapi.testclient import TestClient

    # ignore_cleanup_errors lets Windows clean up even if SQLite hasn't
    # released the file lock by the time the temp dir is removed.
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name in {
            "garmin_plan_delivery_eligible",
            "stryd_connection_enabled",
        },
    )
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY", "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o="
    )
    # Reset the module-level engine singletons so init_db rebuilds against tmpdir.
    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.main import app
    from api.auth import (
        get_current_user_id,
        get_data_user_id,
        require_write_access,
    )
    from db.session import get_db
    from api.routes import sync as _sync_routes

    # The sync routes keep an in-memory, process-global status map keyed by
    # user_id (api/routes/sync.py::_sync_status). Every api_client test reuses
    # the same user id, so stale runtime status (e.g. "error" left by a prior
    # sync test) would bleed across tests. Clear it on setup and teardown.
    _sync_routes._sync_status.clear()

    test_user_id = "test-user-settings-api"

    # Persist the authenticated user. The sync routes now assert the user exists
    # and is active (the account-deletion guard in
    # api/routes/sync.py::_ensure_user_active_for_sync), so overriding the auth
    # dependency alone is no longer enough — the row must exist.
    from db.models import User as _User
    _seed = db_session.SessionLocal()
    try:
        _seed.add(_User(
            id=test_user_id,
            email="settings-api@test.local",
            hashed_password="x",
            is_active=True,
        ))
        _seed.commit()
    finally:
        _seed.close()

    def _override_user():
        return test_user_id

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[require_write_access] = _override_user
    app.dependency_overrides[get_data_user_id] = _override_user
    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app)
    try:
        yield client, test_user_id
    finally:
        app.dependency_overrides.clear()
        _sync_routes._sync_status.clear()
        # Dispose engines so SQLite releases the file before tmpdir cleanup
        # (Windows can't unlink a file held by an open connection pool).
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


def test_put_settings_rejects_invalid_sync_interval(api_client):
    """An invalid sync_interval_hours must return 400 with the validator's message."""
    client, _ = api_client
    res = client.put("/api/settings", json={"source_options": {"sync_interval_hours": 3}})
    assert res.status_code == 400, res.text
    detail = res.json().get("detail", "")
    assert "interval" in detail.lower()
    assert "(6, 12, 24)" in detail


def test_put_settings_accepts_allowed_sync_interval(api_client):
    """An allowed sync_interval_hours must persist and round-trip via GET."""
    client, _ = api_client
    res = client.put("/api/settings", json={"source_options": {"sync_interval_hours": 12}})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ok"
    assert body["config"]["source_options"]["sync_interval_hours"] == 12

    got = client.get("/api/settings")
    assert got.status_code == 200, got.text
    got_body = got.json()
    assert got_body["config"]["source_options"]["sync_interval_hours"] == 12


def test_get_settings_exposes_sync_interval_options(api_client):
    """GET /api/settings must expose the option list the Settings UI dropdown consumes."""
    client, _ = api_client
    res = client.get("/api/settings")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sync_interval_options_hours"] == [6, 12, 24]
    assert body["default_sync_interval_hours"] == 6


def test_put_science_reloads_config_after_plan_write_lock(
    api_client,
    monkeypatch,
):
    """A blocked science save must preserve a Goal committed while waiting."""
    client, user_id = api_client
    initial_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
        "race_date": "",
    }
    saved = client.put("/api/settings", json={"goal": initial_goal})
    assert saved.status_code == 200, saved.text

    import api.routes.science as science
    from db import session as db_session
    from db.models import UserConfig
    from db.plan_ledger import lock_plan_writes

    lock_attempted = threading.Event()
    original_lock = science.lock_plan_writes

    def observed_lock(db, locked_user_id: str) -> None:
        lock_attempted.set()
        original_lock(db, locked_user_id)

    monkeypatch.setattr(science, "lock_plan_writes", observed_lock)
    concurrent_goal = {
        **initial_goal,
        "target_time_sec": 1_180,
    }
    locker = db_session.SessionLocal()
    try:
        locker.rollback()
        lock_plan_writes(locker, user_id)
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(
                lambda: client.put(
                    "/api/science",
                    json={"science": {"load": "banister_ultra"}},
                )
            )
            assert lock_attempted.wait(timeout=5)
            row = locker.get(UserConfig, user_id)
            assert row is not None
            row.goal = concurrent_goal
            locker.commit()
            response = pending.result(timeout=10)
    finally:
        locker.close()

    assert response.status_code == 200, response.text
    with db_session.SessionLocal() as db:
        row = db.get(UserConfig, user_id)
        assert row is not None
        assert row.goal == concurrent_goal
        assert row.science["load"] == "banister_ultra"


def _seed_connection(
    user_id: str,
    platform: str,
    *,
    status: str = "connected",
) -> None:
    """Insert a connected platform row for settings validation tests."""
    from db import session as db_session
    from db.models import UserConnection

    db = db_session.SessionLocal()
    try:
        db.add(UserConnection(
            user_id=user_id,
            platform=platform,
            status=status,
            preferences={"plan": platform == "stryd"},
        ))
        db.commit()
    finally:
        db.close()


def test_get_settings_distinguishes_configured_from_live_connections(
    api_client,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd", status="auth_required")

    response = client.get("/api/settings")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["config"]["connections"] == ["stryd"]
    assert body["connection_statuses"] == {
        "stryd": "auth_required",
    }


def test_stryd_surfaces_and_actions_are_hidden_when_gate_is_off(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    selected = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
        },
    })
    assert selected.status_code == 200, selected.text

    from db import session as db_session
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        config = db.get(UserConfig, user_id)
        config.activity_routing = {
            "default": "stryd",
            "running": "stryd",
            "cycling": "garmin",
        }
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: (
            gate_name == "garmin_plan_delivery_eligible"
        ),
    )

    settings = client.get("/api/settings")
    assert settings.status_code == 200, settings.text
    body = settings.json()
    assert "stryd" not in body["config"]["connections"]
    assert body["config"]["plan_management"]["execution_target"] is None
    assert body["config"]["plan_management"]["delivery_enabled"] is False
    assert body["config"]["activity_routing"] == {"cycling": "garmin"}
    assert "stryd" not in body["connection_statuses"]
    assert "stryd" not in body["platform_capabilities"]
    assert all(
        option["platform"] != "stryd"
        for option in body["plan_delivery_options"]
    )
    assert all(
        "stryd" not in providers
        for providers in body["available_providers"].values()
    )

    connections = client.get("/api/settings/connections")
    assert connections.status_code == 200, connections.text
    assert "stryd" not in connections.json()["connections"]

    update = client.put(
        "/api/settings",
        json={"connections": ["stryd"]},
    )
    assert update.status_code == 404, update.text

    connect = client.post(
        "/api/settings/connections/stryd",
        json={"email": "runner@example.test", "password": "secret"},
    )
    assert connect.status_code == 404, connect.text

    sync = client.post("/api/sync/stryd")
    assert sync.status_code == 404, sync.text


def test_legacy_mixed_case_stryd_values_are_sanitized() -> None:
    """Persisted provider casing cannot evade response or mutation filters."""
    from analysis.config import UserConfig
    from api.routes.settings import (
        SettingsUpdate,
        _settings_update_requests_stryd,
        _without_stryd_config,
        _without_stryd_thresholds,
    )

    config = UserConfig()
    config.connections = [" STRYD ", "garmin"]
    config.preferences = {
        "plan": "sTrYd",
        "threshold_sources": {
            "cp_watts": "STRYD",
            "lthr_bpm": "garmin",
        },
    }
    config.plan_management = {
        "mode": "praxys",
        "execution_target": " Stryd ",
        "delivery_enabled": True,
        "adjustment_policy": "suggest_only",
    }
    config.activity_routing = {
        "running": "STRYD",
        "cycling": "garmin",
    }

    payload = _without_stryd_config(config)
    thresholds = _without_stryd_thresholds({
        "cp_watts": {
            "value": 265,
            "source": "STRYD",
            "options": [{"source": " STRYD ", "value": 265}],
        },
        "lthr_bpm": {
            "value": 170,
            "source": "garmin",
            "options": [{"source": "garmin", "value": 170}],
        },
    })

    assert payload["connections"] == ["garmin"]
    assert payload["preferences"] == {
        "threshold_sources": {"lthr_bpm": "garmin"},
    }
    assert payload["plan_management"]["execution_target"] is None
    assert payload["plan_management"]["delivery_enabled"] is False
    assert payload["activity_routing"] == {"cycling": "garmin"}
    assert thresholds == {
        "lthr_bpm": {
            "value": 170,
            "source": "garmin",
            "options": [{"source": "garmin", "value": 170}],
        },
    }
    assert _settings_update_requests_stryd(
        SettingsUpdate(connections=[" STRYD "])
    )


def test_get_settings_exposes_safe_plan_management_defaults(api_client):
    client, _ = api_client
    res = client.get("/api/settings")
    assert res.status_code == 200, res.text
    assert res.json()["config"]["plan_management"] == {
        "mode": "external",
        "execution_target": None,
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }
    assert res.json()["plan_delivery_options"] == []
    assert "experimental_plan_delivery" not in res.json()
    assert res.json()["platform_capabilities"]["garmin"]["plan"] is False


def test_plan_delivery_options_include_connected_activity_platforms(
    api_client,
):
    client, user_id = api_client
    for platform in ("garmin", "stryd", "strava", "coros", "oura"):
        _seed_connection(user_id, platform)

    response = client.get("/api/settings")

    assert response.status_code == 200, response.text
    options = {
        option["platform"]: option
        for option in response.json()["plan_delivery_options"]
    }
    assert options == {
        "garmin": {
            "platform": "garmin",
            "selectable": True,
            "reason": None,
        },
        "stryd": {
            "platform": "stryd",
            "selectable": True,
            "reason": None,
        },
        "strava": {
            "platform": "strava",
            "selectable": False,
            "reason": "delivery_not_supported",
        },
        "coros": {
            "platform": "coros",
            "selectable": False,
            "reason": "delivery_not_supported",
        },
    }
    assert "oura" not in options


def test_selecting_eligible_garmin_binds_account_fence(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")

    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert enabled.status_code == 200, enabled.text
    body = enabled.json()
    assert body["config"]["plan_management"]["execution_target"] == "garmin"
    assert body["platform_capabilities"]["garmin"]["plan"] is True
    assert "experimental_plan_delivery" not in body

    from db import session as db_session
    from db.models import UserConnection

    db = db_session.SessionLocal()
    try:
        connection = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).one()
        assert connection.plan_delivery_consent
    finally:
        db.close()


def test_selecting_eligible_legacy_garmin_backfills_region_and_fence(
    api_client,
):
    client, user_id = api_client
    from db import session as db_session
    from db.crypto import get_vault
    from db.models import UserConfig, UserConnection

    encrypted, wrapped = get_vault().encrypt(json.dumps({
        "email": "runner@example.test",
        "password": "secret",
        "is_cn": False,
    }))
    db = db_session.SessionLocal()
    try:
        db.add(UserConnection(
            user_id=user_id,
            platform="garmin",
            status="connected",
            encrypted_credentials=encrypted,
            wrapped_dek=wrapped,
        ))
        config = db.query(UserConfig).filter(
            UserConfig.user_id == user_id,
        ).one_or_none()
        if config is None:
            config = UserConfig(user_id=user_id)
            db.add(config)
        config.source_options = {}
        db.commit()
    finally:
        db.close()

    status = client.get("/api/settings")
    assert status.status_code == 200, status.text
    assert status.json()["plan_delivery_options"] == [{
        "platform": "garmin",
        "selectable": True,
        "reason": None,
    }]

    selected = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert selected.status_code == 200, selected.text
    body = selected.json()
    assert body["config"]["source_options"]["garmin_region"] == "international"
    db = db_session.SessionLocal()
    try:
        connection = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).one()
        assert connection.plan_delivery_consent
    finally:
        db.close()


def test_garmin_delivery_requires_operator_gate(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    monkeypatch.delenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        raising=False,
    )

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "not available for this account" in blocked.json()["detail"]
    status = client.get("/api/settings")
    assert status.status_code == 200, status.text
    assert status.json()["plan_delivery_options"] == [{
        "platform": "garmin",
        "selectable": False,
        "reason": "account_not_eligible",
    }]
    assert status.json()["platform_capabilities"]["garmin"]["plan"] is False


def test_garmin_delivery_requires_statsig_eligibility(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name == "stryd_connection_enabled",
    )

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "not available for this account" in blocked.json()["detail"]
    status = client.get("/api/settings")
    assert status.json()["plan_delivery_options"] == [{
        "platform": "garmin",
        "selectable": False,
        "reason": "account_not_eligible",
    }]
    assert status.json()["platform_capabilities"]["garmin"]["plan"] is False


def test_forward_target_fence_survives_legacy_worker_settings_save(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })
    assert enabled.status_code == 200, enabled.text

    from db import session as db_session
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        row = db.get(UserConfig, user_id)
        assert row.plan_execution_target == "garmin"
        row.display_name = "Saved by an old worker"
        row.plan_management = {
            "mode": "praxys",
            "execution_target": None,
            "delivery_enabled": True,
            "adjustment_policy": "suggest_only",
        }
        db.commit()
    finally:
        db.close()

    restored = client.get("/api/settings")

    assert restored.status_code == 200, restored.text
    management = restored.json()["config"]["plan_management"]
    assert management["execution_target"] == "garmin"
    assert management["delivery_enabled"] is True


def test_target_switch_requires_old_target_cleanup(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")

    from datetime import date, timedelta
    from uuid import uuid4

    from db import session as db_session
    from db.models import PlanDelivery

    db = db_session.SessionLocal()
    try:
        db.add(PlanDelivery(
            id=str(uuid4()),
            user_id=user_id,
            canonical_key="praxys:old-target",
            workout_date=date.today() + timedelta(days=1),
            workout_version="a" * 64,
            target="stryd",
            state="synced",
            external_id="stryd-owned-1",
        ))
        db.commit()
    finally:
        db.close()

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "Remove future Praxys deliveries from stryd" in (
        blocked.json()["detail"]
    )


def test_paused_target_switch_preserves_managed_mode_and_pause(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    _seed_connection(user_id, "garmin")
    adopted = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
        },
    })
    assert adopted.status_code == 200, adopted.text

    switched = client.put("/api/settings", json={
        "plan_management": {
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert switched.status_code == 200, switched.text
    assert switched.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "garmin",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }
    persisted = client.get("/api/settings")
    assert persisted.status_code == 200, persisted.text
    assert persisted.json()["config"]["plan_management"] == (
        switched.json()["config"]["plan_management"]
    )


def test_paused_target_switch_cannot_resume_in_same_request(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    _seed_connection(user_id, "garmin")
    adopted = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
        },
    })
    assert adopted.status_code == 200, adopted.text

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "separate requests" in blocked.json()["detail"]
    current = client.get("/api/settings")
    assert current.status_code == 200, current.text
    assert current.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "stryd",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }


def test_active_managed_target_switch_requires_pause(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    _seed_connection(user_id, "garmin")
    active = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })
    assert active.status_code == 200, active.text

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "Pause managed delivery" in blocked.json()["detail"]
    current = client.get("/api/settings")
    assert current.status_code == 200, current.text
    assert current.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "stryd",
        "delivery_enabled": True,
        "adjustment_policy": "suggest_only",
    }


def test_paused_switch_to_garmin_enforces_account_eligibility(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    _seed_connection(user_id, "garmin")
    adopted = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
        },
    })
    assert adopted.status_code == 200, adopted.text
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name == "stryd_connection_enabled",
    )

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "not available for this account" in blocked.json()["detail"]
    current = client.get("/api/settings")
    assert current.status_code == 200, current.text
    management = current.json()["config"]["plan_management"]
    assert management["execution_target"] == "stryd"
    assert management["mode"] == "praxys"
    assert management["delivery_enabled"] is False


def test_legacy_plan_preference_cannot_bypass_target_cleanup(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    _seed_connection(user_id, "stryd")
    selected = client.put("/api/settings", json={
        "plan_management": {
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })
    assert selected.status_code == 200, selected.text

    from datetime import date, timedelta
    from uuid import uuid4

    from db import session as db_session
    from db.models import PlanDelivery

    with db_session.SessionLocal() as db:
        db.add(PlanDelivery(
            id=str(uuid4()),
            user_id=user_id,
            canonical_key="praxys:garmin-owned",
            workout_date=date.today() + timedelta(days=1),
            workout_version="a" * 64,
            target="garmin",
            state="synced",
            external_id="garmin-owned-1",
        ))
        db.commit()

    blocked = client.put("/api/settings", json={
        "preferences": {"plan": "stryd"},
    })

    assert blocked.status_code == 409, blocked.text
    assert "Remove future Praxys deliveries from garmin" in (
        blocked.json()["detail"]
    )
    current = client.get("/api/settings")
    assert current.status_code == 200, current.text
    assert (
        current.json()["config"]["plan_management"]["execution_target"]
        == "garmin"
    )


def test_target_switch_imports_legacy_stryd_state_before_validation(
    api_client,
    monkeypatch,
    tmp_path,
):
    import json
    from datetime import date, timedelta

    from api.routes import plan as plan_routes

    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    status_dir = tmp_path / "stryd-status"
    status_dir.mkdir()
    monkeypatch.setattr(
        plan_routes,
        "_STRYD_PUSH_STATUS_DIR",
        str(status_dir),
    )
    workout_date = (date.today() + timedelta(days=1)).isoformat()
    with open(status_dir / f"{user_id}.json", "w", encoding="utf-8") as handle:
        json.dump({
            workout_date: {
                "workout_id": "legacy-stryd-owned",
                "status": "pushed",
            },
        }, handle)

    blocked = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert blocked.status_code == 409, blocked.text
    assert "Remove future Praxys deliveries from stryd" in (
        blocked.json()["detail"]
    )


def test_garmin_delivery_requires_explicit_region_before_selection(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")

    from db import session as db_session
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        row = db.get(UserConfig, user_id)
        if row is None:
            row = UserConfig(user_id=user_id)
            db.add(row)
        row.source_options = {}
        db.commit()
    finally:
        db.close()

    status = client.get("/api/settings")
    assert status.status_code == 200, status.text
    assert status.json()["plan_delivery_options"] == [{
        "platform": "garmin",
        "selectable": False,
        "reason": "account_not_eligible",
    }]

    selected = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
        },
    })

    assert selected.status_code == 409, selected.text
    assert "not available for this account" in selected.json()["detail"]


def test_resuming_garmin_rebinds_the_live_account_fence(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })
    assert enabled.status_code == 200, enabled.text

    from db import session as db_session
    from db.models import UserConfig, UserConnection

    db = db_session.SessionLocal()
    try:
        connection = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).one()
        connection.plan_delivery_consent = None
        row = db.get(UserConfig, user_id)
        row.plan_management = {
            **row.plan_management,
            "delivery_enabled": False,
        }
        db.commit()
    finally:
        db.close()

    resumed = client.put("/api/settings", json={
        "plan_management": {"delivery_enabled": True},
    })

    assert resumed.status_code == 200, resumed.text
    db = db_session.SessionLocal()
    try:
        connection = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).one()
        assert connection.plan_delivery_consent
    finally:
        db.close()


def test_garmin_region_change_revokes_account_fence_and_pauses_delivery(
    api_client,
):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })
    assert enabled.status_code == 200, enabled.text

    changed = client.put("/api/settings", json={
        "source_options": {"garmin_region": "cn"},
    })

    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["plan_delivery_options"] == []
    assert body["connection_statuses"]["garmin"] == "disconnected"
    assert body["config"]["plan_management"]["delivery_enabled"] is False

    from db import session as db_session
    from db.models import UserConnection

    db = db_session.SessionLocal()
    try:
        connection = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).one()
        assert connection.plan_delivery_consent is None
    finally:
        db.close()


def test_garmin_region_change_requires_reconnect_before_reselection(
    api_client,
):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })
    assert enabled.status_code == 200, enabled.text

    changed = client.put("/api/settings", json={
        "source_options": {"garmin_region": "cn"},
        "plan_management": {
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })

    assert changed.status_code == 409, changed.text
    body = client.get("/api/settings").json()
    assert body["config"]["source_options"]["garmin_region"] == "international"
    assert body["config"]["plan_management"]["delivery_enabled"] is True


def test_disconnecting_garmin_clears_account_fence(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "garmin")
    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": True,
        },
    })
    assert enabled.status_code == 200, enabled.text

    disconnected = client.delete("/api/settings/connections/garmin")

    assert disconnected.status_code == 200, disconnected.text
    got = client.get("/api/settings")
    body = got.json()
    assert body["plan_delivery_options"] == []
    assert body["config"]["plan_management"]["delivery_enabled"] is False


def test_settings_roundtrip_explicit_praxys_ownership(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")

    res = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
            "adjustment_policy": "suggest_only",
        },
    })
    assert res.status_code == 200, res.text
    assert res.json()["config"]["plan_management"]["mode"] == "praxys"

    got = client.get("/api/settings")
    assert got.status_code == 200, got.text
    assert got.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "stryd",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }


def test_settings_rejects_unconnected_plan_target(api_client):
    client, _ = api_client
    res = client.put("/api/settings", json={
        "plan_management": {"execution_target": "stryd"},
    })
    assert res.status_code == 400, res.text
    assert "connected platform" in res.json()["detail"]


def test_settings_enables_delivery_and_runs_post_commit_hook(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    preview_start = datetime.now(timezone.utc).date().isoformat()
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda called_user_id, *, trigger, window_start: calls.append(
            (called_user_id, trigger, window_start.isoformat())
        ),
    )

    res = client.put("/api/settings", json={
        "managed_plan_preview_start": preview_start,
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })

    assert res.status_code == 200, res.text
    assert res.json()["config"]["plan_management"]["delivery_enabled"] is True
    assert res.json()["connection_statuses"] == {
        "stryd": "connected",
    }
    assert calls == [
        (user_id, "plan_management_enabled", preview_start),
    ]


def test_settings_accepts_current_athlete_local_preview(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz is not None else value.replace(
                tzinfo=None
            )

    monkeypatch.setattr("api.routes.settings.datetime", FixedDateTime)
    calls: list[str] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start: calls.append(
            window_start.isoformat()
        ),
    )

    response = client.put("/api/settings", json={
        "managed_plan_preview_start": "2026-09-15",
        "source_options": {"athlete_timezone": "Pacific/Kiritimati"},
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })

    assert response.status_code == 200, response.text
    assert calls == ["2026-09-15"]


def test_settings_rejects_expired_preview_before_enabling_delivery(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    calls: list[str] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda *args, **kwargs: calls.append("called"),
    )

    response = client.put("/api/settings", json={
        "managed_plan_preview_start": "2000-01-01",
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })

    assert response.status_code == 409, response.text
    assert "preview expired" in response.json()["detail"]
    assert calls == []
    settings = client.get("/api/settings").json()
    assert settings["config"]["plan_management"]["mode"] == "external"
    assert settings["config"]["plan_management"]["delivery_enabled"] is False


def test_settings_update_returns_post_hook_connection_status(
    api_client,
    monkeypatch,
):
    from db import session as db_session
    from db.models import UserConnection

    client, user_id = api_client
    _seed_connection(user_id, "stryd")

    def degrade_connection(
        called_user_id: str,
        *,
        trigger: str,
    ) -> None:
        assert called_user_id == user_id
        assert trigger == "plan_management_enabled"
        db = db_session.SessionLocal()
        try:
            connection = db.query(UserConnection).filter_by(
                user_id=user_id,
                platform="stryd",
            ).one()
            connection.status = "error"
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        degrade_connection,
    )

    response = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })

    assert response.status_code == 200, response.text
    assert response.json()["connection_statuses"] == {
        "stryd": "error",
    }


def test_leaving_managed_mode_pauses_without_cleanup_hook(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda called_user_id, *, trigger: calls.append(
            (called_user_id, trigger)
        ),
    )
    enabled = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })
    assert enabled.status_code == 200, enabled.text
    calls.clear()

    disabled = client.put("/api/settings", json={
        "plan_management": {"mode": "external"},
    })

    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["config"]["plan_management"] == {
        "mode": "external",
        "execution_target": "stryd",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }
    assert calls == []


def test_disconnecting_target_preserves_managed_plan_intent(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    adopted = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
        },
    })
    assert adopted.status_code == 200, adopted.text

    disconnected = client.delete("/api/settings/connections/stryd")
    assert disconnected.status_code == 200, disconnected.text

    settings = client.get("/api/settings")
    assert settings.status_code == 200, settings.text
    assert settings.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "stryd",
        "delivery_enabled": True,
        "adjustment_policy": "suggest_only",
    }
    assert "stryd" not in settings.json()["config"]["connections"]


def test_adjustment_consent_can_be_revoked_after_target_disconnect(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda *args, **kwargs: {"status": "no_change"},
    )
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda *args, **kwargs: None,
    )
    adopted = client.put("/api/settings", json={
        "source_options": {"athlete_timezone": "UTC"},
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
            "adjustment_policy": "auto_conservative",
        },
    })
    assert adopted.status_code == 200, adopted.text
    disconnected = client.delete("/api/settings/connections/stryd")
    assert disconnected.status_code == 200, disconnected.text

    revoked = client.put("/api/settings", json={
        "plan_management": {"adjustment_policy": "suggest_only"},
    })

    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "stryd",
        "delivery_enabled": True,
        "adjustment_policy": "suggest_only",
    }


def test_legacy_resume_payload_preserves_adjustment_consent(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda *args, **kwargs: {"status": "no_change"},
    )
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda *args, **kwargs: None,
    )
    configured = client.put("/api/settings", json={
        "source_options": {"athlete_timezone": "UTC"},
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
            "adjustment_policy": "auto_conservative",
        },
    })
    assert configured.status_code == 200, configured.text

    resumed = client.put("/api/settings", json={
        "managed_plan_preview_start": (
            datetime.now(timezone.utc).date().isoformat()
        ),
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
            # N-1 clients sent this placeholder during every resume.
            "adjustment_policy": "suggest_only",
        },
    })

    assert resumed.status_code == 200, resumed.text
    assert (
        resumed.json()["config"]["plan_management"]["adjustment_policy"]
        == "auto_conservative"
    )


def test_cleanup_endpoint_rejects_before_leaving_managed_mode(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    adopted = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": False,
        },
    })
    assert adopted.status_code == 200, adopted.text

    cleanup = client.post(
        "/api/plan/deliveries/cleanup",
        json={"scope": "future"},
    )

    assert cleanup.status_code == 409, cleanup.text
    assert "Leave managed mode" in cleanup.json()["detail"]


@pytest.mark.parametrize(
    ("mode", "cleanup_request"),
    [
        ("external", {"scope": "future"}),
        (
            "praxys",
            {
                "scope": "future",
                "intent": "switch_execution_target",
            },
        ),
    ],
)
def test_cleanup_endpoint_removes_future_delivery_when_disabled(
    api_client,
    monkeypatch,
    mode,
    cleanup_request,
):
    from datetime import date, timedelta
    from uuid import uuid4

    from api.plan_delivery.base import ProviderRemoveResult
    from db import session as db_session
    from db.models import PlanDelivery

    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    configured = client.put("/api/settings", json={
        "plan_management": {
            "mode": mode,
            "execution_target": "stryd",
            "delivery_enabled": False,
        },
    })
    assert configured.status_code == 200, configured.text

    canonical_id = str(uuid4())
    db = db_session.SessionLocal()
    try:
        delivery = PlanDelivery(
            user_id=user_id,
            canonical_key=f"ai:{canonical_id}",
            canonical_id=canonical_id,
            workout_date=date.today() + timedelta(days=1),
            workout_version="cleanup-endpoint-version",
            plan_version="cleanup-endpoint-plan-version",
            provider_content_version="cleanup-endpoint-content-version",
            target="stryd",
            state="synced",
            external_id="cleanup-endpoint-workout",
            provider_account_id="cleanup-endpoint-account",
        )
        db.add(delivery)
        db.commit()
        delivery_id = delivery.id
    finally:
        db.close()

    class CleanupAdapter:
        target = "stryd"
        display_name = "Cleanup adapter"

        def __init__(self):
            self.deleted: list[str] = []

        @property
        def account_id(self) -> str:
            return "cleanup-endpoint-account"

        def authenticate(self) -> None:
            return None

        def delete_workout(
            self,
            external_id: str,
            *,
            hooks,
        ) -> ProviderRemoveResult:
            hooks.before_mutation()
            self.deleted.append(external_id)
            return ProviderRemoveResult()

    adapter = CleanupAdapter()
    monkeypatch.setattr(
        "api.plan_cleanup.load_plan_delivery_adapter",
        lambda db, *, user_id, target: adapter,
    )

    cleanup = client.post(
        "/api/plan/deliveries/cleanup",
        json=cleanup_request,
    )

    assert cleanup.status_code == 200, cleanup.text
    assert cleanup.json()["status"] == "complete"
    assert cleanup.json()["removed_count"] == 1
    assert adapter.deleted == ["cleanup-endpoint-workout"]
    db = db_session.SessionLocal()
    try:
        assert db.get(PlanDelivery, delivery_id).state == "removed"
    finally:
        db.close()
    current = client.get("/api/settings")
    assert current.status_code == 200, current.text
    assert current.json()["config"]["plan_management"]["mode"] == mode
    assert (
        current.json()["config"]["plan_management"]["delivery_enabled"]
        is False
    )


@pytest.mark.parametrize(
    "plan_management",
    [
        {"mode": "automatic"},
        {"adjustment_policy": "autonomous"},
        {"unknown_field": True},
    ],
)
def test_settings_strictly_validates_plan_management(
    api_client,
    plan_management,
):
    client, _ = api_client
    res = client.put("/api/settings", json={
        "plan_management": plan_management,
    })
    assert res.status_code == 422, res.text


def test_auto_adjustment_requires_praxys_mode(api_client):
    client, _ = api_client

    res = client.put("/api/settings", json={
        "plan_management": {
            "adjustment_policy": "auto_conservative",
        },
    })

    assert res.status_code == 400, res.text
    assert "requires Praxys mode" in res.json()["detail"]


@pytest.mark.parametrize(
    "source_options",
    [None, {"athlete_timezone": "not/a-timezone"}],
)
def test_auto_adjustment_requires_valid_athlete_timezone(
    api_client,
    source_options,
):
    client, _ = api_client
    payload = {
        "plan_management": {
            "mode": "praxys",
            "adjustment_policy": "auto_conservative",
        },
    }
    if source_options is not None:
        payload["source_options"] = source_options

    res = client.put("/api/settings", json=payload)

    assert res.status_code == 400, res.text
    assert "timezone" in res.json()["detail"].lower()


def test_auto_adjustment_requires_explicit_consent_and_resets_on_exit(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    calls: list[tuple[str, str]] = []

    def capture(called_user_id: str, *, trigger: str) -> dict:
        calls.append((called_user_id, trigger))
        return {"status": "no_change"}

    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        capture,
    )
    enabled = client.put("/api/settings", json={
        "source_options": {"athlete_timezone": "Asia/Shanghai"},
        "plan_management": {
            "mode": "praxys",
            "adjustment_policy": "auto_conservative",
        },
    })
    repeated = client.put("/api/settings", json={
        "plan_management": {
            "adjustment_policy": "auto_conservative",
        },
    })
    disabled = client.put("/api/settings", json={
        "plan_management": {"mode": "external"},
    })

    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["config"]["plan_management"]["adjustment_policy"] == (
        "auto_conservative"
    )
    assert enabled.json()["config"]["source_options"]["athlete_timezone"] == (
        "Asia/Shanghai"
    )
    assert repeated.status_code == 200, repeated.text
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["config"]["plan_management"]["adjustment_policy"] == (
        "suggest_only"
    )
    assert calls == [(user_id, "adjustment_policy_enabled")]


def test_combined_consent_adjusts_before_initial_delivery(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    calls: list[str] = []

    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda user_id, *, trigger: (
            calls.append(f"adjust:{trigger}") or {"status": "adjusted"}
        ),
    )
    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda user_id, *, trigger, window_start=None: (
            calls.append(f"deliver:{trigger}") or None
        ),
    )

    res = client.put("/api/settings", json={
        "managed_plan_preview_start": datetime.now(timezone.utc).date().isoformat(),
        "source_options": {"athlete_timezone": "America/Los_Angeles"},
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
            "delivery_enabled": True,
            "adjustment_policy": "auto_conservative",
        },
    })

    assert res.status_code == 200, res.text
    assert calls == ["adjust:adjustment_policy_enabled"]


def test_legacy_plan_preference_seeds_target_without_adoption(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")

    res = client.put("/api/settings", json={
        "preferences": {"plan": "stryd"},
    })
    assert res.status_code == 200, res.text
    assert res.json()["config"]["plan_management"] == {
        "mode": "external",
        "execution_target": "stryd",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }


def test_legacy_full_preferences_save_does_not_target_disconnected_stryd(
    api_client,
):
    client, _ = api_client
    res = client.put("/api/settings", json={
        "preferences": {
            "activities": "garmin",
            "recovery": "oura",
            "plan": "stryd",
        },
    })
    assert res.status_code == 200, res.text
    assert res.json()["config"]["plan_management"]["execution_target"] is None


@pytest.mark.parametrize("status", ["error", "auth_required"])
def test_legacy_preferences_echo_does_not_block_unrelated_save(
    api_client,
    status,
):
    client, user_id = api_client
    _seed_connection(user_id, "stryd", status=status)
    seeded = client.put("/api/settings", json={
        "preferences": {"plan": "stryd"},
    })
    assert seeded.status_code == 200, seeded.text

    saved = client.put("/api/settings", json={
        "display_name": "Updated while connector is degraded",
        "preferences": {
            "activities": "garmin",
            "recovery": "oura",
            "plan": "stryd",
        },
    })

    assert saved.status_code == 200, saved.text
    assert saved.json()["config"]["display_name"] == (
        "Updated while connector is degraded"
    )
    assert (
        saved.json()["config"]["plan_management"]["execution_target"]
        == "stryd"
    )


def test_legacy_preferences_save_does_not_clobber_managed_target(api_client):
    client, user_id = api_client
    _seed_connection(user_id, "stryd")
    adopted = client.put("/api/settings", json={
        "plan_management": {
            "mode": "praxys",
            "execution_target": "stryd",
        },
    })
    assert adopted.status_code == 200, adopted.text

    saved = client.put("/api/settings", json={
        "preferences": {
            "activities": "garmin",
            "recovery": "oura",
            "plan": "ai",
        },
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["config"]["plan_management"] == {
        "mode": "praxys",
        "execution_target": "stryd",
        "delivery_enabled": False,
        "adjustment_policy": "suggest_only",
    }


# --- Threshold source selection (clean-break: no manual overrides) ---


def _seed_cp_rows(user_id: str):
    """Insert two cp_estimate rows from different sources for the test user."""
    from datetime import date, timedelta

    from db import session as db_session
    from db.models import FitnessData
    db = db_session.SessionLocal()
    try:
        today = date.today()
        db.add(FitnessData(
            user_id=user_id, date=today,
            metric_type="cp_estimate", value=350.0, source="garmin",
        ))
        db.add(FitnessData(
            user_id=user_id, date=today - timedelta(days=3),
            metric_type="cp_estimate", value=265.0, source="stryd",
        ))
        db.commit()
    finally:
        db.close()


def test_settings_roundtrip_threshold_source_preference(api_client):
    """Integration: PUT preferences.threshold_sources survives GET and flows
    through to effective_thresholds.origin. Guards the whole source-selection
    contract the frontend relies on — the Pydantic widening that lets the
    nested dict through, the resolver source preference, the response shape.
    """
    client, user_id = api_client
    _seed_cp_rows(user_id)

    # Baseline: latest-by-date wins → Garmin (newer) → 350.
    res = client.get("/api/settings")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["effective_thresholds"]["cp_watts"]["value"] == 350.0
    assert body["effective_thresholds"]["cp_watts"]["origin"] == "auto (garmin)"
    # options[] must include both sources.
    opts = {o["source"] for o in body["detected_thresholds"]["cp_watts"]["options"]}
    assert opts == {"garmin", "stryd"}

    # Pick Stryd via preferences.threshold_sources.
    put = client.put(
        "/api/settings",
        json={"preferences": {"threshold_sources": {"cp_estimate": "stryd"}}},
    )
    assert put.status_code == 200, put.text

    got = client.get("/api/settings").json()
    assert got["config"]["preferences"]["threshold_sources"]["cp_estimate"] == "stryd"
    # Resolver now picks Stryd's value even though Garmin's row is newer.
    assert got["effective_thresholds"]["cp_watts"]["value"] == 265.0
    assert got["effective_thresholds"]["cp_watts"]["origin"] == "auto (stryd)"


def test_settings_activity_source_defaults_threshold_source(api_client):
    """If no explicit threshold_sources set, the activity-source preference
    drives CP selection."""
    client, user_id = api_client
    _seed_cp_rows(user_id)

    client.put("/api/settings", json={"preferences": {"activities": "stryd"}})
    got = client.get("/api/settings").json()
    assert got["effective_thresholds"]["cp_watts"]["value"] == 265.0
    assert got["effective_thresholds"]["cp_watts"]["origin"] == "auto (stryd)"


def test_put_settings_discards_legacy_thresholds_body(api_client, caplog):
    """Regression lock: sending thresholds.cp_watts must not persist as a
    manual override. The server accepts the payload for API compat and logs
    that it was ignored, but nothing reaches config.thresholds."""
    import logging
    client, user_id = api_client
    _seed_cp_rows(user_id)

    with caplog.at_level(logging.INFO, logger="api.routes.settings"):
        res = client.put(
            "/api/settings",
            json={"thresholds": {"cp_watts": 999, "lthr_bpm": 888}},
        )
    assert res.status_code == 200, res.text

    got = client.get("/api/settings").json()
    # config.thresholds didn't receive the values.
    stored = got["config"].get("thresholds") or {}
    assert "cp_watts" not in stored or not stored.get("cp_watts")
    assert "lthr_bpm" not in stored or not stored.get("lthr_bpm")
    # effective CP should still come from the seed data, not the bogus 999.
    assert got["effective_thresholds"]["cp_watts"]["value"] == 350.0
    # Discard was logged so the next maintainer can spot old clients.
    assert any(
        "discarding legacy thresholds" in rec.getMessage() for rec in caplog.records
    )


def test_detect_thresholds_options_deduped_and_date_sorted(api_client):
    """_detect_thresholds_from_db contract: one entry per source, sorted
    date-desc, with the newest-per-source value chosen when a source has
    multiple rows."""
    from datetime import date, timedelta

    from api.routes.settings import _detect_thresholds_from_db
    from db import session as db_session
    from db.models import FitnessData

    _, user_id = api_client
    db = db_session.SessionLocal()
    today = date.today()
    try:
        # Two Stryd rows (older should lose to newer), plus one Garmin.
        db.add(FitnessData(
            user_id=user_id, date=today - timedelta(days=10),
            metric_type="cp_estimate", value=255.0, source="stryd",
        ))
        db.add(FitnessData(
            user_id=user_id, date=today - timedelta(days=1),
            metric_type="cp_estimate", value=265.0, source="stryd",
        ))
        db.add(FitnessData(
            user_id=user_id, date=today - timedelta(days=4),
            metric_type="cp_estimate", value=350.0, source="garmin",
        ))
        db.commit()
        detected = _detect_thresholds_from_db(user_id, db)
    finally:
        db.close()

    opts = detected["cp_watts"]["options"]
    assert len(opts) == 2, "one entry per source, not per row"
    # Sorted date-desc — Stryd's newer row wins over Garmin.
    assert [o["source"] for o in opts] == ["stryd", "garmin"]
    assert opts[0]["value"] == 265.0  # Stryd's newest, not the older 255.
    assert opts[1]["value"] == 350.0
