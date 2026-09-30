"""Real trusted manifest coverage on an accepted/active DFA registry."""
from pathlib import Path
import json
import shutil

import pytest

from analysis.evidence_registry import load_science_registry
from analysis.science_activation import project_active_registry, verify_governed_maintenance
from analysis.science_artifacts import build_policy_contract

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = 'sdr-activity-dfa-alpha1-v1'
REQUIRED_FILES = [
    'analysis/__init__.py', 'api/__init__.py', 'api/routes/__init__.py',
    'db/__init__.py', 'sync/__init__.py', 'tests/__init__.py',
    'tests/test_science_activation.py', 'tests/test_science_activation_github.py',
    'tests/test_science_approval_workflow.py', 'tests/test_science_artifacts.py',
    'tests/test_health_ready.py', 'scripts/check_projected_dfa_policy.py',
    'scripts/collect_science_activation_validation.py', 'scripts/agent_preflight.py',
    'scripts/run_science_policy_probe.py', 'scripts/observe_science_policy.py', 'tests/test_science_policy_probe.py',
    '.github/workflows/ci-premerge.yml', '.github/workflows/science-activation-validation.yml',
    'scripts/ci_pytest.py', 'scripts/ci_pytest_plugin.py', 'scripts/ci_metrics.py',
    'tests/test_ci_pytest.py', 'tests/test_ci_metrics.py',
]


@pytest.fixture(scope='module')
def accepted_active_baseline(tmp_path_factory):
    root = tmp_path_factory.mktemp('real-governed-baseline')
    policy = json.loads((ROOT / 'config/science-implementation-coverage.json').read_text())
    assert set(REQUIRED_FILES) <= set(policy['contracts'][SUBJECT])
    for name in policy['contracts'][SUBJECT]:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    # Run the real synthetic projection script, retaining only its disposable
    # validated registry for maintenance tests. No production approval exists.
    from scripts.check_projected_dfa_policy import synthetic_active_registry
    with synthetic_active_registry(ROOT, SUBJECT, None, fresh_hypothetical=True) as (science, contract):
        expected = contract.contract_digest
        shutil.copytree(science, root / 'data/science')
    registry = load_science_registry(root / 'data/science')
    assert build_policy_contract(registry, SUBJECT).contract_digest == expected
    assert registry.decisions[SUBJECT].artifact_policy.runtime_state.value == 'active'
    return root


@pytest.fixture
def maintenance_pair(accepted_active_baseline, tmp_path):
    candidate = tmp_path / 'candidate'
    shutil.copytree(accepted_active_baseline, candidate)
    return accepted_active_baseline, candidate


@pytest.mark.parametrize('name', REQUIRED_FILES)
def test_real_manifest_rejects_each_required_initializer_and_validation_source(maintenance_pair, name):
    base, candidate = maintenance_pair
    path = candidate / name
    path.write_bytes(path.read_bytes() + b'\n# changed under existing approval\n')
    with pytest.raises(ValueError, match='governed files or import slots'):
        verify_governed_maintenance(load_science_registry(base / 'data/science'),
                                   load_science_registry(candidate / 'data/science'))


@pytest.mark.parametrize('name', [
    'api/activity_dfa/__init__.py', 'analysis/activity_dfa/__init__.py',
    'api/activity_dfa/__init__.abi3.so', 'api/activity_dfa.cpython-312-x86_64-linux-gnu.so',
    'analysis/activity_dfa.cp312-win_amd64.pyd', 'api/activity_dfa/__init__.pyc',
    'api/__pycache__/activity_dfa.cpython-312.pyc',
    'numpy.py', 'numpy/__init__.py', 'fitdecode.abi3.so',
    'sitecustomize.py', 'usercustomize/__init__.py',
])
def test_new_name_resolution_alternative_rejected(maintenance_pair, name):
    base, candidate = maintenance_pair
    target = candidate / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'synthetic import shadow; never executed')
    with pytest.raises(ValueError, match='governed files or import slots'):
        verify_governed_maintenance(load_science_registry(base / 'data/science'),
                                   load_science_registry(candidate / 'data/science'))


def test_unrelated_document_and_api_file_additions_remain_allowed(maintenance_pair):
    base, candidate = maintenance_pair
    (candidate / 'unrelated.md').write_text('ordinary maintenance')
    (candidate / 'api/unrelated_new_feature.py').write_text('VALUE = 1\n')
    verify_governed_maintenance(load_science_registry(base / 'data/science'),
                               load_science_registry(candidate / 'data/science'))


def test_package_symlink_cannot_hide_unchanged_initializer_bytes(maintenance_pair):
    base, candidate = maintenance_pair
    shutil.rmtree(candidate / 'api')
    (candidate / 'api').symlink_to(base / 'api', target_is_directory=True)
    with pytest.raises(ValueError, match='governed files or import slots'):
        verify_governed_maintenance(load_science_registry(base / 'data/science'),
                                   load_science_registry(candidate / 'data/science'))
