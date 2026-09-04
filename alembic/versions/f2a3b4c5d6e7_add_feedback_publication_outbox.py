"""add consent-bound feedback publication outbox

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-04
"""
from datetime import datetime
from typing import Sequence, Union
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_target_repo(
    issue_url: object,
    issue_number: int,
    feedback_id: int,
) -> tuple[str, bool]:
    """Return a strict GitHub repo or an internal non-queryable placeholder."""
    if isinstance(issue_url, str):
        parsed = urlsplit(issue_url)
        parts = [part for part in parsed.path.split("/") if part]
        if (
            parsed.scheme == "https"
            and parsed.netloc.casefold() == "github.com"
            and not parsed.query
            and not parsed.fragment
            and len(parts) == 4
            and parts[2].casefold() == "issues"
            and parts[3].isascii()
            and parts[3].isdecimal()
            and int(parts[3]) == issue_number
            and parts[0]
            and parts[1]
        ):
            return f"{parts[0]}/{parts[1]}", True
    return f"legacy-unresolved/{feedback_id}", False


def _backfill_legacy_publications(bind: object) -> None:
    """Retain already-public issue locators without inventing v2 authority."""
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, status, github_issue_number, github_issue_url, "
                "created_at, updated_at FROM feedback "
                "WHERE github_issue_number IS NOT NULL"
            )
        ).mappings()
    )
    now = datetime.utcnow()
    for row in rows:
        try:
            feedback_id = int(row["id"])
            issue_number = int(row["github_issue_number"])
        except (TypeError, ValueError):
            continue
        if feedback_id <= 0 or issue_number <= 0:
            continue
        target_repo, _url_is_strict = _legacy_target_repo(
            row["github_issue_url"],
            issue_number,
            feedback_id,
        )
        # The legacy application assigned a positive issue number only after a
        # confirmed GitHub creation. Preserve that evidence even when a later
        # admin action changed the private lifecycle status or its stored URL
        # is no longer safe to expose.
        identity = (
            f"feedback:{feedback_id}:repo:{target_repo}:issue:{issue_number}"
        )
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM feedback_publication_outbox "
                "WHERE feedback_id = :feedback_id LIMIT 1"
            ),
            {"feedback_id": feedback_id},
        ).first()
        if exists is None:
            created_at = row["created_at"] or row["updated_at"] or now
            published_at = row["updated_at"] or row["created_at"] or now
            bind.execute(
                sa.text(
                    "INSERT INTO feedback_publication_outbox ("
                    "id, feedback_id, public_id, marker_version, target_repo, "
                    "consent_version, consented_at, payload_sha256, "
                    "public_content_sha256, state, delivery_evidence, "
                    "attempt_count, reconcile_count, available_at, "
                    "lease_token, lease_expires_at, github_issue_number, "
                    "github_issue_url, last_error_code, created_at, updated_at, "
                    "published_at) VALUES ("
                    ":id, :feedback_id, :public_id, 'legacy', :target_repo, "
                    "NULL, NULL, NULL, NULL, 'published', 'published', "
                    "0, 0, :available_at, NULL, NULL, :issue_number, "
                    ":issue_url, 'legacy_publication_migrated', :created_at, "
                    ":updated_at, :published_at)"
                ),
                {
                    "id": str(
                        uuid5(
                            NAMESPACE_URL,
                            "praxys-feedback-legacy-outbox:" + identity,
                        )
                    ),
                    "feedback_id": feedback_id,
                    "public_id": uuid5(
                        NAMESPACE_URL,
                        "praxys-feedback-legacy-public:" + identity,
                    ).hex,
                    "target_repo": target_repo,
                    "available_at": published_at,
                    "issue_number": issue_number,
                    "issue_url": row["github_issue_url"],
                    "created_at": created_at,
                    "updated_at": published_at,
                    "published_at": published_at,
                },
            )
        bind.execute(
            sa.text(
                "UPDATE feedback SET publication_status = 'published' "
                "WHERE id = :feedback_id"
            ),
            {"feedback_id": feedback_id},
        )


def upgrade() -> None:
    op.add_column(
        "feedback",
        sa.Column(
            "publication_status",
            sa.String(length=24),
            nullable=False,
            server_default="private",
        ),
    )
    op.add_column(
        "feedback",
        sa.Column("image_storage_provenance", sa.JSON(), nullable=True),
    )
    op.create_index(
        op.f("ix_feedback_publication_status"),
        "feedback",
        ["publication_status"],
        unique=False,
    )
    op.create_table(
        "feedback_publication_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feedback_id", sa.Integer(), nullable=True),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("marker_version", sa.String(length=12), nullable=False),
        sa.Column("target_repo", sa.String(length=200), nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=True),
        sa.Column("consented_at", sa.DateTime(), nullable=True),
        sa.Column("payload_sha256", sa.String(length=71), nullable=True),
        sa.Column("public_content_sha256", sa.String(length=71), nullable=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("delivery_evidence", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("reconcile_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("github_issue_number", sa.Integer(), nullable=True),
        sa.Column("github_issue_url", sa.String(length=500), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'sending', 'retry_wait', 'reconciling', "
            "'published', 'manual_review', 'held', 'cancelled')",
            name="ck_feedback_publication_outbox_state",
        ),
        sa.CheckConstraint(
            "delivery_evidence IN ('not_sent', 'ambiguous', 'published')",
            name="ck_feedback_publication_outbox_delivery_evidence",
        ),
        sa.CheckConstraint(
            "((marker_version = 'legacy' AND state = 'published' AND "
            "delivery_evidence = 'published' AND consent_version IS NULL AND "
            "consented_at IS NULL AND payload_sha256 IS NULL AND "
            "public_content_sha256 IS NULL) OR "
            "(marker_version = 'v2' AND consent_version IS NOT NULL AND "
            "consented_at IS NOT NULL AND payload_sha256 LIKE 'sha256:%' AND "
            "public_content_sha256 LIKE 'sha256:%') OR "
            "(marker_version = 'v1' AND state IN ('manual_review', "
            "'cancelled', 'published') AND consent_version IS NOT NULL AND "
            "consented_at IS NOT NULL AND payload_sha256 LIKE 'sha256:%' AND "
            "public_content_sha256 IS NULL))",
            name="ck_feedback_publication_outbox_binding_shape",
        ),
        sa.CheckConstraint(
            "((state = 'published' AND delivery_evidence = 'published') OR "
            "(state != 'published' AND delivery_evidence != 'published'))",
            name="ck_feedback_publication_outbox_published_evidence",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"], ["feedback.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feedback_id", name="uq_feedback_publication_feedback_id"
        ),
        sa.UniqueConstraint(
            "public_id", name="uq_feedback_publication_public_id"
        ),
    )
    op.create_index(
        "ix_feedback_publication_claim",
        "feedback_publication_outbox",
        ["state", "available_at"],
        unique=False,
    )
    op.create_index(
        "uq_feedback_publication_repo_issue_current",
        "feedback_publication_outbox",
        ["target_repo", "github_issue_number"],
        unique=True,
        postgresql_where=sa.text(
            "marker_version != 'legacy' AND github_issue_number IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "marker_version != 'legacy' AND github_issue_number IS NOT NULL"
        ),
    )
    op.create_table(
        "feedback_publication_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("outbox_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(length=36), nullable=False),
        sa.Column("target_repo", sa.String(length=200), nullable=False),
        sa.Column("payload_sha256", sa.String(length=71), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('in_flight', 'created', 'not_sent', 'rejected', "
            "'unknown', 'reconciled')",
            name="ck_feedback_publication_attempt_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_id"],
            ["feedback_publication_outbox.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "outbox_id",
            "attempt_no",
            name="uq_feedback_publication_attempt_no",
        ),
    )
    op.create_index(
        "ix_feedback_publication_attempt_outbox",
        "feedback_publication_attempts",
        ["outbox_id", "started_at"],
        unique=False,
    )
    _backfill_legacy_publications(op.get_bind())
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER "
            "trg_feedback_publication_outbox_binding_immutable "
            "BEFORE UPDATE OF feedback_id, public_id, marker_version, "
            "target_repo, consent_version, consented_at, payload_sha256, "
            "public_content_sha256 "
            "ON feedback_publication_outbox WHEN NOT ("
            "(OLD.feedback_id IS NEW.feedback_id OR "
            "(OLD.feedback_id IS NOT NULL AND NEW.feedback_id IS NULL)) AND "
            "OLD.public_id IS NEW.public_id AND "
            "OLD.marker_version IS NEW.marker_version AND "
            "OLD.target_repo IS NEW.target_repo AND "
            "OLD.consent_version IS NEW.consent_version AND "
            "OLD.consented_at IS NEW.consented_at AND "
            "OLD.payload_sha256 IS NEW.payload_sha256 AND "
            "OLD.public_content_sha256 IS NEW.public_content_sha256) BEGIN "
            "SELECT RAISE(ABORT, "
            "'feedback publication binding is immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_feedback_publication_attempt_binding_immutable "
            "BEFORE UPDATE OF outbox_id, attempt_no, lease_token, target_repo, "
            "payload_sha256, started_at ON feedback_publication_attempts BEGIN "
            "SELECT RAISE(ABORT, "
            "'feedback publication attempt binding is immutable'); END"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_feedback_publication_evidence_published_terminal "
            "BEFORE UPDATE OF delivery_evidence ON "
            "feedback_publication_outbox WHEN "
            "OLD.delivery_evidence = 'published' AND "
            "NEW.delivery_evidence != 'published' BEGIN "
            "SELECT RAISE(ABORT, "
            "'published feedback evidence is terminal'); END"
        )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION feedback_publication_outbox_binding_immutable() "
            "RETURNS trigger AS $$ BEGIN "
            "IF (OLD.feedback_id IS DISTINCT FROM NEW.feedback_id AND NOT "
            "(OLD.feedback_id IS NOT NULL AND NEW.feedback_id IS NULL)) OR "
            "OLD.public_id IS DISTINCT FROM NEW.public_id OR "
            "OLD.marker_version IS DISTINCT FROM NEW.marker_version OR "
            "OLD.target_repo IS DISTINCT FROM NEW.target_repo OR "
            "OLD.consent_version IS DISTINCT FROM NEW.consent_version OR "
            "OLD.consented_at IS DISTINCT FROM NEW.consented_at OR "
            "OLD.payload_sha256 IS DISTINCT FROM NEW.payload_sha256 OR "
            "OLD.public_content_sha256 IS DISTINCT FROM "
            "NEW.public_content_sha256 OR "
            "(OLD.delivery_evidence = 'published' AND "
            "NEW.delivery_evidence IS DISTINCT FROM 'published') THEN "
            "RAISE EXCEPTION 'feedback publication binding is immutable'; "
            "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_feedback_publication_outbox_binding_immutable "
            "BEFORE UPDATE ON feedback_publication_outbox FOR EACH ROW "
            "EXECUTE FUNCTION feedback_publication_outbox_binding_immutable()"
        )
        op.execute(
            "CREATE FUNCTION feedback_publication_attempt_binding_immutable() "
            "RETURNS trigger AS $$ BEGIN "
            "IF OLD.outbox_id IS DISTINCT FROM NEW.outbox_id OR "
            "OLD.attempt_no IS DISTINCT FROM NEW.attempt_no OR "
            "OLD.lease_token IS DISTINCT FROM NEW.lease_token OR "
            "OLD.target_repo IS DISTINCT FROM NEW.target_repo OR "
            "OLD.payload_sha256 IS DISTINCT FROM NEW.payload_sha256 OR "
            "OLD.started_at IS DISTINCT FROM NEW.started_at THEN "
            "RAISE EXCEPTION 'feedback publication attempt binding is immutable'; "
            "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"
        )
        op.execute(
            "CREATE TRIGGER "
            "trg_feedback_publication_attempt_binding_immutable "
            "BEFORE UPDATE ON feedback_publication_attempts FOR EACH ROW "
            "EXECUTE FUNCTION feedback_publication_attempt_binding_immutable()"
        )


def downgrade() -> None:
    bind = op.get_bind()
    publication_evidence_count = bind.execute(
        sa.text(
            "SELECT "
            "(SELECT COUNT(*) FROM feedback_publication_outbox) + "
            "(SELECT COUNT(*) FROM feedback_publication_attempts)"
        )
    ).scalar_one()
    screenshot_evidence_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM feedback WHERE image_keys IS NOT NULL OR "
            "image_storage_provenance IS NOT NULL"
        )
    ).scalar_one()
    if publication_evidence_count or screenshot_evidence_count:
        raise RuntimeError(
            "Cannot downgrade while feedback publication or screenshot "
            "storage evidence exists; preserve every ledger and locator, "
            "engage the kill switch, and deploy a forward application fix."
        )
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_evidence_published_terminal"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_attempt_binding_immutable"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_outbox_binding_immutable"
        )
    elif dialect == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_attempt_binding_immutable "
            "ON feedback_publication_attempts"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS "
            "feedback_publication_attempt_binding_immutable()"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS "
            "trg_feedback_publication_outbox_binding_immutable "
            "ON feedback_publication_outbox"
        )
        op.execute(
            "DROP FUNCTION IF EXISTS "
            "feedback_publication_outbox_binding_immutable()"
        )
    op.drop_index(
        "ix_feedback_publication_attempt_outbox",
        table_name="feedback_publication_attempts",
    )
    op.drop_table("feedback_publication_attempts")
    op.drop_index(
        "ix_feedback_publication_claim",
        table_name="feedback_publication_outbox",
    )
    op.drop_index(
        "uq_feedback_publication_repo_issue_current",
        table_name="feedback_publication_outbox",
    )
    op.drop_table("feedback_publication_outbox")
    op.drop_index(
        op.f("ix_feedback_publication_status"),
        table_name="feedback",
    )
    op.drop_column("feedback", "publication_status")
    op.drop_column("feedback", "image_storage_provenance")
