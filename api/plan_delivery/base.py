"""Provider-neutral contracts for external workout delivery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class PreparedWorkoutDelivery:
    """Immutable delivery identity paired with its exact provider request."""

    version: str
    request: Mapping[str, Any]


@dataclass(frozen=True)
class ProviderCreateResult:
    """Confirmed provider workout creation."""

    external_id: str
    provider_account_id: str
    response: Mapping[str, Any]


@dataclass(frozen=True)
class ProviderRemoveResult:
    """Confirmed provider workout removal."""

    already_absent: bool = False


class PlanDeliveryProviderError(RuntimeError):
    """Base class for provider delivery failures."""


class ProviderAuthenticationError(PlanDeliveryProviderError):
    """The provider rejected or could not complete authentication."""


class ProviderRequestError(PlanDeliveryProviderError):
    """Praxys could not prepare a valid provider request."""


class ProviderRejectedError(PlanDeliveryProviderError):
    """The provider definitely rejected a request."""


class ProviderOutcomeUnknownError(PlanDeliveryProviderError):
    """The request may have reached the provider, so retry requires reconciliation."""


class ProviderRemovalError(PlanDeliveryProviderError):
    """The provider removal request failed."""


class ProviderReadError(PlanDeliveryProviderError):
    """The provider calendar could not be read."""


@runtime_checkable
class PlanDeliveryAdapter(Protocol):
    """Provider operations required by managed-plan delivery.

    Replacement is deliberately composed as a confirmed delete followed by a
    create so callers can persist and surface partial outcomes between steps.
    """

    target: str
    display_name: str

    @property
    def account_id(self) -> str:
        """Return the authenticated provider account identity."""
        ...

    def authenticate(self) -> None:
        """Authenticate once and cache the provider session for this adapter."""
        ...

    def prepare_workout(
        self,
        workout: Mapping[str, Any],
        *,
        threshold_value: float,
    ) -> PreparedWorkoutDelivery:
        """Prepare and fingerprint the exact provider request once."""
        ...

    def create_workout(
        self,
        prepared: PreparedWorkoutDelivery,
    ) -> ProviderCreateResult:
        """Create one workout and return its confirmed provider identity."""
        ...

    def delete_workout(self, external_id: str) -> ProviderRemoveResult:
        """Delete one provider workout."""
        ...

    def fetch_calendar(
        self,
        *,
        threshold_value: float | None = None,
        days_ahead: int = 14,
        days_back: int = 0,
        timezone_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch normalized upcoming workouts from the provider calendar."""
        ...
