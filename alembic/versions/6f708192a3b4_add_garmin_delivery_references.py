"""add Garmin delivery references and consent fence

Revision ID: 6f708192a3b4
Revises: 5e6f708192a3
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f708192a3b4"
down_revision: Union[str, Sequence[str], None] = "5e6f708192a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_json_mapping(table_name: str, column_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            column_name,
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )


def upgrade() -> None:
    op.add_column(
        "user_config",
        sa.Column(
            "plan_execution_target",
            sa.String(length=20),
            nullable=True,
        ),
    )
    op.add_column(
        "user_connections",
        sa.Column(
            "plan_delivery_consent",
            sa.String(length=64),
            nullable=True,
        ),
    )
    _add_json_mapping("plan_deliveries", "provider_references")
    _add_json_mapping("plan_target_workouts", "provider_references")
    _add_json_mapping("plan_target_calendar_syncs", "provider_references")


def downgrade() -> None:
    op.drop_column("plan_target_calendar_syncs", "provider_references")
    op.drop_column("plan_target_workouts", "provider_references")
    op.drop_column("plan_deliveries", "provider_references")
    op.drop_column("user_connections", "plan_delivery_consent")
    op.drop_column("user_config", "plan_execution_target")
