"""Explicit restore reconciliation. Never a grant, sync event or host handover."""
from db.models import ActivityDFAControl, User, UserConnection, ActivityDFASyncGrant
from api import activity_dfa_storage as storage


def prepare_restored_database(db):
    """Operators must call this before reopening a restored API or compute lane."""
    control=db.query(ActivityDFAControl).filter_by(id=1).with_for_update().first()
    if control:
        control.enabled=False;control.drained=True;control.ready_until=None
        control.epoch+=1
    db.commit()
    owners=[row[0] for row in db.query(User.id).all()]
    for owner in owners:
        state=storage.authority_state(owner)
        if state['deleted']:
            from api.account_deletion import delete_user_account
            # Replay an acknowledged prior account deletion unconditionally;
            # this is not a new last-admin deletion request.
            delete_user_account(db,owner,enforce_last_admin_guard=False)
        else:
            storage.record_negative(owner,'restore','owner',owner)
            from api.activity_dfa import ensure_replayed
            ensure_replayed(db,owner)
            from api.activity_dfa import _erase
            from datetime import datetime
            _erase(db, {'user_id':owner,'scope':'owner','target_id':owner,'requested_at':datetime.max.isoformat()})
            db.query(ActivityDFASyncGrant).filter_by(user_id=owner).delete(synchronize_session=False)
            db.query(UserConnection).filter_by(user_id=owner,platform='garmin').update(
                {UserConnection.dfa_account_generation:None},synchronize_session=False)
            db.commit()
    # Restored origin grants cannot match the fresh independent journal epoch.
    # The existing bound incarnation is retained as history, never replaced here.
    return {'drained':True,'reconciled_owners':len(owners),'activation':False}


def main():
    from db import session
    session.init_db()
    with session.SessionLocal() as db:
        prepare_restored_database(db)


if __name__=='__main__':main()
