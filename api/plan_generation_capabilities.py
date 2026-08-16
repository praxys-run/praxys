"""Authoritative discovery and purpose selection for accepted plan policies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
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
from db.models import AdaptivePlan, AdaptivePlanGoalSnapshot, PlanProposal


PLAN_PURPOSE_SCHEMA_VERSION = 1
PLAN_PURPOSE_SOURCES = ("current_goal", "capability", "unlinked")
PLAN_GENERATION_CAPABILITY_SCHEMA_VERSION = 1
NO_ACCEPTED_PLAN_GENERATION_POLICY = "no_accepted_policy"


class PlanPurposeError(RuntimeError):
    """Structured, safe-to-expose purpose-selection error."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = {"code": code, "message": message, **details}


@dataclass(frozen=True)
class PlanGenerationCapability:
    """One accepted policy that runtime plan generation may execute."""

    capability_id: str
    status: str
    discipline: str
    activity_types: tuple[str, ...]
    goal_kinds: tuple[str, ...]
    distances: tuple[str, ...]
    surfaces: tuple[str, ...]
    constraint_schema_id: str
    policy_status: str
    policy_version: str
    generator_version: str
    science_decision_id: str
    horizon_days: int
    reassessment_days: int
    readiness_href: str
    alternatives_href: str
    generate_href: str
    regenerate_href_template: str
    purpose_goal_kind: str
    purpose_distance: str | None
    allows_capability_goal: bool
    allows_unlinked: bool

    def matches(self, goal: Mapping[str, Any]) -> bool:
        """Return whether a normalized user goal maps to this policy."""
        normalized = build_goal_baseline_goal(goal)
        return (
            normalized.goal_kind in self.goal_kinds
            and normalized.distance in self.distances
        )

    def default_goal(self) -> dict[str, Any]:
        """Return the policy-owned goal contract for a separate purpose."""
        return {
            "goal_kind": self.purpose_goal_kind,
            "distance": self.purpose_distance,
        }


@dataclass(frozen=True)
class CurrentGoalReference:
    """Stable identity and revision for the mutable current Goal."""

    goal_id: str
    revision: str
    raw_goal: dict[str, Any]


@dataclass(frozen=True)
class ResolvedPlanGenerationPurpose:
    """Exact accepted purpose resolved against current owner state."""

    capability: PlanGenerationCapability
    source: str
    goal: dict[str, Any]
    source_goal_id: str | None
    source_goal_revision: str | None

    def selection_payload(self) -> dict[str, Any]:
        """Serialize the exact replayable selection."""
        return {
            "capability_id": self.capability.capability_id,
            "source": self.source,
            "expected_goal_id": self.source_goal_id,
            "expected_goal_revision": self.source_goal_revision,
        }

    def public_payload(self) -> dict[str, Any]:
        """Serialize selection plus its resolved immutable goal contract."""
        return {
            **self.selection_payload(),
            "goal": _serialize_purpose_goal(self.goal),
        }


PLAN_GENERATION_CAPABILITIES = (
    PlanGenerationCapability(
        capability_id="outdoor_road_5k_v1",
        status="available",
        discipline="running",
        activity_types=("running",),
        goal_kinds=("performance_5k",),
        distances=("5k",),
        surfaces=("outdoor_road",),
        constraint_schema_id="outdoor_road_5k_constraints_v1",
        policy_status="accepted",
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        generator_version=OUTDOOR_5K_GENERATOR_VERSION,
        science_decision_id=OUTDOOR_5K_SCIENCE_DECISION_ID,
        horizon_days=OUTDOOR_5K_BLOCK_DAYS,
        reassessment_days=OUTDOOR_5K_REASSESSMENT_DAYS,
        readiness_href="/api/plan/outdoor-5k/readiness",
        alternatives_href="/api/plan/outdoor-5k/alternatives",
        generate_href="/api/plan/outdoor-5k/generate",
        regenerate_href_template=(
            "/api/plan/outdoor-5k/proposals/{proposal_id}/regenerate"
        ),
        purpose_goal_kind="performance_5k",
        purpose_distance="5k",
        allows_capability_goal=True,
        allows_unlinked=False,
    ),
)
OUTDOOR_ROAD_5K_CAPABILITY = PLAN_GENERATION_CAPABILITIES[0]
_CAPABILITIES = PLAN_GENERATION_CAPABILITIES


def current_goal_reference(
    *,
    user_id: str,
    goal: Mapping[str, Any],
) -> CurrentGoalReference | None:
    """Return a stable current-Goal identity and content revision."""
    raw_goal = dict(goal or {})
    if not raw_goal:
        return None
    canonical = json.dumps(
        raw_goal,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return CurrentGoalReference(
        goal_id=str(
            uuid5(
                NAMESPACE_URL,
                f"https://praxys.run/users/{user_id}/goals/current",
            )
        ),
        revision=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        raw_goal=raw_goal,
    )


def resolve_plan_generation_purpose(
    db: Session,
    *,
    user_id: str,
    selection: Mapping[str, Any] | None,
) -> ResolvedPlanGenerationPurpose:
    """Resolve and fence a selected purpose against current owner state."""
    config = load_config_from_db(user_id, db)
    raw_goal = dict(config.goal or {})
    current_goal = current_goal_reference(user_id=user_id, goal=raw_goal)
    selected_current = _select_capability(raw_goal)
    explicit = selection is not None

    if selection is None:
        if selected_current is None or current_goal is None:
            raise PlanPurposeError(
                409,
                "PLAN_PURPOSE_REQUIRED",
                "Choose an accepted plan purpose before checking readiness.",
            )
        capability = selected_current
        source = "current_goal"
        expected_goal_id = current_goal.goal_id
        expected_goal_revision = current_goal.revision
    else:
        capability_id = str(selection.get("capability_id") or "").strip()
        capability = next(
            (
                item
                for item in PLAN_GENERATION_CAPABILITIES
                if item.capability_id == capability_id
            ),
            None,
        )
        if capability is None:
            raise PlanPurposeError(
                400,
                "PLAN_PURPOSE_UNSUPPORTED",
                "The selected plan capability is not accepted.",
                capability_id=capability_id or None,
            )
        source = str(selection.get("source") or "").strip()
        if source not in PLAN_PURPOSE_SOURCES:
            raise PlanPurposeError(
                400,
                "PLAN_PURPOSE_INVALID",
                "The selected plan-purpose source is invalid.",
                source=source or None,
            )
        expected_goal_id = (
            str(selection.get("expected_goal_id") or "").strip() or None
        )
        expected_goal_revision = (
            str(selection.get("expected_goal_revision") or "").strip() or None
        )

    if source == "current_goal":
        if current_goal is None or selected_current is None:
            raise PlanPurposeError(
                409,
                "PLAN_PURPOSE_UNAVAILABLE",
                "The current Goal does not map to this accepted policy.",
            )
        if selected_current.capability_id != capability.capability_id:
            raise PlanPurposeError(
                409,
                "PLAN_PURPOSE_UNAVAILABLE",
                "The current Goal maps to a different accepted policy.",
            )
        if explicit and (
            expected_goal_id is None or expected_goal_revision is None
        ):
            raise PlanPurposeError(
                400,
                "PLAN_PURPOSE_INVALID",
                "Current-Goal selection requires its expected ID and revision.",
            )
        if (
            expected_goal_id != current_goal.goal_id
            or expected_goal_revision != current_goal.revision
        ):
            raise PlanPurposeError(
                409,
                "PLAN_PURPOSE_STALE",
                "The current Goal changed after this purpose was selected.",
                current_goal_id=current_goal.goal_id,
                current_goal_revision=current_goal.revision,
            )
        return ResolvedPlanGenerationPurpose(
            capability=capability,
            source=source,
            goal=current_goal.raw_goal,
            source_goal_id=current_goal.goal_id,
            source_goal_revision=current_goal.revision,
        )

    if expected_goal_id is not None or expected_goal_revision is not None:
        raise PlanPurposeError(
            400,
            "PLAN_PURPOSE_INVALID",
            "Only current-Goal selection may carry source Goal fencing.",
        )
    if source == "capability" and not capability.allows_capability_goal:
        raise PlanPurposeError(
            400,
            "PLAN_PURPOSE_UNSUPPORTED",
            "This policy cannot be used as a separate plan purpose.",
        )
    if source == "unlinked" and not capability.allows_unlinked:
        raise PlanPurposeError(
            400,
            "PLAN_PURPOSE_UNSUPPORTED",
            "This policy does not support an unlinked or base plan.",
        )
    return ResolvedPlanGenerationPurpose(
        capability=capability,
        source=source,
        goal=capability.default_goal(),
        source_goal_id=None,
        source_goal_revision=None,
    )


def discover_plan_generation_capabilities(
    db: Session,
    *,
    user_id: str,
) -> dict[str, Any]:
    """Return the owner-scoped current Goal and all accepted policies."""
    config = load_config_from_db(user_id, db)
    raw_goal = dict(config.goal or {})
    normalized_goal = _normalize_goal(raw_goal)
    current_goal = current_goal_reference(user_id=user_id, goal=raw_goal)
    selected = _select_capability(raw_goal)
    active_plan_goal = _active_plan_goal_link(
        db,
        user_id=user_id,
        current_goal=current_goal,
    )
    return {
        "schema_version": 1,
        "purpose_schema_version": PLAN_PURPOSE_SCHEMA_VERSION,
        "goal": normalized_goal,
        "current_goal": (
            {
                "id": current_goal.goal_id,
                "revision": current_goal.revision,
                "goal": normalized_goal,
            }
            if current_goal is not None
            else None
        ),
        "selected_capability": (
            _serialize_capability(selected) if selected is not None else None
        ),
        "capabilities": [
            _serialize_capability(capability)
            for capability in PLAN_GENERATION_CAPABILITIES
        ],
        "active_plan_goal": active_plan_goal,
        "unsupported_reason": (
            None if selected is not None else NO_ACCEPTED_PLAN_GENERATION_POLICY
        ),
    }


def build_plan_generation_capability_discovery(
    db: Session,
    *,
    user_id: str,
) -> dict[str, Any]:
    """Backward-compatible capability discovery entry point."""
    return discover_plan_generation_capabilities(db, user_id=user_id)


def list_plan_generation_capabilities(
) -> tuple[PlanGenerationCapability, ...]:
    """Return accepted capabilities in deterministic presentation order."""
    return PLAN_GENERATION_CAPABILITIES


def select_plan_generation_capability(
    goal: Mapping[str, Any],
) -> PlanGenerationCapability | None:
    """Resolve one normalized goal to an accepted generation capability."""
    return _select_capability(goal)


def get_plan_generation_actions(
    *,
    capability_id: str,
) -> dict[str, Any]:
    """Return tool-facing actions only for an accepted capability."""
    capability = next(
        (
            item
            for item in PLAN_GENERATION_CAPABILITIES
            if item.capability_id == capability_id
        ),
        None,
    )
    if capability is None:
        return {
            "schema_version": 1,
            "capability_id": capability_id,
            "authorized": False,
            "actions": [],
            "reason": "unknown_capability",
        }
    return {
        "schema_version": 1,
        "capability_id": capability.capability_id,
        "authorized": True,
        "purpose_schema": _serialize_purpose(capability),
        "actions": [
            {
                "action": "check_readiness",
                "method": "POST",
                "href": capability.readiness_href,
                "constraint_schema_id": capability.constraint_schema_id,
            },
            {
                "action": "list_alternatives",
                "method": "POST",
                "href": capability.alternatives_href,
                "constraint_schema_id": capability.constraint_schema_id,
            },
            {
                "action": "generate_proposal",
                "method": "POST",
                "href": capability.generate_href,
                "constraint_schema_id": capability.constraint_schema_id,
                "requires": [
                    "purpose",
                    "expected_source_revision",
                    "idempotency_key",
                ],
            },
            {
                "action": "regenerate_proposal",
                "method": "POST",
                "href_template": capability.regenerate_href_template,
                "constraint_schema_id": capability.constraint_schema_id,
                "requires": [
                    "purpose",
                    "expected_source_revision",
                    "expected_proposal_version",
                    "idempotency_key",
                ],
            },
        ],
        "reason": None,
    }


def authorize_plan_generation_action(
    *,
    capability_id: str,
    action: str,
) -> bool:
    """Fail closed unless an accepted capability advertises the action."""
    payload = get_plan_generation_actions(capability_id=capability_id)
    if not payload["authorized"]:
        return False
    return action in {
        item["action"] for item in payload["actions"]
    }


def _active_plan_goal_link(
    db: Session,
    *,
    user_id: str,
    current_goal: CurrentGoalReference | None,
) -> dict[str, Any] | None:
    plan = db.execute(
        select(AdaptivePlan)
        .where(
            AdaptivePlan.user_id == user_id,
            AdaptivePlan.lifecycle.in_(("draft", "active")),
        )
        .order_by(AdaptivePlan.updated_at.desc())
    ).scalars().first()
    if plan is None:
        return None
    goal_snapshot_id = plan.goal_snapshot_id
    if plan.active_proposal_id is not None:
        active_proposal = db.get(PlanProposal, plan.active_proposal_id)
        if (
            active_proposal is not None
            and active_proposal.state == "draft"
            and (
                active_proposal.expires_at is None
                or active_proposal.expires_at > datetime.utcnow()
            )
        ):
            goal_snapshot_id = active_proposal.goal_snapshot_id
    goal = db.get(AdaptivePlanGoalSnapshot, goal_snapshot_id)
    if goal is None:
        return None

    if goal.purpose_source in {"capability", "unlinked"}:
        link_status = "independent"
    elif goal.purpose_source == "current_goal":
        if (
            current_goal is not None
            and goal.source_goal_id == current_goal.goal_id
            and goal.source_goal_revision == current_goal.revision
        ):
            link_status = "current"
        else:
            link_status = "reassessment_required"
    else:
        link_status = "legacy_unknown"

    return {
        "adaptive_plan_id": plan.id,
        "lifecycle": plan.lifecycle,
        "goal_snapshot_id": goal.id,
        "purpose_source": goal.purpose_source,
        "source_goal_id": goal.source_goal_id,
        "source_goal_revision": goal.source_goal_revision,
        "link_status": link_status,
    }


def _select_capability(
    goal: Mapping[str, Any],
) -> PlanGenerationCapability | None:
    return next(
        (
            capability
            for capability in PLAN_GENERATION_CAPABILITIES
            if capability.policy_status == "accepted"
            and capability.matches(goal)
        ),
        None,
    )


def _normalize_goal(goal: Mapping[str, Any]) -> dict[str, str | None]:
    if not goal:
        return {"goal_kind": None, "distance": None}
    normalized = build_goal_baseline_goal(goal)
    return {
        "goal_kind": normalized.goal_kind,
        "distance": normalized.distance,
    }


def _serialize_purpose_goal(
    goal: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_input = dict(goal)
    if normalized_input.get("target_time_sec") is None:
        normalized_input["target_time_sec"] = goal.get(
            "race_target_time_sec"
        )
    normalized = build_goal_baseline_goal(normalized_input)
    return {
        "goal_kind": normalized.goal_kind,
        "distance": normalized.distance,
        "target_time_sec": normalized.target_time_sec,
        "race_date": str(goal.get("race_date") or "").strip() or None,
    }


def _serialize_purpose(
    capability: PlanGenerationCapability,
) -> dict[str, Any]:
    return {
        "schema_version": PLAN_PURPOSE_SCHEMA_VERSION,
        "goal_kind": capability.purpose_goal_kind,
        "distance": capability.purpose_distance,
        "allows_capability_goal": capability.allows_capability_goal,
        "allows_unlinked": capability.allows_unlinked,
    }


def _serialize_capability(
    capability: PlanGenerationCapability,
) -> dict[str, Any]:
    return {
        "id": capability.capability_id,
        "status": capability.status,
        "discipline": capability.discipline,
        "activity_types": list(capability.activity_types),
        "policy_status": capability.policy_status,
        "goal_match": {
            "goal_kinds": list(capability.goal_kinds),
            "distances": list(capability.distances),
            "surfaces": list(capability.surfaces),
        },
        "constraint_schema_id": capability.constraint_schema_id,
        "purpose": _serialize_purpose(capability),
        "policy_version": capability.policy_version,
        "generator_version": capability.generator_version,
        "science_decision_id": capability.science_decision_id,
        "horizon_days": capability.horizon_days,
        "reassessment_days": capability.reassessment_days,
        "actions": {
            "readiness_href": capability.readiness_href,
            "alternatives_href": capability.alternatives_href,
            "generate_href": capability.generate_href,
            "regenerate_href_template": (
                capability.regenerate_href_template
            ),
        },
    }
