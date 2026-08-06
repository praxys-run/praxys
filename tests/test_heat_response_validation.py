"""Synthetic tests for the research-only heat-response validation pipeline."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

import pytest

from analysis import heat_response_validation as heat_validation
from analysis.heat_response_validation import (
    HeatValidationConfig,
    HeatValidationInputError,
    validate_heat_response,
)


TEST_CONFIG = HeatValidationConfig(bootstrap_iterations=80)


def synthetic_research_dataset(
    *,
    activity_count: int = 20,
    constant_environment: bool = False,
) -> dict:
    """Build a non-personal activity-research-dataset-v1 fixture."""
    wet_bulb_pattern = (16.0, 24.0, 18.0, 28.0, 20.0, 30.0, 22.0, 26.0)
    adaptation_pattern = (
        False,
        True,
        False,
        True,
        True,
        False,
        True,
        False,
    )
    start = date(2026, 1, 1)
    records = []
    for activity_index in range(activity_count):
        wet_bulb = (
            21.0
            if constant_environment
            else wet_bulb_pattern[
                activity_index % len(wet_bulb_pattern)
            ]
        )
        temperature = wet_bulb + 7.0
        terrain = 8.0 + (activity_index * 7) % 28
        tsb = -12.0 + (activity_index * 5) % 24
        readiness = 64.0 + (activity_index * 3) % 24
        adapted = adaptation_pattern[
            activity_index % len(adaptation_pattern)
        ]
        activity_date = start + timedelta(days=activity_index)
        segments = []
        for segment_index in range(2):
            mean_pct_cp = 72.0 + (
                (activity_index * 3 + segment_index * 7) % 18
            )
            start_offset_sec = 720.0 + segment_index * 720.0
            duration_sec = 360.0 + segment_index * 60.0
            mean_hr = (
                105.0
                + 0.9 * wet_bulb
                + 0.42 * (mean_pct_cp - 75.0)
                + 0.035 * (start_offset_sec / 60.0)
                + 0.02 * (duration_sec / 60.0)
                + 0.025 * terrain
                + 0.04 * tsb
                - 0.06 * readiness
                + (-0.22 * (wet_bulb - 22.0) if adapted else 0.0)
            )
            segments.append({
                "source": "samples",
                "stability_state": "evaluated",
                "split_num": None,
                "start_offset_sec": start_offset_sec,
                "end_offset_sec": start_offset_sec + duration_sec,
                "duration_sec": duration_sec,
                "mean_power_watts": mean_pct_cp * 3.0,
                "mean_pct_cp": mean_pct_cp,
                "power_cv_pct": 1.2,
                "mean_hr_bpm": round(mean_hr, 3),
                "hr_slope_bpm_per_min": 0.3,
                "hr_at_power_decoupling_pct": 2.0,
                "sample_coverage_ratio": 1.0,
                "power_provider": "stryd",
                "heart_rate_provider": "stryd",
                "reason_codes": [],
            })
        records.append({
            "activity": {
                "activity_id": f"synthetic-private-{activity_index}",
                "date": activity_date.isoformat(),
                "source": "stryd",
                "activity_type": "running",
                "distance_km": 10.0,
                "elevation_gain_m": terrain * 10.0,
                "environment": {
                    "model_version":
                        "environmental-performance-context-v1",
                    "science_decision_id":
                        "sdr-environmental-performance-v1",
                    "state": "available",
                    "temperature_c": temperature,
                    "relative_humidity_pct": 65.0,
                    "source": "stryd_activity_weather",
                    "wet_bulb_c": wet_bulb,
                    "wet_bulb_method": "stull_psychrometric",
                    "reason_codes": [],
                    "limitations": ["outdoor_wbgt_unavailable"],
                },
                "sample_coverage": {
                    "state": "available",
                    "sample_count": 3600,
                    "sample_coverage_ratio": 1.0,
                    "power_coverage_ratio": 1.0,
                    "heart_rate_coverage_ratio": 1.0,
                    "gap_count": 0,
                    "reason_codes": [],
                },
            },
            "stable_segments": {
                "model_version": "stable-power-segments-v3",
                "status": "available",
                "source": "samples",
                "segments": segments,
            },
            "pre_activity_context": {
                "critical_power": {
                    "state": "available",
                    "value_watts": 300.0,
                    "effective_date": (
                        activity_date - timedelta(days=1)
                    ).isoformat(),
                    "source": "stryd",
                    "power_provider": "stryd",
                    "selection":
                        "latest_strictly_before_activity_date",
                    "reason_codes": [],
                },
                "load": {
                    "state": "available",
                    "as_of_date": (
                        activity_date - timedelta(days=1)
                    ).isoformat(),
                    "model_version": "banister-pmc-causal-v2",
                    "tsb": tsb,
                },
                "recovery": {
                    "state": "available",
                    "date": (
                        activity_date - timedelta(days=1)
                    ).isoformat(),
                    "source": "oura",
                    "values": {
                        "readiness_score": readiness,
                    },
                    "reason_codes": [],
                },
                "heat_adaptation": {
                    "state": "available",
                    "as_of_date": (
                        activity_date - timedelta(days=1)
                    ).isoformat(),
                    "stage": (
                        "likely_adapted"
                        if adapted
                        else "insufficient_evidence"
                    ),
                    "model_version": "heat-adaptation-v8",
                    "reason_codes": [],
                },
            },
        })
    return {
        "schema_version": "activity-research-dataset-v1",
        "model_versions": {
            "stable_segments": "stable-power-segments-v3",
            "environment": "environmental-performance-context-v1",
            "pre_activity_load": "banister-pmc-causal-v2",
            "heat_adaptation": ["heat-adaptation-v8"],
        },
        "records": records,
        "total": len(records),
        "limit": len(records),
        "offset": 0,
        "privacy": {
            "precise_gps_included": False,
            "credentials_included": False,
            "raw_samples_included": False,
        },
    }


def test_recovers_reviewable_heat_signal_with_activity_holdout() -> None:
    report = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )

    assert report["schema_version"] == (
        "heat-response-validation-report-v1"
    )
    assert report["model"]["status"] == "available"
    holdout = report["model"]["holdout"]
    assert holdout["train_activity_count"] == 15
    assert holdout["train_segment_count"] == 30
    assert holdout["test_activity_count"] == 5
    assert holdout["test_segment_count"] == 10
    assert holdout["activity_overlap_count"] == 0
    coefficient = report["model"]["heat_stress_coefficient"]
    assert coefficient["estimate_bpm_per_c"] > 0.2
    assert coefficient["uncertainty_interval_bpm_per_c"][0] is not None
    assert "adaptation_evidence" not in report["model"]["predictors"]
    assert "heat_x_adaptation" not in report["model"]["predictors"]
    exploratory = report["exploratory_analyses"][
        "heat_adaptation_secondary_model"
    ]
    assert exploratory["status"] == "available"
    assert exploratory["cannot_improve_recommendation"] is True
    assert report["recommendation"]["value"] == (
        "eligible_for_science_review"
    )
    assert report["recommendation"]["value"] != "ship"


def test_insufficient_observations_and_spread_are_unavailable() -> None:
    report = validate_heat_response(
        synthetic_research_dataset(
            activity_count=6,
            constant_environment=True,
        ),
        TEST_CONFIG,
    )

    assert report["gates"]["minimum_activities"]["status"] == (
        "unavailable"
    )
    assert report["gates"]["environmental_spread"]["status"] == (
        "unavailable"
    )
    assert report["model"]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_latest_activity_outcomes_do_not_change_training_coefficients() -> None:
    original = synthetic_research_dataset()
    changed_holdout = deepcopy(original)
    for record in changed_holdout["records"][-5:]:
        for segment in record["stable_segments"]["segments"]:
            segment["mean_hr_bpm"] += 50.0

    first = validate_heat_response(original, TEST_CONFIG)
    second = validate_heat_response(changed_holdout, TEST_CONFIG)

    assert first["model"]["coefficients"] == second["model"]["coefficients"]
    assert first["model"]["heat_stress_coefficient"][
        "uncertainty_interval_bpm_per_c"
    ] == second["model"]["heat_stress_coefficient"][
        "uncertainty_interval_bpm_per_c"
    ]
    assert first["model"]["performance"]["test"] != (
        second["model"]["performance"]["test"]
    )
    assert second["gates"][
        "chronological_holdout_performance"
    ]["status"] == "unavailable"
    assert second["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_split_fallback_is_excluded_with_explicit_reason() -> None:
    dataset = synthetic_research_dataset()
    split_record = deepcopy(dataset["records"][0])
    split_record["activity"]["activity_id"] = "split-only-private"
    split_record["stable_segments"]["source"] = "splits"
    split_record["stable_segments"]["status"] = "limited"
    for segment in split_record["stable_segments"]["segments"]:
        segment["source"] = "splits"
        segment["stability_state"] = "not_evaluated"
    dataset["records"].append(split_record)
    dataset["total"] += 1
    dataset["limit"] += 1

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_activity_count"] == 20
    assert report["exclusions"]["excluded_activity_reason_counts"][
        "split_fallback_excluded"
    ] == 1


def test_report_is_deterministic_and_contains_no_record_identity() -> None:
    dataset = synthetic_research_dataset()

    first = validate_heat_response(dataset, TEST_CONFIG)
    second = validate_heat_response(dataset, TEST_CONFIG)

    assert first == second
    serialized = repr(first)
    assert "synthetic-private-" not in serialized
    assert "2026-01-" not in serialized


def test_fixed_seed_report_is_independent_of_activity_id_names() -> None:
    dataset = synthetic_research_dataset()
    renamed = deepcopy(dataset)
    for index, record in enumerate(renamed["records"]):
        record["activity"]["activity_id"] = (
            f"opaque-renamed-{1000 - index * 17}"
        )

    original_report = validate_heat_response(dataset, TEST_CONFIG)
    renamed_report = validate_heat_response(renamed, TEST_CONFIG)

    assert renamed_report == original_report
    assert "opaque-renamed-" not in repr(renamed_report)


def test_adaptation_secondary_model_requires_activity_level_variation() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["heat_adaptation"]["stage"] = (
            "insufficient_evidence"
        )

    report = validate_heat_response(dataset, TEST_CONFIG)

    gate = report["gates"][
        "heat_adaptation_exploratory_availability"
    ]
    assert gate["status"] == "unavailable"
    assert gate["decision_required"] is False
    assert report["exploratory_analyses"][
        "heat_adaptation_secondary_model"
    ]["status"] == "unavailable"
    assert report["model"]["qualitative_heat_adaptation_used"] is False
    assert report["recommendation"]["value"] == (
        "eligible_for_science_review"
    )


def test_missing_recovery_is_never_silently_imputed() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["recovery"] = {
            "state": "unavailable",
            "date": None,
            "values": {},
            "reason_codes": ["recovery_unavailable_before_activity"],
        }

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["gates"]["dated_recovery"]["status"] == "unavailable"
    assert {
        omission["predictor"]: omission["reason_code"]
        for omission in report["omissions"]
    }["recovery_readiness_score"] == "missing_context_not_imputed"
    assert report["gates"]["dated_recovery"]["decision_required"] is False
    assert report["model"]["status"] == "available"
    assert report["recommendation"]["value"] == (
        "eligible_for_science_review"
    )


def test_dated_recovery_without_readiness_fails_recovery_gate() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["recovery"]["state"] = "partial"
        record["pre_activity_context"]["recovery"]["values"] = {
            "readiness_score": None,
            "hrv_avg": 55.0,
        }

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["gates"]["dated_recovery"]["status"] == "unavailable"
    assert report["gates"]["dated_recovery"]["observed"][
        "usable_dated_readiness_activities"
    ] == 0
    assert {
        omission["predictor"]: omission["reason_code"]
        for omission in report["omissions"]
    }["recovery_readiness_score"] == "missing_context_not_imputed"


def test_stale_recovery_readiness_is_reported_and_omitted() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        activity_date = date.fromisoformat(record["activity"]["date"])
        record["pre_activity_context"]["recovery"]["date"] = (
            activity_date - timedelta(days=2)
        ).isoformat()

    report = validate_heat_response(dataset, TEST_CONFIG)

    recovery = report["data_coverage"]["recovery_readiness"]
    assert recovery["dated_readiness_activity_count"] == 20
    assert recovery["usable_within_maximum_lag_activity_count"] == 0
    assert recovery["stale_dated_readiness_activity_count"] == 20
    assert recovery["observed_lag_days"] == {
        "minimum": 2,
        "median": 2.0,
        "maximum": 2,
    }
    assert recovery["maximum_recovery_lag_days"] == 1
    assert {
        omission["predictor"]: omission["reason_code"]
        for omission in report["omissions"]
    }["recovery_readiness_score"] == "missing_context_not_imputed"
    assert report["gates"]["dated_recovery"]["decision_required"] is False
    assert report["recommendation"]["value"] == (
        "eligible_for_science_review"
    )


def test_stale_adaptation_context_is_not_no_evidence() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["heat_adaptation"][
            "as_of_date"
        ] = "2020-01-01"

    report = validate_heat_response(dataset, TEST_CONFIG)

    gate = report["gates"][
        "heat_adaptation_exploratory_availability"
    ]
    assert gate["status"] == "unavailable"
    assert gate["observed"]["known_all_eligible"] == 0
    assert gate["observed"]["unavailable_all_eligible"] == 20
    assert report["exploratory_analyses"][
        "heat_adaptation_secondary_model"
    ]["status"] == "unavailable"


def test_per_record_stable_segment_version_is_pinned() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"][0]["stable_segments"]["model_version"] = (
        "stable-power-segments-future"
    )

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_activity_reason_counts"][
        "stable_segment_model_version_mismatch"
    ] == 1


def test_sensitivities_and_negative_control_are_reported() -> None:
    report = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )

    sensitivity_names = {
        item["name"] for item in report["sensitivity_analyses"]
    }
    assert {
        "wider_power_band",
        "narrower_power_band",
        "shorter_warmup_exclusion",
        "longer_warmup_exclusion",
        "shorter_minimum_duration",
        "longer_minimum_duration",
        "temperature_only",
        "critical_power_lower_assumption",
        "critical_power_higher_assumption",
    } == sensitivity_names
    assert report["negative_control"]["status"] == "available"
    assert report["negative_control"]["random_seed"] == (
        TEST_CONFIG.random_seed + 1
    )
    cp_sensitivities = {
        item["name"]: item
        for item in report["sensitivity_analyses"]
        if item["name"].startswith("critical_power_")
    }
    assert cp_sensitivities[
        "critical_power_lower_assumption"
    ]["research_configuration_changes"]["critical_power_change_pct"] == -5.0
    assert cp_sensitivities[
        "critical_power_higher_assumption"
    ]["research_configuration_changes"]["critical_power_change_pct"] == 5.0


def test_duplicate_source_and_activity_id_is_deduplicated() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"].append(deepcopy(dataset["records"][0]))
    dataset["total"] += 1
    dataset["limit"] += 1

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["input_activity_count"] == 21
    assert report["data_coverage"]["eligible_activity_count"] == 20
    assert report["exclusions"]["excluded_activity_reason_counts"][
        "duplicate_activity_identity"
    ] == 1
    assert report["model"]["holdout"]["activity_overlap_count"] == 0


@pytest.mark.parametrize(
    ("science_decision_id", "reason_code"),
    [
        (None, "environment_science_decision_id_missing"),
        ("sdr-environmental-performance-v2",
         "environment_science_decision_id_mismatch"),
    ],
)
def test_environment_science_decision_id_is_required(
    science_decision_id: str | None,
    reason_code: str,
) -> None:
    dataset = synthetic_research_dataset()
    environment = dataset["records"][0]["activity"]["environment"]
    if science_decision_id is None:
        environment.pop("science_decision_id")
    else:
        environment["science_decision_id"] = science_decision_id

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_activity_reason_counts"][
        reason_code
    ] == 1


def test_critical_power_must_be_strictly_pre_activity() -> None:
    dataset = synthetic_research_dataset()
    record = dataset["records"][0]
    record["pre_activity_context"]["critical_power"][
        "effective_date"
    ] = record["activity"]["date"]

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_activity_reason_counts"][
        "critical_power_not_strictly_pre_activity"
    ] == 1


@pytest.mark.parametrize(
    ("selection", "reason_code"),
    [
        (None, "critical_power_selection_missing"),
        ("latest_on_or_before_activity_date",
         "critical_power_selection_unsupported"),
    ],
)
def test_critical_power_selection_provenance_is_required(
    selection: str | None,
    reason_code: str,
) -> None:
    dataset = synthetic_research_dataset()
    critical_power = dataset["records"][0][
        "pre_activity_context"
    ]["critical_power"]
    if selection is None:
        critical_power.pop("selection")
    else:
        critical_power["selection"] = selection

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_activity_reason_counts"][
        reason_code
    ] == 1


def test_segment_pct_cp_must_match_dated_critical_power() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"][0]["stable_segments"]["segments"][0][
        "mean_pct_cp"
    ] += 2.0

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_segment_count"] == 39
    assert report["exclusions"]["excluded_segment_reason_counts"][
        "mean_pct_cp_critical_power_mismatch"
    ] == 1


def test_critical_power_provider_must_match_segment_provider() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"][0]["pre_activity_context"]["critical_power"][
        "power_provider"
    ] = "garmin"

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_segment_reason_counts"][
        "critical_power_provider_mismatch"
    ] == 2


def test_same_day_date_only_recovery_is_not_pre_activity() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["recovery"]["date"] = (
            record["activity"]["date"]
        )

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["gates"]["dated_recovery"]["status"] == "unavailable"
    assert report["gates"]["dated_recovery"]["observed"][
        "usable_dated_readiness_activities"
    ] == 0
    assert {
        omission["predictor"]: omission["reason_code"]
        for omission in report["omissions"]
    }["recovery_readiness_score"] == "missing_context_not_imputed"


def test_holdout_missing_selected_predictor_rows_are_excluded() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"][-5:]:
        record["pre_activity_context"]["recovery"] = {
            "state": "unavailable",
            "date": None,
            "values": {},
            "reason_codes": ["recovery_unavailable_before_activity"],
        }

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["model"]["status"] == "unavailable"
    assert "recovery_readiness_score" in report["model"][
        "selected_predictors"
    ]
    holdout = report["model"]["holdout"]
    assert holdout["candidate_test_activity_count"] == 5
    assert holdout["test_activity_count"] == 0
    assert holdout["excluded_test_segment_count"] == 10
    assert holdout["exclusion_reason_counts"][
        "selected_predictor_missing:recovery_readiness_score"
    ] == 10
    assert report["gates"]["chronological_holdout"]["status"] == (
        "unavailable"
    )


def test_evaluated_holdout_requires_environmental_spread() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"][-5:]:
        environment = record["activity"]["environment"]
        environment["wet_bulb_c"] = 22.0
        environment["temperature_c"] = 29.0

    report = validate_heat_response(dataset, TEST_CONFIG)

    gate = report["gates"]["holdout_environmental_spread"]
    assert gate["status"] == "unavailable"
    assert gate["decision_required"] is True
    assert gate["observed"]["evaluated_holdout_activity_count"] == 5
    assert gate["observed"]["evaluated_holdout_spread_c"] == 0.0
    assert gate["research_estimate"] == {
        "minimum_evaluated_holdout_spread_c":
            TEST_CONFIG.minimum_holdout_environmental_spread_c,
    }
    assert gate["reason_codes"] == [
        "holdout_environmental_spread_insufficient_after_exclusions"
    ]
    assert report["model"]["status"] == "available"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_same_date_activities_stay_in_one_holdout_partition() -> None:
    dataset = synthetic_research_dataset()
    record = dataset["records"][14]
    shared_date = dataset["records"][15]["activity"]["date"]
    previous_date = (
        date.fromisoformat(shared_date) - timedelta(days=1)
    ).isoformat()
    record["activity"]["date"] = shared_date
    context = record["pre_activity_context"]
    context["critical_power"]["effective_date"] = previous_date
    context["load"]["as_of_date"] = previous_date
    context["recovery"]["date"] = previous_date
    context["heat_adaptation"]["as_of_date"] = previous_date

    report = validate_heat_response(dataset, TEST_CONFIG)

    holdout = report["model"]["holdout"]
    assert holdout["train_activity_count"] == 14
    assert holdout["test_activity_count"] == 6
    assert holdout["activity_overlap_count"] == 0


@pytest.mark.parametrize("offset", [None, 0.0, True, "0"])
def test_pagination_offset_must_be_an_integer(offset: object) -> None:
    dataset = synthetic_research_dataset()
    if offset is None:
        dataset.pop("offset")
    else:
        dataset["offset"] = offset

    with pytest.raises(
        HeatValidationInputError,
        match="pagination offset must be an integer",
    ):
        validate_heat_response(dataset, TEST_CONFIG)


def test_nonzero_offset_withholds_as_not_first_page() -> None:
    dataset = synthetic_research_dataset()
    dataset["offset"] = 1
    dataset["records"] = dataset["records"][1:]

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["gates"]["first_input_page"]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total", None),
        ("total", True),
        ("total", 20.0),
        ("limit", None),
        ("limit", False),
        ("limit", "20"),
    ],
)
def test_pagination_total_and_limit_must_be_integers(
    field: str,
    value: object,
) -> None:
    dataset = synthetic_research_dataset()
    if value is None:
        dataset.pop(field)
    else:
        dataset[field] = value

    with pytest.raises(
        HeatValidationInputError,
        match=f"pagination {field} must be an integer",
    ):
        validate_heat_response(dataset, TEST_CONFIG)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("total", -1, "total must be non-negative"),
        ("limit", 0, "limit must be between 1 and 50"),
        ("limit", 51, "limit must be between 1 and 50"),
        ("offset", -1, "offset must be non-negative"),
    ],
)
def test_pagination_ranges_are_validated(
    field: str,
    value: int,
    message: str,
) -> None:
    dataset = synthetic_research_dataset()
    dataset[field] = value

    with pytest.raises(HeatValidationInputError, match=message):
        validate_heat_response(dataset, TEST_CONFIG)


def test_truncated_first_page_is_rejected() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"].pop()

    with pytest.raises(
        HeatValidationInputError,
        match="pagination records are incomplete: expected 20, got 19",
    ):
        validate_heat_response(dataset, TEST_CONFIG)


def test_insufficient_valid_bootstrap_resamples_withholds(
    monkeypatch,
) -> None:
    def insufficient_bootstrap(
        train_rows,
        feature_names,
        *,
        heat_representation,
        heat_center,
        config,
    ):
        del train_rows, heat_representation, heat_center, config
        return {name: [0.1, 0.2] for name in feature_names}

    monkeypatch.setattr(
        heat_validation,
        "_cluster_bootstrap",
        insufficient_bootstrap,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )

    heat = report["model"]["heat_stress_coefficient"]
    assert heat["bootstrap_interval_status"] == "unavailable"
    assert heat["uncertainty_interval_bpm_per_c"] == [None, None]
    assert report["gates"][
        "bootstrap_resample_sufficiency"
    ]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_failed_permuted_negative_control_withholds(
    monkeypatch,
) -> None:
    original = heat_validation._negative_control

    def failed_control(config, primary):
        result = original(config, primary)
        primary_mae = primary["model"]["performance"]["test"]["mae_bpm"]
        result["test_mae_bpm"] = max(0.0, float(primary_mae) - 1.0)
        return result

    monkeypatch.setattr(
        heat_validation,
        "_negative_control",
        failed_control,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )

    assert report["gates"][
        "permuted_negative_control_falsification"
    ]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_configurable_no_heat_falsification_gate_withholds() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        minimum_holdout_mae_improvement_vs_no_heat_bpm=100.0,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        config,
    )

    assert report["gates"][
        "no_heat_baseline_falsification"
    ]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_insufficient_sensitivity_variant_coverage_withholds() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        minimum_sensitivity_available_count=9,
        minimum_sensitivity_available_fraction=1.0,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        config,
    )

    gate = report["gates"]["sensitivity_analysis_coverage"]
    assert gate["status"] == "unavailable"
    assert gate["observed"]["planned_variant_count"] == 9
    assert gate["observed"]["available_variant_count"] == 8
    assert gate["observed"]["available_fraction"] == pytest.approx(8 / 9, 1e-4)
    assert gate["observed"]["unavailable_variants"] == [
        "longer_warmup_exclusion"
    ]
    assert report["model"]["heat_stress_coefficient"]["stability"][
        "classification"
    ] == "inconclusive_insufficient_sensitivity_coverage"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_unavailable_permissive_sensitivity_is_counted(
    monkeypatch,
) -> None:
    original = heat_validation._sensitivity_analyses

    def unavailable_wider_band(dataset, config):
        items = original(dataset, config)
        wider = next(
            item for item in items
            if item["name"] == "wider_power_band"
        )
        wider["status"] = "unavailable"
        wider["reason_codes"] = ["synthetic_variant_unavailable"]
        wider.pop("heat_coefficient_bpm_per_c", None)
        wider.pop("test_mae_bpm", None)
        wider.pop("test_rmse_bpm", None)
        return items

    monkeypatch.setattr(
        heat_validation,
        "_sensitivity_analyses",
        unavailable_wider_band,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )

    gate = report["gates"]["sensitivity_analysis_coverage"]
    assert gate["status"] == "unavailable"
    assert gate["observed"]["available_variant_count"] == 7
    assert gate["observed"]["unavailable_variants"] == [
        "wider_power_band",
        "longer_warmup_exclusion",
    ]
    assert report["model"]["heat_stress_coefficient"]["stability"][
        "classification"
    ] == "inconclusive_insufficient_sensitivity_coverage"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_cp_sensitivity_can_admit_segment_crossing_power_band() -> None:
    dataset = synthetic_research_dataset()
    segment = dataset["records"][0]["stable_segments"]["segments"][0]
    segment["mean_pct_cp"] = 96.0
    segment["mean_power_watts"] = 288.0

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert report["data_coverage"]["eligible_segment_count"] == 39
    sensitivities = {
        item["name"]: item
        for item in report["sensitivity_analyses"]
    }
    assert sensitivities["critical_power_higher_assumption"][
        "eligible_segment_count"
    ] == 40


def test_critical_power_sensitivity_fraction_must_be_bounded() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        critical_power_sensitivity_fraction=1.0,
    )

    with pytest.raises(
        ValueError,
        match="critical_power_sensitivity_fraction",
    ):
        validate_heat_response(
            synthetic_research_dataset(),
            config,
        )
