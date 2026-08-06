"""Synthetic tests for the research-only heat-response validation pipeline."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json

import pytest

from analysis import heat_response_validation as heat_validation
from analysis.heat_response_validation import (
    HeatValidationConfig,
    HeatValidationInputError,
    validate_heat_response,
)


TEST_CONFIG = HeatValidationConfig(
    bootstrap_iterations=80,
    permutation_iterations=80,
)


def _api_dataset_hash(dataset: dict) -> str:
    core = {
        key: value
        for key, value in dataset.items()
        if key not in {"dataset_hash", "generated_at"}
    }
    encoded = json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _refresh_dataset_hash(dataset: dict) -> dict:
    dataset["dataset_hash"] = _api_dataset_hash(dataset)
    return dataset


def _validate_modified_synthetic(
    dataset: dict,
    config: HeatValidationConfig = TEST_CONFIG,
) -> dict:
    return validate_heat_response(_refresh_dataset_hash(dataset), config)


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
                    "selection":
                        "latest_on_or_before_activity_date",
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
    dataset = {
        "schema_version": "activity-research-dataset-v1",
        "model_versions": {
            "stable_segments": "stable-power-segments-v3",
            "environment": "environmental-performance-context-v1",
            "pre_activity_load": "banister-pmc-causal-v2",
            "heat_adaptation": (
                ["heat-adaptation-v8"] if records else []
            ),
        },
        "records": records,
        "total": len(records),
        "limit": max(1, len(records)),
        "offset": 0,
        "privacy": {
            "precise_gps_included": False,
            "credentials_included": False,
            "raw_samples_included": False,
        },
        "generated_at": "2026-02-01T00:00:00Z",
    }
    return _refresh_dataset_hash(dataset)


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
    assert report["input_contract"][
        "input_contains_private_activity_ids"
    ] is True
    assert report["input_contract"][
        "input_contains_private_activity_dates"
    ] is True
    assert report["input_contract"]["report_includes_activity_ids"] is False
    assert report["input_contract"]["report_includes_activity_dates"] is False


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
    assert report["gates"][
        "no_heat_baseline_falsification"
    ]["status"] == "unavailable"
    assert report["gates"][
        "permuted_negative_control_falsification"
    ]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_legitimate_empty_api_export_returns_withheld_report() -> None:
    dataset = synthetic_research_dataset(activity_count=0)

    report = validate_heat_response(dataset, TEST_CONFIG)

    assert dataset["records"] == []
    assert dataset["total"] == 0
    assert dataset["model_versions"]["heat_adaptation"] == []
    assert report["model"]["status"] == "unavailable"
    assert report["gates"]["minimum_activities"]["status"] == "unavailable"
    assert report["gates"]["minimum_segments"]["status"] == "unavailable"
    assert report["negative_control"]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )
    assert "synthetic-private-" not in repr(report)
    assert "2026-01-" not in repr(report)


def test_latest_activity_outcomes_do_not_change_training_coefficients() -> None:
    original = synthetic_research_dataset()
    changed_holdout = deepcopy(original)
    for record in changed_holdout["records"][-5:]:
        for segment in record["stable_segments"]["segments"]:
            segment["mean_hr_bpm"] += 50.0

    first = validate_heat_response(original, TEST_CONFIG)
    second = _validate_modified_synthetic(changed_holdout)

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
    ]["status"] == "fail"
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

    report = _validate_modified_synthetic(dataset)

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
    renamed_report = _validate_modified_synthetic(renamed)

    assert renamed_report == original_report
    assert "opaque-renamed-" not in repr(renamed_report)


def test_adaptation_secondary_model_requires_activity_level_variation() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["heat_adaptation"]["stage"] = (
            "insufficient_evidence"
        )

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_activity_reason_counts"][
        reason_code
    ] == 1


def test_segment_pct_cp_must_match_dated_critical_power() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"][0]["stable_segments"]["segments"][0][
        "mean_pct_cp"
    ] += 2.0

    report = _validate_modified_synthetic(dataset)

    assert report["data_coverage"]["eligible_segment_count"] == 39
    assert report["exclusions"]["excluded_segment_reason_counts"][
        "mean_pct_cp_critical_power_mismatch"
    ] == 1


def test_critical_power_provider_must_match_segment_provider() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"][0]["pre_activity_context"]["critical_power"][
        "power_provider"
    ] = "garmin"

    report = _validate_modified_synthetic(dataset)

    assert report["data_coverage"]["eligible_activity_count"] == 19
    assert report["exclusions"]["excluded_segment_reason_counts"][
        "critical_power_provider_mismatch"
    ] == 2


def test_mixed_provider_regimes_fail_decision_gate_without_identity() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"][::2]:
        for segment in record["stable_segments"]["segments"]:
            segment["heart_rate_provider"] = "garmin"

    report = _validate_modified_synthetic(dataset)

    gate = report["gates"]["provider_regime_consistency"]
    assert gate["status"] == "fail"
    assert gate["decision_required"] is True
    assert gate["observed"] == {
        "combination_count": 2,
        "combinations": [
            {
                "label": "power=stryd|heart_rate=garmin",
                "activity_count": 10,
                "segment_count": 20,
            },
            {
                "label": "power=stryd|heart_rate=stryd",
                "activity_count": 10,
                "segment_count": 20,
            },
        ],
    }
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )
    assert "synthetic-private-" not in repr(gate)
    assert "2026-01-" not in repr(gate)


@pytest.mark.parametrize(
    ("field", "sentinel"),
    [
        ("heart_rate_provider", "mixed"),
        ("heart_rate_provider", "unverified"),
        ("power_provider", "mixed"),
    ],
)
def test_uniform_unverified_provider_sentinel_fails_consistency_gate(
    field: str,
    sentinel: str,
) -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        if field == "power_provider":
            record["pre_activity_context"]["critical_power"][
                "power_provider"
            ] = sentinel
        for segment in record["stable_segments"]["segments"]:
            segment[field] = sentinel

    report = _validate_modified_synthetic(dataset)

    gate = report["gates"]["provider_regime_consistency"]
    assert gate["status"] == "fail"
    assert gate["reason_codes"] == ["unverified_provider_sentinel"]
    assert gate["observed"]["combination_count"] == 1
    assert gate["observed"]["unverified_providers"] == [{
        "field": field,
        "value": sentinel,
        "activity_count": 20,
        "segment_count": 40,
    }]
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )
    assert "synthetic-private-" not in repr(gate)
    assert "2026-01-" not in repr(gate)


def test_mixed_environment_sources_fail_decision_gate_with_aggregate_counts(
) -> None:
    dataset = synthetic_research_dataset()
    sources = (
        "garmin_activity_weather",
        "coros_activity_weather",
        "stryd_activity_weather",
    )
    for index, record in enumerate(dataset["records"]):
        record["activity"]["environment"]["source"] = sources[index % 3]

    report = _validate_modified_synthetic(dataset)

    expected = {
        "source_count": 3,
        "sources": [
            {
                "source": "coros_activity_weather",
                "activity_count": 7,
                "segment_count": 14,
            },
            {
                "source": "garmin_activity_weather",
                "activity_count": 7,
                "segment_count": 14,
            },
            {
                "source": "stryd_activity_weather",
                "activity_count": 6,
                "segment_count": 12,
            },
        ],
    }
    gate = report["gates"]["environment_source_consistency"]
    assert gate["status"] == "fail"
    assert gate["decision_required"] is True
    assert gate["observed"] == expected
    assert report["data_coverage"]["environment_sources"] == expected
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )
    assert "synthetic-private-" not in repr(gate)
    assert "2026-01-" not in repr(gate)


def test_same_day_date_only_recovery_is_not_pre_activity() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        record["pre_activity_context"]["recovery"]["date"] = (
            record["activity"]["date"]
        )

    report = _validate_modified_synthetic(dataset)

    assert report["gates"]["dated_recovery"]["status"] == "unavailable"
    assert report["gates"]["dated_recovery"]["observed"][
        "usable_dated_readiness_activities"
    ] == 0
    assert {
        omission["predictor"]: omission["reason_code"]
        for omission in report["omissions"]
    }["recovery_readiness_score"] == "missing_context_not_imputed"


@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        ("missing_source", "recovery_source_unavailable"),
        ("unsupported_source", "recovery_source_unsupported"),
        ("wrong_selection", "recovery_selection_unsupported"),
        ("reason_codes", "recovery_reason_codes_present"),
    ],
)
def test_recovery_predictor_requires_supported_clean_provenance(
    mutation: str,
    reason_code: str,
) -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        recovery = record["pre_activity_context"]["recovery"]
        if mutation == "missing_source":
            recovery["source"] = ""
        elif mutation == "unsupported_source":
            recovery["source"] = "unsupported"
        elif mutation == "wrong_selection":
            recovery["selection"] = "latest_available"
        else:
            recovery["reason_codes"] = ["partial_recovery_context"]

    report = _validate_modified_synthetic(dataset)

    coverage = report["data_coverage"]["recovery_readiness"]
    assert coverage["usable_within_maximum_lag_activity_count"] == 0
    assert coverage["provenance_reason_counts"][reason_code] == 20
    assert {
        omission["predictor"]: omission["reason_code"]
        for omission in report["omissions"]
    }["recovery_readiness_score"] == "missing_context_not_imputed"
    assert report["gates"]["dated_recovery"]["decision_required"] is False
    assert report["model"]["status"] == "available"


def test_mixed_training_recovery_sources_omit_readiness_predictor() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"][::2]:
        record["pre_activity_context"]["recovery"]["source"] = "garmin"

    report = _validate_modified_synthetic(dataset)

    assert "recovery_readiness_score" not in report["model"]["predictors"]
    omission = next(
        item
        for item in report["omissions"]
        if item["predictor"] == "recovery_readiness_score"
    )
    assert omission["reason_code"] == (
        "mixed_recovery_source_provenance"
    )
    assert omission["source_counts"] == [
        {
            "source": "garmin",
            "activity_count": 8,
            "segment_count": 16,
        },
        {
            "source": "oura",
            "activity_count": 7,
            "segment_count": 14,
        },
    ]
    gate = report["gates"]["recovery_source_consistency"]
    assert gate["status"] == "fail"
    assert gate["decision_required"] is False
    assert gate["reason_codes"] == [
        "mixed_recovery_source_provenance"
    ]
    assert report["recommendation"]["value"] == (
        "eligible_for_science_review"
    )
    assert "synthetic-private-" not in repr(gate)
    assert "2026-01-" not in repr(gate)


def test_holdout_missing_selected_predictor_rows_are_excluded() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"][-5:]:
        record["pre_activity_context"]["recovery"] = {
            "state": "unavailable",
            "date": None,
            "values": {},
            "reason_codes": ["recovery_unavailable_before_activity"],
        }

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

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

    report = _validate_modified_synthetic(dataset)

    holdout = report["model"]["holdout"]
    assert holdout["train_activity_count"] == 14
    assert holdout["test_activity_count"] == 6
    assert holdout["activity_overlap_count"] == 0


def test_dataset_hash_matches_api_canonical_core_algorithm() -> None:
    dataset = synthetic_research_dataset()

    assert dataset["dataset_hash"] == _api_dataset_hash(dataset)
    changed_timestamp = deepcopy(dataset)
    changed_timestamp["generated_at"] = "2030-12-31T23:59:59Z"
    assert _api_dataset_hash(changed_timestamp) == dataset["dataset_hash"]
    validate_heat_response(changed_timestamp, TEST_CONFIG)


def test_missing_dataset_hash_is_rejected() -> None:
    dataset = synthetic_research_dataset()
    dataset.pop("dataset_hash")

    with pytest.raises(
        HeatValidationInputError,
        match="dataset_hash is required",
    ):
        validate_heat_response(dataset, TEST_CONFIG)


def test_stale_dataset_hash_is_rejected() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"][0]["stable_segments"]["segments"][0][
        "mean_hr_bpm"
    ] += 1.0

    with pytest.raises(
        HeatValidationInputError,
        match="dataset_hash does not match",
    ):
        validate_heat_response(dataset, TEST_CONFIG)


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
        _validate_modified_synthetic(dataset)


def test_nonzero_offset_withholds_as_not_first_page() -> None:
    dataset = synthetic_research_dataset()
    dataset["offset"] = 1
    dataset["records"] = dataset["records"][1:]

    report = _validate_modified_synthetic(dataset)

    assert report["gates"]["first_input_page"]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


@pytest.mark.parametrize("offset", [20, 25])
def test_empty_page_accepts_empty_heat_adaptation_manifest(
    offset: int,
) -> None:
    dataset = synthetic_research_dataset()
    dataset["records"] = []
    dataset["offset"] = offset
    dataset["model_versions"]["heat_adaptation"] = []

    report = _validate_modified_synthetic(dataset)

    assert report["gates"]["first_input_page"]["status"] == "unavailable"
    assert report["gates"]["minimum_activities"]["status"] == "unavailable"
    assert report["model"]["status"] == "unavailable"
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
        _validate_modified_synthetic(dataset)


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
        _validate_modified_synthetic(dataset)


def test_truncated_first_page_is_rejected() -> None:
    dataset = synthetic_research_dataset()
    dataset["records"].pop()

    with pytest.raises(
        HeatValidationInputError,
        match="pagination records are incomplete: expected 20, got 19",
    ):
        _validate_modified_synthetic(dataset)


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
    assert report["gates"]["coefficient_stability"]["status"] == (
        "unavailable"
    )
    assert report["gates"]["coefficient_stability"]["reason_codes"] == [
        "heat_coefficient_stability_unavailable"
    ]
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_permutation_distribution_is_deterministic() -> None:
    first = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )
    second = validate_heat_response(
        synthetic_research_dataset(),
        TEST_CONFIG,
    )

    assert first["negative_control"] == second["negative_control"]
    negative = first["negative_control"]
    assert negative["status"] == "available"
    assert negative["requested_iterations"] == 80
    assert negative["valid_iterations"] == 80
    assert negative["valid_fraction"] == 1.0
    assert negative["validity_estimate"] == {
        "minimum_valid_count": 50,
        "minimum_valid_fraction": 0.8,
        "effective_required_valid_count": 64,
    }
    assert negative["distribution"]["test_mae_bpm"]["minimum"] is not None
    assert negative["method_source"] == (
        "https://doi.org/10.1214/088342304000000396"
    )


def test_failed_permutation_distribution_is_evaluated_fail() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        permutation_iterations=80,
        minimum_holdout_mae_improvement_vs_permuted_bpm=100.0,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        config,
    )

    assert report["negative_control"]["status"] == "available"
    assert report["gates"][
        "permuted_negative_control_falsification"
    ]["status"] == "fail"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_insufficient_permutation_valid_count_is_unavailable() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        permutation_iterations=80,
        minimum_permutation_valid_count=81,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        config,
    )

    assert report["negative_control"]["status"] == "unavailable"
    assert report["negative_control"]["valid_iterations"] == 80
    assert report["negative_control"]["reason_codes"] == [
        "permutation_valid_iterations_insufficient"
    ]
    assert report["gates"][
        "permuted_negative_control_falsification"
    ]["status"] == "unavailable"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_configurable_no_heat_falsification_gate_withholds() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        permutation_iterations=80,
        minimum_holdout_mae_improvement_vs_no_heat_bpm=100.0,
    )

    report = validate_heat_response(
        synthetic_research_dataset(),
        config,
    )

    assert report["gates"][
        "no_heat_baseline_falsification"
    ]["status"] == "fail"
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_insufficient_sensitivity_variant_coverage_withholds() -> None:
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        permutation_iterations=80,
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
    assert report["gates"]["coefficient_stability"]["status"] == (
        "unavailable"
    )
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


def test_temperature_direction_reversal_counts_in_sign_agreement() -> None:
    dataset = synthetic_research_dataset()
    for record in dataset["records"]:
        environment = record["activity"]["environment"]
        environment["temperature_c"] = 50.0 - environment["wet_bulb_c"]
    config = HeatValidationConfig(
        bootstrap_iterations=80,
        permutation_iterations=80,
        minimum_coefficient_sign_agreement=0.90,
    )

    report = _validate_modified_synthetic(dataset, config)

    temperature = next(
        item
        for item in report["sensitivity_analyses"]
        if item["name"] == "temperature_only"
    )
    assert temperature["status"] == "available"
    assert temperature["heat_coefficient_bpm_per_c"] < 0
    stability = report["model"]["heat_stress_coefficient"]["stability"]
    assert stability["sensitivity_direction_variant_count"] == 8
    assert stability[
        "sensitivity_magnitude_comparable_variant_count"
    ] == 7
    assert stability["sensitivity_direction_agreement"] == 0.875
    assert stability["classification"] == (
        "unstable_or_inconclusive_research_estimate"
    )
    assert report["gates"]["coefficient_stability"]["status"] == "fail"
    assert report["gates"]["coefficient_stability"]["reason_codes"] == [
        "heat_coefficient_stability_insufficient"
    ]
    assert report["recommendation"]["value"] == (
        "withhold_personal_estimate"
    )


def test_cp_sensitivity_can_admit_segment_crossing_power_band() -> None:
    dataset = synthetic_research_dataset()
    segment = dataset["records"][0]["stable_segments"]["segments"][0]
    segment["mean_pct_cp"] = 96.0
    segment["mean_power_watts"] = 288.0

    report = _validate_modified_synthetic(dataset)

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
