from unittest.mock import MagicMock, patch

import pytest
import requests

from sync.stryd_sync import (
    _workout_type_from_name,
    fetch_activities_api,
    fetch_training_plan_api,
)


def test_workout_type_from_name():
    assert _workout_type_from_name("Day 46 - Steady Aerobic") == "steady aerobic"
    assert _workout_type_from_name("Day 48 - Long") == "long"
    assert _workout_type_from_name("Day 47 - Recovery") == "recovery"
    assert _workout_type_from_name("Custom Name") == "custom name"


# --- fetch_training_plan_api parses power targets ---

@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_parses_power_targets(mock_get):
    """Training plan should convert CP percentage targets to absolute watts."""
    workout = {
        "deleted": False,
        "date": "2026-04-04T02:00:00Z",
        "duration": 3600,
        "distance": 10000,
        "workout": {
            "title": "Day 10 - Threshold",
            "type": "threshold",
            "blocks": [
                {
                    "repeat": 1,
                    "segments": [
                        {
                            "intensity_class": "work",
                            "intensity_percent": {"min": 95, "max": 105},
                            "duration_time": {"minute": 20},
                        }
                    ],
                }
            ],
        },
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )

    rows = fetch_training_plan_api("user-1", "tok", cp_watts=250.0)

    assert len(rows) == 1
    assert rows[0]["target_power_min"] == "238"  # round(250 * 95 / 100)
    assert rows[0]["target_power_max"] == "262"  # round(250 * 105 / 100) = 262 (banker's rounding)
    assert rows[0]["workout_type"] == "threshold"


@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_date_uses_local_timezone(mock_get):
    """Date must truncate in the workout's local tz, not UTC. A workout at
    local midnight is serialized by Stryd as the prior day 16:00Z for +08:00;
    truncating in UTC drops a day, so tomorrow's session shows as today."""
    workout = {
        "deleted": False,
        # Tue Apr 7 00:00 +08:00 -> Mon Apr 6 16:00 UTC. Naive UTC truncation
        # would yield 2026-04-06; the local date is 2026-04-07.
        "date": "2026-04-06T16:00:00Z",
        "time_zone": "Asia/Shanghai",
        "duration": 3600,
        "workout": {"title": "Day 11 - Time Trial", "type": "time trial", "blocks": []},
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )

    rows = fetch_training_plan_api("user-1", "tok")

    assert len(rows) == 1
    assert rows[0]["date"] == "2026-04-07"


@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_tz_name_fallback_on_utc_server(mock_get):
    """When the item has no time_zone, the caller-supplied athlete tz must
    still pull the date into local time so a UTC server doesn't drop a day."""
    workout = {
        "deleted": False,
        "date": "2026-06-29T16:00:00Z",  # Tue 00:00 +08:00 == Mon 16:00Z
        "workout": {"title": "Time Trial", "type": "time trial", "blocks": []},
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )
    rows = fetch_training_plan_api("u", "t", tz_name="Asia/Shanghai")
    assert rows[0]["date"] == "2026-06-30"


@patch("sync.stryd_sync.requests.get")
def test_fetch_activities_normalizes_relative_humidity_to_percent(mock_get):
    """Stryd's fractional humidity is persisted in an explicit percent unit."""
    activity = {
        "id": "heat-1",
        "start_time": 1_752_643_200,
        "time_zone": "Asia/Shanghai",
        "moving_time": 3600,
        "distance": 10_000,
        "temperature": 33.4,
        "humidity": 0.72,
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"activities": [activity]}),
        raise_for_status=MagicMock(),
    )

    rows, _ = fetch_activities_api(
        "user-1",
        "token",
        from_date="2025-07-01",
        to_date="2025-07-31",
    )

    assert rows[0]["temperature_c"] == "33.4"
    assert rows[0]["relative_humidity_pct"] == "72.0"
    assert rows[0]["environment_source"] == "stryd_activity_weather"
    assert "humidity" not in rows[0]


@patch("sync.stryd_sync.requests.get")
def test_fetch_activities_excludes_treadmill_weather(mock_get):
    """Outdoor summary weather cannot stand in for treadmill conditions."""
    activity = {
        "id": "indoor-heat-1",
        "start_time": 1_752_643_200,
        "time_zone": "Asia/Shanghai",
        "moving_time": 3600,
        "distance": 10_000,
        "type": "run",
        "surface_type": "treadmill",
        "temperature": 33.4,
        "humidity": 0.72,
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"activities": [activity]}),
        raise_for_status=MagicMock(),
    )

    rows, _ = fetch_activities_api(
        "user-1",
        "token",
        from_date="2025-07-01",
        to_date="2025-07-31",
    )

    assert rows[0]["temperature_c"] == ""
    assert rows[0]["relative_humidity_pct"] == ""
    assert rows[0]["environment_source"] == ""
