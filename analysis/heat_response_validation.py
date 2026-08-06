"""Offline, research-only validation of personal heat-response observations.

The module consumes ``activity-research-dataset-v1`` JSON decoded to a Python
dictionary. It never loads athlete data, performs network I/O, or emits
activity identifiers or dates in its report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta
import math
from typing import Any

import numpy as np


INPUT_SCHEMA_VERSION = "activity-research-dataset-v1"
REPORT_SCHEMA_VERSION = "heat-response-validation-report-v1"
MODEL_VERSION = "within-athlete-ridge-mean-hr-v1"
WET_BULB_METHOD = "stull_psychrometric"
ENVIRONMENT_MODEL_VERSION = "environmental-performance-context-v1"
ENVIRONMENT_SCIENCE_DECISION_ID = "sdr-environmental-performance-v1"
STABLE_SEGMENT_MODEL_VERSION = "stable-power-segments-v3"
HEAT_ADAPTATION_MODEL_VERSION = "heat-adaptation-v8"
PRE_ACTIVITY_LOAD_MODEL_VERSION = "banister-pmc-causal-v2"
SUPPORTED_ENVIRONMENT_SOURCES = frozenset({
    "coros_activity_weather",
    "garmin_activity_weather",
    "stryd_activity_weather",
})

_MISMATCH_REASON_CODES = frozenset({
    "critical_power_provider_mismatch",
    "power_provider_alignment_unavailable",
    "power_source_mismatch",
    "power_source_unverified",
    "mixed_providers",
})
_ADAPTATION_EVIDENCE_STAGES = frozenset({
    "building",
    "maintaining",
    "likely_adapted",
    "decaying",
})
_NO_ADAPTATION_EVIDENCE_STAGES = frozenset({
    "insufficient_evidence",
})
_BLOCKING_MODEL_GATES = frozenset({
    "first_input_page",
    "minimum_activities",
    "minimum_segments",
    "chronological_holdout",
    "environmental_spread",
})
_MAX_INPUT_PAGE_LIMIT = 50


class HeatValidationInputError(ValueError):
    """Raised when an offline research dataset has an invalid public shape."""


@dataclass(frozen=True)
class HeatValidationConfig:
    """Configurable research estimates used by the offline validation.

    These defaults are analysis configuration, not accepted product gates.
    """

    # RESEARCH ESTIMATES -- eligibility and stability values are configurable
    # analysis choices, not accepted product gates or physiological constants.
    minimum_activities: int = 12
    minimum_segments: int = 24
    minimum_train_activities: int = 8
    minimum_test_activities: int = 3
    holdout_fraction: float = 0.25
    minimum_environmental_spread_c: float = 5.0
    minimum_holdout_environmental_spread_c: float = 5.0
    minimum_power_pct_cp: float = 65.0
    maximum_power_pct_cp: float = 95.0
    minimum_start_offset_sec: float = 600.0
    minimum_segment_duration_sec: float = 180.0
    minimum_sample_coverage_ratio: float = 0.90
    maximum_power_cv_pct: float = 5.0
    minimum_mean_hr_bpm: float = 40.0
    maximum_mean_hr_bpm: float = 230.0
    minimum_hr_slope_bpm_per_min: float = -20.0
    maximum_hr_slope_bpm_per_min: float = 20.0
    minimum_decoupling_pct: float = -100.0
    maximum_decoupling_pct: float = 100.0
    maximum_mean_pct_cp_error_percentage_points: float = 0.5
    critical_power_sensitivity_fraction: float = 0.05
    minimum_adaptation_group_activities: int = 3
    minimum_dated_recovery_fraction: float = 0.80
    maximum_recovery_lag_days: int = 1
    minimum_sensitivity_available_count: int = 8
    minimum_sensitivity_available_fraction: float = 0.80
    minimum_coefficient_sign_agreement: float = 0.80
    maximum_holdout_mae_bpm: float = 10.0
    minimum_holdout_mae_improvement_vs_no_heat_bpm: float = 0.0
    minimum_holdout_mae_improvement_vs_permuted_bpm: float = 0.0
    ridge_alpha: float = 4.0
    bootstrap_iterations: int = 300
    minimum_bootstrap_valid_resamples: int = 50
    minimum_bootstrap_valid_fraction: float = 0.80
    random_seed: int = 523
    eligible_activity_types: tuple[str, ...] = (
        "run",
        "running",
        "trail_run",
        "trail_running",
        "trail running",
    )


@dataclass(frozen=True)
class _SegmentRow:
    activity_key: str
    activity_order: int
    activity_date: date
    mean_hr_bpm: float
    mean_power_watts: float
    mean_pct_cp: float
    critical_power_watts: float
    start_offset_min: float
    duration_min: float
    wet_bulb_c: float
    temperature_c: float
    terrain_gain_m_per_km: float | None
    pre_activity_tsb: float | None
    recovery_readiness_score: float | None
    adaptation_evidence: float | None


@dataclass(frozen=True)
class _Flattened:
    rows: tuple[_SegmentRow, ...]
    input_record_count: int
    input_segment_count: int
    activity_reason_counts: dict[str, int]
    segment_reason_counts: dict[str, int]
    recovery_usable_activity_count: int
    recovery_dated_activity_count: int
    recovery_observed_lag_days: tuple[int, ...]
    adaptation_known_activity_count: int
    input_total: int
    input_limit: int
    input_offset: int
    first_input_page: bool


@dataclass(frozen=True)
class _Fit:
    feature_names: tuple[str, ...]
    coefficients: np.ndarray
    intercept: float
    train_predictions: np.ndarray
    test_predictions: np.ndarray


def validate_heat_response(
    dataset: dict[str, Any],
    config: HeatValidationConfig | None = None,
) -> dict[str, Any]:
    """Return a deterministic, privacy-safe heat-response validation report.

    The analysis fits a regularized within-athlete linear model to mean heart
    rate in SAMPLE-derived stable-power segments. All thresholds are explicitly
    labeled research estimates. The result can recommend science review, but
    can never recommend shipping a personal estimate.
    """
    selected = config or HeatValidationConfig()
    _validate_config(selected)
    _validate_dataset(dataset)
    flattened = _flatten_dataset(dataset, selected)
    primary = _analyze_rows(
        flattened,
        selected,
        heat_representation="wet_bulb_c",
        include_bootstrap=True,
    )
    sensitivities = _sensitivity_analyses(dataset, selected)
    negative_control = _negative_control(
        selected,
        primary,
    )
    _add_sensitivity_stability(primary, sensitivities, selected)
    _add_falsification_gates(primary, negative_control, selected)
    model = primary["model"]
    stability = (
        model["heat_stress_coefficient"]["stability"]
        if model["status"] == "available"
        else None
    )
    primary["gates"]["coefficient_stability"] = _gate(
        (
            stability is not None
            and stability["classification"]
            == "directionally_stable_research_estimate"
        ),
        observed=stability,
        estimate={
            "minimum_bootstrap_and_sensitivity_sign_agreement":
                selected.minimum_coefficient_sign_agreement,
            "minimum_sensitivity_available_count":
                selected.minimum_sensitivity_available_count,
            "minimum_sensitivity_available_fraction":
                selected.minimum_sensitivity_available_fraction,
        },
        reason_code="heat_coefficient_stability_insufficient",
        decision_required=True,
    )
    exploratory_adaptation = _exploratory_adaptation_analysis(
        primary,
        selected,
    )

    required_gates = [
        gate
        for gate in primary["gates"].values()
        if gate["decision_required"]
    ]
    gates_pass = all(gate["status"] == "pass" for gate in required_gates)
    model_available = model["status"] == "available"
    recommendation_value = (
        "eligible_for_science_review"
        if gates_pass and model_available
        else "withhold_personal_estimate"
    )
    recommendation_reasons = [
        name
        for name, gate in primary["gates"].items()
        if gate["decision_required"] and gate["status"] != "pass"
    ]
    if not model_available:
        recommendation_reasons.append("primary_model_unavailable")

    limitations = [
        "research_only_not_product_validation",
        "stull_psychrometric_wet_bulb_proxy_is_not_wbgt",
        "wind_solar_radiation_clothing_and_hydration_are_unobserved",
        "regularized_association_is_not_a_causal_personal_correction",
        "activity_level_weather_does_not_capture_within_activity_exposure",
        "private_athlete_run_human_science_review_and_superseding_sdr_required",
        "no_user_facing_api_or_ui_authorized",
    ]
    if primary["gates"]["dated_recovery"]["status"] != "pass":
        limitations.append("dated_recovery_context_incomplete")
    if exploratory_adaptation["status"] != "available":
        limitations.append(
            "exploratory_heat_adaptation_evaluation_unavailable"
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": "research_only",
        "purpose": (
            "Offline validation of whether SAMPLE-derived steady-segment "
            "heart rate contains a reviewable within-athlete heat association."
        ),
        "input_contract": {
            "schema_version": INPUT_SCHEMA_VERSION,
            "model_versions": {
                "stable_segments": STABLE_SEGMENT_MODEL_VERSION,
                "environment": ENVIRONMENT_MODEL_VERSION,
                "pre_activity_load": PRE_ACTIVITY_LOAD_MODEL_VERSION,
                "heat_adaptation": HEAT_ADAPTATION_MODEL_VERSION,
            },
            "raw_records_included": False,
            "activity_ids_included": False,
            "activity_dates_included": False,
        },
        "research_configuration": _configuration_report(selected),
        "methodology": {
            "wet_bulb_proxy": {
                "method": WET_BULB_METHOD,
                "classification": "published_proxy_not_wbgt",
                "source": "https://doi.org/10.1175/JAMC-D-11-0143.1",
            },
            "regularization": {
                "method": "ridge_regression",
                "classification": "research_method_choice",
                "source": "https://doi.org/10.1080/00401706.1970.10488634",
            },
            "uncertainty": {
                "method": "fixed_seed_activity_cluster_bootstrap_percentile_interval",
                "classification": "research_method_choice",
                "source": (
                    "https://doi.org/10.1017/CBO9780511802843"
                ),
                "claim_limit": (
                    "Descriptive 2.5th-to-97.5th percentile sensitivity "
                    "interval only; not an accepted coverage guarantee or "
                    "product confidence interval."
                ),
            },
            "eligibility_falsification": {
                "classification": (
                    "configurable_research_falsification_choices_"
                    "not_physiology_claims"
                ),
                "comparators": [
                    "otherwise_identical_no_heat_baseline",
                    "activity_level_permuted_environment_negative_control",
                ],
            },
        },
        "data_coverage": primary["data_coverage"],
        "exclusions": primary["exclusions"],
        "gates": primary["gates"],
        "model": primary["model"],
        "sensitivity_analyses": sensitivities,
        "negative_control": negative_control,
        "exploratory_analyses": {
            "heat_adaptation_secondary_model":
                exploratory_adaptation,
        },
        "limitations": limitations,
        "omissions": primary["omissions"],
        "recommendation": {
            "issue": "#444",
            "value": recommendation_value,
            "reason_codes": sorted(set(recommendation_reasons)),
            "meaning": (
                "A research handoff only; it is not validation success, an "
                "accepted science lifecycle change, or permission to ship."
            ),
            "next_steps": [
                "Run this pipeline on the consented private athlete export.",
                "Review diagnostics and assumptions with a human science reviewer.",
                "Draft and accept a superseding SDR before any API or UI work.",
            ],
        },
    }


def render_heat_response_markdown(report: dict[str, Any]) -> str:
    """Render a validation report as privacy-safe research Markdown."""
    coverage = report["data_coverage"]
    recovery_coverage = coverage["recovery_readiness"]
    model = report["model"]
    recommendation = report["recommendation"]
    lines = [
        "# Heat-response validation report",
        "",
        "**Mode:** Research-only/offline. This report does not authorize a "
        "personal estimate or product change.",
        "",
        "## Purpose",
        "",
        report["purpose"],
        "",
        "The primary heat input is the versioned Stull psychrometric wet-bulb "
        "proxy. It is **not WBGT**.",
        "",
        "## Data coverage",
        "",
        f"- Input activities: {coverage['input_activity_count']}",
        f"- Input stable segments: {coverage['input_segment_count']}",
        f"- Eligible activities: {coverage['eligible_activity_count']}",
        f"- Eligible SAMPLE segments: {coverage['eligible_segment_count']}",
        (
            "- Wet-bulb activity spread: "
            f"{_display(coverage['wet_bulb_activity_spread_c'])} °C"
        ),
        (
            "- Recovery readiness within configured lag: "
            f"{recovery_coverage['usable_within_maximum_lag_activity_count']}"
            f"/{recovery_coverage['eligible_activity_count']} activities; "
            "observed lag days "
            f"{_display(recovery_coverage['observed_lag_days'])}"
        ),
        "",
        "## Research gates",
        "",
        "| Gate | Status | Observed | Research estimate |",
        "|---|---|---:|---:|",
    ]
    for name, gate in report["gates"].items():
        lines.append(
            f"| `{name}` | {gate['status']} | "
            f"{_display(gate['observed'])} | "
            f"{_display(gate['research_estimate'])} |"
        )

    lines.extend(["", "## Model and chronological holdout", ""])
    if model["status"] == "available":
        holdout = model["holdout"]
        performance = model["performance"]
        heat = model["heat_stress_coefficient"]
        lines.extend([
            (
                f"- Train: {holdout['train_activity_count']} activities / "
                f"{holdout['train_segment_count']} segments"
            ),
            (
                f"- Test: {holdout['test_activity_count']} activities / "
                f"{holdout['test_segment_count']} segments"
            ),
            (
                "- Activity overlap across train/test: "
                f"{holdout['activity_overlap_count']}"
            ),
            (
                "- Evaluated holdout environmental spread: "
                f"{_display(holdout['evaluated_environmental_spread_c'])} "
                "°C"
            ),
            (
                f"- Test MAE / RMSE: "
                f"{_display(performance['test']['mae_bpm'])} / "
                f"{_display(performance['test']['rmse_bpm'])} bpm"
            ),
            (
                "- Wet-bulb coefficient "
                f"({heat['reference_group']}): "
                f"{_display(heat['estimate_bpm_per_c'])} bpm/°C "
                f"(cluster-bootstrap 2.5th–97.5th percentile interval "
                f"{_display(heat['uncertainty_interval_bpm_per_c'][0])} to "
                f"{_display(heat['uncertainty_interval_bpm_per_c'][1])})"
            ),
            (
                "- Coefficient stability: "
                f"{heat['stability']['classification']}"
            ),
            (
                "- Otherwise-identical no-heat baseline test MAE: "
                f"{_display(model['falsification_controls']['no_heat_baseline']['test_mae_bpm'])} "
                "bpm"
            ),
        ])
        if holdout["excluded_test_segment_count"]:
            lines.append(
                "- Held-out rows excluded for selected-predictor "
                f"completeness: {holdout['excluded_test_segment_count']} "
                "segments across "
                f"{holdout['excluded_test_activity_count']} activities."
            )
    else:
        lines.append(
            "- Unavailable: "
            + ", ".join(model.get("reason_codes", []))
        )

    lines.extend(["", "## Sensitivity analyses", ""])
    for item in report["sensitivity_analyses"]:
        if item["status"] == "available":
            lines.append(
                f"- **{item['name']}**: "
                f"{_display(item['heat_coefficient_bpm_per_c'])} bpm/°C; "
                f"test MAE {_display(item['test_mae_bpm'])} bpm."
            )
        else:
            lines.append(
                f"- **{item['name']}**: unavailable "
                f"({', '.join(item['reason_codes'])})."
            )

    negative = report["negative_control"]
    lines.extend(["", "## Negative control", ""])
    if negative["status"] == "available":
        lines.append(
            "Environmental exposure was permuted at the activity level with "
            f"fixed seed {negative['random_seed']}. The permuted heat "
            f"coefficient was "
            f"{_display(negative['heat_coefficient_bpm_per_c'])} bpm/°C "
            f"with test MAE {_display(negative['test_mae_bpm'])} bpm."
        )
    else:
        lines.append(
            "Unavailable: " + ", ".join(negative["reason_codes"])
        )

    exploratory = report["exploratory_analyses"][
        "heat_adaptation_secondary_model"
    ]
    lines.extend(["", "## Exploratory heat-adaptation sensitivity", ""])
    if exploratory["status"] == "available":
        lines.append(
            "Available as a secondary heterogeneity sensitivity only. It is "
            "not part of the primary model or eligibility recommendation, "
            "and its coefficient must not be interpreted as an adaptation "
            "benefit or acute-heat discount."
        )
        lines.append(
            "- Exploratory heat-by-stage interaction: "
            f"{_display(exploratory['interaction_estimate_bpm_per_c'])} "
            "bpm/°C."
        )
    else:
        lines.append(
            "Unavailable: " + ", ".join(exploratory["reason_codes"])
        )

    lines.extend(["", "## Limitations and omissions", ""])
    for limitation in report["limitations"]:
        lines.append(f"- `{limitation}`")
    for omission in report["omissions"]:
        lines.append(
            f"- Omitted `{omission['predictor']}`: "
            f"`{omission['reason_code']}`."
        )

    lines.extend([
        "",
        "## #444 recommendation",
        "",
        f"**{recommendation['value']}**",
        "",
        recommendation["meaning"],
        "",
    ])
    for step in recommendation["next_steps"]:
        lines.append(f"- {step}")
    return "\n".join(lines).rstrip() + "\n"


def _validate_config(config: HeatValidationConfig) -> None:
    numeric_positive = (
        config.minimum_activities,
        config.minimum_segments,
        config.minimum_train_activities,
        config.minimum_test_activities,
        config.minimum_environmental_spread_c,
        config.minimum_holdout_environmental_spread_c,
        config.minimum_segment_duration_sec,
        config.minimum_sample_coverage_ratio,
        config.maximum_power_cv_pct,
        config.maximum_mean_pct_cp_error_percentage_points,
        config.critical_power_sensitivity_fraction,
        config.minimum_adaptation_group_activities,
        config.maximum_recovery_lag_days,
        config.minimum_sensitivity_available_count,
        config.minimum_coefficient_sign_agreement,
        config.maximum_holdout_mae_bpm,
        config.ridge_alpha,
        config.bootstrap_iterations,
        config.minimum_bootstrap_valid_resamples,
    )
    if any(value <= 0 for value in numeric_positive):
        raise ValueError("Heat validation research configuration must be positive")
    if not 0 < config.holdout_fraction < 1:
        raise ValueError("holdout_fraction must be between zero and one")
    if not 0 < config.minimum_dated_recovery_fraction <= 1:
        raise ValueError(
            "minimum_dated_recovery_fraction must be between zero and one"
        )
    if not 0 < config.minimum_sensitivity_available_fraction <= 1:
        raise ValueError(
            "minimum_sensitivity_available_fraction must be between "
            "zero and one"
        )
    if not 0 < config.minimum_coefficient_sign_agreement <= 1:
        raise ValueError(
            "minimum_coefficient_sign_agreement must be between zero and one"
        )
    if not 0 < config.minimum_bootstrap_valid_fraction <= 1:
        raise ValueError(
            "minimum_bootstrap_valid_fraction must be between zero and one"
        )
    if not 0 < config.critical_power_sensitivity_fraction < 1:
        raise ValueError(
            "critical_power_sensitivity_fraction must be between zero and one"
        )
    if config.minimum_power_pct_cp >= config.maximum_power_pct_cp:
        raise ValueError("Power-band lower bound must be below upper bound")
    if config.minimum_mean_hr_bpm >= config.maximum_mean_hr_bpm:
        raise ValueError("Heart-rate lower bound must be below upper bound")
    if (
        config.minimum_hr_slope_bpm_per_min
        >= config.maximum_hr_slope_bpm_per_min
    ):
        raise ValueError("HR-slope lower bound must be below upper bound")
    if config.minimum_decoupling_pct >= config.maximum_decoupling_pct:
        raise ValueError("Decoupling lower bound must be below upper bound")
    if (
        config.minimum_holdout_mae_improvement_vs_no_heat_bpm < 0
        or config.minimum_holdout_mae_improvement_vs_permuted_bpm < 0
    ):
        raise ValueError(
            "Minimum falsification improvements cannot be negative"
        )
    integer_config = {
        "maximum_recovery_lag_days": config.maximum_recovery_lag_days,
        "minimum_sensitivity_available_count":
            config.minimum_sensitivity_available_count,
    }
    for name, value in integer_config.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be a positive integer")


def _validate_dataset(dataset: dict[str, Any]) -> None:
    if not isinstance(dataset, dict):
        raise HeatValidationInputError("Input must be one decoded JSON object")
    if dataset.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise HeatValidationInputError(
            f"Input schema must be {INPUT_SCHEMA_VERSION}"
        )
    records = dataset.get("records")
    if not isinstance(records, list):
        raise HeatValidationInputError("Input records must be a JSON array")
    pagination: dict[str, int] = {}
    for name in ("total", "limit", "offset"):
        value = dataset.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise HeatValidationInputError(
                f"Input pagination {name} must be an integer"
            )
        pagination[name] = value
    total = pagination["total"]
    limit = pagination["limit"]
    offset = pagination["offset"]
    if total < 0:
        raise HeatValidationInputError(
            "Input pagination total must be non-negative"
        )
    if not 1 <= limit <= _MAX_INPUT_PAGE_LIMIT:
        raise HeatValidationInputError(
            "Input pagination limit must be between 1 and 50"
        )
    if offset < 0:
        raise HeatValidationInputError(
            "Input pagination offset must be non-negative"
        )
    expected_records = min(limit, max(total - offset, 0))
    if len(records) != expected_records:
        raise HeatValidationInputError(
            "Input pagination records are incomplete: "
            f"expected {expected_records}, got {len(records)}"
        )
    versions = dataset.get("model_versions")
    if not isinstance(versions, dict):
        raise HeatValidationInputError("Input model_versions must be an object")
    if versions.get("environment") != ENVIRONMENT_MODEL_VERSION:
        raise HeatValidationInputError(
            "Input environment model version is unsupported"
        )
    stable_version = versions.get("stable_segments")
    if stable_version != STABLE_SEGMENT_MODEL_VERSION:
        raise HeatValidationInputError(
            "Input stable-segment model version is unsupported"
        )
    if versions.get("pre_activity_load") != PRE_ACTIVITY_LOAD_MODEL_VERSION:
        raise HeatValidationInputError(
            "Input pre-activity load model version is unsupported"
        )
    heat_versions = versions.get("heat_adaptation")
    if (
        not isinstance(heat_versions, list)
        or HEAT_ADAPTATION_MODEL_VERSION not in heat_versions
    ):
        raise HeatValidationInputError(
            "Input heat-adaptation model version is unsupported"
        )


def _flatten_dataset(
    dataset: dict[str, Any],
    config: HeatValidationConfig,
    *,
    critical_power_multiplier: float = 1.0,
) -> _Flattened:
    rows: list[_SegmentRow] = []
    activity_reasons: Counter[str] = Counter()
    segment_reasons: Counter[str] = Counter()
    input_segments = 0
    recovery_usable_keys: set[str] = set()
    recovery_lag_by_key: dict[str, int] = {}
    adaptation_known_keys: set[str] = set()
    eligible_activity_keys: set[str] = set()
    seen_activity_keys: set[str] = set()

    for activity_order, record_value in enumerate(dataset["records"]):
        if not isinstance(record_value, dict):
            activity_reasons["record_not_object"] += 1
            continue
        record = record_value
        activity = record.get("activity")
        stable = record.get("stable_segments")
        context = record.get("pre_activity_context")
        if not isinstance(activity, dict):
            activity_reasons["activity_contract_missing"] += 1
            continue
        if not isinstance(stable, dict):
            activity_reasons["stable_segment_contract_missing"] += 1
            continue
        if not isinstance(context, dict):
            activity_reasons["pre_activity_context_missing"] += 1
            continue

        activity_id = _text(activity.get("activity_id"))
        source = _text(activity.get("source"))
        activity_date = _date_value(activity.get("date"))
        environment = activity.get("environment")
        coverage = activity.get("sample_coverage")
        activity_type = _text(activity.get("activity_type"))
        segments_value = stable.get("segments")
        segments = segments_value if isinstance(segments_value, list) else []
        input_segments += len(segments)

        reasons: list[str] = []
        if activity_id is None or source is None:
            reasons.append("activity_identity_missing")
            activity_key = ""
        else:
            activity_key = f"{source.casefold()}|{activity_id}"
            if activity_key in seen_activity_keys:
                activity_reasons["duplicate_activity_identity"] += 1
                continue
            seen_activity_keys.add(activity_key)
        if activity_date is None:
            reasons.append("activity_date_missing_or_invalid")
        if (
            activity_type is None
            or activity_type.casefold() not in config.eligible_activity_types
        ):
            reasons.append("activity_type_not_eligible")
        if not isinstance(environment, dict):
            reasons.append("environment_contract_missing")
        else:
            if environment.get("state") != "available":
                reasons.append("environment_unavailable")
            if (
                environment.get("model_version")
                != ENVIRONMENT_MODEL_VERSION
            ):
                reasons.append("environment_model_version_mismatch")
            if environment.get("science_decision_id") is None:
                reasons.append(
                    "environment_science_decision_id_missing"
                )
            elif (
                environment.get("science_decision_id")
                != ENVIRONMENT_SCIENCE_DECISION_ID
            ):
                reasons.append(
                    "environment_science_decision_id_mismatch"
                )
            if environment.get("wet_bulb_method") != WET_BULB_METHOD:
                reasons.append("wet_bulb_method_unsupported")
            environment_source = _text(environment.get("source"))
            if environment_source is None:
                reasons.append("environment_source_unavailable")
            elif (
                environment_source.casefold()
                not in SUPPORTED_ENVIRONMENT_SOURCES
            ):
                reasons.append("environment_source_unsupported")
            if _number(environment.get("temperature_c")) is None:
                reasons.append("temperature_missing_or_invalid")
            if _number(environment.get("relative_humidity_pct")) is None:
                reasons.append("relative_humidity_missing_or_invalid")
            if _number(environment.get("wet_bulb_c")) is None:
                reasons.append("wet_bulb_missing_or_invalid")
            environment_reason_codes = environment.get("reason_codes")
            if (
                isinstance(environment_reason_codes, list)
                and any(environment_reason_codes)
            ):
                reasons.append("environment_reason_codes_present")

        activity_coverage = (
            _number(coverage.get("sample_coverage_ratio"))
            if isinstance(coverage, dict)
            else None
        )
        if activity_coverage is None:
            reasons.append("activity_sample_coverage_missing")
        elif activity_coverage < config.minimum_sample_coverage_ratio:
            reasons.append("activity_sample_coverage_low")

        if stable.get("source") != "samples":
            reasons.append("split_fallback_excluded")
        if stable.get("status") != "available":
            reasons.append("stable_segments_unavailable")
        if stable.get("model_version") != STABLE_SEGMENT_MODEL_VERSION:
            reasons.append("stable_segment_model_version_mismatch")
        cp_failures, critical_power, critical_power_provider = (
            _critical_power_context(
                context.get("critical_power"),
                activity_date,
            )
        )
        reasons.extend(cp_failures)

        for reason in sorted(set(reasons)):
            activity_reasons[reason] += 1
        if (
            reasons
            or activity_date is None
            or not isinstance(environment, dict)
            or critical_power is None
            or critical_power_provider is None
        ):
            continue

        wet_bulb = _number(environment.get("wet_bulb_c"))
        temperature = _number(environment.get("temperature_c"))
        if wet_bulb is None or temperature is None:
            continue

        terrain = _terrain_gain(activity)
        load = context.get("load")
        tsb = _load_context(load, activity_date)
        recovery = context.get("recovery")
        recovery_usable, readiness, recovery_lag_days = _recovery_context(
            recovery,
            activity_date,
            maximum_lag_days=config.maximum_recovery_lag_days,
        )
        if recovery_lag_days is not None:
            recovery_lag_by_key[activity_key] = recovery_lag_days
        if recovery_usable:
            recovery_usable_keys.add(activity_key)
        adaptation = context.get("heat_adaptation")
        adaptation_value = _adaptation_context(
            adaptation,
            activity_date,
        )
        if adaptation_value is not None:
            adaptation_known_keys.add(activity_key)

        for segment_value in segments:
            if not isinstance(segment_value, dict):
                segment_reasons["segment_not_object"] += 1
                continue
            segment = segment_value
            segment_failures = _segment_failures(
                segment,
                config,
                critical_power_watts=critical_power,
                critical_power_provider=critical_power_provider,
                critical_power_multiplier=critical_power_multiplier,
            )
            if segment_failures:
                for reason in segment_failures:
                    segment_reasons[reason] += 1
                continue
            mean_hr = _number(segment.get("mean_hr_bpm"))
            mean_power = _number(segment.get("mean_power_watts"))
            mean_pct_cp = _number(segment.get("mean_pct_cp"))
            start_offset = _number(segment.get("start_offset_sec"))
            duration = _number(segment.get("duration_sec"))
            if (
                mean_hr is None
                or mean_power is None
                or mean_pct_cp is None
                or start_offset is None
                or duration is None
            ):
                continue
            adjusted_critical_power = (
                critical_power * critical_power_multiplier
            )
            adjusted_mean_pct_cp = (
                mean_power / adjusted_critical_power * 100.0
            )
            rows.append(_SegmentRow(
                activity_key=activity_key,
                activity_order=activity_order,
                activity_date=activity_date,
                mean_hr_bpm=mean_hr,
                mean_power_watts=mean_power,
                mean_pct_cp=adjusted_mean_pct_cp,
                critical_power_watts=adjusted_critical_power,
                start_offset_min=start_offset / 60.0,
                duration_min=duration / 60.0,
                wet_bulb_c=wet_bulb,
                temperature_c=temperature,
                terrain_gain_m_per_km=terrain,
                pre_activity_tsb=tsb,
                recovery_readiness_score=readiness,
                adaptation_evidence=adaptation_value,
            ))
            eligible_activity_keys.add(activity_key)

    first_input_page = dataset["offset"] == 0
    eligible_recovery_lags = tuple(sorted(
        recovery_lag_by_key[key]
        for key in eligible_activity_keys
        if key in recovery_lag_by_key
    ))
    return _Flattened(
        rows=tuple(rows),
        input_record_count=len(dataset["records"]),
        input_segment_count=input_segments,
        activity_reason_counts=dict(sorted(activity_reasons.items())),
        segment_reason_counts=dict(sorted(segment_reasons.items())),
        recovery_usable_activity_count=len(
            recovery_usable_keys & eligible_activity_keys
        ),
        recovery_dated_activity_count=len(eligible_recovery_lags),
        recovery_observed_lag_days=eligible_recovery_lags,
        adaptation_known_activity_count=len(
            adaptation_known_keys & eligible_activity_keys
        ),
        input_total=dataset["total"],
        input_limit=dataset["limit"],
        input_offset=dataset["offset"],
        first_input_page=first_input_page,
    )


def _critical_power_context(
    critical_power: Any,
    activity_date: date | None,
) -> tuple[list[str], float | None, str | None]:
    failures: list[str] = []
    if not isinstance(critical_power, dict):
        return ["critical_power_contract_missing"], None, None
    if critical_power.get("state") != "available":
        failures.append("critical_power_unavailable")
    value = _number(critical_power.get("value_watts"))
    if value is None or value <= 0:
        failures.append("critical_power_value_missing_or_invalid")
    effective_date = _date_value(critical_power.get("effective_date"))
    if (
        effective_date is None
        or activity_date is None
        or effective_date >= activity_date
    ):
        failures.append("critical_power_not_strictly_pre_activity")
    if _text(critical_power.get("source")) is None:
        failures.append("critical_power_source_missing")
    provider = _text(critical_power.get("power_provider"))
    if provider is None:
        failures.append("critical_power_provider_missing")
    selection = critical_power.get("selection")
    if selection is None:
        failures.append("critical_power_selection_missing")
    elif selection != "latest_strictly_before_activity_date":
        failures.append("critical_power_selection_unsupported")
    reason_codes = critical_power.get("reason_codes")
    if isinstance(reason_codes, list) and any(reason_codes):
        failures.append("critical_power_reason_codes_present")
    return sorted(set(failures)), value, provider


def _segment_failures(
    segment: dict[str, Any],
    config: HeatValidationConfig,
    *,
    critical_power_watts: float,
    critical_power_provider: str,
    critical_power_multiplier: float,
) -> list[str]:
    failures: list[str] = []
    if segment.get("source") != "samples":
        failures.append("split_fallback_excluded")
    if segment.get("stability_state") != "evaluated":
        failures.append("segment_stability_not_evaluated")

    reason_codes = segment.get("reason_codes")
    if isinstance(reason_codes, list) and _MISMATCH_REASON_CODES.intersection(
        str(code) for code in reason_codes
    ):
        failures.append("provider_mismatch_reason_code")
    segment_power_provider = _text(segment.get("power_provider"))
    if segment_power_provider is None:
        failures.append("power_provider_missing")
    elif (
        segment_power_provider.casefold()
        != critical_power_provider.casefold()
    ):
        failures.append("critical_power_provider_mismatch")
    if _text(segment.get("heart_rate_provider")) is None:
        failures.append("heart_rate_provider_missing")

    mean_power = _number(segment.get("mean_power_watts"))
    mean_pct_cp = _number(segment.get("mean_pct_cp"))
    mean_hr = _number(segment.get("mean_hr_bpm"))
    start_offset = _number(segment.get("start_offset_sec"))
    duration = _number(segment.get("duration_sec"))
    coverage = _number(segment.get("sample_coverage_ratio"))
    power_cv = _number(segment.get("power_cv_pct"))
    hr_slope = _number(segment.get("hr_slope_bpm_per_min"))
    decoupling = _number(segment.get("hr_at_power_decoupling_pct"))

    if mean_power is None or mean_power <= 0:
        failures.append("power_missing_or_invalid")
    if mean_pct_cp is None or mean_pct_cp <= 0:
        failures.append("mean_pct_cp_missing_or_invalid")
    if mean_power is not None and mean_power > 0 and mean_pct_cp is not None:
        expected_pct_cp = mean_power / critical_power_watts * 100.0
        if (
            abs(mean_pct_cp - expected_pct_cp)
            > config.maximum_mean_pct_cp_error_percentage_points
        ):
            failures.append("mean_pct_cp_critical_power_mismatch")
        assumed_pct_cp = expected_pct_cp / critical_power_multiplier
        if not (
            config.minimum_power_pct_cp
            <= assumed_pct_cp
            <= config.maximum_power_pct_cp
        ):
            failures.append("outside_power_band")
    if mean_hr is None or not (
        config.minimum_mean_hr_bpm
        <= mean_hr
        <= config.maximum_mean_hr_bpm
    ):
        failures.append("mean_hr_missing_or_invalid")
    if start_offset is None or start_offset < 0:
        failures.append("start_offset_missing_or_invalid")
    elif start_offset < config.minimum_start_offset_sec:
        failures.append("warmup_exclusion")
    if duration is None or duration <= 0:
        failures.append("duration_missing_or_invalid")
    elif duration < config.minimum_segment_duration_sec:
        failures.append("segment_duration_too_short")
    if coverage is None:
        failures.append("segment_sample_coverage_missing")
    elif coverage < config.minimum_sample_coverage_ratio:
        failures.append("segment_sample_coverage_low")
    if power_cv is None:
        failures.append("power_stability_missing")
    elif power_cv > config.maximum_power_cv_pct:
        failures.append("power_variability_too_high")
    if hr_slope is None or not (
        config.minimum_hr_slope_bpm_per_min
        <= hr_slope
        <= config.maximum_hr_slope_bpm_per_min
    ):
        failures.append("hr_slope_missing_or_invalid")
    if decoupling is None or not (
        config.minimum_decoupling_pct
        <= decoupling
        <= config.maximum_decoupling_pct
    ):
        failures.append("decoupling_missing_or_invalid")
    return sorted(set(failures))


def _analyze_rows(
    flattened: _Flattened,
    config: HeatValidationConfig,
    *,
    heat_representation: str,
    include_bootstrap: bool,
) -> dict[str, Any]:
    rows = list(flattened.rows)
    activity_keys = sorted({row.activity_key for row in rows})
    train_rows, candidate_test_rows = _chronological_split(rows, config)
    spread_rows = train_rows if train_rows else rows
    spread = _activity_spread(spread_rows, heat_representation)
    recovery_fraction = (
        flattened.recovery_usable_activity_count / len(activity_keys)
        if activity_keys
        else 0.0
    )
    recovery_lags = flattened.recovery_observed_lag_days
    stale_recovery_count = sum(
        lag > config.maximum_recovery_lag_days
        for lag in recovery_lags
    )
    recovery_lag_summary = {
        "minimum": min(recovery_lags) if recovery_lags else None,
        "median": (
            _rounded(float(np.median(recovery_lags)), 2)
            if recovery_lags
            else None
        ),
        "maximum": max(recovery_lags) if recovery_lags else None,
    }
    adaptation_counts = _adaptation_activity_counts(train_rows)
    adaptation_counts["known_all_eligible"] = (
        flattened.adaptation_known_activity_count
    )
    adaptation_counts["unavailable_all_eligible"] = (
        len(activity_keys) - flattened.adaptation_known_activity_count
    )
    initial_train_keys = {row.activity_key for row in train_rows}
    initial_test_keys = {
        row.activity_key for row in candidate_test_rows
    }
    initial_overlap = initial_train_keys & initial_test_keys

    gates = {
        "first_input_page": _gate(
            flattened.first_input_page,
            observed={
                "total": flattened.input_total,
                "limit": flattened.input_limit,
                "offset": flattened.input_offset,
                "record_count": flattened.input_record_count,
                "page_complete": True,
            },
            estimate={"required_offset": 0},
            reason_code="nonzero_offset_dataset_page",
            decision_required=True,
        ),
        "minimum_activities": _gate(
            len(activity_keys) >= config.minimum_activities,
            observed=len(activity_keys),
            estimate=config.minimum_activities,
            reason_code="eligible_activity_count_insufficient",
            decision_required=True,
        ),
        "minimum_segments": _gate(
            len(rows) >= config.minimum_segments,
            observed=len(rows),
            estimate=config.minimum_segments,
            reason_code="eligible_segment_count_insufficient",
            decision_required=True,
        ),
        "chronological_holdout": _gate(
            (
                len(initial_train_keys)
                >= config.minimum_train_activities
                and len(initial_test_keys)
                >= config.minimum_test_activities
                and not initial_overlap
            ),
            observed={
                "train_activities": len(initial_train_keys),
                "test_activities": len(initial_test_keys),
                "activity_overlap_count": len(initial_overlap),
            },
            estimate={
                "minimum_train_activities": config.minimum_train_activities,
                "minimum_test_activities": config.minimum_test_activities,
            },
            reason_code="chronological_holdout_insufficient",
            decision_required=True,
        ),
        "environmental_spread": _gate(
            (
                spread is not None
                and spread >= config.minimum_environmental_spread_c
            ),
            observed=_rounded(spread),
            estimate=config.minimum_environmental_spread_c,
            reason_code="training_environmental_spread_insufficient",
            decision_required=True,
        ),
        "holdout_environmental_spread": _gate(
            False,
            observed={
                "status": "not_evaluated_before_predictor_filtering",
                "heat_representation": heat_representation,
            },
            estimate={
                "minimum_evaluated_holdout_spread_c":
                    config.minimum_holdout_environmental_spread_c,
            },
            reason_code="holdout_environmental_spread_not_evaluated",
            decision_required=True,
        ),
        "heat_adaptation_exploratory_availability": _gate(
            (
                adaptation_counts["evidence"] >=
                config.minimum_adaptation_group_activities
                and adaptation_counts["no_evidence"] >=
                config.minimum_adaptation_group_activities
                and adaptation_counts["unavailable_all_eligible"] == 0
            ),
            observed=adaptation_counts,
            estimate={
                "minimum_activities_per_group":
                    config.minimum_adaptation_group_activities,
            },
            reason_code="heat_adaptation_variation_insufficient",
            decision_required=False,
        ),
        "dated_recovery": _gate(
            recovery_fraction >= config.minimum_dated_recovery_fraction,
            observed={
                "dated_readiness_activities":
                    flattened.recovery_dated_activity_count,
                "usable_dated_readiness_activities":
                    flattened.recovery_usable_activity_count,
                "stale_dated_readiness_activities":
                    stale_recovery_count,
                "eligible_activities": len(activity_keys),
                "fraction": _rounded(recovery_fraction, 4),
                "observed_lag_days": recovery_lag_summary,
            },
            estimate={
                "minimum_fraction":
                    config.minimum_dated_recovery_fraction,
                "maximum_recovery_lag_days":
                    config.maximum_recovery_lag_days,
            },
            reason_code="usable_dated_recovery_missing",
            decision_required=False,
        ),
    }

    coverage = {
        "input_activity_count": flattened.input_record_count,
        "input_segment_count": flattened.input_segment_count,
        "eligible_activity_count": len(activity_keys),
        "eligible_segment_count": len(rows),
        "wet_bulb_activity_spread_c": _rounded(
            _activity_spread(rows, "wet_bulb_c")
        ),
        "temperature_activity_spread_c": _rounded(
            _activity_spread(rows, "temperature_c")
        ),
        "usable_dated_recovery_activity_count":
            flattened.recovery_usable_activity_count,
        "recovery_readiness": {
            "dated_readiness_activity_count":
                flattened.recovery_dated_activity_count,
            "usable_within_maximum_lag_activity_count":
                flattened.recovery_usable_activity_count,
            "stale_dated_readiness_activity_count":
                stale_recovery_count,
            "missing_or_invalid_activity_count": (
                len(activity_keys)
                - flattened.recovery_dated_activity_count
            ),
            "eligible_activity_count": len(activity_keys),
            "usable_coverage_fraction": _rounded(
                recovery_fraction,
                4,
            ),
            "observed_lag_days": recovery_lag_summary,
            "maximum_recovery_lag_days":
                config.maximum_recovery_lag_days,
        },
        "known_heat_adaptation_activity_count":
            flattened.adaptation_known_activity_count,
    }
    exclusions = {
        "excluded_activity_reason_counts":
            flattened.activity_reason_counts,
        "excluded_segment_reason_counts":
            flattened.segment_reason_counts,
        "excluded_holdout_segment_reason_counts": {},
    }
    blockers = [
        name
        for name, gate in gates.items()
        if name in _BLOCKING_MODEL_GATES and gate["status"] != "pass"
    ]
    if blockers:
        return {
            "data_coverage": coverage,
            "exclusions": exclusions,
            "gates": gates,
            "model": {
                "status": "unavailable",
                "model_version": MODEL_VERSION,
                "reason_codes": blockers,
            },
            "omissions": [],
            "_internal": {
                "train_rows": train_rows,
                "test_rows": candidate_test_rows,
                "feature_names": (),
                "heat_center": None,
            },
        }

    feature_names, omissions = _select_features(
        train_rows,
        heat_representation=heat_representation,
    )
    (
        test_rows,
        holdout_exclusion_counts,
        holdout_excluded_activity_count,
    ) = _filter_evaluation_rows(
        candidate_test_rows,
        feature_names,
    )
    exclusions["excluded_holdout_segment_reason_counts"] = (
        holdout_exclusion_counts
    )
    train_keys = {row.activity_key for row in train_rows}
    test_keys = {row.activity_key for row in test_rows}
    overlap = train_keys & test_keys
    holdout_spread = _activity_spread(
        test_rows,
        heat_representation,
    )
    gates["holdout_environmental_spread"] = _gate(
        (
            holdout_spread is not None
            and holdout_spread
            >= config.minimum_holdout_environmental_spread_c
        ),
        observed={
            "heat_representation": heat_representation,
            "candidate_holdout_activity_count": len(initial_test_keys),
            "evaluated_holdout_activity_count": len(test_keys),
            "candidate_holdout_spread_c": _rounded(
                _activity_spread(
                    candidate_test_rows,
                    heat_representation,
                )
            ),
            "evaluated_holdout_spread_c": _rounded(holdout_spread),
        },
        estimate={
            "minimum_evaluated_holdout_spread_c":
                config.minimum_holdout_environmental_spread_c,
        },
        reason_code=(
            "holdout_environmental_spread_insufficient_after_exclusions"
        ),
        decision_required=True,
    )
    gates["chronological_holdout"] = _gate(
        (
            len(train_keys) >= config.minimum_train_activities
            and len(test_keys) >= config.minimum_test_activities
            and not overlap
        ),
        observed={
            "train_activities": len(train_keys),
            "candidate_test_activities": len(initial_test_keys),
            "evaluated_test_activities": len(test_keys),
            "excluded_test_activities":
                holdout_excluded_activity_count,
            "candidate_test_segments": len(candidate_test_rows),
            "evaluated_test_segments": len(test_rows),
            "excluded_test_segments": (
                len(candidate_test_rows) - len(test_rows)
            ),
            "activity_overlap_count": len(overlap),
        },
        estimate={
            "minimum_train_activities": config.minimum_train_activities,
            "minimum_test_activities": config.minimum_test_activities,
        },
        reason_code="chronological_holdout_insufficient_after_exclusions",
        decision_required=True,
    )
    if gates["chronological_holdout"]["status"] != "pass":
        return {
            "data_coverage": coverage,
            "exclusions": exclusions,
            "gates": gates,
            "model": {
                "status": "unavailable",
                "model_version": MODEL_VERSION,
                "reason_codes": ["chronological_holdout"],
                "selected_predictors": list(feature_names),
                "holdout": {
                    "candidate_test_activity_count":
                        len(initial_test_keys),
                    "candidate_test_segment_count":
                        len(candidate_test_rows),
                    "test_activity_count": len(test_keys),
                    "test_segment_count": len(test_rows),
                    "excluded_test_activity_count":
                        holdout_excluded_activity_count,
                    "excluded_test_segment_count": (
                        len(candidate_test_rows) - len(test_rows)
                    ),
                    "evaluated_environmental_spread_c":
                        _rounded(holdout_spread),
                    "exclusion_reason_counts":
                        holdout_exclusion_counts,
                    "activity_overlap_count": len(overlap),
                },
            },
            "omissions": omissions,
            "_internal": {
                "train_rows": train_rows,
                "test_rows": test_rows,
                "feature_names": feature_names,
                "heat_center": None,
            },
        }

    heat_center = float(np.mean([
        _heat_value(row, heat_representation) for row in train_rows
    ]))
    fit = _fit_model(
        train_rows,
        test_rows,
        feature_names,
        heat_representation=heat_representation,
        heat_center=heat_center,
        ridge_alpha=config.ridge_alpha,
    )
    train_metrics = _metrics(
        train_rows,
        fit.train_predictions,
    )
    test_metrics = _metrics(
        test_rows,
        fit.test_predictions,
    )
    coefficient_map = {
        name: float(value)
        for name, value in zip(
            fit.feature_names,
            fit.coefficients,
            strict=True,
        )
    }
    bootstrap = (
        _cluster_bootstrap(
            train_rows,
            feature_names,
            heat_representation=heat_representation,
            heat_center=heat_center,
            config=config,
        )
        if include_bootstrap
        else {}
    )
    heat_name = heat_representation
    heat_estimate = coefficient_map[heat_name]
    heat_samples = bootstrap.get(heat_name, [])
    required_valid_resamples = max(
        config.minimum_bootstrap_valid_resamples,
        int(math.ceil(
            config.bootstrap_iterations
            * config.minimum_bootstrap_valid_fraction
        )),
    )
    bootstrap_sufficient = (
        not include_bootstrap
        or len(heat_samples) >= required_valid_resamples
    )
    if include_bootstrap:
        gates["bootstrap_resample_sufficiency"] = _gate(
            bootstrap_sufficient,
            observed={
                "valid_resamples": len(heat_samples),
                "requested_resamples": config.bootstrap_iterations,
                "valid_fraction": _rounded(
                    len(heat_samples) / config.bootstrap_iterations,
                    4,
                ),
            },
            estimate={
                "minimum_valid_resamples":
                    config.minimum_bootstrap_valid_resamples,
                "minimum_valid_fraction":
                    config.minimum_bootstrap_valid_fraction,
                "effective_required_valid_resamples":
                    required_valid_resamples,
            },
            reason_code="bootstrap_valid_resamples_insufficient",
            decision_required=True,
        )
    heat_interval = (
        _interval(heat_samples)
        if bootstrap_sufficient and include_bootstrap
        else [None, None]
    )
    heat_stability = _coefficient_stability(
        heat_estimate,
        heat_samples if bootstrap_sufficient and include_bootstrap else [],
    )
    no_heat_features = tuple(
        name for name in feature_names if name != heat_representation
    )
    no_heat_fit = _fit_model(
        train_rows,
        test_rows,
        no_heat_features,
        heat_representation=heat_representation,
        heat_center=heat_center,
        ridge_alpha=config.ridge_alpha,
    )
    no_heat_test_metrics = _metrics(
        test_rows,
        no_heat_fit.test_predictions,
    )

    model = {
        "status": "available",
        "model_version": MODEL_VERSION,
        "outcome": "steady_segment_mean_hr_bpm",
        "heat_representation": heat_representation,
        "regularization": {
            "method": "ridge",
            "classification": "research_method_choice",
            "source": "https://doi.org/10.1080/00401706.1970.10488634",
            "alpha": config.ridge_alpha,
            "predictors_standardized_on_training_rows": True,
            "intercept_penalized": False,
        },
        "weighting": "equal_activity_weight_within_partition",
        "predictors": list(feature_names),
        "qualitative_heat_adaptation_used": False,
        "holdout": {
            "method": "latest_activities_chronological_holdout",
            "train_activity_count": len(train_keys),
            "train_segment_count": len(train_rows),
            "candidate_test_activity_count": len(initial_test_keys),
            "candidate_test_segment_count": len(candidate_test_rows),
            "test_activity_count": len(test_keys),
            "test_segment_count": len(test_rows),
            "excluded_test_activity_count":
                holdout_excluded_activity_count,
            "excluded_test_segment_count": (
                len(candidate_test_rows) - len(test_rows)
            ),
            "evaluated_environmental_spread_c":
                _rounded(holdout_spread),
            "exclusion_reason_counts": holdout_exclusion_counts,
            "activity_overlap_count": len(overlap),
        },
        "performance": {
            "train": train_metrics,
            "test": test_metrics,
        },
        "heat_stress_coefficient": {
            "predictor": heat_name,
            "reference_group": "all_eligible_segments",
            "estimate_bpm_per_c": _rounded(heat_estimate),
            "uncertainty_interval_bpm_per_c": heat_interval,
            "uncertainty_method": (
                "training_activity_cluster_bootstrap_fixed_seed"
            ),
            "uncertainty_classification": "research_method_choice",
            "bootstrap_iterations": config.bootstrap_iterations,
            "bootstrap_valid_iterations": len(heat_samples),
            "bootstrap_interval_status": (
                "available"
                if bootstrap_sufficient and include_bootstrap
                else "unavailable"
            ),
            "stability": heat_stability,
        },
        "falsification_controls": {
            "no_heat_baseline": {
                "status": "available",
                "definition": (
                    "Same training rows, held-out rows, predictors, "
                    "regularization, and weighting with only the heat "
                    "predictor removed."
                ),
                "predictors": list(no_heat_features),
                "test_mae_bpm": no_heat_test_metrics["mae_bpm"],
                "test_rmse_bpm": no_heat_test_metrics["rmse_bpm"],
            },
        },
        "coefficients": {
            name: _rounded(value)
            for name, value in coefficient_map.items()
        },
        "intercept_bpm": _rounded(fit.intercept),
    }
    return {
        "data_coverage": coverage,
        "exclusions": exclusions,
        "gates": gates,
        "model": model,
        "omissions": omissions,
        "_internal": {
            "train_rows": train_rows,
            "test_rows": test_rows,
            "feature_names": feature_names,
            "heat_center": heat_center,
        },
    }


def _chronological_split(
    rows: list[_SegmentRow],
    config: HeatValidationConfig,
) -> tuple[list[_SegmentRow], list[_SegmentRow]]:
    activities_by_date: dict[date, set[str]] = {}
    for row in rows:
        activities_by_date.setdefault(
            row.activity_date,
            set(),
        ).add(row.activity_key)
    if not activities_by_date:
        return [], []
    activity_count = sum(
        len(keys) for keys in activities_by_date.values()
    )
    test_count = max(
        config.minimum_test_activities,
        int(math.ceil(activity_count * config.holdout_fraction)),
    )
    if test_count >= activity_count:
        return [], list(rows)
    test_keys: set[str] = set()
    for activity_date in sorted(activities_by_date, reverse=True):
        test_keys.update(activities_by_date[activity_date])
        if len(test_keys) >= test_count:
            break
    train_rows = [
        row for row in rows if row.activity_key not in test_keys
    ]
    test_rows = [
        row for row in rows if row.activity_key in test_keys
    ]
    return train_rows, test_rows


def _select_features(
    train_rows: list[_SegmentRow],
    *,
    heat_representation: str,
) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    features = [
        heat_representation,
        "mean_pct_cp",
        "start_offset_min",
        "duration_min",
    ]
    omissions: list[dict[str, Any]] = []
    optional = (
        ("terrain_gain_m_per_km", lambda row: row.terrain_gain_m_per_km),
        ("pre_activity_tsb", lambda row: row.pre_activity_tsb),
        (
            "recovery_readiness_score",
            lambda row: row.recovery_readiness_score,
        ),
    )
    for name, getter in optional:
        missing_activities = {
            row.activity_key for row in train_rows if getter(row) is None
        }
        train_values = [
            getter(row) for row in train_rows if getter(row) is not None
        ]
        if missing_activities:
            omissions.append({
                "predictor": name,
                "reason_code": "missing_context_not_imputed",
                "missing_activity_count": len(missing_activities),
            })
        elif len(set(train_values)) < 2:
            omissions.append({
                "predictor": name,
                "reason_code": "training_variation_insufficient",
                "missing_activity_count": 0,
            })
        else:
            features.append(name)
    return tuple(features), omissions


def _filter_evaluation_rows(
    rows: list[_SegmentRow],
    feature_names: tuple[str, ...],
) -> tuple[list[_SegmentRow], dict[str, int], int]:
    included: list[_SegmentRow] = []
    reasons: Counter[str] = Counter()
    excluded_activity_keys: set[str] = set()
    optional_getters = {
        "terrain_gain_m_per_km":
            lambda row: row.terrain_gain_m_per_km,
        "pre_activity_tsb": lambda row: row.pre_activity_tsb,
        "recovery_readiness_score":
            lambda row: row.recovery_readiness_score,
    }
    for row in rows:
        missing = [
            name
            for name, getter in optional_getters.items()
            if name in feature_names and getter(row) is None
        ]
        if not missing:
            included.append(row)
            continue
        excluded_activity_keys.add(row.activity_key)
        for name in missing:
            reasons[f"selected_predictor_missing:{name}"] += 1
    return (
        included,
        dict(sorted(reasons.items())),
        len(excluded_activity_keys),
    )


def _fit_model(
    train_rows: list[_SegmentRow],
    test_rows: list[_SegmentRow],
    feature_names: tuple[str, ...],
    *,
    heat_representation: str,
    heat_center: float,
    ridge_alpha: float,
) -> _Fit:
    x_train = _design_matrix(
        train_rows,
        feature_names,
        heat_representation=heat_representation,
        heat_center=heat_center,
    )
    x_test = _design_matrix(
        test_rows,
        feature_names,
        heat_representation=heat_representation,
        heat_center=heat_center,
    )
    y_train = np.array(
        [row.mean_hr_bpm for row in train_rows],
        dtype=float,
    )
    train_weights = _activity_weights(train_rows) * len(train_rows)
    means = np.average(x_train, axis=0, weights=train_weights)
    variances = np.average(
        (x_train - means) ** 2,
        axis=0,
        weights=train_weights,
    )
    scales = np.sqrt(variances)
    scales[scales < 1e-9] = 1.0
    train_standard = (x_train - means) / scales
    test_standard = (x_test - means) / scales
    design = np.column_stack((
        np.ones(len(train_standard)),
        train_standard,
    ))
    sqrt_weights = np.sqrt(train_weights)
    weighted_design = design * sqrt_weights[:, None]
    weighted_target = y_train * sqrt_weights
    # Hoerl & Kennard's ridge normal equations; the intercept is unpenalized.
    # https://doi.org/10.1080/00401706.1970.10488634
    penalty = np.eye(design.shape[1], dtype=float) * ridge_alpha
    penalty[0, 0] = 0.0
    normal = weighted_design.T @ weighted_design + penalty
    right = weighted_design.T @ weighted_target
    try:
        beta = np.linalg.solve(normal, right)
    except np.linalg.LinAlgError:
        beta = np.linalg.pinv(normal) @ right
    coefficients = beta[1:] / scales
    intercept = float(beta[0] - np.sum(beta[1:] * means / scales))
    train_predictions = intercept + x_train @ coefficients
    test_predictions = intercept + x_test @ coefficients
    return _Fit(
        feature_names=feature_names,
        coefficients=coefficients,
        intercept=intercept,
        train_predictions=train_predictions,
        test_predictions=test_predictions,
    )


def _design_matrix(
    rows: list[_SegmentRow],
    feature_names: tuple[str, ...],
    *,
    heat_representation: str,
    heat_center: float,
) -> np.ndarray:
    return np.array([
        [
            _feature_value(
                row,
                feature,
                heat_representation=heat_representation,
                heat_center=heat_center,
            )
            for feature in feature_names
        ]
        for row in rows
    ], dtype=float)


def _feature_value(
    row: _SegmentRow,
    feature: str,
    *,
    heat_representation: str,
    heat_center: float,
) -> float:
    if feature in {"wet_bulb_c", "temperature_c"}:
        return _heat_value(row, heat_representation)
    if feature == "mean_pct_cp":
        return row.mean_pct_cp
    if feature == "start_offset_min":
        return row.start_offset_min
    if feature == "duration_min":
        return row.duration_min
    if feature == "terrain_gain_m_per_km":
        return _required(row.terrain_gain_m_per_km)
    if feature == "pre_activity_tsb":
        return _required(row.pre_activity_tsb)
    if feature == "recovery_readiness_score":
        return _required(row.recovery_readiness_score)
    if feature == "adaptation_evidence":
        return _required(row.adaptation_evidence)
    if feature == "heat_x_adaptation":
        return (
            (_heat_value(row, heat_representation) - heat_center)
            * _required(row.adaptation_evidence)
        )
    raise ValueError(f"Unsupported heat validation feature: {feature}")


def _cluster_bootstrap(
    train_rows: list[_SegmentRow],
    feature_names: tuple[str, ...],
    *,
    heat_representation: str,
    heat_center: float,
    config: HeatValidationConfig,
) -> dict[str, list[float]]:
    # Resample whole activities with replacement so within-activity segment
    # dependence is retained: https://doi.org/10.1017/CBO9780511802843
    activity_groups = _ordered_activity_groups(train_rows)
    rng = np.random.default_rng(config.random_seed)
    samples: dict[str, list[float]] = {
        name: [] for name in feature_names
    }
    for _ in range(config.bootstrap_iterations):
        sampled_indices = rng.integers(
            0,
            len(activity_groups),
            size=len(activity_groups),
        )
        sampled_rows: list[_SegmentRow] = []
        for draw, index in enumerate(sampled_indices):
            sampled_rows.extend(
                replace(
                    row,
                    activity_key=f"bootstrap-cluster-{draw}",
                    activity_order=draw,
                )
                for row in activity_groups[int(index)]
            )
        if not sampled_rows:
            continue
        fit = _fit_model(
            sampled_rows,
            sampled_rows,
            feature_names,
            heat_representation=heat_representation,
            heat_center=heat_center,
            ridge_alpha=config.ridge_alpha,
        )
        for name, value in zip(
            feature_names,
            fit.coefficients,
            strict=True,
        ):
            if math.isfinite(float(value)):
                samples[name].append(float(value))
    return samples


def _negative_control(
    config: HeatValidationConfig,
    primary: dict[str, Any],
) -> dict[str, Any]:
    if primary["model"]["status"] != "available":
        return {
            "status": "unavailable",
            "reason_codes": ["primary_model_unavailable"],
            "random_seed": config.random_seed + 1,
        }
    internal = primary["_internal"]
    train_rows = internal["train_rows"]
    test_rows = internal["test_rows"]
    rng = np.random.default_rng(config.random_seed + 1)
    permuted_train = _permute_activity_exposure(train_rows, rng)
    permuted_test = _permute_activity_exposure(test_rows, rng)
    fit = _fit_model(
        permuted_train,
        permuted_test,
        internal["feature_names"],
        heat_representation="wet_bulb_c",
        heat_center=internal["heat_center"],
        ridge_alpha=config.ridge_alpha,
    )
    coefficient = float(fit.coefficients[
        internal["feature_names"].index("wet_bulb_c")
    ])
    primary_coefficient = primary["model"][
        "heat_stress_coefficient"
    ]["estimate_bpm_per_c"]
    ratio = (
        abs(coefficient) / abs(float(primary_coefficient))
        if primary_coefficient not in (None, 0)
        else None
    )
    return {
        "status": "available",
        "method": (
            "permute_environmental_exposure_between_activities_separately_"
            "within_train_and_test"
        ),
        "random_seed": config.random_seed + 1,
        "heat_coefficient_bpm_per_c": _rounded(coefficient),
        "test_mae_bpm": _metrics(
            permuted_test,
            fit.test_predictions,
        )["mae_bpm"],
        "test_rmse_bpm": _metrics(
            permuted_test,
            fit.test_predictions,
        )["rmse_bpm"],
        "absolute_coefficient_ratio_vs_primary": _rounded(ratio),
        "interpretation": (
            "A negative-control diagnostic only. A smaller permuted "
            "coefficient is supportive but does not establish causality or "
            "validate a personal product estimate."
        ),
    }


def _add_falsification_gates(
    primary: dict[str, Any],
    negative_control: dict[str, Any],
    config: HeatValidationConfig,
) -> None:
    model = primary["model"]
    if model["status"] != "available":
        unavailable = (
            ("chronological_holdout_performance", "holdout_performance_unavailable"),
            ("no_heat_baseline_falsification", "no_heat_baseline_unavailable"),
            (
                "permuted_negative_control_falsification",
                "permuted_negative_control_unavailable",
            ),
        )
        for name, reason in unavailable:
            primary["gates"][name] = _gate(
                False,
                observed=None,
                estimate=None,
                reason_code=reason,
                decision_required=True,
                classification=(
                    "research_falsification_choice_not_physiology_claim"
                ),
            )
        return

    primary_mae = model["performance"]["test"]["mae_bpm"]
    no_heat_mae = model["falsification_controls"][
        "no_heat_baseline"
    ]["test_mae_bpm"]
    no_heat_improvement = (
        float(no_heat_mae) - float(primary_mae)
        if no_heat_mae is not None and primary_mae is not None
        else None
    )
    permuted_mae = (
        negative_control.get("test_mae_bpm")
        if negative_control.get("status") == "available"
        else None
    )
    permuted_improvement = (
        float(permuted_mae) - float(primary_mae)
        if permuted_mae is not None and primary_mae is not None
        else None
    )
    classification = (
        "research_falsification_choice_not_physiology_claim"
    )
    primary["gates"]["chronological_holdout_performance"] = _gate(
        (
            primary_mae is not None
            and float(primary_mae) <= config.maximum_holdout_mae_bpm
        ),
        observed={"test_mae_bpm": primary_mae},
        estimate={
            "maximum_holdout_mae_bpm":
                config.maximum_holdout_mae_bpm,
        },
        reason_code="gross_holdout_performance_failure",
        decision_required=True,
        classification=classification,
    )
    primary["gates"]["no_heat_baseline_falsification"] = _gate(
        (
            no_heat_improvement is not None
            and no_heat_improvement
            >= config.minimum_holdout_mae_improvement_vs_no_heat_bpm
        ),
        observed={
            "primary_test_mae_bpm": primary_mae,
            "no_heat_test_mae_bpm": no_heat_mae,
            "improvement_bpm": _rounded(no_heat_improvement),
        },
        estimate={
            "minimum_improvement_bpm":
                config.minimum_holdout_mae_improvement_vs_no_heat_bpm,
        },
        reason_code="no_heat_baseline_not_beaten",
        decision_required=True,
        classification=classification,
    )
    primary["gates"][
        "permuted_negative_control_falsification"
    ] = _gate(
        (
            permuted_improvement is not None
            and permuted_improvement
            >= config.minimum_holdout_mae_improvement_vs_permuted_bpm
        ),
        observed={
            "primary_test_mae_bpm": primary_mae,
            "permuted_test_mae_bpm": permuted_mae,
            "improvement_bpm": _rounded(permuted_improvement),
        },
        estimate={
            "minimum_improvement_bpm":
                config.minimum_holdout_mae_improvement_vs_permuted_bpm,
        },
        reason_code="permuted_negative_control_not_beaten",
        decision_required=True,
        classification=classification,
    )


def _exploratory_adaptation_analysis(
    primary: dict[str, Any],
    config: HeatValidationConfig,
) -> dict[str, Any]:
    gate = primary["gates"].get(
        "heat_adaptation_exploratory_availability"
    )
    if primary["model"]["status"] != "available":
        return {
            "status": "unavailable",
            "role": (
                "exploratory_secondary_model_not_used_by_recommendation"
            ),
            "reason_codes": ["primary_model_unavailable"],
        }
    if gate is None or gate["status"] != "pass":
        return {
            "status": "unavailable",
            "role": (
                "exploratory_secondary_model_not_used_by_recommendation"
            ),
            "reason_codes": ["heat_adaptation_variation_insufficient"],
        }
    internal = primary["_internal"]
    feature_names = tuple(internal["feature_names"]) + (
        "adaptation_evidence",
        "heat_x_adaptation",
    )
    fit = _fit_model(
        internal["train_rows"],
        internal["test_rows"],
        feature_names,
        heat_representation="wet_bulb_c",
        heat_center=internal["heat_center"],
        ridge_alpha=config.ridge_alpha,
    )
    coefficient_map = {
        name: float(value)
        for name, value in zip(
            fit.feature_names,
            fit.coefficients,
            strict=True,
        )
    }
    secondary_metrics = _metrics(
        internal["test_rows"],
        fit.test_predictions,
    )
    primary_mae = primary["model"]["performance"]["test"]["mae_bpm"]
    secondary_mae = secondary_metrics["mae_bpm"]
    return {
        "status": "available",
        "role": (
            "exploratory_secondary_model_not_used_by_recommendation"
        ),
        "primary_model_unchanged": True,
        "cannot_improve_recommendation": True,
        "interpretation_limit": (
            "The qualitative stage interaction is a heterogeneity "
            "sensitivity only. Its sign or magnitude must not be interpreted "
            "as an adaptation benefit or a discount to acute heat response."
        ),
        "adaptation_evidence_stages": sorted(
            _ADAPTATION_EVIDENCE_STAGES
        ),
        "interaction_estimate_bpm_per_c": _rounded(
            coefficient_map["heat_x_adaptation"]
        ),
        "secondary_test_mae_bpm": secondary_mae,
        "secondary_minus_primary_test_mae_bpm": _rounded(
            (
                float(secondary_mae) - float(primary_mae)
                if secondary_mae is not None and primary_mae is not None
                else None
            )
        ),
    }


def _sensitivity_analyses(
    dataset: dict[str, Any],
    config: HeatValidationConfig,
) -> list[dict[str, Any]]:
    variants: tuple[
        tuple[str, HeatValidationConfig, str, dict[str, Any]],
        ...,
    ] = (
        # RESEARCH SENSITIVITY ESTIMATES: these perturbations are method
        # choices, not physiological boundaries or accepted product gates.
        (
            "wider_power_band",
            replace(
                config,
                minimum_power_pct_cp=60.0,
                maximum_power_pct_cp=100.0,
            ),
            "wet_bulb_c",
            {"power_band_pct_cp": [60.0, 100.0]},
        ),
        (
            "narrower_power_band",
            replace(
                config,
                minimum_power_pct_cp=70.0,
                maximum_power_pct_cp=90.0,
            ),
            "wet_bulb_c",
            {"power_band_pct_cp": [70.0, 90.0]},
        ),
        (
            "shorter_warmup_exclusion",
            replace(config, minimum_start_offset_sec=300.0),
            "wet_bulb_c",
            {"minimum_start_offset_sec": 300.0},
        ),
        (
            "longer_warmup_exclusion",
            replace(config, minimum_start_offset_sec=900.0),
            "wet_bulb_c",
            {"minimum_start_offset_sec": 900.0},
        ),
        (
            "shorter_minimum_duration",
            replace(config, minimum_segment_duration_sec=120.0),
            "wet_bulb_c",
            {"minimum_segment_duration_sec": 120.0},
        ),
        (
            "longer_minimum_duration",
            replace(config, minimum_segment_duration_sec=300.0),
            "wet_bulb_c",
            {"minimum_segment_duration_sec": 300.0},
        ),
        (
            "temperature_only",
            config,
            "temperature_c",
            {"heat_representation": "temperature_c"},
        ),
    )
    output: list[dict[str, Any]] = []
    for name, variant_config, representation, changes in variants:
        flattened = _flatten_dataset(dataset, variant_config)
        result = _analyze_rows(
            flattened,
            variant_config,
            heat_representation=representation,
            include_bootstrap=False,
        )
        model = result["model"]
        unavailable_reasons = _sensitivity_unavailability_reasons(
            result
        )
        if not unavailable_reasons:
            output.append({
                "name": name,
                "status": "available",
                "research_configuration_changes": changes,
                "heat_representation": representation,
                "eligible_activity_count":
                    result["data_coverage"]["eligible_activity_count"],
                "eligible_segment_count":
                    result["data_coverage"]["eligible_segment_count"],
                "heat_coefficient_bpm_per_c":
                    model["heat_stress_coefficient"][
                        "estimate_bpm_per_c"
                    ],
                "test_mae_bpm":
                    model["performance"]["test"]["mae_bpm"],
                "test_rmse_bpm":
                    model["performance"]["test"]["rmse_bpm"],
            })
        else:
            output.append({
                "name": name,
                "status": "unavailable",
                "research_configuration_changes": changes,
                "heat_representation": representation,
                "eligible_activity_count":
                    result["data_coverage"]["eligible_activity_count"],
                "eligible_segment_count":
                    result["data_coverage"]["eligible_segment_count"],
                "reason_codes": unavailable_reasons,
            })
    sensitivity_fraction = config.critical_power_sensitivity_fraction
    for name, multiplier in (
        (
            "critical_power_lower_assumption",
            1.0 - sensitivity_fraction,
        ),
        (
            "critical_power_higher_assumption",
            1.0 + sensitivity_fraction,
        ),
    ):
        flattened = _flatten_dataset(
            dataset,
            config,
            critical_power_multiplier=multiplier,
        )
        result = _analyze_rows(
            flattened,
            config,
            heat_representation="wet_bulb_c",
            include_bootstrap=False,
        )
        model = result["model"]
        unavailable_reasons = _sensitivity_unavailability_reasons(
            result
        )
        changes = {
            "critical_power_multiplier": _rounded(multiplier, 4),
            "critical_power_change_pct": _rounded(
                (multiplier - 1.0) * 100.0,
                2,
            ),
        }
        item: dict[str, Any] = {
            "name": name,
            "status": (
                "available"
                if not unavailable_reasons
                else "unavailable"
            ),
            "research_configuration_changes": changes,
            "heat_representation": "wet_bulb_c",
            "eligible_activity_count":
                result["data_coverage"]["eligible_activity_count"],
            "eligible_segment_count":
                result["data_coverage"]["eligible_segment_count"],
        }
        if not unavailable_reasons:
            item.update({
                "heat_coefficient_bpm_per_c":
                    model["heat_stress_coefficient"][
                        "estimate_bpm_per_c"
                    ],
                "test_mae_bpm":
                    model["performance"]["test"]["mae_bpm"],
                "test_rmse_bpm":
                    model["performance"]["test"]["rmse_bpm"],
            })
        else:
            item["reason_codes"] = unavailable_reasons
        output.append(item)
    return output


def _sensitivity_unavailability_reasons(
    result: dict[str, Any],
) -> list[str]:
    reasons = set(result["model"].get("reason_codes", []))
    for gate in result["gates"].values():
        if gate["decision_required"] and gate["status"] != "pass":
            reasons.update(gate["reason_codes"])
    return sorted(reasons)


def _add_sensitivity_stability(
    primary: dict[str, Any],
    sensitivities: list[dict[str, Any]],
    config: HeatValidationConfig,
) -> None:
    planned_count = len(sensitivities)
    available_items = [
        item for item in sensitivities
        if item["status"] == "available"
    ]
    available_count = len(available_items)
    available_fraction = (
        available_count / planned_count
        if planned_count
        else 0.0
    )
    required_count = max(
        config.minimum_sensitivity_available_count,
        int(math.ceil(
            planned_count
            * config.minimum_sensitivity_available_fraction
        )),
    )
    coverage_sufficient = (
        planned_count > 0
        and available_count >= required_count
    )
    coverage_observed = {
        "planned_variant_count": planned_count,
        "available_variant_count": available_count,
        "available_fraction": _rounded(available_fraction, 4),
        "effective_required_available_count": required_count,
        "unavailable_variants": [
            item["name"]
            for item in sensitivities
            if item["status"] != "available"
        ],
    }
    primary["gates"]["sensitivity_analysis_coverage"] = _gate(
        coverage_sufficient,
        observed=coverage_observed,
        estimate={
            "minimum_available_count":
                config.minimum_sensitivity_available_count,
            "minimum_available_fraction":
                config.minimum_sensitivity_available_fraction,
        },
        reason_code="sensitivity_analysis_coverage_insufficient",
        decision_required=True,
    )
    model = primary["model"]
    if model["status"] != "available":
        return
    heat = model["heat_stress_coefficient"]
    estimate = heat["estimate_bpm_per_c"]
    comparable = [
        item["heat_coefficient_bpm_per_c"]
        for item in sensitivities
        if item["status"] == "available"
        and item["heat_representation"] == "wet_bulb_c"
    ]
    if not comparable or estimate == 0:
        agreement = None
    else:
        agreement = sum(
            math.copysign(1.0, value)
            == math.copysign(1.0, estimate)
            for value in comparable
            if value != 0
        ) / len(comparable)
    heat["stability"]["sensitivity_direction_agreement"] = _rounded(
        agreement,
        4,
    )
    heat["stability"]["sensitivity_estimate_range_bpm_per_c"] = (
        [_rounded(min(comparable)), _rounded(max(comparable))]
        if comparable
        else None
    )
    heat["stability"]["sensitivity_coverage"] = coverage_observed
    bootstrap_agreement = heat["stability"][
        "bootstrap_sign_agreement"
    ]
    if not coverage_sufficient:
        classification = (
            "inconclusive_insufficient_sensitivity_coverage"
        )
    elif (
        bootstrap_agreement is not None
        and bootstrap_agreement
        >= config.minimum_coefficient_sign_agreement
        and agreement is not None
        and agreement >= config.minimum_coefficient_sign_agreement
    ):
        classification = "directionally_stable_research_estimate"
    else:
        classification = "unstable_or_inconclusive_research_estimate"
    heat["stability"]["classification"] = classification


def _metrics(
    rows: list[_SegmentRow],
    predictions: np.ndarray,
) -> dict[str, float | None]:
    if not rows:
        return {"mae_bpm": None, "rmse_bpm": None}
    actual = np.array([row.mean_hr_bpm for row in rows], dtype=float)
    weights = _activity_weights(rows)
    errors = predictions - actual
    return {
        "mae_bpm": _rounded(
            float(np.average(np.abs(errors), weights=weights))
        ),
        "rmse_bpm": _rounded(
            float(np.sqrt(np.average(errors ** 2, weights=weights)))
        ),
    }


def _activity_weights(rows: list[_SegmentRow]) -> np.ndarray:
    counts = Counter(row.activity_key for row in rows)
    weights = np.array([
        1.0 / counts[row.activity_key] for row in rows
    ], dtype=float)
    return weights / float(weights.sum())


def _group_rows(
    rows: list[_SegmentRow],
) -> dict[str, list[_SegmentRow]]:
    grouped: dict[str, list[_SegmentRow]] = {}
    for row in rows:
        grouped.setdefault(row.activity_key, []).append(row)
    return grouped


def _ordered_activity_groups(
    rows: list[_SegmentRow],
) -> list[list[_SegmentRow]]:
    """Order clusters without using opaque source activity identifiers."""
    grouped = _group_rows(rows)
    return sorted(
        grouped.values(),
        key=_activity_cluster_order_key,
    )


def _activity_cluster_order_key(
    rows: list[_SegmentRow],
) -> tuple[Any, ...]:
    content = tuple(sorted(
        (
            row.mean_hr_bpm,
            row.mean_power_watts,
            row.mean_pct_cp,
            row.critical_power_watts,
            row.start_offset_min,
            row.duration_min,
            row.wet_bulb_c,
            row.temperature_c,
            _optional_number_order_key(row.terrain_gain_m_per_km),
            _optional_number_order_key(row.pre_activity_tsb),
            _optional_number_order_key(
                row.recovery_readiness_score
            ),
            _optional_number_order_key(row.adaptation_evidence),
        )
        for row in rows
    ))
    return (
        min(row.activity_date for row in rows),
        content,
        min(row.activity_order for row in rows),
    )


def _optional_number_order_key(
    value: float | None,
) -> tuple[int, float]:
    return (1, 0.0) if value is None else (0, value)


def _permute_activity_exposure(
    rows: list[_SegmentRow],
    rng: np.random.Generator,
) -> list[_SegmentRow]:
    groups = _ordered_activity_groups(rows)
    keys = [group[0].activity_key for group in groups]
    exposures = [
        (
            group[0].wet_bulb_c,
            group[0].temperature_c,
        )
        for group in groups
    ]
    permutation = rng.permutation(len(keys))
    mapping = {
        key: exposures[int(permutation[index])]
        for index, key in enumerate(keys)
    }
    return [
        replace(
            row,
            wet_bulb_c=mapping[row.activity_key][0],
            temperature_c=mapping[row.activity_key][1],
        )
        for row in rows
    ]


def _adaptation_activity_counts(
    rows: list[_SegmentRow],
) -> dict[str, int]:
    values = {
        row.activity_key: row.adaptation_evidence for row in rows
    }
    known = [
        value for value in values.values() if value is not None
    ]
    evidence = sum(value >= 0.5 for value in known)
    return {
        "evidence": evidence,
        "no_evidence": len(known) - evidence,
        "unavailable_training": len(values) - len(known),
    }


def _activity_spread(
    rows: list[_SegmentRow],
    representation: str,
) -> float | None:
    values = {
        row.activity_key: _heat_value(row, representation)
        for row in rows
    }
    if len(values) < 2:
        return None
    return max(values.values()) - min(values.values())


def _heat_value(
    row: _SegmentRow,
    representation: str,
) -> float:
    if representation == "wet_bulb_c":
        return row.wet_bulb_c
    if representation == "temperature_c":
        return row.temperature_c
    raise ValueError(f"Unsupported heat representation: {representation}")


def _terrain_gain(activity: dict[str, Any]) -> float | None:
    distance = _number(activity.get("distance_km"))
    elevation = _number(activity.get("elevation_gain_m"))
    if (
        distance is None
        or distance <= 0
        or elevation is None
        or elevation < 0
    ):
        return None
    return elevation / distance


def _recovery_context(
    recovery: Any,
    activity_date: date,
    *,
    maximum_lag_days: int,
) -> tuple[bool, float | None, int | None]:
    if not isinstance(recovery, dict):
        return False, None, None
    recovery_date = _date_value(recovery.get("date"))
    dated = (
        recovery_date is not None
        and recovery_date < activity_date
        and recovery.get("state") in {"available", "partial"}
    )
    values = recovery.get("values")
    readiness = (
        _number(values.get("readiness_score"))
        if dated and isinstance(values, dict)
        else None
    )
    if not dated or readiness is None or recovery_date is None:
        return False, None, None
    lag_days = (activity_date - recovery_date).days
    if lag_days > maximum_lag_days:
        return False, None, lag_days
    return True, readiness, lag_days


def _load_context(
    load: Any,
    activity_date: date,
) -> float | None:
    if not isinstance(load, dict):
        return None
    if load.get("state") not in {"available", "partial"}:
        return None
    if load.get("model_version") != PRE_ACTIVITY_LOAD_MODEL_VERSION:
        return None
    expected_as_of = activity_date - timedelta(days=1)
    if _date_value(load.get("as_of_date")) != expected_as_of:
        return None
    return _number(load.get("tsb"))


def _adaptation_context(
    adaptation: Any,
    activity_date: date,
) -> float | None:
    if not isinstance(adaptation, dict):
        return None
    if adaptation.get("state") not in {"available", "partial"}:
        return None
    if adaptation.get("model_version") != HEAT_ADAPTATION_MODEL_VERSION:
        return None
    expected_as_of = activity_date - timedelta(days=1)
    if _date_value(adaptation.get("as_of_date")) != expected_as_of:
        return None
    stage = _text(adaptation.get("stage"))
    if stage in _ADAPTATION_EVIDENCE_STAGES:
        return 1.0
    if stage in _NO_ADAPTATION_EVIDENCE_STAGES:
        return 0.0
    return None


def _gate(
    passed: bool,
    *,
    observed: Any,
    estimate: Any,
    reason_code: str,
    decision_required: bool,
    classification: str = (
        "research_estimate_not_accepted_product_gate"
    ),
) -> dict[str, Any]:
    return {
        "status": "pass" if passed else "unavailable",
        "observed": observed,
        "research_estimate": estimate,
        "classification": classification,
        "decision_required": decision_required,
        "reason_codes": [] if passed else [reason_code],
    }


def _configuration_report(
    config: HeatValidationConfig,
) -> dict[str, Any]:
    return {
        "classification": "research_estimates_not_accepted_product_gates",
        "minimum_activities": config.minimum_activities,
        "minimum_segments": config.minimum_segments,
        "minimum_train_activities": config.minimum_train_activities,
        "minimum_test_activities": config.minimum_test_activities,
        "holdout_fraction": config.holdout_fraction,
        "minimum_environmental_spread_c":
            config.minimum_environmental_spread_c,
        "minimum_holdout_environmental_spread_c":
            config.minimum_holdout_environmental_spread_c,
        "power_band_pct_cp": [
            config.minimum_power_pct_cp,
            config.maximum_power_pct_cp,
        ],
        "minimum_start_offset_sec": config.minimum_start_offset_sec,
        "minimum_segment_duration_sec":
            config.minimum_segment_duration_sec,
        "minimum_sample_coverage_ratio":
            config.minimum_sample_coverage_ratio,
        "maximum_power_cv_pct": config.maximum_power_cv_pct,
        "mean_hr_bounds_bpm": [
            config.minimum_mean_hr_bpm,
            config.maximum_mean_hr_bpm,
        ],
        "hr_slope_bounds_bpm_per_min": [
            config.minimum_hr_slope_bpm_per_min,
            config.maximum_hr_slope_bpm_per_min,
        ],
        "decoupling_bounds_pct": [
            config.minimum_decoupling_pct,
            config.maximum_decoupling_pct,
        ],
        "maximum_mean_pct_cp_error_percentage_points":
            config.maximum_mean_pct_cp_error_percentage_points,
        "critical_power_sensitivity_fraction":
            config.critical_power_sensitivity_fraction,
        "minimum_adaptation_group_activities":
            config.minimum_adaptation_group_activities,
        "minimum_dated_recovery_fraction":
            config.minimum_dated_recovery_fraction,
        "maximum_recovery_lag_days":
            config.maximum_recovery_lag_days,
        "minimum_sensitivity_available_count":
            config.minimum_sensitivity_available_count,
        "minimum_sensitivity_available_fraction":
            config.minimum_sensitivity_available_fraction,
        "minimum_coefficient_sign_agreement":
            config.minimum_coefficient_sign_agreement,
        "maximum_holdout_mae_bpm":
            config.maximum_holdout_mae_bpm,
        "minimum_holdout_mae_improvement_vs_no_heat_bpm":
            config.minimum_holdout_mae_improvement_vs_no_heat_bpm,
        "minimum_holdout_mae_improvement_vs_permuted_bpm":
            config.minimum_holdout_mae_improvement_vs_permuted_bpm,
        "ridge_alpha": config.ridge_alpha,
        "bootstrap_iterations": config.bootstrap_iterations,
        "minimum_bootstrap_valid_resamples":
            config.minimum_bootstrap_valid_resamples,
        "minimum_bootstrap_valid_fraction":
            config.minimum_bootstrap_valid_fraction,
        "random_seed": config.random_seed,
    }


def _coefficient_stability(
    estimate: float,
    samples: list[float],
) -> dict[str, Any]:
    if not samples or estimate == 0:
        return {
            "bootstrap_sign_agreement": None,
            "bootstrap_median_bpm_per_c": None,
            "bootstrap_iqr_bpm_per_c": None,
            "classification": "unavailable",
        }
    estimate_sign = math.copysign(1.0, estimate)
    sign_agreement = sum(
        value != 0 and math.copysign(1.0, value) == estimate_sign
        for value in samples
    ) / len(samples)
    values = np.array(samples, dtype=float)
    return {
        "bootstrap_sign_agreement": _rounded(sign_agreement, 4),
        "bootstrap_median_bpm_per_c": _rounded(
            float(np.median(values))
        ),
        "bootstrap_iqr_bpm_per_c": [
            _rounded(float(np.percentile(values, 25))),
            _rounded(float(np.percentile(values, 75))),
        ],
        "classification": "pending_sensitivity_analysis",
    }


def _interval(samples: list[float]) -> list[float | None]:
    # Descriptive percentile bounds only, without a coverage guarantee.
    # Bootstrap reference: https://doi.org/10.1017/CBO9780511802843
    if not samples:
        return [None, None]
    values = np.array(samples, dtype=float)
    return [
        _rounded(float(np.percentile(values, 2.5))),
        _rounded(float(np.percentile(values, 97.5))),
    ]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_value(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _required(value: float | None) -> float:
    if value is None:
        raise ValueError("Selected optional predictor is missing")
    return value


def _rounded(
    value: float | None,
    digits: int = 4,
) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _display(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        return ", ".join(
            f"{key}={_display(item)}"
            for key, item in value.items()
        )
    if isinstance(value, list):
        return "–".join(_display(item) for item in value)
    return str(value)
