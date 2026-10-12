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


def wait_for(predicate, seconds=8):
    deadline = time.monotonic()+seconds
    while not predicate():
        assert time.monotonic()<deadline, 'bounded finalization observation absent'
        time.sleep(.005)


class Cell:
    def __init__(self, store, monkeypatch, tmp_path, mode='lock_release', change=None, seed_complete=False):
        self.factory, self.owner = store
        self.sup = self.factory.dfa_supervisor
        _, self.admitted = confirmed(self.factory, self.owner)
        if seed_complete:
            with self.factory() as db: claimed=service.claim(db)
            service.execute(self.factory,*claimed)
        self.path, self.mode, self.change = tmp_path, mode, change
        self.target = None
        self.renew_commit_callback = None
        self.current_renewal = threading.Event()
        renew_code = self.sup.renew.__func__.__code__
        self.events, self.renewals, self.launches = [], [], []
        self.blocker = None
        self.finish_calls = 0
        self.finished = threading.Event()
        self.errors = []
        backend = self.factory.kw['bind'].dialect.name
        args = {'timeout': .1} if backend=='sqlite' else {'options':'-c lock_timeout=200 -c statement_timeout=200'}
        self.engine = create_engine(self.factory.kw['bind'].url, pool_size=2, max_overflow=0, pool_timeout=.1, connect_args=args)
        actual_exit = self.sup.record_exit
        actual_work_code = self.sup.work.__func__.__code__
        exit_code = actual_exit.__func__.__code__
        cell = self
        class Controls(Session):
            def commit(self):
                caller = sys._getframe(1)
                result = super().commit()
                if caller.f_code is renew_code:
                    cell.current_renewal.set()
                    if cell.renew_commit_callback and cell.target:
                        cell.renew_commit_callback()
                if caller.f_code is actual_work_code:
                    cell.target = deepcopy(caller.f_locals['actor'])
                    cell.note('occupied_commit_ack', actor=cell.target)
                if caller.f_code is exit_code and cell.target and caller.f_locals['actor']['actor_token']==cell.target['actor_token']:
                    cell.note('exit_commit_ack', actor=deepcopy(caller.f_locals['actor']))
                    if mode=='lost_ack' and not any(e['event']=='lost_ack' for e in cell.events):
                        cell.note('lost_ack')
                        if backend=='postgresql':
                            from psycopg.errors import ConnectionFailure
                            error=ConnectionFailure('synthetic lost ACK after actual commit')
                        else:
                            error=sqlite3.OperationalError('synthetic lost ACK')
                            error.sqlite_errorcode=sqlite3.SQLITE_BUSY
                        raise OperationalError('redacted',{},error)
                return result
        self.sup.controls = sessionmaker(class_=Controls, bind=self.engine)
        self.monitor = CapacityWorker(self.sup, self.errors)
        def exited():
            actor = self.sup.lane.actor()
            matching = self.target and actor['actor_token']==self.target['actor_token']
            if matching:
                self.note('exit_attempt', actor=deepcopy(actor))
                if mode in ('lock_release','persistent') and self.blocker is None and not any(e['event']=='lock_released' for e in self.events):
                    self.blocker = self.factory.kw['bind'].connect()
                    if backend=='sqlite': self.blocker.exec_driver_sql('BEGIN IMMEDIATE')
                    else:
                        self.blocker.begin()
                        self.blocker.execute(text('SELECT id FROM activity_dfa_control WHERE id=1 FOR UPDATE'))
                    self.note('real_control_lock')
                if mode=='unknown': raise RuntimeError('controlled_unknown_exit_error')
            try:
                return self.monitor.record_exit(actual_exit)
            except Exception as exc:
                if matching:
                    self.note('exit_error', error=failure(exc), sqlite_code=getattr(getattr(exc,'orig',None),'sqlite_errorcode',None), sqlstate=getattr(getattr(exc,'orig',None),'sqlstate',None))
                    if mode=='lock_release':
                        self.release_lock()
                        if change: change(self)
                raise
        monkeypatch.setattr(self.sup,'record_exit',exited)
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

    def note(self,event,**fields):
        self.events.append({'event':event,'at':time.monotonic(),**fields})

    def release_lock(self):
        if self.blocker:
            self.blocker.rollback();self.blocker.close();self.blocker=None
            self.note('lock_released')

    def state(self):
        with self.factory() as db:
            run=db.get(Run,self.admitted['id']);control=db.get(Control,1)
            return {'run':{k:getattr(run,k) for k in ('id','status','progress','generation','recoveries','error_code')},'actor':deepcopy(control.actor)}

    def start(self): self.monitor.start()

    def close(self):
        self.release_lock();self.monitor.close()
        for thread in self.renewals: thread.join(5)
        joined=all(not thread.is_alive() for thread in self.renewals)
        self.sup.lane.retire();self.engine.dispose();self.factory.kw['bind'].dispose()
        (self.path/'finalization-evidence.json').write_text(json.dumps({'mode':self.mode,'events':self.events,'monitor':self.monitor.evidence(),'runtime_finalization':list(getattr(self.sup,'finalization_events',[])),'pending':getattr(self.sup,'pending_evidence',lambda:None)(),'launches':self.launches,'finish_calls':self.finish_calls,'state':self.state(),'renewals_joined':joined},indent=2))
        assert joined


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('mode',['lock_release','lost_ack'])
def test_same_exit_persistence_recovers_without_reexecution(store,monkeypatch,tmp_path,mode):
    cell=Cell(store,monkeypatch,tmp_path,mode)
    try:
        cell.start()
        wait_for(lambda:cell.finished.is_set() or bool(cell.errors))
        assert cell.finished.is_set(), cell.monitor.evidence()
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
def test_pending_stop_and_scheduling_limit_do_not_start_more_work(store,monkeypatch,tmp_path,action):
    def change(cell):
        if action=='stop':cell.sup.stop.set()
        else:time.sleep(1.02)  # Real elapsed time, never substituted freshness.
    cell=Cell(store,monkeypatch,tmp_path,change=change)
    try:
        cell.start();wait_for(lambda:bool(cell.errors))
        attempts=[e for e in cell.sup.finalization_events if e['operation']=='exit_persistence' and e['event']=='attempt']
        assert len(attempts)==1 and len(cell.launches)==1 and cell.finish_calls==0
        assert cell.state()['run']['status']=='running'
        assert not cell.sup.allowed and cell.sup.pending is not None
    finally:cell.close()


@pytest.mark.parametrize('change',['actor','epoch','incarnation'])
@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_exit_projection_cas_rejects_changed_predecessor(store,monkeypatch,tmp_path,change):
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
    cell=Cell(store,monkeypatch,tmp_path,change=install)
    try:
        cell.start();wait_for(lambda:bool(cell.errors))
        assert cell.finish_calls==0 and len(cell.launches)==1
        assert cell.state()['run']['status']=='running'
        assert any(e['event']=='predecessor_changed_after_read' for e in cell.events)
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
