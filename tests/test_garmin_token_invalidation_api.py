"""End-to-end invalidation tests: connect / disconnect / delete_user.

Locks down the contract that every credential-change endpoint clears the
per-user Garmin tokenstore. Regressions here would reproduce the cross-user
leak through a different code path than the original fix.
"""
import contextlib
import os
import tempfile

import pytest


@pytest.fixture
def api_client(monkeypatch):
    """Yield a TestClient + helpers that isolate API under a temp DB + DATA_DIR."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY", "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o="
    )

    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.main import app
    from api.auth import get_current_user_id, get_data_user_id, require_write_access
    from db.session import get_db

    test_user_id = "test-user-tokens"
    admin_user_id = "test-admin-tokens"

    def _override_current_user():
        return test_user_id

    def _override_admin_user():
        return admin_user_id

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Seed both users so role-based endpoints can look them up.
    from db.models import User
    with db_session.SessionLocal() as db:
        db.add(User(
            id=test_user_id, email="user@test.local",
            hashed_password="x", is_active=True, is_superuser=False,
        ))
        db.add(User(
            id=admin_user_id, email="admin@test.local",
            hashed_password="x", is_active=True, is_superuser=True,
        ))
        db.commit()

    app.dependency_overrides[get_current_user_id] = _override_current_user
    app.dependency_overrides[get_data_user_id] = _override_current_user
    app.dependency_overrides[require_write_access] = _override_current_user
    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "user_id": test_user_id,
            "admin_id": admin_user_id,
            "override_admin": _override_admin_user,
        }
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


def _seed_token_dir(user_id: str) -> str:
    """Drop a dummy tokenstore on disk and return its path."""
    from api.routes.sync import _garmin_token_dir

    path = _garmin_token_dir(user_id)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "oauth2_token.json"), "w") as f:
        f.write("{}")
    assert os.path.isdir(path)
    return path


def test_connect_garmin_clears_existing_tokens(api_client):
    path = _seed_token_dir(api_client["user_id"])
    res = api_client["client"].post(
        "/api/settings/connections/garmin",
        json={"email": "new@example.com", "password": "newpw"},
    )
    assert res.status_code == 200
    assert not os.path.isdir(path)


def test_reconnecting_garmin_revokes_delivery_consent_and_pauses_plan(
    api_client,
):
    client = api_client["client"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text
    enabled = client.put(
        "/api/settings",
        json={
            "experimental_plan_delivery": {"garmin": True},
            "plan_management": {
                "mode": "praxys",
                "execution_target": "garmin",
                "delivery_enabled": True,
            },
        },
    )
    assert enabled.status_code == 200, enabled.text

    reconnected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "second@example.com", "password": "secondpw"},
    )

    assert reconnected.status_code == 200, reconnected.text
    settings = client.get("/api/settings").json()
    assert settings["experimental_plan_delivery"]["garmin"]["enabled"] is False
    assert settings["platform_capabilities"]["garmin"]["plan"] is False
    assert (
        settings["config"]["plan_management"]["delivery_enabled"]
        is False
    )


def test_reconnect_token_clear_failure_leaves_connection_disconnected(
    api_client,
    monkeypatch,
):
    from db import session as db_session
    from db.models import UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text

    def fail_clear(called_user_id: str) -> None:
        assert called_user_id == user_id
        with db_session.SessionLocal() as db:
            connection = db.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            assert connection.status == "disconnected"
            assert connection.plan_delivery_consent is None
        raise OSError("tokenstore locked")

    monkeypatch.setattr("api.routes.sync.clear_garmin_tokens", fail_clear)

    with pytest.raises(OSError, match="tokenstore locked"):
        client.post(
            "/api/settings/connections/garmin",
            json={"email": "second@example.com", "password": "secondpw"},
        )

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        assert connection.status == "disconnected"


def test_reconnect_holds_token_lease_through_credential_commit(
    api_client,
    monkeypatch,
):
    from api.routes import settings as settings_routes
    from api.routes import sync as sync_routes

    client = api_client["client"]
    user_id = api_client["user_id"]
    client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    lease_depth = 0
    events: list[str] = []
    real_revoke = settings_routes._revoke_garmin_delivery_before_login
    real_upsert = settings_routes._upsert_connection_credentials

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        events.append("lease")
        try:
            yield
        finally:
            lease_depth -= 1

    def guarded_revoke(called_user_id, db):
        assert lease_depth == 1
        events.append("revoke")
        return real_revoke(called_user_id, db)

    def guarded_clear(called_user_id: str):
        assert called_user_id == user_id
        assert lease_depth == 1
        events.append("clear")

    def guarded_upsert(called_user_id, platform, creds, db):
        assert called_user_id == user_id
        assert platform == "garmin"
        assert lease_depth == 1
        events.append("upsert")
        return real_upsert(called_user_id, platform, creds, db)

    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(
        settings_routes,
        "_revoke_garmin_delivery_before_login",
        guarded_revoke,
    )
    monkeypatch.setattr(sync_routes, "clear_garmin_tokens", guarded_clear)
    monkeypatch.setattr(
        settings_routes,
        "_upsert_connection_credentials",
        guarded_upsert,
    )

    response = client.post(
        "/api/settings/connections/garmin",
        json={"email": "second@example.com", "password": "secondpw"},
    )

    assert response.status_code == 200, response.text
    assert events == ["lease", "revoke", "clear", "upsert"]


def test_interactive_login_holds_token_lease_through_revoke_and_start(
    api_client,
    monkeypatch,
):
    from api.routes import settings as settings_routes
    from api.routes import sync as sync_routes

    client = api_client["client"]
    user_id = api_client["user_id"]
    lease_depth = 0
    events: list[str] = []
    real_revoke = settings_routes._revoke_garmin_delivery_before_login

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        events.append("lease")
        try:
            yield
        finally:
            lease_depth -= 1

    def guarded_revoke(called_user_id, db):
        assert lease_depth == 1
        events.append("revoke")
        return real_revoke(called_user_id, db)

    def begin_login(called_user_id, creds):
        assert called_user_id == user_id
        assert creds["email"] == "runner@example.test"
        assert lease_depth == 1
        events.append("begin")
        return "mfa_required", "attempt-id"

    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(
        settings_routes,
        "_revoke_garmin_delivery_before_login",
        guarded_revoke,
    )
    monkeypatch.setattr(sync_routes, "begin_garmin_login", begin_login)

    response = client.post(
        "/api/settings/connections/garmin/login",
        json={"email": "runner@example.test", "password": "secret"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "mfa_required"
    assert events == ["lease", "revoke", "begin"]


def test_stale_garmin_sync_cannot_commit_after_credential_rotation(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_routes
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConfig, UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text
    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        expected_generation = connection_credentials_generation(connection)

    def stale_sync(
        called_user_id,
        creds,
        from_date,
        db,
        **kwargs,
    ):
        del creds, from_date
        assert called_user_id == user_id
        assert kwargs["credential_generation"] == expected_generation
        with db_session.SessionLocal() as other:
            connection = other.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            connection.encrypted_credentials = b"rotated"
            connection.wrapped_dek = b"rotated"
            other.commit()
        config = db.get(UserConfig, user_id)
        config.display_name = "stale sync write"
        return {"activities": 1}

    monkeypatch.setattr(sync_routes, "_sync_garmin", stale_sync)

    sync_routes._run_sync(
        user_id,
        "garmin",
        {"email": "first@example.com", "password": "firstpw"},
        expected_connection_generation=expected_generation,
    )

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        config = db.get(UserConfig, user_id)
        assert connection.status == "connected"
        assert config.display_name != "stale sync write"
    assert sync_routes._get_user_status(user_id)["garmin"]["status"] == "idle"


def test_stale_sync_cannot_publish_legacy_token_mirror(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_routes
    from db import session as db_session
    from db import connection_credentials as credential_fence
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text
    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        expected_generation = connection_credentials_generation(connection)

    def stale_sync(called_user_id, creds, from_date, db, **kwargs):
        del creds, from_date, db
        assert called_user_id == user_id
        assert kwargs["credential_generation"] == expected_generation
        with db_session.SessionLocal() as other:
            connection = other.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            connection.encrypted_credentials = b"rotated"
            connection.wrapped_dek = b"rotated"
            other.commit()
        return {"activities": 1}

    mirror_calls: list[tuple[str, str]] = []
    lease_events: list[str] = []
    lease_depth = 0
    real_require_generation = (
        credential_fence.require_connection_generation
    )

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        lease_events.append("enter")
        try:
            yield
        finally:
            lease_events.append("exit")
            lease_depth -= 1

    def guarded_require_generation(*args, **kwargs):
        assert lease_depth == 1
        return real_require_generation(*args, **kwargs)

    monkeypatch.setattr(sync_routes, "_sync_garmin", stale_sync)
    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(
        credential_fence,
        "require_connection_generation",
        guarded_require_generation,
    )
    monkeypatch.setattr(
        sync_routes,
        "_mirror_generation_tokens_for_legacy_workers",
        lambda called_user_id, generation: mirror_calls.append(
            (called_user_id, generation)
        ),
    )

    sync_routes._run_sync(
        user_id,
        "garmin",
        {"email": "first@example.com", "password": "firstpw"},
        expected_connection_generation=expected_generation,
    )

    assert mirror_calls == []
    assert lease_events == ["enter", "exit"]


def test_manual_sync_commits_before_publishing_legacy_tokens(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_routes
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConfig, UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    client.post(
        "/api/settings/connections/garmin",
        json={"email": "runner@example.test", "password": "secret"},
    )
    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        generation = connection_credentials_generation(connection)

    lease_depth = 0
    published: list[str] = []

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        try:
            yield
        finally:
            lease_depth -= 1

    def stage_sync(called_user_id, creds, from_date, db, **kwargs):
        del creds, from_date
        assert called_user_id == user_id
        assert kwargs["credential_generation"] == generation
        config = db.get(UserConfig, user_id)
        if config is None:
            config = UserConfig(user_id=user_id)
            db.add(config)
        config.display_name = "committed before mirror"
        return {"activities": 0}

    def publish(called_user_id: str, called_generation: str):
        assert lease_depth == 1
        assert called_user_id == user_id
        assert called_generation == generation
        with db_session.SessionLocal() as verification_db:
            assert (
                verification_db.get(UserConfig, user_id).display_name
                == "committed before mirror"
            )
        published.append(called_generation)

    monkeypatch.setattr(sync_routes, "_sync_garmin", stage_sync)
    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(
        sync_routes,
        "_mirror_generation_tokens_for_legacy_workers",
        publish,
    )
    monkeypatch.setattr(
        sync_routes,
        "_run_post_sync_plan_adjustment",
        lambda user_id, *, source: None,
    )
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user",
        lambda user_id, db, counts: {},
    )

    sync_routes._run_sync(
        user_id,
        "garmin",
        {"email": "runner@example.test", "password": "secret"},
        expected_connection_generation=generation,
    )

    assert published == [generation]


def test_scheduled_sync_commits_before_publishing_legacy_tokens(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_routes
    from db import session as db_session
    from db import sync_scheduler
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConfig, UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    client.post(
        "/api/settings/connections/garmin",
        json={"email": "runner@example.test", "password": "secret"},
    )
    lease_depth = 0
    published: list[str] = []

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        try:
            yield
        finally:
            lease_depth -= 1

    def stage_sync(called_user_id, creds, from_date, db, **kwargs):
        del creds, from_date
        assert called_user_id == user_id
        config = db.get(UserConfig, user_id)
        if config is None:
            config = UserConfig(user_id=user_id)
            db.add(config)
        config.display_name = "scheduled commit before mirror"
        return {"activities": 0}

    def publish(called_user_id: str, called_generation: str):
        assert lease_depth == 1
        with db_session.SessionLocal() as verification_db:
            connection = verification_db.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            assert (
                connection_credentials_generation(connection)
                == called_generation
            )
            assert (
                verification_db.get(UserConfig, user_id).display_name
                == "scheduled commit before mirror"
            )
        published.append(called_generation)

    monkeypatch.setattr(sync_routes, "_sync_garmin", stage_sync)
    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(
        sync_routes,
        "_mirror_generation_tokens_for_legacy_workers",
        publish,
    )
    monkeypatch.setattr(
        "api.plan_adjustments.run_plan_adjustment_for_user",
        lambda user_id, *, trigger: {"status": "no_change"},
    )
    monkeypatch.setattr(
        "api.insights_runner.run_insights_for_user",
        lambda user_id, db, counts: {},
    )

    with db_session.SessionLocal() as db:
        sync_scheduler._sync_connection(user_id, "garmin", db)

    assert len(published) == 1


def test_delivery_token_publication_rechecks_credential_generation(
    api_client,
):
    from api.routes import sync as sync_routes
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConnection
    from db.sync_scheduler import SCHEDULABLE_STATUSES

    client = api_client["client"]
    user_id = api_client["user_id"]
    client.post(
        "/api/settings/connections/garmin",
        json={"email": "runner@example.test", "password": "secret"},
    )

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        generation = connection_credentials_generation(connection)
        generation_dir = sync_routes._garmin_token_dir(user_id, generation)
        os.makedirs(generation_dir, exist_ok=True)
        with open(
            os.path.join(generation_dir, "oauth2_token.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write("current")

        assert sync_routes.publish_garmin_generation_tokens(
            db,
            user_id=user_id,
            credential_generation=generation,
            allowed_statuses=SCHEDULABLE_STATUSES,
        )

        legacy_token = os.path.join(
            sync_routes._garmin_token_dir(user_id),
            "oauth2_token.json",
        )
        with open(legacy_token, encoding="utf-8") as handle:
            assert handle.read() == "current"

        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        connection.encrypted_credentials = b"rotated"
        connection.wrapped_dek = b"rotated"
        db.commit()
        with open(
            os.path.join(generation_dir, "oauth2_token.json"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write("stale")

        assert not sync_routes.publish_garmin_generation_tokens(
            db,
            user_id=user_id,
            credential_generation=generation,
            allowed_statuses=SCHEDULABLE_STATUSES,
        )
        with open(legacy_token, encoding="utf-8") as handle:
            assert handle.read() == "current"


def test_stale_manual_failure_cannot_degrade_rotated_connection(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_routes
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text
    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        expected_generation = connection_credentials_generation(connection)

    def stale_failure(
        called_user_id,
        creds,
        from_date,
        db,
        **kwargs,
    ):
        del creds, from_date, db
        assert called_user_id == user_id
        assert kwargs["credential_generation"] == expected_generation
        with db_session.SessionLocal() as other:
            connection = other.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            connection.encrypted_credentials = b"rotated"
            connection.wrapped_dek = b"rotated"
            connection.status = "connected"
            other.commit()
        raise RuntimeError("stale provider failure")

    monkeypatch.setattr(sync_routes, "_sync_garmin", stale_failure)

    sync_routes._run_sync(
        user_id,
        "garmin",
        {"email": "first@example.com", "password": "firstpw"},
        expected_connection_generation=expected_generation,
    )

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        assert connection.status == "connected"
        assert connection.consecutive_failures == 0
    assert sync_routes._get_user_status(user_id)["garmin"]["status"] == "idle"


def test_stale_scheduled_failure_cannot_degrade_rotated_connection(
    api_client,
    monkeypatch,
):
    from db import session as db_session
    from db import sync_scheduler
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text
    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        expected_generation = connection_credentials_generation(connection)

    captured_generations: list[str | None] = []

    def stale_failure(
        called_user_id,
        platform,
        db,
        *,
        expected_connection_generation=None,
    ):
        del db
        assert called_user_id == user_id
        assert platform == "garmin"
        captured_generations.append(expected_connection_generation)
        with db_session.SessionLocal() as other:
            connection = other.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            connection.encrypted_credentials = b"rotated"
            connection.wrapped_dek = b"rotated"
            connection.status = "connected"
            other.commit()
        raise RuntimeError("stale scheduled provider failure")

    monkeypatch.setattr(sync_scheduler, "_sync_connection", stale_failure)
    sync_scheduler._check_and_sync()

    assert captured_generations == [expected_generation]
    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        assert connection.status == "connected"
        assert connection.consecutive_failures == 0


def test_stale_scheduled_failure_cannot_reopen_disconnected_connection(
    api_client,
    monkeypatch,
):
    from db import session as db_session
    from db import sync_scheduler
    from db.models import UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "first@example.com", "password": "firstpw"},
    )
    assert connected.status_code == 200, connected.text

    def stale_failure(
        called_user_id,
        platform,
        db,
        *,
        expected_connection_generation=None,
    ):
        del db, expected_connection_generation
        assert called_user_id == user_id
        assert platform == "garmin"
        with db_session.SessionLocal() as other:
            connection = other.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            connection.status = "disconnected"
            other.commit()
        raise RuntimeError("stale scheduled provider failure")

    monkeypatch.setattr(sync_scheduler, "_sync_connection", stale_failure)
    sync_scheduler._check_and_sync()

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        assert connection.status == "disconnected"
        assert connection.consecutive_failures == 0
        assert connection.next_retry_at is None


def test_delivery_adapter_binds_current_credential_generation(api_client):
    from api.plan_delivery import load_plan_delivery_adapter
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.models import UserConnection

    client = api_client["client"]
    user_id = api_client["user_id"]
    connected = client.post(
        "/api/settings/connections/garmin",
        json={"email": "runner@example.com", "password": "secret"},
    )
    assert connected.status_code == 200, connected.text

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one()
        expected_generation = connection_credentials_generation(connection)
        adapter = load_plan_delivery_adapter(
            db,
            user_id=user_id,
            target="garmin",
        )

    assert adapter._credential_generation == expected_generation


def test_sync_trigger_handles_unreadable_credentials(api_client):
    from db import session as db_session
    from db.models import UserConnection

    user_id = api_client["user_id"]
    with db_session.SessionLocal() as db:
        db.add(UserConnection(
            user_id=user_id,
            platform="garmin",
            status="connected",
            encrypted_credentials=b"unreadable",
            wrapped_dek=b"unreadable",
        ))
        db.commit()

    single = api_client["client"].post(
        "/api/sync/garmin",
        json={},
    )
    assert single.status_code == 200
    assert single.json()["status"] == "error"
    assert "No active credentials" in single.json()["message"]

    all_sources = api_client["client"].post("/api/sync", json={})
    assert all_sources.status_code == 200
    assert all_sources.json()["sources"] == []


def test_connect_non_garmin_does_not_touch_garmin_tokens(api_client):
    """Guards against a future invert-the-if regression."""
    path = _seed_token_dir(api_client["user_id"])
    res = api_client["client"].post(
        "/api/settings/connections/oura",
        json={"token": "sk-fake"},
    )
    assert res.status_code == 200
    assert os.path.isdir(path), "Oura connect must not wipe the Garmin tokenstore"


def test_disconnect_garmin_clears_tokens(api_client):
    """Connect first (so there's a DB row to delete), then disconnect."""
    api_client["client"].post(
        "/api/settings/connections/garmin",
        json={"email": "a@example.com", "password": "pw"},
    )
    path = _seed_token_dir(api_client["user_id"])
    res = api_client["client"].delete("/api/settings/connections/garmin")
    assert res.status_code == 200
    assert not os.path.isdir(path)


def test_disconnect_holds_token_lease_before_database_locks(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_routes
    from db import plan_ledger

    client = api_client["client"]
    user_id = api_client["user_id"]
    client.post(
        "/api/settings/connections/garmin",
        json={"email": "a@example.com", "password": "pw"},
    )
    lease_depth = 0
    events: list[str] = []
    real_lock_plan_writes = plan_ledger.lock_plan_writes

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        events.append("lease")
        try:
            yield
        finally:
            lease_depth -= 1

    def guarded_plan_lock(db, called_user_id: str):
        assert lease_depth == 1
        events.append("database")
        return real_lock_plan_writes(db, called_user_id)

    def guarded_clear(called_user_id: str):
        assert called_user_id == user_id
        assert lease_depth == 1
        events.append("clear")

    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(plan_ledger, "lock_plan_writes", guarded_plan_lock)
    monkeypatch.setattr(sync_routes, "clear_garmin_tokens", guarded_clear)

    response = client.delete("/api/settings/connections/garmin")

    assert response.status_code == 200, response.text
    assert events == ["lease", "database", "clear"]


def test_region_change_holds_token_lease_through_commit_and_clear(
    api_client,
    monkeypatch,
):
    from api.routes import settings as settings_routes
    from api.routes import sync as sync_routes

    client = api_client["client"]
    user_id = api_client["user_id"]
    client.post(
        "/api/settings/connections/garmin",
        json={"email": "a@example.com", "password": "pw"},
    )
    lease_depth = 0
    events: list[str] = []
    real_save = settings_routes.save_config_to_db

    @contextlib.contextmanager
    def token_lease(called_user_id: str):
        nonlocal lease_depth
        assert called_user_id == user_id
        lease_depth += 1
        events.append("lease")
        try:
            yield
        finally:
            lease_depth -= 1

    def guarded_save(called_user_id, config, db):
        assert called_user_id == user_id
        assert lease_depth == 1
        real_save(called_user_id, config, db)
        events.append("commit")

    def guarded_clear(called_user_id: str):
        assert called_user_id == user_id
        assert lease_depth == 1
        events.append("clear")

    monkeypatch.setattr(
        sync_routes,
        "_garmin_tokenstore_lease",
        token_lease,
    )
    monkeypatch.setattr(settings_routes, "save_config_to_db", guarded_save)
    monkeypatch.setattr(sync_routes, "clear_garmin_tokens", guarded_clear)

    response = client.put(
        "/api/settings",
        json={"source_options": {"garmin_region": "cn"}},
    )

    assert response.status_code == 200, response.text
    assert events == ["lease", "commit", "clear"]


def test_admin_delete_user_clears_tokens(api_client):
    """Admin deletion is a privacy boundary — cached OAuth tokens must go too."""
    from api.auth import get_current_user_id

    path = _seed_token_dir(api_client["user_id"])
    # Swap in the admin override so the admin route passes _require_admin.
    api_client["client"].app.dependency_overrides[get_current_user_id] = (
        api_client["override_admin"]
    )
    res = api_client["client"].delete(f"/api/admin/users/{api_client['user_id']}")
    assert res.status_code == 200
    assert not os.path.isdir(path)


def test_admin_delete_user_survives_token_cleanup_failure(api_client, monkeypatch):
    """User deletion must succeed even if filesystem cleanup errors — the user
    is already gone from the DB and the endpoint shouldn't 500 the admin."""
    from api.auth import get_current_user_id

    _seed_token_dir(api_client["user_id"])

    def _boom(user_id):
        raise OSError("simulated")

    monkeypatch.setattr("api.routes.sync.clear_garmin_tokens", _boom)

    api_client["client"].app.dependency_overrides[get_current_user_id] = (
        api_client["override_admin"]
    )
    res = api_client["client"].delete(f"/api/admin/users/{api_client['user_id']}")
    assert res.status_code == 200
