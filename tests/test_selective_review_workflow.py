"""Static safeguards for selective-review automation."""
from pathlib import Path

from scripts.selective_review_gate import (
    _changes_requested,
    _parse_time,
    _policy_state_present,
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
    assert "actions/create-github-app-token@v3" in workflow
    assert "actions/create-github-app-token@v2" not in workflow
    assert "scripts/selective_review_gate.py" in workflow
    assert "gh pr merge" in workflow
    assert "--auto" in workflow
    assert "--match-head-commit" in workflow
    assert "BASE_REF" in workflow
    assert "BASE_SHA" in workflow
    assert "-f commit_id=\"$HEAD_SHA\"" in workflow
    assert "group: selective-review-${{" in workflow
    assert "actions/variables/PRAXYS_SELECTIVE_REVIEW" not in workflow
    assert workflow.count(
        "RUNTIME_ENABLED: ${{ vars.PRAXYS_SELECTIVE_REVIEW_ENABLED }}"
    ) == 2
    assert workflow.count(
        "RUNTIME_KILL_SWITCH: ${{ vars.PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH }}"
    ) == 3
    assert "set -euo pipefail" in workflow
    assert "steps.policy-token.outputs.app-slug" in workflow
    assert "Require the policy App for targeted pull requests" not in workflow
    assert "Require the policy App for autonomous action or cleanup" in workflow
    assert "steps.policy.outputs.needs_policy_app == 'true'" in workflow
    assert "vars.PRAXYS_REVIEW_POLICY_APP_SLUG" in workflow
    assert "id: policy-app" in workflow
    assert 'if [[ -z "$EXPECTED_POLICY_APP_SLUG" ]]' in workflow
    assert '"$POLICY_APP_SLUG" != "$EXPECTED_POLICY_APP_SLUG"' in workflow
    assert workflow.count("steps.policy-app.outcome == 'success'") == 6
    assert "REQUIRE_POLICY_STATE: ${{ steps.policy.outputs.policy_state_present }}" in workflow
    assert "Selective review was emergency-stopped before policy completion." in workflow
    assert 'actions/variables?per_page=100' not in workflow
    safe_step = workflow.split("Mark policy gate safe", 1)[1].split(
        "Revoke policy state after action failure", 1
    )[0]
    assert "RUNTIME_KILL_SWITCH: ${{ vars.PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH }}" in safe_step
    assert "2>/dev/null || printf 'false'" not in workflow
    assert workflow.index("Mark policy gate safe") < workflow.index(
        "Revoke policy state after action failure"
    )
    assert workflow.index("Evaluate deterministic review policy") < workflow.index(
        "Mint independent policy App token"
    )
    assert "Require the same exact refs after privileged setup" in workflow
    assert 'FINAL_HEAD_SHA" != "$INITIAL_HEAD_SHA' in workflow
    assert 'FINAL_BASE_SHA" != "$INITIAL_BASE_SHA' in workflow
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
    assert "REQUIRE_POLICY_STATE" in revoke_script
    assert "selective-review-(revoked|emergency-stop)" in revoke_script
    assert "foreign_owners" in revoke_script
    assert "unexpected bot" in revoke_script
    assert "sort_by([.submitted_at, (.id // 0)])" in revoke_script
    assert "merged during selective-review cleanup" in revoke_script
    assert "always()" in workflow
    assert "previous_filename" in (
        ROOT / "scripts" / "selective_review_gate.py"
    ).read_text(encoding="utf-8")
    assert "changed_file_list_complete" in (
        ROOT / "scripts" / "selective_review_gate.py"
    ).read_text(encoding="utf-8")
    assert "python scripts/validate_review_policy.py" in (
        ROOT / ".github" / "workflows" / "ci-premerge.yml"
    ).read_text(encoding="utf-8")
    assert "--admin" not in workflow
    assert "Require translation validation for generated i18n PRs" in workflow
    assert "github-actions[bot]" in workflow
    assert "i18n/refresh-zh-*" in workflow
    assert "translation-validation" in workflow
    assert "translation_state" in workflow

    emergency = (
        ROOT
        / ".github"
        / "workflows"
        / "selective-review-emergency-stop.yml"
    ).read_text(encoding="utf-8")
    assert "actions/create-github-app-token@v3" in emergency
    assert "actions/create-github-app-token@v2" not in emergency
    assert "steps.policy-token.outputs.app-slug" in emergency
    assert "vars.PRAXYS_REVIEW_POLICY_APP_SLUG" in emergency
    assert "id: policy-app" in emergency
    assert 'if [[ -z "$EXPECTED_POLICY_APP_SLUG" ]]' in emergency
    assert '"$POLICY_APP_SLUG" != "$EXPECTED_POLICY_APP_SLUG"' in emergency
    assert "if: steps.policy-app.outcome == 'success'" in emergency
    assert "statuses: write" in emergency
    assert "actions: write" in emergency
    assert "Quiesce in-flight selective-review runs" in emergency
    assert "/actions/runs/${run_id}/cancel" in emergency
    assert "did not quiesce before emergency cleanup" in emergency
    assert "Block active policy state before privileged cleanup" in emergency
    assert "Reassert emergency barriers after quiescence" in emergency
    assert "Merge races detected during emergency quiescence" in emergency
    assert "context=selective-review-policy" in emergency
    assert "-f state=failure" in emergency
    assert "steps.barrier.outputs.affected != '0'" in emergency
    assert "bash .github/scripts/revoke-selective-review.sh" in emergency
    assert "REQUIRE_POLICY_STATE=true" in emergency
    assert emergency.index(
        "Block active policy state before privileged cleanup"
    ) < emergency.index("Quiesce in-flight selective-review runs")
    assert emergency.index(
        "Quiesce in-flight selective-review runs"
    ) < emergency.index("Reassert emergency barriers after quiescence")
    assert emergency.index(
        "Reassert emergency barriers after quiescence"
    ) < emergency.index("Mint independent policy App token")
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


def test_policy_tuner_rejects_stale_or_duplicate_proposals():
    source = (
        ROOT / ".github" / "workflows" / "change-loop-policy-tuner.md"
    ).read_text(encoding="utf-8")
    for path in (
        "analysis/review_policy.py",
        "scripts/selective_review_gate.py",
        "tests/test_review_policy.py",
        "tests/test_selective_review_workflow.py",
    ):
        assert path in source
    assert "active selective-review `version` and `classifier_semantics`" in source
    assert "predates those semantics" in source
    assert "already enforced" in source
    assert "emit `noop`" in source
    assert "`current_policy_gap`" in source


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
            "user": {"login": "policy-app[bot]", "type": "Bot"},
            "submitted_at": "2026-07-25T10:15:00Z",
            "state": "CHANGES_REQUESTED",
            "body": "Human review required. (selective-review-revoked)",
        }
    ]
    assert not _changes_requested(
        policy_reviews,
        policy_app_login="policy-app[bot]",
    )

    assert _changes_requested(policy_reviews) is True


def test_only_bot_authored_policy_markers_trigger_stale_state_cleanup():
    marker = (
        "Approved by the independent selective-review policy App. "
        "(selective-review:selective-review-v1:"
        "0123456789abcdef0123456789abcdef01234567)"
    )
    human_review = {
        "user": {"login": "reviewer", "type": "User"},
        "submitted_at": "2026-07-25T10:00:00Z",
        "state": "APPROVED",
        "body": marker,
    }
    assert not _policy_state_present(
        [human_review],
        auto_merge_enabled=False,
    )

    app_approval = {
        **human_review,
        "user": {"login": "policy-app[bot]", "type": "Bot"},
    }
    assert _policy_state_present(
        [app_approval],
        auto_merge_enabled=False,
    )

    app_revocation = {
        "user": {"login": "policy-app[bot]", "type": "Bot"},
        "submitted_at": "2026-07-25T10:05:00Z",
        "state": "CHANGES_REQUESTED",
        "body": "Human review required. (selective-review-revoked)",
    }
    assert not _policy_state_present(
        [app_approval, app_revocation],
        auto_merge_enabled=False,
    )
    assert _policy_state_present(
        [app_approval, app_revocation],
        auto_merge_enabled=True,
    )

    dismissed_approval = {
        **app_approval,
        "state": "DISMISSED",
        "submitted_at": "2026-07-25T10:10:00Z",
    }
    assert not _policy_state_present(
        [dismissed_approval],
        auto_merge_enabled=False,
    )
    assert _policy_state_present(
        [dismissed_approval],
        auto_merge_enabled=True,
    )

    same_second_revocation = {
        **app_revocation,
        "id": 101,
        "submitted_at": "2026-07-25T10:15:00Z",
    }
    same_second_approval = {
        **app_approval,
        "id": 102,
        "submitted_at": "2026-07-25T10:15:00Z",
    }
    assert _policy_state_present(
        [same_second_revocation, same_second_approval],
        auto_merge_enabled=False,
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
