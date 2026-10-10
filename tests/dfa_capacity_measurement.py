"""Prospective capacity observations; never alters runtime admission or renewal."""
from copy import deepcopy
import sys
import time

from sqlalchemy import event
from sqlalchemy.orm import Query, Session, sessionmaker
from api import activity_dfa as service
from api.dfa_supervisor import manual_admission
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run


def observed_requests(factory, before_locked_read=None):
    """Capture the already-read locked actor and actual commit/ACK bracket."""
    class AdmissionQuery(Query):
        def first(self):
            caller = sys._getframe(1)
            if caller.f_code is manual_admission.__code__ and before_locked_read is not None:
                before_locked_read(self.session)
            row = super().first()
            record = self.session.info.get('capacity_admission_record')
            if record is not None and caller.f_code is manual_admission.__code__ and row is not None:
                record['locked_admission'] = {'observed_at': time.monotonic(), 'actor': deepcopy(row.actor),
                    'epoch': row.epoch, 'incarnation': deepcopy(row.incarnation),
                    'manual_sequence_before': row.manual_sequence}
            return row
    class AdmissionSession(Session):
        def commit(self):
            record = self.info.get('capacity_admission_record')
            request = record is not None and sys._getframe(1).f_code is service.change_run.__code__
            if request: record['commit_begin'] = time.monotonic()
            connection = self.connection() if request else None
            def committing(connection):
                # SQLAlchemy invokes this before the DBAPI COMMIT call. This
                # proves earlier exits precede commit, never its server time.
                record['sql_commit_call_begin'] = time.monotonic()
            if request: event.listen(connection, 'commit', committing)
            try:
                super().commit()
            except Exception as exc:
                if request: record['commit_exception_class'] = type(exc).__name__
                raise
            finally:
                if request: event.remove(connection, 'commit', committing)
            if request: record['commit_ack'] = time.monotonic()
    return sessionmaker(class_=AdmissionSession, query_cls=AdmissionQuery, **factory.kw)


def workload_eligibility(factory, owner):
    """No pulse-duration selector: observe actor and exact running origin binding."""
    with factory() as db:
        control = db.get(Control, 1)
        actor = deepcopy(control.actor) if control else None
        automatic = [{'id': r.id, 'status': r.status, 'generation': r.generation,
            'input': r.input_digest, 'epoch': r.execution_epoch, 'error_code': r.error_code,
            'recoveries': r.recoveries} for r in db.query(Run.id,Run.status,Run.generation,Run.input_digest,Run.execution_epoch,Run.error_code,Run.recoveries).filter_by(user_id=owner, origin='automatic')]
        matching = next((r for r in automatic if actor and r['status']=='running'
            and actor.get('binding')=={k:r[k] for k in ('generation','epoch','input')}), None)
        eligible = bool(control and actor and actor.get('state')=='occupied' and matching
            and actor.get('incarnation')==control.incarnation and actor['binding']['epoch']==str(control.epoch))
        return {'at': time.monotonic(), 'actor': actor, 'eligible': eligible, 'workload': matching,
                'automatic_states': automatic}


def observe_acceptance(factory, owner, admitted, entry, manual_input, evidence, transitions,
                       committed_exits, overall_deadline, errors):
    """Every accepted request obtains an outcome before any cohort assertion."""
    outcome = {'admission_id': admitted['admission_id'], 'generation': admitted['generation'],
               'service': 'observing', 'classification': 'unproved', 'required_preemption': False}
    entry['accepted_observation'] = outcome
    deadline = min(time.monotonic()+15, overall_deadline)
    while True:
        with factory() as db:
            row = db.get(Run, admitted['id'])
            state = {'status': row.status, 'generation': row.generation, 'error_code': row.error_code} if row else {'status':'erased'}
            if row and row.status=='complete' and row.generation==admitted['generation']:
                try:
                    view = service.read_run(db, owner, '123', row.id, 0, 120)
                    outcome['authorization_current'] = view['freshness']=='current' and bool(view['result_revision'])
                    outcome['service'] = 'complete' if outcome['authorization_current'] else 'authority_denied'
                except Exception as exc:
                    outcome['service']='authority_check_failed'
                    outcome['authority_exception_class']=type(exc).__name__
                break
        outcome['last_state'] = state
        if state['status'] in ('failed','cancelled','unavailable','erased') or state.get('generation')!=admitted['generation']:
            outcome['service']='failed'; break
        if time.monotonic()>=deadline:
            outcome['service']='timeout'; outcome['supervisor_errors']=list(errors); break
        time.sleep(.01)
    outcome['service_observed_at']=time.monotonic()
    starts = [a for a in transitions if a.get('state')=='occupied' and a.get('binding')=={
        'generation':admitted['generation'], 'epoch':entry['after_durable']['execution_epoch'], 'input':manual_input}]
    outcome['manual_actor']=deepcopy(starts[-1]) if starts else None
    outcome['post_popen_start_upper_seconds']=(starts[-1]['process_start_observed_at']-entry['before_monotonic']) if starts else None
    violations=[]
    for previous, current in zip(transitions, transitions[1:]):
        if current.get('state')=='launching' and current.get('actor_token')!=previous.get('actor_token'):
            if previous.get('state')!='idle' or current['launch_at']<previous.get('exit_observed_at',float('inf')):
                violations.append({'previous':deepcopy(previous), 'current':deepcopy(current)})
    outcome['reuse_violations']=violations
    eligibility=entry.get('eligibility', {'actor':entry['readiness']['actor']})
    actor=eligibility['actor']; locked=entry.get('locked_admission', {}).get('actor')
    outcome['locked_admission']=deepcopy(entry.get('locked_admission'))
    outcome['commit_bracket']=[entry.get('commit_begin'),entry.get('commit_ack')]
    if actor and actor.get('state')=='occupied':
        classify_occupied(outcome, admitted, actor, locked, entry, evidence, committed_exits)
        outcome['required_preemption']=bool(outcome['classification']=='causal_preemption'
            and outcome['service']=='complete' and starts and not violations
            and outcome.get('retirement_within_budget') is True)
    elif (actor and actor.get('state')=='idle' and locked and locked.get('state')=='idle'
            and actor['actor_token']==locked['actor_token'] and entry.get('commit_ack') is not None):
        outcome['classification']='idle_service'
    elif actor is None and locked is None and entry.get('locked_admission') is not None and entry.get('commit_ack') is not None:
        outcome['classification']='idle_service'
        outcome['no_prior_actor']=True
    if outcome['service']=='complete' and (not starts or violations):
        outcome['service']='physical_evidence_insufficient';outcome['required_preemption']=False
    return outcome


def classify_occupied(outcome, admitted, actor, locked, entry, evidence, committed_exits):
    """Affirmative ordering only; failed causal checks never establish a race."""
    outcome['classification']='insufficient_retirement_evidence'
    matches=[r for r in evidence.retirements if r['actor_token']==actor['actor_token']]
    outcome['actor_retirements']=deepcopy(matches)
    if len(matches)!=1:
        outcome['evidence_failure']='nonunique_or_missing_retirement'; return
    retirement=matches[0]
    available=committed_exits.get(actor['actor_token'])
    exit_at=retirement.get('exit_observed_at')
    if exit_at is not None:
        outcome['physical_exit_upper_seconds']=exit_at-entry['before_monotonic']
    if available is not None:
        outcome['durable_availability_upper_seconds']=available-entry['before_monotonic']
    # Snapshot and serialized admission must identify precisely the same actor,
    # including physical incarnation and the full computation binding.
    if not locked or any(locked.get(k)!=actor.get(k) for k in ('actor_token','binding','incarnation','state')):
        outcome['evidence_failure']='locked_actor_mismatch'; return
    begin=entry.get('commit_begin'); call=entry.get('sql_commit_call_begin'); ack=entry.get('commit_ack')
    if begin is None or call is None or ack is None or not entry['before_monotonic']<=begin<=call<=ack:
        outcome['evidence_failure']='missing_or_invalid_commit_bracket'; return
    if (exit_at is None or available is None or
            not entry['before_monotonic']<=retirement['started_monotonic']<=exit_at<=available):
        outcome['evidence_failure']='missing_or_invalid_durable_retirement'; return
    outcome['retirement_within_budget']=max(outcome['physical_exit_upper_seconds'],
        outcome['durable_availability_upper_seconds'])<=5
    if not outcome['retirement_within_budget']:
        outcome['evidence_failure']='occupied_retirement_over_budget'; return
    priority=retirement.get('priority_invalidation')
    if priority is not None:
        try:
            proof=evidence.accepted_preemption(admitted,actor,entry)
            assert proof['priority_invalidation']['observed_monotonic']>=begin
        except AssertionError:
            outcome['evidence_failure']='invalid_committed_priority'; return
        outcome.update(classification='causal_preemption',causal_receipt=deepcopy(proof))
    elif exit_at<=call:
        # Physical exit observed BEFORE the DBAPI commit invocation proves a
        # precommit retirement. Exit merely before ACK does not prove a race.
        outcome.update(classification='retirement_race',retirement_order={
            'physical_exit_observed_at':exit_at,'sql_commit_call_begin':call,
            'commit_ack':ack,'predicate':'verified_exit_before_dbapi_commit_call'})
    else:
        outcome['evidence_failure']='retirement_commit_order_unproved'
