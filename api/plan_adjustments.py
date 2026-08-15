"""Opt-in conservative plan adjustment lifecycle."""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import (
    PRAXYS_PLAN_SOURCES,
    PRAXYS_PLAN_WRITE_SOURCE,
    athlete_local_date,
    load_config_from_db,
)
from analysis.data_loader import load_plan_adjustment_inputs
from analysis.metrics import daily_training_signal
from analysis.plan_adjustments import (
    PlanAdjustmentDecision,
    TargetEvidenceState,
    evaluate_conservative_plan_adjustment,
)
from analysis.science import load_active_science
from api.deps import _compute_recovery_analysis, _recovery_for_guidance
from api.plan_reconciliation import classify_plan_delivery_snapshot
from api.stryd_access import without_stryd_delivery_metadata
from api.views import utc_isoformat
from db.cache_revision import bump_revisions
from db.models import (
    PlanDelivery,
    PlanRevision,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    TrainingPlan,
)
from db.plan_ledger import (
    lock_plan_writes,
    plan_snapshot,
    record_plan_revision_idempotent,
)

logger = logging.getLogger(__name__)

# ESTIMATE -- product data-quality guardrail, not an exercise-science
# threshold. A target calendar older than this cannot prove that the delivered
# workout is still unchanged, so automatic mutation fails closed.
TARGET_CALENDAR_MAX_AGE = timedelta(hours=24)

_AUTO_OPERATION = "auto_adjustment"
_CONTEXT_PILOT_OPERATION = "context_pilot_accept"
_UNDO_OPERATION = "auto_adjustment_undo"
_DELIVERY_OPERATION = "auto_adjustment_delivery"
_UNDO_DELIVERY_OPERATION = "auto_adjustment_undo_delivery"

_REST_MUTATION_FIELDS = (
    "activity_type",
    "workout_type",
    "planned_duration_min",
    "planned_distance_km",
    "target_power_min",
    "target_power_max",
    "target_hr_min",
    "target_hr_max",
    "target_pace_min",
    "target_pace_max",
    "workout_description",
    "workout_structure_version",
    "workout_structure",
    "start_time",
    "meta",
)


class PlanAdjustmentNotFoundError(LookupError):
    """Requested automatic adjustment does not exist for this user."""


class PlanAdjustmentConflictError(RuntimeError):
    """The canonical workout no longer matches the reversible snapshot."""


def _target_evidence_state(
    *,
    canonical: TrainingPlan,
    delivery: PlanDelivery | None,
    calendar_sync: PlanTargetCalendarSync | None,
    observations: list[PlanTargetWorkout],
    current_date: date,
    now: datetime,
) -> TargetEvidenceState:
    """Classify whether provider state is safe for an automatic mutation."""
    if delivery is None:
        return "not_applicable"
    if calendar_sync is None:
        return "missing"
    synced_at = calendar_sync.synced_at
    if (
        synced_at is None
        or synced_at > now
        or now - synced_at > TARGET_CALENDAR_MAX_AGE
        or not (
            calendar_sync.window_start
            <= current_date
            <= calendar_sync.window_end
        )
    ):
        return "stale"
    state, _, observation = classify_plan_delivery_snapshot(
        canonical=canonical,
        delivery=delivery,
        calendar_sync=calendar_sync,
        observations=observations,
    )
    if state == "matching":
        if (
            observation is None
            or observation.observed_at < synced_at
            or observation.observed_at > now
        ):
            return "stale"
        return "current"
    if state == "pending_observation":
        return "pending"
    return "conflict"


def _decision_for_current_state(
    db: Session,
    *,
    user_id: str,
    trigger: str,
    current_date: date,
    now: datetime,
    for_update: bool = False,
) -> tuple[PlanAdjustmentDecision, list[TrainingPlan]]:
    """Load current evidence and produce one pure policy decision."""
    config = load_config_from_db(user_id, db)
    (
        workouts,
        has_completed_activity,
        recovery,
        active_delivery,
        calendar_sync,
        target_workouts,
    ) = load_plan_adjustment_inputs(
        user_id,
        db,
        current_date=current_date,
        recovery_source=config.preferences.get("recovery"),
        target=config.plan_management.get("execution_target"),
        for_update=for_update,
    )
    snapshots = [plan_snapshot(workout) for workout in workouts]
    science = load_active_science(
        config.science,
        config.zone_labels,
        locale=config.language if config.language in {"en", "zh"} else None,
    )
    recovery_theory = science.get("recovery")
    recovery_params = recovery_theory.params if recovery_theory else {}
    recovery_analysis, _, _, _ = _compute_recovery_analysis(
        recovery,
        recovery_params=recovery_params,
        current_date=current_date,
    )
    training_signal: dict[str, Any] = {}
    if len(snapshots) == 1:
        snapshot = snapshots[0]
        training_signal = daily_training_signal(
            _recovery_for_guidance(recovery_analysis),
            None,
            str(snapshot.get("workout_type") or ""),
            planned_detail=snapshot,
            recovery_thresholds=recovery_params,
            hrv_only=True,
        )
    target_state: TargetEvidenceState = "not_applicable"
    if len(snapshots) == 1:
        target_state = _target_evidence_state(
            canonical=workouts[0],
            delivery=active_delivery,
            calendar_sync=calendar_sync,
            observations=target_workouts,
            current_date=current_date,
            now=now,
        )
    decision = evaluate_conservative_plan_adjustment(
        policy=config.plan_management["adjustment_policy"],
        management_mode=config.plan_management["mode"],
        workouts=snapshots,
        training_signal=training_signal,
        recovery_analysis=recovery_analysis,
        has_completed_activity=has_completed_activity,
        target_evidence_state=target_state,
    )
    decision["evidence"]["trigger"] = trigger
    return decision, workouts


def _apply_snapshot(plan: TrainingPlan, snapshot: Mapping[str, Any]) -> None:
    """Apply the bounded workout fields while preserving canonical ownership."""
    for field in _REST_MUTATION_FIELDS:
        setattr(plan, field, snapshot.get(field))
    plan.source = PRAXYS_PLAN_WRITE_SOURCE


def _restore_snapshot(plan: TrainingPlan, snapshot: Mapping[str, Any]) -> None:
    """Restore every mutable field recorded by the exact before-snapshot."""
    normalized = plan_snapshot(snapshot)
    for field in _REST_MUTATION_FIELDS:
        value = normalized.get(field)
        if field == "start_time" and isinstance(value, str):
            try:
                value = datetime.fromisoformat(
                    value.strip().replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise PlanAdjustmentConflictError(
                    "Adjustment start time is invalid"
                ) from exc
            if value.tzinfo is not None:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
        setattr(plan, field, value)
    plan.source = str(normalized["source"])
    plan.workout_origin = str(normalized["workout_origin"])


def _snapshots_match_exactly(left: Any, right: Any) -> bool:
    """Return whether all canonical snapshot fields match."""
    return plan_snapshot(left) == plan_snapshot(right)


def apply_conservative_plan_adjustment(
    db: Session,
    *,
    user_id: str,
    trigger: str,
    current_date: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate and atomically apply one opted-in automatic adjustment."""
    raw_timestamp = now or datetime.utcnow()
    timestamp = (
        raw_timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        if raw_timestamp.tzinfo is not None
        else raw_timestamp
    )
    config = load_config_from_db(user_id, db)
    if (
        config.plan_management["mode"] != "praxys"
        or config.plan_management["adjustment_policy"] != "auto_conservative"
    ):
        decision = evaluate_conservative_plan_adjustment(
            policy=config.plan_management["adjustment_policy"],
            management_mode=config.plan_management["mode"],
            workouts=[],
            training_signal={},
            recovery_analysis={},
            has_completed_activity=False,
            target_evidence_state="not_applicable",
        )
        db.rollback()
        return {"status": decision["status"], "decision": decision}
    as_of = current_date or athlete_local_date(config, timestamp)
    if as_of is None:
        decision = evaluate_conservative_plan_adjustment(
            policy=config.plan_management["adjustment_policy"],
            management_mode=config.plan_management["mode"],
            workouts=[],
            training_signal={},
            recovery_analysis={},
            has_completed_activity=False,
            target_evidence_state="not_applicable",
            local_date_trusted=False,
        )
        db.rollback()
        return {"status": decision["status"], "decision": decision}

    decision, _ = _decision_for_current_state(
        db,
        user_id=user_id,
        trigger=trigger,
        current_date=as_of,
        now=timestamp,
    )
    if decision["status"] != "adjust":
        db.rollback()
        return {"status": decision["status"], "decision": decision}

    db.rollback()
    lock_plan_writes(db, user_id)
    decision, locked_workouts = _decision_for_current_state(
        db,
        user_id=user_id,
        trigger=trigger,
        current_date=as_of,
        now=timestamp,
        for_update=True,
    )
    if decision["status"] != "adjust":
        db.rollback()
        return {"status": decision["status"], "decision": decision}

    idempotency_key = decision["idempotency_key"]
    assert idempotency_key is not None
    existing = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing_after = (
            existing.after_snapshot[0]
            if len(existing.after_snapshot or []) == 1
            else None
        )
        db.rollback()
        return {
            "status": "already_evaluated",
            "revision_id": existing.id,
            "snapshot": existing_after,
            "decision": decision,
        }

    plan = locked_workouts[0]
    current_snapshot = plan_snapshot(plan)
    after = decision["after"]
    assert after is not None
    config = load_config_from_db(user_id, db)
    _apply_snapshot(plan, after)
    db.flush()
    committed_after = plan_snapshot(plan)
    revision, created = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation=_AUTO_OPERATION,
        actor_type="system",
        actor_id="conservative-adjustment-v1",
        origin="api.plan_adjustments",
        before=[current_snapshot],
        after=[committed_after],
        details={
            "rule": {
                "id": decision["rule_id"],
                "version": decision["rule_version"],
                "classification": "product_estimate",
            },
            "reason_code": decision["reason_code"],
            "rationale": decision["rationale"],
            "evidence": decision["evidence"],
            "bounds": decision["bounds"],
            "citations": decision["citations"],
            "delivery": {
                "requested": bool(config.plan_management["delivery_enabled"]),
                "target": config.plan_management.get("execution_target"),
                "status": "pending",
            },
        },
        idempotency_key=idempotency_key,
    )
    if not created:
        db.rollback()
        return {
            "status": "already_evaluated",
            "revision_id": revision.id,
            "decision": decision,
        }
    bump_revisions(db, user_id, ["plans"])
    db.commit()
    return {
        "status": "adjusted",
        "revision_id": revision.id,
        "snapshot": committed_after,
        "decision": decision,
    }


def _delivery_payload(result: object) -> dict[str, Any]:
    """Return a JSON-safe delivery consequence payload."""
    if result is None:
        return {
            "status": "unavailable",
            "reason": "delivery_runner_returned_no_result",
        }
    payload = asdict(result)
    payload["items"] = [dict(item) for item in payload.get("items", ())]
    return payload


def _snapshot_workout_date(snapshot: Mapping[str, Any]) -> date | None:
    """Return the logical workout date recorded in a plan snapshot."""
    value = snapshot.get("date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _record_delivery_consequence(
    db: Session,
    *,
    user_id: str,
    adjustment_revision_id: str,
    operation: str,
    snapshot: Mapping[str, Any],
    delivery_result: object,
    delivery_payload: Mapping[str, Any] | None = None,
) -> None:
    """Append the actual delivery outcome without rewriting the mutation event."""
    payload = (
        dict(delivery_payload)
        if delivery_payload is not None
        else _delivery_payload(delivery_result)
    )
    _, created = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation=operation,
        actor_type="system",
        actor_id="managed-delivery",
        origin="api.plan_adjustments.delivery",
        before=[snapshot],
        after=[snapshot],
        details={
            "adjustment_revision_id": adjustment_revision_id,
            "delivery": payload,
        },
        idempotency_key=f"{operation}:{adjustment_revision_id}",
    )
    if created:
        bump_revisions(db, user_id, ["plans"])
    db.commit()


def _delivery_consequence(
    db: Session,
    *,
    user_id: str,
    adjustment_revision_id: str,
    operation: str,
) -> dict[str, Any] | None:
    """Return an already-recorded delivery consequence, if present."""
    revision = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key
            == f"{operation}:{adjustment_revision_id}",
        )
    ).scalar_one_or_none()
    if revision is None or not isinstance(revision.details, Mapping):
        return None
    delivery = revision.details.get("delivery")
    return dict(delivery) if isinstance(delivery, Mapping) else {}


def _plan_snapshot_is_current(
    db: Session,
    *,
    user_id: str,
    snapshot: Mapping[str, Any],
) -> bool:
    """Return whether an exact snapshot still represents active plan state."""
    canonical_id = str(snapshot.get("canonical_id") or "")
    if not canonical_id:
        return False
    current = db.execute(
        select(TrainingPlan).where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.canonical_id == canonical_id,
        )
    ).scalar_one_or_none()
    return current is not None and _snapshots_match_exactly(current, snapshot)


def _adjustment_snapshot_is_current(
    db: Session,
    *,
    user_id: str,
    revision_id: str,
    snapshot: Mapping[str, Any],
) -> bool:
    """Return whether a pending adjustment still represents active plan state."""
    undo = db.execute(
        select(PlanRevision.id).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key
            == f"auto-adjustment-undo:{revision_id}",
        )
    ).scalar_one_or_none()
    return undo is None and _plan_snapshot_is_current(
        db,
        user_id=user_id,
        snapshot=snapshot,
    )


def _pending_adjustment_deliveries(
    db: Session,
    *,
    user_id: str,
) -> list[tuple[PlanRevision, Mapping[str, Any]]]:
    """Return recent adjustment events missing a consequence event."""
    adjustments = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == _AUTO_OPERATION,
        )
        .order_by(PlanRevision.created_at.desc(), PlanRevision.id.desc())
        .limit(50)
    ).scalars().all()
    pending: list[tuple[PlanRevision, Mapping[str, Any]]] = []
    for revision in adjustments:
        if _delivery_consequence(
            db,
            user_id=user_id,
            adjustment_revision_id=revision.id,
            operation=_DELIVERY_OPERATION,
        ) is not None:
            continue
        if len(revision.after_snapshot or []) != 1:
            continue
        snapshot = revision.after_snapshot[0]
        if isinstance(snapshot, Mapping):
            pending.append((revision, snapshot))
    return pending


def run_plan_adjustment_for_user(
    user_id: str,
    *,
    trigger: str,
    current_date: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run one isolated post-sync or consent-time adjustment pass."""
    from api.plan_delivery.rolling import trigger_managed_plan_delivery
    from db.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        active_pending: list[tuple[PlanRevision, Mapping[str, Any]]] = []
        for pending_revision, pending_snapshot in (
            _pending_adjustment_deliveries(db, user_id=user_id)
        ):
            if _adjustment_snapshot_is_current(
                db,
                user_id=user_id,
                revision_id=pending_revision.id,
                snapshot=pending_snapshot,
            ):
                active_pending.append((pending_revision, pending_snapshot))
                continue
            try:
                _record_delivery_consequence(
                    db,
                    user_id=user_id,
                    adjustment_revision_id=pending_revision.id,
                    operation=_DELIVERY_OPERATION,
                    snapshot=pending_snapshot,
                    delivery_result=None,
                    delivery_payload={
                        "status": "skipped",
                        "reason": "adjustment_no_longer_current",
                    },
                )
            except Exception:
                db.rollback()
                logger.exception(
                    "Could not close stale plan adjustment delivery audit "
                    "user=%s revision=%s",
                    user_id,
                    pending_revision.id,
                )
        if active_pending:
            for pending_revision, pending_snapshot in active_pending:
                recovered_delivery = trigger_managed_plan_delivery(
                    user_id,
                    trigger="automatic_plan_adjustment_audit_recovery",
                    window_start=_snapshot_workout_date(pending_snapshot),
                )
                try:
                    _record_delivery_consequence(
                        db,
                        user_id=user_id,
                        adjustment_revision_id=pending_revision.id,
                        operation=_DELIVERY_OPERATION,
                        snapshot=pending_snapshot,
                        delivery_result=recovered_delivery,
                    )
                except Exception:
                    db.rollback()
                    logger.exception(
                        "Plan adjustment delivery audit remains pending "
                        "user=%s revision=%s",
                        user_id,
                        pending_revision.id,
                    )
        result = apply_conservative_plan_adjustment(
            db,
            user_id=user_id,
            trigger=trigger,
            current_date=current_date,
            now=now,
        )
        if result["status"] not in {"adjusted", "already_evaluated"}:
            return result
        revision_id = str(result["revision_id"])
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, Mapping):
            return result
        recorded_delivery = _delivery_consequence(
            db,
            user_id=user_id,
            adjustment_revision_id=revision_id,
            operation=_DELIVERY_OPERATION,
        )
        if recorded_delivery is not None:
            result["delivery"] = recorded_delivery
            return result
        if not _adjustment_snapshot_is_current(
            db,
            user_id=user_id,
            revision_id=revision_id,
            snapshot=snapshot,
        ):
            skipped = {
                "status": "skipped",
                "reason": "adjustment_no_longer_current",
            }
            try:
                _record_delivery_consequence(
                    db,
                    user_id=user_id,
                    adjustment_revision_id=revision_id,
                    operation=_DELIVERY_OPERATION,
                    snapshot=snapshot,
                    delivery_result=None,
                    delivery_payload=skipped,
                )
                result["delivery_audit_status"] = "recorded"
            except Exception:
                db.rollback()
                logger.exception(
                    "Plan adjustment skip audit remains pending "
                    "user=%s revision=%s",
                    user_id,
                    revision_id,
                )
                result["delivery_audit_status"] = "pending"
            result["delivery"] = skipped
            return result
        delivery = trigger_managed_plan_delivery(
            user_id,
            trigger="automatic_plan_adjustment",
            window_start=_snapshot_workout_date(snapshot),
        )
        payload = _delivery_payload(delivery)
        try:
            _record_delivery_consequence(
                db,
                user_id=user_id,
                adjustment_revision_id=revision_id,
                operation=_DELIVERY_OPERATION,
                snapshot=snapshot,
                delivery_result=delivery,
            )
            result["delivery_audit_status"] = "recorded"
        except Exception:
            db.rollback()
            logger.exception(
                "Plan adjustment delivery audit remains pending "
                "user=%s revision=%s",
                user_id,
                revision_id,
            )
            result["delivery_audit_status"] = "pending"
        result["delivery"] = payload
        return result
    finally:
        db.close()


def _public_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project an audit snapshot into the authenticated client contract."""
    source = snapshot or {}
    return {
        "canonical_id": source.get("canonical_id"),
        "date": source.get("date"),
        "workout_type": source.get("workout_type"),
        "planned_duration_min": source.get("planned_duration_min"),
        "planned_distance_km": source.get("planned_distance_km"),
        "target_power_min": source.get("target_power_min"),
        "target_power_max": source.get("target_power_max"),
        "workout_description": source.get("workout_description"),
    }


def list_plan_adjustments(
    db: Session,
    *,
    user_id: str,
    limit: int = 20,
    start: date | None = None,
    end: date | None = None,
    include_stryd_delivery: bool = True,
) -> dict[str, Any]:
    """Return durable automatic-change notices with current undoability."""
    bounded_limit = max(1, min(limit, 50))
    adjustments = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == _AUTO_OPERATION,
        )
        .order_by(PlanRevision.created_at.desc(), PlanRevision.id.desc())
        .limit(100)
    ).scalars().all()
    adjustment_ids = [revision.id for revision in adjustments]
    related_keys = [
        key
        for adjustment_id in adjustment_ids
        for key in (
            f"auto-adjustment-undo:{adjustment_id}",
            f"{_DELIVERY_OPERATION}:{adjustment_id}",
            f"{_UNDO_DELIVERY_OPERATION}:{adjustment_id}",
        )
    ]
    related = (
        db.execute(
            select(PlanRevision)
            .where(
                PlanRevision.user_id == user_id,
                PlanRevision.idempotency_key.in_(related_keys),
            )
            .order_by(
                PlanRevision.created_at.desc(),
                PlanRevision.id.desc(),
            )
        ).scalars().all()
        if related_keys
        else []
    )

    undos: dict[str, PlanRevision] = {}
    deliveries: dict[str, PlanRevision] = {}
    for revision in related:
        details = revision.details if isinstance(revision.details, Mapping) else {}
        adjustment_id = str(details.get("adjustment_revision_id") or "")
        if not adjustment_id:
            continue
        if revision.operation == _UNDO_OPERATION:
            undos.setdefault(adjustment_id, revision)
        else:
            deliveries.setdefault(adjustment_id, revision)

    canonical_ids = {
        str((revision.after_snapshot or [{}])[0].get("canonical_id") or "")
        for revision in adjustments
        if revision.after_snapshot
    }
    current_rows = (
        db.execute(
            select(TrainingPlan).where(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                TrainingPlan.canonical_id.in_(canonical_ids),
            )
        ).scalars().all()
        if canonical_ids
        else []
    )
    current_by_id = {row.canonical_id: row for row in current_rows}

    items: list[dict[str, Any]] = []
    for revision in adjustments:
        before = (
            revision.before_snapshot[0]
            if len(revision.before_snapshot or []) == 1
            else {}
        )
        after = (
            revision.after_snapshot[0]
            if len(revision.after_snapshot or []) == 1
            else {}
        )
        workout_date_raw = after.get("date") or before.get("date")
        try:
            workout_date = date.fromisoformat(str(workout_date_raw))
        except (TypeError, ValueError):
            workout_date = None
        if start is not None and (
            workout_date is None or workout_date < start
        ):
            continue
        if end is not None and (
            workout_date is None or workout_date > end
        ):
            continue

        undo_revision = undos.get(revision.id)
        canonical_id = str(after.get("canonical_id") or "")
        current = current_by_id.get(canonical_id)
        matches_after = (
            current is not None
            and _snapshots_match_exactly(current, after)
        )
        can_undo = undo_revision is None and matches_after
        status = (
            "undone"
            if undo_revision is not None
            else "active"
            if can_undo
            else "superseded"
        )
        details = revision.details if isinstance(revision.details, Mapping) else {}
        consequence = deliveries.get(revision.id)
        consequence_details = (
            consequence.details
            if consequence is not None
            and isinstance(consequence.details, Mapping)
            else {}
        )
        delivery = (
            consequence_details.get("delivery")
            or details.get("delivery")
            or {}
        )
        if not include_stryd_delivery:
            delivery = without_stryd_delivery_metadata(delivery)
        items.append({
            "id": revision.id,
            "created_at": utc_isoformat(revision.created_at),
            "status": status,
            "can_undo": can_undo,
            "workout_date": workout_date_raw,
            "before": _public_snapshot(before),
            "after": _public_snapshot(after),
            "rule": details.get("rule") or {},
            "reason_code": details.get("reason_code"),
            "rationale": details.get("rationale"),
            "evidence": details.get("evidence") or {},
            "bounds": details.get("bounds") or {},
            "citations": details.get("citations") or [],
            "delivery": delivery,
            "undo_revision_id": (
                undo_revision.id if undo_revision is not None else None
            ),
        })
        if len(items) >= bounded_limit:
            break
    return {"items": items}


def undo_plan_adjustment(
    db: Session,
    *,
    user_id: str,
    revision_id: str,
) -> dict[str, Any]:
    """Restore one supported revision if its after-snapshot is still current."""
    from api.plan_delivery.rolling import trigger_managed_plan_delivery

    db.rollback()
    lock_plan_writes(db, user_id)
    adjustment = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.id == revision_id,
            PlanRevision.user_id == user_id,
            PlanRevision.operation.in_(
                (_AUTO_OPERATION, _CONTEXT_PILOT_OPERATION)
            ),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if adjustment is None:
        db.rollback()
        raise PlanAdjustmentNotFoundError(revision_id)
    undo_key = f"auto-adjustment-undo:{revision_id}"
    existing_undo = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key == undo_key,
        )
    ).scalar_one_or_none()
    if existing_undo is not None:
        restored = (
            existing_undo.after_snapshot[0]
            if len(existing_undo.after_snapshot or []) == 1
            else None
        )
        db.rollback()
        result: dict[str, Any] = {
            "status": "already_undone",
            "adjustment_revision_id": revision_id,
            "revision_id": existing_undo.id,
        }
        recorded = _delivery_consequence(
            db,
            user_id=user_id,
            adjustment_revision_id=revision_id,
            operation=_UNDO_DELIVERY_OPERATION,
        )
        if recorded is not None:
            result["delivery"] = recorded
            result["delivery_audit_status"] = "recorded"
            return result
        if not isinstance(restored, Mapping):
            return result
        if _plan_snapshot_is_current(
            db,
            user_id=user_id,
            snapshot=restored,
        ):
            delivery = trigger_managed_plan_delivery(
                user_id,
                trigger="automatic_plan_adjustment_undo_retry",
                window_start=_snapshot_workout_date(restored),
            )
            payload = _delivery_payload(delivery)
        else:
            delivery = None
            payload = {
                "status": "skipped",
                "reason": "restored_workout_no_longer_current",
            }
        try:
            _record_delivery_consequence(
                db,
                user_id=user_id,
                adjustment_revision_id=revision_id,
                operation=_UNDO_DELIVERY_OPERATION,
                snapshot=restored,
                delivery_result=delivery,
                delivery_payload=payload,
            )
            result["delivery_audit_status"] = "recorded"
        except Exception:
            db.rollback()
            logger.exception(
                "Plan adjustment undo delivery audit remains pending "
                "user=%s revision=%s",
                user_id,
                revision_id,
            )
            result["delivery_audit_status"] = "pending"
        result["delivery"] = payload
        return result
    if (
        len(adjustment.before_snapshot or []) != 1
        or len(adjustment.after_snapshot or []) != 1
    ):
        db.rollback()
        raise PlanAdjustmentConflictError(
            "Adjustment does not contain one reversible workout"
        )
    before = adjustment.before_snapshot[0]
    after = adjustment.after_snapshot[0]
    canonical_id = str(after.get("canonical_id") or "")
    if (
        not canonical_id
        or canonical_id != str(before.get("canonical_id") or "")
    ):
        db.rollback()
        raise PlanAdjustmentConflictError(
            "Adjustment canonical identity is invalid"
        )
    current = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.canonical_id == canonical_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        current is None
        or not _snapshots_match_exactly(current, after)
    ):
        db.rollback()
        raise PlanAdjustmentConflictError(
            "Workout changed after the plan adjustment"
        )

    current_snapshot = plan_snapshot(current)
    _restore_snapshot(current, before)
    db.flush()
    restored_snapshot = plan_snapshot(current)
    if not _snapshots_match_exactly(restored_snapshot, before):
        db.rollback()
        raise PlanAdjustmentConflictError(
            "Workout could not be restored to the exact prior snapshot"
        )
    revision, _ = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation=_UNDO_OPERATION,
        actor_type="user",
        actor_id=user_id,
        origin="api.plan_adjustments.undo",
        before=[current_snapshot],
        after=[restored_snapshot],
        details={
            "adjustment_revision_id": revision_id,
            "rationale": (
                "Athlete reversed the accepted context-pilot proposal."
                if adjustment.operation == _CONTEXT_PILOT_OPERATION
                else "User restored the workout that preceded the automatic "
                "adjustment."
            ),
            "delivery": {
                "requested": True,
                "status": "pending",
            },
        },
        idempotency_key=undo_key,
    )
    bump_revisions(db, user_id, ["plans"])
    db.commit()

    delivery = trigger_managed_plan_delivery(
        user_id,
        trigger="automatic_plan_adjustment_undo",
        window_start=_snapshot_workout_date(restored_snapshot),
    )
    payload = _delivery_payload(delivery)
    audit_status = "recorded"
    try:
        _record_delivery_consequence(
            db,
            user_id=user_id,
            adjustment_revision_id=revision_id,
            operation=_UNDO_DELIVERY_OPERATION,
            snapshot=restored_snapshot,
            delivery_result=delivery,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Plan adjustment undo delivery audit remains pending "
            "user=%s revision=%s",
            user_id,
            revision_id,
        )
        audit_status = "pending"
    return {
        "status": "undone",
        "adjustment_revision_id": revision_id,
        "revision_id": revision.id,
        "delivery": payload,
        "delivery_audit_status": audit_status,
    }
