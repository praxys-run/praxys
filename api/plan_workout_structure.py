"""Typed workout-structure contract and compatibility helpers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from analysis.metrics import is_rest_workout

AdaptivePlanDiscipline = Literal["running", "trail_running"]
PlanActivityType = Literal[
    "running",
    "trail_running",
    "cycling",
    "walking",
    "hiking",
    "strength",
    "mobility",
    "cross_training",
    "rest",
    "other",
]
WorkoutPhase = Literal[
    "warmup",
    "work",
    "recovery",
    "rest",
    "cooldown",
    "other",
]
WorkoutStructureVersion = Literal["v1"]
WorkoutStructureState = Literal[
    "absent",
    "supported",
    "invalid",
    "unsupported",
]
ProviderCompatibilityTarget = Literal["garmin", "stryd"]
ProviderCompatibilityMode = Literal[
    "legacy_flat",
    "structured",
    "unsupported",
]
ProviderCompatibilityReasonCode = Literal[
    "activity_type_not_supported",
    "duration_required",
    "empty_structure_not_supported",
    "flat_workout_not_lossless",
    "invalid_structure",
    "phase_not_supported",
    "structured_workout_not_supported",
    "target_not_supported",
    "termination_not_supported",
    "wording_not_supported",
]

_ALLOWED_DISCIPLINES = {"running", "trail_running"}
_ALLOWED_ACTIVITY_TYPES = {
    "running",
    "trail_running",
    "cycling",
    "walking",
    "hiking",
    "strength",
    "mobility",
    "cross_training",
    "rest",
    "other",
}
_SUPPORTED_ACTIVITY_TYPES_BY_TARGET = {
    "stryd": {"running", "trail_running"},
    "garmin": {"running"},
}

# Limits are measured after trimming and reject overflow without truncation.
# Labels stay compact enough for portable list/device surfaces; instructions
# retain a substantially larger canonical coaching cue in Praxys.
WORKOUT_LABEL_MAX_LENGTH = 80
WORKOUT_INSTRUCTIONS_MAX_LENGTH = 1000


def _normalize_optional_user_wording(value: object) -> object:
    """Trim optional wording and represent blank-only input as absent."""
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


@dataclass(frozen=True)
class WorkoutStructureInspection:
    """Classification of one persisted structure/version pair."""

    state: WorkoutStructureState
    structure: StructuredWorkoutV1 | None = None


class IntensityTargetV1(BaseModel):
    """One typed v1 intensity target."""

    model_config = ConfigDict(extra="forbid")

    metric: Literal["none", "power", "heart_rate", "pace", "rpe"]
    unit: Literal[
        "none",
        "watts",
        "percent_cp",
        "bpm",
        "percent_lthr",
        "sec_per_km",
        "sec_per_km_delta",
        "scale_10",
    ]
    reference: Literal[
        "none",
        "absolute",
        "critical_power",
        "lthr",
        "threshold_pace",
        "perceived_exertion",
    ]
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "IntensityTargetV1":
        combo = (self.metric, self.unit, self.reference)
        allowed = {
            ("none", "none", "none"),
            ("power", "watts", "absolute"),
            ("power", "percent_cp", "critical_power"),
            ("heart_rate", "bpm", "absolute"),
            ("heart_rate", "percent_lthr", "lthr"),
            ("pace", "sec_per_km", "absolute"),
            ("pace", "sec_per_km_delta", "threshold_pace"),
            ("rpe", "scale_10", "perceived_exertion"),
        }
        if combo not in allowed:
            raise PydanticCustomError(
                "workout_intensity_target_invalid",
                "Intensity target metric, unit, and reference do not form a supported combination.",
            )
        if self.metric == "none":
            if self.min is not None or self.max is not None:
                raise PydanticCustomError(
                    "workout_intensity_target_invalid",
                    "A no-target step cannot include min or max values.",
                )
            return self
        if self.min is None and self.max is None:
            raise PydanticCustomError(
                "workout_intensity_target_missing",
                "An intensity target must include at least one bound.",
            )
        bounds = {
            ("power", "watts", "absolute"): (0, 5000),
            ("power", "percent_cp", "critical_power"): (0, 300),
            ("heart_rate", "bpm", "absolute"): (0, 300),
            ("heart_rate", "percent_lthr", "lthr"): (0, 200),
            ("pace", "sec_per_km", "absolute"): (0, 7200),
            ("pace", "sec_per_km_delta", "threshold_pace"): (-7200, 7200),
            ("rpe", "scale_10", "perceived_exertion"): (0, 10),
        }
        low, high = bounds[combo]
        for value_name in ("min", "max"):
            value = getattr(self, value_name)
            if value is None:
                continue
            if not math.isfinite(value):
                raise PydanticCustomError(
                    "workout_intensity_target_invalid",
                    "Intensity target bounds must be finite.",
                )
            if value < low or value > high:
                raise PydanticCustomError(
                    "workout_intensity_target_out_of_range",
                    "Intensity target bound is outside the supported range.",
                )
        if (
            self.min is not None
            and self.max is not None
            and self.min > self.max
        ):
            raise PydanticCustomError(
                "workout_intensity_target_invalid",
                "Intensity target minimum cannot exceed the maximum.",
            )
        return self


class WorkoutTerminationV1(BaseModel):
    """One typed v1 step termination."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["time", "distance", "open", "manual"]
    seconds: int | None = Field(default=None, ge=1, le=86_400)
    meters: int | None = Field(default=None, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def validate_termination(self) -> "WorkoutTerminationV1":
        if self.type == "time":
            if self.seconds is None or self.meters is not None:
                raise PydanticCustomError(
                    "workout_termination_invalid",
                    "A time termination must include only seconds.",
                )
            return self
        if self.type == "distance":
            if self.meters is None or self.seconds is not None:
                raise PydanticCustomError(
                    "workout_termination_invalid",
                    "A distance termination must include only meters.",
                )
            return self
        if self.seconds is not None or self.meters is not None:
            raise PydanticCustomError(
                "workout_termination_invalid",
                "Open and manual terminations cannot include numeric bounds.",
            )
        return self


class StructuredWorkoutStepV1(BaseModel):
    """One executable structured step."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["step"] = "step"
    phase: WorkoutPhase
    label: str | None = Field(
        default=None,
        max_length=WORKOUT_LABEL_MAX_LENGTH,
        description=(
            "Optional user-defined display label, trimmed without truncation."
        ),
    )
    instructions: str | None = Field(
        default=None,
        max_length=WORKOUT_INSTRUCTIONS_MAX_LENGTH,
        description=(
            "Optional user-defined coaching cue, trimmed without truncation."
        ),
    )
    termination: WorkoutTerminationV1
    target: IntensityTargetV1

    @field_validator("label", "instructions", mode="before")
    @classmethod
    def normalize_user_wording(cls, value: object) -> object:
        """Normalize optional user wording without changing internal text."""
        return _normalize_optional_user_wording(value)


class StructuredWorkoutRepeatGroupV1(BaseModel):
    """One repeat group containing executable steps."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["repeat"] = "repeat"
    label: str | None = Field(
        default=None,
        max_length=WORKOUT_LABEL_MAX_LENGTH,
        description=(
            "Optional user-defined group label, trimmed without truncation."
        ),
    )
    repetitions: int = Field(ge=1, le=100)
    steps: list[StructuredWorkoutStepV1] = Field(min_length=1)

    @field_validator("label", mode="before")
    @classmethod
    def normalize_user_label(cls, value: object) -> object:
        """Normalize an optional group label without changing internal text."""
        return _normalize_optional_user_wording(value)


StructuredWorkoutNodeV1 = Annotated[
    StructuredWorkoutStepV1 | StructuredWorkoutRepeatGroupV1,
    Field(discriminator="type"),
]


class StructuredWorkoutV1(BaseModel):
    """One structured workout definition."""

    model_config = ConfigDict(extra="forbid")

    steps: list[StructuredWorkoutNodeV1] = Field(default_factory=list)


class WorkoutProviderCompatibilityReason(BaseModel):
    """One lossless-delivery constraint for a named provider."""

    model_config = ConfigDict(extra="forbid")

    code: ProviderCompatibilityReasonCode
    path: str | None = None


class WorkoutProviderCompatibility(BaseModel):
    """Provider-neutral content compatibility for one canonical workout."""

    model_config = ConfigDict(extra="forbid")

    target: ProviderCompatibilityTarget
    compatible: bool
    mode: ProviderCompatibilityMode
    reasons: list[WorkoutProviderCompatibilityReason] = Field(
        default_factory=list,
    )


def inspect_workout_structure(
    *,
    workout_structure_version: object,
    workout_structure: object,
) -> WorkoutStructureInspection:
    """Distinguish truly flat rows from supported and unsafe structures."""
    if workout_structure_version is None and workout_structure is None:
        return WorkoutStructureInspection(state="absent")
    if workout_structure_version is None or workout_structure is None:
        return WorkoutStructureInspection(state="invalid")
    if workout_structure_version != "v1":
        return WorkoutStructureInspection(state="unsupported")
    try:
        model = (
            workout_structure
            if isinstance(workout_structure, StructuredWorkoutV1)
            else StructuredWorkoutV1.model_validate(workout_structure)
        )
    except (TypeError, ValueError):
        return WorkoutStructureInspection(state="invalid")
    return WorkoutStructureInspection(
        state="supported",
        structure=model,
    )


def normalize_adaptive_plan_discipline(value: str) -> str:
    """Normalize and validate an adaptive-plan discipline string."""
    normalized = str(value or "").strip()
    if normalized not in _ALLOWED_DISCIPLINES:
        raise ValueError("adaptive-plan discipline is invalid")
    return normalized


def default_activity_type(workout_type: str) -> str:
    """Return the compatibility default activity type for a workout type."""
    return "rest" if is_rest_workout(workout_type) else "running"


def normalize_activity_type(
    workout_type: str,
    activity_type: str | None,
) -> str:
    """Normalize and validate a per-workout activity type."""
    normalized = str(
        activity_type or default_activity_type(workout_type)
    ).strip()
    if normalized not in _ALLOWED_ACTIVITY_TYPES:
        raise ValueError("activity_type is invalid")
    workout_is_rest = is_rest_workout(workout_type)
    if workout_is_rest and normalized != "rest":
        raise ValueError("rest workouts must use activity_type=rest")
    if not workout_is_rest and normalized == "rest":
        raise ValueError("non-rest workouts cannot use activity_type=rest")
    return normalized


def project_activity_type(
    workout_type: str,
    activity_type: object,
) -> str:
    """Project provider text into the strict portable activity enum.

    Provider-owned calendar rows may contain sport keys Praxys does not yet
    model. Returning ``other`` keeps the API contract truthful without
    treating an unknown activity as road running or mutating source data.
    """
    try:
        return normalize_activity_type(
            workout_type,
            None if activity_type is None else str(activity_type),
        )
    except ValueError:
        return "rest" if is_rest_workout(workout_type) else "other"


def validate_structured_workout(
    *,
    workout_type: str,
    activity_type: str,
    workout_structure_version: str,
    workout_structure: Mapping[str, Any] | StructuredWorkoutV1,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Validate one authoritative structured workout and derive flat fields."""
    if workout_structure_version != "v1":
        raise ValueError("workout_structure_version is invalid")
    normalized_activity_type = normalize_activity_type(
        workout_type,
        activity_type,
    )
    model = (
        workout_structure
        if isinstance(workout_structure, StructuredWorkoutV1)
        else StructuredWorkoutV1.model_validate(workout_structure)
    )
    step_count = executable_step_count(model)
    if not is_rest_workout(workout_type) and step_count < 1:
        raise ValueError("non-rest workouts require at least one executable step")
    if is_rest_workout(workout_type):
        if normalized_activity_type != "rest":
            raise ValueError("rest workouts must use activity_type=rest")
        if step_count:
            raise ValueError("rest workouts cannot include executable steps")
    structure_dict = model.model_dump(mode="json", exclude_none=True)
    return (
        normalized_activity_type,
        structure_dict,
        derive_flat_compatibility_from_structure(structure_dict),
    )


def executable_step_count(
    structure: StructuredWorkoutV1 | Mapping[str, Any],
) -> int:
    """Count executable steps, including those nested inside repeat groups."""
    model = (
        structure
        if isinstance(structure, StructuredWorkoutV1)
        else StructuredWorkoutV1.model_validate(structure)
    )
    count = 0
    for node in model.steps:
        if isinstance(node, StructuredWorkoutStepV1):
            count += 1
        else:
            count += len(node.steps)
    return count


def expand_structured_steps(
    structure: StructuredWorkoutV1 | Mapping[str, Any],
) -> list[StructuredWorkoutStepV1]:
    """Return the executable steps with repeat groups expanded."""
    model = (
        structure
        if isinstance(structure, StructuredWorkoutV1)
        else StructuredWorkoutV1.model_validate(structure)
    )
    steps: list[StructuredWorkoutStepV1] = []
    for node in model.steps:
        if isinstance(node, StructuredWorkoutStepV1):
            steps.append(node)
            continue
        for _ in range(node.repetitions):
            steps.extend(node.steps)
    return steps


def derive_flat_compatibility_from_structure(
    structure: StructuredWorkoutV1 | Mapping[str, Any],
) -> dict[str, Any]:
    """Project authoritative structured data into legacy flat fields safely."""
    steps = expand_structured_steps(structure)
    projection: dict[str, Any] = {
        "planned_duration_min": None,
        "planned_distance_km": None,
        "target_power_min": None,
        "target_power_max": None,
        "target_hr_min": None,
        "target_hr_max": None,
        "target_pace_min": None,
        "target_pace_max": None,
    }
    if not steps:
        return projection

    duration_seconds = 0
    duration_known = True
    distance_meters = 0
    distance_known = True
    target_signatures: list[tuple[Any, ...] | None] = []
    for step in steps:
        if step.termination.type == "time":
            assert step.termination.seconds is not None
            duration_seconds += step.termination.seconds
            distance_known = False
        elif step.termination.type == "distance":
            assert step.termination.meters is not None
            distance_meters += step.termination.meters
            duration_known = False
        else:
            duration_known = False
            distance_known = False
        target_signatures.append(_projectable_target_signature(step.target))

    if duration_known:
        projection["planned_duration_min"] = round(duration_seconds / 60, 3)
    if distance_known:
        projection["planned_distance_km"] = round(distance_meters / 1000, 3)

    if not target_signatures or any(signature is None for signature in target_signatures):
        return projection

    unique_signatures = {signature for signature in target_signatures}
    if len(unique_signatures) != 1:
        return projection

    signature = unique_signatures.pop()
    if signature[0] == "none":
        return projection
    if signature[0] == "power":
        projection["target_power_min"] = signature[1]
        projection["target_power_max"] = signature[2]
    elif signature[0] == "heart_rate":
        projection["target_hr_min"] = signature[1]
        projection["target_hr_max"] = signature[2]
    elif signature[0] == "pace":
        projection["target_pace_min"] = _format_pace_seconds(signature[1])
        projection["target_pace_max"] = _format_pace_seconds(signature[2])
    return projection


def synthesize_v1_structure_from_flat(
    *,
    workout_type: str,
    activity_type: str | None,
    planned_duration_min: float | None,
    planned_distance_km: float | None,
    target_power_min: float | None,
    target_power_max: float | None,
    target_hr_min: float | None,
    target_hr_max: float | None,
    target_pace_min: str | None,
    target_pace_max: str | None,
) -> tuple[str, str, StructuredWorkoutV1]:
    """Build a compatibility v1 structure from legacy flat workout fields."""
    normalized_activity_type = normalize_activity_type(
        workout_type,
        activity_type,
    )
    if is_rest_workout(workout_type):
        return normalized_activity_type, "v1", StructuredWorkoutV1()

    duration = _finite_nonnegative(
        planned_duration_min,
        field_name="planned duration",
    )
    distance = _finite_nonnegative(
        planned_distance_km,
        field_name="planned distance",
    )
    if (
        duration is not None
        and duration > 0
        and distance is not None
        and distance > 0
    ):
        raise ValueError(
            "planned duration and distance cannot both be represented "
            "by one structured termination"
        )
    if duration is not None and duration > 0:
        seconds = round(duration * 60)
        if seconds < 1:
            raise ValueError(
                "planned duration is too small for a structured termination"
            )
        termination = {
            "type": "time",
            "seconds": seconds,
        }
    elif distance is not None and distance > 0:
        meters = round(distance * 1000)
        if meters < 1:
            raise ValueError(
                "planned distance is too small for a structured termination"
            )
        termination = {
            "type": "distance",
            "meters": meters,
        }
    else:
        termination = {"type": "open"}

    structure = {
        "steps": [{
            "type": "step",
            "phase": "other",
            "termination": termination,
            "target": _compatibility_target_from_flat(
                target_power_min=target_power_min,
                target_power_max=target_power_max,
                target_hr_min=target_hr_min,
                target_hr_max=target_hr_max,
                target_pace_min=target_pace_min,
                target_pace_max=target_pace_max,
            ),
        }],
    }
    model = StructuredWorkoutV1.model_validate(structure)
    validate_structured_workout(
        workout_type=workout_type,
        activity_type=normalized_activity_type,
        workout_structure_version="v1",
        workout_structure=model,
    )
    return normalized_activity_type, "v1", model


def activity_type_supported_by_target(
    *,
    activity_type: str | None,
    target: str,
) -> bool:
    """Return whether a provider adapter safely supports this activity type."""
    normalized_target = str(target or "").strip().casefold()
    supported = _SUPPORTED_ACTIVITY_TYPES_BY_TARGET.get(normalized_target)
    if supported is None:
        return False
    normalized_activity_type = str(activity_type or "running").strip()
    return normalized_activity_type in supported


def project_workout_provider_compatibility(
    *,
    activity_type: str | None,
    workout_structure_version: object,
    workout_structure: object,
    planned_duration_min: object,
    planned_distance_km: object,
    target_power_min: object,
    target_power_max: object,
    target_hr_min: object,
    target_hr_max: object,
    target_pace_min: object,
    target_pace_max: object,
) -> list[dict[str, Any]]:
    """Project content-only provider compatibility without adapting a workout.

    This mirrors the narrow structures accepted by the existing delivery
    adapters. It deliberately reports every lossy detail instead of deriving
    a flat representation or contacting a provider. Connection eligibility,
    credentials, and delivery authorization remain separate concerns.
    """
    inspection = inspect_workout_structure(
        workout_structure_version=workout_structure_version,
        workout_structure=workout_structure,
    )
    normalized_activity_type = str(activity_type or "running").strip()

    return [
        _garmin_workout_compatibility(
            activity_type=normalized_activity_type,
            inspection=inspection,
            planned_duration_min=planned_duration_min,
            target_values=(
                target_power_min,
                target_power_max,
                target_hr_min,
                target_hr_max,
                target_pace_min,
                target_pace_max,
            ),
        ).model_dump(mode="json", exclude_none=True),
        _stryd_workout_compatibility(
            activity_type=normalized_activity_type,
            inspection=inspection,
            planned_duration_min=planned_duration_min,
            planned_distance_km=planned_distance_km,
            target_power_min=target_power_min,
            target_power_max=target_power_max,
            target_hr_min=target_hr_min,
            target_hr_max=target_hr_max,
            target_pace_min=target_pace_min,
            target_pace_max=target_pace_max,
        ).model_dump(mode="json", exclude_none=True),
    ]


def _garmin_workout_compatibility(
    *,
    activity_type: str,
    inspection: WorkoutStructureInspection,
    planned_duration_min: object,
    target_values: tuple[object, ...],
) -> WorkoutProviderCompatibility:
    """Describe the flat running subset accepted by Garmin delivery."""
    reasons: list[WorkoutProviderCompatibilityReason] = []
    if inspection.state != "absent":
        reasons.append(WorkoutProviderCompatibilityReason(
            code=(
                "structured_workout_not_supported"
                if inspection.state == "supported"
                else "invalid_structure"
            ),
        ))
    if not activity_type_supported_by_target(
        activity_type=activity_type,
        target="garmin",
    ):
        reasons.append(WorkoutProviderCompatibilityReason(
            code="activity_type_not_supported",
        ))
    if inspection.state == "absent":
        if _has_provider_target(target_values):
            reasons.append(WorkoutProviderCompatibilityReason(
                code="target_not_supported",
            ))
        if not _duration_encodes_positive_seconds(planned_duration_min):
            reasons.append(WorkoutProviderCompatibilityReason(
                code="duration_required",
            ))
    return WorkoutProviderCompatibility(
        target="garmin",
        compatible=not reasons,
        mode=(
            "legacy_flat"
            if inspection.state == "absent"
            else "unsupported"
        ),
        reasons=reasons,
    )


def _stryd_workout_compatibility(
    *,
    activity_type: str,
    inspection: WorkoutStructureInspection,
    planned_duration_min: object,
    planned_distance_km: object,
    target_power_min: object,
    target_power_max: object,
    target_hr_min: object,
    target_hr_max: object,
    target_pace_min: object,
    target_pace_max: object,
) -> WorkoutProviderCompatibility:
    """Describe Stryd's verified portable-structure subset."""
    if inspection.state == "absent":
        reasons: list[WorkoutProviderCompatibilityReason] = []
        if not activity_type_supported_by_target(
            activity_type=activity_type,
            target="stryd",
        ):
            reasons.append(WorkoutProviderCompatibilityReason(
                code="activity_type_not_supported",
            ))
        if not _duration_encodes_positive_seconds(planned_duration_min):
            reasons.append(WorkoutProviderCompatibilityReason(
                code="duration_required",
            ))
        if _positive_number(planned_distance_km):
            reasons.append(WorkoutProviderCompatibilityReason(
                code="flat_workout_not_lossless",
            ))
        has_power_min = _positive_number(target_power_min)
        has_power_max = _positive_number(target_power_max)
        has_non_power_target = any((
            target_hr_min not in (None, ""),
            target_hr_max not in (None, ""),
            bool(str(target_pace_min or "").strip()),
            bool(str(target_pace_max or "").strip()),
        ))
        if has_non_power_target or has_power_min != has_power_max:
            reasons.append(WorkoutProviderCompatibilityReason(
                code="target_not_supported",
            ))
        if not (has_power_min and has_power_max):
            reasons.append(WorkoutProviderCompatibilityReason(
                code="flat_workout_not_lossless",
            ))
        return WorkoutProviderCompatibility(
            target="stryd",
            compatible=not reasons,
            mode="legacy_flat",
            reasons=reasons,
        )
    if inspection.state != "supported" or inspection.structure is None:
        return WorkoutProviderCompatibility(
            target="stryd",
            compatible=False,
            mode="unsupported",
            reasons=[WorkoutProviderCompatibilityReason(
                code="invalid_structure",
            )],
        )

    reasons: list[WorkoutProviderCompatibilityReason] = []
    if not activity_type_supported_by_target(
        activity_type=activity_type,
        target="stryd",
    ):
        reasons.append(WorkoutProviderCompatibilityReason(
            code="activity_type_not_supported",
        ))
    if not inspection.structure.steps:
        reasons.append(WorkoutProviderCompatibilityReason(
            code="empty_structure_not_supported",
        ))

    wording_path: str | None = None
    phase_path: str | None = None
    termination_path: str | None = None
    target_path: str | None = None
    for root_index, node in enumerate(inspection.structure.steps):
        if (
            isinstance(node, StructuredWorkoutRepeatGroupV1)
            and node.label is not None
            and wording_path is None
        ):
            wording_path = f"steps[{root_index}].label"
        node_steps = (
            [node]
            if isinstance(node, StructuredWorkoutStepV1)
            else node.steps
        )
        for child_index, step in enumerate(node_steps):
            path = (
                f"steps[{root_index}]"
                if isinstance(node, StructuredWorkoutStepV1)
                else f"steps[{root_index}].steps[{child_index}]"
            )
            if (
                wording_path is None
                and (step.label is not None or step.instructions is not None)
            ):
                wording_path = (
                    f"{path}.label"
                    if step.label is not None
                    else f"{path}.instructions"
                )
            if (
                phase_path is None
                and step.phase not in {
                    "warmup",
                    "work",
                    "recovery",
                    "cooldown",
                }
            ):
                phase_path = f"{path}.phase"
            if (
                termination_path is None
                and step.termination.type != "time"
            ):
                termination_path = f"{path}.termination"
            target_combo = (
                step.target.metric,
                step.target.unit,
                step.target.reference,
            )
            if (
                target_path is None
                and (
                    target_combo not in {
                        ("power", "watts", "absolute"),
                        ("power", "percent_cp", "critical_power"),
                    }
                    or step.target.min is None
                    or step.target.max is None
                )
            ):
                target_path = f"{path}.target"

    for code, path in (
        ("wording_not_supported", wording_path),
        ("phase_not_supported", phase_path),
        ("termination_not_supported", termination_path),
        ("target_not_supported", target_path),
    ):
        if path is not None:
            reasons.append(WorkoutProviderCompatibilityReason(
                code=code,
                path=path,
            ))
    return WorkoutProviderCompatibility(
        target="stryd",
        compatible=not reasons,
        mode="structured" if not reasons else "unsupported",
        reasons=reasons,
    )


def _has_provider_target(values: tuple[object, ...]) -> bool:
    """Return whether a legacy flat target would be omitted by Garmin."""
    return any(value not in (None, "", 0, 0.0) for value in values)


def _positive_number(value: object) -> bool:
    """Return whether a finite numeric value is strictly positive."""
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def _duration_encodes_positive_seconds(value: object) -> bool:
    """Match adapters that encode legacy minutes as rounded whole seconds."""
    if not _positive_number(value):
        return False
    return round(float(value) * 60) >= 1


def stryd_surface_for_activity_type(activity_type: str | None) -> str:
    """Return the safest known Stryd surface for an activity type."""
    normalized = str(activity_type or "running").strip()
    if normalized == "trail_running":
        return "trail"
    return "road"


def structure_is_explicit(
    *,
    workout_structure_version: str | None,
    workout_structure: object,
) -> bool:
    """Return whether an authoritative structure was explicitly provided."""
    return workout_structure_version is not None or workout_structure is not None


def _projectable_target_signature(
    target: IntensityTargetV1,
) -> tuple[Any, ...] | None:
    combo = (target.metric, target.unit, target.reference)
    if combo == ("none", "none", "none"):
        return ("none", None, None)
    if combo == ("power", "watts", "absolute"):
        return ("power", target.min, target.max)
    if combo == ("heart_rate", "bpm", "absolute"):
        return ("heart_rate", target.min, target.max)
    if combo == ("pace", "sec_per_km", "absolute"):
        return ("pace", target.min, target.max)
    return None


def _format_pace_seconds(value: float | None) -> str | None:
    if value is None:
        return None
    rounded = int(round(value))
    minutes, seconds = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _parse_pace_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for suffix in ("min/km", "mi/km", "/km", "min", "sec"):
        while text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    if ":" in text:
        try:
            parts = text.split(":")
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = float(parts[1])
                if minutes < 0 or not 0 <= seconds < 60:
                    return None
                total = minutes * 60 + seconds
            elif len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                if (
                    hours < 0
                    or not 0 <= minutes < 60
                    or not 0 <= seconds < 60
                ):
                    return None
                total = hours * 3600 + minutes * 60 + seconds
            else:
                return None
            return total if total > 0 else None
        except ValueError:
            return None
    try:
        candidate = float(text)
    except ValueError:
        return None
    return candidate if candidate > 0 else None


def _finite_nonnegative(
    value: float | None,
    *,
    field_name: str,
) -> float | None:
    if value is None:
        return None
    candidate = float(value)
    if not math.isfinite(candidate) or candidate < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return candidate


def _compatibility_target_from_flat(
    *,
    target_power_min: float | None,
    target_power_max: float | None,
    target_hr_min: float | None,
    target_hr_max: float | None,
    target_pace_min: str | None,
    target_pace_max: str | None,
) -> dict[str, Any]:
    target_families = sum((
        target_power_min is not None or target_power_max is not None,
        target_hr_min is not None or target_hr_max is not None,
        bool(str(target_pace_min or "").strip())
        or bool(str(target_pace_max or "").strip()),
    ))
    if target_families > 1:
        raise ValueError(
            "flat targets use multiple metrics and cannot form one v1 target"
        )
    if target_power_min is not None or target_power_max is not None:
        result = {
            "metric": "power",
            "unit": "watts",
            "reference": "absolute",
        }
        if target_power_min is not None:
            result["min"] = target_power_min
        if target_power_max is not None:
            result["max"] = target_power_max
        return result
    if target_hr_min is not None or target_hr_max is not None:
        result = {
            "metric": "heart_rate",
            "unit": "bpm",
            "reference": "absolute",
        }
        if target_hr_min is not None:
            result["min"] = target_hr_min
        if target_hr_max is not None:
            result["max"] = target_hr_max
        return result
    pace_min = _parse_pace_seconds(target_pace_min)
    pace_max = _parse_pace_seconds(target_pace_max)
    if (
        str(target_pace_min or "").strip()
        and pace_min is None
    ) or (
        str(target_pace_max or "").strip()
        and pace_max is None
    ):
        raise ValueError("pace target is invalid")
    if pace_min is not None or pace_max is not None:
        result = {
            "metric": "pace",
            "unit": "sec_per_km",
            "reference": "absolute",
        }
        if pace_min is not None:
            result["min"] = pace_min
        if pace_max is not None:
            result["max"] = pace_max
        return result
    return {
        "metric": "none",
        "unit": "none",
        "reference": "none",
    }
