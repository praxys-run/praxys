"""AI-related endpoints: training context, plan upload, per-day upsert/delete."""
from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Optional, Self
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from analysis.config import (
    LEGACY_PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCES,
    PRAXYS_PLAN_WRITE_SOURCE,
    effective_athlete_date,
    load_config_from_db,
)
from analysis.metrics import is_rest_workout
from api.auth import get_data_user_id, require_write_access
from api.deps import get_dashboard_data
from db.cache_revision import bump_revisions
from db.models import TrainingPlan
from db.plan_ledger import (
    lock_plan_writes,
    plan_snapshot,
    record_plan_revision,
    workout_version,
)
from db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)
PlanDate = date


@router.get("/ai/context")
def get_ai_context(
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    """Return full training context for AI plan generation."""
    data = get_dashboard_data(user_id=user_id, db=db)
    from api.ai import _build_context_from_data
    return _build_context_from_data(data)


class PlanUpload(BaseModel):
    csv: str


class PlanWorkout(BaseModel):
    """Single-day workout payload for `PUT /api/plan/{plan_date}`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workout_type: str = Field(min_length=1, max_length=50)
    planned_duration_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=1440,
    )
    planned_distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        le=1000,
    )
    target_power_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=5000,
    )
    target_power_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=5000,
    )
    target_hr_min: Optional[float] = Field(default=None, ge=0, le=300)
    target_hr_max: Optional[float] = Field(default=None, ge=0, le=300)
    target_pace_min: Optional[str] = Field(default=None, max_length=20)
    target_pace_max: Optional[str] = Field(default=None, max_length=20)
    workout_description: Optional[str] = Field(default=None, max_length=4000)

class PlanWorkoutCreate(PlanWorkout):
    """Create one future Praxys-owned canonical workout."""

    date: PlanDate


class PlanWorkoutUpdate(BaseModel):
    """Optimistic update for one future canonical workout."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    date: Optional[PlanDate] = None
    workout_type: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    planned_duration_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=1440,
    )
    planned_distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        le=1000,
    )
    target_power_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=5000,
    )
    target_power_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=5000,
    )
    target_hr_min: Optional[float] = Field(default=None, ge=0, le=300)
    target_hr_max: Optional[float] = Field(default=None, ge=0, le=300)
    target_pace_min: Optional[str] = Field(default=None, max_length=20)
    target_pace_max: Optional[str] = Field(default=None, max_length=20)
    workout_description: Optional[str] = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        """Reject explicit nulls for required workout fields."""
        changed = self.model_fields_set - {"expected_version"}
        if "date" in changed and self.date is None:
            raise ValueError("date cannot be null")
        if "workout_type" in changed and self.workout_type is None:
            raise ValueError("workout_type cannot be null")
        return self


_MUTABLE_WORKOUT_FIELDS = (
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


def _delivery_unavailable(reason: str) -> dict:
    """Return a stable post-commit delivery result when no run is available."""
    return {
        "status": "unavailable",
        "target": None,
        "reason": reason,
        "items": [],
    }


def _current_athlete_date(db: Session, user_id: str) -> date:
    """Resolve the plan-history boundary in the athlete's timezone."""
    return effective_athlete_date(load_config_from_db(user_id, db))


def _row_to_response(
    plan: TrainingPlan,
    *,
    current_date: date,
    status: str | None = None,
    revision_id: str | None = None,
    delivery: dict | None = None,
) -> dict:
    response = {
        "id": plan.id,
        "canonical_id": plan.canonical_id,
        "date": plan.date.isoformat() if plan.date else None,
        "workout_type": plan.workout_type or "",
        "planned_duration_min": plan.planned_duration_min,
        "planned_distance_km": plan.planned_distance_km,
        "target_power_min": plan.target_power_min,
        "target_power_max": plan.target_power_max,
        "target_hr_min": plan.target_hr_min,
        "target_hr_max": plan.target_hr_max,
        "target_pace_min": plan.target_pace_min,
        "target_pace_max": plan.target_pace_max,
        "workout_description": plan.workout_description or "",
        # Deprecated compatibility value for older cached clients.
        "source": LEGACY_PRAXYS_PLAN_SOURCE,
        "owner": PRAXYS_PLAN_SOURCE,
        "origin": plan.workout_origin,
        "workout_version": workout_version(plan_snapshot(plan)),
        "editable": bool(plan.date and plan.date >= current_date),
    }
    if status is not None:
        response["status"] = status
    if revision_id is not None:
        response["revision_id"] = revision_id
    if delivery is not None:
        response["delivery"] = delivery
    return response


def _mutation_error(code: str, message: str, **details: object) -> dict:
    """Build a stable machine-readable FastAPI error detail."""
    return {"code": code, "message": message, **details}


def _require_mutable_date(workout_date: date, current_date: date) -> None:
    """Keep completed plan history immutable from authoring controls."""
    if workout_date < current_date:
        raise HTTPException(
            status_code=409,
            detail=_mutation_error(
                "PLAN_HISTORY_IMMUTABLE",
                "Completed and past workouts cannot be changed.",
                minimum_date=current_date.isoformat(),
            ),
        )


def _validate_plan_targets(plan: TrainingPlan) -> None:
    """Validate target ranges after a partial update is merged."""
    if (
        plan.target_power_min is not None
        and plan.target_power_max is not None
        and plan.target_power_min > plan.target_power_max
    ):
        raise HTTPException(
            status_code=400,
            detail=_mutation_error(
                "PLAN_TARGET_RANGE_INVALID",
                "Minimum target power cannot exceed maximum target power.",
            ),
        )
    if (
        plan.target_hr_min is not None
        and plan.target_hr_max is not None
        and plan.target_hr_min > plan.target_hr_max
    ):
        raise HTTPException(
            status_code=400,
            detail=_mutation_error(
                "PLAN_TARGET_RANGE_INVALID",
                "Minimum target heart rate cannot exceed maximum target heart rate.",
            ),
        )


def _normalize_rest_plan(plan: TrainingPlan) -> None:
    """Clear all load-bearing fields when a workout becomes rest."""
    if not is_rest_workout(plan.workout_type):
        return
    for field in (
        "planned_duration_min",
        "planned_distance_km",
        "target_power_min",
        "target_power_max",
        "target_hr_min",
        "target_hr_max",
        "target_pace_min",
        "target_pace_max",
        "start_time",
    ):
        setattr(plan, field, None)


def _apply_workout_fields(
    plan: TrainingPlan,
    fields: dict[str, object],
) -> None:
    """Apply explicitly supplied authoring fields to one canonical row."""
    for field in _MUTABLE_WORKOUT_FIELDS:
        if field not in fields:
            continue
        value = fields[field]
        if field == "workout_description":
            value = value or ""
        setattr(plan, field, value)


def _load_canonical_workout(
    db: Session,
    *,
    user_id: str,
    canonical_id: str,
) -> TrainingPlan:
    """Load and lock one user-owned Praxys workout without leaking others."""
    plan = (
        db.query(TrainingPlan)
        .filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.canonical_id == canonical_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail=_mutation_error(
                "PLAN_WORKOUT_NOT_FOUND",
                "Praxys workout not found.",
            ),
        )
    return plan


def _require_expected_version(
    plan: TrainingPlan,
    *,
    expected_version: str,
) -> str:
    """Fail closed when another writer changed the canonical workout."""
    current_version = workout_version(plan_snapshot(plan))
    if current_version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=_mutation_error(
                "PLAN_VERSION_CONFLICT",
                "This workout changed after it was loaded. Refresh and try again.",
                current_version=current_version,
            ),
        )
    return current_version


def _reuse_canonical_ids(
    plans: list[TrainingPlan],
    existing: list[TrainingPlan],
) -> None:
    """Preserve logical workout identity across replace-style plan writes."""
    existing_by_version: dict[str, list[TrainingPlan]] = defaultdict(list)
    plans_by_version: dict[str, list[TrainingPlan]] = defaultdict(list)
    for row in existing:
        if row.canonical_id:
            existing_by_version[workout_version(plan_snapshot(row))].append(row)
    for plan in plans:
        plans_by_version[workout_version(plan_snapshot(plan))].append(plan)

    matched_existing: set[str] = set()
    for version, version_plans in plans_by_version.items():
        version_existing = existing_by_version.get(version, [])
        if len(version_plans) == 1 and len(version_existing) == 1:
            row = version_existing[0]
            version_plans[0].canonical_id = row.canonical_id
            matched_existing.add(row.canonical_id)

    unmatched_existing_by_date: dict[date, list[TrainingPlan]] = defaultdict(list)
    unmatched_plans_by_date: dict[date, list[TrainingPlan]] = defaultdict(list)
    for row in existing:
        if row.canonical_id and row.canonical_id not in matched_existing:
            unmatched_existing_by_date[row.date].append(row)
    for plan in plans:
        if not plan.canonical_id:
            unmatched_plans_by_date[plan.date].append(plan)

    for workout_date, date_plans in unmatched_plans_by_date.items():
        date_existing = unmatched_existing_by_date.get(workout_date, [])
        if len(date_plans) == 1 and len(date_existing) == 1:
            date_plans[0].canonical_id = date_existing[0].canonical_id


def _assign_missing_canonical_ids(plans: list[TrainingPlan]) -> None:
    """Assign durable identities before revision snapshots are recorded."""
    for plan in plans:
        if not plan.canonical_id:
            plan.canonical_id = str(uuid4())


def _trigger_managed_delivery(user_id: str, *, trigger: str) -> dict:
    """Run the post-commit delivery hook without changing mutation success."""
    try:
        from api.plan_delivery.rolling import trigger_managed_plan_delivery

        result = trigger_managed_plan_delivery(user_id, trigger=trigger)
    except Exception:
        logger.exception(
            "Post-commit managed delivery hook failed user=%s trigger=%s",
            user_id,
            trigger,
        )
        return _delivery_unavailable("delivery_trigger_failed")
    if result is None:
        return _delivery_unavailable("delivery_result_unavailable")
    if is_dataclass(result):
        result = asdict(result)
    if not isinstance(result, dict):
        return _delivery_unavailable("delivery_result_invalid")
    return {
        "status": result.get("status"),
        "target": result.get("target"),
        "reason": result.get("reason"),
        "items": result.get("items") or [],
    }


def _parse_csv_row(row: dict, row_index: int) -> dict:
    """Parse one CSV dict-row into TrainingPlan kwargs (without user_id)."""
    try:
        d_raw = row.get("date", "")
        d = datetime.strptime(d_raw, "%Y-%m-%d").date() if d_raw else None
        return {
            "date": d,
            "workout_type": row.get("workout_type", ""),
            "planned_duration_min": float(row["planned_duration_min"])
                if row.get("planned_duration_min") else None,
            "planned_distance_km": float(row["planned_distance_km"])
                if row.get("planned_distance_km") else None,
            "target_power_min": float(row["target_power_min"])
                if row.get("target_power_min") else None,
            "target_power_max": float(row["target_power_max"])
                if row.get("target_power_max") else None,
            "workout_description": row.get("workout_description", ""),
        }
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid data in row {row_index + 1}: {e}")


@router.post("/plan/upload")
def upload_plan(
    payload: PlanUpload,
    mode: str = Query("replace", pattern="^(replace|merge)$"),
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Upload a Praxys-generated training plan as CSV text.

    `mode=replace` (default, backwards-compatible): delete every future Praxys
    plan row for the user, then insert the payload. Past rows are preserved.

    `mode=merge`: upsert the Praxys-owned dates present in the payload while
    leaving other past and future canonical rows alone.
    """
    current_date = _current_athlete_date(db, user_id)
    reader = csv.DictReader(io.StringIO(payload.csv))
    rows = list(reader)

    if not rows:
        raise HTTPException(status_code=400, detail="No rows in CSV")

    parsed_rows = []
    for i, row in enumerate(rows):
        kwargs = _parse_csv_row(row, i)
        parsed_date = kwargs.get("date")
        if not isinstance(parsed_date, date):
            raise HTTPException(400, f"Missing date in row {i + 1}")
        _require_mutable_date(parsed_date, current_date)
        plan = TrainingPlan(
            user_id=user_id,
            source=PRAXYS_PLAN_WRITE_SOURCE,
            workout_origin="generated",
            meta={"uploaded_at": datetime.utcnow().isoformat()},
            **kwargs,
        )
        _normalize_rest_plan(plan)
        parsed_rows.append(plan)

    target_dates = {p.date for p in parsed_rows if p.date is not None}
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        if mode == "replace":
            affected = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                TrainingPlan.date >= current_date,
            )
        else:
            affected = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                TrainingPlan.date.in_(target_dates),
            )
        before_rows = affected.order_by(TrainingPlan.date, TrainingPlan.id).all()
        before = [plan_snapshot(row) for row in before_rows]
        _reuse_canonical_ids(parsed_rows, before_rows)
        _assign_missing_canonical_ids(parsed_rows)
        for row in before_rows:
            db.expunge(row)
        affected.delete(synchronize_session=False)

        for plan in parsed_rows:
            db.add(plan)

        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="upload",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.upload",
            before=before,
            after=parsed_rows,
            details={"mode": mode, "rows": len(parsed_rows)},
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        raise

    delivery = _trigger_managed_delivery(user_id, trigger="plan_upload")
    return {
        "status": "saved",
        "rows": len(parsed_rows),
        "mode": mode,
        "revision_id": revision.id,
        "delivery": delivery,
    }


@router.put("/plan/{plan_date}")
def upsert_plan_day(
    plan_date: str,
    workout: PlanWorkout,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Upsert one manually authored Praxys workout for the given date.

    Replaces any existing Praxys rows for `(user, date)` with one new row from
    the payload. Other dates are untouched. Use this for partial edits —
    e.g. shifting a single workout — instead of round-tripping the whole
    future plan via /plan/upload.
    """
    current_date = _current_athlete_date(db, user_id)
    try:
        d = datetime.strptime(plan_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    _require_mutable_date(d, current_date)

    plan = TrainingPlan(
        user_id=user_id,
        date=d,
        workout_type=workout.workout_type,
        planned_duration_min=workout.planned_duration_min,
        planned_distance_km=workout.planned_distance_km,
        target_power_min=workout.target_power_min,
        target_power_max=workout.target_power_max,
        target_hr_min=workout.target_hr_min,
        target_hr_max=workout.target_hr_max,
        target_pace_min=workout.target_pace_min,
        target_pace_max=workout.target_pace_max,
        workout_description=workout.workout_description or "",
        source=PRAXYS_PLAN_WRITE_SOURCE,
        workout_origin="manual",
        meta={"uploaded_at": datetime.utcnow().isoformat()},
    )
    _normalize_rest_plan(plan)
    _validate_plan_targets(plan)
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date == d,
        )
        before_rows = existing.order_by(TrainingPlan.id).all()
        before = [plan_snapshot(row) for row in before_rows]
        _reuse_canonical_ids([plan], before_rows)
        _assign_missing_canonical_ids([plan])
        for row in before_rows:
            db.expunge(row)
        existing.delete(synchronize_session=False)
        db.add(plan)
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="upsert",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.upsert",
            before=before,
            after=[plan],
            details={"date": plan_date},
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(plan)
    delivery = _trigger_managed_delivery(user_id, trigger="plan_upsert")
    return _row_to_response(
        plan,
        current_date=current_date,
        status="updated" if before else "created",
        revision_id=revision.id,
        delivery=delivery,
    )


@router.delete("/plan/{plan_date}")
def delete_plan_day(
    plan_date: str,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Delete the Praxys plan workout(s) for the given date."""
    current_date = _current_athlete_date(db, user_id)
    try:
        d = datetime.strptime(plan_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    _require_mutable_date(d, current_date)

    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date == d,
        )
        before_rows = existing.order_by(TrainingPlan.id).all()
        before = [plan_snapshot(row) for row in before_rows]
        for row in before_rows:
            db.expunge(row)
        deleted = existing.delete(synchronize_session=False)
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="delete",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.delete",
            before=before,
            after=[],
            details={"date": plan_date, "rows": deleted},
        )
        if deleted:
            bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        raise
    delivery = None
    if deleted:
        delivery = _trigger_managed_delivery(user_id, trigger="plan_delete")
    return {
        "status": "deleted",
        "rows": deleted,
        "date": plan_date,
        "revision_id": revision.id,
        "delivery": delivery,
    }


@router.post("/plan/workouts", status_code=201)
def create_plan_workout(
    workout: PlanWorkoutCreate,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Create one future Praxys-owned canonical workout."""
    current_date = _current_athlete_date(db, user_id)
    _require_mutable_date(workout.date, current_date)
    fields = workout.model_dump()
    plan = TrainingPlan(
        user_id=user_id,
        source=PRAXYS_PLAN_WRITE_SOURCE,
        workout_origin="manual",
        meta={"authored_at": datetime.utcnow().isoformat()},
    )
    _apply_workout_fields(plan, fields)
    _normalize_rest_plan(plan)
    _validate_plan_targets(plan)
    _assign_missing_canonical_ids([plan])

    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        db.add(plan)
        db.flush()
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="create",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.workouts.create",
            before=[],
            after=[plan],
            details={"canonical_id": plan.canonical_id},
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(plan)
    delivery = _trigger_managed_delivery(
        user_id,
        trigger="plan_workout_create",
    )
    return _row_to_response(
        plan,
        current_date=current_date,
        status="created",
        revision_id=revision.id,
        delivery=delivery,
    )


@router.put("/plan/workouts/{canonical_id}")
def update_plan_workout(
    canonical_id: UUID,
    workout: PlanWorkoutUpdate,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Edit or reschedule one future canonical workout by durable UUID."""
    current_date = _current_athlete_date(db, user_id)
    canonical_id_str = str(canonical_id)
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        plan = _load_canonical_workout(
            db,
            user_id=user_id,
            canonical_id=canonical_id_str,
        )
        _require_mutable_date(plan.date, current_date)
        before = [plan_snapshot(plan)]
        current_version = _require_expected_version(
            plan,
            expected_version=workout.expected_version,
        )
        fields = workout.model_dump(exclude_unset=True)
        fields.pop("expected_version", None)
        next_date = fields.get("date")
        if isinstance(next_date, date):
            _require_mutable_date(next_date, current_date)
        original_date = plan.date
        _apply_workout_fields(plan, fields)
        if plan.date != original_date:
            # A date-only editor cannot preserve an instant after rescheduling.
            plan.start_time = None
        _normalize_rest_plan(plan)
        _validate_plan_targets(plan)
        plan.source = PRAXYS_PLAN_WRITE_SOURCE
        plan.workout_origin = "manual"
        plan.external_id = None
        plan.meta = {
            **dict(plan.meta or {}),
            "manual_updated_at": datetime.utcnow().isoformat(),
        }
        next_version = workout_version(plan_snapshot(plan))
        if next_version == current_version:
            raise HTTPException(
                status_code=400,
                detail=_mutation_error(
                    "PLAN_NO_CHANGES",
                    "No workout changes were provided.",
                ),
            )
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="update",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.workouts.update",
            before=before,
            after=[plan],
            details={
                "canonical_id": canonical_id_str,
                "expected_version": workout.expected_version,
                "resulting_version": next_version,
            },
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(plan)
    delivery = _trigger_managed_delivery(
        user_id,
        trigger="plan_workout_update",
    )
    return _row_to_response(
        plan,
        current_date=current_date,
        status="updated",
        revision_id=revision.id,
        delivery=delivery,
    )


@router.delete("/plan/workouts/{canonical_id}")
def delete_plan_workout(
    canonical_id: UUID,
    expected_version: str = Query(pattern=r"^[0-9a-f]{64}$"),
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Delete one future canonical workout by durable UUID."""
    current_date = _current_athlete_date(db, user_id)
    canonical_id_str = str(canonical_id)
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        plan = _load_canonical_workout(
            db,
            user_id=user_id,
            canonical_id=canonical_id_str,
        )
        _require_mutable_date(plan.date, current_date)
        before = plan_snapshot(plan)
        current_version = _require_expected_version(
            plan,
            expected_version=expected_version,
        )
        workout_date = plan.date.isoformat()
        db.delete(plan)
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="delete",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.workouts.delete",
            before=[before],
            after=[],
            details={
                "canonical_id": canonical_id_str,
                "expected_version": expected_version,
            },
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        raise

    delivery = _trigger_managed_delivery(
        user_id,
        trigger="plan_workout_delete",
    )
    return {
        "status": "deleted",
        "canonical_id": canonical_id_str,
        "date": workout_date,
        "workout_version": current_version,
        "revision_id": revision.id,
        "delivery": delivery,
    }
