"""Fail-closed optional-processing runtime controls."""
from __future__ import annotations

import pytest

from api.optional_processing import (
    background_ai_authorized,
    background_ai_disabled,
    background_ai_enabled,
    feedback_publication_authorized,
    feedback_publication_disabled,
    feedback_publication_enabled,
    validate_optional_processing_config,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from db.models import Base, User


_FLAGS = (
    "PRAXYS_DISABLE_BACKGROUND_AI",
    "PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
    "PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
)


def _clear(monkeypatch) -> None:
    for name in _FLAGS:
        monkeypatch.delenv(name, raising=False)


def test_ai_kill_switch_defaults_fail_closed(monkeypatch) -> None:
    _clear(monkeypatch)

    assert background_ai_enabled() is False
    assert background_ai_disabled() is True
    assert feedback_publication_enabled() is False
    assert feedback_publication_disabled() is True


def test_ai_requires_kill_release_while_publication_keeps_two_switches(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")

    assert background_ai_enabled() is True
    assert feedback_publication_enabled() is True


def test_negative_kill_switch_overrides_positive_enable(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "true")

    assert background_ai_enabled() is False
    assert feedback_publication_enabled() is False


def test_malformed_optional_processing_config_fails_closed(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "sometimes")

    assert background_ai_enabled() is False
    with pytest.raises(ValueError):
        validate_optional_processing_config()


def test_ai_authorization_uses_current_terms_and_runtime(
    monkeypatch,
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.setenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", "false")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(User(
            id="current",
            email="current@example.test",
            hashed_password="x",
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
        ))
        db.add(User(
            id="stale",
            email="stale@example.test",
            hashed_password="x",
            terms_version="old",
            terms_digest=TERMS_CONTENT_DIGEST,
        ))
        db.commit()

        assert background_ai_authorized(db, user_id="current")
        assert not background_ai_authorized(db, user_id="stale")
        assert not background_ai_authorized(db, user_id=None)
        assert feedback_publication_authorized(
            db, user_id="current", submission_authorized=True
        )
        assert not feedback_publication_authorized(
            db, user_id="current", submission_authorized=False
        )
        assert not feedback_publication_authorized(
            db, user_id="stale", submission_authorized=True
        )
    finally:
        db.close()
        engine.dispose()


def test_azure_client_construction_honors_emergency_stop(monkeypatch) -> None:
    import api.llm as llm

    cached_client = object()
    monkeypatch.setattr(llm, "_get_cached_client", lambda: cached_client)
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "false")
    assert llm.get_client() is cached_client

    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")
    assert llm.get_client() is None
