"""Unit and schema tests for the managed-plan revision/delivery ledger."""
from datetime import date


def test_workout_version_is_content_stable_and_meta_independent():
    from db.plan_ledger import workout_version

    base = {
        "date": date(2026, 8, 10),
        "source": "ai",
        "workout_type": "threshold",
        "planned_duration_min": 60,
        "workout_description": "2 x 20 minutes",
        "meta": {"uploaded_at": "2026-07-28T01:00:00"},
    }
    same_content = {
        **base,
        "meta": {"uploaded_at": "2026-07-28T02:00:00"},
    }
    changed = {
        **base,
        "workout_description": "3 x 15 minutes",
    }

    assert workout_version(base) == workout_version(same_content)
    assert workout_version(base) != workout_version(changed)


def test_sqlite_init_adds_ledger_tables_to_existing_database(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from db import session as db_session
    from db.models import TrainingPlan, User

    sqlite_path = tmp_path / "trainsight.db"
    legacy = create_engine(f"sqlite:///{sqlite_path}")
    User.__table__.create(legacy)
    TrainingPlan.__table__.create(legacy)
    legacy.dispose()

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    try:
        db_session.init_db()
        tables = set(inspect(db_session.engine).get_table_names())
        assert {
            "plan_revisions",
            "plan_deliveries",
            "plan_delivery_attempts",
        }.issubset(tables)
    finally:
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


def test_alembic_head_includes_plan_ledger():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "2b3c4d5e6f70"
