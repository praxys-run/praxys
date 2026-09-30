"""Execute the actual quiescence shell with local fakes; never call Azure or HTTP."""
from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
INCIDENT_SHA = 'bafd1714df108747758bd58273578be3613b7bd0'
WORKFLOW = ROOT / '.github/workflows/deploy-backend.yml'
pytestmark = pytest.mark.skipif(os.name == 'nt', reason='Deployment shell targets GitHub Linux runners')


@lru_cache(maxsize=1)
def _workflow_document():
    return yaml.load(WORKFLOW.read_text(), Loader=getattr(yaml, 'CBaseLoader', yaml.BaseLoader))


def workflow():
    # Each caller owns its document; only immutable checked-in source is cached.
    return deepcopy(_workflow_document())


def steps():
    return {step.get('name'):step for job in workflow()['jobs'].values() for step in job['steps'] if 'name' in step}


def test_workflow_parser_preserves_base_loader_semantics_and_caller_isolation():
    expected = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    document = workflow()
    assert document == expected
    document['jobs'].clear()
    selected = steps()['Quiesce feedback publication before deployment']
    selected['run'] = 'must not reach another caller'
    selected['env'].clear()
    assert workflow() == expected
    assert steps()['Quiesce feedback publication before deployment'] != selected


def ready_payload():
    return {'status':'ready', 'optional_processing':{
        'feedback_publication_positive_enable':False,
        'feedback_publication_kill_switch':True,
        'feedback_publication_enabled':False}}


@pytest.fixture
def execute_quiescence(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    log = tmp_path / 'calls.jsonl'
    program = f'#!{sys.executable}\n' + '''import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
with Path(os.environ['FAKE_LOG']).open('a') as stream:
    stream.write(json.dumps({'name':name,'args':args})+'\\n')
if name=='az':
    if args[:4]==['webapp','config','appsettings','list']:
        print(json.dumps([{'name':'PRAXYS_ENABLE_FEEDBACK_PUBLICATION','value':'false'},
                          {'name':'PRAXYS_DISABLE_FEEDBACK_PUBLICATION','value':'true'}]))
    elif args[:4]!=['webapp','config','appsettings','set']:
        raise SystemExit(99)
elif name=='curl':
    if args[-1].endswith('/api/version'):
        print(os.environ['FAKE_VERSION'])
        raise SystemExit(int(os.environ['FAKE_VERSION_EXIT']))
    assert args[-1].endswith('/api/health/ready')
    counter=Path(os.environ['FAKE_COUNTER'])
    index=int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(index+1))
    responses=json.loads(os.environ['FAKE_RESPONSES'])
    response=responses[min(index,len(responses)-1)]
    body=response['body']
    print(body if isinstance(body,str) else json.dumps(body))
    raise SystemExit(response.get('exit',0))
elif name=='python3':
    print(json.dumps({'restore_positive':True,'producer_run_id':101,'artifact_id':202,'artifact_digest':'sha256:'+'a'*64}))
    raise SystemExit(int(os.environ.get('FAKE_PROOF_EXIT','0')))
elif name!='sleep':
    raise SystemExit(98)
'''
    for name in ('az','curl','sleep','python3'):
        path=bin_dir/name
        path.write_text(program)
        path.chmod(0o755)

    def run(*, recovery=True, overrides=None, responses=None):
        env=dict(os.environ, PATH=f'{bin_dir}:/usr/bin:/bin',
            FAKE_LOG=str(log), FAKE_COUNTER=str(tmp_path/'counter'),
            FAKE_VERSION=json.dumps({'source_sha':INCIDENT_SHA}), FAKE_VERSION_EXIT='0',
            FAKE_RESPONSES=json.dumps(responses or [{'body':ready_payload()}]),
            RECOVER_DFA_CUTOVER_842='true' if recovery else 'false',
            RECOVER_READINESS_TIMING_00577='false', ORIGINAL_FEEDBACK_PUBLICATION='true',
            QUIESCENCE_PRODUCER_RUN='', QUIESCENCE_PROOF_ZIP='', GITHUB_WORKSPACE=str(ROOT),
            GITHUB_OUTPUT=str(tmp_path/'outputs'), RUNNER_TEMP=str(tmp_path),
            GITHUB_EVENT_NAME='workflow_dispatch' if recovery else 'push',
            GITHUB_REF='refs/heads/main', GITHUB_RUN_ID='12345', GITHUB_RUN_ATTEMPT='1',
            GITHUB_STEP_SUMMARY=str(tmp_path/'summary'), SYNC_CONFIG='true',
            CONFIGURED_FEEDBACK_PUBLICATION='true', AZURE_BACKEND_APP_NAME='synthetic',
            AZURE_RESOURCE_GROUP='synthetic')
        env.update(overrides or {})
        result=subprocess.run(['bash','-c',steps()['Quiesce feedback publication before deployment']['run']],
                              env=env,cwd=tmp_path,capture_output=True,text=True,timeout=20)
        calls=[json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        summary=(tmp_path/'summary').read_text() if (tmp_path/'summary').exists() else ''
        return result,calls,summary
    return run


def readiness_calls(calls):
    return [call for call in calls if call['name']=='curl' and call['args'][-1].endswith('/api/health/ready')]


def test_dispatch_option_is_boolean_default_false_and_postdeployment_gates_unchanged():
    parsed=workflow()
    option=parsed['on']['workflow_dispatch']['inputs']['recover_dfa_cutover_842']
    assert option['type']=='boolean' and option['default']=='false'
    stage=steps()['Quiesce feedback publication before deployment']
    assert stage['timeout-minutes']=="${{ (inputs.recover_dfa_cutover_842 == true || inputs.recover_readiness_timing_00577 == true) && 9 || 5 }}"
    assert stage['env']['RECOVER_DFA_CUTOVER_842']=="${{ inputs.recover_dfa_cutover_842 == true && 'true' || 'false' }}"
    assert stage['env']['SYNC_CONFIG']=='${{ steps.mode.outputs.sync_config }}'
    assert stage['env']['CONFIGURED_FEEDBACK_PUBLICATION']=="${{ vars.PRAXYS_ENABLE_FEEDBACK_PUBLICATION || 'false' }}"
    assert '--retry' not in stage['run']
    for name in ['Verify deployed backend cutover','Restore reviewed feedback publication after verified cutover']:
        assert ('--max-time 8' in steps()[name]['run'] or "'--max-time', '8'" in steps()[name]['run'])
        assert '--max-time 210' not in steps()[name]['run']
        assert 'RECOVER_DFA_CUTOVER_842' not in steps()[name]['run']
    restore=steps()['Restore reviewed feedback publication after verified cutover']['run']
    assert 'verified = True' in restore and 'def cleanup()' in restore
    assert 'PRAXYS_DISABLE_FEEDBACK_PUBLICATION' in restore and 'PRAXYS_DISABLE_FEEDBACK_PUBLICATION=' not in restore


def test_recovery_validates_source_and_uses_one_complete_bounded_read(execute_quiescence):
    result,calls,summary=execute_quiescence()
    assert result.returncode==0,result.stderr
    ready=readiness_calls(calls)
    assert len(ready)==1
    assert ready[0]['args'][:5]==['-fsS','--connect-timeout','5','--max-time','210']
    assert calls[0]['name']=='curl' and calls[0]['args'][-1].endswith('/api/version')
    assert any(call['name']=='az' and 'PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false' in call['args'] for call in calls)
    assert 'Dispatch run: 12345; attempt: 1' in summary and 'consumes the one-off authorization' in summary
    assert not any(call['name']=='sleep' for call in calls)


def test_second_attempt_has_one_gap_and_no_nested_retry(execute_quiescence):
    result,calls,_=execute_quiescence(responses=[{'body':'','exit':28},{'body':ready_payload()}])
    assert result.returncode==0,result.stderr
    assert len(readiness_calls(calls))==2
    assert [call['args'] for call in calls if call['name']=='sleep']==[['5']]
    assert all('--retry' not in call['args'] for call in calls)


@pytest.mark.parametrize('override', [
    {'GITHUB_EVENT_NAME':'push'}, {'GITHUB_REF':'refs/heads/not-main'},
    {'GITHUB_RUN_ATTEMPT':'2'}, {'GITHUB_RUN_ID':'not-a-run'},
    {'SYNC_CONFIG':'false'}, {'CONFIGURED_FEEDBACK_PUBLICATION':'false'},
    {'CONFIGURED_FEEDBACK_PUBLICATION':'True'}, {'RECOVER_DFA_CUTOVER_842':'yes'},
    {'FAKE_VERSION':json.dumps({'source_sha':'0'*40})}, {'FAKE_VERSION':'not JSON'},
    {'FAKE_VERSION':'{}'}, {'FAKE_VERSION_EXIT':'28'},
])
def test_recovery_guard_failures_precede_quiescence_mutation(execute_quiescence, override):
    result,calls,_=execute_quiescence(overrides=override)
    assert result.returncode!=0
    assert not any(call['name']=='az' for call in calls)
    assert readiness_calls(calls)==[]


@pytest.mark.parametrize('mutation', ['status','positive_true','positive_string','kill_missing','kill_string','effective_true','effective_string','empty','malformed'])
def test_recovery_never_relaxes_quiescence_predicates(execute_quiescence, mutation):
    body=ready_payload()
    controls=body['optional_processing']
    if mutation=='status':body['status']='unavailable'
    if mutation=='positive_true':controls['feedback_publication_positive_enable']=True
    if mutation=='positive_string':controls['feedback_publication_positive_enable']='false'
    if mutation=='kill_missing':controls.pop('feedback_publication_kill_switch')
    if mutation=='kill_string':controls['feedback_publication_kill_switch']='true'
    if mutation=='effective_true':controls['feedback_publication_enabled']=True
    if mutation=='effective_string':controls['feedback_publication_enabled']='false'
    if mutation=='empty':body=''
    if mutation=='malformed':body='{"status":'
    result,calls,_=execute_quiescence(responses=[{'body':body}])
    assert result.returncode!=0
    assert len(readiness_calls(calls))==2
    assert [call['args'] for call in calls if call['name']=='sleep']==[['5']]


def test_normal_push_keeps_original_transport_and_attempt_budget(execute_quiescence):
    result,calls,summary=execute_quiescence(recovery=False,responses=[{'body':'','exit':28}],
                                         overrides={'SYNC_CONFIG':'false','CONFIGURED_FEEDBACK_PUBLICATION':'false'})
    assert result.returncode!=0
    ready=readiness_calls(calls)
    assert len(ready)==36
    assert all(call['args'][:3]==['-fsS','--max-time','8'] and '--connect-timeout' not in call['args'] for call in ready)
    assert not any(call['name']=='curl' and call['args'][-1].endswith('/api/version') for call in calls)
    assert len([call for call in calls if call['name']=='sleep'])==36
    assert summary==''


@pytest.mark.parametrize('curl_exit', [28, 18])
def test_valid_body_with_failed_transport_never_satisfies_recovery(execute_quiescence, curl_exit):
    result,calls,_=execute_quiescence(responses=[{'body':ready_payload(),'exit':curl_exit}])
    assert result.returncode!=0
    assert len(readiness_calls(calls))==2
    assert [call['args'] for call in calls if call['name']=='sleep']==[['5']]


@pytest.mark.parametrize('curl_exit', [28, 18])
def test_failed_transport_valid_body_requires_second_complete_response(execute_quiescence, curl_exit):
    result,calls,_=execute_quiescence(responses=[
        {'body':ready_payload(),'exit':curl_exit}, {'body':ready_payload(),'exit':0}])
    assert result.returncode==0,result.stderr
    assert len(readiness_calls(calls))==2
    assert [call['args'] for call in calls if call['name']=='sleep']==[['5']]


TIMING_SOURCE = '00577ce859ff90bbdf50a90e8ba00c4822243ec4'


def test_new_delivery_is_distinct_default_false_and_exactly_guarded(execute_quiescence):
    option = workflow()['on']['workflow_dispatch']['inputs']['recover_readiness_timing_00577']
    assert option['type'] == 'boolean' and option['default'] == 'false'
    result, calls, _ = execute_quiescence(overrides={
        'RECOVER_DFA_CUTOVER_842': 'false', 'RECOVER_READINESS_TIMING_00577': 'true',
        'ORIGINAL_FEEDBACK_PUBLICATION':'false', 'QUIESCENCE_PRODUCER_RUN':'101', 'QUIESCENCE_PROOF_ZIP':'synthetic-unit-proof',
        'FAKE_VERSION': json.dumps({'source_sha': TIMING_SOURCE})})
    assert result.returncode == 0, result.stderr
    assert len(readiness_calls(calls)) == 1
    assert readiness_calls(calls)[0]['args'][4] == '210'


@pytest.mark.parametrize('override', [
    {'RECOVER_DFA_CUTOVER_842': 'true'}, {'ORIGINAL_FEEDBACK_PUBLICATION': 'true'},
    {'ORIGINAL_FEEDBACK_PUBLICATION': ''}, {'CONFIGURED_FEEDBACK_PUBLICATION': 'false'},
    {'GITHUB_EVENT_NAME': 'push'}, {'GITHUB_REF': 'refs/heads/other'},
    {'GITHUB_RUN_ATTEMPT': '2'}, {'SYNC_CONFIG': 'false'},
    {'FAKE_VERSION': json.dumps({'source_sha': INCIDENT_SHA})},
    {'FAKE_VERSION_EXIT': '28'}, {'RECOVER_READINESS_TIMING_00577': 'yes'},
])
def test_new_delivery_guard_failures_never_mutate(execute_quiescence, override):
    options = {'RECOVER_DFA_CUTOVER_842': 'false', 'RECOVER_READINESS_TIMING_00577': 'true',
               'ORIGINAL_FEEDBACK_PUBLICATION':'false', 'QUIESCENCE_PRODUCER_RUN':'101', 'QUIESCENCE_PROOF_ZIP':'synthetic-unit-proof',
               'FAKE_VERSION': json.dumps({'source_sha': TIMING_SOURCE})}
    options.update(override)
    result, calls, _ = execute_quiescence(overrides=options)
    assert result.returncode != 0
    assert not any(call['name'] == 'az' for call in calls)
    assert readiness_calls(calls) == []


@pytest.fixture
def execute_restoration(tmp_path):
    """Execute the exact shell and jq; fakes never reach Azure or HTTP.

    A test-only interpreter adapter supplies deterministic elapsed time or scales
    ONLY deadline constants for real watchdog tests. Production has no test input.
    """
    import stat
    import time
    import signal
    bin_dir = tmp_path / 'restore-bin'
    bin_dir.mkdir()
    log = tmp_path / 'restore-calls.jsonl'
    clock = tmp_path / 'clock'
    state = tmp_path / 'state.json'
    pids = tmp_path / 'pids'
    bootstrap = f'#!{sys.executable}\n' + r'''
import ast,json,os,sys,time
from pathlib import Path
source=sys.stdin.read()
Path(os.environ['FAKE_CONTROLLER_PID']).write_text(str(os.getpid()))
scale=float(os.environ.get('FAKE_SCALE','1'))
if scale!=1:
    tree=ast.parse(source)
    names={'WORK_SECONDS','CLEANUP_SECONDS','END_SECONDS','GRACE_SECONDS',
           'LOCAL_RESERVE_SECONDS','WRITE_SECONDS','READ_SECONDS','HTTP_SECONDS',
           'PREDICATE_SECONDS','OUTPUT_SECONDS','GAP_SECONDS'}
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):
            value=node.value.value*scale
            # Keep real subprocess startup from eclipsing unrelated tiny test
            # budgets; only constants change, never the controller algorithm.
            name=node.targets[0].id
            if name in {'READ_SECONDS','HTTP_SECONDS'}:value=max(value,.25)
            if name=='PREDICATE_SECONDS':value=max(value,.10)
            node.value=ast.Constant(value)
    source=compile(ast.fix_missing_locations(tree),'<actual-restoration-short-deadlines>','exec')
else:
    clock=Path(os.environ['FAKE_CLOCK'])
    os.environ['PRAXYS_RESTORE_STARTED']='0'
    time.clock_gettime=lambda _:float(clock.read_text())
if os.environ.get('FAKE_PARSE_STALL')=='true':
    original=json.loads
    def stalled(value,*args,**kwargs):
        time.sleep(30)
        return original(value,*args,**kwargs)
    json.loads=stalled
exec(source,{'__name__':'__main__'})
'''
    (bin_dir / 'python3').write_text(bootstrap)
    (bin_dir / 'python3').chmod(0o755)
    program = f'#!{sys.executable}\n' + r'''
import json,os,signal,sys,time
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
clock=Path(os.environ['FAKE_CLOCK'])
state=Path(os.environ['FAKE_STATE'])
plan=json.loads(os.environ['FAKE_PLAN'])
if name=='az':
    operation='settings_read'
    if args[3]=='set':
        counter=state.with_name('writes')
        count=int(counter.read_text()) if counter.exists() else 0
        counter.write_text(str(count+1))
        operation='restore_write' if count==0 else 'disable_write'
elif name=='curl':operation='version' if args[-1].endswith('/api/version') else 'readiness'
else:operation='retry_gap'
counter=state.with_name(operation+'-count')
count=int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(count+1))
events=plan.get(operation,[{}]);event=events[min(count,len(events)-1)]
with Path(os.environ['FAKE_LOG']).open('a') as out:
    out.write(json.dumps({'operation':operation,'args':args,'time':float(clock.read_text())})+'\n')
current=json.loads(state.read_text())
if operation in ('restore_write','disable_write') and event.get('applied',True):
    current['positive']=next(arg.split('=',1)[1] for arg in args if arg.startswith('PRAXYS_ENABLE_FEEDBACK_PUBLICATION='))=='true'
    state.write_text(json.dumps(current))
if event.get('hang'):
    if event['hang']=='descendant_pipe':
        if os.fork():raise SystemExit(0)
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    with Path(os.environ['FAKE_PIDS']).open('a') as out:out.write(str(os.getpid())+'\n')
    time.sleep(30)
if os.environ.get('FAKE_SCALE','1')=='1':
    duration=event.get('duration',5 if operation=='retry_gap' else 0)
    # The controller reads concurrently: publish a complete clock value so it
    # cannot observe a truncated file that a real monotonic clock never exposes.
    next_clock=clock.with_name(f'{clock.name}.{os.getpid()}.tmp')
    next_clock.write_text(str(float(clock.read_text())+duration))
    next_clock.replace(clock)
if operation=='settings_read':
    payload=event.get('body',[{'name':'PRAXYS_ENABLE_FEEDBACK_PUBLICATION','value':str(current['positive']).lower()},
          {'name':'PRAXYS_DISABLE_FEEDBACK_PUBLICATION','value':str(current['kill']).lower()},
          {'name':'PRIVATE_TEST_SETTING','value':'secret-settings-canary'}])
elif operation=='version':payload=event.get('body',{'version':'synthetic-version','source_sha':os.environ['PRAXYS_EXPECTED_API_SOURCE_SHA']})
elif operation=='readiness':payload=event.get('body',{'status':'ready','optional_processing':{
    'feedback_publication_positive_enable':current['positive'],
    'feedback_publication_kill_switch':current['kill'],
    'feedback_publication_enabled':current['positive'] and not current['kill']}})
else:payload=''
print(payload if isinstance(payload,str) else json.dumps(payload))
print('secret-stderr-canary',file=sys.stderr)
raise SystemExit(event.get('exit',0))
'''
    for name in ('az', 'curl', 'sleep'):
        path = bin_dir / name
        path.write_text(program)
        path.chmod(0o755)

    def run(*, desired=True, kill=False, plan=None, scale=1, blocked_output=False, parse_stall=False,
            start_elapsed=0, signal_after=None):
        clock.write_text(str(start_elapsed))
        state.write_text(json.dumps({'positive': False, 'kill': kill}))
        output = tmp_path / 'output'
        if blocked_output:
            os.mkfifo(output)
        env = dict(os.environ, PATH=f'{bin_dir}:/usr/bin:/bin', FAKE_LOG=str(log),
            FAKE_CLOCK=str(clock), FAKE_STATE=str(state), FAKE_PLAN=json.dumps(plan or {}),
            FAKE_SCALE=str(scale), FAKE_PIDS=str(pids), FAKE_CONTROLLER_PID=str(tmp_path/'controller-pid'), FAKE_PARSE_STALL=str(parse_stall).lower(),
            DESIRED_FEEDBACK_PUBLICATION=str(desired).lower(),
            AZURE_BACKEND_APP_NAME='synthetic', AZURE_RESOURCE_GROUP='synthetic',
            PRAXYS_EXPECTED_API_SOURCE_SHA=TIMING_SOURCE, PRAXYS_EXPECTED_API_VERSION='synthetic-version',
            GITHUB_OUTPUT=str(output))
        begin = time.monotonic()
        process = subprocess.Popen(['bash', '-c', steps()['Restore reviewed feedback publication after verified cutover']['run']],
            cwd=tmp_path, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        if signal_after is not None:
            time.sleep(signal_after)
            # The outer GNU watchdog forwards TERM to its controller.
            os.kill(int((tmp_path/'controller-pid').read_text()), signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=12)
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise
        elapsed = time.monotonic() - begin
        result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        text = output.read_text() if output.exists() and stat.S_ISREG(output.stat().st_mode) else ''
        descendants = [int(line) for line in pids.read_text().splitlines()] if pids.exists() else []
        return result, calls, text, elapsed, descendants
    return run


@pytest.mark.parametrize('desired,kill', [(True,False),(True,True),(False,False),(False,True)])
def test_restoration_current_authority_all_combinations(execute_restoration, desired, kill):
    result, calls, output, _, _ = execute_restoration(desired=desired, kill=kill)
    assert result.returncode == 0, result.stderr + result.stdout
    assert output == (f'observation=verified\npositive={str(desired).lower()}\n'
                      f'kill_switch={str(kill).lower()}\nenabled={str(desired and not kill).lower()}\n')
    assert [call['operation'] for call in calls] == ['restore_write','settings_read','version','readiness']
    assert all('PRAXYS_DISABLE_FEEDBACK_PUBLICATION=' not in ' '.join(call['args']) for call in calls)
    assert 'secret-' not in result.stdout + result.stderr + output


@pytest.mark.parametrize('endpoint', ['version','readiness'])
@pytest.mark.parametrize('exit_code', [18,28])
def test_restoration_rejects_valid_body_with_failed_transport(execute_restoration, endpoint, exit_code):
    result, calls, output, _, _ = execute_restoration(plan={endpoint:[{'exit':exit_code}]})
    assert result.returncode != 0
    assert 'observation=verified\n' not in output
    assert sum(call['operation']=='disable_write' for call in calls) == 1
    assert 'control_plane_only' in output


@pytest.mark.parametrize('body', [
    {}, {'status':'unavailable'}, {'status':'ready','optional_processing':{}},
    {'status':'ready','optional_processing':{'feedback_publication_positive_enable':'true',
      'feedback_publication_kill_switch':False,'feedback_publication_enabled':True}},
    {'status':'ready','optional_processing':{'feedback_publication_positive_enable':True,
      'feedback_publication_kill_switch':True,'feedback_publication_enabled':True}},
    'secret-invalid-json-canary',
])
def test_restoration_rejects_malformed_and_contradictory_runtime(execute_restoration, body):
    result, calls, output, _, _ = execute_restoration(plan={'readiness':[{'body':body}]})
    assert result.returncode != 0 and 'observation=verified\n' not in output
    assert 'secret-' not in result.stdout + result.stderr + output
    assert sum(call['operation']=='disable_write' for call in calls) == 1


def test_restoration_wrong_source_and_exhausted_attempts(execute_restoration):
    result, calls, output, _, _ = execute_restoration(plan={'version':[{'body':{'version':'synthetic-version','source_sha':'0'*40}}]})
    assert result.returncode != 0
    assert sum(call['operation']=='restore_write' for call in calls) == 1
    assert sum(call['operation']=='readiness' for call in calls) == 37  # 36 attempts + cleanup
    assert sum(call['operation']=='retry_gap' for call in calls) == 35
    assert 'control_plane_only' in output


@pytest.mark.parametrize('write_phase', ['restore_write','disable_write'])
def test_ambiguous_applied_write_never_becomes_settled(execute_restoration, write_phase):
    plan = {write_phase:[{'exit':124,'applied':True}]}
    if write_phase == 'disable_write':
        plan['version'] = [{'exit':1}]
    result, calls, output, _, _ = execute_restoration(plan=plan)
    assert result.returncode != 0
    assert 'observation=unknown' in output
    assert 'verified_disabled' not in result.stdout + output
    assert sum(call['operation']=='disable_write' for call in calls) == 1


def test_failed_verification_can_prove_disabled_without_claiming_restoration(execute_restoration):
    result, calls, output, _, _ = execute_restoration(plan={'settings_read':[{'exit':1},{}]})
    assert result.returncode != 0
    assert 'observation=verified_disabled' in output
    assert 'positive=unknown' in output
    assert sum(call['operation']=='disable_write' for call in calls) == 1


def test_no_config_proof_never_accepts_runtime_false(execute_restoration):
    result, _, output, _, _ = execute_restoration(plan={'settings_read':[{'exit':1}]})
    assert result.returncode != 0
    assert 'verified_disabled' not in result.stdout + output
    assert '"outcome": "unknown"' in result.stdout


def test_main_deadline_preserves_cleanup_reserve(execute_restoration):
    # Each completed settings read spends19s. HTTP failures spend8s. The
    # controller must stop admitting work before its absolute360s deadline.
    result, calls, output, _, _ = execute_restoration(plan={
        'settings_read':[{'duration':19}], 'readiness':[{'duration':8,'exit':28}]})
    assert result.returncode != 0
    assert sum(call['operation']=='readiness' for call in calls) < 36
    cleanup = next(call for call in calls if call['operation']=='disable_write')
    assert cleanup['time'] <= 360
    assert max(call['time'] for call in calls) <= 465
    assert 'observation=verified\n' not in output


@pytest.mark.parametrize('hang', ['ignore_term','descendant_pipe'])
def test_real_watchdog_reaps_command_tree_and_inherited_pipe(execute_restoration, hang):
    result, calls, output, elapsed, descendants = execute_restoration(
        scale=.01, plan={'restore_write':[{'hang':hang}]})
    assert result.returncode != 0
    assert elapsed < 6
    assert descendants
    for pid in descendants:
        status = Path(f'/proc/{pid}/stat')
        assert not status.exists() or status.read_text().split()[2] == 'Z'
    assert sum(call['operation']=='disable_write' for call in calls) <= 1
    assert 'verified_disabled' not in output + result.stdout


def test_real_watchdog_bounds_blocked_outputs_and_cleanup(execute_restoration):
    result, calls, output, elapsed, _ = execute_restoration(scale=.01, blocked_output=True)
    assert result.returncode != 0 and elapsed < 6
    assert output == ''
    assert '"phase": "outputs", "outcome": "started"' in result.stdout, result.stdout
    assert sum(call['operation']=='disable_write' for call in calls) == 1
    assert '"phase": "restoration", "outcome": "unknown"' in result.stdout


def test_independent_phase_watchdog_bounds_parsing_and_cleanup(execute_restoration):
    result, calls, output, elapsed, _ = execute_restoration(scale=.01, parse_stall=True)
    assert result.returncode != 0 and elapsed < 6
    assert sum(call['operation']=='disable_write' for call in calls) == 1
    assert 'observation=verified\n' not in output
    assert '"phase": "restoration", "outcome": "unknown"' in result.stdout


def test_failure_and_signal_cannot_repeat_cleanup(execute_restoration):
    result, calls, output, elapsed, _ = execute_restoration(scale=.02,
        plan={'restore_write':[{'hang':'ignore_term'}], 'disable_write':[{'hang':'ignore_term'}]},
        signal_after=1.1)
    assert result.returncode == 124 and elapsed < 10  # original write timeout survives the later signal
    assert sum(call['operation']=='disable_write' for call in calls) <= 1
    assert 'verified_disabled' not in output + result.stdout


def test_workflow_order_and_failure_summary_never_reuse_cutover_values():
    ordered = list(steps())
    assert ordered.index('Verify deployed backend cutover') < ordered.index('Restore reviewed feedback publication after verified cutover')
    assert ordered.index('Restore reviewed feedback publication after verified cutover') < ordered.index('Observe exact DFA policy after normal publication restoration')
    restore = steps()['Restore reviewed feedback publication after verified cutover']
    assert restore.get('if', 'success()') == 'success()'
    assert restore['timeout-minutes'] == '8'
    summary = steps()['Summarize backend deployment']['env']
    for key in ('LIVE_FEEDBACK_PUBLICATION_POSITIVE','LIVE_FEEDBACK_PUBLICATION_KILL','LIVE_FEEDBACK_PUBLICATION_ENABLED'):
        assert "steps.publication.outcome == 'success'" in summary[key]
        assert 'steps.live.outputs' not in summary[key] and "'unknown'" in summary[key]


@pytest.mark.parametrize('elapsed,admitted', [(311.999, True), (312, True), (312.001, False)])
def test_startup_cost_and_exact_write_admission_boundary(execute_restoration, elapsed, admitted):
    result, calls, output, _, _ = execute_restoration(start_elapsed=elapsed)
    assert any(call['operation']=='restore_write' for call in calls) is admitted
    assert (result.returncode == 0) is admitted
    if not admitted:
        assert calls == [] and output == ''


@pytest.mark.parametrize('settings', [[], [{'name':'PRAXYS_ENABLE_FEEDBACK_PUBLICATION','value':'true'}],
    [{'name':'PRAXYS_ENABLE_FEEDBACK_PUBLICATION','value':'true'},
     {'name':'PRAXYS_ENABLE_FEEDBACK_PUBLICATION','value':'false'},
     {'name':'PRAXYS_DISABLE_FEEDBACK_PUBLICATION','value':'false'}]])
def test_missing_duplicate_config_is_unknown(execute_restoration, settings):
    result, _, output, _, _ = execute_restoration(plan={'settings_read':[{'body':settings}]})
    assert result.returncode != 0
    assert 'verified_disabled' not in output + result.stdout
    assert '"phase": "restoration", "outcome": "unknown"' in result.stdout


def test_normal_runtime_failure_and_current_false_config_is_control_plane_only(execute_restoration):
    result, _, output, _, _ = execute_restoration(plan={
        'settings_read':[{'exit':1},{}], 'readiness':[{'exit':28}]})
    assert result.returncode != 0
    assert 'observation=control_plane_only' in output


def test_signal_during_initial_write_is_retained_and_ambiguous(execute_restoration):
    result, calls, output, elapsed, _ = execute_restoration(scale=.02,
        plan={'restore_write':[{'hang':'ignore_term'}]}, signal_after=.2)
    assert result.returncode == 143 and elapsed < 6
    assert '"exit_class": "signal"' in result.stdout
    assert sum(call['operation']=='disable_write' for call in calls) == 1
    assert 'verified_disabled' not in result.stdout + output


def test_guard_conflict_is_before_receipt_and_any_command():
    run = steps()['Quiesce feedback publication before deployment']['run']
    assert run.index('&& "${RECOVER_READINESS_TIMING_00577}" == "true"') < run.index('GITHUB_STEP_SUMMARY')
    assert run.index('ORIGINAL_FEEDBACK_PUBLICATION') < run.index('incident_version=')
    assert run.index('incident_version=') < run.index('az webapp config appsettings set')


def test_completed_body_after_command_deadline_is_still_ambiguous(execute_restoration):
    result, calls, output, _, _ = execute_restoration(plan={
        'restore_write':[{'duration':45.001,'applied':True}]})
    assert result.returncode == 124
    assert '"exit_class": "deadline"' in result.stdout
    assert sum(call['operation']=='disable_write' for call in calls) == 1
    assert 'observation=unknown' in output
    assert 'verified_disabled' not in output + result.stdout


def test_invalid_desired_intent_has_no_mutation(execute_restoration):
    result, calls, output, _, _ = execute_restoration(desired='invalid')
    assert result.returncode != 0 and calls == [] and output == ''
