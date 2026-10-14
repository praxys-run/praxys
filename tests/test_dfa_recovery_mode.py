"""Final recovery-mode observation, actual SDK/projected-policy/SQL boundaries."""
from copy import deepcopy
import json

import pytest

from api import dfa_rights
from db.models import ActivityDFARun as Run, ActivityDFAControl as Control
from tests.test_activity_dfa import store
from tests.test_dfa_origins import both_origins
from tests.test_dfa_review_repairs import automatic_job


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
@pytest.mark.parametrize('final_mode,prior_recoveries', [(False, 0), (None, 0), (True, 0), (True, 1)])
def test_final_recovery_mode_fence(both_origins, monkeypatch, tmp_path, final_mode, prior_recoveries):
    factory, owner = both_origins
    supervisor, job = automatic_job(factory, owner)
    assert job is not None
    with factory() as db:
        row = db.get(Run, job['id'])
        row.recoveries = prior_recoveries
        actor = deepcopy(db.get(Control, 1).actor)
        generation = row.generation
        db.commit()
    # Change only the synthetic SDK dataset AFTER the actual initial execution
    # validation (real policy, source, rights and recognized ON evaluation).
    real_current = dfa_rights.execution_current
    observations = []
    def validate_then_flip(db, run):
        current = real_current(db, run)
        assert current and factory.dfa_modes[owner] is True
        observations.append('initial_real_validation_ON')
        factory.dfa_modes[owner] = final_mode
        return current
    monkeypatch.setattr(dfa_rights, 'execution_current', validate_then_flip)
    supervisor.finish(job, 'failed', 'execution_unavailable')
    with factory() as db:
        row = db.get(Run, job['id'])
        observed = {key: getattr(row, key) for key in
            ('status', 'progress', 'recoveries', 'error_code', 'result', 'result_revision',
             'lease_token', 'lease_until', 'generation', 'retained_bytes')}
        evidence = {'observations': observations, 'final_sdk_value': final_mode,
                    'prior_recoveries': prior_recoveries, 'run': observed,
                    'completed': row.completed_at is not None,
                    'actor_unchanged': db.get(Control, 1).actor == actor}
        (tmp_path / 'recovery-mode-evidence.json').write_text(json.dumps(evidence, indent=2))
        assert row.lease_token is None and row.lease_until is None
        assert row.result is None and row.result_revision is None
        assert row.generation == generation and db.get(Control, 1).actor == actor
        if final_mode is True and prior_recoveries == 0:
            assert row.status == row.progress == 'queued' and row.recoveries == 1
            assert row.error_code == 'execution_unavailable' and row.completed_at is None
        else:
            assert row.status == row.progress == 'failed'
            assert row.recoveries == prior_recoveries and row.completed_at is not None
            assert row.retained_bytes == 0
            expected = ('execution_unavailable' if final_mode is True else
                        'mode_unavailable' if final_mode is None else 'mode_changed')
            assert row.error_code == expected
    # A later ON observation cannot resurrect the fenced/exhausted terminal unit.
    monkeypatch.setattr(dfa_rights, 'execution_current', real_current)
    factory.dfa_modes[owner] = True
    acquired = supervisor.acquire_job()
    if final_mode is True and prior_recoveries == 0:
        assert acquired['id'] == job['id'] and acquired['generation'] == generation
    else:
        assert acquired is None
        with factory() as db:
            assert db.get(Run, job['id']).status == 'failed'
