"""Fresh STOP source authentication is separate from candidate execution."""
from dataclasses import replace

import pytest

from analysis.science_approval_workflow import verify_science_approval_changes
from analysis.science_implementation_stop import materialize_stop
from analysis.science_stop_github import authenticated_stop_context, fetch_stop_source
from tests.test_science_activation import commit
from tests.test_science_implementation_stop import stop_case, accepted_active_baseline


def test_stop_source_refresh_and_whole_verifier(stop_case, monkeypatch):
    import analysis.science_stop_github as github
    root, base_root, base_sha, stop, comment = stop_case
    materialize_stop(root, stop)
    head_sha = commit(root, 'authenticated stop only')
    permission = 'admin'
    pr = {'number':88,'state':'open','base':{'ref':'main','sha':base_sha,'repo':{'full_name':stop.repository}},
          'head':{'sha':head_sha,'repo':{'full_name':stop.repository}}}
    class Reader:
        repository = stop.repository
        def __init__(self, repository):
            assert repository == stop.repository
        def read(self, path, **kwargs):
            if path == 'issues/comments/77': return comment
            if path == 'collaborators/human/permission': return {'permission':permission}
            if path == 'pulls/88': return pr
            raise AssertionError(path)
    monkeypatch.setattr(github, 'GitHubReader', Reader)
    context = authenticated_stop_context(base_root / 'data/science', root / 'data/science',
                                         repository=stop.repository, pull_request=88)
    verify_science_approval_changes(base_root / 'data/science', root / 'data/science', [], {}, stop_context=context)
    permission = 'read'
    with pytest.raises(ValueError, match='authorized human'):
        context.recheck()
    with pytest.raises(ValueError, match='authorized human'):
        authenticated_stop_context(base_root / 'data/science', root / 'data/science',
                                    repository=stop.repository, pull_request=88)


def test_stop_comment_id_and_bot_substitution_rejected(stop_case):
    _, _, _, stop, comment = stop_case
    class Reader:
        repository = stop.repository
        def read(self, path, **kwargs):
            if path == 'issues/comments/77': return comment
            return {'permission':'admin'}
    reader = Reader()
    assert fetch_stop_source(reader,77) == stop
    comment['id'] = 78
    with pytest.raises(ValueError, match='identity mismatch'):
        fetch_stop_source(reader,77)
    comment['id'] = 77
    comment['user']['type'] = 'Bot'
    with pytest.raises(ValueError, match='human'):
        fetch_stop_source(reader,77)


@pytest.mark.parametrize('mutation', [None, 'failed_job', 'skipped_collector', 'wrong_head',
    'wrong_base', 'wrong_repository', 'wrong_workflow', 'wrong_stop', 'rerun', 'expired',
    'tampered_archive', 'active_candidate'])
def test_authenticated_stopped_maintenance_artifact_admission(stop_case, mutation):
    from hashlib import sha256
    import io
    import json
    import zipfile
    from analysis.science_activation import VALIDATION_JOB, COLLECTOR_JOB, WORKFLOW_PATH, diff_digest
    from analysis.science_stop_github import StopContext, find_denial_evidence
    root, _, _, stop, _ = stop_case
    materialize_stop(root, stop)
    base = commit(root, 'trusted stopped base')
    path = root / 'api/activity_dfa.py'
    path.write_bytes(path.read_bytes()+b'\n# reviewed stopped maintenance\n')
    head = commit(root, 'maintained candidate')
    manifest = dict(schema_version=1, purpose='stopped-maintenance', repository=stop.repository,
        pull_request=88, base_sha=base, reviewed_head_sha=head, diff_digest=diff_digest(root,base,head),
        active_contract_digest=stop.active_contract_digest, subject_id=stop.subject_id,
        stop_digest=stop.stop_digest, candidate_guard_result='denied', workflow_path=WORKFLOW_PATH,
        workflow_sha=base, run_id=5, run_attempt=1, conclusion='success', required_jobs=[VALIDATION_JOB])
    run = dict(id=5,run_attempt=1,head_sha=base,head_branch='main',event='workflow_dispatch',
               path=WORKFLOW_PATH,conclusion='success',repository={'full_name':stop.repository},
               head_repository={'full_name':stop.repository})
    jobs = [{'name':VALIDATION_JOB,'conclusion':'success'}, {'name':COLLECTOR_JOB,'conclusion':'success'}]
    if mutation == 'failed_job': jobs[0]['conclusion'] = 'failure'
    if mutation == 'skipped_collector': jobs[1]['conclusion'] = 'skipped'
    if mutation == 'wrong_head': manifest['reviewed_head_sha'] = '0'*40
    if mutation == 'wrong_base': manifest['base_sha'] = '0'*40
    if mutation == 'wrong_repository': run['repository'] = {'full_name':'other/repository'}
    if mutation == 'wrong_workflow': run['path'] = '.github/workflows/other.yml'
    if mutation == 'wrong_stop': manifest['stop_digest'] = 'sha256:'+'0'*64
    if mutation == 'rerun': run['run_attempt'] = 2
    if mutation == 'active_candidate': manifest['candidate_guard_result'] = 'active'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:
        archive.writestr('validation.json',json.dumps(manifest))
    content = buffer.getvalue()
    artifact = dict(id=6,name=f"science-activation-validation-5-{run['run_attempt']}",
        expired=mutation == 'expired',size_in_bytes=len(content),workflow_run={'id':5,'head_sha':base},
        digest='sha256:'+sha256(content).hexdigest())
    if mutation == 'tampered_archive': artifact['digest'] = 'sha256:'+'0'*64
    class Reader:
        repository = stop.repository
        def read(self,path,**kwargs):
            if path.startswith('actions/workflows/'): return {'workflow_runs':[run]}
            if path == 'actions/artifacts/6/zip': return content
            raise AssertionError(path)
        def pages(self,path,key):
            if path == 'actions/runs/5/artifacts': return [artifact]
            if path == f"actions/runs/5/attempts/{run['run_attempt']}/jobs": return jobs
            raise AssertionError(path)
    def admit():
        verified = find_denial_evidence(Reader(),root,base,head,88,stop)
        context = StopContext(root,stop.repository,88,base,head,(),{stop.subject_id:verified})
        context.require_denial(stop)
    if mutation is None:
        admit()
    else:
        with pytest.raises(ValueError):
            admit()
