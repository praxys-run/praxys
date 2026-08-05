"""Fresh connection guards for provider workout mutations."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.plan_delivery.capabilities import (
    garmin_plan_delivery_operator_enabled,
    plan_delivery_capability_enabled,
)
from api.plan_delivery.service import DeliveryMutationBlockedError
from db.connection_credentials import connection_credentials_generation
from db.models import UserConfig, UserConnection
from db.plan_ledger import lock_plan_writes


def capture_delivery_connection_generation(
    db: Session,
    *,
    user_id: str,
    target: str,
    allow_missing: bool = False,
    refresh: bool = False,
) -> str | None:
    """Return the live connection generation used to fence provider writes."""
    query = select(UserConnection).where(
        UserConnection.user_id == user_id,
        UserConnection.platform == target,
    )
    if refresh:
        query = query.with_for_update().execution_options(
            populate_existing=True
        )
    connection = db.execute(query).scalar_one_or_none()
    if connection is None:
        if allow_missing:
            return None
        raise DeliveryMutationBlockedError("connection_missing")
    if connection.status != "connected":
        raise DeliveryMutationBlockedError(
            f"connection_{connection.status}"
        )
    config_query = select(UserConfig).where(
        UserConfig.user_id == user_id,
    )
    if refresh:
        config_query = config_query.with_for_update().execution_options(
            populate_existing=True
        )
    config = db.execute(config_query).scalar_one_or_none()
    if not plan_delivery_capability_enabled(
        target,
        user_id=user_id,
        source_options=(
            config.source_options
            if config is not None
            and isinstance(config.source_options, dict)
            else {}
        ),
        connection=connection,
    ):
        raise DeliveryMutationBlockedError(
            (
                "experimental_delivery_disabled"
                if not garmin_plan_delivery_operator_enabled(user_id)
                else "experimental_consent_required"
            )
            if target == "garmin"
            else "execution_target_unsupported",
        )
    return connection_credentials_generation(connection)


def guard_delivery_connection(
    db: Session,
    *,
    user_id: str,
    target: str,
    expected_generation: str,
) -> None:
    """Block a provider write if its live connection changed or degraded."""
    lock_plan_writes(db, user_id)
    current_generation = capture_delivery_connection_generation(
        db,
        user_id=user_id,
        target=target,
        refresh=True,
    )
    if current_generation != expected_generation:
        raise DeliveryMutationBlockedError("connection_changed")
