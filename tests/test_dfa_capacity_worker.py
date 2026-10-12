"""Bounded failures in the capacity reactor's shared terminal/ingress path."""
import threading
import time
import sys
import json

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.test_activity_dfa import store, confirmed
from tests.dfa_capacity_worker import CapacityWorker, WorkerUnavailable
from tests.dfa_capacity_measurement import observe_acceptance
from db.models import ActivityDFARun as Run


def wait_for_exit(worker):
    worker.thread.join(timeout=5)
    assert not worker.thread.is_alive(), worker.evidence()


@pytest.mark.parametrize('exception', [True, False])
def test_unexpected_terminal_worker_stops_backoff_and_certification(store, monkeypatch, exception):
    factory, _ = store
    supervisor = factory.dfa_supervisor
    entered = threading.Event()
    release = threading.Event()
    def reactor():
        entered.set()
        assert release.wait(2)
        try:
            if exception:
                raise RuntimeError('SECRET_SENTINEL must never be retained')
        finally:
            supervisor.stop.set()
    monkeypatch.setattr(supervisor, 'run', reactor)
    errors = []
    worker = CapacityWorker(supervisor, errors)
    worker.start()
    assert entered.wait(2)
    threading.Timer(.02, release.set).start()
    receipt = worker.backoff(5)
    wait_for_exit(worker)
    assert receipt['interrupted'] and receipt['elapsed_seconds'] < 2
    assert not worker.ingress_allowed()
    calls=[]
    with pytest.raises(WorkerUnavailable): worker.guarded_ingress(lambda: calls.append('new_request'))
    assert calls == []
    assert errors[0]['class'] == ('RuntimeError' if exception else 'UnexpectedWorkerReturn')
    assert 'SECRET_SENTINEL' not in str(worker.evidence())
    with pytest.raises(AssertionError):
        worker.assert_certifiable()
    worker.close()
    assert any(e.get('issuer', {}).get('function') == 'reactor' for e in worker.events)


def test_real_reactor_exit_commit_error_retained(store, monkeypatch, tmp_path):
    factory, owner = store
    confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    actual = supervisor.record_exit
    code = actual.__func__.__code__
    class ExitCommitFailure(Session):
        def commit(self):
            if sys._getframe(1).f_code is code:
                raise RuntimeError('controlled_exit_commit_failure')
            return super().commit()
    supervisor.controls = sessionmaker(class_=ExitCommitFailure, **factory.kw)
    worker = CapacityWorker(supervisor, [])
    monkeypatch.setattr(supervisor, 'record_exit', lambda: worker.record_exit(actual))
    worker.start()
    worker.thread.join(timeout=10)
    try:
        assert not worker.thread.is_alive(), worker.evidence()
        assert worker.errors and worker.errors[0]['class'] == 'RuntimeError'
        assert worker.exit_attempts[0]['error']['class'] == 'RuntimeError'
        assert 'commit_ack_at' not in worker.exit_attempts[0]
        assert worker.failure_snapshot['physical_actor']['state'] == 'idle'
        assert not worker.ingress_allowed()
        with pytest.raises(AssertionError): worker.assert_certifiable()
    finally:
        worker.close()
        (tmp_path/'worker-terminal.json').write_text(json.dumps(worker.evidence(), indent=2))


def test_normal_requested_shutdown_and_stop_before_ingress(store, monkeypatch):
    factory, _ = store
    supervisor = factory.dfa_supervisor
    monkeypatch.setattr(supervisor, 'run', lambda: supervisor.stop.wait(2))
    worker = CapacityWorker(supervisor, [])
    worker.start()
    worker.close()
    assert not worker.ingress_allowed()
    worker.assert_certifiable()


def test_accepted_status_observed_despite_worker_failure(store, monkeypatch):
    factory, owner = store
    _, admitted = confirmed(factory, owner)
    with factory() as db:
        run = db.get(Run, admitted['id'])
        run.status = 'failed'
        run.error_code = 'execution_unavailable'
        db.commit()
        digest = run.input_digest
    supervisor = factory.dfa_supervisor
    release=threading.Event()
    def reactor():
        assert release.wait(2)
        try: raise RuntimeError('controlled_post_acceptance_error')
        finally: supervisor.stop.set()
    monkeypatch.setattr(supervisor, 'run', reactor)
    worker = CapacityWorker(supervisor, [])
    worker.start()
    def accepted_during_failure():
        release.set()
        wait_for_exit(worker)
        return admitted
    admitted=worker.guarded_ingress(accepted_during_failure)
    entry = {'outcome': 'accepted', 'readiness': {'actor': None}, 'eligibility': {'actor': None}}
    # The real observer records the existing accepted unit's actual failed SQL
    # status before classification; termination must not erase or resample it.
    observation = observe_acceptance(factory, owner, admitted, entry, digest,
        None, [], {}, time.monotonic()+1, worker.errors)
    assert entry['accepted_observation'] is observation
    assert observation['service'] == 'failed'
    assert observation['last_state']['status'] == 'failed'
    assert not observation['service_success']
    with pytest.raises(AssertionError): worker.assert_certifiable()
    worker.close()


def test_cleanup_error_kept_separate_from_primary_worker_error(store, monkeypatch):
    factory, _ = store
    supervisor = factory.dfa_supervisor
    def reactor(): raise ValueError('controlled_primary')
    monkeypatch.setattr(supervisor, 'run', reactor)
    worker = CapacityWorker(supervisor, [])
    worker.start()
    wait_for_exit(worker)
    monkeypatch.setattr(worker.thread, 'join', lambda timeout: (_ for _ in ()).throw(RuntimeError('cleanup')))
    worker.close()
    assert worker.errors[0]['class'] == 'ValueError'
    assert worker.cleanup_errors[0]['class'] == 'RuntimeError'
    with pytest.raises(AssertionError): worker.assert_certifiable()


def test_stop_before_first_ingress_cannot_certify(store, monkeypatch):
    factory, _ = store
    supervisor = factory.dfa_supervisor
    monkeypatch.setattr(supervisor, 'run', lambda: supervisor.stop.wait(2))
    worker = CapacityWorker(supervisor, [])
    supervisor.stop.set()
    worker.start()
    assert not worker.ingress_allowed()
    with pytest.raises(WorkerUnavailable): worker.guarded_ingress(lambda: pytest.fail('new ingress'))
    worker.close()
    with pytest.raises(AssertionError): worker.assert_certifiable()
