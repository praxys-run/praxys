"""Shared, fail-closed authority for China-channel worker jobs.

HTTP requests use App Service environment switches. The isolated Labs worker
cannot see them, so each API process publishes one atomic snapshot at startup.
Readiness only compares the snapshot; it never lets an old process rewrite it.
Worker result commits take a shared transaction advisory lock, serializing
with a later exclusive reconciliation without broadening table grants.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from db.models import AppConfig, TermsAcceptanceReceipt
from db.session import begin_serialized_write

CN_WEB_CHANNEL = "cn-web"
MINIAPP_CHANNEL = "wechat-miniapp"
CHANNEL_AUTHORITY_KEY = "processing_authority.channels"
CHANNEL_AUTHORITY_SCHEMA_VERSION = 1
CHANNELS = frozenset({CN_WEB_CHANNEL, MINIAPP_CHANNEL})
_POSTGRES_ADVISORY_LOCK = 1_347_570_776
logger = logging.getLogger(__name__)


def expected_channel_processing_status() -> dict[str, bool]:
    """Return this API process's effective environment authority."""
    from api.china_client_boundary import (
        china_processing_enabled,
        miniapp_processing_enabled,
    )

    return {
        CN_WEB_CHANNEL: china_processing_enabled(),
        MINIAPP_CHANNEL: miniapp_processing_enabled(),
    }


def _encode(status: dict[str, bool]) -> str:
    return json.dumps(
        {
            "schema_version": CHANNEL_AUTHORITY_SCHEMA_VERSION,
            CN_WEB_CHANNEL: status[CN_WEB_CHANNEL],
            MINIAPP_CHANNEL: status[MINIAPP_CHANNEL],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode(value: object) -> dict[str, bool] | None:
    if not isinstance(value, str):
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    expected = {"schema_version", CN_WEB_CHANNEL, MINIAPP_CHANNEL}
    if (
        not isinstance(payload, dict)
        or set(payload) != expected
        or payload.get("schema_version")
        != CHANNEL_AUTHORITY_SCHEMA_VERSION
        or type(payload.get(CN_WEB_CHANNEL)) is not bool
        or type(payload.get(MINIAPP_CHANNEL)) is not bool
    ):
        return None
    return {
        CN_WEB_CHANNEL: payload[CN_WEB_CHANNEL],
        MINIAPP_CHANNEL: payload[MINIAPP_CHANNEL],
    }


def shared_channel_processing_snapshot(
    db: Session,
    *,
    lock_for_commit: bool = False,
) -> dict[str, bool] | None:
    """Return shared state, or ``None`` when missing/malformed."""
    query = db.query(AppConfig.key, AppConfig.value).filter(
        AppConfig.key == CHANNEL_AUTHORITY_KEY
    )
    if lock_for_commit:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock_shared(:lock_key)"),
                {"lock_key": _POSTGRES_ADVISORY_LOCK},
            )
        elif dialect == "sqlite":
            # The result path already owns SQLite's serialized write
            # transaction. Starting a nested BEGIN IMMEDIATE would fail.
            if not db.in_transaction():
                begin_serialized_write(db)
        else:
            raise RuntimeError(
                "Unsupported processing-authority database dialect: "
                f"{dialect}"
            )
    row = query.one_or_none()
    decoded = _decode(None if row is None else row[1])
    if row is not None and decoded is None:
        logger.error(
            "Invalid shared channel processing authority; failing closed"
        )
    return decoded


def shared_channel_processing_status(
    db: Session,
    *,
    lock_for_commit: bool = False,
) -> dict[str, bool]:
    return shared_channel_processing_snapshot(
        db, lock_for_commit=lock_for_commit,
    ) or {CN_WEB_CHANNEL: False, MINIAPP_CHANNEL: False}


def channels_processing_authorized(
    db: Session,
    channels: Iterable[str],
    *,
    lock_for_commit: bool = False,
) -> bool:
    required = {str(channel) for channel in channels}
    if not required:
        return True
    if not required.issubset(CHANNELS):
        return False
    status = shared_channel_processing_status(
        db, lock_for_commit=lock_for_commit,
    )
    return all(status[channel] for channel in required)


def user_channels_processing_authorized(
    db: Session,
    user_id: str,
    *,
    lock_for_commit: bool = False,
) -> bool:
    """Apply shared authority only to the user's current CN channels."""
    channels = {
        str(channel)
        for channel, in db.query(TermsAcceptanceReceipt.channel)
        .filter(
            TermsAcceptanceReceipt.user_id == user_id,
            TermsAcceptanceReceipt.terms_version == TERMS_VERSION,
            TermsAcceptanceReceipt.terms_digest == TERMS_CONTENT_DIGEST,
            TermsAcceptanceReceipt.channel.in_(tuple(CHANNELS)),
        )
        .distinct()
        .all()
    }
    return channels_processing_authorized(
        db, channels, lock_for_commit=lock_for_commit,
    )


def _lock_reconciliation(db: Session) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        begin_serialized_write(db)
    elif dialect == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _POSTGRES_ADVISORY_LOCK},
        )
    else:
        raise RuntimeError(
            f"Unsupported processing-authority database dialect: {dialect}"
        )


def reconcile_channel_processing_authority(
    db: Session,
) -> dict[str, bool]:
    """Publish this process's environment state exactly once at startup."""
    desired = expected_channel_processing_status()
    _lock_reconciliation(db)
    row = (
        db.query(AppConfig)
        .filter(AppConfig.key == CHANNEL_AUTHORITY_KEY)
        .with_for_update()
        .one_or_none()
    )
    value = _encode(desired)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row is None:
        db.add(AppConfig(
            key=CHANNEL_AUTHORITY_KEY, value=value,
            updated_at=now, updated_by=None,
        ))
    else:
        row.value = value
        row.updated_at = now
        row.updated_by = None
    db.commit()
    return desired
