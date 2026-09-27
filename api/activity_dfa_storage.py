"""Payload-free DFA erasure manifests in the existing private storage account."""
from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from api import feedback_storage

PREFIX = "activity-dfa-deletions"
SCOPES = {"owner", "activity", "snapshot", "confirmation"}
REASONS = {"withdrawal", "account_deletion", "source_deletion", "source_changed"}


class StorageError(RuntimeError):
    pass


def _root() -> Path:
    from db.session import get_data_dir
    return Path(get_data_dir()) / "activity_dfa_deletion_manifests"


def _key(value: dict) -> str:
    owner = hashlib.sha256(value["user_id"].encode()).hexdigest()
    return f"{PREFIX}/{owner}/{value['id']}.json"


def _validate(value: dict) -> dict:
    try:
        if set(value) != {"id", "user_id", "scope", "target_id", "reason", "requested_at", "completed_at"}:
            raise ValueError()
        UUID(value["id"])
        if not isinstance(value["user_id"], str) or not 1 <= len(value["user_id"]) <= 120:
            raise ValueError()
        if value["scope"] not in SCOPES or value["reason"] not in REASONS:
            raise ValueError()
        if not isinstance(value["target_id"], str) or not 1 <= len(value["target_id"]) <= 120:
            raise ValueError()
        datetime.fromisoformat(value["requested_at"])
        if value["completed_at"] is not None:
            datetime.fromisoformat(value["completed_at"])
        return value
    except (KeyError, TypeError, ValueError) as exc:
        raise StorageError("dfa_manifest_invalid") from exc


def store(value: dict) -> None:
    _validate(value)
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
    try:
        if feedback_storage.private_blob_enabled():
            client = feedback_storage.private_container_client()
            if client is None:
                raise StorageError("dfa_storage_unavailable")
            client.upload_blob(name=_key(value), data=payload, overwrite=True)
        else:
            path = _root() / _key(value).removeprefix(PREFIX + "/")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f".{uuid4().hex}.tmp")
            try:
                with temporary.open("xb") as stream:
                    os.chmod(temporary, 0o600)
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
                fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            finally:
                temporary.unlink(missing_ok=True)
    except Exception as exc:
        raise StorageError("dfa_storage_unavailable") from exc


def request(user_id: str, scope: str, target_id: str, reason: str) -> dict:
    value = {"id": str(uuid4()), "user_id": user_id, "scope": scope, "target_id": target_id,
             "reason": reason, "requested_at": datetime.utcnow().isoformat(), "completed_at": None}
    store(value)
    return value


def complete(value: dict) -> None:
    store({**value, "completed_at": datetime.utcnow().isoformat()})


def iter_active():
    cutoff = datetime.utcnow() - timedelta(days=14)
    try:
        if feedback_storage.private_blob_enabled():
            client = feedback_storage.private_container_client()
            if client is None:
                raise StorageError("dfa_storage_unavailable")
            for item in client.list_blobs(name_starts_with=PREFIX + "/"):
                blob = client.get_blob_client(item.name)
                value = _validate(json.loads(blob.download_blob().readall()))
                if value["completed_at"] is None or datetime.fromisoformat(value["completed_at"]) >= cutoff:
                    yield value
                else:
                    blob.delete_blob()
        else:
            for path in _root().glob("*/*.json"):
                value = _validate(json.loads(path.read_bytes()))
                if value["completed_at"] is None or datetime.fromisoformat(value["completed_at"]) >= cutoff:
                    yield value
                else:
                    path.unlink(missing_ok=True)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError("dfa_storage_unavailable") from exc
