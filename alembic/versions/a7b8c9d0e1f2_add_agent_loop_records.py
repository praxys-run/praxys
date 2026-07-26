"""add shared agent decision and outcome records

Revision ID: a7b8c9d0e1f2
Revises: cb5d71ba7571
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "cb5d71ba7571"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("loop", sa.String(length=30), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_ref", sa.String(length=120), nullable=False),
        sa.Column("policy_name", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_decisions_input_sha256",
        "agent_decisions",
        ["input_sha256"],
        unique=False,
    )
    op.create_index(
        "ix_agent_decisions_loop_created",
        "agent_decisions",
        ["loop", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_decisions_subject",
        "agent_decisions",
        ["subject_type", "subject_ref", "created_at"],
        unique=False,
    )

    op.create_table(
        "agent_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("outcome_type", sa.String(length=60), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["agent_decisions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_id",
            "fingerprint",
            name="uq_agent_outcomes_decision_fingerprint",
        ),
    )
    op.create_index(
        "ix_agent_outcomes_decision_id",
        "agent_outcomes",
        ["decision_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_outcomes_type_observed",
        "agent_outcomes",
        ["outcome_type", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_outcomes_type_observed", table_name="agent_outcomes")
    op.drop_index("ix_agent_outcomes_decision_id", table_name="agent_outcomes")
    op.drop_table("agent_outcomes")
    op.drop_index("ix_agent_decisions_subject", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_loop_created", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_input_sha256", table_name="agent_decisions")
    op.drop_table("agent_decisions")
