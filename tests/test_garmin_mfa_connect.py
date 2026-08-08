"""Interactive Garmin connect flow with MFA support.

Garmin Connect accounts with multi-factor auth enabled can't be connected
through the lazy background-sync login (garminconnect raises
``GarminConnectAuthenticationError("MFA Required but no prompt_mfa mechanism
supplied")`` because there's no place to prompt for a code in a background
thread). These tests lock down the synchronous connect endpoints that drive
garminconnect's ``return_on_mfa`` / ``resume_login`` handshake so an MFA code
can be entered while the user is present.
"""
import json
import os
import tempfile

import pytest


class _FakeInnerClient:
    """Stand-in for garminconnect's underlying Client serialization."""

    def __init__(self) -> None:
        self.dumps_calls = 0
        self.skip_strategies: set[str] = set()

    def dumps(self) -> str:
        self.dumps_calls += 1
        return json.dumps({
            "di_token": "access-" + ("a" * 600),
            "di_refresh_token": "refresh-" + ("b" * 600),
            "di_client_id": "client-id",
        })


def _make_fake_garmin(*, needs_mfa: bool, auth_error: str | None = None):
    """Build a fake ``garminconnect.Garmin`` class + a record of instances."""

    instances: list = []

    class _FakeGarmin:
        def __init__(self, email, password, is_cn=False, return_on_mfa=False, **kw):
            self.email = email
            self.password = password
            self.is_cn = is_cn
            self.return_on_mfa = return_on_mfa
            self.client = _FakeInnerClient()
            self.resume_calls: list[str] = []
            instances.append(self)

        def login(self, tokenstore=None):
            if auth_error is not None:
                from garminconnect import GarminConnectAuthenticationError
                raise GarminConnectAuthenticationError(auth_error)
            if needs_mfa:
                return "needs_mfa", None
            return None, None

        def resume_login(self, client_state, code):
            self.resume_calls.append(code)
            if code != "123456":
                from garminconnect import GarminConnectAuthenticationError
                raise GarminConnectAuthenticationError("Invalid MFA code")
            return None, None

    return _FakeGarmin, instances


@pytest.fixture
def api_client(monkeypatch):
    """TestClient isolated under a temp DB + DATA_DIR, with a seeded user."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", os.path.join(tmpdir.name, "data"))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name
        == "garmin_plan_delivery_eligible",
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

    test_user_id = "test-user-mfa"

    def _override_current_user():
        return test_user_id

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    from db.models import User
    with db_session.SessionLocal() as db:
        db.add(User(
            id=test_user_id, email="user@test.local",
            hashed_password="x", is_active=True, is_superuser=False,
        ))
        db.commit()

    app.dependency_overrides[get_current_user_id] = _override_current_user
    app.dependency_overrides[get_data_user_id] = _override_current_user
    app.dependency_overrides[require_write_access] = _override_current_user
    app.dependency_overrides[get_db] = _override_db

    # Reset the process-local pending-MFA store between tests.
    from api.routes import sync as sync_mod
    sync_mod._pending_garmin_mfa.clear()
    sync_mod._completed_garmin_tokens.clear()
    sync_mod._completed_garmin_token_created.clear()

    client = TestClient(app)
    try:
        yield {"client": client, "user_id": test_user_id}
    finally:
        app.dependency_overrides.clear()
        sync_mod._pending_garmin_mfa.clear()
        sync_mod._completed_garmin_tokens.clear()
        sync_mod._completed_garmin_token_created.clear()
        if db_session.engine is not None:
            db_session.engine.dispose()
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _connection_status(user_id: str) -> str | None:
    from db import session as db_session
    from db.models import UserConnection
    with db_session.SessionLocal() as db:
        conn = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == "garmin",
        ).first()
        return conn.status if conn else None


def test_connect_without_mfa_persists_credentials(api_client, monkeypatch):
    fake, instances = _make_fake_garmin(needs_mfa=False)
    monkeypatch.setattr("garminconnect.Garmin", fake)

    res = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "a@example.com", "password": "pw"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "connected"
    # Credentials and an encrypted token bundle are stored together.
    assert _connection_status(api_client["user_id"]) == "connected"
    assert instances[0].client.dumps_calls == 1
    # The portal login strategy is forced so the minted token is one the
    # Garmin API tier accepts (avoids the widget-token rejection, #369).
    assert instances[0].client.skip_strategies == {
        "mobile+cffi", "mobile+requests", "widget+cffi",
    }
    from db import session as db_session
    from db.garmin_tokens import load_garmin_tokens
    from db.models import UserConnection

    with db_session.SessionLocal() as db:
        connection = db.query(UserConnection).filter_by(
            user_id=api_client["user_id"],
            platform="garmin",
        ).one()
        assert connection.encrypted_garmin_tokens is not None
        assert connection.wrapped_token_dek is not None
        assert load_garmin_tokens(
            db,
            user_id=api_client["user_id"],
        ) == instances[0].client.dumps()


def test_connect_requiring_mfa_then_verify(api_client, monkeypatch):
    fake, instances = _make_fake_garmin(needs_mfa=True)
    monkeypatch.setattr("garminconnect.Garmin", fake)

    res = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "a@example.com", "password": "pw", "is_cn": True},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "mfa_required"
    login_attempt_id = res.json()["login_attempt_id"]
    # Nothing persisted until the code is verified.
    assert _connection_status(api_client["user_id"]) is None

    res = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={
            "code": "123456",
            "login_attempt_id": login_attempt_id,
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "connected"
    assert _connection_status(api_client["user_id"]) == "connected"
    assert instances[0].resume_calls == ["123456"]
    assert instances[0].client.dumps_calls == 1
    assert instances[0].client.skip_strategies == {
        "mobile+cffi", "mobile+requests", "widget+cffi",
    }


def test_completed_logins_bind_only_the_matching_attempt(api_client):
    from api.routes import sync as sync_mod
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.crypto import get_vault
    from db.garmin_tokens import load_garmin_tokens
    from db.models import UserConnection

    user_id = api_client["user_id"]
    first_tokens = _FakeInnerClient().dumps()
    second_tokens = first_tokens[:-4] + "AAAA"
    sync_mod._completed_garmin_tokens.update({
        (user_id, "attempt-first"): first_tokens,
        (user_id, "attempt-second"): second_tokens,
    })
    encrypted, wrapped = get_vault().encrypt(json.dumps({
        "email": "a@example.com",
        "password": "pw",
        "is_cn": False,
    }))
    with db_session.SessionLocal() as db:
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            encrypted_credentials=encrypted,
            wrapped_dek=wrapped,
            status="connected",
        )
        db.add(connection)
        db.flush()
        generation = connection_credentials_generation(connection)
        sync_mod.bind_garmin_login_tokens(
            db,
            user_id,
            generation,
            "attempt-first",
        )
        db.commit()
        assert load_garmin_tokens(db, user_id=user_id) == first_tokens
    assert (
        user_id,
        "attempt-second",
    ) in sync_mod._completed_garmin_tokens


def test_failed_token_binding_drops_sensitive_memory(api_client):
    from api.routes import sync as sync_mod
    from db import session as db_session
    from db.connection_credentials import connection_credentials_generation
    from db.crypto import get_vault
    from db.garmin_tokens import GarminTokenAccessError
    from db.models import UserConnection

    user_id = api_client["user_id"]
    key = (user_id, "attempt-failed")
    sync_mod._completed_garmin_tokens[key] = "sensitive-token"
    sync_mod._completed_garmin_token_created[key] = 1.0
    encrypted, wrapped = get_vault().encrypt("{}")
    with db_session.SessionLocal() as db:
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            encrypted_credentials=encrypted,
            wrapped_dek=wrapped,
            status="connected",
        )
        db.add(connection)
        db.flush()
        generation = connection_credentials_generation(connection)
        with pytest.raises(GarminTokenAccessError):
            sync_mod.bind_garmin_login_tokens(
                db,
                user_id,
                generation,
                "attempt-failed",
            )

    assert key not in sync_mod._completed_garmin_tokens
    assert key not in sync_mod._completed_garmin_token_created


def test_failed_credential_commit_does_not_publish_encrypted_tokens(
    api_client,
    monkeypatch,
):
    from api.routes import sync as sync_mod
    from api.routes.settings import _persist_connected_garmin_login
    from db import session as db_session

    user_id = api_client["user_id"]
    attempt_id = "commit-failure"
    key = (user_id, attempt_id)
    sync_mod._completed_garmin_tokens[key] = _FakeInnerClient().dumps()
    sync_mod._completed_garmin_token_created[key] = 1.0

    with db_session.SessionLocal() as db:
        monkeypatch.setattr(
            db,
            "commit",
            lambda: (_ for _ in ()).throw(
                RuntimeError("commit failed")
            ),
        )
        with pytest.raises(RuntimeError, match="commit failed"):
            _persist_connected_garmin_login(
                db,
                user_id=user_id,
                creds={
                    "email": "new@example.test",
                    "password": "new-password",
                    "is_cn": False,
                },
                login_attempt_id=attempt_id,
            )

    with db_session.SessionLocal() as db:
        from db.models import UserConnection

        assert db.query(UserConnection).filter_by(
            user_id=user_id,
            platform="garmin",
        ).one_or_none() is None
    assert key not in sync_mod._completed_garmin_tokens


def test_concurrent_mfa_logins_require_the_matching_attempt(
    api_client,
    monkeypatch,
):
    fake, instances = _make_fake_garmin(needs_mfa=True)
    monkeypatch.setattr("garminconnect.Garmin", fake)

    first = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "first@example.com", "password": "first"},
    ).json()
    second = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "second@example.com", "password": "second"},
    ).json()

    assert first["login_attempt_id"] != second["login_attempt_id"]
    ambiguous = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={"code": "123456"},
    )
    assert ambiguous.json()["message"] == "mfa_session_expired"
    assert instances[0].resume_calls == []
    assert instances[1].resume_calls == []

    completed = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={
            "code": "123456",
            "login_attempt_id": first["login_attempt_id"],
        },
    )
    assert completed.json()["status"] == "connected"
    assert instances[0].resume_calls == ["123456"]
    assert instances[1].resume_calls == []


def test_reconnect_revokes_old_consent_before_token_login(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.capabilities import plan_delivery_consent_token
    from db import session as db_session
    from db.models import UserConfig, UserConnection

    user_id = api_client["user_id"]
    with db_session.SessionLocal() as db:
        db.add(UserConfig(
            user_id=user_id,
            source_options={"garmin_region": "international"},
            plan_management={
                "mode": "praxys",
                "execution_target": "garmin",
                "delivery_enabled": True,
                "adjustment_policy": "suggest_only",
            },
        ))
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            status="connected",
            encrypted_credentials=b"old-credentials",
            wrapped_dek=b"old-dek",
        )
        db.add(connection)
        db.flush()
        connection.plan_delivery_consent = plan_delivery_consent_token(
            connection,
            region="international",
        )
        db.commit()

    def begin_login(called_user_id, creds):
        assert called_user_id == user_id
        assert creds["email"] == "new@example.com"
        with db_session.SessionLocal() as db:
            connection = db.query(UserConnection).filter_by(
                user_id=user_id,
                platform="garmin",
            ).one()
            config = db.get(UserConfig, user_id)
            assert connection.plan_delivery_consent is None
            assert connection.status == "disconnected"
            assert config.plan_management["delivery_enabled"] is False
        return "mfa_required", "login-attempt"

    monkeypatch.setattr(
        "api.routes.sync.begin_garmin_login",
        begin_login,
    )

    response = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "new@example.com", "password": "new-password"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "mfa_required"


def test_verify_with_wrong_code_keeps_session_for_retry(api_client, monkeypatch):
    fake, instances = _make_fake_garmin(needs_mfa=True)
    monkeypatch.setattr("garminconnect.Garmin", fake)

    api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "a@example.com", "password": "pw"},
    )
    bad = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={"code": "000000"},
    )
    assert bad.status_code == 200
    assert bad.json()["status"] == "error"

    # The pending session survives a wrong code so the user can retry.
    good = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={"code": "123456"},
    )
    assert good.json()["status"] == "connected"


def test_verify_without_pending_session_reports_expired(api_client):
    res = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={"code": "123456"},
    )
    assert res.status_code == 200
    assert res.json() == {"status": "error", "message": "mfa_session_expired"}


def test_connect_with_bad_credentials_returns_error(api_client, monkeypatch):
    fake, _ = _make_fake_garmin(needs_mfa=False, auth_error="Invalid Username or Password")
    monkeypatch.setattr("garminconnect.Garmin", fake)
    from api.routes import sync as sync_mod

    existing_pending = set(sync_mod._pending_garmin_mfa)
    existing_completed = set(sync_mod._completed_garmin_tokens)

    res = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "a@example.com", "password": "wrong"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "error"
    assert _connection_status(api_client["user_id"]) is None
    assert set(sync_mod._pending_garmin_mfa) == existing_pending
    assert set(sync_mod._completed_garmin_tokens) == existing_completed


def test_login_missing_credentials_returns_error(api_client):
    res = api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "a@example.com"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "error"


def test_expired_pending_mfa_is_pruned(api_client, monkeypatch):
    fake, _ = _make_fake_garmin(needs_mfa=True)
    monkeypatch.setattr("garminconnect.Garmin", fake)

    api_client["client"].post(
        "/api/settings/connections/garmin/login",
        json={"email": "a@example.com", "password": "pw"},
    )

    from api.routes import sync as sync_mod
    # Age the pending entry past the TTL.
    pending_key = next(
        key
        for key in sync_mod._pending_garmin_mfa
        if key[0] == api_client["user_id"]
    )
    sync_mod._pending_garmin_mfa[pending_key]["created"] -= (
        sync_mod._GARMIN_MFA_TTL_SEC + 1
    )

    res = api_client["client"].post(
        "/api/settings/connections/garmin/mfa",
        json={"code": "123456"},
    )
    assert res.json()["message"] == "mfa_session_expired"
    assert pending_key not in sync_mod._pending_garmin_mfa


def test_sync_login_forces_portal_and_rewraps_headless_mfa(tmp_path):
    """Background sync forces the portal strategy and, when a re-auth hits MFA
    with no user present, surfaces a clean auth_required message instead of the
    raw garminconnect string."""
    from api.routes.sync import _login_garmin_with_cn_fallback
    from db.sync_scheduler import classify_sync_failure
    from garminconnect import GarminConnectAuthenticationError

    class _Inner:
        def __init__(self) -> None:
            self.skip_strategies: set[str] = set()

    class _Client:
        def __init__(self) -> None:
            self.client = _Inner()

        def login(self, token_dir):
            raise GarminConnectAuthenticationError(
                "MFA Required but no prompt_mfa mechanism supplied"
            )

    c = _Client()
    with pytest.raises(GarminConnectAuthenticationError) as ei:
        _login_garmin_with_cn_fallback(
            c, {"email": "a@example.com", "password": "pw"}, str(tmp_path)
        )

    # Portal strategy forced (widget/mobile skipped) so a re-auth can't re-mint
    # a token the API tier rejects (#369).
    assert c.client.skip_strategies == {
        "mobile+cffi", "mobile+requests", "widget+cffi",
    }
    # The raw library string is replaced with an actionable reconnect message
    # that still classifies as a terminal auth_required.
    msg = str(ei.value)
    assert "prompt_mfa" not in msg
    assert "reconnect" in msg.lower()
    assert classify_sync_failure(ei.value) == ("auth_required", True)
