"""Real Linux processes with synthetic handshake input; no athlete payloads."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from api.dfa_physical import Lane, PhysicalUnavailable, group_members, worker_environment


IDENTITY = {"resource": "synthetic", "slot": "test", "instance": "fixture", "source": "fixture",
            "incarnation": "fixture", "epoch": 1, "boot": "fixture", "namespace": "fixture"}


def test_real_child_exclusion_and_exit_before_reuse(tmp_path):
    lane = Lane(tmp_path / 'lane', IDENTITY)
    actor, child = lane.launch({'epoch': 1, 'generation': 1, 'input': 'synthetic'}, authorized=True)
    assert actor['process_start_observed_at'] >= actor['launch_at']
    assert group_members(child.pid)
    other = Lane(tmp_path / 'lane', IDENTITY)
    with pytest.raises(PhysicalUnavailable, match='physical_guard_occupied'):
        other.acquire()
    before = time.monotonic()
    lane.retire(actor)
    assert time.monotonic() - before < 5
    assert not group_members(child.pid)
    assert lane.actor()['exit_observed_at'] >= actor['launch_at']
    lane.close()
    other.acquire()
    other.close()


def test_crashed_parent_inherited_lock_recovery_order(tmp_path):
    directory = tmp_path / 'lane'
    code = '''
import json, os, sys
from pathlib import Path
from api.dfa_physical import Lane
lane=Lane(Path(sys.argv[1]),json.loads(sys.argv[2]))
lane.launch({'epoch':1,'generation':1,'input':'synthetic'},authorized=True)
os._exit(0)
'''
    subprocess.run([sys.executable, '-c', code, str(directory), __import__('json').dumps(IDENTITY)], check=True)
    lane = Lane(directory, IDENTITY)
    old = lane.actor()['identity']['pid']
    assert group_members(old)
    with pytest.raises(PhysicalUnavailable, match='physical_guard_occupied'):
        lane.acquire()
    lane.recover(authorized=True)
    assert not group_members(old)
    assert lane.actor()['state'] == 'idle'
    lane.close()


def test_identity_change_unacknowledged_launch_and_disabled_start(tmp_path):
    lane = Lane(tmp_path / 'lane', IDENTITY)
    with pytest.raises(PhysicalUnavailable, match='launch_not_authorized'):
        lane.launch({}, authorized=False)
    lane.record({'incarnation': IDENTITY, 'state': 'launching', 'identity': None})
    with pytest.raises(PhysicalUnavailable, match='unacknowledged_launch'):
        lane.recover(authorized=True)
    lane.close()
    changed = Lane(tmp_path / 'lane', {**IDENTITY, 'incarnation': 'new'})
    with pytest.raises(PhysicalUnavailable, match='incarnation_changed'):
        changed.recover(authorized=True)
    changed.close()
    with lane.recovery_mutex():
        with pytest.raises(PhysicalUnavailable, match='recovery_busy'):
            lane.recover(authorized=True)


def test_child_environment_explicit_allowlist(monkeypatch):
    for key in ['DATABASE_URL','JWT_SECRET','AZURE_CLIENT_SECRET','GARMIN_PASSWORD','STATSIG_SDK_KEY']:
        monkeypatch.setenv(key, 'synthetic')
    assert set(worker_environment()) <= {'PATH','LANG','LC_ALL','TZ','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'}
