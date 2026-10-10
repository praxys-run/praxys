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


def state(factory, run_id):
    with factory() as db:
        run = db.get(Run, run_id); control = db.get(Control, 1)
        return {'generation':run.generation,'admission_id':run.admission_id,'status':run.status,
                'manual_sequence':control.manual_sequence}


def once(supervisor, factory):
    class Completed(Session):
        def commit(self):
            super().commit();supervisor.stop.set()
    supervisor.controls=sessionmaker(bind=factory.kw['bind'],class_=Completed)
    supervisor.stop.clear()
    worker=threading.Thread(target=supervisor.renew);worker.start();worker.join(3)
    if worker.is_alive():supervisor.stop.set();worker.join(1)
    assert not worker.is_alive(), supervisor.control_observation
    assert supervisor.allowed and supervisor.control_observation['state']=='ready'
    supervisor.stop.clear()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('warm',[False,True])
@pytest.mark.parametrize('publication',['late_publish','timely_publish_late_ack'])
def test_sql_publication_and_local_ack_are_distinct(store,warm,publication):
    factory,owner=store
    _,run=confirmed(factory,owner)
    with factory() as db:db.get(Run,run['id']).status='failed';db.commit()
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.
    if warm:once(supervisor,factory)
    prior_permission=supervisor.permission_until
    prior_state=state(factory,run['id'])
    published=threading.Event();release=threading.Event();trace=[];errors=[]
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
    def renew():
        try:supervisor.renew()
        except Exception as exc:errors.append(type(exc).__name__)
    worker=threading.Thread(target=renew);worker.start()
    outcome='failed';attempt=None
    try:
        assert published.wait(2),errors
        with factory() as db:
            control=db.get(Control,1)
            trace.append({'event':'independent_sql_visible','at':time.monotonic(),
                'ready_until':control.ready_until.isoformat(),'wall':datetime.utcnow().isoformat(),
                'sequence':control.readiness_sequence})
        # The real commit is independently visible while supervisor ACK/local
        # state is still blocked. No clock, permission or priority is fabricated.
        assert supervisor.permission_until==prior_permission
        assert supervisor.allowed is warm
        before=time.monotonic()
        try:
            with factory() as db:
                admitted=service.change_run(db,owner,'123',run['id'],'retry',run['generation'])
            attempt={'outcome':'accepted','before':before,'after':time.monotonic(),'admission_id':admitted['admission_id']}
        except HTTPException as exc:
            attempt={'outcome':'denied','before':before,'after':time.monotonic(),'status':exc.status_code,'detail':exc.detail}
        if publication=='late_publish':
            assert attempt['outcome']=='denied'
            assert (attempt['status'],attempt['detail'])==(503,'DFA_CAPACITY_UNAVAILABLE')
            assert state(factory,run['id'])==prior_state
        else:
            assert attempt['outcome']=='accepted',attempt
            # Preserve the accepted request when later ACK misses the budget.
            with factory() as db:
                assert db.get(Run,run['id']).admission_id==attempt['admission_id']
        # Ensure the eventual ACK misses250ms; this cannot rewrite admission.
        remaining=.31-(time.monotonic()-trace[0]['at'])
        if remaining>0:time.sleep(remaining)
        release.set();worker.join(2)
        assert not worker.is_alive() and not errors
        assert supervisor.allowed is False and supervisor.permission_until==prior_permission
        if publication=='timely_publish_late_ack':
            with factory() as db:
                row=db.get(Run,run['id']);assert row.status=='queued' and row.admission_id==attempt['admission_id']
        outcome='passed'
    finally:
        release.set();supervisor.stop.set();worker.join(2)
        root=Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-ready-{publication}-{warm}-{factory.kw["bind"].dialect.name}-{time.time_ns()}.json').write_text(json.dumps({
            'outcome':outcome,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'source_bindings':{str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in
                [Path(__file__),root/'api/dfa_supervisor.py',root/'api/activity_dfa.py']},
            'warm':warm,'publication':publication,'trace':trace,'attempt':attempt,'errors':errors,
            'server_commit':'not timestamped; independent visibility and Session commit return bracket it; neither is local permission ACK',
            'perturbation':'controlled commit/publication acknowledgement delay in this boundary negative, never used in cohort'},indent=2))


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('stage',['timely','first_expiry_observation','after_expiry','cross_expiry_commit'])
def test_admission_check_commit_and_pulse_expiry(store,stage):
    factory,owner=store
    _,run=confirmed(factory,owner)
    with factory() as db:db.get(Run,run['id']).status='failed';db.commit()
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.;once(supervisor,factory)
    previous=state(factory,run['id'])
    with factory() as db:deadline=db.get(Control,1).ready_until
    timing={'deadline':deadline.isoformat()};commits=[];attempt=None
    if stage in ('first_expiry_observation','after_expiry'):
        while datetime.utcnow()<deadline:time.sleep(.001)
        timing['first_expired_wall']=datetime.utcnow().isoformat()
        if stage=='after_expiry':time.sleep(.025)
    request=factory()
    def before_commit(db):
        commits.append({'invoked_at':time.monotonic(),'wall':datetime.utcnow().isoformat()})
        if stage=='cross_expiry_commit':
            while datetime.utcnow()<=deadline:time.sleep(.001)
            time.sleep(.01)
    event.listen(request,'before_commit',before_commit)
    try:
        try:
            result=service.change_run(request,owner,'123',run['id'],'retry',run['generation'])
            attempt={'outcome':'accepted','admission_id':result['admission_id'],'accepted_at':result['accepted_at'].isoformat(),
                     'response_wall':datetime.utcnow().isoformat()}
        except HTTPException as exc:
            attempt={'outcome':'denied','status':exc.status_code,'detail':exc.detail,'response_wall':datetime.utcnow().isoformat()}
        if stage in ('timely','cross_expiry_commit'):
            assert attempt['outcome']=='accepted',attempt
            assert datetime.fromisoformat(attempt['accepted_at'])<deadline
            with factory() as db:
                row=db.get(Run,run['id']);assert row.admission_id==attempt['admission_id'] and row.status=='queued'
            if stage=='cross_expiry_commit':assert datetime.fromisoformat(attempt['response_wall'])>deadline
        else:
            assert (attempt['outcome'],attempt['status'],attempt['detail'])==('denied',503,'DFA_CAPACITY_UNAVAILABLE')
            assert state(factory,run['id'])==previous
    finally:
        event.remove(request,'before_commit',before_commit);request.close()
        root=Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-pulse-boundary-{stage}-{factory.kw["bind"].dialect.name}-{time.time_ns()}.json').write_text(json.dumps({
            'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'timing':timing,'commit_invocations':commits,'attempt':attempt,
            'source_bindings':{str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),root/'api/dfa_supervisor.py',root/'api/activity_dfa.py']},
            'expiry_observation':'real wall clock bracket, not exact mathematical equality or substituted time'},indent=2))


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('change',['drain','epoch','incarnation'])
def test_readiness_publication_cannot_cross_concurrent_control_change(store,monkeypatch,change):
    factory,owner=store
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.;once(supervisor,factory)
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
