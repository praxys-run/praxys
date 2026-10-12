"""Finite account-mode contract, real projected Science and SDK evaluation shapes."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from statsig.feature_gate import FeatureGate
from statsig.evaluation_details import EvaluationDetails, EvaluationReason, DataSource

from api import activity_dfa as service, statsig_client
from api.routes import activity_dfa as routes
from api.auth import require_write_access, require_dfa_rights_access
from db.session import get_db
from db.models import (User, Activity, TermsAcceptanceReceipt, UserConnection,
    ActivityDFASyncGrant, ActivityDFASyncReceipt as Receipt, ActivityDFARun as Run)
from db import sync_writer
from tests.test_activity_dfa import store, confirmed, synthetic_fit
from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_dfa_finalization import Cell, wait_for


def gate(value=False, name='activity_dfa_automatic', reason=EvaluationReason.none, source=DataSource.BOOTSTRAP):
    return FeatureGate(value, name, 'synthetic-rule', 'userID',
        evaluation_details=EvaluationDetails(1, 1, source, reason))


@pytest.mark.parametrize('shape', ['bare_false','missing_details','missing_data','wrong_name','nonbool',
    'unrecognized','unsupported','error','uninitialized','unknown_source','raised'])
def test_strict_mode_rejects_sdk_default_and_unknown_shapes(monkeypatch, shape):
    monkeypatch.setattr(statsig_client, '_initialized', True)
    value = gate()
    if shape == 'bare_false': value = False
    elif shape in ('missing_details','missing_data'):
        value = FeatureGate(None if shape=='missing_data' else False, 'activity_dfa_automatic', '', '')
    elif shape == 'wrong_name': value = gate(name='another-gate')
    elif shape == 'nonbool': value = gate(value=0)
    elif shape in ('unrecognized','unsupported','error'):
        value = gate(reason=getattr(EvaluationReason,shape))
    elif shape == 'uninitialized': value = gate(source=DataSource.UNINITIALIZED)
    elif shape == 'unknown_source': value.evaluation_details.source='future-source'
    def sdk(user,name,log_exposure):
        assert log_exposure is False
        if shape == 'raised': raise RuntimeError('synthetic SDK failure')
        return value
    monkeypatch.setattr(statsig_client.statsig, 'get_feature_gate', sdk)
    assert statsig_client.recognized_gate('activity_dfa_automatic', object()) is None


@pytest.mark.parametrize('value',[True,False])
def test_recognized_boolean_is_explicit_and_generic_gate_unchanged(monkeypatch,value):
    monkeypatch.setattr(statsig_client, '_initialized', True)
    monkeypatch.setattr(statsig_client.statsig,'get_feature_gate',lambda *a,**k:gate(value))
    monkeypatch.setattr(statsig_client.statsig,'check_gate',lambda *a:False)
    assert statsig_client.recognized_gate('activity_dfa_automatic',object()) is value
    assert statsig_client.check_gate('other',object()) is False


def client(factory,owner):
    app=FastAPI();app.include_router(routes.router,prefix='/api')
    app.dependency_overrides[require_write_access]=lambda:owner
    app.dependency_overrides[require_dfa_rights_access]=lambda:owner
    def database():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=database
    return TestClient(app)


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('mode',[True,None])
def test_stale_client_manual_endpoints_and_idempotent_post_denied(both_origins,mode):
    factory,owner=both_origins
    proof,manual=confirmed(factory,owner)
    with factory() as db:
        catalog=service.catalog(db,owner,'123')
        preparation=db.query(Run).filter_by(user_id=owner,phase='prepare').one()
        confirmation={'run_id':preparation.id,'sensor_ref':proof['sensor_ref'],
            'evidence_digest':preparation.result['evidence_digest'],'statement_version':catalog['statement_version'],'confirmed':True}
        run=db.get(Run,manual['id']);run.status='failed';db.commit()
        before={k:getattr(run,k) for k in ('generation','status','admission_id','recoveries')}
    factory.dfa_modes[owner]=mode
    api=client(factory,owner);base='/api/activities/123/dfa-alpha1'
    submit={'input':{k:catalog['inputs'][0]['input'][k] for k in ('provider','snapshot_id','parse_id')},'catalog_revision':catalog['catalog_revision']}
    bodies=[('',submit),('',{**submit,'source_confirmation_id':proof['id']}),('/source-confirmations',confirmation),
        (f"/runs/{manual['id']}/retry",{'expected_generation':manual['generation']})]
    for suffix,body in bodies:
        for _ in range(2):
            response=api.post(base+suffix,json=body)
            assert response.status_code==(409 if mode is True else 503)
    with factory() as db:
        run=db.get(Run,manual['id']);assert {k:getattr(run,k) for k in before}==before
    metadata=api.get(base).json()
    assert metadata['manual_compute_allowed'] is False
    # Cancel/erase do not become compute-only permission endpoints.
    assert api.post(base+f"/runs/{manual['id']}/cancel").status_code==200
    assert api.delete(base).status_code==200


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_off_double_click_one_unit_real_compute_and_history_on(both_origins):
    factory,owner=both_origins;proof,manual=confirmed(factory,owner)
    api=client(factory,owner);base='/api/activities/123/dfa-alpha1';c=api.get(base).json()
    body={'input':{k:c['inputs'][0]['input'][k] for k in ('provider','snapshot_id','parse_id')},'catalog_revision':c['catalog_revision'],'source_confirmation_id':proof['id']}
    first=api.post(base,json=body);second=api.post(base,json=body)
    assert first.status_code==second.status_code==202
    assert first.json()['id']==second.json()['id']==manual['id']
    with factory() as db: claim=service.claim(db)
    service.execute(factory,*claim)
    factory.dfa_modes[owner]=True
    history=api.get(base+f"/runs/{manual['id']}").json()
    assert history['origin']=='manual' and history['freshness']=='current' and history['summary']['valid_windows']>0
    assert api.get(base).json()['manual_compute_allowed'] is False


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_unknown_defers_queued_known_flip_fences_without_resurrection(both_origins):
    factory,owner=both_origins;_,manual=confirmed(factory,owner);sup=factory.dfa_supervisor
    with factory() as db:
        before={k:getattr(db.get(Run,manual['id']),k) for k in ('status','generation','recoveries','lease_token')}
    factory.dfa_modes[owner]=None
    assert sup.acquire_job() is None
    with factory() as db: assert {k:getattr(db.get(Run,manual['id']),k) for k in before}==before
    factory.dfa_modes[owner]=True
    assert sup.acquire_job() is None
    with factory() as db:
        row=db.get(Run,manual['id']);assert row.status=='cancelled' and row.error_code=='mode_changed'
        assert row.recoveries==before['recoveries'] and row.generation==before['generation']+1
    factory.dfa_modes[owner]=False
    assert sup.acquire_job() is None


def second_owner(factory):
    from api.legal import TERMS_VERSION, TERMS_CONTENT_DIGEST
    owner=str(uuid4())
    with factory() as db:
        db.add(User(id=owner,email=owner+'@example.invalid',hashed_password='x',is_active=True,
            terms_version=TERMS_VERSION,terms_digest=TERMS_CONTENT_DIGEST));db.flush()
        db.add(TermsAcceptanceReceipt(user_id=owner,terms_version=TERMS_VERSION,terms_digest=TERMS_CONTENT_DIGEST,channel='web'))
        db.add(Activity(user_id=owner,activity_id='123',date=date.today(),source='garmin',activity_type='running'));db.flush()
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',synthetic_fit(transport=True),db)
        sync_writer.write_garmin_fit_parse(snapshot,db)
        service.storage.record_negative(owner,'account_generation_replaced','origin','automatic')
        connection=UserConnection(user_id=owner,platform='garmin',status='connected',dfa_account_generation=str(uuid4()))
        db.add(connection);db.flush()
        db.add(ActivityDFASyncGrant(user_id=owner,account_id='account',account_generation=connection.dfa_account_generation,
            connection_id=connection.id,action='connect_activity_sync'));db.commit()
    return owner


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('blocked',['active','unknown'])
def test_receipt_selection_skips_blocked_owner_before_rr_decode(both_origins,monkeypatch,blocked):
    factory,a=both_origins;b=second_owner(factory);sup=factory.dfa_supervisor
    if blocked == 'active':
        complete_unit(factory,a);sup.admit_completion()  # Genuine queued A authority.
        complete_unit(factory,a)
    else:
        complete_unit(factory,a,mode=None)  # Unknown successful sync stays pending.
    complete_unit(factory,b)
    from sync.rr_recording import RRRecordingReader
    actual=RRRecordingReader.iter_recording;reads=[]
    def recording(reader,ref):
        reads.append(ref.user_id);return actual(reader,ref)
    monkeypatch.setattr(RRRecordingReader,'iter_recording',recording)
    sup.admit_completion()
    assert reads==[b]
    with factory() as db:
        assert db.query(Run).filter_by(user_id=b,origin='automatic',status='queued').count()==1
        assert db.query(Receipt).filter_by(user_id=a,disposition='pending').count()==1


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_mixed_owner_modes_neutral_queue_skips_unknown(both_origins):
    factory,a=both_origins;b=second_owner(factory);_,manual=confirmed(factory,b)
    complete_unit(factory,a);sup=factory.dfa_supervisor;sup.admit_completion()
    assert factory.dfa_modes[a] is True and factory.dfa_modes[b] is False
    with factory() as db: assert service.catalog(db,b,'123')['manual_compute_allowed'] is True
    factory.dfa_modes[b]=None
    job=sup.acquire_job();assert job['owner']==a and job['origin']=='automatic'
    with factory() as db: assert db.get(Run,manual['id']).status=='queued'
    # This is acquisition evidence, not a second physical launch.


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('mode',[True,None])
def test_mode_flip_during_lost_ack_finalization_no_stale_publication(both_origins,monkeypatch,tmp_path,mode):
    factory,owner=both_origins
    from sqlalchemy.exc import OperationalError
    cell=Cell(both_origins,monkeypatch,tmp_path,'lost_ack')
    actual_exit=cell.sup.record_exit
    changed=[]
    def exit_then_mode_change():
        try: return actual_exit()
        except OperationalError:
            assert cell.sup.pending is not None and cell.sup.lane.actor()['state']=='idle'
            factory.dfa_modes[owner]=mode
            changed.append(True);cell.note('mode_changed_after_actual_lost_ack',mode=mode)
            raise
    monkeypatch.setattr(cell.sup,'record_exit',exit_then_mode_change)
    try:
        cell.start();wait_for(lambda:cell.finished.is_set() or bool(cell.errors))
        assert cell.finished.is_set() and not cell.errors and changed
        with factory() as db:
            row=db.get(Run,cell.admitted['id']);assert row.status=='failed' and row.result is None and row.recoveries==0
        assert len(cell.launches)==1 and cell.finish_calls==1
        assert any(e['operation']=='exit_persistence' and e['event']=='retry' for e in cell.sup.finalization_events)
    finally:cell.close()

@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_mode_flip_at_admission_mutation_rolls_back_real_retry(both_origins,monkeypatch):
    from api import dfa_supervisor
    from fastapi import HTTPException
    factory,owner=both_origins;_,manual=confirmed(factory,owner)
    with factory() as db:
        row=db.get(Run,manual['id']);row.status='failed';db.commit()
        before={k:getattr(row,k) for k in ('generation','status','admission_id','recoveries')}
    actual=dfa_supervisor.manual_admission;observed=[]
    def admission(db):
        result=actual(db);factory.dfa_modes[owner]=True;observed.append(True);return result
    monkeypatch.setattr(dfa_supervisor,'manual_admission',admission)
    with factory() as db,pytest.raises(HTTPException) as failure:
        service.change_run(db,owner,'123',manual['id'],'retry',manual['generation'])
    assert failure.value.status_code==409 and observed
    with factory() as db: assert {k:getattr(db.get(Run,manual['id']),k) for k in before}==before


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_mode_flip_after_actual_raw_read_refuses_physical_start(both_origins,monkeypatch):
    import queue
    from sync.rr_recording import RRRecordingReader
    factory,owner=both_origins;_,manual=confirmed(factory,owner);sup=factory.dfa_supervisor
    job=sup.acquire_job();assert job
    previous=deepcopy(sup.lane.actor());actual=RRRecordingReader.raw;reads=[]
    def raw(reader,ref):
        value=actual(reader,ref);reads.append(True);factory.dfa_modes[owner]=True;return value
    monkeypatch.setattr(RRRecordingReader,'raw',raw)
    outputs=queue.Queue();sup.work(job,outputs);status,value=outputs.get(timeout=2)
    assert reads and status=='failed_before_spawn' and value=='authority_changed'
    assert sup.lane.actor()==previous
    sup.finish(job,status,value)
    with factory() as db: assert db.get(Run,manual['id']).result is None


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_running_mode_switch_exit_ack_finish_before_automatic_launch(both_origins,monkeypatch,tmp_path):
    import io,os,select,subprocess,sys,threading,time
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from tests.dfa_capacity_worker import CapacityWorker
    from tests.dfa_boundary_evidence import RenewalDecision, safe_binding
    from api import dfa_rights
    from api.dfa_supervisor import SAFE_FAILURES
    factory,owner=both_origins;_,manual=confirmed(factory,owner);sup=factory.dfa_supervisor
    url=factory.kw['bind'].url
    args={'timeout':.1} if url.get_backend_name()=='sqlite' else {'connect_timeout':1,'options':'-c statement_timeout=200 -c lock_timeout=200'}
    engine=create_engine(url,pool_size=2,max_overflow=0,pool_timeout=.1,connect_args=args)
    sup.controls=sessionmaker(bind=engine);sup.allowed=False;sup.permission_until=0.
    read_fd,write_fd=os.pipe();actual_popen=subprocess.Popen
    code=f'''import io,json,os,signal,sys,time
raw=sys.stdin.buffer.readline(90*1024*1024+1)
payload=json.loads(raw)
if payload['origin']=='manual':
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    os.write({write_fd},b'M')
    while True:time.sleep(.01)
else:
    sys.stdin=io.TextIOWrapper(io.BytesIO(raw))
    from api.dfa_worker import main
    main()
'''
    def child(command,**kw):
        if command[-2:]==['-m','api.dfa_worker']:
            command=[sys.executable,'-E','-B','-c',code];kw['pass_fds']=(*kw.get('pass_fds',()),write_fd)
        return actual_popen(command,**kw)
    monkeypatch.setattr(subprocess,'Popen',child)
    events=[];launches=[];completed=threading.Event();errors=[];validations=[];finishes=[];modes=[];exit_receipts=[]
    renewal=RenewalDecision(sup,monkeypatch)
    actual_acquire=sup.acquire_job;start_barrier_used=False
    def acquire():
        nonlocal start_barrier_used
        job=actual_acquire()
        if job and job['origin']=='manual' and not start_barrier_used:
            start_barrier_used=True
            events.append(('acquisition_commit_return',time.monotonic()))
            # acquire_job has exited its owner transaction. Both SQLite and PG
            # can now publish a genuine control renewal without a writer cycle.
            renewal.arm();renewal.wait()
        return job
    monkeypatch.setattr(sup,'acquire_job',acquire)
    actual_source_current=service._current
    def source_current(db,run):
        before=time.monotonic();result=actual_source_current(db,run)
        validations.append({'source_call':'_current','before':before,'after':time.monotonic(),
            'job':safe_binding({'id':run.id,'generation':run.generation,'origin':run.origin,'phase':run.phase}),
            'current':result,'thread':threading.current_thread().name})
        return result
    monkeypatch.setattr(service,'_current',source_current)
    actual_current=dfa_rights.execution_current
    def current(db,run):
        before=time.monotonic();result=actual_current(db,run)
        validations.append({'source_call':'execution_current','before':before,'after':time.monotonic(),
            'job':safe_binding({'id':run.id,'generation':run.generation,'origin':run.origin,'phase':run.phase}),
            'current':result,'thread':threading.current_thread().name})
        return result
    monkeypatch.setattr(dfa_rights,'execution_current',current)
    actual_mode=dfa_rights.account_mode
    def mode(db,owner):
        value=actual_mode(db,owner);modes.append({'at':time.monotonic(),'mode':value,
                                               'thread':threading.current_thread().name});return value
    monkeypatch.setattr(dfa_rights,'account_mode',mode)
    actual_launch=sup.lane.launch
    def launch(*a,**kw):
        if launches: assert sup.pending is None and sup.active['origin']=='automatic'
        result=actual_launch(*a,**kw);launches.append(deepcopy(result[0]));events.append(('launch',time.monotonic()));return result
    monkeypatch.setattr(sup.lane,'launch',launch)
    actual_exit=sup.record_exit
    def exited():
        result=actual_exit();events.append(('exit_ack',time.monotonic()))
        exit_receipts.append({'kind':result['kind'],'at':result['at'],
            'observed_at':result['observed_at'],'actor':safe_binding(sup.lane.actor())})
        return result
    monkeypatch.setattr(sup,'record_exit',exited)
    actual_finish=sup.finish
    def finish(job,status,value):
        with sup.lock:
            decision=deepcopy(sup.permission_decision);allowed=sup.allowed;deadline=sup.permission_until
        pending=sup.pending
        # Snapshot before finish/phase cleanup; never log output payloads.
        finishes.append({'at':time.monotonic(),'job':safe_binding(job),'status':status,
            'reason':value if isinstance(value,str) and value in SAFE_FAILURES|{'mode_changed','mode_unavailable'} else None,
            'actor':safe_binding(sup.lane.actor()),'allowed':allowed,'permission_until':deadline,
            'decision':None if decision is None else {'at':decision['at'],'reason':decision['reason'],
                'phase':decision['phase'],'job':safe_binding(decision['job']),
                'actor':safe_binding(decision['actor'])},
            'cancelled':pending.cancellation.is_set() if pending else None,
            'pending_status':pending.status if pending else None,
            'last_mode':deepcopy(modes[-1]) if modes else None})
        actual_finish(job,status,value);events.append(('finish_'+job['origin'],time.monotonic()))
        if job['origin']=='automatic':completed.set()
    monkeypatch.setattr(sup,'finish',finish)
    monitor=CapacityWorker(sup,errors);monitor.start()
    try:
        assert select.select([read_fd],[],[],5)[0],monitor.evidence()
        assert os.read(read_fd,1)==b'M'
        events.append(('manual_payload_handshake',time.monotonic()))
        assert len(launches)==1 and launches[0]['state']=='occupied'
        complete_unit(factory,owner)  # Actual new sync; ON, no manual bypass.
        assert completed.wait(15),monitor.evidence()
        wait_for(lambda:sup.pending is None and sup.active is None)
        with factory() as db:
            old=db.get(Run,manual['id']);auto=db.query(Run).filter_by(user_id=owner,origin='automatic').one()
            assert old.status=='failed' and old.result is None and old.recoveries==0
            assert auto.status=='complete' and auto.result['summary']['valid_windows']>0
        assert len(launches)==2 and not errors
        first_finish=next(at for event,at in events if event=='finish_manual')
        manual_actor=safe_binding(launches[0])['actor']
        exact_exit=next(receipt for receipt in exit_receipts if receipt['actor']['actor']==manual_actor)
        assert exact_exit['actor']['binding']==safe_binding(launches[0])['binding']
        assert launches[0]['launch_at']<=exact_exit['actor']['exit_observed_at']<=exact_exit['at']<=first_finish
        assert next(value for value in finishes if value['job']['origin']=='manual')['actor']['actor']==manual_actor
        assert first_finish<=launches[1]['launch_at'] and launches[1]['launch_at']>=launches[0]['launch_at']
    finally:
        monitor.close();os.close(read_fd);os.close(write_fd);engine.dispose()
        (tmp_path/'mode-switch-evidence.json').write_text(__import__('json').dumps({
            'events':events,'launches':[safe_binding(actor) for actor in launches],
            'monitor':monitor.evidence(),'finishes':finishes,'validations':validations,
            'mode_evaluations':modes,'renewal_boundary':renewal.events,
            'exit_receipts':exit_receipts},indent=2))


def test_actual_installed_sdk_invalid_input_false_is_unknown(monkeypatch):
    from statsig.statsig_server import StatsigServer
    # Execute the installed SDK's actual invalid-input branch without initialize,
    # network or credentials; no duplicate implementation of gate evaluation.
    sdk=StatsigServer.__new__(StatsigServer)
    sdk._verify_inputs=lambda *a:False
    sdk._options=SimpleNamespace(evaluation_callback=None)
    sdk._errorBoundary=SimpleNamespace(capture=lambda name,task,fallback,metadata:task())
    assert sdk.get_feature_gate(object(),'activity_dfa_automatic',False) is False
    monkeypatch.setattr(statsig_client,'_initialized',True)
    monkeypatch.setattr(statsig_client.statsig,'get_feature_gate',sdk.get_feature_gate)
    assert statsig_client.recognized_gate('activity_dfa_automatic',object()) is None

@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_unknown_provenance_hides_automatic_history_without_generic_gate_change(both_origins,monkeypatch):
    factory,owner=both_origins;complete_unit(factory,owner);sup=factory.dfa_supervisor;sup.admit_completion()
    with factory() as db: claim=service.claim(db)
    service.execute(factory,*claim)
    with factory() as db:
        row=db.query(Run).filter_by(origin='automatic').one();run_id=row.id
        assert service.read_run(db,owner,'123',run_id,0,120)['summary']['valid_windows']>0
    monkeypatch.setattr(statsig_client.statsig,'get_feature_gate',lambda *a,**k:gate(True,reason=EvaluationReason.unsupported))
    from statsig import StatsigUser
    assert statsig_client.check_gate('activity_dfa_automatic',StatsigUser(user_id=owner)) is True
    with factory() as db:
        view=service.read_run(db,owner,'123',run_id,0,120)
        assert view['freshness']=='stale' and 'summary' not in view and 'windows' not in view and view['result_revision'] is None


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
def test_owner_change_after_queue_snapshot_cannot_mutate_another_owner(both_origins,monkeypatch):
    from contextlib import contextmanager
    factory,a=both_origins;_,manual=confirmed(factory,a);b=second_owner(factory)
    actual=service.owner_write;changed=[]
    @contextmanager
    def owner_write(db,owner):
        if not changed:
            with factory() as external:
                external.get(Run,manual['id']).user_id=b;external.commit()
            changed.append(True)
        with actual(db,owner):yield
    monkeypatch.setattr(service,'owner_write',owner_write)
    assert factory.dfa_supervisor.acquire_job() is None
    with factory() as db:
        row=db.get(Run,manual['id']);assert row.user_id==b and row.status=='queued' and row.generation==manual['generation']
