"""Failure retention for capacity's real reactor; no permission/admission changes."""
import threading
import time
import traceback
from copy import deepcopy

from db.models import ActivityDFAControl as Control, ActivityDFARun as Run


def failure(exc):
    # Exception messages, source lines and locals can contain private payloads.
    return {'class': type(exc).__name__, 'at': time.monotonic(),
            'stack': [{'file': frame.filename.rsplit('/', 1)[-1],
                       'function': frame.name, 'line': frame.lineno}
                      for frame in traceback.extract_tb(exc.__traceback__)]}


class WorkerUnavailable(RuntimeError):
    pass


class CapacityWorker:
    def __init__(self, supervisor, errors):
        self.supervisor = supervisor
        self.errors = errors
        self.events = []
        self.exit_attempts = []
        self.cleanup_errors = []
        self.shutdown_requested = False
        self.unexpected_stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        original_set = supervisor.stop.set

        def stopped():
            if not self.shutdown_requested:
                self.unexpected_stop = True
            frame = traceback.extract_stack(limit=2)[0]
            self.events.append({'event': 'stop_set', 'at': time.monotonic(),
                                'issuer': {'file': frame.filename.rsplit('/', 1)[-1],
                                           'function': frame.name, 'line': frame.lineno}})
            original_set()
        supervisor.stop.set = stopped

    def start(self):
        self.events.append({'event': 'start_requested', 'at': time.monotonic()})
        self.thread.start()

    def _run(self):
        self.events.append({'event': 'worker_started', 'at': time.monotonic()})
        try:
            self.supervisor.run()
            if not self.shutdown_requested:
                self.errors.append({'class': 'UnexpectedWorkerReturn', 'at': time.monotonic(), 'stack': []})
        except BaseException as exc:
            self.errors.append(failure(exc))
        finally:
            self.events.append({'event': 'worker_exited', 'at': time.monotonic()})
            if self.errors:
                self.failure_snapshot = self.snapshot()

    def snapshot(self):
        result = {'at': time.monotonic()}
        try:
            result['physical_actor'] = deepcopy(self.supervisor.lane.actor())
        except Exception as exc:
            result['physical_error'] = failure(exc)
        try:
            # One bounded reserved-control read at failure/terminal, no payloads.
            with self.supervisor.controls() as db:
                row = db.get(Control, 1)
                result['sql_control'] = ({'actor': deepcopy(row.actor), 'epoch': row.epoch,
                    'enabled': row.enabled, 'drained': row.drained,
                    'readiness_sequence': row.readiness_sequence} if row else None)
                with self.supervisor.lock:
                    active = deepcopy(self.supervisor.active)
                result['active_binding'] = ({k: active[k] for k in
                    ('id', 'generation', 'epoch', 'input')} if active else None)
                if active:
                    run = db.query(Run.status, Run.generation, Run.progress, Run.error_code).filter_by(id=active['id']).first()
                    result['run'] = dict(run._mapping) if run else None
        except Exception as exc:
            result['sql_error'] = failure(exc)
        return result

    def record_exit(self, actual):
        entry = {'attempt_at': time.monotonic(), 'physical_actor': deepcopy(self.supervisor.lane.actor())}
        self.exit_attempts.append(entry)
        try:
            value = actual()
        except BaseException as exc:
            entry['error'] = failure(exc)
            raise
        entry['commit_ack_at'] = time.monotonic()
        entry['receipt'] = deepcopy(value)
        entry['physical_actor_after'] = deepcopy(self.supervisor.lane.actor())
        return value

    def ingress_allowed(self):
        return (self.thread.is_alive() and not self.supervisor.stop.is_set()
                and not self.errors and not self.shutdown_requested)

    def guarded_ingress(self, actual, *args, **kwargs):
        if not self.ingress_allowed():
            raise WorkerUnavailable('capacity_supervisor_terminated')
        # This check is no reservation: observe any accepted return even if the
        # reactor fails during actual admission. Never check/drop it afterwards.
        return actual(*args, **kwargs)

    def backoff(self, seconds):
        started = time.monotonic()
        interrupted = self.supervisor.stop.wait(seconds)
        return {'elapsed_seconds': time.monotonic()-started, 'interrupted': interrupted,
                'ingress_allowed_after': self.ingress_allowed()}

    def close(self):
        self.shutdown_requested = True
        self.events.append({'event': 'cleanup_requested', 'at': time.monotonic()})
        try:
            self.supervisor.stop.set()
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise AssertionError('capacity_worker_cleanup_timeout')
        except BaseException as exc:
            self.cleanup_errors.append(failure(exc))

    def evidence(self):
        return {'events': list(self.events), 'errors': list(self.errors),
                'cleanup_errors': list(self.cleanup_errors), 'exit_attempts': list(self.exit_attempts),
                'alive': self.thread.is_alive(), 'stop_set': self.supervisor.stop.is_set(),
                'unexpected_stop': self.unexpected_stop,
                'failure_snapshot': getattr(self, 'failure_snapshot', None),
                'finalization_events': list(getattr(self.supervisor, 'finalization_events', [])),
                'finalization_pending': getattr(self.supervisor, 'pending_evidence', lambda: None)()}

    def assert_certifiable(self):
        assert not self.errors and not self.cleanup_errors and not self.unexpected_stop, self.evidence()
