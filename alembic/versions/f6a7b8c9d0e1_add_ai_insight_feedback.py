"""add durable AI insight feedback

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-12

Stores one Coach vote per user, insight type, and generated dataset so
idempotency survives later insight regeneration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_insight_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("insight_type", sa.String(length=30), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("vote", sa.String(length=4), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "vote IN ('up', 'down')",
            name="ck_ai_insight_feedback_vote",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "insight_type",
            "dataset_hash",
            name="uq_ai_insight_feedback_dataset",
        ),
    )
    op.create_index(
        op.f("ix_ai_insight_feedback_user_id"),
        "ai_insight_feedback",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ai_insight_feedback_user_id"),
        table_name="ai_insight_feedback",
    )
    op.drop_table("ai_insight_feedback")
