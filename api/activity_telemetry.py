"""Minimize activity identifiers at local HTTP telemetry emission boundaries."""
from __future__ import annotations

import logging
import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import Span


_ACTIVITY_DETAIL_URL = re.compile(r"(/api/history/)([\s\S]+)")


def redact_activity_url(value: str) -> str:
    """Template detail paths, including decoded or unmatched trailing segments."""
    def template(match: re.Match[str]) -> str:
        """Keep the known route shape without any identifier-bearing suffix."""
        detail = "/detail" if re.search(r"/detail(?:[/?#\s]|$)", match[2]) else ""
        return match[1] + "{activity_id}" + detail

    redacted, count = _ACTIVITY_DETAIL_URL.subn(template, value)
    return re.split(r"[?#]", redacted, maxsplit=1)[0] if count else value


def sanitize_activity_span(span: Span | None, scope: dict[str, Any]) -> None:
    """Minimize server-span attributes without modifying the ASGI request scope."""
    if span is None or not span.is_recording():
        return
    for key, value in tuple(span.attributes.items()):
        if isinstance(value, str):
            redacted = redact_activity_url(value)
            if redacted != value:
                span.set_attribute(key, redacted)
    name = redact_activity_url(span.name)
    if name != span.name:
        span.update_name(name)


class _ActivityAccessLogFilter(logging.Filter):
    """Sanitize Uvicorn URL arguments before formatting or OTel log capture."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Retain request method, status and the access formatter's tuple shape."""
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_activity_url(value) if isinstance(value, str) else value
                for value in record.args
            )
        return True


def configure_activity_access_logging() -> None:
    """Install the activity-only boundary once, before telemetry handlers attach."""
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, _ActivityAccessLogFilter) for item in logger.filters):
        logger.addFilter(_ActivityAccessLogFilter())
