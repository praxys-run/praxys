"""Bounded primitive test capture; formatting is deliberately a cold operation.

The session timings describe delegated Session methods, not isolated DBAPI
calls. Capture contributes overhead; no observation establishes nonperturbation.
"""
from collections import namedtuple
from contextlib import contextmanager
import threading
import time

Job = namedtuple('Job', 'id generation epoch input origin phase')
Actor = namedtuple('Actor', 'token binding identity incarnation state launch start term exit')
Decision = namedtuple('Decision', 'at reason phase job actor')
State = namedtuple('State', 'status generation recoveries execution_epoch input_digest origin error_code lease result_present missing')
SelectedValue = namedtuple('SelectedValue', 'status phase encoded failure')
Value = namedtuple('Value', 'kind reason digest valid_windows missing')
Pending = namedtuple('Pending', 'at job actor status cancelled value missing errors')
Finish = namedtuple('Finish', 'at job status reason value pending actor before current mode')
Published = namedtuple('Published', 'number job claim_at claim_state claim_current claim_mode occupied trigger exit_ack finish ack_at after')


def primitive(value):
    return value if type(value) in (type(None),str,int,float,bool) else ('unsupported_primitive',type(value).__name__)


def capture_job(value):
    if value is None:return None
    return Job(*(primitive(value.get(k)) for k in Job._fields))


def capture_actor(value, keys):
    if value is None:return None
    b=value.get('binding') or {};i=value.get('identity') or {};inc=value.get('incarnation') or {}
    return Actor(primitive(value.get('actor_token')),tuple(primitive(b.get(k)) for k in ('generation','epoch','input')),
        tuple(primitive(i.get(k)) for k in ('pid','pgid','start','state')),
        (len(inc),tuple(primitive(inc.get(k)) for k in keys)),primitive(value.get('state')),primitive(value.get('launch_at')),
        primitive(value.get('process_start_observed_at')),primitive(value.get('term_at')),primitive(value.get('exit_observed_at')))


def capture_decision(value, keys):
    if value is None:return None
    return Decision(value['at'],value['reason'],value['phase'],capture_job(value['job']),capture_actor(value['actor'],keys))


def decision_values(value, keys):
    """Cold reconstruction uses only the event's frozen primitive values."""
    if value is None:return None
    actor=value.actor
    return {'at':value.at,'reason':value.reason,'phase':value.phase,
        'job':{k:v for k,v in zip(Job._fields,value.job) if v is not None} if value.job else None,
        'actor':({'actor_token':actor.token,'binding':dict(zip(('generation','epoch','input'),actor.binding)),
            'identity':dict(zip(('pid','pgid','start','state'),actor.identity)),
            'incarnation':dict(zip(keys,actor.incarnation[1])),'state':actor.state,
            'launch_at':actor.launch,'process_start_observed_at':actor.start,'term_at':actor.term,'exit_observed_at':actor.exit} if actor else None)}


class PrimitiveSignal:
    """One producer publishes immutable data before a nonblocking scalar flag."""
    def __init__(self):self.ready=False
    def set(self):self.ready=True
    def clear(self):self.ready=False
    def is_set(self):return self.ready
    def wait(self, seconds):
        end=time.monotonic()+seconds
        while not self.ready and time.monotonic()<end:time.sleep(.001)
        return self.ready


class FirstOccupiedCycle:
    """One prospective post-release cycle, including first denial/exception.

    Capture uses the shared observer's immutable primitives. No renewal is
    parked and no later successful cycle can replace the first outcome.
    """
    def __init__(self,observer):
        self.observer=observer;self.target=None;self.cycle=None;self.raw=None
        self.event=PrimitiveSignal()
    def arm(self,job,actor,released_at):
        assert self.target is None,'duplicate_occupied_cycle_arm'
        self.target=(job,actor,released_at)
    def started(self,cycle):
        if self.target is not None and self.cycle is None and cycle['start']>=self.target[2]:
            self.cycle=cycle
    def completed(self,cycle):
        if cycle is self.cycle and self.raw is None:
            outcome=cycle.get('outcome')
            errors=tuple(row for row in cycle['critical'] if row[0].endswith('error'))
            self.raw=(cycle['start'],cycle['end'],cycle['job'],cycle['actor'],outcome,errors)
            self.event.set()
    @property
    def observation(self):
        return decision_values(self.raw[4][3][2],self.observer.keys) if self.raw and self.raw[4] else None


class RawFinishObservation:
    def __init__(self, job, number, render):
        self.job,self.number,self.render=job,number,render
        self.done=PrimitiveSignal();self.record=None;self.error=None
    def publish(self, value):
        assert not self.done.is_set(),'duplicate_finish_observation'
        assert isinstance(value,Published) and value.job==self.job and value.number==self.number,'wrong_finish_observation_binding'
        self.record=value
        self.done.set()
    def fail(self, error):self.error=error;self.done.set()
    def require(self):
        assert self.done.is_set(),'finish_observation_not_complete'
        assert self.error is None,'finish_observation_failed'
        assert self.record is not None,'finish_observation_record_missing'
        return self.render(self.record)


class ActiveRenewalEvidence:
    def __init__(self, supervisor, factory, monkeypatch):
        from sqlalchemy.orm import sessionmaker
        from api import activity_dfa as service, dfa_rights
        self.sup,self.factory=supervisor,factory
        self.keys=tuple(sorted(supervisor.identity))  # Prospectively, outside renewal.
        self.local=threading.local();supervisor._test_renewal_capture=self.local
        self.raw_cycles=[];self.retained=[];self.raw_attempts=[];self.finish_observations=[]
        self.raw_resources=[];self.raw_stops=[];self.raw_errors=[];self.raw_returns=[]
        self.errors=[];self.cleanup_errors=[];self.threads=[]
        self.dropped=0;self.resource_dropped=0;self.actor=None
        self.error_dropped=0;self.stop_dropped=0
        self.cold_values={}
        self.raw_operations=[];self.operation_dropped=0;self.unbound_selections=[]
        self.on_occupied_ack_raw=self.on_work_controls_exit=None
        self.first_occupied_cycle=FirstOccupiedCycle(self)
        self.on_occupied_ack=self.on_active_bound=self.on_sql_commit=self.on_finish_observed=None
        observer=self
        original_class=type(supervisor)

        class Observed(original_class):
            def __setattr__(self,name,value):
                entered=time.monotonic()
                super().__setattr__(name,value)
                returned=time.monotonic()
                if not getattr(observer.local,'renew',False):return
                c=getattr(observer.local,'cycle',None)
                if c is None:return
                if name=='permission_decision':
                    observer.event(c,'assignment',name,capture_decision(value,observer.keys),entered,returned)
                elif name in ('allowed','permission_until'):
                    observer.event(c,'assignment',name,value,entered,returned)
                elif name=='control_observation':
                    state=value['state'];duration=value['duration_seconds']
                    observer.event(c,'observation',state,duration,entered,returned)
                    c['outcome']=(state,duration,returned,
                        (self.allowed,self.permission_until,capture_decision(self.permission_decision,observer.keys)))
                    if c['end'] is not None:observer.first_occupied_cycle.completed(c)
                    if not self.allowed and c['job'] is not None:
                        previous=observer.raw_cycles[-2] if len(observer.raw_cycles)>1 else None
                        for item in (previous,c):
                            if item is not None and not any(x is item for x in observer.retained):observer.retained.append(item)
                        observer.retained=observer.retained[-4:]
                observer.event(c,'capture_overhead','assignment',entered,time.monotonic())
        monkeypatch.setattr(supervisor,'__class__',Observed)

        class Controls(supervisor.controls.class_):
            def __enter__(session):
                entered=time.monotonic()
                if getattr(observer.local,'renew',False):
                    c={'start':entered,'phase':supervisor.renewal_phase,'job':capture_job(supervisor.active),
                       'actor':observer.actor,'before':(supervisor.allowed,supervisor.permission_until,
                            capture_decision(supervisor.permission_decision,observer.keys)),
                       'events':[],'critical':[],'dropped':0,'end':None}
                    if len(observer.raw_cycles)==12:observer.raw_cycles.pop(1);observer.dropped+=1
                    observer.raw_cycles.append(c);observer.local.cycle=c
                    observer.first_occupied_cycle.started(c)
                else:c=None
                session._capture_cycle=c
                called=time.monotonic()
                try:result=super().__enter__()
                except BaseException as exc:
                    returned=time.monotonic();observer.event(c,'session_enter_error',observer.raw_error(exc),entered,called,returned,time.monotonic());raise
                returned=time.monotonic();observer.event(c,'session_enter',entered,called,returned,time.monotonic())
                return result
            def execute(session,statement,*args,**kwargs):
                entered=time.monotonic();c=getattr(session,'_capture_cycle',None)
                update=bool(getattr(statement,'is_update',False) and getattr(getattr(statement,'table',None),'name',None)=='activity_dfa_control')
                category='control_update' if update else 'select' if getattr(statement,'is_select',False) else 'other'
                observer.operation('controls','execute',category,'entry',entered,session=session)
                if update:observer.event(c,'sql_update_invoked',entered)
                called=time.monotonic()
                try:result=super().execute(statement,*args,**kwargs)
                except BaseException as exc:
                    returned=time.monotonic();observer.operation('controls','execute',category,'error',returned,observer.raw_error(exc),session)
                    observer.event(c,'sql_update_error' if update else 'sql_error',observer.raw_error(exc),entered,called,returned,time.monotonic());raise
                returned=time.monotonic()
                observer.operation('controls','execute',category,'return',returned,session=session)
                if update:observer.event(c,'sql_update_return',result.rowcount,entered,called,returned,time.monotonic())
                setting={"SET LOCAL statement_timeout='200ms'":'statement_timeout_ms',"SET LOCAL lock_timeout='200ms'":'lock_timeout_ms'}.get(getattr(statement,'text',None))
                if setting:observer.event(c,'timeout_setting_return',setting,200,returned)
                return result
            def commit(session):
                entered=time.monotonic();c=getattr(session,'_capture_cycle',None)
                observer.operation('controls','commit',None,'entry',entered,session=session)
                observer.event(c,'commit_invoked',entered)
                called=time.monotonic()
                try:result=super().commit()
                except BaseException as exc:
                    returned=time.monotonic();observer.operation('controls','commit',None,'error',returned,observer.raw_error(exc),session);observer.event(c,'commit_error',observer.raw_error(exc),entered,called,returned,time.monotonic());raise
                returned=time.monotonic()  # BEFORE capture or any fixture callback.
                observer.operation('controls','commit',None,'return',returned,session=session)
                observer.event(c,'sql_commit_return',returned,entered,called)
                if getattr(observer.local,'work',False) and observer.local.actor is not None:
                    a=observer.local.attempt;a['occupied']=(returned,observer.local.actor)
                    observer.operation('controls','occupied_capture',None,'published',time.monotonic(),session=session)
                    if observer.on_occupied_ack_raw:observer.on_occupied_ack_raw(a['job'],observer.local.actor,returned)
                    if observer.on_occupied_ack:
                        # Work thread, outside timed renewal/supervisor lock.
                        try:observer.on_occupied_ack(observer.job_dict(a['job']),observer.actor_dict(observer.local.actor))
                        except BaseException as exc:
                            observer.operation('controls','occupied_callback',None,'error',time.monotonic(),observer.raw_error(exc),session);raise
                        observer.operation('controls','occupied_callback',None,'published',time.monotonic(),session=session)
                if observer.on_sql_commit:
                    if c is not None:observer.on_sql_commit('renew',{'started':c['start']})
                    elif getattr(observer.local,'exit',False):observer.on_sql_commit('exit',{'actor':observer.actor_dict(observer.actor)})
                ack=time.monotonic();observer.event(c,'commit_return_ack',ack,entered,called,returned,time.monotonic())
                return result
            def __exit__(session,*args):
                entered=time.monotonic();c=getattr(session,'_capture_cycle',None);observer.operation('controls','session_exit',None,'entry',entered,session=session);called=time.monotonic()
                try:result=super().__exit__(*args)
                except BaseException as exc:
                    returned=time.monotonic()
                    if c is not None:c['end']=returned
                    observer.event(c,'session_exit_error',observer.raw_error(exc),entered,called,returned,time.monotonic());raise
                returned=time.monotonic();observer.event(c,'session_exit_return',entered,called,returned,time.monotonic())
                observer.operation('controls','session_exit',None,'return',returned,session=session)
                if c is not None:
                    c['end']=returned
                    if c.get('outcome') is not None:observer.first_occupied_cycle.completed(c)
                if getattr(observer.local,'work',False) and observer.local.actor is not None and observer.on_work_controls_exit:
                    try:observer.on_work_controls_exit(observer.local.attempt['job'],observer.local.actor,returned)
                    except BaseException as exc:
                        observer.operation('controls','released_callback',None,'error',time.monotonic(),observer.raw_error(exc),session);raise
                    observer.operation('controls','released_callback',None,'published',time.monotonic(),session=session)
                return result
        monkeypatch.setattr(supervisor,'controls',sessionmaker(class_=Controls,**supervisor.controls.kw))

        class Owners(supervisor.factory.class_):
            def execute(session,statement,*args,**kwargs):
                entered=time.monotonic();category='update' if getattr(statement,'is_update',False) else 'select' if getattr(statement,'is_select',False) else 'other'
                observer.operation('owner','execute',category,'entry',entered,session=session)
                try:result=super().execute(statement,*args,**kwargs)
                except BaseException as exc:
                    returned=time.monotonic();observer.operation('owner','execute',category,'error',returned,observer.raw_error(exc),session);raise
                returned=time.monotonic();observer.operation('owner','execute',category,'return',returned,session=session);return result
            def __exit__(session,*args):
                entered=time.monotonic();observer.operation('owner','session_exit',None,'entry',entered,session=session)
                try:result=super().__exit__(*args)
                except BaseException as exc:
                    returned=time.monotonic();observer.operation('owner','session_exit',None,'error',returned,observer.raw_error(exc),session);raise
                returned=time.monotonic();observer.operation('owner','session_exit',None,'return',returned,session=session);return result
            def commit(session):
                # Existing owner transaction only: cached primitive values are
                # frozen BEFORE expiry-on-commit; no supplementary SQL session.
                model=getattr(observer.local,'model',None)
                state=observer.capture_state(model) if model is not None else None
                binding=observer.model_binding(model) if model is not None else None
                entered=time.monotonic()
                observer.operation('owner','commit',None,'entry',entered,session=session)
                try:result=super().commit()
                except BaseException as exc:
                    returned=time.monotonic();observer.operation('owner','commit',None,'error',returned,observer.raw_error(exc),session);raise
                returned=time.monotonic();observer.operation('owner','commit',None,'return',returned,session=session)
                op=getattr(observer.local,'operation',None)
                if op in ('acquire','finish'):
                    observer.local.owner_ack=(state,entered,returned)
                    observer.local.owner_binding=binding
                return result
        monkeypatch.setattr(supervisor,'factory',sessionmaker(class_=Owners,**supervisor.factory.kw))
        actual_bound=supervisor._bound
        def bound(db):
            entered=time.monotonic();result=actual_bound(db);returned=time.monotonic()
            c=getattr(observer.local,'cycle',None) if getattr(observer.local,'renew',False) else None
            if c is not None:
                sql_actor=capture_actor(result.actor,observer.keys) if result is not None else None
                inc=(len(result.incarnation),tuple(result.incarnation.get(k) for k in observer.keys)) if result is not None else None
                observer.event(c,'bound_return',result is not None,result.epoch if result is not None else None,
                    inc,result.readiness_sequence if result is not None else None,sql_actor,entered,returned,time.monotonic())
                if observer.on_active_bound:observer.on_active_bound({'started':c['start'],'phase':c['phase'],
                    'job':c['job'],'actor':observer.actor,'sql_actor':sql_actor,
                    'epoch':result.epoch if result is not None else None,'incarnation':inc})
            return result
        monkeypatch.setattr(supervisor,'_bound',bound)

        def validation(actual,name):
            def call(db,value):
                entered=time.monotonic()
                if name!='mode' and not getattr(observer.local,'renew',False):
                    observer.local.model=value
                    if getattr(observer.local,'operation',None)=='finish' and observer.local.before_state is None:
                        observer.local.before_state=observer.capture_state(value)
                        observer.local.before_binding=observer.model_binding(value)
                try:result=actual(db,value)
                except BaseException as exc:
                    returned=time.monotonic();observer.event(getattr(observer.local,'cycle',None),'validation_error',name,observer.raw_error(exc),entered,returned);raise
                returned=time.monotonic()
                if getattr(observer.local,'renew',False):
                    if name!='mode':
                        d=value.__dict__
                        observer.local.cycle['validated_job']=Job(d.get('id'),d.get('generation'),d.get('execution_epoch'),
                            d.get('input_digest'),d.get('origin'),d.get('phase'))
                    observer.event(observer.local.cycle,name+'_return',result,entered,returned,time.monotonic())
                elif getattr(observer.local,'operation',None) in ('acquire','finish'):
                    if name=='mode':observer.local.mode=result
                    else:observer.local.current=result is True
                return result
            return call
        monkeypatch.setattr(service,'_current',validation(service._current,'source'))
        monkeypatch.setattr(dfa_rights,'execution_current',validation(dfa_rights.execution_current,'rights'))
        monkeypatch.setattr(dfa_rights,'account_mode',validation(dfa_rights.account_mode,'mode'))
        actual_owner=service.owner_write
        @contextmanager
        def owner(db,who):
            with actual_owner(db,who) as result:
                observer.resource('owner_write','start')
                try:yield result
                finally:observer.resource('owner_write','end')
        monkeypatch.setattr(service,'owner_write',owner)

        actual_acquire=supervisor.acquire_job
        def acquire():
            observer.local.operation='acquire';observer.local.model=None;observer.local.owner_ack=None
            observer.local.current=False;observer.local.mode=None
            observer.local.before_state=None;observer.local.before_binding=None;observer.local.owner_binding=None
            try:job=actual_acquire()
            finally:observer.local.operation=None
            if job:
                assert len(observer.raw_attempts)<4,'attempt_capture_bound'
                a={'number':len(observer.raw_attempts)+1,'job':capture_job(job),'claim_at':time.monotonic(),
                   'claim_state':observer.local.owner_ack[0] if observer.local.owner_ack else None,
                   'claim_current':observer.local.current,'claim_mode':observer.local.mode,
                   'occupied':None,'trigger':None,'cleanup_retirements':[],'cleanup_retirements_dropped':0,'exit_ack':None,'finish':None,'after':None,'ack_at':None}
                observer.raw_attempts.append(a)
                observation=RawFinishObservation(a['job'],a['number'],observer.render_attempt)
                observer.finish_observations.append(observation)
                try:
                    assert observer.local.owner_binding==a['job'],'claim_model_binding_missing_or_changed'
                    assert a['claim_state'] is not None and a['claim_state'].lease,'claim_lease_missing'
                except BaseException as exc:observation.fail(observer.raw_error(exc));observer.keep_error(exc)
            return job
        monkeypatch.setattr(supervisor,'acquire_job',acquire)
        actual_work=supervisor.work
        def work(job,outputs,cancellation=None):
            observer.local.work=True;observer.local.actor=None
            matches=[a for a in observer.raw_attempts if a['job']==capture_job(job)]
            assert matches,'work_claim_missing'
            observer.local.attempt=matches[-1]
            try:return actual_work(job,outputs,cancellation)
            finally:observer.local.work=False
        monkeypatch.setattr(supervisor,'work',work)
        actual_record=supervisor.lane.record
        def record(value):
            result=actual_record(value);returned=time.monotonic()
            actor=capture_actor(value,observer.keys);observer.actor=actor
            if getattr(observer.local,'work',False):observer.local.actor=actor
            return result
        monkeypatch.setattr(supervisor.lane,'record',record)
        actual_retire=supervisor.lane.retire
        def retire(*args,**kwargs):
            # Cold reactor boundary only. No stack inspection exists in renewal
            # or locked assignments; only these named reactor locals are read.
            from api.dfa_supervisor import Supervisor,SAFE_FAILURES
            import sys
            f=sys._getframe(1)
            for _ in range(12):
                if f.f_code is Supervisor.run.__code__:break
                f=f.f_back
                if f is None:break
            if f is not None and f.f_locals.get('job') and observer.raw_attempts:
                try:
                    v=f.f_locals
                    observer.capture_retirement(v['job'],v['expired'],v['timed_out'],v['ready'],v['status'],
                        v.get('value'),v['decision'],v['actor_before'],v.get('chosen_value_json'))
                except BaseException as exc:
                    # Observation failure is retained; original retirement still
                    # receives exactly its original arguments and exception path.
                    observer.keep_error(exc)
            return actual_retire(*args,**kwargs)
        monkeypatch.setattr(supervisor.lane,'retire',retire)
        actual_exit=supervisor.record_exit
        def exited():
            observer.local.exit=True
            try:result=actual_exit()
            finally:observer.local.exit=False
            if observer.raw_attempts:observer.raw_attempts[-1]['exit_ack']=(result['at'],result['kind'],observer.actor)
            return result
        monkeypatch.setattr(supervisor,'record_exit',exited)
        actual_finish=supervisor.finish
        def finish(job,status,value):
            from api.dfa_supervisor import SAFE_FAILURES
            entered=time.monotonic()
            rawjob=capture_job(job)
            a=observer.raw_attempts[-1] if observer.raw_attempts and observer.raw_attempts[-1]['job']==rawjob else None
            observer.local.operation='finish';observer.local.model=None;observer.local.owner_ack=None
            observer.local.current=False;observer.local.mode=None
            observer.local.before_state=None;observer.local.before_binding=None;observer.local.owner_binding=None
            reason=value if isinstance(value,str) and value in SAFE_FAILURES|{'mode_changed','mode_unavailable'} else None
            # COLD entry, before original finish mutates any output or pending.
            pending=observer.capture_pending(supervisor.pending)
            argument_value=observer.capture_value(status,value,rawjob.phase)
            argument_actor=observer.actor
            try:result=actual_finish(job,status,value)
            except BaseException as exc:
                returned=time.monotonic()
                if a:
                    a['finish']=Finish(entered,rawjob,status,reason,argument_value,pending,argument_actor,observer.local.before_state,observer.local.current,observer.local.mode)
                    if observer.local.owner_ack:a['after'],_,a['ack_at']=observer.local.owner_ack
                    observer.finish_observations[a['number']-1].fail(observer.raw_error(exc))
                raise
            finally:observer.local.operation=None
            returned=time.monotonic()
            if a:
                try:
                    before=observer.local.before_state
                    a['finish']=Finish(entered,rawjob,status,reason,argument_value,pending,argument_actor,before,observer.local.current,observer.local.mode)
                    if observer.local.owner_ack:a['after'],_,a['ack_at']=observer.local.owner_ack
                    assert observer.local.before_binding==rawjob,'finish_model_binding_missing_or_changed'
                    assert before is not None and before.lease,'finish_before_lease_missing'
                    assert observer.local.owner_ack is not None,'owner_finish_ack_missing'
                    assert observer.local.owner_binding==rawjob,'finish_commit_binding_changed'
                    assert not observer.finish_observations[a['number']-1].done.is_set(),'prior_observation_failed'
                    published=Published(*(a[k] for k in Published._fields))
                    assert not pending.missing,'pending_snapshot_incomplete'
                    if a['trigger'] is not None:
                        from tests.dfa_attempt_evidence import assert_pending_binding
                        assert_pending_binding(observer.render_attempt(published))
                    observation=observer.finish_observations[a['number']-1];observation.publish(published)
                    if observer.on_finish_observed:observer.on_finish_observed(published)
                except BaseException as exc:
                    observer.finish_observations[a['number']-1].fail(observer.raw_error(exc));observer.keep_error(exc)
            return result
        monkeypatch.setattr(supervisor,'finish',finish)
        actual_renew=supervisor.renew
        def renew():
            observer.threads.append(threading.current_thread());observer.local.renew=True;observer.local.cycle=None
            try:return actual_renew()
            except BaseException as exc:observer.keep_error(exc);raise
            finally:
                returned=time.monotonic();c=observer.local.cycle
                if c is not None and c['end'] is not None:observer.first_occupied_cycle.completed(c)
                observer.raw_returns.append(returned);observer.local.renew=False
        monkeypatch.setattr(supervisor,'renew',renew)
        actual_stop=supervisor.stop.set
        def stop():
            # Cold shutdown only; caller code/line is sufficient, no locals.
            entered=time.monotonic()
            if getattr(observer.local,'renew',False):item=(entered,'unavailable','renewal_thread_stop',None)
            else:
                import sys
                f=sys._getframe(1);item=(entered,f.f_code.co_filename,f.f_code.co_name,f.f_lineno)
            if len(observer.raw_stops)<8:observer.raw_stops.append(item)
            else:observer.stop_dropped+=1
            return actual_stop()
        monkeypatch.setattr(supervisor.stop,'set',stop)

    def capture_retirement(self,job,expired,timed_out,ready,status,value,decision,actor,encoded=None):
        """Cold reactor boundary: primitive exact-attempt snapshot only."""
        from api.dfa_supervisor import SAFE_FAILURES
        j=capture_job(job)
        physical=capture_actor(actor,self.keys)
        reason=value if isinstance(value,str) and value in SAFE_FAILURES|{'mode_changed','mode_unavailable'} else None
        snapshot=(time.monotonic(),expired,timed_out,ready,status,reason,capture_decision(decision,self.keys),physical,
            SelectedValue(status,j.phase if j else None,encoded if status=='output' and isinstance(encoded,str) else None,reason),j)
        matches=[a for a in self.raw_attempts if a['job']==j]
        if not matches:
            if len(self.unbound_selections)<4:self.unbound_selections.append((*snapshot,False))
            raise AssertionError('retirement_claim_binding_missing')
        a=matches[-1]
        snapshot=(*snapshot,a['occupied'] is not None)
        if a['trigger'] is None:a['trigger']=snapshot
        elif len(a['cleanup_retirements'])<4:a['cleanup_retirements'].append(snapshot)
        else:a['cleanup_retirements_dropped']+=1
        # A missing ACK is exported as partial provenance, never a reason to
        # erase the FIRST reactor choice or reconstruct it after cleanup.
        if a['occupied'] is not None and physical is not None:
            assert physical.token==a['occupied'][1].token and physical.binding==a['occupied'][1].binding,'retirement_actor_binding_changed'

    @staticmethod
    def capture_value(status,value,phase):
        # Cold only. Bound the canonical private envelope, export its digest and
        # allowlisted failure/actual numerical summary, never numerical payload.
        import json,hashlib
        from api.dfa_supervisor import SAFE_FAILURES
        from api.activity_dfa import MAX_RESULT_BYTES
        if status in ('failed','failed_before_spawn'):
            if isinstance(value,str) and value in SAFE_FAILURES|{'mode_changed','mode_unavailable'}:
                digest=hashlib.sha256(json.dumps(value).encode()).hexdigest()
                return Value('failure',value,digest,None,())
            return Value('invalid_failure',None,None,None,('value.reason',))
        if status!='output':return Value('invalid_status',None,None,None,('value.status',))
        try:
            assert isinstance(value,dict) and isinstance(value.get('result'),dict)
            result=value['result'];windows=None
            if phase=='compute':
                windows=result['summary']['valid_windows']
                assert type(windows) is int and windows>=0
            elif phase!='prepare':raise ValueError('unsupported_phase')
            encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            assert len(encoded)<=MAX_RESULT_BYTES
            return Value('output',None,hashlib.sha256(encoded).hexdigest(),windows,())
        except (KeyError,TypeError,ValueError,AssertionError,RecursionError):
            return Value('invalid_output',None,None,None,('value.envelope',))

    def capture_pending(self,p):
        import json,re
        from api import dfa_ipc
        at=time.monotonic();missing=[];errors=[]
        if p is None:return Pending(at,None,None,None,None,None,('pending',),())
        def decode(field):
            try:
                raw=getattr(p,field)
                assert isinstance(raw,str) and len(raw.encode())<=65536
                return dfa_ipc.loads(raw.encode())
            except BaseException as exc:
                missing.append(field);errors.append(self.raw_error(exc));return None
        job_value=decode('job_json');actor_value=decode('actor_json')
        value=None
        try:
            raw=p.value_json
            from api.activity_dfa import MAX_RESULT_BYTES
            assert isinstance(raw,str) and len(raw.encode())<=MAX_RESULT_BYTES
            value=dfa_ipc.loads(raw.encode())
        except BaseException as exc:missing.append('value_json');errors.append(self.raw_error(exc))
        job=None;actor=None
        if isinstance(job_value,dict):
            required=('id','generation','epoch','input','origin','phase')
            for key in required:
                v=job_value.get(key)
                good=type(v) is int and v>0 if key=='generation' else isinstance(v,str) and 0<len(v)<=256
                if key=='input':good=isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) is not None
                if key=='epoch':good=isinstance(v,str) and v.isdigit()
                if key=='origin':good=v in ('manual','automatic')
                if key=='phase':good=v in ('compute','prepare')
                if not good:missing.append('job.'+key);job_value[key]=None
            job=capture_job(job_value)
        else:missing.append('job')
        if isinstance(actor_value,dict):
            for field in ('actor_token','binding','identity','incarnation','state','exit_observed_at'):
                if actor_value.get(field) is None:missing.append('actor.'+field)
            try:
                assert isinstance(actor_value.get('binding'),dict)
                dfa_ipc.binding(actor_value['binding'])
                identity=actor_value.get('identity')
                assert isinstance(identity,dict) and all(type(identity.get(k)) is int and identity[k]>0 for k in ('pid','pgid'))
                assert isinstance(identity.get('start'),str) and identity['start'].isdigit() and len(identity['start'])<=128
                assert identity.get('state') is None or isinstance(identity['state'],str) and len(identity['state'])==1
                assert isinstance(actor_value.get('actor_token'),str) and 0<len(actor_value['actor_token'])<=256
                assert actor_value.get('state') in ('idle','occupied','retiring','recovery_required')
                assert type(actor_value.get('exit_observed_at')) in (int,float)
                assert isinstance(actor_value.get('incarnation'),dict) and set(actor_value['incarnation'])==set(self.keys)
                actor=capture_actor(actor_value,self.keys)
            except BaseException as exc:missing.append('actor.shape');errors.append(self.raw_error(exc))
        else:missing.append('actor')
        try:status=getattr(p,'status',None)
        except BaseException as exc:status=None;missing.append('status');errors.append(self.raw_error(exc))
        if status not in ('output','failed','failed_before_spawn'):missing.append('status');status=None
        try:cancelled=p.cancellation.is_set();assert type(cancelled) is bool
        except BaseException as exc:cancelled=None;missing.append('cancellation');errors.append(self.raw_error(exc))
        captured=self.capture_value(status,value,job.phase if job else None)
        missing.extend(captured.missing)
        return Pending(at,job,actor,status,cancelled,captured,tuple(missing),tuple(errors))

    @staticmethod
    def model_binding(run):
        d=run.__dict__
        return Job(*(primitive(d.get(k)) for k in ('id','generation','execution_epoch','input_digest','origin','phase')))

    @staticmethod
    def capture_state(run):
        d=run.__dict__;fields=State._fields[:7]
        missing=tuple(k for k in (*fields,'lease_token','result') if k not in d)
        return State(*(primitive(d.get(k)) for k in fields),primitive(d.get('lease_token')),d.get('result') is not None,missing)

    @staticmethod
    def raw_error(exc):
        orig=getattr(exc,'orig',exc)
        return (type(exc).__name__,getattr(orig,'sqlite_errorcode',None),getattr(orig,'sqlstate',None),exc.__traceback__,time.monotonic())

    @staticmethod
    def error(exc):
        from tests.dfa_boundary_evidence import FirstRenewalOutcome
        return FirstRenewalOutcome.error(exc)  # Cold public formatter only.

    @staticmethod
    def event(c,name,*values):
        if c is None:return
        row=(name,time.monotonic(),values)
        if len(c['events'])<32:c['events'].append(row)
        else:c['dropped']+=1
        if name.endswith('error') or name=='observation':
            if len(c['critical'])<8:c['critical'].append(row)

    def operation(self,scope,name,category,stage,at,error=None,session=None):
        a=getattr(self.local,'attempt',None) if getattr(self.local,'work',False) else None
        c=getattr(self.local,'cycle',None) if getattr(self.local,'renew',False) else None
        row=(scope,name,category,stage,at,id(session) if session is not None else None,
            c['job'] if c else a['job'] if a else None,a['number'] if a else None,error,threading.get_ident())
        if len(self.raw_operations)<96:self.raw_operations.append(row)
        elif stage=='error':self.raw_operations.pop(1);self.raw_operations.append(row);self.operation_dropped+=1
        else:self.operation_dropped+=1

    @property
    def operations(self):
        return [{'scope':s,'operation':n,'category':c,'stage':v,'at':t,'session':i,'job':self.safe_job(j),'attempt':a,
                 'error':self.render_error(e) if e else None,'thread':thread} for s,n,c,v,t,i,j,a,e,thread in tuple(self.raw_operations)]

    @property
    def renewals(self):
        return [{'completed_at':e['at'],'permission_granted_at':d['at'],'permission_until':c['after']['deadline']}
                for c in self.cycles if c['after'] and c['after']['allowed']
                for d in [c['after']['decision']] if d for e in c['events'] if e['event']=='commit_return_ack']

    @property
    def renewal_decisions(self):
        return [{'at':c['after']['decision']['at'],'allowed':c['after']['allowed'],'permission_until':c['after']['deadline'],
                 'sqlite_errorcode':next((e['error']['sqlite_errorcode'] for e in c['events'] if e['event'].endswith('error')),None)}
                for c in self.cycles if c['after'] and c['after']['decision']]

    @property
    def retirements(self):
        return [{'actor_token':a['trigger'][7].token,'started_monotonic':a['trigger'][0],
                 'exit_observed_at':a['finish'].actor.exit if a['finish'] and a['finish'].actor else None}
                for a in tuple(self.raw_attempts) if a['trigger'] and a['trigger'][7]]

    def resource(self,name,action):
        if len(self.raw_resources)<64:self.raw_resources.append((name,action,time.monotonic()))
        else:self.resource_dropped+=1

    def deliver(self,actual,*args,**kwargs):
        try:return actual(*args,**kwargs)
        except BaseException as exc:self.keep_error(exc);raise

    def keep_error(self,exc):
        if len(self.raw_errors)<4:self.raw_errors.append(self.raw_error(exc))
        else:self.error_dropped+=1

    def job_dict(self,j):
        return None if j is None else {k:v for k,v in zip(Job._fields,j) if v is not None}
    def actor_dict(self,a):
        if a is None:return None
        return {'actor_token':a.token,'binding':dict(zip(('generation','epoch','input'),a.binding)),
            'identity':dict(zip(('pid','pgid','start','state'),a.identity)),
            'incarnation':dict(zip(self.keys,a.incarnation[1])),'state':a.state,'launch_at':a.launch,
            'process_start_observed_at':a.start,'term_at':a.term,'exit_observed_at':a.exit}
    def safe_job(self,j):
        from tests.dfa_boundary_evidence import safe_binding
        return safe_binding(self.job_dict(j))
    def safe_actor(self,a):
        from tests.dfa_boundary_evidence import safe_binding
        return safe_binding(self.actor_dict(a))
    def safe_decision(self,d):
        return None if d is None else {'at':d.at,'reason':d.reason,'phase':d.phase,'job':self.safe_job(d.job),'actor':self.safe_actor(d.actor)}
    def state_dict(self,s):
        from hashlib import sha256
        if s is None:return {'status':'unavailable'}
        return {k:getattr(s,k) for k in State._fields[:7]}|{'lease_token_hash':sha256(s.lease.encode()).hexdigest() if s.lease else None,
            'result_present':s.result_present,'unavailable_fields':s.missing}
    @staticmethod
    def render_error(e):
        from pathlib import Path
        frames=[];tb=e[3]
        while tb is not None:
            frames.append({'file':Path(tb.tb_frame.f_code.co_filename).name,'function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno});tb=tb.tb_next
        return {'class':e[0],'sqlite_errorcode':e[1],'sqlstate':e[2],'stack':frames,'at':e[4]}
    def render_trigger(self,t):
        if t is None:return None
        return {'at':t[0],'expired':t[1],'timed_out':t[2],'output_ready':t[3],
            'selected_status':t[4],'selected_reason':t[5],'decision':self.safe_decision(t[6]),'actor':self.safe_actor(t[7]),
            'value':self.selected_value_dict(t[8]),'job':self.safe_job(t[9]),'occupied_ack_captured_at_selection':t[10]}
    def selected_value_dict(self,source):
        # Source is a frozen failure scalar or runtime's immutable chosen JSON
        # string made BEFORE its locks. Parse/hash only on this cold path.
        from api import dfa_ipc
        from api.activity_dfa import MAX_RESULT_BYTES
        key=id(source)
        if key not in self.cold_values:
            if source.status=='output':
                try:
                    assert isinstance(source.encoded,str) and len(source.encoded.encode())<=MAX_RESULT_BYTES
                    value=dfa_ipc.loads(source.encoded.encode())
                    captured=self.capture_value(source.status,value,source.phase)
                except BaseException:captured=Value('invalid_output',None,None,None,('selected.value_json',))
            else:captured=self.capture_value(source.status,source.failure,source.phase)
            assert len(self.cold_values)<20,'selected_value_cache_bound'
            self.cold_values[key]=captured
        return self.value_dict(self.cold_values[key])
    @staticmethod
    def value_dict(v):
        return None if v is None else {'kind':v.kind,'reason':v.reason,'sha256':v.digest,'valid_windows':v.valid_windows,'missing_fields':v.missing}
    def pending_dict(self,p):
        return {'at':p.at,'job':self.safe_job(p.job),'actor':self.safe_actor(p.actor),'status':p.status,
            'cancelled':p.cancelled,'value':self.value_dict(p.value),'missing_fields':p.missing,
            'observation_errors':[self.render_error(e) for e in p.errors]}
    def render_attempt(self,p):
        trigger=self.render_trigger(p.trigger)
        f=p.finish;exit_ack=p.exit_ack
        return {'attempt':p.number,'claim':{'at':p.claim_at,'job':self.safe_job(p.job),'state':self.state_dict(p.claim_state),'current':p.claim_current,'mode':p.claim_mode},
            'occupied_ack':{'at':p.occupied[0],'actor':self.safe_actor(p.occupied[1])} if p.occupied else None,
            'trigger':trigger,'exit_ack':{'at':exit_ack[0],'kind':exit_ack[1],'actor':self.safe_actor(exit_ack[2])} if exit_ack else None,
            'finish':{'at':f.at,'job':self.safe_job(f.job),'status':f.status,'reason':f.reason,'value':self.value_dict(f.value),
                'pending_snapshot':self.pending_dict(f.pending),'pending_status':f.pending.status,
                'pending_reason':f.pending.value.reason if f.pending.value else None,
                'pending_job':self.safe_job(f.pending.job),'pending_actor':self.safe_actor(f.pending.actor),'actor':self.safe_actor(f.actor),'cancelled':f.pending.cancelled,
                'before':self.state_dict(f.before),'trigger':trigger,'exit_ack_at':exit_ack[0] if exit_ack else None,'current':f.current,'mode':f.mode} if f else None,
            'finish_ack':{'at':p.ack_at,'after':self.state_dict(p.after)}}
    def export_attempts(self):
        out=[]
        for raw,observation in zip(tuple(self.raw_attempts),tuple(self.finish_observations)):
            p=Published(*(raw[k] for k in Published._fields))
            row=self.render_attempt(p)
            required=('claim_state','occupied','trigger','exit_ack','finish','ack_at','after')
            missing=[k for k in required if raw[k] is None]
            if raw['trigger'] is not None:
                if raw['trigger'][7] is None:missing.append('selection.actor')
                if not raw['trigger'][10] or raw['occupied'] is None or raw['occupied'][0]>raw['trigger'][0]:missing.append('selection.occupied_ack_before_selection')
            if raw['finish'] is not None:missing.extend('pending.'+k for k in raw['finish'].pending.missing)
            row['cleanup_retirements']=[{'event':'subsequent_cleanup_retirement_capture',**self.render_trigger(t)} for t in tuple(raw['cleanup_retirements'])]
            row['cleanup_retirements_dropped']=raw['cleanup_retirements_dropped']
            row['publication']='FAILED' if observation.error is not None else 'PARTIAL' if missing or observation.record is None else 'PUBLISHED'
            row['present_fields']=[k for k in required if raw[k] is not None]
            row['missing_fields']=missing
            row['observation_error']=self.render_error(observation.error) if observation.error else None
            row['successful_provenance']=row['publication']=='PUBLISHED'
            out.append(row)
        return out

    def observation_ready(self,admitted):
        return any(c.job.id==admitted['id'] and c.job.generation==admitted['generation'] and c.done.is_set() for c in self.finish_observations)
    def completed(self,admitted):
        matches=[c for c in self.finish_observations if c.job.id==admitted['id'] and c.job.generation==admitted['generation']]
        assert len(matches)==1,'missing_or_ambiguous_finish_attempt'
        return matches[0].require()
    def published_attempts(self,origin):return [c.require() for c in self.finish_observations if c.job.origin==origin]
    @property
    def attempts(self):return [c.require() for c in self.finish_observations if c.done.is_set() and c.error is None]
    @property
    def resources(self):return [{'resource':n,'action':a,'at':t} for n,a,t in tuple(self.raw_resources)]
    def render_cycle(self,c):
        rows=list(tuple(c['events']));rows.extend(r for r in tuple(c['critical']) if r not in rows)
        out=[]
        for name,t,v in rows:
            e={'event':name,'at':t}
            if name=='assignment':e.update(field=v[0],value=self.safe_decision(v[1]) if v[0]=='permission_decision' else v[1],wrapper_entry_at=v[2],original_return_at=v[3])
            elif name=='observation':e.update(observation={'state':v[0],'duration_seconds':v[1]},error=None)
            elif name.endswith('error'):e['error']=self.render_error(v[0] if name!='validation_error' else v[1])
            elif name=='bound_return':e.update(bound=v[0],epoch=v[1],sequence=v[3],sql_actor=self.safe_actor(v[4]))
            elif name.endswith('_return') and name in ('mode_return','source_return','rights_return'):e.update(result=v[0],start=v[1],original_return_at=v[2])
            elif name=='sql_update_return':e.update(rowcount=v[0],original_entry_at=v[2],original_return_at=v[3])
            elif name=='timeout_setting_return':e.update(setting=v[0],milliseconds=v[1])
            elif name=='sql_commit_return':e.update(at=v[0],wrapper_entry_at=v[1],original_entry_at=v[2],scope='delegated Session.commit, not isolated DBAPI')
            elif name=='commit_invoked':e['at']=v[0]
            elif name=='commit_return_ack':e.update(at=v[0],original_entry_at=v[2],original_return_at=v[3],observer_exit_at=v[4])
            elif name=='capture_overhead':e.update(operation=v[0],observer_entry_at=v[1],observer_exit_at=v[2])
            out.append(e)
        before=c['before'];outcome=c.get('outcome');after=outcome[3] if outcome else None;end=c['end']
        return {'start':c['start'],'scope':'observer session-entry interval; runtime aggregate is recorded separately',
            'phase':c['phase'],'job':self.safe_job(c['job']),'actor':self.safe_actor(c['actor']),
            'validated_job':self.safe_job(c.get('validated_job')),
            'events':out,'dropped_events':c['dropped'],'end':end,'duration':end-c['start'] if end else None,
            'before':{'allowed':before[0],'deadline':before[1],'decision':self.safe_decision(before[2])},
            'after':{'allowed':after[0],'deadline':after[1],'decision':self.safe_decision(after[2])} if after else None}
    @property
    def cycles(self):return [self.render_cycle(c) for c in tuple(self.raw_cycles)]
    def cycle_at(self,start):
        matches={c['start']:c for c in [*tuple(self.raw_cycles),*tuple(self.retained)]}
        assert start in matches,'target_cycle_unavailable'
        return self.render_cycle(matches[start])
    def close(self):
        for t in self.threads:t.join(3)
        self.joined=all(not t.is_alive() for t in self.threads)
        assert self.joined,'active renewal owned join absent'
    @property
    def failed(self):return bool(self.errors or self.raw_errors or any(c.error is not None for c in self.finish_observations))
    def compact(self):
        import json
        out={'scope':'bounded primitive capture; nonzero observer overhead, no availability proof',
            'operations':self.operations,'dropped_operations':self.operation_dropped,
            'unbound_selections':[self.render_trigger(t) for t in tuple(self.unbound_selections)],
            'cycles':self.cycles,'retained_denial_cycles':[self.render_cycle(c) for c in tuple(self.retained)],
            'dropped_cycles':self.dropped,'attempts':self.export_attempts(),'resources':self.resources,
            'dropped_resource_events':self.resource_dropped,'errors':[*self.errors,*[self.render_error(e) for e in tuple(self.raw_errors)]],
            'dropped_errors':self.error_dropped,'dropped_stops':self.stop_dropped,
            'cleanup_errors':self.cleanup_errors,'owned_joined':getattr(self,'joined',None),
            'renewal_returns':list(self.raw_returns),'stops':[{'at':t,'issuer':{'file':f.rsplit('/',1)[-1],'function':n,'line':l}} for t,f,n,l in tuple(self.raw_stops)]}
        encoded=json.dumps(out,separators=(',',':'))
        while len(encoded.encode())>60000 and len(out['operations'])>8:
            index=next((i for i,row in enumerate(out['operations']) if row['stage']!='error'),None)
            if index is None:break
            out['operations'].pop(index);out['dropped_operations']+=1;encoded=json.dumps(out,separators=(',',':'))
        while len(encoded.encode())>60000 and len(out['cycles'])>1:
            out['cycles'].pop(1);out['dropped_cycles']+=1;encoded=json.dumps(out,separators=(',',':'))
        assert len(encoded.encode())<65536,'active evidence bound exceeded'
        return encoded
    def emit(self):print('DFA_ACTIVE_RENEWAL '+self.compact(),flush=True)
