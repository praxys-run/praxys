"""Data sync endpoints — per-user sync with encrypted credentials.

Credentials are read from user_connections (encrypted in DB). Falls back to
environment variables when auth is disabled (local dev).
"""
import contextlib
import json
import hashlib
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Iterable, Iterator
from contextvars import ContextVar, Token
from datetime import date, datetime, timedelta, timezone

import portalocker
import requests

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from api.auth import (
    get_current_user_id,
    get_data_user_id,
    require_write_access,
)
from api.env_compat import getenv_compat
from api.views import utc_isoformat
from db.session import get_db
from sync.garmin_errors import garmin_http_status

router = APIRouter()


class SyncRequest(BaseModel):
    """Optional request body for sync endpoints."""
    from_date: str | None = None

    @field_validator("from_date")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        if v is not None:
            from datetime import datetime as dt
            try:
                dt.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("from_date must be in YYYY-MM-DD format")
        return v


# Per-user sync status: {user_id: {source: {status, last_sync, error}}}
_sync_status: dict[str, dict[str, dict]] = {}
_sync_lock = threading.Lock()

_DEFAULT_SOURCES = ["garmin", "strava", "stryd", "oura", "coros"]
_background_sync_context: ContextVar[tuple[str, Session] | None] = ContextVar(
    "praxys_background_sync_context",
    default=None,
)


class BackgroundProcessingAuthorizationLost(RuntimeError):
    """Raised when an in-flight background sync loses processing authority."""


def _begin_background_sync_execution(
    user_id: str,
    db: Session,
) -> Token[tuple[str, Session] | None]:
    """Enter the shared commit-fencing context for one background sync."""
    return _background_sync_context.set((user_id, db))


def _end_background_sync_execution(
    token: Token[tuple[str, Session] | None],
) -> None:
    """Leave the shared background-sync commit-fencing context."""
    _background_sync_context.reset(token)


def _require_background_processing_authorized(
    user_id: str,
    db: Session,
) -> None:
    """Fence background work on current Terms and China-channel switches."""
    from api.legal_receipts import user_background_processing_authorized

    if not user_background_processing_authorized(db, user_id):
        raise BackgroundProcessingAuthorizationLost(
            "SYNC_BACKGROUND_PROCESSING_NOT_AUTHORIZED"
        )


def _require_background_sync_commit_authorized(
    user_id: str,
    db: Session,
) -> None:
    """Fence provider commits made inside manual or scheduled sync work."""
    context = _background_sync_context.get()
    if context is not None and context[0] == user_id and context[1] is db:
        _require_background_processing_authorized(user_id, db)


def _ensure_user_active_for_sync(user_id: str, db: Session) -> None:
    """Abort a sync before commit if the account disappeared or is deactivated.

    ``flush()`` pushes pending sync writes into the current transaction before
    the active-user check. On SQLite this acquires the writer lock, so account
    deletion cannot flip/delete the user between the check and the following
    commit; if deletion already won, the check sees the inactive/missing user
    and the caller rolls the pending writes back.
    """
    from db.models import User

    db.flush()

    user_exists = db.query(User.id).filter(
        User.id == user_id,
        User.is_active == True,  # noqa: E712
    ).first()
    if not user_exists:
        raise RuntimeError("SYNC_USER_DELETED")


def _commit_background_sync_provider_changes(
    user_id: str,
    db: Session,
) -> None:
    """Preserve deletion fencing and authorize provider-internal commits."""
    _ensure_user_active_for_sync(user_id, db)
    _require_background_sync_commit_authorized(user_id, db)
    db.commit()


def _commit_authorized_background_sync_changes(
    user_id: str,
    db: Session,
) -> None:
    """Commit sync data only while background work remains allowed."""
    _ensure_user_active_for_sync(user_id, db)
    _require_background_processing_authorized(user_id, db)
    db.commit()


def _get_user_status(user_id: str) -> dict[str, dict]:
    """Get or create sync status dict for a user."""
    with _sync_lock:
        if user_id not in _sync_status:
            _sync_status[user_id] = {
                s: {"status": "idle", "last_sync": None, "error": None}
                for s in _DEFAULT_SOURCES
            }
        return _sync_status[user_id]


def _activity_ids_needing_environment(
    user_id: str,
    activity_ids: Iterable[str],
    db: Session,
) -> set[str]:
    """Return activity IDs whose environment observation can still be filled."""
    from db.models import Activity

    candidate_ids = {
        str(activity_id)
        for activity_id in activity_ids
        if activity_id
    }
    if not candidate_ids:
        return set()

    existing = db.query(Activity).filter(
        Activity.user_id == user_id,
        Activity.activity_id.in_(sorted(candidate_ids)),
    ).all()
    needed = set(candidate_ids)
    for activity in existing:
        temperature = activity.temperature_c
        humidity = activity.relative_humidity_pct
        source = activity.environment_source
        if temperature is None and humidity is None:
            continue
        if temperature is not None and humidity is not None and source is None:
            continue
        needed.discard(activity.activity_id)
    return needed


def _exception_status_code(exc: BaseException) -> int | None:
    """Extract an HTTP status from an exception response or provider message."""
    return garmin_http_status(exc)


def _get_data_dir() -> str:
    return os.environ.get(
        "DATA_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "data"),
    )


def _garmin_token_root() -> str:
    """Return the legacy plaintext token root used before issue #61."""
    return os.path.abspath(
        os.path.join(os.path.dirname(_get_data_dir()), "sync", ".garmin_tokens")
    )


def _garmin_token_dir(
    user_id: str,
    credential_generation: str | None = None,
) -> str:
    """Return a legacy per-user Garmin tokenstore path.

    New code stores encrypted token bundles in ``user_connections``. These
    paths remain only so the startup migration and invalidation paths can
    remove token files created by older releases.

    ``user_id`` is an authenticated account ID (a UUID), never free-form input,
    but the path is validated defensively: the tokenstore isolation is a
    security boundary, so a malformed ID must not be able to traverse out of
    the per-user root into another user's store (or elsewhere on disk).
    """
    root = _garmin_token_root()
    path = os.path.normpath(os.path.join(root, user_id))
    # Require the result to be a direct child of the token root: this rejects
    # empty/"."/absolute/".."-containing ids that would escape or collapse to
    # the root itself. The ``startswith`` prefix check confines the normalized
    # path to the token root (defence against path traversal).
    if os.path.dirname(path) != root or not path.startswith(root + os.sep):
        raise ValueError(f"Invalid user_id for Garmin token directory: {user_id!r}")
    if credential_generation is None:
        return path
    digest = hashlib.sha256(
        credential_generation.encode("utf-8")
    ).hexdigest()
    return os.path.join(path, "generations", digest)


_GARMIN_TOKEN_PROCESS_LOCKS = tuple(
    threading.RLock() for _ in range(64)
)
_GARMIN_MIGRATION_PROCESS_LOCK = threading.Lock()
_garmin_token_lease_depth = threading.local()


def _garmin_token_lock_path(user_id: str) -> str:
    """Return the stable lock file for every tokenstore owned by one user."""
    _garmin_token_dir(user_id)
    root = os.path.abspath(
        os.path.join(
            os.path.dirname(_get_data_dir()),
            "sync",
            ".garmin_token_locks",
        )
    )
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return os.path.join(root, f"{digest}.lock")


@contextlib.contextmanager
def _garmin_tokenstore_lease(user_id: str) -> Iterator[None]:
    """Serialize bound Garmin token access across threads and workers.

    Callers that also lock database rows must enter this lease first.
    """
    lock_path = _garmin_token_lock_path(user_id)
    process_lock = _GARMIN_TOKEN_PROCESS_LOCKS[
        int(hashlib.sha256(lock_path.encode("utf-8")).hexdigest()[:8], 16)
        % len(_GARMIN_TOKEN_PROCESS_LOCKS)
    ]
    process_lock.acquire()
    try:
        depths = getattr(_garmin_token_lease_depth, "paths", None)
        if depths is None:
            depths = {}
            _garmin_token_lease_depth.paths = depths
        current_depth = int(depths.get(lock_path, 0))
        if current_depth:
            depths[lock_path] = current_depth + 1
            try:
                yield
            finally:
                depths[lock_path] = current_depth
            return

        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        depths[lock_path] = 1
        try:
            with portalocker.Lock(
                lock_path,
                mode="a",
                timeout=float("inf"),
            ):
                yield
        finally:
            depths.pop(lock_path, None)
    finally:
        process_lock.release()


def _read_legacy_garmin_tokens(path: str) -> str | None:
    """Read one current-format legacy token file without network I/O."""
    from db.garmin_tokens import validate_garmin_tokens

    token_path = os.path.join(path, "garmin_tokens.json")
    if not os.path.isfile(token_path) or os.path.islink(token_path):
        return None
    with open(token_path, encoding="utf-8") as handle:
        return validate_garmin_tokens(handle.read())


def _merge_recreated_legacy_root(root: str, quarantine: str) -> None:
    """Move post-crash old-worker writes into the resumable quarantine."""
    import shutil

    if os.path.islink(quarantine) or not os.path.isdir(quarantine):
        raise RuntimeError(
            f"Refusing unsafe Garmin token migration quarantine: {quarantine}"
        )
    for entry in os.scandir(root):
        if entry.is_symlink():
            raise RuntimeError(
                f"Refusing unsafe recreated Garmin token entry: {entry.path}"
            )
        destination = os.path.join(quarantine, entry.name)
        if os.path.lexists(destination):
            if os.path.islink(destination):
                raise RuntimeError(
                    f"Refusing unsafe quarantined Garmin token entry: {destination}"
                )
            if os.path.isdir(destination):
                shutil.rmtree(destination)
            else:
                os.unlink(destination)
        os.replace(entry.path, destination)
    os.rmdir(root)


def _garmin_token_migration_lock_path() -> str:
    """Return the cross-worker migration lock outside the blocked token root."""
    return os.path.abspath(
        os.path.join(
            os.path.dirname(_get_data_dir()),
            "sync",
            ".garmin_token_migration.lock",
        )
    )


def migrate_legacy_garmin_tokenstores() -> dict[str, int]:
    """Serialize startup migration and quiesce every known legacy user."""
    from contextlib import ExitStack

    from db.models import User
    from db.session import SessionLocal

    lock_path = _garmin_token_migration_lock_path()
    with _GARMIN_MIGRATION_PROCESS_LOCK:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with portalocker.Lock(
            lock_path,
            mode="a",
            timeout=float("inf"),
        ):
            root = _garmin_token_root()
            quarantine = root + ".migration"
            with ExitStack() as leases:
                locked_user_ids: set[str] = set()
                while True:
                    discovered_user_ids: set[str] = set()
                    with SessionLocal() as db:
                        discovered_user_ids.update(
                            str(user_id)
                            for (user_id,) in db.query(User.id).all()
                        )
                    for candidate_root in (root, quarantine):
                        if not os.path.isdir(candidate_root):
                            continue
                        discovered_user_ids.update(
                            entry.name
                            for entry in os.scandir(candidate_root)
                            if entry.is_dir(follow_symlinks=False)
                        )
                    new_user_ids = discovered_user_ids - locked_user_ids
                    if not new_user_ids:
                        break
                    for user_id in sorted(new_user_ids):
                        leases.enter_context(_garmin_tokenstore_lease(user_id))
                        locked_user_ids.add(user_id)
                return _migrate_legacy_garmin_tokenstores_locked()


def _migrate_legacy_garmin_tokenstores_locked() -> dict[str, int]:
    """Encrypt legacy Garmin token files and remove every plaintext store.

    This runs during API startup before the scheduler. Valid tokens are
    committed to their current ``UserConnection`` before their directory is
    deleted. Orphaned, partial, and stale-generation stores are deleted so a
    failed or abandoned login cannot leave bearer tokens on persistent disk.
    """
    import shutil
    from db.connection_credentials import connection_credentials_generation
    from db.crypto import get_vault
    from db.garmin_tokens import (
        GarminTokenAccessError,
        load_garmin_tokens,
        stage_garmin_tokens,
    )
    from db.models import UserConnection
    from db.session import SessionLocal

    root = _garmin_token_root()
    quarantine = root + ".migration"
    result = {"migrated": 0, "removed": 0}
    if os.path.lexists(root):
        if os.path.islink(root):
            raise RuntimeError(f"Refusing symlinked Garmin token root: {root}")
        if os.path.isfile(root):
            with open(root, "rb") as handle:
                is_blocker = handle.read() == _GARMIN_LEGACY_BLOCKER
            if not is_blocker:
                raise RuntimeError(
                    f"Refusing unexpected Garmin token root file: {root}"
                )
            if not os.path.lexists(quarantine):
                return result
        elif os.path.isdir(root):
            if os.path.lexists(quarantine):
                _merge_recreated_legacy_root(root, quarantine)
            else:
                os.replace(root, quarantine)
            _write_legacy_garmin_root_blocker()
        else:
            raise RuntimeError(f"Refusing unsafe Garmin token root: {root}")
    else:
        _write_legacy_garmin_root_blocker()
        if not os.path.lexists(quarantine):
            return result

    if os.path.islink(quarantine) or not os.path.isdir(quarantine):
        raise RuntimeError(
            f"Refusing unsafe Garmin token migration quarantine: {quarantine}"
        )
    legacy_root = quarantine

    for filename in (
        "oauth1_token.json",
        "oauth2_token.json",
        "garmin_tokens.json",
    ):
        shared_path = os.path.join(legacy_root, filename)
        if os.path.lexists(shared_path):
            os.unlink(shared_path)
            result["removed"] += 1

    user_entries = list(os.scandir(legacy_root))
    for entry in user_entries:
        if not entry.is_dir(follow_symlinks=False):
            if entry.is_symlink():
                raise RuntimeError(
                    f"Refusing unsafe Garmin tokenstore entry: {entry.path}"
                )
            continue
        user_id = entry.name
        with _garmin_tokenstore_lease(user_id):
            if not os.path.isdir(entry.path):
                continue
            with SessionLocal() as db:
                connection = db.query(UserConnection).filter(
                    UserConnection.user_id == user_id,
                    UserConnection.platform == "garmin",
                ).one_or_none()
                if connection is not None:
                    encrypted = connection.encrypted_garmin_tokens
                    wrapped = connection.wrapped_token_dek
                    stored_generation = connection.garmin_token_generation
                    token_metadata = (
                        encrypted,
                        wrapped,
                        stored_generation,
                        connection.tokens_updated_at,
                    )
                    if any(value is not None for value in token_metadata) and not all(
                        value is not None for value in token_metadata
                    ):
                        raise RuntimeError(
                            "Garmin token encryption metadata is incomplete "
                            f"for user {user_id}"
                        )
                    generation = connection_credentials_generation(connection)
                    generation_digest = hashlib.sha256(
                        generation.encode("utf-8")
                    ).hexdigest()
                    candidates = (
                        os.path.join(
                            entry.path,
                            "generations",
                            generation_digest,
                        ),
                        entry.path,
                    )
                    serialized = None
                    for candidate in candidates:
                        try:
                            serialized = _read_legacy_garmin_tokens(candidate)
                        except (
                            GarminTokenAccessError,
                            json.JSONDecodeError,
                            TypeError,
                            ValueError,
                        ):
                            logger.warning(
                                "Discarding malformed legacy Garmin tokens "
                                "for user %s",
                                user_id,
                            )
                        if serialized is not None:
                            break
                    if serialized is not None:
                        if not get_vault().is_persistent:
                            raise RuntimeError(
                                "Refusing to delete plaintext Garmin tokens "
                                "without a persistent encryption key"
                            )
                        stage_garmin_tokens(
                            db,
                            user_id=user_id,
                            serialized_tokens=serialized,
                            expected_generation=generation,
                        )
                        db.commit()
                        result["migrated"] += 1
                    elif encrypted is not None:
                        load_garmin_tokens(db, user_id=user_id)
            shutil.rmtree(entry.path)
            result["removed"] += 1
    shutil.rmtree(legacy_root)
    if result["migrated"] or result["removed"]:
        logger.info(
            "Garmin token migration complete: %d encrypted, %d plaintext "
            "stores removed",
            result["migrated"],
            result["removed"],
        )
    return result


def publish_garmin_tokens(
    db: Session,
    *,
    user_id: str,
    credential_generation: str,
    serialized_tokens: str,
    expected_serialized_tokens: str | None,
    allowed_statuses: tuple[str, ...],
) -> bool:
    """Encrypt refreshed tokens after rechecking the credential generation."""
    from db.connection_credentials import (
        ConnectionGenerationChanged,
    )
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens

    with _garmin_tokenstore_lease(user_id):
        try:
            current_tokens = load_garmin_tokens(
                db,
                user_id=user_id,
                expected_generation=credential_generation,
                allowed_statuses=allowed_statuses,
            )
            if current_tokens == serialized_tokens:
                _commit_background_sync_provider_changes(user_id, db)
                return True
            if current_tokens != expected_serialized_tokens:
                db.rollback()
                return False
            stage_garmin_tokens(
                db,
                user_id=user_id,
                serialized_tokens=serialized_tokens,
                expected_generation=credential_generation,
                allowed_statuses=allowed_statuses,
            )
        except ConnectionGenerationChanged:
            db.rollback()
            return False
        _commit_background_sync_provider_changes(user_id, db)
    return True


def _persist_garmin_token_state_after_rollback(
    db: Session,
    *,
    user_id: str,
    credential_generation: str,
    token_state: dict[str, object],
    allowed_statuses: tuple[str, ...],
) -> bool:
    """Persist the latest client tokens after sync data has been rolled back."""
    client = token_state.get("client")
    if client is None:
        return True
    committed_tokens = token_state.get("committed_tokens")
    pending_tokens = token_state.get("pending_tokens")
    final_tokens = (
        pending_tokens
        if isinstance(pending_tokens, str)
        else _serialize_garmin_tokens(client)
    )
    if final_tokens == committed_tokens:
        return True
    return publish_garmin_tokens(
        db,
        user_id=user_id,
        credential_generation=credential_generation,
        serialized_tokens=final_tokens,
        expected_serialized_tokens=(
            committed_tokens if isinstance(committed_tokens, str) else None
        ),
        allowed_statuses=allowed_statuses,
    )


_GARMIN_LEGACY_BLOCKER = b"praxys-encrypted-garmin-tokenstore-v1\n"


def _write_legacy_garmin_root_blocker() -> None:
    """Atomically create the blocker that prevents every plaintext tokenstore."""
    root = _garmin_token_root()
    parent = os.path.dirname(root)
    os.makedirs(parent, exist_ok=True)
    temporary = os.path.join(
        parent,
        f".garmin_tokens.blocker-{os.getpid()}-{secrets.token_hex(8)}",
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(temporary, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(_GARMIN_LEGACY_BLOCKER)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, root)
        with contextlib.suppress(OSError):
            parent_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def _block_legacy_garmin_tokenstore(user_id: str) -> None:
    """Replace the legacy root with a file that blocks every old worker."""
    import shutil

    _garmin_token_dir(user_id)
    root = _garmin_token_root()
    if os.path.lexists(root):
        if os.path.islink(root):
            raise OSError(f"Refusing symlinked Garmin token root: {root}")
        if os.path.isfile(root):
            with open(root, "rb") as handle:
                if handle.read() == _GARMIN_LEGACY_BLOCKER:
                    return
            raise OSError(f"Refusing unexpected Garmin token root file: {root}")
        if not os.path.isdir(root):
            raise OSError(f"Refusing unsafe Garmin token root: {root}")
        user_path = _garmin_token_dir(user_id)
        if os.path.lexists(user_path):
            if os.path.islink(user_path):
                raise OSError(
                    f"Refusing symlinked Garmin tokenstore path: {user_path}"
                )
            if os.path.isdir(user_path):
                shutil.rmtree(user_path)
            else:
                os.unlink(user_path)
        if any(os.scandir(root)):
            raise OSError(
                "Legacy Garmin token migration is incomplete; refusing a "
                "writable token root"
            )
        os.rmdir(root)
    _write_legacy_garmin_root_blocker()


def _clear_garmin_bound_tokens(user_id: str) -> None:
    """Block legacy disk tokens while preserving in-flight memory state."""
    with _garmin_tokenstore_lease(user_id):
        _block_legacy_garmin_tokenstore(user_id)


def clear_garmin_tokens(
    user_id: str,
    db: Session | None = None,
    *,
    block_legacy: bool = True,
) -> None:
    """Remove encrypted and legacy Garmin OAuth tokens for a user.

    Call whenever cached tokens should no longer be trusted: credential
    rotation on connect, explicit disconnect, or user deletion. Database
    changes are staged on ``db`` for the caller's transaction. Residual
    filesystem cleanup raises on failure so bearer tokens cannot be silently
    left behind.
    """
    import shutil
    from db import session as db_session
    from db.garmin_tokens import clear_stored_garmin_tokens

    owned_db = None
    if db is None and db_session.SessionLocal is not None:
        owned_db = db_session.SessionLocal()
        db = owned_db
    try:
        with _garmin_tokenstore_lease(user_id):
            with _pending_mfa_lock:
                for key in [
                    key
                    for key in _pending_garmin_mfa
                    if key[0] == user_id
                ]:
                    _pending_garmin_mfa.pop(key, None)
                for key in [
                    key
                    for key in _completed_garmin_tokens
                    if key[0] == user_id
                ]:
                    _completed_garmin_tokens.pop(key, None)
                    _completed_garmin_token_created.pop(key, None)
            path = _garmin_token_dir(user_id)
            if os.path.lexists(path):
                try:
                    if os.path.islink(path):
                        raise OSError(f"Refusing symlinked tokenstore path: {path}")
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.unlink(path)
                except OSError:
                    logger.exception(
                        "Failed to clear legacy Garmin tokenstore for user %s at %s",
                        user_id,
                        path,
                    )
                    raise
            if block_legacy:
                _block_legacy_garmin_tokenstore(user_id)
            if db is not None:
                clear_stored_garmin_tokens(db, user_id=user_id)
                if owned_db is not None:
                    owned_db.commit()
    finally:
        if owned_db is not None:
            owned_db.close()


# Pending interactive Garmin MFA logins, keyed by user and attempt ID.
#
# Garmin's MFA challenge state (the SSO session mid-handshake) lives on the
# live garminconnect client instance, not in any serializable token, so the
# client that started the login must be the one that completes it. We park it
# here between the credential submit and the MFA-code submit. This is
# process-local: an MFA verify must reach the same worker that began the
# login. That's fine for the single-worker deployment, and the pending entry
# self-expires within minutes regardless (Garmin MFA codes are short-lived).
_pending_garmin_mfa: dict[tuple[str, str], dict] = {}
_completed_garmin_tokens: dict[tuple[str, str], str] = {}
_completed_garmin_token_created: dict[tuple[str, str], float] = {}
_pending_mfa_lock = threading.Lock()
_GARMIN_MFA_TTL_SEC = 300
_garmin_prune_timer: threading.Timer | None = None


def _prune_expired_mfa() -> None:
    """Forget pending and completed interactive logins older than the TTL."""
    cutoff = time.time() - _GARMIN_MFA_TTL_SEC
    with _pending_mfa_lock:
        stale_pending = [
            key
            for key, pending in _pending_garmin_mfa.items()
            if pending["created"] < cutoff
        ]
        for key in stale_pending:
            _pending_garmin_mfa.pop(key, None)
        stale_completed = [
            key
            for key in _completed_garmin_tokens
            if _completed_garmin_token_created.get(key, 0) < cutoff
        ]
        for key in stale_completed:
            _completed_garmin_tokens.pop(key, None)
            _completed_garmin_token_created.pop(key, None)


def _schedule_garmin_login_prune() -> None:
    """Ensure abandoned login state is pruned even without another request."""
    global _garmin_prune_timer

    def prune_and_rearm() -> None:
        global _garmin_prune_timer
        _prune_expired_mfa()
        with _pending_mfa_lock:
            _garmin_prune_timer = None
            needs_rearm = bool(
                _pending_garmin_mfa
                or _completed_garmin_tokens
            )
        if needs_rearm:
            _schedule_garmin_login_prune()

    with _pending_mfa_lock:
        if (
            _garmin_prune_timer is not None
            and _garmin_prune_timer.is_alive()
        ):
            return
        timer = threading.Timer(
            _GARMIN_MFA_TTL_SEC + 1,
            prune_and_rearm,
        )
        timer.daemon = True
        _garmin_prune_timer = timer
    timer.start()


def discard_garmin_login_tokens(
    user_id: str,
    login_attempt_id: str,
) -> None:
    """Forget one pending or completed interactive login."""
    key = (user_id, login_attempt_id)
    with _pending_mfa_lock:
        _pending_garmin_mfa.pop(key, None)
        _completed_garmin_tokens.pop(key, None)
        _completed_garmin_token_created.pop(key, None)


# garminconnect tries login strategies in order (mobile, widget, portal).
# The ``widget+cffi`` strategy handles MFA, but the DI token it mints is
# rejected by the Garmin API tier (401 "Token is not active" on
# /userprofile-service/socialProfile) — upstream
# cyberjunky/python-garminconnect issue #369. The ``portal`` strategy mints a
# token the API accepts *and* handles MFA, so we force it for every login.
# Validated end-to-end against a live MFA-enabled garmin.cn account: portal
# token → socialProfile / user-settings 200.
_GARMIN_API_REJECTED_STRATEGIES = frozenset(
    {"mobile+cffi", "mobile+requests", "widget+cffi"}
)


def _force_portal_login_strategy(client) -> None:
    """Skip the login strategies whose DI tokens the API tier rejects (#369).

    Leaves only ``portal+cffi`` / ``portal+requests`` — confirmed to mint
    API-accepted tokens for MFA accounts. Best-effort: if the library ever
    drops ``skip_strategies`` we log and fall back to the default chain.
    """
    try:
        client.client.skip_strategies = set(_GARMIN_API_REJECTED_STRATEGIES)
    except Exception:
        logger.warning(
            "Could not force Garmin portal login strategy; using default chain",
            exc_info=True,
        )


def _serialize_garmin_tokens(client) -> str:
    """Return a validated in-memory garminconnect token bundle."""
    from db.garmin_tokens import validate_garmin_tokens

    return validate_garmin_tokens(client.client.dumps())


_GARMIN_DIRECT_TOKEN_MIN_LENGTH = 513


def _garmin_login_argument(serialized_tokens: str | None) -> str:
    """Force garminconnect's in-memory branch and bypass ``GARMINTOKENS``.

    garminconnect 0.3.x treats strings longer than 512 characters as serialized
    tokens and shorter strings as filesystem paths. A padded empty JSON object
    safely fails token loading and falls through to credentials without setting
    a tokenstore path, so the library cannot read or write plaintext files.
    """
    value = serialized_tokens or "{}"
    if len(value) < _GARMIN_DIRECT_TOKEN_MIN_LENGTH:
        value += " " * (_GARMIN_DIRECT_TOKEN_MIN_LENGTH - len(value))
    return value


def begin_garmin_login(
    user_id: str,
    creds: dict,
) -> tuple[str, str]:
    """Start an interactive Garmin login, transparently handling MFA.

    Returns the status and an opaque server-side attempt ID. The status is
    ``"connected"`` when login completes or ``"mfa_required"`` when Garmin
    demands a code, in which case the live client is parked in
    ``_pending_garmin_mfa`` for :func:`complete_garmin_mfa`.
    Raises ``GarminConnect*`` errors on authentication/connection failure.

    Unlike the lazy background-sync login, this runs synchronously while the
    user is present so an MFA code can be prompted for. Completed token bundles
    remain only in process memory until the matching credentials are committed.
    """
    from garminconnect import Garmin

    is_cn = bool(creds.get("is_cn", False))
    _prune_expired_mfa()
    _clear_garmin_bound_tokens(user_id)
    attempt_id = secrets.token_urlsafe(24)

    client = Garmin(
        creds["email"], creds["password"], is_cn=is_cn, return_on_mfa=True,
    )
    _force_portal_login_strategy(client)
    mfa_status, _ = client.login(_garmin_login_argument(None))
    if mfa_status == "needs_mfa":
        with _pending_mfa_lock:
            _pending_garmin_mfa[(user_id, attempt_id)] = {
                "client": client,
                "creds": creds,
                "created": time.time(),
                "attempt_id": attempt_id,
            }
        _schedule_garmin_login_prune()
        return "mfa_required", attempt_id

    serialized_tokens = _serialize_garmin_tokens(client)
    completed_key = (user_id, attempt_id)
    with _pending_mfa_lock:
        _completed_garmin_tokens[completed_key] = serialized_tokens
        _completed_garmin_token_created[completed_key] = time.time()
    _schedule_garmin_login_prune()
    return "connected", attempt_id


def complete_garmin_mfa(
    user_id: str,
    code: str,
    login_attempt_id: str | None = None,
) -> tuple[dict, str]:
    """Finish a pending interactive Garmin login with an MFA code.

    Returns the credential dict to persist on success. Raises
    ``RuntimeError("GARMIN_MFA_EXPIRED")`` when there is no matching live
    pending login (never started, ambiguous legacy request, or TTL elapsed),
    and re-raises ``GarminConnect*`` errors when the code is wrong/expired. On
    a bad code the pending entry is left in place for retry within the TTL.
    """
    _prune_expired_mfa()
    with _pending_mfa_lock:
        if login_attempt_id:
            pending_key = (user_id, login_attempt_id)
            pending = _pending_garmin_mfa.get(pending_key)
        else:
            matching_keys = [
                key for key in _pending_garmin_mfa
                if key[0] == user_id
            ]
            pending_key = (
                matching_keys[0]
                if len(matching_keys) == 1
                else None
            )
            pending = (
                _pending_garmin_mfa.get(pending_key)
                if pending_key is not None
                else None
            )
    if not pending:
        raise RuntimeError("GARMIN_MFA_EXPIRED")

    client = pending["client"]
    # resume_login ignores its client_state arg (the MFA state lives on the
    # client) and raises on a bad/expired code.
    client.resume_login({}, code)
    serialized_tokens = _serialize_garmin_tokens(client)
    expired_after_completion = False
    with _pending_mfa_lock:
        assert pending_key is not None
        current = _pending_garmin_mfa.get(pending_key)
        if (
            current is None
            or current.get("attempt_id") != pending.get("attempt_id")
        ):
            expired_after_completion = True
        else:
            _pending_garmin_mfa.pop(pending_key, None)
            attempt_id = str(pending["attempt_id"])
            completed_key = (user_id, attempt_id)
            _completed_garmin_tokens[completed_key] = serialized_tokens
            _completed_garmin_token_created[completed_key] = time.time()
    if expired_after_completion:
        raise RuntimeError("GARMIN_MFA_EXPIRED")
    _schedule_garmin_login_prune()
    return pending["creds"], attempt_id


def bind_garmin_login_tokens(
    db: Session,
    user_id: str,
    credential_generation: str,
    login_attempt_id: str,
) -> None:
    """Encrypt freshly authenticated tokens in the credential transaction."""
    from db.garmin_tokens import stage_garmin_tokens

    with _pending_mfa_lock:
        completed_key = (user_id, login_attempt_id)
        serialized_tokens = _completed_garmin_tokens.pop(completed_key, None)
        _completed_garmin_token_created.pop(completed_key, None)
    if serialized_tokens is None:
        raise RuntimeError("GARMIN_LOGIN_TOKENS_UNAVAILABLE")
    with _garmin_tokenstore_lease(user_id):
        stage_garmin_tokens(
            db,
            user_id=user_id,
            serialized_tokens=serialized_tokens,
            expected_generation=credential_generation,
            allowed_statuses=("connected",),
        )


def _get_credentials(user_id: str, platform: str, db: Session) -> dict | None:
    """Get decrypted credentials for a user's platform connection.

    Returns credential dict or None if not connected.
    """
    from db.connection_credentials import (
        CredentialAccessError,
        load_connection_credentials,
    )

    try:
        return load_connection_credentials(
            db,
            user_id=user_id,
            platform=platform,
        )
    except CredentialAccessError as exc:
        logger.warning(
            "Failed to decode credentials for user=%s platform=%s: %s",
            user_id,
            platform,
            exc,
        )
        return None


def _sync_credentials_snapshot(
    user_id: str,
    platform: str,
    db: Session,
) -> tuple[dict, str] | None:
    """Capture runnable credentials and their immutable DB generation."""
    from db.connection_credentials import (
        CredentialAccessError,
        connection_credentials_generation,
        load_connection_credentials,
    )
    from db.models import UserConnection
    from db.sync_scheduler import SCHEDULABLE_STATUSES

    connection = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == platform,
        UserConnection.status.in_(SCHEDULABLE_STATUSES),
    ).one_or_none()
    if connection is None:
        return None
    try:
        credentials = load_connection_credentials(
            db,
            user_id=user_id,
            platform=platform,
        )
    except CredentialAccessError as exc:
        logger.warning(
            "Failed to capture sync credentials for user=%s platform=%s: %s",
            user_id,
            platform,
            exc,
        )
        return None
    if credentials is None:
        return None
    return (
        credentials,
        connection_credentials_generation(connection),
    )


def _persist_credentials(user_id: str, platform: str, creds: dict, db: Session) -> None:
    """Encrypt and persist updated platform credentials."""

    from db.crypto import get_vault
    from db.models import UserConnection

    vault = get_vault()
    encrypted_credentials, wrapped_dek = vault.encrypt(json.dumps(creds))
    conn = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == platform,
    ).first()
    if conn is None:
        return
    conn.encrypted_credentials = encrypted_credentials
    conn.wrapped_dek = wrapped_dek


def _get_strava_client_config(creds: dict | None = None) -> tuple[str, str]:
    """Load Strava OAuth client credentials from user's stored credentials or environment."""

    if creds:
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if client_id and client_secret:
            return client_id, client_secret

    client_id = getenv_compat("STRAVA_CLIENT_ID")
    client_secret = getenv_compat("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Strava OAuth is not configured. Provide your Strava Client ID and Client Secret when connecting."
        )
    return client_id, client_secret


def _run_post_sync_plan_adjustment(
    user_id: str,
    *,
    source: str,
) -> None:
    """Run opted-in deterministic adjustment without changing sync success."""
    try:
        from api.plan_adjustments import run_plan_adjustment_for_user

        result = run_plan_adjustment_for_user(
            user_id,
            trigger=f"manual_sync:{source}",
        )
        logger.info(
            "Plan adjustment for user=%s source=%s: %s",
            user_id,
            source,
            result.get("status"),
        )
    except Exception:
        logger.exception(
            "Post-sync plan adjustment failed for user=%s source=%s",
            user_id,
            source,
        )


def _run_sync(
    user_id: str,
    source: str,
    creds: dict,
    from_date: str | None = None,
    expected_connection_generation: str | None = None,
) -> None:
    """Run sync for a single source. Called in a background thread.

    Fetches data from platform APIs and writes directly to DB — no CSV
    intermediate step. The sync scripts' parse functions produce row dicts
    which are written to DB via db.sync_writer.

    Args:
        user_id: User to sync for.
        source: Platform name (garmin, stryd, oura).
        creds: Decrypted credentials dict.
        from_date: Optional start date for backfill.
    """
    from db.session import init_db, SessionLocal
    from db.models import UserConnection
    from db import sync_writer
    from db.connection_credentials import (
        ConnectionGenerationChanged,
        require_connection_generation,
    )
    from db.sync_scheduler import SCHEDULABLE_STATUSES

    status = _get_user_status(user_id)

    with _sync_lock:
        status[source] = {"status": "syncing", "last_sync": None, "error": None}

    init_db()
    db = SessionLocal()
    garmin_token_state: dict[str, object] = {}
    context_token = _begin_background_sync_execution(user_id, db)

    try:
        _require_background_processing_authorized(user_id, db)
        if source == "stryd":
            from api.stryd_access import stryd_connection_enabled

            if not stryd_connection_enabled(db, user_id=user_id):
                raise RuntimeError("Stryd integration is not available")
        token_lease = (
            _garmin_tokenstore_lease(user_id)
            if source == "garmin"
            else contextlib.nullcontext()
        )
        with token_lease:
            _require_background_processing_authorized(user_id, db)
            if expected_connection_generation is not None:
                require_connection_generation(
                    db,
                    user_id=user_id,
                    platform=source,
                    expected_generation=expected_connection_generation,
                    allowed_statuses=SCHEDULABLE_STATUSES,
                )
            counts = {}

            if source == "garmin":
                if expected_connection_generation is None:
                    counts = _sync_garmin(
                        user_id,
                        creds,
                        from_date,
                        db,
                    )
                else:
                    counts = _sync_garmin(
                        user_id,
                        creds,
                        from_date,
                        db,
                        credential_generation=(
                            expected_connection_generation
                        ),
                        _token_state=garmin_token_state,
                    )

            elif source == "strava":
                counts = _sync_strava(user_id, creds, from_date, db)

            elif source == "stryd":
                counts = _sync_stryd(user_id, creds, from_date, db)

            elif source == "oura":
                counts = _sync_oura(user_id, creds, from_date, db)

            elif source == "coros":
                counts = _sync_coros(user_id, creds, from_date, db)

            else:
                raise ValueError(f"Unknown source: {source}")

            if expected_connection_generation is not None:
                require_connection_generation(
                    db,
                    user_id=user_id,
                    platform=source,
                    expected_generation=expected_connection_generation,
                    allowed_statuses=SCHEDULABLE_STATUSES,
                    lock=True,
                )
            _commit_authorized_background_sync_changes(user_id, db)
        # Refresh activity-derived CP on any sync that can change activity
        # power observations (Garmin, Strava, Stryd — not Oura). The fit
        # itself is cheap and idempotent; skipping Oura just avoids the
        # no-op DB read.
        if source in ("garmin", "strava", "stryd", "coros"):
            try:
                from db.sync_writer import update_cp_from_activities
                fit = update_cp_from_activities(user_id, db)
                if fit is not None:
                    if expected_connection_generation is not None:
                        require_connection_generation(
                            db,
                            user_id=user_id,
                            platform=source,
                            expected_generation=(
                                expected_connection_generation
                            ),
                            allowed_statuses=SCHEDULABLE_STATUSES,
                            lock=True,
                        )
                    _commit_authorized_background_sync_changes(user_id, db)
                    logger.info(
                        "Activity-derived CP for user %s: %.1fW (r²=%.2f, %d points)",
                        user_id, fit["cp_watts"], fit["r_squared"], fit["point_count"],
                    )
            except ConnectionGenerationChanged:
                raise
            except BackgroundProcessingAuthorizationLost:
                raise
            except Exception:
                # CP refresh is best-effort; never let it break the sync.
                logger.exception("Activity-derived CP refresh failed for user %s", user_id)
                db.rollback()

        # Update last_sync on the connection record. Clear any prior
        # backoff state so a previously-failed connection that the user
        # successfully synced manually (or that recovered on its own)
        # rejoins the regular schedule immediately.
        from db.sync_scheduler import reset_connection_backoff
        conn = (
            require_connection_generation(
                db,
                user_id=user_id,
                platform=source,
                expected_generation=expected_connection_generation,
                allowed_statuses=SCHEDULABLE_STATUSES,
                lock=True,
            )
            if expected_connection_generation is not None
            else db.query(UserConnection).filter(
                UserConnection.user_id == user_id,
                UserConnection.platform == source,
            ).first()
        )
        if conn:
            conn.last_sync = datetime.now(timezone.utc).replace(tzinfo=None)
            conn.status = "connected"
            reset_connection_backoff(conn)
            _commit_authorized_background_sync_changes(user_id, db)

        logger.info("Sync %s for user %s: %s", source, user_id, counts)

        # Manual-path success telemetry (scheduled path emits from _sync_connection).
        _require_background_processing_authorized(user_id, db)
        try:
            from api import telemetry
            telemetry.record_sync(
                platform=source, outcome="success", failure_class="none",
                trigger="manual", user_id=user_id,
            )
        except Exception:
            pass

        _require_background_processing_authorized(user_id, db)
        _run_post_sync_plan_adjustment(user_id, source=source)

        # Post-sync LLM insight generation. Best-effort: failures here must
        # never break the sync. The runner is content-addressable (skips when
        # the dataset hash is unchanged) and self-throttling (per-user daily
        # cap), so calling it on every sync is safe.
        try:
            _require_background_processing_authorized(user_id, db)
            from api.insights_runner import run_insights_for_user
            insight_results = run_insights_for_user(user_id, db, counts)
            logger.info("Insight generation for user %s: %s", user_id, insight_results)
        except BackgroundProcessingAuthorizationLost:
            raise
        except Exception:
            # No rollback: the runner uses its own session, and the caller's
            # session has nothing pending past the prior db.commit().
            logger.exception("Insight generation failed for user %s", user_id)

        _require_background_processing_authorized(user_id, db)
        with _sync_lock:
            status[source] = {
                "status": "done",
                "last_sync": utc_isoformat(datetime.now(timezone.utc)),
                "error": None,
            }

    except (
        BackgroundProcessingAuthorizationLost,
        ConnectionGenerationChanged,
    ):
        db.rollback()
        logger.info(
            "Cancelled sync outside its current authorization or generation "
            "for %s (user %s)",
            source,
            user_id,
        )
        with _sync_lock:
            status[source] = {
                "status": "idle",
                "last_sync": None,
                "error": None,
            }
    except Exception as e:
        db.rollback()
        try:
            _require_background_processing_authorized(user_id, db)
        except BackgroundProcessingAuthorizationLost:
            logger.info(
                "Cancelled failed sync after processing authorization was "
                "withdrawn for %s (user %s)",
                source,
                user_id,
            )
            with _sync_lock:
                status[source] = {
                    "status": "idle",
                    "last_sync": None,
                    "error": None,
                }
            return
        except Exception:
            # Preserve the original provider failure when the authorization
            # read itself is temporarily unavailable.
            db.rollback()
        if (
            source == "garmin"
            and expected_connection_generation is not None
        ):
            try:
                persisted = _persist_garmin_token_state_after_rollback(
                    db,
                    user_id=user_id,
                    credential_generation=expected_connection_generation,
                    token_state=garmin_token_state,
                    allowed_statuses=SCHEDULABLE_STATUSES,
                )
                if not persisted:
                    logger.warning(
                        "Skipped stale Garmin token publication after sync "
                        "failure for user %s",
                        user_id,
                    )
            except BackgroundProcessingAuthorizationLost:
                db.rollback()
                logger.info(
                    "Cancelled Garmin token publication after processing "
                    "authorization was withdrawn for user %s",
                    user_id,
                )
                with _sync_lock:
                    status[source] = {
                        "status": "idle",
                        "last_sync": None,
                        "error": None,
                    }
                return
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to persist Garmin OAuth tokens after outer sync "
                    "failure for user %s",
                    user_id,
                )
        logger.exception("Sync failed for %s (user %s)", source, user_id)
        with _sync_lock:
            status[source] = {
                "status": "error",
                "last_sync": None,
                "error": str(e),
            }
        # Update connection status with classification + backoff so the
        # background scheduler stops hammering a stuck connection.
        # ``_record_sync_failure`` handles its own rollback and commit.
        failure_recorded = False
        try:
            from api.legal_receipts import (
                user_background_processing_authorized,
            )
            from db.sync_scheduler import _record_sync_failure
            conn = db.query(UserConnection).filter(
                UserConnection.user_id == user_id,
                UserConnection.platform == source,
            ).first()
            if conn:
                failure_recorded = _record_sync_failure(
                    conn,
                    e,
                    db,
                    trigger="manual",
                    expected_credential_generation=(
                        expected_connection_generation
                    ),
                    authorize_commit=lambda check_db: (
                        user_background_processing_authorized(
                            check_db,
                            user_id,
                        )
                    ),
                )
        except Exception:
            pass
        if not failure_recorded:
            try:
                _require_background_processing_authorized(user_id, db)
            except BackgroundProcessingAuthorizationLost:
                with _sync_lock:
                    status[source] = {
                        "status": "idle",
                        "last_sync": None,
                        "error": None,
                    }
                return
            except Exception:
                db.rollback()
        if (
            expected_connection_generation is not None
            and not failure_recorded
        ):
            try:
                require_connection_generation(
                    db,
                    user_id=user_id,
                    platform=source,
                    expected_generation=expected_connection_generation,
                    allowed_statuses=SCHEDULABLE_STATUSES,
                )
            except ConnectionGenerationChanged:
                with _sync_lock:
                    status[source] = {
                        "status": "idle",
                        "last_sync": None,
                        "error": None,
                    }
    finally:
        _end_background_sync_execution(context_token)
        db.close()


def _login_garmin_with_cn_fallback(
    client,
    creds: dict,
    serialized_tokens: str | None,
) -> None:
    """Log in the Garmin client, working around the 0.3.x JWT_WEB CN bug.

    **Mobile/widget strategies' JWT_WEB fallback is ``.com``-only.** The
    first four login strategies can reach a point where the CAS ticket is
    consumed against ``mobile.integration.garmin.com`` /
    ``sso.garmin.com/sso/embed`` — for CN the DNS fails or no ``JWT_WEB``
    cookie is set. The library re-raises that as an auth error and aborts
    the chain *before* reaching the portal strategies (which do use the
    domain-aware ``_portal_service_url``). When we see that specific
    message we retry ``_portal_web_login_cffi`` directly. The message
    match keeps real credential failures
    (``"Invalid Username or Password"``) bubbling up.

    The sibling DI Bearer token bug (``DI_TOKEN_URL`` hardcoded to
    ``.com``) was fixed upstream in garminconnect 0.3.4 (PR #360 —
    ``_di_token_url`` is now a domain-aware instance attribute), so no
    DI patching is needed here.
    """
    from garminconnect import GarminConnectAuthenticationError

    # Force the portal strategy: the widget strategy mints tokens the API
    # tier rejects (#369) and is also the MFA-handling path, so a re-auth
    # would otherwise re-mint a rejected token. Portal mints accepted tokens.
    _force_portal_login_strategy(client)

    try:
        client.login(_garmin_login_argument(serialized_tokens))
        return
    except GarminConnectAuthenticationError as e:
        msg = str(e)
        # A background sync has no user present to answer an MFA challenge.
        # When cached tokens are gone/rejected and a fresh credential login
        # hits MFA, garminconnect raises "MFA Required but no prompt_mfa
        # mechanism supplied". Surface a clean, actionable status
        # (classify_sync_failure maps GarminConnectAuthenticationError →
        # auth_required) instead of leaking the raw library string.
        if "MFA" in msg and "prompt_mfa" in msg:
            raise GarminConnectAuthenticationError(
                "Garmin requires re-authentication (MFA). Please reconnect "
                "your account from Settings to enter a verification code."
            ) from e
        if "JWT_WEB cookie not set" not in msg:
            raise
        logger.warning(
            "Garmin login hit JWT_WEB fallback bug (hardcoded .com host); "
            "retrying via portal strategy.",
        )

    inner = client.client
    inner._portal_web_login_cffi(creds["email"], creds["password"])


def _persist_garmin_calendar_snapshot(
    db: Session,
    *,
    user_id: str,
    provider_account_id: str,
    profile_account_id: str | None = None,
    rows: list[dict],
    window_start: date,
    window_end: date,
    observed_at: datetime,
) -> int:
    """Atomically persist one complete read-only Garmin calendar snapshot."""
    from db import sync_writer
    from db.plan_reconciliation import record_target_calendar_sync

    observed_external_ids = {
        str(row.get("external_id") or "").strip()
        for row in rows
        if str(row.get("external_id") or "").strip()
    }
    with db.begin_nested():
        snapshot_changes = record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id=provider_account_id,
            provider_references=(
                {"profile_account_id": profile_account_id}
                if profile_account_id
                else {}
            ),
            rows=rows,
            window_start=window_start,
            window_end=window_end,
            observed_at=observed_at,
        )
        if snapshot_changes is None:
            return 0
        changed = sync_writer.write_training_plan(
            user_id,
            rows,
            "garmin",
            db,
        )
        changed += sync_writer.prune_training_plan_window(
            user_id,
            source="garmin",
            observed_external_ids=observed_external_ids,
            window_start=window_start,
            window_end=window_end,
            db=db,
        )
    return changed


def _sync_garmin(
    user_id: str,
    creds: dict,
    from_date: str | None,
    db,
    *,
    credential_generation: str | None = None,
    _token_state: dict[str, object] | None = None,
) -> dict:
    """Fetch Garmin data while serializing mutable OAuth token access."""
    with _garmin_tokenstore_lease(user_id):
        _block_legacy_garmin_tokenstore(user_id)
        token_state = _token_state if _token_state is not None else {}
        try:
            return _sync_garmin_locked(
                user_id,
                creds,
                from_date,
                db,
                credential_generation=credential_generation,
                _token_state=token_state,
            )
        except Exception:
            rollback_ok = True
            if credential_generation is not None:
                try:
                    db.rollback()
                except Exception:
                    rollback_ok = False
                    logger.exception(
                        "Failed to roll back Garmin sync data before token "
                        "persistence for user %s",
                        user_id,
                    )
            _require_background_sync_commit_authorized(user_id, db)
            client = token_state.get("client")
            if (
                credential_generation is not None
                and client is not None
                and rollback_ok
            ):
                try:
                    from db.sync_scheduler import SCHEDULABLE_STATUSES

                    _persist_garmin_token_state_after_rollback(
                        db,
                        user_id=user_id,
                        credential_generation=credential_generation,
                        token_state=token_state,
                        allowed_statuses=SCHEDULABLE_STATUSES,
                    )
                except BackgroundProcessingAuthorizationLost:
                    raise
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Failed to persist refreshed Garmin OAuth tokens after "
                        "sync failure for user %s",
                        user_id,
                    )
            raise


def _sync_garmin_locked(
    user_id: str,
    creds: dict,
    from_date: str | None,
    db,
    *,
    credential_generation: str | None = None,
    _token_state: dict[str, object] | None = None,
) -> dict:
    """Fetch Garmin data and write directly to DB."""
    from db import sync_writer
    from db.garmin_tokens import load_garmin_tokens, stage_garmin_tokens
    from db.sync_scheduler import SCHEDULABLE_STATUSES
    from garminconnect import Garmin
    from garminconnect.exceptions import (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
    from sync.garmin_sync import (
        parse_activities, parse_splits, parse_activity_stream,
        parse_daily_metrics, parse_lactate_threshold, parse_user_profile,
        parse_activity_weather, parse_heart_rates, parse_running_ftp,
        RATE_LIMIT_DELAY,
        GARMIN_MAX_CHART_SIZE,
        GARMIN_CALENDAR_DAYS_AHEAD,
        GARMIN_CALENDAR_DAYS_BACK,
        enrich_training_plan_content,
        fetch_training_plan_api,
        garmin_profile_account_id,
        garmin_provider_account_id,
        garmin_user_profile_id,
    )
    import time

    # Region resolution: the Settings UI writes user_config.source_options.
    # garmin_region, but the reconnect flow separately stores is_cn inside the
    # encrypted credentials blob. These two values used to drift — a user
    # could change the region in Settings, see it reflected in the UI, and
    # still hit the wrong Garmin SSO because the sync read is_cn only from
    # the encrypted blob. Prefer source_options as the authoritative setting;
    # fall back to the legacy creds.is_cn for connections that predate the
    # region toggle.
    from analysis.config import load_config_from_db
    user_config = load_config_from_db(user_id, db)
    region = user_config.source_options.get("garmin_region")
    if region in ("cn", "international"):
        is_cn = region == "cn"
    else:
        is_cn = bool(creds.get("is_cn", False))

    client = Garmin(creds["email"], creds["password"], is_cn=is_cn)
    serialized_tokens = None
    if credential_generation is not None:
        serialized_tokens = load_garmin_tokens(
            db,
            user_id=user_id,
            expected_generation=credential_generation,
            allowed_statuses=SCHEDULABLE_STATUSES,
        )
    if _token_state is not None:
        _token_state["client"] = client
        _token_state["committed_tokens"] = serialized_tokens
    _login_garmin_with_cn_fallback(client, creds, serialized_tokens)
    authenticated_tokens: str | None = None
    if credential_generation is not None:
        authenticated_tokens = _serialize_garmin_tokens(client)
        if authenticated_tokens != serialized_tokens:
            stage_garmin_tokens(
                db,
                user_id=user_id,
                serialized_tokens=authenticated_tokens,
                expected_generation=credential_generation,
                allowed_statuses=SCHEDULABLE_STATUSES,
            )
            _commit_background_sync_provider_changes(user_id, db)
        if _token_state is not None:
            _token_state["committed_tokens"] = authenticated_tokens

    # Fetch read-only workout-calendar evidence before any DB writes. Auth and
    # rate-limit failures must reach the normal source backoff path, but doing
    # so after activities/recovery were staged would roll those successful
    # writes back. Non-auth endpoint/schema failures remain calendar-local and
    # preserve the last complete snapshot.
    plan_rows: list[dict] | None = None
    provider_account_id: str | None = None
    profile_account_id: str | None = None
    calendar_today = date.today()
    calendar_window_start = (
        calendar_today - timedelta(days=GARMIN_CALENDAR_DAYS_BACK)
    )
    calendar_window_end = (
        calendar_today + timedelta(days=GARMIN_CALENDAR_DAYS_AHEAD)
    )
    calendar_fetch_started_at = datetime.now(timezone.utc).replace(
        tzinfo=None
    )
    calendar_reader = getattr(client, "get_scheduled_workouts", None)
    if not callable(calendar_reader):
        logger.warning(
            "Garmin workout calendar method is unavailable for user %s",
            user_id,
        )
    else:
        try:
            profile_account_id = garmin_profile_account_id(
                user_id=user_id,
                is_cn=is_cn,
                garmin_user_profile_id=garmin_user_profile_id(client),
            )
            provider_account_id = garmin_provider_account_id(
                user_id=user_id,
                display_name=getattr(client, "display_name", None),
                is_cn=is_cn,
            )
            fetched_plan_rows = fetch_training_plan_api(
                client,
                window_start=calendar_window_start,
                window_end=calendar_window_end,
            )
            enrich_training_plan_content(client, fetched_plan_rows)
            for plan_row in fetched_plan_rows:
                plan_row["provider_references"] = {
                    **dict(plan_row.get("provider_references") or {}),
                    "profile_account_id": profile_account_id,
                }
            plan_rows = fetched_plan_rows
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
        ):
            raise
        except GarminConnectConnectionError as e:
            if _exception_status_code(e) in {401, 429}:
                raise
            logger.warning(
                "Garmin workout calendar fetch failed for user %s: %s",
                user_id,
                e,
            )
        except (
            requests.ConnectionError,
            requests.Timeout,
            TypeError,
            ValueError,
        ) as e:
            logger.warning(
                "Garmin workout calendar payload was unavailable for user %s: %s",
                user_id,
                e,
            )

    end = date.today().isoformat()
    start = from_date or (date.today() - timedelta(days=7)).isoformat()

    # Read configured activity categories from user config (already loaded
    # above for region resolution). Garmin's search API only accepts top-level
    # types (running, cycling, etc.) not subtypes (trail_running,
    # treadmill_running). We fetch by top-level category — all subtypes are
    # returned automatically.
    categories = user_config.source_options.get(
        "garmin_activity_categories", ["running"]
    )
    # Map category names to Garmin API activitytype parameter
    CATEGORY_TO_API_TYPE = {
        "running": "running",
        "cycling": "cycling",
        "swimming": "swimming",
        "hiking": "hiking",
        "walking": "walking",
        # "strength" intentionally absent: Garmin's API now rejects
        # activityType=strength_training with "Activity type cannot be an
        # activity sub type" (it was reclassified as a subtype of
        # fitness_equipment). Users who selected Strength in Setup will
        # have it fall through to the top-level query via the default
        # mapping (``c`` maps to itself). The resulting 400 is logged at
        # warning level and the other categories still sync fine.
    }
    api_types = list({CATEGORY_TO_API_TYPE.get(c) for c in categories if CATEGORY_TO_API_TYPE.get(c)})

    # Fetch activities for each configured type
    raw_activities = []
    for atype in api_types:
        try:
            batch = client.get_activities_by_date(start, end, activitytype=atype)
            raw_activities.extend(batch)
        except Exception as e:
            logger.warning(
                "Garmin activities fetch failed for user %s type %s: %s",
                user_id, atype, e,
            )
    activity_rows = parse_activities(raw_activities)
    status = _get_user_status(user_id)
    weather_rows_by_id = {
        str(row.get("activity_id")): row
        for row in activity_rows
        if row.get("activity_id")
        and row.get("activity_type") in {"running", "trail_running"}
    }
    needed_weather_ids = _activity_ids_needing_environment(
        user_id, weather_rows_by_id, db,
    )
    weather_rows = [
        (activity_id, row)
        for activity_id, row in weather_rows_by_id.items()
        if activity_id in needed_weather_ids
    ]
    weather_failures = 0
    weather_completed = 0
    weather_abort: Exception | None = None
    for idx, (aid, row) in enumerate(weather_rows):
        with _sync_lock:
            status["garmin"]["progress"] = (
                f"Fetching weather: {idx + 1}/{len(weather_rows)}"
            )
        try:
            weather = client.get_activity_weather(aid) or {}
            row.update(parse_activity_weather(weather))
        except (
            GarminConnectAuthenticationError,
            GarminConnectTooManyRequestsError,
        ):
            raise
        except GarminConnectConnectionError as e:
            status_code = _exception_status_code(e)
            if status_code in {401, 403, 429}:
                raise
            if status_code not in {400, 404}:
                weather_abort = e
                break
            weather_failures += 1
            logger.debug("Weather for %s: skipped (%s)", aid, e)
        except ValueError as e:
            weather_failures += 1
            logger.debug("Weather for %s: skipped (%s)", aid, e)
        time.sleep(RATE_LIMIT_DELAY)
        weather_completed += 1
    if weather_abort is not None:
        logger.warning(
            "Garmin weather enrichment stopped after %d of %d eligible "
            "activities (user %s): %s",
            weather_completed,
            len(weather_rows),
            user_id,
            weather_abort,
        )
    elif weather_rows and weather_failures >= max(3, len(weather_rows) // 2):
        logger.warning(
            "Garmin weather fetch failed for %d of %d eligible activities "
            "(user %s) — heat-adaptation evidence will be incomplete",
            weather_failures, len(weather_rows), user_id,
        )
    act_count = sync_writer.write_activities(user_id, activity_rows, db)

    # Splits — per-activity lap data. Splits drive interval intensity analysis
    # (see CLAUDE.md: "Always use activity_splits.csv for intensity analysis").
    # Per-activity misses are logged at debug, but a systemic failure would
    # quietly lose intensity metrics, so we surface an aggregate warning.
    activity_ids = [str(a.get("activityId", "")) for a in raw_activities]
    total = len(activity_ids)
    split_payloads: dict[str, object] = {}
    split_failures = 0
    for idx, aid in enumerate(activity_ids):
        with _sync_lock:
            status["garmin"]["progress"] = f"Fetching splits: {idx + 1}/{total}"
        try:
            splits_data = client.get_activity_splits(aid) or {}
            split_payloads[aid] = splits_data
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            split_failures += 1
            logger.debug("Splits for %s: skipped (%s)", aid, e)
    if total and split_failures >= max(3, total // 2):
        logger.warning(
            "Garmin splits fetch failed for %d of %d activities (user %s) — "
            "intensity analysis will be missing for those runs",
            split_failures, total, user_id,
        )

    # Fetch per-second streams and write to activity_samples. One extra API
    # call per activity (get_activity_details). Rate-limited the same as splits.
    # Standard and explicitly recognized Stryd ConnectIQ power also enriches
    # laps that do not carry their own power aggregate.
    all_samples = []
    samples_by_activity: dict[str, list[dict]] = {}
    stream_failures = 0
    for idx, aid in enumerate(activity_ids):
        with _sync_lock:
            status["garmin"]["progress"] = f"Fetching streams: {idx + 1}/{total}"
        try:
            details = client.get_activity_details(aid, maxchart=GARMIN_MAX_CHART_SIZE) or {}
            parsed_samples = parse_activity_stream(aid, details)
            samples_by_activity[aid] = parsed_samples
            all_samples.extend(parsed_samples)
            time.sleep(RATE_LIMIT_DELAY)
        except Exception as e:
            stream_failures += 1
            logger.debug("Stream for %s: skipped (%s)", aid, e)
    if total and stream_failures >= max(3, total // 2):
        logger.warning(
            "Garmin stream fetch failed for %d of %d activities (user %s)",
            stream_failures, total, user_id,
        )

    all_splits = []
    for aid in activity_ids:
        all_splits.extend(parse_splits(
            aid,
            split_payloads.get(aid, {}),
            activity_samples=samples_by_activity.get(aid),
        ))
    split_count = sync_writer.write_splits(user_id, all_splits, db)
    sample_count = sync_writer.write_samples(user_id, all_samples, db)
    logger.debug("Garmin sync: %d splits, %d samples written", split_count, sample_count)

    # Lactate threshold. Log at warning so intermittent failures surface
    # instead of vanishing at debug level — the previous behaviour silently
    # hid real failures when endpoints rejected the request.
    lt_count = 0
    try:
        lt_start = (date.today() - timedelta(days=365)).isoformat()
        lt_data = client.get_lactate_threshold(latest=False, start_date=lt_start, end_date=end)
        lt_rows = parse_lactate_threshold(lt_data)
        if not lt_rows:
            lt_rows = parse_lactate_threshold(client.get_lactate_threshold(latest=True))
        with db.begin_nested():
            lt_count = sync_writer.write_lactate_threshold(user_id, lt_rows, db)
    except Exception as e:
        logger.warning("Garmin lactate threshold fetch failed for user %s: %s", user_id, e)

    # User profile + today's heart-rates → threshold inputs for _resolve_thresholds.
    # Profile carries LTHR (and sometimes max HR). The profile endpoint does
    # NOT return resting HR on International accounts — that comes from
    # get_heart_rates(date), whose lastSevenDaysAvgRestingHeartRate is the
    # stable reference we want for TRIMP's rest_hr.
    profile_count = 0
    try:
        profile_raw = client.get_user_profile()
        profile_parsed = parse_user_profile(profile_raw)
    except Exception as e:
        profile_parsed = {}
        logger.warning("Garmin user profile fetch failed for user %s: %s", user_id, e)

    today_str = date.today().isoformat()
    try:
        today_hr = client.get_heart_rates(today_str) or {}
        hr_parsed = parse_heart_rates(today_hr)
        rolling = hr_parsed.get("rolling_rest_hr")
        if rolling is not None:
            profile_parsed["rest_hr_bpm"] = rolling
    except Exception as e:
        logger.warning("Garmin heart_rates fetch failed for user %s: %s", user_id, e)

    # Running FTP / Critical Power. Garmin exposes this at the same URL
    # pattern as cycling FTP — garminconnect wraps cycling but not running,
    # so we call the endpoint directly. Note: Garmin's native running power
    # reads substantially higher than Stryd (~30% gap on the same athlete);
    # see docs/dev/gotchas.md. For users who have both sources syncing, the
    # latest write to fitness_data.cp_estimate wins — which can cause CP
    # thresholds to whiplash between the two systems.
    try:
        rftp_raw = client.connectapi(
            "/biometric-service/biometric/latestFunctionalThresholdPower/RUNNING"
        )
        rftp_parsed = parse_running_ftp(rftp_raw)
        if rftp_parsed:
            profile_parsed.update(rftp_parsed)
    except Exception as e:
        logger.warning("Garmin running FTP fetch failed for user %s: %s", user_id, e)

    if profile_parsed:
        try:
            with db.begin_nested():
                profile_count = sync_writer.write_profile_thresholds(
                    user_id, profile_parsed, db,
                )
        except Exception as e:
            logger.warning(
                "Garmin profile threshold write failed for user %s: %s", user_id, e,
            )

    # Daily metrics (VO2max, training status, readiness, race prediction).
    # Kept independent of recovery so one endpoint failing (common on Garmin
    # CN where some endpoints aren't live) doesn't wipe out the other.
    dm_count = 0
    tr = None
    try:
        today_str = date.today().isoformat()
        ts = client.get_training_status(today_str) or {}
        try:
            tr = client.get_training_readiness(today_str)
        except Exception as e:
            logger.debug("Training readiness: skipped (%s)", e)
        rp = None
        try:
            rp = client.get_race_predictions()
        except Exception as e:
            logger.debug("Race predictions: skipped (%s)", e)
        dm_rows = parse_daily_metrics(today_str, ts, training_readiness=tr, race_predictions=rp)
        with db.begin_nested():
            dm_count = sync_writer.write_daily_metrics(user_id, dm_rows, db)
    except Exception as e:
        logger.warning("Garmin daily metrics fetch failed for user %s: %s", user_id, e)

    # Recovery (HRV, sleep, readiness). Honour the same date window as the
    # activity sync so a 6-month backfill doesn't leave us with a 7-day HRV
    # trend. Cap to a year to avoid hammering Garmin if from_date is ancient.
    recovery_count = 0
    recovery_rows: list[dict] = []
    try:
        from sync.garmin_sync import parse_garmin_recovery

        start_date = date.fromisoformat(start)
        today_date = date.today()
        requested_days = (today_date - start_date).days + 1
        total_days = max(1, min(requested_days, 365))
        if requested_days > total_days:
            logger.info(
                "Garmin recovery backfill window capped at %d days for user %s "
                "(requested %d)", total_days, user_id, requested_days,
            )

        # Circuit-breaker: if an endpoint rejects N consecutive times, stop
        # calling it for the rest of the loop. Prevents a 180-day backfill
        # with a systemic auth failure from spamming 360 debug lines and
        # waiting RATE_LIMIT_DELAY×180 for nothing.
        consec_break = 5
        hrv_fail_streak = 0
        sleep_fail_streak = 0
        hr_fail_streak = 0
        hrv_last_err: Exception | None = None
        sleep_last_err: Exception | None = None
        hr_last_err: Exception | None = None
        hrv_aborted = False
        sleep_aborted = False
        hr_aborted = False

        parse_failures = 0
        for days_ago in range(total_days):
            d = (today_date - timedelta(days=days_ago)).isoformat()
            hrv = None
            sleep = None
            hr_daily = None
            if not hrv_aborted:
                try:
                    hrv = client.get_hrv_data(d)
                    hrv_fail_streak = 0
                except Exception as e:
                    hrv_fail_streak += 1
                    hrv_last_err = e
                    logger.debug("HRV for %s: skipped (%s)", d, e)
                    if hrv_fail_streak >= consec_break:
                        hrv_aborted = True
                        logger.warning(
                            "Garmin HRV aborted after %d consecutive failures "
                            "for user %s: %s",
                            hrv_fail_streak, user_id, hrv_last_err,
                        )
            if not sleep_aborted:
                try:
                    sleep = client.get_sleep_data(d)
                    sleep_fail_streak = 0
                except Exception as e:
                    sleep_fail_streak += 1
                    sleep_last_err = e
                    logger.debug("Sleep for %s: skipped (%s)", d, e)
                    if sleep_fail_streak >= consec_break:
                        sleep_aborted = True
                        logger.warning(
                            "Garmin sleep aborted after %d consecutive failures "
                            "for user %s: %s",
                            sleep_fail_streak, user_id, sleep_last_err,
                        )
            if not hr_aborted:
                try:
                    hr_daily = client.get_heart_rates(d)
                    hr_fail_streak = 0
                except Exception as e:
                    hr_fail_streak += 1
                    hr_last_err = e
                    logger.debug("Heart rates for %s: skipped (%s)", d, e)
                    if hr_fail_streak >= consec_break:
                        hr_aborted = True
                        logger.warning(
                            "Garmin heart_rates aborted after %d consecutive "
                            "failures for user %s: %s",
                            hr_fail_streak, user_id, hr_last_err,
                        )
            # Per-day try/except: keep one malformed Garmin payload from
            # skipping the rest of the window. parse_garmin_recovery is
            # hardened against the known null shapes, but Garmin's schema is
            # undocumented and has regressed before — treat any parse error
            # as "skip this day" rather than aborting the loop.
            try:
                row = parse_garmin_recovery(
                    d, hrv_data=hrv, sleep_data=sleep,
                    training_readiness=tr if days_ago == 0 else None,
                    heart_rates=hr_daily,
                )
            except Exception as e:
                parse_failures += 1
                logger.debug("Recovery parse for %s: skipped (%s)", d, e)
                row = None
            if row:
                recovery_rows.append(row)
            time.sleep(RATE_LIMIT_DELAY)
            if hrv_aborted and sleep_aborted and hr_aborted:
                break

        if total_days and parse_failures >= max(3, total_days // 2):
            logger.warning(
                "Garmin recovery parse failed for %d of %d days (user %s) — "
                "recovery trend will be incomplete",
                parse_failures, total_days, user_id,
            )
    except Exception as e:
        logger.warning("Garmin recovery fetch failed for user %s: %s", user_id, e)

    # DB write is intentionally outside the fetch try/except so a DB error
    # doesn't get mislabelled as a Garmin fetch failure.
    if recovery_rows:
        try:
            # Sleep RHR feeds recovery_data per day for the HRV trend.
            # fitness_data.rest_hr_bpm (the TRIMP reference) is written by
            # write_profile_thresholds above — kept stable, not per-day noisy.
            with db.begin_nested():
                recovery_count = sync_writer.write_recovery(
                    user_id, [], [], {}, db,
                    garmin_recovery=recovery_rows,
                )
        except Exception as e:
            logger.warning(
                "Garmin recovery write failed for user %s: %s", user_id, e,
            )

    # Persist only after every covered month was fetched and parsed. This does
    # not enable Garmin as a delivery target; issue #484 remains the write-
    # feasibility gate.
    plan_count = 0
    if (
        plan_rows is not None
        and provider_account_id is not None
        and profile_account_id is not None
    ):
        try:
            plan_count = _persist_garmin_calendar_snapshot(
                db,
                user_id=user_id,
                provider_account_id=provider_account_id,
                profile_account_id=profile_account_id,
                rows=plan_rows,
                window_start=calendar_window_start,
                window_end=calendar_window_end,
                observed_at=calendar_fetch_started_at,
            )
        except Exception as e:
            logger.warning(
                "Garmin workout calendar write failed for user %s: %s",
                user_id,
                e,
            )

    if credential_generation is not None:
        final_tokens = _serialize_garmin_tokens(client)
        if final_tokens != authenticated_tokens:
            stage_garmin_tokens(
                db,
                user_id=user_id,
                serialized_tokens=final_tokens,
                expected_generation=credential_generation,
                allowed_statuses=SCHEDULABLE_STATUSES,
            )
            if _token_state is not None:
                _token_state["pending_tokens"] = final_tokens

    return {"activities": act_count, "splits": split_count,
            "lactate_threshold": lt_count, "profile": profile_count,
            "daily_metrics": dm_count, "recovery": recovery_count,
            "plan": plan_count}


def _sync_stryd(user_id: str, creds: dict, from_date: str | None,
                db) -> dict:
    """Fetch Stryd data and write directly to DB."""
    from db import sync_writer
    from db.models import PlanDelivery
    from db.plan_reconciliation import record_target_calendar_sync
    from sync.stryd_sync import (
        _login_api, fetch_activities_api, fetch_training_plan_api,
        fetch_current_cp,
    )

    stryd_user_id, token = _login_api(creds["email"], creds["password"])
    start = from_date or (date.today() - timedelta(days=14)).isoformat()

    # Fetch current CP from Stryd profile (rolling calculation, may differ from per-activity)
    current_cp = fetch_current_cp(stryd_user_id, token)

    # Activities (power data)
    status = _get_user_status(user_id)
    activity_rows, _raw = fetch_activities_api(stryd_user_id, token, start)
    total = len(activity_rows)
    with _sync_lock:
        status["stryd"]["progress"] = f"Writing {total} activities..."
    # Add activity_type and source for DB writer
    for row in activity_rows:
        row.setdefault("activity_type", "running")
        row.setdefault("source", "stryd")
        # Fallback activity_id if not provided by API
        if not row.get("activity_id"):
            row["activity_id"] = f"stryd_{row.get('date', '')}_{row.get('start_time', '')}"
    act_count = sync_writer.write_activities(user_id, activity_rows, db)

    # Fetch per-activity splits and per-second samples from the activity detail API.
    # fetch_activity_splits returns both from a single API call — samples are the
    # raw per-second arrays that were previously discarded after lap averaging.
    import time as time_mod
    from sync.stryd_sync import fetch_activity_splits
    all_splits = []
    all_samples = []
    for idx, raw_act in enumerate(_raw):
        act_id = raw_act.get("id")
        if not act_id:
            continue
        with _sync_lock:
            status["stryd"]["progress"] = f"Fetching splits: {idx + 1}/{total}"
        try:
            splits, samples = fetch_activity_splits(str(act_id), token)
            all_splits.extend(splits)
            all_samples.extend(samples)
            time_mod.sleep(0.3)  # Rate limit
        except Exception as e:
            logger.debug("Stryd splits for %s: skipped (%s)", act_id, e)
    split_count = sync_writer.write_splits(user_id, all_splits, db)
    sample_count = sync_writer.write_samples(user_id, all_samples, db)
    logger.debug("Stryd sync: %d splits, %d samples written", split_count, sample_count)

    # CP estimates → fitness_data table (for threshold auto-detection)
    cp_by_date: dict = {}
    for row in activity_rows:
        d = row.get("date")
        cp = row.get("cp_estimate")
        if d and cp and cp != "":
            try:
                cp_by_date[d] = float(cp)  # last per date wins
            except (ValueError, TypeError):
                pass
    # Current profile CP for today (the authoritative rolling value from Stryd)
    if current_cp:
        cp_by_date[date.today().isoformat()] = current_cp
    cp_count = sync_writer.write_cp_estimates(
        user_id,
        cp_by_date,
        source="stryd",
        db=db,
    )

    # Training plan. Derive the athlete's tz from a recent activity so plan
    # dates resolve to the user's local day even when the server runs UTC
    # (Stryd serializes a local-midnight workout as UTC; truncating in UTC
    # drops a day east of UTC).
    user_tz = next((a.get("time_zone") for a in _raw if a.get("time_zone")), None)
    today = date.today()
    farthest_delivery = db.query(PlanDelivery.workout_date).filter(
        PlanDelivery.user_id == user_id,
        PlanDelivery.target == "stryd",
        PlanDelivery.provider_account_id == str(stryd_user_id),
        PlanDelivery.state != "removed",
        PlanDelivery.workout_date >= today,
    ).order_by(PlanDelivery.workout_date.desc()).first()
    farthest_days = (
        (farthest_delivery[0] - today).days
        if farthest_delivery is not None
        else 0
    )
    days_ahead = min(365, max(16, farthest_days + 31))
    calendar_fetch_started_at = datetime.utcnow()
    plan_rows = fetch_training_plan_api(
        stryd_user_id,
        token,
        cp_watts=current_cp,
        days_ahead=days_ahead,
        days_back=2,
        tz_name=user_tz,
    )
    # The raw API window is UTC/server based while Stryd workouts are bucketed
    # to the athlete's local day. Excluding one edge day on each side avoids
    # false deletions caused by that timezone conversion.
    covered_start = today - timedelta(days=1)
    covered_end = today + timedelta(days=days_ahead - 1)
    observed_external_ids = {
        str(row.get("external_id") or "").strip()
        for row in plan_rows
        if str(row.get("external_id") or "").strip()
    }
    snapshot_changes = record_target_calendar_sync(
        db,
        user_id=user_id,
        target="stryd",
        provider_account_id=str(stryd_user_id),
        rows=plan_rows,
        window_start=covered_start,
        window_end=covered_end,
        observed_at=calendar_fetch_started_at,
    )
    if snapshot_changes is None:
        plan_count = 0
        logger.info(
            "Ignored stale Stryd calendar fetch for user=%s started_at=%s",
            user_id,
            calendar_fetch_started_at.isoformat(),
        )
    else:
        plan_count = sync_writer.write_training_plan(
            user_id,
            plan_rows,
            "stryd",
            db,
        )
        plan_count += sync_writer.prune_training_plan_window(
            user_id,
            source="stryd",
            observed_external_ids=observed_external_ids,
            window_start=covered_start,
            window_end=covered_end,
            db=db,
        )

    return {"activities": act_count, "splits": split_count, "cp_estimates": cp_count, "plan": plan_count}


def _sync_strava(user_id: str, creds: dict, from_date: str | None, db) -> dict:
    """Fetch Strava activity data and write directly to DB."""

    import time as time_mod

    from db import sync_writer
    from sync.strava_sync import (
        fetch_activities_api,
        fetch_activity_laps,
        refresh_access_token_if_needed,
    )

    client_id, client_secret = _get_strava_client_config(creds)
    creds, changed = refresh_access_token_if_needed(creds, client_id, client_secret)
    if changed:
        _persist_credentials(user_id, "strava", creds, db)
        # Strava rotates refresh tokens. Commit the rotated credentials before
        # any downstream activity/lap fetch can trigger a rollback.
        _commit_background_sync_provider_changes(user_id, db)

    access_token = creds.get("access_token")
    if not access_token:
        raise RuntimeError("Strava credentials missing access_token")

    start = from_date or (date.today() - timedelta(days=14)).isoformat()
    status = _get_user_status(user_id)

    activity_rows, raw_activities = fetch_activities_api(access_token, start)
    total = len(activity_rows)
    with _sync_lock:
        status["strava"]["progress"] = f"Writing {total} activities..."
    for row in activity_rows:
        row.setdefault("activity_type", "other")
        row.setdefault("source", "strava")
    act_count = sync_writer.write_activities(user_id, activity_rows, db)

    from sync.strava_sync import fetch_activity_streams, parse_activity_stream as parse_strava_stream

    all_splits = []
    all_samples = []
    for idx, raw_act in enumerate(raw_activities):
        activity_id = raw_act.get("id")
        if not activity_id:
            continue
        with _sync_lock:
            status["strava"]["progress"] = f"Fetching laps: {idx + 1}/{total}"
        try:
            all_splits.extend(fetch_activity_laps(str(activity_id), access_token))
            time_mod.sleep(0.2)
        except Exception as exc:
            logger.debug("Strava laps for %s: skipped (%s)", activity_id, exc)
        try:
            streams = fetch_activity_streams(str(activity_id), access_token)
            start_utc = str(raw_act.get("start_date") or "")
            all_samples.extend(parse_strava_stream(str(activity_id), streams, start_utc))
            time_mod.sleep(0.2)
        except Exception as exc:
            logger.info("Strava streams for %s: skipped (%s)", activity_id, exc)
    split_count = sync_writer.write_splits(user_id, all_splits, db)
    sample_count = sync_writer.write_samples(user_id, all_samples, db)
    logger.info("Strava sync: %d splits, %d samples written", split_count, sample_count)

    return {"activities": act_count, "splits": split_count, "samples": sample_count}


def _sync_oura(user_id: str, creds: dict, from_date: str | None,
               db) -> dict:
    """Fetch Oura data and write directly to DB."""
    from db import sync_writer
    from sync.oura_sync import (
        fetch_sleep_data, fetch_daily_sleep_data, fetch_readiness_data,
        parse_sleep_records, parse_daily_sleep_records, parse_readiness_records,
        merge_daily_sleep_score, select_oura_hrv_per_day,
    )

    token = creds["token"]
    end = date.today().isoformat()
    start = from_date or (date.today() - timedelta(days=7)).isoformat()

    # /sleep gives per-sleep-period detail (HRV, RHR, total/deep/REM,
    # efficiency); /daily_sleep gives the once-per-day sleep score
    # (0–100) that the dashboard renders. Merge by date so each day's
    # detail row carries the canonical sleep_score.
    sleep_raw = fetch_sleep_data(token, start, end)
    sleep_rows = parse_sleep_records(sleep_raw)
    daily_sleep_raw = fetch_daily_sleep_data(token, start, end)
    daily_sleep_rows = parse_daily_sleep_records(daily_sleep_raw)
    sleep_rows = merge_daily_sleep_score(sleep_rows, daily_sleep_rows)

    hrv_by_date = select_oura_hrv_per_day(sleep_raw)

    readiness_raw = fetch_readiness_data(token, start, end)
    readiness_rows = parse_readiness_records(readiness_raw)

    # Write directly to DB
    count = sync_writer.write_recovery(
        user_id, readiness_rows, sleep_rows, hrv_by_date, db
    )
    return {"recovery": count}


def _sync_coros(user_id: str, creds: dict, from_date: str | None,
                db) -> dict:
    """Fetch COROS data and write directly to DB."""
    import time as time_mod

    from db import sync_writer
    from sync.coros_sync import (
        refresh_if_needed,
        fetch_activities,
        fetch_activity_detail,
        fetch_activity_detail_data,
        fetch_daily_metrics,
        fetch_fitness_summary,
        parse_activities,
        parse_activity_weather,
        parse_fit_laps,
        parse_fit_stream,
        parse_daily_metrics as parse_daily,
        parse_fitness_summary as parse_fitness,
        mobile_login,
        fetch_sleep,
        parse_sleep,
    )

    email = creds.get("email", "")
    password = creds.get("password", "")
    region = creds.get("region", "us")

    # Build token creds from stored credentials
    token_creds = {
        "access_token": creds.get("access_token", ""),
        "user_id": creds.get("coros_user_id", ""),
        "region": region,
        "timestamp": creds.get("timestamp", 0),
    }
    token_creds, changed = refresh_if_needed(token_creds, email, password)
    logger.info("COROS hub token refresh: changed=%s, timestamp=%s", changed, token_creds.get("timestamp"))
    if changed:
        updated = dict(creds)
        updated["access_token"] = token_creds["access_token"]
        updated["coros_user_id"] = token_creds["user_id"]
        updated["timestamp"] = token_creds["timestamp"]
        _persist_credentials(user_id, "coros", updated, db)
        _commit_background_sync_provider_changes(user_id, db)

    access_token = token_creds["access_token"]
    end = date.today().isoformat()
    start = from_date or (date.today() - timedelta(days=14)).isoformat()

    status = _get_user_status(user_id)

    # Activities — retry with fresh login if token was revoked early
    try:
        raw_activities = fetch_activities(access_token, region, start, end)
    except Exception:
        # Force re-login and retry once
        from sync.coros_sync import login as coros_login
        logger.info("COROS hub token invalid, forcing re-login for user %s", user_id)
        token_creds = coros_login(email, password, region)
        access_token = token_creds["access_token"]
        updated = dict(creds)
        updated["access_token"] = access_token
        updated["coros_user_id"] = token_creds["user_id"]
        updated["timestamp"] = token_creds["timestamp"]
        _persist_credentials(user_id, "coros", updated, db)
        _commit_background_sync_provider_changes(user_id, db)
        raw_activities = fetch_activities(access_token, region, start, end)
    activity_rows = parse_activities(raw_activities)
    for row in activity_rows:
        row.setdefault("activity_type", "other")
        row.setdefault("source", "coros")
    rows_by_id = {
        str(row.get("activity_id")): row
        for row in activity_rows
        if row.get("activity_id")
    }
    weather_activities_by_id = {}
    for raw_act in raw_activities:
        act_id = str(raw_act.get("labelId") or raw_act.get("activityId") or "")
        row = rows_by_id.get(act_id)
        if row and row.get("activity_type") in {"running", "trail_running"}:
            weather_activities_by_id[act_id] = raw_act
    needed_weather_ids = _activity_ids_needing_environment(
        user_id, weather_activities_by_id, db,
    )
    weather_activities = [
        (activity_id, raw_activity)
        for activity_id, raw_activity in weather_activities_by_id.items()
        if activity_id in needed_weather_ids
    ]
    weather_failures = 0
    weather_abort: Exception | None = None
    from requests import RequestException

    for idx, (act_id, raw_act) in enumerate(weather_activities):
        with _sync_lock:
            status.setdefault("coros", {})["progress"] = (
                f"Fetching weather: {idx + 1}/{len(weather_activities)}"
            )
        try:
            detail = fetch_activity_detail_data(
                access_token,
                region,
                act_id,
                raw_act.get("sportType"),
            )
            rows_by_id[act_id].update(parse_activity_weather(detail))
        except RequestException as e:
            status_code = _exception_status_code(e)
            if status_code in {401, 403, 429}:
                raise
            if status_code not in {400, 404}:
                weather_abort = e
                break
            weather_failures += 1
            logger.debug("COROS weather for %s: skipped (%s)", act_id, e)
        except RuntimeError as e:
            if str(e).startswith("COROS auth error:"):
                raise
            weather_failures += 1
            logger.debug("COROS weather for %s: skipped (%s)", act_id, e)
        except ValueError as e:
            weather_failures += 1
            logger.debug("COROS weather for %s: skipped (%s)", act_id, e)
        time_mod.sleep(0.3)
    if weather_abort is not None:
        logger.warning(
            "COROS weather enrichment stopped for user %s: %s",
            user_id,
            weather_abort,
        )
    elif (
        weather_activities
        and weather_failures >= max(3, len(weather_activities) // 2)
    ):
        logger.warning(
            "COROS weather fetch failed for %d of %d eligible activities "
            "(user %s) — heat-adaptation evidence will be incomplete",
            weather_failures, len(weather_activities), user_id,
        )
    act_count = sync_writer.write_activities(user_id, activity_rows, db)

    # Splits and per-second samples from the same activity detail call.
    # parse_activity_stream() reads trackPoints when present; returns []
    # otherwise (UNVERIFIED field names — needs real COROS data to confirm).
    all_splits = []
    all_samples = []
    total = len(raw_activities)
    for idx, raw_act in enumerate(raw_activities):
        act_id = str(raw_act.get("labelId") or raw_act.get("activityId") or "")
        if not act_id:
            continue
        with _sync_lock:
            status.setdefault("coros", {})["progress"] = f"Fetching splits: {idx + 1}/{total}"
        try:
            sport_type = raw_act.get("sportType")
            fit_bytes = fetch_activity_detail(access_token, region, act_id, sport_type)
            if fit_bytes:
                all_splits.extend(parse_fit_laps(act_id, fit_bytes))
                all_samples.extend(parse_fit_stream(act_id, fit_bytes))
            time_mod.sleep(0.3)
        except Exception as e:
            logger.debug("COROS splits for %s: skipped (%s)", act_id, e)
    split_count = sync_writer.write_splits(user_id, all_splits, db)
    sample_count = sync_writer.write_samples(user_id, all_samples, db)
    logger.debug("COROS sync: %d splits, %d samples written", split_count, sample_count)

    # Daily metrics (HRV, resting HR, training load)
    # Fetch a wider window (90 days) to ensure enough HRV readings for
    # baseline analysis (requires ≥5 data points).
    dm_count = 0
    recovery_count = 0
    dm_start = (date.today() - timedelta(days=90)).isoformat()
    try:
        raw_daily = fetch_daily_metrics(access_token, region, dm_start, end)
        daily_rows = parse_daily(raw_daily)

        # Write recovery data (HRV, resting HR)
        recovery_rows = [
            r for r in daily_rows
            if r.get("hrv_ms") or r.get("resting_hr")
        ]
        if recovery_rows:
            recovery_count = sync_writer.write_recovery(
                user_id, [], [], {}, db,
                garmin_recovery=recovery_rows,
                recovery_source="coros",
            )
    except Exception as e:
        logger.warning("COROS daily metrics fetch failed for user %s: %s", user_id, e)

    # Sleep data (via mobile API)
    sleep_count = 0
    try:
        mobile_token = creds.get("mobile_access_token", "")
        mobile_ts = int(creds.get("mobile_timestamp", 0))
        # Mobile API tokens expire after ~1 hour — always re-login
        if not mobile_token or (time_mod.time() - mobile_ts) > 3500:
            mobile_creds = mobile_login(email, password, region)
            mobile_token = mobile_creds["mobile_access_token"]
            updated = dict(creds)
            updated["mobile_access_token"] = mobile_token
            updated["mobile_timestamp"] = mobile_creds["mobile_timestamp"]
            _persist_credentials(user_id, "coros", updated, db)
            _commit_background_sync_provider_changes(user_id, db)

        raw_sleep = fetch_sleep(mobile_token, region, dm_start, end)
        sleep_rows = parse_sleep(raw_sleep)
        logger.info("COROS sleep: %d nights fetched for user %s, latest dates: %s",
                     len(sleep_rows), user_id,
                     [r["date"] for r in sleep_rows[:5]] if sleep_rows else [])

        if sleep_rows:
            # Merge sleep into recovery rows: write_recovery handles upsert
            sleep_recovery = []
            for sr in sleep_rows:
                row = {"date": sr["date"], "source": "coros"}
                if sr.get("sleep_score"):
                    row["sleep_score"] = sr["sleep_score"]
                if sr.get("total_sleep_sec"):
                    # Convert to hours for write_recovery compatibility
                    row["total_sleep_hours"] = str(round(int(sr["total_sleep_sec"]) / 3600, 2))
                if sr.get("deep_sleep_sec"):
                    row["deep_sleep_sec"] = sr["deep_sleep_sec"]
                if sr.get("rem_sleep_sec"):
                    row["rem_sleep_sec"] = sr["rem_sleep_sec"]
                sleep_recovery.append(row)
            sleep_count = sync_writer.write_recovery(
                user_id, [], [], {}, db,
                garmin_recovery=sleep_recovery,
                recovery_source="coros",
            )
    except BackgroundProcessingAuthorizationLost:
        raise
    except Exception as e:
        logger.warning("COROS sleep fetch failed for user %s: %s", user_id, e)

    # Fitness summary (VO2max, LTHR)
    profile_count = 0
    try:
        fitness_raw = fetch_fitness_summary(access_token, region)
        fitness_parsed = parse_fitness(fitness_raw)
        if fitness_parsed:
            profile_count = sync_writer.write_profile_thresholds(
                user_id, fitness_parsed, db,
                source="coros",
            )
    except Exception as e:
        logger.warning("COROS fitness summary fetch failed for user %s: %s", user_id, e)

    return {
        "activities": act_count,
        "splits": split_count,
        "recovery": recovery_count + sleep_count,
        "profile": profile_count,
    }


@router.get("/sync/status")
def get_sync_status(
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Return current sync status for this user's connected platforms."""
    from api.stryd_access import stryd_connection_enabled
    from db.models import UserConnection
    from db.sync_scheduler import ACTIVE_CONNECTION_STATUSES

    stryd_enabled = stryd_connection_enabled(
        db,
        user_id=viewer_user_id,
    )

    # Snapshot runtime status under lock to avoid reading partial updates.
    # _get_user_status acquires _sync_lock internally, so call it outside
    # our own `with _sync_lock` — threading.Lock is not reentrant.
    status = _get_user_status(user_id)
    with _sync_lock:
        runtime_snapshot = {src: dict(info) for src, info in status.items()}

    # Merge with DB connection info (last_sync from DB is more reliable)
    connections = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
    ).all()
    result = {}
    for conn in connections:
        src = conn.platform
        if src == "stryd" and not stryd_enabled:
            continue
        runtime = runtime_snapshot.get(src, {})
        result[src] = {
            "status": runtime.get("status", "idle"),
            "last_sync": utc_isoformat(conn.last_sync) or runtime.get("last_sync"),
            "error": runtime.get("error"),
            "connected": conn.status in ACTIVE_CONNECTION_STATUSES,
            "progress": runtime.get("progress"),
        }

    # Include platforms with env var creds but no DB connection (dev mode)
    for src in _DEFAULT_SOURCES:
        if src == "stryd" and not stryd_enabled:
            continue
        if src not in result:
            creds = _get_credentials(user_id, src, db)
            if creds:
                runtime = runtime_snapshot.get(src, {})
                result[src] = {
                    "status": runtime.get("status", "idle"),
                    "last_sync": runtime.get("last_sync"),
                    "error": runtime.get("error"),
                    "connected": True,
                }

    return result


@router.post("/sync/{source}")
def trigger_sync(
    source: str,
    background_tasks: BackgroundTasks,
    body: SyncRequest | None = None,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Trigger sync for a single source using the user's stored credentials."""
    if source not in _DEFAULT_SOURCES:
        return {"status": "error", "message": f"Unknown source: {source}"}
    if source == "stryd":
        from api.stryd_access import require_stryd_connection_enabled

        require_stryd_connection_enabled(db, user_id=user_id)

    sync_snapshot = _sync_credentials_snapshot(
        user_id,
        source,
        db,
    )
    if sync_snapshot is None:
        return {
            "status": "error",
            "message": (
                f"No active credentials for {source}. "
                "Connect it in Settings first."
            ),
        }
    creds, connection_generation = sync_snapshot

    status = _get_user_status(user_id)
    with _sync_lock:
        if status.get(source, {}).get("status") == "syncing":
            return {"status": "already_syncing", "source": source}
        status[source] = {"status": "syncing", "last_sync": None, "error": None}

    from_date = body.from_date if body else None
    background_tasks.add_task(
        _run_sync,
        user_id,
        source,
        creds,
        from_date,
        connection_generation if source == "garmin" else None,
    )
    return {"status": "started", "source": source}


@router.post("/sync")
def trigger_sync_all(
    background_tasks: BackgroundTasks,
    body: SyncRequest | None = None,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Trigger sync for all connected sources."""
    from_date = body.from_date if body else None
    started = []
    status = _get_user_status(user_id)

    for source in _DEFAULT_SOURCES:
        if source == "stryd":
            from api.stryd_access import stryd_connection_enabled

            if not stryd_connection_enabled(db, user_id=user_id):
                continue
        sync_snapshot = _sync_credentials_snapshot(
            user_id,
            source,
            db,
        )
        if sync_snapshot is None:
            continue
        creds, connection_generation = sync_snapshot
        with _sync_lock:
            if status.get(source, {}).get("status") == "syncing":
                continue
            status[source] = {"status": "syncing", "last_sync": None, "error": None}
        background_tasks.add_task(
            _run_sync,
            user_id,
            source,
            creds,
            from_date,
            connection_generation if source == "garmin" else None,
        )
        started.append(source)

    return {"status": "started", "sources": started}
