"""Public first-decision transport against the actual supervisor method.

Declared local state only: these tests do not prove SQL renewal or service.
"""
import threading
import time

import pytest
from api.dfa_supervisor import Supervisor
from tests.dfa_boundary_evidence import RenewalDecision


def transport(monkeypatch):
    # No engine, physical actor or cleanup identity overrides.
    sup = Supervisor.__new__(Supervisor)
    sup.lock = threading.RLock()
    sup.identity = {'epoch': '1'}
    sup.renewal_phase = 1
    sup.permission_decision = None
    sup.allowed = False
    sup.permission_until = 0.
    return sup, RenewalDecision(sup, monkeypatch)


def deliver(sup, job, reason):
    with sup.lock:
        value = sup._decision(job, reason)
        sup.permission_decision = value
        sup.allowed = reason is None
        sup.permission_until = time.monotonic() + 1 if sup.allowed else 0.
    return value


@pytest.mark.parametrize('reason', [None, 'permission', 'permission_expired'])
def test_first_public_snapshot_without_positive_wait(monkeypatch, reason):
    sup, observation = transport(monkeypatch)
    job = {'id': 'transport-job', 'generation': 1, 'epoch': '1', 'input': 'synthetic'}
    assert observation.first_decision() is None and observation.observation is None
    observation.arm()
    assert observation.first_decision() is None
    actual = deliver(sup, job, reason)
    first = observation.first_decision()
    assert first['reason'] == reason and first['job'] == job
    assert observation.observation == first
    actual['job']['generation'] = 9
    first['job']['generation'] = 10
    assert observation.first_decision()['job']['generation'] == 1
    deliver(sup, dict(job, id='later'), None)
    assert observation.first_decision()['job']['id'] == 'transport-job'
    # A different current decision must refuse a positive wait even if allowed.
    with pytest.raises(AssertionError): observation.wait()
    assert observation.first_decision()['reason'] == reason
    observation.arm()
    assert observation.first_decision() is None
    deliver(sup, dict(job, id='new-attempt'), None)
    observation.wait()
    assert observation.first_decision()['job']['id'] == 'new-attempt'


@pytest.mark.parametrize('invalid', ['denial', 'not_allowed', 'expired', 'wrong_current'])
def test_positive_wait_remains_strict(monkeypatch, invalid):
    sup, observation = transport(monkeypatch)
    observation.arm()
    deliver(sup, None, 'permission' if invalid == 'denial' else None)
    if invalid == 'not_allowed': sup.allowed = False
    if invalid == 'expired': sup.permission_until = time.monotonic() - 1
    if invalid == 'wrong_current': sup.permission_decision = dict(sup.permission_decision, phase=2)
    with pytest.raises(AssertionError): observation.wait()
    assert observation.first_decision() is not None


def test_first_exception_is_unavailable_and_forwarded_then_rearm(monkeypatch):
    sup, _ = transport(monkeypatch)
    original = RuntimeError('PRIVATE_CANARY')
    failing = [True]
    def failure(*args, **kwargs):
        if failing[0]: raise original
        return Supervisor._decision(sup, *args, **kwargs)
    monkeypatch.setattr(sup, '_decision', failure)
    observation = RenewalDecision(sup, monkeypatch)
    observation.arm()
    with pytest.raises(RuntimeError) as raised: sup._decision(None, None)
    assert raised.value is original
    assert observation.event.is_set() and observation.first_decision() is None
    assert observation.decision_error == 'RuntimeError'
    with pytest.raises(AssertionError) as refused: observation.wait()
    assert 'PRIVATE_CANARY' not in str(refused.value)
    # A subsequent successful call cannot replace a first exception.
    failing[0] = False
    deliver(sup, None, None)
    assert observation.first_decision() is None
    observation.arm()
    assert observation.decision_error is None
    deliver(sup, None, None)
    observation.wait()
    assert observation.first_decision()['reason'] is None
