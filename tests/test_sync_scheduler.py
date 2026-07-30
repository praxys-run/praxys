"""Tests for sync scheduler frequency guardrails."""

import pytest

from db.sync_scheduler import (
    ALLOWED_SYNC_INTERVAL_HOURS,
    DEFAULT_SYNC_INTERVAL_HOURS,
    _run_managed_delivery_tick,
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
