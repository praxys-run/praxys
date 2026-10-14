"""Real projected-policy service stays fenced after fresh changes and late output."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest
from fastapi import HTTPException
from analysis import science_artifacts as artifacts
from api import activity_dfa as service, activity_dfa_storage as storage, dfa_automatic
from db.models import ActivityDFARun as Run, ActivityDFAControl as Control
from tests.test_activity_dfa import store, confirmed
from tests.test_dfa_origins import both_origins


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_real_policy_numerical_service(both_origins):
    factory, owner = both_origins
    _, run = confirmed(factory, owner)
    with factory() as db: claim = service.claim(db)
    service.execute(factory, *claim)
    with factory() as db:
        view = service.read_run(db, owner, '123', run['id'], 0, 120)
        assert view['status'] == 'complete' and view['summary']['valid_windows'] > 0
        assert db.get(Control, 1).actor['state'] == 'idle'


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
@pytest.mark.parametrize('change', ['rights', 'source', 'generation', 'stop', 'content'])
def test_real_policy_late_output_cannot_cross_fresh_change(both_origins, monkeypatch, change):
    factory, owner = both_origins
    _, run = confirmed(factory, owner)
    with factory() as db: claim = service.claim(db)
    supervisor = factory.dfa_supervisor
    ready, release = threading.Event(), threading.Event()
    finish = supervisor.finish
    def paused(*args, **kwargs):
        assert args[1] == 'output', 'real numerical output must precede invalidation'
        ready.set();assert release.wait(10)
        return finish(*args, **kwargs)
    monkeypatch.setattr(supervisor, 'finish', paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.execute, factory, *claim)
        try:
            assert ready.wait(10)
            if change == 'rights':
                storage.record_negative(owner, 'synthetic_revocation', 'origin', 'manual')
            elif change == 'source':
                from api.connectiq import reparse_snapshot
                with factory() as db: reparse_snapshot(owner, '123', run['snapshot_id'], db)
            elif change == 'generation':
                with factory() as db: service.change_run(db, owner, '123', run['id'], 'cancel')
            else:
                science = Path(artifacts._SCIENCE_DIR)
                if change == 'stop':
                    # An invalid new STOP must deny even with a warmed valid cache.
                    (science / 'stops' / 'synthetic-new-stop.yaml').write_text('schema_version: broken\n')
                else:
                    (science / 'generated/contracts/sdr-activity-dfa-alpha1-v2.json').write_text('{}\n')
                for guard in (service.require_policy, dfa_automatic.require_policy):
                    with pytest.raises(HTTPException): guard()
        finally: release.set()
        future.result(timeout=10)
    with factory() as db:
        record = db.get(Run, run['id'])
        assert record.result is None and record.status != 'complete'
        assert db.get(Control, 1).actor['state'] == 'idle'


def test_warm_actual_guard_observes_mode_and_valid_stop(both_origins, monkeypatch):
    from datetime import datetime, timezone
    import yaml
    from analysis.evidence_registry import load_science_registry
    from analysis.science_artifacts import load_science_approvals, ReviewRole
    from analysis.science_implementation_stop import render_stop_comment, stop_from_comment, validate_stop_target
    science = Path(artifacts._SCIENCE_DIR)
    real_validator = artifacts.load_policy_contract
    calls = []
    def measured(subject, **kwargs):
        calls.append(subject);return real_validator(subject, **kwargs)
    monkeypatch.setattr(artifacts, 'load_policy_contract', measured)
    expected = service.require_policy()
    registry_file = science / 'REGISTRY.md'
    mode = registry_file.stat().st_mode & 0o777
    registry_file.chmod(mode ^ 0o100)
    # Ungoverned metadata may remain valid, but it must trigger real validation.
    assert service.require_policy() == expected
    assert len(calls) == 2
    registry = load_science_registry(science)
    approval = next(a for a in load_science_approvals(science)
                    if a.subject_id == 'sdr-activity-dfa-alpha1-v2' and a.role == ReviewRole.IMPLEMENTATION_REVIEWER)
    binding = approval.implementation_binding
    target = dict(schema_version=1, action='stop', repository=binding.repository,
                  subject_id=approval.subject_id, active_contract_digest=approval.subject_digest,
                  implementation_envelope_digest=binding.envelope_digest)
    comment = dict(id=999, body=render_stop_comment(target), user={'type':'User','login':'synthetic-human'},
                   created_at=datetime.now(timezone.utc).isoformat(),
                   html_url=f'https://github.com/{binding.repository}/pull/{binding.pull_request}#issuecomment-999')
    stop = stop_from_comment(comment, 'admin', binding.repository)
    validate_stop_target(registry, stop)
    (science / 'stops/sdr-activity-dfa-alpha1-v2.yaml').write_text(yaml.safe_dump(stop.model_dump(mode='json')))
    for guard in (service.require_policy, dfa_automatic.require_policy):
        with pytest.raises(HTTPException): guard()
