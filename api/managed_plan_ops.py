"""Privacy-safe diagnostics and fenced recovery for managed-plan delivery."""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import PRAXYS_PLAN_SOURCES, normalize_plan_management
from analysis.metrics import is_rest_workout
from api import telemetry
from api.plan_delivery.rolling import (
    AUTOMATIC_DELIVERY_MAX_ATTEMPTS,
    ManagedDeliveryReplayFence,
    ManagedDeliveryRunResult,
    run_rolling_delivery_for_user,
)
from api.views import utc_isoformat
from db.models import (
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanRevision,
    TrainingPlan,
    UserConfig,
)
from db.plan_ledger import (
    DELIVERY_ATTEMPT_LEASE,
    canonical_workout_key,
    delivery_canonical_id,
    lock_plan_writes,
    plan_snapshot,
    record_plan_revision_idempotent,
    workout_version,
)

ManagedPlanAttentionIssue = Literal[
    "stale_pending",
    "stuck_inflight",
    "delivery_failed",
    "retry_exhausted",
    "delivery_conflict",
    "provider_outcome_unknown",
]
ManagedPlanRecoveryBlockedReason = Literal[
    "attempt_not_managed",
    "failure_not_managed",
    "failure_not_retryable",
    "user_resolution_required",
]
ManagedPlanRecoveryStatus = Literal[
    "complete",
    "partial",
    "blocked",
    "skipped",
]

_RECOVERY_ORIGIN = "admin.managed_plan_recovery"
_RECOVERY_REQUEST_LEASE = timedelta(minutes=5)
_ACTIVE_DELIVERY_STATES = (
    "pending",
    "delivering",
    "synced",
    "conflict",
    "failed",
)


class ManagedPlanDeliveryStateCounts(BaseModel):
    """Current future-delivery counts by durable ledger state."""

    pending: int = 0
    delivering: int = 0
    synced: int = 0
    conflict: int = 0
    failed: int = 0


class ManagedPlanHealthData(BaseModel):
    """Aggregate managed-plan health for the admin operations summary."""

    adopted_users: int
    delivery_enabled_users: int
    paused_users: int
    active_deliveries: int
    states: ManagedPlanDeliveryStateCounts
    attention_required: int
    recoverable: int
    retry_exhausted: int
    stuck_inflight: int
    oldest_attention_at: str | None


class ManagedPlanAttentionItem(BaseModel):
    """One pseudonymous operator queue item with no provider payload."""

    recovery_id: str
    user_id_hash: str
    target: str
    state: str
    operation: str | None
    issue: ManagedPlanAttentionIssue
    failure_domain: str
    attempt_count: int
    last_attempt_at: str | None
    updated_at: str
    expected_version: str
    recovery_supported: bool
    recovery_blocked_reason: ManagedPlanRecoveryBlockedReason | None = None


class ManagedPlanAttentionResponse(BaseModel):
    """Bounded admin queue for failed or stuck managed deliveries."""

    generated_at: str
    items: list[ManagedPlanAttentionItem]


class ManagedPlanRecoveryRequest(BaseModel):
    """Optimistic fence supplied by the operator queue."""

    expected_version: str = Field(min_length=20, max_length=64)


class ManagedPlanRecoveryResponse(BaseModel):
    """Privacy-safe result of one reconcile-and-replay request."""

    status: ManagedPlanRecoveryStatus
    target: str
    reason: str | None
    final_state: str
    attempted_items: int
    successful_items: int
    failed_items: int
    blocked_items: int
    audit_revision_id: str


class ManagedPlanRecoveryNotFound(LookupError):
    """The selected delivery no longer exists."""


class ManagedPlanRecoveryStale(RuntimeError):
    """The operator queue version is no longer current."""


class ManagedPlanRecoveryUnsupported(RuntimeError):
    """The selected delivery cannot be replayed without user resolution."""


class ManagedPlanRecoveryBusy(RuntimeError):
    """An equivalent recovery request is already running."""


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _latest_attempts(
    db: Session,
    delivery_ids: list[str],
) -> dict[str, list[PlanDeliveryAttempt]]:
    if not delivery_ids:
        return {}
    rows = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.delivery_id.in_(delivery_ids))
        .order_by(
            PlanDeliveryAttempt.delivery_id,
            PlanDeliveryAttempt.attempt_number,
            PlanDeliveryAttempt.id,
        )
    ).scalars().all()
    grouped: dict[str, list[PlanDeliveryAttempt]] = {}
    for row in rows:
        grouped.setdefault(row.delivery_id, []).append(row)
    return grouped


def _current_canonical(
    db: Session,
    delivery: PlanDelivery,
) -> TrainingPlan | None:
    canonical_id = delivery_canonical_id(delivery)
    query = select(TrainingPlan).where(
        TrainingPlan.user_id == delivery.user_id,
        TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
    )
    if canonical_id is not None:
        query = query.where(TrainingPlan.canonical_id == canonical_id)
    else:
        query = query.where(TrainingPlan.date == delivery.workout_date)
    rows = db.execute(query).scalars().all()
    if canonical_id is None:
        rows = [
            row
            for row in rows
            if canonical_workout_key(plan_snapshot(row))
            == delivery.canonical_key
        ]
    if len(rows) != 1:
        return None
    return rows[0]


def _current_canonical_version(
    db: Session,
    delivery: PlanDelivery,
) -> str | None:
    canonical = _current_canonical(db, delivery)
    return (
        workout_version(plan_snapshot(canonical))
        if canonical is not None
        else None
    )


def _recovery_expected_version(
    db: Session,
    delivery: PlanDelivery,
    attempts: list[PlanDeliveryAttempt],
) -> str:
    latest = attempts[-1] if attempts else None
    material = "|".join((
        utc_isoformat(delivery.updated_at) or "",
        delivery.state,
        str(latest.id if latest is not None else ""),
        latest.operation if latest is not None else "",
        latest.state if latest is not None else "",
        _current_canonical_version(db, delivery) or "canonical_absent",
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _automatic_failure_count(
    attempts: list[PlanDeliveryAttempt],
) -> int:
    last_success_index = max(
        (
            index
            for index, attempt in enumerate(attempts)
            if attempt.state in {"synced", "removed"}
        ),
        default=-1,
    )
    return sum(
        (attempt.response or {}).get("counts_toward_retry_limit", True)
        is not False
        for attempt in attempts[last_success_index + 1:]
        if (
            attempt.state == "failed"
            and isinstance(attempt.response, dict)
            and attempt.response.get("managed_delivery") is True
        )
    )


def _attention_item(
    delivery: PlanDelivery,
    attempts: list[PlanDeliveryAttempt],
    *,
    now: datetime,
    expected_version: str,
    current_canonical_version: str | None,
) -> ManagedPlanAttentionItem | None:
    if delivery.workout_date < now.date():
        return None
    if (
        current_canonical_version is None
        and delivery.canonical_id is not None
        and delivery.external_id is None
    ):
        return None
    latest = attempts[-1] if attempts else None
    if (
        delivery.state == "synced"
        and latest is not None
        and latest.state == "failed"
        and latest.operation == "deliver"
        and isinstance(latest.response, dict)
        and latest.response.get("canonical_version") is not None
        and latest.response.get("canonical_version")
        != current_canonical_version
    ):
        return None
    issue: ManagedPlanAttentionIssue
    supported = False
    blocked_reason: str | None = None

    if delivery.state == "pending":
        if delivery.updated_at > now - DELIVERY_ATTEMPT_LEASE:
            return None
        issue = "stale_pending"
        supported = True
    elif delivery.state == "delivering":
        if (
            latest is None
            or latest.state != "delivering"
            or latest.started_at > now - DELIVERY_ATTEMPT_LEASE
        ):
            return None
        issue = "stuck_inflight"
        supported = bool(
            isinstance(latest.response, dict)
            and latest.response.get("managed_delivery") is True
        )
        if not supported:
            blocked_reason = "attempt_not_managed"
    elif delivery.state == "failed" or (
        delivery.state == "synced"
        and latest is not None
        and latest.state == "failed"
        and latest.operation in {"deliver", "remove"}
    ):
        issue = (
            "retry_exhausted"
            if _automatic_failure_count(attempts)
            >= AUTOMATIC_DELIVERY_MAX_ATTEMPTS
            else "delivery_failed"
        )
        response = latest.response if latest is not None else None
        managed = bool(
            isinstance(response, dict)
            and response.get("managed_delivery") is True
        )
        retryable = bool(
            isinstance(response, dict)
            and response.get("retryable") is True
        )
        supported = managed and retryable
        if not managed:
            blocked_reason = "failure_not_managed"
        elif not retryable:
            blocked_reason = "failure_not_retryable"
    elif delivery.state == "conflict":
        error_category = (
            str((latest.response or {}).get("error_category") or "")
            if latest is not None and isinstance(latest.response, dict)
            else ""
        )
        issue = (
            "provider_outcome_unknown"
            if error_category == "provider_outcome_unknown"
            else "delivery_conflict"
        )
        blocked_reason = "user_resolution_required"
    else:
        return None

    error_category = (
        str((latest.response or {}).get("error_category") or "")
        if latest is not None and isinstance(latest.response, dict)
        else ""
    )
    version = utc_isoformat(delivery.updated_at) or ""
    return ManagedPlanAttentionItem(
        recovery_id=delivery.id,
        user_id_hash=telemetry.hash_user_id(delivery.user_id),
        target=delivery.target,
        state=delivery.state,
        operation=latest.operation if latest is not None else None,
        issue=issue,
        failure_domain=telemetry.managed_plan_failure_domain(error_category),
        attempt_count=latest.attempt_number if latest is not None else 0,
        last_attempt_at=utc_isoformat(
            (
                latest.completed_at or latest.started_at
                if latest is not None
                else None
            )
        ),
        updated_at=version,
        expected_version=expected_version,
        recovery_supported=supported,
        recovery_blocked_reason=blocked_reason,
    )


def _authoritative_future_deliveries(
    db: Session,
    *,
    now: datetime,
    user_id: str | None = None,
) -> list[PlanDelivery]:
    filters = [
        PlanDelivery.state.in_((*_ACTIVE_DELIVERY_STATES, "removed")),
        PlanDelivery.workout_date >= now.date(),
    ]
    if user_id is not None:
        filters.append(PlanDelivery.user_id == user_id)
    rows = db.execute(
        select(PlanDelivery).where(*filters)
    ).scalars().all()
    authoritative: dict[tuple[str, str, str], PlanDelivery] = {}
    canonical_versions: dict[tuple[str, str, str], str | None] = {}
    for delivery in rows:
        identity = (
            delivery.user_id,
            delivery.target,
            delivery_canonical_id(delivery) or delivery.canonical_key,
        )
        if identity not in canonical_versions:
            canonical_versions[identity] = _current_canonical_version(
                db,
                delivery,
            )
        canonical_version = canonical_versions[identity]

        def rank(row: PlanDelivery) -> tuple[int, datetime, datetime, str]:
            return (
                int(
                    canonical_version is not None
                    and (row.plan_version or row.workout_version)
                    == canonical_version
                ),
                row.updated_at,
                row.created_at,
                row.id,
            )

        current = authoritative.get(identity)
        if current is None or rank(delivery) > rank(current):
            authoritative[identity] = delivery
    return sorted(
        (
            delivery
            for delivery in authoritative.values()
            if delivery.state != "removed"
            and not (
                canonical_versions[
                    (
                        delivery.user_id,
                        delivery.target,
                        delivery_canonical_id(delivery)
                        or delivery.canonical_key,
                    )
                ]
                is None
                and delivery.canonical_id is not None
                and delivery.external_id is None
            )
        ),
        key=lambda delivery: (delivery.updated_at, delivery.id),
    )


def _attention_items(
    db: Session,
    *,
    now: datetime,
    limit: int | None,
) -> list[ManagedPlanAttentionItem]:
    deliveries = _authoritative_future_deliveries(db, now=now)
    attempts = _latest_attempts(db, [delivery.id for delivery in deliveries])
    items = [
        item
        for delivery in deliveries
        if (
            item := _attention_item(
                delivery,
                attempts.get(delivery.id, []),
                now=now,
                current_canonical_version=_current_canonical_version(
                    db,
                    delivery,
                ),
                expected_version=_recovery_expected_version(
                    db,
                    delivery,
                    attempts.get(delivery.id, []),
                ),
            )
        )
        is not None
    ]
    items.sort(
        key=lambda item: (
            not item.recovery_supported,
            item.updated_at,
            item.recovery_id,
        )
    )
    return items if limit is None else items[:limit]


def list_managed_plan_attention(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> ManagedPlanAttentionResponse:
    """Return a bounded, pseudonymous queue of delivery states needing action."""
    timestamp = now or datetime.utcnow()
    return ManagedPlanAttentionResponse(
        generated_at=utc_isoformat(timestamp) or "",
        items=_attention_items(
            db,
            now=timestamp,
            limit=max(1, min(limit, 100)),
        ),
    )


def managed_plan_health_data(
    db: Session,
    *,
    now: datetime | None = None,
) -> ManagedPlanHealthData:
    """Return aggregate managed-plan adoption and delivery health."""
    timestamp = now or datetime.utcnow()
    adopted_users = 0
    delivery_enabled_users = 0
    for raw_management in db.execute(
        select(UserConfig.plan_management)
    ).scalars():
        management = normalize_plan_management(raw_management)
        if management["mode"] != "praxys":
            continue
        adopted_users += 1
        if management["delivery_enabled"]:
            delivery_enabled_users += 1

    deliveries = _authoritative_future_deliveries(db, now=timestamp)
    state_counts = {
        state: sum(delivery.state == state for delivery in deliveries)
        for state in _ACTIVE_DELIVERY_STATES
    }
    states = ManagedPlanDeliveryStateCounts(
        **{
            state: state_counts.get(state, 0)
            for state in _ACTIVE_DELIVERY_STATES
        }
    )
    attention = _attention_items(db, now=timestamp, limit=None)
    oldest = min(
        (item.updated_at for item in attention),
        default=None,
    )
    return ManagedPlanHealthData(
        adopted_users=adopted_users,
        delivery_enabled_users=delivery_enabled_users,
        paused_users=adopted_users - delivery_enabled_users,
        active_deliveries=sum(state_counts.values()),
        states=states,
        attention_required=len(attention),
        recoverable=sum(item.recovery_supported for item in attention),
        retry_exhausted=sum(
            item.issue == "retry_exhausted" for item in attention
        ),
        stuck_inflight=sum(
            item.issue == "stuck_inflight" for item in attention
        ),
        oldest_attention_at=oldest,
    )


def _completion_response(revision: PlanRevision) -> ManagedPlanRecoveryResponse:
    details = revision.details if isinstance(revision.details, dict) else {}
    payload = details.get("response")
    if not isinstance(payload, dict):
        raise ManagedPlanRecoveryBusy(
            "The prior recovery result is not available yet"
        )
    return ManagedPlanRecoveryResponse.model_validate(payload)


def _recent_equivalent_recovery(
    db: Session,
    *,
    user_id: str,
    delivery_id: str,
    expected_version: str,
    now: datetime,
) -> tuple[PlanRevision, PlanRevision | None] | None:
    requests = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "managed_recovery_requested",
            PlanRevision.origin == _RECOVERY_ORIGIN,
            PlanRevision.created_at > now - _RECOVERY_REQUEST_LEASE,
        )
        .order_by(
            PlanRevision.created_at.desc(),
            PlanRevision.id.desc(),
        )
    ).scalars().all()
    for request in requests:
        details = request.details if isinstance(request.details, dict) else {}
        if (
            details.get("delivery_id") != delivery_id
            or details.get("expected_version") != expected_version
        ):
            continue
        completion = db.execute(
            select(PlanRevision).where(
                PlanRevision.user_id == user_id,
                PlanRevision.idempotency_key
                == f"managed-recovery-complete:{request.id}",
            )
        ).scalar_one_or_none()
        return request, completion
    return None


def _run_result_response(
    result: ManagedDeliveryRunResult,
    *,
    final_state: str,
    expected_final_state: str,
    audit_revision_id: str,
) -> ManagedPlanRecoveryResponse:
    successful_statuses = {"delivered", "replaced", "removed"}
    failed_statuses = {"failed"}
    blocked_statuses = {"blocked"}
    status = result.status
    reason = result.reason
    if (
        status == "complete"
        and final_state != expected_final_state
    ):
        status = "blocked"
        reason = "recovery_incomplete"
    return ManagedPlanRecoveryResponse(
        status=status,
        target=result.target or "unknown",
        reason=reason,
        final_state=final_state,
        attempted_items=len(result.items),
        successful_items=sum(
            item.status in successful_statuses for item in result.items
        ),
        failed_items=sum(
            item.status in failed_statuses for item in result.items
        ),
        blocked_items=sum(
            item.status in blocked_statuses for item in result.items
        ),
        audit_revision_id=audit_revision_id,
    )


def _locked_recovery_completion_state(
    db: Session,
    *,
    user_id: str,
    target: str,
    workout_date: date,
    delivery_id: str,
    replay: ManagedDeliveryReplayFence,
) -> tuple[str, str, bool]:
    """Return final state, current intent, and whether intent stayed fenced."""
    lock_plan_writes(db, user_id)
    original = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.id == delivery_id,
            PlanDelivery.user_id == user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if original is None:
        expected_state = (
            "synced"
            if replay.expected_canonical_version is not None
            else "removed"
        )
        return "missing", expected_state, False

    canonical = _current_canonical(db, original)
    current_version = (
        workout_version(plan_snapshot(canonical))
        if canonical is not None
        else None
    )
    expected_state = (
        "synced"
        if canonical is not None
        and not is_rest_workout(canonical.workout_type)
        else "removed"
    )
    intent_matches = current_version == replay.expected_canonical_version
    rows = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.workout_date == workout_date,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    slot_rows = [
        row
        for row in rows
        if (
            delivery_canonical_id(row) == replay.expected_canonical_id
            if replay.expected_canonical_id is not None
            else row.canonical_key == original.canonical_key
        )
    ]

    if expected_state == "synced":
        version_rows = [
            row
            for row in slot_rows
            if (row.plan_version or row.workout_version) == current_version
        ]
        authoritative = max(
            version_rows,
            key=lambda row: (row.updated_at, row.created_at, row.id),
            default=None,
        )
        if authoritative is None:
            return "missing", expected_state, intent_matches
        if (
            authoritative.state == "synced"
            and authoritative.external_id is None
        ):
            return "missing", expected_state, intent_matches
        return authoritative.state, expected_state, intent_matches

    active_owned = [
        row
        for row in slot_rows
        if row.state != "removed" and row.external_id is not None
    ]
    if active_owned:
        authoritative = max(
            active_owned,
            key=lambda row: (row.updated_at, row.created_at, row.id),
        )
        return authoritative.state, expected_state, intent_matches
    return original.state, expected_state, intent_matches


def recover_managed_plan_delivery(
    db: Session,
    *,
    admin_user_id: str,
    delivery_id: str,
    expected_version: str,
    now: datetime | None = None,
    adapter_loader: Callable[..., Any] | None = None,
    threshold_loader: Callable[..., float | None] | None = None,
) -> ManagedPlanRecoveryResponse:
    """Reconcile fresh provider state and replay one fenced retryable failure."""
    timestamp = _naive_utc(now or datetime.utcnow())
    db.rollback()
    initial = db.get(PlanDelivery, delivery_id)
    if initial is None:
        raise ManagedPlanRecoveryNotFound(
            "Managed delivery not found"
        )
    target_user_id = initial.user_id
    from api.legal_receipts import (
        user_background_processing_authorized,
        user_has_current_legal_bundle,
    )

    if not user_has_current_legal_bundle(db, target_user_id):
        db.rollback()
        raise ManagedPlanRecoveryUnsupported("terms_not_current")
    if not user_background_processing_authorized(db, target_user_id):
        db.rollback()
        raise ManagedPlanRecoveryUnsupported("processing_not_authorized")
    db.rollback()
    lock_plan_writes(db, target_user_id)
    if not user_has_current_legal_bundle(db, target_user_id):
        db.rollback()
        raise ManagedPlanRecoveryUnsupported("terms_not_current")
    if not user_background_processing_authorized(db, target_user_id):
        db.rollback()
        raise ManagedPlanRecoveryUnsupported("processing_not_authorized")
    delivery = db.execute(
        select(PlanDelivery)
        .where(PlanDelivery.id == delivery_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if delivery is None:
        db.rollback()
        raise ManagedPlanRecoveryNotFound(
            "Managed delivery not found"
        )
    recent = _recent_equivalent_recovery(
        db,
        user_id=delivery.user_id,
        delivery_id=delivery.id,
        expected_version=expected_version,
        now=timestamp,
    )
    if recent is not None:
        _, completion = recent
        if completion is not None:
            response = _completion_response(completion)
            db.rollback()
            return response
        db.rollback()
        raise ManagedPlanRecoveryBusy(
            "An equivalent managed-plan recovery is already running"
        )
    attempts = _latest_attempts(db, [delivery.id]).get(delivery.id, [])
    current_version = _recovery_expected_version(db, delivery, attempts)
    if current_version != expected_version:
        db.rollback()
        raise ManagedPlanRecoveryStale(
            "Managed delivery changed; refresh the operator queue"
        )
    authoritative_ids = {
        row.id
        for row in _authoritative_future_deliveries(
            db,
            now=timestamp,
            user_id=delivery.user_id,
        )
    }
    if delivery.id not in authoritative_ids:
        db.rollback()
        raise ManagedPlanRecoveryStale(
            "Managed delivery was superseded; refresh the operator queue"
        )
    attention = _attention_item(
        delivery,
        attempts,
        now=timestamp,
        expected_version=current_version,
        current_canonical_version=_current_canonical_version(db, delivery),
    )
    if attention is None or not attention.recovery_supported:
        db.rollback()
        raise ManagedPlanRecoveryUnsupported(
            (
                attention.recovery_blocked_reason
                if attention is not None
                else "delivery_no_longer_requires_recovery"
            )
        )
    latest = attempts[-1] if attempts else None
    expected_operation = (
        latest.operation
        if latest is not None
        else "deliver"
        if delivery.state == "pending"
        else None
    )
    expected_canonical_version = _current_canonical_version(db, delivery)
    if (
        expected_operation == "deliver"
        and expected_canonical_version is None
    ):
        db.rollback()
        raise ManagedPlanRecoveryStale(
            "Canonical workout changed; refresh the operator queue"
        )
    lease_bucket = int(
        (
            timestamp - datetime(1970, 1, 1)
        ).total_seconds()
        // _RECOVERY_REQUEST_LEASE.total_seconds()
    )
    request_fingerprint = hashlib.sha256(
        f"{delivery_id}:{expected_version}:{lease_bucket}".encode("utf-8")
    ).hexdigest()
    request_key = (
        f"managed-recovery:{request_fingerprint}"
    )
    request_revision, request_created = record_plan_revision_idempotent(
        db,
        user_id=delivery.user_id,
        operation="managed_recovery_requested",
        actor_type="admin",
        actor_id=admin_user_id,
        origin=_RECOVERY_ORIGIN,
        before=[],
        after=[],
        details={
            "delivery_id": delivery.id,
            "target": delivery.target,
            "state": delivery.state,
            "issue": attention.issue,
            "expected_version": expected_version,
        },
        idempotency_key=request_key,
    )
    if request_created:
        request_revision.created_at = timestamp
    replay = ManagedDeliveryReplayFence(
        delivery_id=delivery.id,
        expected_updated_at=delivery.updated_at,
        expected_attempt_id=latest.id if latest is not None else None,
        expected_attempt_number=(
            latest.attempt_number if latest is not None else 0
        ),
        expected_state=delivery.state,
        expected_operation=expected_operation,
        expected_canonical_id=delivery_canonical_id(delivery),
        expected_canonical_version=expected_canonical_version,
    )
    target = delivery.target
    workout_date = delivery.workout_date
    db.commit()

    run_kwargs: dict[str, Any] = {
        "user_id": target_user_id,
        "trigger": "admin_recovery",
        "now": timestamp,
        "window_start": workout_date,
        "replay": replay,
    }
    if adapter_loader is not None:
        run_kwargs["adapter_loader"] = adapter_loader
    if threshold_loader is not None:
        run_kwargs["threshold_loader"] = threshold_loader
    result = run_rolling_delivery_for_user(db, **run_kwargs)
    db.rollback()
    (
        final_state,
        expected_final_state,
        intent_matches,
    ) = _locked_recovery_completion_state(
        db,
        user_id=target_user_id,
        target=target,
        workout_date=workout_date,
        delivery_id=delivery_id,
        replay=replay,
    )
    response = _run_result_response(
        result,
        final_state=final_state,
        expected_final_state=expected_final_state,
        audit_revision_id=request_revision.id,
    )
    if not intent_matches:
        response = response.model_copy(update={
            "status": "skipped",
            "reason": "recovery_superseded",
        })
    completion_revision, completion_created = record_plan_revision_idempotent(
        db,
        user_id=target_user_id,
        operation="managed_recovery_completed",
        actor_type="admin",
        actor_id=admin_user_id,
        origin=_RECOVERY_ORIGIN,
        before=[],
        after=[],
        details={"response": response.model_dump()},
        idempotency_key=f"managed-recovery-complete:{request_revision.id}",
    )
    if completion_created:
        completion_revision.created_at = max(
            datetime.utcnow(),
            timestamp + timedelta(microseconds=1),
        )
    db.commit()
    telemetry.record_managed_plan_event(
        category="recovery",
        action="reconcile_and_replay",
        outcome=response.status,
        user_id=target_user_id,
        target=target,
        trigger="admin_recovery",
        reason=response.reason,
    )
    return response
