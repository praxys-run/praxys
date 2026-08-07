"""Privacy-safe self-service export of caller-owned training data."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from analysis.config import load_config_from_db
from api.views import utc_isoformat
from db.models import (
    Activity,
    ActivitySplit,
    FitnessData,
    RecoveryData,
    TrainingPlan,
)


_SENSITIVE_KEY_PARTS = frozenset({
    "credential",
    "token",
    "password",
    "secret",
    "encrypted",
    "wrapped",
    "authorization",
    "private_key",
})

_ACTIVITY_FIELDS = (
    "activity_id",
    "date",
    "activity_type",
    "distance_km",
    "duration_sec",
    "temperature_c",
    "relative_humidity_pct",
    "environment_source",
    "avg_power",
    "max_power",
    "avg_hr",
    "max_hr",
    "avg_pace_min_km",
    "avg_pace_sec_km",
    "elevation_gain_m",
    "avg_cadence",
    "training_effect",
    "rss",
    "trimp",
    "rtss",
    "cp_estimate",
    "load_score",
    "start_time",
    "source",
)
_ACTIVITY_SPLIT_FIELDS = (
    "activity_id",
    "split_num",
    "distance_km",
    "duration_sec",
    "avg_power",
    "power_source",
    "avg_hr",
    "max_hr",
    "avg_pace_min_km",
    "avg_pace_sec_km",
    "avg_cadence",
    "elevation_change_m",
)
_RECOVERY_FIELDS = (
    "date",
    "readiness_score",
    "hrv_avg",
    "resting_hr",
    "sleep_score",
    "total_sleep_sec",
    "deep_sleep_sec",
    "rem_sleep_sec",
    "body_temp_delta",
    "source",
)
_FITNESS_FIELDS = (
    "date",
    "metric_type",
    "value",
    "value_str",
    "source",
    "power_source",
)
_TRAINING_PLAN_FIELDS = (
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
    "source",
    "workout_origin",
    "external_id",
    "start_time",
    "meta",
)


def _json_value(value: Any) -> Any:
    """Convert database scalar values to JSON-safe export values."""
    if isinstance(value, datetime):
        return utc_isoformat(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def _without_credentials(value: Any) -> Any:
    """Remove credential-shaped keys from flexible JSON configuration fields."""
    if isinstance(value, dict):
        return {
            key: _without_credentials(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_without_credentials(item) for item in value]
    return _json_value(value)


def _serialize_rows(
    rows: Iterable[Any],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Serialize explicit export fields without internal ownership columns."""
    return [
        {field: _without_credentials(getattr(row, field)) for field in fields}
        for row in rows
    ]


def build_user_data_export(user_id: str, db: Session) -> dict[str, Any]:
    """Return the requested user's portable training data without credentials."""
    config = _without_credentials(asdict(load_config_from_db(user_id, db)))
    return {
        "schema_version": 1,
        "exported_at": utc_isoformat(datetime.now(timezone.utc)),
        "user_config": config,
        "activities": _serialize_rows(
            db.query(Activity)
            .filter(Activity.user_id == user_id)
            .order_by(Activity.date, Activity.id)
            .all(),
            _ACTIVITY_FIELDS,
        ),
        "activity_splits": _serialize_rows(
            db.query(ActivitySplit)
            .filter(ActivitySplit.user_id == user_id)
            .order_by(ActivitySplit.activity_id, ActivitySplit.split_num, ActivitySplit.id)
            .all(),
            _ACTIVITY_SPLIT_FIELDS,
        ),
        "recovery": _serialize_rows(
            db.query(RecoveryData)
            .filter(RecoveryData.user_id == user_id)
            .order_by(RecoveryData.date, RecoveryData.source, RecoveryData.id)
            .all(),
            _RECOVERY_FIELDS,
        ),
        "fitness": _serialize_rows(
            db.query(FitnessData)
            .filter(FitnessData.user_id == user_id)
            .order_by(FitnessData.date, FitnessData.metric_type, FitnessData.source, FitnessData.id)
            .all(),
            _FITNESS_FIELDS,
        ),
        "training_plans": _serialize_rows(
            db.query(TrainingPlan)
            .filter(TrainingPlan.user_id == user_id)
            .order_by(TrainingPlan.date, TrainingPlan.id)
            .all(),
            _TRAINING_PLAN_FIELDS,
        ),
    }
