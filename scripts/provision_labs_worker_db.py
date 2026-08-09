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

from api.labs_worker_permissions import (
    COLUMN_PRIVILEGES,
    TABLE_PRIVILEGES,
    required_tables,
    verify_labs_worker_grants,
)


def _comma_separated(values: Iterable[str]) -> str:
    return ", ".join(values)


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

    table_names = required_tables()
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

    try:
        verify_labs_worker_grants(db, normalized)
    except RuntimeError:
        db.rollback()
        raise
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
