"""Typed authenticated API for deterministic road 10K proposals."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from analysis.road_10k_plan_generation import Road10KPlanGenerationConstraints
from api.adaptive_plan_service import AdaptivePlanError
from api.auth import get_data_user_id, require_write_access
from api.plan_generation_capabilities import (
    PlanPurposeError,
    road_10k_capability_available,
)
from api.road_10k_baseline import (
    Road10KBaselineConflict,
    Road10KBaselineForbidden,
    Road10KBaselineInvalid,
    Road10KBaselineNotFound,
    confirm_road_10k_history_candidate,
)
from api.road_10k_plan_generation import (
    Road10KGenerationError,
    build_road_10k_alternatives,
    build_road_10k_readiness,
    generate_road_10k_proposal,
    regenerate_road_10k_proposal,
)
from db.session import get_db


def _require_road_10k_capability_available() -> None:
    if not road_10k_capability_available():
        raise HTTPException(status_code=404, detail="Not found")


router = APIRouter(
    dependencies=[Depends(_require_road_10k_capability_available)]
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
    expected_goal_id: str | None = Field(default=None, min_length=36, max_length=36)
    expected_goal_revision: str | None = Field(
        default=None,
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
    current_symptom_stop: bool = False
    available_weekdays: list[Weekday] = Field(min_length=1, max_length=7)
    weekly_time_limit_min: int = Field(ge=1)
    maximum_session_duration_min: int = Field(ge=1)
    unavailable_dates: list[date] = Field(default_factory=list, max_length=28)
    preferred_longest_easy_weekday: Weekday | None = None
    benchmark_date: date | None = None


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
    event_context: dict[str, Any]
    history_statistics: dict[str, Any]
    failed_rule_id: str | None
    observed_or_stated_reason: str | None
    uncertainty_or_missing_field: str | None
    alternatives: list[str]


class Road10KPurposeResponse(BaseModel):
    """Resolved purpose included in readiness and proposal responses."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    source: Literal["current_goal", "capability", "unlinked"]
    expected_goal_id: str | None
    expected_goal_revision: str | None
    goal: dict[str, Any]


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
    purpose: Road10KPurposeResponse
    baseline: dict[str, Any]
    athlete_today: str
    block_start: str
    event_context: dict[str, Any]
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
    purpose: Road10KPurposeResponse
    event_context: dict[str, Any]
    history_cutoff_completed_days: int
    template_ids: list[str]
    result: Road10KOutcomeResponse
    proposal: dict[str, Any] | None = None
    replayed: bool = False
    reassessment_dates: list[str] = Field(default_factory=list)


class Road10KBaselineMutationResponse(BaseModel):
    """Append-only confirmation response for direct 10K baseline review."""

    replayed: bool
    baseline: dict[str, Any]
    confirmation: dict[str, Any] | None = None


def _constraints(body: Road10KConstraintsRequest) -> Road10KPlanGenerationConstraints:
    return Road10KPlanGenerationConstraints(
        adult_confirmed=body.adult_confirmed,
        current_symptom_stop=body.current_symptom_stop,
        available_weekdays=tuple(int(item) for item in body.available_weekdays),
        weekly_time_limit_min=body.weekly_time_limit_min,
        maximum_session_duration_min=body.maximum_session_duration_min,
        unavailable_dates=tuple(body.unavailable_dates),
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
    if isinstance(error, Road10KGenerationError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    if isinstance(error, AdaptivePlanError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    if isinstance(error, PlanPurposeError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    raise error


def _raise_baseline(error: Exception) -> None:
    if isinstance(error, PlanPurposeError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    if isinstance(error, Road10KBaselineConflict):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ROAD_10K_BASELINE_IDEMPOTENCY_CONFLICT",
                "message": "This Idempotency-Key was already used for a different road 10K baseline request.",
            },
        )
    if isinstance(error, Road10KBaselineNotFound):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ROAD_10K_BASELINE_NOT_FOUND",
                "message": "The requested 10K baseline activity was not found for this athlete.",
            },
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
        )
    if isinstance(error, Road10KBaselineInvalid):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ROAD_10K_BASELINE_INVALID_REQUEST",
                "message": str(error),
            },
        )
    raise error


@router.post(
    "/plan/road-10k/readiness",
    response_model=Road10KReadinessResponse,
    response_model_exclude_none=True,
)
def post_road_10k_readiness(
    body: Road10KReadinessRequest,
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evaluate the reviewed road 10K policy without persisting a proposal."""
    try:
        return build_road_10k_readiness(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise_generation(exc)
        raise


@router.post(
    "/plan/road-10k/alternatives",
    response_model=Road10KAlternativesResponse,
    response_model_exclude_none=True,
)
def post_road_10k_alternatives(
    body: Road10KReadinessRequest,
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return only policy-bounded alternatives for the current 10K state."""
    try:
        return build_road_10k_alternatives(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise_generation(exc)
        raise


@router.post(
    "/plan/road-10k/generate",
    response_model=Road10KProposalResponse | Road10KReadinessResponse,
    response_model_exclude_none=True,
)
def post_road_10k_generate(
    body: Road10KGenerateRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
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
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.post(
    "/plan/road-10k/proposals/{proposal_id}/regenerate",
    response_model=Road10KProposalResponse | Road10KReadinessResponse,
    response_model_exclude_none=True,
)
def post_road_10k_regenerate(
    proposal_id: UUID,
    body: Road10KRegenerateRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
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
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.post(
    "/plan/road-10k/baseline/history/confirm",
    response_model=Road10KBaselineMutationResponse,
    status_code=201,
)
def post_road_10k_history_confirmation(
    body: Road10KHistoryConfirmationRequest,
    idempotency_key: IdempotencyKey,
    user_id: str = Depends(require_write_access),
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
        return JSONResponse(content=result, status_code=200)
    return result
