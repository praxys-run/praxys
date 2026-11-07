"""Tests for optional local validation selection."""
from __future__ import annotations

from scripts.agent_preflight import (
    has_rendered_ui,
    main,
    needs_backend_validation,
    needs_miniapp_validation,
    needs_web_validation,
)


def test_preflight_routes_web_and_rendered_ui_changes() -> None:
    paths = ["web/src/pages/Today.tsx", "web/tests/format.test.mjs"]

    assert needs_web_validation(paths)
    assert has_rendered_ui(paths)
    assert not needs_miniapp_validation(paths)


def test_preflight_routes_web_canonical_inputs_to_miniapp() -> None:
    assert needs_miniapp_validation(["web/src/types/api.ts"])
    assert needs_miniapp_validation(["web/src/locales/zh/messages.po"])
    assert needs_miniapp_validation(["web/src/lib/legal.ts"])


def test_preflight_ignores_backend_only_changes_for_frontend_checks() -> None:
    paths = ["api/routes/today.py", "tests/test_today.py"]

    assert not needs_web_validation(paths)
    assert not needs_miniapp_validation(paths)
    assert not has_rendered_ui(paths)


def test_documentation_checks_do_not_run_backend_suite(monkeypatch) -> None:
    """Documentation-only work should not pay for the whole regression suite."""
    commands = []
    monkeypatch.setattr("scripts.agent_preflight.changed_files", lambda *a: ["docs/dev/gotchas.md"])
    monkeypatch.setattr("scripts.agent_preflight._run", lambda cmd, **kw: commands.append(cmd))
    assert main([]) == 0
    assert commands == [["git", "diff", "--check", "origin/main...HEAD"]]


def test_explicit_tests_are_run_without_another_full_suite(monkeypatch) -> None:
    """A focused verification choice stays focused even for shared backend inputs."""
    commands = []
    monkeypatch.setattr("scripts.agent_preflight.changed_files", lambda *a: ["analysis/metrics.py"])
    monkeypatch.setattr("scripts.agent_preflight._run", lambda cmd, **kw: commands.append(cmd))
    assert main(["--test", "tests/test_metrics.py"]) == 0
    pytest_command = next(cmd for cmd in commands if "pytest" in cmd)
    assert pytest_command[-1] == "tests/test_metrics.py"
    assert "tests/" not in pytest_command


def test_shared_backend_inputs_still_require_regression_checks() -> None:
    for path in ["analysis/metrics.py", "requirements.txt", "config/science.json",
                 "data/science/model.yaml", "scripts/sync.py", "alembic/versions/update.py"]:
        assert needs_backend_validation([path])
    assert not needs_backend_validation(["docs/dev/contributing.md"])
