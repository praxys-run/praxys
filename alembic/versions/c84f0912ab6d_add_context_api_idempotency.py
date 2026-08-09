"""add personal-context API idempotency

Revision ID: c84f0912ab6d
Revises: b2c3d4e5f6a7
Create Date: 2026-08-09

Adds owner-scoped idempotency keys to context versions and consent receipts.
The keys are opaque command identifiers and never contain context payloads.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c84f0912ab6d"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("personal_context_items") as batch_op:
        batch_op.add_column(
            sa.Column("idempotency_key", sa.String(length=128), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_personal_context_item_idempotency",
            ["user_id", "idempotency_key"],
        )

    with op.batch_alter_table(
        "personal_context_consent_receipts"
    ) as batch_op:
        batch_op.add_column(
            sa.Column("idempotency_key", sa.String(length=128), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_personal_context_consent_idempotency",
            ["user_id", "idempotency_key"],
        )

    op.create_table(
        "personal_context_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("target_item_id", sa.String(length=36), nullable=True),
        sa.Column("lineage_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "operation IN ('confirm','correct','ai_consent')",
            name="ck_personal_context_command_operation",
        ),
        sa.CheckConstraint(
            "status IN ('active','retired')",
            name="ck_personal_context_command_status",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND target_item_id IS NOT NULL "
            "AND lineage_id IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'retired' AND target_item_id IS NULL "
            "AND lineage_id IS NULL AND retired_at IS NOT NULL)",
            name="ck_personal_context_command_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_personal_context_command_idempotency",
        ),
    )
    op.create_index(
        "ix_personal_context_commands_user_id",
        "personal_context_commands",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_command_user_status",
        "personal_context_commands",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_personal_context_command_user_status",
        table_name="personal_context_commands",
    )
    op.drop_index(
        "ix_personal_context_commands_user_id",
        table_name="personal_context_commands",
    )
    op.drop_table("personal_context_commands")

    with op.batch_alter_table(
        "personal_context_consent_receipts"
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_personal_context_consent_idempotency",
            type_="unique",
        )
        batch_op.drop_column("idempotency_key")

    with op.batch_alter_table("personal_context_items") as batch_op:
        batch_op.drop_constraint(
            "uq_personal_context_item_idempotency",
            type_="unique",
        )
        batch_op.drop_column("idempotency_key")
