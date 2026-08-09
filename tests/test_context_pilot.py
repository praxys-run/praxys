"""Suggestion-only adaptive-plan context pilot tests."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Event, Lock
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.context_pilot import (
    PILOT_POLICY_VERSION,
    ContextPilotConflict,
    ContextPilotValidationError,
    build_context_pilot_evaluation,
    get_context_pilot_proposal,
    list_context_pilot_scenarios,
    respond_to_context_pilot_proposal,
    run_context_pilot,
)
from api.personal_context import (
    PersonalContextAccessError,
    confirm_context_item,
    withdraw_context,
)
from api.plan_adjustments import undo_plan_adjustment
from db.models import (
    Base,
    PersonalContextUseReceipt,
    PlanRevision,
    TrainingPlan,
    User,
)


USER_ID = "context-pilot-owner"
OTHER_USER_ID = "context-pilot-other"
NOW = datetime(2026, 9, 14, 9, 0)
WORKOUT_DATE = date(2026, 9, 16)


@pytest.fixture
def pilot_db(tmp_path, monkeypatch) -> Session:
    """Yield an encrypted, isolated pilot database."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    from db import crypto

    crypto._vault = None
    engine = create_engine(f"sqlite:///{tmp_path / 'context-pilot.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        User(
            id=USER_ID,
            email="context-pilot@example.test",
            hashed_password="test",
            is_active=True,
        ),
        User(
            id=OTHER_USER_ID,
            email="context-pilot-other@example.test",
            hashed_password="test",
            is_active=True,
        ),
    ])
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        crypto._vault = None


def _add_workout(
    db: Session,
    *,
    user_id: str = USER_ID,
    workout_date: date = WORKOUT_DATE,
    duration: float = 60.0,
) -> TrainingPlan:
    workout = TrainingPlan(
        user_id=user_id,
        canonical_id=str(uuid4()),
        date=workout_date,
        workout_type="easy",
        planned_duration_min=duration,
        planned_distance_km=None,
        workout_description="Synthetic easy run",
        source="praxys",
        workout_origin="generated",
        meta={"fixture": "synthetic"},
    )
    db.add(workout)
    db.commit()
    return workout


def _add_constraint(
    db: Session,
    *,
    user_id: str = USER_ID,
    category: str = "less_time",
    fields: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> str:
    active_until = expires_at or NOW + timedelta(days=14)
    result = confirm_context_item(
        db,
        user_id=user_id,
        kind="temporary_constraint",
        purpose="plan_adjustment",
        payload={
            "category": category,
            "fields": fields or {
                "affected_dates": [WORKOUT_DATE.isoformat()],
                "maximum_available_minutes": 30,
            },
            "narrative": "Synthetic private detail that must stay private",
        },
        source_actor_type="first_party_web",
        source_actor_id=None,
        consent_text_version="personal-context-purpose-v1",
        client="web",
        idempotency_key=f"context:{uuid4()}",
        starts_at=NOW,
        expires_at=active_until,
        narrative_purge_at=NOW + timedelta(days=30),
        purge_after=active_until + timedelta(days=30),
        now=NOW,
    )
    db.commit()
    return result.item.id


def _add_durable_preference(db: Session) -> str:
    result = confirm_context_item(
        db,
        user_id=USER_ID,
        kind="durable_preference",
        purpose="plan_adjustment",
        payload={
            "category": "less_time",
            "fields": {
                "affected_dates": [WORKOUT_DATE.isoformat()],
                "maximum_available_minutes": 30,
            },
        },
        source_actor_type="first_party_web",
        source_actor_id=None,
        consent_text_version="personal-context-purpose-v1",
        client="web",
        idempotency_key=f"context:{uuid4()}",
        starts_at=NOW,
        now=NOW,
    )
    db.commit()
    return result.item.id


def _run_opt_in(db: Session) -> dict[str, Any]:
    return run_context_pilot(
        db,
        user_id=USER_ID,
        source="opt_in",
        purpose="plan_adjustment",
        confirmed_opt_in=True,
        allow_ai=False,
        idempotency_key=f"pilot:{uuid4()}",
        now=NOW,
    )


def test_predefined_scenarios_cover_all_five_outcomes_without_mutation(
    pilot_db: Session,
) -> None:
    scenarios = list_context_pilot_scenarios()

    assert {scenario["expected_outcome"] for scenario in scenarios} == {
        "clarification",
        "no_change",
        "insufficient_evidence",
        "safety",
        "suggestion",
    }
    for scenario in scenarios:
        result = run_context_pilot(
            pilot_db,
            user_id=USER_ID,
            source="synthetic",
            scenario_id=scenario["id"],
            idempotency_key=f"synthetic:{scenario['id']}",
            now=NOW,
        )
        assert result["outcome"] == scenario["expected_outcome"]
        assert result["policy_version"] == PILOT_POLICY_VERSION
        assert result["scenario_source"] == "synthetic"
        assert result["no_change_comparator"]["action"] == "keep_current_plan"
        assert result["review_gate"]["scope_expansion"] == (
            "new_review_required"
        )
        if result["outcome"] == "clarification":
            assert result["clarification"]["question_code"]
        if result["outcome"] == "safety":
            assert result["safety"]["performance_optimization_blocked"] is True
        if result["outcome"] == "suggestion":
            assert result["proposal"]["status"] == "synthetic_only"
            assert result["proposal"]["acceptance_available"] is False

    assert pilot_db.query(TrainingPlan).count() == 0
    assert not pilot_db.query(PlanRevision).filter(
        PlanRevision.operation == "context_pilot_accept"
    ).all()


def test_opt_in_proposal_requires_athlete_response_and_uses_canonical_undo(
    pilot_db: Session,
    monkeypatch,
) -> None:
    workout = _add_workout(pilot_db)
    context_id = _add_constraint(pilot_db)

    result = _run_opt_in(pilot_db)

    pilot_db.refresh(workout)
    assert result["outcome"] == "suggestion"
    assert result["proposal"]["status"] == "pending"
    assert result["proposal"]["action"] == {
        "type": "shorten_workout_duration",
        "canonical_id": workout.canonical_id,
        "planned_duration_min": 30,
    }
    assert result["proposal"]["acceptance_requires_athlete"] is True
    assert workout.planned_duration_min == 60

    monkeypatch.setattr(
        "api.plan_delivery.rolling.trigger_managed_plan_delivery",
        lambda *args, **kwargs: None,
    )
    accepted = respond_to_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        response="accept",
        idempotency_key="pilot-response-accept",
        now=NOW + timedelta(minutes=1),
    )

    pilot_db.refresh(workout)
    assert accepted["status"] == "accepted"
    assert accepted["revision_id"]
    assert accepted["undo_path"].endswith(
        f"/{accepted['revision_id']}/undo"
    )
    assert workout.planned_duration_min == 30
    assert workout.workout_origin == "accepted_target"
    revision = pilot_db.get(PlanRevision, accepted["revision_id"])
    assert revision is not None
    assert revision.operation == "context_pilot_accept"
    assert revision.actor_type == "user"
    serialized = json.dumps(revision.details)
    assert context_id in serialized
    assert "Synthetic private detail" not in serialized
    assert "less_time" not in serialized

    undone = undo_plan_adjustment(
        pilot_db,
        user_id=USER_ID,
        revision_id=accepted["revision_id"],
    )

    pilot_db.refresh(workout)
    assert undone["status"] == "undone"
    assert workout.planned_duration_min == 60
    assert workout.workout_origin == "generated"
    proposal = get_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        now=NOW + timedelta(minutes=2),
    )
    assert proposal["status"] == "reversed"
    assert withdraw_context(
        pilot_db,
        user_id=USER_ID,
        item_id=context_id,
        expected_version=1,
        now=NOW + timedelta(minutes=3),
    )
    after_deletion = get_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        now=NOW + timedelta(minutes=4),
    )
    assert after_deletion["status"] == "reversed"
    assert after_deletion["accepted_revision_id"] == accepted["revision_id"]


def test_acceptance_replay_returns_the_original_delivery_result(
    pilot_db: Session,
    monkeypatch,
) -> None:
    _add_workout(pilot_db)
    _add_constraint(pilot_db)
    proposal = _run_opt_in(pilot_db)["proposal"]
    delivery_calls = 0
    delivery = {
        "status": "disabled",
        "target": None,
        "reason": "delivery_disabled",
        "items": [],
    }

    def trigger_delivery(*args, **kwargs):
        nonlocal delivery_calls
        delivery_calls += 1
        return delivery

    monkeypatch.setattr(
        "api.context_pilot._trigger_managed_delivery",
        trigger_delivery,
    )

    accepted = respond_to_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=proposal["id"],
        response="accept",
        idempotency_key="pilot-accept-delivery-replay",
        now=NOW + timedelta(minutes=1),
    )
    replay = respond_to_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=proposal["id"],
        response="accept",
        idempotency_key="pilot-accept-delivery-replay",
        now=NOW + timedelta(minutes=2),
    )

    assert replay == accepted
    assert replay["delivery"] == delivery
    assert delivery_calls == 1
    consequence = pilot_db.query(PlanRevision).filter(
        PlanRevision.operation == "context_pilot_accept_delivery"
    ).one()
    assert consequence.details["delivery"] == delivery


@pytest.mark.parametrize("response", ["reject", "defer"])
def test_rejection_and_deferral_leave_the_plan_unchanged(
    pilot_db: Session,
    response: str,
) -> None:
    workout = _add_workout(pilot_db)
    _add_constraint(pilot_db)
    result = _run_opt_in(pilot_db)

    lifecycle = respond_to_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        response=response,
        idempotency_key=f"pilot-response-{response}",
        now=NOW + timedelta(minutes=1),
    )

    pilot_db.refresh(workout)
    assert lifecycle["status"] == (
        "rejected" if response == "reject" else "deferred"
    )
    assert lifecycle["revision_id"] is None
    assert workout.planned_duration_min == 60
    assert not pilot_db.query(PlanRevision).filter(
        PlanRevision.operation == "context_pilot_accept"
    ).all()


def test_context_deletion_invalidates_a_pending_proposal(
    pilot_db: Session,
) -> None:
    workout = _add_workout(pilot_db)
    context_id = _add_constraint(pilot_db)
    result = _run_opt_in(pilot_db)

    assert withdraw_context(
        pilot_db,
        user_id=USER_ID,
        item_id=context_id,
        expected_version=1,
        now=NOW + timedelta(minutes=1),
    )
    proposal = get_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        now=NOW + timedelta(minutes=2),
    )
    assert proposal["status"] == "invalidated"
    assert proposal["action"] is None
    assert proposal["after"] is None
    stored = pilot_db.get(PlanRevision, result["proposal"]["id"])
    assert stored is not None
    assert stored.after_snapshot == []
    assert "action" not in stored.details
    assert "reason_code" not in stored.details
    with pytest.raises(ContextPilotConflict):
        respond_to_context_pilot_proposal(
            pilot_db,
            user_id=USER_ID,
            proposal_id=result["proposal"]["id"],
            response="accept",
            idempotency_key="pilot-accept-after-delete",
            now=NOW + timedelta(minutes=2),
        )
    pilot_db.refresh(workout)
    assert workout.planned_duration_min == 60


def test_expired_workout_proposal_cannot_mutate_history(
    pilot_db: Session,
) -> None:
    workout = _add_workout(pilot_db)
    _add_constraint(pilot_db)
    result = _run_opt_in(pilot_db)

    proposal = get_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        now=NOW + timedelta(days=6),
    )
    assert proposal["status"] == "expired"
    with pytest.raises(ContextPilotConflict):
        respond_to_context_pilot_proposal(
            pilot_db,
            user_id=USER_ID,
            proposal_id=result["proposal"]["id"],
            response="accept",
            idempotency_key="pilot-expired-workout-accept",
            now=NOW + timedelta(days=6),
        )
    pilot_db.refresh(workout)
    assert workout.planned_duration_min == 60


def test_explicit_proposal_expiry_precedes_context_invalidation(
    pilot_db: Session,
) -> None:
    _add_workout(pilot_db)
    _add_constraint(
        pilot_db,
        expires_at=NOW + timedelta(days=1),
    )
    result = _run_opt_in(pilot_db)

    proposal = get_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=result["proposal"]["id"],
        now=NOW + timedelta(days=1, minutes=1),
    )

    assert proposal["status"] == "expired"


def test_unassociated_availability_fields_do_not_create_a_suggestion(
    pilot_db: Session,
) -> None:
    _add_workout(pilot_db)
    _add_constraint(
        pilot_db,
        fields={"affected_dates": [WORKOUT_DATE.isoformat()]},
    )
    _add_constraint(
        pilot_db,
        fields={"maximum_available_minutes": 30},
    )

    result = _run_opt_in(pilot_db)

    assert result["outcome"] == "insufficient_evidence"
    assert (
        result["reason_code"]
        == "availability_window_and_limit_not_associated"
    )
    assert result["proposal"] is None


def test_out_of_scope_context_is_rejected_before_use_receipt_creation(
    pilot_db: Session,
    monkeypatch,
) -> None:
    _add_durable_preference(pilot_db)
    processing_called = False

    def unexpected_processing(*args, **kwargs):
        nonlocal processing_called
        processing_called = True
        raise AssertionError("out-of-scope context reached processing")

    monkeypatch.setattr(
        "api.context_pilot.process_personal_context",
        unexpected_processing,
    )

    with pytest.raises(ContextPilotValidationError):
        run_context_pilot(
            pilot_db,
            user_id=USER_ID,
            source="opt_in",
            purpose="plan_adjustment",
            confirmed_opt_in=True,
            allow_ai=True,
            idempotency_key="pilot-disallowed-kind",
            now=NOW,
        )

    assert processing_called is False
    assert pilot_db.query(PersonalContextUseReceipt).count() == 0
    assert pilot_db.query(PlanRevision).filter(
        PlanRevision.idempotency_key == "pilot-disallowed-kind"
    ).one_or_none() is None


def test_idempotency_key_rejects_a_changed_pilot_command(
    pilot_db: Session,
) -> None:
    first = run_context_pilot(
        pilot_db,
        user_id=USER_ID,
        source="synthetic",
        scenario_id="missed-no-change",
        idempotency_key="pilot-command-fingerprint",
        now=NOW,
    )
    replay = run_context_pilot(
        pilot_db,
        user_id=USER_ID,
        source="synthetic",
        scenario_id="missed-no-change",
        idempotency_key="pilot-command-fingerprint",
        now=NOW,
    )
    assert replay == first

    with pytest.raises(ContextPilotConflict):
        run_context_pilot(
            pilot_db,
            user_id=USER_ID,
            source="synthetic",
            scenario_id="safety-boundary",
            idempotency_key="pilot-command-fingerprint",
            now=NOW,
        )


def test_concurrent_identical_runs_process_context_once(
    pilot_db: Session,
    monkeypatch,
) -> None:
    _add_workout(pilot_db)
    _add_constraint(pilot_db)
    session_factory = sessionmaker(bind=pilot_db.get_bind())
    first_processing = Event()
    release_first = Event()
    duplicate_processing = Event()
    call_lock = Lock()
    call_count = 0
    from api import context_pilot

    original_process = context_pilot.process_personal_context

    def blocking_process(*args, **kwargs):
        nonlocal call_count
        with call_lock:
            call_count += 1
            current_call = call_count
        if current_call == 1:
            first_processing.set()
            assert release_first.wait(5)
        else:
            duplicate_processing.set()
        return original_process(*args, **kwargs)

    monkeypatch.setattr(
        "api.context_pilot.process_personal_context",
        blocking_process,
    )

    def submit() -> dict[str, Any]:
        with session_factory() as db:
            return run_context_pilot(
                db,
                user_id=USER_ID,
                source="opt_in",
                purpose="plan_adjustment",
                confirmed_opt_in=True,
                idempotency_key="pilot-concurrent-run",
                now=NOW,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(submit)
        assert first_processing.wait(5)
        second = executor.submit(submit)
        assert duplicate_processing.wait(0.5) is False
        release_first.set()
        results = [first.result(timeout=10), second.result(timeout=10)]

    assert results[0] == results[1]
    assert call_count == 1
    assert pilot_db.query(PersonalContextUseReceipt).count() == 1
    assert pilot_db.query(PlanRevision).filter(
        PlanRevision.idempotency_key == "pilot-concurrent-run"
    ).count() == 1


def test_unexpected_processing_failure_releases_run_reservation(
    pilot_db: Session,
    monkeypatch,
) -> None:
    _add_workout(pilot_db)
    _add_constraint(pilot_db)
    from api import context_pilot

    original_process = context_pilot.process_personal_context
    monkeypatch.setattr(
        "api.context_pilot.process_personal_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic processing failure")
        ),
    )

    with pytest.raises(RuntimeError):
        run_context_pilot(
            pilot_db,
            user_id=USER_ID,
            source="opt_in",
            purpose="plan_adjustment",
            confirmed_opt_in=True,
            idempotency_key="pilot-recoverable-failure",
            now=NOW,
        )

    assert pilot_db.query(PlanRevision).filter(
        PlanRevision.idempotency_key == "pilot-recoverable-failure"
    ).one_or_none() is None

    monkeypatch.setattr(
        "api.context_pilot.process_personal_context",
        original_process,
    )
    retry = run_context_pilot(
        pilot_db,
        user_id=USER_ID,
        source="opt_in",
        purpose="plan_adjustment",
        confirmed_opt_in=True,
        idempotency_key="pilot-recoverable-failure",
        now=NOW,
    )

    assert retry["outcome"] == "suggestion"


def test_processing_failure_is_insufficient_evidence_without_private_output(
    pilot_db: Session,
    monkeypatch,
) -> None:
    _add_workout(pilot_db)
    _add_constraint(pilot_db)
    call_count = 0

    def fail_processing(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise PersonalContextAccessError("PRIVATE-PILOT-MARKER")

    monkeypatch.setattr(
        "api.context_pilot.process_personal_context",
        fail_processing,
    )

    result = run_context_pilot(
        pilot_db,
        user_id=USER_ID,
        source="opt_in",
        purpose="plan_adjustment",
        confirmed_opt_in=True,
        idempotency_key="pilot-processing-failure",
        now=NOW,
    )
    replay = run_context_pilot(
        pilot_db,
        user_id=USER_ID,
        source="opt_in",
        purpose="plan_adjustment",
        confirmed_opt_in=True,
        idempotency_key="pilot-processing-failure",
        now=NOW,
    )

    assert result["outcome"] == "insufficient_evidence"
    assert result["processing_status"] == "failed"
    assert result["reason_code"] == "context_processing_unavailable"
    assert replay == result
    assert call_count == 1
    assert "PRIVATE-PILOT-MARKER" not in json.dumps(result)
    failure = pilot_db.query(PlanRevision).filter(
        PlanRevision.operation == "context_pilot_failure"
    ).one()
    assert "PRIVATE-PILOT-MARKER" not in json.dumps(failure.details)


def test_evaluation_is_aggregate_only_and_marks_unsupported_checks(
    pilot_db: Session,
) -> None:
    _add_workout(pilot_db)
    context_id = _add_constraint(pilot_db)
    suggestion = _run_opt_in(pilot_db)
    respond_to_context_pilot_proposal(
        pilot_db,
        user_id=USER_ID,
        proposal_id=suggestion["proposal"]["id"],
        response="reject",
        idempotency_key="pilot-evaluation-reject",
        now=NOW + timedelta(minutes=1),
    )
    assert withdraw_context(
        pilot_db,
        user_id=USER_ID,
        item_id=context_id,
        expected_version=1,
        now=NOW + timedelta(minutes=2),
    )
    run_context_pilot(
        pilot_db,
        user_id=OTHER_USER_ID,
        source="synthetic",
        scenario_id="safety-boundary",
        idempotency_key="pilot-evaluation-safety",
        now=NOW,
    )

    report = build_context_pilot_evaluation(pilot_db, now=NOW)
    serialized = json.dumps(report)

    assert report["policy_version"] == PILOT_POLICY_VERSION
    assert report["operational_counts"]["runs"] == 2
    assert report["proposal_responses"]["rejected"] == 1
    assert report["checks"]["subgroup"]["state"] == "not_measured"
    assert report["checks"]["adverse_outcomes"]["state"] == "not_measured"
    assert report["checks"]["drift"]["unexpected_policy_versions"] == 0
    assert report["falsification"]["automatic_mutation"]["observed"] == 0
    assert report["operational_counts"]["deletions"] == {
        "completed_proposal_privacy_scrubs": 1,
        "failure_state": "not_measured",
        "failure_reason_code":
            "privacy_preserving_failure_link_unavailable",
    }
    assert "context_item_ids" not in serialized
    assert "user_id" not in serialized
    assert "narrative" not in serialized
    assert "Synthetic private detail" not in serialized
