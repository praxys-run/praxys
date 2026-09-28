"""Exact activation admission, replay and real DFA policy acceptance."""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from analysis.evidence_registry import load_science_registry
from analysis.science_activation import (
    ActivationContext, VALIDATION_JOB, WORKFLOW_PATH, diff_digest, git,
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
    git(root, 'add', '.')
    git(root, '-c', 'user.name=synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-m', message)
    return git(root, 'rev-parse', 'HEAD').decode().strip()


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
                      conclusion='success', required_jobs=[VALIDATION_JOB])
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
    projected = project_active_registry(load_science_registry(root / 'data/science'), 'sdr-activity-dfa-alpha1-v1')
    expected = build_policy_contract(projected, 'sdr-activity-dfa-alpha1-v1').contract_digest
    result = subprocess.run([sys.executable, str(root / 'scripts/check_projected_dfa_policy.py')],
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
