"""Tests for deterministic selective-review and promotion policy."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from analysis.review_policy import (
    PromotionObservation,
    PullRequestFacts,
    ReviewDecision,
    apply_runtime_controls,
    class_policy_fingerprint,
    classify_change,
    evaluate_promotion,
    evaluate_selective_review,
    validate_promoted_classes,
)


POLICY = {
    "version": "selective-review-test-v1",
    "classifier_semantics": "review-policy-test-v1",
    "default_decision": "review-required",
    "enforcement_model": "independent-github-app-approval",
    "allowed_authors": ["Copilot"],
    "allowed_base_branches": ["main"],
    "trusted_assignment_actors": ["maintainer"],
    "assignment_assignee_login": "Copilot",
    "maximum_assignment_to_pr_minutes": 30,
    "maximum_pr_cross_reference_minutes": 10,
    "disqualifying_issue_labels": ["backlog", "later"],
    "required_checks": ["backend-tests"],
    "merge_gate_status": "selective-review-policy",
    "sensitive_paths": [".github/**", "db/**", "alembic/**", "docs/ops/**"],
    "promoted_classes": [],
    "candidate_classes": {
        "documentation-only": {
            "allowed_paths": ["docs/**"],
            "denied_paths": ["docs/ops/**"],
            "test_policy": "not-applicable",
        },
        "translation-catalog-only": {
            "allowed_paths": ["web/src/locales/**"],
            "denied_paths": [],
            "test_policy": "not-applicable",
        },
    },
}


def _facts(**overrides):
    values = {
        "author_login": "Copilot",
        "base_repository": "praxys-run/praxys",
        "base_ref": "main",
        "base_sha": "base123",
        "head_repository": "praxys-run/praxys",
        "is_draft": False,
        "changed_files": ("docs/dev/architecture.md",),
        "changed_file_list_complete": True,
        "check_states": {"backend-tests": "success"},
        "head_sha": "abc123",
        "ready_head_sha": "abc123",
        "changes_requested": False,
        "agent_ready_issue_linked": True,
        "repository_auto_merge_enabled": True,
        "required_approving_review_count": 1,
        "approval_invalidated_on_push": True,
        "required_status_checks_strict": True,
    }
    values.update(overrides)
    return PullRequestFacts(**values)


def _observation(number: int, **overrides) -> PromotionObservation:
    values = {
        "pr_number": number,
        "completed": True,
        "merged": True,
        "required_checks_successful": True,
        "pr_caused_readiness_failure": False,
        "corrected_after_ready": False,
        "test_policy": "covered",
        "reverted_or_reopened": False,
        "observation_days": 8.0,
    }
    values.update(overrides)
    return PromotionObservation(**values)


def test_classifies_only_exclusive_narrow_paths():
    assert (
        classify_change(("docs/dev/a.md", "docs/user/b.md"), POLICY["candidate_classes"])
        == "documentation-only"
    )
    assert (
        classify_change(("docs/ops/change-loop.md",), POLICY["candidate_classes"])
        is None
    )
    assert (
        classify_change(
            ("web/src/locales/en/messages.po",),
            POLICY["candidate_classes"],
        )
        == "translation-catalog-only"
    )


def test_unpromoted_class_remains_review_required():
    decision = evaluate_selective_review(_facts(), POLICY)
    assert decision.disposition == "review-required"
    assert decision.change_class == "documentation-only"
    assert decision.reasons == ("class_not_promoted:documentation-only",)


def test_runtime_controls_are_default_off_and_kill_switch_closed():
    candidate = ReviewDecision(
        disposition="auto-merge-candidate",
        change_class="documentation-only",
        reasons=(),
    )
    disabled = apply_runtime_controls(
        candidate,
        enabled=False,
        kill_switch=False,
    )
    assert disabled.disposition == "review-required"
    assert disabled.reasons == ("selective_review_disabled",)

    killed = apply_runtime_controls(
        candidate,
        enabled=True,
        kill_switch=True,
    )
    assert killed.disposition == "review-required"
    assert killed.reasons == ("kill_switch_enabled",)

    enabled = apply_runtime_controls(
        candidate,
        enabled=True,
        kill_switch=False,
    )
    assert enabled == candidate


def test_promoted_class_passes_only_after_stable_handoff():
    policy = {**POLICY, "promoted_classes": ["documentation-only"]}
    assert evaluate_selective_review(_facts(), policy).disposition == (
        "auto-merge-candidate"
    )

    decision = evaluate_selective_review(
        _facts(head_sha="def456"),
        policy,
    )
    assert decision.disposition == "review-required"
    assert "commit_after_ready_for_review" in decision.reasons


def test_sensitive_paths_fail_closed_even_if_class_is_promoted():
    policy = {**POLICY, "promoted_classes": ["documentation-only"]}
    decision = evaluate_selective_review(
        _facts(changed_files=("docs/ops/change-loop.md",)),
        policy,
    )
    assert decision.disposition == "review-required"
    assert "sensitive_path_changed" in decision.reasons


def test_repository_merge_guardrails_fail_closed():
    policy = {**POLICY, "promoted_classes": ["documentation-only"]}
    decision = evaluate_selective_review(
        _facts(
            repository_auto_merge_enabled=False,
            required_approving_review_count=0,
            approval_invalidated_on_push=False,
            required_status_checks_strict=False,
        ),
        policy,
    )
    assert decision.disposition == "review-required"
    assert "repository_auto_merge_disabled" in decision.reasons
    assert "independent_approval_not_required" in decision.reasons
    assert "stale_policy_approval_not_invalidated" in decision.reasons
    assert "required_checks_do_not_require_latest_base" in decision.reasons


def test_pr_must_close_an_agent_ready_issue():
    policy = {**POLICY, "promoted_classes": ["documentation-only"]}
    decision = evaluate_selective_review(
        _facts(agent_ready_issue_linked=False),
        policy,
    )
    assert decision.disposition == "review-required"
    assert "agent_ready_issue_not_linked" in decision.reasons


def test_base_and_changed_file_inventory_must_be_trusted():
    policy = {**POLICY, "promoted_classes": ["documentation-only"]}
    decision = evaluate_selective_review(
        _facts(base_ref="release", changed_file_list_complete=False),
        policy,
    )
    assert decision.disposition == "review-required"
    assert "base_branch_not_allowed" in decision.reasons
    assert "changed_file_list_incomplete" in decision.reasons


def test_promotion_requires_five_clean_observed_prs():
    requirements = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": 7,
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    clean = [_observation(number) for number in range(1, 6)]
    assert evaluate_promotion(clean, requirements).eligible is True

    corrected = [*clean[:-1], _observation(5, corrected_after_ready=True)]
    assessment = evaluate_promotion(corrected, requirements)
    assert assessment.eligible is False
    assert "correction_rate_above_limit" in assessment.reasons


def test_duplicate_prs_cannot_satisfy_promotion_sample_size():
    requirements = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": 7,
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    duplicated = [_observation(1) for _ in range(5)]
    assessment = evaluate_promotion(duplicated, requirements)
    assert assessment.eligible is False
    assert "duplicate_pr_observations:4" in assessment.reasons
    assert "insufficient_completed_prs:1/5" in assessment.reasons


def test_required_test_class_rejects_not_applicable_evidence():
    requirements = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": 7,
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    observations = [
        _observation(number, test_policy="not-applicable")
        for number in range(1, 6)
    ]
    assessment = evaluate_promotion(
        observations,
        requirements,
        class_test_policy="required",
    )
    assert assessment.eligible is False
    assert "test_policy_rate_below_minimum" in assessment.reasons


def test_promoted_class_without_evidence_is_rejected():
    policy = {
        "change": {
            "selective_review": {
                **POLICY,
                "promoted_classes": ["documentation-only"],
                "promotion_requirements": {
                    "minimum_completed_prs": 5,
                    "minimum_observation_days": 7,
                    "maximum_correction_rate": 0.0,
                    "maximum_pr_caused_failure_rate": 0.0,
                    "maximum_revert_or_reopen_rate": 0.0,
                    "minimum_test_policy_rate": 1.0,
                },
            }
        }
    }
    with pytest.raises(ValueError, match="promotion_evidence_missing"):
        validate_promoted_classes(policy, {"classes": {}})


def test_promotion_thresholds_cannot_be_weakened():
    policy = {
        "change": {
            "selective_review": {
                **POLICY,
                "promotion_requirements": {
                    "minimum_completed_prs": 0,
                    "minimum_observation_days": 0,
                    "maximum_correction_rate": 1.0,
                    "maximum_pr_caused_failure_rate": 1.0,
                    "maximum_revert_or_reopen_rate": 1.0,
                    "minimum_test_policy_rate": 0.0,
                },
            }
        }
    }
    with pytest.raises(ValueError, match="minimum_completed_prs_below_floor"):
        validate_promoted_classes(policy, {"classes": {}})


def test_promotion_requires_the_independent_app_approval_model():
    selective = deepcopy(POLICY)
    selective["enforcement_model"] = "status-check"
    selective["promotion_requirements"] = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": 7,
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    with pytest.raises(
        ValueError,
        match="enforcement_model_must_use_independent_app_approval",
    ):
        validate_promoted_classes(
            {"change": {"selective_review": selective}},
            {"classes": {}},
        )


def test_promotion_evidence_is_bound_to_the_exact_class_policy():
    requirements = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": 7,
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    selective = deepcopy(POLICY)
    selective["promoted_classes"] = ["documentation-only"]
    selective["promotion_requirements"] = requirements
    policy = {"change": {"selective_review": selective}}
    observations = [asdict(_observation(number)) for number in range(1, 6)]
    evidence = {
        "classes": {
            "documentation-only": {
                "policy_fingerprint": class_policy_fingerprint(
                    selective,
                    "documentation-only",
                ),
                "observations": observations,
            },
            "translation-catalog-only": {
                "policy_fingerprint": class_policy_fingerprint(
                    selective,
                    "translation-catalog-only",
                ),
                "observations": [],
            },
        }
    }
    assert validate_promoted_classes(policy, evidence)[
        "documentation-only"
    ].eligible

    selective["candidate_classes"]["documentation-only"]["allowed_paths"] = ["**"]
    with pytest.raises(ValueError, match="policy_fingerprint_mismatch"):
        validate_promoted_classes(policy, evidence)


def test_promotion_rejects_non_finite_thresholds_and_invalid_rows():
    requirements = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": float("nan"),
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    assessment = evaluate_promotion(
        [_observation(1, observation_days=float("nan"))],
        requirements,
    )
    assert assessment.eligible is False
    assert "minimum_observation_days_not_finite_number" in assessment.reasons

    requirements["minimum_observation_days"] = 7
    assessment = evaluate_promotion(
        [_observation(1.5), _observation(2, merged="false")],
        requirements,
    )
    assert assessment.eligible is False
    assert any(reason.startswith("invalid_observation:") for reason in assessment.reasons)


def test_same_pr_cannot_supply_evidence_for_multiple_classes():
    selective = deepcopy(POLICY)
    selective["promoted_classes"] = []
    selective["promotion_requirements"] = {
        "minimum_completed_prs": 5,
        "minimum_observation_days": 7,
        "maximum_correction_rate": 0.0,
        "maximum_pr_caused_failure_rate": 0.0,
        "maximum_revert_or_reopen_rate": 0.0,
        "minimum_test_policy_rate": 1.0,
    }
    row = asdict(_observation(42))
    evidence = {
        "classes": {
            name: {
                "policy_fingerprint": class_policy_fingerprint(selective, name),
                "observations": [row],
            }
            for name in selective["candidate_classes"]
        }
    }
    with pytest.raises(ValueError, match="pr_observed_in_multiple_classes:42"):
        validate_promoted_classes(
            {"change": {"selective_review": selective}},
            evidence,
        )


def test_checked_in_review_policy_is_valid():
    root = Path(__file__).resolve().parent.parent
    policy = json.loads(
        (root / "config" / "agent-loop-policies.json").read_text()
    )
    evidence = json.loads(
        (
            root
            / "data"
            / "agent_evals"
            / "change"
            / "review_promotion.json"
        ).read_text()
    )
    assert validate_promoted_classes(policy, evidence) == {}
