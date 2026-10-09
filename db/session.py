"""Database engine and session management.

Supports **SQLite** (local dev / tests) and **PostgreSQL** (production). The
engine URL is resolved from the environment (``PRAXYS_DATABASE_URL`` /
``DATABASE_URL``) with a SQLite file under ``DATA_DIR`` as the default
fallback, so existing local and CI workflows keep working unchanged.

Provides both sync (for pandas ``read_sql`` data loading) and async (for
FastAPI-Users) sessions. On PostgreSQL a single psycopg3 driver backs both
the sync and async engines.

Schema management:
- SQLite (dev / tests): ``Base.metadata.create_all`` builds new databases and
  narrow compatibility migrations upgrade existing local files.
- PostgreSQL (real deployments): Alembic owns schema evolution. ``init_db``
  runs ``alembic upgrade head`` under a Postgres advisory lock so exactly one
  worker/instance applies pending migrations.
"""
import json
import logging
import os
from datetime import datetime
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import DateTime, String, create_engine, event, inspect, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

logger = logging.getLogger(__name__)


# SQLite tuning pragmas applied to every new connection.
#
# journal_mode is DELETE (rollback journal), NOT WAL — deliberately.
# On Azure App Service Linux the DATA_DIR (/home) is an Azure Files (SMB)
# network mount, and SQLite's WAL mode requires a shared-memory index (the
# ``-shm`` file) backed by mmap that does NOT work over a network filesystem.
# SQLite documents this explicitly ("WAL does not work over a network
# filesystem", https://www.sqlite.org/wal.html). Running WAL on /home caused
# "database disk image is malformed" corruption in production — the failure
# is amplified by multiple gunicorn worker processes acting as concurrent
# writers over SMB. A classic rollback journal works over SMB (byte-range
# locks); paired with a SINGLE writer (run the backend with one gunicorn
# worker — see docs/ops/backup-and-restore.md) and busy_timeout, writes stay
# safe.
#
# synchronous=FULL (not NORMAL): on the SMB mount a container recycle mid-write
# (every deploy/scale) is the "power loss" equivalent, and FULL fsyncs the
# rollback journal so an interrupted write can't corrupt the file. It costs
# extra SMB round-trips per commit, but on this low-traffic workload
# correctness beats throughput. The remaining pragmas are cache/locality wins.
#
# NB: migrating to PostgreSQL (#360) retires this whole failure class — the
# pragmas below no-op for non-SQLite engines.
_SQLITE_PRAGMAS = (
    ("journal_mode", "DELETE"),
    ("synchronous", "FULL"),
    # 20 MB SQLite page cache (negative value = KB; default is 2 MB).
    ("cache_size", "-20000"),
    ("temp_store", "MEMORY"),
    # Wait up to 5s on writer contention before raising "database is locked".
    ("busy_timeout", "5000"),
)

# Postgres connection-pool defaults, sized for a Burstable Flexible Server
# tier (low max_connections). Overridable via env for larger tiers.
_PG_POOL_SIZE = int(os.environ.get("PRAXYS_DB_POOL_SIZE", "5"))
_PG_MAX_OVERFLOW = int(os.environ.get("PRAXYS_DB_MAX_OVERFLOW", "5"))
_PG_POOL_RECYCLE = int(os.environ.get("PRAXYS_DB_POOL_RECYCLE", "1800"))

# AAD scope for Azure Database for PostgreSQL Entra (Managed Identity) auth.
# https://learn.microsoft.com/azure/postgresql/flexible-server/how-to-configure-sign-in-azure-ad-authentication
_AAD_DB_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
_entra_token_cache: dict[str, object] = {"token": None, "expires_on": 0.0}


def _attach_sqlite_pragmas(engine_obj) -> None:
    """Attach a connect listener that applies _SQLITE_PRAGMAS to each connection.

    No-op for non-SQLite engines (so the Postgres migration drops in without
    code changes). PRAGMA journal_mode is also a no-op against ``:memory:``
    databases used in tests, which is fine.
    """
    if engine_obj.dialect.name != "sqlite":
        return

    # AsyncEngine wraps a sync core; DBAPI events live on the sync side.
    @event.listens_for(getattr(engine_obj, "sync_engine", engine_obj), "connect")
    def _apply_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            for pragma, value in _SQLITE_PRAGMAS:
                cursor.execute(f"PRAGMA {pragma}={value}")
        finally:
            cursor.close()


def _uses_entra_auth() -> bool:
    """True when the Postgres password should be a short-lived AAD token."""
    return os.environ.get("PRAXYS_DB_AUTH", "").strip().lower() == "entra"


def _entra_db_token() -> str:
    """Return a cached Azure AD access token for the Postgres AAD scope.

    Uses the App Service system-assigned managed identity in production
    (``WEBSITE_SITE_NAME`` present) and DefaultAzureCredential elsewhere, so
    no DB password lives in app settings. Tokens are cached until ~5 min
    before expiry.
    """
    import time

    now = time.time()
    tok = _entra_token_cache.get("token")
    exp = float(_entra_token_cache.get("expires_on") or 0.0)
    if tok and exp - now > 300:
        return str(tok)

    client_id = os.environ.get("AZURE_CLIENT_ID")
    if os.environ.get("WEBSITE_SITE_NAME"):
        from azure.identity import ManagedIdentityCredential

        cred = (
            ManagedIdentityCredential(client_id=client_id)
            if client_id
            else ManagedIdentityCredential()
        )
    else:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential()
    access = cred.get_token(_AAD_DB_SCOPE)
    _entra_token_cache["token"] = access.token
    _entra_token_cache["expires_on"] = float(access.expires_on)
    return access.token


def _attach_entra_token(engine_obj) -> None:
    """Inject a fresh AAD token as the DB password on each new connection."""
    if not _uses_entra_auth():
        return
    target = getattr(engine_obj, "sync_engine", engine_obj)

    @event.listens_for(target, "do_connect")
    def _provide_token(_dialect, _conn_rec, _cargs, cparams):
        cparams["password"] = _entra_db_token()


def get_data_dir() -> str:
    """Return the data directory path (configurable via DATA_DIR env var)."""
    return os.environ.get(
        "DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data")
    )


_POSTGRES_DRIVER = "postgresql+psycopg"


def _normalize_db_url(raw: str) -> str:
    """Normalize a user-supplied DATABASE_URL into a SQLAlchemy URL.

    - ``postgres://`` and driver-less ``postgresql://`` become
      ``postgresql+psycopg://`` (psycopg3 backs both sync and async engines).
    - URLs that already name a driver (``postgresql+asyncpg``, ``sqlite``,
      etc.) are returned unchanged.
    """
    raw = raw.strip()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = _POSTGRES_DRIVER + "://" + raw[len("postgresql://"):]
    return raw


def _configured_db_url() -> str | None:
    """Return the normalized configured DB URL, or None to use the SQLite default."""
    for var in ("PRAXYS_DATABASE_URL", "DATABASE_URL"):
        val = os.environ.get(var)
        if val and val.strip():
            return _normalize_db_url(val)
    return None


def get_database_url() -> str:
    """Return the sync database URL (Postgres when configured, else SQLite file)."""
    configured = _configured_db_url()
    if configured:
        return configured
    data_dir = get_data_dir()
    db_path = os.path.join(data_dir, "trainsight.db")
    return f"sqlite:///{db_path}"


def get_async_database_url() -> str:
    """Return the async database URL derived from get_database_url()."""
    sync_url = get_database_url()
    if sync_url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + sync_url[len("sqlite:///"):]
    # psycopg3 supports async engines with the same driver name.
    return sync_url


def is_postgres() -> bool:
    """True when the active engine targets PostgreSQL."""
    return make_url(get_database_url()).get_backend_name() == "postgresql"


def begin_serialized_write(db: Session) -> None:
    """Serialize a read-modify-write transaction on supported backends.

    PostgreSQL callers pair this with ``FOR UPDATE`` row locks. SQLite ignores
    ``FOR UPDATE``, so begin an immediate transaction before the first read to
    acquire its database-wide writer lock.
    """
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def _make_sync_engine(url: str):
    """Build a sync Engine appropriate for the URL's dialect."""
    backend = make_url(url).get_backend_name()
    hide_parameters = (
        os.getenv("PRAXYS_HIDE_SQL_PARAMETERS", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if backend == "sqlite":
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False},
            hide_parameters=hide_parameters,
        )
        _attach_sqlite_pragmas(eng)
        return eng
    eng = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=_PG_POOL_SIZE,
        max_overflow=_PG_MAX_OVERFLOW,
        pool_recycle=_PG_POOL_RECYCLE,
        hide_parameters=hide_parameters,
    )
    _attach_entra_token(eng)
    return eng


def _make_async_engine(url: str):
    """Build an async Engine appropriate for the URL's dialect."""
    backend = make_url(url).get_backend_name()
    hide_parameters = (
        os.getenv("PRAXYS_HIDE_SQL_PARAMETERS", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if backend == "sqlite":
        eng = create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            hide_parameters=hide_parameters,
        )
        _attach_sqlite_pragmas(eng)
        return eng
    eng = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=_PG_POOL_SIZE,
        max_overflow=_PG_MAX_OVERFLOW,
        pool_recycle=_PG_POOL_RECYCLE,
        hide_parameters=hide_parameters,
    )
    _attach_entra_token(eng)
    return eng


# Module-level engine/session singletons (initialized lazily)
engine = None
SessionLocal = None
async_engine = None
AsyncSessionLocal = None


def _skip_migrations() -> bool:
    return os.environ.get("PRAXYS_SKIP_MIGRATIONS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def dispose_engines() -> None:
    """Dispose the sync + async engine pools and clear the singletons.

    Closes every pooled DB connection so PostgreSQL frees the backend at once,
    instead of leaving it idle until TCP-keepalive reap. Called before any
    re-initialization (so a forced init cannot orphan a live pool). For the
    await-correct shutdown path use dispose_engines_async(). Best-effort;
    never raises.

    Background: abandoned pools accumulated as idle "zombie" backends across
    container recycles and per-tick init_db() calls, exhausting the Burstable
    server's small max_connections and 500ing every data endpoint (2026-07-05
    outage). See docs/ops/incident-response.md.
    """
    global engine, SessionLocal, async_engine, AsyncSessionLocal
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            logger.debug("sync engine dispose failed", exc_info=True)
    if async_engine is not None:
        try:
            # AsyncEngine wraps a sync core; disposing that core closes the
            # pool synchronously (fine from sync callers and tests).
            async_engine.sync_engine.dispose()
        except Exception:
            logger.debug("async engine dispose failed", exc_info=True)
    engine = None
    SessionLocal = None
    async_engine = None
    AsyncSessionLocal = None


async def dispose_engines_async() -> None:
    """Await-correct pool disposal for the FastAPI lifespan shutdown.

    Uses ``await async_engine.dispose()`` so the async (psycopg3) pool closes
    on the running event loop, then disposes the sync pool. Releasing pools on
    shutdown stops abandoned connections from lingering as idle "zombie"
    backends after a container recycle (2026-07-05 outage).
    """
    global engine, SessionLocal, async_engine, AsyncSessionLocal
    if async_engine is not None:
        try:
            await async_engine.dispose()
        except Exception:
            logger.debug("async engine dispose failed", exc_info=True)
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            logger.debug("sync engine dispose failed", exc_info=True)
    engine = None
    SessionLocal = None
    async_engine = None
    AsyncSessionLocal = None


def init_db(force: bool = False):
    """Initialize sync and async database engines and ensure the schema exists.

    Idempotent: once the engines exist this is a no-op, so hot paths that only
    need to guarantee initialization (the sync scheduler's per-tick call, the
    get_db / get_async_db fallbacks) do not rebuild the pools or re-run
    migrations. Rebuilding on every scheduler tick orphaned a pool each time
    and was a root cause of the 2026-07-05 connection-exhaustion outage. Pass
    ``force=True`` to rebuild (disposing the previous pools first); tests that
    repoint DATA_DIR at a fresh database null the module globals, same effect.
    """
    global engine, SessionLocal, async_engine, AsyncSessionLocal

    if not force and SessionLocal is not None and engine is not None:
        return

    # Drop any previous / half-initialized pool before rebuilding so a forced
    # re-init cannot leak the old connections.
    dispose_engines()

    url = get_database_url()
    async_url = get_async_database_url()
    backend = make_url(url).get_backend_name()

    # Ensure the SQLite data directory exists.
    if backend == "sqlite":
        db_path = url.split("sqlite:///", 1)[-1]
        if db_path and db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    # Sync engine (for pandas read_sql, data loading, migration)
    engine = _make_sync_engine(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Async engine (for FastAPI-Users)
    async_engine = _make_async_engine(async_url)
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    _ensure_schema(engine, backend)
    _run_startup_db_check(engine, backend)


_SQLITE_COMPAT_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "users": (
        ("terms_digest", "VARCHAR(71)"),
    ),
    "activities": (
        ("temperature_c", "FLOAT"),
        ("relative_humidity_pct", "FLOAT"),
        ("environment_source", "VARCHAR(40)"),
    ),
    "activity_splits": (
        ("power_source", "VARCHAR(20)"),
    ),
    "fitness_data": (
        ("power_source", "VARCHAR(20)"),
    ),
    "user_config": (
        ("plan_management", "JSON"),
        ("plan_execution_target", "VARCHAR(20)"),
        ("today_decision_check_claimed_at", "DATETIME"),
        ("today_decision_check_shown_at", "DATETIME"),
        ("today_decision_check_submitted_at", "DATETIME"),
    ),
    "adaptive_plans": (
        ("discipline", "VARCHAR(30) NOT NULL DEFAULT 'running'"),
    ),
    "adaptive_plan_goal_snapshots": (
        ("purpose_source", "VARCHAR(30)"),
        ("source_goal_id", "VARCHAR(36)"),
        ("source_goal_revision", "VARCHAR(64)"),
    ),
    "goal_baseline_test_records": (
        ("purpose_source", "VARCHAR(30)"),
        ("source_goal_id", "VARCHAR(36)"),
        ("source_goal_revision", "VARCHAR(64)"),
    ),
    "plan_proposals": (
        ("discipline", "VARCHAR(30) NOT NULL DEFAULT 'running'"),
        ("idempotency_fingerprint", "VARCHAR(64)"),
    ),
    "training_plans": (
        ("canonical_id", "VARCHAR(36)"),
        ("activity_type", "VARCHAR(30)"),
        ("workout_structure_version", "VARCHAR(20)"),
        ("workout_structure", "JSON"),
        ("workout_origin", "VARCHAR(30) NOT NULL DEFAULT 'legacy'"),
        ("adaptive_plan_id", "VARCHAR(36)"),
    ),
    "plan_deliveries": (
        ("canonical_id", "VARCHAR(36)"),
        ("plan_version", "VARCHAR(64)"),
        ("provider_content_version", "VARCHAR(64)"),
        ("provider_account_id", "VARCHAR(200)"),
        ("provider_references", "JSON NOT NULL DEFAULT '{}'"),
    ),
    "plan_target_workouts": (
        ("provider_references", "JSON NOT NULL DEFAULT '{}'"),
    ),
    "plan_target_calendar_syncs": (
        ("provider_references", "JSON NOT NULL DEFAULT '{}'"),
    ),
    "user_connections": (
        ("plan_delivery_consent", "VARCHAR(64)"),
        ("encrypted_garmin_tokens", "BLOB"),
        ("wrapped_token_dek", "BLOB"),
        ("garmin_token_generation", "VARCHAR(160)"),
        ("tokens_updated_at", "DATETIME"),
    ),
    "personal_context_items": (
        ("idempotency_key", "VARCHAR(128)"),
    ),
    "personal_context_consent_receipts": (
        ("idempotency_key", "VARCHAR(128)"),
    ),
    "feedback": (
        ("publication_consent_version", "VARCHAR(64)"),
        ("publication_consented_at", "DATETIME"),
        (
            "publication_status",
            "VARCHAR(24) NOT NULL DEFAULT 'private'",
        ),
        ("image_storage_provenance", "JSON"),
    ),
    "feedback_publication_outbox": (
        ("public_content_sha256", "VARCHAR(71)"),
        (
            "delivery_evidence",
            "VARCHAR(16) NOT NULL DEFAULT 'not_sent'",
        ),
    ),
}


def _sqlite_legacy_target_repo(
    issue_url: object,
    issue_number: int,
    feedback_id: int,
) -> tuple[str, bool]:
    """Return a strict GitHub repo or an internal legacy placeholder."""
    if isinstance(issue_url, str):
        parsed = urlsplit(issue_url)
        parts = [part for part in parsed.path.split("/") if part]
        if (
            parsed.scheme == "https"
            and parsed.netloc.casefold() == "github.com"
            and not parsed.query
            and not parsed.fragment
            and len(parts) == 4
            and parts[2].casefold() == "issues"
            and parts[3].isascii()
            and parts[3].isdecimal()
            and int(parts[3]) == issue_number
            and parts[0]
            and parts[1]
        ):
            return f"{parts[0]}/{parts[1]}", True
    return f"legacy-unresolved/{feedback_id}", False


def _normalize_sqlite_feedback_publication_rows(connection) -> None:
    """Fence rows written by the unshipped v1-marker outbox implementation."""
    connection.exec_driver_sql(
        "UPDATE feedback_publication_outbox SET state = 'published', "
        "delivery_evidence = 'published' WHERE state = 'published' OR "
        "github_issue_number IS NOT NULL"
    )
    connection.exec_driver_sql(
        "UPDATE feedback_publication_outbox SET delivery_evidence = "
        "'ambiguous' WHERE delivery_evidence != 'published' AND ("
        "state IN ('sending', 'reconciling') OR "
        "last_error_code = 'multiple_marker_matches' OR EXISTS ("
        "SELECT 1 FROM feedback_publication_attempts AS attempt WHERE "
        "attempt.outbox_id = feedback_publication_outbox.id AND "
        "attempt.outcome IN ('in_flight', 'unknown', 'created', "
        "'reconciled')))"
    )
    connection.exec_driver_sql(
        "UPDATE feedback_publication_outbox SET state = 'manual_review', "
        "last_error_code = COALESCE(last_error_code, "
        "'marker_content_binding_missing') WHERE marker_version NOT IN "
        "('v2', 'legacy') AND state NOT IN ('published', 'cancelled')"
    )


def _normalize_sqlite_feedback_publication_evidence(engine_obj) -> None:
    """Apply the idempotent old-row fence outside a required table rebuild."""
    table_names = set(inspect(engine_obj).get_table_names())
    if not {
        "feedback_publication_outbox",
        "feedback_publication_attempts",
    } <= table_names:
        return
    outbox_columns = {
        column["name"]
        for column in inspect(engine_obj).get_columns(
            "feedback_publication_outbox"
        )
    }
    if "delivery_evidence" not in outbox_columns:
        return
    with engine_obj.begin() as connection:
        _normalize_sqlite_feedback_publication_rows(connection)


def _sqlite_feedback_publication_outbox_needs_rebuild(engine_obj) -> bool:
    inspector = inspect(engine_obj)
    if "feedback_publication_outbox" not in set(inspector.get_table_names()):
        return False
    columns = {
        column["name"]: column
        for column in inspector.get_columns("feedback_publication_outbox")
    }
    if any(
        not columns.get(name, {}).get("nullable", True)
        for name in ("consent_version", "consented_at", "payload_sha256")
    ):
        return True
    unique_names = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints(
            "feedback_publication_outbox"
        )
    }
    check_names = {
        constraint.get("name")
        for constraint in inspector.get_check_constraints(
            "feedback_publication_outbox"
        )
    }
    return bool(
        "uq_feedback_publication_repo_issue" in unique_names
        or {
            "ck_feedback_publication_outbox_delivery_evidence",
            "ck_feedback_publication_outbox_binding_shape",
            "ck_feedback_publication_outbox_published_evidence",
        }
        - check_names
    )


def _rebuild_sqlite_feedback_publication_outbox(engine_obj) -> None:
    """Transactionally replace only the obsolete local outbox table shape."""
    if not _sqlite_feedback_publication_outbox_needs_rebuild(engine_obj):
        return

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    connection = engine_obj.connect()
    foreign_keys_enabled = bool(
        connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
    )
    connection.commit()
    if foreign_keys_enabled:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
    transaction = connection.begin()
    try:
        _normalize_sqlite_feedback_publication_rows(connection)
        inspector = inspect(connection)
        unique_names = {
            constraint.get("name")
            for constraint in inspector.get_unique_constraints(
                "feedback_publication_outbox"
            )
        }
        check_names = {
            constraint.get("name")
            for constraint in inspector.get_check_constraints(
                "feedback_publication_outbox"
            )
        }
        operations = Operations(MigrationContext.configure(connection))
        with operations.batch_alter_table(
            "feedback_publication_outbox",
            recreate="always",
        ) as batch_op:
            if "uq_feedback_publication_repo_issue" in unique_names:
                batch_op.drop_constraint(
                    "uq_feedback_publication_repo_issue",
                    type_="unique",
                )
            if "ck_feedback_publication_outbox_digest" in check_names:
                batch_op.drop_constraint(
                    "ck_feedback_publication_outbox_digest",
                    type_="check",
                )
            batch_op.alter_column(
                "consent_version",
                existing_type=String(64),
                nullable=True,
            )
            batch_op.alter_column(
                "consented_at",
                existing_type=DateTime(),
                nullable=True,
            )
            batch_op.alter_column(
                "payload_sha256",
                existing_type=String(71),
                nullable=True,
            )
            if (
                "ck_feedback_publication_outbox_delivery_evidence"
                not in check_names
            ):
                batch_op.create_check_constraint(
                    "ck_feedback_publication_outbox_delivery_evidence",
                    "delivery_evidence IN "
                    "('not_sent', 'ambiguous', 'published')",
                )
            if "ck_feedback_publication_outbox_binding_shape" not in check_names:
                batch_op.create_check_constraint(
                    "ck_feedback_publication_outbox_binding_shape",
                    "((marker_version = 'legacy' AND state = 'published' AND "
                    "delivery_evidence = 'published' AND consent_version IS NULL "
                    "AND consented_at IS NULL AND payload_sha256 IS NULL AND "
                    "public_content_sha256 IS NULL) OR (marker_version = 'v2' "
                    "AND consent_version IS NOT NULL AND consented_at IS NOT NULL "
                    "AND payload_sha256 LIKE 'sha256:%' AND "
                    "public_content_sha256 LIKE 'sha256:%') OR "
                    "(marker_version = 'v1' AND state IN ('manual_review', "
                    "'cancelled', 'published') AND consent_version IS NOT NULL "
                    "AND consented_at IS NOT NULL AND payload_sha256 LIKE "
                    "'sha256:%' AND public_content_sha256 IS NULL))",
                )
            if (
                "ck_feedback_publication_outbox_published_evidence"
                not in check_names
            ):
                batch_op.create_check_constraint(
                    "ck_feedback_publication_outbox_published_evidence",
                    "((state = 'published' AND delivery_evidence = 'published') "
                    "OR (state != 'published' AND "
                    "delivery_evidence != 'published'))",
                )
        violations = connection.exec_driver_sql(
            "PRAGMA foreign_key_check"
        ).all()
        if violations:
            raise RuntimeError(
                "Feedback publication outbox rebuild would violate foreign keys"
            )
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        if foreign_keys_enabled:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
        connection.close()


def _repair_sqlite_feedback_publication(engine_obj) -> None:
    """Idempotently retain legacy issues and fence intermediate outbox rows."""
    inspector = inspect(engine_obj)
    table_names = set(inspector.get_table_names())
    if not {"feedback", "feedback_publication_outbox"} <= table_names:
        return
    feedback_columns = {
        column["name"] for column in inspector.get_columns("feedback")
    }
    required = {
        "id",
        "status",
        "github_issue_number",
        "github_issue_url",
        "created_at",
        "updated_at",
        "publication_status",
    }
    if not required <= feedback_columns:
        return
    now = datetime.utcnow()
    with engine_obj.begin() as conn:
        rows = list(
            conn.execute(
                text(
                    "SELECT id, status, github_issue_number, github_issue_url, "
                    "created_at, updated_at FROM feedback "
                    "WHERE github_issue_number IS NOT NULL"
                )
            ).mappings()
        )
        for row in rows:
            try:
                feedback_id = int(row["id"])
                issue_number = int(row["github_issue_number"])
            except (TypeError, ValueError):
                continue
            if feedback_id <= 0 or issue_number <= 0:
                continue
            target_repo, _url_is_strict = _sqlite_legacy_target_repo(
                row["github_issue_url"],
                issue_number,
                feedback_id,
            )
            existing = conn.execute(
                text(
                    "SELECT 1 FROM feedback_publication_outbox "
                    "WHERE feedback_id = :feedback_id LIMIT 1"
                ),
                {"feedback_id": feedback_id},
            ).first()
            if existing is None:
                identity = (
                    f"feedback:{feedback_id}:repo:{target_repo}:"
                    f"issue:{issue_number}"
                )
                created_at = row["created_at"] or row["updated_at"] or now
                published_at = row["updated_at"] or row["created_at"] or now
                conn.execute(
                    text(
                        "INSERT INTO feedback_publication_outbox ("
                        "id, feedback_id, public_id, marker_version, "
                        "target_repo, consent_version, consented_at, "
                        "payload_sha256, public_content_sha256, state, "
                        "delivery_evidence, attempt_count, reconcile_count, "
                        "available_at, lease_token, lease_expires_at, "
                        "github_issue_number, github_issue_url, "
                        "last_error_code, created_at, updated_at, published_at"
                        ") VALUES ("
                        ":id, :feedback_id, :public_id, 'legacy', "
                        ":target_repo, NULL, NULL, NULL, NULL, 'published', "
                        "'published', 0, 0, :available_at, NULL, NULL, "
                        ":issue_number, :issue_url, "
                        "'legacy_publication_migrated', :created_at, "
                        ":updated_at, :published_at)"
                    ),
                    {
                        "id": str(
                            uuid5(
                                NAMESPACE_URL,
                                "praxys-feedback-legacy-outbox:" + identity,
                            )
                        ),
                        "feedback_id": feedback_id,
                        "public_id": uuid5(
                            NAMESPACE_URL,
                            "praxys-feedback-legacy-public:" + identity,
                        ).hex,
                        "target_repo": target_repo,
                        "available_at": published_at,
                        "issue_number": issue_number,
                        "issue_url": row["github_issue_url"],
                        "created_at": created_at,
                        "updated_at": published_at,
                        "published_at": published_at,
                    },
                )
            conn.execute(
                text(
                    "UPDATE feedback SET publication_status = 'published' "
                    "WHERE id = :feedback_id"
                ),
                {"feedback_id": feedback_id},
            )

        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_feedback_publication_repo_issue_current ON "
            "feedback_publication_outbox (target_repo, github_issue_number) "
            "WHERE marker_version != 'legacy' AND "
            "github_issue_number IS NOT NULL"
        )
        conn.exec_driver_sql(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_outbox_binding_immutable"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER "
            "trg_feedback_publication_outbox_binding_immutable "
            "BEFORE UPDATE OF feedback_id, public_id, marker_version, "
            "target_repo, consent_version, consented_at, payload_sha256, "
            "public_content_sha256 ON feedback_publication_outbox WHEN NOT ("
            "(OLD.feedback_id IS NEW.feedback_id OR "
            "(OLD.feedback_id IS NOT NULL AND NEW.feedback_id IS NULL)) AND "
            "OLD.public_id IS NEW.public_id AND "
            "OLD.marker_version IS NEW.marker_version AND "
            "OLD.target_repo IS NEW.target_repo AND "
            "OLD.consent_version IS NEW.consent_version AND "
            "OLD.consented_at IS NEW.consented_at AND "
            "OLD.payload_sha256 IS NEW.payload_sha256 AND "
            "OLD.public_content_sha256 IS NEW.public_content_sha256) BEGIN "
            "SELECT RAISE(ABORT, "
            "'feedback publication binding is immutable'); END"
        )
        conn.exec_driver_sql(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_evidence_published_terminal"
        )
        conn.exec_driver_sql(
            "CREATE TRIGGER "
            "trg_feedback_publication_evidence_published_terminal "
            "BEFORE UPDATE OF delivery_evidence ON "
            "feedback_publication_outbox WHEN "
            "OLD.delivery_evidence = 'published' AND "
            "NEW.delivery_evidence != 'published' BEGIN "
            "SELECT RAISE(ABORT, "
            "'published feedback evidence is terminal'); END"
        )


def _ensure_sqlite_compat_columns(engine_obj) -> None:
    """Apply narrow additive upgrades to existing local SQLite databases."""
    with engine_obj.begin() as conn:
        for table, columns in _SQLITE_COMPAT_COLUMNS.items():
            existing = {
                str(row[1])
                for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")')
            }
            for column, ddl_type in columns:
                if column in existing:
                    continue
                conn.exec_driver_sql(
                    f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl_type}'
                )
                logger.info("Added SQLite compatibility column %s.%s", table, column)
            if table == "plan_deliveries":
                conn.exec_driver_sql(
                    'UPDATE "plan_deliveries" '
                    'SET "plan_version" = "workout_version" '
                    'WHERE "plan_version" IS NULL'
                )
            elif table == "training_plans":
                missing_ids = conn.exec_driver_sql(
                    'SELECT "id" FROM "training_plans" '
                    'WHERE "canonical_id" IS NULL OR "canonical_id" = \'\''
                ).scalars().all()
                for plan_id in missing_ids:
                    conn.exec_driver_sql(
                        'UPDATE "training_plans" SET "canonical_id" = ? '
                        'WHERE "id" = ?',
                        (str(uuid4()), plan_id),
                    )
                meta_projection = (
                    '"meta"'
                    if "meta" in existing
                    else "NULL AS meta"
                )
                rows = conn.exec_driver_sql(
                    'SELECT "id", "source", '
                    f'{meta_projection}, "workout_origin" '
                    'FROM "training_plans"'
                ).all()
                for plan_id, source, raw_meta, workout_origin in rows:
                    normalized_source = str(source or "").strip().casefold()
                    meta = raw_meta
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except (TypeError, ValueError):
                            meta = None
                    if normalized_source in {"ai", "praxys"}:
                        origin = (
                            "accepted_target"
                            if isinstance(meta, dict)
                            and isinstance(
                                meta.get("accepted_from_target"),
                                dict,
                            )
                            else str(workout_origin or "legacy")
                        )
                        conn.exec_driver_sql(
                            'UPDATE "training_plans" '
                            'SET "workout_origin" = ? '
                            'WHERE "id" = ?',
                            (origin, plan_id),
                        )
                    elif workout_origin in (None, "", "legacy"):
                        conn.exec_driver_sql(
                            'UPDATE "training_plans" '
                            'SET "workout_origin" = ? WHERE "id" = ?',
                            ("imported", plan_id),
                        )
            elif table == "feedback":
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_feedback_publication_status "
                    "ON feedback (publication_status)"
                )

        delivery_rows = conn.exec_driver_sql(
            'SELECT "id", "user_id", "target", "canonical_key", '
            '"workout_version", "canonical_id" FROM "plan_deliveries"'
        ).all()
        delivery_identities: dict[tuple[str, str, str, str], str] = {}
        for (
            delivery_id,
            user_id,
            target,
            canonical_key,
            version,
            stored_canonical_id,
        ) in delivery_rows:
            canonical_id = stored_canonical_id
            if not canonical_id:
                prefix, separator, candidate = str(
                    canonical_key or ""
                ).partition(":")
                if (
                    separator
                    and prefix.strip().casefold() in {"ai", "praxys"}
                ):
                    try:
                        canonical_id = str(UUID(candidate))
                    except (ValueError, AttributeError):
                        canonical_id = None
            if not canonical_id:
                continue
            identity = (user_id, target, canonical_id, version)
            duplicate_id = delivery_identities.get(identity)
            if duplicate_id is not None and duplicate_id != delivery_id:
                raise RuntimeError(
                    "Duplicate plan delivery canonical identity "
                    f"{identity!r}: {duplicate_id}, {delivery_id}"
                )
            delivery_identities[identity] = delivery_id
            conn.exec_driver_sql(
                'UPDATE "plan_deliveries" '
                'SET "canonical_id" = ?, "canonical_key" = ? '
                'WHERE "id" = ?',
                (canonical_id, f"ai:{canonical_id}", delivery_id),
            )
        conn.exec_driver_sql(
            'CREATE UNIQUE INDEX IF NOT EXISTS '
            '"uq_plan_delivery_canonical_version_target" '
            'ON "plan_deliveries" '
            '("user_id", "target", "canonical_id", "workout_version")'
        )


def _ensure_sqlite_context_idempotency_indexes(engine_obj) -> None:
    """Add owner-scoped uniqueness after compatibility columns are present."""
    with engine_obj.begin() as conn:
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_personal_context_item_idempotency "
            "ON personal_context_items (user_id, idempotency_key)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "uq_personal_context_consent_idempotency "
            "ON personal_context_consent_receipts "
            "(user_id, idempotency_key)"
        )


def _ensure_sqlite_terms_receipt_immutability(engine_obj) -> None:
    """Prevent local/test code from updating append-only legal receipts."""
    with engine_obj.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS "
            "trg_terms_acceptance_receipts_immutable "
            "BEFORE UPDATE ON terms_acceptance_receipts "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'terms acceptance receipts are immutable'); "
            "END"
        )


def _ensure_sqlite_training_plan_identity(engine_obj) -> None:
    """Replace the legacy date/type uniqueness rule with canonical identity."""
    constraints = inspect(engine_obj).get_unique_constraints("training_plans")
    legacy_constraint = next(
        (
            item
            for item in constraints
            if item.get("name") == "uq_user_date_plan"
            or item.get("column_names")
            == ["user_id", "date", "source", "workout_type"]
        ),
        None,
    )
    if legacy_constraint is None:
        return

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine_obj.begin() as conn:
        operations = Operations(MigrationContext.configure(conn))
        with operations.batch_alter_table(
            "training_plans",
            recreate="always",
            naming_convention={
                "uq": "uq_%(table_name)s_%(column_0_name)s",
            },
        ) as batch_op:
            batch_op.drop_constraint(
                legacy_constraint.get("name")
                or "uq_training_plans_user_id",
                type_="unique",
            )
            batch_op.create_unique_constraint(
                "uq_training_plan_user_canonical",
                ["user_id", "canonical_id"],
            )
    logger.info("Migrated SQLite training-plan identity constraints")


def _ensure_sqlite_road_10k_snapshot_schema(engine_obj) -> None:
    """Remove legacy raw 10K history IDs and ensure aggregate snapshot support."""
    table_names = set(inspect(engine_obj).get_table_names())
    generation_table = "road_10k_plan_generations"
    snapshot_table = "road_10k_training_pattern_snapshots"
    if generation_table not in table_names:
        return

    generation_columns = {
        column["name"]
        for column in inspect(engine_obj).get_columns(generation_table)
    }
    with engine_obj.begin() as conn:
        if "history_observation_ids" in generation_columns:
            from alembic.migration import MigrationContext
            from alembic.operations import Operations

            conn.exec_driver_sql("PRAGMA secure_delete=ON")
            operations = Operations(MigrationContext.configure(conn))
            with operations.batch_alter_table(
                generation_table,
                recreate="always",
            ) as batch_op:
                batch_op.drop_column("history_observation_ids")
            logger.info(
                "Removed obsolete raw road 10K history IDs from SQLite audit schema"
            )

        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS "
            "ix_road_10k_generation_owner_training_pattern "
            "ON road_10k_plan_generations "
            "(user_id, training_pattern_snapshot_version)"
        )
        if snapshot_table in table_names:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS "
                "ix_road_10k_training_pattern_snapshots_user_id "
                "ON road_10k_training_pattern_snapshots (user_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS "
                "ix_road_10k_training_pattern_owner_created "
                "ON road_10k_training_pattern_snapshots (user_id, created_at)"
            )
            conn.exec_driver_sql(
                "CREATE TRIGGER IF NOT EXISTS "
                "trg_road_10k_training_pattern_snapshots_immutable "
                "BEFORE UPDATE ON road_10k_training_pattern_snapshots "
                "BEGIN "
                "SELECT RAISE(ABORT, "
                "'road 10K training pattern snapshots are immutable'); "
                "END"
            )


def _ensure_schema(engine_obj, backend: str) -> None:
    """Create / migrate the schema for the active backend.

    SQLite uses ``create_all`` for new databases plus a narrow additive upgrade
    list for existing local files. PostgreSQL uses Alembic for all evolution.
    """
    if _skip_migrations():
        return
    if backend == "sqlite":
        Base.metadata.create_all(bind=engine_obj)
        _ensure_sqlite_road_10k_snapshot_schema(engine_obj)
        _ensure_sqlite_compat_columns(engine_obj)
        _rebuild_sqlite_feedback_publication_outbox(engine_obj)
        _normalize_sqlite_feedback_publication_evidence(engine_obj)
        _repair_sqlite_feedback_publication(engine_obj)
        _ensure_sqlite_context_idempotency_indexes(engine_obj)
        _ensure_sqlite_terms_receipt_immutability(engine_obj)
        _ensure_sqlite_training_plan_identity(engine_obj)
        _normalize_praxys_plan_sources(engine_obj)
        return
    _run_alembic_upgrade(engine_obj)
    _normalize_praxys_plan_sources(engine_obj)


def _normalize_praxys_plan_sources(engine_obj) -> None:
    """Contract legacy Praxys ownership aliases without changing identity."""
    from analysis.config import (
        LEGACY_PRAXYS_PLAN_SOURCE,
        PRAXYS_PLAN_SOURCE,
    )

    with engine_obj.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE training_plans "
                "SET source = :canonical_source "
                "WHERE source = :legacy_source"
            ),
            {
                "canonical_source": PRAXYS_PLAN_SOURCE,
                "legacy_source": LEGACY_PRAXYS_PLAN_SOURCE,
            },
        )
    if result.rowcount and result.rowcount > 0:
        logger.info(
            "Normalized %d legacy Praxys plan source rows",
            result.rowcount,
        )


def _run_alembic_upgrade(engine_obj) -> None:
    """Run ``alembic upgrade head`` under a Postgres advisory lock.

    The advisory lock serializes concurrent workers/instances so only one
    applies pending migrations; the rest block briefly, then no-op.
    """
    from alembic import command
    from alembic.config import Config

    ini_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
    cfg = Config(ini_path)
    # Advisory-lock key: arbitrary constant shared by all workers ("prax").
    lock_key = 0x70726178
    lock_conn = engine_obj.connect()
    try:
        lock_conn.exec_driver_sql(f"SELECT pg_advisory_lock({lock_key})")
        logger.info("Running Alembic migrations (upgrade head)")
        command.upgrade(cfg, "head")
        logger.info("Alembic migrations up to date")
    finally:
        try:
            lock_conn.exec_driver_sql(f"SELECT pg_advisory_unlock({lock_key})")
        except Exception:
            logger.debug("pg_advisory_unlock failed", exc_info=True)
        lock_conn.close()


def _run_startup_db_check(engine_obj, backend: str) -> None:
    """Cheap DB integrity / connectivity check at startup (issue #351).

    - SQLite: ``PRAGMA quick_check`` (bounded; not full integrity_check on the
      ~230 MB file) catches ``database disk image is malformed`` before reads
      start 500ing.
    - PostgreSQL: ``SELECT 1`` confirms the connection is live.

    Non-fatal by design: a failure logs ERROR + emits telemetry (so it pages
    oncall) and lets the readiness probe report unhealthy, rather than
    crashing the process — which would remove our ability to serve the
    readiness signal at all.
    """
    detail = ""
    try:
        with engine_obj.connect() as conn:
            if backend == "sqlite":
                row = conn.exec_driver_sql("PRAGMA quick_check").fetchone()
                detail = (row[0] if row else "") or ""
                ok = detail.strip().lower() == "ok"
            else:
                conn.exec_driver_sql("SELECT 1")
                ok = True
    except Exception as exc:
        logger.error("Database startup check errored (%s): %s", backend, exc, exc_info=True)
        _emit_db_health(status="check_error", backend=backend)
        return

    if ok:
        logger.info("Database startup check OK (%s)", backend)
    else:
        logger.error("Database integrity check FAILED (%s): quick_check=%r", backend, detail)
        _emit_db_health(status="integrity_failed", backend=backend)


def _emit_db_health(*, status: str, backend: str) -> None:
    """Best-effort telemetry emit; never raises."""
    try:
        from api.telemetry import record_db_health

        record_db_health(status=status, backend=backend)
    except Exception:
        logger.debug("record_db_health emit failed", exc_info=True)


def get_db():
    """FastAPI dependency that yields a sync DB session."""
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """FastAPI dependency that yields an async DB session (for FastAPI-Users)."""
    if AsyncSessionLocal is None:
        init_db()
    async with AsyncSessionLocal() as session:
        yield session
