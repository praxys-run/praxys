"""Regression tests for the change-loop outcome observer contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "change-loop-outcomes.md"


def test_outcome_observer_uses_issue_first_readiness_attribution() -> None:
    """Reports must measure real loop stages instead of raw PR creation noise."""
    workflow = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert "### A. Change-loop issue cohort" in workflow
    assert "first `agent-ready` timestamp and actor" in workflow
    assert "first readiness boundary" in workflow
    assert "Do not use PR creation as the readiness boundary for a draft PR." in workflow
    assert "`action_required` with no jobs is `approval-gated`" in workflow
    assert "`baseline/default-branch`" in workflow
    assert "checks: read" in workflow


def test_outcome_observer_separates_tests_and_gates_autonomy_evidence() -> None:
    """Smoke tests and weak samples must not distort quality or autonomy advice."""
    workflow = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    flattened = " ".join(workflow.split())

    assert "### Operational exercises" in workflow
    assert (
        "Exclude them from acceptance, rejection, quality, latency, and autonomy"
        in flattened
    )
    assert "at least five completed non-test PRs" in workflow
    assert "no recorded correction after first readiness" in workflow
    assert "Never recommend immediate auto-merge" in workflow
    assert "`schema_version: 2`" in workflow


def test_outcome_observer_reserves_time_to_emit_a_report() -> None:
    """Evidence gathering must finish before the workflow runtime is exhausted."""
    workflow = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    flattened = " ".join(workflow.split())

    assert "timeout-minutes: 20" in workflow
    assert "Stop starting new evidence queries after 12 minutes" in flattened
    assert "mark unresolved fields `unknown`" in flattened
    assert (
        "at most one bounded log excerpt per distinct failure signature" in flattened
    )
