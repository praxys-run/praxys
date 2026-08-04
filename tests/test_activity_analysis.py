"""Pure-function tests for analysis-ready activity segment features."""
from __future__ import annotations

import pandas as pd
import pytest

from analysis.metrics import (
    build_activity_environment_context,
    derive_stable_power_segments,
)
from api.views import normalize_activity_start_time


def test_environment_context_is_versioned_and_method_labeled() -> None:
    context = build_activity_environment_context(
        34.0,
        70.0,
        "stryd_activity_weather",
    )

    assert context["state"] == "available"
    assert context["model_version"] == "environmental-performance-context-v1"
    assert context["science_decision_id"] == (
        "sdr-environmental-performance-v1"
    )
    assert context["wet_bulb_c"] is not None
    assert context["wet_bulb_method"] == "stull_psychrometric"
    assert context["reason_codes"] == []
    assert any(
        source["id"] == "stull-2011"
        for source in context["science_sources"]
    )
    assert "outdoor_wbgt_unavailable" in context["limitations"]


def test_environment_context_marks_partial_inputs_explicitly() -> None:
    context = build_activity_environment_context(
        24.0,
        None,
        "garmin_activity_weather",
    )

    assert context["state"] == "partial"
    assert context["temperature_c"] == 24.0
    assert context["relative_humidity_pct"] is None
    assert context["wet_bulb_c"] is None
    assert context["reason_codes"] == ["relative_humidity_unavailable"]


def test_environment_context_rejects_corrupt_or_unknown_inputs() -> None:
    corrupt = build_activity_environment_context(
        95.0,
        140.0,
        "stryd_activity_weather",
    )
    unsupported = build_activity_environment_context(
        24.0,
        50.0,
        "weather_station_summary",
    )

    assert corrupt["state"] == "unavailable"
    assert corrupt["temperature_c"] is None
    assert corrupt["relative_humidity_pct"] is None
    assert corrupt["reason_codes"] == [
        "temperature_out_of_range",
        "relative_humidity_out_of_range",
    ]
    assert unsupported["state"] == "unavailable"
    assert unsupported["temperature_c"] is None
    assert unsupported["relative_humidity_pct"] is None
    assert unsupported["source"] == "weather_station_summary"
    assert unsupported["reason_codes"] == [
        "environment_source_unsupported"
    ]


def test_stable_segments_use_samples_for_power_and_hr_drift() -> None:
    base_epoch = 1_750_000_000
    samples = pd.DataFrame({
        "activity_id": ["activity-1"] * 601,
        "t_sec": [base_epoch + second for second in range(601)],
        "power_watts": [250.0] * 601,
        "hr_bpm": [
            140.0 + second / 60.0
            for second in range(601)
        ],
        "source": ["stryd"] * 601,
    })

    result = derive_stable_power_segments(
        samples,
        pd.DataFrame(),
        activity_duration_sec=600,
        cp_watts=300,
        cp_source="stryd",
        cp_power_provider="stryd",
        activity_provider="stryd",
    )

    assert result["status"] == "available"
    assert result["source"] == "samples"
    assert result["coverage"]["sample_coverage_ratio"] == 1.0
    assert result["coverage"]["gap_count"] == 0
    segment = result["segments"][0]
    assert segment["duration_sec"] == 600.0
    assert segment["mean_power_watts"] == 250.0
    assert segment["mean_pct_cp"] == 83.3
    assert segment["power_cv_pct"] == 0.0
    assert segment["hr_slope_bpm_per_min"] == pytest.approx(1.0)
    assert segment["hr_at_power_decoupling_pct"] > 0
    assert segment["power_provider"] == "stryd"


def test_split_fallback_is_explicitly_limited() -> None:
    splits = pd.DataFrame([{
        "split_num": 1,
        "duration_sec": 300,
        "avg_power": 240,
        "avg_hr": 150,
        "power_source": "stryd",
    }])

    result = derive_stable_power_segments(
        pd.DataFrame(),
        splits,
        activity_duration_sec=300,
        cp_watts=300,
        cp_source="stryd",
        cp_power_provider="stryd",
        activity_provider="garmin",
    )

    assert result["status"] == "limited"
    assert result["source"] == "splits"
    segment = result["segments"][0]
    assert segment["stability_state"] == "not_evaluable"
    assert segment["mean_pct_cp"] == 80.0
    assert segment["power_cv_pct"] is None
    assert segment["hr_slope_bpm_per_min"] is None
    assert segment["hr_at_power_decoupling_pct"] is None
    assert "stability_not_evaluable_from_splits" in segment["reason_codes"]


def test_missing_cp_and_hr_are_explicit_unavailable_states() -> None:
    base_epoch = 1_750_000_000
    samples = pd.DataFrame({
        "t_sec": [base_epoch + second for second in range(301)],
        "power_watts": [220.0] * 301,
        "hr_bpm": [None] * 301,
        "source": ["garmin"] * 301,
    })

    result = derive_stable_power_segments(
        samples,
        pd.DataFrame(),
        activity_duration_sec=300,
        cp_watts=None,
        activity_provider="garmin",
    )

    assert result["availability"]["critical_power"]["state"] == "unavailable"
    assert result["availability"]["heart_rate"]["state"] == "unavailable"
    segment = result["segments"][0]
    assert segment["mean_pct_cp"] is None
    assert segment["mean_hr_bpm"] is None
    assert "critical_power_unavailable" in segment["reason_codes"]
    assert "heart_rate_unavailable" in segment["reason_codes"]


def test_five_second_samples_still_use_a_sixty_second_window() -> None:
    base_epoch = 1_750_000_000
    samples = pd.DataFrame({
        "t_sec": [
            base_epoch + second
            for second in range(0, 601, 5)
        ],
        "power_watts": [230.0] * 121,
        "hr_bpm": [145.0] * 121,
        "source": ["stryd"] * 121,
    })

    result = derive_stable_power_segments(
        samples,
        pd.DataFrame(),
        activity_duration_sec=600,
        cp_watts=300,
        cp_source="stryd",
        cp_power_provider="stryd",
        activity_provider="stryd",
    )

    assert result["status"] == "available"
    assert result["segments"][0]["duration_sec"] == 600.0
    assert result["segments"][0]["power_cv_pct"] == 0.0


def test_shuffled_samples_do_not_fragment_a_continuous_segment() -> None:
    base_epoch = 1_750_000_000
    samples = pd.DataFrame({
        "t_sec": [base_epoch + second for second in range(601)],
        "power_watts": [230.0] * 601,
        "hr_bpm": [145.0] * 601,
        "source": ["stryd"] * 601,
    }).sample(frac=1.0, random_state=42)

    result = derive_stable_power_segments(
        samples,
        pd.DataFrame(),
        activity_duration_sec=600,
        cp_watts=300,
        cp_source="stryd",
        cp_power_provider="stryd",
        activity_provider="stryd",
    )

    assert result["status"] == "available"
    assert len(result["segments"]) == 1
    assert result["segments"][0]["duration_sec"] == 600.0


def test_adjacent_stable_plateaus_do_not_overlap() -> None:
    base_epoch = 1_750_000_000
    samples = pd.DataFrame({
        "t_sec": [base_epoch + second for second in range(601)],
        "power_watts": [200.0] * 300 + [260.0] + [220.0] * 300,
        "hr_bpm": [145.0] * 601,
        "source": ["stryd"] * 601,
    })

    result = derive_stable_power_segments(
        samples,
        pd.DataFrame(),
        activity_duration_sec=600,
        cp_watts=300,
        cp_source="stryd",
        cp_power_provider="stryd",
        activity_provider="stryd",
    )

    assert result["status"] == "available"
    assert len(result["segments"]) == 2
    first, second = result["segments"]
    assert first["end_offset_sec"] <= second["start_offset_sec"]
    assert first["duration_sec"] + second["duration_sec"] <= 600.0
    assert second["mean_power_watts"] == 220.0


def test_sparse_adjacent_stable_plateaus_do_not_overlap() -> None:
    base_epoch = 1_750_000_000
    samples = pd.DataFrame({
        "t_sec": [
            base_epoch + second
            for second in range(0, 601, 5)
        ],
        "power_watts": [200.0] * 60 + [260.0] + [220.0] * 60,
        "hr_bpm": [145.0] * 121,
        "source": ["stryd"] * 121,
    })

    result = derive_stable_power_segments(
        samples,
        pd.DataFrame(),
        activity_duration_sec=600,
        cp_watts=300,
        cp_source="stryd",
        cp_power_provider="stryd",
        activity_provider="stryd",
    )

    assert result["status"] == "available"
    assert len(result["segments"]) == 2
    first, second = result["segments"]
    assert first["end_offset_sec"] <= second["start_offset_sec"]
    assert first["duration_sec"] + second["duration_sec"] <= 600.0
    assert second["mean_power_watts"] == 220.0


def test_empty_samples_and_splits_are_unavailable() -> None:
    result = derive_stable_power_segments(
        pd.DataFrame(),
        pd.DataFrame(),
        activity_duration_sec=None,
        cp_watts=None,
    )

    assert result["status"] == "unavailable"
    assert result["source"] == "none"
    assert result["segments"] == []
    assert result["availability"]["samples"]["state"] == "unavailable"
    assert result["availability"]["stable_segments"]["state"] == (
        "unavailable"
    )


def test_activity_start_time_falls_back_to_sample_epoch_without_guessing() -> None:
    result = normalize_activity_start_time(
        "2026-07-01 14:00:00",
        sample_start_epoch=1_751_350_400,
    )

    assert result["state"] == "available"
    assert result["timezone"] == "UTC"
    assert result["provenance"] == "sample_epoch_fallback"
    assert result["utc"].endswith("Z")
    assert "activity_start_timezone_unknown" in result["reason_codes"]


def test_activity_start_time_without_offset_or_samples_is_unavailable() -> None:
    result = normalize_activity_start_time("2026-07-01 14:00:00")

    assert result == {
        "state": "unavailable",
        "utc": None,
        "timezone": None,
        "provenance": "none",
        "reason_codes": [
            "activity_start_timezone_unknown",
            "sample_start_unavailable",
        ],
    }
