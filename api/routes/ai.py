"""AI-related endpoints: training context, plan upload, per-day upsert/delete."""
from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Mapping, Optional, Self
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
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
from api.auth import (
    get_current_user_id,
    get_data_user_id,
    require_write_access,
)
from api.deps import get_dashboard_data
from api.plan_workout_structure import (
    PlanActivityType,
    StructuredWorkoutV1,
    WorkoutProviderCompatibility,
    WorkoutStructureVersion,
    inspect_workout_structure,
    normalize_activity_type,
    project_workout_provider_compatibility,
    synthesize_v1_structure_from_flat,
    validate_structured_workout,
)
from api.stryd_access import stryd_connection_enabled
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
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    """Return full training context for AI plan generation."""
    data = get_dashboard_data(
        user_id=user_id,
        db=db,
        include_stryd_plan=stryd_connection_enabled(
            db,
            user_id=viewer_user_id,
        ),
    )
    from api.ai import _build_context_from_data
    return _build_context_from_data(data, user_id=user_id, db=db)


class PlanUpload(BaseModel):
    csv: str


class PlanWorkout(BaseModel):
    """Single-day workout payload for `PUT /api/plan/{plan_date}`."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    activity_type: PlanActivityType | None = None
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
    workout_structure_version: WorkoutStructureVersion | None = None
    workout_structure: StructuredWorkoutV1 | None = None

    @model_validator(mode="after")
    def validate_structure_pair(self) -> Self:
        if (
            self.workout_structure is None
            and self.workout_structure_version is None
        ):
            return self
        if (
            self.workout_structure is None
            or self.workout_structure_version is None
        ):
            raise ValueError(
                "workout_structure and workout_structure_version must be provided together"
            )
        return self

class PlanWorkoutCreate(PlanWorkout):
    """Create one future Praxys-owned canonical workout."""

    date: PlanDate


class PlanWorkoutCompatibilityRequest(PlanWorkout):
    """Validate an unsaved workout against provider content capabilities."""

    date: PlanDate


class PlanWorkoutCompatibilityResponse(BaseModel):
    """Typed, content-only compatibility preview for the portable workout."""

    model_config = ConfigDict(extra="forbid")

    providers: list[WorkoutProviderCompatibility]


class PlanWorkoutUpdate(BaseModel):
    """Optimistic update for one future canonical workout."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    date: Optional[PlanDate] = None
    activity_type: PlanActivityType | None = None
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
    workout_structure_version: WorkoutStructureVersion | None = None
    workout_structure: StructuredWorkoutV1 | None = None

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        """Reject explicit nulls for required workout fields."""
        changed = self.model_fields_set - {"expected_version"}
        if "date" in changed and self.date is None:
            raise ValueError("date cannot be null")
        if "activity_type" in changed and self.activity_type is None:
            raise ValueError("activity_type cannot be null")
        if "workout_type" in changed and self.workout_type is None:
            raise ValueError("workout_type cannot be null")
        if (
            "workout_structure" in changed
            or "workout_structure_version" in changed
        ):
            if self.workout_structure is None or self.workout_structure_version is None:
                raise ValueError(
                    "workout_structure and workout_structure_version must be provided together"
                )
        return self

_MUTABLE_WORKOUT_FIELDS = (
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
    structure_inspection = inspect_workout_structure(
        workout_structure_version=plan.workout_structure_version,
        workout_structure=plan.workout_structure,
    )
    response = {
        "id": plan.id,
        "canonical_id": plan.canonical_id,
        "date": plan.date.isoformat() if plan.date else None,
        "activity_type": plan.activity_type,
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
        "workout_structure_version": plan.workout_structure_version,
        "workout_structure": plan.workout_structure,
        "workout_structure_status": structure_inspection.state,
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


_STRUCTURE_DRIVING_FIELDS = {
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
}

_COMPATIBILITY_PROJECTION_FIELDS = (
    "planned_duration_min",
    "planned_distance_km",
    "target_power_min",
    "target_power_max",
    "target_hr_min",
    "target_hr_max",
    "target_pace_min",
    "target_pace_max",
)


def _apply_flat_projections(
    plan: TrainingPlan,
    projections: dict[str, object],
) -> None:
    for field in _COMPATIBILITY_PROJECTION_FIELDS:
        setattr(plan, field, projections.get(field))


def _effective_activity_type(
    plan: TrainingPlan,
    *,
    previous_workout_type: str | None,
    previous_activity_type: str | None,
) -> str:
    workout_type = str(plan.workout_type or "")
    if is_rest_workout(workout_type):
        return "rest"
    candidate = str(plan.activity_type or "").strip() or None
    if candidate is None:
        candidate = (
            str(previous_activity_type or "").strip()
            or None
        )
    if (
        previous_workout_type is not None
        and is_rest_workout(previous_workout_type)
        and candidate == "rest"
    ):
        candidate = None
    return normalize_activity_type(workout_type, candidate)


def _apply_explicit_structure(
    plan: TrainingPlan,
    *,
    activity_type: str,
    workout_structure_version: str,
    workout_structure: StructuredWorkoutV1,
) -> None:
    normalized_activity_type, normalized_structure, projections = (
        validate_structured_workout(
            workout_type=str(plan.workout_type or ""),
            activity_type=activity_type,
            workout_structure_version=workout_structure_version,
            workout_structure=workout_structure,
        )
    )
    plan.activity_type = normalized_activity_type
    plan.workout_structure_version = workout_structure_version
    plan.workout_structure = normalized_structure
    _apply_flat_projections(plan, projections)


def _synthesize_structure(
    plan: TrainingPlan,
    *,
    activity_type: str,
) -> None:
    normalized_activity_type, version, structure_model = (
        synthesize_v1_structure_from_flat(
            workout_type=str(plan.workout_type or ""),
            activity_type=activity_type,
            planned_duration_min=plan.planned_duration_min,
            planned_distance_km=plan.planned_distance_km,
            target_power_min=plan.target_power_min,
            target_power_max=plan.target_power_max,
            target_hr_min=plan.target_hr_min,
            target_hr_max=plan.target_hr_max,
            target_pace_min=plan.target_pace_min,
            target_pace_max=plan.target_pace_max,
        )
    )
    _apply_explicit_structure(
        plan,
        activity_type=normalized_activity_type,
        workout_structure_version=version,
        workout_structure=structure_model,
    )


def _projection_values_match(
    field: str,
    supplied: object,
    projected: object,
) -> bool:
    if supplied is None or projected is None:
        return supplied is None and projected is None
    if field in {
        "planned_duration_min",
        "planned_distance_km",
        "target_power_min",
        "target_power_max",
        "target_hr_min",
        "target_hr_max",
    }:
        try:
            return abs(float(supplied) - float(projected)) <= 1e-6
        except (TypeError, ValueError):
            return False
    return str(supplied) == str(projected)


def _projection_conflicts(
    supplied_fields: Mapping[str, object],
    projections: Mapping[str, object],
) -> list[str]:
    return sorted(
        field
        for field in _COMPATIBILITY_PROJECTION_FIELDS
        if field in supplied_fields
        and not _projection_values_match(
            field,
            supplied_fields.get(field),
            projections.get(field),
        )
    )


def _raise_structure_error(
    *,
    code: str,
    message: str,
    status_code: int,
    **details: object,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_mutation_error(code, message, **details),
    )


def _ensure_authoritative_structure_unchecked(
    plan: TrainingPlan,
    *,
    supplied_fields: Mapping[str, object],
    previous_snapshot: Mapping[str, object] | None,
) -> None:
    requested = inspect_workout_structure(
        workout_structure_version=supplied_fields.get(
            "workout_structure_version"
        ),
        workout_structure=supplied_fields.get("workout_structure"),
    )
    previous = inspect_workout_structure(
        workout_structure_version=(
            previous_snapshot.get("workout_structure_version")
            if previous_snapshot is not None
            else None
        ),
        workout_structure=(
            previous_snapshot.get("workout_structure")
            if previous_snapshot is not None
            else None
        ),
    )
    previous_workout_type = (
        str(previous_snapshot.get("workout_type") or "")
        if previous_snapshot is not None
        else None
    )
    previous_activity_type = (
        str(previous_snapshot.get("activity_type") or "")
        if previous_snapshot is not None
        else None
    )
    current_workout_type = str(plan.workout_type or "")
    activity_type = _effective_activity_type(
        plan,
        previous_workout_type=previous_workout_type,
        previous_activity_type=previous_activity_type,
    )

    if requested.state != "absent":
        if requested.state != "supported" or requested.structure is None:
            _raise_structure_error(
                code="PLAN_WORKOUT_STRUCTURE_INVALID",
                message=(
                    "Workout structure and version must form a supported "
                    "authoritative pair."
                ),
                status_code=422,
            )
        _apply_explicit_structure(
            plan,
            activity_type=activity_type,
            workout_structure_version="v1",
            workout_structure=requested.structure,
        )
        return

    if previous_snapshot is None:
        # New legacy flat CRUD and CSV writes remain genuinely flat.
        plan.activity_type = activity_type
        plan.workout_structure_version = None
        plan.workout_structure = None
        return

    previous_rest = is_rest_workout(previous_workout_type or "")
    current_rest = is_rest_workout(current_workout_type)
    if current_rest and not previous_rest:
        if previous.state == "absent":
            plan.activity_type = "rest"
            plan.workout_structure_version = None
            plan.workout_structure = None
        else:
            _apply_explicit_structure(
                plan,
                activity_type="rest",
                workout_structure_version="v1",
                workout_structure=StructuredWorkoutV1(),
            )
        return

    if previous_rest and not current_rest:
        if previous.state == "supported":
            _synthesize_structure(
                plan,
                activity_type=activity_type,
            )
        elif previous.state == "absent":
            plan.activity_type = activity_type
            plan.workout_structure_version = None
            plan.workout_structure = None
        else:
            _raise_structure_error(
                code="PLAN_WORKOUT_STRUCTURE_UNSUPPORTED",
                message=(
                    "This workout structure must be replaced explicitly "
                    "before changing workout fields."
                ),
                status_code=409,
            )
        return

    if previous.state == "supported" and previous.structure is not None:
        normalized_activity, normalized_structure, projections = (
            validate_structured_workout(
                workout_type=current_workout_type,
                activity_type=activity_type,
                workout_structure_version="v1",
                workout_structure=previous.structure,
            )
        )
        conflicts = _projection_conflicts(supplied_fields, projections)
        if conflicts:
            _raise_structure_error(
                code="PLAN_STRUCTURE_PROJECTION_CONFLICT",
                message=(
                    "Flat workout fields cannot change an authoritative "
                    "workout structure."
                ),
                status_code=409,
                fields=conflicts,
            )
        plan.activity_type = normalized_activity
        plan.workout_structure_version = "v1"
        plan.workout_structure = normalized_structure
        _apply_flat_projections(plan, projections)
        return

    if previous.state == "absent":
        plan.activity_type = activity_type
        plan.workout_structure_version = None
        plan.workout_structure = None
        return

    if _STRUCTURE_DRIVING_FIELDS.intersection(supplied_fields):
        _raise_structure_error(
            code="PLAN_WORKOUT_STRUCTURE_UNSUPPORTED",
            message=(
                "This workout structure must be replaced explicitly before "
                "changing workout fields."
            ),
            status_code=409,
        )
    # Non-structural edits preserve future structure versions byte-for-byte.
    plan.workout_structure_version = previous_snapshot.get(
        "workout_structure_version"
    )
    plan.workout_structure = previous_snapshot.get("workout_structure")


def _ensure_authoritative_structure(
    plan: TrainingPlan,
    *,
    supplied_fields: Mapping[str, object],
    previous_snapshot: Mapping[str, object] | None,
) -> None:
    try:
        _ensure_authoritative_structure_unchecked(
            plan,
            supplied_fields=supplied_fields,
            previous_snapshot=previous_snapshot,
        )
    except HTTPException:
        raise
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=_mutation_error(
                "PLAN_WORKOUT_STRUCTURE_INVALID",
                "Workout fields cannot form a valid authoritative structure.",
            ),
        ) from exc


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
    def flat_signature(record: TrainingPlan) -> tuple[object, ...]:
        snapshot = plan_snapshot(record)
        return (
            snapshot.get("date"),
            snapshot.get("workout_type"),
            snapshot.get("planned_duration_min"),
            snapshot.get("planned_distance_km"),
            snapshot.get("target_power_min"),
            snapshot.get("target_power_max"),
            snapshot.get("target_hr_min"),
            snapshot.get("target_hr_max"),
            snapshot.get("target_pace_min"),
            snapshot.get("target_pace_max"),
            snapshot.get("workout_description"),
        )

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

    existing_by_flat_signature: dict[tuple[object, ...], list[TrainingPlan]] = defaultdict(list)
    plans_by_flat_signature: dict[tuple[object, ...], list[TrainingPlan]] = defaultdict(list)
    for row in existing:
        if row.canonical_id and row.canonical_id not in matched_existing:
            existing_by_flat_signature[flat_signature(row)].append(row)
    for plan in plans:
        if not plan.canonical_id:
            plans_by_flat_signature[flat_signature(plan)].append(plan)

    for signature, signature_plans in plans_by_flat_signature.items():
        signature_existing = existing_by_flat_signature.get(signature, [])
        if len(signature_plans) == 1 and len(signature_existing) == 1:
            row = signature_existing[0]
            signature_plans[0].canonical_id = row.canonical_id
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
        _ensure_authoritative_structure(
            plan,
            supplied_fields=kwargs,
            previous_snapshot=None,
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

    fields = workout.model_dump()
    plan = TrainingPlan(
        user_id=user_id,
        date=d,
        activity_type=workout.activity_type,
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
        _ensure_authoritative_structure(
            plan,
            supplied_fields=fields,
            previous_snapshot=(
                before[0] if len(before) == 1 else None
            ),
        )
        _normalize_rest_plan(plan)
        _validate_plan_targets(plan)
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


@router.post(
    "/plan/workouts/compatibility",
    response_model=PlanWorkoutCompatibilityResponse,
)
def preview_plan_workout_compatibility(
    workout: PlanWorkoutCompatibilityRequest,
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Preview lossless provider compatibility without saving or delivering.

    The endpoint intentionally has no database mutation, provider lookup, or
    credential access. It validates the same canonical payload shape accepted
    by workout CRUD, then returns content-only reasons that clients can
    localize before a delivery is ever requested.
    """
    del user_id
    fields = workout.model_dump()
    candidate = TrainingPlan(
        source=PRAXYS_PLAN_WRITE_SOURCE,
        workout_origin="manual",
    )
    _apply_workout_fields(candidate, fields)
    _ensure_authoritative_structure(
        candidate,
        supplied_fields=fields,
        previous_snapshot=None,
    )
    _normalize_rest_plan(candidate)
    _validate_plan_targets(candidate)
    providers = project_workout_provider_compatibility(
        activity_type=candidate.activity_type,
        workout_structure_version=candidate.workout_structure_version,
        workout_structure=candidate.workout_structure,
        planned_duration_min=candidate.planned_duration_min,
        planned_distance_km=candidate.planned_distance_km,
        target_power_min=candidate.target_power_min,
        target_power_max=candidate.target_power_max,
        target_hr_min=candidate.target_hr_min,
        target_hr_max=candidate.target_hr_max,
        target_pace_min=candidate.target_pace_min,
        target_pace_max=candidate.target_pace_max,
    )
    if not stryd_connection_enabled(db, user_id=viewer_user_id):
        providers = [
            provider
            for provider in providers
            if provider.get("target") != "stryd"
        ]
    return {
        "providers": providers,
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
    _ensure_authoritative_structure(
        plan,
        supplied_fields=fields,
        previous_snapshot=None,
    )
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
        _ensure_authoritative_structure(
            plan,
            supplied_fields=fields,
            previous_snapshot=before[0],
        )
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
