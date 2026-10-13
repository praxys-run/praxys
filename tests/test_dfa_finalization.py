"""Deterministic same-exit persistence; synthetic authority and real children/SQL."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from api import activity_dfa as service
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run
from tests.test_activity_dfa import store, confirmed
from tests.test_dfa_origins import both_origins, complete_unit
from tests.dfa_capacity_worker import CapacityWorker, failure
from tests.dfa_boundary_evidence import StartupEvidence,ActiveRenewalEvidence,OccupiedTarget,safe_binding,boundary_junit
from tests.dfa_active_capture import PrimitiveSignal,capture_actor


def wait_for(predicate, seconds=8):
    deadline = time.monotonic()+seconds
    while not predicate():
        assert time.monotonic()<deadline, 'bounded finalization observation absent'
        time.sleep(.005)


def require_complete_output(pending):
    """Check the real validated IPC envelope before a COMPLETE-service fault."""
    assert pending.status=='output','COMPLETE_SERVICE_BOUNDARY_NOT_REACHED'
    count=json.loads(pending.value_json)['result']['summary']['valid_windows']
    assert type(count) is int and count>0,'COMPLETE_NUMERICAL_OUTPUT_NOT_REACHED'


class Cell:
    def __init__(self, store, monkeypatch, tmp_path, mode='lock_release', change=None, seed_complete=False, require_output=False, active_fault=None):
        self.factory, self.owner = store
        self.sup = self.factory.dfa_supervisor
        _, self.admitted = confirmed(self.factory, self.owner)
        if seed_complete:
            with self.factory() as db: claimed=service.claim(db)
            service.execute(self.factory,*claimed)
        self.path, self.mode, self.change = tmp_path, mode, change
        self.target = None
        self.renew_commit_callback = None
        self.current_renewal = PrimitiveSignal()
        self.events, self.renewals, self.launches = [], [], []
        self.blocker = None
        self.finish_calls = 0
        self.finished = threading.Event()
        self.errors = []
        self.active_fault=active_fault
        self.active_cycle=None
        self.active_fault_done=PrimitiveSignal()
        self.active_fault_marker=False
        backend = self.factory.kw['bind'].dialect.name
        args = {'timeout': .1} if backend=='sqlite' else {'options':'-c lock_timeout=200 -c statement_timeout=200'}
        self.engine = create_engine(self.factory.kw['bind'].url, pool_size=2, max_overflow=0, pool_timeout=.1, connect_args=args)
        actual_exit = self.sup.record_exit
        cell = self
        class Controls(Session):
            def execute(session, statement, *a, **kw):
                try:return super().execute(statement,*a,**kw)
                except OperationalError:
                    if cell.active_fault=='lock' and cell.blocker is not None:
                        cell.active_lock_exception_at=time.monotonic()
                        cell.blocker.rollback();cell.blocker.close();cell.blocker=None
                        cell.active_evidence.resource('control_lock','end')
                    raise
        self.sup.controls = sessionmaker(class_=Controls, bind=self.engine)
        self.monitor = CapacityWorker(self.sup, self.errors)
        self.actual_exit=actual_exit
        self.require_output=require_output
        self.backend=backend
        monkeypatch.setattr(self.sup,'record_exit',self.record_exit)
        actual_finish=self.sup.finish
        def finished(job,status,value):
            self.finish_calls+=1
            self.note('finish_entered',status=status,job_binding={k:job[k] for k in ('id','generation','epoch','input')})
            actual_finish(job,status,value)
            self.note('finish_committed')
            self.finished.set()
        monkeypatch.setattr(self.sup,'finish',finished)
        actual_launch=self.sup.lane.launch
        def launch(*a,**kw):
            result=actual_launch(*a,**kw)
            self.launches.append(deepcopy(result[0]))
            return result
        monkeypatch.setattr(self.sup.lane,'launch',launch)
        actual_renew=self.sup.renew
        def renew():
            self.renewals.append(threading.current_thread());actual_renew()
        monkeypatch.setattr(self.sup,'renew',renew)
        self.sup.allowed=False;self.sup.permission_until=0.
        self.diagnostic=StartupEvidence(self.sup,monkeypatch)
        self.diagnostic.note('admitted_entry',job=safe_binding(self.admitted))
        self.active_evidence=ActiveRenewalEvidence(self.sup,self.factory,monkeypatch)
        target=OccupiedTarget(self.admitted,self.sup.identity)
        self.target_primitive=None
        expected_inc=(len(self.sup.identity),tuple(self.sup.identity[k] for k in self.active_evidence.keys))
        def occupied(job,actor):
            self.target=target.acknowledge(job,actor)
            self.target_primitive=capture_actor(self.target,self.active_evidence.keys)
            self.note('occupied_commit_ack',actor=self.target)
        self.active_evidence.on_occupied_ack=occupied
        self.active_evidence.on_sql_commit=self.control_committed
        if active_fault:
            def bound(fields):
                if self.target is None or self.active_cycle is not None:return
                # Pin first post-ACK cycle BEFORE checking it. A mismatch cannot
                # be qualified away by a later favourable cycle/replacement.
                self.active_cycle=fields['started']
                actor=fields['actor']
                assert actor==self.target_primitive and fields['sql_actor']==actor and actor.state=='occupied','FIRST_ACTIVE_TARGET_MISMATCH'
                assert fields['job'] and fields['job'].id==self.admitted['id']
                assert fields['incarnation']==expected_inc and fields['epoch']==self.sup.identity['epoch']
                self.active_fault_marker=True
                self.events.append({'event':'first_active_fault_target','at':time.monotonic()})
                if active_fault=='lock':
                    self.blocker=self.factory.kw['bind'].connect()
                    if backend=='sqlite':self.blocker.exec_driver_sql('BEGIN IMMEDIATE')
                    else:
                        self.blocker.begin()
                        self.blocker.execute(text('SELECT id FROM activity_dfa_control WHERE id=1 FOR UPDATE'))
                    self.active_evidence.resource('control_lock','start')
            self.active_evidence.on_active_bound=bound
            actual_decision=self.sup._decision
            def decision(job,reason,actor=None):
                value=actual_decision(job,reason,actor)
                if self.active_cycle is not None and job and job['id']==self.admitted['id']:
                    self.active_fault_done.set()
                return value
            monkeypatch.setattr(self.sup,'_decision',decision)
            actual_work=self.sup.work
            def work(job,outputs,cancellation=None):
                class Delivered:
                    def put(_,value):
                        def deliver():
                            if value[0]=='output':
                                self.active_evidence.resource('result_delivery','start')
                                try:
                                    assert self.active_fault_done.wait(2),'FIRST_ACTIVE_FAULT_NOT_OBSERVED'
                                    with self.sup.lock:assert not self.sup.allowed
                                finally:self.active_evidence.resource('result_delivery','end')
                            return outputs.put(value)
                        return self.active_evidence.deliver(deliver)
                return actual_work(job,Delivered(),cancellation)
            monkeypatch.setattr(self.sup,'work',work)

    def record_exit(self):
        actor = self.sup.lane.actor()
        matching = self.target and actor['actor_token']==self.target['actor_token']
        if matching:
            assert actor['state']=='idle' and actor.get('exit_observed_at') is not None
            assert actor['binding']==self.target['binding'] and actor['identity']==self.target['identity']
            self.note('verified_target_exit',actor=deepcopy(actor))
            self.note('exit_attempt', actor=deepcopy(actor))
            if self.require_output:
                require_complete_output(self.sup.pending)
            if self.mode in ('lock_release','persistent') and self.blocker is None and not any(e['event']=='lock_released' for e in self.events):
                self.blocker = self.factory.kw['bind'].connect()
                if self.backend=='sqlite': self.blocker.exec_driver_sql('BEGIN IMMEDIATE')
                else:
                    self.blocker.begin()
                    self.blocker.execute(text('SELECT id FROM activity_dfa_control WHERE id=1 FOR UPDATE'))
                self.note('real_control_lock')
                self.active_evidence.resource('control_lock','start')
            if self.mode=='unknown':
                self.note('unknown_fault_applied')
                raise RuntimeError('controlled_unknown_exit_error')
        try:
            return self.monitor.record_exit(self.actual_exit)
        except Exception as exc:
            if matching:
                self.note('exit_error', error=failure(exc), sqlite_code=getattr(getattr(exc,'orig',None),'sqlite_errorcode',None), sqlstate=getattr(getattr(exc,'orig',None),'sqlstate',None))
                if self.mode=='lock_release':
                    self.release_lock()
                    if self.change:
                        self.note('change_callback_entered')
                        self.change(self)
                        self.note('change_callback_returned')
            raise

    def control_committed(self,operation,fields):
        if operation=='renew':
            self.events.append({'event':'renewal_sql_ack','at':time.monotonic()})
            if self.active_fault=='late_ack' and self.active_cycle==fields['started']:
                self.active_evidence.resource('local_ack','start')
                self.events.append({'event':'active_durable_sql_before_delayed_local_ack','at':time.monotonic()})
                time.sleep(.30)
                self.active_evidence.resource('local_ack','end')
            self.current_renewal.set()
            if self.renew_commit_callback and self.target:self.renew_commit_callback()
        elif operation=='exit' and self.target and fields['actor']['actor_token']==self.target['actor_token']:
            self.note('exit_commit_ack',actor=fields['actor'])
            if self.mode=='lost_ack' and not any(e['event']=='lost_ack' for e in self.events):
                if self.require_output:
                    require_complete_output(self.sup.pending)
                self.note('lost_ack_selected_outcome',status=self.sup.pending.status)
                self.note('lost_ack')
                if self.backend=='postgresql':
                    from psycopg.errors import ConnectionFailure
                    error=ConnectionFailure('synthetic lost ACK after actual commit')
                else:
                    error=sqlite3.OperationalError('synthetic lost ACK')
                    error.sqlite_errorcode=sqlite3.SQLITE_BUSY
                raise OperationalError('redacted',{},error)

    def note(self,event,**fields):
        self.events.append({'event':event,'at':time.monotonic(),**fields})
        safe={k:deepcopy(fields[k]) for k in ('status','change','sqlite_code','sqlstate','error') if k in fields}
        if 'actor' in fields:safe['actor']=safe_binding(fields['actor'])
        if 'job_binding' in fields:safe['job']=safe_binding(fields['job_binding'])
        self.diagnostic.note(event,**safe)

    def release_lock(self):
        if self.blocker:
            self.blocker.rollback();self.blocker.close();self.blocker=None
            self.note('lock_released')
            self.active_evidence.resource('control_lock','end')

    def state(self):
        with self.factory() as db:
            run=db.get(Run,self.admitted['id']);control=db.get(Control,1)
            return {'run':{k:getattr(run,k) for k in ('id','status','progress','generation','recoveries','error_code')},'actor':deepcopy(control.actor)}

    def start(self): self.monitor.start()

    def wait_finish_record(self):
        wait_for(lambda:bool(self.errors) or self.active_evidence.observation_ready(self.admitted))
        assert not self.errors,self.active_evidence.compact()
        return self.active_evidence.completed(self.admitted)

    def wait_error(self):
        try:
            wait_for(lambda:bool(self.errors) or self.finished.is_set())
        except BaseException as exc:
            self.diagnostic.error(exc)
            raise AssertionError(self.diagnostic.compact(alive=self.monitor.thread.is_alive(),
                target=self.target,finished=self.finished.is_set())) from exc
        assert self.errors, self.diagnostic.compact(alive=self.monitor.thread.is_alive(),
            target=self.target,finished=self.finished.is_set())
        assert any(e['event']=='occupied_commit_ack' for e in self.events),self.diagnostic.compact()
        assert any(e['event']=='verified_target_exit' for e in self.events),self.diagnostic.compact()

    def close(self):
        primary=sys.exc_info()[1]
        if primary is not None:self.active_evidence.errors.append(self.active_evidence.error(primary))
        snapshot_error=None
        try:
            try:
                for event in list(self.sup.finalization_events)[-16:]:
                    self.diagnostic.note('runtime_finalization',**{k:deepcopy(event[k]) for k in
                        ('operation','attempt','code','error') if k in event},
                        transition=event['event'],observed_at=event['at'])
                # Before any cleanup/owner-erasure: retain observed durable
                # status, never infer a historical reason from current state.
                state=self.state()['run']
                state.pop('id',None)
                self.diagnostic.accepted(self.admitted,{'last_state':state,'service':state['status']})
            except BaseException as exc:
                snapshot_error=exc
                self.diagnostic.error(exc,cleanup=True)
            # Diagnostic collection is never allowed to skip owned shutdown.
            self.release_lock();self.monitor.close()
            self.active_evidence.close()
            for thread in self.renewals: thread.join(5)
            joined=all(not thread.is_alive() for thread in self.renewals)
            self.sup.lane.retire();self.engine.dispose();self.factory.kw['bind'].dispose()
            (self.path/'finalization-evidence.json').write_text(json.dumps({'mode':self.mode,'events':self.events,'monitor':self.monitor.evidence(),'runtime_finalization':list(getattr(self.sup,'finalization_events',[])),'pending':getattr(self.sup,'pending_evidence',lambda:None)(),'launches':self.launches,'finish_calls':self.finish_calls,'state':self.state() if snapshot_error is None else None,'state_error':failure(snapshot_error) if snapshot_error else None,'renewals_joined':joined},indent=2))
            assert joined
            if snapshot_error is not None:raise snapshot_error
        except BaseException as exc:
            if exc is not snapshot_error:self.diagnostic.error(exc,cleanup=True)
            raise
        finally:
            self.diagnostic.primary_errors.extend(self.errors[:4])
            self.diagnostic.cleanup_errors.extend(self.monitor.cleanup_errors[:4])
            self.diagnostic.emit(alive=self.monitor.thread.is_alive(),target=self.target,finished=self.finished.is_set())
            self.active_evidence.emit()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('mode',['lock_release','lost_ack'])
def test_same_exit_persistence_recovers_without_reexecution(store,monkeypatch,tmp_path,mode):
    cell=Cell(store,monkeypatch,tmp_path,mode,require_output=True)
    try:
        cell.start()
        record=cell.wait_finish_record()
        assert record['finish_ack']['after']['status']=='complete',cell.active_evidence.compact()
        assert not cell.errors
        assert cell.finish_calls==1 and len(cell.launches)==1
        state=cell.state();assert state['run']['status']=='complete'
        assert state['run']['recoveries']==0 and state['actor']['state']=='idle'
        assert state['actor']['actor_token']==cell.target['actor_token']
        events=list(getattr(cell.sup,'finalization_events',[]))
        assert any(e['operation']=='exit_persistence' and e['event']=='retry' for e in events)
        assert cell.monitor.thread.is_alive()
        with cell.factory() as db:
            view=service.read_run(db,cell.owner,'123',cell.admitted['id'],0,120)
            assert view['status']=='complete' and view['freshness']=='current'
    finally: cell.close()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_uninjected_active_numerical_service_control(store,monkeypatch,tmp_path):
    cell=Cell(store,monkeypatch,tmp_path,mode='none')
    try:
        cell.start();record=cell.wait_finish_record()
        assert record['finish_ack']['after']['status']=='complete',cell.active_evidence.compact()
        assert cell.state()['run']['status']=='complete',cell.active_evidence.compact()
        with cell.factory() as db:
            view=service.read_run(db,cell.owner,'123',cell.admitted['id'],0,120)
            assert view['freshness']=='current' and view['summary']['valid_windows']>0
        assert cell.active_evidence.attempts[0]['trigger']['selected_status']=='output'
        assert cell.finish_calls==1 and len(cell.launches)==1
    finally:cell.close()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('active_fault',['lock','late_ack'])
def test_real_active_denial_preserved_through_lost_ack(store,monkeypatch,tmp_path,active_fault):
    # A declared failed-service negative, NEVER the COMPLETE-service positive.
    cell=Cell(store,monkeypatch,tmp_path,mode='lost_ack',active_fault=active_fault)
    try:
        cell.start();attempt=cell.wait_finish_record()
        assert cell.active_fault_marker and not cell.errors,cell.active_evidence.compact()
        assert attempt['trigger']['selected_status']=='failed' and attempt['trigger']['expired']
        assert not attempt['trigger']['timed_out']
        assert attempt['finish']['pending_status']=='failed' and attempt['finish']['pending_reason']=='permission_expired'
        assert attempt['finish']['status']=='failed' and attempt['finish']['reason']=='permission_expired'
        assert attempt['finish_ack']['after']['status']=='failed' and attempt['finish_ack']['after']['recoveries']==0
        assert not attempt['finish_ack']['after']['lease_token_hash'] and not attempt['finish_ack']['after']['result_present']
        assert any(e['event']=='lost_ack' for e in cell.events)
        assert attempt['exit_ack']['kind']=='already_durable'
        assert attempt['occupied_ack']['actor']['actor']==attempt['finish']['actor']['actor']
        assert attempt['finish']['actor']['exit_observed_at']<=attempt['exit_ack']['at']<=attempt['finish']['at']
        cycle=cell.active_evidence.cycle_at(cell.active_cycle)
        if active_fault=='lock':
            error=next(e['error'] for e in cycle['events'] if e['event']=='sql_update_error')
            assert error['class']=='OperationalError'
            assert cycle['job']==attempt['claim']['job']
            assert cycle['actor']==attempt['occupied_ack']['actor']
            assert any(e['event']=='bound_return' and e['sql_actor']==attempt['occupied_ack']['actor'] for e in cycle['events'])
            update=next(e for e in cycle['events'] if e['event']=='sql_update_invoked')
            denied=next(e for e in cycle['events'] if e['event']=='sql_update_error')
            held=[e for e in cell.active_evidence.resources if e['resource']=='control_lock']
            assert len(held)==2 and held[0]['action']=='start' and held[1]['action']=='end'
            assert held[0]['at']<=update['at']<=held[1]['at']<=denied['at']
            assert any(e['event']=='mode_return' and e['result']=='manual' for e in cycle['events'])
            assert any(e['event']=='source_return' and e['result'] is True for e in cycle['events'])
            if cell.engine.dialect.name=='sqlite':assert error['sqlite_errorcode']==sqlite3.SQLITE_BUSY
            else:
                settings={e['setting']:e['milliseconds'] for e in cycle['events'] if e['event']=='timeout_setting_return'}
                assert settings=={'statement_timeout_ms':200,'lock_timeout_ms':200}
                assert error['sqlstate'] in ('57014','55P03')
                #57014 alone cannot identify an external cancel issuer. Prove
                # exact control UPDATE/held-lock correlation, not that issuer.
                cell.diagnostic.note('pg_control_denial_scope',sqlstate=error['sqlstate'],
                    query_cancel_issuer='unavailable' if error['sqlstate']=='57014' else None)
        else:
            updated=next(e for e in cycle['events'] if e['event']=='sql_update_return')
            sql_ack=next(e for e in cycle['events'] if e['event']=='sql_commit_return')
            return_ack=next(e for e in cycle['events'] if e['event']=='commit_return_ack')
            held=[e for e in cell.active_evidence.resources if e['resource']=='local_ack']
            assert len(held)==2 and updated['rowcount']==1
            assert sql_ack['at']<=held[0]['at']<held[1]['at']<=return_ack['at']
            assert cycle['duration']>=.30
        assert not cycle['after']['allowed'] and len(cell.launches)==1 and cell.finish_calls==1
    finally:cell.close()




@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('mode',['persistent','unknown'])
def test_unavailable_exit_stops_without_reuse(store,monkeypatch,tmp_path,mode):
    cell=Cell(store,monkeypatch,tmp_path,mode)
    try:
        cell.start();wait_for(lambda:bool(cell.errors))
        state=cell.state()
        assert state['run']['status']=='running' and state['actor']['state']=='occupied'
        assert len(cell.launches)==1 and cell.finish_calls==0
        assert not cell.sup.allowed and cell.sup.pending is not None
        attempts=[e for e in cell.sup.finalization_events if e['event']=='attempt' and e['operation']=='exit_persistence']
        assert len(attempts)==(3 if mode=='persistent' else 1)
        assert all(e['at']-cell.sup.pending.started<1 for e in attempts)
        assert all(b['at']-a['at']>=.125 for a,b in zip(attempts,attempts[1:]))
        assert not cell.monitor.ingress_allowed()
    finally:cell.close()


@pytest.mark.parametrize('action',['stop','start_limit'])
@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_pending_stop_and_scheduling_limit_do_not_start_more_work(both_origins,monkeypatch,tmp_path,action):
    def change(cell):
        if action=='stop':cell.sup.stop.set()
        else:time.sleep(1.02)  # Real elapsed time, never substituted freshness.
        cell.note('scheduling_fault_applied',change=action)
    cell=Cell(both_origins,monkeypatch,tmp_path,change=change)
    try:
        cell.start();cell.wait_error()
        assert any(e['event']=='scheduling_fault_applied' for e in cell.events),cell.diagnostic.compact()
        terminal='stopped' if action=='stop' else 'start_limit'
        code='finalization_stopped' if action=='stop' else 'exit_persistence_start_limit'
        assert any(e['event']==terminal and e.get('code')==code for e in cell.sup.finalization_events),cell.diagnostic.compact()
        attempts=[e for e in cell.sup.finalization_events if e['operation']=='exit_persistence' and e['event']=='attempt']
        assert len(attempts)==1 and len(cell.launches)==1 and cell.finish_calls==0
        assert cell.state()['run']['status']=='running'
        assert not cell.sup.allowed and cell.sup.pending is not None
    finally:cell.close()


@pytest.mark.parametrize('change',['actor','epoch','incarnation'])
@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_exit_projection_cas_rejects_changed_predecessor(both_origins,monkeypatch,tmp_path,change):
    def install(cell):
        actual=cell.sup._actor_guard
        once=[]
        def raced(db,previous):
            if sys._getframe(1).f_code.co_name=='record_exit' and not once:
                once.append(True)
                with cell.factory() as controller:
                    row=controller.get(Control,1)
                    if change=='actor':row.actor={**row.actor,'actor_token':'different-synthetic-actor'}
                    elif change=='epoch':row.epoch+=1
                    else:row.incarnation={**row.incarnation,'source':'different-synthetic-host'}
                    controller.commit()
                cell.note('predecessor_changed_after_read',change=change)
            return actual(db,previous)
        monkeypatch.setattr(cell.sup,'_actor_guard',raced)
    cell=Cell(both_origins,monkeypatch,tmp_path,change=install)
    try:
        cell.start();cell.wait_error()
        assert cell.finish_calls==0 and len(cell.launches)==1
        assert cell.state()['run']['status']=='running'
        assert any(e['event']=='predecessor_changed_after_read' for e in cell.events)
        assert cell.sup.pending is not None and not cell.sup.allowed
        assert any(e['event']=='error' and e['operation']=='exit_persistence'
            and e['error']['reason_code']=='exit_journal_binding_changed'
            for e in cell.sup.finalization_events),cell.diagnostic.compact()
        state=cell.state()
        assert state['actor']['state']=='occupied'  # Exit projection did not overwrite replacement.
        if change=='actor':assert state['actor']['actor_token']=='different-synthetic-actor'
    finally:cell.close()


@pytest.mark.parametrize('store',['postgresql'],indirect=True)
@pytest.mark.parametrize('change',['actor','epoch','incarnation'])
def test_finish_projection_cas_rolls_back_stale_output(store,monkeypatch,tmp_path,change):
    def install(cell):
        actual=cell.sup._actor_guard
        once=[]
        def raced(db,previous):
            if sys._getframe(1).f_code.co_name=='finish' and not once:
                once.append(True)
                with cell.factory() as controller:
                    row=controller.get(Control,1)
                    if change=='actor':row.actor={**row.actor,'actor_token':'different-synthetic-actor'}
                    elif change=='epoch':row.epoch+=1
                    else:row.incarnation={**row.incarnation,'source':'different-synthetic-host'}
                    controller.commit()
                cell.note('finish_predecessor_changed_after_read',change=change)
            return actual(db,previous)
        monkeypatch.setattr(cell.sup,'_actor_guard',raced)
    cell=Cell(store,monkeypatch,tmp_path,change=install)
    try:
        cell.start();wait_for(lambda:bool(cell.errors))
        assert cell.finish_calls==1 and len(cell.launches)==1
        assert cell.state()['run']['status']=='running'
        assert not cell.sup.allowed and cell.sup.pending is not None
        assert any(e['event']=='finish_predecessor_changed_after_read' for e in cell.events)
    finally:cell.close()


@pytest.mark.parametrize('change',['rights','source','generation','STOP'])
def test_fresh_subject_fences_while_finalization_pending(both_origins,monkeypatch,tmp_path,change):
    from analysis import science_artifacts
    from db.models import GarminFitSnapshot
    def invalidate(cell):
        if change=='rights':
            service.storage.record_negative(cell.owner,'processing_withdrawn','origin','manual')
        elif change=='STOP':
            (Path(science_artifacts._SCIENCE_DIR)/'stops/synthetic-pending-stop.yaml').write_text('schema_version: invalid\n')
        else:
            with cell.factory() as db:
                row=db.get(Run,cell.admitted['id'])
                if change=='generation':row.generation+=1;row.status=row.progress='cancelled'
                else:db.get(GarminFitSnapshot,row.snapshot_id).active_parse_id=None
                db.commit()
        cell.note('fresh_subject_invalidated',change=change)
    cell=Cell(both_origins,monkeypatch,tmp_path,change=invalidate)
    try:
        cell.start();wait_for(lambda:cell.finished.is_set() or bool(cell.errors))
        assert not cell.errors
        with cell.factory() as db:
            row=db.get(Run,cell.admitted['id'])
            assert row.status in ('failed','cancelled') and row.result is None
        assert len(cell.launches)==1
    finally:cell.close()


def test_genuine_permission_denied_manual_stays_failed_after_exit_ack(store,monkeypatch,tmp_path):
    import subprocess
    cell=Cell(store,monkeypatch,tmp_path)
    actual=subprocess.Popen
    def held(command,**kw):
        if command[-2:]==['-m','api.dfa_worker']:
            command=[sys.executable,'-E','-B','-c','import sys,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);sys.stdin.buffer.readline(90*1024*1024+1);time.sleep(60)']
        return actual(command,**kw)
    monkeypatch.setattr(subprocess,'Popen',held)
    actual_retire=cell.sup.lane.retire
    def reason_changes(*args,**kwargs):
        actor=cell.sup.lane.actor()
        if actor and actor.get('state')=='occupied' and not cell.sup.allowed:
            cell.sup.retirement_reason='priority'  # Later derived string, not a fresh grant.
            cell.note('derived_reason_changed_during_retirement')
        return actual_retire(*args,**kwargs)
    monkeypatch.setattr(cell.sup.lane,'retire',reason_changes)
    try:
        cell.start();wait_for(lambda:bool(cell.target))
        cell.blocker=cell.factory.kw['bind'].connect();cell.blocker.exec_driver_sql('BEGIN IMMEDIATE')
        cell.note('control_lock_after_manual_ack')
        wait_for(lambda:cell.finished.is_set() or bool(cell.errors))
        assert not cell.errors
        state=cell.state()['run']
        assert state['status']=='failed' and state['error_code']=='permission_expired' and state['recoveries']==0
        assert len(cell.launches)==1 and cell.finish_calls==1
        assert any(e['event']=='exit_error' and e.get('sqlite_code')==5 for e in cell.events)
        assert any(e['event']=='derived_reason_changed_during_retirement' for e in cell.events)
    finally:cell.close()


def test_inflight_renewal_ack_cannot_restore_pending_permission(store,monkeypatch,tmp_path):
    published=threading.Event();release_ack=threading.Event()
    pending=threading.Event();release_pending=threading.Event();held=[]
    def change(cell):
        pending.set();assert release_pending.wait(5)
    cell=Cell(store,monkeypatch,tmp_path,change=change)
    def delayed():
        if held:return
        held.append(True);published.set();assert release_ack.wait(5)
    cell.renew_commit_callback=delayed
    try:
        cell.start();assert published.wait(5);assert pending.wait(5)
        before=cell.sup.permission_until
        assert cell.sup.pending is not None and not cell.sup.allowed
        release_ack.set()
        wait_for(lambda:cell.sup.control_observation['state']=='finalization_pending')
        assert not cell.sup.allowed and cell.sup.permission_until==before
        with cell.factory() as db:
            observed=db.get(Control,1).readiness_sequence
        time.sleep(.15)
        with cell.factory() as db:
            assert db.get(Control,1).readiness_sequence==observed  # No new pending-phase publications.
        release_pending.set();wait_for(lambda:cell.finished.is_set() or bool(cell.errors))
        assert not cell.errors
    finally:
        release_ack.set();release_pending.set();cell.close()


def test_no_replacement_until_exit_ack_and_owner_finish(both_origins,monkeypatch,tmp_path):
    pending=threading.Event();release=threading.Event()
    def change(cell):
        pending.set();assert release.wait(5)
    cell=Cell(both_origins,monkeypatch,tmp_path,change=change)
    from tests.test_dfa_modes import second_owner
    peer = second_owner(cell.factory)
    complete_unit(cell.factory,peer)  # Different entitled owner; no same-owner mode conflict.
    try:
        cell.start();assert pending.wait(5)
        assert cell.sup.pending is not None and not cell.sup.allowed
        assert cell.sup.acquire_job() is None
        assert len(cell.launches)==1 and cell.finish_calls==0
        with cell.factory() as db:
            automatic=db.query(Run).filter_by(origin='automatic').one()
            assert automatic.status=='queued'
        release.set();wait_for(lambda:len(cell.launches)>=2 or bool(cell.errors))
        assert not cell.errors
        ack=next(e['at'] for e in cell.sup.finalization_events if e['operation']=='owner_finish' and e['event']=='ack')
        assert cell.launches[1]['launch_at']>=ack
        assert cell.launches[1]['actor_token']!=cell.launches[0]['actor_token']
    finally:
        release.set();cell.close()


def test_other_idle_actor_is_not_an_allowed_retry_predecessor(store,monkeypatch,tmp_path):
    def replace(cell):
        with cell.factory() as db:
            control=db.get(Control,1)
            control.actor={**control.actor,'state':'idle','actor_token':'foreign-idle-actor','exit_observed_at':time.monotonic()}
            db.commit()
    cell=Cell(store,monkeypatch,tmp_path,change=replace)
    try:
        cell.start();wait_for(lambda:bool(cell.errors))
        assert cell.finish_calls==0 and len(cell.launches)==1
        assert cell.state()['actor']['actor_token']=='foreign-idle-actor'
    finally:cell.close()


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_full_binding_cas_accepts_only_reordered_equivalent_identity(store):
    factory,owner=store
    _,admitted=confirmed(factory,owner)
    supervisor=factory.dfa_supervisor
    with factory() as db:
        control=db.get(Control,1)
        control.incarnation=dict(reversed(list(control.incarnation.items())))
        control.actor=dict(reversed(list(control.actor.items())))
        db.commit()
    with factory() as db:claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        assert db.get(Run,admitted['id']).status=='complete'
        assert db.get(Control,1).actor['state']=='idle'
