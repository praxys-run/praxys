"""Private Road 10K control routes.

The route is intentionally not linked from public navigation.  Without an
independently issued stage authority every response is the accepted hidden
404, including direct-link attempts.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy.orm import Session

from api.auth import get_authenticated_identity
from api.road_10k_control import (
    Road10KControlConflict,
    Road10KControlDenied,
    Road10KControlUnavailable,
    Road10KDeletionFailed,
    enroll_owner,
    export_owner_records,
    withdraw_owner,
)
from api.road_10k_stage_authority import load_stage_authority
from db.models import Road10KOwnerStageReceipt
from db.session import get_db

router = APIRouter(prefix="/road-10k", tags=["road-10k"])
_password_helper = PasswordHelper()


class Road10KOptInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    password: SecretStr | None = Field(default=None, min_length=1, max_length=512)
    notice_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    client: Literal["web", "miniapp"]

    @model_validator(mode="after")
    def require_client_reauthentication(self) -> "Road10KOptInRequest":
        if self.client == "web" and self.password is None:
            raise ValueError("web reauthentication requires password")
        return self


class Road10KStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollout_status: str
    plan_status: str
    invitation_issued_at: str | None = None
    enrolled_at: str | None = None
    first_exposed_at: str | None = None


class Road10KAccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rollout_status: Literal["invited", "enrolled", "withdrawn", "removed"]
    plan_status: Literal["none"]
    stage_id: str
    notice_digest: str
    screenshot_available: Literal[False]


class Road10KActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["enrolled", "withdrawn"]
    rollout_status: Literal["enrolled", "withdrawn"]
    plan_status: Literal["none", "unchanged"]
    receipt_id: str


class Road10KEvaluationExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    stage_id: str
    result_code: str
    payload: dict[str, Any]
    created_at: str
    expires_at: str


class Road10KExportReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
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


def _hidden(response: Response) -> JSONResponse:
    headers = {
        "Cache-Control": "private, no-store",
        "Pragma": "no-cache",
        "Vary": "Authorization",
    }
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"},
        headers=headers,
    )


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
    headers = {
        "Cache-Control": "private, no-store",
        "Pragma": "no-cache",
        "Vary": "Authorization",
    }
    if isinstance(exc, Road10KControlUnavailable):
        return HTTPException(404, "Not found", headers=headers)
    if isinstance(exc, Road10KControlDenied):
        return HTTPException(409, {"code": str(exc)}, headers=headers)
    if isinstance(exc, Road10KControlConflict):
        return HTTPException(409, {"code": str(exc)}, headers=headers)
    if isinstance(exc, Road10KDeletionFailed):
        return HTTPException(503, {"code": str(exc)}, headers=headers)
    return HTTPException(500, {"code": "ROAD_10K_CONTROL_FAILED"}, headers=headers)


@router.get("/access", response_model=Road10KAccessResponse)
def get_access(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Return the owner-scoped catalog only after authority and invitation."""
    user_id = _owner(request, db)
    authority = load_stage_authority()
    if authority is None or not authority.is_usable:
        return _hidden(response)
    receipt = (
        db.query(Road10KOwnerStageReceipt)
        .filter(
            Road10KOwnerStageReceipt.user_id == user_id,
            Road10KOwnerStageReceipt.stage_id == authority.stage_id,
        )
        .first()
    )
    if (
        receipt is None
        or receipt.authority_digest != authority.authority_digest
        or receipt.schema_version != 2
        or receipt.policy_version != "road-10k-plan-generation-policy-v2"
        or receipt.notice_digest != authority.notice_digest
    ):
        return _hidden(response)
    _private(response)
    rollout_status = {
        "invited_only": "invited",
        "enrolled_unexposed": "enrolled",
        "exposed": "enrolled",
        "withdrawn": "withdrawn",
        "deleted": "removed",
    }.get(receipt.state)
    if rollout_status is None:
        return _hidden(response)
    return {
        "rollout_status": rollout_status,
        "plan_status": "none",
        "stage_id": authority.stage_id,
        "notice_digest": authority.notice_digest,
        "screenshot_available": False,
    }


@router.post("/opt-in", response_model=Road10KActionResponse)
def opt_in(
    body: Road10KOptInRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Reauthenticate and enroll the current invited owner."""
    user_id = _owner(request, db)
    authority = load_stage_authority()
    if authority is None or not authority.is_usable:
        return _hidden(response)
    # Fetching the native user is deliberately separate from the control
    # receipt; the client can never select an owner through the request body.
    from db.models import User

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(401, "User not found")
    if body.client == "web":
        valid, updated_hash = _password_helper.verify_and_update(
            body.password.get_secret_value() if body.password else "",
            user.hashed_password,
        )
        if not valid:
            raise HTTPException(401, "Reauthentication required")
        if updated_hash:
            user.hashed_password = updated_hash
    try:
        receipt = enroll_owner(
            db,
            user_id=user_id,
            notice_digest=body.notice_digest,
        )
    except Exception as exc:
        raise _control_error(exc) from exc
    _private(response)
    return {
        "outcome": "enrolled",
        "rollout_status": "enrolled",
        "plan_status": "none",
        "receipt_id": receipt.id,
    }


@router.post("/withdraw", response_model=Road10KActionResponse)
def withdraw(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Withdraw the current owner without changing cumulative accounting."""
    user_id = _owner(request, db)
    try:
        receipt = withdraw_owner(db, user_id=user_id)
    except Exception as exc:
        raise _control_error(exc) from exc
    _private(response)
    return {
        "outcome": "withdrawn",
        "rollout_status": "withdrawn",
        "plan_status": "unchanged",
        "receipt_id": receipt.id,
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
