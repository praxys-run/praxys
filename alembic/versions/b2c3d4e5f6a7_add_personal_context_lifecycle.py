"""add encrypted personal-context lifecycle

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-08

Stores encrypted athlete-owned context versions, consent and use receipts,
and payload-free retryable deletion jobs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "personal_context_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("payload_schema_version", sa.Integer(), nullable=False),
        sa.Column("has_narrative", sa.Boolean(), nullable=False),
        sa.Column("source_actor_type", sa.String(length=32), nullable=False),
        sa.Column("source_actor_id", sa.String(length=120), nullable=True),
        sa.Column("linked_subject_type", sa.String(length=32), nullable=True),
        sa.Column("linked_subject_id", sa.String(length=120), nullable=True),
        sa.Column("processing_mode", sa.String(length=24), nullable=False),
        sa.Column("consent_receipt_id", sa.String(length=36), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("narrative_purge_at", sa.DateTime(), nullable=True),
        sa.Column("narrative_purged_at", sa.DateTime(), nullable=True),
        sa.Column("purge_after", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_personal_context_version_positive",
        ),
        sa.CheckConstraint(
            "payload_schema_version >= 1",
            name="ck_personal_context_payload_schema_positive",
        ),
        sa.CheckConstraint(
            "kind IN ("
            "'durable_preference','temporary_constraint',"
            "'execution_explanation'"
            ")",
            name="ck_personal_context_kind",
        ),
        sa.CheckConstraint(
            "purpose IN ("
            "'plan_generation','execution_interpretation','plan_adjustment',"
            "'goal_review','outcome_review'"
            ")",
            name="ck_personal_context_purpose",
        ),
        sa.CheckConstraint(
            "state IN ('active','expired','withdrawn','deleting')",
            name="ck_personal_context_state",
        ),
        sa.CheckConstraint(
            "processing_mode IN ('deterministic_only','ai_allowed')",
            name="ck_personal_context_processing_mode",
        ),
        sa.CheckConstraint(
            "processing_mode != 'ai_allowed' OR consent_receipt_id IS NOT NULL",
            name="ck_personal_context_ai_consent",
        ),
        sa.CheckConstraint(
            "has_narrative = false OR narrative_purge_at IS NOT NULL",
            name="ck_personal_context_narrative_purge",
        ),
        sa.CheckConstraint(
            "kind = 'durable_preference' OR "
            "(expires_at IS NOT NULL AND purge_after IS NOT NULL)",
            name="ck_personal_context_bounded_lifetime",
        ),
        sa.CheckConstraint(
            "kind != 'durable_preference' OR "
            "(expires_at IS NULL AND purge_after IS NULL "
            "AND has_narrative = false)",
            name="ck_personal_context_durable_lifetime",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > starts_at",
            name="ck_personal_context_expiry_order",
        ),
        sa.CheckConstraint(
            "purge_after IS NULL OR expires_at IS NULL "
            "OR purge_after >= expires_at",
            name="ck_personal_context_purge_order",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["personal_context_items.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_personal_context_lineage_version",
        ),
        sa.UniqueConstraint(
            "id",
            "user_id",
            name="uq_personal_context_item_owner",
        ),
    )
    op.create_index(
        "ix_personal_context_items_user_id",
        "personal_context_items",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_user_lineage_state",
        "personal_context_items",
        ["user_id", "lineage_id", "state", "version"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_expiry",
        "personal_context_items",
        ["state", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_narrative_purge",
        "personal_context_items",
        ["has_narrative", "narrative_purge_at"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_retention_purge",
        "personal_context_items",
        ["state", "purge_after"],
        unique=False,
    )

    op.create_table(
        "personal_context_consent_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("context_item_id", sa.String(length=36), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("consent_scope", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("disclosed_fields", sa.JSON(), nullable=False),
        sa.Column("narrative_disclosed", sa.Boolean(), nullable=False),
        sa.Column("consent_text_version", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("client", sa.String(length=32), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('granted','denied','withdrawn')",
            name="ck_personal_context_consent_decision",
        ),
        sa.CheckConstraint(
            "consent_scope IN ('purpose_confirmation','ai_processing')",
            name="ck_personal_context_consent_scope",
        ),
        sa.CheckConstraint(
            "purpose IN ("
            "'plan_generation','execution_interpretation','plan_adjustment',"
            "'goal_review','outcome_review'"
            ")",
            name="ck_personal_context_consent_purpose",
        ),
        sa.CheckConstraint(
            "(consent_scope != 'purpose_confirmation' OR provider IS NULL) "
            "AND (consent_scope != 'ai_processing' "
            "OR decision != 'granted' OR provider IS NOT NULL)",
            name="ck_personal_context_consent_provider",
        ),
        sa.CheckConstraint(
            "context_version >= 1",
            name="ck_personal_context_consent_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["context_item_id", "user_id"],
            ["personal_context_items.id", "personal_context_items.user_id"],
            ondelete="CASCADE",
            name="fk_personal_context_consent_item_owner",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "user_id",
            name="uq_personal_context_consent_owner",
        ),
    )
    op.create_index(
        "ix_personal_context_consent_receipts_user_id",
        "personal_context_consent_receipts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_consent_receipts_context_item_id",
        "personal_context_consent_receipts",
        ["context_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_consent_item_decided",
        "personal_context_consent_receipts",
        ["context_item_id", "decided_at"],
        unique=False,
    )

    op.create_table(
        "personal_context_use_receipts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("context_item_id", sa.String(length=36), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("consumer_type", sa.String(length=32), nullable=False),
        sa.Column("consumer_name", sa.String(length=100), nullable=False),
        sa.Column("disclosed_fields", sa.JSON(), nullable=False),
        sa.Column("narrative_disclosed", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("consent_receipt_id", sa.String(length=36), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "context_version >= 1",
            name="ck_personal_context_use_version_positive",
        ),
        sa.CheckConstraint(
            "purpose IN ("
            "'plan_generation','execution_interpretation','plan_adjustment',"
            "'goal_review','outcome_review'"
            ")",
            name="ck_personal_context_use_purpose",
        ),
        sa.CheckConstraint(
            "consumer_type IN ("
            "'deterministic_policy','planning_ai','provider_adapter'"
            ")",
            name="ck_personal_context_use_consumer",
        ),
        sa.ForeignKeyConstraint(
            ["consent_receipt_id", "user_id"],
            [
                "personal_context_consent_receipts.id",
                "personal_context_consent_receipts.user_id",
            ],
            ondelete="CASCADE",
            name="fk_personal_context_use_consent_owner",
        ),
        sa.ForeignKeyConstraint(
            ["context_item_id", "user_id"],
            ["personal_context_items.id", "personal_context_items.user_id"],
            ondelete="CASCADE",
            name="fk_personal_context_use_item_owner",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_personal_context_use_receipts_user_id",
        "personal_context_use_receipts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_use_receipts_context_item_id",
        "personal_context_use_receipts",
        ["context_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_use_item_used",
        "personal_context_use_receipts",
        ["context_item_id", "used_at"],
        unique=False,
    )

    op.create_table(
        "personal_context_deletion_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=True),
        sa.Column("target_item_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "reason IN ('withdrawal','expiry','retention','account_deletion')",
            name="ck_personal_context_deletion_reason",
        ),
        sa.CheckConstraint(
            "operation IN ("
            "'delete_owner_context','delete_lineage',"
            "'delete_version','purge_narrative'"
            ")",
            name="ck_personal_context_deletion_operation",
        ),
        sa.CheckConstraint(
            "(operation = 'delete_owner_context' "
            "AND lineage_id IS NULL AND target_item_id IS NULL) OR "
            "(operation = 'delete_lineage' "
            "AND lineage_id IS NOT NULL AND target_item_id IS NULL) OR "
            "(operation IN ('delete_version','purge_narrative') "
            "AND lineage_id IS NOT NULL AND target_item_id IS NOT NULL)",
            name="ck_personal_context_deletion_target",
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','failed','completed')",
            name="ck_personal_context_deletion_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_personal_context_deletion_attempts",
        ),
        sa.CheckConstraint(
            "status != 'running' OR started_at IS NOT NULL",
            name="ck_personal_context_deletion_started",
        ),
        sa.CheckConstraint(
            "status != 'completed' OR completed_at IS NOT NULL",
            name="ck_personal_context_deletion_completed",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_personal_context_deletion_jobs_user_id",
        "personal_context_deletion_jobs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_personal_context_deletion_user_target",
        "personal_context_deletion_jobs",
        [
            "user_id",
            "operation",
            "lineage_id",
            "target_item_id",
            "status",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_personal_context_deletion_user_target",
        table_name="personal_context_deletion_jobs",
    )
    op.drop_index(
        "ix_personal_context_deletion_jobs_user_id",
        table_name="personal_context_deletion_jobs",
    )
    op.drop_table("personal_context_deletion_jobs")
    op.drop_index(
        "ix_personal_context_use_item_used",
        table_name="personal_context_use_receipts",
    )
    op.drop_index(
        "ix_personal_context_use_receipts_context_item_id",
        table_name="personal_context_use_receipts",
    )
    op.drop_index(
        "ix_personal_context_use_receipts_user_id",
        table_name="personal_context_use_receipts",
    )
    op.drop_table("personal_context_use_receipts")
    op.drop_index(
        "ix_personal_context_consent_item_decided",
        table_name="personal_context_consent_receipts",
    )
    op.drop_index(
        "ix_personal_context_consent_receipts_context_item_id",
        table_name="personal_context_consent_receipts",
    )
    op.drop_index(
        "ix_personal_context_consent_receipts_user_id",
        table_name="personal_context_consent_receipts",
    )
    op.drop_table("personal_context_consent_receipts")
    op.drop_index(
        "ix_personal_context_retention_purge",
        table_name="personal_context_items",
    )
    op.drop_index(
        "ix_personal_context_narrative_purge",
        table_name="personal_context_items",
    )
    op.drop_index(
        "ix_personal_context_expiry",
        table_name="personal_context_items",
    )
    op.drop_index(
        "ix_personal_context_user_lineage_state",
        table_name="personal_context_items",
    )
    op.drop_index(
        "ix_personal_context_items_user_id",
        table_name="personal_context_items",
    )
    op.drop_table("personal_context_items")
