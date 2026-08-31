"""grant isolated worker access to shared channel authority

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WORKER_ROLE = "id-praxys-labs-worker"


def _postgres_role_exists() -> bool:
    bind = op.get_bind()
    return bool(bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_roles "
            "WHERE rolname = :role)"
        ),
        {"role": _WORKER_ROLE},
    ).scalar_one())


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _postgres_role_exists():
        return
    preparer = bind.dialect.identifier_preparer
    role = preparer.quote(_WORKER_ROLE)
    statements = (
        "GRANT SELECT (key, value) ON TABLE app_config",
        "GRANT SELECT (terms_version, terms_digest) ON TABLE users",
        "GRANT SELECT (user_id, terms_version, terms_digest, channel) "
        "ON TABLE terms_acceptance_receipts",
        "GRANT SELECT ON TABLE labs_analysis_outbox",
        "GRANT UPDATE (status, lease_expires_at, last_error_code, updated_at) "
        "ON TABLE labs_analysis_outbox",
    )
    for statement in statements:
        op.execute(f"{statement} TO {role}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _postgres_role_exists():
        return
    preparer = bind.dialect.identifier_preparer
    role = preparer.quote(_WORKER_ROLE)
    statements = (
        "REVOKE SELECT (key, value) ON TABLE app_config",
        "REVOKE SELECT (terms_version, terms_digest) ON TABLE users",
        "REVOKE SELECT (user_id, terms_version, terms_digest, channel) "
        "ON TABLE terms_acceptance_receipts",
        "REVOKE SELECT ON TABLE labs_analysis_outbox",
        "REVOKE UPDATE (status, lease_expires_at, last_error_code, updated_at) "
        "ON TABLE labs_analysis_outbox",
    )
    for statement in statements:
        op.execute(f"{statement} FROM {role}")
