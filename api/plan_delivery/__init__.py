"""Provider-neutral managed-plan delivery service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from api.plan_delivery.base import (
    PlanDeliveryAdapter,
    PreparedWorkoutDelivery,
    ProviderAuthenticationError,
    ProviderAuthenticationRequiredError,
    ProviderMutationHooks,
    ProviderOutcomeUnknownError,
    ProviderRateLimitError,
    ProviderReadError,
    ProviderRejectedError,
    ProviderRemovalError,
    ProviderRemovalOutcomeUnknownError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.credentials import (
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
    resolve_delivery_credentials,
)
from api.plan_delivery.guards import (
    capture_delivery_connection_generation,
    guard_delivery_connection,
)
from api.plan_delivery.garmin import GarminPlanDeliveryAdapter
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
from db.connection_credentials import connection_credentials_generation
from db.models import UserConnection


class UnsupportedDeliveryTargetError(ValueError):
    """No delivery adapter is registered for the requested target."""


@dataclass(frozen=True)
class DeliveryAdapterContext:
    """Authenticated-user context available to one adapter instance."""

    user_id: str
    credentials: Mapping[str, Any]
    source_options: Mapping[str, Any]
    credential_generation: str | None = None
    token_publisher: Callable[[], bool] | None = None


AdapterFactory = Callable[[DeliveryAdapterContext], PlanDeliveryAdapter]

_ADAPTER_TYPES: dict[str, AdapterFactory] = {
    StrydPlanDeliveryAdapter.target: (
        lambda context: StrydPlanDeliveryAdapter(context.credentials)
    ),
    GarminPlanDeliveryAdapter.target: (
        lambda context: GarminPlanDeliveryAdapter(
            context.credentials,
            user_id=context.user_id,
            source_options=context.source_options,
            credential_generation=context.credential_generation,
            token_publisher=context.token_publisher,
        )
    ),
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
    credential_generation = None
    token_publisher = None
    if target == GarminPlanDeliveryAdapter.target:
        connection = db.query(UserConnection).filter(
            UserConnection.user_id == user_id,
            UserConnection.platform == target,
        ).first()
        if connection is None:
            raise DeliveryCredentialsUnavailable(
                f"No credentials available for {target}"
            )
        credential_generation = connection_credentials_generation(
            connection
        )

        def publish_tokens() -> bool:
            from api.routes.sync import publish_garmin_generation_tokens
            from db.sync_scheduler import SCHEDULABLE_STATUSES

            assert credential_generation is not None
            return publish_garmin_generation_tokens(
                db,
                user_id=user_id,
                credential_generation=credential_generation,
                allowed_statuses=SCHEDULABLE_STATUSES,
            )

        token_publisher = publish_tokens
    credentials = resolve_delivery_credentials(
        db,
        user_id=user_id,
        target=target,
    )
    from analysis.config import load_config_from_db

    config = load_config_from_db(user_id, db)
    return adapter_type(DeliveryAdapterContext(
        user_id=user_id,
        credentials=credentials,
        source_options=config.source_options,
        credential_generation=credential_generation,
        token_publisher=token_publisher,
    ))


__all__ = [
    "DeliveryAccountMismatchError",
    "DeliveryAccountVerificationError",
    "DeliveryBusyError",
    "DeliveryCredentialsInvalid",
    "DeliveryCredentialsUnavailable",
    "DeliveryAdapterContext",
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
    "ProviderMutationHooks",
    "ProviderOutcomeUnknownError",
    "ProviderRateLimitError",
    "ProviderReadError",
    "ProviderRejectedError",
    "ProviderRemovalError",
    "ProviderRemovalOutcomeUnknownError",
    "ProviderRequestError",
    "ProviderTransientError",
    "RemovalResult",
    "UnsupportedDeliveryTargetError",
    "capture_delivery_connection_generation",
    "guard_delivery_connection",
    "is_plan_delivery_target_registered",
    "load_plan_delivery_adapter",
    "register_plan_delivery_adapter",
]
