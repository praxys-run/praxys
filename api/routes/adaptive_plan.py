"""Authenticated adaptive plan proposal endpoints."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from analysis.config import effective_athlete_date, load_config_from_db
from api.adaptive_plan_service import (
    AdaptivePlanError,
    ProposalInput,
    adopt_proposal,
    create_draft_proposal,
    create_successor_proposal,
    read_current_proposal,
    reject_proposal,
)
from api.auth import get_data_user_id, require_write_access
from api.routes.ai import _trigger_managed_delivery
from db.session import get_db


router = APIRouter()


class ProposalGoalInput(BaseModel):
    """Versioned goal target and planning horizon for a proposal."""

    model_config = ConfigDict(extra="forbid")

    goal_kind: str = Field(min_length=1, max_length=40)
    target: dict[str, Any] = Field(default_factory=dict)
    horizon_start: date
    horizon_end: date


class ProposalWorkoutInput(BaseModel):
    """Supported canonical workout fields accepted in a proposal snapshot."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    canonical_id: UUID | None = None
    date: date
    workout_type: str = Field(min_length=1, max_length=50)
    planned_duration_min: float | None = Field(default=None, ge=0, le=1440)
    planned_distance_km: float | None = Field(default=None, ge=0, le=1000)
    target_power_min: float | None = Field(default=None, ge=0, le=5000)
    target_power_max: float | None = Field(default=None, ge=0, le=5000)
    target_hr_min: float | None = Field(default=None, ge=0, le=300)
    target_hr_max: float | None = Field(default=None, ge=0, le=300)
    target_pace_min: str | None = Field(default=None, max_length=20)
    target_pace_max: str | None = Field(default=None, max_length=20)
    workout_description: str | None = Field(default=None, max_length=4000)


class ProposalMutation(BaseModel):
    """Create or edit a non-canonical proposal from structured workouts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goal: ProposalGoalInput
    workouts: list[ProposalWorkoutInput] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    origin: str = Field(default="api.plan.proposals", min_length=1, max_length=80)
    policy_version: str | None = Field(default=None, max_length=80)
    model_version: str | None = Field(default=None, max_length=80)
    science_version: str | None = Field(default=None, max_length=80)
    assumptions: list[Any] = Field(default_factory=list)
    unknowns: list[Any] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    alternatives: list[Any] = Field(default_factory=list)
    expires_at: datetime | None = None


class ProposalEditRequest(ProposalMutation):
    """Exact-version edit request that creates a successor proposal."""

    expected_version: int = Field(ge=1)


class ProposalDecisionRequest(BaseModel):
    """Idempotent exact-version proposal decision."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


class ProposalAdoptRequest(BaseModel):
    """Idempotent exact-version adoption into the canonical plan lane."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_proposal_version: int = Field(ge=1)
    expected_plan_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)


def _current_athlete_date(db: Session, user_id: str) -> date:
    return effective_athlete_date(load_config_from_db(user_id, db))


def _proposal_input(payload: ProposalMutation, *, user_id: str) -> ProposalInput:
    return ProposalInput(
        goal=payload.goal.model_dump(mode="json"),
        workouts=[workout.model_dump(mode="json", exclude_none=True) for workout in payload.workouts],
        origin=payload.origin,
        actor_type="user",
        actor_id=user_id,
        idempotency_key=payload.idempotency_key,
        policy_version=payload.policy_version,
        model_version=payload.model_version,
        science_version=payload.science_version,
        assumptions=payload.assumptions,
        unknowns=payload.unknowns,
        warnings=payload.warnings,
        alternatives=payload.alternatives,
        expires_at=payload.expires_at,
    )


def _raise(error: AdaptivePlanError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail)


@router.post("/plan/proposals", status_code=status.HTTP_201_CREATED)
def create_plan_proposal(
    payload: ProposalMutation,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Persist a structured, non-canonical draft plan proposal."""
    try:
        return create_draft_proposal(
            db,
            user_id=user_id,
            payload=_proposal_input(payload, user_id=user_id),
            current_date=_current_athlete_date(db, user_id),
        )
    except AdaptivePlanError as exc:
        _raise(exc)


@router.get("/plan/proposals/current")
def get_current_plan_proposal(
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Read the authenticated athlete's active proposal and exact version."""
    proposal = read_current_proposal(db, user_id=user_id)
    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PLAN_PROPOSAL_NOT_FOUND",
                "message": "No active plan proposal exists.",
            },
        )
    return proposal


@router.post("/plan/proposals/{proposal_id}/edits", status_code=status.HTTP_201_CREATED)
def edit_plan_proposal(
    proposal_id: UUID,
    payload: ProposalEditRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a successor edit without mutating the prior proposal payload."""
    try:
        return create_successor_proposal(
            db,
            user_id=user_id,
            proposal_id=str(proposal_id),
            expected_version=payload.expected_version,
            payload=_proposal_input(payload, user_id=user_id),
            current_date=_current_athlete_date(db, user_id),
        )
    except AdaptivePlanError as exc:
        _raise(exc)


@router.post("/plan/proposals/{proposal_id}/reject")
def reject_plan_proposal(
    proposal_id: UUID,
    payload: ProposalDecisionRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reject an exact draft proposal without canonical writes."""
    try:
        return reject_proposal(
            db,
            user_id=user_id,
            proposal_id=str(proposal_id),
            expected_version=payload.expected_version,
            idempotency_key=payload.idempotency_key,
        )
    except AdaptivePlanError as exc:
        _raise(exc)


@router.post("/plan/proposals/{proposal_id}/adopt")
def adopt_plan_proposal(
    proposal_id: UUID,
    payload: ProposalAdoptRequest,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Atomically adopt an exact proposal into canonical Praxys workouts."""
    try:
        result = adopt_proposal(
            db,
            user_id=user_id,
            proposal_id=str(proposal_id),
            expected_proposal_version=payload.expected_proposal_version,
            expected_plan_version=payload.expected_plan_version,
            idempotency_key=payload.idempotency_key,
            current_date=_current_athlete_date(db, user_id),
        )
    except AdaptivePlanError as exc:
        _raise(exc)
    if result["status"] == "adopted":
        _trigger_managed_delivery(
            user_id,
            trigger="plan_proposal_adopt",
        )
    return result
