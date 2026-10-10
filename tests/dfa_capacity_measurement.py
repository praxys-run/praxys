"""Prospective capacity observations; never alters runtime admission or renewal."""
from copy import deepcopy
import sys
import time

from sqlalchemy import event
from sqlalchemy.orm import Query, Session, sessionmaker
from api import activity_dfa as service
from api.dfa_supervisor import manual_admission
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run


def observed_requests(factory, before_locked_read=None, *, supervisor=None):
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
                if supervisor is not None:
                    record['locked_admission']['physical_actor']=deepcopy(supervisor.lane.actor())
                    record['locked_admission']['physical_observed_at']=time.monotonic()
            return row
    class AdmissionSession(Session):
        def commit(self):
            record = self.info.get('capacity_admission_record')
            caller=sys._getframe(1)
            request = record is not None and caller.f_code in (service.change_run.__code__,service.submit.__code__)
            if request:
                record['commit_begin'] = time.monotonic()
                subject=caller.f_locals.get('run')
                if subject is not None:
                    record['transaction_subject']={k:getattr(subject,k) for k in ('id','generation','admission_id','execution_epoch','input_digest','phase')}
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
                       committed_exits, overall_deadline, errors, *, terminal_status="complete",
                       allow_existing_retirement=False):
    """Every accepted request obtains an outcome before any cohort assertion."""
    outcome = {'admission_id': admitted['admission_id'], 'generation': admitted['generation'],
               'service': 'observing', 'classification': 'unproved', 'required_preemption': False}
    entry['accepted_observation'] = outcome
    deadline = min(time.monotonic()+15, overall_deadline)
    while True:
        with factory() as db:
            row = db.get(Run, admitted['id'])
            state = {'status': row.status, 'generation': row.generation, 'error_code': row.error_code,
                     'execution_epoch':row.execution_epoch} if row else {'status':'erased'}
            if row and row.status==terminal_status and row.generation==admitted['generation']:
                try:
                    view = service.read_run(db, owner, '123', row.id, 0, 120)
                    outcome['authorization_current'] = (view['freshness']=='current' and view['status']==terminal_status
                        and view['id']==admitted['id'] and view['generation']==admitted['generation']
                        and (bool(view['result_revision']) if terminal_status=='complete' else
                             row.phase=='prepare' and bool(view.get('evidence_digest')) and bool(view.get('sensors'))))
                    outcome['service'] = terminal_status if outcome['authorization_current'] else 'authority_denied'
                    outcome['authorized_read']={'id':view['id'],'generation':view['generation'],'status':view['status'],'freshness':view['freshness']}
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
    outcome['last_state']=state
    outcome['service_success']=outcome['service']==terminal_status
    outcome['terminal_expected']=terminal_status
    outcome['service_observed_at']=time.monotonic()
    outcome['response_outcome']=entry.get('outcome')
    starts = [a for a in transitions if a.get('state')=='occupied' and a.get('binding')=={
        'generation':admitted['generation'], 'epoch':state.get('execution_epoch'), 'input':manual_input}]
    # Even a failed/unauthorized accepted run must retain physical outcome.
    # Terminal SQL publication alone is not physical/durable availability.
    while starts and starts[-1]['actor_token'] not in committed_exits and time.monotonic()<deadline:
        time.sleep(.005)
    manual_actor=starts[-1] if starts else None
    manual_exit=next((a for a in reversed(transitions) if manual_actor and
        a.get('actor_token')==manual_actor['actor_token'] and a.get('state')=='idle'),None)
    outcome['manual_physical_exit']=deepcopy(manual_exit)
    outcome['manual_durable_available_at']=committed_exits.get(manual_actor['actor_token']) if manual_actor else None
    outcome['manual_input_digest']=manual_input
    outcome['manual_actor']=deepcopy(manual_actor)
    outcome['post_popen_start_upper_seconds']=(starts[-1]['process_start_observed_at']-entry['before_monotonic']) if starts else None
    violations=[]
    for previous, current in zip(transitions, transitions[1:]):
        if current.get('state')=='launching' and current.get('actor_token')!=previous.get('actor_token'):
            available=committed_exits.get(previous.get('actor_token'))
            if (previous.get('state')!='idle' or available is None
                    or current['launch_at']<max(previous.get('exit_observed_at',float('inf')),available)):
                violations.append({'previous':deepcopy(previous), 'current':deepcopy(current)})
    outcome['reuse_violations']=violations
    eligibility=entry.get('eligibility', {'actor':entry['readiness']['actor']})
    actor=eligibility['actor']; locked=entry.get('locked_admission', {}).get('actor')
    outcome['locked_admission']=deepcopy(entry.get('locked_admission'))
    outcome['commit_bracket']=[entry.get('commit_begin'),entry.get('commit_ack')]
    outcome['admission_receipt_valid']=_admission_binding_matches(outcome,admitted,entry)
    if not outcome['admission_receipt_valid']:
        outcome['classification']='insufficient_admission_evidence'
    elif actor and actor.get('state') in ('occupied','retiring'):
        classify_occupied(outcome, admitted, actor, locked, entry, evidence, committed_exits,
                          allow_existing_retirement=allow_existing_retirement)
        outcome['required_preemption']=bool(outcome['classification']=='causal_preemption'
            and outcome['service_success'] and starts and not violations
            and outcome.get('retirement_within_budget') is True)
    elif (actor and actor.get('state')=='idle' and locked and locked.get('state')=='idle'
            and all(actor.get(k)==locked.get(k) for k in ('actor_token','binding','incarnation')) and entry.get('commit_ack') is not None):
        outcome['classification']='idle_service'
    elif actor is None and locked is None and entry.get('locked_admission') is not None and entry.get('commit_ack') is not None:
        outcome['classification']='idle_service'
        outcome['no_prior_actor']=True
    if outcome['service_success'] and (not starts or violations or not manual_exit or outcome['manual_durable_available_at'] is None):
        outcome['service']='physical_evidence_insufficient';outcome['service_success']=False;outcome['required_preemption']=False
    return outcome


def classify_occupied(outcome, admitted, actor, locked, entry, evidence, committed_exits, *, allow_existing_retirement=False):
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
    same_keys=('actor_token','binding','incarnation','identity')
    if not all(_physical_binding_complete(a) for a in (actor,locked)):
        outcome['evidence_failure']='incomplete_actor_binding'; return
    if (not locked or any(actor.get(k) is None or locked.get(k)!=actor.get(k) for k in same_keys)
            or actor.get('state') not in ('occupied','retiring') or locked.get('state') not in ('occupied','retiring')
            or (locked.get('state')!=actor.get('state') and not allow_existing_retirement)):
        outcome['evidence_failure']='locked_actor_mismatch'; return
    begin=entry.get('commit_begin'); call=entry.get('sql_commit_call_begin'); ack=entry.get('commit_ack')
    if begin is None or call is None or ack is None or not entry['before_monotonic']<=begin<=call<=ack:
        outcome['evidence_failure']='missing_or_invalid_commit_bracket'; return
    actual_actor=retirement.get('actor_snapshot')
    if not _physical_binding_complete(actual_actor) or any(actual_actor.get(k)!=actor.get(k) for k in same_keys):
        outcome['evidence_failure']='retirement_actor_mismatch';return
    if not _admission_binding_matches(outcome,admitted,entry):
        outcome['evidence_failure']='admission_binding_mismatch';return
    if (exit_at is None or available is None or
            not retirement['started_monotonic']<=exit_at<=available
            or (retirement['started_monotonic']<entry['before_monotonic'] and not allow_existing_retirement)):
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
    elif allow_existing_retirement and _already_retiring(actor,entry,retirement):
        outcome.update(classification='already_retiring_service',retirement_order={
            'retirement_started':retirement['started_monotonic'],'persisted_term_dispatch':deepcopy(retirement['dispatches'][0]),
            'sql_commit_call_begin':call,'predicate':'persisted_matching_journal_and_successful_live_group_TERM_before_dbapi_commit_call'})
    elif exit_at<=call:
        # Physical exit observed BEFORE the DBAPI commit invocation proves a
        # precommit retirement. Exit merely before ACK does not prove a race.
        outcome.update(classification='retirement_race',retirement_order={
            'physical_exit_observed_at':exit_at,'sql_commit_call_begin':call,
            'commit_ack':ack,'predicate':'verified_exit_before_dbapi_commit_call'})
    else:
        outcome['evidence_failure']='retirement_commit_order_unproved'


def _physical_binding_complete(actor):
    if not isinstance(actor,dict) or actor.get('actor_token') is None:return False
    fields={'binding':('generation','epoch','input'), 'identity':('pid','pgid','start'),
            'incarnation':('resource','slot','instance','source','incarnation','epoch','boot','namespace')}
    return all(isinstance(actor.get(group),dict) and all(actor[group].get(k) is not None for k in keys)
               for group,keys in fields.items())


def _already_retiring(actor,entry,retirement):
    """Successful real persisted journal AND completed live-group TERM before COMMIT invocation."""
    dispatches=retirement.get('dispatches',[])
    if len(dispatches)!=1:return False
    dispatch=dispatches[0];persisted=dispatch.get('journal_persisted_at');term=dispatch.get('term_dispatch_completed_at')
    physical=dispatch.get('actor',{});identity=actor.get('identity')
    return bool(identity and persisted is not None and term is not None
        and physical.get('state')=='retiring'
        and all(physical.get(k)==actor.get(k) for k in ('actor_token','binding','incarnation','identity'))
        and dispatch.get('dispatch_identity')==identity and dispatch.get('pgid')==identity['pgid']
        and all(identity.get(k) is not None for k in ('pid','pgid','start'))
        and dispatch.get('live_members') and all(
            all(m.get(k)==identity[k] for k in ('pid','pgid','start')) and m.get('state') not in ('Z','X')
            for m in dispatch['live_members'])
        and retirement['allowed_at_start'] is False
        and retirement['started_monotonic']<=persisted<=term<=entry['sql_commit_call_begin'])


def fresh_physical_eligibility(factory,owner,supervisor):
    value=workload_eligibility(factory,owner);value['sql_actor']=value['actor']
    value['actor']=deepcopy(supervisor.lane.actor());value['physical_observed_at']=time.monotonic()
    value['eligible']=bool(value['eligible'] and value['actor'] and value['actor'].get('state')=='occupied'
        and all(value['actor'].get(k)==value['sql_actor'].get(k) for k in ('actor_token','binding','incarnation')))
    return value


def lifecycle_observations(supervisor,monkeypatch):
    """Actual journal transitions and post-commit durable availability, no authority mutation."""
    initial=supervisor.lane.actor()
    transitions=[deepcopy(initial)] if initial else [];availability={};actual_record=supervisor.lane.record;actual_exit=supervisor.record_exit
    def record(actor):
        actual_record(actor);transitions.append(deepcopy(actor))
    def exited():
        actual_exit();actor=supervisor.lane.actor()
        if actor and actor.get('state')=='idle':availability[actor['actor_token']]=time.monotonic()
    monkeypatch.setattr(supervisor.lane,'record',record);monkeypatch.setattr(supervisor,'record_exit',exited)
    return transitions,availability


def _admission_binding_matches(outcome,admitted,entry):
    subject=entry.get('transaction_subject',{});durable=entry.get('after_durable',{})
    # Required for a CURRENT accepted manual admission, although the SQL model
    # permits null admission/epoch for historical or other-origin rows. The
    # acknowledged projection intentionally contains only id/gen/admission;
    # epoch/input come from the transaction and durable snapshot. Phase/status
    # and timestamps are separate service/timeline metadata, not this binding.
    identity=('id','generation','admission_id')
    binding=identity+('execution_epoch','input_digest')
    for record,fields in ((admitted,identity),(subject,binding),(durable,binding),
                          (outcome,('manual_input_digest',))):
        if not isinstance(record,dict) or any(k not in record or record[k] is None for k in fields):
            return False
    return bool(entry.get('acceptance_consistent',True)
        and entry.get('metadata_response_valid',True)
        and all(subject.get(k)==admitted.get(k)==durable.get(k) for k in ('id','generation','admission_id'))
        and subject.get('execution_epoch')==durable.get('execution_epoch')
        and subject.get('input_digest')==durable.get('input_digest')==outcome['manual_input_digest'])
