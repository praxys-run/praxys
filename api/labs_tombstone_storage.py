"""Restore-safe private storage for Labs withdrawal tombstones."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from api import feedback_storage

RETENTION_DAYS = 14
_PREFIX = "labs-deletions"


class TombstoneStorageError(RuntimeError):
    """Raised when a withdrawal marker cannot be durably stored."""


def _owner_key(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


def _blob_key(user_id: str, experiment_id: str) -> str:
    return f"{_PREFIX}/{_owner_key(user_id)}/{experiment_id}.json"


def _local_dir() -> Path:
    from db.session import get_data_dir

    return Path(get_data_dir()) / "labs_deletion_tombstones"


def store(user_id: str, experiment_id: str, deleted_at: datetime) -> None:
    """Durably write a tombstone before deleting active consent/results."""
    payload = json.dumps(
        {
            "user_id": user_id,
            "experiment_id": experiment_id,
            "deleted_at": deleted_at.isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    key = _blob_key(user_id, experiment_id)
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise TombstoneStorageError("Private Blob storage is unavailable")
        try:
            client.upload_blob(
                name=key,
                data=payload,
                overwrite=True,
            )
            return
        except Exception as exc:
            raise TombstoneStorageError(
                "Could not persist the Labs withdrawal tombstone"
            ) from exc
    path = _local_dir() / _owner_key(user_id) / f"{experiment_id}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError as exc:
        raise TombstoneStorageError(
            "Could not persist the Labs withdrawal tombstone"
        ) from exc


def iter_active(now: datetime | None = None) -> Iterator[dict[str, object]]:
    """Yield valid tombstones within the production backup-retention window."""
    cutoff = (now or datetime.utcnow()) - timedelta(days=RETENTION_DAYS)
    if feedback_storage.private_blob_enabled():
        client = feedback_storage.private_container_client()
        if client is None:
            raise TombstoneStorageError("Private Blob storage is unavailable")
        try:
            for item in client.list_blobs(name_starts_with=f"{_PREFIX}/"):
                blob = client.get_blob_client(item.name)
                payload = _decode(blob.download_blob().readall())
                if payload["deleted_at"] >= cutoff:
                    yield payload
                else:
                    blob.delete_blob()
            return
        except TombstoneStorageError:
            raise
        except Exception as exc:
            raise TombstoneStorageError(
                "Could not replay Labs withdrawal tombstones"
            ) from exc
    root = _local_dir()
    if not root.exists():
        return
    for path in root.glob("*/*.json"):
        payload = _decode(path.read_bytes())
        if payload["deleted_at"] >= cutoff:
            yield payload
        else:
            path.unlink(missing_ok=True)


def _decode(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
        deleted_at = datetime.fromisoformat(str(payload["deleted_at"]))
        user_id = str(payload["user_id"])
        experiment_id = str(payload["experiment_id"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise TombstoneStorageError("Invalid Labs withdrawal tombstone") from exc
    if not user_id or not experiment_id:
        raise TombstoneStorageError("Invalid Labs withdrawal tombstone")
    return {
        "user_id": user_id,
        "experiment_id": experiment_id,
        "deleted_at": deleted_at,
    }
