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
    assert script.get_current_head() == "3c4d5e6f7081"


def test_sqlite_init_backfills_delivery_identity_columns(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    sqlite_path = tmp_path / "trainsight.db"
    legacy = create_engine(f"sqlite:///{sqlite_path}")
    with legacy.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE plan_deliveries (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                canonical_key VARCHAR(120) NOT NULL,
                workout_date DATE NOT NULL,
                workout_version VARCHAR(64) NOT NULL,
                target VARCHAR(20) NOT NULL,
                state VARCHAR(20) NOT NULL,
                external_id VARCHAR(200),
                last_error TEXT,
                delivered_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO plan_deliveries (
                id, user_id, canonical_key, workout_date, workout_version,
                target, state, created_at, updated_at
            ) VALUES (
                'legacy-delivery', 'legacy-user', 'ai:2026-08-04',
                '2026-08-04', 'legacy-version', 'stryd', 'pending',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        )
    legacy.dispose()

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    try:
        db_session.init_db()
        columns = {
            column["name"]
            for column in inspect(db_session.engine).get_columns(
                "plan_deliveries"
            )
        }
        assert {"plan_version", "provider_account_id"}.issubset(columns)
        with db_session.engine.connect() as conn:
            plan_version = conn.execute(
                text(
                    "SELECT plan_version FROM plan_deliveries "
                    "WHERE id = 'legacy-delivery'"
                )
            ).scalar_one()
        assert plan_version == "legacy-version"
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
