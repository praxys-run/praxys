"""add Today Decision Check cadence columns to user_config

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-12

Persists the Today Decision Check cadence across web, miniapp, devices, and
backend workers. SQLite dev/test DBs get the column via
Base.metadata.create_all; Postgres (prod) needs this migration under
`alembic upgrade head`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_config",
        sa.Column("today_decision_check_claimed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "user_config",
        sa.Column("today_decision_check_shown_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "user_config",
        sa.Column("today_decision_check_submitted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_config", "today_decision_check_submitted_at")
    op.drop_column("user_config", "today_decision_check_shown_at")
    op.drop_column("user_config", "today_decision_check_claimed_at")