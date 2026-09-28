"""Execute the actual quiescence shell with local fakes; never call Azure or HTTP."""
from __future__ import annotations

import json
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


def workflow():
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def steps():
    return {step.get('name'):step for job in workflow()['jobs'].values() for step in job['steps'] if 'name' in step}


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
elif name!='sleep':
    raise SystemExit(98)
'''
    for name in ('az','curl','sleep'):
        path=bin_dir/name
        path.write_text(program)
        path.chmod(0o755)

    def run(*, recovery=True, overrides=None, responses=None):
        env=dict(os.environ, PATH=f'{bin_dir}:/usr/bin:/bin',
            FAKE_LOG=str(log), FAKE_COUNTER=str(tmp_path/'counter'),
            FAKE_VERSION=json.dumps({'source_sha':INCIDENT_SHA}), FAKE_VERSION_EXIT='0',
            FAKE_RESPONSES=json.dumps(responses or [{'body':ready_payload()}]),
            RECOVER_DFA_CUTOVER_842='true' if recovery else 'false',
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
    assert stage['timeout-minutes']=="${{ inputs.recover_dfa_cutover_842 == true && 9 || 5 }}"
    assert stage['env']['RECOVER_DFA_CUTOVER_842']=="${{ inputs.recover_dfa_cutover_842 == true && 'true' || 'false' }}"
    assert stage['env']['SYNC_CONFIG']=='${{ steps.mode.outputs.sync_config }}'
    assert stage['env']['CONFIGURED_FEEDBACK_PUBLICATION']=="${{ vars.PRAXYS_ENABLE_FEEDBACK_PUBLICATION || 'false' }}"
    assert '--retry' not in stage['run']
    for name in ['Verify deployed backend cutover','Restore reviewed feedback publication after verified cutover']:
        assert '--max-time 8' in steps()[name]['run']
        assert '--max-time 210' not in steps()[name]['run']
        assert 'RECOVER_DFA_CUTOVER_842' not in steps()[name]['run']
    restore=steps()['Restore reviewed feedback publication after verified cutover']['run']
    assert 'restoration_verified=true' in restore and 'leave_disabled_on_failure' in restore
    assert 'publication_kill' in restore and 'PRAXYS_DISABLE_FEEDBACK_PUBLICATION=' not in restore


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
