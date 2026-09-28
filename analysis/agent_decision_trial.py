"""Pure, default-off transitions for a bounded decision-card experiment.

These transitions are not admission authority. A future trusted entrypoint must
authenticate callers and persist the entire state with a shared atomic CAS.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from analysis.agentic_task_routing import (
    TaskRoute,
    load_task_routing_config,
    route_task,
)


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_POLICY_PATH = _ROOT / "config" / "agent-decision-card-trial.json"
_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_TASK_PATTERN = r"^tsk_[0-9a-f]{64}$"
_EVENT_PATTERN = r"^evt_[0-9a-f]{64}$"


class TrialUnavailable(ValueError):
    """The trial cannot safely admit or resume this task."""


class TrialRecord(BaseModel):
    """Reject unexpected or silently coerced trial fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TrialPolicy(TrialRecord):
    """Versioned, presentation-only cohort policy."""

    schema_version: Literal[1]
    cohort_id: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    candidate_version: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    status: Literal["disabled", "active"]
    max_assignments: Literal[16]
    checkpoint_at: Literal[8]
    permitted_entrypoints: tuple[Literal["cloud", "local", "paseo"], ...]
    eligible_primary_objects: tuple[str, ...] = Field(min_length=1)
    excluded_impacts: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_boundaries(self) -> "TrialPolicy":
        """Refuse duplicate or unrecognized eligibility and entrypoint IDs."""
        routing = load_task_routing_config()
        for name, values, known in (
            ("permitted_entrypoints", self.permitted_entrypoints, {"cloud", "local", "paseo"}),
            (
                "eligible_primary_objects",
                self.eligible_primary_objects,
                set(routing.primary_objects),
            ),
            ("excluded_impacts", self.excluded_impacts, set(routing.impacts)),
        ):
            if len(values) != len(set(values)) or set(values) - known:
                raise ValueError(f"invalid {name}")
        if self.status == "active" and len(self.permitted_entrypoints) != 1:
            raise ValueError("the first cohort requires exactly one trusted entrypoint")
        return self


def load_trial_policy(path: Path = _DEFAULT_POLICY_PATH) -> TrialPolicy:
    """Read the checked-in policy; reject any live enrollment without a broker."""
    policy = TrialPolicy.model_validate_json(path.read_text(encoding="utf-8"))
    if policy.status != "disabled" or policy.permitted_entrypoints:
        raise TrialUnavailable("no protected admission broker is installed")
    return policy


def policy_digest(policy: TrialPolicy) -> str:
    """Pin all cohort rules while allowing an emergency status disable."""
    payload = policy.model_dump(exclude={"status"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class OutcomeEvent(TrialRecord):
    """A privacy-minimal, append-only outcome, including no-PR attempts."""

    event_key: str = Field(pattern=_EVENT_PATTERN)
    kind: Literal[
        "no_pr", "blocked", "abandoned", "failed", "pr_open", "merged", "baseline_fallback"
    ]
    pr_number: int | None = Field(default=None, ge=1)
    head_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    @model_validator(mode="after")
    def validate_pr_link(self) -> "OutcomeEvent":
        """Prevent a supposed PR outcome from losing its head binding."""
        if (self.pr_number is None) != (self.head_sha is None):
            raise ValueError("PR number and head SHA must be provided together")
        if self.kind in {"pr_open", "merged"} and self.pr_number is None:
            raise ValueError("PR outcomes require a head-bound PR link")
        if self.kind == "no_pr" and self.pr_number is not None:
            raise ValueError("a no-PR outcome cannot link a PR")
        return self


class Admission(TrialRecord):
    """The first group assignment; later events cannot change its arm."""

    arm: Literal["A", "B"]
    entrypoint: Literal["cloud", "local", "paseo"]
    candidate_version: str
    route_digest: str = Field(pattern=_DIGEST_PATTERN)
    classification_digest: str = Field(pattern=_DIGEST_PATTERN)
    events: tuple[OutcomeEvent, ...] = ()


class CohortState(TrialRecord):
    """One whole-cohort CAS value; never merge independently written copies."""

    schema_version: Literal[1]
    cohort_id: str
    policy_digest: str = Field(pattern=_DIGEST_PATTERN)
    assignments: dict[str, Admission] = Field(default_factory=dict)
    checkpoint_review_digest: str | None = Field(default=None, pattern=_DIGEST_PATTERN)
    stopped: bool = False

    @model_validator(mode="after")
    def validate_history(self) -> "CohortState":
        """Reject malformed keys and fabricated or missing checkpoint reviews."""
        if any(not re.fullmatch(_TASK_PATTERN, key) for key in self.assignments):
            raise ValueError("invalid opaque task key")
        if len(self.assignments) > 16:
            raise ValueError("cohort exceeds its assignment cap")
        if self.checkpoint_review_digest is not None and len(self.assignments) < 8:
            raise ValueError("checkpoint cannot precede its eighth assignment")
        if len(self.assignments) > 8 and self.checkpoint_review_digest is None:
            raise ValueError("assignments beyond eight require checkpoint review")
        if sum(item.arm == "A" for item in self.assignments.values()) != (
            len(self.assignments) + 1
        ) // 2:
            raise ValueError("cohort assignment balance is invalid")
        if any(
            len({event.event_key for event in item.events}) != len(item.events)
            for item in self.assignments.values()
        ):
            raise ValueError("outcome event identity must be unique per task")
        return self


def new_cohort(policy: TrialPolicy) -> CohortState:
    """Initialize one empty cohort for a future protected store."""
    return CohortState(
        schema_version=1,
        cohort_id=policy.cohort_id,
        policy_digest=policy_digest(policy),
    )


class AdmissionRequest(TrialRecord):
    """Trusted entrypoint input with an opaque, stable task identity."""

    task_key: str = Field(pattern=_TASK_PATTERN)
    entrypoint: Literal["cloud", "local", "paseo"]
    work_contract: TaskRoute


@dataclass(frozen=True)
class AdmissionResult:
    """Proposed transition and group, never a dispatch receipt."""

    state: CohortState
    arm: Literal["A", "B"] | None
    reason: str


def _check_state(policy: TrialPolicy, state: CohortState) -> None:
    if state.cohort_id != policy.cohort_id or state.policy_digest != policy_digest(policy):
        raise TrialUnavailable("cohort policy or version mismatch")
    if any(
        assignment.candidate_version != policy.candidate_version
        for assignment in state.assignments.values()
    ):
        raise TrialUnavailable("an assignment has a different candidate version")


def plan_admission(
    policy: TrialPolicy, state: CohortState, request: AdmissionRequest
) -> AdmissionResult:
    """Propose one idempotent assignment; a trusted broker must commit it."""
    _check_state(policy, state)
    canonical = route_task(request.work_contract.classification)
    if canonical != request.work_contract:
        raise TrialUnavailable("work contract does not match deterministic routing")

    existing = state.assignments.get(request.task_key)
    if existing is not None:
        if (
            existing.route_digest != canonical.route_digest
            or existing.classification_digest != canonical.classification_digest
        ):
            raise TrialUnavailable("the task's original Work Contract changed")
        permitted = (
            policy.status == "active"
            and not state.stopped
            and request.entrypoint in policy.permitted_entrypoints
        )
        return AdmissionResult(
            state, existing.arm, "existing" if permitted else "existing_inactive",
        )

    if policy.status != "active":
        return AdmissionResult(state, None, "disabled")
    if request.entrypoint not in policy.permitted_entrypoints:
        return AdmissionResult(state, None, "unregistered_entrypoint")
    if state.stopped:
        return AdmissionResult(state, None, "stopped")
    if len(state.assignments) >= policy.max_assignments:
        return AdmissionResult(state, None, "closed")
    if len(state.assignments) >= policy.checkpoint_at and state.checkpoint_review_digest is None:
        return AdmissionResult(state, None, "checkpoint_due")

    classification = canonical.classification
    if classification.primary_object not in policy.eligible_primary_objects:
        return AdmissionResult(state, None, "ineligible_object")
    if classification.risk_triggers:
        return AdmissionResult(state, None, "risk_trigger")
    if set(classification.impacts) & set(policy.excluded_impacts):
        return AdmissionResult(state, None, "excluded_impact")

    first = sum(item.arm == "A" for item in state.assignments.values())
    second = len(state.assignments) - first
    arm: Literal["A", "B"] = "A" if first <= second else "B"
    next_state = CohortState.model_validate(
        {
            **state.model_dump(),
            "assignments": {
                **state.assignments,
                request.task_key: Admission(
                    arm=arm,
                    entrypoint=request.entrypoint,
                    candidate_version=policy.candidate_version,
                    route_digest=canonical.route_digest,
                    classification_digest=canonical.classification_digest,
                ),
            },
        }
    )
    return AdmissionResult(next_state, arm, "assigned")


class CohortStore(Protocol):
    """Protected shared store: read revision, then atomically swap one whole state."""

    def read(self) -> tuple[str, CohortState]: ...

    def compare_and_swap(self, revision: str, state: CohortState) -> bool: ...


def admit_with_cas(
    store: CohortStore, policy: TrialPolicy, request: AdmissionRequest
) -> AdmissionResult:
    """Retry CAS conflicts, but never dispatch B after an ambiguous store error."""
    for _ in range(8):
        revision, state = store.read()
        result = plan_admission(policy, state, request)
        if result.state == state:
            return result
        if store.compare_and_swap(revision, result.state):
            return result
    raise TrialUnavailable("cohort CAS contention; no candidate receipt")


def record_outcome(state: CohortState, task_key: str, event: OutcomeEvent) -> CohortState:
    """Append a coded event without erasing the initial group or earlier failures."""
    admission = state.assignments.get(task_key)
    if admission is None:
        raise TrialUnavailable("unknown trial task")
    for prior in admission.events:
        if prior.event_key == event.event_key:
            if prior == event:
                return state
            raise TrialUnavailable("conflicting outcome event identity")
    assignments = {
        **state.assignments,
        task_key: admission.model_copy(update={"events": (*admission.events, event)}),
    }
    return CohortState.model_validate({**state.model_dump(), "assignments": assignments})


def record_checkpoint(state: CohortState, review_digest: str) -> CohortState:
    """Require an independent broker to authenticate the review before calling."""
    if len(state.assignments) != 8 or state.checkpoint_review_digest is not None:
        raise TrialUnavailable("checkpoint requires exactly eight unreviewed assignments")
    return CohortState.model_validate(
        {**state.model_dump(), "checkpoint_review_digest": review_digest}
    )


def stop_cohort(state: CohortState) -> CohortState:
    """Propose a stop without deleting any assignments or outcome history."""
    return state.model_copy(update={"stopped": True})


class DecisionCard(TrialRecord):
    """An existing independently reviewed human decision, not approval."""

    review_route: Literal["human-review-required"]
    subject_digest: str = Field(pattern=_DIGEST_PATTERN)
    evidence_digest: str = Field(pattern=_DIGEST_PATTERN)
    question: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    main_tradeoff: str = Field(min_length=1)
    human_authority: str = Field(min_length=1)
    why_human: str = Field(min_length=1)
    if_declined: str = Field(min_length=1)
    deferred: str = Field(min_length=1)
    dissent: str | None = None
    evidence_refs: tuple[str, ...] = Field(min_length=1)


def render_decision_card(
    card: DecisionCard, *, subject_digest: str, evidence_digest: str
) -> str:
    """Render only complete, current evidence; never imply an approval occurred."""
    if card.subject_digest != subject_digest or card.evidence_digest != evidence_digest:
        raise TrialUnavailable("stale decision subject or evidence")
    sections = [
        f"**请决定：** {card.question}",
        f"**建议：** {card.recommendation}",
        f"**主要取舍：** {card.main_tradeoff}",
        f"**授权范围：** {card.human_authority}",
        f"**为什么需要你：** {card.why_human}",
        f"**若不批准：** {card.if_declined}",
        f"**暂不决定：** {card.deferred}",
    ]
    if card.dissent:
        sections.append(f"**不同意见：** {card.dissent}")
    sections.append(f"**依据：** {', '.join(card.evidence_refs)}")
    sections.append("**状态：** 待人明确决定；此卡不是批准记录。")
    return "\n".join(sections)
