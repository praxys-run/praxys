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
    record_negative(user_id, reason, scope, target_id)
    store(value)
    return value


def complete(value: dict) -> None:
    store({**value, "completed_at": datetime.utcnow().isoformat()})


def expired(value: dict) -> bool:
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


def _authority_key(owner: str) -> str:
    return 'activity-dfa-authority/' + hashlib.sha256(owner.encode()).hexdigest() + '.json'


def authority_state(owner: str) -> dict:
    """Independent negative authority is not restored from the SQL backup.

    Absence is an empty negative journal, never positive processing authority.
    No completed negative marker expires automatically.
    """
    key = _authority_key(owner)
    empty = {'schema': 1, 'sequence': 0, 'deleted': False, 'events': {}, 'epoch': 'missing'}
    try:
        if feedback_storage.private_blob_enabled():
            from azure.core.exceptions import ResourceNotFoundError
            try:
                raw = feedback_storage.private_container_client().get_blob_client(key).download_blob().readall()
            except ResourceNotFoundError:
                return empty
        else:
            path = _root().parent / 'activity_dfa_authority' / key.split('/')[-1]
            if not path.exists():
                return empty
            raw = path.read_bytes()
        value = json.loads(raw)
        if (set(value) != set(empty) or value['schema'] != 1 or type(value['sequence']) is not int
                or type(value['deleted']) is not bool or not isinstance(value['events'], dict)):
            raise ValueError('invalid journal')
        return value
    except Exception as exc:
        raise StorageError('dfa_authority_unavailable') from exc


def record_negative(owner: str, operation: str, scope: str, target: str) -> dict:
    """Report durability failure consistently; no caller may acknowledge erasure."""
    try:
        return _record_negative(owner, operation, scope, target)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError('dfa_authority_write_unavailable') from exc


def _record_negative(owner: str, operation: str, scope: str, target: str) -> dict:
    """Append negative authority before exposing a SQL rights/source transition."""
    from db.account_lifecycle import account_lifecycle_lease
    import portalocker
    with account_lifecycle_lease(owner, timeout_seconds=30):
        key = _authority_key(owner)
        directory = _root().parent / 'activity_dfa_authority'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / key.split('/')[-1]
        # Local cross-process serialization; production additionally uses ETag
        # compare-and-swap so distinct hosts cannot lose a negative event.
        with portalocker.Lock(str(path) + '.lock', timeout=30):
            for attempt in range(5):
                client, etag = None, None
                if feedback_storage.private_blob_enabled():
                    from azure.core.exceptions import ResourceNotFoundError, ResourceModifiedError, ResourceExistsError
                    from azure.core import MatchConditions
                    client = feedback_storage.private_container_client().get_blob_client(key)
                    try:
                        etag = client.get_blob_properties().etag
                    except ResourceNotFoundError:
                        pass
                state = authority_state(owner)
                if state['epoch'] == 'missing':
                    state['epoch'] = str(uuid4())
                state['sequence'] += 1
                state['events'][hashlib.sha256(json.dumps([operation,scope,target],separators=(',',':')).encode()).hexdigest()] = {'sequence': state['sequence'], 'operation': operation,
                                               'scope': scope, 'target': target}
                if operation == 'account_deletion':
                    state['deleted'] = True
                if operation == 'restore':
                    state['epoch'] = str(uuid4())
                payload = json.dumps(state, separators=(',', ':'), sort_keys=True).encode()
                if client:
                    try:
                        kwargs = {'overwrite': etag is not None}
                        if etag:
                            kwargs.update(etag=etag, match_condition=MatchConditions.IfNotModified)
                        client.upload_blob(payload, **kwargs)
                        return state
                    except (ResourceModifiedError, ResourceExistsError):
                        continue
                temporary = path.with_suffix('.' + uuid4().hex + '.tmp')
                with temporary.open('xb') as stream:
                    os.chmod(temporary, 0o600)
                    stream.write(payload); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, path)
                fd = os.open(directory, os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                return state
    raise StorageError('dfa_authority_write_conflict')


def authority_revision(owner: str, origin: str, ref: dict, confirmation_id: str | None = None) -> str:
    from analysis.activity_dfa import digest
    state = authority_state(owner)
    if state['deleted']:
        raise StorageError('dfa_owner_deleted')
    if state['epoch'] == 'missing':
        raise StorageError('dfa_authority_missing')
    events = []
    for event in state['events'].values():
        scope, target = event['scope'], event['target']
        applies = (scope == 'owner' or scope == 'origin' and target == origin
                   or scope == 'activity' and target == ref['activity_id']
                   or scope == 'snapshot' and target == ref['snapshot_id']
                   or scope == 'confirmation' and target == confirmation_id)
        if applies:
            events.append(event)
    return digest([state['epoch'], sorted(events, key=lambda value: value['sequence'])])


def establish_for_explicit_manual_action(owner: str) -> None:
    """Create the independent store only during a fresh explicit owner action."""
    if authority_state(owner)['epoch'] == 'missing':
        record_negative(owner, 'authority_store_initialized', 'owner', owner)
