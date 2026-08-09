"""Default-off rolling delivery for Praxys-managed plans."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterator, Mapping

from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from api import telemetry
from analysis.config import (
    PRAXYS_PLAN_SOURCES,
    normalize_persisted_plan_management,
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
    ProviderRateLimitError,
    ProviderReadError,
    ProviderRequestError,
    is_plan_delivery_target_registered,
    load_plan_delivery_adapter,
)
from api.plan_delivery.capabilities import (
    garmin_plan_delivery_eligible,
    plan_delivery_capability_enabled,
)
from api.plan_delivery.base import (
    adapter_provider_account_matches,
    provider_account_references_match,
)
from api.plan_reconciliation import (
    PlanReconciliationItem,
    build_plan_reconciliation,
    observation_matches_calendar,
)
from api.plan_resolution import (
    PlanResolutionConflict,
    PlanResolutionProviderError,
    PlanResolutionRateLimitError,
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

_RUN_LOCKS_GUARD = threading.Lock()
_RUN_LOCKS: dict[str, threading.Lock] = {}

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
class ManagedDeliveryReplayFence:
    """Freshness fence for one explicit operator retry override."""

    delivery_id: str
    expected_updated_at: datetime
    expected_attempt_id: int | None
    expected_attempt_number: int
    expected_state: str
    expected_operation: str | None
    expected_canonical_id: str | None
    expected_canonical_version: str | None


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
    ProviderRateLimitError,
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
    plan_management = normalize_persisted_plan_management(
        config_row.plan_management if config_row is not None else None,
        execution_target_fence=(
            config_row.plan_execution_target
            if config_row is not None
            else None
        ),
    )
    target = plan_management["execution_target"]
    if plan_management["mode"] != "praxys":
        return _DeliveryGate(target, None, "external_mode")
    if not plan_management["delivery_enabled"]:
        return _DeliveryGate(target, None, "delivery_paused")
    if not target:
        return _DeliveryGate(None, None, "execution_target_missing")
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
    garmin_eligible = False
    if target == "garmin":
        from api.statsig_client import get_statsig_user_for_account

        statsig_user = get_statsig_user_for_account(
            db,
            user_id=user_id,
            training_base=(
                config_row.training_base
                if config_row is not None
                else None
            ),
            language=(
                config_row.language
                if config_row is not None
                else None
            ),
        )
        garmin_eligible = garmin_plan_delivery_eligible(statsig_user)
    if not plan_delivery_capability_enabled(
        target,
        source_options=(
            config_row.source_options
            if config_row is not None
            and isinstance(config_row.source_options, dict)
            else {}
        ),
        connection=connection,
        garmin_eligible=garmin_eligible,
    ):
        return _DeliveryGate(
            target,
            connection,
            (
                (
                    "delivery_account_fence_required"
                    if garmin_eligible
                    else "delivery_not_eligible"
                )
                if target == "garmin"
                else "execution_target_unsupported"
            ),
        )
    if not is_plan_delivery_target_registered(target):
        return _DeliveryGate(
            target,
            connection,
            "delivery_adapter_unavailable",
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
    expected_health_fence: tuple[object, ...] | None = None,
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
    if (
        expected_health_fence is not None
        and _connection_health_fence(connection) != expected_health_fence
    ):
        db.rollback()
        return False
    if connection.status not in {"connected", "error"}:
        db.rollback()
        return False
    connection.status = "connected"
    reset_connection_backoff(connection)
    db.commit()
    return True


def _connection_health_fence(
    connection: UserConnection,
) -> tuple[object, ...]:
    return (
        connection.status,
        int(connection.consecutive_failures or 0),
        connection.next_retry_at,
        connection.last_error,
    )


@contextmanager
def _managed_delivery_run_lease(
    db: Session,
    user_id: str,
) -> Iterator[Session | None]:
    """Hold one cross-worker managed-delivery lease for a user."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        engine = _managed_delivery_lock_engine(bind)
        lock_key = int.from_bytes(
            hashlib.sha256(
                f"managed-plan:{user_id}".encode("utf-8")
            ).digest()[:8],
            "big",
            signed=True,
        )
        db.rollback()

        def hold_on_connection(
            connection: Connection,
            leased_db: Session,
        ) -> Iterator[Session | None]:
            acquired = bool(connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            ).scalar_one())
            connection.commit()
            if not acquired:
                yield None
                return
            try:
                yield leased_db
            finally:
                leased_db.rollback()
                unlocked = bool(connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": lock_key},
                ).scalar_one())
                connection.commit()
                if not unlocked:
                    logger.error(
                        "Managed-delivery advisory lock was not held: user=%s",
                        user_id,
                    )

        if isinstance(bind, Connection):
            yield from hold_on_connection(bind, db)
            return

        with engine.connect() as connection:
            leased_db = Session(bind=connection, autoflush=False)
            try:
                yield from hold_on_connection(connection, leased_db)
            finally:
                leased_db.close()
                db.expire_all()
        return

    with _RUN_LOCKS_GUARD:
        run_lock = _RUN_LOCKS.setdefault(user_id, threading.Lock())
        acquired = run_lock.acquire(blocking=False)
    try:
        yield db if acquired else None
    finally:
        if acquired:
            with _RUN_LOCKS_GUARD:
                run_lock.release()
                if _RUN_LOCKS.get(user_id) is run_lock:
                    _RUN_LOCKS.pop(user_id, None)


def _managed_delivery_lock_engine(
    bind: Engine | Connection,
) -> Engine:
    """Return an engine even when the ORM session owns a connection."""
    return bind.engine if isinstance(bind, Connection) else bind


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
    account_references = getattr(adapter, "account_references", {})
    if not isinstance(account_references, Mapping):
        account_references = {}
    record_target_calendar_sync(
        db,
        user_id=user_id,
        target=target,
        provider_account_id=adapter.account_id,
        provider_references=account_references,
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
    adapter: PlanDeliveryAdapter | None = None,
) -> None:
    lock_plan_writes(db, user_id)
    calendar_sync = db.execute(
        select(PlanTargetCalendarSync).where(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == target,
        )
    ).scalar_one_or_none()
    if (
        calendar_sync is None
        or (
            calendar_sync.provider_account_id != provider_account_id
            and (
                adapter is None
                or not adapter_provider_account_matches(
                    adapter,
                    stored_account_id=calendar_sync.provider_account_id,
                    current_account_id=provider_account_id,
                    provider_references=(
                        calendar_sync.provider_references or {}
                    ),
                )
            )
        )
    ):
        db.rollback()
        return
    observations = db.execute(
        select(PlanTargetWorkout).where(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.target == target,
        )
    ).scalars().all()
    observations = [
        observation
        for observation in observations
        if observation_matches_calendar(calendar_sync, observation)
    ]
    claimed_external_ids: dict[str, set[str]] = {}
    for claiming_delivery_id, external_id in db.execute(
        select(PlanDelivery.id, PlanDelivery.external_id).where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.external_id.is_not(None),
            PlanDelivery.state != "removed",
        )
    ):
        if external_id:
            claimed_external_ids.setdefault(
                str(external_id),
                set(),
            ).add(str(claiming_delivery_id))
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
        attempt_references = attempt.response.get("provider_references")
        if not isinstance(attempt_references, Mapping):
            attempt_references = delivery.provider_references or {}
        attempt_account_id = str(
            attempt.response.get("provider_account_id") or ""
        )
        account_matches = (
            attempt_account_id == provider_account_id
            or (
                adapter is not None
                and adapter_provider_account_matches(
                    adapter,
                    stored_account_id=attempt_account_id,
                    current_account_id=provider_account_id,
                    provider_references=attempt_references,
                )
            )
        )
        if (
            not account_matches
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
            provider_references = (
                dict(delivery.provider_references)
                if isinstance(delivery.provider_references, dict)
                else {}
            )
            template_id = str(
                provider_references.get("template_id") or ""
            ).strip()
            if template_id:
                matches = [
                    observation
                    for observation in observations
                    if (
                        observation.present
                        and observation.workout_date
                        == delivery.workout_date
                        and isinstance(
                            observation.provider_references,
                            dict,
                        )
                        and str(
                            observation.provider_references.get(
                                "template_id"
                            )
                            or ""
                        )
                        == template_id
                        and observation.external_id
                        not in preexisting_external_ids
                    )
                ]
            else:
                matches = [
                    observation
                    for observation in observations
                    if (
                        observation.present
                        and observation.workout_date
                        == delivery.workout_date
                        and delivery.provider_content_version
                        and observation.content_fingerprint
                        == delivery.provider_content_version
                        and observation.external_id
                        not in preexisting_external_ids
                    )
                ]
            checkpointed_schedule_id = str(
                provider_references.get("schedule_id") or ""
            ).strip()
            if delivery.target == "garmin" and checkpointed_schedule_id:
                matches = [
                    observation
                    for observation in matches
                    if observation.external_id == checkpointed_schedule_id
                ]
            confirmed_identity = (
                delivery.target != "garmin"
                or bool(checkpointed_schedule_id)
            )
            claimed_match = (
                len(matches) == 1
                and any(
                    claiming_delivery_id != delivery.id
                    for claiming_delivery_id in claimed_external_ids.get(
                        matches[0].external_id,
                        set(),
                    )
                )
            )
            if claimed_match:
                complete_delivery_attempt(
                    db,
                    user_id=user_id,
                    delivery_id=delivery.id,
                    attempt_id=attempt.id,
                    attempt_state="conflict",
                    error="Recovered provider identity is already claimed",
                    response={
                        **response,
                        "error_category": "provider_identity_claimed",
                        "retryable": False,
                    },
                    provider_references=provider_references,
                )
            elif len(matches) == 1 and confirmed_identity:
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
                claimed_external_ids.setdefault(
                    observation.external_id,
                    set(),
                ).add(delivery.id)
            elif (
                not matches
                and delivery.target == "garmin"
                and provider_references.get("template_marker")
                and "preexisting_template_ids" in provider_references
                and (
                    (
                        provider_references.get("template_id")
                        and not provider_references.get("schedule_started")
                    )
                    or (
                        not provider_references.get("template_id")
                        and not provider_references.get("upload_started")
                    )
                )
            ):
                complete_delivery_attempt(
                    db,
                    user_id=user_id,
                    delivery_id=delivery.id,
                    attempt_id=attempt.id,
                    attempt_state="failed",
                    delivery_state="failed",
                    error=(
                        "Garmin template creation requires a safe resume"
                    ),
                    response={
                        **response,
                        "error_category": "provider_partial_create",
                        "retryable": True,
                    },
                    provider_references=provider_references,
                )
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
    operator_retry_override: bool | None = None,
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
    if operator_retry_override is False:
        return False, "operator_recovery_stale"
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
    if operator_retry_override:
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


def _operator_retry_override(
    db: Session,
    delivery: PlanDelivery,
    replay: ManagedDeliveryReplayFence | None,
    *,
    operation: str,
) -> bool | None:
    """Return whether ``replay`` still fences the selected retryable failure."""
    if (
        replay is None
        or delivery.id != replay.delivery_id
        or replay.expected_operation != operation
    ):
        return None
    return _replay_fence_matches(db, replay, allow_started=False)


def _replay_fence_matches(
    db: Session,
    replay: ManagedDeliveryReplayFence,
    *,
    allow_started: bool,
) -> bool:
    delivery = db.execute(
        select(PlanDelivery)
        .where(PlanDelivery.id == replay.delivery_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if delivery is None:
        return False
    latest = db.execute(
        select(PlanDeliveryAttempt)
        .where(PlanDeliveryAttempt.delivery_id == delivery.id)
        .order_by(
            PlanDeliveryAttempt.attempt_number.desc(),
            PlanDeliveryAttempt.id.desc(),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().first()
    if replay.expected_canonical_id is not None:
        canonical = _current_canonical(
            db,
            user_id=delivery.user_id,
            canonical_id=replay.expected_canonical_id,
        )
        current_version = (
            workout_version(plan_snapshot(canonical))
            if canonical is not None
            else None
        )
        if current_version != replay.expected_canonical_version:
            return False

    latest_response = (
        latest.response if latest is not None and isinstance(latest.response, dict)
        else {}
    )
    original_attempt = bool(
        (latest.id if latest is not None else None)
        == replay.expected_attempt_id
        and (
            latest is None
            or latest.operation == replay.expected_operation
        )
    )
    original_delivery = bool(
        delivery.updated_at == replay.expected_updated_at
        or (
            replay.expected_state == "delivering"
            and latest is not None
            and latest.state == "failed"
            and latest_response.get("recovered_from_calendar") is True
            and latest_response.get("retryable") is True
        )
    )
    if original_attempt and original_delivery:
        return True
    if not allow_started or latest is None:
        return False

    expected_recovery_attempt = replay.expected_attempt_number + 1
    is_this_recovery = bool(
        latest.attempt_number == expected_recovery_attempt
        and latest_response.get("managed_delivery") is True
        and latest_response.get("trigger") == "admin_recovery"
    )
    if not is_this_recovery:
        return False
    if (
        latest.operation == replay.expected_operation
        and latest.state == "delivering"
        and delivery.state == "delivering"
    ):
        return True
    return bool(
        replay.expected_operation in {"deliver", "remove"}
        and latest.operation == "remove"
        and latest.state in {"delivering", "removed"}
        and latest_response.get("resolution") == "restore_praxys"
        and delivery.state in {"delivering", "removed"}
    )


def _replay_protected_guard(
    db: Session,
    replay: ManagedDeliveryReplayFence | None,
    base_guard: Callable[[], None],
) -> Callable[[], None]:
    def guard() -> None:
        base_guard()
        if replay is not None and not _replay_fence_matches(
            db,
            replay,
            allow_started=True,
        ):
            raise DeliveryMutationBlockedError("operator_recovery_stale")

    return guard


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
    if delivery.state != "synced" or not delivery.external_id:
        return False, f"delivery_{delivery.state}"

    calendar_sync = db.execute(
        select(PlanTargetCalendarSync).where(
            PlanTargetCalendarSync.user_id == delivery.user_id,
            PlanTargetCalendarSync.target == delivery.target,
        )
    ).scalar_one_or_none()
    if calendar_sync is None:
        return False, "target_workout_absent"
    if not provider_account_references_match(
        stored_account_id=calendar_sync.provider_account_id,
        current_account_id=provider_account_id,
        stored_references=calendar_sync.provider_references or {},
        current_references=delivery.provider_references or {},
    ):
        return False, "provider_account_mismatch"

    exact_candidates = db.execute(
        select(PlanTargetWorkout).where(
            PlanTargetWorkout.user_id == delivery.user_id,
            PlanTargetWorkout.target == delivery.target,
            PlanTargetWorkout.external_id == delivery.external_id,
        )
    ).scalars().all()
    exact = next(
        (
            observation
            for observation in exact_candidates
            if observation_matches_calendar(calendar_sync, observation)
        ),
        None,
    )
    if exact is None or not exact.present:
        if not provider_account_references_match(
            stored_account_id=str(delivery.provider_account_id or ""),
            current_account_id=provider_account_id,
            stored_references=delivery.provider_references or {},
            current_references=calendar_sync.provider_references or {},
        ):
            return False, "provider_account_mismatch"
        return False, "target_workout_absent"
    if not provider_account_references_match(
        stored_account_id=str(delivery.provider_account_id or ""),
        current_account_id=provider_account_id,
        stored_references=delivery.provider_references or {},
        current_references=exact.provider_references or {},
    ):
        return False, "provider_account_mismatch"
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
    replay: ManagedDeliveryReplayFence | None,
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
        operator_retry_override=_operator_retry_override(
            db,
            delivery,
            replay,
            operation="remove",
        ),
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
    window_start: date | None = None,
    adapter_loader: AdapterLoader = _default_adapter_loader,
    threshold_loader: ThresholdLoader = _default_threshold_loader,
    replay: ManagedDeliveryReplayFence | None = None,
) -> ManagedDeliveryRunResult:
    """Run one serialized rolling managed-delivery pass."""
    timestamp = now or datetime.utcnow()
    start, end = _window(window_start or timestamp.date())
    with _managed_delivery_run_lease(db, user_id) as leased_db:
        if leased_db is None:
            return ManagedDeliveryRunResult(
                user_id=user_id,
                trigger=trigger,
                status="skipped",
                target=None,
                window_start=start.isoformat(),
                window_end=end.isoformat(),
                reason="delivery_run_busy",
            )
        return _run_rolling_delivery_for_user(
            leased_db,
            user_id=user_id,
            trigger=trigger,
            now=timestamp,
            window_start=start,
            adapter_loader=adapter_loader,
            threshold_loader=threshold_loader,
            replay=replay,
        )


def _run_rolling_delivery_for_user(
    db: Session,
    *,
    user_id: str,
    trigger: str,
    now: datetime | None = None,
    window_start: date | None = None,
    adapter_loader: AdapterLoader = _default_adapter_loader,
    threshold_loader: ThresholdLoader = _default_threshold_loader,
    replay: ManagedDeliveryReplayFence | None = None,
) -> ManagedDeliveryRunResult:
    """Reconcile and deliver one user's managed plan for 14 calendar days."""
    started_at = time.monotonic()

    def finish(result: ManagedDeliveryRunResult) -> ManagedDeliveryRunResult:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        telemetry.record_managed_plan_event(
            category="delivery_run",
            action="reconcile_and_deliver",
            outcome=result.status,
            user_id=user_id,
            target=result.target,
            trigger=trigger,
            reason=result.reason,
            duration_ms=duration_ms,
        )
        for item in result.items:
            telemetry.record_managed_plan_event(
                category="delivery_item",
                action=item.action,
                outcome=item.status,
                user_id=user_id,
                target=result.target,
                trigger=trigger,
                reason=item.reason,
            )
        return result

    timestamp = now or datetime.utcnow()
    window_start, window_end = _window(window_start or timestamp.date())
    gate = _delivery_gate(db, user_id)
    if not gate.enabled:
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status=(
                "blocked"
                if gate.reason == "delivery_adapter_unavailable"
                else "skipped"
            ),
            target=gate.target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason=gate.reason,
        ))
    assert gate.target is not None
    assert gate.connection is not None
    target = gate.target
    connection_generation = connection_credentials_generation(
        gate.connection
    )
    connection_health_fence = _connection_health_fence(gate.connection)
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
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="complete",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
        ))

    threshold_value = threshold_loader(db, user_id)
    try:
        adapter = adapter_loader(db, user_id, target)
        db.rollback()
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
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="skipped",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason=str(exc),
        ))
    except (
        DeliveryCredentialsInvalid,
        DeliveryCredentialsUnavailable,
        ProviderAuthenticationError,
        ProviderRateLimitError,
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
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="blocked",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason=category,
        ))

    if not _record_connection_success(
        db,
        user_id=user_id,
        target=target,
        connection_generation=connection_generation,
        expected_health_fence=connection_health_fence,
    ):
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="skipped",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason="connection_changed",
        ))
    _recover_managed_inflight_attempts(
        db,
        user_id=user_id,
        target=target,
        provider_account_id=adapter.account_id,
        connection_generation=connection_generation,
        deliveries=owned_deliveries,
        adapter=adapter,
    )
    reconciliation = build_plan_reconciliation(
        db,
        user_id=user_id,
        target=target,
        start=window_start,
        end=window_end,
    )
    if reconciliation is None:
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="blocked",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            reason="calendar_reconciliation_unavailable",
        ))

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

    provider_mutation_guard = _replay_protected_guard(
        db,
        replay,
        mutation_guard,
    )
    items: list[ManagedDeliveryItemResult] = []
    stop_after_owned_removal = False

    for delivery in owned_deliveries:
        if replay is not None and (
            delivery.id != replay.delivery_id
            or replay.expected_operation != "remove"
        ):
            continue
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
            mutation_guard=provider_mutation_guard,
            replay=replay,
        )
        items.append(removal_result)
        if stop_batch:
            stop_after_owned_removal = True
            break

    if stop_after_owned_removal:
        failed = sum(item.status == "failed" for item in items)
        blocked = sum(item.status == "blocked" for item in items)
        return finish(ManagedDeliveryRunResult(
            user_id=user_id,
            trigger=trigger,
            status="partial" if failed or blocked else "complete",
            target=target,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            items=tuple(items),
        ))

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
        if (
            replay is not None
            and (
                item.delivery is None
                or item.delivery.id != replay.delivery_id
            )
        ):
            continue
        if (
            replay is not None
            and replay.expected_operation == "deliver"
            and (
                replay.expected_canonical_version is None
                or workout_version(plan_snapshot(canonical))
                != replay.expected_canonical_version
            )
        ):
            items.append(_result(
                canonical_id,
                canonical.date,
                "deliver",
                "skipped",
                reason="canonical_changed_during_recovery",
            ))
            continue
        replay_stale_pending = bool(
            replay is not None
            and item.delivery is not None
            and item.delivery.id == replay.delivery_id
            and item.delivery.state == "pending"
            and replay.expected_attempt_id is None
            and item.observation is None
        )
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
            rest_mutation_guard = provider_mutation_guard
            if current_rest is not None:
                expected_rest_version = workout_version(
                    plan_snapshot(current_rest)
                )
                rest_mutation_guard = _replay_protected_guard(
                    db,
                    replay,
                    lambda: _rest_mutation_guard(
                        db,
                        user_id=user_id,
                        target=target,
                        connection_generation=connection_generation,
                        canonical_id=canonical_id,
                        expected_version=expected_rest_version,
                    ),
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
                replay=replay,
            )
            items.append(removal_result)
            if stop_batch:
                break
            continue

        action = "deliver"
        if item.state in {"matching", "pending_observation"}:
            if not replay_stale_pending:
                items.append(_result(
                    canonical_id,
                    canonical.date,
                    action,
                    (
                        "blocked"
                        if (
                            replay is not None
                            and item.delivery is not None
                            and item.delivery.id == replay.delivery_id
                            and item.delivery.state == "pending"
                        )
                        else "skipped"
                    ),
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
                    operator_retry_override=_operator_retry_override(
                        db,
                        item.delivery,
                        replay,
                        operation="deliver",
                    ),
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
        elif item.state != "not_delivered" and not replay_stale_pending:
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
        if not threshold_value and target == "stryd":
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
                operator_retry_override=_operator_retry_override(
                    db,
                    item.delivery,
                    replay,
                    operation="deliver",
                ),
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
                operator_retry_override=_operator_retry_override(
                    db,
                    item.delivery,
                    replay,
                    operation="remove",
                ),
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
                canonical_mutation_guard = _replay_protected_guard(
                    db,
                    replay,
                    lambda: _canonical_mutation_guard(
                        db,
                        user_id=user_id,
                        target=target,
                        connection_generation=connection_generation,
                        canonical_id=canonical_id,
                        expected_version=expected_version,
                    ),
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
            except PlanResolutionRateLimitError as exc:
                recorded = _record_connection_failure(
                    db,
                    gate.connection,
                    ProviderRateLimitError(str(exc)),
                    trigger=trigger,
                    connection_generation=connection_generation,
                )
                items.append(_result(
                    canonical_id,
                    current.date,
                    action,
                    "failed",
                    reason=(
                        "provider_rate_limited"
                        if recorded
                        else "connection_changed"
                    ),
                ))
                break
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
            canonical_mutation_guard = _replay_protected_guard(
                db,
                replay,
                lambda: _canonical_mutation_guard(
                    db,
                    user_id=user_id,
                    target=target,
                    connection_generation=connection_generation,
                    canonical_id=canonical_id,
                    expected_version=expected_version,
                ),
            )
            outcome = service.deliver(
                plan_snapshot(current),
                threshold_value=threshold_value,
                observed_external_ids=None,
                attempt_context=attempt_context(),
                mutation_guard=canonical_mutation_guard,
                expected_delivery_id=(
                    replay.delivery_id
                    if replay is not None
                    else None
                ),
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
        if outcome.error_category == "provider_rate_limited":
            _record_connection_failure(
                db,
                gate.connection,
                ProviderRateLimitError(
                    outcome.error or "provider rate limited"
                ),
                trigger=trigger,
                connection_generation=connection_generation,
            )
            break
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
    return finish(ManagedDeliveryRunResult(
        user_id=user_id,
        trigger=trigger,
        status="partial" if failed or blocked else "complete",
        target=target,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        items=tuple(items),
    ))


def trigger_managed_plan_delivery(
    user_id: str,
    *,
    trigger: str,
    window_start: date | None = None,
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
            window_start=window_start,
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
            select(
                UserConfig.user_id,
                UserConfig.plan_management,
                UserConfig.plan_execution_target,
            )
        ).all()
        user_ids = []
        for user_id, raw_plan_management, execution_target_fence in rows:
            plan_management = normalize_persisted_plan_management(
                raw_plan_management,
                execution_target_fence=execution_target_fence,
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
