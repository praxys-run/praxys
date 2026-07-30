"""separate plan ownership from workout origin

Revision ID: 5e6f708192a3
Revises: 4d5e6f708192
Create Date: 2026-07-30
"""
from __future__ import annotations

import json
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision: str = "5e6f708192a3"
down_revision: Union[str, Sequence[str], None] = "4d5e6f708192"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _meta_dict(raw_meta: object) -> dict:
    if isinstance(raw_meta, dict):
        return raw_meta
    if isinstance(raw_meta, str):
        try:
            parsed = json.loads(raw_meta)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _canonical_id(canonical_key: object) -> str | None:
    prefix, separator, candidate = str(canonical_key or "").partition(":")
    if not separator or prefix.strip().casefold() not in {"ai", "praxys"}:
        return None
    try:
        return str(UUID(candidate))
    except (ValueError, AttributeError):
        return None


def upgrade() -> None:
    connection = op.get_bind()
    op.add_column(
        "training_plans",
        sa.Column(
            "workout_origin",
            sa.String(length=30),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "plan_deliveries",
        sa.Column("canonical_id", sa.String(length=36), nullable=True),
    )

    plan_rows = connection.execute(
        sa.text(
            "SELECT id, source, meta, workout_origin FROM training_plans"
        )
    ).mappings().all()
    for row in plan_rows:
        source = str(row["source"] or "").strip().casefold()
        if source in {"ai", "praxys"}:
            origin = (
                "accepted_target"
                if isinstance(
                    _meta_dict(row["meta"]).get("accepted_from_target"),
                    dict,
                )
                else str(row["workout_origin"] or "legacy")
            )
            connection.execute(
                sa.text(
                    "UPDATE training_plans "
                    "SET workout_origin = :origin "
                    "WHERE id = :plan_id"
                ),
                {
                    "origin": origin,
                    "plan_id": row["id"],
                },
            )
        else:
            connection.execute(
                sa.text(
                    "UPDATE training_plans SET workout_origin = :origin "
                    "WHERE id = :plan_id"
                ),
                {"origin": "imported", "plan_id": row["id"]},
            )

    delivery_rows = connection.execute(
        sa.text(
            "SELECT id, user_id, target, canonical_key, workout_version, "
            "canonical_id FROM plan_deliveries"
        )
    ).mappings().all()
    identities: dict[tuple[str, str, str, str], str] = {}
    for row in delivery_rows:
        canonical_id = row["canonical_id"] or _canonical_id(
            row["canonical_key"]
        )
        if not canonical_id:
            continue
        identity = (
            row["user_id"],
            row["target"],
            canonical_id,
            row["workout_version"],
        )
        duplicate_id = identities.get(identity)
        if duplicate_id is not None and duplicate_id != row["id"]:
            raise RuntimeError(
                "Duplicate plan delivery canonical identity "
                f"{identity!r}: {duplicate_id}, {row['id']}"
            )
        identities[identity] = row["id"]
        connection.execute(
            sa.text(
                "UPDATE plan_deliveries "
                "SET canonical_id = :canonical_id, "
                "canonical_key = :canonical_key "
                "WHERE id = :delivery_id"
            ),
            {
                "canonical_id": canonical_id,
                # Frozen for older workers that still derive this key from
                # source="ai". Modern code uses canonical_id directly.
                "canonical_key": f"ai:{canonical_id}",
                "delivery_id": row["id"],
            },
        )

    op.create_index(
        "uq_plan_delivery_canonical_version_target",
        "plan_deliveries",
        ["user_id", "target", "canonical_id", "workout_version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_plan_delivery_canonical_version_target",
        table_name="plan_deliveries",
    )
    op.drop_column("plan_deliveries", "canonical_id")
    op.drop_column("training_plans", "workout_origin")
