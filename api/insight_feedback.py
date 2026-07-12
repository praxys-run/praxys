"""Shared durable state helpers for generated Coach insight feedback."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from api.views import utc_isoformat

_DATASET_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
GENERATION_PROVENANCE_KEY = "_generation_provenance"


def is_dataset_hash(value: object) -> bool:
    """Return whether ``value`` is a generated insight dataset hash."""
    return isinstance(value, str) and _DATASET_HASH_RE.fullmatch(value) is not None


def feedback_state(
    value: object,
    dataset_hash: object,
) -> dict[str, str] | None:
    """Return a valid feedback state for ``dataset_hash``, else ``None``."""
    if not is_dataset_hash(dataset_hash) or not isinstance(value, dict):
        return None
    vote = value.get("vote")
    submitted_at = value.get("submitted_at")
    if (
        value.get("dataset_hash") != dataset_hash
        or vote not in {"up", "down"}
        or not isinstance(submitted_at, str)
        or not submitted_at
    ):
        return None
    return {
        "dataset_hash": dataset_hash,
        "vote": vote,
        "submitted_at": submitted_at,
    }


def feedback_payload(row: Any) -> dict[str, str]:
    """Serialize one durable Coach feedback row for API/meta use."""
    submitted_at = utc_isoformat(row.submitted_at)
    if submitted_at is None:
        raise ValueError("Insight feedback is missing submitted_at")
    return {
        "dataset_hash": row.dataset_hash,
        "vote": row.vote,
        "submitted_at": submitted_at,
    }


@lru_cache(maxsize=1)
def _known_science_ids() -> dict[str, frozenset[str]]:
    """Return the configured theory ids accepted for telemetry dimensions."""
    from analysis.science import PILLARS, list_theories

    return {
        pillar: frozenset(theory.id for theory in list_theories(pillar))
        for pillar in PILLARS
    }


def validated_feedback_pillars(value: object) -> dict[str, str]:
    """Keep only known pillar/theory pairs for low-cardinality telemetry."""
    if not isinstance(value, dict):
        return {}
    known = _known_science_ids()
    return {
        pillar: theory_id
        for pillar, theory_id in value.items()
        if (
            pillar in known
            and isinstance(theory_id, str)
            and theory_id in known[pillar]
        )
    }


def build_generation_provenance(
    model: object,
    pillars: object,
    *,
    run_started_at: str | None = None,
    source_revisions: object = None,
) -> dict[str, object]:
    """Build server-owned metadata for the exact generated dataset version."""
    provenance: dict[str, object] = {
        "model": model if isinstance(model, str) else "unknown",
        "pillars": validated_feedback_pillars(pillars),
    }
    if run_started_at:
        provenance["run_started_at"] = run_started_at
    if isinstance(source_revisions, dict):
        provenance["source_revisions"] = {
            key: revision
            for key, revision in source_revisions.items()
            if (
                isinstance(key, str)
                and isinstance(revision, int)
                and not isinstance(revision, bool)
                and revision >= 0
            )
        }
    return provenance


def feedback_telemetry_dimensions(meta: object) -> tuple[str, dict[str, str]]:
    """Read immutable generation dimensions or default external pushes to unknown."""
    if not isinstance(meta, dict):
        return "unknown", {}
    provenance = meta.get(GENERATION_PROVENANCE_KEY)
    if not isinstance(provenance, dict):
        return "unknown", {}
    model = provenance.get("model")
    return (
        model if isinstance(model, str) else "unknown",
        validated_feedback_pillars(provenance.get("pillars")),
    )

def merge_feedback_meta(
    db: Session,
    user_id: str,
    insight_type: str,
    incoming: dict[str, Any],
    existing: object = None,
) -> dict[str, Any]:
    """Strip client feedback and restore the durable vote for this dataset."""
    from db.models import AiInsightFeedback

    merged = dict(incoming)
    merged.pop("feedback", None)
    existing_meta = existing if isinstance(existing, dict) else {}
    existing_feedback = feedback_state(
        existing_meta.get("feedback"),
        merged.get("dataset_hash"),
    )
    if existing_feedback is not None:
        merged["feedback"] = existing_feedback

    dataset_hash = merged.get("dataset_hash")
    if not is_dataset_hash(dataset_hash):
        return merged
    durable = db.query(AiInsightFeedback).filter(
        AiInsightFeedback.user_id == user_id,
        AiInsightFeedback.insight_type == insight_type,
        AiInsightFeedback.dataset_hash == dataset_hash,
    ).first()
    if durable is not None:
        merged["feedback"] = feedback_payload(durable)
    return merged
