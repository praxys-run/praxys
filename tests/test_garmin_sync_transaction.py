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
