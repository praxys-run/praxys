"""Repository-only runtime boundary primitives for Road 10K.

These functions are read-only.  They provide no authority writer, scheduler,
alert resource, actor binding, or production purge execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from api.road_10k_control import road_10k_runtime_snapshot
from api.road_10k_stage_authority import (
    Road10KStageAuthority,
    authority_denial_reason,
    load_stage_authority,
)

Road10KBoundary = Literal[
    "discovery",
    "invitation",
    "enrollment",
    "processing",
    "first_exposure",
    "screenshot",
    "purge",
    "restore",
    "export",
    "withdrawal",
    "deletion",
]


@dataclass(frozen=True)
class Road10KRuntimeDecision:
    allowed: bool
    reason: str
    rollout_status: str
    plan_actions_read_only: bool
    provider_calls_allowed: bool


def read_stage_authority() -> Road10KStageAuthority | None:
    """Read the external artifact; never cache or mutate it."""
    return load_stage_authority()


def evaluate_boundary(
    boundary: Road10KBoundary,
    *,
    lifecycle: bool = False,
) -> Road10KRuntimeDecision:
    """Evaluate one runtime boundary from the current authoritative artifact."""
    authority = load_stage_authority()
    if authority is None:
        return Road10KRuntimeDecision(
            False,
            "authority_missing_or_malformed",
            "hidden",
            False,
            False,
        )
    lifecycle_state = authority.lifecycle_status
    allowed = lifecycle_state == "active" or (
        lifecycle and lifecycle_state in {"paused", "killed", "hold", "rollback"}
    )
    read_only = lifecycle_state in {"paused", "killed", "hold", "rollback"}
    return Road10KRuntimeDecision(
        allowed,
        authority_denial_reason(authority) if not allowed else "allowed",
        "enrolled" if allowed else (lifecycle_state or authority.state),
        read_only,
        False,
    )


def road_10k_ready(db: Session) -> bool:
    """Readiness is closed unless authority, ledger, and replay are healthy."""
    snapshot = road_10k_runtime_snapshot(db)
    return bool(snapshot.get("ready") is True)


def provider_fence_is_closed() -> bool:
    """Provider/AI/MCP delivery is permanently closed in this foundation."""
    authority = load_stage_authority()
    return authority is None or authority.provider_fence == "closed"
