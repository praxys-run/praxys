"""Offline incident admission/state-machine tests: no provider credentials or writes."""
import copy
import importlib.util
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def recovery(monkeypatch):
    spec = importlib.util.spec_from_file_location('restore837', ROOT / 'scripts/restore_feedback_publication_837.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.started = module.now()
    module.phase_deadline = module.started + 360
    module.hard_deadline = module.started + 465
    monkeypatch.setattr(module, 'arm', lambda _: None)
    monkeypatch.setattr(module, 'emit', lambda *a, **k: None)
    return module


@pytest.fixture
def harness(recovery, monkeypatch):
    calls = []
    for name in ('controller_evidence', 'producer_evidence', 'github_no_overlap', 'worker'):
        monkeypatch.setattr(recovery, name, lambda name=name: calls.append(name))
    monkeypatch.setattr(recovery, 'admission', lambda positive: calls.append(('admit', positive)) or {})
    monkeypatch.setattr(recovery, 'operation_evidence', lambda: {})
    flags = {recovery.POSITIVE: True, recovery.KILL: False}
    monkeypatch.setattr(recovery, 'settings', lambda: flags)
    monkeypatch.setattr(recovery, 'runtime', lambda positive: calls.append(('runtime', positive)))
    monkeypatch.setattr(recovery, 'outputs', lambda state: calls.append(('output', state)))

    def write(value, before):
        recovery.mutation_started = True
        calls.append(('write', value))
        return {}, 'receipt'

    monkeypatch.setattr(recovery, 'set_positive', write)
    return recovery, calls


def test_valid_restore_is_one_true_write(harness):
    r, calls = harness
    assert r.restore() == 'verified'
    assert [c for c in calls if isinstance(c, tuple) and c[0] == 'write'] == [('write', True)]
    assert calls.count(('admit', False)) == 2


@pytest.mark.parametrize('gate', ['controller_evidence', 'producer_evidence', 'admission'])
def test_preconditions_never_write(harness, monkeypatch, gate):
    r, calls = harness
    monkeypatch.setattr(r, gate, lambda *a: (_ for _ in ()).throw(r.Failure()))
    assert r.restore() == 'prewrite_rejected'
    assert not any(isinstance(c, tuple) and c[0] == 'write' for c in calls)


@pytest.mark.parametrize('failure', ['timeout', 'nonzero', 'missing_receipt', 'signal'])
def test_uncertain_true_never_compensates(harness, monkeypatch, failure):
    r, calls = harness

    def uncertain(*_):
        r.mutation_started = r.conflicting_write = True
        calls.append(('write', True))
        raise r.Failure({'timeout': 124, 'signal': 143}.get(failure, 1))

    monkeypatch.setattr(r, 'set_positive', uncertain)
    monkeypatch.setattr(r, 'compensate', lambda *_: pytest.fail('Uncertain write must stop'))
    assert r.restore() == 'unknown'
    assert calls.count(('write', True)) == 1


@pytest.mark.parametrize('outcome', ['verified_disabled', 'control_plane_only'])
def test_only_acknowledged_true_may_compensate(harness, monkeypatch, outcome):
    r, calls = harness
    monkeypatch.setattr(r, 'runtime', lambda *_: (_ for _ in ()).throw(r.Failure()))
    monkeypatch.setattr(r, 'command', lambda *_a, **_k: (_ for _ in ()).throw(r.Failure(124)))
    monkeypatch.setattr(r, 'compensate', lambda ack: calls.append(('compensate', ack)) or outcome)
    assert r.restore() == outcome
    assert ('compensate', True) in calls


def test_compensation_rejects_uncertainty(recovery):
    recovery.conflicting_write = True
    with pytest.raises(recovery.Failure):
        recovery.compensate(True)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}', b'not json'])
def test_strict_json(recovery, raw):
    with pytest.raises((recovery.Failure, ValueError)):
        recovery.strict_json(raw)


@pytest.mark.parametrize('payload', [
    {'total_count': 2, 'jobs': [{'id': 1}]},
    {'total_count': 2, 'jobs': [{'id': 1}, {'id': 1}]},
    {'total_count': True, 'jobs': [{'id': 1}]},
    {'total_count': 0, 'jobs': None},
])
def test_incomplete_collections_rejected(recovery, payload):
    with pytest.raises(recovery.Failure):
        recovery.collection(payload, 'jobs')


def audit_events(r):
    return [{'eventDataId': status, 'correlationId': '12345678-1234-1234-1234-123456789012',
             'resourceId': r.SETTINGS_ID, 'operationName': {'value': 'Microsoft.Web/sites/config/write'},
             'status': {'value': status}, 'claims': {'appid': 'expected-client'}, 'caller': 'same-caller',
             'eventTimestamp': f'2026-09-30T03:00:0{index}Z'}
            for index, status in enumerate(('Started', 'Succeeded'))]


def test_receipt_requires_unique_exact_audit_operation(recovery, monkeypatch):
    monkeypatch.setenv('AZURE_CLIENT_ID', 'expected-client')
    events = audit_events(recovery)
    assert recovery.receipt({}, {'new': events}, '2026-09-30T03:00:00Z', '2026-09-30T03:00:02Z') == 'new'


@pytest.mark.parametrize('mutation', ['missing', 'overlap', 'caller', 'resource', 'operation', 'status', 'late'])
def test_receipt_ambiguity_rejected(recovery, monkeypatch, mutation):
    monkeypatch.setenv('AZURE_CLIENT_ID', 'expected-client')
    events = audit_events(recovery)
    after = {'new': events}
    if mutation == 'missing':
        after = {}
    elif mutation == 'overlap':
        after['other'] = copy.deepcopy(events)
    elif mutation == 'caller':
        events[1]['claims']['appid'] = 'other'
    elif mutation == 'resource':
        events[1]['resourceId'] = recovery.WORKER_ID
    elif mutation == 'operation':
        events[1]['operationName']['value'] = 'Microsoft.Web/sites/restart/action'
    elif mutation == 'status':
        events[1]['status']['value'] = 'Accepted'
    elif mutation == 'late':
        events[1]['eventTimestamp'] = '2026-09-30T03:00:03Z'
    with pytest.raises(recovery.Failure):
        recovery.receipt({}, after, '2026-09-30T03:00:00Z', '2026-09-30T03:00:02Z')


@pytest.mark.parametrize('value', ['TRUE', '', None, '1'])
def test_flags_fail_closed(recovery, monkeypatch, value):
    monkeypatch.setattr(recovery, 'az_json', lambda _: [
        {'name': recovery.POSITIVE, 'value': value}, {'name': recovery.KILL, 'value': 'false'}])
    with pytest.raises(recovery.Failure):
        recovery.settings()


def test_duplicate_flags_rejected(recovery, monkeypatch):
    monkeypatch.setattr(recovery, 'az_json', lambda _: [
        {'name': recovery.POSITIVE, 'value': 'true'}, {'name': recovery.POSITIVE, 'value': 'false'},
        {'name': recovery.KILL, 'value': 'false'}])
    with pytest.raises(recovery.Failure):
        recovery.settings()


def test_command_deadline_before_write(recovery):
    recovery.phase_deadline = recovery.now() + 0.01
    with pytest.raises(recovery.Failure):
        recovery.command('restore_write', [sys.executable, '-c', 'pass'], 1, write=True)
    assert not recovery.mutation_started


def test_command_timeout_latches_uncertainty(recovery):
    start = time.monotonic()
    with pytest.raises(recovery.Failure):
        recovery.command('restore_write', [sys.executable, '-c', 'import time; time.sleep(10)'], 0.1, write=True)
    assert time.monotonic() - start < 3
    assert recovery.conflicting_write


def test_descendant_held_pipe_is_bounded(recovery):
    start = time.monotonic()
    with pytest.raises(recovery.Failure):
        recovery.command('read', [sys.executable, '-c',
            'import subprocess; subprocess.Popen(["sleep", "10"])'], 0.1)
    assert time.monotonic() - start < 3


def test_oversized_capture_is_rejected(recovery):
    with pytest.raises(recovery.Failure):
        recovery.command('read', [sys.executable, '-c', 'print("x" * 300000)'], 2)


def test_provider_canary_is_not_printed(recovery, capfd):
    with pytest.raises(recovery.Failure):
        recovery.command('read', [sys.executable, '-c',
            'import sys; print("SECRET_CANARY"); print("SECRET_CANARY", file=sys.stderr); sys.exit(1)'], 2)
    assert 'SECRET_CANARY' not in ''.join(capfd.readouterr())


def test_workflow_has_no_automatic_trigger_or_authority_broadening():
    import yaml
    workflow = yaml.safe_load((ROOT / '.github/workflows/restore-feedback-publication-837.yml').read_text())
    assert set(workflow.get('on', workflow.get(True))) == {'workflow_dispatch'}
    assert workflow['concurrency'] == {'group': 'praxys-backend-deploy', 'cancel-in-progress': False}
    assert workflow['permissions'] == {'contents': 'read', 'actions': 'read', 'id-token': 'write'}
    step = workflow['jobs']['restore']['steps'][-1]
    assert step['timeout-minutes'] == 8
    assert step['run'].index('/proc/uptime') < step['run'].index('python3')
    assert 'timeout --signal=KILL 465s' in step['run']


def test_source_drift_never_compensates(harness, monkeypatch):
    r, _ = harness
    monkeypatch.setattr(r, 'runtime', lambda *_: (_ for _ in ()).throw(r.Drift()))
    monkeypatch.setattr(r, 'compensate', lambda *_: pytest.fail('Source drift must stop'))
    assert r.restore() == 'unknown'


def controller(r, monkeypatch):
    sha = 'a' * 40
    for key, value in {'GITHUB_REPOSITORY': r.REPOSITORY, 'GITHUB_REF': 'refs/heads/main',
                       'GITHUB_REF_PROTECTED': 'true', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
                       'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_SHA': sha,
                       'PRAXYS_REVIEWED_CONTROLLER_SHA': sha, 'GITHUB_RUN_ID': '123'}.items():
        monkeypatch.setenv(key, value)
    run = {'id': 123, 'run_attempt': 1, 'head_sha': sha, 'head_branch': 'main',
           'path': r.WORKFLOW, 'event': 'workflow_dispatch',
           'repository': {'full_name': r.REPOSITORY}, 'head_repository': {'full_name': r.REPOSITORY}}
    evidence = {'branches/main': {'protected': True, 'commit': {'sha': sha}},
                'actions/runs/123': run,
                'actions/workflows/restore-feedback-publication-837.yml/runs?per_page=100':
                {'total_count': 1, 'workflow_runs': [run]}}
    monkeypatch.setattr(r, 'gh', lambda path: evidence[path])
    return evidence


def test_first_invocation_controller(recovery, monkeypatch):
    controller(recovery, monkeypatch)
    recovery.controller_evidence()


@pytest.mark.parametrize('mutation', ['prior_revision', 'attempt', 'wrong_sha', 'unprotected', 'truncated'])
def test_controller_gate_rejects_reuse_and_drift(recovery, monkeypatch, mutation):
    evidence = controller(recovery, monkeypatch)
    history = evidence['actions/workflows/restore-feedback-publication-837.yml/runs?per_page=100']
    if mutation == 'prior_revision':
        old = {**history['workflow_runs'][0], 'id': 122, 'head_sha': 'b' * 40}
        history['workflow_runs'].append(old)
        history['total_count'] = 2
    elif mutation == 'attempt':
        monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    elif mutation == 'wrong_sha':
        monkeypatch.setenv('GITHUB_SHA', 'b' * 40)
    elif mutation == 'unprotected':
        evidence['branches/main']['protected'] = False
    else:
        history['total_count'] = 101
    with pytest.raises(recovery.Failure):
        recovery.controller_evidence()


def labs(r, monkeypatch):
    run = {'id': r.LABS_RUN, 'run_attempt': 1, 'head_sha': r.PRODUCER_SHA, 'head_branch': 'main',
           'path': '.github/workflows/deploy-labs-worker.yml', 'event': 'push',
           'repository': {'full_name': r.REPOSITORY}, 'head_repository': {'full_name': r.REPOSITORY}}
    job = {'id': r.LABS_JOB, 'name': 'deploy', 'run_attempt': 1, 'status': 'in_progress',
           'steps': [{'number': number, 'name': ('Require matching backend migration and authority'
                                                if number == 3 else str(number)),
                      'status': 'completed' if number < 3 else 'in_progress' if number == 3 else 'pending',
                      'conclusion': 'success' if number < 3 else None} for number in range(1, 11)]}
    monkeypatch.setattr(r, 'gh', lambda _: {'total_count': 1, 'jobs': [job]})
    return run, job


def test_only_exact_labs_guard_is_allowed(recovery, monkeypatch):
    run, _ = labs(recovery, monkeypatch)
    recovery.labs_guard(run)


@pytest.mark.parametrize('mutation', ['attempt', 'run', 'job', 'login', 'reconciliation', 'missing_step'])
def test_labs_exception_cannot_admit_provider_phase(recovery, monkeypatch, mutation):
    run, job = labs(recovery, monkeypatch)
    if mutation == 'attempt':
        run['run_attempt'] = 2
    elif mutation == 'run':
        run['id'] += 1
    elif mutation == 'job':
        job['id'] += 1
    elif mutation == 'missing_step':
        job['steps'].pop()
    else:
        job['steps'][4 if mutation == 'login' else 6]['status'] = 'in_progress'
    with pytest.raises(recovery.Failure):
        recovery.labs_guard(run)


def test_terminal_labs_guard_failure_is_nonconflicting(recovery, monkeypatch):
    run, job = labs(recovery, monkeypatch)
    job.update(status='completed', conclusion='failure')
    job['steps'][2].update(status='completed', conclusion='failure')
    for step in job['steps'][3:]:
        step.update(status='completed', conclusion='skipped')
    recovery.labs_guard(run)


@pytest.mark.parametrize('mutation', ['next_page', 'unresolved', 'duplicate', 'producer_missing'])
def test_provider_completeness_failures(recovery, monkeypatch, mutation):
    events = audit_events(recovery)
    for event in events:
        event['correlationId'] = recovery.PRODUCER_CORRELATION
    payload = {'value': events}
    if mutation == 'next_page':
        payload['nextLink'] = 'https://example.invalid/next'
    elif mutation == 'unresolved':
        events.pop()
    elif mutation == 'duplicate':
        events.append(copy.deepcopy(events[-1]))
    else:
        payload['value'] = []
    monkeypatch.setattr(recovery, 'az_json', lambda _: payload)
    with pytest.raises(recovery.Failure):
        recovery.operation_evidence()


@pytest.mark.parametrize('mutation', ['valid', 'changed_byte', 'duplicate_intent', 'wrong_line', 'truncated'])
def test_pinned_log_authentication_and_unique_intent(recovery, monkeypatch, mutation):
    from hashlib import sha256
    lines = [b'x'] * 593 + [recovery.LOG_LINE, b'x']
    raw = b'\n'.join(lines)
    raw += b'x' * (58978 - len(raw))
    if mutation == 'duplicate_intent':
        lines[10] = recovery.LOG_LINE
        raw = b'\n'.join(lines)
        raw += b'x' * (58978 - len(raw))
    elif mutation == 'wrong_line':
        lines[593], lines[1] = lines[1], lines[593]
        raw = b'\n'.join(lines)
        raw += b'x' * (58978 - len(raw))
    monkeypatch.setattr(recovery, 'LOG_SHA256', sha256(raw).hexdigest())
    if mutation == 'changed_byte':
        raw = b'Y' + raw[1:]
    elif mutation == 'truncated':
        raw = raw[:-1]
    if mutation == 'valid':
        recovery.authenticate_log(raw)
    else:
        with pytest.raises(recovery.Failure):
            recovery.authenticate_log(raw)


def test_real_command_records_launch_to_exit_interval(recovery):
    recovery.command('restore_write', [sys.executable, '-c', 'pass'], 2, write=True)
    begin, end = recovery.write_interval
    assert begin <= end
