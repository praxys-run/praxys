"""Road 10K screenshot fence and private-object deletion helpers.

The independent Trust blocker is intentionally still closed: no code path in
this module can upload or expose a screenshot.  Deletion remains implemented
so a future verified storage reference can be removed safely.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from api import feedback_storage


class Road10KScreenshotUnavailable(RuntimeError):
    """Screenshot capture is unavailable until the independent blocker closes."""


def screenshot_capture_available() -> bool:
    return False


def _validate_key(object_key: str) -> str:
    parts = object_key.split("/")
    if len(parts) != 3 or parts[0] != "road-10k" or parts[1] != "screenshots":
        raise ValueError("invalid Road 10K screenshot object key")
    UUID(parts[2].split(".", 1)[0])
    if "." not in parts[2] or parts[2].rsplit(".", 1)[1] not in {
        "png",
        "jpg",
        "webp",
    }:
        raise ValueError("invalid Road 10K screenshot object key")
    return object_key


def store_screenshot(*_args: object, **_kwargs: object) -> str:
    """Always fail closed; upload is technically unavailable."""
    raise Road10KScreenshotUnavailable(
        "Road 10K screenshots are unavailable pending private deletion verification"
    )


def delete_object(object_key: str) -> None:
    """Idempotently delete a previously referenced private object."""
    key = _validate_key(object_key)
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise Road10KScreenshotUnavailable("private screenshot storage unavailable")
        try:
            blob = client.get_blob_client(key)
            try:
                # Azure requires the snapshot flag to remove snapshots with
                # the base object. Versioned containers retain no separately
                # addressable Road 10K key; the provider's delete operation
                # removes all versions for this private reference.
                try:
                    blob.delete_blob(delete_snapshots=True)
                except TypeError:
                    blob.delete_blob()
            except Exception as exc:
                if "not found" not in str(exc).lower() and "resourceNotFound" not in str(exc):
                    raise
        except Exception as exc:
            raise Road10KScreenshotUnavailable(
                "private screenshot deletion failed"
            ) from exc
        return
    from db.session import get_data_dir

    path = Path(get_data_dir()) / "feedback_images" / key
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise Road10KScreenshotUnavailable(
            "private screenshot deletion failed"
        ) from exc
