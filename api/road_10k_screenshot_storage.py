"""Road 10K screenshot fence and private-object deletion helpers.

The independent Trust blocker is intentionally still closed: no code path in
this module can upload or expose a screenshot.  Deletion remains implemented
so a future verified storage reference can be removed safely.
"""
from __future__ import annotations

from uuid import UUID

from api import feedback_storage


class Road10KScreenshotUnavailable(RuntimeError):
    """Screenshot capture is unavailable until the independent blocker closes."""


def screenshot_capture_available() -> bool:
    return False


def _validate_key(object_key: str) -> str:
    parts = object_key.split("/")
    if len(parts) == 3 and parts[0] == "road-10k" and parts[1] == "screenshots":
        UUID(parts[2].split(".", 1)[0])
        if "." not in parts[2] or parts[2].rsplit(".", 1)[1] not in {
            "png",
            "jpg",
            "webp",
        }:
            raise ValueError("invalid Road 10K screenshot object key")
        return object_key
    raise ValueError("invalid Road 10K screenshot object key")


def store_screenshot(*_args: object, **_kwargs: object) -> str:
    """Always fail closed; upload is technically unavailable."""
    raise Road10KScreenshotUnavailable(
        "Road 10K screenshots are unavailable pending private deletion verification"
    )


def delete_object(object_key: str) -> None:
    """Idempotently delete a previously referenced private object."""
    key = _validate_key(object_key)
    _delete_private(key)


def delete_manifest_object(object_key: str) -> None:
    """Delete a Road 10K or owner-scoped feedback object during replay."""
    key = object_key
    if key.startswith("road-10k/"):
        key = _validate_key(key)
    elif not key.startswith("feedback/"):
        raise ValueError("invalid private screenshot object key")
    _delete_private(key)


def _delete_private(key: str) -> None:
    try:
        feedback_storage.delete_private_object(key)
    except (OSError, ValueError) as exc:
        raise Road10KScreenshotUnavailable(
            "private screenshot deletion failed"
        ) from exc
