"""Bounded real admission/renewal cells, with payload-free timing observations."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from api import activity_dfa as service
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run
from tests.test_activity_dfa import store, confirmed
from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_dfa_supervisor_capacity import PriorityEvidence, admission_attempt


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_retry_metadata_never_projects_old_numbers(store, monkeypatch):
    factory, owner = store
    _, manual = confirmed(factory, owner)
    with factory() as db:
        row = db.get(Run, manual['id']); row.status = 'failed'
        row.result = {'summary': {'alpha': 12345}, 'windows': [{'alpha': 12345}]}
        row.result_revision = 'old-revision'; db.commit()
    def forbidden(*args, **kwargs):
        raise AssertionError('Retry must not recompute result disclosure under admission lock')
    monkeypatch.setattr(service, 'view', forbidden)
    with factory() as db:
        response = service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
    assert response['status'] == 'queued' and response['freshness'] == 'current'
    assert response['result_revision'] is None
    assert not {'summary', 'windows', 'result'}.intersection(response)
    with factory() as db:
        row = db.get(Run, manual['id'])
        assert row.result is None and row.result_revision is None


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
@pytest.mark.parametrize('invalidate', ['rights', 'source', 'generation'])
def test_retry_revalidates_serialized_authority_before_acceptance(store, invalidate):
    factory, owner = store
    _, manual = confirmed(factory, owner)
    with factory() as db:
        row = db.get(Run, manual['id']); row.status = 'failed'; db.commit()
        old_sequence = db.get(Control, 1).manual_sequence
    if invalidate == 'rights':
        service.storage.record_negative(owner, 'withdrawal', 'origin', 'manual')
    elif invalidate == 'source':
        with factory() as db:
            service.invalidate_snapshot(db, owner, manual['snapshot_id']); db.commit()
    else:
        with factory() as db:
            db.get(Run, manual['id']).generation += 1; db.commit()
    with factory() as db, pytest.raises(HTTPException) as failure:
        service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
    assert (failure.value.status_code, failure.value.detail) == (
        (404, 'DFA_RUN_NOT_FOUND') if invalidate == 'source' else (409, 'DFA_RETRY_CHANGED'))
    with factory() as db:
        assert db.get(Control, 1).manual_sequence == old_sequence
        row = db.get(Run, manual['id'])
        assert row is None if invalidate == 'source' else row.status != 'queued'


def new_submission_attempt(factory, owner, catalog, confirmation, ledger, context):
    def snapshot(run_id=None):
        with factory() as db:
            control = db.get(Control, 1)
            rows = db.query(Run).filter_by(user_id=owner, origin='manual').all()
            if run_id:
                row = db.get(Run, run_id)
                return {'status': row.status, 'generation': row.generation, 'admission_id': row.admission_id,
                        'accepted_at': row.accepted_at.isoformat(), 'execution_epoch': row.execution_epoch,
                        'manual_sequence': control.manual_sequence}
            return {'runs': sorted((r.id, r.generation, r.admission_id) for r in rows),
                    'manual_sequence': control.manual_sequence}
    previous = snapshot()
    with factory() as db:
        control = db.get(Control, 1)
        readiness = {'sequence': control.readiness_sequence, 'ready_until': str(control.ready_until),
                     'actor': control.actor, 'observed_at_utc': datetime.utcnow().isoformat()}
    entry = {**context, 'before_monotonic': time.monotonic(), 'before_durable': previous, 'readiness': readiness}
    ledger.append(entry)
    try:
        with factory() as db:
            admitted, status = service.submit(db, owner, '123', catalog['inputs'][0]['input'], catalog['catalog_revision'], confirmation)
    except HTTPException as exc:
        entry.update(after_monotonic=time.monotonic(), after_durable=snapshot(), outcome='exception',
                     http_status=exc.status_code, detail=exc.detail)
        if (exc.status_code, exc.detail) != (503, 'DFA_CAPACITY_UNAVAILABLE'): raise
        assert previous == entry['after_durable'], entry
        entry['outcome'] = 'pre_admission_denied'
        return None, entry
    entry.update(after_monotonic=time.monotonic(), after_durable=snapshot(admitted['id']), outcome='accepted')
    assert status == 202 and not {'result', 'summary', 'windows'}.intersection(admitted)
    assert entry['after_durable']['manual_sequence'] == previous['manual_sequence']+1
    return admitted, entry


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
@pytest.mark.parametrize('operation', ['retry', 'prepare', 'compute'])
def test_real_renewal_admission_and_delayed_response(both_origins, monkeypatch, operation):
    """ONE ingress per DB: accepted failure is terminal, never resampled."""
    factory, owner = both_origins
    confirmation, manual = confirmed(factory, owner)
    with factory() as db: claimed = service.claim(db)
    service.execute(factory, *claimed)
    with factory() as db:
        row = db.get(Run, manual['id']); generation = row.generation
        if operation == 'retry': row.status = 'failed'
        else:
            db.query(Run).filter_by(user_id=owner, origin='manual', phase=operation).delete(synchronize_session=False)
        db.commit()
        catalog = service.catalog(db, owner, '123')
    complete_unit(factory, owner)
    supervisor = factory.dfa_supervisor
    # Discard only the legacy direct-step fixture's permission. This cell must
    # obtain its own real completed 750ms renewal before launching any work.
    supervisor.allowed = False; supervisor.permission_until = 0.
    with factory() as db: initial_sequence = db.get(Control, 1).readiness_sequence
    url = factory.kw['bind'].url
    args = {'timeout': .1} if url.get_backend_name() == 'sqlite' else {
        'connect_timeout': 1, 'options': '-c statement_timeout=200 -c lock_timeout=200'}
    control_engine = create_engine(url, pool_size=2, max_overflow=0, pool_timeout=.1, connect_args=args)
    supervisor.controls = sessionmaker(bind=control_engine)
    actual_popen = subprocess.Popen
    code = '''import io,json,signal,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
raw=sys.stdin.buffer.readline(90*1024*1024+1)
payload=json.loads(raw)
if payload['origin']=='automatic':
    while True:time.sleep(.01)
else:
    signal.signal(signal.SIGTERM,signal.SIG_DFL)
    sys.stdin=io.TextIOWrapper(io.BytesIO(raw))
    from api.dfa_worker import main
    main()
'''
    def child(command, **kwargs):
        if command[-2:] == ['-m', 'api.dfa_worker']:
            command = [sys.executable, '-E', '-B', '-c', code]
        return actual_popen(command, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', child)
    proof = PriorityEvidence(supervisor, monkeypatch)
    observations = []; ledger = []; errors = []; actors = []; availability = {}; pulse_samples = []
    observe_stop = threading.Event()
    def observe_renewal():
        previous = None
        while not observe_stop.wait(.002):
            value = supervisor.control_observation
            if value is not previous:
                observations.append({'kind': 'renewal', 'observed_at': time.monotonic(), **value})
                previous = value
    observer = threading.Thread(target=observe_renewal); observer.start()
    def observe_pulse():
        while not observe_stop.wait(.025):
            try:
                with factory() as db:
                    control = db.get(Control, 1)
                    observed = time.monotonic(); wall = datetime.utcnow()
                    ready = bool(control.readiness_sequence > initial_sequence and control.enabled and not control.drained
                        and control.incarnation == supervisor.identity and control.epoch == supervisor.identity['epoch']
                        and control.ready_until and control.ready_until > wall)
                    deadline = observed+(control.ready_until-wall).total_seconds() if control.ready_until else observed
                    with supervisor.lock: active = supervisor.active
                    pulse_samples.append({'at': observed, 'eligible': ready, 'deadline_monotonic': deadline,
                        'automatic_occupied': bool(active and active['origin']=='automatic' and control.actor
                            and control.actor.get('state')=='occupied'), 'sequence': control.readiness_sequence})
            except Exception as exc:
                pulse_samples.append({'at':time.monotonic(), 'eligible':False, 'exception_class':type(exc).__name__})
    pulse_observer = threading.Thread(target=observe_pulse); pulse_observer.start()
    def committed(db):
        if db.get_bind() in (factory.kw['bind'], control_engine):
            observations.append({'kind': 'commit_completed', 'at': time.monotonic(),
                                 'thread': threading.current_thread().name})
    def db_error(context):
        observations.append({'kind': 'db_error', 'at': time.monotonic(),
                             'exception_class': type(context.original_exception).__name__})
    def begun(db, transaction, connection):
        if db.get_bind() in (factory.kw['bind'], control_engine):
            observations.append({'kind': 'transaction_started', 'at': time.monotonic(),
                                 'thread': threading.current_thread().name})
    event.listen(Session, 'after_begin', begun)
    event.listen(Session, 'after_commit', committed)
    for engine in (factory.kw['bind'], control_engine): event.listen(engine, 'handle_error', db_error)
    actual_exit = supervisor.record_exit
    def record_exit():
        actual_exit()
        actor = supervisor.lane.actor()
        availability[actor['actor_token']] = time.monotonic()
    monkeypatch.setattr(supervisor, 'record_exit', record_exit)
    actual_record = supervisor.lane.record
    def record(actor):
        actual_record(actor); actors.append(dict(actor))
    monkeypatch.setattr(supervisor.lane, 'record', record)
    from api import activity_dfa_dispatch
    def delayed_delivery():
        observations.append({'kind': 'delivery_start', 'at': time.monotonic()})
        # Actual committed transaction; only response delivery waits.
        time.sleep(.35)
        observations.append({'kind': 'delivery_end', 'at': time.monotonic()})
    monkeypatch.setattr(activity_dfa_dispatch, 'wake', delayed_delivery)
    def worker():
        try: supervisor.run()
        except Exception as exc: errors.append(type(exc).__name__)
    thread = threading.Thread(target=worker); thread.start()
    root = Path(__file__).resolve().parents[1]
    outcome = 'failed'
    try:
        deadline = time.monotonic() + 15
        while True:
            with factory() as db:
                control = db.get(Control, 1); actor = control.actor
            if control.readiness_sequence > initial_sequence and actor and actor['state'] == 'occupied': break
            assert time.monotonic() < deadline, {'stage': 'ready', 'errors': errors, 'observations': observations}
            time.sleep(.01)
        # Fixed observation period covers several complete cadence cycles; no
        # readiness predicate chooses when this profile issues its one ingress.
        time.sleep(.75)
        # Predetermined phase offsets, independent of readiness eligibility.
        phase_delay = {'retry': 0., 'prepare': .06, 'compute': .12}[operation]
        time.sleep(phase_delay)
        if operation == 'retry':
            admitted, entry = admission_attempt(factory, owner, manual['id'], generation, ledger,
                {'cell': str(url.get_backend_name()), 'operation': operation, 'phase_delay': phase_delay})
        else:
            admitted, entry = new_submission_attempt(factory, owner, catalog, confirmation['id'] if operation=='compute' else None,
                ledger, {'cell': str(url.get_backend_name()), 'operation': operation, 'phase_delay': phase_delay})
        if admitted is None:
            # This is a profile measurement, not a selected-window promise of
            # ingress success. Retain the real bounded refusal separately;
            # accepted requests still require every causal/completion assertion.
            assert entry['outcome']=='pre_admission_denied', entry
            assert entry['before_durable']==entry['after_durable'], entry
            outcome='pre_admission_denied'
            return
        deadline = time.monotonic() + 5
        while not proof.retired.is_set():
            assert time.monotonic() < deadline, errors
            time.sleep(.01)
        retirement = proof.accepted_preemption(admitted, entry['readiness']['actor'], entry)
        assert retirement['exit_observed_at'] - entry['before_monotonic'] <= 5
        deadline = time.monotonic() + 15
        while True:
            with factory() as db:
                row = db.get(Run, admitted['id']); state = row.status
                durable_actor = db.get(Control, 1).actor
            if state == ('awaiting_source_confirmation' if operation=='prepare' else 'complete'): break
            assert time.monotonic() < deadline, {'stage': 'manual_completion', 'state': state, 'errors': errors}
            time.sleep(.01)
        assert row.result and not errors
        assert entry['readiness']['actor']['actor_token'] in availability
        available_at = availability[entry['readiness']['actor']['actor_token']]
        assert available_at - entry['before_monotonic'] <= 5
        for previous, following in zip(actors, actors[1:]):
            if following['state'] == 'launching' and following['actor_token'] != previous.get('actor_token'):
                assert previous['state'] == 'idle'
                assert following['launch_at'] >= previous['exit_observed_at']
                assert following['launch_at'] >= availability[previous['actor_token']]
        assert any(e['kind'] == 'commit_completed' and e['thread'] == 'dfa-control' for e in observations)
        outcome = 'passed'
    finally:
        supervisor.stop.set(); thread.join(10)
        observe_stop.set(); observer.join(2); pulse_observer.join(2)
        event.remove(Session, 'after_begin', begun)
        event.remove(Session, 'after_commit', committed)
        for engine in (factory.kw['bind'], control_engine): event.remove(engine, 'handle_error', db_error)
        control_engine.dispose()
        artifact = root / f'.git/pr871-new-admission-{operation}-{url.get_backend_name()}-{time.time_ns()}.json'
        artifact.write_text(json.dumps({'operation': operation, 'outcome': outcome, 'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'working_tree_source_bindings': {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in
                [root/'api/activity_dfa.py',root/'api/dfa_rights.py',root/'api/dfa_supervisor.py',Path(__file__),root/'tests/test_dfa_supervisor_capacity.py']},
            'observations': observations, 'ingress': ledger, 'retirements': proof.retirements,
            'priorities': proof.priorities, 'actors': actors, 'durable_availability': availability, 'errors': errors,
            'pulse_samples':pulse_samples, 'profile':{'start_cadence_seconds':.125,'sql_admission_budget_seconds':.25,
                'physical_permission_seconds':.75,'phase_delay_seconds':{'retry':0.,'prepare':.06,'compute':.12}[operation],
                'attempt_budget':1,'fast_window_selection':False,'fixed_observation_seconds':.75,'pulse_sampling_seconds':.025},
            'instrumentation': 'SQLAlchemy actual after_commit/error callbacks and 2ms read-only renewal/25ms independent SQL pulse sampling; no SQL payloads, tracing, parking or forged renewal; observer overhead unquantified'}, default=str, indent=2))
        assert not thread.is_alive(), errors


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
@pytest.mark.parametrize('action', ['cancel', 'revoke', 'reparse'])
def test_late_child_output_cannot_cross_committed_revocation(store, monkeypatch, action):
    # The established regression runs a real child up to publication, commits
    # the owner/source change concurrently, then releases the stale output.
    from tests.test_activity_dfa import test_inflight_publication_cannot_outlive_rights_or_source_change
    test_inflight_publication_cannot_outlive_rights_or_source_change(store, monkeypatch, action)


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_current_grant_denies_changed_run_contract(store):
    factory, owner = store
    _, manual = confirmed(factory, owner)
    with factory() as db:
        row = db.get(Run, manual['id']); row.science_contract_digest = 'sha256:' + 'f'*64; db.commit()
    with factory() as db:
        assert service._current(db, db.get(Run, manual['id'])) is False


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_reserved_control_pool_allows_renewal_during_lifecycle_checkout(store, monkeypatch):
    from api.dfa_supervisor import control_factory
    factory, owner = store
    monkeypatch.setenv('PRAXYS_DATABASE_URL', str(factory.kw['bind'].url))
    controls = control_factory()
    supervisor = factory.dfa_supervisor; supervisor.controls = controls
    observations = []; errors = []
    def renew():
        try: supervisor.renew()
        except Exception as exc: errors.append(type(exc).__name__)
    thread = threading.Thread(target=renew)
    try:
        with controls() as lifecycle:
            lifecycle.connection()  # Real concurrent checkout, no actor/DB locks.
            thread.start()
            deadline = time.monotonic()+3
            while supervisor.control_observation['state'] != 'ready':
                observations.append(dict(supervisor.control_observation))
                assert time.monotonic()<deadline, {'observations': observations, 'errors': errors}
                time.sleep(.01)
            assert supervisor.control_observation['duration_seconds'] < .25
            if lifecycle.get_bind().dialect.name == 'sqlite':
                from sqlalchemy import text
                assert lifecycle.execute(text('PRAGMA busy_timeout')).scalar() == 100
    finally:
        supervisor.stop.set(); thread.join(3); controls.kw['bind'].dispose()
        assert not thread.is_alive() and not errors


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_late_completed_renewal_commit_does_not_extend_permission(store):
    factory, owner = store
    supervisor = factory.dfa_supervisor
    previous_permission = supervisor.permission_until
    class DelayedCommit(Session):
        def commit(self):
            super().commit()  # Real completion, then delayed control receipt.
            time.sleep(.3)
            supervisor.stop.set()
    supervisor.controls = sessionmaker(bind=factory.kw['bind'], class_=DelayedCommit)
    supervisor.renew()
    assert supervisor.allowed is False
    assert supervisor.permission_until == previous_permission
    assert supervisor.control_observation['state'] == 'deadline'
    assert supervisor.control_observation['duration_seconds'] >= .3


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_real_control_lock_failure_denies_without_renewal(store, monkeypatch):
    from api.dfa_supervisor import control_factory
    from sqlalchemy import text
    factory, owner = store
    monkeypatch.setenv('PRAXYS_DATABASE_URL', str(factory.kw['bind'].url))
    controls = control_factory()
    supervisor = factory.dfa_supervisor; supervisor.controls = controls
    failures = []; timing = {}
    def failure(context):
        failures.append({'at_monotonic': time.monotonic(), 'exception_class': type(context.original_exception).__name__,
                         'operation': context.statement.split()[0].upper(),
                         'target_control': 'activity_dfa_control' in context.statement.lower(),
                         'sqlstate': getattr(context.original_exception, 'sqlstate', None),
                         'sqlite_errorcode': getattr(context.original_exception, 'sqlite_errorcode', None)})
    event.listen(controls.kw['bind'], 'handle_error', failure)
    worker = threading.Thread(target=supervisor.renew)
    try:
        # First establish a genuine completed renewal, then take the exact
        # competing write lock. No permission/readiness is manufactured here.
        with factory() as writer:
            worker.start()
            deadline = time.monotonic()+3
            while supervisor.control_observation['state'] != 'ready':
                assert time.monotonic()<deadline
                time.sleep(.005)
            previous_permission = supervisor.permission_until
            if writer.get_bind().dialect.name == 'sqlite':
                writer.execute(text('BEGIN IMMEDIATE'))
            else:
                writer.query(Control).filter_by(id=1).with_for_update().one()
            timing['lock_acquired_at'] = time.monotonic()
            deadline = time.monotonic()+3
            while not failures or supervisor.allowed:
                assert time.monotonic()<deadline, {'failures': failures, 'control': supervisor.control_observation}
                time.sleep(.005)
            timing.update(denial_observed_at=time.monotonic(), previous_permission=previous_permission,
                          permission_after=supervisor.permission_until, observation=dict(supervisor.control_observation))
            supervisor.stop.set()
            assert supervisor.permission_until == previous_permission
            assert supervisor.control_observation['state'] == 'OperationalError'
            if writer.get_bind().dialect.name == 'sqlite':
                assert failures[-1]['sqlite_errorcode'] == 5
            else:
                # Equal 200ms statement/lock deadlines race. Record whichever
                # real timer wins on the blocked UPDATE; reject every other error.
                assert failures[-1]['operation'] == 'UPDATE' and failures[-1]['target_control']
                assert failures[-1]['sqlstate'] in ('55P03', '57014')
            writer.rollback()
    finally:
        supervisor.stop.set();worker.join(3)
        event.remove(controls.kw['bind'], 'handle_error', failure)
        root = Path(__file__).resolve().parents[1]
        artifact = root/f'.git/pr871-control-lock-{factory.kw["bind"].dialect.name}-{time.time_ns()}.json'
        artifact.write_text(json.dumps({'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'timing': timing, 'failures': failures,
            'source_bindings': {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in
                [Path(__file__),root/'api/dfa_supervisor.py']},
            'instrumentation': 'real lock and DBAPI error callback, payload-free; no replaced control decisions/timer'},indent=2))
        controls.kw['bind'].dispose()
        assert not worker.is_alive()


@pytest.mark.parametrize('store', ['postgresql'], indirect=True)
def test_admission_refreshes_locked_control_after_projection(store, monkeypatch):
    factory, owner = store
    _, manual = confirmed(factory, owner)
    with factory() as db:
        row = db.get(Run, manual['id']); row.status = 'failed'; db.commit()
        previous = {'generation': row.generation, 'admission_id': row.admission_id,
                    'sequence': db.get(Control, 1).manual_sequence}
    actual = service._metadata
    def concurrent_drain(db, run, current):
        response = actual(db, run, current)  # Loads old Control into request identity map.
        with factory() as controller:
            controller.get(Control, 1).drained = True
            controller.commit()  # Genuine independent committed control change.
        return response
    monkeypatch.setattr(service, '_metadata', concurrent_drain)
    with factory() as db, pytest.raises(HTTPException) as failure:
        service.change_run(db, owner, '123', manual['id'], 'retry', manual['generation'])
    assert (failure.value.status_code, failure.value.detail) == (503, 'DFA_CAPACITY_UNAVAILABLE')
    with factory() as db:
        row = db.get(Run, manual['id']); control = db.get(Control, 1)
        assert row.status == 'failed' and row.generation == previous['generation']
        assert row.admission_id == previous['admission_id']
        assert control.drained and control.manual_sequence == previous['sequence']


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('phase',['prepare','compute'])
@pytest.mark.parametrize('failure',['expired','drained','epoch'])
def test_new_submission_failed_admission_rolls_back_all_sql(store,phase,failure):
    from db.models import ActivityDFAOriginGrant
    factory,owner=store
    confirmation,manual=confirmed(factory,owner)
    with factory() as db:claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        db.query(Run).filter_by(user_id=owner,origin='manual',phase=phase).delete(synchronize_session=False);db.commit()
        catalog=service.catalog(db,owner,'123')
        before_runs=sorted((r.id,r.generation,r.admission_id) for r in db.query(Run).filter_by(user_id=owner).all())
        before_grants=[r.id for r in db.query(ActivityDFAOriginGrant).filter_by(user_id=owner).all()]
        control=db.get(Control,1);before_sequence=control.manual_sequence
        if failure=='expired':control.ready_until=datetime.utcnow()
        elif failure=='drained':control.drained=True
        else:
            control.actor=None;control.epoch+=1  # Cold actor cannot hide epoch mismatch.
        db.commit()
    with factory() as db,pytest.raises(HTTPException) as denied:
        service.submit(db,owner,'123',catalog['inputs'][0]['input'],catalog['catalog_revision'],confirmation['id'] if phase=='compute' else None)
    assert (denied.value.status_code,denied.value.detail)==(503,'DFA_CONTROL_GENERATION_CHANGED' if failure=='epoch' else 'DFA_CAPACITY_UNAVAILABLE')
    with factory() as db:
        assert sorted((r.id,r.generation,r.admission_id) for r in db.query(Run).filter_by(user_id=owner).all())==before_runs
        assert [r.id for r in db.query(ActivityDFAOriginGrant).filter_by(user_id=owner).all()]==before_grants
        assert db.get(Control,1).manual_sequence==before_sequence


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('phase',['prepare','compute'])
def test_new_queued_submission_projects_no_result_under_control_lock(store,monkeypatch,phase):
    factory,owner=store
    confirmation,manual=confirmed(factory,owner)
    with factory() as db:claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        db.query(Run).filter_by(user_id=owner,origin='manual',phase=phase).delete(synchronize_session=False);db.commit()
        catalog=service.catalog(db,owner,'123')
    from api import dfa_supervisor
    actual=dfa_supervisor.manual_admission
    projection_done=threading.Event()
    metadata=service._metadata
    def delayed_metadata(db,run,current):
        response=metadata(db,run,current)
        time.sleep(.03)  # Deliberate projection work before admission lock.
        projection_done.set()
        return response
    def final_admission(db):
        assert projection_done.is_set()
        return actual(db)
    monkeypatch.setattr(service,'_metadata',delayed_metadata)
    monkeypatch.setattr(dfa_supervisor,'manual_admission',final_admission)
    def forbidden(*args,**kwargs):raise AssertionError('New queued submission must not run result-disclosure view')
    monkeypatch.setattr(service,'view',forbidden)
    with factory() as db:
        result,status=service.submit(db,owner,'123',catalog['inputs'][0]['input'],catalog['catalog_revision'],confirmation['id'] if phase=='compute' else None)
    assert status==202 and result['status']=='queued' and result['result_revision'] is None
    assert not {'windows','summary','result'}.intersection(result)
    with factory() as db:
        row=db.get(Run,result['id']);assert row.result is None and row.admission_id==result['admission_id']
