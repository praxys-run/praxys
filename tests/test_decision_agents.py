"""Contract checks for role agents and control-plane routers."""

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


def test_role_agent_manifests_are_available_and_bounded() -> None:
    expectations = {
        "product.agent.md": (
            "Praxys Product",
            "Product Decision Record",
            "Do not implement production behavior",
        ),
        "design.agent.md": (
            "Praxys Design",
            "Experience Specification",
            "Do not implement backend behavior",
        ),
        "engineering.agent.md": (
            "Praxys Engineering",
            "implementation impact map",
            "Do not invent product value",
        ),
        "architecture.agent.md": (
            "Praxys Architecture",
            "Architecture Decision Record",
            "Do not choose product value",
        ),
        "quality.agent.md": (
            "Praxys Quality",
            "Verification Evidence",
            "Do not claim validation that was not performed",
        ),
        "science.agent.md": (
            "Praxys Science",
            "Science Decision Records",
            "Do not substitute scientific prohibitions",
        ),
        "trust.agent.md": (
            "Praxys Trust",
            "Trust Decision Record",
            "Never request, reveal, store, or copy secrets",
        ),
        "operations.agent.md": (
            "Praxys Operations",
            "Operations Decision Record",
            "Do not perform an unapproved high-impact production action",
        ),
        "meta-eval.agent.md": (
            "Praxys Meta/Eval",
            "Evaluation Report",
            "Do not promote autonomy from one successful decision",
        ),
    }
    for filename, (name, artifact, boundary) in expectations.items():
        metadata, body = _agent(AGENTS / filename)
        normalized = _normalized(body)
        assert metadata["name"] == name
        assert metadata["target"] == "github-copilot"
        assert metadata["user-invocable"] is True
        assert artifact in normalized
        assert boundary in normalized


def test_product_science_design_engineering_and_quality_stay_separate() -> None:
    product = _normalized(_agent(AGENTS / "product.agent.md")[1])
    science = _normalized(_agent(AGENTS / "science.agent.md")[1])
    design = _normalized(_agent(AGENTS / "design.agent.md")[1])
    engineering = _normalized(_agent(AGENTS / "engineering.agent.md")[1])
    quality = _normalized(_agent(AGENTS / "quality.agent.md")[1])
    meta = _normalized(_agent(AGENTS / "meta-eval.agent.md")[1])

    assert "Product owns what user value Praxys should provide" in science
    assert "Engineering owns its implementation" in design
    assert "Quality owns independent verification" in design
    assert "Praxys Design" in engineering
    assert "Praxys Science" in engineering
    assert "distinct from Meta/Eval" in quality
    assert "Do not replace Quality's verification" in meta


def test_decision_router_is_independent_and_default_human() -> None:
    metadata, body = _agent(AGENTS / "decision-review-router.agent.md")

    assert metadata["name"] == "Praxys Decision Review Router"
    assert metadata["tools"] == ["read", "search", "agent"]
    assert "must be independent" in body
    assert "specification-only and default-human" in body
    assert "Work Router assigned every triggered specialist role" in body
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


def test_work_router_composes_roles_without_executing() -> None:
    metadata, body = _agent(AGENTS / "work-router.agent.md")
    normalized = _normalized(body)

    assert metadata["name"] == "Praxys Work Router"
    assert metadata["tools"] == ["read", "search", "agent"]
    for slot in (
        "lead",
        "contributors",
        "independent reviewers",
        "executor",
        "verifier",
        "outcome observer",
        "human authority",
    ):
        assert slot in normalized
    assert "Do not execute, approve, or review the work you route" in normalized
    assert "different directory or technology" in normalized


def test_science_and_delivery_loops_use_role_handoffs() -> None:
    science_skill = (
        ROOT / ".github" / "skills" / "science-research" / "SKILL.md"
    ).read_text(encoding="utf-8")
    normalized_science_skill = _normalized(science_skill)
    change_loop = (AGENTS / "praxys-change-loop.agent.md").read_text(
        encoding="utf-8"
    )
    normalized_change_loop = _normalized(change_loop)

    assert "Praxys Product" in science_skill
    assert ".github/agents/product.agent.md" in science_skill
    assert "Product Decision Record" in science_skill
    assert "Science Decision Record" in science_skill
    assert (
        "must not substitute scientific prohibitions"
        in normalized_science_skill
    )
    assert "Praxys Work Router" in change_loop
    assert "Praxys Engineering" in change_loop
    assert "Praxys Quality" in change_loop
    assert "delivery loop implements accepted artifacts" in normalized_change_loop
    assert "Praxys Decision Review Router" in change_loop
    assert (
        "Do not decide that your own proposal or implementation can skip review"
        in normalized_change_loop
    )
