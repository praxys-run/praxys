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


def _athlete_today() -> date:
    return datetime.now(timezone.utc).date()


SCHEDULED_TEST_DATE = _athlete_today() + timedelta(days=1)
SCHEDULED_TEST_DATE_STR = SCHEDULED_TEST_DATE.isoformat()
NEXT_SCHEDULED_TEST_DATE_STR = (
    SCHEDULED_TEST_DATE + timedelta(days=1)
).isoformat()


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


def test_current_goal_purpose_is_resolved_after_the_plan_write_lock(
    goal_api,
    monkeypatch,
) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)
    discovery = client.get(
        "/api/plan/generation/capabilities",
        headers=_headers(user_id),
    )
    assert discovery.status_code == 200, discovery.text
    discovery_body = discovery.json()
    purpose = {
        "capability_id": discovery_body["selected_capability"]["id"],
        "source": "current_goal",
        "expected_goal_id": discovery_body["current_goal"]["id"],
        "expected_goal_revision": discovery_body["current_goal"]["revision"],
    }

    import api.goal_baseline as goal_baseline
    from db.models import GoalBaselineTestRecord, UserConfig
    from db.plan_ledger import lock_plan_writes

    lock_attempted = threading.Event()
    original_lock = goal_baseline.lock_plan_writes

    def observed_lock(db, locked_user_id: str) -> None:
        lock_attempted.set()
        original_lock(db, locked_user_id)

    monkeypatch.setattr(goal_baseline, "lock_plan_writes", observed_lock)
    locker = db_session.SessionLocal()
    try:
        locker.rollback()
        lock_plan_writes(locker, user_id)
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(
                lambda: client.post(
                    "/api/goal/baseline/test",
                    headers={
                        **_headers(user_id),
                        "Idempotency-Key": "goal-test-stale-after-lock",
                    },
                    json={"action": "offer", "purpose": purpose},
                )
            )
            assert lock_attempted.wait(timeout=5)
            config = locker.query(UserConfig).filter(
                UserConfig.user_id == user_id,
            ).one()
            config.goal = {
                "goal_kind": "performance_5k",
                "distance": "5k",
                "target_time_sec": 1_190,
                "race_date": "",
            }
            locker.commit()
            response = pending.result(timeout=10)
    finally:
        locker.close()

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "PLAN_PURPOSE_STALE"
    with db_session.SessionLocal() as db:
        assert db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
        ).count() == 0


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
            "scheduled_date": SCHEDULED_TEST_DATE_STR,
        },
    )
    assert scheduled.status_code == 201, scheduled.text
    payload = scheduled.json()
    assert payload["baseline"]["status"] == "pending_test"
    assert payload["test"]["state"] == "scheduled"
    assert payload["test"]["scheduled_workout"]["date"] == SCHEDULED_TEST_DATE_STR

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
            "scheduled_date": SCHEDULED_TEST_DATE_STR,
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
        observed_date=SCHEDULED_TEST_DATE,
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
        json={"action": "schedule", "scheduled_date": SCHEDULED_TEST_DATE_STR},
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
        json={"action": "schedule", "scheduled_date": SCHEDULED_TEST_DATE_STR},
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
        json={"action": "schedule", "scheduled_date": SCHEDULED_TEST_DATE_STR},
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


def test_shared_history_retires_tests_for_every_plan_purpose(goal_api) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)
    _add_activity(
        db_session,
        user_id=user_id,
        activity_id="shared-history-win",
        observed_date=date(2026, 8, 10),
        distance_km=5.0,
        duration_sec=1_228,
    )
    independent_purpose = {
        "capability_id": "outdoor_road_5k_v1",
        "source": "capability",
    }
    assert client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "shared-history-current-offer",
        },
        json={"action": "offer"},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "shared-history-current-schedule",
        },
        json={"action": "schedule", "scheduled_date": SCHEDULED_TEST_DATE_STR},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "shared-history-independent-offer",
        },
        json={"action": "offer", "purpose": independent_purpose},
    ).status_code == 201
    second_schedule = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "shared-history-independent-schedule",
        },
        json={
            "action": "schedule",
            "scheduled_date": NEXT_SCHEDULED_TEST_DATE_STR,
            "purpose": independent_purpose,
        },
    )
    assert second_schedule.status_code == 409
    assert second_schedule.json()["detail"]["message"] == (
        "A pilot test is already scheduled. Stop or complete it before "
        "scheduling another one."
    )

    confirmed = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "shared-history-confirm",
        },
        json={
            "activity_id": "shared-history-win",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    from db.models import GoalBaselineTestRecord, TrainingPlan

    with db_session.SessionLocal() as db:
        rows = db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
        ).all()
        latest_by_lineage = {
            lineage_id: max(
                (
                    row
                    for row in rows
                    if row.lineage_id == lineage_id
                ),
                key=lambda row: row.version,
            )
            for lineage_id in {row.lineage_id for row in rows}
        }
        assert len(latest_by_lineage) == 2
        assert {
            row.state for row in latest_by_lineage.values()
        } == {"deleted"}
        assert db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
        ).count() == 0


def test_current_purpose_view_blocks_schedule_when_independent_test_scheduled(
    goal_api,
) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)
    independent_purpose = {
        "capability_id": "outdoor_road_5k_v1",
        "source": "capability",
    }
    offered = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "independent-view-offer",
        },
        json={"action": "offer", "purpose": independent_purpose},
    )
    assert offered.status_code == 201, offered.text
    scheduled = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "independent-view-schedule",
        },
        json={
            "action": "schedule",
            "scheduled_date": (
                date.today() + timedelta(days=7)
            ).isoformat(),
            "purpose": independent_purpose,
        },
    )
    assert scheduled.status_code == 201, scheduled.text

    current = client.get("/api/goal", headers=_headers(user_id))

    assert current.status_code == 200, current.text
    baseline = current.json()["baseline"]
    assert baseline["test"]["state"] == "not_offered"
    assert baseline["test"]["can_schedule"] is False
    assert baseline["timeline"] == []


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
        json={"action": "schedule", "scheduled_date": SCHEDULED_TEST_DATE_STR},
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
        assert latest.idempotency_key is not None
        assert len(latest.idempotency_key) <= 128


def test_repeated_goal_change_cleanup_uses_distinct_bounded_keys(
    goal_api,
) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    supported_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
        "race_date": "",
    }
    unsupported_goal = {
        "goal_kind": "race",
        "distance": "5k",
        "race_date": "2026-10-20",
        "target_time_sec": 1_200,
    }
    _seed_goal_user(db_session, user_id)

    for cycle in range(2):
        assert client.post(
            "/api/goal/baseline/test",
            headers={
                **_headers(user_id),
                "Idempotency-Key": f"goal-change-cycle-offer-{cycle}",
            },
            json={"action": "offer"},
        ).status_code == 201
        updated = client.put(
            "/api/settings",
            headers=_headers(user_id),
            json={"goal": unsupported_goal},
        )
        assert updated.status_code == 200, updated.text
        if cycle == 0:
            restored = client.put(
                "/api/settings",
                headers=_headers(user_id),
                json={"goal": supported_goal},
            )
            assert restored.status_code == 200, restored.text

    from db.models import GoalBaselineTestRecord

    with db_session.SessionLocal() as db:
        deleted = db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
            GoalBaselineTestRecord.state == "deleted",
        ).all()
        keys = [row.idempotency_key for row in deleted]
        assert len(keys) == 2
        assert len(set(keys)) == 2
        assert all(key is not None and len(key) <= 128 for key in keys)


def test_goal_change_preserves_independent_baseline_test_lineage(goal_api) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)
    assert client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "goal-test-current-offer",
        },
        json={"action": "offer"},
    ).status_code == 201
    purpose = {
        "capability_id": "outdoor_road_5k_v1",
        "source": "capability",
    }
    assert client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "goal-test-independent-offer",
        },
        json={"action": "offer", "purpose": purpose},
    ).status_code == 201
    scheduled = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "goal-test-independent-schedule",
        },
        json={
            "action": "schedule",
            "scheduled_date": SCHEDULED_TEST_DATE_STR,
            "purpose": purpose,
        },
    )
    assert scheduled.status_code == 201, scheduled.text

    from db.models import GoalBaselineTestRecord, TrainingPlan

    with db_session.SessionLocal() as db:
        rows = db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
        ).all()
        assert {row.purpose_source for row in rows} == {
            "current_goal",
            "capability",
        }
        assert len({row.lineage_id for row in rows}) == 2

    updated = client.put(
        "/api/settings",
        headers=_headers(user_id),
        json={
            "goal": {
                "goal_kind": "race",
                "distance": "5k",
                "race_date": "2026-10-20",
                "target_time_sec": 1_200,
            },
        },
    )
    assert updated.status_code == 200, updated.text

    with db_session.SessionLocal() as db:
        current = db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
            GoalBaselineTestRecord.purpose_source == "current_goal",
        ).order_by(
            GoalBaselineTestRecord.version.desc(),
            GoalBaselineTestRecord.created_at.desc(),
        ).first()
        independent = db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
            GoalBaselineTestRecord.purpose_source == "capability",
        ).order_by(
            GoalBaselineTestRecord.version.desc(),
            GoalBaselineTestRecord.created_at.desc(),
        ).first()
        assert current is not None
        assert current.state in {"deleted", "invalidated"}
        assert independent is not None
        assert independent.state == "scheduled"
        assert db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
        ).count() == 1


def test_pilot_snapshots_are_isolated_by_plan_purpose(goal_api) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)

    from analysis.goal_baseline import (
        BASELINE_PROTOCOL_ID,
        BaselineActivity,
        build_goal_baseline_goal,
    )
    from api.goal_baseline import (
        _record_test_snapshot,
        build_goal_baseline_view,
        resolve_goal_baseline_snapshot_id,
    )
    from api.plan_generation_capabilities import current_goal_reference
    from db.models import GoalBaselineTestRecord

    raw_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
        "race_date": "",
    }
    goal = build_goal_baseline_goal(raw_goal)
    reference = current_goal_reference(user_id=user_id, goal=raw_goal)
    assert reference is not None
    observed_date = date.today() - timedelta(days=1)
    current_test = GoalBaselineTestRecord(
        id="current-purpose-test",
        lineage_id="current-purpose-lineage",
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        purpose_source="current_goal",
        source_goal_id=reference.goal_id,
        source_goal_revision=reference.revision,
        version=1,
        state="completed",
        protocol_id=BASELINE_PROTOCOL_ID,
        request_fingerprint="c" * 64,
        activity_id="current-purpose-activity",
        observed_date=observed_date,
        measured_5k=True,
        elapsed_timing_confirmed=True,
        protocol_followed=True,
        created_at=datetime.utcnow() - timedelta(minutes=1),
    )
    independent_test = GoalBaselineTestRecord(
        id="independent-purpose-test",
        lineage_id="independent-purpose-lineage",
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        purpose_source="capability",
        source_goal_id=None,
        source_goal_revision=None,
        version=1,
        state="completed",
        protocol_id=BASELINE_PROTOCOL_ID,
        request_fingerprint="i" * 64,
        activity_id="independent-purpose-activity",
        observed_date=observed_date,
        measured_5k=True,
        elapsed_timing_confirmed=True,
        protocol_followed=True,
        created_at=datetime.utcnow(),
    )
    with db_session.SessionLocal() as db:
        db.add_all([current_test, independent_test])
        db.flush()
        current_snapshot = _record_test_snapshot(
            db,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            test=current_test,
            activity=BaselineActivity(
                activity_id="current-purpose-activity",
                observed_date=observed_date,
                distance_km=5.0,
                duration_sec=1_500,
                activity_type="running",
                source="garmin",
            ),
            created_at=datetime.utcnow() - timedelta(minutes=1),
        )
        independent_snapshot = _record_test_snapshot(
            db,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            test=independent_test,
            activity=BaselineActivity(
                activity_id="independent-purpose-activity",
                observed_date=observed_date,
                distance_km=5.0,
                duration_sec=1_400,
                activity_type="running",
                source="garmin",
            ),
            created_at=datetime.utcnow(),
        )
        db.commit()
        current_snapshot_id = current_snapshot.id
        independent_snapshot_id = independent_snapshot.id
        assert current_snapshot.lineage_id != independent_snapshot.lineage_id
        assert current_snapshot.version == 1
        assert independent_snapshot.version == 1

    independent_purpose = {
        "capability_id": "outdoor_road_5k_v1",
        "source": "capability",
    }
    with db_session.SessionLocal() as db:
        current = build_goal_baseline_view(db, user_id=user_id)
        independent = build_goal_baseline_view(
            db,
            user_id=user_id,
            purpose_selection=independent_purpose,
        )
        assert current["baseline"]["evidence"]["elapsed_time_sec"] == 1_500
        assert independent["baseline"]["evidence"]["elapsed_time_sec"] == 1_400
        assert resolve_goal_baseline_snapshot_id(
            db,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            evidence=current["baseline"]["evidence"],
        ) == current_snapshot_id
        assert resolve_goal_baseline_snapshot_id(
            db,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            evidence=independent["baseline"]["evidence"],
            purpose_selection=independent_purpose,
        ) == independent_snapshot_id


def test_goal_and_garmin_transition_imports_before_plan_lock(
    goal_api,
    monkeypatch,
) -> None:
    _, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)

    import api.routes.settings as settings
    import db.plan_ledger as plan_ledger
    from db.models import UserConfig

    with db_session.SessionLocal() as db:
        config = db.query(UserConfig).filter(
            UserConfig.user_id == user_id,
        ).one()
        config.connections = ["stryd", "garmin"]
        config.source_options = {
            **config.source_options,
            "garmin_region": "international",
        }
        config.plan_management = {
            "mode": "external",
            "execution_target": "stryd",
            "delivery_enabled": False,
            "adjustment_policy": "suggest_only",
        }
        db.commit()

    events: list[tuple[str, bool]] = []

    def import_legacy(db, *args, **kwargs) -> str:
        events.append(("import", db.in_transaction()))
        return "missing"

    def lock_writes(db, *args, **kwargs) -> None:
        events.append(("lock", db.in_transaction()))

    class StopAfterLock(RuntimeError):
        pass

    def stop_during_apply(*args, **kwargs) -> None:
        raise StopAfterLock

    monkeypatch.setattr(
        plan_ledger,
        "import_legacy_stryd_status",
        import_legacy,
    )
    monkeypatch.setattr(
        plan_ledger,
        "has_unresolved_legacy_stryd_corruption",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(plan_ledger, "lock_plan_writes", lock_writes)
    monkeypatch.setattr(
        settings,
        "_garmin_delivery_eligibility",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        settings,
        "_apply_plan_management_update",
        stop_during_apply,
    )
    body = settings.SettingsUpdate(
        goal={"target_time_sec": 1_190},
        plan_management={"execution_target": "garmin"},
    )
    with db_session.SessionLocal() as db:
        with pytest.raises(StopAfterLock):
            settings._update_settings(body, user_id, db)

    assert events == [("import", False), ("lock", False)]


def test_unrelated_settings_update_locks_before_final_config_reload(
    goal_api,
    monkeypatch,
) -> None:
    _, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)

    import api.routes.settings as settings
    import db.plan_ledger as plan_ledger

    events: list[str] = []
    real_load = settings.load_config_from_db

    class StopAfterReload(RuntimeError):
        pass

    def tracked_load(*args, **kwargs):
        events.append("load")
        if events == ["load", "lock", "load"]:
            raise StopAfterReload
        return real_load(*args, **kwargs)

    def tracked_lock(*args, **kwargs) -> None:
        events.append("lock")

    monkeypatch.setattr(settings, "load_config_from_db", tracked_load)
    monkeypatch.setattr(plan_ledger, "lock_plan_writes", tracked_lock)

    with db_session.SessionLocal() as db:
        with pytest.raises(StopAfterReload):
            settings._update_settings(
                settings.SettingsUpdate(language="zh"),
                user_id,
                db,
            )

    assert events == ["load", "lock", "load"]


def test_legacy_baseline_test_rows_belong_only_to_current_goal_flow(
    goal_api,
) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)
    offered = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "goal-test-legacy-lineage",
        },
        json={"action": "offer"},
    )
    assert offered.status_code == 201, offered.text

    from api.goal_baseline import build_goal_baseline_view
    from db.models import GoalBaselineTestRecord

    with db_session.SessionLocal() as db:
        row = db.query(GoalBaselineTestRecord).filter(
            GoalBaselineTestRecord.user_id == user_id,
        ).one()
        row.purpose_source = None
        row.source_goal_id = None
        row.source_goal_revision = None
        legacy_id = row.id
        db.commit()

    with db_session.SessionLocal() as db:
        current = build_goal_baseline_view(db, user_id=user_id)
        independent = build_goal_baseline_view(
            db,
            user_id=user_id,
            purpose_selection={
                "capability_id": "outdoor_road_5k_v1",
                "source": "capability",
            },
        )

    assert current["baseline"]["test"]["state"] == "offered"
    assert any(
        item["id"] == legacy_id
        for item in current["baseline"]["timeline"]
    )
    assert independent["baseline"]["test"]["state"] == "not_offered"
    assert all(
        item["id"] != legacy_id
        for item in independent["baseline"]["timeline"]
    )


def test_pre_purpose_baseline_idempotency_replays_without_provenance(
    goal_api,
) -> None:
    client, db_session = goal_api
    user_id = "goal-baseline-owner"
    _seed_goal_user(db_session, user_id)
    _add_activity(
        db_session,
        user_id=user_id,
        activity_id="legacy-idempotency-race",
        observed_date=date(2026, 8, 10),
        distance_km=5.0,
        duration_sec=1_220,
    )

    from analysis.goal_baseline import (
        BASELINE_PROTOCOL_ID,
        build_goal_baseline_goal,
    )
    from api.goal_baseline import _request_fingerprint
    from db.models import (
        GoalBaselineConfirmation,
        GoalBaselineTestRecord,
    )

    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
        "race_date": "",
    })
    with db_session.SessionLocal() as db:
        db.add(GoalBaselineConfirmation(
            lineage_id="legacy-confirmation-lineage",
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=1,
            activity_id="legacy-idempotency-race",
            response="race",
            measured_5k=True,
            elapsed_timing_confirmed=True,
            request_fingerprint=_request_fingerprint({
                "activity_id": "legacy-idempotency-race",
                "response": "race",
                "measured_5k": True,
                "elapsed_timing_confirmed": True,
                "supersedes_confirmation_id": None,
                "goal_signature": goal.goal_signature,
            }),
            idempotency_key="legacy-confirmation-key",
        ))
        db.add(GoalBaselineTestRecord(
            lineage_id="legacy-test-lineage",
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=1,
            state="offered",
            protocol_id=BASELINE_PROTOCOL_ID,
            request_fingerprint=_request_fingerprint({
                "action": "offer",
                "scheduled_date": None,
                "activity_id": None,
                "measured_5k": None,
                "elapsed_timing_confirmed": None,
                "protocol_followed": None,
                "reason_code": None,
                "goal_signature": goal.goal_signature,
            }),
            idempotency_key="legacy-test-key",
        ))
        db.commit()

    confirmation = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "legacy-confirmation-key",
        },
        json={
            "activity_id": "legacy-idempotency-race",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["replayed"] is True

    test = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers(user_id),
            "Idempotency-Key": "legacy-test-key",
        },
        json={"action": "offer"},
    )
    assert test.status_code == 200, test.text
    assert test.json()["replayed"] is True


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


def test_history_search_deduplicates_providers_and_rejects_hidden_duplicate(
    goal_api,
) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="garmin-run",
        observed_date=date(2026, 8, 9),
        distance_km=5.0,
        duration_sec=1_240,
        source="garmin",
    )
    _add_activity(
        db_session,
        activity_id="stryd-duplicate",
        observed_date=date(2026, 8, 9),
        distance_km=5.01,
        duration_sec=1_245,
        source="stryd",
    )

    response = client.get("/api/goal", headers=_headers("goal-baseline-owner"))
    assert response.status_code == 200, response.text
    assert [
        candidate["activity_id"]
        for candidate in response.json()["baseline"]["candidates"]
    ] == ["garmin-run"]

    hidden = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-hidden-duplicate",
        },
        json={
            "activity_id": "stryd-duplicate",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert hidden.status_code == 404


def test_history_search_deduplicates_with_deterministic_source_fallback(
    goal_api,
) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    from db.models import UserConfig

    with db_session.SessionLocal() as db:
        config = db.query(UserConfig).filter(
            UserConfig.user_id == "goal-baseline-owner",
        ).one()
        config.preferences = {
            key: value
            for key, value in (config.preferences or {}).items()
            if key != "activities"
        }
        db.commit()
    _add_activity(
        db_session,
        activity_id="garmin-fallback",
        observed_date=date(2026, 8, 9),
        distance_km=5.0,
        duration_sec=1_240,
        source="garmin",
    )
    _add_activity(
        db_session,
        activity_id="stryd-fallback-duplicate",
        observed_date=date(2026, 8, 9),
        distance_km=5.0,
        duration_sec=1_245,
        source="stryd",
    )

    response = client.get("/api/goal", headers=_headers("goal-baseline-owner"))
    assert response.status_code == 200, response.text
    assert len(response.json()["baseline"]["candidates"]) == 1


def test_history_search_deduplicates_secondary_provider_cluster(
    goal_api,
) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="garmin-unrelated",
        observed_date=date(2026, 8, 10),
        distance_km=10.0,
        duration_sec=3_000,
        source="garmin",
    )
    _add_activity(
        db_session,
        activity_id="stryd-secondary-duplicate",
        observed_date=date(2026, 8, 9),
        distance_km=5.0,
        duration_sec=1_240,
        source="stryd",
    )
    _add_activity(
        db_session,
        activity_id="coros-secondary-winner",
        observed_date=date(2026, 8, 9),
        distance_km=5.01,
        duration_sec=1_245,
        source="coros",
    )

    response = client.get("/api/goal", headers=_headers("goal-baseline-owner"))
    assert response.status_code == 200, response.text
    assert [
        candidate["activity_id"]
        for candidate in response.json()["baseline"]["candidates"]
    ] == ["coros-secondary-winner"]

    hidden = client.post(
        "/api/goal/baseline/history/confirm",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-history-secondary-hidden-duplicate",
        },
        json={
            "activity_id": "stryd-secondary-duplicate",
            "response": "race",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
        },
    )
    assert hidden.status_code == 404


def test_completed_test_requires_a_candidate_from_the_scheduled_window(goal_api) -> None:
    client, db_session = goal_api
    _seed_goal_user(db_session)
    _add_activity(
        db_session,
        activity_id="old-run",
        observed_date=SCHEDULED_TEST_DATE - timedelta(days=1),
        distance_km=5.0,
        duration_sec=1300,
    )
    _add_activity(
        db_session,
        activity_id="later-run",
        observed_date=SCHEDULED_TEST_DATE + timedelta(days=1),
        distance_km=5.0,
        duration_sec=1_290,
    )
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-offer-window"},
        json={"action": "offer"},
    ).status_code == 201
    assert client.post(
        "/api/goal/baseline/test",
        headers={**_headers("goal-baseline-owner"), "Idempotency-Key": "goal-test-schedule-window"},
        json={"action": "schedule", "scheduled_date": SCHEDULED_TEST_DATE_STR},
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

    later = client.post(
        "/api/goal/baseline/test",
        headers={
            **_headers("goal-baseline-owner"),
            "Idempotency-Key": "goal-test-complete-later-window",
        },
        json={
            "action": "complete",
            "activity_id": "later-run",
            "measured_5k": True,
            "elapsed_timing_confirmed": True,
            "protocol_followed": True,
        },
    )
    assert later.status_code == 409


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
