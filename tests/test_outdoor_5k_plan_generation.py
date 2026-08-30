"""Tests for the deterministic outdoor-road 5K policy service."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

from tests.test_plan_proposals import proposal_client

from analysis.outdoor_5k_plan_generation import (
    OUTDOOR_5K_POLICY_VERSION,
    Outdoor5KGenerationInput,
    Outdoor5KGoal,
    PlanGenerationConstraints,
    RunningHistoryObservation,
    generate_outdoor_5k_plan,
)


def _history(today: date) -> tuple[RunningHistoryObservation, ...]:
    """Return four complete, three-run weeks ending before ``today``."""
    current_week = today - timedelta(days=today.weekday())
    activities: list[RunningHistoryObservation] = []
    for week in range(1, 5):
        week_start = current_week - timedelta(days=7 * week)
        for offset, duration in ((0, 45.0), (2, 50.0), (5, 55.0)):
            activities.append(
                RunningHistoryObservation(
                    activity_id=f"run-{week}-{offset}",
                    observed_date=week_start + timedelta(days=offset),
                    duration_min=duration,
                    source="garmin",
                )
            )
    return tuple(activities)


def _three_run_history(
    today: date,
    *,
    duration_min: float,
) -> tuple[RunningHistoryObservation, ...]:
    """Return four complete three-run weeks at one explicit duration anchor."""
    current_week = today - timedelta(days=today.weekday())
    activities: list[RunningHistoryObservation] = []
    for week in range(1, 5):
        week_start = current_week - timedelta(days=7 * week)
        for offset in (0, 2, 5):
            activities.append(
                RunningHistoryObservation(
                    activity_id=f"anchored-{duration_min}-{week}-{offset}",
                    observed_date=week_start + timedelta(days=offset),
                    duration_min=duration_min,
                    source="garmin",
                )
            )
    return tuple(activities)


def _input(*, baseline_current: bool = True) -> Outdoor5KGenerationInput:
    today = date(2026, 8, 13)
    return Outdoor5KGenerationInput(
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        athlete_today=today,
        block_start=today + timedelta(days=1),
        goal=Outdoor5KGoal(
            goal_kind="performance_5k",
            distance="5k",
            outdoor_road_confirmed=True,
            target_time_sec=1500,
            target_event_date=None,
        ),
        baseline_current=baseline_current,
        baseline_snapshot_id="baseline-snapshot-1" if baseline_current else None,
        baseline_evidence_date=today - timedelta(days=3) if baseline_current else None,
        history=_history(today),
        reserved_dates=(),
        constraints=PlanGenerationConstraints(
            age_18_or_older=True,
            self_coached_recreational_road_runner=True,
            can_complete_5k=True,
            safety_stop=False,
            available_weekdays=(0, 2, 5),
            maximum_session_duration_min=60,
            unavailable_dates=(),
            preferred_longest_run_weekday=5,
        ),
    )


def test_generation_is_deterministic_and_keeps_the_accepted_envelope() -> None:
    """The same versioned input produces one conservative, valid schedule."""
    first = generate_outdoor_5k_plan(_input())
    replay = generate_outdoor_5k_plan(_input())

    assert first.code == "ready"
    assert first.plan is not None
    assert replay == first
    assert first.policy_version == OUTDOOR_5K_POLICY_VERSION
    assert first.deterministic_input_hash == replay.deterministic_input_hash
    assert first.plan.horizon_end - first.plan.horizon_start == timedelta(days=27)
    assert len(first.plan.reassessment_dates) == 4

    for week in first.plan.weeks:
        running = week.workouts
        low_minutes = sum(
            workout.planned_duration_min
            for workout in running
            if workout.intensity_bucket == "low"
        )
        total_minutes = sum(workout.planned_duration_min for workout in running)
        quality_dates = [
            workout.scheduled_date
            for workout in running
            if workout.intensity_bucket == "quality"
        ]
        assert len(running) == 3
        assert total_minutes <= 150
        assert all(workout.planned_duration_min <= 55 for workout in running)
        assert low_minutes / total_minutes >= 0.70
        assert all(
            (right - left).days >= 2
            for left, right in zip(quality_dates, quality_dates[1:])
        )
        assert sum(
            workout.workout_type == "longest_easy" for workout in running
        ) <= 1


def test_modal_history_frequency_below_three_is_typed_unsupported_frequency() -> None:
    """Two-run completed weeks fail with the explicit accepted frequency code."""
    base = _input()
    current_week = base.athlete_today - timedelta(
        days=base.athlete_today.weekday()
    )
    two_run_history = tuple(
        RunningHistoryObservation(
            activity_id=f"two-run-{week}-{offset}",
            observed_date=current_week - timedelta(days=7 * week - offset),
            duration_min=30,
            source="garmin",
        )
        for week in range(1, 5)
        for offset in (0, 3)
    )

    result = generate_outdoor_5k_plan(replace(base, history=two_run_history))

    assert result.code == "unsupported_frequency"
    assert result.plan is None
    assert result.failed_rule_id == "recent_history_frequency"


def test_policy_valid_short_sessions_do_not_hit_an_invented_duration_floor() -> None:
    """A history-anchored 10-minute all-easy schedule remains policy-valid."""
    base = _input()
    result = generate_outdoor_5k_plan(
        replace(
            base,
            history=_three_run_history(base.athlete_today, duration_min=10),
            constraints=replace(
                base.constraints,
                maximum_session_duration_min=10,
            ),
        )
    )

    assert result.code == "ready"
    assert result.plan is not None
    assert all(
        workout.workout_type in {"easy", "longest_easy"}
        and workout.planned_duration_min == 10
        for week in result.plan.weeks
        for workout in week.workouts
    )


def test_three_by_thirty_history_can_generate_a_history_anchored_all_easy_plan() -> None:
    """Quality is optional when a 3×30 dose cannot retain the 70% easy floor."""
    base = _input()
    result = generate_outdoor_5k_plan(
        replace(
            base,
            history=_three_run_history(base.athlete_today, duration_min=30),
            constraints=replace(
                base.constraints,
                maximum_session_duration_min=30,
            ),
        )
    )

    assert result.code == "ready"
    assert result.plan is not None
    assert result.history_statistics.recent_typical_complete_week_minutes == 90
    assert result.history_statistics.recent_longest_completed_run_minutes == 30
    for week in result.plan.weeks:
        workouts = week.workouts
        total_minutes = sum(item.planned_duration_min for item in workouts)
        easy_minutes = sum(
            item.planned_duration_min
            for item in workouts
            if item.workout_type in {"easy", "longest_easy"}
        )
        quality_dates = [
            item.scheduled_date
            for item in workouts
            if item.intensity_bucket == "quality"
        ]
        assert total_minutes == 90
        assert all(item.planned_duration_min <= 30 for item in workouts)
        assert easy_minutes / total_minutes >= 0.70
        assert len(quality_dates) <= 2
        assert all(
            (right - left).days >= 2
            for left, right in zip(quality_dates, quality_dates[1:])
        )


def _expanded_step_duration(step) -> int:
    """Return the exact duration represented by a generated structured step."""
    if step.kind == "repeat":
        return int(step.repetitions or 0) * sum(
            _expanded_step_duration(child) for child in step.steps
        )
    return int(step.duration_min or 0)


def _three_day_taper_input(event_offset: int) -> Outdoor5KGenerationInput:
    """Build a three-day schedule where a bounded taper retains quality."""
    base = _input()
    block_start = date(2026, 8, 17)
    history: list[RunningHistoryObservation] = []
    current_week = base.athlete_today - timedelta(days=base.athlete_today.weekday())
    for week in range(1, 5):
        week_start = current_week - timedelta(days=7 * week)
        for offset in (0, 1, 3, 5):
            history.append(
                RunningHistoryObservation(
                    activity_id=f"three-day-{week}-{offset}",
                    observed_date=week_start + timedelta(days=offset),
                    duration_min=120,
                    source="garmin",
                )
            )
    return replace(
        base,
        block_start=block_start,
        goal=replace(
            base.goal,
            target_event_date=block_start + timedelta(days=event_offset),
        ),
        history=tuple(history),
        constraints=replace(
            base.constraints,
            available_weekdays=(0, 1, 2),
            maximum_session_duration_min=120,
            preferred_longest_run_weekday=2,
        ),
    )


def test_generation_uses_exact_step_duration_and_stops_before_target_date() -> None:
    """Workout structures enforce duration and never schedule on or after race day."""
    generation_input = _three_day_taper_input(10)
    result = generate_outdoor_5k_plan(generation_input)

    assert result.code == "ready"
    assert result.plan is not None
    target_date = generation_input.goal.target_event_date
    assert target_date is not None
    all_workouts = [
        workout for week in result.plan.weeks for workout in week.workouts
    ]
    assert all(workout.scheduled_date < target_date for workout in all_workouts)
    assert all(
        workout.planned_duration_min
        == sum(_expanded_step_duration(step) for step in workout.steps)
        for workout in all_workouts
    )
    assert all(
        workout.planned_duration_min
        <= generation_input.constraints.maximum_session_duration_min
        for workout in all_workouts
    )


def test_taper_covers_the_full_pre_event_window_and_keeps_quality_when_fit() -> None:
    """An accepted 8–14-day taper runs through race eve without post-race work."""
    first_input = _three_day_taper_input(10)
    reassessment_input = _three_day_taper_input(17)
    first_window = generate_outdoor_5k_plan(first_input)
    reassessment_window = generate_outdoor_5k_plan(reassessment_input)

    assert first_window.plan is not None
    assert reassessment_window.plan is not None
    assert [week.is_taper for week in first_window.plan.weeks] == [
        True,
        True,
    ]
    assert [week.is_taper for week in reassessment_window.plan.weeks] == [
        False,
        True,
        True,
    ]
    for result, generation_input in (
        (first_window, first_input),
        (reassessment_window, reassessment_input),
    ):
        assert result.plan is not None
        target_date = generation_input.goal.target_event_date
        assert target_date is not None
        assert result.plan.horizon_end == target_date - timedelta(days=1)
        assert all(
            workout.scheduled_date < target_date
            for week in result.plan.weeks
            for workout in week.workouts
        )
        assert all(
            sum(
                workout.intensity_bucket == "quality"
                for workout in week.workouts
            )
            == 1
            for week in result.plan.weeks
            if week.is_taper
        )


def test_eight_day_target_allows_a_target_truncated_partial_taper_week() -> None:
    """A valid Mon/Tue/Wed runner keeps the available Monday before a Tuesday event."""
    base = _input()
    block_start = date(2026, 8, 17)
    target_date = block_start + timedelta(days=8)
    result = generate_outdoor_5k_plan(
        replace(
            base,
            block_start=block_start,
            history=_three_run_history(base.athlete_today, duration_min=60),
            goal=replace(base.goal, target_event_date=target_date),
            constraints=replace(
                base.constraints,
                available_weekdays=(0, 1, 2),
                maximum_session_duration_min=60,
                preferred_longest_run_weekday=2,
            ),
        )
    )

    assert result.code == "ready"
    assert result.plan is not None
    assert [week.is_taper for week in result.plan.weeks] == [True, True]
    assert [
        [workout.scheduled_date for workout in week.workouts]
        for week in result.plan.weeks
    ] == [
        [block_start, block_start + timedelta(days=1), block_start + timedelta(days=2)],
        [block_start + timedelta(days=7)],
    ]
    final_taper_week = result.plan.weeks[-1]
    final_taper_minutes = sum(
        workout.planned_duration_min for workout in final_taper_week.workouts
    )

    assert final_taper_minutes == 30
    assert all(
        workout.intensity_bucket == "low"
        and workout.scheduled_date < target_date
        for workout in final_taper_week.workouts
    )
    assert 0.41 <= (60 - final_taper_minutes) / 60 <= 0.60


def test_taper_uses_half_the_normal_schedule_not_half_capacity() -> None:
    """The 50% taper target references generated normal work, not capacity."""
    base = _input()
    block_start = date(2026, 8, 17)
    target_date = block_start + timedelta(days=17)
    result = generate_outdoor_5k_plan(
        replace(
            base,
            block_start=block_start,
            history=_three_run_history(base.athlete_today, duration_min=61),
            goal=replace(base.goal, target_event_date=target_date),
            constraints=replace(
                base.constraints,
                available_weekdays=(0, 1, 2),
                maximum_session_duration_min=61,
                preferred_longest_run_weekday=2,
            ),
        )
    )

    assert result.code == "ready"
    assert result.plan is not None
    normal_reference = generate_outdoor_5k_plan(
        replace(
            base,
            block_start=block_start,
            history=_three_run_history(base.athlete_today, duration_min=61),
            constraints=replace(
                base.constraints,
                available_weekdays=(0, 1, 2),
                maximum_session_duration_min=61,
                preferred_longest_run_weekday=2,
            ),
        )
    )
    assert normal_reference.plan is not None
    taper_week = result.plan.weeks[1]
    taper_minutes = sum(
        workout.planned_duration_min for workout in taper_week.workouts
    )
    normal_minutes = sum(
        workout.planned_duration_min
        for workout in normal_reference.plan.weeks[1].workouts
    )
    taper_long_run = next(
        workout
        for workout in taper_week.workouts
        if workout.workout_type == "longest_easy"
    )

    assert taper_week.is_taper is True
    assert normal_minutes == 150
    assert taper_minutes == 75
    assert abs(2 * taper_minutes - normal_minutes) == 0
    assert 0.41 <= (normal_minutes - taper_minutes) / normal_minutes <= 0.60
    assert taper_long_run.planned_duration_min == 25
    assert all(
        workout.scheduled_date < target_date
        for week in result.plan.weeks
        for workout in week.workouts
    )
    assert target_date not in {
        workout.scheduled_date
        for week in result.plan.weeks
        for workout in week.workouts
    }


def test_taper_retains_short_interval_quality_when_the_envelope_allows() -> None:
    """A valid short interval must not be rejected by the longer template's floor."""
    base = _input()
    block_start = date(2026, 8, 17)
    target_date = block_start + timedelta(days=17)
    result = generate_outdoor_5k_plan(
        replace(
            base,
            block_start=block_start,
            history=_three_run_history(base.athlete_today, duration_min=66),
            goal=replace(base.goal, target_event_date=target_date),
            constraints=replace(
                base.constraints,
                available_weekdays=(0, 1, 2),
                maximum_session_duration_min=66,
                preferred_longest_run_weekday=2,
            ),
        )
    )

    assert result.code == "ready"
    assert result.plan is not None
    taper_week = result.plan.weeks[1]
    taper_minutes = sum(
        workout.planned_duration_min for workout in taper_week.workouts
    )
    low_minutes = sum(
        workout.planned_duration_min
        for workout in taper_week.workouts
        if workout.intensity_bucket == "low"
    )

    assert taper_week.is_taper is True
    assert taper_minutes == 94
    assert low_minutes / taper_minutes >= 0.70
    assert [
        workout.template_id
        for workout in taper_week.workouts
        if workout.intensity_bucket == "quality"
    ] == ["outdoor-5k-short-interval-quality-v1"]


def test_three_by_five_history_taper_stays_within_volume_guardrail() -> None:
    """Integer taper rounding keeps a valid low-volume plan within 41–60%."""
    base = _input()
    block_start = date(2026, 8, 17)
    result = generate_outdoor_5k_plan(
        replace(
            base,
            block_start=block_start,
            history=_three_run_history(base.athlete_today, duration_min=5),
            goal=replace(
                base.goal,
                target_event_date=block_start + timedelta(days=10),
            ),
            constraints=replace(
                base.constraints,
                maximum_session_duration_min=5,
                available_weekdays=(0, 1, 2),
                preferred_longest_run_weekday=2,
            ),
        )
    )

    assert result.code == "ready"
    assert result.plan is not None
    taper_week = result.plan.weeks[0]
    normal_minutes = 15
    taper_minutes = sum(
        workout.planned_duration_min for workout in taper_week.workouts
    )

    assert taper_week.is_taper is True
    assert normal_minutes == 15
    assert 0.41 <= (normal_minutes - taper_minutes) / normal_minutes <= 0.60


def test_stale_or_missing_baseline_is_a_typed_no_plan_outcome() -> None:
    """Baseline failure never extrapolates a performance-shaped plan."""
    result = generate_outdoor_5k_plan(_input(baseline_current=False))

    assert result.code == "insufficient_or_stale_baseline"
    assert result.plan is None
    assert result.failed_rule_id == "current_qualified_baseline"
    assert result.alternatives == (
        "refresh_qualified_5k_baseline",
        "defer_plan_generation",
    )


def _api_request(*, purpose: dict | None = None) -> dict:
    payload = {
        "age_18_or_older": True,
        "self_coached_recreational_road_runner": True,
        "can_complete_5k": True,
        "safety_stop": False,
        "outdoor_road_goal_confirmed": True,
        "available_weekdays": [0, 2, 5],
        "maximum_session_duration_min": 60,
        "unavailable_dates": [],
        "preferred_longest_run_weekday": 5,
    }
    if purpose is not None:
        payload["purpose"] = purpose
    return payload


def _api_today() -> date:
    """Match the API's explicit UTC athlete-date test contract."""
    return datetime.now(timezone.utc).date()


def _current_goal_purpose(client) -> dict:
    discovery = client.get("/api/plan/generation/capabilities")
    assert discovery.status_code == 200, discovery.text
    body = discovery.json()
    return {
        "capability_id": body["selected_capability"]["id"],
        "source": "current_goal",
        "expected_goal_id": body["current_goal"]["id"],
        "expected_goal_revision": body["current_goal"]["revision"],
    }


def _replace_goal(db_session, *, user_id: str, goal: dict) -> None:
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        row = db.query(UserConfig).filter(UserConfig.user_id == user_id).one()
        row.goal = goal
        db.commit()
    finally:
        db.close()


def _seed_api_context(db_session, user_id: str) -> None:
    """Seed an owner-scoped current baseline and four complete running weeks."""
    from analysis.goal_baseline import build_goal_baseline_goal
    from db.models import (
        Activity,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        UserConfig,
    )

    today = _api_today()
    goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
    }
    signature = build_goal_baseline_goal(goal).goal_signature
    current_week = today - timedelta(days=today.weekday())
    db = db_session.SessionLocal()
    try:
        db.add(UserConfig(
            user_id=user_id,
            goal=goal,
            source_options={"athlete_timezone": "UTC"},
        ))
        db.add(Activity(
            user_id=user_id,
            activity_id="current-baseline",
            date=today - timedelta(days=3),
            activity_type="running",
            distance_km=5.0,
            duration_sec=1500,
            source="garmin",
        ))
        for week in range(1, 5):
            week_start = current_week - timedelta(days=week * 7)
            for offset, duration in ((0, 45), (2, 50), (5, 55)):
                db.add(Activity(
                    user_id=user_id,
                    activity_id=f"history-{week}-{offset}",
                    date=week_start + timedelta(days=offset),
                    activity_type="running",
                    distance_km=8.0,
                    duration_sec=duration * 60,
                    source="garmin",
                ))
        db.add(GoalBaselineConfirmation(
            id="current-confirmation",
            lineage_id="current-confirmation-lineage",
            user_id=user_id,
            goal_signature=signature,
            goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
            version=1,
            activity_id="current-baseline",
            response="race",
            measured_5k=True,
            elapsed_timing_confirmed=True,
            request_fingerprint="a" * 64,
        ))
        db.add(GoalBaselineSnapshot(
            id="current-baseline-snapshot",
            lineage_id="current-baseline-snapshot-lineage",
            user_id=user_id,
            goal_signature=signature,
            goal_snapshot={"goal_kind": "performance_5k", "distance": "5k"},
            version=1,
            source_kind="history_confirmation",
            source_id="current-baseline",
            provenance="race",
            observed_date=today - timedelta(days=3),
            distance_km=5.0,
            elapsed_time_sec=1500,
            measured_5k=True,
            elapsed_timing_confirmed=True,
            qualification_status="direct_current",
            change_comparability="not_assessed",
            invalidators=[],
        ))
        db.commit()
    finally:
        db.close()


def test_api_generation_replays_idempotently_and_fences_stale_source(
    proposal_client,
) -> None:
    """The typed API creates only a proposal and enforces source/idempotency fences."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])

    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    readiness_body = readiness.json()
    assert readiness_body["result"]["code"] == "ready"

    request = {
        **_api_request(),
        "expected_source_revision": readiness_body["source_revision"],
        "idempotency_key": "outdoor-5k-generate-1",
    }
    created = client.post("/api/plan/outdoor-5k/generate", json=request)
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]
    assert proposal["state"] == "draft"
    assert client.delivery_calls == []

    replay = client.post("/api/plan/outdoor-5k/generate", json=request)
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["proposal"]["id"] == proposal["id"]

    changed_readiness = client.post(
        "/api/plan/outdoor-5k/readiness",
        json={**_api_request(), "maximum_session_duration_min": 59},
    )
    assert changed_readiness.status_code == 200, changed_readiness.text
    changed_key_reuse = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **_api_request(),
            "maximum_session_duration_min": 59,
            "expected_source_revision": changed_readiness.json()["source_revision"],
            "idempotency_key": "outdoor-5k-generate-1",
        },
    )
    assert changed_key_reuse.status_code == 409, changed_key_reuse.text
    assert changed_key_reuse.json()["detail"]["code"] == (
        "OUTDOOR_5K_IDEMPOTENCY_CONFLICT"
    )

    unchanged_regeneration = client.post(
        f"/api/plan/outdoor-5k/proposals/{proposal['id']}/regenerate",
        json={
            **_api_request(),
            "expected_source_revision": readiness_body["source_revision"],
            "expected_proposal_version": proposal["version"],
            "idempotency_key": "outdoor-5k-regenerate-unchanged",
        },
    )
    assert unchanged_regeneration.status_code == 409, unchanged_regeneration.text
    assert unchanged_regeneration.json()["detail"]["code"] == (
        "OUTDOOR_5K_REGENERATION_INPUT_UNCHANGED"
    )

    stale = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **_api_request(),
            "expected_source_revision": "0" * 64,
            "idempotency_key": "outdoor-5k-generate-stale",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "OUTDOOR_5K_SOURCE_REVISION_STALE"

    from db.models import Activity, Outdoor5KPlanGeneration, TrainingPlan

    db = db_session.SessionLocal()
    try:
        generation_audit = db.query(Outdoor5KPlanGeneration).one()
        assert generation_audit.science_decision_id == (
            "sdr-outdoor-5k-plan-generation-policy-v1"
        )
        assert generation_audit.evidence_review_ids
        assert generation_audit.evidence_claim_ids
        assert generation_audit.ai_explanation_present is False
        today = _api_today()
        current_week = today - timedelta(days=today.weekday())
        db.add(Activity(
            user_id=current_user["value"],
            activity_id="history-changed-after-proposal",
            date=current_week - timedelta(days=6),
            activity_type="running",
            distance_km=7.0,
            duration_sec=45 * 60,
            source="garmin",
        ))
        db.commit()
    finally:
        db.close()

    refreshed = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["source_revision"] != readiness_body["source_revision"]
    successor_request = {
        **_api_request(),
        "expected_source_revision": refreshed.json()["source_revision"],
        "expected_proposal_version": proposal["version"],
        "idempotency_key": "outdoor-5k-regenerate-2",
    }
    successor = client.post(
        f"/api/plan/outdoor-5k/proposals/{proposal['id']}/regenerate",
        json=successor_request,
    )
    assert successor.status_code == 201, successor.text
    assert successor.json()["proposal"]["version"] == proposal["version"] + 1
    assert successor.json()["proposal"]["supersedes_proposal_id"] == proposal["id"]

    db = db_session.SessionLocal()
    try:
        db.add(Activity(
            user_id=current_user["value"],
            activity_id="history-changed-after-successor",
            date=current_week - timedelta(days=5),
            activity_type="running",
            distance_km=7.0,
            duration_sec=45 * 60,
            source="garmin",
        ))
        db.commit()
    finally:
        db.close()

    successor_replay = client.post(
        f"/api/plan/outdoor-5k/proposals/{proposal['id']}/regenerate",
        json=successor_request,
    )
    assert successor_replay.status_code == 200, successor_replay.text
    assert successor_replay.json()["replayed"] is True
    assert successor_replay.json()["proposal"]["id"] == successor.json()["proposal"]["id"]

    db = db_session.SessionLocal()
    try:
        assert db.query(Outdoor5KPlanGeneration).count() == 2
        assert db.query(TrainingPlan).count() == 0
    finally:
        db.close()


def test_api_generation_persists_explicit_current_goal_provenance(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    purpose = _current_goal_purpose(client)
    request = _api_request(purpose=purpose)

    readiness = client.post("/api/plan/outdoor-5k/readiness", json=request)
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["purpose"] == {
        **purpose,
        "goal": {
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1500,
            "race_date": None,
        },
    }

    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **request,
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "explicit-current-goal-purpose",
        },
    )
    assert created.status_code == 201, created.text
    goal = created.json()["proposal"]["goal"]
    assert goal["purpose_source"] == "current_goal"
    assert goal["source_goal_id"] == purpose["expected_goal_id"]
    assert goal["source_goal_revision"] == purpose["expected_goal_revision"]


def test_api_generation_normalizes_legacy_target_time_alias(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "race_target_time_sec": 1475,
        },
    )
    purpose = _current_goal_purpose(client)
    request = _api_request(purpose=purpose)

    readiness = client.post("/api/plan/outdoor-5k/readiness", json=request)
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["purpose"]["goal"]["target_time_sec"] == 1475

    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **request,
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "legacy-target-time-alias",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["proposal"]["goal"]["target"]["target_time_sec"] == 1475

    from db.models import Outdoor5KPlanGeneration

    db = db_session.SessionLocal()
    try:
        audit = db.query(Outdoor5KPlanGeneration).one()
        assert audit.observed_input_snapshot["goal"]["target_time_sec"] == 1475
    finally:
        db.close()


def test_api_generation_fences_stale_current_goal_selection(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    purpose = _current_goal_purpose(client)
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1490,
        },
    )

    response = client.post(
        "/api/plan/outdoor-5k/readiness",
        json=_api_request(purpose=purpose),
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "PLAN_PURPOSE_STALE"


def test_api_generation_can_use_independent_5k_purpose_with_marathon_goal(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={
            "goal_kind": "race",
            "distance": "marathon",
            "race_date": "2027-04-18",
        },
    )
    request = _api_request(
        purpose={
            "capability_id": "outdoor_road_5k_v1",
            "source": "capability",
        },
    )

    readiness = client.post("/api/plan/outdoor-5k/readiness", json=request)
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["result"]["code"] == "ready"
    assert readiness.json()["purpose"]["source"] == "capability"
    assert readiness.json()["purpose"]["expected_goal_id"] is None
    assert readiness.json()["purpose"]["expected_goal_revision"] is None

    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **request,
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "independent-5k-purpose",
        },
    )
    assert created.status_code == 201, created.text
    goal = created.json()["proposal"]["goal"]
    assert goal["purpose_source"] == "capability"
    assert goal["source_goal_id"] is None
    assert goal["source_goal_revision"] is None
    assert goal["target"]["distance"] == "5k"
    assert goal["target"]["target_time_sec"] is None
    assert goal["target"]["target_event_date"] is None


def test_api_generation_rejects_unlinked_5k_purpose(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])

    response = client.post(
        "/api/plan/outdoor-5k/readiness",
        json=_api_request(
            purpose={
                "capability_id": "outdoor_road_5k_v1",
                "source": "unlinked",
            },
        ),
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "PLAN_PURPOSE_UNSUPPORTED"


def test_independent_5k_purpose_can_confirm_its_own_baseline(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={
            "goal_kind": "race",
            "distance": "marathon",
            "race_date": "2027-04-18",
        },
    )
    from db.models import GoalBaselineConfirmation, GoalBaselineSnapshot

    db = db_session.SessionLocal()
    try:
        db.query(GoalBaselineSnapshot).filter(
            GoalBaselineSnapshot.user_id == user_id
        ).delete()
        db.query(GoalBaselineConfirmation).filter(
            GoalBaselineConfirmation.user_id == user_id
        ).delete()
        db.commit()
    finally:
        db.close()

    purpose = {
        "capability_id": "outdoor_road_5k_v1",
        "source": "capability",
    }
    before = client.post(
        "/api/plan/outdoor-5k/readiness",
        json=_api_request(purpose=purpose),
    )
    assert before.status_code == 200, before.text
    assert before.json()["result"]["code"] == (
        "insufficient_or_stale_baseline"
    )
    assert before.json()["baseline"]["candidates"]

    confirmed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={"Idempotency-Key": "independent-purpose-baseline"},
        json={
            "activity_id": "current-baseline",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
            "purpose": purpose,
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    after = client.post(
        "/api/plan/outdoor-5k/readiness",
        json=_api_request(purpose=purpose),
    )
    assert after.status_code == 200, after.text
    assert after.json()["result"]["code"] == "ready"


def test_current_goal_change_requires_draft_reassessment_before_adoption(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    purpose = _current_goal_purpose(client)
    request = _api_request(purpose=purpose)
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=request)
    assert readiness.status_code == 200, readiness.text
    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **request,
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "linked-goal-reassessment",
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1490,
        },
    )

    discovery = client.get("/api/plan/generation/capabilities")
    assert discovery.status_code == 200, discovery.text
    assert discovery.json()["active_plan_goal"]["link_status"] == (
        "reassessment_required"
    )

    adopted = client.post(
        f"/api/plan/proposals/{proposal['id']}/adopt",
        json={
            "expected_proposal_version": proposal["version"],
            "expected_plan_version": proposal["adaptive_plan"]["version"],
            "idempotency_key": "linked-goal-reassessment",
        },
    )
    assert adopted.status_code == 409, adopted.text
    assert adopted.json()["detail"]["code"] == (
        "PLAN_PURPOSE_REASSESSMENT_REQUIRED"
    )


def test_independent_5k_plan_stays_valid_when_current_goal_changes(
    proposal_client,
) -> None:
    client, db_session, current_user = proposal_client
    user_id = current_user["value"]
    _seed_api_context(db_session, user_id)
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={"goal_kind": "race", "distance": "marathon"},
    )
    purpose = {
        "capability_id": "outdoor_road_5k_v1",
        "source": "capability",
    }
    request = _api_request(purpose=purpose)
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=request)
    assert readiness.status_code == 200, readiness.text
    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **request,
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "independent-goal-adoption",
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]
    _replace_goal(
        db_session,
        user_id=user_id,
        goal={"goal_kind": "race", "distance": "half_marathon"},
    )

    adopted = client.post(
        f"/api/plan/proposals/{proposal['id']}/adopt",
        json={
            "expected_proposal_version": proposal["version"],
            "expected_plan_version": proposal["adaptive_plan"]["version"],
            "idempotency_key": "independent-goal-adoption",
        },
    )
    assert adopted.status_code == 200, adopted.text
    discovery = client.get("/api/plan/generation/capabilities")
    assert discovery.status_code == 200, discovery.text
    assert discovery.json()["active_plan_goal"]["link_status"] == (
        "independent"
    )


def test_api_accepts_policy_valid_duration_above_former_240_minute_cap(
    proposal_client,
) -> None:
    """The API leaves the duration limit to the history-backed policy."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])

    readiness = client.post(
        "/api/plan/outdoor-5k/readiness",
        json={**_api_request(), "maximum_session_duration_min": 300},
    )

    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["result"]["code"] == "ready"


def test_api_idempotency_replays_before_source_fence_after_source_changes(
    proposal_client,
) -> None:
    """An exact retry returns its immutable response despite source mutations."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    request = {
        **_api_request(),
        "expected_source_revision": readiness.json()["source_revision"],
        "idempotency_key": "outdoor-5k-replay-before-source-fence",
    }
    created = client.post("/api/plan/outdoor-5k/generate", json=request)
    assert created.status_code == 201, created.text
    created_body = created.json()

    from db.models import (
        Activity,
        GoalBaselineSnapshot,
        TrainingPlan,
        UserConfig,
    )

    db = db_session.SessionLocal()
    try:
        config = db.query(UserConfig).filter(
            UserConfig.user_id == current_user["value"]
        ).one()
        config.goal = {**config.goal, "target_time_sec": 1499}
        baseline = db.query(GoalBaselineSnapshot).filter(
            GoalBaselineSnapshot.user_id == current_user["value"]
        ).one()
        today = _api_today()
        baseline.observed_date = today - timedelta(days=2)
        current_week = today - timedelta(days=today.weekday())
        db.add_all([
            Activity(
                user_id=current_user["value"],
                activity_id="replay-source-change-activity",
                date=current_week - timedelta(days=6),
                activity_type="running",
                duration_sec=45 * 60,
                source="garmin",
            ),
            TrainingPlan(
                user_id=current_user["value"],
                canonical_id="replay-source-change-reservation",
                date=today + timedelta(days=1),
                source="manual",
            ),
        ])
        db.commit()
    finally:
        db.close()

    changed_readiness = client.post(
        "/api/plan/outdoor-5k/readiness",
        json=_api_request(),
    )
    assert changed_readiness.status_code == 200, changed_readiness.text
    assert changed_readiness.json()["source_revision"] != request[
        "expected_source_revision"
    ]

    replay = client.post("/api/plan/outdoor-5k/generate", json=request)

    assert replay.status_code == 200, replay.text
    assert replay.json() == {**created_body, "replayed": True}

    changed_payload = client.post(
        "/api/plan/outdoor-5k/generate",
        json={**request, "maximum_session_duration_min": 59},
    )
    assert changed_payload.status_code == 409, changed_payload.text
    assert changed_payload.json()["detail"]["code"] == (
        "OUTDOOR_5K_IDEMPOTENCY_CONFLICT"
    )


def test_api_replays_pre_purpose_idempotency_audit(
    proposal_client,
) -> None:
    """An exact pre-feature retry reconstructs its immutable current Goal."""
    import api.outdoor_5k_plan_generation as generation_service
    from db.models import (
        AdaptivePlanGoalSnapshot,
        Outdoor5KPlanGeneration,
    )

    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    request = {
        **_api_request(),
        "expected_source_revision": readiness.json()["source_revision"],
        "idempotency_key": "outdoor-5k-pre-purpose-replay",
    }
    created = client.post("/api/plan/outdoor-5k/generate", json=request)
    assert created.status_code == 201, created.text
    created_body = created.json()

    db = db_session.SessionLocal()
    try:
        audit = db.query(Outdoor5KPlanGeneration).one()
        constraints = generation_service._constraints_from_snapshot(
            audit.constraint_snapshot
        )
        audit.request_fingerprint = (
            generation_service._legacy_request_fingerprint(
                request_kind="generate",
                expected_source_revision=request["expected_source_revision"],
                constraints=constraints,
                outdoor_road_goal_confirmed=True,
            )
        )
        observed_snapshot = dict(audit.observed_input_snapshot)
        observed_snapshot.pop("purpose")
        audit.observed_input_snapshot = observed_snapshot
        constraint_snapshot = dict(audit.constraint_snapshot)
        constraint_snapshot.pop("purpose")
        audit.constraint_snapshot = constraint_snapshot
        goal = db.get(
            AdaptivePlanGoalSnapshot,
            created_body["proposal"]["goal_snapshot_id"],
        )
        assert goal is not None
        goal.purpose_source = None
        goal.source_goal_id = None
        goal.source_goal_revision = None
        db.commit()
    finally:
        db.close()

    replay = client.post("/api/plan/outdoor-5k/generate", json=request)

    assert replay.status_code == 200, replay.text
    replay_body = replay.json()
    assert replay_body["replayed"] is True
    assert replay_body["proposal"]["id"] == created_body["proposal"]["id"]
    assert replay_body["purpose"] == {
        "capability_id": "outdoor_road_5k_v1",
        "source": "current_goal",
        "expected_goal_id": None,
        "expected_goal_revision": None,
        "goal": created_body["purpose"]["goal"],
    }


def test_adoption_revalidates_pre_purpose_source_hash(
    proposal_client,
) -> None:
    """A faithful pre-purpose draft remains adoptable when inputs are unchanged."""
    import api.outdoor_5k_plan_generation as generation_service
    from db.models import (
        AdaptivePlanGoalSnapshot,
        Outdoor5KPlanGeneration,
        PlanProposal,
    )

    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    request = {
        **_api_request(),
        "expected_source_revision": readiness.json()["source_revision"],
        "idempotency_key": "outdoor-5k-pre-purpose-adopt",
    }
    created = client.post("/api/plan/outdoor-5k/generate", json=request)
    assert created.status_code == 201, created.text
    created_body = created.json()

    db = db_session.SessionLocal()
    try:
        audit = db.query(Outdoor5KPlanGeneration).one()
        constraints = generation_service._constraints_from_snapshot(
            audit.constraint_snapshot
        )
        _, legacy_result, _, _ = generation_service._evaluate(
            db,
            user_id=current_user["value"],
            constraints=constraints,
            outdoor_road_goal_confirmed=True,
            purpose_selection=None,
            bind_purpose_revision=False,
        )
        assert legacy_result.plan is not None
        audit.source_revision = legacy_result.deterministic_input_hash
        audit.deterministic_input_hash = (
            legacy_result.deterministic_input_hash
        )
        observed_snapshot = dict(audit.observed_input_snapshot)
        observed_snapshot.pop("purpose")
        audit.observed_input_snapshot = observed_snapshot
        constraint_snapshot = dict(audit.constraint_snapshot)
        constraint_snapshot.pop("purpose")
        audit.constraint_snapshot = constraint_snapshot
        goal = db.get(
            AdaptivePlanGoalSnapshot,
            created_body["proposal"]["goal_snapshot_id"],
        )
        assert goal is not None
        goal.purpose_source = None
        goal.source_goal_id = None
        goal.source_goal_revision = None
        proposal = db.get(PlanProposal, created_body["proposal"]["id"])
        assert proposal is not None
        proposal.workout_snapshot = generation_service._proposal_workouts(
            legacy_result.plan,
            legacy_result.deterministic_input_hash,
        )
        db.commit()
    finally:
        db.close()

    adoption = client.post(
        f"/api/plan/proposals/{created_body['proposal']['id']}/adopt",
        json={
            "expected_proposal_version": (
                created_body["proposal"]["version"]
            ),
            "expected_plan_version": (
                created_body["proposal"]["adaptive_plan"]["version"]
            ),
            "idempotency_key": "outdoor-5k-pre-purpose-adoption",
        },
    )
    assert adoption.status_code == 200, adoption.text
    assert adoption.json()["status"] == "adopted"


def test_inflight_exact_retry_replays_the_first_persisted_proposal(
    proposal_client,
    monkeypatch,
) -> None:
    """A peer that commits in the idempotency gap is returned as a replay."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    request = {
        **_api_request(),
        "expected_source_revision": readiness.json()["source_revision"],
        "idempotency_key": "outdoor-5k-inflight-retry",
    }

    import api.outdoor_5k_plan_generation as generation_service

    real_create = generation_service.create_draft_proposal
    peer_result: dict[str, object] = {}
    create_peer_first = {"value": True}
    constraints = PlanGenerationConstraints(
        age_18_or_older=True,
        self_coached_recreational_road_runner=True,
        can_complete_5k=True,
        safety_stop=False,
        available_weekdays=(0, 2, 5),
        maximum_session_duration_min=60,
        unavailable_dates=(),
        preferred_longest_run_weekday=5,
    )

    def create_after_inflight_peer(*args, **kwargs):
        if create_peer_first["value"]:
            create_peer_first["value"] = False
            peer = db_session.SessionLocal()
            try:
                result, replayed = generation_service.generate_outdoor_5k_proposal(
                    peer,
                    user_id=current_user["value"],
                    constraints=constraints,
                    outdoor_road_goal_confirmed=True,
                    expected_source_revision=request["expected_source_revision"],
                    idempotency_key=request["idempotency_key"],
                )
                peer_result["result"] = result
                peer_result["replayed"] = replayed
            finally:
                peer.close()
        return real_create(*args, **kwargs)

    monkeypatch.setattr(
        generation_service,
        "create_draft_proposal",
        create_after_inflight_peer,
    )
    retry = client.post("/api/plan/outdoor-5k/generate", json=request)

    assert peer_result["replayed"] is False
    assert retry.status_code == 200, retry.text
    assert retry.json()["replayed"] is True
    assert retry.json()["proposal"]["id"] == peer_result["result"]["proposal"]["id"]


def test_source_change_between_evaluation_and_persistence_cannot_create_proposal(
    proposal_client,
    monkeypatch,
) -> None:
    """The locked write fence rejects a source mutation in the evaluation gap."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text

    import api.outdoor_5k_plan_generation as generation_service
    from db.models import Activity, Outdoor5KPlanGeneration, PlanProposal

    real_create = generation_service.create_draft_proposal

    def mutate_source_before_locked_persistence(*args, **kwargs):
        writer = db_session.SessionLocal()
        try:
            today = _api_today()
            current_week = today - timedelta(days=today.weekday())
            writer.add(
                Activity(
                    user_id=current_user["value"],
                    activity_id="concurrent-source-change",
                    date=current_week - timedelta(days=6),
                    activity_type="running",
                    duration_sec=45 * 60,
                    source="garmin",
                )
            )
            writer.commit()
        finally:
            writer.close()
        return real_create(*args, **kwargs)

    monkeypatch.setattr(
        generation_service,
        "create_draft_proposal",
        mutate_source_before_locked_persistence,
    )
    generated = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "outdoor-5k-locked-source-race",
        },
    )

    assert generated.status_code == 409, generated.text
    assert generated.json()["detail"]["code"] == "OUTDOOR_5K_SOURCE_REVISION_STALE"
    db = db_session.SessionLocal()
    try:
        assert db.query(PlanProposal).count() == 0
        assert db.query(Outdoor5KPlanGeneration).count() == 0
    finally:
        db.close()


def test_adoption_revalidates_baseline_and_never_triggers_delivery(
    proposal_client,
) -> None:
    """A stale #665 baseline blocks canonical adoption before any delivery call."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "outdoor-5k-adopt-fence",
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]

    from db.models import GoalBaselineConfirmation, TrainingPlan

    db = db_session.SessionLocal()
    try:
        db.query(GoalBaselineConfirmation).filter(
            GoalBaselineConfirmation.user_id == current_user["value"]
        ).delete()
        db.commit()
    finally:
        db.close()

    adopted = client.post(
        f"/api/plan/proposals/{proposal['id']}/adopt",
        json={
            "expected_proposal_version": proposal["version"],
            "expected_plan_version": proposal["adaptive_plan"]["version"],
            "idempotency_key": "outdoor-5k-adopt-fence",
        },
    )
    assert adopted.status_code == 409, adopted.text
    assert adopted.json()["detail"]["code"] == (
        "OUTDOOR_5K_PROPOSAL_REVALIDATION_FAILED"
    )
    assert client.delivery_calls == []

    db = db_session.SessionLocal()
    try:
        assert db.query(TrainingPlan).count() == 0
    finally:
        db.close()


def test_outdoor_5k_proposals_require_the_bounded_regenerate_route(
    proposal_client,
) -> None:
    """Generic proposal editing cannot replace an audited deterministic draft."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "outdoor-5k-edit-fence",
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]
    goal = proposal["goal"]

    generic_edit = client.post(
        f"/api/plan/proposals/{proposal['id']}/edits",
        json={
            "goal": {
                "goal_kind": goal["goal_kind"],
                "target": goal["target"],
                "horizon_start": goal["horizon_start"],
                "horizon_end": goal["horizon_end"],
            },
            "discipline": proposal["discipline"],
            "workouts": proposal["workouts"],
            "expected_version": proposal["version"],
            "idempotency_key": "outdoor-5k-generic-edit",
        },
    )
    assert generic_edit.status_code == 409, generic_edit.text
    assert generic_edit.json()["detail"]["code"] == (
        "OUTDOOR_5K_PROPOSAL_REGENERATE_REQUIRED"
    )


def test_successful_adoption_keeps_outdoor_5k_delivery_separate(
    proposal_client,
) -> None:
    """Canonical adoption is explicit, but does not call a provider-delivery path."""
    client, db_session, current_user = proposal_client
    _seed_api_context(db_session, current_user["value"])
    readiness = client.post("/api/plan/outdoor-5k/readiness", json=_api_request())
    assert readiness.status_code == 200, readiness.text
    created = client.post(
        "/api/plan/outdoor-5k/generate",
        json={
            **_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "outdoor-5k-adopt-success",
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]

    adopted = client.post(
        f"/api/plan/proposals/{proposal['id']}/adopt",
        json={
            "expected_proposal_version": proposal["version"],
            "expected_plan_version": proposal["adaptive_plan"]["version"],
            "idempotency_key": "outdoor-5k-adopt-success",
        },
    )
    assert adopted.status_code == 200, adopted.text
    assert adopted.json()["status"] == "adopted"
    assert client.delivery_calls == []

    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        assert db.query(TrainingPlan).count() > 0
    finally:
        db.close()
