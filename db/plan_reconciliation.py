"""Persistence helpers for execution-target calendar reconciliation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.cache_revision import bump_revisions
from db.models import (
    PlanDelivery,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
)
from db.plan_ledger import lock_plan_writes


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalized_target_workout(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical plan fields retained from a provider workout."""
    workout_date = _parse_date(row.get("date"))
    if workout_date is None:
        raise ValueError("target workout must include an ISO date")
    start_time = _parse_datetime(row.get("start_time"))
    return {
        "date": workout_date.isoformat(),
        "workout_type": str(row.get("workout_type") or ""),
        "planned_duration_min": _float_or_none(
            row.get("planned_duration_min")
        ),
        "planned_distance_km": _float_or_none(
            row.get("planned_distance_km")
        ),
        "target_power_min": _float_or_none(row.get("target_power_min")),
        "target_power_max": _float_or_none(row.get("target_power_max")),
        "target_hr_min": _float_or_none(row.get("target_hr_min")),
        "target_hr_max": _float_or_none(row.get("target_hr_max")),
        "target_pace_min": (
            str(row.get("target_pace_min"))
            if row.get("target_pace_min") not in (None, "")
            else None
        ),
        "target_pace_max": (
            str(row.get("target_pace_max"))
            if row.get("target_pace_max") not in (None, "")
            else None
        ),
        "workout_description": str(
            row.get("workout_description") or ""
        ),
        "start_time": start_time.isoformat() if start_time else None,
    }


def record_target_calendar_sync(
    db: Session,
    *,
    user_id: str,
    target: str,
    provider_account_id: str,
    rows: Sequence[Mapping[str, Any]],
    window_start: date,
    window_end: date,
    observed_at: datetime | None = None,
) -> int | None:
    """Persist a snapshot, or return ``None`` when its fetch is stale."""
    if window_end < window_start:
        raise ValueError("calendar sync window is inverted")
    account_id = str(provider_account_id or "").strip()
    if not account_id:
        raise ValueError("provider account identity is required")
    timestamp = observed_at or datetime.utcnow()

    normalized_rows: list[
        tuple[str, date, datetime | None, dict[str, Any], str | None, str | None]
    ] = []
    observed_ids: set[str] = set()
    for row in rows:
        external_id = str(row.get("external_id") or "").strip()
        if not external_id or len(external_id) > 200:
            continue
        snapshot = normalized_target_workout(row)
        workout_date = date.fromisoformat(snapshot["date"])
        start_time = _parse_datetime(row.get("start_time"))
        content_fingerprint = str(
            row.get("provider_content_fingerprint") or ""
        ).strip() or None
        payload_fingerprint = str(
            row.get("provider_payload_fingerprint") or ""
        ).strip() or None
        normalized_rows.append(
            (
                external_id,
                workout_date,
                start_time,
                snapshot,
                content_fingerprint,
                payload_fingerprint,
            )
        )
        observed_ids.add(external_id)

    lock_plan_writes(db, user_id)
    changed = 0
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync)
        .where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if calendar_sync is not None and timestamp < calendar_sync.synced_at:
        return None
    if calendar_sync is None:
        calendar_sync = PlanTargetCalendarSync(
            user_id=user_id,
            target=target,
            provider_account_id=account_id,
            window_start=window_start,
            window_end=window_end,
            synced_at=timestamp,
        )
        db.add(calendar_sync)
        changed += 1
    else:
        if (
            calendar_sync.provider_account_id != account_id
            or calendar_sync.window_start != window_start
            or calendar_sync.window_end != window_end
        ):
            changed += 1
        calendar_sync.provider_account_id = account_id
        calendar_sync.window_start = window_start
        calendar_sync.window_end = window_end
        calendar_sync.synced_at = timestamp

    existing_rows = db.execute(
        select(PlanTargetWorkout)
        .where(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
            PlanTargetWorkout.provider_account_id == account_id,
        )
        .with_for_update()
    ).scalars().all()
    by_external_id = {row.external_id: row for row in existing_rows}

    for (
        external_id,
        workout_date,
        start_time,
        snapshot,
        content_fingerprint,
        payload_fingerprint,
    ) in normalized_rows:
        observation = by_external_id.get(external_id)
        if observation is None:
            observation = PlanTargetWorkout(
                user_id=user_id,
                target=target,
                provider_account_id=account_id,
                external_id=external_id,
                workout_date=workout_date,
                start_time=start_time,
                normalized_workout=snapshot,
                content_fingerprint=content_fingerprint,
                payload_fingerprint=payload_fingerprint,
                present=True,
                observed_at=timestamp,
            )
            db.add(observation)
            by_external_id[external_id] = observation
            changed += 1
            continue
        if timestamp < observation.observed_at:
            continue
        if (
            observation.workout_date != workout_date
            or observation.start_time != start_time
            or observation.normalized_workout != snapshot
            or observation.content_fingerprint != content_fingerprint
            or observation.payload_fingerprint != payload_fingerprint
            or not observation.present
        ):
            changed += 1
        observation.workout_date = workout_date
        observation.start_time = start_time
        observation.normalized_workout = snapshot
        observation.content_fingerprint = content_fingerprint
        observation.payload_fingerprint = payload_fingerprint
        observation.present = True
        observation.observed_at = timestamp

    for observation in existing_rows:
        if (
            observation.present
            and timestamp >= observation.observed_at
            and window_start <= observation.workout_date <= window_end
            and observation.external_id not in observed_ids
        ):
            observation.present = False
            observation.observed_at = timestamp
            changed += 1

    deliveries = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.provider_account_id == account_id,
            PlanDelivery.external_id.is_not(None),
            PlanDelivery.state != "removed",
            PlanDelivery.workout_date >= window_start,
            PlanDelivery.workout_date <= window_end,
        )
    ).scalars().all()
    for delivery in deliveries:
        external_id = str(delivery.external_id)
        if external_id in observed_ids:
            continue
        reference_time = delivery.delivered_at or delivery.updated_at
        if timestamp < reference_time:
            continue
        observation = by_external_id.get(external_id)
        if observation is None:
            observation = PlanTargetWorkout(
                user_id=user_id,
                target=target,
                provider_account_id=account_id,
                external_id=external_id,
                workout_date=delivery.workout_date,
                normalized_workout={},
                present=False,
                observed_at=timestamp,
            )
            db.add(observation)
            by_external_id[external_id] = observation
            changed += 1
        elif (
            observation.present
            and window_start <= observation.workout_date <= window_end
        ):
            observation.present = False
            observation.observed_at = timestamp
            changed += 1

    if changed:
        bump_revisions(db, user_id, ["plans"])
    return changed


def mark_target_workout_absent(
    db: Session,
    *,
    user_id: str,
    target: str,
    provider_account_id: str,
    external_id: str,
) -> bool:
    """Mark a provider observation absent after a confirmed owned removal."""
    observation = db.execute(
        select(PlanTargetWorkout).where(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
            PlanTargetWorkout.provider_account_id == provider_account_id,
            PlanTargetWorkout.external_id == external_id,
        )
    ).scalar_one_or_none()
    if observation is None or not observation.present:
        return False
    observation.present = False
    observation.observed_at = datetime.utcnow()
    return True
