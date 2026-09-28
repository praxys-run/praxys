"""Read-only candidate guard-denial check on the isolated validation runner."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

candidate = Path(os.environ['CANDIDATE_ROOT']).resolve()
sys.path.insert(0, str(candidate))
from analysis.evidence_registry import load_science_registry
from analysis.science_implementation_stop import load_implementation_stops
from api.activity_dfa import require_policy
from fastapi import HTTPException

subject = os.environ['ACTIVATION_SUBJECT']
contract_digest = os.environ['ACTIVATION_CONTRACT']
if subject != 'sdr-activity-dfa-alpha1-v1':
    raise ValueError('This bounded regression checks the actual DFA policy guard')
registry = load_science_registry(candidate / 'data/science')
stops = [stop for stop in load_implementation_stops(registry.science_dir)
         if stop.subject_id == subject and stop.active_contract_digest == contract_digest]
if len(stops) != 1:
    raise ValueError('Candidate must preserve exactly one valid terminal subject stop')
try:
    require_policy()
except HTTPException as error:
    if error.status_code != 503 or error.detail != 'DFA_SCIENCE_POLICY_INACTIVE':
        raise AssertionError('Candidate guard did not report the expected denied policy') from error
else:
    raise AssertionError('Stopped implementation was reactivated by candidate code')
print(json.dumps({'subject_id':subject, 'contract_digest':contract_digest, 'stop_digest':stops[0].stop_digest, 'candidate_guard_result':'denied'}, sort_keys=True))
