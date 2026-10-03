"""Metadata-only sync receipts. No gate evaluation, worker or RR hydration here."""
from hashlib import sha256
import json
from db.models import ActivityDFAReceipt, ActivityDFARightsState


def record_completion(db, owner: str, activity: str, provider: str, *, account: str | None = None, recording_ref: dict | None = None, event_key: str) -> ActivityDFAReceipt:
    identity = sha256(json.dumps([owner,activity,provider,account,recording_ref,event_key],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    receipt = db.query(ActivityDFAReceipt).filter_by(user_id=owner,event_digest=identity).first()
    if receipt:
        return receipt
    state = db.get(ActivityDFARightsState,(owner,activity))
    owner_state = db.get(ActivityDFARightsState,(owner,''))
    receipt = ActivityDFAReceipt(user_id=owner,activity_id=activity,provider=provider,account_id=account,
        recording_ref=recording_ref,event_digest=identity,rights_generation=state.generation if state else 0,
        status='suppressed' if owner_state and owner_state.suppressed or state and state.suppressed else 'pending')
    db.add(receipt)
    db.info['dfa_completion_pending'] = True
    return receipt
