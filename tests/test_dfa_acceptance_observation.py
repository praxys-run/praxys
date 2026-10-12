"""Bounded real service, phase, response-error and physical evidence negatives.

Evidence mutations are applied only to copies AFTER actual accepted service;
these cases never count as operational/preemption profile observations.
"""
from copy import deepcopy
import time

import pytest
from fastapi import HTTPException

from api import activity_dfa as service
from db.models import ActivityDFARun as Run
from tests.test_activity_dfa import store
from tests.test_dfa_origins import both_origins
from tests.test_dfa_capacity_outcomes import outcome_cell, attempt, observe
from tests.test_dfa_admission_contention import new_submission_attempt
from tests.dfa_capacity_measurement import observed_requests, fresh_physical_eligibility, observe_acceptance
from tests.dfa_boundary_evidence import safe_binding,boundary_junit

pytestmark=pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)


def completed_idle(cell):
    cell.start(False)
    requests=observed_requests(cell.factory,supervisor=cell.supervisor)
    admitted,entry=attempt(cell,requests,fresh_physical_eligibility(cell.factory,cell.owner,cell.supervisor))
    assert admitted,entry
    result=observe(cell,admitted,entry)
    assert result['service_success'] and result['manual_payload_handshake'] and result['manual_physical_exit'] and result['manual_durable_available_at'],cell.diagnostic.compact(alive=cell.worker.is_alive())
    return admitted,entry,result


@pytest.mark.parametrize('defect',['missing_manual_exit','missing_manual_availability','overlap'])
def test_actual_complete_service_requires_physical_and_durable_reuse_proof(outcome_cell,defect):
    c=outcome_cell;admitted,entry,result=completed_idle(c)
    transitions=deepcopy(c.transitions);available=dict(c.available)
    token=result['manual_actor']['actor_token']
    if defect=='missing_manual_exit':
        transitions=[a for a in transitions if not(a['actor_token']==token and a['state']=='idle')]
    elif defect=='missing_manual_availability':available.pop(token)
    else:
        launch=next(a for a in transitions if a['actor_token']==token and a['state']=='launching')
        launch['launch_at']=min(available.values())-1  # Deliberately invalid recorded overlap.
    copied=deepcopy(entry)
    negative=observe_acceptance(c.factory,c.owner,admitted,copied,c.manual_input,c.evidence,
        transitions,available,time.monotonic()+.1,c.errors)
    assert negative['authorization_current'] is True
    assert negative['service']=='physical_evidence_insufficient' and not negative['service_success']
    assert not negative['required_preemption'],negative
    if defect=='overlap':assert negative['reuse_violations'],negative
    result['deliberately_mutated_physical_negative']={'defect':defect,'observation':negative}
    assert entry['accepted_observation'] is result and result['service_success']


def test_genuine_withdrawal_after_completion_blocks_authorized_success(outcome_cell):
    c=outcome_cell;admitted,entry,result=completed_idle(c)
    service.storage.record_negative(c.owner,'withdrawal','origin','manual')
    negative=observe_acceptance(c.factory,c.owner,admitted,deepcopy(entry),c.manual_input,c.evidence,
        c.transitions,c.available,time.monotonic()+.2,c.errors)
    assert not negative['service_success'] and not negative['required_preemption'],negative
    assert negative['manual_actor'] and negative['manual_physical_exit'],negative
    result['later_genuine_withdrawal_observation']=negative


@pytest.mark.parametrize('phase',['prepare','compute'])
def test_new_submit_postcommit_503_is_accepted_and_fully_observed(outcome_cell,monkeypatch,phase):
    c=outcome_cell
    # Preserve the actual confirmation for compute; prepare gets a new real
    # two-phase request. No synthetic child result or grant is supplied.
    with c.factory() as db:
        old=db.get(Run,c.manual['id']);confirmation=old.confirmation_id
        db.query(Run).filter_by(user_id=c.owner,origin='manual',phase=phase).delete(synchronize_session=False)
        db.commit();catalog=service.catalog(db,c.owner,'123')
    c.start(False)
    from api import activity_dfa_dispatch
    def response_error():raise HTTPException(503,'DFA_CAPACITY_UNAVAILABLE')
    requests=observed_requests(c.factory,supervisor=c.supervisor)
    with monkeypatch.context() as scoped:
        scoped.setattr(activity_dfa_dispatch,'wake',response_error)
        admitted,entry=new_submission_attempt(requests,c.owner,catalog,confirmation if phase=='compute' else None,
            c.attempts,{'phase':phase,'eligibility':fresh_physical_eligibility(c.factory,c.owner,c.supervisor)})
    c.diagnostic.note('admission_return',job=safe_binding(admitted),
                      outcome=entry.get('outcome'),http_status=entry.get('http_status'))
    assert admitted,entry
    with c.factory() as db:manual_input=db.get(Run,admitted['id']).input_digest
    expected='awaiting_source_confirmation' if phase=='prepare' else 'complete'
    result=observe_acceptance(c.factory,c.owner,admitted,entry,manual_input,c.evidence,c.transitions,
        c.available,c.deadline,c.errors,terminal_status=expected)
    c.retain(admitted,result)
    assert entry['outcome']=='accepted_error' and entry['http_status']==503,c.diagnostic.compact()
    assert result['service_success'] and result['authorization_current'] and result['manual_payload_handshake'],c.diagnostic.compact(alive=c.worker.is_alive())
    assert result['manual_actor'] and result['manual_physical_exit'] and result['manual_durable_available_at'],result
    assert not result['reuse_violations'] and result['response_outcome']=='accepted_error',result
    assert not result['required_preemption']  # These are idle service/error-accounting cells.
    if phase=='prepare':
        # Actual authorized preparation must contain evidence and sensors. A
        # metadata-only read observation cannot substitute for that service.
        actual_read=service.read_run
        def metadata_only(*args,**kwargs):
            view=actual_read(*args,**kwargs)
            return {k:v for k,v in view.items() if k not in ('sensors','evidence_digest')}
        monkeypatch.setattr(service,'read_run',metadata_only)
        negative=observe_acceptance(c.factory,c.owner,admitted,deepcopy(entry),manual_input,c.evidence,
            c.transitions,c.available,time.monotonic()+.2,c.errors,terminal_status=expected)
        assert negative['service']=='authority_denied' and not negative['service_success'],negative
        assert not negative['required_preemption']
        result['deliberately_incomplete_preparation_read']=negative
