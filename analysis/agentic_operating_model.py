"""Typed repository contract for Praxys roles, loops, and governance."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MODEL_PATH = _ROOT / "config" / "agentic-operating-model.json"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_relative_path(value: str, label: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be a repository-relative path")


class OperatingModelRecord(BaseModel):
    """Strict immutable base model for the operating-model specification."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RoleDefinition(OperatingModelRecord):
    """One decision-owning role and its bounded capabilities."""

    display_name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    manifest_status: Literal["available", "defined", "external"]
    agent_path: str | None = None
    external_reference: str | None = None
    decision_classes: list[str] = Field(min_length=1)
    owned_artifacts: list[str] = Field(min_length=1)
    capabilities: list[str] = Field(min_length=1)
    prohibited_actions: list[str] = Field(min_length=1)
    activation_triggers: list[str] = Field(default_factory=list)
    outcome_measures: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_role(self) -> "RoleDefinition":
        """Require one implementation location and deterministic lists."""
        if self.manifest_status == "available":
            if self.agent_path is None:
                raise ValueError("available roles require agent_path")
            if self.external_reference is not None:
                raise ValueError(
                    "available roles cannot define external_reference"
                )
        elif self.manifest_status == "external":
            if self.external_reference is None:
                raise ValueError(
                    "external roles require external_reference"
                )
            if self.agent_path is not None:
                raise ValueError("external roles cannot define agent_path")
        elif self.agent_path is not None or self.external_reference is not None:
            raise ValueError(
                "defined roles cannot claim an available implementation"
            )
        if self.agent_path is not None:
            _validate_relative_path(self.agent_path, "agent_path")
        for label, values in (
            ("decision_classes", self.decision_classes),
            ("owned_artifacts", self.owned_artifacts),
            ("capabilities", self.capabilities),
            ("prohibited_actions", self.prohibited_actions),
            ("activation_triggers", self.activation_triggers),
            ("outcome_measures", self.outcome_measures),
        ):
            _require_unique(values, label)
        return self


class ArtifactDefinition(OperatingModelRecord):
    """One durable interface owned by a role."""

    kind: Literal[
        "decision",
        "evidence",
        "execution",
        "verification",
        "outcome",
        "policy",
    ]
    implementation_status: Literal[
        "logical-contract",
        "repository-native",
        "schema-backed",
    ]
    owner_role: str
    purpose: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_artifact(self) -> "ArtifactDefinition":
        """Keep artifact dependencies unambiguous."""
        _require_unique(self.depends_on, "artifact dependencies")
        return self


class LoopDefinition(OperatingModelRecord):
    """One learning loop around an object rather than an organizational role."""

    object: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    lead_role: str
    participant_roles: list[str] = Field(default_factory=list)
    entry_signals: list[str] = Field(min_length=1)
    stages: list[str] = Field(min_length=1)
    artifacts: list[str] = Field(min_length=1)
    outcome_signals: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_loop(self) -> "LoopDefinition":
        """Require deterministic role, stage, artifact, and signal lists."""
        for label, values in (
            ("participant_roles", self.participant_roles),
            ("entry_signals", self.entry_signals),
            ("stages", self.stages),
            ("artifacts", self.artifacts),
            ("outcome_signals", self.outcome_signals),
        ):
            _require_unique(values, label)
        if self.lead_role in self.participant_roles:
            raise ValueError(
                "lead_role must not be repeated in participant_roles"
            )
        return self


class IndependencePolicy(OperatingModelRecord):
    """Separation-of-duty rules enforced by the control plane."""

    proposer_may_select_own_review_route: Literal[False]
    proposer_may_review_own_decision: Literal[False]
    executor_may_verify_own_high_risk_work: Literal[False]
    router_may_approve: Literal[False]
    agent_may_materialize_human_approval: Literal[False]


class ControlPlaneDefinition(OperatingModelRecord):
    """Shared routing and review infrastructure outside role ownership."""

    work_router_agent_path: str
    decision_review_router_agent_path: str
    role_slots: list[
        Literal[
            "lead",
            "contributors",
            "independent_reviewers",
            "executor",
            "verifier",
            "outcome_observer",
            "human_authority",
        ]
    ] = Field(min_length=1)
    routing_outcomes: list[
        Literal[
            "agent-resolved",
            "agent-reviewed",
            "human-review-required",
            "blocked",
        ]
    ] = Field(min_length=1)
    independence: IndependencePolicy
    human_attention_objective: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_control_plane(self) -> "ControlPlaneDefinition":
        """Keep control-plane paths and enumerations deterministic."""
        _validate_relative_path(
            self.work_router_agent_path,
            "work_router_agent_path",
        )
        _validate_relative_path(
            self.decision_review_router_agent_path,
            "decision_review_router_agent_path",
        )
        _require_unique(self.role_slots, "role_slots")
        _require_unique(self.routing_outcomes, "routing_outcomes")
        return self


class DecisionRecordContract(OperatingModelRecord):
    """Shared fields and typed specializations for durable decisions."""

    required_fields: list[str] = Field(min_length=1)
    specializations: dict[str, str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> "DecisionRecordContract":
        """Require deterministic fields and at least one specialization."""
        _require_unique(self.required_fields, "decision required_fields")
        return self


class RoleEvolutionPolicy(OperatingModelRecord):
    """Criteria for splitting, retaining, or retiring role boundaries."""

    create_role_when: list[str] = Field(min_length=1)
    keep_as_capability_when: list[str] = Field(min_length=1)
    retire_or_merge_role_when: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evolution(self) -> "RoleEvolutionPolicy":
        """Keep evolution criteria explicit and non-duplicated."""
        for label, values in (
            ("create_role_when", self.create_role_when),
            ("keep_as_capability_when", self.keep_as_capability_when),
            ("retire_or_merge_role_when", self.retire_or_merge_role_when),
        ):
            _require_unique(values, label)
        return self


class AgenticOperatingModel(OperatingModelRecord):
    """Complete versioned model of Praxys roles, loops, and governance."""

    schema_version: Literal[1]
    model_version: str = Field(min_length=1)
    status: Literal["specification-only"]
    principles: list[str] = Field(min_length=1)
    canonical_stages: list[str] = Field(min_length=1)
    roles: dict[str, RoleDefinition] = Field(min_length=1)
    artifacts: dict[str, ArtifactDefinition] = Field(min_length=1)
    loops: dict[str, LoopDefinition] = Field(min_length=1)
    control_plane: ControlPlaneDefinition
    decision_record_contract: DecisionRecordContract
    role_evolution: RoleEvolutionPolicy

    @model_validator(mode="after")
    def validate_references(self) -> "AgenticOperatingModel":
        """Cross-check every role, loop, artifact, and decision reference."""
        for label, identifiers in (
            ("role", self.roles),
            ("artifact", self.artifacts),
            ("loop", self.loops),
        ):
            invalid = sorted(
                identifier
                for identifier in identifiers
                if _ID_RE.fullmatch(identifier) is None
            )
            if invalid:
                raise ValueError(f"invalid {label} IDs: {invalid}")

        _require_unique(self.principles, "principles")
        _require_unique(self.canonical_stages, "canonical_stages")
        canonical_stage_index = {
            stage: index
            for index, stage in enumerate(self.canonical_stages)
        }

        for role_id, role in self.roles.items():
            unknown_artifacts = (
                set(role.owned_artifacts) - set(self.artifacts)
            )
            if unknown_artifacts:
                raise ValueError(
                    f"role {role_id} owns unknown artifacts: "
                    f"{sorted(unknown_artifacts)}"
                )
            wrong_owner = sorted(
                artifact_id
                for artifact_id in role.owned_artifacts
                if self.artifacts[artifact_id].owner_role != role_id
            )
            if wrong_owner:
                raise ValueError(
                    f"role {role_id} lists artifacts owned elsewhere: "
                    f"{wrong_owner}"
                )

        for artifact_id, artifact in self.artifacts.items():
            if artifact.owner_role not in self.roles:
                raise ValueError(
                    f"artifact {artifact_id} has unknown owner role "
                    f"{artifact.owner_role}"
                )
            if (
                artifact_id
                not in self.roles[artifact.owner_role].owned_artifacts
            ):
                raise ValueError(
                    f"artifact {artifact_id} is not listed by owner role "
                    f"{artifact.owner_role}"
                )
            unknown_dependencies = (
                set(artifact.depends_on) - set(self.artifacts)
            )
            if unknown_dependencies:
                raise ValueError(
                    f"artifact {artifact_id} has unknown dependencies: "
                    f"{sorted(unknown_dependencies)}"
                )
            if artifact_id in artifact.depends_on:
                raise ValueError(
                    f"artifact {artifact_id} cannot depend on itself"
                )

        visited: set[str] = set()
        active: list[str] = []

        def visit_artifact(artifact_id: str) -> None:
            if artifact_id in active:
                cycle_start = active.index(artifact_id)
                cycle = [*active[cycle_start:], artifact_id]
                raise ValueError(
                    "artifact dependency cycle: " + " -> ".join(cycle)
                )
            if artifact_id in visited:
                return
            active.append(artifact_id)
            for dependency_id in self.artifacts[artifact_id].depends_on:
                visit_artifact(dependency_id)
            active.pop()
            visited.add(artifact_id)

        for artifact_id in self.artifacts:
            visit_artifact(artifact_id)

        for loop_id, loop in self.loops.items():
            unknown_roles = (
                {loop.lead_role, *loop.participant_roles} - set(self.roles)
            )
            if unknown_roles:
                raise ValueError(
                    f"loop {loop_id} references unknown roles: "
                    f"{sorted(unknown_roles)}"
                )
            unknown_artifacts = set(loop.artifacts) - set(self.artifacts)
            if unknown_artifacts:
                raise ValueError(
                    f"loop {loop_id} references unknown artifacts: "
                    f"{sorted(unknown_artifacts)}"
                )
            unknown_stages = set(loop.stages) - set(self.canonical_stages)
            if unknown_stages:
                raise ValueError(
                    f"loop {loop_id} references unknown stages: "
                    f"{sorted(unknown_stages)}"
                )
            stage_indexes = [
                canonical_stage_index[stage]
                for stage in loop.stages
            ]
            if stage_indexes != sorted(stage_indexes):
                raise ValueError(
                    f"loop {loop_id} stages must preserve canonical order"
                )

        for artifact_id, owner_role in (
            self.decision_record_contract.specializations.items()
        ):
            if artifact_id not in self.artifacts:
                raise ValueError(
                    "decision specialization references unknown artifact "
                    f"{artifact_id}"
                )
            artifact = self.artifacts[artifact_id]
            if artifact.kind != "decision":
                raise ValueError(
                    f"decision specialization {artifact_id} is not a decision"
                )
            if owner_role != artifact.owner_role:
                raise ValueError(
                    f"decision specialization {artifact_id} owner mismatch"
                )
        decision_artifacts = {
            artifact_id
            for artifact_id, artifact in self.artifacts.items()
            if artifact.kind == "decision"
        }
        missing_specializations = (
            decision_artifacts
            - set(self.decision_record_contract.specializations)
        )
        if missing_specializations:
            raise ValueError(
                "decision artifacts missing specializations: "
                f"{sorted(missing_specializations)}"
            )
        return self


def validate_agent_manifest_paths(
    model: AgenticOperatingModel,
    *,
    root: Path = _ROOT,
) -> None:
    """Require every available role and router manifest to exist."""
    paths = [
        role.agent_path
        for role in model.roles.values()
        if role.agent_path is not None
    ]
    paths.extend([
        model.control_plane.work_router_agent_path,
        model.control_plane.decision_review_router_agent_path,
    ])
    concrete_paths = [path for path in paths if path is not None]
    _require_unique(concrete_paths, "agent manifest paths")
    missing = sorted(
        path
        for path in concrete_paths
        if not (root / path).is_file()
    )
    if missing:
        raise ValueError(f"agent manifests are missing: {missing}")


def load_agentic_operating_model(
    path: str | Path | None = None,
    *,
    validate_paths: bool = True,
) -> AgenticOperatingModel:
    """Load and validate the repository agentic operating model."""
    if path is None:
        return _load_default_agentic_operating_model()
    model_path = Path(path)
    model = AgenticOperatingModel.model_validate_json(
        model_path.read_text(encoding="utf-8")
    )
    if validate_paths:
        validate_agent_manifest_paths(
            model,
            root=model_path.resolve().parents[1],
        )
    return model


@lru_cache(maxsize=1)
def _load_default_agentic_operating_model() -> AgenticOperatingModel:
    """Load the immutable checked-in operating model once per process."""
    model = AgenticOperatingModel.model_validate(
        json.loads(_DEFAULT_MODEL_PATH.read_text(encoding="utf-8"))
    )
    validate_agent_manifest_paths(model)
    return model
