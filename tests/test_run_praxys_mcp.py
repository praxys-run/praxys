"""Deterministic local and production-test MCP launcher coverage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts import run_praxys_mcp


def _database_snapshot() -> dict[str, object]:
    from db import session as db_session
    from db.models import Activity, RecoveryData, TrainingPlan, User, UserConfig

    db_session.dispose_engines()
    db_session.init_db(force=True)
    db = db_session.SessionLocal()
    try:
        users = db.query(User).all()
        config = db.get(UserConfig, run_praxys_mcp.LOCAL_USER_ID)
        return {
            "user_ids": [user.id for user in users],
            "activities": db.query(Activity).filter(
                Activity.user_id == run_praxys_mcp.LOCAL_USER_ID,
            ).count(),
            "recovery": db.query(RecoveryData).filter(
                RecoveryData.user_id == run_praxys_mcp.LOCAL_USER_ID,
            ).count(),
            "plans": db.query(TrainingPlan).filter(
                TrainingPlan.user_id == run_praxys_mcp.LOCAL_USER_ID,
            ).count(),
            "display_name": config.display_name if config else None,
        }
    finally:
        db.close()
        db_session.dispose_engines()


def test_local_sandbox_bootstraps_once_and_resets_explicitly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = run_praxys_mcp.project_root()
    data_dir = tmp_path / "local-mcp"
    monkeypatch.setenv(
        "PRAXYS_DATABASE_URL",
        "postgresql://must-not-be-used.invalid/praxys",
    )
    with mock.patch.dict(os.environ, {}, clear=False):
        first = run_praxys_mcp.ensure_local_sandbox(root, data_dir)
        initial = _database_snapshot()
        key = (data_dir / ".encryption-key").read_text(
            encoding="utf-8",
        ).strip()

        assert first.reset is True
        assert initial["user_ids"] == [run_praxys_mcp.LOCAL_USER_ID]
        assert initial["activities"] > 0
        assert initial["recovery"] > 0
        assert initial["plans"] > 0
        assert initial["display_name"] == "Local MCP Athlete"
        assert key

        from db import session as db_session
        from db.models import UserConfig

        db_session.init_db(force=True)
        db = db_session.SessionLocal()
        try:
            config = db.get(UserConfig, run_praxys_mcp.LOCAL_USER_ID)
            assert config is not None
            config.display_name = "Persistent local edit"
            db.commit()
        finally:
            db.close()
            db_session.dispose_engines()

        reused = run_praxys_mcp.ensure_local_sandbox(root, data_dir)
        assert reused.reset is False
        assert (data_dir / ".encryption-key").read_text(
            encoding="utf-8",
        ).strip() == key
        assert _database_snapshot()["display_name"] == "Persistent local edit"

        reset = run_praxys_mcp.ensure_local_sandbox(
            root,
            data_dir,
            reset=True,
        )
        restored = _database_snapshot()
        assert reset.reset is True
        assert restored == initial


def test_local_sandbox_refuses_an_unowned_nonempty_directory(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "existing-data"
    data_dir.mkdir()
    (data_dir / "personal.txt").write_text(
        "do not overwrite",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="not owned by Praxys MCP"):
        run_praxys_mcp._claim_sandbox(data_dir)

    assert (data_dir / "personal.txt").read_text(
        encoding="utf-8",
    ) == "do not overwrite"


def test_sandbox_lock_serializes_concurrent_bootstrap(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "locked-sandbox"
    data_dir.mkdir()
    first_acquired = threading.Event()
    release_first = threading.Event()
    second_acquired = threading.Event()

    def hold_first_lock() -> None:
        with run_praxys_mcp._sandbox_lock(data_dir):
            first_acquired.set()
            assert release_first.wait(timeout=5)

    def acquire_second_lock() -> None:
        assert first_acquired.wait(timeout=5)
        with run_praxys_mcp._sandbox_lock(data_dir):
            second_acquired.set()

    first = threading.Thread(target=hold_first_lock)
    second = threading.Thread(target=acquire_second_lock)
    first.start()
    assert first_acquired.wait(timeout=5)
    second.start()
    time.sleep(0.2)
    assert not second_acquired.is_set()

    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert not first.is_alive()
    assert not second.is_alive()
    assert second_acquired.is_set()


def test_remote_profile_forces_isolated_production_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRAXYS_LOCAL", "1")
    monkeypatch.setenv("PRAXYS_TOKEN_PATH", "shared-token")
    monkeypatch.setenv("PRAXYS_URL", "https://staging.invalid")

    run_praxys_mcp.configure_remote_profile("dev-test")

    assert os.environ["PRAXYS_LOCAL"] == "0"
    assert os.environ["PRAXYS_PROFILE"] == "dev-test"
    assert os.environ["PRAXYS_TOKEN_PATH"] == ""
    assert (
        os.environ["PRAXYS_URL"]
        == "https://api.praxys.run"
    )


def test_runtime_python_override_does_not_require_project_venv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = run_praxys_mcp.project_root()
    monkeypatch.setenv("PRAXYS_MCP_PYTHON", sys.executable)
    monkeypatch.setattr(
        run_praxys_mcp,
        "_venv_python",
        lambda _root: tmp_path / "missing-python",
    )

    assert run_praxys_mcp._runtime_python(root) == Path(
        sys.executable
    ).resolve()
    run_praxys_mcp._reexec_in_runtime_python(root)


def test_runtime_python_can_opt_into_current_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = run_praxys_mcp.project_root()
    monkeypatch.delenv("PRAXYS_MCP_PYTHON", raising=False)
    monkeypatch.setenv("PRAXYS_MCP_USE_CURRENT_PYTHON", "1")
    monkeypatch.setattr(
        run_praxys_mcp,
        "_venv_python",
        lambda _root: tmp_path / "missing-python",
    )

    assert run_praxys_mcp._runtime_python(root) == Path(
        sys.executable
    ).resolve()
    run_praxys_mcp._reexec_in_runtime_python(root)


def test_prepare_only_does_not_require_plugin_submodule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = run_praxys_mcp.project_root()
    data_dir = tmp_path / "prepared-sandbox"
    monkeypatch.chdir(root)
    monkeypatch.setattr(
        run_praxys_mcp,
        "_reexec_in_runtime_python",
        lambda _root: None,
    )
    monkeypatch.setattr(
        run_praxys_mcp,
        "_parse_args",
        lambda: SimpleNamespace(
            mode="local",
            profile=None,
            reset=False,
            prepare_only=True,
        ),
    )
    monkeypatch.setattr(
        run_praxys_mcp,
        "_resolve_local_data_dir",
        lambda _root: data_dir,
    )
    monkeypatch.setattr(
        run_praxys_mcp,
        "ensure_local_sandbox",
        lambda _root, _data_dir, *, reset: run_praxys_mcp.BootstrapResult(
            data_dir=data_dir,
            reset=reset,
            fingerprint="test",
        ),
    )
    monkeypatch.setattr(
        run_praxys_mcp,
        "_plugin_server",
        lambda _root: tmp_path / "missing-server.py",
    )
    monkeypatch.setattr(
        run_praxys_mcp,
        "_require_mcp_runtime",
        lambda _root: pytest.fail("prepare-only loaded the MCP runtime"),
    )

    with pytest.raises(SystemExit) as exc_info:
        run_praxys_mcp.main()

    assert exc_info.value.code == 0


def test_repository_mcp_config_registers_local_and_dev_test_profiles() -> None:
    root = run_praxys_mcp.project_root()
    config = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    servers = config["mcpServers"]

    assert servers["praxys-local"]["command"] == "node"
    assert servers["praxys-local"]["args"] == [
        "scripts/run_praxys_mcp.cjs",
        "local",
    ]
    assert servers["praxys-dev-test"]["command"] == "node"
    assert servers["praxys-dev-test"]["args"] == [
        "scripts/run_praxys_mcp.cjs",
        "remote-profile",
        "dev-test",
    ]
    assert servers["praxys-local"]["env"] == {}
    assert servers["praxys-dev-test"]["env"] == {}
    assert servers["chrome-devtools"]["type"] == "stdio"
    assert "chrome-devtools-mcp@1.6.0" in servers["chrome-devtools"]["args"]


def test_repository_mcp_launcher_honors_python_override(
    tmp_path: Path,
) -> None:
    root = run_praxys_mcp.project_root()
    node = shutil.which("node")
    assert node is not None
    data_dir = tmp_path / "node-launcher-sandbox"
    env = os.environ.copy()
    env["PRAXYS_LOCAL_MCP_DATA_DIR"] = str(data_dir)
    env["PRAXYS_MCP_PYTHON"] = sys.executable

    result = subprocess.run(
        [
            node,
            str(root / "scripts" / "run_praxys_mcp.cjs"),
            "local",
            "--prepare-only",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    marker = json.loads(
        (data_dir / ".praxys-mcp-sandbox.json").read_text(
            encoding="utf-8",
        )
    )
    assert marker["owner"] == "praxys-local-mcp"
    assert marker["state"] == "ready"


@pytest.mark.skipif(
    os.name == "nt",
    reason="The cloud MCP launcher targets GitHub's Linux runner.",
)
def test_cloud_mcp_launcher_resolves_workspace_from_symlink(
    tmp_path: Path,
) -> None:
    root = run_praxys_mcp.project_root()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python").symlink_to(sys.executable)
    installed_launcher = bin_dir / "praxys-local-mcp"
    installed_launcher.symlink_to(
        root / "scripts" / "run_praxys_mcp_cloud.sh",
    )
    data_dir = tmp_path / "cloud-launcher-sandbox"
    env = os.environ.copy()
    env.pop("GITHUB_WORKSPACE", None)
    env["PRAXYS_LOCAL_MCP_DATA_DIR"] = str(data_dir)
    env.pop("PRAXYS_MCP_USE_CURRENT_PYTHON", None)
    env["PATH"] = os.pathsep.join((str(bin_dir), env.get("PATH", "")))

    result = subprocess.run(
        [
            str(installed_launcher),
            "--prepare-only",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    marker = json.loads(
        (data_dir / ".praxys-mcp-sandbox.json").read_text(
            encoding="utf-8",
        )
    )
    assert marker["owner"] == "praxys-local-mcp"
    assert marker["state"] == "ready"


@pytest.mark.parametrize("profile", ["..", "dev/test", r"dev\test"])
def test_remote_profile_rejects_unsafe_names(profile: str) -> None:
    with pytest.raises(SystemExit, match="Profile names"):
        run_praxys_mcp.configure_remote_profile(profile)
