"""Agent invocation admission, lifecycle, and ledger contracts."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

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
)
from analysis.agentic_task_routing import TaskClassification, TaskRoute, route_task
from scripts.agent_invocation_control import (
    FinishConflict,
    IdentityConflict,
    Ledger,
    NativeBoundary,
    RecoveryRequired,
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
        'schema_version': 1,
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
    return request


def new_ledger(tmp_path: Path) -> Ledger:
    ledger = Ledger(tmp_path / 'control.sqlite3')
    assert ledger.initialize() is True
    return ledger


def finish(
    ledger: Ledger,
    attempt: int,
    terminal: int,
    status: str = 'failed',
) -> tuple[str, bool]:
    return ledger.finish(opaque('attempt', attempt), status, fingerprint(terminal))


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
    initialized = run_cli(repository, {'schema_version': 1, 'command': 'init'})
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
        MACHINE_REASON_CODES[:21]
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
        {'schema_version': 1, 'command': 'kill_switch', 'active': True},
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
            'schema_version': 1,
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
    initialized = run_cli(repository, {'schema_version': 1, 'command': 'init'})
    assert initialized.returncode == 0
    with sqlite3.connect(ledger_path) as connection:
        connection.execute("DELETE FROM metadata WHERE key = 'policy_version'")
    assert_nonblocking_state(
        run_cli(repository, admission(5, mode='shadow')), 'state_corrupt'
    )

    shutil.rmtree(ledger_path.parent)
    initialized = run_cli(repository, {'schema_version': 1, 'command': 'init'})
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
        repository, {'schema_version': 1, 'command': 'status'}
    )
    assert damaged_status.returncode == 4
    assert json.loads(damaged_status.stdout)['policy_reason'] == 'state_corrupt'

    shutil.rmtree(ledger_path.parent)
    initialized = run_cli(repository, {'schema_version': 1, 'command': 'init'})
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
        'schema_version': 1,
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

    status = run_cli(repository, {'schema_version': 1, 'command': 'status'})
    assert status.returncode == 0
    durable = json.loads(status.stdout)
    assert durable['counts']['decisions'] == 6
    assert durable['counts']['active_attempts'] == 6
    assert durable['decision_counts'] == {
        'admit': 1,
        'duplicate_active': 5,
    }


def test_ledger_is_wal_foreign_keyed_and_persists_no_raw_content(tmp_path: Path) -> None:
    repository = init_repository(tmp_path)
    valid = admission(1, mode='instrument')
    recorded = run_cli(repository, valid)
    assert recorded.returncode == 0
    assert json.loads(recorded.stdout)['reason_code'] == 'instrument_recorded'

    sentinels = {
        'prompt': 'RAW_PROMPT_SENTINEL',
        'task': 'RAW_TASK_SENTINEL',
        'issue': 'RAW_ISSUE_SENTINEL',
        'user': 'RAW_USER_SENTINEL',
        'code': 'RAW_CODE_SENTINEL',
        'credential': 'RAW_CREDENTIAL_SENTINEL',
        'artifact': 'RAW_ARTIFACT_SENTINEL',
    }
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


def test_explicit_init_compatibly_extends_original_v1_ledger(tmp_path: Path) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(admission(1), accepted_route(), 'engineering', limits())
    with sqlite3.connect(ledger.path) as connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        for table in (
            'active_work_keys',
            'replacement_eligibility',
            'native_invocations',
            'progress_evidence',
            'work_history',
            'lifecycle_decisions',
        ):
            connection.execute(f'DROP TABLE {table}')
    assert ledger.initialize() is False
    assert ledger.status()['counts']['active_attempts'] == 1
    assert finish(ledger, 1, 1, 'succeeded') == ('succeeded', False)
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
    }.issubset(tables)


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


def test_first_not_found_refuses_reread_and_allows_one_replacement(
    tmp_path: Path,
) -> None:
    ledger = new_ledger(tmp_path)
    route = accepted_route()
    ledger.admit(
        lifecycle_admission(1, slot=1), route, 'engineering', limits()
    )
    native = opaque('native', 1)
    assert ledger.bind_native(opaque('attempt', 1), native, True) == 'active'
    with pytest.raises(NativeBoundary, match='completion_notification_required'):
        ledger.claim_native_read(native)
    assert ledger.native_notification(native) is False
    ledger.claim_native_read(native)
    state, orphaned = ledger.observe_native(native, 'not_found', fingerprint(10))
    assert (state, orphaned) == ('lost', [])
    with pytest.raises(NativeBoundary, match='native_read_refused'):
        ledger.claim_native_read(native)

    replacement = ledger.admit(
        lifecycle_admission(
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
        lifecycle_admission(
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
    ledger.bind_native(opaque('attempt', 2), replacement_native, True)
    ledger.native_notification(replacement_native)
    ledger.claim_native_read(replacement_native)
    ledger.observe_native(replacement_native, 'not_found', fingerprint(11))
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
) -> None:
    ledger = new_ledger(tmp_path)
    ledger.admit(
        lifecycle_admission(1), accepted_route(), 'engineering', limits()
    )
    native = opaque('native', 1)
    ledger.bind_native(opaque('attempt', 1), native, True)
    ledger.native_notification(native)
    ledger.claim_native_read(native)
    ledger.observe_native(native, 'found', None)
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT last_progress_at_ms FROM work_history'
        ).fetchone()[0] is None
    first_at, first_idempotent = ledger.record_progress(
        opaque('attempt', 1), fingerprint(30)
    )
    repeated_at, repeated_idempotent = ledger.record_progress(
        opaque('attempt', 1), fingerprint(30)
    )
    assert first_idempotent is False
    assert repeated_idempotent is True
    assert repeated_at == first_at
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute(
            'SELECT COUNT(*) FROM progress_evidence'
        ).fetchone()[0] == 1
        assert connection.execute(
            'SELECT last_progress_at_ms FROM work_history'
        ).fetchone()[0] == first_at


def test_notifications_unavailable_exposes_limitation_without_read(
    tmp_path: Path,
) -> None:
    repository = init_repository(tmp_path)
    started = run_cli(repository, lifecycle_admission(1, slot=1))
    assert started.returncode == 0
    duplicate = run_cli(
        repository,
        lifecycle_admission(
            2, slot=1, generation=2, logical=2, transition='resume'
        ),
    )
    assert duplicate.returncode == 2
    duplicate_payload = json.loads(duplicate.stdout)
    assert duplicate_payload['reason_code'] == 'lifecycle_transition_rejected'
    assert duplicate_payload['lifecycle_transition'] == 'duplicate_launch'
    assert duplicate_payload['launch_authorized'] is False
    native = opaque('native', 1)
    bound = run_cli(
        repository,
        {
            'schema_version': 1,
            'command': 'bind_native',
            'attempt_id': opaque('attempt', 1),
            'native_invocation_id': native,
            'notifications_available': False,
        },
    )
    assert bound.returncode == 0
    assert json.loads(bound.stdout)['wait_strategy'] == (
        'notifications_unavailable_no_polling'
    )
    refused = run_cli(
        repository,
        {
            'schema_version': 1,
            'command': 'native_read',
            'native_invocation_id': native,
        },
    )
    assert refused.returncode == 5
    assert json.loads(refused.stdout) == {
        'schema_version': 1,
        'policy_version': 'agent-invocation-control-v1',
        'command': 'native_read',
        'reason_code': 'native_notifications_unavailable',
        'read_authorized': False,
    }


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
        'schema_version': 1,
        'policy_version': 'agent-invocation-control-v1',
        'status': 'instrument-shadow-only',
        'default_mode': 'instrument',
        'approved_modes': ['instrument', 'shadow'],
        'enforcement_approved': False,
        'ledger_schema_version': 1,
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
