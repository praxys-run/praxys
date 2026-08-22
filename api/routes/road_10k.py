"""Private Road 10K control routes.

Stage access and opt-in are mechanically hidden in this revision.  The only
remaining routes are authenticated first-party withdrawal and data export
rights; they never authorize a Road capability.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.auth import get_authenticated_identity
from api.road_10k_control import (
    Road10KControlConflict,
    Road10KControlDenied,
    Road10KControlUnavailable,
    Road10KDeletionFailed,
    coerce_road_10k_control_error,
    export_owner_records,
    withdraw_owner,
)
from db.session import get_db

_PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Pragma": "no-cache",
    "Vary": "Authorization",
}


def _require_surface() -> None:
    """Statically deny disabled Road stage surfaces before all request I/O."""
    raise HTTPException(
        status_code=404,
        detail="Not found",
        headers=_PRIVATE_HEADERS,
    )


router = APIRouter(
    prefix="/road-10k",
    tags=["road-10k"],
)


class Road10KActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["withdrawn"]
    rollout_status: Literal["withdrawn"]
    plan_status: Literal["unchanged"]


class Road10KEvaluationExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    stage_id: str
    result_code: Literal[
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
    payload: dict[str, object]
    created_at: str
    expires_at: str


class Road10KExportReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal[
        "invited_only",
        "enrolled_unexposed",
        "exposed",
        "withdrawn",
        "deleted",
    ]
    invitation_issued_at: str
    enrolled_at: str | None
    first_exposed_at: str | None


class Road10KExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: str
    receipt: Road10KExportReceipt | None
    evaluations: list[Road10KEvaluationExport]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization"


def _owner(request: Request, db: Session) -> str:
    identity = get_authenticated_identity(request, db)
    if (
        identity.credential_kind != "first_party_jwt"
        or identity.is_demo
        or not identity.user.is_active
    ):
        raise HTTPException(403, "First-party authentication required")
    return identity.user_id


def _control_error(exc: Exception) -> HTTPException:
    error = coerce_road_10k_control_error(exc)
    headers = {
        "Cache-Control": "private, no-store",
        "Pragma": "no-cache",
        "Vary": "Authorization",
    }
    if isinstance(error, Road10KControlUnavailable):
        return HTTPException(404, "Not found", headers=headers)
    if isinstance(error, Road10KControlDenied):
        if str(error) == "participation_required":
            return HTTPException(404, "Not found", headers=headers)
        return HTTPException(409, {"code": str(error)}, headers=headers)
    if isinstance(error, Road10KControlConflict):
        return HTTPException(409, {"code": str(error)}, headers=headers)
    if isinstance(error, Road10KDeletionFailed):
        return HTTPException(503, {"code": str(error)}, headers=headers)
    return HTTPException(500, {"code": "ROAD_10K_CONTROL_FAILED"}, headers=headers)


@router.get("/access", dependencies=[Depends(_require_surface)])
def get_access() -> None:
    """This Road capability is mechanically hidden in this revision."""
    _require_surface()


@router.post("/opt-in", dependencies=[Depends(_require_surface)])
def opt_in() -> None:
    """This Road capability is mechanically hidden in this revision."""
    _require_surface()


@router.post("/withdraw", response_model=Road10KActionResponse)
def withdraw(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Withdraw the current owner without changing cumulative accounting."""
    user_id = _owner(request, db)
    try:
        withdraw_owner(db, user_id=user_id)
    except Exception as exc:
        raise _control_error(exc) from exc
    _private(response)
    return {
        "outcome": "withdrawn",
        "rollout_status": "withdrawn",
        "plan_status": "unchanged",
    }


@router.get("/export", response_model=Road10KExportResponse)
def export(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Owner-scoped export; it never changes rollout or plan status."""
    user_id = _owner(request, db)
    try:
        result = export_owner_records(db, user_id=user_id)
    except Exception as exc:
        raise _control_error(exc) from exc
    _private(response)
    return result
