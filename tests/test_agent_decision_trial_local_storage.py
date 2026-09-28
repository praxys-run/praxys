"""The local trial ledger is atomic and refuses unsafe or ambiguous admission."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import sqlite3

import pytest

from analysis.agent_decision_trial import (
    AdmissionRequest,
    CohortState,
    OutcomeEvent,
    TrialPolicy,
    TrialUnavailable,
    admit_with_cas,
    load_trial_policy,
    record_checkpoint,
    record_outcome,
    stop_cohort,
)
from analysis.agent_decision_trial_local_storage import LocalSQLiteCohortStore
from analysis.agentic_task_routing import TaskClassification, route_task


def _policy(*, active: bool = False) -> TrialPolicy:
    return TrialPolicy.model_validate({
        **load_trial_policy().model_dump(),
        "status": "active" if active else "disabled",
        "permitted_entrypoints": ("paseo",),
    })


def _store(tmp_path: Path, *, active: bool = True) -> LocalSQLiteCohortStore:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "trial.sqlite3"
    LocalSQLiteCohortStore.provision(path, _policy())
    return LocalSQLiteCohortStore(path, _policy(active=active))


def _request(number: int, *, entrypoint: str = "paseo") -> AdmissionRequest:
    contract = route_task(TaskClassification(
        primary_object="repository-behavior",
        impacts=["repository-change"],
        risk_triggers=[],
    ))
    return AdmissionRequest(
        task_key="tsk_" + hashlib.sha256(f"local-task-{number}".encode()).hexdigest(),
        entrypoint=entrypoint,
        work_contract=contract,
    )


def test_local_store_requires_private_operator_provisioning(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(TrialUnavailable, match="directory must be private"):
        LocalSQLiteCohortStore.provision(public / "trial.sqlite3", _policy())
    with pytest.raises(TrialUnavailable, match="while disabled"):
        LocalSQLiteCohortStore.provision(public / "trial.sqlite3", _policy(active=True))

    store = _store(tmp_path, active=False)
    path = tmp_path / "private" / "trial.sqlite3"
    assert path.stat().st_mode & 0o777 == 0o600
    assert store.read()[0] == "0"
    assert admit_with_cas(store, _policy(), _request(1)).reason == "disabled"
    assert store.read()[1].assignments == {}
    with pytest.raises(TrialUnavailable, match="exclusively provisioned"):
        LocalSQLiteCohortStore.provision(path, _policy())


def test_local_store_reopens_as_one_shared_paseo_cohort(tmp_path: Path) -> None:
    store = _store(tmp_path)
    other = LocalSQLiteCohortStore(
        tmp_path / "private" / "trial.sqlite3", _policy(active=True)
    )
    first = admit_with_cas(store, _policy(active=True), _request(1))
    assert first.arm == "A"
    assert first.reason == "assigned"
    assert admit_with_cas(other, _policy(active=True), _request(1)).reason == "existing"
    second = admit_with_cas(other, _policy(active=True), _request(2))
    assert second.arm == "B"
    assert len(store.read()[1].assignments) == 2
    assert admit_with_cas(
        store, _policy(active=True), _request(3, entrypoint="local")
    ).reason == "unregistered_entrypoint"
    assert len(store.read()[1].assignments) == 2


def test_local_store_cas_conflicts_never_overwrite_an_assignment(tmp_path: Path) -> None:
    store = _store(tmp_path)
    policy = _policy(active=True)
    revision, original = store.read()
    with ThreadPoolExecutor(max_workers=4) as pool:
        attempts = [
            pool.submit(admit_with_cas, store, policy, _request(number))
            for number in range(1, 5)
        ]
        assert {attempt.result().reason for attempt in attempts} == {"assigned"}
    assert store.compare_and_swap(revision, original) is False
    state = store.read()[1]
    assert len(state.assignments) == 4
    arms = [state.assignments[_request(number).task_key].arm for number in range(1, 5)]
    assert arms.count("B") == 2


def test_local_store_checkpoint_cap_outcomes_and_stop(tmp_path: Path) -> None:
    store = _store(tmp_path)
    policy = _policy(active=True)
    for number in range(1, 9):
        assert admit_with_cas(store, policy, _request(number)).reason == "assigned"
    assert admit_with_cas(store, policy, _request(9)).reason == "checkpoint_due"
    revision, state = store.read()
    assert store.compare_and_swap(revision, record_checkpoint(state, "sha256:" + "a" * 64))
    for number in range(9, 17):
        assert admit_with_cas(store, policy, _request(number)).reason == "assigned"
    assert admit_with_cas(store, policy, _request(17)).reason == "closed"

    revision, state = store.read()
    outcome = OutcomeEvent(event_key="evt_" + "b" * 64, kind="no_pr")
    assert store.compare_and_swap(revision, record_outcome(state, _request(2).task_key, outcome))
    revision, state = store.read()
    assert store.compare_and_swap(revision, stop_cohort(state))
    assert store.read()[1].assignments[_request(2).task_key].events == (outcome,)
    assert admit_with_cas(store, policy, _request(2)).reason == "existing_inactive"

    revision, stopped = store.read()
    with pytest.raises(TrialUnavailable, match="cannot resume"):
        store.compare_and_swap(revision, stopped.model_copy(update={"stopped": False}))
    assert store.read()[1].stopped


def test_local_store_rejects_downgrade_corruption_and_unsafe_paths(tmp_path: Path) -> None:
    store = _store(tmp_path)
    policy = _policy(active=True)
    path = tmp_path / "private" / "trial.sqlite3"
    revision, state = store.read()
    assert admit_with_cas(store, policy, _request(1)).reason == "assigned"
    with pytest.raises(TrialUnavailable, match="cannot be removed"):
        store.compare_and_swap(store.read()[0], state)
    assert store.compare_and_swap(revision, state) is False

    link = tmp_path / "private" / "alias.sqlite3"
    link.symlink_to(path)
    with pytest.raises(TrialUnavailable, match="file must be private"):
        LocalSQLiteCohortStore(link, policy).read()
    alias = tmp_path / "linked-private"
    alias.symlink_to(path.parent, target_is_directory=True)
    with pytest.raises(TrialUnavailable, match="directory must be private"):
        LocalSQLiteCohortStore(alias / "trial.sqlite3", policy).read()
    hardlink = tmp_path / "private" / "hardlink.sqlite3"
    os.link(path, hardlink)
    with pytest.raises(TrialUnavailable, match="file must be private"):
        store.read()
    hardlink.unlink()
    path.chmod(0o644)
    with pytest.raises(TrialUnavailable, match="file must be private"):
        store.read()
    path.chmod(0o600)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE cohort SET state = ? WHERE id = 1", ("{invalid",))
    with pytest.raises(TrialUnavailable, match="record is invalid"):
        store.read()


def test_local_store_never_creates_missing_or_reused_database(tmp_path: Path) -> None:
    store = _store(tmp_path)
    path = tmp_path / "private" / "trial.sqlite3"
    missing = LocalSQLiteCohortStore(tmp_path / "private" / "other.sqlite3", _policy(active=True))
    with pytest.raises(TrialUnavailable, match="not been provisioned"):
        missing.read()
    assert not (tmp_path / "private" / "other.sqlite3").exists()
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM cohort")
    with pytest.raises(TrialUnavailable, match="record is invalid"):
        store.read()
