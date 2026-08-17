"""Contracts for the versioned Praxys agentic operating model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.agentic_operating_model import (
    AgenticOperatingModel,
    load_agentic_operating_model,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "config" / "agentic-operating-model.json"
POLICY_PATH = ROOT / "config" / "agent-loop-policies.json"


def test_operating_model_defines_roles_loops_and_control_plane() -> None:
    model = load_agentic_operating_model()

    assert model.model_version == "praxys-agentic-operating-model-v1"
    assert model.status == "active-routing"
    assert set(model.roles) == {
        "product",
        "design",
        "engineering",
        "architecture",
        "quality",
        "science",
        "trust",
        "operations",
        "meta-eval",
    }
    assert set(model.loops) == {
        "product",
        "science",
        "design",
        "delivery",
        "runtime",
        "incident",
        "meta-eval",
    }
    assert model.control_plane.role_slots == [
        "lead",
        "contributors",
        "independent_reviewers",
        "executor",
        "verifier",
        "outcome_observer",
        "human_authority",
    ]
    assert model.control_plane.routing_outcomes == [
        "agent-resolved",
        "agent-reviewed",
        "human-review-required",
        "blocked",
    ]
    assert model.control_plane.orchestrator_agent_path == (
        ".github/agents/praxys-orchestrator.agent.md"
    )
    assert model.control_plane.task_routing_config_path == (
        "config/agentic-task-routing.json"
    )
    assert model.control_plane.execution_parity_config_path == (
        "config/copilot-execution-parity.json"
    )


def test_roles_own_decisions_not_technology_directories() -> None:
    model = load_agentic_operating_model()
    engineering = model.roles["engineering"]
    architecture = model.roles["architecture"]
    quality = model.roles["quality"]
    meta = model.roles["meta-eval"]

    assert {
        "frontend",
        "backend-and-api",
        "data-pipeline",
        "analysis-and-model-integration",
        "database",
    } <= set(engineering.capabilities)
    assert "new-service-or-datastore" in architecture.activation_triggers
    assert (
        "become-a-mandatory-gate-for-local-code-choices"
        in architecture.prohibited_actions
    )
    assert "release-confidence" in quality.decision_classes
    assert (
        "replace-quality-verification-for-current-change"
        in meta.prohibited_actions
    )
    assert all(role.outcome_measures for role in model.roles.values())
    assert "human-product-correction" in model.roles["product"].outcome_measures
    assert "escaped-defect-rate" in quality.outcome_measures
    assert "replay-and-shadow-score" in meta.outcome_measures


def test_decision_record_specializations_preserve_role_authority() -> None:
    model = load_agentic_operating_model()
    contract = model.decision_record_contract

    assert contract.required_fields == [
        "id",
        "schema_version",
        "decision_type",
        "owner_role",
        "question",
        "options",
        "recommendation",
        "rationale",
        "dependencies",
        "review_route",
        "outcome_plan",
        "digest",
    ]
    assert contract.specializations == {
        "product-decision-record": "product",
        "design-decision-record": "design",
        "architecture-decision-record": "architecture",
        "science-decision-record": "science",
        "trust-decision-record": "trust",
        "operations-decision-record": "operations",
    }
    for artifact_id, role_id in contract.specializations.items():
        artifact = model.artifacts[artifact_id]
        assert artifact.kind == "decision"
        assert artifact.owner_role == role_id
    assert (
        model.artifacts["product-decision-record"].implementation_status
        == "logical-contract"
    )
    assert (
        model.artifacts["science-decision-record"].implementation_status
        == "schema-backed"
    )
    assert (
        model.artifacts["implementation-change"].implementation_status
        == "repository-native"
    )


def test_runtime_review_policy_matches_operating_model_control_plane() -> None:
    model = load_agentic_operating_model()
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    assert policy["operating_model"] == {
        "path": "config/agentic-operating-model.json",
        "version": model.model_version,
        "status": model.status,
    }
    autonomy = policy["decision_autonomy"]
    assert autonomy["routing_outcomes"] == (
        model.control_plane.routing_outcomes
    )
    assert autonomy["independence"] == (
        model.control_plane.independence.model_dump()
    )
    assert autonomy["promoted_judgment_classes"] == []


def test_role_evolution_is_decision_based_not_org_chart_based() -> None:
    model = load_agentic_operating_model()
    evolution = model.role_evolution

    assert "a-distinct-decision-class-recurs" in evolution.create_role_when
    assert (
        "the-work-is-a-specialization-within-an-existing-decision-boundary"
        in evolution.keep_as_capability_when
    )
    assert (
        "the-role-no-longer-owns-a-distinct-decision"
        in evolution.retire_or_merge_role_when
    )


def test_operating_model_rejects_unknown_roles_and_stage_reordering() -> None:
    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    payload["loops"]["product"]["participant_roles"].append("missing-role")
    with pytest.raises(ValidationError, match="unknown roles"):
        AgenticOperatingModel.model_validate(payload)

    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    payload["loops"]["delivery"]["stages"] = ["act", "plan", "verify"]
    with pytest.raises(ValidationError, match="canonical order"):
        AgenticOperatingModel.model_validate(payload)


def test_operating_model_rejects_artifact_owner_drift() -> None:
    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    payload["artifacts"]["product-decision-record"][
        "owner_role"
    ] = "engineering"

    with pytest.raises(ValidationError, match="owned elsewhere"):
        AgenticOperatingModel.model_validate(payload)


def test_operating_model_rejects_incomplete_artifact_ownership() -> None:
    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    payload["roles"]["product"]["owned_artifacts"].remove(
        "product-outcome-record"
    )

    with pytest.raises(ValidationError, match="not listed by owner role"):
        AgenticOperatingModel.model_validate(payload)


def test_operating_model_rejects_artifact_dependency_cycles() -> None:
    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    payload["artifacts"]["product-decision-record"]["depends_on"] = [
        "product-outcome-record"
    ]

    with pytest.raises(ValidationError, match="artifact dependency cycle"):
        AgenticOperatingModel.model_validate(payload)


def test_operating_model_requires_every_decision_specialization() -> None:
    payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    del payload["decision_record_contract"]["specializations"][
        "product-decision-record"
    ]

    with pytest.raises(
        ValidationError,
        match="decision artifacts missing specializations",
    ):
        AgenticOperatingModel.model_validate(payload)
