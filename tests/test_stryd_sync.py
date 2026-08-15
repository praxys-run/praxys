from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from sync.stryd_sync import (
    _login_api,
    _workout_type_from_name,
    fetch_activities_api,
    fetch_training_plan_api,
    stryd_client_available,
    stryd_delivery_content_fingerprint,
)

pytestmark = pytest.mark.skipif(
    not stryd_client_available(),
    reason="private stryd-client dependency is unavailable",
)


def test_workout_type_from_name():
    assert _workout_type_from_name("Day 46 - Steady Aerobic") == "steady aerobic"
    assert _workout_type_from_name("Day 48 - Long") == "long"
    assert _workout_type_from_name("Day 47 - Recovery") == "recovery"
    assert _workout_type_from_name("Custom Name") == "custom name"


@patch("sync.stryd_sync.StrydClient")
def test_login_delegates_to_shared_stryd_client(mock_client):
    session = MagicMock(user_id="stryd-user", token="stryd-token")
    mock_client.return_value.authenticate.return_value = session

    assert _login_api("runner@example.test", "secret") == (
        "stryd-user",
        "stryd-token",
    )
    mock_client.assert_called_once_with(
        email="runner@example.test",
        password="secret",
        timeout=15,
        http=requests,
    )


def test_delivery_content_fingerprint_ignores_provider_uuids():
    base = {
        "workout_date": "2026-08-04",
        "title": "Threshold",
        "workout_type": "threshold",
        "description": "3x8min",
        "blocks": [{
            "uuid": "block-a",
            "repeat": 3,
            "segments": [{
                "uuid": "segment-a",
                "intensity_class": "work",
                "intensity_percent": {"min": 95, "max": 100},
            }],
        }],
    }
    regenerated = {
        **base,
        "blocks": [{
            **base["blocks"][0],
            "uuid": "block-b",
            "segments": [{
                **base["blocks"][0]["segments"][0],
                "uuid": "segment-b",
            }],
        }],
    }
    edited = {
        **regenerated,
        "description": "4x8min",
    }

    assert stryd_delivery_content_fingerprint(base) == (
        stryd_delivery_content_fingerprint(regenerated)
    )
    assert stryd_delivery_content_fingerprint(base) != (
        stryd_delivery_content_fingerprint(edited)
    )


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
            "desc": "Edited on Stryd",
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
    assert rows[0]["workout_description"] == "Edited on Stryd"
    assert rows[0]["activity_type"] == "running"
    assert rows[0]["workout_structure_status"] == "supported"
    assert rows[0]["workout_structure_version"] == "v1"
    assert rows[0]["workout_structure"] == {
        "steps": [{
            "type": "step",
            "phase": "work",
            "termination": {"type": "time", "seconds": 1200},
            "target": {
                "metric": "power",
                "unit": "percent_cp",
                "reference": "critical_power",
                "min": 95.0,
                "max": 105.0,
            },
        }],
    }
    assert len(rows[0]["provider_content_fingerprint"]) == 64
    assert len(rows[0]["provider_payload_fingerprint"]) == 64


@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_preserves_repeat_structure_and_trail_activity(
    mock_get,
):
    workout = {
        "deleted": False,
        "date": "2026-04-04T02:00:00Z",
        "workout": {
            "title": "Trail intervals",
            "type": "intervals",
            "surface": "trail",
            "blocks": [{
                "repeat": 4,
                "segments": [
                    {
                        "duration_type": "time",
                        "duration_time": {
                            "hour": 0,
                            "minute": 2,
                            "second": 3,
                        },
                        "intensity_class": "work",
                        "intensity_type": "percentage",
                        "intensity_percent": {"min": 100, "max": 105},
                    },
                    {
                        "duration_type": "time",
                        "duration_time": {
                            "hour": 0,
                            "minute": 1,
                            "second": 17,
                        },
                        "intensity_class": "rest",
                        "intensity_type": "percentage",
                        "intensity_percent": {"min": 55, "max": 65},
                    },
                ],
            }],
        },
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )

    row = fetch_training_plan_api("user-1", "tok")[0]

    assert row["activity_type"] == "trail_running"
    assert row["workout_structure_status"] == "supported"
    repeat = row["workout_structure"]["steps"][0]
    assert repeat["type"] == "repeat"
    assert repeat["repetitions"] == 4
    assert [
        step["termination"]["seconds"] for step in repeat["steps"]
    ] == [123, 77]
    assert [step["phase"] for step in repeat["steps"]] == [
        "work",
        "recovery",
    ]


@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_normalizes_distance_termination(
    mock_get,
):
    workout = {
        "deleted": False,
        "date": "2026-04-04T02:00:00Z",
        "workout": {
            "title": "Provider-specific workout",
            "type": "intervals",
            "blocks": [{
                "repeat": 2,
                "segments": [{
                    "duration_type": "distance",
                    "duration_distance": 1,
                    "distance_unit_selected": "mi",
                    "intensity_class": "work",
                    "intensity_type": "percentage",
                    "intensity_percent": {"min": 100, "max": 105},
                }],
            }],
        },
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )

    row = fetch_training_plan_api("user-1", "tok")[0]

    assert row["workout_structure_status"] == "supported"
    repeat = row["workout_structure"]["steps"][0]
    assert repeat["repetitions"] == 2
    assert repeat["steps"][0]["termination"] == {
        "type": "distance",
        "meters": 1609,
    }


@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_parses_no_target_and_rpe(mock_get):
    workout = {
        "deleted": False,
        "date": "2026-04-04T02:00:00Z",
        "workout": {
            "title": "Mixed targets",
            "type": "intervals",
            "blocks": [{
                "repeat": 1,
                "segments": [
                    {
                        "duration_type": "time",
                        "duration_time": {"minute": 2},
                        "intensity_class": "rest",
                        "intensity_type": "",
                        "intensity_percent": {
                            "min": 0,
                            "max": 0,
                            "value": 0,
                        },
                    },
                    {
                        "duration_type": "time",
                        "duration_time": {"minute": 3},
                        "intensity_class": "work",
                        "intensity_type": "rpe",
                        "rpe_selected": 7,
                        "intensity_percent": {
                            "min": 0,
                            "max": 0,
                            "value": 0,
                        },
                    },
                ],
            }],
        },
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )

    row = fetch_training_plan_api("user-1", "tok")[0]

    assert row["workout_structure_status"] == "supported"
    rest, work = row["workout_structure"]["steps"]
    assert rest["phase"] == "rest"
    assert rest["target"] == {
        "metric": "none",
        "unit": "none",
        "reference": "none",
    }
    assert work["phase"] == "work"
    assert work["target"] == {
        "metric": "rpe",
        "unit": "scale_10",
        "reference": "perceived_exertion",
        "min": 7.0,
        "max": 7.0,
    }


@patch("sync.stryd_sync.requests.get")
def test_fetch_training_plan_rejects_non_round_trippable_surface(mock_get):
    workout = {
        "deleted": False,
        "date": "2026-04-04T02:00:00Z",
        "workout": {
            "title": "Track intervals",
            "type": "intervals",
            "surface": "track",
            "blocks": [{
                "repeat": 1,
                "segments": [{
                    "duration_type": "time",
                    "duration_time": {"minute": 5},
                    "intensity_class": "work",
                    "intensity_type": "percentage",
                    "intensity_percent": {"min": 100, "max": 105},
                }],
            }],
        },
    }
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": [workout]}),
        raise_for_status=MagicMock(),
    )

    row = fetch_training_plan_api("user-1", "tok")[0]

    assert row["activity_type"] == "running"
    assert row["workout_structure_status"] == "unsupported"
    assert "workout_structure_version" not in row
    assert "workout_structure" not in row


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
def test_fetch_training_plan_days_back_expands_lower_bound(mock_get):
    """A buffered verification query must include the full prior UTC day."""
    mock_get.return_value = MagicMock(
        json=MagicMock(return_value={"workouts": []}),
        raise_for_status=MagicMock(),
    )

    fetch_training_plan_api("u", "t", days_back=3)

    params = mock_get.call_args.kwargs["params"]
    expected_start = int(
        datetime.combine(
            date.today() - timedelta(days=3),
            datetime.min.time(),
        ).timestamp()
    )
    assert params["from"] == expected_start


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
