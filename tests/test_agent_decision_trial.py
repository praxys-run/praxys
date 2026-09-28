"""No-live-entry tests for the bounded, presentation-only agent trial."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from threading import Lock

import pytest
from pydantic import ValidationError

from analysis.agent_decision_trial import (
    AdmissionRequest,
    CohortState,
    DecisionCard,
    OutcomeEvent,
    TrialPolicy,
    TrialUnavailable,
    admit_with_cas,
    load_trial_policy,
    new_cohort,
    plan_admission,
    policy_digest,
    record_checkpoint,
    record_outcome,
    render_decision_card,
    stop_cohort,
)
from analysis.agentic_task_routing import TaskClassification, TaskRoute, route_task


ROOT = Path(__file__).resolve().parents[1]
DIGEST = "sha256:" + "a" * 64


def _active_policy() -> TrialPolicy:
    payload = load_trial_policy().model_dump()
    payload.update(status="active", permitted_entrypoints=("local",))
    return TrialPolicy.model_validate(payload)


def _work_contract(
    primary_object: str = "repository-behavior",
    impacts: list[str] | None = None,
    risks: list[str] | None = None,
) -> TaskRoute:
    return route_task(
        TaskClassification(
            primary_object=primary_object,
            impacts=impacts or ["repository-change"],
            risk_triggers=risks or [],
        )
    )


def _request(
    number: int,
    contract: TaskRoute | None = None,
    entrypoint: str = "local",
) -> AdmissionRequest:
    task_key = "tsk_" + hashlib.sha256(f"synthetic-{number}".encode()).hexdigest()
    return AdmissionRequest(
        task_key=task_key,
        entrypoint=entrypoint,
        work_contract=contract or _work_contract(),
    )


def _event(number: int, kind: str) -> OutcomeEvent:
    event_key = "evt_" + hashlib.sha256(f"synthetic-{number}".encode()).hexdigest()
    return OutcomeEvent(event_key=event_key, kind=kind)


class MemoryStore:
    def __init__(self, state: CohortState) -> None:
        self._state = state
        self._revision = 0
        self._lock = Lock()

    def read(self) -> tuple[str, CohortState]:
        with self._lock:
            return str(self._revision), self._state

    def compare_and_swap(self, revision: str, state: CohortState) -> bool:
        with self._lock:
            if revision != str(self._revision):
                return False
            self._state = state
            self._revision += 1
            return True


def test_checked_in_policy_cannot_enroll_tasks_or_enable_via_cli() -> None:
    policy = load_trial_policy()
    assert policy.status == "disabled"
    assert policy.permitted_entrypoints == ()
    assert plan_admission(policy, new_cohort(policy), _request(1)).reason == "disabled"
    status = subprocess.run(
        [sys.executable, "scripts/agent_decision_trial.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(status.stdout)["can_enroll"] is False
    assert json.loads(status.stdout)["policy_digest"] == policy_digest(policy)
    rejected = subprocess.run(
        [sys.executable, "scripts/agent_decision_trial.py", "--enable"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert rejected.returncode != 0


def test_policy_rejects_direct_enablement_corruption_and_multiple_entries(
    tmp_path: Path,
) -> None:
    policy = load_trial_policy()
    activated = policy.model_dump()
    activated.update(status="active", permitted_entrypoints=("local",))
    path = tmp_path / "trial.json"
    path.write_text(json.dumps(activated), encoding="utf-8")
    with pytest.raises(TrialUnavailable, match="no protected admission broker"):
        load_trial_policy(path)

    activated["permitted_entrypoints"] = ["local", "cloud"]
    with pytest.raises(ValidationError, match="one trusted entrypoint"):
        TrialPolicy.model_validate_json(json.dumps(activated))

    activated["status"] = "disabled"
    activated["permitted_entrypoints"] = []
    activated["excluded_impacts"] = ["made-up"]
    with pytest.raises(ValidationError, match="invalid excluded_impacts"):
        TrialPolicy.model_validate_json(json.dumps(activated))


def test_retries_keep_the_original_group_even_after_pausing_or_stopping() -> None:
    policy = _active_policy()
    request = _request(1)
    first = plan_admission(policy, new_cohort(policy), request)
    assert first.arm == "A"
    assert first.reason == "assigned"

    again = plan_admission(policy, first.state, request)
    assert again.reason == "existing"
    assert again.arm == first.arm
    assert again.state == first.state
    assert len(again.state.assignments) == 1

    disabled = TrialPolicy.model_validate({**policy.model_dump(), "status": "disabled"})
    assert policy_digest(disabled) == policy_digest(policy)
    inactive = plan_admission(disabled, first.state, request)
    assert inactive.reason == "existing_inactive"
    assert not plan_admission(disabled, first.state, _request(2)).arm

    stopped = stop_cohort(first.state)
    assert plan_admission(policy, stopped, request).arm == "A"
    assert plan_admission(policy, stopped, _request(2)).reason == "stopped"


@pytest.mark.parametrize(
    ("contract", "entrypoint", "expected_reason"),
    [
        (_work_contract("agent-system"), "local", "ineligible_object"),
        (_work_contract(risks=["security-or-privacy-boundary"]), "local", "risk_trigger"),
        (
            _work_contract(impacts=["repository-change", "trust-boundary"]),
            "local",
            "excluded_impact",
        ),
        (_work_contract(), "cloud", "unregistered_entrypoint"),
    ],
)
def test_ineligible_work_never_uses_the_cohort_quota(
    contract: TaskRoute, entrypoint: str, expected_reason: str
) -> None:
    policy = _active_policy()
    initial = new_cohort(policy)
    decision = plan_admission(
        policy, initial, _request(1, contract=contract, entrypoint=entrypoint)
    )
    assert decision.reason == expected_reason
    assert decision.state == initial
    assert decision.arm is None


def test_changed_or_forged_work_contract_fails_closed() -> None:
    policy = _active_policy()
    state = new_cohort(policy)
    canonical = _work_contract()
    forged = canonical.model_copy(update={"route_digest": DIGEST})
    with pytest.raises(TrialUnavailable, match="does not match"):
        plan_admission(policy, state, _request(1, contract=forged))
    admitted = plan_admission(policy, state, _request(1)).state
    different = _work_contract(impacts=["repository-change", "user-visible-experience"])
    with pytest.raises(TrialUnavailable, match="original Work Contract changed"):
        plan_admission(policy, admitted, _request(1, contract=different))
    with pytest.raises(TrialUnavailable, match="policy or version mismatch"):
        plan_admission(
            policy,
            admitted.model_copy(update={"policy_digest": DIGEST}),
            _request(2),
        )


def test_checkpoint_and_cap_are_based_on_distinct_tasks() -> None:
    policy = _active_policy()
    store = MemoryStore(new_cohort(policy))
    for number in range(1, 9):
        result = admit_with_cas(store, policy, _request(number))
        assert result.reason == "assigned"
    assert [item.arm for item in result.state.assignments.values()].count("A") == 4
    assert admit_with_cas(store, policy, _request(2)).reason == "existing"
    assert admit_with_cas(store, policy, _request(9)).reason == "checkpoint_due"
    with pytest.raises(TrialUnavailable, match="exactly eight"):
        record_checkpoint(new_cohort(policy), DIGEST)

    revision, state = store.read()
    assert store.compare_and_swap(revision, record_checkpoint(state, DIGEST))
    for number in range(9, 17):
        result = admit_with_cas(store, policy, _request(number))
        assert result.reason == "assigned"
    assert len(result.state.assignments) == 16
    assert [item.arm for item in result.state.assignments.values()].count("B") == 8
    assert admit_with_cas(store, policy, _request(17)).reason == "closed"
    assert admit_with_cas(store, policy, _request(10)).reason == "existing"


def test_parallel_admission_cannot_pass_the_checkpoint() -> None:
    policy = _active_policy()
    store = MemoryStore(new_cohort(policy))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda number: admit_with_cas(store, policy, _request(number)),
                range(1, 22),
            )
        )
    _, state = store.read()
    assert len(state.assignments) == 8
    assert sum(result.reason == "assigned" for result in results) == 8
    assert all(result.reason in {"assigned", "checkpoint_due"} for result in results)


def test_parallel_admission_cannot_pass_the_sixteen_task_cap() -> None:
    policy = _active_policy()
    store = MemoryStore(new_cohort(policy))
    for number in range(1, 9):
        admit_with_cas(store, policy, _request(number))
    revision, state = store.read()
    assert store.compare_and_swap(revision, record_checkpoint(state, DIGEST))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda number: admit_with_cas(store, policy, _request(number)),
                range(9, 30),
            )
        )
    _, state = store.read()
    assert len(state.assignments) == 16
    assert sum(result.reason == "assigned" for result in results) == 8
    assert all(result.reason in {"assigned", "closed"} for result in results)


def test_cas_conflict_retries_but_an_ambiguous_write_cannot_dispatch() -> None:
    policy = _active_policy()

    class ConflictingStore(MemoryStore):
        def __init__(self, state: CohortState) -> None:
            super().__init__(state)
            self.first_try = True

        def compare_and_swap(self, revision: str, state: CohortState) -> bool:
            if self.first_try:
                self.first_try = False
                return False
            return super().compare_and_swap(revision, state)

    conflicting = ConflictingStore(new_cohort(policy))
    assert admit_with_cas(conflicting, policy, _request(1)).reason == "assigned"
    assert len(conflicting.read()[1].assignments) == 1

    class AmbiguousStore(MemoryStore):
        def compare_and_swap(self, revision: str, state: CohortState) -> bool:
            assert super().compare_and_swap(revision, state)
            raise OSError("lost response")

    ambiguous = AmbiguousStore(new_cohort(policy))
    with pytest.raises(OSError, match="lost response"):
        admit_with_cas(ambiguous, policy, _request(2))
    assert len(ambiguous.read()[1].assignments) == 1
    assert admit_with_cas(ambiguous, policy, _request(2)).reason == "existing"


def test_invalid_state_and_missing_checkpoint_fail_closed() -> None:
    policy = _active_policy()
    state = new_cohort(policy)
    admission = plan_admission(policy, state, _request(1)).state.assignments[
        _request(1).task_key
    ]
    with pytest.raises(ValidationError, match="invalid opaque task key"):
        CohortState.model_validate(
            {**state.model_dump(), "assignments": {"raw-issue-number": admission}}
        )
    with pytest.raises(ValidationError, match="beyond eight"):
        CohortState.model_validate(
            {**state.model_dump(), "assignments": {
                _request(number).task_key: admission
                for number in range(1, 10)
            }}
        )
    with pytest.raises(ValidationError, match="assignment balance"):
        CohortState.model_validate(
            {**state.model_dump(), "assignments": {
                _request(1).task_key: admission,
                _request(2).task_key: admission,
            }}
        )


def test_no_pr_and_fallback_events_preserve_original_b_attribution() -> None:
    policy = _active_policy()
    first = plan_admission(policy, new_cohort(policy), _request(1)).state
    second = plan_admission(policy, first, _request(2)).state
    task_key = _request(2).task_key
    failed = record_outcome(second, task_key, _event(1, "failed"))
    fallback = record_outcome(failed, task_key, _event(2, "baseline_fallback"))
    final = record_outcome(fallback, task_key, _event(3, "no_pr"))
    assert final.assignments[task_key].arm == "B"
    assert [event.kind for event in final.assignments[task_key].events] == [
        "failed", "baseline_fallback", "no_pr"
    ]
    assert record_outcome(final, task_key, _event(3, "no_pr")) == final
    with pytest.raises(TrialUnavailable, match="conflicting outcome"):
        record_outcome(final, task_key, _event(3, "abandoned"))
    with pytest.raises(TrialUnavailable, match="unknown trial task"):
        record_outcome(final, _request(19).task_key, _event(4, "no_pr"))
    with pytest.raises(ValidationError, match="require a head-bound"):
        OutcomeEvent(event_key=_event(5, "failed").event_key, kind="merged")


def test_decision_card_requires_current_human_review_and_complete_fields() -> None:
    card = DecisionCard(
        review_route="human-review-required",
        subject_digest=DIGEST,
        evidence_digest=DIGEST,
        question="是否批准本次低风险展示调整？",
        recommendation="先维持默认关闭",
        main_tradeoff="更易读，但必须保留完整证据",
        human_authority="只批准指定版本的展示",
        why_human="当前政策不授权代理自批",
        if_declined="继续现行流程",
        deferred="减少审查角色",
        dissent="质量审查发现一处疑点",
        evidence_refs=("docs/dev/agentic-operating-model.md",),
    )
    rendered = render_decision_card(card, subject_digest=DIGEST, evidence_digest=DIGEST)
    assert "质量审查发现一处疑点" in rendered
    assert "此卡不是批准记录" in rendered
    with pytest.raises(TrialUnavailable, match="stale"):
        render_decision_card(card, subject_digest="sha256:" + "b" * 64, evidence_digest=DIGEST)
    with pytest.raises(ValidationError, match="human-review-required"):
        DecisionCard.model_validate({**card.model_dump(), "review_route": "blocked"})
    with pytest.raises(ValidationError, match="main_tradeoff"):
        DecisionCard.model_validate(
            {
                key: value
                for key, value in card.model_dump().items()
                if key != "main_tradeoff"
            }
        )
    for field_name in (
        "question", "recommendation", "main_tradeoff", "human_authority",
        "why_human", "if_declined", "deferred", "dissent",
    ):
        with pytest.raises(ValidationError, match="blank decision-card field"):
            DecisionCard.model_validate({**card.model_dump(), field_name: " \t "})
    for references in (("",), ("docs/dev/agentic-operating-model.md", "  ")):
        with pytest.raises(ValidationError, match="blank evidence reference"):
            DecisionCard.model_validate({**card.model_dump(), "evidence_refs": references})
