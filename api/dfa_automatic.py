"""Conditional receipt admission and minimal activity rights generations."""
from datetime import datetime
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import defer
from db.models import (ActivityDFAReceipt as Receipt, ActivityDFAMetadataProof as MetadataProof,
                       ActivityDFARightsState as RightsState, ActivityDFARun as Run)
from analysis.activity_dfa import METHOD_VERSION, SOURCE_VERSION, GARMIN_ECG, digest
from analysis.dfa_source import (AUTO_SDR_ID, FROZEN_NUMERICAL_DIGEST, SOURCE_RULE_VERSION,
                                 METADATA_PROJECTION_VERSION, source_inventory)

# Empty activity keys cannot be addressed by an activity URL. The existing
# rights table uses that reserved key for a payload-free owner erasure fence.
OWNER_RIGHTS_KEY = ''
GATE = 'dfa_alpha1_auto_analysis_enabled'
WAITING = ('pending','deferred','gate_paused','science_inactive','processing_unavailable','queued','running')


def enabled(db, owner: str) -> bool:
    try:
        from api.statsig_client import check_gate, get_statsig_user_for_account
        identity = get_statsig_user_for_account(db,user_id=owner,training_base=None,language=None)
        return check_gate(GATE,identity)
    except Exception:
        return False


def require_policy() -> str:
    from analysis.science_artifacts import load_policy_contract
    try:
        contract = load_policy_contract(AUTO_SDR_ID, require_active=True)
        parameters = {key:value.value for key,value in contract.parameters.items()}
        frozen = {key:parameters[key] for key in ('window','rr_quality','time_alignment','dfa','context')}
        if (contract.model_version != METHOD_VERSION or digest(frozen) != FROZEN_NUMERICAL_DIGEST
                or digest(parameters) != '7085fa6e244569be475e6908576d0abfc63f957c8fdda73a52d24488b08718a3'):
            raise ValueError('automatic branch contract mismatch')
        return contract.contract_digest
    except Exception as exc:
        raise HTTPException(503,'DFA_AUTO_SCIENCE_POLICY_INACTIVE') from exc


def require_authority(db, owner: str) -> str:
    from api.legal_receipts import user_background_processing_authorized
    from db.models import User
    require_owner_rights(db,owner)
    user = db.get(User,owner)
    if not user or not user.is_active or user.is_demo or not user_background_processing_authorized(db,owner):
        raise HTTPException(403,'DFA_PROCESSING_NOT_AUTHORIZED')
    return require_policy()


def state(db, owner: str, activity: str, *, create=False):
    value = db.get(RightsState,(owner,activity))
    if value is None and create:
        value = RightsState(user_id=owner,activity_id=activity,generation=0,suppressed=False,reason='initial')
        db.add(value); db.flush()
    return value


def owner_erased(db, owner: str) -> bool:
    value = state(db,owner,OWNER_RIGHTS_KEY)
    return bool(value and value.suppressed)


def require_owner_rights(db, owner: str) -> None:
    if owner_erased(db,owner):
        raise HTTPException(403,'DFA_OWNER_ERASED')


def suppress_owner_locked(db, owner: str) -> None:
    """Irreversible owner fence; replay needs no result/blob hydration."""
    from db.models import User
    from api import activity_dfa as service
    # A real account deletion cascades this SQL fence. Its durable owner marker
    # recreates it before a restored account can admit/read/export anything.
    if db.get(User,owner) is None:
        return
    value=state(db,owner,OWNER_RIGHTS_KEY,create=True)
    value.generation=max(1,value.generation);value.suppressed=True
    value.reason='account_deletion';value.changed_at=datetime.utcnow()
    for activity_state in db.query(RightsState).filter(RightsState.user_id==owner,RightsState.activity_id!=OWNER_RIGHTS_KEY).all():
        if not activity_state.suppressed:
            activity_state.generation+=1
        activity_state.suppressed=True;activity_state.reason='account_deletion'
    # Fence even work restored/created AFTER the original cutoff; retained
    # result columns are deliberately deferred for this metadata-only operation.
    for run in db.query(Run).options(defer(Run.result)).filter_by(user_id=owner).all():
        if run.status in service.ACTIVE+('gate_paused',) or run.result_revision is not None:
            run.generation+=1
        run.status=run.progress='cancelled';run.lease_token=run.lease_until=None
        run.result=run.result_revision=None;run.retained_bytes=0
        service._release_slot(db,run.id)
    db.query(Receipt).filter_by(user_id=owner).update(
        {Receipt.status:'suppressed',Receipt.reason:'account_deletion'},synchronize_session=False)


def require_expected_rights(db,owner,activity,expected):
    require_owner_rights(db,owner)
    value=state(db,owner,activity)
    generation=value.generation if value else 0
    if expected is None:
        if generation != 0:
            raise HTTPException(409,'DFA_RIGHTS_CHANGED')
    elif expected != generation:
        raise HTTPException(409,'DFA_RIGHTS_CHANGED')
    if value and value.suppressed:
        raise HTTPException(409,'DFA_ACTIVITY_SUPPRESSED')
    return generation


def rights_current(db, run) -> bool:
    value = state(db,run.user_id,run.activity_id)
    return not owner_erased(db,run.user_id) and not (value and (value.suppressed or value.generation != run.rights_generation))


def proof_current(db, run, candidates) -> bool:
    proof = db.query(MetadataProof).filter_by(id=run.metadata_proof_id,user_id=run.user_id,activity_id=run.activity_id).first()
    rules={digest([SOURCE_VERSION,1,product]) for product in GARMIN_ECG};rules.add(digest([SOURCE_VERSION,123,'h10']))
    candidates_valid=bool(proof and proof.candidates and all(candidate.get('rule_fingerprint') in rules and candidate.get('transport') in ('ANT+','BLE') for candidate in proof.candidates) and len({candidate['rule_fingerprint'] for candidate in proof.candidates})==1)
    return bool(candidates_valid and proof and proof.recording_ref == run.recording_ref and
        any(candidate['input']==proof.recording_ref for candidate in candidates) and
        proof.source_contract_digest==run.science_contract_digest and proof.source_rule_version==SOURCE_RULE_VERSION and
        proof.metadata_projection_version==METADATA_PROJECTION_VERSION and rights_current(db,run))


def pause(db, run, reason='gate_paused'):
    from api import activity_dfa as service
    run.status=run.progress='gate_paused';run.error_code=reason
    run.generation+=1;run.lease_token=run.lease_until=None;run.retained_bytes=0
    service._release_slot(db,run.id)
    db.query(Receipt).filter_by(user_id=run.user_id,run_id=run.id).update(
        {Receipt.status:'gate_paused',Receipt.reason:reason,Receipt.checked_at:datetime.utcnow()},synchronize_session=False)


def suppress_locked(db, owner, activity, reason, *, durable=True):
    from api import activity_dfa as service
    value=state(db,owner,activity,create=True)
    value.generation+=1;value.suppressed=True;value.reason=reason;value.changed_at=datetime.utcnow()
    manifest=None
    if durable:
        try:
            manifest=service.storage.request_rights(owner,activity,value.generation,True,reason)
        except service.storage.StorageError:
            # SQL fences cancellation immediately; no auto work while this durable
            # marker is pending. Reconciliation must persist it before resumption.
            value.reason='pending_'+reason
    for run in db.query(Run).options(defer(Run.result)).filter_by(user_id=owner,activity_id=activity,origin='automatic').all():
        run.generation+=1;run.lease_token=run.lease_until=None
        if run.status in service.ACTIVE+('gate_paused',):
            run.status=run.progress='cancelled';run.retained_bytes=0
        service._release_slot(db,run.id)
    db.query(Receipt).filter_by(user_id=owner,activity_id=activity).update(
        {Receipt.status:'suppressed',Receipt.reason:reason,Receipt.checked_at:datetime.utcnow()},synchronize_session=False)
    return value,manifest


def apply_rights(db, manifest):
    owner,activity,generation=manifest['user_id'],manifest['activity_id'],manifest['rights_generation']
    value=state(db,owner,activity,create=True)
    if generation < value.generation:
        return
    if generation==value.generation and value.suppressed==manifest['suppressed']:
        if value.reason.startswith('pending_'):
            value.reason=manifest['reason']
        return
    value.generation=generation;value.suppressed=manifest['suppressed'];value.reason=manifest['reason'];value.changed_at=datetime.fromisoformat(manifest['requested_at'])
    if value.suppressed:
        from api import activity_dfa as service
        for run in db.query(Run).options(defer(Run.result)).filter_by(user_id=owner,activity_id=activity,origin='automatic').all():
            if run.rights_generation <= generation:
                run.generation+=1;run.status=run.progress='cancelled';run.lease_token=run.lease_until=None;run.result=run.result_revision=None;run.retained_bytes=0
                service._release_slot(db,run.id)
        db.query(Receipt).filter(Receipt.user_id==owner,Receipt.activity_id==activity,Receipt.rights_generation<=generation).update(
            {Receipt.status:'suppressed',Receipt.reason:manifest['reason']},synchronize_session=False)


def reauthorize(db, owner, activity, catalog_revision, expected_generation):
    from api import activity_dfa as service
    service.ensure_replayed(db,owner)
    with service.owner_write(db,owner):
        service.require_authority(db,owner)
        candidates=service._inputs(db,owner,activity)
        value=state(db,owner,activity,create=True)
        if catalog_revision != digest(candidates) or expected_generation != value.generation or value.reason.startswith('pending_'):
            raise HTTPException(409,'DFA_RIGHTS_CHANGED')
        generation=value.generation+1
        try:
            manifest=service.storage.request_rights(owner,activity,generation,False,'reauthorized')
        except service.storage.StorageError as exc:
            raise HTTPException(503,'DFA_RIGHTS_STORAGE_UNAVAILABLE') from exc
        apply_rights(db,manifest)
        # This explicit manual action grants no automatic rescheduling or proof.
        db.commit();service._complete_manifest(manifest)
    return {'rights_generation':generation,'suppressed':False}


def receipt_view(db, owner, activity):
    receipt=db.query(Receipt).filter_by(user_id=owner,activity_id=activity).order_by(Receipt.created_at.desc(),Receipt.id.desc()).first()
    value=state(db,owner,activity)
    return {'gate_enabled':enabled(db,owner),'scheduled':receipt is not None,
        'receipt':{'id':receipt.id,'state':receipt.status,'reason':receipt.reason,'run_id':receipt.run_id,'generation':receipt.generation} if receipt else None,
        'suppressed':owner_erased(db,owner) or bool(value and value.suppressed),'rights_generation':value.generation if value else 0}


def reconcile(db, limit=20):
    from api import activity_dfa as service
    # Retry payload-free cancellation durability without weakening the SQL fence.
    pending=db.query(RightsState.user_id,RightsState.activity_id).filter(RightsState.reason.in_(('pending_cancelled','pending_withdrawal'))).limit(limit).all()
    db.rollback()
    for owner,activity in pending:
        try:
            with service.owner_write(db,owner):
                value=state(db,owner,activity)
                if value and value.reason.startswith('pending_'):
                    reason=value.reason.removeprefix('pending_')
                    manifest=service.storage.request_rights(owner,activity,value.generation,value.suppressed,reason)
                    value.reason=reason;db.commit();service._complete_manifest(manifest)
        except Exception:
            db.rollback()
    # Index-driven fair owner rotation, one receipt per owner per bounded tick.
    owners=db.query(Receipt.user_id,func.min(Receipt.checked_at).label('oldest')).filter(
        Receipt.status.in_(WAITING)).group_by(Receipt.user_id).order_by('oldest',Receipt.user_id).limit(limit).all()
    db.rollback()
    for owner,_ in owners:
        try:
            service.ensure_replayed(db,owner)
            with service.owner_write(db,owner):
                receipt=db.query(Receipt).filter(Receipt.user_id==owner,Receipt.status.in_(WAITING)).order_by(Receipt.checked_at,Receipt.created_at,Receipt.id).first()
                if not receipt:
                    continue
                receipt.checked_at=datetime.utcnow()
                value=state(db,owner,receipt.activity_id)
                if owner_erased(db,owner) or value and (value.suppressed or value.generation!=receipt.rights_generation):
                    receipt.status='suppressed';receipt.reason='activity_suppressed';db.commit();continue
                gate=enabled(db,owner)
                run=db.get(Run,receipt.run_id) if receipt.run_id else None
                if not gate:
                    if run and run.status in service.ACTIVE:
                        pause(db,run)
                    receipt.status='gate_paused';receipt.reason='gate_off';db.commit();continue
                try:
                    contract=require_authority(db,owner)
                except HTTPException as exc:
                    receipt.status='science_inactive' if exc.status_code==503 else 'processing_unavailable'
                    receipt.reason=exc.detail
                    if run and run.status in service.ACTIVE:
                        pause(db,run,receipt.status)
                    db.commit();continue
                if run:
                    if run.status=='gate_paused':
                        if not service._current(db,run):
                            receipt.status='stale';receipt.reason='input_changed'
                        else:
                            try:
                                service._reserve(db,owner,retry_run=run)
                                run.status=run.progress='queued';run.retained_bytes=service.MAX_RESULT_BYTES;run.error_code=None
                                receipt.status='queued';receipt.reason=None
                            except HTTPException as exc:
                                receipt.status='deferred';receipt.reason=exc.detail
                    else:
                        receipt.status=run.status;receipt.reason=run.error_code
                    db.commit();continue
                if receipt.provider!='garmin' or not receipt.recording_ref:
                    receipt.status='unavailable';receipt.reason='provider_unsupported' if receipt.provider!='garmin' else 'original_unavailable'
                    db.commit();continue
                try:
                    candidates=service._inputs(db,owner,receipt.activity_id)
                    if not any(c['input']==receipt.recording_ref for c in candidates):
                        receipt.status='stale';receipt.reason='input_changed';db.commit();continue
                    identity=digest([receipt.recording_ref,METHOD_VERSION,contract,'automatic','prepare',SOURCE_RULE_VERSION,METADATA_PROJECTION_VERSION,receipt.rights_generation])
                    run=db.query(Run).filter_by(user_id=owner,input_digest=identity).first()
                    if not run:
                        service._reserve(db,owner)
                        run=Run(user_id=owner,activity_id=receipt.activity_id,snapshot_id=receipt.recording_ref['snapshot_id'],parse_id=receipt.recording_ref['parse_id'],recording_ref=receipt.recording_ref,
                            input_digest=identity,method_version=METHOD_VERSION,science_contract_digest=contract,phase='prepare',origin='automatic',source_assurance='metadata_inferred',rights_generation=receipt.rights_generation,retained_bytes=service.MAX_RESULT_BYTES)
                        db.add(run);db.flush()
                    receipt.run_id=run.id;receipt.status=run.status;receipt.reason=None
                except HTTPException as exc:
                    receipt.status='deferred' if exc.status_code==429 else 'unavailable';receipt.reason=exc.detail
                db.commit()
        except Exception:
            db.rollback()  # durable receipt remains pending; no payload/owner log


def qualify(db, run, messages):
    """Global execution lease owns qualification; never runs in the sync writer."""
    from api import activity_dfa as service
    inventory=source_inventory(messages,run.recording_ref)
    if inventory['outcome']!='eligible_metadata_inferred':
        return inventory
    identity=digest([run.recording_ref,inventory['source_evidence_digest'],SOURCE_RULE_VERSION,METADATA_PROJECTION_VERSION,run.science_contract_digest])
    proof=db.query(MetadataProof).filter_by(user_id=run.user_id,identity_digest=identity).first()
    if not proof:
        proof=MetadataProof(user_id=run.user_id,activity_id=run.activity_id,snapshot_id=run.snapshot_id,parse_id=run.parse_id,recording_ref=run.recording_ref,
            identity_digest=identity,source_evidence_digest=inventory['source_evidence_digest'],source_rule_version=SOURCE_RULE_VERSION,metadata_projection_version=METADATA_PROJECTION_VERSION,source_contract_digest=run.science_contract_digest,candidates=inventory['candidates'])
        db.add(proof);db.flush()
    compute_identity=digest([run.recording_ref,METHOD_VERSION,run.science_contract_digest,'automatic','compute',proof.identity_digest,run.rights_generation])
    successor=db.query(Run).filter_by(user_id=run.user_id,input_digest=compute_identity).first()
    run.completed_at=datetime.utcnow()
    from datetime import timedelta
    run.expires_at=run.completed_at+timedelta(days=1)
    run.status=run.progress='unavailable';run.error_code='source_qualified';run.retained_bytes=0;run.lease_token=run.lease_until=None
    service._release_slot(db,run.id);db.flush()
    if not successor:
        service._reserve(db,run.user_id)
        successor=Run(user_id=run.user_id,activity_id=run.activity_id,snapshot_id=run.snapshot_id,parse_id=run.parse_id,recording_ref=run.recording_ref,input_digest=compute_identity,
            method_version=METHOD_VERSION,science_contract_digest=run.science_contract_digest,phase='compute',origin='automatic',source_assurance='metadata_inferred',metadata_proof_id=proof.id,
            rights_generation=run.rights_generation,retained_bytes=service.MAX_RESULT_BYTES)
        db.add(successor);db.flush()
    db.query(Receipt).filter_by(user_id=run.user_id,run_id=run.id).update({Receipt.run_id:successor.id,Receipt.status:successor.status,Receipt.reason:None},synchronize_session=False)
    return inventory
