"""add durable external account-deletion cleanup obligations

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_deletion_cleanup_obligations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("cleanup_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(user_id) BETWEEN 1 AND 36 "
            "AND user_id NOT LIKE '%/%' "
            "AND user_id NOT IN ('.','..')",
            name="ck_account_deletion_cleanup_obligation_user_id",
        ),
        sa.CheckConstraint(
            "cleanup_kind IN ('garmin_tokens','legacy_plan_status')",
            name="ck_account_deletion_cleanup_obligation_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending','completed')",
            name="ck_account_deletion_cleanup_obligation_status",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND completed_at IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL)",
            name="ck_account_deletion_cleanup_obligation_completion",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= requested_at",
            name="ck_account_deletion_cleanup_obligation_order",
        ),
    )
    op.create_index(
        "ix_account_deletion_cleanup_obligation_status",
        "account_deletion_cleanup_obligations",
        ["status"],
    )
    op.create_index(
        "ix_account_deletion_cleanup_obligation_user_status",
        "account_deletion_cleanup_obligations",
        ["user_id", "status"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER "
            "trg_account_deletion_cleanup_obligations_no_delete "
            "BEFORE DELETE ON account_deletion_cleanup_obligations "
            "BEGIN SELECT RAISE(ABORT, "
            "'account deletion cleanup obligations cannot be deleted'); END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_account_deletion_cleanup_obligations_immutable "
            "BEFORE UPDATE ON account_deletion_cleanup_obligations "
            "WHEN NOT ((OLD.status = 'pending' AND NEW.status = 'completed' "
            "AND NEW.id = OLD.id "
            "AND NEW.user_id = OLD.user_id "
            "AND NEW.cleanup_kind = OLD.cleanup_kind "
            "AND NEW.requested_at = OLD.requested_at "
            "AND NEW.completed_at IS NOT NULL "
            "AND NEW.completed_at >= OLD.requested_at) "
            "OR (OLD.status = 'completed' AND NEW.status = 'completed' "
            "AND NEW.id = OLD.id "
            "AND NEW.user_id = OLD.user_id "
            "AND NEW.cleanup_kind = OLD.cleanup_kind "
            "AND NEW.requested_at = OLD.requested_at "
            "AND NEW.completed_at = OLD.completed_at)) "
            "BEGIN SELECT RAISE(ABORT, "
            "'account deletion cleanup obligation immutable'); END"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION account_deletion_cleanup_obligations_immutable() "
            "RETURNS trigger AS $$ BEGIN "
            "IF TG_OP = 'DELETE' THEN "
            "RAISE EXCEPTION 'account deletion cleanup obligations cannot be deleted'; "
            "END IF; "
            "IF (OLD.status = 'pending' AND NEW.status = 'completed' "
            "AND NEW.id IS NOT DISTINCT FROM OLD.id "
            "AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id "
            "AND NEW.cleanup_kind IS NOT DISTINCT FROM OLD.cleanup_kind "
            "AND NEW.requested_at IS NOT DISTINCT FROM OLD.requested_at "
            "AND NEW.completed_at IS NOT NULL "
            "AND NEW.completed_at >= OLD.requested_at) "
            "OR (OLD.status = 'completed' AND NEW.status = 'completed' "
            "AND NEW.id IS NOT DISTINCT FROM OLD.id "
            "AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id "
            "AND NEW.cleanup_kind IS NOT DISTINCT FROM OLD.cleanup_kind "
            "AND NEW.requested_at IS NOT DISTINCT FROM OLD.requested_at "
            "AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at) "
            "THEN RETURN NEW; END IF; "
            "RAISE EXCEPTION 'account deletion cleanup obligation immutable'; "
            "END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_account_deletion_cleanup_obligations_immutable "
            "BEFORE UPDATE OR DELETE ON account_deletion_cleanup_obligations "
            "FOR EACH ROW EXECUTE FUNCTION "
            "account_deletion_cleanup_obligations_immutable()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    count = bind.execute(
        sa.text(
            "SELECT count(*) FROM account_deletion_cleanup_obligations"
        )
    ).scalar_one()
    if count:
        raise RuntimeError(
            "Cannot downgrade account deletion cleanup obligations after "
            "durable cleanup data exists"
        )

    if bind.dialect.name == "sqlite":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_account_deletion_cleanup_obligations_no_delete"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_account_deletion_cleanup_obligations_immutable"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_account_deletion_cleanup_obligations_immutable "
            "ON account_deletion_cleanup_obligations"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS "
            "account_deletion_cleanup_obligations_immutable()"
        )
    op.drop_index(
        "ix_account_deletion_cleanup_obligation_user_status",
        table_name="account_deletion_cleanup_obligations",
    )
    op.drop_index(
        "ix_account_deletion_cleanup_obligation_status",
        table_name="account_deletion_cleanup_obligations",
    )
    op.drop_table("account_deletion_cleanup_obligations")
