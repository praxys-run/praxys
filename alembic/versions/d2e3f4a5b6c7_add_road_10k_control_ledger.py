"""add the Road 10K control ledger and deletable evaluation references

Revision ID: d2e3f4a5b6c7
Revises: b8d4e6f7a9c1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "b8d4e6f7a9c1"
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
            "invitation_ceiling = 60 AND exposure_ceiling = 30",
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
        sa.Column(
            "sampling_run_evidence_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("invitation_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("invitation_issued_at", sa.DateTime(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(), nullable=True),
        sa.Column("first_exposed_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
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
            "length(authority_digest) = 64 "
            "AND length(notice_digest) = 64 "
            "AND length(cohort_rule_digest) = 64 "
            "AND length(sampling_run_evidence_digest) = 64",
            name="ck_road_10k_owner_stage_receipt_digests",
        ),
        sa.CheckConstraint(
            "state IN ('invited_only','enrolled_unexposed','exposed',"
            "'withdrawn','deleted')",
            name="ck_road_10k_owner_stage_receipt_state",
        ),
        sa.CheckConstraint(
            "(state = 'invited_only' AND enrolled_at IS NULL AND first_exposed_at IS NULL AND withdrawn_at IS NULL AND deleted_at IS NULL) OR "
            "(state = 'enrolled_unexposed' AND enrolled_at IS NOT NULL AND first_exposed_at IS NULL AND withdrawn_at IS NULL AND deleted_at IS NULL) OR "
            "(state = 'exposed' AND enrolled_at IS NOT NULL AND first_exposed_at IS NOT NULL AND withdrawn_at IS NULL AND deleted_at IS NULL) OR "
            "(state = 'withdrawn' AND withdrawn_at IS NOT NULL AND deleted_at IS NULL) OR "
            "(state = 'deleted' AND deleted_at IS NOT NULL)",
            name="ck_road_10k_owner_stage_receipt_lifecycle",
        ),
        sa.CheckConstraint(
            "created_at = invitation_issued_at AND updated_at >= invitation_issued_at AND "
            "(enrolled_at IS NULL OR enrolled_at >= invitation_issued_at) AND "
            "(first_exposed_at IS NULL OR (enrolled_at IS NOT NULL AND first_exposed_at >= enrolled_at)) AND "
            "(withdrawn_at IS NULL OR withdrawn_at >= invitation_issued_at) AND "
            "(deleted_at IS NULL OR deleted_at >= invitation_issued_at)",
            name="ck_road_10k_owner_stage_receipt_timestamps",
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
            "expires_at >= created_at",
            name="ck_road_10k_evaluation_expiry_after_creation",
        ),
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
    op.create_table(
        "road_10k_deletion_obligations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stage_id", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("committed_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("reason IN ('withdrawal','account_deletion','retention')", name="ck_road_10k_deletion_obligation_reason"),
        sa.CheckConstraint("length(manifest_digest) = 64", name="ck_road_10k_deletion_obligation_manifest_digest"),
        sa.CheckConstraint("status IN ('committed','completed')", name="ck_road_10k_deletion_obligation_status"),
        sa.CheckConstraint("(status = 'committed' AND completed_at IS NULL) OR (status = 'completed' AND completed_at IS NOT NULL)", name="ck_road_10k_deletion_obligation_completion"),
        sa.CheckConstraint("requested_at <= committed_at", name="ck_road_10k_deletion_obligation_commit_order"),
        sa.CheckConstraint("completed_at IS NULL OR completed_at >= committed_at", name="ck_road_10k_deletion_obligation_complete_order"),
    )
    op.create_index(
        "ix_road_10k_deletion_obligation_status",
        "road_10k_deletion_obligations",
        ["status"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_stage_counters_monotonic "
            "BEFORE UPDATE ON road_10k_stage_counters "
            "WHEN NEW.invitation_slots_consumed "
            "< OLD.invitation_slots_consumed "
            "OR NEW.distinct_exposed_owners_consumed "
            "< OLD.distinct_exposed_owners_consumed "
            "OR NEW.invitation_ceiling != OLD.invitation_ceiling "
            "OR NEW.exposure_ceiling != OLD.exposure_ceiling "
            "OR NEW.capability_id != OLD.capability_id "
            "OR NEW.schema_version != OLD.schema_version "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K counters cannot decrement'); "
            "END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_owner_stage_receipts_no_delete "
            "BEFORE DELETE ON road_10k_owner_stage_receipts "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K owner receipts cannot be deleted'); "
            "END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_owner_stage_receipts_immutable "
            "BEFORE UPDATE ON road_10k_owner_stage_receipts "
            "WHEN NEW.id != OLD.id OR NEW.stage_id != OLD.stage_id "
            "OR NEW.capability_id != OLD.capability_id "
            "OR NEW.schema_version != OLD.schema_version "
            "OR NEW.policy_version != OLD.policy_version "
            "OR NEW.authority_digest != OLD.authority_digest "
            "OR NEW.notice_digest != OLD.notice_digest "
            "OR NEW.cohort_rule_digest != OLD.cohort_rule_digest "
            "OR NEW.sampling_run_evidence_digest != OLD.sampling_run_evidence_digest "
            "OR NEW.invitation_idempotency_key != OLD.invitation_idempotency_key "
            "OR NEW.invitation_issued_at != OLD.invitation_issued_at "
            "OR NEW.created_at != OLD.created_at "
            "OR (OLD.user_id IS NULL AND NEW.user_id IS NOT NULL) "
            "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state != 'deleted') "
            "OR NOT (NEW.state = OLD.state "
            "OR (OLD.state = 'invited_only' AND NEW.state IN ('enrolled_unexposed','withdrawn')) "
            "OR (OLD.state = 'enrolled_unexposed' AND NEW.state IN ('exposed','withdrawn')) "
            "OR (OLD.state = 'exposed' AND NEW.state = 'withdrawn') "
            "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state = 'deleted')) "
            "BEGIN SELECT RAISE(ABORT, "
            "'road 10K owner receipt immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_exposure_receipts_immutable "
            "BEFORE UPDATE ON road_10k_exposure_receipts "
            "WHEN NOT ("
            "OLD.user_id IS NOT NULL AND NEW.user_id IS NULL "
            "AND NEW.id = OLD.id "
            "AND NEW.stage_id = OLD.stage_id "
            "AND NEW.owner_stage_receipt_id = OLD.owner_stage_receipt_id "
            "AND NEW.authority_digest = OLD.authority_digest "
            "AND NEW.exposed_at = OLD.exposed_at"
            ") "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K exposure receipts are immutable'); "
            "END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_exposure_receipts_no_delete "
            "BEFORE DELETE ON road_10k_exposure_receipts "
            "BEGIN "
            "SELECT RAISE(ABORT, "
            "'road 10K exposure receipts cannot be deleted'); "
            "END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_owner_stage_receipts_lifecycle "
            "BEFORE UPDATE ON road_10k_owner_stage_receipts "
            "WHEN NOT ("
            "(OLD.state = 'invited_only' AND NEW.state = 'enrolled_unexposed' "
            "AND NEW.user_id IS OLD.user_id AND NEW.enrolled_at IS NOT NULL "
            "AND NEW.first_exposed_at IS OLD.first_exposed_at AND NEW.withdrawn_at IS OLD.withdrawn_at "
            "AND NEW.deleted_at IS OLD.deleted_at AND NEW.updated_at = NEW.enrolled_at) "
            "OR (OLD.state = 'enrolled_unexposed' AND NEW.state = 'exposed' "
            "AND NEW.user_id IS OLD.user_id AND NEW.enrolled_at IS OLD.enrolled_at "
            "AND NEW.first_exposed_at IS NOT NULL AND NEW.withdrawn_at IS OLD.withdrawn_at "
            "AND NEW.deleted_at IS OLD.deleted_at AND NEW.updated_at = NEW.first_exposed_at) "
            "OR (OLD.state IN ('invited_only','enrolled_unexposed','exposed') AND NEW.state = 'withdrawn' "
            "AND NEW.user_id IS OLD.user_id AND NEW.enrolled_at IS OLD.enrolled_at "
            "AND NEW.first_exposed_at IS OLD.first_exposed_at AND NEW.withdrawn_at IS NOT NULL "
            "AND NEW.deleted_at IS OLD.deleted_at AND NEW.updated_at = NEW.withdrawn_at) "
            "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state = 'deleted' "
            "AND NEW.enrolled_at IS OLD.enrolled_at AND NEW.first_exposed_at IS OLD.first_exposed_at "
            "AND NEW.withdrawn_at IS OLD.withdrawn_at AND NEW.deleted_at IS NOT NULL "
            "AND NEW.updated_at = NEW.deleted_at)"
            ") "
            "BEGIN SELECT RAISE(ABORT, "
            "'road 10K owner receipt lifecycle invalid'); END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_deletion_obligations_no_delete "
            "BEFORE DELETE ON road_10k_deletion_obligations "
            "BEGIN SELECT RAISE(ABORT, "
            "'road 10K deletion obligations cannot be deleted'); END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_deletion_obligations_immutable "
            "BEFORE UPDATE ON road_10k_deletion_obligations "
            "WHEN NOT ((OLD.status = 'committed' AND NEW.status = 'completed' "
            "AND NEW.id = OLD.id AND NEW.stage_id = OLD.stage_id "
            "AND NEW.reason = OLD.reason AND NEW.manifest_digest = OLD.manifest_digest "
            "AND NEW.requested_at = OLD.requested_at AND NEW.committed_at = OLD.committed_at "
            "AND NEW.completed_at IS NOT NULL "
            "AND NEW.completed_at >= OLD.committed_at) "
            "OR (OLD.status = 'completed' AND NEW.status = 'completed' "
            "AND NEW.id = OLD.id AND NEW.stage_id = OLD.stage_id "
            "AND NEW.reason = OLD.reason AND NEW.manifest_digest = OLD.manifest_digest "
            "AND NEW.requested_at = OLD.requested_at AND NEW.committed_at = OLD.committed_at "
            "AND NEW.completed_at = OLD.completed_at)) "
            "BEGIN SELECT RAISE(ABORT, "
            "'road 10K deletion obligation immutable'); END"
        )

        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_evaluations_expiry_immutable "
            "BEFORE INSERT ON road_10k_evaluations "
            "WHEN julianday(NEW.expires_at) < julianday(NEW.created_at) "
            "OR julianday(NEW.expires_at) > julianday(NEW.created_at) + 30 "
            "BEGIN SELECT RAISE(ABORT, "
            "'road 10K evaluation expiry invalid'); END"
        )

        op.execute(
            "CREATE TRIGGER "
            "trg_road_10k_evaluations_expiry_no_update "
            "BEFORE UPDATE ON road_10k_evaluations "
            "WHEN NEW.expires_at != OLD.expires_at "
            "BEGIN SELECT RAISE(ABORT, "
            "'road 10K evaluation expiry immutable'); END"
        )
    elif bind.dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION road_10k_stage_counters_monotonic() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "IF NEW.invitation_slots_consumed "
            "< OLD.invitation_slots_consumed "
            "OR NEW.distinct_exposed_owners_consumed "
            "< OLD.distinct_exposed_owners_consumed "
            "OR NEW.invitation_ceiling != OLD.invitation_ceiling "
            "OR NEW.exposure_ceiling != OLD.exposure_ceiling "
            "OR NEW.capability_id != OLD.capability_id "
            "OR NEW.schema_version != OLD.schema_version THEN "
            "RAISE EXCEPTION 'road 10K counters cannot decrement'; "
            "END IF; "
            "RETURN NEW; "
            "END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_stage_counters_monotonic "
            "BEFORE UPDATE ON road_10k_stage_counters "
            "FOR EACH ROW EXECUTE FUNCTION "
            "road_10k_stage_counters_monotonic()"
        )
        op.execute(
            "CREATE FUNCTION road_10k_receipts_no_delete() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "RAISE EXCEPTION 'road 10K receipts cannot be deleted'; "
            "END; "
            "$$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_owner_stage_receipts_no_delete "
            "BEFORE DELETE ON road_10k_owner_stage_receipts "
            "FOR EACH ROW EXECUTE FUNCTION road_10k_receipts_no_delete()"
        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_exposure_receipts_no_delete "
            "BEFORE DELETE ON road_10k_exposure_receipts "
            "FOR EACH ROW EXECUTE FUNCTION road_10k_receipts_no_delete()"
        )
        op.execute(
            "CREATE FUNCTION road_10k_exposure_receipts_immutable() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "IF OLD.user_id IS NOT NULL AND NEW.user_id IS NULL "
            "AND NEW.id IS NOT DISTINCT FROM OLD.id "
            "AND NEW.stage_id IS NOT DISTINCT FROM OLD.stage_id "
            "AND NEW.owner_stage_receipt_id IS NOT DISTINCT FROM "
            "OLD.owner_stage_receipt_id "
            "AND NEW.authority_digest IS NOT DISTINCT FROM "
            "OLD.authority_digest "
            "AND NEW.exposed_at IS NOT DISTINCT FROM OLD.exposed_at "
            "THEN RETURN NEW; "
            "END IF; "
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

        op.execute(
            "CREATE FUNCTION road_10k_owner_stage_receipts_immutable() "
            "RETURNS trigger AS $$ "
            "BEGIN "
            "IF NEW.id IS DISTINCT FROM OLD.id OR NEW.stage_id IS DISTINCT FROM OLD.stage_id "
            "OR NEW.capability_id IS DISTINCT FROM OLD.capability_id OR NEW.schema_version IS DISTINCT FROM OLD.schema_version "
            "OR NEW.policy_version IS DISTINCT FROM OLD.policy_version OR NEW.authority_digest IS DISTINCT FROM OLD.authority_digest "
            "OR NEW.notice_digest IS DISTINCT FROM OLD.notice_digest OR NEW.cohort_rule_digest IS DISTINCT FROM OLD.cohort_rule_digest "
            "OR NEW.sampling_run_evidence_digest IS DISTINCT FROM OLD.sampling_run_evidence_digest "
            "OR NEW.invitation_idempotency_key IS DISTINCT FROM OLD.invitation_idempotency_key "
            "OR NEW.invitation_issued_at IS DISTINCT FROM OLD.invitation_issued_at OR NEW.created_at IS DISTINCT FROM OLD.created_at "
            "OR (OLD.user_id IS NULL AND NEW.user_id IS NOT NULL) THEN "
            "RAISE EXCEPTION 'road 10K owner receipt immutable'; END IF; "
            "IF (OLD.state = 'invited_only' AND NEW.state = 'enrolled_unexposed' AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id "
            "AND NEW.enrolled_at IS NOT NULL AND NEW.first_exposed_at IS NOT DISTINCT FROM OLD.first_exposed_at "

            "AND NEW.withdrawn_at IS NOT DISTINCT FROM OLD.withdrawn_at AND NEW.deleted_at IS NOT DISTINCT FROM OLD.deleted_at "
            "AND NEW.updated_at = NEW.enrolled_at) "
            "OR (OLD.state = 'enrolled_unexposed' AND NEW.state = 'exposed' AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id "
            "AND NEW.enrolled_at IS NOT DISTINCT FROM OLD.enrolled_at AND NEW.first_exposed_at IS NOT NULL "
            "AND NEW.withdrawn_at IS NOT DISTINCT FROM OLD.withdrawn_at AND NEW.deleted_at IS NOT DISTINCT FROM OLD.deleted_at "
            "AND NEW.updated_at = NEW.first_exposed_at) "
            "OR (OLD.state IN ('invited_only','enrolled_unexposed','exposed') AND NEW.state = 'withdrawn' "
            "AND NEW.user_id IS NOT DISTINCT FROM OLD.user_id AND NEW.enrolled_at IS NOT DISTINCT FROM OLD.enrolled_at "
            "AND NEW.first_exposed_at IS NOT DISTINCT FROM OLD.first_exposed_at AND NEW.withdrawn_at IS NOT NULL "
            "AND NEW.deleted_at IS NOT DISTINCT FROM OLD.deleted_at AND NEW.updated_at = NEW.withdrawn_at) "
            "OR (OLD.user_id IS NOT NULL AND NEW.user_id IS NULL AND NEW.state = 'deleted' "
            "AND NEW.enrolled_at IS NOT DISTINCT FROM OLD.enrolled_at AND NEW.first_exposed_at IS NOT DISTINCT FROM OLD.first_exposed_at "
            "AND NEW.withdrawn_at IS NOT DISTINCT FROM OLD.withdrawn_at AND NEW.deleted_at IS NOT NULL AND NEW.updated_at = NEW.deleted_at) "
            "THEN RETURN NEW; END IF; "
            "RAISE EXCEPTION 'road 10K owner receipt lifecycle invalid'; "
            "END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_owner_stage_receipts_immutable "
            "BEFORE UPDATE ON road_10k_owner_stage_receipts "
            "FOR EACH ROW EXECUTE FUNCTION road_10k_owner_stage_receipts_immutable()"
        )

        op.execute(
            "CREATE FUNCTION road_10k_deletion_obligations_immutable() "
            "RETURNS trigger AS $$ BEGIN "
            "IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'road 10K deletion obligations cannot be deleted'; END IF; "
            "IF (OLD.status = 'committed' AND NEW.status = 'completed' "
            "AND NEW.id IS NOT DISTINCT FROM OLD.id AND NEW.stage_id IS NOT DISTINCT FROM OLD.stage_id "
            "AND NEW.reason IS NOT DISTINCT FROM OLD.reason AND NEW.manifest_digest IS NOT DISTINCT FROM OLD.manifest_digest "
            "AND NEW.requested_at IS NOT DISTINCT FROM OLD.requested_at "
            "AND NEW.committed_at IS NOT DISTINCT FROM OLD.committed_at AND NEW.completed_at IS NOT NULL "
            "AND NEW.completed_at >= OLD.committed_at) "
            "OR (OLD.status = 'completed' AND NEW.status = 'completed' "
            "AND NEW.id IS NOT DISTINCT FROM OLD.id AND NEW.stage_id IS NOT DISTINCT FROM OLD.stage_id "
            "AND NEW.reason IS NOT DISTINCT FROM OLD.reason AND NEW.manifest_digest IS NOT DISTINCT FROM OLD.manifest_digest "
            "AND NEW.requested_at IS NOT DISTINCT FROM OLD.requested_at "
            "AND NEW.committed_at IS NOT DISTINCT FROM OLD.committed_at AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at) "
            "THEN RETURN NEW; END IF; "
            "RAISE EXCEPTION 'road 10K deletion obligation immutable'; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_deletion_obligations_immutable "
            "BEFORE UPDATE OR DELETE ON road_10k_deletion_obligations "
            "FOR EACH ROW EXECUTE FUNCTION road_10k_deletion_obligations_immutable()"
        )

        op.execute(
            "CREATE FUNCTION road_10k_evaluation_expiry_insert() RETURNS trigger AS $$ "
            "BEGIN IF NEW.expires_at < NEW.created_at OR NEW.expires_at > NEW.created_at + INTERVAL '30 days' THEN RAISE EXCEPTION 'road 10K evaluation expiry invalid'; END IF; "
            "RETURN NEW; END; $$ LANGUAGE plpgsql"

        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_evaluations_expiry_immutable "
            "BEFORE INSERT ON road_10k_evaluations FOR EACH ROW EXECUTE FUNCTION road_10k_evaluation_expiry_insert()"
        )
        op.execute(
            "CREATE FUNCTION road_10k_evaluation_expiry_update() RETURNS trigger AS $$ "
            "BEGIN IF NEW.expires_at IS DISTINCT FROM OLD.expires_at THEN RAISE EXCEPTION 'road 10K evaluation expiry immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"

        )
        op.execute(
            "CREATE TRIGGER trg_road_10k_evaluations_expiry_no_update "
            "BEFORE UPDATE ON road_10k_evaluations FOR EACH ROW EXECUTE FUNCTION road_10k_evaluation_expiry_update()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    consumed = bind.execute(
        sa.text(
            "SELECT CASE WHEN "
            "EXISTS (SELECT 1 FROM road_10k_stage_counters "
            "WHERE invitation_slots_consumed > 0 "
            "OR distinct_exposed_owners_consumed > 0) "
            "OR EXISTS (SELECT 1 FROM road_10k_owner_stage_receipts) "
            "OR EXISTS (SELECT 1 FROM road_10k_exposure_receipts) "
            "OR EXISTS (SELECT 1 FROM road_10k_deletion_obligations) "
            "THEN 1 ELSE 0 END"
        )
    ).scalar_one()
    if consumed:
        raise RuntimeError(
            "Cannot downgrade Road 10K control ledger after slot or receipt consumption"
        )
    if bind.dialect.name == "sqlite":
        for trigger_name in (
            "trg_road_10k_stage_counters_monotonic",
            "trg_road_10k_owner_stage_receipts_no_delete",
            "trg_road_10k_owner_stage_receipts_immutable",
            "trg_road_10k_owner_stage_receipts_lifecycle",
            "trg_road_10k_evaluations_expiry_immutable",
            "trg_road_10k_evaluations_expiry_no_update",
            "trg_road_10k_exposure_receipts_immutable",
            "trg_road_10k_exposure_receipts_no_delete",
            "trg_road_10k_deletion_obligations_no_delete",
            "trg_road_10k_deletion_obligations_immutable",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
    elif bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_stage_counters_monotonic "
            "ON road_10k_stage_counters"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_owner_stage_receipts_no_delete "
            "ON road_10k_owner_stage_receipts"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_owner_stage_receipts_immutable "
            "ON road_10k_owner_stage_receipts"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_evaluations_expiry_immutable "
            "ON road_10k_evaluations"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_evaluations_expiry_no_update "
            "ON road_10k_evaluations"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_exposure_receipts_immutable "
            "ON road_10k_exposure_receipts"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_road_10k_exposure_receipts_no_delete "
            "ON road_10k_exposure_receipts"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_road_10k_deletion_obligations_immutable "
            "ON road_10k_deletion_obligations"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_stage_counters_monotonic()"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_receipts_no_delete()"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_exposure_receipts_immutable()"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_owner_stage_receipts_immutable()"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_deletion_obligations_immutable()"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_evaluation_expiry_insert()"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS road_10k_evaluation_expiry_update()"
        )
    for index_name, table_name in (
        ("ix_road_10k_deletion_obligation_status", "road_10k_deletion_obligations"),
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
        "road_10k_deletion_obligations",
        "road_10k_screenshot_references",
        "road_10k_evaluations",
        "road_10k_exposure_receipts",
        "road_10k_owner_stage_receipts",
        "road_10k_stage_counters",
    ):
        op.drop_table(table_name)
