"""Goal endpoint and history-first 5 km baseline mutations."""
from __future__ import annotations

from datetime import date
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.auth import get_current_user_id, get_data_user_id, require_write_access
from api.dashboard_cache import cached_or_compute
from api.etag import CACHE_CONTROL, ETagGuard, etag_guard_for_endpoint
from api.goal_baseline import (
    GoalBaselineConflict,
    GoalBaselineForbidden,
    GoalBaselineInvalid,
    GoalBaselineNotFound,
    build_goal_baseline_evaluation,
    build_goal_baseline_view,
    confirm_history_candidate,
    mutate_optional_test,
)
from api.packs import RequestContext, get_race_pack
from api.plan_generation_capabilities import (
    PlanPurposeError,
)
from api.views import require_admin
from db.session import get_db

router = APIRouter()
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]


class HistoryConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str
    response: Literal["race", "intentional_all_out", "not_all_out", "deleted"]
    measured_5k: bool
    elapsed_timing_confirmed: bool
    supersedes_confirmation_id: str | None = None
    purpose: "GoalBaselinePurposeRequest | None" = None


class GoalBaselineTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["offer", "schedule", "decline", "stop", "complete"]
    scheduled_date: date | None = None
    activity_id: str | None = None
    measured_5k: bool | None = None
    elapsed_timing_confirmed: bool | None = None
    protocol_followed: bool | None = None
    reason_code: str | None = None
    purpose: "GoalBaselinePurposeRequest | None" = None


class GoalBaselinePurposeRequest(BaseModel):
    """Purpose selection used to scope baseline evidence mutations."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    source: Literal["current_goal", "capability", "unlinked"]
    expected_goal_id: str | None = None
    expected_goal_revision: str | None = None


class GoalBaselineMutationResponse(BaseModel):
    replayed: bool
    baseline: dict
    confirmation: dict | None = None
    test: dict | None = None


class GoalBaselineEvaluationResponse(BaseModel):
    schema_version: int
    policy_version: str
    generated_at: str
    operational_counts: dict
    checks: dict
    falsification: dict
    review_gate: dict


def _build_goal_payload(user_id: str, db: Session) -> dict:
    """Compute the /api/goal response from packs and baseline state."""
    ctx = RequestContext(user_id=user_id, db=db)
    race = get_race_pack(ctx)
    baseline = build_goal_baseline_view(db, user_id=user_id)
    return {
        "race_countdown": race["race_countdown"],
        "cp_trend": race["cp_trend"],
        "cp_trend_data": race["cp_trend_data"],
        "latest_cp": race["latest_cp"],
        "training_base": ctx.config.training_base,
        "display": ctx.display,
        "data_meta": ctx.data_meta,
        "science_notes": ctx.science_notes,
        **baseline,
    }


@router.get("/goal")
def get_goal(
    guard: ETagGuard = Depends(etag_guard_for_endpoint("goal")),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    if guard.is_match:
        return guard.not_modified()
    body = cached_or_compute(
        db,
        user_id,
        "goal",
        compute=lambda: _build_goal_payload(user_id, db),
    )
    return Response(
        content=body,
        media_type="application/json",
        headers={"ETag": guard.etag, "Cache-Control": CACHE_CONTROL},
    )


def _mutation_error(code: str, message: str, **details: object) -> dict:
    return {"code": code, "message": message, **details}


def _translate_goal_baseline_error(exc: Exception) -> None:
    if isinstance(exc, PlanPurposeError):
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        )
    if isinstance(exc, GoalBaselineConflict):
        raise HTTPException(
            status_code=409,
            detail=_mutation_error(
                "GOAL_BASELINE_IDEMPOTENCY_CONFLICT",
                "This Idempotency-Key was already used for a different baseline request.",
            ),
        )
    if isinstance(exc, GoalBaselineNotFound):
        raise HTTPException(
            status_code=404,
            detail=_mutation_error(
                "GOAL_BASELINE_NOT_FOUND",
                "The requested baseline activity or record was not found for this athlete.",
            ),
        )
    if isinstance(exc, GoalBaselineForbidden):
        message = {
            "BASELINE_NOT_REQUIRED": "This goal is outside the current 5K baseline pilot.",
            "CURRENT_HISTORY_SUPPRESSES_TEST": "Qualified current history already exists, so the optional pilot test is unavailable.",
            "PAST_SCHEDULE_FORBIDDEN": "Pilot tests can only be scheduled on or after today in the athlete calendar.",
            "TEST_ALREADY_SCHEDULED": "A pilot test is already scheduled. Stop or complete it before scheduling another one.",
            "TEST_NOT_OFFERED": "Record a pilot test only after offering or scheduling it explicitly.",
            "TEST_NOT_SCHEDULED": "Complete a pilot test only after it has been explicitly scheduled.",
            "TEST_ACTIVITY_BEFORE_SCHEDULE": "Use a synced activity from the offered or scheduled pilot-test window.",
            "TEST_ACTIVITY_OUTSIDE_SCHEDULED_DAY": "Use the synced activity from the exact scheduled pilot-test day, or reschedule first.",
            "ACTIVITY_OUTSIDE_5K_REVIEW_WINDOW": "Only complete near-5K full activities can be reviewed in this pilot flow.",
        }.get(str(exc), "The requested baseline action is unavailable in the current state.")
        raise HTTPException(
            status_code=409,
            detail=_mutation_error(
                "GOAL_BASELINE_MUTATION_FORBIDDEN",
                message,
            ),
        )
    if isinstance(exc, GoalBaselineInvalid):
        raise HTTPException(
            status_code=400,
            detail=_mutation_error(
                "GOAL_BASELINE_INVALID_REQUEST",
                str(exc),
            ),
        )
    raise exc


def _purpose_selection(
    purpose: GoalBaselinePurposeRequest | None,
) -> dict | None:
    return purpose.model_dump() if purpose is not None else None


@router.post(
    "/goal/baseline/history/confirm",
    response_model=GoalBaselineMutationResponse,
    status_code=201,
)
def post_goal_baseline_history_confirmation(
    body: HistoryConfirmationRequest,
    idempotency_key: IdempotencyKey,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = confirm_history_candidate(
            db,
            user_id=user_id,
            activity_id=body.activity_id,
            response=body.response,
            measured_5k=body.measured_5k,
            elapsed_timing_confirmed=body.elapsed_timing_confirmed,
            idempotency_key=idempotency_key,
            supersedes_confirmation_id=body.supersedes_confirmation_id,
            purpose_selection=_purpose_selection(body.purpose),
        )
    except Exception as exc:
        _translate_goal_baseline_error(exc)
        raise
    if result["replayed"]:
        return Response(
            content=json.dumps(result),
            media_type="application/json",
            status_code=200,
        )
    return result


@router.post(
    "/goal/baseline/test",
    response_model=GoalBaselineMutationResponse,
    status_code=201,
)
def post_goal_baseline_test_mutation(
    body: GoalBaselineTestRequest,
    idempotency_key: IdempotencyKey,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = mutate_optional_test(
            db,
            user_id=user_id,
            action=body.action,
            idempotency_key=idempotency_key,
            scheduled_date=body.scheduled_date,
            activity_id=body.activity_id,
            measured_5k=body.measured_5k,
            elapsed_timing_confirmed=body.elapsed_timing_confirmed,
            protocol_followed=body.protocol_followed,
            reason_code=body.reason_code,
            purpose_selection=_purpose_selection(body.purpose),
        )
    except Exception as exc:
        _translate_goal_baseline_error(exc)
        raise
    if result["replayed"]:
        return Response(
            content=json.dumps(result),
            media_type="application/json",
            status_code=200,
        )
    return result


@router.get(
    "/goal/baseline/evaluation",
    response_model=GoalBaselineEvaluationResponse,
)
def get_goal_baseline_evaluation(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    require_admin(user_id, db)
    return build_goal_baseline_evaluation(db)
