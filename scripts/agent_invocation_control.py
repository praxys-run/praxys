"""Cooperative CLI and local ledger for agent invocation control."""

from __future__ import annotations

import hashlib
import hmac
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
    DISPATCH_PROFILES,
    MACHINE_REASON_CODES,
    POLICY_REASONS,
    POLICY_VERSION,
    SCHEMA_VERSION,
    AdmissionFacts,
    InvocationLimits,
    evaluate_admission,
    format_identity,
    is_valid_artifact_revision,
    is_valid_fingerprint,
    is_valid_identity,
    is_valid_public_agent_id,
)
from analysis.agentic_task_routing import TaskClassification, TaskRoute, route_task  # noqa: E402

POLICY_PATH = ROOT / 'config' / 'agent-invocation-control.json'
LEDGER_SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_INVALID = 2
EXIT_CONTRACT = 3
EXIT_LEDGER = 4
EXIT_MODE = 5
LIFECYCLE_TRANSITIONS = (
    'initial_launch', 'resume', 'replacement', 'review_after_new_digest'
)
TERMINATION_STATUSES = {
    'abort': 'aborted', 'shutdown': 'shutdown', 'failure': 'failed'
}
NATIVE_INVALIDATION_REASONS = (
    'shutdown', 'resume', 'context_replacement'
)
NATIVE_BINDING_SOURCE = 'task_result'
_NATIVE_FINGERPRINT_DOMAIN = b'praxys-native-public-agent-id-v1\x00'


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


class NativeBoundary(RuntimeError):
    """A cooperative native-notification/read boundary refused an action."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


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
        'kill_switch', 'status', 'bind_native', 'native_notification',
        'native_read', 'native_observation', 'invalidate_native',
        'progress', 'terminate_tree',
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
        'dispatch_profiles', 'native_binding', 'limits',
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
        or payload['dispatch_profiles'] != {
            'default': DISPATCH_PROFILES['sync'],
            **DISPATCH_PROFILES,
        }
        or payload['native_binding'] != {
            'binding_source': NATIVE_BINDING_SOURCE,
            'public_id_storage': 'domain-separated-sha256-fingerprint',
            'invalidation_reasons': list(NATIVE_INVALIDATION_REASONS),
        }
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


def _validate_lifecycle_fields(request: dict[str, object]) -> None:
    revision = request['artifact_revision']
    transition = request['lifecycle_transition']
    replacement = request['replacement_of_attempt_id']
    if not is_valid_artifact_revision(revision):
        raise RequestFailure('invalid artifact_revision')
    if transition not in LIFECYCLE_TRANSITIONS:
        raise RequestFailure('invalid lifecycle_transition')
    if replacement is not None and not is_valid_identity(replacement, 'attempt'):
        raise RequestFailure('invalid replacement_of_attempt_id')
    if transition == 'replacement' and replacement is None:
        raise RequestFailure('replacement requires replacement_of_attempt_id')
    if transition != 'replacement' and replacement is not None:
        raise RequestFailure('replacement_of_attempt_id is only valid for replacement')


def _dispatch_profile(request: dict[str, object]) -> tuple[str, str]:
    """Return the closed lifecycle dispatch pair, defaulting legacy calls to sync."""
    has_mode = 'dispatch_mode' in request
    has_provenance = 'execution_provenance' in request
    if not has_mode and not has_provenance:
        return 'sync', DISPATCH_PROFILES['sync']
    if not has_mode or not has_provenance:
        raise NativeBoundary('execution_provenance_invalid')
    mode = request['dispatch_mode']
    provenance = request['execution_provenance']
    if (
        not isinstance(mode, str)
        or not isinstance(provenance, str)
        or DISPATCH_PROFILES.get(mode) != provenance
    ):
        raise NativeBoundary('execution_provenance_invalid')
    return mode, provenance


def _native_public_fingerprint(public_agent_id: str) -> str:
    digest = hashlib.sha256(
        _NATIVE_FINGERPRINT_DOMAIN + public_agent_id.encode('utf-8')
    ).hexdigest()
    return f'sha256:{digest}'


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
_BASE_SCHEMA_COLUMNS = {
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
_BASE_SCHEMA_INDEXES = {
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

_LIFECYCLE_SCHEMA_COLUMNS = {
    'lifecycle_decisions': (
        'decision_id', 'attempt_id', 'contract_id', 'slot_id',
        'artifact_revision', 'requested_transition', 'effective_transition',
        'replacement_of_attempt_id', 'launch_authorized', 'decided_at_ms',
    ),
    'work_history': (
        'attempt_id', 'contract_id', 'slot_id', 'artifact_revision',
        'lifecycle_transition', 'replacement_of_attempt_id',
        'lifecycle_status', 'terminal_fingerprint', 'last_progress_at_ms',
    ),
    'active_work_keys': (
        'contract_id', 'slot_id', 'artifact_revision', 'attempt_id',
    ),
    'replacement_eligibility': (
        'source_attempt_id', 'replacement_attempt_id', 'eligible_at_ms',
        'consumed_at_ms',
    ),
    'native_invocations': (
        'native_invocation_id', 'attempt_id', 'notifications_available',
        'lifecycle_status', 'bound_at_ms', 'notified_at_ms',
        'read_claimed_at_ms', 'observed_at_ms',
    ),
    'progress_evidence': ('attempt_id', 'progress_fingerprint', 'recorded_at_ms'),
}
_AUXILIARY_SCHEMA_COLUMNS = {
    'lifecycle_dispatch': (
        'decision_id', 'attempt_id', 'dispatch_mode',
        'execution_provenance', 'admission_reason', 'recorded_at_ms',
    ),
    'native_binding_provenance': (
        'native_alias', 'attempt_id', 'public_agent_id_fingerprint',
        'binding_source', 'invalidation_reason', 'invalidated_at_ms',
    ),
}
_SCHEMA_COLUMNS = {
    **_BASE_SCHEMA_COLUMNS,
    **_LIFECYCLE_SCHEMA_COLUMNS,
    **_AUXILIARY_SCHEMA_COLUMNS,
}
_LIFECYCLE_SCHEMA_INDEXES = {
    'work_history_slot_revision',
    'work_history_replacement',
    'native_invocations_attempt',
}
_SCHEMA_INDEXES = _BASE_SCHEMA_INDEXES | _LIFECYCLE_SCHEMA_INDEXES
_LIFECYCLE_SCHEMA = """
CREATE TABLE lifecycle_decisions (
    decision_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    artifact_revision TEXT NOT NULL,
    requested_transition TEXT NOT NULL,
    effective_transition TEXT NOT NULL CHECK (effective_transition IN (
        'initial_launch', 'resume', 'replacement',
        'review_after_new_digest', 'duplicate_launch', 'illegal_transition'
    )),
    replacement_of_attempt_id TEXT,
    launch_authorized INTEGER NOT NULL CHECK (launch_authorized IN (0, 1)),
    decided_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE work_history (
    attempt_id TEXT PRIMARY KEY REFERENCES attempts(attempt_id),
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    artifact_revision TEXT NOT NULL,
    lifecycle_transition TEXT NOT NULL CHECK (lifecycle_transition IN (
        'initial_launch', 'resume', 'replacement', 'review_after_new_digest'
    )),
    replacement_of_attempt_id TEXT,
    lifecycle_status TEXT NOT NULL CHECK (lifecycle_status IN (
        'active', 'succeeded', 'failed', 'recovered', 'lost', 'orphaned',
        'aborted', 'shutdown'
    )),
    terminal_fingerprint TEXT,
    last_progress_at_ms INTEGER
) STRICT;
CREATE TABLE active_work_keys (
    contract_id TEXT NOT NULL REFERENCES contracts(contract_id),
    slot_id TEXT NOT NULL REFERENCES slots(slot_id),
    artifact_revision TEXT NOT NULL,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES work_history(attempt_id),
    PRIMARY KEY (contract_id, slot_id, artifact_revision)
) STRICT;
CREATE TABLE replacement_eligibility (
    source_attempt_id TEXT PRIMARY KEY REFERENCES work_history(attempt_id),
    replacement_attempt_id TEXT UNIQUE REFERENCES work_history(attempt_id),
    eligible_at_ms INTEGER NOT NULL,
    consumed_at_ms INTEGER
) STRICT;
CREATE TABLE native_invocations (
    native_invocation_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES work_history(attempt_id),
    notifications_available INTEGER NOT NULL CHECK (notifications_available IN (0, 1)),
    lifecycle_status TEXT NOT NULL CHECK (lifecycle_status IN (
        'active', 'notifications_unavailable', 'completion_notified',
        'read_claimed', 'found', 'lost', 'orphaned', 'aborted',
        'shutdown', 'failed', 'recovered', 'succeeded'
    )),
    bound_at_ms INTEGER NOT NULL,
    notified_at_ms INTEGER,
    read_claimed_at_ms INTEGER,
    observed_at_ms INTEGER
) STRICT;
CREATE TABLE progress_evidence (
    attempt_id TEXT NOT NULL REFERENCES work_history(attempt_id),
    progress_fingerprint TEXT NOT NULL,
    recorded_at_ms INTEGER NOT NULL,
    PRIMARY KEY (attempt_id, progress_fingerprint)
) STRICT;
CREATE INDEX work_history_slot_revision
    ON work_history(contract_id, slot_id, artifact_revision);
CREATE INDEX work_history_replacement
    ON work_history(replacement_of_attempt_id);
CREATE INDEX native_invocations_attempt ON native_invocations(attempt_id);
"""
_AUXILIARY_SCHEMA = """
CREATE TABLE lifecycle_dispatch (
    decision_id TEXT PRIMARY KEY REFERENCES lifecycle_decisions(decision_id),
    attempt_id TEXT NOT NULL UNIQUE,
    dispatch_mode TEXT NOT NULL CHECK (dispatch_mode IN ('sync', 'background')),
    execution_provenance TEXT NOT NULL CHECK (execution_provenance IN (
        'sync_inline', 'background_independent_immediate_no_poll'
    )),
    admission_reason TEXT NOT NULL CHECK (admission_reason IN (
        'admit', 'policy_denied', 'direct_sibling_active',
        'lifecycle_transition_rejected'
    )),
    recorded_at_ms INTEGER NOT NULL
) STRICT;
CREATE TABLE native_binding_provenance (
    native_alias TEXT PRIMARY KEY REFERENCES native_invocations(native_invocation_id),
    attempt_id TEXT NOT NULL UNIQUE REFERENCES work_history(attempt_id),
    public_agent_id_fingerprint TEXT NOT NULL UNIQUE,
    binding_source TEXT NOT NULL CHECK (binding_source = 'task_result'),
    invalidation_reason TEXT CHECK (invalidation_reason IN (
        'shutdown', 'resume', 'context_replacement'
    )),
    invalidated_at_ms INTEGER,
    CHECK (
        (invalidation_reason IS NULL AND invalidated_at_ms IS NULL)
        OR (invalidation_reason IS NOT NULL AND invalidated_at_ms IS NOT NULL)
    )
) STRICT;
"""


class Ledger:
    """Concurrency-safe local SQLite lifecycle ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> bool:
        """Create the v1 ledger once, or validate an existing ledger."""
        if self.path.exists():
            connection = self._connect_for_initialization()
            try:
                tables = self._table_names(connection)
                lifecycle_tables = set(_LIFECYCLE_SCHEMA_COLUMNS)
                lifecycle_present = tables & lifecycle_tables
                auxiliary_tables = set(_AUXILIARY_SCHEMA_COLUMNS)
                auxiliary_present = tables & auxiliary_tables
                if (
                    lifecycle_present and lifecycle_present != lifecycle_tables
                ) or (
                    auxiliary_present and auxiliary_present != auxiliary_tables
                ) or (auxiliary_present and not lifecycle_present):
                    raise StateCorrupt
                if not lifecycle_present or not auxiliary_present:
                    connection.execute('BEGIN IMMEDIATE')
                    if not lifecycle_present:
                        self._execute_schema(connection, _LIFECYCLE_SCHEMA)
                    if not auxiliary_present:
                        self._execute_schema(connection, _AUXILIARY_SCHEMA)
                        connection.execute(
                            """INSERT INTO lifecycle_dispatch
                            SELECT decision_id, attempt_id, 'sync', 'sync_inline',
                                   CASE
                                     WHEN effective_transition IN (
                                         'duplicate_launch', 'illegal_transition'
                                     )
                                     THEN 'lifecycle_transition_rejected'
                                     WHEN launch_authorized = 0
                                     THEN 'policy_denied'
                                     ELSE 'admit'
                                   END,
                                   decided_at_ms
                            FROM lifecycle_decisions"""
                        )
                    self._validate(connection)
                    connection.commit()
                else:
                    self._validate(connection)
            except (StateCorrupt, StateUnsupported):
                if connection.in_transaction:
                    connection.rollback()
                raise
            except sqlite3.Error as exc:
                if connection.in_transaction:
                    connection.rollback()
                raise StateCorrupt from exc
            finally:
                connection.close()
            return False
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        connection: sqlite3.Connection | None = None
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
            self._execute_schema(connection, _SCHEMA)
            self._execute_schema(connection, _LIFECYCLE_SCHEMA)
            self._execute_schema(connection, _AUXILIARY_SCHEMA)
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
            self._validate(connection)
            connection.commit()
            self.path.chmod(0o600)
            return True
        except (StateCorrupt, StateUnsupported):
            if connection is not None and connection.in_transaction:
                connection.rollback()
            raise
        except (sqlite3.Error, OSError) as exc:
            if connection is not None and connection.in_transaction:
                connection.rollback()
            raise StateCorrupt from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _execute_schema(connection: sqlite3.Connection, schema: str) -> None:
        for statement in schema.split(';'):
            if statement.strip():
                connection.execute(statement)

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set[str]:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

    def _connect_for_initialization(self) -> sqlite3.Connection:
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
            self._validate(connection, require_lifecycle=False)
            return connection
        except (sqlite3.Error, OSError, UnicodeError) as exc:
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
    def _validate(
        connection: sqlite3.Connection, *, require_lifecycle: bool = True
    ) -> None:
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

            tables = Ledger._table_names(connection)
            indexes = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'index' AND sql IS NOT NULL"
                )
            }
            expected_columns = (
                _SCHEMA_COLUMNS if require_lifecycle else _BASE_SCHEMA_COLUMNS
            )
            columns = {
                table: tuple(
                    row[1]
                    for row in connection.execute(f'PRAGMA table_info({table})')
                )
                for table in expected_columns
            }
            foreign_keys = connection.execute('PRAGMA foreign_keys').fetchone()
            control = connection.execute(
                'SELECT kill_switch FROM control WHERE singleton = 1'
            ).fetchone()
            if (
                (
                    tables != set(_SCHEMA_COLUMNS)
                    if require_lifecycle
                    else not set(_BASE_SCHEMA_COLUMNS).issubset(tables)
                )
                or (
                    indexes != _SCHEMA_INDEXES
                    if require_lifecycle
                    else not _BASE_SCHEMA_INDEXES.issubset(indexes)
                )
                or columns != expected_columns
                or foreign_keys is None or foreign_keys[0] != 1
                or control is None or control[0] not in (0, 1)
                or (
                    require_lifecycle
                    and connection.execute(
                        "SELECT 1 FROM attempts child JOIN attempts parent "
                        "ON child.parent_attempt_id = parent.attempt_id "
                        "WHERE child.lifecycle_status = 'active' "
                        "AND parent.lifecycle_status != 'active' LIMIT 1"
                    ).fetchone() is not None
                )
                or (
                    require_lifecycle
                    and connection.execute(
                        "SELECT 1 FROM native_invocations native "
                        "JOIN attempts USING (attempt_id) "
                        "WHERE native.lifecycle_status IN "
                        "('active', 'notifications_unavailable', "
                        "'completion_notified', 'read_claimed') "
                        "AND attempts.lifecycle_status != 'active' LIMIT 1"
                    ).fetchone() is not None
                )
                or (
                    require_lifecycle
                    and connection.execute(
                        """SELECT 1 FROM lifecycle_decisions
                        LEFT JOIN lifecycle_dispatch USING (decision_id)
                        WHERE lifecycle_dispatch.decision_id IS NULL LIMIT 1"""
                    ).fetchone() is not None
                )
                or (
                    require_lifecycle
                    and connection.execute(
                        """SELECT 1 FROM native_binding_provenance
                        JOIN lifecycle_dispatch USING (attempt_id)
                        WHERE lifecycle_dispatch.dispatch_mode != 'background'
                           OR length(public_agent_id_fingerprint) != 71
                           OR substr(public_agent_id_fingerprint, 1, 7) != 'sha256:'
                           OR substr(public_agent_id_fingerprint, 8)
                              GLOB '*[^0-9a-f]*'
                        LIMIT 1"""
                    ).fetchone() is not None
                )
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
        dispatch_mode, execution_provenance = _dispatch_profile(request)
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

            decision_id = format_identity('decision', secrets.token_hex(16))
            lifecycle_transition: str | None = None
            if 'artifact_revision' in request:
                revision = str(request['artifact_revision'])
                requested_transition = str(request['lifecycle_transition'])
                replacement_of = request['replacement_of_attempt_id']
                active_work = connection.execute(
                    """SELECT attempt_id FROM active_work_keys
                    WHERE contract_id = ? AND slot_id = ? AND artifact_revision = ?""",
                    (contract_id, slot_id, revision),
                ).fetchone()
                same_revision = connection.execute(
                    """SELECT work_history.attempt_id,
                              work_history.lifecycle_transition,
                              work_history.lifecycle_status
                    FROM work_history JOIN attempts USING (attempt_id)
                    WHERE work_history.contract_id = ?
                      AND work_history.slot_id = ?
                      AND work_history.artifact_revision = ?
                    ORDER BY attempts.admitted_at_ms DESC, attempts.rowid DESC""",
                    (contract_id, slot_id, revision),
                ).fetchall()
                has_slot_history = connection.execute(
                    'SELECT 1 FROM work_history WHERE contract_id = ? AND slot_id = ? LIMIT 1',
                    (contract_id, slot_id),
                ).fetchone() is not None
                lifecycle_transition = requested_transition
                if active_work is not None:
                    lifecycle_transition = 'duplicate_launch'
                elif requested_transition == 'initial_launch':
                    if has_slot_history:
                        lifecycle_transition = 'illegal_transition'
                elif requested_transition == 'resume':
                    if (
                        not same_revision
                        or same_revision[0]['lifecycle_status'] == 'lost'
                    ):
                        lifecycle_transition = 'illegal_transition'
                elif requested_transition == 'review_after_new_digest':
                    if not has_slot_history or same_revision:
                        lifecycle_transition = 'illegal_transition'
                elif requested_transition == 'replacement':
                    source = connection.execute(
                        """SELECT work_history.contract_id, work_history.slot_id,
                                  work_history.artifact_revision,
                                  work_history.lifecycle_transition,
                                  work_history.lifecycle_status,
                                  replacement_eligibility.source_attempt_id AS eligible_source,
                                  replacement_eligibility.replacement_attempt_id
                        FROM work_history
                        LEFT JOIN replacement_eligibility
                          ON replacement_eligibility.source_attempt_id = work_history.attempt_id
                        WHERE work_history.attempt_id = ?""",
                        (replacement_of,),
                    ).fetchone()
                    if (
                        source is None
                        or tuple(source[:3]) != (contract_id, slot_id, revision)
                        or source['lifecycle_transition'] == 'replacement'
                        or source['lifecycle_status'] != 'lost'
                        or source['eligible_source'] is None
                        or source['replacement_attempt_id'] is not None
                    ):
                        lifecycle_transition = 'illegal_transition'

                if lifecycle_transition in {'duplicate_launch', 'illegal_transition'}:
                    connection.execute(
                        """INSERT INTO lifecycle_decisions VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                        (
                            decision_id, attempt_id, contract_id, slot_id, revision,
                            requested_transition, lifecycle_transition, replacement_of, now,
                        ),
                    )
                    connection.execute(
                        """INSERT INTO lifecycle_dispatch VALUES
                        (?, ?, ?, ?, 'lifecycle_transition_rejected', ?)""",
                        (
                            decision_id, attempt_id, dispatch_mode,
                            execution_provenance, now,
                        ),
                    )
                    connection.commit()
                    return {
                        'decision_id': decision_id,
                        'policy_reason': None,
                        'would_reject': True,
                        'launch_authorized': False,
                        'lifecycle_transition': lifecycle_transition,
                        'dispatch_mode': dispatch_mode,
                        'execution_provenance': execution_provenance,
                    }

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
                parent_is_lifecycle = connection.execute(
                    'SELECT 1 FROM work_history WHERE attempt_id = ?',
                    (current_parent,),
                ).fetchone() is not None
                if parent_is_lifecycle != ('artifact_revision' in request):
                    raise IdentityConflict
                ancestor_slots.append(parent['slot_id'])
                proposed_depth += 1
                current_parent = parent['parent_attempt_id']

            if 'artifact_revision' in request and parent_id is not None:
                active_sibling = connection.execute(
                    """SELECT 1 FROM attempts
                    WHERE parent_attempt_id = ? AND lifecycle_status = 'active'
                    LIMIT 1""",
                    (parent_id,),
                ).fetchone()
                if active_sibling is not None:
                    connection.execute(
                        """INSERT INTO lifecycle_decisions VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                        (
                            decision_id, attempt_id, contract_id, slot_id,
                            request['artifact_revision'],
                            request['lifecycle_transition'],
                            lifecycle_transition,
                            request['replacement_of_attempt_id'],
                            now,
                        ),
                    )
                    connection.execute(
                        """INSERT INTO lifecycle_dispatch VALUES
                        (?, ?, ?, ?, 'direct_sibling_active', ?)""",
                        (
                            decision_id, attempt_id, dispatch_mode,
                            execution_provenance, now,
                        ),
                    )
                    connection.commit()
                    return {
                        'decision_id': decision_id,
                        'policy_reason': None,
                        'would_reject': True,
                        'launch_authorized': False,
                        'lifecycle_transition': lifecycle_transition,
                        'protocol_reason': 'direct_sibling_active',
                        'dispatch_mode': dispatch_mode,
                        'execution_provenance': execution_provenance,
                    }

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
            if 'artifact_revision' in request:
                connection.execute(
                    """INSERT INTO lifecycle_decisions VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        decision_id, attempt_id, contract_id, slot_id,
                        request['artifact_revision'], request['lifecycle_transition'],
                        lifecycle_transition, request['replacement_of_attempt_id'],
                        int(decision.launch_authorized), now,
                    ),
                )
                connection.execute(
                    """INSERT INTO lifecycle_dispatch VALUES
                    (?, ?, ?, ?, ?, ?)""",
                    (
                        decision_id, attempt_id, dispatch_mode,
                        execution_provenance,
                        (
                            'admit'
                            if decision.launch_authorized
                            else 'policy_denied'
                        ),
                        now,
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
                if 'artifact_revision' in request:
                    connection.execute(
                        """INSERT INTO work_history VALUES
                        (?, ?, ?, ?, ?, ?, 'active', NULL, NULL)""",
                        (
                            attempt_id, contract_id, slot_id,
                            request['artifact_revision'], lifecycle_transition,
                            request['replacement_of_attempt_id'],
                        ),
                    )
                    connection.execute(
                        'INSERT INTO active_work_keys VALUES (?, ?, ?, ?)',
                        (contract_id, slot_id, request['artifact_revision'], attempt_id),
                    )
                    if lifecycle_transition == 'replacement':
                        updated = connection.execute(
                            """UPDATE replacement_eligibility
                            SET replacement_attempt_id = ?, consumed_at_ms = ?
                            WHERE source_attempt_id = ?
                              AND replacement_attempt_id IS NULL""",
                            (attempt_id, now, request['replacement_of_attempt_id']),
                        )
                        if updated.rowcount != 1:
                            raise StateCorrupt
            connection.commit()
            outcome = {
                'decision_id': decision_id,
                'policy_reason': decision.policy_reason,
                'would_reject': decision.would_reject,
                'launch_authorized': decision.launch_authorized,
            }
            if lifecycle_transition is not None:
                outcome['lifecycle_transition'] = lifecycle_transition
                outcome['dispatch_mode'] = dispatch_mode
                outcome['execution_provenance'] = execution_provenance
            return outcome
        except (IdentityConflict, StateCorrupt):
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    @staticmethod
    def _terminalize(
        connection: sqlite3.Connection,
        attempt_id: str,
        status: str,
        terminal_fingerprint: str,
        now: int,
    ) -> None:
        base_status = {
            'lost': 'recovered',
            'orphaned': 'recovered',
            'shutdown': 'recovered',
            'aborted': 'failed',
        }.get(status, status)
        updated = connection.execute(
            """UPDATE attempts
            SET lifecycle_status = ?, terminal_fingerprint = ?, finished_at_ms = ?
            WHERE attempt_id = ? AND lifecycle_status = 'active'""",
            (base_status, terminal_fingerprint, now, attempt_id),
        )
        if updated.rowcount != 1:
            raise FinishConflict
        work_updated = connection.execute(
            """UPDATE work_history
            SET lifecycle_status = ?, terminal_fingerprint = ?
            WHERE attempt_id = ?""",
            (status, terminal_fingerprint, attempt_id),
        )
        if work_updated.rowcount != 1:
            raise StateCorrupt
        connection.execute(
            'DELETE FROM active_work_keys WHERE attempt_id = ?', (attempt_id,)
        )
        connection.execute(
            """UPDATE native_invocations
            SET lifecycle_status = ?, observed_at_ms = ?
            WHERE attempt_id = ?""",
            (status, now, attempt_id),
        )
        if status == 'lost':
            transition = connection.execute(
                'SELECT lifecycle_transition FROM work_history WHERE attempt_id = ?',
                (attempt_id,),
            ).fetchone()
            if transition is not None and transition[0] != 'replacement':
                connection.execute(
                    """INSERT OR IGNORE INTO replacement_eligibility
                    VALUES (?, NULL, ?, NULL)""",
                    (attempt_id, now),
                )

    @classmethod
    def _terminate_tree_in_transaction(
        cls,
        connection: sqlite3.Connection,
        attempt_id: str,
        status: str,
        terminal_fingerprint: str,
    ) -> tuple[list[str], bool]:
        target = connection.execute(
            """SELECT attempts.lifecycle_status, work_history.lifecycle_status,
                      work_history.terminal_fingerprint
            FROM attempts JOIN work_history USING (attempt_id)
            WHERE attempts.attempt_id = ?""",
            (attempt_id,),
        ).fetchone()
        if target is None:
            raise IdentityConflict
        if target[0] != 'active':
            if target[1] == status and target[2] == terminal_fingerprint:
                return [], True
            raise FinishConflict
        descendants = [
            row[0]
            for row in connection.execute(
                """WITH RECURSIVE descendants(attempt_id, depth) AS (
                    SELECT attempt_id, depth FROM attempts
                    WHERE parent_attempt_id = ? AND lifecycle_status = 'active'
                    UNION ALL
                    SELECT child.attempt_id, child.depth
                    FROM attempts child JOIN descendants parent
                      ON child.parent_attempt_id = parent.attempt_id
                    WHERE child.lifecycle_status = 'active'
                )
                SELECT attempt_id FROM descendants ORDER BY depth DESC""",
                (attempt_id,),
            )
        ]
        now = _now_ms()
        for descendant_id in descendants:
            cls._terminalize(
                connection, descendant_id, 'orphaned', terminal_fingerprint, now
            )
        cls._terminalize(
            connection, attempt_id, status, terminal_fingerprint, now
        )
        return descendants, False

    def terminate_tree(
        self, attempt_id: str, reason: str, terminal_fingerprint: str
    ) -> tuple[str, list[str], bool]:
        """Terminalize active descendants leaf first, then their parent."""
        status = TERMINATION_STATUSES[reason]
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            descendants, idempotent = self._terminate_tree_in_transaction(
                connection, attempt_id, status, terminal_fingerprint
            )
            connection.commit()
            return status, descendants, idempotent
        except (IdentityConflict, FinishConflict):
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def bind_native(
        self,
        attempt_id: str,
        native_alias: str,
        public_agent_id: str,
        binding_source: str,
        notifications_available: bool = True,
    ) -> str:
        """Bind a task-returned public ID fingerprint to one background attempt."""
        if (
            not is_valid_public_agent_id(public_agent_id)
            or binding_source != NATIVE_BINDING_SOURCE
            or not isinstance(notifications_available, bool)
        ):
            raise NativeBoundary('native_binding_mismatch')
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            active = connection.execute(
                """SELECT lifecycle_dispatch.dispatch_mode,
                          lifecycle_dispatch.execution_provenance
                FROM attempts
                JOIN work_history USING (attempt_id)
                JOIN lifecycle_dispatch USING (attempt_id)
                WHERE attempt_id = ? AND attempts.lifecycle_status = 'active'""",
                (attempt_id,),
            ).fetchone()
            if active is None:
                raise IdentityConflict
            if tuple(active) != (
                'background',
                DISPATCH_PROFILES['background'],
            ):
                raise NativeBoundary('execution_provenance_invalid')
            connection.execute(
                "INSERT INTO native_invocations VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)",
                (
                    native_alias,
                    attempt_id,
                    int(notifications_available),
                    (
                        'active'
                        if notifications_available
                        else 'notifications_unavailable'
                    ),
                    _now_ms(),
                ),
            )
            connection.execute(
                """INSERT INTO native_binding_provenance
                VALUES (?, ?, ?, ?, NULL, NULL)""",
                (
                    native_alias,
                    attempt_id,
                    _native_public_fingerprint(public_agent_id),
                    binding_source,
                ),
            )
            connection.commit()
            return (
                'active'
                if notifications_available
                else 'notifications_unavailable'
            )
        except (IdentityConflict, NativeBoundary):
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise NativeBoundary('native_binding_mismatch') from exc
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    @staticmethod
    def _verified_native_binding(
        connection: sqlite3.Connection,
        attempt_id: str,
        native_alias: str,
        public_agent_id: str,
    ) -> sqlite3.Row:
        native = connection.execute(
            """SELECT native_invocations.notifications_available,
                      native_invocations.lifecycle_status,
                      native_binding_provenance.attempt_id,
                      native_binding_provenance.public_agent_id_fingerprint,
                      native_binding_provenance.invalidation_reason
            FROM native_invocations
            JOIN native_binding_provenance
              ON native_binding_provenance.native_alias =
                 native_invocations.native_invocation_id
            WHERE native_invocations.native_invocation_id = ?""",
            (native_alias,),
        ).fetchone()
        if native is None:
            raise NativeBoundary('native_binding_mismatch')
        expected = _native_public_fingerprint(public_agent_id)
        if (
            native['attempt_id'] != attempt_id
            or not hmac.compare_digest(
                native['public_agent_id_fingerprint'], expected
            )
        ):
            raise NativeBoundary('native_binding_mismatch')
        if native['invalidation_reason'] is not None:
            raise NativeBoundary('native_binding_invalidated')
        return native

    def native_notification(
        self, attempt_id: str, native_alias: str, public_agent_id: str
    ) -> bool:
        """Record a platform completion notification without inferring progress."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            native = self._verified_native_binding(
                connection, attempt_id, native_alias, public_agent_id
            )
            if not native['notifications_available']:
                raise NativeBoundary('native_notifications_unavailable')
            if native['lifecycle_status'] == 'completion_notified':
                connection.commit()
                return True
            if native['lifecycle_status'] != 'active':
                raise NativeBoundary('native_read_refused')
            connection.execute(
                """UPDATE native_invocations
                SET lifecycle_status = 'completion_notified', notified_at_ms = ?
                WHERE native_invocation_id = ?""",
                (_now_ms(), native_alias),
            )
            connection.commit()
            return False
        except NativeBoundary:
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def claim_native_read(
        self, attempt_id: str, native_alias: str, public_agent_id: str
    ) -> None:
        """Authorize exactly one read, and only after completion notification."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            native = self._verified_native_binding(
                connection, attempt_id, native_alias, public_agent_id
            )
            if not native['notifications_available']:
                raise NativeBoundary('native_notifications_unavailable')
            if native['lifecycle_status'] == 'active':
                raise NativeBoundary('completion_notification_required')
            if native['lifecycle_status'] != 'completion_notified':
                raise NativeBoundary('native_read_refused')
            connection.execute(
                """UPDATE native_invocations
                SET lifecycle_status = 'read_claimed', read_claimed_at_ms = ?
                WHERE native_invocation_id = ?""",
                (_now_ms(), native_alias),
            )
            connection.commit()
        except NativeBoundary:
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def observe_native(
        self,
        attempt_id: str,
        native_alias: str,
        public_agent_id: str,
        observation: str,
        terminal_fingerprint: str | None,
    ) -> tuple[str, list[str]]:
        """Record the one claimed read result; not-found is terminal loss."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            native = self._verified_native_binding(
                connection, attempt_id, native_alias, public_agent_id
            )
            if not native['notifications_available']:
                raise NativeBoundary('native_notifications_unavailable')
            if native['lifecycle_status'] != 'read_claimed':
                raise NativeBoundary('native_read_refused')
            descendants: list[str] = []
            now = _now_ms()
            if observation == 'not_found':
                if terminal_fingerprint is None:
                    raise FinishConflict
                descendants, _ = self._terminate_tree_in_transaction(
                    connection,
                    attempt_id,
                    'lost',
                    terminal_fingerprint,
                )
                state = 'lost'
            else:
                state = 'found'
            connection.execute(
                """UPDATE native_invocations
                SET lifecycle_status = ?, observed_at_ms = ?
                WHERE native_invocation_id = ?""",
                (state, now, native_alias),
            )
            connection.commit()
            return state, descendants
        except (NativeBoundary, FinishConflict):
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def invalidate_native(
        self,
        attempt_id: str,
        native_alias: str,
        public_agent_id: str,
        invalidation_reason: str,
    ) -> bool:
        """Permanently invalidate one exact native binding without registry access."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            native = connection.execute(
                """SELECT attempt_id, public_agent_id_fingerprint,
                          invalidation_reason
                FROM native_binding_provenance WHERE native_alias = ?""",
                (native_alias,),
            ).fetchone()
            expected = _native_public_fingerprint(public_agent_id)
            if (
                native is None
                or native['attempt_id'] != attempt_id
                or not hmac.compare_digest(
                    native['public_agent_id_fingerprint'], expected
                )
            ):
                raise NativeBoundary('native_binding_mismatch')
            if native['invalidation_reason'] is not None:
                if native['invalidation_reason'] != invalidation_reason:
                    raise NativeBoundary('native_binding_invalidated')
                connection.commit()
                return True
            connection.execute(
                """UPDATE native_binding_provenance
                SET invalidation_reason = ?, invalidated_at_ms = ?
                WHERE native_alias = ?""",
                (invalidation_reason, _now_ms(), native_alias),
            )
            connection.commit()
            return False
        except NativeBoundary:
            connection.rollback()
            raise
        except sqlite3.Error as exc:
            connection.rollback()
            raise StateCorrupt from exc
        finally:
            connection.close()

    def record_progress(
        self, attempt_id: str, progress_fingerprint: str
    ) -> tuple[int, bool]:
        """Advance last progress only for a new explicit evidence fingerprint."""
        connection = self._connect()
        try:
            connection.execute('BEGIN IMMEDIATE')
            active = connection.execute(
                """SELECT 1 FROM attempts JOIN work_history USING (attempt_id)
                WHERE attempt_id = ? AND attempts.lifecycle_status = 'active'""",
                (attempt_id,),
            ).fetchone()
            if active is None:
                raise IdentityConflict
            prior = connection.execute(
                """SELECT recorded_at_ms FROM progress_evidence
                WHERE attempt_id = ? AND progress_fingerprint = ?""",
                (attempt_id, progress_fingerprint),
            ).fetchone()
            if prior is not None:
                connection.commit()
                return prior[0], True
            now = _now_ms()
            connection.execute(
                'INSERT INTO progress_evidence VALUES (?, ?, ?)',
                (attempt_id, progress_fingerprint, now),
            )
            connection.execute(
                'UPDATE work_history SET last_progress_at_ms = ? WHERE attempt_id = ?',
                (now, attempt_id),
            )
            connection.commit()
            return now, False
        except IdentityConflict:
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
            connection.execute(
                """UPDATE work_history
                SET lifecycle_status = ?, terminal_fingerprint = ?
                WHERE attempt_id = ?""",
                (status, terminal_fingerprint, attempt_id),
            )
            connection.execute(
                'DELETE FROM active_work_keys WHERE attempt_id = ?', (attempt_id,)
            )
            connection.execute(
                """UPDATE native_invocations
                SET lifecycle_status = ?, observed_at_ms = ?
                WHERE attempt_id = ?""",
                (status, _now_ms(), attempt_id),
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
            if kind not in {
                'contract', 'slot', 'generation', 'logical', 'attempt', 'native'
            }:
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
            legacy_keys = {
                'schema_version', 'command', 'mode', 'primary_object',
                'impacts', 'risk_triggers', 'classification_digest',
                'route_digest', 'contract_id', 'slot_id', 'slot_role',
                'generation_id', 'logical_id', 'attempt_id',
                'parent_attempt_id', 'retry_fingerprint',
            }
            lifecycle_keys = legacy_keys | {
                'artifact_revision', 'lifecycle_transition',
                'replacement_of_attempt_id',
            }
            dispatch_keys = {'dispatch_mode', 'execution_provenance'}
            if frozenset(request) not in {
                frozenset(legacy_keys),
                frozenset(lifecycle_keys),
                frozenset(lifecycle_keys | dispatch_keys),
                frozenset(lifecycle_keys | {'dispatch_mode'}),
                frozenset(lifecycle_keys | {'execution_provenance'}),
            }:
                raise RequestFailure('request keys do not match schema v1')
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
            if 'artifact_revision' in request:
                _validate_lifecycle_fields(request)
                _dispatch_profile(request)
            route, slot_role = _validate_contract(request)
            limits = _load_policy()
            ledger = Ledger(_ledger_path())
            outcome = ledger.admit(request, route, slot_role, limits)
            if outcome.get('protocol_reason') == 'direct_sibling_active':
                outcome.pop('protocol_reason')
                _emit(
                    _response(command, 'direct_sibling_active', **outcome),
                    EXIT_INVALID,
                )
            if outcome.get('lifecycle_transition') in {
                'duplicate_launch', 'illegal_transition'
            }:
                _emit(
                    _response(
                        command, 'lifecycle_transition_rejected', **outcome
                    ),
                    EXIT_INVALID,
                )
            _emit(
                _response(
                    command,
                    _machine_reason(str(mode), str(outcome['policy_reason'])),
                    **outcome,
                ),
                EXIT_OK,
            )

        if command == 'bind_native':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'native_alias', 'public_agent_id', 'binding_source',
                    'notifications_available',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_identity(request['native_alias'], 'native'):
                raise RequestFailure('invalid native_alias')
            if not is_valid_public_agent_id(request['public_agent_id']):
                raise RequestFailure('invalid public_agent_id')
            if request['binding_source'] != NATIVE_BINDING_SOURCE:
                raise RequestFailure('invalid binding_source')
            if not isinstance(request['notifications_available'], bool):
                raise RequestFailure('notifications_available must be boolean')
            state = Ledger(_ledger_path()).bind_native(
                str(request['attempt_id']),
                str(request['native_alias']),
                str(request['public_agent_id']),
                str(request['binding_source']),
                request['notifications_available'],
            )
            _emit(
                _response(
                    command, 'native_bound', native_status=state,
                    wait_strategy=(
                        'external_completion_notification_no_poll'
                        if request['notifications_available']
                        else 'notifications_unavailable_no_polling'
                    ),
                ),
                EXIT_OK,
            )

        if command == 'native_notification':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'native_alias', 'public_agent_id',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_identity(request['native_alias'], 'native'):
                raise RequestFailure('invalid native_alias')
            if not is_valid_public_agent_id(request['public_agent_id']):
                raise RequestFailure('invalid public_agent_id')
            idempotent = Ledger(_ledger_path()).native_notification(
                str(request['attempt_id']),
                str(request['native_alias']),
                str(request['public_agent_id']),
            )
            _emit(
                _response(
                    command, 'native_notification_recorded', idempotent=idempotent
                ),
                EXIT_OK,
            )

        if command == 'native_read':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'native_alias', 'public_agent_id',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_identity(request['native_alias'], 'native'):
                raise RequestFailure('invalid native_alias')
            if not is_valid_public_agent_id(request['public_agent_id']):
                raise RequestFailure('invalid public_agent_id')
            Ledger(_ledger_path()).claim_native_read(
                str(request['attempt_id']),
                str(request['native_alias']),
                str(request['public_agent_id']),
            )
            _emit(
                _response(command, 'native_read_authorized', read_authorized=True),
                EXIT_OK,
            )

        if command == 'native_observation':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'native_alias', 'public_agent_id', 'observation',
                    'terminal_fingerprint',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_identity(request['native_alias'], 'native'):
                raise RequestFailure('invalid native_alias')
            if not is_valid_public_agent_id(request['public_agent_id']):
                raise RequestFailure('invalid public_agent_id')
            observation = request['observation']
            terminal = request['terminal_fingerprint']
            if observation not in {'found', 'not_found'}:
                raise RequestFailure('invalid native observation')
            if (
                observation == 'not_found'
                and not is_valid_fingerprint(terminal)
            ) or (observation == 'found' and terminal is not None):
                raise RequestFailure('invalid native observation fingerprint')
            state, orphaned = Ledger(_ledger_path()).observe_native(
                str(request['attempt_id']),
                str(request['native_alias']),
                str(request['public_agent_id']),
                str(observation),
                str(terminal) if terminal is not None else None,
            )
            _emit(
                _response(
                    command, 'native_observation_recorded', native_status=state,
                    orphaned_attempt_ids=orphaned,
                ),
                EXIT_OK,
            )

        if command == 'invalidate_native':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'native_alias', 'public_agent_id',
                    'invalidation_reason',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_identity(request['native_alias'], 'native'):
                raise RequestFailure('invalid native_alias')
            if not is_valid_public_agent_id(request['public_agent_id']):
                raise RequestFailure('invalid public_agent_id')
            if request['invalidation_reason'] not in NATIVE_INVALIDATION_REASONS:
                raise RequestFailure('invalid invalidation_reason')
            idempotent = Ledger(_ledger_path()).invalidate_native(
                str(request['attempt_id']),
                str(request['native_alias']),
                str(request['public_agent_id']),
                str(request['invalidation_reason']),
            )
            _emit(
                _response(
                    command, 'native_invalidated',
                    invalidation_reason=request['invalidation_reason'],
                    idempotent=idempotent,
                ),
                EXIT_OK,
            )

        if command == 'progress':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'progress_fingerprint',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if not is_valid_fingerprint(request['progress_fingerprint']):
                raise RequestFailure('invalid progress_fingerprint')
            progressed_at_ms, idempotent = Ledger(_ledger_path()).record_progress(
                str(request['attempt_id']), str(request['progress_fingerprint'])
            )
            _emit(
                _response(
                    command,
                    'progress_idempotent' if idempotent else 'progress_recorded',
                    last_progress_at_ms=progressed_at_ms, idempotent=idempotent,
                ),
                EXIT_OK,
            )

        if command == 'terminate_tree':
            _load_policy()
            _require_exact_keys(
                request,
                {
                    'schema_version', 'command', 'attempt_id',
                    'termination_reason', 'terminal_fingerprint',
                },
            )
            if not is_valid_identity(request['attempt_id'], 'attempt'):
                raise RequestFailure('invalid attempt_id')
            if request['termination_reason'] not in TERMINATION_STATUSES:
                raise RequestFailure('invalid termination_reason')
            if not is_valid_fingerprint(request['terminal_fingerprint']):
                raise RequestFailure('invalid terminal_fingerprint')
            status, orphaned, idempotent = Ledger(_ledger_path()).terminate_tree(
                str(request['attempt_id']), str(request['termination_reason']),
                str(request['terminal_fingerprint']),
            )
            _emit(
                _response(
                    command,
                    'tree_termination_idempotent'
                    if idempotent else 'tree_termination_recorded',
                    lifecycle_status=status, orphaned_attempt_ids=orphaned,
                    idempotent=idempotent,
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
    except NativeBoundary as exc:
        command = str(locals().get('command', 'invalid'))
        values: dict[str, object] = {}
        if command == 'native_read':
            values['read_authorized'] = False
        if command == 'admit':
            values.update(
                {
                    'policy_reason': None,
                    'would_reject': True,
                    'launch_authorized': False,
                }
            )
        _emit(
            _response(command, exc.reason_code, **values),
            EXIT_MODE
            if exc.reason_code == 'native_notifications_unavailable'
            else EXIT_INVALID,
        )
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
