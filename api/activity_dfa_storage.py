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
SCOPES = {"owner", "activity", "snapshot", "confirmation", "rights", "metadata_proof"}
REASONS = {"withdrawal", "account_deletion", "source_deletion", "source_changed", "cancelled", "reauthorized"}


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
        legacy = {"id", "user_id", "scope", "target_id", "reason", "requested_at", "completed_at"}
        versioned = legacy | {"version", "activity_id", "rights_generation", "suppressed"}
        if set(value) not in (legacy, versioned):
            raise ValueError()
        if set(value) == versioned:
            if value['version'] != 2 or type(value['rights_generation']) is not int or value['rights_generation'] < 1 or type(value['suppressed']) is not bool or not isinstance(value['activity_id'],str) or not 1 <= len(value['activity_id']) <= 100:
                raise ValueError()
        elif value.get('scope') in ('rights','metadata_proof'):
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


def request_rights(user_id: str, activity: str, generation: int, suppressed: bool, reason: str, *, scope='rights', target_id=None) -> dict:
    value = {'id':str(uuid4()),'user_id':user_id,'scope':scope,'target_id':target_id or activity,
        'reason':reason,'requested_at':datetime.utcnow().isoformat(),'completed_at':None,
        'version':2,'activity_id':activity,'rights_generation':generation,'suppressed':suppressed}
    store(value)
    return value


def complete(value: dict) -> None:
    store({**value, "completed_at": datetime.utcnow().isoformat()})


def expired(value: dict) -> bool:
    # Owner erasure is an irreversible admission/read fence, including later
    # provider completions after SQL restore. Keep its payload-free marker.
    if value['scope']=='owner':
        return False
    return (value["completed_at"] is not None and
            datetime.fromisoformat(value["completed_at"]) < datetime.utcnow() - timedelta(days=14))


def discard(value: dict) -> None:
    """Only completed manifests beyond backup retention may be removed."""
    if not expired(value):
        return
    try:
        if feedback_storage.private_blob_enabled():
            client = feedback_storage.private_container_client()
            if client is None:
                raise StorageError("dfa_storage_unavailable")
            client.get_blob_client(_key(value)).delete_blob()
        else:
            (_root() / _key(value).removeprefix(PREFIX + "/")).unlink(missing_ok=True)
    except Exception as exc:
        raise StorageError("dfa_storage_unavailable") from exc


def iter_manifests(user_id: str | None = None):
    """Stream stored records, including expired ones so background work is bounded."""
    owner = hashlib.sha256(user_id.encode()).hexdigest() if user_id is not None else None
    prefix = PREFIX + "/" + (owner + "/" if owner else "")
    try:
        if feedback_storage.private_blob_enabled():
            client = feedback_storage.private_container_client()
            if client is None:
                raise StorageError("dfa_storage_unavailable")
            for item in client.list_blobs(name_starts_with=prefix):
                value = _validate(json.loads(client.get_blob_client(item.name).download_blob().readall()))
                if _key(value) != item.name or (user_id is not None and value["user_id"] != user_id):
                    raise StorageError("dfa_manifest_invalid")
                yield value
        else:
            paths = (_root() / owner).glob("*.json") if owner else _root().glob("*/*.json")
            for path in paths:
                value = _validate(json.loads(path.read_bytes()))
                if path != _root() / _key(value).removeprefix(PREFIX + "/") or (user_id is not None and value["user_id"] != user_id):
                    raise StorageError("dfa_manifest_invalid")
                yield value
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError("dfa_storage_unavailable") from exc


def iter_active(user_id: str | None = None):
    for value in iter_manifests(user_id):
        if expired(value):
            discard(value)
        else:
            yield value
