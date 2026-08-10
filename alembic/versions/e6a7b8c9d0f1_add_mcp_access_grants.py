"""add server-authoritative MCP access grants

Revision ID: e6a7b8c9d0f1
Revises: d95e6f7a8b9c
Create Date: 2026-08-10

Stores only hashed opaque credentials and payload-free, short-lived approval
metadata. Personal-context values and narrative never enter these tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6a7b8c9d0f1"
down_revision: Union[str, Sequence[str], None] = "d95e6f7a8b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_access_handoffs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("state_digest", sa.String(length=64), nullable=False),
        sa.Column("exchange_digest", sa.String(length=64), nullable=False),
        sa.Column("request_type", sa.String(length=16), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("requested_scopes", sa.JSON(), nullable=False),
        sa.Column("requested_purposes", sa.JSON(), nullable=False),
        sa.Column("requested_kinds", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("exchanged_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "request_type IN ('session','context')",
            name="ck_mcp_access_handoff_request_type",
        ),
        sa.CheckConstraint(
            "audience = 'praxys-coach-plugin'",
            name="ck_mcp_access_handoff_audience",
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','denied','exchanged')",
            name="ck_mcp_access_handoff_status",
        ),
        sa.CheckConstraint(
            "request_type = 'session' OR user_id IS NOT NULL",
            name="ck_mcp_access_handoff_context_owner",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_digest"),
        sa.UniqueConstraint("state_digest"),
    )
    op.create_index(
        "ix_mcp_access_handoffs_user_id",
        "mcp_access_handoffs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_mcp_access_handoff_expiry",
        "mcp_access_handoffs",
        ["status", "expires_at"],
        unique=False,
    )

    op.create_table(
        "mcp_access_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("token_type", sa.String(length=16), nullable=False),
        sa.Column("audience", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("purposes", sa.JSON(), nullable=False),
        sa.Column("kinds", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("write_consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "token_type IN ('session','context')",
            name="ck_mcp_access_token_type",
        ),
        sa.CheckConstraint(
            "audience = 'praxys-coach-plugin'",
            name="ck_mcp_access_token_audience",
        ),
        sa.CheckConstraint(
            "actor_type = 'mcp'",
            name="ck_mcp_access_token_actor_type",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(
        "ix_mcp_access_tokens_user_id",
        "mcp_access_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_mcp_access_token_owner_status",
        "mcp_access_tokens",
        ["user_id", "token_type", "expires_at", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mcp_access_token_owner_status",
        table_name="mcp_access_tokens",
    )
    op.drop_index(
        "ix_mcp_access_tokens_user_id",
        table_name="mcp_access_tokens",
    )
    op.drop_table("mcp_access_tokens")

    op.drop_index(
        "ix_mcp_access_handoff_expiry",
        table_name="mcp_access_handoffs",
    )
    op.drop_index(
        "ix_mcp_access_handoffs_user_id",
        table_name="mcp_access_handoffs",
    )
    op.drop_table("mcp_access_handoffs")
