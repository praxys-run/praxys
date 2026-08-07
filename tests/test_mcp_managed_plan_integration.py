"""Integration coverage for the pinned Praxys plugin managed-plan contract."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = ROOT / "plugins" / "praxys"
SERVER_PATH = PLUGIN_ROOT / "mcp-server" / "server.py"
PLUGIN_TESTS = PLUGIN_ROOT / "mcp-server" / "tests"
BACKEND_CI = ROOT / ".github" / "workflows" / "ci-premerge.yml"


class _FakeFastMCP:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def tool(self):
        return lambda function: function


def _require_plugin() -> None:
    if not SERVER_PATH.exists():
        pytest.skip("Praxys plugin submodule is not initialized")


def _load_local_server(monkeypatch):
    _require_plugin()
    mcp_module = ModuleType("mcp")
    mcp_server_module = ModuleType("mcp.server")
    fastmcp_module = ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = _FakeFastMCP
    module_name = "praxys_managed_plan_integration_server"
    spec = importlib.util.spec_from_file_location(module_name, SERVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.server", mcp_server_module)
    monkeypatch.setitem(
        sys.modules,
        "mcp.server.fastmcp",
        fastmcp_module,
    )
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _dispose_test_database(db_session) -> None:
    if db_session.engine is not None:
        db_session.engine.dispose()
    if db_session.async_engine is not None:
        try:
            asyncio.run(db_session.async_engine.dispose())
        except RuntimeError:
            pass
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None


def test_pinned_plugin_contract_suite() -> None:
    """The plugin's public-repository tests must pass at the pinned revision."""
    _require_plugin()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(PLUGIN_TESTS),
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_backend_ci_initializes_plugin_submodule() -> None:
    """The required Python check must not silently skip plugin integration."""
    workflow = BACKEND_CI.read_text(encoding="utf-8")
    python_job = workflow.split("  web-build:", maxsplit=1)[0]
    assert "submodules: true" in python_job


def test_local_managed_plan_lifecycle_uses_host_api(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Local tools must preserve API revisions, ownership, and lifecycle rules."""
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv("PRAXYS_LOCAL", "1")
    monkeypatch.setenv("PRAXYS_USER_ID", "mcp-managed-plan-user")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )

    from db import session as db_session

    _dispose_test_database(db_session)
    db_session.init_db()
    assert db_session.engine.url.get_backend_name() == "sqlite"
    database_path = Path(db_session.engine.url.database).resolve()
    assert database_path.is_relative_to(tmp_path.resolve())

    from db.models import User, UserConnection

    db = db_session.SessionLocal()
    try:
        db.add(User(
            id="mcp-managed-plan-user",
            email="mcp-managed-plan@test.local",
            hashed_password="x",
            is_active=True,
        ))
        db.add(UserConnection(
            user_id="mcp-managed-plan-user",
            platform="stryd",
            status="connected",
            preferences={"plan": True},
        ))
        db.commit()
    finally:
        db.close()

    from api.plan_delivery import rolling

    monkeypatch.setattr(
        rolling,
        "trigger_managed_plan_delivery",
        lambda *_args, **_kwargs: None,
    )
    server = _load_local_server(monkeypatch)
    server._cached_user_id = "mcp-managed-plan-user"
    server._db_initialized = True

    workout_date = (date.today() + timedelta(days=1)).isoformat()
    csv_text = (
        "date,workout_type,planned_duration_min,planned_distance_km,"
        "target_power_min,target_power_max,workout_description\n"
        f"{workout_date},easy,45,8,180,210,Local MCP integration"
    )

    try:
        saved = json.loads(server.save_training_plan(csv_text))
        initial = json.loads(server.get_managed_plan_status())
        with pytest.raises(RuntimeError, match=r"HTTP 422"):
            server.adopt_managed_plan(
                "not-a-platform",
                initial["window"]["start"],
                initial["window"]["end"],
            )
        adopted = json.loads(server.adopt_managed_plan(
            "stryd",
            initial["window"]["start"],
            initial["window"]["end"],
        ))
        paused = json.loads(server.pause_managed_plan())
        resume_preview = json.loads(server.get_managed_plan_status())
        resumed = json.loads(server.resume_managed_plan(
            resume_preview["window"]["start"],
            resume_preview["window"]["end"],
        ))
        left = json.loads(server.leave_managed_plan())
    finally:
        _dispose_test_database(db_session)

    assert saved["status"] == "saved"
    assert saved["operation"] == "plan_authoring"
    assert initial["summary"]["praxys_workouts"] == 1
    assert initial["plan_management"]["mode"] == "external"
    assert adopted["plan_management"]["mode"] == "praxys"
    assert adopted["plan_management"]["delivery_enabled"] is True
    assert paused["plan_management"]["delivery_enabled"] is False
    assert resumed["plan_management"]["delivery_enabled"] is True
    assert left["plan_management"]["mode"] == "external"
    assert left["cleanup"]["status"] == "kept"
