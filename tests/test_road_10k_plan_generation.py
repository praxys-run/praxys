"""Tests for the deterministic road 10K policy service."""
from __future__ import annotations

import importlib
import os
import tempfile
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest


def _history(today: date):
    from analysis.road_10k_plan_generation import RunningHistoryObservation

    current_week = today - timedelta(days=today.weekday())
    activities: list[RunningHistoryObservation] = []
    for week in range(1, 9):
        week_start = current_week - timedelta(days=7 * week)
        for offset, duration, distance in (
            (0, 55.0, 9.0),
            (2, 60.0, 10.0),
            (5, 65.0, 12.0),
        ):
            activities.append(
                RunningHistoryObservation(
                    activity_id=f"road-10k-{week}-{offset}",
                    observed_date=week_start + timedelta(days=offset),
                    duration_min=duration,
                    distance_km=distance,
                    source="garmin",
                )
            )
    return tuple(activities)


def _intensity_sources(history) -> tuple[tuple[str, str], ...]:
    return tuple((item.activity_id, "activity_splits") for item in history)


def _input(
    *,
    baseline_current: bool = True,
    target_event_date: date | None = None,
    benchmark_date: date | None = None,
    history=None,
    intensity_sources: tuple[tuple[str, str], ...] | None = None,
):
    from analysis.road_10k_plan_generation import (
        ROAD_10K_CONTRACT_DIGEST,
        ROAD_10K_POLICY_VERSION,
        ROAD_10K_SCIENCE_DECISION_ID,
        ROAD_10K_SOURCE_DECISION_DIGEST,
        ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION,
        Road10KGenerationInput,
        Road10KGoal,
        Road10KPlanGenerationConstraints,
    )

    today = date(2026, 8, 18)
    history_items = tuple(history or _history(today))
    return Road10KGenerationInput(
        policy_version=ROAD_10K_POLICY_VERSION,
        science_decision_id=ROAD_10K_SCIENCE_DECISION_ID,
        contract_digest=ROAD_10K_CONTRACT_DIGEST,
        source_decision_digest=ROAD_10K_SOURCE_DECISION_DIGEST,
        athlete_today=today,
        block_start=today + timedelta(days=1),
        goal=Road10KGoal(
            goal_kind="performance_10k",
            distance="10k",
            target_time_sec=2_520,
            target_event_date=target_event_date,
        ),
        baseline_current=baseline_current,
        baseline_snapshot_id=(
            "road-10k-baseline-snapshot-1" if baseline_current else None
        ),
        baseline_source="race" if baseline_current else None,
        baseline_evidence_date=(
            today - timedelta(days=6) if baseline_current else None
        ),
        history=history_items,
        intensity_sources=(
            intensity_sources
            if intensity_sources is not None
            else _intensity_sources(history_items)
        ),
        reserved_dates=(),
        training_pattern_snapshot_version=(
            ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION
        ),
        constraints=Road10KPlanGenerationConstraints(
            adult_confirmed=True,
            current_symptom_stop=False,
            available_weekdays=(0, 2, 5),
            weekly_time_limit_min=180,
            maximum_session_duration_min=70,
            unavailable_dates=(),
            preferred_longest_easy_weekday=5,
            benchmark_date=benchmark_date,
        ),
    )


def test_generation_is_deterministic_and_uses_the_reviewed_templates() -> None:
    """A replay of the same versioned input returns the same 14-day schedule."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    first = generate_road_10k_plan(_input())
    replay = generate_road_10k_plan(_input())

    assert replay == first
    assert first.code == "eligible_rolling_proposal"
    assert first.plan is not None
    assert first.plan.horizon_end - first.plan.horizon_start == timedelta(days=13)
    assert list(first.plan.reassessment_dates) == [
        first.plan.horizon_start + timedelta(days=7),
    ]
    assert [week.is_taper for week in first.plan.weeks] == [False, False]
    assert [
        workout.template_id
        for week in first.plan.weeks
        for workout in week.workouts
        if workout.intensity_bucket == "quality"
    ] == [
        "road-10k-controlled-threshold-quality-v1",
        "road-10k-specific-interval-quality-v1",
    ]

    for week in first.plan.weeks:
        workouts = week.workouts
        total_minutes = sum(item.planned_duration_min for item in workouts)
        low_minutes = sum(
            item.planned_duration_min
            for item in workouts
            if item.intensity_bucket == "low"
        )
        assert 3 <= len(workouts) <= 6
        assert sum(
            item.intensity_bucket == "quality" for item in workouts
        ) == 1
        assert total_minutes <= 180
        assert low_minutes / total_minutes >= 0.75


def test_missing_baseline_and_target_conflicts_are_typed_fail_closed_results() -> None:
    """Road 10K readiness keeps missing baseline and event conflicts distinct."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    missing = generate_road_10k_plan(_input(baseline_current=False))
    near_term = generate_road_10k_plan(
        _input(target_event_date=date(2026, 8, 24))
    )
    dense = generate_road_10k_plan(
        _input(
            target_event_date=date(2026, 9, 2),
            benchmark_date=date(2026, 8, 29),
        )
    )

    assert missing.code == "missing_or_stale_direct_baseline"
    assert missing.plan is None
    assert near_term.code == "limited_near_term_guidance"
    assert near_term.plan is None
    assert dense.code == "limited_guidance_event_conflict"
    assert dense.plan is None


def test_eight_to_fourteen_day_targets_produce_a_truncated_taper() -> None:
    """A single confirmed target inside the accepted taper window ends on event eve."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    target_date = date(2026, 8, 29)
    result = generate_road_10k_plan(
        _input(target_event_date=target_date)
    )

    assert result.code == "eligible_taper_proposal"
    assert result.plan is not None
    assert result.plan.horizon_end == target_date - timedelta(days=1)
    assert any(week.is_taper for week in result.plan.weeks)
    assert all(
        workout.scheduled_date < target_date
        for week in result.plan.weeks
        for workout in week.workouts
    )


@pytest.mark.parametrize(
    ("days_after_start", "expected_code", "expect_taper"),
    [
        (7, "limited_near_term_guidance", None),
        (8, "eligible_taper_proposal", True),
        (14, "eligible_taper_proposal", True),
        (15, "eligible_rolling_proposal", False),
        (21, "eligible_rolling_proposal", False),
    ],
)
def test_taper_boundaries_anchor_only_to_block_start(
    days_after_start: int,
    expected_code: str,
    expect_taper: bool | None,
) -> None:
    """Only targets 8-14 days after block start may enter the taper path."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    block_start = _input().block_start
    target_date = block_start + timedelta(days=days_after_start)

    result = generate_road_10k_plan(
        _input(target_event_date=target_date)
    )

    assert result.code == expected_code
    if expect_taper is None:
        assert result.plan is None
        return
    assert result.plan is not None
    assert any(week.is_taper for week in result.plan.weeks) is expect_taper
    if expect_taper:
        assert all(week.is_taper for week in result.plan.weeks)
        assert result.plan.horizon_end == target_date - timedelta(days=1)
    else:
        assert not any(week.is_taper for week in result.plan.weeks)
        assert result.plan.horizon_end == block_start + timedelta(days=13)


def test_distance_cap_is_required_and_preserved_per_workout() -> None:
    """Every generated workout carries the recent session-distance ceiling."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base_input = _input()
    missing_distance_cap = generate_road_10k_plan(
        _input(
            history=tuple(
                replace(observation, distance_km=None)
                for observation in base_input.history
            )
        )
    )

    assert missing_distance_cap.code == "insufficient_recent_history"
    assert "distance" in (
        missing_distance_cap.observed_or_stated_reason or ""
    ).casefold()

    result = generate_road_10k_plan(base_input)

    assert result.plan is not None
    recent_cap = result.history_statistics.recent_maximum_session_distance_km
    assert recent_cap == pytest.approx(12.0)
    for week in result.plan.weeks:
        for workout in week.workouts:
            assert workout.maximum_distance_ceiling_km == pytest.approx(
                recent_cap
            )
            assert workout.maximum_distance_ceiling_km <= recent_cap


def test_input_hash_tracks_intensity_source_provenance() -> None:
    """Changing split/sample provenance must change the replay hash."""
    from analysis.road_10k_plan_generation import deterministic_input_hash

    base_input = _input()
    changed_input = replace(
        base_input,
        intensity_sources=tuple(
            (activity_id, "activity_samples")
            for activity_id, _source in base_input.intensity_sources
        ),
    )

    assert deterministic_input_hash(base_input) != deterministic_input_hash(
        changed_input
    )


def test_typed_outcomes_match_the_accepted_contract_and_fail_closed() -> None:
    """Each accepted road 10K code maps one-to-one to typed runtime fields."""
    from analysis.road_10k_contract import road_10k_typed_outcome

    expected = {
        "adult_scope_or_constraints_unconfirmed": {
            "route_state": "clarification_required",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "contradictory_input": {
            "route_state": "clarification_required",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "eligible_rolling_proposal": {
            "route_state": "plan_candidate",
            "plan_returned": True,
            "adoption_required": True,
        },
        "eligible_taper_proposal": {
            "route_state": "plan_candidate",
            "plan_returned": True,
            "adoption_required": True,
        },
        "insufficient_recent_history": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "limited_guidance_event_conflict": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
            "limited_guidance_returned": True,
        },
        "limited_near_term_guidance": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
            "limited_guidance_returned": True,
        },
        "missing_or_stale_direct_baseline": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "no_schedule_within_envelope": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "safety_stop": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "unsupported_intent_distance_surface_or_population": {
            "route_state": "policy_unavailable",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "validation_failed": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
    }

    assert {
        code: road_10k_typed_outcome(code)
        for code in expected
    } == expected

    with pytest.raises(ValueError):
        road_10k_typed_outcome("unknown_result_code")


@pytest.fixture
def road_10k_client(monkeypatch):
    """Authenticated TestClient with the reviewed 10K route activated for tests."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", os.path.join(tmpdir.name, "data"))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    import api.plan_generation_capabilities as capabilities

    monkeypatch.setattr(
        capabilities,
        "PLAN_GENERATION_CAPABILITIES",
        (
            capabilities.OUTDOOR_ROAD_5K_CAPABILITY,
            replace(
                capabilities.OUTDOOR_ROAD_10K_CAPABILITY,
                status="available",
            ),
        ),
    )

    import api.main

    importlib.reload(api.main)
    app = api.main.app
    current_user_id = {"value": "road-10k-owner"}

    def _override_user() -> str:
        return current_user_id["value"]

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    from api.auth import get_current_user_id, get_data_user_id, require_write_access
    from api.routes import adaptive_plan as adaptive_plan_route
    from db.models import User
    from db.session import get_db

    with db_session.SessionLocal() as db:
        db.add(User(id="road-10k-owner", email="road-10k@test.local", hashed_password="x"))
        db.commit()

    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[get_data_user_id] = _override_user
    app.dependency_overrides[require_write_access] = _override_user
    app.dependency_overrides[get_db] = _override_db
    delivery_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        adaptive_plan_route,
        "_trigger_managed_delivery",
        lambda user_id, *, trigger: delivery_calls.append((user_id, trigger)) or {
            "status": "skipped",
            "target": None,
            "reason": trigger,
            "items": [],
        },
    )
    client = TestClient(app)
    client.delivery_calls = delivery_calls  # type: ignore[attr-defined]
    try:
        yield client, db_session
    finally:
        app.dependency_overrides.clear()
        if db_session.engine is not None:
            db_session.engine.dispose()
        if db_session.async_engine is not None:
            import asyncio

            try:
                asyncio.run(db_session.async_engine.dispose())
            except RuntimeError:
                pass
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _seed_road_10k_api_context(db_session, user_id: str) -> None:
    from analysis.road_10k_baseline import build_road_10k_goal
    from db.models import (
        Activity,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
        UserConfig,
    )

    today = date.today()
    goal = {
        "goal_kind": "performance_10k",
        "distance": "10k",
        "target_time_sec": 2_520,
    }
    signature = build_road_10k_goal(goal).goal_signature
    current_week = today - timedelta(days=today.weekday())
    with db_session.SessionLocal() as db:
        db.add(UserConfig(user_id=user_id, goal=goal))
        db.add(Activity(
            user_id=user_id,
            activity_id="road-10k-current-baseline",
            date=today - timedelta(days=6),
            activity_type="running",
            distance_km=10.0,
            duration_sec=2_520,
            start_time=f"{(today - timedelta(days=6)).isoformat()}T07:00:00Z",
            source="garmin",
        ))
        for split_num in range(1, 11):
            from db.models import ActivitySplit

            db.add(ActivitySplit(
                user_id=user_id,
                activity_id="road-10k-current-baseline",
                split_num=split_num,
                duration_sec=252,
                distance_km=1.0,
                avg_power=270,
            ))
        for week in range(1, 9):
            week_start = current_week - timedelta(days=week * 7)
            for offset, duration, distance in (
                (0, 55, 9.0),
                (2, 60, 10.0),
                (5, 65, 12.0),
            ):
                activity_id = f"road-10k-history-{week}-{offset}"
                db.add(Activity(
                    user_id=user_id,
                    activity_id=activity_id,
                    date=week_start + timedelta(days=offset),
                    activity_type="running",
                    distance_km=distance,
                    duration_sec=duration * 60,
                    start_time=f"{(week_start + timedelta(days=offset)).isoformat()}T06:30:00Z",
                    source="garmin",
                ))
                for split_num in range(1, 4):
                    from db.models import ActivitySplit

                    db.add(ActivitySplit(
                        user_id=user_id,
                        activity_id=activity_id,
                        split_num=split_num,
                        duration_sec=(duration * 60) / 3,
                        distance_km=distance / 3,
                        avg_power=250 + 5 * split_num,
                    ))
        db.add(Road10KBaselineConfirmation(
            id="road-10k-current-confirmation",
            lineage_id="road-10k-current-confirmation-lineage",
            user_id=user_id,
            goal_signature=signature,
            goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
            version=1,
            activity_id="road-10k-current-baseline",
            response="race",
            measured_10k=True,
            elapsed_timing_confirmed=True,
            completed_at=datetime.fromisoformat(
                f"{(today - timedelta(days=6)).isoformat()}T07:42:00"
            ),
            elapsed_time_sec=2_520,
            surface_or_protocol="organized_outdoor_road_10k_race",
            route_or_venue_identifier="sample-road-10k-race",
            assistance_status="unassisted",
            source_provider="garmin",
            request_fingerprint="a" * 64,
        ))
        db.add(Road10KBaselineSnapshot(
            id="road-10k-current-baseline-snapshot",
            lineage_id="road-10k-current-baseline-snapshot-lineage",
            user_id=user_id,
            goal_signature=signature,
            goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
            version=1,
            source_kind="history_confirmation",
            source_id="road-10k-current-baseline",
            provenance="race",
            observed_date=today - timedelta(days=6),
            completed_at=datetime.fromisoformat(
                f"{(today - timedelta(days=6)).isoformat()}T07:42:00"
            ),
            distance_km=10.0,
            elapsed_time_sec=2_520,
            measured_10k=True,
            elapsed_timing_confirmed=True,
            surface_or_protocol="organized_outdoor_road_10k_race",
            route_or_venue_identifier="sample-road-10k-race",
            assistance_status="unassisted",
            source_provider="garmin",
            qualification_status="direct_current",
            change_comparability="not_assessed",
            invalidators=[],
        ))
        db.commit()


def _road_10k_api_request(*, purpose: dict | None = None) -> dict:
    payload = {
        "adult_confirmed": True,
        "current_symptom_stop": False,
        "available_weekdays": [0, 2, 5],
        "weekly_time_limit_min": 180,
        "maximum_session_duration_min": 70,
        "unavailable_dates": [],
        "preferred_longest_easy_weekday": 5,
        "benchmark_date": None,
    }
    if purpose is not None:
        payload["purpose"] = purpose
    return payload


def test_api_generation_replays_idempotently_and_stays_noncanonical(
    road_10k_client,
) -> None:
    client, db_session = road_10k_client
    _seed_road_10k_api_context(db_session, "road-10k-owner")

    readiness = client.post("/api/plan/road-10k/readiness", json=_road_10k_api_request())
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["result"]["code"] == "eligible_rolling_proposal"

    created = client.post(
        "/api/plan/road-10k/generate",
        json={
            **_road_10k_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "road-10k-generate-1",
        },
    )
    assert created.status_code == 201, created.text
    proposal = created.json()["proposal"]
    assert proposal["state"] == "draft"
    assert client.delivery_calls == []  # type: ignore[attr-defined]

    replay = client.post(
        "/api/plan/road-10k/generate",
        json={
            **_road_10k_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "road-10k-generate-1",
        },
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["proposal"]["id"] == proposal["id"]


def test_history_confirmation_upgrades_missing_10k_readiness(
    road_10k_client,
) -> None:
    client, db_session = road_10k_client
    _seed_road_10k_api_context(db_session, "road-10k-owner")

    from db.models import Road10KBaselineConfirmation, Road10KBaselineSnapshot

    with db_session.SessionLocal() as db:
        db.query(Road10KBaselineSnapshot).delete()
        db.query(Road10KBaselineConfirmation).delete()
        db.commit()

    readiness = client.post("/api/plan/road-10k/readiness", json=_road_10k_api_request())
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["result"]["code"] == "missing_or_stale_direct_baseline"
    assert readiness.json()["baseline"]["candidates"]

    confirmed = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-confirm"},
        json={
            "activity_id": "road-10k-current-baseline",
            "response": "race",
            "measured_10k": True,
            "elapsed_timing_confirmed": True,
            "surface_or_protocol": "organized_outdoor_road_10k_race",
            "route_or_venue_identifier": "sample-road-10k-race",
            "assistance_status": "unassisted",
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    refreshed = client.post("/api/plan/road-10k/readiness", json=_road_10k_api_request())
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["result"]["code"] == "eligible_rolling_proposal"


def test_protocol_qualified_off_device_distance_can_still_be_confirmed(
    road_10k_client,
) -> None:
    client, db_session = road_10k_client
    _seed_road_10k_api_context(db_session, "road-10k-owner")

    from db.models import Activity, Road10KBaselineConfirmation, Road10KBaselineSnapshot

    today = date.today()
    with db_session.SessionLocal() as db:
        db.query(Road10KBaselineSnapshot).delete()
        db.query(Road10KBaselineConfirmation).delete()
        db.add(Activity(
            user_id="road-10k-owner",
            activity_id="road-10k-off-device-distance",
            date=today - timedelta(days=2),
            activity_type="running",
            distance_km=10.8,
            duration_sec=2_545,
            start_time=f"{(today - timedelta(days=2)).isoformat()}T07:10:00Z",
            source="garmin",
        ))
        db.commit()

    readiness = client.post("/api/plan/road-10k/readiness", json=_road_10k_api_request())
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["result"]["code"] == "missing_or_stale_direct_baseline"
    assert {
        candidate["activity_id"]
        for candidate in readiness.json()["baseline"]["candidates"]
    } >= {"road-10k-off-device-distance"}

    confirmed = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-off-device-confirm"},
        json={
            "activity_id": "road-10k-off-device-distance",
            "response": "race",
            "measured_10k": True,
            "elapsed_timing_confirmed": True,
            "surface_or_protocol": "organized_outdoor_road_10k_race",
            "route_or_venue_identifier": "off-device-road-10k-race",
            "assistance_status": "unassisted",
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    confirmed_body = confirmed.json()
    assert confirmed_body["baseline"]["status"] == "current"
    assert confirmed_body["baseline"]["evidence"]["activity_id"] == (
        "road-10k-off-device-distance"
    )
    assert confirmed_body["baseline"]["evidence"]["distance_km"] == pytest.approx(10.8)


def test_history_confirmation_requires_contract_metadata_and_replays_idempotently(
    road_10k_client,
) -> None:
    client, db_session = road_10k_client
    _seed_road_10k_api_context(db_session, "road-10k-owner")

    from db.models import (
        Activity,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
        UserConfig,
    )

    with db_session.SessionLocal() as db:
        db.query(Road10KBaselineSnapshot).delete()
        db.query(Road10KBaselineConfirmation).delete()
        db.commit()

    missing_metadata = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-missing-metadata"},
        json={
            "activity_id": "road-10k-current-baseline",
            "response": "race",
            "measured_10k": True,
            "elapsed_timing_confirmed": True,
            "assistance_status": "assisted",
        },
    )
    assert missing_metadata.status_code == 400, missing_metadata.text
    assert missing_metadata.json()["detail"]["code"] == (
        "ROAD_10K_BASELINE_INVALID_REQUEST"
    )

    mismatched_protocol = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-bad-protocol"},
        json={
            "activity_id": "road-10k-current-baseline",
            "response": "intentional_all_out",
            "measured_10k": True,
            "elapsed_timing_confirmed": True,
            "surface_or_protocol": "organized_outdoor_road_10k_race",
            "route_or_venue_identifier": "sample-track-10k",
            "assistance_status": "unknown_or_unreported",
        },
    )
    assert mismatched_protocol.status_code == 400, mismatched_protocol.text
    assert mismatched_protocol.json()["detail"]["code"] == (
        "ROAD_10K_BASELINE_INVALID_REQUEST"
    )

    request = {
        "activity_id": "road-10k-current-baseline",
        "response": "race",
        "measured_10k": True,
        "elapsed_timing_confirmed": True,
        "surface_or_protocol": "organized_outdoor_road_10k_race",
        "route_or_venue_identifier": "sample-road-10k-race",
        "assistance_status": "assisted",
    }
    created = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-create"},
        json=request,
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["confirmation"]["surface_or_protocol"] == (
        "organized_outdoor_road_10k_race"
    )
    assert created_body["confirmation"]["route_or_venue_identifier"] == (
        "sample-road-10k-race"
    )
    assert created_body["confirmation"]["assistance_status"] == "assisted"
    assert created_body["confirmation"]["source_provider"] == "garmin"
    assert created_body["confirmation"]["elapsed_time_sec"] == 2_520
    assert created_body["confirmation"]["completed_at"].startswith(
        str(date.today() - timedelta(days=6))
    )
    assert created_body["baseline"]["evidence"]["surface_or_protocol"] == (
        "organized_outdoor_road_10k_race"
    )
    assert created_body["baseline"]["evidence"]["route_or_venue_identifier"] == (
        "sample-road-10k-race"
    )
    assert created_body["baseline"]["evidence"]["assistance_status"] == (
        "assisted"
    )
    assert created_body["baseline"]["status"] == "current"

    with db_session.SessionLocal() as db:
        activity = db.query(Activity).filter(
            Activity.user_id == "road-10k-owner",
            Activity.activity_id == "road-10k-current-baseline",
        ).one()
        activity.start_time = f"{(date.today() - timedelta(days=5)).isoformat()}T09:15:00Z"
        activity.duration_sec = 2_700
        activity.source = "strava"
        db.commit()

    replay_after_correction = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-create"},
        json=request,
    )
    assert replay_after_correction.status_code == 200, replay_after_correction.text
    corrected_body = replay_after_correction.json()
    assert corrected_body["replayed"] is True
    assert corrected_body["confirmation"]["id"] == created_body["confirmation"]["id"]
    assert corrected_body["baseline"]["evidence"] == created_body["baseline"]["evidence"]

    with db_session.SessionLocal() as db:
        db.query(Activity).filter(
            Activity.user_id == "road-10k-owner",
            Activity.activity_id == "road-10k-current-baseline",
        ).delete()
        config = db.query(UserConfig).filter(
            UserConfig.user_id == "road-10k-owner",
        ).one()
        config.goal = {
            "goal_kind": "race",
            "distance": "10k",
            "race_date": "2026-09-20",
            "target_time_sec": 2_520,
        }
        db.commit()

    replay_after_deletion = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-create"},
        json=request,
    )
    assert replay_after_deletion.status_code == 200, replay_after_deletion.text
    deleted_body = replay_after_deletion.json()
    assert deleted_body["replayed"] is True
    assert deleted_body["confirmation"]["id"] == created_body["confirmation"]["id"]
    assert deleted_body["baseline"]["status"] == "current"
    assert deleted_body["baseline"]["evidence"] == created_body["baseline"]["evidence"]

    conflict = client.post(
        "/api/plan/road-10k/baseline/history/confirm",
        headers={"Idempotency-Key": "road-10k-baseline-create"},
        json={**request, "assistance_status": "unassisted"},
    )
    assert conflict.status_code == 409, conflict.text


def test_confirmed_snapshot_stays_stable_when_live_activity_metadata_drifts(
    road_10k_client,
) -> None:
    client, db_session = road_10k_client
    _seed_road_10k_api_context(db_session, "road-10k-owner")

    from analysis.road_10k_baseline import build_road_10k_goal
    from api.road_10k_baseline import (
        build_road_10k_baseline_view,
        resolve_road_10k_baseline_snapshot_id,
    )
    from db.models import (
        Activity,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
    )

    today = date.today()
    goal = {
        "goal_kind": "performance_10k",
        "distance": "10k",
        "target_time_sec": 2_520,
    }
    signature = build_road_10k_goal(goal).goal_signature
    with db_session.SessionLocal() as db:
        db.add(Activity(
            user_id="road-10k-owner",
            activity_id="road-10k-drift-baseline",
            date=today,
            activity_type="running",
            distance_km=10.1,
            duration_sec=2_460,
            start_time=f"{today.isoformat()}T06:45:00Z",
            source="garmin",
        ))
        db.add(Road10KBaselineConfirmation(
            id="road-10k-drift-confirmation",
            lineage_id="road-10k-drift-confirmation-lineage",
            user_id="road-10k-owner",
            goal_signature=signature,
            goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
            version=1,
            activity_id="road-10k-drift-baseline",
            response="race",
            measured_10k=True,
            elapsed_timing_confirmed=True,
            completed_at=datetime.fromisoformat(f"{today.isoformat()}T07:26:00"),
            elapsed_time_sec=2_460,
            surface_or_protocol="organized_outdoor_road_10k_race",
            route_or_venue_identifier="drift-road-10k-race",
            assistance_status="unassisted",
            source_provider="garmin",
            request_fingerprint="d" * 64,
        ))
        db.add(Road10KBaselineSnapshot(
            id="road-10k-drift-snapshot",
            lineage_id="road-10k-drift-snapshot-lineage",
            user_id="road-10k-owner",
            goal_signature=signature,
            goal_snapshot={"goal_kind": "performance_10k", "distance": "10k"},
            version=1,
            source_kind="history_confirmation",
            source_id="road-10k-drift-baseline",
            provenance="race",
            observed_date=today,
            completed_at=datetime.fromisoformat(f"{today.isoformat()}T07:26:00"),
            distance_km=10.1,
            elapsed_time_sec=2_460,
            measured_10k=True,
            elapsed_timing_confirmed=True,
            surface_or_protocol="organized_outdoor_road_10k_race",
            route_or_venue_identifier="drift-road-10k-race",
            assistance_status="unassisted",
            source_provider="garmin",
            qualification_status="direct_current",
            change_comparability="not_assessed",
            invalidators=[],
        ))
        db.commit()

    readiness = client.post("/api/plan/road-10k/readiness", json=_road_10k_api_request())
    assert readiness.status_code == 200, readiness.text
    readiness_body = readiness.json()
    assert readiness_body["result"]["code"] == "eligible_rolling_proposal"
    assert readiness_body["result"]["plan_returned"] is True

    with db_session.SessionLocal() as db:
        activity = db.query(Activity).filter(
            Activity.user_id == "road-10k-owner",
            Activity.activity_id == "road-10k-drift-baseline",
        ).one()
        activity.date = today + timedelta(days=1)
        activity.start_time = f"{(today + timedelta(days=1)).isoformat()}T12:00:00Z"
        activity.duration_sec = 3_000
        activity.source = "strava"
        db.commit()

    drifted = client.post("/api/plan/road-10k/readiness", json=_road_10k_api_request())
    assert drifted.status_code == 200, drifted.text
    drifted_body = drifted.json()
    assert drifted_body["source_revision"] == readiness_body["source_revision"]
    assert drifted_body["baseline"]["evidence"] == readiness_body["baseline"]["evidence"]

    with db_session.SessionLocal() as db:
        baseline_view = build_road_10k_baseline_view(
            db,
            user_id="road-10k-owner",
        )
        assert resolve_road_10k_baseline_snapshot_id(
            db,
            user_id="road-10k-owner",
            goal_signature=signature,
            evidence=baseline_view["baseline"]["evidence"],
        ) == "road-10k-drift-snapshot"


def test_generation_audit_keeps_only_contract_fields_and_replays_without_raw_storage(
    road_10k_client,
) -> None:
    from api.adaptive_plan_service import AdaptivePlanError
    from api.road_10k_plan_generation import validate_road_10k_proposal_adoption
    from db.models import ActivitySample, ActivitySplit, PlanProposal, Road10KPlanGeneration

    client, db_session = road_10k_client
    _seed_road_10k_api_context(db_session, "road-10k-owner")

    readiness = client.post(
        "/api/plan/road-10k/readiness",
        json=_road_10k_api_request(),
    )
    assert readiness.status_code == 200, readiness.text

    created = client.post(
        "/api/plan/road-10k/generate",
        json={
            **_road_10k_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "road-10k-audit-generate",
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["result"]["route_state"] == "plan_candidate"
    assert created_body["result"]["plan_returned"] is True
    assert created_body["result"]["adoption_required"] is True
    proposal_id = created.json()["proposal"]["id"]

    replay = client.post(
        "/api/plan/road-10k/generate",
        json={
            **_road_10k_api_request(),
            "expected_source_revision": readiness.json()["source_revision"],
            "idempotency_key": "road-10k-audit-generate",
        },
    )
    assert replay.status_code == 200, replay.text
    replay_body = replay.json()
    assert replay_body["replayed"] is True
    assert replay_body["proposal"]["id"] == proposal_id
    assert replay_body["result"]["code"] == "eligible_rolling_proposal"
    assert replay_body["result"]["route_state"] == "plan_candidate"
    assert replay_body["result"]["plan_returned"] is True
    assert replay_body["result"]["history_statistics"]["usable_completed_weeks"] == 8
    assert replay_body["event_context"]["snapshot_version"] == (
        "road-10k-event-context-v1"
    )

    with db_session.SessionLocal() as db:
        audit = (
            db.query(Road10KPlanGeneration)
            .filter(Road10KPlanGeneration.proposal_id == proposal_id)
            .one()
        )
        assert audit.history_cutoff_completed_days == 56
        assert audit.baseline_snapshot_id == "road-10k-current-baseline-snapshot"
        assert audit.baseline_source == "race"
        assert set(audit.history_observation_ids) == {
            "road-10k-current-baseline",
            "road-10k-history-1-0",
            "road-10k-history-1-2",
            "road-10k-history-1-5",
            "road-10k-history-2-0",
            "road-10k-history-2-2",
            "road-10k-history-2-5",
            "road-10k-history-3-0",
            "road-10k-history-3-2",
            "road-10k-history-3-5",
            "road-10k-history-4-0",
            "road-10k-history-4-2",
            "road-10k-history-4-5",
            "road-10k-history-5-0",
            "road-10k-history-5-2",
            "road-10k-history-5-5",
            "road-10k-history-6-0",
            "road-10k-history-6-2",
            "road-10k-history-6-5",
            "road-10k-history-7-0",
            "road-10k-history-7-2",
            "road-10k-history-7-5",
            "road-10k-history-8-0",
            "road-10k-history-8-2",
            "road-10k-history-8-5",
        }
        assert len(audit.history_observation_ids) == 25
        assert audit.selected_template_ids == [
            "road-10k-controlled-threshold-quality-v1",
            "road-10k-specific-interval-quality-v1",
        ]
        assert audit.normalized_constraints == {
            "adult_confirmed": True,
            "current_symptom_stop": False,
            "available_weekdays": [0, 2, 5],
            "weekly_time_limit_min": 180,
            "maximum_session_duration_min": 70,
            "unavailable_dates": [],
            "preferred_longest_easy_weekday": 5,
            "benchmark_date": None,
        }
        assert audit.result_code == "eligible_rolling_proposal"
        assert audit.validation_reason_code is None
        assert not hasattr(audit, "observed_input_snapshot")
        assert not hasattr(audit, "derived_history_statistics")
        assert not hasattr(audit, "validation_results")
        proposal = (
            db.query(PlanProposal)
            .filter(PlanProposal.id == proposal_id)
            .one()
        )
        assert all(
            workout["planned_distance_km"] is None
            for workout in proposal.workout_snapshot
        )
        assert all(
            "distance cap" in workout["workout_description"].casefold()
            for workout in proposal.workout_snapshot
        )

        db.query(ActivitySplit).filter(
            ActivitySplit.user_id == "road-10k-owner",
            ActivitySplit.activity_id == "road-10k-history-1-0",
        ).delete()
        db.add_all([
            ActivitySample(
                user_id="road-10k-owner",
                activity_id="road-10k-history-1-0",
                source="stryd",
                t_sec=0,
                power_watts=250,
                distance_m=0,
            ),
            ActivitySample(
                user_id="road-10k-owner",
                activity_id="road-10k-history-1-0",
                source="stryd",
                t_sec=5,
                power_watts=255,
                distance_m=1000,
            ),
            ActivitySample(
                user_id="road-10k-owner",
                activity_id="road-10k-history-1-0",
                source="stryd",
                t_sec=10,
                power_watts=260,
                distance_m=2000,
            ),
        ])
        db.commit()

        with pytest.raises(AdaptivePlanError) as exc_info:
            validate_road_10k_proposal_adoption(
                db,
                user_id="road-10k-owner",
                proposal=proposal,
            )

        assert exc_info.value.detail["code"] == (
            "ROAD_10K_PROPOSAL_REVALIDATION_FAILED"
        )
        assert exc_info.value.detail["current_source_revision"] != (
            audit.source_revision
        )
