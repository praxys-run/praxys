"""Regression tests for the change-loop assignment workflow."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "assign-copilot.yml"
READINESS_WORKFLOW = ROOT / ".github" / "workflows" / "copilot-pr-readiness.yml"


def test_assignment_deduplication_is_job_scoped() -> None:
    """Unrelated label events must not cancel an eligible assignment job."""
    workflow = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    workflow_prefix, jobs = workflow.split("\njobs:\n", maxsplit=1)
    assignment_job = jobs.split("  assign-to-copilot:\n", maxsplit=1)[1]

    assert "\nconcurrency:" not in workflow_prefix
    assert assignment_job.index("\n    if:") < assignment_job.index(
        "\n    concurrency:"
    )
    assert "group: assign-copilot-${{ github.event.issue.number }}" in assignment_job
    assert "cancel-in-progress: true" in assignment_job


def test_assignment_selects_the_praxys_orchestrator_custom_agent() -> None:
    """Agent-ready issues must not fall back to the generic Copilot profile."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "GraphQL-Features: issues_copilot_assignment_api_support" in workflow
    assert "agentAssignment:" in workflow
    assert "customAgent:$customAgent" in workflow
    assert "-F customAgent=praxys-orchestrator" in workflow
    assert "-F baseRef=main" in workflow


def test_copilot_readiness_guard_restores_draft_invariants() -> None:
    """Ready Copilot PRs must have preflight evidence and green required checks."""
    workflow = READINESS_WORKFLOW.read_text(encoding="utf-8")

    assert "types: [ready_for_review, synchronize]" in workflow
    assert "github.event.pull_request.user.login == 'Copilot'" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "python scripts/agent_preflight.py --base origin/main" in workflow
    assert "Preflight head:" in workflow
    assert "github.event.pull_request.head.sha" in workflow
    assert "github.event.pull_request.updated_at" in workflow
    assert 'REQUIRED_CHECKS_JSON: \'["backend-tests","frontend-quality"]\'' in workflow
    assert "always() &&" in workflow
    assert workflow.count('gh pr ready "$PR_NUMBER"') == 2
    assert workflow.count("--undo") == 2