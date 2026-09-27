"""Synthetic DFA contracts: raw protocol, independent math, QC and owner lifecycle."""
from datetime import date, datetime, timedelta
import hashlib
import json
import struct
from uuid import uuid4

import numpy as np
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis import activity_dfa as core
from sync.rr_recording import decode, RRRecordingReader, RecordingRef
from api import activity_dfa as service, activity_dfa_storage as storage
from db.models import Base, User, Activity, ActivityDFARun as Run, ActivityDFAConfirmation as Confirmation
from db import sync_writer


class Fit:
    def __init__(self):
        self.body = bytearray()

    def definition(self, local, message, fields):
        self.body.extend(struct.pack('<BBBHB', 0x40 | local, 0, 0, message, len(fields)))
        for field in fields:
            self.body.extend(bytes(field))

    def data(self, local, raw):
        self.body.append(local)
        self.body.extend(raw)

    def finish(self):
        from fitdecode.utils import compute_crc
        raw = struct.pack('<BBHI4s', 12, 0x20, 2180, len(self.body), b'.FIT') + self.body
        return raw + struct.pack('<H', compute_crc(raw))


def synthetic_fit(values=None, product=4130, sport=1, with_rr=True):
    rr = values if values is not None else np.random.default_rng(18).integers(480, 521, 650).tolist()
    fit = Fit()
    fit.definition(0, 23, [(0,1,2),(2,2,132),(4,2,132)])
    fit.data(0, struct.pack('<BHH', 1, 1, product))
    fit.definition(1, 21, [(253,4,134),(0,1,0),(1,1,0),(4,1,2)])
    fit.definition(2, 20, [(253,4,134)])
    fit.definition(3, 78, [(0,4,132)])
    fit.definition(4, 18, [(5,1,0)])
    start = 1_000_000
    fit.data(1, struct.pack('<IBBB', start, 0, 0, 0))
    fit.data(2, struct.pack('<I', start))
    elapsed = 0
    for value in rr:
        if with_rr:
            fit.data(3, struct.pack('<HH', value, 65535))
        elapsed += value
        fit.data(2, struct.pack('<I', start + elapsed // 1000))
    fit.data(1, struct.pack('<IBBB', start+(elapsed+999)//1000, 0, 4, 0))
    fit.data(4, bytes([sport]))
    return fit.finish()


def reference(rr):
    y = np.cumsum(np.asarray(rr, dtype=float)-np.mean(rr))
    fs = []
    for n in range(4,17):
        residuals = []
        x = np.column_stack((np.ones(n), np.arange(n)))
        for start in [j*n for j in range(len(y)//n)] + [len(y)-(j+1)*n for j in range(len(y)//n)]:
            box = y[start:start+n]
            residuals.extend((box-x@np.linalg.lstsq(x, box, rcond=None)[0])**2)
        fs.append(np.sqrt(np.mean(residuals)))
    return np.polyfit(np.log(np.arange(4,17)), np.log(fs), 1)[0]


@pytest.mark.parametrize('length', [200,201,240,599,1000])
@pytest.mark.parametrize('integrated', [False,True])
def test_independent_numeric_reference(length, integrated):
    values = np.random.default_rng(length).normal(size=length)
    if integrated:
        values = np.cumsum(values)
    for rr in (values, values[::-1], values+500, values*1000):
        alpha, r2 = core.dfa_alpha1(rr)
        assert abs(alpha-reference(rr)) <= 1e-9
        assert r2 is None or 0 <= r2 <= 1
    assert core.dfa_alpha1(values)[0] == pytest.approx(core.dfa_alpha1(values*1000+500)[0], abs=1e-9)
    with pytest.raises(core.DFAError, match='numerical_invalid'):
        core.dfa_alpha1([500]*length)


def test_raw_native_garmin_subfield_no_alphahrv():
    messages = list(decode(synthetic_fit()))
    device = next(m for m in messages if m['message'] == 23)
    assert device['values']['product'] == 4130
    recording = core.build_recording(messages)
    assert recording.sensors[0]['label'] == 'Garmin HRM-Pro Plus'
    result = core.compute(recording)
    assert result['summary']['valid_windows'] > 20
    assert result['summary']['scheduled_windows'] == len(result['windows'])
    assert result['navigation']['start_ms'] == core.FIT_UNIX_OFFSET_MS+1_000_000_000
    assert result['time_alignment'] == 'estimated'
    assert 'serial_number' not in json.dumps(recording.preparation())


def test_native_rr_required_crc_and_running():
    with pytest.raises(core.DFAError, match='rr_missing'):
        core.build_recording(list(decode(synthetic_fit(with_rr=False))))
    with pytest.raises(core.DFAError, match='activity_type_unsupported'):
        core.build_recording(list(decode(synthetic_fit(sport=2))))
    with pytest.raises(core.DFAError, match='source_unsupported'):
        core.build_recording(list(decode(synthetic_fit(product=999))))
    raw = bytearray(synthetic_fit())
    raw[-1] ^= 1
    with pytest.raises(core.DFAError, match='fit_invalid'):
        list(decode(bytes(raw)))


def test_source_identity_incomplete_descriptor_does_not_erase_history():
    messages = [{"frame": i, "message": 23, "values": d} for i,d in enumerate([
        {'device_index': 1, 'manufacturer': 1, 'product': 4130},
        {'device_index': 1, 'manufacturer': None, 'product': None},
        {'device_index': 1, 'manufacturer': 123, 'product': None}])]
    with pytest.raises(core.DFAError, match='source_contradiction'):
        core.sensor_evidence(messages)
    polar = [{'frame':0,'message':23,'values':{'manufacturer':123,'product_name':' Polar H10\t'}}]
    assert core.sensor_evidence(polar)[0][0]['label'] == 'Polar H10'
    polar[0]['values']['product_name'] = 'My H10'
    assert not core.sensor_evidence(polar)[0]


def test_rr_quality_does_not_join_deleted_beats():
    assert core.qc_reasons([500]*20) == [None]*20
    assert core.qc_reasons([500]*4) == ['qc_incomplete']*4
    values = [500]*20
    values[10] = 601
    assert core.qc_reasons(values)[10] == 'rr_suspect'
    values[10] = 600
    assert core.qc_reasons(values)[10] is None
    values[10] = 2001
    assert core.qc_reasons(values)[10] == 'rr_out_of_range'
    messages = list(decode(synthetic_fit()))
    packet = [m for m in messages if m['message'] == 78][250]
    packet['values']['time'] = [500, None, 500]
    result = core.compute(core.build_recording(messages))
    assert any('rr_discontinuity' in w['reasons'] for w in result['windows'])


def test_window_minimum_beat_and_support_guards():
    recording = core.build_recording(list(decode(synthetic_fit(values=np.random.default_rng(2).integers(790,811,400).tolist()))))
    result = core.compute(recording)
    assert result['summary']['valid_windows'] == 0
    assert any('insufficient_beats' in w['reasons'] for w in result['windows'])


def test_timer_pause_and_clock_breaks_never_bridge():
    recording = core.build_recording(list(decode(synthetic_fit())))
    first = recording.blocks[0]
    mid = (first.start+first.end)//2
    second = core.Block(mid+60000, first.end+60000, [])
    # Explicit second timer segment without RR remains missing, not joined.
    recording.blocks = [core.Block(first.start, mid, [p for p in first.packets if p.b <= mid]), second]
    result = core.compute(recording)
    assert all(w['end_ms'] <= mid or w['start_ms'] >= mid+60000 for w in result['windows'])
    assert any('alignment_missing' in w['reasons'] for w in result['windows'])


def test_overlays_unix_time_independent_support_zeros_and_gaps():
    start = 1_750_000_000
    windows = [{'index':0,'start_ms':start*1000,'end_ms':(start+120)*1000}]
    samples = [{'t_sec':start+i,'power_watts':0,'speed_ms':4} for i in range(120)]
    value = core.overlay(windows, samples)[0]
    assert value == {'index':0,'power_watts':0,'pace_sec_km':250}
    assert core.overlay(windows, samples[:94])[0]['power_watts'] is None
    assert core.overlay(windows, samples[:95])[0]['power_watts'] == 0
    samples[10]['power_watts'] = -1
    samples[11]['speed_ms'] = float('nan')
    assert core.overlay(windows, samples)[0]['power_watts'] == 0


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    engine = create_engine('sqlite:///'+str(tmp_path/'dfa.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(service, 'require_policy', lambda: 'sha256:'+'a'*64)
    monkeypatch.setattr('api.legal_receipts.user_background_processing_authorized', lambda db, owner: True)
    with factory() as db:
        owner = str(uuid4())
        db.add(User(id=owner, email='dfa@example.invalid', hashed_password='x', is_active=True))
        db.add(Activity(user_id=owner, activity_id='123', date=date.today(), source='garmin', activity_type='new_running_subtype'))
        db.flush()
        snapshot = sync_writer.write_garmin_fit_snapshot(user_id=owner, account_id='account', activity_id='123', raw=synthetic_fit(), db=db)
        sync_writer.write_garmin_fit_parse(snapshot, db)
        db.commit()
    yield factory, owner
    engine.dispose()


def prepare(factory, owner):
    with factory() as db:
        c = service.catalog(db, owner, '123')
        result, code = service.submit(db, owner, '123', c['inputs'][0]['input'], c['catalog_revision'], None)
        assert code == 202
    with factory() as db:
        claim = service.claim(db)
    service.execute(factory, *claim)
    with factory() as db:
        result = service.read_run(db, owner, '123', result['id'], 0, 120)
        assert result['status'] == 'awaiting_source_confirmation', result
        return result


def confirmed(factory, owner):
    preparation = prepare(factory, owner)
    with factory() as db:
        proof = service.confirm(db, owner, '123', {
            'run_id': preparation['id'], 'sensor_ref': preparation['sensors'][0]['sensor_ref'],
            'evidence_digest': preparation['evidence_digest'], 'statement_version':core.STATEMENT_VERSION, 'confirmed':True})
        c = service.catalog(db, owner, '123')
        run, _ = service.submit(db, owner, '123', c['inputs'][0]['input'], c['catalog_revision'], proof['id'])
    return proof, run


def test_end_to_end_two_phase_cache_and_context(store):
    factory, owner = store
    proof, run = confirmed(factory, owner)
    with factory() as db:
        claim = service.claim(db)
    service.execute(factory, *claim)
    with factory() as db:
        result = service.read_run(db, owner, '123', run['id'], 0, 120)
        assert result['status'] == 'complete', result
        assert result['summary']['valid_windows'] > 0
        assert result['source_assurance'] == 'user_confirmed'
        context = service.context(db, owner, '123', run['id'],0,120,result['result_revision'],None)
        assert all(w['power_watts'] is None for w in context['windows'])
        c = service.catalog(db, owner, '123')
        cached, code = service.submit(db, owner, '123', c['inputs'][0]['input'], c['catalog_revision'], proof['id'])
        assert code == 200 and cached['id'] == run['id']
        with pytest.raises(HTTPException) as exc:
            service.read_run(db, 'another-owner', '123', run['id'],0,120)
        assert exc.value.status_code == 404


def test_delete_fences_late_worker_and_keeps_raw(store):
    factory, owner = store
    proof, run = confirmed(factory, owner)
    with factory() as db:
        claim = service.claim(db)
    with factory() as db:
        service.erase(db, owner, '123')
    service.execute(factory, *claim)
    with factory() as db:
        assert not db.query(Run).filter_by(user_id=owner).count()
        assert not db.query(Confirmation).filter_by(user_id=owner).count()
        assert RRRecordingReader(db).list_inputs(owner, '123')
        assert service.export(db, owner)['confirmations'] == []


def test_reparse_and_expiry_preserve_correct_confirmation_scope(store):
    factory, owner = store
    proof, run = confirmed(factory, owner)
    with factory() as db:
        p = db.query(Run).filter_by(phase='prepare').one()
        p.expires_at = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
        service.cleanup(db, owner)
        db.commit()
        assert db.get(Confirmation, proof['id']) is not None
        from api.connectiq import reparse_snapshot
        reparse_snapshot(owner, '123', run['snapshot_id'], db)
        assert db.get(Confirmation, proof['id']) is None
        assert db.get(Run, run['id']).freshness == 'stale'


def test_manifest_pending_never_expires_and_replay_failure_closed(store, monkeypatch):
    factory, owner = store
    value = storage.request(owner, 'activity', '123', 'withdrawal')
    value['requested_at'] = (datetime.utcnow()-timedelta(days=100)).isoformat()
    storage.store(value)
    assert list(storage.iter_active())
    monkeypatch.setattr(storage, 'iter_active', lambda: (_ for _ in ()).throw(storage.StorageError('unavailable')))
    with factory() as db:
        with pytest.raises(HTTPException) as exc:
            service.catalog(db, owner, '123')
        assert exc.value.status_code == 503
        assert service.erase(db, owner, '123')['deleted']


def test_cancel_retry_generation_and_lease_recovery(store):
    factory, owner = store
    proof, run = confirmed(factory, owner)
    with factory() as db:
        first = service.claim(db)
        current = db.get(Run, run['id'])
        current.lease_until = datetime.utcnow()-timedelta(seconds=1)
        db.get(service.Slot,1).lease_until = current.lease_until
        db.commit()
        second = service.claim(db)
        assert second[1] == first[1]+1
    service.execute(factory, *first)
    with factory() as db:
        assert db.get(Run, run['id']).status == 'running'
        cancelled = service.change_run(db,owner,'123',run['id'],'cancel')
        with pytest.raises(HTTPException):
            service.change_run(db,owner,'123',run['id'],'retry',first[1])
        retried = service.change_run(db,owner,'123',run['id'],'retry',cancelled['generation'])
        assert retried['status'] == 'queued'


def test_original_rr_indices_survive_off_timer_and_corrupt_packets():
    messages = list(decode(synthetic_fit()))
    start = next(i for i,m in enumerate(messages) if m['message']==21)
    messages.insert(start, {'frame':0,'message':78,'values':{'time':[450,550,65535]}})
    packet = [m for m in messages if m['message']==78][202]
    packet['values']['time']=[500,None,500,65535]
    recording=core.build_recording(messages)
    assert recording.blocks[0].packets[0].first_index == 2
    after=[p for p in recording.blocks[0].packets if p.frame>packet['frame']][0]
    assert after.first_index == 206


def test_science_contract_parameter_mapping_and_activation_fail_closed(monkeypatch):
    from analysis.science_artifacts import load_policy_contract
    contract=load_policy_contract(core.SDR_ID)
    assert core.digest({k:v.value for k,v in contract.parameters.items()}) == core.POLICY_PARAMETER_DIGEST
    assert contract.model_version == core.METHOD_VERSION
    with pytest.raises(HTTPException, match='503'):
        service.require_policy()
    from types import SimpleNamespace
    fake=SimpleNamespace(model_version='changed',parameters=contract.parameters,contract_digest='sha256:'+'a'*64)
    monkeypatch.setattr('analysis.science_artifacts.load_policy_contract',lambda *a,**kw:fake)
    with pytest.raises(HTTPException):
        service.require_policy()


def test_quota_retry_target_preserved_and_policy_change_stales_result(store,monkeypatch):
    factory,owner=store
    proof,run=confirmed(factory,owner)
    with factory() as db:
        cancelled=service.change_run(db,owner,'123',run['id'],'cancel')
        db.get(Run,run['id']).retained_bytes=service.MAX_RESULT_BYTES
        db.commit()
        monkeypatch.setattr(service,'OWNER_QUOTA',service.MAX_RESULT_BYTES)
        retry=service.change_run(db,owner,'123',run['id'],'retry',cancelled['generation'])
        assert retry['id']==run['id'] and retry['status']=='queued'
        monkeypatch.setattr(service,'require_policy',lambda:'sha256:'+'b'*64)
        assert service.read_run(db,owner,'123',run['id'],0,120)['freshness']=='stale'


def test_boundaries_and_rights_route_scope(store,monkeypatch):
    from api.auth import is_dfa_rights_route
    from api.china_client_boundary import _is_rights_route
    root='/api/activities/123/dfa-alpha1'
    for method,path in [('DELETE',root),('DELETE',root+'/source-confirmations/abc'),('POST',root+'/runs/abc/cancel')]:
        assert is_dfa_rights_route(method,path) and _is_rights_route(method,path)
    for method,path in [('GET',root),('POST',root),('POST',root+'/runs/abc/retry'),('DELETE',root+'/anything')]:
        assert not is_dfa_rights_route(method,path)
    factory,owner=store
    with factory() as db:
        c=service.catalog(db,owner,'123')
        monkeypatch.setattr('sync.rr_recording.MAX_FIT_BYTES',5)
        with pytest.raises(core.DFAError,match='fit_too_large'):
            RRRecordingReader(db).raw(RecordingRef(**c['inputs'][0]['input']))


def test_confirmation_must_use_server_evidence_and_no_optical_override(store):
    factory,owner=store
    prepared=prepare(factory,owner)
    with factory() as db:
        payload={'run_id':prepared['id'],'sensor_ref':'forged','evidence_digest':prepared['evidence_digest'],
                 'statement_version':core.STATEMENT_VERSION,'confirmed':True}
        with pytest.raises(HTTPException) as exc:
            service.confirm(db,owner,'123',payload)
        assert exc.value.status_code==409
        assert db.query(Confirmation).count()==0


def test_http_owner_routes_are_private_for_success_and_errors(store):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes.activity_dfa import router
    from api.auth import require_write_access, require_dfa_rights_access
    from api.main import DFAResponsePrivacyMiddleware
    from db.session import get_db
    factory,owner=store
    app=FastAPI()
    app.include_router(router,prefix='/api')
    app.add_middleware(DFAResponsePrivacyMiddleware)
    def db_override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db]=db_override
    app.dependency_overrides[require_write_access]=lambda:owner
    app.dependency_overrides[require_dfa_rights_access]=lambda:owner
    client=TestClient(app)
    root='/api/activities/123/dfa-alpha1'
    for response in [client.get(root),client.get(root+'/runs/missing'),client.post(root,json={}),client.delete(root)]:
        assert response.headers['cache-control']=='private, no-store'
        assert 'etag' not in response.headers
    def forbidden():
        raise HTTPException(403,'first_party_required')
    app.dependency_overrides[require_write_access]=forbidden
    response=client.get(root)
    assert response.status_code==403 and response.headers['cache-control']=='private, no-store'
    def crashed():
        raise RuntimeError('synthetic internal detail that must not escape')
    app.dependency_overrides[require_write_access]=crashed
    response=TestClient(app,raise_server_exceptions=False).get(root)
    assert response.status_code==500 and response.headers['cache-control']=='private, no-store'
    assert response.json()=={'detail':'DFA_REQUEST_FAILED'}


def test_postgresql_global_slot_and_read_timeout(tmp_path,monkeypatch):
    import os
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import text
    from db.models import GarminFitSnapshot,GarminFitParse,GarminFitChunk
    url=os.environ.get('DFA_TEST_DATABASE_URL')
    if not url:
        pytest.skip('DFA_TEST_DATABASE_URL selects the isolated migrated PostgreSQL test database')
    monkeypatch.setenv('DATA_DIR',str(tmp_path))
    monkeypatch.setattr(service,'require_policy',lambda:'sha256:'+'a'*64)
    monkeypatch.setattr('api.legal_receipts.user_background_processing_authorized',lambda db,owner:True)
    engine=create_engine(url)
    factory=sessionmaker(bind=engine)
    owners=[]
    try:
        for _ in range(2):
            owner=str(uuid4());owners.append(owner)
            with factory() as db:
                db.add(User(id=owner,email=owner+'@example.invalid',hashed_password='x',is_active=True))
                db.flush()
                db.add(Activity(user_id=owner,activity_id='123',date=date.today(),source='garmin'))
                snapshot=sync_writer.write_garmin_fit_snapshot(user_id=owner,account_id='account',activity_id='123',raw=synthetic_fit(),db=db)
                sync_writer.write_garmin_fit_parse(snapshot,db);db.commit()
                c=service.catalog(db,owner,'123')
                service.submit(db,owner,'123',c['inputs'][0]['input'],c['catalog_revision'],None)
        def claim():
            with factory() as db: return service.claim(db)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims=list(pool.map(lambda _:claim(),range(2)))
        active=[c for c in claims if c]
        assert len(active)==1
        service.execute(factory,*active[0])
        with factory() as db:
            assert db.get(Run,active[0][0]).status=='awaiting_source_confirmation'
            ref=RecordingRef(**RRRecordingReader(db).list_inputs(owners[0],'123')[0]['input'])
            assert RRRecordingReader(db).raw(ref)
            assert db.execute(text('SHOW statement_timeout')).scalar()=='30s'
        # Actual two-session PostgreSQL interleaving: pause the numerical
        # worker immediately before publication, commit source revocation, release.
        with factory() as db:
            other_claim=service.claim(db)
        service.execute(factory,*other_claim)
        with factory() as db:
            prepared=service.read_run(db,owners[0],'123',active[0][0],0,120)
            proof=service.confirm(db,owners[0],'123',{'run_id':prepared['id'],
                'sensor_ref':prepared['sensors'][0]['sensor_ref'],'evidence_digest':prepared['evidence_digest'],
                'statement_version':core.STATEMENT_VERSION,'confirmed':True})
            c=service.catalog(db,owners[0],'123')
            computation,_=service.submit(db,owners[0],'123',c['inputs'][0]['input'],c['catalog_revision'],proof['id'])
            claim_for_compute=service.claim(db)
        import threading
        ready,release=threading.Event(),threading.Event()
        real_compute=service.compute
        def paused_compute(*args,**kwargs):
            result=real_compute(*args,**kwargs)
            ready.set()
            assert release.wait(10)
            return result
        monkeypatch.setattr(service,'compute',paused_compute)
        with ThreadPoolExecutor(max_workers=1) as pool:
            worker=pool.submit(service.execute,factory,*claim_for_compute)
            try:
                assert ready.wait(10)
                with factory() as db:
                    service.erase(db,owners[0],'123',proof['id'])
            finally:
                release.set()
            worker.result(timeout=10)
        with factory() as db:
            assert db.get(Run,computation['id']) is None
            assert db.get(service.Slot,1).run_id is None
    finally:
        with factory() as db:
            for owner in owners:
                service._erase(db,{'user_id':owner,'scope':'owner','target_id':owner,'requested_at':datetime.utcnow().isoformat()})
                for model in [GarminFitChunk,GarminFitParse,GarminFitSnapshot,Activity]:
                    db.query(model).filter_by(user_id=owner).delete(synchronize_session=False)
                db.query(User).filter_by(id=owner).delete(synchronize_session=False)
            db.commit()
        engine.dispose()


def test_decoder_and_elapsed_caps_are_explicit(monkeypatch):
    raw=synthetic_fit()
    with monkeypatch.context() as m:
        m.setattr('sync.rr_recording.MAX_RR',3)
        with pytest.raises(core.DFAError,match='rr_limit'):
            list(decode(raw))
    with monkeypatch.context() as m:
        m.setattr('sync.rr_recording.MAX_FRAMES',3)
        with pytest.raises(core.DFAError,match='frame_limit'):
            list(decode(raw))
    with monkeypatch.context() as m:
        m.setattr(core,'MAX_ELAPSED_MS',1000)
        with pytest.raises(core.DFAError,match='elapsed_limit'):
            core.build_recording(list(decode(raw)))


@pytest.mark.parametrize('cap,code',[('MAX_RESULT_BYTES','result_limit'),('MAX_EXECUTION_SECONDS','execution_time_limit')])
def test_worker_output_and_execution_caps_release_reservation(store,monkeypatch,cap,code):
    factory,owner=store
    proof,run=confirmed(factory,owner)
    with factory() as db:
        claimed=service.claim(db)
    monkeypatch.setattr(service,cap,0)
    service.execute(factory,*claimed)
    with factory() as db:
        record=db.get(Run,run['id'])
        assert record.status=='failed' and record.error_code==code
        assert record.result is None and record.retained_bytes==0
        assert db.get(Confirmation,proof['id']) is not None
        assert db.get(service.Slot,1).run_id is None


def seed_archive(db,owner,activity):
    db.add(Activity(user_id=owner,activity_id=activity,date=date.today(),source='garmin'))
    snapshot=sync_writer.write_garmin_fit_snapshot(user_id=owner,account_id='account',activity_id=activity,raw=synthetic_fit(),db=db)
    sync_writer.write_garmin_fit_parse(snapshot,db)
    db.commit()


def test_owner_and_global_admission_limits_preserve_queued_work(store,monkeypatch):
    factory,owner=store
    with factory() as db:
        c=service.catalog(db,owner,'123')
        queued,_=service.submit(db,owner,'123',c['inputs'][0]['input'],c['catalog_revision'],None)
        seed_archive(db,owner,'456')
        second=service.catalog(db,owner,'456')
        with pytest.raises(HTTPException) as exc:
            service.submit(db,owner,'456',second['inputs'][0]['input'],second['catalog_revision'],None)
        assert exc.value.status_code==429 and exc.value.detail=='DFA_OWNER_QUEUE_FULL'
        other=str(uuid4())
        db.add(User(id=other,email=other+'@example.invalid',hashed_password='x',is_active=True))
        db.flush()
        seed_archive(db,other,'123')
        c2=service.catalog(db,other,'123')
        monkeypatch.setattr(service,'MAX_ACTIVE_GLOBAL',1)
        with pytest.raises(HTTPException) as exc:
            service.submit(db,other,'123',c2['inputs'][0]['input'],c2['catalog_revision'],None)
        assert exc.value.status_code==429 and exc.value.detail=='DFA_QUEUE_FULL'
        assert db.get(Run,queued['id']).status=='queued'


@pytest.mark.parametrize('action',['cancel','revoke','delete','reparse'])
def test_inflight_publication_cannot_outlive_rights_or_source_change(store,monkeypatch,action):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from api.connectiq import reparse_snapshot
    factory,owner=store
    proof,run=confirmed(factory,owner)
    with factory() as db:
        claimed=service.claim(db)
    ready,release=threading.Event(),threading.Event()
    real_compute=service.compute
    def paused(*args,**kwargs):
        result=real_compute(*args,**kwargs)
        ready.set()
        assert release.wait(10),'test must release the blocked publisher'
        return result
    monkeypatch.setattr(service,'compute',paused)
    with ThreadPoolExecutor(max_workers=1) as executor:
        worker=executor.submit(service.execute,factory,*claimed)
        try:
            assert ready.wait(10),'computation must reach prepublication barrier'
            with factory() as db:
                if action=='cancel': service.change_run(db,owner,'123',run['id'],'cancel')
                elif action=='revoke': service.erase(db,owner,'123',proof['id'])
                elif action=='delete': service.erase(db,owner,'123')
                else: reparse_snapshot(owner,'123',run['snapshot_id'],db)
        finally:
            release.set()
        worker.result(timeout=10)
    with factory() as db:
        record=db.get(Run,run['id'])
        if action in ('delete','revoke'):
            assert record is None
        else:
            assert record.status=='cancelled' and record.result is None
        assert db.get(service.Slot,1).run_id is None


def test_restored_pre_reparse_confirmation_and_numeric_result_are_erased(store):
    from copy import deepcopy
    from api.connectiq import reparse_snapshot
    from db.models import GarminFitSnapshot
    factory,owner=store
    proof,run=confirmed(factory,owner)
    with factory() as db:
        claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        old_run=db.get(Run,run['id']);old_proof=db.get(Confirmation,proof['id'])
        assert old_run.status=='complete' and old_run.result['summary']['valid_windows']>0
        saved_run={c.name:deepcopy(getattr(old_run,c.name)) for c in Run.__table__.columns}
        saved_proof={c.name:deepcopy(getattr(old_proof,c.name)) for c in Confirmation.__table__.columns}
        reparse_snapshot(owner,'123',run['snapshot_id'],db)
        assert any(v['reason']=='source_changed' for v in storage.iter_active())
        service._delete_runs(db,db.query(Run).filter_by(user_id=owner))
        db.query(Confirmation).filter_by(user_id=owner).delete(synchronize_session=False)
        db.get(GarminFitSnapshot,run['snapshot_id']).active_parse_id=run['parse_id']
        db.add(Confirmation(**saved_proof));db.flush();db.add(Run(**saved_run));db.commit()
        # Same method, same old active parse and same proof would look current
        # without the restore manifest. The read preflight must remove them.
        c=service.catalog(db,owner,'123')
        assert c['latest_run'] is None and c['source_confirmations']==[]
        assert db.get(Run,run['id']) is None and db.get(Confirmation,proof['id']) is None


def test_catalog_distinguishes_unsupported_provider_and_known_nonrunning(store):
    factory,owner=store
    with factory() as db:
        activity=db.query(Activity).filter_by(user_id=owner,activity_id='123').one()
        activity.source='coros';db.commit()
        assert service.catalog(db,owner,'123')['availability']=='provider_unsupported'
        activity.source='garmin';activity.activity_type='cycling';db.commit()
        assert service.catalog(db,owner,'123')['availability']=='activity_type_unsupported'
