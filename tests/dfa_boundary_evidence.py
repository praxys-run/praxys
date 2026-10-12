"""Test-only first-decision barrier; real renewal owns every permission value."""
import threading
import time
import json
import pytest
from copy import deepcopy


class RenewalDecision:
    def __init__(self, supervisor, monkeypatch):
        self.supervisor = supervisor
        self.event = threading.Event()
        self.armed = False
        self.observation = None
        self.events = []
        actual = supervisor._decision

        def decision(job, reason, actor=None):
            value = actual(job, reason, actor)
            if self.armed:
                self.armed = False
                self.observation = deepcopy(value)
                self.events.append({'event': 'first_renewal_decision',
                                    'at': time.monotonic(), 'reason': reason,
                                    'phase': value['phase']})
                # _decision runs under the reactor state lock. The waiter takes
                # that lock after wakeup, after renewal assigns allowed/deadline.
                self.event.set()
            return value
        monkeypatch.setattr(supervisor, '_decision', decision)

    def arm(self):
        with self.supervisor.lock:
            self.event.clear()
            self.observation = None
            self.armed = True
            self.events.append({'event': 'barrier_armed', 'at': time.monotonic()})

    def wait(self):
        assert self.event.wait(2), self.events
        with self.supervisor.lock:
            value = deepcopy(self.observation)
            current = deepcopy(self.supervisor.permission_decision)
            allowed = self.supervisor.allowed
            deadline = self.supervisor.permission_until
        # A first denial fails this positive; never select a later favourable
        # cycle, manufacture permission, or extend the runtime lease.
        assert value['reason'] is None and allowed and current == value, self.events
        assert time.monotonic() < deadline, self.events
        self.events.append({'event': 'completed_renewal_observed',
                            'at': time.monotonic(), 'permission_until': deadline})


def safe_binding(value):
    """Exclude payloads and tokens while retaining immutable job association."""
    from hashlib import sha256
    if value is None:
        return None
    result = {key: value[key] for key in ('generation', 'epoch', 'input', 'origin', 'phase') if key in value}
    if 'id' in value:
        result['job'] = sha256(value['id'].encode()).hexdigest()
    if 'actor_token' in value:
        result['actor'] = sha256(value['actor_token'].encode()).hexdigest()
        result['binding'] = deepcopy(value.get('binding'))
        result['state'] = value.get('state')
        result['identity'] = deepcopy(value.get('identity'))
        for key in ('launch_at', 'process_start_observed_at', 'term_at', 'exit_observed_at'):
            result[key] = value.get(key)
    return result


class StartupEvidence:
    """Bounded test orchestration, never a natural availability measurement.

    The first acquisition returns only after ONE prospective real renewal.
    The owner transaction has already closed; no writer waits for itself.
    Diagnostic fields are explicitly selected, never arbitrary exception text.
    """
    def __init__(self, supervisor, monkeypatch):
        from api import dfa_rights
        from api.dfa_supervisor import SAFE_FAILURES
        self.supervisor = supervisor
        self.events, self.outcomes = [], []
        self.terminal_events = []
        self.primary_errors, self.cleanup_errors = [], []
        self.dropped = 0
        self.used = False
        self.renewal = RenewalDecision(supervisor, monkeypatch)
        actual_acquire = supervisor.acquire_job
        actual_finish = supervisor.finish
        actual_current = dfa_rights.execution_current
        actual_mode = dfa_rights.account_mode

        def acquire():
            job = actual_acquire()
            if job and not self.used:
                self.used = True
                self.note('acquisition_return', job=safe_binding(job))
                try:
                    assert str(job['epoch']) == str(supervisor.identity['epoch'])
                    self.renewal.arm()
                    self.renewal.wait()
                except BaseException as exc:
                    self.error(exc)
                    self.note('setup_failed', job=safe_binding(job),
                              first_decision=self.decision(self.renewal.observation))
                    raise
                self.note('first_completed_renewal', job=safe_binding(job),
                          decision=self.decision(self.renewal.observation),
                          actor=safe_binding(supervisor.lane.actor()))
            return job

        def current(db, run):
            started = time.monotonic()
            result = actual_current(db, run)
            self.note('execution_validation', started=started, current=result,
                      job=safe_binding({'id':run.id, 'generation':run.generation,
                                        'epoch':run.execution_epoch, 'origin':run.origin,
                                        'phase':run.phase}))
            return result

        def mode(db, owner):
            result = actual_mode(db, owner)
            self.note('account_mode_validation', owner=safe_binding({'id':owner}), mode=result)
            return result

        def finish(job, status, value):
            with supervisor.lock:
                decision = self.decision(supervisor.permission_decision)
                allowed, deadline = supervisor.allowed, supervisor.permission_until
            pending = supervisor.pending
            self.note('finish_entered', job=safe_binding(job), status=status,
                      reason=value if isinstance(value,str) and value in SAFE_FAILURES|{'mode_changed','mode_unavailable'} else None,
                      decision=decision, allowed=allowed, permission_until=deadline,
                      actor=safe_binding(supervisor.lane.actor()),
                      cancelled=pending.cancellation.is_set() if pending else None,
                      pending_status=pending.status if pending else None)
            try:
                result = actual_finish(job, status, value)
            except BaseException as exc:
                self.error(exc)
                raise
            self.note('finish_ack', job=safe_binding(job))
            return result

        monkeypatch.setattr(supervisor, 'acquire_job', acquire)
        monkeypatch.setattr(supervisor, 'finish', finish)
        monkeypatch.setattr(dfa_rights, 'execution_current', current)
        monkeypatch.setattr(dfa_rights, 'account_mode', mode)

    @staticmethod
    def decision(value):
        return None if value is None else {
            'at':value['at'], 'reason':value['reason'], 'phase':value['phase'],
            'job':safe_binding(value['job']), 'actor':safe_binding(value['actor'])}

    def note(self, event, **fields):
        value={'event':event, 'at':time.monotonic(), **deepcopy(fields)}
        if event in {'setup_failed','finish_entered','finish_ack','verified_target_exit',
                     'scheduling_fault_applied','predecessor_changed_after_read','runtime_finalization'}:
            # Reserve bounded space for immutable terminal observations even
            # if ordinary repeated validation records exhaust the trace limit.
            if len(self.terminal_events) < 32:self.terminal_events.append(value)
        if len(self.events) < 96:
            self.events.append(value)
        else:
            self.dropped += 1

    def error(self, exc, *, cleanup=False):
        from tests.dfa_capacity_worker import failure
        target = self.cleanup_errors if cleanup else self.primary_errors
        if len(target) < 4:
            target.append(failure(exc))

    def accepted(self, admitted, outcome):
        # No raw admission/token/input values; immutable association is hashed.
        fields = ('service', 'service_success', 'authorization_current', 'terminal_expected',
                  'classification', 'response_outcome', 'last_state', 'service_observed_at',
                  'manual_durable_available_at')
        safe = {k:deepcopy(outcome.get(k)) for k in fields}
        safe['job'] = safe_binding(admitted)
        safe['manual_actor'] = safe_binding(outcome.get('manual_actor'))
        safe['manual_physical_exit'] = safe_binding(outcome.get('manual_physical_exit'))
        self.outcomes.append(safe)

    def compact(self, *, alive=None, target=None, finished=None):
        return json.dumps({'scope':'controlled first-renewal setup, not natural availability',
            'events':self.events, 'terminal_events':self.terminal_events,
            'dropped_events':self.dropped, 'outcomes':self.outcomes,
            'primary_errors':self.primary_errors, 'cleanup_errors':self.cleanup_errors,
            'renewal_events':self.renewal.events, 'alive':alive, 'target':safe_binding(target),
            'finished':finished}, separators=(',', ':'))

    def emit(self, **fields):
        # Human-readable captured log; boundary_junit also persists properties
        # regardless of the runner's optional stdout logging configuration.
        print('DFA_BOUNDARY_EVIDENCE '+self.compact(**fields), flush=True)


@pytest.fixture(autouse=True)
def boundary_junit(monkeypatch, record_property):
    """Only imported by the affected fixture modules; no workflow changes."""
    actual=StartupEvidence.emit
    def emit(self, **fields):
        try:record_property('dfa_boundary',self.compact(**fields))
        finally:actual(self,**fields)
    monkeypatch.setattr(StartupEvidence,'emit',emit)
