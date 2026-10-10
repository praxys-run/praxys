"""Behavioral replay: no handoffs for routine work, one review for material risk."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from analysis.agentic_task_routing import TaskClassification, TaskRoutingConfig, load_task_routing_config, route_task

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("primary,impacts", [
    ("repository-behavior", []),
    ("repository-behavior", ["repository-change"]),
    ("user-experience", ["repository-change", "user-visible-experience"]),
    ("product-promise", ["product-value", "repository-change", "user-visible-experience"]),
])
def test_routine_work_stays_in_one_session(primary, impacts):
    route = route_task(TaskClassification(primary_object=primary, impacts=impacts))
    assert route.execution_mode == "single-session"
    assert route.reviewer_agent is None
    assert route.authority_checks == []
    assert "loop_agents" not in route.model_dump()
    assert "required_artifacts" not in route.model_dump()


@pytest.mark.parametrize("impact", [
    "scientific-evidence-or-claim", "trust-boundary", "architecture-boundary",
    "production-operation", "incident-response", "agent-policy-or-autonomy",
])
def test_each_material_risk_requires_independent_review(impact):
    route = route_task(TaskClassification(primary_object="repository-behavior", impacts=[impact]))
    assert route.execution_mode == "independent-review"
    assert route.reviewer_agent and route.reviewer_agent != route.executor_agent


@pytest.mark.parametrize("risk", load_task_routing_config().risk_triggers)
def test_risk_trigger_alone_cannot_escape_review(risk):
    route = route_task(TaskClassification(primary_object="repository-behavior", risk_triggers=[risk]))
    assert route.reviewer_agent
    assert (risk in route.authority_checks) == (risk in load_task_routing_config().authority_triggers)
    # The result neither grants authority nor assumes existing authorization is absent.
    assert "approved" not in route.model_dump()
    assert "human_review_required" not in route.model_dump()


def test_combined_science_security_runtime_risk_has_one_reviewer():
    route = route_task(TaskClassification(
        primary_object="production-incident",
        impacts=["trust-boundary", "scientific-evidence-or-claim", "repository-change", "production-operation"],
        risk_triggers=["security-or-privacy-boundary"],
    ))
    assert isinstance(route.reviewer_agent, str)
    assert len(route.contexts) == 3
    assert route.authority_checks == ["security-or-privacy-boundary"]


@pytest.mark.parametrize("section,concern", [
    ("primary_objects", "scientific-evidence"),
    ("primary_objects", "production-state"),
    ("primary_objects", "production-incident"),
    ("primary_objects", "agent-system"),
    ("impacts", "scientific-evidence-or-claim"),
    ("impacts", "production-operation"),
    ("impacts", "incident-response"),
    ("impacts", "agent-policy-or-autonomy"),
    ("impacts", "architecture-boundary"),
    ("impacts", "trust-boundary"),
])
@pytest.mark.parametrize("mutation", ["disable", "remove"])
def test_mandatory_material_risk_review_cannot_be_disabled(section, concern, mutation):
    payload = load_task_routing_config().model_dump()
    if mutation == "disable":
        payload[section][concern]["independent_review"] = False
    else:
        del payload[section][concern]
    with pytest.raises(ValidationError, match="independent review is mandatory"):
        TaskRoutingConfig.model_validate(payload)


def test_order_does_not_change_route_and_policy_edits_invalidate_it():
    a = TaskClassification(primary_object="agent-system", impacts=["repository-change", "agent-policy-or-autonomy"])
    b = TaskClassification(primary_object=a.primary_object, impacts=list(reversed(a.impacts)))
    original = route_task(a)
    assert original == route_task(b)
    config = load_task_routing_config().model_dump()
    config["impacts"]["repository-change"]["description"] += " Changed policy."
    changed = route_task(a, config=TaskRoutingConfig.model_validate(config))
    assert changed.route_digest != original.route_digest


@pytest.mark.parametrize("field,value", [("primary_object", "missing"), ("impacts", ["missing"]), ("risk_triggers", ["missing"])])
def test_unknown_classification_is_rejected(field, value):
    payload = {"primary_object": "repository-behavior", field: value}
    with pytest.raises(ValueError, match="unknown"):
        route_task(TaskClassification.model_validate(payload))


def test_duplicate_and_malformed_classifications_are_rejected():
    with pytest.raises(ValidationError):
        TaskClassification(primary_object="repository-behavior", impacts=["repository-change"] * 2)
    with pytest.raises(ValidationError):
        TaskClassification(primary_object="repository-behavior", impacts="repository-change")


def test_cli_summarizes_without_ledger_or_approval():
    result = subprocess.run([sys.executable, "scripts/route_agentic_task.py", "--primary-object", "repository-behavior"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert json.loads(result.stdout)["execution_mode"] == "single-session"
