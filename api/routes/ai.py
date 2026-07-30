"""AI-related endpoints: training context, plan upload, per-day upsert/delete."""
import csv
import io
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

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

    workout_type: str
    planned_duration_min: Optional[float] = None
    planned_distance_km: Optional[float] = None
    target_power_min: Optional[float] = None
    target_power_max: Optional[float] = None
    workout_description: Optional[str] = None


def _row_to_response(plan: TrainingPlan) -> dict:
    return {
        "id": plan.id,
        "canonical_id": plan.canonical_id,
        "date": plan.date.isoformat() if plan.date else None,
        "workout_type": plan.workout_type,
        "planned_duration_min": plan.planned_duration_min,
        "planned_distance_km": plan.planned_distance_km,
        "target_power_min": plan.target_power_min,
        "target_power_max": plan.target_power_max,
        "workout_description": plan.workout_description,
        "source": plan.source,
    }


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


def _trigger_managed_delivery(user_id: str, *, trigger: str) -> None:
    """Run the post-commit delivery hook without changing mutation success."""
    try:
        from api.plan_delivery.rolling import trigger_managed_plan_delivery

        trigger_managed_plan_delivery(user_id, trigger=trigger)
    except Exception:
        logger.exception(
            "Post-commit managed delivery hook failed user=%s trigger=%s",
            user_id,
            trigger,
        )


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
    """Upload an AI-generated training plan as CSV text.

    `mode=replace` (default, backwards-compatible): delete every future AI
    plan row for the user, then insert the payload. Past rows are preserved.

    `mode=merge`: upsert by `(user, date, source='ai')` — only the dates
    present in the payload are touched; all other AI rows (past and future)
    are left alone. Use this when shifting or editing individual workouts
    without resending the whole plan window.
    """
    reader = csv.DictReader(io.StringIO(payload.csv))
    rows = list(reader)

    if not rows:
        return {"status": "error", "message": "No rows in CSV"}

    parsed_rows = []
    for i, row in enumerate(rows):
        kwargs = _parse_csv_row(row, i)
        parsed_rows.append(TrainingPlan(
            user_id=user_id,
            source="ai",
            meta={"uploaded_at": datetime.utcnow().isoformat()},
            **kwargs,
        ))

    target_dates = {p.date for p in parsed_rows if p.date is not None}
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        if mode == "replace":
            affected = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source == "ai",
                TrainingPlan.date >= date.today(),
            )
        else:
            affected = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source == "ai",
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

        record_plan_revision(
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

    _trigger_managed_delivery(user_id, trigger="plan_upload")
    return {"status": "saved", "rows": len(parsed_rows), "mode": mode}


@router.put("/plan/{plan_date}")
def upsert_plan_day(
    plan_date: str,
    workout: PlanWorkout,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Upsert a single AI plan workout for the given date (YYYY-MM-DD).

    Replaces any existing AI rows for `(user, date)` with one new row from
    the payload. Other dates are untouched. Use this for partial edits —
    e.g. shifting a single workout — instead of round-tripping the whole
    future plan via /plan/upload.
    """
    try:
        d = datetime.strptime(plan_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    plan = TrainingPlan(
        user_id=user_id,
        date=d,
        workout_type=workout.workout_type,
        planned_duration_min=workout.planned_duration_min,
        planned_distance_km=workout.planned_distance_km,
        target_power_min=workout.target_power_min,
        target_power_max=workout.target_power_max,
        workout_description=workout.workout_description or "",
        source="ai",
        meta={"uploaded_at": datetime.utcnow().isoformat()},
    )
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source == "ai",
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
        record_plan_revision(
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
    _trigger_managed_delivery(user_id, trigger="plan_upsert")
    return _row_to_response(plan)


@router.delete("/plan/{plan_date}")
def delete_plan_day(
    plan_date: str,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
):
    """Delete the AI plan workout(s) for the given date (YYYY-MM-DD)."""
    try:
        d = datetime.strptime(plan_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        existing = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source == "ai",
            TrainingPlan.date == d,
        )
        before_rows = existing.order_by(TrainingPlan.id).all()
        before = [plan_snapshot(row) for row in before_rows]
        for row in before_rows:
            db.expunge(row)
        deleted = existing.delete(synchronize_session=False)
        record_plan_revision(
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
    if deleted:
        _trigger_managed_delivery(user_id, trigger="plan_delete")
    return {"status": "deleted", "rows": deleted, "date": plan_date}
