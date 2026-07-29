"""Credential resolution for provider workout delivery."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy.orm import Session

from db.connection_credentials import (
    CredentialAccessError,
    load_connection_credentials,
)

logger = logging.getLogger(__name__)


class DeliveryCredentialsUnavailable(RuntimeError):
    """No credentials are available for the requested delivery target."""


class DeliveryCredentialsInvalid(RuntimeError):
    """Stored credentials require the user to reconnect the platform."""


def _legacy_stryd_credentials(user_id: str) -> dict[str, str] | None:
    """Return explicitly pinned local-development Stryd credentials."""
    environment = (
        os.environ.get("PRAXYS_ENV")
        or os.environ.get("TRAINSIGHT_ENV")
        or ""
    ).strip().casefold()
    if environment != "development":
        return None

    values: dict[str, Any] = {}
    legacy_path = Path(__file__).resolve().parents[2] / "sync" / ".env"
    if legacy_path.exists():
        values.update(dotenv_values(legacy_path))

    def configured(name: str) -> str:
        value = os.environ.get(name)
        if value is None:
            value = values.get(name)
        return str(value or "").strip()

    pinned_user_id = configured("PRAXYS_STRYD_ENV_USER_ID")
    if pinned_user_id != user_id:
        return None

    email = configured("STRYD_EMAIL")
    password = configured("STRYD_PASSWORD")
    if not email or not password:
        return None
    logger.warning(
        "Using local-only environment Stryd credentials for pinned user=%s",
        user_id,
    )
    return {"email": email, "password": password}


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

    if target == "stryd":
        legacy = _legacy_stryd_credentials(user_id)
        if legacy is not None:
            return legacy

    raise DeliveryCredentialsUnavailable(
        f"No credentials available for {target}"
    )
