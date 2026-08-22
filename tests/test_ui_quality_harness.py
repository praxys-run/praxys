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
- Primary journey: Today -> recovery verdict -> supporting metrics
- Reviewer handoff: local-only - test-screenshots/ui-quality/today/index.html reviewed in the maintainer session
- States checked: loading, empty, error, success, long EN/zh
- Accessibility: keyboard, focus, contrast, reduced motion, touch targets
- Design system impact: none - existing tokens and components cover this change
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


def test_reviewer_handoff_accepts_bounded_modes_with_detail():
    current_handoff = (
        "local-only - test-screenshots/ui-quality/today/index.html "
        "reviewed in the maintainer session"
    )
    for handoff in (
        "local-only - test-screenshots/ui-quality/pr-123/index.html",
        "PR media - 25 second journey video and unsupported-state screenshot",
        "CI artifact - frontend-quality run 123456",
        "preview - https://preview.example.test/pr-123",
        "none - copy-only change reviewed live; media adds no reviewer value",
    ):
        evidence = VALID_WEB_EVIDENCE.replace(current_handoff, handoff)
        assert validate_ui_evidence(
            evidence,
            has_web=True,
            has_miniapp=False,
        ) == []

    errors = validate_ui_evidence(
        VALID_WEB_EVIDENCE.replace(current_handoff, "uploaded somewhere"),
        has_web=True,
        has_miniapp=False,
    )
    assert any("reviewer handoff" in error for error in errors)


def test_template_placeholders_do_not_count_as_evidence():
    template = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
        encoding="utf-8"
    )
    assert "never claim validation or review that was not performed" in template
    errors = validate_ui_evidence(template, has_web=True, has_miniapp=False)
    assert errors
    assert any("missing or unverified" in error for error in errors)


def test_copilot_draft_can_record_truthful_pending_ui_evidence():
    """Draft CI may be green without pretending rendered review happened."""
    draft = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(
        encoding="utf-8"
    )

    assert validate_ui_evidence(
        draft,
        has_web=False,
        has_miniapp=True,
        allow_unverified=True,
    ) == []
    assert validate_ui_evidence(
        draft,
        has_web=False,
        has_miniapp=True,
    )


def test_unavailable_source_only_evidence_requires_draft_mode():
    evidence = (
        "## UI quality\n"
        "- Impeccable: clarify web/src/pages/Road10KControlledOptIn.tsx - "
        "existing source-level target\n"
        "- Visual review: unavailable - desktop and mobile Chrome were not "
        "performed\n"
        "- Primary journey: invited Goal -> Training summary\n"
        "- Reviewer handoff: none - exact-head captures are unavailable\n"
        "- States checked: source and test only - invited and enrolled states\n"
        "- Accessibility: source only - keyboard and focus were not verified\n"
        "- Design system impact: none - accepted components cover the change\n"
        "- Miniapp parity: preserved - native WeChat rendering is unavailable\n"
        "- Exceptions: none\n"
    )

    errors = validate_ui_evidence(
        evidence,
        has_web=True,
        has_miniapp=True,
    )
    for field in (
        "impeccable",
        "visual review",
        "reviewer handoff",
        "states checked",
        "accessibility",
        "miniapp parity",
    ):
        assert any(field in error for error in errors)

    assert validate_ui_evidence(
        evidence,
        has_web=True,
        has_miniapp=True,
        allow_unverified=True,
    ) == []

    hyphenated = evidence.replace(
        "source and test only",
        "source-and-test-only",
    )
    assert any(
        "states checked" in error
        for error in validate_ui_evidence(
            hyphenated,
            has_web=True,
            has_miniapp=True,
        )
    )
    assert validate_ui_evidence(
        hyphenated,
        has_web=True,
        has_miniapp=True,
        allow_unverified=True,
    ) == []


def test_design_system_update_requires_changed_governance_path():
    evidence = VALID_WEB_EVIDENCE.replace(
        "none - existing tokens and components cover this change",
        "updated in this PR - docs/dev/design-system.md",
    )
    assert validate_ui_evidence(
        evidence,
        has_web=True,
        has_miniapp=False,
        changed_paths=[
            "web/src/pages/Today.tsx",
            "docs/dev/design-system.md",
        ],
    ) == []

    errors = validate_ui_evidence(
        evidence,
        has_web=True,
        has_miniapp=False,
        changed_paths=["web/src/pages/Today.tsx"],
    )
    assert any("no design-governance file changed" in error for error in errors)


def test_design_system_follow_up_requires_filed_issue():
    evidence = VALID_WEB_EVIDENCE.replace(
        "none - existing tokens and components cover this change",
        "follow-up #812 - define compact recovery-card spacing",
    )
    assert validate_ui_evidence(
        evidence,
        has_web=True,
        has_miniapp=False,
    ) == []

    errors = validate_ui_evidence(
        evidence.replace("#812", "later"),
        has_web=True,
        has_miniapp=False,
    )
    assert any("must reference a filed GitHub issue" in error for error in errors)


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
    workflow = (ROOT / ".github" / "workflows" / "ci-premerge.yml").read_text(
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
    assert "frontend-quality:" in workflow
    assert "name: Pre-merge CI" in workflow
    assert "scripts/check_ui_quality.py" in workflow
    assert "needs: [web-build, ui-quality]" in workflow
    assert "needs: [python-tests]" in workflow
    assert "FRONTEND_RESULT" not in workflow
    assert "--pr-body-env UI_PR_BODY" in workflow
    assert "--allow-unverified-draft" in workflow
    assert "UI Quality Harness (mandatory)" in instructions
    assert "scripts/agent_preflight.py --base origin/main" in instructions
    skill_path = ROOT / ".github" / "skills" / "ui-quality" / "SKILL.md"
    assert skill_path.is_file()
    skill = skill_path.read_text(encoding="utf-8")
    assert "test-screenshots/ui-quality/<branch-or-pr>/" in skill
    assert "15-45 second video" in skill
    assert "browser-native WebM is acceptable locally" in skill
    assert "downscaled raster storyboard" in skill
    assert (
        ROOT / ".github" / "instructions" / "ui-quality.instructions.md"
    ).is_file()

    agent = (
        ROOT / ".github" / "agents" / "praxys-change-loop.agent.md"
    ).read_text(encoding="utf-8")
    assert "description:" in agent
    assert "agent-ready" in agent
    assert "playwright/*" not in agent
    assert "python scripts/agent_preflight.py --base origin/main" in agent

    science_template = (
        ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "science-change.md"
    ).read_text(encoding="utf-8")
    assert "Do not check any item that was not actually performed." in science_template
    assert "## UI quality" in science_template

    assert "types: [opened, synchronize, reopened, ready_for_review, edited]" in workflow


def test_i18n_pr_body_contains_valid_catalog_only_ui_evidence():
    workflow = (ROOT / ".github" / "workflows" / "i18n.yml").read_text(
        encoding="utf-8"
    )
    section_start = workflow.index("            ## UI quality")
    section_end = workflow.index(
        "\n\n      - name: Dispatch required validation",
        section_start,
    )
    body = "\n".join(
        line.removeprefix("            ")
        for line in workflow[section_start:section_end].splitlines()
    )

    assert validate_ui_evidence(
        body,
        has_web=True,
        has_miniapp=False,
        changed_paths=["web/src/locales/zh/messages.po"],
    ) == []


def test_ui_mcp_configs_are_pinned_and_cloud_safe():
    local_config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    local_chrome = local_config["mcpServers"]["chrome-devtools"]
    assert "chrome-devtools-mcp@1.6.0" in local_chrome["args"]
    assert "--headless" in local_chrome["args"]
    assert "--isolated" in local_chrome["args"]

    cloud_config = json.loads(
        (ROOT / "config" / "copilot-cloud-mcp.json").read_text(
            encoding="utf-8"
        )
    )
    servers = cloud_config["mcpServers"]
    assert set(servers) == {"chrome-devtools", "praxys-local"}
    assert "praxys-dev-test" not in servers
    assert {
        "take_screenshot",
        "take_snapshot",
        "list_console_messages",
        "lighthouse_audit",
        "resize_page",
    }.issubset(servers["chrome-devtools"]["tools"])
    cloud_praxys = servers["praxys-local"]
    local_praxys = local_config["mcpServers"]["praxys-local"]
    assert local_praxys["tools"] == cloud_praxys["tools"]
    assert cloud_praxys["command"] == "praxys-local-mcp"
    assert cloud_praxys["args"] == []
    assert "env" not in cloud_praxys
    assert all(
        not tool.startswith(
            ("update_", "set_", "connect_", "disconnect_", "trigger_")
        )
        for tool in cloud_praxys["tools"]
    )

    wrapper = (
        ROOT / "scripts" / "run_praxys_mcp_cloud.sh"
    ).read_text(encoding="utf-8")
    assert 'readlink -f "${BASH_SOURCE[0]}"' in wrapper
    assert "GITHUB_WORKSPACE" not in wrapper
    assert 'cd "$workspace"' in wrapper
    assert "export PRAXYS_MCP_USE_CURRENT_PYTHON=1" in wrapper
    assert 'exec python -m scripts.run_praxys_mcp local "$@"' in wrapper

    setup = (
        ROOT / ".github" / "workflows" / "copilot-setup-steps.yml"
    ).read_text(encoding="utf-8")
    assert "submodules: true" in setup
    assert "plugins/praxys/mcp-server/requirements.txt" in setup
    assert "chrome-devtools-mcp@1.6.0 --version" in setup
    assert "from mcp.server.fastmcp import FastMCP" in setup
    assert (
        '"$GITHUB_WORKSPACE/scripts/run_praxys_mcp_cloud.sh"'
        in setup
    )
    assert "/usr/local/bin/praxys-local-mcp" in setup
    assert "praxys-local-mcp --prepare-only" in setup
    assert "git restore --source=HEAD -- package-lock.json" in setup
    assert "git diff --exit-code -- package-lock.json" in setup

    plugin_requirements = (
        ROOT / "plugins" / "praxys" / "mcp-server" / "requirements.txt"
    ).read_text(encoding="utf-8")
    assert "mcp==1.28.1" in plugin_requirements.splitlines()


def test_backend_deploy_initializes_plugin_submodule():
    workflow = (
        ROOT / ".github" / "workflows" / "deploy-backend.yml"
    ).read_text(encoding="utf-8")
    test_job = workflow.split("  deploy:", maxsplit=1)[0]
    assert "submodules: true" in test_job
