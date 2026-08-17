"""Deterministic task-characteristic routing contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from analysis.agentic_operating_model import load_agentic_operating_model
from analysis.agentic_task_routing import (
    TaskClassification,
    TaskRoutingConfig,
    load_task_routing_config,
    route_task,
    validate_task_routing_references,
)


ROOT = Path(__file__).resolve().parents[1]
ROUTING_PATH = ROOT / "config" / "agentic-task-routing.json"


def test_every_loop_has_a_primary_object_and_agent() -> None:
    config = load_task_routing_config()
    model = load_agentic_operating_model()

    assert config.status == "active"
    assert set(config.loop_agents) == set(model.loops)
    assert {
        contribution.loop
        for contribution in config.primary_objects.values()
    } == set(model.loops)
    assert config.orchestrator_agent_path == (
        ".github/agents/praxys-orchestrator.agent.md"
    )


def test_product_feature_routes_product_design_and_delivery() -> None:
    route = route_task(
        TaskClassification(
            primary_object="product-promise",
            impacts=[
                "repository-change",
                "user-visible-experience",
            ],
        )
    )

    assert route.primary_loop == "product"
    assert route.nested_loops == ["design", "delivery"]
    assert route.lead_role == "product"
    assert route.contributor_roles == ["design"]
    assert route.executor_roles == ["engineering"]
    assert route.verifier_roles == ["quality"]
    assert route.outcome_observer_roles == ["product"]
    assert route.loop_agents == {
        "product": ".github/agents/product.agent.md",
        "design": ".github/agents/design.agent.md",
        "delivery": ".github/agents/praxys-change-loop.agent.md",
    }
    assert route.decision_review_required is True
    assert "product-decision-record" in route.required_artifacts
    assert "implementation-change" in route.required_artifacts
    assert route.required_input_artifacts == []
    assert route.outcome_artifacts == ["product-outcome-record"]


def test_science_change_keeps_science_primary_and_adds_specialists() -> None:
    route = route_task(
        TaskClassification(
            primary_object="scientific-evidence",
            impacts=[
                "scientific-evidence-or-claim",
                "architecture-boundary",
                "repository-change",
                "product-value",
                "user-visible-experience",
            ],
            risk_triggers=["scientific-uncertainty"],
        )
    )

    assert route.primary_loop == "science"
    assert route.nested_loops == ["product", "design", "delivery"]
    assert route.lead_role == "science"
    assert route.contributor_roles == [
        "product",
        "design",
        "architecture",
    ]
    assert route.executor_roles == ["engineering"]
    assert route.verifier_roles == ["quality"]
    assert route.risk_triggers == ["scientific-uncertainty"]
    assert "architecture-decision-record" in route.required_artifacts
    assert "science-decision-record" in route.required_artifacts
    assert route.required_input_artifacts == []


def test_incident_fix_routes_incident_then_delivery_and_runtime() -> None:
    route = route_task(
        TaskClassification(
            primary_object="production-incident",
            impacts=[
                "trust-boundary",
                "repository-change",
                "production-operation",
            ],
            risk_triggers=["security-or-privacy-boundary"],
        )
    )

    assert route.primary_loop == "incident"
    assert route.nested_loops == ["delivery", "runtime"]
    assert route.lead_role == "operations"
    assert route.contributor_roles == ["trust"]
    assert route.executor_roles == ["operations", "engineering"]
    assert route.verifier_roles == ["quality"]
    assert route.decision_review_required is True
    assert route.required_input_artifacts == []


def test_agent_policy_change_routes_meta_eval_then_delivery() -> None:
    route = route_task(
        TaskClassification(
            primary_object="agent-system",
            impacts=[
                "repository-change",
                "agent-policy-or-autonomy",
            ],
        )
    )

    assert route.primary_loop == "meta-eval"
    assert route.nested_loops == ["delivery"]
    assert route.lead_role == "meta-eval"
    assert route.executor_roles == ["engineering"]
    assert route.verifier_roles == ["quality"]
    assert "policy-change-proposal" in route.required_artifacts


def test_research_and_evaluation_do_not_force_downstream_decisions() -> None:
    research = route_task(
        TaskClassification(primary_object="scientific-evidence")
    )
    evaluation = route_task(
        TaskClassification(primary_object="agent-system")
    )

    assert research.required_artifacts == ["evidence-review"]
    assert "science-decision-record" not in research.required_artifacts
    assert evaluation.required_artifacts == ["evaluation-report"]
    assert "policy-change-proposal" not in evaluation.required_artifacts


def test_design_and_runtime_routes_require_their_accepted_inputs() -> None:
    design = route_task(
        TaskClassification(primary_object="user-experience")
    )
    runtime = route_task(
        TaskClassification(primary_object="production-state")
    )

    assert design.required_input_artifacts == ["product-decision-record"]
    assert runtime.required_input_artifacts == [
        "implementation-change",
        "verification-evidence",
    ]


def test_route_normalizes_trait_order_and_produces_stable_digests() -> None:
    first = route_task(
        TaskClassification(
            primary_object="product-promise",
            impacts=["repository-change", "user-visible-experience"],
        )
    )
    second = route_task(
        TaskClassification(
            primary_object="product-promise",
            impacts=["user-visible-experience", "repository-change"],
        )
    )

    assert first == second
    assert first.classification_digest.startswith("sha256:")
    assert first.route_digest.startswith("sha256:")
    assert first.decision_review_agent == (
        ".github/agents/decision-review-router.agent.md"
    )


def test_route_rejects_unknown_traits() -> None:
    with pytest.raises(ValueError, match="unknown primary object"):
        route_task(TaskClassification(primary_object="missing"))

    with pytest.raises(ValueError, match="unknown impacts"):
        route_task(
            TaskClassification(
                primary_object="repository-behavior",
                impacts=["missing"],
            )
        )


def test_routing_config_rejects_incomplete_loop_coverage() -> None:
    payload = json.loads(ROUTING_PATH.read_text(encoding="utf-8"))
    del payload["loop_agents"]["product"]
    config = TaskRoutingConfig.model_validate(payload)

    with pytest.raises(ValueError, match="every operating-model loop"):
        validate_task_routing_references(
            config,
            load_agentic_operating_model(),
        )


def test_route_cli_emits_the_same_contract() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/route_agentic_task.py",
            "--primary-object",
            "repository-behavior",
            "--impact",
            "trust-boundary",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["primary_loop"] == "delivery"
    assert payload["contributor_roles"] == ["trust"]
    assert payload["executor_roles"] == ["engineering"]
    assert payload["verifier_roles"] == ["quality"]
