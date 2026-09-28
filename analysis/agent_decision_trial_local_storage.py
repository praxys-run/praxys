"""Single-host SQLite cohort storage for a future trusted local task broker."""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import stat

from pydantic import ValidationError

from analysis.agent_decision_trial import (
    CohortState,
    TrialPolicy,
    TrialUnavailable,
    _check_monotonic,
    _check_state,
    new_cohort,
)


_MAX_STATE_BYTES = 1024 * 1024


class LocalSQLiteCohortStore:
    """One pre-provisioned POSIX cohort shared across one host's worktrees."""

    def __init__(self, path: Path, policy: TrialPolicy) -> None:
        self._path = path.absolute()
        self._policy = policy

    @classmethod
    def provision(cls, path: Path, policy: TrialPolicy) -> "LocalSQLiteCohortStore":
        """Create an inert cohort only in an existing, operator-owned directory."""
        if policy.status != "disabled":
            raise TrialUnavailable("a new cohort must be provisioned while disabled")
        cls._check_parent(path)
        try:
            descriptor = os.open(
                path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
            )
            os.close(descriptor)
        except OSError as error:
            raise TrialUnavailable("the cohort file cannot be exclusively provisioned") from error
        store = cls(path, policy)
        try:
            with closing(store._connect()) as connection, connection:
                connection.execute(
                    "CREATE TABLE cohort (id INTEGER PRIMARY KEY CHECK (id = 1), "
                    "revision INTEGER NOT NULL, state TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO cohort (id, revision, state) VALUES (1, 0, ?)",
                    (new_cohort(policy).model_dump_json(),),
                )
        except sqlite3.Error as error:
            raise TrialUnavailable("cohort provisioning failed; no admission permitted") from error
        return store

    @staticmethod
    def _check_parent(path: Path) -> None:
        try:
            parent = path.parent.lstat()
            resolved_parent = path.parent.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise TrialUnavailable("the private cohort directory is unavailable") from error
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or parent.st_mode & 0o077
            or path.parent.absolute() != resolved_parent
        ):
            raise TrialUnavailable("the cohort directory must be private and owned by this user")

    def _connect(self) -> sqlite3.Connection:
        self._check_parent(self._path)
        try:
            file_info = self._path.lstat()
        except OSError as error:
            raise TrialUnavailable("the cohort file has not been provisioned") from error
        if (
            not stat.S_ISREG(file_info.st_mode)
            or file_info.st_uid != os.getuid()
            or file_info.st_mode & 0o077
            or file_info.st_nlink != 1
        ):
            raise TrialUnavailable("the cohort file must be private and owned by this user")
        try:
            connection = sqlite3.connect(
                f"{self._path.as_uri()}?mode=rw",
                uri=True,
                isolation_level=None,
                timeout=2,
            )
        except sqlite3.Error as error:
            raise TrialUnavailable("cohort storage is unavailable; candidate withheld") from error
        try:
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except sqlite3.Error as error:
            connection.close()
            raise TrialUnavailable("cohort storage is unavailable; candidate withheld") from error

    def _read_row(self, connection: sqlite3.Connection) -> tuple[int, CohortState]:
        row = connection.execute("SELECT revision, state FROM cohort WHERE id = 1").fetchone()
        if row is None or type(row[0]) is not int or row[0] < 0 or type(row[1]) is not str:
            raise TrialUnavailable("the cohort record is invalid")
        if len(row[1].encode("utf-8")) > _MAX_STATE_BYTES:
            raise TrialUnavailable("the cohort record exceeds its size limit")
        try:
            state = CohortState.model_validate_json(row[1])
            _check_state(self._policy, state)
        except (ValidationError, ValueError) as error:
            raise TrialUnavailable("the cohort record is invalid") from error
        return row[0], state

    def read(self) -> tuple[str, CohortState]:
        try:
            with closing(self._connect()) as connection:
                revision, state = self._read_row(connection)
            return str(revision), state
        except sqlite3.Error as error:
            raise TrialUnavailable("cohort storage is unavailable; candidate withheld") from error

    def compare_and_swap(self, revision: str, state: CohortState) -> bool:
        if not revision.isdecimal():
            raise TrialUnavailable("a cohort write requires a revision")
        try:
            with closing(self._connect()) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                current_revision, previous = self._read_row(connection)
                if str(current_revision) != revision:
                    return False
                try:
                    serialized = state.model_dump_json()
                    updated = CohortState.model_validate_json(serialized)
                    _check_state(self._policy, updated)
                except (ValidationError, ValueError) as error:
                    raise TrialUnavailable("the cohort update is invalid") from error
                _check_monotonic(previous, updated)
                if (
                    len(updated.assignments) > len(previous.assignments)
                    and self._policy.status != "active"
                ):
                    raise TrialUnavailable("a disabled policy cannot admit tasks")
                if len(serialized.encode("utf-8")) > _MAX_STATE_BYTES:
                    raise TrialUnavailable("the cohort update exceeds its size limit")
                result = connection.execute(
                    "UPDATE cohort SET revision = ?, state = ? WHERE id = 1 AND revision = ?",
                    (current_revision + 1, serialized, current_revision),
                )
                if result.rowcount != 1:
                    raise TrialUnavailable("cohort revision changed; candidate withheld")
            return True
        except sqlite3.Error as error:
            raise TrialUnavailable("cohort write outcome is ambiguous; candidate withheld") from error
