"""Contracts for the public science contribution and review workflow."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
ISSUE_FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "science-correction.yml"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "science-change.md"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
SCIENCE_REVIEWER = ROOT / ".claude" / "agents" / "science-reviewer.md"
CONTRIBUTING = ROOT / "docs" / "science" / "contributing.md"
README = ROOT / "README.md"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_science_correction_form_captures_evidence_without_code() -> None:
    """The public form collects the minimum context needed for a review."""
    form = yaml.safe_load(_source(ISSUE_FORM))
    body = {item.get("id"): item for item in form["body"] if "id" in item}

    assert set(form["labels"]) == {
        "science",
        "evidence review",
        "science correction",
    }
    for field in (
        "challenged_claim",
        "affected_surface",
        "proposed_correction",
        "sources",
        "applicability",
        "conflicts_and_limitations",
        "product_impact",
        "urgency",
    ):
        assert body[field]["validations"]["required"] is True
    assert "contributor_role" in body
    assert "conflicts_of_interest" in body


def test_science_change_template_preserves_traceability_and_parity() -> None:
    """Scientific implementation PRs must expose their evidence and limits."""
    source = _source(PR_TEMPLATE)

    for requirement in (
        "linked evidence review",
        "linked science decision record",
        "verification levels",
        "model version and migration behavior",
        "docs/science/",
        "miniapp parity",
        "english and chinese",
        "validation/falsification",
        "science-reviewer",
        "api-contract-reviewer",
        "avg_power",
    ):
        assert requirement in source.lower()


def test_science_review_is_layered_and_human_owned() -> None:
    """The public guide and local reviewer state their separate boundaries."""
    guide = _source(CONTRIBUTING)
    reviewer = _source(SCIENCE_REVIEWER)
    codeowners = _source(CODEOWNERS)
    normalized_guide = " ".join(guide.lower().split())

    for layer in (
        "deterministic checks",
        "research-capable review",
        "human science approval",
        "no configured independent science reviewer",
        "verification:",
        "superseded",
        "urgent safety correction",
    ):
        assert layer in normalized_guide
    assert "External source content: not verified" in reviewer
    assert "recorded verification level" in reviewer
    assert "missing entries, duplicate entries, unknown citation IDs" in reviewer
    assert "does **not** duplicate citation metadata" in reviewer
    for science_path in (
        "/analysis/",
        "/data/science/",
        "/docs/science/",
        "/web/src/components/ScienceNote.tsx",
        "/web/src/pages/Science.tsx",
        "/miniapp/pages/science/",
        "/.github/ISSUE_TEMPLATE/science-correction.yml",
        "/.github/PULL_REQUEST_TEMPLATE/science-change.md",
        "/.claude/agents/science-reviewer.md",
    ):
        assert science_path in codeowners


def test_science_contribution_guide_is_linked_from_readme() -> None:
    """Coaches and scientists can find the guide without developer docs."""
    assert "docs/science/contributing.md" in _source(README)
