"""HTTP privacy boundary for personal-context endpoints."""
from __future__ import annotations

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_CONTEXT_PREFIX = "/api/personal-context"
_CACHE_CONTROL = "private, no-store"


def _is_context_path(path: str) -> bool:
    return path == _CONTEXT_PREFIX or path.startswith(
        f"{_CONTEXT_PREFIX}/"
    )


class PersonalContextPrivacyMiddleware:
    """Apply private caching policy to every context response path."""

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
            or not _is_context_path(str(scope.get("path", "")))
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
    if not _is_context_path(request.url.path):
        return await request_validation_exception_handler(request, exc)
    return JSONResponse(
        status_code=422,
        content={"detail": "PERSONAL_CONTEXT_INVALID"},
        headers={"Cache-Control": _CACHE_CONTROL},
    )
