"""Cooperative local bookkeeping; never an authentication or approval boundary."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import secrets
import subprocess
from typing import Callable, Literal

from pydantic import Field, model_validator

from analysis.agent_decision_trial import (
    AdmissionRequest, CohortState, DecisionCard, OutcomeEvent, TrialPolicy,
    TrialRecord, TrialUnavailable, _check_state, plan_admission, policy_digest,
    record_checkpoint, record_outcome, render_decision_card, stop_cohort,
)
from analysis.agent_decision_trial_local_storage import LocalSQLiteCohortStore
from analysis.agentic_task_routing import TaskRoute


DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config/agent-decision-card-cooperative.json"


class CooperativePolicy(TrialPolicy):
    """A separate cohort whose complete rules, including expiry, are pinned."""

    mode: Literal["cooperative-local"]
    expires_at: str

    @model_validator(mode="after")
    def local_boundary(self) -> "CooperativePolicy":
        if self.permitted_entrypoints != ("local",):
            raise ValueError("cooperative policy requires only local entry")
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            raise ValueError("expiry requires an absolute timezone")
        return self


def load_cooperative_policy(path: Path = DEFAULT_POLICY) -> CooperativePolicy:
    """Load only the explicitly separate cooperative policy."""
    return CooperativePolicy.model_validate_json(path.read_text(encoding="utf-8"))


def canonical_store_path(repository: Path, policy: CooperativePolicy) -> Path:
    """Resolve one ledger across worktrees without creating any files."""
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=True, capture_output=True, text=True,
    )
    return Path(result.stdout.strip()).resolve() / "praxys-decision-trial" / f"{policy.cohort_id}.sqlite3"


def new_task_key() -> str:
    """Create an opaque task identity; keep it through all resumes."""
    return "tsk_" + secrets.token_hex(32)


class ReviewedDecision(TrialRecord):
    """Caller-supplied independent review evidence, not authenticated authority."""

    card: DecisionCard
    subject_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evidence_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    review_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reviewer: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    proposer: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    executor: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")

    @model_validator(mode="after")
    def separate_reviewer(self) -> "ReviewedDecision":
        if self.reviewer in {self.proposer, self.executor}:
            raise ValueError("reviewer must be independent of proposer and executor")
        return self


class CooperativeTrial:
    """Atomic local transitions with conservative, baseline-only failure behavior."""

    def __init__(
        self, path: Path, policy: CooperativePolicy,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.policy = policy
        self.store = LocalSQLiteCohortStore(path, policy)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def initialize(self) -> dict[str, object]:
        """Explicitly provision once; never recreate on admission or status."""
        self.path.parent.mkdir(mode=0o700, parents=False, exist_ok=True)
        LocalSQLiteCohortStore.provision(
            self.path, self.policy.model_copy(update={"status": "disabled"})
        )
        return self.status()

    def _inactive(self, state: CohortState) -> str | None:
        if self.policy.status != "active":
            return "disabled"
        if state.stopped:
            return "stopped"
        expiry = datetime.fromisoformat(self.policy.expires_at.replace("Z", "+00:00"))
        if self.clock() >= expiry:
            return "expired"
        return None

    def status(self) -> dict[str, object]:
        """Report only observed coded counts; absence of observations is unknown."""
        _, state = self.store.read()
        arms: dict[str, object] = {}
        for arm in ("A", "B"):
            assignments = [item for item in state.assignments.values() if item.arm == arm]
            events = Counter(event.kind for item in assignments for event in item.events)
            arms[arm] = {
                "assigned": len(assignments), "events": dict(events),
                "completion_unknown": sum(
                    not any(event.kind in {"completed", "merged", "failed", "abandoned"}
                            for event in item.events) for item in assignments
                ),
                "exposure_unknown": sum(
                    not any(event.kind in {"card_displayed", "no_human_decision"}
                            for event in item.events) for item in assignments
                ),
            }
        return {
            "mode": self.policy.mode, "cohort_id": state.cohort_id,
            "policy_digest": policy_digest(self.policy), "expires_at": self.policy.expires_at,
            "reason": self._inactive(state) or (
                "closed" if len(state.assignments) == 16 else
                "checkpoint_due" if len(state.assignments) == 8
                and state.checkpoint_review_digest is None else "open"
            ),
            "arms": arms, "human_active_minutes": "unknown", "accurate_restatement": "unknown",
            "corrections": "unknown", "overrides": "unknown", "missed_escalations": "unknown",
            "unnecessary_escalations": "unknown", "adverse_outcomes": "unknown",
            "latency": "unknown", "cost": "unknown", "authority": "none",
        }

    def _update(self, transform: Callable[[CohortState], CohortState]) -> CohortState:
        for _ in range(8):
            revision, state = self.store.read()
            updated = transform(state)
            if updated == state or self.store.compare_and_swap(revision, updated):
                return updated
        raise TrialUnavailable("cohort contention; use baseline")

    def outcome(self, task_key: str, event: OutcomeEvent) -> dict[str, object]:
        """Keep coded outcomes even after stop or expiry; do not rewrite attribution."""
        if event.kind == "card_issued":
            raise TrialUnavailable("card issuance is recorded only by card")

        def append(state: CohortState) -> CohortState:
            admission = state.assignments.get(task_key)
            if event.kind == "card_displayed" and (
                admission is None or admission.arm != "B"
                or not any(prior.kind == "card_issued" for prior in admission.events)
            ):
                raise TrialUnavailable("display requires a previously issued B card")
            return record_outcome(state, task_key, event)

        state = self._update(append)
        return {"recorded": True, "original_arm": state.assignments[task_key].arm}

    def checkpoint(self, review_digest: str) -> dict[str, object]:
        """Record a reference after real independent checkpoint review has occurred."""
        self._update(lambda state: record_checkpoint(state, review_digest))
        return {"recorded": True, "authority": "none"}

    def stop(self) -> dict[str, object]:
        """Permanently stop future admissions and card checks, retaining all history."""
        self._update(stop_cohort)
        return {"stopped": True}

    def admit(self, task_key: str, contract: TaskRoute, *, resume: bool = False) -> dict[str, object]:
        """Reuse assignments; an unknown resume or drift never consumes a new slot."""
        request = AdmissionRequest(task_key=task_key, entrypoint="local", work_contract=contract)
        for _ in range(8):
            revision, state = self.store.read()
            original = state.assignments.get(task_key)
            reason = self._inactive(state)
            if resume and original is None:
                reason = "unknown_resume"
            if reason is None:
                try:
                    result = plan_admission(self.policy, state, request)
                except TrialUnavailable:
                    reason = "contract_mismatch"
                else:
                    reason = result.reason
                    if result.state != state and not self.store.compare_and_swap(revision, result.state):
                        continue
                    original = result.state.assignments.get(task_key)
            if original and any(event.kind == "baseline_fallback" for event in original.events):
                reason = "baseline_fallback"
            if original and reason not in {"assigned", "existing", "baseline_fallback"}:
                event = OutcomeEvent(
                    event_key="evt_" + hashlib.sha256((task_key + ":fallback").encode()).hexdigest(),
                    kind="baseline_fallback",
                )
                self._update(lambda current: record_outcome(current, task_key, event))
            return {
                "task_key": task_key, "original_arm": original.arm if original else None,
                "enrolled": original is not None, "reason": reason,
                "presentation": "candidate_eligible" if original and original.arm == "B"
                and reason in {"existing", "assigned"} else "baseline",
            }
        raise TrialUnavailable("cohort contention; use baseline")

    def card(self, task_key: str, contract: TaskRoute, review: ReviewedDecision) -> dict[str, object]:
        """Issue at most one card; emission is not evidence of human exposure."""
        result = self.admit(task_key, contract, resume=True)
        if result["presentation"] != "candidate_eligible":
            return {**result, "card": None}
        try:
            rendered = render_decision_card(
                review.card, subject_digest=review.subject_digest, evidence_digest=review.evidence_digest,
            )
        except TrialUnavailable:
            return {**result, "presentation": "baseline", "reason": "stale_evidence", "card": None}
        event = OutcomeEvent(
            event_key="evt_" + hashlib.sha256((task_key + ":card_issued").encode()).hexdigest(),
            kind="card_issued",
        )
        for _ in range(8):
            revision, state = self.store.read()
            _check_state(self.policy, state)
            reason = self._inactive(state)
            admission = state.assignments[task_key]
            if any(prior.kind == "baseline_fallback" for prior in admission.events):
                reason = "baseline_fallback"
            if reason or any(prior.kind == "card_issued" for prior in admission.events):
                return {**result, "presentation": "baseline", "reason": reason or "already_issued", "card": None}
            if self.store.compare_and_swap(revision, record_outcome(state, task_key, event)):
                return {**result, "card": rendered, "reason": "issued_display_unknown"}
        raise TrialUnavailable("card write unavailable; use baseline")
