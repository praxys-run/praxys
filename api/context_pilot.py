"""Suggestion-only personal-context pilot and aggregate evaluation.

The pilot is deliberately fixed to missed/modified-workout explanations and
temporary availability constraints. It can create one reviewable duration
proposal, but only an authenticated athlete response may commit that proposal
through the canonical plan revision lane.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from time import monotonic, sleep
from typing import Any, Literal, Mapping, Sequence

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from analysis.config import (
    PRAXYS_PLAN_SOURCES,
    effective_athlete_date,
    load_config_from_db,
)
from api.personal_context import (
    PersonalContextAccessError,
    PersonalContextConflict,
    PersonalContextDeletionError,
    PersonalContextUnavailable,
    PersonalContextValidationError,
)
from api.personal_context_processing import (
    ContextDecision,
    ContextProjection,
    ProjectedContextItem,
    process_personal_context,
    project_personal_context,
)
from api.plan_adjustments import _restore_snapshot, _snapshots_match_exactly
from api.routes.ai import _trigger_managed_delivery
from api.views import utc_isoformat
from db.cache_revision import bump_revisions
from db.models import (
    PersonalContextConsentReceipt,
    PersonalContextItem,
    PlanRevision,
    TrainingPlan,
)
from db.plan_ledger import (
    lock_plan_writes,
    plan_snapshot,
    record_plan_revision_idempotent,
)

PILOT_POLICY_VERSION = "suggestion-context-pilot-v1"
PILOT_SCHEMA_VERSION = 1
PILOT_ALLOWED_PURPOSES = frozenset({
    "execution_interpretation",
    "plan_adjustment",
})
PILOT_ALLOWED_KINDS = frozenset({
    "execution_explanation",
    "temporary_constraint",
})
PILOT_OUTCOMES = frozenset({
    "clarification",
    "no_change",
    "insufficient_evidence",
    "safety",
    "suggestion",
})

PilotSource = Literal["synthetic", "opt_in"]
PilotResponse = Literal["accept", "reject", "defer"]

_RUN_OPERATIONS = frozenset({
    "context_pilot_decision",
    "context_pilot_failure",
    "context_pilot_proposal",
})
_RUN_RESERVATION_OPERATION = "context_pilot_reservation"
_RUN_RESERVATION_WAIT_SECONDS = 35.0
_RESPONSE_OPERATIONS = {
    "accept": "context_pilot_accept",
    "reject": "context_pilot_reject",
    "defer": "context_pilot_defer",
}
_ACCEPTANCE_DELIVERY_OPERATION = "context_pilot_accept_delivery"
_REVERSAL_OPERATION = "auto_adjustment_undo"
_PRIVATE_PROCESSING_EXCEPTIONS = (
    PersonalContextAccessError,
    PersonalContextConflict,
    PersonalContextDeletionError,
    PersonalContextUnavailable,
    PersonalContextValidationError,
)
_FORBIDDEN_STORED_KEYS = frozenset({
    "category",
    "context_values",
    "free_text",
    "model_output",
    "narrative",
    "prompt",
    "private_context_rationale",
})

_SYNTHETIC_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "ambiguity-clarification",
        "title_code": "multiple_workouts_need_selection",
        "expected_outcome": "clarification",
        "reason_code": "multiple_eligible_workouts",
        "question_code": "which_workout_to_adjust",
    },
    {
        "id": "missed-no-change",
        "title_code": "missed_workout_no_catch_up",
        "expected_outcome": "no_change",
        "reason_code": "missed_session_catch_up_disabled",
    },
    {
        "id": "missing-evidence",
        "title_code": "availability_without_bounded_window",
        "expected_outcome": "insufficient_evidence",
        "reason_code": "availability_window_missing",
    },
    {
        "id": "safety-boundary",
        "title_code": "athlete_reported_safety_boundary",
        "expected_outcome": "safety",
        "reason_code": "athlete_reported_safety_boundary",
    },
    {
        "id": "availability-suggestion",
        "title_code": "bounded_duration_suggestion",
        "expected_outcome": "suggestion",
        "reason_code": "availability_duration_conflict",
        "action": {
            "type": "shorten_workout_duration",
            "canonical_id": "synthetic-workout",
            "planned_duration_min": 30,
        },
    },
)


class ContextPilotError(RuntimeError):
    """Base error for a bounded pilot command."""


class ContextPilotValidationError(ContextPilotError, ValueError):
    """The pilot command falls outside the reviewed contract."""


class ContextPilotNotFound(ContextPilotError, LookupError):
    """The owner-scoped pilot proposal does not exist."""


class ContextPilotConflict(ContextPilotError):
    """The proposal is no longer pending against its exact base state."""


def list_context_pilot_scenarios() -> list[dict[str, Any]]:
    """Return the fixed synthetic pilot catalog without private inputs."""
    return [
        {
            "id": str(scenario["id"]),
            "title_code": str(scenario["title_code"]),
            "expected_outcome": str(scenario["expected_outcome"]),
        }
        for scenario in _SYNTHETIC_SCENARIOS
    ]


def run_context_pilot(
    db: Session,
    *,
    user_id: str,
    source: PilotSource,
    idempotency_key: str,
    scenario_id: str | None = None,
    purpose: str | None = None,
    confirmed_opt_in: bool = False,
    allow_ai: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run one predefined synthetic or explicitly opted-in pilot scenario."""
    timestamp = _utc_naive(now or datetime.utcnow())
    key = _validate_idempotency_key(idempotency_key)
    request_fingerprint = _request_fingerprint({
        "command": "run",
        "source": source,
        "scenario_id": scenario_id,
        "purpose": purpose,
        "confirmed_opt_in": confirmed_opt_in,
        "allow_ai": allow_ai,
    })

    if source == "synthetic":
        if purpose is not None or confirmed_opt_in or allow_ai:
            raise ContextPilotValidationError(
                "Synthetic scenarios do not accept athlete context options"
            )
        scenario = _synthetic_scenario(scenario_id)
        expected_kind = None
    elif source == "opt_in":
        scenario = None
        if not confirmed_opt_in:
            raise ContextPilotValidationError(
                "The athlete must explicitly opt in to this pilot run"
            )
        if scenario_id is not None:
            raise ContextPilotValidationError(
                "Opt-in runs cannot select a synthetic scenario"
            )
        if purpose not in PILOT_ALLOWED_PURPOSES:
            raise ContextPilotValidationError("Pilot purpose is outside scope")
        expected_kind = (
            "execution_explanation"
            if purpose == "execution_interpretation"
            else "temporary_constraint"
        )
    else:
        raise ContextPilotValidationError("Pilot source is invalid")

    reservation, reserved = _reserve_run(
        db,
        user_id=user_id,
        source=source,
        idempotency_key=key,
        request_fingerprint=request_fingerprint,
        timestamp=timestamp,
    )
    if not reserved:
        return _run_result_from_revision(db, reservation, now=timestamp)

    try:
        if source == "synthetic":
            assert scenario is not None
            result = _synthetic_result(scenario)
            revision = _finalize_run(
                db,
                reservation=reservation,
                result=result,
                source=source,
                scenario_id=str(scenario["id"]),
                context_item_ids=(),
                before=(),
                after=(),
                request_fingerprint=request_fingerprint,
                timestamp=timestamp,
            )
            result["run_id"] = revision.id
            if result["proposal"] is not None:
                result["proposal"]["id"] = None
            return result

        assert purpose is not None
        assert expected_kind is not None
        _validate_pilot_context_kinds(
            db,
            user_id=user_id,
            purpose=purpose,
            expected_kind=expected_kind,
            now=timestamp,
        )
        try:
            decision = process_personal_context(
                db,
                user_id=user_id,
                purpose=purpose,
                kinds=(expected_kind,),
                allow_ai=allow_ai,
                now=timestamp,
            )
            db.rollback()
            lock_plan_writes(db, user_id)
            projection = project_personal_context(
                db,
                user_id=user_id,
                purpose=purpose,
                kinds=(expected_kind,),
                now=timestamp,
            )
        except _PRIVATE_PROCESSING_EXCEPTIONS:
            db.rollback()
            result = _base_result(
                source="opt_in",
                outcome="insufficient_evidence",
                reason_code="context_processing_unavailable",
                processing_status="failed",
                processing_mode="deterministic_policy",
                uncertainty="high",
            )
            revision = _finalize_run(
                db,
                reservation=reservation,
                result=result,
                source=source,
                scenario_id=None,
                context_item_ids=(),
                before=(),
                after=(),
                request_fingerprint=request_fingerprint,
                timestamp=timestamp,
            )
            result["run_id"] = revision.id
            return result

        if set(decision.context_item_ids) != {
            item.item_id for item in projection.items
        }:
            result = _base_result(
                source="opt_in",
                outcome="insufficient_evidence",
                reason_code="context_changed_during_processing",
                processing_status="failed",
                processing_mode=decision.processing_mode,
                uncertainty="high",
            )
            revision = _finalize_run(
                db,
                reservation=reservation,
                result=result,
                source=source,
                scenario_id=None,
                context_item_ids=(),
                before=(),
                after=(),
                request_fingerprint=request_fingerprint,
                timestamp=timestamp,
            )
            result["run_id"] = revision.id
            return result

        item_rows = _pilot_item_rows(
            db,
            user_id=user_id,
            item_ids=decision.context_item_ids,
        )
        evaluated, before, after, expiry = _evaluate_opt_in_result(
            db,
            user_id=user_id,
            purpose=purpose,
            decision=decision,
            projection=projection,
            item_rows=item_rows,
            now=timestamp,
        )
        revision = _finalize_run(
            db,
            reservation=reservation,
            result=evaluated,
            source=source,
            scenario_id=None,
            context_item_ids=decision.context_item_ids,
            before=before,
            after=after,
            request_fingerprint=request_fingerprint,
            timestamp=timestamp,
            expires_at=expiry,
        )
        evaluated["run_id"] = revision.id
        if evaluated["proposal"] is not None:
            evaluated["proposal"]["id"] = revision.id
        return evaluated
    except Exception:
        _release_run_reservation(db, reservation)
        raise


def get_context_pilot_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return one owner-scoped proposal and its derived lifecycle state."""
    proposal = db.execute(
        select(PlanRevision).where(
            PlanRevision.id == proposal_id,
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "context_pilot_proposal",
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise ContextPilotNotFound(proposal_id)
    return _proposal_from_revision(
        db,
        proposal,
        now=_utc_naive(now or datetime.utcnow()),
    )


def respond_to_context_pilot_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    response: PilotResponse,
    idempotency_key: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Accept, reject, or defer a pending proposal.

    Rejection and deferral never mutate the plan. Acceptance revalidates the
    exact context and workout snapshot, then appends the canonical revision.
    """
    if response not in _RESPONSE_OPERATIONS:
        raise ContextPilotValidationError("Pilot response is invalid")
    timestamp = _utc_naive(now or datetime.utcnow())
    key = _validate_idempotency_key(idempotency_key)
    request_fingerprint = _request_fingerprint({
        "command": "respond",
        "proposal_id": proposal_id,
        "response": response,
    })
    existing = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key == key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        details = _details(existing)
        if (
            existing.operation != _RESPONSE_OPERATIONS[response]
            or details.get("proposal_revision_id") != proposal_id
            or details.get("request_fingerprint") != request_fingerprint
        ):
            raise ContextPilotConflict("Pilot idempotency key is already used")
        return _response_result_for_event(
            db,
            user_id=user_id,
            response=response,
            event=existing,
            proposal_id=proposal_id,
        )

    db.rollback()
    lock_plan_writes(db, user_id)
    existing = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key == key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        details = _details(existing)
        if (
            existing.operation != _RESPONSE_OPERATIONS[response]
            or details.get("proposal_revision_id") != proposal_id
            or details.get("request_fingerprint") != request_fingerprint
        ):
            db.rollback()
            raise ContextPilotConflict(
                "Pilot idempotency key is already used"
            )
        db.rollback()
        return _response_result_for_event(
            db,
            user_id=user_id,
            response=response,
            event=existing,
            proposal_id=proposal_id,
        )
    proposal = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.id == proposal_id,
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "context_pilot_proposal",
        )
        .with_for_update()
    ).scalar_one_or_none()
    if proposal is None:
        db.rollback()
        raise ContextPilotNotFound(proposal_id)
    current = _proposal_from_revision(db, proposal, now=timestamp)
    if current["status"] != "pending":
        db.rollback()
        raise ContextPilotConflict(
            f"Pilot proposal is {current['status']}"
        )

    details = _details(proposal)
    context_item_ids = tuple(_string_list(details.get("context_item_ids")))
    if not context_item_ids or not _context_references_are_current(
        db,
        user_id=user_id,
        item_ids=context_item_ids,
        now=timestamp,
    ):
        db.rollback()
        raise ContextPilotConflict("Pilot context is no longer current")

    if response in {"reject", "defer"}:
        event, _ = record_plan_revision_idempotent(
            db,
            user_id=user_id,
            operation=_RESPONSE_OPERATIONS[response],
            actor_type="user",
            actor_id=user_id,
            origin="api.context_pilot.response",
            before=proposal.before_snapshot or [],
            after=proposal.before_snapshot or [],
            details={
                "pilot_schema_version": PILOT_SCHEMA_VERSION,
                "policy_version": PILOT_POLICY_VERSION,
                "proposal_revision_id": proposal.id,
                "response": response,
                "request_fingerprint": request_fingerprint,
            },
            idempotency_key=key,
        )
        db.commit()
        return _response_result_for_event(
            db,
            user_id=user_id,
            response=response,
            event=event,
            proposal_id=proposal.id,
        )

    before = _single_snapshot(
        proposal.before_snapshot,
        error="Pilot proposal base snapshot is invalid",
    )
    after = _single_snapshot(
        proposal.after_snapshot,
        error="Pilot proposal result snapshot is invalid",
    )
    _validate_pilot_diff(before, after)
    canonical_id = str(before.get("canonical_id") or "")
    workout = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.canonical_id == canonical_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if workout is None or not _snapshots_match_exactly(workout, before):
        db.rollback()
        raise ContextPilotConflict(
            "Workout changed after the pilot proposal"
        )
    current_date = effective_athlete_date(
        load_config_from_db(user_id, db),
        timestamp,
    )
    if workout.date < current_date:
        db.rollback()
        raise ContextPilotConflict("Pilot proposal workout is no longer mutable")

    current_snapshot = plan_snapshot(workout)
    _restore_snapshot(workout, after)
    db.flush()
    committed = plan_snapshot(workout)
    if not _snapshots_match_exactly(committed, after):
        db.rollback()
        raise ContextPilotConflict(
            "Pilot proposal could not be applied exactly"
        )
    event, created = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation="context_pilot_accept",
        actor_type="user",
        actor_id=user_id,
        origin="api.context_pilot.accept",
        before=[current_snapshot],
        after=[committed],
        details={
            "pilot_schema_version": PILOT_SCHEMA_VERSION,
            "policy_version": PILOT_POLICY_VERSION,
            "proposal_revision_id": proposal.id,
            "context_item_ids": list(context_item_ids),
            "action_code": "shorten_workout_duration",
            "approval": "athlete",
            "request_fingerprint": request_fingerprint,
        },
        idempotency_key=key,
    )
    if not created:
        db.rollback()
        return _response_result_for_event(
            db,
            user_id=user_id,
            response=response,
            event=event,
            proposal_id=proposal.id,
        )
    bump_revisions(db, user_id, ["plans"])
    db.commit()
    return _response_result_for_event(
        db,
        user_id=user_id,
        response=response,
        event=event,
        proposal_id=proposal.id,
    )


def build_context_pilot_evaluation(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return aggregate operational counts with explicit evidence gaps."""
    timestamp = _utc_naive(now or datetime.utcnow())
    events = db.execute(
        select(PlanRevision).where(
            PlanRevision.operation.in_(
                tuple(_RUN_OPERATIONS)
                + tuple(_RESPONSE_OPERATIONS.values())
                + (_REVERSAL_OPERATION,)
            )
        )
    ).scalars().all()
    runs = [event for event in events if event.operation in _RUN_OPERATIONS]
    responses = [
        event
        for event in events
        if event.operation in _RESPONSE_OPERATIONS.values()
    ]
    outcomes = {outcome: 0 for outcome in sorted(PILOT_OUTCOMES)}
    processing_failures = 0
    synthetic_runs = 0
    opt_in_runs = 0
    policy_drift = 0
    private_schema_violations = 0
    safety_proposals = 0
    autonomous_acceptances = 0
    completed_proposal_privacy_scrubs = 0
    acceptance_ids: set[str] = set()

    for event in runs:
        details = _details(event)
        outcome = details.get("outcome")
        if outcome in outcomes:
            outcomes[str(outcome)] += 1
        if details.get("processing_status") == "failed":
            processing_failures += 1
        if details.get("scenario_source") == "synthetic":
            synthetic_runs += 1
        elif details.get("scenario_source") == "opt_in":
            opt_in_runs += 1
        if details.get("policy_version") != PILOT_POLICY_VERSION:
            policy_drift += 1
        if _contains_forbidden_stored_key(details):
            private_schema_violations += 1
        if event.operation == "context_pilot_proposal" and outcome == "safety":
            safety_proposals += 1
        if (
            event.operation == "context_pilot_proposal"
            and details.get("proposal_content_status")
            == "removed_by_athlete"
        ):
            completed_proposal_privacy_scrubs += 1

    response_counts = {
        "accepted": 0,
        "rejected": 0,
        "deferred": 0,
        "reversed": 0,
    }
    for event in responses:
        if event.operation == "context_pilot_accept":
            response_counts["accepted"] += 1
            acceptance_ids.add(event.id)
            if event.actor_type != "user":
                autonomous_acceptances += 1
        elif event.operation == "context_pilot_reject":
            response_counts["rejected"] += 1
        elif event.operation == "context_pilot_defer":
            response_counts["deferred"] += 1
        if _details(event).get("policy_version") != PILOT_POLICY_VERSION:
            policy_drift += 1
        if _contains_forbidden_stored_key(_details(event)):
            private_schema_violations += 1
    for event in events:
        if (
            event.operation == _REVERSAL_OPERATION
            and str(_details(event).get("adjustment_revision_id") or "")
            in acceptance_ids
        ):
            response_counts["reversed"] += 1

    return {
        "schema_version": PILOT_SCHEMA_VERSION,
        "policy_version": PILOT_POLICY_VERSION,
        "generated_at": utc_isoformat(timestamp),
        "scope": {
            "inputs": [
                "missed_or_modified_workout_explanation",
                "temporary_availability_constraint",
            ],
            "automation": "suggestion_only",
            "retention_expansion": False,
        },
        "operational_counts": {
            "runs": len(runs),
            "synthetic_runs": synthetic_runs,
            "opt_in_runs": opt_in_runs,
            "processing_failures": processing_failures,
            "outcomes": outcomes,
            "deletions": {
                "completed_proposal_privacy_scrubs":
                    completed_proposal_privacy_scrubs,
                "failure_state": "not_measured",
                "failure_reason_code":
                    "privacy_preserving_failure_link_unavailable",
            },
        },
        "proposal_responses": response_counts,
        "checks": {
            "privacy": {
                "state": "measured",
                "measure": "stored_payload_schema",
                "violations": private_schema_violations,
            },
            "safety": {
                "state": "measured",
                "safety_outcomes": outcomes["safety"],
                "safety_proposals": safety_proposals,
            },
            "subgroup": {
                "state": "not_measured",
                "reason_code": "private_context_cohorts_prohibited",
            },
            "drift": {
                "state": "measured",
                "unexpected_policy_versions": policy_drift,
            },
            "adverse_outcomes": {
                "state": "not_measured",
                "reason_code": "no_validated_adverse_outcome_link",
            },
        },
        "falsification": {
            "automatic_mutation": {
                "state": "measured",
                "observed": autonomous_acceptances,
            },
            "safety_boundary_bypass": {
                "state": "measured",
                "observed": safety_proposals,
            },
            "private_payload_schema": {
                "state": "measured",
                "observed": private_schema_violations,
            },
            "policy_version_drift": {
                "state": "measured",
                "observed": policy_drift,
            },
            "worse_outcomes_than_no_change": {
                "state": "not_measured",
                "reason_code": "no_comparable_outcome_evidence",
            },
            "deletion_cleanup": {
                "state": (
                    "insufficient_evidence"
                    if not completed_proposal_privacy_scrubs
                    else "measured"
                ),
                "completed_proposal_privacy_scrubs":
                    completed_proposal_privacy_scrubs,
                "failure_state": "not_measured",
            },
        },
        "review_gate": _review_gate(),
    }


def _evaluate_opt_in_result(
    db: Session,
    *,
    user_id: str,
    purpose: str,
    decision: ContextDecision,
    projection: ContextProjection,
    item_rows: Sequence[PersonalContextItem],
    now: datetime,
) -> tuple[
    dict[str, Any],
    Sequence[Mapping[str, Any]],
    Sequence[Mapping[str, Any]],
    datetime | None,
]:
    result = _base_result(
        source="opt_in",
        outcome=decision.outcome,
        reason_code=decision.reason_code,
        processing_status="completed",
        processing_mode=decision.processing_mode,
        uncertainty=decision.uncertainty,
    )
    expiry = min(
        (
            row.expires_at
            for row in item_rows
            if row.expires_at is not None
        ),
        default=None,
    )
    if decision.outcome != "suggestion":
        if decision.outcome == "clarification":
            result["clarification"] = {
                "question_code": _clarification_code(decision.reason_code),
                "optional": True,
            }
        return result, (), (), expiry

    if purpose == "execution_interpretation":
        statuses = {
            str(item.fields.get("workout_status"))
            for item in projection.items
            if item.fields.get("workout_status") in {"missed", "modified"}
        }
        if statuses:
            result = _base_result(
                source="opt_in",
                outcome="no_change",
                reason_code="missed_session_catch_up_disabled",
                processing_status="completed",
                processing_mode=decision.processing_mode,
                uncertainty=decision.uncertainty,
            )
        else:
            result = _base_result(
                source="opt_in",
                outcome="insufficient_evidence",
                reason_code="execution_outcome_missing",
                processing_status="completed",
                processing_mode=decision.processing_mode,
                uncertainty=decision.uncertainty,
            )
        return result, (), (), expiry

    action = _availability_action(
        db,
        user_id=user_id,
        items=projection.items,
        now=now,
    )
    if action["outcome"] != "suggestion":
        result = _base_result(
            source="opt_in",
            outcome=str(action["outcome"]),
            reason_code=str(action["reason_code"]),
            processing_status="completed",
            processing_mode=decision.processing_mode,
            uncertainty=decision.uncertainty,
        )
        if action["outcome"] == "clarification":
            result["clarification"] = {
                "question_code": str(action["question_code"]),
                "optional": True,
            }
        return result, (), (), expiry

    before = action["before"]
    after = action["after"]
    proposal_action = action["action"]
    result["outcome"] = "suggestion"
    result["reason_code"] = "availability_duration_conflict"
    result["proposal_scope"] = "workout"
    result["proposal"] = {
        "id": None,
        "status": "pending",
        "action": proposal_action,
        "before": _public_snapshot(before),
        "after": _public_snapshot(after),
        "context_item_ids": [
            item.item_id for item in projection.items
        ],
        "allowed_responses": ["accept", "reject", "defer"],
        "acceptance_available": True,
        "acceptance_requires_athlete": True,
        "automatic_mutation": False,
        "unknowns": ["training_response", "goal_effect"],
        "tradeoffs": [
            "reduced_planned_duration",
            "session_not_completed_as_originally_planned",
        ],
        "expected_goal_effect": "not_estimated",
        "context_controls": ["inspect", "correct", "exclude", "delete"],
        "expires_at": (
            utc_isoformat(expiry) if expiry is not None else None
        ),
        "accepted_revision_id": None,
    }
    return result, (before,), (after,), expiry


def _availability_action(
    db: Session,
    *,
    user_id: str,
    items: Sequence[ProjectedContextItem],
    now: datetime,
) -> dict[str, Any]:
    associated: list[tuple[set[date], int]] = []
    saw_dates = False
    saw_limits = False
    current_date = effective_athlete_date(
        load_config_from_db(user_id, db),
        now,
    )
    for item in items:
        item_dates: set[date] = set()
        for value in item.fields.get("affected_dates", []):
            try:
                parsed = date.fromisoformat(str(value))
            except ValueError:
                continue
            if parsed >= current_date:
                item_dates.add(parsed)
        saw_dates = saw_dates or bool(item_dates)
        limit = item.fields.get("maximum_available_minutes")
        item_limit = (
            limit
            if isinstance(limit, int) and not isinstance(limit, bool)
            else None
        )
        saw_limits = saw_limits or item_limit is not None
        if item_dates and item_limit is not None:
            associated.append((item_dates, item_limit))
    if not saw_dates:
        return {
            "outcome": "insufficient_evidence",
            "reason_code": "availability_window_missing",
        }
    if not saw_limits:
        return {
            "outcome": "insufficient_evidence",
            "reason_code": "availability_limit_missing",
        }
    if not associated:
        return {
            "outcome": "insufficient_evidence",
            "reason_code": "availability_window_and_limit_not_associated",
        }
    dates = set().union(*(item_dates for item_dates, _ in associated))
    limits = {item_limit for _, item_limit in associated}
    if len(limits) != 1:
        return {
            "outcome": "clarification",
            "reason_code": "conflicting_availability_limits",
            "question_code": "which_availability_limit_applies",
        }
    maximum_minutes = next(iter(limits))
    workouts = db.execute(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date.in_(dates),
            TrainingPlan.workout_origin == "generated",
        )
        .order_by(TrainingPlan.date, TrainingPlan.id)
    ).scalars().all()
    if not workouts:
        return {
            "outcome": "no_change",
            "reason_code": "no_eligible_generated_workout",
        }
    missing_duration = [
        workout
        for workout in workouts
        if workout.planned_duration_min is None
    ]
    if missing_duration:
        return {
            "outcome": "insufficient_evidence",
            "reason_code": "workout_duration_missing",
        }
    conflicts = [
        workout
        for workout in workouts
        if float(workout.planned_duration_min or 0) > maximum_minutes
    ]
    if not conflicts:
        return {
            "outcome": "no_change",
            "reason_code": "current_plan_within_availability",
        }
    if len(conflicts) > 1:
        return {
            "outcome": "clarification",
            "reason_code": "multiple_eligible_workouts",
            "question_code": "which_workout_to_adjust",
        }
    workout = conflicts[0]
    if workout.planned_distance_km is not None:
        return {
            "outcome": "insufficient_evidence",
            "reason_code": "distance_based_workout_not_supported",
        }
    before = plan_snapshot(workout)
    after = dict(before)
    after["planned_duration_min"] = maximum_minutes
    after["workout_origin"] = "accepted_target"
    return {
        "outcome": "suggestion",
        "reason_code": "availability_duration_conflict",
        "before": before,
        "after": after,
        "action": {
            "type": "shorten_workout_duration",
            "canonical_id": workout.canonical_id,
            "planned_duration_min": maximum_minutes,
        },
    }


def _reserve_run(
    db: Session,
    *,
    user_id: str,
    source: PilotSource,
    idempotency_key: str,
    request_fingerprint: str,
    timestamp: datetime,
) -> tuple[PlanRevision, bool]:
    """Atomically claim a run key before any context use or AI disclosure."""
    while True:
        revision, created = record_plan_revision_idempotent(
            db,
            user_id=user_id,
            operation=_RUN_RESERVATION_OPERATION,
            actor_type="user" if source == "opt_in" else "system",
            actor_id=user_id if source == "opt_in" else "synthetic-scenario",
            origin="api.context_pilot.run",
            before=(),
            after=(),
            details={
                "pilot_schema_version": PILOT_SCHEMA_VERSION,
                "scenario_source": source,
                "request_fingerprint": request_fingerprint,
                "processing_status": "reserved",
            },
            idempotency_key=idempotency_key,
        )
        if created:
            revision.created_at = timestamp
            db.commit()
            return revision, True

        details = _details(revision)
        if details.get("request_fingerprint") != request_fingerprint:
            db.rollback()
            raise ContextPilotConflict(
                "Pilot idempotency key is already used"
            )
        if revision.operation in _RUN_OPERATIONS:
            db.rollback()
            current = db.get(PlanRevision, revision.id)
            if current is None:
                continue
            return current, False
        if revision.operation != _RUN_RESERVATION_OPERATION:
            db.rollback()
            raise ContextPilotConflict(
                "Pilot idempotency key is already used"
            )

        revision_id = revision.id
        db.rollback()
        completed = _wait_for_reserved_run(
            db,
            user_id=user_id,
            revision_id=revision_id,
            request_fingerprint=request_fingerprint,
        )
        if completed is not None:
            return completed, False


def _wait_for_reserved_run(
    db: Session,
    *,
    user_id: str,
    revision_id: str,
    request_fingerprint: str,
) -> PlanRevision | None:
    """Wait briefly for the reservation owner, or retry after clean release."""
    deadline = monotonic() + _RUN_RESERVATION_WAIT_SECONDS
    while monotonic() < deadline:
        db.rollback()
        revision = db.execute(
            select(PlanRevision).where(
                PlanRevision.id == revision_id,
                PlanRevision.user_id == user_id,
            )
        ).scalar_one_or_none()
        if revision is None:
            return None
        details = _details(revision)
        if details.get("request_fingerprint") != request_fingerprint:
            raise ContextPilotConflict(
                "Pilot idempotency key is already used"
            )
        if revision.operation in _RUN_OPERATIONS:
            return revision
        if revision.operation != _RUN_RESERVATION_OPERATION:
            raise ContextPilotConflict(
                "Pilot idempotency key is already used"
            )
        sleep(0.025)
    raise ContextPilotConflict("Pilot run is still processing")


def _release_run_reservation(
    db: Session,
    reservation: PlanRevision,
) -> None:
    """Release only an unfinished reservation so a clean retry can proceed."""
    try:
        db.rollback()
        lock_plan_writes(db, reservation.user_id)
        current = db.execute(
            select(PlanRevision)
            .where(
                PlanRevision.id == reservation.id,
                PlanRevision.user_id == reservation.user_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if (
            current is not None
            and current.operation == _RUN_RESERVATION_OPERATION
        ):
            db.delete(current)
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()


def _finalize_run(
    db: Session,
    *,
    reservation: PlanRevision,
    result: Mapping[str, Any],
    source: PilotSource,
    scenario_id: str | None,
    context_item_ids: Sequence[str],
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    request_fingerprint: str,
    timestamp: datetime,
    expires_at: datetime | None = None,
) -> PlanRevision:
    """Finalize the already-reserved run row into its durable replay result."""
    operation = (
        "context_pilot_failure"
        if result["processing_status"] == "failed"
        else "context_pilot_proposal"
        if result["outcome"] == "suggestion" and source == "opt_in"
        else "context_pilot_decision"
    )
    proposal = result.get("proposal")
    action = (
        dict(proposal.get("action") or {})
        if isinstance(proposal, Mapping)
        else None
    )
    details: dict[str, Any] = {
        "pilot_schema_version": PILOT_SCHEMA_VERSION,
        "policy_version": PILOT_POLICY_VERSION,
        "scenario_source": source,
        "scenario_id": scenario_id,
        "outcome": result["outcome"],
        "reason_code": result["reason_code"],
        "processing_status": result["processing_status"],
        "processing_mode": result["processing_mode"],
        "proposal_scope": result["proposal_scope"],
        "uncertainty": result["uncertainty"],
        "request_fingerprint": request_fingerprint,
        "no_change_comparator": "keep_current_plan",
        "safety_blocked": result["outcome"] == "safety",
    }
    if context_item_ids:
        details["context_item_ids"] = list(context_item_ids)
    if action:
        details["action"] = action
    if result.get("clarification"):
        details["question_code"] = result["clarification"]["question_code"]
    if expires_at is not None:
        details["expires_at"] = utc_isoformat(expires_at)
    db.rollback()
    lock_plan_writes(db, reservation.user_id)
    revision = db.execute(
        select(PlanRevision)
        .where(
            PlanRevision.id == reservation.id,
            PlanRevision.user_id == reservation.user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if (
        revision is None
        or revision.operation != _RUN_RESERVATION_OPERATION
        or _details(revision).get("request_fingerprint")
        != request_fingerprint
    ):
        db.rollback()
        raise ContextPilotConflict("Pilot run reservation was lost")
    revision.operation = operation
    revision.actor_type = "user" if source == "opt_in" else "system"
    revision.actor_id = (
        reservation.user_id if source == "opt_in" else "synthetic-scenario"
    )
    revision.before_snapshot = [plan_snapshot(row) for row in before]
    revision.after_snapshot = [plan_snapshot(row) for row in after]
    revision.details = details
    revision.created_at = timestamp
    db.commit()
    return revision


def _run_result_from_revision(
    db: Session,
    revision: PlanRevision,
    *,
    now: datetime,
) -> dict[str, Any]:
    details = _details(revision)
    source = str(details.get("scenario_source") or "")
    outcome = str(details.get("outcome") or "")
    if source not in {"synthetic", "opt_in"} or outcome not in PILOT_OUTCOMES:
        raise ContextPilotConflict("Stored pilot run is invalid")
    result = _base_result(
        source=source,
        outcome=outcome,
        reason_code=str(details.get("reason_code") or "unknown"),
        processing_status=str(
            details.get("processing_status") or "completed"
        ),
        processing_mode=str(
            details.get("processing_mode") or "deterministic_policy"
        ),
        uncertainty=str(details.get("uncertainty") or "high"),
    )
    result["run_id"] = revision.id
    result["scenario_id"] = details.get("scenario_id")
    if details.get("question_code"):
        result["clarification"] = {
            "question_code": details["question_code"],
            "optional": True,
        }
    if revision.operation == "context_pilot_proposal":
        result["proposal_scope"] = "workout"
        result["proposal"] = _proposal_from_revision(db, revision, now=now)
    elif outcome == "suggestion" and source == "synthetic":
        result["proposal_scope"] = "workout"
        result["proposal"] = {
            "id": None,
            "status": "synthetic_only",
            "action": dict(details.get("action") or {}),
            "before": None,
            "after": None,
            "context_item_ids": [],
            "allowed_responses": [],
            "acceptance_available": False,
            "acceptance_requires_athlete": True,
            "automatic_mutation": False,
            "unknowns": ["training_response", "goal_effect"],
            "tradeoffs": [
                "reduced_planned_duration",
                "session_not_completed_as_originally_planned",
            ],
            "expected_goal_effect": "not_estimated",
            "context_controls": [],
            "expires_at": None,
        }
    return result


def _proposal_from_revision(
    db: Session,
    proposal: PlanRevision,
    *,
    now: datetime,
) -> dict[str, Any]:
    details = _details(proposal)
    status = "pending"
    acceptance: PlanRevision | None = None
    before = (
        proposal.before_snapshot[0]
        if len(proposal.before_snapshot or []) == 1
        else None
    )
    after = (
        proposal.after_snapshot[0]
        if len(proposal.after_snapshot or []) == 1
        else None
    )
    responses = [
        event
        for event in db.execute(
            select(PlanRevision).where(
                PlanRevision.user_id == proposal.user_id,
                PlanRevision.operation.in_(
                    tuple(_RESPONSE_OPERATIONS.values())
                ),
            )
        ).scalars().all()
        if _details(event).get("proposal_revision_id") == proposal.id
    ]
    responses.sort(key=lambda event: (event.created_at, event.id))
    if responses:
        latest = responses[-1]
        if latest.operation == "context_pilot_accept":
            acceptance = latest
            status = "accepted"
        elif latest.operation == "context_pilot_reject":
            status = "rejected"
        else:
            status = "deferred"
    if status == "pending":
        item_ids = _string_list(details.get("context_item_ids"))
        expiry = _parse_utc(details.get("expires_at"))
        if expiry is not None and expiry <= now:
            status = "expired"
        elif (
            details.get("personal_context_status")
            == "removed_by_athlete"
            or not item_ids
            or not _context_references_are_current(
                db,
                user_id=proposal.user_id,
                item_ids=item_ids,
                now=now,
            )
        ):
            status = "invalidated"
        elif not isinstance(before, Mapping):
            status = "invalidated"
        else:
            canonical_id = str(before.get("canonical_id") or "")
            workout = db.execute(
                select(TrainingPlan).where(
                    TrainingPlan.user_id == proposal.user_id,
                    TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                    TrainingPlan.canonical_id == canonical_id,
                )
            ).scalar_one_or_none()
            if (
                workout is None
                or not _snapshots_match_exactly(workout, before)
            ):
                status = "invalidated"
            elif workout.date < effective_athlete_date(
                load_config_from_db(proposal.user_id, db),
                now,
            ):
                status = "expired"
    if acceptance is not None:
        reversal = db.execute(
            select(PlanRevision).where(
                PlanRevision.user_id == proposal.user_id,
                PlanRevision.operation == _REVERSAL_OPERATION,
                PlanRevision.idempotency_key
                == f"auto-adjustment-undo:{acceptance.id}",
            )
        ).scalar_one_or_none()
        if reversal is not None:
            status = "reversed"

    action = details.get("action")
    return {
        "id": proposal.id,
        "status": status,
        "action": dict(action) if isinstance(action, Mapping) else None,
        "before": _public_snapshot(before),
        "after": _public_snapshot(after),
        "context_item_ids": _string_list(details.get("context_item_ids")),
        "allowed_responses": (
            ["accept", "reject", "defer"] if status == "pending" else []
        ),
        "acceptance_available": status == "pending",
        "acceptance_requires_athlete": True,
        "automatic_mutation": False,
        "unknowns": ["training_response", "goal_effect"],
        "tradeoffs": [
            "reduced_planned_duration",
            "session_not_completed_as_originally_planned",
        ],
        "expected_goal_effect": "not_estimated",
        "context_controls": (
            ["inspect", "correct", "exclude", "delete"]
            if details.get("scenario_source") == "opt_in"
            else []
        ),
        "expires_at": details.get("expires_at"),
        "accepted_revision_id": (
            acceptance.id if acceptance is not None else None
        ),
    }


def _response_result(
    *,
    response: PilotResponse,
    event: PlanRevision,
    proposal_id: str,
) -> dict[str, Any]:
    accepted = response == "accept"
    return {
        "proposal_id": proposal_id,
        "status": (
            "accepted"
            if accepted
            else "rejected"
            if response == "reject"
            else "deferred"
        ),
        "revision_id": event.id if accepted else None,
        "event_id": event.id,
        "undo_path": (
            f"/api/plan/adjustments/{event.id}/undo"
            if accepted
            else None
        ),
        "canonical_plan_changed": accepted,
        "athlete_approved": accepted,
    }


def _response_result_for_event(
    db: Session,
    *,
    user_id: str,
    response: PilotResponse,
    event: PlanRevision,
    proposal_id: str,
) -> dict[str, Any]:
    """Return the stable response, recovering accepted delivery if needed."""
    result = _response_result(
        response=response,
        event=event,
        proposal_id=proposal_id,
    )
    if response == "accept":
        result["delivery"] = _acceptance_delivery_result(
            db,
            user_id=user_id,
            acceptance_id=event.id,
        )
    return result


def _acceptance_delivery_result(
    db: Session,
    *,
    user_id: str,
    acceptance_id: str,
) -> dict[str, Any]:
    """Return or durably reconstruct one acceptance delivery consequence."""
    stored = _stored_acceptance_delivery(
        db,
        user_id=user_id,
        acceptance_id=acceptance_id,
    )
    if stored is not None:
        return stored

    db.rollback()
    acceptance = db.execute(
        select(PlanRevision).where(
            PlanRevision.id == acceptance_id,
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "context_pilot_accept",
        )
    ).scalar_one_or_none()
    if acceptance is None:
        raise ContextPilotConflict("Pilot acceptance is unavailable")
    snapshot = _single_snapshot(
        acceptance.after_snapshot,
        error="Pilot acceptance snapshot is invalid",
    )
    db.rollback()
    delivery = _trigger_managed_delivery(
        user_id,
        trigger="context_pilot_athlete_acceptance",
    )
    consequence, created = record_plan_revision_idempotent(
        db,
        user_id=user_id,
        operation=_ACCEPTANCE_DELIVERY_OPERATION,
        actor_type="system",
        actor_id="managed-delivery",
        origin="api.context_pilot.delivery",
        before=[snapshot],
        after=[snapshot],
        details={
            "pilot_schema_version": PILOT_SCHEMA_VERSION,
            "acceptance_revision_id": acceptance_id,
            "delivery": delivery,
        },
        idempotency_key=(
            f"{_ACCEPTANCE_DELIVERY_OPERATION}:{acceptance_id}"
        ),
    )
    if created:
        db.commit()
        return delivery
    db.rollback()
    stored = _stored_acceptance_delivery(
        db,
        user_id=user_id,
        acceptance_id=acceptance_id,
    )
    if stored is None:
        raise ContextPilotConflict("Pilot delivery replay is unavailable")
    return stored


def _stored_acceptance_delivery(
    db: Session,
    *,
    user_id: str,
    acceptance_id: str,
) -> dict[str, Any] | None:
    """Load a previously audited acceptance delivery payload."""
    consequence = db.execute(
        select(PlanRevision).where(
            PlanRevision.user_id == user_id,
            PlanRevision.idempotency_key
            == f"{_ACCEPTANCE_DELIVERY_OPERATION}:{acceptance_id}",
        )
    ).scalar_one_or_none()
    if consequence is None:
        return None
    details = _details(consequence)
    delivery = details.get("delivery")
    if not isinstance(delivery, Mapping):
        raise ContextPilotConflict("Stored pilot delivery is invalid")
    return dict(delivery)


def _base_result(
    *,
    source: str,
    outcome: str,
    reason_code: str,
    processing_status: str,
    processing_mode: str,
    uncertainty: str,
) -> dict[str, Any]:
    return {
        "run_id": None,
        "scenario_source": source,
        "scenario_id": None,
        "outcome": outcome,
        "reason_code": reason_code,
        "processing_status": processing_status,
        "processing_mode": processing_mode,
        "policy_version": PILOT_POLICY_VERSION,
        "uncertainty": uncertainty,
        "proposal_scope": "none",
        "clarification": None,
        "no_change_comparator": {
            "action": "keep_current_plan",
            "selected": outcome != "suggestion",
        },
        "safety": {
            "performance_optimization_blocked": outcome == "safety",
            "medical_assessment_not_provided": True,
        },
        "proposal": None,
        "claim_limits": {
            "guarantees": False,
            "causal_inference": False,
            "diagnosis_or_treatment": False,
        },
        "review_gate": _review_gate(),
    }


def _synthetic_result(scenario: Mapping[str, Any]) -> dict[str, Any]:
    outcome = str(scenario["expected_outcome"])
    result = _base_result(
        source="synthetic",
        outcome=outcome,
        reason_code=str(scenario["reason_code"]),
        processing_status="completed",
        processing_mode="synthetic_policy_replay",
        uncertainty="high",
    )
    result["scenario_id"] = scenario["id"]
    if outcome == "clarification":
        result["clarification"] = {
            "question_code": scenario["question_code"],
            "optional": True,
        }
    if outcome == "suggestion":
        result["proposal_scope"] = "workout"
        result["proposal"] = {
            "id": None,
            "status": "synthetic_only",
            "action": dict(scenario["action"]),
            "before": None,
            "after": None,
            "context_item_ids": [],
            "allowed_responses": [],
            "acceptance_available": False,
            "acceptance_requires_athlete": True,
            "automatic_mutation": False,
            "unknowns": ["training_response", "goal_effect"],
            "tradeoffs": [
                "reduced_planned_duration",
                "session_not_completed_as_originally_planned",
            ],
            "expected_goal_effect": "not_estimated",
            "context_controls": [],
            "expires_at": None,
        }
    return result


def _synthetic_scenario(scenario_id: str | None) -> Mapping[str, Any]:
    for scenario in _SYNTHETIC_SCENARIOS:
        if scenario["id"] == scenario_id:
            return scenario
    raise ContextPilotValidationError("Synthetic pilot scenario is invalid")


def _validate_pilot_context_kinds(
    db: Session,
    *,
    user_id: str,
    purpose: str,
    expected_kind: str,
    now: datetime,
) -> None:
    """Reject out-of-scope active context before payload processing begins."""
    purpose_confirmed = (
        db.query(PersonalContextConsentReceipt.id)
        .filter(
            PersonalContextConsentReceipt.user_id
            == PersonalContextItem.user_id,
            PersonalContextConsentReceipt.context_item_id
            == PersonalContextItem.id,
            PersonalContextConsentReceipt.context_version
            == PersonalContextItem.version,
            PersonalContextConsentReceipt.purpose
            == PersonalContextItem.purpose,
            PersonalContextConsentReceipt.consent_scope
            == "purpose_confirmation",
            PersonalContextConsentReceipt.decision == "granted",
        )
        .exists()
    )
    rows = (
        db.query(PersonalContextItem)
        .filter(
            PersonalContextItem.user_id == user_id,
            PersonalContextItem.purpose == purpose,
            PersonalContextItem.state == "active",
            PersonalContextItem.starts_at <= now,
            or_(
                PersonalContextItem.expires_at.is_(None),
                PersonalContextItem.expires_at > now,
            ),
            purpose_confirmed,
        )
        .order_by(
            PersonalContextItem.lineage_id,
            PersonalContextItem.version.desc(),
        )
        .all()
    )
    seen_lineages: set[str] = set()
    for row in rows:
        if row.lineage_id in seen_lineages:
            continue
        seen_lineages.add(row.lineage_id)
        if (
            row.kind not in PILOT_ALLOWED_KINDS
            or row.kind != expected_kind
        ):
            raise ContextPilotValidationError(
                "Context kind is outside pilot scope"
            )


def _pilot_item_rows(
    db: Session,
    *,
    user_id: str,
    item_ids: Sequence[str],
) -> list[PersonalContextItem]:
    if not item_ids:
        return []
    rows = db.execute(
        select(PersonalContextItem).where(
            PersonalContextItem.user_id == user_id,
            PersonalContextItem.id.in_(item_ids),
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    return [by_id[item_id] for item_id in item_ids if item_id in by_id]


def _context_references_are_current(
    db: Session,
    *,
    user_id: str,
    item_ids: Sequence[str],
    now: datetime,
) -> bool:
    rows = _pilot_item_rows(db, user_id=user_id, item_ids=item_ids)
    if len(rows) != len(set(item_ids)):
        return False
    for row in rows:
        if (
            row.kind not in PILOT_ALLOWED_KINDS
            or row.state != "active"
            or row.starts_at > now
            or (row.expires_at is not None and row.expires_at <= now)
        ):
            return False
        newer = db.execute(
            select(PersonalContextItem.id).where(
                PersonalContextItem.user_id == user_id,
                PersonalContextItem.lineage_id == row.lineage_id,
                PersonalContextItem.version > row.version,
            )
        ).scalar_one_or_none()
        if newer is not None:
            return False
        purpose_receipt = db.execute(
            select(PersonalContextConsentReceipt.id).where(
                PersonalContextConsentReceipt.user_id == user_id,
                PersonalContextConsentReceipt.context_item_id == row.id,
                PersonalContextConsentReceipt.context_version == row.version,
                PersonalContextConsentReceipt.purpose == row.purpose,
                PersonalContextConsentReceipt.consent_scope
                == "purpose_confirmation",
                PersonalContextConsentReceipt.decision == "granted",
            )
        ).scalar_one_or_none()
        if purpose_receipt is None:
            return False
    return True


def _validate_pilot_diff(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> None:
    if (
        before.get("canonical_id") != after.get("canonical_id")
        or before.get("date") != after.get("date")
        or before.get("source") != after.get("source")
    ):
        raise ContextPilotConflict("Pilot proposal identity is invalid")
    changed = {
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }
    if changed != {"planned_duration_min", "workout_origin"}:
        raise ContextPilotConflict("Pilot proposal scope is invalid")
    before_minutes = before.get("planned_duration_min")
    after_minutes = after.get("planned_duration_min")
    if (
        not isinstance(before_minutes, (int, float))
        or isinstance(before_minutes, bool)
        or not isinstance(after_minutes, (int, float))
        or isinstance(after_minutes, bool)
        or after_minutes <= 0
        or after_minutes >= before_minutes
        or before.get("workout_origin") != "generated"
        or after.get("workout_origin") != "accepted_target"
    ):
        raise ContextPilotConflict("Pilot duration proposal is invalid")


def _single_snapshot(
    snapshots: Any,
    *,
    error: str,
) -> Mapping[str, Any]:
    if (
        not isinstance(snapshots, list)
        or len(snapshots) != 1
        or not isinstance(snapshots[0], Mapping)
    ):
        raise ContextPilotConflict(error)
    return snapshots[0]


def _public_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "canonical_id": snapshot.get("canonical_id"),
        "date": snapshot.get("date"),
        "workout_type": snapshot.get("workout_type"),
        "planned_duration_min": snapshot.get("planned_duration_min"),
        "planned_distance_km": snapshot.get("planned_distance_km"),
        "target_power_min": snapshot.get("target_power_min"),
        "target_power_max": snapshot.get("target_power_max"),
        "workout_description": snapshot.get("workout_description"),
    }


def _clarification_code(reason_code: str) -> str:
    return {
        "athlete_clarification_needed": "context_detail_that_changes_action",
        "constraint_details_needed": "availability_window_and_limit",
    }.get(reason_code, "missing_detail_that_changes_action")


def _review_gate() -> dict[str, Any]:
    return {
        "scope_expansion": "new_review_required",
        "automation_expansion": "new_review_required",
        "retention_expansion": "new_review_required",
        "policy_version_change": "new_review_required",
    }


def _details(revision: PlanRevision) -> dict[str, Any]:
    return revision.details if isinstance(revision.details, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _contains_forbidden_stored_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in _FORBIDDEN_STORED_KEYS
            or _contains_forbidden_stored_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_stored_key(item) for item in value)
    return False


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return _utc_naive(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _request_fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_idempotency_key(value: str) -> str:
    if not isinstance(value, str):
        raise ContextPilotValidationError("Idempotency key is invalid")
    normalized = value.strip()
    if not 8 <= len(normalized) <= 128:
        raise ContextPilotValidationError("Idempotency key is invalid")
    return normalized


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
