"""Restore-safe private manifests for personal-context deletion."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from uuid import UUID, uuid4

from api import feedback_storage

RETENTION_DAYS = 14
_PREFIX = "personal-context-deletions"
_OPERATIONS = frozenset({
    "delete_owner_context",
    "delete_lineage",
    "delete_version",
    "purge_narrative",
})
_REASONS = frozenset({
    "withdrawal",
    "expiry",
    "retention",
    "account_deletion",
})
_STATUSES = frozenset({"requested", "completed"})


class DeletionManifestStorageError(RuntimeError):
    """Raised when a deletion manifest cannot be stored or replayed."""


def _owner_key(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def _normalized_job_id(job_id: str) -> str:
    try:
        return str(UUID(job_id))
    except (AttributeError, TypeError, ValueError) as exc:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion job identifier"
        ) from exc


def _blob_key(user_id: str, job_id: str) -> str:
    return f"{_PREFIX}/{_owner_key(user_id)}/{_normalized_job_id(job_id)}.json"


def _local_dir() -> Path:
    from db.session import get_data_dir

    return Path(get_data_dir()) / "personal_context_deletion_manifests"


def store_requested(
    *,
    job_id: str,
    user_id: str,
    operation: str,
    reason: str,
    requested_at: datetime,
    lineage_id: str | None = None,
    target_item_id: str | None = None,
) -> None:
    """Persist a deletion request before private database rows are changed."""
    _store(
        job_id=job_id,
        user_id=user_id,
        operation=operation,
        reason=reason,
        requested_at=requested_at,
        lineage_id=lineage_id,
        target_item_id=target_item_id,
        status="requested",
        completed_at=None,
    )


def mark_completed(
    *,
    job_id: str,
    user_id: str,
    operation: str,
    reason: str,
    requested_at: datetime,
    completed_at: datetime,
    lineage_id: str | None = None,
    target_item_id: str | None = None,
) -> None:
    """Replace a requested manifest with its payload-free completion state."""
    _store(
        job_id=job_id,
        user_id=user_id,
        operation=operation,
        reason=reason,
        requested_at=requested_at,
        lineage_id=lineage_id,
        target_item_id=target_item_id,
        status="completed",
        completed_at=completed_at,
    )


def _store(
    *,
    job_id: str,
    user_id: str,
    operation: str,
    reason: str,
    requested_at: datetime,
    lineage_id: str | None,
    target_item_id: str | None,
    status: str,
    completed_at: datetime | None,
) -> None:
    normalized_job_id = _normalized_job_id(job_id)
    _validate_target(
        user_id=user_id,
        operation=operation,
        reason=reason,
        status=status,
        lineage_id=lineage_id,
        target_item_id=target_item_id,
    )
    payload = json.dumps(
        {
            "job_id": normalized_job_id,
            "user_id": user_id,
            "operation": operation,
            "reason": reason,
            "lineage_id": lineage_id,
            "target_item_id": target_item_id,
            "status": status,
            "requested_at": _utc_naive(requested_at).isoformat(),
            "completed_at": (
                _utc_naive(completed_at).isoformat()
                if completed_at is not None
                else None
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    key = _blob_key(user_id, normalized_job_id)
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise DeletionManifestStorageError(
                "Private Blob storage is unavailable"
            )
        try:
            client.upload_blob(name=key, data=payload, overwrite=True)
            return
        except Exception as exc:
            raise DeletionManifestStorageError(
                "Could not persist the personal-context deletion manifest"
            ) from exc

    path = (
        _local_dir()
        / _owner_key(user_id)
        / f"{normalized_job_id}.json"
    )
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise DeletionManifestStorageError(
            "Could not persist the personal-context deletion manifest"
        ) from exc


def iter_active(now: datetime | None = None) -> Iterator[dict[str, object]]:
    """Yield valid manifests retained across the database backup window."""
    cutoff = _utc_naive(now or datetime.utcnow()) - timedelta(
        days=RETENTION_DAYS
    )
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise DeletionManifestStorageError(
                "Private Blob storage is unavailable"
            )
        try:
            for item in client.list_blobs(name_starts_with=f"{_PREFIX}/"):
                blob = client.get_blob_client(item.name)
                payload = _decode(blob.download_blob().readall())
                if payload["requested_at"] >= cutoff:
                    yield payload
                else:
                    blob.delete_blob()
            return
        except DeletionManifestStorageError:
            raise
        except Exception as exc:
            raise DeletionManifestStorageError(
                "Could not replay personal-context deletion manifests"
            ) from exc

    root = _local_dir()
    if not root.exists():
        return
    try:
        paths = list(root.glob("*/*.json"))
    except OSError as exc:
        raise DeletionManifestStorageError(
            "Could not list personal-context deletion manifests"
        ) from exc
    for path in paths:
        try:
            payload = _decode(path.read_bytes())
            if payload["requested_at"] >= cutoff:
                yield payload
            else:
                path.unlink(missing_ok=True)
        except DeletionManifestStorageError:
            raise
        except OSError as exc:
            raise DeletionManifestStorageError(
                "Could not replay personal-context deletion manifests"
            ) from exc


def _validate_target(
    *,
    user_id: str,
    operation: str,
    reason: str,
    status: str,
    lineage_id: str | None,
    target_item_id: str | None,
) -> None:
    if not isinstance(user_id, str) or not user_id or len(user_id) > 120:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion owner"
        )
    if operation not in _OPERATIONS or reason not in _REASONS:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion operation"
        )
    if status not in _STATUSES:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion status"
        )
    if operation == "delete_owner_context":
        valid = lineage_id is None and target_item_id is None
    elif operation == "delete_lineage":
        valid = bool(lineage_id) and target_item_id is None
    else:
        valid = bool(lineage_id) and bool(target_item_id)
    if not valid:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion target"
        )
    if lineage_id is not None and len(lineage_id) > 120:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion lineage"
        )
    if target_item_id is not None and len(target_item_id) > 120:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion item"
        )


def _decode(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
        job_id = _normalized_job_id(str(payload["job_id"]))
        user_id = str(payload["user_id"])
        operation = str(payload["operation"])
        reason = str(payload["reason"])
        lineage_id = payload.get("lineage_id")
        target_item_id = payload.get("target_item_id")
        status = str(payload["status"])
        requested_at = _utc_naive(
            datetime.fromisoformat(str(payload["requested_at"]))
        )
        raw_completed_at = payload.get("completed_at")
        completed_at = (
            _utc_naive(datetime.fromisoformat(str(raw_completed_at)))
            if raw_completed_at is not None
            else None
        )
    except (
        DeletionManifestStorageError,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
    ) as exc:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion manifest"
        ) from exc
    lineage_id = str(lineage_id) if lineage_id is not None else None
    target_item_id = (
        str(target_item_id) if target_item_id is not None else None
    )
    _validate_target(
        user_id=user_id,
        operation=operation,
        reason=reason,
        status=status,
        lineage_id=lineage_id,
        target_item_id=target_item_id,
    )
    if status == "completed" and completed_at is None:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion manifest"
        )
    if completed_at is not None and completed_at < requested_at:
        raise DeletionManifestStorageError(
            "Invalid personal-context deletion manifest"
        )
    return {
        "job_id": job_id,
        "user_id": user_id,
        "operation": operation,
        "reason": reason,
        "lineage_id": lineage_id,
        "target_item_id": target_item_id,
        "status": status,
        "requested_at": requested_at,
        "completed_at": completed_at,
    }


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
