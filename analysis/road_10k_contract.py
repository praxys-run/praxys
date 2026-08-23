"""Reviewed machine-contract helpers for the inactive road 10K capability."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from analysis.science_artifacts import load_policy_contract


ROAD_10K_SCIENCE_DECISION_ID = "sdr-road-10k-plan-generation-policy-v2"
ROAD_10K_GENERATOR_VERSION = "road-10k-deterministic-generator-v1"
ROAD_10K_CONTRACT_DIGEST = (
    "sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496"
)
ROAD_10K_SOURCE_DECISION_DIGEST = (
    "sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad"
)
ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION = "road-10k-training-pattern-v1"
ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION = "road-10k-event-context-v1"
ROAD_10K_BASELINE_SNAPSHOT_VERSION = "road-10k-direct-baseline-v1"

ROAD_10K_CONTRACT = load_policy_contract(
    ROAD_10K_SCIENCE_DECISION_ID,
    require_active=False,
)
if ROAD_10K_CONTRACT.contract_digest != ROAD_10K_CONTRACT_DIGEST:
    raise ValueError("road 10K contract digest mismatch")
if ROAD_10K_CONTRACT.source_decision_digest != ROAD_10K_SOURCE_DECISION_DIGEST:
    raise ValueError("road 10K source decision digest mismatch")

ROAD_10K_POLICY_VERSION = ROAD_10K_CONTRACT.model_version
ROAD_10K_PARAMETER_VALUES = ROAD_10K_CONTRACT.parameter_values
ROAD_10K_CAPABILITY = ROAD_10K_PARAMETER_VALUES["road_10k_v2_capability_tuple"]
ROAD_10K_REQUIRED_INPUTS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_required_inputs"
]
ROAD_10K_READINESS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_readiness_and_missingness"
]
ROAD_10K_EXECUTION = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_execution_window_and_reassessment"
]
ROAD_10K_SCHEDULE = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_schedule_construction"
]
ROAD_10K_TEMPLATES = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_workout_templates"
]
ROAD_10K_INTENSITY = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_intensity_quality_and_spacing"
]
ROAD_10K_EVENTS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_event_benchmark_and_taper"
]
ROAD_10K_TYPED_OUTCOMES = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_typed_outcomes"
]["outcomes"]
ROAD_10K_DEMOGRAPHICS = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_demographic_and_claim_limits"
]
ROAD_10K_ACTIVATION = ROAD_10K_PARAMETER_VALUES[
    "road_10k_v2_activation_and_dependencies"
]
ROAD_10K_AUDIT = ROAD_10K_PARAMETER_VALUES["road_10k_v2_privacy_and_audit"]


@dataclass(frozen=True)
class Road10KTaperGuardrailProjection:
    """Accepted taper and claim limits exposed without provenance."""

    planned_volume_reduction_fraction: float
    maintain_intensity_exposure_without_adding_quality: bool
    evidence_population: str
    direct_recreational_road_10k_validation: bool
    single_target_taper_result: str
    personal_performance_gain_claim: bool
    causal_plan_benefit_claim: str
    personal_injury_probability: str


@dataclass(frozen=True)
class Road10KGuardrailProjection:
    """Public read-only values used to explain the accepted policy."""

    committed_proposal_days: int
    advisory_reassessment_after_completed_days: int
    minimum_planned_low_intensity_running_minutes_fraction: float
    baseline_current_through_completed_days: int
    taper: Road10KTaperGuardrailProjection

    def public_payload(self) -> dict[str, Any]:
        """Return the response-safe projection without policy provenance."""
        return asdict(self)


ROAD_10K_HISTORY_LOOKBACK_COMPLETED_WEEKS = int(
    ROAD_10K_REQUIRED_INPUTS["recent_history_lookback_completed_weeks"]
)
ROAD_10K_HISTORY_CUTOFF_COMPLETED_DAYS = (
    ROAD_10K_HISTORY_LOOKBACK_COMPLETED_WEEKS * 7
)
ROAD_10K_BASELINE_CURRENT_THROUGH_COMPLETED_DAYS = int(
    ROAD_10K_READINESS["baseline_current_through_completed_days"]
)
ROAD_10K_BASELINE_STALE_FROM_COMPLETED_DAYS = int(
    ROAD_10K_READINESS["baseline_stale_from_completed_days"]
)
ROAD_10K_PROPOSAL_DAYS = int(ROAD_10K_EXECUTION["committed_proposal_days"])
ROAD_10K_REASSESSMENT_COMPLETED_DAYS = int(
    ROAD_10K_EXECUTION["advisory_reassessment_after_completed_days"]
)
ROAD_10K_TAPER_MINIMUM_DAYS_BEFORE_EVENT = int(
    ROAD_10K_EVENTS["taper"]["supported_window_days_before_event"]["minimum"]
)
ROAD_10K_TAPER_MAXIMUM_DAYS_BEFORE_EVENT = int(
    ROAD_10K_EVENTS["taper"]["supported_window_days_before_event"]["maximum"]
)
ROAD_10K_GUARDRAILS = Road10KGuardrailProjection(
    committed_proposal_days=ROAD_10K_PROPOSAL_DAYS,
    advisory_reassessment_after_completed_days=(
        ROAD_10K_REASSESSMENT_COMPLETED_DAYS
    ),
    minimum_planned_low_intensity_running_minutes_fraction=float(
        ROAD_10K_INTENSITY[
            "minimum_planned_low_intensity_running_minutes_fraction"
        ]
    ),
    baseline_current_through_completed_days=(
        ROAD_10K_BASELINE_CURRENT_THROUGH_COMPLETED_DAYS
    ),
    taper=Road10KTaperGuardrailProjection(
        planned_volume_reduction_fraction=float(
            ROAD_10K_EVENTS["taper"]["planned_volume_reduction_fraction"]
        ),
        maintain_intensity_exposure_without_adding_quality=bool(
            ROAD_10K_EVENTS["taper"][
                "maintain_intensity_exposure_without_adding_quality"
            ]
        ),
        evidence_population=str(
            ROAD_10K_EVENTS["taper"]["evidence_population"]
        ),
        direct_recreational_road_10k_validation=bool(
            ROAD_10K_EVENTS["taper"][
                "direct_recreational_road_10k_validation"
            ]
        ),
        single_target_taper_result=str(
            ROAD_10K_EVENTS["single_target"][
                "target_8_to_14_days_after_start"
            ]
        ),
        personal_performance_gain_claim=bool(
            ROAD_10K_EVENTS["taper"][
                "personal_performance_gain_claim"
            ]
        ),
        causal_plan_benefit_claim=str(
            ROAD_10K_DEMOGRAPHICS["causal_plan_benefit_claim"]
        ),
        personal_injury_probability=str(
            ROAD_10K_DEMOGRAPHICS["personal_injury_probability"]
        ),
    ),
)
ROAD_10K_RESULT_CODES = frozenset(str(code) for code in ROAD_10K_TYPED_OUTCOMES)
_ROAD_10K_TYPED_OUTCOME_FIELDS = frozenset({
    "route_state",
    "plan_returned",
    "adoption_required",
    "goal_remains_recorded",
    "limited_guidance_returned",
})


def road_10k_typed_outcome(code: str) -> dict[str, Any]:
    """Return the exact accepted runtime outcome fields for one result code."""
    raw = ROAD_10K_TYPED_OUTCOMES.get(code)
    if not isinstance(raw, dict):
        raise ValueError(f"Unsupported road 10K typed outcome code: {code}")
    keys = set(raw)
    missing = {"route_state", "plan_returned"} - keys
    if missing:
        raise ValueError(
            f"Road 10K typed outcome {code} is missing fields: {sorted(missing)}"
        )
    unexpected = keys - _ROAD_10K_TYPED_OUTCOME_FIELDS
    if unexpected:
        raise ValueError(
            f"Road 10K typed outcome {code} has unsupported fields: {sorted(unexpected)}"
        )
    payload: dict[str, Any] = {
        "route_state": str(raw["route_state"]),
        "plan_returned": bool(raw["plan_returned"]),
    }
    for field in (
        "adoption_required",
        "goal_remains_recorded",
        "limited_guidance_returned",
    ):
        if field in raw:
            payload[field] = bool(raw[field])
    return payload
