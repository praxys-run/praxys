"""Unit and schema tests for the managed-plan revision/delivery ledger."""
from datetime import date
import logging

import pytest


@pytest.fixture
def preserve_logger_disabled_state():
    """Restore loggers disabled by Alembic's in-process logging setup."""
    states = {
        name: logger.disabled
        for name, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }
    yield
    for name, disabled in states.items():
        logger = logging.root.manager.loggerDict.get(name)
        if isinstance(logger, logging.Logger):
            logger.disabled = disabled


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
        "source": "praxys",
        "workout_origin": "manual",
    }
    changed = {
        **base,
        "workout_description": "3 x 15 minutes",
    }

    assert workout_version(base) == workout_version(same_content)
    assert workout_version(base) != workout_version(changed)


def test_canonical_identity_is_stable_but_not_part_of_content_version():
    from db.plan_ledger import canonical_workout_key, workout_version

    first = {
        "canonical_id": "11111111-1111-1111-1111-111111111111",
        "date": date(2026, 8, 10),
        "source": "ai",
        "workout_type": "easy",
    }
    second = {
        **first,
        "canonical_id": "22222222-2222-2222-2222-222222222222",
    }

    assert workout_version(first) == workout_version(second)
    assert canonical_workout_key(first) != canonical_workout_key(second)
    assert canonical_workout_key(first) == canonical_workout_key({
        **first,
        "source": "praxys",
    })


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
            "plan_target_calendar_syncs",
            "plan_target_workouts",
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
    assert script.get_current_head() == "7a8192b3c4d5"


def test_alembic_canonical_default_supports_old_worker_inserts(
    tmp_path,
    monkeypatch,
    preserve_logger_disabled_state,
):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from db import session as db_session

    db_session.dispose_engines()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    migrated = create_engine(db_session.get_database_url())
    try:
        with migrated.begin() as conn:
            conn.exec_driver_sql(
                """
                INSERT INTO users (
                    id, email, hashed_password, is_active, is_superuser,
                    is_verified, is_demo
                ) VALUES (
                    'rolling-user', 'rolling@example.com', 'hash',
                    1, 0, 0, 0
                )
                """
            )
            for description in ("Morning", "Evening"):
                conn.exec_driver_sql(
                    """
                    INSERT INTO training_plans (
                        user_id, date, workout_type, workout_description, source
                    ) VALUES (
                        'rolling-user', '2026-08-04', 'easy', ?, 'ai'
                    )
                    """,
                    (description,),
                )
            canonical_ids = conn.exec_driver_sql(
                """
                SELECT canonical_id
                FROM training_plans
                WHERE user_id = 'rolling-user'
                ORDER BY id
                """
            ).scalars().all()
            origins = conn.exec_driver_sql(
                """
                SELECT workout_origin
                FROM training_plans
                WHERE user_id = 'rolling-user'
                ORDER BY id
                """
            ).scalars().all()
            conn.exec_driver_sql(
                """
                INSERT INTO plan_deliveries (
                    id, user_id, canonical_key, workout_date,
                    workout_version, target, state, created_at, updated_at
                ) VALUES (
                    'old-worker-delivery', 'rolling-user', ?,
                    '2026-08-04', ?, 'stryd', 'pending',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """,
                (f"ai:{canonical_ids[0]}", "a" * 64),
            )
            conn.exec_driver_sql(
                """
                INSERT INTO plan_target_calendar_syncs (
                    user_id, target, provider_account_id, window_start,
                    window_end, synced_at
                ) VALUES (
                    'rolling-user', 'stryd', 'account', '2026-08-01',
                    '2026-08-31', CURRENT_TIMESTAMP
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO plan_target_workouts (
                    id, user_id, target, provider_account_id, external_id,
                    workout_date, normalized_workout, present, observed_at
                ) VALUES (
                    'old-worker-observation', 'rolling-user', 'stryd',
                    'account', 'external', '2026-08-04', '{}', 1,
                    CURRENT_TIMESTAMP
                )
                """
            )
            provider_references = conn.exec_driver_sql(
                """
                SELECT provider_references
                FROM plan_deliveries
                WHERE id = 'old-worker-delivery'
                UNION ALL
                SELECT provider_references
                FROM plan_target_workouts
                WHERE id = 'old-worker-observation'
                UNION ALL
                SELECT provider_references
                FROM plan_target_calendar_syncs
                WHERE user_id = 'rolling-user' AND target = 'stryd'
                """
            ).scalars().all()
        assert len(canonical_ids) == 2
        assert len(set(canonical_ids)) == 2
        assert all(len(canonical_id) == 36 for canonical_id in canonical_ids)
        assert origins == ["legacy", "legacy"]
        assert provider_references == ["{}", "{}", "{}"]
        migrated.dispose()
        with pytest.raises(
            RuntimeError,
            match="Cannot downgrade plan reconciliation",
        ):
            command.downgrade(config, "3c4d5e6f7081")
        verification = create_engine(db_session.get_database_url())
        try:
            with verification.connect() as conn:
                assert conn.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one() == "4d5e6f708192"
                assert conn.exec_driver_sql(
                    "SELECT COUNT(*) FROM plan_target_workouts"
                ).scalar_one() == 1
        finally:
            verification.dispose()
    finally:
        migrated.dispose()
        db_session.dispose_engines()


def test_alembic_migrates_plan_ownership_origin_and_delivery_uuid(
    tmp_path,
    monkeypatch,
    preserve_logger_disabled_state,
):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from db import session as db_session

    db_session.dispose_engines()
    config = Config("alembic.ini")
    command.upgrade(config, "4d5e6f708192")
    migrated = create_engine(db_session.get_database_url())
    canonical_id = "11111111-1111-1111-1111-111111111111"
    accepted_id = "22222222-2222-2222-2222-222222222222"
    try:
        with migrated.begin() as conn:
            conn.exec_driver_sql(
                """
                INSERT INTO users (
                    id, email, hashed_password, is_active, is_superuser,
                    is_verified, is_demo
                ) VALUES (
                    'migration-user', 'migration@example.com', 'hash',
                    1, 0, 0, 0
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO training_plans (
                    user_id, canonical_id, date, workout_type, source, meta
                ) VALUES
                    (
                        'migration-user', ?, '2026-08-04', 'easy', 'ai',
                        '{"generated_at":"2026-07-30"}'
                    ),
                    (
                        'migration-user', ?, '2026-08-05', 'tempo', 'ai',
                        '{"accepted_from_target":{"target":"stryd"}}'
                    ),
                    (
                        'migration-user',
                        '33333333-3333-3333-3333-333333333333',
                        '2026-08-06', 'long_run', 'stryd', '{}'
                    )
                """,
                (canonical_id, accepted_id),
            )
            conn.exec_driver_sql(
                """
                INSERT INTO plan_deliveries (
                    id, user_id, canonical_key, workout_date,
                    workout_version, plan_version, target, state,
                    created_at, updated_at
                ) VALUES (
                    'migration-delivery', 'migration-user', ?,
                    '2026-08-04', ?, ?, 'stryd', 'synced',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """,
                (
                    f"praxys:{canonical_id}",
                    "a" * 64,
                    "b" * 64,
                ),
            )

        command.upgrade(config, "head")
        with migrated.connect() as conn:
            plan_rows = conn.exec_driver_sql(
                """
                SELECT canonical_id, source, workout_origin
                FROM training_plans
                WHERE user_id = 'migration-user'
                ORDER BY date
                """
            ).all()
            delivery = conn.exec_driver_sql(
                """
                SELECT canonical_id, canonical_key, provider_references
                FROM plan_deliveries
                WHERE id = 'migration-delivery'
                """
            ).one()

        assert plan_rows == [
            (canonical_id, "ai", "legacy"),
            (accepted_id, "ai", "accepted_target"),
            (
                "33333333-3333-3333-3333-333333333333",
                "stryd",
                "imported",
            ),
        ]
        assert delivery == (canonical_id, f"ai:{canonical_id}", "{}")

        command.downgrade(config, "4d5e6f708192")
        with migrated.connect() as conn:
            plan_columns = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("training_plans")'
                )
            }
            delivery_columns = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("plan_deliveries")'
                )
            }
            sources = conn.exec_driver_sql(
                """
                SELECT source
                FROM training_plans
                WHERE user_id = 'migration-user'
                ORDER BY date
                """
            ).scalars().all()
        assert "workout_origin" not in plan_columns
        assert "canonical_id" not in delivery_columns
        assert sources == ["ai", "ai", "stryd"]
    finally:
        migrated.dispose()
        db_session.dispose_engines()


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
        assert {
            "canonical_id",
            "plan_version",
            "provider_content_version",
            "provider_account_id",
        }.issubset(columns)
        with db_session.engine.connect() as conn:
            plan_version, canonical_id = conn.execute(
                text(
                    "SELECT plan_version, canonical_id FROM plan_deliveries "
                    "WHERE id = 'legacy-delivery'"
                )
            ).one()
        assert plan_version == "legacy-version"
        assert canonical_id is None
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


def test_sqlite_init_migrates_training_plan_identity_constraint(
    tmp_path,
    monkeypatch,
):
    from sqlalchemy import create_engine, inspect

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    sqlite_path = tmp_path / "trainsight.db"
    legacy = create_engine(f"sqlite:///{sqlite_path}")
    with legacy.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE training_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR(36) NOT NULL,
                date DATE NOT NULL,
                workout_type VARCHAR(50),
                source VARCHAR(20),
                CONSTRAINT uq_user_date_plan
                    UNIQUE (user_id, date, source, workout_type)
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO training_plans (
                user_id, date, workout_type, source
            ) VALUES
                ('legacy-user', '2026-08-04', 'easy', 'ai'),
                ('legacy-user', '2026-08-05', 'long_run', 'stryd')
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
        constraints = inspect(
            db_session.engine
        ).get_unique_constraints("training_plans")
        assert all(
            item["column_names"]
            != ["user_id", "date", "source", "workout_type"]
            for item in constraints
        )
        assert any(
            item["column_names"] == ["user_id", "canonical_id"]
            for item in constraints
        )
        with db_session.engine.begin() as conn:
            canonical_id, source, origin = conn.exec_driver_sql(
                """
                SELECT canonical_id, source, workout_origin
                FROM training_plans
                WHERE id = 1
                """
            ).one()
            assert canonical_id
            assert source == "praxys"
            assert origin == "legacy"
            external_source, external_origin = conn.exec_driver_sql(
                """
                SELECT source, workout_origin
                FROM training_plans
                WHERE id = 2
                """
            ).one()
            assert external_source == "stryd"
            assert external_origin == "imported"
            conn.exec_driver_sql(
                """
                INSERT INTO training_plans (
                    user_id, canonical_id, date, workout_type, source
                ) VALUES (
                    'legacy-user',
                    '22222222-2222-2222-2222-222222222222',
                    '2026-08-04',
                    'easy',
                    'ai'
                )
                """
            )
        db_session._normalize_praxys_plan_sources(db_session.engine)
        db_session._normalize_praxys_plan_sources(db_session.engine)
        with db_session.engine.connect() as conn:
            assert conn.exec_driver_sql(
                """
                SELECT source
                FROM training_plans
                WHERE canonical_id =
                    '22222222-2222-2222-2222-222222222222'
                """
            ).scalar_one() == "praxys"
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
