"""Cross-worker account lifecycle leases for outbound user-data processing."""
from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import threading
from collections.abc import Iterator

import portalocker

from db.session import get_data_dir

logger = logging.getLogger(__name__)


class AccountLifecycleBusy(RuntimeError):
    """Raised when an account lifecycle lease cannot be acquired in time."""


_PROCESS_LOCKS = tuple(threading.RLock() for _ in range(64))
_lease_depth = threading.local()


def _lease_path(user_id: str) -> str:
    """Return the privacy-safe cross-worker lock path for one account."""
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return os.path.join(
        os.path.abspath(get_data_dir()),
        ".account_lifecycle_locks",
        f"{digest}.lock",
    )


@contextlib.contextmanager
def account_lifecycle_lease(
    user_id: str,
    *,
    timeout_seconds: float = 60.0,
) -> Iterator[None]:
    """Serialize account deletion with outbound processing for one user."""
    if not user_id:
        raise ValueError("user_id is required")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    lock_path = _lease_path(user_id)
    process_lock = _PROCESS_LOCKS[
        int(hashlib.sha256(lock_path.encode("utf-8")).hexdigest()[:8], 16)
        % len(_PROCESS_LOCKS)
    ]
    if not process_lock.acquire(timeout=timeout_seconds):
        raise AccountLifecycleBusy("account lifecycle lease is busy")
    try:
        depths = getattr(_lease_depth, "paths", None)
        if depths is None:
            depths = {}
            _lease_depth.paths = depths
        current_depth = int(depths.get(lock_path, 0))
        if current_depth:
            depths[lock_path] = current_depth + 1
            try:
                yield
            finally:
                depths[lock_path] = current_depth
            return

        try:
            os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        except OSError as exc:
            raise AccountLifecycleBusy(
                "account lifecycle lease is unavailable"
            ) from exc
        depths[lock_path] = 1
        file_lock = portalocker.Lock(
            lock_path,
            mode="a",
            timeout=timeout_seconds,
        )
        try:
            try:
                file_lock.acquire()
            except (OSError, portalocker.exceptions.LockException) as exc:
                raise AccountLifecycleBusy(
                    "account lifecycle lease is busy"
                ) from exc
            try:
                yield
            finally:
                _release_file_lock(file_lock)
        finally:
            depths.pop(lock_path, None)
    finally:
        process_lock.release()


def _release_file_lock(file_lock: portalocker.Lock) -> None:
    """Release without replacing a completed protected operation with an error."""
    try:
        file_lock.release()
    except Exception:
        logger.exception("Account lifecycle lease release failed")
        handle = getattr(file_lock, "fh", None)
        if handle is not None:
            try:
                handle.close()
            except OSError:
                logger.exception(
                    "Account lifecycle lease handle close failed"
                )
            finally:
                file_lock.fh = None
