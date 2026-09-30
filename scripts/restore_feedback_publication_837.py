"""One-shot incident 36658804615 recovery; no generic deployment authority.

The bounded subprocess engine is derived from deploy-backend.yml restoration.
Unknown writes are latched and NEVER compensated by this controller.
"""
from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import tempfile
import time

WORK_SECONDS = 360
CLEANUP_SECONDS = 105
END_SECONDS = 465
GRACE_SECONDS = 2
LOCAL_RESERVE_SECONDS = 1
MAX_CAPTURE_BYTES = 262144
WRITE_SECONDS = 45
READ_SECONDS = 20
HTTP_SECONDS = 8
PREDICATE_SECONDS = 2
OUTPUT_SECONDS = 5
GAP_SECONDS = 5


class Failure(Exception):
    def __init__(self, code=1):
        self.code = code


def now():
    return time.clock_gettime(time.CLOCK_BOOTTIME)


started = 0.0
phase_deadline = started + WORK_SECONDS
hard_deadline = started + END_SECONDS
expired = False
conflicting_write = False
mutation_started = False
cleanup_started = False
verified = False
observation = 'unknown'
original_failure = 1
write_interval = None
receipts = []


def emit(phase, *, outcome, elapsed_ms=0, exit_class=None):
    # Bounded enum metadata only. Never print provider responses or exceptions.
    payload = json.dumps({'phase': phase, 'outcome': outcome,
                          'elapsed_ms': max(0, int(elapsed_ms)),
                          'exit_class': exit_class}) + '\n'
    try:
        os.set_blocking(1, False)
        os.write(1, payload.encode())
    except (OSError, ValueError):
        pass


def interrupt(signum, _frame):
    global expired
    expired = signum == signal.SIGALRM
    raise Failure(124 if expired else 128 + signum)


def arm(deadline):
    signal.setitimer(signal.ITIMER_REAL, max(0.001, deadline - now()))


def stop_tree(process, *, immediate=False):
    # Kill the whole owned process group, even after its leader exits: a
    # descendant may still retain stdout. Never wait for pipe EOF during reap.
    try:
        os.killpg(process.pid, signal.SIGKILL if immediate else signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        if not immediate:
            try:
                process.wait(timeout=GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.stdout.close()
        try:
            process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            pass


def command(phase, argv, seconds, *, payload=None, write=False):
    """Cap startup, pipes and descendants; the phase watchdog also bounds reap."""
    global conflicting_write, mutation_started, write_interval
    begin = now()
    if begin + seconds + GRACE_SECONDS + LOCAL_RESERVE_SECONDS > phase_deadline:
        emit(phase, outcome='not_admitted', exit_class='deadline')
        raise Failure(124)
    process = None
    completed = False
    result = bytearray()
    arm(min(phase_deadline, begin + seconds + GRACE_SECONDS))
    try:
        if write:
            mutation_started = True
        emit(phase, outcome='started')
        # A regular temporary stdin avoids blocking while feeding jq or output.
        with tempfile.TemporaryFile() as source:
            if payload is not None:
                source.write(payload)
                source.seek(0)
            if write:
                write_interval = [utc(), None]
            process = subprocess.Popen(argv, stdin=source, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            os.set_blocking(process.stdout.fileno(), False)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                eof = False
                while not (eof and process.poll() is not None):
                    remaining = begin + seconds - now()
                    if remaining <= 0:
                        raise Failure(124)
                    for key, _ in selector.select(min(remaining, 0.05)):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            eof = True
                        else:
                            result.extend(chunk)
                            if len(result) > MAX_CAPTURE_BYTES:
                                raise Failure(1)
                if now() > begin + seconds:
                    raise Failure(124)
                code = process.wait(timeout=0)
                if write:
                    write_interval[1] = utc()
                if code:
                    raise Failure(code if code > 0 else 128 - code)
                completed = True
                emit(phase, outcome='completed', elapsed_ms=(now() - begin) * 1000,
                     exit_class='success')
                return bytes(result)
    except Failure as failure:
        classification = ('deadline' if failure.code == 124 else
                          'signal' if failure.code in (130, 143) else 'nonzero')
        emit(phase, outcome='failed', elapsed_ms=(now() - begin) * 1000,
             exit_class=classification)
        raise
    except BaseException:
        emit(phase, outcome='failed', elapsed_ms=(now() - begin) * 1000,
             exit_class='internal')
        raise
    finally:
        if write and not completed:
            # A timed-out/failed control-plane write may still complete remotely.
            # Later samples cannot resolve an outstanding conflicting operation.
            conflicting_write = True
        if process is not None:
            stop_tree(process, immediate=expired or completed)
        if not expired and now() < phase_deadline:
            arm(phase_deadline)
        else:
            signal.setitimer(signal.ITIMER_REAL, 0)


# Immutable incident bindings. Controller revision is a separate reviewed input.
REPOSITORY = 'praxys-run/praxys'
WORKFLOW = '.github/workflows/restore-feedback-publication-837.yml'
PRODUCER_WORKFLOW = '.github/workflows/deploy-backend.yml'
PRODUCER = 36658804615
PRODUCER_JOB = 109708776965
PRODUCER_SHA = '4ac9393ba12b41e591d18f2fba1816143b4b889b'
PRODUCER_BLOB = '19aaa6ac50b90e6ca1762fc92f9322b0d7d2dfc8'
LOG_SHA256 = 'deff84b222c386426f1c1cd5f9f211bf9c1c62c5162242da91e06ea23f3e4301'
LOG_LINE = b'2026-09-30T02:13:21.8902077Z   ORIGINAL_FEEDBACK_PUBLICATION: true'
INCIDENT_START = '2026-09-30T02:13:00Z'
PRODUCER_CORRELATION = 'c2a3967b-31be-4762-b9a1-a4a4dce5d734'
SERVING_SHA = '38954c4a40dcc80cd3acd87400bcc9cf6a16ac46'
SERVING_VERSION = '2026.09.29.310-38954c4'
LABS_RUN = 36658804592
LABS_JOB = 109709408253
SUBSCRIPTION = '3ff02750-211c-4579-94a6-8c9af4e6d891'
GROUP = 'rg-trainsight'
APP = 'trainsight-app'
RESOURCE_GROUP = f'/subscriptions/{SUBSCRIPTION}/resourceGroups/{GROUP}'
APP_ID = RESOURCE_GROUP + '/providers/Microsoft.Web/sites/' + APP
SETTINGS_ID = APP_ID + '/config/appsettings'
WORKER_ID = RESOURCE_GROUP + '/providers/Microsoft.App/jobs/praxys-labs-environment-worker'
POSITIVE = 'PRAXYS_ENABLE_FEEDBACK_PUBLICATION'
KILL = 'PRAXYS_DISABLE_FEEDBACK_PUBLICATION'


class Drift(Failure):
    """A source or authority mismatch; never compensate across this boundary."""


def require(condition):
    if not condition:
        raise Failure()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result

    def constant(_):
        raise Failure()

    arm(min(phase_deadline, now() + PREDICATE_SECONDS))
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    finally:
        arm(phase_deadline)


def gh(path, *, raw=False):
    payload = command('github_read', ['gh', 'api', f'repos/{REPOSITORY}/{path}',
                      '-H', 'Cache-Control: no-cache'], HTTP_SECONDS)
    return payload if raw else strict_json(payload)


def collection(payload, key):
    items = payload.get(key)
    require(isinstance(items, list) and type(payload.get('total_count')) is int)
    require(payload['total_count'] == len(items) <= 100)
    require(all(isinstance(item, dict) for item in items))
    require(len({item['id'] for item in items}) == len(items))
    return items


def one(items, key, value):
    matches = [item for item in items if item.get(key) == value]
    require(len(matches) == 1)
    return matches[0]


def run_identity(run, run_id, sha, workflow, event):
    require(run.get('id') == run_id and run.get('run_attempt') == 1)
    require(run.get('head_sha') == sha and run.get('head_branch') == 'main')
    require(run.get('path') == workflow and run.get('event') == event)
    require(run.get('repository', {}).get('full_name') == REPOSITORY)
    require(run.get('head_repository', {}).get('full_name') == REPOSITORY)


def producer_evidence():
    run = gh(f'actions/runs/{PRODUCER}')
    run_identity(run, PRODUCER, PRODUCER_SHA, PRODUCER_WORKFLOW, 'push')
    require(run.get('status') == 'completed' and run.get('conclusion') == 'failure')
    attempt = gh(f'actions/runs/{PRODUCER}/attempts/1')
    run_identity(attempt, PRODUCER, PRODUCER_SHA, PRODUCER_WORKFLOW, 'push')
    job = gh(f'actions/jobs/{PRODUCER_JOB}')
    require(job.get('id') == PRODUCER_JOB and job.get('run_id') == PRODUCER)
    require(job.get('run_attempt') == 1 and job.get('name') == 'deploy')
    require(job.get('status') == 'completed' and job.get('conclusion') == 'failure')
    require(job.get('completed_at') == '2026-09-30T02:18:26Z')
    steps = job['steps']
    for number, name, conclusion in (
        (8, 'Capture state preserved by deployment', 'success'),
        (9, 'Quiesce feedback publication before deployment', 'failure'),
        (10, 'Publish acknowledged pre-quiescence intent proof', 'skipped'),
        (17, 'Deploy to App Service', 'skipped'),
        (18, 'Verify deployed backend cutover', 'skipped'),
        (19, 'Restore reviewed feedback publication after verified cutover', 'skipped'),
    ):
        step = one(steps, 'number', number)
        require(step.get('name') == name and step.get('status') == 'completed')
        require(step.get('conclusion') == conclusion)
    require(all(step.get('conclusion') == 'skipped' for step in steps
                if 10 <= step.get('number', 0) <= 22))
    source = gh(f'contents/{PRODUCER_WORKFLOW}?ref={PRODUCER_SHA}')
    require(source.get('sha') == PRODUCER_BLOB)
    log = gh(f'actions/jobs/{PRODUCER_JOB}/logs', raw=True)
    authenticate_log(log)


def authenticate_log(log):
    from hashlib import sha256

    require(len(log) == 58978 and sha256(log).hexdigest() == LOG_SHA256)
    lines = log.splitlines()
    require(lines[593] == LOG_LINE and lines.count(LOG_LINE) == 1)
    require(sum(b'Z   ORIGINAL_FEEDBACK_PUBLICATION:' in line for line in lines) == 1)


def controller_evidence():
    import re

    env = os.environ
    require(env.get('GITHUB_REPOSITORY') == REPOSITORY)
    require(env.get('GITHUB_REF') == 'refs/heads/main')
    require(env.get('GITHUB_REF_PROTECTED') == 'true')
    require(env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch')
    require(env.get('GITHUB_RUN_ATTEMPT') == '1')
    sha = env['PRAXYS_REVIEWED_CONTROLLER_SHA']
    require(re.fullmatch('[0-9a-f]{40}', sha) is not None)
    require(env.get('GITHUB_SHA') == sha)
    branch = gh('branches/main')
    require(branch.get('protected') is True and branch.get('commit', {}).get('sha') == sha)
    run_id = int(env['GITHUB_RUN_ID'])
    current = gh(f'actions/runs/{run_id}')
    run_identity(current, run_id, sha, WORKFLOW, 'workflow_dispatch')
    history = collection(gh('actions/workflows/restore-feedback-publication-837.yml/runs?per_page=100'),
                         'workflow_runs')
    # Every invocation consumes the one-off attempt, including prewrite rejection.
    require(len(history) == 1 and history[0].get('id') == run_id)


def labs_guard(run):
    run_identity(run, LABS_RUN, PRODUCER_SHA, '.github/workflows/deploy-labs-worker.yml', 'push')
    jobs = collection(gh(f'actions/runs/{LABS_RUN}/attempts/1/jobs?per_page=100'), 'jobs')
    job = one(jobs, 'name', 'deploy')
    require(job.get('id') == LABS_JOB and job.get('run_attempt') == 1)
    guard = one(job['steps'], 'name', 'Require matching backend migration and authority')
    require(guard.get('number') == 3)
    if job.get('status') == 'in_progress':
        require(guard.get('status') == 'in_progress' and guard.get('conclusion') is None)
    else:
        require(job.get('status') == 'completed' and job.get('conclusion') == 'failure')
        require(guard.get('status') == 'completed' and guard.get('conclusion') == 'failure')
    for step in job['steps']:
        if 4 <= step.get('number', 0) <= 10:
            require(step.get('status') == 'pending' or step.get('conclusion') == 'skipped')
            require(step.get('conclusion') in (None, 'skipped'))
    require({step.get('number') for step in job['steps']} >= set(range(1, 11)))
    require(all(j.get('status') == 'completed' for j in jobs if j.get('id') != LABS_JOB))


def github_no_overlap():
    controller_evidence()
    for workflow in ('deploy-backend.yml', 'deploy-labs-worker.yml'):
        runs = collection(gh(f'actions/workflows/{workflow}/runs?per_page=100&created=%3E%3D2026-09-30'),
                          'workflow_runs')
        require(any(r.get('id') == (PRODUCER if workflow == 'deploy-backend.yml' else LABS_RUN)
                    for r in runs))
        for run in runs:
            if run.get('id') == LABS_RUN:
                labs_guard(run)
            elif run.get('status') != 'completed':
                raise Failure()
            if run.get('id') == PRODUCER:
                require(run.get('run_attempt') == 1 and run.get('conclusion') == 'failure')


def az_json(argv):
    return strict_json(command('azure_read', ['az', *argv, '--output', 'json', '--only-show-errors'],
                               READ_SECONDS))


def settings():
    values = az_json(['webapp', 'config', 'appsettings', 'list', '--ids', APP_ID])
    require(isinstance(values, list))
    flags = {}
    for name in (POSITIVE, KILL):
        value = one(values, 'name', name).get('value')
        require(value in ('true', 'false'))
        flags[name] = value == 'true'
    return flags


def runtime(positive):
    def read(path):
        return strict_json(command('runtime_read', ['curl', '-fsS', '--max-time', '8', '-H',
                           'Cache-Control: no-cache', 'https://api.praxys.run/api/' + path], HTTP_SECONDS))
    version = read('version')
    if version.get('source_sha') != SERVING_SHA or version.get('version') != SERVING_VERSION:
        raise Drift()
    ready = read('health/ready')
    require(ready.get('status') == 'ready' and ready.get('database') == 'ok')
    flags = ready.get('optional_processing', {})
    require(flags.get('feedback_publication_positive_enable') is positive)
    if flags.get('feedback_publication_kill_switch') is not False:
        raise Drift()
    require(flags.get('feedback_publication_enabled') is positive)


def worker():
    value = az_json(['containerapp', 'job', 'show', '--ids', WORKER_ID])
    require(value.get('id', '').lower() == WORKER_ID.lower())
    props = value['properties']
    require(props.get('provisioningState') == 'Succeeded')
    config = props['configuration']
    require(config.get('triggerType') == 'Event' and config.get('replicaTimeout') == 1800)
    require(config.get('replicaRetryLimit') == 0)
    event = config['eventTriggerConfig']
    require(event.get('parallelism') == 1 and event.get('replicaCompletionCount') == 1)
    require(event['scale'].get('minExecutions') == 0 and event['scale'].get('maxExecutions') == 1)
    containers = props['template']['containers']
    require(len(containers) == 1)
    require(containers[0].get('image') == 'ghcr.io/praxys-run/praxys-labs-worker:' + SERVING_SHA)
    require(containers[0]['resources'].get('cpu') == 1)
    require(containers[0]['resources'].get('memory') == '2Gi')


def utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def operation_evidence():
    from urllib.parse import urlencode
    # Read raw REST envelope: CLI activity-log list hides pagination/truncation.
    query = urlencode({'api-version': '2015-04-01', '$filter':
                       f"eventTimestamp ge '{INCIDENT_START}' and resourceGroupName eq '{GROUP}'"})
    url = (f'https://management.azure.com/subscriptions/{SUBSCRIPTION}'
           '/providers/microsoft.insights/eventtypes/management/values?' + query)
    payload = az_json(['rest', '--method', 'get', '--url', url])
    require(isinstance(payload.get('value'), list) and not payload.get('nextLink'))
    events = payload['value']
    require(len(events) <= 500)
    require(len({e['eventDataId'] for e in events}) == len(events))
    groups = {}
    for event in events:
        operation = event.get('operationName', {}).get('value', '').lower()
        if operation.endswith('/read') or operation.endswith('/list/action'):
            continue
        require(operation.endswith(('/write', '/delete', '/action')))
        resource = event.get('resourceId', '').lower()
        require(resource.startswith(RESOURCE_GROUP.lower() + '/'))
        correlation = event.get('correlationId')
        require(isinstance(correlation, str) and len(correlation) == 36)
        groups.setdefault(correlation, []).append(event)
    for events in groups.values():
        statuses = [e.get('status', {}).get('value') for e in events]
        require(all(s in ('Started', 'Accepted', 'Succeeded', 'Failed') for s in statuses))
        terminal = [e for e in events if e.get('status', {}).get('value') in ('Succeeded', 'Failed')]
        require(len(terminal) == 1)
        require(all(e['eventTimestamp'] <= terminal[0]['eventTimestamp'] for e in events))
    producer = groups.get(PRODUCER_CORRELATION, [])
    require(any(e.get('status', {}).get('value') == 'Succeeded' and
                e.get('resourceId', '').lower() == SETTINGS_ID.lower() and
                e.get('operationName', {}).get('value') == 'Microsoft.Web/sites/config/write'
                for e in producer))
    return groups


def admission(positive):
    github_no_overlap()
    operations = operation_evidence()
    worker()
    require(settings() == {POSITIVE: positive, KILL: False})
    runtime(positive)
    return operations


def receipt(before, after, begin, end):
    """CLI success alone is insufficient; one unique authenticated audit operation.

    Audit ingestion may lag. Missing/ambiguous evidence is unknown, never retried.
    Caller appid comes from the OIDC login configuration, never a guessed identity.
    """
    require(set(before) <= set(after))
    require(all(after[key] == value for key, value in before.items()))
    new = set(after) - set(before)
    require(len(new) == 1)
    correlation = new.pop()
    events = after[correlation]
    require(len(events) >= 2)
    require({e.get('status', {}).get('value') for e in events} == {'Started', 'Succeeded'})
    from datetime import datetime
    lower, upper = datetime.fromisoformat(begin), datetime.fromisoformat(end)
    callers = set()
    for event in events:
        require(event.get('resourceId', '').lower() == SETTINGS_ID.lower())
        require(event.get('operationName', {}).get('value') == 'Microsoft.Web/sites/config/write')
        require(event.get('claims', {}).get('appid') == os.environ['AZURE_CLIENT_ID'])
        require(lower <= datetime.fromisoformat(event['eventTimestamp']) <= upper)
        callers.add(event.get('caller'))
    require(len(callers) == 1 and None not in callers and '' not in callers)
    return correlation


def set_positive(value, before):
    global conflicting_write
    # Mark uncertainty BEFORE spawning. Only the definitive audit receipt clears it.
    conflicting_write = True
    command('restore_write' if value else 'disable_write',
            ['az', 'webapp', 'config', 'appsettings', 'set', '--ids', APP_ID,
             '--settings', POSITIVE + '=' + str(value).lower(), '--output', 'none',
             '--only-show-errors'], WRITE_SECONDS, write=True)
    require(write_interval is not None and write_interval[1] is not None)
    begin, end = write_interval
    after = operation_evidence()
    correlation = receipt(before, after, begin, end)
    conflicting_write = False
    receipts.append(correlation)
    emit('write_receipt', outcome='terminal_success')
    return after, correlation


def outputs(state):
    require(state in ('verified', 'verified_disabled', 'control_plane_only', 'unknown', 'prewrite_rejected'))
    command('outputs', ['bash', '-c', 'cat >> "$GITHUB_OUTPUT"'], OUTPUT_SECONDS,
            payload=(f'observation={state}\n' +
                     ''.join(f'write_{i + 1}_correlation={value}\n'
                             for i, value in enumerate(receipts))).encode())


def compensate(acknowledged):
    global phase_deadline, expired
    require(acknowledged and not conflicting_write)
    expired = False
    phase_deadline = min(now() + CLEANUP_SECONDS, hard_deadline)
    arm(phase_deadline)
    # No retry, no uncertain write, and no source/kill/worker drift is admissible.
    github_no_overlap()
    before = operation_evidence()
    worker()
    require(settings() == {POSITIVE: True, KILL: False})
    version = strict_json(command('version_read', ['curl', '-fsS', '--max-time', '8', '-H',
        'Cache-Control: no-cache', 'https://api.praxys.run/api/version'], HTTP_SECONDS))
    if version.get('source_sha') != SERVING_SHA or version.get('version') != SERVING_VERSION:
        raise Drift()
    set_positive(False, before)
    require(settings() == {POSITIVE: False, KILL: False})
    try:
        runtime(False)
    except Drift:
        raise
    except Failure:
        return 'control_plane_only'
    return 'verified_disabled'


def restore():
    acknowledged = False
    try:
        controller_evidence()
        producer_evidence()
        admission(False)
        # Fresh repeat after all historical evidence; never reuse the first sample.
        before = admission(False)
        after, _ = set_positive(True, before)
        acknowledged = True
        for _ in range(36):
            try:
                require(settings() == {POSITIVE: True, KILL: False})
                runtime(True)
                worker()
            except Drift:
                raise
            except Failure as failure:
                if expired or failure.code in (130, 143):
                    raise
                command('retry_gap', ['sleep', '5'], GAP_SECONDS + LOCAL_RESERVE_SECONDS)
            else:
                github_no_overlap()
                require(operation_evidence() == after)
                outputs('verified')
                return 'verified'
        raise Failure()
    except BaseException as failure:
        state = 'unknown' if mutation_started else 'prewrite_rejected'
        if acknowledged and not conflicting_write and not isinstance(failure, Drift):
            try:
                state = compensate(acknowledged)
            except BaseException:
                state = 'unknown'
        try:
            outputs(state)
        except BaseException:
            state = 'unknown'
        return state


def main():
    global started, phase_deadline, hard_deadline
    state = 'unknown'
    try:
        started = float(os.environ['PRAXYS_RESTORE_STARTED'])
        require(0 < started <= now())
        phase_deadline = started + WORK_SECONDS
        hard_deadline = started + END_SECONDS
        require(now() < phase_deadline)
        for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, interrupt)
        arm(phase_deadline)
        state = restore()
    except BaseException:
        pass
    emit('restoration', outcome=state)
    os._exit(0 if state == 'verified' else 1)


if __name__ == '__main__':
    main()
