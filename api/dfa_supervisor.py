"""Pinned, default-disabled Linux supervisor; API processes only admit and read."""
from __future__ import annotations
import base64
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import queue
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, defer

from api.dfa_physical import Lane, PhysicalUnavailable, MAX_OUTPUT, PROFILE
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run, ActivityDFASyncReceipt as Receipt


def manual_admission(db):
    control = db.query(Control).filter_by(id=1).with_for_update().first()
    now = datetime.utcnow()
    if (control is None or not control.enabled or control.drained or not control.incarnation
            or not control.ready_until or control.ready_until < now):
        raise HTTPException(503, 'DFA_CAPACITY_UNAVAILABLE', headers={'Retry-After': '5'})
    if control.actor and control.actor.get('state') in ('launching', 'recovery_required'):
        raise HTTPException(503, 'DFA_RECOVERY_REQUIRED')
    if control.actor:
        actor = control.actor
        if actor.get('incarnation') != control.incarnation or actor.get('binding', {}).get('epoch') != str(control.epoch):
            raise HTTPException(503, 'DFA_CONTROL_GENERATION_CHANGED')
    control.manual_sequence += 1
    return str(uuid4()), now, str(control.epoch)


def incarnation():
    # Supplied identity only proposes a candidate; exact durable binding is
    # checked below. Startup never generates an authority nonce or elects itself.
    raw = os.environ.get('PRAXYS_DFA_INCARNATION')
    value = json.loads(raw) if raw else None
    required = {'resource','slot','instance','source','incarnation','epoch','boot','namespace'}
    if (not isinstance(value, dict) or set(value) != required
            or type(value['epoch']) is not int or value['epoch'] < 1
            or any(not isinstance(value[key], str) or not 1 <= len(value[key]) <= 512 for key in required - {'epoch'})):
        raise PhysicalUnavailable('incarnation_not_configured')
    from uuid import UUID
    UUID(value['incarnation'])
    import subprocess
    source_file = Path(__file__).with_name('_build_sha.txt')
    if source_file.exists():
        source = source_file.read_text().strip()
    else:
        source = subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],text=True).strip()
    observations = {
        'resource': os.environ.get('PRAXYS_DFA_PLACEMENT_ID'),
        'slot': os.environ.get('WEBSITE_SLOT_NAME', 'production'),
        'instance': os.environ.get('WEBSITE_INSTANCE_ID'),
        'source': source,
        'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'namespace': os.readlink('/proc/self/ns/pid') + '|' + os.readlink('/proc/self/ns/mnt'),
    }
    if any(value[key] != observed or not observed for key, observed in observations.items()):
        raise PhysicalUnavailable('incarnation_observation_changed')
    return value


def control_factory():
    # Existing database authority is used only in supervisor, never child env.
    url = os.environ.get('PRAXYS_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if not url:
        from db import session
        return session.SessionLocal
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    engine = create_engine(url, pool_size=1, max_overflow=0, pool_timeout=.1,
        connect_args={'connect_timeout': 1, 'options': '-c statement_timeout=200 -c lock_timeout=200'})
    from db.session import _attach_entra_token
    _attach_entra_token(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class Supervisor:
    def __init__(self, factory, control_sessions, identity, directory):
        self.factory, self.controls, self.identity = factory, control_sessions, identity
        self.lane = Lane(directory, identity)
        self.permission_until = 0.
        self.allowed = False
        self.control_observation = {'state':'not_checked','duration_seconds':None}
        self.stop = threading.Event()
        self.active = None
        self.lock = threading.Lock()
        self.physical_mutex = threading.RLock()
        self.retired = threading.Event()

    def _bound(self, db):
        row = db.query(Control).filter_by(id=1).populate_existing().first()
        return row if row and row.incarnation == self.identity and row.epoch == self.identity['epoch'] and row.enabled and not row.drained else None

    def renew(self):
        """I/O runs independently. Only completed current checks renew permission."""
        from api import activity_dfa as service
        while not self.stop.is_set():
            started = time.monotonic()
            valid = False
            try:
                with self.controls() as db:
                    if db.get_bind().dialect.name == 'postgresql':
                        db.execute(text("SET LOCAL statement_timeout='200ms'"))
                        db.execute(text("SET LOCAL lock_timeout='200ms'"))
                    row = self._bound(db)
                    with self.lock:
                        active = self.active
                    valid = row is not None
                    if active:
                        run = db.query(Run).options(defer(Run.result)).filter_by(id=active['id'],
                            generation=active['generation'], status='running', execution_epoch=str(row.epoch) if row else '').first()
                        valid = bool(valid and run and service._current(db, run))
                        if valid and run.origin == 'automatic' and db.query(Run.id).filter_by(origin='manual', status='queued').first():
                            valid = False
                    if valid and time.monotonic() - started < PROFILE['poll_seconds']:
                        row.ready_until = datetime.utcnow() + timedelta(seconds=PROFILE['permission_seconds'])
                        row.readiness_sequence += 1
                        db.commit()
                        self.permission_until = time.monotonic() + PROFILE['permission_seconds']
                        self.allowed = True
                    else:
                        self.allowed = False
                    self.control_observation = {'state':'ready' if self.allowed else 'denied' if not valid else 'deadline', 'duration_seconds':time.monotonic()-started}
            except Exception as exc:
                self.allowed = False
                self.control_observation = {'state':type(exc).__name__, 'duration_seconds':time.monotonic()-started}
            self.stop.wait(max(0., PROFILE['poll_seconds'] - (time.monotonic() - started)))

    def admit_completion(self):
        from api import activity_dfa as service, dfa_rights
        from api.dfa_automatic import require_policy
        from analysis.activity_dfa import digest, METHOD_VERSION
        from analysis.dfa_source import source_inventory
        from sync.rr_recording import RRRecordingReader, RecordingRef
        with self.factory() as db:
            receipt = db.query(Receipt).filter_by(disposition='pending').order_by(Receipt.created_at).first()
            if receipt is None:
                return
            receipt_id, owner, ref = receipt.id, receipt.user_id, receipt.recording_ref
            db.rollback()
            with service.owner_write(db, owner):
                receipt = db.get(Receipt, receipt_id)
                if not receipt or receipt.disposition != 'pending':
                    return
                try:
                    state = service.storage.authority_state(owner)
                    if state['deleted'] or any(e['scope'] == 'activity' and e['target'] == ref['activity_id']
                        for e in state['events'].values()):
                        raise ValueError('suppressed')
                    policy = require_policy()
                    inventory = source_inventory(list(RRRecordingReader(db).iter_recording(RecordingRef(**ref))), ref)
                    if inventory['outcome'] != 'eligible_metadata_inferred':
                        receipt.disposition = inventory['outcome']; db.commit(); return
                    value = dfa_rights.binding(db, owner, ref, 'automatic', policy, completion=receipt, inventory=inventory)
                    # Associate a later successful receipt only inside its origin.
                    previous = db.query(Run).filter_by(user_id=owner, origin='automatic', snapshot_id=ref['snapshot_id'], parse_id=ref['parse_id'],
                                                      science_contract_digest=policy, freshness='current').first()
                    if previous and service._current(db, previous):
                        receipt.run_id, receipt.disposition = previous.id, 'unchanged'
                        db.commit(); return
                    if db.query(Run.id).filter_by(user_id=owner, origin='automatic').filter(Run.status.in_(service.ACTIVE)).first():
                        return
                    control = self._bound(db)
                    if control is None or not self.allowed:
                        return
                    if db.query(Run.id).filter(Run.status.in_(service.ACTIVE)).count() >= service.MAX_ACTIVE_GLOBAL:
                        receipt.disposition = 'capacity_denied'; db.commit(); return
                    from sqlalchemy import func
                    used = db.query(func.coalesce(func.sum(Run.retained_bytes), 0)).filter_by(user_id=owner).scalar()
                    if used + service.MAX_RESULT_BYTES > service.OWNER_QUOTA:
                        receipt.disposition = 'quota_denied'; db.commit(); return
                    grant = dfa_rights.create_grant(db, value)
                    run = Run(user_id=owner, activity_id=ref['activity_id'], snapshot_id=ref['snapshot_id'],
                        parse_id=ref['parse_id'], origin='automatic', grant_id=grant.id, recording_ref=ref,
                        input_digest=digest(['automatic', grant.id]), method_version=METHOD_VERSION,
                        science_contract_digest=policy, phase='compute', execution_epoch=str(control.epoch),
                        retained_bytes=service.MAX_RESULT_BYTES)
                    db.add(run); db.flush()
                    receipt.run_id, receipt.disposition = run.id, 'admitted'
                except Exception:
                    receipt.disposition = 'authority_denied'
                db.commit()

    def acquire_job(self):
        from api import activity_dfa as service
        from sqlalchemy import case
        with self.factory() as db:
            row = db.query(Run.id, Run.user_id).filter_by(status='queued').order_by(
                case((Run.origin == 'manual', 0), else_=1), Run.created_at).first()
            if not row:
                return None
            owner, run_id = row.user_id, row.id
            db.rollback()
            with service.owner_write(db, owner):
                control = self._bound(db)
                run = db.query(Run).filter_by(id=run_id, status='queued').with_for_update().first()
                if control is None or run is None or not self.allowed or not service._current(db, run):
                    return None
                run.status, run.progress = 'running', 'reading'
                run.lease_token = str(uuid4())
                run.execution_epoch = str(control.epoch)
                run.lease_until = datetime.utcnow() + timedelta(seconds=service.LEASE_SECONDS)
                value = {'id': run.id, 'owner': owner, 'generation': run.generation, 'epoch': run.execution_epoch,
                         'input': run.input_digest, 'phase': run.phase, 'ref': run.recording_ref, 'origin': run.origin}
                db.commit()
                return value

    def work(self, job, result_queue):
        """Loading/IPC/publication is off the retirement reactor."""
        from api import activity_dfa as service
        from sync.rr_recording import RRRecordingReader, RecordingRef
        from analysis.activity_dfa import digest
        child = None
        started = time.monotonic()
        try:
            with self.factory() as db:
                run = db.query(Run).filter_by(id=job['id'], generation=job['generation'], status='running').first()
                if run is None or not service._current(db, run):
                    raise ValueError('authority_changed')
                raw = RRRecordingReader(db).raw(RecordingRef(**job['ref']))
                proof = db.get(service.Confirmation, run.confirmation_id) if run.confirmation_id else None
                manual_proof = {'sensor_ref': proof.sensor_ref, 'rule_fingerprint': proof.rule_fingerprint,
                                'evidence_digest': proof.evidence_digest} if proof else None
            if not self.allowed or time.monotonic() > self.permission_until:
                raise ValueError('permission_expired')
            if time.monotonic() - started > service.MAX_EXECUTION_SECONDS:
                raise ValueError("execution_time_limit")
            binding = {key: job[key] for key in ('generation','epoch','input')}
            with self.physical_mutex:
                if self.retired.is_set() or not self.allowed or time.monotonic() > self.permission_until:
                    raise ValueError("permission_expired")
                actor, child = self.lane.launch(binding, authorized=True)
            # Acknowledged local journal is durable before any private bytes flow.
            with self.controls() as db:
                control = self._bound(db)
                if control is None:
                    raise ValueError('binding_changed')
                control.actor = actor; db.commit()
            payload = {'binding': binding, 'actor_token': actor['actor_token'], 'phase': job['phase'],
                       'raw_fit': base64.b64encode(raw).decode(), 'recording_ref': job['ref'], 'manual_proof': manual_proof, 'origin': job['origin']}
            child.stdin.write(json.dumps(payload, separators=(',', ':')).encode() + b'\n')
            child.stdin.close()
            output = child.stdout.read(MAX_OUTPUT + 2)
            if len(output) > MAX_OUTPUT + 1 or not output.endswith(b'\n'):
                raise ValueError('ipc_output_invalid')
            if len(output) > service.MAX_RESULT_BYTES:
                raise ValueError("result_limit")
            from api import dfa_ipc
            value = dfa_ipc.loads(output)
            dfa_ipc.binding(value.get("binding"))
            if (set(value) != {'binding','actor_token','inventory','result'} or value['binding'] != binding
                    or value['actor_token'] != actor['actor_token']):
                raise ValueError('ipc_binding_changed')
            dfa_ipc.result(value['result'], job['phase'])
            result_queue.put(('output', value))
        except Exception as exc:
            safe = str(exc) if str(exc) in {'execution_time_limit','result_limit'} else 'execution_unavailable'
            result_queue.put(('failed', safe))

    def record_exit(self):
        """Physical availability commits independently from owner cleanup I/O."""
        actor = self.lane.actor()
        if actor is None or actor.get('state') != 'idle':
            raise PhysicalUnavailable('exit_not_observed')
        with self.controls() as db:
            if db.get_bind().dialect.name == 'postgresql':
                db.execute(text("SET LOCAL statement_timeout='200ms'"))
                db.execute(text("SET LOCAL lock_timeout='200ms'"))
            control = db.query(Control).filter_by(id=1).with_for_update().first()
            if control is None or control.incarnation != self.identity or control.epoch != self.identity['epoch']:
                raise PhysicalUnavailable('exit_journal_binding_changed')
            previous = control.actor
            if not previous or previous.get('actor_token') != actor['actor_token']:
                # A bounded acknowledgement query can fail after the local
                # journal recorded this live supervisor's child. Its verified
                # exit is safe to project over an empty/idle predecessor only,
                # after the work thread is joined. Never replace another actor.
                with self.lock:
                    active = self.active
                expected = {key: active[key] for key in ('generation','epoch','input')} if active else None
                if (expected != actor.get('binding') or previous and previous.get('state') != 'idle'):
                    raise PhysicalUnavailable('exit_journal_binding_changed')
            control.actor = actor
            db.commit()

    def finish(self, job, status, value):
        from api import activity_dfa as service
        from analysis.activity_dfa import digest
        with self.factory() as db:
            with service.owner_write(db, job['owner']):
                run = db.query(Run).filter_by(id=job['id'], generation=job['generation'], status='running').first()
                if run:
                    current = service._current(db, run) and self._bound(db) is not None
                    if status == 'output' and current:
                        output = value['result']
                        output['source_assurance'] = 'metadata_inferred' if run.origin == 'automatic' else 'user_confirmed'
                        if run.origin == 'automatic' and value['inventory']['outcome'] != 'eligible_metadata_inferred':
                            current = False
                        if current:
                            run.result, run.result_revision = output, digest(output)
                            run.status = 'complete' if run.phase == 'compute' else 'awaiting_source_confirmation'
                            run.retained_bytes = len(json.dumps(output).encode())
                    if run.status == 'running':
                        run.status = 'queued' if job['origin'] == 'automatic' and current else 'failed'
                        run.error_code = 'preempted' if run.status == 'queued' else value if status == 'failed' else 'execution_unavailable'
                        run.retained_bytes = 0 if run.status == 'failed' else run.retained_bytes
                    run.progress = run.status
                    run.completed_at = datetime.utcnow() if run.status != 'queued' else None
                    run.expires_at = datetime.utcnow() + timedelta(days=30 if run.status == 'complete' else 7)
                    run.lease_token = run.lease_until = None
                control = db.query(Control).filter_by(id=1).first()
                if control and control.incarnation == self.identity:
                    control.actor = self.lane.actor()
                db.commit()

    def reconcile_recovery(self):
        """Commit an old actor's verified exit before admitting replacement work."""
        self.lane.recover(authorized=True)
        actor = self.lane.actor()
        with self.controls() as db:
            control = self._bound(db)
            if control is None:
                raise PhysicalUnavailable('host_not_bound')
            recorded = control.actor
        if recorded and recorded.get('state') != 'idle' and actor is None:
            raise PhysicalUnavailable('recovery_actor_missing')
        if actor is not None:
            if not recorded or recorded.get('actor_token') != actor.get('actor_token'):
                raise PhysicalUnavailable('exit_journal_binding_changed')
            self.record_exit()
            with self.factory() as db:
                previous = db.query(Run).filter_by(input_digest=actor['binding']['input'],
                    generation=actor['binding']['generation'], status='running').first()
                job = {'id': previous.id, 'owner': previous.user_id,
                       'generation': previous.generation, 'origin': previous.origin} if previous else None
            if job:
                self.finish(job, 'retired', None)

    def run(self):
        with self.controls() as db:
            if self._bound(db) is None:
                raise PhysicalUnavailable('host_not_bound')
        self.reconcile_recovery()
        threading.Thread(target=self.renew, daemon=True, name='dfa-control').start()
        work_thread, outputs, job = None, None, None
        try:
            while not self.stop.wait(.01):
                if job:
                    ready = not outputs.empty()
                    expired = time.monotonic() > self.permission_until or not self.allowed
                    from api.activity_dfa import MAX_EXECUTION_SECONDS
                    timed_out = time.monotonic() - launched_at > MAX_EXECUTION_SECONDS
                    if expired or timed_out or ready:
                        self.retired.set()
                        with self.physical_mutex:
                            self.lane.retire()
                        status, value = outputs.get() if ready and not expired and not timed_out else ('retired', None)
                        # Retired output is discarded. A physical slot is reusable
                        # only after the durable exit observation above.
                        if work_thread.is_alive():
                            work_thread.join(timeout=.25)
                        if work_thread.is_alive():
                            raise PhysicalUnavailable('loading_or_ipc_not_retired')
                        self.record_exit()
                        self.finish(job, status, value)
                        with self.lock:
                            self.active = None
                        job = None
                elif self.allowed and time.monotonic() < self.permission_until:
                    self.admit_completion()
                    job = self.acquire_job()
                    if job:
                        outputs = queue.Queue(maxsize=1)
                        with self.lock:
                            self.active = job
                        self.retired.clear()
                        launched_at = time.monotonic()
                        work_thread = threading.Thread(target=self.work, args=(job, outputs), daemon=True)
                        work_thread.start()
        finally:
            self.stop.set()
            self.lane.retire()
            self.lane.close()


def main():
    if os.environ.get('PRAXYS_DFA_SUPERVISOR_ENABLED', '').lower() != 'true':
        return
    from db import session
    session.init_db()
    identity = incarnation()
    directory = Path('/tmp') / ('praxys-dfa-' + str(os.getuid()) + '-' + identity['incarnation'])
    supervisor = Supervisor(session.SessionLocal, control_factory(), identity, directory)
    import signal
    signal.signal(signal.SIGTERM, lambda signum, frame: supervisor.stop.set())
    signal.signal(signal.SIGINT, lambda signum, frame: supervisor.stop.set())
    import asyncio
    from api.statsig_client import init_statsig, shutdown_statsig
    asyncio.run(init_statsig())
    try:
        supervisor.run()
    finally:
        asyncio.run(shutdown_statsig())


if __name__ == '__main__':
    main()
