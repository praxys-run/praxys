"""Restore-safe, payload-free Road 10K deletion manifests.

Manifests live outside the primary database backup boundary and contain only
references needed for idempotent deletion.  Evaluation or screenshot bytes
are never copied into a marker.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Callable, Iterator, Mapping
from uuid import UUID, uuid4

from api import feedback_storage

MARKER_RETENTION_DAYS = 14
_PREFIX = "road-10k/deletion-manifests"
_last_replay_status = "not_run"


class Road10KDeletionStorageError(RuntimeError):
    """A marker could not be staged, replayed, or completed."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _job_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise Road10KDeletionStorageError("invalid deletion marker id") from exc


def _local_dir() -> Path:
    from db.session import get_data_dir

    return Path(get_data_dir()) / "road_10k_deletion_manifests"


def _key(job_id: str) -> str:
    return f"{_PREFIX}/{job_id}.json"


def _validate_manifest(manifest: Mapping[str, object]) -> None:
    required = {
        "job_id",
        "owner_id",
        "stage_id",
        "reason",
        "evaluation_ids",
        "screenshot_keys",
        "requested_at",
        "completed_at",
        "status",
    }
    if set(manifest) != required:
        raise Road10KDeletionStorageError("invalid Road 10K deletion marker")
    try:
        UUID(str(manifest["job_id"]))
    except (TypeError, ValueError) as exc:
        raise Road10KDeletionStorageError("invalid Road 10K deletion marker id") from exc
    if (
        not isinstance(manifest["owner_id"], str)
        or not manifest["owner_id"]
        or len(manifest["owner_id"]) > 36
        or not isinstance(manifest["stage_id"], str)
        or not manifest["stage_id"]
        or len(manifest["stage_id"]) > 80
    ):
        raise Road10KDeletionStorageError("invalid Road 10K deletion owner")
    if manifest["reason"] not in {"withdrawal", "account_deletion", "retention"}:
        raise Road10KDeletionStorageError("invalid Road 10K deletion reason")
    if manifest["status"] not in {"requested", "completed"}:
        raise Road10KDeletionStorageError("invalid Road 10K deletion status")
    for key in ("evaluation_ids", "screenshot_keys"):
        values = manifest[key]
        if not isinstance(values, list) or any(
            not isinstance(item, str) or not item for item in values
        ):
            raise Road10KDeletionStorageError("invalid Road 10K deletion targets")


def _store(manifest: Mapping[str, object]) -> None:
    _validate_manifest(manifest)
    payload = json.dumps(
        dict(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    key = _key(str(manifest["job_id"]))
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise Road10KDeletionStorageError("private marker storage unavailable")
        try:
            client.upload_blob(name=key, data=payload, overwrite=True)
            return
        except Exception as exc:
            raise Road10KDeletionStorageError(
                "could not persist Road 10K deletion marker"
            ) from exc
    path = _local_dir() / f"{manifest['job_id']}.json"
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
        raise Road10KDeletionStorageError(
            "could not persist Road 10K deletion marker"
        ) from exc


def stage_manifest(
    *,
    owner_id: str,
    stage_id: str,
    reason: str,
    evaluation_ids: list[str],
    screenshot_keys: list[str],
    requested_at: datetime,
    job_id: str | None = None,
) -> dict[str, object]:
    """Write a requested marker before deleting any DB/object data."""
    manifest: dict[str, object] = {
        "job_id": _job_id(job_id),
        "owner_id": owner_id,
        "stage_id": stage_id,
        "reason": reason,
        "evaluation_ids": list(evaluation_ids),
        "screenshot_keys": list(screenshot_keys),
        "requested_at": _utc(requested_at).isoformat(),
        "completed_at": None,
        "status": "requested",
    }
    _store(manifest)
    return manifest


def mark_completed(manifest: Mapping[str, object], completed_at: datetime) -> None:
    """Persist the completion state without changing target references."""
    completed = dict(manifest)
    completed["status"] = "completed"
    completed["completed_at"] = _utc(completed_at).isoformat()
    _store(completed)


def _decode(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Road10KDeletionStorageError("invalid Road 10K deletion marker") from exc
    if not isinstance(value, dict):
        raise Road10KDeletionStorageError("invalid Road 10K deletion marker")
    _validate_manifest(value)
    return value


def iter_active(now: datetime | None = None) -> Iterator[dict[str, object]]:
    """Yield markers within the actual restore horizon and expire older ones."""
    cutoff = _utc(now or datetime.now(timezone.utc)) - timedelta(
        days=MARKER_RETENTION_DAYS
    )
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise Road10KDeletionStorageError("private marker storage unavailable")
        try:
            for item in client.list_blobs(name_starts_with=f"{_PREFIX}/"):
                blob = client.get_blob_client(item.name)
                value = _decode(blob.download_blob().readall())
                requested = datetime.fromisoformat(
                    str(value["requested_at"]).replace("Z", "+00:00")
                )
                if requested >= cutoff:
                    yield value
                else:
                    blob.delete_blob()
        except Road10KDeletionStorageError:
            raise
        except Exception as exc:
            raise Road10KDeletionStorageError(
                "could not enumerate Road 10K deletion markers"
            ) from exc
        return
    root = _local_dir()
    if not root.exists():
        return
    try:
        paths = list(root.glob("*.json"))
        for path in paths:
            value = _decode(path.read_bytes())
            requested = datetime.fromisoformat(
                str(value["requested_at"]).replace("Z", "+00:00")
            )
            if requested >= cutoff:
                yield value
            else:
                path.unlink(missing_ok=True)
    except Road10KDeletionStorageError:
        raise
    except OSError as exc:
        raise Road10KDeletionStorageError(
            "could not enumerate Road 10K deletion markers"
        ) from exc


def replay_manifests(
    *,
    delete_object: Callable[[str], None],
    delete_evaluation: Callable[[str, Mapping[str, object]], None],
    now: datetime | None = None,
) -> int:
    """Replay every active marker before Road 10K traffic is considered ready."""
    global _last_replay_status
    completed = 0
    try:
        for manifest in iter_active(now):
            for key in manifest["screenshot_keys"]:
                delete_object(str(key))
            for evaluation_id in manifest["evaluation_ids"]:
                delete_evaluation(str(evaluation_id), manifest)
            mark_completed(manifest, now or datetime.now(timezone.utc))
            completed += 1
    except Exception as exc:
        _last_replay_status = "blocked"
        raise Road10KDeletionStorageError(
            "Road 10K deletion marker replay failed"
        ) from exc
    _last_replay_status = "ready"
    return completed


def replay_status() -> str:
    """Return only a bounded replay status for readiness/operations."""
    return _last_replay_status


def marker_contains_payload(manifest: Mapping[str, object]) -> bool:
    """Test helper used by storage checks; payload fields are never permitted."""
    return any(
        key in manifest
        for key in {"payload", "screenshot_bytes", "evaluation_payload", "image"}
    )
