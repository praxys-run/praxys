"""Default-off rolling delivery for Praxys-managed plans."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import (
    PLATFORM_CAPABILITIES,
    PRAXYS_PLAN_SOURCES,
    normalize_plan_management,
)
from analysis.metrics import is_rest_workout
from api.packs import RequestContext
from api.plan_delivery import (
    DeliveryAccountMismatchError,
    DeliveryAccountVerificationError,
    DeliveryBusyError,
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
    DeliveryFinalizationError,
    DeliveryMutationBlockedError,
    DeliveryNotFoundError,
    DeliveryRemovalFailedError,
    DeliveryStartError,
    PlanDeliveryAdapter,
    PlanDeliveryService,
    ProviderAuthenticationError,
    ProviderReadError,
    ProviderRequestError,
    is_plan_delivery_target_registered,
    load_plan_delivery_adapter,
)
from api.plan_reconciliation import (
    PlanReconciliationItem,
    build_plan_reconciliation,
)
from api.plan_resolution import (
    PlanResolutionConflict,
    PlanResolutionProviderError,
    restore_praxys_version,
)
from db.models import (
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    TrainingPlan,
    UserConfig,
    UserConnection,
)
from db.connection_credentials import connection_credentials_generation
from db.plan_ledger import (
    DELIVERY_ATTEMPT_LEASE,
    canonical_workout_key,
    delivery_canonical_id,
    complete_delivery_attempt,
    lock_plan_writes,
    plan_snapshot,
    workout_version,
)
from db.plan_reconciliation import record_target_calendar_sync

logger = logging.getLogger(__name__)

ROLLING_DELIVERY_DAYS = 14
AUTOMATIC_DELIVERY_MAX_ATTEMPTS = 5
AUTOMATIC_RETRY_BASE = timedelta(minutes=15)
AUTOMATIC_RETRY_MAX = timedelta(hours=6)


@dataclass(frozen=True)
class ManagedDeliveryItemResult:
    """Outcome for one canonical workout or owned orphan delivery."""

    canonical_id: str | None
    workout_date: str
    action: str
    status: str
    reason: str | None = None
    external_id: str | None = None


@dataclass(frozen=True)
class ManagedDeliveryRunResult:
    """Summary of one user-scoped rolling delivery pass."""

    user_id: str
    trigger: str
    status: str
    target: str | None
    window_start: str
    window_end: str
    items: tuple[ManagedDeliveryItemResult, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class _DeliveryGate:
    target: str | None
    connection: UserConnection | None
    reason: str | None

    @property
    def enabled(self) -> bool:
        return self.reason is None and self.target is not None


AdapterLoader = Callable[[Session, str, str], PlanDeliveryAdapter]
ThresholdLoader = Callable[[Session, str], float | None]

_CONNECTION_FAILURES = (
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
    ProviderAuthenticationError,
)
_REMOVAL_FAILURES = (
    DeliveryAccountMismatchError,
    DeliveryAccountVerificationError,
    DeliveryBusyError,
    DeliveryFinalizationError,
    DeliveryNotFoundError,
    DeliveryRemovalFailedError,
    DeliveryStartError,
)
_REPLACEMENT_FAILURES = (
    PlanResolutionProviderError,
    ProviderRequestError,
    *_REMOVAL_FAILURES,
)


def automatic_retry_delay(failure_count: int) -> timedelta:
    """Return the bounded delay before the next automatic delivery attempt."""
    exponent = max(failure_count - 1, 0)
    delay = AUTOMATIC_RETRY_BASE * (2 ** exponent)
    return min(delay, AUTOMATIC_RETRY_MAX)


def _window(today: date) -> tuple[date, date]:
    return today, today + timedelta(days=ROLLING_DELIVERY_DAYS - 1)


def _delivery_gate(
    db: Session,
    user_id: str,
    *,
    refresh: bool = False,
) -> _DeliveryGate:
    config_query = select(UserConfig).where(UserConfig.user_id == user_id)
    connection_query = select(UserConnection).where(
        UserConnection.user_id == user_id,
    )
    if refresh:
        config_query = config_query.with_for_update().execution_options(
            populate_existing=True
        )
        connection_query = (
            connection_query
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    config_row = db.execute(config_query).scalar_one_or_none()
    plan_management = normalize_plan_management(
        config_row.plan_management if config_row is not None else None
    )
    target = plan_management["execution_target"]
    if plan_management["mode"] != "praxys":
        return _DeliveryGate(target, None, "external_mode")
    if not plan_management["delivery_enabled"]:
        return _DeliveryGate(target, None, "delivery_paused")
    if not target:
        return _DeliveryGate(None, None, "execution_target_missing")
    capabilities = PLATFORM_CAPABILITIES.get(target)
    if not capabilities or not capabilities.get("plan"):
        return _DeliveryGate(target, None, "execution_target_unsupported")
    if not is_plan_delivery_target_registered(target):
        return _DeliveryGate(target, None, "delivery_adapter_unavailable")

    connection = db.execute(
        connection_query.where(UserConnection.platform == target)
    ).scalar_one_or_none()
    if connection is None:
        return _DeliveryGate(target, None, "connection_missing")
    if connection.status != "connected":
        return _DeliveryGate(
            target,
            connection,
            f"connection_{connection.status}",
        )
    return _DeliveryGate(target, connection, None)


def _default_adapter_loader(
    db: Session,
    user_id: str,
    target: str,
) -> PlanDeliveryAdapter:
    return load_plan_delivery_adapter(
        db,
        user_id=user_id,
        target=target,
    )


def _default_threshold_loader(db: Session, user_id: str) -> float | None:
    return RequestContext(user_id, db).latest_cp_watts


def _record_connection_failure(
    db: Session,
    connection: UserConnection | None,
    exc: BaseException,
    *,
    trigger: str,
    connection_generation: str,
) -> bool:
    if connection is None:
        db.rollback()
        return False
    from db.sync_scheduler import _record_sync_failure

    return _record_sync_failure(
        connection,
        exc,
        db,
        trigger=f"managed_delivery:{trigger}",
        expected_credential_generation=connection_generation,
    )


def _record_connection_success(
    db: Session,
    *,
    user_id: str,
    target: str,
    connection_generation: str,
) -> bool:
    from db.sync_scheduler import reset_connection_backoff

    connection = db.execute(
        select(UserConnection)
        .where(
            UserConnection.user_id == user_id,
            UserConnection.platform == target,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if connection is None:
        db.rollback()
        return False
    if (
        connection_credentials_generation(connection)
        != connection_generation
    ):
        db.rollback()
        return False
    connection.status = "connected"
    reset_connection_backoff(connection)
    db.commit()
    return True


def _mutation_guard(
    db: Session,
    *,
    user_id: str,
    target: str,
    connection_generation: str,
) -> None:
    lock_plan_writes(db, user_id)
    gate = _delivery_gate(db, user_id, refresh=True)
    if not gate.enabled or gate.target != target:
        raise DeliveryMutationBlockedError(
            gate.reason or "execution_target_changed"
        )
    assert gate.connection is not None
    if (
        connection_credentials_generation(gate.connection)
        != connection_generation
    ):
        raise DeliveryMutationBlockedError("connection_changed")


def _canonical_mutation_guard(
    db: Session,
    *,
    user_id: str,
    target: str,
    connection_generation: str,
    canonical_id: str,
    expected_version: str,
) -> None:
    _mutation_guard(
        db,
        user_id=user_id,
        target=target,
        connection_generation=connection_generation,
    )
    canonical = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.canonical_id == canonical_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if canonical is None:
        raise DeliveryMutationBlockedError("canonical_deleted_during_run")
    if is_rest_workout(str(canonical.workout_type or "")):
        raise DeliveryMutationBlockedError("canonical_became_rest")
    if workout_version(plan_snapshot(canonical)) != expected_version:
        raise DeliveryMutationBlockedError("canonical_changed_during_run")


def _rest_mutation_guard(
    db: Session,
    *,
    user_id: str,
    target: str,
    connection_generation: str,
    canonical_id: str,
    expected_version: str,
) -> None:
    _mutation_guard(
        db,
        user_id=user_id,
        target=target,
        connection_generation=connection_generation,
    )
    canonical = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.canonical_id == canonical_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if canonical is None:
        return
    if (
        not is_rest_workout(str(canonical.workout_type or ""))
        or workout_version(plan_snapshot(canonical)) != expected_version
    ):
        raise DeliveryMutationBlockedError("canonical_changed_during_run")


def _refresh_target_calendar(
    db: Session,
    *,
    user_id: str,
    target: str,
    adapter: PlanDeliveryAdapter,
    threshold_value: float | None,
    window_start: date,
    window_end: date,
    observed_at: datetime,
    mutation_guard: Callable[[], None],
) -> set[str]:
    rows = adapter.fetch_calendar(
        threshold_value=threshold_value,
        days_ahead=ROLLING_DELIVERY_DAYS + 2,
        days_back=2,
    )
    external_ids = {
        str(row.get("external_id") or "").strip()
        for row in rows
        if str(row.get("external_id") or "").strip()
    }
    mutation_guard()
    record_target_calendar_sync(
        db,
        user_id=user_id,
        target=target,
        provider_account_id=adapter.account_id,
        rows=rows,
        window_start=window_start,
        window_end=window_end,
        observed_at=observed_at,
    )
    db.commit()
    return external_ids


def _recover_managed_inflight_attempts(
    db: Session,
    *,
    user_id: str,
    target: str,
    provider_account_id: str,
    connection_generation: str,
    deliveries: list[PlanDelivery],
) -> None:
    lock_plan_writes(db, user_id)
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync).where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
            PlanTargetCalendarSync.provider_account_id
            == provider_account_id,
        )
    ).scalar_one_or_none()
    if calendar_sync is None:
        db.rollback()
        return
    observations = db.execute(
        select(PlanTargetWorkout).where(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
            PlanTargetWorkout.provider_account_id == provider_account_id,
        )
    ).scalars().all()
    claimed_external_ids = {
        external_id
        for external_id in db.execute(
            select(PlanDelivery.external_id).where(
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == target,
                PlanDelivery.external_id.is_not(None),
                PlanDelivery.state != "removed",
            )
        ).scalars()
        if external_id
    }
    changed = False

    for delivery in deliveries:
        if delivery.state != "delivering":
            continue
        attempt = db.execute(
            select(PlanDeliveryAttempt)
            .where(PlanDeliveryAttempt.delivery_id == delivery.id)
            .order_by(
                PlanDeliveryAttempt.attempt_number.desc(),
                PlanDeliveryAttempt.id.desc(),
            )
        ).scalars().first()
        if (
            attempt is None
            or attempt.state != "delivering"
            or not isinstance(attempt.response, dict)
            or attempt.response.get("managed_delivery") is not True
            or calendar_sync.synced_at < attempt.started_at
            or attempt.started_at
            > datetime.utcnow() - DELIVERY_ATTEMPT_LEASE
            or not (
                calendar_sync.window_start
                <= delivery.workout_date
                <= calendar_sync.window_end
            )
        ):
            continue

        response = {
            **attempt.response,
            "recovered_from_calendar": True,
        }
        if (
            attempt.response.get("provider_account_id")
            != provider_account_id
            or attempt.response.get("connection_generation")
            != connection_generation
        ):
            complete_delivery_attempt(
                db,
                user_id=user_id,
                delivery_id=delivery.id,
                attempt_id=attempt.id,
                attempt_state="conflict",
                error="Provider account changed during recovery",
                response={
                    **response,
                    "error_category": "provider_account_changed",
                    "retryable": False,
                },
            )
            changed = True
            continue
        if attempt.operation == "deliver":
            preexisting_external_ids = {
                str(external_id)
                for external_id in attempt.response.get(
                    "preexisting_external_ids",
                    [],
                )
                if external_id
            }
            matches = [
                observation
                for observation in observations
                if (
                    observation.present
                    and observation.workout_date == delivery.workout_date
                    and delivery.provider_content_version
                    and observation.content_fingerprint
                    == delivery.provider_content_version
                    and observation.external_id
                    not in preexisting_external_ids
                )
            ]
            if len(matches) == 1:
                if matches[0].external_id in claimed_external_ids:
                    matches = []
            if len(matches) == 1:
                observation = matches[0]
                complete_delivery_attempt(
                    db,
                    user_id=user_id,
                    delivery_id=delivery.id,
                    attempt_id=attempt.id,
                    attempt_state="synced",
                    external_id=observation.external_id,
                    response=response,
                    provider_account_id=provider_account_id,
                )
                claimed_external_ids.add(observation.external_id)
            else:
                complete_delivery_attempt(
                    db,
                    user_id=user_id,
                    delivery_id=delivery.id,
                    attempt_id=attempt.id,
                    attempt_state="conflict",
                    error="Delivery outcome requires reconciliation",
                    response={
                        **response,
                        "error_category": "provider_outcome_unknown",
                        "retryable": False,
                    },
                )
            changed = True
            continue

        if attempt.operation != "remove" or not delivery.external_id:
            continue
        exact = next(
            (
                observation
                for observation in observations
                if observation.external_id == delivery.external_id
            ),
            None,
        )
        if exact is not None and exact.present:
            unchanged = (
                exact.workout_date == delivery.workout_date
                and delivery.provider_content_version is not None
                and exact.content_fingerprint
                == delivery.provider_content_version
            )
            complete_delivery_attempt(
                db,
                user_id=user_id,
                delivery_id=delivery.id,
                attempt_id=attempt.id,
                attempt_state="failed",
                delivery_state="synced",
                error="Removal was not confirmed by the target calendar",
                response={
                    **response,
                    "error_category": "provider_removal",
                    "retryable": unchanged,
                },
            )
        else:
            complete_delivery_attempt(
                db,
                user_id=user_id,
                delivery_id=delivery.id,
                attempt_id=attempt.id,
                attempt_state="conflict",
                error="Removal outcome requires reconciliation",
                response={
                    **response,
                    "error_category": "provider_outcome_unknown",
                    "retryable": False,
                },
            )
        changed = True

    if changed:
        from db.cache_revision import bump_revisions

        bump_revisions(db, user_id, ["plans"])
        db.commit()
    else:
        db.rollback()


def _retry_eligibility(
    db: Session,
    delivery: PlanDelivery,
    *,
    operation: str,
    now: datetime,
    allow_initial: bool = False,
    expected_canonical_version: str | None = None,
) -> tuple[bool, str | None]:
    attempts = db.execute(
        select(PlanDeliveryAttempt)
        .where(
            PlanDeliveryAttempt.delivery_id == delivery.id,
            PlanDeliveryAttempt.operation == operation,
        )
        .order_by(
            PlanDeliveryAttempt.attempt_number,
            PlanDeliveryAttempt.id,
        )
    ).scalars().all()
    if not attempts:
        return (
            (True, None)
            if allow_initial
            else (False, "failure_not_recorded")
        )
    latest = attempts[-1]
    if latest.state != "failed":
        return True, None
    if (
        expected_canonical_version is not None
        and isinstance(latest.response, dict)
        and latest.response.get("canonical_version") is not None
        and latest.response.get("canonical_version")
        != expected_canonical_version
    ):
        return True, None
    if not (
        isinstance(latest.response, dict)
        and latest.response.get("managed_delivery") is True
    ):
        return False, "failure_not_automatic"
    last_success_index = max(
        (
            index
            for index, attempt in enumerate(attempts)
            if attempt.state in {"synced", "removed"}
        ),
        default=-1,
    )
    automatic_attempts = [
        attempt
        for attempt in attempts[last_success_index + 1:]
        if attempt.state == "failed"
        and isinstance(attempt.response, dict)
        and attempt.response.get("managed_delivery") is True
    ]
    if not bool((latest.response or {}).get("retryable")):
        return False, "failure_not_retryable"
    if (latest.response or {}).get("error_category") == "delivery_gate_changed":
        return True, None
    failure_count = sum(
        (attempt.response or {}).get(
            "counts_toward_retry_limit",
            True,
        )
        is not False
        for attempt in automatic_attempts
    )
    if failure_count >= AUTOMATIC_DELIVERY_MAX_ATTEMPTS:
        return False, "retry_limit_reached"
    completed_at = latest.completed_at or latest.started_at
    if now < completed_at + automatic_retry_delay(failure_count):
        return False, "retry_backoff"
    return True, None


def _current_canonical(
    db: Session,
    *,
    user_id: str,
    canonical_id: str,
) -> TrainingPlan | None:
    return db.execute(
        select(TrainingPlan).where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.canonical_id == canonical_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _retry_wait_status(reason: str | None) -> str:
    return "skipped" if reason == "retry_backoff" else "blocked"


def _owned_removal_safe(
    db: Session,
    *,
    delivery: PlanDelivery,
    provider_account_id: str,
) -> tuple[bool, str | None]:
    if delivery.provider_account_id != provider_account_id:
        return False, "provider_account_mismatch"
    if delivery.state != "synced" or not delivery.external_id:
        return False, f"delivery_{delivery.state}"

    exact = db.execute(
        select(PlanTargetWorkout).where(
            PlanTargetWorkout.user_id == delivery.user_id,
            PlanTargetWorkout.target == delivery.target,
            PlanTargetWorkout.provider_account_id == provider_account_id,
            PlanTargetWorkout.external_id == delivery.external_id,
        )
    ).scalar_one_or_none()
    if exact is None or not exact.present:
        return False, "target_workout_absent"
    if exact.workout_date != delivery.workout_date:
        return False, "target_workout_moved"
    if (
        not delivery.provider_content_version
        or exact.content_fingerprint != delivery.provider_content_version
    ):
        return False, "target_workout_edited"
    return True, None


def _result(
    canonical_id: str | None,
    workout_date: date,
    action: str,
    status: str,
    *,
    reason: str | None = None,
    external_id: str | None = None,
) -> ManagedDeliveryItemResult:
    return ManagedDeliveryItemResult(
        canonical_id=canonical_id,
        workout_date=workout_date.isoformat(),
        action=action,
        status=status,
        reason=reason,
        external_id=external_id,
    )


def _remove_owned_delivery(
    db: Session,
    *,
    service: PlanDeliveryService,
    delivery: PlanDelivery,
    canonical_id: str | None,
    provider_account_id: str,
    connection: UserConnection | None,
    connection_generation: str,
    trigger: str,
    timestamp: datetime,
    attempt_context: Mapping[str, Any],
    mutation_guard: Callable[[], None],
) -> tuple[ManagedDeliveryItemResult, bool]:
    safe, reason = _owned_removal_safe(
        db,
        delivery=delivery,
        provider_account_id=provider_account_id,
    )
    if not safe:
        return (
            _result(
                canonical_id,
                delivery.workout_date,
                "remove",
                "blocked",
                reason=reason,
                external_id=delivery.external_id,
            ),
            False,
        )
    retryable, reason = _retry_eligibility(
        db,
        delivery,
        operation="remove",
        now=timestamp,
        allow_initial=True,
    )
    if not retryable:
        return (
            _result(
                canonical_id,
                delivery.workout_date,
                "remove",
                _retry_wait_status(reason),
                reason=reason,
                external_id=delivery.external_id,
            ),
            False,
        )
    try:
        removal = service.remove(
            str(delivery.external_id),
            attempt_context=attempt_context,
            mutation_guard=mutation_guard,
        )
    except DeliveryMutationBlockedError as exc:
        return (
            _result(
                canonical_id,
                delivery.workout_date,
                "remove",
                "skipped",
                reason=str(exc),
                external_id=delivery.external_id,
            ),
            True,
        )
    except _CONNECTION_FAILURES as exc:
        recorded = _record_connection_failure(
            db,
            connection,
            exc,
            trigger=trigger,
            connection_generation=connection_generation,
        )
        category = (
            type(exc).__name__ if recorded else "connection_changed"
        )
        logger.warning(
            "Managed removal blocked user=%s target=%s canonical=%s "
            "category=%s",
            delivery.user_id,
            delivery.target,
            canonical_id,
            category,
        )
        return (
            _result(
                canonical_id,
                delivery.workout_date,
                "remove",
                "failed",
                reason=category,
                external_id=delivery.external_id,
            ),
            True,
        )
    except _REMOVAL_FAILURES as exc:
        category = type(exc).__name__
        logger.warning(
            "Managed removal failed user=%s target=%s canonical=%s category=%s",
            delivery.user_id,
            delivery.target,
            canonical_id,
            category,
        )
        return (
            _result(
                canonical_id,
                delivery.workout_date,
                "remove",
                "failed",
                reason=category,
                external_id=delivery.external_id,
            ),
            False,
        )
    return (
        _result(
            canonical_id,
            delivery.workout_date,
            "remove",
            "removed",
            external_id=removal.external_id,
        ),
        False,
    )


def run_rolling_delivery_for_user(
    db: Session,
    *,
    user_id: str,
    trigger: str,
    now: datetime | None = None,
    adapter_loader: AdapterLoader = _default_adapter_loader,
    threshold_loader: ThresholdLoader = _default_threshold_loader,
) -> ManagedDeliveryRunResult:
    """Reconcile and deliver one user's managed plan for 14 calendar days."""
    timestamp = now or datetime.utcnow()
    window_start, window_end = _window(timestamp.date())
    gate = _delivery_gate(db, user_id)
    if not gate.enabled:
        return ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="skipped",
            target=gate.target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason=gate.reason,
        )
    assert gate.target is not None
    assert gate.connection is not None
    target = gate.target
    connection_generation = connection_credentials_generation(
        gate.connection
    )
    mutation_guard = lambda: _mutation_guard(
        db,
        user_id=user_id,
        target=target,
        connection_generation=connection_generation,
    )

    canonicals = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date >= window_start,
            TrainingPlan.date <= window_end,
        )
        .order_by(TrainingPlan.date, TrainingPlan.id)
    ).scalars().all()
    canonical_ids = {
        canonical.canonical_id
        for canonical in canonicals
    }
    owned_deliveries = db.execute(
        select(PlanDelivery).where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.workout_date >= window_start,
            PlanDelivery.workout_date <= window_end,
            PlanDelivery.state != "removed",
        )
    ).scalars().all()
    if not canonicals and not owned_deliveries:
        return ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="complete",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
        )

    threshold_value = threshold_loader(db, user_id)
    try:
        adapter = adapter_loader(db, user_id, target)
        adapter.authenticate()
        observed_external_ids = _refresh_target_calendar(
            db,
            user_id=user_id,
            target=target,
            adapter=adapter,
            threshold_value=threshold_value,
            window_start=window_start,
            window_end=window_end,
            observed_at=timestamp,
            mutation_guard=mutation_guard,
        )
    except DeliveryMutationBlockedError as exc:
        db.rollback()
        return ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="skipped",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason=str(exc),
        )
    except (
        DeliveryCredentialsInvalid,
        DeliveryCredentialsUnavailable,
        ProviderAuthenticationError,
        ProviderReadError,
    ) as exc:
        recorded = _record_connection_failure(
            db,
            gate.connection,
            exc,
            trigger=trigger,
            connection_generation=connection_generation,
        )
        category = (
            type(exc).__name__ if recorded else "connection_changed"
        )
        logger.warning(
            "Managed delivery blocked user=%s target=%s trigger=%s category=%s",
            user_id,
            target,
            trigger,
            category,
        )
        return ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="blocked",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason=category,
        )

    if not _record_connection_success(
        db,
        user_id=user_id,
        target=target,
        connection_generation=connection_generation,
    ):
        return ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="skipped",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason="connection_changed",
        )
    _recover_managed_inflight_attempts(
        db,
        user_id=user_id,
        target=target,
        provider_account_id=adapter.account_id,
        connection_generation=connection_generation,
        deliveries=owned_deliveries,
    )
    reconciliation = build_plan_reconciliation(
        db,
        user_id=user_id,
        target=target,
        start=window_start,
        end=window_end,
    )
    if reconciliation is None:
        return ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="blocked",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason="calendar_reconciliation_unavailable",
        )

    service = PlanDeliveryService(
        db=db,
        user_id=user_id,
        target=target,
        adapter_loader=lambda: adapter,
    )
    base_attempt_context: dict[str, Any] = {
        "managed_delivery": True,
        "trigger": trigger,
        "provider_account_id": adapter.account_id,
        "connection_generation": connection_generation,
        "calendar_synced_at": (
            reconciliation.calendar_sync.synced_at.isoformat()
        ),
    }

    def attempt_context() -> Mapping[str, Any]:
        return {
            **base_attempt_context,
            "preexisting_external_ids": sorted(observed_external_ids),
        }

    items: list[ManagedDeliveryItemResult] = []

    for delivery in owned_deliveries:
        canonical_id = delivery_canonical_id(delivery)
        if canonical_id is None or canonical_id in canonical_ids:
            continue
        gate = _delivery_gate(db, user_id)
        if not gate.enabled or gate.target != target:
            items.append(_result(
                canonical_id,
                delivery.workout_date,
                "remove",
                "skipped",
                reason=gate.reason or "execution_target_changed",
            ))
            break
        removal_result, stop_batch = _remove_owned_delivery(
            db,
            service=service,
            delivery=delivery,
            provider_account_id=adapter.account_id,
            canonical_id=canonical_id,
            connection=gate.connection,
            connection_generation=connection_generation,
            trigger=trigger,
            timestamp=timestamp,
            attempt_context=attempt_context(),
            mutation_guard=mutation_guard,
        )
        items.append(removal_result)
        if stop_batch:
            break

    for canonical in canonicals:
        canonical_id = str(canonical.canonical_id)
        workout_type = str(canonical.workout_type or "")
        item: PlanReconciliationItem | None = (
            reconciliation.canonical_items.get(canonical_id)
        )
        if item is None:
            items.append(_result(
                canonical_id,
                canonical.date,
                "deliver",
                "blocked",
                reason="reconciliation_item_missing",
            ))
            continue
        if is_rest_workout(workout_type):
            if item.state == "not_delivered" or (
                item.state == "delivery_failed"
                and item.delivery is not None
                and not item.delivery.external_id
            ):
                items.append(_result(
                    canonical_id,
                    canonical.date,
                    "deliver",
                    "skipped",
                    reason="rest_day",
                ))
                continue
            if (
                item.state
                not in {"matching", "pending_observation", "canonical_changed"}
                or item.delivery is None
            ):
                items.append(_result(
                    canonical_id,
                    canonical.date,
                    "remove",
                    "blocked",
                    reason=item.state,
                    external_id=(
                        item.delivery.external_id
                        if item.delivery is not None
                        else None
                    ),
                ))
                continue
            current_rest = _current_canonical(
                db,
                user_id=user_id,
                canonical_id=canonical_id,
            )
            if (
                current_rest is not None
                and not is_rest_workout(
                    str(current_rest.workout_type or "")
                )
            ):
                items.append(_result(
                    canonical_id,
                    canonical.date,
                    "remove",
                    "skipped",
                    reason="canonical_changed_during_run",
                    external_id=item.delivery.external_id,
                ))
                continue
            gate = _delivery_gate(db, user_id)
            if not gate.enabled or gate.target != target:
                items.append(_result(
                    canonical_id,
                    canonical.date,
                    "remove",
                    "skipped",
                    reason=gate.reason or "execution_target_changed",
                    external_id=item.delivery.external_id,
                ))
                break
            rest_mutation_guard = mutation_guard
            if current_rest is not None:
                expected_rest_version = workout_version(
                    plan_snapshot(current_rest)
                )
                rest_mutation_guard = lambda: _rest_mutation_guard(
                    db,
                    user_id=user_id,
                    target=target,
                    connection_generation=connection_generation,
                    canonical_id=canonical_id,
                    expected_version=expected_rest_version,
                )
            removal_result, stop_batch = _remove_owned_delivery(
                db,
                service=service,
                delivery=item.delivery,
                canonical_id=canonical_id,
                provider_account_id=adapter.account_id,
                connection=gate.connection,
                connection_generation=connection_generation,
                trigger=trigger,
                timestamp=timestamp,
                attempt_context=attempt_context(),
                mutation_guard=rest_mutation_guard,
            )
            items.append(removal_result)
            if stop_batch:
                break
            continue

        action = "deliver"
        if item.state in {"matching", "pending_observation"}:
            items.append(_result(
                canonical_id,
                canonical.date,
                action,
                "skipped",
                reason=item.state,
                external_id=(
                    item.delivery.external_id
                    if item.delivery is not None
                    else None
                ),
            ))
            continue
        if item.state == "canonical_changed":
            action = "replace"
        elif item.state == "delivery_failed":
            if item.delivery is None or item.delivery.state != "failed":
                items.append(_result(
                    canonical_id,
                    canonical.date,
                    action,
                    "blocked",
                    reason="reconciliation_required",
                ))
                continue
            current_version = workout_version(plan_snapshot(canonical))
            failed_version = (
                item.delivery.plan_version
                or item.delivery.workout_version
            )
            corrected_version = (
                current_version != failed_version
                and not item.delivery.external_id
            )
            if not corrected_version:
                retryable, reason = _retry_eligibility(
                    db,
                    item.delivery,
                    operation="deliver",
                    now=timestamp,
                )
                if not retryable:
                    items.append(_result(
                        canonical_id,
                        canonical.date,
                        action,
                        _retry_wait_status(reason),
                        reason=reason,
                    ))
                    continue
        elif item.state != "not_delivered":
            items.append(_result(
                canonical_id,
                canonical.date,
                action,
                "blocked",
                reason=item.state,
                external_id=(
                    item.delivery.external_id
                    if item.delivery is not None
                    else None
                ),
            ))
            continue

        gate = _delivery_gate(db, user_id)
        if not gate.enabled or gate.target != target:
            items.append(_result(
                canonical_id,
                canonical.date,
                action,
                "skipped",
                reason=gate.reason or "execution_target_changed",
            ))
            break
        current = _current_canonical(
            db,
            user_id=user_id,
            canonical_id=canonical_id,
        )
        if current is None or not (
            window_start <= current.date <= window_end
        ):
            items.append(_result(
                canonical_id,
                canonical.date,
                action,
                "skipped",
                reason="canonical_changed_during_run",
            ))
            continue
        if not threshold_value:
            items.append(_result(
                canonical_id,
                current.date,
                action,
                "blocked",
                reason="threshold_unavailable",
            ))
            continue

        if action == "replace":
            assert item.delivery is not None
            expected_version = workout_version(plan_snapshot(current))
            retryable, reason = _retry_eligibility(
                db,
                item.delivery,
                operation="deliver",
                now=timestamp,
                allow_initial=True,
                expected_canonical_version=expected_version,
            )
            if not retryable:
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    _retry_wait_status(reason),
                    reason=reason,
                    external_id=item.delivery.external_id,
                ))
                continue
            retryable, reason = _retry_eligibility(
                db,
                item.delivery,
                operation="remove",
                now=timestamp,
                allow_initial=True,
            )
            if not retryable:
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    _retry_wait_status(reason),
                    reason=reason,
                    external_id=item.delivery.external_id,
                ))
                continue
            try:
                canonical_mutation_guard = lambda: _canonical_mutation_guard(
                    db,
                    user_id=user_id,
                    target=target,
                    connection_generation=connection_generation,
                    canonical_id=canonical_id,
                    expected_version=expected_version,
                )
                restored = restore_praxys_version(
                    db,
                    user_id=user_id,
                    target=target,
                    item=item,
                    threshold_value=threshold_value,
                    adapter_loader=lambda: adapter,
                    actor_type="system",
                    actor_id=None,
                    origin="managed_plan.rolling_delivery",
                    trigger=trigger,
                    attempt_context=attempt_context(),
                    mutation_guard=canonical_mutation_guard,
                )
            except DeliveryMutationBlockedError as exc:
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    "skipped",
                    reason=str(exc),
                ))
                break
            except _CONNECTION_FAILURES as exc:
                recorded = _record_connection_failure(
                    db,
                    gate.connection,
                    exc,
                    trigger=trigger,
                    connection_generation=connection_generation,
                )
                category = (
                    type(exc).__name__
                    if recorded
                    else "connection_changed"
                )
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    "failed",
                    reason=category,
                ))
                break
            except PlanResolutionConflict as exc:
                logger.info(
                    "Managed replacement blocked user=%s target=%s "
                    "canonical=%s category=PlanResolutionConflict reason=%s",
                    user_id,
                    target,
                    canonical_id,
                    str(exc),
                )
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    "blocked",
                    reason="plan_resolution_conflict",
                ))
                continue
            except _REPLACEMENT_FAILURES as exc:
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    "failed",
                    reason=type(exc).__name__,
                ))
                continue
            items.append(_result(
                canonical_id,
                current.date,
                action,
                "replaced",
                external_id=restored.external_id,
            ))
            if restored.external_id:
                observed_external_ids.add(restored.external_id)
            continue

        try:
            expected_version = workout_version(plan_snapshot(current))
            canonical_mutation_guard = lambda: _canonical_mutation_guard(
                db,
                user_id=user_id,
                target=target,
                connection_generation=connection_generation,
                canonical_id=canonical_id,
                expected_version=expected_version,
            )
            outcome = service.deliver(
                plan_snapshot(current),
                threshold_value=threshold_value,
                observed_external_ids=None,
                attempt_context=attempt_context(),
                mutation_guard=canonical_mutation_guard,
            )
        except DeliveryMutationBlockedError as exc:
            items.append(_result(
                canonical_id,
                current.date,
                action,
                "skipped",
                reason=str(exc),
            ))
            break
        except _CONNECTION_FAILURES as exc:
            recorded = _record_connection_failure(
                db,
                gate.connection,
                exc,
                trigger=trigger,
                connection_generation=connection_generation,
            )
            category = (
                type(exc).__name__
                if recorded
                else "connection_changed"
            )
            items.append(_result(
                canonical_id,
                current.date,
                action,
                "failed",
                reason=category,
            ))
            break
        if outcome.error_category == "delivery_gate_changed":
            items.append(_result(
                canonical_id,
                current.date,
                action,
                "skipped",
                reason=outcome.error or "delivery_gate_changed",
            ))
            break
        items.append(_result(
            canonical_id,
            current.date,
            action,
            "delivered" if outcome.status == "success" else "failed",
            reason=outcome.error_category or "delivery_failed",
            external_id=outcome.external_id,
        ))
        if outcome.external_id:
            observed_external_ids.add(outcome.external_id)

    failed = sum(item.status == "failed" for item in items)
    blocked = sum(item.status == "blocked" for item in items)
    logger.info(
        "Managed delivery complete user=%s target=%s trigger=%s items=%d "
        "failed=%d blocked=%d",
        user_id,
        target,
        trigger,
        len(items),
        failed,
        blocked,
    )
    return ManagedDeliveryRunResult(
        user_id=user_id,
        trigger=trigger,
        status="partial" if failed or blocked else "complete",
        target=target,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        items=tuple(items),
    )


def trigger_managed_plan_delivery(
    user_id: str,
    *,
    trigger: str,
) -> ManagedDeliveryRunResult | None:
    """Run one post-commit delivery pass without changing mutation success."""
    from db.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        return run_rolling_delivery_for_user(
            db,
            user_id=user_id,
            trigger=trigger,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Managed delivery trigger failed user=%s trigger=%s",
            user_id,
            trigger,
        )
        return None
    finally:
        db.close()


def run_scheduled_managed_deliveries() -> None:
    """Run one isolated rolling-delivery pass for every explicitly enabled user."""
    from db.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        rows = db.execute(
            select(UserConfig.user_id, UserConfig.plan_management)
        ).all()
        user_ids = []
        for user_id, raw_plan_management in rows:
            plan_management = normalize_plan_management(
                raw_plan_management
            )
            if (
                plan_management["mode"] == "praxys"
                and plan_management["delivery_enabled"]
            ):
                user_ids.append(user_id)
    finally:
        db.close()

    for user_id in user_ids:
        trigger_managed_plan_delivery(
            user_id,
            trigger="scheduled_retry",
        )
