"""Test-only first-decision barrier; real renewal owns every permission value."""
import threading
import time
import json
import pytest
from copy import deepcopy


class RenewalDecision:
    def __init__(self, supervisor, monkeypatch):
        self.supervisor = supervisor
        from tests.dfa_active_capture import PrimitiveSignal,capture_decision
        self.event = PrimitiveSignal()
        self.armed = False
        self.observation = None
        self.raw_observation = None
        self.actor_keys=tuple(sorted(supervisor.identity))
        self.events = []
        actual = supervisor._decision

        def decision(job, reason, actor=None):
            value = actual(job, reason, actor)
            if self.armed:
                self.armed = False
                self.raw_observation = capture_decision(value,self.actor_keys)
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
            self.raw_observation = None
            self.armed = True
            self.events.append({'event': 'barrier_armed', 'at': time.monotonic()})

    def wait(self):
        assert self.event.wait(2), self.events
        from tests.dfa_active_capture import capture_decision,decision_values
        with self.supervisor.lock:
            raw=self.raw_observation
            current=capture_decision(self.supervisor.permission_decision,self.actor_keys)
            allowed = self.supervisor.allowed
            deadline = self.supervisor.permission_until
        # A first denial fails this positive; never select a later favourable
        # cycle, manufacture permission, or extend the runtime lease.
        assert raw.reason is None and allowed and current == raw, self.events
        # Formatting is outside the supervisor lock and timed renewal.
        self.observation=decision_values(raw,self.actor_keys)
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
        if value.get('incarnation') is not None:
            result['incarnation'] = sha256(json.dumps(value['incarnation'],sort_keys=True).encode()).hexdigest()
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
        from tests.dfa_active_capture import capture_decision,decision_values
        self.supervisor = supervisor
        self.events, self.outcomes = [], []
        self.terminal_events = []
        self.primary_errors, self.cleanup_errors = [], []
        self.dropped = 0
        self.used = False
        self.claim_observer = None
        self.synchronize_acquisition = True
        self.renew_each_acquisition = False
        self.renewal = RenewalDecision(supervisor, monkeypatch)
        actual_acquire = supervisor.acquire_job
        actual_finish = supervisor.finish
        actual_current = dfa_rights.execution_current
        actual_mode = dfa_rights.account_mode

        def acquire():
            started=time.monotonic()
            job = actual_acquire()
            if job and self.claim_observer:self.claim_observer(job,started)
            if job and (not self.used or self.renew_each_acquisition):
                self.used = True
                self.note('acquisition_return', job=safe_binding(job))
                if not self.synchronize_acquisition:
                    return job
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
            if getattr(getattr(supervisor,'_test_renewal_capture',None),'renew',False):return result
            self.note('execution_validation', started=started, current=result,
                      job=safe_binding({'id':run.id, 'generation':run.generation,
                                        'epoch':run.execution_epoch, 'origin':run.origin,
                                        'phase':run.phase}))
            return result

        def mode(db, owner):
            result = actual_mode(db, owner)
            if getattr(getattr(supervisor,'_test_renewal_capture',None),'renew',False):return result
            self.note('account_mode_validation', owner=safe_binding({'id':owner}), mode=result)
            return result

        def finish(job, status, value):
            with supervisor.lock:
                raw_decision = capture_decision(supervisor.permission_decision,self.renewal.actor_keys)
                allowed, deadline = supervisor.allowed, supervisor.permission_until
            decision=self.decision(decision_values(raw_decision,self.renewal.actor_keys))
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
                     'attempt_claim','attempt_occupied_ack','attempt_finish','attempt_finish_ack',
                     'first_renewal_outcome',
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


class FirstRenewalOutcome:
    """Observe one complete real renewal, including exception/denial; never retry it.

    A control observation can precede Session exit. Stop after the first cycle
    observation, retain any same-cycle close exception, and require thread return
    before certifying the completed outcome; never start another cycle.
    """
    def __init__(self, supervisor, factory, monkeypatch):
        self.supervisor, self.factory, self.monkeypatch = supervisor, factory, monkeypatch
        self.first = None
        self.cycle_started=None
        self.observations=[]
        self.stop_at=None
        self.sql, self.assignments, self.errors = [], [], []
        self.cleanup_errors = []
        self.thread = None

    def observe(self, scoped):
        import sys
        from hashlib import sha256
        from tests.dfa_capacity_worker import failure
        observer = self
        original_class = type(self.supervisor)
        renewal_code = self.supervisor.renew.__func__.__code__
        class Observed(original_class):
            def __setattr__(self, name, value):
                caller = sys._getframe(1)
                super().__setattr__(name, value)
                if caller.f_code is not renewal_code:return
                cycle=caller.f_locals['started']
                if observer.cycle_started is not None and cycle!=observer.cycle_started:
                    observer.errors.append({'class':'UnexpectedSecondRenewalCycle'});return
                if name in ('allowed', 'permission_until', 'permission_decision'):
                    observer.assignments.append({'field':name, 'at':time.monotonic(),
                        'value':StartupEvidence.decision(value) if name=='permission_decision' else value})
                if name == 'control_observation':
                    exc = caller.f_locals.get('exc')
                    observer.cycle_started=cycle
                    observer.first = {'at':time.monotonic(), 'observation':deepcopy(value),
                        'allowed':self.allowed, 'permission_until':self.permission_until,
                        'decision':StartupEvidence.decision(self.permission_decision),
                        'error':observer.error(exc) if exc else None,
                        'stop_issuer':'test_first_cycle_observation'}
                    if observer.stop_at is None:
                        self.stop.set();observer.stop_at=time.monotonic()
                    observer.first['stop_requested_at']=observer.stop_at
                    observer.observations.append(deepcopy(observer.first))
        scoped.setattr(self.supervisor, '__class__', Observed)
        class Controls(self.supervisor.controls.class_):
            def commit(session):
                caller = sys._getframe(1)
                row = caller.f_locals.get('row') if caller.f_code is renewal_code else None
                if row is not None:
                    observer.sql.append({'event':'invoked','at':time.monotonic(),
                        'epoch':row.epoch, 'incarnation':sha256(json.dumps(row.incarnation,sort_keys=True).encode()).hexdigest(),
                        'expected_sequence':row.readiness_sequence+1})
                try:
                    result = super().commit()
                except BaseException as exc:
                    if row is not None:observer.sql.append({'event':'error','at':time.monotonic(),'error':observer.error(exc)})
                    raise
                if row is not None:observer.sql.append({'event':'ack','at':time.monotonic()})
                return result
        from sqlalchemy.orm import sessionmaker
        scoped.setattr(self.supervisor,'controls',sessionmaker(class_=Controls,**self.supervisor.controls.kw))

    @staticmethod
    def error(exc):
        from tests.dfa_capacity_worker import failure
        origin=getattr(exc,'orig',exc)
        return {**failure(exc),'sqlite_errorcode':getattr(origin,'sqlite_errorcode',None),
                'sqlstate':getattr(origin,'sqlstate',None)}

    def capture_sql(self):
        from db.models import ActivityDFAControl as Control
        from hashlib import sha256
        with self.factory() as db:
            row=db.get(Control,1)
            return {'epoch':row.epoch,'incarnation':sha256(json.dumps(row.incarnation,sort_keys=True).encode()).hexdigest(),
                    'sequence':row.readiness_sequence,'deadline':row.ready_until.isoformat() if row.ready_until else None}

    def run(self):
        from tests.dfa_capacity_worker import failure
        with self.monkeypatch.context() as scoped:
            self.observe(scoped)
            self.supervisor.stop.clear()
            def renew():
                try:self.supervisor.renew()
                except BaseException as exc:self.errors.append(failure(exc))
                finally:self.returned_at=time.monotonic()
            self.thread=threading.Thread(target=renew,name='first-real-renewal')
            self.thread.start();self.thread.join(3)
            if self.thread.is_alive():
                self.errors.append({'exception_class':'FirstRenewalDidNotTerminate'})
                self.supervisor.stop.set();self.thread.join(1)
            # Snapshot is supplemental. First outcome survives snapshot failure.
            try:self.persisted=self.capture_sql() if not self.thread.is_alive() else None
            except BaseException as exc:
                self.persisted=None;self.cleanup_errors.append(failure(exc))
        if not self.thread.is_alive():self.supervisor.stop.clear()
        return self

    def evidence(self):
        return {'scope':'first completed renewal, not natural availability',
                'first':self.first,'cycle_observations':self.observations[:3],
                'returned_at':getattr(self,'returned_at',None),
                'sql':self.sql[:4], 'assignments':self.assignments[:8],
                'persisted':getattr(self,'persisted',None),'errors':self.errors[:2],
                'cleanup_errors':self.cleanup_errors[:2],
                'worker_alive':self.thread.is_alive() if self.thread else None}

    def require_ready(self):
        detail=json.dumps(self.evidence(),separators=(',',':'))
        assert self.first and not self.thread.is_alive() and not self.errors and not self.cleanup_errors, detail
        assert self.first['allowed'] and self.first['observation']['state']=='ready', 'FIRST_RENEWAL_SETUP_FAILURE '+detail
        assert self.first['decision']['reason'] is None and self.sql[-1]['event']=='ack', detail
        assert time.monotonic()<self.first['permission_until'], detail
        return self.persisted


class OccupiedTarget:
    """One exact post-commit actor; rejection never selects a later replacement."""
    def __init__(self, job, identity):
        self.job, self.identity = deepcopy(job), deepcopy(identity)
        self.actor = None
        self.seen = False

    def acknowledge(self, job, actor):
        assert not self.seen, 'duplicate_or_replacement_occupied_target'
        self.seen = True
        assert actor is not None and actor.get('state')=='occupied', 'missing_occupied_target'
        assert all(job.get(k)==self.job.get(k) for k in ('id','generation','origin','phase')), 'wrong_job_target'
        assert str(job['epoch'])==str(self.identity['epoch']), 'wrong_job_epoch'
        assert actor.get('binding')=={k:job[k] for k in ('generation','epoch','input')}, 'wrong_actor_binding'
        assert actor.get('incarnation')==self.identity, 'wrong_actor_incarnation'
        assert actor.get('actor_token') and all(actor.get('identity',{}).get(k) is not None for k in ('pid','pgid','start')), 'missing_actor_identity'
        self.actor=deepcopy(actor)
        return deepcopy(self.actor)


class FinishObservation:
    """Immutable exact-attempt publication precedes its observation signal."""
    def __init__(self, binding, attempt):
        self.binding, self.attempt = deepcopy(binding), attempt
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.record = self.error_record = None

    def publish(self, value):
        try:
            assert value['claim']['job']==self.binding and value['attempt']==self.attempt,'wrong_finish_observation_binding'
            encoded=json.dumps(value,separators=(',',':'))
            with self.lock:
                assert not self.done.is_set(),'duplicate_finish_observation'
                self.record=encoded
                self.done.set()
        except BaseException as exc:
            self.fail(FirstRenewalOutcome.error(exc))
            raise

    def fail(self, error):
        with self.lock:
            self.error_record=json.dumps(error,separators=(',',':'))
            self.done.set()

    def require(self):
        with self.lock:
            assert self.done.is_set(),'finish_observation_not_complete'
            assert self.error_record is None,'finish_observation_failed '+str(self.error_record)
            assert self.record is not None,'finish_observation_record_missing'
            return json.loads(self.record)

    def metadata(self):
        from hashlib import sha256
        with self.lock:
            return {'binding':deepcopy(self.binding),'attempt':self.attempt,'done':self.done.is_set(),
                'record_sha256':sha256(self.record.encode()).hexdigest() if self.record else None,
                'error':json.loads(self.error_record) if self.error_record else None}


from tests.dfa_active_capture import ActiveRenewalEvidence


@pytest.fixture(autouse=True)
def boundary_junit(monkeypatch, record_property):
    """Only imported by the affected fixture modules; no workflow changes."""
    actual=StartupEvidence.emit
    def emit(self, **fields):
        try:record_property('dfa_boundary',self.compact(**fields))
        finally:actual(self,**fields)
    monkeypatch.setattr(StartupEvidence,'emit',emit)
    active=ActiveRenewalEvidence.emit
    def active_emit(self):
        try:record_property('dfa_active_renewal',self.compact())
        finally:active(self)
    monkeypatch.setattr(ActiveRenewalEvidence,'emit',active_emit)
