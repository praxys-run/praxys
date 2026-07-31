"""Durable plan revision and provider-neutral delivery bookkeeping."""
from __future__ import annotations

import hashlib
import glob
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator, Mapping, Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from analysis.config import (
    LEGACY_PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCES,
    is_praxys_plan_source,
    normalize_workout_origin,
)
from db.cache_revision import bump_revisions, lock_revision_writes
from db.models import (
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanRevision,
    TrainingPlan,
    User,
)
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

PLAN_DELIVERY_STATES = frozenset(
    {"pending", "delivering", "synced", "conflict", "failed", "removed"}
)
DELIVERY_ATTEMPT_LEASE = timedelta(minutes=5)

_SNAPSHOT_FIELDS = (
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
    "start_time",
    "meta",
)
_LEGACY_LOCK_STATE = threading.local()


def lock_plan_writes(db: Session, user_id: str) -> None:
    """Serialize plan DB and compatibility-file writes for one user."""
    if db.get_bind().dialect.name == "sqlite" and not db.in_transaction():
        begin_serialized_write(db)
    lock_revision_writes(db, user_id)


def normalize_stryd_workout_id(raw_id: object) -> str | None:
    """Return a safe Stryd provider ID, or ``None`` for malformed values."""
    if isinstance(raw_id, int):
        if isinstance(raw_id, bool) or raw_id <= 0:
            return None
        candidate = str(raw_id)
    elif isinstance(raw_id, str):
        candidate = raw_id.strip()
    else:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", candidate):
        return None
    return candidate


def _user_exists(db: Session, user_id: str) -> bool:
    return db.execute(
        select(User.id).where(User.id == user_id)
    ).scalar_one_or_none() is not None


@contextmanager
def legacy_stryd_status_lock(
    status_dir: str,
    user_id: str,
) -> Iterator[None]:
    """Cross-process lock for one user's legacy compatibility files."""
    os.makedirs(status_dir, exist_ok=True)
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    lock_path = os.path.join(status_dir, f".{digest}.lock")
    held = getattr(_LEGACY_LOCK_STATE, "paths", set())
    if lock_path in held:
        yield
        return

    deadline = time.monotonic() + 10.0
    while True:
        try:
            fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock_path) > 60.0:
                    os.unlink(lock_path)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out acquiring legacy status lock for user {user_id}"
                )
            time.sleep(0.05)

    held = set(held)
    held.add(lock_path)
    _LEGACY_LOCK_STATE.paths = held
    try:
        yield
    finally:
        held.remove(lock_path)
        _LEGACY_LOCK_STATE.paths = held
        try:
            os.unlink(lock_path)
        except FileNotFoundError:
            pass


def _atomic_write_legacy_status(path: str, payload: Mapping[str, Any]) -> None:
    """Atomically replace one legacy JSON snapshot without shared temp names."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path),
        prefix=f"{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_field(record: Any, field: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(field)
    return getattr(record, field, None)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if value.__class__.__name__ in {"NAType", "NaTType"}:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_value(item())
        except (TypeError, ValueError):
            pass
    return str(value)


def plan_snapshot(record: Any) -> dict[str, Any]:
    """Return a JSON-safe canonical snapshot of one training-plan row."""
    snapshot = {
        field: _json_value(_read_field(record, field))
        for field in _SNAPSHOT_FIELDS
    }
    snapshot["source"] = snapshot.get("source") or PRAXYS_PLAN_SOURCE
    snapshot["workout_origin"] = normalize_workout_origin(
        snapshot.get("workout_origin"),
        source=snapshot["source"],
    )
    return snapshot


def _delivery_key_source(source: object) -> str:
    normalized = str(source or "").strip().casefold()
    if is_praxys_plan_source(normalized):
        # Frozen storage namespace for old workers. This is an encoding only;
        # canonical UUID, not this prefix, is the modern delivery identity.
        return LEGACY_PRAXYS_PLAN_SOURCE
    return normalized


def canonical_workout_key(snapshot: Mapping[str, Any]) -> str:
    """Return the stable logical key used across versions of one workout slot."""
    canonical_id = str(snapshot.get("canonical_id") or "").strip()
    source = _delivery_key_source(
        snapshot.get("source") or PRAXYS_PLAN_SOURCE
    )
    if canonical_id:
        return f"{source}:{canonical_id}"

    workout_date = str(snapshot.get("date") or "")
    if not workout_date:
        raise ValueError("plan snapshot must include a date")
    workout_type = str(snapshot.get("workout_type") or "unknown").strip().casefold()
    return f"{source}:{workout_date}:{workout_type or 'unknown'}"


def canonical_id_from_workout_key(canonical_key: str) -> str | None:
    """Return the UUID from a modern canonical key, excluding legacy slots."""
    prefix, separator, candidate = str(canonical_key or "").partition(":")
    if (
        not separator
        or prefix.strip().casefold() not in PRAXYS_PLAN_SOURCES
    ):
        return None
    try:
        return str(UUID(candidate))
    except (ValueError, AttributeError):
        return None


def delivery_canonical_id(delivery: PlanDelivery) -> str | None:
    """Return one delivery's durable UUID, including legacy key fallback."""
    if delivery.canonical_id:
        try:
            return str(UUID(delivery.canonical_id))
        except (ValueError, AttributeError):
            return None
    return canonical_id_from_workout_key(delivery.canonical_key)


def legacy_unknown_version(snapshot: Mapping[str, Any]) -> str:
    """Return the sentinel version for an unverified legacy push record."""
    return f"legacy-unknown:{canonical_workout_key(snapshot)}"


def workout_version(snapshot: Mapping[str, Any]) -> str:
    """Hash delivery-relevant workout content into an immutable version id."""
    normalized = plan_snapshot(snapshot)
    normalized.pop("meta", None)
    normalized.pop("canonical_id", None)
    normalized.pop("workout_origin", None)
    if is_praxys_plan_source(normalized.get("source")):
        # Preserve hashes produced before source="praxys" so ownership and
        # provenance migrations never trigger provider replacements.
        normalized["source"] = LEGACY_PRAXYS_PLAN_SOURCE
    payload = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def record_plan_revision(
    db: Session,
    *,
    user_id: str,
    operation: str,
    actor_type: str,
    actor_id: str | None,
    origin: str,
    before: Sequence[Any],
    after: Sequence[Any],
    details: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> PlanRevision:
    """Stage one append-only plan revision in the caller's transaction."""
    revision = PlanRevision(
        user_id=user_id,
        operation=operation,
        actor_type=actor_type,
        actor_id=actor_id,
        origin=origin,
        before_snapshot=[plan_snapshot(row) for row in before],
        after_snapshot=[plan_snapshot(row) for row in after],
        details=_json_value(dict(details or {})),
        idempotency_key=idempotency_key,
    )
    db.add(revision)
    db.flush()
    return revision


def record_plan_revision_idempotent(
    db: Session,
    *,
    user_id: str,
    operation: str,
    actor_type: str,
    actor_id: str | None,
    origin: str,
    before: Sequence[Any],
    after: Sequence[Any],
    details: Mapping[str, Any] | None,
    idempotency_key: str,
) -> tuple[PlanRevision, bool]:
    """Stage a revision once and return the existing row on an exact retry."""
    lock_plan_writes(db, user_id)
    existing = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    try:
        with db.begin_nested():
            revision = record_plan_revision(
                db,
                user_id=user_id,
                operation=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                origin=origin,
                before=before,
                after=after,
                details=details,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        revision = db.execute(
            select(PlanRevision).where(
                PlanRevision.user_id == user_id,
                PlanRevision.idempotency_key == idempotency_key,
            )
        ).scalar_one()
        return revision, False
    return revision, True


def _legacy_rekey_target(
    db: Session,
    *,
    user_id: str,
    source: str,
    workout_date: date,
    workout_type: str,
    legacy_delivery: PlanDelivery,
) -> tuple[str, str]:
    source_aliases = (
        PRAXYS_PLAN_SOURCES
        if is_praxys_plan_source(source)
        else (source,)
    )
    legacy_untyped_keys = {
        f"{alias}:{workout_date.isoformat()}"
        for alias in source_aliases
    }
    candidates: list[tuple[str, str, str]] = []
    rows = db.execute(
        select(TrainingPlan).where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(source_aliases),
            TrainingPlan.date == workout_date,
        )
    ).scalars().all()
    for row in rows:
        snapshot = plan_snapshot(row)
        if not snapshot.get("canonical_id"):
            continue
        candidate_type = str(
            snapshot.get("workout_type") or "unknown"
        ).strip().casefold()
        if (
            legacy_delivery.canonical_key not in legacy_untyped_keys
            and candidate_type != workout_type
        ):
            continue
        candidates.append((
            canonical_workout_key(snapshot),
            str(snapshot["canonical_id"]),
            workout_version(snapshot),
        ))

    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1]

    legacy_versions = {
        legacy_delivery.workout_version,
        legacy_delivery.plan_version,
    }
    matching_keys = {
        (candidate_key, candidate_id)
        for candidate_key, candidate_id, candidate_version in candidates
        if candidate_version in legacy_versions
    }
    if len(matching_keys) == 1:
        return matching_keys.pop()

    raise ValueError(
        "ambiguous legacy delivery identity requires reconciliation"
    )


def get_or_create_delivery(
    db: Session,
    *,
    user_id: str,
    target: str,
    snapshot: Mapping[str, Any] | Any,
    workout_version_override: str | None = None,
    plan_version_override: str | None = None,
    provider_content_version_override: str | None = None,
) -> tuple[PlanDelivery, bool]:
    """Return the stable delivery row for a workout version and target."""
    lock_plan_writes(db, user_id)
    normalized = plan_snapshot(snapshot)
    workout_date = date.fromisoformat(str(normalized["date"]))
    key = canonical_workout_key(normalized)
    canonical_id = str(normalized.get("canonical_id") or "").strip() or None
    plan_version = plan_version_override or workout_version(normalized)
    version = workout_version_override or plan_version
    identity_filter = (
        or_(
            PlanDelivery.canonical_id == canonical_id,
            PlanDelivery.canonical_key == key,
        )
        if canonical_id
        else PlanDelivery.canonical_key == key
    )
    existing = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            identity_filter,
            PlanDelivery.workout_version == version,
        )
    ).scalar_one_or_none()
    if existing is None:
        source = str(
            normalized.get("source") or PRAXYS_PLAN_SOURCE
        ).strip().lower()
        source_aliases = (
            PRAXYS_PLAN_SOURCES
            if is_praxys_plan_source(source)
            else (source,)
        )
        workout_type = str(
            normalized.get("workout_type") or "unknown"
        ).strip().casefold()
        legacy_keys = {
            legacy_key
            for source_alias in source_aliases
            for legacy_key in (
                f"{source_alias}:{workout_date.isoformat()}",
                (
                    f"{source_alias}:{workout_date.isoformat()}:"
                    f"{workout_type or 'unknown'}"
                ),
            )
        }
        legacy_keys.discard(key)
        if legacy_keys:
            legacy_rows = db.execute(
                select(PlanDelivery).where(
                    PlanDelivery.user_id == user_id,
                    PlanDelivery.target == target,
                    PlanDelivery.canonical_key.in_(legacy_keys),
                )
            ).scalars().all()
            active_legacy = [
                row for row in legacy_rows if row.state != "removed"
            ]
            version_matches = [
                row for row in legacy_rows
                if row.workout_version == version
            ]
            if len(active_legacy) > 1 or len(version_matches) > 1:
                raise ValueError(
                    "ambiguous legacy delivery identity requires reconciliation"
                )
            rows_to_rekey = {
                row.id: row
                for row in [*active_legacy, *version_matches]
            }
            for legacy_row in rows_to_rekey.values():
                if normalized.get("canonical_id"):
                    (
                        legacy_row.canonical_key,
                        legacy_row.canonical_id,
                    ) = _legacy_rekey_target(
                        db,
                        user_id=user_id,
                        source=source,
                        workout_date=workout_date,
                        workout_type=workout_type,
                        legacy_delivery=legacy_row,
                    )
                else:
                    legacy_row.canonical_key = key
                    legacy_row.canonical_id = canonical_id
            matching_versions = [
                row for row in version_matches
                if row.canonical_key == key
                or (
                    canonical_id is not None
                    and row.canonical_id == canonical_id
                )
            ]
            if matching_versions:
                existing = matching_versions[0]
    if existing is not None:
        if canonical_id and existing.canonical_id != canonical_id:
            existing.canonical_id = canonical_id
        if canonical_id and existing.canonical_key != key:
            existing.canonical_key = key
        if existing.plan_version != plan_version:
            existing.plan_version = plan_version
        if (
            provider_content_version_override is not None
            and existing.provider_content_version
            != provider_content_version_override
        ):
            existing.provider_content_version = (
                provider_content_version_override
            )
        db.flush()
        return existing, False

    delivery = PlanDelivery(
        user_id=user_id,
        canonical_key=key,
        canonical_id=canonical_id,
        workout_date=workout_date,
        workout_version=version,
        plan_version=plan_version,
        provider_content_version=provider_content_version_override,
        target=target,
        state="pending",
    )
    try:
        with db.begin_nested():
            db.add(delivery)
            db.flush()
    except IntegrityError:
        identity_filter = (
            or_(
                PlanDelivery.canonical_id == canonical_id,
                PlanDelivery.canonical_key == key,
            )
            if canonical_id
            else PlanDelivery.canonical_key == key
        )
        delivery = db.execute(
            select(PlanDelivery).where(
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == target,
                identity_filter,
                PlanDelivery.workout_version == version,
            )
        ).scalar_one()
        if delivery.plan_version != plan_version:
            delivery.plan_version = plan_version
        if (
            provider_content_version_override is not None
            and delivery.provider_content_version
            != provider_content_version_override
        ):
            delivery.provider_content_version = (
                provider_content_version_override
            )
        return delivery, False
    return delivery, True


def append_delivery_event(
    db: Session,
    delivery: PlanDelivery,
    *,
    operation: str,
    state: str,
    external_id: str | None,
    response: Mapping[str, Any] | None = None,
    error: str | None = None,
    completed_at: datetime | None = None,
) -> PlanDeliveryAttempt:
    """Append a terminal audit event without performing provider I/O."""
    if operation not in {"deliver", "remove", "import"}:
        raise ValueError(f"unsupported delivery operation: {operation}")
    if state not in PLAN_DELIVERY_STATES:
        raise ValueError(f"unsupported delivery state: {state}")
    lock_plan_writes(db, delivery.user_id)
    latest_number = db.execute(
        select(func.coalesce(func.max(PlanDeliveryAttempt.attempt_number), 0))
        .where(PlanDeliveryAttempt.delivery_id == delivery.id)
    ).scalar_one()
    timestamp = completed_at or datetime.utcnow()
    attempt = PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=int(latest_number) + 1,
        operation=operation,
        state=state,
        external_id=external_id,
        error=error,
        response=(
            _json_value(dict(response or {}))
            if response is not None
            else None
        ),
        started_at=timestamp,
        completed_at=timestamp,
    )
    db.add(attempt)
    db.flush()
    return attempt


def begin_delivery_attempt(
    db: Session,
    delivery: PlanDelivery,
    *,
    operation: str,
) -> tuple[PlanDelivery, PlanDeliveryAttempt | None, str]:
    """Stage a delivery attempt and report whether external work should start."""
    if operation not in {"deliver", "remove"}:
        raise ValueError(f"unsupported delivery operation: {operation}")
    lock_plan_writes(db, delivery.user_id)

    # A user-row lock serializes different content versions of the same
    # canonical slot. PlanDelivery's uniqueness is version-scoped, so locking
    # only the selected row would let two concurrent versions POST together.
    db.execute(
        select(User.id)
        .where(User.id == delivery.user_id)
        .with_for_update()
    ).scalar_one_or_none()
    slot_rows = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == delivery.user_id,
            PlanDelivery.target == delivery.target,
            (
                or_(
                    PlanDelivery.canonical_id == delivery.canonical_id,
                    PlanDelivery.canonical_key == delivery.canonical_key,
                )
                if delivery.canonical_id
                else PlanDelivery.canonical_key == delivery.canonical_key
            ),
        )
        .order_by(PlanDelivery.created_at.asc(), PlanDelivery.id.asc())
        .with_for_update()
    ).scalars().all()
    locked = next(
        (row for row in slot_rows if row.id == delivery.id),
        None,
    )
    if locked is None:
        raise ValueError(
            "delivery row left its canonical slot before attempt start"
        )

    if operation == "deliver":
        if any(
            row.id != locked.id and row.state in {"delivering", "conflict"}
            for row in slot_rows
        ):
            return locked, None, "reconciliation_required"
        if any(
            row.id != locked.id
            and row.state == "synced"
            and row.external_id is not None
            for row in slot_rows
        ):
            return locked, None, "replacement_required"

    if operation == "deliver" and locked.state == "synced" and locked.external_id:
        return locked, None, "already_complete"
    if operation == "remove" and locked.state == "removed":
        return locked, None, "already_complete"
    if locked.state == "delivering":
        latest_attempt = db.execute(
            select(PlanDeliveryAttempt)
            .where(PlanDeliveryAttempt.delivery_id == locked.id)
            .order_by(
                PlanDeliveryAttempt.attempt_number.desc(),
                PlanDeliveryAttempt.id.desc(),
            )
        ).scalars().first()
        now = datetime.utcnow()
        lease_expired = (
            latest_attempt is not None
            and latest_attempt.operation == "remove"
            and latest_attempt.state == "delivering"
            and latest_attempt.started_at <= now - DELIVERY_ATTEMPT_LEASE
        )
        if operation != "remove" or not lease_expired:
            return locked, None, "reconciliation_required"
        latest_attempt.state = "failed"
        latest_attempt.error = "Removal attempt lease expired; superseded by retry"
        latest_attempt.completed_at = now
    if operation == "deliver" and locked.state == "conflict":
        return locked, None, "reconciliation_required"

    latest_number = db.execute(
        select(func.coalesce(func.max(PlanDeliveryAttempt.attempt_number), 0))
        .where(PlanDeliveryAttempt.delivery_id == locked.id)
    ).scalar_one()
    attempt = PlanDeliveryAttempt(
        delivery_id=locked.id,
        attempt_number=int(latest_number) + 1,
        operation=operation,
        state="delivering",
        started_at=datetime.utcnow(),
    )
    locked.state = "delivering"
    locked.last_error = None
    locked.updated_at = datetime.utcnow()
    db.add(attempt)
    db.flush()
    return locked, attempt, "started"


def complete_delivery_attempt(
    db: Session,
    *,
    user_id: str,
    delivery_id: str,
    attempt_id: int,
    attempt_state: str,
    delivery_state: str | None = None,
    external_id: str | None = None,
    error: str | None = None,
    response: Mapping[str, Any] | None = None,
    provider_account_id: str | None = None,
) -> bool:
    """Stage a terminal result if this attempt still owns the delivery."""
    if attempt_state not in PLAN_DELIVERY_STATES:
        raise ValueError(f"unsupported attempt state: {attempt_state}")
    final_delivery_state = delivery_state or attempt_state
    if final_delivery_state not in PLAN_DELIVERY_STATES:
        raise ValueError(f"unsupported delivery state: {final_delivery_state}")
    lock_plan_writes(db, user_id)
    locked_delivery = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.id == delivery_id,
            PlanDelivery.user_id == user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    locked_attempt = db.execute(
        select(PlanDeliveryAttempt)
        .where(
            PlanDeliveryAttempt.id == attempt_id,
            PlanDeliveryAttempt.delivery_id == delivery_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()
    latest_attempt_id = db.execute(
        select(PlanDeliveryAttempt.id)
        .where(PlanDeliveryAttempt.delivery_id == locked_delivery.id)
        .order_by(
            PlanDeliveryAttempt.attempt_number.desc(),
            PlanDeliveryAttempt.id.desc(),
        )
    ).scalars().first()
    if (
        locked_attempt.id != latest_attempt_id
        or locked_attempt.state != "delivering"
    ):
        late_removal_success = (
            locked_attempt.operation == "remove"
            and attempt_state == "removed"
            and external_id is not None
            and locked_delivery.external_id == external_id
        )
        if locked_attempt.state == "delivering" or late_removal_success:
            now = datetime.utcnow()
            locked_attempt.state = attempt_state
            locked_attempt.external_id = external_id or locked_attempt.external_id
            locked_attempt.error = error
            locked_attempt.response = (
                _json_value(dict(response or {})) if response is not None else None
            )
            locked_attempt.completed_at = now
            if late_removal_success:
                locked_delivery.state = "removed"
                locked_delivery.last_error = None
                locked_delivery.updated_at = now
        return False

    now = datetime.utcnow()
    locked_attempt.state = attempt_state
    locked_attempt.external_id = external_id or locked_attempt.external_id
    locked_attempt.error = error
    locked_attempt.response = (
        _json_value(dict(response or {})) if response is not None else None
    )
    locked_attempt.completed_at = now

    if (
        locked_attempt.operation == "remove"
        and attempt_state == "failed"
        and locked_delivery.state == "removed"
    ):
        return False

    locked_delivery.state = final_delivery_state
    locked_delivery.external_id = external_id or locked_delivery.external_id
    if provider_account_id is not None:
        locked_delivery.provider_account_id = provider_account_id
    locked_delivery.last_error = error
    locked_delivery.updated_at = now
    if final_delivery_state == "synced":
        locked_delivery.delivered_at = now
    return True


def find_delivery_by_external_id(
    db: Session,
    *,
    user_id: str,
    target: str,
    external_id: str,
    provider_account_id: str | None = None,
) -> PlanDelivery | None:
    """Find the newest delivery row associated with a provider workout id."""
    statement = select(PlanDelivery).where(
        PlanDelivery.user_id == user_id,
        PlanDelivery.target == target,
        PlanDelivery.external_id == external_id,
    )
    if provider_account_id is not None:
        statement = statement.where(
            PlanDelivery.provider_account_id == provider_account_id
        )
    return db.execute(
        statement
        .order_by(PlanDelivery.updated_at.desc(), PlanDelivery.created_at.desc())
    ).scalars().first()


def find_unverified_delivery_for_date(
    db: Session,
    *,
    user_id: str,
    target: str,
    workout_date: date,
) -> PlanDelivery | None:
    """Find a synced delivery whose content version is not verified."""
    return db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.workout_date == workout_date,
            PlanDelivery.state == "synced",
            PlanDelivery.workout_version.like("legacy-unknown:%"),
        )
        .order_by(PlanDelivery.updated_at.desc(), PlanDelivery.created_at.desc())
    ).scalars().first()


def delivery_status_for_snapshots(
    db: Session,
    *,
    user_id: str,
    target: str,
    current_snapshots: Mapping[str, Mapping[str, Any]],
    include_prior_versions: bool = True,
) -> dict[str, dict[str, str]]:
    """Project synced delivery rows into the legacy date-keyed status shape."""
    current_versions = {
        date_key: workout_version(snapshot)
        for date_key, snapshot in current_snapshots.items()
    }
    rows = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.state == "synced",
            PlanDelivery.external_id.is_not(None),
        )
        .order_by(PlanDelivery.updated_at.asc(), PlanDelivery.created_at.asc())
    ).scalars().all()
    delivery_ids = [row.id for row in rows]
    attempts = (
        db.execute(
            select(
                PlanDeliveryAttempt.delivery_id,
                PlanDeliveryAttempt.operation,
                PlanDeliveryAttempt.response,
            ).where(PlanDeliveryAttempt.delivery_id.in_(delivery_ids))
        ).all()
        if delivery_ids
        else []
    )
    status_eligible: set[str] = set()
    for delivery_id, operation, response in attempts:
        if operation == "deliver":
            status_eligible.add(delivery_id)
        elif (
            operation == "import"
            and isinstance(response, Mapping)
            and response.get("legacy_import") is True
        ):
            status_eligible.add(delivery_id)

    status: dict[str, dict[str, str]] = {}
    priorities: dict[str, int] = {}
    for delivery in rows:
        if delivery.id not in status_eligible:
            continue
        date_key = delivery.workout_date.isoformat()
        current_version = current_versions.get(date_key)
        delivery_plan_version = (
            delivery.plan_version or delivery.workout_version
        )
        if (
            not include_prior_versions
            and delivery_plan_version != current_version
        ):
            continue
        priority = int(current_version == delivery_plan_version)
        if priority < priorities.get(date_key, -1):
            continue
        entry = {
            "workout_id": str(delivery.external_id),
            "status": "pushed",
        }
        pushed_at = delivery.delivered_at or delivery.updated_at
        if pushed_at is not None:
            if pushed_at.tzinfo is None:
                pushed_at = pushed_at.replace(tzinfo=timezone.utc)
            entry["pushed_at"] = pushed_at.isoformat()
        status[date_key] = entry
        priorities[date_key] = priority
    return status


def legacy_stryd_status_path(status_dir: str, user_id: str) -> str:
    """Return the old per-user Stryd push-status JSON path."""
    return os.path.join(status_dir, f"{user_id}.json")


def write_legacy_stryd_status(
    db: Session,
    *,
    status_dir: str,
    user_id: str,
    workout_date: str,
    external_id: str,
    pushed_at: str,
) -> None:
    """Dual-write a successful delivery for mixed-version deployments."""
    external_id = normalize_stryd_workout_id(external_id)
    if external_id is None:
        raise ValueError("invalid Stryd workout id")
    lock_plan_writes(db, user_id)
    if not _user_exists(db, user_id):
        db.rollback()
        raise LookupError(f"user {user_id} no longer exists")
    active_delivery = db.execute(
        select(PlanDelivery.id).where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == "stryd",
            PlanDelivery.workout_date == date.fromisoformat(workout_date),
            PlanDelivery.external_id == external_id,
            PlanDelivery.state == "synced",
            ~PlanDelivery.workout_version.startswith("legacy-unknown:"),
        )
    ).scalars().first()
    if active_delivery is None:
        db.rollback()
        logger.info(
            "Skipped stale legacy Stryd status write for user %s and workout %s",
            user_id,
            external_id,
        )
        return
    if has_unresolved_legacy_stryd_corruption(db, user_id=user_id):
        db.rollback()
        logger.warning(
            "Skipped legacy Stryd status write for user %s because "
            "quarantined state requires an authoritative recovery snapshot",
            user_id,
        )
        return
    with legacy_stryd_status_lock(status_dir, user_id):
        path = legacy_stryd_status_path(status_dir, user_id)
        payload: dict[str, Any] = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                db.rollback()
                raise ValueError(f"expected object in {path}")
            payload = loaded
        payload[workout_date] = {
            "workout_id": external_id,
            "pushed_at": pushed_at,
            "status": "pushed",
        }
        try:
            _atomic_write_legacy_status(path, payload)
        except Exception:
            db.rollback()
            raise
        import_legacy_stryd_status(db, user_id=user_id, status_dir=status_dir)


def remove_legacy_stryd_status(
    db: Session,
    *,
    status_dir: str,
    user_id: str,
    external_id: str,
) -> None:
    """Dual-write a provider removal into the legacy compatibility file."""
    external_id = normalize_stryd_workout_id(external_id)
    if external_id is None:
        raise ValueError("invalid Stryd workout id")
    lock_plan_writes(db, user_id)
    if not _user_exists(db, user_id):
        db.rollback()
        raise LookupError(f"user {user_id} no longer exists")
    with legacy_stryd_status_lock(status_dir, user_id):
        path = legacy_stryd_status_path(status_dir, user_id)
        if not os.path.exists(path):
            db.rollback()
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise ValueError(f"expected object in {path}")
        except Exception:
            db.rollback()
            raise
        payload = {
            date_key: entry
            for date_key, entry in loaded.items()
            if not (
                isinstance(entry, Mapping)
                and str(entry.get("workout_id") or "") == external_id
            )
        }
        try:
            _atomic_write_legacy_status(path, payload)
        except Exception:
            db.rollback()
            raise
        import_legacy_stryd_status(db, user_id=user_id, status_dir=status_dir)


def _parse_legacy_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _archive_legacy_file(path: str, suffix: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = f"{path}.{suffix}-{stamp}"
    try:
        os.replace(path, destination)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Failed to archive legacy plan status %s: %s", path, exc)


def _legacy_entries_from_revision(revision: PlanRevision | None) -> dict[str, dict[str, Any]]:
    """Return the normalized compatibility snapshot stored on an import event."""
    if revision is None or not isinstance(revision.details, Mapping):
        return {}
    entries = revision.details.get("entries")
    if not isinstance(entries, Mapping):
        return {}
    return {
        str(date_key): dict(entry)
        for date_key, entry in entries.items()
        if isinstance(entry, Mapping)
    }


def _legacy_revision_has_unresolved_corruption(
    revision: PlanRevision | None,
) -> bool:
    return bool(
        revision is not None
        and isinstance(revision.details, Mapping)
        and revision.details.get("unresolved_corruption") is True
    )


def _legacy_corrupt_archive_paths(path: str) -> list[str]:
    return sorted(glob.glob(f"{glob.escape(path)}.corrupt-*"))


def _read_latest_legacy_corrupt_archive(
    archive_paths: Sequence[str],
    *,
    user_id: str,
) -> bytes:
    if not archive_paths:
        return b""
    try:
        with open(archive_paths[-1], "rb") as handle:
            return handle.read()
    except OSError:
        logger.warning(
            "Could not read quarantined legacy Stryd state for user=%s",
            user_id,
        )
        return b""


def _legacy_archives_resolved(
    revision: PlanRevision | None,
    *,
    archive_paths: Sequence[str],
) -> bool:
    if not archive_paths:
        return True
    if (
        revision is None
        or _legacy_revision_has_unresolved_corruption(revision)
        or not isinstance(revision.details, Mapping)
    ):
        return False
    resolved_names = revision.details.get("resolved_corrupt_archives")
    if isinstance(resolved_names, list) and {
        os.path.basename(archive_path)
        for archive_path in archive_paths
    }.issubset({
        str(name)
        for name in resolved_names
    }):
        return True
    return False


def _latest_legacy_stryd_revision(
    db: Session,
    *,
    user_id: str,
) -> PlanRevision | None:
    return db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.user_id == user_id,
            PlanRevision.origin == "legacy.stryd_push_status",
        )
        .order_by(PlanRevision.created_at.desc(), PlanRevision.id.desc())
    ).scalars().first()


def has_unresolved_legacy_stryd_corruption(
    db: Session,
    *,
    user_id: str,
) -> bool:
    """Return whether a quarantined legacy snapshot still needs review."""
    return _legacy_revision_has_unresolved_corruption(
        _latest_legacy_stryd_revision(db, user_id=user_id)
    )


def _record_legacy_stryd_corruption(
    db: Session,
    *,
    user_id: str,
    raw: bytes,
) -> bool:
    """Persist a durable cleanup fence before quarantining corrupt state."""
    digest = hashlib.sha256(raw).hexdigest()
    previous_revision = _latest_legacy_stryd_revision(
        db,
        user_id=user_id,
    )
    if (
        _legacy_revision_has_unresolved_corruption(previous_revision)
        and isinstance(previous_revision.details, Mapping)
        and previous_revision.details.get("content_sha256") == digest
    ):
        db.rollback()
        return True
    previous_token = (
        previous_revision.id if previous_revision is not None else "initial"
    )
    previous_entries = _legacy_entries_from_revision(previous_revision)
    try:
        record_plan_revision(
            db,
            user_id=user_id,
            operation="legacy_import",
            actor_type="system",
            actor_id=None,
            origin="legacy.stryd_push_status",
            before=[],
            after=[],
            details={
                "imported": 0,
                "skipped": 0,
                "entries": previous_entries,
                "unresolved_corruption": True,
                "content_sha256": digest,
            },
            idempotency_key=(
                f"legacy-stryd-corrupt:{digest}:after:{previous_token}"
            ),
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Failed to persist corrupt legacy Stryd marker for user=%s",
            user_id,
        )
        return False
    return True


def _append_legacy_attempt(
    db: Session,
    delivery: PlanDelivery,
    *,
    state: str,
    external_id: str,
    completed_at: datetime,
    action: str,
) -> None:
    """Append one compatibility-file transition to a delivery's history."""
    latest_number = db.execute(
        select(func.coalesce(func.max(PlanDeliveryAttempt.attempt_number), 0))
        .where(PlanDeliveryAttempt.delivery_id == delivery.id)
    ).scalar_one()
    db.add(
        PlanDeliveryAttempt(
            delivery_id=delivery.id,
            attempt_number=int(latest_number) + 1,
            operation="import",
            state=state,
            external_id=external_id,
            response={"legacy_import": True, "action": action},
            started_at=completed_at,
            completed_at=completed_at,
        )
    )
    db.flush()


def import_legacy_stryd_status(
    db: Session,
    *,
    user_id: str,
    status_dir: str,
    authoritative_recovery: bool = False,
) -> str:
    """Reconcile one user's current legacy Stryd JSON snapshot into the ledger."""
    path = legacy_stryd_status_path(status_dir, user_id)
    if (
        not os.path.exists(path)
        and not _legacy_corrupt_archive_paths(path)
    ):
        return "missing"
    lock_plan_writes(db, user_id)
    if not _user_exists(db, user_id):
        db.rollback()
        return "missing_user"
    with legacy_stryd_status_lock(status_dir, user_id):
        if os.path.exists(path):
            return _import_legacy_stryd_status_locked(
                db,
                user_id=user_id,
                path=path,
                authoritative_recovery=authoritative_recovery,
            )
        archive_paths = _legacy_corrupt_archive_paths(path)
        previous_revision = _latest_legacy_stryd_revision(
            db,
            user_id=user_id,
        )
        if _legacy_archives_resolved(
            previous_revision,
            archive_paths=archive_paths,
        ):
            db.rollback()
            return "missing"
        _record_legacy_stryd_corruption(
            db,
            user_id=user_id,
            raw=_read_latest_legacy_corrupt_archive(
                archive_paths,
                user_id=user_id,
            ),
        )
        return "corrupt"


def _import_legacy_stryd_status_locked(
    db: Session,
    *,
    user_id: str,
    path: str,
    authoritative_recovery: bool,
) -> str:
    """Reconcile a compatibility snapshot while its file lock is held."""

    raw = b""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected object, got {type(payload).__name__}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        logger.error(
            "Quarantining corrupt legacy Stryd status for user=%s path=%s: %s",
            user_id,
            path,
            exc,
        )
        if _record_legacy_stryd_corruption(
            db,
            user_id=user_id,
            raw=raw,
        ):
            _archive_legacy_file(path, "corrupt")
        return "corrupt"

    previous_revision = _latest_legacy_stryd_revision(
        db,
        user_id=user_id,
    )
    previous_entries = _legacy_entries_from_revision(previous_revision)
    archive_paths = _legacy_corrupt_archive_paths(path)
    archives_resolved = _legacy_archives_resolved(
        previous_revision,
        archive_paths=archive_paths,
    )
    recovery_required = (
        _legacy_revision_has_unresolved_corruption(previous_revision)
        or not archives_resolved
    )
    if recovery_required and not authoritative_recovery:
        if not _legacy_revision_has_unresolved_corruption(previous_revision):
            _record_legacy_stryd_corruption(
                db,
                user_id=user_id,
                raw=_read_latest_legacy_corrupt_archive(
                    archive_paths,
                    user_id=user_id,
                ),
            )
        else:
            db.rollback()
        return "corrupt"
    if recovery_required:
        if not _legacy_revision_has_unresolved_corruption(previous_revision):
            _record_legacy_stryd_corruption(
                db,
                user_id=user_id,
                raw=_read_latest_legacy_corrupt_archive(
                    archive_paths,
                    user_id=user_id,
                ),
            )
        previous_revision = _latest_legacy_stryd_revision(
            db,
            user_id=user_id,
        )
        previous_entries = _legacy_entries_from_revision(previous_revision)

    parsed: list[tuple[str, dict[str, Any], str, datetime | None]] = []
    normalized_entries: dict[str, dict[str, Any]] = {}
    skipped = 0
    for date_key, entry in payload.items():
        if not isinstance(entry, Mapping):
            skipped += 1
            continue
        try:
            workout_date = date.fromisoformat(str(date_key))
        except ValueError:
            skipped += 1
            continue
        external_id = normalize_stryd_workout_id(entry.get("workout_id"))
        legacy_state = str(entry.get("status") or "pushed").strip().lower()
        if not external_id or legacy_state not in {"pushed", "synced", "success"}:
            skipped += 1
            continue

        snapshot = plan_snapshot(
            {
                "date": workout_date,
                "source": LEGACY_PRAXYS_PLAN_SOURCE,
                "workout_type": None,
            }
        )
        pushed_at = _parse_legacy_timestamp(entry.get("pushed_at"))
        normalized_entry: dict[str, Any] = {
            "workout_id": external_id,
            "status": "pushed",
        }
        if pushed_at is not None:
            normalized_entry["pushed_at"] = pushed_at.replace(
                tzinfo=timezone.utc
            ).isoformat()
        normalized_entries[workout_date.isoformat()] = normalized_entry
        parsed.append((workout_date.isoformat(), snapshot, external_id, pushed_at))

    if (
        previous_revision is not None
        and not _legacy_revision_has_unresolved_corruption(previous_revision)
        and archives_resolved
        and normalized_entries == previous_entries
    ):
        db.rollback()
        return "already_imported"
    normalized_payload = json.dumps(
        normalized_entries,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    digest = hashlib.sha256(normalized_payload).hexdigest()
    previous_token = previous_revision.id if previous_revision is not None else "initial"
    idempotency_key = (
        f"legacy-stryd-status:{digest}:after:{previous_token}"
    )

    try:
        record_plan_revision(
            db,
            user_id=user_id,
            operation="legacy_import",
            actor_type="system",
            actor_id=None,
            origin="legacy.stryd_push_status",
            before=[],
            after=[snapshot for _, snapshot, _, _ in parsed],
            details={
                "imported": len(parsed),
                "skipped": skipped,
                "entries": normalized_entries,
                **(
                    {
                        "resolved_corrupt_archives": [
                            os.path.basename(archive_path)
                            for archive_path in archive_paths
                        ],
                    }
                    if archive_paths
                    else {}
                ),
            },
            idempotency_key=idempotency_key,
        )
        changed = False
        completed_at = datetime.utcnow()

        # Old workers can delete or replace a date in the compatibility file.
        # Reconcile the prior imported snapshot before applying the new one.
        for date_key, previous_entry in previous_entries.items():
            previous_external_id = str(
                previous_entry.get("workout_id") or ""
            ).strip()
            current_external_id = str(
                normalized_entries.get(date_key, {}).get("workout_id") or ""
            ).strip()
            if not previous_external_id or current_external_id == previous_external_id:
                continue
            previous_delivery = find_delivery_by_external_id(
                db,
                user_id=user_id,
                target="stryd",
                external_id=previous_external_id,
            )
            if previous_delivery is None or previous_delivery.state == "removed":
                continue
            current_delivery = (
                find_delivery_by_external_id(
                    db,
                    user_id=user_id,
                    target="stryd",
                    external_id=current_external_id,
                )
                if current_external_id
                else None
            )
            if (
                current_delivery is not None
                and current_delivery.state == "synced"
                and not current_delivery.workout_version.startswith(
                    "legacy-unknown:"
                )
                and (
                    delivery_canonical_id(current_delivery)
                    != delivery_canonical_id(previous_delivery)
                    if (
                        delivery_canonical_id(current_delivery)
                        and delivery_canonical_id(previous_delivery)
                    )
                    else current_delivery.canonical_key
                    != previous_delivery.canonical_key
                )
            ):
                # The compatibility file can represent only one workout per
                # date. Replacing its date entry must not tombstone a separate
                # verified canonical workout that still exists at the target.
                continue
            previous_delivery.state = "removed"
            previous_delivery.last_error = None
            previous_delivery.updated_at = completed_at
            _append_legacy_attempt(
                db,
                previous_delivery,
                state="removed",
                external_id=previous_external_id,
                completed_at=completed_at,
                action="removed",
            )
            changed = True

        for _, snapshot, external_id, pushed_at in parsed:
            existing_external = find_delivery_by_external_id(
                db,
                user_id=user_id,
                target="stryd",
                external_id=external_id,
            )
            if existing_external is not None:
                if not existing_external.workout_version.startswith(
                    "legacy-unknown:"
                ):
                    continue
                restored_at = pushed_at or completed_at
                existing_external.state = "synced"
                existing_external.last_error = None
                existing_external.delivered_at = (
                    pushed_at
                    or existing_external.delivered_at
                    or completed_at
                )
                existing_external.updated_at = restored_at
                _append_legacy_attempt(
                    db,
                    existing_external,
                    state="synced",
                    external_id=external_id,
                    completed_at=restored_at,
                    action="restored",
                )
                changed = True
                continue
            delivery, created = get_or_create_delivery(
                db,
                user_id=user_id,
                target="stryd",
                snapshot=snapshot,
                workout_version_override=legacy_unknown_version(snapshot),
                plan_version_override=legacy_unknown_version(snapshot),
            )
            if (
                not created
                and delivery.state == "synced"
                and delivery.external_id == external_id
            ):
                continue
            imported_at = pushed_at or completed_at
            delivery.state = "synced"
            delivery.external_id = external_id
            delivery.last_error = None
            delivery.delivered_at = pushed_at or delivery.delivered_at
            delivery.updated_at = imported_at
            _append_legacy_attempt(
                db,
                delivery,
                state="synced",
                external_id=external_id,
                completed_at=imported_at,
                action="created" if created else "replaced",
            )
            changed = True
        if changed:
            bump_revisions(db, user_id, ["plans"])
        db.commit()
    except IntegrityError:
        db.rollback()
        marker = db.execute(
            select(PlanRevision.id).where(
                PlanRevision.user_id == user_id,
                PlanRevision.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if marker is None:
            raise
        return "already_imported"
    except Exception:
        db.rollback()
        raise

    return "imported"
