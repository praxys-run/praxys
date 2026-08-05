"""Regression tests for aborted-transaction recovery in Garmin sync.

Issue: when a write in one sync section fails with a DB error on PostgreSQL,
the transaction is left in an aborted state, making all subsequent queries on
the same session fail with "current transaction is aborted, commands ignored
until end of transaction block".

Fix: each independent write section in _sync_garmin uses db.begin_nested()
(a SAVEPOINT in PostgreSQL, a SQL SAVEPOINT in SQLite via SQLAlchemy) so that
a write failure only rolls back that section — the outer transaction, and all
earlier writes (activities, splits), remain intact.
"""
import tempfile

import pytest
import requests
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def db_with_user(monkeypatch):
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
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

    from db.models import User
    user_id = "test-user-garmin-tx"
    db = db_session.SessionLocal()
    db.add(User(id=user_id, email="garmin-tx@example.com", hashed_password="x"))
    db.commit()
    try:
        yield db, user_id
    finally:
        db.close()
        if db_session.engine is not None:
            db_session.engine.dispose()
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def test_write_failure_in_nested_transaction_does_not_abort_outer(db_with_user):
    """A DB write failure inside db.begin_nested() leaves the outer transaction intact.

    This is the core regression check: before the fix, a DB error inside one
    sync section (e.g. write_lactate_threshold) would abort the PostgreSQL
    transaction, causing all subsequent writes to raise "current transaction is
    aborted".  After the fix, only the savepoint is rolled back, and the outer
    transaction (with activities, splits etc.) remains valid.
    """
    from db import sync_writer
    from db.models import Activity, RecoveryData

    db, user_id = db_with_user

    # Step 1 — write an activity (simulates the early writes in _sync_garmin).
    sync_writer.write_activities(user_id, [{
        "activity_id": "act-tx-001",
        "date": "2024-03-01",
        "activity_type": "running",
        "distance_km": 10.0,
        "duration_sec": 3600,
    }], db)

    # Step 2 — simulate a DB write failure wrapped in db.begin_nested(), exactly
    # as the fixed _sync_garmin does.  We trigger an IntegrityError by trying to
    # insert a duplicate FitnessData row (unique constraint on user/date/metric/source).
    from db.models import FitnessData
    from datetime import date

    db.add(FitnessData(
        user_id=user_id, date=date(2024, 3, 1),
        metric_type="lthr_bpm", value=170.0, source="garmin",
    ))
    db.flush()  # stage the first row so the second insert is a duplicate

    try:
        with db.begin_nested():
            # Duplicate insert — raises IntegrityError; savepoint rolls back only
            # this block, outer transaction stays alive.
            db.add(FitnessData(
                user_id=user_id, date=date(2024, 3, 1),
                metric_type="lthr_bpm", value=175.0, source="garmin",
            ))
            db.flush()
    except IntegrityError:
        pass  # expected — savepoint rolled back, outer tx still valid

    # Step 3 — write recovery data AFTER the savepoint failure.  This must
    # succeed; if the outer transaction had been aborted, this would raise
    # "current transaction is aborted" (PostgreSQL) or a similar session error.
    count = sync_writer.write_recovery(user_id, [], [], {}, db, garmin_recovery=[{
        "date": "2024-03-01",
        "readiness_score": 85,
        "hrv_ms": 55.0,
    }])
    assert count == 1, "Recovery write must succeed after a savepoint failure"

    # Step 4 — commit and verify all prior work is preserved.
    db.commit()

    activity = db.query(Activity).filter_by(
        user_id=user_id, activity_id="act-tx-001",
    ).first()
    assert activity is not None, "Activity written before the failure must be preserved"

    recovery = db.query(RecoveryData).filter_by(
        user_id=user_id, source="garmin",
    ).first()
    assert recovery is not None
    assert recovery.readiness_score == 85

    # The failed duplicate insert must not have persisted.
    fitness_rows = db.query(FitnessData).filter_by(
        user_id=user_id, metric_type="lthr_bpm",
    ).all()
    assert len(fitness_rows) == 1, "Only the first (successful) insert should be present"
    assert fitness_rows[0].value == 170.0


def test_independent_write_sections_all_succeed_when_no_failures(db_with_user):
    """All four independent write sections in _sync_garmin succeed when their
    data is valid — the savepoint wrapper is transparent on the happy path."""
    from db import sync_writer
    from db.models import Activity, FitnessData, RecoveryData
    from datetime import date

    db, user_id = db_with_user

    # activities
    sync_writer.write_activities(user_id, [{
        "activity_id": "act-happy-001",
        "date": "2024-04-01",
        "activity_type": "running",
        "distance_km": 5.0,
    }], db)

    # lactate threshold (uses begin_nested in sync)
    with db.begin_nested():
        sync_writer.write_lactate_threshold(user_id, [{
            "date": "2024-04-01",
            "lthr_bpm": 168.0,
        }], db)

    # profile thresholds (uses begin_nested in sync)
    with db.begin_nested():
        sync_writer.write_profile_thresholds(user_id, {
            "max_hr_bpm": 192.0,
            "rest_hr_bpm": 48.0,
        }, db)

    # daily metrics (uses begin_nested in sync)
    with db.begin_nested():
        sync_writer.write_daily_metrics(user_id, [{
            "date": "2024-04-01",
            "vo2max": 58.5,
        }], db)

    # recovery (uses begin_nested in sync)
    with db.begin_nested():
        sync_writer.write_recovery(user_id, [], [], {}, db, garmin_recovery=[{
            "date": "2024-04-01",
            "readiness_score": 90,
        }])

    db.commit()

    assert db.query(Activity).filter_by(user_id=user_id).count() == 1
    assert db.query(FitnessData).filter_by(user_id=user_id).count() >= 1
    assert db.query(RecoveryData).filter_by(user_id=user_id).count() == 1


def test_garmin_calendar_snapshot_persists_and_prunes_atomically(
    db_with_user,
):
    """A successful empty follow-up snapshot removes only covered Garmin rows."""
    from datetime import date, datetime, timedelta

    from api.plan_reconciliation import build_plan_reconciliation
    from api.routes.sync import _persist_garmin_calendar_snapshot
    from db.models import (
        PlanTargetCalendarSync,
        PlanTargetWorkout,
        TrainingPlan,
    )

    db, user_id = db_with_user
    today = date.today()
    window_start = today - timedelta(days=2)
    window_end = today + timedelta(days=31)
    observed_at = datetime(2026, 8, 2, 8, 0, 0)
    rows = [{
        "date": (today + timedelta(days=1)).isoformat(),
        "workout_type": "threshold",
        "planned_duration_min": "45.0",
        "workout_description": "Threshold",
        "external_id": "garmin-schedule-1",
        "provider_references": {"template_id": "garmin-template-1"},
        "provider_payload_fingerprint": "a" * 64,
        "provider_content_fingerprint": "b" * 64,
    }]

    created = _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:account",
        rows=rows,
        window_start=window_start,
        window_end=window_end,
        observed_at=observed_at,
    )
    db.commit()

    assert created > 0
    plan = db.query(TrainingPlan).filter_by(
        user_id=user_id,
        source="garmin",
    ).one()
    assert plan.external_id == "garmin-schedule-1"
    assert plan.workout_origin == "imported"
    calendar_sync = db.query(PlanTargetCalendarSync).filter_by(
        user_id=user_id,
        target="garmin",
    ).one()
    assert calendar_sync.provider_account_id == "international:account"
    observation = db.query(PlanTargetWorkout).filter_by(
        user_id=user_id,
        target="garmin",
    ).one()
    assert observation.present is True
    assert observation.provider_references == {
        "template_id": "garmin-template-1",
    }
    assert observation.payload_fingerprint == "a" * 64
    assert observation.content_fingerprint == "b" * 64
    reconciliation = build_plan_reconciliation(
        db,
        user_id=user_id,
        target="garmin",
        start=today,
        end=window_end,
    )
    assert reconciliation is not None
    assert len(reconciliation.target_only_items) == 1
    assert reconciliation.target_only_items[0].state == "target_only"
    assert (
        reconciliation.target_only_items[0].observation.external_id
        == "garmin-schedule-1"
    )

    ordinary_sync_rows = [dict(rows[0])]
    ordinary_sync_rows[0].pop("provider_content_fingerprint")
    refreshed = _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:account",
        rows=ordinary_sync_rows,
        window_start=window_start,
        window_end=window_end,
        observed_at=observed_at + timedelta(seconds=30),
    )
    db.commit()

    assert refreshed >= 0
    db.refresh(observation)
    assert observation.content_fingerprint == "b" * 64

    edited_rows = [dict(ordinary_sync_rows[0])]
    edited_rows[0]["provider_payload_fingerprint"] = "c" * 64
    _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:account",
        rows=edited_rows,
        window_start=window_start,
        window_end=window_end,
        observed_at=observed_at + timedelta(seconds=45),
    )
    db.commit()

    db.refresh(observation)
    assert observation.content_fingerprint is None

    removed = _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:account",
        rows=[],
        window_start=window_start,
        window_end=window_end,
        observed_at=observed_at + timedelta(minutes=1),
    )
    db.commit()

    assert removed > 0
    assert db.query(TrainingPlan).filter_by(
        user_id=user_id,
        source="garmin",
    ).count() == 0
    db.refresh(observation)
    assert observation.present is False


def test_garmin_account_change_retires_prior_account_observations(
    db_with_user,
):
    """Calendar ownership never transfers between authenticated accounts."""
    from datetime import date, datetime, timedelta

    from api.routes.sync import _persist_garmin_calendar_snapshot
    from db.models import PlanTargetCalendarSync, PlanTargetWorkout

    db, user_id = db_with_user
    today = date.today()
    window_end = today + timedelta(days=14)
    first_observed = datetime(2026, 8, 2, 8, 0, 0)
    _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:first-account",
        rows=[{
            "date": (today + timedelta(days=1)).isoformat(),
            "workout_type": "easy",
            "workout_description": "First account",
            "external_id": "7001",
            "provider_references": {"template_id": "9001"},
        }],
        window_start=today,
        window_end=window_end,
        observed_at=first_observed,
    )
    db.commit()

    _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:second-account",
        rows=[{
            "date": (today + timedelta(days=2)).isoformat(),
            "workout_type": "easy",
            "workout_description": "Second account",
            "external_id": "7002",
            "provider_references": {"template_id": "9002"},
        }],
        window_start=today,
        window_end=window_end,
        observed_at=first_observed + timedelta(minutes=1),
    )
    db.commit()

    observations = db.query(PlanTargetWorkout).filter_by(
        user_id=user_id,
        target="garmin",
    ).order_by(PlanTargetWorkout.external_id).all()
    assert [
        (
            row.external_id,
            row.provider_account_id,
            row.present,
            row.provider_references,
        )
        for row in observations
    ] == [
        (
            "7001",
            "international:first-account",
            False,
            {"template_id": "9001"},
        ),
        (
            "7002",
            "international:second-account",
            True,
            {"template_id": "9002"},
        ),
    ]
    calendar_sync = db.query(PlanTargetCalendarSync).filter_by(
        user_id=user_id,
        target="garmin",
    ).one()
    assert (
        calendar_sync.provider_account_id
        == "international:second-account"
    )


def test_sync_garmin_persists_calendar_through_authenticated_client(
    db_with_user,
    monkeypatch,
):
    """The production Garmin sync path writes a complete calendar snapshot."""
    from datetime import date, timedelta
    from types import SimpleNamespace

    from api.routes.sync import _sync_garmin
    from db.models import PlanTargetWorkout, TrainingPlan

    db, user_id = db_with_user
    workout_date = date.today() + timedelta(days=1)

    class FakeGarmin:
        display_name = "garmin-profile"

        def __init__(self, email, password, is_cn=False):
            self.client = SimpleNamespace()

        def login(self, token_dir):
            return None

        def get_scheduled_workouts(self, year, month):
            if (year, month) != (
                workout_date.year,
                workout_date.month,
            ):
                return {"calendarItems": []}
            return {
                "calendarItems": [{
                    "id": 7001,
                    "workoutId": 9001,
                    "itemType": "workout",
                    "date": workout_date.isoformat(),
                    "title": "Tomorrow's threshold",
                    "sportTypeKey": "running",
                    "duration": 2700,
                }]
            }

        def get_workout_by_id(self, workout_id):
            assert str(workout_id) == "9001"
            return {
                "workoutName": "Tomorrow's threshold",
                "description": "",
                "sportType": {"sportTypeKey": "running"},
                "estimatedDurationInSecs": 2700,
                "workoutSegments": [{
                    "segmentOrder": 1,
                    "sportType": {"sportTypeKey": "running"},
                    "workoutSteps": [{
                        "type": "ExecutableStepDTO",
                        "stepOrder": 1,
                        "stepType": {"stepTypeKey": "interval"},
                        "endCondition": {"conditionTypeKey": "time"},
                        "endConditionValue": 2700,
                        "targetType": {
                            "workoutTargetTypeKey": "no.target",
                        },
                    }],
                }],
            }

        def get_activities_by_date(self, *args, **kwargs):
            return []

        def get_lactate_threshold(self, **kwargs):
            return []

        def get_user_profile(self):
            return {}

        def get_heart_rates(self, activity_date):
            return {}

        def connectapi(self, path):
            if path == "/userprofile-service/socialProfile":
                return {"userProfileId": 12345}
            return {}

        def get_training_status(self, activity_date):
            return {}

        def get_training_readiness(self, activity_date):
            return None

        def get_race_predictions(self):
            return None

        def get_hrv_data(self, activity_date):
            return None

        def get_sleep_data(self, activity_date):
            return None

    monkeypatch.setattr("garminconnect.Garmin", FakeGarmin)
    monkeypatch.setattr("sync.garmin_sync.RATE_LIMIT_DELAY", 0)

    result = _sync_garmin(
        user_id,
        {"email": "runner@example.test", "password": "secret"},
        date.today().isoformat(),
        db,
    )
    db.commit()

    assert result["plan"] == 1
    plan = db.query(TrainingPlan).filter_by(
        user_id=user_id,
        source="garmin",
    ).one()
    assert plan.date == workout_date
    assert plan.external_id == "7001"
    observation = db.query(PlanTargetWorkout).filter_by(
        user_id=user_id,
        target="garmin",
    ).one()
    assert observation.external_id == "7001"
    assert observation.present is True
    from sync.garmin_sync import garmin_profile_account_id

    assert observation.provider_references["profile_account_id"] == (
        garmin_profile_account_id(
            user_id=user_id,
            is_cn=False,
            garmin_user_profile_id=12345,
        )
    )


def test_sync_garmin_calendar_rate_limit_happens_before_data_writes(
    db_with_user,
    monkeypatch,
):
    """Calendar backoff cannot roll back activity rows staged earlier."""
    from types import SimpleNamespace

    from garminconnect.exceptions import GarminConnectTooManyRequestsError

    from api.routes.sync import _sync_garmin
    from db.models import Activity

    db, user_id = db_with_user

    class RateLimitedGarmin:
        display_name = "garmin-profile"

        def __init__(self, email, password, is_cn=False):
            self.client = SimpleNamespace()

        def login(self, token_dir):
            return None

        def get_scheduled_workouts(self, year, month):
            raise GarminConnectTooManyRequestsError("rate limited")

        def connectapi(self, path):
            assert path == "/userprofile-service/socialProfile"
            return {"userProfileId": 12345}

        def get_activities_by_date(self, *args, **kwargs):
            raise AssertionError(
                "activity fetch must not start after calendar backoff"
            )

    monkeypatch.setattr("garminconnect.Garmin", RateLimitedGarmin)

    with pytest.raises(GarminConnectTooManyRequestsError):
        _sync_garmin(
            user_id,
            {"email": "runner@example.test", "password": "secret"},
            None,
            db,
        )

    assert db.query(Activity).filter_by(user_id=user_id).count() == 0


def test_sync_garmin_template_timeout_preserves_prior_snapshot(
    db_with_user,
    monkeypatch,
):
    """Partial template enrichment cannot replace complete calendar evidence."""
    from datetime import date, datetime, timedelta
    from types import SimpleNamespace

    from api.routes.sync import (
        _persist_garmin_calendar_snapshot,
        _sync_garmin,
    )
    from db.models import PlanTargetCalendarSync, PlanTargetWorkout

    db, user_id = db_with_user
    today = date.today()
    prior_observed_at = datetime(2026, 8, 1, 8, 0, 0)
    _persist_garmin_calendar_snapshot(
        db,
        user_id=user_id,
        provider_account_id="international:garmin-profile",
        rows=[{
            "date": (today + timedelta(days=1)).isoformat(),
            "workout_type": "easy",
            "workout_description": "Prior complete workout",
            "external_id": "existing-schedule",
            "provider_references": {
                "template_id": "existing-template",
                "profile_account_id": "profile-fence",
            },
            "provider_payload_fingerprint": "a" * 64,
            "provider_content_fingerprint": "b" * 64,
        }],
        window_start=today - timedelta(days=2),
        window_end=today + timedelta(days=31),
        observed_at=prior_observed_at,
    )
    db.commit()

    class TimeoutGarmin:
        display_name = "garmin-profile"

        def __init__(self, email, password, is_cn=False):
            self.client = SimpleNamespace()

        def login(self, token_dir):
            return None

        def get_scheduled_workouts(self, year, month):
            return {"calendarItems": []}

        def connectapi(self, path):
            if path == "/userprofile-service/socialProfile":
                return {"userProfileId": 12345}
            return {}

        def get_activities_by_date(self, *args, **kwargs):
            return []

        def get_lactate_threshold(self, **kwargs):
            return []

        def get_user_profile(self):
            return {}

        def get_heart_rates(self, activity_date):
            return {}

        def get_training_status(self, activity_date):
            return {}

        def get_training_readiness(self, activity_date):
            return None

        def get_race_predictions(self):
            return None

        def get_hrv_data(self, activity_date):
            return None

        def get_sleep_data(self, activity_date):
            return None

    monkeypatch.setattr("garminconnect.Garmin", TimeoutGarmin)
    monkeypatch.setattr(
        "sync.garmin_sync.fetch_training_plan_api",
        lambda *args, **kwargs: [{
            "date": (today + timedelta(days=2)).isoformat(),
            "external_id": "partial-schedule",
            "provider_references": {"template_id": "partial-template"},
        }],
    )

    def timeout_during_enrichment(*args, **kwargs):
        raise requests.Timeout("template response timed out")

    monkeypatch.setattr(
        "sync.garmin_sync.enrich_training_plan_content",
        timeout_during_enrichment,
    )
    monkeypatch.setattr("sync.garmin_sync.RATE_LIMIT_DELAY", 0)

    result = _sync_garmin(
        user_id,
        {"email": "runner@example.test", "password": "secret"},
        today.isoformat(),
        db,
    )
    db.commit()

    assert result["plan"] == 0
    assert db.query(PlanTargetWorkout).filter_by(
        user_id=user_id,
        target="garmin",
        external_id="existing-schedule",
        present=True,
    ).count() == 1
    assert db.query(PlanTargetWorkout).filter_by(
        user_id=user_id,
        target="garmin",
        external_id="partial-schedule",
    ).count() == 0
    calendar_sync = db.query(PlanTargetCalendarSync).filter_by(
        user_id=user_id,
        target="garmin",
    ).one()
    assert calendar_sync.synced_at == prior_observed_at
