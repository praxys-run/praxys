"""Agent invocation admission, lifecycle, and ledger contracts."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

import scripts.agent_invocation_control as invocation_control
from analysis.agentic_invocation_control import (
    AdmissionFacts,
    DECISION_REASONS,
    InvocationLimits,
    MACHINE_REASON_CODES,
    POLICY_REASONS,
    evaluate_admission,
    format_identity,
    is_valid_fingerprint,
    is_valid_identity,
    is_valid_public_agent_id,
)
from analysis.agentic_task_routing import TaskClassification, TaskRoute, route_task
from scripts.agent_invocation_control import (
    CommitOutcomeAmbiguous,
    FinishConflict,
    IdentityConflict,
    Ledger,
    NativeBoundary,
    RecoveryRequired,
    StateCorrupt,
    StateUnsupported,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'agent_invocation_control.py'
CLASSIFICATION_DIGEST = 'sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2'
ROUTE_DIGEST = 'sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51'

CONCURRENT_ADMISSION_WRAPPER = r"""
from pathlib import Path
import subprocess
import sys
import time

request_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
gate_path = Path(sys.argv[3])
script_path = sys.argv[4]
request = request_path.read_text(encoding='utf-8')
ready_path.touch()
deadline = time.monotonic() + 30
while not gate_path.exists():
    if time.monotonic() >= deadline:
        sys.stderr.write('timed out waiting for admission gate')
        raise SystemExit(124)
    time.sleep(0.005)
completed = subprocess.run(
    [sys.executable, script_path],
    input=request,
    capture_output=True,
    text=True,
    check=False,
)
sys.stdout.write(completed.stdout)
sys.stderr.write(completed.stderr)
raise SystemExit(completed.returncode)
"""


def opaque(kind: str, number: int) -> str:
    return format_identity(kind, f'{number:032x}')


def fingerprint(number: int) -> str:
    return f'fpr_{number:064x}'


def accepted_route() -> TaskRoute:
    return route_task(
        TaskClassification(
            primary_object='agent-system',
            impacts=[
                'repository-change',
                'agent-policy-or-autonomy',
                'architecture-boundary',
            ],
            risk_triggers=[
                'irreversible-or-high-blast-radius-action',
                'out-of-policy-or-out-of-distribution-decision',
            ],
        )
    )


def limits() -> InvocationLimits:
    return InvocationLimits(6, 8, 32, 3, 1, 2)


def admission(
    number: int,
    *,
    contract: int = 1,
    slot: int | None = None,
    generation: int | None = None,
    logical: int | None = None,
    parent: str | None = None,
    retry: str | None = None,
    mode: str = 'shadow',
    role: str = 'engineering',
) -> dict[str, object]:
    return {
        'schema_version': 2,
        'command': 'admit',
        'mode': mode,
        'primary_object': 'agent-system',
        'impacts': [
            'repository-change',
            'agent-policy-or-autonomy',
            'architecture-boundary',
        ],
        'risk_triggers': [
            'irreversible-or-high-blast-radius-action',
            'out-of-policy-or-out-of-distribution-decision',
        ],
        'classification_digest': CLASSIFICATION_DIGEST,
        'route_digest': ROUTE_DIGEST,
        'contract_id': opaque('contract', contract),
        'slot_id': opaque('slot', slot if slot is not None else number),
        'slot_role': role,
        'generation_id': opaque(
            'generation', generation if generation is not None else number
        ),
        'logical_id': opaque('logical', logical if logical is not None else number),
        'attempt_id': opaque('attempt', number),
        'parent_attempt_id': parent,
        'retry_fingerprint': retry,
    }


def lifecycle_admission(
    number: int,
    *,
    revision: int = 1,
    transition: str = 'initial_launch',
    replacement_of: int | None = None,
    dispatch_mode: str | None = None,
    execution_provenance: str | None = None,
    **values: object,
) -> dict[str, object]:
    request = admission(number, **values)
    request.update(
        {
            'artifact_revision': f'sha256:{revision:064x}',
            'lifecycle_transition': transition,
            'replacement_of_attempt_id': (
                opaque('attempt', replacement_of)
                if replacement_of is not None else None
            ),
        }
    )
    if dispatch_mode is not None:
        request['dispatch_mode'] = dispatch_mode
    if execution_provenance is not None:
        request['execution_provenance'] = execution_provenance
    return request


def background_admission(number: int, **values: object) -> dict[str, object]:
    return lifecycle_admission(
        number,
        dispatch_mode='background',
        execution_provenance='background_independent_immediate_no_poll',
        **values,
    )


def new_ledger(tmp_path: Path) -> Ledger:
    ledger = Ledger(tmp_path / 'control.sqlite3')
    assert ledger.initialize() is True
    return ledger


def downgrade_ledger_to_v2(ledger: Ledger) -> None:
    connection = sqlite3.connect(ledger.path)
    try:
        connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute(
            'DROP INDEX native_invocations_read_claim_fingerprint_uq'
        )
        connection.execute(
            'ALTER TABLE native_invocations DROP COLUMN read_claim_fingerprint'
        )
        connection.execute(
            "UPDATE metadata SET value = '2' WHERE key = 'schema_version'"
        )
        connection.commit()
    finally:
        connection.close()


def downgrade_ledger_to_v1(ledger: Ledger, layout: str) -> None:
    downgrade_ledger_to_v2(ledger)
    drop_tables = {
        'full': (),
        'lifecycle': (
            'native_binding_provenance',
            'lifecycle_dispatch',
        ),
        'base': (
            'native_binding_provenance',
            'lifecycle_dispatch',
            'active_work_keys',
            'replacement_eligibility',
            'native_invocations',
            'progress_evidence',
            'work_history',
            'lifecycle_decisions',
        ),
    }
    connection = sqlite3.connect(ledger.path)
    try:
        connection.execute('PRAGMA foreign_keys=OFF')
        for table in drop_tables[layout]:
            connection.execute(f'DROP TABLE {table}')
        connection.execute(
            "UPDATE metadata SET value = '1' WHERE key = 'schema_version'"
        )
        connection.commit()
    finally:
        connection.close()


def set_ledger_schema_version(
    ledger: Ledger, schema_version: int, legacy_layout: str
) -> None:
    if schema_version == 1:
        downgrade_ledger_to_v1(ledger, legacy_layout)
    elif schema_version == 2:
        downgrade_ledger_to_v2(ledger)
    elif schema_version != 3:
        raise ValueError('unsupported test ledger schema')


def finish(
    ledger: Ledger,
    attempt: int,
    terminal: int,
    status: str = 'failed',
) -> tuple[str, bool]:
    return ledger.finish(opaque('attempt', attempt), status, fingerprint(terminal))


def bind_notified_native(
    ledger: Ledger, number: int, public_agent_id: str
) -> str:
    native_alias = opaque('native', number)
    ledger.bind_native(
        opaque('attempt', number),
        native_alias,
        public_agent_id,
        'task_result',
    )
    ledger.native_notification(
        opaque('attempt', number), native_alias, public_agent_id
    )
    return native_alias


def race_native_claims(
    ledger: Ledger,
    claims: list[tuple[str, str, str, str]],
) -> list[tuple[str, object]]:
    barrier = threading.Barrier(len(claims) + 1)
    results: list[tuple[str, object]] = []
    result_lock = threading.Lock()

    def claim(values: tuple[str, str, str, str]) -> None:
        attempt_id, native_alias, public_agent_id, read_claim_id = values
        barrier.wait(timeout=30)
        try:
            outcome: object = ledger.claim_native_read(
                attempt_id,
                native_alias,
                public_agent_id,
                read_claim_id,
            )
        except BaseException as exc:
            outcome = exc
        with result_lock:
            results.append((read_claim_id, outcome))

    threads = [
        threading.Thread(target=claim, args=(values,))
        for values in claims
    ]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=30)
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()
    return results


def run_cli(repository: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=repository,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def init_repository(tmp_path: Path) -> Path:
    repository = tmp_path / 'repository'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)
    initialized = run_cli(repository, {'schema_version': 2, 'command': 'init'})
    assert initialized.returncode == 0
    assert json.loads(initialized.stdout)['reason_code'] == 'ledger_initialized'
    return repository


def test_pure_identity_and_policy_precedence() -> None:
    identity = opaque('contract', 1)
    assert is_valid_identity(identity, 'contract')
    assert not is_valid_identity(identity, 'slot')
    assert is_valid_fingerprint(fingerprint(1))
    facts = AdmissionFacts(
        kill_switch_active=False,
        duplicate_active=True,
        ancestor_slot_ids=(opaque('slot', 1),),
        proposed_slot_id=opaque('slot', 1),
        proposed_depth=7,
        active_count=8,
        logical_count=32,
        is_new_logical=True,
        retry_fingerprint=fingerprint(1),
        retries_for_fingerprint=1,
        attempt_count=3,
        recent_terminal_fingerprints=(fingerprint(2), fingerprint(2)),
    )
    decision = evaluate_admission(facts, limits())
    assert decision.policy_reason == 'duplicate_active'
    assert decision.would_reject is True
    assert decision.launch_authorized is True


def test_read_claim_identity_and_fingerprint_vector() -> None:
    read_claim_id = opaque('read_claim', 1)
    assert is_valid_identity(read_claim_id, 'read_claim')
    assert invocation_control._read_claim_fingerprint(read_claim_id) == (
        'sha256:63d8396ca0725fc208a724c7e0a7a042b8e8c74a02ad223b'
        'c1a77bbd3f3abff6'
    )
    for invalid in (
        'rcl_' + ('A' * 32),
        'rcl_' + ('1' * 31),
        'sha256:' + ('1' * 64),
        opaque('native', 1),
    ):
        assert not is_valid_identity(invalid, 'read_claim')


def test_reason_code_schemas_and_docs_are_exact() -> None:
    assert POLICY_REASONS == (
        'admit',
        'kill_switch_active',
        'duplicate_active',
        'ancestry_cycle',
        'ancestry_depth_limit',
        'active_contract_limit',
        'logical_contract_limit',
        'retry_fingerprint_limit',
        'attempt_limit',
        'no_progress',
    )
    assert DECISION_REASONS == (
        'admit',
        'work_contract_invalid',
        'kill_switch_active',
        'duplicate_active',
        'ancestry_cycle',
        'ancestry_depth_limit',
        'active_contract_limit',
        'logical_contract_limit',
        'retry_fingerprint_limit',
        'attempt_limit',
        'no_progress',
        'state_missing',
        'state_corrupt',
        'state_unsupported',
    )
    assert MACHINE_REASON_CODES == (
        'instrument_recorded',
        'shadow_would_admit',
        'shadow_would_deny_cycle',
        'shadow_would_deny_policy_limit',
        'invalid_request',
        'invalid_identity',
        'work_contract_unavailable',
        'work_contract_mismatch',
        'policy_unavailable',
        'recovery_required',
        'ledger_unavailable',
        'enforcement_unavailable',
        'kill_switch_active',
        'ledger_initialized',
        'ledger_ready',
        'identity_created',
        'finish_recorded',
        'finish_idempotent',
        'recovery_recorded',
        'kill_switch_updated',
        'status_reported',
        'lifecycle_transition_rejected',
        'native_bound',
        'native_notification_recorded',
        'completion_notification_required',
        'native_notifications_unavailable',
        'native_read_authorized',
        'native_read_refused',
        'native_observation_recorded',
        'progress_recorded',
        'progress_idempotent',
        'tree_termination_recorded',
        'tree_termination_idempotent',
        'direct_sibling_active',
        'execution_provenance_invalid',
        'native_binding_mismatch',
        'native_binding_invalidated',
        'native_invalidated',
    )

    implementation = (ROOT / 'docs/dev/agent-invocation-control.md').read_text(
        encoding='utf-8'
    )
    policy_section = implementation.split('Stable policy reasons:', 1)[1].split(
        'Stable machine reason codes', 1
    )[0]
    assert tuple(
        re.findall(r'^\| ([a-z_]+) \|', policy_section, flags=re.MULTILINE)
    ) == DECISION_REASONS
    machine_section = implementation.split(
        'Stable machine reason codes are', 1
    )[1].split('Additions must', 1)[0]
    assert tuple(re.findall(r'`([a-z_]+)`', machine_section)) == (
        MACHINE_REASON_CODES
    )

    adr = (ROOT / 'docs/dev/adr-2026-08-20-agent-invocation-control.md').read_text(
        encoding='utf-8'
    )
    adr_machine_section = adr.split(
        'Stable v1 machine reason-code namespace:', 1
    )[1].split('Meanings cannot change', 1)[0]
    assert tuple(re.findall(r'`([a-z_]+)`', adr_machine_section)) == (
        MACHINE_REASON_CODES
    )

    proposal = (
        ROOT / 'docs/dev/policy-change-proposal-agent-invocation-control-v1.md'
    ).read_text(encoding='utf-8')
    proposal_policy_section = proposal.split(
        '## Atomic admission decisions and stable reason codes', 1
    )[1].split('## Starting limits', 1)[0]
    assert tuple(
        re.findall(
            r'^\| [^|]+ \| `([a-z_]+)` \|',
            proposal_policy_section,
            flags=re.MULTILINE,
        )
    ) == DECISION_REASONS


def test_direct_indirect_cycles_depth_and_generation_semantics(tmp_path: Path) -> None:
    route = accepted_route()

    direct = new_ledger(tmp_path / 'direct')
    first = direct.admit(admission(1, slot=1), route, 'engineering', limits())
    assert first['policy_reason'] == 'admit'
    changed_generation_cycle = direct.admit(
        admission(2, slot=1, generation=2, parent=opaque('attempt', 1)),
        route,
        'engineering',
        limits(),
    )
    assert changed_generation_cycle['policy_reason'] == 'ancestry_cycle'
    assert changed_generation_cycle['launch_authorized'] is True

    indirect = new_ledger(tmp_path / 'indirect')
    indirect.admit(admission(101, slot=11), route, 'engineering', limits())
    indirect.admit(
        admission(102, slot=12, parent=opaque('attempt', 101)),
        route,
        'engineering',
        limits(),
    )
    cycle = indirect.admit(
        admission(103, slot=11, generation=103, parent=opaque('attempt', 102)),
        route,
        'engineering',
        limits(),
    )
    assert cycle['policy_reason'] == 'ancestry_cycle'

    deep = new_ledger(tmp_path / 'deep')
    parent = None
    for number in range(201, 207):
        result = deep.admit(
            admission(number, slot=number, parent=parent),
            route,
            'engineering',
            limits(),
        )
        assert result['policy_reason'] == 'admit'
        parent = opaque('attempt', number)
    beyond = deep.admit(
        admission(207, slot=207, parent=parent), route, 'engineering', limits()
    )
    assert beyond['policy_reason'] == 'ancestry_depth_limit'

    resumed = new_ledger(tmp_path / 'resumed')
    resumed.admit(admission(301, slot=31), route, 'engineering', limits())
    finish(resumed, 301, 301, 'succeeded')
    next_generation = resumed.admit(
        admission(302, slot=31, generation=302, logical=302),
        route,
        'engineering',
        limits(),
    )
    assert next_generation['policy_reason'] == 'admit'


def test_active_and_logical_contract_boundaries(tmp_path: Path) -> None:
    route = accepted_route()
    active = new_ledger(tmp_path / 'active')
    for number in range(1, 9):
        outcome = active.admit(
            admission(number, slot=number, generation=number, logical=number),
            route,
            'engineering',
            limits(),
        )
        assert outcome['policy_reason'] == 'admit'
    ninth = active.admit(admission(9, slot=9), route, 'engineering', limits())
    assert ninth['policy_reason'] == 'active_contract_limit'
    assert ninth['launch_authorized'] is True

    logical = new_ledger(tmp_path / 'logical')
    for number in range(101, 133):
        outcome = logical.admit(
            admission(number, slot=55, generation=number, logical=number),
            route,
            'engineering',
            limits(),
        )
        assert outcome['policy_reason'] == 'admit'
        finish(logical, number, number, 'succeeded')
    thirty_third = logical.admit(
        admission(133, slot=55, generation=133, logical=133),
        route,
        'engineering',
        limits(),
    )
    assert thirty_third['policy_reason'] == 'logical_contract_limit'


def test_attempt_retry_and_no_progress_boundaries(tmp_path: Path) -> None:
    route = accepted_route()
    attempts = new_ledger(tmp_path / 'attempts')
    attempts.admit(admission(1, slot=1, logical=1), route, 'engineering', limits())
    finish(attempts, 1, 1)
    attempts.admit(
        admission(2, slot=1, logical=1, retry=fingerprint(1)),
        route,
        'engineering',
        limits(),
    )
    finish(attempts, 2, 2)
    attempts.admit(
        admission(3, slot=1, logical=1, retry=fingerprint(2)),
        route,
        'engineering',
        limits(),
    )
    finish(attempts, 3, 3)
    fourth = attempts.admit(
        admission(4, slot=1, logical=1, retry=fingerprint(3)),
        route,
        'engineering',
        limits(),
    )
    assert fourth['policy_reason'] == 'attempt_limit'

    retries = new_ledger(tmp_path / 'retries')
    retries.admit(admission(11, slot=11, logical=11), route, 'engineering', limits())
    finish(retries, 11, 11)
    retries.admit(
        admission(12, slot=11, logical=11, retry=fingerprint(11)),
        route,
        'engineering',
        limits(),
    )
    finish(retries, 12, 12)
    repeated_retry = retries.admit(
        admission(13, slot=11, logical=11, retry=fingerprint(11)),
        route,
        'engineering',
        limits(),
    )
    assert repeated_retry['policy_reason'] == 'retry_fingerprint_limit'

    progress = new_ledger(tmp_path / 'progress')
    progress.admit(admission(21, slot=21), route, 'engineering', limits())
    finish(progress, 21, 99, 'failed')
    progress.admit(
        admission(22, slot=21, generation=22, logical=22),
        route,
        'engineering',
        limits(),
    )
    finish(progress, 22, 99, 'succeeded')
    stopped = progress.admit(
        admission(23, slot=21, generation=23, logical=23),
        route,
        'engineering',
        limits(),
    )
    assert stopped['policy_reason'] == 'no_progress'


def test_kill_switch_is_the_only_blocking_candidate_decision(tmp_path: Path) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.set_kill_switch(True)
    blocked = ledger.admit(admission(1), route, 'engineering', limits())
    assert blocked == {
        'decision_id': blocked['decision_id'],
        'policy_reason': 'kill_switch_active',
        'would_reject': True,
        'launch_authorized': False,
    }
    state = ledger.status()
    assert state['counts']['decisions'] == 1
    assert state['counts']['active_attempts'] == 0
    ledger.set_kill_switch(False)
    admitted = ledger.admit(admission(2), route, 'engineering', limits())
    assert admitted['launch_authorized'] is True


def test_cli_instrument_duplicate_and_kill_switch_contract(tmp_path: Path) -> None:
    repository = init_repository(tmp_path)
    first = admission(1, slot=1, generation=1, logical=1, mode='instrument')
    assert run_cli(repository, first).returncode == 0
    duplicate = admission(2, slot=1, generation=1, logical=1, mode='instrument')
    duplicate_result = run_cli(repository, duplicate)
    duplicate_payload = json.loads(duplicate_result.stdout)
    assert duplicate_result.returncode == 0
    assert duplicate_payload['reason_code'] == 'instrument_recorded'
    assert duplicate_payload['policy_reason'] == 'duplicate_active'
    assert duplicate_payload['would_reject'] is True
    assert duplicate_payload['launch_authorized'] is True

    switched = run_cli(
        repository,
        {'schema_version': 2, 'command': 'kill_switch', 'active': True},
    )
    assert switched.returncode == 0
    blocked = run_cli(repository, admission(3, slot=3, mode='shadow'))
    blocked_payload = json.loads(blocked.stdout)
    assert blocked.returncode == 0
    assert blocked_payload['reason_code'] == 'kill_switch_active'
    assert blocked_payload['policy_reason'] == 'kill_switch_active'
    assert blocked_payload['would_reject'] is True
    assert blocked_payload['launch_authorized'] is False


def test_parent_binding_leaf_first_recovery_and_finish_idempotency(tmp_path: Path) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(admission(1, contract=1, slot=1), route, 'engineering', limits())
    with pytest.raises(IdentityConflict):
        ledger.admit(
            admission(2, contract=2, slot=2, parent=opaque('attempt', 1)),
            route,
            'engineering',
            limits(),
        )
    ledger.admit(
        admission(3, contract=1, slot=3, parent=opaque('attempt', 1)),
        route,
        'engineering',
        limits(),
    )
    with pytest.raises(RecoveryRequired):
        finish(ledger, 1, 1)
    assert ledger.finish(opaque('attempt', 3), 'recovered', fingerprint(3)) == (
        'recovered',
        False,
    )
    assert finish(ledger, 1, 1) == ('failed', False)
    assert finish(ledger, 1, 1) == ('failed', True)
    with pytest.raises(FinishConflict):
        finish(ledger, 1, 2)


def test_old_active_attempt_never_recovers_by_timeout(tmp_path: Path) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(admission(1), accepted_route(), 'engineering', limits())
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('UPDATE attempts SET admitted_at_ms = 0')
    assert ledger.status()['counts']['active_attempts'] == 1
    assert ledger.initialize() is False
    assert ledger.status()['counts']['active_attempts'] == 1


def test_missing_corrupt_and_unsupported_state_are_visible_non_enforcement(
    tmp_path: Path,
) -> None:
    repository = tmp_path / 'repository'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)

    def assert_nonblocking_state(
        result: subprocess.CompletedProcess[str], expected_reason: str
    ) -> None:
        assert result.returncode == 4
        assert json.loads(result.stdout) == {
            'schema_version': 2,
            'policy_version': 'agent-invocation-control-v1',
            'command': 'admit',
            'reason_code': 'ledger_unavailable',
            'policy_reason': expected_reason,
            'would_reject': True,
            'launch_authorized': True,
        }

    assert_nonblocking_state(
        run_cli(repository, admission(1, mode='instrument')), 'state_missing'
    )
    assert_nonblocking_state(
        run_cli(repository, admission(2, mode='shadow')), 'state_missing'
    )

    ledger_path = repository / '.git' / 'praxys' / 'agent-invocation-control-v1.sqlite3'
    ledger_path.parent.mkdir()
    ledger_path.write_bytes(b'not a sqlite ledger')
    assert_nonblocking_state(
        run_cli(repository, admission(3, mode='instrument')), 'state_corrupt'
    )
    assert_nonblocking_state(
        run_cli(repository, admission(4, mode='shadow')), 'state_corrupt'
    )

    shutil.rmtree(ledger_path.parent)
    initialized = run_cli(repository, {'schema_version': 2, 'command': 'init'})
    assert initialized.returncode == 0
    with sqlite3.connect(ledger_path) as connection:
        connection.execute("DELETE FROM metadata WHERE key = 'policy_version'")
    assert_nonblocking_state(
        run_cli(repository, admission(5, mode='shadow')), 'state_corrupt'
    )

    shutil.rmtree(ledger_path.parent)
    initialized = run_cli(repository, {'schema_version': 2, 'command': 'init'})
    assert initialized.returncode == 0
    with sqlite3.connect(ledger_path) as connection:
        connection.execute('DROP TABLE attempts')
    assert_nonblocking_state(
        run_cli(repository, admission(6, mode='instrument')), 'state_corrupt'
    )
    assert_nonblocking_state(
        run_cli(repository, admission(16, mode='shadow')), 'state_corrupt'
    )
    damaged_status = run_cli(
        repository, {'schema_version': 2, 'command': 'status'}
    )
    assert damaged_status.returncode == 4
    assert json.loads(damaged_status.stdout)['policy_reason'] == 'state_corrupt'

    shutil.rmtree(ledger_path.parent)
    initialized = run_cli(repository, {'schema_version': 2, 'command': 'init'})
    assert initialized.returncode == 0
    for number, (key, supported_value) in enumerate(
        (
            ('schema_version', '1'),
            ('policy_version', 'agent-invocation-control-v1'),
        ),
        start=7,
    ):
        with sqlite3.connect(ledger_path) as connection:
            connection.execute(
                'UPDATE metadata SET value = ? WHERE key = ?',
                ('unsupported-v2', key),
            )
        assert_nonblocking_state(
            run_cli(repository, admission(number, mode='instrument')),
            'state_unsupported',
        )
        assert_nonblocking_state(
            run_cli(repository, admission(number + 10, mode='shadow')),
            'state_unsupported',
        )
        with sqlite3.connect(ledger_path) as connection:
            connection.execute(
                'UPDATE metadata SET value = ? WHERE key = ?',
                (supported_value, key),
            )


def test_work_contract_guard_precedes_missing_ledger_and_enforce_is_unavailable(
    tmp_path: Path,
) -> None:
    repository = tmp_path / 'repository'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)
    mismatched = admission(1)
    mismatched['route_digest'] = 'sha256:' + ('0' * 64)
    guarded = run_cli(repository, mismatched)
    payload = json.loads(guarded.stdout)
    assert guarded.returncode == 3
    assert payload['reason_code'] == 'work_contract_mismatch'
    assert payload['policy_reason'] == 'work_contract_invalid'
    assert payload['launch_authorized'] is True

    enforce = admission(2)
    enforce['mode'] = 'enforce'
    unavailable = run_cli(repository, enforce)
    assert unavailable.returncode == 5
    assert json.loads(unavailable.stdout) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'admit',
        'reason_code': 'enforcement_unavailable',
        'policy_reason': None,
        'would_reject': None,
        'launch_authorized': None,
    }


def test_concurrent_process_duplicate_admissions_are_atomic(tmp_path: Path) -> None:
    repository = init_repository(tmp_path)
    coordination = tmp_path / 'concurrent-admission'
    coordination.mkdir()
    gate_path = coordination / 'release'
    processes: list[subprocess.Popen[str]] = []
    ready_paths: list[Path] = []

    for number in range(1, 7):
        request_path = coordination / f'request-{number}.json'
        ready_path = coordination / f'ready-{number}'
        request_path.write_text(
            json.dumps(admission(number, slot=1, generation=1, logical=1)),
            encoding='utf-8',
        )
        ready_paths.append(ready_path)
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    '-c',
                    CONCURRENT_ADMISSION_WRAPPER,
                    str(request_path),
                    str(ready_path),
                    str(gate_path),
                    str(SCRIPT),
                ],
                cwd=repository,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    ready_deadline = time.monotonic() + 30
    while not all(path.exists() for path in ready_paths):
        failed = [process for process in processes if process.poll() is not None]
        assert not failed, 'an admission wrapper exited before reaching the gate'
        assert time.monotonic() < ready_deadline, 'admission wrappers were not ready'
        time.sleep(0.005)

    gate_path.touch()
    results = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        results.append(json.loads(stdout))

    reasons = [result['policy_reason'] for result in results]
    assert reasons.count('admit') == 1
    assert reasons.count('duplicate_active') == 5
    assert all(result['launch_authorized'] is True for result in results)
    assert all(
        result['reason_code'] in {'shadow_would_admit', 'shadow_would_deny_policy_limit'}
        for result in results
    )

    status = run_cli(repository, {'schema_version': 2, 'command': 'status'})
    assert status.returncode == 0
    durable = json.loads(status.stdout)
    assert durable['counts']['decisions'] == 6
    assert durable['counts']['active_attempts'] == 6
    assert durable['decision_counts'] == {
        'admit': 1,
        'duplicate_active': 5,
    }


def test_concurrent_same_parent_lifecycle_siblings_create_at_most_one_attempt(
    tmp_path: Path,
) -> None:
    repository = init_repository(tmp_path)
    parent = run_cli(repository, lifecycle_admission(100, slot=100))
    assert parent.returncode == 0
    coordination = tmp_path / 'concurrent-siblings'
    coordination.mkdir()
    gate_path = coordination / 'release'
    processes: list[subprocess.Popen[str]] = []
    ready_paths: list[Path] = []

    for number in (101, 102):
        request_path = coordination / f'request-{number}.json'
        ready_path = coordination / f'ready-{number}'
        request_path.write_text(
            json.dumps(
                lifecycle_admission(
                    number,
                    slot=number,
                    revision=number,
                    parent=opaque('attempt', 100),
                )
            ),
            encoding='utf-8',
        )
        ready_paths.append(ready_path)
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    '-c',
                    CONCURRENT_ADMISSION_WRAPPER,
                    str(request_path),
                    str(ready_path),
                    str(gate_path),
                    str(SCRIPT),
                ],
                cwd=repository,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    ready_deadline = time.monotonic() + 30
    while not all(path.exists() for path in ready_paths):
        assert all(process.poll() is None for process in processes)
        assert time.monotonic() < ready_deadline
        time.sleep(0.005)
    gate_path.touch()

    results: list[tuple[int, dict[str, object]]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert not stderr
        results.append((int(process.returncode), json.loads(stdout)))

    assert sorted(result[0] for result in results) == [0, 2]
    assert [result[1]['reason_code'] for result in results].count(
        'direct_sibling_active'
    ) == 1
    with sqlite3.connect(
        repository / '.git' / 'praxys' / 'agent-invocation-control-v1.sqlite3'
    ) as connection:
        assert connection.execute(
            """SELECT COUNT(*) FROM attempts
            WHERE parent_attempt_id = ? AND lifecycle_status = 'active'""",
            (opaque('attempt', 100),),
        ).fetchone()[0] == 1


def test_open_validation_uses_one_snapshot_across_dispatch_queries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1),
        route,
        'engineering',
        limits(),
    )
    main_thread = threading.get_ident()
    start_writer = threading.Event()
    writer_done = threading.Event()
    writer_errors: list[BaseException] = []
    real_expected_dispatch = Ledger._expected_dispatch_records
    coordinated = False

    def expected_dispatch(
        connection: sqlite3.Connection,
    ) -> dict[str, tuple[str, str, int]]:
        nonlocal coordinated
        result = real_expected_dispatch(connection)
        if threading.get_ident() == main_thread and not coordinated:
            coordinated = True
            start_writer.set()
            assert writer_done.wait(30)
        return result

    def write_lifecycle_decision() -> None:
        assert start_writer.wait(30)
        try:
            ledger.admit(
                lifecycle_admission(2, slot=2, revision=2),
                route,
                'engineering',
                limits(),
            )
        except BaseException as exc:
            writer_errors.append(exc)
        finally:
            writer_done.set()

    monkeypatch.setattr(
        Ledger,
        '_expected_dispatch_records',
        staticmethod(expected_dispatch),
    )
    writer = threading.Thread(target=write_lifecycle_decision)
    writer.start()
    assert ledger.status()['counts']['decisions'] == 2
    writer.join(timeout=30)
    assert not writer.is_alive()
    assert writer_errors == []


def test_lifecycle_sibling_scope_allows_finish_nesting_and_unrelated_parents(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    for number in (1, 2):
        ledger.admit(
            lifecycle_admission(number, slot=number, revision=number),
            route,
            'engineering',
            limits(),
        )
    first_child = ledger.admit(
        lifecycle_admission(
            3, slot=3, revision=3, parent=opaque('attempt', 1)
        ),
        route,
        'engineering',
        limits(),
    )
    unrelated_child = ledger.admit(
        lifecycle_admission(
            4, slot=4, revision=4, parent=opaque('attempt', 2)
        ),
        route,
        'engineering',
        limits(),
    )
    nested = ledger.admit(
        lifecycle_admission(
            5, slot=5, revision=5, parent=opaque('attempt', 3)
        ),
        route,
        'engineering',
        limits(),
    )
    assert first_child['launch_authorized'] is True
    assert unrelated_child['launch_authorized'] is True
    assert nested['launch_authorized'] is True

    finish(ledger, 5, 5, 'succeeded')
    finish(ledger, 3, 3, 'succeeded')
    next_sibling = ledger.admit(
        lifecycle_admission(
            6, slot=6, revision=6, parent=opaque('attempt', 1)
        ),
        route,
        'engineering',
        limits(),
    )
    assert next_sibling['launch_authorized'] is True


def test_ledger_is_wal_foreign_keyed_and_persists_no_raw_content(tmp_path: Path) -> None:
    repository = init_repository(tmp_path)
    valid = admission(1, mode='instrument')
    recorded = run_cli(repository, valid)
    assert recorded.returncode == 0
    assert json.loads(recorded.stdout)['reason_code'] == 'instrument_recorded'
    background = run_cli(
        repository, background_admission(3, mode='instrument')
    )
    assert background.returncode == 0

    sentinels = {
        'prompt': 'RAW_PROMPT_SENTINEL',
        'task': 'RAW_TASK_SENTINEL',
        'issue': 'RAW_ISSUE_SENTINEL',
        'user': 'RAW_USER_SENTINEL',
        'code': 'RAW_CODE_SENTINEL',
        'credential': 'RAW_CREDENTIAL_SENTINEL',
        'artifact': 'RAW_ARTIFACT_SENTINEL',
        'public_agent_id': 'RAW_PUBLIC_AGENT_ID_SENTINEL',
    }
    bound = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'bind_native',
            'attempt_id': opaque('attempt', 3),
            'native_alias': opaque('native', 3),
            'public_agent_id': sentinels['public_agent_id'],
            'binding_source': 'task_result',
            'notifications_available': True,
        },
    )
    assert bound.returncode == 0
    invalid = dict(admission(2))
    invalid.update(sentinels)
    rejected = run_cli(repository, invalid)
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)['reason_code'] == 'invalid_request'

    ledger_path = repository / '.git' / 'praxys' / 'agent-invocation-control-v1.sqlite3'
    with sqlite3.connect(ledger_path) as connection:
        assert connection.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        connection.execute('PRAGMA foreign_keys=ON')
        assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        columns = {
            row[1]
            for table in (
                'contracts', 'slots', 'generations', 'logical_invocations',
                'decisions', 'attempts', 'lifecycle_decisions', 'work_history',
                'active_work_keys', 'replacement_eligibility',
                'native_invocations', 'progress_evidence',
                'lifecycle_dispatch', 'native_binding_provenance',
            )
            for row in connection.execute(f'PRAGMA table_info({table})')
        }
        assert not columns & set(sentinels)
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    persisted = b''.join(
        path.read_bytes()
        for path in ledger_path.parent.iterdir()
        if path.is_file()
    )
    for sentinel in sentinels.values():
        assert sentinel.encode() not in persisted


def test_explicit_init_migrates_original_v1_ledger_to_v3(tmp_path: Path) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(admission(1), accepted_route(), 'engineering', limits())
    downgrade_ledger_to_v1(ledger, 'base')
    assert ledger.initialize() is False
    assert ledger.status()['counts']['active_attempts'] == 1
    assert finish(ledger, 1, 1, 'succeeded') == ('succeeded', False)
    assert finish(ledger, 1, 1, 'succeeded') == ('succeeded', True)
    with sqlite3.connect(ledger.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert {
        'lifecycle_decisions',
        'work_history',
        'active_work_keys',
        'replacement_eligibility',
        'native_invocations',
        'progress_evidence',
        'lifecycle_dispatch',
        'native_binding_provenance',
    }.issubset(tables)
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '3'
        assert {
            row[1]
            for row in connection.execute('PRAGMA table_info(native_invocations)')
        } >= {'read_claim_fingerprint'}


def test_explicit_init_upgrades_745_lifecycle_ledger_transactionally(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    downgrade_ledger_to_v1(ledger, 'lifecycle')
    assert ledger.initialize() is False
    with sqlite3.connect(ledger.path) as connection:
        dispatch = connection.execute(
            """SELECT dispatch_mode, execution_provenance, admission_reason
            FROM lifecycle_dispatch WHERE attempt_id = ?""",
            (opaque('attempt', 1),),
        ).fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert dispatch == ('sync', 'sync_inline', 'admit')
    assert {
        'lifecycle_dispatch',
        'native_binding_provenance',
    }.issubset(tables)


def test_explicit_init_versions_full_v1_without_rewriting_auxiliary_rows(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    ledger.bind_native(
        opaque('attempt', 1),
        opaque('native', 1),
        'task-agent-full-v1',
        'task_result',
    )
    with sqlite3.connect(ledger.path) as connection:
        dispatch_before = connection.execute(
            'SELECT * FROM lifecycle_dispatch ORDER BY decision_id'
        ).fetchall()
        provenance_before = connection.execute(
            'SELECT * FROM native_binding_provenance ORDER BY native_alias'
        ).fetchall()
    downgrade_ledger_to_v1(ledger, 'full')

    with pytest.raises(StateUnsupported):
        ledger.status()
    assert ledger.initialize() is False

    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '3'
        assert connection.execute(
            'SELECT * FROM lifecycle_dispatch ORDER BY decision_id'
        ).fetchall() == dispatch_before
        assert connection.execute(
            'SELECT * FROM native_binding_provenance ORDER BY native_alias'
        ).fetchall() == provenance_before


def test_existing_init_locks_before_inspecting_migration_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v1(ledger, 'base')
    real_read_metadata = Ledger._read_metadata
    real_classify_layout = Ledger._classify_layout

    def locked_read_metadata(
        connection: sqlite3.Connection,
    ) -> dict[str, str]:
        assert connection.in_transaction
        return real_read_metadata(connection)

    def locked_classify_layout(
        cls: type[Ledger], connection: sqlite3.Connection
    ) -> str:
        del cls
        assert connection.in_transaction
        return real_classify_layout(connection)

    monkeypatch.setattr(
        Ledger, '_read_metadata', staticmethod(locked_read_metadata)
    )
    monkeypatch.setattr(
        Ledger, '_classify_layout', classmethod(locked_classify_layout)
    )
    assert ledger.initialize() is False


def test_concurrent_explicit_initializers_share_one_v1_to_v3_migration(
    tmp_path: Path,
) -> None:
    repository = init_repository(tmp_path)
    ledger = Ledger(
        repository / '.git' / 'praxys' / 'agent-invocation-control-v1.sqlite3'
    )
    downgrade_ledger_to_v1(ledger, 'base')
    coordination = tmp_path / 'concurrent-init'
    coordination.mkdir()
    gate_path = coordination / 'release'
    processes: list[subprocess.Popen[str]] = []
    ready_paths: list[Path] = []

    for number in range(4):
        request_path = coordination / f'request-{number}.json'
        ready_path = coordination / f'ready-{number}'
        request_path.write_text(
            json.dumps({'schema_version': 2, 'command': 'init'}),
            encoding='utf-8',
        )
        ready_paths.append(ready_path)
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    '-c',
                    CONCURRENT_ADMISSION_WRAPPER,
                    str(request_path),
                    str(ready_path),
                    str(gate_path),
                    str(SCRIPT),
                ],
                cwd=repository,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    ready_deadline = time.monotonic() + 30
    while not all(path.exists() for path in ready_paths):
        assert all(process.poll() is None for process in processes)
        assert time.monotonic() < ready_deadline
        time.sleep(0.005)
    gate_path.touch()

    results: list[dict[str, object]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        results.append(json.loads(stdout))
    assert {result['reason_code'] for result in results} == {'ledger_ready'}
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '3'


def test_concurrent_explicit_initializers_share_one_new_v3_ledger(
    tmp_path: Path,
) -> None:
    repository = tmp_path / 'repository'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)
    coordination = tmp_path / 'concurrent-new-init'
    coordination.mkdir()
    gate_path = coordination / 'release'
    processes: list[subprocess.Popen[str]] = []
    ready_paths: list[Path] = []

    for number in range(4):
        request_path = coordination / f'request-{number}.json'
        ready_path = coordination / f'ready-{number}'
        request_path.write_text(
            json.dumps({'schema_version': 2, 'command': 'init'}),
            encoding='utf-8',
        )
        ready_paths.append(ready_path)
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    '-c',
                    CONCURRENT_ADMISSION_WRAPPER,
                    str(request_path),
                    str(ready_path),
                    str(gate_path),
                    str(SCRIPT),
                ],
                cwd=repository,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )

    ready_deadline = time.monotonic() + 30
    while not all(path.exists() for path in ready_paths):
        assert all(process.poll() is None for process in processes)
        assert time.monotonic() < ready_deadline
        time.sleep(0.005)
    gate_path.touch()

    results: list[dict[str, object]] = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr
        results.append(json.loads(stdout))
    reasons = [result['reason_code'] for result in results]
    assert reasons.count('ledger_initialized') == 1
    assert reasons.count('ledger_ready') == 3


def test_new_initializers_publish_only_a_complete_v3_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = Ledger(tmp_path / 'control.sqlite3')
    initialized = threading.Barrier(3)
    publish = threading.Event()
    results: list[bool] = []
    errors: list[BaseException] = []
    real_initialize_new = Ledger._initialize_new

    def delayed_initialize_new(candidate: Ledger) -> bool:
        result = real_initialize_new(candidate)
        initialized.wait(timeout=30)
        assert publish.wait(30)
        return result

    def initialize() -> None:
        try:
            results.append(ledger.initialize())
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(Ledger, '_initialize_new', delayed_initialize_new)
    threads = [threading.Thread(target=initialize) for _ in range(2)]
    for thread in threads:
        thread.start()
    initialized.wait(timeout=30)
    assert not ledger.path.exists()
    publish.set()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()
    assert errors == []
    assert sorted(results) == [False, True]
    assert ledger.status()['counts']['decisions'] == 0


def test_fresh_init_allocation_failure_uses_the_json_error_protocol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger_path = tmp_path / 'control.sqlite3'

    def fail_allocation(*_args: object, **_kwargs: object) -> tuple[int, str]:
        raise OSError('injected allocation failure')

    monkeypatch.setattr(invocation_control, '_ledger_path', lambda: ledger_path)
    monkeypatch.setattr(invocation_control.tempfile, 'mkstemp', fail_allocation)
    monkeypatch.setattr(
        sys,
        'stdin',
        io.StringIO(json.dumps({'schema_version': 2, 'command': 'init'})),
    )
    with pytest.raises(SystemExit) as exit_info:
        invocation_control.main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 4
    assert captured.err == ''
    assert json.loads(captured.out) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'init',
        'reason_code': 'ledger_unavailable',
        'policy_reason': 'state_corrupt',
    }


def test_existing_init_does_not_change_non_wal_v1_before_refusing(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v1(ledger, 'base')
    connection = sqlite3.connect(ledger.path)
    try:
        assert connection.execute(
            'PRAGMA wal_checkpoint(TRUNCATE)'
        ).fetchone() is not None
    finally:
        connection.close()
    connection = sqlite3.connect(ledger.path)
    try:
        assert connection.execute('PRAGMA journal_mode=DELETE').fetchone()[0] == (
            'delete'
        )
    finally:
        connection.close()

    with pytest.raises(StateCorrupt):
        ledger.initialize()

    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '1'
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert 'lifecycle_decisions' not in tables


@pytest.mark.parametrize(
    'mutation', ['extra_table', 'extra_view', 'changed_constraint']
)
def test_v1_migration_refuses_unknown_schema_fingerprints(
    tmp_path: Path,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v1(ledger, 'base')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        if mutation == 'extra_table':
            connection.execute('CREATE TABLE unexpected(value TEXT) STRICT')
        elif mutation == 'extra_view':
            connection.execute(
                'CREATE VIEW unexpected_view AS SELECT value FROM metadata'
            )
        else:
            connection.execute('ALTER TABLE control RENAME TO old_control')
            connection.execute(
                """CREATE TABLE control (
                    singleton INTEGER PRIMARY KEY,
                    kill_switch INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                ) STRICT"""
            )
            connection.execute(
                'INSERT INTO control SELECT * FROM old_control'
            )
            connection.execute('DROP TABLE old_control')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '1'


def test_lifecycle_v1_dispatch_backfill_preserves_all_historical_reasons(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1, revision=1),
        route,
        'engineering',
        limits(),
    )
    ledger.admit(
        lifecycle_admission(
            2,
            slot=2,
            revision=2,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    direct_sibling = ledger.admit(
        lifecycle_admission(
            3,
            slot=3,
            revision=3,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    duplicate = ledger.admit(
        lifecycle_admission(
            4,
            slot=1,
            generation=4,
            logical=4,
            revision=1,
            transition='resume',
        ),
        route,
        'engineering',
        limits(),
    )
    ledger.set_kill_switch(True)
    denied = ledger.admit(
        lifecycle_admission(5, slot=5, revision=5),
        route,
        'engineering',
        limits(),
    )
    ledger.set_kill_switch(False)
    finish(ledger, 2, 2, 'succeeded')

    expected_reasons = {
        direct_sibling['decision_id']: 'direct_sibling_active',
        duplicate['decision_id']: 'lifecycle_transition_rejected',
        denied['decision_id']: 'policy_denied',
    }
    with sqlite3.connect(ledger.path) as connection:
        admitted = connection.execute(
            """SELECT decision_id FROM lifecycle_dispatch
            WHERE admission_reason = 'admit' ORDER BY decision_id"""
        ).fetchall()
        expected_reasons.update(
            {decision_id: 'admit' for (decision_id,) in admitted}
        )
    downgrade_ledger_to_v1(ledger, 'lifecycle')

    assert ledger.initialize() is False
    with sqlite3.connect(ledger.path) as connection:
        actual = {
            decision_id: (reason, recorded_at_ms, decided_at_ms)
            for decision_id, reason, recorded_at_ms, decided_at_ms
            in connection.execute(
                """SELECT dispatch.decision_id, dispatch.admission_reason,
                          dispatch.recorded_at_ms, lifecycle.decided_at_ms
                FROM lifecycle_dispatch dispatch
                JOIN lifecycle_decisions lifecycle USING (decision_id)"""
            )
        }
    assert {key: value[0] for key, value in actual.items()} == expected_reasons
    assert all(recorded == decided for _, recorded, decided in actual.values())


def test_full_v1_migration_refuses_conflicting_auxiliary_rows(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    downgrade_ledger_to_v1(ledger, 'full')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            """UPDATE lifecycle_dispatch
            SET admission_reason = 'policy_denied'"""
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '1'


def test_full_v1_migration_refuses_mismatched_dispatch_profile(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    downgrade_ledger_to_v1(ledger, 'full')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            """UPDATE lifecycle_dispatch
            SET execution_provenance =
                'background_independent_immediate_no_poll'"""
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '1'


def test_full_v1_migration_requires_provenance_for_every_native_invocation(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    ledger.bind_native(
        opaque('attempt', 1),
        opaque('native', 1),
        'task-agent-missing-provenance',
        'task_result',
    )
    downgrade_ledger_to_v1(ledger, 'full')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute('DELETE FROM native_binding_provenance')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '1'


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    'mutation',
    ['missing_attempt', 'generation_id', 'logical_id', 'parent_attempt_id'],
)
def test_validation_requires_exact_authorized_base_attempt(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    ledger.admit(
        lifecycle_admission(2, slot=2, revision=2),
        route,
        'engineering',
        limits(),
    )
    set_ledger_schema_version(ledger, schema_version, 'base')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        if mutation == 'missing_attempt':
            if schema_version != 1:
                connection.execute(
                    'DELETE FROM active_work_keys WHERE attempt_id = ?',
                    (opaque('attempt', 2),),
                )
                connection.execute(
                    'DELETE FROM work_history WHERE attempt_id = ?',
                    (opaque('attempt', 2),),
                )
            connection.execute(
                'DELETE FROM attempts WHERE attempt_id = ?',
                (opaque('attempt', 2),),
            )
        elif mutation == 'generation_id':
            connection.execute(
                'UPDATE attempts SET generation_id = ? WHERE attempt_id = ?',
                (opaque('generation', 2), opaque('attempt', 1)),
            )
        elif mutation == 'logical_id':
            connection.execute(
                'UPDATE attempts SET logical_id = ? WHERE attempt_id = ?',
                (opaque('logical', 2), opaque('attempt', 1)),
            )
        else:
            connection.execute(
                'UPDATE attempts SET parent_attempt_id = ? WHERE attempt_id = ?',
                (opaque('attempt', 1), opaque('attempt', 2)),
            )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    'mutation',
    ['self_cycle', 'two_node_cycle', 'root_depth', 'child_depth'],
)
def test_validation_rejects_parent_cycles_and_inconsistent_depths(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    ledger.admit(
        lifecycle_admission(
            2,
            slot=2,
            revision=2,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    set_ledger_schema_version(ledger, schema_version, 'base')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        if mutation == 'self_cycle':
            connection.execute(
                'UPDATE attempts SET parent_attempt_id = ? WHERE attempt_id = ?',
                (opaque('attempt', 2), opaque('attempt', 2)),
            )
            connection.execute(
                'UPDATE decisions SET parent_attempt_id = ? WHERE attempt_id = ?',
                (opaque('attempt', 2), opaque('attempt', 2)),
            )
        elif mutation == 'two_node_cycle':
            connection.execute(
                'UPDATE attempts SET parent_attempt_id = ? WHERE attempt_id = ?',
                (opaque('attempt', 2), opaque('attempt', 1)),
            )
            connection.execute(
                'UPDATE decisions SET parent_attempt_id = ? WHERE attempt_id = ?',
                (opaque('attempt', 2), opaque('attempt', 1)),
            )
        elif mutation == 'root_depth':
            connection.execute(
                'UPDATE attempts SET depth = 2 WHERE attempt_id = ?',
                (opaque('attempt', 1),),
            )
        else:
            connection.execute(
                'UPDATE attempts SET depth = 1 WHERE attempt_id = ?',
                (opaque('attempt', 2),),
            )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
def test_validation_rejects_multiple_active_lifecycle_direct_siblings(
    tmp_path: Path,
    schema_version: int,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    ledger.admit(
        lifecycle_admission(
            2,
            slot=2,
            revision=2,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    ledger.admit(
        lifecycle_admission(3, slot=3, revision=3),
        route,
        'engineering',
        limits(),
    )
    set_ledger_schema_version(ledger, schema_version, 'full')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute(
            """UPDATE attempts SET parent_attempt_id = ?, depth = 2
            WHERE attempt_id = ?""",
            (opaque('attempt', 1), opaque('attempt', 3)),
        )
        connection.execute(
            """UPDATE decisions SET parent_attempt_id = ?
            WHERE attempt_id = ?""",
            (opaque('attempt', 1), opaque('attempt', 3)),
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    'mutation',
    ['slot_contract', 'generation_slot', 'logical_slot'],
)
def test_validation_requires_canonical_identity_bindings(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    set_ledger_schema_version(ledger, schema_version, 'base')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        if mutation == 'slot_contract':
            source = connection.execute(
                """SELECT classification_digest, route_digest, routing_version,
                          operating_model_version, created_at_ms
                FROM contracts LIMIT 1"""
            ).fetchone()
            connection.execute(
                'INSERT INTO contracts VALUES (?, ?, ?, ?, ?, ?)',
                (opaque('contract', 2), *source),
            )
            connection.execute(
                'UPDATE slots SET contract_id = ?',
                (opaque('contract', 2),),
            )
        else:
            connection.execute(
                'INSERT INTO slots VALUES (?, ?, ?, ?)',
                (
                    opaque('slot', 2),
                    opaque('contract', 1),
                    'engineering',
                    1,
                ),
            )
            if mutation == 'generation_slot':
                connection.execute(
                    'UPDATE generations SET slot_id = ?',
                    (opaque('slot', 2),),
                )
            else:
                connection.execute(
                    'UPDATE logical_invocations SET slot_id = ?',
                    (opaque('slot', 2),),
                )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('identity_kind', ['generation', 'logical'])
def test_denied_decision_identity_binding_cannot_be_reused(
    tmp_path: Path,
    identity_kind: str,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.set_kill_switch(True)
    denied = ledger.admit(
        admission(1, slot=1), route, 'engineering', limits()
    )
    assert denied['launch_authorized'] is False
    ledger.set_kill_switch(False)
    values = {
        'contract': 2,
        'slot': 2,
        'generation': 1 if identity_kind == 'generation' else 2,
        'logical': 1 if identity_kind == 'logical' else 2,
    }

    with pytest.raises(IdentityConflict):
        ledger.admit(
            admission(2, **values), route, 'engineering', limits()
        )
    assert ledger.status()['counts']['active_attempts'] == 0


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize('identity_kind', ['generation', 'logical'])
def test_validation_rejects_conflicting_unmaterialized_decision_bindings(
    tmp_path: Path,
    schema_version: int,
    identity_kind: str,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.set_kill_switch(True)
    ledger.admit(admission(1, slot=1), route, 'engineering', limits())
    ledger.admit(admission(2, slot=2), route, 'engineering', limits())
    ledger.set_kill_switch(False)
    set_ledger_schema_version(ledger, schema_version, 'base')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            f'UPDATE decisions SET {identity_kind}_id = ? WHERE attempt_id = ?',
            (opaque(identity_kind, 1), opaque('attempt', 2)),
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    'mutation',
    ['missing_active_key', 'stale_active_key', 'mismatched_active_key'],
)
def test_validation_requires_exact_active_work_key_mapping(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    if mutation == 'stale_active_key':
        finish(ledger, 1, 1, 'succeeded')
        with sqlite3.connect(ledger.path) as connection:
            connection.execute(
                """INSERT INTO active_work_keys
                SELECT contract_id, slot_id, artifact_revision, attempt_id
                FROM work_history WHERE attempt_id = ?""",
                (opaque('attempt', 1),),
            )
    else:
        with sqlite3.connect(ledger.path) as connection:
            if mutation == 'missing_active_key':
                connection.execute('DELETE FROM active_work_keys')
            else:
                connection.execute(
                    """UPDATE active_work_keys
                    SET artifact_revision = ?""",
                    (f'sha256:{9:064x}',),
                )
    set_ledger_schema_version(ledger, schema_version, 'full')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    'mutation',
    [
        'missing_history',
        'contract_id',
        'slot_id',
        'artifact_revision',
        'lifecycle_transition',
        'replacement_source',
    ],
)
def test_validation_requires_exact_authorized_lifecycle_history(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        if mutation == 'missing_history':
            connection.execute('DELETE FROM active_work_keys')
            connection.execute('DELETE FROM work_history')
        elif mutation == 'contract_id':
            source = connection.execute(
                """SELECT classification_digest, route_digest, routing_version,
                          operating_model_version, created_at_ms
                FROM contracts LIMIT 1"""
            ).fetchone()
            connection.execute(
                'INSERT INTO contracts VALUES (?, ?, ?, ?, ?, ?)',
                (opaque('contract', 2), *source),
            )
            connection.execute(
                'UPDATE work_history SET contract_id = ?',
                (opaque('contract', 2),),
            )
            connection.execute(
                'UPDATE active_work_keys SET contract_id = ?',
                (opaque('contract', 2),),
            )
        elif mutation == 'slot_id':
            connection.execute(
                'INSERT INTO slots VALUES (?, ?, ?, ?)',
                (
                    opaque('slot', 2),
                    opaque('contract', 1),
                    'engineering',
                    1,
                ),
            )
            connection.execute(
                'UPDATE work_history SET slot_id = ?',
                (opaque('slot', 2),),
            )
            connection.execute(
                'UPDATE active_work_keys SET slot_id = ?',
                (opaque('slot', 2),),
            )
        elif mutation == 'artifact_revision':
            changed_revision = f'sha256:{9:064x}'
            connection.execute(
                'UPDATE work_history SET artifact_revision = ?',
                (changed_revision,),
            )
            connection.execute(
                'UPDATE active_work_keys SET artifact_revision = ?',
                (changed_revision,),
            )
        elif mutation == 'lifecycle_transition':
            connection.execute(
                "UPDATE work_history SET lifecycle_transition = 'resume'"
            )
        else:
            connection.execute(
                'UPDATE work_history SET replacement_of_attempt_id = ?',
                (opaque('attempt', 9),),
            )
    set_ledger_schema_version(ledger, schema_version, 'full')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    ('native_status', 'work_status'),
    [
        ('active', 'succeeded'),
        ('notifications_unavailable', 'succeeded'),
        ('completion_notified', 'succeeded'),
        ('read_claimed', 'succeeded'),
        ('found', 'succeeded'),
        ('lost', 'active'),
        ('orphaned', 'active'),
        ('aborted', 'active'),
        ('shutdown', 'active'),
        ('failed', 'active'),
        ('recovered', 'active'),
        ('succeeded', 'active'),
        ('failed', 'succeeded'),
    ],
)
def test_validation_rejects_contradictory_native_and_work_states(
    tmp_path: Path,
    schema_version: int,
    native_status: str,
    work_status: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    ledger.bind_native(
        opaque('attempt', 1),
        opaque('native', 1),
        'native-state-matrix',
        'task_result',
    )
    if work_status == 'succeeded':
        finish(ledger, 1, 1, 'succeeded')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            """UPDATE native_invocations
            SET lifecycle_status = ?, notifications_available = ?""",
            (
                native_status,
                0 if native_status == 'notifications_unavailable' else 1,
            ),
        )
    set_ledger_schema_version(ledger, schema_version, 'full')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('native_status', ['active', 'completion_notified'])
def test_schema_v3_rejects_claim_fingerprint_before_read_claim(
    tmp_path: Path,
    native_status: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'native-preclaim-fingerprint'
    native = opaque('native', 1)
    ledger.bind_native(
        opaque('attempt', 1), native, public_id, 'task_result'
    )
    if native_status == 'completion_notified':
        ledger.native_notification(
            opaque('attempt', 1), native, public_id
        )
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            """UPDATE native_invocations
            SET read_claim_fingerprint = ?""",
            (
                invocation_control._read_claim_fingerprint(
                    opaque('read_claim', 1)
                ),
            ),
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()


def test_schema_v3_requires_fingerprint_for_read_claimed_state(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'native-claimed-fingerprint'
    native = bind_notified_native(ledger, 1, public_id)
    ledger.claim_native_read(
        opaque('attempt', 1),
        native,
        public_id,
        opaque('read_claim', 1),
    )
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            'UPDATE native_invocations SET read_claim_fingerprint = NULL'
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()


def test_schema_v3_allows_null_fingerprint_on_migrated_observation_history(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'native-migrated-observation'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    )
    ledger.observe_native(
        opaque('attempt', 1),
        native,
        public_id,
        read_claim_id,
        'found',
        None,
    )
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            'UPDATE native_invocations SET read_claim_fingerprint = NULL'
        )

    assert ledger.initialize() is False


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize('mutation', ['stale_latest', 'missing_evidence'])
def test_validation_requires_exact_latest_progress_timestamp(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    recorded_at, _ = ledger.record_progress(
        opaque('attempt', 1), fingerprint(1)
    )
    with sqlite3.connect(ledger.path) as connection:
        if mutation == 'stale_latest':
            connection.execute(
                'UPDATE work_history SET last_progress_at_ms = ?',
                (recorded_at + 1,),
            )
        else:
            connection.execute('DELETE FROM progress_evidence')
    set_ledger_schema_version(ledger, schema_version, 'full')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
@pytest.mark.parametrize(
    'mutation',
    [
        'consumed_without_replacement',
        'replacement_without_consumed',
        'reset_consumed_pair',
        'wrong_replacement',
        'missing_eligibility',
    ],
)
def test_validation_requires_exact_replacement_eligibility_history(
    tmp_path: Path,
    schema_version: int,
    mutation: str,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(background_admission(1), route, 'engineering', limits())
    native = opaque('native', 1)
    public_id = 'replacement-integrity-source'
    ledger.bind_native(
        opaque('attempt', 1), native, public_id, 'task_result'
    )
    ledger.native_notification(opaque('attempt', 1), native, public_id)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
    )
    ledger.observe_native(
        opaque('attempt', 1),
        native,
        public_id,
        opaque('read_claim', 1),
        'not_found',
        fingerprint(1),
    )
    if mutation != 'consumed_without_replacement':
        admitted = ledger.admit(
            background_admission(
                2,
                slot=1,
                generation=2,
                logical=2,
                transition='replacement',
                replacement_of=1,
            ),
            route,
            'engineering',
            limits(),
        )
        assert admitted['launch_authorized'] is True

    with sqlite3.connect(ledger.path) as connection:
        if mutation == 'consumed_without_replacement':
            connection.execute(
                'UPDATE replacement_eligibility SET consumed_at_ms = 1'
            )
        elif mutation == 'replacement_without_consumed':
            connection.execute(
                'UPDATE replacement_eligibility SET consumed_at_ms = NULL'
            )
        elif mutation == 'reset_consumed_pair':
            connection.execute(
                """UPDATE replacement_eligibility
                SET replacement_attempt_id = NULL, consumed_at_ms = NULL"""
            )
        elif mutation == 'wrong_replacement':
            connection.execute(
                """UPDATE replacement_eligibility
                SET replacement_attempt_id = ?""",
                (opaque('attempt', 1),),
            )
        else:
            connection.execute('DELETE FROM replacement_eligibility')
    set_ledger_schema_version(ledger, schema_version, 'full')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


@pytest.mark.parametrize('schema_version', [1, 2, 3])
def test_validation_requires_eligibility_for_every_lost_source(
    tmp_path: Path,
    schema_version: int,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    native = opaque('native', 1)
    public_id = 'missing-loss-eligibility'
    ledger.bind_native(
        opaque('attempt', 1), native, public_id, 'task_result'
    )
    ledger.native_notification(opaque('attempt', 1), native, public_id)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
    )
    ledger.observe_native(
        opaque('attempt', 1),
        native,
        public_id,
        opaque('read_claim', 1),
        'not_found',
        fingerprint(1),
    )
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('DELETE FROM replacement_eligibility')
    set_ledger_schema_version(ledger, schema_version, 'full')

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        metadata = dict(connection.execute('SELECT key, value FROM metadata'))
    assert metadata['schema_version'] == str(schema_version)


def test_rejected_lifecycle_attempt_identity_cannot_be_reused(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1), route, 'engineering', limits()
    )
    rejected = ledger.admit(
        lifecycle_admission(
            2,
            slot=1,
            generation=2,
            logical=2,
            transition='resume',
        ),
        route,
        'engineering',
        limits(),
    )
    assert rejected['lifecycle_transition'] == 'duplicate_launch'
    finish(ledger, 1, 1, 'succeeded')

    with pytest.raises(IdentityConflict):
        ledger.admit(
            lifecycle_admission(
                2,
                slot=1,
                generation=3,
                logical=3,
                transition='resume',
            ),
            route,
            'engineering',
            limits(),
        )
    assert ledger.status()['counts']['active_attempts'] == 0


def test_lifecycle_v1_migration_refuses_ambiguous_dispatch_history(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1),
        route,
        'engineering',
        limits(),
    )
    ledger.admit(
        lifecycle_admission(
            2,
            slot=2,
            revision=2,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    refused = ledger.admit(
        lifecycle_admission(
            3,
            slot=3,
            revision=3,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    downgrade_ledger_to_v1(ledger, 'lifecycle')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            """UPDATE lifecycle_decisions SET launch_authorized = 1
            WHERE decision_id = ?""",
            (refused['decision_id'],),
        )

    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert 'lifecycle_dispatch' not in tables


@pytest.mark.parametrize(
    ('source_layout', 'failure_schema'),
    [
        ('base', 'CREATE TABLE lifecycle_decisions'),
        ('lifecycle', 'CREATE TABLE lifecycle_dispatch'),
    ],
)
def test_v1_migration_schema_failure_rolls_back_logical_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_layout: str,
    failure_schema: str,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v1(ledger, source_layout)
    with sqlite3.connect(ledger.path) as connection:
        before = (
            dict(connection.execute('SELECT key, value FROM metadata')),
            Ledger._schema_objects(connection),
        )
    real_execute_schema = Ledger._execute_schema

    def fail_after_schema(
        connection: sqlite3.Connection, schema: str
    ) -> None:
        real_execute_schema(connection, schema)
        database_path = connection.execute(
            'PRAGMA database_list'
        ).fetchone()[2]
        if database_path and failure_schema in schema:
            raise sqlite3.OperationalError('injected migration failure')

    monkeypatch.setattr(
        Ledger, '_execute_schema', staticmethod(fail_after_schema)
    )
    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        after = (
            dict(connection.execute('SELECT key, value FROM metadata')),
            Ledger._schema_objects(connection),
        )
    assert after == before


def test_v1_migration_final_validation_failure_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v1(ledger, 'base')
    with sqlite3.connect(ledger.path) as connection:
        before = (
            dict(connection.execute('SELECT key, value FROM metadata')),
            Ledger._schema_objects(connection),
        )
    real_validate = Ledger._validate

    def reject_v3(
        cls: type[Ledger],
        connection: sqlite3.Connection,
        *,
        layout: str = 'full',
        schema_version: int = 3,
    ) -> None:
        del cls
        if schema_version == 3:
            raise StateCorrupt
        real_validate(
            connection,
            layout=layout,
            schema_version=schema_version,
        )

    monkeypatch.setattr(Ledger, '_validate', classmethod(reject_v3))
    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        after = (
            dict(connection.execute('SELECT key, value FROM metadata')),
            Ledger._schema_objects(connection),
        )
    assert after == before


def test_ambiguous_migration_commit_is_revalidated_under_a_fresh_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v1(ledger, 'base')

    def commit_then_raise(connection: sqlite3.Connection) -> None:
        connection.commit()
        raise CommitOutcomeAmbiguous

    monkeypatch.setattr(Ledger, '_commit', staticmethod(commit_then_raise))
    assert ledger.initialize() is False
    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '3'


def test_explicit_init_migrates_v2_ledger_to_v3_without_rewriting_rows(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    ledger.bind_native(
        opaque('attempt', 1),
        opaque('native', 1),
        'task-agent-v2-source',
        'task_result',
    )
    ledger.native_notification(
        opaque('attempt', 1), opaque('native', 1), 'task-agent-v2-source'
    )
    downgrade_ledger_to_v2(ledger)
    with sqlite3.connect(ledger.path) as connection:
        before = connection.execute(
            'SELECT * FROM native_invocations'
        ).fetchone()

    assert ledger.initialize() is False

    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '3'
        assert connection.execute(
            """SELECT native_invocation_id, attempt_id,
                      notifications_available, lifecycle_status,
                      bound_at_ms, notified_at_ms, read_claimed_at_ms,
                      observed_at_ms
            FROM native_invocations"""
        ).fetchone() == before
        assert connection.execute(
            'SELECT read_claim_fingerprint FROM native_invocations'
        ).fetchone()[0] is None


@pytest.mark.parametrize(
    'source_state',
    [
        'active',
        'notifications_unavailable',
        'completion_notified',
        'found',
        'lost',
        'succeeded',
    ],
)
def test_v2_to_v3_preserves_supported_native_states(
    tmp_path: Path,
    source_state: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = f'task-agent-v2-state-{source_state}'
    native = opaque('native', 1)
    ledger.bind_native(
        opaque('attempt', 1),
        native,
        public_id,
        'task_result',
        source_state != 'notifications_unavailable',
    )
    read_claim_id = opaque('read_claim', 1)
    if source_state in {'completion_notified', 'found', 'lost'}:
        ledger.native_notification(
            opaque('attempt', 1), native, public_id
        )
    if source_state in {'found', 'lost'}:
        ledger.claim_native_read(
            opaque('attempt', 1), native, public_id, read_claim_id
        )
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            read_claim_id,
            'found' if source_state == 'found' else 'not_found',
            None if source_state == 'found' else fingerprint(1),
        )
    elif source_state == 'succeeded':
        finish(ledger, 1, 1, 'succeeded')
    downgrade_ledger_to_v2(ledger)

    assert ledger.initialize() is False

    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            """SELECT lifecycle_status, read_claim_fingerprint
            FROM native_invocations"""
        ).fetchone() == (source_state, None)


def test_ordinary_commands_refuse_ledger_v2_without_migrating(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    downgrade_ledger_to_v2(ledger)

    with pytest.raises(StateUnsupported):
        ledger.status()

    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '2'
        assert 'read_claim_fingerprint' not in {
            row[1]
            for row in connection.execute('PRAGMA table_info(native_invocations)')
        }


@pytest.mark.parametrize('source_schema_version', [1, 2])
def test_ownerless_read_claim_blocks_legacy_migration(
    tmp_path: Path,
    source_schema_version: int,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    ledger.bind_native(
        opaque('attempt', 1),
        opaque('native', 1),
        'task-agent-ownerless-read',
        'task_result',
    )
    ledger.native_notification(
        opaque('attempt', 1),
        opaque('native', 1),
        'task-agent-ownerless-read',
    )
    set_ledger_schema_version(ledger, source_schema_version, 'full')
    with sqlite3.connect(ledger.path) as connection:
        connection.execute(
            """UPDATE native_invocations
            SET lifecycle_status = 'read_claimed',
                read_claimed_at_ms = 123"""
        )

    with pytest.raises(StateUnsupported):
        ledger.initialize()

    with sqlite3.connect(ledger.path) as connection:
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == str(source_schema_version)
        assert 'read_claim_fingerprint' not in {
            row[1]
            for row in connection.execute('PRAGMA table_info(native_invocations)')
        }


def test_released_v1_client_fresh_open_reports_v3_as_unsupported(
    tmp_path: Path,
) -> None:
    commit = 'c99b3d45b4f15bda9ed8632ca40c78779875e089'
    script_result = subprocess.run(
        ['git', 'show', f'{commit}:scripts/agent_invocation_control.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    config_result = subprocess.run(
        ['git', 'show', f'{commit}:config/agent-invocation-control.json'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    analysis_result = subprocess.run(
        ['git', 'show', f'{commit}:analysis/agentic_invocation_control.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if (
        script_result.returncode != 0
        or config_result.returncode != 0
        or analysis_result.returncode != 0
    ):
        pytest.skip('immutable released v1 artifact is unavailable in shallow checkout')
    assert hashlib.sha256(script_result.stdout.encode()).hexdigest() == (
        '24c397303ed592c7bc0835a75bbe421da5dda59fe20f6e92d0139dcca06162ff'
    )
    assert hashlib.sha256(config_result.stdout.encode()).hexdigest() == (
        '416d4f4293ea4d4c7fd6be71c4ec3710607eddb799492f7daeea73fe0777ec11'
    )

    repository = init_repository(tmp_path)
    released_root = tmp_path / 'released-v1'
    (released_root / 'scripts').mkdir(parents=True)
    (released_root / 'config').mkdir()
    (released_root / 'scripts' / 'agent_invocation_control.py').write_text(
        script_result.stdout,
        encoding='utf-8',
    )
    (released_root / 'config' / 'agent-invocation-control.json').write_text(
        config_result.stdout,
        encoding='utf-8',
    )
    shutil.copytree(ROOT / 'analysis', released_root / 'analysis')
    (released_root / 'analysis' / 'agentic_invocation_control.py').write_text(
        analysis_result.stdout,
        encoding='utf-8',
    )
    result = subprocess.run(
        [
            sys.executable,
            str(released_root / 'scripts' / 'agent_invocation_control.py'),
        ],
        cwd=repository,
        input=json.dumps({'schema_version': 1, 'command': 'status'}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 4
    assert json.loads(result.stdout)['policy_reason'] == 'state_unsupported'


def test_current_cli_refuses_json_schema_v1(tmp_path: Path) -> None:
    repository = tmp_path / 'repository'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)

    result = run_cli(repository, {'schema_version': 1, 'command': 'status'})

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'invalid',
        'reason_code': 'invalid_request',
    }


def test_new_identity_returns_one_valid_read_claim_token(tmp_path: Path) -> None:
    repository = tmp_path / 'repository'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)

    result = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'new_identity',
            'kind': 'read_claim',
        },
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'new_identity',
        'reason_code': 'identity_created',
        'kind': 'read_claim',
        'identity': payload['identity'],
    }
    assert is_valid_identity(payload['identity'], 'read_claim')


def test_failed_745_ledger_upgrade_rolls_back_auxiliary_schema(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute('DROP TABLE native_binding_provenance')
        connection.execute('DROP TABLE lifecycle_dispatch')
        connection.execute('ALTER TABLE work_history ADD COLUMN unexpected TEXT')
        connection.execute(
            "UPDATE metadata SET value = '1' WHERE key = 'schema_version'"
        )
    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert 'lifecycle_dispatch' not in tables
    assert 'native_binding_provenance' not in tables


def test_new_ledger_validation_failure_rolls_back_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = Ledger(tmp_path / 'ledger.sqlite3')

    def reject_schema(
        _connection: sqlite3.Connection,
        *,
        layout: str = 'full',
        schema_version: int = 2,
    ) -> None:
        del layout, schema_version
        raise StateCorrupt

    monkeypatch.setattr(Ledger, '_validate', staticmethod(reject_schema))
    with pytest.raises(StateCorrupt):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert tables == set()


@pytest.mark.parametrize(
    ('failure', 'expected_error'),
    [
        ('corrupt', StateCorrupt),
        ('unsupported', StateUnsupported),
        ('sqlite', StateCorrupt),
    ],
)
def test_existing_ledger_prevalidation_failure_closes_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_error: type[Exception],
) -> None:
    ledger = new_ledger(tmp_path)
    real_connect = sqlite3.connect
    if failure == 'corrupt':
        with real_connect(ledger.path) as connection:
            connection.execute(
                'ALTER TABLE metadata ADD COLUMN unexpected TEXT'
            )
    elif failure == 'unsupported':
        with real_connect(ledger.path) as connection:
            connection.execute(
                "UPDATE metadata SET value = '999' WHERE key = 'schema_version'"
            )

    class TrackedConnection:
        def __init__(
            self, connection: sqlite3.Connection, fail_with_sqlite: bool
        ) -> None:
            object.__setattr__(self, '_connection', connection)
            object.__setattr__(self, '_fail_with_sqlite', fail_with_sqlite)
            object.__setattr__(self, 'closed', False)

        def __getattr__(self, name: str) -> object:
            return getattr(self._connection, name)

        def __setattr__(self, name: str, value: object) -> None:
            if name in {'_connection', '_fail_with_sqlite', 'closed'}:
                object.__setattr__(self, name, value)
                return
            setattr(self._connection, name, value)

        def execute(
            self, statement: str, parameters: tuple[object, ...] = ()
        ) -> sqlite3.Cursor:
            if self._fail_with_sqlite and statement == 'PRAGMA busy_timeout=30000':
                raise sqlite3.OperationalError('injected prevalidation failure')
            return self._connection.execute(statement, parameters)

        def close(self) -> None:
            object.__setattr__(self, 'closed', True)
            self._connection.close()

    tracked: list[TrackedConnection] = []

    def tracked_connect(*args: object, **kwargs: object) -> TrackedConnection:
        connection = real_connect(*args, **kwargs)
        wrapper = TrackedConnection(connection, failure == 'sqlite')
        tracked.append(wrapper)
        return wrapper

    monkeypatch.setattr(sqlite3, 'connect', tracked_connect)
    with pytest.raises(expected_error):
        ledger.initialize()
    assert len(tracked) == 1
    assert tracked[0].closed is True


def test_lifecycle_key_deduplicates_active_work_and_allows_new_digest(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    first = ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    assert first['lifecycle_transition'] == 'initial_launch'

    duplicate = ledger.admit(
        lifecycle_admission(
            2, slot=1, generation=2, logical=2, transition='resume'
        ),
        route,
        'engineering',
        limits(),
    )
    assert duplicate['lifecycle_transition'] == 'duplicate_launch'
    assert duplicate['launch_authorized'] is False

    review = ledger.admit(
        lifecycle_admission(
            3,
            slot=1,
            generation=3,
            logical=3,
            revision=2,
            transition='review_after_new_digest',
        ),
        route,
        'engineering',
        limits(),
    )
    assert review['lifecycle_transition'] == 'review_after_new_digest'
    assert review['launch_authorized'] is True
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM active_work_keys"
        ).fetchone()[0] == 2
        assert connection.execute(
            """SELECT effective_transition, launch_authorized
            FROM lifecycle_decisions ORDER BY decided_at_ms, rowid"""
        ).fetchall() == [
            ('initial_launch', 1),
            ('duplicate_launch', 0),
            ('review_after_new_digest', 1),
        ]


@pytest.mark.parametrize('commit_became_durable', [False, True])
def test_lifecycle_rejection_persistence_failure_remains_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    commit_became_durable: bool,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )

    def fail_commit(connection: sqlite3.Connection) -> None:
        if commit_became_durable:
            connection.commit()
            raise CommitOutcomeAmbiguous
        connection.rollback()
        raise StateCorrupt

    monkeypatch.setattr(invocation_control, '_ledger_path', lambda: ledger.path)
    monkeypatch.setattr(Ledger, '_commit', staticmethod(fail_commit))
    monkeypatch.setattr(
        sys,
        'stdin',
        io.StringIO(
            json.dumps(
                lifecycle_admission(
                    2,
                    slot=1,
                    generation=2,
                    logical=2,
                    transition='resume',
                )
            )
        ),
    )
    with pytest.raises(SystemExit) as exit_info:
        invocation_control.main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 4
    assert captured.err == ''
    assert json.loads(captured.out) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'admit',
        'reason_code': 'ledger_unavailable',
        'policy_reason': 'state_corrupt',
        'would_reject': True,
        'launch_authorized': False,
        'lifecycle_transition': 'duplicate_launch',
    }
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT 1 FROM attempts WHERE attempt_id = ?',
            (opaque('attempt', 2),),
        ).fetchone() is None
        assert connection.execute(
            'SELECT COUNT(*) FROM lifecycle_decisions WHERE attempt_id = ?',
            (opaque('attempt', 2),),
        ).fetchone()[0] == int(commit_became_durable)


def test_replayed_lifecycle_rejection_remains_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    request = lifecycle_admission(
        2,
        slot=1,
        generation=2,
        logical=2,
        transition='resume',
    )
    rejected = ledger.admit(
        request, accepted_route(), 'engineering', limits()
    )
    assert rejected['launch_authorized'] is False

    monkeypatch.setattr(invocation_control, '_ledger_path', lambda: ledger.path)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(request)))
    with pytest.raises(SystemExit) as exit_info:
        invocation_control.main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.err == ''
    assert json.loads(captured.out) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'admit',
        'reason_code': 'invalid_identity',
        'would_reject': True,
        'launch_authorized': False,
    }


@pytest.mark.parametrize('commit_became_durable', [False, True])
def test_kill_switch_rejection_commit_failure_remains_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    commit_became_durable: bool,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.set_kill_switch(True)

    def fail_commit(connection: sqlite3.Connection) -> None:
        if commit_became_durable:
            connection.commit()
            raise CommitOutcomeAmbiguous
        connection.rollback()
        raise StateCorrupt

    monkeypatch.setattr(invocation_control, '_ledger_path', lambda: ledger.path)
    monkeypatch.setattr(Ledger, '_commit', staticmethod(fail_commit))
    monkeypatch.setattr(
        sys, 'stdin', io.StringIO(json.dumps(lifecycle_admission(1)))
    )
    with pytest.raises(SystemExit) as exit_info:
        invocation_control.main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 4
    assert captured.err == ''
    assert json.loads(captured.out) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'admit',
        'reason_code': 'ledger_unavailable',
        'policy_reason': 'state_corrupt',
        'would_reject': True,
        'launch_authorized': False,
        'lifecycle_transition': 'initial_launch',
    }
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM decisions'
        ).fetchone()[0] == int(commit_became_durable)


def test_kill_switch_rejection_insert_failure_remains_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.set_kill_switch(True)
    real_connect = Ledger._connect

    def connect_with_denied_decision_insert(
        self: Ledger,
    ) -> sqlite3.Connection:
        connection = real_connect(self)

        def authorize(
            action: int,
            argument: str | None,
            _database: str | None,
            _trigger: str | None,
            _source: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_INSERT and argument == 'decisions':
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(invocation_control, '_ledger_path', lambda: ledger.path)
    monkeypatch.setattr(Ledger, '_connect', connect_with_denied_decision_insert)
    monkeypatch.setattr(
        sys, 'stdin', io.StringIO(json.dumps(lifecycle_admission(1)))
    )
    with pytest.raises(SystemExit) as exit_info:
        invocation_control.main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 4
    assert captured.err == ''
    assert json.loads(captured.out) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'admit',
        'reason_code': 'ledger_unavailable',
        'policy_reason': 'state_corrupt',
        'would_reject': True,
        'launch_authorized': False,
        'lifecycle_transition': 'initial_launch',
    }
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM decisions'
        ).fetchone()[0] == 0


def test_first_not_found_refuses_reread_and_allows_one_replacement(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        background_admission(1, slot=1), route, 'engineering', limits()
    )
    native = opaque('native', 1)
    public_id = 'agent-public-1'
    assert ledger.bind_native(
        opaque('attempt', 1), native, public_id, 'task_result'
    ) == 'active'
    with pytest.raises(NativeBoundary, match='completion_notification_required'):
        ledger.claim_native_read(
            opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
        )
    assert ledger.native_notification(
        opaque('attempt', 1), native, public_id
    ) is False
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
    )
    state, orphaned = ledger.observe_native(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1),
        'not_found', fingerprint(10)
    )
    assert (state, orphaned) == ('lost', [])
    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.claim_native_read(
            opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
        )

    replacement = ledger.admit(
        background_admission(
            2,
            slot=1,
            generation=2,
            logical=2,
            transition='replacement',
            replacement_of=1,
        ),
        route,
        'engineering',
        limits(),
    )
    assert replacement['lifecycle_transition'] == 'replacement'
    second_for_source = ledger.admit(
        background_admission(
            3,
            slot=1,
            generation=3,
            logical=3,
            transition='replacement',
            replacement_of=1,
        ),
        route,
        'engineering',
        limits(),
    )
    assert second_for_source['lifecycle_transition'] == 'duplicate_launch'

    replacement_native = opaque('native', 2)
    replacement_public_id = 'agent-public-2'
    ledger.bind_native(
        opaque('attempt', 2), replacement_native,
        replacement_public_id, 'task_result',
    )
    ledger.native_notification(
        opaque('attempt', 2), replacement_native, replacement_public_id
    )
    ledger.claim_native_read(
        opaque('attempt', 2), replacement_native, replacement_public_id,
        opaque('read_claim', 2),
    )
    ledger.observe_native(
        opaque('attempt', 2), replacement_native, replacement_public_id,
        opaque('read_claim', 2), 'not_found', fingerprint(11),
    )
    chained = ledger.admit(
        lifecycle_admission(
            4,
            slot=1,
            generation=4,
            logical=4,
            transition='replacement',
            replacement_of=2,
        ),
        route,
        'engineering',
        limits(),
    )
    assert chained['lifecycle_transition'] == 'illegal_transition'
    assert chained['launch_authorized'] is False
    reused_source = ledger.admit(
        lifecycle_admission(
            5, slot=1, generation=5, logical=5,
            transition='replacement', replacement_of=1,
        ),
        route,
        'engineering',
        limits(),
    )
    assert reused_source['lifecycle_transition'] == 'illegal_transition'
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM replacement_eligibility'
        ).fetchone()[0] == 1


def test_native_read_claim_is_idempotent_and_raw_token_is_not_persisted(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-claim-owner'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)

    assert ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    ) is False
    assert ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    ) is True
    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.claim_native_read(
            opaque('attempt', 1),
            native,
            public_id,
            opaque('read_claim', 2),
        )

    claim_fingerprint = invocation_control._read_claim_fingerprint(
        read_claim_id
    )
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT read_claim_fingerprint FROM native_invocations'
        ).fetchone()[0] == claim_fingerprint
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    persisted = b''.join(
        path.read_bytes()
        for path in ledger.path.parent.iterdir()
        if path.is_file()
    )
    assert read_claim_id.encode() not in persisted
    assert claim_fingerprint.encode() in persisted


def test_native_read_claim_cannot_be_reused_across_bindings(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(background_admission(1), route, 'engineering', limits())
    ledger.admit(background_admission(2), route, 'engineering', limits())
    first_public_id = 'task-agent-first-claim-binding'
    second_public_id = 'task-agent-second-claim-binding'
    first_native = bind_notified_native(ledger, 1, first_public_id)
    second_native = bind_notified_native(ledger, 2, second_public_id)
    read_claim_id = opaque('read_claim', 1)

    ledger.claim_native_read(
        opaque('attempt', 1),
        first_native,
        first_public_id,
        read_claim_id,
    )

    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.claim_native_read(
            opaque('attempt', 2),
            second_native,
            second_public_id,
            read_claim_id,
        )


def test_concurrent_same_token_same_row_claim_is_one_logical_operation(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-same-token-race'
    native = bind_notified_native(ledger, 1, public_id)
    claim = (
        opaque('attempt', 1),
        native,
        public_id,
        opaque('read_claim', 1),
    )

    outcomes = race_native_claims(ledger, [claim, claim])

    assert sorted(outcome for _, outcome in outcomes) == [False, True]


def test_concurrent_different_tokens_same_row_allow_one_owner(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-different-token-race'
    native = bind_notified_native(ledger, 1, public_id)
    claims = [
        (
            opaque('attempt', 1),
            native,
            public_id,
            opaque('read_claim', number),
        )
        for number in (1, 2)
    ]

    outcomes = race_native_claims(ledger, claims)

    assert sum(outcome is False for _, outcome in outcomes) == 1
    refusals = [
        outcome for _, outcome in outcomes if isinstance(outcome, BaseException)
    ]
    assert len(refusals) == 1
    assert isinstance(refusals[0], NativeBoundary)
    assert str(refusals[0]) == 'native_read_refused'


def test_concurrent_same_token_cross_row_allow_one_owner(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(background_admission(1), route, 'engineering', limits())
    ledger.admit(background_admission(2), route, 'engineering', limits())
    read_claim_id = opaque('read_claim', 1)
    first_public_id = 'task-agent-cross-row-race-one'
    second_public_id = 'task-agent-cross-row-race-two'
    claims = [
        (
            opaque('attempt', 1),
            bind_notified_native(ledger, 1, first_public_id),
            first_public_id,
            read_claim_id,
        ),
        (
            opaque('attempt', 2),
            bind_notified_native(ledger, 2, second_public_id),
            second_public_id,
            read_claim_id,
        ),
    ]

    outcomes = race_native_claims(ledger, claims)

    assert sum(outcome is False for _, outcome in outcomes) == 1
    refusals = [
        outcome for _, outcome in outcomes if isinstance(outcome, BaseException)
    ]
    assert len(refusals) == 1
    assert isinstance(refusals[0], NativeBoundary)
    assert str(refusals[0]) == 'native_read_refused'


@pytest.mark.parametrize('commit_became_durable', [False, True])
def test_native_read_claim_reconciles_ambiguous_commit_with_same_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    commit_became_durable: bool,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-ambiguous-claim'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)

    def ambiguous_commit(connection: sqlite3.Connection) -> None:
        if commit_became_durable:
            connection.commit()
        else:
            connection.rollback()
        raise CommitOutcomeAmbiguous

    monkeypatch.setattr(
        Ledger, '_commit', staticmethod(ambiguous_commit)
    )

    assert ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    ) is commit_became_durable
    assert ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    ) is True


def test_native_read_claim_ambiguity_honors_binding_invalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-invalidated-claim'
    native = bind_notified_native(ledger, 1, public_id)

    def commit_invalidate_then_raise(connection: sqlite3.Connection) -> None:
        connection.commit()
        with sqlite3.connect(ledger.path) as invalidator:
            invalidator.execute(
                """UPDATE native_binding_provenance
                SET invalidation_reason = 'context_replacement',
                    invalidated_at_ms = 123
                WHERE native_alias = ?""",
                (native,),
            )
        raise CommitOutcomeAmbiguous

    monkeypatch.setattr(
        Ledger, '_commit', staticmethod(commit_invalidate_then_raise)
    )

    with pytest.raises(NativeBoundary, match='native_binding_invalidated'):
        ledger.claim_native_read(
            opaque('attempt', 1),
            native,
            public_id,
            opaque('read_claim', 1),
        )


def test_native_observation_requires_same_claim_and_remains_one_shot(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-observation-owner'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    )

    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            opaque('read_claim', 2),
            'found',
            None,
        )
    assert ledger.observe_native(
        opaque('attempt', 1),
        native,
        public_id,
        read_claim_id,
        'found',
        None,
    ) == ('found', [])
    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            read_claim_id,
            'found',
            None,
        )


def test_ambiguous_native_observation_fails_closed_without_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-ambiguous-observation'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    )

    def commit_then_raise(connection: sqlite3.Connection) -> None:
        connection.commit()
        raise CommitOutcomeAmbiguous

    monkeypatch.setattr(
        Ledger, '_commit', staticmethod(commit_then_raise)
    )
    with pytest.raises(StateCorrupt):
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            read_claim_id,
            'found',
            None,
        )
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT lifecycle_status FROM native_invocations'
        ).fetchone()[0] == 'found'
    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            read_claim_id,
            'found',
            None,
        )


@pytest.mark.parametrize(
    ('transition', 'expected_status'),
    [
        ('found', 'found'),
        ('lost', 'lost'),
        ('succeeded', 'succeeded'),
        ('failed', 'failed'),
        ('recovered', 'recovered'),
        ('abort', 'aborted'),
        ('shutdown', 'shutdown'),
        ('failure', 'failed'),
    ],
)
def test_claim_fingerprint_survives_observation_and_terminal_paths(
    tmp_path: Path,
    transition: str,
    expected_status: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = f'task-agent-claim-terminal-{transition}'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)
    claim_fingerprint = invocation_control._read_claim_fingerprint(
        read_claim_id
    )
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    )

    if transition == 'found':
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            read_claim_id,
            'found',
            None,
        )
    elif transition == 'lost':
        ledger.observe_native(
            opaque('attempt', 1),
            native,
            public_id,
            read_claim_id,
            'not_found',
            fingerprint(1),
        )
    elif transition in {'succeeded', 'failed', 'recovered'}:
        ledger.finish(
            opaque('attempt', 1), transition, fingerprint(1)
        )
    else:
        ledger.terminate_tree(
            opaque('attempt', 1), transition, fingerprint(1)
        )

    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            """SELECT lifecycle_status, read_claim_fingerprint
            FROM native_invocations"""
        ).fetchone() == (expected_status, claim_fingerprint)


def test_claim_fingerprint_survives_invalidation(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    public_id = 'task-agent-claim-invalidation'
    native = bind_notified_native(ledger, 1, public_id)
    read_claim_id = opaque('read_claim', 1)
    claim_fingerprint = invocation_control._read_claim_fingerprint(
        read_claim_id
    )
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, read_claim_id
    )

    ledger.invalidate_native(
        opaque('attempt', 1),
        native,
        public_id,
        'context_replacement',
    )

    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT read_claim_fingerprint FROM native_invocations'
        ).fetchone()[0] == claim_fingerprint
    with pytest.raises(NativeBoundary, match='native_binding_invalidated'):
        ledger.claim_native_read(
            opaque('attempt', 1), native, public_id, read_claim_id
        )


def test_claim_fingerprint_survives_orphan_terminalization(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        background_admission(1), route, 'engineering', limits()
    )
    ledger.admit(
        background_admission(
            2, parent=opaque('attempt', 1), revision=2
        ),
        route,
        'engineering',
        limits(),
    )
    public_id = 'task-agent-claimed-orphan'
    native = bind_notified_native(ledger, 2, public_id)
    read_claim_id = opaque('read_claim', 2)
    claim_fingerprint = invocation_control._read_claim_fingerprint(
        read_claim_id
    )
    ledger.claim_native_read(
        opaque('attempt', 2), native, public_id, read_claim_id
    )

    status, descendants, _ = ledger.terminate_tree(
        opaque('attempt', 1), 'failure', fingerprint(1)
    )

    assert status == 'failed'
    assert descendants == [opaque('attempt', 2)]
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            """SELECT lifecycle_status, read_claim_fingerprint
            FROM native_invocations"""
        ).fetchone() == ('orphaned', claim_fingerprint)


def test_completed_replacement_cannot_resume_into_a_new_replacement_chain(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        background_admission(1, slot=1),
        route,
        'engineering',
        limits(),
    )
    native = opaque('native', 1)
    public_id = 'replacement-lineage-source'
    ledger.bind_native(
        opaque('attempt', 1), native, public_id, 'task_result'
    )
    ledger.native_notification(opaque('attempt', 1), native, public_id)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
    )
    ledger.observe_native(
        opaque('attempt', 1),
        native,
        public_id,
        opaque('read_claim', 1),
        'not_found',
        fingerprint(12),
    )
    replacement = ledger.admit(
        background_admission(
            2,
            slot=1,
            generation=2,
            logical=2,
            transition='replacement',
            replacement_of=1,
        ),
        route,
        'engineering',
        limits(),
    )
    assert replacement['launch_authorized'] is True
    finish(ledger, 2, 13, 'succeeded')

    resumed = ledger.admit(
        lifecycle_admission(
            3,
            slot=1,
            generation=3,
            logical=3,
            transition='resume',
        ),
        route,
        'engineering',
        limits(),
    )
    assert resumed['lifecycle_transition'] == 'illegal_transition'
    assert resumed['launch_authorized'] is False
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT 1 FROM attempts WHERE attempt_id = ?',
            (opaque('attempt', 3),),
        ).fetchone() is None


def test_clock_regression_cannot_hide_the_latest_lost_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    clock = [2_000]
    monkeypatch.setattr(invocation_control, '_now_ms', lambda: clock[0])
    ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    finish(ledger, 1, 1, 'succeeded')

    clock[0] = 1_000
    resumed = ledger.admit(
        background_admission(
            2,
            slot=1,
            generation=2,
            logical=2,
            transition='resume',
        ),
        route,
        'engineering',
        limits(),
    )
    assert resumed['launch_authorized'] is True
    native = opaque('native', 1)
    public_id = 'clock-regression-loss'
    ledger.bind_native(
        opaque('attempt', 2), native, public_id, 'task_result'
    )
    ledger.native_notification(opaque('attempt', 2), native, public_id)
    ledger.claim_native_read(
        opaque('attempt', 2), native, public_id, opaque('read_claim', 2)
    )
    ledger.observe_native(
        opaque('attempt', 2),
        native,
        public_id,
        opaque('read_claim', 2),
        'not_found',
        fingerprint(2),
    )

    clock[0] = 1_200
    refused = ledger.admit(
        lifecycle_admission(
            3,
            slot=1,
            generation=3,
            logical=3,
            transition='resume',
        ),
        route,
        'engineering',
        limits(),
    )
    assert refused['lifecycle_transition'] == 'illegal_transition'
    assert refused['launch_authorized'] is False
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM replacement_eligibility'
        ).fetchone()[0] == 1
        assert connection.execute(
            'SELECT 1 FROM attempts WHERE attempt_id = ?',
            (opaque('attempt', 3),),
        ).fetchone() is None


def test_parent_shutdown_is_leaf_first_idempotent_and_orphans_descendants(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    ledger.admit(
        lifecycle_admission(
            2,
            slot=2,
            revision=2,
            parent=opaque('attempt', 1),
        ),
        route,
        'engineering',
        limits(),
    )
    ledger.admit(
        lifecycle_admission(
            3,
            slot=3,
            revision=3,
            parent=opaque('attempt', 2),
        ),
        route,
        'engineering',
        limits(),
    )
    status, orphaned, idempotent = ledger.terminate_tree(
        opaque('attempt', 1), 'shutdown', fingerprint(20)
    )
    assert status == 'shutdown'
    assert orphaned == [opaque('attempt', 3), opaque('attempt', 2)]
    assert idempotent is False
    assert ledger.terminate_tree(
        opaque('attempt', 1), 'shutdown', fingerprint(20)
    ) == ('shutdown', [], True)
    with sqlite3.connect(ledger.path) as connection:
        assert dict(
            connection.execute(
                'SELECT attempt_id, lifecycle_status FROM work_history'
            )
        ) == {
            opaque('attempt', 1): 'shutdown',
            opaque('attempt', 2): 'orphaned',
            opaque('attempt', 3): 'orphaned',
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM attempts WHERE lifecycle_status = 'active'"
        ).fetchone()[0] == 0
        assert connection.execute(
            'SELECT COUNT(*) FROM active_work_keys'
        ).fetchone()[0] == 0


@pytest.mark.parametrize(
    ('tree_reason', 'collapsed_finish_status'),
    [('shutdown', 'recovered'), ('abort', 'failed')],
)
def test_collapsed_base_status_does_not_hide_exact_lifecycle_conflict(
    tmp_path: Path,
    tree_reason: str,
    collapsed_finish_status: str,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    terminal = fingerprint(21)
    ledger.terminate_tree(opaque('attempt', 1), tree_reason, terminal)

    with pytest.raises(FinishConflict):
        ledger.finish(
            opaque('attempt', 1),
            collapsed_finish_status,
            terminal,
        )


@pytest.mark.parametrize('reason, expected', [('abort', 'aborted'), ('failure', 'failed')])
def test_parent_abort_and_failure_cleanup(
    tmp_path: Path, reason: str, expected: str
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(lifecycle_admission(1), route, 'engineering', limits())
    ledger.admit(
        lifecycle_admission(
            2, slot=2, revision=2, parent=opaque('attempt', 1)
        ),
        route,
        'engineering',
        limits(),
    )
    status, orphaned, _ = ledger.terminate_tree(
        opaque('attempt', 1), reason, fingerprint(21)
    )
    assert status == expected
    assert orphaned == [opaque('attempt', 2)]


def test_illegal_transitions_fail_closed_and_resume_is_explicit(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(lifecycle_admission(1), route, 'engineering', limits())
    finish(ledger, 1, 1, 'succeeded')

    repeated_initial = ledger.admit(
        lifecycle_admission(2, slot=1, generation=2, logical=2),
        route,
        'engineering',
        limits(),
    )
    assert repeated_initial['lifecycle_transition'] == 'illegal_transition'
    assert repeated_initial['launch_authorized'] is False

    resumed = ledger.admit(
        lifecycle_admission(
            3, slot=1, generation=3, logical=3, transition='resume'
        ),
        route,
        'engineering',
        limits(),
    )
    assert resumed['lifecycle_transition'] == 'resume'
    finish(ledger, 3, 3, 'succeeded')
    wrong_review = ledger.admit(
        lifecycle_admission(
            4,
            slot=1,
            generation=4,
            logical=4,
            transition='review_after_new_digest',
        ),
        route,
        'engineering',
        limits(),
    )
    assert wrong_review['lifecycle_transition'] == 'illegal_transition'


def test_progress_only_advances_for_new_substantive_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    native = opaque('native', 1)
    public_id = 'agent-public-progress'
    ledger.bind_native(
        opaque('attempt', 1), native, public_id, 'task_result'
    )
    ledger.native_notification(opaque('attempt', 1), native, public_id)
    ledger.claim_native_read(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1)
    )
    ledger.observe_native(
        opaque('attempt', 1), native, public_id, opaque('read_claim', 1),
        'found', None
    )
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT last_progress_at_ms FROM work_history'
        ).fetchone()[0] is None
    progress_times = iter((2_000, 1_000))
    monkeypatch.setattr(invocation_control, '_now_ms', lambda: next(progress_times))
    first_at, first_idempotent = ledger.record_progress(
        opaque('attempt', 1), fingerprint(30)
    )
    second_at, second_idempotent = ledger.record_progress(
        opaque('attempt', 1), fingerprint(31)
    )
    repeated_at, repeated_idempotent = ledger.record_progress(
        opaque('attempt', 1), fingerprint(30)
    )
    assert first_idempotent is False
    assert second_idempotent is False
    assert repeated_idempotent is True
    assert repeated_at == second_at
    assert second_at == first_at
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM progress_evidence'
        ).fetchone()[0] == 2
        assert connection.execute(
            'SELECT last_progress_at_ms FROM work_history'
        ).fetchone()[0] == second_at


def test_sync_default_explicit_sync_and_background_provenance(tmp_path: Path) -> None:
    repository = init_repository(tmp_path)
    default_sync = run_cli(repository, lifecycle_admission(1, slot=1))
    assert default_sync.returncode == 0
    assert json.loads(default_sync.stdout)['execution_provenance'] == 'sync_inline'
    explicit_sync = run_cli(
        repository,
        lifecycle_admission(
            2,
            slot=2,
            revision=2,
            dispatch_mode='sync',
            execution_provenance='sync_inline',
        ),
    )
    assert explicit_sync.returncode == 0
    assert json.loads(explicit_sync.stdout)['dispatch_mode'] == 'sync'

    invalid_background = lifecycle_admission(
        3,
        slot=3,
        revision=3,
        dispatch_mode='background',
        execution_provenance='sync_inline',
    )
    rejected = run_cli(repository, invalid_background)
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'admit',
        'reason_code': 'execution_provenance_invalid',
        'policy_reason': None,
        'would_reject': True,
        'launch_authorized': False,
    }

    valid_background = run_cli(
        repository, background_admission(4, slot=4, revision=4)
    )
    assert valid_background.returncode == 0
    background_payload = json.loads(valid_background.stdout)
    assert background_payload['dispatch_mode'] == 'background'
    assert background_payload['execution_provenance'] == (
        'background_independent_immediate_no_poll'
    )

    native = opaque('native', 1)
    sync_bind = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'bind_native',
            'attempt_id': opaque('attempt', 1),
            'native_alias': native,
            'public_agent_id': 'agent-sync-must-return-inline',
            'binding_source': 'task_result',
            'notifications_available': True,
        },
    )
    assert sync_bind.returncode == 2
    assert json.loads(sync_bind.stdout)['reason_code'] == (
        'execution_provenance_invalid'
    )
    sync_read = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'native_read',
            'attempt_id': opaque('attempt', 1),
            'native_alias': native,
            'public_agent_id': 'agent-sync-must-return-inline',
            'read_claim_id': opaque('read_claim', 1),
        },
    )
    assert sync_read.returncode == 2
    assert json.loads(sync_read.stdout)['reason_code'] == (
        'native_binding_mismatch'
    )


def test_cli_native_read_reuses_one_claim_without_echoing_it(
    tmp_path: Path,
) -> None:
    repository = init_repository(tmp_path)
    assert run_cli(repository, background_admission(1)).returncode == 0
    alias = opaque('native', 1)
    public_id = 'task-agent-cli-read-claim'
    assert run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'bind_native',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
            'binding_source': 'task_result',
            'notifications_available': True,
        },
    ).returncode == 0
    assert run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'native_notification',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
        },
    ).returncode == 0
    read_claim_id = opaque('read_claim', 1)
    claim_request = {
        'schema_version': 2,
        'command': 'native_read',
        'attempt_id': opaque('attempt', 1),
        'native_alias': alias,
        'public_agent_id': public_id,
        'read_claim_id': read_claim_id,
    }

    malformed = dict(claim_request)
    malformed_claim = 'sha256:' + ('1' * 64)
    malformed['read_claim_id'] = malformed_claim
    malformed_result = run_cli(repository, malformed)
    assert malformed_result.returncode == 2
    assert malformed_claim not in malformed_result.stdout

    first = run_cli(repository, claim_request)
    repeated = run_cli(repository, claim_request)

    assert first.returncode == 0
    assert repeated.returncode == 0
    assert json.loads(first.stdout) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'native_read',
        'reason_code': 'native_read_authorized',
        'read_authorized': True,
        'idempotent': False,
    }
    assert json.loads(repeated.stdout)['idempotent'] is True
    assert read_claim_id not in first.stdout
    assert read_claim_id not in repeated.stdout


def test_lifecycle_dispatch_distinguishes_policy_denial(tmp_path: Path) -> None:
    ledger = new_ledger(tmp_path)
    ledger.set_kill_switch(True)
    denied = ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    assert denied['policy_reason'] == 'kill_switch_active'
    assert denied['launch_authorized'] is False
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT admission_reason FROM lifecycle_dispatch'
        ).fetchone()[0] == 'policy_denied'


@pytest.mark.parametrize(
    'value',
    [
        '',
        ' public-agent',
        'public-agent ',
        'public agent',
        'public\tagent',
        'public\nagent',
        'public\u00a0agent',
        'public\u2003agent',
        'call_123456',
        'dummy',
        'nonexistent',
        'placeholder',
        'UNKNOWN',
        'x',
        opaque('native', 1),
        opaque('attempt', 1),
        opaque('read_claim', 1),
        'x' * 513,
        '界' * 171,
    ],
)
def test_public_agent_id_validation_rejects_non_task_result_ids(value: str) -> None:
    assert is_valid_public_agent_id(value) is False


def test_public_agent_id_validation_accepts_opaque_non_uuid_format() -> None:
    assert is_valid_public_agent_id('task-agent-01HZY6Q91M')
    assert is_valid_public_agent_id(f'abc_{"1" * 32}')
    assert is_valid_public_agent_id('界' * 170)


def test_notifications_unavailable_stops_native_reads_and_polling(
    tmp_path: Path,
) -> None:
    repository = init_repository(tmp_path)
    assert run_cli(repository, background_admission(1)).returncode == 0
    alias = opaque('native', 1)
    public_id = 'task-agent-no-notifications'
    bound = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'bind_native',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
            'binding_source': 'task_result',
            'notifications_available': False,
        },
    )
    assert bound.returncode == 0
    assert json.loads(bound.stdout) == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'bind_native',
        'reason_code': 'native_bound',
        'native_status': 'notifications_unavailable',
        'wait_strategy': 'notifications_unavailable_no_polling',
    }
    for command in ('native_notification', 'native_read'):
        refused = run_cli(
            repository,
            {
                'schema_version': 2,
                'command': command,
                'attempt_id': opaque('attempt', 1),
                'native_alias': alias,
                'public_agent_id': public_id,
                **(
                    {'read_claim_id': opaque('read_claim', 1)}
                    if command == 'native_read'
                    else {}
                ),
            },
        )
        assert refused.returncode == 5
        assert json.loads(refused.stdout)['reason_code'] == (
            'native_notifications_unavailable'
        )
    observed = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'native_observation',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
            'read_claim_id': opaque('read_claim', 1),
            'observation': 'found',
            'terminal_fingerprint': None,
        },
    )
    assert observed.returncode == 5
    assert json.loads(observed.stdout)['reason_code'] == (
        'native_notifications_unavailable'
    )


def test_lifecycle_v1_native_binding_without_provenance_blocks_migration(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        background_admission(1), accepted_route(), 'engineering', limits()
    )
    alias = opaque('native', 1)
    public_id = 'task-agent-before-provenance'
    ledger.bind_native(
        opaque('attempt', 1), alias, public_id, 'task_result'
    )
    downgrade_ledger_to_v1(ledger, 'lifecycle')
    with pytest.raises(StateUnsupported):
        ledger.initialize()
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM native_invocations'
        ).fetchone()[0] == 1
        assert dict(connection.execute(
            'SELECT key, value FROM metadata'
        ))['schema_version'] == '1'
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
        }
    assert 'native_binding_provenance' not in tables
    assert 'lifecycle_dispatch' not in tables


def test_public_agent_binding_mismatch_notification_one_read_and_invalidation(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(background_admission(1), route, 'engineering', limits())
    ledger.admit(
        background_admission(2, slot=2, revision=2),
        route,
        'engineering',
        limits(),
    )
    alias = opaque('native', 1)
    public_id = 'task-agent-01HZY6Q91M'
    ledger.bind_native(
        opaque('attempt', 1), alias, public_id, 'task_result'
    )
    with pytest.raises(NativeBoundary, match='native_binding_mismatch'):
        ledger.bind_native(
            opaque('attempt', 2),
            opaque('native', 2),
            public_id,
            'task_result',
        )

    with pytest.raises(NativeBoundary, match='native_binding_mismatch'):
        ledger.native_notification(
            opaque('attempt', 1), alias, 'task-agent-guessed'
        )
    with pytest.raises(NativeBoundary, match='native_binding_mismatch'):
        ledger.native_notification(opaque('attempt', 2), alias, public_id)

    assert ledger.native_notification(
        opaque('attempt', 1), alias, public_id
    ) is False
    assert ledger.native_notification(
        opaque('attempt', 1), alias, public_id
    ) is True
    ledger.claim_native_read(
        opaque('attempt', 1), alias, public_id, opaque('read_claim', 1)
    )
    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.claim_native_read(
            opaque('attempt', 1), alias, public_id, opaque('read_claim', 2)
        )
    assert ledger.observe_native(
        opaque('attempt', 1), alias, public_id, opaque('read_claim', 1),
        'found', None
    ) == ('found', [])

    assert ledger.invalidate_native(
        opaque('attempt', 1), alias, public_id, 'context_replacement'
    ) is False
    assert ledger.invalidate_native(
        opaque('attempt', 1), alias, public_id, 'context_replacement'
    ) is True
    with pytest.raises(NativeBoundary, match='native_binding_mismatch'):
        ledger.native_notification(
            opaque('attempt', 1), alias, 'task-agent-wrong-after-invalidation'
        )
    with pytest.raises(NativeBoundary, match='native_binding_invalidated'):
        ledger.invalidate_native(
            opaque('attempt', 1), alias, public_id, 'resume'
        )
    for operation in (
        lambda: ledger.native_notification(
            opaque('attempt', 1), alias, public_id
        ),
        lambda: ledger.claim_native_read(
            opaque('attempt', 1), alias, public_id, opaque('read_claim', 1)
        ),
        lambda: ledger.observe_native(
            opaque('attempt', 1), alias, public_id, opaque('read_claim', 1),
            'found', None
        ),
    ):
        with pytest.raises(NativeBoundary, match='native_binding_invalidated'):
            operation()

    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT lifecycle_status FROM work_history WHERE attempt_id = ?',
            (opaque('attempt', 1),),
        ).fetchone()[0] == 'active'
        assert connection.execute(
            'SELECT COUNT(*) FROM replacement_eligibility'
        ).fetchone()[0] == 0
        assert connection.execute(
            """SELECT public_agent_id_fingerprint, invalidation_reason
            FROM native_binding_provenance WHERE native_alias = ?""",
            (alias,),
        ).fetchone() == (
            _expected_native_fingerprint(public_id),
            'context_replacement',
        )


def _expected_native_fingerprint(public_agent_id: str) -> str:
    import hashlib

    digest = hashlib.sha256(
        b'praxys-native-public-agent-id-v1\x00'
        + public_agent_id.encode('utf-8')
    ).hexdigest()
    return f'sha256:{digest}'


@pytest.mark.parametrize('reason', ['shutdown', 'resume', 'context_replacement'])
def test_cli_native_invalidation_has_stable_reason(
    tmp_path: Path, reason: str
) -> None:
    repository = init_repository(tmp_path)
    assert run_cli(repository, background_admission(1)).returncode == 0
    alias = opaque('native', 1)
    public_id = f'task-agent-invalidate-{reason}'
    bound = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'bind_native',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
            'binding_source': 'task_result',
            'notifications_available': True,
        },
    )
    assert bound.returncode == 0
    invalidated = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'invalidate_native',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
            'invalidation_reason': reason,
        },
    )
    assert invalidated.returncode == 0
    assert json.loads(invalidated.stdout)['reason_code'] == 'native_invalidated'
    stale = run_cli(
        repository,
        {
            'schema_version': 2,
            'command': 'native_notification',
            'attempt_id': opaque('attempt', 1),
            'native_alias': alias,
            'public_agent_id': public_id,
        },
    )
    assert stale.returncode == 2
    assert json.loads(stale.stdout)['reason_code'] == (
        'native_binding_invalidated'
    )


def test_exact_work_contract_and_autonomy_composition_are_unchanged() -> None:
    route = accepted_route()
    assert route.classification_digest == CLASSIFICATION_DIGEST
    assert route.route_digest == ROUTE_DIGEST
    assert route.routing_version == 'praxys-task-routing-v1'
    assert route.operating_model_version == 'praxys-agentic-operating-model-v1'
    assert route.primary_loop == 'meta-eval'
    assert route.nested_loops == ['delivery']
    assert route.lead_role == 'meta-eval'
    assert route.contributor_roles == ['architecture']
    assert route.executor_roles == ['engineering']
    assert route.verifier_roles == ['quality']
    assert route.required_artifacts == [
        'evaluation-report',
        'implementation-impact-map',
        'implementation-change',
        'verification-evidence',
        'policy-change-proposal',
        'architecture-decision-record',
    ]
    assert route.decision_review_required is True
    assert route.decision_review_agent == '.github/agents/decision-review-router.agent.md'

    policy = json.loads(
        (ROOT / 'config' / 'agent-loop-policies.json').read_text(encoding='utf-8')
    )
    autonomy = policy['decision_autonomy']
    assert autonomy['status'] == 'specification-only'
    assert autonomy['default_judgment_route'] == 'human-review-required'
    assert autonomy['agent_reviewed_classes'] == []
    assert autonomy['promoted_judgment_classes'] == []
    assert autonomy['independence']['executor_may_verify_own_high_risk_work'] is False


def test_policy_parity_and_cooperative_manifest_boundaries() -> None:
    policy = json.loads(
        (ROOT / 'config' / 'agent-invocation-control.json').read_text(encoding='utf-8')
    )
    assert policy == {
        'schema_version': 2,
        'policy_version': 'agent-invocation-control-v1',
        'status': 'instrument-shadow-only',
        'default_mode': 'instrument',
        'approved_modes': ['instrument', 'shadow'],
        'enforcement_approved': False,
        'ledger_schema_version': 3,
        'dispatch_profiles': {
            'default': 'sync_inline',
            'sync': 'sync_inline',
            'background': 'background_independent_immediate_no_poll',
        },
        'native_binding': {
            'binding_source': 'task_result',
            'public_id_storage': 'domain-separated-sha256-fingerprint',
            'invalidation_reasons': [
                'shutdown',
                'resume',
                'context_replacement',
            ],
        },
        'limits': {
            'maximum_ancestry_depth': 6,
            'maximum_active_per_contract': 8,
            'maximum_logical_per_contract': 32,
            'maximum_attempts_per_logical': 3,
            'maximum_retries_per_failure_fingerprint': 1,
            'no_progress_identical_terminals': 2,
        },
    }
    parity = json.loads(
        (ROOT / 'config' / 'copilot-execution-parity.json').read_text(encoding='utf-8')
    )
    assert 'cooperative-invocation-mediation' in {
        limitation['id'] for limitation in parity['limitations']
    }
    for relative in (
        '.github/agents/praxys-orchestrator.agent.md',
        '.github/agents/praxys-change-loop.agent.md',
    ):
        manifest = (ROOT / relative).read_text(encoding='utf-8')
        assert 'scripts/agent_invocation_control.py' in manifest
        assert 'native' in manifest.lower()
        assert 'instrument' in manifest.lower()
        assert 'shadow' in manifest.lower()
        assert 'completion' in manifest.lower()
        assert 'notification' in manifest.lower()
        assert 'poll' in manifest.lower()
        assert 'replacement' in manifest.lower()
        assert 'sync_inline' in manifest
        assert 'background_independent_immediate_no_poll' in manifest
        assert 'direct child' in manifest.lower()
        assert 'task_result' in manifest
        assert 'invalidate' in manifest.lower()
