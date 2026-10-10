"""Single-session boundaries and external authority stay explicit."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.agentic_operating_model import AgenticOperatingModel, load_agentic_operating_model
from analysis.agentic_task_routing import load_task_routing_config, validate_task_routing_references

ROOT = Path(__file__).resolve().parents[1]


def test_policy_has_one_workflow_and_distinct_review_identity():
    model = load_agentic_operating_model()
    assert model.workflow == ["understand", "implement", "verify"]
    assert len({model.executor_agent, model.reviewer_agent, model.operations_agent}) == 3
    assert model.independence.reviewer_read_only
    assert model.independence.reviewer_fresh_context
    validate_task_routing_references(load_task_routing_config(), model)


@pytest.mark.parametrize("field", ["high_risk_review_required", "reviewer_read_only", "reviewer_fresh_context"])
def test_review_independence_cannot_be_disabled(field):
    payload = load_agentic_operating_model().model_dump()
    payload["independence"][field] = False
    with pytest.raises(ValidationError):
        AgenticOperatingModel.model_validate(payload)


def test_executor_cannot_be_its_own_reviewer():
    payload = load_agentic_operating_model().model_dump()
    payload["reviewer_agent"] = payload["executor_agent"]
    with pytest.raises(ValidationError, match="distinct"):
        AgenticOperatingModel.model_validate(payload)


def test_executor_and_reviewer_identities_cannot_be_swapped():
    payload = load_agentic_operating_model().model_dump()
    payload["executor_agent"], payload["reviewer_agent"] = payload["reviewer_agent"], payload["executor_agent"]
    with pytest.raises(ValidationError, match="identities must match"):
        AgenticOperatingModel.model_validate(payload)


@pytest.mark.parametrize("path", ["../external.md", "/tmp/external.md"])
def test_context_cannot_escape_repository(path):
    payload = load_agentic_operating_model().model_dump()
    payload["contexts"]["trust"] = path
    with pytest.raises(ValidationError, match="repository-relative"):
        AgenticOperatingModel.model_validate(payload)


def test_session_policy_does_not_promote_merge_or_science_approval():
    policy = json.loads((ROOT / "config/agent-loop-policies.json").read_text())
    assert policy["decision_autonomy"]["default_judgment_route"] == "agent-resolved"
    assert policy["change"]["selective_review"]["default_decision"] == "review-required"
    assert policy["change"]["selective_review"]["promoted_classes"] == []
    assert not policy["decision_autonomy"]["independence"]["agent_may_materialize_human_approval"]
