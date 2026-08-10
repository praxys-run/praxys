"""Pure aggregate analysis for the Labs environmental-response experiment."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np

from analysis.heat_response_validation import (
    HeatValidationConfig,
    MODEL_VERSION,
    _analyze_rows,
    _fit_model,
    _flatten_dataset,
    _prepare_dataset,
    validate_heat_response,
)


LABS_ENVIRONMENT_MODEL_VERSION = f"{MODEL_VERSION}-labs-v3"
POWER_REGIME = "stryd_continuous_samples"
LABS_MODEL_MINIMUM_POWER_PCT_CP = 65.0
LABS_MODEL_MAXIMUM_POWER_PCT_CP = 95.0
# ESTIMATE -- Product guardrails below are governed by the proposed
# data/science/decisions/sdr-environmental-performance-v4.yaml. They are not
# published physiological constants and cannot ship before human acceptance.


@dataclass(frozen=True)
class LabsEnvironmentConfig:
    """Proposed Labs v3 display-support and influence guardrails."""

    curve_domain_percentiles: tuple[float, float] = (10.0, 90.0)
    curve_support_bin_count: int = 5
    minimum_activities_per_curve_bin: int = 5
    minimum_segments_per_curve_bin: int = 10
    reference_power_half_width_percentage_points: float = 10.0
    minimum_reference_power_activities_per_curve_bin: int = 5
    minimum_contiguous_supported_bins: int = 2
    maximum_bootstrap_width_ratio: float = 1.0
    minimum_leave_one_out_sign_agreement: float = 0.8
    maximum_leave_one_out_relative_change: float = 0.5


_PREDICTION_GATES = frozenset({
    "chronological_holdout_performance",
    "no_heat_baseline_falsification",
    "permuted_negative_control_falsification",
})
_DATA_SUPPORT_GATES = frozenset({
    "complete_export",
    "minimum_activities",
    "minimum_segments",
    "chronological_holdout",
    "environmental_spread",
    "holdout_environmental_spread",
    "provider_regime_consistency",
    "environment_source_consistency",
})


def assess_environment_response_preflight(
    counts: dict[str, int | bool],
    *,
    validation_config: HeatValidationConfig | None = None,
) -> dict[str, Any]:
    """Classify only definite blockers before the full Labs analysis runs.

    This aggregate preflight deliberately avoids fitting, segmentation, and
    release-gate evaluation. Passing means the analysis is worth attempting,
    not that a curve or conclusion will be released.
    """
    config = validation_config or HeatValidationConfig()
    required = config.minimum_activities

    def count(name: str) -> int:
        return int(counts.get(name, 0))

    reason_code: str | None = None
    status = "likely_eligible"
    can_start = True
    if count("candidate_activity_count") < required:
        reason_code = "insufficient_activities"
    elif count("temperature_activity_count") < required:
        reason_code = "missing_temperature"
    elif count("humidity_activity_count") < required:
        reason_code = "missing_relative_humidity"
    elif count("environment_activity_count") < required:
        reason_code = "missing_environment_pairing"
    elif count("power_activity_count") < required:
        reason_code = "missing_continuous_sample_power"
    elif count("heart_rate_activity_count") < required:
        reason_code = "missing_continuous_heart_rate"
    elif count("complete_any_provider_activity_count") < required:
        reason_code = "insufficient_prerequisite_overlap"
    elif count("stryd_power_activity_count") < required:
        reason_code = "unsupported_power_provider"
    elif count("complete_stryd_activity_count") < required:
        reason_code = "insufficient_prerequisite_overlap"
    elif count("provider_aligned_cp_activity_count") < required:
        reason_code = "missing_provider_aligned_critical_power"
    elif (
        count("complete_any_provider_activity_count")
        > count("complete_stryd_activity_count")
    ):
        status = "needs_full_analysis"
        reason_code = "provider_alignment_requires_full_analysis"
    else:
        status = "likely_eligible"

    if reason_code and status != "needs_full_analysis":
        status = "ineligible"
        can_start = False

    return {
        "status": status,
        "can_start_analysis": can_start,
        "reason_code": reason_code,
        "minimum_activity_count": required,
        "observed": {
            **counts,
        },
        "full_analysis_still_required": True,
    }


def build_environment_response_result(
    dataset: dict[str, Any],
    *,
    config: LabsEnvironmentConfig | None = None,
    validation_config: HeatValidationConfig | None = None,
) -> dict[str, Any]:
    """Return the aggregate-only Labs environmental-response result."""
    selected = config or LabsEnvironmentConfig()
    heat_config = validation_config or HeatValidationConfig()
    if (
        heat_config.minimum_power_pct_cp
        != LABS_MODEL_MINIMUM_POWER_PCT_CP
        or heat_config.maximum_power_pct_cp
        != LABS_MODEL_MAXIMUM_POWER_PCT_CP
    ):
        raise ValueError(
            "Labs environmental-response analysis requires the governed "
            "65-95% CP model domain"
        )
    report = validate_heat_response(dataset, heat_config)
    gate_statuses = {
        name: gate["status"]
        for name, gate in report["gates"].items()
    }
    coverage = report["data_coverage"]
    exclusions = report["exclusions"]
    exclusion_reason_counts = dict(
        Counter(exclusions["excluded_activity_reason_counts"])
        + Counter(exclusions["excluded_segment_reason_counts"])
    )
    eligibility_counts = {
        "input_activity_count": coverage["input_activity_count"],
        "input_segment_count": coverage["input_segment_count"],
        "eligible_activity_count": coverage["eligible_activity_count"],
        "eligible_segment_count": coverage["eligible_segment_count"],
        "exclusion_reason_counts": exclusion_reason_counts,
        "provider_regimes": coverage["provider_regimes"]["combinations"],
        "workload_support": None,
    }
    provider_combinations = coverage["provider_regimes"]["combinations"]
    stryd_regime_pass = bool(
        len(provider_combinations) == 1
        and str(provider_combinations[0]["label"]).startswith("power=stryd|")
    )
    gate_statuses["stryd_power_regime"] = (
        "pass" if stryd_regime_pass else "fail"
    )
    model = report["model"]
    association_gates_pass = stryd_regime_pass and all(
        gate["status"] == "pass"
        for name, gate in report["gates"].items()
        if gate["decision_required"] and name not in _PREDICTION_GATES
    )
    prediction_gates = [
        report["gates"][name]
        for name in sorted(_PREDICTION_GATES)
    ]
    if any(gate["status"] == "unavailable" for gate in prediction_gates):
        prediction_status = "unavailable"
    elif all(gate["status"] == "pass" for gate in prediction_gates):
        prediction_status = "passed_research_diagnostics"
    else:
        prediction_status = "failed_research_diagnostics"

    if model["status"] != "available":
        return _withheld_result(
            result_state="insufficient_data",
            prediction_status=prediction_status,
            eligibility_counts=eligibility_counts,
            gate_statuses=gate_statuses,
            report=report,
        )

    combined, export = _prepare_dataset(dataset)
    flattened = _flatten_dataset(combined, heat_config, export=export)
    primary = _analyze_rows(
        flattened,
        heat_config,
        heat_representation="wet_bulb_c",
        include_bootstrap=False,
    )
    internal = primary["_internal"]
    train_rows = internal["train_rows"]
    test_rows = internal["test_rows"]
    feature_names = internal["feature_names"]
    heat_center = internal["heat_center"]
    workload_support = _workload_support(
        train_rows,
        selected,
    )
    eligibility_counts["workload_support"] = workload_support

    activity_environment: dict[str, list[float]] = {}
    for row in train_rows:
        activity_environment.setdefault(row.activity_key, []).append(row.wet_bulb_c)
    activity_wet_bulb = {
        key: float(np.mean(values))
        for key, values in activity_environment.items()
    }
    activity_values = np.array(list(activity_wet_bulb.values()), dtype=float)
    lower_pct, upper_pct = selected.curve_domain_percentiles
    domain_low, domain_high = np.percentile(
        activity_values,
        [lower_pct, upper_pct],
    )
    edges = np.linspace(
        float(domain_low),
        float(domain_high),
        selected.curve_support_bin_count + 1,
    )
    support_bins = _curve_support_bins(
        combined.get("records", []),
        train_rows,
        edges,
        selected,
        (
            workload_support["personal_display_pct_cp"][0],
            workload_support["personal_display_pct_cp"][1],
        ),
    )
    supported_sections = _supported_bin_sections(support_bins)
    curve_support_pass = _has_displayable_section(
        supported_sections,
        selected.minimum_contiguous_supported_bins,
    )
    reference_overlap_pass = curve_support_pass
    displayed_domains = [
        [
            support_bins[section[0]]["lower_wet_bulb_c"],
            support_bins[section[-1]]["upper_wet_bulb_c"],
        ]
        for section in supported_sections
    ] if curve_support_pass else []
    coefficient = model["heat_stress_coefficient"]
    estimate = float(coefficient["estimate_bpm_per_c"])
    interval = coefficient["uncertainty_interval_bpm_per_c"]
    interval_available = all(value is not None for value in interval)
    # SDR environmental-performance-v2: the descriptive activity-cluster
    # interval must exclude zero and its width may not exceed |estimate|.
    interval_excludes_zero = bool(
        interval_available
        and (float(interval[0]) > 0.0 or float(interval[1]) < 0.0)
    )
    width_ratio = (
        (float(interval[1]) - float(interval[0])) / abs(estimate)
        if interval_available and abs(estimate) > 1e-12
        else None
    )
    interval_width_pass = bool(
        width_ratio is not None
        and width_ratio <= selected.maximum_bootstrap_width_ratio
    )
    leave_one_out = _leave_one_activity_out(
        train_rows,
        test_rows,
        feature_names,
        heat_center,
        heat_config,
        estimate,
    )
    influence_pass = bool(
        leave_one_out["sign_agreement"]
        >= selected.minimum_leave_one_out_sign_agreement
        and leave_one_out["maximum_relative_change"] is not None
        and leave_one_out["maximum_relative_change"]
        <= selected.maximum_leave_one_out_relative_change
    )

    product_gates = {
        "curve_bin_support": "pass" if curve_support_pass else "fail",
        "reference_power_overlap": (
            "pass" if reference_overlap_pass else "fail"
        ),
        "bootstrap_interval_excludes_zero": (
            "pass" if interval_excludes_zero else "fail"
        ),
        "bootstrap_interval_width": (
            "pass" if interval_width_pass else "fail"
        ),
        "leave_one_activity_out_influence": (
            "pass" if influence_pass else "fail"
        ),
        "stryd_power_regime": "pass" if stryd_regime_pass else "fail",
        "partial_domain_support": "pass" if curve_support_pass else "fail",
    }
    gate_statuses.update(product_gates)
    product_gates_pass = all(status == "pass" for status in product_gates.values())

    if not association_gates_pass or not product_gates_pass:
        failed_data_gate = any(
            gate_statuses.get(name) != "pass"
            for name in _DATA_SUPPORT_GATES
        ) or not curve_support_pass or not reference_overlap_pass or not stryd_regime_pass
        return _withheld_result(
            result_state=(
                "insufficient_data"
                if failed_data_gate
                else "unstable_association"
            ),
            prediction_status=prediction_status,
            eligibility_counts={
                **eligibility_counts,
                "curve_support_bins": support_bins,
            },
            gate_statuses=gate_statuses,
            report=report,
            uncertainty={
                "estimate_bpm_per_c": estimate,
                "interval_bpm_per_c": interval,
                "interval_width_to_absolute_estimate_ratio": (
                    round(width_ratio, 4)
                    if width_ratio is not None
                    else None
                ),
                "leave_one_activity_out": leave_one_out,
            },
        )
    if prediction_status == "unavailable":
        return _withheld_result(
            result_state="prediction_unavailable",
            prediction_status=prediction_status,
            eligibility_counts={
                **eligibility_counts,
                "curve_support_bins": support_bins,
            },
            gate_statuses=gate_statuses,
            report=report,
        )

    supported_point_specs = [
        (
            bin_index,
            section_index,
            (
                support_bins[bin_index]["lower_wet_bulb_c"]
                + support_bins[bin_index]["upper_wet_bulb_c"]
            ) / 2.0,
        )
        for section_index, section in enumerate(supported_sections)
        for bin_index in section
    ]
    curve_points = _curve_points(
        train_rows,
        model,
        feature_names,
        interval,
        supported_point_specs,
    )
    partial_domain = len(supported_point_specs) < selected.curve_support_bin_count
    return {
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "power_regime": POWER_REGIME,
        "result_state": "historical_association_only",
        "prediction_status": prediction_status,
        "eligibility_counts": {
            **eligibility_counts,
            "observed_wet_bulb_domain_c": [
                round(float(domain_low), 4),
                round(float(domain_high), 4),
            ],
            "curve_support_bins": support_bins,
            "displayed_wet_bulb_domains_c": displayed_domains,
        },
        "aggregate_curve_points": curve_points,
        "aggregate_uncertainty": {
            "estimate_bpm_per_c": estimate,
            "interval_bpm_per_c": interval,
            "interval_method": coefficient["uncertainty_method"],
            "interval_width_to_absolute_estimate_ratio": round(width_ratio, 4),
            "leave_one_activity_out": leave_one_out,
        },
        "gate_statuses": gate_statuses,
        "limitations": [
            "historical_association_not_causal",
            "not_predictively_validated_for_product_use",
            "psychrometric_wet_bulb_proxy_not_wbgt",
            "no_extrapolation_beyond_observed_domain",
            *(
                ["partial_domain_contains_unsupported_gaps"]
                if partial_domain
                else []
            ),
        ],
    }


def _curve_support_bins(
    records: list[dict[str, Any]],
    train_rows: list[Any],
    edges: np.ndarray,
    config: LabsEnvironmentConfig,
    reference_power_pct_cp: tuple[float, float],
) -> list[dict[str, Any]]:
    """Build aggregate support for one prespecified personal power band."""
    activity_support: dict[str, dict[str, Any]] = {}
    for record in records:
        activity = record.get("activity")
        if not isinstance(activity, dict):
            continue
        activity_id = str(activity.get("activity_id") or "")
        source = str(activity.get("source") or "").strip().casefold()
        activity_key = (
            f"{source}|{activity_id}"
            if source and activity_id
            else ""
        )
        environment = activity.get("environment")
        if not activity_key or not isinstance(environment, dict):
            continue
        wet_bulb = environment.get("wet_bulb_c")
        try:
            wet_bulb_value = float(wet_bulb)
        except (TypeError, ValueError):
            continue
        segments = record.get("stable_segments", {}).get("segments", [])
        accepted = any(
            reference_power_pct_cp[0]
            <= float(segment.get("mean_pct_cp"))
            <= reference_power_pct_cp[1]
            for segment in segments
            if segment.get("mean_pct_cp") is not None
            and segment.get("source") == "samples"
            and not segment.get("reason_codes")
        )
        activity_support[activity_key] = {
            "wet_bulb_c": wet_bulb_value,
            "accepted_stable_segment_mean": accepted,
        }

    bins: list[dict[str, Any]] = []
    for index in range(config.curve_support_bin_count):
        low = float(edges[index])
        high = float(edges[index + 1])

        def in_bin(value: float) -> bool:
            return value >= low and (
                value < high
                or (
                    index == config.curve_support_bin_count - 1
                    and value <= high
                )
            )

        all_activity_keys = {
            key
            for key, support in activity_support.items()
            if in_bin(float(support["wet_bulb_c"]))
        }
        stable_keys = {
            key for key in all_activity_keys
            if activity_support[key]["accepted_stable_segment_mean"]
        }
        rows = [row for row in train_rows if in_bin(row.wet_bulb_c)]
        train_activity_keys = {row.activity_key for row in rows}
        retained_reference_keys = stable_keys & train_activity_keys
        final_reference_keys = {
            row.activity_key
            for row in rows
            if reference_power_pct_cp[0]
            <= row.mean_pct_cp
            <= reference_power_pct_cp[1]
        } & retained_reference_keys
        failure_reasons: list[str] = []
        if len(train_activity_keys) < config.minimum_activities_per_curve_bin:
            failure_reasons.append("insufficient_activities")
        if len(rows) < config.minimum_segments_per_curve_bin:
            failure_reasons.append("insufficient_segments")
        if (
            len(final_reference_keys)
            < config.minimum_reference_power_activities_per_curve_bin
        ):
            failure_reasons.append("insufficient_reference_power_activities")
        bins.append({
            "bin_index": index,
            "lower_wet_bulb_c": round(low, 4),
            "upper_wet_bulb_c": round(high, 4),
            "activity_count": len(train_activity_keys),
            "segment_count": len(rows),
            "reference_power_activity_count": len(final_reference_keys),
            "required_activity_count": config.minimum_activities_per_curve_bin,
            "required_segment_count": config.minimum_segments_per_curve_bin,
            "required_reference_power_activity_count": (
                config.minimum_reference_power_activities_per_curve_bin
            ),
            "supported": not failure_reasons,
            "support_failure_reasons": failure_reasons,
            "reference_power_funnel": {
                "environment_activity_count": len(all_activity_keys),
                "stable_segment_mean_activity_count": len(stable_keys),
                "training_partition_activity_count": len(
                    retained_reference_keys
                ),
                "final_reference_power_activity_count": len(
                    final_reference_keys
                ),
            },
        })
    return bins


def _workload_support(
    train_rows: list[Any],
    config: LabsEnvironmentConfig,
) -> dict[str, Any]:
    """Return aggregate provenance for personal display and common model rows."""
    if not train_rows:
        raise ValueError("Personal workload support requires training rows")
    median_pct_cp = float(np.median([
        float(row.mean_pct_cp)
        for row in train_rows
    ]))
    half_width = config.reference_power_half_width_percentage_points
    minimum_pct_cp = LABS_MODEL_MINIMUM_POWER_PCT_CP
    maximum_pct_cp = LABS_MODEL_MAXIMUM_POWER_PCT_CP
    personal_low = max(minimum_pct_cp, median_pct_cp - half_width)
    personal_high = min(maximum_pct_cp, median_pct_cp + half_width)
    return {
        "policy": "training_median_centered_v1",
        "training_median_pct_cp": round(median_pct_cp, 4),
        "personal_display_pct_cp": [
            round(float(personal_low), 4),
            round(float(personal_high), 4),
        ],
        "half_width_percentage_points": half_width,
        "model_eligible_pct_cp": [
            minimum_pct_cp,
            maximum_pct_cp,
        ],
        "display_filter_applied_to_model_rows": False,
    }


def _supported_bin_sections(
    support_bins: list[dict[str, Any]],
) -> list[list[int]]:
    """Return consecutive supported-bin indices without bridging gaps."""
    sections: list[list[int]] = []
    current: list[int] = []
    for item in support_bins:
        if item["supported"]:
            current.append(int(item["bin_index"]))
        elif current:
            sections.append(current)
            current = []
    if current:
        sections.append(current)
    return sections


def _has_displayable_section(
    sections: list[list[int]],
    minimum_contiguous_bins: int,
) -> bool:
    """Return whether at least one supported section can form a curve."""
    return any(
        len(section) >= minimum_contiguous_bins
        for section in sections
    )


def _leave_one_activity_out(
    train_rows: list[Any],
    test_rows: list[Any],
    feature_names: tuple[str, ...],
    heat_center: float,
    config: HeatValidationConfig,
    primary_estimate: float,
) -> dict[str, Any]:
    # Influence formulas and the 0.8 / 0.5 release bounds are accepted product
    # guardrails in sdr-environmental-performance-v2, not inferential tests.
    estimates: list[float] = []
    heat_index = feature_names.index("wet_bulb_c")
    for activity_key in sorted({row.activity_key for row in train_rows}):
        reduced = [row for row in train_rows if row.activity_key != activity_key]
        if not reduced:
            continue
        fit = _fit_model(
            reduced,
            test_rows,
            feature_names,
            heat_representation="wet_bulb_c",
            heat_center=heat_center,
            ridge_alpha=config.ridge_alpha,
        )
        estimates.append(float(fit.coefficients[heat_index]))
    primary_sign = np.sign(primary_estimate)
    sign_agreement = (
        sum(np.sign(value) == primary_sign for value in estimates) / len(estimates)
        if estimates and primary_sign != 0
        else 0.0
    )
    maximum_relative_change = (
        max(abs(value - primary_estimate) / abs(primary_estimate) for value in estimates)
        if estimates and abs(primary_estimate) > 1e-12
        else float("inf")
    )
    return {
        "evaluated_activity_count": len(estimates),
        "sign_agreement": round(float(sign_agreement), 4),
        "maximum_relative_change": (
            round(float(maximum_relative_change), 4)
            if np.isfinite(maximum_relative_change)
            else None
        ),
    }


def _curve_points(
    train_rows: list[Any],
    model: dict[str, Any],
    feature_names: tuple[str, ...],
    interval: list[float | None],
    point_specs: list[tuple[int, int, float]],
) -> list[dict[str, float | int]]:
    # SDR environmental-performance-v2 fixes training medians as the reference
    # profile and prohibits extrapolation beyond the 10th-90th percentile
    # activity-level wet-bulb domain.
    coefficients = model["coefficients"]
    reference_values: dict[str, float] = {}
    for feature in feature_names:
        if feature == "wet_bulb_c":
            continue
        reference_values[feature] = float(np.median([
            getattr(row, feature)
            for row in train_rows
        ]))
    reference_wet_bulb = float(np.median([
        row.wet_bulb_c
        for row in train_rows
    ]))
    baseline = float(model["intercept_bpm"])
    for feature, value in reference_values.items():
        baseline += float(coefficients[feature]) * value
    baseline += float(coefficients["wet_bulb_c"]) * reference_wet_bulb
    lower_slope = float(interval[0])
    upper_slope = float(interval[1])
    points: list[dict[str, float]] = []
    for bin_index, section_index, wet_bulb in point_specs:
        delta = float(wet_bulb - reference_wet_bulb)
        relative = float(coefficients["wet_bulb_c"]) * delta
        relative_bounds = sorted((lower_slope * delta, upper_slope * delta))
        points.append({
            "wet_bulb_c": round(float(wet_bulb), 4),
            "modeled_hr_bpm": round(baseline + relative, 4),
            "relative_hr_bpm": round(relative, 4),
            "relative_lower_bpm": round(relative_bounds[0], 4),
            "relative_upper_bpm": round(relative_bounds[1], 4),
            "reference_wet_bulb_c": round(reference_wet_bulb, 4),
            "support_bin_index": bin_index,
            "section_index": section_index,
        })
    return points


def _withheld_result(
    *,
    result_state: str,
    prediction_status: str,
    eligibility_counts: dict[str, Any],
    gate_statuses: dict[str, str],
    report: dict[str, Any],
    uncertainty: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "power_regime": POWER_REGIME,
        "result_state": result_state,
        "prediction_status": prediction_status,
        "eligibility_counts": eligibility_counts,
        "aggregate_curve_points": [],
        "aggregate_uncertainty": uncertainty or {},
        "gate_statuses": gate_statuses,
        "limitations": report["limitations"],
    }
