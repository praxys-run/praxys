"""Server-authoritative opaque access grants for Praxys MCP clients."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from api.personal_context import CONTEXT_KINDS, CONTEXT_PURPOSES
from db.models import McpAccessHandoff, McpAccessToken, User
from db.session import begin_serialized_write

MCP_AUDIENCE = "praxys-coach-plugin"
MCP_ACTOR_TYPE = "mcp"
MCP_SESSION_PREFIX = "praxys_mcp_"
MCP_CONTEXT_PREFIX = "praxys_ctx_"
MCP_HANDOFF_TTL = timedelta(minutes=10)
MCP_SESSION_TTL = timedelta(hours=24)
MCP_CONTEXT_TTL = timedelta(minutes=15)

CONTEXT_ACCESS_READ = "read"
CONTEXT_ACCESS_WRITE = "write"
CONTEXT_ACCESS = frozenset({
    CONTEXT_ACCESS_READ,
    CONTEXT_ACCESS_WRITE,
})
_ACCESS_TO_SCOPE = {
    CONTEXT_ACCESS_READ: "plan:context:read",
    CONTEXT_ACCESS_WRITE: "plan:context:write",
}
_PURPOSE_KINDS = {
    "plan_generation": frozenset({"temporary_constraint"}),
    "execution_interpretation": frozenset({"execution_explanation"}),
    "plan_adjustment": frozenset({
        "temporary_constraint",
        "execution_explanation",
    }),
    "goal_review": frozenset({"temporary_constraint"}),
    "outcome_review": frozenset({
        "temporary_constraint",
        "execution_explanation",
    }),
}


class McpAccessError(RuntimeError):
    """Base class for opaque MCP grant failures."""


class McpAccessInvalid(McpAccessError, ValueError):
    """Raised for an invalid request without echoing its values."""


class McpAccessNotFound(McpAccessError):
    """Raised when a handoff or token must not be enumerated."""


class McpAccessPending(McpAccessError):
    """Raised while a handoff still needs a first-party decision."""


class McpAccessDenied(McpAccessError):
    """Raised after the athlete denies a handoff."""


class McpAccessExpired(McpAccessError):
    """Raised when a handoff or token is outside its bounded lifetime."""


class McpAccessConflict(McpAccessError):
    """Raised for one-time exchange or write-grant replay."""


@dataclass(frozen=True)
class CreatedMcpHandoff:
    """Raw one-time handoff material returned only to its initiating client."""

    state: str
    exchange_secret: str
    handoff: McpAccessHandoff


@dataclass(frozen=True)
class ExchangedMcpToken:
    """A newly minted opaque bearer returned exactly once."""

    access_token: str
    token: McpAccessToken


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.utcnow()
    if current.tzinfo is not None:
        return current.astimezone(timezone.utc).replace(tzinfo=None)
    return current


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _opaque_secret() -> str:
    return secrets.token_urlsafe(32)


def _validate_audience(audience: str) -> str:
    if audience != MCP_AUDIENCE:
        raise McpAccessInvalid("MCP audience is invalid")
    return audience


def _validate_actor_id(actor_id: str) -> str:
    if not isinstance(actor_id, str) or not 1 <= len(actor_id) <= 120:
        raise McpAccessInvalid("MCP actor is invalid")
    return actor_id


def _validate_context_dimensions(
    *,
    purpose: str,
    kind: str,
    access: Iterable[str],
) -> tuple[list[str], list[str]]:
    if (
        purpose not in CONTEXT_PURPOSES
        or kind not in CONTEXT_KINDS
        or kind not in _PURPOSE_KINDS.get(purpose, frozenset())
    ):
        raise McpAccessInvalid("Context grant dimensions are invalid")
    requested = list(access)
    if (
        not requested
        or len(requested) != len(set(requested))
        or not set(requested).issubset(CONTEXT_ACCESS)
    ):
        raise McpAccessInvalid("Context grant access is invalid")
    ordered = [
        item
        for item in (CONTEXT_ACCESS_READ, CONTEXT_ACCESS_WRITE)
        if item in requested
    ]
    return ordered, [_ACCESS_TO_SCOPE[item] for item in ordered]


def _purge_expired_access(db: Session, *, now: datetime) -> None:
    """Bound ephemeral MCP storage when a new handoff is persisted."""
    db.query(McpAccessToken).filter(
        McpAccessToken.expires_at <= now,
    ).delete(synchronize_session=False)
    db.query(McpAccessHandoff).filter(
        McpAccessHandoff.expires_at <= now,
    ).delete(synchronize_session=False)


def create_session_handoff(
    db: Session,
    *,
    audience: str,
    now: datetime | None = None,
) -> CreatedMcpHandoff:
    """Create an ownerless login handoff awaiting a first-party sign-in."""
    current = _now(now)
    validated_audience = _validate_audience(audience)
    _purge_expired_access(db, now=current)
    state = _opaque_secret()
    exchange_secret = _opaque_secret()
    handoff = McpAccessHandoff(
        state_digest=_digest(state),
        exchange_digest=_digest(exchange_secret),
        request_type="session",
        audience=validated_audience,
        actor_id=f"mcp:{uuid4()}",
        requested_scopes=[],
        requested_purposes=[],
        requested_kinds=[],
        status="pending",
        expires_at=current + MCP_HANDOFF_TTL,
        created_at=current,
    )
    db.add(handoff)
    db.flush()
    return CreatedMcpHandoff(
        state=state,
        exchange_secret=exchange_secret,
        handoff=handoff,
    )


def create_context_handoff(
    db: Session,
    *,
    user_id: str,
    actor_id: str,
    audience: str,
    purpose: str,
    kind: str,
    access: Iterable[str],
    now: datetime | None = None,
) -> CreatedMcpHandoff:
    """Create an immutable purpose-bound request awaiting athlete approval."""
    current = _now(now)
    _, scopes = _validate_context_dimensions(
        purpose=purpose,
        kind=kind,
        access=access,
    )
    validated_audience = _validate_audience(audience)
    if db.get(User, user_id) is None:
        raise McpAccessNotFound("MCP owner is unavailable")
    _purge_expired_access(db, now=current)
    state = _opaque_secret()
    exchange_secret = _opaque_secret()
    handoff = McpAccessHandoff(
        user_id=user_id,
        state_digest=_digest(state),
        exchange_digest=_digest(exchange_secret),
        request_type="context",
        audience=validated_audience,
        actor_id=_validate_actor_id(actor_id),
        requested_scopes=scopes,
        requested_purposes=[purpose],
        requested_kinds=[kind],
        status="pending",
        expires_at=current + MCP_HANDOFF_TTL,
        created_at=current,
    )
    db.add(handoff)
    db.flush()
    return CreatedMcpHandoff(
        state=state,
        exchange_secret=exchange_secret,
        handoff=handoff,
    )


def _handoff_by_state(
    db: Session,
    state: str,
    *,
    lock: bool,
) -> McpAccessHandoff | None:
    if not isinstance(state, str) or not 20 <= len(state) <= 128:
        return None
    query = db.query(McpAccessHandoff).filter(
        McpAccessHandoff.state_digest == _digest(state),
    )
    if lock:
        query = query.with_for_update()
    return query.one_or_none()


def _active_handoff(
    handoff: McpAccessHandoff | None,
    *,
    now: datetime,
) -> McpAccessHandoff:
    if handoff is None:
        raise McpAccessNotFound("MCP handoff is unavailable")
    if handoff.expires_at <= now:
        raise McpAccessExpired("MCP handoff expired")
    return handoff


def inspect_handoff(
    db: Session,
    *,
    state: str,
    user_id: str,
    now: datetime | None = None,
) -> McpAccessHandoff:
    """Inspect a handoff without allowing another owner to enumerate it."""
    handoff = _active_handoff(
        _handoff_by_state(db, state, lock=False),
        now=_now(now),
    )
    if handoff.user_id is not None and handoff.user_id != user_id:
        raise McpAccessNotFound("MCP handoff is unavailable")
    return handoff


def decide_handoff(
    db: Session,
    *,
    state: str,
    user_id: str,
    decision: str,
    now: datetime | None = None,
) -> McpAccessHandoff:
    """Record an athlete decision without changing requested grant bounds."""
    if decision not in {"approved", "denied"}:
        raise McpAccessInvalid("MCP handoff decision is invalid")
    current = _now(now)
    begin_serialized_write(db)
    handoff = _active_handoff(
        _handoff_by_state(db, state, lock=True),
        now=current,
    )
    if handoff.user_id is not None and handoff.user_id != user_id:
        raise McpAccessNotFound("MCP handoff is unavailable")
    if handoff.status == decision:
        return handoff
    if handoff.status != "pending":
        raise McpAccessConflict("MCP handoff is no longer pending")
    if handoff.user_id is None:
        handoff.user_id = user_id
    handoff.status = decision
    handoff.decided_at = current
    db.flush()
    return handoff


def exchange_handoff(
    db: Session,
    *,
    state: str,
    exchange_secret: str,
    now: datetime | None = None,
) -> ExchangedMcpToken:
    """Exchange an approved handoff for one hashed, revocable bearer."""
    current = _now(now)
    # Reject random state/secret probes and non-exchangeable states without
    # taking SQLite's database-wide write lock. The locked re-read below
    # remains the authority for the one-time exchange.
    _validate_exchange_handoff(
        _handoff_by_state(db, state, lock=False),
        exchange_secret=exchange_secret,
        now=current,
    )
    db.rollback()
    begin_serialized_write(db)
    handoff = _validate_exchange_handoff(
        _handoff_by_state(db, state, lock=True),
        exchange_secret=exchange_secret,
        now=current,
    )
    user = db.get(User, handoff.user_id)
    if user is None or not user.is_active or user.is_demo:
        raise McpAccessDenied("MCP owner cannot authorize access")

    token_type = "session" if handoff.request_type == "session" else "context"
    prefix = (
        MCP_SESSION_PREFIX
        if token_type == "session"
        else MCP_CONTEXT_PREFIX
    )
    raw_token = f"{prefix}{_opaque_secret()}"
    token = McpAccessToken(
        user_id=handoff.user_id,
        token_digest=_digest(raw_token),
        token_type=token_type,
        audience=handoff.audience,
        actor_type=MCP_ACTOR_TYPE,
        actor_id=handoff.actor_id,
        scopes=list(handoff.requested_scopes or []),
        purposes=list(handoff.requested_purposes or []),
        kinds=list(handoff.requested_kinds or []),
        expires_at=current + (
            MCP_SESSION_TTL
            if token_type == "session"
            else MCP_CONTEXT_TTL
        ),
        created_at=current,
    )
    db.add(token)
    handoff.status = "exchanged"
    handoff.exchanged_at = current
    db.flush()
    return ExchangedMcpToken(access_token=raw_token, token=token)


def _validate_exchange_handoff(
    handoff: McpAccessHandoff | None,
    *,
    exchange_secret: str,
    now: datetime,
) -> McpAccessHandoff:
    """Validate opaque exchange proof and state without mutating it."""
    active = _active_handoff(handoff, now=now)
    if (
        not isinstance(exchange_secret, str)
        or not 20 <= len(exchange_secret) <= 128
        or not secrets.compare_digest(
            active.exchange_digest,
            _digest(exchange_secret),
        )
    ):
        raise McpAccessNotFound("MCP handoff is unavailable")
    if active.status == "pending":
        raise McpAccessPending("MCP handoff is pending")
    if active.status == "denied":
        raise McpAccessDenied("MCP handoff was denied")
    if active.status == "exchanged":
        raise McpAccessConflict("MCP handoff was already exchanged")
    if active.status != "approved" or active.user_id is None:
        raise McpAccessConflict("MCP handoff cannot be exchanged")
    return active


def authenticate_access_token(
    db: Session,
    *,
    raw_token: str,
    expected_type: str | None = None,
    expected_audience: str = MCP_AUDIENCE,
    now: datetime | None = None,
) -> McpAccessToken:
    """Resolve one current opaque token on every request."""
    if not isinstance(raw_token, str) or not (
        raw_token.startswith(MCP_SESSION_PREFIX)
        or raw_token.startswith(MCP_CONTEXT_PREFIX)
    ):
        raise McpAccessNotFound("MCP token is unavailable")
    token = (
        db.query(McpAccessToken)
        .filter(McpAccessToken.token_digest == _digest(raw_token))
        .one_or_none()
    )
    current = _now(now)
    if (
        token is None
        or token.revoked_at is not None
        or token.expires_at <= current
        or token.audience != expected_audience
        or (expected_type is not None and token.token_type != expected_type)
    ):
        raise McpAccessExpired("MCP token is unavailable")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active or user.is_demo:
        raise McpAccessExpired("MCP token is unavailable")
    return token


def token_claims(token: McpAccessToken) -> dict[str, Any]:
    """Build trusted dynamic claims from the current server-side grant."""
    return {
        "sub": token.user_id,
        "aud": token.audience,
        "praxys_actor_type": token.actor_type,
        "praxys_actor_id": token.actor_id,
        "praxys_credential_kind": (
            "mcp_session"
            if token.token_type == "session"
            else "context_grant"
        ),
        "praxys_access_token_id": token.id,
        "praxys_context_grant_id": (
            token.id if token.token_type == "context" else None
        ),
        "scope": list(token.scopes or []),
        "context_purposes": list(token.purposes or []),
        "context_kinds": list(token.kinds or []),
        "context_audience": token.audience,
    }


def access_names(token: McpAccessToken) -> list[str]:
    """Return stable read/write labels for a validated context grant."""
    return access_names_from_scopes(token.scopes or [])


def access_names_from_scopes(scopes: Iterable[str]) -> list[str]:
    """Return stable read/write labels for a trusted scope collection."""
    scope_set = set(scopes)
    return [
        access
        for access in (CONTEXT_ACCESS_READ, CONTEXT_ACCESS_WRITE)
        if _ACCESS_TO_SCOPE[access] in scope_set
    ]


def revoke_access_token(
    db: Session,
    *,
    token_id: str,
    user_id: str,
    now: datetime | None = None,
) -> McpAccessToken:
    """Revoke one exact owner-bound token immediately."""
    current = _now(now)
    begin_serialized_write(db)
    token = (
        db.query(McpAccessToken)
        .filter(
            McpAccessToken.id == token_id,
            McpAccessToken.user_id == user_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if token is None:
        raise McpAccessNotFound("MCP token is unavailable")
    if token.revoked_at is None:
        token.revoked_at = current
        db.flush()
    return token


def consume_context_write(
    db: Session,
    *,
    token_id: str,
    user_id: str,
    now: datetime | None = None,
) -> McpAccessToken:
    """Consume a write grant once after its structured preview validates."""
    current = _now(now)
    token = lock_context_write(
        db,
        token_id=token_id,
        user_id=user_id,
        now=current,
    )
    token.write_consumed_at = current
    db.flush()
    return token


def lock_context_write(
    db: Session,
    *,
    token_id: str,
    user_id: str,
    now: datetime | None = None,
) -> McpAccessToken:
    """Lock and validate a single-use write grant before draft validation."""
    current = _now(now)
    begin_serialized_write(db)
    token = (
        db.query(McpAccessToken)
        .filter(
            McpAccessToken.id == token_id,
            McpAccessToken.user_id == user_id,
            McpAccessToken.token_type == "context",
        )
        .with_for_update()
        .one_or_none()
    )
    if (
        token is None
        or token.revoked_at is not None
        or token.expires_at <= current
        or _ACCESS_TO_SCOPE[CONTEXT_ACCESS_WRITE]
        not in set(token.scopes or [])
    ):
        raise McpAccessExpired("MCP write grant is unavailable")
    if token.write_consumed_at is not None:
        raise McpAccessConflict("MCP write grant was already consumed")
    return token
