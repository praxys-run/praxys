"""Synthetic projected-active integration; real child math, isolated origin grants."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import numpy as np
import pytest

from api import activity_dfa as service, dfa_rights
from analysis import science_artifacts as artifacts
from db.models import (UserConnection, ActivityDFASyncGrant, ActivityDFASyncReceipt,
    GarminFitSnapshot, GarminConnectIQJob, GarminConnectIQItem, ActivityDFARun, ActivityDFAOriginGrant)
from db import sync_writer
from tests.test_activity_dfa import store, synthetic_fit, confirmed, reference
from tests.dfa_supervisor_harness import install, IDENTITY
from api.dfa_supervisor import Supervisor

REAL_POLICY = service.require_policy


@pytest.fixture
def both_origins(store, monkeypatch, tmp_path):
    from analysis.evidence_registry import load_science_registry
    from analysis.science_activation import project_active_registry
    from scripts.check_projected_dfa_policy import synthetic_v2_registry
    root=Path(__file__).resolve().parents[1]
    registry=load_science_registry(root/'data/science')
    expected=artifacts.build_policy_contract(project_active_registry(registry,'sdr-activity-dfa-alpha1-v2'),'sdr-activity-dfa-alpha1-v2').contract_digest
    factory,owner=store
    monkeypatch.setattr(service,'require_policy',REAL_POLICY)
    with synthetic_v2_registry(root,'projected-active',expected) as (science,contract):
        monkeypatch.setattr(artifacts,'_SCIENCE_DIR',science)
        with factory() as db:
            old=db.query(GarminFitSnapshot).filter_by(user_id=owner).first()
            raw=synthetic_fit(transport=True)
            snapshot=sync_writer.write_garmin_fit_snapshot(owner,'account','123',raw,db)
            sync_writer.write_garmin_fit_parse(snapshot,db)
            old_id=old.id
            # Only fixture setup removes the manual legacy archive alternative.
            from db.models import GarminFitParse, GarminFitChunk
            parses=[v[0] for v in db.query(GarminFitParse.id).filter_by(snapshot_id=old_id)]
            db.query(GarminFitChunk).filter(GarminFitChunk.parse_id.in_(parses)).delete(synchronize_session=False)
            db.query(GarminFitParse).filter_by(snapshot_id=old_id).delete(synchronize_session=False)
            db.delete(old)
            service.storage.record_negative(owner,'account_generation_replaced','origin','automatic')
            connection=UserConnection(user_id=owner,platform='garmin',status='connected',dfa_account_generation=str(uuid4()))
            db.add(connection);db.flush()
            grant=ActivityDFASyncGrant(user_id=owner,account_id='account',account_generation=connection.dfa_account_generation,
                connection_id=connection.id,action='connect_activity_sync')
            db.add(grant);db.commit()
        yield factory,owner


def complete_unit(factory,owner,kind='daily',success=True,mode=True):
    factory.dfa_modes[owner] = mode  # Explicit automatic-mode synthetic sync.
    with factory() as db:
        job=GarminConnectIQJob(user_id=owner,account_id='account',credential_generation='synthetic',region='international',kind=kind)
        db.add(job);db.flush()
        item=GarminConnectIQItem(user_id=owner,job_id=job.id,activity_id='123',status='complete' if success else 'parse_failed')
        db.add(item);db.flush()
        snapshots=db.query(GarminFitSnapshot).filter_by(user_id=owner).all()
        sync_writer.write_dfa_sync_completion(db,job,item,snapshots)
        sync_writer.write_dfa_sync_completion(db,job,item,snapshots)
        db.commit()


def test_duplicate_partial_backfill_and_independent_raw_results(both_origins,monkeypatch,tmp_path):
    factory,owner=both_origins
    complete_unit(factory,owner,kind='backfill')
    complete_unit(factory,owner,success=False)
    with factory() as db: assert db.query(ActivityDFASyncReceipt).count()==0
    complete_unit(factory,owner)
    with factory() as db: assert db.query(ActivityDFASyncReceipt).count()==1
    supervisor=Supervisor(factory,factory,IDENTITY,tmp_path/'automatic-physical')
    supervisor.allowed=True
    import time
    supervisor.permission_until=time.monotonic()+3600
    try:
        supervisor.admit_completion()
        with factory() as db:
            auto=db.query(ActivityDFARun).filter_by(origin='automatic').one()
            assert auto.confirmation_id is None
            auto_id=auto.id
        # Use the same real supervisor step harness for both independent origins.
        with factory() as db: claimed=service.claim(db)
        service.execute(factory,*claimed)
        proof,manual=confirmed(factory,owner)
        with factory() as db: claimed=service.claim(db)
        service.execute(factory,*claimed)
        factory.dfa_modes[owner] = True  # History keeps independent origins after sequential execution.
        with factory() as db:
            auto=service.read_run(db,owner,'123',auto_id,0,1000)
            manual=service.read_run(db,owner,'123',manual['id'],0,1000)
            assert auto['source_assurance']=='metadata_inferred'
            assert manual['source_assurance']=='user_confirmed'
            assert auto['windows']==manual['windows']
            assert auto['id']!=manual['id']
            grants=db.query(ActivityDFAOriginGrant).filter_by(user_id=owner).all()
            assert {'manual','automatic'}=={g.origin for g in grants}
            raw=np.random.default_rng(18).integers(480,521,650).tolist()
            for origin in (auto,manual):
                for window in origin['windows']:
                    if window['alpha1'] is not None:
                        rr=raw[window['rr_index_start']:window['rr_index_end']+1]
                        assert abs(window['alpha1']-reference(rr))<=1e-9
            monkeypatch.setattr(dfa_rights,'automatic_gate',lambda db,owner:False)
            denied=service.read_run(db,owner,'123',auto_id,0,1000)
            assert 'windows' not in denied and denied['freshness']=='stale'
            retained=service.read_run(db,owner,'123',manual['id'],0,1000)
            assert retained['windows']
            from fastapi import HTTPException
            with pytest.raises(HTTPException): service.context(db,owner,'123',auto_id,0,1000,auto['result_revision'],None)
    finally:
        supervisor.lane.close()
