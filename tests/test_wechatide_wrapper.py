"""Exercise the real shell flow with isolated host-path and bridge stubs.

Only the hardcoded PowerShell executable and mounted-drive prefix are redirected
in the temporary script copy. No Windows process, mount, token or GUI is used.
The production mirror refusal, argument conversion and dispatch logic run intact.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _executable(path: Path, source: str) -> None:
    path.write_text(source)
    path.chmod(0o755)


@pytest.fixture
def wrapper(tmp_path: Path):
    repo = tmp_path / "source repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (repo / "miniapp").mkdir()
    (scripts / "wechatide.ps1").write_bytes((ROOT / "scripts/wechatide.ps1").read_bytes())
    install = tmp_path / "Nightly install"
    install.mkdir()
    mount = tmp_path / "mounted drive"
    mount.mkdir()
    mirror = mount / "Praxys mirror"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "bridge.json"
    sync_calls = tmp_path / "sync.json"
    bridge = bin_dir / "powershell-stub"
    _executable(bridge, """#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ['WECHATIDE_TEST_CALLS']).write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.environ.get('WECHATIDE_TEST_EXIT', '0')))
""")
    _executable(bin_dir / "wslpath", """#!/usr/bin/env python3
import sys
assert sys.argv[1] == '-w' and len(sys.argv) == 3
print('WIN:' + sys.argv[2])
""")
    _executable(bin_dir / "rsync", """#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ['WECHATIDE_TEST_SYNC']).write_text(json.dumps(sys.argv[1:]))
""")
    source = (ROOT / "scripts/wechatide").read_text()
    executable = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    assert source.count(executable) == source.count("/mnt/?/*") == 1
    source = source.replace(executable, str(bridge)).replace(
        "/mnt/?/*", '"${WECHATIDE_TEST_MOUNT}"/*'
    )
    script = scripts / "wechatide"
    _executable(script, source)
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
        "WSL_DISTRO_NAME": "isolated-test",
        "WECHATIDE_INSTALL_ROOT": str(install),
        "WECHATIDE_PROJECT_MIRROR": str(mirror),
        "WECHATIDE_TEST_MOUNT": str(mount),
        "WECHATIDE_TEST_CALLS": str(calls),
        "WECHATIDE_TEST_SYNC": str(sync_calls),
    }
    env.pop("WECHATIDE_ALLOW_FOREGROUND", None)
    env.pop("BASH_ENV", None)

    def run(*args: str, changes: dict[str, str] | None = None):
        return subprocess.run(
            ["bash", str(script), *args], env={**env, **(changes or {})},
            capture_output=True, text=True, timeout=10, check=False,
        )

    return SimpleNamespace(
        repo=repo, script=script, install=install, mirror=mirror,
        bridge=bridge, calls=calls, sync_calls=sync_calls, run=run,
    )


def test_unset_foreground_variable_dispatches_registered_status(wrapper):
    args = ["-c", "Copilot", "check_wechatide_status", "--skill-version", "0.3.11"]
    result = wrapper.run(*args)
    assert result.returncode == 0, result.stderr
    dispatched = json.loads(wrapper.calls.read_text())
    assert dispatched[-len(args):] == args
    assert dispatched[:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    assert dispatched[4:7] == [
        "WIN:" + str(wrapper.repo / "scripts/wechatide.ps1"),
        "-InstallRoot", "WIN:" + str(wrapper.install),
    ]
    assert not wrapper.mirror.exists()
    assert not wrapper.sync_calls.exists()


def test_project_conversion_preserves_arguments_and_sync_exclusions(wrapper):
    function = 'function () { return "quoted value"; }\n// $(not-a-shell-command)'
    result = wrapper.run("automation_evaluate", "--project", str(wrapper.repo / "miniapp"),
                         "--fn-source", function)
    assert result.returncode == 0, result.stderr
    assert json.loads(wrapper.calls.read_text())[-5:] == [
        "automation_evaluate", "--project", "WIN:" + str(wrapper.mirror),
        "--fn-source", function,
    ]
    assert (wrapper.mirror / ".praxys-wechatide-mirror").is_file()
    args = json.loads(wrapper.sync_calls.read_text())
    assert args[:2] == ["-a", "--delete"]
    assert args[2:-2] == [
        "--exclude", ".praxys-wechatide-mirror", "--exclude", "node_modules/",
        "--exclude", "miniprogram_npm/", "--exclude", "project.private.config.json",
        "--exclude", "*.log",
    ]
    assert args[-2:] == [str(wrapper.repo / "miniapp") + "/", str(wrapper.mirror) + "/"]


def test_nonempty_unmarked_mirror_is_refused_without_dispatch(wrapper):
    wrapper.mirror.mkdir()
    personal = wrapper.mirror / "unrelated.txt"
    personal.write_text("must remain")
    result = wrapper.run("--sync-project")
    assert result.returncode == 1
    assert "non-empty unmarked directory" in result.stderr
    assert personal.read_text() == "must remain"
    assert not wrapper.sync_calls.exists()
    assert not wrapper.calls.exists()


def test_marked_mirror_may_be_reused(wrapper):
    wrapper.mirror.mkdir()
    (wrapper.mirror / ".praxys-wechatide-mirror").touch()
    result = wrapper.run("--sync-project")
    assert result.returncode == 0, result.stderr
    assert wrapper.sync_calls.exists()
    assert not wrapper.calls.exists()


@pytest.mark.parametrize("target", ["outside-mount", "source"])
def test_invalid_mirror_target_still_fails_before_sync(wrapper, target):
    path = wrapper.repo / ("miniapp" if target == "source" else "unrelated")
    result = wrapper.run("--sync-project", changes={"WECHATIDE_PROJECT_MIRROR": str(path)})
    assert result.returncode == 1
    assert "dedicated directory on a mounted Windows drive" in result.stderr
    assert not wrapper.sync_calls.exists()
    assert not wrapper.calls.exists()


def test_missing_install_directory_still_fails(wrapper):
    result = wrapper.run("check_wechatide_status", changes={
        "WECHATIDE_INSTALL_ROOT": str(wrapper.install / "missing"),
    })
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
    assert not wrapper.calls.exists()


@pytest.mark.parametrize("missing", ["script", "executable"])
def test_missing_bridge_still_fails(wrapper, missing):
    path = wrapper.repo / "scripts/wechatide.ps1" if missing == "script" else wrapper.bridge
    path.unlink()
    result = wrapper.run("check_wechatide_status")
    assert result.returncode == 1
    assert ("Missing PowerShell bridge" if missing == "script" else "Windows PowerShell is unavailable") in result.stderr
    assert not wrapper.calls.exists()


def test_upstream_argument_failure_exit_is_preserved(wrapper):
    result = wrapper.run("unknown_tool", "--invalid-option", changes={"WECHATIDE_TEST_EXIT": "2"})
    assert result.returncode == 2
    assert json.loads(wrapper.calls.read_text())[-2:] == ["unknown_tool", "--invalid-option"]
