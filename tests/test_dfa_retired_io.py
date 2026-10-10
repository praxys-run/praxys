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
@pytest.mark.parametrize('another_receipt', [False, True])
def test_manual_completes_while_retired_automatic_pipe_cleanup_lingers(both_origins, monkeypatch, another_receipt):
    factory, owner = both_origins
    _, manual = confirmed(factory, owner)
    with factory() as db: claimed = service.claim(db)
    service.execute(factory, *claimed)
    with factory() as db:
        row = db.get(Run, manual['id']); row.status = 'failed'; db.commit()
    complete_unit(factory, owner)
    supervisor = factory.dfa_supervisor
    supervisor.allowed = False; supervisor.permission_until = 0.
    url = factory.kw['bind'].url
    args = {'timeout': .1} if url.get_backend_name() == 'sqlite' else {
        'connect_timeout': 1, 'options': '-c statement_timeout=200 -c lock_timeout=200'}
    engine = create_engine(url, pool_size=2, max_overflow=0, pool_timeout=.1, connect_args=args)
    supervisor.controls = sessionmaker(bind=engine)
    producer = create_engine(url, pool_size=1, max_overflow=0, pool_timeout=.1,
                             connect_args={'timeout':.1} if url.get_backend_name()=='sqlite' else {'connect_timeout':1})
    if url.get_backend_name()=='sqlite':
        from db.session import _attach_sqlite_pragmas
        _attach_sqlite_pragmas(producer)
    supervisor.factory = sessionmaker(bind=producer)
    actual_popen = subprocess.Popen
    eof = threading.Event(); release = threading.Event(); cleanup_done = threading.Event()
    actors = []; errors = []; attempts = []; timeline = []
    ready_read, ready_write = os.pipe()
    second_receipt = None; receipt_reads = []; second_load = threading.Event()
    if another_receipt:
        # Queue both genuine receipts before live startup. Creating a new sync
        # transaction during admission would add an unrelated SQLite writer
        # contention cell, rather than isolate this scheduling boundary.
        with factory() as db: previous_receipts={row.id for row in db.query(Receipt).filter_by(user_id=owner)}
        complete_unit(factory, owner)
        with factory() as db:
            added=[row for row in db.query(Receipt).filter_by(user_id=owner, disposition='pending')
                   if row.id not in previous_receipts]
            assert len(added)==1 and added[0].run_id is None
            second_receipt=added[0].id
    from sync.rr_recording import RRRecordingReader
    actual_iter = RRRecordingReader.iter_recording
    def observe_receipt_load(reader, ref):
        caller = sys._getframe(1)
        if (second_receipt and caller.f_code.co_name=='admit_completion'
                and caller.f_locals.get('receipt_id')==second_receipt):
            receipt_reads.append({'at':time.monotonic(), 'receipt_id':second_receipt,
                                  'cleanup_released':release.is_set(), 'retained_cleanups':len(supervisor.cleanups)})
            second_load.set()
            # A forbidden early automatic load genuinely holds this reactor's
            # producer connection until cleanup is released. No fake renewal.
            assert release.wait(8)
        return actual_iter(reader, ref)
    monkeypatch.setattr(RRRecordingReader, 'iter_recording', observe_receipt_load)
    code = f'''import io,json,os,signal,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
raw=sys.stdin.buffer.readline(90*1024*1024+1)
payload=json.loads(raw)
if payload['origin']=='automatic':
    os.write({ready_write},b'A')
    while True:time.sleep(.01)
else:
    signal.signal(signal.SIGTERM,signal.SIG_DFL)
    sys.stdin=io.TextIOWrapper(io.BytesIO(raw))
    from api.dfa_worker import main
    main()
'''
    class DelayedEOF:
        def __init__(self, pipe): self.pipe = pipe
        def read(self, limit):
            data = self.pipe.read(limit)
            # Actual group termination has already closed its writer. Hold only
            # this Python continuation/private read handle; no numerical actor.
            timeline.append({'kind':'real_pipe_eof','at':time.monotonic(),
                             'owned_private_read_fd':self.pipe.fileno(),
                             'data_pool_checked_out':producer.pool.checkedout()})
            assert producer.pool.checkedout()==0
            eof.set()
            assert release.wait(8)
            self.pipe.close(); cleanup_done.set()
            return data
        def close(self): self.pipe.close()
    def popen(command, **kwargs):
        if command[-2:] == ['-m', 'api.dfa_worker']:
            command = [sys.executable, '-E', '-B', '-c', code]
            kwargs['pass_fds']=(*kwargs.get('pass_fds',()),ready_write)
        child = actual_popen(command, **kwargs)
        # Fixture setup already completed. First real-loop child is automatic.
        if not actors: child.stdout = DelayedEOF(child.stdout)
        return child
    monkeypatch.setattr(subprocess, 'Popen', popen)
    actual_record = supervisor.lane.record
    def record(actor):
        actual_record(actor)
        if actor['state']=='occupied': actors.append(dict(actor))
        timeline.append({'kind':actor['state'],'at':time.monotonic(),'actor_token':actor['actor_token']})
    monkeypatch.setattr(supervisor.lane, 'record', record)
    evidence = PriorityEvidence(supervisor, monkeypatch)
    transitions, availability = lifecycle_observations(supervisor, monkeypatch)
    requests = observed_requests(factory, supervisor=supervisor)
    def run():
        try: supervisor.run()
        except Exception as exc: errors.append(type(exc).__name__+':'+str(exc))
    thread = threading.Thread(target=run); thread.start()
    deadline = time.monotonic()+15
    try:
        while not actors:
            assert time.monotonic()<deadline, errors
            time.sleep(.01)
        # Occupied/PID publication precedes payload transfer. Wait for the
        # actual child to decode that payload, not a selected readiness pulse;
        # otherwise admission can cancel before the EOF boundary even exists.
        assert select.select([ready_read],[],[],3)[0], errors
        assert os.read(ready_read,1)==b'A'
        timeline.append({'kind':'automatic_payload_handshake','at':time.monotonic()})
        initial = actors[0]; startup_ack=evidence.startup_launch(initial)
        for attempt in range(3):
            eligibility = fresh_physical_eligibility(factory, owner, supervisor)
            admitted, entry = admission_attempt(requests, owner, manual['id'], manual['generation'], attempts,
                                              {'attempt':attempt,'eligibility':eligibility})
            if admitted: break
            time.sleep(.125)
        assert admitted, attempts
        with factory() as db: manual_input=db.get(Run,admitted['id']).input_digest
        # Fully observe this durable acceptance before assertions/classification
        # for the independently held real EOF continuation.
        result=observe_acceptance(factory,owner,admitted,entry,manual_input,evidence,
            transitions,availability,entry['before_monotonic']+5,errors,allow_existing_retirement=True)
        require_eof_acceptance(admitted,entry,result)
        assert eof.is_set() and not cleanup_done.is_set(),timeline
        retirement=next((r for r in evidence.retirements if r['actor_token']==initial['actor_token']),None)
        assert retirement and retirement['actor_snapshot']['binding']==initial['binding'],retirement
        assert retirement['actor_snapshot']['incarnation']==initial['incarnation'],retirement
        available=availability.get(initial['actor_token'])
        assert available is not None and retirement['exit_observed_at']<=available,retirement
        assert available-entry['before_monotonic']<=5,retirement
        assert result['manual_actor']['launch_at']>=available and not result['reuse_violations'],result
        # This cell proves service during physical post-exit cleanup, regardless
        # of its retirement cause. It is NOT a strict-priority positive and does
        # not turn unavailable commit/cause ordering into a race certificate.
        entry['cleanup_service_proof']={'actor_token':initial['actor_token'],
            'physical_exit':retirement['exit_observed_at'],'durable_availability':available,
            'manual_launch':result['manual_actor']['launch_at'],'priority_required':False,
            'causal_classification':result['classification']}
        if another_receipt:
            assert not second_load.is_set() and not receipt_reads
            with factory() as db:
                pending=db.get(Receipt, second_receipt)
                assert pending.disposition=='pending' and pending.run_id is None
        assert not errors
        release.set(); assert cleanup_done.wait(2)
        if another_receipt:
            while True:
                with factory() as db:
                    serviced=db.get(Receipt, second_receipt)
                    done=serviced.disposition=='unchanged' and serviced.run_id is not None
                if done: break
                assert time.monotonic()<deadline, errors
                time.sleep(.01)
            assert second_load.is_set() and receipt_reads
            assert all(read['cleanup_released'] and read['retained_cleanups']==0 for read in receipt_reads)
        # These negatives run AFTER actual cleanup/release checks and actual
        # completed service; they never change a DB receipt or sample a new
        # accepted request. The same EOF decision above must reject each copy.
        entry['deliberately_damaged_EOF_receipt_negatives']=[]
        defects=('missing_consistency','false_consistency','missing_response',
                 'response_id','response_generation','response_admission',
                 'missing_subject','subject_id','subject_generation','subject_admission',
                 'subject_epoch','subject_input','false_observer_receipt')
        for defect in defects:
            damaged=deepcopy(entry)
            if defect=='missing_consistency':damaged.pop('acceptance_consistent')
            elif defect=='false_consistency':damaged['acceptance_consistent']=False
            elif defect=='missing_response':damaged.pop('accepted_response')
            elif defect.startswith('response_'):
                key={'response_id':'id','response_generation':'generation','response_admission':'admission_id'}[defect]
                damaged['accepted_response'][key]='wrong'
            elif defect=='missing_subject':damaged.pop('transaction_subject')
            elif defect.startswith('subject_'):
                key={'subject_id':'id','subject_generation':'generation','subject_admission':'admission_id',
                     'subject_epoch':'execution_epoch','subject_input':'input_digest'}[defect]
                damaged['transaction_subject'][key]='wrong'
            negative=observe_acceptance(factory,owner,admitted,damaged,manual_input,evidence,
                transitions,availability,time.monotonic()+.5,errors,allow_existing_retirement=True)
            if defect=='false_observer_receipt':negative['admission_receipt_valid']=False
            # This is the previously unsafe case: authorized service succeeds
            # despite invalid evidence, so successful service alone cannot pass
            # THE actual EOF caller's acceptance predicate.
            assert negative['service_success'] and negative['authorization_current'],negative
            if defect=='false_consistency' or defect.startswith('subject_') or defect=='missing_subject':
                assert negative['classification']=='insufficient_admission_evidence',negative
            with pytest.raises(AssertionError):
                require_eof_acceptance(admitted,damaged,negative)
            entry['deliberately_damaged_EOF_receipt_negatives'].append({
                'defect':defect,'observation':negative,'EOF_decision':'rejected'})
        assert entry['accepted_observation'] is result and result['service_success']
    finally:
        release.set(); supervisor.stop.set(); thread.join(10); engine.dispose(); producer.dispose()
        os.close(ready_read); os.close(ready_write)
        assert not thread.is_alive()
        root = Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-retired-io-{url.get_backend_name()}-{time.time_ns()}.json').write_text(json.dumps({
            'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'source_hashes':{name:__import__('hashlib').sha256((root/name).read_bytes()).hexdigest()
                             for name in ('api/dfa_supervisor.py','api/dfa_physical.py','tests/test_dfa_retired_io.py','tests/dfa_capacity_measurement.py','tests/test_dfa_supervisor_capacity.py')},
            'injection':'bounded task-local delay after actual pipe EOF; not diagnosis of historical blocked phase',
            'producer_pool':{'size':1,'overflow':0,'checkout_seconds':.1},
            'control_pool':{'size':2,'overflow':0,'checkout_seconds':.1},
            'startup_ack':locals().get('startup_ack'),'another_receipt':another_receipt,'second_receipt':second_receipt,'receipt_reads':receipt_reads,
            'timeline':timeline,'attempts':attempts,'errors':errors,'transitions':transitions,
            'durable_availability':availability,'retirements':evidence.retirements,
            'renewal_decisions':evidence.renewal_decisions,'completed_renewals':evidence.renewals},indent=2))


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
def test_cleanup_capacity_denies_then_reserves_recovered_slot_for_manual(both_origins, monkeypatch):
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
    complete_unit(factory, owner)
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
            pending=db.query(Receipt).filter_by(user_id=owner, disposition='pending').one()
            assert pending.run_id is None
    finally:
        for signal in release: signal.set()
        supervisor.stop.set(); reactor.join(5)
        for thread in cleanups: thread.join(1)
        assert not reactor.is_alive()
