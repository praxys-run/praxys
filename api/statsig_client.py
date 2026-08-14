"""Fail-closed Statsig server SDK wrapper.

The application remains fully functional without ``STATSIG_SDK_KEY``. In that
state gates evaluate to ``False`` and dynamic configs return their caller-owned
fallbacks, so feature rollout never becomes an availability dependency.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, TypeVar

from statsig import StatsigOptions, StatsigUser, statsig

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)
_initialized = False
T = TypeVar("T")


async def init_statsig() -> None:
    """Initialize Statsig when a server SDK key is configured."""
    global _initialized

    sdk_key = os.environ.get("STATSIG_SDK_KEY", "").strip()
    if not sdk_key:
        _initialized = False
        return
    try:
        options = StatsigOptions(
            tier=os.environ.get("STATSIG_ENV", "development").strip()
            or "development",
        )
        await asyncio.to_thread(statsig.initialize, sdk_key, options)
        _initialized = bool(statsig.is_initialized())
        if not _initialized:
            logger.error("Statsig initialization completed without a ready client")
    except Exception:
        _initialized = False
        logger.exception("Statsig initialization failed; feature gates remain off")


async def shutdown_statsig() -> None:
    """Flush pending events and stop Statsig background workers."""
    global _initialized

    if not _initialized:
        return
    try:
        await asyncio.to_thread(statsig.flush)
    except Exception:
        logger.exception("Statsig event flush failed during shutdown")
    try:
        await asyncio.to_thread(statsig.shutdown)
    except Exception:
        logger.exception("Statsig shutdown failed")
    finally:
        _initialized = False


def is_statsig_initialized() -> bool:
    """Return whether the server SDK is ready for gate evaluation."""
    return _initialized


def get_statsig_user(
    user_id: str,
    email: str | None,
    is_admin: bool,
    is_demo: bool,
    training_base: str | None,
    language: str | None,
) -> StatsigUser:
    """Build the per-user targeting identity shared by all backend gates."""
    targeting_email = (
        None
        if email and email.casefold().startswith("wechat:")
        else email
    )
    return StatsigUser(
        user_id=str(user_id),
        email=targeting_email,
        locale=language,
        custom={
            "is_admin": bool(is_admin),
            "is_demo": bool(is_demo),
            "training_base": training_base,
            "language": language,
        },
    )


def get_statsig_user_for_account(
    db: Session,
    *,
    user_id: str,
    training_base: str | None,
    language: str | None,
) -> StatsigUser | None:
    """Build a targeting identity from the authenticated account."""
    from db.models import User

    user = db.get(User, user_id)
    if user is None:
        return None
    return get_statsig_user(
        user_id=user_id,
        email=user.email,
        is_admin=user.is_superuser,
        is_demo=user.is_demo,
        training_base=training_base,
        language=language,
    )


def check_gate(gate_name: str, user: StatsigUser | None) -> bool:
    """Evaluate ``gate_name``, returning ``False`` on absence or any error."""
    if not _initialized or user is None:
        return False
    try:
        return bool(statsig.check_gate(user, gate_name))
    except Exception:
        logger.exception("Statsig gate evaluation failed: gate=%s", gate_name)
        return False


def get_config(
    config_name: str,
    user: StatsigUser | None,
    default: T,
) -> T:
    """Return a dynamic config's ``value`` property or ``default``."""
    if not _initialized or user is None:
        return default
    try:
        config = statsig.get_config(user, config_name)
        return config.get("value", default)
    except Exception:
        logger.exception(
            "Statsig dynamic config evaluation failed: config=%s",
            config_name,
        )
        return default
