"""Fail-closed runtime controls for optional external processing."""
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
    """Raise when an optional-processing setting is malformed."""
    for name, default in (
        ("PRAXYS_ENABLE_BACKGROUND_AI", False),
        ("PRAXYS_DISABLE_BACKGROUND_AI", True),
        ("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", False),
        ("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", True),
    ):
        _strict_flag(name, default=default)


def background_ai_enabled() -> bool:
    """Return whether nonessential background AI is explicitly enabled."""
    try:
        enabled = _strict_flag(
            "PRAXYS_ENABLE_BACKGROUND_AI",
            default=False,
        )
        disabled = _strict_flag(
            "PRAXYS_DISABLE_BACKGROUND_AI",
            default=True,
        )
    except ValueError:
        return False
    return enabled and not disabled


def background_ai_disabled() -> bool:
    """Return whether nonessential background AI processing is disabled."""
    return not background_ai_enabled()


def background_ai_authorized(
    db: Session,
    *,
    user_id: str | None,
    purpose_authorized: bool,
) -> bool:
    """Require operational enablement plus current purpose-level authority."""
    if (
        not purpose_authorized
        or not user_id
        or not background_ai_enabled()
    ):
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
    background_positive = _strict_flag(
        "PRAXYS_ENABLE_BACKGROUND_AI", default=False
    )
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
        "background_ai_enabled": background_positive and not background_kill,
        "background_ai_positive_enable": background_positive,
        "background_ai_kill_switch": background_kill,
        "feedback_publication_enabled": (
            publication_positive and not publication_kill
        ),
        "feedback_publication_positive_enable": publication_positive,
        "feedback_publication_kill_switch": publication_kill,
    }
