"""add durable Labs analysis jobs and transactional outbox

Revision ID: d95e6f7a8b9c
Revises: c84f0912ab6d
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d95e6f7a8b9c"
down_revision: Union[str, Sequence[str], None] = "c84f0912ab6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTIVE_JOB_PREDICATE = (
    "status IN ('queued','dispatched','processing','retrying')"
)


def upgrade() -> None:
    op.create_table(
        "labs_analysis_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=80), nullable=False),
        sa.Column("trigger", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("source_revision", sa.String(length=100), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("retryable_failure", sa.Boolean(), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "trigger IN ('enrollment','manual_recompute')",
            name="ck_labs_analysis_job_trigger",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'queued','dispatched','processing','retrying',"
            "'succeeded','failed','cancelled','dead_lettered'"
            ")",
            name="ck_labs_analysis_job_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "experiment_id",
            "trigger",
            "idempotency_key",
            name="uq_labs_analysis_job_idempotency",
        ),
    )
    op.create_index(
        "ix_labs_analysis_jobs_user_id",
        "labs_analysis_jobs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_labs_analysis_job_requested",
        "labs_analysis_jobs",
        ["user_id", "experiment_id", "requested_at"],
        unique=False,
    )
    op.create_index(
        "uq_labs_analysis_job_active",
        "labs_analysis_jobs",
        ["user_id", "experiment_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_JOB_PREDICATE),
        sqlite_where=sa.text(_ACTIVE_JOB_PREDICATE),
    )

    op.create_table(
        "labs_analysis_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','dispatching','dispatched','cancelled')",
            name="ck_labs_analysis_outbox_status",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["labs_analysis_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        "ix_labs_analysis_outbox_dispatch",
        "labs_analysis_outbox",
        ["status", "available_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_labs_analysis_outbox_dispatch",
        table_name="labs_analysis_outbox",
    )
    op.drop_table("labs_analysis_outbox")
    op.drop_index(
        "uq_labs_analysis_job_active",
        table_name="labs_analysis_jobs",
    )
    op.drop_index(
        "ix_labs_analysis_job_requested",
        table_name="labs_analysis_jobs",
    )
    op.drop_index(
        "ix_labs_analysis_jobs_user_id",
        table_name="labs_analysis_jobs",
    )
    op.drop_table("labs_analysis_jobs")
