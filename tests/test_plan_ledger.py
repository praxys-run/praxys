"""Unit and schema tests for the managed-plan revision/delivery ledger."""
import copy
from datetime import date
import logging
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parent.parent


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


def test_backend_legal_contract_matches_the_canonical_web_bundle():
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION

    source = (ROOT / "web/src/lib/legal.ts").read_text(encoding="utf-8")
    version = re.search(
        r'export const TERMS_VERSION\s*=\s*"([^"]+)";',
        source,
    )
    digest = re.search(
        r'export const TERMS_CONTENT_DIGEST\s*=\s*"([^"]+)";',
        source,
    )

    assert version is not None
    assert digest is not None
    assert version.group(1) == TERMS_VERSION
    assert digest.group(1) == TERMS_CONTENT_DIGEST


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


def test_workout_version_tracks_activity_type_and_structure_without_rehashing_legacy_rows():
    from db.plan_ledger import workout_version

    legacy = {
        "date": date(2026, 8, 10),
        "source": "ai",
        "workout_type": "easy",
        "planned_duration_min": 45,
        "workout_description": "Aerobic run",
    }
    legacy_with_empty_structured_fields = {
        **legacy,
        "activity_type": None,
        "workout_structure_version": None,
        "workout_structure": None,
    }
    road = {
        **legacy,
        "activity_type": "running",
        "workout_structure_version": "v1",
        "workout_structure": {
            "steps": [
                {
                    "type": "step",
                    "phase": "other",
                    "termination": {"type": "time", "seconds": 2700},
                    "target": {
                        "metric": "none",
                        "unit": "none",
                        "reference": "none",
                    },
                }
            ]
        },
    }
    trail = {
        **road,
        "activity_type": "trail_running",
    }
    changed_structure = {
        **road,
        "workout_structure": {
            "steps": [
                {
                    "type": "step",
                    "phase": "warmup",
                    "termination": {"type": "time", "seconds": 600},
                    "target": {
                        "metric": "none",
                        "unit": "none",
                        "reference": "none",
                    },
                },
                {
                    "type": "step",
                    "phase": "work",
                    "termination": {"type": "time", "seconds": 2100},
                    "target": {
                        "metric": "none",
                        "unit": "none",
                        "reference": "none",
                    },
                },
                {
                    "type": "step",
                    "phase": "cooldown",
                    "termination": {"type": "time", "seconds": 300},
                    "target": {
                        "metric": "none",
                        "unit": "none",
                        "reference": "none",
                    },
                },
            ]
        },
    }

    assert workout_version(legacy) == workout_version(
        legacy_with_empty_structured_fields
    )
    assert workout_version(road) != workout_version(trail)
    assert workout_version(road) != workout_version(changed_structure)

    worded = {
        **road,
        "workout_structure": {
            "steps": [{
                "type": "repeat",
                "label": "Main set",
                "repetitions": 3,
                "steps": [{
                    "type": "step",
                    "phase": "work",
                    "label": "Threshold",
                    "instructions": "Stay smooth through the final minute.",
                    "termination": {"type": "time", "seconds": 300},
                    "target": {
                        "metric": "none",
                        "unit": "none",
                        "reference": "none",
                    },
                }],
            }],
        },
    }
    changed_step_label = copy.deepcopy(worded)
    changed_step_label["workout_structure"]["steps"][0]["steps"][0][
        "label"
    ] = "Threshold rep"
    changed_instructions = copy.deepcopy(worded)
    changed_instructions["workout_structure"]["steps"][0]["steps"][0][
        "instructions"
    ] = "Stay smooth and controlled through the final minute."
    changed_repeat_label = copy.deepcopy(worded)
    changed_repeat_label["workout_structure"]["steps"][0]["label"] = (
        "Primary set"
    )

    canonical_version = workout_version(worded)
    assert workout_version(changed_step_label) != canonical_version
    assert workout_version(changed_instructions) != canonical_version
    assert workout_version(changed_repeat_label) != canonical_version


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


def test_alembic_head_includes_adaptive_plan_proposals():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["e1f2a3b4c5d6"]
    assert script.get_revision("e1f2a3b4c5d6").down_revision == "d0e1f2a3b4c5"
    assert script.get_revision("d0e1f2a3b4c5").down_revision == "c9d0e1f2a3b4"
    assert script.get_revision("c9d0e1f2a3b4").down_revision == "b8d4e6f7a9c1"
    assert set(script.get_revision("b8d4e6f7a9c1").down_revision) == {
        "a7f3c2d1e9b4",
        "ae1f2a3b4c5d",
    }
    assert script.get_revision("9d0e1f2a3b4c").down_revision == "8c9d0e1f2a3b"
    assert script.get_revision("8c9d0e1f2a3b").down_revision == "f7b8c9d0e1f2"
    assert script.get_revision("e6a7b8c9d0f1").down_revision == "d95e6f7a8b9c"
    assert script.get_revision("d95e6f7a8b9c").down_revision == "c84f0912ab6d"


def test_terms_receipt_migration_refuses_destructive_downgrade(
    monkeypatch,
):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    from sqlalchemy import create_engine

    migration_path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "c9d0e1f2a3b4_add_terms_acceptance_receipts.py"
    )
    spec = importlib.util.spec_from_file_location(
        "terms_receipt_migration",
        migration_path,
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE terms_acceptance_receipts (id TEXT PRIMARY KEY)"
        )
        connection.exec_driver_sql(
            "INSERT INTO terms_acceptance_receipts (id) VALUES ('receipt-1')"
        )
        monkeypatch.setattr(
            migration,
            "op",
            SimpleNamespace(get_bind=lambda: connection),
        )
        with pytest.raises(RuntimeError, match="preserve the ledger"):
            migration.downgrade()


def test_road_10k_merge_secure_deletes_legacy_ids_before_rebuild(
    tmp_path,
    monkeypatch,
    preserve_logger_disabled_state,
):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import Engine

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from db import session as db_session

    db_session.dispose_engines()
    config = Config("alembic.ini")
    command.upgrade(config, "a7f3c2d1e9b4")
    migrated = create_engine(db_session.get_database_url())
    marker = "legacy-road-10k-raw-activity-id"

    def insert_legacy_marker(value: str) -> None:
        with migrated.begin() as conn:
            conn.exec_driver_sql(
                """
                INSERT INTO road_10k_plan_generations (
                    id, user_id, proposal_id, capability_id, policy_version,
                    generator_version, science_decision_id,
                    source_decision_digest, contract_digest,
                    baseline_snapshot_id, baseline_source, source_goal_id,
                    source_goal_revision, history_cutoff_completed_days,
                    history_observation_ids,
                    training_pattern_snapshot_version,
                    event_context_snapshot_version, active_zone_model_id,
                    active_zone_model_version, normalized_constraints,
                    selected_template_ids, source_revision,
                    deterministic_input_hash, request_kind,
                    request_fingerprint, predecessor_proposal_id,
                    predecessor_version, result_code,
                    validation_reason_code, created_at
                ) VALUES (
                    'legacy-road-10k-generation', 'migration-user',
                    'legacy-road-10k-proposal',
                    'outdoor_road_10k_performance_v1',
                    'road-10k-plan-generation-policy-v2',
                    'road-10k-deterministic-generator-v1',
                    'sdr-road-10k-plan-generation-policy-v2',
                    ?, ?, NULL, NULL, NULL, NULL, 56, ?,
                    'road-10k-training-pattern-v1',
                    'road-10k-event-context-v1', NULL, NULL, '{}', '[]',
                    ?, ?, 'generate', ?, NULL, NULL,
                    'eligible_rolling_proposal', NULL, CURRENT_TIMESTAMP
                )
                """,
                (
                    "a" * 64,
                    "b" * 64,
                    f'["{value}"]',
                    "c" * 64,
                    "d" * 64,
                    "e" * 64,
                ),
            )

    def upgrade_with_statement_capture() -> list[str]:
        statements: list[str] = []

        def capture(
            _conn,
            _cursor,
            statement,
            _parameters,
            _context,
            _executemany,
        ):
            normalized = " ".join(statement.split())
            upper = normalized.upper()
            if (
                "PRAGMA SECURE_DELETE" in upper
                or (
                    "ROAD_10K_PLAN_GENERATIONS" in upper
                    and "DROP TABLE" in upper
                )
            ):
                statements.append(normalized)

        event.listen(Engine, "before_cursor_execute", capture)
        try:
            command.upgrade(config, "head")
        finally:
            event.remove(Engine, "before_cursor_execute", capture)
        return statements

    database_path = migrated.url.database
    assert database_path is not None
    try:
        insert_legacy_marker(marker)
        with open(database_path, "rb") as database_file:
            assert marker.encode() in database_file.read()

        statements = upgrade_with_statement_capture()
        secure_delete_index = next(
            index
            for index, statement in enumerate(statements)
            if "PRAGMA SECURE_DELETE" in statement.upper()
        )
        destructive_drop_index = next(
            index
            for index, statement in enumerate(statements)
            if "DROP TABLE ROAD_10K_PLAN_GENERATIONS" in statement.upper()
        )
        assert secure_delete_index < destructive_drop_index

        with migrated.connect() as conn:
            columns = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("road_10k_plan_generations")'
                )
            }
            assert conn.exec_driver_sql(
                "SELECT version_num FROM alembic_version"
            ).scalar_one() == "e1f2a3b4c5d6"
        assert "history_observation_ids" not in columns
        with open(database_path, "rb") as database_file:
            assert marker.encode() not in database_file.read()

        command.downgrade(config, "a7f3c2d1e9b4")
        with migrated.begin() as conn:
            conn.exec_driver_sql(
                """
                UPDATE road_10k_plan_generations
                SET history_observation_ids = ?
                WHERE id = 'legacy-road-10k-generation'
                """,
                (f'["{marker}"]',),
            )
        with open(database_path, "rb") as database_file:
            assert marker.encode() in database_file.read()

        statements = upgrade_with_statement_capture()
        secure_delete_index = next(
            index
            for index, statement in enumerate(statements)
            if "PRAGMA SECURE_DELETE" in statement.upper()
        )
        destructive_drop_index = next(
            index
            for index, statement in enumerate(statements)
            if "DROP TABLE ROAD_10K_PLAN_GENERATIONS" in statement.upper()
        )
        assert secure_delete_index < destructive_drop_index
        with open(database_path, "rb") as database_file:
            assert marker.encode() not in database_file.read()
    finally:
        migrated.dispose()
        db_session.dispose_engines()


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
