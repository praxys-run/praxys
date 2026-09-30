"""Exercise the shared Linux source guard without Node or WeChat credentials."""
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check_miniapp_source.sh'
PAGES = ('login', 'today', 'training', 'goal', 'history', 'settings', 'science')
COMPONENTS = ('nav-bar', 'line-chart', 'bar-chart', 'scatter-chart')


@pytest.fixture
def miniapp(tmp_path):
    for directory, names in (('pages', PAGES), ('components', COMPONENTS)):
        for name in names:
            root = tmp_path / directory / name
            root.mkdir(parents=True)
            for suffix in ('ts', 'wxml'):
                (root / f'index.{suffix}').write_text('synthetic source\n')
    return tmp_path


def check(root):
    return subprocess.run(['bash', str(SCRIPT)], cwd=root, capture_output=True, text=True, timeout=5)


@pytest.mark.parametrize('relative', [f'pages/{name}/index.{suffix}' for name in PAGES for suffix in ('ts', 'wxml')]
                         + [f'components/{name}/index.{suffix}' for name in COMPONENTS for suffix in ('ts', 'wxml')])
def test_every_missing_page_or_component_fails(miniapp, relative):
    (miniapp / relative).unlink()
    result = check(miniapp)
    assert result.returncode != 0 and '::error::Missing' in result.stdout


def test_complete_sources_pass_and_development_inputs_do_not_count(miniapp):
    for relative in ('node_modules/huge.js', 'scripts/huge.js', 'package-lock.json',
                     'package.json', 'tsconfig.json', 'utils/i18n-catalog.ts'):
        path = miniapp / relative
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b'x' * 2_100_000)
    result = check(miniapp)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'All 7 page entries present.' in result.stdout
    assert 'All 4 components present.' in result.stdout


@pytest.mark.parametrize('size,exit_code,level', [(1_600_000, 0, 'warning'), (2_200_000, 1, 'error')])
def test_actual_packaged_source_size_warns_and_rejects(miniapp, size, exit_code, level):
    (miniapp / 'runtime.js').write_bytes(b'x' * size)
    result = check(miniapp)
    assert result.returncode == exit_code
    assert f'::{level}::miniapp/' in result.stdout


def test_both_workflows_require_identical_source_checks_and_generated_typechecks():
    standalone = yaml.load((ROOT / '.github/workflows/miniapp-build.yml').read_text(), Loader=yaml.BaseLoader)
    unified = yaml.load((ROOT / '.github/workflows/ci-premerge.yml').read_text(), Loader=yaml.BaseLoader)
    assert 'pull_request' not in standalone['on']
    assert standalone['on']['push']['branches'] == ['main']
    assert 'workflow_dispatch' in standalone['on']
    assert 'scripts/check_miniapp_source.sh' in standalone['on']['push']['paths']
    assert 'paths' not in unified['on']['pull_request']
    for steps in (standalone['jobs']['build']['steps'], unified['jobs']['miniapp-legal']['steps']):
        commands = [step.get('run', '') for step in steps]
        assert commands.count('bash ../scripts/check_miniapp_source.sh') == 1
        assert any('npm run typecheck' in command for command in commands)
        assert any('git diff --exit-code' in command and all(path in command for path in (
            'types/api.ts', 'utils/i18n-catalog.ts', 'utils/legal.ts')) for command in commands)
