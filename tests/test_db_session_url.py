"""URL resolution for the dual SQLite/PostgreSQL engine (#360).

Pure-function tests (no DB connection) covering the DATABASE_URL /
PRAXYS_DATABASE_URL resolution and psycopg-driver normalization added in
db/session.py.
"""
from datetime import datetime

import pytest


@pytest.fixture
def dbs(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from db import session as s
    return s


def test_default_is_sqlite_under_data_dir(dbs):
    url = dbs.get_database_url()
    assert url.startswith("sqlite:///")
    assert "trainsight.db" in url
    assert dbs.get_async_database_url().startswith("sqlite+aiosqlite:///")
    assert dbs.is_postgres() is False


def test_postgres_scheme_normalized_to_psycopg(dbs, monkeypatch):
    monkeypatch.setenv("PRAXYS_DATABASE_URL", "postgres://u:p@host:5432/db")
    assert dbs.get_database_url() == "postgresql+psycopg://u:p@host:5432/db"
    # Async reuses the same psycopg driver.
    assert dbs.get_async_database_url() == "postgresql+psycopg://u:p@host:5432/db"
    assert dbs.is_postgres() is True


def test_postgresql_scheme_normalized(dbs, monkeypatch):
    monkeypatch.setenv("PRAXYS_DATABASE_URL", "postgresql://u:p@host/db")
    assert dbs.get_database_url() == "postgresql+psycopg://u:p@host/db"


def test_explicit_driver_preserved(dbs, monkeypatch):
    monkeypatch.setenv("PRAXYS_DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    assert dbs.get_database_url() == "postgresql+asyncpg://u:p@host/db"


def test_database_url_fallback_var(dbs, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert dbs.get_database_url() == "postgresql+psycopg://u:p@host/db"


def test_praxys_url_takes_precedence(dbs, monkeypatch):
    monkeypatch.setenv("PRAXYS_DATABASE_URL", "postgresql://a/db1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://b/db2")
    assert "db1" in dbs.get_database_url()


def test_blank_url_falls_back_to_sqlite(dbs, monkeypatch):
    monkeypatch.setenv("PRAXYS_DATABASE_URL", "   ")
    assert dbs.get_database_url().startswith("sqlite:///")


def test_existing_sqlite_gets_additive_compatibility_columns(dbs, tmp_path):
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE user_config (user_id VARCHAR(36) PRIMARY KEY)"
            )
            conn.exec_driver_sql("CREATE TABLE activities (id INTEGER PRIMARY KEY)")
            conn.exec_driver_sql(
                "CREATE TABLE activity_splits (id INTEGER PRIMARY KEY)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE fitness_data (id INTEGER PRIMARY KEY)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE user_connections (id INTEGER PRIMARY KEY)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE personal_context_items "
                "(id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36))"
            )
            conn.exec_driver_sql(
                "CREATE TABLE personal_context_consent_receipts "
                "(id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36))"
            )

        dbs._ensure_schema(engine, "sqlite")

        with engine.connect() as conn:
            columns_by_table = {
                table: {
                    row[1]
                    for row in conn.exec_driver_sql(
                        f'PRAGMA table_info("{table}")'
                    )
                }
                for table in (
                    "user_config",
                    "activities",
                    "activity_splits",
                    "fitness_data",
                    "user_connections",
                    "personal_context_items",
                    "personal_context_consent_receipts",
                )
            }
            tables = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            context_indexes = {
                row[1]
                for table in (
                    "personal_context_items",
                    "personal_context_consent_receipts",
                )
                for row in conn.exec_driver_sql(
                    f'PRAGMA index_list("{table}")'
                )
            }
        assert "today_decision_check_claimed_at" in columns_by_table["user_config"]
        assert "today_decision_check_shown_at" in columns_by_table["user_config"]
        assert "today_decision_check_submitted_at" in columns_by_table["user_config"]
        assert "plan_management" in columns_by_table["user_config"]
        assert {
            "temperature_c",
            "relative_humidity_pct",
            "environment_source",
        } <= columns_by_table["activities"]
        assert "power_source" in columns_by_table["activity_splits"]
        assert "power_source" in columns_by_table["fitness_data"]
        assert {
            "encrypted_garmin_tokens",
            "wrapped_token_dek",
            "garmin_token_generation",
            "tokens_updated_at",
        } <= columns_by_table["user_connections"]
        assert "idempotency_key" in columns_by_table[
            "personal_context_items"
        ]
        assert "idempotency_key" in columns_by_table[
            "personal_context_consent_receipts"
        ]
        assert {
            "uq_personal_context_item_idempotency",
            "uq_personal_context_consent_idempotency",
        } <= context_indexes
        assert "personal_context_commands" in tables
        assert "ai_insight_feedback" in tables
    finally:
        engine.dispose()


def test_existing_sqlite_plan_proposals_get_idempotency_fingerprint(
    dbs,
    tmp_path,
):
    """A pre-5K proposal table remains ORM-readable and writable after boot."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from db.models import PlanProposal

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-proposals.db'}")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE plan_proposals (
                    id VARCHAR(36) PRIMARY KEY NOT NULL,
                    user_id VARCHAR(36) NOT NULL,
                    adaptive_plan_id VARCHAR(36) NOT NULL,
                    goal_snapshot_id VARCHAR(36) NOT NULL,
                    discipline VARCHAR(30) NOT NULL,
                    version INTEGER NOT NULL,
                    state VARCHAR(20) NOT NULL,
                    origin VARCHAR(80) NOT NULL,
                    actor_type VARCHAR(20) NOT NULL,
                    actor_id VARCHAR(100),
                    base_plan_version INTEGER NOT NULL,
                    supersedes_proposal_id VARCHAR(36),
                    policy_version VARCHAR(80),
                    model_version VARCHAR(80),
                    science_version VARCHAR(80),
                    assumptions JSON NOT NULL,
                    unknowns JSON NOT NULL,
                    warnings JSON NOT NULL,
                    alternatives JSON NOT NULL,
                    expires_at DATETIME,
                    idempotency_key VARCHAR(128),
                    decision_idempotency_key VARCHAR(128),
                    workout_snapshot JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    decided_at DATETIME
                )
                """
            )

        dbs._ensure_schema(engine, "sqlite")
        with engine.connect() as conn:
            columns = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("plan_proposals")'
                )
            }
        assert "idempotency_fingerprint" in columns

        session = sessionmaker(bind=engine)()
        try:
            session.add(
                PlanProposal(
                    id="legacy-proposal",
                    user_id="legacy-owner",
                    adaptive_plan_id="legacy-plan",
                    goal_snapshot_id="legacy-goal",
                    discipline="running",
                    version=1,
                    state="draft",
                    origin="test.legacy",
                    actor_type="system",
                    base_plan_version=0,
                    assumptions=[],
                    unknowns=[],
                    warnings=[],
                    alternatives=[],
                    idempotency_key="legacy-key",
                    idempotency_fingerprint="a" * 64,
                    workout_snapshot=[],
                    created_at=datetime(2026, 8, 13),
                )
            )
            session.commit()
            session.expire_all()
            proposal = session.get(PlanProposal, "legacy-proposal")
            assert proposal is not None
            assert proposal.idempotency_fingerprint == "a" * 64
        finally:
            session.close()
    finally:
        engine.dispose()