"""Provider-neutral contracts for external workout delivery."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class PreparedWorkoutDelivery:
    """Immutable delivery identity paired with its exact provider request."""

    version: str
    request: Mapping[str, Any]
    content_version: str | None = None


@dataclass(frozen=True)
class ProviderCreateResult:
    """Confirmed provider workout creation."""

    external_id: str
    provider_account_id: str
    response: Mapping[str, Any]
    provider_references: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRemoveResult:
    """Confirmed provider workout removal."""

    already_absent: bool = False
    response: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderMutationHooks:
    """Durability and replay fences invoked around provider side effects."""

    provider_references: Mapping[str, Any]
    before_mutation: Callable[[], None]
    checkpoint: Callable[[Mapping[str, Any], str | None], None]


NOOP_PROVIDER_MUTATION_HOOKS = ProviderMutationHooks(
    provider_references={},
    before_mutation=lambda: None,
    checkpoint=lambda _references, _external_id: None,
)


def provider_account_references_match(
    *,
    stored_account_id: str,
    current_account_id: str,
    stored_references: Mapping[str, Any],
    current_references: Mapping[str, Any],
) -> bool:
    """Compare account keys, preferring a shared immutable profile fence."""
    stored_profile = str(
        stored_references.get("profile_account_id") or ""
    ).strip()
    current_profile = str(
        current_references.get("profile_account_id") or ""
    ).strip()
    if stored_profile and current_profile:
        return stored_profile == current_profile
    return stored_account_id == current_account_id


def provider_snapshot_references_match(
    *,
    stored_account_id: str,
    current_account_id: str,
    stored_references: Mapping[str, Any],
    current_references: Mapping[str, Any],
) -> bool:
    """Match snapshot evidence without weakening an immutable current fence."""
    current_profile = str(
        current_references.get("profile_account_id") or ""
    ).strip()
    if current_profile:
        stored_profile = str(
            stored_references.get("profile_account_id") or ""
        ).strip()
        return bool(stored_profile) and stored_profile == current_profile
    return stored_account_id == current_account_id


def adapter_provider_account_matches(
    adapter: PlanDeliveryAdapter,
    *,
    stored_account_id: str,
    current_account_id: str,
    provider_references: Mapping[str, Any],
) -> bool:
    """Accept an adapter's immutable identity alias when account keys rotate."""
    matcher = getattr(adapter, "matches_provider_account", None)
    if (
        callable(matcher)
        and str(
            provider_references.get("profile_account_id") or ""
        ).strip()
    ):
        return bool(matcher(stored_account_id, provider_references))
    if stored_account_id == current_account_id:
        return True
    if not callable(matcher):
        return False
    return bool(matcher(stored_account_id, provider_references))


class PlanDeliveryProviderError(RuntimeError):
    """Base class for provider delivery failures."""


class ProviderAuthenticationError(PlanDeliveryProviderError):
    """The provider rejected or could not complete authentication."""


class ProviderAuthenticationRequiredError(ProviderAuthenticationError):
    """The provider confirmed that the user must reconnect credentials."""


class ProviderRequestError(PlanDeliveryProviderError):
    """Praxys could not prepare a valid provider request."""


class ProviderRejectedError(PlanDeliveryProviderError):
    """The provider definitely rejected a request."""


class ProviderTransientError(PlanDeliveryProviderError):
    """The provider safely rejected a request that may be retried later."""


class ProviderRateLimitError(ProviderTransientError):
    """The provider rejected work due to an account-level rate limit."""


class ProviderOutcomeUnknownError(PlanDeliveryProviderError):
    """The request may have reached the provider, so retry requires reconciliation."""

    def __init__(
        self,
        message: str,
        *,
        provider_references: Mapping[str, Any] | None = None,
        external_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_references = dict(provider_references or {})
        self.external_id = external_id


class ProviderRemovalError(PlanDeliveryProviderError):
    """The provider removal request failed."""


class ProviderRemovalOutcomeUnknownError(ProviderRemovalError):
    """Removal may have happened and must be reconciled before replay."""

    def __init__(
        self,
        message: str,
        *,
        provider_references: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_references = dict(provider_references or {})


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
        *,
        hooks: ProviderMutationHooks = NOOP_PROVIDER_MUTATION_HOOKS,
    ) -> ProviderCreateResult:
        """Create one workout and return its confirmed provider identity."""
        ...

    def delete_workout(
        self,
        external_id: str,
        *,
        hooks: ProviderMutationHooks = NOOP_PROVIDER_MUTATION_HOOKS,
    ) -> ProviderRemoveResult:
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
