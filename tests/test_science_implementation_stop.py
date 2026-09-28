"""Terminal STOP preserves history, denies the real guard and unlocks safe maintenance."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import shutil

import pytest

from analysis.evidence_registry import load_science_registry
from analysis.science_activation import (VALIDATION_JOB, WORKFLOW_PATH, diff_digest, git,
                                       project_active_registry, verify_governed_maintenance)
from analysis.science_artifacts import ReviewRole, load_science_approvals
from analysis.science_implementation_stop import (
    load_implementation_stops, materialize_stop, render_stop_comment,
    stop_from_comment, stop_paths, validate_stop_target, verify_stop_changes,
)
from analysis.science_stop_github import StopContext
from tests.test_science_activation import commit
from tests.test_science_implementation_coverage import accepted_active_baseline, SUBJECT


@pytest.fixture
def stop_case(accepted_active_baseline, tmp_path):
    root = tmp_path / 'candidate'
    shutil.copytree(accepted_active_baseline, root)
    git(root, 'init')
    base = commit(root, 'accepted active synthetic baseline')
    original = tmp_path / 'base'
    shutil.copytree(root, original)
    registry = load_science_registry(root / 'data/science')
    approval = next(a for a in load_science_approvals(registry.science_dir)
                    if a.subject_id == SUBJECT and a.role == ReviewRole.IMPLEMENTATION_REVIEWER)
    binding = approval.implementation_binding
    target = dict(schema_version=1, action='stop', repository=binding.repository, subject_id=SUBJECT,
                  active_contract_digest=approval.subject_digest,
                  implementation_envelope_digest=binding.envelope_digest)
    comment = dict(id=77, body=render_stop_comment(target),
        user={'type':'User','login':'human'}, created_at=datetime.now(timezone.utc).isoformat(),
        html_url=f'https://github.com/{binding.repository}/pull/{binding.pull_request}#issuecomment-77')
    stop = stop_from_comment(comment, 'admin', binding.repository)
    return root, original, base, stop, comment


def test_stop_only_is_atomic_idempotent_and_real_guard_denies(stop_case, monkeypatch):
    root, original, base, stop, _ = stop_case
    from analysis import science_artifacts
    from api.activity_dfa import require_policy
    from fastapi import HTTPException
    monkeypatch.setattr(science_artifacts, '_SCIENCE_DIR', root / 'data/science')
    assert require_policy() == stop.active_contract_digest
    changed = materialize_stop(root, stop)
    assert changed == list(stop_paths(SUBJECT))
    assert materialize_stop(root, stop) == []
    base_registry = load_science_registry(original / 'data/science')
    head_registry = load_science_registry(root / 'data/science')
    assert verify_stop_changes(base_registry, head_registry, repository_root=root,
                               base_sha=base, authenticated=[stop]) == [stop]
    with pytest.raises(HTTPException) as denied:
        require_policy()
    assert denied.value.status_code == 503
    with pytest.raises(ValueError, match='terminally stopped'):
        project_active_registry(head_registry, SUBJECT)


@pytest.mark.parametrize('mutation', ['code', 'workflow', 'science'])
def test_stop_cannot_unlock_its_own_commit(stop_case, mutation):
    root, original, base, stop, _ = stop_case
    materialize_stop(root, stop)
    path = {'code':'api/activity_dfa.py', 'workflow':'.github/workflows/selective-review.yml',
            'science':'data/science/REGISTRY.md'}[mutation]
    target = root / path
    target.write_bytes(target.read_bytes()+b'\n# extra simultaneous change\n')
    with pytest.raises(ValueError, match='only its append-only record'):
        verify_stop_changes(load_science_registry(original / 'data/science'), load_science_registry(root / 'data/science'),
                            repository_root=root, base_sha=base, authenticated=[stop])


@pytest.mark.parametrize('permission,user_type', [('read','User'),('admin','Bot')])
def test_stop_rejects_unqualified_source(stop_case, permission, user_type):
    _, _, _, stop, comment = stop_case
    comment['user']['type'] = user_type
    with pytest.raises(ValueError, match='authorized human'):
        stop_from_comment(comment, permission, stop.repository)


def test_wrong_target_source_and_partial_statement_rejected(stop_case):
    root, _, _, stop, comment = stop_case
    registry = load_science_registry(root / 'data/science')
    for update in ({'active_contract_digest':'sha256:'+'0'*64},
                   {'implementation_envelope_digest':'sha256:'+'0'*64},
                   {'source_ref':'https://github.com/praxys-run/praxys/pull/999#issuecomment-77'}):
        with pytest.raises(ValueError):
            validate_stop_target(registry, stop.model_copy(update=update))
    comment['body'] = comment['body'].replace('I explicitly stop', 'Maybe stop')
    with pytest.raises(ValueError, match='canonical'):
        stop_from_comment(comment, 'admin', stop.repository)


def test_stop_source_race_and_partial_write_leave_no_stop(stop_case, monkeypatch):
    import analysis.science_approval_workflow as workflow
    root, _, _, stop, _ = stop_case
    def changed_source():
        raise ValueError('source changed')
    with pytest.raises(ValueError, match='source changed'):
        materialize_stop(root, stop, recheck=changed_source)
    assert not load_implementation_stops(root / 'data/science')
    original = workflow._atomic_copy
    calls = 0
    def fail_second(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('synthetic partial failure')
        return original(source, target)
    monkeypatch.setattr(workflow, '_atomic_copy', fail_second)
    with pytest.raises(OSError):
        materialize_stop(root, stop)
    assert not load_implementation_stops(root / 'data/science')
    assert git(root, 'status', '--porcelain') == b''


def test_prior_base_stop_unlocks_only_with_exact_isolated_denial(stop_case, tmp_path):
    root, _, _, stop, _ = stop_case
    materialize_stop(root, stop)
    stopped_base = commit(root, 'terminal stop')
    baseline = tmp_path / 'stopped-base'
    shutil.copytree(root, baseline)
    target = root / 'analysis/science_approval_workflow.py'
    target.write_bytes(target.read_bytes()+b'\n# separately reviewed maintenance\n')
    maintained_head = commit(root, 'maintain after stop')
    base_registry = load_science_registry(baseline / 'data/science')
    head_registry = load_science_registry(root / 'data/science')
    with pytest.raises(ValueError, match='denial evidence'):
        verify_governed_maintenance(base_registry, head_registry)
    evidence = dict(schema_version=1, purpose='stopped-maintenance', repository=stop.repository,
        pull_request=88, base_sha=stopped_base, reviewed_head_sha=maintained_head,
        diff_digest=diff_digest(root,stopped_base,maintained_head),
        active_contract_digest=stop.active_contract_digest, subject_id=SUBJECT, stop_digest=stop.stop_digest,
        candidate_guard_result='denied', workflow_path=WORKFLOW_PATH, conclusion='success',
        required_jobs=[VALIDATION_JOB], workflow_sha=stopped_base, run_id=1, run_attempt=1)
    context = StopContext(root,stop.repository,88,stopped_base,maintained_head,(),{SUBJECT:evidence})
    verify_governed_maintenance(base_registry, head_registry, stop_context=context)
    verify_stop_changes(base_registry, head_registry, repository_root=root, base_sha=stopped_base, authenticated=[])
    evidence['candidate_guard_result'] = 'active'
    with pytest.raises(ValueError, match='mismatch'):
        verify_governed_maintenance(base_registry, head_registry, stop_context=context)


def test_stop_history_cannot_be_deleted_or_relabelled(stop_case):
    root, original, base, stop, _ = stop_case
    materialize_stop(root, stop)
    shutil.rmtree(original)
    shutil.copytree(root, original)
    (root / 'data/science' / stop_paths(SUBJECT)[0]).unlink()
    with pytest.raises(ValueError, match='history was removed'):
        verify_stop_changes(load_science_registry(original / 'data/science'), load_science_registry(root / 'data/science'),
                            repository_root=root, base_sha=base, authenticated=[])


# Capture the real function before the existing isolated store fixture installs
# its ordinary test policy stub. These STOP tests restore the real guard.
from api import activity_dfa as dfa_service
from tests.test_activity_dfa import store, confirmed
_REAL_REQUIRE_POLICY = dfa_service.require_policy


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_stop_race_denies_final_publication_and_preserves_rights(stop_case, store, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from analysis import science_artifacts
    from sync.rr_recording import RRRecordingReader
    root, _, _, stop, _ = stop_case
    factory, owner = store
    monkeypatch.setattr(science_artifacts, '_SCIENCE_DIR', root / 'data/science')
    monkeypatch.setattr(dfa_service, 'require_policy', _REAL_REQUIRE_POLICY)
    proof, run = confirmed(factory, owner)
    with factory() as db:
        claimed = dfa_service.claim(db)
    ready, release = threading.Event(), threading.Event()
    real_compute = dfa_service.compute
    def paused(*args, **kwargs):
        result = real_compute(*args, **kwargs)
        ready.set()
        assert release.wait(30)
        return result
    monkeypatch.setattr(dfa_service, 'compute', paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        worker = pool.submit(dfa_service.execute, factory, *claimed)
        try:
            assert ready.wait(30)
            materialize_stop(root, stop)
        finally:
            release.set()
        worker.result(timeout=30)
    with factory() as db:
        record = db.get(dfa_service.Run, run['id'])
        assert record.status == 'failed' and record.error_code == 'processing_not_authorized'
        assert record.result is None
        assert db.get(dfa_service.Slot, 1).run_id is None
        assert dfa_service.catalog(db, owner, '123')['policy_active'] is False
        assert any(item['id'] == proof['id'] for item in dfa_service.export(db, owner)['confirmations'])
        dfa_service.change_run(db, owner, '123', run['id'], 'cancel')
        dfa_service.erase(db, owner, '123', proof['id'])
        assert not dfa_service.export(db, owner)['confirmations']
        assert RRRecordingReader(db).list_inputs(owner, '123')


@pytest.mark.parametrize('store', ['sqlite', 'postgresql'], indirect=True)
def test_terminal_stop_retains_existing_rights_export(stop_case, store, monkeypatch):
    from analysis import science_artifacts
    root, _, _, stop, _ = stop_case
    factory, owner = store
    monkeypatch.setattr(science_artifacts, '_SCIENCE_DIR', root / 'data/science')
    monkeypatch.setattr(dfa_service, 'require_policy', _REAL_REQUIRE_POLICY)
    _, run = confirmed(factory, owner)
    with factory() as db:
        claim = dfa_service.claim(db)
    dfa_service.execute(factory, *claim)
    with factory() as db:
        expected = db.get(dfa_service.Run, run['id']).result
        assert expected['summary']['valid_windows'] > 0
    materialize_stop(root, stop)
    with factory() as db:
        retained = next(item for item in dfa_service.export(db, owner)['runs'] if item['id'] == run['id'])
        assert retained['result'] == expected
        dfa_service.erase(db, owner, '123')
        assert list(dfa_service.export(db, owner)['runs']) == []


def test_new_reviewer_or_envelope_cannot_resurrect_stopped_subject(stop_case, monkeypatch):
    import yaml
    from analysis import science_artifacts
    from fastapi import HTTPException
    root, _, _, stop, _ = stop_case
    materialize_stop(root, stop)
    approvals = load_science_approvals(root / 'data/science')
    current = next(a for a in approvals if a.subject_id == SUBJECT and a.role == ReviewRole.IMPLEMENTATION_REVIEWER)
    replacement_binding = current.implementation_binding.model_copy(update={'validation_artifact_id':999})
    replacement = current.model_copy(update={'reviewer':'github:another-human', 'implementation_binding':replacement_binding})
    (root / 'data/science/approvals/replacement.yaml').write_text(yaml.safe_dump(replacement.model_dump(mode='json')))
    load_science_registry(root / 'data/science')
    monkeypatch.setattr(science_artifacts, '_SCIENCE_DIR', root / 'data/science')
    with pytest.raises(HTTPException) as denied:
        _REAL_REQUIRE_POLICY()
    assert denied.value.status_code == 503


def test_malformed_stop_fails_real_guard_closed(stop_case, monkeypatch):
    from analysis import science_artifacts
    from fastapi import HTTPException
    root, _, _, stop, _ = stop_case
    materialize_stop(root, stop)
    (root / 'data/science' / stop_paths(SUBJECT)[0]).write_text('action: stop\nsubject_id: ambiguous\n')
    monkeypatch.setattr(science_artifacts, '_SCIENCE_DIR', root / 'data/science')
    with pytest.raises(HTTPException) as denied:
        _REAL_REQUIRE_POLICY()
    assert denied.value.status_code == 503


def test_stopped_release_observation_expects_false_null_with_historical_active_contract(stop_case):
    from scripts.observe_dfa_policy import expected_policy
    root, _, _, stop, _ = stop_case
    contract = root / f'data/science/generated/contracts/{SUBJECT}.json'
    assert expected_policy(contract) == (True, stop.active_contract_digest)
    materialize_stop(root, stop)
    assert expected_policy(contract) == (False, None)
