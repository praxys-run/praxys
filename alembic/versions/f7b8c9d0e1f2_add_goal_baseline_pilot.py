"""add goal baseline pilot tables

Revision ID: f7b8c9d0e1f2
Revises: e6a7b8c9d0f1
Create Date: 2026-08-11 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "e6a7b8c9d0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goal_baseline_confirmations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_signature", sa.String(length=64), nullable=False),
        sa.Column("goal_snapshot", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("activity_id", sa.String(length=100), nullable=False),
        sa.Column("response", sa.String(length=24), nullable=False),
        sa.Column("measured_5k", sa.Boolean(), nullable=False),
        sa.Column("elapsed_timing_confirmed", sa.Boolean(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["goal_baseline_confirmations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_goal_baseline_confirmation_idempotency"),
        sa.UniqueConstraint("user_id", "lineage_id", "version", name="uq_goal_baseline_confirmation_lineage_version"),
        sa.CheckConstraint("version >= 1", name="ck_goal_baseline_confirmation_version_positive"),
        sa.CheckConstraint("response IN ('race','intentional_all_out','not_all_out','deleted')", name="ck_goal_baseline_confirmation_response"),
    )
    op.create_index("ix_goal_baseline_confirmation_user_goal_activity", "goal_baseline_confirmations", ["user_id", "goal_signature", "activity_id", "created_at"], unique=False)

    op.create_table(
        "goal_baseline_test_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_signature", sa.String(length=64), nullable=False),
        sa.Column("goal_snapshot", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("protocol_id", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("plan_canonical_id", sa.String(length=36), nullable=True),
        sa.Column("activity_id", sa.String(length=100), nullable=True),
        sa.Column("observed_date", sa.Date(), nullable=True),
        sa.Column("measured_5k", sa.Boolean(), nullable=True),
        sa.Column("elapsed_timing_confirmed", sa.Boolean(), nullable=True),
        sa.Column("protocol_followed", sa.Boolean(), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("safety_stop", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["goal_baseline_test_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_goal_baseline_test_idempotency"),
        sa.UniqueConstraint("user_id", "lineage_id", "version", name="uq_goal_baseline_test_lineage_version"),
        sa.CheckConstraint("version >= 1", name="ck_goal_baseline_test_version_positive"),
        sa.CheckConstraint("state IN ('offered','scheduled','declined','stopped','completed','invalidated','deleted')", name="ck_goal_baseline_test_state"),
        sa.CheckConstraint("reason_code IS NULL OR reason_code IN ('acute_illness','injury_or_pain_altering_running','chest_pain_or_pressure','fainting_or_near_fainting','unusual_severe_breathlessness','confusion_or_loss_of_coordination','other_red_flag_symptom','known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing','self_reported_inadequate_recovery_or_unresolved_substantial_fatigue','unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course','protocol_or_provenance_unresolved')", name="ck_goal_baseline_test_reason_code"),
    )
    op.create_index("ix_goal_baseline_test_user_goal_created", "goal_baseline_test_records", ["user_id", "goal_signature", "created_at"], unique=False)

    op.create_table(
        "goal_baseline_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_signature", sa.String(length=64), nullable=False),
        sa.Column("goal_snapshot", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("provenance", sa.String(length=24), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("elapsed_time_sec", sa.Float(), nullable=True),
        sa.Column("measured_5k", sa.Boolean(), nullable=False),
        sa.Column("elapsed_timing_confirmed", sa.Boolean(), nullable=False),
        sa.Column("qualification_status", sa.String(length=24), nullable=False),
        sa.Column("change_comparability", sa.String(length=24), nullable=False),
        sa.Column("invalidators", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["goal_baseline_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lineage_id", "version", name="uq_goal_baseline_snapshot_lineage_version"),
        sa.CheckConstraint("version >= 1", name="ck_goal_baseline_snapshot_version_positive"),
        sa.CheckConstraint("source_kind IN ('history_confirmation','pilot_test')", name="ck_goal_baseline_snapshot_source_kind"),
        sa.CheckConstraint("provenance IN ('race','intentional_all_out','pilot_test','unqualified')", name="ck_goal_baseline_snapshot_provenance"),
        sa.CheckConstraint("qualification_status IN ('direct_current','incomparable','invalidated','deleted')", name="ck_goal_baseline_snapshot_qualification_status"),
        sa.CheckConstraint("change_comparability IN ('not_assessed','supporting','incomparable','directly_comparable')", name="ck_goal_baseline_snapshot_change_comparability"),
    )
    op.create_index("ix_goal_baseline_snapshot_user_goal_created", "goal_baseline_snapshots", ["user_id", "goal_signature", "created_at"], unique=False)

    op.create_table(
        "goal_baseline_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_signature", sa.String(length=64), nullable=False),
        sa.Column("goal_snapshot", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("science_decision_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("readiness", sa.String(length=40), nullable=False),
        sa.Column("evidence_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("test_record_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["goal_baseline_assessments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lineage_id", "version", name="uq_goal_baseline_assessment_lineage_version"),
        sa.CheckConstraint("version >= 1", name="ck_goal_baseline_assessment_version_positive"),
        sa.CheckConstraint("status IN ('current','stale','incomparable','missing','not_required','pending_test')", name="ck_goal_baseline_assessment_status"),
        sa.CheckConstraint("readiness IN ('sufficient_baseline','insufficient_evidence','non_diagnostic_safety_stop')", name="ck_goal_baseline_assessment_readiness"),
    )
    op.create_index("ix_goal_baseline_assessment_user_goal_created", "goal_baseline_assessments", ["user_id", "goal_signature", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_goal_baseline_assessment_user_goal_created", table_name="goal_baseline_assessments")
    op.drop_table("goal_baseline_assessments")
    op.drop_index("ix_goal_baseline_snapshot_user_goal_created", table_name="goal_baseline_snapshots")
    op.drop_table("goal_baseline_snapshots")
    op.drop_index("ix_goal_baseline_test_user_goal_created", table_name="goal_baseline_test_records")
    op.drop_table("goal_baseline_test_records")
    op.drop_index("ix_goal_baseline_confirmation_user_goal_activity", table_name="goal_baseline_confirmations")
    op.drop_table("goal_baseline_confirmations")
