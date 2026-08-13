"""Owner-scoped orchestration for deterministic outdoor-road 5K proposals."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
import hashlib
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import effective_athlete_date, load_config_from_db
from analysis.data_loader import load_plan_generation_data
from analysis.goal_baseline import build_goal_baseline_goal
from analysis.outdoor_5k_plan_generation import (
    OUTDOOR_5K_GENERATOR_VERSION,
    OUTDOOR_5K_EVIDENCE_CLAIM_IDS,
    OUTDOOR_5K_EVIDENCE_REVIEW_IDS,
    OUTDOOR_5K_POLICY_VERSION,
    OUTDOOR_5K_SCIENCE_DECISION_ID,
    GeneratedOutdoor5KPlan,
    GeneratedWorkout,
    Outdoor5KGenerationInput,
    Outdoor5KGenerationResult,
    Outdoor5KGoal,
    PlanGenerationConstraints,
    RunningHistoryObservation,
    generate_outdoor_5k_plan,
    serialize_generation_result,
    serialize_workout_structure,
)
from api.adaptive_plan_service import (
    AdaptivePlanError,
    ProposalInput,
    create_draft_proposal,
    create_successor_proposal,
    read_proposal,
)
from api.goal_baseline import build_goal_baseline_view
from db.models import GoalBaselineSnapshot, Outdoor5KPlanGeneration, PlanProposal


class Outdoor5KGenerationError(RuntimeError):
    """Structured, safe-to-expose 5K generation service error."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = {"code": code, "message": message, **details}


def build_outdoor_5k_readiness(
    db: Session,
    *,
    user_id: str,
    constraints: PlanGenerationConstraints,
    outdoor_road_goal_confirmed: bool,
) -> dict[str, Any]:
    """Return the typed readiness envelope without persisting a proposal."""
    generation_input, result = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        outdoor_road_goal_confirmed=outdoor_road_goal_confirmed,
    )
    return _readiness_envelope(generation_input, result)


def build_outdoor_5k_alternatives(
    db: Session,
    *,
    user_id: str,
    constraints: PlanGenerationConstraints,
    outdoor_road_goal_confirmed: bool,
) -> dict[str, Any]:
    """Return bounded alternatives for the exact current readiness result."""
    generation_input, result = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        outdoor_road_goal_confirmed=outdoor_road_goal_confirmed,
    )
    return {
        **_readiness_envelope(generation_input, result),
        "alternatives": list(result.alternatives),
    }


def generate_outdoor_5k_proposal(
    db: Session,
    *,
    user_id: str,
    constraints: PlanGenerationConstraints,
    outdoor_road_goal_confirmed: bool,
    expected_source_revision: str,
    idempotency_key: str,
) -> tuple[dict[str, Any], bool]:
    """Persist one valid immutable proposal or return a typed no-plan result."""
    generation_input, result = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        outdoor_road_goal_confirmed=outdoor_road_goal_confirmed,
    )
    _require_source_revision(
        expected_source_revision=expected_source_revision,
        actual_source_revision=result.deterministic_input_hash,
    )
    request_fingerprint = _request_fingerprint(
        request_kind="generate",
        source_revision=result.deterministic_input_hash,
    )
    replay = _idempotency_replay(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay, True
    if result.code != "ready" or result.plan is None:
        return _readiness_envelope(generation_input, result), False

    proposal_input = _proposal_input(
        generation_input=generation_input,
        result=result,
        idempotency_key=idempotency_key,
    )
    proposal = create_draft_proposal(
        db,
        user_id=user_id,
        payload=proposal_input,
        current_date=generation_input.athlete_today,
        on_created=lambda session, created: _record_generation(
            session,
            user_id=user_id,
            proposal=created,
            generation_input=generation_input,
            result=result,
            request_kind="generate",
            request_fingerprint=request_fingerprint,
            predecessor=None,
        ),
    )
    return _proposal_envelope(
        generation_input,
        result,
        proposal=proposal,
        replayed=False,
    ), False


def regenerate_outdoor_5k_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    expected_proposal_version: int,
    constraints: PlanGenerationConstraints,
    outdoor_road_goal_confirmed: bool,
    expected_source_revision: str,
    idempotency_key: str,
) -> tuple[dict[str, Any], bool]:
    """Create one bounded immutable successor after an exact source revision."""
    parent = db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.id == proposal_id,
        )
    ).scalar_one_or_none()
    if parent is None:
        raise Outdoor5KGenerationError(
            404,
            "OUTDOOR_5K_PROPOSAL_NOT_FOUND",
            "The outdoor 5K proposal was not found.",
        )
    if parent.policy_version != OUTDOOR_5K_POLICY_VERSION:
        raise Outdoor5KGenerationError(
            409,
            "OUTDOOR_5K_PROPOSAL_POLICY_MISMATCH",
            "Only a deterministic outdoor 5K proposal can be regenerated here.",
        )
    if parent.version != expected_proposal_version:
        raise Outdoor5KGenerationError(
            409,
            "OUTDOOR_5K_PROPOSAL_STALE",
            "The proposal version is stale.",
            current_version=parent.version,
        )

    generation_input, result = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        outdoor_road_goal_confirmed=outdoor_road_goal_confirmed,
    )
    _require_source_revision(
        expected_source_revision=expected_source_revision,
        actual_source_revision=result.deterministic_input_hash,
    )
    request_fingerprint = _request_fingerprint(
        request_kind="regenerate",
        source_revision=result.deterministic_input_hash,
        predecessor=(parent.id, parent.version),
    )
    replay = _idempotency_replay(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay, True
    parent_audit = _generation_for_proposal(db, user_id=user_id, proposal_id=parent.id)
    if (
        parent_audit is not None
        and parent_audit.source_revision == result.deterministic_input_hash
    ):
        raise Outdoor5KGenerationError(
            409,
            "OUTDOOR_5K_REGENERATION_INPUT_UNCHANGED",
            "Regeneration requires a changed versioned input.",
        )
    if result.code != "ready" or result.plan is None:
        return _readiness_envelope(generation_input, result), False

    proposal_input = _proposal_input(
        generation_input=generation_input,
        result=result,
        idempotency_key=idempotency_key,
    )
    proposal = create_successor_proposal(
        db,
        user_id=user_id,
        proposal_id=proposal_id,
        expected_version=expected_proposal_version,
        payload=proposal_input,
        current_date=generation_input.athlete_today,
        allow_policy_successor=True,
        on_created=lambda session, created: _record_generation(
            session,
            user_id=user_id,
            proposal=created,
            generation_input=generation_input,
            result=result,
            request_kind="regenerate",
            request_fingerprint=request_fingerprint,
            predecessor=(parent.id, parent.version),
        ),
    )
    return _proposal_envelope(
        generation_input,
        result,
        proposal=proposal,
        replayed=False,
    ), False


def validate_outdoor_5k_proposal_adoption(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
) -> None:
    """Revalidate a generated proposal through the #665 baseline boundary."""
    audit = _generation_for_proposal(db, user_id=user_id, proposal_id=proposal.id)
    if audit is None:
        raise AdaptivePlanError(
            409,
            "OUTDOOR_5K_PROPOSAL_AUDIT_MISSING",
            "The deterministic outdoor 5K proposal has no audit record.",
        )
    snapshot = audit.constraint_snapshot or {}
    constraints = _constraints_from_snapshot(snapshot)
    outdoor_road_goal_confirmed = bool(
        snapshot.get("outdoor_road_goal_confirmed")
    )
    generation_input, result = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        outdoor_road_goal_confirmed=outdoor_road_goal_confirmed,
    )
    if (
        result.code != "ready"
        or result.deterministic_input_hash != audit.source_revision
        or result.deterministic_input_hash != audit.deterministic_input_hash
    ):
        raise AdaptivePlanError(
            409,
            "OUTDOOR_5K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal no longer meets the deterministic outdoor 5K policy.",
            result_code=result.code,
            current_source_revision=result.deterministic_input_hash,
        )
    if generation_input.policy_version != proposal.policy_version:
        raise AdaptivePlanError(
            409,
            "OUTDOOR_5K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal policy version no longer matches its deterministic input.",
            result_code="unsupported_goal_or_population",
        )
    if result.plan is None or not _proposal_matches_generated_plan(
        proposal,
        plan=result.plan,
        input_hash=result.deterministic_input_hash,
    ):
        raise AdaptivePlanError(
            409,
            "OUTDOOR_5K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal workout snapshot no longer matches deterministic output.",
            result_code="validation_failed",
        )


def _evaluate(
    db: Session,
    *,
    user_id: str,
    constraints: PlanGenerationConstraints,
    outdoor_road_goal_confirmed: bool,
) -> tuple[Outdoor5KGenerationInput, Outdoor5KGenerationResult]:
    config = load_config_from_db(user_id, db)
    athlete_today = effective_athlete_date(config)
    block_start = athlete_today + timedelta(days=1)
    baseline_view = build_goal_baseline_view(db, user_id=user_id)
    baseline = baseline_view["baseline"]
    goal_contract = build_goal_baseline_goal(config.goal)
    generation_data = load_plan_generation_data(
        user_id,
        db,
        athlete_today=athlete_today,
        block_start=block_start,
        activity_source=config.preferences.get("activities"),
        purpose="plan_generation",
    )
    generation_input = Outdoor5KGenerationInput(
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        athlete_today=athlete_today,
        block_start=block_start,
        goal=Outdoor5KGoal(
            goal_kind=goal_contract.goal_kind,
            distance=goal_contract.distance,
            outdoor_road_confirmed=outdoor_road_goal_confirmed,
            target_time_sec=goal_contract.target_time_sec,
            target_event_date=_goal_event_date(config.goal.get("race_date")),
        ),
        baseline_current=baseline.get("status") == "current",
        baseline_snapshot_id=_current_baseline_snapshot_id(
            db,
            user_id=user_id,
            goal_signature=goal_contract.goal_signature,
            activity_id=(baseline.get("evidence") or {}).get("activity_id"),
        ),
        baseline_evidence_date=_goal_evidence_date(
            (baseline.get("evidence") or {}).get("observed_date")
        ),
        history=tuple(
            RunningHistoryObservation(
                activity_id=item.activity_id,
                observed_date=item.observed_date,
                duration_min=item.duration_min,
                source=item.source,
            )
            for item in generation_data.activities
        ),
        reserved_dates=generation_data.reserved_dates,
        constraints=constraints,
    )
    return generation_input, generate_outdoor_5k_plan(generation_input)


def _proposal_input(
    *,
    generation_input: Outdoor5KGenerationInput,
    result: Outdoor5KGenerationResult,
    idempotency_key: str,
) -> ProposalInput:
    if result.plan is None:
        raise ValueError("a ready result is required to persist a proposal")
    return ProposalInput(
        goal={
            "goal_kind": "performance_5k",
            "target": {
                "distance": "5k",
                "criterion": "elapsed_time_seconds",
                "setting": "outdoor_road",
                "target_time_sec": generation_input.goal.target_time_sec,
                "target_event_date": (
                    generation_input.goal.target_event_date.isoformat()
                    if generation_input.goal.target_event_date
                    else None
                ),
            },
            "horizon_start": result.plan.horizon_start.isoformat(),
            "horizon_end": result.plan.horizon_end.isoformat(),
        },
        discipline="running",
        workouts=_proposal_workouts(result.plan, result.deterministic_input_hash),
        origin="api.plan.outdoor-5k.deterministic",
        actor_type="system",
        actor_id=None,
        idempotency_key=idempotency_key,
        policy_version=OUTDOOR_5K_POLICY_VERSION,
        model_version=OUTDOOR_5K_GENERATOR_VERSION,
        science_version="sdr-outdoor-5k-plan-generation-policy-v1",
        assumptions=(),
        unknowns=(
            "Goal feasibility remains unknown; the block does not promise a target outcome.",
        ),
        warnings=(
            "The 28-day horizon, templates, and schedule limits are Praxys pilot guardrails.",
        ),
        alternatives=result.alternatives,
    )


def _proposal_workouts(
    plan: GeneratedOutdoor5KPlan,
    input_hash: str,
) -> list[dict[str, Any]]:
    workouts: list[dict[str, Any]] = []
    for week in plan.weeks:
        for workout in week.workouts:
            workouts.append(
                {
                    "canonical_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            ":".join(
                                (
                                    OUTDOOR_5K_GENERATOR_VERSION,
                                    input_hash,
                                    workout.template_id,
                                    workout.scheduled_date.isoformat(),
                                )
                            ),
                        )
                    ),
                    "date": workout.scheduled_date.isoformat(),
                    "activity_type": "running",
                    "workout_type": workout.workout_type,
                    "planned_duration_min": workout.planned_duration_min,
                    "workout_description": _workout_description(workout),
                    "workout_structure_version": "v1",
                    "workout_structure": serialize_workout_structure(workout),
                }
            )
    return workouts


def _workout_description(workout: GeneratedWorkout) -> str:
    labels = {
        "easy": "Easy running",
        "longest_easy": "Longest easy run",
        "controlled_quality": "Controlled quality session",
        "short_interval_quality": "Short interval quality session",
    }
    return (
        f"{labels[workout.workout_type]}. "
        "Deterministic outdoor 5K pilot guardrail; do not add catch-up work."
    )


def _record_generation(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
    generation_input: Outdoor5KGenerationInput,
    result: Outdoor5KGenerationResult,
    request_kind: str,
    request_fingerprint: str,
    predecessor: tuple[str, int] | None,
) -> None:
    observed_snapshot = {
        "goal": {
            "goal_kind": generation_input.goal.goal_kind,
            "distance": generation_input.goal.distance,
            "target_time_sec": generation_input.goal.target_time_sec,
            "target_event_date": (
                generation_input.goal.target_event_date.isoformat()
                if generation_input.goal.target_event_date
                else None
            ),
        },
        "baseline": {
            "current": generation_input.baseline_current,
            "snapshot_id": generation_input.baseline_snapshot_id,
            "evidence_date": (
                generation_input.baseline_evidence_date.isoformat()
                if generation_input.baseline_evidence_date
                else None
            ),
        },
        "completed_running_history": [
            {
                "activity_id": item.activity_id,
                "observed_date": item.observed_date.isoformat(),
                "duration_min": item.duration_min,
                "source": item.source,
            }
            for item in generation_input.history
        ],
        "reserved_dates": [
            item.isoformat() for item in generation_input.reserved_dates
        ],
    }
    result_snapshot = serialize_generation_result(result)
    result_snapshot.pop("plan", None)
    db.add(
        Outdoor5KPlanGeneration(
            user_id=user_id,
            proposal_id=proposal.id,
            policy_version=result.policy_version,
            generator_version=result.generator_version,
            science_decision_id=result.science_decision_id,
            evidence_review_ids=list(OUTDOOR_5K_EVIDENCE_REVIEW_IDS),
            evidence_claim_ids=list(OUTDOOR_5K_EVIDENCE_CLAIM_IDS),
            ai_explanation_present=False,
            baseline_snapshot_id=generation_input.baseline_snapshot_id,
            source_revision=result.deterministic_input_hash,
            deterministic_input_hash=result.deterministic_input_hash,
            request_kind=request_kind,
            request_fingerprint=request_fingerprint,
            predecessor_proposal_id=predecessor[0] if predecessor else None,
            predecessor_version=predecessor[1] if predecessor else None,
            observed_input_snapshot=observed_snapshot,
            constraint_snapshot=_constraints_snapshot(
                generation_input.constraints,
                outdoor_road_goal_confirmed=generation_input.goal.outdoor_road_confirmed,
            ),
            derived_history_statistics=_json_safe(asdict(result.history_statistics)),
            validation_results=result_snapshot,
        )
    )


def _idempotency_replay(
    db: Session,
    *,
    user_id: str,
    idempotency_key: str,
    request_fingerprint: str,
) -> dict[str, Any] | None:
    existing = db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is None:
        return None
    audit = _generation_for_proposal(db, user_id=user_id, proposal_id=existing.id)
    if audit is None or audit.request_fingerprint != request_fingerprint:
        raise Outdoor5KGenerationError(
            409,
            "OUTDOOR_5K_IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used for a different proposal request.",
        )
    proposal = read_proposal(db, user_id=user_id, proposal_id=existing.id)
    if proposal is None:
        raise Outdoor5KGenerationError(
            409,
            "OUTDOOR_5K_IDEMPOTENCY_CONFLICT",
            "This idempotency key belongs to a proposal that is no longer readable.",
        )
    return {
        "schema_version": 1,
        "policy_version": audit.policy_version,
        "generator_version": audit.generator_version,
        "science_decision_id": audit.science_decision_id,
        "source_revision": audit.source_revision,
        "result": audit.validation_results,
        "proposal": proposal,
        "replayed": True,
    }


def _proposal_envelope(
    generation_input: Outdoor5KGenerationInput,
    result: Outdoor5KGenerationResult,
    *,
    proposal: dict[str, Any],
    replayed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_version": result.policy_version,
        "generator_version": result.generator_version,
        "science_decision_id": result.science_decision_id,
        "source_revision": result.deterministic_input_hash,
        "result": _result_without_plan(result),
        "proposal": proposal,
        "replayed": replayed,
        "reassessment_dates": [
            item.isoformat()
            for item in (result.plan.reassessment_dates if result.plan else ())
        ],
    }


def _readiness_envelope(
    generation_input: Outdoor5KGenerationInput,
    result: Outdoor5KGenerationResult,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_version": result.policy_version,
        "generator_version": result.generator_version,
        "science_decision_id": result.science_decision_id,
        "source_revision": result.deterministic_input_hash,
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "result": _result_without_plan(result),
    }


def _result_without_plan(result: Outdoor5KGenerationResult) -> dict[str, Any]:
    payload = serialize_generation_result(result)
    payload.pop("plan", None)
    return payload


def _request_fingerprint(
    *,
    request_kind: str,
    source_revision: str,
    predecessor: tuple[str, int] | None = None,
) -> str:
    """Hash one exact generation command without retaining private payloads twice."""
    payload = {
        "request_kind": request_kind,
        "source_revision": source_revision,
        "predecessor": (
            {"proposal_id": predecessor[0], "version": predecessor[1]}
            if predecessor is not None
            else None
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _proposal_matches_generated_plan(
    proposal: PlanProposal,
    *,
    plan: GeneratedOutdoor5KPlan,
    input_hash: str,
) -> bool:
    """Compare the immutable proposal snapshot with exact deterministic output."""
    fields = (
        "canonical_id",
        "date",
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
    )

    def projection(snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {field: item.get(field) for field in fields}
            for item in sorted(snapshot, key=lambda item: str(item.get("date", "")))
        ]

    expected = projection(_proposal_workouts(plan, input_hash))
    actual = projection(list(proposal.workout_snapshot or []))
    return _json_safe(expected) == _json_safe(actual)


def _require_source_revision(
    *,
    expected_source_revision: str,
    actual_source_revision: str,
) -> None:
    if expected_source_revision != actual_source_revision:
        raise Outdoor5KGenerationError(
            409,
            "OUTDOOR_5K_SOURCE_REVISION_STALE",
            "The readiness source revision changed; fetch readiness again before generating.",
            current_source_revision=actual_source_revision,
        )


def _generation_for_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
) -> Outdoor5KPlanGeneration | None:
    return db.execute(
        select(Outdoor5KPlanGeneration).where(
            Outdoor5KPlanGeneration.user_id == user_id,
            Outdoor5KPlanGeneration.proposal_id == proposal_id,
        )
    ).scalar_one_or_none()


def _current_baseline_snapshot_id(
    db: Session,
    *,
    user_id: str,
    goal_signature: str,
    activity_id: str | None,
) -> str | None:
    query = select(GoalBaselineSnapshot).where(
        GoalBaselineSnapshot.user_id == user_id,
        GoalBaselineSnapshot.goal_signature == goal_signature,
        GoalBaselineSnapshot.qualification_status == "direct_current",
    )
    if activity_id:
        exact = db.execute(
            query.where(GoalBaselineSnapshot.source_id == str(activity_id))
            .order_by(
                GoalBaselineSnapshot.created_at.desc(),
                GoalBaselineSnapshot.version.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if exact is not None:
            return exact.id
    latest = db.execute(
        query.order_by(
            GoalBaselineSnapshot.created_at.desc(),
            GoalBaselineSnapshot.version.desc(),
        ).limit(1)
    ).scalar_one_or_none()
    return latest.id if latest is not None else None


def _goal_event_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _goal_evidence_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _constraints_snapshot(
    constraints: PlanGenerationConstraints,
    *,
    outdoor_road_goal_confirmed: bool,
) -> dict[str, Any]:
    return {
        "age_18_or_older": constraints.age_18_or_older,
        "self_coached_recreational_road_runner": (
            constraints.self_coached_recreational_road_runner
        ),
        "can_complete_5k": constraints.can_complete_5k,
        "safety_stop": constraints.safety_stop,
        "available_weekdays": list(constraints.available_weekdays),
        "maximum_session_duration_min": constraints.maximum_session_duration_min,
        "unavailable_dates": [
            item.isoformat() for item in constraints.unavailable_dates
        ],
        "preferred_longest_run_weekday": constraints.preferred_longest_run_weekday,
        "outdoor_road_goal_confirmed": outdoor_road_goal_confirmed,
    }


def _constraints_from_snapshot(
    snapshot: dict[str, Any],
) -> PlanGenerationConstraints:
    try:
        return PlanGenerationConstraints(
            age_18_or_older=bool(snapshot["age_18_or_older"]),
            self_coached_recreational_road_runner=bool(
                snapshot["self_coached_recreational_road_runner"]
            ),
            can_complete_5k=bool(snapshot["can_complete_5k"]),
            safety_stop=bool(snapshot["safety_stop"]),
            available_weekdays=tuple(
                int(item) for item in snapshot["available_weekdays"]
            ),
            maximum_session_duration_min=int(
                snapshot["maximum_session_duration_min"]
            ),
            unavailable_dates=tuple(
                date.fromisoformat(str(item))
                for item in snapshot["unavailable_dates"]
            ),
            preferred_longest_run_weekday=(
                int(snapshot["preferred_longest_run_weekday"])
                if snapshot.get("preferred_longest_run_weekday") is not None
                else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AdaptivePlanError(
            409,
            "OUTDOOR_5K_PROPOSAL_AUDIT_INVALID",
            "The stored deterministic constraints cannot be revalidated.",
        ) from exc


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=lambda item: item.isoformat()))
