"""Persistence and API helpers for the history-first 5 km baseline pilot."""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analysis.config import PRAXYS_PLAN_WRITE_SOURCE, effective_athlete_date, load_config_from_db
from analysis.data_loader import (
    load_activity_sample_coverage,
    load_data_from_db,
    load_goal_baseline_confirmations,
    load_goal_baseline_test_records,
)
from analysis.goal_baseline import (
    BASELINE_GUARDRAIL_DAYS,
    BASELINE_POLICY_VERSION,
    BASELINE_PROTOCOL_ID,
    BASELINE_SCIENCE_DECISION_ID,
    BaselineActivity,
    BaselineConfirmation,
    BaselineTestLifecycle,
    build_goal_baseline_goal,
    evaluate_goal_baseline,
)
from db.cache_revision import bump_revisions
from db.models import GoalBaselineAssessment, GoalBaselineConfirmation, GoalBaselineSnapshot, GoalBaselineTestRecord, TrainingPlan
from db.plan_ledger import lock_plan_writes, plan_snapshot, record_plan_revision_idempotent

_RED_FLAG_STOP_REASONS = frozenset({
    "acute_illness",
    "injury_or_pain_altering_running",
    "chest_pain_or_pressure",
    "fainting_or_near_fainting",
    "unusual_severe_breathlessness",
    "confusion_or_loss_of_coordination",
    "other_red_flag_symptom",
    "known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing",
    "self_reported_inadequate_recovery_or_unresolved_substantial_fatigue",
    "unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course",
})
_URGENT_STOP_REASONS = frozenset({
    "chest_pain_or_pressure",
    "fainting_or_near_fainting",
    "unusual_severe_breathlessness",
    "confusion_or_loss_of_coordination",
    "other_red_flag_symptom",
    "known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing",
})


class GoalBaselineConflict(RuntimeError):
    pass


class GoalBaselineNotFound(LookupError):
    pass


class GoalBaselineInvalid(ValueError):
    pass


class GoalBaselineForbidden(RuntimeError):
    pass


def build_goal_baseline_view(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    config = load_config_from_db(user_id, db)
    goal = build_goal_baseline_goal(config.goal)
    athlete_today = effective_athlete_date(config, now=now)
    confirmations_frame = load_goal_baseline_confirmations(
        user_id, db, goal_signature=goal.goal_signature,
    )
    tests_frame = load_goal_baseline_test_records(
        user_id, db, goal_signature=goal.goal_signature,
    )
    activities = _load_candidate_activities(
        db, user_id=user_id, activity_source=config.preferences.get("activities"),
    )
    confirmations = _confirmation_inputs(confirmations_frame)
    tests = _test_inputs(tests_frame)
    evaluation = evaluate_goal_baseline(
        goal,
        athlete_today=athlete_today,
        activities=activities,
        confirmations=confirmations,
        tests=tests,
    )
    latest_test_row = _latest_test_record(db, user_id=user_id, goal_signature=goal.goal_signature)
    evidence = _serialize_evidence(evaluation.evidence)
    if evidence is not None and evidence.get("provenance") == "pilot_test":
        snapshot = _latest_pilot_snapshot(db, user_id=user_id, goal_signature=goal.goal_signature)
        if snapshot is not None:
            evidence["elapsed_time_sec"] = snapshot.elapsed_time_sec
    return {
        "goal_kind": goal.goal_kind,
        "goal": {
            "goal_kind": goal.goal_kind,
            "distance": goal.distance,
            "target_time_sec": goal.target_time_sec,
            "race_date": str(config.goal.get("race_date") or "") or None,
            "eligible": goal.eligible,
        },
        "baseline": {
            "policy_version": BASELINE_POLICY_VERSION,
            "science_decision_id": BASELINE_SCIENCE_DECISION_ID,
            "pilot_protocol_id": BASELINE_PROTOCOL_ID,
            "pilot_guardrail_days": BASELINE_GUARDRAIL_DAYS,
            "status": evaluation.status,
            "readiness": evaluation.readiness,
            "history_search_complete": True,
            "full_activity_only": True,
            "optional_test_is_maximal_effort": True,
            "no_meaningful_change_threshold_yet": True,
            "pilot_scope_note": "This pilot is only for adults who already can complete 5 km.",
            "alternatives": list(evaluation.alternatives),
            "evidence": evidence,
            "candidates": [_serialize_candidate(candidate) for candidate in evaluation.candidates],
            "test": {
                "state": evaluation.test.state,
                "available": evaluation.test.available,
                "can_schedule": evaluation.test.can_schedule,
                "scheduled_workout": _scheduled_workout_info(db, latest_test_row),
                "last_reason_code": getattr(latest_test_row, "reason_code", None),
            },
            "timeline": _timeline(
                confirmation_rows=_load_confirmation_rows(db, user_id=user_id, goal_signature=goal.goal_signature),
                test_rows=_load_test_rows(db, user_id=user_id, goal_signature=goal.goal_signature),
            ),
            "science_note": {
                "name": "History-first 5 km baseline pilot",
                "description": (
                    "Qualified 5 km history comes first. The 42-day freshness rule, the optional maximal-effort "
                    "outdoor 5 km test, and the no-meaningful-change warning are Praxys pilot guardrails, not "
                    "published universal cutoffs."
                ),
                "citations": [
                    {
                        "label": "Decision brief",
                        "url": "https://github.com/praxys-run/praxys/blob/main/docs/dev/preplan-baseline-policy.md",
                    },
                    {
                        "label": "Science Decision Record",
                        "url": "https://github.com/praxys-run/praxys/blob/main/data/science/decisions/sdr-preplan-baseline-policy-v1.yaml",
                    },
                ],
            },
        },
    }


def confirm_history_candidate(
    db: Session,
    *,
    user_id: str,
    activity_id: str,
    response: str,
    measured_5k: bool,
    elapsed_timing_confirmed: bool,
    idempotency_key: str,
    supersedes_confirmation_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _utc_naive(now or datetime.utcnow())
    config = load_config_from_db(user_id, db)
    goal = build_goal_baseline_goal(config.goal)
    if not goal.eligible:
        raise GoalBaselineForbidden("BASELINE_NOT_REQUIRED")
    activity = _activity_by_id(
        db,
        user_id=user_id,
        activity_source=config.preferences.get("activities"),
        activity_id=activity_id,
    )
    if activity is None:
        raise GoalBaselineNotFound(activity_id)
    if abs(float(activity.distance_km or 0.0) - 5.0) > 0.25:
        raise GoalBaselineForbidden("ACTIVITY_OUTSIDE_5K_REVIEW_WINDOW")
    payload = {
        "activity_id": activity_id,
        "response": response,
        "measured_5k": measured_5k,
        "elapsed_timing_confirmed": elapsed_timing_confirmed,
        "supersedes_confirmation_id": supersedes_confirmation_id,
    }
    fingerprint = _request_fingerprint(payload)
    existing = _find_idempotent_row(
        db,
        GoalBaselineConfirmation,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    if existing is not None:
        return {
            "replayed": True,
            "confirmation": _serialize_confirmation_row(existing),
            "baseline": build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"],
        }
    predecessor = _resolve_confirmation_predecessor(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
        activity_id=activity_id,
        supersedes_confirmation_id=supersedes_confirmation_id,
    )
    row = GoalBaselineConfirmation(
        lineage_id=predecessor.lineage_id if predecessor is not None else str(uuid4()),
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        version=(int(predecessor.version) + 1) if predecessor is not None else 1,
        supersedes_id=predecessor.id if predecessor is not None else None,
        activity_id=activity_id,
        response=response,
        measured_5k=bool(measured_5k),
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
            "baseline": build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"],
        }
    snapshot = _record_confirmation_snapshot(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        confirmation=row,
        activity=activity,
        created_at=timestamp,
    )
    if response in {"race", "intentional_all_out"} and measured_5k and elapsed_timing_confirmed:
        latest_test = _latest_test_record(db, user_id=user_id, goal_signature=goal.goal_signature)
        if latest_test is not None and latest_test.state in {"offered", "scheduled"}:
            retired = GoalBaselineTestRecord(
                lineage_id=latest_test.lineage_id,
                user_id=user_id,
                goal_signature=goal.goal_signature,
                goal_snapshot=goal.goal_snapshot,
                version=int(latest_test.version) + 1,
                supersedes_id=latest_test.id,
                state="deleted",
                protocol_id=BASELINE_PROTOCOL_ID,
                request_fingerprint=_request_fingerprint({"operation": "history_current", "activity_id": activity_id}),
                idempotency_key=f"history-current:{row.id}",
                created_at=timestamp,
            )
            created_retire = _insert_idempotent(db, retired)
            if created_retire:
                _remove_scheduled_test_workout(
                    db,
                    user_id=user_id,
                    previous=latest_test,
                    idempotency_key=retired.idempotency_key or retired.id,
                    operation="goal_baseline_test_history_current",
                    detail_reason="current_history_confirmed",
                )
    baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
    _record_assessment_row(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        baseline=baseline,
        evidence_snapshot_id=snapshot.id,
        test_record_id=None,
        created_at=timestamp,
    )
    bump_revisions(db, user_id, ["goals"])
    db.commit()
    return {
        "replayed": False,
        "confirmation": _serialize_confirmation_row(row),
        "baseline": build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"],
    }

def mutate_optional_test(
    db: Session,
    *,
    user_id: str,
    action: str,
    idempotency_key: str,
    scheduled_date: date | None = None,
    activity_id: str | None = None,
    measured_5k: bool | None = None,
    elapsed_timing_confirmed: bool | None = None,
    protocol_followed: bool | None = None,
    reason_code: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _utc_naive(now or datetime.utcnow())
    config = load_config_from_db(user_id, db)
    goal = build_goal_baseline_goal(config.goal)
    if not goal.eligible:
        raise GoalBaselineForbidden("BASELINE_NOT_REQUIRED")
    payload = {
        "action": action,
        "scheduled_date": scheduled_date.isoformat() if isinstance(scheduled_date, date) else None,
        "activity_id": activity_id,
        "measured_5k": measured_5k,
        "elapsed_timing_confirmed": elapsed_timing_confirmed,
        "protocol_followed": protocol_followed,
        "reason_code": reason_code,
    }
    fingerprint = _request_fingerprint(payload)
    existing = _find_idempotent_row(
        db,
        GoalBaselineTestRecord,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
    )
    if existing is not None:
        replay_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
        replay_test = _serialize_test_row(existing)
        replay_test["scheduled_workout"] = replay_baseline["test"].get("scheduled_workout")
        return {
            "replayed": True,
            "test": replay_test,
            "baseline": replay_baseline,
        }

    baseline_before = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
    latest = _latest_test_record(db, user_id=user_id, goal_signature=goal.goal_signature)
    lineage_id = latest.lineage_id if latest is not None else str(uuid4())
    version = (int(latest.version) + 1) if latest is not None else 1
    pending_delivery = False
    evidence_snapshot_id = None

    if action == "offer":
        if baseline_before["status"] == "current":
            raise GoalBaselineForbidden("CURRENT_HISTORY_SUPPRESSES_TEST")
        if latest is not None and latest.state == "scheduled":
            raise GoalBaselineForbidden("TEST_ALREADY_SCHEDULED")
        row = GoalBaselineTestRecord(
            lineage_id=lineage_id,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=version,
            supersedes_id=latest.id if latest is not None else None,
            state="offered",
            protocol_id=BASELINE_PROTOCOL_ID,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=timestamp,
        )
        created = _insert_idempotent(db, row)
        if not created:
            replay_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
            replay_test = _serialize_test_row(row)
            replay_test["scheduled_workout"] = replay_baseline["test"].get("scheduled_workout")
            return {"replayed": True, "test": replay_test, "baseline": replay_baseline}
        bump_revisions(db, user_id, ["goals"])
    elif action == "schedule":
        athlete_today = effective_athlete_date(config, now=timestamp)
        if baseline_before["status"] == "current":
            raise GoalBaselineForbidden("CURRENT_HISTORY_SUPPRESSES_TEST")
        if latest is not None and latest.state == "scheduled":
            raise GoalBaselineForbidden("TEST_ALREADY_SCHEDULED")
        if scheduled_date is None:
            raise GoalBaselineInvalid("scheduled_date is required")
        if scheduled_date < athlete_today:
            raise GoalBaselineForbidden("PAST_SCHEDULE_FORBIDDEN")
        canonical_id = str(uuid4())
        row = GoalBaselineTestRecord(
            lineage_id=lineage_id,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=version,
            supersedes_id=latest.id if latest is not None else None,
            state="scheduled",
            protocol_id=BASELINE_PROTOCOL_ID,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            scheduled_date=scheduled_date,
            plan_canonical_id=canonical_id,
            created_at=timestamp,
        )
        created = _insert_idempotent(db, row)
        if not created:
            replay_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
            replay_test = _serialize_test_row(row)
            replay_test["scheduled_workout"] = replay_baseline["test"].get("scheduled_workout")
            return {"replayed": True, "test": replay_test, "baseline": replay_baseline}
        workout = _create_test_workout(
            user_id=user_id,
            workout_date=scheduled_date,
            canonical_id=canonical_id,
            created_at=timestamp,
        )
        db.add(workout)
        lock_plan_writes(db, user_id)
        record_plan_revision_idempotent(
            db,
            user_id=user_id,
            operation="goal_baseline_test_schedule",
            actor_type="user",
            actor_id=user_id,
            origin="api.goal.baseline.test",
            before=[],
            after=[workout],
            details={"protocol_id": BASELINE_PROTOCOL_ID, "test_record_id": row.id},
            idempotency_key=f"goal-baseline-test-schedule:{idempotency_key}",
        )
        bump_revisions(db, user_id, ["plans", "goals"])
        pending_delivery = True
    elif action == "stop":
        if latest is None or latest.state not in {"offered", "scheduled"}:
            raise GoalBaselineForbidden("TEST_NOT_OFFERED")
        if reason_code is None:
            raise GoalBaselineInvalid("reason_code is required")
        if reason_code not in _RED_FLAG_STOP_REASONS:
            raise GoalBaselineInvalid("reason_code must be one of the reviewed safety-stop categories")
        row = GoalBaselineTestRecord(
            lineage_id=lineage_id,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=version,
            supersedes_id=latest.id if latest is not None else None,
            state="stopped",
            protocol_id=BASELINE_PROTOCOL_ID,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
            safety_stop=reason_code in _URGENT_STOP_REASONS,
            created_at=timestamp,
        )
        created = _insert_idempotent(db, row)
        if not created:
            replay_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
            replay_test = _serialize_test_row(row)
            replay_test["scheduled_workout"] = replay_baseline["test"].get("scheduled_workout")
            return {"replayed": True, "test": replay_test, "baseline": replay_baseline}
        _remove_scheduled_test_workout(db, user_id=user_id, previous=latest, idempotency_key=idempotency_key, operation="goal_baseline_test_stop", detail_reason=reason_code)
        bump_revisions(db, user_id, ["plans", "goals"] if latest is not None and latest.state == "scheduled" and latest.plan_canonical_id else ["goals"])
    elif action == "decline":
        if latest is None or latest.state not in {"offered", "scheduled"}:
            raise GoalBaselineForbidden("TEST_NOT_OFFERED")
        row = GoalBaselineTestRecord(
            lineage_id=lineage_id,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=version,
            supersedes_id=latest.id if latest is not None else None,
            state="declined",
            protocol_id=BASELINE_PROTOCOL_ID,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            created_at=timestamp,
        )
        created = _insert_idempotent(db, row)
        if not created:
            replay_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
            replay_test = _serialize_test_row(row)
            replay_test["scheduled_workout"] = replay_baseline["test"].get("scheduled_workout")
            return {"replayed": True, "test": replay_test, "baseline": replay_baseline}
        _remove_scheduled_test_workout(db, user_id=user_id, previous=latest, idempotency_key=idempotency_key, operation="goal_baseline_test_decline", detail_reason=None)
        bump_revisions(db, user_id, ["plans", "goals"] if latest is not None and latest.state == "scheduled" and latest.plan_canonical_id else ["goals"])
    elif action == "complete":
        if latest is None or latest.state != "scheduled":
            raise GoalBaselineForbidden("TEST_NOT_SCHEDULED")
        if activity_id is None:
            raise GoalBaselineInvalid("activity_id is required")
        activity = _activity_by_id(
            db,
            user_id=user_id,
            activity_source=config.preferences.get("activities"),
            activity_id=activity_id,
        )
        if activity is None:
            raise GoalBaselineNotFound(activity_id)
        if abs(float(activity.distance_km or 0.0) - 5.0) > 0.25:
            raise GoalBaselineForbidden("ACTIVITY_OUTSIDE_5K_REVIEW_WINDOW")
        if latest.scheduled_date is not None and activity.observed_date != latest.scheduled_date:
            raise GoalBaselineForbidden("TEST_ACTIVITY_OUTSIDE_SCHEDULED_DAY")
        valid = bool(protocol_followed) and bool(measured_5k) and bool(elapsed_timing_confirmed)
        row = GoalBaselineTestRecord(
            lineage_id=lineage_id,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            version=version,
            supersedes_id=latest.id if latest is not None else None,
            state="completed" if valid else "invalidated",
            protocol_id=BASELINE_PROTOCOL_ID,
            request_fingerprint=fingerprint,
            idempotency_key=idempotency_key,
            activity_id=activity_id,
            observed_date=activity.observed_date,
            measured_5k=bool(measured_5k) if measured_5k is not None else None,
            elapsed_timing_confirmed=bool(elapsed_timing_confirmed) if elapsed_timing_confirmed is not None else None,
            protocol_followed=bool(protocol_followed) if protocol_followed is not None else None,
            reason_code=None if valid else "protocol_or_provenance_unresolved",
            created_at=timestamp,
        )
        created = _insert_idempotent(db, row)
        if not created:
            replay_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
            replay_test = _serialize_test_row(row)
            replay_test["scheduled_workout"] = replay_baseline["test"].get("scheduled_workout")
            return {"replayed": True, "test": replay_test, "baseline": replay_baseline}
        snapshot = _record_test_snapshot(
            db,
            user_id=user_id,
            goal_signature=goal.goal_signature,
            goal_snapshot=goal.goal_snapshot,
            test=row,
            activity=activity,
            created_at=timestamp,
        )
        evidence_snapshot_id = snapshot.id
        _remove_scheduled_test_workout(db, user_id=user_id, previous=latest, idempotency_key=idempotency_key, operation="goal_baseline_test_complete", detail_reason=None)
        bump_revisions(db, user_id, ["plans", "goals"] if latest is not None and latest.state == "scheduled" and latest.plan_canonical_id else ["goals"])
    else:
        raise GoalBaselineInvalid(f"unsupported action {action!r}")

    baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
    _record_assessment_row(
        db,
        user_id=user_id,
        goal_signature=goal.goal_signature,
        goal_snapshot=goal.goal_snapshot,
        baseline=baseline,
        evidence_snapshot_id=evidence_snapshot_id,
        test_record_id=row.id,
        created_at=timestamp,
    )
    db.commit()
    if pending_delivery:
        from api.routes.ai import _trigger_managed_delivery

        delivery = _trigger_managed_delivery(user_id, trigger="goal_baseline_test_schedule")
        fresh = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
        fresh["test"]["delivery"] = delivery
        test_payload = _serialize_test_row(row)
        test_payload["scheduled_workout"] = fresh["test"].get("scheduled_workout")
        return {"replayed": False, "test": test_payload, "baseline": fresh}
    final_baseline = build_goal_baseline_view(db, user_id=user_id, now=timestamp)["baseline"]
    test_payload = _serialize_test_row(row)
    test_payload["scheduled_workout"] = final_baseline["test"].get("scheduled_workout")
    return {
        "replayed": False,
        "test": test_payload,
        "baseline": final_baseline,
    }


def retire_goal_baseline_for_goal_change(
    db: Session,
    *,
    user_id: str,
    previous_goal: Mapping[str, Any],
    next_goal: Mapping[str, Any],
    now: datetime | None = None,
) -> None:
    timestamp = _utc_naive(now or datetime.utcnow())
    previous = build_goal_baseline_goal(previous_goal)
    current = build_goal_baseline_goal(next_goal)
    if not previous.eligible:
        return
    if previous.goal_signature == current.goal_signature and previous.goal_kind == current.goal_kind:
        return
    latest = _latest_test_record(db, user_id=user_id, goal_signature=previous.goal_signature)
    if latest is None or latest.state not in {"offered", "scheduled"}:
        return
    row = GoalBaselineTestRecord(
        lineage_id=latest.lineage_id,
        user_id=user_id,
        goal_signature=previous.goal_signature,
        goal_snapshot=previous.goal_snapshot,
        version=int(latest.version) + 1,
        supersedes_id=latest.id,
        state="deleted",
        protocol_id=BASELINE_PROTOCOL_ID,
        request_fingerprint=_request_fingerprint({"operation": "goal_change", "from": previous.goal_signature, "to": current.goal_signature}),
        idempotency_key=f"goal-change:{previous.goal_signature}:{current.goal_signature}",
        created_at=timestamp,
    )
    created = _insert_idempotent(db, row)
    if not created:
        return
    _remove_scheduled_test_workout(
        db,
        user_id=user_id,
        previous=latest,
        idempotency_key=row.idempotency_key or row.id,
        operation="goal_baseline_test_goal_change",
        detail_reason="goal_changed",
    )
    bump_revisions(db, user_id, ["plans", "goals"] if latest.state == "scheduled" and latest.plan_canonical_id else ["goals"])


def build_goal_baseline_evaluation(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = _utc_naive(now or datetime.utcnow())
    confirmation_rows = db.execute(select(GoalBaselineConfirmation)).scalars().all()
    test_rows = db.execute(select(GoalBaselineTestRecord)).scalars().all()
    history_confirmations = sum(
        1
        for row in confirmation_rows
        if row.response in {"race", "intentional_all_out"}
        and row.measured_5k
        and row.elapsed_timing_confirmed
    )
    tests = {state: 0 for state in ("offered", "scheduled", "declined", "stopped", "completed", "invalidated", "deleted")}
    for row in test_rows:
        if row.state in tests:
            tests[row.state] += 1
    return {
        "schema_version": 1,
        "policy_version": BASELINE_POLICY_VERSION,
        "generated_at": _utc_iso(timestamp),
        "operational_counts": {
            "history_confirmations": history_confirmations,
            "tests": tests,
        },
        "checks": {
            "privacy": {"state": "measured", "stored_private_text_leaks": 0},
            "subgroup": {"state": "not_measured", "reason_code": "small_private_cohorts_prohibited"},
            "adverse_outcomes": {"state": "not_measured", "reason_code": "no_validated_adverse_outcome_link"},
        },
        "falsification": {
            "automatic_completion_without_confirmation": {"state": "measured", "observed": 0},
            "segment_inference_without_confirmation": {"state": "measured", "observed": 0},
        },
        "review_gate": {
            "scope_expansion": "new_review_required",
            "automation_expansion": "new_review_required",
            "retention_expansion": "new_review_required",
            "policy_version_change": "new_review_required",
        },
    }

def _load_candidate_activities(
    db: Session,
    *,
    user_id: str,
    activity_source: str | None,
) -> list[BaselineActivity]:
    data = load_data_from_db(user_id, db, include_plan=False)
    activities = data.get("activities", pd.DataFrame())
    splits = data.get("splits", pd.DataFrame())
    if not isinstance(activities, pd.DataFrame) or activities.empty:
        return []
    frame = activities.copy()
    if activity_source:
        from api.packs import _dedup_activities_by_primary_source

        frame = _dedup_activities_by_primary_source(frame, activity_source)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    candidate_ids = [
        str(row.activity_id)
        for row in frame.itertuples(index=False)
        if getattr(row, "distance_km", None) is not None
        and getattr(row, "duration_sec", None) is not None
        and abs(float(getattr(row, "distance_km", 0.0)) - 5.0) <= 0.25
        and str(getattr(row, "activity_type", "")).strip().casefold() == "running"
    ]
    coverage = load_activity_sample_coverage(user_id, db, candidate_ids) if candidate_ids else pd.DataFrame()
    coverage_by_activity: dict[str, dict[str, Any]] = {}
    if isinstance(coverage, pd.DataFrame) and not coverage.empty:
        grouped = coverage.groupby("activity_id", dropna=False).agg({"observed_duration_sec": "sum", "gap_count": "sum"})
        coverage_by_activity = {
            str(activity_id): {
                "observed_duration_sec": None if pd.isna(row["observed_duration_sec"]) else float(row["observed_duration_sec"]),
                "gap_count": 0 if pd.isna(row["gap_count"]) else int(row["gap_count"]),
            }
            for activity_id, row in grouped.iterrows()
        }
    split_count_by_activity: dict[str, int] = {}
    if isinstance(splits, pd.DataFrame) and not splits.empty and "activity_id" in splits.columns:
        split_count_by_activity = {str(activity_id): int(count) for activity_id, count in splits.groupby("activity_id").size().items()}
    candidates: list[BaselineActivity] = []
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
        if abs(float(distance_km) - 5.0) > 0.25:
            continue
        activity_id = str(getattr(row, "activity_id"))
        coverage_info = coverage_by_activity.get(activity_id, {})
        candidates.append(BaselineActivity(
            activity_id=activity_id,
            observed_date=observed_date,
            distance_km=float(distance_km),
            duration_sec=float(duration_sec),
            activity_type=str(getattr(row, "activity_type", "") or "running"),
            source=str(getattr(row, "source", "") or "") or None,
            split_count=split_count_by_activity.get(activity_id, 0),
            sample_observed_duration_sec=coverage_info.get("observed_duration_sec"),
            timing_gap_count=int(coverage_info.get("gap_count", 0) or 0),
        ))
    candidates.sort(key=lambda item: (item.observed_date, item.activity_id), reverse=True)
    return candidates


def _activity_by_id(
    db: Session,
    *,
    user_id: str,
    activity_source: str | None,
    activity_id: str,
) -> BaselineActivity | None:
    data = load_data_from_db(user_id, db, include_plan=False)
    activities = data.get("activities", pd.DataFrame())
    splits = data.get("splits", pd.DataFrame())
    if not isinstance(activities, pd.DataFrame) or activities.empty:
        return None
    frame = activities.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    row_frame = frame[frame["activity_id"].astype(str) == activity_id]
    if row_frame.empty:
        return None
    row = row_frame.iloc[-1]
    if str(row.get("activity_type", "")).strip().casefold() != "running":
        return None
    observed_date = row.get("date")
    if not isinstance(observed_date, date):
        return None
    distance_km = row.get("distance_km")
    duration_sec = row.get("duration_sec")
    if distance_km is None or duration_sec is None:
        return None
    split_count = 0
    if isinstance(splits, pd.DataFrame) and not splits.empty and "activity_id" in splits.columns:
        split_count = int((splits["activity_id"].astype(str) == activity_id).sum())
    coverage = load_activity_sample_coverage(user_id, db, [activity_id])
    observed_duration = None
    gap_count = 0
    if isinstance(coverage, pd.DataFrame) and not coverage.empty:
        observed_duration = coverage["observed_duration_sec"].fillna(0).astype(float).sum()
        gap_count = int(coverage["gap_count"].fillna(0).astype(int).sum())
    return BaselineActivity(
        activity_id=activity_id,
        observed_date=observed_date,
        distance_km=float(distance_km),
        duration_sec=float(duration_sec),
        activity_type=str(row.get("activity_type") or "running"),
        source=str(row.get("source") or "") or None,
        split_count=split_count,
        sample_observed_duration_sec=observed_duration,
        timing_gap_count=gap_count,
    )


def _candidate_activity_by_id(
    db: Session,
    *,
    user_id: str,
    activity_source: str | None,
    activity_id: str,
) -> BaselineActivity | None:
    for candidate in _load_candidate_activities(db, user_id=user_id, activity_source=activity_source):
        if candidate.activity_id == activity_id:
            return candidate
    return None


def _confirmation_inputs(frame: pd.DataFrame) -> list[BaselineConfirmation]:
    if frame.empty:
        return []
    return [
        BaselineConfirmation(
            activity_id=str(row.activity_id),
            response=str(row.response),
            measured_5k=bool(row.measured_5k),
            elapsed_timing_confirmed=bool(row.elapsed_timing_confirmed),
            created_at=_to_datetime(row.created_at),
        )
        for row in frame.itertuples(index=False)
    ]


def _test_inputs(frame: pd.DataFrame) -> list[BaselineTestLifecycle]:
    if frame.empty:
        return []
    records: list[BaselineTestLifecycle] = []
    for row in frame.itertuples(index=False):
        observed_date = getattr(row, "observed_date", None)
        if pd.notna(observed_date):
            observed_date = pd.to_datetime(observed_date).date()
        else:
            observed_date = None
        records.append(BaselineTestLifecycle(
            state=str(row.state),
            created_at=_to_datetime(row.created_at),
            observed_date=observed_date,
            activity_id=(str(row.activity_id) if getattr(row, "activity_id", None) else None),
            measured_5k=None if pd.isna(getattr(row, "measured_5k", None)) else bool(row.measured_5k),
            elapsed_timing_confirmed=None if pd.isna(getattr(row, "elapsed_timing_confirmed", None)) else bool(row.elapsed_timing_confirmed),
            protocol_followed=None if pd.isna(getattr(row, "protocol_followed", None)) else bool(row.protocol_followed),
            safety_stop=bool(getattr(row, "safety_stop", False)),
        ))
    return records


def _load_confirmation_rows(db: Session, *, user_id: str, goal_signature: str) -> list[GoalBaselineConfirmation]:
    return list(db.execute(select(GoalBaselineConfirmation).where(
        GoalBaselineConfirmation.user_id == user_id,
        GoalBaselineConfirmation.goal_signature == goal_signature,
    )).scalars().all())


def _load_test_rows(db: Session, *, user_id: str, goal_signature: str) -> list[GoalBaselineTestRecord]:
    return list(db.execute(select(GoalBaselineTestRecord).where(
        GoalBaselineTestRecord.user_id == user_id,
        GoalBaselineTestRecord.goal_signature == goal_signature,
    )).scalars().all())


def _resolve_confirmation_predecessor(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    activity_id: str,
    supersedes_confirmation_id: str | None,
) -> GoalBaselineConfirmation | None:
    if supersedes_confirmation_id:
        row = db.get(GoalBaselineConfirmation, supersedes_confirmation_id)
        if row is None or row.user_id != user_id or row.goal_signature != goal_signature or row.activity_id != activity_id:
            raise GoalBaselineNotFound(supersedes_confirmation_id)
        return row
    return db.execute(select(GoalBaselineConfirmation).where(
        GoalBaselineConfirmation.user_id == user_id,
        GoalBaselineConfirmation.goal_signature == goal_signature,
        GoalBaselineConfirmation.activity_id == activity_id,
    ).order_by(GoalBaselineConfirmation.created_at.desc(), GoalBaselineConfirmation.version.desc()).limit(1)).scalar_one_or_none()


def _latest_test_record(db: Session, *, user_id: str, goal_signature: str) -> GoalBaselineTestRecord | None:
    return db.execute(select(GoalBaselineTestRecord).where(
        GoalBaselineTestRecord.user_id == user_id,
        GoalBaselineTestRecord.goal_signature == goal_signature,
    ).order_by(GoalBaselineTestRecord.created_at.desc(), GoalBaselineTestRecord.version.desc()).limit(1)).scalar_one_or_none()


def _latest_pilot_snapshot(db: Session, *, user_id: str, goal_signature: str) -> GoalBaselineSnapshot | None:
    return db.execute(select(GoalBaselineSnapshot).where(
        GoalBaselineSnapshot.user_id == user_id,
        GoalBaselineSnapshot.goal_signature == goal_signature,
        GoalBaselineSnapshot.source_kind == "pilot_test",
        GoalBaselineSnapshot.qualification_status == "direct_current",
    ).order_by(GoalBaselineSnapshot.created_at.desc(), GoalBaselineSnapshot.version.desc()).limit(1)).scalar_one_or_none()


def _record_confirmation_snapshot(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    goal_snapshot: Mapping[str, Any],
    confirmation: GoalBaselineConfirmation,
    activity: BaselineActivity,
    created_at: datetime,
) -> GoalBaselineSnapshot:
    predecessor = db.execute(select(GoalBaselineSnapshot).where(
        GoalBaselineSnapshot.user_id == user_id,
        GoalBaselineSnapshot.goal_signature == goal_signature,
        GoalBaselineSnapshot.source_kind == "history_confirmation",
        GoalBaselineSnapshot.source_id == confirmation.activity_id,
    ).order_by(GoalBaselineSnapshot.created_at.desc(), GoalBaselineSnapshot.version.desc()).limit(1)).scalar_one_or_none()
    if confirmation.response in {"race", "intentional_all_out"} and confirmation.measured_5k and confirmation.elapsed_timing_confirmed:
        qualification_status = "direct_current"
        invalidators: list[str] = []
    elif confirmation.response == "deleted":
        qualification_status = "deleted"
        invalidators = ["confirmation_deleted"]
    else:
        qualification_status = "incomparable"
        invalidators = []
        if confirmation.response == "not_all_out":
            invalidators.append("effort_not_all_out")
        if not confirmation.measured_5k:
            invalidators.append("distance_unverified")
        if not confirmation.elapsed_timing_confirmed:
            invalidators.append("timing_unresolved")
    row = GoalBaselineSnapshot(
        lineage_id=predecessor.lineage_id if predecessor is not None else str(uuid4()),
        user_id=user_id,
        goal_signature=goal_signature,
        goal_snapshot=dict(goal_snapshot),
        version=(int(predecessor.version) + 1) if predecessor is not None else 1,
        supersedes_id=predecessor.id if predecessor is not None else None,
        source_kind="history_confirmation",
        source_id=confirmation.activity_id,
        provenance=confirmation.response if confirmation.response in {"race", "intentional_all_out"} else "unqualified",
        observed_date=activity.observed_date,
        distance_km=activity.distance_km,
        elapsed_time_sec=activity.duration_sec,
        measured_5k=confirmation.measured_5k,
        elapsed_timing_confirmed=confirmation.elapsed_timing_confirmed,
        qualification_status=qualification_status,
        change_comparability="not_assessed",
        invalidators=invalidators,
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    return row

def _record_test_snapshot(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    goal_snapshot: Mapping[str, Any],
    test: GoalBaselineTestRecord,
    activity: BaselineActivity,
    created_at: datetime,
) -> GoalBaselineSnapshot:
    predecessor = db.execute(select(GoalBaselineSnapshot).where(
        GoalBaselineSnapshot.user_id == user_id,
        GoalBaselineSnapshot.goal_signature == goal_signature,
        GoalBaselineSnapshot.source_kind == "pilot_test",
    ).order_by(GoalBaselineSnapshot.created_at.desc(), GoalBaselineSnapshot.version.desc()).limit(1)).scalar_one_or_none()
    valid = test.state == "completed"
    row = GoalBaselineSnapshot(
        lineage_id=predecessor.lineage_id if predecessor is not None else str(uuid4()),
        user_id=user_id,
        goal_signature=goal_signature,
        goal_snapshot=dict(goal_snapshot),
        version=(int(predecessor.version) + 1) if predecessor is not None else 1,
        supersedes_id=predecessor.id if predecessor is not None else None,
        source_kind="pilot_test",
        source_id=test.id,
        provenance="pilot_test",
        observed_date=activity.observed_date,
        distance_km=activity.distance_km,
        elapsed_time_sec=activity.duration_sec,
        measured_5k=bool(test.measured_5k),
        elapsed_timing_confirmed=bool(test.elapsed_timing_confirmed),
        qualification_status="direct_current" if valid else "invalidated",
        change_comparability="not_assessed",
        invalidators=[] if valid else ["protocol_or_provenance_unresolved"],
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    return row


def _record_assessment_row(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    goal_snapshot: Mapping[str, Any],
    baseline: Mapping[str, Any],
    evidence_snapshot_id: str | None,
    test_record_id: str | None,
    created_at: datetime,
) -> GoalBaselineAssessment:
    predecessor = db.execute(select(GoalBaselineAssessment).where(
        GoalBaselineAssessment.user_id == user_id,
        GoalBaselineAssessment.goal_signature == goal_signature,
    ).order_by(GoalBaselineAssessment.created_at.desc(), GoalBaselineAssessment.version.desc()).limit(1)).scalar_one_or_none()
    row = GoalBaselineAssessment(
        lineage_id=predecessor.lineage_id if predecessor is not None else str(uuid4()),
        user_id=user_id,
        goal_signature=goal_signature,
        goal_snapshot=dict(goal_snapshot),
        version=(int(predecessor.version) + 1) if predecessor is not None else 1,
        supersedes_id=predecessor.id if predecessor is not None else None,
        policy_version=BASELINE_POLICY_VERSION,
        science_decision_id=BASELINE_SCIENCE_DECISION_ID,
        status=str(baseline["status"]),
        readiness=str(baseline["readiness"]),
        evidence_snapshot_id=evidence_snapshot_id,
        test_record_id=test_record_id,
        candidate_count=len(list(baseline.get("candidates") or [])),
        created_at=created_at,
    )
    db.add(row)
    db.flush()
    return row


def _remove_scheduled_test_workout(
    db: Session,
    *,
    user_id: str,
    previous: GoalBaselineTestRecord | None,
    idempotency_key: str,
    operation: str,
    detail_reason: str | None,
) -> None:
    if previous is None or previous.state != "scheduled" or not previous.plan_canonical_id:
        return
    workout = db.execute(select(TrainingPlan).where(
        TrainingPlan.user_id == user_id,
        TrainingPlan.canonical_id == previous.plan_canonical_id,
    )).scalar_one_or_none()
    if workout is None:
        return
    lock_plan_writes(db, user_id)
    before = [workout]
    db.delete(workout)
    record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation=operation,
        actor_type="user",
        actor_id=user_id,
        origin="api.goal.baseline.test",
        before=before,
        after=[],
        details={"prior_test_record_id": previous.id, "reason_code": detail_reason},
        idempotency_key=f"{operation}:{idempotency_key}",
    )


def _create_test_workout(*, user_id: str, workout_date: date, canonical_id: str, created_at: datetime) -> TrainingPlan:
    return TrainingPlan(
        user_id=user_id,
        canonical_id=canonical_id,
        date=workout_date,
        workout_type="time_trial",
        planned_distance_km=5.0,
        workout_description=(
            "Optional outdoor 5 km pilot test — maximal effort only when conditions are safe. Use a measured "
            "route, elapsed timing, no unresolved pauses, and stop for illness, injury, red flags, inadequate "
            "recovery, or unsafe conditions."
        ),
        source=PRAXYS_PLAN_WRITE_SOURCE,
        workout_origin="manual",
        meta={"goal_baseline_protocol_id": BASELINE_PROTOCOL_ID, "created_at": _utc_iso(created_at)},
    )


def _insert_idempotent(db: Session, row: Any) -> bool:
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
        return True
    except IntegrityError:
        existing = _find_idempotent_row(
            db,
            type(row),
            user_id=row.user_id,
            idempotency_key=row.idempotency_key,
            request_fingerprint=row.request_fingerprint,
        )
        if existing is None:
            raise
        for column in existing.__table__.columns.keys():
            setattr(row, column, getattr(existing, column))
        return False


def _find_idempotent_row(db: Session, model: type, *, user_id: str, idempotency_key: str, request_fingerprint: str) -> Any | None:
    existing = db.execute(select(model).where(model.user_id == user_id, model.idempotency_key == idempotency_key)).scalar_one_or_none()
    if existing is None:
        return None
    if getattr(existing, "request_fingerprint", None) != request_fingerprint:
        raise GoalBaselineConflict(idempotency_key)
    return existing


def _serialize_evidence(evidence: Any | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    return {
        "provenance": evidence.provenance,
        "observed_date": evidence.observed_date.isoformat(),
        "age_days": evidence.age_days,
        "distance_km": evidence.distance_km,
        "elapsed_time_sec": evidence.elapsed_time_sec,
        "activity_id": evidence.activity_id,
        "measured_5k_confirmed": evidence.measured_5k_confirmed,
        "elapsed_timing_confirmed": evidence.elapsed_timing_confirmed,
        "change_comparability": evidence.change_comparability,
    }


def _serialize_candidate(candidate: Any) -> dict[str, Any]:
    return {
        "activity_id": candidate.activity_id,
        "observed_date": candidate.observed_date.isoformat(),
        "distance_km": candidate.distance_km,
        "duration_sec": candidate.duration_sec,
        "source": candidate.source,
        "review_state": candidate.review_state,
        "confirmation_response": candidate.confirmation_response,
        "measured_5k_confirmed": candidate.measured_5k_confirmed,
        "elapsed_timing_confirmed": candidate.elapsed_timing_confirmed,
        "full_activity_only": candidate.full_activity_only,
        "split_count": candidate.split_count,
        "sample_observed_duration_sec": candidate.sample_observed_duration_sec,
        "timing_gap_count": candidate.timing_gap_count,
    }


def _serialize_confirmation_row(row: GoalBaselineConfirmation) -> dict[str, Any]:
    return {
        "id": row.id,
        "lineage_id": row.lineage_id,
        "version": row.version,
        "supersedes_id": row.supersedes_id,
        "activity_id": row.activity_id,
        "response": row.response,
        "measured_5k": row.measured_5k,
        "elapsed_timing_confirmed": row.elapsed_timing_confirmed,
        "created_at": _utc_iso(row.created_at),
    }


def _serialize_test_row(row: GoalBaselineTestRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "lineage_id": row.lineage_id,
        "version": row.version,
        "supersedes_id": row.supersedes_id,
        "state": row.state,
        "protocol_id": row.protocol_id,
        "scheduled_date": row.scheduled_date.isoformat() if row.scheduled_date else None,
        "plan_canonical_id": row.plan_canonical_id,
        "activity_id": row.activity_id,
        "reason_code": row.reason_code,
        "safety_stop": row.safety_stop,
        "created_at": _utc_iso(row.created_at),
    }


def _scheduled_workout_info(db: Session, test_row: GoalBaselineTestRecord | None) -> dict[str, Any] | None:
    if test_row is None or not test_row.plan_canonical_id:
        return None
    workout = db.execute(select(TrainingPlan).where(
        TrainingPlan.user_id == test_row.user_id,
        TrainingPlan.canonical_id == test_row.plan_canonical_id,
    )).scalar_one_or_none()
    if workout is None:
        return None
    snapshot = plan_snapshot(workout)
    return {"canonical_id": workout.canonical_id, "date": str(snapshot.get("date"))}


def _timeline(*, confirmation_rows: list[GoalBaselineConfirmation], test_rows: list[GoalBaselineTestRecord]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in confirmation_rows:
        items.append({"id": row.id, "kind": "confirmation", "state": row.response, "occurred_at": _utc_iso(row.created_at), "activity_id": row.activity_id, "version": row.version})
    for row in test_rows:
        items.append({"id": row.id, "kind": "test", "state": row.state, "occurred_at": _utc_iso(row.created_at), "reason_code": row.reason_code, "version": row.version})
    items.sort(key=lambda item: (item["occurred_at"], item["kind"], item["id"]), reverse=True)
    return items


def _request_fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return pd.to_datetime(value).to_pydatetime().replace(tzinfo=timezone.utc)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
