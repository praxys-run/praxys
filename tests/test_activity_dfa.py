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

    def definition(self, local, message, fields, dev=()):
        self.body.extend(struct.pack('<BBBHB', 0x40 | local | (0x20 if dev else 0), 0, 0, message, len(fields)))
        for field in fields:
            self.body.extend(bytes(field))
        if dev:
            self.body.append(len(dev))
            for field in dev:
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


@pytest.mark.parametrize('fields,payload', [
    ([(0,4,134)], struct.pack('<I',500)),
    ([(0,2,131)], struct.pack('<h',500)),
    ([(0,4,133)], struct.pack('<i',500)),
    ([(0,4,136)], struct.pack('<f',500)),
    ([(0,3,132)], b'\xf4\x01\x00'),
    ([(0,0,132)], b''),
    ([(0,2,132),(0,2,132)], struct.pack('<HH',500,500)),
])
def test_native_rr_rejects_wrong_base_shape_and_duplicate_definitions(fields,payload):
    fit=Fit();fit.definition(0,78,fields);fit.data(0,payload)
    with pytest.raises(core.DFAError,match='fit_invalid'):
        list(decode(fit.finish()))


@pytest.mark.parametrize('number,fields,payload', [
    (23,[(2,4,134)],struct.pack('<I',1)),
    (23,[(4,4,134)],struct.pack('<I',4130)),
    (23,[(27,2,132)],struct.pack('<H',500)),
    (23,[(0,2,132)],struct.pack('<H',1)),
    (23,[(2,4,132)],struct.pack('<HH',1,1)),
    (18,[(5,1,2)],bytes([1])),
    (21,[(253,4,133)],struct.pack('<i',1000000)),
])
def test_native_provenance_fields_reject_wrong_types_or_arrays(number,fields,payload):
    fit=Fit();fit.definition(0,number,fields);fit.data(0,payload)
    with pytest.raises(core.DFAError,match='fit_invalid'):
        list(decode(fit.finish()))


def add_developer_field(fit,name,base_type):
    fit.definition(5,207,[(3,1,2),(1,16,13)])
    fit.data(5,b'\0'+bytes(range(16)))
    fit.definition(6,206,[(0,1,2),(1,1,2),(2,1,2),(3,32,7)])
    fit.data(6,bytes([0,8,base_type])+name.encode().ljust(32,b'\0'))


@pytest.mark.parametrize('name', ['time','manufacturer','product','product_name'])
def test_developer_display_names_never_supply_native_rr_or_sensor_provenance(name):
    fit=Fit()
    add_developer_field(fit,name,7 if name=='product_name' else 132)
    if name=='time':
        fit.definition(0,78,[(0,4,132)],[(8,4,0)])
        fit.data(0,struct.pack('<HHHH',500,510,300,320))
        message=next(m for m in decode(fit.finish()) if m['message']==78)
        assert message['values']=={'time':(500,510)}
    else:
        native_fields=[(0,1,2),(2,2,132),(27,16,7)]
        fake=b'Polar OH1'.ljust(16,b'\0') if name=='product_name' else struct.pack('<H',1 if name=='manufacturer' else 999)
        fit.definition(0,23,native_fields,[(8,len(fake),0)])
        fit.data(0,struct.pack('<BH',1,123)+b'H10'.ljust(16,b'\0')+fake)
        messages=list(decode(fit.finish()))
        device=next(m for m in messages if m['message']==23)
        assert device['values']['manufacturer']==123 and device['values']['product_name']=='H10'
        assert 'product' not in device['values']
        assert core.sensor_evidence(messages)[0][0]['label']=='Polar H10'


def polar_messages(descriptors):
    fit=Fit();fit.definition(0,23,[(0,1,2),(2,2,132),(27,16,7)])
    for manufacturer,name in descriptors:
        fit.data(0,struct.pack('<BH',1,manufacturer if manufacturer is not None else 65535)+(name or '').encode().ljust(16,b'\0'))
    return list(decode(fit.finish()))


@pytest.mark.parametrize('names',[['H10','Polar OH1'],['Polar OH1','H10'],['H10','','Polar OH1']])
def test_native_polar_recording_handle_cannot_change_sensor_model(names):
    with pytest.raises(core.DFAError,match='source_contradiction'):
        core.sensor_evidence(polar_messages([(123,name) for name in names]))


@pytest.mark.parametrize('descriptors',[
    [(123,'H10'),(None,''),(123,' Polar H10 ')],
    [(None,'H10'),(123,'')],
    [(123,''),(None,'Polar H10')],
])
def test_native_polar_aliases_and_missing_fields_enrich_one_identity(descriptors):
    sensors,_=core.sensor_evidence(polar_messages(descriptors))
    assert len(sensors)==1 and sensors[0]['label']=='Polar H10'


def isolated_window(count=200,total=117600,anchor_width=0):
    base,remainder=divmod(total,count)
    values=[base+(i<remainder)+(1 if i%2==0 else -1) for i in range(count)]
    values[-1]+=total-sum(values)
    a=118000 if anchor_width else total
    packet=core.Packet(1,values,a,a+anchor_width,chain=0,cumulative=total)
    return core.Recording([core.Block(0,120000,[packet])],[],"synthetic",count,1)


@pytest.mark.parametrize('count,total,width,reason',[
    (199,117600,0,'insufficient_beats'),(200,117600,0,None),
    (200,117599,0,'insufficient_coverage'),(200,117600,3000,None),
    (200,117600,3001,'alignment_uncertain'),
])
def test_exact_beat_support_and_alignment_width_boundaries(count,total,width,reason):
    window=core.compute(isolated_window(count,total,width))['windows'][0]
    if reason:
        assert window['alpha1'] is None and reason in window['reasons']
    else:
        assert window['alpha1'] is not None and window['coverage_ms']==total
        if width: assert window['offset_width_ms']==5000


def test_rights_export_preserves_retained_numbers_after_processing_and_math_changes(store,monkeypatch):
    factory,owner=store
    proof,run=confirmed(factory,owner)
    with factory() as db: claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        record=db.get(Run,run['id'])
        expected=record.result
        monkeypatch.setattr('api.legal_receipts.user_background_processing_authorized',lambda db,owner:False)
        # Fail loudly if rights export attempts any computational-authority check.
        monkeypatch.setattr(service,'require_authority',lambda *args: (_ for _ in ()).throw(AssertionError('compute authority on rights export')))
        exported=next(item for item in service.export(db,owner)['runs'] if item['id']==run['id'])
        assert exported['result']==expected and exported['result_revision']==record.result_revision
        monkeypatch.setattr(service,'METHOD_VERSION','future-numerical-method')
        exported=next(item for item in service.export(db,owner)['runs'] if item['id']==run['id'])
        assert exported['result']==expected and exported['freshness']=='stale'
        assert exported['method_version']==core.METHOD_VERSION
        service.erase(db,owner,'123',proof['id'])
        assert not any(item['id']==run['id'] for item in service.export(db,owner)['runs'])


def reviewed_projection(step=1,factor=1.0,jump_ms=0):
    """Exact Science review fixture: two RR per packet, file-order anchors."""
    frames=[]
    stamp=1_000_000
    rr=np.random.default_rng(733).integers(480,521,3600)
    def add(number,**values):
        frames.append({'frame':len(frames),'message':number,'values':values})
    add(23,manufacturer=1,product=4130,device_index=1)
    add(21,timestamp=stamp,event=0,event_type=0,event_group=0)
    add(20,timestamp=stamp)
    elapsed=last=0
    for i in range(0,len(rr),2):
        values=rr[i:i+2].tolist()
        elapsed+=sum(values)
        wall=elapsed*factor+(jump_ms if i>=1800 else 0)
        add(78,time=values)
        sampled=int(wall//(step*1000))*step
        if sampled>last:
            add(20,timestamp=stamp+sampled)
            last=sampled
    add(21,timestamp=stamp+int(np.ceil(wall/1000)),event=0,event_type=4,event_group=0)
    add(18,sport=1)
    return frames


@pytest.mark.parametrize('step',[1,10])
def test_reviewed_slow_drift_and_smart_recording_remain_usable(step):
    recording=core.build_recording(reviewed_projection(step=step,factor=1+4/3600))
    result=core.compute(recording)
    assert result['summary']['scheduled_windows']==337
    assert result['summary']['valid_windows']==337


def test_gathered_packet_membership_removes_clock_gap_false_windows():
    recording=core.build_recording(reviewed_projection(jump_ms=10000))
    result=core.compute(recording)
    assert result['summary']['scheduled_windows']==339
    assert result['summary']['valid_windows']==314
    crossing=[w for w in result['windows'] if w['alpha1'] is not None and w['rr_index_start']<1800<=w['rr_index_end']]
    assert crossing==[]
    for w in result['windows']:
        if w['rr_index_start'] is None:
            continue
        gathered={index for p in recording.blocks[w['block']].packets
                  if p.b>=w['start_ms'] and p.a<=w['end_ms']
                  for index in range(p.first_index,p.first_index+len(p.values))}
        assert set(range(w['rr_index_start'],w['rr_index_end']+1)) <= gathered
    origin=recording.blocks[0].start
    for start,end in [(785,905),(790,910),(905,1025)]:
        window=next(w for w in result['windows'] if w['start_ms']==origin+start*1000 and w['end_ms']==origin+end*1000)
        assert window['alpha1'] is None


def test_detectable_large_clock_gap_breaks_chain_without_bridging():
    recording=core.build_recording(reviewed_projection(jump_ms=40000))
    result=core.compute(recording)
    assert len({p.chain for b in recording.blocks for p in b.packets})>1
    assert not any(w['alpha1'] is not None and w['rr_index_start']<1800<=w['rr_index_end'] for w in result['windows'])


def test_native_compressed_record_header_timestamp_remains_an_anchor():
    fit=Fit();stamp=1_000_000
    fit.definition(0,20,[(253,4,134)]);fit.data(0,struct.pack('<I',stamp))
    fit.definition(1,20,[])
    fit.body.append(0x80 | (1 << 5) | ((stamp+1)&31))
    records=[m for m in decode(fit.finish()) if m['message']==20]
    assert [m['values']['timestamp'] for m in records]==[stamp,stamp+1]


@pytest.mark.parametrize('names', [
    ['Polar OH1','H10'], ['H10','Polar OH1'],
    ['Polar OH1','','Polar H10'], ['Polar H10','','Polar OH1'],
])
def test_delayed_polar_manufacturer_preserves_earlier_native_model_conflicts(names):
    descriptors=[(None,name) for name in names]+[(123,'')]
    with pytest.raises(core.DFAError,match='source_contradiction'):
        core.sensor_evidence(polar_messages(descriptors))


@pytest.mark.parametrize('descriptors', [
    [(None,'H10'),(None,'Polar H10'),(123,'')],
    [(None,' Polar H10 '),(None,''),(None,'h10'),(123,'')],
    [(None,''),(None,'H10'),(123,''),(None,'')],
])
def test_delayed_polar_manufacturer_keeps_aliases_and_missing_metadata_eligible(descriptors):
    sensors,_=core.sensor_evidence(polar_messages(descriptors))
    assert len(sensors)==1 and sensors[0]['label']=='Polar H10'


def test_watch_native_model_names_do_not_establish_optical_rr_provenance():
    fit=Fit();fit.definition(0,23,[(0,1,2),(2,2,132),(27,16,7)])
    for name in ('Optical watch','Watch model'):
        fit.data(0,struct.pack('<BH',0,1)+name.encode().ljust(16,b'\0'))
    fit.data(0,struct.pack('<BH',1,123)+b'H10'.ljust(16,b'\0'))
    sensors,_=core.sensor_evidence(list(decode(fit.finish())))
    assert len(sensors)==1 and sensors[0]['label']=='Polar H10'
