"""Owner-scoped domain service for adaptive plan proposals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Callable, Mapping, MutableMapping, Sequence
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analysis.config import PRAXYS_PLAN_SOURCES, PRAXYS_PLAN_WRITE_SOURCE
from analysis.metrics import is_rest_workout
from api.plan_workout_structure import (
    normalize_adaptive_plan_discipline,
    validate_structured_workout,
)
from db.cache_revision import bump_revisions
from db.models import (
    AdaptivePlan,
    AdaptivePlanGoalSnapshot,
    PlanProposal,
    PlanRevision,
    TrainingPlan,
)
from db.plan_ledger import lock_plan_writes, plan_snapshot, record_plan_revision


class AdaptivePlanError(Exception):
    """Structured domain error safe to expose through the API."""

    def __init__(self, status_code: int, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = {"code": code, "message": message, **details}


@dataclass(frozen=True)
class ProposalInput:
    """Structured, privacy-minimized input for one immutable proposal."""

    goal: Mapping[str, Any]
    discipline: str
    workouts: Sequence[Mapping[str, Any]]
    origin: str
    actor_type: str
    actor_id: str | None
    idempotency_key: str
    policy_version: str | None = None
    model_version: str | None = None
    science_version: str | None = None
    assumptions: Sequence[Any] = ()
    unknowns: Sequence[Any] = ()
    warnings: Sequence[Any] = ()
    alternatives: Sequence[Any] = ()
    expires_at: datetime | None = None


_WORKOUT_FIELDS = (
    "canonical_id",
    "date",
    "activity_type",
    "workout_type",
    "planned_duration_min",
    "planned_distance_km",
    "target_power_min",
    "target_power_max",
    "target_hr_min",
    "target_hr_max",
    "target_pace_min",
    "target_pace_max",
    "workout_description",
    "workout_structure_version",
    "workout_structure",
)


_NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "planned_duration_min": (0, 1440),
    "planned_distance_km": (0, 1000),
    "target_power_min": (0, 5000),
    "target_power_max": (0, 5000),
    "target_hr_min": (0, 300),
    "target_hr_max": (0, 300),
}


_ACTIVE_PLAN_STATES = ("draft", "active")
_TERMINAL_PROPOSAL_STATES = ("rejected", "adopted", "expired")


def _parse_date(value: Any, *, field: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                f"{field} must be an ISO date.",
                field=field,
            ) from exc
    raise AdaptivePlanError(
        400,
        "PLAN_PROPOSAL_VALIDATION_FAILED",
        f"{field} must be an ISO date.",
        field=field,
    )


def _parse_uuid(value: Any, *, field: str) -> str:
    if value in (None, ""):
        return str(uuid4())
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError) as exc:
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            f"{field} must be a UUID.",
            field=field,
        ) from exc


def _json_list(value: Sequence[Any]) -> list[Any]:
    return list(value or [])


def _validate_goal(goal: Mapping[str, Any]) -> dict[str, Any]:
    goal_kind = str(goal.get("goal_kind") or "").strip()
    if not goal_kind:
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            "goal_kind is required.",
            field="goal.goal_kind",
        )
    horizon_start = _parse_date(goal.get("horizon_start"), field="goal.horizon_start")
    horizon_end = _parse_date(goal.get("horizon_end"), field="goal.horizon_end")
    if horizon_end < horizon_start:
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            "Goal horizon end cannot be before horizon start.",
            field="goal.horizon_end",
        )
    target = goal.get("target") or {}
    if not isinstance(target, Mapping):
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            "goal.target must be an object.",
            field="goal.target",
        )
    purpose_source = str(goal.get("purpose_source") or "").strip() or None
    if purpose_source not in {None, "current_goal", "capability", "unlinked"}:
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            "goal.purpose_source is invalid.",
            field="goal.purpose_source",
        )
    source_goal_id = str(goal.get("source_goal_id") or "").strip() or None
    source_goal_revision = (
        str(goal.get("source_goal_revision") or "").strip() or None
    )
    if purpose_source == "current_goal":
        if source_goal_id is None or source_goal_revision is None:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                "Current-Goal proposals require source Goal provenance.",
                field="goal.source_goal_id",
            )
        source_goal_id = _parse_uuid(
            source_goal_id,
            field="goal.source_goal_id",
        )
        if len(source_goal_revision) != 64:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                "goal.source_goal_revision must be a SHA-256 digest.",
                field="goal.source_goal_revision",
            )
    elif source_goal_id is not None or source_goal_revision is not None:
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            "Only current-Goal proposals may carry source Goal provenance.",
            field="goal.source_goal_id",
        )
    snapshot = {
        "goal_kind": goal_kind,
        "target": dict(target),
        "horizon_start": horizon_start.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "purpose_source": purpose_source,
        "source_goal_id": source_goal_id,
        "source_goal_revision": source_goal_revision,
    }
    return {
        "purpose_source": purpose_source,
        "source_goal_id": source_goal_id,
        "source_goal_revision": source_goal_revision,
        "goal_kind": goal_kind,
        "target": dict(target),
        "horizon_start": horizon_start,
        "horizon_end": horizon_end,
        "snapshot": snapshot,
    }


def _require_validated_policy_purpose(
    goal: Mapping[str, Any],
    *,
    validated_policy_purpose: bool,
) -> None:
    """Keep capability-owned purpose provenance behind policy validation."""
    if (
        goal.get("purpose_source") in {"capability", "unlinked"}
        and not validated_policy_purpose
    ):
        raise AdaptivePlanError(
            400,
            "PLAN_PURPOSE_UNSUPPORTED",
            (
                "Capability-owned purpose provenance must be created through "
                "an accepted plan-generation policy."
            ),
            field="goal.purpose_source",
        )


def _fence_current_goal_provenance(
    db: Session,
    *,
    user_id: str,
    goal: Mapping[str, Any],
) -> None:
    """Reject linked proposal writes after the mutable current Goal changes."""
    if goal.get("purpose_source") != "current_goal":
        return

    from analysis.config import load_config_from_db
    from api.plan_generation_capabilities import current_goal_reference

    config = load_config_from_db(user_id, db)
    current_goal = current_goal_reference(
        user_id=user_id,
        goal=dict(config.goal or {}),
    )
    if (
        current_goal is None
        or goal.get("source_goal_id") != current_goal.goal_id
        or goal.get("source_goal_revision") != current_goal.revision
    ):
        raise AdaptivePlanError(
            409,
            "PLAN_PURPOSE_REASSESSMENT_REQUIRED",
            "The Goal linked to this proposal changed; reassess before continuing.",
            current_goal_id=(
                current_goal.goal_id if current_goal is not None else None
            ),
            current_goal_revision=(
                current_goal.revision if current_goal is not None else None
            ),
        )
    if "goal_kind" not in goal or "target" not in goal:
        return

    from analysis.goal_baseline import build_goal_baseline_goal

    target = goal.get("target")
    if not isinstance(target, Mapping):
        target = {}
    expected = build_goal_baseline_goal(current_goal.contract)
    observed = build_goal_baseline_goal({
        "goal_kind": goal.get("goal_kind"),
        "distance": target.get("distance"),
        "target_time_sec": target.get("target_time_sec"),
        "race_target_time_sec": target.get("race_target_time_sec"),
    })
    expected_event_date = (
        str(current_goal.contract.get("race_date") or "").strip() or None
    )
    observed_event_date = (
        str(
            target.get("target_event_date")
            or target.get("race_date")
            or ""
        ).strip()
        or None
    )
    if (
        observed.goal_kind != expected.goal_kind
        or observed.distance != expected.distance
        or observed.target_time_sec != expected.target_time_sec
        or observed_event_date != expected_event_date
    ):
        raise AdaptivePlanError(
            400,
            "PLAN_PURPOSE_INVALID",
            "The proposal goal does not match the linked current Goal.",
            field="goal",
        )


def _bounded_number(value: Any, *, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise AdaptivePlanError(400, "PLAN_PROPOSAL_VALIDATION_FAILED", f"{field} must be numeric.", field=field)
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise AdaptivePlanError(400, "PLAN_PROPOSAL_VALIDATION_FAILED", f"{field} must be numeric.", field=field) from exc
    low, high = _NUMERIC_BOUNDS[field]
    if numeric < low or numeric > high:
        raise AdaptivePlanError(
            400,
            "PLAN_PROPOSAL_VALIDATION_FAILED",
            f"{field} is outside the supported range.",
            field=field,
        )
    return numeric


def _validate_workouts(
    workouts: Sequence[Mapping[str, Any]],
    *,
    horizon_start: date,
    horizon_end: date,
    current_date: date,
) -> list[dict[str, Any]]:
    if not workouts:
        raise AdaptivePlanError(400, "PLAN_PROPOSAL_VALIDATION_FAILED", "At least one workout is required.")
    seen_dates: set[str] = set()
    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, workout in enumerate(workouts):
        unsupported = sorted(set(workout) - set(_WORKOUT_FIELDS))
        if unsupported:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_UNSUPPORTED_FIELD",
                "Unsupported workout field supplied.",
                index=index,
                fields=unsupported,
            )
        workout_date = _parse_date(workout.get("date"), field=f"workouts[{index}].date")
        if workout_date < current_date:
            raise AdaptivePlanError(
                409,
                "PLAN_PROPOSAL_DATE_IMMUTABLE",
                "Proposal workouts cannot target completed or past dates.",
                minimum_date=current_date.isoformat(),
            )
        if workout_date < horizon_start or workout_date > horizon_end:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_DATE_OUT_OF_BOUNDS",
                "Workout date is outside the goal horizon.",
                index=index,
                date=workout_date.isoformat(),
            )
        date_key = workout_date.isoformat()
        if date_key in seen_dates:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_DUPLICATE_DATE",
                "Only one proposal workout per date is supported.",
                date=date_key,
            )
        seen_dates.add(date_key)
        canonical_id = _parse_uuid(workout.get("canonical_id"), field=f"workouts[{index}].canonical_id")
        if canonical_id in seen_ids:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_DUPLICATE_WORKOUT_ID",
                "Proposal workout identities must be unique.",
                canonical_id=canonical_id,
            )
        seen_ids.add(canonical_id)
        workout_type = str(workout.get("workout_type") or "").strip()
        if not workout_type:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                "workout_type is required.",
                field=f"workouts[{index}].workout_type",
            )
        activity_type = str(workout.get("activity_type") or "").strip()
        if not activity_type:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                "activity_type is required.",
                field=f"workouts[{index}].activity_type",
            )
        workout_structure_version = str(
            workout.get("workout_structure_version") or ""
        ).strip()
        workout_structure = workout.get("workout_structure")
        if not workout_structure_version or workout_structure is None:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                "workout_structure_version and workout_structure are required.",
                field=f"workouts[{index}].workout_structure",
            )
        item = {
            "canonical_id": canonical_id,
            "date": date_key,
            "activity_type": activity_type,
            "workout_type": workout_type,
            "planned_duration_min": _bounded_number(workout.get("planned_duration_min"), field="planned_duration_min"),
            "planned_distance_km": _bounded_number(workout.get("planned_distance_km"), field="planned_distance_km"),
            "target_power_min": _bounded_number(workout.get("target_power_min"), field="target_power_min"),
            "target_power_max": _bounded_number(workout.get("target_power_max"), field="target_power_max"),
            "target_hr_min": _bounded_number(workout.get("target_hr_min"), field="target_hr_min"),
            "target_hr_max": _bounded_number(workout.get("target_hr_max"), field="target_hr_max"),
            "target_pace_min": workout.get("target_pace_min"),
            "target_pace_max": workout.get("target_pace_max"),
            "workout_description": workout.get("workout_description") or "",
            "workout_structure_version": workout_structure_version,
        }
        for pace_field in ("target_pace_min", "target_pace_max"):
            pace = item[pace_field]
            if pace is not None:
                item[pace_field] = str(pace).strip()[:20]
        if item["target_power_min"] is not None and item["target_power_max"] is not None and item["target_power_min"] > item["target_power_max"]:
            raise AdaptivePlanError(400, "PLAN_PROPOSAL_TARGET_RANGE_INVALID", "Minimum target power cannot exceed maximum target power.")
        if item["target_hr_min"] is not None and item["target_hr_max"] is not None and item["target_hr_min"] > item["target_hr_max"]:
            raise AdaptivePlanError(400, "PLAN_PROPOSAL_TARGET_RANGE_INVALID", "Minimum target heart rate cannot exceed maximum target heart rate.")
        try:
            (
                normalized_activity_type,
                normalized_structure,
                projections,
            ) = validate_structured_workout(
                workout_type=workout_type,
                activity_type=activity_type,
                workout_structure_version=workout_structure_version,
                workout_structure=workout_structure,
            )
        except (ValidationError, ValueError) as exc:
            raise AdaptivePlanError(
                400,
                "PLAN_PROPOSAL_VALIDATION_FAILED",
                "Structured workout is invalid.",
                field=f"workouts[{index}].workout_structure",
            ) from exc
        item["activity_type"] = normalized_activity_type
        item["workout_structure"] = normalized_structure
        item.update(projections)
        normalized.append(item)
    return sorted(normalized, key=lambda item: item["date"])


def _proposal_to_dict(
    db: Session,
    proposal: PlanProposal,
) -> dict[str, Any]:
    plan = db.get(AdaptivePlan, proposal.adaptive_plan_id)
    goal = db.get(AdaptivePlanGoalSnapshot, proposal.goal_snapshot_id)
    return {
        "id": proposal.id,
        "adaptive_plan_id": proposal.adaptive_plan_id,
        "goal_snapshot_id": proposal.goal_snapshot_id,
        "discipline": proposal.discipline,
        "version": proposal.version,
        "state": proposal.state,
        "base_plan_version": proposal.base_plan_version,
        "supersedes_proposal_id": proposal.supersedes_proposal_id,
        "origin": proposal.origin,
        "actor_type": proposal.actor_type,
        "actor_id": proposal.actor_id,
        "policy_version": proposal.policy_version,
        "model_version": proposal.model_version,
        "science_version": proposal.science_version,
        "assumptions": proposal.assumptions or [],
        "unknowns": proposal.unknowns or [],
        "warnings": proposal.warnings or [],
        "alternatives": proposal.alternatives or [],
        "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        "decided_at": proposal.decided_at.isoformat() if proposal.decided_at else None,
        "workouts": proposal.workout_snapshot or [],
        "adaptive_plan": None if plan is None else {
            "id": plan.id,
            "discipline": plan.discipline,
            "version": plan.version,
            "lifecycle": plan.lifecycle,
            "active_proposal_id": plan.active_proposal_id,
        },
        "goal": None if goal is None else {
            "id": goal.id,
            "version": goal.version,
            "state": goal.state,
            "purpose_source": goal.purpose_source,
            "source_goal_id": goal.source_goal_id,
            "source_goal_revision": goal.source_goal_revision,
            "goal_kind": goal.goal_kind,
            "target": goal.target or {},
            "horizon_start": goal.horizon_start.isoformat(),
            "horizon_end": goal.horizon_end.isoformat(),
            "acknowledged_at": goal.acknowledged_at.isoformat() if goal.acknowledged_at else None,
        },
    }


def _proposal_snapshot_for_replay(
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Add nullable purpose provenance omitted by pre-purpose adoption snapshots."""
    normalized = dict(snapshot)
    goal = normalized.get("goal")
    if isinstance(goal, Mapping):
        normalized_goal = dict(goal)
        for field in (
            "purpose_source",
            "source_goal_id",
            "source_goal_revision",
        ):
            normalized_goal.setdefault(field, None)
        normalized["goal"] = normalized_goal
    return normalized


def _idempotency_matches_proposal(
    *,
    proposal: PlanProposal,
    request_fingerprint: str,
) -> bool:
    """Return whether an idempotency replay is the exact same immutable command."""
    return proposal.idempotency_fingerprint == request_fingerprint


def _utc_naive(value: datetime | None) -> datetime | None:
    """Normalize a validated public timestamp to the SQLite UTC representation."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _idempotency_conflict() -> AdaptivePlanError:
    """Build the safe error returned for a non-identical idempotency reuse."""
    return AdaptivePlanError(
        409,
        "PLAN_PROPOSAL_IDEMPOTENCY_CONFLICT",
        "This idempotency key was already used for a different proposal request.",
    )


def _mark_idempotency_replay(
    idempotency_replay_state: MutableMapping[str, bool] | None,
) -> None:
    """Tell an optional policy caller that this invocation returned a replay."""
    if idempotency_replay_state is not None:
        idempotency_replay_state["replayed"] = True


def _proposal_request_fingerprint(
    *,
    payload: ProposalInput,
    goal: Mapping[str, Any],
    discipline: str,
    workouts: Sequence[Mapping[str, Any]],
    predecessor_proposal_id: str | None,
    predecessor_version: int | None,
) -> str:
    """Hash the complete immutable proposal command without retaining duplicate PII."""
    expires_at = _utc_naive(payload.expires_at)
    requested_workouts: list[dict[str, Any]] = []
    for workout in payload.workouts:
        item = dict(workout)
        # Initial proposal identity is generated server-side when omitted. It
        # must not make an otherwise exact retry look like a new command.
        if item.get("canonical_id") in (None, ""):
            item.pop("canonical_id", None)
        requested_workouts.append(item)
    goal_command = {
        "goal_kind": goal["goal_kind"],
        "target": goal["target"],
        "horizon_start": goal["horizon_start"].isoformat(),
        "horizon_end": goal["horizon_end"].isoformat(),
    }
    if goal.get("purpose_source") is not None:
        goal_command.update({
            "purpose_source": goal["purpose_source"],
            "source_goal_id": goal.get("source_goal_id"),
            "source_goal_revision": goal.get("source_goal_revision"),
        })
    command = {
        "goal": goal_command,
        "discipline": discipline,
        "workouts": requested_workouts,
        "origin": payload.origin,
        "actor_type": payload.actor_type,
        "actor_id": payload.actor_id,
        "policy_version": payload.policy_version,
        "model_version": payload.model_version,
        "science_version": payload.science_version,
        "assumptions": _json_list(payload.assumptions),
        "unknowns": _json_list(payload.unknowns),
        "warnings": _json_list(payload.warnings),
        "alternatives": _json_list(payload.alternatives),
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
        "predecessor_proposal_id": predecessor_proposal_id,
        "predecessor_version": predecessor_version,
    }
    canonical = json.dumps(command, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing_proposal_for_key(db: Session, *, user_id: str, idempotency_key: str) -> PlanProposal | None:
    return db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()


def _active_plan(db: Session, *, user_id: str, for_update: bool = False) -> AdaptivePlan | None:
    stmt = select(AdaptivePlan).where(
        AdaptivePlan.user_id == user_id,
        AdaptivePlan.lifecycle.in_(_ACTIVE_PLAN_STATES),
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def _canonical_plan_version(db: Session, *, user_id: str) -> int:
    """Return the owner-scoped canonical plan revision-stream version."""
    return int(
        db.execute(
            select(func.count(PlanRevision.id)).where(PlanRevision.user_id == user_id)
        ).scalar_one()
        or 0
    )


def _sync_plan_version(db: Session, *, user_id: str, adaptive_plan: AdaptivePlan) -> int:
    current_version = max(
        int(adaptive_plan.version or 0),
        _canonical_plan_version(db, user_id=user_id),
    )
    adaptive_plan.version = current_version
    return current_version


def _next_proposal_version(db: Session, *, adaptive_plan_id: str) -> int:
    current = db.execute(
        select(func.max(PlanProposal.version)).where(
            PlanProposal.adaptive_plan_id == adaptive_plan_id
        )
    ).scalar_one()
    return int(current or 0) + 1


def _proposal_expired(proposal: PlanProposal, *, now: datetime) -> bool:
    return proposal.expires_at is not None and proposal.expires_at <= now


def _archive_expired_draft(
    db: Session,
    *,
    user_id: str,
    adaptive_plan: AdaptivePlan,
    now: datetime,
) -> bool:
    if not adaptive_plan.active_proposal_id:
        return False
    proposal = db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.id == adaptive_plan.active_proposal_id,
            PlanProposal.state == "draft",
        ).with_for_update()
    ).scalar_one_or_none()
    if proposal is None or not _proposal_expired(proposal, now=now):
        return False
    proposal.state = "expired"
    proposal.decided_at = now
    adaptive_plan.active_proposal_id = None
    if adaptive_plan.lifecycle == "draft":
        adaptive_plan.lifecycle = "archived"
    return True


def _expire_proposal_if_needed(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
    now: datetime,
) -> bool:
    if proposal.state != "draft" or not _proposal_expired(proposal, now=now):
        return False
    adaptive_plan = db.execute(
        select(AdaptivePlan).where(
            AdaptivePlan.user_id == user_id,
            AdaptivePlan.id == proposal.adaptive_plan_id,
        ).with_for_update()
    ).scalar_one()
    proposal.state = "expired"
    proposal.decided_at = now
    if adaptive_plan.active_proposal_id == proposal.id:
        adaptive_plan.active_proposal_id = None
    if adaptive_plan.lifecycle == "draft":
        adaptive_plan.lifecycle = "archived"
    return True


def _idempotent_proposal_hit(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
) -> dict[str, Any]:
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        locked = db.execute(
            select(PlanProposal).where(
                PlanProposal.user_id == user_id,
                PlanProposal.id == proposal.id,
            ).with_for_update()
        ).scalar_one()
        if _expire_proposal_if_needed(
            db,
            user_id=user_id,
            proposal=locked,
            now=datetime.utcnow(),
        ):
            db.commit()
        return _proposal_to_dict(db, locked)
    except Exception:
        db.rollback()
        raise


def create_draft_proposal(
    db: Session,
    *,
    user_id: str,
    payload: ProposalInput,
    current_date: date,
    before_persist: Callable[[Session], None] | None = None,
    idempotency_replay_state: MutableMapping[str, bool] | None = None,
    on_created: Callable[[Session, PlanProposal], None] | None = None,
    validated_policy_purpose: bool = False,
) -> dict[str, Any]:
    """Create the first immutable proposal for a new adaptive plan aggregate.

    ``before_persist`` runs after the owner-scoped plan write lock is held,
    before any proposal row is staged. Policy services use it to recheck
    mutable source inputs in that locked transaction.

    ``idempotency_replay_state`` lets a policy wrapper reconstruct its own
    persisted response when an in-flight exact retry is found under that lock.
    """
    goal = _validate_goal(payload.goal)
    _require_validated_policy_purpose(
        goal,
        validated_policy_purpose=validated_policy_purpose,
    )
    discipline = normalize_adaptive_plan_discipline(payload.discipline)
    workouts = _validate_workouts(
        payload.workouts,
        horizon_start=goal["horizon_start"],
        horizon_end=goal["horizon_end"],
        current_date=current_date,
    )
    request_fingerprint = _proposal_request_fingerprint(
        payload=payload,
        goal=goal,
        discipline=discipline,
        workouts=workouts,
        predecessor_proposal_id=None,
        predecessor_version=None,
    )
    existing = _existing_proposal_for_key(
        db,
        user_id=user_id,
        idempotency_key=payload.idempotency_key,
    )
    if existing is not None:
        if _idempotency_matches_proposal(
            proposal=existing,
            request_fingerprint=request_fingerprint,
        ):
            _mark_idempotency_replay(idempotency_replay_state)
            return _idempotent_proposal_hit(db, user_id=user_id, proposal=existing)
        raise _idempotency_conflict()
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing = _existing_proposal_for_key(
            db,
            user_id=user_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            if _idempotency_matches_proposal(
                proposal=existing,
                request_fingerprint=request_fingerprint,
            ):
                _mark_idempotency_replay(idempotency_replay_state)
                return _idempotent_proposal_hit(
                    db,
                    user_id=user_id,
                    proposal=existing,
                )
            raise _idempotency_conflict()
        _fence_current_goal_provenance(
            db,
            user_id=user_id,
            goal=goal,
        )
        if before_persist is not None:
            before_persist(db)
        active_plan = _active_plan(db, user_id=user_id, for_update=True)
        if active_plan is not None:
            _archive_expired_draft(
                db,
                user_id=user_id,
                adaptive_plan=active_plan,
                now=datetime.utcnow(),
            )
        if (
            active_plan is not None
            and active_plan.lifecycle == "active"
            and active_plan.active_proposal_id is None
        ):
            plan_version = _sync_plan_version(
                db,
                user_id=user_id,
                adaptive_plan=active_plan,
            )
            goal_snapshot = AdaptivePlanGoalSnapshot(
                user_id=user_id,
                version=_next_proposal_version(db, adaptive_plan_id=active_plan.id),
                **goal,
            )
            db.add(goal_snapshot)
            db.flush()
            proposal = PlanProposal(
                user_id=user_id,
                adaptive_plan_id=active_plan.id,
                goal_snapshot_id=goal_snapshot.id,
                discipline=discipline,
                version=goal_snapshot.version,
                state="draft",
                origin=payload.origin,
                actor_type=payload.actor_type,
                actor_id=payload.actor_id,
                base_plan_version=plan_version,
                policy_version=payload.policy_version,
                model_version=payload.model_version,
                science_version=payload.science_version,
                assumptions=_json_list(payload.assumptions),
                unknowns=_json_list(payload.unknowns),
                warnings=_json_list(payload.warnings),
                alternatives=_json_list(payload.alternatives),
                expires_at=_utc_naive(payload.expires_at),
                idempotency_key=payload.idempotency_key,
                idempotency_fingerprint=request_fingerprint,
                workout_snapshot=workouts,
            )
            db.add(proposal)
            db.flush()
            active_plan.active_proposal_id = proposal.id
            if on_created is not None:
                on_created(db, proposal)
            db.commit()
            return _proposal_to_dict(db, proposal)
        if (
            active_plan is not None
            and active_plan.lifecycle in _ACTIVE_PLAN_STATES
        ):
            raise AdaptivePlanError(
                409,
                "ADAPTIVE_PLAN_ACTIVE_EXISTS",
                "An active adaptive plan already owns this athlete's plan lane.",
            )
        goal_snapshot = AdaptivePlanGoalSnapshot(user_id=user_id, **goal)
        db.add(goal_snapshot)
        db.flush()
        adaptive_plan = AdaptivePlan(
            user_id=user_id,
            goal_snapshot_id=goal_snapshot.id,
            discipline=discipline,
            lifecycle="draft",
            version=_canonical_plan_version(db, user_id=user_id),
        )
        db.add(adaptive_plan)
        db.flush()
        proposal = PlanProposal(
            user_id=user_id,
            adaptive_plan_id=adaptive_plan.id,
            goal_snapshot_id=goal_snapshot.id,
            discipline=discipline,
            version=1,
            state="draft",
            origin=payload.origin,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            base_plan_version=adaptive_plan.version,
            policy_version=payload.policy_version,
            model_version=payload.model_version,
            science_version=payload.science_version,
            assumptions=_json_list(payload.assumptions),
            unknowns=_json_list(payload.unknowns),
            warnings=_json_list(payload.warnings),
            alternatives=_json_list(payload.alternatives),
            expires_at=_utc_naive(payload.expires_at),
            idempotency_key=payload.idempotency_key,
            idempotency_fingerprint=request_fingerprint,
            workout_snapshot=workouts,
        )
        db.add(proposal)
        db.flush()
        adaptive_plan.active_proposal_id = proposal.id
        if on_created is not None:
            on_created(db, proposal)
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_proposal_for_key(db, user_id=user_id, idempotency_key=payload.idempotency_key)
        if existing is not None:
            if _idempotency_matches_proposal(
                proposal=existing,
                request_fingerprint=request_fingerprint,
            ):
                _mark_idempotency_replay(idempotency_replay_state)
                return _idempotent_proposal_hit(db, user_id=user_id, proposal=existing)
            raise _idempotency_conflict()
        raise AdaptivePlanError(409, "ADAPTIVE_PLAN_CONFLICT", "Adaptive plan proposal could not be created.") from exc
    except Exception:
        db.rollback()
        raise
    return _proposal_to_dict(db, proposal)


def read_current_proposal(db: Session, *, user_id: str) -> dict[str, Any] | None:
    """Return the active proposal for the authenticated owner, if one exists."""
    plan = _active_plan(db, user_id=user_id)
    if plan is None or not plan.active_proposal_id:
        return None
    proposal = db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.id == plan.active_proposal_id,
        )
    ).scalar_one_or_none()
    if proposal is None:
        return None
    if proposal.state != "draft":
        return None
    if _proposal_expired(proposal, now=datetime.utcnow()):
        return None
    return _proposal_to_dict(db, proposal)


def read_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
) -> dict[str, Any] | None:
    """Return one owner-scoped immutable proposal in any lifecycle state."""
    proposal = db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.id == proposal_id,
        )
    ).scalar_one_or_none()
    return _proposal_to_dict(db, proposal) if proposal is not None else None


def create_successor_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    expected_version: int,
    payload: ProposalInput,
    current_date: date,
    before_persist: Callable[[Session], None] | None = None,
    idempotency_replay_state: MutableMapping[str, bool] | None = None,
    on_created: Callable[[Session, PlanProposal], None] | None = None,
    allow_policy_successor: bool = False,
    validated_policy_purpose: bool = False,
) -> dict[str, Any]:
    """Supersede a draft proposal with a new immutable edited version.

    ``before_persist`` runs under the owner-scoped plan write lock before the
    predecessor is read or a successor is staged.

    ``idempotency_replay_state`` lets a policy wrapper reconstruct its own
    persisted response when an in-flight exact retry is found under that lock.
    """
    goal = _validate_goal(payload.goal)
    _require_validated_policy_purpose(
        goal,
        validated_policy_purpose=validated_policy_purpose,
    )
    discipline = normalize_adaptive_plan_discipline(payload.discipline)
    workouts = _validate_workouts(
        payload.workouts,
        horizon_start=goal["horizon_start"],
        horizon_end=goal["horizon_end"],
        current_date=current_date,
    )
    request_fingerprint = _proposal_request_fingerprint(
        payload=payload,
        goal=goal,
        discipline=discipline,
        workouts=workouts,
        predecessor_proposal_id=proposal_id,
        predecessor_version=expected_version,
    )
    existing = _existing_proposal_for_key(
        db,
        user_id=user_id,
        idempotency_key=payload.idempotency_key,
    )
    if existing is not None:
        if _idempotency_matches_proposal(
            proposal=existing,
            request_fingerprint=request_fingerprint,
        ):
            _mark_idempotency_replay(idempotency_replay_state)
            return _idempotent_proposal_hit(db, user_id=user_id, proposal=existing)
        raise _idempotency_conflict()
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing = _existing_proposal_for_key(
            db,
            user_id=user_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            if _idempotency_matches_proposal(
                proposal=existing,
                request_fingerprint=request_fingerprint,
            ):
                _mark_idempotency_replay(idempotency_replay_state)
                return _idempotent_proposal_hit(
                    db,
                    user_id=user_id,
                    proposal=existing,
                )
            raise _idempotency_conflict()
        _fence_current_goal_provenance(
            db,
            user_id=user_id,
            goal=goal,
        )
        if before_persist is not None:
            before_persist(db)
        parent = db.execute(
            select(PlanProposal).where(
                PlanProposal.user_id == user_id,
                PlanProposal.id == proposal_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if parent is None:
            raise AdaptivePlanError(404, "PLAN_PROPOSAL_NOT_FOUND", "Plan proposal not found.")
        if parent.version != expected_version:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_STALE", "The proposal version is stale.", current_version=parent.version)
        if parent.state == "expired":
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        if _expire_proposal_if_needed(
            db,
            user_id=user_id,
            proposal=parent,
            now=datetime.utcnow(),
        ):
            db.commit()
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        if parent.state != "draft":
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_NOT_EDITABLE", "Only draft proposals can be edited.", state=parent.state)
        from analysis.road_10k_contract import ROAD_10K_POLICY_VERSION
        if (
            parent.policy_version in {
                "outdoor-5k-plan-generation-policy-v1",
                ROAD_10K_POLICY_VERSION,
            }
            and not allow_policy_successor
        ):
            raise AdaptivePlanError(
                409,
                (
                    "OUTDOOR_5K_PROPOSAL_REGENERATE_REQUIRED"
                    if parent.policy_version
                    == "outdoor-5k-plan-generation-policy-v1"
                    else "ROAD_10K_PROPOSAL_REGENERATE_REQUIRED"
                ),
                (
                    "Use the deterministic outdoor 5K regenerate endpoint for this proposal."
                    if parent.policy_version
                    == "outdoor-5k-plan-generation-policy-v1"
                    else "Use the deterministic road 10K regenerate endpoint for this proposal."
                ),
            )
        adaptive_plan = db.execute(
            select(AdaptivePlan).where(
                AdaptivePlan.user_id == user_id,
                AdaptivePlan.id == parent.adaptive_plan_id,
            ).with_for_update()
        ).scalar_one()
        plan_version = max(
            int(adaptive_plan.version or 0),
            _canonical_plan_version(db, user_id=user_id),
        )
        if plan_version != parent.base_plan_version:
            raise AdaptivePlanError(
                409,
                "ADAPTIVE_PLAN_VERSION_CONFLICT",
                "The adaptive plan changed after the proposal was loaded.",
                current_version=plan_version,
            )
        if adaptive_plan.active_proposal_id != parent.id:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_SUPERSEDED", "The proposal is no longer active.")
        parent_goal = db.execute(
            select(AdaptivePlanGoalSnapshot).where(
                AdaptivePlanGoalSnapshot.user_id == user_id,
                AdaptivePlanGoalSnapshot.id == parent.goal_snapshot_id,
            ).with_for_update()
        ).scalar_one()
        goal_snapshot = AdaptivePlanGoalSnapshot(user_id=user_id, version=parent.version + 1, **goal)
        db.add(goal_snapshot)
        db.flush()
        parent.state = "superseded"
        parent.decided_at = datetime.utcnow()
        parent_goal.state = "superseded"
        proposal = PlanProposal(
            user_id=user_id,
            adaptive_plan_id=adaptive_plan.id,
            goal_snapshot_id=goal_snapshot.id,
            discipline=discipline,
            version=parent.version + 1,
            state="draft",
            origin=payload.origin,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            base_plan_version=plan_version,
            supersedes_proposal_id=parent.id,
            policy_version=payload.policy_version,
            model_version=payload.model_version,
            science_version=payload.science_version,
            assumptions=_json_list(payload.assumptions),
            unknowns=_json_list(payload.unknowns),
            warnings=_json_list(payload.warnings),
            alternatives=_json_list(payload.alternatives),
            expires_at=_utc_naive(payload.expires_at),
            idempotency_key=payload.idempotency_key,
            idempotency_fingerprint=request_fingerprint,
            workout_snapshot=workouts,
        )
        db.add(proposal)
        db.flush()
        if adaptive_plan.lifecycle == "draft":
            adaptive_plan.goal_snapshot_id = goal_snapshot.id
            adaptive_plan.discipline = discipline
        adaptive_plan.active_proposal_id = proposal.id
        if on_created is not None:
            on_created(db, proposal)
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_proposal_for_key(db, user_id=user_id, idempotency_key=payload.idempotency_key)
        if existing is not None:
            if _idempotency_matches_proposal(
                proposal=existing,
                request_fingerprint=request_fingerprint,
            ):
                _mark_idempotency_replay(idempotency_replay_state)
                return _idempotent_proposal_hit(db, user_id=user_id, proposal=existing)
            raise _idempotency_conflict()
        raise AdaptivePlanError(409, "ADAPTIVE_PLAN_CONFLICT", "Adaptive plan proposal could not be edited.") from exc
    except Exception:
        db.rollback()
        raise
    return _proposal_to_dict(db, proposal)


def reject_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    expected_version: int,
    idempotency_key: str,
) -> dict[str, Any]:
    """Reject an exact draft proposal without touching canonical workouts."""
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        proposal = db.execute(
            select(PlanProposal).where(
                PlanProposal.user_id == user_id,
                PlanProposal.id == proposal_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if proposal is None:
            raise AdaptivePlanError(404, "PLAN_PROPOSAL_NOT_FOUND", "Plan proposal not found.")
        if proposal.state == "rejected" and proposal.decision_idempotency_key == idempotency_key:
            db.commit()
            return _proposal_to_dict(db, proposal)
        if proposal.state == "expired":
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        if proposal.state in _TERMINAL_PROPOSAL_STATES:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_DECIDED", "The proposal has already been decided.", state=proposal.state)
        if proposal.version != expected_version:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_STALE", "The proposal version is stale.", current_version=proposal.version)
        if _expire_proposal_if_needed(
            db,
            user_id=user_id,
            proposal=proposal,
            now=datetime.utcnow(),
        ):
            db.commit()
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        adaptive_plan = db.execute(
            select(AdaptivePlan).where(
                AdaptivePlan.user_id == user_id,
                AdaptivePlan.id == proposal.adaptive_plan_id,
            ).with_for_update()
        ).scalar_one()
        if adaptive_plan.active_proposal_id != proposal.id:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_SUPERSEDED", "The proposal is no longer active.")
        proposal.state = "rejected"
        proposal.decision_idempotency_key = idempotency_key
        proposal.decided_at = datetime.utcnow()
        adaptive_plan.active_proposal_id = None
        if adaptive_plan.lifecycle == "draft":
            adaptive_plan.lifecycle = "archived"
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _proposal_to_dict(db, proposal)


def keep_current_plan_after_goal_change(
    db: Session,
    *,
    user_id: str,
    adaptive_plan_id: str,
    expected_goal_revision: str,
    expected_goal_snapshot_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Keep adopted workouts while detaching them from a changed Goal."""
    operation = "keep_plan_after_goal_change"
    request_details = {
        "adaptive_plan_id": adaptive_plan_id,
        "expected_goal_revision": expected_goal_revision,
        "expected_goal_snapshot_id": expected_goal_snapshot_id,
    }
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing_revision = db.execute(
            select(PlanRevision).where(
                PlanRevision.user_id == user_id,
                PlanRevision.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing_revision is not None:
            details = existing_revision.details or {}
            if (
                existing_revision.operation != operation
                or details.get("request") != request_details
            ):
                raise AdaptivePlanError(
                    409,
                    "GOAL_PLAN_RECONCILIATION_IDEMPOTENCY_CONFLICT",
                    "This idempotency key was already used for another plan decision.",
                )
            response = details.get("response")
            if not isinstance(response, Mapping):
                raise AdaptivePlanError(
                    500,
                    "GOAL_PLAN_RECONCILIATION_AUDIT_MISSING",
                    "The saved plan decision is missing its audit response.",
                )
            db.commit()
            return {**dict(response), "status": "already_kept"}

        from analysis.config import load_config_from_db
        from api.plan_generation_capabilities import current_goal_reference

        config = load_config_from_db(user_id, db)
        current_goal = current_goal_reference(
            user_id=user_id,
            goal=dict(config.goal or {}),
        )
        if (
            current_goal is None
            or current_goal.revision != expected_goal_revision
        ):
            raise AdaptivePlanError(
                409,
                "GOAL_PLAN_RECONCILIATION_STALE",
                "The Goal changed after this plan decision was opened.",
                current_goal_revision=(
                    current_goal.revision
                    if current_goal is not None
                    else None
                ),
            )

        adaptive_plan = db.execute(
            select(AdaptivePlan).where(
                AdaptivePlan.user_id == user_id,
                AdaptivePlan.id == adaptive_plan_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if adaptive_plan is None:
            raise AdaptivePlanError(
                404,
                "ADAPTIVE_PLAN_NOT_FOUND",
                "The active plan was not found.",
            )
        if adaptive_plan.lifecycle != "active":
            raise AdaptivePlanError(
                409,
                "GOAL_PLAN_RECONCILIATION_NO_ACTIVE_PLAN",
                "Only an adopted active plan can be kept after a Goal change.",
                lifecycle=adaptive_plan.lifecycle,
            )
        if adaptive_plan.goal_snapshot_id != expected_goal_snapshot_id:
            raise AdaptivePlanError(
                409,
                "GOAL_PLAN_RECONCILIATION_STALE",
                "The plan purpose changed after this decision was opened.",
                current_goal_snapshot_id=adaptive_plan.goal_snapshot_id,
            )

        active_goal = db.execute(
            select(AdaptivePlanGoalSnapshot).where(
                AdaptivePlanGoalSnapshot.user_id == user_id,
                AdaptivePlanGoalSnapshot.id == adaptive_plan.goal_snapshot_id,
            ).with_for_update()
        ).scalar_one()
        active_goal_is_stale = (
            active_goal.purpose_source == "current_goal"
            and (
                active_goal.source_goal_id != current_goal.goal_id
                or active_goal.source_goal_revision != current_goal.revision
            )
        )
        if not active_goal_is_stale:
            raise AdaptivePlanError(
                409,
                "GOAL_PLAN_RECONCILIATION_STALE",
                "This plan no longer needs the saved Goal-change decision.",
            )

        active_proposal: PlanProposal | None = None
        proposal_goal: AdaptivePlanGoalSnapshot | None = None
        now = datetime.utcnow()
        if adaptive_plan.active_proposal_id is not None:
            active_proposal = db.execute(
                select(PlanProposal).where(
                    PlanProposal.user_id == user_id,
                    PlanProposal.id == adaptive_plan.active_proposal_id,
                ).with_for_update()
            ).scalar_one_or_none()
            if active_proposal is not None:
                if active_proposal.state != "draft":
                    raise AdaptivePlanError(
                        409,
                        "GOAL_PLAN_RECONCILIATION_STALE",
                        "The plan proposal changed after this decision was opened.",
                    )
                if _proposal_expired(active_proposal, now=now):
                    active_proposal.state = "expired"
                    active_proposal.decided_at = now
                    adaptive_plan.active_proposal_id = None
                    active_proposal = None
                else:
                    proposal_goal = db.execute(
                        select(AdaptivePlanGoalSnapshot).where(
                            AdaptivePlanGoalSnapshot.user_id == user_id,
                            AdaptivePlanGoalSnapshot.id
                            == active_proposal.goal_snapshot_id,
                        ).with_for_update()
                    ).scalar_one()
                    proposal_goal_is_stale = (
                        proposal_goal.purpose_source == "current_goal"
                        and (
                            proposal_goal.source_goal_id
                            != current_goal.goal_id
                            or proposal_goal.source_goal_revision
                            != current_goal.revision
                        )
                    )
                    if not proposal_goal_is_stale:
                        raise AdaptivePlanError(
                            409,
                            "GOAL_PLAN_RECONCILIATION_STALE",
                            "A newer plan proposal already owns the current Goal.",
                        )

        detached_goal = _validate_goal({
            "goal_kind": active_goal.goal_kind,
            "target": dict(active_goal.target or {}),
            "horizon_start": active_goal.horizon_start,
            "horizon_end": active_goal.horizon_end,
            "purpose_source": "capability",
            "source_goal_id": None,
            "source_goal_revision": None,
        })
        detached_snapshot = AdaptivePlanGoalSnapshot(
            user_id=user_id,
            version=active_goal.version + 1,
            state="active",
            acknowledged_at=now,
            **detached_goal,
        )
        db.add(detached_snapshot)
        db.flush()

        active_goal.state = "superseded"
        adaptive_plan.goal_snapshot_id = detached_snapshot.id
        rejected_proposal_id: str | None = None
        if active_proposal is not None:
            rejected_proposal_id = active_proposal.id
            active_proposal.state = "rejected"
            active_proposal.decision_idempotency_key = idempotency_key
            active_proposal.decided_at = now
            adaptive_plan.active_proposal_id = None
            if proposal_goal is not None:
                proposal_goal.state = "superseded"

        plan_rows = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.adaptive_plan_id == adaptive_plan.id,
            )
            .order_by(TrainingPlan.date, TrainingPlan.id)
        ).scalars().all()
        response = {
            "status": "kept",
            "adaptive_plan_id": adaptive_plan.id,
            "goal_snapshot_id": detached_snapshot.id,
            "link_status": "independent",
            "rejected_proposal_id": rejected_proposal_id,
        }
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation=operation,
            actor_type="user",
            actor_id=user_id,
            origin="goal_plan_reconciliation",
            before=plan_rows,
            after=plan_rows,
            details={
                "request": request_details,
                "previous_goal_snapshot_id": active_goal.id,
                "response": response,
            },
            idempotency_key=idempotency_key,
        )
        response["revision_id"] = revision.id
        revision.details = {
            **dict(revision.details or {}),
            "response": response,
        }
        bump_revisions(db, user_id, ["plans"])
        db.commit()
        return response
    except AdaptivePlanError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise AdaptivePlanError(
            409,
            "GOAL_PLAN_RECONCILIATION_CONFLICT",
            "The plan changed while saving this Goal decision.",
        ) from exc
    except Exception:
        db.rollback()
        raise


def _plans_from_snapshot(
    user_id: str,
    adaptive_plan_id: str,
    proposal: PlanProposal,
    workouts: Sequence[Mapping[str, Any]],
) -> list[TrainingPlan]:
    rows: list[TrainingPlan] = []
    for workout in workouts:
        rows.append(
            TrainingPlan(
                user_id=user_id,
                adaptive_plan_id=adaptive_plan_id,
                canonical_id=str(workout["canonical_id"]),
                date=date.fromisoformat(str(workout["date"])),
                activity_type=str(workout.get("activity_type") or ""),
                workout_type=str(workout["workout_type"]),
                planned_duration_min=workout.get("planned_duration_min"),
                planned_distance_km=workout.get("planned_distance_km"),
                target_power_min=workout.get("target_power_min"),
                target_power_max=workout.get("target_power_max"),
                target_hr_min=workout.get("target_hr_min"),
                target_hr_max=workout.get("target_hr_max"),
                target_pace_min=workout.get("target_pace_min"),
                target_pace_max=workout.get("target_pace_max"),
                workout_description=workout.get("workout_description") or "",
                workout_structure_version=str(
                    workout.get("workout_structure_version") or ""
                )
                or None,
                workout_structure=workout.get("workout_structure"),
                source=PRAXYS_PLAN_WRITE_SOURCE,
                workout_origin="proposal",
                meta={
                    "proposal_id": proposal.id,
                    "policy_version": proposal.policy_version,
                    "generator_version": proposal.model_version,
                },
            )
        )
    return rows


def adopt_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    expected_proposal_version: int,
    expected_plan_version: int,
    idempotency_key: str,
    current_date: date,
) -> dict[str, Any]:
    """Atomically adopt an exact proposal into the canonical plan lane."""
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        proposal = db.execute(
            select(PlanProposal).where(
                PlanProposal.user_id == user_id,
                PlanProposal.id == proposal_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if proposal is None:
            raise AdaptivePlanError(404, "PLAN_PROPOSAL_NOT_FOUND", "Plan proposal not found.")
        if proposal.state == "adopted":
            if proposal.decision_idempotency_key != idempotency_key:
                raise AdaptivePlanError(409, "PLAN_PROPOSAL_ALREADY_ADOPTED", "The proposal was adopted with a different idempotency key.")
            revision = db.execute(
                select(PlanRevision).where(
                    PlanRevision.user_id == user_id,
                    PlanRevision.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if revision is None:
                raise AdaptivePlanError(
                    500,
                    "ADAPTIVE_PLAN_ADOPTION_REVISION_MISSING",
                    "The adopted proposal is missing its canonical revision.",
                )
            proposal_snapshot = (revision.details or {}).get(
                "proposal_snapshot"
            )
            if not isinstance(proposal_snapshot, Mapping):
                raise AdaptivePlanError(
                    500,
                    "ADAPTIVE_PLAN_ADOPTION_SNAPSHOT_MISSING",
                    "The adopted proposal is missing its immutable response snapshot.",
                )
            proposal_snapshot = _proposal_snapshot_for_replay(
                proposal_snapshot
            )
            db.commit()
            return {
                "status": "already_adopted",
                "proposal": proposal_snapshot,
                "revision_id": revision.id,
                "workouts": revision.after_snapshot or [],
            }
        if proposal.state == "expired":
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        if proposal.state != "draft":
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_NOT_ADOPTABLE", "Only active draft proposals can be adopted.", state=proposal.state)
        if proposal.version != expected_proposal_version:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_STALE", "The proposal version is stale.", current_version=proposal.version)
        adaptive_plan = db.execute(
            select(AdaptivePlan).where(
                AdaptivePlan.user_id == user_id,
                AdaptivePlan.id == proposal.adaptive_plan_id,
            ).with_for_update()
        ).scalar_one()
        current_plan_version = max(
            int(adaptive_plan.version or 0),
            _canonical_plan_version(db, user_id=user_id),
        )
        if proposal.base_plan_version != expected_plan_version:
            raise AdaptivePlanError(
                409,
                "ADAPTIVE_PLAN_VERSION_CONFLICT",
                "The proposal was based on a different canonical plan version.",
                current_version=current_plan_version,
            )
        if current_plan_version != expected_plan_version:
            raise AdaptivePlanError(409, "ADAPTIVE_PLAN_VERSION_CONFLICT", "The adaptive plan changed after the proposal was loaded.", current_version=current_plan_version)
        if adaptive_plan.active_proposal_id != proposal.id:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_SUPERSEDED", "The proposal is no longer active.")
        now = datetime.utcnow()
        if _proposal_expired(proposal, now=now):
            proposal.state = "expired"
            proposal.decided_at = now
            adaptive_plan.active_proposal_id = None
            if adaptive_plan.lifecycle == "draft":
                adaptive_plan.lifecycle = "archived"
            db.commit()
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        goal = db.execute(
            select(AdaptivePlanGoalSnapshot).where(
                AdaptivePlanGoalSnapshot.user_id == user_id,
                AdaptivePlanGoalSnapshot.id == proposal.goal_snapshot_id,
            ).with_for_update()
        ).scalar_one()
        _fence_current_goal_provenance(
            db,
            user_id=user_id,
            goal={
                "purpose_source": goal.purpose_source,
                "source_goal_id": goal.source_goal_id,
                "source_goal_revision": goal.source_goal_revision,
                "goal_kind": goal.goal_kind,
                "target": goal.target,
            },
        )
        from analysis.road_10k_contract import ROAD_10K_POLICY_VERSION
        if proposal.policy_version == "outdoor-5k-plan-generation-policy-v1":
            # This import stays local to keep the generic immutable-proposal
            # foundation independent of the policy-specific data orchestration.
            # The policy service reruns the #665 current-baseline boundary and
            # exact deterministic source revision before canonical mutation.
            from api.outdoor_5k_plan_generation import (
                validate_outdoor_5k_proposal_adoption,
            )

            validate_outdoor_5k_proposal_adoption(
                db,
                user_id=user_id,
                proposal=proposal,
            )
        elif proposal.policy_version == ROAD_10K_POLICY_VERSION:
            from api.road_10k_plan_generation import (
                validate_road_10k_proposal_adoption,
            )

            validate_road_10k_proposal_adoption(
                db,
                user_id=user_id,
                proposal=proposal,
            )
        active_goal = db.execute(
            select(AdaptivePlanGoalSnapshot).where(
                AdaptivePlanGoalSnapshot.user_id == user_id,
                AdaptivePlanGoalSnapshot.id == adaptive_plan.goal_snapshot_id,
            ).with_for_update()
        ).scalar_one()
        workouts = _validate_workouts(
            proposal.workout_snapshot or [],
            horizon_start=goal.horizon_start,
            horizon_end=goal.horizon_end,
            current_date=current_date,
        )
        rows = _plans_from_snapshot(
            user_id,
            adaptive_plan.id,
            proposal,
            workouts,
        )
        existing_query = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date >= current_date,
        )
        before_rows = existing_query.order_by(TrainingPlan.date, TrainingPlan.id).all()
        before = [plan_snapshot(row) for row in before_rows]
        for row in before_rows:
            db.expunge(row)
        existing_query.delete(synchronize_session=False)
        for row in rows:
            db.add(row)
        db.flush()
        adaptive_plan.discipline = proposal.discipline
        adaptive_plan.version = current_plan_version + 1
        adaptive_plan.lifecycle = "active"
        adaptive_plan.active_proposal_id = None
        if active_goal.id != goal.id and active_goal.state == "active":
            active_goal.state = "superseded"
        adaptive_plan.goal_snapshot_id = goal.id
        goal.state = "active"
        goal.acknowledged_at = now
        proposal.state = "adopted"
        proposal.decision_idempotency_key = idempotency_key
        proposal.decided_at = now
        proposal_snapshot = _proposal_to_dict(db, proposal)
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="adopt_proposal",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.proposals.adopt",
            before=before,
            after=rows,
            details={
                "adaptive_plan_id": adaptive_plan.id,
                "proposal_id": proposal.id,
                "proposal_version": proposal.version,
                "goal_snapshot_id": goal.id,
                "resulting_plan_version": adaptive_plan.version,
                "proposal_snapshot": proposal_snapshot,
            },
            idempotency_key=idempotency_key,
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise AdaptivePlanError(409, "ADAPTIVE_PLAN_ADOPTION_CONFLICT", "The proposal could not be adopted without conflicting canonical writes.") from exc
    except Exception:
        db.rollback()
        raise
    return {
        "status": "adopted",
        "proposal": proposal_snapshot,
        "revision_id": revision.id,
        "workouts": [plan_snapshot(row) for row in rows],
    }
