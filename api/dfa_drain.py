"""Authorized host-local drain; no placement handover or activation authority."""
from __future__ import annotations
import time
from db.models import ActivityDFAControl
from api.dfa_physical import Lane, PhysicalUnavailable, group_members


def drain(factory, lane: Lane, *, timeout_seconds: float = 10) -> dict:
    """Fence both origins, then observe the matching physical exit receipt."""
    if not 0 < timeout_seconds <= 60:
        raise ValueError('Invalid drain observation bound')
    with factory() as db:
        row = db.query(ActivityDFAControl).filter_by(id=1).with_for_update().first()
        if row is None or row.incarnation != lane.incarnation:
            raise PhysicalUnavailable('host_not_bound')
        row.drained = True
        row.enabled = False
        row.ready_until = None
        db.commit()
    earliest = time.monotonic() + 1.25
    deadline = time.monotonic() + timeout_seconds
    while True:
        actor = lane.actor()
        with factory() as db:
            row = db.get(ActivityDFAControl, 1)
            acknowledged = row.actor
            closed = row.drained and not row.enabled and row.incarnation == lane.incarnation
        if (closed and time.monotonic() >= earliest and actor and actor.get('state') == 'idle'
                and acknowledged == actor and not group_members(actor['identity']['pgid'])):
            return {'drained': True, 'exit_verified': True, 'activation': False}
        if closed and time.monotonic() >= earliest and actor is None and acknowledged is None:
            return {'drained': True, 'exit_verified': True, 'activation': False}
        if time.monotonic() >= deadline:
            raise PhysicalUnavailable('drain_exit_unproved')
        time.sleep(.05)


def main() -> None:
    """Run only in the separately authorized bound execution environment."""
    import json
    import os
    from pathlib import Path
    from api.dfa_supervisor import incarnation
    from db import session
    identity = incarnation()
    lane = Lane(Path('/tmp') / ('praxys-dfa-' + str(os.getuid()) + '-' + identity['incarnation']), identity)
    session.init_db()
    try:
        print(json.dumps(drain(session.SessionLocal, lane), sort_keys=True))
    finally:
        lane.close()


if __name__ == '__main__':
    main()
