"""Focused tests for the dormant China channel boundary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.china_client_boundary import (
    CHINA_CLIENT_CONTEXT_SCOPE_KEY,
    CN_PRIVACY_CONTRACT_VERSION,
    CN_WEB_CLIENT,
    DISABLE_CN_PROCESSING_ENV,
    DISABLE_MINIAPP_PROCESSING_ENV,
    MINIAPP_CLIENT,
    MINIMUM_MINIAPP_VERSION,
    ChinaClientBoundaryMiddleware,
    _parse_calver,
    _parse_miniapp_version,
    china_processing_enabled,
    china_processing_status,
    miniapp_processing_enabled,
    miniapp_processing_status,
    revalidate_china_client_context,
)
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from api.legal_receipts import (
    TERMS_ACCEPTANCE_ACTION,
    TermsAcceptanceRequest,
    build_terms_receipt,
    user_background_processing_authorized,
)
from db.models import Base, TermsAcceptanceReceipt, User


@pytest.fixture(autouse=True)
def explicit_test_processing_enable(monkeypatch) -> None:
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")
    monkeypatch.setenv(DISABLE_MINIAPP_PROCESSING_ENV, "false")


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(ChinaClientBoundaryMiddleware)

    @app.get("/api/today")
    def today(request: Request) -> dict[str, object]:
        state = request.scope.get("state", {})
        return {
            "ok": True,
            "china_context": state.get(CHINA_CLIENT_CONTEXT_SCOPE_KEY),
        }

    @app.post("/api/auth/wechat/login")
    def wechat_login() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/status")
    def status() -> dict[str, bool]:
        return {"ok": True}

    @app.api_route(
        "/api/auth/logout",
        methods=["POST"],
    )
    @app.api_route(
        "/api/auth/wechat/unlink",
        methods=["POST"],
    )
    @app.api_route(
        "/api/me/export",
        methods=["GET"],
    )
    @app.api_route(
        "/api/me",
        methods=["DELETE"],
    )
    @app.api_route(
        "/api/settings/connections/garmin",
        methods=["DELETE"],
    )
    def rights_route(request: Request) -> dict[str, object]:
        state = request.scope.get("state", {})
        return {
            "ok": True,
            "china_context": state.get(CHINA_CLIENT_CONTEXT_SCOPE_KEY),
        }

    @app.post("/api/terms-receipt-context")
    def terms_receipt_context(request: Request) -> dict[str, str | None]:
        receipt = build_terms_receipt(
            user_id="receipt-user",
            request=request,
            payload=TermsAcceptanceRequest(
                terms_version=TERMS_VERSION,
                terms_digest=TERMS_CONTENT_DIGEST,
                locale="en",
            ),
            accepted_at=datetime.now(timezone.utc),
        )
        return {
            "action": receipt.action,
            "channel": receipt.channel,
            "client_version": receipt.client_version,
            "source_sha": receipt.source_sha,
            "notice_version": receipt.notice_version,
            "release_id": receipt.release_id,
        }

    return TestClient(app)


@pytest.fixture
def actual_app_client(monkeypatch, tmp_path):
    """Use the real route table with isolated auth and storage."""

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
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

    from api.auth import (
        get_current_user_id,
        get_data_user_id,
        require_account_deletion_access,
        require_write_access,
    )
    from api.main import app
    from db.session import get_db

    user_id = "china-boundary-actual-app"
    with db_session.SessionLocal() as db:
        db.add(User(
            id=user_id,
            email="china-boundary@example.test",
            hashed_password="not-used",
            is_active=True,
            is_verified=True,
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
            terms_accepted_at=datetime.now(timezone.utc),
        ))
        db.commit()

    def override_user() -> str:
        return user_id

    def override_db():
        with db_session.SessionLocal() as db:
            yield db

    app.dependency_overrides[get_current_user_id] = override_user
    app.dependency_overrides[get_data_user_id] = override_user
    app.dependency_overrides[require_write_access] = override_user
    app.dependency_overrides[require_account_deletion_access] = override_user
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, db_session, user_id
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


def _cn_web_headers() -> dict[str, str]:
    return {
        "Origin": "https://praxys.cn",
        "X-Praxys-Client": CN_WEB_CLIENT,
        "X-Praxys-Notice-Version": TERMS_VERSION,
        "X-Praxys-Policy-Digest": TERMS_CONTENT_DIGEST,
        "X-Praxys-Api-Contract": CN_PRIVACY_CONTRACT_VERSION,
    }


def _miniapp_headers(
    *,
    version: str = MINIMUM_MINIAPP_VERSION,
) -> dict[str, str]:
    return {
        "Referer": "https://servicewechat.com/test-appid/1/page-frame.html",
        "X-Praxys-Client": MINIAPP_CLIENT,
        "X-Praxys-Client-Version": version,
        "X-Praxys-Notice-Version": TERMS_VERSION,
        "X-Praxys-Policy-Digest": TERMS_CONTENT_DIGEST,
        "X-Praxys-Api-Contract": CN_PRIVACY_CONTRACT_VERSION,
    }


def test_cn_web_uses_only_minimal_current_contract() -> None:
    client = _client()
    blocked = client.get(
        "/api/today",
        headers={"Origin": "https://praxys.cn"},
    )
    assert blocked.status_code == 428
    assert (
        blocked.json()["detail"]["code"]
        == "CLIENT_PRIVACY_UPDATE_REQUIRED"
    )

    headers = _cn_web_headers()
    headers.update({
        "X-Praxys-Client-Version": "legacy-version",
        "X-Praxys-Source-Sha": "not-a-release-authority",
        "X-Praxys-Release-Id": "legacy-provider-id",
    })
    allowed = client.get("/api/today", headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["china_context"] == {
        "channel": CN_WEB_CLIENT,
        "notice_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }


def test_signed_context_ignores_only_legacy_release_fields() -> None:
    context = {
        "channel": CN_WEB_CLIENT,
        "notice_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        "client_version": "legacy",
        "source_sha": "legacy",
        "release_id": "legacy",
    }
    assert revalidate_china_client_context(context) == {
        "channel": CN_WEB_CLIENT,
        "notice_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }
    with pytest.raises(ValueError):
        revalidate_china_client_context({**context, "unexpected": "value"})


@pytest.mark.parametrize(
    ("channel", "channel_switch", "other_switch"),
    (
        (
            CN_WEB_CLIENT,
            DISABLE_CN_PROCESSING_ENV,
            DISABLE_MINIAPP_PROCESSING_ENV,
        ),
        (
            MINIAPP_CLIENT,
            DISABLE_MINIAPP_PROCESSING_ENV,
            DISABLE_CN_PROCESSING_ENV,
        ),
    ),
)
def test_signed_context_uses_only_its_validated_channel_switch(
    channel: str,
    channel_switch: str,
    other_switch: str,
    monkeypatch,
) -> None:
    context = {
        "channel": channel,
        "notice_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }
    monkeypatch.setenv(channel_switch, "false")
    monkeypatch.setenv(other_switch, "true")
    assert revalidate_china_client_context(context) == context

    monkeypatch.setenv(channel_switch, "true")
    monkeypatch.setenv(other_switch, "false")
    with pytest.raises(ValueError, match="processing is disabled"):
        revalidate_china_client_context(context)


@pytest.mark.parametrize(
    ("header", "value"),
    (
        ("X-Praxys-Notice-Version", "stale-notice"),
        ("X-Praxys-Policy-Digest", "sha256:" + ("0" * 64)),
        ("X-Praxys-Api-Contract", "stale-contract"),
    ),
)
def test_cn_web_rejects_stale_minimal_contract(
    header: str,
    value: str,
) -> None:
    headers = _cn_web_headers()
    headers[header] = value
    response = _client().get("/api/today", headers=headers)
    assert response.status_code == 428


def test_channel_classification_is_server_authoritative() -> None:
    forged = _cn_web_headers()
    forged.pop("Origin")
    response = _client().get("/api/today", headers=forged)
    assert response.status_code == 200
    assert response.json()["china_context"] is None

    lookalike = _cn_web_headers()
    lookalike["Origin"] = "https://praxys.cn.evil.example"
    response = _client().get("/api/today", headers=lookalike)
    assert response.status_code == 200
    assert response.json()["china_context"] is None


def test_miniapp_accepts_release_and_robot_five_versions() -> None:
    assert _parse_calver(MINIMUM_MINIAPP_VERSION) == (2026, 8, 2)
    assert _parse_miniapp_version("2026.08.29.15-deadbee") == (
        2026,
        8,
        29,
    )
    client = _client()
    for version in (
        "2026.08.1",
        "2026.08.01.15-deadbee",
        "develop",
        "2026.08.29.0-deadbee",
        "2026.08.29.15-DEADBEE",
    ):
        old = client.post(
            "/api/auth/wechat/login",
            headers=_miniapp_headers(version=version),
        )
        assert old.status_code == 428
        assert (
            old.json()["detail"]["minimum_version"]
            == MINIMUM_MINIAPP_VERSION
        )

    for version in ("2026.08.2", "2026.08.02.15-deadbee"):
        current = _miniapp_headers(version=version)
        current["X-Praxys-Source-Sha"] = "legacy-is-ignored"
        assert (
            client.post(
                "/api/auth/wechat/login",
                headers=current,
            ).status_code
            == 200
        )


@pytest.mark.parametrize("raw", (None, "", "malformed"))
def test_cn_switch_is_fail_closed(raw: str | None, monkeypatch) -> None:
    if raw is None:
        monkeypatch.delenv(DISABLE_CN_PROCESSING_ENV, raising=False)
    else:
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, raw)
    assert china_processing_enabled() is False
    response = _client().get("/api/today", headers=_cn_web_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "CN_PROCESSING_DISABLED"
    assert china_processing_status()["disabled"] is True


def test_china_processing_status_has_no_release_registry_fields(
    monkeypatch,
) -> None:
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
    assert china_processing_status() == {
        "enabled": False,
        "disabled": True,
        "notice_version": TERMS_VERSION,
        "legal_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }


@pytest.mark.parametrize("raw", (None, "", "malformed", "true"))
def test_miniapp_switch_is_independent_and_fail_closed(
    raw: str | None,
    monkeypatch,
) -> None:
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")
    if raw is None:
        monkeypatch.delenv(DISABLE_MINIAPP_PROCESSING_ENV, raising=False)
    else:
        monkeypatch.setenv(DISABLE_MINIAPP_PROCESSING_ENV, raw)

    assert miniapp_processing_enabled() is False
    assert miniapp_processing_status() == {
        "enabled": False,
        "disabled": True,
    }
    response = _client().post(
        "/api/auth/wechat/login",
        headers=_miniapp_headers(),
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == (
        "MINIAPP_PROCESSING_DISABLED"
    )
    rights = _client().post(
        "/api/auth/wechat/unlink",
        headers=_miniapp_headers(),
    )
    assert rights.status_code == 200
    assert rights.json()["china_context"]["channel"] == MINIAPP_CLIENT
    assert _client().get(
        "/api/today",
        headers=_cn_web_headers(),
    ).status_code == 200


def test_exact_cn_origin_precedes_conflicting_miniapp_claim(
    monkeypatch,
) -> None:
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
    monkeypatch.setenv(DISABLE_MINIAPP_PROCESSING_ENV, "false")
    headers = _miniapp_headers()
    headers["Origin"] = "https://praxys.cn"

    blocked = _client().post(
        "/api/auth/wechat/login",
        headers=headers,
    )
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["code"] == (
        "CN_PROCESSING_DISABLED"
    )

    rights = _client().post(
        "/api/auth/wechat/unlink",
        headers=headers,
    )
    assert rights.status_code == 200
    assert rights.json()["china_context"]["channel"] == CN_WEB_CLIENT


def test_kill_switch_preserves_exact_rights_and_public_routes(
    monkeypatch,
) -> None:
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
    client = _client()
    assert (
        client.get("/api/today", headers=_cn_web_headers()).status_code
        == 503
    )
    for method, path, expected_channel in (
        ("get", "/api/me/export", CN_WEB_CLIENT),
        ("post", "/api/auth/logout", CN_WEB_CLIENT),
        ("post", "/api/auth/wechat/unlink", CN_WEB_CLIENT),
        ("delete", "/api/settings/connections/garmin", CN_WEB_CLIENT),
        ("delete", "/api/me", CN_WEB_CLIENT),
    ):
        response = getattr(client, method)(
            path,
            headers={"Origin": "https://praxys.cn"},
        )
        assert response.status_code == 200
        assert (
            response.json()["china_context"]["channel"]
            == expected_channel
        )
    assert client.post(
        "/api/auth/jwt/logout",
        headers={"Origin": "https://praxys.cn"},
    ).status_code == 503
    assert (
        client.get(
            "/api/status",
            headers={"Origin": "https://www.praxys.cn"},
        ).status_code
        == 200
    )


def test_actual_app_cn_origin_wins_conflicting_claim_and_receipt_channel(
    actual_app_client,
    monkeypatch,
) -> None:
    client, db_session, user_id = actual_app_client
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
    monkeypatch.setenv(DISABLE_MINIAPP_PROCESSING_ENV, "false")
    headers = _miniapp_headers()
    headers["Origin"] = "https://praxys.cn"

    blocked = client.post(
        "/api/auth/wechat/login",
        headers=headers,
        json={"code": "not-used"},
    )
    assert blocked.status_code == 503
    assert blocked.json()["detail"]["code"] == (
        "CN_PROCESSING_DISABLED"
    )

    accepted = client.post(
        "/api/me/accept-terms",
        headers=headers,
        json={
            "terms_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "locale": "en",
        },
    )
    assert accepted.status_code == 200
    with db_session.SessionLocal() as db:
        channels = {
            receipt.channel
            for receipt in db.query(TermsAcceptanceReceipt)
            .filter_by(user_id=user_id)
            .all()
        }
    assert channels == {CN_WEB_CLIENT}


@pytest.mark.parametrize("channel", (CN_WEB_CLIENT, MINIAPP_CLIENT))
def test_actual_app_rights_routes_bypass_disabled_channel_boundary(
    actual_app_client,
    monkeypatch,
    channel: str,
) -> None:
    client, db_session, user_id = actual_app_client
    if channel == CN_WEB_CLIENT:
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
        headers = {"Origin": "https://praxys.cn"}
    else:
        monkeypatch.setenv(DISABLE_MINIAPP_PROCESSING_ENV, "true")
        headers = _miniapp_headers()

    assert client.post(
        "/api/auth/logout",
        headers=headers,
    ).status_code == 401

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["terms_current"] is False

    exported = client.get("/api/me/export", headers=headers)
    assert exported.status_code == 200
    assert "praxys-data-export-" in exported.headers["content-disposition"]

    connections = client.get(
        "/api/settings/connections",
        headers=headers,
    )
    assert connections.status_code == 200
    assert connections.json() == {"connections": {}}

    accepted = client.post(
        "/api/me/accept-terms",
        headers=headers,
        json={
            "terms_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "locale": "en",
        },
    )
    assert accepted.status_code == 200

    disconnected = client.delete(
        "/api/settings/connections/garmin",
        headers=headers,
    )
    assert disconnected.status_code == 200
    assert disconnected.json() == {
        "status": "disconnected",
        "platform": "garmin",
    }

    withdrawn = client.delete(
        "/api/labs/environment-response",
        headers=headers,
    )
    assert withdrawn.status_code == 204

    with db_session.SessionLocal() as db:
        receipt = db.query(TermsAcceptanceReceipt).filter_by(
            user_id=user_id,
        ).one()
        assert receipt.channel == channel

    deleted = client.delete("/api/me", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_terms_receipts_store_channel_not_client_release_identity() -> None:
    client = _client()
    ordinary = client.post("/api/terms-receipt-context")
    assert ordinary.json() == {
        "action": TERMS_ACCEPTANCE_ACTION,
        "channel": "web",
        "client_version": None,
        "source_sha": None,
        "notice_version": None,
        "release_id": None,
    }

    cn = client.post(
        "/api/terms-receipt-context",
        headers=_cn_web_headers(),
    )
    assert cn.json() == {
        "action": TERMS_ACCEPTANCE_ACTION,
        "channel": CN_WEB_CLIENT,
        "client_version": None,
        "source_sha": None,
        "notice_version": TERMS_VERSION,
        "release_id": None,
    }


def _background_session(channel: str | None) -> tuple[Session, str]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    user = User(
        email=f"{channel or 'legacy'}@example.test",
        hashed_password="not-used",
        is_active=True,
        is_verified=True,
        terms_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    if channel is not None:
        db.add(TermsAcceptanceReceipt(
            user_id=user.id,
            action=TERMS_ACCEPTANCE_ACTION,
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
            channel=channel,
            accepted_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ))
        db.commit()
    return db, user.id


@pytest.mark.parametrize(
    ("channel", "switch"),
    (
        (CN_WEB_CLIENT, DISABLE_CN_PROCESSING_ENV),
        (MINIAPP_CLIENT, DISABLE_MINIAPP_PROCESSING_ENV),
    ),
)
def test_channel_switch_gates_background_jobs_for_channel_receipts(
    channel: str,
    switch: str,
    monkeypatch,
) -> None:
    db, user_id = _background_session(channel)
    try:
        from api.optional_processing import background_ai_authorized

        monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
        monkeypatch.setenv(switch, "true")
        assert not user_background_processing_authorized(db, user_id)
        assert not background_ai_authorized(db, user_id=user_id)
        db.add(TermsAcceptanceReceipt(
            user_id=user_id,
            action=TERMS_ACCEPTANCE_ACTION,
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
            channel="web",
            accepted_at=datetime.now(timezone.utc),
        ))
        db.commit()
        assert not user_background_processing_authorized(db, user_id)
        monkeypatch.setenv(switch, "false")
        assert user_background_processing_authorized(db, user_id)
        assert background_ai_authorized(db, user_id=user_id)
    finally:
        db.close()


@pytest.mark.parametrize("channel", (None, "web"))
def test_run_background_jobs_do_not_depend_on_cn_switch(
    channel: str | None,
    monkeypatch,
) -> None:
    db, user_id = _background_session(channel)
    try:
        monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
        assert user_background_processing_authorized(db, user_id)
    finally:
        db.close()
