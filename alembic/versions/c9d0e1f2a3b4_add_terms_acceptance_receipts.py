"""add terms acceptance receipts

Revision ID: c9d0e1f2a3b4
Revises: b8d4e6f7a9c1
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8d4e6f7a9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("terms_digest", sa.String(length=71), nullable=True)
        )

    op.create_table(
        "terms_acceptance_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("terms_version", sa.String(length=20), nullable=False),
        sa.Column("terms_digest", sa.String(length=71), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("client_version", sa.String(length=80), nullable=True),
        sa.Column("source_sha", sa.String(length=64), nullable=True),
        sa.Column("notice_version", sa.String(length=20), nullable=True),
        sa.Column("release_id", sa.String(length=128), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action = 'accept_terms_and_acknowledge_privacy'",
            name="ck_terms_receipt_action",
        ),
        sa.CheckConstraint(
            "terms_digest LIKE 'sha256:%'",
            name="ck_terms_receipt_digest",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_terms_acceptance_receipts_user_id"),
        "terms_acceptance_receipts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_terms_receipt_user_accepted",
        "terms_acceptance_receipts",
        ["user_id", "accepted_at"],
        unique=False,
    )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER trg_terms_acceptance_receipts_immutable "
            "BEFORE UPDATE ON terms_acceptance_receipts "
            "BEGIN "
            "SELECT RAISE(ABORT, 'terms acceptance receipts are immutable'); "
            "END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION terms_acceptance_receipts_immutable() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "RAISE EXCEPTION 'terms acceptance receipts are immutable'; "
            "END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER trg_terms_acceptance_receipts_immutable "
            "BEFORE UPDATE ON terms_acceptance_receipts "
            "FOR EACH ROW EXECUTE FUNCTION "
            "terms_acceptance_receipts_immutable()"
        )


def downgrade() -> None:
    receipt_count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM terms_acceptance_receipts")
    ).scalar_one()
    if receipt_count:
        raise RuntimeError(
            "Cannot downgrade while Terms acceptance receipts exist; "
            "preserve the ledger and deploy a forward application fix."
        )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_terms_acceptance_receipts_immutable"
        )
    elif dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_terms_acceptance_receipts_immutable "
            "ON terms_acceptance_receipts"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS terms_acceptance_receipts_immutable()"
        )

    op.drop_index(
        "ix_terms_receipt_user_accepted",
        table_name="terms_acceptance_receipts",
    )
    op.drop_index(
        op.f("ix_terms_acceptance_receipts_user_id"),
        table_name="terms_acceptance_receipts",
    )
    op.drop_table("terms_acceptance_receipts")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("terms_digest")
