"""Real child exit stays independent of cancelled Python I/O cleanup."""
from copy import deepcopy
import json
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import activity_dfa as service
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run, ActivityDFASyncReceipt as Receipt
from tests.test_activity_dfa import store, confirmed
from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_dfa_supervisor_capacity import admission_attempt, PriorityEvidence
from tests.dfa_capacity_measurement import observed_requests, fresh_physical_eligibility, observe_acceptance, lifecycle_observations, _admission_binding_matches


def require_eof_acceptance(admitted, entry, result):
    """Accept real service only with its exact durable and acknowledged receipt.

    Retirement cause is deliberately independent of this service contract.
    Recheck the recorded transaction/response as well as the observer decision;
    completed service is retained even when any of that evidence is invalid.
    """
    assert result['service_success'],result
    assert entry['outcome']=='accepted',entry
    assert result.get('admission_receipt_valid') is True,result
    assert entry.get('acceptance_consistent') is True,entry
    assert _admission_binding_matches(result,admitted,entry),entry
    response=entry.get('accepted_response',{})
    durable=entry.get('after_durable',{})
    assert all(response.get(k)==admitted[k]==durable.get(k)
               for k in ('id','generation','admission_id')),entry




@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_cancelled_raw_load_cannot_launch_or_mutate_retried_generation(store, monkeypatch):
    from sync.rr_recording import RRRecordingReader
    factory, owner = store
    _, manual = confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    job = supervisor.acquire_job(); supervisor.active = job
    previous_actor = supervisor.lane.actor()
    entered = threading.Event(); release = threading.Event(); cancellation = threading.Event()
    actual_raw = RRRecordingReader.raw
    def delayed_raw(reader, ref):
        raw = actual_raw(reader, ref)
        entered.set(); assert release.wait(5)
        return raw
    monkeypatch.setattr(RRRecordingReader, 'raw', delayed_raw)
    import queue
    outputs = queue.Queue(maxsize=1)
    worker = threading.Thread(target=supervisor.work, args=(job, outputs, cancellation)); worker.start()
    try:
        assert entered.wait(3)
        with supervisor.physical_mutex:
            cancellation.set(); supervisor.lane.retire()
        supervisor.finish(job, 'failed_before_spawn', 'permission_expired')
        with factory() as db:
            accepted = service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
        release.set(); worker.join(3)
        assert not worker.is_alive()
        assert outputs.get_nowait()[0]=='failed_before_spawn'
        assert supervisor.lane.actor() == previous_actor
        with factory() as db:
            row = db.get(Run, manual['id'])
            assert row.generation==accepted['generation'] and row.status==row.progress=='queued'
            assert row.result is None
    finally:
        release.set(); worker.join(5); supervisor.lane.close()


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_late_actor_ack_cannot_overwrite_exit_or_replacement(store, monkeypatch):
    from sqlalchemy import event
    import queue
    factory, owner = store
    _, manual = confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    job = supervisor.acquire_job(); supervisor.active = job
    entered = threading.Event(); release = threading.Event(); cancellation = threading.Event()
    outputs = queue.Queue(maxsize=1)
    worker = threading.Thread(target=supervisor.work, args=(job, outputs, cancellation))
    engine = factory.kw['bind']
    def delay_actor_ack(connection, cursor, statement, parameters, context, executemany):
        if threading.current_thread() is worker and statement.startswith('UPDATE activity_dfa_control SET actor='):
            entered.set(); assert release.wait(8)
    event.listen(engine, 'before_cursor_execute', delay_actor_ack)
    try:
        worker.start(); assert entered.wait(5)
        first = supervisor.lane.actor()
        with supervisor.physical_mutex:
            cancellation.set(); supervisor.lane.retire()
        retired = supervisor.lane.actor()
        assert retired['state']=='idle' and retired['actor_token']==first['actor_token']
        supervisor.record_exit()
        supervisor.finish(job, 'failed', 'permission_expired')
        with factory() as db:
            accepted = service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
        with factory() as db: replacement = service.claim(db)
        service.execute(factory, *replacement)
        replacement_actor = supervisor.lane.actor()
        assert replacement_actor['actor_token']!=first['actor_token']
        assert replacement_actor['launch_at']>=retired['exit_observed_at']
        release.set(); worker.join(3)
        assert not worker.is_alive() and outputs.get_nowait()[0]=='failed'
        with factory() as db:
            assert db.get(Control, 1).actor==replacement_actor
            row = db.get(Run, manual['id'])
            assert row.generation==accepted['generation'] and row.status=='complete'
    finally:
        release.set(); worker.join(5)
        event.remove(engine, 'before_cursor_execute', delay_actor_ack)
        supervisor.lane.retire(); supervisor.lane.close()


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
@pytest.mark.parametrize('absence', ['json_null', 'sql_null'])
def test_absent_actor_ack_handles_both_database_null_encodings(store, absence):
    from sqlalchemy import null
    factory, owner = store
    _, manual = confirmed(factory, owner)
    with factory() as db:
        control = db.get(Control, 1)
        control.actor = None if absence=='json_null' else null()
        db.commit()
    with factory() as db: claimed = service.claim(db)
    service.execute(factory, *claimed)
    with factory() as db:
        row = db.get(Run, manual['id'])
        assert row.status=='complete', row.error_code
        actor = db.get(Control, 1).actor
        assert actor['state']=='idle'
        assert actor['binding']['generation']==row.generation


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_cleanup_capacity_denies_then_allows_neutral_queue(both_origins, monkeypatch):
    from datetime import datetime, timedelta
    from fastapi import HTTPException
    from tests.test_dfa_supervisor_capacity import admission_snapshot
    factory, owner = both_origins
    _, manual = confirmed(factory, owner)
    with factory() as db: claimed = service.claim(db)
    service.execute(factory, *claimed)
    with factory() as db:
        row = db.get(Run, manual['id']); row.status='failed'
        control = db.get(Control, 1); control.ready_until=datetime.utcnow()-timedelta(seconds=1)
        db.commit()
    supervisor = factory.dfa_supervisor
    supervisor.allowed=False; supervisor.permission_until=0.
    release = [threading.Event(), threading.Event()]
    cleanups = [threading.Thread(target=signal.wait, daemon=True) for signal in release]
    for thread in cleanups: thread.start()
    supervisor.cleanups=list(cleanups)
    errors=[]; launches=[]
    actual_launch = supervisor.lane.launch
    def launch(*args, **kwargs):
        actor, child = actual_launch(*args, **kwargs); launches.append(actor)
        return actor, child
    monkeypatch.setattr(supervisor.lane, 'launch', launch)
    def run():
        try: supervisor.run()
        except Exception as exc: errors.append(type(exc).__name__+':'+str(exc))
    reactor=threading.Thread(target=run); reactor.start()
    deadline=time.monotonic()+10
    try:
        while supervisor.control_observation['state']!='denied':
            assert time.monotonic()<deadline, errors
            time.sleep(.005)
        before=admission_snapshot(factory, manual['id'])
        with factory() as db, pytest.raises(HTTPException) as failure:
            service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
        assert (failure.value.status_code, failure.value.detail)==(503, 'DFA_CAPACITY_UNAVAILABLE')
        assert admission_snapshot(factory, manual['id'])==before
        assert not launches and not supervisor.allowed and supervisor.permission_until==0.
        release[0].set(); cleanups[0].join(1)
        while supervisor.control_observation['state']!='ready':
            assert time.monotonic()<deadline, errors
            time.sleep(.005)
        assert len(supervisor.cleanups)==1
        with factory() as db:
            accepted=service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
        while True:
            with factory() as db: complete=db.get(Run, manual['id']).status=='complete'
            if complete: break
            assert time.monotonic()<deadline, errors
            time.sleep(.01)
        assert len(launches)==1 and launches[0]['binding']['generation']==accepted['generation']
        assert not errors and cleanups[1].is_alive()
        with factory() as db:
            assert db.query(Run).filter_by(user_id=owner, origin='automatic').count()==0
            assert db.query(Receipt).filter_by(user_id=owner, disposition='pending').count()==0
    finally:
        for signal in release: signal.set()
        supervisor.stop.set(); reactor.join(5)
        for thread in cleanups: thread.join(1)
        assert not reactor.is_alive()
