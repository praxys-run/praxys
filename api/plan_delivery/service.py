"""Ledger-backed orchestration for provider workout delivery."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Mapping

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.plan_delivery.base import (
    PlanDeliveryAdapter,
    ProviderAuthenticationError,
    ProviderOutcomeUnknownError,
    ProviderReadError,
    ProviderRejectedError,
    ProviderRemovalError,
    ProviderRequestError,
)
from api.plan_delivery.credentials import (
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
)
from db.cache_revision import bump_revisions
from db.models import TrainingPlan
from db.plan_reconciliation import mark_target_workout_absent
from db.plan_ledger import (
    begin_delivery_attempt,
    complete_delivery_attempt,
    find_delivery_by_external_id,
    find_unverified_delivery_for_date,
    get_or_create_delivery,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryResult:
    """One manual delivery outcome."""

    status: str
    external_id: str | None = None
    error: str | None = None
    delivered_at: datetime | None = None


@dataclass(frozen=True)
class RemovalResult:
    """One manual removal outcome."""

    external_id: str
    already_absent: bool = False


class DeliveryNotFoundError(LookupError):
    """The caller does not own a matching delivery record."""


class DeliveryBusyError(RuntimeError):
    """Another attempt currently owns the delivery."""


class DeliveryStartError(RuntimeError):
    """The delivery attempt could not be started durably."""


class DeliveryAccountMismatchError(RuntimeError):
    """The delivery belongs to a different provider account."""


class DeliveryAccountVerificationError(RuntimeError):
    """The provider account for a migrated delivery could not be verified."""


class DeliveryRemovalFailedError(RuntimeError):
    """The provider workout could not be removed."""


class DeliveryFinalizationError(RuntimeError):
    """The provider changed but the durable ledger could not be finalized."""


class PlanDeliveryService:
    """Coordinate provider calls with durable per-user delivery state."""

    def __init__(
        self,
        *,
        db: Session,
        user_id: str,
        target: str,
        adapter_loader: Callable[[], PlanDeliveryAdapter],
    ):
        self.db = db
        self.user_id = user_id
        self.target = target
        self._adapter_loader = adapter_loader
        self._loaded_adapter: PlanDeliveryAdapter | None = None

    def _adapter(self) -> PlanDeliveryAdapter:
        if self._loaded_adapter is None:
            self._loaded_adapter = self._adapter_loader()
        return self._loaded_adapter

    def authenticate(self) -> None:
        """Authenticate the configured provider before a batch operation."""
        self._adapter().authenticate()

    def _cleanup_new_delivery(self, delivery, created: bool) -> None:
        if created:
            self.db.delete(delivery)
            self.db.commit()
        else:
            self.db.rollback()

    def _record_terminal_attempt(
        self,
        *,
        delivery_id: str,
        attempt_id: int,
        state: str,
        error: str | None = None,
        external_id: str | None = None,
        response: Mapping[str, Any] | None = None,
        provider_account_id: str | None = None,
        delivery_state: str | None = None,
        commit: bool = True,
    ) -> bool:
        updated = complete_delivery_attempt(
            self.db,
            user_id=self.user_id,
            delivery_id=delivery_id,
            attempt_id=attempt_id,
            attempt_state=state,
            delivery_state=delivery_state,
            external_id=external_id,
            error=error,
            response=response,
            provider_account_id=provider_account_id,
        )
        bump_revisions(self.db, self.user_id, ["plans"])
        if commit:
            self.db.commit()
        return updated

    def deliver(
        self,
        snapshot: Mapping[str, Any],
        *,
        threshold_value: float,
        observed_external_ids: object = None,
    ) -> DeliveryResult:
        """Deliver one canonical workout version to the configured target."""
        workout_date = str(snapshot["date"])
        provider_name = self.target.capitalize()
        try:
            adapter = self._adapter()
            prepared = adapter.prepare_workout(
                snapshot,
                threshold_value=threshold_value,
            )
            adapter.authenticate()
            provider_account_id = adapter.account_id
        except ProviderRequestError as exc:
            return DeliveryResult(status="error", error=str(exc))

        try:
            delivery, delivery_created = get_or_create_delivery(
                self.db,
                user_id=self.user_id,
                target=self.target,
                snapshot=snapshot,
                workout_version_override=prepared.version,
                provider_content_version_override=(
                    prepared.content_version or prepared.version
                ),
            )
            if (
                delivery.provider_account_id
                and delivery.provider_account_id != provider_account_id
            ):
                self._cleanup_new_delivery(delivery, delivery_created)
                return DeliveryResult(
                    status="error",
                    error=(
                        f"This {provider_name} delivery belongs to a "
                        f"different {provider_name} account"
                    ),
                )
            unverified = find_unverified_delivery_for_date(
                self.db,
                user_id=self.user_id,
                target=self.target,
                workout_date=delivery.workout_date,
            )
            if unverified is not None:
                self._cleanup_new_delivery(delivery, delivery_created)
                return DeliveryResult(
                    status="error",
                    error=(
                        f"Delivery outcome is uncertain; sync {provider_name} before retrying"
                    ),
                )

            delivery, attempt, disposition = begin_delivery_attempt(
                self.db,
                delivery,
                operation="deliver",
            )
            if disposition == "already_complete":
                external_id = str(delivery.external_id)
                delivered_at = delivery.delivered_at
                self.db.commit()
                return DeliveryResult(
                    status="success",
                    external_id=external_id,
                    delivered_at=delivered_at,
                )
            if disposition == "reconciliation_required":
                self._cleanup_new_delivery(delivery, delivery_created)
                return DeliveryResult(
                    status="error",
                    error=(
                        f"Delivery outcome is uncertain; sync {provider_name} before retrying"
                    ),
                )
            if disposition == "replacement_required":
                self._cleanup_new_delivery(delivery, delivery_created)
                return DeliveryResult(
                    status="error",
                    error=(
                        f"The existing Praxys-managed {provider_name} workout "
                        "must be removed before replacement"
                    ),
                )
            assert attempt is not None
            delivery_id = delivery.id
            attempt_id = attempt.id
            bump_revisions(self.db, self.user_id, ["plans"])
            self.db.commit()
        except (SQLAlchemyError, ValueError) as exc:
            self.db.rollback()
            logger.exception(
                "Failed to start %s delivery for user=%s date=%s",
                self.target,
                self.user_id,
                workout_date,
            )
            return DeliveryResult(
                status="error",
                error=f"Could not start delivery: {exc}",
            )

        try:
            provider_result = adapter.create_workout(prepared)
            if provider_result.provider_account_id != provider_account_id:
                raise ProviderOutcomeUnknownError(
                    f"{provider_name} account changed during delivery"
                )
        except (ProviderRequestError, ProviderRejectedError) as exc:
            try:
                self._record_terminal_attempt(
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    state="failed",
                    error=str(exc),
                )
            except SQLAlchemyError:
                self.db.rollback()
                logger.exception(
                    "Failed to persist %s delivery failure for user=%s date=%s",
                    self.target,
                    self.user_id,
                    workout_date,
                )
            return DeliveryResult(status="error", error=str(exc))
        except ProviderOutcomeUnknownError as exc:
            message = (
                f"{provider_name} delivery outcome is uncertain; "
                f"sync {provider_name} before retrying"
            )
            try:
                self._record_terminal_attempt(
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    state="conflict",
                    error=f"{message}: {exc}",
                )
            except SQLAlchemyError:
                self.db.rollback()
                logger.exception(
                    "Failed to persist ambiguous %s delivery for user=%s date=%s",
                    self.target,
                    self.user_id,
                    workout_date,
                )
            return DeliveryResult(status="error", error=message)

        try:
            self._record_terminal_attempt(
                delivery_id=delivery_id,
                attempt_id=attempt_id,
                state="synced",
                external_id=provider_result.external_id,
                response=provider_result.response,
                provider_account_id=provider_result.provider_account_id,
            )
        except SQLAlchemyError:
            self.db.rollback()
            logger.exception(
                "%s accepted workout but ledger commit failed for user=%s date=%s id=%s",
                self.target,
                self.user_id,
                workout_date,
                provider_result.external_id,
            )
            return DeliveryResult(
                status="error",
                error=(
                    f"{provider_name} accepted the workout, but delivery state could not "
                    "be finalized"
                ),
            )
        return DeliveryResult(
            status="success",
            external_id=provider_result.external_id,
            delivered_at=datetime.utcnow(),
        )

    def remove(self, external_id: str) -> RemovalResult:
        """Remove one caller-owned provider workout and finalize its ledger."""
        provider_name = self.target.capitalize()
        delivery = find_delivery_by_external_id(
            self.db,
            user_id=self.user_id,
            target=self.target,
            external_id=external_id,
        )
        if delivery is None:
            self.db.rollback()
            raise DeliveryNotFoundError(
                f"No {provider_name} delivery found for this user and workout"
            )
        if delivery.state == "removed":
            self.db.rollback()
            return RemovalResult(external_id=external_id)

        adapter = self._adapter()
        adapter.authenticate()
        provider_account_id = adapter.account_id
        if delivery.provider_account_id is None:
            days_until_workout = (delivery.workout_date - date.today()).days
            if days_until_workout < -2 or days_until_workout > 365:
                self.db.rollback()
                raise DeliveryAccountMismatchError(
                    f"This migrated {provider_name} delivery must be "
                    "reconciled before removal"
                )
            try:
                calendar = adapter.fetch_calendar(
                    days_ahead=max(14, days_until_workout + 3),
                    days_back=3,
                )
            except ProviderReadError as exc:
                self.db.rollback()
                raise DeliveryAccountVerificationError(
                    f"Could not verify the {provider_name} account before "
                    "removal"
                ) from exc
            verified = any(
                str(row.get("external_id") or "").strip() == external_id
                for row in calendar
            )
            if not verified:
                self.db.rollback()
                raise DeliveryAccountMismatchError(
                    f"This migrated {provider_name} delivery could not be "
                    "verified on the connected account"
                )
            delivery.provider_account_id = provider_account_id
        elif delivery.provider_account_id != provider_account_id:
            self.db.rollback()
            raise DeliveryAccountMismatchError(
                f"This {provider_name} delivery belongs to a different "
                f"{provider_name} account"
            )

        previous_state = delivery.state
        if previous_state == "delivering" and delivery.external_id:
            previous_state = "synced"
        try:
            delivery, attempt, disposition = begin_delivery_attempt(
                self.db,
                delivery,
                operation="remove",
            )
            if disposition == "already_complete":
                self.db.rollback()
                return RemovalResult(external_id=external_id)
            if disposition == "reconciliation_required":
                self.db.rollback()
                raise DeliveryBusyError(
                    f"{provider_name} workout delivery is already being updated"
                )
            assert attempt is not None
            delivery_id = delivery.id
            attempt_id = attempt.id
            bump_revisions(self.db, self.user_id, ["plans"])
            self.db.commit()
        except DeliveryBusyError:
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception(
                "Failed to start %s removal for user=%s workout=%s",
                self.target,
                self.user_id,
                external_id,
            )
            raise DeliveryStartError(
                f"Could not start {provider_name} workout removal"
            ) from exc

        def record_failure(message: str) -> bool:
            try:
                updated = self._record_terminal_attempt(
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    state="failed",
                    delivery_state=previous_state,
                    error=message,
                )
                current = find_delivery_by_external_id(
                    self.db,
                    user_id=self.user_id,
                    target=self.target,
                    external_id=external_id,
                )
                return (
                    not updated
                    and current is not None
                    and current.state == "removed"
                )
            except SQLAlchemyError:
                self.db.rollback()
                logger.exception(
                    "Failed to persist %s removal failure for user=%s workout=%s",
                    self.target,
                    self.user_id,
                    external_id,
                )
                return False

        try:
            provider_result = adapter.delete_workout(external_id)
        except (
            DeliveryCredentialsUnavailable,
            DeliveryCredentialsInvalid,
            ProviderAuthenticationError,
        ) as exc:
            if record_failure(str(exc)):
                return RemovalResult(external_id=external_id)
            raise
        except ProviderRemovalError as exc:
            if record_failure(str(exc)):
                return RemovalResult(external_id=external_id)
            raise DeliveryRemovalFailedError(str(exc)) from exc

        try:
            self._record_terminal_attempt(
                delivery_id=delivery_id,
                attempt_id=attempt_id,
                state="removed",
                external_id=external_id,
                response={"already_absent": provider_result.already_absent},
                commit=False,
            )
            self.db.query(TrainingPlan).filter(
                TrainingPlan.user_id == self.user_id,
                TrainingPlan.source == self.target,
                TrainingPlan.external_id == external_id,
            ).delete(synchronize_session=False)
            mark_target_workout_absent(
                self.db,
                user_id=self.user_id,
                target=self.target,
                provider_account_id=provider_account_id,
                external_id=external_id,
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception(
                "%s workout deleted but ledger finalization failed for user=%s workout=%s",
                self.target,
                self.user_id,
                external_id,
            )
            raise DeliveryFinalizationError(
                f"{provider_name} workout was deleted, but delivery state "
                "could not be finalized"
            ) from exc
        return RemovalResult(
            external_id=external_id,
            already_absent=provider_result.already_absent,
        )
