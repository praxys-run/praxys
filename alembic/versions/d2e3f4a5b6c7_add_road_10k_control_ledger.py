"""add the Road 10K control ledger and deletable evaluation references

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RESULT_CODES = (
    "'eligible_rolling_proposal','eligible_taper_proposal',"
    "'missing_or_stale_direct_baseline','insufficient_recent_history',"
    "'limited_guidance_event_conflict','limited_near_term_guidance',"
    "'safety_stop','adult_scope_or_constraints_unconfirmed',"
    "'contradictory_input','unsupported_intent_distance_surface_or_population',"
    "'no_schedule_within_envelope','validation_failed'"
)


def upgrade() -> None:
    op.create_table(
        "road_10k_stage_counters",
        sa.Column("stage_id", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("capability_id", sa.String(length=80), nullable=False),
        sa.Column(
            "invitation_slots_consumed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "distinct_exposed_owners_consumed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("invitation_ceiling", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("exposure_ceiling", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("aggregate", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("stage_id"),
        sa.CheckConstraint(
            "schema_version = 2",
            name="ck_road_10k_stage_counter_schema",
        ),
        sa.CheckConstraint(
            "capability_id = 'outdoor_road_10k_performance_v1'",
            name="ck_road_10k_stage_counter_capability",
        ),
        sa.CheckConstraint(
            "invitation_slots_consumed >= 0 AND invitation_slots_consumed <= 60",
            name="ck_road_10k_stage_counter_invitations",
        ),
        sa.CheckConstraint(
            "distinct_exposed_owners_consumed >= 0 "
            "AND distinct_exposed_owners_consumed <= 30",
            name="ck_road_10k_stage_counter_exposures",
        ),
        sa.CheckConstraint(
            "invitation_ceiling >= 0 AND invitation_ceiling <= 60 "
            "AND exposure_ceiling >= 0 AND exposure_ceiling <= 30",
            name="ck_road_10k_stage_counter_ceilings",
        ),
    )
    op.create_table(
        "road_10k_owner_stage_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("stage_id", sa.String(length=80), nullable=False),
        sa.Column("capability_id", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("authority_digest", sa.String(length=64), nullable=False),
        sa.Column("notice_digest", sa.String(length=64), nullable=False),
        sa.Column("cohort_rule_digest", sa.String(length=64), nullable=False),
        sa.Column("invitation_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("invitation_issued_at", sa.DateTime(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(), nullable=True),
        sa.Column("first_exposed_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "stage_id",
            name="uq_road_10k_owner_stage_receipt_owner_stage",
        ),
        sa.UniqueConstraint(
            "stage_id",
            "invitation_idempotency_key",
            name="uq_road_10k_owner_stage_receipt_invitation_key",
        ),
        sa.CheckConstraint(
            "capability_id = 'outdoor_road_10k_performance_v1'",
            name="ck_road_10k_owner_stage_receipt_capability",
        ),
        sa.CheckConstraint(
            "schema_version = 2",
            name="ck_road_10k_owner_stage_receipt_schema",
        ),
        sa.CheckConstraint(
            "state IN ('invited_only','enrolled_unexposed','exposed',"
            "'withdrawn','deleted')",
            name="ck_road_10k_owner_stage_receipt_state",
        ),
    )
    op.create_index(
        "ix_road_10k_owner_stage_receipt_user_id",
        "road_10k_owner_stage_receipts",
        ["user_id"],
    )
    op.create_index(
        "ix_road_10k_owner_stage_receipt_stage_id",
        "road_10k_owner_stage_receipts",
        ["stage_id"],
    )
    op.create_index(
        "ix_road_10k_owner_stage_receipt_stage_state",
        "road_10k_owner_stage_receipts",
        ["stage_id", "state"],
    )
    op.create_table(
        "road_10k_exposure_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stage_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("owner_stage_receipt_id", sa.String(length=36), nullable=False),
        sa.Column("authority_digest", sa.String(length=64), nullable=False),
        sa.Column("exposed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["owner_stage_receipt_id"],
            ["road_10k_owner_stage_receipts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stage_id",
            "user_id",
            name="uq_road_10k_exposure_owner_stage",
        ),
        sa.CheckConstraint(
            "length(authority_digest) = 64",
            name="ck_road_10k_exposure_authority_digest",
        ),
    )
    op.create_index(
        "ix_road_10k_exposure_receipts_stage_id",
        "road_10k_exposure_receipts",
        ["stage_id"],
    )
    op.create_index(
        "ix_road_10k_exposure_receipts_user_id",
        "road_10k_exposure_receipts",
        ["user_id"],
    )
    op.create_table(
        "road_10k_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("stage_id", sa.String(length=80), nullable=False),
        sa.Column("result_code", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("deletion_reason", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            f"result_code IN ({RESULT_CODES})",
            name="ck_road_10k_evaluation_result",
        ),
    )
    op.create_index(
        "ix_road_10k_evaluations_user_id",
        "road_10k_evaluations",
        ["user_id"],
    )
    op.create_index(
        "ix_road_10k_evaluations_stage_id",
        "road_10k_evaluations",
        ["stage_id"],
    )
    op.create_table(
        "road_10k_screenshot_references",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("object_key", sa.String(length=240), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["road_10k_evaluations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.CheckConstraint(
            "object_key NOT LIKE '%@%' AND object_key NOT LIKE '%email%'",
            name="ck_road_10k_screenshot_key_private",
        ),
    )
    op.create_index(
        "ix_road_10k_screenshot_references_evaluation_id",
        "road_10k_screenshot_references",
        ["evaluation_id"],
    )
    op.create_index(
        "ix_road_10k_screenshot_references_user_id",
        "road_10k_screenshot_references",
        ["user_id"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_exposure_receipts_immutable "
            "BEFORE UPDATE ON road_10k_exposure_receipts "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K exposure receipts are immutable'); "
            "END"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION road_10k_exposure_receipts_immutable() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "RAISE EXCEPTION 'road 10K exposure receipts are immutable'; "
            "END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_exposure_receipts_immutable "
            "BEFORE UPDATE ON road_10k_exposure_receipts "
            "FOR EACH ROW EXECUTE FUNCTION "
            "road_10k_exposure_receipts_immutable()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_exposure_receipts_immutable"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_exposure_receipts_immutable "
            "ON road_10k_exposure_receipts"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_exposure_receipts_immutable()"
        )
    for index_name, table_name in (
        ("ix_road_10k_screenshot_references_user_id", "road_10k_screenshot_references"),
        (
            "ix_road_10k_screenshot_references_evaluation_id",
            "road_10k_screenshot_references",
        ),
        ("ix_road_10k_evaluations_stage_id", "road_10k_evaluations"),
        ("ix_road_10k_evaluations_user_id", "road_10k_evaluations"),
        ("ix_road_10k_exposure_receipts_user_id", "road_10k_exposure_receipts"),
        ("ix_road_10k_exposure_receipts_stage_id", "road_10k_exposure_receipts"),
        ("ix_road_10k_owner_stage_receipt_stage_state", "road_10k_owner_stage_receipts"),
        ("ix_road_10k_owner_stage_receipt_stage_id", "road_10k_owner_stage_receipts"),
        ("ix_road_10k_owner_stage_receipt_user_id", "road_10k_owner_stage_receipts"),
    ):
        op.drop_index(index_name, table_name=table_name)
    for table_name in (
        "road_10k_screenshot_references",
        "road_10k_evaluations",
        "road_10k_exposure_receipts",
        "road_10k_owner_stage_receipts",
        "road_10k_stage_counters",
    ):
        op.drop_table(table_name)
