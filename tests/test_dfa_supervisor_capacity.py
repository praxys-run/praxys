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


def admission_snapshot(factory, run_id):
    """Independent post-transaction read; an old admission is not a new one."""
    with factory() as db:
        row=db.get(Run,run_id);control=db.get(Control,1)
        return {'status':row.status,'generation':row.generation,'admission_id':row.admission_id,
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
            accepted=service.change_run(db,owner,'123',run_id,'retry',generation)
    except Exception as exc:
        record.update(after_monotonic=time.monotonic(),after_durable=admission_snapshot(factory,run_id),
                      outcome='exception',http_status=getattr(exc,'status_code',None),
                      detail=getattr(exc,'detail',type(exc).__name__))
        record['no_durable_acceptance']=record['before_durable']==record['after_durable']
        if isinstance(exc,HTTPException) and exc.status_code==503 and exc.detail=='DFA_CAPACITY_UNAVAILABLE':
            # Never relabel a post-commit exception as a pre-admission denial.
            assert record['no_durable_acceptance'],record
            record['outcome']='pre_admission_denied'
            return None,record
        raise
    record.update(after_monotonic=time.monotonic(),after_durable=admission_snapshot(factory,run_id),outcome='accepted')
    assert record['after_durable']['admission_id']==accepted['admission_id']
    assert record['after_durable']['accepted_at'] and record['after_durable']['generation']==accepted['generation']
    assert record['after_durable']['manual_sequence']==previous['manual_sequence']+1
    return accepted,record


class PriorityEvidence:
    """Observe real committed priority queries and the actual retirement cause.

    Uses only the supervisor's existing control connection and query results;
    no readiness, watchdog, admission or retirement decisions are changed.
    """
    def __init__(self, supervisor, monkeypatch):
        self.priorities=[];self.retirements=[];self.retired=threading.Event()
        self.invalidation=None
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
        monkeypatch.setattr(supervisor,'__class__',ObservedSupervisor)
        class ObservedSession(Session):
            def commit(self):
                super().commit()
                self.info['capacity_actual_commit_completed']=True
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
                observer.retirements.append({'actor_token':actor['actor_token'],'reason':reason,
                    'allowed_at_start':allowed,'started_monotonic':started,'priority_invalidation':priority,
                    'exit_observed_at':exited['exit_observed_at']})
                observer.retired.set()
            return result
        monkeypatch.setattr(supervisor.lane,'retire',retire)

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


def test_100_healthy_synthetic_manual_admission_preemptions(both_origins,monkeypatch,tmp_path):
    factory,owner=both_origins
    proof,manual=confirmed(factory,owner)
    with factory() as db: claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        row=db.get(Run,manual['id']);row.status='failed';row.error_code='synthetic_retry';db.commit()
    complete_unit(factory,owner)
    supervisor=factory.dfa_supervisor
    supervisor.controls=sessionmaker(bind=create_engine(factory.kw['bind'].url,pool_size=1,max_overflow=0,pool_timeout=.1,
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
                         'tests/test_activity_dfa.py','tests/test_dfa_origins.py'})
    source_bindings={name:sha256((root/name).read_bytes()).hexdigest() for name in sorted(source_paths)}
    admission_denials=[]
    ingress=[]
    overall_started=time.monotonic()
    overall_deadline=overall_started+600
    maximum_attempts=300
    outcomes=[]
    error=[]
    transitions=[]
    committed_exits={}
    priority_evidence=PriorityEvidence(supervisor,monkeypatch)
    real_record=supervisor.lane.record
    def record(value):
        real_record(value)
        transitions.append(json.loads(json.dumps(value)))
    monkeypatch.setattr(supervisor.lane,'record',record)
    real_record_exit=supervisor.record_exit
    def record_exit():
        real_record_exit()
        value=supervisor.lane.actor()
        committed_exits[value['actor_token']]=time.monotonic()
    monkeypatch.setattr(supervisor,'record_exit',record_exit)
    def run():
        try:supervisor.run()
        except Exception as exc:error.append(str(exc))
    worker=threading.Thread(target=run,daemon=True);worker.start()
    try:
        for trial in range(100):
            deadline=min(time.monotonic()+15,overall_deadline)
            while True:
                with factory() as db:
                    control=db.get(Control,1)
                    actor=control.actor
                    automatic=db.query(Run).filter_by(origin='automatic').first()
                    if actor and actor.get('state')=='occupied' and automatic and actor['binding']['input']==automatic.input_digest:
                        break
                if time.monotonic()>deadline: raise AssertionError({'trial':trial,'stage':'automatic_start','errors':error})
                time.sleep(.01)
            # Actual durable manual retry transaction, bracketed conservatively.
            with factory() as db:
                row=db.get(Run,manual['id'])
                if row.status=='complete': row.status='failed';db.commit()
                generation=row.generation
            # A healthy trial starts only with freshly completed real control
            # readiness. No fixture heartbeat or permission timestamp is forged.
            health_deadline=min(time.monotonic()+15,overall_deadline)
            while True:
                with factory() as db:
                    health=db.get(Control,1)
                    fresh=health.ready_until and health.ready_until > datetime.utcnow()+timedelta(seconds=.4)
                    readiness_sequence=health.readiness_sequence
                if fresh:break
                if time.monotonic()>health_deadline:raise AssertionError({'trial':trial,'stage':'fresh_control_readiness','errors':error,'control':supervisor.control_observation})
                time.sleep(.01)
            # Expiry during SQLite admission is a real pre-admission refusal,
            # not an accepted-request preemption failure. Retain every attempt;
            # bound retries and require a newer completed renewal before retry.
            for attempt in range(3):
                assert len(ingress)<maximum_attempts and time.monotonic()<overall_deadline
                admitted,entry=admission_attempt(factory,owner,manual['id'],generation,ingress,
                    {'trial':trial,'attempt':attempt,'readiness_sequence':readiness_sequence,
                     'ready_until_observed':health.ready_until.isoformat(),
                     'cohort_elapsed_seconds':time.monotonic()-overall_started})
                if admitted:
                    before,after=entry['before_monotonic'],entry['after_monotonic']
                    actor=entry['readiness']['actor']
                    assert actor and actor['state']=='occupied'
                    assert actor['binding']['input']==automatic.input_digest
                    break
                admission_denials.append(entry)
                with progress.with_suffix('.ingress.jsonl').open('a') as stream:
                    stream.write(json.dumps(entry)+'\n')
                assert attempt<2,entry
                entry['backoff_requested_seconds']=5
                assert time.monotonic()+5 <= overall_deadline
                backoff_started=time.monotonic()
                supervisor.stop.wait(5)
                entry['backoff_elapsed_seconds']=time.monotonic()-backoff_started
                deadline=min(time.monotonic()+15,overall_deadline)
                while True:
                    with factory() as db:
                        health=db.get(Control,1)
                        renewed=health.readiness_sequence>readiness_sequence
                        fresh=health.ready_until and health.ready_until>datetime.utcnow()+timedelta(seconds=.4)
                        next_sequence=health.readiness_sequence
                    if renewed and fresh:
                        readiness_sequence=next_sequence
                        entry['next_readiness_sequence']=next_sequence
                        break
                    if time.monotonic()>deadline:raise AssertionError({'trial':trial,'stage':'renewal_after_refused_admission','errors':error})
                    time.sleep(.01)
            with progress.with_suffix('.ingress.jsonl').open('a') as stream:
                stream.write(json.dumps(entry)+'\n')
            until=before+5
            while True:
                with factory() as db:
                    acknowledged=db.get(Control,1).actor
                if acknowledged and acknowledged.get('state')=='idle' and acknowledged.get('actor_token')==actor['actor_token']:
                    observed=time.monotonic();break
                # A new actor may start only after the old exit receipt was committed.
                if actor['actor_token'] in committed_exits:
                    observed=max(time.monotonic(),committed_exits[actor['actor_token']]);break
                if time.monotonic()>until: raise AssertionError({'trial':trial,'stage':'retirement','errors':error})
                time.sleep(.005)
            exits=[value for value in transitions if value.get('state')=='idle'
                   and value.get('actor_token')==actor['actor_token']]
            assert exits
            causal_retirement=priority_evidence.accepted_preemption(admitted,actor,entry)
            outcomes.append({'retired_actor_token':actor['actor_token'],'committed_priority_retirement':causal_retirement,'readiness_sequence':readiness_sequence,'trial':trial,'admission_id':admitted['admission_id'],'commit_bracket_seconds':after-before,
                             'availability_upper_seconds':observed-before})
            deadline=min(time.monotonic()+15,overall_deadline)
            while True:
                with factory() as db:
                    if db.get(Run,manual['id']).status=='complete':break
                if time.monotonic()>deadline:raise AssertionError({'trial':trial,'stage':'manual_start_completion','errors':error})
                time.sleep(.01)
            starts=[value for value in transitions if value.get('state')=='occupied'
                    and value.get('binding',{}).get('generation')==admitted['generation']
                    and value.get('binding',{}).get('input')==row.input_digest]
            assert starts
            outcomes[-1]['manual_process_start_upper_seconds']=starts[-1]['process_start_observed_at']-before
            with progress.open('a') as stream:stream.write(json.dumps(outcomes[-1])+'\n')
        for previous,next_actor in zip(transitions,transitions[1:]):
            if next_actor['state']=='launching' and previous.get('actor_token') != next_actor.get('actor_token'):
                assert previous['state']=='idle'
                assert next_actor['launch_at']>=previous['exit_observed_at']
        assert time.monotonic()<=overall_deadline
        assert len(outcomes)==100
        assert max(row['availability_upper_seconds'] for row in outcomes)<=5
        (tmp_path/'capacity.json').write_text(json.dumps(outcomes,indent=2))
        destination=Path(__file__).resolve().parents[1]/'test-screenshots/ui-quality/pr871'
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'synthetic-capacity.json').write_text(json.dumps({'source_head':source_head,'source_bindings':source_bindings,'profile':'one SQLite writer + reserved control connection; 650 native RR; post-handshake ignored-TERM automatic fixture; real manual child computation',
            'cohort':'100 accepted durable admissions; pre-admission refusals separately retained, not 100/100 ingress success',
            'measurement_scope':'cohort excluding fixture setup; full pytest duration reported separately',
            'attempts':len(ingress),'maximum_attempts':maximum_attempts,'maximum_seconds':600,
            'overall_elapsed_seconds':time.monotonic()-overall_started,
            'pre_admission_denial_rate':len(admission_denials)/len(ingress),
            'ingress_attempts':ingress,'pre_admission_denials':admission_denials,
            'trials':outcomes,'unproved':['raw-loading preemption','maximum-input/native-compute preemption','output-transfer preemption','Azure/API/sync contention','60-minute mixed-load soak','cross-host placement/handover']},indent=2))
    finally:
        try:
            progress.with_suffix('.ingress-final.json').write_text(json.dumps({
                'source_head':source_head,'source_bindings':source_bindings,'attempts':ingress,
                'retirements_observed':len(outcomes),'priority_observations':priority_evidence.priorities,
                'retirement_observations':priority_evidence.retirements,
                'completed_trials':sum('manual_process_start_upper_seconds' in trial for trial in outcomes),
                'elapsed_seconds':time.monotonic()-overall_started,
                'denial_rate':len(admission_denials)/len(ingress) if ingress else None},indent=2))
        finally:
            supervisor.stop.set();worker.join(timeout=10)
            assert not worker.is_alive(),error



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
        with pytest.raises(AssertionError):admission_attempt(factory,owner,run['id'],generation,ledger,{})
        assert ledger[0]['no_durable_acceptance'] is False
        assert ledger[0]['outcome']=='exception'
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
                ready=control.readiness_sequence>0 and control.ready_until and control.ready_until>datetime.utcnow()+timedelta(seconds=.5)
            if ready and actor and actor.get('state')=='occupied':break
            assert time.monotonic()<deadline,errors
            time.sleep(.01)
        if pause_phase!='before_commit':
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
