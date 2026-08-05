"""Encrypted persistence for Garmin OAuth token bundles."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from azure.core.exceptions import AzureError
from cryptography.fernet import InvalidToken
from garminconnect import GarminConnectConnectionError
from garminconnect.client import Client
from sqlalchemy.orm import Session

from db.connection_credentials import (
    ConnectionGenerationChanged,
    CredentialAccessError,
    connection_credentials_generation,
)
from db.crypto import get_vault
from db.models import UserConnection


class GarminTokenAccessError(CredentialAccessError):
    """Stored Garmin OAuth tokens exist but cannot be decoded safely."""


def validate_garmin_tokens(serialized_tokens: str) -> str:
    """Validate garminconnect's JSON ``Client.dumps()`` representation."""
    if not isinstance(serialized_tokens, str):
        raise GarminTokenAccessError("Stored Garmin OAuth tokens are malformed")
    try:
        payload = json.loads(serialized_tokens)
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise GarminTokenAccessError(
            "Stored Garmin OAuth tokens are malformed"
        ) from exc
    if (
        not isinstance(payload, dict)
        or not all(
            isinstance(payload.get(field), str) and payload[field]
            for field in ("di_token", "di_refresh_token", "di_client_id")
        )
    ):
        raise GarminTokenAccessError("Stored Garmin OAuth tokens are malformed")
    try:
        Client().loads(serialized_tokens)
    except (GarminConnectConnectionError, KeyError, TypeError, ValueError) as exc:
        raise GarminTokenAccessError(
            "Stored Garmin OAuth tokens are malformed"
        ) from exc
    return serialized_tokens


def _connection_for_generation(
    db: Session,
    *,
    user_id: str,
    expected_generation: str | None,
    allowed_statuses: tuple[str, ...] | None,
    lock: bool,
) -> UserConnection | None:
    query = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == "garmin",
    )
    if lock:
        query = query.with_for_update()
    connection = query.execution_options(populate_existing=True).one_or_none()
    if connection is None:
        if expected_generation is not None:
            raise ConnectionGenerationChanged("garmin connection changed")
        return None
    if (
        expected_generation is not None
        and connection_credentials_generation(connection) != expected_generation
    ):
        raise ConnectionGenerationChanged("garmin connection changed")
    if allowed_statuses is not None and connection.status not in allowed_statuses:
        raise ConnectionGenerationChanged("garmin connection changed")
    return connection


def load_garmin_tokens(
    db: Session,
    *,
    user_id: str,
    expected_generation: str | None = None,
    allowed_statuses: tuple[str, ...] | None = None,
) -> str | None:
    """Decrypt the current connection's garminconnect token bundle."""
    connection = _connection_for_generation(
        db,
        user_id=user_id,
        expected_generation=expected_generation,
        allowed_statuses=allowed_statuses,
        lock=False,
    )
    if connection is None:
        return None
    encrypted = connection.encrypted_garmin_tokens
    wrapped_dek = connection.wrapped_token_dek
    stored_generation = connection.garmin_token_generation
    updated_at = connection.tokens_updated_at
    if all(
        value is None
        for value in (encrypted, wrapped_dek, stored_generation, updated_at)
    ):
        return None
    if not encrypted or not wrapped_dek or not stored_generation or updated_at is None:
        raise GarminTokenAccessError(
            "Stored Garmin OAuth token encryption metadata is incomplete"
        )
    current_generation = connection_credentials_generation(connection)
    if stored_generation != current_generation:
        raise GarminTokenAccessError(
            "Stored Garmin OAuth tokens do not match current credentials"
        )
    try:
        serialized = get_vault().decrypt(encrypted, wrapped_dek)
    except (
        AzureError,
        InvalidToken,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise GarminTokenAccessError(
            "Stored Garmin OAuth tokens could not be decrypted"
        ) from exc
    return validate_garmin_tokens(serialized)


def stage_garmin_tokens(
    db: Session,
    *,
    user_id: str,
    serialized_tokens: str,
    expected_generation: str,
    allowed_statuses: tuple[str, ...] | None = None,
) -> UserConnection:
    """Encrypt and stage tokens after rechecking the credential generation."""
    validate_garmin_tokens(serialized_tokens)
    connection = _connection_for_generation(
        db,
        user_id=user_id,
        expected_generation=expected_generation,
        allowed_statuses=allowed_statuses,
        lock=True,
    )
    assert connection is not None
    encrypted, wrapped_dek = get_vault().encrypt(serialized_tokens)
    connection.encrypted_garmin_tokens = encrypted
    connection.wrapped_token_dek = wrapped_dek
    connection.garmin_token_generation = expected_generation
    connection.tokens_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return connection


def clear_stored_garmin_tokens(db: Session, *, user_id: str) -> bool:
    """Clear encrypted Garmin OAuth tokens from an existing connection row."""
    connection = db.query(UserConnection).filter(
        UserConnection.user_id == user_id,
        UserConnection.platform == "garmin",
    ).one_or_none()
    if connection is None:
        return False
    changed = any(
        value is not None
        for value in (
            connection.encrypted_garmin_tokens,
            connection.wrapped_token_dek,
            connection.garmin_token_generation,
            connection.tokens_updated_at,
        )
    )
    connection.encrypted_garmin_tokens = None
    connection.wrapped_token_dek = None
    connection.garmin_token_generation = None
    connection.tokens_updated_at = None
    return changed
