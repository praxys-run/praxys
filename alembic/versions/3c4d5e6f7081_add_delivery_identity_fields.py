"""add delivery plan and provider account identity

Revision ID: 3c4d5e6f7081
Revises: 2b3c4d5e6f70
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c4d5e6f7081"
down_revision: Union[str, Sequence[str], None] = "2b3c4d5e6f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plan_deliveries",
        sa.Column("plan_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "plan_deliveries",
        sa.Column(
            "provider_account_id",
            sa.String(length=200),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE plan_deliveries "
            "SET plan_version = workout_version "
            "WHERE plan_version IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("plan_deliveries", "provider_account_id")
    op.drop_column("plan_deliveries", "plan_version")
