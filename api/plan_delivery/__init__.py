"""Provider-neutral managed-plan delivery service."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from api.plan_delivery.base import (
    PlanDeliveryAdapter,
    PreparedWorkoutDelivery,
    ProviderAuthenticationError,
    ProviderOutcomeUnknownError,
    ProviderReadError,
    ProviderRejectedError,
    ProviderRemovalError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.credentials import (
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
    resolve_delivery_credentials,
)
from api.plan_delivery.service import (
    DeliveryAccountMismatchError,
    DeliveryAccountVerificationError,
    DeliveryBusyError,
    DeliveryFinalizationError,
    DeliveryMutationBlockedError,
    DeliveryNotFoundError,
    DeliveryRemovalFailedError,
    DeliveryResult,
    DeliveryStartError,
    PlanDeliveryService,
    RemovalResult,
)
from api.plan_delivery.stryd import StrydPlanDeliveryAdapter


class UnsupportedDeliveryTargetError(ValueError):
    """No delivery adapter is registered for the requested target."""


AdapterFactory = Callable[[Mapping[str, Any]], PlanDeliveryAdapter]

_ADAPTER_TYPES: dict[str, AdapterFactory] = {
    StrydPlanDeliveryAdapter.target: StrydPlanDeliveryAdapter,
}


def register_plan_delivery_adapter(
    target: str,
    adapter_type: AdapterFactory,
) -> None:
    """Register a provider adapter without changing delivery callers."""
    _ADAPTER_TYPES[target] = adapter_type


def is_plan_delivery_target_registered(target: str) -> bool:
    """Return whether a provider adapter is registered for the target."""
    return target in _ADAPTER_TYPES


def load_plan_delivery_adapter(
    db: Session,
    *,
    user_id: str,
    target: str,
) -> PlanDeliveryAdapter:
    """Build a delivery adapter using only the caller's credentials."""
    adapter_type = _ADAPTER_TYPES.get(target)
    if adapter_type is None:
        raise UnsupportedDeliveryTargetError(
            f"Unsupported plan delivery target: {target}"
        )
    credentials = resolve_delivery_credentials(
        db,
        user_id=user_id,
        target=target,
    )
    return adapter_type(credentials)


__all__ = [
    "DeliveryAccountMismatchError",
    "DeliveryAccountVerificationError",
    "DeliveryBusyError",
    "DeliveryCredentialsInvalid",
    "DeliveryCredentialsUnavailable",
    "DeliveryFinalizationError",
    "DeliveryMutationBlockedError",
    "DeliveryNotFoundError",
    "DeliveryRemovalFailedError",
    "DeliveryResult",
    "DeliveryStartError",
    "PlanDeliveryAdapter",
    "PlanDeliveryService",
    "PreparedWorkoutDelivery",
    "ProviderAuthenticationError",
    "ProviderOutcomeUnknownError",
    "ProviderReadError",
    "ProviderRejectedError",
    "ProviderRemovalError",
    "ProviderRequestError",
    "ProviderTransientError",
    "RemovalResult",
    "UnsupportedDeliveryTargetError",
    "is_plan_delivery_target_registered",
    "load_plan_delivery_adapter",
    "register_plan_delivery_adapter",
]
