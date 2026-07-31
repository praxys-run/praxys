"""Explicit cleanup of future workouts delivered by Praxys."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Callable, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import normalize_plan_management
from api.plan_delivery import (
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
    load_plan_delivery_adapter,
)
from db.models import PlanDelivery, UserConfig
from db.plan_ledger import delivery_canonical_id


class PlanCleanupRequiresExternalMode(RuntimeError):
    """Cleanup was requested before managed delivery was disabled."""


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

    target = plan_management["execution_target"]
    if not target:
        return PlanCleanupResult(
            status="complete",
            target=None,
            window_start=start.isoformat(),
            removed_count=0,
            remaining_count=0,
        )

    deliveries = db.execute(
        select(PlanDelivery)
        .where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.target == target,
            PlanDelivery.workout_date >= start,
            PlanDelivery.state != "removed",
            PlanDelivery.external_id.is_not(None),
        )
        .order_by(PlanDelivery.workout_date, PlanDelivery.created_at)
    ).scalars().all()
    if not deliveries:
        return PlanCleanupResult(
            status="complete",
            target=target,
            window_start=start.isoformat(),
            removed_count=0,
            remaining_count=0,
        )

    results: list[PlanCleanupItemResult] = []
    removable = [
        delivery
        for delivery in deliveries
        if delivery.state == "synced" and delivery.external_id
    ]
    removable_ids = {delivery.id for delivery in removable}
    for delivery in deliveries:
        if delivery.id not in removable_ids:
            results.append(
                _item(
                    delivery,
                    status="blocked",
                    reason=f"delivery_{delivery.state}",
                )
            )

    if removable:
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
            for delivery in removable:
                try:
                    removal = service.remove(
                        str(delivery.external_id),
                        attempt_context={
                            "managed_cleanup": True,
                            "trigger": "leave_managed_mode",
                        },
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
    return PlanCleanupResult(
        status="complete" if remaining_count == 0 else "partial",
        target=target,
        window_start=start.isoformat(),
        removed_count=removed_count,
        remaining_count=remaining_count,
        items=tuple(results),
    )
