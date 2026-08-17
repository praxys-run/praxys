"""Contract checks for product-policy and decision-routing agents."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".github" / "agents"


def _agent(path: Path) -> tuple[dict[str, object], str]:
    raw = path.read_text(encoding="utf-8")
    _, frontmatter, body = raw.split("---", 2)
    return yaml.safe_load(frontmatter), body


def _normalized(source: str) -> str:
    return " ".join(source.split())


def test_product_policy_agent_owns_value_not_approval() -> None:
    metadata, body = _agent(AGENTS / "product-policy.agent.md")

    assert metadata["name"] == "Praxys Product Policy"
    assert metadata["target"] == "github-copilot"
    assert metadata["user-invocable"] is True
    assert "user problem" in body
    assert "value hypothesis" in body
    assert "representative user scenarios" in body
    assert "minimum valuable implementation slice" in body
    assert "schema-version-2 SDR" in body
    assert "Praxys Decision Review Router" in body
    assert "Do not approve a decision" in body
    assert "decide that your own proposal can skip review" in body


def test_decision_router_is_independent_and_default_human() -> None:
    metadata, body = _agent(AGENTS / "decision-review-router.agent.md")

    assert metadata["name"] == "Praxys Decision Review Router"
    assert metadata["tools"] == ["read", "search", "agent"]
    assert "must be independent" in body
    assert "specification-only and default-human" in body
    for route in (
        "agent-resolved",
        "agent-reviewed",
        "human-review-required",
        "blocked",
    ):
        assert f"`{route}`" in body
    assert "Never approve or merge the proposal you route" in body
    assert "Never create, infer, widen, or materialize a human approval" in body
    assert "Never promote an autonomy class from a single successful decision" in body


def test_science_and_change_loops_handoff_product_judgments() -> None:
    science_skill = (
        ROOT / ".github" / "skills" / "science-research" / "SKILL.md"
    ).read_text(encoding="utf-8")
    change_loop = (AGENTS / "praxys-change-loop.agent.md").read_text(
        encoding="utf-8"
    )
    normalized_change_loop = _normalized(change_loop)

    assert "Praxys Product Policy" in science_skill
    assert ".github/agents/product-policy.agent.md" in science_skill
    assert "schema_version: 2" in science_skill
    assert "must not substitute scientific prohibitions" in science_skill
    assert "Praxys Product Policy" in change_loop
    assert "before editing implementation code" in normalized_change_loop
    assert "Praxys Decision Review Router" in change_loop
    assert (
        "Do not decide that your own proposal can skip review"
        in normalized_change_loop
    )
