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


def test_existing_sqlite_feedback_gets_publication_compatibility(dbs, tmp_path):
    """Legacy feedback stays readable and gains the exact public-state index."""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-feedback.db'}")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE feedback ("
                "id INTEGER PRIMARY KEY, message TEXT NOT NULL)"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback (id, message) VALUES (1, 'private')"
            )

        # Startup schema compatibility must be repeatable, including indexes.
        dbs._ensure_schema(engine, "sqlite")
        dbs._ensure_schema(engine, "sqlite")

        with engine.connect() as conn:
            columns = {
                row[1]: {
                    "type": row[2],
                    "not_null": row[3],
                    "default": row[4],
                }
                for row in conn.exec_driver_sql('PRAGMA table_info("feedback")')
            }
            indexes = [
                row
                for row in conn.exec_driver_sql('PRAGMA index_list("feedback")')
                if row[1] == "ix_feedback_publication_status"
            ]
            publication_status = conn.exec_driver_sql(
                "SELECT publication_status FROM feedback WHERE id = 1"
            ).scalar_one()

        assert columns["publication_consent_version"]["type"] == "VARCHAR(64)"
        assert columns["publication_consented_at"]["type"] == "DATETIME"
        assert columns["publication_status"] == {
            "type": "VARCHAR(24)",
            "not_null": 1,
            "default": "'private'",
        }
        assert publication_status == "private"
        assert len(indexes) == 1
        assert indexes[0][2] == 0  # non-unique
    finally:
        engine.dispose()


def test_existing_sqlite_backfills_only_already_public_legacy_feedback(
    dbs,
    tmp_path,
):
    """Legacy issue locators survive; a v1 grant alone never becomes queued."""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-publication.db'}")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE feedback ("
                "id INTEGER PRIMARY KEY, message TEXT NOT NULL, "
                "status VARCHAR(20) NOT NULL, "
                "publication_consent_version VARCHAR(64), "
                "publication_consented_at DATETIME, "
                "github_issue_number INTEGER, github_issue_url VARCHAR(500), "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback VALUES ("
                "1, 'already public', 'issue_created', "
                "'feedback-publication-v1', '2026-01-01 00:00:00', 42, "
                "'https://github.com/legacy-owner/legacy-repo/issues/42', "
                "'2026-01-01 00:00:00', '2026-01-02 00:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback VALUES ("
                "2, 'never public', 'needs_review', "
                "'feedback-publication-v1', '2026-01-01 00:00:00', NULL, "
                "NULL, '2026-01-01 00:00:00', '2026-01-02 00:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback VALUES ("
                "3, 'public with unsafe URL', 'rejected', NULL, NULL, 77, "
                "'https://untrusted.invalid/issues/77', "
                "'2026-01-01 00:00:00', '2026-01-02 00:00:00')"
            )

        dbs._ensure_schema(engine, "sqlite")
        dbs._ensure_schema(engine, "sqlite")

        with engine.connect() as conn:
            feedback = conn.exec_driver_sql(
                "SELECT id, publication_status, "
                "publication_consent_version, image_storage_provenance "
                "FROM feedback ORDER BY id"
            ).all()
            outboxes = conn.exec_driver_sql(
                "SELECT feedback_id, marker_version, target_repo, "
                "consent_version, payload_sha256, public_content_sha256, "
                "state, delivery_evidence, github_issue_number, "
                "github_issue_url FROM feedback_publication_outbox "
                "ORDER BY feedback_id"
            ).all()
            attempts = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM feedback_publication_attempts"
            ).scalar_one()

        assert feedback == [
            (1, "published", "feedback-publication-v1", None),
            (2, "private", "feedback-publication-v1", None),
            (3, "published", None, None),
        ]
        assert outboxes == [
            (
                1,
                "legacy",
                "legacy-owner/legacy-repo",
                None,
                None,
                None,
                "published",
                "published",
                42,
                "https://github.com/legacy-owner/legacy-repo/issues/42",
            ),
            (
                3,
                "legacy",
                "legacy-unresolved/3",
                None,
                None,
                None,
                "published",
                "published",
                77,
                "https://untrusted.invalid/issues/77",
            ),
        ]
        assert attempts == 0
    finally:
        engine.dispose()


def test_existing_sqlite_old_f2_shape_is_rebuilt_without_losing_evidence(
    dbs,
    tmp_path,
):
    """An unshipped old-f2 local DB upgrades without synthetic legacy grants."""
    from uuid import NAMESPACE_URL, uuid5

    from sqlalchemy import create_engine, event, inspect

    engine = create_engine(f"sqlite:///{tmp_path / 'old-f2.db'}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE feedback ("
                "id INTEGER PRIMARY KEY, message TEXT NOT NULL, "
                "status VARCHAR(20) NOT NULL, github_issue_number INTEGER, "
                "github_issue_url VARCHAR(500), created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL, "
                "publication_status VARCHAR(24) NOT NULL DEFAULT 'private')"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback VALUES ("
                "1, 'legacy linked', 'issue_created', 42, "
                "'https://github.com/legacy-owner/legacy-repo/issues/42', "
                "'2026-01-01 00:00:00', '2026-01-02 00:00:00', 'private')"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback VALUES ("
                "2, 'old f2 unknown', 'needs_review', NULL, NULL, "
                "'2026-01-01 00:00:00', '2026-01-02 00:00:00', 'unknown')"
            )
            conn.exec_driver_sql(
                "CREATE TABLE feedback_publication_outbox ("
                "id VARCHAR(36) PRIMARY KEY NOT NULL, "
                "feedback_id INTEGER UNIQUE, public_id VARCHAR(36) NOT NULL UNIQUE, "
                "marker_version VARCHAR(12) NOT NULL, "
                "target_repo VARCHAR(200) NOT NULL, "
                "consent_version VARCHAR(64) NOT NULL, "
                "consented_at DATETIME NOT NULL, "
                "payload_sha256 VARCHAR(71) NOT NULL, "
                "state VARCHAR(24) NOT NULL, attempt_count INTEGER NOT NULL, "
                "reconcile_count INTEGER NOT NULL, available_at DATETIME NOT NULL, "
                "lease_token VARCHAR(36), lease_expires_at DATETIME, "
                "github_issue_number INTEGER, github_issue_url VARCHAR(500), "
                "last_error_code VARCHAR(80), created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL, published_at DATETIME, "
                "CONSTRAINT ck_feedback_publication_outbox_digest "
                "CHECK (payload_sha256 LIKE 'sha256:%'), "
                "CONSTRAINT ck_feedback_publication_outbox_state CHECK ("
                "state IN ('pending','sending','retry_wait','reconciling',"
                "'published','manual_review','held','cancelled')), "
                "CONSTRAINT uq_feedback_publication_repo_issue UNIQUE ("
                "target_repo, github_issue_number), "
                "FOREIGN KEY(feedback_id) REFERENCES feedback(id) ON DELETE SET NULL)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX ix_feedback_publication_claim ON "
                "feedback_publication_outbox (state, available_at)"
            )
            conn.exec_driver_sql(
                "CREATE TRIGGER "
                "trg_feedback_publication_outbox_binding_immutable "
                "BEFORE UPDATE OF public_id ON feedback_publication_outbox "
                "BEGIN SELECT RAISE(ABORT, 'old outbox immutable'); END"
            )
            conn.exec_driver_sql(
                "CREATE TABLE feedback_publication_attempts ("
                "id VARCHAR(36) PRIMARY KEY NOT NULL, outbox_id VARCHAR(36) NOT NULL, "
                "attempt_no INTEGER NOT NULL, lease_token VARCHAR(36) NOT NULL, "
                "target_repo VARCHAR(200) NOT NULL, "
                "payload_sha256 VARCHAR(71) NOT NULL, started_at DATETIME NOT NULL, "
                "finished_at DATETIME, outcome VARCHAR(20) NOT NULL, "
                "http_status INTEGER, error_code VARCHAR(80), "
                "UNIQUE(outbox_id, attempt_no), FOREIGN KEY(outbox_id) "
                "REFERENCES feedback_publication_outbox(id) ON DELETE RESTRICT)"
            )
            conn.exec_driver_sql(
                "CREATE TRIGGER "
                "trg_feedback_publication_attempt_binding_immutable "
                "BEFORE UPDATE OF outbox_id ON feedback_publication_attempts "
                "BEGIN SELECT RAISE(ABORT, 'old attempt immutable'); END"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback_publication_outbox VALUES ("
                "'old-outbox', 2, '22222222222222222222222222222222', 'v1', "
                "'praxys-run/praxys', 'feedback-publication-v2-public-github', "
                "'2026-01-01 00:00:00', 'sha256:" + "2" * 64 + "', "
                "'reconciling', 1, 1, '2026-01-02 00:00:00', NULL, NULL, "
                "NULL, NULL, 'network_unknown', '2026-01-01 00:00:00', "
                "'2026-01-02 00:00:00', NULL)"
            )
            conn.exec_driver_sql(
                "INSERT INTO feedback_publication_attempts VALUES ("
                "'old-attempt', 'old-outbox', 1, 'old-lease', "
                "'praxys-run/praxys', 'sha256:" + "2" * 64 + "', "
                "'2026-01-01 00:00:00', '2026-01-02 00:00:00', "
                "'unknown', NULL, 'network_unknown')"
            )

        dbs._ensure_schema(engine, "sqlite")
        dbs._ensure_schema(engine, "sqlite")

        columns = {
            column["name"]: column for column in inspect(engine).get_columns(
                "feedback_publication_outbox"
            )
        }
        with engine.connect() as conn:
            outboxes = conn.exec_driver_sql(
                "SELECT id, feedback_id, marker_version, consent_version, "
                "payload_sha256, public_content_sha256, state, "
                "delivery_evidence, github_issue_number FROM "
                "feedback_publication_outbox ORDER BY feedback_id"
            ).all()
            attempts = conn.exec_driver_sql(
                "SELECT id, outbox_id, outcome, error_code FROM "
                "feedback_publication_attempts"
            ).all()
            foreign_key_violations = conn.exec_driver_sql(
                "PRAGMA foreign_key_check"
            ).all()
            trigger_names = {
                row[0]
                for row in conn.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND name LIKE 'trg_feedback_publication_%'"
                )
            }
            index_names = {
                row[1]
                for row in conn.exec_driver_sql(
                    "PRAGMA index_list('feedback_publication_outbox')"
                )
            }

        assert columns["consent_version"]["nullable"] is True
        assert columns["consented_at"]["nullable"] is True
        assert columns["payload_sha256"]["nullable"] is True
        legacy_id = str(
            uuid5(
                NAMESPACE_URL,
                "praxys-feedback-legacy-outbox:feedback:1:"
                "repo:legacy-owner/legacy-repo:issue:42",
            )
        )
        assert outboxes == [
            (
                legacy_id,
                1,
                "legacy",
                None,
                None,
                None,
                "published",
                "published",
                42,
            ),
            (
                "old-outbox",
                2,
                "v1",
                "feedback-publication-v2-public-github",
                "sha256:" + "2" * 64,
                None,
                "manual_review",
                "ambiguous",
                None,
            ),
        ]
        assert attempts == [
            ("old-attempt", "old-outbox", "unknown", "network_unknown")
        ]
        assert foreign_key_violations == []
        assert {
            "trg_feedback_publication_outbox_binding_immutable",
            "trg_feedback_publication_evidence_published_terminal",
            "trg_feedback_publication_attempt_binding_immutable",
        } <= trigger_names
        assert {
            "ix_feedback_publication_claim",
            "uq_feedback_publication_repo_issue_current",
        } <= index_names
        assert "uq_feedback_publication_repo_issue" not in {
            constraint.get("name")
            for constraint in inspect(engine).get_unique_constraints(
                "feedback_publication_outbox"
            )
        }
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


def test_existing_sqlite_goal_snapshots_get_purpose_provenance(
    dbs,
    tmp_path,
):
    """A pre-purpose goal snapshot table receives additive provenance."""
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-goals.db'}")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE adaptive_plan_goal_snapshots "
                "(id VARCHAR(36) PRIMARY KEY NOT NULL)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE goal_baseline_test_records "
                "(id VARCHAR(36) PRIMARY KEY NOT NULL)"
            )

        dbs._ensure_schema(engine, "sqlite")
        with engine.connect() as conn:
            goal_snapshot_columns = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("adaptive_plan_goal_snapshots")'
                )
            }
            baseline_test_columns = {
                row[1]
                for row in conn.exec_driver_sql(
                    'PRAGMA table_info("goal_baseline_test_records")'
                )
            }
        assert {
            "purpose_source",
            "source_goal_id",
            "source_goal_revision",
        } <= goal_snapshot_columns
        assert {
            "purpose_source",
            "source_goal_id",
            "source_goal_revision",
        } <= baseline_test_columns
    finally:
        engine.dispose()


def test_postgres_alembic_migration_lock_serializes_and_releases(
    dbs,
    monkeypatch,
):
    from alembic import command

    calls: list[tuple[str, str]] = []

    class Connection:
        def exec_driver_sql(self, statement: str) -> None:
            calls.append(("sql", statement))

        def close(self) -> None:
            calls.append(("close", ""))

    class Engine:
        def connect(self) -> Connection:
            calls.append(("connect", ""))
            return Connection()

    def upgrade(_config, target: str) -> None:
        calls.append(("upgrade", target))

    monkeypatch.setattr(command, "upgrade", upgrade)
    dbs._run_alembic_upgrade(Engine())

    assert calls[0] == ("connect", "")
    assert calls[1][1].startswith("SELECT pg_advisory_lock(")
    assert calls[2] == ("upgrade", "head")
    assert calls[3][1].startswith("SELECT pg_advisory_unlock(")
    assert calls[4] == ("close", "")


def test_postgres_alembic_migration_lock_releases_on_upgrade_failure(
    dbs,
    monkeypatch,
):
    from alembic import command

    calls: list[str] = []

    class Connection:
        def exec_driver_sql(self, statement: str) -> None:
            calls.append(statement)

        def close(self) -> None:
            calls.append("close")

    class Engine:
        def connect(self) -> Connection:
            return Connection()

    def upgrade(_config, _target: str) -> None:
        raise RuntimeError("migration failed")

    monkeypatch.setattr(command, "upgrade", upgrade)
    with pytest.raises(RuntimeError, match="migration failed"):
        dbs._run_alembic_upgrade(Engine())

    assert calls[0].startswith("SELECT pg_advisory_lock(")
    assert calls[1].startswith("SELECT pg_advisory_unlock(")
    assert calls[2] == "close"
