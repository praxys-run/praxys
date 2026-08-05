"""Shared Garmin transport-error classification helpers."""
from __future__ import annotations

import re


def garmin_http_status(error: BaseException) -> int | None:
    """Extract an HTTP status through wrapped requests and Garth errors."""
    seen: set[int] = set()
    pending: list[object] = [error]
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        for candidate in (
            getattr(current, "status_code", None),
            getattr(current, "status", None),
            getattr(getattr(current, "response", None), "status_code", None),
        ):
            if isinstance(candidate, int):
                return candidate
            if (
                isinstance(candidate, str)
                and candidate.strip().isdecimal()
            ):
                return int(candidate.strip())
        match = re.search(
            r"(?:API Error|client error|status(?:_code)?|HTTP(?: error)?)"
            r"\D*([1-5]\d{2})",
            str(current),
            re.IGNORECASE,
        )
        if match:
            return int(match.group(1))
        for attribute in ("error", "__cause__", "__context__"):
            nested = getattr(current, attribute, None)
            if nested is not None and id(nested) not in seen:
                pending.append(nested)
    return None
