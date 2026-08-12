"""Tests for Stryd workout upload functions."""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from sync.stryd_sync import (
    build_workout_blocks,
    create_workout_api,
    delete_workout_api,
    _make_segment,
)


# --- build_workout_blocks ---


class TestBuildWorkoutBlocks:
    """Tests for converting AI plan workouts to Stryd block format."""

    def test_easy_run_single_block(self):
        """Easy run produces a single warmup-class block."""
        workout = {
            "workout_type": "easy",
            "planned_duration_min": "50",
            "target_power_min": "140",
            "target_power_max": "191",
            "workout_description": "Easy aerobic run.",
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        assert len(blocks) == 1
        seg = blocks[0]["segments"][0]
        assert seg["intensity_class"] == "warmup"
        assert seg["duration_time"]["minute"] == 50
        # CP percentages: 140/248 ≈ 56%, 191/248 ≈ 77%
        assert seg["intensity_percent"]["min"] == 56
        assert seg["intensity_percent"]["max"] == 77

    def test_recovery_run(self):
        """Recovery run uses warmup class with lower power."""
        workout = {
            "workout_type": "recovery",
            "planned_duration_min": "35",
            "target_power_min": "130",
            "target_power_max": "155",
            "workout_description": "Recovery shake-out.",
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        assert len(blocks) == 1
        seg = blocks[0]["segments"][0]
        assert seg["intensity_class"] == "warmup"
        assert seg["intensity_percent"]["min"] == 52  # 130/248
        assert seg["intensity_percent"]["max"] == 62  # round(155/248*100) = 62

    def test_structured_workout_is_authoritative(self):
        """Authoritative structured workouts drive block layout without parsing descriptions."""
        workout = {
            "workout_type": "interval",
            "activity_type": "trail_running",
            "workout_description": "WU 15min, 4x4min @265-280W w/ 3min jog recovery, CD 10min.",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [
                    {
                        "type": "step",
                        "phase": "warmup",
                        "termination": {"type": "time", "seconds": 900},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 65,
                            "max": 75,
                        },
                    },
                    {
                        "type": "repeat",
                        "repetitions": 4,
                        "steps": [
                            {
                                "type": "step",
                                "phase": "work",
                                "termination": {
                                    "type": "time",
                                    "seconds": 240,
                                },
                                "target": {
                                    "metric": "power",
                                    "unit": "percent_cp",
                                    "reference": "critical_power",
                                    "min": 107,
                                    "max": 113,
                                },
                            },
                            {
                                "type": "step",
                                "phase": "recovery",
                                "termination": {
                                    "type": "time",
                                    "seconds": 180,
                                },
                                "target": {
                                    "metric": "power",
                                    "unit": "percent_cp",
                                    "reference": "critical_power",
                                    "min": 60,
                                    "max": 65,
                                },
                            },
                        ],
                    },
                    {
                        "type": "step",
                        "phase": "cooldown",
                        "termination": {"type": "time", "seconds": 600},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 60,
                            "max": 70,
                        },
                    },
                ]
            },
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        assert len(blocks) == 3  # warmup, intervals, cooldown

        # Warmup
        assert blocks[0]["repeat"] == 1
        assert blocks[0]["segments"][0]["intensity_class"] == "warmup"
        assert blocks[0]["segments"][0]["duration_time"]["minute"] == 15

        # Intervals: 4x(work + rest)
        assert blocks[1]["repeat"] == 4
        assert len(blocks[1]["segments"]) == 2
        assert blocks[1]["segments"][0]["intensity_class"] == "work"
        assert blocks[1]["segments"][0]["duration_time"]["minute"] == 4
        assert blocks[1]["segments"][1]["intensity_class"] == "rest"
        assert blocks[1]["segments"][1]["duration_time"]["minute"] == 3

        # Work intensity uses the structured %CP target directly.
        work_pct = blocks[1]["segments"][0]["intensity_percent"]
        assert work_pct["min"] == 107
        assert work_pct["max"] == 113

        # Cooldown
        assert blocks[2]["segments"][0]["intensity_class"] == "cooldown"
        assert blocks[2]["segments"][0]["duration_time"]["minute"] == 10

    def test_structured_step_preserves_integer_seconds(self):
        workout = {
            "workout_type": "interval",
            "activity_type": "running",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [{
                    "type": "step",
                    "phase": "work",
                    "termination": {"type": "time", "seconds": 123},
                    "target": {
                        "metric": "power",
                        "unit": "percent_cp",
                        "reference": "critical_power",
                        "min": 95,
                        "max": 100,
                    },
                }],
            },
        }

        segment = build_workout_blocks(
            workout,
            cp_watts=248.0,
        )[0]["segments"][0]

        assert segment["duration_time"] == {
            "hour": 0,
            "minute": 2,
            "second": 3,
        }

    @pytest.mark.parametrize(
        "structure_fields",
        [
            {
                "workout_structure_version": "v2",
                "workout_structure": {"steps": []},
            },
            {
                "workout_structure_version": "v1",
                "workout_structure": None,
            },
            {
                "workout_structure": {
                    "steps": [{
                        "type": "step",
                        "phase": "work",
                        "termination": {
                            "type": "time",
                            "seconds": 300,
                        },
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 95,
                            "max": 100,
                        },
                    }],
                },
            },
            {
                "workout_structure_version": "v1",
                "workout_structure": {"steps": []},
            },
        ],
    )
    def test_unknown_mismatched_and_empty_structures_never_fall_back_to_flat(
        self,
        structure_fields,
    ):
        workout = {
            "workout_type": "interval",
            "planned_duration_min": 45,
            "target_power_min": 240,
            "target_power_max": 260,
            **structure_fields,
        }

        with pytest.raises(
            ValueError,
            match="structured delivery",
        ):
            build_workout_blocks(workout, cp_watts=248.0)

    @pytest.mark.parametrize(
        "step",
        [
            {
                "type": "step",
                "phase": "other",
                "termination": {"type": "time", "seconds": 300},
                "target": {
                    "metric": "power",
                    "unit": "percent_cp",
                    "reference": "critical_power",
                    "min": 95,
                },
            },
            {
                "type": "step",
                "phase": "work",
                "termination": {"type": "distance", "meters": 1000},
                "target": {
                    "metric": "power",
                    "unit": "percent_cp",
                    "reference": "critical_power",
                    "min": 95,
                },
            },
            {
                "type": "step",
                "phase": "work",
                "termination": {"type": "time", "seconds": 300},
                "target": {
                    "metric": "heart_rate",
                    "unit": "bpm",
                    "reference": "absolute",
                    "min": 150,
                },
            },
        ],
    )
    def test_only_exact_safe_v1_subset_is_translated(self, step):
        workout = {
            "workout_type": "interval",
            "workout_structure_version": "v1",
            "workout_structure": {"steps": [step]},
        }

        with pytest.raises(ValueError, match="cannot safely encode"):
            build_workout_blocks(workout, cp_watts=248.0)

    def test_description_is_not_parsed_without_structured_workout(self):
        """Legacy flat workouts no longer recover interval structure from free text."""
        workout = {
            "workout_type": "interval",
            "planned_duration_min": "65",
            "target_power_min": "265",
            "target_power_max": "280",
            "workout_description": "WU 15min, 4x4min @265-280W w/ 3min jog recovery, CD 10min.",
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        assert len(blocks) == 1
        seg = blocks[0]["segments"][0]
        assert seg["intensity_class"] == "work"
        assert seg["duration_time"] == {"hour": 1, "minute": 5, "second": 0}
        assert seg["intensity_percent"] == {"min": 107, "max": 113, "value": 110}

    def test_rest_day_fallback(self):
        """Rest day still produces blocks (caller should filter)."""
        workout = {
            "workout_type": "rest",
            "planned_duration_min": "",
            "target_power_min": "",
            "target_power_max": "",
            "workout_description": "Rest day.",
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        # Falls back to default single block
        assert len(blocks) == 1

    def test_no_power_targets_uses_defaults(self):
        """When power targets are missing, uses type-based defaults."""
        workout = {
            "workout_type": "long_run",
            "planned_duration_min": "140",
            "target_power_min": "",
            "target_power_max": "",
            "workout_description": "Long trail run.",
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        seg = blocks[0]["segments"][0]
        assert seg["intensity_percent"]["min"] == 68
        assert seg["intensity_percent"]["max"] == 78

    def test_blocks_have_uuids(self):
        """All blocks and segments have unique UUIDs."""
        workout = {
            "workout_type": "interval",
            "activity_type": "running",
            "workout_structure_version": "v1",
            "workout_structure": {
                "steps": [
                    {
                        "type": "step",
                        "phase": "warmup",
                        "termination": {"type": "time", "seconds": 900},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 65,
                            "max": 75,
                        },
                    },
                    {
                        "type": "repeat",
                        "repetitions": 4,
                        "steps": [
                            {
                                "type": "step",
                                "phase": "work",
                                "termination": {
                                    "type": "time",
                                    "seconds": 240,
                                },
                                "target": {
                                    "metric": "power",
                                    "unit": "percent_cp",
                                    "reference": "critical_power",
                                    "min": 107,
                                    "max": 113,
                                },
                            },
                            {
                                "type": "step",
                                "phase": "recovery",
                                "termination": {
                                    "type": "time",
                                    "seconds": 180,
                                },
                                "target": {
                                    "metric": "power",
                                    "unit": "percent_cp",
                                    "reference": "critical_power",
                                    "min": 60,
                                    "max": 65,
                                },
                            },
                        ],
                    },
                    {
                        "type": "step",
                        "phase": "cooldown",
                        "termination": {"type": "time", "seconds": 600},
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 60,
                            "max": 70,
                        },
                    },
                ]
            },
        }
        blocks = build_workout_blocks(workout, cp_watts=248.0)
        uuids = set()
        for b in blocks:
            uuids.add(b["uuid"])
            for seg in b["segments"]:
                uuids.add(seg["uuid"])
        # All unique
        total = sum(1 + len(b["segments"]) for b in blocks)
        assert len(uuids) == total


# --- _make_segment ---


class TestMakeSegment:
    def test_segment_structure(self):
        seg = _make_segment("work", 5, 90, 100)
        assert seg["intensity_class"] == "work"
        assert seg["duration_type"] == "time"
        assert seg["duration_time"] == {"hour": 0, "minute": 5, "second": 0}
        assert seg["intensity_type"] == "percentage"
        assert seg["intensity_percent"] == {"min": 90, "max": 100, "value": 95}
        assert "uuid" in seg

    def test_long_duration(self):
        seg = _make_segment("warmup", 90, 65, 75)
        assert seg["duration_time"] == {"hour": 1, "minute": 30, "second": 0}


# --- create_workout_api ---


class TestCreateWorkoutApi:
    @patch("sync.stryd_sync.requests.post")
    def test_payload_shape(self, mock_post: MagicMock):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 12345, "stress": 13.0}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        blocks = [{"uuid": "test", "repeat": 1, "segments": []}]
        create_workout_api(
            user_id="abc-123",
            token="tok",
            workout_date="2026-04-10",
            title="Test Workout",
            blocks=blocks,
            workout_type="easy run",
            description="A test",
            surface="road",
        )

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["title"] == "Test Workout"
        assert payload["id"] == -1
        assert payload["source"] == "USER"
        assert payload["blocks"] == blocks

    @patch("sync.stryd_sync.requests.post")
    def test_timestamp_calculation(self, mock_post: MagicMock):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 1}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        create_workout_api("uid", "tok", "2026-04-10", "Test", [])

        call_kwargs = mock_post.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        # 2026-04-10 00:00:00 UTC
        expected_ts = int(datetime(2026, 4, 10, tzinfo=timezone.utc).timestamp())
        assert params["timestamp"] == expected_ts


# --- delete_workout_api ---


class TestDeleteWorkoutApi:
    @patch("sync.stryd_sync.requests.delete")
    def test_delete_url(self, mock_delete: MagicMock):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_delete.return_value = mock_resp

        result = delete_workout_api("abc-123", "tok", "5401718379937792")
        assert result is True

        url = mock_delete.call_args[0][0]
        assert "abc-123" in url
        assert "5401718379937792" in url
