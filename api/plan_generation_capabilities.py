"""Authoritative discovery for accepted plan-generation capabilities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from sqlalchemy.orm import Session

from analysis.config import load_config_from_db
from analysis.goal_baseline import build_goal_baseline_goal
from analysis.outdoor_5k_plan_generation import (
    OUTDOOR_5K_BLOCK_DAYS,
    OUTDOOR_5K_GENERATOR_VERSION,
    OUTDOOR_5K_POLICY_VERSION,
    OUTDOOR_5K_REASSESSMENT_DAYS,
    OUTDOOR_5K_SCIENCE_DECISION_ID,
)


PLAN_GENERATION_CAPABILITY_SCHEMA_VERSION = 1
NO_ACCEPTED_PLAN_GENERATION_POLICY = "no_accepted_policy"


@dataclass(frozen=True)
class PlanGenerationActions:
    """Policy-specific action paths exposed to every client."""

    readiness_href: str
    alternatives_href: str
    generate_href: str
    regenerate_href_template: str


@dataclass(frozen=True)
class PlanGenerationCapability:
    """One accepted policy that clients may safely offer to an athlete."""

    id: str
    status: str
    policy_status: str
    discipline: str
    activity_types: tuple[str, ...]
    goal_kinds: tuple[str, ...]
    distances: tuple[str, ...]
    surfaces: tuple[str, ...]
    constraint_schema_id: str
    policy_version: str
    generator_version: str
    science_decision_id: str
    horizon_days: int
    reassessment_days: int
    actions: PlanGenerationActions

    def matches_goal(self, goal: Mapping[str, Any]) -> bool:
        """Return whether the normalized goal can enter this capability."""
        goal_kind = str(goal.get("goal_kind") or "").strip().casefold()
        distance = str(goal.get("distance") or "").strip().casefold()
        return (
            goal_kind in self.goal_kinds
            and (not self.distances or distance in self.distances)
        )

    def serialize(self) -> dict[str, Any]:
        """Return a stable JSON-safe capability contract."""
        payload = asdict(self)
        payload["goal_match"] = {
            "goal_kinds": list(payload.pop("goal_kinds")),
            "distances": list(payload.pop("distances")),
            "surfaces": list(payload.pop("surfaces")),
        }
        payload["activity_types"] = list(payload["activity_types"])
        return payload


OUTDOOR_ROAD_5K_CAPABILITY = PlanGenerationCapability(
    id="outdoor_road_5k_v1",
    status="available",
    policy_status="accepted",
    discipline="running",
    activity_types=("running",),
    goal_kinds=("performance_5k",),
    distances=("5k",),
    surfaces=("outdoor_road",),
    constraint_schema_id="outdoor_road_5k_constraints_v1",
    policy_version=OUTDOOR_5K_POLICY_VERSION,
    generator_version=OUTDOOR_5K_GENERATOR_VERSION,
    science_decision_id=OUTDOOR_5K_SCIENCE_DECISION_ID,
    horizon_days=OUTDOOR_5K_BLOCK_DAYS,
    reassessment_days=OUTDOOR_5K_REASSESSMENT_DAYS,
    actions=PlanGenerationActions(
        readiness_href="/api/plan/outdoor-5k/readiness",
        alternatives_href="/api/plan/outdoor-5k/alternatives",
        generate_href="/api/plan/outdoor-5k/generate",
        regenerate_href_template=(
            "/api/plan/outdoor-5k/proposals/{proposal_id}/regenerate"
        ),
    ),
)

_CAPABILITIES = (OUTDOOR_ROAD_5K_CAPABILITY,)


def list_plan_generation_capabilities() -> tuple[PlanGenerationCapability, ...]:
    """Return accepted capabilities in deterministic presentation order."""
    return _CAPABILITIES


def select_plan_generation_capability(
    goal: Mapping[str, Any],
) -> PlanGenerationCapability | None:
    """Resolve one normalized goal to an accepted generation capability."""
    return next(
        (
            capability
            for capability in _CAPABILITIES
            if capability.matches_goal(goal)
        ),
        None,
    )


def build_plan_generation_capability_discovery(
    db: Session,
    *,
    user_id: str,
) -> dict[str, Any]:
    """Build the owner-scoped capability response for the athlete's current goal."""
    config = load_config_from_db(user_id, db)
    normalized_goal = build_goal_baseline_goal(config.goal)
    goal = {
        "goal_kind": normalized_goal.goal_kind,
        "distance": normalized_goal.distance,
    }
    selected = select_plan_generation_capability(goal)
    return {
        "schema_version": PLAN_GENERATION_CAPABILITY_SCHEMA_VERSION,
        "goal": goal,
        "selected_capability": selected.serialize() if selected else None,
        "capabilities": [
            capability.serialize()
            for capability in list_plan_generation_capabilities()
        ],
        "unsupported_reason": (
            None if selected else NO_ACCEPTED_PLAN_GENERATION_POLICY
        ),
    }
