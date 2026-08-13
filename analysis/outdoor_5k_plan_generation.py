"""Pure deterministic policy generation for the accepted outdoor-road 5K pilot.

This module deliberately accepts only typed, already-loaded observations.  It
does not read databases, models, files, clocks, providers, or mutable module
state.  The policy record is
``sdr-outdoor-5k-plan-generation-policy-v1``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import json
from statistics import median
from typing import Any, Mapping, Sequence


OUTDOOR_5K_POLICY_VERSION = "outdoor-5k-plan-generation-policy-v1"
OUTDOOR_5K_SCIENCE_DECISION_ID = "sdr-outdoor-5k-plan-generation-policy-v1"
OUTDOOR_5K_GENERATOR_VERSION = "outdoor-5k-deterministic-generator-v1"
OUTDOOR_5K_BLOCK_DAYS = 28
OUTDOOR_5K_REASSESSMENT_DAYS = 7
OUTDOOR_5K_EVIDENCE_REVIEW_IDS = (
    "evidence-preplan-baseline-policy-v1",
    "evidence-outdoor-5k-plan-generation-policy-v1",
)
OUTDOOR_5K_EVIDENCE_CLAIM_IDS = (
    "baseline.goal-protocol-match",
    "baseline.current-capability-not-change-comparability",
    "baseline.freshness-cutoff-not-validated",
    "baseline.vigorous-test-symptom-screen",
    "outdoor-5k-plan.structured-periodization-bounded-benefit",
    "outdoor-5k-plan.mostly-low-intensity-no-universal-winner",
    "outdoor-5k-plan.one-to-two-quality-sessions-indirect",
    "outdoor-5k-plan.taper-volume-reduction-supported",
    "outdoor-5k-plan.fixed-progression-not-safety-threshold",
    "outdoor-5k-plan.individual-outcomes-require-error-aware-validation",
)

_ALLOWED_RESULT_CODES = (
    "ready",
    "unsupported_goal_or_population",
    "safety_stop",
    "insufficient_or_stale_baseline",
    "insufficient_goal_horizon",
    "goal_gap_not_actionable_v1",
    "insufficient_recent_history",
    "clarification_required",
    "unsupported_frequency",
    "contradictory_constraints",
    "unsupported_power_target",
    "no_schedule_within_envelope",
)
_LOW_INTENSITY_SESSION_TYPES = ("easy", "longest_easy")
_QUALITY_SESSION_TYPES = ("controlled_quality", "short_interval_quality")


@dataclass(frozen=True)
class Outdoor5KGoal:
    """Structured goal fields admitted by the outdoor-road 5K policy."""

    goal_kind: str
    distance: str | None
    outdoor_road_confirmed: bool
    target_time_sec: int | None
    target_event_date: date | None


@dataclass(frozen=True)
class PlanGenerationConstraints:
    """Purpose-bounded athlete-stated constraints; narrative is intentionally absent."""

    age_18_or_older: bool
    self_coached_recreational_road_runner: bool
    can_complete_5k: bool
    safety_stop: bool
    available_weekdays: tuple[int, ...]
    maximum_session_duration_min: int
    unavailable_dates: tuple[date, ...]
    preferred_longest_run_weekday: int | None


@dataclass(frozen=True)
class RunningHistoryObservation:
    """One provenance-preserving completed running observation."""

    activity_id: str
    observed_date: date
    duration_min: float
    source: str


@dataclass(frozen=True)
class Outdoor5KGenerationInput:
    """All versioned inputs required to replay a generation decision."""

    policy_version: str
    athlete_today: date
    block_start: date
    goal: Outdoor5KGoal
    baseline_current: bool
    baseline_snapshot_id: str | None
    baseline_evidence_date: date | None
    history: tuple[RunningHistoryObservation, ...]
    reserved_dates: tuple[date, ...]
    constraints: PlanGenerationConstraints


@dataclass(frozen=True)
class RecentHistoryStatistics:
    """Reproducible six-completed-week dose anchors."""

    usable_completed_weeks: int
    recent_modal_running_frequency: int
    recent_typical_complete_week_minutes: int
    recent_maximum_complete_week_minutes: int
    recent_longest_completed_run_minutes: int
    latest_run_date: date | None


@dataclass(frozen=True)
class WorkoutStep:
    """One immutable portable workout-structure step or repeat group."""

    kind: str
    phase: str | None = None
    duration_min: int | None = None
    repetitions: int | None = None
    steps: tuple["WorkoutStep", ...] = ()


@dataclass(frozen=True)
class GeneratedWorkout:
    """One deterministic non-canonical proposed running workout."""

    template_id: str
    scheduled_date: date
    workout_type: str
    intensity_bucket: str
    planned_duration_min: int
    steps: tuple[WorkoutStep, ...]


@dataclass(frozen=True)
class GeneratedWeek:
    """One seven-day proposal slice."""

    week_number: int
    is_taper: bool
    workouts: tuple[GeneratedWorkout, ...]


@dataclass(frozen=True)
class GeneratedOutdoor5KPlan:
    """A policy-valid, immutable 28-day non-canonical proposal payload."""

    policy_version: str
    generator_version: str
    horizon_start: date
    horizon_end: date
    reassessment_dates: tuple[date, ...]
    history_statistics: RecentHistoryStatistics
    weeks: tuple[GeneratedWeek, ...]


@dataclass(frozen=True)
class Outdoor5KGenerationResult:
    """Typed success or fail-closed no-plan outcome."""

    policy_version: str
    generator_version: str
    science_decision_id: str
    code: str
    deterministic_input_hash: str
    plan: GeneratedOutdoor5KPlan | None
    history_statistics: RecentHistoryStatistics
    failed_rule_id: str | None
    observed_or_stated_reason: str | None
    uncertainty_or_missing_field: str | None
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class WorkoutTemplateGuardrail:
    """Transparent, versioned product template; not a published optimum."""

    template_id: str
    workout_type: str
    steps: tuple[WorkoutStep, ...]
    policy_decision_id: str
    classification: str = "guardrail"


# These structures implement the SDR's accepted session taxonomy. Their exact
# repeats and durations are transparent Praxys product guardrails, not claims
# about published optimal intervals; see the accepted SDR decision notes.
OUTDOOR_5K_TEMPLATE_GUARDRAILS = (
    WorkoutTemplateGuardrail(
        template_id="outdoor-5k-controlled-quality-v1",
        workout_type="controlled_quality",
        steps=(
            WorkoutStep(kind="step", phase="warmup", duration_min=10),
            WorkoutStep(
                kind="repeat",
                repetitions=2,
                steps=(
                    WorkoutStep(kind="step", phase="work", duration_min=3),
                    WorkoutStep(kind="step", phase="recovery", duration_min=2),
                ),
            ),
            WorkoutStep(kind="step", phase="cooldown", duration_min=10),
        ),
        policy_decision_id=OUTDOOR_5K_SCIENCE_DECISION_ID,
    ),
    WorkoutTemplateGuardrail(
        template_id="outdoor-5k-short-interval-quality-v1",
        workout_type="short_interval_quality",
        steps=(
            WorkoutStep(kind="step", phase="warmup", duration_min=10),
            WorkoutStep(
                kind="repeat",
                repetitions=4,
                steps=(
                    WorkoutStep(kind="step", phase="work", duration_min=1),
                    WorkoutStep(kind="step", phase="recovery", duration_min=1),
                ),
            ),
            WorkoutStep(kind="step", phase="cooldown", duration_min=10),
        ),
        policy_decision_id=OUTDOOR_5K_SCIENCE_DECISION_ID,
    ),
)


def derive_recent_history_statistics(
    history: Sequence[RunningHistoryObservation],
    *,
    athlete_today: date,
) -> RecentHistoryStatistics:
    """Derive conservative complete-week anchors from at most six prior weeks."""
    current_week_start = athlete_today - timedelta(days=athlete_today.weekday())
    first_week_start = current_week_start - timedelta(days=42)
    complete = tuple(
        observation
        for observation in history
        if first_week_start <= observation.observed_date < current_week_start
        and observation.duration_min > 0
    )
    week_minutes: dict[date, list[float]] = {}
    for observation in complete:
        week_start = observation.observed_date - timedelta(
            days=observation.observed_date.weekday()
        )
        week_minutes.setdefault(week_start, []).append(observation.duration_min)

    usable = sorted(
        (
            (week_start, values)
            for week_start, values in week_minutes.items()
            if len(values) >= 2 and sum(values) > 0
        ),
        key=lambda item: item[0],
    )
    frequencies = [len(values) for _, values in usable]
    total_minutes = [int(sum(values)) for _, values in usable]
    modal_frequency = _conservative_mode(frequencies)
    latest_run_date = max(
        (observation.observed_date for observation in complete),
        default=None,
    )
    return RecentHistoryStatistics(
        usable_completed_weeks=len(usable),
        recent_modal_running_frequency=modal_frequency,
        recent_typical_complete_week_minutes=(
            int(median(total_minutes)) if total_minutes else 0
        ),
        recent_maximum_complete_week_minutes=max(total_minutes, default=0),
        recent_longest_completed_run_minutes=int(
            max(
                (observation.duration_min for observation in complete),
                default=0,
            )
        ),
        latest_run_date=latest_run_date,
    )


def generate_outdoor_5k_plan(
    generation_input: Outdoor5KGenerationInput,
) -> Outdoor5KGenerationResult:
    """Generate a conservative 28-day proposal or a typed accepted no-plan code."""
    statistics = derive_recent_history_statistics(
        generation_input.history,
        athlete_today=generation_input.athlete_today,
    )
    input_hash = deterministic_input_hash(generation_input)

    if generation_input.policy_version != OUTDOOR_5K_POLICY_VERSION:
        return _no_plan(
            code="unsupported_goal_or_population",
            input_hash=input_hash,
            statistics=statistics,
            rule="accepted_policy_active",
            reason="The supplied policy version is not the accepted outdoor-road 5K policy.",
            missing="accepted policy version",
            alternatives=("use_accepted_outdoor_5k_policy",),
        )
    if not _eligible_goal_and_population(generation_input):
        return _no_plan(
            code="unsupported_goal_or_population",
            input_hash=input_hash,
            statistics=statistics,
            rule="eligible_goal_and_population",
            reason="The goal or stated population is outside the accepted pilot.",
            missing="eligible outdoor-road 5K goal and population confirmation",
            alternatives=("use_baseline_or_consistency_guidance",),
        )
    if generation_input.constraints.safety_stop:
        return _no_plan(
            code="safety_stop",
            input_hash=input_hash,
            statistics=statistics,
            rule="athlete_reported_safety_stop",
            reason="The athlete reported a current safety stop.",
            missing=None,
            alternatives=("defer_plan_generation", "use_non_medical_safety_guidance"),
        )
    if (
        not generation_input.baseline_current
        or not generation_input.baseline_snapshot_id
        or generation_input.baseline_evidence_date is None
    ):
        return _no_plan(
            code="insufficient_or_stale_baseline",
            input_hash=input_hash,
            statistics=statistics,
            rule="current_qualified_baseline",
            reason="A current qualified 5K baseline is required before generation.",
            missing="current qualified 5K baseline",
            alternatives=(
                "refresh_qualified_5k_baseline",
                "defer_plan_generation",
            ),
        )
    if _target_is_too_close(generation_input.goal, generation_input.block_start):
        return _no_plan(
            code="insufficient_goal_horizon",
            input_hash=input_hash,
            statistics=statistics,
            rule="goal_target_and_feasibility",
            reason="The target event or same-protocol test is less than eight days away.",
            missing=None,
            alternatives=(
                "revise_target_time_or_date",
                "defer_plan_generation",
            ),
        )
    history_error = _history_error(statistics, generation_input.athlete_today)
    if history_error is not None:
        return _no_plan(
            code="insufficient_recent_history",
            input_hash=input_hash,
            statistics=statistics,
            rule="recent_history_completeness",
            reason=history_error,
            missing="three usable completed running weeks and a run within fourteen days",
            alternatives=("future_consistency_or_base_policy",),
        )
    # The three-day envelope is an accepted v1 policy guardrail, not a
    # physiological threshold or a claim about an individual athlete.
    if statistics.recent_modal_running_frequency < 3:
        return _no_plan(
            code="unsupported_frequency",
            input_hash=input_hash,
            statistics=statistics,
            rule="recent_history_frequency",
            reason=(
                "The recent modal completed-running frequency is below the "
                "three-day policy envelope."
            ),
            missing=None,
            alternatives=("future_consistency_or_base_policy",),
        )
    constraint_error = _constraint_error(generation_input.constraints)
    if constraint_error is not None:
        code, rule, reason, alternatives = constraint_error
        return _no_plan(
            code=code,
            input_hash=input_hash,
            statistics=statistics,
            rule=rule,
            reason=reason,
            missing=None,
            alternatives=alternatives,
        )

    schedule = _build_schedule(generation_input, statistics)
    if schedule is None:
        return _no_plan(
            code="no_schedule_within_envelope",
            input_hash=input_hash,
            statistics=statistics,
            rule="schedule_frequency_and_spacing",
            reason="The stated availability, reserved dates, and dose limits cannot form a valid weekly schedule.",
            missing="a schedule with three to five bounded running days",
            alternatives=("revise_stated_availability", "defer_plan_generation"),
        )
    validation_error = _validate_schedule(
        schedule,
        generation_input=generation_input,
        statistics=statistics,
    )
    if validation_error is not None:
        code, rule, reason = validation_error
        return _no_plan(
            code=code,
            input_hash=input_hash,
            statistics=statistics,
            rule=rule,
            reason=reason,
            missing=None,
            alternatives=("revise_stated_availability", "defer_plan_generation"),
        )
    horizon_end = _schedule_end_exclusive(generation_input) - timedelta(days=1)
    plan = GeneratedOutdoor5KPlan(
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        generator_version=OUTDOOR_5K_GENERATOR_VERSION,
        horizon_start=generation_input.block_start,
        horizon_end=horizon_end,
        reassessment_dates=tuple(
            generation_input.block_start
            + timedelta(days=OUTDOOR_5K_REASSESSMENT_DAYS * index)
            for index in range(4)
            if generation_input.block_start
            + timedelta(days=OUTDOOR_5K_REASSESSMENT_DAYS * index)
            <= horizon_end
        ),
        history_statistics=statistics,
        weeks=schedule,
    )
    return Outdoor5KGenerationResult(
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        generator_version=OUTDOOR_5K_GENERATOR_VERSION,
        science_decision_id=OUTDOOR_5K_SCIENCE_DECISION_ID,
        code="ready",
        deterministic_input_hash=input_hash,
        plan=plan,
        history_statistics=statistics,
        failed_rule_id=None,
        observed_or_stated_reason=None,
        uncertainty_or_missing_field=None,
        alternatives=(
            "accept_history_anchored_block_with_feasibility_unknown",
            "revise_target_time_or_date",
            "defer_plan_generation",
        ),
    )


def deterministic_input_hash(generation_input: Outdoor5KGenerationInput) -> str:
    """Return the stable replay hash for the complete versioned input."""
    payload = {
        "policy_version": generation_input.policy_version,
        "generator_version": OUTDOOR_5K_GENERATOR_VERSION,
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "goal": {
            "goal_kind": generation_input.goal.goal_kind,
            "distance": generation_input.goal.distance,
            "outdoor_road_confirmed": generation_input.goal.outdoor_road_confirmed,
            "target_time_sec": generation_input.goal.target_time_sec,
            "target_event_date": _date_or_none(generation_input.goal.target_event_date),
        },
        "baseline": {
            "current": generation_input.baseline_current,
            "snapshot_id": generation_input.baseline_snapshot_id,
            "evidence_date": _date_or_none(generation_input.baseline_evidence_date),
        },
        "history": [
            {
                "activity_id": item.activity_id,
                "observed_date": item.observed_date.isoformat(),
                "duration_min": item.duration_min,
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
        "reserved_dates": sorted(item.isoformat() for item in generation_input.reserved_dates),
        "constraints": {
            "age_18_or_older": generation_input.constraints.age_18_or_older,
            "self_coached_recreational_road_runner": (
                generation_input.constraints.self_coached_recreational_road_runner
            ),
            "can_complete_5k": generation_input.constraints.can_complete_5k,
            "safety_stop": generation_input.constraints.safety_stop,
            "available_weekdays": tuple(
                sorted(generation_input.constraints.available_weekdays)
            ),
            "maximum_session_duration_min": (
                generation_input.constraints.maximum_session_duration_min
            ),
            "unavailable_dates": sorted(
                item.isoformat()
                for item in generation_input.constraints.unavailable_dates
            ),
            "preferred_longest_run_weekday": (
                generation_input.constraints.preferred_longest_run_weekday
            ),
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def serialize_workout_structure(workout: GeneratedWorkout) -> dict[str, Any]:
    """Return the portable v1 workout structure for a generated workout."""
    return {"steps": [_serialize_step(step) for step in workout.steps]}


def serialize_generation_input(
    generation_input: Outdoor5KGenerationInput,
) -> dict[str, Any]:
    """Return an audit-safe JSON snapshot of the typed input."""
    payload = asdict(generation_input)
    return _json_safe_dates(payload)


def serialize_generation_result(
    result: Outdoor5KGenerationResult,
) -> dict[str, Any]:
    """Return a JSON-safe policy outcome without changing its authority."""
    payload = asdict(result)
    return _json_safe_dates(payload)


def _eligible_goal_and_population(generation_input: Outdoor5KGenerationInput) -> bool:
    constraints = generation_input.constraints
    goal = generation_input.goal
    return (
        goal.goal_kind == "performance_5k"
        and str(goal.distance or "").casefold() == "5k"
        and goal.outdoor_road_confirmed
        and constraints.age_18_or_older
        and constraints.self_coached_recreational_road_runner
        and constraints.can_complete_5k
    )


def _target_is_too_close(goal: Outdoor5KGoal, block_start: date) -> bool:
    if goal.target_event_date is None:
        return False
    return (goal.target_event_date - block_start).days < 8


def _history_error(
    statistics: RecentHistoryStatistics,
    athlete_today: date,
) -> str | None:
    if statistics.usable_completed_weeks < 3:
        return "Fewer than three usable completed running weeks were observed."
    if statistics.latest_run_date is None:
        return "No completed recent running observation is available."
    if (athlete_today - statistics.latest_run_date).days > 14:
        return "The latest completed run is more than fourteen days old."
    return None


def _constraint_error(
    constraints: PlanGenerationConstraints,
) -> tuple[str, str, str, tuple[str, ...]] | None:
    weekdays = constraints.available_weekdays
    if len(set(weekdays)) != len(weekdays) or any(
        day < 0 or day > 6 for day in weekdays
    ):
        return (
            "clarification_required",
            "stated_availability_and_constraints",
            "Available running days must be unique weekday values from zero through six.",
            ("clarify_available_running_days",),
        )
    if len(weekdays) > 5:
        return (
            "clarification_required",
            "stated_availability_and_constraints",
            "More than five requested running days is outside the v1 envelope.",
            ("clarify_available_running_days",),
        )
    if len(weekdays) < 3:
        return (
            "unsupported_frequency",
            "stated_availability_and_constraints",
            "Fewer than three stated running days cannot support this policy.",
            ("future_consistency_or_base_policy",),
        )
    if constraints.maximum_session_duration_min <= 0:
        return (
            "clarification_required",
            "stated_availability_and_constraints",
            "Maximum session duration must be a positive number of minutes.",
            ("clarify_maximum_session_duration",),
        )
    preferred = constraints.preferred_longest_run_weekday
    if preferred is not None and (
        preferred not in weekdays or preferred < 0 or preferred > 6
    ):
        return (
            "contradictory_constraints",
            "stated_availability_and_constraints",
            "The preferred longest-run day is not one of the available running days.",
            ("revise_stated_availability",),
        )
    return None


def _build_schedule(
    generation_input: Outdoor5KGenerationInput,
    statistics: RecentHistoryStatistics,
) -> tuple[GeneratedWeek, ...] | None:
    requested_frequency = len(generation_input.constraints.available_weekdays)
    modal_frequency = statistics.recent_modal_running_frequency
    if modal_frequency < 3:
        return None
    frequency = min(requested_frequency, modal_frequency, 5)
    if frequency < 3:
        return None
    session_limit = min(
        generation_input.constraints.maximum_session_duration_min,
        statistics.recent_longest_completed_run_minutes,
    )
    if session_limit <= 0:
        return None
    blocked_dates = set(generation_input.reserved_dates) | set(
        generation_input.constraints.unavailable_dates
    )
    if generation_input.goal.target_event_date is not None:
        blocked_dates.add(generation_input.goal.target_event_date)
    weekly_cap = min(
        statistics.recent_typical_complete_week_minutes,
        statistics.recent_maximum_complete_week_minutes,
        session_limit * frequency,
    )
    normal_base_duration = min(session_limit, weekly_cap // frequency)
    weeks: list[GeneratedWeek] = []
    schedule_end = _schedule_end_exclusive(generation_input)
    for index in range(4):
        week_start = generation_input.block_start + timedelta(days=index * 7)
        if week_start >= schedule_end:
            break
        dates = tuple(
            current
            for current in (
                week_start + timedelta(days=offset) for offset in range(7)
            )
            if current.weekday() in generation_input.constraints.available_weekdays
            and current not in blocked_dates
            and current < schedule_end
        )
        if len(dates) < frequency:
            return None
        selected_dates = _select_schedule_dates(
            dates,
            frequency=frequency,
            preferred_longest_run_weekday=(
                generation_input.constraints.preferred_longest_run_weekday
            ),
        )
        if selected_dates is None:
            return None
        is_taper = _is_taper_week(
            generation_input,
            reassessment_date=week_start,
        )
        longest_date = _longest_date(
            selected_dates,
            generation_input.constraints.preferred_longest_run_weekday,
        )
        normal_workouts = _week_workouts(
            selected_dates,
            base_duration=normal_base_duration,
            longest_date=longest_date,
            quality_count=_quality_count(
                selected_dates,
                frequency=frequency,
                base_duration=normal_base_duration,
                session_limit=session_limit,
                longest_date=longest_date,
                week_index=index,
            ),
            week_index=index,
        )
        weeks.append(
            GeneratedWeek(
                week_number=index + 1,
                is_taper=is_taper,
                workouts=normal_workouts,
            )
        )
    for index, week in enumerate(weeks):
        if not week.is_taper:
            continue
        dates = tuple(item.scheduled_date for item in week.workouts)
        longest_date = _longest_date(
            dates,
            generation_input.constraints.preferred_longest_run_weekday,
        )
        # V1 selects 50% inside its accepted 41–60% taper guardrail; this is
        # not a universal taper prescription (see the accepted SDR).
        workouts = _taper_workouts(
            dates,
            normal_workouts=week.workouts,
            frequency=frequency,
            session_limit=session_limit,
            normal_base_duration=normal_base_duration,
            longest_date=longest_date,
            week_index=index,
        )
        if workouts is None:
            return None
        weeks[index] = GeneratedWeek(
            week_number=week.week_number,
            is_taper=True,
            workouts=workouts,
        )
    return tuple(weeks)


def _select_schedule_dates(
    dates: Sequence[date],
    *,
    frequency: int,
    preferred_longest_run_weekday: int | None,
) -> tuple[date, ...] | None:
    ordered = tuple(sorted(dates))
    if len(ordered) < frequency:
        return None
    if preferred_longest_run_weekday is None:
        return ordered[:frequency]
    preferred = tuple(
        item for item in ordered if item.weekday() == preferred_longest_run_weekday
    )
    if not preferred:
        return None
    selected = tuple(
        sorted((preferred[0],) + tuple(item for item in ordered if item != preferred[0])[: frequency - 1])
    )
    return selected


def _longest_date(
    dates: Sequence[date],
    preferred_longest_run_weekday: int | None,
) -> date:
    if preferred_longest_run_weekday is not None:
        matching = tuple(
            item for item in dates if item.weekday() == preferred_longest_run_weekday
        )
        if matching:
            return matching[0]
    return max(dates)


def _quality_count(
    dates: Sequence[date],
    *,
    frequency: int,
    base_duration: int,
    session_limit: int,
    longest_date: date,
    week_index: int,
) -> int:
    quality_dates = _quality_dates(dates, longest_date, quality_count=1)
    if not quality_dates:
        return 0
    quality_date = quality_dates[0]
    position = tuple(sorted(dates)).index(quality_date)
    template_id = (
        "outdoor-5k-controlled-quality-v1"
        if (week_index + position) % 2 == 0
        else "outdoor-5k-short-interval-quality-v1"
    )
    template = next(
        item
        for item in OUTDOOR_5K_TEMPLATE_GUARDRAILS
        if item.template_id == template_id
    )
    required_minutes = _steps_duration(template.steps)
    if session_limit < required_minutes:
        return 0
    low_intensity_minutes = (frequency - 1) * base_duration
    total_minutes = low_intensity_minutes + required_minutes
    if (
        low_intensity_minutes <= 0
        or low_intensity_minutes / total_minutes < 0.70
    ):
        return 0
    # The accepted envelope permits up to two quality days but does not require
    # two. V1 chooses the simplest one-session template when it fits.
    return 1


def _week_workouts(
    dates: Sequence[date],
    *,
    base_duration: int,
    longest_date: date,
    quality_count: int,
    week_index: int,
    durations_by_date: Mapping[date, int] | None = None,
) -> tuple[GeneratedWorkout, ...]:
    quality_dates = _quality_dates(dates, longest_date, quality_count)
    workouts: list[GeneratedWorkout] = []
    for position, scheduled_date in enumerate(sorted(dates)):
        duration = (durations_by_date or {}).get(scheduled_date, base_duration)
        if scheduled_date in quality_dates:
            template_id = (
                "outdoor-5k-controlled-quality-v1"
                if (week_index + position) % 2 == 0
                else "outdoor-5k-short-interval-quality-v1"
            )
            workouts.append(_quality_workout(template_id, scheduled_date))
        elif scheduled_date == longest_date:
            workouts.append(
                _simple_workout(
                    template_id="outdoor-5k-longest-easy-v1",
                    scheduled_date=scheduled_date,
                    workout_type="longest_easy",
                    duration=duration,
                )
            )
        else:
            workouts.append(
                _simple_workout(
                    template_id="outdoor-5k-easy-v1",
                    scheduled_date=scheduled_date,
                    workout_type="easy",
                    duration=duration,
                )
            )
    return tuple(workouts)


def _taper_workouts(
    dates: Sequence[date],
    *,
    normal_workouts: Sequence[GeneratedWorkout],
    frequency: int,
    session_limit: int,
    normal_base_duration: int,
    longest_date: date,
    week_index: int,
) -> tuple[GeneratedWorkout, ...] | None:
    """Build the nearest integer taper schedule within the accepted volume range."""
    own_normal_minutes = sum(
        item.planned_duration_min for item in normal_workouts
    )
    candidates: list[tuple[int, int, tuple[GeneratedWorkout, ...]]] = []
    for base_duration in range(1, normal_base_duration + 1):
        workouts = _week_workouts(
            dates,
            base_duration=base_duration,
            longest_date=longest_date,
            quality_count=_quality_count(
                dates,
                frequency=frequency,
                base_duration=base_duration,
                session_limit=session_limit,
                longest_date=longest_date,
                week_index=week_index,
            ),
            week_index=week_index,
        )
        taper_minutes = sum(item.planned_duration_min for item in workouts)
        if _is_taper_volume_within_bounds(taper_minutes, own_normal_minutes):
            candidates.append((base_duration, taper_minutes, workouts))
    if candidates:
        return min(
            candidates,
            key=lambda candidate: (
                -sum(
                    item.intensity_bucket == "quality"
                    for item in candidate[2]
                ),
                abs(2 * candidate[1] - own_normal_minutes),
                candidate[0],
            ),
        )[2]

    minimum_minutes = (40 * own_normal_minutes + 99) // 100
    maximum_minutes = (59 * own_normal_minutes) // 100
    target_minutes = min(
        max((own_normal_minutes + 1) // 2, minimum_minutes),
        maximum_minutes,
    )
    if not (
        minimum_minutes <= target_minutes <= maximum_minutes
        and frequency <= target_minutes <= frequency * normal_base_duration
    ):
        return None
    base_duration, extra_minutes = divmod(target_minutes, frequency)
    duration_dates = (longest_date,) + tuple(
        item for item in sorted(dates) if item != longest_date
    )
    durations_by_date = {
        scheduled_date: base_duration + int(index < extra_minutes)
        for index, scheduled_date in enumerate(duration_dates)
    }
    return _week_workouts(
        dates,
        base_duration=base_duration,
        longest_date=longest_date,
        quality_count=0,
        week_index=week_index,
        durations_by_date=durations_by_date,
    )


def _quality_dates(
    dates: Sequence[date],
    longest_date: date,
    quality_count: int,
) -> tuple[date, ...]:
    if quality_count <= 0:
        return ()
    candidates = tuple(item for item in sorted(dates) if item != longest_date)
    selected: list[date] = []
    for candidate in candidates:
        if all((candidate - prior).days >= 2 for prior in selected):
            selected.append(candidate)
        if len(selected) == quality_count:
            return tuple(selected)
    return tuple(selected)


def _simple_workout(
    *,
    template_id: str,
    scheduled_date: date,
    workout_type: str,
    duration: int,
) -> GeneratedWorkout:
    return GeneratedWorkout(
        template_id=template_id,
        scheduled_date=scheduled_date,
        workout_type=workout_type,
        intensity_bucket="low",
        planned_duration_min=duration,
        steps=(
            WorkoutStep(
                kind="step",
                phase="other",
                duration_min=duration,
            ),
        ),
    )


def _quality_workout(template_id: str, scheduled_date: date) -> GeneratedWorkout:
    template = next(
        (
            candidate
            for candidate in OUTDOOR_5K_TEMPLATE_GUARDRAILS
            if candidate.template_id == template_id
        ),
        None,
    )
    if template is None:
        raise ValueError("unknown outdoor 5K workout template")
    return GeneratedWorkout(
        template_id=template_id,
        scheduled_date=scheduled_date,
        workout_type=template.workout_type,
        intensity_bucket="quality",
        planned_duration_min=_steps_duration(template.steps),
        steps=template.steps,
    )


def _is_taper_volume_within_bounds(
    taper_minutes: int,
    normal_minutes: int,
) -> bool:
    """Return whether the taper reduces normal scheduled volume by 41–60%."""
    return (
        normal_minutes > 0
        and 41 * normal_minutes
        <= 100 * (normal_minutes - taper_minutes)
        <= 60 * normal_minutes
    )


def _validate_schedule(
    weeks: Sequence[GeneratedWeek],
    *,
    generation_input: Outdoor5KGenerationInput,
    statistics: RecentHistoryStatistics,
) -> tuple[str, str, str] | None:
    expected_frequency = min(
        len(generation_input.constraints.available_weekdays),
        statistics.recent_modal_running_frequency,
        5,
    )
    session_limit = min(
        generation_input.constraints.maximum_session_duration_min,
        statistics.recent_longest_completed_run_minutes,
    )
    weekly_cap = min(
        statistics.recent_typical_complete_week_minutes,
        statistics.recent_maximum_complete_week_minutes,
        session_limit * expected_frequency,
    )
    normal_base_duration = min(session_limit, weekly_cap // expected_frequency)
    taper_start = _taper_start(generation_input)
    for week in weeks:
        workouts = week.workouts
        if not 3 <= len(workouts) <= 5 or len(workouts) != expected_frequency:
            return (
                "unsupported_frequency",
                "schedule_frequency_and_spacing",
                "The generated running-day frequency is outside the accepted envelope.",
            )
        if any(
            item.planned_duration_min != _steps_duration(item.steps)
            for item in workouts
        ):
            return (
                "no_schedule_within_envelope",
                "weekly_and_session_duration_bounds",
                "A generated workout summary does not match its structured duration.",
            )
        total_minutes = sum(_steps_duration(item.steps) for item in workouts)
        cap = min(
            statistics.recent_typical_complete_week_minutes,
            statistics.recent_maximum_complete_week_minutes,
        )
        if total_minutes > cap:
            return (
                "no_schedule_within_envelope",
                "weekly_and_session_duration_bounds",
                "The generated week exceeds the history-anchored minute limit.",
            )
        if week.is_taper:
            dates = tuple(item.scheduled_date for item in workouts)
            normal_reference_minutes = sum(
                _steps_duration(item.steps)
                for item in _week_workouts(
                    dates,
                    base_duration=normal_base_duration,
                    longest_date=_longest_date(
                        dates,
                        generation_input.constraints.preferred_longest_run_weekday,
                    ),
                    quality_count=_quality_count(
                        dates,
                        frequency=expected_frequency,
                        base_duration=normal_base_duration,
                        session_limit=session_limit,
                        longest_date=_longest_date(
                            dates,
                            generation_input.constraints.preferred_longest_run_weekday,
                        ),
                        week_index=week.week_number - 1,
                    ),
                    week_index=week.week_number - 1,
                )
            )
            if not _is_taper_volume_within_bounds(
                total_minutes,
                normal_reference_minutes,
            ):
                return (
                    "no_schedule_within_envelope",
                    "taper_volume_reduction",
                    "Generated taper volume is outside the accepted 41–60% reduction range.",
                )
        if taper_start is not None and any(
            item.scheduled_date >= taper_start for item in workouts
        ) and not week.is_taper:
            return (
                "no_schedule_within_envelope",
                "taper_eligibility",
                "A normal workout was scheduled inside the pre-event taper window.",
            )
        event_date = generation_input.goal.target_event_date
        if event_date is not None and any(
            item.scheduled_date >= event_date for item in workouts
        ):
            return (
                "no_schedule_within_envelope",
                "taper_eligibility",
                "A workout was scheduled on or after the target event date.",
            )
        if any(
            _steps_duration(item.steps)
            > statistics.recent_longest_completed_run_minutes
            or _steps_duration(item.steps)
            > generation_input.constraints.maximum_session_duration_min
            for item in workouts
        ):
            return (
                "no_schedule_within_envelope",
                "weekly_and_session_duration_bounds",
                "A generated session exceeds a stated or observed duration bound.",
            )
        if sum(item.workout_type == "longest_easy" for item in workouts) > 1:
            return (
                "no_schedule_within_envelope",
                "weekly_and_session_duration_bounds",
                "More than one longest easy session was generated in a week.",
            )
        quality_dates = tuple(
            item.scheduled_date
            for item in workouts
            if item.workout_type in _QUALITY_SESSION_TYPES
        )
        if len(quality_dates) > 2 or any(
            (right - left).days < 2
            for left, right in zip(quality_dates, quality_dates[1:])
        ):
            return (
                "no_schedule_within_envelope",
                "schedule_frequency_and_spacing",
                "Quality sessions are consecutive or exceed the weekly ceiling.",
            )
        low_minutes = sum(
            _steps_duration(item.steps)
            for item in workouts
            if item.workout_type in _LOW_INTENSITY_SESSION_TYPES
        )
        if total_minutes <= 0 or low_minutes / total_minutes < 0.70:
            return (
                "no_schedule_within_envelope",
                "intensity_distribution",
                "Planned low-intensity minutes fall below the accepted floor.",
            )
    return None


def _is_taper_week(
    generation_input: Outdoor5KGenerationInput,
    *,
    reassessment_date: date,
) -> bool:
    taper_start = _taper_start(generation_input)
    event_date = generation_input.goal.target_event_date
    return (
        taper_start is not None
        and event_date is not None
        and taper_start <= reassessment_date < event_date
    )


def _schedule_end_exclusive(generation_input: Outdoor5KGenerationInput) -> date:
    """Return the first unscheduled day of this bounded proposal."""
    block_end = generation_input.block_start + timedelta(days=OUTDOOR_5K_BLOCK_DAYS)
    event_date = generation_input.goal.target_event_date
    if event_date is None:
        return block_end
    return min(block_end, event_date)


def _taper_start(generation_input: Outdoor5KGenerationInput) -> date | None:
    """Return the accepted pre-event taper anchor, if this block owns one."""
    event_date = generation_input.goal.target_event_date
    if event_date is None:
        return None
    for index in range(4):
        reassessment_date = generation_input.block_start + timedelta(
            days=OUTDOOR_5K_REASSESSMENT_DAYS * index
        )
        delta = (event_date - reassessment_date).days
        if 8 <= delta <= 14:
            return reassessment_date
    return None


def _steps_duration(steps: Sequence[WorkoutStep]) -> int:
    """Return the exact integer minutes represented by a structured template."""
    total = 0
    for step in steps:
        if step.kind == "repeat":
            total += int(step.repetitions or 0) * _steps_duration(step.steps)
        else:
            total += int(step.duration_min or 0)
    return total


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
    rule: str,
    reason: str,
    missing: str | None,
    alternatives: tuple[str, ...],
) -> Outdoor5KGenerationResult:
    if code not in _ALLOWED_RESULT_CODES or code == "ready":
        raise ValueError("code must be an accepted typed no-plan code")
    return Outdoor5KGenerationResult(
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        generator_version=OUTDOOR_5K_GENERATOR_VERSION,
        science_decision_id=OUTDOOR_5K_SCIENCE_DECISION_ID,
        code=code,
        deterministic_input_hash=input_hash,
        plan=None,
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
    if isinstance(value, Mapping):
        return {str(key): _json_safe_dates(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe_dates(item) for item in value]
    if isinstance(value, list):
        return [_json_safe_dates(item) for item in value]
    return value
