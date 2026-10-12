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
from tests.dfa_capacity_measurement import (observed_requests,fresh_physical_eligibility,observe_acceptance,lifecycle_observations)


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
            control=db.get(Control,1)
            if run_id:
                row=db.get(Run,run_id)
                return None if row is None else {k:getattr(row,k).isoformat() if k=='accepted_at' and getattr(row,k) else getattr(row,k)
                    for k in ('id','status','phase','generation','admission_id','accepted_at','execution_epoch','input_digest')} | {'manual_sequence':control.manual_sequence}
            return {'runs':sorted(tuple(r) for r in db.query(Run.id,Run.generation,Run.admission_id).filter_by(user_id=owner,origin='manual')),
                    'manual_sequence':control.manual_sequence}
    previous=snapshot();before=time.monotonic()
    with factory() as db:
        control=db.get(Control,1)
        readiness={'sequence':control.readiness_sequence,'ready_until':str(control.ready_until),
                   'actor':control.actor,'observed_at_utc':datetime.utcnow().isoformat()}
    entry={**context,'before_monotonic':before,'before_durable':previous,'readiness':readiness};ledger.append(entry)
    try:
        with factory() as db:
            db.info['capacity_admission_record']=entry
            admitted,status=service.submit(db,owner,'123',catalog['inputs'][0]['input'],catalog['catalog_revision'],confirmation)
    except Exception as exc:
        entry.update(after_monotonic=time.monotonic(),outcome='exception',http_status=getattr(exc,'status_code',None),
                     detail=getattr(exc,'detail',type(exc).__name__))
        subject=entry.get('transaction_subject',{});after=snapshot(subject['id']) if subject.get('id') else None
        if (after and after['accepted_at'] and after['manual_sequence']>previous['manual_sequence']
                and all(after[k]==subject[k] for k in ('generation','admission_id'))
                and (after['id'],after['generation'],after['admission_id']) not in previous['runs']):
            entry.update(after_durable=after,outcome='accepted_error')
            return {k:after[k] for k in ('id','generation','admission_id')},entry
        entry['after_durable']=snapshot();entry['no_durable_acceptance']=entry['after_durable']==previous
        if isinstance(exc,HTTPException) and (exc.status_code,exc.detail)==(503,'DFA_CAPACITY_UNAVAILABLE'):
            assert entry['no_durable_acceptance'],entry
            entry['outcome']='pre_admission_denied';return None,entry
        raise
    # Retain durable acceptance before response or cohort validity assertions.
    entry.update(after_monotonic=time.monotonic(),outcome='accepted',accepted_response={k:admitted[k] for k in ('id','generation','admission_id')},
                 metadata_response_valid=status==202 and not {'result','summary','windows'}.intersection(admitted))
    subject=entry.get('transaction_subject',admitted);entry['after_durable']=snapshot(subject['id'])
    entry['acceptance_consistent']=bool(entry['after_durable'] and entry['after_durable']['accepted_at']
        and entry['after_durable']['manual_sequence']==previous['manual_sequence']+1
        and all(entry['after_durable'][k]==admitted[k] for k in ('id','generation','admission_id')))
    return {k:entry['after_durable'][k] for k in ('id','generation','admission_id')},entry




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
