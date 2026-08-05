"""add encrypted Garmin OAuth token storage

Revision ID: 7a8192b3c4d5
Revises: 6f708192a3b4
Create Date: 2026-08-05
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a8192b3c4d5"
down_revision: Union[str, Sequence[str], None] = "6f708192a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_connections",
        sa.Column("encrypted_garmin_tokens", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "user_connections",
        sa.Column("wrapped_token_dek", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "user_connections",
        sa.Column("garmin_token_generation", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "user_connections",
        sa.Column("tokens_updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_connections", "tokens_updated_at")
    op.drop_column("user_connections", "garmin_token_generation")
    op.drop_column("user_connections", "wrapped_token_dek")
    op.drop_column("user_connections", "encrypted_garmin_tokens")
