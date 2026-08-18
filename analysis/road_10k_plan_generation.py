"""Pure deterministic generation for the reviewed inactive road 10K policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import json
from statistics import median
from typing import Any, Literal, Mapping, Sequence

from analysis.road_10k_contract import (
    ROAD_10K_BASELINE_CURRENT_THROUGH_COMPLETED_DAYS,
    ROAD_10K_CONTRACT_DIGEST,
    ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
    ROAD_10K_EVENTS,
    ROAD_10K_GENERATOR_VERSION,
    ROAD_10K_HISTORY_LOOKBACK_COMPLETED_WEEKS,
    ROAD_10K_INTENSITY,
    ROAD_10K_POLICY_VERSION,
    ROAD_10K_PROPOSAL_DAYS,
    ROAD_10K_REASSESSMENT_COMPLETED_DAYS,
    ROAD_10K_REQUIRED_INPUTS,
    ROAD_10K_RESULT_CODES,
    ROAD_10K_SCHEDULE,
    ROAD_10K_SCIENCE_DECISION_ID,
    ROAD_10K_SOURCE_DECISION_DIGEST,
    ROAD_10K_TEMPLATES,
    ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION,
)


_ALLOWED_RESULT_CODES = ROAD_10K_RESULT_CODES
_LOOKBACK_COMPLETED_WEEKS = ROAD_10K_HISTORY_LOOKBACK_COMPLETED_WEEKS
_MINIMUM_USABLE_WEEKS = int(
    ROAD_10K_REQUIRED_INPUTS["minimum_usable_completed_weeks"]
)
_MINIMUM_RUNS_PER_WEEK = int(
    ROAD_10K_REQUIRED_INPUTS["minimum_runs_per_usable_week"]
)
_LATEST_RUN_DAYS = int(
    ROAD_10K_REQUIRED_INPUTS["latest_run_within_completed_days"]
)
_CURRENT_BASELINE_DAYS = ROAD_10K_BASELINE_CURRENT_THROUGH_COMPLETED_DAYS
_PROPOSAL_DAYS = ROAD_10K_PROPOSAL_DAYS
_REASSESSMENT_DAYS = ROAD_10K_REASSESSMENT_COMPLETED_DAYS
_MIN_RUN_DAYS = int(
    ROAD_10K_SCHEDULE["selected_running_days_per_7_day_unit"]["minimum"]
)
_MAX_RUN_DAYS = int(
    ROAD_10K_SCHEDULE["selected_running_days_per_7_day_unit"]["maximum"]
)
_LOW_INTENSITY_FLOOR = float(
    ROAD_10K_INTENSITY["minimum_planned_low_intensity_running_minutes_fraction"]
)
_TAPER_VOLUME_REDUCTION = float(
    ROAD_10K_EVENTS["taper"]["planned_volume_reduction_fraction"]
)


@dataclass(frozen=True)
class Road10KGoal:
    """Goal fields admitted by the reviewed road 10K generator."""

    goal_kind: str
    distance: str | None
    target_time_sec: int | None
    target_event_date: date | None


@dataclass(frozen=True)
class Road10KPlanGenerationConstraints:
    """Typed athlete-stated constraints for the deterministic generator."""

    adult_confirmed: bool
    current_symptom_stop: bool
    available_weekdays: tuple[int, ...]
    weekly_time_limit_min: int
    maximum_session_duration_min: int
    unavailable_dates: tuple[date, ...]
    preferred_longest_easy_weekday: int | None
    benchmark_date: date | None = None


@dataclass(frozen=True)
class RunningHistoryObservation:
    """One completed running observation with provenance."""

    activity_id: str
    observed_date: date
    duration_min: float
    distance_km: float | None
    source: str


@dataclass(frozen=True)
class RecentHistoryStatistics:
    """Reproducible 8-week history anchors for the reviewed policy."""

    usable_completed_weeks: int
    recent_modal_running_frequency: int
    recent_median_usable_weekly_minutes: int
    recent_maximum_usable_weekly_minutes: int
    recent_maximum_session_minutes: int
    recent_maximum_session_distance_km: float | None
    latest_run_date: date | None


@dataclass(frozen=True)
class Road10KEventContext:
    """Explicit event or benchmark context admitted by the policy."""

    snapshot_version: str
    state: Literal["confirmed_none", "single_target", "race_dense"]
    goal_target_date: date | None
    benchmark_date: date | None
    target_date: date | None
    target_source: Literal["goal", "benchmark", None]


@dataclass(frozen=True)
class WorkoutStep:
    """One immutable structured workout step."""

    kind: str
    phase: str | None = None
    duration_min: int | None = None
    repetitions: int | None = None
    steps: tuple["WorkoutStep", ...] = ()


@dataclass(frozen=True)
class GeneratedWorkout:
    """One deterministic planned workout."""

    template_id: str | None
    scheduled_date: date
    workout_type: str
    intensity_bucket: Literal["low", "quality"]
    planned_duration_min: int
    maximum_distance_ceiling_km: float
    steps: tuple[WorkoutStep, ...]


@dataclass(frozen=True)
class GeneratedWeek:
    """One seven-day proposal unit."""

    week_number: int
    is_taper: bool
    external_quality_date: date | None
    workouts: tuple[GeneratedWorkout, ...]


@dataclass(frozen=True)
class GeneratedRoad10KPlan:
    """A reviewed immutable 14-day non-canonical proposal payload."""

    policy_version: str
    generator_version: str
    horizon_start: date
    horizon_end: date
    reassessment_dates: tuple[date, ...]
    history_statistics: RecentHistoryStatistics
    event_context: Road10KEventContext
    weeks: tuple[GeneratedWeek, ...]


@dataclass(frozen=True)
class Road10KGenerationInput:
    """All versioned inputs required to replay a road 10K decision."""

    policy_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    athlete_today: date
    block_start: date
    goal: Road10KGoal
    baseline_current: bool
    baseline_snapshot_id: str | None
    baseline_source: str | None
    baseline_evidence_date: date | None
    history: tuple[RunningHistoryObservation, ...]
    intensity_sources: tuple[tuple[str, str], ...]
    reserved_dates: tuple[date, ...]
    training_pattern_snapshot_version: str
    constraints: Road10KPlanGenerationConstraints


@dataclass(frozen=True)
class Road10KGenerationResult:
    """Typed success or fail-closed readiness outcome."""

    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    code: str
    deterministic_input_hash: str
    plan: GeneratedRoad10KPlan | None
    event_context: Road10KEventContext
    history_statistics: RecentHistoryStatistics
    failed_rule_id: str | None
    observed_or_stated_reason: str | None
    uncertainty_or_missing_field: str | None
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class WorkoutTemplateGuardrail:
    """Reviewed product template; not an optimum claim."""

    template_id: str
    workout_type: str
    low_intensity_minutes: int
    steps: tuple[WorkoutStep, ...]


def _template_steps(
    template: Mapping[str, Any],
) -> tuple[WorkoutStep, ...]:
    def build(step: Mapping[str, Any]) -> WorkoutStep:
        if step["kind"] == "repeat":
            return WorkoutStep(
                kind="repeat",
                repetitions=int(step["repetitions"]),
                steps=tuple(
                    build(child) for child in step["steps"]
                ),
            )
        return WorkoutStep(
            kind="step",
            phase=str(step["phase"]),
            duration_min=int(step["duration_minutes"]),
        )

    return tuple(build(step) for step in template["steps"])


ROAD_10K_TEMPLATE_GUARDRAILS = tuple(
    WorkoutTemplateGuardrail(
        template_id=str(template["template_id"]),
        workout_type=str(template["workout_type"]),
        low_intensity_minutes=sum(
            int(step["duration_minutes"])
            for step in template["steps"]
            if step["kind"] == "step"
            and str(step.get("intended_intensity")) == "low"
        )
        + sum(
            int(child["duration_minutes"]) * int(step["repetitions"])
            for step in template["steps"]
            if step["kind"] == "repeat"
            for child in step["steps"]
            if str(child.get("intended_intensity")) == "low"
        ),
        steps=_template_steps(template),
    )
    for template in ROAD_10K_TEMPLATES["templates"]
)
_TEMPLATE_BY_ID = {
    item.template_id: item for item in ROAD_10K_TEMPLATE_GUARDRAILS
}


def derive_recent_history_statistics(
    history: Sequence[RunningHistoryObservation],
    *,
    athlete_today: date,
) -> RecentHistoryStatistics:
    """Derive conservative 8-week anchors from completed running history."""
    current_week_start = athlete_today - timedelta(days=athlete_today.weekday())
    first_week_start = current_week_start - timedelta(
        days=7 * _LOOKBACK_COMPLETED_WEEKS
    )
    complete = tuple(
        observation
        for observation in history
        if first_week_start <= observation.observed_date < current_week_start
        and observation.duration_min > 0
    )
    week_buckets: dict[date, list[RunningHistoryObservation]] = {}
    for observation in complete:
        week_start = observation.observed_date - timedelta(
            days=observation.observed_date.weekday()
        )
        week_buckets.setdefault(week_start, []).append(observation)

    usable = sorted(
        (
            (week_start, values)
            for week_start, values in week_buckets.items()
            if len(values) >= _MINIMUM_RUNS_PER_WEEK
            and sum(value.duration_min for value in values) > 0
        ),
        key=lambda item: item[0],
    )
    frequencies = [len(values) for _, values in usable]
    total_minutes = [
        int(sum(value.duration_min for value in values))
        for _, values in usable
    ]
    all_usable = [
        observation
        for _, values in usable
        for observation in values
    ]
    return RecentHistoryStatistics(
        usable_completed_weeks=len(usable),
        recent_modal_running_frequency=_conservative_mode(frequencies),
        recent_median_usable_weekly_minutes=(
            int(median(total_minutes)) if total_minutes else 0
        ),
        recent_maximum_usable_weekly_minutes=max(total_minutes, default=0),
        recent_maximum_session_minutes=int(
            max((item.duration_min for item in all_usable), default=0)
        ),
        recent_maximum_session_distance_km=max(
            (
                float(item.distance_km)
                for item in all_usable
                if item.distance_km is not None
            ),
            default=None,
        ),
        latest_run_date=max(
            (item.observed_date for item in complete),
            default=None,
        ),
    )


def build_event_context(
    goal: Road10KGoal,
    constraints: Road10KPlanGenerationConstraints,
) -> Road10KEventContext:
    """Return the explicit event or benchmark context admitted by the policy."""
    goal_target = goal.target_event_date
    benchmark = constraints.benchmark_date
    if goal_target is not None and benchmark is not None:
        return Road10KEventContext(
            snapshot_version=ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
            state="race_dense",
            goal_target_date=goal_target,
            benchmark_date=benchmark,
            target_date=None,
            target_source=None,
        )
    if goal_target is not None:
        return Road10KEventContext(
            snapshot_version=ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
            state="single_target",
            goal_target_date=goal_target,
            benchmark_date=None,
            target_date=goal_target,
            target_source="goal",
        )
    if benchmark is not None:
        return Road10KEventContext(
            snapshot_version=ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
            state="single_target",
            goal_target_date=None,
            benchmark_date=benchmark,
            target_date=benchmark,
            target_source="benchmark",
        )
    return Road10KEventContext(
        snapshot_version=ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
        state="confirmed_none",
        goal_target_date=None,
        benchmark_date=None,
        target_date=None,
        target_source=None,
    )


def generate_road_10k_plan(
    generation_input: Road10KGenerationInput,
) -> Road10KGenerationResult:
    """Generate a reviewed 14-day proposal or a typed no-plan outcome."""
    statistics = derive_recent_history_statistics(
        generation_input.history,
        athlete_today=generation_input.athlete_today,
    )
    event_context = build_event_context(
        generation_input.goal,
        generation_input.constraints,
    )
    input_hash = deterministic_input_hash(
        generation_input,
        event_context=event_context,
    )

    if not _accepted_contract(generation_input):
        return _no_plan(
            code="validation_failed",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="accepted_contract",
            reason="The supplied contract or version identifiers do not match the reviewed road 10K policy.",
            missing="reviewed contract identifiers",
            alternatives=("refresh_policy_metadata",),
        )
    if not _eligible_goal(generation_input.goal):
        return _no_plan(
            code="unsupported_intent_distance_surface_or_population",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="eligible_goal",
            reason="The supplied goal is outside the reviewed road 10K capability.",
            missing="performance_10k current-goal or capability purpose",
            alternatives=("keep_manual_training",),
        )
    if not generation_input.constraints.adult_confirmed:
        return _no_plan(
            code="adult_scope_or_constraints_unconfirmed",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="adult_confirmation",
            reason="Adult confirmation is required before this capability can proceed.",
            missing="adult confirmation",
            alternatives=("confirm_adult_scope", "keep_manual_training"),
        )
    constraint_error = _constraint_error(generation_input.constraints)
    if constraint_error is not None:
        code, rule, reason, missing, alternatives = constraint_error
        return _no_plan(
            code=code,
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule=rule,
            reason=reason,
            missing=missing,
            alternatives=alternatives,
        )
    if generation_input.constraints.current_symptom_stop:
        return _no_plan(
            code="safety_stop",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="current_symptom_stop",
            reason="The athlete reported a current symptom stop.",
            missing=None,
            alternatives=("defer_plan_generation", "use_non_medical_safety_guidance"),
        )
    if not _baseline_is_current(generation_input):
        return _no_plan(
            code="missing_or_stale_direct_baseline",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="direct_current_10k_baseline",
            reason="A current direct 10K baseline is required before plan generation.",
            missing="current direct 10K baseline",
            alternatives=(
                "confirm_direct_10k_history",
                "choose_optional_10k_benchmark",
                "keep_manual_training",
            ),
        )
    history_error = _history_error(
        statistics=statistics,
        athlete_today=generation_input.athlete_today,
    )
    if history_error is not None:
        return _no_plan(
            code="insufficient_recent_history",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="recent_history_prerequisite",
            reason=history_error,
            missing="four usable completed weeks and a run within ten completed days",
            alternatives=("accumulate_more_consistent_running",),
        )
    if event_context.state == "race_dense":
        return _no_plan(
            code="limited_guidance_event_conflict",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="race_dense_event_context",
            reason="A confirmed target date and a separate benchmark date cannot both drive one reviewed 14-day proposal.",
            missing=None,
            alternatives=("keep_one_target_date", "decline_optional_benchmark"),
        )
    if _target_is_too_close(
        event_context=event_context,
        block_start=generation_input.block_start,
    ):
        return _no_plan(
            code="limited_near_term_guidance",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="near_term_target",
            reason="The confirmed target date is fewer than eight days after this proposal start.",
            missing=None,
            alternatives=("wait_for_post_target_reassessment", "keep_manual_training"),
        )

    schedule = _build_schedule(
        generation_input=generation_input,
        statistics=statistics,
        event_context=event_context,
    )
    if schedule is None:
        return _no_plan(
            code="no_schedule_within_envelope",
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule="schedule_within_envelope",
            reason="The stated availability, load limits, and event context cannot form a reviewed schedule within the envelope.",
            missing="a reviewed schedule within the current envelope",
            alternatives=("revise_constraints", "keep_manual_training"),
        )
    validation_error = _validate_schedule(
        schedule,
        statistics=statistics,
        generation_input=generation_input,
        event_context=event_context,
    )
    if validation_error is not None:
        code, rule, reason = validation_error
        return _no_plan(
            code=code,
            input_hash=input_hash,
            statistics=statistics,
            event_context=event_context,
            rule=rule,
            reason=reason,
            missing=None,
            alternatives=("revise_constraints", "keep_manual_training"),
        )

    horizon_end = _schedule_end_exclusive(
        generation_input,
        event_context=event_context,
    ) - timedelta(days=1)
    plan = GeneratedRoad10KPlan(
        policy_version=ROAD_10K_POLICY_VERSION,
        generator_version=ROAD_10K_GENERATOR_VERSION,
        horizon_start=generation_input.block_start,
        horizon_end=horizon_end,
        reassessment_dates=tuple(
            generation_input.block_start + timedelta(days=_REASSESSMENT_DAYS)
            for _ in [0]
            if generation_input.block_start + timedelta(days=_REASSESSMENT_DAYS)
            <= horizon_end
        ),
        history_statistics=statistics,
        event_context=event_context,
        weeks=schedule,
    )
    success_code = (
        "eligible_taper_proposal"
        if any(week.is_taper for week in schedule)
        else "eligible_rolling_proposal"
    )
    return Road10KGenerationResult(
        policy_version=ROAD_10K_POLICY_VERSION,
        generator_version=ROAD_10K_GENERATOR_VERSION,
        science_decision_id=ROAD_10K_SCIENCE_DECISION_ID,
        contract_digest=ROAD_10K_CONTRACT_DIGEST,
        source_decision_digest=ROAD_10K_SOURCE_DECISION_DIGEST,
        code=success_code,
        deterministic_input_hash=input_hash,
        plan=plan,
        event_context=event_context,
        history_statistics=statistics,
        failed_rule_id=None,
        observed_or_stated_reason=None,
        uncertainty_or_missing_field=None,
        alternatives=(
            "review_before_adopting",
            "keep_current_plan_until_adoption",
        ),
    )


def deterministic_input_hash(
    generation_input: Road10KGenerationInput,
    *,
    event_context: Road10KEventContext | None = None,
) -> str:
    """Return the stable replay hash for the complete versioned input."""
    context = (
        event_context
        if event_context is not None
        else build_event_context(generation_input.goal, generation_input.constraints)
    )
    payload = {
        "policy_version": generation_input.policy_version,
        "science_decision_id": generation_input.science_decision_id,
        "contract_digest": generation_input.contract_digest,
        "source_decision_digest": generation_input.source_decision_digest,
        "generator_version": ROAD_10K_GENERATOR_VERSION,
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "goal": {
            "goal_kind": generation_input.goal.goal_kind,
            "distance": generation_input.goal.distance,
            "target_time_sec": generation_input.goal.target_time_sec,
            "target_event_date": _date_or_none(
                generation_input.goal.target_event_date
            ),
        },
        "baseline": {
            "current": generation_input.baseline_current,
            "snapshot_id": generation_input.baseline_snapshot_id,
            "source": generation_input.baseline_source,
            "evidence_date": _date_or_none(
                generation_input.baseline_evidence_date
            ),
        },
        "history": [
            {
                "activity_id": item.activity_id,
                "observed_date": item.observed_date.isoformat(),
                "duration_min": item.duration_min,
                "distance_km": item.distance_km,
                "source": item.source,
            }
            for item in sorted(
                generation_input.history,
                key=lambda item: (
                    item.observed_date,
                    item.activity_id,
                    item.source,
                ),
            )
        ],
        "intensity_sources": [
            {"activity_id": activity_id, "source": source}
            for activity_id, source in sorted(
                generation_input.intensity_sources,
                key=lambda item: (item[0], item[1]),
            )
        ],
        "reserved_dates": sorted(
            item.isoformat() for item in generation_input.reserved_dates
        ),
        "training_pattern_snapshot_version": (
            generation_input.training_pattern_snapshot_version
        ),
        "event_context": asdict(context),
        "constraints": {
            "adult_confirmed": generation_input.constraints.adult_confirmed,
            "current_symptom_stop": (
                generation_input.constraints.current_symptom_stop
            ),
            "available_weekdays": tuple(
                sorted(generation_input.constraints.available_weekdays)
            ),
            "weekly_time_limit_min": (
                generation_input.constraints.weekly_time_limit_min
            ),
            "maximum_session_duration_min": (
                generation_input.constraints.maximum_session_duration_min
            ),
            "unavailable_dates": sorted(
                item.isoformat()
                for item in generation_input.constraints.unavailable_dates
            ),
            "preferred_longest_easy_weekday": (
                generation_input.constraints.preferred_longest_easy_weekday
            ),
            "benchmark_date": _date_or_none(
                generation_input.constraints.benchmark_date
            ),
        },
    }
    canonical = json.dumps(
        _json_safe_dates(payload),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_workout_structure(workout: GeneratedWorkout) -> dict[str, Any]:
    """Return the portable v1 workout structure for a generated workout."""
    return {"steps": [_serialize_step(step) for step in workout.steps]}


def serialize_generation_input(
    generation_input: Road10KGenerationInput,
) -> dict[str, Any]:
    """Return an audit-safe JSON snapshot of the typed input."""
    return _json_safe_dates(asdict(generation_input))


def serialize_generation_result(
    result: Road10KGenerationResult,
) -> dict[str, Any]:
    """Return a JSON-safe policy outcome without changing its authority."""
    return _json_safe_dates(asdict(result))


def _accepted_contract(generation_input: Road10KGenerationInput) -> bool:
    return (
        generation_input.policy_version == ROAD_10K_POLICY_VERSION
        and generation_input.science_decision_id
        == ROAD_10K_SCIENCE_DECISION_ID
        and generation_input.contract_digest == ROAD_10K_CONTRACT_DIGEST
        and generation_input.source_decision_digest
        == ROAD_10K_SOURCE_DECISION_DIGEST
        and generation_input.training_pattern_snapshot_version
        == ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION
    )


def _eligible_goal(goal: Road10KGoal) -> bool:
    return (
        goal.goal_kind == "performance_10k"
        and str(goal.distance or "").casefold() == "10k"
    )


def _baseline_is_current(
    generation_input: Road10KGenerationInput,
) -> bool:
    if (
        not generation_input.baseline_current
        or generation_input.baseline_snapshot_id is None
        or generation_input.baseline_source is None
        or generation_input.baseline_evidence_date is None
    ):
        return False
    age_days = (
        generation_input.athlete_today - generation_input.baseline_evidence_date
    ).days
    return age_days <= _CURRENT_BASELINE_DAYS


def _history_error(
    *,
    statistics: RecentHistoryStatistics,
    athlete_today: date,
) -> str | None:
    if statistics.usable_completed_weeks < _MINIMUM_USABLE_WEEKS:
        return "Fewer than four usable completed running weeks were observed."
    if statistics.latest_run_date is None:
        return "No completed recent running observation is available."
    if (athlete_today - statistics.latest_run_date).days > _LATEST_RUN_DAYS:
        return "The latest completed run is more than ten days old."
    if (
        statistics.recent_maximum_session_distance_km is None
        or statistics.recent_maximum_session_distance_km <= 0
    ):
        return (
            "Usable recent session distance is unavailable, so Praxys cannot "
            "set the reviewed maximum-distance ceiling."
        )
    return None


def _constraint_error(
    constraints: Road10KPlanGenerationConstraints,
) -> tuple[str, str, str, str | None, tuple[str, ...]] | None:
    weekdays = constraints.available_weekdays
    if len(set(weekdays)) != len(weekdays) or any(
        item < 0 or item > 6 for item in weekdays
    ):
        return (
            "contradictory_input",
            "stated_constraints",
            "Available running days must be unique weekday values from zero through six.",
            "available weekdays",
            ("clarify_available_weekdays",),
        )
    if len(weekdays) < _MIN_RUN_DAYS:
        return (
            "contradictory_input",
            "stated_constraints",
            "At least three available running days are required for this capability.",
            "three to six available running days",
            ("expand_available_weekdays",),
        )
    if len(weekdays) > _MAX_RUN_DAYS:
        return (
            "contradictory_input",
            "stated_constraints",
            "More than six available running days is outside the reviewed envelope.",
            "three to six available running days",
            ("reduce_available_weekdays",),
        )
    if constraints.weekly_time_limit_min <= 0:
        return (
            "adult_scope_or_constraints_unconfirmed",
            "stated_constraints",
            "A positive weekly time limit is required.",
            "weekly time limit",
            ("enter_weekly_time_limit",),
        )
    if constraints.maximum_session_duration_min <= 0:
        return (
            "adult_scope_or_constraints_unconfirmed",
            "stated_constraints",
            "A positive single-session time limit is required.",
            "single-session time limit",
            ("enter_single_session_limit",),
        )
    preferred = constraints.preferred_longest_easy_weekday
    if preferred is not None and preferred not in weekdays:
        return (
            "contradictory_input",
            "stated_constraints",
            "The preferred longest-easy day must also be an available running day.",
            "preferred longest-easy day",
            ("revise_preferred_longest_easy_day",),
        )
    return None


def _target_is_too_close(
    *,
    event_context: Road10KEventContext,
    block_start: date,
) -> bool:
    if event_context.target_date is None:
        return False
    return (event_context.target_date - block_start).days < 8


def _taper_start(
    *,
    block_start: date,
    event_context: Road10KEventContext,
) -> date | None:
    event_date = event_context.target_date
    if event_date is None:
        return None
    delta = (event_date - block_start).days
    return block_start if 8 <= delta <= 14 else None


def _schedule_end_exclusive(
    generation_input: Road10KGenerationInput,
    *,
    event_context: Road10KEventContext,
) -> date:
    proposal_end = generation_input.block_start + timedelta(days=_PROPOSAL_DAYS)
    if event_context.target_date is None:
        return proposal_end
    return min(proposal_end, event_context.target_date)


def _build_schedule(
    *,
    generation_input: Road10KGenerationInput,
    statistics: RecentHistoryStatistics,
    event_context: Road10KEventContext,
) -> tuple[GeneratedWeek, ...] | None:
    requested_frequency = len(generation_input.constraints.available_weekdays)
    modal_frequency = statistics.recent_modal_running_frequency
    frequency = min(requested_frequency, modal_frequency, _MAX_RUN_DAYS)
    if frequency < _MIN_RUN_DAYS:
        return None
    session_cap = min(
        generation_input.constraints.maximum_session_duration_min,
        statistics.recent_maximum_session_minutes,
    )
    session_distance_cap = statistics.recent_maximum_session_distance_km
    if session_cap <= 0:
        return None
    if session_distance_cap is None or session_distance_cap <= 0:
        return None
    weekly_target = min(
        statistics.recent_median_usable_weekly_minutes,
        generation_input.constraints.weekly_time_limit_min,
    )
    weekly_cap = min(
        statistics.recent_maximum_usable_weekly_minutes,
        generation_input.constraints.weekly_time_limit_min,
    )
    if weekly_target <= 0 or weekly_cap <= 0 or weekly_target > weekly_cap:
        return None

    blocked_dates = set(generation_input.reserved_dates) | set(
        generation_input.constraints.unavailable_dates
    )
    if event_context.target_date is not None:
        blocked_dates.add(event_context.target_date)

    schedule_end = _schedule_end_exclusive(
        generation_input,
        event_context=event_context,
    )
    taper_start = _taper_start(
        block_start=generation_input.block_start,
        event_context=event_context,
    )

    weeks: list[GeneratedWeek] = []
    for week_index in range(2):
        unit_start = generation_input.block_start + timedelta(days=7 * week_index)
        if unit_start >= schedule_end:
            break
        unit_end = min(unit_start + timedelta(days=6), schedule_end - timedelta(days=1))
        is_taper = (
            taper_start is not None
            and event_context.target_date is not None
            and taper_start <= unit_start < event_context.target_date
        )
        external_quality_date = (
            event_context.target_date
            if event_context.target_date is not None
            and unit_start <= event_context.target_date <= unit_start + timedelta(days=6)
            else None
        )
        available_dates = tuple(
            current
            for current in (
                unit_start + timedelta(days=offset)
                for offset in range((unit_end - unit_start).days + 1)
            )
            if current.weekday() in generation_input.constraints.available_weekdays
            and current not in blocked_dates
        )
        truncated = unit_end < unit_start + timedelta(days=6)
        minimum_dates = 1 if truncated else _MIN_RUN_DAYS
        if len(available_dates) < minimum_dates:
            return None
        frequency_for_unit = min(frequency, len(available_dates))
        if not truncated and frequency_for_unit < frequency:
            return None
        selected_dates = _select_schedule_dates(
            available_dates,
            frequency=frequency_for_unit,
            preferred_longest_easy_weekday=(
                generation_input.constraints.preferred_longest_easy_weekday
            ),
        )
        if selected_dates is None:
            return None
        if is_taper:
            reference = _normal_week_workouts(
                dates=selected_dates,
                total_target=weekly_target,
                session_cap=session_cap,
                maximum_distance_ceiling_km=session_distance_cap,
                preferred_longest_easy_weekday=(
                    generation_input.constraints.preferred_longest_easy_weekday
                ),
                week_index=week_index,
                external_quality_date=None,
            )
            if reference is None:
                return None
            reference_total = sum(
                item.planned_duration_min for item in reference.workouts
            )
            target_total = max(1, int(round(reference_total * (1.0 - _TAPER_VOLUME_REDUCTION))))
            week = _normal_week_workouts(
                dates=selected_dates,
                total_target=target_total,
                session_cap=session_cap,
                maximum_distance_ceiling_km=session_distance_cap,
                preferred_longest_easy_weekday=(
                    generation_input.constraints.preferred_longest_easy_weekday
                ),
                week_index=week_index,
                external_quality_date=external_quality_date,
            )
        else:
            week = _normal_week_workouts(
                dates=selected_dates,
                total_target=weekly_target,
                session_cap=session_cap,
                maximum_distance_ceiling_km=session_distance_cap,
                preferred_longest_easy_weekday=(
                    generation_input.constraints.preferred_longest_easy_weekday
                ),
                week_index=week_index,
                external_quality_date=None,
            )
        if week is None:
            return None
        weeks.append(
            GeneratedWeek(
                week_number=week_index + 1,
                is_taper=is_taper,
                external_quality_date=external_quality_date,
                workouts=week.workouts,
            )
        )
    return tuple(weeks)


@dataclass(frozen=True)
class _WeekBuild:
    workouts: tuple[GeneratedWorkout, ...]


def _normal_week_workouts(
    *,
    dates: Sequence[date],
    total_target: int,
    session_cap: int,
    maximum_distance_ceiling_km: float,
    preferred_longest_easy_weekday: int | None,
    week_index: int,
    external_quality_date: date | None,
) -> _WeekBuild | None:
    if not dates:
        return None
    if maximum_distance_ceiling_km <= 0:
        return None
    quality_template = _quality_template(week_index)
    quality_date = (
        None
        if external_quality_date is not None
        else _quality_date(
            dates,
            preferred_longest_easy_weekday=preferred_longest_easy_weekday,
        )
    )
    easy_dates = [
        item for item in sorted(dates)
        if item != quality_date
    ]
    quality_minutes = 0 if quality_date is None else _steps_duration(
        quality_template.steps
    )
    low_minutes = 0 if quality_date is None else quality_template.low_intensity_minutes
    if quality_date is not None and quality_minutes > session_cap:
        return None
    max_total = quality_minutes + session_cap * len(easy_dates)
    effective_total = min(total_target, max_total)
    if effective_total < quality_minutes + len(easy_dates):
        return None
    remaining = effective_total - quality_minutes
    durations_by_date = _allocate_easy_minutes(
        dates=easy_dates,
        remaining_minutes=remaining,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    if any(duration > session_cap for duration in durations_by_date.values()):
        return None
    total_low_minutes = low_minutes + sum(durations_by_date.values())
    if (
        effective_total <= 0
        or total_low_minutes / effective_total < _LOW_INTENSITY_FLOOR
    ):
        return None
    longest_easy_date = _longest_easy_date(
        easy_dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    workouts: list[GeneratedWorkout] = []
    for scheduled_date in sorted(dates):
        if quality_date is not None and scheduled_date == quality_date:
            workouts.append(
                GeneratedWorkout(
                    template_id=quality_template.template_id,
                    scheduled_date=scheduled_date,
                    workout_type=quality_template.workout_type,
                    intensity_bucket="quality",
                    planned_duration_min=quality_minutes,
                    maximum_distance_ceiling_km=maximum_distance_ceiling_km,
                    steps=quality_template.steps,
                )
            )
            continue
        duration = durations_by_date.get(scheduled_date, 0)
        if duration <= 0:
            return None
        workout_type = (
            "longest_easy"
            if longest_easy_date is not None
            and scheduled_date == longest_easy_date
            else "easy"
        )
        workouts.append(
            GeneratedWorkout(
                template_id=None,
                scheduled_date=scheduled_date,
                workout_type=workout_type,
                intensity_bucket="low",
                planned_duration_min=duration,
                maximum_distance_ceiling_km=maximum_distance_ceiling_km,
                steps=(
                    WorkoutStep(
                        kind="step",
                        phase="other",
                        duration_min=duration,
                    ),
                ),
            )
        )
    return _WeekBuild(workouts=tuple(workouts))


def _quality_template(week_index: int) -> WorkoutTemplateGuardrail:
    template_ids = [
        str(template["template_id"])
        for template in ROAD_10K_TEMPLATES["templates"]
    ]
    template_id = (
        template_ids[0]
        if week_index % 2 == 0
        else template_ids[1]
    )
    return _TEMPLATE_BY_ID[template_id]


def _quality_date(
    dates: Sequence[date],
    *,
    preferred_longest_easy_weekday: int | None,
) -> date | None:
    longest = _longest_easy_date(
        dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    for candidate in sorted(dates):
        if candidate != longest:
            return candidate
    return None


def _allocate_easy_minutes(
    *,
    dates: Sequence[date],
    remaining_minutes: int,
    preferred_longest_easy_weekday: int | None,
) -> dict[date, int]:
    if not dates:
        return {}
    base, remainder = divmod(remaining_minutes, len(dates))
    if base <= 0:
        base = 1
        remainder = max(0, remaining_minutes - len(dates))
    priority = list(
        _easy_allocation_priority(
            dates,
            preferred_longest_easy_weekday=preferred_longest_easy_weekday,
        )
    )
    allocations = {scheduled_date: base for scheduled_date in dates}
    for index in range(remainder):
        allocations[priority[index]] += 1
    return allocations


def _easy_allocation_priority(
    dates: Sequence[date],
    *,
    preferred_longest_easy_weekday: int | None,
) -> tuple[date, ...]:
    longest = _longest_easy_date(
        dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    ordered = tuple(sorted(dates))
    if longest is None:
        return ordered
    return (longest,) + tuple(item for item in ordered if item != longest)


def _longest_easy_date(
    dates: Sequence[date],
    *,
    preferred_longest_easy_weekday: int | None,
) -> date | None:
    if not dates:
        return None
    if preferred_longest_easy_weekday is not None:
        for candidate in sorted(dates):
            if candidate.weekday() == preferred_longest_easy_weekday:
                return candidate
    return max(dates)


def _select_schedule_dates(
    dates: Sequence[date],
    *,
    frequency: int,
    preferred_longest_easy_weekday: int | None,
) -> tuple[date, ...] | None:
    ordered = tuple(sorted(dates))
    if len(ordered) < frequency:
        return None
    if preferred_longest_easy_weekday is None:
        return ordered[:frequency]
    preferred = [
        item
        for item in ordered
        if item.weekday() == preferred_longest_easy_weekday
    ]
    if not preferred:
        return ordered[:frequency]
    selected = [preferred[0]]
    for candidate in ordered:
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) == frequency:
            break
    return tuple(sorted(selected))


def _validate_schedule(
    weeks: Sequence[GeneratedWeek],
    *,
    statistics: RecentHistoryStatistics,
    generation_input: Road10KGenerationInput,
    event_context: Road10KEventContext,
) -> tuple[str, str, str] | None:
    session_cap = min(
        generation_input.constraints.maximum_session_duration_min,
        statistics.recent_maximum_session_minutes,
    )
    distance_cap = statistics.recent_maximum_session_distance_km
    weekly_cap = min(
        statistics.recent_maximum_usable_weekly_minutes,
        generation_input.constraints.weekly_time_limit_min,
    )
    target_date = event_context.target_date
    for week in weeks:
        workouts = week.workouts
        if not workouts:
            return (
                "validation_failed",
                "empty_week",
                "A generated week contained no workouts.",
            )
        total_minutes = sum(item.planned_duration_min for item in workouts)
        low_minutes = sum(
            _workout_low_minutes(item) for item in workouts
        )
        quality_exposures = sum(
            item.intensity_bucket == "quality" for item in workouts
        ) + (1 if week.external_quality_date is not None else 0)
        if week.external_quality_date is None and not week.is_taper and not (
            _MIN_RUN_DAYS <= len(workouts) <= _MAX_RUN_DAYS
        ):
            return (
                "validation_failed",
                "running_day_count",
                "A non-taper week fell outside the reviewed three-to-six-day envelope.",
            )
        if any(item.planned_duration_min > session_cap for item in workouts):
            return (
                "validation_failed",
                "session_cap",
                "A generated session exceeded the reviewed single-session cap.",
            )
        if distance_cap is None or distance_cap <= 0:
            return (
                "validation_failed",
                "session_distance_cap_missing",
                "The reviewed session-distance cap was unavailable.",
            )
        if any(
            item.maximum_distance_ceiling_km > distance_cap
            for item in workouts
        ):
            return (
                "validation_failed",
                "session_distance_cap",
                "A generated session exceeded the reviewed distance ceiling.",
            )
        if total_minutes > weekly_cap:
            return (
                "validation_failed",
                "weekly_cap",
                "A generated week exceeded the reviewed weekly cap.",
            )
        if total_minutes <= 0 or low_minutes / total_minutes < _LOW_INTENSITY_FLOOR:
            return (
                "validation_failed",
                "low_intensity_floor",
                "Planned low-intensity minutes fell below the reviewed floor.",
            )
        if quality_exposures != 1:
            return (
                "validation_failed",
                "quality_exposure_count",
                "Each seven-day unit must contain exactly one quality exposure.",
            )
        if target_date is not None and any(
            item.scheduled_date >= target_date for item in workouts
        ):
            return (
                "validation_failed",
                "post_target_workout",
                "A workout was scheduled on or after the confirmed target date.",
            )
    return None


def _steps_duration(steps: Sequence[WorkoutStep]) -> int:
    total = 0
    for step in steps:
        if step.kind == "repeat":
            total += int(step.repetitions or 0) * _steps_duration(step.steps)
        else:
            total += int(step.duration_min or 0)
    return total


def _workout_low_minutes(workout: GeneratedWorkout) -> int:
    if workout.intensity_bucket == "low":
        return workout.planned_duration_min
    template = _TEMPLATE_BY_ID.get(workout.template_id)
    return int(template.low_intensity_minutes) if template is not None else 0


def _conservative_mode(values: Sequence[int]) -> int:
    if not values:
        return 0
    counts = {value: values.count(value) for value in set(values)}
    highest = max(counts.values())
    return min(value for value, count in counts.items() if count == highest)


def _no_plan(
    *,
    code: str,
    input_hash: str,
    statistics: RecentHistoryStatistics,
    event_context: Road10KEventContext,
    rule: str,
    reason: str,
    missing: str | None,
    alternatives: tuple[str, ...],
) -> Road10KGenerationResult:
    if code not in _ALLOWED_RESULT_CODES or code.startswith("eligible_"):
        raise ValueError("code must be an accepted typed no-plan outcome")
    return Road10KGenerationResult(
        policy_version=ROAD_10K_POLICY_VERSION,
        generator_version=ROAD_10K_GENERATOR_VERSION,
        science_decision_id=ROAD_10K_SCIENCE_DECISION_ID,
        contract_digest=ROAD_10K_CONTRACT_DIGEST,
        source_decision_digest=ROAD_10K_SOURCE_DECISION_DIGEST,
        code=code,
        deterministic_input_hash=input_hash,
        plan=None,
        event_context=event_context,
        history_statistics=statistics,
        failed_rule_id=rule,
        observed_or_stated_reason=reason,
        uncertainty_or_missing_field=missing,
        alternatives=alternatives,
    )


def _serialize_step(step: WorkoutStep) -> dict[str, Any]:
    if step.kind == "repeat":
        return {
            "type": "repeat",
            "repetitions": step.repetitions,
            "steps": [_serialize_step(child) for child in step.steps],
        }
    return {
        "type": "step",
        "phase": step.phase,
        "termination": {
            "type": "time",
            "seconds": int(step.duration_min or 0) * 60,
        },
        "target": {
            "metric": "none",
            "unit": "none",
            "reference": "none",
        },
    }


def _date_or_none(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _json_safe_dates(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe_dates(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_dates(item) for item in value]
    return value
