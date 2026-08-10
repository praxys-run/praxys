"""Opaque browser handoff and session endpoints for MCP clients."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.mcp_access import (
    MCP_AUDIENCE,
    McpAccessConflict,
    McpAccessDenied,
    McpAccessExpired,
    McpAccessInvalid,
    McpAccessNotFound,
    McpAccessPending,
    access_names,
    create_session_handoff,
    decide_handoff,
    exchange_handoff,
    inspect_handoff,
    revoke_access_token,
)
from api.personal_context_auth import ContextActor, get_context_actor
from api.views import utc_isoformat
from db.models import User
from db.session import get_db

router = APIRouter(prefix="/auth/mcp", tags=["auth", "mcp"])
_NO_STORE = "private, no-store"


class McpSessionHandoffRequest(BaseModel):
    """Fixed audience requested by the official Praxys MCP client."""

    model_config = ConfigDict(extra="forbid")

    audience: Literal["praxys-coach-plugin"]


class McpHandoffDecisionRequest(BaseModel):
    """Trusted first-party decision for one opaque handoff."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "denied"]


class McpHandoffExchangeRequest(BaseModel):
    """Client-held proof used to exchange one approved handoff."""

    model_config = ConfigDict(extra="forbid")

    state: str = Field(min_length=20, max_length=128)
    exchange_secret: str = Field(min_length=20, max_length=128)


class McpHandoffCreatedResponse(BaseModel):
    """Opaque state for the browser plus separate client exchange proof."""

    model_config = ConfigDict(extra="forbid")

    state: str
    exchange_secret: str
    authorize_path: str
    expires_at: str


class McpHandoffViewResponse(BaseModel):
    """Non-sensitive authority shown on the first-party approval page."""

    model_config = ConfigDict(extra="forbid")

    request_type: Literal["session", "context"]
    audience: Literal["praxys-coach-plugin"]
    status: Literal["pending", "approved", "denied", "exchanged"]
    purpose: Literal[
        "plan_generation",
        "execution_interpretation",
        "plan_adjustment",
        "goal_review",
        "outcome_review",
    ] | None
    kind: Literal[
        "durable_preference",
        "temporary_constraint",
        "execution_explanation",
    ] | None
    access: list[Literal["read", "write"]]
    expires_at: str


class McpPendingExchangeResponse(BaseModel):
    """Pending exchange state without any credential material."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pending"]


class McpTokenExchangeResponse(BaseModel):
    """One-time opaque token exchange response."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["bearer"]
    expires_at: str
    audience: Literal["praxys-coach-plugin"]
    purpose: Literal[
        "plan_generation",
        "execution_interpretation",
        "plan_adjustment",
        "goal_review",
        "outcome_review",
    ] | None
    kind: Literal[
        "durable_preference",
        "temporary_constraint",
        "execution_explanation",
    ] | None
    access: list[Literal["read", "write"]]


class McpIdentityResponse(BaseModel):
    """Current MCP session owner and fixed client audience."""

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    is_superuser: bool
    actor_type: Literal["mcp"]
    audience: Literal["praxys-coach-plugin"]


class McpRevocationResponse(BaseModel):
    """Immediate server-side revocation result."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["revoked"]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = _NO_STORE


def _handoff_payload(created) -> dict[str, Any]:
    return {
        "state": created.state,
        "exchange_secret": created.exchange_secret,
        "authorize_path": f"/mcp/authorize?state={created.state}",
        "expires_at": utc_isoformat(created.handoff.expires_at),
    }


def _first_party(actor: ContextActor) -> None:
    if not actor.is_athlete or actor.credential_kind != "first_party_jwt":
        raise HTTPException(403, detail="MCP_FIRST_PARTY_APPROVAL_REQUIRED")


def _translate_handoff_error(db: Session, exc: Exception) -> None:
    db.rollback()
    if isinstance(exc, McpAccessNotFound):
        raise HTTPException(404, detail="MCP_HANDOFF_NOT_FOUND") from exc
    if isinstance(exc, McpAccessExpired):
        raise HTTPException(410, detail="MCP_HANDOFF_EXPIRED") from exc
    if isinstance(exc, McpAccessDenied):
        raise HTTPException(403, detail="MCP_HANDOFF_DENIED") from exc
    if isinstance(exc, McpAccessConflict):
        raise HTTPException(409, detail="MCP_HANDOFF_CONFLICT") from exc
    if isinstance(exc, McpAccessInvalid):
        raise HTTPException(422, detail="MCP_HANDOFF_INVALID") from exc
    raise exc


@router.post(
    "/handoffs",
    status_code=201,
    response_model=McpHandoffCreatedResponse,
)
def request_mcp_session_handoff(
    body: McpSessionHandoffRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a short-lived login state without embedding an account JWT."""
    _private(response)
    try:
        created = create_session_handoff(db, audience=body.audience)
        db.commit()
        return _handoff_payload(created)
    except (
        McpAccessInvalid,
        McpAccessNotFound,
        McpAccessExpired,
        McpAccessConflict,
    ) as exc:
        _translate_handoff_error(db, exc)
        raise


@router.get(
    "/handoffs/{state}",
    response_model=McpHandoffViewResponse,
)
def get_mcp_handoff(
    state: str,
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return non-sensitive approval details to a first-party surface."""
    _private(response)
    _first_party(actor)
    try:
        handoff = inspect_handoff(
            db,
            state=state,
            user_id=actor.user_id,
        )
    except (
        McpAccessNotFound,
        McpAccessExpired,
    ) as exc:
        _translate_handoff_error(db, exc)
        raise
    return {
        "request_type": handoff.request_type,
        "audience": handoff.audience,
        "status": handoff.status,
        "purpose": (
            list(handoff.requested_purposes or [None])[0]
            if handoff.requested_purposes
            else None
        ),
        "kind": (
            list(handoff.requested_kinds or [None])[0]
            if handoff.requested_kinds
            else None
        ),
        "access": access_names_from_scopes(handoff.requested_scopes or []),
        "expires_at": utc_isoformat(handoff.expires_at),
    }


def access_names_from_scopes(scopes: list[str]) -> list[str]:
    """Map stored server scopes to stable approval labels."""
    return [
        name
        for name, scope in (
            ("read", "plan:context:read"),
            ("write", "plan:context:write"),
        )
        if scope in set(scopes)
    ]


@router.post("/handoffs/{state}/decision", status_code=204)
def decide_mcp_handoff(
    state: str,
    body: McpHandoffDecisionRequest,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> Response:
    """Approve or deny one exact request from a trusted first-party JWT."""
    _first_party(actor)
    try:
        decide_handoff(
            db,
            state=state,
            user_id=actor.user_id,
            decision=body.decision,
        )
        db.commit()
    except (
        McpAccessInvalid,
        McpAccessNotFound,
        McpAccessExpired,
        McpAccessConflict,
    ) as exc:
        _translate_handoff_error(db, exc)
        raise
    return Response(status_code=204, headers={"Cache-Control": _NO_STORE})


@router.post(
    "/handoffs/exchange",
    response_model=McpTokenExchangeResponse | McpPendingExchangeResponse,
)
def exchange_mcp_handoff(
    body: McpHandoffExchangeRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Exchange an approved state exactly once; pending requests stay pending."""
    _private(response)
    try:
        exchanged = exchange_handoff(
            db,
            state=body.state,
            exchange_secret=body.exchange_secret,
        )
        db.commit()
    except McpAccessPending:
        db.rollback()
        response.status_code = 202
        return {"status": "pending"}
    except (
        McpAccessInvalid,
        McpAccessNotFound,
        McpAccessExpired,
        McpAccessDenied,
        McpAccessConflict,
    ) as exc:
        _translate_handoff_error(db, exc)
        raise
    token = exchanged.token
    return {
        "access_token": exchanged.access_token,
        "token_type": "bearer",
        "expires_at": utc_isoformat(token.expires_at),
        "audience": token.audience,
        "purpose": (
            list(token.purposes or [None])[0]
            if token.purposes
            else None
        ),
        "kind": (
            list(token.kinds or [None])[0]
            if token.kinds
            else None
        ),
        "access": access_names(token),
    }


@router.get("/me", response_model=McpIdentityResponse)
def get_mcp_identity(
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the current MCP session owner without exposing token metadata."""
    _private(response)
    if actor.actor_type != "mcp" or actor.credential_kind != "mcp_session":
        raise HTTPException(403, detail="MCP_SESSION_REQUIRED")
    user = db.get(User, actor.user_id)
    if user is None:
        raise HTTPException(401, detail="MCP_SESSION_INVALID")
    return {
        "id": user.id,
        "email": user.email,
        "is_superuser": bool(user.is_superuser),
        "actor_type": actor.actor_type,
        "audience": MCP_AUDIENCE,
    }


@router.post("/revoke", response_model=McpRevocationResponse)
def revoke_mcp_session(
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Literal["revoked"]]:
    """Revoke the exact MCP session used for this request."""
    _private(response)
    if (
        actor.actor_type != "mcp"
        or actor.credential_kind != "mcp_session"
        or actor.token_id is None
    ):
        raise HTTPException(403, detail="MCP_SESSION_REQUIRED")
    try:
        revoke_access_token(
            db,
            token_id=actor.token_id,
            user_id=actor.user_id,
        )
        db.commit()
    except (
        McpAccessNotFound,
        McpAccessExpired,
        McpAccessConflict,
    ) as exc:
        _translate_handoff_error(db, exc)
        raise
    return {"status": "revoked"}
