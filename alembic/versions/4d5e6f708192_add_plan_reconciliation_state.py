"""add plan reconciliation state

Revision ID: 4d5e6f708192
Revises: 3c4d5e6f7081
Create Date: 2026-07-30
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.elements import TextClause


revision: str = "4d5e6f708192"
down_revision: Union[str, Sequence[str], None] = "3c4d5e6f7081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _canonical_id_server_default(dialect_name: str) -> TextClause:
    if dialect_name == "postgresql":
        return sa.text("gen_random_uuid()::text")
    if dialect_name == "sqlite":
        return sa.text(
            "("
            "lower(hex(randomblob(4))) || '-' || "
            "lower(hex(randomblob(2))) || '-4' || "
            "substr(lower(hex(randomblob(2))), 2) || '-a' || "
            "substr(lower(hex(randomblob(2))), 2) || '-' || "
            "lower(hex(randomblob(6)))"
            ")"
        )
    raise RuntimeError(f"Unsupported database dialect: {dialect_name}")


def upgrade() -> None:
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    canonical_id_default = _canonical_id_server_default(dialect_name)
    op.add_column(
        "training_plans",
        sa.Column(
            "canonical_id",
            sa.String(length=36),
            nullable=True,
            server_default=(
                canonical_id_default
                if dialect_name != "sqlite"
                else None
            ),
        ),
    )
    plan_ids = connection.execute(
        sa.text("SELECT id FROM training_plans WHERE canonical_id IS NULL")
    ).scalars().all()
    for plan_id in plan_ids:
        connection.execute(
            sa.text(
                "UPDATE training_plans "
                "SET canonical_id = :canonical_id WHERE id = :plan_id"
            ),
            {"canonical_id": str(uuid4()), "plan_id": plan_id},
        )
    with op.batch_alter_table(
        "training_plans",
        naming_convention={
            "uq": "uq_%(table_name)s_%(column_0_name)s",
        },
    ) as batch_op:
        batch_op.alter_column(
            "canonical_id",
            existing_type=sa.String(length=36),
            nullable=False,
            server_default=canonical_id_default,
        )
        batch_op.drop_constraint(
            "uq_user_date_plan",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_training_plan_user_canonical",
            ["user_id", "canonical_id"],
        )

    op.add_column(
        "plan_deliveries",
        sa.Column(
            "provider_content_version",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.create_table(
        "plan_target_calendar_syncs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=200), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "target",
            name="uq_plan_target_calendar_sync",
        ),
    )
    op.create_index(
        "ix_plan_target_calendar_syncs_user_id",
        "plan_target_calendar_syncs",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "plan_target_workouts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=200), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("workout_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("normalized_workout", sa.JSON(), nullable=False),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "target",
            "provider_account_id",
            "external_id",
            name="uq_plan_target_workout_external",
        ),
    )
    op.create_index(
        "ix_plan_target_workouts_user_id",
        "plan_target_workouts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_plan_target_workouts_user_target_date",
        "plan_target_workouts",
        ["user_id", "target", "provider_account_id", "workout_date"],
        unique=False,
    )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate_slot = connection.execute(
        sa.text(
            "SELECT user_id, date, source, workout_type "
            "FROM training_plans "
            "GROUP BY user_id, date, source, workout_type "
            "HAVING COUNT(*) > 1 "
            "LIMIT 1"
        )
    ).first()
    if duplicate_slot is not None:
        raise RuntimeError(
            "Cannot downgrade plan reconciliation while multiple workouts "
            "share a user/date/source/type slot; consolidate them first."
        )
    op.drop_index(
        "ix_plan_target_workouts_user_target_date",
        table_name="plan_target_workouts",
    )
    op.drop_index(
        "ix_plan_target_workouts_user_id",
        table_name="plan_target_workouts",
    )
    op.drop_table("plan_target_workouts")
    op.drop_index(
        "ix_plan_target_calendar_syncs_user_id",
        table_name="plan_target_calendar_syncs",
    )
    op.drop_table("plan_target_calendar_syncs")
    op.drop_column("plan_deliveries", "provider_content_version")
    with op.batch_alter_table(
        "training_plans",
        naming_convention={
            "uq": "uq_%(table_name)s_%(column_0_name)s",
        },
    ) as batch_op:
        batch_op.drop_constraint(
            "uq_training_plan_user_canonical",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_user_date_plan",
            ["user_id", "date", "source", "workout_type"],
        )
        batch_op.drop_column("canonical_id")
