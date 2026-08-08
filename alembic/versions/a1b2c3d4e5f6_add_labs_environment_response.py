"""add Labs environmental-response lifecycle

Revision ID: a1b2c3d4e5f6
Revises: 7a8192b3c4d5
Create Date: 2026-08-08

Stores explicit experiment consent, aggregate-only results, and withdrawal
tombstones. Raw activities, samples, dates, routes, and per-activity research
rows are never persisted in these tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7a8192b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "labs_experiment_enrollments",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=80), nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=False),
        sa.Column("consented_at", sa.DateTime(), nullable=False),
        sa.Column("adult_attested_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("source_revision", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("availability_reason", sa.JSON(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','processing','available','unavailable','failed','stale')",
            name="ck_labs_enrollment_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "experiment_id"),
    )
    op.create_table(
        "labs_experiment_results",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("source_revision", sa.String(length=100), nullable=False),
        sa.Column("result_state", sa.String(length=40), nullable=False),
        sa.Column("eligibility_counts", sa.JSON(), nullable=False),
        sa.Column("aggregate_curve_points", sa.JSON(), nullable=False),
        sa.Column("aggregate_uncertainty", sa.JSON(), nullable=False),
        sa.Column("gate_statuses", sa.JSON(), nullable=False),
        sa.Column("prediction_status", sa.String(length=40), nullable=False),
        sa.Column("power_regime", sa.String(length=60), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "experiment_id"),
    )
    op.create_table(
        "labs_deletion_tombstones",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=80), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "experiment_id"),
    )


def downgrade() -> None:
    op.drop_table("labs_deletion_tombstones")
    op.drop_table("labs_experiment_results")
    op.drop_table("labs_experiment_enrollments")
