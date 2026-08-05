"""Persistence helpers for append-only agent decisions and outcomes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import AgentDecision, AgentOutcome


def canonical_json_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for a JSON-compatible value."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def record_decision(
    db: Session,
    *,
    loop: str,
    subject_type: str,
    subject_ref: str,
    policy_name: str,
    policy_version: str,
    prompt_version: str | None,
    model: str | None,
    mode: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
) -> AgentDecision:
    """Append a structured decision without committing the surrounding unit of work."""
    decision = AgentDecision(
        id=str(uuid4()),
        loop=loop,
        subject_type=subject_type,
        subject_ref=subject_ref,
        policy_name=policy_name,
        policy_version=policy_version,
        prompt_version=prompt_version,
        model=model,
        mode=mode,
        input_sha256=canonical_json_hash(input_data),
        input_json=input_data,
        output_json=output_data,
    )
    db.add(decision)
    db.flush()
    return decision


def latest_decision(
    db: Session,
    *,
    loop: str,
    subject_type: str,
    subject_ref: str,
) -> AgentDecision | None:
    """Return the newest decision for one loop subject."""
    return (
        db.query(AgentDecision)
        .filter(
            AgentDecision.loop == loop,
            AgentDecision.subject_type == subject_type,
            AgentDecision.subject_ref == subject_ref,
        )
        .order_by(AgentDecision.created_at.desc(), AgentDecision.id.desc())
        .first()
    )


def latest_decisions_for_subjects(
    db: Session,
    *,
    loop: str,
    subject_type: str,
    subject_refs: Iterable[str],
) -> dict[str, AgentDecision]:
    """Return the newest decision for each requested subject reference."""
    refs = list(dict.fromkeys(subject_refs))
    if not refs:
        return {}
    rows = (
        db.query(AgentDecision)
        .filter(
            AgentDecision.loop == loop,
            AgentDecision.subject_type == subject_type,
            AgentDecision.subject_ref.in_(refs),
        )
        .order_by(
            AgentDecision.created_at.desc(),
            AgentDecision.id.desc(),
        )
        .all()
    )
    latest: dict[str, AgentDecision] = {}
    for row in rows:
        latest.setdefault(row.subject_ref, row)
    return latest


def latest_outcomes_for_decisions(
    db: Session,
    *,
    decision_ids: Iterable[str],
    outcome_types: Iterable[str],
) -> dict[str, AgentOutcome]:
    """Return the newest matching outcome for each requested decision."""
    ids = list(dict.fromkeys(decision_ids))
    kinds = list(dict.fromkeys(outcome_types))
    if not ids or not kinds:
        return {}
    rows = (
        db.query(AgentOutcome)
        .filter(
            AgentOutcome.decision_id.in_(ids),
            AgentOutcome.outcome_type.in_(kinds),
        )
        .order_by(
            AgentOutcome.observed_at.desc(),
            AgentOutcome.id.desc(),
        )
        .all()
    )
    latest: dict[str, AgentOutcome] = {}
    for row in rows:
        latest.setdefault(row.decision_id, row)
    return latest


def record_outcome(
    db: Session,
    *,
    decision_id: str,
    outcome_type: str,
    source: str,
    payload: dict[str, Any],
    observed_at: datetime | None = None,
    dedupe_key: str | None = None,
) -> AgentOutcome | None:
    """Append an outcome, returning ``None`` when a snapshot was already recorded."""
    fingerprint_seed = dedupe_key or str(uuid4())
    fingerprint = canonical_json_hash(
        {
            "outcome_type": outcome_type,
            "source": source,
            "key": fingerprint_seed,
        }
    )
    outcome = AgentOutcome(
        decision_id=decision_id,
        outcome_type=outcome_type,
        source=source,
        fingerprint=fingerprint,
        payload_json=payload,
        observed_at=observed_at or datetime.utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(outcome)
            db.flush()
    except IntegrityError:
        existing = (
            db.query(AgentOutcome.id)
            .filter(
                AgentOutcome.decision_id == decision_id,
                AgentOutcome.fingerprint == fingerprint,
            )
            .first()
        )
        if existing:
            return None
        raise
    return outcome
