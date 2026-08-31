"""Tests for the WeChat Mini Program auth endpoints.

Mocks the Tencent jscode2session call so tests run offline and don't
require real WeChat credentials. Covers the tri-state login, the
link-with-password path, and the invitation-aware register path.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from api.china_client_boundary import (
    CN_PRIVACY_CONTRACT_VERSION,
)
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION


class WeChatTestClient(TestClient):
    """Supply the exact legal bundle for cooperative current-client calls."""

    def post(self, url, *args, **kwargs):
        body = kwargs.get("json")
        if isinstance(body, dict) and url in {
            "/api/auth/register",
            "/api/auth/wechat/register",
        }:
            body = dict(body)
            body.setdefault("terms_version", TERMS_VERSION)
            body.setdefault("terms_digest", TERMS_CONTENT_DIGEST)
            body.setdefault("terms_locale", "en")
            kwargs["json"] = body
        elif url == "/api/me/accept-terms" and "json" not in kwargs:
            kwargs["json"] = {
                "terms_version": TERMS_VERSION,
                "terms_digest": TERMS_CONTENT_DIGEST,
                "locale": "en",
            }
        return super().post(url, *args, **kwargs)


# ---------------------------------------------------------------------------
# Fixture: fresh DB + TestClient + deterministic WeChat mock
# ---------------------------------------------------------------------------


@pytest.fixture
def wechat_client(monkeypatch):
    """A FastAPI TestClient wired to a fresh SQLite DB with a stubbed WeChat API.

    `wechat_mock` is attached to the yielded client so individual tests can
    program the openid/unionid returned by the fake jscode2session call.
    """
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("TRAINSIGHT_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "TRAINSIGHT_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    # Do NOT override TRAINSIGHT_JWT_SECRET. The api.auth module caches
    # JWT_SECRET at import time and is shared across tests; using the default
    # secret keeps api.users and api.auth in agreement on the signing key.
    monkeypatch.setenv("WECHAT_MINIAPP_APPID", "test-appid")
    monkeypatch.setenv("WECHAT_MINIAPP_SECRET", "test-secret")
    monkeypatch.setenv("TRAINSIGHT_ADMIN_EMAIL", "")
    # The auth rate limiter (api/auth_rate_limit.py) caps wechat/register
    # at 5/hour per IP. TestClient pins client.host to "testclient", so a
    # single test that calls register more than five times would otherwise
    # bleed into 429s. Tests for the limiter itself live in
    # tests/test_auth_rate_limit.py and re-enable it explicitly.
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "false")
    monkeypatch.setenv("PRAXYS_DISABLE_MINIAPP_PROCESSING", "false")

    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    # Reload modules that cached SECRET / ADMIN_EMAIL at import time.
    import importlib
    import api.users
    import api.invitations
    import api.routes.wechat
    importlib.reload(api.users)
    importlib.reload(api.invitations)
    importlib.reload(api.routes.wechat)

    # Rebuild the app so include_router() picks up the reloaded modules.
    import api.main
    importlib.reload(api.main)
    app = api.main.app

    # Replace the jscode2session call with a programmable stub.
    class WeChatMock:
        def __init__(self):
            # Default to returning a fresh openid; tests override as needed.
            self.next_openid = "openid-default"
            self.next_unionid = None
            self.should_fail = None  # set to (status_code, detail) to force an error

        async def fake(self, js_code: str) -> dict:
            if self.should_fail:
                from fastapi import HTTPException
                code, detail = self.should_fail
                raise HTTPException(code, detail)
            return {
                "openid": self.next_openid,
                "unionid": self.next_unionid,
                "session_key": "stub-session-key",
            }

    mock = WeChatMock()
    monkeypatch.setattr(api.routes.wechat, "_jscode2session", mock.fake)

    client = WeChatTestClient(
        app,
        headers={
            "X-Praxys-Client": "wechat-miniapp",
            "X-Praxys-Client-Version": "2026.08.2",
            "X-Praxys-Notice-Version": TERMS_VERSION,
            "X-Praxys-Policy-Digest": TERMS_CONTENT_DIGEST,
            "X-Praxys-Api-Contract": CN_PRIVACY_CONTRACT_VERSION,
        },
    )
    client.wechat_mock = mock  # type: ignore[attr-defined]
    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        try:
            if db_session.engine is not None:
                db_session.engine.dispose()
        except Exception:
            pass
        try:
            tmpdir.cleanup()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# /auth/wechat/login
# ---------------------------------------------------------------------------


def test_login_new_user_returns_setup_ticket(wechat_client):
    wechat_client.wechat_mock.next_openid = "openid-alice"
    r = wechat_client.post("/api/auth/wechat/login", json={"js_code": "code-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "needs_setup"
    assert body["access_token"] is None
    assert body["wechat_login_ticket"]

    # Ticket carries the openid under the right audience.
    from api.auth_secrets import get_jwt_secret
    decoded = pyjwt.decode(
        body["wechat_login_ticket"],
        get_jwt_secret(),
        algorithms=["HS256"],
        audience="trainsight:wechat-setup",
    )
    assert decoded["sub"] == "openid-alice"


def test_login_returning_user_gets_jwt(wechat_client):
    # Bootstrap: register a new user via the WeChat register endpoint first.
    wechat_client.wechat_mock.next_openid = "openid-bob"
    login = wechat_client.post("/api/auth/wechat/login", json={"js_code": "c1"})
    ticket = login.json()["wechat_login_ticket"]
    reg = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": ticket, "accepted_terms": True, "invitation_code": ""},
    )
    assert reg.status_code == 200, reg.text

    # Now a second login should short-circuit to status=ok + JWT.
    r = wechat_client.post("/api/auth/wechat/login", json={"js_code": "c2"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["access_token"]
    assert body["wechat_login_ticket"] is None


def test_jscode2session_without_config_raises_503(monkeypatch):
    """Unit test the helper directly — going through the full TestClient
    plus an importlib.reload to "unload" the wechat mock ends up
    re-running api.main's load_dotenv(), which silently restores any
    real credentials a developer has in their local .env. Testing the
    helper in isolation avoids that fragility entirely."""
    import asyncio
    from fastapi import HTTPException
    import api.routes.wechat as wechat_routes

    monkeypatch.setenv("WECHAT_MINIAPP_APPID", "")
    monkeypatch.setenv("WECHAT_MINIAPP_SECRET", "")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(wechat_routes._jscode2session("any-code"))
    assert exc_info.value.status_code == 503
    assert "WECHAT_NOT_CONFIGURED" in str(exc_info.value.detail)


# ---------------------------------------------------------------------------
# /auth/wechat/register
# ---------------------------------------------------------------------------


def _get_ticket(client, openid: str, unionid: str | None = None) -> str:
    client.wechat_mock.next_openid = openid
    client.wechat_mock.next_unionid = unionid
    r = client.post("/api/auth/wechat/login", json={"js_code": f"c-{openid}"})
    return r.json()["wechat_login_ticket"]


def test_register_first_user_becomes_admin_no_invite(wechat_client):
    ticket = _get_ticket(wechat_client, "openid-first")
    r = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": ticket, "accepted_terms": True, "invitation_code": ""},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    # The issued JWT should grant access to /api/auth/me (real auth middleware).
    me = wechat_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["is_superuser"] is True
    # WeChat-only users get a deterministic sentinel in the email column.
    assert body["email"] == "wechat:openid-first"


def test_register_second_user_without_invite_fails(wechat_client):
    # First user seeds the DB.
    first_ticket = _get_ticket(wechat_client, "openid-one")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": first_ticket, "accepted_terms": True, "invitation_code": ""},
    )

    # Second user has no invitation.
    second_ticket = _get_ticket(wechat_client, "openid-two")
    r = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": second_ticket, "accepted_terms": True, "invitation_code": ""},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "REGISTER_INVITATION_REQUIRED"


def test_register_second_user_with_valid_invite_succeeds(wechat_client):
    # Bootstrap an admin.
    admin_ticket = _get_ticket(wechat_client, "openid-admin")
    admin_reg = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": admin_ticket, "accepted_terms": True, "invitation_code": ""},
    )
    admin_token = admin_reg.json()["access_token"]

    # Admin creates an invitation via the admin API.
    inv_resp = wechat_client.post(
        "/api/admin/invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"note": "test"},
    )
    assert inv_resp.status_code in (200, 201), inv_resp.text
    code = inv_resp.json()["code"]

    # Second user registers with the invite.
    second_ticket = _get_ticket(wechat_client, "openid-invitee")
    r = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": second_ticket, "accepted_terms": True, "invitation_code": code},
    )
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]

    # Re-using the same invite must fail.
    third_ticket = _get_ticket(wechat_client, "openid-leech")
    r2 = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": third_ticket, "accepted_terms": True, "invitation_code": code},
    )
    assert r2.status_code == 400


def test_register_openid_already_bound_conflicts(wechat_client):
    ticket = _get_ticket(wechat_client, "openid-x")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": ticket, "accepted_terms": True, "invitation_code": ""},
    )

    # Try to register again with the same ticket (and therefore same openid).
    r = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": ticket, "accepted_terms": True, "invitation_code": ""},
    )
    assert r.status_code == 409
    assert "WECHAT_REGISTER_OPENID_ALREADY_BOUND" in r.text


def test_register_with_email_password_stores_both(wechat_client):
    ticket = _get_ticket(wechat_client, "openid-web")
    r = wechat_client.post(
        "/api/auth/wechat/register",
        json={
            "wechat_login_ticket": ticket, "accepted_terms": True,
            "invitation_code": "",
            "email": "alice@example.com",
            "password": "hunter2-longish",
        },
    )
    assert r.status_code == 200, r.text

    me = wechat_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {r.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


# ---------------------------------------------------------------------------
# /auth/wechat/link-with-password
# ---------------------------------------------------------------------------


def test_link_with_password_binds_openid_to_existing_account(wechat_client):
    # Existing web user (registered via the normal route).
    # First register as admin with email+password via the WeChat register path
    # (gives us a password we know; the normal register endpoint works too).
    admin_ticket = _get_ticket(wechat_client, "openid-seed-admin")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": admin_ticket, "accepted_terms": True, "invitation_code": ""},
    )

    # Now create a *separate* web-style user via the normal /api/auth/register,
    # with invitation code from admin.
    # Simpler: register a user directly using the WeChat register with email+pass,
    # then pretend they never bound WeChat. Achieve that by:
    #   1. Create user with email+pass via wechat register (binds openid A)
    #   2. Unbind openid A manually through a fresh openid B linking flow
    # Easier: use the FastAPI-Users normal register endpoint via admin-issued invite.

    # Admin invite
    admin_login = wechat_client.post(
        "/api/auth/wechat/login",
        json={"js_code": "c-seed-admin-reuse"},
    )
    admin_token = admin_login.json()["access_token"]
    inv = wechat_client.post(
        "/api/admin/invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"note": "for web user"},
    )
    invite_code = inv.json()["code"]

    reg = wechat_client.post(
        "/api/auth/register",
        json={
            "email": "bob@example.com",
            "password": "correct-horse-battery",
            "invitation_code": invite_code,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 200, reg.text

    # Now Bob opens the mini program for the first time. openid unknown → needs_setup.
    setup_ticket = _get_ticket(wechat_client, "openid-bob-phone")

    # Bob picks "I already have an account" and types his email+password.
    link = wechat_client.post(
        "/api/auth/wechat/link-with-password",
        json={
            "wechat_login_ticket": setup_ticket, "accepted_terms": True,
            "email": "bob@example.com",
            "password": "correct-horse-battery",
        },
    )
    assert link.status_code == 200, link.text
    token = link.json()["access_token"]

    me = wechat_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "bob@example.com"

    # Subsequent WeChat logins now go straight to status=ok.
    wechat_client.wechat_mock.next_openid = "openid-bob-phone"
    second = wechat_client.post("/api/auth/wechat/login", json={"js_code": "c-x"})
    assert second.json()["status"] == "ok"


def test_link_with_password_wrong_password_rejected(wechat_client):
    # Seed admin + invited web user exactly as above.
    admin_ticket = _get_ticket(wechat_client, "openid-admin-2")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": admin_ticket, "accepted_terms": True, "invitation_code": ""},
    )
    admin_token = wechat_client.post(
        "/api/auth/wechat/login", json={"js_code": "c-a2"}
    ).json()["access_token"]
    invite_code = wechat_client.post(
        "/api/admin/invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"note": "x"},
    ).json()["code"]
    wechat_client.post(
        "/api/auth/register",
        json={
            "email": "carol@example.com",
            "password": "real-password-abc",
            "invitation_code": invite_code,
            "accepted_terms": True,
        },
    )

    setup_ticket = _get_ticket(wechat_client, "openid-carol")
    r = wechat_client.post(
        "/api/auth/wechat/link-with-password",
        json={
            "wechat_login_ticket": setup_ticket, "accepted_terms": True,
            "email": "carol@example.com",
            "password": "wrong-password",
        },
    )
    assert r.status_code == 400
    assert "WECHAT_LINK_INVALID_CREDENTIALS" in r.text


def test_link_with_expired_ticket_rejected(wechat_client):
    # Manually forge an expired ticket with the real secret.
    from api.auth_secrets import get_jwt_secret
    expired = pyjwt.encode(
        {
            "sub": "openid-expired",
            "aud": "trainsight:wechat-setup",
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),
        },
        get_jwt_secret(),
        algorithm="HS256",
    )
    r = wechat_client.post(
        "/api/auth/wechat/link-with-password",
        json={
            "wechat_login_ticket": expired, "accepted_terms": True,
            "email": "anyone@example.com",
            "password": "whatever-long",
        },
    )
    assert r.status_code == 400
    assert "WECHAT_TICKET_EXPIRED" in r.text


def test_link_refuses_to_rebind_account_with_different_openid(wechat_client):
    # Bootstrap admin + one web user linked to openid-phone-A.
    admin_ticket = _get_ticket(wechat_client, "openid-admin-3")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": admin_ticket, "accepted_terms": True, "invitation_code": ""},
    )
    admin_token = wechat_client.post(
        "/api/auth/wechat/login", json={"js_code": "c-a3"}
    ).json()["access_token"]
    invite_code = wechat_client.post(
        "/api/admin/invitations",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"note": "x"},
    ).json()["code"]
    wechat_client.post(
        "/api/auth/register",
        json={
            "email": "dan@example.com",
            "password": "pw-dan-12345",
            "invitation_code": invite_code,
            "accepted_terms": True,
        },
    )
    # First link with phone-A openid.
    setup_a = _get_ticket(wechat_client, "openid-dan-phone-A")
    first = wechat_client.post(
        "/api/auth/wechat/link-with-password",
        json={
            "wechat_login_ticket": setup_a, "accepted_terms": True,
            "email": "dan@example.com",
            "password": "pw-dan-12345",
        },
    )
    assert first.status_code == 200

    # Second link attempt from phone-B openid (different device / re-install).
    # For now we block this — the user would need to unlink first via a future UI.
    setup_b = _get_ticket(wechat_client, "openid-dan-phone-B")
    second = wechat_client.post(
        "/api/auth/wechat/link-with-password",
        json={
            "wechat_login_ticket": setup_b, "accepted_terms": True,
            "email": "dan@example.com",
            "password": "pw-dan-12345",
        },
    )
    assert second.status_code == 409
    assert "WECHAT_LINK_ACCOUNT_ALREADY_LINKED" in second.text


def test_unlink_returns_was_bound_true_and_clears_openid(wechat_client):
    # Bootstrap an admin + grab the JWT, then unlink and verify next login
    # is treated as needs_setup (since wx_openid was wiped).
    admin_ticket = _get_ticket(wechat_client, "openid-unlink-A")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": admin_ticket, "accepted_terms": True, "invitation_code": ""},
    )
    token = wechat_client.post(
        "/api/auth/wechat/login", json={"js_code": "c-unlink-A"}
    ).json()["access_token"]

    unlink = wechat_client.post(
        "/api/auth/wechat/unlink",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert unlink.status_code == 200, unlink.text
    body = unlink.json()
    assert body["status"] == "ok"
    assert body["was_bound"] is True

    # Same openid now looks brand new to /login.
    wechat_client.wechat_mock.next_openid = "openid-unlink-A"
    after = wechat_client.post("/api/auth/wechat/login", json={"js_code": "c-after-unlink"})
    assert after.status_code == 200
    assert after.json()["status"] == "needs_setup"


def test_unlink_idempotent_when_no_binding(wechat_client):
    # An admin user whose wechat_openid we manually clear, then unlink
    # again — must succeed with was_bound=False.
    admin_ticket = _get_ticket(wechat_client, "openid-unlink-B")
    wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": admin_ticket, "accepted_terms": True, "invitation_code": ""},
    )
    token = wechat_client.post(
        "/api/auth/wechat/login", json={"js_code": "c-unlink-B"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = wechat_client.post("/api/auth/wechat/unlink", headers=headers)
    assert first.status_code == 200
    assert first.json()["was_bound"] is True

    second = wechat_client.post("/api/auth/wechat/unlink", headers=headers)
    assert second.status_code == 200
    assert second.json()["was_bound"] is False


def test_unlink_requires_authentication(wechat_client):
    no_auth = wechat_client.post("/api/auth/wechat/unlink")
    assert no_auth.status_code == 401

# ---------------------------------------------------------------------------
# EULA / Terms acceptance gate on web /api/auth/register
# ---------------------------------------------------------------------------


def test_register_requires_terms_acceptance(wechat_client):
    r = wechat_client.post(
        "/api/auth/register",
        json={"email": "noterm@example.com", "password": "pw-123456", "invitation_code": ""},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "REGISTER_TERMS_NOT_ACCEPTED"


def test_register_records_terms_version(wechat_client):
    r = wechat_client.post(
        "/api/auth/register",
        json={"email": "yesterm@example.com", "password": "pw-123456", "accepted_terms": True},
    )
    assert r.status_code == 200, r.text
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db.models import TermsAcceptanceReceipt, User
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == "yesterm@example.com").first()
        assert u is not None and u.terms_version == TERMS_VERSION
        assert u.terms_digest == TERMS_CONTENT_DIGEST
        assert u.terms_accepted_at is not None
        receipts = (
            db.query(TermsAcceptanceReceipt)
            .filter(TermsAcceptanceReceipt.user_id == u.id)
            .all()
        )
        assert len(receipts) == 1
        assert receipts[0].terms_digest == TERMS_CONTENT_DIGEST
    finally:
        db.close()


def test_wechat_invitation_race_cleanup_removes_terms_receipt(
    wechat_client,
    monkeypatch,
):
    admin_ticket = _get_ticket(wechat_client, "openid-race-admin")
    admin_response = wechat_client.post(
        "/api/auth/wechat/register",
        json={
            "wechat_login_ticket": admin_ticket,
            "accepted_terms": True,
            "invitation_code": "",
        },
    )
    assert admin_response.status_code == 200, admin_response.text

    import api.routes.wechat as wechat_routes
    from db.models import Invitation, TermsAcceptanceReceipt, User
    from db.session import SessionLocal

    db = SessionLocal()
    admin = db.query(User).filter(
        User.wechat_openid == "openid-race-admin"
    ).one()
    db.add(Invitation(code="TS-WRACE-001", created_by=admin.id))
    db.commit()
    receipt_count = db.query(TermsAcceptanceReceipt).count()
    db.close()

    monkeypatch.setattr(
        wechat_routes,
        "claim_invitation",
        lambda *_args, **_kwargs: False,
    )
    user_ticket = _get_ticket(wechat_client, "openid-race-loser")
    response = wechat_client.post(
        "/api/auth/wechat/register",
        json={
            "wechat_login_ticket": user_ticket,
            "accepted_terms": True,
            "invitation_code": "TS-WRACE-001",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "REGISTER_INVALID_INVITATION"
    db = SessionLocal()
    try:
        assert (
            db.query(User)
            .filter(User.wechat_openid == "openid-race-loser")
            .count()
            == 0
        )
        assert db.query(TermsAcceptanceReceipt).count() == receipt_count
    finally:
        db.close()


def test_register_rejects_missing_legal_bundle(wechat_client):
    response = TestClient.post(
        wechat_client,
        "/api/auth/register",
        json={
            "email": "old-client@example.com",
            "password": "pw-123456",
            "accepted_terms": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TERMS_BUNDLE_MISMATCH"


def test_wechat_register_requires_terms_acceptance(wechat_client):
    ticket = _get_ticket(wechat_client, "openid-noterm")
    r = wechat_client.post(
        "/api/auth/wechat/register",
        json={"wechat_login_ticket": ticket, "invitation_code": ""},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "REGISTER_TERMS_NOT_ACCEPTED"


# ---------------------------------------------------------------------------
# EULA re-acceptance gate (issue #324)
# ---------------------------------------------------------------------------


def _login_token(client, email: str, password: str) -> str:
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": "Bear" + "er " + token}


def test_accept_terms_clears_stale_version(wechat_client):
    email, pw = "stale@example.com", "pw-123456"
    reg = wechat_client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "accepted_terms": True},
    )
    assert reg.status_code == 200, reg.text
    token = _login_token(wechat_client, email, pw)
    hdr = {"Authorization": f"Bearer {token}"}

    # Force a stale terms_version to simulate a post-bump returning user.
    from db.models import User, UserConnection
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        u.terms_version = "0000.00.0"
        db.add(
            UserConnection(
                user_id=u.id,
                platform="oura",
                encrypted_credentials=b"opaque-test-credentials",
                status="connected",
            )
        )
        db.commit()
    finally:
        db.close()

    me = wechat_client.get("/api/auth/me", headers=hdr).json()
    assert me["terms_current"] is False  # stale -> 1 prompt

    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    blocked = wechat_client.get("/api/today", headers=hdr)
    assert blocked.status_code == 428
    assert blocked.json()["detail"] == {
        "code": "TERMS_ACCEPTANCE_REQUIRED",
        "terms_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
    }

    export = wechat_client.get("/api/me/export", headers=hdr)
    assert export.status_code == 200, export.text

    connections = wechat_client.get(
        "/api/settings/connections",
        headers=hdr,
    )
    assert connections.status_code == 200, connections.text
    assert connections.json()["connections"]["oura"] == {
        "status": "connected",
        "last_sync": None,
        "has_credentials": True,
        "next_retry_at": None,
        "consecutive_failures": 0,
        "last_error": None,
    }

    disconnected = wechat_client.delete(
        "/api/settings/connections/oura",
        headers=hdr,
    )
    assert disconnected.status_code == 200, disconnected.text
    assert disconnected.json() == {
        "status": "disconnected",
        "platform": "oura",
    }
    connections_after = wechat_client.get(
        "/api/settings/connections",
        headers=hdr,
    )
    assert "oura" not in connections_after.json()["connections"]

    acc = wechat_client.post("/api/me/accept-terms", headers=hdr)
    assert acc.status_code == 200, acc.text
    assert acc.json()["terms_version"] == TERMS_VERSION
    assert acc.json()["terms_current"] is True
    assert acc.json()["terms_digest"] == TERMS_CONTENT_DIGEST

    me2 = wechat_client.get("/api/auth/me", headers=hdr).json()
    assert me2["terms_current"] is True  # cleared after accept
    assert wechat_client.get("/api/today", headers=hdr).status_code == 200

    from db.models import TermsAcceptanceReceipt, User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        receipts = (
            db.query(TermsAcceptanceReceipt)
            .filter(TermsAcceptanceReceipt.user_id == user.id)
            .order_by(TermsAcceptanceReceipt.accepted_at)
            .all()
        )
        assert len(receipts) == 2
        assert {receipt.channel for receipt in receipts} == {
            "wechat-miniapp"
        }
        assert {
            receipt.action for receipt in receipts
        } == {"accept_terms_and_acknowledge_privacy"}
        assert {receipt.release_id for receipt in receipts} == {None}
        assert {receipt.client_version for receipt in receipts} == {None}
        assert {receipt.source_sha for receipt in receipts} == {None}
        assert {receipt.notice_version for receipt in receipts} == {
            TERMS_VERSION
        }
        user.is_demo = True
        user.terms_version = "0000.00.0"
        user.terms_digest = "sha256:" + ("0" * 64)
        db.commit()
    finally:
        db.close()

    demo_me = wechat_client.get("/api/auth/me", headers=hdr)
    assert demo_me.status_code == 200, demo_me.text
    assert demo_me.json()["is_demo"] is True
    assert demo_me.json()["terms_current"] is False
    demo_blocked = wechat_client.get("/api/today", headers=hdr)
    assert demo_blocked.status_code == 428
    assert (
        demo_blocked.json()["detail"]["code"]
        == "TERMS_ACCEPTANCE_REQUIRED"
    )


def test_existing_web_user_must_acknowledge_cn_before_processing(
    wechat_client,
    monkeypatch,
):
    """A current .run receipt does not silently classify a .cn user."""

    client = TestClient(wechat_client.app)
    email, password = "existing-run-to-cn@example.com", "pw-123456"
    registered = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
            "terms_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "terms_locale": "en",
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login_token(client, email, password)
    cn_headers = {
        **_auth_headers(token),
        "Origin": "https://praxys.cn",
        "X-Praxys-Client": "cn-web",
        "X-Praxys-Notice-Version": TERMS_VERSION,
        "X-Praxys-Policy-Digest": TERMS_CONTENT_DIGEST,
        "X-Praxys-Api-Contract": CN_PRIVACY_CONTRACT_VERSION,
    }

    me = client.get("/api/auth/me", headers=cn_headers)
    assert me.status_code == 200, me.text
    assert me.json()["terms_current"] is False
    blocked = client.get("/api/today", headers=cn_headers)
    assert blocked.status_code == 428
    assert blocked.json()["detail"]["code"] == "TERMS_ACCEPTANCE_REQUIRED"

    from db.models import TermsAcceptanceReceipt, User
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user_id = user.id
        assert (
            db.query(TermsAcceptanceReceipt)
            .filter(
                TermsAcceptanceReceipt.user_id == user_id,
                TermsAcceptanceReceipt.channel == "cn-web",
            )
            .count()
            == 0
        )
    finally:
        db.close()

    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "true")
    accepted = client.post(
        "/api/me/accept-terms",
        headers=cn_headers,
        json={
            "terms_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "locale": "en",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["terms_current"] is True
    assert client.get("/api/auth/me", headers=cn_headers).json()[
        "terms_current"
    ] is True

    db = SessionLocal()
    try:
        receipt = (
            db.query(TermsAcceptanceReceipt)
            .filter(
                TermsAcceptanceReceipt.user_id == user_id,
                TermsAcceptanceReceipt.channel == "cn-web",
                TermsAcceptanceReceipt.terms_version == TERMS_VERSION,
                TermsAcceptanceReceipt.terms_digest
                == TERMS_CONTENT_DIGEST,
            )
            .one()
        )
        assert receipt.notice_version == TERMS_VERSION

        from api.legal_receipts import (
            user_background_processing_authorized,
        )

        assert not user_background_processing_authorized(db, user_id)
    finally:
        db.close()

    rights = client.get("/api/auth/me", headers=cn_headers)
    assert rights.status_code == 200
    assert rights.json()["terms_current"] is True
    stopped = client.get("/api/today", headers=cn_headers)
    assert stopped.status_code == 503
    assert stopped.json()["detail"]["code"] == "CN_PROCESSING_DISABLED"


def test_stale_terms_user_can_delete_account(wechat_client):
    email, password = "stale-delete@example.com", "pw-123456"
    registered = wechat_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login_token(wechat_client, email, password)

    from fastapi_users.password import PasswordHelper
    from db.models import User
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.terms_version = "0000.00.0"
        user.terms_digest = "sha256:" + ("0" * 64)
        db.add(
            User(
                id="backup-admin",
                email="backup-admin@example.com",
                hashed_password=PasswordHelper().hash("unused-password"),
                is_active=True,
                is_superuser=True,
                is_verified=True,
            )
        )
        db.commit()
        user_id = user.id
    finally:
        db.close()

    deleted = wechat_client.delete(
        "/api/me",
        headers=_auth_headers(token),
    )
    assert deleted.status_code == 200, deleted.text

    db = SessionLocal()
    try:
        assert db.query(User).filter(User.id == user_id).count() == 0
        assert (
            db.query(User)
            .filter(User.id == "backup-admin", User.is_superuser.is_(True))
            .count()
            == 1
        )
    finally:
        db.close()


def test_stale_terms_user_can_unlink_wechat_identity(wechat_client):
    email, password = "stale-unlink@example.com", "pw-123456"
    registered = wechat_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login_token(wechat_client, email, password)

    from db.models import User
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.wechat_openid = "openid-stale-unlink"
        user.wechat_unionid = "unionid-stale-unlink"
        user.wechat_nickname = "stale nickname"
        user.wechat_avatar_url = "https://example.test/stale.png"
        user.terms_version = "0000.00.0"
        user.terms_digest = "sha256:" + ("0" * 64)
        db.commit()
        user_id = user.id
    finally:
        db.close()

    response = wechat_client.post(
        "/api/auth/wechat/unlink",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "was_bound": True}

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.wechat_openid is None
        assert user.wechat_unionid is None
        assert user.wechat_nickname is None
        assert user.wechat_avatar_url is None
    finally:
        db.close()


def test_stale_terms_user_can_read_only_owned_feedback_image(
    wechat_client,
    monkeypatch,
):
    email, password = "stale-image@example.com", "pw-123456"
    registered = wechat_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login_token(wechat_client, email, password)

    from api import feedback_storage
    from db.models import Feedback, User
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.terms_version = "0000.00.0"
        user.terms_digest = "sha256:" + ("0" * 64)
        owned = Feedback(
            user_id=user.id,
            kind="other",
            message="owned image",
            image_keys=["feedback/owned/0.png"],
        )
        outsider = Feedback(
            user_id="another-user",
            kind="other",
            message="not owned",
            image_keys=["feedback/outsider/0.png"],
        )
        db.add(
            User(
                id="another-user",
                email="another-user@example.com",
                hashed_password="unused",
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
        )
        db.add_all([owned, outsider])
        db.commit()
        owned_id = owned.id
        outsider_id = outsider.id
    finally:
        db.close()

    monkeypatch.setattr(
        feedback_storage,
        "load_image",
        lambda key: (
            (b"owned-image", "image/png")
            if key == "feedback/owned/0.png"
            else None
        ),
    )
    headers = _auth_headers(token)

    response = wechat_client.get(
        f"/api/me/feedback/{owned_id}/image/0",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.content == b"owned-image"
    assert response.headers["cache-control"] == "private, no-store"
    assert (
        wechat_client.get(
            f"/api/me/feedback/{outsider_id}/image/0",
            headers=headers,
        ).status_code
        == 404
    )


def test_authenticated_demo_must_accept_current_terms_before_access(
    wechat_client,
):
    email, password = "demo-terms@example.com", "pw-123456"
    registered = wechat_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login_token(wechat_client, email, password)
    headers = {"Authorization": f"Bearer {token}"}

    from db.models import TermsAcceptanceReceipt, User
    from db.session import SessionLocal

    stale_version = "0000.00.0"
    stale_digest = "sha256:" + ("0" * 64)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.is_demo = True
        user.terms_version = stale_version
        user.terms_digest = stale_digest
        db.commit()
        user_id = user.id
        receipt_count = (
            db.query(TermsAcceptanceReceipt)
            .filter(TermsAcceptanceReceipt.user_id == user_id)
            .count()
        )
    finally:
        db.close()

    blocked = wechat_client.get("/api/today", headers=headers)
    assert blocked.status_code == 428
    assert blocked.json()["detail"]["code"] == (
        "TERMS_ACCEPTANCE_REQUIRED"
    )

    accepted = wechat_client.post("/api/me/accept-terms", headers=headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["terms_current"] is True

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        observed = {
            "terms_version": user.terms_version,
            "terms_digest": user.terms_digest,
            "receipt_count": (
                db.query(TermsAcceptanceReceipt)
                .filter(TermsAcceptanceReceipt.user_id == user_id)
                .count()
            ),
        }
    finally:
        db.close()

    assert observed["terms_version"] == TERMS_VERSION
    assert observed["terms_digest"] == TERMS_CONTENT_DIGEST
    assert observed["receipt_count"] == receipt_count + 1
    assert wechat_client.get("/api/today", headers=headers).status_code == 200


def test_accept_terms_rejects_mismatched_digest_without_new_receipt(
    wechat_client,
):
    email, password = "mismatch@example.com", "pw-123456"
    reg = wechat_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 200, reg.text
    token = _login_token(wechat_client, email, password)

    from db.models import TermsAcceptanceReceipt, User
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.terms_version = "0000.00.0"
        db.commit()
        user_id = user.id
    finally:
        db.close()

    response = TestClient.post(
        wechat_client,
        "/api/me/accept-terms",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "terms_version": TERMS_VERSION,
            "terms_digest": "sha256:" + ("0" * 64),
            "locale": "en",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TERMS_BUNDLE_MISMATCH"
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).one()
        assert user.terms_version == "0000.00.0"
        assert (
            db.query(TermsAcceptanceReceipt)
            .filter(TermsAcceptanceReceipt.user_id == user_id)
            .count()
        ) == 1
    finally:
        db.close()


def test_accept_terms_serializes_channel_receipt_with_background_commits(
    wechat_client,
    monkeypatch,
):
    email, password = "receipt-lock@example.com", "pw-123456"
    registered = wechat_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 200, registered.text
    token = _login_token(wechat_client, email, password)

    from db import cache_revision

    locked_users: list[str] = []
    monkeypatch.setattr(
        cache_revision,
        "lock_revision_writes",
        lambda _db, user_id: locked_users.append(user_id),
    )

    accepted = wechat_client.post(
        "/api/me/accept-terms",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "terms_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "locale": "en",
        },
    )

    assert accepted.status_code == 200, accepted.text
    assert len(locked_users) == 1


def test_terms_acceptance_receipts_reject_updates(wechat_client):
    reg = wechat_client.post(
        "/api/auth/register",
        json={
            "email": "immutable@example.com",
            "password": "pw-123456",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 200, reg.text

    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError
    from db.models import TermsAcceptanceReceipt, User
    from db.session import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "immutable@example.com").one()
        receipt = (
            db.query(TermsAcceptanceReceipt)
            .filter(TermsAcceptanceReceipt.user_id == user.id)
            .one()
        )
        with pytest.raises(DatabaseError, match="immutable"):
            db.execute(
                text(
                    "UPDATE terms_acceptance_receipts "
                    "SET locale = 'zh' WHERE id = :receipt_id"
                ),
                {"receipt_id": receipt.id},
            )
            db.commit()
        db.rollback()
        db.refresh(receipt)
        assert receipt.locale == "en"
    finally:
        db.close()


def test_accept_terms_requires_auth(wechat_client):
    assert wechat_client.post("/api/me/accept-terms").status_code == 401
