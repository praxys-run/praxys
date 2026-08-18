"""Persistence and API helpers for direct 10K baseline confirmation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analysis.config import effective_athlete_date, load_config_from_db
from analysis.data_loader import load_activity_sample_coverage, load_data_from_db
from analysis.road_10k_baseline import (
    Road10KBaselineActivity,
    Road10KBaselineConfirmation,
    build_road_10k_goal,
    evaluate_road_10k_baseline,
)
from analysis.road_10k_contract import (
    ROAD_10K_BASELINE_SNAPSHOT_VERSION,
    ROAD_10K_CONTRACT_DIGEST,
    ROAD_10K_POLICY_VERSION,
    ROAD_10K_SCIENCE_DECISION_ID,
)
from db.cache_revision import bump_revisions
from db.models import (
    Road10KBaselineConfirmation as Road10KBaselineConfirmationRow,
    Road10KBaselineSnapshot,
)
from db.plan_ledger import lock_plan_writes


class Road10KBaselineConflict(RuntimeError):
    pass


class Road10KBaselineNotFound(LookupError):
    pass


class Road10KBaselineInvalid(ValueError):
    pass


class Road10KBaselineForbidden(RuntimeError):
    pass


class _BaselinePurposeScope:
    def __init__(
        self,
        source: str | None,
        source_goal_id: str | None,
        source_goal_revision: str | None,
    ) -> None:
        self.source = source
        self.source_goal_id = source_goal_id
        self.source_goal_revision = source_goal_revision


def build_road_10k_baseline_view(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
    purpose_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the current direct-baseline view for a 10K plan purpose."""
    config, goal_source, _scope = _resolve_context(
        db,
        user_id=user_id,
        purpose_selection=purpose_selection,
    )
    goal = build_road_10k_goal(goal_source)
    athlete_today = effective_athlete_date(config, now=now)
    activities = _load_candidate_activities(
        db,
        user_id=user_id,
        activity_source=config.preferences.get("activities"),
    )
    confirmations = _confirmation_inputs(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
    )
    evaluation = evaluate_road_10k_baseline(
        goal,
        athlete_today=athlete_today,
        activities=activities,
        confirmations=confirmations,
    )
    return {
        "goal_kind": goal.goal_kind,
        "goal": {
            "goal_kind": goal.goal_kind,
            "distance": goal.distance,
            "target_time_sec": goal.target_time_sec,
            "race_date": str(goal_source.get("race_date") or "") or None,
            "eligible": goal.eligible,
        },
        "baseline": {
            "policy_version": ROAD_10K_POLICY_VERSION,
            "science_decision_id": ROAD_10K_SCIENCE_DECISION_ID,
            "contract_digest": ROAD_10K_CONTRACT_DIGEST,
            "baseline_snapshot_version": ROAD_10K_BASELINE_SNAPSHOT_VERSION,
            "status": evaluation.status,
            "readiness": evaluation.readiness,
            "history_search_complete": True,
            "full_activity_only": True,
            "history_cutoff_completed_days": 56,
            "alternatives": list(evaluation.alternatives),
            "evidence": _serialize_evidence(evaluation.evidence),
            "candidates": [
                _serialize_candidate(candidate)
                for candidate in evaluation.candidates
            ],
            "benchmark": {
                "available": evaluation.readiness != "sufficient_baseline",
                "automatic_scheduling": False,
                "explicit_choice_required": True,
            },
            "science_note": {
                "name": "Direct 10K baseline",
                "description": (
                    "Only current direct 10K race or explicit all-out 10K "
                    "history can qualify. The 56-day freshness guardrail and "
                    "the optional self-selected benchmark path are reviewed "
                    "product boundaries, not universal physiological cutoffs."
                ),
                "citations": [
                    {
                        "label": "Science Decision Record",
                        "url": "https://github.com/praxys-run/praxys/blob/main/data/science/decisions/sdr-road-10k-plan-generation-policy-v2.yaml",
                    },
                ],
            },
        },
    }


def confirm_road_10k_history_candidate(
    db: Session,
    *,
    user_id: str,
    activity_id: str,
    response: str,
    measured_10k: bool,
    elapsed_timing_confirmed: bool,
    idempotency_key: str,
    supersedes_confirmation_id: str | None = None,
    now: datetime | None = None,
    purpose_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one owner-scoped 10K history confirmation."""
    timestamp = _utc_naive(now or datetime.utcnow())
    db.rollback()
    lock_plan_writes(db, user_id)
    config, goal_source, _scope = _resolve_context(
        db,
        user_id=user_id,
        purpose_selection=purpose_selection,
    )
    goal = build_road_10k_goal(goal_source)
    if not goal.eligible:
        raise Road10KBaselineForbidden("BASELINE_NOT_REQUIRED")
    activity = _activity_by_id(
        db,
        user_id=user_id,
        activity_source=config.preferences.get("activities"),
        activity_id=activity_id,
    )
    if activity is None:
        raise Road10KBaselineNotFound(activity_id)
    if abs(float(activity.distance_km or 0.0) - 10.0) > 0.5:
        raise Road10KBaselineForbidden("ACTIVITY_OUTSIDE_10K_REVIEW_WINDOW")

    payload = {
        "activity_id": activity_id,
        "response": response,
        "measured_10k": measured_10k,
        "elapsed_timing_confirmed": elapsed_timing_confirmed,
        "supersedes_confirmation_id": supersedes_confirmation_id,
        "goal_signature": goal.goal_signature,
        "purpose": dict(purpose_selection) if purpose_selection is not None else None,
    }
    fingerprint = _request_fingerprint(payload)
    existing = _find_idempotent_confirmation(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    if existing is not None:
        return {
            "replayed": True,
            "confirmation": _serialize_confirmation_row(existing),
            "baseline": build_road_10k_baseline_view(
                db,
                user_id=user_id,
                now=timestamp,
                purpose_selection=purpose_selection,
            )["baseline"],
        }
    predecessor = _resolve_confirmation_predecessor(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
        activity_id=activity_id,
        supersedes_confirmation_id=supersedes_confirmation_id,
    )
    row = Road10KBaselineConfirmationRow(
        lineage_id=predecessor.lineage_id if predecessor is not None else str(uuid4()),
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        version=(int(predecessor.version) + 1) if predecessor is not None else 1,
        supersedes_id=predecessor.id if predecessor is not None else None,
        activity_id=activity_id,
        response=response,
        measured_10k=bool(measured_10k),
        elapsed_timing_confirmed=bool(elapsed_timing_confirmed),
        request_fingerprint=fingerprint,
        idempotency_key=idempotency_key,
        created_at=timestamp,
    )
    created = _insert_idempotent(db, row)
    if not created:
        return {
            "replayed": True,
            "confirmation": _serialize_confirmation_row(row),
            "baseline": build_road_10k_baseline_view(
                db,
                user_id=user_id,
                now=timestamp,
                purpose_selection=purpose_selection,
            )["baseline"],
        }
    _record_snapshot(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        confirmation=row,
        activity=activity,
        created_at=timestamp,
    )
    bump_revisions(db, user_id, ["goals"])
    db.commit()
    return {
        "replayed": False,
        "confirmation": _serialize_confirmation_row(row),
        "baseline": build_road_10k_baseline_view(
            db,
            user_id=user_id,
            now=timestamp,
            purpose_selection=purpose_selection,
        )["baseline"],
    }


def resolve_road_10k_baseline_snapshot_id(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    evidence: Mapping[str, Any] | None,
) -> str | None:
    """Return the snapshot id for the currently selected direct evidence."""
    if not evidence:
        return None
    activity_id = str(evidence.get("activity_id") or "").strip()
    observed_date = _parse_date(evidence.get("observed_date"))
    if not activity_id or observed_date is None:
        return None
    row = db.execute(
        select(Road10KBaselineSnapshot)
        .where(
            Road10KBaselineSnapshot.user_id == user_id,
            Road10KBaselineSnapshot.goal_signature == goal_signature,
            Road10KBaselineSnapshot.source_id == activity_id,
            Road10KBaselineSnapshot.observed_date == observed_date,
            Road10KBaselineSnapshot.qualification_status == "direct_current",
        )
        .order_by(
            Road10KBaselineSnapshot.created_at.desc(),
            Road10KBaselineSnapshot.version.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    return row.id if row is not None else None


def _resolve_context(
    db: Session,
    *,
    user_id: str,
    purpose_selection: Mapping[str, Any] | None,
) -> tuple[Any, dict[str, Any], _BaselinePurposeScope]:
    config = load_config_from_db(user_id, db)
    if purpose_selection is not None:
        from api.plan_generation_capabilities import resolve_plan_generation_purpose

        resolved = resolve_plan_generation_purpose(
            db,
            user_id=user_id,
            selection=purpose_selection,
        )
        return (
            config,
            dict(resolved.goal),
            _BaselinePurposeScope(
                resolved.source,
                resolved.source_goal_id,
                resolved.source_goal_revision,
            ),
        )
    goal_source = dict(config.goal or {})
    from api.plan_generation_capabilities import current_goal_reference

    current_goal = current_goal_reference(user_id=user_id, goal=goal_source)
    return (
        config,
        goal_source,
        _BaselinePurposeScope(
            "current_goal" if current_goal is not None else None,
            current_goal.goal_id if current_goal is not None else None,
            current_goal.revision if current_goal is not None else None,
        ),
    )


def _load_candidate_activities(
    db: Session,
    *,
    user_id: str,
    activity_source: str | None,
) -> list[Road10KBaselineActivity]:
    from api.goal_baseline import _deduplicate_activity_frame

    data = load_data_from_db(user_id, db, include_plan=False)
    activities = data.get("activities", pd.DataFrame())
    splits = data.get("splits", pd.DataFrame())
    if not isinstance(activities, pd.DataFrame) or activities.empty:
        return []
    frame = _deduplicate_activity_frame(activities.copy(), activity_source)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    candidate_ids = [
        str(row.activity_id)
        for row in frame.itertuples(index=False)
        if getattr(row, "distance_km", None) is not None
        and getattr(row, "duration_sec", None) is not None
        and abs(float(getattr(row, "distance_km", 0.0)) - 10.0) <= 0.5
        and str(getattr(row, "activity_type", "")).strip().casefold()
        == "running"
    ]
    coverage = (
        load_activity_sample_coverage(user_id, db, candidate_ids)
        if candidate_ids
        else pd.DataFrame()
    )
    coverage_by_activity: dict[str, dict[str, Any]] = {}
    if isinstance(coverage, pd.DataFrame) and not coverage.empty:
        grouped = coverage.groupby("activity_id", dropna=False).agg(
            {"observed_duration_sec": "sum", "gap_count": "sum"}
        )
        coverage_by_activity = {
            str(activity_id): {
                "observed_duration_sec": (
                    None
                    if pd.isna(row["observed_duration_sec"])
                    else float(row["observed_duration_sec"])
                ),
                "gap_count": 0 if pd.isna(row["gap_count"]) else int(row["gap_count"]),
            }
            for activity_id, row in grouped.iterrows()
        }
    split_count_by_activity: dict[str, int] = {}
    if (
        isinstance(splits, pd.DataFrame)
        and not splits.empty
        and "activity_id" in splits.columns
    ):
        split_count_by_activity = {
            str(activity_id): int(count)
            for activity_id, count in splits.groupby("activity_id").size().items()
        }
    candidates: list[Road10KBaselineActivity] = []
    for row in frame.itertuples(index=False):
        observed_date = getattr(row, "date", None)
        if not isinstance(observed_date, date):
            continue
        if str(getattr(row, "activity_type", "")).strip().casefold() != "running":
            continue
        distance_km = getattr(row, "distance_km", None)
        duration_sec = getattr(row, "duration_sec", None)
        if distance_km is None or duration_sec is None:
            continue
        if abs(float(distance_km) - 10.0) > 0.5:
            continue
        activity_id = str(getattr(row, "activity_id"))
        coverage_info = coverage_by_activity.get(activity_id, {})
        candidates.append(
            Road10KBaselineActivity(
                activity_id=activity_id,
                observed_date=observed_date,
                distance_km=float(distance_km),
                duration_sec=float(duration_sec),
                activity_type=str(getattr(row, "activity_type", "") or "running"),
                source=str(getattr(row, "source", "") or "") or None,
                split_count=split_count_by_activity.get(activity_id, 0),
                sample_observed_duration_sec=coverage_info.get("observed_duration_sec"),
                timing_gap_count=int(coverage_info.get("gap_count", 0) or 0),
            )
        )
    candidates.sort(key=lambda item: (item.observed_date, item.activity_id), reverse=True)
    return candidates


def _activity_by_id(
    db: Session,
    *,
    user_id: str,
    activity_source: str | None,
    activity_id: str,
) -> Road10KBaselineActivity | None:
    for candidate in _load_candidate_activities(
        db,
        user_id=user_id,
        activity_source=activity_source,
    ):
        if candidate.activity_id == activity_id:
            return candidate
    return None


def _confirmation_inputs(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
) -> list[Road10KBaselineConfirmation]:
    rows = db.execute(
        select(Road10KBaselineConfirmationRow).where(
            Road10KBaselineConfirmationRow.user_id == user_id,
            Road10KBaselineConfirmationRow.goal_signature == goal_signature,
        )
    ).scalars().all()
    return [
        Road10KBaselineConfirmation(
            activity_id=str(row.activity_id),
            response=str(row.response),
            measured_10k=bool(row.measured_10k),
            elapsed_timing_confirmed=bool(row.elapsed_timing_confirmed),
            created_at=row.created_at,
        )
        for row in rows
    ]


def _resolve_confirmation_predecessor(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    activity_id: str,
    supersedes_confirmation_id: str | None,
) -> Road10KBaselineConfirmationRow | None:
    if supersedes_confirmation_id:
        row = db.get(Road10KBaselineConfirmationRow, supersedes_confirmation_id)
        if (
            row is None
            or row.user_id != user_id
            or row.goal_signature != goal_signature
            or row.activity_id != activity_id
        ):
            raise Road10KBaselineNotFound(supersedes_confirmation_id)
        return row
    return db.execute(
        select(Road10KBaselineConfirmationRow)
        .where(
            Road10KBaselineConfirmationRow.user_id == user_id,
            Road10KBaselineConfirmationRow.goal_signature == goal_signature,
            Road10KBaselineConfirmationRow.activity_id == activity_id,
        )
        .order_by(
            Road10KBaselineConfirmationRow.created_at.desc(),
            Road10KBaselineConfirmationRow.version.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def _record_snapshot(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    goal_snapshot: Mapping[str, Any],
    confirmation: Road10KBaselineConfirmationRow,
    activity: Road10KBaselineActivity,
    created_at: datetime,
) -> None:
    predecessor = db.execute(
        select(Road10KBaselineSnapshot)
        .where(
            Road10KBaselineSnapshot.user_id == user_id,
            Road10KBaselineSnapshot.goal_signature == goal_signature,
            Road10KBaselineSnapshot.source_id == activity.activity_id,
        )
        .order_by(
            Road10KBaselineSnapshot.created_at.desc(),
            Road10KBaselineSnapshot.version.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    qualified = (
        confirmation.response in {"race", "intentional_all_out"}
        and confirmation.measured_10k
        and confirmation.elapsed_timing_confirmed
    )
    db.add(
        Road10KBaselineSnapshot(
            lineage_id=(
                predecessor.lineage_id
                if predecessor is not None
                else str(uuid4())
            ),
            user_id=user_id,
            goal_signature=goal_signature,
            goal_snapshot=dict(goal_snapshot),
            version=(int(predecessor.version) + 1) if predecessor is not None else 1,
            supersedes_id=predecessor.id if predecessor is not None else None,
            source_kind="history_confirmation",
            source_id=activity.activity_id,
            provenance=(
                confirmation.response if qualified else "unqualified"
            ),
            observed_date=activity.observed_date,
            distance_km=activity.distance_km,
            elapsed_time_sec=activity.duration_sec,
            measured_10k=bool(confirmation.measured_10k),
            elapsed_timing_confirmed=bool(
                confirmation.elapsed_timing_confirmed
            ),
            qualification_status=(
                "direct_current" if qualified else "incomparable"
            ),
            change_comparability="not_assessed",
            invalidators=[],
            created_at=created_at,
        )
    )


def _find_idempotent_confirmation(
    db: Session,
    *,
    user_id: str,
    idempotency_key: str,
    request_fingerprint: str,
) -> Road10KBaselineConfirmationRow | None:
    existing = db.execute(
        select(Road10KBaselineConfirmationRow).where(
            Road10KBaselineConfirmationRow.user_id == user_id,
            Road10KBaselineConfirmationRow.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is None:
        return None
    if existing.request_fingerprint != request_fingerprint:
        raise Road10KBaselineConflict("ROAD_10K_BASELINE_IDEMPOTENCY_CONFLICT")
    return existing


def _insert_idempotent(db: Session, row: Road10KBaselineConfirmationRow) -> bool:
    try:
        db.add(row)
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = _find_idempotent_confirmation(
            db,
            user_id=row.user_id,
            idempotency_key=row.idempotency_key or "",
            request_fingerprint=row.request_fingerprint,
        )
        if existing is None:
            raise Road10KBaselineConflict("ROAD_10K_BASELINE_IDEMPOTENCY_CONFLICT")
        row.id = existing.id
        row.lineage_id = existing.lineage_id
        row.version = existing.version
        row.created_at = existing.created_at
        return False
    return True


def _serialize_evidence(evidence) -> dict[str, Any] | None:
    if evidence is None:
        return None
    payload = asdict(evidence)
    return {
        **payload,
        "observed_date": evidence.observed_date.isoformat(),
    }


def _serialize_candidate(candidate) -> dict[str, Any]:
    payload = asdict(candidate)
    payload["observed_date"] = candidate.observed_date.isoformat()
    return payload


def _serialize_confirmation_row(
    row: Road10KBaselineConfirmationRow,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "lineage_id": row.lineage_id,
        "version": int(row.version),
        "supersedes_id": row.supersedes_id,
        "activity_id": row.activity_id,
        "response": row.response,
        "measured_10k": bool(row.measured_10k),
        "elapsed_timing_confirmed": bool(row.elapsed_timing_confirmed),
        "created_at": row.created_at.isoformat(),
    }


def _request_fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc_naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None

