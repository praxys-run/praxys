"""Fail-closed runtime controls for Azure AI and external publication."""
from __future__ import annotations

import os

from sqlalchemy.orm import Session


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
FEEDBACK_PUBLICATION_CONSENT_VERSION = (
    "feedback-publication-v2-public-github"
)


def _strict_flag(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean")


def validate_optional_processing_config() -> None:
    """Raise when an AI or external-publication setting is malformed."""
    # The feedback switches deliberately treat absent or malformed values as
    # stopped at request time. A typo must disable publication, not take down
    # the rest of the API. Background AI retains its existing boot validation.
    _strict_flag("PRAXYS_DISABLE_BACKGROUND_AI", default=True)


def _safe_flag(name: str, *, default: bool) -> tuple[bool, bool]:
    """Return ``(value, valid)`` while failing closed on malformed input."""
    try:
        return _strict_flag(name, default=default), True
    except ValueError:
        return default, False


def background_ai_enabled() -> bool:
    """Return whether ordinary Azure AI processing is operationally available.

    The negative switch is the single runtime authority and defaults to the
    safe stopped state when absent or malformed. Current Terms authorization
    is checked separately for every user-bound call.
    """
    try:
        return not _strict_flag(
            "PRAXYS_DISABLE_BACKGROUND_AI",
            default=True,
        )
    except ValueError:
        return False


def background_ai_disabled() -> bool:
    """Return whether the centralized Azure AI emergency stop is active."""
    return not background_ai_enabled()


def background_ai_authorized(
    db: Session,
    *,
    user_id: str | None,
) -> bool:
    """Require the runtime switch and the user's current Terms receipt."""
    if not user_id or not background_ai_enabled():
        return False
    from api.legal_receipts import user_background_processing_authorized

    return user_background_processing_authorized(db, user_id)


def feedback_publication_enabled() -> bool:
    """Return whether external feedback publication is explicitly enabled."""
    enabled, enabled_valid = _safe_flag(
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
        default=False,
    )
    disabled, disabled_valid = _safe_flag(
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
        default=True,
    )
    return enabled_valid and disabled_valid and enabled and not disabled


def feedback_publication_disabled() -> bool:
    """Return whether feedback publication to external trackers is disabled."""
    return not feedback_publication_enabled()


def feedback_publication_authorized(
    db: Session,
    *,
    user_id: str | None,
    submission_authorized: bool,
) -> bool:
    """Require the global gate and current submission/account authority."""
    if (
        not submission_authorized
        or not user_id
        or not feedback_publication_enabled()
    ):
        return False
    from db.models import User

    account = (
        db.query(User.is_active, User.is_demo)
        .populate_existing()
        .filter(User.id == user_id)
        .first()
    )
    if account is None or not account.is_active or account.is_demo:
        return False
    from api.legal_receipts import user_background_processing_authorized

    return user_background_processing_authorized(db, user_id)


def feedback_has_publication_consent(feedback: object) -> bool:
    """Validate the exact persisted submitter grant for one submission."""
    return (
        getattr(feedback, "publication_consent_version", None)
        == FEEDBACK_PUBLICATION_CONSENT_VERSION
        and getattr(feedback, "publication_consented_at", None) is not None
    )


def optional_processing_status() -> dict[str, bool]:
    """Return effective non-secret runtime control values."""
    background_kill, background_valid = _safe_flag(
        "PRAXYS_DISABLE_BACKGROUND_AI", default=True
    )
    publication_positive, positive_valid = _safe_flag(
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION", default=False
    )
    publication_kill, kill_valid = _safe_flag(
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION", default=True
    )
    return {
        "background_ai_enabled": background_valid and not background_kill,
        "background_ai_kill_switch": background_kill,
        "feedback_publication_enabled": (
            positive_valid
            and kill_valid
            and publication_positive
            and not publication_kill
        ),
        "feedback_publication_positive_enable": publication_positive,
        "feedback_publication_kill_switch": publication_kill,
    }


def feedback_publication_switch_status() -> dict[str, bool]:
    """Return fail-closed, non-secret publication switch metadata."""
    positive, positive_valid = _safe_flag(
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION", default=False
    )
    kill, kill_valid = _safe_flag(
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION", default=True
    )
    return {
        "positive_enable": positive,
        "kill_switch": kill,
        "config_valid": positive_valid and kill_valid,
        "effective": (
            positive_valid and kill_valid and positive and not kill
        ),
    }
