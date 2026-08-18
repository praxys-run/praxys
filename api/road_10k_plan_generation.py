"""Owner-scoped orchestration for deterministic road 10K proposals."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, timedelta
import hashlib
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.config import effective_athlete_date, load_config_from_db
from analysis.data_loader import load_road_10k_plan_generation_data
from analysis.road_10k_baseline import build_road_10k_goal
from analysis.road_10k_contract import (
    ROAD_10K_CONTRACT_DIGEST,
    ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
    ROAD_10K_EXECUTION,
    ROAD_10K_GENERATOR_VERSION,
    ROAD_10K_POLICY_VERSION,
    ROAD_10K_REQUIRED_INPUTS,
    ROAD_10K_SCIENCE_DECISION_ID,
    ROAD_10K_SOURCE_DECISION_DIGEST,
    ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION,
)
from analysis.road_10k_plan_generation import (
    GeneratedRoad10KPlan,
    GeneratedWorkout,
    Road10KGenerationInput,
    Road10KGenerationResult,
    Road10KGoal,
    Road10KPlanGenerationConstraints,
    RunningHistoryObservation,
    build_event_context,
    generate_road_10k_plan,
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
from api.plan_generation_capabilities import (
    OUTDOOR_ROAD_10K_CAPABILITY,
    PlanPurposeError,
    ResolvedPlanGenerationPurpose,
    resolve_plan_generation_purpose,
)
from api.road_10k_baseline import (
    build_road_10k_baseline_view,
    resolve_road_10k_baseline_snapshot_id,
)
from db.models import AdaptivePlanGoalSnapshot, PlanProposal, Road10KPlanGeneration


class Road10KGenerationError(RuntimeError):
    """Structured, safe-to-expose road 10K generation service error."""

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


def build_road_10k_readiness(
    db: Session,
    *,
    user_id: str,
    constraints: Road10KPlanGenerationConstraints,
    purpose_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the typed road 10K readiness envelope without persisting."""
    generation_input, result, purpose, baseline = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    return _readiness_envelope(
        generation_input,
        result,
        purpose=purpose,
        baseline=baseline,
    )


def build_road_10k_alternatives(
    db: Session,
    *,
    user_id: str,
    constraints: Road10KPlanGenerationConstraints,
    purpose_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bounded alternatives for the exact current road 10K readiness."""
    generation_input, result, purpose, baseline = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    return {
        **_readiness_envelope(
            generation_input,
            result,
            purpose=purpose,
            baseline=baseline,
        ),
        "alternatives": list(result.alternatives),
    }


def generate_road_10k_proposal(
    db: Session,
    *,
    user_id: str,
    constraints: Road10KPlanGenerationConstraints,
    expected_source_revision: str,
    idempotency_key: str,
    purpose_selection: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Persist one valid immutable proposal or return a typed no-plan result."""
    request_fingerprint = _request_fingerprint(
        request_kind="generate",
        expected_source_revision=expected_source_revision,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    replay = _idempotency_replay(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay, True

    generation_input, result, purpose, baseline = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    _require_source_revision(
        expected_source_revision=expected_source_revision,
        actual_source_revision=result.deterministic_input_hash,
    )
    if not result.code.startswith("eligible_") or result.plan is None:
        return _readiness_envelope(
            generation_input,
            result,
            purpose=purpose,
            baseline=baseline,
        ), False

    proposal_input = _proposal_input(
        generation_input=generation_input,
        result=result,
        purpose=purpose,
        idempotency_key=idempotency_key,
    )
    idempotency_replay_state = {"replayed": False}
    proposal = create_draft_proposal(
        db,
        user_id=user_id,
        payload=proposal_input,
        current_date=generation_input.athlete_today,
        before_persist=lambda session: _require_locked_source_revision(
            session,
            user_id=user_id,
            constraints=constraints,
            purpose_selection=purpose.selection_payload(),
            expected_source_revision=expected_source_revision,
        ),
        idempotency_replay_state=idempotency_replay_state,
        validated_policy_purpose=True,
        on_created=lambda session, created: _record_generation(
            session,
            user_id=user_id,
            proposal=created,
            generation_input=generation_input,
            result=result,
            purpose=purpose,
            request_kind="generate",
            request_fingerprint=request_fingerprint,
            predecessor=None,
        ),
    )
    if idempotency_replay_state["replayed"]:
        replay = _idempotency_replay(
            db,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if replay is not None:
            return replay, True
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used for a different proposal request.",
        )
    return _proposal_envelope(
        generation_input,
        result,
        purpose=purpose,
        proposal=proposal,
        replayed=False,
    ), False


def regenerate_road_10k_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
    expected_proposal_version: int,
    constraints: Road10KPlanGenerationConstraints,
    expected_source_revision: str,
    idempotency_key: str,
    purpose_selection: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Create one bounded immutable successor after an exact source revision."""
    request_fingerprint = _request_fingerprint(
        request_kind="regenerate",
        expected_source_revision=expected_source_revision,
        constraints=constraints,
        purpose_selection=purpose_selection,
        predecessor=(proposal_id, expected_proposal_version),
    )
    replay = _idempotency_replay(
        db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )
    if replay is not None:
        return replay, True

    parent = db.execute(
        select(PlanProposal).where(
            PlanProposal.user_id == user_id,
            PlanProposal.id == proposal_id,
        )
    ).scalar_one_or_none()
    if parent is None:
        raise Road10KGenerationError(
            404,
            "ROAD_10K_PROPOSAL_NOT_FOUND",
            "The road 10K proposal was not found.",
        )
    if parent.policy_version != ROAD_10K_POLICY_VERSION:
        raise Road10KGenerationError(
            409,
            "ROAD_10K_PROPOSAL_POLICY_MISMATCH",
            "Only a deterministic road 10K proposal can be regenerated here.",
        )
    if parent.version != expected_proposal_version:
        raise Road10KGenerationError(
            409,
            "ROAD_10K_PROPOSAL_STALE",
            "The proposal version is stale.",
            current_version=parent.version,
        )

    generation_input, result, purpose, baseline = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    _require_source_revision(
        expected_source_revision=expected_source_revision,
        actual_source_revision=result.deterministic_input_hash,
    )
    parent_audit = _generation_for_proposal(
        db,
        user_id=user_id,
        proposal_id=parent.id,
    )
    if (
        parent_audit is not None
        and parent_audit.source_revision == result.deterministic_input_hash
    ):
        raise Road10KGenerationError(
            409,
            "ROAD_10K_REGENERATION_INPUT_UNCHANGED",
            "Regeneration requires a changed versioned input.",
        )
    if not result.code.startswith("eligible_") or result.plan is None:
        return _readiness_envelope(
            generation_input,
            result,
            purpose=purpose,
            baseline=baseline,
        ), False

    proposal_input = _proposal_input(
        generation_input=generation_input,
        result=result,
        purpose=purpose,
        idempotency_key=idempotency_key,
    )
    idempotency_replay_state = {"replayed": False}
    proposal = create_successor_proposal(
        db,
        user_id=user_id,
        proposal_id=proposal_id,
        expected_version=expected_proposal_version,
        payload=proposal_input,
        current_date=generation_input.athlete_today,
        before_persist=lambda session: _require_locked_source_revision(
            session,
            user_id=user_id,
            constraints=constraints,
            purpose_selection=purpose.selection_payload(),
            expected_source_revision=expected_source_revision,
        ),
        idempotency_replay_state=idempotency_replay_state,
        allow_policy_successor=True,
        validated_policy_purpose=True,
        on_created=lambda session, created: _record_generation(
            session,
            user_id=user_id,
            proposal=created,
            generation_input=generation_input,
            result=result,
            purpose=purpose,
            request_kind="regenerate",
            request_fingerprint=request_fingerprint,
            predecessor=(parent.id, parent.version),
        ),
    )
    if idempotency_replay_state["replayed"]:
        replay = _idempotency_replay(
            db,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if replay is not None:
            return replay, True
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used for a different proposal request.",
        )
    return _proposal_envelope(
        generation_input,
        result,
        purpose=purpose,
        proposal=proposal,
        replayed=False,
    ), False


def validate_road_10k_proposal_adoption(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
) -> None:
    """Revalidate a generated proposal before canonical adoption."""
    audit = _generation_for_proposal(db, user_id=user_id, proposal_id=proposal.id)
    if audit is None:
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_AUDIT_MISSING",
            "The deterministic road 10K proposal has no audit record.",
        )
    constraints = _constraints_from_snapshot(dict(audit.normalized_constraints or {}))
    goal_snapshot = db.get(AdaptivePlanGoalSnapshot, proposal.goal_snapshot_id)
    if goal_snapshot is None:
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal goal snapshot is missing.",
            result_code="validation_failed",
        )
    purpose_selection = {
        "capability_id": audit.capability_id,
        "source": goal_snapshot.purpose_source,
        "expected_goal_id": audit.source_goal_id,
        "expected_goal_revision": audit.source_goal_revision,
    }
    try:
        generation_input, result, _, _ = _evaluate(
            db,
            user_id=user_id,
            constraints=constraints,
            purpose_selection=purpose_selection,
            bind_purpose_revision=True,
        )
    except PlanPurposeError as exc:
        raise AdaptivePlanError(
            409,
            "PLAN_PURPOSE_REASSESSMENT_REQUIRED",
            "The Goal linked to this proposal changed; reassess before adoption.",
            purpose_error=exc.detail["code"],
        ) from exc
    if (
        not result.code.startswith("eligible_")
        or result.deterministic_input_hash != audit.source_revision
        or result.plan is None
    ):
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal no longer meets the deterministic road 10K policy.",
            result_code=result.code,
            current_source_revision=result.deterministic_input_hash,
        )
    if generation_input.policy_version != proposal.policy_version:
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal policy version no longer matches its deterministic input.",
            result_code="validation_failed",
        )
    if not _proposal_matches_generated_plan(
        proposal,
        plan=result.plan,
        input_hash=result.deterministic_input_hash,
    ):
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_REVALIDATION_FAILED",
            "The proposal workout snapshot no longer matches deterministic output.",
            result_code="validation_failed",
        )


def _evaluate(
    db: Session,
    *,
    user_id: str,
    constraints: Road10KPlanGenerationConstraints,
    purpose_selection: Mapping[str, Any] | None,
    bind_purpose_revision: bool = True,
) -> tuple[
    Road10KGenerationInput,
    Road10KGenerationResult,
    ResolvedPlanGenerationPurpose,
    dict[str, Any],
]:
    purpose = resolve_plan_generation_purpose(
        db,
        user_id=user_id,
        selection=purpose_selection,
    )
    config = load_config_from_db(user_id, db)
    athlete_today = effective_athlete_date(config)
    block_start = athlete_today + timedelta(days=1)
    baseline_view = build_road_10k_baseline_view(
        db,
        user_id=user_id,
        purpose_selection=purpose.selection_payload(),
    )
    baseline = baseline_view["baseline"]
    goal_contract = build_road_10k_goal(purpose.goal)
    generation_data = load_road_10k_plan_generation_data(
        user_id,
        db,
        athlete_today=athlete_today,
        block_start=block_start,
        activity_source=config.preferences.get("activities"),
        purpose="road_10k_plan_generation",
    )
    generation_input = Road10KGenerationInput(
        policy_version=ROAD_10K_POLICY_VERSION,
        science_decision_id=ROAD_10K_SCIENCE_DECISION_ID,
        contract_digest=ROAD_10K_CONTRACT_DIGEST,
        source_decision_digest=ROAD_10K_SOURCE_DECISION_DIGEST,
        athlete_today=athlete_today,
        block_start=block_start,
        goal=Road10KGoal(
            goal_kind=goal_contract.goal_kind,
            distance=goal_contract.distance,
            target_time_sec=goal_contract.target_time_sec,
            target_event_date=_goal_event_date(purpose.goal.get("race_date")),
        ),
        baseline_current=baseline.get("status") == "current",
        baseline_snapshot_id=resolve_road_10k_baseline_snapshot_id(
            db,
            user_id=user_id,
            goal_signature=goal_contract.goal_signature,
            evidence=baseline.get("evidence"),
        ),
        baseline_source=(baseline.get("evidence") or {}).get("provenance"),
        baseline_evidence_date=_goal_evidence_date(
            (baseline.get("evidence") or {}).get("observed_date")
        ),
        history=tuple(
            RunningHistoryObservation(
                activity_id=item.activity_id,
                observed_date=item.observed_date,
                duration_min=item.duration_min,
                distance_km=item.distance_km,
                source=item.source,
            )
            for item in generation_data.activities
        ),
        intensity_sources=generation_data.intensity_sources,
        reserved_dates=generation_data.reserved_dates,
        training_pattern_snapshot_version=ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION,
        constraints=constraints,
    )
    result = generate_road_10k_plan(generation_input)
    if bind_purpose_revision:
        result = _bind_purpose_revision(result, purpose=purpose)
    return generation_input, result, purpose, baseline


def _bind_purpose_revision(
    result: Road10KGenerationResult,
    *,
    purpose: ResolvedPlanGenerationPurpose,
) -> Road10KGenerationResult:
    payload = {
        "generator_input_hash": result.deterministic_input_hash,
        "purpose": purpose.selection_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return replace(
        result,
        deterministic_input_hash=hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
    )


def _proposal_input(
    *,
    generation_input: Road10KGenerationInput,
    result: Road10KGenerationResult,
    purpose: ResolvedPlanGenerationPurpose,
    idempotency_key: str,
) -> ProposalInput:
    if result.plan is None:
        raise ValueError("an eligible result is required to persist a proposal")
    return ProposalInput(
        goal={
            "goal_kind": "performance_10k",
            "purpose_source": purpose.source,
            "source_goal_id": purpose.source_goal_id,
            "source_goal_revision": purpose.source_goal_revision,
            "target": {
                "distance": "10k",
                "criterion": "elapsed_time_seconds",
                "setting": "outdoor_road",
                "target_time_sec": generation_input.goal.target_time_sec,
                "target_event_date": (
                    generation_input.goal.target_event_date.isoformat()
                    if generation_input.goal.target_event_date
                    else None
                ),
                "benchmark_date": (
                    generation_input.constraints.benchmark_date.isoformat()
                    if generation_input.constraints.benchmark_date
                    else None
                ),
                "event_state": result.event_context.state,
            },
            "horizon_start": result.plan.horizon_start.isoformat(),
            "horizon_end": result.plan.horizon_end.isoformat(),
        },
        discipline="running",
        workouts=_proposal_workouts(
            result.plan,
            result.deterministic_input_hash,
        ),
        origin="api.plan.road-10k.deterministic",
        actor_type="system",
        actor_id=None,
        idempotency_key=idempotency_key,
        policy_version=ROAD_10K_POLICY_VERSION,
        model_version=ROAD_10K_GENERATOR_VERSION,
        science_version=ROAD_10K_SCIENCE_DECISION_ID,
        assumptions=(
            {"baseline_source": generation_input.baseline_source},
            {"history_cutoff_completed_days": 56},
            {"event_state": result.event_context.state},
            {
                "template_versions": _selected_template_ids(result.plan),
            },
        ),
        unknowns=(
            "Goal feasibility remains unknown; the block does not promise a target outcome.",
        ),
        warnings=(
            "This proposal remains non-canonical until explicit adoption.",
            "Reviewed road 10K templates stay within history-anchored load caps and do not add catch-up work.",
        ),
        alternatives=result.alternatives,
    )


def _proposal_workouts(
    plan: GeneratedRoad10KPlan,
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
                                    ROAD_10K_GENERATOR_VERSION,
                                    input_hash,
                                    workout.template_id
                                    or f"duration-only:{workout.workout_type}",
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
        "controlled_threshold_quality": "Controlled threshold quality",
        "ten_k_specific_interval_quality": "10K-specific interval quality",
    }
    return (
        f"{labels.get(workout.workout_type, workout.workout_type)}. "
        "Deterministic road 10K guardrail; do not add catch-up work. "
        f"Keep the full session at or below the recent distance cap of "
        f"{_format_distance_km(workout.maximum_distance_ceiling_km)} km."
    )


def _record_generation(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
    generation_input: Road10KGenerationInput,
    result: Road10KGenerationResult,
    purpose: ResolvedPlanGenerationPurpose,
    request_kind: str,
    request_fingerprint: str,
    predecessor: tuple[str, int] | None,
) -> None:
    observed_snapshot = {
        "purpose": purpose.public_payload(),
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
            "source": generation_input.baseline_source,
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
                "distance_km": item.distance_km,
                "source": item.source,
            }
            for item in generation_input.history
        ],
        "intensity_sources": [
            [activity_id, source]
            for activity_id, source in generation_input.intensity_sources
        ],
        "reserved_dates": [
            item.isoformat() for item in generation_input.reserved_dates
        ],
        "event_context": _json_safe(asdict(result.event_context)),
    }
    result_snapshot = serialize_generation_result(result)
    result_snapshot.pop("plan", None)
    db.add(
        Road10KPlanGeneration(
            user_id=user_id,
            proposal_id=proposal.id,
            capability_id=OUTDOOR_ROAD_10K_CAPABILITY.capability_id,
            policy_version=result.policy_version,
            generator_version=result.generator_version,
            science_decision_id=result.science_decision_id,
            source_decision_digest=result.source_decision_digest,
            contract_digest=result.contract_digest,
            baseline_snapshot_id=generation_input.baseline_snapshot_id,
            baseline_source=generation_input.baseline_source,
            source_goal_id=purpose.source_goal_id,
            source_goal_revision=purpose.source_goal_revision,
            history_cutoff_completed_days=int(
                ROAD_10K_REQUIRED_INPUTS[
                    "recent_history_lookback_completed_weeks"
                ]
            ) * 7,
            history_observation_ids=[
                item.activity_id for item in generation_input.history
            ],
            training_pattern_snapshot_version=(
                generation_input.training_pattern_snapshot_version
            ),
            event_context_snapshot_version=ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
            active_zone_model_id=None,
            active_zone_model_version=None,
            normalized_constraints=_constraints_snapshot(
                generation_input.constraints,
                purpose=purpose.selection_payload(),
            ),
            selected_template_ids=(
                _selected_template_ids(result.plan)
                if result.plan is not None
                else []
            ),
            source_revision=result.deterministic_input_hash,
            deterministic_input_hash=result.deterministic_input_hash,
            request_kind=request_kind,
            request_fingerprint=request_fingerprint,
            predecessor_proposal_id=predecessor[0] if predecessor else None,
            predecessor_version=predecessor[1] if predecessor else None,
            observed_input_snapshot=observed_snapshot,
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
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used for a different proposal request.",
        )
    proposal_view = read_proposal(db, user_id=user_id, proposal_id=existing.id)
    if proposal_view is None:
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key belongs to a proposal that is no longer readable.",
        )
    purpose = {
        "capability_id": audit.capability_id,
        "source": proposal_view["goal"]["purpose_source"],
        "expected_goal_id": audit.source_goal_id,
        "expected_goal_revision": audit.source_goal_revision,
        "goal": {
            "goal_kind": proposal_view["goal"]["goal_kind"],
            "distance": (proposal_view["goal"].get("target") or {}).get("distance"),
            "target_time_sec": (proposal_view["goal"].get("target") or {}).get("target_time_sec"),
            "race_date": (proposal_view["goal"].get("target") or {}).get("target_event_date"),
        },
    }
    return {
        "schema_version": 1,
        "capability_id": audit.capability_id,
        "policy_version": audit.policy_version,
        "generator_version": audit.generator_version,
        "science_decision_id": audit.science_decision_id,
        "contract_digest": audit.contract_digest,
        "source_decision_digest": audit.source_decision_digest,
        "source_revision": audit.source_revision,
        "purpose": purpose,
        "event_context": (audit.observed_input_snapshot or {}).get("event_context"),
        "history_cutoff_completed_days": 56,
        "template_ids": list(audit.selected_template_ids or []),
        "result": audit.validation_results,
        "proposal": proposal_view,
        "replayed": True,
        "reassessment_dates": _persisted_reassessment_dates(proposal_view),
    }


def _proposal_envelope(
    generation_input: Road10KGenerationInput,
    result: Road10KGenerationResult,
    *,
    purpose: ResolvedPlanGenerationPurpose,
    proposal: dict[str, Any],
    replayed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "capability_id": OUTDOOR_ROAD_10K_CAPABILITY.capability_id,
        "policy_version": result.policy_version,
        "generator_version": result.generator_version,
        "science_decision_id": result.science_decision_id,
        "contract_digest": result.contract_digest,
        "source_decision_digest": result.source_decision_digest,
        "source_revision": result.deterministic_input_hash,
        "purpose": purpose.public_payload(),
        "event_context": _json_safe(asdict(result.event_context)),
        "history_cutoff_completed_days": 56,
        "template_ids": (
            _selected_template_ids(result.plan)
            if result.plan is not None
            else []
        ),
        "result": _result_without_plan(result),
        "proposal": proposal,
        "replayed": replayed,
        "reassessment_dates": [
            item.isoformat()
            for item in (result.plan.reassessment_dates if result.plan else ())
        ],
    }


def _readiness_envelope(
    generation_input: Road10KGenerationInput,
    result: Road10KGenerationResult,
    *,
    purpose: ResolvedPlanGenerationPurpose,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "capability_id": OUTDOOR_ROAD_10K_CAPABILITY.capability_id,
        "policy_version": result.policy_version,
        "generator_version": result.generator_version,
        "science_decision_id": result.science_decision_id,
        "contract_digest": result.contract_digest,
        "source_decision_digest": result.source_decision_digest,
        "source_revision": result.deterministic_input_hash,
        "purpose": purpose.public_payload(),
        "baseline": baseline,
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "event_context": _json_safe(asdict(result.event_context)),
        "history_cutoff_completed_days": 56,
        "template_ids": (
            _selected_template_ids(result.plan)
            if result.plan is not None
            else []
        ),
        "result": _result_without_plan(result),
    }


def _result_without_plan(result: Road10KGenerationResult) -> dict[str, Any]:
    payload = serialize_generation_result(result)
    payload.pop("plan", None)
    return payload


def _request_fingerprint(
    *,
    request_kind: str,
    expected_source_revision: str,
    constraints: Road10KPlanGenerationConstraints,
    purpose_selection: Mapping[str, Any] | None,
    predecessor: tuple[str, int] | None = None,
) -> str:
    payload = {
        "request_kind": request_kind,
        "expected_source_revision": expected_source_revision,
        "constraints": _constraints_snapshot(
            constraints,
            purpose=(
                dict(purpose_selection) if purpose_selection is not None else None
            ),
        ),
        "predecessor": (
            {"proposal_id": predecessor[0], "version": predecessor[1]}
            if predecessor is not None
            else None
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_locked_source_revision(
    db: Session,
    *,
    user_id: str,
    constraints: Road10KPlanGenerationConstraints,
    purpose_selection: Mapping[str, Any] | None,
    expected_source_revision: str,
) -> None:
    db.expire_all()
    _, locked_result, _, _ = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    _require_source_revision(
        expected_source_revision=expected_source_revision,
        actual_source_revision=locked_result.deterministic_input_hash,
    )


def _proposal_matches_generated_plan(
    proposal: PlanProposal,
    *,
    plan: GeneratedRoad10KPlan,
    input_hash: str,
) -> bool:
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
        raise Road10KGenerationError(
            409,
            "ROAD_10K_SOURCE_REVISION_STALE",
            "The readiness source revision changed; fetch readiness again before generating.",
            current_source_revision=actual_source_revision,
        )


def _generation_for_proposal(
    db: Session,
    *,
    user_id: str,
    proposal_id: str,
) -> Road10KPlanGeneration | None:
    return db.execute(
        select(Road10KPlanGeneration).where(
            Road10KPlanGeneration.user_id == user_id,
            Road10KPlanGeneration.proposal_id == proposal_id,
        )
    ).scalar_one_or_none()


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
    constraints: Road10KPlanGenerationConstraints,
    *,
    purpose: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "adult_confirmed": constraints.adult_confirmed,
        "current_symptom_stop": constraints.current_symptom_stop,
        "available_weekdays": list(constraints.available_weekdays),
        "weekly_time_limit_min": constraints.weekly_time_limit_min,
        "maximum_session_duration_min": constraints.maximum_session_duration_min,
        "unavailable_dates": [
            item.isoformat() for item in constraints.unavailable_dates
        ],
        "preferred_longest_easy_weekday": (
            constraints.preferred_longest_easy_weekday
        ),
        "benchmark_date": (
            constraints.benchmark_date.isoformat()
            if constraints.benchmark_date is not None
            else None
        ),
        "purpose": dict(purpose) if purpose is not None else None,
    }


def _constraints_from_snapshot(
    snapshot: dict[str, Any],
) -> Road10KPlanGenerationConstraints:
    try:
        return Road10KPlanGenerationConstraints(
            adult_confirmed=bool(snapshot["adult_confirmed"]),
            current_symptom_stop=bool(snapshot["current_symptom_stop"]),
            available_weekdays=tuple(
                int(item) for item in snapshot["available_weekdays"]
            ),
            weekly_time_limit_min=int(snapshot["weekly_time_limit_min"]),
            maximum_session_duration_min=int(
                snapshot["maximum_session_duration_min"]
            ),
            unavailable_dates=tuple(
                date.fromisoformat(str(item))
                for item in snapshot["unavailable_dates"]
            ),
            preferred_longest_easy_weekday=(
                None
                if snapshot.get("preferred_longest_easy_weekday") is None
                else int(snapshot["preferred_longest_easy_weekday"])
            ),
            benchmark_date=(
                None
                if snapshot.get("benchmark_date") in {None, ""}
                else date.fromisoformat(str(snapshot["benchmark_date"]))
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_AUDIT_INVALID",
            "The deterministic road 10K proposal audit is invalid.",
        ) from exc


def _persisted_reassessment_dates(proposal: dict[str, Any]) -> list[str]:
    goal = proposal.get("goal") or {}
    try:
        horizon_start = date.fromisoformat(str(goal["horizon_start"]))
        horizon_end = date.fromisoformat(str(goal["horizon_end"]))
    except (KeyError, TypeError, ValueError):
        return []
    reassessment = horizon_start + timedelta(days=7)
    return [reassessment.isoformat()] if reassessment <= horizon_end else []


def _selected_template_ids(plan: GeneratedRoad10KPlan) -> list[str]:
    return sorted(
        {
            workout.template_id
            for week in plan.weeks
            for workout in week.workouts
            if workout.template_id is not None
        }
    )


def _format_distance_km(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _json_safe(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
