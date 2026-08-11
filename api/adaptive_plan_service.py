"""Owner-scoped domain service for adaptive plan proposals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analysis.config import PRAXYS_PLAN_SOURCES, PRAXYS_PLAN_WRITE_SOURCE
from analysis.metrics import is_rest_workout
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
    snapshot = {
        "goal_kind": goal_kind,
        "target": dict(target),
        "horizon_start": horizon_start.isoformat(),
        "horizon_end": horizon_end.isoformat(),
    }
    return {
        "goal_kind": goal_kind,
        "target": dict(target),
        "horizon_start": horizon_start,
        "horizon_end": horizon_end,
        "snapshot": snapshot,
    }


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
        item = {
            "canonical_id": canonical_id,
            "date": date_key,
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
        }
        for pace_field in ("target_pace_min", "target_pace_max"):
            pace = item[pace_field]
            if pace is not None:
                item[pace_field] = str(pace).strip()[:20]
        if item["target_power_min"] is not None and item["target_power_max"] is not None and item["target_power_min"] > item["target_power_max"]:
            raise AdaptivePlanError(400, "PLAN_PROPOSAL_TARGET_RANGE_INVALID", "Minimum target power cannot exceed maximum target power.")
        if item["target_hr_min"] is not None and item["target_hr_max"] is not None and item["target_hr_min"] > item["target_hr_max"]:
            raise AdaptivePlanError(400, "PLAN_PROPOSAL_TARGET_RANGE_INVALID", "Minimum target heart rate cannot exceed maximum target heart rate.")
        if is_rest_workout(workout_type):
            for field in (
                "planned_duration_min",
                "planned_distance_km",
                "target_power_min",
                "target_power_max",
                "target_hr_min",
                "target_hr_max",
                "target_pace_min",
                "target_pace_max",
            ):
                item[field] = None
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
            "version": plan.version,
            "lifecycle": plan.lifecycle,
            "active_proposal_id": plan.active_proposal_id,
        },
        "goal": None if goal is None else {
            "id": goal.id,
            "version": goal.version,
            "state": goal.state,
            "goal_kind": goal.goal_kind,
            "target": goal.target or {},
            "horizon_start": goal.horizon_start.isoformat(),
            "horizon_end": goal.horizon_end.isoformat(),
            "acknowledged_at": goal.acknowledged_at.isoformat() if goal.acknowledged_at else None,
        },
    }


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
    if adaptive_plan.version == 0:
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
    if adaptive_plan.version == 0:
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
) -> dict[str, Any]:
    """Create the first immutable proposal for a new adaptive plan aggregate."""
    existing = _existing_proposal_for_key(db, user_id=user_id, idempotency_key=payload.idempotency_key)
    if existing is not None:
        return _idempotent_proposal_hit(db, user_id=user_id, proposal=existing)
    goal = _validate_goal(payload.goal)
    workouts = _validate_workouts(
        payload.workouts,
        horizon_start=goal["horizon_start"],
        horizon_end=goal["horizon_end"],
        current_date=current_date,
    )
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        active_plan = _active_plan(db, user_id=user_id, for_update=True)
        archived_expired = False
        if active_plan is not None:
            archived_expired = _archive_expired_draft(
                db,
                user_id=user_id,
                adaptive_plan=active_plan,
                now=datetime.utcnow(),
            )
        if active_plan is not None and not archived_expired:
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
            lifecycle="draft",
            version=0,
        )
        db.add(adaptive_plan)
        db.flush()
        proposal = PlanProposal(
            user_id=user_id,
            adaptive_plan_id=adaptive_plan.id,
            goal_snapshot_id=goal_snapshot.id,
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
            expires_at=payload.expires_at,
            idempotency_key=payload.idempotency_key,
            workout_snapshot=workouts,
        )
        db.add(proposal)
        db.flush()
        adaptive_plan.active_proposal_id = proposal.id
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_proposal_for_key(db, user_id=user_id, idempotency_key=payload.idempotency_key)
        if existing is not None:
            return _idempotent_proposal_hit(db, user_id=user_id, proposal=existing)
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


def create_successor_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    expected_version: int,
    payload: ProposalInput,
    current_date: date,
) -> dict[str, Any]:
    """Supersede a draft proposal with a new immutable edited version."""
    existing = _existing_proposal_for_key(db, user_id=user_id, idempotency_key=payload.idempotency_key)
    if existing is not None:
        return _proposal_to_dict(db, existing)
    goal = _validate_goal(payload.goal)
    workouts = _validate_workouts(
        payload.workouts,
        horizon_start=goal["horizon_start"],
        horizon_end=goal["horizon_end"],
        current_date=current_date,
    )
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
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
        adaptive_plan = db.execute(
            select(AdaptivePlan).where(
                AdaptivePlan.user_id == user_id,
                AdaptivePlan.id == parent.adaptive_plan_id,
            ).with_for_update()
        ).scalar_one()
        if adaptive_plan.active_proposal_id != parent.id:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_SUPERSEDED", "The proposal is no longer active.")
        goal_snapshot = AdaptivePlanGoalSnapshot(user_id=user_id, version=parent.version + 1, **goal)
        db.add(goal_snapshot)
        db.flush()
        parent.state = "superseded"
        parent.decided_at = datetime.utcnow()
        proposal = PlanProposal(
            user_id=user_id,
            adaptive_plan_id=adaptive_plan.id,
            goal_snapshot_id=goal_snapshot.id,
            version=parent.version + 1,
            state="draft",
            origin=payload.origin,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            base_plan_version=adaptive_plan.version,
            supersedes_proposal_id=parent.id,
            policy_version=payload.policy_version,
            model_version=payload.model_version,
            science_version=payload.science_version,
            assumptions=_json_list(payload.assumptions),
            unknowns=_json_list(payload.unknowns),
            warnings=_json_list(payload.warnings),
            alternatives=_json_list(payload.alternatives),
            expires_at=payload.expires_at,
            idempotency_key=payload.idempotency_key,
            workout_snapshot=workouts,
        )
        db.add(proposal)
        db.flush()
        adaptive_plan.goal_snapshot_id = goal_snapshot.id
        adaptive_plan.active_proposal_id = proposal.id
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        existing = _existing_proposal_for_key(db, user_id=user_id, idempotency_key=payload.idempotency_key)
        if existing is not None:
            return _proposal_to_dict(db, existing)
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
        if proposal.state in _TERMINAL_PROPOSAL_STATES:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_DECIDED", "The proposal has already been decided.", state=proposal.state)
        if proposal.version != expected_version:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_STALE", "The proposal version is stale.", current_version=proposal.version)
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
        if adaptive_plan.version == 0:
            adaptive_plan.lifecycle = "archived"
        db.commit()
    except AdaptivePlanError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _proposal_to_dict(db, proposal)


def _plans_from_snapshot(user_id: str, adaptive_plan_id: str, workouts: Sequence[Mapping[str, Any]]) -> list[TrainingPlan]:
    rows: list[TrainingPlan] = []
    for workout in workouts:
        rows.append(
            TrainingPlan(
                user_id=user_id,
                adaptive_plan_id=adaptive_plan_id,
                canonical_id=str(workout["canonical_id"]),
                date=date.fromisoformat(str(workout["date"])),
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
                source=PRAXYS_PLAN_WRITE_SOURCE,
                workout_origin="proposal",
                meta={"proposal_id": adaptive_plan_id},
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
            rows = db.execute(
                select(TrainingPlan).where(
                    TrainingPlan.user_id == user_id,
                    TrainingPlan.adaptive_plan_id == proposal.adaptive_plan_id,
                ).order_by(TrainingPlan.date, TrainingPlan.id)
            ).scalars().all()
            db.commit()
            return {
                "status": "already_adopted",
                "proposal": _proposal_to_dict(db, proposal),
                "revision_id": revision.id if revision else None,
                "workouts": [plan_snapshot(row) for row in rows],
            }
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
        if adaptive_plan.version != expected_plan_version:
            raise AdaptivePlanError(409, "ADAPTIVE_PLAN_VERSION_CONFLICT", "The adaptive plan changed after the proposal was loaded.", current_version=adaptive_plan.version)
        if adaptive_plan.active_proposal_id != proposal.id:
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_SUPERSEDED", "The proposal is no longer active.")
        now = datetime.utcnow()
        if _proposal_expired(proposal, now=now):
            proposal.state = "expired"
            proposal.decided_at = now
            adaptive_plan.active_proposal_id = None
            if adaptive_plan.version == 0:
                adaptive_plan.lifecycle = "archived"
            db.commit()
            raise AdaptivePlanError(409, "PLAN_PROPOSAL_EXPIRED", "The proposal has expired.")
        goal = db.execute(
            select(AdaptivePlanGoalSnapshot).where(
                AdaptivePlanGoalSnapshot.user_id == user_id,
                AdaptivePlanGoalSnapshot.id == proposal.goal_snapshot_id,
            ).with_for_update()
        ).scalar_one()
        workouts = _validate_workouts(
            proposal.workout_snapshot or [],
            horizon_start=goal.horizon_start,
            horizon_end=goal.horizon_end,
            current_date=current_date,
        )
        rows = _plans_from_snapshot(user_id, adaptive_plan.id, workouts)
        date_values = [date.fromisoformat(str(item["date"])) for item in workouts]
        existing_query = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date.in_(date_values),
        )
        before_rows = existing_query.order_by(TrainingPlan.date, TrainingPlan.id).all()
        before = [plan_snapshot(row) for row in before_rows]
        for row in before_rows:
            db.expunge(row)
        existing_query.delete(synchronize_session=False)
        for row in rows:
            db.add(row)
        db.flush()
        adaptive_plan.version += 1
        adaptive_plan.lifecycle = "active"
        adaptive_plan.active_proposal_id = None
        goal.state = "active"
        goal.acknowledged_at = now
        proposal.state = "adopted"
        proposal.decision_idempotency_key = idempotency_key
        proposal.decided_at = now
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
        "proposal": _proposal_to_dict(db, proposal),
        "revision_id": revision.id,
        "workouts": [plan_snapshot(row) for row in rows],
    }
