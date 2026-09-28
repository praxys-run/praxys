"""Immutable producer binding and the actual stateful two-run deployment shell."""
from copy import deepcopy
from hashlib import sha256
import base64
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

import pytest

from scripts import readiness_quiescence_proof as proof
from tests.test_dfa_recovery_workflow import steps, workflow, ROOT

TARGET = 'a' * 40
RUN = 101
ARTIFACT = 202


def archive_bytes(payload=None, *, members=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        if members is None:
            archive.writestr(proof.MEMBER, json.dumps(payload or proof.expected_proof(TARGET, RUN)))
        else:
            for name, content in members:
                archive.writestr(name, content)
    return stream.getvalue()


def metadata(raw):
    artifact = {'id':ARTIFACT, 'name':f'{proof.ARTIFACT_PREFIX}-{RUN}-1', 'expired':False,
        'size_in_bytes':len(raw), 'digest':'sha256:'+sha256(raw).hexdigest(),
        'workflow_run':{'id':RUN,'head_sha':TARGET}}
    step_values = []
    names = [('Stamp build version','success'), ('Materialize private Stryd client for Oryx','success'),
             ('Capture state preserved by deployment','success'), (proof.QUIESCE,'failure'),
             (proof.UPLOAD,'success'), *[(name,'skipped') for name in proof.POST_QUIESCE]]
    for number, (name, conclusion) in enumerate(names,1):
        step_values.append({'number':number,'name':name,'status':'completed','conclusion':conclusion})
    return {
        'branches/main':{'name':'main','protected':True,'commit':{'sha':TARGET}},
        f'actions/runs/{RUN}':{'id':RUN,'event':'push','head_branch':'main','path':proof.WORKFLOW,
            'head_sha':TARGET,'run_attempt':1,'status':'completed','conclusion':'failure',
            'repository':{'full_name':proof.REPOSITORY},'head_repository':{'full_name':proof.REPOSITORY}},
        f'actions/runs/{RUN}/attempts/1/jobs?per_page=100':{'total_count':1,'jobs':[
            {'name':'deploy','head_sha':TARGET,'status':'completed','conclusion':'failure','steps':step_values}]},
        f'actions/runs/{RUN}/artifacts?per_page=100':{'total_count':1,'artifacts':[deepcopy(artifact)]},
        f'actions/artifacts/{ARTIFACT}':artifact,
    }


class Reader:
    def __init__(self, responses):
        self.responses, self.calls = responses, []
    def read(self, path):
        self.calls.append(path)
        return deepcopy(self.responses[path])


def verify(raw, responses=None, **kwargs):
    return proof.verify_proof(Reader(responses or metadata(raw)), base64.b64encode(raw).decode(),
        producer_run=str(RUN), consumer_run='303', target=TARGET, **kwargs)


def test_original_archive_and_harmless_preparation_are_accepted():
    result = verify(archive_bytes())
    assert result['restore_positive'] is True and result['producer_run_id'] == RUN
    assert result['artifact_id'] == ARTIFACT


@pytest.mark.parametrize('field,value', [('id',999),('event','workflow_dispatch'),('head_branch','other'),
    ('path','.github/workflows/other.yml'),('head_sha','b'*40),('run_attempt',2),('run_attempt',True),
    ('status','in_progress'),('conclusion','success'),('repository',{'full_name':'other/repo'}),
    ('head_repository',{'full_name':'other/repo'})])
def test_wrong_producer_or_rerun_denied(field,value):
    raw=archive_bytes(); responses=metadata(raw)
    responses[f'actions/runs/{RUN}'][field]=value
    with pytest.raises(ValueError):verify(raw,responses)


@pytest.mark.parametrize('field,value', [('id',True),('expired',True),('expired',None),
    ('digest','sha256:'+'0'*64),('size_in_bytes',proof.MAX_ZIP+1),('size_in_bytes',True),
    ('name','other-artifact'),('workflow_run',{'id':999,'head_sha':TARGET}),
    ('workflow_run',{'id':RUN,'head_sha':'b'*40})])
def test_wrong_artifact_denied(field,value):
    raw=archive_bytes(); responses=metadata(raw)
    responses[f'actions/artifacts/{ARTIFACT}'][field]=value
    with pytest.raises(ValueError):verify(raw,responses)


@pytest.mark.parametrize('mutation', ['duplicate_artifact','duplicate_job','duplicate_step','missing_step',
    'quiescence_succeeded','upload_failed','deployment_started','config_started','branch_unprotected','main_changed','truncated_collection'])
def test_ambiguous_or_ineligible_outcome_denied(mutation):
    raw=archive_bytes(); responses=metadata(raw)
    jobs=responses[f'actions/runs/{RUN}/attempts/1/jobs?per_page=100']
    artifact_list=responses[f'actions/runs/{RUN}/artifacts?per_page=100']
    stages=jobs['jobs'][0]['steps']
    if mutation=='duplicate_artifact':artifact_list['artifacts']*=2;artifact_list['total_count']=2
    if mutation=='duplicate_job':jobs['jobs']*=2;jobs['total_count']=2
    if mutation=='duplicate_step':stages.append(deepcopy(stages[3]))
    if mutation=='missing_step':stages.pop()
    if mutation=='quiescence_succeeded':stages[3]['conclusion']='success'
    if mutation=='upload_failed':stages[4]['conclusion']='failure'
    if mutation=='deployment_started':next(s for s in stages if s['name']=='Deploy to App Service')['conclusion']='failure'
    if mutation=='config_started':next(s for s in stages if s['name']=='Sync App Service settings')['conclusion']='success'
    if mutation=='branch_unprotected':responses['branches/main']['protected']=False
    if mutation=='main_changed':responses['branches/main']['commit']['sha']='b'*40
    if mutation=='truncated_collection':artifact_list['total_count']=2
    with pytest.raises(ValueError):verify(raw,responses)


@pytest.mark.parametrize('field,value', [('schema_version',True),('original_positive',False),('configured_positive',False),
    ('disable_acknowledged',False),('readback_positive',True),('protected_main',False),('sync_config',False),
    ('producer_run_id',999),('producer_run_attempt',2),('serving_source_sha','b'*40),('extra','unapproved')])
def test_partial_or_substituted_proof_fields_denied(field,value):
    payload=proof.expected_proof(TARGET,RUN);payload[field]=value
    with pytest.raises(ValueError):verify(archive_bytes(payload))


@pytest.mark.parametrize('layout', ['extra','duplicate','absolute','parent','symlink','oversized','encrypted','duplicate_json'])
def test_unsafe_archive_denied_after_digest_binding(layout):
    content=json.dumps(proof.expected_proof(TARGET,RUN))
    if layout=='extra':raw=archive_bytes(members=[(proof.MEMBER,content),('extra.txt','bad')])
    if layout=='duplicate':raw=archive_bytes(members=[(proof.MEMBER,content),(proof.MEMBER,content)])
    if layout=='absolute':raw=archive_bytes(members=[('/'+proof.MEMBER,content)])
    if layout=='parent':raw=archive_bytes(members=[('../'+proof.MEMBER,content)])
    if layout=='oversized':raw=archive_bytes(members=[(proof.MEMBER,' '* (proof.MAX_PROOF+1))])
    if layout=='duplicate_json':raw=archive_bytes(members=[(proof.MEMBER,content[:-1]+',"original_positive":true}')])
    if layout=='symlink':
        info=zipfile.ZipInfo(proof.MEMBER);info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
        raw=archive_bytes(members=[(info,content)])
    if layout=='encrypted':
        raw=bytearray(archive_bytes())
        start=raw.index(b'PK\x01\x02')
        raw[start+8]|=1;raw[6]|=1
        raw=bytes(raw)
    with pytest.raises((ValueError,zipfile.BadZipFile)):verify(raw)


def test_digest_checked_before_any_zip_parse(monkeypatch):
    raw=archive_bytes();responses=metadata(raw)
    responses[f'actions/artifacts/{ARTIFACT}']['digest']='sha256:'+'0'*64
    responses[f'actions/runs/{RUN}/artifacts?per_page=100']['artifacts'][0]['digest']='sha256:'+'0'*64
    def forbidden(*args):raise AssertionError('unauthenticated archive was parsed')
    monkeypatch.setattr(proof.zipfile,'ZipFile',forbidden)
    with pytest.raises(ValueError):verify(raw,responses)


@pytest.mark.parametrize('encoded', ['bad!', 'YQ==\n', 'YQ=', 'YQ===', 'A'*(proof.MAX_ENCODED+1)])
def test_noncanonical_or_oversized_relay_has_no_metadata_request(encoded):
    reader=Reader({})
    with pytest.raises(ValueError):proof.verify_proof(reader,encoded,producer_run='101',consumer_run='303',target=TARGET)
    assert reader.calls==[]


@pytest.mark.parametrize('change', ['attempt','expiry','main','digest'])
def test_fresh_recheck_denies_new_attempt_or_expiry(change):
    raw=archive_bytes();responses=metadata(raw)
    class Race(Reader):
        def read(self,path):
            value=super().read(path)
            if self.calls.count(path)>1:
                if change=='attempt' and path==f'actions/runs/{RUN}':value['run_attempt']=2
                if change=='expiry' and path==f'actions/artifacts/{ARTIFACT}':value['expired']=True
                if change=='main' and path=='branches/main':value['commit']['sha']='b'*40
                if change=='digest' and path==f'actions/artifacts/{ARTIFACT}':value['digest']='sha256:'+'0'*64
            return value
    with pytest.raises(ValueError):proof.verify_proof(Race(responses),base64.b64encode(raw).decode(),producer_run='101',consumer_run='303',target=TARGET)


def test_receipt_is_not_a_technical_single_use_capability():
    raw=archive_bytes();encoded=base64.b64encode(raw).decode()
    for consumer in ('303','304'):
        assert proof.verify_proof(Reader(metadata(raw)),encoded,producer_run='101',consumer_run=consumer,target=TARGET)['restore_positive'] is True


def test_anonymous_transport_has_no_token_proxy_or_redirect_fallback(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN','secret-token-canary')
    monkeypatch.setenv('GH_TOKEN','secret-other-canary')
    captured=[]
    class Response(io.BytesIO):
        headers={'Content-Length':'2'}
        def getcode(self):return 200
    class Opener:
        def open(self,request,timeout):
            captured.append((request,timeout));return Response(b'{}')
    reader=proof.PublicMetadata();reader.opener=Opener()
    assert reader.read('branches/main')=={}
    request,timeout=captured[0]
    assert request.full_url=='https://api.github.com/repos/praxys-run/praxys/branches/main'
    assert not any(name.lower() in ('authorization','proxy-authorization','cookie') for name,_ in request.header_items())
    assert timeout<=10
    with pytest.raises(ValueError):proof.NoRedirect().redirect_request(request,None,302,'redirect',{},'https://other.example')


@pytest.mark.parametrize('status,length,body', [(403,'2',b'{}'),(429,'2',b'{}'),(206,'2',b'{}'),(200,'9',b'{}'),(200,str(proof.MAX_METADATA+1),b'{}')])
def test_rate_limit_partial_and_oversized_metadata_fail_closed(status,length,body):
    class Response(io.BytesIO):
        headers={'Content-Length':length}
        def getcode(self):return status
    class Opener:
        def open(self,*args,**kwargs):return Response(body)
    reader=proof.PublicMetadata();reader.opener=Opener()
    with pytest.raises(ValueError):reader.read('branches/main')


def test_workflow_transport_is_data_only_and_does_not_grant_actions_read():
    job=workflow()['jobs']['deploy']
    assert job['permissions']=={'id-token':'write','contents':'read'}
    env=steps()[proof.QUIESCE]['env']
    assert env['QUIESCENCE_PROOF_ZIP']=="${{ inputs.quiescence_proof_zip || '' }}"
    run=steps()[proof.QUIESCE]['run']
    assert '${{ inputs.quiescence_proof_zip' not in run
    assert 'GITHUB_TOKEN' not in run and 'GH_TOKEN' not in run
    upload=steps()[proof.UPLOAD]
    assert upload['if']=="always() && github.event_name == 'push' && steps.quiesce.outputs.producer_proof_ready == 'true'"
    assert upload['with']['overwrite']=='false'
    assert upload['with']['if-no-files-found']=='error'
    for name in proof.POST_QUIESCE:assert name in steps()


@pytest.fixture
def two_run(tmp_path):
    """One shared fake cloud; real capture/quiescence/helper/restoration programs."""
    bin_dir=tmp_path/'bin';bin_dir.mkdir()
    state=tmp_path/'cloud.json';calls=tmp_path/'calls.jsonl';responses=tmp_path/'metadata.json'
    state.write_text(json.dumps({'positive':True,'kill':False,'source':proof.SERVING_SOURCE}))
    commands=f'#!{sys.executable}\n'+r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:];name=Path(sys.argv[0]).name
path=Path(os.environ['FAKE_STATE']);state=json.loads(path.read_text())
operation=name
if name=='az':operation='set' if args[:4]==['webapp','config','appsettings','set'] else 'list' if args[:4]==['webapp','config','appsettings','list'] else 'cors'
elif name=='curl':operation='version' if args[-1].endswith('/api/version') else 'ready'
with Path(os.environ['FAKE_CALLS']).open('a') as stream:stream.write(json.dumps({'run':os.environ['GITHUB_RUN_ID'],'operation':operation,'args':args})+'\n')
if operation=='set':
    state['positive']=next(value.split('=',1)[1] for value in args if value.startswith('PRAXYS_ENABLE_FEEDBACK_PUBLICATION='))=='true'
    path.write_text(json.dumps(state))
    raise SystemExit(int(os.environ.get('FAKE_DISABLE_EXIT','0')))
if operation=='list':
    values={'PRAXYS_ENABLE_FEEDBACK_PUBLICATION':str(state['positive']).lower(),
       'PRAXYS_DISABLE_FEEDBACK_PUBLICATION':str(state['kill']).lower(),
       'PRAXYS_DISABLE_CN_PROCESSING':'false','PRAXYS_DISABLE_MINIAPP_PROCESSING':'false',
       'PRAXYS_DISABLE_BACKGROUND_AI':'false','PRIVATE_VALUE':'secret-settings-canary'}
    print(json.dumps([{'name':key,'value':value} for key,value in values.items()]))
elif operation=='cors':print('[]')
elif operation=='version':
    print(json.dumps({'version':'synthetic-version','source_sha':state['source']}))
    raise SystemExit(int(os.environ.get('FAKE_VERSION_EXIT','0')))
elif operation=='ready':
    if os.environ.get('FAKE_READY_FAIL')=='true':raise SystemExit(28)
    print(json.dumps({'status':'ready','optional_processing':{
       'feedback_publication_positive_enable':state['positive'],
       'feedback_publication_kill_switch':state['kill'],
       'feedback_publication_enabled':state['positive'] and not state['kill']}}))
'''
    for name in ('az','curl','sleep'):
        path=bin_dir/name;path.write_text(commands);path.chmod(0o755)
    python=f'#!{sys.executable}\n'+r'''
import importlib.util,json,os,sys
from pathlib import Path
if sys.argv[1:]==['-']:
    exec(compile(sys.stdin.read(),'<actual-restoration-controller>','exec'),{'__name__':'__main__'})
else:
    spec=importlib.util.spec_from_file_location('proof_under_test',sys.argv[1])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Metadata:
        def read(self,path):return json.loads(Path(os.environ['FAKE_METADATA']).read_text())[path]
    module.PublicMetadata=Metadata
    sys.argv=sys.argv[1:]
    raise SystemExit(module.main())
'''
    path=bin_dir/'python3';path.write_text(python);path.chmod(0o755)
    common=dict(os.environ,PATH=f'{bin_dir}:/usr/bin:/bin',FAKE_STATE=str(state),FAKE_CALLS=str(calls),
        FAKE_METADATA=str(responses),GITHUB_REPOSITORY=proof.REPOSITORY,GITHUB_SHA=TARGET,
        GITHUB_REF='refs/heads/main',GITHUB_REF_PROTECTED='true',GITHUB_RUN_ATTEMPT='1',
        GITHUB_WORKSPACE=str(ROOT),SYNC_CONFIG='true',CONFIGURED_FEEDBACK_PUBLICATION='true',
        AZURE_BACKEND_APP_NAME='synthetic',AZURE_RESOURCE_GROUP='synthetic',
        RECOVER_DFA_CUTOVER_842='false',RECOVER_READINESS_TIMING_00577='false',
        QUIESCENCE_PRODUCER_RUN='',QUIESCENCE_PROOF_ZIP='',
        PRAXYS_EXPECTED_API_SOURCE_SHA=TARGET,PRAXYS_EXPECTED_API_VERSION='synthetic-version')
    transcripts=[]
    def execute(name,env):
        result=subprocess.run(['bash','-c',steps()[name]['run']],env=env,cwd=tmp_path,
                              capture_output=True,text=True,timeout=20)
        transcripts.append(result.stdout+result.stderr)
        return result
    def context(run,event):
        directory=tmp_path/str(run);directory.mkdir(exist_ok=True)
        return dict(common,GITHUB_RUN_ID=str(run),GITHUB_EVENT_NAME=event,RUNNER_TEMP=str(directory),
                    GITHUB_OUTPUT=str(directory/'capture-output'),GITHUB_STEP_SUMMARY=str(directory/'summary'))
    def capture(env):
        result=execute('Capture state preserved by deployment',env)
        assert result.returncode==0,result.stderr
        values=dict(line.split('=',1) for line in Path(env['GITHUB_OUTPUT']).read_text().splitlines())
        return dict(env,ORIGINAL_FEEDBACK_PUBLICATION=values['feedback_publication_original'],
                    GITHUB_OUTPUT=str(Path(env['RUNNER_TEMP'])/'quiesce-output'))
    def produce(**overrides):
        env=context(RUN,'push');env.update(overrides)
        env=capture(env);env['FAKE_READY_FAIL']='true'
        result=execute(proof.QUIESCE,env)
        assert result.returncode!=0
        return env,Path(env['RUNNER_TEMP'])/proof.MEMBER
    def bundle(path):
        raw=archive_bytes(members=[(proof.MEMBER,path.read_bytes())])
        responses.write_text(json.dumps(metadata(raw)))
        return base64.b64encode(raw).decode()
    def consumer(encoded,**overrides):
        env=capture(context(303,'workflow_dispatch'))
        env.update(RECOVER_READINESS_TIMING_00577='true',QUIESCENCE_PRODUCER_RUN=str(RUN),QUIESCENCE_PROOF_ZIP=encoded)
        env.update(overrides)
        return env
    return dict(execute=execute,produce=produce,bundle=bundle,consumer=consumer,state=state,calls=calls,
                responses=responses,transcripts=transcripts)


@pytest.mark.parametrize('kill', [False,True])
def test_stateful_automatic_failure_then_authenticated_diagnostic_restores_historical_intent(two_run,kill):
    system=two_run
    producer,path=system['produce']()
    payload=json.loads(path.read_text())
    assert payload==proof.expected_proof(TARGET,RUN)
    assert 'producer_proof_ready=true' in Path(producer['GITHUB_OUTPUT']).read_text()
    cloud=json.loads(system['state'].read_text());assert cloud['positive'] is False
    cloud['kill']=kill;system['state'].write_text(json.dumps(cloud))
    env=system['consumer'](system['bundle'](path))
    assert env['ORIGINAL_FEEDBACK_PUBLICATION']=='false'
    result=system['execute'](proof.QUIESCE,env)
    assert result.returncode==0,result.stderr
    outputs=dict(line.split('=',1) for line in Path(env['GITHUB_OUTPUT']).read_text().splitlines())
    assert outputs['recovery_restore']=='true'
    # Simulate package cutover only after admitted quiescence. The actual
    # restoration shell then uses the proof's target and the CURRENT kill switch.
    cloud=json.loads(system['state'].read_text());cloud['source']=TARGET
    system['state'].write_text(json.dumps(cloud))
    env.update(DESIRED_FEEDBACK_PUBLICATION=outputs['recovery_restore'],
               GITHUB_OUTPUT=str(Path(env['RUNNER_TEMP'])/'restoration-output'))
    restored=system['execute']('Restore reviewed feedback publication after verified cutover',env)
    assert restored.returncode==0,restored.stdout+restored.stderr
    restored_outputs=Path(env['GITHUB_OUTPUT']).read_text()
    assert f'positive=true\nkill_switch={str(kill).lower()}\nenabled={str(not kill).lower()}\n' in restored_outputs
    calls=[json.loads(line) for line in system['calls'].read_text().splitlines()]
    ready=[call for call in calls if call['operation']=='ready']
    assert ready[0]['args'][ready[0]['args'].index('--max-time')+1]=='8'
    assert any(call['run']=='303' and '210' in call['args'] for call in ready)
    assert ready[-1]['args'][ready[-1]['args'].index('--max-time')+1]=='8'
    assert 'secret-settings-canary' not in ''.join(system['transcripts'])
    assert env['QUIESCENCE_PROOF_ZIP'] not in ''.join(system['transcripts'])


@pytest.mark.parametrize('mutation', ['missing_zip','bad_digest','wrong_run','wrong_target','rerun',
    'expired','missing_artifact','current_positive_changed','source_changed'])
def test_two_run_bad_evidence_or_changed_current_state_never_mutates(two_run,mutation):
    system=two_run;_,path=system['produce']();encoded=system['bundle'](path)
    env=system['consumer'](encoded)
    if mutation=='missing_zip':env['QUIESCENCE_PROOF_ZIP']=''
    if mutation=='bad_digest':env['QUIESCENCE_PROOF_ZIP']=base64.b64encode(archive_bytes({'forged':True})).decode()
    if mutation=='wrong_run':env['QUIESCENCE_PRODUCER_RUN']='999'
    if mutation=='wrong_target':env['GITHUB_SHA']='b'*40
    if mutation in ('rerun','expired','missing_artifact'):
        responses=json.loads(system['responses'].read_text())
        if mutation=='rerun':responses[f'actions/runs/{RUN}']['run_attempt']=2
        if mutation=='expired':responses[f'actions/artifacts/{ARTIFACT}']['expired']=True
        if mutation=='missing_artifact':responses[f'actions/runs/{RUN}/artifacts?per_page=100']={'total_count':0,'artifacts':[]}
        system['responses'].write_text(json.dumps(responses))
    if mutation in ('current_positive_changed','source_changed'):
        cloud=json.loads(system['state'].read_text())
        if mutation=='current_positive_changed':cloud['positive']=True
        else:cloud['source']='b'*40
        system['state'].write_text(json.dumps(cloud))
    result=system['execute'](proof.QUIESCE,env)
    assert result.returncode!=0
    calls=[json.loads(line) for line in system['calls'].read_text().splitlines()]
    assert not any(call['run']=='303' and call['operation']=='set' for call in calls)


@pytest.mark.parametrize('override', [
    {'FAKE_DISABLE_EXIT':'1'}, {'FAKE_VERSION_EXIT':'28'},
    {'CONFIGURED_FEEDBACK_PUBLICATION':'false'}, {'GITHUB_RUN_ATTEMPT':'2'},
    {'GITHUB_REF_PROTECTED':'false'},
])
def test_unacknowledged_or_ineligible_producer_never_creates_proof(two_run,override):
    _,path=two_run['produce'](**override)
    assert not path.exists()


@pytest.mark.parametrize('path', ['../other/repo','https://other.example','actions/artifacts/202/zip',
    'branches/other','actions/runs/101?other=1','/branches/main'])
def test_metadata_client_cannot_become_a_general_downloader(path):
    with pytest.raises(ValueError):proof.PublicMetadata().read(path)


def test_create_requires_complete_acknowledgement_and_never_overwrites(tmp_path):
    env=dict(GITHUB_REPOSITORY=proof.REPOSITORY,GITHUB_EVENT_NAME='push',GITHUB_REF='refs/heads/main',
        GITHUB_REF_PROTECTED='true',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_ID='101',GITHUB_SHA=TARGET,
        SYNC_CONFIG='true',ORIGINAL_FEEDBACK_PUBLICATION='true',CONFIGURED_FEEDBACK_PUBLICATION='true',
        DISABLE_ACKNOWLEDGED='true',READBACK_POSITIVE='false',PRODUCER_SOURCE_SHA=proof.SERVING_SOURCE,
        RUNNER_TEMP=str(tmp_path))
    for missing in ('DISABLE_ACKNOWLEDGED','READBACK_POSITIVE','PRODUCER_SOURCE_SHA'):
        changed=dict(env);changed.pop(missing)
        with pytest.raises(ValueError):proof.create_proof(changed)
        assert not (tmp_path/proof.MEMBER).exists()
    path=proof.create_proof(env)
    before=path.read_bytes()
    with pytest.raises(FileExistsError):proof.create_proof(env)
    assert path.read_bytes()==before


def test_cli_failure_is_sanitized_and_never_uses_privileged_fallback(monkeypatch,capsys):
    monkeypatch.setenv('GITHUB_REPOSITORY',proof.REPOSITORY)
    monkeypatch.setenv('GITHUB_SHA',TARGET)
    monkeypatch.setenv('GITHUB_RUN_ID','303')
    monkeypatch.setenv('QUIESCENCE_PRODUCER_RUN','101')
    monkeypatch.setenv('QUIESCENCE_PROOF_ZIP',base64.b64encode(archive_bytes()).decode())
    monkeypatch.setenv('GITHUB_TOKEN','secret-token-canary')
    monkeypatch.setattr(sys,'argv',['proof.py','verify'])
    class Unavailable:
        def read(self,path):raise RuntimeError('secret-provider-error-canary')
    monkeypatch.setattr(proof,'PublicMetadata',Unavailable)
    assert proof.main()==1
    captured=capsys.readouterr()
    assert captured.out=='' and 'secret-' not in captured.err
    assert 'no credential fallback' in captured.err
