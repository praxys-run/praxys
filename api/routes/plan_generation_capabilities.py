"""Authenticated plan-generation capability discovery."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.auth import get_data_user_id
from api.plan_generation_capabilities import (
    build_plan_generation_capability_discovery,
)
from db.session import get_db


router = APIRouter()


class PlanGenerationActionsResponse(BaseModel):
    """Policy-specific action paths for a generation client."""

    model_config = ConfigDict(extra="forbid")

    readiness_href: str
    alternatives_href: str
    generate_href: str
    regenerate_href_template: str


class PlanGenerationGoalMatchResponse(BaseModel):
    """Goal fields and explicit setting boundary admitted by a capability."""

    model_config = ConfigDict(extra="forbid")

    goal_kinds: list[str]
    distances: list[str]
    surfaces: list[str]


class PlanGenerationCapabilityResponse(BaseModel):
    """One accepted capability available to every Praxys client."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["available"]
    policy_status: Literal["accepted"]
    discipline: Literal["running", "trail_running"]
    activity_types: list[str]
    goal_match: PlanGenerationGoalMatchResponse
    constraint_schema_id: str
    purpose: dict[str, Any]
    policy_version: str
    generator_version: str
    science_decision_id: str
    horizon_days: int = Field(ge=1)
    reassessment_days: int = Field(ge=1)
    actions: PlanGenerationActionsResponse


class PlanGenerationGoalResponse(BaseModel):
    """Privacy-minimized current goal fields used for capability matching."""

    model_config = ConfigDict(extra="forbid")

    goal_kind: str | None
    distance: str | None


class PlanGenerationCurrentGoalResponse(BaseModel):
    """Stable current-Goal identity used for optimistic purpose fencing."""

    model_config = ConfigDict(extra="forbid")

    id: str
    revision: str
    goal: PlanGenerationGoalResponse


class ActivePlanGoalResponse(BaseModel):
    """How the current adaptive-plan goal relates to the mutable Goal."""

    model_config = ConfigDict(extra="forbid")

    adaptive_plan_id: str
    lifecycle: str
    goal_snapshot_id: str
    purpose_source: str | None
    source_goal_id: str | None
    source_goal_revision: str | None
    link_status: Literal[
        "current",
        "independent",
        "reassessment_required",
        "legacy_unknown",
    ]


class PlanGenerationCapabilityDiscoveryResponse(BaseModel):
    """Versioned owner-scoped capability discovery response."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    purpose_schema_version: Literal[1]
    goal: PlanGenerationGoalResponse
    current_goal: PlanGenerationCurrentGoalResponse | None
    selected_capability: PlanGenerationCapabilityResponse | None
    capabilities: list[PlanGenerationCapabilityResponse]
    active_plan_goal: ActivePlanGoalResponse | None
    unsupported_reason: Literal["no_accepted_policy"] | None


@router.get(
    "/plan/generation/capabilities",
    response_model=PlanGenerationCapabilityDiscoveryResponse,
)
def get_plan_generation_capabilities(
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return accepted policies and the match for the caller's current goal."""
    return build_plan_generation_capability_discovery(db, user_id=user_id)
