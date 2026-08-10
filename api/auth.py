"""Authentication middleware — JWT token validation.

Every request to a protected endpoint must include a valid Bearer token
from the Authorization header. Tokens are issued by the /api/auth/login endpoint.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Mapping

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.auth_secrets import get_jwt_secret
from db.session import get_db

if TYPE_CHECKING:
    from db.models import User

logger = logging.getLogger(__name__)

# How stale User.last_seen_at must be before we rewrite it. Bounds the extra
# write to at most one UPDATE per user per window, keeping the WAU/DAU gauge
# (api/app_config.activity_counts) fed without a per-request DB write.
LAST_SEEN_THROTTLE = timedelta(minutes=15)


@dataclass(frozen=True)
class AuthenticatedIdentity:
    """Validated bearer identity plus its signed JWT claims."""

    user_id: str
    user: "User"
    claims: Mapping[str, Any]
    is_demo: bool
    credential_kind: str


def _touch_last_seen(db: Session, user: "User") -> None:
    """Best-effort, throttled update of the user's last-activity timestamp.

    Never raises: an activity-gauge write must not be able to fail a real
    request. Only writes when the stored value is missing or older than
    LAST_SEEN_THROTTLE.
    """
    try:
        now = datetime.utcnow()
        last = user.last_seen_at
        if last is None or (now - last) >= LAST_SEEN_THROTTLE:
            user.last_seen_at = now
            db.commit()
    except Exception:
        db.rollback()


def get_authenticated_identity(
    request: Request,
    db: Session,
) -> AuthenticatedIdentity:
    """Validate a first-party JWT or server-authoritative MCP bearer."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")

    token = auth_header.split(" ", 1)[1]
    from api.mcp_access import (
        MCP_CONTEXT_PREFIX,
        MCP_SESSION_PREFIX,
        McpAccessError,
        authenticate_access_token,
        token_claims,
    )

    if token.startswith((MCP_SESSION_PREFIX, MCP_CONTEXT_PREFIX)):
        try:
            access = authenticate_access_token(db, raw_token=token)
        except McpAccessError as exc:
            raise HTTPException(401, "Invalid or expired token") from exc
        if (
            access.token_type == "context"
            and not request.url.path.startswith("/api/personal-context/")
        ):
            raise HTTPException(403, "Context token cannot access this route")
        from db.models import User

        user = db.query(User).filter(User.id == access.user_id).first()
        if user is None:
            raise HTTPException(401, "User not found")
        return AuthenticatedIdentity(
            user_id=access.user_id,
            user=user,
            claims=token_claims(access),
            is_demo=bool(user.is_demo),
            credential_kind=(
                "mcp_session"
                if access.token_type == "session"
                else "context_grant"
            ),
        )

    import jwt
    try:
        payload = jwt.decode(
            token, get_jwt_secret(), algorithms=["HS256"],
            audience=["fastapi-users:auth"],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Invalid token: no subject")

        from db.models import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(401, "User not found")
        return AuthenticatedIdentity(
            user_id=str(user_id),
            user=user,
            claims=payload,
            is_demo=bool(user.is_demo),
            credential_kind="first_party_jwt",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")


def _get_token_user(request: Request, db: Session) -> tuple[str, "User"]:
    """Validate a first-party bearer and return its current database user."""
    identity = get_authenticated_identity(request, db)
    _require_first_party(identity)
    return identity.user_id, identity.user


def _require_first_party(identity: AuthenticatedIdentity) -> None:
    """Keep MCP capabilities out of ordinary account and data endpoints."""
    if identity.credential_kind != "first_party_jwt":
        raise HTTPException(403, "First-party authentication required")


def get_active_identity(
    request: Request,
    db: Session,
) -> AuthenticatedIdentity:
    """Return an active bearer identity and update its activity timestamp."""
    identity = get_authenticated_identity(request, db)
    if not identity.user.is_active:
        raise HTTPException(401, "User account is deactivated")
    _touch_last_seen(db, identity.user)
    # Context mutations acquire SQLite's BEGIN IMMEDIATE themselves. End the
    # authentication read transaction so that lock is not silently skipped.
    db.rollback()
    return identity


def get_current_user_id(request: Request, db: Session = Depends(get_db)) -> str:
    """Get the active user ID from the JWT bearer token."""
    identity = get_active_identity(request, db)
    _require_first_party(identity)
    return identity.user_id


def require_account_deletion_access(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    """Allow a token owner, including a pending inactive account, to self-delete."""
    user_id, user = _get_token_user(request, db)
    if user.is_demo:
        raise HTTPException(403, "Demo accounts cannot modify data")
    return user_id


def get_data_user_id(request: Request, db: Session = Depends(get_db)) -> str:
    """Get the user_id whose data should be displayed.

    For demo users, returns the source admin's user_id (demo_of).
    For normal users, returns their own user_id.
    Use this on READ endpoints so demo users transparently see admin's data.
    """
    user_id = get_current_user_id(request, db)
    from db.models import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    if user.is_demo and user.demo_of:
        # Verify the source admin still exists
        target = db.query(User).filter(User.id == user.demo_of, User.is_active == True).first()
        if not target:
            raise HTTPException(403, "Demo source account is no longer available")
        return user.demo_of
    return user_id


def require_write_access(request: Request, db: Session = Depends(get_db)) -> str:
    """Get current user_id and verify write access.

    Raises 403 for demo accounts. Fails closed — unknown users are rejected.
    Use this on WRITE endpoints.
    """
    user_id = get_current_user_id(request, db)
    from db.models import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "User not found")
    if user.is_demo:
        raise HTTPException(403, "Demo accounts cannot modify data")
    return user_id
