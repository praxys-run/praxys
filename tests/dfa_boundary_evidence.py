"""Test-only first-decision barrier; real renewal owns every permission value."""
import threading
import time
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
