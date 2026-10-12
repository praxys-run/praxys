"""Real queued acquisition deferral; no forged permission or extra recovery."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import hashlib
import json
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
        actual = self.sup.renew
        def renew():
            self.threads.append(threading.current_thread())
            try: actual()
            except Exception as exc: self.errors.append(type(exc).__name__)
        monkeypatch.setattr(self.sup, 'renew', renew)
        self.backend = backend
        self.outcome = 'failed'
        self.before = self.snapshot()

    def record(self, kind, **fields):
        self.events.append({'kind': kind, 'at': time.monotonic(), **fields})

    def snapshot(self):
        with self.factory() as db:
            run = db.get(Run, self.id)
            if run is None: return {'status': 'erased'}
            return {key: getattr(run, key) for key in ('id','origin','phase','status','progress','generation','recoveries','error_code','execution_epoch')} | {
                'lease_token_present': run.lease_token is not None, 'lease_until': str(run.lease_until) if run.lease_until else None,
                'result_present': run.result is not None}

    def start_renew(self):
        self.sup.stop.clear()
        thread = threading.Thread(target=self.sup.renew, name='dfa-control')
        thread.start()
        wait_for(lambda: bool(self.proof.renewals) and self.sup.allowed)
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
        assert self.snapshot()['recoveries'] == 0
        launched = next(a for a in self.actors if a.get('state') == 'occupied')
        assert launched['process_start_observed_at'] >= launched['launch_at']
        denial_at = next(e['decision']['at'] for e in self.events if e['kind'] == 'actual_control_busy_denial')
        assert any(r['completed_at'] > denial_at and r['permission_granted_at'] <= launched['launch_at'] for r in self.proof.renewals)
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
            'errors': self.errors, 'all_owned_threads_joined': joined,
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
    finally: value.close()


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
