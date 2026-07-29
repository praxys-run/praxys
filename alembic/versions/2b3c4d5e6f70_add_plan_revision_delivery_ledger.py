"""add plan revision and delivery ledger

Revision ID: 2b3c4d5e6f70
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b3c4d5e6f70"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("origin", sa.String(length=80), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_plan_revision_user_idempotency",
        ),
    )
    op.create_index(
        "ix_plan_revisions_user_id",
        "plan_revisions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_plan_revisions_user_created",
        "plan_revisions",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "plan_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_key", sa.String(length=120), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("workout_version", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending','delivering','synced','conflict','failed','removed')",
            name="ck_plan_deliveries_state",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "target",
            "canonical_key",
            "workout_version",
            name="uq_plan_delivery_version_target",
        ),
    )
    op.create_index(
        "ix_plan_deliveries_user_id",
        "plan_deliveries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_plan_deliveries_user_target_date",
        "plan_deliveries",
        ["user_id", "target", "workout_date"],
        unique=False,
    )
    op.create_index(
        "ix_plan_deliveries_user_target_external",
        "plan_deliveries",
        ["user_id", "target", "external_id"],
        unique=False,
    )

    op.create_table(
        "plan_delivery_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("delivery_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending','delivering','synced','conflict','failed','removed')",
            name="ck_plan_delivery_attempts_state",
        ),
        sa.CheckConstraint(
            "operation IN ('deliver','remove','import')",
            name="ck_plan_delivery_attempts_operation",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["plan_deliveries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_plan_delivery_attempt_number",
        ),
    )
    op.create_index(
        "ix_plan_delivery_attempts_delivery_id",
        "plan_delivery_attempts",
        ["delivery_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plan_delivery_attempts_delivery_id",
        table_name="plan_delivery_attempts",
    )
    op.drop_table("plan_delivery_attempts")
    op.drop_index(
        "ix_plan_deliveries_user_target_external",
        table_name="plan_deliveries",
    )
    op.drop_index(
        "ix_plan_deliveries_user_target_date",
        table_name="plan_deliveries",
    )
    op.drop_index("ix_plan_deliveries_user_id", table_name="plan_deliveries")
    op.drop_table("plan_deliveries")
    op.drop_index("ix_plan_revisions_user_created", table_name="plan_revisions")
    op.drop_index("ix_plan_revisions_user_id", table_name="plan_revisions")
    op.drop_table("plan_revisions")
