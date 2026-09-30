"""Completion/provenance evidence, not semantic isolation of malicious Python."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import pytest

from analysis.science_artifacts import ReviewRole, load_science_approvals
from analysis.science_activation import git
from analysis.science_implementation_stop import materialize_stop, render_stop_comment, stop_from_comment
from scripts.run_science_policy_probe import (
    CHILD_ENV, MODULE_PATHS, SUBJECT, bounded_child, observe, prepared_probe, validate_observation,
)
from tests.test_science_activation import commit
from tests.test_science_implementation_coverage import accepted_active_baseline


@pytest.fixture(scope='module')
def probe_candidates(accepted_active_baseline, tmp_path_factory):
    active = accepted_active_baseline
    stopped = tmp_path_factory.mktemp('stopped-policy-probe') / 'candidate'
    shutil.copytree(active, stopped)
    git(stopped, 'init')
    commit(stopped, 'synthetic active candidate')
    approval = next(item for item in load_science_approvals(stopped / 'data/science')
                    if item.subject_id == SUBJECT and item.role == ReviewRole.IMPLEMENTATION_REVIEWER)
    binding = approval.implementation_binding
    target = dict(schema_version=1, action='stop', repository=binding.repository, subject_id=SUBJECT,
                  active_contract_digest=approval.subject_digest, implementation_envelope_digest=binding.envelope_digest)
    comment = dict(id=77, body=render_stop_comment(target), user={'type':'User','login':'human'},
                   created_at=datetime.now(timezone.utc).isoformat(),
                   html_url=f'https://github.com/{binding.repository}/pull/{binding.pull_request}#issuecomment-77')
    materialize_stop(stopped, stop_from_comment(comment, 'admin', binding.repository))
    return {'activation':active, 'stopped-maintenance':stopped}, approval.subject_digest


@pytest.fixture
def candidate(probe_candidates, request, tmp_path):
    roots, contract = probe_candidates
    purpose = request.param
    root = tmp_path / 'candidate'
    shutil.copytree(roots[purpose], root, ignore=shutil.ignore_patterns('.git'))
    return root, purpose, contract


@pytest.fixture(scope='module')
def prepared_observations(probe_candidates):
    """Prepare real expectations once; candidate-execution tests stay fresh."""
    roots, contract = probe_candidates
    observations = {}
    for purpose, root in roots.items():
        with prepared_probe(root, purpose, SUBJECT, contract) as (_, expected):
            observations[purpose] = deepcopy(expected)
    return observations


@pytest.fixture
def expected_observations(prepared_observations):
    return deepcopy(prepared_observations)


@pytest.mark.parametrize('candidate', ['activation', 'stopped-maintenance'], indirect=True)
def test_genuine_guard_uses_candidate_modules_after_trusted_preparation(candidate):
    from analysis import science_artifacts as trusted_artifacts
    root, purpose, contract = candidate
    trusted_file = trusted_artifacts.__file__
    observed = observe(root, purpose, SUBJECT, contract)
    assert observed['module_paths'] == {name:str(root / path) for name, path in MODULE_PATHS.items()}
    assert trusted_artifacts.__file__ == trusted_file
    assert not Path(trusted_file).is_relative_to(root)
    if purpose == 'activation':
        assert observed['observation']['returned_contract'] == contract
    else:
        assert observed['observation'] == {'http_status':503, 'detail':'DFA_SCIENCE_POLICY_INACTIVE'}


@pytest.mark.parametrize('candidate', ['activation', 'stopped-maintenance'], indirect=True)
@pytest.mark.parametrize('stage', ['import', 'guard'])
@pytest.mark.parametrize('exit_code', ['raise SystemExit(0)', 'import os; os._exit(0)'])
def test_zero_exit_without_guard_observation_never_completes(candidate, stage, exit_code):
    import ast
    root, purpose, contract = candidate
    module = root / 'api/activity_dfa.py'
    if stage == 'import':
        module.write_text(exit_code + '\n')
    else:
        source = module.read_text()
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'require_policy')
        lines = source.splitlines(keepends=True)
        lines[function.lineno-1:function.end_lineno] = [f'def require_policy():\n    {exit_code}\n']
        module.write_text(''.join(lines))
    git(root, 'init')
    commit(root, 'frozen synthetic early-exit candidate')
    assert git(root, 'status', '--porcelain') == b''
    with pytest.raises(ValueError, match='complete strict observation'):
        observe(root, purpose, SUBJECT, contract)


@pytest.mark.parametrize('candidate', ['activation', 'stopped-maintenance'], indirect=True)
def test_static_controller_does_not_import_candidate_dependency(candidate):
    root, purpose, contract = candidate
    path = root / 'analysis/science_artifacts.py'
    path.write_text("raise RuntimeError('candidate dependency imported')\n")
    # Static preparation must still work using trusted code, even though the
    # candidate dependency deliberately fails. The child must actually import it.
    with prepared_probe(root, purpose, SUBJECT, contract) as (_, expected):
        assert expected['contract_digest'] == contract
    with pytest.raises(ValueError, match='did not complete successfully'):
        observe(root, purpose, SUBJECT, contract)


@pytest.mark.parametrize('purpose', ['activation', 'stopped-maintenance'])
@pytest.mark.parametrize('mutation', ['empty', 'truncated', 'malformed', 'duplicate', 'extra', 'extra_object',
                                      'mismatch', 'wrong_type', 'missing', 'provenance', 'nonzero'])
def test_completion_requires_one_strict_exact_typed_observation(expected_observations, purpose, mutation):
    expected = expected_observations[purpose]
    changed = deepcopy(expected)
    if mutation == 'extra': changed['claimed_success'] = True
    if mutation == 'mismatch': changed['contract_digest'] = 'sha256:' + '0'*64
    if mutation == 'wrong_type': changed['schema_version'] = True
    if mutation == 'missing': changed.pop('observation')
    if mutation == 'provenance': changed['module_paths']['analysis.science_artifacts'] = '/trusted/analysis/science_artifacts.py'
    encoded = json.dumps(changed).encode()
    if mutation == 'empty': encoded = b''
    if mutation == 'truncated': encoded = encoded[:-1]
    if mutation == 'malformed': encoded = b'not JSON'
    if mutation == 'duplicate': encoded = encoded[:-1] + b', "schema_version":1}'
    if mutation == 'extra_object': encoded += b'\n{}'
    with pytest.raises(ValueError):
        validate_observation(encoded, 1 if mutation == 'nonzero' else 0, expected)


def test_expected_observations_do_not_share_nested_mutable_state(expected_observations, prepared_observations):
    original = deepcopy(prepared_observations)
    expected_observations['activation']['module_paths'].clear()
    expected_observations['stopped-maintenance']['observation']['http_status'] = 200
    assert prepared_observations == original


def test_child_environment_is_explicit_and_excludes_parent_authority(tmp_path, monkeypatch):
    for name in ['GH_TOKEN', 'GITHUB_TOKEN', 'AZURE_CLIENT_SECRET', 'PRAXYS_DATABASE_URL', 'HOME',
                 'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'GITHUB_ENV', 'GITHUB_PATH', 'GITHUB_OUTPUT']:
        monkeypatch.setenv(name, 'synthetic-must-not-reach-child')
    stdout, result = bounded_child([sys.executable, '-E', '-B', '-P', '-c',
        'import os,json; print(json.dumps(dict(os.environ)))'], cwd=tmp_path)
    assert result == 0
    assert json.loads(stdout) == CHILD_ENV


@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_output_is_bounded_during_capture(tmp_path, stream):
    with pytest.raises(ValueError, match='output limit'):
        bounded_child([sys.executable, '-E', '-B', '-P', '-c',
            f'import os; data=b"x"*4096\nwhile True: os.write({1 if stream == "stdout" else 2}, data)'],
            cwd=tmp_path, timeout=2, output_limit=1024)


def test_timeout_terminates_child_and_descendant_pipe_holder(tmp_path):
    import os
    import time
    pid_file = tmp_path / 'child-pid'
    code = ('import os,time\nfrom pathlib import Path\n'
            f'Path({str(pid_file)!r}).write_text(str(os.getpid()))\n'
            'if os.fork() == 0: time.sleep(30)\n'
            'time.sleep(30)\n')
    started = time.monotonic()
    with pytest.raises(ValueError, match='timeout'):
        bounded_child([sys.executable, '-E', '-B', '-P', '-c', code], cwd=tmp_path, timeout=0.5)
    assert time.monotonic() - started < 3
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@pytest.mark.parametrize('purpose', ['activation', 'stopped-maintenance'])
def test_correct_child_output_with_actual_nonzero_exit_is_rejected(probe_candidates, purpose, tmp_path):
    roots, contract = probe_candidates
    with prepared_probe(roots[purpose], purpose, SUBJECT, contract) as (_, expected):
        encoded = json.dumps(expected).encode()
        code = f'import os; os.write(1, {encoded!r}); os._exit(1)'
        stdout, returncode = bounded_child([sys.executable, '-E', '-B', '-P', '-c', code], cwd=tmp_path)
        assert stdout == encoded and returncode == 1
        with pytest.raises(ValueError, match='did not complete successfully'):
            validate_observation(stdout, returncode, expected)


def test_controller_never_projects_an_actual_stopped_subject(probe_candidates):
    roots, contract = probe_candidates
    with pytest.raises(ValueError, match='terminally stopped'):
        with prepared_probe(roots['stopped-maintenance'], 'activation', SUBJECT, contract):
            pytest.fail('Stopped subject cannot reach its hypothetical observer')
