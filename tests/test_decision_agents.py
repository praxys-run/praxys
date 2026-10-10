"""Discoverable adapters enforce one owner, optional independent review and tool isolation."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _agent(name):
    text = (ROOT / f".github/agents/{name}.agent.md").read_text()
    _, metadata, body = text.split("---", 2)
    return yaml.safe_load(metadata), body


def test_only_three_adapters_are_discoverable():
    assert {p.name for p in (ROOT / ".github/agents").glob("*.agent.md")} == {
        "praxys-orchestrator.agent.md", "quality.agent.md", "operations.agent.md",
    }
    assert {p.stem for p in (ROOT / ".codex/agents").glob("*.toml")} == {
        "praxys-orchestrator", "quality", "operations",
    }


def test_executor_can_finish_without_dispatch_and_reviewer_cannot_edit_or_dispatch():
    main, body = _agent("praxys-orchestrator")
    reviewer, review = _agent("quality")
    operations, _ = _agent("operations")
    assert "edit" in main["tools"] and "agent" in main["tools"]
    assert "edit" not in reviewer["tools"] and "agent" not in reviewer["tools"]
    assert "agent" not in operations["tools"]
    assert "without executor history" in body
    assert "Do not inherit the executor's conversation" in review
    assert "scripts/agent_preflight.py --base origin/main" in body
    assert "Never approve or merge your own PR" in body


def test_science_and_ui_quality_remain_mandatory_without_role_handoffs():
    science = (ROOT / ".github/skills/science-research/SKILL.md").read_text()
    ui = (ROOT / ".github/skills/ui-quality/SKILL.md").read_text()
    assert "Current science approval artifacts remain human-authenticated" in science
    assert "independent evidence" in science.lower()
    assert "draft" in science and "accepted" in science
    assert "rendered" in ui and "accessibility" in ui and "parity" in ui
    assert "without separate Product/Design handoffs" in ui
