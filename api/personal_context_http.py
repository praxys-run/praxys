"""HTTP privacy boundary for personal-context endpoints."""
from __future__ import annotations

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_CONTEXT_PREFIX = "/api/personal-context"
_MCP_AUTH_PREFIX = "/api/auth/mcp"
_CACHE_CONTROL = "private, no-store"


def _is_context_path(path: str) -> bool:
    return path == _CONTEXT_PREFIX or path.startswith(
        f"{_CONTEXT_PREFIX}/"
    )


def _is_mcp_auth_path(path: str) -> bool:
    return path == _MCP_AUTH_PREFIX or path.startswith(
        f"{_MCP_AUTH_PREFIX}/"
    )


def _is_private_path(path: str) -> bool:
    return _is_context_path(path) or _is_mcp_auth_path(path)


class PersonalContextPrivacyMiddleware:
    """Apply private caching to context and opaque MCP credential paths."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope.get("type") != "http"
            or not _is_private_path(str(scope.get("path", "")))
        ):
            await self.app(scope, receive, send)
            return

        async def send_private(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = _CACHE_CONTROL
            await send(message)

        await self.app(scope, receive, send_private)


async def private_context_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> Response:
    """Avoid reflecting rejected private values in validation responses."""
    if not _is_private_path(request.url.path):
        return await request_validation_exception_handler(request, exc)
    detail = (
        "MCP_AUTH_INVALID"
        if _is_mcp_auth_path(request.url.path)
        else "PERSONAL_CONTEXT_INVALID"
    )
    return JSONResponse(
        status_code=422,
        content={"detail": detail},
        headers={"Cache-Control": _CACHE_CONTROL},
    )
