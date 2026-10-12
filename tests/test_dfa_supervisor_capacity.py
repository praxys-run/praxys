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
                    observer.invalidation=None
                    caller=sys._getframe(1)
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
                    assert observer.retired.wait(5)
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


def test_100_healthy_synthetic_manual_admission_preemptions(both_origins,monkeypatch,tmp_path):
    overall_started=time.monotonic()
    overall_deadline=overall_started+600
    factory,owner=both_origins
    proof,manual=confirmed(factory,owner)
    with factory() as db: claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        row=db.get(Run,manual['id']);row.status='failed';row.error_code='synthetic_retry';db.commit()
    completion_plan=predeclare_automatic_completions(factory,owner,32)
    supervisor=factory.dfa_supervisor
    # The direct-step fixture grants long synthetic permission for setup only.
    # Real benchmark startup must obtain its own completed valid renewal ACK.
    supervisor.allowed=False;supervisor.permission_until=0.
    supervisor.controls=sessionmaker(bind=create_engine(factory.kw['bind'].url,pool_size=2,max_overflow=0,pool_timeout=.1,
                                                        connect_args={'timeout':.1}))
    real_popen=subprocess.Popen
    code='''import io,json,signal,sys,time
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
    def fixture_process(command,**kwargs):
        if command[-2:]==['-m','api.dfa_worker']:
            command=[sys.executable,'-E','-B','-c',code]
        return real_popen(command,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',fixture_process)
    progress=Path(__file__).resolve().parents[1]/f'.git/pr871-capacity-{time.time_ns()}-steps.jsonl'
    root=Path(__file__).resolve().parents[1]
    source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    from hashlib import sha256
    source_paths = {path.relative_to(root).as_posix()
        for family in ('api','analysis','sync','db') for path in (root/family).rglob('*.py')}
    source_paths.update({'tests/test_dfa_supervisor_capacity.py','tests/dfa_supervisor_harness.py',
                         'tests/test_activity_dfa.py','tests/test_dfa_origins.py','tests/dfa_capacity_measurement.py',
                         'tests/dfa_capacity_worker.py'})
    source_bindings={name:sha256((root/name).read_bytes()).hexdigest() for name in sorted(source_paths)}
    admission_denials=[]
    ingress=[]
    maximum_attempts=300
    requests=observed_requests(factory)
    eligibility_observations=[]
    accepted_outcomes=[]
    coverage_reason=None
    outcomes=[]
    error=[]
    initial_actor=supervisor.lane.actor()
    transitions=[initial_actor] if initial_actor else []
    committed_exits={}
    priority_evidence=PriorityEvidence(supervisor,monkeypatch)
    startup_evidence=None
    real_record=supervisor.lane.record
    def record(value):
        real_record(value)
        transitions.append(json.loads(json.dumps(value)))
    monkeypatch.setattr(supervisor.lane,'record',record)
    lifecycle=CapacityWorker(supervisor,error)
    real_record_exit=supervisor.record_exit
    def record_exit():
        lifecycle.record_exit(real_record_exit)
        value=supervisor.lane.actor()
        committed_exits[value['actor_token']]=time.monotonic()
    monkeypatch.setattr(supervisor,'record_exit',record_exit)
    lifecycle.start()
    try:
        # Predeclared300 ingress slots, including refusals and supplemental
        # idle/race admissions; never replenish terminal runs or resample a
        # genuinely failed accepted request. Stop early only at the stated goal.
        for trial in range(maximum_attempts):
            if not lifecycle.ingress_allowed():
                coverage_reason='supervisor_terminated';break
            if len(outcomes)>=100: break
            if len(ingress)>=maximum_attempts or time.monotonic()>=overall_deadline:
                coverage_reason='whole_run_budget';break
            with factory() as db:
                row=db.get(Run,manual['id'])
                if row.status=='complete':row.status='failed';db.commit()
                generation=row.generation;manual_input=row.input_digest
            admitted=None
            for attempt in range(3):
                if not lifecycle.ingress_allowed():
                    coverage_reason='supervisor_terminated';break
                if len(ingress)>=maximum_attempts or time.monotonic()>=overall_deadline:
                    coverage_reason='whole_run_budget';break
                qualification_deadline=min(time.monotonic()+15,overall_deadline)
                previous_state=None
                while True:
                    if not lifecycle.ingress_allowed():
                        coverage_reason='supervisor_terminated';break
                    eligibility=workload_eligibility(factory,owner)
                    signature=(eligibility['actor'],eligibility['automatic_states'])
                    if signature!=previous_state:
                        eligibility_observations.append(eligibility);previous_state=signature
                    if eligibility['eligible']:break
                    if time.monotonic()>=qualification_deadline:
                        coverage_reason='no_eligible_predeclared_workload';break
                    time.sleep(.01)
                if coverage_reason:break
                if startup_evidence is None:
                    startup_evidence=priority_evidence.startup_launch(eligibility['actor'])
                # Requalify exact actor/workload every ingress, including after
                # a denial. Do not select a favourable SQL pulse or duration.
                if not lifecycle.ingress_allowed():
                    coverage_reason='supervisor_terminated';break
                try:
                    admitted,entry=lifecycle.guarded_ingress(admission_attempt, requests,owner,manual['id'],generation,ingress,
                        {'trial':trial,'attempt':attempt,'eligibility':eligibility,
                         'cohort_elapsed_seconds':time.monotonic()-overall_started})
                except WorkerUnavailable:
                    coverage_reason='supervisor_terminated';break
                if admitted:
                    observation=observe_acceptance(factory,owner,admitted,entry,manual_input,
                        priority_evidence,transitions,committed_exits,overall_deadline,error,allow_existing_retirement=True)
                    accepted_outcomes.append(observation)
                    with progress.with_suffix('.accepted.jsonl').open('a') as stream:
                        stream.write(json.dumps({'ingress':entry,'observation':observation})+'\n')
                    # Service failures stay retained and fail certification;
                    # further accepted successes cannot replace them.
                    assert entry['outcome']=='accepted',entry
                    assert observation['service']=='complete',observation
                    assert not observation['reuse_violations'],observation
                    assert observation['classification'] in ('causal_preemption','retirement_race','already_retiring_service','idle_service'),observation
                    if observation['classification'] in ('causal_preemption','retirement_race','already_retiring_service'):
                        assert observation['retirement_within_budget'],observation
                    if observation['classification']=='causal_preemption':
                        assert observation['physical_exit_upper_seconds']<=5,observation
                        assert observation['durable_availability_upper_seconds']<=5,observation
                        assert observation['required_preemption'],observation
                    if observation['required_preemption']:
                        outcomes.append(observation)
                        with progress.open('a') as stream:stream.write(json.dumps(observation)+'\n')
                    break
                admission_denials.append(entry)
                with progress.with_suffix('.ingress.jsonl').open('a') as stream:
                    stream.write(json.dumps(entry)+'\n')
                if attempt==2:
                    coverage_reason='three_pre_admission_refusals';break
                entry['backoff_requested_seconds']=5
                if time.monotonic()+5>overall_deadline:
                    coverage_reason='whole_run_budget';break
                backoff=lifecycle.backoff(5)
                entry['backoff_elapsed_seconds']=backoff['elapsed_seconds']
                entry['backoff_interrupted']=backoff['interrupted']
                if not backoff['ingress_allowed_after']:
                    coverage_reason='supervisor_terminated';break
            if coverage_reason:break
        for previous,next_actor in zip(transitions,transitions[1:]):
            if next_actor['state']=='launching' and previous.get('actor_token') != next_actor.get('actor_token'):
                assert previous['state']=='idle'
                assert next_actor['launch_at']>=previous['exit_observed_at']
        lifecycle.assert_certifiable()
        assert time.monotonic()<=overall_deadline
        assert len(outcomes)==100, {'required_preemptions':len(outcomes),'accepted_outcomes':accepted_outcomes,'coverage_reason':coverage_reason}
        assert all(row['classification'] in ('causal_preemption','retirement_race','already_retiring_service','idle_service') for row in accepted_outcomes),accepted_outcomes
        assert max(row['durable_availability_upper_seconds'] for row in outcomes)<=5
        (tmp_path/'capacity.json').write_text(json.dumps(outcomes,indent=2))
        destination=Path(__file__).resolve().parents[1]/'test-screenshots/ui-quality/pr871'
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'synthetic-capacity.json').write_text(json.dumps({'source_head':source_head,'source_bindings':source_bindings,'profile':'one SQLite writer + two bounded control connections (renewal and lifecycle); 125ms start cadence, 250ms SQL admission pulse, no fast-window selection; 650 native RR; post-handshake ignored-TERM automatic fixture; real manual child computation',
            'startup_evidence':startup_evidence,
            'cohort':'100 causally proven accepted preemptions PLUS separate idle/race/persisted-TERM service acceptance outcomes; every ingress/time counts, not100mixed successes',
            'completion_plan':completion_plan,'accepted_outcomes':accepted_outcomes,'eligibility_observations':eligibility_observations,
            'measurement_scope':'cohort excluding fixture setup; full pytest duration reported separately',
            'attempts':len(ingress),'maximum_attempts':maximum_attempts,'maximum_seconds':600,
            'overall_elapsed_seconds':time.monotonic()-overall_started,
            'pre_admission_denial_rate':len(admission_denials)/len(ingress),
            'ingress_attempts':ingress,'pre_admission_denials':admission_denials,
            'trials':outcomes,'unproved':['raw-loading preemption','maximum-input/native-compute preemption','output-transfer preemption','Azure/API/sync contention','60-minute mixed-load soak','cross-host placement/handover']},indent=2))
    finally:
        primary=sys.exc_info()[1]
        lifecycle.close()
        try:
            progress.with_suffix('.ingress-final.json').write_text(json.dumps({
                'source_head':source_head,'source_bindings':source_bindings,'attempts':ingress,
                'worker_terminal':lifecycle.evidence(),
                'primary_error':failure(primary) if primary else None,
                'committed_exits':committed_exits,'physical_transitions':transitions,
                'terminal_snapshot':lifecycle.snapshot(),
                'completion_plan':completion_plan,'eligibility_observations':eligibility_observations,
                'accepted_outcomes':accepted_outcomes,'coverage_reason':coverage_reason,
                'renewal_decisions':priority_evidence.renewal_decisions,
                'startup_evidence':startup_evidence,'completed_valid_renewals':priority_evidence.renewals,
                'retirements_observed':len(outcomes),'priority_observations':priority_evidence.priorities,
                'retirement_observations':priority_evidence.retirements,
                'completed_trials':sum(row['service']=='complete' for row in accepted_outcomes),
                'required_causal_preemptions':len(outcomes),
                'elapsed_seconds':time.monotonic()-overall_started,
                'denial_rate':len(admission_denials)/len(ingress) if ingress else None},indent=2))
        except BaseException as retention_error:
            # A ledger I/O error cannot replace the already retained primary.
            if primary is not None:
                raise primary.with_traceback(primary.__traceback__) from retention_error
            raise
        finally:
            if primary is None:
                lifecycle.assert_certifiable()



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


@pytest.mark.parametrize('pause_phase',['before_commit','after_commit','after_commit_delayed_reason'])
def test_preemption_requires_committed_priority_not_ingress_or_response(both_origins,monkeypatch,pause_phase):
    factory,owner=both_origins
    _,manual=confirmed(factory,owner)
    with factory() as db:claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        row=db.get(Run,manual['id']);row.status='failed';generation=row.generation;db.commit()
    complete_unit(factory,owner)
    supervisor=factory.dfa_supervisor
    supervisor.controls=sessionmaker(bind=create_engine(factory.kw['bind'].url,pool_size=1,max_overflow=0,
        pool_timeout=.1,connect_args={'timeout':.1}))
    actual_popen=subprocess.Popen
    code="import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
    def fixture_child(command,**kw):
        if command[-2:]==['-m','api.dfa_worker']:command=[sys.executable,'-E','-B','-c',code]
        return actual_popen(command,**kw)
    monkeypatch.setattr(subprocess,'Popen',fixture_child)
    evidence=PriorityEvidence(supervisor,monkeypatch)
    errors=[]
    def run():
        try:supervisor.run()
        except Exception as exc:errors.append(exc)
    worker=threading.Thread(target=run);worker.start()
    admission_session=factory()
    ledger=[];commit_observations=[]
    def pause(db):
        callback={'entered_monotonic':time.monotonic()}
        commit_observations.append(callback)
        if pause_phase=='before_commit':db.flush()
        else:evidence.resume.set()
        assert evidence.retired.wait(5),'Actual old actor did not exit'
        callback['released_monotonic']=time.monotonic()
    commit_event='before_commit' if pause_phase=='before_commit' else 'after_commit'
    event.listen(admission_session,commit_event,pause)
    class RequestFactory:
        def __call__(self):return admission_session
    # Admission snapshots must use separate readers, not the request session.
    actual_snapshot=admission_snapshot
    monkeypatch.setattr(sys.modules[__name__],'admission_snapshot',
        lambda selected,run_id:actual_snapshot(factory,run_id))
    try:
        deadline=time.monotonic()+10
        while True:
            with factory() as db:
                control=db.get(Control,1);actor=control.actor
                ready=control.readiness_sequence>0 and control.ready_until and control.ready_until>datetime.utcnow()
            if ready and actor and actor.get('state')=='occupied':break
            assert time.monotonic()<deadline,errors
            time.sleep(.01)
        # Deterministic boundary regression only: start from an actual
        # completed renewal, retaining its independent750ms physical timer.
        # Before-commit expiry deliberately holds renewal until that timer
        # retires the old group; unparked profile/cohort code never uses this.
        evidence.hold_reason_until_exit=pause_phase=='after_commit_delayed_reason'
        evidence.park_after_renewal.set()
        assert evidence.parked.wait(3),'Real completed renewal did not reach synchronization point'
        # Only this request's commit is paused; renewal and 750ms expiry remain real.
        admitted,entry=admission_attempt(RequestFactory(),owner,manual['id'],generation,ledger,{})
        actor=entry['readiness']['actor']
        assert admitted and commit_observations
        retirement=next(value for value in evidence.retirements if value['actor_token']==actor['actor_token'])
        assert entry['before_monotonic']<=retirement['exit_observed_at']<entry['after_monotonic']
        trace={'phase':pause_phase,'ingress':entry,'admitted_id':admitted['id'],
               'admitted_generation':admitted['generation'],'admission_id':admitted['admission_id'],
               'commit_callback':commit_observations[0],
               'retirement':retirement,'priority_observations':evidence.priorities}
        from hashlib import sha256
        trace['source_test_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
        trace_path=Path(__file__).resolve().parents[1]/f'.git/pr871-causality-{pause_phase}-{time.time_ns()}.json'
        trace_path.write_text(json.dumps(trace,indent=2))
        if pause_phase=='before_commit':
            assert commit_observations[0]['entered_monotonic']<=retirement['exit_observed_at']<commit_observations[0]['released_monotonic']
            with pytest.raises(AssertionError):evidence.accepted_preemption(admitted,actor,entry)
        else:
            proof=evidence.accepted_preemption(admitted,actor,entry)
            assert proof['priority_invalidation']['admission_id']==admitted['admission_id']
            assert commit_observations[0]['entered_monotonic']<=proof['priority_invalidation']['observed_monotonic']
            assert proof['exit_observed_at']<=commit_observations[0]['released_monotonic']
            if pause_phase=='after_commit_delayed_reason':assert proof['reason'] is None
            for changed in ({**admitted,'generation':admitted['generation']+1},
                            {**admitted,'admission_id':'another-admission'}):
                with pytest.raises(AssertionError):evidence.accepted_preemption(changed,actor,entry)
            with pytest.raises(AssertionError):
                evidence.accepted_preemption(admitted,{**actor,'actor_token':'another-actor'},entry)
    finally:
        evidence.resume.set()
        event.remove(admission_session,commit_event,pause)
        admission_session.close();supervisor.stop.set();worker.join(10)
        assert not worker.is_alive()
