"""Tests for coding-agent final preflight routing."""
from __future__ import annotations

from scripts.agent_preflight import (
    has_rendered_ui,
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
