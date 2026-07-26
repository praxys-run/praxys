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
from analysis.agent_replay import replay_agent_ready_cases


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


def test_policy_config_matches_production_and_starts_default_deny() -> None:
    """Repository policy metadata must not drift from executable policy."""
    payload = json.loads(
        (ROOT / "config" / "agent-loop-policies.json").read_text(encoding="utf-8")
    )
    assert payload["change"]["agent_ready"] == {
        "policy_name": AGENT_READY_POLICY_NAME,
        "version": AGENT_READY_POLICY_VERSION,
    }
    review = payload["change"]["selective_review"]
    assert review["default_decision"] == "review-required"
    assert review["promoted_classes"] == []
