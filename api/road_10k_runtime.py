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
    load_stage_authority,
)

Road10KBoundary = Literal[
    "discovery", "invitation", "enrollment", "processing",
    "generation", "adoption", "first_exposure", "screenshot",
    "purge", "restore", "provider", "export", "withdrawal",
    "deletion",
]

# This is the canonical stage-capability vocabulary.  Owner data rights are
# intentionally listed for callers' audit clarity, but are never granted by
# this evaluator; their authority-independent handlers own those rights.
ROAD_10K_BOUNDARIES = frozenset(Road10KBoundary.__args__)



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
    boundary: Road10KBoundary | str,
    *,
    lifecycle: bool = False,
) -> Road10KRuntimeDecision:
    """Fail closed for every Road 10K stage boundary in this revision.

    The authority artifact is parsed elsewhere only as dormant schema input.
    No branch in this evaluator can authorize discovery, enrollment,
    processing, result exposure, generation, adoption, storage, provider, or
    lifecycle access.  Unknown boundaries receive the same deny decision.
    """
    del lifecycle
    reason = "inactive_revision" if boundary in ROAD_10K_BOUNDARIES else "unknown_boundary"
    return Road10KRuntimeDecision(False, reason, "hidden", False, False)


def road_10k_ready(db: Session) -> bool:
    """Readiness is closed unless authority, ledger, and replay are healthy."""
    snapshot = road_10k_runtime_snapshot(db)
    return bool(snapshot.get("ready") is True)


def provider_fence_is_closed() -> bool:
    """Provider/AI/MCP delivery is permanently closed in this foundation."""
    # A closed provider fence is not provider authority.
    return True
