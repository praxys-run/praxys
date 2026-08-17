"""Deterministic task-to-loop routing for the Praxys agentic runtime."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from analysis.agentic_operating_model import (
    AgenticOperatingModel,
    load_agentic_operating_model,
)


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ROUTING_PATH = _ROOT / "config" / "agentic-task-routing.json"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _append_unique(target: list[str], values: list[str]) -> None:
    for value in values:
        if value not in target:
            target.append(value)


def _digest(payload: object) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


class RoutingRecord(BaseModel):
    """Strict immutable base model for routing records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RouteContribution(RoutingRecord):
    """Roles, artifacts, and loop contributed by one task characteristic."""

    description: str = Field(min_length=1)
    loop: str | None
    required_roles: list[str] = Field(min_length=1)
    required_artifacts: list[str] = Field(default_factory=list)
    outcome_artifacts: list[str] = Field(default_factory=list)
    executor_roles: list[str] = Field(default_factory=list)
    verifier_roles: list[str] = Field(default_factory=list)
    material_judgment: bool

    @model_validator(mode="after")
    def validate_contribution(self) -> "RouteContribution":
        """Keep every contribution deterministic and internally complete."""
        for label, values in (
            ("required_roles", self.required_roles),
            ("required_artifacts", self.required_artifacts),
            ("outcome_artifacts", self.outcome_artifacts),
            ("executor_roles", self.executor_roles),
            ("verifier_roles", self.verifier_roles),
        ):
            _require_unique(values, label)
        missing_role_assignments = (
            set(self.executor_roles) | set(self.verifier_roles)
        ) - set(self.required_roles)
        if missing_role_assignments:
            raise ValueError(
                "executor and verifier roles must be required roles: "
                f"{sorted(missing_role_assignments)}"
            )
        return self


class TaskRoutingConfig(RoutingRecord):
    """Versioned task-characteristic and loop-routing policy."""

    schema_version: Literal[1]
    routing_version: str = Field(min_length=1)
    status: Literal["active"]
    operating_model_version: str = Field(min_length=1)
    orchestrator_agent_path: str = Field(min_length=1)
    loop_agents: dict[str, str] = Field(min_length=1)
    primary_objects: dict[str, RouteContribution] = Field(min_length=1)
    impacts: dict[str, RouteContribution] = Field(min_length=1)
    risk_triggers: list[str] = Field(min_length=1)
    nested_loop_order: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self) -> "TaskRoutingConfig":
        """Require stable identifiers and deterministic ordering."""
        for label, identifiers in (
            ("loop agent", self.loop_agents),
            ("primary object", self.primary_objects),
            ("impact", self.impacts),
        ):
            invalid = sorted(
                identifier
                for identifier in identifiers
                if _ID_RE.fullmatch(identifier) is None
            )
            if invalid:
                raise ValueError(f"invalid {label} IDs: {invalid}")
        _require_unique(self.risk_triggers, "risk_triggers")
        _require_unique(self.nested_loop_order, "nested_loop_order")
        return self


class TaskClassification(RoutingRecord):
    """Model-produced classification constrained to repository-owned IDs."""

    primary_object: str = Field(min_length=1)
    impacts: list[str] = Field(default_factory=list)
    risk_triggers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_classification(self) -> "TaskClassification":
        """Reject duplicated model output before deterministic routing."""
        _require_unique(self.impacts, "classification impacts")
        _require_unique(self.risk_triggers, "classification risk_triggers")
        return self


class TaskRoute(RoutingRecord):
    """Canonical work contract shared by local and cloud Copilot."""

    routing_version: str
    operating_model_version: str
    classification: TaskClassification
    classification_digest: str
    primary_loop: str
    nested_loops: list[str]
    loop_agents: dict[str, str]
    lead_role: str
    contributor_roles: list[str]
    executor_roles: list[str]
    verifier_roles: list[str]
    outcome_observer_roles: list[str]
    required_input_artifacts: list[str]
    required_artifacts: list[str]
    outcome_artifacts: list[str]
    risk_triggers: list[str]
    decision_review_agent: str
    decision_review_required: bool
    route_digest: str


def validate_task_routing_references(
    config: TaskRoutingConfig,
    model: AgenticOperatingModel,
    *,
    root: Path = _ROOT,
) -> None:
    """Cross-check routing policy against loops, roles, artifacts, and agents."""
    if config.operating_model_version != model.model_version:
        raise ValueError("task routing operating-model version mismatch")
    if set(config.loop_agents) != set(model.loops):
        raise ValueError("every operating-model loop requires one loop agent")
    if set(config.nested_loop_order) != set(model.loops):
        raise ValueError("nested_loop_order must contain every loop exactly once")
    primary_loops = {
        contribution.loop
        for contribution in config.primary_objects.values()
    }
    if primary_loops != set(model.loops):
        raise ValueError("every loop must be selectable as a primary object")

    agent_paths = [
        config.orchestrator_agent_path,
        *config.loop_agents.values(),
    ]
    for path in agent_paths:
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("routing agent paths must be repository-relative")
        if not (root / candidate).is_file():
            raise ValueError(f"routing agent manifest is missing: {path}")

    for characteristic_id, contribution in (
        list(config.primary_objects.items()) + list(config.impacts.items())
    ):
        if contribution.loop is not None and contribution.loop not in model.loops:
            raise ValueError(
                f"characteristic {characteristic_id} references unknown loop "
                f"{contribution.loop}"
            )
        unknown_roles = set(contribution.required_roles) - set(model.roles)
        if unknown_roles:
            raise ValueError(
                f"characteristic {characteristic_id} references unknown roles: "
                f"{sorted(unknown_roles)}"
            )
        unknown_artifacts = (
            set(contribution.required_artifacts)
            | set(contribution.outcome_artifacts)
        ) - set(model.artifacts)
        if unknown_artifacts:
            raise ValueError(
                f"characteristic {characteristic_id} references unknown "
                f"artifacts: {sorted(unknown_artifacts)}"
            )

    for object_id, contribution in config.primary_objects.items():
        assert contribution.loop is not None
        expected_lead = model.loops[contribution.loop].lead_role
        if expected_lead not in contribution.required_roles:
            raise ValueError(
                f"primary object {object_id} must require loop lead "
                f"{expected_lead}"
            )


def route_task(
    classification: TaskClassification,
    *,
    config: TaskRoutingConfig | None = None,
    model: AgenticOperatingModel | None = None,
) -> TaskRoute:
    """Convert a bounded classification into one canonical work contract."""
    active_config = config or load_task_routing_config()
    active_model = model or load_agentic_operating_model()

    if classification.primary_object not in active_config.primary_objects:
        raise ValueError(
            f"unknown primary object: {classification.primary_object}"
        )
    unknown_impacts = (
        set(classification.impacts) - set(active_config.impacts)
    )
    if unknown_impacts:
        raise ValueError(f"unknown impacts: {sorted(unknown_impacts)}")
    unknown_risks = (
        set(classification.risk_triggers)
        - set(active_config.risk_triggers)
    )
    if unknown_risks:
        raise ValueError(f"unknown risk triggers: {sorted(unknown_risks)}")

    normalized_impacts = [
        impact_id
        for impact_id in active_config.impacts
        if impact_id in classification.impacts
    ]
    normalized_risks = [
        risk_id
        for risk_id in active_config.risk_triggers
        if risk_id in classification.risk_triggers
    ]
    normalized_classification = TaskClassification(
        primary_object=classification.primary_object,
        impacts=normalized_impacts,
        risk_triggers=normalized_risks,
    )

    primary = active_config.primary_objects[
        normalized_classification.primary_object
    ]
    assert primary.loop is not None
    selected_loops = [primary.loop]
    required_roles: list[str] = []
    executor_roles: list[str] = []
    verifier_roles: list[str] = []
    required_artifacts: list[str] = []
    outcome_artifacts: list[str] = []
    material_judgment = primary.material_judgment

    contributions = [
        primary,
        *(
            active_config.impacts[impact_id]
            for impact_id in normalized_impacts
        ),
    ]
    for contribution in contributions:
        if (
            contribution.loop is not None
            and contribution.loop not in selected_loops
        ):
            selected_loops.append(contribution.loop)
        _append_unique(required_roles, contribution.required_roles)
        _append_unique(executor_roles, contribution.executor_roles)
        _append_unique(verifier_roles, contribution.verifier_roles)
        _append_unique(required_artifacts, contribution.required_artifacts)
        _append_unique(outcome_artifacts, contribution.outcome_artifacts)
        material_judgment = (
            material_judgment or contribution.material_judgment
        )

    ordered_nested_loops = [
        loop_id
        for loop_id in active_config.nested_loop_order
        if loop_id in selected_loops and loop_id != primary.loop
    ]
    ordered_loops = [primary.loop, *ordered_nested_loops]
    for loop_id in ordered_loops:
        _append_unique(required_roles, [active_model.loops[loop_id].lead_role])

    lead_role = active_model.loops[primary.loop].lead_role
    contributor_roles = [
        role_id
        for role_id in required_roles
        if role_id != lead_role
        and role_id not in executor_roles
        and role_id not in verifier_roles
    ]
    loop_agents = {
        loop_id: active_config.loop_agents[loop_id]
        for loop_id in ordered_loops
    }
    required_input_artifacts: list[str] = []
    selected_artifacts = set(required_artifacts)
    outcome_observer_roles: list[str] = []
    for artifact_id in outcome_artifacts:
        _append_unique(
            outcome_observer_roles,
            [active_model.artifacts[artifact_id].owner_role],
        )

    def add_input_dependencies(artifact_id: str) -> None:
        for dependency_id in active_model.artifacts[artifact_id].depends_on:
            if dependency_id in selected_artifacts:
                add_input_dependencies(dependency_id)
                continue
            add_input_dependencies(dependency_id)
            if dependency_id not in required_input_artifacts:
                required_input_artifacts.append(dependency_id)

    for artifact_id in required_artifacts:
        add_input_dependencies(artifact_id)

    classification_payload = normalized_classification.model_dump()
    route_payload = {
        "routing_version": active_config.routing_version,
        "operating_model_version": active_model.model_version,
        "primary_loop": primary.loop,
        "nested_loops": ordered_nested_loops,
        "loop_agents": loop_agents,
        "lead_role": lead_role,
        "contributor_roles": contributor_roles,
        "executor_roles": executor_roles,
        "verifier_roles": verifier_roles,
        "outcome_observer_roles": outcome_observer_roles,
        "required_input_artifacts": required_input_artifacts,
        "required_artifacts": required_artifacts,
        "outcome_artifacts": outcome_artifacts,
        "risk_triggers": normalized_risks,
        "decision_review_agent": (
            active_model.control_plane.decision_review_router_agent_path
        ),
        "decision_review_required": (
            material_judgment or bool(normalized_risks)
        ),
    }
    digest_payload = {
        **route_payload,
        "classification": classification_payload,
    }
    return TaskRoute(
        **route_payload,
        classification=normalized_classification,
        classification_digest=_digest(classification_payload),
        route_digest=_digest(digest_payload),
    )


def load_task_routing_config(
    path: str | Path | None = None,
    *,
    validate_paths: bool = True,
) -> TaskRoutingConfig:
    """Load and validate task routing plus operating-model references."""
    if path is None:
        return _load_default_task_routing_config()
    routing_path = Path(path)
    config = TaskRoutingConfig.model_validate_json(
        routing_path.read_text(encoding="utf-8")
    )
    if validate_paths:
        root = routing_path.resolve().parents[1]
        validate_task_routing_references(
            config,
            load_agentic_operating_model(
                root / "config" / "agentic-operating-model.json"
            ),
            root=root,
        )
    return config


@lru_cache(maxsize=1)
def _load_default_task_routing_config() -> TaskRoutingConfig:
    """Load the checked-in task routing policy once per process."""
    config = TaskRoutingConfig.model_validate_json(
        _DEFAULT_ROUTING_PATH.read_text(encoding="utf-8")
    )
    validate_task_routing_references(
        config,
        load_agentic_operating_model(),
    )
    return config
