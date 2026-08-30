"""merge road 10K snapshot lineage

Revision ID: b8d4e6f7a9c1
Revises: a7f3c2d1e9b4, ae1f2a3b4c5d
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d4e6f7a9c1"
down_revision: Union[str, Sequence[str], None] = (
    "a7f3c2d1e9b4",
    "ae1f2a3b4c5d",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        bind.exec_driver_sql("PRAGMA secure_delete=ON")

    op.create_table(
        "road_10k_training_pattern_snapshots",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=67), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("usable_completed_weeks", sa.Integer(), nullable=False),
        sa.Column("recent_modal_running_frequency", sa.Integer(), nullable=False),
        sa.Column(
            "recent_median_usable_weekly_minutes",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "recent_maximum_usable_weekly_minutes",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("recent_maximum_session_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "recent_maximum_session_distance_km",
            sa.Float(),
            nullable=False,
        ),
        sa.Column("latest_run_date", sa.Date(), nullable=False),
        sa.Column("history_observation_count", sa.Integer(), nullable=False),
        sa.Column(
            "history_provenance_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("intensity_observation_count", sa.Integer(), nullable=False),
        sa.Column(
            "intensity_provenance_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("reserved_date_count", sa.Integer(), nullable=False),
        sa.Column(
            "reservation_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "canonical_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "version = 'v1:' || canonical_fingerprint",
            name="ck_road_10k_training_pattern_version",
        ),
        sa.CheckConstraint(
            "schema_version = 'road-10k-training-pattern-v1'",
            name="ck_road_10k_training_pattern_schema",
        ),
        sa.CheckConstraint(
            "policy_version = 'road-10k-plan-generation-policy-v2'",
            name="ck_road_10k_training_pattern_policy",
        ),
        sa.CheckConstraint(
            "usable_completed_weeks >= 0 AND usable_completed_weeks <= 8",
            name="ck_road_10k_training_pattern_usable_weeks",
        ),
        sa.CheckConstraint(
            "recent_modal_running_frequency >= 0",
            name="ck_road_10k_training_pattern_frequency",
        ),
        sa.CheckConstraint(
            "recent_median_usable_weekly_minutes >= 0",
            name="ck_road_10k_training_pattern_median_minutes",
        ),
        sa.CheckConstraint(
            "recent_maximum_usable_weekly_minutes >= 0",
            name="ck_road_10k_training_pattern_max_weekly_minutes",
        ),
        sa.CheckConstraint(
            "recent_maximum_session_minutes >= 0",
            name="ck_road_10k_training_pattern_max_session_minutes",
        ),
        sa.CheckConstraint(
            "recent_maximum_session_distance_km > 0",
            name="ck_road_10k_training_pattern_max_distance",
        ),
        sa.CheckConstraint(
            "history_observation_count >= 0 "
            "AND history_observation_count <= 1000",
            name="ck_road_10k_training_pattern_history_count",
        ),
        sa.CheckConstraint(
            "intensity_observation_count >= 0 "
            "AND intensity_observation_count <= 1000",
            name="ck_road_10k_training_pattern_intensity_count",
        ),
        sa.CheckConstraint(
            "reserved_date_count >= 0 AND reserved_date_count <= 14",
            name="ck_road_10k_training_pattern_reservation_count",
        ),
        sa.CheckConstraint(
            "length(history_provenance_fingerprint) = 64 "
            "AND length(intensity_provenance_fingerprint) = 64 "
            "AND length(reservation_fingerprint) = 64 "
            "AND length(canonical_fingerprint) = 64",
            name="ck_road_10k_training_pattern_fingerprints",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "version",
            name="pk_road_10k_training_pattern_snapshots",
        ),
    )
    op.create_index(
        op.f("ix_road_10k_training_pattern_snapshots_user_id"),
        "road_10k_training_pattern_snapshots",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_road_10k_training_pattern_owner_created",
        "road_10k_training_pattern_snapshots",
        ["user_id", "created_at"],
        unique=False,
    )

    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_training_pattern_snapshots_immutable "
            "BEFORE UPDATE ON road_10k_training_pattern_snapshots "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K training pattern snapshots are immutable'); "
            "END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION road_10k_training_pattern_snapshots_immutable() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "RAISE EXCEPTION "
            "'road 10K training pattern snapshots are immutable'; "
            "END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_training_pattern_snapshots_immutable "
            "BEFORE UPDATE ON road_10k_training_pattern_snapshots "
            "FOR EACH ROW EXECUTE FUNCTION "
            "road_10k_training_pattern_snapshots_immutable()"
        )

    with op.batch_alter_table("road_10k_plan_generations") as batch_op:
        batch_op.drop_column("history_observation_ids")
        batch_op.create_index(
            "ix_road_10k_generation_owner_training_pattern",
            ["user_id", "training_pattern_snapshot_version"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("road_10k_plan_generations") as batch_op:
        batch_op.drop_index(
            "ix_road_10k_generation_owner_training_pattern"
        )
        batch_op.add_column(
            sa.Column(
                "history_observation_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    with op.batch_alter_table("road_10k_plan_generations") as batch_op:
        batch_op.alter_column(
            "history_observation_ids",
            server_default=None,
        )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_training_pattern_snapshots_immutable"
        )
    elif dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_training_pattern_snapshots_immutable "
            "ON road_10k_training_pattern_snapshots"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS "
            "road_10k_training_pattern_snapshots_immutable()"
        )

    op.drop_index(
        "ix_road_10k_training_pattern_owner_created",
        table_name="road_10k_training_pattern_snapshots",
    )
    op.drop_index(
        op.f("ix_road_10k_training_pattern_snapshots_user_id"),
        table_name="road_10k_training_pattern_snapshots",
    )
    op.drop_table("road_10k_training_pattern_snapshots")
