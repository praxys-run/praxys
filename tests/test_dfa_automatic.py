"""Behavioral automatic admission, source inference and durable withdrawal tests."""
from datetime import datetime, timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from tests.test_activity_dfa import store, synthetic_fit, Fit, confirmed
from api import activity_dfa as service, dfa_automatic as auto, activity_dfa_storage as storage
from analysis import activity_dfa as core
from analysis.dfa_source import source_inventory
from sync.rr_recording import decode
from db import sync_writer
from db.models import ActivityDFAReceipt as Receipt, ActivityDFAMetadataProof as Proof, ActivityDFARightsState as Rights, ActivityDFAConfirmation as Confirmation, ActivityDFARun as Run


def native_fit(dual=False):
    import struct
    fit=Fit();fit.definition(5,23,[(0,1,2),(1,1,2),(2,2,132),(4,2,132),(25,1,0)])
    fit.data(5,struct.pack('<BBHHB',1,120,1,4130,1))
    if dual:
        fit.data(5,struct.pack('<BBHHB',2,1,1,4130,3))
    fit.body.extend(synthetic_fit()[12:-2]);return fit.finish()


def install(factory,owner,raw):
    with factory() as db:
        db.query(Receipt).filter_by(user_id=owner).delete()
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',raw,db)
        sync_writer.write_garmin_fit_parse(snapshot,db,provider_completion=True);db.commit()


def enable(monkeypatch):
    monkeypatch.setattr(auto,'enabled',lambda db,owner:True)
    monkeypatch.setattr(auto,'require_policy',lambda:'sha256:'+'b'*64)


def finish(factory):
    with factory() as db:
        service.reconcile_receipts(db);claim=service.claim(db)
    assert claim
    service.execute(factory,*claim)
    with factory() as db:
        claim=service.claim(db)
    assert claim
    service.execute(factory,*claim)


def test_default_off_receipts_survive_duplicate_wakes_without_rr_work(store,monkeypatch):
    factory,owner=store;install(factory,owner,native_fit())
    monkeypatch.setattr(auto,'enabled',lambda db,owner:False)
    monkeypatch.setattr(service.RRRecordingReader,'raw',lambda *args:pytest.fail('OFF must not hydrate RR'))
    with factory() as db:
        assert db.query(Receipt).filter_by(user_id=owner).count()==1
        for _ in range(3):service.reconcile_receipts(db)
        assert db.query(Run).count()==0
        assert db.query(Receipt).one().status=='gate_paused'
        assert service.catalog(db,owner,'123')['automatic']['scheduled']


def test_sync_receipt_rollback_and_duplicate_archive_are_atomic(store):
    factory,owner=store;install(factory,owner,native_fit())
    with factory() as db:
        original=db.query(Receipt).count()
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','other',native_fit(),db)
        sync_writer.write_garmin_fit_parse(snapshot,db,provider_completion=True)
        assert db.query(Receipt).count()==original+1
        db.rollback()
        assert db.query(Receipt).count()==original
        existing=db.query(service.Receipt).one()
        assert existing.recording_ref['activity_id']=='123'


@pytest.mark.parametrize('dual',[False,True])
def test_source_qualified_auto_finishes_with_no_owner_statement_and_unchanged_numerics(store,monkeypatch,dual):
    factory,owner=store;enable(monkeypatch);raw=native_fit(dual);install(factory,owner,raw);finish(factory)
    with factory() as db:
        assert db.query(Confirmation).count()==0
        proof=db.query(Proof).one();run=db.query(Run).filter_by(phase='compute').one()
        assert run.status=='complete' and run.origin=='automatic' and run.confirmation_id is None
        assert len(proof.candidates)==(2 if dual else 1)
        assert {s['transport'] for s in proof.candidates}==({'ANT+','BLE'} if dual else {'ANT+'})
        manual=core.compute(core.build_recording(list(decode(raw))))
        automatic=run.result.copy()
        for field in ('source_proof_id','source_rule_version','metadata_projection_version','candidates'):automatic.pop(field)
        automatic['source_assurance']='user_confirmed'
        assert automatic==manual
        monkeypatch.setattr(auto,'enabled',lambda db,owner:False)
        assert service.read_run(db,owner,'123',run.id,0,1000)['summary']==manual['summary']
        assert 'serial' not in json.dumps(proof.candidates).lower()


def test_enriched_source_metadata_preserves_genuine_v1_confirmation(store,monkeypatch):
    factory,owner=store;proof,queued=confirmed(factory,owner)
    plain=list(decode(synthetic_fit()));enriched=list(decode(native_fit()))
    assert core.sensor_evidence(plain)==core.sensor_evidence(enriched)
    with factory() as db:
        retained=db.query(Confirmation).one()
        assert service.proof_current(retained,service._inputs(db,owner,'123'))
        assert retained.evidence_digest==core.sensor_evidence(enriched)[1]


@pytest.mark.parametrize('extra,outcome',[
 ({'device_index':2,'manufacturer':1,'product':3300,'source_type':1,'device_type':120},'source_unresolved'),
 ({'device_index':2,'manufacturer':999,'product':9,'source_type':3,'device_type':1},'source_unresolved'),
 ({'device_index':2,'manufacturer':1,'product':999,'source_type':5,'device_type':10},'source_unresolved'),
 ({'device_index':1,'manufacturer':1,'product':3300,'source_type':1,'device_type':120},'source_ineligible'),
 ({'device_index':2,'manufacturer':1,'product':999},'eligible_metadata_inferred'),
])
def test_all_candidate_source_inventory_does_not_guess_optical_or_merge_handles(extra,outcome):
    messages=list(decode(native_fit()));messages.append({'frame':9999,'message':23,'values':extra})
    assert source_inventory(messages,{'snapshot_id':'exact'})['outcome']==outcome


def test_inactive_auto_science_never_relabels_manual_policy(store,monkeypatch):
    factory,owner=store;install(factory,owner,native_fit())
    monkeypatch.setattr(auto,'enabled',lambda db,owner:True)
    with factory() as db:
        service.reconcile_receipts(db)
        assert db.query(Run).count()==0
        assert db.query(Receipt).one().status=='science_inactive'
        assert service.catalog(db,owner,'123')['manual_policy_active'] is True


def test_gate_off_at_claim_and_publication_pauses_then_resumes(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit())
    with factory() as db:
        service.reconcile_receipts(db)
        monkeypatch.setattr(auto,'enabled',lambda db,owner:False)
        assert service.claim(db) is None
        assert db.query(Run).one().status=='gate_paused'
        monkeypatch.setattr(auto,'enabled',lambda db,owner:True)
        service.reconcile_receipts(db);claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:claimed=service.claim(db)
    original=service.compute
    def gate_off(*args,**kwargs):
        value=original(*args,**kwargs);monkeypatch.setattr(auto,'enabled',lambda db,owner:False);return value
    monkeypatch.setattr(service,'compute',gate_off);service.execute(factory,*claimed)
    with factory() as db:
        run=db.query(Run).filter_by(phase='compute').one()
        assert run.status=='gate_paused' and run.result is None
        assert db.get(service.Slot,1).run_id is None


def test_cancel_suppression_survives_new_sync_and_ordered_restore_reauthorization(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit());finish(factory)
    with factory() as db:
        run=db.query(Run).filter_by(phase='compute').one()
        service.change_run(db,owner,'123',run.id,'cancel')
        state=db.get(Rights,(owner,'123'));assert state.suppressed
        old=list(storage.iter_active(owner))[-1]
        revision=service.catalog(db,owner,'123')['catalog_revision']
        generation=state.generation
        service.reconcile_receipts(db)
        assert not service.read_run(db,owner,'123',run.id,0,1000).get('windows')
        response=auto.reauthorize(db,owner,'123',revision,generation)
        assert response['rights_generation']==generation+1
        service.replay_manifest(db,old)
        assert not db.get(Rights,(owner,'123')).suppressed
        assert db.get(Rights,(owner,'123')).generation==generation+1
        assert db.query(Receipt).one().status=='suppressed' # explicit reauth is not auto restart


def test_cap_deferral_is_durable_and_missing_or_foreign_read_never_admits(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit())
    monkeypatch.setattr(service,'MAX_ACTIVE_GLOBAL',0)
    with factory() as db:
        service.reconcile_receipts(db)
        assert db.query(Receipt).one().status=='deferred' and db.query(Run).count()==0
        before=db.query(Receipt).count()
        assert service.catalog(db,owner,'123')['latest_run'] is None
        assert db.query(Receipt).count()==before and db.query(Run).count()==0
        with pytest.raises(HTTPException):service.catalog(db,'other','123')
        monkeypatch.setattr(service,'MAX_ACTIVE_GLOBAL',20)
        service.reconcile_receipts(db);assert db.query(Run).one().status=='queued'


def test_provider_original_receipts_dedupe_and_reparse_does_not_reschedule(store):
    factory,owner=store
    raw=native_fit();install(factory,owner,raw)
    with factory() as db:
        receipt=db.query(Receipt).one();old_event=receipt.event_digest
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',raw,db)
        # Maintenance reparse invalidates old publication but creates no event.
        sync_writer.write_garmin_fit_parse(snapshot,db);db.commit()
        assert db.query(Receipt).count()==1 and db.query(Receipt).one().event_digest==old_event
        assert db.query(Receipt).one().status=='stale'
        # Genuinely new provider bytes are a distinct completion event.
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',native_fit(True),db)
        sync_writer.write_garmin_fit_parse(snapshot,db,provider_completion=True);db.commit()
        assert db.query(Receipt).count()==2
        from db.dfa_receipts import record_completion
        ref=db.query(Receipt).filter(Receipt.event_digest!=old_event).one().recording_ref
        record_completion(db,owner,'123','garmin',account='account',recording_ref=ref,event_key='archive:'+snapshot.id);db.commit()
        assert db.query(Receipt).count()==2
        value,_=auto.suppress_locked(db,owner,'123','withdrawal');db.commit()
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',synthetic_fit(product=3300),db)
        sync_writer.write_garmin_fit_parse(snapshot,db,provider_completion=True);db.commit()
        assert all(r.status in ('stale','suppressed') for r in db.query(Receipt).all())
        assert db.get(Rights,(owner,'123')).suppressed


def test_overview_chunks_keep_exact_null_windows_and_reject_mixed_revision(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit());finish(factory)
    with factory() as db:
        run=db.query(Run).filter_by(phase='compute').one()
        page=service.overview(db,owner,'123',run.id,run.result_revision,0,1000)
        assert page['windows']==run.result['windows']
        assert page['display_resolution']=='original_windows'
        assert page['binding']['source_proof_id']==run.metadata_proof_id
        with pytest.raises(HTTPException):service.overview(db,owner,'123',run.id,'wrong',0,1000)
        with pytest.raises(HTTPException):service.overview(db,owner,'123',run.id,run.result_revision,0,1001)


def test_inferred_source_withdrawal_and_restore_never_resurrect_proof_or_numbers(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit());finish(factory)
    with factory() as db:
        run=db.query(Run).filter_by(phase='compute').one();proof=db.query(Proof).one()
        service.withdraw_inference(db,owner,'123',proof.id)
        assert db.query(Proof).count()==0
        assert db.get(Rights,(owner,'123')).suppressed
        assert db.query(Run).filter_by(phase='compute').count()==0
        service.reconcile_receipts(db)
        assert db.query(Receipt).one().status=='suppressed'
        assert db.query(Confirmation).count()==0


def test_server_gate_missing_identity_and_evaluation_errors_fail_closed(store,monkeypatch):
    factory,owner=store
    from api import statsig_client
    with factory() as db:
        monkeypatch.setattr(statsig_client,'get_statsig_user_for_account',lambda *args,**kwargs:None)
        assert not auto.enabled(db,owner)
        monkeypatch.setattr(statsig_client,'get_statsig_user_for_account',lambda *args,**kwargs:object())
        monkeypatch.setattr(statsig_client,'check_gate',lambda *args: (_ for _ in ()).throw(RuntimeError('gate unavailable')))
        assert not auto.enabled(db,owner)


def test_auto_receipt_unsupported_provider_is_observable_without_rr(store,monkeypatch):
    factory,owner=store;enable(monkeypatch)
    from db.models import Activity
    from db.dfa_receipts import record_completion
    with factory() as db:
        db.add(Activity(user_id=owner,activity_id='other',date=datetime.utcnow().date(),source='strava',activity_type='running'))
        record_completion(db,owner,'other','strava',event_key='completed:other');db.commit()
        service.reconcile_receipts(db)
        value=service.catalog(db,owner,'other')
        assert value['automatic']['receipt']['state']=='unavailable'
        assert value['automatic']['receipt']['reason']=='provider_unsupported'
        assert db.query(Run).count()==0



def test_sqlite_existing_manual_rows_migrate_without_losing_fences(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,inspect
    from db.session import _ensure_sqlite_dfa_automatic
    from db.models import Base
    from alembic import command
    from alembic.config import Config
    url='sqlite:///'+str(tmp_path/'legacy.sqlite')
    monkeypatch.setenv('DATABASE_URL',url)
    config=Config();config.set_main_option('script_location',str(__import__('pathlib').Path('alembic').resolve()))
    command.upgrade(config,'b4d5f6a70819')
    engine=create_engine(url)
    assert 'origin' not in {c['name'] for c in inspect(engine).get_columns('activity_dfa_runs')}
    Base.metadata.create_all(engine)
    _ensure_sqlite_dfa_automatic(engine)
    assert {'origin','source_assurance','metadata_proof_id','rights_generation'} <= {c['name'] for c in inspect(engine).get_columns('activity_dfa_runs')}
    _ensure_sqlite_dfa_automatic(engine)
    engine.dispose()


def test_stale_manual_requests_and_reauthorization_cannot_clear_newer_withdrawal(store):
    factory,owner=store
    with factory() as db:
        catalog=service.catalog(db,owner,'123');revision=catalog['catalog_revision'];selected=catalog['inputs'][0]['input']
        service.erase(db,owner,'123')
        assert service.catalog(db,owner,'123')['catalog_revision']==revision
        for expected in (None,0):
            with pytest.raises(HTTPException) as exc:service.submit(db,owner,'123',selected,revision,None,expected)
            assert exc.value.detail=='DFA_RIGHTS_CHANGED'
        state=db.get(Rights,(owner,'123'));generation=state.generation
        auto.suppress_locked(db,owner,'123','cancelled');db.commit()
        with pytest.raises(HTTPException):auto.reauthorize(db,owner,'123',revision,generation)
        assert db.get(Rights,(owner,'123')).suppressed


def test_deferred_receipt_cancellation_is_available_without_a_run(store,monkeypatch):
    factory,owner=store;install(factory,owner,native_fit());monkeypatch.setattr(auto,'enabled',lambda db,owner:False)
    with factory() as db:
        service.reconcile_receipts(db);receipt=db.query(Receipt).one()
        assert receipt.run_id is None
        response=service.cancel_receipt(db,owner,'123',receipt.id)
        assert response['state']=='suppressed' and response['rights_generation']==1
        service.reconcile_receipts(db)
        assert db.query(Run).count()==0 and db.get(Rights,(owner,'123')).suppressed



def test_new_migration_refuses_unsafe_schema_rollback_without_removing_rights(tmp_path,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlalchemy import create_engine,text
    url='sqlite:///'+str(tmp_path/'new-head.sqlite');monkeypatch.setenv('DATABASE_URL',url)
    config=Config();config.set_main_option('script_location',str(Path('alembic').resolve()))
    command.upgrade(config,'head')
    engine=create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO users(id,email,hashed_password,is_active,is_superuser,is_verified,is_demo) VALUES ('synthetic','synthetic@example.invalid','unused',1,0,0,0)")
        conn.exec_driver_sql("INSERT INTO activity_dfa_rights_state(user_id,activity_id,suppressed,generation,reason,changed_at) VALUES ('synthetic','activity',1,4,'withdrawal',CURRENT_TIMESTAMP)")
    with pytest.raises(RuntimeError,match='DFA automatic rights data requires a compatible rollback artifact'):
        command.downgrade(config,'b4d5f6a70819')
    with engine.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar()=='c5e6f7a81920'
        assert conn.execute(text('SELECT generation FROM activity_dfa_rights_state')).scalar()==4
    engine.dispose()


def test_repeat_activity_withdrawal_after_reauthorization_uses_current_rights(store):
    factory,owner=store
    with factory() as db:
        service.erase(db,owner,'123')
        deleted=service.catalog(db,owner,'123')
        old_generation=deleted['automatic']['rights_generation']
        auto.reauthorize(db,owner,'123',deleted['catalog_revision'],old_generation)
        before=service.catalog(db,owner,'123')
        assert not before['automatic']['suppressed']
        service.erase(db,owner,'123')
        current=service.catalog(db,owner,'123')
        assert current['automatic']['suppressed']
        assert current['automatic']['rights_generation']>before['automatic']['rights_generation']
        count=len(list(storage.iter_active(owner)))
        for _ in range(3):service.erase(db,owner,'123')
        assert len(list(storage.iter_active(owner)))==count
        assert service.catalog(db,owner,'123')['automatic']['rights_generation']==current['automatic']['rights_generation']
        selected=before['inputs'][0]['input']
        with pytest.raises(HTTPException) as exc:
            service.submit(db,owner,'123',selected,before['catalog_revision'],None,before['automatic']['rights_generation'])
        assert exc.value.detail=='DFA_RIGHTS_CHANGED'
        with pytest.raises(HTTPException) as exc:
            service.submit(db,owner,'123',selected,current['catalog_revision'],None,current['automatic']['rights_generation'])
        assert exc.value.detail=='DFA_ACTIVITY_SUPPRESSED'
        assert db.query(Run).count()==0


def test_restored_owner_marker_blocks_genuinely_later_provider_receipts(store,monkeypatch):
    factory,owner=store;enable(monkeypatch)
    marker=storage.request(owner,'owner',owner,'account_deletion')
    with factory() as db:
        service.replay_manifest(db,marker)
        assert auto.owner_erased(db,owner)
    # This is the original Trust sequence: restored owner remains active/legal,
    # then actual provider completion arrives after the marker and its SQL replay.
    install(factory,owner,native_fit())
    with factory() as db:
        assert db.query(Receipt).one().status=='suppressed'
        service.reconcile_receipts(db)
        assert service.claim(db) is None
        assert db.query(Run).count()==db.query(Proof).count()==db.query(Confirmation).count()==0
        with pytest.raises(HTTPException) as exc:service.catalog(db,owner,'123')
        assert exc.value.detail=='DFA_OWNER_ERASED'
        c={'catalog_revision':core.digest(service._inputs(db,owner,'123')),'automatic':auto.receipt_view(db,owner,'123')}
        assert c['automatic']['suppressed']
        with pytest.raises(HTTPException) as exc:
            auto.reauthorize(db,owner,'123',c['catalog_revision'],c['automatic']['rights_generation'])
        assert exc.value.detail=='DFA_OWNER_ERASED'
        exported=service.export(db,owner)
        assert exported['runs']==exported['metadata_proofs']==exported['confirmations']==[]
        assert exported['rights']==[{'activity_id':'','scope':'owner','suppressed':True,'generation':1,'reason':'account_deletion','changed_at':db.get(Rights,(owner,'')).changed_at}]
        service.replay_manifest(db,marker)
        assert db.get(Rights,(owner,'')).generation==1


def test_owner_replay_erases_restored_rows_after_cutoff_without_rights_reset_or_payload_hydration(store,monkeypatch):
    from sqlalchemy import event
    from db.models import User
    from db.dfa_receipts import record_completion
    from uuid import uuid4
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit());finish(factory)
    with factory() as db:
        run=db.query(Run).filter_by(phase='compute').one();run_id=run.id
        # A restored row can be newer than a retained deletion cutoff. Owner
        # erasure must still block it, even with a restored active account.
        marker=storage.request(owner,'owner',owner,'account_deletion')
        marker['requested_at']=(datetime.utcnow()-timedelta(days=100)).isoformat()
        marker['completed_at']=(datetime.utcnow()-timedelta(days=90)).isoformat();storage.store(marker)
        assert not storage.expired(marker)
        db.add(Rights(user_id=owner,activity_id='123',generation=8,suppressed=False,reason='reauthorized'))
        other=str(uuid4());db.add(User(id=other,email=other+'@example.invalid',hashed_password='x',is_active=True));db.flush()
        record_completion(db,other,'other','strava',event_key='other-completion');db.commit()
        reads=[]
        def observe(conn,cursor,statement,parameters,context,executemany):
            if statement.lstrip().upper().startswith('SELECT'):reads.append(statement.lower())
        event.listen(db.get_bind(),'before_cursor_execute',observe)
        monkeypatch.setattr(service.RRRecordingReader,'raw',lambda *a:pytest.fail('rights replay hydrated FIT'))
        service.replay_manifest(db,marker)
        event.remove(db.get_bind(),'before_cursor_execute',observe)
        assert not any('activity_dfa_runs.result ' in sql or 'garmin_fit_snapshots.raw_fit' in sql for sql in reads)
        assert db.get(Rights,(owner,'123')).generation==9 and db.get(Rights,(owner,'123')).suppressed
        assert db.query(Receipt).filter_by(user_id=other).count()==1
        assert db.query(Run).filter_by(user_id=owner).count()==db.query(Proof).filter_by(user_id=owner).count()==0
        with pytest.raises(HTTPException) as exc:service.read_run(db,owner,'123',run_id,0,1000)
        assert exc.value.status_code==404
        service.cleanup(db,owner);db.commit()
        assert any(v['scope']=='owner' for v in storage.iter_active(owner))
        # Replaying older activity authorization cannot reset the owner fence or
        # the monotonic per-activity generation. Gate/science remain irrelevant.
        stale=storage.request_rights(owner,'123',8,False,'reauthorized')
        monkeypatch.setattr(auto,'enabled',lambda *a:False)
        monkeypatch.setattr(auto,'require_policy',lambda:(_ for _ in ()).throw(HTTPException(503,'inactive')))
        service.replay_manifest(db,stale);service.replay_manifest(db,marker)
        assert auto.owner_erased(db,owner) and db.get(Rights,(owner,'123')).generation==9
        assert service.export(db,owner)['runs']==[]


def test_owner_marker_fences_claim_and_publication_and_survives_sql_restore(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit())
    with factory() as db:service.reconcile_receipts(db);prepare=service.claim(db)
    service.execute(factory,*prepare)
    with factory() as db:compute_claim=service.claim(db)
    marker=storage.request(owner,'owner',owner,'account_deletion')
    # Simulate restore losing the SQL fence while an execution token survives;
    # execute must replay the retained marker before any RR or publication.
    monkeypatch.setattr(service.RRRecordingReader,'raw',lambda *a:pytest.fail('owner-erased compute hydrated FIT'))
    service.execute(factory,*compute_claim)
    with factory() as db:
        assert auto.owner_erased(db,owner) and service.claim(db) is None
        assert db.query(Run).count()==db.query(Proof).count()==0
        assert db.get(service.Slot,1).run_id is None
        db.query(Rights).filter_by(user_id=owner).delete();db.commit()
        service.replay_manifest(db,marker)
        assert auto.owner_erased(db,owner)
        assert service.export(db,owner)['runs']==[]


def test_owner_erasure_at_compute_publication_discards_inflight_output(store,monkeypatch):
    factory,owner=store;enable(monkeypatch);install(factory,owner,native_fit())
    with factory() as db:service.reconcile_receipts(db);prepare=service.claim(db)
    service.execute(factory,*prepare)
    with factory() as db:compute_claim=service.claim(db)
    original=service.compute
    def erase_after_compute(*args,**kwargs):
        output=original(*args,**kwargs)
        marker=storage.request(owner,'owner',owner,'account_deletion')
        with factory() as db:service.replay_manifest(db,marker)
        return output
    monkeypatch.setattr(service,'compute',erase_after_compute)
    service.execute(factory,*compute_claim)
    with factory() as db:
        assert db.query(Run).count()==db.query(Proof).count()==db.query(Confirmation).count()==0
        assert db.get(service.Slot,1).run_id is None and auto.owner_erased(db,owner)
        assert service.export(db,owner)['runs']==[]


def test_absent_owner_replay_has_no_fk_insert_and_empty_key_is_not_user_addressable(store):
    from db.models import User
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes.activity_dfa import router, Reauthorize
    from pydantic import ValidationError
    factory,owner=store;marker=storage.request(owner,'owner',owner,'account_deletion')
    with factory() as db:
        # Real account deletion removes owner data; replay of its retained marker
        # must work without attempting to insert an orphan rights FK row.
        service._erase(db,marker);db.query(Rights).filter_by(user_id=owner).delete()
        db.query(User).filter_by(id=owner).delete();db.commit()
        service.replay_manifest(db,marker)
        assert db.query(Rights).filter_by(user_id=owner).count()==0
    app=FastAPI();app.include_router(router,prefix='/api');client=TestClient(app)
    assert client.post('/api/activities//dfa-alpha1/reauthorize',json={'catalog_revision':'c'*64,'expected_rights_generation':0}).status_code==404
    with pytest.raises(ValidationError):Reauthorize(catalog_revision='c'*64,expected_rights_generation=0,activity_id='')
    with pytest.raises(storage.StorageError):storage.request_rights(owner,'',1,False,'reauthorized')


def partial_name_fit(names):
    fit=Fit()
    for name in names:
        fit.definition(6,23,[(0,1,2),(27,len(name),7)]);fit.data(6,bytes([1])+name)
    fit.body.extend(native_fit()[12:-2]);return fit.finish()


def test_complete_native_handle_inventory_rejects_early_name_only_conflicts_before_auto_compute(store,monkeypatch):
    factory,owner=store;enable(monkeypatch)
    raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    messages=list(decode(raw));names=[m['values']['product_name'] for m in messages if m['message']==23 and 'product_name' in m['values']]
    assert names==['HRM-Pro Plus','different native model']
    assert source_inventory(messages,{'snapshot_id':'exact'})['outcome']=='source_ineligible'
    # The v1 manual sensor/proof digest remains exactly the existing behavior.
    assert core.sensor_evidence(messages)==core.sensor_evidence(list(decode(native_fit())))
    install(factory,owner,raw)
    with factory() as db:service.reconcile_receipts(db);claim=service.claim(db)
    service.execute(factory,*claim)
    with factory() as db:
        assert db.query(Proof).count()==db.query(Confirmation).count()==0
        assert db.query(Run).one().status=='unavailable'
        assert db.query(Run).one().error_code=='source_contradiction'
        assert service.claim(db) is None


def test_complete_native_partial_handles_can_supply_later_product_without_expanding_model_rules(store,monkeypatch):
    import struct
    fit=Fit();fit.definition(6,23,[(0,1,2),(1,1,2),(2,2,132),(25,1,0)])
    fit.data(6,struct.pack('<BBHB',1,120,1,1))
    fit.definition(6,23,[(0,1,2),(4,2,132)]);fit.data(6,struct.pack('<BH',1,4130))
    # Synthetic base device is the same recording-local handle, with no transport.
    fit.body.extend(synthetic_fit()[12:-2]);raw=fit.finish()
    projected=source_inventory(list(decode(raw)),{'snapshot_id':'exact'})
    assert projected['outcome']=='eligible_metadata_inferred'
    assert projected['candidates'][0]['label']=='Garmin HRM-Pro Plus'
    assert projected['candidates'][0]['transport']=='ANT+'
    factory,owner=store;enable(monkeypatch);install(factory,owner,raw);finish(factory)
    with factory() as db:
        assert db.query(Run).filter_by(phase='compute').one().status=='complete'
        assert db.query(Confirmation).count()==0
    # Even non-HR native descriptor facts bind the v2 inventory digest.
    messages=list(decode(raw));messages.append({'frame':9999,'message':23,'values':{'device_index':7,'manufacturer':1,'product':999}})
    updated=source_inventory(messages,{'snapshot_id':'exact'})
    assert updated['outcome']=='eligible_metadata_inferred' and updated['source_evidence_digest']!=projected['source_evidence_digest']


@pytest.mark.parametrize('foreign_keys',[False,True])
def test_live_account_delete_clears_sql_fence_while_private_owner_marker_survives(store,foreign_keys):
    from api.account_deletion import _delete_user_owned_rows
    from db.models import User
    factory,owner=store;marker=storage.request(owner,'owner',owner,'account_deletion')
    with factory() as db:
        db.connection().exec_driver_sql('PRAGMA foreign_keys='+('ON' if foreign_keys else 'OFF'))
        assert bool(db.connection().exec_driver_sql('PRAGMA foreign_keys').scalar())==foreign_keys
        _delete_user_owned_rows(db,owner,feedback_ids=[],publication_outboxes_by_feedback_id={},publication_attempts_by_outbox_id={})
        db.query(User).filter_by(id=owner).delete();db.commit()
        assert db.query(Rights).filter_by(user_id=owner).count()==0
        assert any(v['id']==marker['id'] for v in storage.iter_active(owner))
        service.replay_manifest(db,marker)
        assert db.query(Rights).filter_by(user_id=owner).count()==0


def changed_class_fit():
    import struct
    fit=Fit();fit.definition(6,23,[(0,1,2),(1,1,2),(2,2,132),(4,2,132),(25,1,0)])
    fit.data(6,struct.pack('<BBHHB',2,120,999,9,1))
    fit.data(6,struct.pack('<BBHHB',2,99,999,9,5))
    fit.body.extend(native_fit()[12:-2]);return fit.finish()


def legacy_confirmed(factory,owner,raw,monkeypatch,*,complete=True):
    """Genuine historical v1 statement under the pre-r3 native-integrity gap."""
    install(factory,owner,raw)
    exact_inputs=service._inputs
    exact_sha=__import__('hashlib').sha256(raw).hexdigest()
    with monkeypatch.context() as legacy:
        legacy.setattr(service,'_inputs',lambda db,user,activity:[v for v in exact_inputs(db,user,activity) if v['input']['sha256']==exact_sha])
        legacy.setattr(service,'_native_source',lambda *a:{'outcome':'source_unresolved'})
        legacy.setattr('analysis.dfa_source.require_native_integrity',lambda *a:None)
        proof,run=confirmed(factory,owner)
        if complete:
            with factory() as db:claim=service.claim(db)
            service.execute(factory,*claim)
    service._NATIVE_SUMMARIES.clear()
    return proof,run


def test_original_changed_class_native_fit_retains_unknown_hr_relevance_and_manual_clarification(store,monkeypatch):
    raw=changed_class_fit();messages=list(decode(raw))
    descriptors=[m['values'] for m in messages if m['message']==23 and m['values'].get('device_index')==2]
    assert [(v['source_type'],v['device_type']) for v in descriptors]==[(1,120),(5,99)]
    projection=source_inventory(messages,{'snapshot_id':'exact'})
    assert projection['outcome']=='source_unresolved'
    assert core.sensor_evidence(messages)==core.sensor_evidence(list(decode(native_fit())))
    factory,owner=store;enable(monkeypatch);install(factory,owner,raw)
    with factory() as db:service.reconcile_receipts(db);claim=service.claim(db)
    service.execute(factory,*claim)
    with factory() as db:
        assert db.query(Proof).count()==0
        automatic=db.query(Run).one()
        assert automatic.status=='awaiting_source_confirmation'
        assert service.claim(db) is None
    # Unresolved transport/class is not an identity contradiction. Genuine manual
    # clarification of the recorded supported ECG source still computes normally.
    proof,run=confirmed(factory,owner)
    with factory() as db:claim=service.claim(db)
    service.execute(factory,*claim)
    with factory() as db:
        result=service.read_run(db,owner,'123',run['id'],0,1000)
        assert result['status']=='complete' and len(result['windows'])==42
        assert db.query(Confirmation).count()==1 and db.query(Proof).count()==0


def test_original_partial_name_fit_is_rejected_before_new_manual_preparation(store):
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00']);install(factory,owner,raw)
    assert core.sensor_evidence(list(decode(raw)))==core.sensor_evidence(list(decode(native_fit())))
    with pytest.raises(core.DFAError,match='source_contradiction'):core.build_recording(list(decode(raw)))
    with factory() as db:
        c=service.catalog(db,owner,'123')
        with pytest.raises(HTTPException) as exc:service.submit(db,owner,'123',c['inputs'][-1]['input'],c['catalog_revision'],None,c['automatic']['rights_generation'])
        assert exc.value.detail=='source_contradiction'
        assert db.query(Confirmation).count()==0 and db.query(Run).count()==0
        assert any(v['scope']=='snapshot' and v['reason']=='source_changed' for v in storage.iter_active(owner))


@pytest.mark.parametrize('gate',['read','overview','context','catalog','submit','retry'])
def test_legacy_same_digest_proof_and_cached_contradiction_cannot_cross_current_gate(store,monkeypatch,gate):
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    proof,run=legacy_confirmed(factory,owner,raw,monkeypatch)
    with factory() as db:
        row=db.get(Run,run['id']);revision=row.result_revision
        ref=dict(row.recording_ref)
        assert row.status=='complete' and len(row.result['windows'])==42
        assert db.get(Confirmation,proof['id']).evidence_digest==core.sensor_evidence(list(decode(raw)))[1]
        if gate=='read':assert not service.read_run(db,owner,'123',run['id'],0,1000).get('windows')
        elif gate=='catalog':
            c=service.catalog(db,owner,'123');assert c['source_confirmations']==[]
            assert c['latest_run'] is None or c['latest_run']['freshness']=='stale'
        elif gate=='overview':
            with pytest.raises(HTTPException):service.overview(db,owner,'123',run['id'],revision,0,1000)
        elif gate=='context':
            with pytest.raises(HTTPException):service.context(db,owner,'123',run['id'],0,1000,revision,None)
        elif gate=='submit':
            c={'catalog_revision':core.digest(service._inputs(db,owner,'123')),'automatic':auto.receipt_view(db,owner,'123')}
            with pytest.raises(HTTPException):service.submit(db,owner,'123',ref,c['catalog_revision'],proof['id'],c['automatic']['rights_generation'])
        else:
            row.status='failed';db.commit()
            with pytest.raises(HTTPException):service.change_run(db,owner,'123',run['id'],'retry',row.generation,0)
        service._NATIVE_SUMMARIES.clear() # cache eviction/restart cannot erase durable negative
        assert list(service.export(db,owner)['runs'])==[]
        assert db.query(Confirmation).count()==0 and db.query(Run).count()==0


def test_legacy_preparation_cannot_issue_new_confirmation_over_native_contradiction(store,monkeypatch):
    from tests.test_activity_dfa import prepare
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00']);install(factory,owner,raw)
    exact_inputs=service._inputs
    exact_sha=__import__('hashlib').sha256(raw).hexdigest()
    with monkeypatch.context() as legacy:
        legacy.setattr(service,'_inputs',lambda db,user,activity:[v for v in exact_inputs(db,user,activity) if v['input']['sha256']==exact_sha])
        legacy.setattr(service,'_native_source',lambda *a:{'outcome':'source_unresolved'})
        legacy.setattr('analysis.dfa_source.require_native_integrity',lambda *a:None)
        preparation=prepare(factory,owner)
    with factory() as db:
        with pytest.raises(HTTPException):service.confirm(db,owner,'123',{'run_id':preparation['id'],'sensor_ref':preparation['sensors'][0]['sensor_ref'],'evidence_digest':preparation['evidence_digest'],'statement_version':core.STATEMENT_VERSION,'confirmed':True,'expected_rights_generation':0})
        assert db.query(Confirmation).count()==0
        with pytest.raises(HTTPException):service.read_run(db,owner,'123',preparation['id'],0,1000)


def test_pending_native_negative_retains_sql_fact_and_numbers_until_durable_then_restore_fenced(store,monkeypatch):
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    proof,run=legacy_confirmed(factory,owner,raw,monkeypatch)
    with factory() as db:
        old=db.get(Run,run['id']);retained=old.result
        backup={c.name:getattr(old,c.name) for c in Run.__table__.columns}
        proof_row=db.get(Confirmation,proof['id']);proof_backup={c.name:getattr(proof_row,c.name) for c in Confirmation.__table__.columns}
        with monkeypatch.context() as outage:
            outage.setattr(storage,'request',lambda *a:(_ for _ in ()).throw(storage.StorageError('offline')))
            result=service.read_run(db,owner,'123',run['id'],0,1000)
            assert not result.get('windows')
            negative=db.get(Run,run['id']);assert negative.result==retained
            assert negative.error_code=='source_contradiction' and negative.progress==service._NATIVE_PENDING
            service._NATIVE_SUMMARIES.clear()
            negative.expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
            service.cleanup(db,owner);db.commit();assert db.get(Run,run['id']) is not None
            with pytest.raises(HTTPException):service.export(db,owner)
        service.reconcile_source_integrity(db)
        assert db.query(Run).count()==db.query(Confirmation).count()==0
        # Restore the pre-observation backup: private source-changed replay
        # removes old numeric/proof data before a metadata-only rights export.
        db.add(Confirmation(**proof_backup));db.flush();db.add(Run(**backup));db.commit()
        service._NATIVE_SUMMARIES.clear()
        assert list(service.export(db,owner)['runs'])==[]
        assert db.query(Run).count()==db.query(Confirmation).count()==0


def test_native_guard_blocks_late_manual_execution_and_publication(store,monkeypatch):
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    proof,run=legacy_confirmed(factory,owner,raw,monkeypatch,complete=False)
    with factory() as db:claim=service.claim(db)
    service.execute(factory,*claim)
    with factory() as db:
        assert not any(r.status=='complete' or r.result_revision for r in db.query(Run).all())
        assert list(service.export(db,owner)['runs'])==[]


def test_unknown_rights_export_preserves_serialized_numbers_without_any_native_or_authority_read(store,monkeypatch):
    from api.data_export import ExportJSONValue
    from fastapi.encoders import jsonable_encoder
    factory,owner=store;proof,run=confirmed(factory,owner)
    with factory() as db:claim=service.claim(db)
    service.execute(factory,*claim)
    service._NATIVE_SUMMARIES.clear()
    monkeypatch.setattr(service.RRRecordingReader,'raw',lambda *a:pytest.fail('rights export hydrated FIT'))
    monkeypatch.setattr(service.RRRecordingReader,'iter_source_metadata',lambda *a:pytest.fail('rights export inspected native metadata'))
    monkeypatch.setattr(service,'require_authority',lambda *a:pytest.fail('rights export renewed computational authority'))
    with factory() as db:
        result=next(v for v in service.export(db,owner)['runs'] if v['id']==run['id'])
        assert result['result']['windows'] and result['source_assurance']=='user_confirmed'
        assert result['current_native_integrity']=={'state':'UNKNOWN','reason':'not_inspected_for_rights_export','input':result['recording_ref']}
        serialized=json.dumps(jsonable_encoder(result))
        assert json.loads(serialized)['current_native_integrity']['state']=='UNKNOWN'


def test_native_device_only_reader_bounds_exact_integrity_cache_and_early_rights(store,monkeypatch):
    factory,owner=store;raw=native_fit();install(factory,owner,raw)
    with factory() as db:
        c=service.catalog(db,owner,'123');ref=c['inputs'][-1]['input']
        from sync.rr_recording import RRRecordingReader,RecordingRef
        messages=list(RRRecordingReader(db).iter_source_metadata(RecordingRef(**ref)))
        assert messages and {m['message'] for m in messages}=={23}
        assert all('time' not in m['values'] for m in messages)
        calls=[];original=RRRecordingReader.iter_source_metadata
        def inspect(*args):calls.append(1);yield from original(*args)
        monkeypatch.setattr(RRRecordingReader,'iter_source_metadata',inspect)
        service._NATIVE_SUMMARIES.clear()
        for _ in range(3):assert service._native_source(db,ref,'sha256:'+'a'*64)['outcome']=='eligible_metadata_inferred'
        assert len(calls)==1
        assert all(set(summary)<= {'outcome','source_evidence_digest'} for summary in service._NATIVE_SUMMARIES.values())
        auto.suppress_locked(db,owner,'123','withdrawal');db.commit()
        with pytest.raises(HTTPException):service.submit(db,owner,'123',ref,c['catalog_revision'],None,0)
        assert len(calls)==1
        # Device-only decoding still checks existing frame/raw/CRC limits and
        # cooperative deadline; it does not project a single native RR value.
        import sync.rr_recording as reader
        with monkeypatch.context() as bounds:
            bounds.setattr(reader,'MAX_FRAMES',1)
            with pytest.raises(core.DFAError,match='frame_limit'):list(RRRecordingReader(db).iter_source_metadata(RecordingRef(**ref)))
        broken=bytearray(raw);broken[-1]^=1
        with pytest.raises(core.DFAError,match='fit_invalid'):list(reader._decode(bytes(broken),lambda:None,device_only=True))
        with pytest.raises(core.DFAError,match='execution_time_limit'):list(reader._decode(raw,lambda:(_ for _ in ()).throw(core.DFAError('execution_time_limit')),device_only=True))


def test_late_native_contradiction_observation_fences_manual_conditional_publication(store,monkeypatch):
    import analysis.dfa_source as source
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    proof,run=legacy_confirmed(factory,owner,raw,monkeypatch,complete=False)
    with factory() as db:claim=service.claim(db)
    native=service._native_source;integrity=source.require_native_integrity;compute=service.compute
    # Reproduce work that began under the historical gap. The exact native FIT
    # observation becomes visible before publication, with the legacy digest and
    # immutable input unchanged; conditional publication must honor the new fact.
    monkeypatch.setattr(service,'_native_source',lambda *a:{'outcome':'source_unresolved'})
    monkeypatch.setattr(source,'require_native_integrity',lambda *a:None)
    def observed_before_publish(*args,**kwargs):
        output=compute(*args,**kwargs)
        monkeypatch.setattr(service,'_native_source',native)
        monkeypatch.setattr(source,'require_native_integrity',integrity)
        return output
    monkeypatch.setattr(service,'compute',observed_before_publish)
    service.execute(factory,*claim)
    with factory() as db:
        current=db.get(Run,run['id'])
        assert current is None or current.status!='complete' and current.result_revision is None
        service._NATIVE_SUMMARIES.clear()
        assert list(service.export(db,owner)['runs'])==[]
        assert any(v['scope']=='snapshot' and v['reason']=='source_changed' for v in storage.iter_active(owner))


def test_native_negative_durability_failure_before_any_run_remains_enforceable_without_cache(store,monkeypatch):
    factory,owner=store;install(factory,owner,partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00']))
    with factory() as db:
        c=service.catalog(db,owner,'123');ref=c['inputs'][-1]['input']
        with monkeypatch.context() as outage:
            outage.setattr(storage,'request',lambda *a:(_ for _ in ()).throw(storage.StorageError('offline')))
            with pytest.raises(HTTPException):service.submit(db,owner,'123',ref,c['catalog_revision'],None,0)
            negative=db.query(Run).one();assert negative.progress==service._NATIVE_BOOKKEEPING and negative.result is None
            service._NATIVE_SUMMARIES.clear()
            monkeypatch.setattr(service.RRRecordingReader,'raw',lambda *a:pytest.fail('known-negative hydrated FIT after eviction'))
            with pytest.raises(HTTPException):service.submit(db,owner,'123',ref,c['catalog_revision'],None,0)
            assert db.query(Run).one().error_code=='source_contradiction'
        service.reconcile_source_integrity(db)
        assert db.query(Run).count()==0
        assert any(v['scope']=='snapshot' for v in storage.iter_active(owner))


def test_pending_negative_survives_request_rollback_and_fresh_metadata_only_export(store,monkeypatch):
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    proof,run=legacy_confirmed(factory,owner,raw,monkeypatch)
    with monkeypatch.context() as outage:
        outage.setattr(storage,'request',lambda *a:(_ for _ in ()).throw(storage.StorageError('offline')))
        with factory() as db:
            ref=dict(db.get(Run,run['id']).recording_ref)
            revision=core.digest(service._inputs(db,owner,'123'))
            with pytest.raises(HTTPException):service.submit(db,owner,'123',ref,revision,proof['id'],0)
            db.rollback() # simulate the HTTP error handler's transaction cleanup
        service._NATIVE_SUMMARIES.clear()
        outage.setattr(service.RRRecordingReader,'raw',lambda *a:pytest.fail('rights operation hydrated FIT'))
        outage.setattr(service.RRRecordingReader,'iter_source_metadata',lambda *a:pytest.fail('rights operation inspected native metadata'))
        with factory() as fresh:
            row=fresh.get(Run,run['id']);assert row.progress==service._NATIVE_PENDING and row.result['windows']
            with pytest.raises(HTTPException) as exc:service.export(fresh,owner)
            assert exc.value.detail=='DFA_RESTORE_REPLAY_UNAVAILABLE'
            assert fresh.get(Run,run['id']).error_code=='source_contradiction'
            result=service.change_run(fresh,owner,'123',run['id'],'cancel')
            assert 'windows' not in result
    with factory() as db:
        service.reconcile_source_integrity(db)
        assert list(service.export(db,owner)['runs'])==[]


def test_native_snapshot_negative_does_not_remove_other_retained_input(store,monkeypatch):
    factory,owner=store;good_proof,good_run=confirmed(factory,owner)
    with factory() as db:claim=service.claim(db)
    service.execute(factory,*claim)
    bad_proof,bad_run=legacy_confirmed(factory,owner,partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00']),monkeypatch)
    with factory() as db:
        good_ref=dict(db.get(Run,good_run['id']).recording_ref)
        assert not service.read_run(db,owner,'123',bad_run['id'],0,1000).get('windows')
        service._NATIVE_SUMMARIES.clear()
        values=list(service.export(db,owner)['runs'])
        kept=next(v for v in values if v['id']==good_run['id'])
        assert kept['recording_ref']==good_ref and len(kept['result']['windows'])==42
        assert all(v['id']!=bad_run['id'] for v in values)
        assert db.get(Confirmation,good_proof['id']) is not None


def test_stale_retry_never_rebinds_generation_or_inspects_withdrawn_source(store,monkeypatch):
    factory,owner=store;proof,run=confirmed(factory,owner)
    with factory() as db:
        cancelled=service.change_run(db,owner,'123',run['id'],'cancel')
        before=db.get(Run,run['id']).rights_generation
        c=service.catalog(db,owner,'123')
        current=auto.reauthorize(db,owner,'123',c['catalog_revision'],c['automatic']['rights_generation'])['rights_generation']
        monkeypatch.setattr(service.RRRecordingReader,'iter_source_metadata',lambda *a:pytest.fail('stale retry inspected FIT'))
        with pytest.raises(HTTPException):service.change_run(db,owner,'123',run['id'],'retry',cancelled['generation']-1,current)
        assert db.get(Run,run['id']).rights_generation==before and db.get(Run,run['id']).status=='cancelled'
        service.erase(db,owner,'123',proof['id'])
        with pytest.raises(HTTPException):service.change_run(db,owner,'123',run['id'],'retry',cancelled['generation'],current)


@pytest.mark.parametrize('active_status',['queued','running'])
def test_catalog_private_negative_fact_is_terminal_before_flush_with_unrelated_active_job(store,monkeypatch,active_status):
    import hashlib
    from db.models import Activity
    from sqlalchemy import event
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    assert hashlib.sha256(raw).hexdigest()=='80e26bb6174ab51996d5ff0e953afc4b6aa1ece969716bb3dbde932e4955d10b'
    proof,old_run=legacy_confirmed(factory,owner,raw,monkeypatch)
    with factory() as db:
        bad_ref=dict(db.get(Confirmation,proof['id']).recording_ref)
        for row in db.query(Run).filter_by(user_id=owner,snapshot_id=bad_ref['snapshot_id']).all():row.expires_at=datetime.utcnow()-timedelta(seconds=1)
        db.commit();service.cleanup(db,owner);db.commit()
        assert db.query(Run).filter_by(user_id=owner,snapshot_id=bad_ref['snapshot_id']).count()==0
        assert db.get(Confirmation,proof['id']) is not None
        db.add(Activity(user_id=owner,activity_id='unaffected',date=datetime.utcnow().date(),source='garmin',activity_type='running'));db.flush()
        snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','unaffected',native_fit(),db)
        sync_writer.write_garmin_fit_parse(snapshot,db);db.commit()
        c=service.catalog(db,owner,'unaffected')
        active,_=service.submit(db,owner,'unaffected',c['inputs'][0]['input'],c['catalog_revision'],None,0)
        if active_status=='running':
            claim=service.claim(db);assert claim[0]==active['id']
        other=db.get(Run,active['id']);before=(other.status,other.generation,other.rights_generation,other.retained_bytes,other.lease_token)
        slot=db.get(service.Slot,1);slot_before=(slot.run_id,slot.lease_token,slot.lease_until)
    def terminal_on_flush(session,context,instances):
        for candidate in session.new:
            if isinstance(candidate,Run) and candidate.input_digest==core.digest([bad_ref,service._NATIVE_IMPLEMENTATION,'negative']):
                assert candidate.status=='unavailable' and candidate.progress==service._NATIVE_BOOKKEEPING
                assert candidate.retained_bytes==0 and candidate.lease_token is None
    event.listen(factory.class_,'before_flush',terminal_on_flush)
    try:
        with monkeypatch.context() as outage:
            outage.setattr(storage,'request',lambda *a:(_ for _ in ()).throw(storage.StorageError('journal offline')))
            with factory() as db:
                first=service.catalog(db,owner,'123')
                assert first['latest_run'] is None and first['source_confirmations']==[]
                db.rollback()
            service._NATIVE_SUMMARIES.clear()
            outage.setattr(service.RRRecordingReader,'raw',lambda *a:pytest.fail('bookkeeping recovery hydrated FIT'))
            with factory() as fresh:
                fact=fresh.query(Run).filter_by(user_id=owner,progress=service._NATIVE_BOOKKEEPING).one()
                fact_id=fact.id
                assert fact.status=='unavailable' and fact.result is None and fact.retained_bytes==0
                assert fact.confirmation_id is None and fact.metadata_proof_id is None
                other=fresh.get(Run,active['id'])
                assert (other.status,other.generation,other.rights_generation,other.retained_bytes,other.lease_token)==before
                slot=fresh.get(service.Slot,1);assert (slot.run_id,slot.lease_token,slot.lease_until)==slot_before
                assert fresh.query(Run).filter(Run.status.in_(service.ACTIVE)).count()==1
                with pytest.raises(HTTPException) as exc:service._owned(fresh,owner,'123',fact_id)
                assert exc.value.status_code==404
                with pytest.raises(HTTPException):service._run_metadata(fact,False)
                with pytest.raises(HTTPException):service.view(fact,fresh)
                fact.expires_at=datetime.utcnow()-timedelta(seconds=1);fresh.commit()
                service.cleanup(fresh,owner);fresh.commit();assert fresh.get(Run,fact_id) is not None
                # Strict quota at exactly the real job reservation proves the
                # private fact contributes nothing to quota/eviction accounting.
                monkeypatch.setattr(service,'OWNER_QUOTA',service.MAX_RESULT_BYTES)
                with service.owner_write(fresh,owner):
                    reserving=fresh.get(Run,active['id']);reserving.status='cancelled';fresh.flush()
                    service._reserve(fresh,owner,retry_run=reserving)
                    fresh.rollback() # quota probe never changes the unrelated job
                assert fresh.get(Run,fact_id) is not None
                for call in [lambda:service.catalog(fresh,owner,'123'),lambda:service.export(fresh,owner),lambda:service.read_run(fresh,owner,'123',fact_id,0,1000)]:
                    with pytest.raises(HTTPException) as exc:call()
                    assert exc.value.detail=='DFA_RESTORE_REPLAY_UNAVAILABLE'
                assert fresh.query(Run).filter_by(user_id=owner,progress=service._NATIVE_BOOKKEEPING).count()==1
        with factory() as db:
            service.reconcile_source_integrity(db)
            assert db.query(Run).filter_by(user_id=owner,snapshot_id=bad_ref['snapshot_id']).count()==0
            assert db.get(Confirmation,proof['id']) is None
            other=db.get(Run,active['id']);assert (other.status,other.generation,other.rights_generation,other.retained_bytes,other.lease_token)==before
            assert service.catalog(db,owner,'123')['latest_run'] is None
    finally:event.remove(factory.class_,'before_flush',terminal_on_flush)


def test_rejected_correct_generation_retry_keeps_original_run_authority_after_negative_commit(store,monkeypatch):
    factory,owner=store;raw=partial_name_fit([b'HRM-Pro Plus\x00',b'different native model\x00'])
    proof,run=legacy_confirmed(factory,owner,raw,monkeypatch,complete=False)
    with factory() as db:
        cancelled=service.change_run(db,owner,'123',run['id'],'cancel')
        assert db.get(Run,run['id']).rights_generation==0
        # Catalog's old metadata-only path before the integrity observation: keep
        # source validation deferred only until explicit reauthorization is done.
        revision=core.digest(service._inputs(db,owner,'123'))
        current=auto.receipt_view(db,owner,'123')['rights_generation']
        reauthorized=auto.reauthorize(db,owner,'123',revision,current)
        assert reauthorized['rights_generation']==2
        with monkeypatch.context() as outage:
            outage.setattr(storage,'request',lambda *a:(_ for _ in ()).throw(storage.StorageError('journal offline')))
            with pytest.raises(HTTPException) as exc:
                service.change_run(db,owner,'123',run['id'],'retry',cancelled['generation'],reauthorized['rights_generation'])
            assert exc.value.detail=='DFA_RETRY_CHANGED'
            db.rollback()
    service._NATIVE_SUMMARIES.clear()
    with factory() as fresh:
        rejected=fresh.get(Run,run['id'])
        assert rejected.rights_generation==0
        assert rejected.status=='unavailable' and rejected.progress==service._NATIVE_PENDING
        assert rejected.error_code=='source_contradiction'
        assert rejected.generation==cancelled['generation']+1
        assert fresh.get(Rights,(owner,'123')).generation==2 and not fresh.get(Rights,(owner,'123')).suppressed
        assert fresh.query(Run).filter(Run.status.in_(service.ACTIVE)).count()==0
        assert fresh.get(service.Slot,1).run_id is None
        assert rejected.result is None # no computation ever occurred; negative survives rollback
