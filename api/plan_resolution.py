"""Explicit, auditable plan reconciliation resolution operations."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.plan_delivery.base import PlanDeliveryAdapter
from api.plan_delivery.service import PlanDeliveryService
from api.plan_reconciliation import PlanReconciliationItem
from db.cache_revision import bump_revisions
from db.models import (
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanRevision,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    TrainingPlan,
)
from db.plan_ledger import (
    append_delivery_event,
    canonical_workout_key,
    get_or_create_delivery,
    lock_plan_writes,
    plan_snapshot,
    record_plan_revision_idempotent,
    workout_version,
)

logger = logging.getLogger(__name__)


class PlanResolutionError(RuntimeError):
    """Base class for explicit reconciliation resolution failures."""


class PlanResolutionConflict(PlanResolutionError):
    """The selected reconciliation item is stale or cannot be resolved safely."""


class PlanResolutionProviderError(PlanResolutionError):
    """The provider did not complete the requested restore."""


@dataclass(frozen=True)
class PlanResolutionResult:
    """Confirmed resolution outcome."""

    action: str
    reconciliation_id: str
    revision_id: str
    canonical_id: str
    external_id: str | None = None


def completed_plan_resolution(
    db: Session,
    *,
    user_id: str,
    target: str,
    reconciliation_id: str,
    action: str,
) -> PlanResolutionResult | None:
    """Return a prior successful result for an opaque conflict generation."""
    _, separator, resolution_identity = reconciliation_id.partition("@")
    if not separator or not resolution_identity:
        return None
    idempotency_key = _resolution_key(action, resolution_identity)
    revision = _existing_revision(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
    )
    if revision is None or not revision.after_snapshot:
        return None
    snapshot = dict(revision.after_snapshot[0] or {})
    canonical_id = str(snapshot.get("canonical_id") or "").strip()
    if not canonical_id:
        return None
    if action == "accept_target":
        external_id = str(
            (revision.details or {}).get("external_id") or ""
        ).strip() or None
        return PlanResolutionResult(
            action=action,
            reconciliation_id=reconciliation_id,
            revision_id=revision.id,
            canonical_id=canonical_id,
            external_id=external_id,
        )

    canonical_key = canonical_workout_key(snapshot)
    expected_plan_version = workout_version(snapshot)
    completed_attempts = db.execute(
        select(PlanDeliveryAttempt, PlanDelivery)
        .join(
            PlanDelivery,
            PlanDelivery.id == PlanDeliveryAttempt.delivery_id,
        )
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.canonical_key == canonical_key,
            PlanDelivery.plan_version == expected_plan_version,
            PlanDeliveryAttempt.operation.in_(("deliver", "import")),
            PlanDeliveryAttempt.state == "synced",
            PlanDeliveryAttempt.completed_at.is_not(None),
            PlanDeliveryAttempt.completed_at >= revision.created_at,
        )
        .order_by(
            PlanDeliveryAttempt.completed_at.desc(),
            PlanDeliveryAttempt.id.desc(),
        )
    ).all()
    completed_attempt = next(
        (
            (attempt, delivery)
            for attempt, delivery in completed_attempts
            if attempt.operation == "deliver"
            or (
                isinstance(attempt.response, dict)
                and attempt.response.get("resolution") == "restore_praxys"
                and attempt.response.get("revision_id") == revision.id
            )
        ),
        None,
    )
    if completed_attempt is None:
        return None
    attempt, delivery = completed_attempt
    return PlanResolutionResult(
        action=action,
        reconciliation_id=reconciliation_id,
        revision_id=revision.id,
        canonical_id=canonical_id,
        external_id=attempt.external_id or delivery.external_id,
    )


_PLAN_FIELDS = (
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


def _resolution_key(action: str, *parts: object) -> str:
    raw = "|".join([action, *(str(part or "") for part in parts)])
    return f"plan-reconcile:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _parse_start_time(value: Any) -> datetime | None:
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


def _apply_target_snapshot(
    plan: TrainingPlan,
    snapshot: Mapping[str, Any],
) -> None:
    workout_date = snapshot.get("date")
    if not isinstance(workout_date, str):
        raise PlanResolutionConflict("Target workout has no usable date")
    plan.date = date.fromisoformat(workout_date)
    for field in _PLAN_FIELDS:
        setattr(plan, field, snapshot.get(field))
    plan.start_time = _parse_start_time(snapshot.get("start_time"))
    plan.source = "ai"
    plan.external_id = None


def _existing_revision(
    db: Session,
    *,
    user_id: str,
    idempotency_key: str,
) -> PlanRevision | None:
    return db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()


def accept_target_version(
    db: Session,
    *,
    user_id: str,
    target: str,
    item: PlanReconciliationItem,
) -> PlanResolutionResult:
    """Transactionally adopt one observed target workout as canonical."""
    if item.observation is None or not item.observation.present:
        raise PlanResolutionConflict("Target workout is no longer present")
    observation_id = item.observation.id
    canonical_id = (
        item.canonical.canonical_id
        if item.canonical is not None
        else None
    )
    prior_delivery_id = (
        item.delivery.id if item.delivery is not None else None
    )
    idempotency_key = _resolution_key(
        "accept_target",
        item.resolution_identity,
    )

    db.rollback()
    lock_plan_writes(db, user_id)
    existing_revision = _existing_revision(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
    )
    if existing_revision is not None:
        accepted_delivery = db.execute(
            select(PlanDelivery)
            .where(
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == target,
                PlanDelivery.external_id == item.observation.external_id,
                PlanDelivery.state == "synced",
            )
            .order_by(
                PlanDelivery.updated_at.desc(),
                PlanDelivery.created_at.desc(),
            )
        ).scalars().first()
        if accepted_delivery is None:
            raise PlanResolutionConflict(
                "Prior target acceptance did not finish"
            )
        canonical_id = accepted_delivery.canonical_key.split(":", 1)[-1]
        accepted_canonical = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source == "ai",
                TrainingPlan.canonical_id == canonical_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if (
            accepted_canonical is None
            or accepted_delivery.plan_version
            != workout_version(plan_snapshot(accepted_canonical))
        ):
            raise PlanResolutionConflict(
                "Canonical workout changed after reconciliation"
            )
        return PlanResolutionResult(
            action="accept_target",
            reconciliation_id=item.opaque_id,
            revision_id=existing_revision.id,
            canonical_id=canonical_id,
            external_id=accepted_delivery.external_id,
        )

    calendar_sync = db.execute(
        select(PlanTargetCalendarSync)
        .where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
        )
        .with_for_update()
    ).scalar_one()
    observation = db.execute(
        select(PlanTargetWorkout)
        .where(
            PlanTargetWorkout.id == observation_id,
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
        )
        .with_for_update()
    ).scalar_one()
    if (
        not observation.present
        or observation.provider_account_id
        != calendar_sync.provider_account_id
    ):
        raise PlanResolutionConflict(
            "Target workout changed after reconciliation"
        )

    canonical = None
    if canonical_id is not None:
        canonical = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source == "ai",
                TrainingPlan.canonical_id == canonical_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if canonical is None:
            raise PlanResolutionConflict(
                "Canonical workout changed after reconciliation"
            )
    current_delivery = None
    if prior_delivery_id is not None:
        current_delivery = db.execute(
            select(PlanDelivery)
            .where(
                PlanDelivery.id == prior_delivery_id,
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == target,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if current_delivery is None:
            raise PlanResolutionConflict(
                "Delivery changed after reconciliation"
            )
    else:
        active_delivery = db.execute(
            select(PlanDelivery)
            .where(
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == target,
                PlanDelivery.external_id == observation.external_id,
                PlanDelivery.state != "removed",
            )
            .with_for_update()
        ).scalars().first()
        if active_delivery is not None:
            raise PlanResolutionConflict(
                "Target workout is already managed by another delivery"
            )
    if not item.matches_current(
        canonical=canonical,
        observation=observation,
        delivery=current_delivery,
    ):
        raise PlanResolutionConflict(
            "Plan reconciliation changed before acceptance"
        )
    before = [plan_snapshot(canonical)] if canonical is not None else []
    if canonical is None:
        canonical = TrainingPlan(user_id=user_id, source="ai")
        db.add(canonical)

    target_snapshot = dict(observation.normalized_workout or {})
    _apply_target_snapshot(canonical, target_snapshot)
    prior_meta = dict(canonical.meta or {})
    prior_meta["accepted_from_target"] = {
        "target": target,
        "external_id": observation.external_id,
        "provider_account_id": observation.provider_account_id,
        "content_fingerprint": observation.content_fingerprint,
        "observed_at": observation.observed_at.isoformat(),
    }
    canonical.meta = prior_meta
    db.flush()
    after = [plan_snapshot(canonical)]

    revision, _ = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation="accept_target",
        actor_type="user",
        actor_id=user_id,
        origin="api.plan.reconciliation.accept",
        before=before,
        after=after,
        details={
            "target": target,
            "target_workout_id": observation.id,
            "external_id": observation.external_id,
            "provider_account_id": observation.provider_account_id,
            "content_fingerprint": observation.content_fingerprint,
        },
        idempotency_key=idempotency_key,
    )

    canonical_snapshot = plan_snapshot(canonical)
    accepted_delivery, _ = get_or_create_delivery(
        db,
        user_id=user_id,
        target=target,
        snapshot=canonical_snapshot,
        workout_version_override=(
            observation.payload_fingerprint
            or observation.content_fingerprint
            or workout_version(canonical_snapshot)
        ),
        provider_content_version_override=observation.content_fingerprint,
    )
    previous_delivery = current_delivery
    now = datetime.utcnow()
    if (
        previous_delivery is not None
        and previous_delivery.id != accepted_delivery.id
        and previous_delivery.state != "removed"
    ):
        previous_delivery.state = "removed"
        previous_delivery.updated_at = now
        append_delivery_event(
            db,
            previous_delivery,
            operation="import",
            state="removed",
            external_id=previous_delivery.external_id,
            response={
                "resolution": "accept_target",
                "revision_id": revision.id,
                "superseded_by": accepted_delivery.id,
            },
            completed_at=now,
        )

    accepted_delivery.state = "synced"
    accepted_delivery.external_id = observation.external_id
    accepted_delivery.provider_account_id = observation.provider_account_id
    accepted_delivery.provider_content_version = (
        observation.content_fingerprint
    )
    accepted_delivery.last_error = None
    accepted_delivery.delivered_at = observation.observed_at
    accepted_delivery.updated_at = now
    append_delivery_event(
        db,
        accepted_delivery,
        operation="import",
        state="synced",
        external_id=observation.external_id,
        response={
            "resolution": "accept_target",
            "revision_id": revision.id,
            "target_workout_id": observation.id,
        },
        completed_at=now,
    )
    bump_revisions(db, user_id, ["plans"])
    db.commit()
    return PlanResolutionResult(
        action="accept_target",
        reconciliation_id=item.opaque_id,
        revision_id=revision.id,
        canonical_id=canonical.canonical_id,
        external_id=observation.external_id,
    )


def _record_restore_revision(
    db: Session,
    *,
    user_id: str,
    target: str,
    item: PlanReconciliationItem,
    canonical: TrainingPlan,
) -> tuple[PlanRevision, dict[str, Any], str]:
    snapshot = plan_snapshot(canonical)
    current_version = workout_version(snapshot)
    idempotency_key = _resolution_key(
        "restore_praxys",
        item.resolution_identity,
    )
    revision, _ = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation="restore_target",
        actor_type="user",
        actor_id=user_id,
        origin="api.plan.reconciliation.restore",
        before=[snapshot],
        after=[snapshot],
        details={
            "target": target,
            "reconciliation_id": item.opaque_id,
            "state": item.state,
            "external_id": (
                item.observation.external_id
                if item.observation is not None
                else item.delivery.external_id
                if item.delivery is not None
                else None
            ),
        },
        idempotency_key=idempotency_key,
    )
    db.commit()
    return revision, snapshot, current_version


def _bind_confirmed_restore(
    db: Session,
    *,
    user_id: str,
    target: str,
    canonical_id: str,
    prior_delivery_id: str,
    observation_id: str,
    prepared_version: str,
    content_version: str,
    expected_plan_version: str,
    reconciliation_id: str,
    revision_id: str,
) -> PlanResolutionResult:
    lock_plan_writes(db, user_id)
    canonical = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source == "ai",
            TrainingPlan.canonical_id == canonical_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if (
        canonical is None
        or workout_version(plan_snapshot(canonical)) != expected_plan_version
    ):
        raise PlanResolutionConflict(
            "Canonical workout changed during restore"
        )
    observation = db.execute(
        select(PlanTargetWorkout)
        .where(
            PlanTargetWorkout.id == observation_id,
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
        )
        .with_for_update()
    ).scalar_one()
    if not observation.present:
        raise PlanResolutionConflict(
            "Target workout changed after reconciliation"
        )
    delivery, _ = get_or_create_delivery(
        db,
        user_id=user_id,
        target=target,
        snapshot=plan_snapshot(canonical),
        workout_version_override=prepared_version,
        provider_content_version_override=content_version,
    )
    prior_delivery = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.id == prior_delivery_id,
            PlanDelivery.user_id == user_id,
        )
    ).scalar_one()
    now = datetime.utcnow()
    if prior_delivery.id != delivery.id and prior_delivery.state != "removed":
        prior_delivery.state = "removed"
        prior_delivery.updated_at = now
        append_delivery_event(
            db,
            prior_delivery,
            operation="import",
            state="removed",
            external_id=prior_delivery.external_id,
            response={
                "resolution": "restore_praxys",
                "revision_id": revision_id,
                "superseded_by": delivery.id,
            },
            completed_at=now,
        )
    delivery.state = "synced"
    delivery.external_id = observation.external_id
    delivery.provider_account_id = observation.provider_account_id
    delivery.provider_content_version = content_version
    delivery.last_error = None
    delivery.delivered_at = observation.observed_at
    delivery.updated_at = now
    import_events = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.delivery_id == delivery.id,
            PlanDeliveryAttempt.operation == "import",
        )
    ).scalars().all()
    existing_event = any(
        isinstance(event.response, dict)
        and event.response.get("revision_id") == revision_id
        for event in import_events
    )
    if not existing_event:
        append_delivery_event(
            db,
            delivery,
            operation="import",
            state="synced",
            external_id=observation.external_id,
            response={
                "resolution": "restore_praxys",
                "confirmed_existing": True,
                "revision_id": revision_id,
                "target_workout_id": observation.id,
            },
            completed_at=now,
        )
    bump_revisions(db, user_id, ["plans"])
    db.commit()
    return PlanResolutionResult(
        action="restore_praxys",
        reconciliation_id=reconciliation_id,
        revision_id=revision_id,
        canonical_id=canonical_id,
        external_id=observation.external_id,
    )


def _assert_canonical_version(
    db: Session,
    *,
    user_id: str,
    canonical_id: str,
    expected_plan_version: str,
) -> None:
    db.rollback()
    lock_plan_writes(db, user_id)
    canonical = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source == "ai",
            TrainingPlan.canonical_id == canonical_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    unchanged = (
        canonical is not None
        and workout_version(plan_snapshot(canonical)) == expected_plan_version
    )
    db.rollback()
    if not unchanged:
        raise PlanResolutionConflict(
            "Canonical workout changed during restore"
        )


def _assert_resolution_generation(
    db: Session,
    *,
    user_id: str,
    target: str,
    item: PlanReconciliationItem,
) -> None:
    db.rollback()
    lock_plan_writes(db, user_id)
    canonical = None
    if item.canonical is not None:
        canonical = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source == "ai",
                TrainingPlan.canonical_id == item.canonical.canonical_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
    observation = None
    if item.observation is not None:
        observation = db.execute(
            select(PlanTargetWorkout)
            .where(
                PlanTargetWorkout.id == item.observation.id,
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.target == target,
            )
            .with_for_update()
        ).scalar_one_or_none()
    delivery = None
    if item.delivery is not None:
        delivery = db.execute(
            select(PlanDelivery)
            .where(
                PlanDelivery.id == item.delivery.id,
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == target,
            )
            .with_for_update()
        ).scalar_one_or_none()
    matches = item.matches_current(
        canonical=canonical,
        observation=observation,
        delivery=delivery,
    )
    db.rollback()
    if not matches:
        raise PlanResolutionConflict(
            "Plan reconciliation changed before provider mutation"
        )


def _release_conflict_after_confirmed_absence(
    db: Session,
    *,
    user_id: str,
    target: str,
    delivery_id: str,
    provider_account_id: str,
    revision_id: str,
) -> None:
    db.rollback()
    lock_plan_writes(db, user_id)
    delivery = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.id == delivery_id,
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
        )
        .with_for_update()
    ).scalar_one()
    if delivery.state != "conflict":
        db.rollback()
        return
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync)
        .where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
        )
        .with_for_update()
    ).scalar_one_or_none()
    reference_time = delivery.updated_at
    if (
        calendar_sync is None
        or calendar_sync.provider_account_id != provider_account_id
        or not (
            calendar_sync.window_start
            <= delivery.workout_date
            <= calendar_sync.window_end
        )
        or calendar_sync.synced_at < reference_time
    ):
        db.rollback()
        raise PlanResolutionConflict(
            "Sync the target calendar before retrying this uncertain delivery"
        )
    observation_query = select(PlanTargetWorkout.id).where(
        PlanTargetWorkout.user_id == user_id,
        PlanTargetWorkout.target == target,
        PlanTargetWorkout.provider_account_id == provider_account_id,
        PlanTargetWorkout.present.is_(True),
    )
    if delivery.provider_content_version:
        observation_query = observation_query.where(
            PlanTargetWorkout.content_fingerprint
            == delivery.provider_content_version,
        )
    elif not delivery.workout_version.startswith("legacy-unknown:"):
        observation_query = observation_query.where(
            PlanTargetWorkout.payload_fingerprint
            == delivery.workout_version,
        )
    else:
        db.rollback()
        raise PlanResolutionConflict(
            "The uncertain delivery has no verifiable original fingerprint"
        )
    matching_observation = db.execute(
        observation_query
    ).scalars().first()
    if matching_observation is not None:
        db.rollback()
        raise PlanResolutionConflict(
            "The uncertain delivery is still present on the target calendar"
        )

    now = datetime.utcnow()
    delivery.state = "failed"
    delivery.last_error = None
    delivery.updated_at = now
    append_delivery_event(
        db,
        delivery,
        operation="import",
        state="failed",
        external_id=delivery.external_id,
        response={
            "resolution": "restore_praxys",
            "revision_id": revision_id,
            "confirmed_absent": True,
            "calendar_synced_at": calendar_sync.synced_at.isoformat(),
        },
        completed_at=now,
    )
    bump_revisions(db, user_id, ["plans"])
    db.commit()


def _record_restore_preflight_failure(
    db: Session,
    *,
    user_id: str,
    delivery_id: str,
    revision_id: str,
    error: Exception,
) -> None:
    """Best-effort delivery event for a restore that failed before provider I/O."""
    try:
        db.rollback()
        lock_plan_writes(db, user_id)
        delivery = db.execute(
            select(PlanDelivery).where(
                PlanDelivery.id == delivery_id,
                PlanDelivery.user_id == user_id,
            )
        ).scalar_one()
        append_delivery_event(
            db,
            delivery,
            operation="deliver",
            state="failed",
            external_id=delivery.external_id,
            error=str(error),
            response={
                "resolution": "restore_praxys",
                "revision_id": revision_id,
                "preflight": True,
            },
        )
        bump_revisions(db, user_id, ["plans"])
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Could not record restore preflight failure user=%s delivery=%s",
            user_id,
            delivery_id,
        )


def restore_praxys_version(
    db: Session,
    *,
    user_id: str,
    target: str,
    item: PlanReconciliationItem,
    threshold_value: float,
    adapter_loader: Callable[[], PlanDeliveryAdapter],
) -> PlanResolutionResult:
    """Restore the current canonical version with retry-safe provider writes."""
    if item.canonical is None or item.delivery is None:
        raise PlanResolutionConflict(
            "This reconciliation item has no Praxys delivery to restore"
        )
    canonical_id = item.canonical.canonical_id
    prior_delivery_id = item.delivery.id

    db.rollback()
    lock_plan_writes(db, user_id)
    canonical = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source == "ai",
            TrainingPlan.canonical_id == canonical_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if canonical is None:
        raise PlanResolutionConflict(
            "Canonical workout changed after reconciliation"
        )
    current_delivery = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.id == prior_delivery_id,
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
        )
        .with_for_update()
    ).scalar_one_or_none()
    current_observation = None
    if item.observation is not None:
        current_observation = db.execute(
            select(PlanTargetWorkout)
            .where(
                PlanTargetWorkout.id == item.observation.id,
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.target == target,
            )
            .with_for_update()
        ).scalar_one_or_none()
    if (
        current_delivery is None
        or not item.matches_current(
            canonical=canonical,
            observation=current_observation,
            delivery=current_delivery,
        )
    ):
        raise PlanResolutionConflict(
            "Plan reconciliation changed before restore"
        )
    revision, snapshot, expected_plan_version = _record_restore_revision(
        db,
        user_id=user_id,
        target=target,
        item=item,
        canonical=canonical,
    )

    try:
        adapter = adapter_loader()
        prepared = adapter.prepare_workout(
            snapshot,
            threshold_value=threshold_value,
        )
        adapter.authenticate()
        provider_account_id = adapter.account_id
        if (
            item.delivery.provider_account_id
            and item.delivery.provider_account_id != provider_account_id
        ):
            raise PlanResolutionConflict(
                "Delivery belongs to a different provider account"
            )
    except Exception as exc:
        _record_restore_preflight_failure(
            db,
            user_id=user_id,
            delivery_id=prior_delivery_id,
            revision_id=revision.id,
            error=exc,
        )
        raise

    observation = item.observation
    content_version = prepared.content_version or prepared.version
    _assert_resolution_generation(
        db,
        user_id=user_id,
        target=target,
        item=item,
    )
    if observation is not None and observation.present:
        if observation.provider_account_id != provider_account_id:
            raise PlanResolutionConflict(
                "Target workout belongs to a different provider account"
            )
        if observation.content_fingerprint == content_version:
            return _bind_confirmed_restore(
                db,
                user_id=user_id,
                target=target,
                canonical_id=canonical_id,
                prior_delivery_id=prior_delivery_id,
                observation_id=observation.id,
                prepared_version=prepared.version,
                content_version=content_version,
                expected_plan_version=expected_plan_version,
                reconciliation_id=item.opaque_id,
                revision_id=revision.id,
            )
        if (
            item.delivery.external_id
            and observation.external_id != item.delivery.external_id
        ):
            raise PlanResolutionConflict(
                "The changed target workout is not owned by this delivery"
            )

    _release_conflict_after_confirmed_absence(
        db,
        user_id=user_id,
        target=target,
        delivery_id=prior_delivery_id,
        provider_account_id=provider_account_id,
        revision_id=revision.id,
    )
    service = PlanDeliveryService(
        db=db,
        user_id=user_id,
        target=target,
        adapter_loader=lambda: adapter,
    )
    if item.delivery.external_id and item.delivery.state != "removed":
        _assert_resolution_generation(
            db,
            user_id=user_id,
            target=target,
            item=item,
        )
        service.remove(item.delivery.external_id)
    _assert_resolution_generation(
        db,
        user_id=user_id,
        target=target,
        item=item,
    )
    outcome = service.deliver(
        snapshot,
        threshold_value=threshold_value,
        observed_external_ids=None,
    )
    if outcome.status != "success" or not outcome.external_id:
        raise PlanResolutionProviderError(
            outcome.error or "Provider restore did not complete"
        )
    _assert_canonical_version(
        db,
        user_id=user_id,
        canonical_id=canonical_id,
        expected_plan_version=expected_plan_version,
    )
    return PlanResolutionResult(
        action="restore_praxys",
        reconciliation_id=item.opaque_id,
        revision_id=revision.id,
        canonical_id=canonical_id,
        external_id=outcome.external_id,
    )
