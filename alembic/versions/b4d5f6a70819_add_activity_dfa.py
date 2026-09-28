"""Owner-scoped post-run DFA caches, source confirmations and execution slot."""
from alembic import op
import sqlalchemy as sa

revision = "b4d5f6a70819"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("activity_dfa_confirmations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(100), nullable=False),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("garmin_fit_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parse_id", sa.String(36), sa.ForeignKey("garmin_fit_parses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recording_ref", sa.JSON(), nullable=False),
        sa.Column("sensor_ref", sa.String(32), nullable=False),
        sa.Column("sensor_label", sa.String(80), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("rule_fingerprint", sa.String(64), nullable=False),
        sa.Column("statement_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "snapshot_id", "parse_id", name="uq_dfa_confirmation_input"))
    op.create_index("ix_activity_dfa_confirmations_user_id", "activity_dfa_confirmations", ["user_id"])
    op.create_table("activity_dfa_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(100), nullable=False),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("garmin_fit_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parse_id", sa.String(36), sa.ForeignKey("garmin_fit_parses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confirmation_id", sa.String(36), sa.ForeignKey("activity_dfa_confirmations.id", ondelete="CASCADE")),
        sa.Column("recording_ref", sa.JSON(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("method_version", sa.String(80), nullable=False),
        sa.Column("science_contract_digest", sa.String(71), nullable=False),
        sa.Column("phase", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("freshness", sa.String(10), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("recoveries", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("progress", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("result", sa.JSON()),
        sa.Column("result_revision", sa.String(64)),
        sa.Column("retained_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "input_digest", name="uq_dfa_run_input"),
        sa.CheckConstraint("phase IN ('prepare','compute')", name="ck_dfa_phase"),
        sa.CheckConstraint("status IN ('queued','running','awaiting_source_confirmation','complete','unavailable','failed','cancelled')", name="ck_dfa_state"),
        sa.CheckConstraint("freshness IN ('current','stale')", name="ck_dfa_freshness"),
        sa.CheckConstraint("generation >= 1 AND retained_bytes >= 0 AND recoveries BETWEEN 0 AND 1", name="ck_dfa_run_bounds"))
    op.create_index("ix_activity_dfa_runs_user_id", "activity_dfa_runs", ["user_id"])
    op.create_index("uq_dfa_active_owner", "activity_dfa_runs", ["user_id"], unique=True,
        sqlite_where=sa.text("status IN ('queued','running')"), postgresql_where=sa.text("status IN ('queued','running')"))
    op.create_table("activity_dfa_execution_slot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("activity_dfa_runs.id", ondelete="SET NULL")),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_until", sa.DateTime()),
        sa.CheckConstraint("id = 1", name="ck_dfa_single_slot"))
    op.execute(sa.text("INSERT INTO activity_dfa_execution_slot(id) VALUES (1)"))


def downgrade():
    op.drop_table("activity_dfa_execution_slot")
    op.drop_table("activity_dfa_runs")
    op.drop_table("activity_dfa_confirmations")
