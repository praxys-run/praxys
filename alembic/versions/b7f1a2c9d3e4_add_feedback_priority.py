"""add feedback.priority

Revision ID: b7f1a2c9d3e4
Revises: 4507a109335c
Create Date: 2026-07-04 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f1a2c9d3e4"
down_revision: Union[str, Sequence[str], None] = "4507a109335c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # LLM-suggested triage priority (low|medium|high|critical); nullable so
    # existing rows and rule-based/no-LLM triage keep a NULL priority.
    op.add_column("feedback", sa.Column("priority", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("feedback", "priority")