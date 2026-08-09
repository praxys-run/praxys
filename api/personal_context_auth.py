"""Server-enforced actor and scope boundaries for private plan context."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.auth import get_active_identity
from api.personal_context import CONTEXT_KINDS, CONTEXT_PURPOSES
from db.session import get_db

CONTEXT_SCOPE_READ = "plan:context:read"
CONTEXT_SCOPE_NARRATIVE_READ = "plan:context:narrative:read"
CONTEXT_SCOPE_WRITE = "plan:context:write"
CONTEXT_SCOPE_DELETE = "plan:context:delete"
CONTEXT_SCOPE_AI_CONSENT = "plan:context:ai-consent"

CONTEXT_SCOPES = frozenset({
    CONTEXT_SCOPE_READ,
    CONTEXT_SCOPE_NARRATIVE_READ,
    CONTEXT_SCOPE_WRITE,
    CONTEXT_SCOPE_DELETE,
    CONTEXT_SCOPE_AI_CONSENT,
})
_DELEGATED_ACTORS = frozenset({"plugin", "mcp", "delegated_agent"})


@dataclass(frozen=True)
class ContextActor:
    """Authenticated owner plus context-specific delegated authority."""

    user_id: str
    actor_type: str
    actor_id: str
    scopes: frozenset[str]
    purposes: frozenset[str]
    kinds: frozenset[str]
    is_demo: bool

    @property
    def is_athlete(self) -> bool:
        """Whether this request is the owner's trusted first-party action."""
        return self.actor_type == "athlete"


def _claim_values(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset(part for part in value.split() if part)
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(
            str(part)
            for part in value
            if isinstance(part, str) and part
        )
    return frozenset()


def _has_scoped_claims(claims: dict[str, Any] | Any) -> bool:
    return any(
        key in claims
        for key in (
            "scope",
            "scopes",
            "praxys_actor_type",
            "praxys_actor_id",
            "context_purposes",
            "context_kinds",
        )
    )


def get_context_actor(
    request: Request,
    db: Session = Depends(get_db),
) -> ContextActor:
    """Resolve first-party ownership or a narrowly scoped delegated actor."""
    identity = get_active_identity(request, db)
    claims = dict(identity.claims)
    claimed_actor = claims.get("praxys_actor_type")

    if not _has_scoped_claims(claims):
        return ContextActor(
            user_id=identity.user_id,
            actor_type="athlete",
            actor_id=identity.user_id,
            scopes=CONTEXT_SCOPES,
            purposes=CONTEXT_PURPOSES,
            kinds=CONTEXT_KINDS,
            is_demo=identity.is_demo,
        )

    actor_type = (
        str(claimed_actor)
        if claimed_actor in _DELEGATED_ACTORS
        else "scoped_client"
    )
    raw_actor_id = claims.get("praxys_actor_id")
    actor_id = (
        str(raw_actor_id)
        if isinstance(raw_actor_id, str)
        and raw_actor_id
        and len(raw_actor_id) <= 120
        else ""
    )
    scopes = (
        _claim_values(claims.get("scope"))
        | _claim_values(claims.get("scopes"))
    ) & CONTEXT_SCOPES
    purposes = _claim_values(claims.get("context_purposes"))
    kinds = _claim_values(claims.get("context_kinds"))
    if actor_type not in _DELEGATED_ACTORS or not actor_id:
        scopes = frozenset()
        purposes = frozenset()
        kinds = frozenset()
    return ContextActor(
        user_id=identity.user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        scopes=frozenset(scopes),
        purposes=frozenset(purposes & CONTEXT_PURPOSES),
        kinds=frozenset(kinds & CONTEXT_KINDS),
        is_demo=identity.is_demo,
    )


def authorize_context(
    actor: ContextActor,
    scope: str,
    *,
    purpose: str | None = None,
    kind: str | None = None,
    athlete_only: bool = False,
    mutation: bool = False,
    non_enumerating: bool = False,
) -> None:
    """Enforce exact context scope and delegated purpose/kind limits."""
    allowed = scope in actor.scopes
    if athlete_only and not actor.is_athlete:
        allowed = False
    if mutation and actor.is_demo:
        allowed = False
    if (
        purpose is not None
        and not actor.is_athlete
        and purpose not in actor.purposes
    ):
        allowed = False
    if kind is not None and not actor.is_athlete and kind not in actor.kinds:
        allowed = False
    if allowed:
        return
    if non_enumerating:
        raise HTTPException(404, detail="PERSONAL_CONTEXT_NOT_FOUND")
    raise HTTPException(403, detail="PERSONAL_CONTEXT_SCOPE_REQUIRED")


def authorize_context_ids(
    actor: ContextActor,
    scope: str,
    *,
    purposes: Iterable[str],
    kinds: Iterable[str],
) -> None:
    """Authorize a multi-item query against every requested dimension."""
    authorize_context(actor, scope)
    if actor.is_athlete:
        return
    if not set(purposes).issubset(actor.purposes) or not set(kinds).issubset(
        actor.kinds
    ):
        raise HTTPException(403, detail="PERSONAL_CONTEXT_SCOPE_REQUIRED")
