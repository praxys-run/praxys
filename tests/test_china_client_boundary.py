"""Tests for the runtime China client privacy floor."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.china_client_boundary import (
    APPROVED_RELEASES_ENV,
    CN_PRIVACY_CONTRACT_VERSION,
    CN_WEB_CLIENT,
    DISABLE_CN_PROCESSING_ENV,
    MINIAPP_CLIENT,
    MINIMUM_MINIAPP_VERSION,
    ChinaClientBoundaryMiddleware,
    _parse_calver,
    approved_release_registry_digest,
    china_processing_status,
)
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from api.legal_receipts import (
    TERMS_ACCEPTANCE_ACTION,
    TermsAcceptanceRequest,
    build_terms_receipt,
)
from scripts import cn_release_preflight as preflight


@pytest.fixture(autouse=True)
def explicit_test_processing_enable(monkeypatch) -> None:
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(ChinaClientBoundaryMiddleware)

    @app.get("/api/today")
    def today() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/auth/wechat/login")
    def wechat_login() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/status")
    def status() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/me/export")
    def export() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/auth/wechat/unlink")
    def unlink() -> dict[str, bool]:
        return {"ok": True}

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


def _approved_releases() -> str:
    return json.dumps([
        {
            "channel": CN_WEB_CLIENT,
            "client_version": "123456789abc",
            "source_id": "123456789abc",
            "source_commit": "123456789abc" + ("0" * 28),
            "notice_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
            "release_id": "edgeone:test",
        },
        {
            "channel": MINIAPP_CLIENT,
            "client_version": MINIMUM_MINIAPP_VERSION,
            "source_id": "abcdef123456",
            "source_commit": "abcdef123456" + ("0" * 28),
            "notice_version": TERMS_VERSION,
            "terms_digest": TERMS_CONTENT_DIGEST,
            "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
            "release_id": (
                f"wechat:robot-1:{MINIMUM_MINIAPP_VERSION}"
            ),
        },
    ])


_INVALID_CHANNEL_ENTRY_VECTORS = (
    pytest.param(
        CN_WEB_CLIENT,
        "0123456789ab",
        "fedcba654321",
        id="cn-web-version-source-mismatch",
    ),
    pytest.param(
        CN_WEB_CLIENT,
        "ABCDEF123456",
        "abcdef123456",
        id="cn-web-version-must-be-canonical-lowercase",
    ),
    pytest.param(
        MINIAPP_CLIENT,
        "not-a-calver",
        "fedcba654321",
        id="miniapp-invalid-calver",
    ),
    pytest.param(
        MINIAPP_CLIENT,
        "2026.07.99",
        "fedcba654321",
        id="miniapp-below-calver-floor",
    ),
    pytest.param(
        MINIAPP_CLIENT,
        "2026.13.1",
        "fedcba654321",
        id="miniapp-calendar-invalid-month",
    ),
)


def _registry_with_invalid_entry(
    channel: str,
    client_version: str,
    source_id: str,
) -> str:
    releases = json.loads(_approved_releases())
    releases.append({
        "channel": channel,
        "client_version": client_version,
        "source_id": source_id,
        "source_commit": source_id + ("0" * 28),
        "notice_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        "release_id": (
            "edgeone:invalid-test"
            if channel == CN_WEB_CLIENT
            else f"wechat:robot-1:{client_version}"
        ),
    })
    return json.dumps(releases)


def _cn_web_headers() -> dict[str, str]:
    return {
        "Origin": "https://praxys.cn",
        "X-Praxys-Client": CN_WEB_CLIENT,
        "X-Praxys-Client-Version": "123456789abc",
        "X-Praxys-Source-Sha": "123456789abc" + ("0" * 28),
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
        "X-Praxys-Source-Sha": "abcdef123456" + ("0" * 28),
        "X-Praxys-Notice-Version": TERMS_VERSION,
        "X-Praxys-Policy-Digest": TERMS_CONTENT_DIGEST,
        "X-Praxys-Api-Contract": CN_PRIVACY_CONTRACT_VERSION,
    }


def test_minimum_miniapp_privacy_floor_is_exact_calver() -> None:
    assert MINIMUM_MINIAPP_VERSION == "2026.08.2"
    assert _parse_calver(MINIMUM_MINIAPP_VERSION) == (2026, 8, 2)
    assert _parse_calver("2026.08.2-dev") is None
    assert _parse_calver("٢٠٢٦.٠٨.١") is None
    assert _parse_calver("2026.13.1") is None


def test_cn_web_requires_reviewed_build_and_notice(monkeypatch) -> None:
    monkeypatch.setenv(APPROVED_RELEASES_ENV, _approved_releases())
    client = _client()

    blocked = client.get(
        "/api/today",
        headers={"Origin": "https://praxys.cn"},
    )
    assert blocked.status_code == 428
    assert blocked.json()["detail"]["code"] == (
        "CLIENT_PRIVACY_UPDATE_REQUIRED"
    )

    allowed = client.get("/api/today", headers=_cn_web_headers())
    assert allowed.status_code == 200


def test_miniapp_requires_current_minimum_build(monkeypatch) -> None:
    monkeypatch.setenv(APPROVED_RELEASES_ENV, _approved_releases())
    client = _client()

    missing = client.post(
        "/api/auth/wechat/login",
        headers={
            "Referer": (
                "https://servicewechat.com/test-appid/1/page-frame.html"
            ),
        },
    )
    assert missing.status_code == 428

    old = client.post(
        "/api/auth/wechat/login",
        headers=_miniapp_headers(version="2026.07.99"),
    )
    assert old.status_code == 428
    assert old.json()["detail"]["minimum_version"] == (
        MINIMUM_MINIAPP_VERSION
    )

    allowed = client.post(
        "/api/auth/wechat/login",
        headers=_miniapp_headers(),
    )
    assert allowed.status_code == 200


def test_well_formed_but_unlisted_release_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv(APPROVED_RELEASES_ENV, _approved_releases())
    client = _client()
    headers = _cn_web_headers()
    headers["X-Praxys-Client-Version"] = "ffffffffffff"
    headers["X-Praxys-Source-Sha"] = "f" * 40

    response = client.get("/api/today", headers=headers)

    assert response.status_code == 428


def test_terms_receipts_use_server_verified_release_context(
    monkeypatch,
) -> None:
    monkeypatch.setenv(APPROVED_RELEASES_ENV, _approved_releases())
    client = _client()

    forged_headers = _cn_web_headers()
    forged_headers.pop("Origin")
    ordinary = client.post(
        "/api/terms-receipt-context",
        headers=forged_headers,
    )
    assert ordinary.status_code == 200
    assert ordinary.json() == {
        "action": TERMS_ACCEPTANCE_ACTION,
        "channel": "web",
        "client_version": None,
        "source_sha": None,
        "notice_version": None,
        "release_id": None,
    }

    cn_web = client.post(
        "/api/terms-receipt-context",
        headers=_cn_web_headers(),
    )
    assert cn_web.status_code == 200
    assert cn_web.json() == {
        "action": TERMS_ACCEPTANCE_ACTION,
        "channel": CN_WEB_CLIENT,
        "client_version": "123456789abc",
        "source_sha": "123456789abc" + ("0" * 28),
        "notice_version": TERMS_VERSION,
        "release_id": "edgeone:test",
    }

    miniapp = client.post(
        "/api/terms-receipt-context",
        headers=_miniapp_headers(),
    )
    assert miniapp.status_code == 200
    assert miniapp.json() == {
        "action": TERMS_ACCEPTANCE_ACTION,
        "channel": MINIAPP_CLIENT,
        "client_version": MINIMUM_MINIAPP_VERSION,
        "source_sha": "abcdef123456" + ("0" * 28),
        "notice_version": TERMS_VERSION,
        "release_id": (
            f"wechat:robot-1:{MINIMUM_MINIAPP_VERSION}"
        ),
    }


@pytest.mark.parametrize(
    ("channel", "client_version", "source_id"),
    _INVALID_CHANNEL_ENTRY_VECTORS,
)
def test_invalid_channel_entry_rejects_readiness_config(
    monkeypatch,
    channel: str,
    client_version: str,
    source_id: str,
) -> None:
    monkeypatch.setenv(
        APPROVED_RELEASES_ENV,
        _registry_with_invalid_entry(channel, client_version, source_id),
    )

    with pytest.raises(
        ValueError,
        match="approved release version is invalid for channel",
    ):
        china_processing_status()


@pytest.mark.parametrize(
    ("channel", "client_version", "source_id"),
    _INVALID_CHANNEL_ENTRY_VECTORS,
)
def test_invalid_channel_entry_rejects_whole_registry_for_requests(
    monkeypatch,
    channel: str,
    client_version: str,
    source_id: str,
) -> None:
    monkeypatch.setenv(
        APPROVED_RELEASES_ENV,
        _registry_with_invalid_entry(channel, client_version, source_id),
    )
    client = _client()
    headers = (
        _cn_web_headers()
        if channel == CN_WEB_CLIENT
        else _miniapp_headers()
    )
    headers["X-Praxys-Client-Version"] = client_version
    headers["X-Praxys-Source-Sha"] = source_id + ("0" * 28)

    response = client.get("/api/today", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == (
        "CN_CLIENT_REGISTRY_UNAVAILABLE"
    )


def test_missing_registry_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv(APPROVED_RELEASES_ENV, raising=False)
    client = _client()

    response = client.get("/api/today", headers=_cn_web_headers())

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == (
        "CN_CLIENT_REGISTRY_UNAVAILABLE"
    )


def test_china_processing_status_is_fail_closed_without_registry(
    monkeypatch,
) -> None:
    monkeypatch.delenv(APPROVED_RELEASES_ENV, raising=False)
    monkeypatch.delenv(DISABLE_CN_PROCESSING_ENV, raising=False)

    assert china_processing_status() == {
        "enabled": False,
        "disabled": True,
        "registry_configured": False,
        "approved_release_count": 0,
        "registry_sha256": None,
        "notice_version": TERMS_VERSION,
        "legal_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }


def test_china_processing_status_ignores_stale_registry_when_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv(APPROVED_RELEASES_ENV, "not-json-from-a-stale-release")
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")

    assert china_processing_status() == {
        "enabled": False,
        "disabled": True,
        "registry_configured": False,
        "approved_release_count": 0,
        "registry_sha256": None,
        "notice_version": TERMS_VERSION,
        "legal_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }


def test_china_processing_status_requires_registry_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.delenv(APPROVED_RELEASES_ENV, raising=False)
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "false")

    with pytest.raises(ValueError, match=APPROVED_RELEASES_ENV):
        china_processing_status()


def test_kill_switch_preserves_rights_routes(monkeypatch) -> None:
    monkeypatch.setenv(APPROVED_RELEASES_ENV, _approved_releases())
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")
    client = _client()

    blocked = client.get("/api/today", headers=_cn_web_headers())
    rights = client.get(
        "/api/me/export",
        headers={"Origin": "https://praxys.cn"},
    )
    unlink = client.post(
        "/api/auth/wechat/unlink",
        headers={"Referer": "https://servicewechat.com/test/1/page-frame.html"},
    )

    assert blocked.status_code == 503
    assert blocked.json()["detail"]["code"] == "CN_PROCESSING_DISABLED"
    assert rights.status_code == 200
    assert unlink.status_code == 200


def test_public_status_and_preflight_remain_available(monkeypatch) -> None:
    monkeypatch.delenv(APPROVED_RELEASES_ENV, raising=False)
    client = _client()

    status = client.get(
        "/api/status",
        headers={"Origin": "https://www.praxys.cn"},
    )
    assert status.status_code == 200

    preflight = client.options(
        "/api/today",
        headers={
            "Origin": "https://praxys.cn",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code != 428


def test_registry_and_request_source_sha_are_raw_lowercase_exact(
    monkeypatch,
) -> None:
    for invalid in ("A" * 40, "1" * 39, " " + ("1" * 40)):
        releases = json.loads(_approved_releases())
        releases[0]["source_commit"] = invalid
        monkeypatch.setenv(APPROVED_RELEASES_ENV, json.dumps(releases))
        with pytest.raises(
            ValueError,
            match="raw lowercase 40-character|surrounding whitespace",
        ):
            china_processing_status()

    monkeypatch.setenv(APPROVED_RELEASES_ENV, _approved_releases())
    client = _client()
    for invalid in ("A" * 40, "123456789abc", " " + ("1" * 40)):
        headers = _cn_web_headers()
        headers["X-Praxys-Source-Sha"] = invalid
        assert client.get("/api/today", headers=headers).status_code == 428


def test_runtime_registry_validation_matches_release_preflight(monkeypatch) -> None:
    valid = _approved_releases()
    _, preflight_digest = preflight.validate_registry(valid, disabled=True)
    monkeypatch.setenv(APPROVED_RELEASES_ENV, valid)
    assert approved_release_registry_digest() == "sha256:" + str(preflight_digest)

    def payload_with(mutate):
        payload = json.loads(valid)
        mutate(payload)
        return json.dumps(payload)

    def add_duplicate_provider(payload):
        duplicate = dict(payload[0])
        duplicate.update({
            "client_version": "bbbbbbbbbbbb",
            "source_id": "bbbbbbbbbbbb",
            "source_commit": "b" * 40,
        })
        payload.append(duplicate)

    invalid_payloads = (
        payload_with(lambda payload: payload[0].update({"unexpected": "value"})),
        payload_with(lambda payload: payload[0].update({"client_version": 123})),
        payload_with(
            lambda payload: payload[0].update(
                {"release_id": " edgeone:test"}
            )
        ),
        payload_with(lambda payload: payload[0].update({"release_id": "wechat:test"})),
        payload_with(
            lambda payload: payload[1].update(
                {"client_version": "2026.08.2-dev"}
            )
        ),
        payload_with(
            lambda payload: payload[0].update(
                {"terms_digest": TERMS_CONTENT_DIGEST.upper()}
            )
        ),
        payload_with(add_duplicate_provider),
        payload_with(lambda payload: payload[0].pop("api_contract_version")),
    )
    for raw in invalid_payloads:
        with pytest.raises(ValueError):
            preflight.validate_registry(raw, disabled=True)
        monkeypatch.setenv(APPROVED_RELEASES_ENV, raw)
        with pytest.raises(ValueError):
            china_processing_status()
