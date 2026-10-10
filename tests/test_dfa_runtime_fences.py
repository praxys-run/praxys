"""Real-process recovery and independent journal/restore fences, synthetic only."""
from datetime import datetime
import time
import pytest
from api import activity_dfa as service
from api.dfa_physical import PhysicalUnavailable, group_members
from db.models import ActivityDFAControl, ActivityDFARun, ActivityDFAOriginGrant, ActivityDFASyncReceipt
from tests.test_activity_dfa import store, confirmed


def test_recovery_commits_exit_before_requeue(store):
    factory, owner = store
    _, run = confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    with factory() as db:
        job = supervisor.acquire_job()
    actor, child = supervisor.lane.launch({k: job[k] for k in ('generation','epoch','input')}, authorized=True)
    with factory() as db:
        db.get(ActivityDFAControl, 1).actor = actor
        db.commit()
    assert group_members(child.pid)
    supervisor.reconcile_recovery()
    assert not group_members(child.pid)
    with factory() as db:
        assert db.get(ActivityDFAControl, 1).actor['state'] == 'idle'
        assert db.get(ActivityDFARun, run['id']).status == 'failed'


def test_missing_local_actor_blocks_recovery(store):
    factory, _ = store
    supervisor = factory.dfa_supervisor
    with factory() as db:
        db.get(ActivityDFAControl, 1).actor = {'state':'occupied','actor_token':'synthetic-missing'}
        db.commit()
    with pytest.raises(PhysicalUnavailable, match='recovery_actor_missing'):
        supervisor.reconcile_recovery()


def test_restore_advances_independent_epoch_and_discards_authority(store):
    from api.dfa_restore import prepare_restored_database
    factory, owner = store
    _, run = confirmed(factory, owner)
    before = service.storage.authority_state(owner)
    with factory() as db:
        old_epoch = db.get(ActivityDFAControl, 1).epoch
        assert db.query(ActivityDFAOriginGrant).count()
        outcome = prepare_restored_database(db)
        assert outcome['activation'] is False
        control = db.get(ActivityDFAControl, 1)
        assert control.epoch == old_epoch + 1 and control.drained and not control.enabled
        assert not db.query(ActivityDFAOriginGrant).count()
        assert not db.query(ActivityDFASyncReceipt).count()
        assert db.get(ActivityDFARun, run['id']) is None
    after = service.storage.authority_state(owner)
    assert after['epoch'] != before['epoch'] and after['sequence'] > before['sequence']


def test_negative_event_survives_sql_rollback_and_never_lowers_revision(store):
    factory, owner = store
    _, run = confirmed(factory, owner)
    with factory() as db:
        assert service._current(db, db.get(ActivityDFARun, run['id']))
        acknowledged = service.storage.record_negative(owner, 'processing_withdrawn', 'origin', 'manual')
        db.rollback()
    with factory() as db:
        assert not service._current(db, db.get(ActivityDFARun, run['id']))
    assert service.storage.authority_state(owner)['sequence'] == acknowledged['sequence']


def test_expired_permission_retires_while_renewal_is_blocked(store, monkeypatch):
    import subprocess
    import threading
    factory, owner = store
    _, run = confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    original = subprocess.Popen
    def blocked_child(command, **kwargs):
        if command[-2:] == ['-m','api.dfa_worker']:
            command = [command[0], '-E', '-B', '-c',
                'import signal,sys,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);sys.stdin.buffer.readline();time.sleep(30)']
        return original(command, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', blocked_child)
    release = threading.Event()
    def stalled_renewal():
        release.wait(10)
    monkeypatch.setattr(supervisor, 'renew', stalled_renewal)
    supervisor.allowed = True
    supervisor.permission_until = time.monotonic() + 1
    errors = []
    def run_supervisor():
        try: supervisor.run()
        except Exception as exc: errors.append(exc)
    thread = threading.Thread(target=run_supervisor)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while True:
            actor = supervisor.lane.actor()
            if actor and actor['state'] == 'idle' and actor.get('exit_observed_at', 0) > supervisor.permission_until:
                assert not group_members(actor['identity']['pgid'])
                assert time.monotonic() < deadline
                break
            assert time.monotonic() < deadline, errors
            time.sleep(.01)
    finally:
        supervisor.stop.set()
        release.set()
        thread.join(5)
        assert not thread.is_alive()
    assert not errors


def test_drain_timeout_keeps_both_origin_fence_and_occupied_actor(store):
    from api.dfa_drain import drain
    factory, _ = store
    supervisor = factory.dfa_supervisor
    actor, child = supervisor.lane.launch({'epoch':'1','generation':1,'input':'synthetic'}, authorized=True)
    with factory() as db:
        db.get(ActivityDFAControl, 1).actor = actor
        db.commit()
    try:
        with pytest.raises(PhysicalUnavailable, match='drain_exit_unproved'):
            drain(factory, supervisor.lane, timeout_seconds=.1)
        with factory() as db:
            control = db.get(ActivityDFAControl, 1)
            assert control.drained and not control.enabled and control.ready_until is None
            assert control.actor['state'] == 'occupied'
        assert group_members(child.pid)
    finally:
        supervisor.lane.retire()


def test_drain_receipt_requires_matching_sql_and_local_exit(store):
    from api.dfa_drain import drain
    factory, _ = store
    supervisor = factory.dfa_supervisor
    assert drain(factory, supervisor.lane) == {'drained':True,'exit_verified':True,'activation':False}


def test_live_unacknowledged_child_exit_over_idle_predecessor(store):
    factory, owner = store
    _, run = confirmed(factory, owner)
    supervisor = factory.dfa_supervisor
    job = supervisor.acquire_job()
    supervisor.active = job
    actor, child = supervisor.lane.launch({k:job[k] for k in ('generation','epoch','input')}, authorized=True)
    # Simulate acknowledgement checkout failure: SQL still holds the previous
    # idle preparation actor; the local journal and live job identify this child.
    supervisor.lane.retire(actor)
    assert not group_members(child.pid)
    supervisor.record_exit()
    with factory() as db:
        assert db.get(ActivityDFAControl, 1).actor['actor_token'] == actor['actor_token']
        assert db.get(ActivityDFAControl, 1).actor['state'] == 'idle'


@pytest.mark.parametrize('payload', [b'{"binding":1,"binding":2}', b'{"summary":{"supported_time_ratio":1e999}}', b'{"nested":[NaN]}'])
def test_private_ipc_rejects_duplicate_or_nested_nonfinite_payload(payload):
    from api import dfa_ipc
    with pytest.raises(dfa_ipc.IPCInvalid):
        dfa_ipc.loads(payload)


def test_deployment_blocks_enabled_candidate_before_first_recycling_mutation():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]/'.github/workflows/deploy-backend.yml').read_text()
    boundary = source.index('Require inactive DFA candidate before recycling configuration')
    mutation = source.index('az webapp config appsettings set')
    assert boundary < mutation
    assert 'contract[\'runtime_state\'] == \'inactive\'' in source[boundary:mutation]
    assert '--startup-file "python -m api.runtime_startup"' in source


def test_shared_channel_stop_fences_manual_when_local_environment_is_stale(store, monkeypatch):
    from db.models import TermsAcceptanceReceipt
    from api.channel_processing_authority import reconcile_channel_processing_authority
    factory, owner = store
    _, run = confirmed(factory, owner)
    monkeypatch.setenv('PRAXYS_DISABLE_MINIAPP_PROCESSING', 'false')
    with factory() as db:
        receipt = db.query(TermsAcceptanceReceipt).filter_by(user_id=owner).one()
        receipt.channel = 'wechat-miniapp'
        db.commit()
        reconcile_channel_processing_authority(db)
        db.commit()
        assert service._current(db, db.get(ActivityDFARun, run['id']))
    # A different API instance commits the shared stop, while this worker still
    # has its former local environment. Publication/read fencing uses the DB.
    monkeypatch.setenv('PRAXYS_DISABLE_MINIAPP_PROCESSING', 'true')
    with factory() as db:
        reconcile_channel_processing_authority(db)
        db.commit()
    monkeypatch.setenv('PRAXYS_DISABLE_MINIAPP_PROCESSING', 'false')
    with factory() as db:
        assert not service._current(db, db.get(ActivityDFARun, run['id']))
