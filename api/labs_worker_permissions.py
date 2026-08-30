"""Shared least-privilege contract for the isolated Labs worker."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

TABLE_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "cache_revisions": ("SELECT",),
    "user_config": ("SELECT",),
    "activities": ("SELECT",),
    "activity_splits": ("SELECT",),
    "recovery_data": ("SELECT",),
    "fitness_data": ("SELECT",),
    "labs_analysis_jobs": ("SELECT",),
    "labs_analysis_outbox": ("SELECT",),
    "labs_experiment_enrollments": ("SELECT",),
    "labs_experiment_results": ("SELECT", "INSERT", "UPDATE"),
    "labs_deletion_tombstones": ("SELECT",),
}

COLUMN_PRIVILEGES: dict[str, dict[str, tuple[str, ...]]] = {
    "users": {
        "SELECT": (
            "id",
            "email",
            "is_active",
            "is_superuser",
            "is_demo",
            "terms_version",
            "terms_digest",
        ),
    },
    "terms_acceptance_receipts": {
        "SELECT": (
            "user_id",
            "terms_version",
            "terms_digest",
            "channel",
        ),
    },
    "activity_samples": {
        "SELECT": (
            "user_id",
            "activity_id",
            "source",
            "t_sec",
            "power_watts",
            "hr_bpm",
            "pace_sec_km",
        ),
    },
    "labs_analysis_jobs": {
        "UPDATE": (
            "status",
            "attempt_count",
            "failure_code",
            "retryable_failure",
            "started_at",
            "lease_expires_at",
            "completed_at",
            "updated_at",
        ),
    },
    "labs_analysis_outbox": {
        "UPDATE": (
            "status",
            "lease_expires_at",
            "last_error_code",
            "updated_at",
        ),
    },
    "labs_experiment_enrollments": {
        "UPDATE": (
            "status",
            "availability_reason",
            "started_at",
            "completed_at",
            "updated_at",
        ),
    },
    "user_connections": {
        "SELECT": (
            "user_id",
            "platform",
            "status",
            "preferences",
        ),
    },
}

_TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)


def required_tables() -> tuple[str, ...]:
    """Return every table required by the isolated worker."""
    return tuple(dict.fromkeys((*TABLE_PRIVILEGES, *COLUMN_PRIVILEGES)))


def _table_columns(db: Session, table_name: str) -> tuple[str, ...]:
    return tuple(
        str(row[0])
        for row in db.execute(
            text(
                "SELECT a.attname "
                "FROM pg_catalog.pg_attribute AS a "
                "JOIN pg_catalog.pg_class AS c ON c.oid = a.attrelid "
                "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' "
                "AND c.relname = :table_name "
                "AND a.attnum > 0 "
                "AND NOT a.attisdropped "
                "ORDER BY a.attnum"
            ),
            {"table_name": table_name},
        ).all()
    )


def _has_table_privilege(
    db: Session,
    role_name: str,
    table_name: str,
    privilege: str,
) -> bool:
    return bool(db.execute(
        text(
            "SELECT has_table_privilege("
            ":role, :table_name, :privilege"
            ")"
        ),
        {
            "role": role_name,
            "table_name": f"public.{table_name}",
            "privilege": privilege,
        },
    ).scalar_one())


def _has_column_privilege(
    db: Session,
    role_name: str,
    table_name: str,
    column_name: str,
    privilege: str,
) -> bool:
    return bool(db.execute(
        text(
            "SELECT has_column_privilege("
            ":role, :table_name, :column_name, :privilege"
            ")"
        ),
        {
            "role": role_name,
            "table_name": f"public.{table_name}",
            "column_name": column_name,
            "privilege": privilege,
        },
    ).scalar_one())


def verify_labs_worker_grants(
    db: Session,
    role_name: str | None = None,
) -> None:
    """Fail unless a role has exactly the worker's required DB privileges."""
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Labs worker grants require PostgreSQL")
    role = role_name or str(
        db.execute(text("SELECT current_user")).scalar_one()
    )
    failures: list[str] = []

    if not bool(db.execute(
        text(
            "SELECT has_database_privilege("
            ":role, current_database(), 'CONNECT'"
            ")"
        ),
        {"role": role},
    ).scalar_one()):
        failures.append("database CONNECT")
    if not bool(db.execute(
        text("SELECT has_schema_privilege(:role, 'public', 'USAGE')"),
        {"role": role},
    ).scalar_one()):
        failures.append("public schema USAGE")

    table_columns = {
        table: _table_columns(db, table)
        for table in required_tables()
    }
    failures.extend(
        f"missing table {table}"
        for table, columns in table_columns.items()
        if not columns
    )

    for table in required_tables():
        expected = set(TABLE_PRIVILEGES.get(table, ()))
        for privilege in _TABLE_PRIVILEGES:
            granted = _has_table_privilege(
                db,
                role,
                table,
                privilege,
            )
            if privilege in expected and not granted:
                failures.append(f"{table} {privilege}")
            elif privilege not in expected and granted:
                failures.append(f"{table} unexpected {privilege}")

    for table, privilege_map in COLUMN_PRIVILEGES.items():
        columns = table_columns[table]
        for privilege, expected_columns in privilege_map.items():
            expected = set(expected_columns)
            missing_columns = expected - set(columns)
            failures.extend(
                f"missing column {table}.{column}"
                for column in sorted(missing_columns)
            )
            for column in columns:
                granted = _has_column_privilege(
                    db,
                    role,
                    table,
                    column,
                    privilege,
                )
                if column in expected and not granted:
                    failures.append(
                        f"{table}.{column} {privilege}"
                    )
                elif column not in expected and granted:
                    failures.append(
                        f"{table}.{column} unexpected {privilege}"
                    )

    if failures:
        raise RuntimeError(
            "Labs worker database grants are incomplete or overbroad: "
            + ", ".join(sorted(failures))
        )
