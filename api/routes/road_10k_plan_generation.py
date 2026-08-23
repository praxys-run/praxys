"""Typed authenticated API for deterministic road 10K proposals."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from analysis.road_10k_plan_generation import Road10KPlanGenerationConstraints
from api.adaptive_plan_service import AdaptivePlanError
from api.auth import get_current_user_id
from api.plan_generation_capabilities import PlanPurposeError
from api.road_10k_baseline import (
    Road10KBaselineConflict,
    Road10KBaselineForbidden,
    Road10KBaselineInvalid,
    Road10KBaselineNotFound,
    confirm_road_10k_history_candidate,
)
from api.road_10k_control import (
    Road10KControlError,
    coerce_road_10k_control_error,
)
from api.road_10k_plan_generation import (
    Road10KGenerationError,
    build_road_10k_alternatives,
    build_road_10k_readiness,
    generate_road_10k_proposal,
    regenerate_road_10k_proposal,
)
from db.session import get_db

_PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Pragma": "no-cache",
    "Vary": "Authorization",
}


def _require_road_10k_capability_available() -> None:
    """Statically deny every Road stage request before request I/O."""
    raise HTTPException(
        status_code=404,
        detail="Not found",
        headers=_PRIVATE_HEADERS,
    )


def _require_road_10k_owner(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    from db.models import User

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.is_demo or not user.is_active:
        raise HTTPException(403, "First-party authentication required")
    return user_id


def _private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"


router = APIRouter(
    dependencies=[
        Depends(_require_road_10k_capability_available),
        Depends(_private_response),
    ],
    include_in_schema=False,
)
Weekday = Literal[0, 1, 2, 3, 4, 5, 6]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]
Road10KResultCode = Literal[
    "eligible_rolling_proposal",
    "eligible_taper_proposal",
    "missing_or_stale_direct_baseline",
    "insufficient_recent_history",
    "limited_guidance_event_conflict",
    "limited_near_term_guidance",
    "safety_stop",
    "adult_scope_or_constraints_unconfirmed",
    "contradictory_input",
    "unsupported_intent_distance_surface_or_population",
    "no_schedule_within_envelope",
    "validation_failed",
]
Road10KSurfaceOrProtocol = Literal[
    "organized_outdoor_road_10k_race",
    "standardized_outdoor_road_10k_time_trial",
    "standardized_track_10k_time_trial",
]
Road10KAssistanceStatus = Literal[
    "unassisted",
    "assisted",
    "unknown_or_unreported",
]


class PlanGenerationPurposeRequest(BaseModel):
    """Exact current-Goal or capability-owned purpose selection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    capability_id: str = Field(min_length=1, max_length=80)
    source: Literal["current_goal", "capability", "unlinked"]
    expected_goal_id: str | None = Field(
        ...,
        min_length=36,
        max_length=36,
    )
    expected_goal_revision: str | None = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def validate_source_fence(self) -> "PlanGenerationPurposeRequest":
        if self.source == "current_goal":
            if self.expected_goal_id is None or self.expected_goal_revision is None:
                raise ValueError(
                    "current_goal requires expected_goal_id and expected_goal_revision"
                )
        elif (
            self.expected_goal_id is not None
            or self.expected_goal_revision is not None
        ):
            raise ValueError(
                "only current_goal may include expected Goal provenance"
            )
        return self


class Road10KConstraintsRequest(BaseModel):
    """Structured, purpose-bounded athlete statements for the road 10K path."""

    model_config = ConfigDict(extra="forbid", strict=True)

    purpose: PlanGenerationPurposeRequest | None = None
    adult_confirmed: bool
    current_symptom_stop: bool | None
    available_weekdays: list[Weekday] = Field(min_length=1, max_length=7)
    weekly_time_limit_min: int = Field(ge=1)
    maximum_session_duration_min: int = Field(ge=1)
    unavailable_dates: list[date] = Field(max_length=28)
    unavailable_dates_confirmed_none: bool
    event_context_confirmed_none: bool
    outdoor_road_intent_confirmed: bool
    preferred_longest_easy_weekday: Weekday | None = None
    benchmark_date: date | None = None

    @model_validator(mode="after")
    def validate_explicit_statements(self) -> "Road10KConstraintsRequest":
        dates = self.unavailable_dates
        if not dates and not self.unavailable_dates_confirmed_none:
            raise ValueError("empty unavailable dates require explicit none")
        elif dates and self.unavailable_dates_confirmed_none:
            raise ValueError("unavailable dates conflict with explicit none")
        elif dates != sorted(set(dates)):
            raise ValueError("unavailable dates must be unique and sorted")
        return self


class Road10KReadinessRequest(Road10KConstraintsRequest):
    """Read-only readiness request."""


class Road10KGenerateRequest(Road10KConstraintsRequest):
    """Exact source-fenced, idempotent proposal request."""

    expected_source_revision: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    idempotency_key: str = Field(min_length=8, max_length=128)


class Road10KRegenerateRequest(Road10KGenerateRequest):
    """Exact proposal-version request for one bounded successor."""

    expected_proposal_version: int = Field(ge=1)


class Road10KHistoryConfirmationRequest(BaseModel):
    """Explicit review of a surfaced 10K direct-baseline candidate."""

    model_config = ConfigDict(extra="forbid", strict=True)

    activity_id: str
    response: Literal["race", "intentional_all_out", "not_all_out", "deleted"]
    measured_10k: bool
    elapsed_timing_confirmed: bool
    surface_or_protocol: Road10KSurfaceOrProtocol | None = None
    route_or_venue_identifier: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    assistance_status: Road10KAssistanceStatus
    supersedes_confirmation_id: str | None = None
    purpose: PlanGenerationPurposeRequest | None = None


class Road10KEventContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_version: str
    state: Literal["unconfirmed", "confirmed_none", "single_target", "race_dense"]
    goal_target_date: str | None
    benchmark_date: str | None
    target_date: str | None
    target_source: Literal["goal", "benchmark"] | None


class Road10KHistoryStatisticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usable_completed_weeks: int
    recent_modal_running_frequency: int
    recent_median_usable_weekly_minutes: int
    recent_maximum_usable_weekly_minutes: int
    recent_maximum_session_minutes: int
    recent_maximum_session_distance_km: float | None
    latest_run_date: str | None


class Road10KOutcomeResponse(BaseModel):
    """Typed road 10K outcome envelope shared by readiness and proposals."""

    model_config = ConfigDict(extra="forbid")

    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    code: Road10KResultCode
    route_state: Literal[
        "plan_candidate",
        "readiness_only",
        "clarification_required",
        "policy_unavailable",
    ]
    plan_returned: bool
    adoption_required: bool | None = None
    goal_remains_recorded: bool | None = None
    limited_guidance_returned: bool | None = None
    deterministic_input_hash: str
    event_context: Road10KEventContextResponse
    history_statistics: Road10KHistoryStatisticsResponse
    failed_rule_id: str | None
    observed_or_stated_reason: str | None
    uncertainty_or_missing_field: str | None
    alternatives: list[str]


class Road10KTaperGuardrailProjectionResponse(BaseModel):
    """Digest-bound taper evidence and claim-limit projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    planned_volume_reduction_fraction: float
    maintain_intensity_exposure_without_adding_quality: Literal[True]
    evidence_population: Literal["mixed_endurance_athletes"]
    direct_recreational_road_10k_validation: Literal[False]
    single_target_taper_result: Literal[
        "taper_proposal_truncated_to_event_eve"
    ]
    personal_performance_gain_claim: Literal[False]
    causal_plan_benefit_claim: Literal["disabled"]
    personal_injury_probability: Literal["disabled"]


class Road10KGuardrailProjectionResponse(BaseModel):
    """Read-only accepted values exposed without snapshot provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    committed_proposal_days: int
    advisory_reassessment_after_completed_days: int
    minimum_planned_low_intensity_running_minutes_fraction: float
    baseline_current_through_completed_days: int
    taper: Road10KTaperGuardrailProjectionResponse


class Road10KPurposeResponse(BaseModel):
    """Resolved purpose included in readiness and proposal responses."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    source: Literal["current_goal", "capability", "unlinked"]
    expected_goal_id: str | None
    expected_goal_revision: str | None
    goal: "Road10KPurposeGoalResponse"


class Road10KPurposeGoalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_kind: str | None
    distance: str | None
    target_time_sec: int | None
    race_date: str | None


class Road10KBaselineEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provenance: Literal["race", "intentional_all_out"]
    observed_date: str
    age_days: int
    completed_at: str | None
    distance_km: float | None
    elapsed_time_sec: float | None
    activity_id: str | None
    measured_10k_confirmed: bool
    elapsed_timing_confirmed: bool
    surface_or_protocol: Road10KSurfaceOrProtocol | None
    route_or_venue_identifier: str | None
    assistance_status: Road10KAssistanceStatus | None
    source_provider: str | None
    change_comparability: Literal[
        "not_assessed",
        "supporting",
        "incomparable",
        "directly_comparable",
    ]


class Road10KBaselineCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str
    observed_date: str
    distance_km: float | None
    duration_sec: float | None
    source: str | None
    completed_at: str | None
    review_state: Literal[
        "needs_confirmation",
        "qualified",
        "excluded",
        "distance_unverified",
        "timing_unresolved",
    ]
    confirmation_response: Literal[
        "race",
        "intentional_all_out",
        "not_all_out",
    ] | None
    measured_10k_confirmed: bool | None
    elapsed_timing_confirmed: bool | None
    surface_or_protocol: Road10KSurfaceOrProtocol | None
    route_or_venue_identifier: str | None
    assistance_status: Road10KAssistanceStatus | None
    source_provider: str | None
    full_activity_only: Literal[True]
    split_count: int
    sample_observed_duration_sec: float | None
    timing_gap_count: int


class Road10KBenchmarkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    automatic_scheduling: Literal[False]
    explicit_choice_required: Literal[True]


class Road10KScienceCitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    url: str


class Road10KScienceNoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    citations: list[Road10KScienceCitationResponse]


class Road10KBaselineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    science_decision_id: str
    contract_digest: str
    baseline_snapshot_version: str
    guardrails: Road10KGuardrailProjectionResponse
    status: Literal["current", "stale", "incomparable", "missing", "not_required"]
    readiness: Literal["sufficient_baseline", "insufficient_evidence"]
    history_search_complete: Literal[True]
    full_activity_only: Literal[True]
    history_cutoff_completed_days: int
    alternatives: list[str]
    evidence: Road10KBaselineEvidenceResponse | None
    candidates: list[Road10KBaselineCandidateResponse]
    benchmark: Road10KBenchmarkResponse
    science_note: Road10KScienceNoteResponse


class Road10KWorkoutTerminationTimeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["time"]
    seconds: int


class Road10KWorkoutTerminationDistanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["distance"]
    meters: int


class Road10KWorkoutTerminationOpenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["open", "manual"]


Road10KWorkoutTerminationResponse = Annotated[
    Road10KWorkoutTerminationTimeResponse
    | Road10KWorkoutTerminationDistanceResponse
    | Road10KWorkoutTerminationOpenResponse,
    Field(discriminator="type"),
]


class Road10KWorkoutTargetNoneResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: Literal["none"]
    unit: Literal["none"]
    reference: Literal["none"]


class _Road10KBoundedWorkoutTargetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def require_one_bound(self):
        if self.min is None and self.max is None:
            raise ValueError("a bounded workout target requires min or max")
        return self


class Road10KWorkoutPowerWattsTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["power"]
    unit: Literal["watts"]
    reference: Literal["absolute"]


class Road10KWorkoutPowerPercentTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["power"]
    unit: Literal["percent_cp"]
    reference: Literal["critical_power"]


class Road10KWorkoutHeartRateBpmTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["heart_rate"]
    unit: Literal["bpm"]
    reference: Literal["absolute"]


class Road10KWorkoutHeartRatePercentTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["heart_rate"]
    unit: Literal["percent_lthr"]
    reference: Literal["lthr"]


class Road10KWorkoutPaceTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["pace"]
    unit: Literal["sec_per_km"]
    reference: Literal["absolute"]


class Road10KWorkoutPaceDeltaTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["pace"]
    unit: Literal["sec_per_km_delta"]
    reference: Literal["threshold_pace"]


class Road10KWorkoutRpeTargetResponse(_Road10KBoundedWorkoutTargetResponse):
    metric: Literal["rpe"]
    unit: Literal["scale_10"]
    reference: Literal["perceived_exertion"]


Road10KWorkoutTargetResponse = (
    Road10KWorkoutTargetNoneResponse
    | Road10KWorkoutPowerWattsTargetResponse
    | Road10KWorkoutPowerPercentTargetResponse
    | Road10KWorkoutHeartRateBpmTargetResponse
    | Road10KWorkoutHeartRatePercentTargetResponse
    | Road10KWorkoutPaceTargetResponse
    | Road10KWorkoutPaceDeltaTargetResponse
    | Road10KWorkoutRpeTargetResponse
)


class Road10KWorkoutStepResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["step"]
    phase: Literal[
        "warmup",
        "work",
        "recovery",
        "rest",
        "cooldown",
        "other",
    ]
    label: str | None = None
    instructions: str | None = None
    termination: Road10KWorkoutTerminationResponse
    target: Road10KWorkoutTargetResponse


class Road10KWorkoutRepeatGroupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["repeat"]
    label: str | None = None
    repetitions: int = Field(ge=1)
    steps: list[Road10KWorkoutStepResponse]


Road10KWorkoutStructureStepResponse = Annotated[
    Road10KWorkoutStepResponse | Road10KWorkoutRepeatGroupResponse,
    Field(discriminator="type"),
]


class Road10KWorkoutStructureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[Road10KWorkoutStructureStepResponse]


class Road10KProposalWorkoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    date: str
    activity_type: Literal["running"]
    workout_type: str
    planned_duration_min: float | None
    planned_distance_km: float | None
    target_power_min: float | None
    target_power_max: float | None
    target_hr_min: float | None
    target_hr_max: float | None
    target_pace_min: str | None
    target_pace_max: str | None
    workout_description: str
    workout_structure_version: Literal["v1"]
    workout_structure: Road10KWorkoutStructureResponse


class Road10KProposalTargetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance: str
    criterion: str
    setting: str
    target_time_sec: int | None
    target_event_date: str | None
    benchmark_date: str | None
    event_state: Literal["confirmed_none", "single_target", "race_dense"]


class Road10KProposalGoalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int
    state: Literal["draft", "active", "superseded"]
    goal_kind: str
    purpose_source: Literal["current_goal", "capability", "unlinked"]
    source_goal_id: str | None
    source_goal_revision: str | None
    target: Road10KProposalTargetResponse
    horizon_start: str
    horizon_end: str
    acknowledged_at: str | None

    @model_validator(mode="after")
    def validate_purpose_provenance(self) -> "Road10KProposalGoalResponse":
        """Keep current-Goal provenance paired and absent elsewhere."""
        has_goal_id = self.source_goal_id is not None
        has_goal_revision = self.source_goal_revision is not None
        if self.purpose_source == "current_goal":
            if not has_goal_id or not has_goal_revision:
                raise ValueError(
                    "current_goal requires source Goal provenance"
                )
        elif has_goal_id or has_goal_revision:
            raise ValueError(
                "non-current Goal purpose cannot carry source provenance"
            )
        return self


class Road10KAdaptivePlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    discipline: Literal["running"]
    version: int
    lifecycle: Literal["draft", "active", "completed", "archived"]
    active_proposal_id: str | None


class Road10KProposalDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    adaptive_plan_id: str
    goal_snapshot_id: str
    discipline: Literal["running"]
    version: int
    state: Literal["draft", "superseded", "rejected", "adopted", "expired"]
    base_plan_version: int
    supersedes_proposal_id: str | None
    origin: str
    actor_type: Literal["user", "agent", "system"]
    actor_id: str | None
    policy_version: str | None
    model_version: str | None
    science_version: str | None
    assumptions: list[object]
    unknowns: list[object]
    warnings: list[object]
    alternatives: list[object]
    expires_at: str | None
    created_at: str | None
    decided_at: str | None
    workouts: list[Road10KProposalWorkoutResponse]
    adaptive_plan: Road10KAdaptivePlanResponse | None
    goal: Road10KProposalGoalResponse | None


class Road10KConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lineage_id: str
    version: int
    supersedes_id: str | None
    activity_id: str
    response: Literal["race", "intentional_all_out", "not_all_out", "deleted"]
    measured_10k: bool
    elapsed_timing_confirmed: bool
    completed_at: str
    elapsed_time_sec: float | None
    surface_or_protocol: Road10KSurfaceOrProtocol | None
    route_or_venue_identifier: str | None
    assistance_status: Road10KAssistanceStatus
    source_provider: str
    created_at: str


class Road10KReadinessResponse(BaseModel):
    """Typed no-write readiness response."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    capability_id: str
    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    source_revision: str
    guardrails: Road10KGuardrailProjectionResponse
    purpose: Road10KPurposeResponse
    baseline: Road10KBaselineResponse
    athlete_today: str
    block_start: str
    event_context: Road10KEventContextResponse
    history_cutoff_completed_days: int
    template_ids: list[str]
    result: Road10KOutcomeResponse


class Road10KAlternativesResponse(Road10KReadinessResponse):
    """Readiness plus the policy-bounded next steps."""

    alternatives: list[str]


class Road10KProposalResponse(BaseModel):
    """Typed proposal response; the proposal remains non-canonical."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    capability_id: str
    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    source_revision: str
    guardrails: Road10KGuardrailProjectionResponse
    purpose: Road10KPurposeResponse
    event_context: Road10KEventContextResponse
    history_cutoff_completed_days: int
    template_ids: list[str]
    result: Road10KOutcomeResponse
    proposal: Road10KProposalDetailResponse | None = None
    replayed: bool = False
    reassessment_dates: list[str] = Field(default_factory=list)


class Road10KBaselineMutationResponse(BaseModel):
    """Append-only confirmation response for direct 10K baseline review."""

    model_config = ConfigDict(extra="forbid")

    replayed: bool
    guardrails: Road10KGuardrailProjectionResponse
    baseline: Road10KBaselineResponse
    confirmation: Road10KConfirmationResponse | None = None


def _constraints(body: Road10KConstraintsRequest) -> Road10KPlanGenerationConstraints:
    return Road10KPlanGenerationConstraints(
        adult_confirmed=body.adult_confirmed,
        current_symptom_stop=body.current_symptom_stop,
        available_weekdays=tuple(int(item) for item in body.available_weekdays),
        weekly_time_limit_min=body.weekly_time_limit_min,
        maximum_session_duration_min=body.maximum_session_duration_min,
        unavailable_dates=tuple(body.unavailable_dates or ()),
        unavailable_dates_confirmed_none=body.unavailable_dates_confirmed_none,
        event_context_confirmed_none=body.event_context_confirmed_none,
        outdoor_road_intent_confirmed=body.outdoor_road_intent_confirmed,
        preferred_longest_easy_weekday=(
            int(body.preferred_longest_easy_weekday)
            if body.preferred_longest_easy_weekday is not None
            else None
        ),
        benchmark_date=body.benchmark_date,
    )


def _purpose(body: Road10KConstraintsRequest | Road10KHistoryConfirmationRequest) -> dict[str, Any] | None:
    if body.purpose is None:
        return None
    return body.purpose.model_dump(mode="json")


def _raise_generation(error: Exception) -> None:
    normalized = coerce_road_10k_control_error(error)
    if isinstance(normalized, Road10KControlError):
        raise HTTPException(
            status_code=404,
            detail="Not found",
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, Road10KGenerationError):
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, AdaptivePlanError):
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, PlanPurposeError):
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
            headers=_PRIVATE_HEADERS,
        )
    raise error


def _raise_baseline(error: Exception) -> None:
    normalized = coerce_road_10k_control_error(error)
    if isinstance(normalized, Road10KControlError):
        raise HTTPException(
            status_code=404,
            detail="Not found",
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, PlanPurposeError):
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, Road10KBaselineConflict):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ROAD_10K_BASELINE_IDEMPOTENCY_CONFLICT",
                "message": "This Idempotency-Key was already used for a different road 10K baseline request.",
            },
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, Road10KBaselineNotFound):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ROAD_10K_BASELINE_NOT_FOUND",
                "message": "The requested 10K baseline activity was not found for this athlete.",
            },
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, Road10KBaselineForbidden):
        message = {
            "BASELINE_NOT_REQUIRED": "This goal is outside the current road 10K direct-baseline flow.",
        }.get(str(error), "The requested 10K baseline action is unavailable in the current state.")
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ROAD_10K_BASELINE_MUTATION_FORBIDDEN",
                "message": message,
            },
            headers=_PRIVATE_HEADERS,
        )
    if isinstance(error, Road10KBaselineInvalid):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ROAD_10K_BASELINE_INVALID_REQUEST",
                "message": str(error),
            },
            headers=_PRIVATE_HEADERS,
        )
    raise error


@router.post(
    "/plan/road-10k/readiness",
    response_model=Road10KReadinessResponse,
    response_model_exclude_unset=True,
)
def post_road_10k_readiness(
    body: Road10KReadinessRequest,
    user_id: str = Depends(_require_road_10k_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evaluate the reviewed road 10K policy without persisting a proposal."""
    try:
        result = build_road_10k_readiness(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            purpose_selection=_purpose(body),
        )
        return result
    except Exception as exc:
        _raise_generation(exc)
        raise


@router.post(
    "/plan/road-10k/alternatives",
    response_model=Road10KAlternativesResponse,
    response_model_exclude_unset=True,
)
def post_road_10k_alternatives(
    body: Road10KReadinessRequest,
    user_id: str = Depends(_require_road_10k_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return only policy-bounded alternatives for the current 10K state."""
    try:
        result = build_road_10k_alternatives(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            purpose_selection=_purpose(body),
        )
        return result
    except Exception as exc:
        _raise_generation(exc)
        raise


@router.post(
    "/plan/road-10k/generate",
    response_model=Road10KProposalResponse | Road10KReadinessResponse,
    response_model_exclude_unset=True,
)
def post_road_10k_generate(
    body: Road10KGenerateRequest,
    response: Response,
    user_id: str = Depends(_require_road_10k_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a non-canonical road 10K proposal after exact readiness validation."""
    try:
        result, replayed = generate_road_10k_proposal(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            expected_source_revision=body.expected_source_revision,
            idempotency_key=body.idempotency_key,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise_generation(exc)
        raise
    if not result["result"]["plan_returned"] or replayed:
        return result
    response.status_code = status.HTTP_201_CREATED
    return result


@router.post(
    "/plan/road-10k/proposals/{proposal_id}/regenerate",
    response_model=Road10KProposalResponse | Road10KReadinessResponse,
    response_model_exclude_unset=True,
)
def post_road_10k_regenerate(
    proposal_id: UUID,
    body: Road10KRegenerateRequest,
    response: Response,
    user_id: str = Depends(_require_road_10k_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create an exact-version road 10K successor when source inputs changed."""
    try:
        result, replayed = regenerate_road_10k_proposal(
            db,
            user_id=user_id,
            proposal_id=str(proposal_id),
            expected_proposal_version=body.expected_proposal_version,
            constraints=_constraints(body),
            expected_source_revision=body.expected_source_revision,
            idempotency_key=body.idempotency_key,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise_generation(exc)
        raise
    if not result["result"]["plan_returned"] or replayed:
        return result
    response.status_code = status.HTTP_201_CREATED
    return result


@router.post(
    "/plan/road-10k/baseline/history/confirm",
    response_model=Road10KBaselineMutationResponse,
    status_code=201,
)
def post_road_10k_history_confirmation(
    body: Road10KHistoryConfirmationRequest,
    idempotency_key: IdempotencyKey,
    response: Response,
    user_id: str = Depends(_require_road_10k_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Confirm a surfaced 10K activity as direct baseline evidence."""
    try:
        result = confirm_road_10k_history_candidate(
            db,
            user_id=user_id,
            activity_id=body.activity_id,
            response=body.response,
            measured_10k=body.measured_10k,
            elapsed_timing_confirmed=body.elapsed_timing_confirmed,
            surface_or_protocol=body.surface_or_protocol,
            route_or_venue_identifier=body.route_or_venue_identifier,
            assistance_status=body.assistance_status,
            idempotency_key=idempotency_key,
            supersedes_confirmation_id=body.supersedes_confirmation_id,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise_baseline(exc)
        raise
    if result["replayed"]:
        response.status_code = 200
    return result
