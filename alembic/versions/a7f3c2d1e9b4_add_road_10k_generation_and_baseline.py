"""add road 10k baseline and generation audit

Revision ID: a7f3c2d1e9b4
Revises: 9d0e1f2a3b4c
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7f3c2d1e9b4"
down_revision: Union[str, Sequence[str], None] = "9d0e1f2a3b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "road_10k_baseline_confirmations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_signature", sa.String(length=64), nullable=False),
        sa.Column("goal_snapshot", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("activity_id", sa.String(length=100), nullable=False),
        sa.Column("response", sa.String(length=24), nullable=False),
        sa.Column("measured_10k", sa.Boolean(), nullable=False),
        sa.Column("elapsed_timing_confirmed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("elapsed_time_sec", sa.Float(), nullable=False),
        sa.Column("surface_or_protocol", sa.String(length=64), nullable=True),
        sa.Column("route_or_venue_identifier", sa.String(length=200), nullable=True),
        sa.Column("assistance_status", sa.String(length=32), nullable=False),
        sa.Column("source_provider", sa.String(length=20), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["road_10k_baseline_confirmations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_road_10k_baseline_confirmation_lineage_version",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_road_10k_baseline_confirmation_idempotency",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_road_10k_baseline_confirmation_version_positive",
        ),
        sa.CheckConstraint(
            "response IN ('race','intentional_all_out','not_all_out','deleted')",
            name="ck_road_10k_baseline_confirmation_response",
        ),
        sa.CheckConstraint(
            "elapsed_time_sec > 0",
            name="ck_road_10k_baseline_confirmation_elapsed_positive",
        ),
        sa.CheckConstraint(
            "surface_or_protocol IS NULL OR "
            "surface_or_protocol IN "
            "('organized_outdoor_road_10k_race',"
            "'standardized_outdoor_road_10k_time_trial',"
            "'standardized_track_10k_time_trial')",
            name="ck_road_10k_baseline_confirmation_surface_protocol",
        ),
        sa.CheckConstraint(
            "assistance_status IN "
            "('unassisted','assisted','unknown_or_unreported')",
            name="ck_road_10k_baseline_confirmation_assistance_status",
        ),
    )
    op.create_index(
        op.f("ix_road_10k_baseline_confirmations_user_id"),
        "road_10k_baseline_confirmations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_road_10k_baseline_confirmation_user_goal_activity",
        "road_10k_baseline_confirmations",
        ["user_id", "goal_signature", "activity_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "road_10k_baseline_snapshots",
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
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("elapsed_time_sec", sa.Float(), nullable=True),
        sa.Column("measured_10k", sa.Boolean(), nullable=False),
        sa.Column("elapsed_timing_confirmed", sa.Boolean(), nullable=False),
        sa.Column("surface_or_protocol", sa.String(length=64), nullable=True),
        sa.Column("route_or_venue_identifier", sa.String(length=200), nullable=True),
        sa.Column("assistance_status", sa.String(length=32), nullable=False),
        sa.Column("source_provider", sa.String(length=20), nullable=False),
        sa.Column("qualification_status", sa.String(length=24), nullable=False),
        sa.Column("change_comparability", sa.String(length=24), nullable=False),
        sa.Column("invalidators", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["road_10k_baseline_snapshots.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "lineage_id",
            "version",
            name="uq_road_10k_baseline_snapshot_lineage_version",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_road_10k_baseline_snapshot_version_positive",
        ),
        sa.CheckConstraint(
            "source_kind IN ('history_confirmation')",
            name="ck_road_10k_baseline_snapshot_source_kind",
        ),
        sa.CheckConstraint(
            "provenance IN ('race','intentional_all_out','unqualified')",
            name="ck_road_10k_baseline_snapshot_provenance",
        ),
        sa.CheckConstraint(
            "surface_or_protocol IS NULL OR "
            "surface_or_protocol IN "
            "('organized_outdoor_road_10k_race',"
            "'standardized_outdoor_road_10k_time_trial',"
            "'standardized_track_10k_time_trial')",
            name="ck_road_10k_baseline_snapshot_surface_protocol",
        ),
        sa.CheckConstraint(
            "assistance_status IN "
            "('unassisted','assisted','unknown_or_unreported')",
            name="ck_road_10k_baseline_snapshot_assistance_status",
        ),
        sa.CheckConstraint(
            "qualification_status IN ('direct_current','incomparable','deleted')",
            name="ck_road_10k_baseline_snapshot_qualification_status",
        ),
        sa.CheckConstraint(
            "change_comparability IN ('not_assessed','supporting','incomparable','directly_comparable')",
            name="ck_road_10k_baseline_snapshot_change_comparability",
        ),
    )
    op.create_index(
        op.f("ix_road_10k_baseline_snapshots_user_id"),
        "road_10k_baseline_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_road_10k_baseline_snapshot_user_goal_created",
        "road_10k_baseline_snapshots",
        ["user_id", "goal_signature", "created_at"],
        unique=False,
    )

    op.create_table(
        "road_10k_plan_generations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("proposal_id", sa.String(length=36), nullable=False),
        sa.Column("capability_id", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("generator_version", sa.String(length=80), nullable=False),
        sa.Column("science_decision_id", sa.String(length=120), nullable=False),
        sa.Column("source_decision_digest", sa.String(length=80), nullable=False),
        sa.Column("contract_digest", sa.String(length=80), nullable=False),
        sa.Column("baseline_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("baseline_source", sa.String(length=24), nullable=True),
        sa.Column("source_goal_id", sa.String(length=36), nullable=True),
        sa.Column("source_goal_revision", sa.String(length=64), nullable=True),
        sa.Column("history_cutoff_completed_days", sa.Integer(), nullable=False),
        sa.Column("history_observation_ids", sa.JSON(), nullable=False),
        sa.Column("training_pattern_snapshot_version", sa.String(length=80), nullable=False),
        sa.Column("event_context_snapshot_version", sa.String(length=80), nullable=False),
        sa.Column("active_zone_model_id", sa.String(length=80), nullable=True),
        sa.Column("active_zone_model_version", sa.String(length=80), nullable=True),
        sa.Column("normalized_constraints", sa.JSON(), nullable=False),
        sa.Column("selected_template_ids", sa.JSON(), nullable=False),
        sa.Column("source_revision", sa.String(length=64), nullable=False),
        sa.Column("deterministic_input_hash", sa.String(length=64), nullable=False),
        sa.Column("request_kind", sa.String(length=20), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("predecessor_proposal_id", sa.String(length=36), nullable=True),
        sa.Column("predecessor_version", sa.Integer(), nullable=True),
        sa.Column("observed_input_snapshot", sa.JSON(), nullable=False),
        sa.Column("derived_history_statistics", sa.JSON(), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["plan_proposals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "proposal_id",
            name="uq_road_10k_generation_proposal_owner",
        ),
    )
    op.create_index(
        op.f("ix_road_10k_plan_generations_user_id"),
        "road_10k_plan_generations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_road_10k_plan_generations_proposal_id"),
        "road_10k_plan_generations",
        ["proposal_id"],
        unique=True,
    )
    op.create_index(
        "ix_road_10k_generation_user_revision",
        "road_10k_plan_generations",
        ["user_id", "source_revision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_road_10k_generation_user_revision",
        table_name="road_10k_plan_generations",
    )
    op.drop_index(
        op.f("ix_road_10k_plan_generations_proposal_id"),
        table_name="road_10k_plan_generations",
    )
    op.drop_index(
        op.f("ix_road_10k_plan_generations_user_id"),
        table_name="road_10k_plan_generations",
    )
    op.drop_table("road_10k_plan_generations")

    op.drop_index(
        "ix_road_10k_baseline_snapshot_user_goal_created",
        table_name="road_10k_baseline_snapshots",
    )
    op.drop_index(
        op.f("ix_road_10k_baseline_snapshots_user_id"),
        table_name="road_10k_baseline_snapshots",
    )
    op.drop_table("road_10k_baseline_snapshots")

    op.drop_index(
        "ix_road_10k_baseline_confirmation_user_goal_activity",
        table_name="road_10k_baseline_confirmations",
    )
    op.drop_index(
        op.f("ix_road_10k_baseline_confirmations_user_id"),
        table_name="road_10k_baseline_confirmations",
    )
    op.drop_table("road_10k_baseline_confirmations")
