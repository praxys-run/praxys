"""API contract coverage for the history-first 5 km baseline flow."""
from __future__ import annotations

import importlib
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest


@pytest.fixture
def goal_api(monkeypatch):
    """Yield an authenticated TestClient backed by an isolated SQLite DB."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv("PRAXYS_JWT_SECRET", "goal-baseline-test-secret")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    import api.main

    importlib.reload(api.main)
    app = api.main.app

    from db.models import User

    with db_session.SessionLocal() as db:
        db.add_all([
            User(
                id="goal-baseline-owner",
                email="goal-owner@example.test",
                hashed_password="x",
                is_active=True,
            ),
            User(
                id="goal-baseline-other",
                email="goal-other@example.test",
                hashed_password="x",
                is_active=True,
            ),
            User(
                id="goal-baseline-admin",
                email="goal-admin@example.test",
                hashed_password="x",
                is_active=True,
                is_superuser=True,
            ),
        ])
        db.commit()

    with TestClient(app) as client:
        yield client, db_session

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


def _token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "aud": "fastapi-users:auth",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(
        payload,
        "goal-baseline-test-secret",
        algorithm="HS256",
    )


def _headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _seed_goal_user(
    db_session,
    user_id: str = "goal-baseline-owner",
    *,
    athlete_timezone: str = "UTC",
) -> None:
    from db.models import UserConfig

    with db_session.SessionLocal() as db:
        config = db.query(UserConfig).filter(UserConfig.user_id == user_id).first()
        if config is None:
            config = UserConfig(user_id=user_id)
            db.add(config)
        config.goal = {
            "goal_kind": "performance_5k",
            "distance": "5k",
            "target_time_sec": 1_200,
            "race_date": "",
        }
        config.source_options = {
            **(config.source_options or {}),
            "athlete_timezone": athlete_timezone,
        }
        config.preferences = {
            **(config.preferences or {}),
            "activities": "garmin",
        }
        db.commit()


def _add_activity(
    db_session,
    *,
    user_id: str = "goal-baseline-owner",
    activity_id: str,
    observed_date: date,
    distance_km: float,
    duration_sec: float,
    activity_type: str = "running",
    source: str = "garmin",
) -> None:
    from db.models import Activity, ActivitySplit

    with db_session.SessionLocal() as db:
        db.add(Activity(
            user_id=user_id,
            activity_id=activity_id,
            date=observed_date,
            distance_km=distance_km,
            duration_sec=duration_sec,
            activity_type=activity_type,
            source=source,
        ))
        for split_num in range(1, 6):
            db.add(ActivitySplit(
                user_id=user_id,
                activity_id=activity_id,
                split_num=split_num,
                duration_sec=duration_sec / 5,
                distance_km=1.0,
            ))
        db.commit()


def test_goal_endpoint_surfaces_history_candidates_without_qualifying_them(
    goal_api,
) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="close-run",
        observed_date=date(2026, 8, 9),
        distance_km=5.05,
        duration_sec=1_250,
    )
    _add_activity(
        db_session,
        activity_id="long-run",
        observed_date=date(2026, 8, 8),
        distance_km=10.0,
        duration_sec=3_000,
    )
    _add_activity(
        db_session,
        activity_id="trail-run",
        observed_date=date(2026, 8, 7),
        distance_km=5.01,
        duration_sec=1_260,
        activity_type="trail_running",
    )

    response = client.get("/api/goal", headers=_headers("goal-baseline-owner"))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["goal_kind"] == "performance_5k"
    baseline = payload["baseline"]
    assert baseline["status"] == "incomparable"
    assert baseline["readiness"] == "insufficient_evidence"
    assert baseline["evidence"] is None
    assert [candidate["activity_id"] for candidate in baseline["candidates"]] == [
        "close-run"
    ]
    assert baseline["candidates"][0]["review_state"] == "needs_confirmation"
    assert baseline["test"]["state"] == "not_offered"
    assert baseline["test"]["can_schedule"] is True


def test_history_confirmation_is_idempotent_and_owner_scoped(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="history-run",
        observed_date=date(2026, 8, 9),
        distance_km=5.06,
        duration_sec=1_240,
    )
    _seed_goal_user(db_session, user_id="goal-baseline-other")

    body = {
        "activity_id": "history-run",
        "response": "intentional_all_out",
        "measured_5k": True,
        "elapsed_timing_confirmed": True,
    }
    created = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-confirm-1",
        },
        json=body,
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["replayed"] is False
    confirmation_id = created_body["confirmation"]["id"]
    assert created_body["baseline"]["status"] == "current"

    replayed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-confirm-1",
        },
        json=body,
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["replayed"] is True
    assert replayed.json()["confirmation"]["id"] == confirmation_id

    conflict = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-confirm-1",
        },
        json={**body, "response": "race"},
    )
    assert conflict.status_code == 409

    forbidden = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-other"),
            "Idempotency-Key": "goal-history-confirm-other",
        },
        json=body,
    )
    assert forbidden.status_code == 404

    latest = client.get("/api/goal", headers=_headers("goal-baseline-owner"))
    assert latest.status_code == 200
    assert latest.json()["baseline"]["status"] == "current"
    assert latest.json()["baseline"]["evidence"]["provenance"] == (
        "intentional_all_out"
    )


def test_history_confirmation_can_be_corrected_with_a_successor(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="correct-me",
        observed_date=date(2026, 8, 5),
        distance_km=5.02,
        duration_sec=1_238,
    )

    first = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-correct-1",
        },
        json={
            "activity_id": "correct-me",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert first.status_code == 201, first.text
    correction = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-correct-2",
        },
        json={
            "activity_id": "correct-me",
            "response": "not_all_out",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
            "supersedes_confirmation_id": first.json()["confirmation"]["id"],
        },
    )
    assert correction.status_code == 201, correction.text
    payload = correction.json()
    assert payload["baseline"]["status"] == "incomparable"
    assert payload["confirmation"]["version"] == 2


def test_concurrent_confirmation_replays_instead_of_duplicating(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="concurrent-run",
        observed_date=date(2026, 8, 6),
        distance_km=5.04,
        duration_sec=1_236,
    )
    barrier = threading.Barrier(2)

    def submit():
        barrier.wait()
        return client.post(
            "/api/goal/baseline/history/confirm",
            headers={
                **_headers("goal-baseline-owner"),
                "Idempotency-Key": "goal-history-concurrent",
            },
            json={
                "activity_id": "concurrent-run",
                "response": "race",
                "measured_5k": True,
                "elapsed_timing_confirmed": True,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: submit(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert len({
        response.json()["confirmation"]["id"]
        for response in responses
    }) == 1


def test_optional_test_schedule_creates_canonical_workout_and_revision(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)

    offered = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-offer-1",
        },
        json={"action": "offer"},
    )
    assert offered.status_code == 201, offered.text
    assert offered.json()["baseline"]["status"] == "pending_test"
    assert offered.json()["test"]["state"] == "offered"

    scheduled = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-schedule-1",
        },
        json={
            "action": "schedule",
            "scheduled_date": "2026-08-20",
        },
    )
    assert scheduled.status_code == 201, scheduled.text
    payload = scheduled.json()
    assert payload["baseline"]["status"] == "pending_test"
    assert payload["test"]["state"] == "scheduled"
    assert payload["test"]["scheduled_workout"]["date"] == "2026-08-20"

    from db.models import PlanRevision, TrainingPlan

    with db_session.SessionLocal() as db:
        workouts = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == "goal-baseline-owner"
        ).all()
        assert len(workouts) == 1
        assert workouts[0].source == "praxys"
        assert workouts[0].planned_distance_km == 5.0
        revisions = db.query(PlanRevision).filter(
            PlanRevision.user_id == "goal-baseline-owner",
            PlanRevision.operation == "goal_baseline_test_schedule",
        ).all()
        assert len(revisions) == 1

    replayed = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-schedule-1",
        },
        json={
            "action": "schedule",
            "scheduled_date": "2026-08-20",
        },
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["replayed"] is True


def test_stopped_test_preserves_no_test_path_without_blocking_account(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)

    offered = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-offer-stop",
        },
        json={"action": "offer"},
    )
    assert offered.status_code == 201, offered.text

    stopped = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-stop-1",
        },
        json={
            "action": "stop",
            "reason_code": "chest_pain_or_pressure",
        },
    )
    assert stopped.status_code == 201, stopped.text
    payload = stopped.json()
    assert payload["baseline"]["status"] == "missing"
    assert payload["baseline"]["readiness"] == "non_diagnostic_safety_stop"
    assert payload["test"]["state"] == "stopped"


def test_completion_requires_explicit_protocol_checks_and_never_auto_qualifies(
    goal_api,
) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="test-attempt",
        observed_date=date(2026, 8, 20),
        distance_km=5.03,
        duration_sec=1_230,
    )

    offered = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-offer-complete",
        },
        json={"action": "offer"},
    )
    assert offered.status_code == 201, offered.text
    scheduled = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-schedule-complete",
        },
        json={"action": "schedule", "scheduled_date": "2026-08-20"},
    )
    assert scheduled.status_code == 201, scheduled.text

    completed = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-complete-1",
        },
        json={
            "action": "complete",
            "activity_id": "test-attempt",
            "measured_5k": True,
            "elapsed_timing_confirmed": False,
            "protocol_followed": False,
        },
    )
    assert completed.status_code == 201, completed.text
    payload = completed.json()
    assert payload["baseline"]["status"] == "incomparable"
    assert payload["baseline"]["readiness"] == "insufficient_evidence"
    assert payload["test"]["state"] == "invalidated"
    assert payload["baseline"]["evidence"] is None


def test_schedule_stop_cleans_up_the_scheduled_workout(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)

    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-offer-cleanup"},
        json={"action": "offer"},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-schedule-cleanup"},
        json={"action": "schedule", "scheduled_date": "2026-08-20"},
    ).status_code == 201
    stopped = client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-stop-cleanup"},
        json={"action": "stop", "reason_code": "injury_or_pain_altering_running"},
    )
    assert stopped.status_code == 201, stopped.text

    from db.models import TrainingPlan

    with db_session.SessionLocal() as db:
        assert db.query(TrainingPlan).filter(TrainingPlan.user_id == "goal-baseline-owner").count() == 0


def test_current_history_retires_pending_optional_test(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="history-win",
        observed_date=date(2026, 8, 10),
        distance_km=5.0,
        duration_sec=1228,
    )
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-offer-retire"},
        json={"action": "offer"},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-schedule-retire"},
        json={"action": "schedule", "scheduled_date": "2026-08-20"},
    ).status_code == 201

    confirmed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-history-retire-test"},
        json={
            "activity_id": "history-win",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    from db.models import GoalBaselineTestRecord, TrainingPlan

    with db_session.SessionLocal() as db:
        assert db.query(TrainingPlan).filter(TrainingPlan.user_id == "goal-baseline-owner").count() == 0
        latest = db.query(GoalBaselineTestRecord).filter(GoalBaselineTestRecord.user_id == "goal-baseline-owner").order_by(GoalBaselineTestRecord.created_at.desc(), GoalBaselineTestRecord.version.desc()).first()
        assert latest is not None
        assert latest.state == "deleted"


def test_current_history_blocks_optional_test_scheduling(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="already-current",
        observed_date=date(2026, 8, 10),
        distance_km=5.0,
        duration_sec=1235,
    )
    confirmed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-history-current-block"},
        json={
            "activity_id": "already-current",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    scheduled = client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-schedule-blocked"},
        json={"action": "schedule", "scheduled_date": "2026-08-20"},
    )
    assert scheduled.status_code == 409
    assert scheduled.json()["detail"]["message"] == (
        "Qualified current history already exists, so the optional pilot test is unavailable."
    )


def test_goal_change_retires_pending_baseline_tests(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-offer-goal-change"},
        json={"action": "offer"},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-schedule-goal-change"},
        json={"action": "schedule", "scheduled_date": "2026-08-20"},
    ).status_code == 201

    updated = client.put(
        "/api/settings",
        headers=_headers("goal-baseline-owner"),
        json={
            "goal": {
                "goal_kind": "race",
                "distance": "5k",
                "race_date": "2026-10-20",
                "target_time_sec": 1200,
            },
        },
    )
    assert updated.status_code == 200, updated.text

    from db.models import GoalBaselineTestRecord, TrainingPlan

    with db_session.SessionLocal() as db:
        assert db.query(TrainingPlan).filter(TrainingPlan.user_id == "goal-baseline-owner").count() == 0
        latest = db.query(GoalBaselineTestRecord).filter(GoalBaselineTestRecord.user_id == "goal-baseline-owner").order_by(GoalBaselineTestRecord.created_at.desc(), GoalBaselineTestRecord.version.desc()).first()
        assert latest is not None
        assert latest.state == "deleted"


def test_history_search_considers_non_preferred_sources(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="stryd-run",
        observed_date=date(2026, 8, 9),
        distance_km=5.0,
        duration_sec=1240,
        source="stryd",
    )

    response = client.get("/api/goal", headers=_headers("goal-baseline-owner"))
    assert response.status_code == 200, response.text
    assert [candidate["activity_id"] for candidate in response.json()["baseline"]["candidates"]] == ["stryd-run"]


def test_completed_test_requires_a_candidate_from_the_scheduled_window(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="old-run",
        observed_date=date(2026, 8, 1),
        distance_km=5.0,
        duration_sec=1300,
    )
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-offer-window"},
        json={"action": "offer"},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-schedule-window"},
        json={"action": "schedule", "scheduled_date": "2026-08-20"},
    ).status_code == 201

    completed = client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-complete-window"},
        json={
            "action": "complete",
            "activity_id": "old-run",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
            "protocol_followed": True,
        },
    )
    assert completed.status_code == 409


def test_admin_evaluation_is_aggregate_only(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="eval-run",
        observed_date=date(2026, 8, 10),
        distance_km=5.0,
        duration_sec=1_240,
    )

    confirmed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-eval-1",
        },
        json={
            "activity_id": "eval-run",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    denied = client.get(
        "/api/goal/baseline/evaluation",
        headers=_headers("goal-baseline-owner"),
    )
    assert denied.status_code == 403

    response = client.get(
        "/api/goal/baseline/evaluation",
        headers=_headers("goal-baseline-admin"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    serialized = json.dumps(payload)

    assert payload["policy_version"] == "preplan-baseline-policy-v1"
    assert payload["operational_counts"]["history_confirmations"] == 1
    assert payload["checks"]["subgroup"]["state"] == "not_measured"
    assert payload["checks"]["adverse_outcomes"]["state"] == "not_measured"
    assert "goal-baseline-owner" not in serialized
    assert "activity_id" not in serialized
    assert "user_id" not in serialized
