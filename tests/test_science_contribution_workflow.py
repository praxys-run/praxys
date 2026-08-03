"""Contracts for the public science contribution and review workflow."""

from pathlib import Path

import yaml

from analysis.evidence_registry import EvidenceReview


ROOT = Path(__file__).resolve().parent.parent
ISSUE_FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "science-correction.yml"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "science-change.md"
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
SCIENCE_REVIEWER = ROOT / ".claude" / "agents" / "science-reviewer.md"
CONTRIBUTING = ROOT / "docs" / "science" / "contributing.md"
README = ROOT / "README.md"
SAMPLE_EVIDENCE_REVIEW = (
    ROOT
    / "data"
    / "science"
    / "evidence"
    / "heat-adaptation"
    / "evidence-heat-adaptation-v1.yaml"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _codeowners_for(path: str) -> list[str]:
    owners: list[str] = []
    for raw_line in _source(CODEOWNERS).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *candidate_owners = line.split()
        normalized = pattern.lstrip("/")
        if (
            (pattern.endswith("/") and path.startswith(normalized))
            or path == normalized
        ):
            owners = candidate_owners
    return owners


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
        "not currently a ruleset-enforced approval gate",
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
        "/web/src/components/HeatAdaptationPanel.tsx",
        "/web/src/components/RecoveryPanel.tsx",
        "/web/src/components/ManagedPlanSettingsCard.tsx",
        "/web/src/components/charts/",
        "/web/src/contexts/ScienceContext.tsx",
        "/web/src/pages/Science.tsx",
        "/web/src/pages/Training.tsx",
        "/miniapp/pages/science/",
        "/miniapp/pages/training/",
        "/miniapp/pages/settings/",
        "/miniapp/utils/heat-adaptation.ts",
        "/.github/ISSUE_TEMPLATE/science-correction.yml",
        "/.github/PULL_REQUEST_TEMPLATE/science-change.md",
        "/.claude/agents/science-reviewer.md",
    ):
        assert science_path in codeowners


def test_science_codeowners_resolve_representative_product_surfaces() -> None:
    """Scientific claims in both clients request the current science owner."""
    for path in (
        "web/src/components/HeatAdaptationPanel.tsx",
        "web/src/components/RecoveryPanel.tsx",
        "web/src/components/ManagedPlanSettingsCard.tsx",
        "web/src/components/charts/FitnessFatigueChart.tsx",
        "web/src/contexts/ScienceContext.tsx",
        "web/src/pages/Training.tsx",
        "miniapp/pages/training/index.wxml",
        "miniapp/pages/settings/index.ts",
        "miniapp/utils/heat-adaptation.ts",
        "docs/science/contributing.md",
    ):
        assert _codeowners_for(path) == ["@dddtc2005"]


def test_documented_verification_entry_is_valid_evidence_review_yaml() -> None:
    """Contributors can paste the documented verification entry into a review."""
    guide = _source(CONTRIBUTING)
    yaml_example = guide.split("```yaml", 1)[1].split("```", 1)[0]
    review_notes = yaml.safe_load(yaml_example)["review_notes"]
    raw_review = yaml.safe_load(_source(SAMPLE_EVIDENCE_REVIEW))
    raw_review["review_notes"] = review_notes

    review = EvidenceReview.model_validate(raw_review)

    assert isinstance(review.review_notes[0], str)
    assert review.review_notes[0].startswith("Verification:")


def test_named_science_pr_template_has_a_direct_compare_link() -> None:
    """GitHub contributors can actually load the named pull-request template."""
    guide = _source(CONTRIBUTING)

    assert "/compare?expand=1&template=science-change.md" in guide


def test_science_contribution_guide_is_linked_from_readme() -> None:
    """Coaches and scientists can find the guide without developer docs."""
    assert "docs/science/contributing.md" in _source(README)
