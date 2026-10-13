"""Real queued acquisition deferral; no forged permission or extra recovery."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import queue
import threading
import time

import pytest
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import Session, sessionmaker
from api import activity_dfa as service
from db.models import ActivityDFARun as Run, ActivityDFAControl as Control, GarminFitSnapshot
from tests.test_activity_dfa import store
from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_dfa_supervisor_capacity import PriorityEvidence
from tests.dfa_capacity_measurement import lifecycle_observations
from tests.dfa_boundary_evidence import StartupEvidence, RenewalDecision, safe_binding, boundary_junit
from tests.dfa_attempt_evidence import assert_attempt_ledger
from api.dfa_supervisor import SAFE_FAILURES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.git/pr871-acquisition-freshness-r1'


def wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, 'bounded observation did not arrive'
        time.sleep(.005)


class Cell:
    def __init__(self, factory, owner, monkeypatch, name):
        self.factory, self.owner, self.name = factory, owner, name
        self.sup = factory.dfa_supervisor
        complete_unit(factory, owner)
        self.sup.admit_completion()
        with factory() as db:
            self.id = db.query(Run).filter_by(user_id=owner, origin='automatic').one().id
        backend = factory.kw['bind'].dialect.name
        args = {'timeout': .1} if backend == 'sqlite' else {'connect_timeout': 1, 'options': '-c statement_timeout=200 -c lock_timeout=200'}
        self.engine = create_engine(factory.kw['bind'].url, pool_size=2, max_overflow=0, pool_timeout=.1, connect_args=args)
        self.sup.controls = sessionmaker(bind=self.engine)
        self.proof = PriorityEvidence(self.sup, monkeypatch)
        self.actors, self.availability = lifecycle_observations(self.sup, monkeypatch)
        self.events, self.threads, self.errors = [], [], []
        self.diagnostic=StartupEvidence(self.sup,monkeypatch)
        self.diagnostic.synchronize_acquisition=False
        self.attempts=[]
        self.first_execution_denial=False
        self.fault_armed_at=self.fault_started=None
        self.fault_injected=False
        self.fault_target=None
        self.fault_decision=RenewalDecision(self.sup,monkeypatch)
        self.install_attempt_observers(monkeypatch)
        actual = self.sup.renew
        def renew():
            self.threads.append(threading.current_thread())
            try: actual()
            except Exception as exc: self.errors.append(type(exc).__name__)
        monkeypatch.setattr(self.sup, 'renew', renew)
        self.backend = backend
        self.outcome = 'failed'
        self.before = self.snapshot()
        self.diagnostic.note('automatic_admitted_entry',job=safe_binding(self.before))

    def safe_state(self):
        return {k:v for k,v in self.snapshot().items() if k!='id'}

    def install_attempt_observers(self, monkeypatch):
        cell=self;sup=self.sup
        actual_finish=sup.finish;actual_bound=sup._bound;actual_current=service._current
        actual_work=sup.work;work_code=actual_work.__func__.__code__;renew_code=sup.renew.__func__.__code__
        run_code=sup.run.__func__.__code__
        def current(db,run):
            result=actual_current(db,run)
            cell.diagnostic.note('acquisition_validation',current=result,
                job=safe_binding({'id':run.id,'generation':run.generation,'epoch':run.execution_epoch,
                                  'input':run.input_digest,'origin':run.origin,'phase':run.phase}))
            return result
        monkeypatch.setattr(service,'_current',current)
        def claim_observed(job,started):
            assert job['id']==cell.id, 'claim belongs to another unit'
            state=cell.safe_state();binding=safe_binding(job)
            validations=[e for e in cell.diagnostic.events if e['at']>=started]
            current=any(e['event']=='acquisition_validation' and e['current'] and e['job']==binding for e in validations)
            mode=next((e['mode'] for e in reversed(validations) if e['event']=='account_mode_validation'),None)
            claim={'at':time.monotonic(),'job':binding,'state':state,'current':current,'mode':mode}
            cell.attempts.append({'claim':claim,'occupied_ack':None,'finish':None,'finish_ack':None})
            cell.diagnostic.note('attempt_claim',**claim)
        cell.diagnostic.claim_observer=claim_observed
        class Controls(sup.controls.class_):
            def commit(session):
                caller=sys._getframe(1)
                result=super().commit()
                if caller.f_code is work_code:
                    actor=deepcopy(caller.f_locals['actor']);entry=cell.attempts[-1]
                    entry['occupied_ack']={'at':time.monotonic(),'actor':safe_binding(actor)}
                    cell.diagnostic.note('attempt_occupied_ack',**entry['occupied_ack'])
                    if cell.first_execution_denial and len(cell.attempts)==1:
                        cell.fault_armed_at=time.monotonic()
                if (caller.f_code is renew_code and cell.fault_started==caller.f_locals['started']
                        and cell.fault_target and cell.fault_target['matched']):
                    active=safe_binding(caller.f_locals['active']);actor=safe_binding(sup.lane.actor())
                    # Do not qualify a later/global renewal after the target retired.
                    if active==cell.fault_target['job'] and actor==cell.fault_target['actor']:
                        cell.fault_injected=True
                        cell.diagnostic.note('scheduling_fault_applied',delay_seconds=.30,
                            job=active,actor=actor,cycle_started=cell.fault_started)
                        time.sleep(.30)
                    else:cell.diagnostic.note('setup_failed',code='occupied_target_lost_before_control_ack')  # Real ACK delay, not a replaced clock or lease.
                return result
        sup.controls=sessionmaker(class_=Controls,**sup.controls.kw)
        def bound(db):
            caller=sys._getframe(1);row=actual_bound(db)
            if (caller.f_code is renew_code and cell.fault_armed_at is not None and cell.fault_started is None
                    and caller.f_locals['started']>=cell.fault_armed_at):
                # Pin the first eligible cycle even on a mismatch: never search
                # for a later favourable actor, epoch, phase or permission pulse.
                cell.fault_started=caller.f_locals['started']
                job=safe_binding(caller.f_locals['active']);actor=safe_binding(sup.lane.actor())
                expected=cell.attempts[0]
                matched=bool(row and len(cell.attempts)==1 and job==expected['claim']['job']
                    and actor==expected['occupied_ack']['actor'] and actor['state']=='occupied'
                    and safe_binding(row.actor)==actor and row.incarnation==sup.identity)
                cell.fault_target={'matched':matched,'job':job,'actor':actor,'cycle_started':cell.fault_started}
                if matched:cell.fault_decision.arm()
                else:cell.diagnostic.note('setup_failed',code='first_occupied_cycle_binding_lost')
            return row
        monkeypatch.setattr(sup,'_bound',bound)
        def work(job, outputs, cancellation=None):
            class Delivered:
                def put(_, value):
                    if cell.first_execution_denial and len(cell.attempts)==1 and value[0]=='output':
                        # Hold only delivery of the genuine numerical result in the fault
                        # case. Renewal continues; its original clocks decide retirement.
                        cell.diagnostic.note('result_delivery_boundary',status=value[0])
                        assert cell.fault_decision.event.wait(2), cell.diagnostic.compact()
                        with sup.lock:assert sup.allowed is False
                    outputs.put(value)
            actual_work(job,Delivered(),cancellation)
        monkeypatch.setattr(sup,'work',work)
        def finish(job,status,value):
            if not cell.attempts:return actual_finish(job,status,value)
            entry=cell.attempts[-1];pending=sup.pending;actor=sup.lane.actor()
            frame=sys._getframe(1)
            for _ in range(4):
                if frame.f_code is run_code or frame.f_back is None:break
                frame=frame.f_back
            trigger=None
            if frame.f_code is run_code:
                trigger={'expired':frame.f_locals['expired'],'timed_out':frame.f_locals['timed_out'],
                    'decision':StartupEvidence.decision(frame.f_locals['decision']),
                    'actor':safe_binding(frame.f_locals['actor_before'])}
            reason=value if isinstance(value,str) and value in SAFE_FAILURES|{'mode_changed','mode_unavailable','restart_interrupted'} else None
            chosen=json.loads(pending.value_json) if pending else None
            entry['finish']={'at':time.monotonic(),'job':safe_binding(job),'status':status,'reason':reason,
                'pending_status':pending.status if pending else None,'pending_reason':chosen if isinstance(chosen,str) and chosen==reason else None,
                'pending_actor':safe_binding(json.loads(pending.actor_json)) if pending else None,
                'pending_job':safe_binding(json.loads(pending.job_json)) if pending else None,
                'cancelled':pending.cancellation.is_set() if pending else None,'actor':safe_binding(actor),
                'exit_ack_at':cell.availability.get(actor['actor_token']) if actor else None,
                'before':cell.safe_state(),'trigger':trigger,'current':None,'mode':None}
            cell.diagnostic.note('attempt_finish',**entry['finish'])
            began=time.monotonic();actual_finish(job,status,value)
            validations=[e for e in cell.diagnostic.events if e['at']>=began]
            entry['finish']['current']=any(e['event']=='execution_validation' and e['current'] for e in validations)
            entry['finish']['mode']=next((e['mode'] for e in reversed(validations) if e['event']=='account_mode_validation'),None)
            entry['finish_ack']={'at':time.monotonic(),'after':cell.safe_state()}
            cell.diagnostic.note('attempt_finish_ack',**entry['finish_ack'])
        monkeypatch.setattr(sup,'finish',finish)

    def record(self, kind, **fields):
        self.events.append({'kind': kind, 'at': time.monotonic(), **fields})

    def snapshot(self):
        with self.factory() as db:
            run = db.get(Run, self.id)
            if run is None: return {'status': 'erased'}
            return {key: getattr(run, key) for key in ('id','origin','phase','status','progress','generation','recoveries','error_code','execution_epoch','input_digest')} | {
                'lease_token_present': run.lease_token is not None, 'lease_until': str(run.lease_until) if run.lease_until else None,
                'result_present': run.result is not None,
                'lease_token_hash':hashlib.sha256(run.lease_token.encode()).hexdigest() if run.lease_token else None}

    def start_renew(self):
        self.sup.stop.clear()
        thread = threading.Thread(target=self.sup.renew, name='dfa-control')
        self.diagnostic.renewal.arm()
        thread.start()
        self.diagnostic.renewal.wait()
        self.record('genuine_completed_renewal', receipt=deepcopy(self.proof.renewals[-1]))
        return thread

    def stop_renew(self):
        self.sup.stop.set()
        for thread in self.threads: thread.join(3)
        assert all(not thread.is_alive() for thread in self.threads)

    def denial_since(self, started):
        return next((d for d in self.proof.renewal_decisions if d['at'] >= started
                     and d['sqlite_errorcode'] == 5 and d['allowed'] is False), None)

    def complete_same_unit(self):
        # The negative phase's owned renewal loop is terminated, not parked.
        # Restart the actual reactor: it must obtain fresh completed checks.
        self.stop_renew()
        self.diagnostic.synchronize_acquisition=True
        self.diagnostic.renew_each_acquisition=True
        self.diagnostic.used=False
        self.sup.stop.clear()
        def run():
            try: self.sup.run()
            except Exception as exc: self.errors.append(type(exc).__name__)
        reactor = threading.Thread(target=run, name='acquisition-reactor')
        self.threads.append(reactor);reactor.start()
        wait_for(lambda: self.snapshot()['status'] in ('complete','failed','cancelled'), 15)
        assert self.snapshot()['status'] == 'complete', self.snapshot()
        with self.factory() as db:
            view = service.read_run(db, self.owner, '123', self.id, 0, 120)
            assert view['freshness'] == 'current' and view['summary']['valid_windows'] > 0
            actor = db.get(Control, 1).actor
        assert actor['state'] == 'idle' and actor['actor_token'] in self.availability
        recovered=assert_attempt_ledger(self.attempts,self.attempts[0]['claim']['job'])
        assert self.snapshot()['recoveries']==recovered
        launched = next(a for a in self.actors if a.get('state') == 'occupied')
        assert launched['process_start_observed_at'] >= launched['launch_at']
        denials=[e['decision']['at'] for e in self.events if e['kind']=='actual_control_busy_denial']
        if denials:assert any(r['completed_at']>denials[0] and r['permission_granted_at']<=launched['launch_at'] for r in self.proof.renewals)
        assert self.availability[actor['actor_token']] >= actor['exit_observed_at']
        self.record('same_queued_unit_authorized_complete', state=self.snapshot(), actor=actor)

    def close(self):
        self.sup.stop.set()
        for thread in list(self.threads): thread.join(10)
        joined = all(not thread.is_alive() for thread in self.threads)
        OUT.mkdir(exist_ok=True)
        (OUT / f'{self.name}-{self.backend}-{time.time_ns()}.json').write_text(json.dumps({
            'outcome': self.outcome, 'case': self.name, 'backend': self.backend,
            'invocation_head': __import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'supervisor_source_sha256': hashlib.sha256((ROOT/'api/dfa_supervisor.py').read_bytes()).hexdigest(),
            'before': self.before, 'after': self.snapshot(), 'events': self.events,
            'renewal_decisions': self.proof.renewal_decisions, 'completed_renewals': self.proof.renewals,
            'actors': self.actors, 'availability': self.availability,
            'errors': self.errors, 'all_owned_threads_joined': joined, 'attempts':self.attempts,
            'scope': 'deterministic acquisition test; no capacity certificate; owned renewal phase stop/join and real reactor restart disclosed'}, indent=2))
        # Preserve failure evidence before cleanup assertions can interrupt it.
        assert joined, self.errors
        assert not self.errors
        self.engine.dispose()


@pytest.fixture
def cell(both_origins, monkeypatch, request):
    factory, owner = both_origins
    value = Cell(factory, owner, monkeypatch, request.node.name.split('[')[0])
    try: yield value
    except BaseException as exc:
        value.diagnostic.error(exc);raise
    finally:
        try:value.close()
        except BaseException as exc:
            value.diagnostic.error(exc,cleanup=True);raise
        finally:
            value.diagnostic.emit(alive=any(t.is_alive() for t in value.threads))
            request.node.user_properties.append(('dfa_attempts',json.dumps(value.attempts,separators=(',',':'))))


@pytest.mark.parametrize('store', ['sqlite'], indirect=True)
def test_real_busy_denial_defers_before_claim_and_same_unit_completes(cell, monkeypatch):
    cell.start_renew()
    validated, release = threading.Event(), threading.Event()
    actual = service._current
    def current(db, run):
        result = actual(db, run)
        if threading.current_thread().name.startswith('acquisition-held') and run.id == cell.id:
            assert result
            cell.record('post_real_current_writer_held', permission_until=cell.sup.permission_until)
            validated.set();assert release.wait(5)
        return result
    monkeypatch.setattr(service, '_current', current)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='acquisition-held') as executor:
        attempt = executor.submit(cell.sup.acquire_job)
        try:
            assert validated.wait(5)
            held_at = cell.events[-1]['at']
            wait_for(lambda: cell.denial_since(held_at) is not None)
            denial = cell.denial_since(held_at)
            assert denial['permission_until'] > denial['at'], 'real denial precedes physical expiry'
            cell.record('actual_control_busy_denial', decision=deepcopy(denial))
        finally: release.set()
        claimed = attempt.result(timeout=5)
    cell.record('acquisition_return', claimed=claimed is not None, state=cell.snapshot())
    assert claimed is None
    assert cell.snapshot() == cell.before
    assert not any(a.get('state') in ('launching','occupied') for a in cell.actors)
    cell.complete_same_unit()
    cell.outcome = 'passed'


@pytest.mark.parametrize('store', ['sqlite','postgresql'], indirect=True)
@pytest.mark.parametrize('change', ['epoch','drain'])
def test_fresh_control_after_real_validation_defers(cell, monkeypatch, change):
    cell.start_renew();cell.stop_renew()
    actual = service._current
    def current(db, run):
        result = actual(db, run)
        if run.id == cell.id:
            assert result
            values = {'epoch': cell.sup.identity['epoch'] + 1} if change == 'epoch' else {'drained': True}
            if cell.backend == 'postgresql':
                # Real independent committed update under READ COMMITTED;
                # the initially loaded Control ORM object remains stale.
                with cell.factory() as writer:
                    writer.execute(update(Control).where(Control.id == 1).values(**values));writer.commit()
            else:
                # SQLite owner_write already owns the database writer; a
                # concurrent control writer cannot commit across this fence.
                # Test refresh against a real in-transaction SQL change instead.
                db.execute(update(Control).where(Control.id == 1).values(**values).execution_options(synchronize_session=False))
            cell.record('real_control_changed_after_validation', change=change, independent_commit=cell.backend=='postgresql')
        return result
    monkeypatch.setattr(service, '_current', current)
    assert cell.sup.acquire_job() is None
    assert cell.snapshot() == cell.before
    assert not cell.actors
    cell.outcome = 'passed'


@pytest.mark.parametrize('store', ['sqlite','postgresql'], indirect=True)
@pytest.mark.parametrize('when', ['entry','after_current'])
def test_actual_elapsed_permission_does_not_claim(cell, monkeypatch, when):
    cell.start_renew();cell.stop_renew()
    # A standalone renewal phase ends after genuine ACK. No clock/deadline is
    # rewritten; absence of further completed checks expires the actual lease.
    def elapsed():
        deadline = cell.sup.permission_until
        while time.monotonic() < deadline: time.sleep(.005)
        assert cell.sup.allowed is True
        cell.record('actual_permission_elapsed', when=when, permission_until=deadline)
    if when == 'entry': elapsed()
    else:
        actual = service._current
        def current(db, run):
            result = actual(db, run)
            if run.id == cell.id: assert result;elapsed()
            return result
        monkeypatch.setattr(service, '_current', current)
    assert cell.sup.acquire_job() is None
    assert cell.snapshot() == cell.before
    assert not cell.actors
    cell.outcome = 'passed'


def invalidate(cell, change):
    if change == 'rights':
        service.storage.record_negative(cell.owner, 'synthetic_revocation', 'origin', 'automatic')
    elif change == 'source':
        with cell.factory() as db:
            run = db.get(Run, cell.id)
            db.get(GarminFitSnapshot, run.snapshot_id).active_parse_id = None;db.commit()
    elif change == 'generation':
        with cell.factory() as db: service.change_run(db, cell.owner, '123', cell.id, 'cancel')
    else:
        from analysis import science_artifacts
        (Path(science_artifacts._SCIENCE_DIR) / 'stops/synthetic-acquisition-stop.yaml').write_text('schema_version: invalid\n')
    cell.record('actual_synthetic_invalidation', change=change)


@pytest.mark.parametrize('store', ['sqlite','postgresql'], indirect=True)
@pytest.mark.parametrize('change', ['rights','source','generation','stop'])
def test_fresh_authority_source_generation_stop_refuses_acquisition(cell, change):
    cell.start_renew();cell.stop_renew()
    invalidate(cell, change)
    assert cell.sup.acquire_job() is None
    state = cell.snapshot()
    assert state['status'] != 'running' and state['recoveries'] == 0
    assert not state['lease_token_present'] and not state['result_present']
    assert not cell.actors
    cell.outcome = 'passed'


@pytest.mark.parametrize('store', ['sqlite','postgresql'], indirect=True)
@pytest.mark.parametrize('change', ['rights','source','generation','stop'])
def test_change_after_claim_refuses_loading_launch_and_publication(cell, change):
    cell.start_renew();cell.stop_renew()
    job = cell.sup.acquire_job()
    assert job is not None
    invalidate(cell, change)
    outputs = queue.Queue()
    cell.sup.work(job, outputs)
    status, error = outputs.get(timeout=3)
    cell.record('old_claim_refused_before_spawn', status=status, error=error)
    assert status == 'failed_before_spawn'
    assert not cell.actors
    cell.sup.finish(job, status, error)
    state = cell.snapshot()
    assert not state['result_present'] and state['status'] != 'complete'
    assert state['recoveries'] == 0
    if change == 'generation': assert state['generation'] > job['generation']
    cell.outcome = 'passed'


@pytest.mark.parametrize('store', ['sqlite'], indirect=True)
def test_denial_after_final_check_is_failed_attempt_not_deferral(cell):
    cell.start_renew()
    flushed, release = threading.Event(), threading.Event()
    def hold_commit(db, context):
        if db.get_bind() is cell.factory.kw['bind'] and any(isinstance(obj,Run) and obj.id==cell.id and obj.status=='running' for obj in db.dirty):
            assert cell.sup.allowed and time.monotonic() < cell.sup.permission_until
            cell.record('after_final_check_real_running_flush', permission_until=cell.sup.permission_until)
            flushed.set();assert release.wait(5)
    event.listen(Session, 'after_flush', hold_commit)
    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='acquisition-late') as executor:
            attempt = executor.submit(cell.sup.acquire_job)
            try:
                assert flushed.wait(5)
                held_at = cell.events[-1]['at']
                wait_for(lambda: cell.denial_since(held_at) is not None)
                cell.record('actual_post_final_check_denial', decision=deepcopy(cell.denial_since(held_at)))
                cell.stop_renew()
            finally: release.set()
            job = attempt.result(timeout=5)
    finally: event.remove(Session, 'after_flush', hold_commit)
    assert job is not None and cell.snapshot()['status']=='running'
    outputs = queue.Queue();cell.sup.work(job, outputs)
    status, error = outputs.get(timeout=3)
    assert status=='failed_before_spawn' and error=='permission_expired'
    assert not cell.actors
    cell.sup.finish(job, status, error)
    state = cell.snapshot()
    assert state['status']=='queued' and state['recoveries']==1 and not state['result_present']
    cell.record('late_race_claimed_attempt_failed', status=status, error=error, state=state, service_success=False)
    cell.outcome = 'passed_negative_failed_service'


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('first_denial',[False,True])
def test_claimed_attempt_accounting_no_recovery_and_first_execution_denial(cell,first_denial,request):
    cell.start_renew()
    cell.first_execution_denial=first_denial
    cell.complete_same_unit()
    assert len(cell.attempts)==(2 if first_denial else 1)
    assert cell.snapshot()['recoveries']==(1 if first_denial else 0)
    if first_denial:
        assert cell.fault_injected and cell.fault_target['matched'] and cell.fault_decision.observation is not None
        fault=next(e for e in cell.diagnostic.terminal_events if e['event']=='scheduling_fault_applied')
        first=cell.attempts[0]
        assert fault['job']==first['claim']['job'] and fault['actor']==first['occupied_ack']['actor']
        assert first['occupied_ack']['at']<=fault['cycle_started']<=fault['at']<first['finish']['trigger']['decision']['at']
        assert first['finish']['trigger']['decision']['at']<=first['finish']['actor']['exit_observed_at']
        assert cell.attempts[0]['finish']['status']=='failed'
        assert cell.attempts[0]['finish']['reason']=='permission_expired'
        # Falsify using the actual captured two-attempt lifecycle, not a copied
        # helper implementation or fabricated successful claim/authority.
        mutations=[('missing_claim',lambda a:a[0].update(claim=None)),
                   ('claim_binding',lambda a:a[0]['claim']['state'].update(input_digest='different')),
                   ('claim_lease',lambda a:a[0]['claim']['state'].update(lease_token_hash=None)),
                   ('occupied_ack',lambda a:a[0].update(occupied_ack=None)),
                   ('selected_reason',lambda a:a[0]['finish'].update(reason=None)),
                   ('permission_decision',lambda a:a[0]['finish']['trigger'].update(decision=None)),
                   ('failure_actor',lambda a:a[0]['finish']['trigger']['actor'].update(actor='other')),
                   ('pending_binding',lambda a:a[0]['finish'].update(pending_actor=None)),
                   ('physical_identity',lambda a:(a[0]['finish']['actor'].update(identity=None),a[0]['occupied_ack']['actor'].update(identity=None))),
                   ('exit_ack',lambda a:a[0]['finish'].update(exit_ack_at=None)),
                   ('owner_finish_ack',lambda a:a[0].update(finish_ack=None)),
                   ('extra_recovery',lambda a:a[0]['finish_ack']['after'].update(recoveries=2))]
        for name,mutate in mutations:
            invalid=deepcopy(cell.attempts);mutate(invalid)
            with pytest.raises(AssertionError):assert_attempt_ledger(invalid,cell.attempts[0]['claim']['job'])
        request.node.user_properties.append(('dfa_missing_provenance_checks',json.dumps([name for name,_ in mutations])))
    cell.outcome='passed_controlled_attempt_contract'
