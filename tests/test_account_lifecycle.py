"""Tests for cross-worker account lifecycle serialization."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from api import account_deletion
from db import account_lifecycle


def test_same_account_lease_times_out_fail_closed(tmp_path, monkeypatch):
    """A second worker must not bypass an active account lifecycle lease."""
    monkeypatch.setattr(account_lifecycle, "get_data_dir", lambda: str(tmp_path))
    entered = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        with account_lifecycle.account_lifecycle_lease(
            "user-1",
            timeout_seconds=1.0,
        ):
            entered.set()
            release.wait(timeout=2.0)

    thread = threading.Thread(target=_holder)
    thread.start()
    assert entered.wait(timeout=1.0)
    try:
        with pytest.raises(account_lifecycle.AccountLifecycleBusy):
            with account_lifecycle.account_lifecycle_lease(
                "user-1",
                timeout_seconds=0.05,
            ):
                pytest.fail("busy account lease was bypassed")
    finally:
        release.set()
        thread.join(timeout=1.0)
    assert not thread.is_alive()


def test_account_lifecycle_lease_is_reentrant(tmp_path, monkeypatch):
    """Nested deletion helpers may safely reuse the current account lease."""
    monkeypatch.setattr(account_lifecycle, "get_data_dir", lambda: str(tmp_path))

    with account_lifecycle.account_lifecycle_lease("user-1"):
        with account_lifecycle.account_lifecycle_lease("user-1"):
            pass


def test_release_error_does_not_replace_completed_operation(
    tmp_path,
    monkeypatch,
):
    """An SMB unlock anomaly must not make committed deletion look failed."""
    monkeypatch.setattr(account_lifecycle, "get_data_dir", lambda: str(tmp_path))

    class Handle:
        closed = False

        def close(self) -> None:
            self.closed = True

    class Lock:
        def __init__(self) -> None:
            self.fh = Handle()

        def acquire(self):
            return self.fh

        def release(self) -> None:
            raise OSError("unlock failed")

    lock = Lock()
    monkeypatch.setattr(
        account_lifecycle.portalocker,
        "Lock",
        lambda *_args, **_kwargs: lock,
    )

    with account_lifecycle.account_lifecycle_lease("user-1"):
        pass

    assert lock.fh is None


def test_delete_user_account_holds_lifecycle_lease(monkeypatch):
    """The public deletion entry point must fence its complete mutation."""
    events: list[str] = []
    expected = account_deletion.AccountDeletionResult(
        email="athlete@example.com",
        deleted_user_ids=["user-1"],
    )

    @contextmanager
    def _lease(user_id: str, *, timeout_seconds: float):
        assert user_id == "user-1"
        assert timeout_seconds == 60.0
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    def _delete(_db, user_id: str, *, enforce_last_admin_guard: bool):
        assert user_id == "user-1"
        assert enforce_last_admin_guard is True
        events.append("delete")
        return expected

    monkeypatch.setattr(account_deletion, "account_lifecycle_lease", _lease)
    monkeypatch.setattr(account_deletion, "_delete_user_account_locked", _delete)

    result = account_deletion.delete_user_account(
        Mock(),
        "user-1",
        enforce_last_admin_guard=True,
    )

    assert result == expected
    assert events == ["enter", "delete", "exit"]


def test_delete_user_account_rejects_busy_lifecycle(monkeypatch):
    """Deletion must fail explicitly when the account fence is unavailable."""
    db = Mock()

    @contextmanager
    def _busy_lease(_user_id: str, *, timeout_seconds: float):
        raise account_lifecycle.AccountLifecycleBusy("busy")
        yield

    monkeypatch.setattr(
        account_deletion,
        "account_lifecycle_lease",
        _busy_lease,
    )

    with pytest.raises(HTTPException) as exc_info:
        account_deletion.delete_user_account(
            db,
            "user-1",
            enforce_last_admin_guard=False,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "ACCOUNT_DELETE_BUSY"
    db.rollback.assert_called_once_with()
