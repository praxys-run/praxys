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
    monkeypatch.setattr(recovery, 'persist_evidence', lambda *_: None)
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
    step = next(s for s in workflow['jobs']['restore']['steps'] if s.get('id') == 'restoration')
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


def test_completed_competing_write_blocks_compensation(recovery, monkeypatch):
    recovery.receipts.append('12345678-1234-1234-1234-123456789012')
    operations = {recovery.PRODUCER_CORRELATION: [], recovery.receipts[0]: [], 'other': []}
    monkeypatch.setattr(recovery, 'github_no_overlap', lambda: None)
    monkeypatch.setattr(recovery, 'operation_evidence', lambda: operations)
    monkeypatch.setattr(recovery, 'set_positive', lambda *_: pytest.fail('Competing writer blocks false'))
    with pytest.raises(recovery.Failure):
        recovery.compensate(True)


def test_unexpected_historical_writer_blocks_initial_admission(recovery, monkeypatch):
    monkeypatch.setattr(recovery, 'github_no_overlap', lambda: None)
    monkeypatch.setattr(recovery, 'operation_evidence', lambda: {recovery.PRODUCER_CORRELATION: [], 'other': []})
    monkeypatch.setattr(recovery, 'worker', lambda: pytest.fail('Must reject before state sampling'))
    with pytest.raises(recovery.Failure):
        recovery.admission(False)


@pytest.mark.parametrize('result', ['unavailable', 'mismatch', 'source_drift', 'verified'])
def test_compensation_outcome_distinguishes_unavailable_from_contradiction(recovery, monkeypatch, result):
    r = recovery
    r.receipts.append('12345678-1234-1234-1234-123456789012')
    before = {r.PRODUCER_CORRELATION: [], r.receipts[0]: []}
    monkeypatch.setattr(r, 'github_no_overlap', lambda: None)
    monkeypatch.setattr(r, 'operation_evidence', lambda: before)
    workers = []
    monkeypatch.setattr(r, 'worker', lambda: workers.append(True) or {'image': r.SERVING_SHA})
    flags = iter([{r.POSITIVE: True, r.KILL: False}, {r.POSITIVE: False, r.KILL: False}])
    monkeypatch.setattr(r, 'settings', lambda: next(flags))
    monkeypatch.setattr(r, 'command', lambda *_a, **_k: b'{}')
    monkeypatch.setattr(r, 'strict_json', lambda _: {'source_sha': r.SERVING_SHA, 'version': r.SERVING_VERSION})
    writes = []
    monkeypatch.setattr(r, 'set_positive', lambda positive, _: writes.append(positive) or (before, 'false'))

    def runtime(_):
        if result != 'verified':
            raise {'unavailable': r.Failure, 'mismatch': r.RuntimeMismatch, 'source_drift': r.Drift}[result]()
        return {'positive': False}

    monkeypatch.setattr(r, 'runtime', runtime)
    if result in ('mismatch', 'source_drift'):
        with pytest.raises(r.Failure):
            r.compensate(True)
    else:
        assert r.compensate(True) == ('control_plane_only' if result == 'unavailable' else 'verified_disabled')
    assert writes == [False]
    assert len(workers) == 2


def natural_run(r, monkeypatch):
    run, _ = labs(r, monkeypatch)
    run.update(id=999, head_sha='a' * 40, status='completed')
    monkeypatch.setenv('PRAXYS_REVIEWED_CONTROLLER_SHA', 'a' * 40)
    job = {'id': 1000, 'name': 'deploy', 'status': 'completed', 'conclusion': 'skipped', 'steps': []}
    monkeypatch.setattr(r, 'gh', lambda _: {'total_count': 1, 'jobs': [job]})
    return run, job


def test_natural_labs_terminal_bound_to_controller(recovery, monkeypatch):
    run, _ = natural_run(recovery, monkeypatch)
    recovery.natural_labs_terminal([run])


@pytest.mark.parametrize('mutation', ['absent', 'different_sha', 'queued', 'rerun', 'provider_started'])
def test_natural_labs_absence_or_wrong_revision_is_not_completion(recovery, monkeypatch, mutation):
    run, job = natural_run(recovery, monkeypatch)
    if mutation == 'absent':
        runs = []
    else:
        runs = [run]
    if mutation == 'different_sha':
        run['head_sha'] = 'b' * 40
    elif mutation == 'queued':
        run['status'] = 'queued'
    elif mutation == 'rerun':
        run['run_attempt'] = 2
    elif mutation == 'provider_started':
        job.update(conclusion='success', steps=[{'name': 'Azure Login (OIDC)', 'conclusion': 'success'}])
    with pytest.raises(recovery.Failure):
        recovery.natural_labs_terminal(runs)


def test_active_run_from_before_incident_is_not_hidden(recovery, monkeypatch):
    r = recovery
    monkeypatch.setattr(r, 'controller_evidence', lambda: None)
    monkeypatch.setattr(r, 'natural_labs_terminal', lambda _: None)
    monkeypatch.setattr(r, 'labs_guard', lambda _: None)

    def gh(path):
        if 'created=' in path:
            runs = [{'id': r.PRODUCER, 'status': 'completed', 'run_attempt': 1, 'conclusion': 'failure'}]
        elif 'status=queued' in path:
            runs = [{'id': 123, 'created_at': '2026-09-29T00:00:00Z', 'status': 'queued'}]
        else:
            runs = []
        return {'total_count': len(runs), 'workflow_runs': runs}

    monkeypatch.setattr(r, 'gh', gh)
    with pytest.raises(r.Failure):
        r.github_no_overlap()


def test_receipt_artifact_contains_only_curated_fields(recovery, monkeypatch, tmp_path):
    import json
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.setenv('GITHUB_SHA', 'a' * 40)
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setenv('PRAXYS_REVIEWED_CONTROLLER_SHA', 'a' * 40)
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('AZURE_CLIENT_SECRET', 'SECRET_CANARY')
    recovery.persist_evidence('unknown')
    raw = (tmp_path / 'publication-recovery-evidence.json').read_text()
    value = json.loads(raw)
    assert value['incident_run'] == recovery.PRODUCER
    assert value['controller_sha'] == 'a' * 40
    assert value['observation'] == 'unknown'
    assert 'SECRET_CANARY' not in raw


def test_malformed_provider_correlation_never_reaches_output(recovery, monkeypatch):
    events = audit_events(recovery)
    for event in events:
        event['correlationId'] = '\ninjected=true\n' + 'x' * 21
    monkeypatch.setattr(recovery, 'az_json', lambda _: {'value': events})
    with pytest.raises((ValueError, recovery.Failure)):
        recovery.operation_evidence()


@pytest.mark.parametrize('end', ['2026-09-30T03:00:00Z', '2026-09-30T03:00:00.800000Z'])
def test_provider_terminal_before_started_rejected(recovery, monkeypatch, end):
    monkeypatch.setenv('AZURE_CLIENT_ID', 'expected-client')
    events = audit_events(recovery)
    events[0]['eventTimestamp'] = '2026-09-30T03:00:00.900000Z'
    events[1]['eventTimestamp'] = end
    with pytest.raises(recovery.Failure):
        recovery.receipt({}, {'new': events}, '2026-09-30T03:00:00Z', '2026-09-30T03:00:02Z')
    for event in events:
        event['correlationId'] = recovery.PRODUCER_CORRELATION
    monkeypatch.setattr(recovery, 'az_json', lambda _: {'value': events})
    with pytest.raises(recovery.Failure):
        recovery.operation_evidence()


@pytest.fixture
def transport_run(recovery, monkeypatch):
    """Keep all real admission/provenance/state/receipt functions; fake only I/O."""
    from hashlib import sha256
    import json

    r = recovery
    original_gh = r.gh
    evidence = controller(r, monkeypatch)
    monkeypatch.setattr(r, 'gh', original_gh)
    monkeypatch.setenv('AZURE_CLIENT_ID', 'expected-client')
    raw = b'\n'.join([b'x'] * 593 + [r.LOG_LINE, b'x'])
    raw += b'x' * (58978 - len(raw))
    monkeypatch.setattr(r, 'LOG_SHA256', sha256(raw).hexdigest())
    sha = 'a' * 40

    def run(run_id, source_sha, workflow, event='push', status='completed'):
        return {'id': run_id, 'run_attempt': 1, 'head_sha': source_sha, 'head_branch': 'main',
                'path': workflow, 'event': event, 'status': status, 'conclusion': 'failure',
                'repository': {'full_name': r.REPOSITORY}, 'head_repository': {'full_name': r.REPOSITORY}}

    producer = run(r.PRODUCER, r.PRODUCER_SHA, r.PRODUCER_WORKFLOW)
    old_labs = run(r.LABS_RUN, r.PRODUCER_SHA, '.github/workflows/deploy-labs-worker.yml', status='in_progress')
    natural = run(999, sha, '.github/workflows/deploy-labs-worker.yml')
    steps = [{'number': number, 'name': str(number), 'status': 'completed', 'conclusion': 'skipped'}
             for number in range(8, 23)]
    names = {8: ('Capture state preserved by deployment', 'success'),
             9: ('Quiesce feedback publication before deployment', 'failure'),
             10: ('Publish acknowledged pre-quiescence intent proof', 'skipped'),
             17: ('Deploy to App Service', 'skipped'), 18: ('Verify deployed backend cutover', 'skipped'),
             19: ('Restore reviewed feedback publication after verified cutover', 'skipped')}
    for step in steps:
        if step['number'] in names:
            step['name'], step['conclusion'] = names[step['number']]
    job = {'id': r.PRODUCER_JOB, 'run_id': r.PRODUCER, 'run_attempt': 1, 'name': 'deploy',
           'status': 'completed', 'conclusion': 'failure', 'completed_at': '2026-09-30T02:18:26Z', 'steps': steps}
    guard_job = {'id': r.LABS_JOB, 'name': 'deploy', 'run_attempt': 1, 'status': 'in_progress',
                 'steps': [{'number': n, 'name': 'Require matching backend migration and authority' if n == 3 else str(n),
                            'status': 'completed' if n < 3 else 'in_progress' if n == 3 else 'pending',
                            'conclusion': 'success' if n < 3 else None} for n in range(1, 11)]}
    evidence.update({f'actions/runs/{r.PRODUCER}': producer, f'actions/runs/{r.PRODUCER}/attempts/1': producer,
                     f'actions/jobs/{r.PRODUCER_JOB}': job,
                     f'contents/{r.PRODUCER_WORKFLOW}?ref={r.PRODUCER_SHA}': {'sha': r.PRODUCER_BLOB},
                     f'actions/jobs/{r.PRODUCER_JOB}/logs': raw,
                     f'actions/runs/{r.LABS_RUN}/attempts/1/jobs?per_page=100': {'total_count': 1, 'jobs': [guard_job]},
                     'actions/runs/999/attempts/1/jobs?per_page=100': {'total_count': 1, 'jobs': [
                         {'id': 1000, 'name': 'deploy', 'status': 'completed', 'conclusion': 'skipped', 'steps': []}]}})
    for workflow, runs in [('deploy-backend.yml', [producer]), ('deploy-labs-worker.yml', [old_labs, natural])]:
        evidence[f'actions/workflows/{workflow}/runs?per_page=100&created=%3E%3D2026-09-30'] = {
            'total_count': len(runs), 'workflow_runs': runs}
        for status in ('queued', 'in_progress', 'waiting', 'requested', 'pending'):
            active = [old_labs] if workflow == 'deploy-labs-worker.yml' and status == 'in_progress' else []
            evidence[f'actions/workflows/{workflow}/runs?per_page=100&status={status}'] = {
                'total_count': len(active), 'workflow_runs': active}
    worker = {'id': r.WORKER_ID, 'properties': {'provisioningState': 'Succeeded', 'configuration': {
        'triggerType': 'Event', 'replicaTimeout': 1800, 'replicaRetryLimit': 0,
        'eventTriggerConfig': {'parallelism': 1, 'replicaCompletionCount': 1,
                              'scale': {'minExecutions': 0, 'maxExecutions': 1}}},
        'template': {'containers': [{'image': 'ghcr.io/praxys-run/praxys-labs-worker:' + r.SERVING_SHA,
                                     'resources': {'cpu': 1, 'memory': '2Gi'}}]}}}
    audit = audit_events(r)
    for index, event in enumerate(audit):
        event['correlationId'] = r.PRODUCER_CORRELATION
        event['eventDataId'] = 'producer-' + str(index)
        event['eventTimestamp'] = f'2026-09-30T02:13:2{index + 4}Z'
    state = {'writes': [], 'positive': False, 'fault': None, 'artifacts': [], 'fault_seen': False}

    def transport(phase, argv, seconds, *, payload=None, write=False):
        if argv[0] == 'gh':
            result = evidence[argv[2].removeprefix(f'repos/{r.REPOSITORY}/')]
            return result if isinstance(result, bytes) else json.dumps(result).encode()
        if argv[:6] == ['az', 'webapp', 'config', 'appsettings', 'set', '--ids']:
            value = r.POSITIVE + '=true' in argv
            state['writes'].append(value)
            r.mutation_started = True
            index = len(state['writes'])
            r.write_interval = [f'2026-09-30T03:00:0{index * 2}Z', f'2026-09-30T03:00:0{index * 2 + 1}Z']
            state['positive'] = value
            if state['fault'] == 'nonzero' or (state['fault'] == 'false_nonzero' and not value):
                raise r.Failure(1)
            new = audit_events(r)
            for number, event in enumerate(new):
                event['correlationId'] = f'12345678-1234-1234-1234-{index:012}'
                event['eventDataId'] = f'write-{index}-{number}'
                event['eventTimestamp'] = r.write_interval[number]
            if state['fault'] != 'missing_receipt':
                audit.extend(new)
            return b''
        if argv[:5] == ['az', 'webapp', 'config', 'appsettings', 'list']:
            kill = state['fault'] == 'kill_drift' and bool(state['writes']) and not state['fault_seen']
            if kill:
                state['fault_seen'] = True
            return json.dumps([{'name': r.POSITIVE, 'value': str(state['positive']).lower()},
                               {'name': r.KILL, 'value': str(kill).lower()},
                               {'name': 'OTHER_SECRET', 'value': 'SECRET_CANARY'}]).encode()
        if argv[:4] == ['az', 'containerapp', 'job', 'show']:
            response = copy.deepcopy(worker)
            if state['fault'] == 'worker_drift' and state['writes'] and not state['fault_seen']:
                response['properties']['template']['containers'][0]['image'] = 'unexpected'
                state['fault_seen'] = True
            return json.dumps(response).encode()
        if argv[:2] == ['az', 'rest']:
            return json.dumps({'value': audit}).encode()
        if argv[0] == 'curl':
            if argv[-1].endswith('/version'):
                return json.dumps({'version': r.SERVING_VERSION, 'source_sha': r.SERVING_SHA}).encode()
            positive = state['positive']
            if state['writes'] and state['fault'] in ('compensate', 'control_plane_only', 'false_nonzero', 'mixed_bad_ready'):
                if positive or state['fault'] == 'control_plane_only':
                    raise r.Failure()
            if state['fault'] == 'mixed_bad_ready' and state['writes'] and not positive:
                return json.dumps({'status': 'not_ready', 'database': 'error', 'optional_processing': {
                    'feedback_publication_positive_enable': True,
                    'feedback_publication_kill_switch': False, 'feedback_publication_enabled': True}}).encode()
            return json.dumps({'status': 'ready', 'database': 'ok', 'optional_processing': {
                'feedback_publication_positive_enable': positive,
                'feedback_publication_kill_switch': False, 'feedback_publication_enabled': positive}}).encode()
        if phase == 'evidence':
            state['artifacts'].append(json.loads(payload))
            assert b'SECRET_CANARY' not in payload
            return b''
        if phase == 'outputs':
            return b''
        if phase == 'retry_gap':
            raise r.Failure(124)
        pytest.fail(f'Unexpected external transport phase: {phase}')

    monkeypatch.setattr(r, 'command', transport)
    return r, state, evidence


def test_transport_only_complete_producer_to_receipt_path(transport_run):
    r, state, _ = transport_run
    assert r.restore() == 'verified'
    assert state['writes'] == [True]
    receipt = state['artifacts'][-1]
    assert receipt['observation'] == 'verified'
    assert receipt['writes'][0]['outcome'] == 'terminal_success'
    assert len(receipt['snapshots']) == 3


@pytest.mark.parametrize('fault', ['kill_drift', 'worker_drift', 'nonzero', 'missing_receipt'])
def test_transport_only_drift_and_uncertainty_stay_latched(transport_run, fault):
    r, state, _ = transport_run
    state['fault'] = fault
    assert r.restore() == 'unknown'
    assert state['writes'] == [True]
    assert state['artifacts'][-1]['observation'] == 'unknown'
    # The transport would return baseline on a second sample; no later sample may clear drift.
    if fault.endswith('drift'):
        assert state['fault_seen']


def test_transport_only_invalid_producer_means_zero_writes(transport_run):
    r, state, evidence = transport_run
    evidence[f'actions/jobs/{r.PRODUCER_JOB}']['steps'][0]['conclusion'] = 'failure'
    assert r.restore() == 'prewrite_rejected'
    assert state['writes'] == []


@pytest.mark.parametrize(('fault', 'outcome'), [('compensate', 'verified_disabled'),
                                              ('control_plane_only', 'control_plane_only'),
                                              ('false_nonzero', 'unknown')])
def test_transport_only_safe_compensation_uses_distinct_receipt(transport_run, fault, outcome):
    r, state, _ = transport_run
    state['fault'] = fault
    assert r.restore() == outcome
    assert state['writes'] == [True, False]
    record = state['artifacts'][-1]
    assert record['writes'][0]['outcome'] == 'terminal_success'
    if fault != 'false_nonzero':
        assert record['writes'][1]['outcome'] == 'terminal_success'
        assert record['writes'][0]['correlation'] != record['writes'][1]['correlation']
    else:
        assert record['uncertain_write'] is True


def test_unhealthy_runtime_cannot_hide_affirmative_compensation_contradiction(transport_run):
    r, state, _ = transport_run
    state['fault'] = 'mixed_bad_ready'
    assert r.restore() == 'unknown'
    assert state['writes'] == [True, False]
    assert state['artifacts'][-1]['observation'] == 'unknown'
    assert state['artifacts'][-1]['writes'][1]['outcome'] == 'terminal_success'


@pytest.mark.parametrize('rejection', ['wrong_sha', 'attempt_2', 'malformed_sha', 'malformed_attempt', 'malformed_run'])
def test_rejected_context_artifact_records_actual_identity_without_echoing_malformed_input(transport_run, monkeypatch, rejection):
    r, state, _ = transport_run
    if rejection == 'wrong_sha':
        monkeypatch.setenv('GITHUB_SHA', 'b' * 40)
    elif rejection == 'attempt_2':
        monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    elif rejection == 'malformed_sha':
        monkeypatch.setenv('GITHUB_SHA', 'SECRET_CANARY')
    elif rejection == 'malformed_attempt':
        monkeypatch.setenv('GITHUB_RUN_ATTEMPT', 'SECRET_CANARY')
    else:
        monkeypatch.setenv('GITHUB_RUN_ID', 'SECRET_CANARY')
    assert r.restore() == 'prewrite_rejected'
    assert state['writes'] == []
    artifact = state['artifacts'][-1]
    assert artifact['requested_controller_sha'] == 'a' * 40
    assert artifact['controller_sha'] == ('b' * 40 if rejection == 'wrong_sha' else None if rejection == 'malformed_sha' else 'a' * 40)
    assert artifact['controller_attempt'] == (2 if rejection == 'attempt_2' else None if rejection == 'malformed_attempt' else 1)
    assert artifact['controller_run'] == (None if rejection == 'malformed_run' else 123)
    assert artifact['identity_encoding'] == ('missing_or_malformed' if rejection.startswith('malformed') else 'valid_values')


def test_malformed_requested_revision_is_null_not_echoed(transport_run, monkeypatch):
    r, state, _ = transport_run
    monkeypatch.setenv('PRAXYS_REVIEWED_CONTROLLER_SHA', 'SECRET_CANARY')
    assert r.restore() == 'prewrite_rejected'
    assert state['writes'] == []
    assert state['artifacts'][-1]['requested_controller_sha'] is None
    assert state['artifacts'][-1]['controller_sha'] == 'a' * 40
