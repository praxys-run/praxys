"""Fail-closed request boundary for the China web and WeChat channels."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import re
from urllib.parse import urlparse

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION

CN_WEB_CLIENT = "cn-web"
MINIAPP_CLIENT = "wechat-miniapp"
MINIMUM_MINIAPP_VERSION = "2026.08.2"
CN_PRIVACY_CONTRACT_VERSION = "cn-privacy-v2"
DISABLE_CN_PROCESSING_ENV = "PRAXYS_DISABLE_CN_PROCESSING"
DISABLE_MINIAPP_PROCESSING_ENV = "PRAXYS_DISABLE_MINIAPP_PROCESSING"
CHINA_CLIENT_CONTEXT_SCOPE_KEY = "praxys_china_client_context"

CN_WEB_ORIGINS = frozenset({
    "https://praxys.cn",
    "https://www.praxys.cn",
})
CHINA_CLIENT_CHANNELS = frozenset({CN_WEB_CLIENT, MINIAPP_CLIENT})
_PUBLIC_API_PATHS = frozenset({
    "/api/health",
    "/api/health/ready",
    "/api/public/config",
    "/api/status",
    "/api/status/incidents",
    "/api/version",
})
_RIGHTS_API_ROUTES = frozenset({
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/wechat/unlink"),
    ("DELETE", "/api/labs/environment-response"),
    ("GET", "/api/me/export"),
    ("GET", "/api/settings/connections"),
    ("POST", "/api/me/accept-terms"),
    ("DELETE", "/api/me"),
})
_CONNECTION_DELETE_PATH = re.compile(r"^/api/settings/connections/[^/]+$")
_OWN_FEEDBACK_IMAGE_PATH = re.compile(
    r"^/api/me/feedback/\d+/image/\d+$"
)
_RELEASE_CALVER = re.compile(
    r"^([0-9]{4})\.([0-9]{2})\.([0-9]{1,4})$"
)
_DEVELOPMENT_CALVER = re.compile(
    r"^([0-9]{4})\.([0-9]{2})\.([0-9]{2})\."
    r"([1-9][0-9]{0,9})-([0-9a-f]{7})$"
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_LEGACY_CONTEXT_FIELDS = frozenset({
    "client_version",
    "source_sha",
    "release_id",
})


@dataclass(frozen=True)
class ChinaClientContext:
    """Server-classified channel and current compatibility contract."""

    channel: str
    notice_version: str
    terms_digest: str
    api_contract_version: str


def _strict_env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean")


def china_processing_enabled() -> bool:
    """Return the effective China-processing state, failing closed."""

    try:
        return not _strict_env_bool(
            DISABLE_CN_PROCESSING_ENV,
            default=True,
        )
    except ValueError:
        return False


def miniapp_processing_enabled() -> bool:
    """Return the effective Miniapp-processing state, failing closed."""

    try:
        return not _strict_env_bool(
            DISABLE_MINIAPP_PROCESSING_ENV,
            default=True,
        )
    except ValueError:
        return False


def _client_context(channel: str) -> dict[str, str]:
    if channel not in CHINA_CLIENT_CHANNELS:
        raise ValueError("China client channel is invalid")
    return asdict(ChinaClientContext(
        channel=channel,
        notice_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST,
        api_contract_version=CN_PRIVACY_CONTRACT_VERSION,
    ))


def revalidate_china_client_context(value: object) -> dict[str, str]:
    """Revalidate signed China context after an external redirect."""

    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError("China client context is invalid")
    channel = value.get("channel")
    if not isinstance(channel, str):
        raise ValueError("China client context is invalid")
    expected = _client_context(channel)
    if (
        set(value) - set(expected) - _LEGACY_CONTEXT_FIELDS
        or any(value.get(key) != item for key, item in expected.items())
    ):
        raise ValueError("China client context is stale")
    processing_enabled = (
        miniapp_processing_enabled()
        if channel == MINIAPP_CLIENT
        else china_processing_enabled()
    )
    if not processing_enabled:
        raise ValueError(f"{channel} processing is disabled")
    return expected


def is_cn_web_origin(origin: str) -> bool:
    """Return whether an exact origin belongs to the China web channel."""

    return origin.rstrip("/") in CN_WEB_ORIGINS


def _parse_calver(value: str) -> tuple[int, int, int] | None:
    match = _RELEASE_CALVER.fullmatch(value)
    if match is None:
        return None
    year, month, micro = (int(part) for part in match.groups())
    if not 1 <= month <= 12:
        return None
    return year, month, micro


def _parse_miniapp_version(value: str) -> tuple[int, int, int] | None:
    """Return the comparable prefix for release or robot-5 versions."""

    release = _parse_calver(value)
    if release is not None:
        return release
    development = _DEVELOPMENT_CALVER.fullmatch(value)
    if development is None:
        return None
    year, month, day = (
        int(part) for part in development.groups()[:3]
    )
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    return year, month, day


_MINIMUM_MINIAPP_CALVER = _parse_calver(MINIMUM_MINIAPP_VERSION)
if _MINIMUM_MINIAPP_CALVER is None:
    raise ValueError(
        "Miniapp minimum version must be an exact three-part CalVer"
    )


def _is_miniapp_request(path: str, headers: Headers) -> bool:
    if path == "/api/auth/wechat" or path.startswith("/api/auth/wechat/"):
        return True
    if headers.get("x-praxys-client", "") == MINIAPP_CLIENT:
        return True

    referer = headers.get("referer", "")
    try:
        if urlparse(referer).hostname == "servicewechat.com":
            return True
    except ValueError:
        pass

    # Official wx.request traffic has a platform-managed servicewechat.com
    # Referer. The user-agent fallback covers clients that omit that Referer
    # in transit.
    user_agent = headers.get("user-agent", "").lower()
    return "micromessenger" in user_agent and not headers.get("origin")


def _has_current_contract(channel: str, headers: Headers) -> bool:
    """Check only the minimal stale-client compatibility contract.

    Legacy source, web-version, and provider-release headers are deliberately
    ignored. Miniapp version remains a compatibility floor until the deferred
    Miniapp launch has its own reviewed lifecycle.
    """

    if headers.get("x-praxys-client", "") != channel:
        return False
    if headers.get("x-praxys-notice-version", "") != TERMS_VERSION:
        return False
    if headers.get("x-praxys-policy-digest", "") != TERMS_CONTENT_DIGEST:
        return False
    if (
        headers.get("x-praxys-api-contract", "")
        != CN_PRIVACY_CONTRACT_VERSION
    ):
        return False
    if channel != MINIAPP_CLIENT:
        return True
    build = _parse_miniapp_version(
        headers.get("x-praxys-client-version", "").strip()
    )
    return build is not None and build >= _MINIMUM_MINIAPP_CALVER


def china_processing_status() -> dict[str, object]:
    """Return non-secret effective China compatibility-control state."""

    disabled = not china_processing_enabled()
    return {
        "enabled": not disabled,
        "disabled": disabled,
        "notice_version": TERMS_VERSION,
        "legal_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }


def miniapp_processing_status() -> dict[str, bool]:
    """Return the non-secret, fail-closed Miniapp switch state."""

    disabled = not miniapp_processing_enabled()
    return {
        "enabled": not disabled,
        "disabled": disabled,
    }


def _blocked_response(channel: str) -> JSONResponse:
    detail: dict[str, str] = {
        "code": "CLIENT_PRIVACY_UPDATE_REQUIRED",
        "client": channel,
        "message": "Update Praxys before continuing.",
        "notice_version": TERMS_VERSION,
    }
    if channel == MINIAPP_CLIENT:
        detail["minimum_version"] = MINIMUM_MINIAPP_VERSION
    return JSONResponse(
        status_code=428,
        content={"detail": detail},
        headers={"Cache-Control": "no-store"},
    )


def _service_unavailable_response(channel: str) -> JSONResponse:
    miniapp = channel == MINIAPP_CLIENT
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": (
                    "MINIAPP_PROCESSING_DISABLED"
                    if miniapp
                    else "CN_PROCESSING_DISABLED"
                ),
                "message": (
                    "Praxys Miniapp processing is temporarily unavailable."
                    if miniapp
                    else
                    "Praxys China processing is temporarily unavailable."
                ),
            }
        },
        headers={"Cache-Control": "no-store"},
    )


def _is_rights_route(method: str, path: str) -> bool:
    if (method, path) in _RIGHTS_API_ROUTES:
        return True
    return (
        method == "DELETE"
        and _CONNECTION_DELETE_PATH.fullmatch(path) is not None
    ) or (
        method == "GET"
        and _OWN_FEEDBACK_IMAGE_PATH.fullmatch(path) is not None
    )


class ChinaClientBoundaryMiddleware:
    """Enforce the China switch and minimal stale-client contract."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "")).upper()
        path = str(scope.get("path", ""))
        if (
            method == "OPTIONS"
            or not path.startswith("/api/")
            or path in _PUBLIC_API_PATHS
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        channel = ""
        if _is_miniapp_request(path, headers):
            channel = MINIAPP_CLIENT
        else:
            origin = headers.get("origin", "").rstrip("/")
            if origin in CN_WEB_ORIGINS:
                channel = CN_WEB_CLIENT
        if not channel:
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state[CHINA_CLIENT_CONTEXT_SCOPE_KEY] = _client_context(channel)

        if _is_rights_route(method, path):
            await self.app(scope, receive, send)
            return

        processing_enabled = (
            miniapp_processing_enabled()
            if channel == MINIAPP_CLIENT
            else china_processing_enabled()
        )
        if not processing_enabled:
            await _service_unavailable_response(channel)(
                scope,
                receive,
                send,
            )
            return
        if not _has_current_contract(channel, headers):
            await _blocked_response(channel)(scope, receive, send)
            return

        await self.app(scope, receive, send)
