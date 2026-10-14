"""Pinned, default-disabled Linux supervisor; API processes only admit and read."""
from __future__ import annotations
import base64
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
import traceback
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import queue
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, text, cast, String, or_, func, literal, select, exists, and_
from sqlalchemy.exc import OperationalError, TimeoutError as PoolTimeout
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, defer

from api.dfa_physical import Lane, PhysicalUnavailable, MAX_OUTPUT, PROFILE
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run, ActivityDFASyncReceipt as Receipt


# At most eight validation starts per second. This overlaps admission pulses
# when healthy checks complete within125ms, without extending250ms/750ms bounds.
CONTROL_CADENCE_SECONDS = .125

WORKER_FAILURES = {'timer_invalid','fit_invalid','fit_too_large','rr_limit','frame_limit','elapsed_limit',
    'source_contradiction','source_unsupported','rr_missing','manual_source_changed','automatic_source_changed',
    'ipc_result_limit','numerical_invalid'}
TRANSIENT_FAILURES = {'execution_unavailable','permission_expired','restart_interrupted'}
SAFE_FAILURES = WORKER_FAILURES | TRANSIENT_FAILURES | {'execution_time_limit','result_limit',
    'authority_changed','binding_changed','ipc_output_invalid','input_changed','input_integrity_failed'}


EXIT_PERSISTENCE_ATTEMPTS = 3
EXIT_PERSISTENCE_START_SECONDS = 1.


@dataclass(frozen=True)
class PendingFinalization:
    job_json: str
    actor_json: str
    predecessor_json: str
    status: str
    value_json: str
    cancellation: threading.Event
    started: float


def _json_equal(db, column, value):
    if value is None:
        return or_(column.is_(None), cast(column, String)=='null')
    encoded = json.dumps(value)
    if db.get_bind().dialect.name=='postgresql':
        return cast(column, JSONB)==cast(literal(encoded), JSONB)
    left=func.json_tree(column).table_valued('fullkey','type','atom').alias()
    right=func.json_tree(encoded).table_valued('fullkey','type','atom').alias()
    a=select(left.c.fullkey,left.c.type,left.c.atom)
    b=select(right.c.fullkey,right.c.type,right.c.atom)
    return and_(~exists(a.except_(b)),~exists(b.except_(a)))


def _same_actor(left, right):
    return bool(left and right and all(left.get(k)==right.get(k)
        for k in ('actor_token','binding','incarnation','identity')))


def _persistence_error(exc):
    original = getattr(exc, 'orig', None)
    code = getattr(original, 'sqlite_errorcode', None)
    state = getattr(original, 'sqlstate', None)
    transient = (isinstance(exc, PoolTimeout) or isinstance(exc, OperationalError) and
        (isinstance(code, int) and code & 255 in (5, 6) or state in
         ('55P03','40001','40P01','57014','08001','08003','08006')))
    return {'class':type(exc).__name__, 'sqlite_code':code, 'sqlstate':state,
            'transient':bool(transient),
            'reason_code':str(exc) if isinstance(exc,PhysicalUnavailable) and str(exc) in
                {'exit_not_observed','exit_journal_binding_changed','finish_control_binding_changed',
                 'finish_actor_binding_changed','finish_exit_not_observed','finish_run_binding_changed',
                 'finalization_stopped','exit_persistence_start_limit'} else None,
            'stack':[{'file':f.filename.rsplit('/',1)[-1],
                'function':f.name,'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]}


def manual_admission(db):
    # Response metadata may already have loaded this row. Refresh its actual
    # locked values; cached readiness/drain/epoch cannot authorize admission.
    control = db.query(Control).filter_by(id=1).populate_existing().with_for_update().first()
    now = datetime.utcnow()
    if (control is None or not control.enabled or control.drained or not control.incarnation
            or not control.ready_until or control.ready_until <= now):
        raise HTTPException(503, 'DFA_CAPACITY_UNAVAILABLE', headers={'Retry-After': '5'})
    if control.actor and control.actor.get('state') in ('launching', 'recovery_required'):
        raise HTTPException(503, 'DFA_RECOVERY_REQUIRED')
    if not isinstance(control.incarnation, dict) or control.incarnation.get('epoch') != control.epoch:
        raise HTTPException(503, 'DFA_CONTROL_GENERATION_CHANGED')
    if control.actor:
        actor = control.actor
        if actor.get('incarnation') != control.incarnation or actor.get('binding', {}).get('epoch') != str(control.epoch):
            raise HTTPException(503, 'DFA_CONTROL_GENERATION_CHANGED')
    control.manual_sequence += 1
    return str(uuid4()), now, str(control.epoch)


def proposed_incarnation():
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
    return value


def incarnation():
    value = proposed_incarnation()
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
    # Two bounded connections: renewal and the single lifecycle acknowledgement
    # (spawn or verified exit). Exit follows work-thread join, so acknowledgements
    # never overlap each other or consume the renewal connection.
    # Existing database authority is used only in supervisor, never child env.
    url = os.environ.get('PRAXYS_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if not url:
        from db import session
        url = session.get_database_url()
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    from sqlalchemy.engine import make_url
    sqlite = make_url(url).get_backend_name() == 'sqlite'
    args = {'timeout': .1, 'check_same_thread': False} if sqlite else {
        'connect_timeout': 1, 'options': '-c statement_timeout=200 -c lock_timeout=200'}
    engine = create_engine(url, pool_size=2, max_overflow=0, pool_timeout=.1, connect_args=args)
    from db.session import _attach_entra_token, _attach_sqlite_pragmas
    if sqlite:
        _attach_sqlite_pragmas(engine)
        from sqlalchemy import event
        @event.listens_for(engine, 'connect')
        def bounded_busy_timeout(connection, record):
            # Preserve the repository's durable SQLite settings while keeping
            # this supervisor pool's lock wait within the control budget.
            cursor = connection.cursor()
            try: cursor.execute('PRAGMA busy_timeout=100')
            finally: cursor.close()
    else:
        _attach_entra_token(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class Supervisor:
    def __init__(self, factory, control_sessions, identity, directory, *, lane=None):
        self.factory, self.controls, self.identity = factory, control_sessions, identity
        self.lane = lane or Lane(directory, identity)
        self.permission_until = 0.
        self.allowed = False
        self.control_observation = {'state':'not_checked','duration_seconds':None}
        self.stop = threading.Event()
        self.active = None
        self.lock = threading.Lock()
        self.physical_mutex = threading.RLock()
        self.retired = threading.Event()
        self.retirement_reason = None
        # At most two Python I/O continuations including the active job. A
        # cancelled continuation cannot consume the next physical slot.
        self.cleanups = []
        self.retiring = False
        self.pending = None
        self.renewal_phase = 0
        self.permission_decision = None
        self.finalization_events = deque(maxlen=256)

    def _bound(self, db):
        row = db.query(Control).filter_by(id=1).populate_existing().first()
        return row if row and row.incarnation == self.identity and row.epoch == self.identity['epoch'] and row.enabled and not row.drained else None

    def _renewal_current(self, phase):
        with self.lock:
            return phase==self.renewal_phase and not self.retiring and self.pending is None

    def _decision(self, job, reason, actor=None):
        # Called only under the short local state lock. No SQL/hash/file reads.
        previous = self.permission_decision
        binding = {k:job[k] for k in ('id','generation','epoch','input')} if job else None
        if (reason and not self.allowed and previous and previous['reason']
                and previous['phase']==self.renewal_phase and previous['job']==binding):
            return previous  # First invalidation owns the trigger until fresh permission.
        return {'at':time.monotonic(), 'reason':reason,
            'job':{k:job[k] for k in ('id','generation','epoch','input')} if job else None,
            'actor':deepcopy(actor), 'phase':self.renewal_phase}

    def _actor_guard(self, db, previous):
        return db.query(Control).filter_by(id=1, epoch=self.identity['epoch'], enabled=True, drained=False).filter(
            _json_equal(db, Control.incarnation, self.identity), _json_equal(db, Control.actor, previous))

    def _exit_predecessor(self, previous, actor):
        if previous==actor:
            return
        if _same_actor(previous, actor) and previous.get('state') in ('occupied','retiring','launching'):
            return
        with self.lock:
            active = self.active
        expected = {k:active[k] for k in ('generation','epoch','input')} if active else None
        predecessor = (json.loads(self.pending.predecessor_json) if self.pending else
            json.loads(self.launch_sql_predecessor[1]) if getattr(self,'launch_sql_predecessor',(None,))[0]==actor.get('actor_token') else
            json.loads(getattr(self.lane,'launch_predecessor_json','null'))
            if getattr(self.lane,'launch_token',None)==actor.get('actor_token') else None)
        if (expected!=actor.get('binding') or previous!=predecessor
                or previous and (previous.get('state')!='idle' or previous.get('incarnation')!=self.identity)):
            raise PhysicalUnavailable('exit_journal_binding_changed')

    def pending_evidence(self):
        pending = self.pending
        if pending is None: return None
        job=json.loads(pending.job_json)
        return {'job':{k:job[k] for k in ('id','origin','generation','epoch','input')},
                'actor':json.loads(pending.actor_json),'status':pending.status,
                'started':pending.started,'cancelled':pending.cancellation.is_set()}

    def _finalize_pending(self):
        pending=self.pending
        job=json.loads(pending.job_json);actor=json.loads(pending.actor_json)
        if not pending.cancellation.is_set(): raise PhysicalUnavailable('finalization_not_fenced')
        if actor and actor.get('binding')=={k:job[k] for k in ('generation','epoch','input')}:
            for attempt in range(1, EXIT_PERSISTENCE_ATTEMPTS+1):
                if self.stop.is_set():
                    self.finalization_events.append({'operation':'exit_persistence','event':'stopped','code':'finalization_stopped','at':time.monotonic()})
                    raise PhysicalUnavailable('finalization_stopped')
                if time.monotonic()-pending.started>=EXIT_PERSISTENCE_START_SECONDS:
                    self.finalization_events.append({'operation':'exit_persistence','event':'start_limit','code':'exit_persistence_start_limit','at':time.monotonic()})
                    raise PhysicalUnavailable('exit_persistence_start_limit')
                entry={'operation':'exit_persistence','event':'attempt','attempt':attempt,'at':time.monotonic(),
                       'actor_token':actor['actor_token']}
                self.finalization_events.append(entry)
                try:
                    receipt=self.record_exit()
                except Exception as exc:
                    error=_persistence_error(exc)
                    self.finalization_events.append({**entry,'event':'error','error':error,'at':time.monotonic()})
                    if not error['transient'] or attempt==EXIT_PERSISTENCE_ATTEMPTS:
                        self.finalization_events.append({**entry,'event':'exhausted' if error['transient'] else 'unclassified','at':time.monotonic()})
                        raise
                    self.finalization_events.append({**entry,'event':'retry','at':time.monotonic()})
                    if self.stop.wait(CONTROL_CADENCE_SECONDS):
                        self.finalization_events.append({**entry,'event':'stopped','code':'finalization_stopped','at':time.monotonic()})
                        raise PhysicalUnavailable('finalization_stopped') from exc
                else:
                    self.finalization_events.append({**entry,'event':'ack','receipt':receipt,'at':time.monotonic()})
                    break
        if self.stop.is_set():
            self.finalization_events.append({'operation':'owner_finish','event':'stopped','code':'finalization_stopped','at':time.monotonic()})
            raise PhysicalUnavailable('finalization_stopped')
        self.finalization_events.append({'operation':'owner_finish','event':'attempt','at':time.monotonic()})
        try:
            self.finish(job,pending.status,json.loads(pending.value_json))
        except Exception as exc:
            self.finalization_events.append({'operation':'owner_finish','event':'error','at':time.monotonic(),'error':_persistence_error(exc)})
            raise
        self.finalization_events.append({'operation':'owner_finish','event':'ack','at':time.monotonic()})
        with self.lock:
            self.active=None
            self.pending=None
            self.retiring=False
            self.renewal_phase+=1
            self.allowed=False  # Next work requires a new completed renewal.

    def renew(self):
        """I/O runs independently. Only completed current checks renew permission."""
        from api import activity_dfa as service
        while not self.stop.is_set():
            # SQL admission and the independent physical permission are distinct:
            # publication is actionable only within this validation/commit cycle.
            # Sample UTC first so its bound cannot exceed the monotonic budget.
            with self.lock:
                phase = self.renewal_phase
                active = self.active
                blocked = self.retiring or self.pending is not None
            if blocked:
                self.stop.wait(CONTROL_CADENCE_SECONDS)
                continue
            started_utc = datetime.utcnow()
            started = time.monotonic()
            valid = False
            mode_changed = False
            try:
                with self.controls() as db:
                    db.info['dfa_read_timeout_ms']=200
                    if db.get_bind().dialect.name == 'postgresql':
                        db.execute(text("SET LOCAL statement_timeout='200ms'"))
                        db.execute(text("SET LOCAL lock_timeout='200ms'"))
                    row = self._bound(db)
                    valid = row is not None and len(self.cleanups)<2
                    if active:
                        run = db.query(Run).options(defer(Run.result)).filter_by(id=active['id'],
                            generation=active['generation'], status='running', execution_epoch=str(row.epoch) if row else '').first()
                        from api import dfa_rights
                        mode = dfa_rights.account_mode(db, run.user_id) if run else 'unavailable'
                        mode_changed = bool(run and mode != 'unavailable' and mode != run.origin)
                        valid = bool(valid and run and mode == run.origin and service._current(db, run))
                    if valid and self._renewal_current(phase) and time.monotonic() - started < PROFILE['poll_seconds']:
                        # Publish only against the exact still-bound generation.
                        # Do not overwrite a concurrent drain/replacement's row
                        # with readiness derived from an older observation.
                        guard = db.query(Control).filter_by(id=1, epoch=self.identity['epoch'],
                            enabled=True, drained=False, readiness_sequence=row.readiness_sequence)
                        for key, value in self.identity.items():
                            field = Control.incarnation[key]
                            guard = guard.filter((field.as_integer() if key=='epoch' else field.as_string()) == value)
                        updated = guard.update({Control.ready_until: started_utc + timedelta(seconds=PROFILE['poll_seconds']),
                            Control.readiness_sequence: Control.readiness_sequence+1}, synchronize_session=False)
                        if updated != 1:
                            db.rollback()
                            with self.lock:
                                self.permission_decision = self._decision(active, 'permission')
                                self.allowed = False
                                self.retirement_reason = 'permission'
                            self.control_observation = {'state':'generation_changed', 'duration_seconds':time.monotonic()-started}
                            self.stop.wait(max(0., CONTROL_CADENCE_SECONDS-(time.monotonic()-started)))
                            continue
                        db.commit()
                        # The aggregate budget includes the real durable write,
                        # not only validation before commit. A late publication's
                        # SQL deadline is already expired, including before the
                        # local denial assignment or any best-effort cleanup.
                        decision_actor = self.lane.actor() if active else None
                        with self.lock:
                            if (not self.retiring and self.pending is None and phase==self.renewal_phase
                                    and time.monotonic() - started < PROFILE['poll_seconds']):
                                self.permission_decision = self._decision(active, None, decision_actor)
                                self.permission_until = time.monotonic() + PROFILE['permission_seconds']
                                self.allowed = True
                                self.retirement_reason = None
                            else:
                                self.permission_decision = self._decision(active, 'permission', decision_actor)
                                self.allowed = False
                                self.retirement_reason = 'permission'
                    else:
                        decision_actor = self.lane.actor() if active else None
                        with self.lock:
                            self.permission_decision = self._decision(active, 'mode_changed' if mode_changed else 'permission', decision_actor)
                            self.allowed = False
                            self.retirement_reason = 'mode_changed' if mode_changed else 'permission'
                    self.control_observation = {'state':'finalization_pending' if self.retiring or self.pending is not None else 'phase_changed' if phase!=self.renewal_phase else 'ready' if self.allowed else 'denied' if not valid else 'deadline', 'duration_seconds':time.monotonic()-started}
            except Exception as exc:
                try: decision_actor = self.lane.actor() if active else None
                except Exception: decision_actor = None
                with self.lock:
                    self.permission_decision = self._decision(active, 'permission', decision_actor)
                    self.allowed = False
                    self.retirement_reason = 'permission'
                self.control_observation = {'state':type(exc).__name__, 'duration_seconds':time.monotonic()-started}
            self.stop.wait(max(0., CONTROL_CADENCE_SECONDS - (time.monotonic() - started)))

    def admit_completion(self):
        from api import activity_dfa as service, dfa_rights
        from api.dfa_automatic import require_policy
        from analysis.activity_dfa import digest, METHOD_VERSION
        from analysis.dfa_source import source_inventory
        from sync.rr_recording import RRRecordingReader, RecordingRef
        from sqlalchemy import and_, or_, exists
        with self.factory() as db:
            query = db.query(Receipt.id, Receipt.created_at).filter_by(disposition='pending').filter(
                ~exists().where(and_(Run.user_id == Receipt.user_id, Run.status.in_(service.ACTIVE))))
            cursor = getattr(self, 'receipt_cursor', None)
            if cursor:
                query = query.filter(or_(Receipt.created_at > cursor[0], and_(Receipt.created_at == cursor[0], Receipt.id > cursor[1])))
            candidates = query.order_by(Receipt.created_at, Receipt.id).limit(service.MAX_ACTIVE_GLOBAL).all()
            if not candidates:
                self.receipt_cursor = None
                return
            db.rollback()
            for candidate in candidates:
                self.receipt_cursor = (candidate.created_at, candidate.id)
                receipt = db.get(Receipt, candidate.id)
                if receipt is None:
                    continue
                receipt_id, owner, ref = receipt.id, receipt.user_id, receipt.recording_ref
                db.rollback()
                with service.owner_write(db, owner):
                    receipt = db.get(Receipt, receipt_id)
                    if not receipt or receipt.disposition != 'pending':
                        continue
                    mode = dfa_rights.account_mode(db, owner)
                    if mode == 'unavailable':
                        continue
                    if mode != 'automatic':
                        receipt.disposition = 'mode_changed'; db.commit(); continue
                    if db.query(Run.id).filter_by(user_id=owner).filter(Run.status.in_(service.ACTIVE)).first():
                        continue
                    try:
                        state = service.storage.authority_state(owner)
                        if state['deleted'] or any(e['scope'] == 'activity' and e['target'] == ref['activity_id']
                            for e in state['events'].values()):
                            raise ValueError('suppressed')
                        policy = require_policy()
                        inventory = source_inventory(list(RRRecordingReader(db).iter_recording(RecordingRef(**ref))), ref)
                        if inventory['outcome'] != 'eligible_metadata_inferred':
                            receipt.disposition = inventory['outcome']; db.commit(); return
                        if dfa_rights.account_mode(db, owner) != 'automatic':
                            continue
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
                        if control is None or not self.allowed or self.retiring or self.pending is not None:
                            return
                        if db.query(Run.id).filter(Run.status.in_(service.ACTIVE)).count() >= service.MAX_ACTIVE_GLOBAL:
                            receipt.disposition = 'capacity_denied'; db.commit(); return
                        from sqlalchemy import func
                        used = db.query(func.coalesce(func.sum(Run.retained_bytes), 0)).filter_by(user_id=owner).scalar()
                        if used + service.MAX_RESULT_BYTES > service.OWNER_QUOTA:
                            receipt.disposition = 'quota_denied'; db.commit(); return
                        if dfa_rights.account_mode(db, owner) != 'automatic':
                            continue
                        grant = dfa_rights.create_grant(db, value)
                        run = Run(user_id=owner, activity_id=ref['activity_id'], snapshot_id=ref['snapshot_id'],
                            parse_id=ref['parse_id'], origin='automatic', grant_id=grant.id, recording_ref=ref,
                            input_digest=digest(['automatic', grant.id]), method_version=METHOD_VERSION,
                            science_contract_digest=policy, phase='compute', execution_epoch=str(control.epoch),
                            retained_bytes=service.MAX_RESULT_BYTES)
                        db.add(run); db.flush()
                        receipt.run_id, receipt.disposition = run.id, 'admitted'
                    except Exception:
                        mode = dfa_rights.account_mode(db, owner)
                        if mode == 'unavailable':
                            continue
                        receipt.disposition = 'mode_changed' if mode != 'automatic' else 'authority_denied'
                    db.commit()
                    return  # At most one expensive admission per reactor turn.

    def acquire_job(self):
        from api import activity_dfa as service, dfa_rights
        with self.factory() as db:
            query = db.query(Run.id, Run.user_id).filter_by(status='queued')
            candidates = query.order_by(Run.created_at, Run.id).limit(service.MAX_ACTIVE_GLOBAL).all()
            db.rollback()
            for candidate in candidates:
                owner, run_id = candidate.user_id, candidate.id
                with service.owner_write(db, owner):
                    control = self._bound(db)
                    run = db.query(Run).filter_by(id=run_id, user_id=owner, status='queued').with_for_update().first()
                    if control is None or self.retiring or self.pending is not None or not self.allowed or time.monotonic() >= self.permission_until: return None
                    if run is None: continue
                    mode = dfa_rights.account_mode(db, owner)
                    if mode == 'unavailable':
                        continue
                    if mode != run.origin:
                        run.status = run.progress = 'cancelled'
                        run.error_code = 'mode_changed'
                        run.generation += 1
                        run.result = run.result_revision = None
                        run.retained_bytes = 0
                        run.lease_token = run.lease_until = None
                        run.completed_at = datetime.utcnow()
                        run.expires_at = run.completed_at + timedelta(days=7)
                        db.query(Receipt).filter_by(run_id=run.id).update({'disposition':'mode_changed'})
                        db.commit()
                        continue
                    if not service._current(db, run):
                        if dfa_rights.permanently_invalid(db, run):
                            run.status=run.progress='failed';run.freshness='stale'
                            run.error_code='authority_invalidated';run.generation+=1
                            run.result=None;run.retained_bytes=0;run.completed_at=datetime.utcnow()
                            run.expires_at=run.completed_at+timedelta(days=7)
                        db.commit()
                        continue
                    # Validation can outlast a renewal or local permission. Do
                    # not consume queued work/recovery for an already denied
                    # acquisition. Refresh the serialized control facts too;
                    # _bound uses populate_existing rather than cached ORM data.
                    if self.retiring or self.pending is not None or not self.allowed or time.monotonic() >= self.permission_until: return None
                    control = self._bound(db)
                    if control is None or self.retiring or self.pending is not None or not self.allowed or time.monotonic() >= self.permission_until: return None
                    if dfa_rights.account_mode(db, owner) != run.origin: return None
                    # This is not a reservation across commit. Work/reactor and
                    # publication retain their independent late-change fences.
                    run.status, run.progress = 'running', 'reading'
                    run.lease_token = str(uuid4())
                    run.execution_epoch = str(control.epoch)
                    run.lease_until = datetime.utcnow() + timedelta(seconds=service.LEASE_SECONDS)
                    value = {'id': run.id, 'owner': owner, 'generation': run.generation, 'epoch': run.execution_epoch,
                             'input': run.input_digest, 'phase': run.phase, 'ref': run.recording_ref, 'origin': run.origin}
                    db.commit()
                    return value
        return None

    def work(self, job, result_queue, cancellation=None):
        """Loading/IPC/publication is off the retirement reactor."""
        from api import activity_dfa as service
        from sync.rr_recording import RRRecordingReader, RecordingRef
        from analysis.activity_dfa import digest
        child = None
        launch_attempted = False
        validating_output = False
        # This event is never cleared/reused by a subsequent job. Direct-step
        # fixtures retain the existing event when no explicit token is supplied.
        cancellation = cancellation if cancellation is not None else self.retired
        cancellation.launch_attempted = False
        started = time.monotonic()
        try:
            with self.factory() as db:
                run = db.query(Run).filter_by(id=job['id'], user_id=job['owner'], generation=job['generation'], status='running').first()
                from api import dfa_rights
                if run is None or not dfa_rights.execution_current(db, run):
                    raise ValueError('authority_changed')
                raw = RRRecordingReader(db).raw(RecordingRef(**job['ref']))
                proof = db.get(service.Confirmation, run.confirmation_id) if run.confirmation_id else None
                manual_proof = {'sensor_ref': proof.sensor_ref, 'rule_fingerprint': proof.rule_fingerprint,
                                'evidence_digest': proof.evidence_digest} if proof else None
                # Durable intent distinguishes recovery of a proven preload
                # interruption from loss of an unacknowledged spawn journal.
                if cancellation.is_set():
                    raise ValueError('permission_expired')
                if db.query(Run).filter_by(id=job['id'], generation=job['generation'], status='running').update(
                        {Run.progress:'launching'}, synchronize_session=False)!=1:
                    raise ValueError('authority_changed')
                db.commit()
            if cancellation.is_set() or not self.allowed or time.monotonic() > self.permission_until:
                raise ValueError('permission_expired')
            if time.monotonic() - started > service.MAX_EXECUTION_SECONDS:
                raise ValueError("execution_time_limit")
            binding = {key: job[key] for key in ('generation','epoch','input')}
            with self.factory() as db:
                current = db.query(Run).filter_by(id=job['id'], user_id=job['owner'], generation=job['generation'], status='running').first()
                if current is None or not dfa_rights.execution_current(db, current):
                    raise ValueError('authority_changed')
            with self.controls() as db:
                control=self._bound(db)
                if control is None: raise ValueError('binding_changed')
                sql_predecessor=deepcopy(control.actor)
                if sql_predecessor and (sql_predecessor.get('state')!='idle'
                        or sql_predecessor.get('incarnation')!=self.identity
                        or sql_predecessor.get('exit_observed_at') is None):
                    raise ValueError('binding_changed')
            with self.physical_mutex:
                if cancellation.is_set() or not self.allowed or time.monotonic() > self.permission_until:
                    raise ValueError("permission_expired")
                local_predecessor=self.lane.actor()
                if local_predecessor and sql_predecessor is not None and local_predecessor!=sql_predecessor:
                    raise ValueError('binding_changed')
                launch_attempted = True
                cancellation.launch_attempted = True
                actor, child = self.lane.launch(binding, authorized=True)
                self.launch_sql_predecessor=(actor['actor_token'],json.dumps(sql_predecessor))
            # Acknowledged local journal is durable before any private bytes flow.
            with self.controls() as db:
                control = self._bound(db)
                if control is None or cancellation.is_set() or dfa_rights.account_mode(db, job['owner']) != job['origin']:
                    raise ValueError('binding_changed')
                previous = control.actor
                predecessor=sql_predecessor
                if previous!=predecessor:
                    raise ValueError('binding_changed')
                guard = self._actor_guard(db, predecessor)
                # Exit publication may win while this I/O call is blocked. A
                # late acknowledgement must not overwrite that receipt/new actor.
                if guard.update({Control.actor:actor}, synchronize_session=False)!=1:
                    raise ValueError('binding_changed')
                db.commit()
            with self.factory() as db:
                current=db.query(Run).filter_by(id=job['id'],user_id=job['owner'],generation=job['generation'],status='running').first()
                if current is None or not dfa_rights.execution_current(db,current):
                    raise ValueError('authority_changed')
            if cancellation.is_set() or not self.allowed or time.monotonic()>self.permission_until:
                raise ValueError('permission_expired')
            payload = {'binding': binding, 'actor_token': actor['actor_token'], 'phase': job['phase'],
                       'raw_fit': base64.b64encode(raw).decode(), 'recording_ref': job['ref'], 'manual_proof': manual_proof, 'origin': job['origin']}
            child.stdin.write(json.dumps(payload, separators=(',', ':')).encode() + b'\n')
            child.stdin.close()
            output = child.stdout.read(MAX_OUTPUT + 2)
            if cancellation.is_set():
                raise ValueError('permission_expired')
            if len(output) > MAX_OUTPUT + 1 or not output.endswith(b'\n'):
                raise ValueError('ipc_output_invalid')
            if len(output) > service.MAX_RESULT_BYTES:
                raise ValueError("result_limit")
            from api import dfa_ipc
            validating_output = True
            value = dfa_ipc.loads(output)
            dfa_ipc.binding(value.get("binding"))
            if (set(value) not in ({'binding','actor_token','inventory','result'},{'binding','actor_token','error'}) or value['binding'] != binding
                    or value['actor_token'] != actor['actor_token']):
                raise ValueError('ipc_binding_changed')
            if 'error' in value:
                if value['error'] not in WORKER_FAILURES: raise ValueError('ipc_output_invalid')
                result_queue.put(('failed',value['error'])); return
            dfa_ipc.result(value['result'], job['phase'])
            result_queue.put(('output', value))
        except Exception as exc:
            safe = str(exc) if str(exc) in SAFE_FAILURES else 'ipc_output_invalid' if validating_output else 'execution_unavailable'
            result_queue.put(('failed' if launch_attempted else 'failed_before_spawn', safe))
        finally:
            # The worker owns these handles. Closing from the retirement thread
            # could block on a BufferedReader's lock and obstruct its watchdog.
            if child is not None:
                for stream in (child.stdin, child.stdout):
                    if stream is not None:
                        try:
                            stream.close()
                        except (OSError, ValueError):
                            pass

    def record_exit(self):
        """Project only the exact verified exit; an existing receipt is idempotent."""
        actor = self.lane.actor()
        pending = self.pending
        if (actor is None or actor.get('state')!='idle' or actor.get('exit_observed_at') is None
                or actor.get('incarnation')!=self.identity
                or actor.get('binding',{}).get('epoch')!=str(self.identity['epoch'])
                or pending and actor!=json.loads(pending.actor_json)):
            raise PhysicalUnavailable('exit_not_observed')
        with self.controls() as db:
            if db.get_bind().dialect.name=='postgresql':
                db.execute(text("SET LOCAL statement_timeout='200ms'"))
                db.execute(text("SET LOCAL lock_timeout='200ms'"))
            control = db.query(Control).filter_by(id=1).populate_existing().first()
            if (control is None or control.incarnation!=self.identity or control.epoch!=self.identity['epoch']
                    or not control.enabled or control.drained):
                raise PhysicalUnavailable('exit_journal_binding_changed')
            previous=deepcopy(control.actor)
            self._exit_predecessor(previous,actor)
            observed_at=time.monotonic()
            already_durable=previous==actor
            if self._actor_guard(db,previous).update({Control.actor:actor},synchronize_session=False)!=1:
                db.rollback()
                raise PhysicalUnavailable('exit_journal_binding_changed')
            db.commit()
            # Same-value CAS also fences a concurrently replaced host/actor on
            # lost-ACK reconciliation. This ACK is for this fresh transaction,
            # never a reconstructed timestamp of the original successful commit.
            return {'kind':'already_durable' if already_durable else 'commit_ack',
                    'at':time.monotonic(),'observed_at':observed_at,'actor_token':actor['actor_token']}

    def finish(self, job, status, value):
        from api import activity_dfa as service
        from analysis.activity_dfa import digest
        with self.factory() as db:
            with service.owner_write(db, job['owner']):
                run = db.query(Run).filter_by(id=job['id'], user_id=job['owner'], generation=job['generation'], status='running').first()
                if run:
                    from api import dfa_rights
                    prior_recoveries = run.recoveries
                    recovery_proposed = False
                    current = dfa_rights.execution_current(db, run) and self._bound(db) is not None
                    if status == 'output' and current:
                        output = value['result']
                        output['source_assurance'] = 'metadata_inferred' if run.origin == 'automatic' else 'user_confirmed'
                        if run.origin == 'automatic' and value['inventory']['outcome'] != 'eligible_metadata_inferred':
                            current = False
                        if current and dfa_rights.account_mode(db, run.user_id) == run.origin:
                            run.result, run.result_revision = output, digest(output)
                            run.status = 'complete' if run.phase == 'compute' else 'awaiting_source_confirmation'
                            run.retained_bytes = len(json.dumps(output).encode())
                    if run.status == 'running':
                        failure = value if status in ('failed','failed_before_spawn') else 'execution_unavailable'
                        retry = (job['origin']=='automatic' and current and
                            failure in TRANSIENT_FAILURES and run.recoveries<1)
                        run.status = 'queued' if retry else 'failed'
                        recovery_proposed = retry
                        if retry: run.recoveries+=1
                        run.error_code = failure
                        run.retained_bytes = 0 if run.status == 'failed' else run.retained_bytes
                    run.progress = run.status
                    run.completed_at = datetime.utcnow() if run.status != 'queued' else None
                    run.expires_at = datetime.utcnow() + timedelta(days=30 if run.status == 'complete' else 7)
                    run.lease_token = run.lease_until = None
                if run:
                    # This final local observation fences mode loss during
                    # validation; it is not atomic with external rule updates.
                    mode = dfa_rights.account_mode(db, run.user_id)
                    if (run.status in ('complete', 'awaiting_source_confirmation') or recovery_proposed) and mode != run.origin:
                        run.result = run.result_revision = None
                        run.status = run.progress = 'failed'
                        run.error_code = 'mode_unavailable' if mode == 'unavailable' else 'mode_changed'
                        run.retained_bytes = 0
                        if recovery_proposed:
                            # A recovery slot is consumed only by an authorized
                            # continuation, never by a fenced running attempt.
                            run.recoveries = prior_recoveries
                            run.completed_at = datetime.utcnow()
                    fields = ('result','result_revision','status','progress','retained_bytes','recoveries',
                              'error_code','completed_at','expires_at','lease_token','lease_until')
                    values = {getattr(Run,key):getattr(run,key) for key in fields}
                    db.expunge(run)  # Do not let an id-only ORM flush cross a generation fence.
                    if db.query(Run).filter_by(id=job['id'],user_id=job['owner'],generation=job['generation'],
                            status='running',execution_epoch=job.get('epoch',str(self.identity['epoch'])),
                            input_digest=job.get('input',run.input_digest)).update(values,synchronize_session=False)!=1:
                        raise PhysicalUnavailable('finish_run_binding_changed')
                control = self._bound(db)
                if control is None: raise PhysicalUnavailable('finish_control_binding_changed')
                previous=deepcopy(control.actor)
                actor=self.lane.actor()
                if self.pending and actor!=json.loads(self.pending.actor_json):
                    raise PhysicalUnavailable('finish_actor_binding_changed')
                if actor is not None:
                    if actor.get('state')!='idle' or actor.get('exit_observed_at') is None:
                        raise PhysicalUnavailable('finish_exit_not_observed')
                    self._exit_predecessor(previous,actor)
                elif previous is not None:
                    raise PhysicalUnavailable('finish_actor_binding_changed')
                if self.pending and previous!=actor:
                    raise PhysicalUnavailable('finish_actor_binding_changed')
                if self._actor_guard(db,previous).update({Control.actor:actor},synchronize_session=False)!=1:
                    raise PhysicalUnavailable('finish_actor_binding_changed')
                db.commit()

    def reconcile_recovery(self):
        """Commit an old actor's verified exit before admitting replacement work."""
        self.lane.authorize_recovery()
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
                self.finish(job, 'failed', 'restart_interrupted')
        # With the supervisor/physical guards held and no uncertain actor,
        # remaining same-epoch running rows are proven interrupted before spawn.
        with self.factory() as db:
            interrupted=[{'id':run.id,'owner':run.user_id,'generation':run.generation,'origin':run.origin}
                for run in db.query(Run).filter_by(status='running',execution_epoch=str(self.identity['epoch'])).all()]
        for job in interrupted:
            with self.factory() as db:
                pending=db.get(Run,job['id'])
                if pending and pending.progress!='reading':
                    raise PhysicalUnavailable('missing_launch_journal')
            self.finish(job,'failed_before_spawn','restart_interrupted')

    def run(self):
        with self.controls() as db:
            if self._bound(db) is None:
                raise PhysicalUnavailable('host_not_bound')
        self.reconcile_recovery()
        threading.Thread(target=self.renew, daemon=True, name='dfa-control').start()
        work_thread, outputs, job = None, None, None
        try:
            while not self.stop.wait(.01):
                self.cleanups = [thread for thread in self.cleanups if thread.is_alive()]
                if job:
                    ready = not outputs.empty()
                    actor_before = self.lane.actor()
                    with self.lock:
                        expired = time.monotonic() > self.permission_until or not self.allowed
                        decision = deepcopy(self.permission_decision)
                    from api.activity_dfa import MAX_EXECUTION_SECONDS
                    timed_out = time.monotonic() - launched_at > MAX_EXECUTION_SECONDS
                    if expired or timed_out or ready:
                        trigger_mode = bool(expired and decision and decision['reason']=='mode_changed'
                            and decision['job']=={k:job[k] for k in ('id','generation','epoch','input')}
                            and _same_actor(decision['actor'],actor_before))
                        status, value = outputs.get() if ready else ('failed','execution_unavailable')
                        if status!='failed_before_spawn' and (expired or timed_out):
                            status,value = ('failed','execution_time_limit') if timed_out else ('failed','mode_changed') if trigger_mode else ('failed','permission_expired')
                        chosen_value_json=json.dumps(value)
                        with self.lock:
                            self.retiring=True
                            self.renewal_phase+=1
                            self.allowed=False
                        self.retired.set()
                        cancellation.set()
                        with self.physical_mutex:
                            self.lane.retire()
                        # Physical retirement is proved independently. Cancelled
                        # I/O has no permission to launch or publish, and its
                        # private queue is discarded rather than joined here.
                        if work_thread.is_alive():
                            self.cleanups.append(work_thread)
                        actor = self.lane.actor()
                        if not (actor and actor.get('binding')=={key:job[key] for key in ('generation','epoch','input')}):
                            if (getattr(cancellation,'launch_attempted',False) or actor and actor.get('state')!='idle'):
                                raise PhysicalUnavailable('launch_exit_uncertain')
                        self.pending=PendingFinalization(json.dumps(job),json.dumps(actor),
                            self.launch_sql_predecessor[1] if actor and
                            getattr(self,'launch_sql_predecessor',(None,))[0]==actor.get('actor_token') else
                            getattr(self.lane,'launch_predecessor_json','null') if actor and
                            getattr(self.lane,'launch_token',None)==actor.get('actor_token') else 'null',status,
                            chosen_value_json,cancellation,time.monotonic())
                        self._finalize_pending()
                        job = None
                elif self.allowed and time.monotonic() < self.permission_until:
                    if len(self.cleanups)>=2:
                        continue
                    # Preserve receipt loading while post-exit I/O cleanup is
                    # pending; bounded continuations never select by origin.
                    if not self.cleanups:
                        self.admit_completion()
                    job = self.acquire_job()
                    if job:
                        outputs = queue.Queue(maxsize=1)
                        with self.lock:
                            self.active = job
                        self.retired.clear()
                        cancellation = threading.Event()
                        launched_at = time.monotonic()
                        work_thread = threading.Thread(target=self.work, args=(job, outputs, cancellation), daemon=True)
                        work_thread.start()
        finally:
            self.stop.set()
            self.allowed = False
            if job:
                cancellation.set()
            with self.physical_mutex:
                self.lane.retire()
                self.lane.close()


def retire_before_initialization(identity=None, directory=None):
    """Recover only previously granted local retirement authority, without DB/SDK."""
    identity = identity or incarnation()
    directory = directory or Path('/tmp') / ('praxys-dfa-' + str(os.getuid()) + '-' + identity['incarnation'])
    lane = Lane(directory, identity)
    try:
        if lane.has_recovery_authority():
            lane.recover(authorized=True)
        elif lane.actor() and lane.actor().get('state')!='idle':
            raise PhysicalUnavailable('recovery_not_authorized')
        return lane
    except Exception:
        lane.close()
        raise


def main():
    if os.environ.get('PRAXYS_DFA_SUPERVISOR_ENABLED', '').lower() != 'true':
        return
    identity = incarnation()
    lane = retire_before_initialization(identity)
    from db import session
    import asyncio
    from api.statsig_client import init_statsig, shutdown_statsig
    try:
        # The registered old group is already gone before either cold path.
        session.init_db()
        supervisor = Supervisor(session.SessionLocal, control_factory(), identity, lane.directory, lane=lane)
        import signal
        signal.signal(signal.SIGTERM, lambda signum, frame: supervisor.stop.set())
        signal.signal(signal.SIGINT, lambda signum, frame: supervisor.stop.set())
        asyncio.run(init_statsig())
        try:
            supervisor.run()
        finally:
            asyncio.run(shutdown_statsig())
    finally:
        lane.close()


if __name__ == '__main__':
    main()
