"""add inactive Road 10K owner opt-in receipts

Revision ID: c1d2e3f4a5b6
Revises: b8d4e6f7a9c1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b8d4e6f7a9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "road_10k_owner_opt_in_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("capability_id", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("consent_text_version", sa.String(length=80), nullable=False),
        sa.Column("client", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_road_10k_owner_opt_in_idempotency",
        ),
        sa.CheckConstraint(
            "capability_id = 'outdoor_road_10k_performance_v1'",
            name="ck_road_10k_owner_opt_in_capability",
        ),
        sa.CheckConstraint(
            "schema_version = 'road-10k-owner-opt-in-v1'",
            name="ck_road_10k_owner_opt_in_schema",
        ),
        sa.CheckConstraint(
            "policy_version = 'road-10k-plan-generation-policy-v2'",
            name="ck_road_10k_owner_opt_in_policy",
        ),
        sa.CheckConstraint(
            "decision IN ('granted','withdrawn')",
            name="ck_road_10k_owner_opt_in_decision",
        ),
        sa.CheckConstraint(
            "client IN ('web','miniapp')",
            name="ck_road_10k_owner_opt_in_client",
        ),
    )
    op.create_index(
        "ix_road_10k_owner_opt_in_user_decided",
        "road_10k_owner_opt_in_receipts",
        ["user_id", "decided_at", "id"],
        unique=False,
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_owner_opt_in_receipts_immutable "
            "BEFORE UPDATE ON road_10k_owner_opt_in_receipts "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K opt-in receipts are immutable'); "
            "END"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION road_10k_owner_opt_in_receipts_immutable() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "RAISE EXCEPTION 'road 10K opt-in receipts are immutable'; "
            "END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_owner_opt_in_receipts_immutable "
            "BEFORE UPDATE ON road_10k_owner_opt_in_receipts "
            "FOR EACH ROW EXECUTE FUNCTION "
            "road_10k_owner_opt_in_receipts_immutable()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_owner_opt_in_receipts_immutable"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_owner_opt_in_receipts_immutable "
            "ON road_10k_owner_opt_in_receipts"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_owner_opt_in_receipts_immutable()"
        )
    op.drop_index(
        "ix_road_10k_owner_opt_in_user_decided",
        table_name="road_10k_owner_opt_in_receipts",
    )
    op.drop_table("road_10k_owner_opt_in_receipts")
