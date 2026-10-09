"""Authenticated validation producers reject stale, substituted or failed evidence."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from urllib.request import Request
import zipfile

import pytest

from analysis.science_activation import COLLECTOR_JOB, VALIDATION_JOB, PROBE_JOB, WORKFLOW_PATH
from analysis.science_activation_github import _NoCredentialRedirect, fetch_validation, verify_pr
from tests.test_science_activation import activation


@pytest.fixture
def github_evidence(activation):
    root, _, _, context, binding, _, _ = activation
    manifest = context.validations[binding.envelope_digest]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('validation.json', json.dumps(manifest))
    content = buffer.getvalue()
    responses = {
        'actions/runs/5': {'repository':{'full_name':binding.repository},
                          'head_repository':{'full_name':binding.repository},
                          'event':'workflow_dispatch', 'head_branch':'main', 'path':WORKFLOW_PATH,
                          'head_sha':binding.validation_workflow_sha, 'run_attempt':1, 'conclusion':'success'},
        'actions/artifacts/6': {'name':'science-activation-validation-5-1', 'expired':False,
                                'workflow_run':{'id':5,'head_sha':binding.validation_workflow_sha},
                                'size_in_bytes':len(content), 'digest':'sha256:'+sha256(content).hexdigest()},
        'actions/artifacts/6/zip': content,
        'jobs':[{'name':VALIDATION_JOB,'conclusion':'success'}, {'name':PROBE_JOB,'conclusion':'success'}, {'name':COLLECTOR_JOB,'conclusion':'success'}],
    }
    class Reader:
        def read(self, path, **kwargs):
            return responses[path]
        def pages(self, path, key):
            assert path == 'actions/runs/5/attempts/1/jobs' and key == 'jobs'
            return responses['jobs']
    return root, binding, manifest, responses, Reader()


def test_authenticated_validation_round_trip(github_evidence):
    root, binding, manifest, _, reader = github_evidence
    assert fetch_validation(reader, binding, root) == manifest


@pytest.mark.parametrize('field,value', [('event','pull_request'), ('head_branch','candidate'),
    ('head_sha','0'*40), ('run_attempt',2), ('conclusion','failure'), ('path','.github/workflows/other.yml')])
def test_wrong_or_rerun_producer_rejected(github_evidence, field, value):
    root, binding, _, responses, reader = github_evidence
    responses['actions/runs/5'][field] = value
    with pytest.raises(ValueError, match='workflow identity'):
        fetch_validation(reader, binding, root)


@pytest.mark.parametrize('job_index', [0, 1, 2])
@pytest.mark.parametrize('conclusion', ['failure','cancelled','skipped',None])
def test_unsuccessful_required_job_rejected(github_evidence, job_index, conclusion):
    root, binding, _, responses, reader = github_evidence
    responses['jobs'][job_index]['conclusion'] = conclusion
    with pytest.raises(ValueError, match='required job'):
        fetch_validation(reader, binding, root)


@pytest.mark.parametrize('field,value', [('expired',True), ('name','candidate-output'),
    ('workflow_run',{'id':99}), ('digest','sha256:'+'0'*64)])
def test_artifact_substitution_rejected(github_evidence, field, value):
    root, binding, _, responses, reader = github_evidence
    responses['actions/artifacts/6'][field] = value
    with pytest.raises(ValueError, match='artifact'):
        fetch_validation(reader, binding, root)


def test_cross_host_artifact_redirect_strips_authorization():
    request = Request('https://api.github.com/example', headers={'Authorization':'Bearer synthetic'})
    redirected = _NoCredentialRedirect().redirect_request(request, None, 302, 'redirect', {},
                                                           'https://example.blob.core.windows.net/artifact')
    assert redirected.get_header('Authorization') is None
    with pytest.raises(ValueError, match='HTTPS'):
        _NoCredentialRedirect().redirect_request(request, None, 302, 'redirect', {}, 'http://example/artifact')


def test_pr_head_base_repository_races_rejected():
    pr = {'number':42,'state':'open','base':{'ref':'main','sha':'base','repo':{'full_name':'praxys-run/praxys'}},
          'head':{'sha':'head','repo':{'full_name':'praxys-run/praxys'}}}
    verify_pr(pr, 'praxys-run/praxys', 42, 'base', 'head')
    for side, key, value in [('head','sha','other'),('base','sha','other'),('head','repo',{'full_name':'fork/repo'})]:
        changed = deepcopy(pr)
        changed[side][key] = value
        with pytest.raises(ValueError, match='changed'):
            verify_pr(changed, 'praxys-run/praxys', 42, 'base', 'head')


@pytest.mark.parametrize('mutation', ['missing', 'duplicate'])
def test_probe_must_have_one_authenticated_job_result(github_evidence, mutation):
    root, binding, _, responses, reader = github_evidence
    if mutation == 'missing':
        responses['jobs'].pop(1)
    else:
        responses['jobs'].append(dict(responses['jobs'][1]))
    with pytest.raises(ValueError, match='required job'):
        fetch_validation(reader, binding, root)


@pytest.mark.parametrize('probe_result', ['success', 'failure', 'skipped', 'missing'])
def test_collector_requires_distinct_probe_before_emitting_manifest(activation, monkeypatch, tmp_path, probe_result):
    from scripts import collect_science_activation_validation as collector
    root, _, _, _, binding, _, subject = activation
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({'inputs':dict(candidate_sha=binding.reviewed_head_sha,
        pull_request=str(binding.pull_request), subject_id=subject,
        active_contract_digest=binding.active_contract_digest, purpose='activation')}))
    output = tmp_path / 'validation.json'
    pr = {'number':binding.pull_request,'state':'open',
          'base':{'ref':'main','sha':binding.base_sha,'repo':{'full_name':binding.repository}},
          'head':{'sha':binding.reviewed_head_sha,'repo':{'full_name':binding.repository}}}
    jobs = [{'name':VALIDATION_JOB, 'conclusion':'success'}]
    if probe_result != 'missing':
        jobs.append({'name':PROBE_JOB, 'conclusion':probe_result})
    class Reader:
        def __init__(self, repository):
            assert repository == binding.repository
        def read(self, path):
            assert path == f'pulls/{binding.pull_request}'
            return pr
        def pages(self, path, key):
            assert path == 'actions/runs/5/attempts/1/jobs' and key == 'jobs'
            return jobs
    monkeypatch.setattr(collector, 'GitHubReader', Reader)
    monkeypatch.setattr('sys.argv', ['collector', '--candidate', str(root), '--output', str(output)])
    for key, value in dict(GITHUB_REPOSITORY=binding.repository, GITHUB_EVENT_PATH=str(event),
                           GITHUB_SHA=binding.base_sha, GITHUB_RUN_ID='5', GITHUB_RUN_ATTEMPT='1').items():
        monkeypatch.setenv(key, value)
    if probe_result == 'success':
        collector.main()
        assert json.loads(output.read_text())['required_jobs'] == [VALIDATION_JOB, PROBE_JOB]
    else:
        with pytest.raises(ValueError, match='required job'):
            collector.main()
        assert not output.exists()


@pytest.fixture
def designated_github_evidence(tmp_path):
    from tests.test_science_activation import designated_case
    from hashlib import sha256
    import io, zipfile
    root, science, context, binding, _ = designated_case(tmp_path)
    manifest = context.validations[binding.envelope_digest]
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes,'w') as archive:
        archive.writestr('validation.json',json.dumps(manifest))
    content=archive_bytes.getvalue()
    run=dict(id=5, repository={'full_name':binding.repository}, head_repository={'full_name':binding.repository},
        event='workflow_dispatch', head_branch='main', path=WORKFLOW_PATH, head_sha=binding.validation_workflow_sha,
        run_attempt=1, conclusion='success')
    artifact=dict(id=6,name='science-activation-validation-5-1', expired=False,
        workflow_run={'id':5,'head_sha':binding.validation_workflow_sha},
        size_in_bytes=len(content),digest='sha256:'+sha256(content).hexdigest())
    jobs=[dict(id=i+20,run_id=5,status='completed',name=name,conclusion='success')
          for i,name in enumerate([VALIDATION_JOB,PROBE_JOB,COLLECTOR_JOB])]
    responses={'actions/runs/5':run, 'actions/artifacts/6':artifact,'actions/artifacts/6/zip':content,'jobs':jobs}
    class Reader:
        def read(self,path,**kwargs): return responses[path]
        def pages(self,path,key):
            assert path=='actions/runs/5/attempts/1/jobs' and key=='jobs'
            return jobs
    return root, science, context, binding, manifest, responses, Reader()


def test_designated_authenticated_artifact_roundtrip(designated_github_evidence):
    from analysis.evidence_registry import load_science_registry
    root, science, context, binding, manifest, _, reader = designated_github_evidence
    validation = fetch_validation(reader,binding,root)
    assert validation==manifest
    context.verify(binding,load_science_registry(science),manifest['subject_id'])


@pytest.mark.parametrize('target,field,value', [
    ('run','id',5.0),('run','run_attempt',True),('run','run_attempt','1'),
    ('artifact','id',6.0),('artifact-run','id',5.0),('artifact-run','head_sha','0'*40),
    ('job','id',20.0),('job','run_id',5.0),('job','run_id','5'),('job','status','in_progress')])
def test_designated_exact_provider_scalar_identity_rejections(designated_github_evidence,target,field,value):
    root,_,_,binding,_,responses,reader=designated_github_evidence
    objects={'run':responses['actions/runs/5'],'artifact':responses['actions/artifacts/6'],
             'artifact-run':responses['actions/artifacts/6']['workflow_run'],'job':responses['jobs'][0]}
    objects[target][field]=value
    with pytest.raises(ValueError): fetch_validation(reader,binding,root)


@pytest.mark.parametrize('field,value', [('subject_id','sdr-activity-dfa-alpha1-v1'),('schema_version',True),
    ('base_sha','0'*40),('reviewed_head_sha','1'*40),('diff_digest','sha256:'+'0'*64),
    ('purpose','activation'),('baseline_guard_result','synthetic-denial'),('run_id',True),('run_attempt',1.0),
    ('workflow_sha','0'*40),('required_jobs',[VALIDATION_JOB])])
def test_designated_stale_or_swapped_proof_rejections(designated_github_evidence,field,value):
    from dataclasses import replace
    from analysis.evidence_registry import load_science_registry
    from analysis.science_artifacts import digest_payload
    root,science,context,binding,manifest,_,_=designated_github_evidence
    changed=dict(manifest);changed[field]=value
    replacement=binding.model_copy(update={'validation_digest':digest_payload(changed)})
    context=replace(context,validations={replacement.envelope_digest:changed})
    with pytest.raises((ValueError,__import__('subprocess').CalledProcessError)):
        context.verify(replacement,load_science_registry(science),'sdr-activity-dfa-alpha1-v2')


@pytest.mark.parametrize('probe_result',['success','skipped','missing'])
def test_designated_trusted_third_collector_reads_only_static_candidate(tmp_path,monkeypatch,probe_result):
    from tests.test_science_activation import designated_case
    from scripts import collect_science_activation_validation as collector
    root,science,context,binding,_=designated_case(tmp_path)
    event=tmp_path/'event.json';output=tmp_path/'validation.json'
    inputs=dict(purpose='dfa-v2-activation',candidate_sha=context.head_sha,pull_request='42',
                subject_id='sdr-activity-dfa-alpha1-v2',active_contract_digest=binding.active_contract_digest)
    event.write_text(json.dumps({'inputs':inputs}))
    for name,value in {'GITHUB_REPOSITORY':context.repository,'GITHUB_EVENT_PATH':str(event),'GITHUB_SHA':context.base_sha,
                       'GITHUB_RUN_ID':'5','GITHUB_RUN_ATTEMPT':'1'}.items(): monkeypatch.setenv(name,value)
    pr={'number':42,'state':'open','base':{'ref':'main','repo':{'full_name':context.repository},'sha':context.base_sha},
        'head':{'repo':{'full_name':context.repository},'sha':context.head_sha}}
    jobs=[dict(name=VALIDATION_JOB,conclusion='success',id=20,run_id=5,status='completed')]
    if probe_result!='missing': jobs.append(dict(name=PROBE_JOB,conclusion=probe_result,id=21,run_id=5,status='completed'))
    class Reader:
        def __init__(self,repository): pass
        def read(self,path):
            assert path=='pulls/42'
            return pr
        def pages(self,path,key): return jobs
    monkeypatch.setattr(collector,'GitHubReader',Reader)
    monkeypatch.setattr(__import__('sys'),'argv',['collector','--candidate',str(root),'--output',str(output)])
    # Malicious candidate executables cannot run in this trusted process.
    (root/'api/activity_dfa.py').write_text("raise RuntimeError('candidate must never execute in collector')\n")
    from tests.test_science_activation import commit
    new_head = commit(root, 'synthetic untrusted module at exact reviewed head')
    inputs['candidate_sha'] = new_head
    event.write_text(json.dumps({'inputs':inputs}))
    pr['head']['sha'] = new_head
    if probe_result=='success':
        collector.main()
        payload=json.loads(output.read_text())
        assert payload['schema_version']==2 and payload['baseline_guard_result']=='denied'
    else:
        with pytest.raises(ValueError,match='required job'): collector.main()
        assert not output.exists()
