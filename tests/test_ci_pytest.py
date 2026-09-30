"""Real subprocess coverage for serial CI evidence and fail-closed reporting."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.ci_pytest import ROOT, dependency_identity, validate_evidence


def run_case(directory, source, conftest=''):
    directory.mkdir(exist_ok=True)
    (directory / 'test_case.py').write_text(source)
    if conftest:
        (directory / 'conftest.py').write_text(conftest)
    output = directory / 'evidence'
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    environment.pop('PYTEST_ADDOPTS', None)
    environment.pop('PYTEST_PLUGINS', None)
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/ci_pytest.py'),
                             '--output-dir', str(output), '--', str(directory / 'test_case.py')],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    manifest = json.loads((output / 'result.json').read_text())
    try:
        phases = json.loads((output / 'phases.json').read_text())
    except (OSError, ValueError):
        phases = None
    return result, manifest, phases


@pytest.fixture(scope='module')
def successful_run(tmp_path_factory):
    return run_case(tmp_path_factory.mktemp('ci-evidence-success'), '''import pytest
def test_pass(): assert True
@pytest.mark.skip(reason='synthetic setup skip')
def test_skip(): pass
@pytest.mark.xfail(reason='synthetic expected failure')
def test_xfail(): assert False
''')


def test_real_serial_run_records_every_phase_reason_and_identity(successful_run):
    result, manifest, phases = successful_run
    assert result.returncode == 0, result.stdout + result.stderr
    assert manifest['completed'] and manifest['evidence_complete']
    assert manifest['child_exit_code'] == manifest['exit_code'] == 0
    assert len(manifest['git_revision']) == 40
    assert manifest['platform'] and manifest['architecture']
    assert isinstance(manifest['submodules'], list)
    assert manifest['dependencies'] == dependency_identity()
    assert manifest['elapsed_seconds'] > 0
    assert phases['full_collected'] == phases['selected']
    assert len(phases['selected']) == 3
    assert phases['deselected'] == []
    assert any(item['phase'] == 'setup' and item['outcome'] == 'skipped'
               and 'synthetic setup skip' in item['reason'] for item in phases['phases'])
    assert any(item['phase'] == 'call' and item['wasxfail'] == 'synthetic expected failure'
               for item in phases['phases'])


@pytest.mark.parametrize('source,conftest,expected', [
    ('def test_fail(): assert False\n', '', 1),
    ('raise RuntimeError("collection fails")\n', '', 2),
    ('def test_pass(): pass\n', 'def pytest_sessionstart(session): raise RuntimeError("internal")\n', 3),
    ('def test_pass(): pass\n', 'import pytest\ndef pytest_configure(config): raise pytest.UsageError("usage")\n', 4),
    ('VALUE = 1\n', '', 5),
    ('import os,signal\ndef test_signal(): os.kill(os.getpid(), signal.SIGTERM)\n', '', 143),
])
def test_real_pytest_exit_classes_are_preserved(tmp_path, source, conftest, expected):
    result, manifest, _ = run_case(tmp_path, source, conftest)
    assert result.returncode == manifest['exit_code'] == expected, result.stdout + result.stderr
    assert manifest['completed'] and not manifest['evidence_complete']
    assert manifest['child_exit_code'] == (-15 if expected == 143 else expected)


@pytest.mark.parametrize('mode', ['setup_failure', 'teardown_failure', 'strict_xpass', 'all_skipped'])
def test_nonpassing_execution_never_becomes_a_green_gate(tmp_path, mode):
    sources = {
        'setup_failure': 'import pytest\n@pytest.fixture\ndef fixture(): raise RuntimeError("setup")\ndef test_case(fixture): pass\n',
        'teardown_failure': 'import pytest\n@pytest.fixture\ndef fixture():\n yield\n raise RuntimeError("teardown")\ndef test_case(fixture): pass\n',
        'strict_xpass': 'import pytest\n@pytest.mark.xfail(strict=True, reason="strict canary")\ndef test_case(): pass\n',
        'all_skipped': 'import pytest\n@pytest.mark.skip(reason="all skipped canary")\ndef test_case(): pass\n',
    }
    result, manifest, phases = run_case(tmp_path, sources[mode])
    assert result.returncode == (2 if mode == 'all_skipped' else 1)
    assert not manifest['evidence_complete']
    if mode == 'strict_xpass':
        assert any(item['strict_xpass'] and 'strict canary' in item['reason'] for item in phases['phases'])


@pytest.mark.parametrize('mutation', ['missing', 'malformed', 'unwritable', 'deselected', 'empty_junit'])
def test_missing_or_corrupt_reporting_fails_even_when_tests_pass(tmp_path, mutation):
    hooks = {
        'missing': 'from pathlib import Path\ndef pytest_unconfigure(config): Path(config.getoption("--ci-report")).unlink()\n',
        'malformed': 'from pathlib import Path\ndef pytest_unconfigure(config): Path(config.getoption("--ci-report")).write_text("invalid JSON")\n',
        'unwritable': 'from pathlib import Path\ndef pytest_sessionstart(session): Path(session.config.getoption("--ci-report")).mkdir()\n',
        'deselected': 'def pytest_collection_modifyitems(items): items.pop()\n',
        'empty_junit': 'from pathlib import Path\ndef pytest_unconfigure(config): Path(config.option.xmlpath).write_text("<testsuites/>")\n',
    }
    result, manifest, _ = run_case(tmp_path, 'def test_one(): pass\ndef test_two(): pass\n', hooks[mutation])
    assert result.returncode != 0 and not manifest['evidence_complete']
    assert manifest['errors']


def test_collection_skip_is_distinct_from_deselection(tmp_path):
    result, manifest, phases = run_case(tmp_path, 'import pytest\npytest.skip("module skip canary", allow_module_level=True)\n')
    assert result.returncode == 5 and not manifest['evidence_complete']
    assert phases['deselected'] == []
    assert phases['collection_reports'][0]['outcome'] == 'skipped'
    assert 'module skip canary' in phases['collection_reports'][0]['reason']


@pytest.mark.parametrize('mutation', ['partial_collection', 'missing_teardown', 'extra_node', 'duplicate_phase', 'negative_duration'])
def test_completion_guard_rejects_incomplete_or_ambiguous_evidence(successful_run, mutation):
    evidence = deepcopy(successful_run[2])
    if mutation == 'partial_collection': evidence['collection_complete'] = False
    if mutation == 'missing_teardown': evidence['phases'] = [p for p in evidence['phases'] if p['phase'] != 'teardown']
    if mutation == 'extra_node': evidence['phases'][0]['nodeid'] = 'not-collected'
    if mutation == 'duplicate_phase': evidence['phases'].append(deepcopy(evidence['phases'][0]))
    if mutation == 'negative_duration': evidence['phases'][0]['duration_seconds'] = -1
    assert validate_evidence(evidence)


def test_nested_pytest_does_not_inherit_ci_collector(tmp_path):
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'test_nested.py').write_text('def test_nested(pytestconfig): assert not pytestconfig.pluginmanager.hasplugin("ci-evidence")\n')
    source = f'''import subprocess,sys
def test_nested_invocation():
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', {str(nested)!r}], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
'''
    result, manifest, phases = run_case(tmp_path, source)
    assert result.returncode == 0 and manifest['evidence_complete']
    assert len(phases['selected']) == 1


def test_reused_success_cannot_survive_initialization_failure(tmp_path, monkeypatch):
    from scripts import ci_pytest
    previous = tmp_path / 'result.json'
    previous.write_text(json.dumps(dict(completed=True, evidence_complete=True, exit_code=0)))
    (tmp_path / 'phases.json').write_text('{}')
    def unavailable():
        raise ValueError('synthetic dependency metadata failure')
    monkeypatch.setattr(ci_pytest, 'dependency_identity', unavailable)
    assert ci_pytest.run(tmp_path, ['tests/']) == 2
    current = json.loads(previous.read_text())
    assert current['completed'] and not current['evidence_complete']
    assert current['exit_code'] == 2 and current['child_exit_code'] is None
    assert current['errors'] == ['initialization failure: ValueError']


def test_scoped_fixture_reordering_preserves_serial_coverage(tmp_path):
    result, manifest, phases = run_case(tmp_path, '''import pytest
@pytest.fixture(scope='module', params=[1, 2])
def value(request): return request.param
def test_first(value): assert value in (1, 2)
def test_second(value): assert value in (1, 2)
''')
    assert result.returncode == 0, result.stdout + result.stderr
    assert manifest['evidence_complete'] and manifest['child_exit_code'] == 0
    assert len(phases['full_collected']) == len(phases['selected']) == 4
    assert phases['full_collected'] != phases['selected']
    assert set(phases['full_collected']) == set(phases['selected'])


@pytest.mark.parametrize('field', ['full_collected', 'selected'])
def test_serial_collection_lists_reject_duplicates(successful_run, field):
    evidence = deepcopy(successful_run[2])
    evidence[field].append(evidence[field][0])
    assert 'empty or duplicate collection' in validate_evidence(evidence)
