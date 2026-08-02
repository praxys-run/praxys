"""Explicit cleanup of future workouts delivered by Praxys."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Callable, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import normalize_plan_management
from api import telemetry
from api.plan_delivery import (
    DeliveryMutationBlockedError,
    DeliveryAccountMismatchError,
    DeliveryAccountVerificationError,
    DeliveryBusyError,
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
    DeliveryFinalizationError,
    DeliveryNotFoundError,
    DeliveryRemovalFailedError,
    DeliveryStartError,
    PlanDeliveryAdapter,
    PlanDeliveryService,
    ProviderAuthenticationError,
    UnsupportedDeliveryTargetError,
    capture_delivery_connection_generation,
    load_plan_delivery_adapter,
)
from db.connection_credentials import connection_credentials_generation
from db.cache_revision import bump_revisions
from db.models import PlanDelivery, UserConfig, UserConnection
from db.plan_ledger import (
    append_delivery_event,
    delivery_canonical_id,
    lock_plan_writes,
)


class PlanCleanupRequiresExternalMode(RuntimeError):
    """Cleanup was requested before managed delivery was disabled."""


class PlanCleanupAmbiguousTargets(RuntimeError):
    """Cleanup found outstanding deliveries for more than one target."""


PlanCleanupItemStatus = Literal[
    "removed",
    "already_absent",
    "blocked",
    "failed",
]
PlanCleanupStatus = Literal["complete", "partial"]


@dataclass(frozen=True)
class PlanCleanupItemResult:
    """Outcome for one future delivery considered for cleanup."""

    canonical_id: str | None
    workout_date: str
    external_id: str | None
    status: PlanCleanupItemStatus
    reason: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Return the API representation."""
        return asdict(self)


@dataclass(frozen=True)
class PlanCleanupResult:
    """Summary of an explicit future-delivery cleanup."""

    status: PlanCleanupStatus
    target: str | None
    window_start: str
    removed_count: int
    remaining_count: int
    items: tuple[PlanCleanupItemResult, ...] = ()

    def to_dict(self) -> dict:
        """Return the API representation."""
        return {
            "status": self.status,
            "target": self.target,
            "window": {"start": self.window_start, "end": None},
            "removed_count": self.removed_count,
            "remaining_count": self.remaining_count,
            "items": [item.to_dict() for item in self.items],
        }


AdapterLoader = Callable[[], PlanDeliveryAdapter]


def _finish_cleanup(
    *,
    user_id: str,
    result: PlanCleanupResult,
) -> PlanCleanupResult:
    telemetry.record_managed_plan_event(
        category="cleanup",
        action="remove_future",
        outcome=result.status,
        user_id=user_id,
        target=result.target,
        trigger="leave_managed_mode",
        reason=(
            "remaining_deliveries"
            if result.remaining_count > 0
            else None
        ),
    )
    for item in result.items:
        telemetry.record_managed_plan_event(
            category="cleanup_item",
            action="remove",
            outcome=item.status,
            user_id=user_id,
            target=result.target,
            trigger="leave_managed_mode",
            reason=item.reason,
        )
    return result


def _item(
    delivery: PlanDelivery,
    *,
    status: PlanCleanupItemStatus,
    reason: str | None = None,
) -> PlanCleanupItemResult:
    return PlanCleanupItemResult(
        canonical_id=delivery_canonical_id(delivery),
        workout_date=delivery.workout_date.isoformat(),
        external_id=delivery.external_id,
        status=status,
        reason=reason,
    )


def _authentication_reason(exc: BaseException) -> str:
    if isinstance(exc, UnsupportedDeliveryTargetError):
        return "delivery_adapter_unavailable"
    if isinstance(exc, DeliveryCredentialsUnavailable):
        return "credentials_unavailable"
    if isinstance(exc, DeliveryCredentialsInvalid):
        return "credentials_invalid"
    return "provider_authentication_failed"


def cleanup_future_plan_deliveries(
    db: Session,
    *,
    user_id: str,
    today: date | None = None,
    adapter_loader: AdapterLoader | None = None,
) -> PlanCleanupResult:
    """Remove future provider workouts owned by the caller's delivery ledger.

    Managed delivery must already be disabled in external mode. This ordering
    makes "leave and remove" fail safe: if provider cleanup is interrupted,
    Praxys remains unable to create or replace target workouts.
    """
    start = today or date.today()
    config_row = db.execute(
        select(UserConfig).where(UserConfig.user_id == user_id)
    ).scalar_one_or_none()
    plan_management = normalize_plan_management(
        config_row.plan_management if config_row is not None else None
    )
    if (
        plan_management["mode"] != "external"
        or plan_management["delivery_enabled"]
    ):
        raise PlanCleanupRequiresExternalMode(
            "Leave managed mode before removing delivered workouts"
        )

    configured_target = plan_management["execution_target"]

    deliveries = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.workout_date >= start,
            PlanDelivery.state != "removed",
        )
        .order_by(PlanDelivery.workout_date, PlanDelivery.created_at)
    ).scalars().all()
    if not deliveries:
        return _finish_cleanup(
            user_id=user_id,
            result=PlanCleanupResult(
            status="complete",
            target=configured_target,
            window_start=start.isoformat(),
            removed_count=0,
            remaining_count=0,
            ),
        )
    delivery_targets = sorted({
        str(delivery.target).strip()
        for delivery in deliveries
        if str(delivery.target).strip()
    })
    if len(delivery_targets) != 1:
        raise PlanCleanupAmbiguousTargets(
            "Outstanding Praxys deliveries span multiple execution targets"
        )
    target = delivery_targets[0]

    results: list[PlanCleanupItemResult] = []
    terminalized_absent = False
    removable = [
        delivery
        for delivery in deliveries
        if delivery.state in {"synced", "delivering"}
        and delivery.external_id
    ]
    removable_ids = {delivery.id for delivery in removable}
    for delivery in deliveries:
        if delivery.id not in removable_ids:
            if (
                delivery.external_id is None
                and delivery.state in {"pending", "failed"}
            ):
                delivery.state = "removed"
                delivery.last_error = None
                delivery.updated_at = datetime.utcnow()
                append_delivery_event(
                    db,
                    delivery,
                    operation="remove",
                    state="removed",
                    external_id=None,
                    response={
                        "cleanup": "leave_managed_mode",
                        "already_absent": True,
                        "ledger_only": True,
                    },
                )
                terminalized_absent = True
                results.append(
                    _item(
                        delivery,
                        status="already_absent",
                        reason="no_provider_workout",
                    )
                )
                continue
            results.append(
                _item(
                    delivery,
                    status="blocked",
                    reason=f"delivery_{delivery.state}",
                )
            )

    if terminalized_absent:
        bump_revisions(db, user_id, ["plans"])
        db.commit()

    if removable:
        try:
            connection_generation = capture_delivery_connection_generation(
                db,
                user_id=user_id,
                target=target,
            )
        except DeliveryMutationBlockedError as exc:
            results.extend(
                _item(
                    delivery,
                    status="failed",
                    reason=str(exc),
                )
                for delivery in removable
            )
            connection_generation = None

    if removable and connection_generation is not None:
        loader = adapter_loader or (
            lambda: load_plan_delivery_adapter(
                db,
                user_id=user_id,
                target=target,
            )
        )
        service = PlanDeliveryService(
            db=db,
            user_id=user_id,
            target=target,
            adapter_loader=loader,
        )
        try:
            service.authenticate()
        except (
            DeliveryCredentialsUnavailable,
            DeliveryCredentialsInvalid,
            ProviderAuthenticationError,
            UnsupportedDeliveryTargetError,
        ) as exc:
            reason = _authentication_reason(exc)
            results.extend(
                _item(delivery, status="failed", reason=reason)
                for delivery in removable
            )
        else:
            blocked_reason: str | None = None

            def mutation_guard() -> None:
                lock_plan_writes(db, user_id)
                fresh_config = db.execute(
                    select(UserConfig)
                    .where(UserConfig.user_id == user_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).scalar_one_or_none()
                fresh_management = normalize_plan_management(
                    fresh_config.plan_management
                    if fresh_config is not None
                    else None
                )
                if (
                    fresh_management["mode"] != "external"
                    or fresh_management["delivery_enabled"]
                    or (
                        fresh_management["execution_target"]
                        != configured_target
                    )
                ):
                    raise DeliveryMutationBlockedError(
                        "managed_plan_state_changed"
                    )
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
                    raise DeliveryMutationBlockedError(
                        "connection_missing"
                    )
                if connection.status != "connected":
                    raise DeliveryMutationBlockedError(
                        f"connection_{connection.status}"
                    )
                if (
                    connection_credentials_generation(connection)
                    != connection_generation
                ):
                    raise DeliveryMutationBlockedError(
                        "connection_changed"
                    )

            for delivery in removable:
                if blocked_reason is not None:
                    results.append(
                        _item(
                            delivery,
                            status="blocked",
                            reason=blocked_reason,
                        )
                    )
                    continue
                try:
                    removal = service.remove(
                        str(delivery.external_id),
                        attempt_context={
                            "managed_cleanup": True,
                            "trigger": "leave_managed_mode",
                        },
                        mutation_guard=mutation_guard,
                    )
                except DeliveryMutationBlockedError as exc:
                    blocked_reason = str(exc)
                    results.append(
                        _item(
                            delivery,
                            status="blocked",
                            reason=blocked_reason,
                        )
                    )
                except DeliveryBusyError:
                    results.append(
                        _item(
                            delivery,
                            status="blocked",
                            reason="delivery_busy",
                        )
                    )
                except DeliveryAccountMismatchError:
                    results.append(
                        _item(
                            delivery,
                            status="blocked",
                            reason="provider_account_mismatch",
                        )
                    )
                except DeliveryNotFoundError:
                    results.append(
                        _item(
                            delivery,
                            status="blocked",
                            reason="delivery_not_found",
                        )
                    )
                except DeliveryAccountVerificationError:
                    results.append(
                        _item(
                            delivery,
                            status="failed",
                            reason="provider_account_verification_failed",
                        )
                    )
                except (
                    DeliveryCredentialsUnavailable,
                    DeliveryCredentialsInvalid,
                    ProviderAuthenticationError,
                ):
                    results.append(
                        _item(
                            delivery,
                            status="failed",
                            reason="provider_authentication_failed",
                        )
                    )
                except DeliveryRemovalFailedError:
                    results.append(
                        _item(
                            delivery,
                            status="failed",
                            reason="provider_removal_failed",
                        )
                    )
                except DeliveryStartError:
                    results.append(
                        _item(
                            delivery,
                            status="failed",
                            reason="removal_start_failed",
                        )
                    )
                except DeliveryFinalizationError:
                    results.append(
                        _item(
                            delivery,
                            status="failed",
                            reason="removal_finalization_failed",
                        )
                    )
                else:
                    results.append(
                        _item(
                            delivery,
                            status="already_absent"
                            if removal.already_absent
                            else "removed",
                        )
                    )

    results.sort(
        key=lambda item: (
            item.workout_date,
            item.canonical_id or "",
            item.external_id or "",
        )
    )
    removed_count = sum(
        item.status in {"removed", "already_absent"}
        for item in results
    )
    remaining_count = len(results) - removed_count
    return _finish_cleanup(
        user_id=user_id,
        result=PlanCleanupResult(
            status="complete" if remaining_count == 0 else "partial",
            target=target,
            window_start=start.isoformat(),
            removed_count=removed_count,
            remaining_count=remaining_count,
            items=tuple(results),
        ),
    )
