"""Static safeguards for selective-review automation."""
from pathlib import Path

from scripts.selective_review_gate import (
    _changes_requested,
    _parse_time,
    _ready_head_sha,
    _trusted_assignment_matches,
)


ROOT = Path(__file__).resolve().parent.parent


def test_selective_review_workflow_is_default_off_and_never_bypasses():
    workflow = (
        ROOT / ".github" / "workflows" / "selective-review.yml"
    ).read_text(encoding="utf-8")
    assert "PRAXYS_SELECTIVE_REVIEW_ENABLED" in workflow
    assert "PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH" in workflow
    assert "actions/create-github-app-token@v2" in workflow
    assert "scripts/selective_review_gate.py" in workflow
    assert "gh pr merge" in workflow
    assert "--auto" in workflow
    assert "--match-head-commit" in workflow
    assert "BASE_REF" in workflow
    assert "BASE_SHA" in workflow
    assert "-f commit_id=\"$HEAD_SHA\"" in workflow
    assert "group: selective-review-${{" in workflow
    assert workflow.count(
        "actions/variables/PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH"
    ) == 2
    assert "set -euo pipefail" in workflow
    assert "steps.policy-token.outputs.app-slug" in workflow
    assert "Require the policy App for targeted pull requests" in workflow
    assert workflow.count("context=selective-review-policy") == 3
    assert "-f state=pending" in workflow
    assert "-f state=success" in workflow
    assert "-f state=failure" in workflow
    revoke_script = (
        ROOT / ".github" / "scripts" / "revoke-selective-review.sh"
    ).read_text(encoding="utf-8")
    assert "(.user.login // \"\") | ascii_downcase" in revoke_script
    assert "--disable-auto" in revoke_script
    assert "REQUEST_CHANGES" in revoke_script
    assert "always()" in workflow
    assert "previous_filename" in (
        ROOT / "scripts" / "selective_review_gate.py"
    ).read_text(encoding="utf-8")
    assert "changed_file_list_complete" in (
        ROOT / "scripts" / "selective_review_gate.py"
    ).read_text(encoding="utf-8")
    assert "python scripts/validate_review_policy.py" in (
        ROOT / ".github" / "workflows" / "ci-backend.yml"
    ).read_text(encoding="utf-8")
    assert "--admin" not in workflow

    emergency = (
        ROOT
        / ".github"
        / "workflows"
        / "selective-review-emergency-stop.yml"
    ).read_text(encoding="utf-8")
    assert "steps.policy-token.outputs.app-slug" in emergency
    assert "(.user.login // \"\") | ascii_downcase" in emergency
    assert "--disable-auto" in emergency
    assert "REQUEST_CHANGES" in emergency
    assert "sort_by(.submitted_at) | last" in emergency
    assert "--admin" not in emergency

    issue_guard = (
        ROOT / ".github" / "workflows" / "selective-review-issue-guard.yml"
    ).read_text(encoding="utf-8")
    assert "types: [closed, reopened, assigned, unassigned, labeled, unlabeled" in issue_guard
    assert "gh workflow run selective-review.yml" in issue_guard
    assert "context=selective-review-policy" in issue_guard
    assert "group: selective-review-${{ matrix.pr_number }}" in issue_guard
    assert "cancel-in-progress: true" in issue_guard


def test_policy_tuner_can_only_open_draft_proposal_prs():
    source = (
        ROOT / ".github" / "workflows" / "change-loop-policy-tuner.md"
    ).read_text(encoding="utf-8")
    allowed_block = source.split("allowed-files:", 1)[1].split("\n  noop:", 1)[0]
    assert "draft: true" in source
    assert "config/agent-loop-policy-proposals.json" in source
    assert "config/agent-loop-policies.json" not in allowed_block
    assert "merge-pull-request" not in source
    assert "submit-pull-request-review" not in source
    assert (
        ROOT / ".github" / "workflows" / "change-loop-policy-tuner.lock.yml"
    ).exists()


def test_ready_handoff_is_bound_to_the_head_sha():
    timeline = [
        {"event": "committed", "sha": "head-a"},
        {"event": "ready_for_review"},
        {"event": "committed", "sha": "head-b"},
    ]
    assert _ready_head_sha(timeline) == "head-a"

    timeline.append({"event": "ready_for_review"})
    assert _ready_head_sha(timeline) == "head-b"


def test_comment_review_does_not_clear_requested_changes():
    reviews = [
        {
            "user": {"login": "reviewer"},
            "submitted_at": "2026-07-25T10:00:00Z",
            "state": "CHANGES_REQUESTED",
        },
        {
            "user": {"login": "reviewer"},
            "submitted_at": "2026-07-25T10:05:00Z",
            "state": "COMMENTED",
        },
    ]
    assert _changes_requested(reviews) is True

    reviews.append(
        {
            "user": {"login": "reviewer"},
            "submitted_at": "2026-07-25T10:10:00Z",
            "state": "APPROVED",
        }
    )
    assert _changes_requested(reviews) is False

    policy_reviews = [
        {
            "user": {"login": "policy-app[bot]"},
            "submitted_at": "2026-07-25T10:15:00Z",
            "state": "CHANGES_REQUESTED",
            "body": "Human review required. (selective-review-revoked)",
        }
    ]
    assert not _changes_requested(
        policy_reviews,
        policy_app_login="policy-app[bot]",
    )


def test_agent_ready_provenance_requires_the_assigned_pr():
    pr_created_at = _parse_time("2026-07-25T10:02:00Z")
    assert pr_created_at is not None
    valid_timeline = [
        {
            "event": "assigned",
            "created_at": "2026-07-25T10:00:00Z",
            "actor": {"login": "maintainer"},
            "assignee": {"login": "Copilot"},
        },
        {
            "event": "cross-referenced",
            "created_at": "2026-07-25T10:02:05Z",
            "actor": {"login": "Copilot"},
            "source": {
                "issue": {
                    "number": 50,
                    "pull_request": {"url": "https://api.github.test/pulls/50"},
                }
            },
        },
    ]
    assert _trusted_assignment_matches(
        valid_timeline,
        pr_number=50,
        pr_created_at=pr_created_at,
        trusted_assignment_actors={"maintainer"},
        assignment_assignee_login="Copilot",
        pr_author_login="Copilot",
        pr_api_url="https://api.github.test/pulls/50",
        maximum_assignment_to_pr_minutes=30,
        maximum_pr_cross_reference_minutes=10,
    )

    wrong_pr_timeline = [
        valid_timeline[0],
        {
            "event": "cross-referenced",
            "created_at": "2026-07-25T10:01:00Z",
            "actor": {"login": "Copilot"},
            "source": {
                "issue": {
                    "number": 50,
                    "pull_request": {
                        "url": "https://api.github.test/other/pulls/50"
                    },
                }
            },
        },
        valid_timeline[1],
    ]
    assert not _trusted_assignment_matches(
        wrong_pr_timeline,
        pr_number=50,
        pr_created_at=pr_created_at,
        trusted_assignment_actors={"maintainer"},
        assignment_assignee_login="Copilot",
        pr_author_login="Copilot",
        pr_api_url="https://api.github.test/pulls/50",
        maximum_assignment_to_pr_minutes=30,
        maximum_pr_cross_reference_minutes=10,
    )

    unassigned_timeline = [
        valid_timeline[0],
        {
            "event": "unassigned",
            "created_at": "2026-07-25T10:01:30Z",
            "actor": {"login": "maintainer"},
            "assignee": {"login": "Copilot"},
        },
        valid_timeline[1],
    ]
    assert not _trusted_assignment_matches(
        unassigned_timeline,
        pr_number=50,
        pr_created_at=pr_created_at,
        trusted_assignment_actors={"maintainer"},
        assignment_assignee_login="Copilot",
        pr_author_login="Copilot",
        pr_api_url="https://api.github.test/pulls/50",
        maximum_assignment_to_pr_minutes=30,
        maximum_pr_cross_reference_minutes=10,
    )
