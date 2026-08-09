"""Grant the Labs worker least-privilege access as the schema owner."""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TABLE_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "cache_revisions": ("SELECT",),
    "user_config": ("SELECT",),
    "activities": ("SELECT",),
    "activity_splits": ("SELECT",),
    "recovery_data": ("SELECT",),
    "fitness_data": ("SELECT",),
    "labs_analysis_jobs": ("SELECT",),
    "labs_experiment_enrollments": ("SELECT",),
    "labs_experiment_results": ("SELECT", "INSERT", "UPDATE"),
    "labs_deletion_tombstones": ("SELECT",),
}
COLUMN_PRIVILEGES: dict[str, dict[str, tuple[str, ...]]] = {
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


def _comma_separated(values: Iterable[str]) -> str:
    return ", ".join(values)


def _required_tables() -> tuple[str, ...]:
    return tuple(dict.fromkeys((*TABLE_PRIVILEGES, *COLUMN_PRIVILEGES)))


def provision_labs_worker_grants(
    db: Session,
    identity_name: str,
) -> None:
    """Grant and verify the worker permissions using the table-owning role."""
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Labs worker grants require PostgreSQL")
    normalized = identity_name.strip()
    if not normalized:
        raise ValueError("identity_name is required")

    role_exists = db.execute(
        text(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :role"
            ")"
        ),
        {"role": normalized},
    ).scalar_one()
    if not role_exists:
        raise RuntimeError(
            f"PostgreSQL role {normalized!r} does not exist; "
            "create its Microsoft Entra mapping first"
        )

    table_names = _required_tables()
    catalog_rows = db.execute(
        text(
            "SELECT c.relname, pg_catalog.pg_get_userbyid(c.relowner) "
            "FROM pg_catalog.pg_class AS c "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' "
            "AND c.relname::text = ANY(:table_names)"
        ),
        {"table_names": list(table_names)},
    ).all()
    owners = {str(table): str(owner) for table, owner in catalog_rows}
    missing = sorted(set(table_names) - owners.keys())
    if missing:
        raise RuntimeError(
            "Required Labs tables are missing: " + _comma_separated(missing)
        )
    current_user = str(db.execute(text("SELECT current_user")).scalar_one())
    if normalized == current_user:
        raise RuntimeError("Labs worker identity must not be the schema owner")
    not_owned = sorted(
        table for table, owner in owners.items() if owner != current_user
    )
    if not_owned:
        raise RuntimeError(
            f"Current role {current_user!r} does not own required tables: "
            + _comma_separated(not_owned)
        )

    preparer = db.get_bind().dialect.identifier_preparer
    quoted_role = preparer.quote(normalized)
    quoted_tables = {
        table: preparer.quote(table)
        for table in table_names
    }
    table_columns: dict[str, tuple[str, ...]] = {}
    for table, privilege_map in COLUMN_PRIVILEGES.items():
        columns = tuple(
            str(row[0])
            for row in db.execute(
                text(
                    "SELECT column_name "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = :table_name "
                    "ORDER BY ordinal_position"
                ),
                {"table_name": table},
            ).all()
        )
        table_columns[table] = columns
        required_columns = {
            column
            for privilege_columns in privilege_map.values()
            for column in privilege_columns
        }
        missing_columns = sorted(required_columns - set(columns))
        if missing_columns:
            raise RuntimeError(
                f"Required {table} columns are missing: "
                + _comma_separated(missing_columns)
            )

    for table in table_names:
        db.execute(text(
            f"REVOKE ALL PRIVILEGES ON TABLE {quoted_tables[table]} "
            f"FROM {quoted_role}"
        ))
    for table, privilege_map in COLUMN_PRIVILEGES.items():
        quoted_all_columns = _comma_separated(
            preparer.quote(column) for column in table_columns[table]
        )
        for privilege in privilege_map:
            db.execute(text(
                f"REVOKE {privilege} ({quoted_all_columns}) "
                f"ON TABLE {quoted_tables[table]} FROM {quoted_role}"
            ))
    for table, privileges in TABLE_PRIVILEGES.items():
        db.execute(text(
            f"GRANT {_comma_separated(privileges)} "
            f"ON TABLE {quoted_tables[table]} TO {quoted_role}"
        ))
    for table, privilege_map in COLUMN_PRIVILEGES.items():
        for privilege, columns in privilege_map.items():
            quoted_columns = _comma_separated(
                preparer.quote(column) for column in columns
            )
            db.execute(text(
                f"GRANT {privilege} ({quoted_columns}) "
                f"ON TABLE {quoted_tables[table]} TO {quoted_role}"
            ))

    checks = [
        db.execute(
            text("SELECT has_database_privilege(:role, current_database(), 'CONNECT')"),
            {"role": normalized},
        ).scalar_one(),
        db.execute(
            text("SELECT has_schema_privilege(:role, 'public', 'USAGE')"),
            {"role": normalized},
        ).scalar_one(),
    ]
    for table, privileges in TABLE_PRIVILEGES.items():
        for privilege in privileges:
            checks.append(db.execute(
                text(
                    "SELECT has_table_privilege("
                    ":role, :table_name, :privilege"
                    ")"
                ),
                {
                    "role": normalized,
                    "table_name": table,
                    "privilege": privilege,
                },
            ).scalar_one())
    unexpected_column_privileges: list[str] = []
    for table, privilege_map in COLUMN_PRIVILEGES.items():
        for privilege, columns in privilege_map.items():
            has_table_privilege = db.execute(
                text(
                    "SELECT has_table_privilege("
                    ":role, :table_name, :privilege"
                    ")"
                ),
                {
                    "role": normalized,
                    "table_name": table,
                    "privilege": privilege,
                },
            ).scalar_one()
            if has_table_privilege:
                unexpected_column_privileges.append(
                    f"{table} table-wide {privilege}"
                )
            for column in columns:
                checks.append(db.execute(
                    text(
                        "SELECT has_column_privilege("
                        ":role, :table_name, :column_name, :privilege"
                        ")"
                    ),
                    {
                        "role": normalized,
                        "table_name": table,
                        "column_name": column,
                        "privilege": privilege,
                    },
                ).scalar_one())
            unexpected_column_privileges.extend(
                f"{table}.{column} {privilege}"
                for column in table_columns[table]
                if column not in columns
                and db.execute(
                    text(
                        "SELECT has_column_privilege("
                        ":role, :table_name, :column_name, :privilege"
                        ")"
                    ),
                    {
                        "role": normalized,
                        "table_name": table,
                        "column_name": column,
                        "privilege": privilege,
                    },
                ).scalar_one()
            )
    if not all(bool(check) for check in checks):
        db.rollback()
        raise RuntimeError("Labs worker database grants are incomplete")
    if unexpected_column_privileges:
        db.rollback()
        raise RuntimeError(
            "Labs worker has unexpected column privileges: "
            + _comma_separated(sorted(unexpected_column_privileges))
        )
    db.commit()


def main() -> int:
    """Provision the worker grants from the backend schema-owner runtime."""
    from db import session as db_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-name", required=True)
    args = parser.parse_args()
    os.environ.setdefault("PRAXYS_SKIP_MIGRATIONS", "true")
    db_session.init_db()
    with db_session.SessionLocal() as db:
        provision_labs_worker_grants(db, args.identity_name)
    print("Labs worker database grants verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
