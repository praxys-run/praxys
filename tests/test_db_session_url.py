"""URL resolution for the dual SQLite/PostgreSQL engine (#360).

Pure-function tests (no DB connection) covering the DATABASE_URL /
PRAXYS_DATABASE_URL resolution and psycopg-driver normalization added in
db/session.py.
"""
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
                )
            }
            tables = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        assert "today_decision_check_claimed_at" in columns_by_table["user_config"]
        assert "today_decision_check_shown_at" in columns_by_table["user_config"]
        assert "today_decision_check_submitted_at" in columns_by_table["user_config"]
        assert {
            "temperature_c",
            "relative_humidity_pct",
            "environment_source",
        } <= columns_by_table["activities"]
        assert "power_source" in columns_by_table["activity_splits"]
        assert "power_source" in columns_by_table["fitness_data"]
        assert "ai_insight_feedback" in tables
    finally:
        engine.dispose()