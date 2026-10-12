"""Bounded failures in the capacity reactor's shared terminal/ingress path."""
import threading
import time
import sys
import json
from copy import deepcopy

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.test_activity_dfa import store, confirmed
from tests.dfa_capacity_worker import CapacityWorker, WorkerUnavailable
from tests.dfa_capacity_measurement import observe_acceptance
from db.models import ActivityDFARun as Run, ActivityDFAControl as Control


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
    _, admitted = confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    setup_actor = deepcopy(supervisor.lane.actor())
    actual = supervisor.record_exit
    exit_code = actual.__func__.__code__
    work_code = supervisor.work.__func__.__code__
    acknowledged = threading.Event()
    failure_ready = threading.Event()
    backoff_started = threading.Event()
    target = {}
    injected = []
    renewal_threads = []
    actual_renew = supervisor.renew
    def renew():
        renewal_threads.append(threading.current_thread())
        actual_renew()
    monkeypatch.setattr(supervisor, 'renew', renew)

    def same_actor(a, b):
        return (all(a.get(k) == b.get(k) for k in ('actor_token', 'incarnation', 'binding'))
                and all(a.get('identity', {}).get(k) == b.get('identity', {}).get(k)
                        for k in ('pgid', 'pid', 'start')))

    class ExitCommitFailure(Session):
        def commit(self):
            caller = sys._getframe(1)
            physical = supervisor.lane.actor()
            if caller.f_code is exit_code and target and same_actor(physical, target['actor']):
                # This pre-flush read observes the independently committed actor,
                # not record_exit's locally changed ORM projection.
                with factory() as db:
                    committed = deepcopy(db.get(Control, 1).actor)
                assert physical['state'] == 'idle'
                assert committed['state'] == 'occupied' and same_actor(committed, target['actor'])
                assert physical['exit_observed_at'] >= target['ack_at']
                injected.append({'at': time.monotonic(), 'physical': deepcopy(physical),
                                 'sql_actor': committed, 'acknowledged': deepcopy(target)})
                failure_ready.set()
                assert backoff_started.wait(2)
                raise RuntimeError('controlled_midrun_exit_commit_failure')
            result = super().commit()
            if caller.f_code is work_code:
                actor = deepcopy(caller.f_locals['actor'])
                assert actor['state'] == 'occupied'
                assert actor['actor_token'] != setup_actor['actor_token']
                with factory() as db:
                    committed = deepcopy(db.get(Control, 1).actor)
                assert committed['state'] == 'occupied' and same_actor(committed, actor)
                target.update(actor=actor, ack_at=time.monotonic())
                acknowledged.set()
            return result

    supervisor.controls = sessionmaker(class_=ExitCommitFailure, **factory.kw)
    # Setup permission must not stand in for a current completed renewal.
    supervisor.allowed = False
    supervisor.permission_until = 0.
    worker = CapacityWorker(supervisor, [])
    monkeypatch.setattr(supervisor, 'record_exit', lambda: worker.record_exit(actual))
    observation = None
    backoff = None
    requests = []
    worker.start()
    try:
        assert acknowledged.wait(5), worker.evidence()
        assert failure_ready.wait(5), worker.evidence()
        backoff_started.set()
        backoff = worker.backoff(5)
        wait_for_exit(worker)
        assert backoff['interrupted'] and backoff['elapsed_seconds'] < 2
        assert not backoff['ingress_allowed_after']
        with pytest.raises(WorkerUnavailable):
            worker.guarded_ingress(lambda: requests.append('subsequent_ingress'))
        assert requests == []
        assert len(injected) == 1
        failed = [e for e in worker.exit_attempts if 'error' in e]
        assert len(failed) == 1 and 'commit_ack_at' not in failed[0]
        assert same_actor(failed[0]['physical_actor'], target['actor'])
        assert worker.errors[0]['class'] == 'RuntimeError'
        snapshot = worker.failure_snapshot
        assert snapshot['physical_actor']['state'] == 'idle'
        assert snapshot['sql_control']['actor']['state'] == 'occupied'
        assert same_actor(snapshot['physical_actor'], snapshot['sql_control']['actor'])
        stops = [e for e in worker.events if e['event'] == 'stop_set']
        assert len(stops) == 1
        assert stops[0]['issuer']['file'] == 'dfa_supervisor.py'
        assert stops[0]['issuer']['function'] == 'run'
        assert injected[0]['at'] <= stops[0]['at']
        assert not any(e['event'] == 'cleanup_requested' for e in worker.events)
        # The real API already admitted this manual unit. Retain its actual
        # running/terminal SQL state even though the reactor can no longer finish.
        with factory() as db:
            run = db.get(Run, admitted['id'])
            digest = run.input_digest
        entry = {'outcome': 'accepted', 'readiness': {'actor': None}, 'eligibility': {'actor': None}}
        observation = observe_acceptance(factory, owner, admitted, entry, digest,
            None, [], {}, time.monotonic()+.25, worker.errors)
        assert entry['accepted_observation'] is observation
        assert not observation['service_success']
        assert observation['last_state']['status'] in ('running', 'failed', 'cancelled', 'unavailable')
        with pytest.raises(AssertionError): worker.assert_certifiable()
    finally:
        backoff_started.set()
        worker.close()
        for thread in renewal_threads: thread.join(timeout=3)
        joined = all(not thread.is_alive() for thread in renewal_threads)
        supervisor.controls.kw['bind'].dispose()
        factory.kw['bind'].dispose()
        (tmp_path/'worker-terminal.json').write_text(json.dumps({
            'worker': worker.evidence(), 'setup_actor': setup_actor,
            'target': target, 'injected': injected, 'backoff': backoff,
            'subsequent_ingress': requests, 'accepted_observation': observation,
            'renewal_threads_joined': joined}, indent=2))
        assert joined


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
