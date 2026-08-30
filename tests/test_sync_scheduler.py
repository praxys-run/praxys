"""Tests for sync scheduler frequency guardrails."""

import tempfile

import pytest

from db.sync_scheduler import (
    ALLOWED_SYNC_INTERVAL_HOURS,
    DEFAULT_SYNC_INTERVAL_HOURS,
    _run_managed_delivery_tick,
    _run_personal_context_retention_tick,
    get_user_sync_interval_hours,
    normalize_sync_interval_hours,
)


@pytest.mark.parametrize("hours", ALLOWED_SYNC_INTERVAL_HOURS)
def test_normalize_sync_interval_hours_allows_guardrails(hours: int) -> None:
    """Allowed sync interval options should be accepted."""
    assert normalize_sync_interval_hours(hours) == hours


@pytest.mark.parametrize("hours", [1, 3, 4, 8, 48, "fast", None])
def test_normalize_sync_interval_hours_rejects_invalid_values(hours: object) -> None:
    """Invalid sync intervals should be rejected."""
    with pytest.raises(ValueError):
        normalize_sync_interval_hours(hours)


@pytest.mark.parametrize(
    "source_options,expected",
    [
        ({}, DEFAULT_SYNC_INTERVAL_HOURS),
        ({"sync_interval_hours": 12}, 12),
        ({"sync_interval_hours": "24"}, 24),
        ({"sync_interval_hours": 2}, DEFAULT_SYNC_INTERVAL_HOURS),
        ({"sync_interval_hours": "bad"}, DEFAULT_SYNC_INTERVAL_HOURS),
        (None, DEFAULT_SYNC_INTERVAL_HOURS),
    ],
)
def test_get_user_sync_interval_hours_fallbacks(source_options: dict | None, expected: int) -> None:
    """Scheduler should safely fall back to default on missing/invalid config."""
    assert get_user_sync_interval_hours(source_options) == expected


def test_scheduler_tick_runs_managed_delivery(monkeypatch) -> None:
    """Each scheduler cycle should run the isolated managed-plan retry pass."""
    calls: list[str] = []
    monkeypatch.setattr(
        "api.plan_delivery.rolling.run_scheduled_managed_deliveries",
        lambda: calls.append("managed"),
    )

    _run_managed_delivery_tick()

    assert calls == ["managed"]


def test_scheduler_tick_isolates_managed_delivery_failure(
    monkeypatch,
) -> None:
    """Managed delivery failures must not escape into the sync scheduler."""
    def fail() -> None:
        raise RuntimeError("managed delivery failed")

    monkeypatch.setattr(
        "api.plan_delivery.rolling.run_scheduled_managed_deliveries",
        fail,
    )

    _run_managed_delivery_tick()


def test_scheduler_tick_runs_personal_context_retention(monkeypatch) -> None:
    """Each scheduler cycle should run private-context retention."""
    calls: list[str] = []
    monkeypatch.setattr(
        "api.personal_context.run_scheduled_retention",
        lambda: calls.append("retention"),
    )

    _run_personal_context_retention_tick()

    assert calls == ["retention"]


def test_scheduler_tick_isolates_context_retention_failure(
    monkeypatch,
) -> None:
    """Retention failures must not escape into the sync scheduler."""
    monkeypatch.setattr(
        "api.personal_context.run_scheduled_retention",
        lambda: (_ for _ in ()).throw(RuntimeError("retention failed")),
    )

    _run_personal_context_retention_tick()


def test_scheduled_managed_delivery_excludes_stale_terms(monkeypatch) -> None:
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from api.plan_delivery import rolling
    from db import session as db_session
    from db.models import User, UserConfig

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()
    with db_session.SessionLocal() as db:
        db.add_all([
            User(
                id="delivery-current",
                email="delivery-current@example.test",
                hashed_password="x",
                terms_version=TERMS_VERSION,
                terms_digest=TERMS_CONTENT_DIGEST,
            ),
            User(
                id="delivery-stale",
                email="delivery-stale@example.test",
                hashed_password="x",
                terms_version="old",
                terms_digest=TERMS_CONTENT_DIGEST,
            ),
            UserConfig(
                user_id="delivery-current",
                plan_management={
                    "mode": "praxys",
                    "delivery_enabled": True,
                },
            ),
            UserConfig(
                user_id="delivery-stale",
                plan_management={
                    "mode": "praxys",
                    "delivery_enabled": True,
                },
            ),
        ])
        db.commit()

    calls: list[str] = []
    monkeypatch.setattr(
        rolling,
        "trigger_managed_plan_delivery",
        lambda user_id, **_kwargs: calls.append(user_id),
    )
    try:
        rolling.run_scheduled_managed_deliveries()
        assert calls == ["delivery-current"]
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        tmpdir.cleanup()
