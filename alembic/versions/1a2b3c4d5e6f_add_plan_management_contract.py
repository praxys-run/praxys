"""add managed-plan ownership contract

Revision ID: 1a2b3c4d5e6f
Revises: a7b8c9d0e1f2
Create Date: 2026-07-27

Adds an explicit plan ownership/delivery-intent document without enabling
external writes. Existing rows remain nullable and are normalized from legacy
preferences by the application read path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_config",
        sa.Column("plan_management", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_config", "plan_management")
