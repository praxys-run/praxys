"""Owner-scoped orchestration for deterministic road 10K proposals."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, timedelta
import hashlib
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analysis.config import effective_athlete_date, load_config_from_db
from analysis.data_loader import load_road_10k_plan_generation_data
from analysis.road_10k_baseline import build_road_10k_goal
from analysis.road_10k_contract import (
    ROAD_10K_CONTRACT_DIGEST,
    ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
    ROAD_10K_GENERATOR_VERSION,
    ROAD_10K_GUARDRAILS,
    ROAD_10K_HISTORY_CUTOFF_COMPLETED_DAYS,
    ROAD_10K_POLICY_VERSION,
    ROAD_10K_REASSESSMENT_COMPLETED_DAYS,
    ROAD_10K_SCIENCE_DECISION_ID,
    ROAD_10K_SOURCE_DECISION_DIGEST,
    ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION,
    road_10k_typed_outcome,
)
from analysis.road_10k_plan_generation import (
    GeneratedRoad10KPlan,
    GeneratedWorkout,
    RecentHistoryStatistics,
    Road10KGenerationInput,
    Road10KGenerationResult,
    Road10KEventContext,
    Road10KGoal,
    Road10KPlanGenerationConstraints,
    Road10KTrainingPatternSnapshot as TrainingPatternAggregate,
    RunningHistoryObservation,
    build_road_10k_training_pattern_snapshot,
    build_event_context,
    generate_road_10k_plan,
    road_10k_training_pattern_canonical_fingerprint,
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
from api.road_10k_control import record_result, require_road_10k_gate
from db.models import (
    AdaptivePlanGoalSnapshot,
    PlanProposal,
    Road10KBaselineSnapshot,
    Road10KPlanGeneration,
    Road10KTrainingPatternSnapshot,
)


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


def _typed_outcome_fields(code: str) -> dict[str, Any]:
    try:
        return road_10k_typed_outcome(code)
    except ValueError as exc:
        raise Road10KGenerationError(
            409,
            "ROAD_10K_OUTCOME_INVALID",
            "The deterministic road 10K outcome code is not accepted.",
            result_code=code,
        ) from exc


def _plan_returned(code: str) -> bool:
    return bool(_typed_outcome_fields(code)["plan_returned"])


def _record_owner_evaluation(
    db: Session,
    *,
    user_id: str,
    boundary: str,
    result: Road10KGenerationResult,
) -> None:
    """Persist only the accepted typed outcome, never plan or activity data."""
    record_result(
        db,
        user_id=user_id,
        result_code=result.code,
        payload={
            "boundary": boundary,
            **_typed_outcome_fields(result.code),
        },
    )


def build_road_10k_readiness(
    db: Session,
    *,
    user_id: str,
    constraints: Road10KPlanGenerationConstraints,
    purpose_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the typed road 10K readiness envelope without persisting."""
    require_road_10k_gate(db, user_id=user_id, expose=True)
    generation_input, result, purpose, baseline = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    _record_owner_evaluation(
        db,
        user_id=user_id,
        boundary="readiness",
        result=result,
    )
    require_road_10k_gate(db, user_id=user_id, expose=False)
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
    require_road_10k_gate(db, user_id=user_id, expose=True)
    generation_input, result, purpose, baseline = _evaluate(
        db,
        user_id=user_id,
        constraints=constraints,
        purpose_selection=purpose_selection,
    )
    _record_owner_evaluation(
        db,
        user_id=user_id,
        boundary="alternatives",
        result=result,
    )
    require_road_10k_gate(db, user_id=user_id, expose=False)
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
    require_road_10k_gate(db, user_id=user_id, expose=True)
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
        require_road_10k_gate(db, user_id=user_id, expose=False)
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
    if not _plan_returned(result.code) or result.plan is None:
        _record_owner_evaluation(
            db,
            user_id=user_id,
            boundary="generate",
            result=result,
        )
        require_road_10k_gate(db, user_id=user_id, expose=False)
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
    locked_generation_input: Road10KGenerationInput | None = None
    locked_result: Road10KGenerationResult | None = None
    locked_purpose: ResolvedPlanGenerationPurpose | None = None
    locked_snapshot: Road10KTrainingPatternSnapshot | None = None

    def prepare_locked_generation(session: Session) -> None:
        nonlocal locked_generation_input, locked_result
        nonlocal locked_purpose, locked_snapshot
        require_road_10k_gate(
            session,
            user_id=user_id,
            expose=False,
        )
        session.expire_all()
        (
            locked_generation_input,
            locked_result,
            locked_purpose,
            _locked_baseline,
        ) = _evaluate(
            session,
            user_id=user_id,
            constraints=constraints,
            purpose_selection=purpose.selection_payload(),
        )
        _require_source_revision(
            expected_source_revision=expected_source_revision,
            actual_source_revision=locked_result.deterministic_input_hash,
        )
        if not _plan_returned(locked_result.code) or locked_result.plan is None:
            raise Road10KGenerationError(
                409,
                "ROAD_10K_SOURCE_REVISION_STALE",
                "The road 10K input no longer produces an adoptable proposal.",
                current_source_revision=locked_result.deterministic_input_hash,
            )
        locked_snapshot = _persist_training_pattern_snapshot(
            session,
            user_id=user_id,
            generation_input=locked_generation_input,
            result=locked_result,
        )

    def record_locked_generation(
        session: Session,
        created: PlanProposal,
    ) -> None:
        if (
            locked_generation_input is None
            or locked_result is None
            or locked_purpose is None
            or locked_snapshot is None
        ):
            raise RuntimeError("road 10K locked generation state is missing")
        _record_generation(
            session,
            user_id=user_id,
            proposal=created,
            generation_input=locked_generation_input,
            result=locked_result,
            purpose=locked_purpose,
            training_pattern_snapshot=locked_snapshot,
            request_kind="generate",
            request_fingerprint=request_fingerprint,
            predecessor=None,
        )
        require_road_10k_gate(
            session,
            user_id=user_id,
            expose=False,
        )

    proposal = create_draft_proposal(
        db,
        user_id=user_id,
        payload=proposal_input,
        current_date=generation_input.athlete_today,
        before_persist=prepare_locked_generation,
        idempotency_replay_state=idempotency_replay_state,
        validated_policy_purpose=True,
        allow_road_10k_policy=True,
        on_created=record_locked_generation,
    )
    if idempotency_replay_state["replayed"]:
        replay = _idempotency_replay(
            db,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if replay is not None:
            require_road_10k_gate(db, user_id=user_id, expose=False)
            return replay, True
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used for a different proposal request.",
        )
    response = _proposal_envelope(
        generation_input,
        result,
        purpose=purpose,
        proposal=proposal,
        replayed=False,
    )
    _record_owner_evaluation(
        db,
        user_id=user_id,
        boundary="generate",
        result=result,
    )
    require_road_10k_gate(db, user_id=user_id, expose=False)
    return response, False


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
    require_road_10k_gate(db, user_id=user_id, expose=True)
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
        require_road_10k_gate(db, user_id=user_id, expose=False)
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
    if not _plan_returned(result.code) or result.plan is None:
            _record_owner_evaluation(
                db,
                user_id=user_id,
                boundary="regenerate",
                result=result,
            )
            require_road_10k_gate(db, user_id=user_id, expose=False)
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
    locked_generation_input: Road10KGenerationInput | None = None
    locked_result: Road10KGenerationResult | None = None
    locked_purpose: ResolvedPlanGenerationPurpose | None = None
    locked_snapshot: Road10KTrainingPatternSnapshot | None = None

    def prepare_locked_generation(session: Session) -> None:
        nonlocal locked_generation_input, locked_result
        nonlocal locked_purpose, locked_snapshot
        require_road_10k_gate(
            session,
            user_id=user_id,
            expose=False,
        )
        session.expire_all()
        (
            locked_generation_input,
            locked_result,
            locked_purpose,
            _locked_baseline,
        ) = _evaluate(
            session,
            user_id=user_id,
            constraints=constraints,
            purpose_selection=purpose.selection_payload(),
        )
        _require_source_revision(
            expected_source_revision=expected_source_revision,
            actual_source_revision=locked_result.deterministic_input_hash,
        )
        if not _plan_returned(locked_result.code) or locked_result.plan is None:
            raise Road10KGenerationError(
                409,
                "ROAD_10K_SOURCE_REVISION_STALE",
                "The road 10K input no longer produces an adoptable proposal.",
                current_source_revision=locked_result.deterministic_input_hash,
            )
        locked_snapshot = _persist_training_pattern_snapshot(
            session,
            user_id=user_id,
            generation_input=locked_generation_input,
            result=locked_result,
        )

    def record_locked_generation(
        session: Session,
        created: PlanProposal,
    ) -> None:
        if (
            locked_generation_input is None
            or locked_result is None
            or locked_purpose is None
            or locked_snapshot is None
        ):
            raise RuntimeError("road 10K locked generation state is missing")
        _record_generation(
            session,
            user_id=user_id,
            proposal=created,
            generation_input=locked_generation_input,
            result=locked_result,
            purpose=locked_purpose,
            training_pattern_snapshot=locked_snapshot,
            request_kind="regenerate",
            request_fingerprint=request_fingerprint,
            predecessor=(parent.id, parent.version),
        )
        require_road_10k_gate(
            session,
            user_id=user_id,
            expose=False,
        )

    proposal = create_successor_proposal(
        db,
        user_id=user_id,
        proposal_id=proposal_id,
        expected_version=expected_proposal_version,
        payload=proposal_input,
        current_date=generation_input.athlete_today,
        before_persist=prepare_locked_generation,
        idempotency_replay_state=idempotency_replay_state,
        allow_policy_successor=True,
        validated_policy_purpose=True,
        allow_road_10k_policy=True,
        on_created=record_locked_generation,
    )
    if idempotency_replay_state["replayed"]:
        replay = _idempotency_replay(
            db,
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )
        if replay is not None:
            require_road_10k_gate(db, user_id=user_id, expose=False)
            return replay, True
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used for a different proposal request.",
        )
    response = _proposal_envelope(
        generation_input,
        result,
        purpose=purpose,
        proposal=proposal,
        replayed=False,
    )
    _record_owner_evaluation(
        db,
        user_id=user_id,
        boundary="regenerate",
        result=result,
    )
    require_road_10k_gate(db, user_id=user_id, expose=False)
    return response, False


def validate_road_10k_proposal_adoption(
    db: Session,
    *,
    user_id: str,
    proposal: PlanProposal,
) -> None:
    """Revalidate a generated proposal before canonical adoption."""
    try:
        require_road_10k_gate(db, user_id=user_id, expose=False)
    except Exception as exc:
        raise AdaptivePlanError(
            404,
            "ROAD_10K_PROPOSAL_NOT_AVAILABLE",
            "The road 10K proposal is not available under the current rollout.",
        ) from exc
    audit = _generation_for_proposal(db, user_id=user_id, proposal_id=proposal.id)
    if audit is None:
        raise AdaptivePlanError(
            409,
            "ROAD_10K_PROPOSAL_AUDIT_MISSING",
            "The deterministic road 10K proposal has no audit record.",
        )
    try:
        _validate_event_context_snapshot_version(audit)
        _training_pattern_snapshot_for_audit(db, audit=audit)
        _baseline_snapshot_for_audit(db, audit=audit)
    except Road10KGenerationError as exc:
        raise AdaptivePlanError(
            409,
            "ROAD_10K_REGENERATE_REQUIRED",
            "The road 10K proposal cannot be replayed from its persisted provenance; regenerate it before adoption.",
            replay_error=exc.detail["code"],
        ) from exc
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
        not _plan_returned(result.code)
        or result.deterministic_input_hash != audit.source_revision
        or result.plan is None
    ):
        raise AdaptivePlanError(
            409,
            "ROAD_10K_REGENERATE_REQUIRED",
            "The road 10K source inputs changed; regenerate before adoption.",
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
    history = tuple(
        RunningHistoryObservation(
            activity_id=item.activity_id,
            observed_date=item.observed_date,
            duration_min=item.duration_min,
            distance_km=item.distance_km,
            source=item.source,
        )
        for item in generation_data.activities
    )
    training_pattern = build_road_10k_training_pattern_snapshot(
        history,
        athlete_today=athlete_today,
        intensity_sources=generation_data.intensity_sources,
        reserved_dates=generation_data.reserved_dates,
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
        history=history,
        intensity_sources=generation_data.intensity_sources,
        reserved_dates=generation_data.reserved_dates,
        training_pattern_snapshot_version=training_pattern.version,
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
            {"history_cutoff_completed_days": ROAD_10K_HISTORY_CUTOFF_COMPLETED_DAYS},
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
    training_pattern_snapshot: Road10KTrainingPatternSnapshot,
    request_kind: str,
    request_fingerprint: str,
    predecessor: tuple[str, int] | None,
) -> None:
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
            history_cutoff_completed_days=ROAD_10K_HISTORY_CUTOFF_COMPLETED_DAYS,
            training_pattern_snapshot_version=(
                training_pattern_snapshot.version
            ),
            event_context_snapshot_version=ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION,
            active_zone_model_id=None,
            active_zone_model_version=None,
            normalized_constraints=_constraints_snapshot(generation_input.constraints),
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
            result_code=result.code,
            validation_reason_code=result.failed_rule_id,
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
    _validate_event_context_snapshot_version(audit)
    proposal_view = read_proposal(db, user_id=user_id, proposal_id=existing.id)
    if proposal_view is None:
        raise Road10KGenerationError(
            409,
            "ROAD_10K_IDEMPOTENCY_CONFLICT",
            "This idempotency key belongs to a proposal that is no longer readable.",
        )
    training_pattern_snapshot = _training_pattern_snapshot_for_audit(
        db,
        audit=audit,
    )
    _baseline_snapshot_for_audit(db, audit=audit)
    event_context = _replayed_event_context(
        proposal_view,
        constraints_snapshot=dict(audit.normalized_constraints or {}),
    )
    history_statistics = _snapshot_history_statistics(
        training_pattern_snapshot
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
        "guardrails": ROAD_10K_GUARDRAILS.public_payload(),
        "purpose": purpose,
        "event_context": _json_safe(asdict(event_context)),
        "history_cutoff_completed_days": audit.history_cutoff_completed_days,
        "template_ids": list(audit.selected_template_ids or []),
        "result": _replayed_result_payload(
            audit=audit,
            event_context=event_context,
            history_statistics=history_statistics,
            alternatives=list(proposal_view.get("alternatives") or []),
        ),
        "proposal": proposal_view,
        "replayed": True,
        "reassessment_dates": _persisted_reassessment_dates(proposal_view),
    }


def _replayed_result_payload(
    *,
    audit: Road10KPlanGeneration,
    event_context: Road10KEventContext,
    history_statistics: RecentHistoryStatistics,
    alternatives: list[str],
) -> dict[str, Any]:
    payload = {
        "policy_version": audit.policy_version,
        "generator_version": audit.generator_version,
        "science_decision_id": audit.science_decision_id,
        "contract_digest": audit.contract_digest,
        "source_decision_digest": audit.source_decision_digest,
        "code": audit.result_code,
        "deterministic_input_hash": audit.deterministic_input_hash,
        "event_context": _json_safe(asdict(event_context)),
        "history_statistics": _json_safe(asdict(history_statistics)),
        "failed_rule_id": audit.validation_reason_code,
        "observed_or_stated_reason": None,
        "uncertainty_or_missing_field": None,
        "alternatives": alternatives,
    }
    payload.update(_typed_outcome_fields(audit.result_code))
    return payload


def _replayed_event_context(
    proposal: Mapping[str, Any],
    *,
    constraints_snapshot: dict[str, Any],
) -> Road10KEventContext:
    goal = _proposal_goal(proposal)
    constraints = _constraints_from_snapshot(constraints_snapshot)
    return build_event_context(goal, constraints)


def _proposal_goal(proposal: Mapping[str, Any]) -> Road10KGoal:
    goal = dict(proposal.get("goal") or {})
    target = dict(goal.get("target") or {})
    return Road10KGoal(
        goal_kind=str(goal.get("goal_kind") or "performance_10k"),
        distance=(str(target.get("distance") or goal.get("distance") or "").strip() or None),
        target_time_sec=_int_or_none(target.get("target_time_sec")),
        target_event_date=_goal_event_date(target.get("target_event_date")),
    )


def _int_or_none(value: object) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _persist_training_pattern_snapshot(
    db: Session,
    *,
    user_id: str,
    generation_input: Road10KGenerationInput,
    result: Road10KGenerationResult,
) -> Road10KTrainingPatternSnapshot:
    aggregate = build_road_10k_training_pattern_snapshot(
        generation_input.history,
        athlete_today=generation_input.athlete_today,
        intensity_sources=generation_input.intensity_sources,
        reserved_dates=generation_input.reserved_dates,
    )
    if (
        aggregate.version != generation_input.training_pattern_snapshot_version
        or aggregate.history_statistics() != result.history_statistics
        or aggregate.recent_maximum_session_distance_km is None
        or aggregate.latest_run_date is None
    ):
        raise Road10KGenerationError(
            409,
            "ROAD_10K_TRAINING_PATTERN_INVALID",
            "The road 10K aggregate snapshot does not match the deterministic input.",
        )
    existing = db.execute(
        select(Road10KTrainingPatternSnapshot).where(
            Road10KTrainingPatternSnapshot.user_id == user_id,
            Road10KTrainingPatternSnapshot.version == aggregate.version,
        )
    ).scalar_one_or_none()
    if existing is not None:
        _require_training_pattern_snapshot_match(existing, aggregate=aggregate)
        return existing

    row = Road10KTrainingPatternSnapshot(
        user_id=user_id,
        version=aggregate.version,
        schema_version=aggregate.schema_version,
        policy_version=aggregate.policy_version,
        usable_completed_weeks=aggregate.usable_completed_weeks,
        recent_modal_running_frequency=aggregate.recent_modal_running_frequency,
        recent_median_usable_weekly_minutes=(
            aggregate.recent_median_usable_weekly_minutes
        ),
        recent_maximum_usable_weekly_minutes=(
            aggregate.recent_maximum_usable_weekly_minutes
        ),
        recent_maximum_session_minutes=aggregate.recent_maximum_session_minutes,
        recent_maximum_session_distance_km=(
            aggregate.recent_maximum_session_distance_km
        ),
        latest_run_date=aggregate.latest_run_date,
        history_observation_count=aggregate.history_observation_count,
        history_provenance_fingerprint=(
            aggregate.history_provenance_fingerprint
        ),
        intensity_observation_count=aggregate.intensity_observation_count,
        intensity_provenance_fingerprint=(
            aggregate.intensity_provenance_fingerprint
        ),
        reserved_date_count=aggregate.reserved_date_count,
        reservation_fingerprint=aggregate.reservation_fingerprint,
        canonical_fingerprint=aggregate.canonical_fingerprint,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.execute(
            select(Road10KTrainingPatternSnapshot).where(
                Road10KTrainingPatternSnapshot.user_id == user_id,
                Road10KTrainingPatternSnapshot.version == aggregate.version,
            )
        ).scalar_one_or_none()
        if existing is None:
            raise
        _require_training_pattern_snapshot_match(existing, aggregate=aggregate)
        return existing
    return row


def _require_training_pattern_snapshot_match(
    snapshot: Road10KTrainingPatternSnapshot,
    *,
    aggregate: TrainingPatternAggregate,
) -> None:
    fields = (
        "version",
        "schema_version",
        "policy_version",
        "usable_completed_weeks",
        "recent_modal_running_frequency",
        "recent_median_usable_weekly_minutes",
        "recent_maximum_usable_weekly_minutes",
        "recent_maximum_session_minutes",
        "recent_maximum_session_distance_km",
        "latest_run_date",
        "history_observation_count",
        "history_provenance_fingerprint",
        "intensity_observation_count",
        "intensity_provenance_fingerprint",
        "reserved_date_count",
        "reservation_fingerprint",
        "canonical_fingerprint",
    )
    if any(
        getattr(snapshot, field) != getattr(aggregate, field)
        for field in fields
    ):
        raise Road10KGenerationError(
            409,
            "ROAD_10K_TRAINING_PATTERN_CONFLICT",
            "The stored road 10K aggregate snapshot conflicts with its immutable version.",
        )


def _training_pattern_snapshot_for_audit(
    db: Session,
    *,
    audit: Road10KPlanGeneration,
) -> Road10KTrainingPatternSnapshot:
    version = str(audit.training_pattern_snapshot_version or "")
    if not _valid_snapshot_reference(version):
        raise _regenerate_required("legacy_training_pattern_reference")
    snapshot = db.execute(
        select(Road10KTrainingPatternSnapshot).where(
            Road10KTrainingPatternSnapshot.user_id == audit.user_id,
            Road10KTrainingPatternSnapshot.version == version,
        )
    ).scalar_one_or_none()
    if snapshot is None:
        raise _regenerate_required("training_pattern_snapshot_missing")
    statistics = _snapshot_history_statistics(snapshot)
    expected_fingerprint = road_10k_training_pattern_canonical_fingerprint(
        schema_version=snapshot.schema_version,
        policy_version=snapshot.policy_version,
        statistics=statistics,
        history_observation_count=snapshot.history_observation_count,
        history_provenance_fingerprint=(
            snapshot.history_provenance_fingerprint
        ),
        intensity_observation_count=snapshot.intensity_observation_count,
        intensity_provenance_fingerprint=(
            snapshot.intensity_provenance_fingerprint
        ),
        reserved_date_count=snapshot.reserved_date_count,
        reservation_fingerprint=snapshot.reservation_fingerprint,
    )
    if (
        snapshot.schema_version
        != ROAD_10K_TRAINING_PATTERN_SNAPSHOT_VERSION
        or snapshot.policy_version != audit.policy_version
        or not all(
            _valid_sha256(value)
            for value in (
                snapshot.history_provenance_fingerprint,
                snapshot.intensity_provenance_fingerprint,
                snapshot.reservation_fingerprint,
                snapshot.canonical_fingerprint,
            )
        )
        or snapshot.canonical_fingerprint != expected_fingerprint
        or snapshot.version != f"v1:{expected_fingerprint}"
    ):
        raise _regenerate_required("training_pattern_snapshot_invalid")
    return snapshot


def _baseline_snapshot_for_audit(
    db: Session,
    *,
    audit: Road10KPlanGeneration,
) -> Road10KBaselineSnapshot:
    baseline_snapshot_id = str(audit.baseline_snapshot_id or "")
    if not baseline_snapshot_id:
        raise _regenerate_required("baseline_snapshot_missing")
    snapshot = db.execute(
        select(Road10KBaselineSnapshot).where(
            Road10KBaselineSnapshot.user_id == audit.user_id,
            Road10KBaselineSnapshot.id == baseline_snapshot_id,
        )
    ).scalar_one_or_none()
    if (
        snapshot is None
        or snapshot.qualification_status != "direct_current"
        or snapshot.provenance != audit.baseline_source
    ):
        raise _regenerate_required("baseline_snapshot_unavailable")
    return snapshot


def _snapshot_history_statistics(
    snapshot: Road10KTrainingPatternSnapshot,
) -> RecentHistoryStatistics:
    return RecentHistoryStatistics(
        usable_completed_weeks=snapshot.usable_completed_weeks,
        recent_modal_running_frequency=snapshot.recent_modal_running_frequency,
        recent_median_usable_weekly_minutes=(
            snapshot.recent_median_usable_weekly_minutes
        ),
        recent_maximum_usable_weekly_minutes=(
            snapshot.recent_maximum_usable_weekly_minutes
        ),
        recent_maximum_session_minutes=snapshot.recent_maximum_session_minutes,
        recent_maximum_session_distance_km=(
            snapshot.recent_maximum_session_distance_km
        ),
        latest_run_date=snapshot.latest_run_date,
    )


def _valid_snapshot_reference(value: str) -> bool:
    return (
        len(value) == 67
        and value.startswith("v1:")
        and _valid_sha256(value[3:])
    )


def _validate_event_context_snapshot_version(
    audit: Road10KPlanGeneration,
) -> None:
    if (
        audit.event_context_snapshot_version
        != ROAD_10K_EVENT_CONTEXT_SNAPSHOT_VERSION
    ):
        raise _regenerate_required("event_context_snapshot_version_mismatch")


def _valid_sha256(value: str) -> bool:
    return (
        len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _regenerate_required(reason: str) -> Road10KGenerationError:
    return Road10KGenerationError(
        409,
        "ROAD_10K_REGENERATE_REQUIRED",
        "The persisted road 10K replay provenance is unavailable; regenerate the proposal.",
        reason=reason,
    )


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
        "guardrails": ROAD_10K_GUARDRAILS.public_payload(),
        "purpose": purpose.public_payload(),
        "event_context": _json_safe(asdict(result.event_context)),
        "history_cutoff_completed_days": ROAD_10K_HISTORY_CUTOFF_COMPLETED_DAYS,
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
        "guardrails": ROAD_10K_GUARDRAILS.public_payload(),
        "purpose": purpose.public_payload(),
        "baseline": baseline,
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "event_context": _json_safe(asdict(result.event_context)),
        "history_cutoff_completed_days": ROAD_10K_HISTORY_CUTOFF_COMPLETED_DAYS,
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
    payload.update(_typed_outcome_fields(result.code))
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
        "constraints": _constraints_snapshot(constraints),
        "purpose": (
            dict(purpose_selection) if purpose_selection is not None else None
        ),
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
    reassessment = horizon_start + timedelta(
        days=ROAD_10K_REASSESSMENT_COMPLETED_DAYS
    )
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
