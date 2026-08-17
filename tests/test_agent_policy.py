"""Regression coverage for the shared change-loop decision policy."""
from __future__ import annotations

import json
from pathlib import Path

from analysis.agent_policy import (
    AGENT_READY_POLICY_NAME,
    AGENT_READY_POLICY_VERSION,
    AgentReadyFacts,
    evaluate_agent_ready,
)
from analysis.agent_replay import (
    replay_agent_eligibility_cases,
    replay_agent_ready_cases,
)
from api import feedback_scrub


ROOT = Path(__file__).resolve().parent.parent


def test_agent_ready_policy_is_default_deny_and_language_aware() -> None:
    """Only detailed, actionable, non-sensitive bugs enter the change loop."""
    assert evaluate_agent_ready(
        AgentReadyFacts("bug", False, True, 1, 18)
    ).eligible
    assert not evaluate_agent_ready(
        AgentReadyFacts("bug", False, True, 1, 12)
    ).eligible
    assert not evaluate_agent_ready(
        AgentReadyFacts("feature", False, True, 10, 40)
    ).eligible
    assert not evaluate_agent_ready(
        AgentReadyFacts("bug", True, True, 10, 40)
    ).eligible


def test_checked_in_agent_ready_replay_has_no_regressions() -> None:
    """Human-correction seed cases must remain correct in CI."""
    payload = json.loads(
        (
            ROOT / "data" / "agent_evals" / "change" / "agent_ready.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["policy_name"] == AGENT_READY_POLICY_NAME
    assert payload["policy_version"] == AGENT_READY_POLICY_VERSION
    result = replay_agent_ready_cases(payload["cases"])
    assert result.total >= 5
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.accuracy == 1.0


def test_semantic_agent_eligibility_corpus_is_privacy_safe_and_scoreable() -> None:
    """Model cases are public-safe and the pure scorer reports both error types."""
    payload = json.loads(
        (
            ROOT / "data" / "agent_evals" / "change" / "agent_eligibility.json"
        ).read_text(encoding="utf-8")
    )
    cases = payload["cases"]
    assert payload["prompt_family"] == "feedback-triage"
    assert len(cases) >= 8
    assert all("priority" not in case for case in cases)
    for case in cases:
        assert feedback_scrub.scrub_text(case["message"]) == case["message"]
        image_description = case.get("image_description")
        if image_description:
            assert (
                feedback_scrub.scrub_text(image_description)
                == image_description
            )

    predictions = {
        case["id"]: bool(case["expected_agent_eligible"])
        for case in cases
    }
    predictions[cases[0]["id"]] = False
    result = replay_agent_eligibility_cases(
        cases,
        lambda case: predictions[case["id"]],
    )
    assert result.total == len(cases)
    assert result.false_negatives == 1
    assert result.false_positives == 0
    assert result.unavailable == 0


def test_policy_config_matches_production_and_starts_default_deny() -> None:
    """Repository policy metadata must not drift from executable policy."""
    payload = json.loads(
        (ROOT / "config" / "agent-loop-policies.json").read_text(encoding="utf-8")
    )
    assert payload["operating_model"] == {
        "path": "config/agentic-operating-model.json",
        "version": "praxys-agentic-operating-model-v1",
        "status": "active-routing",
    }
    autonomy = payload["decision_autonomy"]
    assert autonomy["status"] == "specification-only"
    assert autonomy["default_judgment_route"] == "human-review-required"
    assert autonomy["routing_outcomes"] == [
        "agent-resolved",
        "agent-reviewed",
        "human-review-required",
        "blocked",
    ]
    assert autonomy["agent_reviewed_classes"] == []
    assert autonomy["agent_reviewed_requirements"] == {
        "class_must_be_explicitly_listed": True,
        "reviewer_assignment_source": "work-router-independent-reviewers",
        "minimum_independent_reviews": 1,
        "reviewer_must_differ_from_proposer_and_executor": True,
        "triggered_roles_must_be_assigned": True,
        "deterministic_validation_required": True,
        "decision_record_digest_required": True,
        "human_review_factor_must_be_absent": True,
    }
    assert autonomy["promoted_judgment_classes"] == []
    assert autonomy["independence"] == {
        "proposer_may_select_own_review_route": False,
        "proposer_may_review_own_decision": False,
        "executor_may_verify_own_high_risk_work": False,
        "router_may_approve": False,
        "agent_may_materialize_human_approval": False,
    }
    assert {
        "new-product-promise",
        "sensitive-data-collection",
        "irreversible-or-high-blast-radius-action",
    } <= set(autonomy["human_review_factors"])
    assert payload["change"]["agent_ready"] == {
        "policy_name": AGENT_READY_POLICY_NAME,
        "version": AGENT_READY_POLICY_VERSION,
        "active_prompt_version": "v1",
        "challenger_prompt_versions": ["v2"],
    }
    review = payload["change"]["selective_review"]
    assert review["default_decision"] == "review-required"
    assert review["promoted_classes"] == []


def test_deploy_owns_agent_ready_runtime_controls() -> None:
    """Optional App Service controls must come from repository variables."""
    workflow = (
        ROOT / ".github" / "workflows" / "deploy-backend.yml"
    ).read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in (
        "PRAXYS_AGENT_READY_SHADOW",
        "PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION",
    ):
        assert f"{name}: ${{{{ vars.{name} }}}}" in workflow
        assert f'{name}="${{{name}}}"' in workflow
        assert name in env_example
