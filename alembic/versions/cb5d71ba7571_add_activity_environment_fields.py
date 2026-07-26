"""add activity environment fields

Revision ID: cb5d71ba7571
Revises: f6a7b8c9d0e1
Create Date: 2026-07-21 12:04:45.283845

Persists a coherent connector-provided activity temperature/relative-humidity
pair and its source for the qualitative heat-adaptation tracker. Split power
also records its provider so workload can be compared only with a compatible
critical-power baseline. Existing rows remain nullable and are filled on a
later connector re-sync.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cb5d71ba7571"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("temperature_c", sa.Float(), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("relative_humidity_pct", sa.Float(), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("environment_source", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "activity_splits",
        sa.Column("power_source", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "fitness_data",
        sa.Column("power_source", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fitness_data", "power_source")
    op.drop_column("activity_splits", "power_source")
    op.drop_column("activities", "environment_source")
    op.drop_column("activities", "relative_humidity_pct")
    op.drop_column("activities", "temperature_c")