"""Shared access to encrypted per-user platform credentials."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from azure.core.exceptions import AzureError
from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Session

from db.crypto import get_vault
from db.models import UserConnection


class CredentialAccessError(RuntimeError):
    """Stored platform credentials exist but cannot be decoded safely."""


class ConnectionGenerationChanged(RuntimeError):
    """A sync's captured connection is no longer current or runnable."""


def connection_credentials_generation(connection: UserConnection) -> str:
    """Fingerprint one connection's encrypted credential generation."""
    digest = hashlib.sha256()
    digest.update(bytes(connection.encrypted_credentials or b""))
    digest.update(b"\0")
    digest.update(bytes(connection.wrapped_dek or b""))
    return f"{connection.id}:{digest.hexdigest()}"


def require_connection_generation(
    db: Session,
    *,
    user_id: str,
    platform: str,
    expected_generation: str,
    allowed_statuses: tuple[str, ...],
    lock: bool = False,
) -> UserConnection:
    """Return the current connection or reject a stale sync generation."""
    query = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == platform,
    )
    if lock:
        query = query.with_for_update()
    connection = query.execution_options(
        populate_existing=True
    ).one_or_none()
    if (
        connection is None
        or connection.status not in allowed_statuses
        or connection_credentials_generation(connection)
        != expected_generation
    ):
        raise ConnectionGenerationChanged(
            f"{platform} connection changed during sync"
        )
    return connection


def load_connection_credentials(
    db: Session,
    *,
    user_id: str,
    platform: str,
) -> dict[str, Any] | None:
    """Return decrypted credentials for one user's platform connection."""
    connection = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == platform,
    ).first()
    if (
        connection is None
        or not connection.encrypted_credentials
        or not connection.wrapped_dek
    ):
        return None

    try:
        raw = get_vault().decrypt(
            connection.encrypted_credentials,
            connection.wrapped_dek,
        )
    except (
        AzureError,
        InvalidToken,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise CredentialAccessError(
            f"Stored {platform} credentials could not be decrypted"
        ) from exc

    try:
        credentials = json.loads(raw)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise CredentialAccessError(
            f"Stored {platform} credentials are malformed"
        ) from exc
    if not isinstance(credentials, dict):
        raise CredentialAccessError(
            f"Stored {platform} credentials must be an object"
        )
    return credentials
