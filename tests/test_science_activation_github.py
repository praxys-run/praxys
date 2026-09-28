"""Authenticated validation producers reject stale, substituted or failed evidence."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from urllib.request import Request
import zipfile

import pytest

from analysis.science_activation import COLLECTOR_JOB, VALIDATION_JOB, WORKFLOW_PATH
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
        'jobs':[{'name':VALIDATION_JOB,'conclusion':'success'}, {'name':COLLECTOR_JOB,'conclusion':'success'}],
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


@pytest.mark.parametrize('conclusion', ['failure','cancelled','skipped',None])
def test_unsuccessful_required_job_rejected(github_evidence, conclusion):
    root, binding, _, responses, reader = github_evidence
    responses['jobs'][0]['conclusion'] = conclusion
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
