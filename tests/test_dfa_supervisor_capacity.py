"""Measured healthy synthetic retirement cell; live/full-input cells remain unproved."""
from datetime import datetime,timedelta
from pathlib import Path
import json
import subprocess
import sys
import threading
import time
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Query, defer, Session

from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_activity_dfa import store, confirmed
from api import activity_dfa as service
from db.models import ActivityDFARun as Run, ActivityDFAControl as Control
from tests.dfa_capacity_measurement import observed_requests, workload_eligibility, observe_acceptance
from tests.dfa_capacity_worker import CapacityWorker, WorkerUnavailable, failure


def admission_snapshot(factory, run_id):
    """Independent post-transaction read; an old admission is not a new one."""
    with factory() as db:
        row=db.get(Run,run_id);control=db.get(Control,1)
        return {'id':row.id,'input_digest':row.input_digest,'status':row.status,'generation':row.generation,'admission_id':row.admission_id,
                'accepted_at':row.accepted_at.isoformat() if row.accepted_at else None,
                'execution_epoch':row.execution_epoch,'manual_sequence':control.manual_sequence}


def admission_attempt(factory, owner, run_id, generation, ledger, observation):
    previous=admission_snapshot(factory,run_id)
    before=time.monotonic()
    with factory() as db:
        control=db.get(Control,1)
        readiness={'sequence':control.readiness_sequence,
                   'ready_until':control.ready_until.isoformat() if control.ready_until else None,
                   'enabled':control.enabled,'drained':control.drained,'epoch':control.epoch,
                   'actor':control.actor,
                   'actor_state':control.actor.get('state') if control.actor else None,
                   'observed_at_utc':datetime.utcnow().isoformat(),'observed_monotonic':time.monotonic()}
    record={**observation,'before_monotonic':before,'before_durable':previous,'readiness':readiness,
            'backoff_requested_seconds':0,'backoff_elapsed_seconds':0}
    ledger.append(record)
    try:
        with factory() as db:
            db.info['capacity_admission_record']=record
            accepted=service.change_run(db,owner,'123',run_id,'retry',generation)
    except Exception as exc:
        record.update(after_monotonic=time.monotonic(),after_durable=admission_snapshot(factory,run_id),
                      outcome='exception',http_status=getattr(exc,'status_code',None),
                      detail=getattr(exc,'detail',type(exc).__name__))
        record['no_durable_acceptance']=record['before_durable']==record['after_durable']
        after=record['after_durable']
        if (after['admission_id'] and after['admission_id']!=previous['admission_id']
                and after['accepted_at'] and after['manual_sequence']>previous['manual_sequence']):
            record['outcome']='accepted_error'
            return {'id':run_id,'generation':after['generation'],'admission_id':after['admission_id']},record
        if isinstance(exc,HTTPException) and exc.status_code==503 and exc.detail=='DFA_CAPACITY_UNAVAILABLE':
            # Never relabel a post-commit exception as a pre-admission denial.
            assert record['no_durable_acceptance'],record
            record['outcome']='pre_admission_denied'
            return None,record
        raise
    # Record acknowledged acceptance before any independent-read/classification assertion.
    record.update(after_monotonic=time.monotonic(),outcome='accepted',accepted_response={key:accepted[key] for key in ('id','generation','admission_id')})
    record['after_durable']=admission_snapshot(factory,run_id)
    after=record['after_durable']
    record['acceptance_consistent']=bool(after['accepted_at'] and after['manual_sequence']==previous['manual_sequence']+1
        and all(after[k]==accepted[k] for k in ('id','generation','admission_id')))
    # Observe actual durable service even when response metadata is inconsistent.
    return {k:after[k] for k in ('id','generation','admission_id')},record


class PriorityEvidence:
    """Observe real committed priority queries and the actual retirement cause.

    Reuses the existing control/query results and observes real journal/signal
    completion. Local journal reads/timestamps add unquantified overhead; no
    readiness, watchdog, admission or retirement decisions are changed.
    """
    def __init__(self, supervisor, monkeypatch):
        self.priorities=[];self.retirements=[];self.renewals=[];self.renewal_decisions=[];self.retired=threading.Event()
        self.invalidation=None
        self.renewal_event=threading.Event();self.renewal_target=None;self.subsequent_receipt=None
        self.park_after_renewal=threading.Event();self.parked=threading.Event();self.resume=threading.Event()
        self.hold_reason_until_exit=False
        observer=self
        class ObservedQuery(Query):
            def filter_by(self, **kw):
                value=super().filter_by(**kw)
                value.manual_priority=kw.get('origin')=='manual' and kw.get('status')=='queued'
                return value
            def first(self):
                value=super().first()
                if value and getattr(self,'manual_priority',False):
                    manual=self.session.get(Run,value.id,options=[defer(Run.result)])
                    control=self.session.get(Control,1)
                    actor=supervisor.lane.actor()
                    with supervisor.lock:
                        active=dict(supervisor.active) if supervisor.active else None
                    if (manual and manual.status=='queued' and manual.admission_id and manual.accepted_at
                            and active and active['origin']=='automatic' and actor and actor['state']=='occupied'
                            and control.actor and control.actor.get('actor_token')==actor['actor_token']
                            and actor['binding']=={key:active[key] for key in ('generation','epoch','input')}):
                        observer.priorities.append({'manual_id':manual.id,'admission_id':manual.admission_id,
                            'generation':manual.generation,'execution_epoch':manual.execution_epoch,
                            'manual_sequence':self.session.query(Control.manual_sequence).filter_by(id=1).scalar(),
                            'actor_token':actor['actor_token'],
                            'active_id':active['id'],'active_binding':actor['binding'],
                            'observed_monotonic':time.monotonic()})
                return value
        # The actual invalidation precedes the independently assigned reason
        # string. Observe that write; never substitute a value or a deadline.
        original_class=type(supervisor)
        renewal_code=supervisor.renew.__func__.__code__
        class ObservedSupervisor(original_class):
            def __setattr__(self,name,value):
                if name=='control_observation':
                    caller=sys._getframe(1)
                    if caller.f_code is renewal_code:
                        local=caller.f_locals;exc=local.get('exc')
                        observer.renewal_decisions.append({'at':time.monotonic(),'observation':dict(value),
                            'valid':local.get('valid'),'priority':local.get('priority'),'allowed':self.allowed,
                            'permission_until':self.permission_until,
                            'exception_class':type(exc).__name__ if exc else None,
                            'dbapi_class':type(getattr(exc,'orig',None)).__name__ if exc and getattr(exc,'orig',None) else None,
                            'sqlstate':getattr(getattr(exc,'orig',None),'sqlstate',None),
                            'sqlite_errorcode':getattr(getattr(exc,'orig',None),'sqlite_errorcode',None)})
                if name=='permission_until':
                    caller=sys._getframe(1)
                    local=caller.f_locals
                    session=local.get('db')
                    receipt=session.info.get('capacity_renewal_commit') if session is not None else None
                    if (caller.f_code is renewal_code and local.get('valid') is True
                            and local.get('updated')==1 and receipt and receipt.get('completed_at') is not None):
                        previous_permission=self.permission_until
                        super().__setattr__(name,value)
                        actor=self.lane.actor()
                        completed={**receipt,'permission_granted_at':time.monotonic(),
                            'permission_until':self.permission_until,'iteration_started':local['started'],
                            'actor':json.loads(json.dumps(actor)) if actor else None,
                            'active':dict(local['active']) if local.get('active') else None,
                            'previous_permission_until':previous_permission}
                        observer.renewals.append(completed)
                        return
                if name=='allowed':
                    caller=sys._getframe(1)
                    if caller.f_code is renewal_code: observer.invalidation=None
                    local=caller.f_locals
                    latest=observer.priorities[-1] if observer.priorities else None
                    active=local.get('active')
                    if (value is False and caller.f_code is renewal_code and local.get('valid') is False
                            and 'exc' not in local and latest and active and active['origin']=='automatic'
                            and latest['active_id']==active['id']
                            and latest['observed_monotonic']>=local['started']):
                        observer.invalidation={**latest,'iteration_started':local['started'],
                            'before_allowed_false_monotonic':time.monotonic()}
                if name=='retirement_reason' and value=='priority' and observer.hold_reason_until_exit:
                    # Delay only this derived string, never the coherent local
                    # decision/state lock or genuine physical permission.
                    observer.delayed_reason=value
                    return
                super().__setattr__(name,value)
                if name=='control_observation' and value.get('state')=='ready' and observer.renewals:
                    completed=observer.renewals[-1];target=observer.renewal_target;actor=self.lane.actor()
                    if (target and actor and self.allowed and completed['iteration_started']>=target['armed_at']
                            and completed['permission_until']==self.permission_until>completed['previous_permission_until']
                            and completed.get('active') and completed['active']['origin']=='automatic'
                            and {k:completed['active'][k] for k in ('generation','epoch','input')}==actor['binding']
                            and all(actor.get(k)==target['actor'].get(k)==completed['actor'].get(k)
                                for k in ('actor_token','binding','incarnation','identity'))
                            and actor.get('state')=='occupied' and completed['epoch']==int(actor['binding']['epoch'])
                            and completed['incarnation']==actor['incarnation']):
                        observer.subsequent_receipt=completed;observer.renewal_event.set()
        monkeypatch.setattr(supervisor,'__class__',ObservedSupervisor)
        class ObservedSession(Session):
            def commit(self):
                caller=sys._getframe(1)
                local=caller.f_locals
                # Capture already-loaded metadata before commit expires ORM
                # state. Observation adds no DB reads or permission decisions.
                if caller.f_code is renewal_code and local.get('valid') is True and local.get('updated')==1:
                    row=local['row']
                    self.info['capacity_renewal_commit']={'epoch':row.epoch,
                        'incarnation':dict(row.incarnation),'readiness_sequence':row.readiness_sequence+1}
                super().commit()
                self.info['capacity_actual_commit_completed']=True
                if self.info.get('capacity_renewal_commit'):
                    self.info['capacity_renewal_commit']['completed_at']=time.monotonic()
            def close(self):
                completed=self.info.get('capacity_actual_commit_completed')
                super().close()
                # Positive regression synchronization only. A real completed
                # renewal supplied the existing 750ms lease; its timer stays live.
                if (threading.current_thread().name=='dfa-control' and completed
                        and supervisor.control_observation['state']=='ready'
                        and observer.park_after_renewal.is_set()):
                    observer.park_after_renewal.clear();observer.parked.set()
                    assert observer.resume.wait(5)
        supervisor.controls=sessionmaker(class_=ObservedSession,query_cls=ObservedQuery,**supervisor.controls.kw)
        from api import dfa_physical
        real_record=supervisor.lane.record;real_killpg=dfa_physical.os.killpg
        retire_code=supervisor.lane.retire.__func__.__code__
        observer.retirement_dispatches=[]
        def record(value):
            real_record(value)
            caller=sys._getframe(1)
            # Lifecycle observers may wrap record; retain the actual retire frame.
            for _ in range(3):
                if caller.f_code is retire_code or caller.f_back is None:break
                caller=caller.f_back
            if caller.f_code is retire_code and caller.f_locals.get('value') is value and value.get('state')=='retiring':
                observer.retirement_dispatches.append({'actor':json.loads(json.dumps(value)),
                    'journal_persisted_at':time.monotonic()})
        def killpg(pgid,sig):
            result=real_killpg(pgid,sig)
            caller=sys._getframe(1)
            if caller.f_code is retire_code and sig==dfa_physical.signal.SIGTERM:
                value=caller.f_locals['value'];members=caller.f_locals['members']
                matches=[d for d in observer.retirement_dispatches if d['actor']['actor_token']==value['actor_token']]
                if len(matches)==1 and value['identity']['pgid']==pgid and members:
                    matches[0].update(term_dispatch_completed_at=time.monotonic(),pgid=pgid,
                        dispatch_identity=dict(value['identity']),live_members=json.loads(json.dumps(members)))
            return result
        monkeypatch.setattr(supervisor.lane,'record',record)
        monkeypatch.setattr(dfa_physical.os,'killpg',killpg)
        real_retire=supervisor.lane.retire
        def retire(*args,**kwargs):
            actor=supervisor.lane.actor()
            reason=supervisor.retirement_reason
            started=time.monotonic()
            allowed=supervisor.allowed
            invalidation=observer.invalidation
            priority=dict(invalidation) if invalidation and actor and invalidation['actor_token']==actor.get('actor_token') else None
            result=real_retire(*args,**kwargs)
            exited=supervisor.lane.actor()
            if actor and actor.get('state')=='occupied' and exited and exited.get('state')=='idle':
                observer.retirements.append({'actor_token':actor['actor_token'],'actor_snapshot':json.loads(json.dumps(actor)),'reason':reason,
                    'allowed_at_start':allowed,'started_monotonic':started,'priority_invalidation':priority,
                    'exit_observed_at':exited['exit_observed_at'],
                    'dispatches':[json.loads(json.dumps(d)) for d in observer.retirement_dispatches if d['actor']['actor_token']==actor['actor_token']]})
                observer.retired.set()
                if getattr(observer,'delayed_reason',None):
                    super(type(supervisor),supervisor).__setattr__('retirement_reason',observer.delayed_reason)
                    observer.delayed_reason=None
            return result
        monkeypatch.setattr(supervisor.lane,'retire',retire)

    def arm_subsequent_renewal(self, actor):
        self.renewal_event.clear();self.subsequent_receipt=None
        self.renewal_target={'actor':json.loads(json.dumps(actor)),'armed_at':time.monotonic()}

    def startup_launch(self, actor):
        matching=[value for value in self.renewals
            if value['incarnation']==actor['incarnation'] and str(value['epoch'])==actor['binding']['epoch']
            and value['completed_at']<=value['permission_granted_at']<=actor['launch_at']<value['permission_until']]
        assert matching, {'actor':actor,'completed_valid_renewals':self.renewals}
        first=matching[0]
        from api.dfa_physical import PROFILE
        assert first['completed_at']-first['iteration_started']<PROFILE['poll_seconds'],first
        assert first['readiness_sequence']>0
        assert actor['launch_at']<=actor['process_start_observed_at']
        return {'actor':actor,'completed_valid_renewal':first}

    def accepted_preemption(self, admitted, actor, entry):
        matching=[value for value in self.retirements if value['actor_token']==actor['actor_token']]
        assert len(matching)==1,matching
        retirement=matching[0];priority=retirement['priority_invalidation']
        assert retirement['allowed_at_start'] is False and priority,retirement
        assert priority['manual_id']==admitted['id']
        assert priority['admission_id']==admitted['admission_id']
        assert priority['generation']==admitted['generation']
        assert priority['execution_epoch']==entry['after_durable']['execution_epoch']
        assert priority['manual_sequence']==entry['after_durable']['manual_sequence']
        assert priority['actor_token']==actor['actor_token']
        assert priority['active_binding']==actor['binding']
        assert entry['before_monotonic']<=priority['observed_monotonic']<=priority['before_allowed_false_monotonic']<=retirement['started_monotonic']<=retirement['exit_observed_at']
        # No comparison with response time: post-commit preemption can be faster.
        return retirement


def predeclare_automatic_completions(factory, owner, count):
    """Finite independent inputs; no terminal run reset or adaptive replenishment."""
    from datetime import date
    from tests.test_activity_dfa import synthetic_fit
    from db import sync_writer
    from db.models import Activity, GarminConnectIQJob, GarminConnectIQItem, ActivityDFASyncReceipt
    plan=[]
    factory.dfa_modes[owner] = True  # Synthetic automatic mode for new-sync inventory.
    with factory() as db:
        for number in range(count):
            activity_id=f'capacity-{number:03d}'
            db.add(Activity(user_id=owner,activity_id=activity_id,date=date.today(),source='garmin',activity_type='new_running_subtype'))
            snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account',activity_id,synthetic_fit(transport=True),db)
            sync_writer.write_garmin_fit_parse(snapshot,db)
            job=GarminConnectIQJob(user_id=owner,account_id='account',credential_generation='synthetic',region='international',kind='daily',status='complete')
            db.add(job);db.flush()
            item=GarminConnectIQItem(user_id=owner,job_id=job.id,activity_id=activity_id,status='complete')
            db.add(item);db.flush()
            sync_writer.write_dfa_sync_completion(db,job,item,[snapshot])
            receipt=db.query(ActivityDFASyncReceipt).filter_by(user_id=owner).filter(
                ActivityDFASyncReceipt.recording_ref['activity_id'].as_string()==activity_id).one()
            assert receipt.disposition=='pending'
            plan.append({'activity_id':activity_id,'snapshot_id':snapshot.id,'parse_id':snapshot.active_parse_id,
                         'job_id':job.id,'item_id':item.id,'receipt_id':receipt.id,'completion_revision':receipt.completion_revision})
        db.commit()
    return plan





@pytest.mark.parametrize('after_commit',[False,True])
def test_capacity_refusal_must_prove_no_new_durable_admission(store,monkeypatch,after_commit):
    factory,owner=store
    _,run=confirmed(factory,owner)
    with factory() as db:
        row=db.get(Run,run['id']);row.status='failed';generation=row.generation;db.commit()
    actual=service.change_run
    def refused(*args,**kwargs):
        if after_commit:actual(*args,**kwargs)
        raise HTTPException(503,'DFA_CAPACITY_UNAVAILABLE')
    monkeypatch.setattr(service,'change_run',refused)
    ledger=[]
    if after_commit:
        accepted,entry=admission_attempt(factory,owner,run['id'],generation,ledger,{})
        assert accepted['admission_id']==entry['after_durable']['admission_id']
        assert entry['no_durable_acceptance'] is False
        assert entry['outcome']=='accepted_error' and entry['http_status']==503
    else:
        accepted,entry=admission_attempt(factory,owner,run['id'],generation,ledger,{})
        assert accepted is None and entry['no_durable_acceptance'] is True
        assert entry['outcome']=='pre_admission_denied'
        assert entry['before_durable']==admission_snapshot(factory,run['id'])


@pytest.mark.parametrize('status,detail',[(403,'DFA_PROCESSING_NOT_AUTHORIZED'),(503,'DFA_RESTORE_REPLAY_UNAVAILABLE')])
def test_noncapacity_admission_failures_are_not_retryable_denials(store,monkeypatch,status,detail):
    factory,owner=store
    _,run=confirmed(factory,owner)
    def refused(*args,**kwargs):raise HTTPException(status,detail)
    monkeypatch.setattr(service,'change_run',refused)
    ledger=[]
    with pytest.raises(HTTPException) as error:
        admission_attempt(factory,owner,run['id'],run['generation'],ledger,{})
    assert error.value.status_code==status and error.value.detail==detail
    assert len(ledger)==1 and ledger[0]['outcome']=='exception'
