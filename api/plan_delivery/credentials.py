"""Credential resolution for provider workout delivery."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from db.connection_credentials import (
    CredentialAccessError,
    load_connection_credentials,
)

class DeliveryCredentialsUnavailable(CredentialAccessError):
    """No credentials are available for the requested delivery target."""


class DeliveryCredentialsInvalid(CredentialAccessError):
    """Stored credentials require the user to reconnect the platform."""


def resolve_delivery_credentials(
    db: Session,
    *,
    user_id: str,
    target: str,
) -> dict[str, Any]:
    """Resolve credentials without ever borrowing another user's connection."""
    try:
        credentials = load_connection_credentials(
            db,
            user_id=user_id,
            platform=target,
        )
    except CredentialAccessError as exc:
        raise DeliveryCredentialsInvalid(str(exc)) from exc
    if credentials is not None:
        return credentials

    raise DeliveryCredentialsUnavailable(
        f"No credentials available for {target}"
    )
