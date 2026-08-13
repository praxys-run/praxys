"""add adaptive plan proposal foundation

Revision ID: 8c9d0e1f2a3b
Revises: f7b8c9d0e1f2
Create Date: 2026-08-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c9d0e1f2a3b"
down_revision: Union[str, Sequence[str], None] = "f7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTIVE_PLAN_PREDICATE = "lifecycle IN ('draft','active')"


def upgrade() -> None:
    op.create_table(
        "adaptive_plan_goal_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("goal_kind", sa.String(length=40), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("horizon_start", sa.Date(), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_adaptive_goal_version_positive"),
        sa.CheckConstraint("state IN ('draft','active','superseded')", name="ck_adaptive_goal_state"),
        sa.CheckConstraint("horizon_end >= horizon_start", name="ck_adaptive_goal_horizon_order"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "id", name="uq_adaptive_goal_snapshot_owner"),
    )
    op.create_index(
        op.f("ix_adaptive_plan_goal_snapshots_user_id"),
        "adaptive_plan_goal_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_adaptive_goal_user_created",
        "adaptive_plan_goal_snapshots",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "adaptive_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("goal_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("discipline", sa.String(length=30), nullable=False),
        sa.Column("lifecycle", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active_proposal_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 0", name="ck_adaptive_plan_version_nonnegative"),
        sa.CheckConstraint(
            "lifecycle IN ('draft','active','completed','archived')",
            name="ck_adaptive_plan_lifecycle",
        ),
        sa.CheckConstraint(
            "discipline IN ('running','trail_running')",
            name="ck_adaptive_plan_discipline",
        ),
        sa.ForeignKeyConstraint(["goal_snapshot_id"], ["adaptive_plan_goal_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "id", name="uq_adaptive_plan_owner"),
    )
    op.create_index(op.f("ix_adaptive_plans_user_id"), "adaptive_plans", ["user_id"], unique=False)
    op.create_index(op.f("ix_adaptive_plans_goal_snapshot_id"), "adaptive_plans", ["goal_snapshot_id"], unique=False)
    op.create_index("ix_adaptive_plan_user_lifecycle", "adaptive_plans", ["user_id", "lifecycle"], unique=False)
    op.create_index(
        "uq_adaptive_plan_one_active",
        "adaptive_plans",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text(_ACTIVE_PLAN_PREDICATE),
        postgresql_where=sa.text(_ACTIVE_PLAN_PREDICATE),
    )

    op.create_table(
        "plan_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("adaptive_plan_id", sa.String(length=36), nullable=False),
        sa.Column("goal_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("discipline", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=80), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=True),
        sa.Column("base_plan_version", sa.Integer(), nullable=False),
        sa.Column("supersedes_proposal_id", sa.String(length=36), nullable=True),
        sa.Column("policy_version", sa.String(length=80), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=True),
        sa.Column("science_version", sa.String(length=80), nullable=True),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("unknowns", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("decision_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("workout_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_plan_proposal_version_positive"),
        sa.CheckConstraint("base_plan_version >= 0", name="ck_plan_proposal_base_version_nonnegative"),
        sa.CheckConstraint(
            "state IN ('draft','superseded','rejected','adopted','expired')",
            name="ck_plan_proposal_state",
        ),
        sa.CheckConstraint("actor_type IN ('user','agent','system')", name="ck_plan_proposal_actor_type"),
        sa.CheckConstraint(
            "discipline IN ('running','trail_running')",
            name="ck_plan_proposal_discipline",
        ),
        sa.ForeignKeyConstraint(["adaptive_plan_id"], ["adaptive_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goal_snapshot_id"], ["adaptive_plan_goal_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supersedes_proposal_id"], ["plan_proposals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "id", name="uq_plan_proposal_owner"),
        sa.UniqueConstraint("adaptive_plan_id", "version", name="uq_plan_proposal_plan_version"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_plan_proposal_idempotency"),
    )
    op.create_index(op.f("ix_plan_proposals_user_id"), "plan_proposals", ["user_id"], unique=False)
    op.create_index(op.f("ix_plan_proposals_adaptive_plan_id"), "plan_proposals", ["adaptive_plan_id"], unique=False)
    op.create_index(op.f("ix_plan_proposals_goal_snapshot_id"), "plan_proposals", ["goal_snapshot_id"], unique=False)
    op.create_index("ix_plan_proposal_user_state", "plan_proposals", ["user_id", "state", "created_at"], unique=False)
    op.create_index("ix_plan_proposal_plan_state", "plan_proposals", ["adaptive_plan_id", "state", "version"], unique=False)

    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.add_column(sa.Column("adaptive_plan_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("activity_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("workout_structure_version", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("workout_structure", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            "fk_training_plan_adaptive_plan",
            "adaptive_plans",
            ["adaptive_plan_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(op.f("ix_training_plans_adaptive_plan_id"), "training_plans", ["adaptive_plan_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_training_plans_adaptive_plan_id"), table_name="training_plans")
    with op.batch_alter_table("training_plans") as batch_op:
        batch_op.drop_constraint("fk_training_plan_adaptive_plan", type_="foreignkey")
        batch_op.drop_column("workout_structure")
        batch_op.drop_column("workout_structure_version")
        batch_op.drop_column("activity_type")
        batch_op.drop_column("adaptive_plan_id")

    op.drop_index("ix_plan_proposal_plan_state", table_name="plan_proposals")
    op.drop_index("ix_plan_proposal_user_state", table_name="plan_proposals")
    op.drop_index(op.f("ix_plan_proposals_goal_snapshot_id"), table_name="plan_proposals")
    op.drop_index(op.f("ix_plan_proposals_adaptive_plan_id"), table_name="plan_proposals")
    op.drop_index(op.f("ix_plan_proposals_user_id"), table_name="plan_proposals")
    op.drop_table("plan_proposals")

    op.drop_index("uq_adaptive_plan_one_active", table_name="adaptive_plans")
    op.drop_index("ix_adaptive_plan_user_lifecycle", table_name="adaptive_plans")
    op.drop_index(op.f("ix_adaptive_plans_goal_snapshot_id"), table_name="adaptive_plans")
    op.drop_index(op.f("ix_adaptive_plans_user_id"), table_name="adaptive_plans")
    op.drop_table("adaptive_plans")

    op.drop_index("ix_adaptive_goal_user_created", table_name="adaptive_plan_goal_snapshots")
    op.drop_index(op.f("ix_adaptive_plan_goal_snapshots_user_id"), table_name="adaptive_plan_goal_snapshots")
    op.drop_table("adaptive_plan_goal_snapshots")
