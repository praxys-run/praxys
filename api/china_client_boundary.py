"""Runtime privacy floor for mainland web and WeChat Miniapp clients."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
from urllib.parse import urlparse

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION

CN_WEB_CLIENT = "cn-web"
MINIAPP_CLIENT = "wechat-miniapp"
MINIMUM_MINIAPP_VERSION = "2026.08.1"
CN_PRIVACY_CONTRACT_VERSION = "cn-privacy-v1"
APPROVED_RELEASES_ENV = "PRAXYS_CN_APPROVED_RELEASES"
DISABLE_CN_PROCESSING_ENV = "PRAXYS_DISABLE_CN_PROCESSING"
VERIFIED_CHINA_RELEASE_SCOPE_KEY = "praxys_verified_china_release"

CN_WEB_ORIGINS = frozenset({
    "https://praxys.cn",
    "https://www.praxys.cn",
})
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
    ("POST", "/api/auth/wechat/unlink"),
    ("GET", "/api/me/export"),
    ("GET", "/api/settings/connections"),
    ("DELETE", "/api/me"),
})
_CONNECTION_DELETE_PATH = re.compile(
    r"^/api/settings/connections/[^/]+$"
)
_OWN_FEEDBACK_IMAGE_PATH = re.compile(
    r"^/api/me/feedback/\d+/image/\d+$"
)
_SOURCE_ID = re.compile(r"^[0-9a-f]{12}$")
_FULL_SOURCE_SHA = re.compile(r"^[0-9a-f]{40}$")
_PROVIDER_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CALVER = re.compile(r"^([0-9]{4})\.([0-9]{2})\.([0-9]{1,4})$")
_RELEASE_FIELDS = frozenset({
    "channel",
    "client_version",
    "source_id",
    "source_commit",
    "notice_version",
    "terms_digest",
    "api_contract_version",
    "release_id",
})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class ApprovedRelease:
    """Exact server-owned China client release identity."""

    channel: str
    client_version: str
    source_id: str
    source_commit: str
    notice_version: str
    terms_digest: str
    api_contract_version: str
    release_id: str


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


def _approved_releases() -> tuple[ApprovedRelease, ...]:
    raw = os.environ.get(APPROVED_RELEASES_ENV, "")
    if not raw.strip():
        raise ValueError(f"{APPROVED_RELEASES_ENV} is required")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{APPROVED_RELEASES_ENV} must be valid JSON") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{APPROVED_RELEASES_ENV} must be a non-empty list")

    releases: list[ApprovedRelease] = []
    identities: set[tuple[str, str, str]] = set()
    provider_release_ids: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("approved release entries must be objects")
        if set(item) != _RELEASE_FIELDS:
            raise ValueError("approved release entry fields must exactly match schema")
        if not all(isinstance(item[name], str) for name in _RELEASE_FIELDS):
            raise ValueError("approved release values must be strings")
        if any(item[name] != item[name].strip() for name in _RELEASE_FIELDS):
            raise ValueError(
                "approved release values must not contain surrounding whitespace"
            )

        release = ApprovedRelease(**{name: item[name] for name in _RELEASE_FIELDS})
        if release.channel not in {CN_WEB_CLIENT, MINIAPP_CLIENT}:
            raise ValueError("approved release channel is invalid")
        if _SOURCE_ID.fullmatch(release.source_id) is None:
            raise ValueError(
                "approved release source_id must be 12 lowercase hex characters"
            )
        if _FULL_SOURCE_SHA.fullmatch(release.source_commit) is None:
            raise ValueError(
                "approved release source_commit must be one raw lowercase "
                "40-character SHA"
            )
        if not release.source_commit.startswith(release.source_id):
            raise ValueError("approved release source_id must prefix source_commit")
        if _PROVIDER_RELEASE_ID.fullmatch(release.release_id) is None:
            raise ValueError("approved release provider release_id is invalid")
        expected_prefix = (
            "edgeone:" if release.channel == CN_WEB_CLIENT else "wechat:"
        )
        if (
            not release.release_id.startswith(expected_prefix)
            or len(release.release_id) == len(expected_prefix)
        ):
            raise ValueError(
                "approved release provider release_id does not match its channel"
            )
        if release.notice_version != TERMS_VERSION:
            raise ValueError("approved release notice version is not current")
        if release.terms_digest != TERMS_CONTENT_DIGEST:
            raise ValueError("approved release legal digest is not current")
        if release.api_contract_version != CN_PRIVACY_CONTRACT_VERSION:
            raise ValueError("approved release API contract is not current")
        if not _valid_release_identity(
            release.channel,
            release.client_version,
            release.source_id,
        ):
            raise ValueError("approved release version is invalid for channel")
        if (
            release.channel == MINIAPP_CLIENT
            and release.release_id
            != f"wechat:robot-1:{release.client_version}"
        ):
            raise ValueError(
                "approved Miniapp release_id must bind robot 1 and version"
            )
        identity = (
            release.channel,
            release.client_version,
            release.source_id,
        )
        if identity in identities:
            raise ValueError("approved release identity is duplicated")
        identities.add(identity)
        if release.release_id in provider_release_ids:
            raise ValueError("approved provider release_id is duplicated")
        provider_release_ids.add(release.release_id)
        releases.append(release)
    return tuple(releases)


def _release_context(release: ApprovedRelease) -> dict[str, str]:
    """Return the exact release and legal tuple carried across redirects."""

    return {
        "channel": release.channel,
        "client_version": release.client_version,
        "source_sha": release.source_commit,
        "notice_version": release.notice_version,
        "terms_digest": release.terms_digest,
        "api_contract_version": release.api_contract_version,
        "release_id": release.release_id,
    }


def revalidate_china_release_context(value: object) -> dict[str, str]:
    """Revalidate a previously verified China release against current policy."""

    if _strict_env_bool(DISABLE_CN_PROCESSING_ENV, default=True):
        raise ValueError("China processing is disabled")
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str)
        for key, item in value.items()
    ):
        raise ValueError("China release context is invalid")
    for release in _approved_releases():
        context = _release_context(release)
        if value == context:
            return context
    raise ValueError("China release context is stale or unapproved")


def is_cn_web_origin(origin: str) -> bool:
    """Return whether an exact origin belongs to the China web channel."""

    return origin.rstrip("/") in CN_WEB_ORIGINS


def approved_release_registry_digest() -> str:
    """Return a canonical non-secret digest of the validated registry."""
    raw = os.environ.get(APPROVED_RELEASES_ENV, "").strip()
    if not raw:
        raise ValueError(f"{APPROVED_RELEASES_ENV} is required")
    _approved_releases()
    payload = json.loads(raw)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _parse_calver(value: str) -> tuple[int, int, int] | None:
    match = _CALVER.fullmatch(value)
    if match is None:
        return None
    year, month, micro = (int(part) for part in match.groups())
    if not 1 <= month <= 12:
        return None
    return year, month, micro


_MINIMUM_MINIAPP_CALVER = _parse_calver(MINIMUM_MINIAPP_VERSION)
if _MINIMUM_MINIAPP_CALVER is None:
    raise ValueError(
        "Miniapp minimum version must be an exact three-part CalVer"
    )


def _valid_release_identity(
    channel: str,
    client_version: str,
    source_id: str,
) -> bool:
    """Validate the channel-specific identity shared by config and claims."""
    if channel not in {CN_WEB_CLIENT, MINIAPP_CLIENT}:
        return False
    if _SOURCE_ID.fullmatch(source_id) is None:
        return False
    if channel == CN_WEB_CLIENT:
        return client_version == source_id

    build = _parse_calver(client_version)
    return build is not None and build >= _MINIMUM_MINIAPP_CALVER


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
    # Referer that app code cannot override:
    # https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html
    # The user-agent fallback covers clients that omit that Referer in transit.
    user_agent = headers.get("user-agent", "").lower()
    return "micromessenger" in user_agent and not headers.get("origin")


def _valid_claim_shape(client: str, headers: Headers) -> bool:
    client_version = headers.get("x-praxys-client-version", "").strip()
    source_commit = headers.get("x-praxys-source-sha", "")
    if headers.get("x-praxys-client", "") != client:
        return False
    if _FULL_SOURCE_SHA.fullmatch(source_commit) is None:
        return False
    if headers.get("x-praxys-notice-version", "") != TERMS_VERSION:
        return False
    if headers.get("x-praxys-policy-digest", "").lower() != TERMS_CONTENT_DIGEST:
        return False
    if (
        headers.get("x-praxys-api-contract", "")
        != CN_PRIVACY_CONTRACT_VERSION
    ):
        return False
    return True


def _approved_release_for_claim(
    client: str,
    headers: Headers,
) -> ApprovedRelease | None:
    releases = _approved_releases()
    if not _valid_claim_shape(client, headers):
        return None
    client_version = headers.get("x-praxys-client-version", "").strip()
    source_commit = headers.get("x-praxys-source-sha", "")
    return next(
        (
            release
            for release in releases
            if release.channel == client
            and release.client_version == client_version
            and release.source_commit == source_commit
        ),
        None,
    )


def _matches_approved_release(client: str, headers: Headers) -> bool:
    return _approved_release_for_claim(client, headers) is not None


def china_processing_status() -> dict[str, object]:
    """Return non-secret effective China release-control state."""
    disabled = _strict_env_bool(DISABLE_CN_PROCESSING_ENV, default=True)
    if disabled:
        return {
            "enabled": False,
            "disabled": True,
            "registry_configured": False,
            "approved_release_count": 0,
            "registry_sha256": None,
            "notice_version": TERMS_VERSION,
            "legal_digest": TERMS_CONTENT_DIGEST,
            "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        }
    if not os.environ.get(APPROVED_RELEASES_ENV, "").strip():
        raise ValueError(
            f"{APPROVED_RELEASES_ENV} is required when China processing is enabled"
        )
    releases = _approved_releases()
    return {
        "enabled": not disabled,
        "disabled": disabled,
        "registry_configured": True,
        "approved_release_count": len(releases),
        "registry_sha256": approved_release_registry_digest(),
        "notice_version": TERMS_VERSION,
        "legal_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }


def _blocked_response(client: str) -> JSONResponse:
    detail: dict[str, str] = {
        "code": "CLIENT_PRIVACY_UPDATE_REQUIRED",
        "client": client,
        "message": "Update Praxys before continuing.",
        "notice_version": TERMS_VERSION,
    }
    if client == MINIAPP_CLIENT:
        detail["minimum_version"] = MINIMUM_MINIAPP_VERSION
    return JSONResponse(
        status_code=428,
        content={"detail": detail},
        headers={"Cache-Control": "no-store"},
    )


def _service_unavailable_response(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": code,
                "message": message,
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
    """Reject notice-incapable China clients before route processing."""

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
        origin = headers.get("origin", "").rstrip("/")
        client = ""
        if origin in CN_WEB_ORIGINS:
            client = CN_WEB_CLIENT
        elif _is_miniapp_request(path, headers):
            client = MINIAPP_CLIENT
        if not client:
            await self.app(scope, receive, send)
            return

        if _is_rights_route(method, path):
            await self.app(scope, receive, send)
            return

        try:
            if _strict_env_bool(DISABLE_CN_PROCESSING_ENV, default=True):
                await _service_unavailable_response(
                    "CN_PROCESSING_DISABLED",
                    "Praxys China processing is temporarily unavailable.",
                )(scope, receive, send)
                return
            release = _approved_release_for_claim(client, headers)
        except ValueError:
            await _service_unavailable_response(
                "CN_CLIENT_REGISTRY_UNAVAILABLE",
                "Praxys China client verification is unavailable.",
            )(scope, receive, send)
            return

        if release is None:
            await _blocked_response(client)(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state[VERIFIED_CHINA_RELEASE_SCOPE_KEY] = _release_context(release)
        await self.app(scope, receive, send)
