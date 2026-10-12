"""Child-only option transport through the actual hostile-regression launcher."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from tests.test_science_stop_github import _hostile_pytest_environment, _run_hostile_pytest


@pytest.mark.parametrize('options,expected', [
    ('--basetemp /tmp/parent -q', ['-q']),
    ('-q --basetemp=/tmp/parent --maxfail=2', ['-q', '--maxfail=2']),
    ('--basetemp "/tmp/parent with spaces" -k "one or two"', ['-k', 'one or two']),
    ('--basetemp="/tmp/parent with spaces" -o "cache_dir=a b"', ['-o', 'cache_dir=a b']),
    ('--basetemp /tmp/one -q --basetemp=/tmp/two --basetemp /tmp/three', ['-q']),
    ('-o "marker=--basetemp=/literal path" --basetemporary=keep',
     ['-o', 'marker=--basetemp=/literal path', '--basetemporary=keep']),
    ('-q -- --basetemp=/literal "a b"', ['-q', '--', '--basetemp=/literal', 'a b']),
    ("-k 'name and not other' -o 'word=it\"s here'", ['-k', 'name and not other', '-o', 'word=it"s here']),
    ('', []),
])
def test_child_options_preserve_tokens_and_parent(options, expected):
    parent = {'PYTEST_ADDOPTS': options, 'OTHER_OPTION': 'literal with spaces', 'TEST_PARENT_TOKEN': 'synthetic-parent-token'}
    before = deepcopy(parent)
    child = _hostile_pytest_environment(parent)
    assert parent == before and child is not parent
    assert shlex.split(child['PYTEST_ADDOPTS']) == expected
    assert {k:v for k,v in child.items() if k!='PYTEST_ADDOPTS'} == {k:v for k,v in before.items() if k!='PYTEST_ADDOPTS'}


def test_absent_options_stay_absent():
    parent = {'OTHER': 'literal'}
    assert _hostile_pytest_environment(parent) == parent
    assert 'PYTEST_ADDOPTS' not in parent


@pytest.mark.parametrize('options', ['--basetemp', '--basetemp -q', '--basetemp --maxfail=1',
    '--basetemp="" -q', '--basetemp "" -q', '--basetemp /tmp/ok --basetemp', '-k "unclosed'])
def test_malformed_options_fail_without_swallowing_or_mutating(options):
    parent = {'PYTEST_ADDOPTS': options, 'OTHER': 'retain'}
    before = deepcopy(parent)
    with pytest.raises(ValueError): _hostile_pytest_environment(parent)
    assert parent == before


@pytest.mark.parametrize('form', ['split', 'equals'])
def test_real_child_override_survives_ancestor_env_and_preserves_evidence(tmp_path, form):
    cwd = tmp_path / 'candidate';cwd.mkdir()
    attack = cwd / 'test_child.py'
    attack.write_text('def test_child(tmp_path):\n    (tmp_path / "worked").write_text("owned")\n')
    parent_flag = shlex.join(['--basetemp', str(tmp_path)]) if form=='split' else shlex.join(['--basetemp='+str(tmp_path)])
    environment = dict(os.environ, PYTEST_ADDOPTS=parent_flag+' -rA')
    before = deepcopy(environment)
    sibling = tmp_path / 'child scratch with spaces'
    evidence = tmp_path / 'child-launch-evidence.json'
    result = _run_hostile_pytest([sys.executable, '-m', 'pytest', '-q', '--basetemp='+str(sibling), str(attack)],
                                cwd=cwd, environment=environment, evidence=evidence)
    assert result.returncode==0 and '1 passed' in result.stdout
    assert environment==before and cwd.exists() and attack.exists()
    assert list(sibling.rglob('worked'))
    assert json.loads(evidence.read_text())['returncode']==0


def test_child_failure_output_is_retained_redacted_before_reraise(tmp_path):
    cwd = tmp_path / 'candidate';cwd.mkdir()
    attack = cwd / 'test_child.py'
    attack.write_text('import os,sys\ndef test_child():\n    print(os.environ["TEST_PARENT_TOKEN"])\n    print(os.environ["TEST_PARENT_PASSWORD"],file=sys.stderr)\n    assert False, "synthetic child failure"\n')
    environment = dict(os.environ, PYTEST_ADDOPTS=shlex.join(['--basetemp',str(tmp_path)]),
                       TEST_PARENT_TOKEN='synthetic-parent-token-canary', TEST_PARENT_PASSWORD='synthetic-parent-password-canary')
    before = deepcopy(environment);evidence=tmp_path/'child-failure-evidence.json'
    with pytest.raises(subprocess.CalledProcessError) as caught:
        _run_hostile_pytest([sys.executable,'-m','pytest','-q','--basetemp='+str(tmp_path/'failed-child'),str(attack)],
                           cwd=cwd,environment=environment,evidence=evidence)
    data=json.loads(evidence.read_text())
    assert data['returncode']==caught.value.returncode==1
    assert 'synthetic child failure' in data['stdout'] and '[REDACTED]' in data['stdout']
    for secret in (environment['TEST_PARENT_TOKEN'],environment['TEST_PARENT_PASSWORD']):
        assert secret not in evidence.read_text() and secret not in caught.value.stdout and secret not in caught.value.stderr
    assert 'TEST_PARENT_TOKEN' not in data and environment==before
    assert cwd.exists() and attack.exists()


def test_malformed_option_trace_does_not_dump_parent_secret(tmp_path):
    cwd=tmp_path/'candidate';cwd.mkdir();test=cwd/'test_private_trace.py'
    root=Path(__file__).resolve().parents[1]
    test.write_text('import os,sys\nsys.path.insert(0,'+repr(str(root))+')\n'
        'from tests.test_science_stop_github import _hostile_pytest_environment\n'
        'def test_private_trace():\n'
        '    _hostile_pytest_environment({"PYTEST_ADDOPTS":"--basetemp -q",'
        '"TEST_PARENT_TOKEN":os.environ["TEST_PARENT_TOKEN"]})\n')
    environment=dict(os.environ,TEST_PARENT_TOKEN='synthetic-private-trace-canary')
    child=_hostile_pytest_environment(environment)
    result=subprocess.run([sys.executable,'-m','pytest','-q','--basetemp='+str(tmp_path/'private-trace-child'),str(test)],
                          cwd=cwd,env=child,capture_output=True,text=True)
    assert result.returncode==1 and 'ValueError' in result.stdout
    assert 'synthetic-private-trace-canary' not in result.stdout+result.stderr
    assert cwd.exists() and test.exists()
    (tmp_path/'private-trace-evidence.json').write_text(json.dumps(
        {'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}))
