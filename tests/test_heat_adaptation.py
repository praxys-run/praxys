"""Scientific and safety invariants for the heat-adaptation tracker."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from analysis.metrics import (
    apply_heat_adaptation_guidance,
    compute_heat_adaptation,
    estimate_wet_bulb_c,
)


def _activities(
    current_date: date,
    day_offsets: list[int],
    *,
    temperature_c: float = 34.0,
    relative_humidity_pct: float | None = 70.0,
    activity_avg_power: float = 0.0,
    source: str = "stryd",
    activity_type: str = "running",
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "activity_id": f"act-{offset}",
            "date": current_date - timedelta(days=offset),
            "activity_type": activity_type,
            "duration_sec": 3600.0,
            "temperature_c": temperature_c,
            "relative_humidity_pct": relative_humidity_pct,
            "avg_power": activity_avg_power,
            "source": source,
            "environment_source": "stryd_activity_weather",
        }
        for offset in day_offsets
    ])


def _splits(
    day_offsets: list[int],
    *,
    avg_power: float = 180.0,
    duration_sec: float = 3600.0,
    power_provider: str | None = "stryd",
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "activity_id": f"act-{offset}",
            "split_num": 1,
            "duration_sec": duration_sec,
            "avg_power": avg_power,
            "power_provider": power_provider,
        }
        for offset in day_offsets
    ])


def _samples(
    day_offsets: list[int],
    *,
    power_watts: float = 180.0,
    duration_sec: float = 3600.0,
    power_provider: str | None = "stryd",
) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "activity_id": f"act-{offset}",
            "power_watts": power_watts,
            "duration_sec": duration_sec,
            "power_provider": power_provider,
        }
        for offset in day_offsets
    ])


def _status(
    current_date: date,
    day_offsets: list[int],
    *,
    temperature_c: float = 34.0,
    relative_humidity_pct: float | None = 70.0,
    split_power: float = 180.0,
    activity_avg_power: float = 0.0,
    cp_watts: float | None = 270.0,
    cp_source: str | None = "stryd",
    cp_power_provider: str | None = None,
    activity_source: str = "stryd",
    activity_type: str = "running",
    split_power_provider: str | None = "stryd",
    sample_power: pd.DataFrame | None = None,
) -> dict:
    return compute_heat_adaptation(
        _activities(
            current_date,
            day_offsets,
            temperature_c=temperature_c,
            relative_humidity_pct=relative_humidity_pct,
            activity_avg_power=activity_avg_power,
            source=activity_source,
            activity_type=activity_type,
        ),
        _splits(
            day_offsets,
            avg_power=split_power,
            power_provider=split_power_provider,
        ),
        sample_power,
        cp_watts=cp_watts,
        cp_source=cp_source,
        cp_power_provider=cp_power_provider,
        current_date=current_date,
    )


def test_estimate_wet_bulb_c_matches_stull_and_rejects_invalid_inputs():
    """Stull's approximation is humidity-aware and used only in its domain."""
    assert estimate_wet_bulb_c(30.0, 70.0) == 25.6
    assert estimate_wet_bulb_c(30.0, 99.0) is not None
    assert estimate_wet_bulb_c(30.0, 100.0) is None
    assert estimate_wet_bulb_c(55.0, 70.0) is None
    assert estimate_wet_bulb_c(30.0, 2.0) is None


def test_heat_adaptation_counts_hot_dry_exposure_without_double_counting():
    """Dry heat contributes through a bounded alternative to the wet ramp."""
    today = date(2026, 7, 16)

    at_reference = _status(
        today,
        [0],
        temperature_c=30.0,
        relative_humidity_pct=5.0,
    )
    halfway = _status(
        today,
        [0],
        temperature_c=35.0,
        relative_humidity_pct=5.0,
    )
    full = _status(
        today,
        [0],
        temperature_c=40.0,
        relative_humidity_pct=5.0,
    )
    hot_humid = _status(
        today,
        [0],
        temperature_c=40.0,
        relative_humidity_pct=70.0,
    )
    outside_stull_rh = _status(
        today,
        [0],
        temperature_c=40.0,
        relative_humidity_pct=2.0,
    )
    partial_overlap = _status(
        today,
        [0],
        temperature_c=32.0,
        relative_humidity_pct=40.0,
    )

    assert at_reference["sessions"][0]["effective_heat_minutes"] == 0.0
    assert halfway["sessions"][0]["effective_heat_minutes"] == 30.0
    assert halfway["sessions"][0]["qualifies"] is True
    assert full["sessions"][0]["wet_bulb_c"] == 15.8
    assert full["sessions"][0]["effective_heat_minutes"] == 60.0
    assert hot_humid["sessions"][0]["effective_heat_minutes"] == 60.0
    assert outside_stull_rh["sessions"][0]["wet_bulb_c"] is None
    assert outside_stull_rh["sessions"][0]["effective_heat_minutes"] == 60.0
    assert partial_overlap["sessions"][0]["wet_bulb_c"] == 22.1
    assert partial_overlap["sessions"][0]["effective_heat_minutes"] == 30.8


def test_heat_adaptation_preserves_humid_heat_weighting():
    """Below the dry ramp, effective minutes still come from wet-bulb evidence."""
    today = date(2026, 7, 16)

    status = _status(
        today,
        [0],
        temperature_c=24.0,
        relative_humidity_pct=80.0,
    )

    assert status["sessions"][0]["wet_bulb_c"] == 21.4
    assert status["sessions"][0]["effective_heat_minutes"] == 25.5


def test_heat_adaptation_reaches_likely_adapted_in_hot_dry_conditions():
    """Seven full dry-heat sessions satisfy the same qualitative evidence bar."""
    today = date(2026, 7, 16)

    status = _status(
        today,
        [0, 1, 2, 3, 4, 5, 6],
        temperature_c=40.0,
        relative_humidity_pct=5.0,
    )

    assert status["stage"] == "likely_adapted"
    assert status["effective_heat_minutes"] == 420


def test_heat_adaptation_preserves_precision_at_adapted_boundary():
    """The displayed total cannot round across the qualitative stage boundary."""
    today = date(2026, 7, 16)
    offsets = [0, 1, 2, 3, 4, 5, 6]
    splits = _splits(offsets)
    splits.loc[splits["activity_id"] == "act-6", "duration_sec"] = 3570.0

    below = compute_heat_adaptation(
        _activities(today, offsets),
        splits,
        cp_watts=270.0,
        cp_source="stryd",
        current_date=today,
    )
    at_threshold = _status(today, offsets)

    assert below["effective_heat_minutes"] == 419.5
    assert below["stage"] == "building"
    assert at_threshold["effective_heat_minutes"] == 420.0
    assert at_threshold["stage"] == "likely_adapted"


def test_heat_adaptation_quantizes_mixed_tenths_before_stage_comparison():
    """Binary float accumulation cannot hold an exact decimal total below 420."""
    today = date(2026, 7, 16)
    offsets = list(range(10))
    splits = _splits(offsets)
    splits["duration_sec"] = [2514.0] * 9 + [2574.0]

    status = compute_heat_adaptation(
        _activities(today, offsets),
        splits,
        cp_watts=270.0,
        cp_source="stryd",
        current_date=today,
    )

    assert status["effective_heat_minutes"] == 420.0
    assert status["stage"] == "likely_adapted"


def test_heat_adaptation_uses_split_power_not_activity_average_power():
    """A high activity average cannot manufacture workload evidence."""
    today = date(2026, 7, 16)
    status = _status(
        today,
        [0, 1, 2, 3, 4, 5, 6],
        split_power=100.0,
        activity_avg_power=500.0,
    )

    assert status["stage"] == "insufficient_evidence"
    assert status["data_coverage"]["workload_supported_activities"] == 7
    assert status["contributing_sessions"] == 0
    assert status["sessions"][0]["workload_source"] == "splits"
    assert status["next_action"] == "continue_normal_training"
    assert "insufficient_power_evidence" not in status["reason_codes"]


def test_heat_adaptation_rejects_non_finite_power_evidence():
    """Infinity cannot manufacture qualifying workload or sample coverage."""
    today = date(2026, 7, 16)
    split_status = _status(
        today,
        [0, 1, 2, 3, 4, 5, 6],
        split_power=float("inf"),
    )
    sample_status = _status(
        today,
        [0],
        split_power=100.0,
        sample_power=_samples(
            [0],
            power_watts=float("inf"),
            duration_sec=float("inf"),
        ),
    )

    assert split_status["stage"] == "insufficient_evidence"
    assert split_status["data_coverage"]["workload_supported_activities"] == 0
    assert split_status["contributing_sessions"] == 0
    assert sample_status["sessions"][0]["workload_source"] == "splits"
    assert sample_status["sessions"][0]["sample_coverage_ratio"] == 0.0


def test_heat_adaptation_prefers_sample_power_over_splits():
    """Sample power prevents a coarser split from manufacturing workload."""
    today = date(2026, 7, 16)
    status = _status(
        today,
        [0, 1, 2],
        split_power=180.0,
        sample_power=_samples([0, 1, 2], power_watts=100.0),
    )

    assert status["stage"] == "insufficient_evidence"
    assert status["effective_heat_minutes"] == 0
    assert {
        session["workload_source"] for session in status["sessions"]
    } == {"samples"}


def test_heat_adaptation_falls_back_when_samples_are_sparse():
    """Partial sample streams cannot suppress complete split workload."""
    today = date(2026, 7, 16)
    status = _status(
        today,
        [0, 1],
        split_power=180.0,
        sample_power=_samples(
            [0, 1],
            power_watts=100.0,
            duration_sec=60.0,
        ),
    )

    assert status["stage"] == "building"
    assert status["effective_heat_minutes"] == 120
    assert {
        session["workload_source"] for session in status["sessions"]
    } == {"splits"}
    assert status["evidence_thresholds"]["sample_coverage_ratio"] == 0.9
    assert status["evidence_thresholds"]["sample_max_interval_sec"] == 5.0
    assert {
        session["sample_coverage_ratio"] for session in status["sessions"]
    } == {round(60 / 3600, 3)}


def test_heat_adaptation_uses_samples_at_exactly_ninety_percent_coverage():
    """The documented completeness boundary is inclusive and deterministic."""
    today = date(2026, 7, 16)

    exact = _status(
        today,
        [0],
        split_power=100.0,
        sample_power=_samples([0], duration_sec=3240.0),
    )
    below = _status(
        today,
        [0],
        split_power=100.0,
        sample_power=_samples([0], duration_sec=3239.0),
    )

    assert exact["sessions"][0]["workload_source"] == "samples"
    assert exact["sessions"][0]["sample_coverage_ratio"] == 0.9
    assert exact["sessions"][0]["work_minutes"] == 54.0
    assert below["sessions"][0]["workload_source"] == "splits"
    assert below["sessions"][0]["work_minutes"] == 0.0


def test_heat_adaptation_marks_sparse_samples_without_splits_unevaluable():
    """Sparse fragments are disclosed rather than treated as below threshold."""
    today = date(2026, 7, 16)
    status = compute_heat_adaptation(
        _activities(today, [0]),
        pd.DataFrame(),
        _samples([0], duration_sec=60.0),
        cp_watts=270.0,
        cp_source="stryd",
        current_date=today,
    )

    assert status["next_action"] == "sync_power_evidence"
    assert status["sessions"][0]["workload_source"] == "samples_incomplete"
    assert status["sessions"][0]["workload_evaluable"] is False


def test_heat_adaptation_rejects_mixed_sample_power_providers():
    """A complete stream assembled from incompatible providers fails closed."""
    today = date(2026, 7, 16)
    mixed_samples = pd.DataFrame([
        {
            "activity_id": "act-0",
            "power_watts": 180.0,
            "duration_sec": 1800.0,
            "power_provider": "stryd",
        },
        {
            "activity_id": "act-0",
            "power_watts": 180.0,
            "duration_sec": 1800.0,
            "power_provider": "garmin",
        },
    ])

    status = _status(today, [0], sample_power=mixed_samples)

    assert status["next_action"] == "sync_power_provenance"
    assert status["confidence"] == "low"
    assert status["data_coverage"]["power_source_unverified_activities"] == 1
    assert status["sessions"][0]["power_provider"] == "mixed"
    assert status["sessions"][0]["power_source_alignment"] == "mixed"
    assert status["sessions"][0]["workload_evaluable"] is False


def test_heat_adaptation_rejects_partially_unknown_sample_provenance():
    """Every selected duration bucket must share one verified provider."""
    today = date(2026, 7, 16)
    partial_samples = pd.DataFrame([
        {
            "activity_id": "act-0",
            "power_watts": 180.0,
            "duration_sec": 1800.0,
            "power_provider": "stryd",
        },
        {
            "activity_id": "act-0",
            "power_watts": 180.0,
            "duration_sec": 1800.0,
            "power_provider": None,
        },
    ])

    status = _status(today, [0], sample_power=partial_samples)

    assert status["next_action"] == "sync_power_provenance"
    assert status["sessions"][0]["power_provider"] is None
    assert status["sessions"][0]["power_source_alignment"] == "unknown"
    assert status["sessions"][0]["workload_evaluable"] is False


def test_heat_adaptation_rejects_unknown_split_power_provider():
    """Legacy splits remain unevaluable until a re-sync backfills provenance."""
    today = date(2026, 7, 16)
    status = _status(today, [0], split_power_provider=None)

    assert status["next_action"] == "sync_power_provenance"
    assert status["sessions"][0]["workload_source"] == "splits"
    assert status["sessions"][0]["power_provider"] is None
    assert status["sessions"][0]["power_source_alignment"] == "unknown"
    assert status["sessions"][0]["workload_evaluable"] is False


def test_heat_adaptation_excludes_non_running_power():
    """Cycling watts must never be compared with a running CP."""
    today = date(2026, 7, 16)
    status = _status(today, [0, 1], activity_type="cycling")

    assert status["stage"] == "insufficient_evidence"
    assert status["next_action"] == "sync_training_data"
    assert status["data_coverage"]["recent_activities"] == 0
    assert status["sessions"] == []


def test_heat_adaptation_rejects_mismatched_power_provider():
    """Garmin CP cannot classify Stryd workload on a different power scale."""
    today = date(2026, 7, 16)
    status = _status(
        today,
        [0, 1],
        cp_source="garmin",
        activity_source="stryd",
    )

    assert status["stage"] == "insufficient_evidence"
    assert status["next_action"] == "align_power_source"
    assert "power_source_mismatch" in status["reason_codes"]
    assert status["data_coverage"]["power_source_mismatch_activities"] == 2
    assert {
        session["workload_source"] for session in status["sessions"]
    } == {"splits"}
    assert {
        session["power_source_alignment"] for session in status["sessions"]
    } == {"mismatch"}
    assert all(
        session["workload_evaluable"] is False
        for session in status["sessions"]
    )


def test_heat_adaptation_accepts_activity_derived_cp_with_known_provider():
    """Activity-derived CP remains usable when its provider is explicit."""
    today = date(2026, 7, 16)
    status = _status(
        today,
        [0, 1],
        cp_source="activities",
        cp_power_provider="stryd",
    )

    assert status["stage"] == "building"
    assert status["cp_source"] == "activities"
    assert status["cp_power_provider"] == "stryd"
    assert {
        session["power_source_alignment"] for session in status["sessions"]
    } == {"matched"}


def test_heat_adaptation_fails_closed_without_cp_power_provenance():
    """A numeric CP without a provider cannot classify cross-device workload."""
    today = date(2026, 7, 16)
    status = _status(today, [0, 1], cp_source=None)

    assert status["stage"] == "insufficient_evidence"
    assert status["next_action"] == "sync_power_provenance"
    assert "power_source_unverified" in status["reason_codes"]
    assert status["data_coverage"]["workload_supported_activities"] == 0
    assert status["confidence"] == "low"


def test_heat_adaptation_reaches_likely_adapted_after_seven_day_block():
    today = date(2026, 7, 16)
    status = _status(today, [0, 1, 2, 3, 4, 5, 6])

    assert status["stage"] == "likely_adapted"
    assert status["confidence"] == "high"
    assert status["confidence_basis"] == "data_coverage"
    assert status["exposure_days"] == 7
    assert status["effective_heat_minutes"] == 420
    assert status["decay"]["start_days"] == 7
    assert status["decay"]["end_days"] == 28
    assert status["next_action"] == "no_additional_heat_needed"
    assert "adaptation_pct" not in status
    assert "acclimation_pct" not in status


def test_heat_adaptation_building_and_insufficient_evidence_are_distinct():
    today = date(2026, 7, 16)

    building = _status(today, [0, 2])
    insufficient = _status(today, [0])

    assert building["stage"] == "building"
    assert building["next_action"] == "continue_normal_training"
    assert insufficient["stage"] == "insufficient_evidence"
    assert insufficient["next_action"] == "continue_normal_training"


def test_heat_adaptation_maintains_then_decays_after_prior_block():
    today = date(2026, 7, 16)
    prior_block = [10, 11, 12, 13, 14, 15, 16]

    maintaining = _status(today, prior_block + [3])
    decaying = _status(today, prior_block)

    assert maintaining["stage"] == "maintaining"
    assert maintaining["next_action"] == "maintain_normal_training"
    assert maintaining["days_since_last_exposure"] == 3
    assert maintaining["decay"]["state"] == "within_retention_window"
    assert decaying["stage"] == "decaying"
    assert decaying["days_since_last_exposure"] == 10
    assert decaying["decay"]["state"] == "early"
    assert decaying["next_action"] == "continue_normal_training"


def test_heat_adaptation_marks_reacclimation_after_one_post_gap_session():
    today = date(2026, 7, 16)
    prior_block = [24, 25, 26, 27, 28, 29, 30]

    status = _status(today, prior_block + [1])

    assert status["stage"] == "building"
    assert status["is_reacclimating"] is True
    assert status["decay"]["state"] == "reacclimating"


def test_heat_adaptation_stale_reacclimation_returns_to_decay():
    """An old post-gap exposure cannot pin the tracker in reacclimation."""
    today = date(2026, 7, 16)
    prior_block = [30, 31, 32, 33, 34, 35, 36]

    status = _status(today, prior_block + [20])

    assert status["stage"] == "decaying"
    assert status["days_since_last_exposure"] == 20
    assert status["is_reacclimating"] is False
    assert status["decay"]["state"] == "early"


def test_heat_adaptation_reacclimates_after_a_later_long_gap():
    """A short first gap cannot hide a later break before the current streak."""
    today = date(2026, 7, 16)
    prior_block = [31, 32, 33, 34, 35, 36, 37]

    status = _status(today, prior_block + [24, 1])

    assert status["stage"] == "building"
    assert status["is_reacclimating"] is True
    assert status["decay"]["state"] == "reacclimating"


def test_heat_adaptation_clears_reacclimation_after_new_completed_block():
    today = date(2026, 7, 16)
    prior_block = [24, 25, 26, 27, 28, 29, 30]

    status = _status(today, prior_block + [0, 1, 2, 3, 4, 5, 6])

    assert status["stage"] == "likely_adapted"
    assert status["is_reacclimating"] is False
    assert status["decay"]["state"] == "retained"


def test_heat_adaptation_reports_missing_environment_and_power_evidence():
    today = date(2026, 7, 16)

    no_humidity = _status(today, [0, 1, 2], relative_humidity_pct=None)
    no_cp = _status(today, [0, 1, 2], cp_watts=None)

    assert no_humidity["stage"] == "insufficient_evidence"
    assert no_humidity["data_coverage"]["environment_supported_activities"] == 0
    assert "no_supported_environment_data" in no_humidity["reason_codes"]
    assert no_cp["stage"] == "insufficient_evidence"
    assert no_cp["next_action"] == "set_power_threshold"
    assert no_cp["confidence"] == "low"
    assert all(
        session["workload_evaluable"] is False
        for session in no_cp["sessions"]
    )


def test_heat_adaptation_handles_empty_and_structurally_missing_inputs():
    today = date(2026, 7, 16)

    empty = compute_heat_adaptation(
        pd.DataFrame(),
        pd.DataFrame(),
        cp_watts=270.0,
        cp_source="stryd",
        current_date=today,
    )
    missing_columns = compute_heat_adaptation(
        _activities(today, [0, 1]).drop(
            columns=["source", "environment_source"],
        ),
        _splits([0, 1]),
        cp_watts=270.0,
        cp_source="stryd",
        current_date=today,
    )

    assert empty["stage"] == "insufficient_evidence"
    assert empty["next_action"] == "sync_training_data"
    assert missing_columns["stage"] == "insufficient_evidence"
    assert missing_columns["sessions"] == []
    assert (
        missing_columns["data_coverage"]["environment_supported_activities"]
        == 0
    )
    assert "no_supported_environment_data" in missing_columns["reason_codes"]


def test_heat_adaptation_exposes_proxy_and_safety_limits():
    today = date(2026, 7, 16)
    status = _status(today, [0, 1])

    assert status["environment_proxy"] == {
        "type": "temperature_humidity_evidence",
        "wet_bulb_method": "stull_psychrometric",
        "combination": "max",
        "pressure_assumption": "standard_sea_level",
        "granularity": "activity_summary",
        "current_conditions_assessed": False,
        "excludes": [
            "wind",
            "solar_radiation",
            "within_session_weather",
            "clothing",
            "hydration_state",
            "core_temperature",
            "skin_temperature",
        ],
    }
    assert status["evidence_thresholds"]["dry_bulb_reference_c"] == 30.0
    assert status["evidence_thresholds"]["dry_bulb_full_weight_c"] == 40.0
    assert status["safety_notice_codes"] == [
        "not_medical_clearance",
        "current_conditions_not_assessed",
        "stop_for_heat_illness_symptoms",
    ]
    daanen = next(
        source
        for source in status["science_sources"]
        if source["id"] == "daanen-2018"
    )
    assert daanen["url"] == "https://doi.org/10.1007/s40279-017-0808-x"
    cramer_jay = next(
        source
        for source in status["science_sources"]
        if source["id"] == "cramer-jay-2016"
    )
    assert cramer_jay["url"] == "https://doi.org/10.1016/j.autneu.2016.03.001"


def test_restrictive_today_signal_suppresses_heat_building_guidance():
    today = date(2026, 7, 16)
    base = _status(today, [0, 2])

    restricted = apply_heat_adaptation_guidance(base, "rest")
    open_day = apply_heat_adaptation_guidance(base, "follow_plan")

    assert restricted["stage"] == "building"
    assert restricted["today_restricted"] is True
    assert restricted["next_action"] == "follow_today_signal"
    assert open_day["today_restricted"] is False
    assert open_day["next_action"] == "continue_normal_training"
    assert base["next_action"] == "continue_normal_training"
