"""Actual observer wrappers with declared transport outcomes; no service proof."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from api import activity_dfa as service, dfa_rights

from tests.test_activity_dfa import store
from tests.dfa_boundary_evidence import ActiveRenewalEvidence,OccupiedTarget,boundary_junit
from tests.dfa_active_capture import capture_actor,capture_decision,PrimitiveSignal


def transport(store,monkeypatch,kind='return',hold=None,closing=None,binding='exact',origin='manual',mode_callback=False,retirement=False,during_finish=None,commit_return_hold=None):
    factory,_=store;sup=factory.dfa_supervisor
    job={'id':'synthetic-transport-only','generation':1,'epoch':'1','input':'a'*64,'origin':origin,'phase':'compute'}
    actor={'actor_token':'synthetic-actor','binding':{k:job[k] for k in ('generation','epoch','input')},
        'identity':{'pid':1,'pgid':1,'start':'1','state':'R'},'incarnation':dict(sup.identity),
        'state':'occupied','launch_at':1.,'process_start_observed_at':1.1,'term_at':None,'exit_observed_at':None}
    # Prospective actual pending object, declared negative transport only.
    # No observer fields are seeded and no numerical/runtime authority created.
    import json
    from api.dfa_supervisor import PendingFinalization
    cancelled=threading.Event();cancelled.set()
    pending_actor=dict(actor,state='idle',term_at=2.,exit_observed_at=3.)
    sup.pending=PendingFinalization(json.dumps(job),json.dumps(pending_actor),'null',
        'failed',json.dumps('execution_unavailable'),cancelled,time.monotonic())
    marker=object();original=RuntimeError('private transport canary');calls=[];holder={}
    def model(status):return SimpleNamespace(id=job['id'],phase='compute',status=status,generation=1,recoveries=0,execution_epoch='1',
        input_digest=job['input'],origin=origin,error_code='execution_unavailable',
        lease_token='synthetic-lease' if status=='running' else None,result=None)
    def acquire():
        with sup.factory() as db:
            dfa_rights.execution_current(db,model('running'));dfa_rights.account_mode(db,'synthetic-owner');db.commit()
        return job
    def record(value):calls.append(('record',value));return marker  # No fake journal/PID.
    def work(received,outputs,cancellation=None):
        calls.append(('work',received,outputs,cancellation));sup.lane.record(actor)
        with sup.controls() as db:db.execute(text('SELECT 1'));db.commit()
        return marker
    def finish(received,status,value):
        calls.append(('finish',received,status,value))
        if during_finish:during_finish(sup,received,status,value)
        if kind=='raise':raise original
        run=model('running')
        if binding=='wrong':run.id='wrong'
        if binding=='stale':run.generation=2
        if binding=='missing':del run.id
        if binding=='epoch':run.execution_epoch='2'
        if binding=='input':run.input_digest='other'
        if binding=='origin':run.origin='automatic'
        if binding=='phase':run.phase='prepare'
        with sup.factory() as db:
            if binding!='absent':dfa_rights.execution_current(db,run)
            dfa_rights.account_mode(db,'synthetic-owner')
            run.status='failed';run.lease_token=None
            if kind!='no_ack':db.commit()
        if hold:
            hold[0].set();assert hold[1].wait(2),'transport return release absent'
        return marker
    def renew():
        started=time.monotonic()
        with sup.controls() as db:
            if db.get_bind().dialect.name=='postgresql':
                db.execute(text("SET LOCAL statement_timeout='200ms'"));db.execute(text("SET LOCAL lock_timeout='200ms'"))
            sup._bound(db);db.execute(text('SELECT 1'));db.commit()
            with sup.lock:
                sup.permission_decision=sup._decision(job,'permission',actor)
                sup.allowed=False  # Never grant positive permission in this transport fixture.
            sup.control_observation={'state':'denied','duration_seconds':time.monotonic()-started}
    mode_events=[]
    if mode_callback:
        from tests.test_dfa_modes import mode_finish_callback
        finish=mode_finish_callback(sup,finish,mode_events,[],[])
    if retirement:
        def retire(*args,**kwargs):calls.append(('retire',args,kwargs));return marker
        monkeypatch.setattr(sup.lane,'retire',retire)
    monkeypatch.setattr(sup,'acquire_job',acquire);monkeypatch.setattr(sup,'work',work)
    monkeypatch.setattr(sup,'finish',finish);monkeypatch.setattr(sup,'renew',renew);monkeypatch.setattr(sup.lane,'record',record)
    if closing:
        class Close(sup.controls.class_):
            def close(session):super().close();raise closing
        sup.controls=sessionmaker(class_=Close,**sup.controls.kw)
    # Declared negative underlying authority outcomes, exercised through the
    # actual shared wrappers. Transport only, never positive policy permission.
    monkeypatch.setattr(dfa_rights,'execution_current',lambda db,run:False)
    monkeypatch.setattr(service,'_current',lambda db,run:False)
    monkeypatch.setattr(dfa_rights,'account_mode',lambda db,owner:'unavailable')
    if commit_return_hold:
        class CommitReturn(sup.controls.class_):
            def commit(session):
                result=super().commit()
                commit_return_hold[0].set()
                assert commit_return_hold[1].wait(2),'declared commit-return hold not released'
                return result
        sup.controls=sessionmaker(class_=CommitReturn,**sup.controls.kw)
    e=ActiveRenewalEvidence(sup,factory,monkeypatch);holder['observer']=e
    e.mode_callback_events=mode_events
    return e,job,actor,marker,original,calls


def invoke_thread(actual):
    errors=[]
    def call():
        try:actual()
        except BaseException as exc:errors.append(exc)
    thread=threading.Thread(target=call,name='observer-transport');thread.start()
    return thread,errors


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_actual_composition_exact_first_target(store,monkeypatch):
    e,job,actor,marker,_,calls=transport(store,monkeypatch)
    target=OccupiedTarget(job,e.sup.identity);acks=[]
    def ack(value,physical):acks.append(target.acknowledge(value,physical))
    e.on_occupied_ack=ack
    try:
        assert e.sup.acquire_job() is job
        output=object();cancel=object()
        assert e.sup.work(job,output,cancel) is marker
        assert len(acks)==1 and acks[0]==actor
        assert calls[-1][0]=='record' and calls[-1][1] is actor
        with pytest.raises(AssertionError,match='duplicate'):e.sup.work(job,output,cancel)
    finally:e.emit()


@pytest.mark.parametrize('change',['missing','binding','generation','epoch','incarnation','identity','replacement'])
def test_first_target_rejection_is_not_reselected(change):
    from copy import deepcopy
    job={'id':'synthetic','generation':1,'origin':'manual','epoch':'1','input':'input','phase':'compute'};inc={'epoch':1}
    actor={'state':'occupied','actor_token':'synthetic','incarnation':dict(inc),'binding':{k:job[k] for k in ('generation','epoch','input')},'identity':{'pid':1,'pgid':1,'start':'synthetic'}}
    target=OccupiedTarget(job,inc);bad=deepcopy(actor);other=dict(job)
    if change=='missing':bad=None
    elif change=='binding':bad['binding']['input']='other'
    elif change=='generation':other['generation']=2
    elif change=='epoch':other['epoch']='2';bad['binding']['epoch']='2'
    elif change=='incarnation':bad['incarnation']['epoch']=2
    elif change=='identity':bad['identity'].pop('start')
    else:target.acknowledge(job,actor);bad['actor_token']='replacement'
    with pytest.raises(AssertionError):target.acknowledge(other,bad)
    with pytest.raises(AssertionError,match='duplicate'):target.acknowledge(job,actor)


def test_missing_and_ambiguous_finish_records_fail(store,monkeypatch):
    e,job,_,_,_,_=transport(store,monkeypatch)
    try:
        with pytest.raises(AssertionError,match='missing_or_ambiguous'):e.completed(job)
        e.sup.acquire_job();e.sup.acquire_job()
        with pytest.raises(AssertionError,match='missing_or_ambiguous'):e.completed(job)
    finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_publication_precedes_signal_for_declared_failed_transport(store,monkeypatch):
    inner=PrimitiveSignal();release=PrimitiveSignal()
    e,job,_,marker,_,_=transport(store,monkeypatch,hold=(inner,release))
    e.sup.acquire_job()
    result=[]
    thread,errors=invoke_thread(lambda:result.append(e.sup.finish(job,'failed','execution_unavailable')))
    try:
        assert inner.wait(2)
        assert not e.observation_ready(job)
        with pytest.raises(AssertionError,match='not_complete'):e.completed(job)
        release.set();thread.join(3)
        assert not thread.is_alive() and not errors and result==[marker]
        record=e.completed(job)
        assert record['finish']['status']=='failed' and record['finish_ack']['after']['status']=='failed'
        record['finish_ack']['after']['status']='modified-copy'
        assert e.completed(job)['finish_ack']['after']['status']=='failed'
    finally:release.set();thread.join(3);e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_original_finish_exception_and_async_delivery_identity(store,monkeypatch):
    e,job,_,_,original,calls=transport(store,monkeypatch,kind='raise');e.sup.acquire_job()
    try:
        with pytest.raises(RuntimeError) as caught:e.sup.finish(job,'failed','execution_unavailable')
        assert caught.value is original and calls[-1]==('finish',job,'failed','execution_unavailable')
        with pytest.raises(AssertionError,match='observation_failed'):e.completed(job)
        def failed():raise original
        with pytest.raises(RuntimeError) as caught:e.deliver(failed)
        assert caught.value is original
        assert 'canary' not in e.compact()
        import json
        partial=json.loads(e.compact())['attempts'][0]
        assert partial['publication']=='FAILED' and partial['observation_error']['class']=='RuntimeError'
        assert partial['finish']['status']=='failed'
    finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_close_error_retained_and_forwarded(store,monkeypatch):
    original=RuntimeError('private close canary');e,*_=transport(store,monkeypatch,closing=original)
    thread,errors=invoke_thread(e.sup.renew);thread.join(3)
    try:
        assert not thread.is_alive() and errors==[original]
        c=e.cycles[0]
        assert any(v['event']=='session_exit_error' and v['error']['class']=='RuntimeError' for v in c['events'])
        assert 'canary' not in e.compact()
    finally:e.sup.stop.set();e.close();e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_unfinished_cycle_shutdown_and_immediate_return_timestamps(store,monkeypatch):
    e,*_=transport(store,monkeypatch);entered=PrimitiveSignal();release=PrimitiveSignal()
    class Held(e.sup.controls.class_):
        def commit(session):
            result=super().commit();entered.set();assert release.wait(2);return result
    e.sup.controls=sessionmaker(class_=Held,**e.sup.controls.kw)
    thread,errors=invoke_thread(e.sup.renew)
    try:
        assert entered.wait(2)
        assert e.cycles[0]['end'] is None
        # Outer fixture still holds its return; inner captured method ACK is
        # explicitly scoped to that method, not the enclosing wrapper/driver.
        assert any(v['event']=='sql_commit_return' for v in e.cycles[0]['events'])
        e.sup.stop.set();release.set();thread.join(3)
        assert not errors and not thread.is_alive()
    finally:release.set();e.close();e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_hot_capture_has_no_formatting_lock_or_supplementary_sql(store,monkeypatch):
    e,_,actor,_,_,_=transport(store,monkeypatch)
    for name in ('safe_job','safe_actor','state_dict','actor_dict','render_error','compact'):
        actual=getattr(e,name)
        def guarded(*args,_actual=actual,**kwargs):
            assert not getattr(e.local,'renew',False) and not e.sup.lock.locked(),'expensive formatting in hot capture'
            return _actual(*args,**kwargs)
        monkeypatch.setattr(e,name,guarded)
    # An extra diagnostic read would touch this API; actual observer uses only
    # already-loaded model fields and delegated original sessions.
    monkeypatch.setattr(e,'factory',lambda:(_ for _ in ()).throw(AssertionError('supplementary SQL')))
    thread,errors=invoke_thread(e.sup.renew);thread.join(3)
    try:
        assert not thread.is_alive() and not errors
        frozen=e.cycles[0]['after']['decision']['actor']['state']
        actor['state']='changed-later'
        assert e.cycles[0]['after']['decision']['actor']['state']==frozen=='occupied'
        tree=ast.parse(Path('tests/dfa_active_capture.py').read_text())
        roots={'__setattr__','__enter__','execute','commit','__exit__','bound','call','event','capture_state','capture_job','capture_actor','capture_decision','raw_error'}
        forbidden={'_getframe','deepcopy','sha256','dumps','loads','Lock','RLock','acquire','actor'}
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in roots:
                for call in ast.walk(node):
                    if isinstance(call,ast.Call):
                        name=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id if isinstance(call.func,ast.Name) else ''
                        assert name not in forbidden,(node.name,name)
        assert not e.raw_attempts  # No pretend claim/authority/service assertion.
    finally:e.sup.stop.set();e.close();e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('binding',['wrong','stale','missing','absent','epoch','input','origin','phase'])
def test_real_rights_wrapper_binding_failure_exports_partial(store,monkeypatch,binding):
    import json
    e,job,_,marker,_,_=transport(store,monkeypatch,binding=binding)
    e.sup.acquire_job()
    try:
        assert e.sup.finish(job,'failed','execution_unavailable') is marker
        with pytest.raises(AssertionError,match='observation_failed'):e.completed(job)
        row=json.loads(e.compact())['attempts'][0]
        assert row['publication']=='FAILED' and not row['successful_provenance']
        assert row['observation_error']['class']=='AssertionError'
        assert row['claim']['state']['lease_token_hash']
        assert row['finish']['status']=='failed'
        assert 'occupied' in row['missing_fields'] and 'finish' in row['present_fields']
        assert 'canary' not in e.compact()
    finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_actual_rights_model_snapshot_survives_source_mutation(store,monkeypatch):
    import json
    e,job,_,marker,_,_=transport(store,monkeypatch)
    e.sup.acquire_job()
    try:
        assert e.sup.finish(job,'failed','execution_unavailable') is marker
        r=e.completed(job)
        assert r['finish']['before']['status']=='running'
        assert r['finish']['before']['lease_token_hash']
        assert r['finish_ack']['after']['status']=='failed'
        assert r['finish']['current'] is False and r['finish']['mode']=='unavailable'
        # Transport has no physical/selected proof and must export PARTIAL.
        row=json.loads(e.compact())['attempts'][0]
        assert row['publication']=='PARTIAL' and not row['successful_provenance']
    finally:e.emit()


# These controlled records exercise the exact Cell fault callbacks, not a
# service/authority positive. No envelope is injected into runtime execution.
def callback_cell(callback,shape):
    import json
    from tests.test_dfa_finalization import Cell
    cell=Cell.__new__(Cell)
    actor={'actor_token':'synthetic-callback','state':'idle','exit_observed_at':2.,
        'binding':{'generation':1,'epoch':'1','input':'synthetic'},
        'identity':{'pid':1,'pgid':1,'start':'synthetic'}}
    value={'binding':dict(actor['binding']),'actor_token':actor['actor_token'],
        'inventory':{'outcome':'controlled-transport'},'result':{'summary':{'valid_windows':42}}}
    status='output'
    if shape=='missing_result':value.pop('result')
    elif shape=='missing_summary':value['result'].pop('summary')
    elif shape=='nonnumeric':value['result']['summary']['valid_windows']='42'
    elif shape=='boolean':value['result']['summary']['valid_windows']=True
    elif shape=='zero':value['result']['summary']['valid_windows']=0
    elif shape=='failed':status='failed';value={'error':'execution_unavailable'}
    elif shape=='error_envelope':value={'error':'execution_unavailable'}
    cell.sup=SimpleNamespace(lane=SimpleNamespace(actor=lambda:actor),
        pending=SimpleNamespace(status=status,value_json=json.dumps(value)))
    cell.target=actor;cell.events=[];cell.require_output=True;cell.backend='sqlite'
    cell.mode='unknown' if callback=='exit' else 'lost_ack'
    cell.note=lambda event,**fields:cell.events.append({'event':event,**fields})
    calls=[];marker=object();original=RuntimeError('private callback canary')
    def forwarded(actual):calls.append(actual);return marker
    cell.monitor=SimpleNamespace(record_exit=forwarded);cell.actual_exit=object()
    cell.change=None;cell.blocker=None
    return cell,calls,marker,original


@pytest.mark.parametrize('callback',['exit','commit'])
@pytest.mark.parametrize('shape',['valid','missing_result','missing_summary','nonnumeric','boolean','zero','failed','error_envelope'])
def test_exact_cell_callback_requires_ipc_result_summary_before_fault(callback,shape):
    from sqlalchemy.exc import OperationalError
    cell,calls,_,_=callback_cell(callback,shape)
    invoke=cell.record_exit if callback=='exit' else lambda:cell.control_committed('exit',{'actor':cell.target})
    if shape=='valid':
        with pytest.raises(RuntimeError if callback=='exit' else OperationalError):invoke()
        assert any(e['event']==('unknown_fault_applied' if callback=='exit' else 'lost_ack') for e in cell.events)
    else:
        with pytest.raises((KeyError,AssertionError)):invoke()
        assert not any(e['event'] in ('unknown_fault_applied','real_control_lock','lost_ack','lost_ack_selected_outcome') for e in cell.events)
    assert calls==[]  # Fault/invalid prerequisite never forwards exit here.


@pytest.mark.parametrize('outcome',['return','exception'])
def test_exact_cell_exit_callback_preserves_original_forwarding(outcome):
    cell,calls,marker,original=callback_cell('exit','valid');cell.mode='none'
    def forwarded(actual):
        calls.append(actual)
        if outcome=='exception':raise original
        return marker
    cell.monitor.record_exit=forwarded
    if outcome=='return':assert cell.record_exit() is marker
    else:
        with pytest.raises(RuntimeError) as caught:cell.record_exit()
        assert caught.value is original
    assert calls==[cell.actual_exit]
    assert not any(e['event'] in ('unknown_fault_applied','real_control_lock','lost_ack') for e in cell.events)


@pytest.mark.parametrize('origin',['manual','automatic'])
@pytest.mark.parametrize('outcome',['return','exception'])
def test_actual_mode_callback_scope_and_owner_ack_transport(store,monkeypatch,origin,outcome):
    e,job,actor,marker,original,calls=transport(store,monkeypatch,
        kind='raise' if outcome=='exception' else 'return',origin=origin,mode_callback=True)
    original_actor=e.sup.lane.actor
    e.sup.acquire_job()
    try:
        with monkeypatch.context() as actor_patch:
            actor_patch.setattr(e.sup.lane,'actor',lambda:actor)
            if outcome=='return':
                assert e.sup.finish(job,'failed','execution_unavailable') is marker
                record=e.completed(job)
                assert record['finish_ack']['at'] and record['finish_ack']['after']['status']=='failed'
                assert [event for event,_ in e.mode_callback_events]==['finish_'+origin]
            else:
                with pytest.raises(RuntimeError) as caught:e.sup.finish(job,'failed','execution_unavailable')
                assert caught.value is original
                assert e.mode_callback_events==[]
                with pytest.raises(AssertionError,match='observation_failed'):e.completed(job)
            assert calls[-1]==('finish',job,'failed','execution_unavailable')
    finally:
        # The real store finalizer must never see the controlled identity.
        try:assert e.sup.lane.actor==original_actor
        finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_missing_owner_ack_never_publishes_finish_success(store,monkeypatch):
    import json
    e,job,actor,marker,_,_=transport(store,monkeypatch,kind='no_ack',mode_callback=True)
    original_actor=e.sup.lane.actor
    e.sup.acquire_job()
    try:
        with monkeypatch.context() as actor_patch:
            actor_patch.setattr(e.sup.lane,'actor',lambda:actor)
            assert e.sup.finish(job,'failed','execution_unavailable') is marker
            with pytest.raises(AssertionError,match='observation_failed'):e.completed(job)
            row=json.loads(e.compact())['attempts'][0]
            assert row['publication']=='FAILED' and not row['successful_provenance']
            assert 'ack_at' in row['missing_fields'] and row['observation_error']['class']=='AssertionError'
    finally:
        try:assert e.sup.lane.actor==original_actor
        finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_actual_retire_wrapper_first_snapshot_survives_finish_exception_and_cleanup(store,monkeypatch):
    import json
    from api.dfa_supervisor import Supervisor
    original_retire=store[0].dfa_supervisor.lane.retire
    with monkeypatch.context() as transport_patch:
        e,job_template,actor,marker,original,calls=transport(store,transport_patch,kind='raise',retirement=True)
        frozen=[]
        def reactor(self):
            # Two predeclared negative transport attempts; no service/authority or
            # recovery claim. Exact shared wrappers, original exceptions forwarded.
            for number in (1,2):
                job=self.acquire_job()
                actor['actor_token']='synthetic-retirement-'+str(number)
                self.work(job,object())
                actor_before=actor;expired=True;timed_out=False;ready=False;status='failed';value='permission_expired'
                decision=self._decision(job,'permission',actor)
                try:
                    assert self.lane.retire() is marker
                    frozen.append(e.raw_attempts[-1]['trigger'])
                    with pytest.raises(RuntimeError) as caught:self.finish(job,status,value)
                    assert caught.value is original
                finally:
                    # Changed cleanup locals cannot replace an initial decision.
                    expired=False;ready=True;status='output';value=None
                    assert self.lane.retire() is marker
        transport_patch.setattr(Supervisor,'run',reactor)
        try:
            e.sup.run()
            assert len(frozen)==2 and frozen[0][0]<frozen[1][0]
            for index,raw in enumerate(e.raw_attempts):
                assert raw['trigger'] is frozen[index]
                assert raw['trigger'][1:6]==(True,False,False,'failed','permission_expired')
                assert len(raw['cleanup_retirements'])==1
                assert raw['cleanup_retirements'][0][0]>=raw['trigger'][0]
                assert raw['cleanup_retirements'][0][1:6]==(False,False,True,'output',None)
            exported=json.loads(e.compact())['attempts']
            assert len(exported)==2
            for record in exported:
                assert record['publication']=='FAILED' and record['observation_error']['class']=='RuntimeError'
                assert not record['successful_provenance']
                assert record['trigger']['selected_reason']=='permission_expired'
                assert record['cleanup_retirements'][0]['event']=='subsequent_cleanup_retirement_capture'
            assert len([c for c in calls if c[0]=='retire'])==4
            assert 'canary' not in e.compact()
        finally:e.emit()
    assert store[0].dfa_supervisor.lane.retire==original_retire


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('change',['valid','job','generation','input','epoch','actor','reason','unknown_value','status','absent','partial','invalid_job_json','invalid_actor_json','invalid_value_json','output_value','mutate'])
def test_actual_pending_snapshot_falsifies_shared_service_ledger(store,monkeypatch,change):
    import json
    from dataclasses import replace
    from api.dfa_supervisor import Supervisor,PendingFinalization
    from tests.dfa_attempt_evidence import assert_pending_binding
    original_retire=store[0].dfa_supervisor.lane.retire
    with monkeypatch.context() as patch:
        mutation=[]
        def mutate_after_entry(sup,job,status,value):
            if change!='mutate':return
            pending=sup.pending;pending.cancellation.clear()
            object.__setattr__(pending,'job_json',json.dumps(dict(job,generation=99)))
            object.__setattr__(pending,'actor_json','null')
            object.__setattr__(pending,'value_json',json.dumps('execution_unavailable'))
            object.__setattr__(pending,'status','output')
            mutation.append(True)
        e,template,actor,marker,_,calls=transport(store,patch,retirement=True,during_finish=mutate_after_entry)
        def reactor(self):
            job=self.acquire_job();self.work(job,object())
            actor_before=dict(actor);expired=True;timed_out=False;ready=False;status='failed';value='permission_expired'
            if change=='output_value':
                # Controlled envelope comparison negative, never numerical
                # service/authority. Original argument/envelope stay untouched.
                expired=False;ready=True;status='output'
                value={'binding':dict(actor['binding']),'actor_token':actor['actor_token'],
                    'inventory':{},'result':{'summary':{'valid_windows':1}}}
            chosen_value_json=json.dumps(value)
            decision=self._decision(job,'permission',actor_before)
            assert self.lane.retire() is marker
            actor.update(state='idle',term_at=time.monotonic(),exit_observed_at=time.monotonic())
            self.lane.record(actor)
            cancellation=threading.Event();cancellation.set()
            actual_job=dict(job);actual_actor=json.loads(json.dumps(actor));actual_value=value;actual_status=status
            if change=='job':actual_job['id']='different-job'
            if change=='generation':actual_job['generation']+=1
            if change=='input':actual_job['input']='f'*64
            if change=='epoch':actual_job['epoch']='2'
            if change=='actor':actual_actor['actor_token']='different-actor'
            if change=='output_value':
                actual_value=json.loads(json.dumps(value));actual_value['result']['summary']['valid_windows']=2
            if change=='reason':actual_value='execution_unavailable'
            if change=='unknown_value':actual_value='private pending canary'
            if change=='status':actual_status='output'
            pending=PendingFinalization(json.dumps(actual_job),json.dumps(actual_actor),'null',actual_status,json.dumps(actual_value),cancellation,time.monotonic())
            if change=='absent':pending=None
            if change=='partial':pending=SimpleNamespace(status=status,cancellation=cancellation)
            if change=='invalid_job_json':pending=replace(pending,job_json='{')
            if change=='invalid_actor_json':pending=replace(pending,actor_json='{')
            if change=='invalid_value_json':pending=replace(pending,value_json='{')
            self.pending=pending
            assert self.finish(job,status,value) is marker
        patch.setattr(Supervisor,'run',reactor)
        try:
            e.sup.run()
            row=json.loads(e.compact())['attempts'][0]
            if change in ('valid','mutate'):
                assert_pending_binding(row)
                assert row['finish']['pending_reason']=='permission_expired'
                assert row['finish']['pending_snapshot']['cancelled'] is True
                assert json.loads(json.dumps(e.completed(template)['finish']['pending_snapshot']))==row['finish']['pending_snapshot']
                assert bool(mutation)==(change=='mutate')
            else:
                with pytest.raises(AssertionError):assert_pending_binding(row)
                assert row['publication']=='FAILED' and not row['successful_provenance']
                assert row['observation_error']['class']=='AssertionError'
                assert row['finish']['reason']==row['trigger']['selected_reason']
                assert row['finish']['value']==row['trigger']['value']
            assert calls[-1][0]=='finish' and calls[-1][1]==template
            assert calls[-1][2]==row['finish']['status']
            assert 'canary' not in e.compact()
        finally:e.emit()
    assert store[0].dfa_supervisor.lane.retire==original_retire


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_actual_selection_before_occupied_publication_is_immutable_partial(store,monkeypatch):
    """Declared negative transport: no permission/service/physical PID proof."""
    from api.dfa_supervisor import Supervisor
    from tests.dfa_attempt_evidence import assert_pending_binding
    from copy import deepcopy
    barrier=(threading.Event(),threading.Event())
    with monkeypatch.context() as patch:
        e,template,actor,marker,_,_=transport(store,patch,retirement=True,commit_return_hold=barrier)
        thread=None;frozen=[]
        def reactor(self):
            nonlocal thread
            job=self.acquire_job()
            thread,errors=invoke_thread(lambda:self.work(job,object()))
            assert barrier[0].wait(2)
            actor_before=actor;expired=True;timed_out=False;ready=False;status='failed';value='permission_expired'
            decision=self._decision(job,'permission',actor)
            assert self.lane.retire() is marker
            first=e.raw_attempts[0]['trigger'];frozen.append(first)
            assert first is not None and first[10] is False and e.raw_attempts[0]['occupied'] is None
            barrier[1].set();thread.join(3);assert not thread.is_alive() and not errors
            assert e.raw_attempts[0]['trigger'] is first and e.raw_attempts[0]['occupied'] is not None
            before=deepcopy(e.render_trigger(first))
            self.finish(job,status,value)
            expired=False;ready=True;status='output';value=None
            assert self.lane.retire() is marker
            assert e.render_trigger(first)==before
        patch.setattr(Supervisor,'run',reactor)
        try:
            e.sup.run();row=e.export_attempts()[0]
            assert row['publication']=='FAILED' and not row['successful_provenance']
            assert row['observation_error']['class']=='AssertionError'
            assert 'selection.occupied_ack_before_selection' in row['missing_fields']
            with pytest.raises(AssertionError,match='occupied_ack_missing_at_selection'):assert_pending_binding(row)
            assert len(row['cleanup_retirements'])==1
        finally:
            barrier[1].set()
            if thread:thread.join(3);assert not thread.is_alive()
            e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('binding',['actor','job','generation','epoch','missing_actor'])
def test_actual_retirement_binding_rejection_still_exports_first_choice(store,monkeypatch,binding):
    from api.dfa_supervisor import Supervisor
    with monkeypatch.context() as patch:
        e,template,actor,marker,_,_=transport(store,patch,retirement=True)
        def reactor(self):
            job=self.acquire_job();self.work(job,object())
            actor_before=dict(actor);expired=True;timed_out=False;ready=False;status='failed';value='permission_expired'
            decision=self._decision(job,'permission',actor)
            if binding=='actor':actor_before['actor_token']='wrong'
            if binding=='missing_actor':actor_before=None
            if binding=='job':job=dict(job,id='wrong')
            if binding=='generation':job=dict(job,generation=99)
            if binding=='epoch':job=dict(job,epoch='99')
            assert self.lane.retire() is marker
        patch.setattr(Supervisor,'run',reactor)
        try:
            e.sup.run();data=json.loads(e.compact())
            if binding in ('job','generation','epoch'):
                assert data['unbound_selections'][0]['selected_reason']=='permission_expired'
                assert data['errors'][0]['class']=='AssertionError'
            else:
                assert data['attempts'][0]['trigger']['selected_reason']=='permission_expired'
                assert not data['attempts'][0]['successful_provenance']
                if binding=='actor':assert data['errors'][0]['class']=='AssertionError'
        finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_actual_occupied_callback_exception_has_separate_commit_exit_publication(store,monkeypatch):
    e,job,actor,marker,_,_=transport(store,monkeypatch)
    original=RuntimeError('PRIVATE_CREDENTIAL RR SQL_PARAMS')
    def callback(*args):raise original
    e.on_occupied_ack=callback
    try:
        e.sup.acquire_job()
        with pytest.raises(RuntimeError) as caught:e.sup.work(job,object())
        assert caught.value is original
        assert e.raw_attempts[0]['occupied'] is not None
        ops=e.operations
        returned=next(x for x in ops if x['scope']=='controls' and x['operation']=='commit' and x['stage']=='return')
        error=next(x for x in ops if x['operation']=='occupied_callback' and x['stage']=='error')
        exited=next(x for x in ops if x['scope']=='controls' and x['operation']=='session_exit' and x['stage']=='return')
        assert returned['at']<=error['at']<=exited['at']
        assert error['error']['class']=='RuntimeError' and error['session']==returned['session']==exited['session']
        assert 'PRIVATE_CREDENTIAL' not in e.compact() and 'SQL_PARAMS' not in e.compact()
    finally:e.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('close_error',[False,True])
def test_actual_first_postoccupied_cycle_retains_denial_close_error_and_no_reselection(store,monkeypatch,close_error):
    from tests.dfa_active_capture import capture_job,capture_actor
    e,job,actor,marker,_,_=transport(store,monkeypatch)
    original=RuntimeError('PRIVATE_CYCLE_CREDENTIAL')
    try:
        e.sup.acquire_job();e.sup.work(job,object())
        e.sup.active=job  # Declared transport state, no positive permission.
        first=e.first_occupied_cycle
        first.arm(capture_job(job),capture_actor(actor,e.keys),time.monotonic())
        actual=e.sup.controls
        if close_error:
            class Closing(actual.class_):
                def close(session):super().close();raise original
            monkeypatch.setattr(e.sup,'controls',sessionmaker(class_=Closing,**actual.kw))
            thread,errors=invoke_thread(e.sup.renew);thread.join(3)
            assert not thread.is_alive() and errors==[original]
        else:
            thread,errors=invoke_thread(e.sup.renew);thread.join(3)
            assert not thread.is_alive() and not errors
        assert first.event.is_set() and first.observation['reason']=='permission'
        frozen=first.raw
        assert frozen[1] is not None and frozen[4][3][0] is False
        assert bool(frozen[5])==close_error
        monkeypatch.setattr(e.sup,'controls',actual)
        actor['state']='changed_after_capture'
        thread,errors=invoke_thread(e.sup.renew);thread.join(3)
        assert not thread.is_alive() and not errors
        assert first.raw is frozen and first.observation['actor']['state']=='occupied'
        with pytest.raises(AssertionError,match='duplicate'):first.arm(capture_job(job),capture_actor(actor,e.keys),time.monotonic())
        assert 'PRIVATE_CYCLE_CREDENTIAL' not in e.compact()
    finally:e.sup.stop.set();e.close();e.emit()
