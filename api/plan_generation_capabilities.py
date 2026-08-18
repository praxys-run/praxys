"""Authoritative discovery and purpose selection for accepted plan policies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Literal, Mapping
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
from analysis.road_10k_contract import (
    ROAD_10K_CAPABILITY,
    ROAD_10K_EXECUTION,
    ROAD_10K_GENERATOR_VERSION,
    ROAD_10K_POLICY_VERSION,
    ROAD_10K_REQUIRED_INPUTS,
    ROAD_10K_SCIENCE_DECISION_ID,
)
from db.models import AdaptivePlan, AdaptivePlanGoalSnapshot, PlanProposal


PLAN_PURPOSE_SCHEMA_VERSION = 1
PLAN_PURPOSE_SOURCES = ("current_goal", "capability", "unlinked")
PLAN_GENERATION_CAPABILITY_SCHEMA_VERSION = 1
NO_ACCEPTED_PLAN_GENERATION_POLICY = "no_accepted_policy"
PLAN_ROUTING_SCHEMA_VERSION = 1
PLAN_ROUTING_POLICY_VERSION = "adult-running-plan-routing-v1"
PLAN_ROUTING_SCIENCE_BOUNDARY_ID = (
    "sdr-adult-running-plan-population-routing-v1"
)
PLAN_INTENTS = (
    "first_completion",
    "performance",
    "return_to_consistency",
)
PlanIntent = Literal[
    "first_completion",
    "performance",
    "return_to_consistency",
]
PlanRoutingState = Literal[
    "plan_candidate",
    "readiness_only",
    "clarification_required",
    "policy_unavailable",
]


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
    plan_intent: PlanIntent
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
    routing_readiness_strategy: str | None

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
    contract: dict[str, Any]


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
        plan_intent="performance",
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
        routing_readiness_strategy="goal_baseline_v1",
    ),
    PlanGenerationCapability(
        capability_id=str(ROAD_10K_CAPABILITY["capability_id"]),
        status="inactive",
        discipline=str(ROAD_10K_CAPABILITY["discipline"]),
        activity_types=tuple(str(item) for item in ROAD_10K_CAPABILITY["activity_types"]),
        goal_kinds=tuple(str(item) for item in ROAD_10K_CAPABILITY["goal_kinds"]),
        distances=(str(ROAD_10K_CAPABILITY["distance"]),),
        surfaces=(str(ROAD_10K_CAPABILITY["surface"]),),
        plan_intent=str(ROAD_10K_CAPABILITY["plan_intent"]),
        constraint_schema_id=str(ROAD_10K_REQUIRED_INPUTS["constraint_schema_id"]),
        policy_status="accepted",
        policy_version=ROAD_10K_POLICY_VERSION,
        generator_version=ROAD_10K_GENERATOR_VERSION,
        science_decision_id=ROAD_10K_SCIENCE_DECISION_ID,
        horizon_days=int(ROAD_10K_EXECUTION["committed_proposal_days"]),
        reassessment_days=int(
            ROAD_10K_EXECUTION["advisory_reassessment_after_completed_days"]
        ),
        readiness_href="/api/plan/road-10k/readiness",
        alternatives_href="/api/plan/road-10k/alternatives",
        generate_href="/api/plan/road-10k/generate",
        regenerate_href_template=(
            "/api/plan/road-10k/proposals/{proposal_id}/regenerate"
        ),
        purpose_goal_kind="performance_10k",
        purpose_distance="10k",
        allows_capability_goal=True,
        allows_unlinked=False,
        routing_readiness_strategy="road_10k_baseline_v1",
    ),
)
PLAN_GENERATION_CAPABILITY_CATALOG = PLAN_GENERATION_CAPABILITIES
PLAN_GENERATION_CAPABILITIES = tuple(
    capability
    for capability in PLAN_GENERATION_CAPABILITY_CATALOG
    if capability.status == "available"
)
OUTDOOR_ROAD_5K_CAPABILITY = PLAN_GENERATION_CAPABILITY_CATALOG[0]
OUTDOOR_ROAD_10K_CAPABILITY = PLAN_GENERATION_CAPABILITY_CATALOG[1]


def capability_is_available(capability_id: str) -> bool:
    """Return whether the capability currently participates in active routing."""
    return any(
        capability.capability_id == capability_id
        for capability in PLAN_GENERATION_CAPABILITIES
    )


def road_10k_capability_available() -> bool:
    """Return whether the reviewed road 10K capability is active."""
    return capability_is_available(OUTDOOR_ROAD_10K_CAPABILITY.capability_id)


def client_visible_goal(goal: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the Goal shape safe to expose while road 10K stays inactive."""
    raw_goal = dict(goal or {})
    if (
        str(raw_goal.get("goal_kind") or "").strip().casefold()
        != "performance_10k"
        or road_10k_capability_available()
    ):
        return raw_goal
    fallback = dict(raw_goal)
    fallback["goal_kind"] = (
        "race"
        if str(
            raw_goal.get("race_date") or raw_goal.get("target_event_date") or ""
        ).strip()
        else "continuous"
    )
    return fallback


def canonical_goal_plan_contract(
    goal: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the normalized Goal fields that can change plan intent."""
    normalized_input = dict(goal or {})
    raw_target = normalized_input.get("target_time_sec")
    target_is_empty = (
        raw_target is None
        or raw_target == 0
        or (
            isinstance(raw_target, str)
            and raw_target.strip() in {"", "0"}
        )
    )
    if target_is_empty:
        normalized_input["target_time_sec"] = normalized_input.get(
            "race_target_time_sec"
        )

    raw_race_date = normalized_input.get("race_date")
    if not str(raw_race_date or "").strip():
        raw_race_date = normalized_input.get("target_event_date")
        normalized_input["race_date"] = raw_race_date
    normalized = build_goal_baseline_goal(normalized_input)
    race_date = str(raw_race_date or "").strip() or None
    return {
        "goal_kind": normalized.goal_kind,
        "distance": normalized.distance,
        "target_time_sec": normalized.target_time_sec,
        "race_date": race_date,
    }


def current_goal_reference(
    *,
    user_id: str,
    goal: Mapping[str, Any],
) -> CurrentGoalReference | None:
    """Return a stable current-Goal identity and content revision."""
    raw_goal = dict(goal or {})
    if not raw_goal:
        return None
    contract = canonical_goal_plan_contract(raw_goal)
    canonical = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
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
        contract=contract,
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
            goal=current_goal.contract,
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
    intent: PlanIntent | None = None,
) -> dict[str, Any]:
    """Return the owner-scoped current Goal and all accepted policies."""
    config = load_config_from_db(user_id, db)
    raw_goal = dict(config.goal or {})
    normalized_goal = _normalize_goal(client_visible_goal(raw_goal))
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
        "goal_plan_impact": goal_plan_reconciliation_impact(
            db,
            user_id=user_id,
        ),
        "routing": _build_plan_routing(
            db,
            user_id=user_id,
            raw_goal=raw_goal,
            current_goal=current_goal,
            selected_capability=selected,
            explicit_intent=intent,
        ),
        "unsupported_reason": (
            None if selected is not None else NO_ACCEPTED_PLAN_GENERATION_POLICY
        ),
    }


def build_plan_generation_capability_discovery(
    db: Session,
    *,
    user_id: str,
    intent: PlanIntent | None = None,
) -> dict[str, Any]:
    """Backward-compatible capability discovery entry point."""
    return discover_plan_generation_capabilities(
        db,
        user_id=user_id,
        intent=intent,
    )


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


def goal_plan_reconciliation_impact(
    db: Session,
    *,
    user_id: str,
) -> dict[str, Any] | None:
    """Return a changed-Goal decision only when plan provenance is stale."""
    config = load_config_from_db(user_id, db)
    raw_goal = dict(config.goal or {})
    current_goal = current_goal_reference(user_id=user_id, goal=raw_goal)
    if current_goal is None:
        return None
    selected = _select_capability(raw_goal)
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

    adopted_goal = db.get(AdaptivePlanGoalSnapshot, plan.goal_snapshot_id)
    if adopted_goal is None:
        return None
    adopted_status = _goal_link_status(adopted_goal, current_goal)

    active_proposal: PlanProposal | None = None
    proposal_status: str | None = None
    if plan.active_proposal_id is not None:
        proposal = db.get(PlanProposal, plan.active_proposal_id)
        if (
            proposal is not None
            and proposal.state == "draft"
            and (
                proposal.expires_at is None
                or proposal.expires_at > datetime.utcnow()
            )
        ):
            proposal_goal = db.get(
                AdaptivePlanGoalSnapshot,
                proposal.goal_snapshot_id,
            )
            if proposal_goal is not None:
                active_proposal = proposal
                proposal_status = _goal_link_status(
                    proposal_goal,
                    current_goal,
                )

    if proposal_status in {"current", "independent", "legacy_unknown"}:
        return None
    stale_proposal = proposal_status == "reassessment_required"
    stale_adopted_plan = (
        active_proposal is None
        and adopted_status == "reassessment_required"
    )
    if not stale_proposal and not stale_adopted_plan:
        return None
    normalized_goal = _normalize_goal(raw_goal)
    can_generate_successor = any(
        len(
            _routing_purpose_candidates(
                intent=intent,
                goal=normalized_goal,
                current_goal=current_goal,
                selected_capability=selected,
            )
        )
        == 1
        for intent in PLAN_INTENTS
    )

    return {
        "status": "reassessment_required",
        "adaptive_plan_id": plan.id,
        "lifecycle": plan.lifecycle,
        "plan_goal_snapshot_id": adopted_goal.id,
        "current_goal_id": current_goal.goal_id,
        "current_goal_revision": current_goal.revision,
        "can_generate_successor": can_generate_successor,
        "can_keep_current_plan": (
            plan.lifecycle == "active"
            and adopted_status == "reassessment_required"
        ),
        "has_stale_proposal": stale_proposal,
        "unsupported_reason": (
            None
            if can_generate_successor
            else NO_ACCEPTED_PLAN_GENERATION_POLICY
        ),
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

    link_status = _goal_link_status(goal, current_goal)

    return {
        "adaptive_plan_id": plan.id,
        "lifecycle": plan.lifecycle,
        "goal_snapshot_id": goal.id,
        "purpose_source": goal.purpose_source,
        "source_goal_id": goal.source_goal_id,
        "source_goal_revision": goal.source_goal_revision,
        "link_status": link_status,
    }


def _goal_link_status(
    goal: AdaptivePlanGoalSnapshot,
    current_goal: CurrentGoalReference | None,
) -> str:
    if goal.purpose_source in {"capability", "unlinked"}:
        return "independent"
    if goal.purpose_source == "current_goal":
        if (
            current_goal is not None
            and goal.source_goal_id == current_goal.goal_id
            and goal.source_goal_revision == current_goal.revision
        ):
            return "current"
        return "reassessment_required"
    return "legacy_unknown"


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


def _build_plan_routing(
    db: Session,
    *,
    user_id: str,
    raw_goal: Mapping[str, Any],
    current_goal: CurrentGoalReference | None,
    selected_capability: PlanGenerationCapability | None,
    explicit_intent: PlanIntent | None,
) -> dict[str, Any]:
    normalized_goal = _normalize_goal(raw_goal)
    readiness_cache: dict[tuple[str, str], str | None] = {}
    options = [
        _build_plan_routing_option(
            db,
            user_id=user_id,
            intent=intent,
            goal=normalized_goal,
            current_goal=current_goal,
            selected_capability=selected_capability,
            readiness_cache=readiness_cache,
        )
        for intent in PLAN_INTENTS
    ]
    inferred_intent: PlanIntent | None = (
        "performance"
        if normalized_goal["goal_kind"] in {"performance_5k", "performance_10k"}
        else None
    )
    selected_intent = explicit_intent or inferred_intent
    if selected_intent is None:
        return {
            "schema_version": PLAN_ROUTING_SCHEMA_VERSION,
            "policy_version": PLAN_ROUTING_POLICY_VERSION,
            "science_boundary_id": PLAN_ROUTING_SCIENCE_BOUNDARY_ID,
            "state": "clarification_required",
            "intent": None,
            "intent_source": "unconfirmed",
            "reason_code": "intent_confirmation_required",
            "capability_id": None,
            "purpose_source": None,
            "baseline_readiness": None,
            "options": options,
        }

    selected_option = next(
        option
        for option in options
        if option["intent"] == selected_intent
    )
    return {
        "schema_version": PLAN_ROUTING_SCHEMA_VERSION,
        "policy_version": PLAN_ROUTING_POLICY_VERSION,
        "science_boundary_id": PLAN_ROUTING_SCIENCE_BOUNDARY_ID,
        **selected_option,
        "intent_source": (
            "explicit" if explicit_intent is not None else "current_goal"
        ),
        "options": options,
    }


def _build_plan_routing_option(
    db: Session,
    *,
    user_id: str,
    intent: str,
    goal: Mapping[str, str | None],
    current_goal: CurrentGoalReference | None,
    selected_capability: PlanGenerationCapability | None,
    readiness_cache: dict[tuple[str, str], str | None],
) -> dict[str, Any]:
    purpose_candidates = _routing_purpose_candidates(
        intent=intent,
        goal=goal,
        current_goal=current_goal,
        selected_capability=selected_capability,
    )
    if len(purpose_candidates) > 1:
        return _routing_option_payload(
            intent=intent,
            state="clarification_required",
            reason_code="capability_context_confirmation_required",
        )
    if not purpose_candidates:
        return _routing_option_payload(
            intent=intent,
            state="policy_unavailable",
            reason_code="no_accepted_policy_for_intent",
        )

    capability, purpose_source = purpose_candidates[0]
    cache_key = (capability.capability_id, purpose_source)
    if cache_key not in readiness_cache:
        readiness_cache[cache_key] = _routing_baseline_readiness(
            db,
            user_id=user_id,
            capability=capability,
            purpose_source=purpose_source,
            current_goal=current_goal,
        )
    baseline_readiness = readiness_cache[cache_key]
    if baseline_readiness == "sufficient_baseline":
        return _routing_option_payload(
            intent=intent,
            state="plan_candidate",
            reason_code="accepted_policy_with_sufficient_baseline",
            capability=capability,
            purpose_source=purpose_source,
            baseline_readiness=baseline_readiness,
        )
    return _routing_option_payload(
        intent=intent,
        state="readiness_only",
        reason_code="accepted_policy_requires_readiness",
        capability=capability,
        purpose_source=purpose_source,
        baseline_readiness=baseline_readiness,
    )


def _routing_purpose_candidates(
    *,
    intent: str,
    goal: Mapping[str, str | None],
    current_goal: CurrentGoalReference | None,
    selected_capability: PlanGenerationCapability | None,
) -> list[tuple[PlanGenerationCapability, str]]:
    distance = goal.get("distance")
    candidates = [
        capability
        for capability in PLAN_GENERATION_CAPABILITIES
        if capability.policy_status == "accepted"
        and capability.plan_intent == intent
        and distance is not None
        and distance in capability.distances
    ]
    if (
        selected_capability is not None
        and selected_capability in candidates
        and current_goal is not None
    ):
        return [(selected_capability, "current_goal")]
    return [
        (item, source)
        for item in candidates
        for source, allowed in (
            ("capability", item.allows_capability_goal),
            ("unlinked", item.allows_unlinked),
        )
        if allowed
    ]


def _routing_baseline_readiness(
    db: Session,
    *,
    user_id: str,
    capability: PlanGenerationCapability,
    purpose_source: str,
    current_goal: CurrentGoalReference | None,
) -> str | None:
    if capability.routing_readiness_strategy is None:
        return "sufficient_baseline"
    if capability.routing_readiness_strategy != "goal_baseline_v1":
        if capability.routing_readiness_strategy != "road_10k_baseline_v1":
            raise RuntimeError(
                "Unsupported plan-routing readiness strategy: "
                f"{capability.routing_readiness_strategy}"
            )
        from api.road_10k_baseline import build_road_10k_baseline_view

        purpose_selection = {
            "capability_id": capability.capability_id,
            "source": purpose_source,
            "expected_goal_id": (
                current_goal.goal_id if purpose_source == "current_goal" else None
            ),
            "expected_goal_revision": (
                current_goal.revision
                if purpose_source == "current_goal"
                else None
            ),
        }
        baseline = build_road_10k_baseline_view(
            db,
            user_id=user_id,
            purpose_selection=purpose_selection,
        )["baseline"]
        return str(baseline["readiness"])
    from api.goal_baseline import build_goal_baseline_view

    purpose_selection = {
        "capability_id": capability.capability_id,
        "source": purpose_source,
        "expected_goal_id": (
            current_goal.goal_id if purpose_source == "current_goal" else None
        ),
        "expected_goal_revision": (
            current_goal.revision
            if purpose_source == "current_goal"
            else None
        ),
    }
    baseline = build_goal_baseline_view(
        db,
        user_id=user_id,
        purpose_selection=purpose_selection,
    )["baseline"]
    return str(baseline["readiness"])


def _routing_option_payload(
    *,
    intent: str,
    state: PlanRoutingState,
    reason_code: str,
    capability: PlanGenerationCapability | None = None,
    purpose_source: str | None = None,
    baseline_readiness: str | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "state": state,
        "reason_code": reason_code,
        "capability_id": (
            capability.capability_id if capability is not None else None
        ),
        "purpose_source": purpose_source,
        "baseline_readiness": baseline_readiness,
    }


def _serialize_purpose_goal(
    goal: Mapping[str, Any],
) -> dict[str, Any]:
    return canonical_goal_plan_contract(goal)


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
        "intent": capability.plan_intent,
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
