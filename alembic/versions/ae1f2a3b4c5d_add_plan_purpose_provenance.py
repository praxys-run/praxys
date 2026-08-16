"""add plan purpose provenance

Revision ID: ae1f2a3b4c5d
Revises: 9d0e1f2a3b4c
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ae1f2a3b4c5d"
down_revision: Union[str, Sequence[str], None] = "9d0e1f2a3b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "adaptive_plan_goal_snapshots",
        sa.Column("purpose_source", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "adaptive_plan_goal_snapshots",
        sa.Column("source_goal_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "adaptive_plan_goal_snapshots",
        sa.Column("source_goal_revision", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "goal_baseline_test_records",
        sa.Column("purpose_source", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "goal_baseline_test_records",
        sa.Column("source_goal_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "goal_baseline_test_records",
        sa.Column("source_goal_revision", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(
        "goal_baseline_test_records",
        "source_goal_revision",
    )
    op.drop_column("goal_baseline_test_records", "source_goal_id")
    op.drop_column("goal_baseline_test_records", "purpose_source")
    op.drop_column(
        "adaptive_plan_goal_snapshots",
        "source_goal_revision",
    )
    op.drop_column("adaptive_plan_goal_snapshots", "source_goal_id")
    op.drop_column("adaptive_plan_goal_snapshots", "purpose_source")
