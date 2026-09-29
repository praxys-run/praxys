"""Exact activation admission, replay and real DFA policy acceptance."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from analysis.evidence_registry import load_science_registry
from analysis.science_activation import (
    ActivationContext, VALIDATION_JOB, PROBE_JOB, WORKFLOW_PATH, diff_digest, git,
    implementation_payload, project_active_registry, render_implementation_comment,
    strict_json,
)
from analysis.science_artifacts import (
    ImplementationBinding, ReviewRole, ReviewSubjectKind, build_policy_contract,
    digest_payload, evidence_review_digest, render_approval_comment_template,
    approval_statement_for_subject, science_decision_digest,
)
from analysis.science_approval_workflow import (
    approvals_from_github_comments, materialize_science_approvals,
    verify_science_approval_changes,
)
from tests.test_science_approval_workflow import _write_fixture_records


def commit(root, message):
    # Fixtures copy complete Git directories; keep object files stable for snapshots.
    # Configure before add/commit can create objects or start automatic maintenance.
    git(root, 'config', '--local', 'maintenance.auto', 'false')
    git(root, 'config', '--local', 'gc.auto', '0')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-m', message)
    return git(root, 'rev-parse', 'HEAD').decode().strip()


def test_synthetic_git_snapshot_retains_complete_history(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    git(root, 'init')
    git(root, 'config', '--local', 'maintenance.auto', 'true')
    git(root, 'config', '--local', 'gc.auto', '1')
    (root / 'feature.py').write_text('version = 1\n')
    first = commit(root, 'first')
    (root / 'feature.py').write_text('version = 2\n')
    second = commit(root, 'second')
    snapshot = tmp_path / 'snapshot'
    shutil.copytree(root, snapshot)
    for repository in (root, snapshot):
        assert git(repository, 'config', '--local', '--get', 'maintenance.auto').strip() == b'false'
        assert git(repository, 'config', '--local', '--get', 'gc.auto').strip() == b'0'
        assert git(repository, 'rev-list', 'HEAD').decode().splitlines() == [second, first]
        assert git(repository, 'show', f'{first}:feature.py') == b'version = 1\n'
        assert git(repository, 'show', f'{second}:feature.py') == b'version = 2\n'
        git(repository, 'fsck', '--full', '--strict')


@pytest.fixture
def activation(tmp_path):
    root = tmp_path / 'candidate'
    root.mkdir()
    science = root / 'data/science'
    review, decision = _write_fixture_records(science)
    git(root, 'init')
    (root / 'feature.py').write_text('version = 1\n')
    base = commit(root, 'base')
    base_science = tmp_path / 'base/data/science'
    shutil.copytree(science, base_science)
    (root / 'feature.py').write_text('version = 2\n')
    head = commit(root, 'reviewed')
    projected = project_active_registry(load_science_registry(science), decision.id)
    contract = build_policy_contract(projected, decision.id)
    validation = dict(schema_version=1, repository='praxys-run/praxys', pull_request=42,
                      base_sha=base, reviewed_head_sha=head, diff_digest=diff_digest(root, base, head),
                      active_contract_digest=contract.contract_digest, subject_id=decision.id,
                      workflow_path=WORKFLOW_PATH, workflow_sha=base, run_id=5, run_attempt=1,
                      conclusion='success', required_jobs=[VALIDATION_JOB, PROBE_JOB])
    binding = ImplementationBinding(version=1, repository='praxys-run/praxys', pull_request=42,
        base_sha=base, reviewed_head_sha=head, diff_digest=validation['diff_digest'],
        active_contract_digest=contract.contract_digest, validation_run_id=5,
        validation_run_attempt=1, validation_workflow_sha=base, validation_artifact_id=6,
        validation_digest=digest_payload(validation))
    context = ActivationContext(root, binding.repository, 42, base, head,
                                {binding.envelope_digest: validation})
    comments = []
    for kind, identity, digest, role in [
        (ReviewSubjectKind.EVIDENCE_REVIEW, review.id, evidence_review_digest(review), ReviewRole.EVIDENCE_REVIEWER),
        (ReviewSubjectKind.SCIENCE_DECISION, decision.id,
         science_decision_digest(projected.decisions[decision.id]), ReviewRole.DECISION_APPROVER),
    ]:
        body = render_approval_comment_template(subject_kind=kind, subject_id=identity,
            subject_digest=digest, role=role, approval_statement=approval_statement_for_subject(
                projected, subject_kind=kind, subject_id=identity, role=role))
        comments.append(dict(id=len(comments)+1, body=body, user={'login':'human', 'type':'User'},
                             html_url=f'https://github.com/praxys-run/praxys/pull/42#issuecomment-{len(comments)+1}',
                             created_at='2026-09-28T01:00:00Z'))
    comments.append(dict(id=3, body=render_implementation_comment(decision.id, binding),
                         user={'login':'human','type':'User'},
                         html_url='https://github.com/praxys-run/praxys/pull/42#issuecomment-3',
                         created_at='2026-09-28T01:00:00Z'))
    return root, science, base_science, context, binding, comments, decision.id


def parsed(fixture):
    _, science, _, context, _, comments, _ = fixture
    return approvals_from_github_comments(science, comments, {'human':'admin'}, activation_context=context)


def test_activation_replays_exact_frozen_tree_and_is_idempotent(activation):
    root, science, base, context, binding, comments, subject = activation
    approvals = parsed(activation)
    assert len(approvals) == 3
    materialize_science_approvals(science, approvals, activation_context=context)
    contract = build_policy_contract(load_science_registry(science), subject)
    assert contract.runtime_state.value == 'active'
    assert contract.contract_digest == binding.active_contract_digest
    verify_science_approval_changes(base, science, comments, {'human':'admin'}, activation_context=context)
    assert materialize_science_approvals(science, approvals, activation_context=context) == []


@pytest.mark.parametrize('path', ['feature.py', 'arbitrary.txt', 'data/science/generated/unapproved.txt'])
def test_unexplained_delta_cannot_hide_in_any_directory(activation, path):
    root, science, base, context, _, comments, _ = activation
    approvals = parsed(activation)
    materialize_science_approvals(science, approvals, activation_context=context)
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text('unexpected\n')
    with pytest.raises(ValueError, match='exact activation replay'):
        verify_science_approval_changes(base, science, comments, {'human':'admin'}, activation_context=context)


@pytest.mark.parametrize('field,value', [('pull_request',43), ('repository','other/repo'),
    ('diff_digest','sha256:'+'0'*64), ('active_contract_digest','sha256:'+'0'*64),
    ('validation_digest','sha256:'+'0'*64), ('validation_run_attempt',2),
    ('validation_workflow_sha','0'*40)])
def test_binding_substitution_rejected(activation, field, value):
    _, science, _, context, binding, _, subject = activation
    changed = binding.model_copy(update={field:value})
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        context.verify(changed, load_science_registry(science), subject)


@pytest.mark.parametrize('permission,user_type', [('read','User'), ('admin','Bot'), ('none','User')])
def test_unqualified_identity_cannot_supply_implementation(activation, permission, user_type):
    _, science, _, context, _, comments, _ = activation
    for comment in comments:
        comment['user']['type'] = user_type
    assert approvals_from_github_comments(science, comments, {'human':permission}, activation_context=context) == []


def test_missing_source_or_revoked_permission_prevents_acceptance(activation):
    _, science, base, context, _, comments, _ = activation
    materialize_science_approvals(science, parsed(activation), activation_context=context)
    for current, permissions in [(comments[:-1], {'human':'admin'}), (comments, {'human':'read'})]:
        with pytest.raises(ValueError, match='authenticated exact PR approval'):
            verify_science_approval_changes(base, science, current, permissions, activation_context=context)


def test_missing_linked_evidence_signature_leaves_tree_unchanged(activation):
    root, science, _, context, binding, _, _ = activation
    approvals = [a for a in parsed(activation) if a.role != ReviewRole.EVIDENCE_REVIEWER]
    before = git(root, 'status', '--porcelain')
    with pytest.raises(ValueError):
        materialize_science_approvals(science, approvals, activation_context=context)
    assert git(root, 'status', '--porcelain') == before
    context.require_reviewed_tree(binding, root)


def test_code_race_and_file_mode_change_prevent_materialization(activation):
    root, science, _, context, _, _, _ = activation
    approvals = parsed(activation)
    (root / 'feature.py').chmod(0o755)
    with pytest.raises(ValueError, match='exact reviewed preapproval tree'):
        materialize_science_approvals(science, approvals, activation_context=context)


def test_duplicate_json_and_canonical_statement_tamper_rejected(activation):
    with pytest.raises(ValueError, match='Duplicate JSON'):
        strict_json('{"version":1,"version":2}')
    body = activation[5][-1]['body']
    with pytest.raises(ValueError, match='canonical statement'):
        implementation_payload(body.replace('I approve activation', 'Looks fine'))


def test_real_projected_dfa_policy(tmp_path):
    import os
    root = Path(__file__).resolve().parents[1]
    from analysis.science_implementation_stop import load_implementation_stops
    stops = [stop for stop in load_implementation_stops(root / 'data/science')
             if stop.subject_id == 'sdr-activity-dfa-alpha1-v1']
    if stops:
        expected = stops[0].active_contract_digest
        checker = 'check_stopped_dfa_policy.py'
    else:
        projected = project_active_registry(load_science_registry(root / 'data/science'), 'sdr-activity-dfa-alpha1-v1')
        expected = build_policy_contract(projected, 'sdr-activity-dfa-alpha1-v1').contract_digest
        checker = 'check_projected_dfa_policy.py'
    result = subprocess.run([sys.executable, str(root / 'scripts' / checker)],
        env={**os.environ, 'CANDIDATE_ROOT':str(root), 'ACTIVATION_SUBJECT':'sdr-activity-dfa-alpha1-v1',
             'ACTIVATION_CONTRACT':expected}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['contract_digest'] == expected


import sys


def test_partial_publication_failure_restores_original_tree(activation, monkeypatch):
    import analysis.science_approval_workflow as workflow
    root, science, _, context, binding, _, _ = activation
    approvals = parsed(activation)
    original = workflow._atomic_copy
    calls = 0
    def fail_once(source, target):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError('synthetic publication failure')
        return original(source, target)
    monkeypatch.setattr(workflow, '_atomic_copy', fail_once)
    with pytest.raises(OSError, match='synthetic publication failure'):
        materialize_science_approvals(science, approvals, activation_context=context)
    context.require_reviewed_tree(binding, root)


def test_prepublication_source_race_leaves_tree_unchanged(activation):
    root, science, _, context, binding, _, _ = activation
    approvals = parsed(activation)
    def revoked():
        raise ValueError('source permission revoked')
    context = replace(context, recheck=revoked)
    with pytest.raises(ValueError, match='permission revoked'):
        materialize_science_approvals(science, approvals, activation_context=context)
    context.require_reviewed_tree(binding, root)


def test_symlink_and_duplicate_yaml_fail_closed(activation):
    from analysis.science_yaml import load_science_yaml
    with pytest.raises(ValueError, match='Duplicate YAML'):
        load_science_yaml('status: draft\nstatus: accepted\n')
    root, science, _, context, _, _, _ = activation
    approvals = parsed(activation)
    (science / 'unexpected').symlink_to(root / 'feature.py')
    with pytest.raises(ValueError):
        materialize_science_approvals(science, approvals, activation_context=context)


def test_observation_requires_exact_shape_digest_and_source():
    from scripts.observe_dfa_policy import validate_observation
    expected = 'sha256:' + 'a' * 64
    ready = {'status':'ready', 'dfa_policy':{'policy_active':True, 'contract_digest':expected}}
    args = dict(expected_sha='abc', expected_active=True, expected_digest=expected)
    assert validate_observation(ready, {'source_sha':'abc'}, **args)['contract_digest'] == expected
    for bad in [{}, {'status':'ready'}, {'status':'ready','dfa_policy':{'policy_active':1, 'contract_digest':expected}},
                {'status':'ready','dfa_policy':{'policy_active':False,'contract_digest':None}},
                {'status':'ready','dfa_policy':{'policy_active':True,'contract_digest':expected,'error':'details'}}]:
        with pytest.raises(ValueError):
            validate_observation(bad, {'source_sha':'abc'}, **args)
    with pytest.raises(ValueError):
        validate_observation(ready, {'source_sha':'old'}, **args)


def test_later_unrelated_change_allowed_but_governed_content_and_modes_blocked(activation, monkeypatch, tmp_path):
    import analysis.science_activation as module
    root, science, _, context, _, _, subject = activation
    materialize_science_approvals(science, parsed(activation), activation_context=context)
    base_root = tmp_path / 'accepted-base'
    shutil.copytree(root, base_root)
    # Explicit trusted manifest fixture, independent of candidate data.
    trusted = tmp_path / 'trusted'
    (trusted / 'config').mkdir(parents=True)
    (trusted / 'config/science-implementation-coverage.json').write_text(json.dumps(
        {'schema_version':1,'contracts':{subject:['feature.py','config/science-implementation-coverage.json']}}))
    monkeypatch.setattr(module, '__file__', str(trusted / 'analysis/science_activation.py'))
    base_registry = load_science_registry(base_root / 'data/science')
    head_registry = load_science_registry(science)
    (root / 'unrelated.md').write_text('ordinary maintenance')
    module.verify_governed_maintenance(base_registry, head_registry)
    (root / 'feature.py').chmod(0o755)
    with pytest.raises(ValueError, match='renewal'):
        module.verify_governed_maintenance(base_registry, head_registry)
    (root / 'feature.py').chmod(0o644)
    (root / 'feature.py').unlink()
    with pytest.raises(ValueError, match='renewal'):
        module.verify_governed_maintenance(base_registry, head_registry)


def test_exact_git_tree_honors_checkout_newline_representation(tmp_path):
    from analysis.science_activation import directory_tree, git_tree
    root = tmp_path / 'repo'
    root.mkdir()
    git(root, 'init')
    git(root, 'config', 'core.autocrlf', 'true')
    (root / '.gitattributes').write_text('* text=auto\n')
    (root / 'record.yaml').write_bytes(b'state: draft\r\n')
    revision = commit(root, 'CRLF checkout')
    expected = git_tree(root, revision)
    assert directory_tree(root, expected, repository=root) == expected


def test_composite_approval_is_one_atomic_idempotent_source(activation):
    from analysis.science_activation import render_activation_comment
    root, science, base, context, binding, comments, subject = activation
    combined = dict(comments[-1], body=render_activation_comment(load_science_registry(science), subject, binding))
    approvals = approvals_from_github_comments(science, [combined], {'human':'admin'}, activation_context=context)
    assert len(approvals) == 3
    assert len({str(approval.source_ref) for approval in approvals}) == 1
    materialize_science_approvals(science, approvals, activation_context=context)
    verify_science_approval_changes(base, science, [combined], {'human':'admin'}, activation_context=context)
    assert materialize_science_approvals(science, approvals, activation_context=context) == []


@pytest.mark.parametrize('mutation', ['missing_evidence', 'conflicting_digest', 'extra_text', 'duplicate_marker'])
def test_partial_or_conflicting_composite_never_publishes(activation, mutation):
    from analysis.science_activation import COMPOSITE_MARKER, render_activation_comment
    root, science, _, context, binding, comments, subject = activation
    body = render_activation_comment(load_science_registry(science), subject, binding)
    if mutation == 'missing_evidence':
        start = body.index('### Role: `evidence_reviewer`')
        end = body.index('### Role: `decision_approver`')
        body = body[:start] + body[end:]
    elif mutation == 'conflicting_digest':
        body = body.replace(binding.active_contract_digest, 'sha256:'+'0'*64, 1)
    elif mutation == 'extra_text':
        body += '\nAlso approve another subject.'
    else:
        body += '\n' + body[body.index('<!-- '+COMPOSITE_MARKER):]
    comment = dict(comments[-1], body=body)
    with pytest.raises(ValueError):
        approvals = approvals_from_github_comments(science, [comment], {'human':'admin'}, activation_context=context)
        materialize_science_approvals(science, approvals, activation_context=context)
    context.require_reviewed_tree(binding, root)


def test_incremental_implementation_compatibility_never_partially_activates(activation):
    root, science, _, context, binding, comments, _ = activation
    for incomplete in ([comments[2]], [comments[2],comments[1]]):
        approvals = approvals_from_github_comments(science, incomplete, {'human':'admin'}, activation_context=context)
        with pytest.raises(ValueError):
            materialize_science_approvals(science, approvals, activation_context=context)
        context.require_reviewed_tree(binding, root)
    approvals = approvals_from_github_comments(science, comments, {'human':'admin'}, activation_context=context)
    materialize_science_approvals(science, approvals, activation_context=context)


def test_diff_digest_binds_blobs_and_modes_without_local_diff_configuration(activation):
    root, _, _, context, _, _, _ = activation
    expected = diff_digest(root, context.base_sha, context.head_sha)
    git(root, 'config', 'diff.context', '99')
    git(root, 'config', 'diff.algorithm', 'histogram')
    git(root, 'config', 'diff.noprefix', 'true')
    assert diff_digest(root, context.base_sha, context.head_sha) == expected
    (root / 'feature.py').chmod(0o755)
    changed = commit(root, 'mode changed')
    assert diff_digest(root, context.base_sha, changed) != expected


def _raw_dfa_activation(tmp_path, *, omit_review_date=False):
    """Keep real nested YAML bytes; never model-dump away the missing-key shape."""
    import re
    from analysis.evidence_registry import render_registry_index
    from analysis.science_artifacts import sync_science_artifacts
    from analysis.science_implementation_stop import stop_paths
    from analysis.science_yaml import load_science_yaml

    subject = 'sdr-activity-dfa-alpha1-v1'
    review_id = 'evidence-activity-dfa-alpha1-v1'
    root = tmp_path / 'raw-dfa'
    science = root / 'data/science'
    shutil.copytree(Path(__file__).resolve().parents[1] / 'data/science', science)
    evidence = science / 'evidence/activity-dfa-alpha1' / f'{review_id}.yaml'
    decision = science / 'decisions' / f'{subject}.yaml'
    assert 'reviewed_on' in load_science_yaml(evidence.read_text())

    # A disposable first-acceptance fixture also works on later accepted/stopped
    # source revisions. Reset lifecycle text only, without serializing science.
    for path in (evidence, decision):
        raw = path.read_bytes()
        raw, count = re.subn(rb'(?m)^(status: )(?:draft|accepted)(\r?)$',
                             lambda match: match[1] + b'draft' + match[2], raw)
        assert count == 1
        if path == evidence:
            raw, count = re.subn(rb'(?m)^(reviewed_on:)[^\r\n]*(\r?\n)',
                lambda match: b'' if omit_review_date else match[1] + b' null' + match[2], raw)
        else:
            raw, count = re.subn(rb'(?m)^(  runtime_state: )(?:inactive|active)(\r?)$',
                                 lambda match: match[1] + b'inactive' + match[2], raw)
        assert count == 1
        path.write_bytes(raw)
    # Exercise exact filesystem-mode restoration, beyond Git's executable bit.
    evidence.chmod(0o640)
    for path in (science / 'approvals').rglob('*.yaml'):
        if load_science_yaml(path.read_text())['subject_id'] in {subject, review_id}:
            path.unlink()
    for relative in stop_paths(subject):
        (science / relative).unlink(missing_ok=True)
    registry = load_science_registry(science)
    sync_science_artifacts(registry, check=False)
    (science / 'REGISTRY.md').write_text(render_registry_index(registry))

    # All normalization precedes both the immutable fixture head and binding.
    git(root, 'init')
    base = commit(root, 'raw nested DFA draft fixture')
    base_science = tmp_path / 'base/data/science'
    shutil.copytree(science, base_science)
    (root / 'outside-science.txt').write_text('Unrelated reviewed bytes must survive.\n')
    (root / 'outside-science.txt').chmod(0o755)
    head = commit(root, 'frozen raw DFA candidate')
    projected = project_active_registry(registry, subject)
    contract = build_policy_contract(projected, subject)
    validation = dict(schema_version=1, repository='praxys-run/praxys', pull_request=42,
        base_sha=base, reviewed_head_sha=head, diff_digest=diff_digest(root, base, head),
        active_contract_digest=contract.contract_digest, subject_id=subject,
        workflow_path=WORKFLOW_PATH, workflow_sha=base, run_id=5, run_attempt=1,
        conclusion='success', required_jobs=[VALIDATION_JOB, PROBE_JOB])
    binding = ImplementationBinding(version=1, repository='praxys-run/praxys', pull_request=42,
        base_sha=base, reviewed_head_sha=head, diff_digest=validation['diff_digest'],
        active_contract_digest=contract.contract_digest, validation_run_id=5,
        validation_run_attempt=1, validation_workflow_sha=base, validation_artifact_id=6,
        validation_digest=digest_payload(validation))
    context = ActivationContext(root, binding.repository, 42, base, head,
                                {binding.envelope_digest: validation})
    from analysis.science_activation import render_activation_comment
    comment = dict(id=101, body=render_activation_comment(registry, subject, binding),
        user={'login': 'synthetic-raw-dfa-reviewer', 'type': 'User'},
        html_url='https://github.com/praxys-run/praxys/pull/42#issuecomment-101',
        created_at='2026-09-28T12:34:56Z')
    return root, science, base_science, context, binding, comment, subject, review_id


def _raw_dfa_files(root):
    import stat
    return {path.relative_to(root).as_posix():
            (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for path in root.rglob('*')
            if path.is_file() and '.git' not in path.relative_to(root).parts}


def _raw_dfa_approvals(case):
    _, science, _, context, _, comment, _, _ = case
    approvals = approvals_from_github_comments(science, [comment],
        {'synthetic-raw-dfa-reviewer': 'admin'}, activation_context=context)
    assert {a.role for a in approvals} == set(ReviewRole)
    assert len(approvals) == 3
    assert {str(a.source_ref) for a in approvals} == {comment['html_url']}
    return approvals


def test_raw_dfa_omitted_review_date_fails_full_composite_without_publication(tmp_path, monkeypatch):
    import analysis.science_approval_workflow as workflow
    from analysis.science_artifacts import load_science_approvals
    case = _raw_dfa_activation(tmp_path, omit_review_date=True)
    root, science, _, context, binding, _, subject, review_id = case
    before = _raw_dfa_files(root)
    def unexpected_publication(*args):
        pytest.fail('The omitted optional field must fail before any publication')
    monkeypatch.setattr(workflow, '_atomic_copy', unexpected_publication)
    approvals = _raw_dfa_approvals(case)
    with pytest.raises(ValueError, match='Expected one top-level reviewed_on field, found 0'):
        materialize_science_approvals(science, approvals, activation_context=context)
    assert _raw_dfa_files(root) == before
    assert not [a for a in load_science_approvals(science)
                if a.subject_id in {subject, review_id}]
    context.require_reviewed_tree(binding, root)


def test_raw_dfa_null_review_date_materializes_replays_and_real_guard_accepts(tmp_path, monkeypatch):
    from datetime import date
    from analysis import science_artifacts, science_approval_workflow as workflow
    from analysis.activity_dfa import METHOD_VERSION, POLICY_PARAMETER_DIGEST, digest
    from api.activity_dfa import require_policy
    from fastapi import HTTPException
    class ExecutionDate(date):
        @classmethod
        def today(cls):
            return cls(2035, 1, 1)
    monkeypatch.setattr(workflow, 'date', ExecutionDate)
    case = _raw_dfa_activation(tmp_path)
    root, science, base, context, binding, comment, subject, review_id = case
    before = _raw_dfa_files(root)
    draft_registry = load_science_registry(science)
    original_review = draft_registry.evidence_reviews[review_id]
    expected_decision_digest = science_decision_digest(
        project_active_registry(draft_registry, subject).decisions[subject])
    assert original_review.reviewed_on is None
    # Select only the temporary data root. The real loader and guard are intact.
    monkeypatch.setattr(science_artifacts, '_SCIENCE_DIR', science)
    with pytest.raises(HTTPException) as inactive:
        require_policy()
    assert inactive.value.status_code == 503
    approvals = _raw_dfa_approvals(case)
    assert {a.reviewed_on for a in approvals} == {date(2026, 9, 28)}
    assert next(iter(approvals)).reviewed_on != ExecutionDate.today()
    changed = materialize_science_approvals(science, approvals, activation_context=context)
    registry = load_science_registry(science)
    review = registry.evidence_reviews[review_id]
    contract = build_policy_contract(registry, subject)
    assert review.status.value == 'accepted'
    assert review.reviewed_on == date(2026, 9, 28)
    assert evidence_review_digest(review) == evidence_review_digest(original_review)
    assert contract.decision_status.value == 'accepted' and contract.runtime_state.value == 'active'
    assert contract.contract_digest == binding.active_contract_digest
    assert contract.source_decision_digest == expected_decision_digest
    assert contract.model_version == METHOD_VERSION
    assert digest({k: v.value for k, v in contract.parameters.items()}) == POLICY_PARAMETER_DIGEST
    assert require_policy() == binding.active_contract_digest
    verify_science_approval_changes(base, science, [comment],
        {'synthetic-raw-dfa-reviewer': 'admin'}, activation_context=context)
    context.verify_replay(binding, approvals, root)
    after = _raw_dfa_files(root)
    actual_delta = {name for name in before.keys() | after.keys()
                    if before.get(name) != after.get(name)}
    assert actual_delta == {'data/science/' + p.as_posix() for p in changed}
    assert materialize_science_approvals(science, approvals, activation_context=context) == []
    assert _raw_dfa_files(root) == after


def test_raw_dfa_late_publication_failure_restores_all_bytes_and_modes(tmp_path, monkeypatch):
    import analysis.science_approval_workflow as workflow
    from analysis.science_artifacts import load_science_approvals
    case = _raw_dfa_activation(tmp_path)
    root, science, _, context, binding, _, subject, review_id = case
    before = _raw_dfa_files(root)
    original = workflow._atomic_copy
    injected = False
    published_roles = set()
    published_lifecycle = {}
    def fail_after_final_packet(source, target):
        nonlocal injected
        original(source, target)
        if not injected and target.relative_to(science).as_posix() == (
                f'generated/review-packets/{subject}.md'):
            injected = True
            published_roles.update(a.role for a in load_science_approvals(science)
                                   if a.subject_id in {subject, review_id})
            registry = load_science_registry(science)
            published_lifecycle.update(
                evidence=registry.evidence_reviews[review_id].status.value,
                decision=registry.decisions[subject].status.value,
                runtime=registry.decisions[subject].artifact_policy.runtime_state.value)
            raise OSError('synthetic late raw-DFA publication failure')
    monkeypatch.setattr(workflow, '_atomic_copy', fail_after_final_packet)
    with pytest.raises(OSError, match='synthetic late raw-DFA publication failure'):
        materialize_science_approvals(science, _raw_dfa_approvals(case), activation_context=context)
    assert injected and published_roles == set(ReviewRole)
    assert published_lifecycle == {'evidence': 'accepted', 'decision': 'accepted', 'runtime': 'active'}
    assert _raw_dfa_files(root) == before
    assert not [a for a in load_science_approvals(science)
                if a.subject_id in {subject, review_id}]
    context.require_reviewed_tree(binding, root)
