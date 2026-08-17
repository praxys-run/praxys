"""Typed authenticated API for deterministic outdoor-road 5K proposals."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from analysis.outdoor_5k_plan_generation import PlanGenerationConstraints
from api.adaptive_plan_service import AdaptivePlanError
from api.auth import get_data_user_id, require_write_access
from api.outdoor_5k_plan_generation import (
    Outdoor5KGenerationError,
    build_outdoor_5k_alternatives,
    build_outdoor_5k_readiness,
    generate_outdoor_5k_proposal,
    regenerate_outdoor_5k_proposal,
)
from api.plan_generation_capabilities import PlanPurposeError
from db.session import get_db


router = APIRouter()
Weekday = Literal[0, 1, 2, 3, 4, 5, 6]
Outdoor5KResultCode = Literal[
    "ready",
    "unsupported_goal_or_population",
    "safety_stop",
    "insufficient_or_stale_baseline",
    "insufficient_goal_horizon",
    "goal_gap_not_actionable_v1",
    "insufficient_recent_history",
    "clarification_required",
    "unsupported_frequency",
    "contradictory_constraints",
    "unsupported_power_target",
    "no_schedule_within_envelope",
]


class PlanGenerationPurposeRequest(BaseModel):
    """Exact current-Goal, capability-owned, or unlinked purpose selection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    capability_id: str = Field(min_length=1, max_length=80)
    source: Literal["current_goal", "capability", "unlinked"]
    expected_goal_id: str | None = Field(
        default=None,
        min_length=36,
        max_length=36,
    )
    expected_goal_revision: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def validate_source_fence(self) -> "PlanGenerationPurposeRequest":
        if self.source == "current_goal":
            if (
                self.expected_goal_id is None
                or self.expected_goal_revision is None
            ):
                raise ValueError(
                    "current_goal requires expected_goal_id and "
                    "expected_goal_revision"
                )
        elif (
            self.expected_goal_id is not None
            or self.expected_goal_revision is not None
        ):
            raise ValueError(
                "only current_goal may include expected Goal provenance"
            )
        return self


class Outdoor5KConstraintsRequest(BaseModel):
    """Structured, purpose-bounded athlete statements for the deterministic path."""

    model_config = ConfigDict(extra="forbid", strict=True)

    purpose: PlanGenerationPurposeRequest | None = None
    age_18_or_older: bool
    self_coached_recreational_road_runner: bool
    can_complete_5k: bool
    safety_stop: bool = False
    outdoor_road_goal_confirmed: bool
    available_weekdays: list[Weekday] = Field(min_length=1, max_length=7)
    maximum_session_duration_min: int = Field(ge=1)
    unavailable_dates: list[date] = Field(default_factory=list, max_length=28)
    preferred_longest_run_weekday: Weekday | None = None


class Outdoor5KReadinessRequest(Outdoor5KConstraintsRequest):
    """Read-only readiness request."""


class Outdoor5KGenerateRequest(Outdoor5KConstraintsRequest):
    """Exact source-fenced, idempotent proposal request."""

    expected_source_revision: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    idempotency_key: str = Field(min_length=8, max_length=128)


class Outdoor5KRegenerateRequest(Outdoor5KGenerateRequest):
    """Exact proposal-version request for one bounded successor."""

    expected_proposal_version: int = Field(ge=1)


class Outdoor5KOutcomeResponse(BaseModel):
    """Typed accepted result-code envelope shared by all plan-start responses."""

    model_config = ConfigDict(extra="forbid")

    policy_version: str
    generator_version: str
    science_decision_id: str
    code: Outdoor5KResultCode
    deterministic_input_hash: str
    history_statistics: dict[str, Any]
    failed_rule_id: str | None
    observed_or_stated_reason: str | None
    uncertainty_or_missing_field: str | None
    alternatives: list[str]


class Outdoor5KPurposeResponse(BaseModel):
    """Resolved purpose included in readiness and proposal responses."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    source: Literal["current_goal", "capability", "unlinked"]
    expected_goal_id: str | None
    expected_goal_revision: str | None
    goal: dict[str, Any]


class Outdoor5KReadinessResponse(BaseModel):
    """Typed no-write readiness response."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    policy_version: str
    generator_version: str
    science_decision_id: str
    source_revision: str
    purpose: Outdoor5KPurposeResponse
    baseline: dict[str, Any]
    athlete_today: str
    block_start: str
    result: Outdoor5KOutcomeResponse


class Outdoor5KAlternativesResponse(Outdoor5KReadinessResponse):
    """Readiness plus the policy-bounded next steps."""

    alternatives: list[str]


class Outdoor5KProposalResponse(BaseModel):
    """Typed proposal response; the proposal remains non-canonical."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    policy_version: str
    generator_version: str
    science_decision_id: str
    source_revision: str
    purpose: Outdoor5KPurposeResponse
    result: Outdoor5KOutcomeResponse
    proposal: dict[str, Any] | None = None
    replayed: bool = False
    reassessment_dates: list[str] = Field(default_factory=list)


def _constraints(body: Outdoor5KConstraintsRequest) -> PlanGenerationConstraints:
    return PlanGenerationConstraints(
        age_18_or_older=body.age_18_or_older,
        self_coached_recreational_road_runner=(
            body.self_coached_recreational_road_runner
        ),
        can_complete_5k=body.can_complete_5k,
        safety_stop=body.safety_stop,
        available_weekdays=tuple(int(item) for item in body.available_weekdays),
        maximum_session_duration_min=body.maximum_session_duration_min,
        unavailable_dates=tuple(body.unavailable_dates),
        preferred_longest_run_weekday=(
            int(body.preferred_longest_run_weekday)
            if body.preferred_longest_run_weekday is not None
            else None
        ),
    )


def _purpose(
    body: Outdoor5KConstraintsRequest,
) -> dict[str, Any] | None:
    if body.purpose is None:
        return None
    return body.purpose.model_dump(mode="json")


def _raise(error: Exception) -> None:
    if isinstance(error, Outdoor5KGenerationError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    if isinstance(error, AdaptivePlanError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    if isinstance(error, PlanPurposeError):
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    raise error


@router.post(
    "/plan/outdoor-5k/readiness",
    response_model=Outdoor5KReadinessResponse,
)
def post_outdoor_5k_readiness(
    body: Outdoor5KReadinessRequest,
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Evaluate the accepted policy without persisting or delivering a plan."""
    try:
        return build_outdoor_5k_readiness(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            outdoor_road_goal_confirmed=body.outdoor_road_goal_confirmed,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise(exc)
        raise


@router.post(
    "/plan/outdoor-5k/alternatives",
    response_model=Outdoor5KAlternativesResponse,
)
def post_outdoor_5k_alternatives(
    body: Outdoor5KReadinessRequest,
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return only policy-bounded alternatives for the supplied current state."""
    try:
        return build_outdoor_5k_alternatives(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            outdoor_road_goal_confirmed=body.outdoor_road_goal_confirmed,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise(exc)
        raise


@router.post(
    "/plan/outdoor-5k/generate",
    response_model=Outdoor5KProposalResponse | Outdoor5KReadinessResponse,
)
def post_outdoor_5k_generate(
    body: Outdoor5KGenerateRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Create a non-canonical proposal after exact readiness-source validation."""
    try:
        result, replayed = generate_outdoor_5k_proposal(
            db,
            user_id=user_id,
            constraints=_constraints(body),
            outdoor_road_goal_confirmed=body.outdoor_road_goal_confirmed,
            expected_source_revision=body.expected_source_revision,
            idempotency_key=body.idempotency_key,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise(exc)
        raise
    if result["result"]["code"] != "ready" or replayed:
        return result
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.post(
    "/plan/outdoor-5k/proposals/{proposal_id}/regenerate",
    response_model=Outdoor5KProposalResponse | Outdoor5KReadinessResponse,
)
def post_outdoor_5k_regenerate(
    proposal_id: UUID,
    body: Outdoor5KRegenerateRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Create an exact-version successor only when source inputs have changed."""
    try:
        result, replayed = regenerate_outdoor_5k_proposal(
            db,
            user_id=user_id,
            proposal_id=str(proposal_id),
            expected_proposal_version=body.expected_proposal_version,
            constraints=_constraints(body),
            outdoor_road_goal_confirmed=body.outdoor_road_goal_confirmed,
            expected_source_revision=body.expected_source_revision,
            idempotency_key=body.idempotency_key,
            purpose_selection=_purpose(body),
        )
    except Exception as exc:
        _raise(exc)
        raise
    if result["result"]["code"] != "ready" or replayed:
        return result
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)
