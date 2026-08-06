"""Tests for the cross-agent UI quality harness."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.check_ui_quality import (
    detector_targets,
    is_design_governance_path,
    rendered_surface,
    validate_ui_evidence,
)


ROOT = Path(__file__).resolve().parent.parent


VALID_WEB_EVIDENCE = """\
## UI quality
- Impeccable: `polish web/src/pages/Today.tsx`
- Visual review: desktop 1440x900; mobile 390x844
- States checked: loading, empty, error, success, long EN/zh
- Accessibility: keyboard, focus, contrast, reduced motion, touch targets
- Miniapp parity: not applicable - copy-only web route has no miniapp equivalent
- Exceptions: none
"""


def test_rendered_surface_classification_is_strict_but_cross_client():
    assert rendered_surface("web/src/pages/Today.tsx") == "web"
    assert rendered_surface("web/src/index.css") == "web"
    assert rendered_surface("web/src/locales/zh/messages.po") == "web"
    assert rendered_surface("web/src/types/api.ts") is None
    assert rendered_surface("web/src/pages/Today.test.tsx") is None
    assert rendered_surface("miniapp/pages/today/index.wxml") == "miniapp"
    assert rendered_surface("miniapp/app.json") == "miniapp"
    assert rendered_surface("miniapp/scripts/sync-types.cjs") is None
    assert rendered_surface("api/routes/today.py") is None
    assert is_design_governance_path("DESIGN.md")
    assert is_design_governance_path("docs/brand/index.html")


def test_detector_targets_only_existing_supported_sources(tmp_path: Path):
    (tmp_path / "web/src").mkdir(parents=True)
    (tmp_path / "web/src/Today.tsx").write_text("export const Today = 1", encoding="utf-8")
    (tmp_path / "web/src/logo.svg").write_text("<svg/>", encoding="utf-8")

    assert detector_targets(
        [
            "web/src/Today.tsx",
            "web/src/logo.svg",
            "web/src/missing.css",
        ],
        root=tmp_path,
    ) == ["web/src/Today.tsx"]


def test_web_evidence_requires_impeccable_and_two_viewports():
    assert validate_ui_evidence(
        VALID_WEB_EVIDENCE,
        has_web=True,
        has_miniapp=False,
    ) == []

    missing_mobile = VALID_WEB_EVIDENCE.replace(
        "desktop 1440x900; mobile 390x844",
        "desktop 1440x900",
    )
    errors = validate_ui_evidence(
        missing_mobile,
        has_web=True,
        has_miniapp=False,
    )
    assert "Web UI evidence must include both desktop and mobile review." in errors


def test_template_placeholders_do_not_count_as_evidence():
    template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
        encoding="utf-8"
    )
    errors = validate_ui_evidence(template, has_web=True, has_miniapp=False)
    assert errors
    assert any("missing or unverified" in error for error in errors)


def test_miniapp_evidence_names_runtime_and_parity_reason():
    evidence = VALID_WEB_EVIDENCE.replace(
        "desktop 1440x900; mobile 390x844",
        "WeChat DevTools Skyline on iPhone viewport",
    ).replace(
        "not applicable - copy-only web route has no miniapp equivalent",
        "updated miniapp/pages/today",
    )
    assert validate_ui_evidence(
        evidence,
        has_web=False,
        has_miniapp=True,
    ) == []


def test_harness_is_wired_into_agents_and_required_ci():
    copilot_hook = json.loads(
        (ROOT / ".github" / "hooks" / "impeccable.json").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads(
        (ROOT / ".impeccable" / "config.json").read_text(encoding="utf-8")
    )
    claude_settings = json.loads(
        (ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    workflow = (ROOT / ".github" / "workflows" / "ci-backend.yml").read_text(
        encoding="utf-8"
    )
    instructions = (
        ROOT / ".github" / "copilot-instructions.md"
    ).read_text(encoding="utf-8")

    command = copilot_hook["hooks"]["postToolUse"][0]["bash"]
    assert ".github/skills/impeccable/scripts/hook.mjs" in command
    assert any(
        ".github/skills/impeccable/scripts/hook.mjs"
        in hook["command"]
        for entry in claude_settings["hooks"]["PostToolUse"]
        for hook in entry["hooks"]
    )
    assert config["hook"]["enabled"] is True
    assert {entry["ext"] for entry in config["detector"]["extensions"]} == {
        ".wxml",
        ".wxss",
    }
    assert "ui-quality:" in workflow
    assert "UI_RESULT" in workflow
    assert "scripts/check_ui_quality.py" in workflow
    assert "needs: [python-tests, web-build, ui-quality]" in workflow
    assert "--pr-body-env UI_PR_BODY" in workflow
    assert "UI Quality Harness (mandatory)" in instructions
    assert (ROOT / ".github" / "skills" / "ui-quality" / "SKILL.md").is_file()
    assert (
        ROOT / ".github" / "instructions" / "ui-quality.instructions.md"
    ).is_file()
