"""Real SQL visibility and observed renewal ACK boundaries; synthetic authority only."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import threading
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from api import activity_dfa as service
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run, ActivityDFAOriginGrant as Grant
from tests.test_activity_dfa import store, confirmed
from tests.test_dfa_origins import both_origins
from tests.dfa_capacity_worker import failure


def state(factory, run_id):
    with factory() as db:
        run = db.get(Run, run_id); control = db.get(Control, 1)
        return {'generation':run.generation,'admission_id':run.admission_id,'status':run.status,
                'manual_sequence':control.manual_sequence,'progress':run.progress,
                'recoveries':run.recoveries,'result_revision':run.result_revision,
                'result_present':run.result is not None,'lease_present':run.lease_token is not None}


@pytest.fixture
def first_renewal(monkeypatch, record_property):
    from tests.dfa_boundary_evidence import FirstRenewalOutcome
    outcomes=[]
    def first(supervisor, factory):
        value=FirstRenewalOutcome(supervisor,factory,monkeypatch)
        outcomes.append(value)
        value.run()
        value.require_ready()
        return value.persisted
    def observe(supervisor, factory):
        value=FirstRenewalOutcome(supervisor,factory,monkeypatch);outcomes.append(value);return value
    first.observe=observe
    first.outcomes=outcomes
    try:yield first
    finally:
        # Registered before assertions/teardown can obscure the first decision.
        record_property('dfa_first_renewal',json.dumps([v.evidence() for v in outcomes],separators=(',',':')))


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('warm',[False,True])
@pytest.mark.parametrize('publication',['late_publish','timely_publish_late_ack'])
def test_sql_publication_and_local_ack_are_distinct(both_origins,monkeypatch,first_renewal,record_property,warm,publication):
    from api import dfa_rights, dfa_supervisor
    factory,owner=both_origins
    _,run=confirmed(factory,owner)
    with factory() as db:db.get(Run,run['id']).status='failed';db.commit()
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.
    if warm:first_renewal(supervisor,factory)
    prior_permission=supervisor.permission_until
    prior_state=state(factory,run['id'])
    published=threading.Event();release=threading.Event();trace=[];errors=[]
    backend=factory.kw['bind'].dialect.name
    scope='whole_API_final_admission_boundary' if backend=='postgresql' else 'direct_locked_admission_only'
    class Delayed(Session):
        def commit(self):
            trace.append({'event':'session_commit_invoked','at':time.monotonic()})
            if publication=='late_publish':time.sleep(.30)
            super().commit()
            trace.append({'event':'session_commit_returned','at':time.monotonic()})
            published.set()
            assert release.wait(2)
            trace.append({'event':'supervisor_ack_return','at':time.monotonic()})
            supervisor.stop.set()
    supervisor.controls=sessionmaker(bind=factory.kw['bind'],class_=Delayed)
    captured=first_renewal.observe(supervisor,factory)
    observation_scope=monkeypatch.context();scoped=observation_scope.__enter__();captured.observe(scoped)
    def renew():
        try:supervisor.renew()
        except BaseException as exc:errors.append(failure(exc))
    worker=threading.Thread(target=renew);captured.thread=worker
    actual_admission=dfa_supervisor.manual_admission
    def publish():
        assert worker.ident is None  # Exactly one prospective renewal, no resampling.
        worker.start();assert published.wait(2),errors
        with factory() as db:
            control=db.get(Control,1)
            trace.append({'event':'independent_sql_visible','at':time.monotonic(),
                'ready_until':control.ready_until.isoformat(),'wall':datetime.utcnow().isoformat(),
                'sequence':control.readiness_sequence})
        assert supervisor.permission_until==prior_permission
        assert supervisor.allowed is warm
    def admission(db):
        # change_run has performed real rights/source/mode checks and flushed
        # owner mutations, but has not locked the PG control row yet.
        trace.append({'event':'API_validation_complete','at':time.monotonic()})
        publish()
        trace.append({'event':'locked_admission_invoked','at':time.monotonic()})
        value=actual_admission(db)
        trace.append({'event':'locked_admission_returned','at':time.monotonic(),
                      'accepted_at':value[1].isoformat()})
        return value
    if backend=='postgresql':monkeypatch.setattr(dfa_supervisor,'manual_admission',admission)
    outcome='failed';attempt=None
    try:
        before=time.monotonic()
        try:
            if backend=='postgresql':
                with factory() as db:
                    admitted=service.change_run(db,owner,'123',run['id'],'retry',run['generation'])
                admission_id=admitted['admission_id']
            else:
                # SQLite owner_write holds its writer from BEGIN IMMEDIATE: a
                # parallel control write inside change_run would deadlock. Keep
                # real authority checks, release that read session, then test the
                # original locked-admission primitive in its own transaction.
                # This proves no whole-API authorization/service outcome.
                with factory() as db:
                    dfa_rights.require_manual_mode(db,owner);service.require_authority(db,owner)
                    assert service._current(db,db.get(Run,run['id']))
                    db.rollback()
                trace.append({'event':'real_authority_validation_complete','at':time.monotonic()})
                publish()
                with factory() as db:
                    with service.owner_write(db,owner):
                        dfa_rights.require_manual_mode(db,owner)
                        trace.append({'event':'locked_admission_invoked','at':time.monotonic()})
                        admission_id,accepted_at,epoch=actual_admission(db)
                        trace.append({'event':'locked_admission_returned','at':time.monotonic(),
                                      'accepted_at':accepted_at.isoformat()})
                        db.commit()
            attempt={'outcome':'accepted','before':before,'after':time.monotonic(),'admission_id':admission_id}
        except HTTPException as exc:
            attempt={'outcome':'denied','before':before,'after':time.monotonic(),'status':exc.status_code,'detail':exc.detail}
        if publication=='late_publish':
            assert (attempt['outcome'],attempt['status'],attempt['detail'])==('denied',503,'DFA_CAPACITY_UNAVAILABLE')
            assert state(factory,run['id'])==prior_state
        else:
            assert attempt['outcome']=='accepted',attempt
            after=state(factory,run['id'])
            assert after['manual_sequence']==prior_state['manual_sequence']+1
            if backend=='postgresql':
                assert after['status']=='queued' and after['admission_id']==attempt['admission_id']
            else:
                assert {k:v for k,v in after.items() if k!='manual_sequence'}=={k:v for k,v in prior_state.items() if k!='manual_sequence'}
        # Delaying ACK beyond the original250ms must not rewrite an accepted
        # boundary/API receipt. This delay never changes the SQL deadline.
        remaining=.31-(time.monotonic()-next(t['at'] for t in trace if t['event']=='session_commit_invoked'))
        if remaining>0:time.sleep(remaining)
        release.set();worker.join(2)
        assert not worker.is_alive() and not errors
        assert captured.first and captured.first['allowed'] is False, captured.evidence()
        assert supervisor.allowed is False and supervisor.permission_until==prior_permission
        outcome='passed'
    finally:
        release.set();supervisor.stop.set()
        if worker.ident is not None:worker.join(2)
        try:captured.persisted=captured.capture_sql() if not worker.is_alive() else None
        except BaseException as exc:captured.cleanup_errors.append(failure(exc))
        observation_scope.__exit__(None,None,None)
        safe_attempt=None if attempt is None else {k:v for k,v in attempt.items() if k!='admission_id'}
        record_property('dfa_publication_ack',json.dumps({'scope':scope,'trace':trace,'attempt':safe_attempt,'first':captured.evidence(),'errors':errors},separators=(',',':')))
        root=Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-ready-{publication}-{warm}-{backend}-{time.time_ns()}.json').write_text(json.dumps({
            'outcome':outcome,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'source_bindings':{str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in
                [Path(__file__),root/'api/dfa_supervisor.py',root/'api/activity_dfa.py']},
            'warm':warm,'publication':publication,'scope':scope,'trace':trace,'attempt':attempt,
            'errors':errors,'worker_alive_after_cleanup':worker.is_alive(),
            'server_commit':'independent SQL visibility and Session return bracket durable commit; neither is local ACK',
            'perturbation':'one controlled post-validation renewal/ACK delay; SQLite direct boundary is not full service'},indent=2))


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_whole_api_expiry_before_locked_admission_rolls_back(both_origins,monkeypatch,tmp_path,first_renewal):
    from api import dfa_supervisor
    factory,owner=both_origins;_,run=confirmed(factory,owner)
    with factory() as db:db.get(Run,run['id']).status='failed';db.commit()
    sup=factory.dfa_supervisor;sup.allowed=False;sup.permission_until=0.;first_renewal(sup,factory)
    with factory() as db:
        deadline=db.get(Control,1).ready_until
        grants=sorted((g.id,g.binding_digest) for g in db.query(Grant).all())
    before=state(factory,run['id']);observations=[];attempt=None
    actual=dfa_supervisor.manual_admission
    def expired(db):
        # The full real API already validated rights/source/mode here. Wait for
        # the actual stored deadline, not a substituted clock or SQL pulse.
        while datetime.utcnow()<=deadline:time.sleep(.001)
        observations.append({'at':time.monotonic(),'wall':datetime.utcnow().isoformat(),
                             'deadline':deadline.isoformat()})
        return actual(db)
    monkeypatch.setattr(dfa_supervisor,'manual_admission',expired)
    try:
        with factory() as db:
            with pytest.raises(HTTPException) as rejected:
                service.change_run(db,owner,'123',run['id'],'retry',run['generation'])
        attempt={'status':rejected.value.status_code,'detail':rejected.value.detail}
        assert attempt=={'status':503,'detail':'DFA_CAPACITY_UNAVAILABLE'}
        assert observations and state(factory,run['id'])==before
        with factory() as db:assert sorted((g.id,g.binding_digest) for g in db.query(Grant).all())==grants
    finally:
        (tmp_path/'whole-api-expiry-evidence.json').write_text(json.dumps({
            'scope':'whole API real validation, final expiry refusal, owner transaction rollback',
            'observations':observations,'before':before,'after':state(factory,run['id']),
            'attempt':attempt},indent=2))


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('stage',['timely','first_expiry_observation','after_expiry','cross_expiry_commit'])
def test_admission_check_commit_and_pulse_expiry(both_origins,stage,monkeypatch,first_renewal,record_property):
    from api import dfa_rights, dfa_supervisor
    factory,owner=both_origins
    _,run=confirmed(factory,owner)
    with factory() as db:db.get(Run,run['id']).status='failed';db.commit()
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.
    previous=state(factory,run['id']);backend=factory.kw['bind'].dialect.name
    scope='whole_API_final_admission_boundary' if backend=='postgresql' or stage in ('first_expiry_observation','after_expiry') else 'direct_locked_admission_only'
    timing={};commits=[];attempt=None;request=None;deadline=None;primary_error=None;cleanup_error=None
    actual=dfa_supervisor.manual_admission
    def publish():
        nonlocal deadline
        assert deadline is None, 'exactly one prospective pulse'
        observed=first_renewal(supervisor,factory)
        deadline=datetime.fromisoformat(observed['deadline']);timing['deadline']=observed['deadline']
    def admitted(db):
        # PG owner validation has finished; control is not yet locked. SQLite
        # negative uses a pulse from a released session, never a control writer
        # waiting behind its own owner-write transaction.
        if deadline is None:publish()
        if stage in ('first_expiry_observation','after_expiry'):
            while datetime.utcnow()<=deadline:time.sleep(.001)
            timing['first_expired_wall']=datetime.utcnow().isoformat()
            if stage=='after_expiry':time.sleep(.025)
        timing['locked_check_wall']=datetime.utcnow().isoformat()
        return actual(db)
    def before_commit(db):
        commits.append({'invoked_at':time.monotonic(),'wall':datetime.utcnow().isoformat()})
        if stage=='cross_expiry_commit':
            while datetime.utcnow()<=deadline:time.sleep(.001)
            time.sleep(.01)
    monkeypatch.setattr(dfa_supervisor,'manual_admission',admitted)
    try:
        if backend=='sqlite':
            with factory() as db:
                dfa_rights.require_manual_mode(db,owner);service.require_authority(db,owner)
                assert service._current(db,db.get(Run,run['id']));db.rollback()
            publish()
        request=factory();event.listen(request,'before_commit',before_commit)
        try:
            if scope=='direct_locked_admission_only':
                with service.owner_write(request,owner):
                    dfa_rights.require_manual_mode(request,owner)
                    admission_id,accepted_at,epoch=admitted(request)
                    request.commit()
                    result={'admission_id':admission_id,'accepted_at':accepted_at}
            else:result=service.change_run(request,owner,'123',run['id'],'retry',run['generation'])
            attempt={'outcome':'accepted','admission_id':result['admission_id'],'accepted_at':result['accepted_at'].isoformat(),
                     'response_wall':datetime.utcnow().isoformat()}
        except HTTPException as exc:
            attempt={'outcome':'denied','status':exc.status_code,'detail':exc.detail,'response_wall':datetime.utcnow().isoformat()}
        if stage in ('timely','cross_expiry_commit'):
            assert attempt['outcome']=='accepted',attempt
            assert datetime.fromisoformat(attempt['accepted_at'])<deadline
            after=state(factory,run['id'])
            assert after['manual_sequence']==previous['manual_sequence']+1
            if scope=='direct_locked_admission_only':
                assert {k:v for k,v in after.items() if k!='manual_sequence'}=={k:v for k,v in previous.items() if k!='manual_sequence'}
            else:assert after['admission_id']==attempt['admission_id'] and after['status']=='queued'
            if stage=='cross_expiry_commit':assert datetime.fromisoformat(attempt['response_wall'])>deadline
        else:
            assert (attempt['outcome'],attempt['status'],attempt['detail'])==('denied',503,'DFA_CAPACITY_UNAVAILABLE')
            assert state(factory,run['id'])==previous
    except BaseException as exc:
        primary_error=failure(exc);raise
    finally:
        safe_attempt=None if attempt is None else {k:v for k,v in attempt.items() if k!='admission_id'}
        if attempt and attempt.get('admission_id'):safe_attempt['admission']=sha256(attempt['admission_id'].encode()).hexdigest()
        diagnostic={'scope':scope,'stage':stage,'timing':timing,'commit_invocations':commits,'attempt':safe_attempt,
                    'first_outcomes':[v.evidence() for v in first_renewal.outcomes],'primary_error':primary_error}
        record_property('dfa_pulse_boundary',json.dumps(diagnostic,separators=(',',':')))
        try:
            if request:
                event.remove(request,'before_commit',before_commit);request.close()
        except BaseException as exc:
            cleanup_error=failure(exc);record_property('dfa_pulse_cleanup',json.dumps(cleanup_error));raise
        finally:
            diagnostic['cleanup_error']=cleanup_error
        root=Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-pulse-boundary-{stage}-{backend}-{time.time_ns()}.json').write_text(json.dumps({
            'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),**diagnostic,
            'source_bindings':{str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),root/'api/dfa_supervisor.py',root/'api/activity_dfa.py']},
            'expiry_observation':'real stored deadline; no substituted time; SQLite positive is narrow boundary, not whole service'},indent=2))


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('change',['drain','epoch','incarnation'])
def test_readiness_publication_cannot_cross_concurrent_control_change(store,monkeypatch,first_renewal,change):
    factory,owner=store
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.;first_renewal(supervisor,factory)
    prior_permission=supervisor.permission_until
    with factory() as db:
        initial=db.get(Control,1);old_ready=initial.ready_until;old_sequence=initial.readiness_sequence
    actual=supervisor._bound
    def concurrent(db):
        row=actual(db)
        with factory() as controller:
            control=controller.get(Control,1)
            if change=='drain':control.drained=True
            elif change=='epoch':control.epoch+=1
            else:control.incarnation={**control.incarnation,'source':'different-synthetic-source'}
            controller.commit()
        supervisor.stop.set()  # One real stale publication attempt only.
        return row
    monkeypatch.setattr(supervisor,'_bound',concurrent)
    supervisor.controls=sessionmaker(bind=factory.kw['bind'])
    supervisor.stop.clear();supervisor.renew()
    assert supervisor.allowed is False and supervisor.permission_until==prior_permission
    assert supervisor.control_observation['state']=='generation_changed'
    with factory() as db:
        control=db.get(Control,1)
        assert control.readiness_sequence==old_sequence and control.ready_until==old_ready


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('fault',['drain','bound_error','session_close','snapshot_cleanup'])
def test_first_renewal_failure_is_retained_without_favorable_cycle(store,monkeypatch,first_renewal,fault):
    from tests.dfa_boundary_evidence import FirstRenewalOutcome
    factory,owner=store;sup=factory.dfa_supervisor
    sup.allowed=False;sup.permission_until=0.
    secret='synthetic-credential-canary SQL-parameter-canary'
    if fault=='drain':
        with factory() as db:db.get(Control,1).drained=True;db.commit()
    elif fault=='bound_error':
        actual=sup._bound
        def fail(db):actual(db);raise RuntimeError(secret)
        monkeypatch.setattr(sup,'_bound',fail)
    elif fault=='session_close':
        class CloseFailure(Session):
            def close(self):super().close();raise RuntimeError(secret)
        sup.controls=sessionmaker(class_=CloseFailure,bind=factory.kw['bind'])
    else:
        def fail_snapshot(self):raise RuntimeError(secret)
        monkeypatch.setattr(FirstRenewalOutcome,'capture_sql',fail_snapshot)
    with pytest.raises(AssertionError):first_renewal(sup,factory)
    observation=first_renewal.outcomes[0].evidence()
    assert len(first_renewal.outcomes)==1 and observation['worker_alive'] is False
    assert secret not in json.dumps(observation)
    assert observation['first']['stop_issuer']=='test_first_cycle_observation'
    if fault=='snapshot_cleanup':
        assert observation['first']['allowed'] and observation['first']['error'] is None
        assert observation['cleanup_errors'] and observation['sql'][-1]['event']=='ack'
    else:
        assert observation['first']['allowed'] is False
        assert not observation['cleanup_errors']
        if fault=='drain':assert observation['sql']==[]
        else:assert observation['first']['error']['class']=='RuntimeError'


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_first_real_commit_late_ack_remains_failed_setup(store,first_renewal):
    factory,owner=store;sup=factory.dfa_supervisor
    sup.allowed=False;sup.permission_until=0.
    with factory() as db:sequence=db.get(Control,1).readiness_sequence
    class DelayedACK(Session):
        def commit(self):super().commit();time.sleep(.30)
    sup.controls=sessionmaker(class_=DelayedACK,bind=factory.kw['bind'])
    with pytest.raises(AssertionError,match='FIRST_RENEWAL_SETUP_FAILURE'):first_renewal(sup,factory)
    observation=first_renewal.outcomes[0].evidence()
    assert observation['first']['observation']['state']=='deadline'
    assert observation['first']['allowed'] is False and observation['first']['error'] is None
    assert [e['event'] for e in observation['sql']]==['invoked','ack']
    assert observation['persisted']['sequence']==sequence+1
    assert datetime.utcnow()>datetime.fromisoformat(observation['persisted']['deadline'])
