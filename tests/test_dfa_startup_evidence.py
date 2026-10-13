"""Real shared Cell/latch failures must reach captured pytest/JUnit output."""
import json

import pytest

from db.models import ActivityDFAControl as Control
from tests.test_activity_dfa import store
from tests.test_dfa_origins import both_origins
from tests.test_dfa_finalization import Cell, wait_for
from tests.dfa_boundary_evidence import boundary_junit


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('cleanup_boundary',['dispose','snapshot'])
def test_first_real_denial_and_cleanup_error_keep_sanitized_evidence(
        both_origins,monkeypatch,tmp_path,capsys,cleanup_boundary):
    cell=Cell(both_origins,monkeypatch,tmp_path)
    actual_arm=cell.diagnostic.renewal.arm
    armed=[]
    def drain_then_arm():
        # Post-acquisition owner transaction has closed. Actual next renewal
        # sees the genuine durable drain; no permission value is injected.
        with cell.factory() as db:
            db.get(Control,1).drained=True
            db.commit()
        armed.append(True)
        actual_arm()
    monkeypatch.setattr(cell.diagnostic.renewal,'arm',drain_then_arm)
    actual_dispose=cell.engine.dispose
    try:
        cell.start()
        wait_for(lambda:bool(cell.errors))
        assert armed==[True]
        assert cell.diagnostic.renewal.first_decision()['reason']=='permission'
        assert not cell.sup.allowed and cell.target is None and not cell.launches
        assert not any(e['event']=='first_completed_renewal' for e in cell.diagnostic.events)
        with pytest.raises(AssertionError):cell.wait_error()
        def cleanup_error():raise RuntimeError('credential=SYNTHETIC_SECRET SQL_PARAMS raw_RR')
        if cleanup_boundary=='dispose':monkeypatch.setattr(cell.engine,'dispose',cleanup_error)
        else:monkeypatch.setattr(cell,'state',cleanup_error)
        with pytest.raises(RuntimeError):cell.close()
        assert not cell.monitor.thread.is_alive()
        assert all(not thread.is_alive() for thread in cell.renewals)
        output=capsys.readouterr().out
        line=next(line for line in output.splitlines() if line.startswith('DFA_BOUNDARY_EVIDENCE '))
        evidence=json.loads(line.split(' ',1)[1])
        assert any(e['event']=='setup_failed' for e in evidence['events'])
        assert evidence['target'] is None and evidence['finished'] is False
        assert evidence['primary_errors'] and evidence['cleanup_errors'][0]['class']=='RuntimeError'
        assert evidence['cleanup_errors'][0]['stack']
        assert all(secret not in output for secret in ('SYNTHETIC_SECRET','SQL_PARAMS','raw_RR',cell.owner,cell.admitted['id']))
        # Re-emit to the actual JUnit capture rather than leave only capsys data.
        print(line)
    finally:
        # Export even if setup assertions fail before the cleanup injection.
        cell.diagnostic.emit(target=cell.target, finished=cell.finished.is_set())
        cell.release_lock();cell.monitor.close()
        for thread in cell.renewals:thread.join(5)
        assert all(not thread.is_alive() for thread in cell.renewals)
        cell.sup.lane.retire();actual_dispose();cell.factory.kw['bind'].dispose()
