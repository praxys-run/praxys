"""A protected cohort store must fail closed on stale or malformed writes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from threading import Lock
from types import SimpleNamespace

from azure.core import MatchConditions
from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
import pytest

from analysis.agent_decision_trial import (
    Admission,
    AdmissionRequest,
    CohortState,
    TrialPolicy,
    TrialUnavailable,
    OutcomeEvent,
    admit_with_cas,
    load_trial_policy,
    new_cohort,
    plan_admission,
    record_checkpoint,
    record_outcome,
    stop_cohort,
)
from analysis.agent_decision_trial_storage import AzureBlobCohortStore
from analysis.agentic_task_routing import TaskClassification, route_task


class FakeBlob:
    def __init__(self, state: CohortState | None) -> None:
        self._content = state.model_dump_json().encode() if state is not None else None
        self._version = 0
        self._lock = Lock()
        self.ambiguous_write = False
        self.ambiguous_precondition = False

    def download_blob(
        self, *, offset: int, length: int, max_concurrency: int
    ) -> SimpleNamespace:
        assert offset == 0
        assert max_concurrency == 1
        with self._lock:
            if self._content is None:
                raise ResourceNotFoundError("missing")
            content = self._content
            etag = f'"v{self._version}"'
        return SimpleNamespace(
            readall=lambda: content[:length], properties=SimpleNamespace(etag=etag)
        )

    def upload_blob(
        self,
        data: bytes,
        *,
        overwrite: bool,
        etag: str,
        match_condition: MatchConditions,
        content_settings: object,
        max_concurrency: int,
    ) -> None:
        assert overwrite is True
        assert match_condition == MatchConditions.IfNotModified
        assert content_settings.content_type == "application/json"
        assert max_concurrency == 1
        with self._lock:
            if etag != f'"v{self._version}"':
                raise ResourceModifiedError("precondition failed", status_code=412)
            self._content = data
            self._version += 1
        if self.ambiguous_write:
            raise OSError("lost write response")
        if self.ambiguous_precondition:
            raise ResourceModifiedError("retry was rejected", status_code=412)


def _policy() -> TrialPolicy:
    return TrialPolicy.model_validate({
        **load_trial_policy().model_dump(),
        "status": "active",
        "permitted_entrypoints": ("cloud",),
    })


def _request(number: int) -> AdmissionRequest:
    contract = route_task(TaskClassification(
        primary_object="repository-behavior",
        impacts=["repository-change"],
        risk_triggers=[],
    ))
    return AdmissionRequest(
        task_key="tsk_" + hashlib.sha256(str(number).encode()).hexdigest(),
        entrypoint="cloud",
        work_contract=contract,
    )


def test_blob_admits_and_round_trips_with_etag_cas() -> None:
    policy = _policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    first = admit_with_cas(store, policy, _request(1))
    assert first.reason == "assigned"
    assert first.arm == "A"
    revision, state = store.read()
    assert revision == '"v1"'
    assert state == first.state
    assert admit_with_cas(store, policy, _request(1)).reason == "existing"
    assert store.read()[0] == '"v1"'


def test_blob_conflicts_cannot_overwrite_new_assignments() -> None:
    policy = _policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    revision, state = store.read()
    first = admit_with_cas(store, policy, _request(1))
    second = admit_with_cas(store, policy, _request(2))
    assert first.arm == "A" and second.arm == "B"
    assert store.compare_and_swap(revision, state) is False
    assert len(store.read()[1].assignments) == 2


def test_blob_parallel_admissions_pause_at_eight() -> None:
    policy = _policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda number: admit_with_cas(store, policy, _request(number)), range(8)))
    assert len(store.read()[1].assignments) == 8
    assert {result.reason for result in results} == {"assigned"}
    assert admit_with_cas(store, policy, _request(9)).reason == "checkpoint_due"
    revision, state = store.read()
    assert store.compare_and_swap(revision, record_checkpoint(state, "sha256:" + "a" * 64))
    assert admit_with_cas(store, policy, _request(9)).reason == "assigned"


def test_blob_rejects_ambiguous_writes_without_candidate_receipts() -> None:
    policy = _policy()
    blob = FakeBlob(new_cohort(policy))
    store = AzureBlobCohortStore(blob, policy)
    blob.ambiguous_write = True
    with pytest.raises(OSError, match="lost write response"):
        admit_with_cas(store, policy, _request(1))
    assert len(store.read()[1].assignments) == 1
    assert admit_with_cas(store, policy, _request(1)).reason == "existing"


def test_blob_never_retries_a_precondition_failure_into_a_b_receipt() -> None:
    policy = _policy()
    blob = FakeBlob(new_cohort(policy))
    store = AzureBlobCohortStore(blob, policy)
    assert admit_with_cas(store, policy, _request(1)).arm == "A"
    blob.ambiguous_precondition = True
    with pytest.raises(TrialUnavailable, match="ambiguous"):
        admit_with_cas(store, policy, _request(2))
    assert store.read()[1].assignments[_request(2).task_key].arm == "B"


def test_blob_rejects_missing_corrupt_and_wrong_cohort_records() -> None:
    policy = _policy()
    with pytest.raises(TrialUnavailable, match="not been provisioned"):
        AzureBlobCohortStore(FakeBlob(None), policy).read()
    blob = FakeBlob(new_cohort(policy))
    blob._content = b"{bad-json"
    with pytest.raises(TrialUnavailable, match="invalid"):
        AzureBlobCohortStore(blob, policy).read()
    wrong_policy = TrialPolicy.model_validate({**policy.model_dump(), "cohort_id": "other-cohort"})
    with pytest.raises(TrialUnavailable, match="invalid"):
        AzureBlobCohortStore(FakeBlob(new_cohort(policy)), wrong_policy).read()
    oversized = FakeBlob(new_cohort(policy))
    oversized._content = b"x" * (1024 * 1024 + 1)
    with pytest.raises(TrialUnavailable, match="size limit"):
        AzureBlobCohortStore(oversized, policy).read()


def test_blob_refuses_direct_admission_under_disabled_policy() -> None:
    policy = load_trial_policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    revision, state = store.read()
    request = _request(1)
    forged = CohortState.model_validate({
        **state.model_dump(),
        "assignments": {
            request.task_key: Admission(
                arm="A",
                entrypoint="cloud",
                candidate_version=policy.candidate_version,
                route_digest=request.work_contract.route_digest,
                classification_digest=request.work_contract.classification_digest,
            ),
        },
    })
    with pytest.raises(TrialUnavailable, match="disabled policy"):
        store.compare_and_swap(revision, forged)


def test_blob_prevents_stopping_and_history_from_being_rolled_back() -> None:
    policy = _policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    first = admit_with_cas(store, policy, _request(1))
    admit_with_cas(store, policy, _request(2))
    revision, state = store.read()
    with pytest.raises(TrialUnavailable, match="cannot be removed"):
        store.compare_and_swap(revision, first.state)
    assert store.compare_and_swap(revision, stop_cohort(state))
    stopped_revision, stopped_state = store.read()
    with pytest.raises(TrialUnavailable, match="cannot resume"):
        store.compare_and_swap(
            stopped_revision, stopped_state.model_copy(update={"stopped": False})
        )


def test_blob_preserves_existing_outcome_history() -> None:
    policy = _policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    request = _request(1)
    admit_with_cas(store, policy, request)
    revision, state = store.read()
    failed = record_outcome(
        state,
        request.task_key,
        OutcomeEvent(event_key="evt_" + "a" * 64, kind="failed"),
    )
    assert store.compare_and_swap(revision, failed)
    next_revision, stored = store.read()
    admission = stored.assignments[request.task_key]
    rollback = CohortState.model_validate({
        **stored.model_dump(),
        "assignments": {
            request.task_key: admission.model_copy(update={"events": ()}),
        },
    })
    with pytest.raises(TrialUnavailable, match="outcome history cannot be changed"):
        store.compare_and_swap(next_revision, rollback)


def test_blob_rejects_combined_checkpoint_or_stop_and_admission() -> None:
    policy = _policy()
    store = AzureBlobCohortStore(FakeBlob(new_cohort(policy)), policy)
    for number in range(1, 9):
        assert admit_with_cas(store, policy, _request(number)).reason == "assigned"
    revision, state = store.read()
    request = _request(9)
    combined = CohortState.model_validate({
        **state.model_dump(),
        "checkpoint_review_digest": "sha256:" + "a" * 64,
        "assignments": {
            **state.assignments,
            request.task_key: Admission(
                arm="A",
                entrypoint="cloud",
                candidate_version=policy.candidate_version,
                route_digest=request.work_contract.route_digest,
                classification_digest=request.work_contract.classification_digest,
            ),
        },
    })
    with pytest.raises(TrialUnavailable, match="checkpoint review must be separate"):
        store.compare_and_swap(revision, combined)

    assert store.compare_and_swap(revision, record_checkpoint(state, "sha256:" + "a" * 64))
    checkpoint_revision, checkpoint_state = store.read()
    admitted = plan_admission(policy, checkpoint_state, request).state
    with pytest.raises(TrialUnavailable, match="stopping cannot admit"):
        store.compare_and_swap(checkpoint_revision, stop_cohort(admitted))
