"""add feedback publication consent

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.add_column(
            sa.Column(
                "publication_consent_version",
                sa.String(length=64),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "publication_consented_at",
                sa.DateTime(),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.drop_column("publication_consented_at")
        batch_op.drop_column("publication_consent_version")
