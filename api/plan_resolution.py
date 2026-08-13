"""Explicit, auditable plan reconciliation resolution operations."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from analysis.config import (
    PRAXYS_PLAN_SOURCES,
    PRAXYS_PLAN_WRITE_SOURCE,
)
from analysis.metrics import is_rest_workout
from api.plan_delivery.base import (
    PlanDeliveryAdapter,
    ProviderAuthenticationError,
    ProviderRequestError,
    adapter_provider_account_matches,
)
from api.plan_delivery.credentials import (
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
)
from api.plan_delivery.service import (
    DeliveryMutationBlockedError,
    PlanDeliveryService,
)
from api.plan_reconciliation import (
    PlanReconciliationItem,
    observation_matches_calendar,
    plan_target_calendar_generation,
)
from api.plan_workout_structure import (
    default_activity_type,
    inspect_workout_structure,
    normalize_activity_type,
    validate_structured_workout,
)
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
    delivery_canonical_id,
    get_or_create_delivery,
    lock_plan_writes,
    normalize_provider_references,
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


class PlanResolutionRateLimitError(PlanResolutionProviderError):
    """The provider rate-limited a requested restore."""


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
    canonical_id = str(snapshot.get("canonical_id") or "").strip() or None
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
            (
                or_(
                    PlanDelivery.canonical_id == canonical_id,
                    PlanDelivery.canonical_key == canonical_key,
                )
                if canonical_id
                else PlanDelivery.canonical_key == canonical_key
            ),
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


def resumable_plan_resolution(
    db: Session,
    *,
    user_id: str,
    target: str,
    reconciliation_id: str,
    action: str,
) -> bool:
    """Return whether an exact restore has a proven interrupted removal."""
    base_id, separator, resolution_identity = reconciliation_id.partition("@")
    if not separator or not resolution_identity:
        return False
    revision = _existing_revision(
        db,
        user_id=user_id,
        idempotency_key=_resolution_key(action, resolution_identity),
    )
    details = revision.details if revision is not None else None
    if (
        revision is None
        or revision.operation != "restore_target"
        or not isinstance(details, Mapping)
        or details.get("target") != target
        or details.get("reconciliation_id") != reconciliation_id
        or not base_id.startswith("delivery:")
    ):
        return False
    delivery = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.id == base_id.removeprefix("delivery:"),
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
        )
    ).scalar_one_or_none()
    if delivery is None or delivery.state not in {"removed", "failed"}:
        return False
    attempts = db.execute(
        select(PlanDeliveryAttempt).where(
            PlanDeliveryAttempt.delivery_id == delivery.id,
            PlanDeliveryAttempt.completed_at.is_not(None),
        )
    ).scalars().all()

    def belongs_to_restore(
        attempt: PlanDeliveryAttempt,
        *,
        operation: str,
        state: str,
    ) -> bool:
        response = attempt.response
        return bool(
            attempt.operation == operation
            and attempt.state == state
            and isinstance(response, Mapping)
            and response.get("resolution") == "restore_praxys"
            and response.get("revision_id") == revision.id
        )

    removal_completed = any(
        belongs_to_restore(
            attempt,
            operation="remove",
            state="removed",
        )
        for attempt in attempts
    )
    if not removal_completed:
        return False
    return delivery.state == "removed" or any(
        belongs_to_restore(
            attempt,
            operation="deliver",
            state="failed",
        )
        for attempt in attempts
    )


_FLAT_PLAN_FIELDS = (
    "planned_duration_min",
    "planned_distance_km",
    "target_power_min",
    "target_power_max",
    "target_hr_min",
    "target_hr_max",
    "target_pace_min",
    "target_pace_max",
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
    try:
        normalized_date = date.fromisoformat(workout_date)
    except ValueError as exc:
        raise PlanResolutionConflict(
            "Target workout has no usable date"
        ) from exc
    workout_type = str(snapshot.get("workout_type") or "")
    status = str(
        snapshot.get("workout_structure_status") or ""
    ).strip()
    if status not in {"", "absent", "supported"}:
        raise PlanResolutionConflict(
            "Target workout structure cannot be represented safely"
        )
    inspection = inspect_workout_structure(
        workout_structure_version=snapshot.get(
            "workout_structure_version"
        ),
        workout_structure=snapshot.get("workout_structure"),
    )
    if (
        status == "absent"
        and inspection.state != "absent"
    ) or (
        status == "supported"
        and inspection.state != "supported"
    ):
        raise PlanResolutionConflict(
            "Target workout structure cannot be represented safely"
        )
    activity_type = str(
        snapshot.get("activity_type")
        or default_activity_type(workout_type)
    )
    values: dict[str, Any] = {
        field: snapshot.get(field)
        for field in _FLAT_PLAN_FIELDS
    }
    try:
        if inspection.state == "absent":
            normalized_activity = normalize_activity_type(
                workout_type,
                activity_type,
            )
            normalized_version = None
            normalized_structure = None
            if is_rest_workout(workout_type):
                values = {
                    field: None for field in _FLAT_PLAN_FIELDS
                }
        elif (
            inspection.state == "supported"
            and inspection.structure is not None
        ):
            (
                normalized_activity,
                normalized_structure,
                values,
            ) = validate_structured_workout(
                workout_type=workout_type,
                activity_type=activity_type,
                workout_structure_version="v1",
                workout_structure=inspection.structure,
            )
            normalized_version = "v1"
        else:
            raise ValueError("unsafe target structure")
    except (TypeError, ValueError) as exc:
        raise PlanResolutionConflict(
            "Target workout structure cannot be represented safely"
        ) from exc
    raw_start_time = snapshot.get("start_time")
    normalized_start_time = _parse_start_time(raw_start_time)
    if raw_start_time not in (None, "") and normalized_start_time is None:
        raise PlanResolutionConflict(
            "Target workout has no usable start time"
        )

    # Validation above completes before any canonical field is mutated.
    plan.date = normalized_date
    plan.activity_type = normalized_activity
    plan.workout_type = workout_type
    for field in _FLAT_PLAN_FIELDS:
        setattr(plan, field, values.get(field))
    plan.workout_description = str(
        snapshot.get("workout_description") or ""
    )
    plan.workout_structure_version = normalized_version
    plan.workout_structure = normalized_structure
    plan.start_time = normalized_start_time
    plan.source = PRAXYS_PLAN_WRITE_SOURCE
    plan.workout_origin = "accepted_target"
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
        canonical_id = delivery_canonical_id(accepted_delivery)
        if canonical_id is None:
            raise PlanResolutionConflict(
                "Prior target acceptance has no canonical identity"
            )
        accepted_canonical = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
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
        or not observation_matches_calendar(calendar_sync, observation)
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
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
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
        calendar_generation=(
            _locked_target_calendar_generation(
                db,
                user_id=user_id,
                target=target,
            )
            if item.calendar_generation is not None
            else None
        ),
    ):
        raise PlanResolutionConflict(
            "Plan reconciliation changed before acceptance"
        )
    before = [plan_snapshot(canonical)] if canonical is not None else []
    if canonical is None:
        canonical = TrainingPlan(
            user_id=user_id,
            source=PRAXYS_PLAN_WRITE_SOURCE,
            workout_origin="accepted_target",
        )
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
    accepted_delivery.provider_references = (
        _merged_delivery_provider_references(
            target=target,
            external_id=observation.external_id,
            references=(
                current_delivery.provider_references
                if current_delivery is not None
                else None,
                accepted_delivery.provider_references,
                observation.provider_references,
            ),
        )
    )
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
    actor_type: str,
    actor_id: str | None,
    origin: str,
    trigger: str | None,
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
        actor_type=actor_type,
        actor_id=actor_id,
        origin=origin,
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
            **({"trigger": trigger} if trigger else {}),
        },
        idempotency_key=idempotency_key,
    )
    db.commit()
    return revision, snapshot, current_version


def _merged_delivery_provider_references(
    *,
    target: str,
    external_id: str | None,
    references: Sequence[Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Merge durable delivery evidence with one observed provider identity."""
    merged: dict[str, Any] = {}
    for source in references:
        merged.update(dict(source or {}))
    if target == "garmin" and external_id:
        merged["schedule_id"] = external_id
    return normalize_provider_references(merged)


def _garmin_restorable_schedule_ids(delivery: PlanDelivery) -> set[str]:
    """Return Garmin schedule IDs safe to bind from matching observations."""
    references = delivery.provider_references or {}
    schedule_ids = {
        value
        for raw in (
            references.get("schedule_id"),
            delivery.external_id,
        )
        if (value := str(raw or "").strip())
    }
    returned_schedule_id = str(
        references.get("returned_schedule_id") or ""
    ).strip()
    if (
        not returned_schedule_id
        or references.get("schedule_started") is not True
        or references.get("unexpected_schedule_date")
    ):
        return schedule_ids
    raw_preexisting_schedule_ids = references.get(
        "preexisting_schedule_ids"
    )
    if not isinstance(raw_preexisting_schedule_ids, list):
        return schedule_ids
    preexisting_schedule_ids = {
        value
        for raw in raw_preexisting_schedule_ids
        if (value := str(raw or "").strip())
    }
    returned_preexisting_id = str(
        references.get("returned_preexisting_schedule_id") or ""
    ).strip()
    if (
        returned_schedule_id not in preexisting_schedule_ids
        and returned_schedule_id != returned_preexisting_id
    ):
        schedule_ids.add(returned_schedule_id)
    return schedule_ids


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
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
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
    delivery.provider_references = _merged_delivery_provider_references(
        target=target,
        external_id=observation.external_id,
        references=(
            prior_delivery.provider_references,
            delivery.provider_references,
            observation.provider_references,
        ),
    )
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
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
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


def _locked_target_calendar_generation(
    db: Session,
    *,
    user_id: str,
    target: str,
    presence_overrides: Mapping[str, bool] | None = None,
) -> str | None:
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync)
        .where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if calendar_sync is None:
        return None
    observations = db.execute(
        select(PlanTargetWorkout)
        .where(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    observations = [
        observation
        for observation in observations
        if observation_matches_calendar(calendar_sync, observation)
    ]
    return plan_target_calendar_generation(
        calendar_sync,
        observations,
        presence_overrides=presence_overrides,
    )


def _calendar_presence_overrides(
    item: PlanReconciliationItem,
) -> dict[str, bool] | None:
    if item.observation is None:
        return None
    return {
        item.observation.id: bool(item.calendar_observation_present),
    }


def _restore_provider_mutation_guard(
    db: Session,
    *,
    user_id: str,
    target: str,
    item: PlanReconciliationItem,
    canonical_id: str,
    expected_plan_version: str,
    connection_guard: Callable[[], None] | None,
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Hold the plan-write fence while revalidating one restore mutation."""
    expected_observation_present = {"value": item.observation_present}
    generation_presence_overrides = _calendar_presence_overrides(item)

    def guard() -> None:
        if connection_guard is not None:
            connection_guard()
        lock_plan_writes(db, user_id)
        canonical = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                TrainingPlan.canonical_id == canonical_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if (
            canonical is None
            or workout_version(plan_snapshot(canonical))
            != expected_plan_version
        ):
            raise DeliveryMutationBlockedError(
                "canonical_changed_during_restore"
            )
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
                .execution_options(populate_existing=True)
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
                .execution_options(populate_existing=True)
            ).scalar_one_or_none()
        if not item.matches_current(
            canonical=canonical,
            observation=observation,
            delivery=delivery,
            calendar_generation=(
                _locked_target_calendar_generation(
                    db,
                    user_id=user_id,
                    target=target,
                    presence_overrides=generation_presence_overrides,
                )
                if item.calendar_generation is not None
                else None
            ),
        ):
            raise DeliveryMutationBlockedError(
                "reconciliation_changed_during_restore"
            )
        if (
            observation is not None
            and bool(observation.present)
            != expected_observation_present["value"]
        ):
            raise DeliveryMutationBlockedError(
                "reconciliation_changed_during_restore"
            )

    def expect_removed_observation() -> None:
        if item.observation is not None:
            expected_observation_present["value"] = False

    return guard, expect_removed_observation


def _assert_resolution_generation(
    db: Session,
    *,
    user_id: str,
    target: str,
    item: PlanReconciliationItem,
    expected_observation_present: bool | None = None,
) -> None:
    db.rollback()
    lock_plan_writes(db, user_id)
    canonical = None
    if item.canonical is not None:
        canonical = db.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
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
        if expected_observation_present is None:
            expected_observation_present = item.observation_present
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
        calendar_generation=(
            _locked_target_calendar_generation(
                db,
                user_id=user_id,
                target=target,
                presence_overrides=_calendar_presence_overrides(item),
            )
            if item.calendar_generation is not None
            else None
        ),
    )
    if (
        observation is not None
        and bool(observation.present) != expected_observation_present
    ):
        matches = False
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
    adapter: PlanDeliveryAdapter,
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
        or not adapter_provider_account_matches(
            adapter,
            stored_account_id=calendar_sync.provider_account_id,
            current_account_id=adapter.account_id,
            provider_references=calendar_sync.provider_references or {},
        )
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
    observation_query = select(PlanTargetWorkout).where(
        PlanTargetWorkout.user_id == user_id,
        PlanTargetWorkout.target == target,
        PlanTargetWorkout.present.is_(True),
    )
    if delivery.external_id:
        observation_query = observation_query.where(
            PlanTargetWorkout.external_id == delivery.external_id,
        )
    else:
        observation_query = observation_query.where(
            PlanTargetWorkout.workout_date == delivery.workout_date,
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
    matching_observation = next(
        (
            observation
            for observation in db.execute(
                observation_query
            ).scalars().all()
            if observation_matches_calendar(calendar_sync, observation)
        ),
        None,
    )
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
    canonical_version: str,
    attempt_context: Mapping[str, Any] | None,
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
                **dict(attempt_context or {}),
                "resolution": "restore_praxys",
                "revision_id": revision_id,
                "preflight": True,
                "canonical_version": canonical_version,
                "error_category": (
                    "invalid_workout"
                    if isinstance(error, ProviderRequestError)
                    else "provider_authentication"
                    if isinstance(
                        error,
                        (
                            DeliveryCredentialsInvalid,
                            DeliveryCredentialsUnavailable,
                            ProviderAuthenticationError,
                        ),
                    )
                    else "reconciliation_required"
                ),
                "retryable": isinstance(
                    error,
                    (
                        DeliveryCredentialsInvalid,
                        DeliveryCredentialsUnavailable,
                        ProviderAuthenticationError,
                    ),
                ),
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
    actor_type: str = "user",
    actor_id: str | None = None,
    origin: str = "api.plan.reconciliation.restore",
    trigger: str | None = None,
    attempt_context: Mapping[str, Any] | None = None,
    mutation_guard: Callable[[], None] | None = None,
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
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
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
        or (
            current_observation is not None
            and bool(current_observation.present)
            != item.observation_present
        )
        or not item.matches_current(
            canonical=canonical,
            observation=current_observation,
            delivery=current_delivery,
            calendar_generation=(
                _locked_target_calendar_generation(
                    db,
                    user_id=user_id,
                    target=target,
                    presence_overrides=_calendar_presence_overrides(item),
                )
                if item.calendar_generation is not None
                else None
            ),
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
        actor_type=actor_type,
        actor_id=(
            user_id
            if actor_type == "user" and actor_id is None
            else actor_id
        ),
        origin=origin,
        trigger=trigger,
    )
    (
        provider_mutation_guard,
        expect_removed_observation,
    ) = _restore_provider_mutation_guard(
        db,
        user_id=user_id,
        target=target,
        item=item,
        canonical_id=canonical_id,
        expected_plan_version=expected_plan_version,
        connection_guard=mutation_guard,
    )

    try:
        adapter = adapter_loader()
        prepared = adapter.prepare_workout(
            snapshot,
            threshold_value=threshold_value,
        )
        db.rollback()
        adapter.authenticate()
        provider_account_id = adapter.account_id
        if (
            item.delivery.provider_account_id
            and not adapter_provider_account_matches(
                adapter,
                stored_account_id=item.delivery.provider_account_id,
                current_account_id=provider_account_id,
                provider_references=(
                    item.delivery.provider_references or {}
                ),
            )
        ):
            raise PlanResolutionConflict(
                "Delivery belongs to a different provider account"
            )
    except (
        DeliveryCredentialsInvalid,
        DeliveryCredentialsUnavailable,
        PlanResolutionConflict,
        ProviderAuthenticationError,
        ProviderRequestError,
    ) as exc:
        _record_restore_preflight_failure(
            db,
            user_id=user_id,
            delivery_id=prior_delivery_id,
            revision_id=revision.id,
            error=exc,
            canonical_version=expected_plan_version,
            attempt_context=attempt_context,
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
        if not adapter_provider_account_matches(
            adapter,
            stored_account_id=observation.provider_account_id,
            current_account_id=provider_account_id,
            provider_references=observation.provider_references or {},
        ):
            raise PlanResolutionConflict(
                "Target workout belongs to a different provider account"
            )
        exact_garmin_identity = (
            target != "garmin"
            or observation.external_id
            in _garmin_restorable_schedule_ids(item.delivery)
        )
        if (
            observation.workout_date == item.delivery.workout_date
            and observation.content_fingerprint == content_version
            and exact_garmin_identity
        ):
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

    owned_observation_present = (
        observation is not None
        and observation.present
        and item.delivery.external_id is not None
        and observation.external_id == item.delivery.external_id
    )
    if not owned_observation_present:
        _release_conflict_after_confirmed_absence(
            db,
            user_id=user_id,
            target=target,
            delivery_id=prior_delivery_id,
            adapter=adapter,
            revision_id=revision.id,
        )
    service = PlanDeliveryService(
        db=db,
        user_id=user_id,
        target=target,
        adapter_loader=lambda: adapter,
    )
    removed_owned_observation = False
    owned_observation_already_removed = (
        item.calendar_observation_present is True
        and item.observation_present is False
    )
    if (
        item.delivery.external_id
        and item.delivery.state != "removed"
        and not owned_observation_already_removed
    ):
        _assert_resolution_generation(
            db,
            user_id=user_id,
            target=target,
            item=item,
        )
        service.remove(
            item.delivery.external_id,
            attempt_context={
                **dict(attempt_context or {}),
                "resolution": "restore_praxys",
                "revision_id": revision.id,
            },
            mutation_guard=provider_mutation_guard,
        )
        expect_removed_observation()
        removed_owned_observation = True
    _assert_resolution_generation(
        db,
        user_id=user_id,
        target=target,
        item=item,
        expected_observation_present=(
            False if removed_owned_observation else None
        ),
    )
    outcome = service.deliver(
        snapshot,
        threshold_value=threshold_value,
        observed_external_ids=None,
        attempt_context={
            **dict(attempt_context or {}),
            "resolution": "restore_praxys",
            "revision_id": revision.id,
        },
        mutation_guard=provider_mutation_guard,
    )
    if outcome.error_category == "delivery_gate_changed":
        raise DeliveryMutationBlockedError(
            outcome.error or "Managed delivery gate changed"
        )
    if outcome.error_category == "provider_rate_limited":
        raise PlanResolutionRateLimitError(
            outcome.error or "Provider rate limited the restored workout"
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
