"""Contracts for the repository-owned science research skill."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
COPILOT_SKILL = ROOT / ".github" / "skills" / "science-research" / "SKILL.md"
CLAUDE_SKILL = (
    ROOT
    / ".claude"
    / "skills"
    / "praxys-science-research-claude"
    / "SKILL.md"
)
SKILLS_DOC = ROOT / "docs" / "skills.md"
CONTRIBUTING_DOC = ROOT / "docs" / "dev" / "contributing.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_science_research_skill_has_a_discoverable_canonical_workflow() -> None:
    """The Copilot skill keeps research and decision proposals auditable."""
    source = _source(COPILOT_SKILL)

    _, frontmatter, _ = source.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == "science-research"
    assert "Research and interpret scientific evidence" in metadata["description"]
    for requirement in (
        "### Research-only",
        "### Decision proposal",
        "full-text|abstract|metadata|inaccessible",
        "human reviewer",
        "activity `avg_power`",
        "science-reviewer",
        "Evidence Review or SDR only",
        "must not require theory-only fields",
        "metric-addition-reviewer",
        "api-contract-reviewer",
        "Decision proposal mode must draft",
        "leave\n  `supersedes` empty",
        "apply the lifecycle change atomically",
        "requester explicitly approves",
        "authenticated local/remote agent session",
        "must not invent, widen, or reuse an approval",
        "materialize the digest-bound approval artifact",
        "every accepted SDR",
        "all governed theory/model references",
        "First fixture: heat adaptation and environmental performance",
        "plugins/praxys/",
    ):
        assert requirement in source


def test_claude_entry_point_delegates_to_canonical_skill() -> None:
    """Claude Code uses the same policy without a second copy to maintain."""
    source = _source(CLAUDE_SKILL)

    _, frontmatter, _ = source.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == CLAUDE_SKILL.parent.name
    assert "disable-model-invocation: true" in source
    assert "../../../.github/skills/science-research/SKILL.md" in source
    assert "Do not duplicate or weaken those rules here." in source


def test_science_research_skill_is_documented_as_developer_only() -> None:
    """Documentation preserves the boundary with athlete-facing science."""
    skills_doc = _source(SKILLS_DOC)
    contributing_doc = _source(CONTRIBUTING_DOC)

    assert "science-research" in skills_doc
    assert "praxys-science-research-claude" in skills_doc
    assert "browse/select only" in skills_doc
    assert ".github/skills/science-research/SKILL.md" in contributing_doc
    assert "leave `supersedes` empty" in contributing_doc
    assert "every accepted SDR" in contributing_doc
    assert "Only after explicit human approval" in contributing_doc
