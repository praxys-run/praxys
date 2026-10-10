"""Behavior regressions for independent b8411ef source findings. Synthetic only."""
import json,os,queue,subprocess,sys,threading,time
from pathlib import Path
from datetime import datetime,timedelta
import pytest
from sqlalchemy import create_engine,event,text
from sqlalchemy.orm import sessionmaker
from api import activity_dfa as service, dfa_rights
from api.dfa_supervisor import Supervisor,retire_before_initialization
from api.dfa_physical import Lane,group_members,PhysicalUnavailable
from db.models import ActivityDFARun as Run,ActivityDFAControl as Control,ActivityDFAOriginGrant as Grant,TermsAcceptanceReceipt
from tests.test_activity_dfa import store,confirmed
from tests.test_dfa_origins import both_origins,complete_unit
from tests.dfa_supervisor_harness import IDENTITY


def second_owner(factory):
    from uuid import uuid4
    from datetime import date
    from db.models import User,Activity
    from db import sync_writer
    from api.legal import TERMS_VERSION,TERMS_CONTENT_DIGEST
    from tests.test_activity_dfa import synthetic_fit
    owner=str(uuid4())
    with factory() as db:
        db.add(User(id=owner,email=owner+'@example.invalid',hashed_password='x',is_active=True,
            terms_version=TERMS_VERSION,terms_digest=TERMS_CONTENT_DIGEST));db.flush()
        db.add(TermsAcceptanceReceipt(user_id=owner,terms_version=TERMS_VERSION,terms_digest=TERMS_CONTENT_DIGEST,channel='web'))
        db.add(Activity(user_id=owner,activity_id='123',date=date.today(),source='garmin',activity_type='running'));db.flush()
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',synthetic_fit(),db)
        sync_writer.write_garmin_fit_parse(snapshot,db);db.commit()
    return owner


def test_invalid_oldest_run_does_not_starve_eligible_peer(store):
    factory,owner=store
    _,first=confirmed(factory,owner)
    with factory() as db:db.get(Run,first['id']).status='complete';db.commit()
    peer=second_owner(factory);_,later=confirmed(factory,peer)
    with factory() as db:
        old=db.get(Run,first['id']);old.status='queued';old.grant_id=None;old.created_at=datetime.utcnow()-timedelta(days=1);db.commit()
    job=factory.dfa_supervisor.acquire_job()
    assert job['id']==later['id']
    with factory() as db:
        invalid=db.get(Run,first['id']);assert invalid.status=='failed' and invalid.freshness=='stale'


def test_temporary_channel_stop_defers_oldest_without_starving_peer(store,monkeypatch):
    from api.channel_processing_authority import reconcile_channel_processing_authority
    factory,owner=store
    monkeypatch.setenv('PRAXYS_DISABLE_MINIAPP_PROCESSING','false')
    with factory() as db:
        db.query(TermsAcceptanceReceipt).filter_by(user_id=owner).one().channel='wechat-miniapp'
        db.commit();reconcile_channel_processing_authority(db);db.commit()
    _,first=confirmed(factory,owner)
    with factory() as db:db.get(Run,first['id']).status='complete';db.commit()
    peer=second_owner(factory);_,later=confirmed(factory,peer)
    monkeypatch.setenv('PRAXYS_DISABLE_MINIAPP_PROCESSING','true')
    with factory() as db:
        reconcile_channel_processing_authority(db)
        old=db.get(Run,first['id']);old.status='queued';old.created_at=datetime.utcnow()-timedelta(days=1);db.commit()
    assert factory.dfa_supervisor.acquire_job()['id']==later['id']
    with factory() as db:assert db.get(Run,first['id']).status=='queued'


def test_proven_failure_before_first_spawn_keeps_supervisor_alive(store,monkeypatch):
    factory,owner=store
    _,manual=confirmed(factory,owner)
    supervisor=factory.dfa_supervisor
    # Remove only the completed fixture preparation journal, never a live actor.
    assert supervisor.lane.actor()['state']=='idle'
    supervisor.lane.journal.unlink()
    with factory() as db:db.get(Control,1).actor=None;db.commit()
    from sync.rr_recording import RRRecordingReader
    monkeypatch.setattr(RRRecordingReader,'raw',lambda *args:(_ for _ in ()).throw(ValueError('input_integrity_failed')))
    errors=[]
    def run():
        try:supervisor.run()
        except Exception as exc:errors.append(exc)
    worker=threading.Thread(target=run);worker.start()
    try:
        until=time.monotonic()+5
        while time.monotonic()<until:
            with factory() as db:status=db.get(Run,manual['id']).status
            if status=='failed':break
            time.sleep(.01)
        assert status=='failed' and worker.is_alive() and not errors
        assert supervisor.lane.actor() is None
    finally:supervisor.stop.set();worker.join(5)


@pytest.mark.parametrize('cold_stage',['database','statsig','coordinator'])
def test_restart_retires_inherited_child_before_blocked_initialization(tmp_path,monkeypatch,cold_stage):
    from api import dfa_supervisor as module
    directory=tmp_path/'lane'
    adopter=Lane(directory,IDENTITY);adopter.close()
    child_code='''import json,os,sys
from pathlib import Path
from api.dfa_physical import Lane
import subprocess
real=subprocess.Popen
subprocess.Popen=lambda command,**kwargs:real([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'],**kwargs)
lane=Lane(Path(sys.argv[1]),json.loads(sys.argv[2]));lane.authorize_recovery()
lane.launch({'epoch':'1','generation':1,'input':'a'*64},authorized=True)
os._exit(0)
'''
    subprocess.run([sys.executable,'-c',child_code,str(directory),json.dumps(IDENTITY)],check=True)
    reader=Lane(directory,IDENTITY);pid=reader.actor()['identity']['pid'];reader.close()
    assert group_members(pid)
    monkeypatch.setenv('PRAXYS_DFA_SUPERVISOR_ENABLED','true')
    import signal
    monkeypatch.setattr(signal,'signal',lambda *args:None)
    monkeypatch.setattr(module,'incarnation',lambda:IDENTITY)
    original=module.retire_before_initialization
    monkeypatch.setattr(module,'retire_before_initialization',lambda identity:original(identity,directory))
    from db import session
    entered=threading.Event();release=threading.Event();errors=[]
    def blocked_init():entered.set();release.wait(5);raise RuntimeError('synthetic_cold_init')
    if cold_stage in {'database','coordinator'}:
        monkeypatch.setattr(session,'init_db',blocked_init)
    else:
        monkeypatch.setattr(session,'init_db',lambda:None)
        from api import statsig_client
        async def blocked_sdk():
            import asyncio
            entered.set();await asyncio.to_thread(release.wait,5)
            raise RuntimeError('synthetic_cold_init')
        monkeypatch.setattr(statsig_client,'init_statsig',blocked_sdk)
    def run():
        try:
            if cold_stage=='coordinator':
                from api.runtime_startup import main
                main()
            else:module.main()
        except RuntimeError as exc:errors.append(str(exc))
    thread=threading.Thread(target=run);thread.start()
    try:
        assert entered.wait(3)
        assert not group_members(pid), 'Cold initialization must not delay orphan retirement'
    finally:release.set();thread.join(5)
    assert errors==['synthetic_cold_init']


def automatic_job(factory,owner):
    complete_unit(factory,owner)
    supervisor=factory.dfa_supervisor;supervisor.admit_completion()
    return supervisor,supervisor.acquire_job()


def test_permanent_automatic_failure_is_terminal_not_preemption(both_origins):
    factory,owner=both_origins;supervisor,job=automatic_job(factory,owner)
    supervisor.finish(job,'failed','timer_invalid')
    with factory() as db:
        row=db.get(Run,job['id']);assert row.status=='failed' and row.error_code=='timer_invalid'
    assert supervisor.acquire_job() is None


def test_transient_automatic_retry_is_bounded_and_preemption_separate(both_origins):
    factory,owner=both_origins;supervisor,job=automatic_job(factory,owner)
    supervisor.finish(job,'preempted',None)
    job=supervisor.acquire_job()
    with factory() as db:assert db.get(Run,job['id']).recoveries==0
    supervisor.finish(job,'failed','execution_unavailable')
    job=supervisor.acquire_job()
    supervisor.finish(job,'failed','execution_unavailable')
    with factory() as db:
        row=db.get(Run,job['id']);assert row.status=='failed' and row.recoveries==1


@pytest.mark.parametrize('store',['postgresql'],indirect=True)
def test_postgresql_concurrent_acquisition_and_revocation_before_publication(store):
    factory,owner=store;proof,manual=confirmed(factory,owner)
    supervisor=factory.dfa_supervisor;barrier=threading.Barrier(2);jobs=[];errors=[]
    def acquire():
        try:barrier.wait();jobs.append(supervisor.acquire_job())
        except Exception as exc:errors.append(exc)
    workers=[threading.Thread(target=acquire) for _ in range(2)]
    for worker in workers:worker.start()
    for worker in workers:worker.join(5)
    assert not errors and sum(job is not None for job in jobs)==1
    job=next(job for job in jobs if job);outputs=queue.Queue();supervisor.work(job,outputs)
    supervisor.lane.retire();supervisor.record_exit();status,value=outputs.get()
    entered=threading.Event();release=threading.Event();done=threading.Event()
    def revoke():
        with factory() as db:
            with service.owner_write(db,owner):
                service.storage.record_negative(owner,'withdrawn','confirmation',proof['id'])
                db.delete(db.get(service.Confirmation,proof['id']))
                entered.set();release.wait(5);db.commit()
    def publish():
        supervisor.finish(job,status,value);done.set()
    revoked=threading.Thread(target=revoke);revoked.start();assert entered.wait(3)
    publisher=threading.Thread(target=publish);publisher.start();assert not done.wait(.15)
    release.set();revoked.join(5);publisher.join(5)
    with factory() as db:
        row=db.get(Run,manual['id']);assert row is None or row.status=='failed' and row.result is None


@pytest.mark.parametrize('store',['postgresql'],indirect=True)
def test_actual_pg_renewal_preserves_200ms_source_and_pool_budget(store):
    factory,owner=store;_,manual=confirmed(factory,owner)
    supervisor=factory.dfa_supervisor;job=supervisor.acquire_job();supervisor.active=job
    engine=create_engine(factory.kw['bind'].url,pool_size=1,max_overflow=0,pool_timeout=.1,
        connect_args={'connect_timeout':1,'options':'-c statement_timeout=200 -c lock_timeout=200'})
    supervisor.controls=sessionmaker(bind=engine)
    observed=[]
    @event.listens_for(engine,'before_cursor_execute')
    def observe(connection,cursor,statement,parameters,context,executemany):
        if 'SET LOCAL statement_timeout' in statement:observed.append(statement)
    thread=threading.Thread(target=supervisor.renew);thread.start()
    try:
        until=time.monotonic()+3
        while supervisor.control_observation['state']!='ready' and time.monotonic()<until:time.sleep(.01)
        assert supervisor.control_observation['state']=='ready'
        with factory.kw['bind'].connect() as blocker:
            transaction=blocker.begin();blocker.execute(text('LOCK TABLE garmin_fit_snapshots IN ACCESS EXCLUSIVE MODE'))
            until=time.monotonic()+2
            while supervisor.control_observation['state'] not in ('OperationalError','InternalError') and time.monotonic()<until:time.sleep(.01)
            assert not supervisor.allowed
            assert supervisor.control_observation['duration_seconds']<.7
            supervisor.stop.set();thread.join(1)
            assert not thread.is_alive(), 'Source query must release reserved connection within its tight deadline'
            start=time.monotonic()
            with engine.connect() as check:assert check.execute(text('SELECT 1')).scalar()==1
            assert time.monotonic()-start<.4
            transaction.rollback()
        assert observed and all('200ms' in value for value in observed),observed
    finally:supervisor.stop.set();thread.join(2);engine.dispose()


def test_blob_negative_cas_conflict_reloads_and_retains_both_writers(store,monkeypatch):
    from types import SimpleNamespace
    from azure.core.exceptions import ResourceNotFoundError,ResourceModifiedError
    from api import activity_dfa_storage as storage
    factory,owner=store
    state={'schema':1,'sequence':1,'deleted':False,'events':{},'epoch':'synthetic-epoch'}
    version=1;attempts=[];conflicted=False
    class Blob:
        def get_blob_properties(self):return SimpleNamespace(etag=str(version))
        def download_blob(self):return SimpleNamespace(readall=lambda:json.dumps(state).encode())
        def upload_blob(self,payload,**kwargs):
            nonlocal state,version,conflicted
            attempts.append(kwargs.get('etag'))
            if not conflicted:
                conflicted=True;state['sequence']+=1
                state['events']['other-host']={'sequence':2,'operation':'withdrawn','scope':'origin','target':'automatic'}
                version+=1
                raise ResourceModifiedError('synthetic concurrent writer')
            assert kwargs['etag']==str(version)
            state=json.loads(payload);version+=1
    blob=Blob()
    monkeypatch.setattr(storage.feedback_storage,'private_blob_enabled',lambda:True)
    monkeypatch.setattr(storage.feedback_storage,'private_container_client',lambda:SimpleNamespace(get_blob_client=lambda key:blob))
    result=storage.record_negative(owner,'cancel','run','synthetic-run')
    assert attempts==['1','2'] and result['sequence']==3
    assert {event['operation'] for event in result['events'].values()}=={'withdrawn','cancel'}


@pytest.mark.parametrize('fail_after_replace',[False,True])
def test_negative_fsync_failure_never_acknowledges_sql_erasure(store,monkeypatch,fail_after_replace):
    from api import activity_dfa_storage as storage
    factory,owner=store;proof,manual=confirmed(factory,owner)
    original=storage.os.fsync;count=0
    def fault(fd):
        nonlocal count
        count+=1
        if count==(2 if fail_after_replace else 1):raise OSError('synthetic fsync failure')
        original(fd)
    monkeypatch.setattr(storage.os,'fsync',fault)
    with factory() as db:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:service.erase(db,owner,'123')
        assert error.value.status_code==503 and error.value.detail=='DFA_DELETE_STORAGE_UNAVAILABLE'
        db.rollback()
        assert db.get(Run,manual['id']) is not None and db.get(service.Confirmation,proof['id']) is not None
    if fail_after_replace:
        with factory() as db:assert not service._current(db,db.get(Run,manual['id']))


def test_recovery_reconciles_proven_preload_but_blocks_lost_launch_intent(store):
    factory,owner=store;_,manual=confirmed(factory,owner);supervisor=factory.dfa_supervisor
    supervisor.lane.journal.unlink()
    with factory() as db:db.get(Control,1).actor=None;db.commit()
    job=supervisor.acquire_job();supervisor.reconcile_recovery()
    with factory() as db:
        row=db.get(Run,manual['id']);assert row.status=='failed' and row.error_code=='restart_interrupted'
        row.status='running';row.progress='launching';db.commit()
    with pytest.raises(PhysicalUnavailable,match='missing_launch_journal'):supervisor.reconcile_recovery()


def test_real_worker_reports_invalid_timer_as_allowlisted_permanent_failure():
    import struct,base64
    from tests.test_activity_dfa import Fit
    fit=Fit();fit.definition(0,23,[(0,1,2),(2,2,132),(4,2,132),(25,1,0),(1,1,2)])
    fit.data(0,struct.pack('<BHHBB',1,1,4130,1,120))
    fit.definition(1,18,[(5,1,0)]);fit.data(1,b'\1')
    fit.definition(2,20,[(253,4,134)]);fit.data(2,struct.pack('<I',1000000))
    fit.definition(3,78,[(0,4,132)]);fit.data(3,struct.pack('<HH',500,500))
    payload={'binding':{'epoch':'1','generation':1,'input':'a'*64},'actor_token':'synthetic-token','phase':'compute',
        'raw_fit':base64.b64encode(fit.finish()).decode(),'recording_ref':{'snapshot_id':'synthetic'},'manual_proof':None,'origin':'automatic'}
    result=subprocess.run([sys.executable,'-E','-B','-m','api.dfa_worker'],input=(json.dumps(payload)+'\n').encode(),capture_output=True,check=True)
    value=json.loads(result.stdout);assert value['error']=='timer_invalid' and 'result' not in value

@pytest.mark.parametrize('enabled,raw', [('false','malformed'),('true','malformed'),('false','stale'),('true','stale'),('false',None)])
def test_startup_coordinator_invalid_candidate_keeps_api_only(tmp_path,monkeypatch,enabled,raw):
    from api import runtime_startup as startup,dfa_supervisor
    from db import session
    from contextlib import nullcontext
    monkeypatch.setenv('PRAXYS_DFA_SUPERVISOR_ENABLED',enabled)
    if raw is None:monkeypatch.delenv('PRAXYS_DFA_INCARNATION',raising=False)
    elif raw=='stale':monkeypatch.setenv('PRAXYS_DFA_INCARNATION',json.dumps({**IDENTITY,'incarnation':'11111111-1111-1111-1111-111111111111',
        'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'namespace':os.readlink('/proc/self/ns/pid')+'|'+os.readlink('/proc/self/ns/mnt')}))
    else:monkeypatch.setenv('PRAXYS_DFA_INCARNATION',raw)
    monkeypatch.setattr(dfa_supervisor.subprocess if hasattr(dfa_supervisor,'subprocess') else startup.subprocess,'check_output',lambda *args,**kw:'current-source')
    original=dfa_supervisor.retire_before_initialization
    monkeypatch.setattr(dfa_supervisor,'retire_before_initialization',lambda identity:original(identity,tmp_path/'lane'))
    events=[]
    monkeypatch.setattr(session,'init_db',lambda:events.append('db'))
    monkeypatch.setattr(session,'dispose_engines',lambda:None)
    class DB:
        def query(self,*args):return self
        def filter_by(self,**kw):return self
        def with_for_update(self):return self
        def first(self):return None
    monkeypatch.setattr(session,'SessionLocal',lambda:nullcontext(DB()))
    class Child:
        returncode=0
        def poll(self):return 0
        def wait(self,**kw):return 0
    monkeypatch.setattr(startup.subprocess,'Popen',lambda args,**kw:(events.append(args) or Child()))
    monkeypatch.setattr(startup.signal,'signal',lambda *args:None)
    assert startup.main()==0
    commands=[x for x in events if isinstance(x,list)]
    assert len(commands)==1 and 'gunicorn' in commands[0]
    assert events[0]=='db'

@pytest.mark.parametrize('receipt',['missing','mismatched'])
@pytest.mark.parametrize('state',['launching','running'])
def test_recovery_without_exact_receipt_never_signals_or_launches(tmp_path,monkeypatch,receipt,state):
    from api import runtime_startup as startup,dfa_supervisor
    directory=tmp_path/'lane'
    lane=Lane(directory,IDENTITY)
    lane.record({'incarnation':IDENTITY,'state':state,'actor_token':'synthetic',
        'identity':{'pid':99999999,'pgid':99999999,'start_ticks':1}})
    if receipt=='mismatched':
        other=Lane(directory,{**IDENTITY,'epoch':IDENTITY['epoch']+1})
        other.authorize_recovery();other.close()
    lane.close()
    signals=[];launches=[]
    monkeypatch.setattr(os,'killpg',lambda *args:signals.append(args))
    monkeypatch.setattr(startup.subprocess,'Popen',lambda *args,**kw:launches.append(args))
    with pytest.raises(PhysicalUnavailable,match='recovery_not_authorized'):
        retire_before_initialization(IDENTITY,directory)
    monkeypatch.setattr(dfa_supervisor,'incarnation',lambda:IDENTITY)
    original=dfa_supervisor.retire_before_initialization
    monkeypatch.setattr(dfa_supervisor,'retire_before_initialization',lambda identity:original(identity,directory))
    assert startup.reconcile_candidate() is False
    assert signals==[] and launches==[]
    check=Lane(directory,IDENTITY)
    assert check.actor()['state']==state
    check.close()
