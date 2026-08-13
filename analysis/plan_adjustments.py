"""Pure conservative plan-adjustment decisions."""
from __future__ import annotations

import math
from typing import Any, Literal, Mapping, Sequence, TypedDict

from analysis.config import is_praxys_plan_source
from analysis.metrics import is_hard_workout


CONSERVATIVE_RULE_ID = "hrv_below_hard_to_rest"
CONSERVATIVE_RULE_VERSION = "1"

# Plews et al. supports individualized ln(RMSSD) trend and variability
# monitoring. Kiviniemi et al. supports adapting endurance training from
# individualized daily HRV.
#
# ESTIMATE -- neither study validates this exact mean-minus-one-SD threshold
# or a universal "replace today's hard workout with rest" action. Praxys uses
# that mapping as a deliberately narrow product guardrail, not a diagnosis or
# treatment prescription.
CONSERVATIVE_RULE_CITATIONS: tuple[dict[str, str], ...] = (
    {
        "label": "Plews et al. (2012)",
        "url": "https://doi.org/10.1007/s00421-012-2354-4",
    },
    {
        "label": "Kiviniemi et al. (2007)",
        "url": "https://doi.org/10.1007/s00421-007-0552-2",
    },
)

# analyze_recovery() serializes ln values to two decimals. A direct value may
# differ from its recomputed rounded value by at most half a unit in the last
# place; a separately rounded mean-minus-SD threshold compounds three such
# half-unit errors.
HRV_VALUE_ROUNDING_TOLERANCE = 0.0050001
HRV_DERIVED_ROUNDING_TOLERANCE = 0.0150001

AdjustmentStatus = Literal["disabled", "no_change", "suggestion", "adjust"]
TargetEvidenceState = Literal[
    "not_applicable",
    "current",
    "missing",
    "stale",
    "pending",
    "conflict",
]


class PlanAdjustmentDecision(TypedDict):
    """Deterministic result of evaluating one same-day plan slot."""

    status: AdjustmentStatus
    reason_code: str
    rationale: str
    rule_id: str | None
    rule_version: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    evidence: dict[str, Any]
    bounds: dict[str, Any]
    citations: list[dict[str, str]]
    idempotency_key: str | None


def _decision(
    status: AdjustmentStatus,
    reason_code: str,
    rationale: str,
    *,
    evidence: Mapping[str, Any] | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> PlanAdjustmentDecision:
    """Build a stable adjustment result shape."""
    has_rule = status == "adjust"
    return {
        "status": status,
        "reason_code": reason_code,
        "rationale": rationale,
        "rule_id": CONSERVATIVE_RULE_ID if has_rule else None,
        "rule_version": CONSERVATIVE_RULE_VERSION if has_rule else None,
        "before": dict(before) if before is not None else None,
        "after": dict(after) if after is not None else None,
        "evidence": dict(evidence or {}),
        "bounds": {
            "date_shift_days": 0,
            "workouts_changed": 1 if has_rule else 0,
            "result_workout_type": "rest" if has_rule else None,
            "external_workouts_changed": 0,
        },
        "citations": [dict(citation) for citation in CONSERVATIVE_RULE_CITATIONS],
        "idempotency_key": idempotency_key,
    }


def evaluate_conservative_plan_adjustment(
    *,
    policy: str,
    management_mode: str,
    workouts: Sequence[Mapping[str, Any]],
    training_signal: Mapping[str, Any],
    recovery_analysis: Mapping[str, Any],
    has_completed_activity: bool,
    target_evidence_state: TargetEvidenceState,
    local_date_trusted: bool = True,
) -> PlanAdjustmentDecision:
    """Evaluate the bounded v1 automatic-adjustment policy.

    The only automatic mutation in v1 replaces today's single Praxys-generated
    hard workout with rest when current, individualized HRV is below the
    personal lower caution band. It never infers intensity from activity
    average power (or any activity power); other recovery/load cautions remain
    suggestions. The caller supplies already-loaded evidence, so this function
    has no I/O or side effects.
    """
    if policy != "auto_conservative":
        return _decision(
            "disabled",
            "suggest_only",
            "Automatic plan changes are off; coaching remains suggestion-only.",
        )
    if management_mode != "praxys":
        return _decision(
            "disabled",
            "managed_plan_inactive",
            "Automatic changes require Praxys to own the canonical plan.",
        )
    if not local_date_trusted:
        return _decision(
            "suggestion",
            "athlete_timezone_unavailable",
            "Praxys could not establish the athlete's local date, so the plan remained unchanged.",
        )
    if not workouts:
        return _decision(
            "no_change",
            "no_workout",
            "No Praxys workout is scheduled for today.",
        )
    if len(workouts) != 1:
        return _decision(
            "suggestion",
            "ambiguous_plan_slot",
            "Multiple Praxys workouts share today's plan slot, so no automatic change was made.",
        )

    workout = dict(workouts[0])
    if not is_praxys_plan_source(workout.get("source")):
        return _decision(
            "no_change",
            "external_workout",
            "The workout is external and remains untouched.",
        )
    if str(workout.get("workout_origin") or "").strip().casefold() != "generated":
        return _decision(
            "no_change",
            "workout_not_praxys_generated",
            "Only workouts generated by Praxys are eligible; manually authored or adopted workouts remain untouched.",
        )
    if not is_hard_workout(workout.get("workout_type")):
        return _decision(
            "no_change",
            "workout_not_hard",
            "The scheduled workout is not in the protected hard-workout taxonomy.",
        )

    evidence = {
        "recovery_status": recovery_analysis.get("status"),
        "hrv_latest_date": recovery_analysis.get("hrv_latest_date"),
        "hrv_is_stale": bool(recovery_analysis.get("hrv_is_stale")),
        "target_state": target_evidence_state,
        "signal_reason_code": training_signal.get("reason_code"),
        "workout_origin": workout.get("workout_origin"),
    }
    hrv = recovery_analysis.get("hrv")
    if isinstance(hrv, Mapping):
        evidence.update({
            "hrv_today_ms": hrv.get("today_ms"),
            "hrv_today_ln": hrv.get("today_ln"),
            "hrv_baseline_mean_ln": hrv.get("baseline_mean_ln"),
            "hrv_baseline_sd_ln": hrv.get("baseline_sd_ln"),
            "hrv_lower_band_ln": hrv.get("threshold_ln"),
        })

    if target_evidence_state not in {"not_applicable", "current"}:
        return _decision(
            "suggestion",
            f"target_{target_evidence_state}",
            "The execution-target state is not current and conflict-free, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )
    if has_completed_activity:
        return _decision(
            "suggestion",
            "activity_already_recorded",
            "An activity is already recorded today, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )
    if (
        recovery_analysis.get("status") == "insufficient_data"
        or recovery_analysis.get("hrv_is_stale")
        or not isinstance(hrv, Mapping)
        or not recovery_analysis.get("hrv_latest_date")
        or hrv.get("today_ms") is None
        or hrv.get("today_ln") is None
        or hrv.get("baseline_mean_ln") is None
        or hrv.get("baseline_sd_ln") is None
        or hrv.get("threshold_ln") is None
    ):
        return _decision(
            "suggestion",
            "recovery_evidence_unavailable",
            "Current individualized HRV evidence is missing or stale, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )
    try:
        today_hrv_ms = float(hrv["today_ms"])
        today_ln = float(hrv["today_ln"])
        baseline_mean_ln = float(hrv["baseline_mean_ln"])
        baseline_sd_ln = float(hrv["baseline_sd_ln"])
        threshold_ln = float(hrv["threshold_ln"])
    except (TypeError, ValueError):
        return _decision(
            "suggestion",
            "recovery_evidence_unavailable",
            "Current individualized HRV evidence is invalid, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )
    if (
        not math.isfinite(today_hrv_ms)
        or today_hrv_ms <= 0
        or not math.isfinite(today_ln)
        or not math.isfinite(baseline_mean_ln)
        or not math.isfinite(baseline_sd_ln)
        or baseline_sd_ln <= 0
        or not math.isfinite(threshold_ln)
        or abs(
            today_ln - round(math.log(today_hrv_ms), 2)
        ) > HRV_VALUE_ROUNDING_TOLERANCE
        or abs(
            threshold_ln - round(baseline_mean_ln - baseline_sd_ln, 2)
        ) > HRV_DERIVED_ROUNDING_TOLERANCE
        or today_ln >= threshold_ln
    ):
        return _decision(
            "suggestion",
            "recovery_evidence_mismatch",
            "Current HRV does not independently confirm the lower-band crossing, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )

    signal_workout_type = (
        (training_signal.get("plan") or {}).get("workout_type")
        if isinstance(training_signal.get("plan"), Mapping)
        else None
    )
    if (
        str(signal_workout_type or "").strip().casefold()
        != str(workout.get("workout_type") or "").strip().casefold()
    ):
        return _decision(
            "suggestion",
            "signal_plan_mismatch",
            "The coaching signal no longer matches the canonical workout, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )
    if (
        recovery_analysis.get("status") != "fatigued"
        or training_signal.get("reason_code") != "hrv_below_hard"
        or training_signal.get("recommendation") != "rest"
    ):
        recommendation = str(training_signal.get("recommendation") or "")
        if recommendation in {"modify", "reduce_intensity", "easy", "rest"}:
            return _decision(
                "suggestion",
                "outside_automatic_rule",
                str(training_signal.get("reason") or (
                    "The coaching signal warrants review but is outside the bounded automatic rule."
                )),
                evidence=evidence,
            )
        return _decision(
            "no_change",
            "follow_plan",
            "The current evidence does not meet the bounded automatic-rest rule.",
            evidence=evidence,
        )

    canonical_id = str(workout.get("canonical_id") or "").strip()
    workout_date = str(workout.get("date") or "").strip()
    hrv_latest_date = str(recovery_analysis["hrv_latest_date"])
    if not canonical_id or not workout_date:
        return _decision(
            "suggestion",
            "missing_canonical_identity",
            "The workout lacks a durable canonical identity, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )
    if hrv_latest_date != workout_date:
        return _decision(
            "suggestion",
            "recovery_evidence_not_same_day",
            "Automatic changes require HRV recorded on the workout date, so Praxys kept the plan unchanged.",
            evidence=evidence,
        )

    after = dict(workout)
    after["workout_type"] = "rest"
    after["activity_type"] = "rest"
    # Persisted legacy-flat rows encode absent nullable structure columns as
    # None; plan snapshots may either include those nulls or omit the keys.
    if (
        workout.get("workout_structure_version") is None
        and workout.get("workout_structure") is None
    ):
        after["workout_structure_version"] = None
        after["workout_structure"] = None
    else:
        after["workout_structure_version"] = "v1"
        after["workout_structure"] = {"steps": []}
    for field in (
        "planned_duration_min",
        "planned_distance_km",
        "target_power_min",
        "target_power_max",
        "target_hr_min",
        "target_hr_max",
        "target_pace_min",
        "target_pace_max",
        "start_time",
    ):
        after[field] = None
    original_type = str(workout.get("workout_type") or "hard workout")
    after["workout_description"] = (
        f"Rest day - Praxys replaced {original_type} after current HRV "
        "fell below your personal caution band."
    )
    meta = dict(workout.get("meta") or {})
    meta["auto_adjustment"] = {
        "rule_id": CONSERVATIVE_RULE_ID,
        "rule_version": CONSERVATIVE_RULE_VERSION,
        "hrv_latest_date": hrv_latest_date,
        "reason_code": "hrv_below_hard",
    }
    after["meta"] = meta
    idempotency_key = (
        f"auto-adjust:{CONSERVATIVE_RULE_VERSION}:"
        f"{canonical_id}:{hrv_latest_date}"
    )
    return _decision(
        "adjust",
        "hrv_below_hard",
        (
            "Current HRV is below the individualized lower caution band, "
            "so today's Praxys-owned hard workout was replaced with rest."
        ),
        evidence=evidence,
        before=workout,
        after=after,
        idempotency_key=idempotency_key,
    )
