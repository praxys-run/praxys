"""Fail-closed runtime controls for Azure AI and external publication."""
from __future__ import annotations

import os

from sqlalchemy.orm import Session


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
FEEDBACK_PUBLICATION_CONSENT_VERSION = "feedback-publication-v1"


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
    for name, default in (
        ("PRAXYS_DISABLE_BACKGROUND_AI", True),
        ("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", False),
        ("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", True),
    ):
        _strict_flag(name, default=default)


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
    from api.legal_receipts import user_has_current_legal_bundle

    return user_has_current_legal_bundle(db, user_id)


def feedback_publication_enabled() -> bool:
    """Return whether external feedback publication is explicitly enabled."""
    try:
        enabled = _strict_flag(
            "PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
            default=False,
        )
        disabled = _strict_flag(
            "PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
            default=True,
        )
    except ValueError:
        return False
    return enabled and not disabled


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
    from api.legal_receipts import user_has_current_legal_bundle

    return user_has_current_legal_bundle(db, user_id)


def feedback_has_publication_consent(feedback: object) -> bool:
    """Validate the exact persisted submitter grant for one submission."""
    return (
        getattr(feedback, "publication_consent_version", None)
        == FEEDBACK_PUBLICATION_CONSENT_VERSION
        and getattr(feedback, "publication_consented_at", None) is not None
    )


def optional_processing_status() -> dict[str, bool]:
    """Return effective non-secret runtime control values."""
    validate_optional_processing_config()
    background_kill = _strict_flag(
        "PRAXYS_DISABLE_BACKGROUND_AI", default=True
    )
    publication_positive = _strict_flag(
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION", default=False
    )
    publication_kill = _strict_flag(
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION", default=True
    )
    return {
        "background_ai_enabled": not background_kill,
        "background_ai_kill_switch": background_kill,
        "feedback_publication_enabled": (
            publication_positive and not publication_kill
        ),
        "feedback_publication_positive_enable": publication_positive,
        "feedback_publication_kill_switch": publication_kill,
    }
