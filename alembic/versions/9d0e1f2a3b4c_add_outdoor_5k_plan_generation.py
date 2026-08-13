"""add deterministic outdoor 5K generation audit

Revision ID: 9d0e1f2a3b4c
Revises: 8c9d0e1f2a3b
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d0e1f2a3b4c"
down_revision: Union[str, Sequence[str], None] = "8c9d0e1f2a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plan_proposals",
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "outdoor_5k_plan_generations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("proposal_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("generator_version", sa.String(length=80), nullable=False),
        sa.Column("science_decision_id", sa.String(length=120), nullable=False),
        sa.Column("evidence_review_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_claim_ids", sa.JSON(), nullable=False),
        sa.Column(
            "ai_explanation_present",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("baseline_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("source_revision", sa.String(length=64), nullable=False),
        sa.Column("deterministic_input_hash", sa.String(length=64), nullable=False),
        sa.Column("request_kind", sa.String(length=20), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("predecessor_proposal_id", sa.String(length=36), nullable=True),
        sa.Column("predecessor_version", sa.Integer(), nullable=True),
        sa.Column("observed_input_snapshot", sa.JSON(), nullable=False),
        sa.Column("constraint_snapshot", sa.JSON(), nullable=False),
        sa.Column("derived_history_statistics", sa.JSON(), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["plan_proposals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "proposal_id",
            name="uq_outdoor_5k_generation_proposal_owner",
        ),
    )
    op.create_index(
        op.f("ix_outdoor_5k_plan_generations_user_id"),
        "outdoor_5k_plan_generations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outdoor_5k_plan_generations_proposal_id"),
        "outdoor_5k_plan_generations",
        ["proposal_id"],
        unique=True,
    )
    op.create_index(
        "ix_outdoor_5k_generation_user_revision",
        "outdoor_5k_plan_generations",
        ["user_id", "source_revision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outdoor_5k_generation_user_revision",
        table_name="outdoor_5k_plan_generations",
    )
    op.drop_index(
        op.f("ix_outdoor_5k_plan_generations_proposal_id"),
        table_name="outdoor_5k_plan_generations",
    )
    op.drop_index(
        op.f("ix_outdoor_5k_plan_generations_user_id"),
        table_name="outdoor_5k_plan_generations",
    )
    op.drop_table("outdoor_5k_plan_generations")
    op.drop_column("plan_proposals", "idempotency_fingerprint")
