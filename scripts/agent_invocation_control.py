"""Cooperative CLI and local ledger for agent invocation control."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.agentic_invocation_control import (  # noqa: E402
    APPROVED_MODES,
    DECISION_REASONS,
    MACHINE_REASON_CODES,
    POLICY_REASONS,
    POLICY_VERSION,
    SCHEMA_VERSION,
    AdmissionFacts,
    InvocationLimits,
    evaluate_admission,
    format_identity,
    is_valid_fingerprint,
    is_valid_identity,
)
from analysis.agentic_task_routing import TaskClassification, TaskRoute, route_task  # noqa: E402

POLICY_PATH = ROOT / 'config' / 'agent-invocation-control.json'
LEDGER_SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_INVALID = 2
EXIT_CONTRACT = 3
EXIT_LEDGER = 4
EXIT_MODE = 5


class RequestFailure(ValueError):
    """A request does not match the versioned machine contract."""


class ContractFailure(RuntimeError):
    """The recomputed Work Contract is unavailable or mismatched."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class StateMissing(RuntimeError):
    """The explicitly initialized local ledger does not exist."""


class StateCorrupt(RuntimeError):
    """The ledger is structurally corrupt or incomplete."""


class StateUnsupported(RuntimeError):
    """The readable ledger has an unsupported schema or policy version."""


class IdentityConflict(RuntimeError):
    """An opaque identity conflicts with its durable binding."""


class RecoveryRequired(RuntimeError):
    """A parent cannot terminate before its active children."""


class FinishConflict(RuntimeError):
    """A terminal transition conflicts with an existing terminal state."""


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _response(command: str, reason_code: str, **values: object) -> dict[str, object]:
    if reason_code not in MACHINE_REASON_CODES:
        raise ValueError('reason code is outside the v1 machine schema')
    policy_reason = values.get('policy_reason')
    if policy_reason is not None and policy_reason not in DECISION_REASONS:
        raise ValueError('policy reason is outside the v1 decision schema')
    payload: dict[str, object] = {
        'schema_version': SCHEMA_VERSION,
        'policy_version': POLICY_VERSION,
        'command': command,
        'reason_code': reason_code,
    }
    payload.update(values)
    return payload


def _emit(payload: dict[str, object], exit_code: int) -> NoReturn:
    print(json.dumps(payload, sort_keys=True, separators=(',', ':')))
    raise SystemExit(exit_code)


def _require_exact_keys(request: dict[str, object], required: set[str]) -> None:
    if set(request) != required:
        raise RequestFailure('request keys do not match schema v1')


def _read_request() -> dict[str, object]:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RequestFailure('request is not valid JSON') from exc
    if not isinstance(payload, dict):
        raise RequestFailure('request must be a JSON object')
    if payload.get('schema_version') != SCHEMA_VERSION:
        raise RequestFailure('unsupported request schema')
    if payload.get('command') not in {
        'init', 'new_identity', 'admit', 'finish', 'recover',
        'kill_switch', 'status',
    }:
        raise RequestFailure('unsupported command')
    return payload


def _load_policy() -> InvocationLimits:
    try:
        payload = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractFailure('policy_unavailable') from exc
    expected_keys = {
        'schema_version', 'policy_version', 'status', 'default_mode',
        'approved_modes', 'enforcement_approved', 'ledger_schema_version',
        'limits',
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise ContractFailure('policy_unavailable')
    if (
        payload['schema_version'] != SCHEMA_VERSION
        or payload['policy_version'] != POLICY_VERSION
        or payload['status'] != 'instrument-shadow-only'
        or payload['default_mode'] != 'instrument'
        or payload['approved_modes'] != list(APPROVED_MODES)
        or payload['enforcement_approved'] is not False
        or payload['ledger_schema_version'] != LEDGER_SCHEMA_VERSION
        or not isinstance(payload['limits'], dict)
    ):
        raise ContractFailure('policy_unavailable')
    try:
        limits = InvocationLimits.from_mapping(payload['limits'])
    except ValueError as exc:
        raise ContractFailure('policy_unavailable') from exc
    if limits != InvocationLimits(6, 8, 32, 3, 1, 2):
        raise ContractFailure('policy_unavailable')
    return limits


def _git_common_dir() -> Path:
    try:
        completed = subprocess.run(
            ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StateMissing from exc
    path = Path(completed.stdout.strip()).resolve()
    if not path.is_dir():
        raise StateMissing
    return path


def _ledger_path() -> Path:
    return _git_common_dir() / 'praxys' / 'agent-invocation-control-v1.sqlite3'


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RequestFailure(f'{label} must be a string list')
    if len(value) != len(set(value)):
        raise RequestFailure(f'{label} must be unique')
    return value


def _validate_contract(request: dict[str, object]) -> tuple[TaskRoute, str]:
    strings = (
        request['primary_object'], request['classification_digest'],
        request['route_digest'], request['slot_role'],
    )
    if not all(isinstance(value, str) for value in strings):
        raise RequestFailure('Work Contract fields must be strings')
    impacts = _string_list(request['impacts'], 'impacts')
    risks = _string_list(request['risk_triggers'], 'risk_triggers')
    try:
        route = route_task(
            TaskClassification(
                primary_object=str(request['primary_object']),
                impacts=impacts,
                risk_triggers=risks,
            )
        )
    except Exception as exc:
        raise ContractFailure('work_contract_unavailable') from exc
    if (
        route.classification_digest != request['classification_digest']
        or route.route_digest != request['route_digest']
    ):
        raise ContractFailure('work_contract_mismatch')
    roles = {
        route.lead_role,
        *route.contributor_roles,
        *route.executor_roles,
        *route.verifier_roles,
        *route.outcome_observer_roles,
    }
    slot_role = str(request['slot_role'])
    if slot_role not in roles:
        raise RequestFailure('slot role is not in the Work Contract')
    return route, slot_role


def _validate_identity_fields(request: dict[str, object]) -> None:
    for field, kind in (
        ('contract_id', 'contract'), ('slot_id', 'slot'),
        ('generation_id', 'generation'), ('logical_id', 'logical'),
        ('attempt_id', 'attempt'),
    ):
        if not is_valid_identity(request[field], kind):
            raise RequestFailure(f'invalid {field}')
    parent = request['parent_attempt_id']
    if parent is not None and not is_valid_identity(parent, 'attempt'):
        raise RequestFailure('invalid parent_attempt_id')
    retry = request['retry_fingerprint']
    if retry is not None and not is_valid_fingerprint(retry):
        raise RequestFailure('invalid retry_fingerprint')


def _machine_reason(mode: str, policy_reason: str) -> str:
    if policy_reason == 'kill_switch_active':
        return 'kill_switch_active'
    if mode == 'instrument':
        return 'instrument_recorded'
    if policy_reason == 'admit':
        return 'shadow_would_admit'
    if policy_reason == 'ancestry_cycle':
        return 'shadow_would_deny_cycle'
    return 'shadow_would_deny_policy_limit'


_SQL_POLICY_REASONS = ', '.join(f"'{reason}'" for reason in POLICY_REASONS)
_SCHEMA_COLUMNS = {
    'metadata': ('key', 'value'),
    'control': ('singleton', 'kill_switch', 'updated_at_ms'),
    'contracts': (
        'contract_id', 'classification_digest', 'route_digest',
        'routing_version', 'operating_model_version', 'created_at_ms',
    ),
    'slots': ('slot_id', 'contract_id', 'role_id', 'created_at_ms'),
    'generations': (
        'generation_id', 'contract_id', 'slot_id', 'created_at_ms',
    ),
    'logical_invocations': (
        'logical_id', 'contract_id', 'slot_id', 'created_at_ms',
    ),
    'decisions': (
        'decision_id', 'contract_id', 'slot_id', 'generation_id', 'logical_id',
        'attempt_id', 'parent_attempt_id', 'mode', 'policy_reason',
        'would_reject', 'launch_authorized', 'decided_at_ms',
    ),
    'attempts': (
        'attempt_id', 'decision_id', 'contract_id', 'slot_id', 'generation_id',
        'logical_id', 'parent_attempt_id', 'retry_fingerprint',
        'terminal_fingerprint', 'lifecycle_status', 'depth', 'admitted_at_ms',
        'finished_at_ms',
    ),
}
_SCHEMA_INDEXES = {
    'attempts_active_contract',
    'attempts_active_match',
    'attempts_parent_status',
    'attempts_slot_finished',
    'decisions_contract_reason',
}
_SCHEMA = f"""
CREATE TABLE metadata (
    key TEXT PRIMARY KEY CHECK (key IN ('schema_version', 'policy_version')),
    value TEXT NOT NULL
) STRICT;
CREATE TABLE control (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    kill_switch INTEGER NOT NULL CHECK (kill_switch IN (0, 1)),
    updated_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE contracts (
    contract_id TEXT PRIMARY KEY,
    classification_digest TEXT NOT NULL,
    route_digest TEXT NOT NULL,
    routing_version TEXT NOT NULL,
    operating_model_version TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE slots (
    slot_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    role_id TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE generations (
    generation_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    created_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE logical_invocations (
    logical_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    created_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    generation_id TEXT NOT NULL,
    logical_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL UNIQUE,
    parent_attempt_id TEXT,
    mode TEXT NOT NULL CHECK (mode IN ('instrument', 'shadow')),
    policy_reason TEXT NOT NULL CHECK (policy_reason IN (
        {_SQL_POLICY_REASONS}
    )),
    would_reject INTEGER NOT NULL CHECK (would_reject IN (0, 1)),
    launch_authorized INTEGER NOT NULL CHECK (launch_authorized IN (0, 1)),
    decided_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE attempts (
    attempt_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(decision_id),
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    generation_id TEXT NOT NULL REFERENCES generations(generation_id),
    logical_id TEXT NOT NULL REFERENCES logical_invocations(logical_id),
    parent_attempt_id TEXT REFERENCES attempts(attempt_id),
    retry_fingerprint TEXT,
    terminal_fingerprint TEXT,
    lifecycle_status TEXT NOT NULL CHECK (
        lifecycle_status IN ('active', 'succeeded', 'failed', 'recovered')
    ),
    depth INTEGER NOT NULL CHECK (depth >= 1),
    admitted_at_ms INTEGER NOT NULL,
    finished_at_ms INTEGER
) STRICT;
CREATE INDEX attempts_active_contract
    ON attempts(contract_id, lifecycle_status);
CREATE INDEX attempts_active_match
    ON attempts(contract_id, logical_id, slot_id, generation_id, lifecycle_status);
CREATE INDEX attempts_parent_status
    ON attempts(parent_attempt_id, lifecycle_status);
CREATE INDEX attempts_slot_finished ON attempts(slot_id, finished_at_ms);
CREATE INDEX decisions_contract_reason ON decisions(contract_id, policy_reason);
"""


class Ledger:
    """Concurrency-safe local SQLite lifecycle ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> bool:
        """Create the v1 ledger once, or validate an existing ledger."""
        if self.path.exists():
            connection = self._connect()
            connection.close()
            return False
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        try:
            descriptor = os.open(
                self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            os.close(descriptor)
            connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            connection.execute('PRAGMA busy_timeout=30000')
            mode = connection.execute('PRAGMA journal_mode=WAL').fetchone()
            if mode is None or mode[0].lower() != 'wal':
                raise StateCorrupt
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('BEGIN IMMEDIATE')
            for statement in _SCHEMA.split(';'):
                if statement.strip():
                    connection.execute(statement)
            connection.executemany(
                'INSERT INTO metadata(key, value) VALUES (?, ?)',
                (
                    ('schema_version', str(LEDGER_SCHEMA_VERSION)),
                    ('policy_version', POLICY_VERSION),
                ),
            )
            connection.execute(
                'INSERT INTO control(singleton, kill_switch, updated_at_ms) VALUES (1, 0, ?)',
                (_now_ms(),),
            )
            connection.commit()
            self.path.chmod(0o600)
            self._validate(connection)
            connection.close()
            return True
        except (sqlite3.Error, OSError) as exc:
            raise StateCorrupt from exc

    def _connect(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise StateMissing
        try:
            connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA busy_timeout=30000')
            connection.execute('PRAGMA foreign_keys=ON')
            mode = connection.execute('PRAGMA journal_mode=WAL').fetchone()
            if mode is None or mode[0].lower() != 'wal':
                raise StateCorrupt
            self._validate(connection)
            return connection
        except (sqlite3.Error, OSError, UnicodeError) as exc:
            raise StateCorrupt from exc

    @staticmethod
    def _validate(connection: sqlite3.Connection) -> None:
        try:
            integrity = connection.execute('PRAGMA quick_check').fetchone()
            metadata_columns = tuple(
                row[1] for row in connection.execute('PRAGMA table_info(metadata)')
            )
            if (
                integrity is None or integrity[0] != 'ok'
                or metadata_columns != _SCHEMA_COLUMNS['metadata']
            ):
                raise StateCorrupt
            metadata = dict(connection.execute('SELECT key, value FROM metadata'))
            if set(metadata) != {'schema_version', 'policy_version'}:
                raise StateCorrupt
            if metadata != {
                'schema_version': str(LEDGER_SCHEMA_VERSION),
                'policy_version': POLICY_VERSION,
            }:
                raise StateUnsupported

            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            indexes = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'index' AND sql IS NOT NULL"
                )
            }
            columns = {
                table: tuple(
                    row[1]
                    for row in connection.execute(f'PRAGMA table_info({table})')
                )
                for table in _SCHEMA_COLUMNS
            }
            foreign_keys = connection.execute('PRAGMA foreign_keys').fetchone()
            control = connection.execute(
                'SELECT kill_switch FROM control WHERE singleton = 1'
            ).fetchone()
            if (
                tables != set(_SCHEMA_COLUMNS)
                or indexes != _SCHEMA_INDEXES
                or columns != _SCHEMA_COLUMNS
                or foreign_keys is None or foreign_keys[0] != 1
                or control is None or control[0] not in (0, 1)
            ):
                raise StateCorrupt
        except sqlite3.Error as exc:
            raise StateCorrupt from exc

    @staticmethod
    def _bind(
        connection: sqlite3.Connection,
        table: str,
        identity_column: str,
        identity: str,
        expected: tuple[object, ...],
        columns: tuple[str, ...],
        insert_values: tuple[object, ...],
    ) -> bool:
        selected_columns = ','.join(columns)
        selected = connection.execute(
            f'SELECT {selected_columns} FROM {table} WHERE {identity_column} = ?',
            (identity,),
        ).fetchone()
        if selected is None:
            placeholders = ','.join('?' for _ in range(len(insert_values) + 2))
            insert_columns = ','.join((identity_column, *columns, 'created_at_ms'))
            connection.execute(
                f'INSERT INTO {table}({insert_columns}) VALUES ({placeholders})',
                (identity, *insert_values, _now_ms()),
            )
            return True
        if tuple(selected) != expected:
            raise IdentityConflict
        return False

    def set_kill_switch(self, active: bool) -> None:
        """Atomically set the mediated-launch kill switch."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute(
                'UPDATE control SET kill_switch = ?, updated_at_ms = ? WHERE singleton = 1',
                (int(active), _now_ms()),
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def admit(
        self,
        request: dict[str, object],
        route: TaskRoute,
        slot_role: str,
        limits: InvocationLimits,
    ) -> dict[str, object]:
        """Evaluate and record admission in one immediate transaction."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            now = _now_ms()
            contract_id = str(request['contract_id'])
            slot_id = str(request['slot_id'])
            generation_id = str(request['generation_id'])
            logical_id = str(request['logical_id'])
            attempt_id = str(request['attempt_id'])
            parent_id = request['parent_attempt_id']
            retry_fingerprint = request['retry_fingerprint']
            mode = str(request['mode'])
            self._bind(
                connection, 'contracts', 'contract_id', contract_id,
                (
                    route.classification_digest, route.route_digest,
                    route.routing_version, route.operating_model_version,
                ),
                (
                    'classification_digest', 'route_digest',
                    'routing_version', 'operating_model_version',
                ),
                (
                    route.classification_digest, route.route_digest,
                    route.routing_version, route.operating_model_version,
                ),
            )
            self._bind(
                connection, 'slots', 'slot_id', slot_id,
                (contract_id, slot_role), ('contract_id', 'role_id'),
                (contract_id, slot_role),
            )
            generation = connection.execute(
                'SELECT contract_id, slot_id FROM generations WHERE generation_id = ?',
                (generation_id,),
            ).fetchone()
            logical = connection.execute(
                'SELECT contract_id, slot_id FROM logical_invocations WHERE logical_id = ?',
                (logical_id,),
            ).fetchone()
            generation_is_new = generation is None
            logical_is_new = logical is None
            if generation is not None and tuple(generation) != (contract_id, slot_id):
                raise IdentityConflict
            if logical is not None and tuple(logical) != (contract_id, slot_id):
                raise IdentityConflict
            if connection.execute(
                'SELECT 1 FROM decisions WHERE attempt_id = ?', (attempt_id,)
            ).fetchone() is not None:
                raise IdentityConflict

            ancestor_slots: list[str] = []
            proposed_depth = 1
            current_parent = parent_id
            seen_attempts: set[str] = set()
            while current_parent is not None:
                if str(current_parent) in seen_attempts:
                    raise StateCorrupt
                seen_attempts.add(str(current_parent))
                parent = connection.execute(
                    """SELECT contract_id, slot_id, parent_attempt_id, lifecycle_status
                    FROM attempts WHERE attempt_id = ?""",
                    (current_parent,),
                ).fetchone()
                if (
                    parent is None
                    or parent['contract_id'] != contract_id
                    or parent['lifecycle_status'] != 'active'
                ):
                    raise IdentityConflict
                ancestor_slots.append(parent['slot_id'])
                proposed_depth += 1
                current_parent = parent['parent_attempt_id']

            duplicate = connection.execute(
                """SELECT 1 FROM attempts
                WHERE contract_id = ? AND lifecycle_status = 'active'
                  AND (logical_id = ? OR (slot_id = ? AND generation_id = ?))
                LIMIT 1""",
                (contract_id, logical_id, slot_id, generation_id),
            ).fetchone() is not None
            active_count = connection.execute(
                "SELECT COUNT(*) FROM attempts "
                "WHERE contract_id = ? AND lifecycle_status = 'active'",
                (contract_id,),
            ).fetchone()[0]
            logical_count = connection.execute(
                'SELECT COUNT(*) FROM logical_invocations WHERE contract_id = ?',
                (contract_id,),
            ).fetchone()[0]
            attempt_count = connection.execute(
                'SELECT COUNT(*) FROM attempts WHERE logical_id = ?',
                (logical_id,),
            ).fetchone()[0]
            if attempt_count and retry_fingerprint is None and not duplicate:
                raise IdentityConflict
            if retry_fingerprint is not None:
                prior_failure = connection.execute(
                    """SELECT 1 FROM attempts
                    WHERE logical_id = ? AND lifecycle_status = 'failed'
                      AND terminal_fingerprint = ? LIMIT 1""",
                    (logical_id, retry_fingerprint),
                ).fetchone()
                if prior_failure is None:
                    raise IdentityConflict
                retries = connection.execute(
                    'SELECT COUNT(*) FROM attempts WHERE slot_id = ? AND retry_fingerprint = ?',
                    (slot_id, retry_fingerprint),
                ).fetchone()[0]
            else:
                retries = 0
            recent = tuple(
                row[0]
                for row in connection.execute(
                    """SELECT terminal_fingerprint FROM attempts
                    WHERE slot_id = ? AND terminal_fingerprint IS NOT NULL
                    ORDER BY finished_at_ms DESC, rowid DESC LIMIT ?""",
                    (slot_id, limits.no_progress_identical_terminals),
                )
            )
            kill_switch = bool(
                connection.execute(
                    'SELECT kill_switch FROM control WHERE singleton = 1'
                ).fetchone()[0]
            )
            decision = evaluate_admission(
                AdmissionFacts(
                    kill_switch_active=kill_switch,
                    duplicate_active=duplicate,
                    ancestor_slot_ids=tuple(ancestor_slots),
                    proposed_slot_id=slot_id,
                    proposed_depth=proposed_depth,
                    active_count=active_count,
                    logical_count=logical_count,
                    is_new_logical=logical_is_new,
                    retry_fingerprint=(
                        str(retry_fingerprint) if retry_fingerprint is not None else None
                    ),
                    retries_for_fingerprint=retries,
                    attempt_count=attempt_count,
                    recent_terminal_fingerprints=recent,
                ),
                limits,
            )
            decision_id = format_identity('decision', secrets.token_hex(16))
            if decision.launch_authorized:
                if generation_is_new:
                    connection.execute(
                        'INSERT INTO generations VALUES (?, ?, ?, ?)',
                        (generation_id, contract_id, slot_id, now),
                    )
                if logical_is_new:
                    connection.execute(
                        'INSERT INTO logical_invocations VALUES (?, ?, ?, ?)',
                        (logical_id, contract_id, slot_id, now),
                    )
            connection.execute(
                """INSERT INTO decisions(
                    decision_id, contract_id, slot_id, generation_id, logical_id,
                    attempt_id, parent_attempt_id, mode, policy_reason,
                    would_reject, launch_authorized, decided_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision_id, contract_id, slot_id, generation_id, logical_id,
                    attempt_id, parent_id, mode, decision.policy_reason,
                    int(decision.would_reject), int(decision.launch_authorized), now,
                ),
            )
            if decision.launch_authorized:
                connection.execute(
                    """INSERT INTO attempts(
                        attempt_id, decision_id, contract_id, slot_id,
                        generation_id, logical_id, parent_attempt_id,
                        retry_fingerprint, terminal_fingerprint, lifecycle_status,
                        depth, admitted_at_ms, finished_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'active', ?, ?, NULL)""",
                    (
                        attempt_id, decision_id, contract_id, slot_id,
                        generation_id, logical_id, parent_id, retry_fingerprint,
                        proposed_depth, now,
                    ),
                )
            connection.commit()
            return {
                'decision_id': decision_id,
                'policy_reason': decision.policy_reason,
                'would_reject': decision.would_reject,
                'launch_authorized': decision.launch_authorized,
            }
        except (IdentityConflict, StateCorrupt):
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def finish(
        self, attempt_id: str, status: str, terminal_fingerprint: str
    ) -> tuple[str, bool]:
        """Finish or recover one leaf attempt, idempotently."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            attempt = connection.execute(
                'SELECT lifecycle_status, terminal_fingerprint FROM attempts WHERE attempt_id = ?',
                (attempt_id,),
            ).fetchone()
            if attempt is None:
                raise IdentityConflict
            if attempt['lifecycle_status'] != 'active':
                if (
                    attempt['lifecycle_status'] == status
                    and attempt['terminal_fingerprint'] == terminal_fingerprint
                ):
                    connection.commit()
                    return status, True
                raise FinishConflict
            if connection.execute(
                "SELECT 1 FROM attempts WHERE parent_attempt_id = ? "
                "AND lifecycle_status = 'active' LIMIT 1",
                (attempt_id,),
            ).fetchone() is not None:
                raise RecoveryRequired
            connection.execute(
                """UPDATE attempts
                SET lifecycle_status = ?, terminal_fingerprint = ?, finished_at_ms = ?
                WHERE attempt_id = ?""",
                (status, terminal_fingerprint, _now_ms(), attempt_id),
            )
            connection.commit()
            return status, False
        except (IdentityConflict, RecoveryRequired, FinishConflict):
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def status(self) -> dict[str, object]:
        """Return privacy-safe aggregate ledger state."""
        connection = self._connect()
        try:
            counts = {
                'contracts': connection.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],
                'logical_invocations': connection.execute(
                    'SELECT COUNT(*) FROM logical_invocations'
                ).fetchone()[0],
                'active_attempts': connection.execute(
                    "SELECT COUNT(*) FROM attempts WHERE lifecycle_status = 'active'"
                ).fetchone()[0],
                'terminal_attempts': connection.execute(
                    "SELECT COUNT(*) FROM attempts WHERE lifecycle_status != 'active'"
                ).fetchone()[0],
                'decisions': connection.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],
            }
            reasons = dict(
                connection.execute(
                    'SELECT policy_reason, COUNT(*) FROM decisions GROUP BY policy_reason'
                )
            )
            kill_switch = bool(
                connection.execute(
                    'SELECT kill_switch FROM control WHERE singleton = 1'
                ).fetchone()[0]
            )
            active_attempts = [
                {
                    'attempt_id': row[0],
                    'parent_attempt_id': row[1],
                    'depth': row[2],
                }
                for row in connection.execute(
                    "SELECT attempt_id, parent_attempt_id, depth FROM attempts "
                    "WHERE lifecycle_status = 'active' "
                    "ORDER BY depth DESC, admitted_at_ms DESC, rowid DESC"
                )
            ]
            return {
                'counts': counts,
                'decision_counts': reasons,
                'kill_switch_active': kill_switch,
                'active_attempts': active_attempts,
            }
        except sqlite3.Error as exc:
            raise StateCorrupt from exc
        finally:
            connection.close()


def _state_error(command: str, mode: object, policy_reason: str) -> NoReturn:
    values: dict[str, object] = {'policy_reason': policy_reason}
    if command == 'admit' and mode in APPROVED_MODES:
        values.update({'would_reject': True, 'launch_authorized': True})
    _emit(_response(command, 'ledger_unavailable', **values), EXIT_LEDGER)


def main() -> int:
    """Execute one versioned request and emit one versioned response."""
    try:
        request = _read_request()
        command = str(request['command'])
        if command == 'new_identity':
            _require_exact_keys(request, {'schema_version', 'command', 'kind'})
            kind = request['kind']
            if kind not in {'contract', 'slot', 'generation', 'logical', 'attempt'}:
                raise RequestFailure('invalid identity kind')
            _emit(
                _response(
                    command, 'identity_created', kind=kind,
                    identity=format_identity(str(kind), secrets.token_hex(16)),
                ),
                EXIT_OK,
            )

        if command == 'init':
            _load_policy()
            _require_exact_keys(request, {'schema_version', 'command'})
            created = Ledger(_ledger_path()).initialize()
            _emit(
                _response(command, 'ledger_initialized' if created else 'ledger_ready'),
                EXIT_OK,
            )

        if command == 'admit':
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'mode', 'primary_object',
                    'impacts', 'risk_triggers', 'classification_digest',
                    'route_digest', 'contract_id', 'slot_id', 'slot_role',
                    'generation_id', 'logical_id', 'attempt_id',
                    'parent_attempt_id', 'retry_fingerprint',
                },
            )
            mode = request['mode']
            if mode == 'enforce' or mode not in APPROVED_MODES:
                _emit(
                    _response(
                        command, 'enforcement_unavailable', policy_reason=None,
                        would_reject=None, launch_authorized=None,
                    ),
                    EXIT_MODE,
                )
            _validate_identity_fields(request)
            route, slot_role = _validate_contract(request)
            limits = _load_policy()
            ledger = Ledger(_ledger_path())
            outcome = ledger.admit(request, route, slot_role, limits)
            _emit(
                _response(
                    command,
                    _machine_reason(str(mode), str(outcome['policy_reason'])),
                    **outcome,
                ),
                EXIT_OK,
            )

        if command in {'finish', 'recover'}:
            _load_policy()
            ledger = Ledger(_ledger_path())
            required = {'schema_version', 'command', 'attempt_id', 'terminal_fingerprint'}
            if command == 'finish':
                required.add('status')
            _require_exact_keys(request, required)
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_fingerprint(request['terminal_fingerprint']):
                raise RequestFailure('invalid terminal_fingerprint')
            if command == 'finish':
                status = request['status']
                if status not in {'succeeded', 'failed'}:
                    raise RequestFailure('invalid finish status')
            else:
                status = 'recovered'
            lifecycle, idempotent = ledger.finish(
                str(request['attempt_id']), str(status),
                str(request['terminal_fingerprint']),
            )
            reason = 'finish_idempotent' if idempotent else (
                'recovery_recorded' if command == 'recover' else 'finish_recorded'
            )
            _emit(
                _response(
                    command, reason, lifecycle_status=lifecycle,
                    idempotent=idempotent,
                ),
                EXIT_OK,
            )

        if command == 'kill_switch':
            _load_policy()
            ledger = Ledger(_ledger_path())
            _require_exact_keys(request, {'schema_version', 'command', 'active'})
            if not isinstance(request['active'], bool):
                raise RequestFailure('active must be boolean')
            ledger.set_kill_switch(request['active'])
            _emit(
                _response(command, 'kill_switch_updated', active=request['active']),
                EXIT_OK,
            )

        if command == 'status':
            _load_policy()
            ledger = Ledger(_ledger_path())
            _require_exact_keys(request, {'schema_version', 'command'})
            _emit(_response(command, 'status_reported', **ledger.status()), EXIT_OK)
        raise RequestFailure('unsupported command')
    except RequestFailure:
        _emit(_response('invalid', 'invalid_request'), EXIT_INVALID)
    except ContractFailure as exc:
        command = str(locals().get('command', 'invalid'))
        local_request = locals().get('request')
        mode = local_request.get('mode') if isinstance(local_request, dict) else None
        values: dict[str, object] = {'policy_reason': 'work_contract_invalid'}
        if command == 'admit' and mode in APPROVED_MODES:
            values.update({'would_reject': True, 'launch_authorized': True})
        _emit(_response(command, exc.reason_code, **values), EXIT_CONTRACT)
    except StateMissing:
        command = str(locals().get('command', 'invalid'))
        local_request = locals().get('request')
        mode = local_request.get('mode') if isinstance(local_request, dict) else None
        _state_error(command, mode, 'state_missing')
    except StateCorrupt:
        command = str(locals().get('command', 'invalid'))
        local_request = locals().get('request')
        mode = local_request.get('mode') if isinstance(local_request, dict) else None
        _state_error(command, mode, 'state_corrupt')
    except StateUnsupported:
        command = str(locals().get('command', 'invalid'))
        local_request = locals().get('request')
        mode = local_request.get('mode') if isinstance(local_request, dict) else None
        _state_error(command, mode, 'state_unsupported')
    except IdentityConflict:
        command = str(locals().get('command', 'invalid'))
        local_request = locals().get('request')
        mode = local_request.get('mode') if isinstance(local_request, dict) else None
        values: dict[str, object] = {}
        if command == 'admit' and mode in APPROVED_MODES:
            values.update({'would_reject': True, 'launch_authorized': True})
        _emit(_response(command, 'invalid_identity', **values), EXIT_INVALID)
    except RecoveryRequired:
        _emit(_response(str(locals().get('command', 'invalid')), 'recovery_required'), EXIT_LEDGER)
    except FinishConflict:
        _emit(_response(str(locals().get('command', 'invalid')), 'invalid_request'), EXIT_INVALID)


if __name__ == '__main__':
    raise SystemExit(main())
