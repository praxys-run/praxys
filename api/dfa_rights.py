"""Exact immutable origin bindings and independently persisted negative authority."""
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from analysis.activity_dfa import METHOD_VERSION, POLICY_PARAMETER_DIGEST, digest
from api import activity_dfa_storage as storage
from db.models import (User, UserConnection, TermsAcceptanceReceipt, ActivityDFAOriginGrant,
                       ActivityDFASyncGrant, ActivityDFASyncReceipt)


def processing_receipt(db: Session, owner: str) -> str:
    from api.legal import TERMS_VERSION, TERMS_CONTENT_DIGEST
    from api.legal_receipts import user_background_processing_authorized, TERMS_ACCEPTANCE_ACTION
    user = db.query(User).filter_by(id=owner, is_active=True, is_demo=False).first()
    if user is None or not user_background_processing_authorized(db, owner):
        raise HTTPException(403, 'DFA_PROCESSING_NOT_AUTHORIZED')
    from api.channel_processing_authority import user_channels_processing_authorized
    if not user_channels_processing_authorized(db, owner, lock_for_commit=True):
        raise HTTPException(403, 'DFA_PROCESSING_NOT_AUTHORIZED')
    receipt = db.query(TermsAcceptanceReceipt).filter_by(user_id=owner, terms_version=TERMS_VERSION,
        terms_digest=TERMS_CONTENT_DIGEST, action=TERMS_ACCEPTANCE_ACTION).order_by(TermsAcceptanceReceipt.accepted_at.desc()).first()
    if receipt is None:
        raise HTTPException(403, 'DFA_EXPLICIT_PROCESSING_RECEIPT_REQUIRED')
    return receipt.id


def automatic_gate(db: Session, owner: str) -> bool:
    # Automatic numeric disclosure also requires a recognized current ON,
    # while manual history remains independent of computation mode.
    return account_mode(db, owner) == 'automatic'


def account_mode(db: Session, owner: str) -> str:
    from api.statsig_client import recognized_gate, get_statsig_user_for_account
    # A fresh mode read must never flush partially selected Run outcome fields
    # before their generation/status/input/epoch CAS. This is not a mode cache.
    with db.no_autoflush:
        value = recognized_gate('activity_dfa_automatic', get_statsig_user_for_account(
            db, user_id=owner, training_base=None, language=None))
    return 'automatic' if value is True else 'manual' if value is False else 'unavailable'


def require_manual_mode(db: Session, owner: str) -> None:
    mode = account_mode(db, owner)
    if mode == 'unavailable':
        raise HTTPException(503, 'DFA_MODE_UNAVAILABLE')
    if mode != 'manual':
        raise HTTPException(409, 'DFA_MANUAL_DISABLED_AUTO_MODE')


def execution_current(db: Session, run) -> bool:
    # Historical read authority is deliberately independent of compute mode.
    from api import activity_dfa as service
    return account_mode(db, run.user_id) == run.origin and service._current(db, run)


def current_sync_grant(db: Session, owner: str, account: str):
    connection = db.query(UserConnection).filter_by(user_id=owner, platform='garmin').first()
    if not connection or connection.status not in ('connected', 'error') or not connection.dfa_account_generation:
        raise HTTPException(403, 'DFA_SYNC_GRANT_REQUIRED')
    grant = db.query(ActivityDFASyncGrant).filter_by(user_id=owner, account_id=account,
        account_generation=connection.dfa_account_generation, connection_id=connection.id).first()
    if grant is None or grant.action != 'connect_activity_sync':
        raise HTTPException(403, 'DFA_SYNC_GRANT_REQUIRED')
    return grant


def binding(db: Session, owner: str, ref: dict, origin: str, contract: str,
            proof=None, completion=None, inventory=None) -> dict:
    receipt = processing_receipt(db, owner)
    if origin == 'manual':
        if storage.authority_state(owner)['epoch'] == 'missing':
            if db.query(ActivityDFAOriginGrant.id).filter_by(user_id=owner).first() or db.query(ActivityDFASyncGrant.id).filter_by(user_id=owner).first():
                raise HTTPException(503, 'DFA_AUTHORITY_RECONCILIATION_REQUIRED')
        storage.establish_for_explicit_manual_action(owner)
    value = {'owner': owner, 'recording': ref, 'origin': origin, 'processing_receipt': receipt,
             'method': METHOD_VERSION, 'parameters': POLICY_PARAMETER_DIGEST, 'contract': contract,
             'negative_revision': storage.authority_revision(owner, origin, ref, proof.id if proof else None)}
    if origin == 'manual':
        value.update(assurance='user_confirmed' if proof else None, confirmation_id=proof.id if proof else None,
                     confirmation_digest=proof.evidence_digest if proof else None,
                     statement_version=proof.statement_version if proof else None)
    elif origin == 'automatic':
        grant = current_sync_grant(db, owner, ref['account_id'])
        if (not automatic_gate(db, owner) or completion is None or inventory is None
                or completion.recording_ref != ref or completion.account_generation != grant.account_generation
                or completion.sync_grant_id != grant.id or completion.disposition not in ('pending','admitted','unchanged')):
            raise HTTPException(403, 'DFA_AUTOMATIC_UNAVAILABLE')
        value.update(assurance='metadata_inferred', sync_grant=grant.id,
                     account_generation=grant.account_generation, completion_id=completion.id,
                     completion_revision=completion.completion_revision, metadata=inventory)
    else:
        raise HTTPException(403, 'DFA_ORIGIN_INVALID')
    return value


def grant_current(db: Session, run) -> bool:
    grant = db.query(ActivityDFAOriginGrant).filter_by(id=run.grant_id, user_id=run.user_id, origin=run.origin).first()
    state = storage.authority_state(run.user_id)
    if state['epoch'] == 'missing' or state['deleted']:
        return False
    if any(e['scope'] == 'run' and e['target'] == run.id and e['sequence'] > run.generation for e in state['events'].values()):
        return False
    if grant is None or grant.binding_digest != digest(grant.binding):
        return False
    try:
        from api.activity_dfa import require_policy, Confirmation
        from api.dfa_automatic import require_policy as automatic_policy
        contract = automatic_policy() if run.origin == 'automatic' else require_policy()
        if contract != run.science_contract_digest:
            return False
        proof = db.query(Confirmation).filter_by(id=run.confirmation_id, user_id=run.user_id).first() if run.confirmation_id else None
        completion = db.query(ActivityDFASyncReceipt).filter_by(id=grant.binding.get('completion_id'), user_id=run.user_id).first()
        current = binding(db, run.user_id, run.recording_ref, run.origin, contract, proof,
                          completion, grant.binding.get('metadata'))
        return current == grant.binding
    except (HTTPException, storage.StorageError):
        return False


def create_grant(db: Session, value: dict):
    """Conflict-safe insertion of a complete immutable origin binding."""
    from uuid import uuid4
    identity = digest(value)
    dialect = db.get_bind().dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise HTTPException(503, 'DFA_DATABASE_UNSUPPORTED')
    statement = insert(ActivityDFAOriginGrant).values(id=str(uuid4()), user_id=value['owner'],
        origin=value['origin'], binding_digest=identity, binding=value, created_at=datetime.utcnow())
    db.execute(statement.on_conflict_do_nothing(index_elements=['user_id','origin','binding_digest']))
    return db.query(ActivityDFAOriginGrant).filter_by(user_id=value['owner'], origin=value['origin'], binding_digest=identity).one()


def permanently_invalid(db: Session, run) -> bool:
    """Classify immutable invalidation; unavailable journals/gates never grant work."""
    from api import activity_dfa as service
    from api.legal import TERMS_VERSION, TERMS_CONTENT_DIGEST
    from api.legal_receipts import TERMS_ACCEPTANCE_ACTION
    try:
        user = db.query(User).filter_by(id=run.user_id).first()
        grant = db.query(ActivityDFAOriginGrant).filter_by(id=run.grant_id,user_id=run.user_id,origin=run.origin).first()
        if (user is None or not user.is_active or user.is_demo or run.freshness!='current'
                or grant is None or grant.binding_digest!=digest(grant.binding)):
            return True
        bound=grant.binding
        if bound.get('method')!=METHOD_VERSION or bound.get('parameters')!=POLICY_PARAMETER_DIGEST:
            return True
        state=storage.authority_state(run.user_id)
        if state['deleted']: return True
        if state['epoch']=='missing': return False
        if bound.get('negative_revision')!=storage.authority_revision(run.user_id,run.origin,run.recording_ref,run.confirmation_id):
            return True
        receipt=db.query(TermsAcceptanceReceipt).filter_by(user_id=run.user_id,
            terms_version=TERMS_VERSION,terms_digest=TERMS_CONTENT_DIGEST,action=TERMS_ACCEPTANCE_ACTION).order_by(TermsAcceptanceReceipt.accepted_at.desc()).first()
        if (receipt is None or receipt.id!=bound.get('processing_receipt')
                or user.terms_version!=TERMS_VERSION or user.terms_digest!=TERMS_CONTENT_DIGEST):
            return True
        inputs=service._inputs(db,run.user_id,run.activity_id)
        if not any(item['input']==run.recording_ref for item in inputs): return True
        if run.origin=='manual' and run.phase=='compute':
            proof=db.get(service.Confirmation,run.confirmation_id)
            if proof is None or not service.proof_current(proof,inputs): return True
        if run.origin=='automatic':
            sync=current_sync_grant(db,run.user_id,run.recording_ref['account_id'])
            completion=db.get(ActivityDFASyncReceipt,bound.get('completion_id'))
            if (sync.id!=bound.get('sync_grant') or sync.account_generation!=bound.get('account_generation')
                    or completion is None or completion.disposition not in ('admitted','unchanged','pending')):
                return True
        # A new active contract permanently supersedes this run. Inactive policy
        # or gate/channel unavailability instead defers it without blocking peers.
        try: contract=service.require_policy()
        except HTTPException: return False
        return contract!=run.science_contract_digest
    except HTTPException as exc:
        return exc.status_code<500
    except storage.StorageError:
        return False
