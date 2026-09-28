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
    'tampered_archive', 'active_candidate', 'missing_probe', 'failed_probe', 'skipped_probe', 'duplicate_probe', 'missing_probe_manifest'])
def test_authenticated_stopped_maintenance_artifact_admission(stop_case, mutation):
    from hashlib import sha256
    import io
    import json
    import zipfile
    from analysis.science_activation import VALIDATION_JOB, PROBE_JOB, COLLECTOR_JOB, WORKFLOW_PATH, diff_digest
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
        workflow_sha=base, run_id=5, run_attempt=1, conclusion='success', required_jobs=[VALIDATION_JOB, PROBE_JOB])
    run = dict(id=5,run_attempt=1,head_sha=base,head_branch='main',event='workflow_dispatch',
               path=WORKFLOW_PATH,conclusion='success',repository={'full_name':stop.repository},
               head_repository={'full_name':stop.repository})
    jobs = [{'name':VALIDATION_JOB,'conclusion':'success'}, {'name':PROBE_JOB,'conclusion':'success'}, {'name':COLLECTOR_JOB,'conclusion':'success'}]
    if mutation == 'failed_job': jobs[0]['conclusion'] = 'failure'
    if mutation == 'skipped_collector': jobs[2]['conclusion'] = 'skipped'
    if mutation == 'missing_probe': jobs.pop(1)
    if mutation == 'failed_probe': jobs[1]['conclusion'] = 'failure'
    if mutation == 'skipped_probe': jobs[1]['conclusion'] = 'skipped'
    if mutation == 'duplicate_probe': jobs.append(dict(jobs[1]))
    if mutation == 'missing_probe_manifest': manifest['required_jobs'] = [VALIDATION_JOB]
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


@pytest.mark.parametrize('relative', ['implementation.yaml', 'implementation.yml',
                                      'archive/nested/implementation.yaml', 'archive/nested/implementation.yml'])
@pytest.mark.parametrize('mutation', ['bytes', 'remove', 'relocate', 'executable'])
def test_whole_verifier_preserves_every_loaded_approval_path_after_stop(stop_case, relative, mutation, tmp_path):
    """Exercise the public verifier, including historically valid nested/YML layouts."""
    import shutil
    from analysis.evidence_registry import _yaml_paths
    from analysis.science_artifacts import ReviewRole
    from analysis.science_stop_github import StopContext
    from analysis.science_yaml import load_science_yaml
    root, _, _, stop, _ = stop_case
    science = root / 'data/science'
    original = next(path for path in _yaml_paths(science / 'approvals')
                    if load_science_yaml(path.read_text())['role'] == ReviewRole.IMPLEMENTATION_REVIEWER.value)
    historical = science / 'approvals' / relative
    historical.parent.mkdir(parents=True, exist_ok=True)
    original.rename(historical)
    active_sha = commit(root, 'valid historical approval layout')
    active = tmp_path / 'active-layout'
    shutil.copytree(root, active)
    materialize_stop(root, stop)
    stopped_sha = commit(root, 'authorized stop preserving historical layout')
    stop_context = StopContext(root, stop.repository, 88, active_sha, stopped_sha, (stop,), {})
    verify_science_approval_changes(active / 'data/science', science, [], {}, stop_context=stop_context)
    baseline = tmp_path / 'stopped-layout'
    shutil.copytree(root, baseline)
    context = StopContext(root, stop.repository, 89, stopped_sha, stopped_sha, (), {})
    verify_science_approval_changes(baseline / 'data/science', science, [], {}, stop_context=context)
    if mutation == 'bytes':
        historical.write_bytes(historical.read_bytes() + b'\n# semantic no-op, forbidden history change\n')
    elif mutation == 'remove':
        historical.unlink()
    elif mutation == 'relocate':
        historical.rename(historical.with_name('moved' + historical.suffix))
    else:
        historical.chmod(historical.stat().st_mode | 0o111)
    # Removal may be rejected by registry validation before the history check.
    with pytest.raises(ValueError):
        verify_science_approval_changes(baseline / 'data/science', science, [], {}, stop_context=context)


def test_fresh_policy_probe_ignores_candidate_regression_workspace_and_environment(stop_case, tmp_path):
    """Run a hostile regression, then the workflow's actual probe on fresh checkouts.

    The workflow assertions bind the local hosted-job simulation to the checked-in
    job boundary. This is synthetic isolation evidence, not a live Actions run.
    """
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import yaml
    from analysis.science_activation import PROBE_JOB, VALIDATION_JOB, git
    root, _, _, stop, _ = stop_case
    materialize_stop(root, stop)
    revision = commit(root, 'frozen stopped probe candidate')
    workflow = yaml.safe_load((root / '.github/workflows/science-activation-validation.yml').read_text())
    jobs = workflow['jobs']
    assert jobs['validate']['name'] == VALIDATION_JOB
    assert jobs['probe']['name'] == PROBE_JOB
    assert set(jobs['collect']['needs']) == {'validate', 'probe'}
    assert jobs['probe']['runs-on'] == 'ubuntu-latest'
    assert not {'needs', 'container', 'services', 'env', 'outputs'} & jobs['probe'].keys()
    steps = jobs['probe']['steps']
    assert [step.get('uses') for step in steps if 'uses' in step] == [
        'actions/checkout@v7', 'actions/checkout@v7', 'actions/setup-python@v7']
    assert [(step['with']['path'], step['with']['ref'], step['with']['persist-credentials'])
            for step in steps if step.get('uses') == 'actions/checkout@v7'] == [
        ('trusted', '${{ github.sha }}', False), ('candidate', '${{ inputs.candidate_sha }}', False)]
    assert next(step for step in steps if step.get('uses') == 'actions/setup-python@v7')['with'] == {'python-version':'3.12'}
    assert [step['run'] for step in steps if 'run' in step] == [
        'pip install -r trusted/requirements.txt',
        'python trusted/scripts/run_science_policy_probe.py']
    assert not any('check_stopped_dfa_policy.py' in step.get('run', '')
                   or 'check_projected_dfa_policy.py' in step.get('run', '')
                   for step in jobs['validate']['steps'])
    selected = next(step for step in steps if step.get('run') == 'python trusted/scripts/run_science_policy_probe.py')

    def fresh_job(name):
        workspace = tmp_path / name
        workspace.mkdir()
        for checkout in ('trusted', 'candidate'):
            subprocess.run(['git', 'clone', '-q', '--no-hardlinks', str(root), str(workspace / checkout)], check=True)
            git(workspace / checkout, 'checkout', '--detach', revision)
        # Hosted jobs do not transfer GITHUB_ENV/GITHUB_PATH from other jobs.
        environment = dict(os.environ, CANDIDATE_ROOT=str(workspace / 'candidate'),
                           ACTIVATION_SUBJECT=stop.subject_id, ACTIVATION_CONTRACT=stop.active_contract_digest,
                           PROBE_PURPOSE='stopped-maintenance',
                           PYTHONDONTWRITEBYTECODE='1', GITHUB_ENV=str(workspace / 'github-env'),
                           GITHUB_PATH=str(workspace / 'github-path'))
        return workspace, environment

    regression, regression_env = fresh_job('regression-runner')
    attack = regression / 'candidate/test_poison.py'
    attack.write_text('''from pathlib import Path
import os

def test_mutate_regression_runner():
    Path('../trusted/scripts/observe_science_policy.py').write_text("raise RuntimeError('regression contaminated probe')\\n")
    Path('api/activity_dfa.py').write_text("raise RuntimeError('regression contaminated candidate')\\n")
    Path(os.environ['GITHUB_ENV']).write_text('CANDIDATE_ROOT=/poisoned\\nPYTHONPATH=/poisoned\\n')
    Path(os.environ['GITHUB_PATH']).write_text('/poisoned/bin\\n')
''')
    subprocess.run([sys.executable, '-m', 'pytest', '-q', str(attack)],
                   cwd=regression / 'candidate', env=regression_env, check=True, capture_output=True, text=True)
    command = [sys.executable, *selected['run'].split()[1:]]
    contaminated = subprocess.run(command, cwd=regression, env=regression_env, capture_output=True, text=True)
    assert contaminated.returncode != 0 and 'Policy observer did not complete successfully' in contaminated.stderr
    assert '/poisoned' in Path(regression_env['GITHUB_ENV']).read_text()
    probe, probe_env = fresh_job('probe-runner')
    assert not Path(probe_env['GITHUB_ENV']).exists() and not Path(probe_env['GITHUB_PATH']).exists()
    assert git(probe / 'candidate', 'status', '--porcelain') == b''
    clean = subprocess.run(command, cwd=probe, env=probe_env, capture_output=True, text=True)
    assert clean.returncode == 0, clean.stderr
    assert json.loads(clean.stdout)['controller_completed'] is True
    assert json.loads(clean.stdout)['observation']['http_status'] == 503
