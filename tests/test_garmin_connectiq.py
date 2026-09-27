"""Synthetic FIT protocol fixtures, archive integrity and durable owner fences."""
import base64
import io
import struct
import uuid
import zipfile
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from sync.garmin_fit import FitProjection, typed, extract_fit_files, FitArchiveError
from db.models import (Base, User, UserConfig, UserConnection, GarminFitSnapshot as Snapshot,
    GarminFitParse as Parse, GarminFitChunk as Chunk, GarminConnectIQJob as Job,
    GarminConnectIQItem as Item)
from db import sync_writer
from api import connectiq


class SyntheticFit:
    """Small FIT encoder; all values are synthetic, no real athlete payloads."""
    def __init__(self):
        self.body = bytearray()

    def definition(self, local, message, fields=(), dev=()):
        self.body.extend(struct.pack('<BBBHB', 0x40 | local | (0x20 if dev else 0), 0, 0, message, len(fields)))
        for number, size, base_type in fields:
            self.body.extend(bytes((number, size, base_type)))
        if dev:
            self.body.append(len(dev))
            for number, size, index in dev:
                self.body.extend(bytes((number, size, index)))

    def data(self, local, raw):
        self.body.append(local); self.body.extend(raw)

    def identity(self, index, app):
        self.definition(0, 207, [(3, 1, 2), (1, 16, 13), (4, 4, 134)])
        self.data(0, bytes([index]) + uuid.UUID(app).bytes + struct.pack('<I', 143))

    def description(self, index, number, name, units, base_type=132, scale=1, offset=0):
        fields = [(0,1,2), (1,1,2), (2,1,2), (3,32,7), (8,16,7), (6,1,2), (7,1,1)]
        self.definition(1,206,fields)
        self.data(1, bytes([index,number,base_type]) + name.encode().ljust(32,b'\0') + units.encode().ljust(16,b'\0') + struct.pack('<Bb',scale,offset))

    def finish(self):
        from fitdecode.utils import compute_crc
        header = struct.pack('<BBHI4s',12,0x20,2180,len(self.body),b'.FIT')
        raw = header + self.body
        return raw + struct.pack('<H',compute_crc(raw))


def sample_fit():
    fit = SyntheticFit()
    fit.identity(0, '18fb2cf0-1a4b-430d-ad66-988c847421f4')
    fit.description(0,0,'Power','Watts')
    fit.description(0,8,'Form Power','Watts',scale=10,offset=1)
    fit.description(0,55,'Unknown','widgets',base_type=143)
    fit.identity(1, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
    fit.description(1,0,'Power','Watts')
    fit.definition(2,20,[(253,4,134),(7,2,132)],[(0,2,0),(8,4,0),(55,8,0),(0,2,1)])
    fit.data(2,struct.pack('<IHHHHQH',1000,300,250,200,65535,2**60+3,999))
    fit.data(2,struct.pack('<IHHHHQH',1000,301,251,210,220,2**60+5,998))
    fit.description(0,8,'Form Power','Watts',scale=2)
    fit.definition(2,20,[(253,4,134)],[(8,2,0)])
    fit.data(2,struct.pack('<IH',1001,100))
    fit.description(0,10,'Lap Power','Watts')
    fit.definition(3,19,(),[(10,2,0)])
    fit.data(3,struct.pack('<H',250))
    fit.description(0,99,'CP','Watts')
    fit.definition(4,18,(),[(99,2,0)])
    fit.data(4,struct.pack('<H',270))
    return fit.finish()


def project(raw):
    projection = FitProjection()
    frames = [f for chunk in projection.chunks(raw) for f in chunk]
    return projection, frames


def test_lossless_all_scopes_arrays_unknowns_and_redefinition():
    raw = sample_fit()
    projection, frames = project(raw)
    assert b''.join(base64.b64decode(f['raw']['value']) for f in frames) == raw
    assert projection.developer_field_count == 11
    data = [f for f in frames if f.get('message_number') == 20 and f['frame_type'] == 4]
    assert len(data) == 3  # Repeated timestamps remain separate messages.
    first = data[0]['fields']
    assert first[1]['value'] == typed(300)  # Native Garmin power not overwritten.
    assert first[2]['normalized']['value'] == typed(250)
    assert first[3]['normalized']['value'] == typed([19.0,None])
    assert first[4]['value'] == typed(2**60+3)
    assert not first[4]['interpreted']
    assert not first[5]['interpreted']  # Same field number/name from unknown app.
    assert data[2]['fields'][1]['normalized']['value'] == typed(50.0)
    assert first[3]['descriptor_index'] != data[2]['fields'][1]['descriptor_index']
    assert {f['normalized']['metric'] for r in frames for f in r.get('fields',[]) if 'normalized' in f} == {'power','form_power','lap_average_power','critical_power'}


def test_legacy_and_new_registry_maps_are_application_scoped():
    from sync.garmin_fit import normalized_metric
    cases = [(0,'Watts','power'),(2,'RPM','cadence'),(3,'Milliseconds','ground_contact_time'),
             (4,'Centimeters','vertical_oscillation'),(8,'Watts','form_power'),(9,'kN/m','leg_spring_stiffness')]
    for app in ('660a581e-5301-460c-8f2f-034c8b6dc90f','18fb2cf0-1a4b-430d-ad66-988c847421f4'):
        for number, unit, metric in cases:
            result = normalized_metric(app,number,20,{'units':unit},10)
            assert result['metric'] == metric
            assert normalized_metric('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',number,20,{'units':unit},10) is None
    assert normalized_metric(app,0,20,{'units':'unknown'},10) is None


def test_archive_zip_multi_original_and_safety(monkeypatch):
    raw = sample_fit()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,'w') as archive:
        archive.writestr('../../one.fit',raw)
        archive.writestr('two.FIT',raw)
    assert extract_fit_files(buf.getvalue()) == [raw,raw]
    assert extract_fit_files(raw) == [raw]
    with pytest.raises(FitArchiveError):
        extract_fit_files(b'no original')
    monkeypatch.setattr('sync.garmin_fit.MAX_ORIGINAL_BYTES',8)
    with pytest.raises(FitArchiveError,match='original_too_large'):
        extract_fit_files(raw)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine,expire_on_commit=False)
    session = factory()
    session.add_all([User(id='owner',email='owner@example.test',hashed_password='x',is_active=True),
        User(id='other',email='other@example.test',hashed_password='x',is_active=True),
        UserConfig(user_id='owner',source_options={'garmin_region':'international'}),
        UserConnection(user_id='owner',platform='garmin',status='connected',encrypted_credentials=b'fake',wrapped_dek=b'fake')])
    session.commit()
    monkeypatch.setattr('api.legal_receipts.user_background_processing_authorized',lambda db,user_id: True)
    monkeypatch.setattr('time.sleep',lambda _:None)
    yield session
    session.close();engine.dispose()


def test_snapshot_idempotence_failed_reparse_and_owner_boundaries(db,monkeypatch):
    raw = sample_fit()
    s = sync_writer.write_garmin_fit_snapshot('owner','account','123',raw,db)
    assert sync_writer.write_garmin_fit_snapshot('owner','account','123',raw,db).id == s.id
    p = sync_writer.write_garmin_fit_parse(s,db)
    assert p.status == 'complete'
    db.commit()
    page = connectiq.messages('owner','123',p.id,0,10,db)
    assert len(page['frames']) == 10
    assert page['next_offset'] == 10
    with pytest.raises(HTTPException) as error:
        connectiq.messages('other','123',p.id,0,10,db)
    assert error.value.status_code == 404
    old = s.active_parse_id
    def fail(self,raw):
        yield [{'index':0}]
        raise ValueError('private_payload')
    monkeypatch.setattr(FitProjection,'chunks',fail)
    failed = sync_writer.write_garmin_fit_parse(s,db)
    assert failed.status == 'parse_failed' and failed.error_code == 'invalid_fit'
    assert s.active_parse_id == old
    assert db.query(Chunk).filter_by(parse_id=failed.id).count() == 0
    assert s.raw_fit == raw


def make_job(db,**kw):
    from db.connection_credentials import connection_credentials_generation
    connection = db.query(UserConnection).filter_by(user_id='owner').one()
    job = Job(user_id='owner',credential_generation=connection_credentials_generation(connection),
              region='international',kind='daily',discovery_complete=True,**kw)
    db.add(job);db.flush();sync_writer.write_connectiq_items(job,['123'],db);db.commit()
    return job


class FakeClient:
    def __init__(self,raw=None):
        self.raw = raw if raw is not None else sample_fit()
        self.downloads = 0
        self._praxys_user_profile_id = '77'
    def download_activity(self,aid,dl_fmt):
        self.downloads += 1
        return self.raw
    def connectapi(self,path,params):
        return []


def test_durable_worker_original_hash_reparse_and_account_identity(db):
    job = make_job(db)
    client = FakeClient()
    claim = connectiq._claim(db)
    connectiq.run_job(db,*claim,client_factory=lambda db,job:client)
    db.refresh(job)
    assert job.status == 'complete'
    assert client.downloads == 1
    item = db.query(Item).filter_by(job_id=job.id).one()
    assert item.status == 'complete'
    snapshot = db.query(Snapshot).one()
    assert snapshot.raw_fit == client.raw
    job.status = 'queued';item.status = 'queued';db.commit()
    connectiq.run_job(db,*connectiq._claim(db),client_factory=lambda db,job:client)
    assert client.downloads == 1
    assert db.query(Parse).count() == 1
    job.status='queued';db.commit();client._praxys_user_profile_id='88'
    with pytest.raises(RuntimeError,match='account_changed'):
        connectiq.run_job(db,*connectiq._claim(db),client_factory=lambda db,job:client)
    assert client.downloads == 1


@pytest.mark.parametrize('mode',['cancel','generation','terms','delete','lease'])
def test_stale_worker_cannot_commit_download(db,monkeypatch,mode):
    job=make_job(db)
    client=FakeClient()
    original=client.download_activity
    def download(aid,dl_fmt):
        result=original(aid,dl_fmt)
        if mode=='cancel':job.status='cancelled';job.lease_token=None
        elif mode=='generation':db.query(UserConnection).one().encrypted_credentials=b'changed'
        elif mode=='terms':monkeypatch.setattr('api.legal_receipts.user_background_processing_authorized',lambda db,user:False)
        elif mode=='delete':db.query(User).filter_by(id='owner').one().is_active=False
        else:job.lease_until=datetime.utcnow()-timedelta(seconds=1)
        db.commit()
        return result
    client.download_activity=download
    with pytest.raises(RuntimeError):
        connectiq.run_job(db,*connectiq._claim(db),client_factory=lambda db,job:client)
    db.rollback()
    assert db.query(Snapshot).count()==0


def test_unavailable_and_invalid_original_are_explicit(db):
    job=make_job(db)
    connectiq.run_job(db,*connectiq._claim(db),client_factory=lambda db,job:FakeClient(b''))
    db.refresh(job)
    assert job.status=='completed_with_errors'
    assert db.query(Item).one().status=='unavailable'


def test_lease_recovery_and_stale_claim(db):
    job=make_job(db)
    first=connectiq._claim(db)
    assert connectiq._claim(db) is None
    db.refresh(job);job.lease_until=datetime.utcnow()-timedelta(seconds=1);db.commit()
    second=connectiq._claim(db)
    assert second[0]==first[0] and second[1]!=first[1]
    with pytest.raises(RuntimeError,match='lease_lost'):connectiq._fence(db,*first)


def test_api_owner_only_pagination_and_raw_download(db):
    from api.routes.connectiq import router
    from api.auth import get_current_user_id,require_write_access
    from db.session import get_db
    app=FastAPI();app.include_router(router,prefix='/api')
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user_id]=lambda:'owner'
    app.dependency_overrides[require_write_access]=lambda:'owner'
    raw=sample_fit();s=sync_writer.write_garmin_fit_snapshot('owner','account','123',raw,db)
    p=sync_writer.write_garmin_fit_parse(s,db);db.commit()
    with TestClient(app) as client:
        catalog=client.get('/api/activities/123/connectiq').json()
        assert catalog['snapshots'][0]['parse_id']==p.id
        response=client.get(f'/api/activities/123/connectiq/original/{s.id}')
        assert response.content==raw and response.headers['cache-control']=='private, no-store'
        exported=client.get(f'/api/activities/123/connectiq/export?parse_id={p.id}')
        assert exported.status_code==200
        assert len(exported.json()['frames'])==p.frame_count
        app.dependency_overrides[get_current_user_id]=lambda:'other'
        assert client.get(f'/api/activities/123/connectiq/original/{s.id}').status_code==404
        assert client.get(f'/api/activities/123/connectiq/messages?parse_id={p.id}').status_code==404
        assert client.get('/api/activities/123/connectiq').status_code==404


def test_streaming_original_enforces_length_and_closes(monkeypatch):
    from sync.garmin_original import GarminOriginalClient
    from sync import garmin_original
    class Response:
        headers={}
        closed=False
        def iter_content(self,chunk_size):yield b'123';yield b'456'
        def close(self):self.closed=True
    response=Response()
    fake=SimpleNamespace(client=SimpleNamespace(request=lambda *a,**k:response))
    monkeypatch.setattr(garmin_original,'MAX_ORIGINAL_BYTES',5)
    with pytest.raises(FitArchiveError,match='original_too_large'):
        GarminOriginalClient.download(fake,'/download')
    assert response.closed


def test_cn_region_fence_uses_legacy_credentials_fallback(db,monkeypatch):
    db.query(UserConfig).filter_by(user_id='owner').one().source_options={}
    monkeypatch.setattr('db.connection_credentials.load_connection_credentials',lambda *a,**kw:{'is_cn':True})
    job=make_job(db);job.region='cn';db.commit()
    assert connectiq._fence(db,*connectiq._claim(db)).region=='cn'


def test_multiple_jobs_same_owner_are_serialized(db):
    make_job(db);make_job(db)
    assert connectiq._claim(db) is not None
    assert connectiq._claim(db) is None


def test_account_export_and_explicit_deletion_cover_archive(db):
    from api.account_deletion import _delete_user_owned_rows
    raw=sample_fit()
    owner=sync_writer.write_garmin_fit_snapshot('owner','a','123',raw,db)
    other=sync_writer.write_garmin_fit_snapshot('other','a','123',raw,db)
    sync_writer.write_garmin_fit_parse(owner,db);sync_writer.write_garmin_fit_parse(other,db)
    make_job(db);db.commit()
    exported=connectiq.account_export('owner',db)
    assert len(exported)==1 and exported[0]['snapshot_id']==owner.id
    assert exported[0]['parses'][0]['frames']
    _delete_user_owned_rows(db,'owner',feedback_ids=[],publication_outboxes_by_feedback_id={},publication_attempts_by_outbox_id={})
    db.commit()
    for model in (Snapshot,Parse,Chunk,Job,Item):
        assert db.query(model).filter_by(user_id='owner').count()==0
    assert db.query(Snapshot).filter_by(user_id='other').count()==1


def test_additive_alembic_migration_and_postgres_types():
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable,CreateIndex
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('connectiq_migration', Path(__file__).resolve().parents[1] / 'alembic/versions/0a1b2c3d4e5f_add_garmin_connectiq_archive.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)')
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert 'garmin_fit_snapshots' in inspect(connection).get_table_names()
        assert len(inspect(connection).get_columns('garmin_connectiq_jobs'))==len(Job.__table__.columns)
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert inspect(connection).get_table_names()==['users']
    ddl=str(CreateTable(Snapshot.__table__).compile(dialect=postgresql.dialect()))
    assert 'BYTEA' in ddl and 'ON DELETE CASCADE' in ddl
    unique=next(index for index in Job.__table__.indexes if index.unique)
    assert "WHERE status = 'running'" in str(CreateIndex(unique).compile(dialect=postgresql.dialect()))
    engine.dispose()


def test_crc_failure_and_resource_limit_preserve_original(db,monkeypatch):
    raw=bytearray(sample_fit());raw[-1]^=1
    snapshot=sync_writer.write_garmin_fit_snapshot('owner','a','123',bytes(raw),db)
    parsed=sync_writer.write_garmin_fit_parse(snapshot,db)
    assert parsed.status=='parse_failed' and snapshot.raw_fit==bytes(raw)
    monkeypatch.setattr('sync.garmin_fit.MAX_FRAMES',2)
    with pytest.raises(FitArchiveError,match='frame_limit'):project(sample_fit())


def test_backfill_resume_cancel_and_paginated_discovery(db,monkeypatch):
    monkeypatch.setattr('db.connection_credentials.load_connection_credentials',lambda *a,**kw:{'is_cn':False})
    job=connectiq.create_backfill('owner',date(2024,1,1),date(2024,12,31),db)
    client=FakeClient()
    calls=[]
    def page(path,params):calls.append(params);return []
    client.connectapi=page
    connectiq.run_job(db,*connectiq._claim(db),client_factory=lambda db,job:client)
    assert calls[0]['startDate']=='2024-01-01' and calls[0]['endDate']=='2024-12-31'
    db.refresh(job);assert job.status=='complete'
    assert connectiq.change_job('owner',job.id,'cancel',db)['status']=='cancelled'
    assert connectiq.change_job('owner',job.id,'resume',db)['status']=='queued'
    with pytest.raises(HTTPException):connectiq.change_job('other',job.id,'cancel',db)


def test_offline_reparse_requires_owner_and_preserves_old_pagination(db):
    raw=sample_fit();s=sync_writer.write_garmin_fit_snapshot('owner','a','123',raw,db)
    first=sync_writer.write_garmin_fit_parse(s,db);db.commit()
    db.query(UserConnection).delete();db.commit()
    second=connectiq.reparse_snapshot('owner','123',s.id,db)
    assert second['status']=='complete' and second['parse_id']!=first.id
    assert connectiq.messages('owner','123',first.id,0,128,db)['total']==first.frame_count
    with pytest.raises(HTTPException):connectiq.reparse_snapshot('other','123',s.id,db)


def test_job_items_failure_visibility_is_bounded_and_owned(db):
    job=make_job(db);sync_writer.write_connectiq_items(job,['124','125'],db)
    db.query(Item).filter_by(job_id=job.id,activity_id='123').one().status='unavailable';db.commit()
    page=connectiq.job_items('owner',job.id,0,2,db)
    assert page['next_offset']==2 and page['total']==3
    assert page['items'][0]['status']=='unavailable'
    with pytest.raises(HTTPException):connectiq.job_items('other',job.id,0,2,db)
