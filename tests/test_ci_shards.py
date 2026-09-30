"""Deterministic whole-file plans and complete same-run execution evidence."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.ci_pytest import ROOT
from scripts.ci_shards import DATABASE_GROUP, load_weights, plan_files, selected_nodes
from scripts.verify_ci_pytest import verify


def test_lpt_is_order_independent_whole_file_and_preserves_database_affinity():
    weights, _ = load_weights()
    nodes = ['tests/test_unknown.py::test_a', 'tests/test_unknown.py::test_b',
             'tests/test_dfa_recovery_workflow.py::test_a',
             'tests/test_activity_dfa.py::test_a', 'tests/test_pg_migration.py::test_b']
    planned = plan_files(nodes, weights)
    assert planned == plan_files(list(reversed(nodes)), weights)
    assert not set(planned[0]) & set(planned[1])
    assert set(planned[0]) | set(planned[1]) == {node.split('::')[0] for node in nodes}
    assert any(DATABASE_GROUP <= set(bucket) for bucket in planned)
    for index in (0, 1):
        selected = selected_nodes(nodes, index, weights)
        assert len([node for node in selected if node.startswith('tests/test_unknown.py')]) in (0, 2)


def test_unknown_file_uses_positive_median_and_stable_ties():
    weights = dict(files={'a.py': 2, 'b.py': 6}, groups=[])
    assert plan_files(['a.py::test', 'b.py::test', 'new.py::test'], weights) == [['b.py'], ['a.py', 'new.py']]


@pytest.mark.parametrize('mutation', ['zero', 'negative', 'nonfinite', 'boolean', 'missing_group', 'overlap'])
def test_invalid_or_unsafe_weights_fail_closed(tmp_path, mutation):
    weights, _ = load_weights()
    if mutation in ('zero', 'negative', 'nonfinite', 'boolean'):
        weights['files']['new.py'] = {'zero': 0, 'negative': -1, 'nonfinite': float('inf'), 'boolean': True}[mutation]
    if mutation == 'missing_group': weights['groups'] = []
    if mutation == 'overlap': weights['groups'].append(['tests/test_activity_dfa.py'])
    path = tmp_path / 'weights.json'
    path.write_text(json.dumps(weights))
    with pytest.raises(ValueError):
        load_weights(path)


def write_execution(root, key, nodes, weights, digest):
    count, index = key
    directory = root / f'{count}-{index}'
    directory.mkdir()
    packages = [{'name': 'pytest', 'version': '9.1.1'}]
    package_digest = sha256(json.dumps(packages, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    mode = 'serial' if count == 1 else 'sharded'
    manifest = dict(schema_version=1, mode=mode, shard_count=count, shard_index=index,
                    weights_sha256=digest, completed=True, evidence_complete=True, child_exit_code=0,
                    exit_code=0, errors=[], git_revision='a' * 40, python_version='Python 3.12.3',
                    platform='Linux', architecture='x86_64', tracked_changes_present=False,
                    submodules=[' ' + 'b' * 40 + ' plugins/praxys (synthetic)'], requested_paths=['tests/'],
                    dependencies=dict(packages=packages, sha256=package_digest),
                    github=dict(GITHUB_REPOSITORY='owner/repo', GITHUB_RUN_ID='42',
                                GITHUB_RUN_ATTEMPT='1', GITHUB_SHA='a' * 40))
    selected = nodes if count == 1 else selected_nodes(nodes, index, weights)
    phases = []
    for node in selected:
        for phase in ('setup', 'call', 'teardown'):
            phases.append(dict(nodeid=node, phase=phase, outcome='passed', duration_seconds=0.01,
                               reason=None, wasxfail=None, strict_xpass=False))
    data = dict(schema_version=1, mode=mode, shard_count=count, shard_index=index, weights_sha256=digest,
                session_finished=True, collection_complete=True, full_collected=nodes,
                pre_shard_selected=nodes, selected=selected, deselected=[], phases=phases, exit_code=0,
                collection_reports=[dict(nodeid='tests/test_optional.py', outcome='skipped', reason='optional unavailable')])
    (directory / 'result.json').write_text(json.dumps(manifest))
    (directory / 'phases.json').write_text(json.dumps(data))
    (directory / 'junit.xml').write_text('<testsuite>' + '<testcase/>' * len(selected) + '</testsuite>')
    return directory


@pytest.fixture
def artifacts(tmp_path):
    weights, digest = load_weights()
    nodes = [f'tests/test_{name}.py::test_{case}' for name in ('a', 'b', 'c', 'd') for case in ('one', 'two')]
    for key in ((1, 0), (2, 0), (2, 1)):
        write_execution(tmp_path, key, nodes, weights, digest)
    return tmp_path


def verify_comparison(root):
    return verify(root, mode='compare', expected_sha='a' * 40, repository='owner/repo', run_id='42', run_attempt='1')


def test_serial_baseline_is_verified_separately_from_two_shard_union(artifacts):
    result = verify_comparison(artifacts)
    assert result['verified'] and result['collected_count'] == 8 and result['executions'] == 3
    assert result['activation_authorized'] is False


def test_collection_order_may_differ_without_changing_coverage(artifacts):
    path = artifacts / '2-1/phases.json'
    data = json.loads(path.read_text())
    data['full_collected'].reverse()
    data['pre_shard_selected'].reverse()
    data['selected'].reverse()
    path.write_text(json.dumps(data))
    assert verify_comparison(artifacts)['verified']


@pytest.mark.parametrize('mutation', ['missing', 'failed', 'cancelled', 'all_skipped', 'missing_phase',
    'different_collection', 'overlap', 'missing_selected', 'wrong_sha', 'wrong_python', 'wrong_packages',
    'wrong_submodule', 'dirty', 'subset', 'wrong_run', 'wrong_attempt', 'wrong_repository', 'wrong_weights',
    'module_skip', 'runtime_skip', 'xfail', 'missing_junit', 'wrong_platform', 'boolean_schema', 'duplicate_collected'])
def test_verifier_rejects_incomplete_or_mismatched_execution(artifacts, mutation):
    directory = artifacts / '2-1'
    manifest = json.loads((directory / 'result.json').read_text())
    data = json.loads((directory / 'phases.json').read_text())
    if mutation == 'missing':
        (directory / 'result.json').unlink()
    elif mutation == 'missing_junit':
        (directory / 'junit.xml').unlink()
    else:
        if mutation == 'failed': manifest['exit_code'] = manifest['child_exit_code'] = 1
        if mutation == 'cancelled': manifest['completed'] = False
        if mutation == 'all_skipped':
            for phase in data['phases']:
                if phase['phase'] == 'call': phase['outcome'] = 'skipped'
        if mutation == 'missing_phase': data['phases'].pop()
        if mutation == 'different_collection': data['full_collected'] = data['full_collected'][:-1]
        if mutation == 'overlap': data['selected'].append(json.loads((artifacts / '2-0/phases.json').read_text())['selected'][0])
        if mutation == 'missing_selected': data['selected'].pop()
        if mutation == 'wrong_sha': manifest['git_revision'] = 'c' * 40
        if mutation == 'wrong_python': manifest['python_version'] = 'Python 3.11'
        if mutation == 'wrong_platform': manifest['platform'] = 'Darwin'
        if mutation == 'wrong_packages': manifest['dependencies']['packages'][0]['version'] = '0'
        if mutation == 'wrong_submodule': manifest['submodules'] = ['-' + 'b' * 40 + ' plugins/praxys']
        if mutation == 'dirty': manifest['tracked_changes_present'] = True
        if mutation == 'subset': manifest['requested_paths'] = ['tests/test_a.py']
        if mutation == 'wrong_run': manifest['github']['GITHUB_RUN_ID'] = '99'
        if mutation == 'wrong_attempt': manifest['github']['GITHUB_RUN_ATTEMPT'] = '2'
        if mutation == 'wrong_repository': manifest['github']['GITHUB_REPOSITORY'] = 'other/repo'
        if mutation == 'wrong_weights': manifest['weights_sha256'] = '0' * 64
        if mutation == 'boolean_schema': manifest['schema_version'] = True
        if mutation == 'duplicate_collected': data['full_collected'].append(data['full_collected'][0])
        if mutation == 'module_skip': data['collection_reports'][0]['reason'] = 'different missing optional dependency'
        if mutation in ('runtime_skip', 'xfail'):
            phase = next(item for item in data['phases'] if item['phase'] == 'call')
            phase.update(outcome='skipped', reason='different outcome')
            if mutation == 'xfail': phase['wasxfail'] = 'different outcome'
        (directory / 'result.json').write_text(json.dumps(manifest))
        (directory / 'phases.json').write_text(json.dumps(data))
    with pytest.raises((ValueError, OSError)):
        verify_comparison(artifacts)


def test_real_processes_collect_once_and_cover_all_files_with_skip_equivalence(tmp_path):
    suite = tmp_path / 'suite'
    suite.mkdir()
    (suite / 'test_a.py').write_text('import pytest\ndef test_a(): pass\n@pytest.mark.skip(reason="same skip")\ndef test_skip(): pass\n')
    (suite / 'test_b.py').write_text('import pytest\ndef test_b(): pass\n@pytest.mark.xfail(reason="same xfail")\ndef test_xfail(): assert False\n')
    (suite / 'test_optional.py').write_text('import pytest\npytest.skip("same module skip",allow_module_level=True)\n')
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    environment.pop('PYTEST_ADDOPTS', None)
    environment.pop('PYTEST_PLUGINS', None)
    evidence = {}
    for count, index in ((1, 0), (2, 0), (2, 1)):
        output = tmp_path / f'evidence-{count}-{index}'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/ci_pytest.py'), '--output-dir', str(output),
                                 '--shard-count', str(count), '--shard-index', str(index), '--', str(suite)],
                                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads((output / 'result.json').read_text())
        assert manifest['evidence_complete'] and manifest['child_exit_code'] == 0
        evidence[count, index] = json.loads((output / 'phases.json').read_text())
    serial, first, second = (evidence[key] for key in ((1, 0), (2, 0), (2, 1)))
    assert serial['full_collected'] == first['full_collected'] == second['full_collected']
    assert len(serial['full_collected']) == 4
    assert not set(first['selected']) & set(second['selected'])
    assert set(first['selected']) | set(second['selected']) == set(serial['selected'])
    from scripts.verify_ci_pytest import outcomes, collection_outcomes
    assert outcomes(serial) == outcomes(first) + outcomes(second)
    assert collection_outcomes(serial) == collection_outcomes(first) == collection_outcomes(second)


def test_workflow_defaults_to_serial_and_keeps_required_contexts_and_same_run_artifacts():
    workflow = yaml.load((ROOT / '.github/workflows/ci-premerge.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['on']['workflow_dispatch']['inputs']['test_mode']['default'] == 'serial'
    assert workflow['on']['workflow_dispatch']['inputs']['test_mode']['options'] == ['serial', 'sharded', 'compare']
    job = workflow['jobs']['python-tests']
    assert job['strategy']['fail-fast'] == 'false'
    expression = job['strategy']['matrix']['include']
    assert "|| '[{\"label\":\"serial\",\"count\":1,\"index\":0}]')" in expression
    assert '"count":2,"index":0' in expression and '"count":2,"index":1' in expression
    assert workflow['jobs']['backend-tests']['name'] == 'backend-tests'
    assert workflow['jobs']['backend-tests']['needs'] == ['python-tests']
    assert workflow['jobs']['frontend-quality']['name'] == 'frontend-quality'
    aggregate = workflow['jobs']['backend-tests']['steps']
    download = next(step for step in aggregate if step.get('uses') == 'actions/download-artifact@v8')
    assert set(download['with']) == {'pattern', 'path'}  # defaults to THIS run, no cross-run token/ref
    assert '${{ github.run_id }}-${{ github.run_attempt }}' in download['with']['pattern']
    assert 'test "$PYTHON_RESULT" = "success"' in aggregate[0]['run']
