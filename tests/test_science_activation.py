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
    from analysis.science_admission_amendment import prune_designated_fixture_closure
    prune_designated_fixture_closure(science)
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
    from datetime import date, datetime, timezone
    from analysis import science_artifacts, science_approval_workflow as workflow
    from analysis.activity_dfa import METHOD_VERSION, POLICY_PARAMETER_DIGEST, digest
    from api.activity_dfa import require_policy
    from fastapi import HTTPException
    class ExecutionDate(date):
        @classmethod
        def today(cls):
            return cls(2035, 1, 1)
    class ExecutionDateTime(datetime):
        # Keep authenticated source parsing real; only execution clocks differ.
        fromisoformat = staticmethod(datetime.fromisoformat)

        @classmethod
        def now(cls, tz=None):
            return cls(2035, 1, 1, tzinfo=tz)

        @classmethod
        def today(cls):
            return cls.now()

        @classmethod
        def utcnow(cls):
            return cls(2035, 1, 1)
    monkeypatch.setattr(workflow, 'date', ExecutionDate)
    monkeypatch.setattr(workflow, 'datetime', ExecutionDateTime)
    assert workflow.date.today() == date(2035, 1, 1)
    assert workflow.datetime.now() == workflow.datetime.today() == workflow.datetime.utcnow() == datetime(2035, 1, 1)
    assert workflow.datetime.now(timezone.utc) == datetime(2035, 1, 1, tzinfo=timezone.utc)
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
    assert workflow.datetime.fromisoformat(comment['created_at']).date() == date(2026, 9, 28)
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


def designated_case(tmp_path):
    """Disposable designated V2, inheriting actual shipped V1 history/STOP."""
    import yaml
    from analysis import science_admission_amendment as amendment
    from analysis.evidence_registry import render_registry_index
    from analysis.science_artifacts import sync_science_artifacts
    from analysis.science_yaml import load_science_yaml
    root = tmp_path / 'designated'
    source = Path(__file__).resolve().parents[1]
    for family in ('analysis', 'api', 'db', 'sync'):
        shutil.copytree(source / family, root / family, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    science = root / 'data/science'
    shutil.copytree(source / 'data/science', science)
    amendment.prune_designated_fixture_closure(science)
    git(root, 'init')
    base = commit(root, 'synthetic exact shipped stopped baseline')
    baseline = science / 'decisions' / (amendment.BASELINE + '.yaml')
    raw = load_science_yaml(baseline.read_text())
    value = dict(schema_version=1, kind='designated_activity_dfa_v2',
        baseline_subject=amendment.BASELINE, baseline_version=1,
        baseline_decision_digest=amendment.BASELINE_DECISION,
        baseline_contract_digest=amendment.BASELINE_CONTRACT,
        baseline_implementation_envelope=amendment.BASELINE_ENVELOPE,
        evidence_subject=amendment.EVIDENCE, evidence_digest=amendment.EVIDENCE_DIGEST,
        baseline_stop_digest=amendment.BASELINE_STOP,
        frozen_group_value_digest=amendment.FROZEN_DIGEST, model_version=amendment.METHOD,
        manual_statement_revision=amendment.MANUAL_STATEMENT, modalities=amendment.MODALITIES.copy())
    raw.update(id=amendment.DESIGNATED, version=2, status='draft', supersedes=[], superseded_by=None)
    raw['artifact_policy']['runtime_state'] = 'inactive'
    parameter = dict(raw['model_parameters'][0], name='admission_amendment', value=value)
    raw['model_parameters'].append(parameter)
    raw['decision_review']['items'][0]['parameter_names'].append('admission_amendment')
    path = science / 'decisions' / (amendment.DESIGNATED + '.yaml')
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    registry = load_science_registry(science)
    sync_science_artifacts(registry, check=False)
    (science / 'REGISTRY.md').write_text(render_registry_index(registry))
    head = commit(root, 'synthetic designated draft only')
    contract = build_policy_contract(project_active_registry(registry, amendment.DESIGNATED), amendment.DESIGNATED)
    validation = dict(schema_version=2, purpose='dfa-v2-activation', repository='praxys-run/praxys', pull_request=42,
        base_sha=base, reviewed_head_sha=head, diff_digest=diff_digest(root, base, head),
        active_contract_digest=contract.contract_digest, subject_id=amendment.DESIGNATED,
        admission_amendment=value, baseline_guard_result='denied', workflow_path=WORKFLOW_PATH,
        workflow_sha=base, run_id=5, run_attempt=1, conclusion='success', required_jobs=[VALIDATION_JOB, PROBE_JOB])
    binding = ImplementationBinding(version=1, repository='praxys-run/praxys', pull_request=42,
        base_sha=base, reviewed_head_sha=head, diff_digest=validation['diff_digest'],
        active_contract_digest=contract.contract_digest, validation_run_id=5, validation_run_attempt=1,
        validation_workflow_sha=base, validation_artifact_id=6, validation_digest=digest_payload(validation))
    context = ActivationContext(root, 'praxys-run/praxys', 42, base, head, {binding.envelope_digest: validation})
    return root, science, context, binding, raw


def test_designated_new_only_activation_preserves_all_history_and_replays(tmp_path):
    from analysis.science_activation import render_activation_comment, V2_COMPOSITE_MARKER
    from analysis.science_admission_amendment import DESIGNATED, BASELINE, EVIDENCE
    from analysis.science_artifacts import load_science_approvals
    root, science, context, binding, _ = designated_case(tmp_path)
    before = {p.relative_to(science): (p.read_bytes(), p.stat().st_mode) for p in science.rglob('*') if p.is_file()}
    registry = load_science_registry(science)
    body = render_activation_comment(registry, DESIGNATED, binding)
    assert V2_COMPOSITE_MARKER in body and 'APPROVE NEW V2 DECISION AND IMPLEMENTATION' in body
    comment = dict(id=90, body=body, user={'type':'User','login':'synthetic'},
        created_at='2026-10-08T00:00:00Z', html_url='https://github.com/praxys-run/praxys/pull/42#issuecomment-90')
    approvals = approvals_from_github_comments(science, [comment], {'synthetic':'admin'}, activation_context=context)
    assert len(approvals) == 2 and {a.subject_id for a in approvals} == {DESIGNATED}
    shared = [a for a in load_science_approvals(science) if a.subject_id == EVIDENCE]
    materialize_science_approvals(science, approvals, activation_context=context)
    assert [a for a in load_science_approvals(science) if a.subject_id == EVIDENCE] == shared
    for relative, (content, mode) in before.items():
        if DESIGNATED not in relative.name and relative.as_posix() != 'REGISTRY.md':
            assert (science / relative).read_bytes() == content
            assert (science / relative).stat().st_mode == mode
    with pytest.raises(ValueError, match='terminally stopped'):
        project_active_registry(load_science_registry(science), BASELINE)
    assert materialize_science_approvals(science, approvals, activation_context=context) == []
    context.verify_replay(binding, approvals, root)


@pytest.mark.parametrize('mutation', ['missing', 'unknown', 'string-version', 'bool-version', 'float-version',
    'supersedes', 'generic', 'stop-pin', 'digest', 'modalities', 'duplicate-parameter'])
def test_designated_raw_amendment_denies_malformed_or_generic_inputs(tmp_path, mutation):
    from copy import deepcopy
    import yaml
    from analysis.science_admission_amendment import DESIGNATED
    _, science, _, _, original = designated_case(tmp_path)
    raw = deepcopy(original)
    value = raw['model_parameters'][-1]['value']
    if mutation == 'missing': value.pop('baseline_subject')
    if mutation == 'unknown': value['authorized'] = True
    if mutation == 'string-version': raw['version'] = '2'
    if mutation == 'bool-version': value['baseline_version'] = True
    if mutation == 'float-version': raw['version'] = 2.0
    if mutation == 'supersedes': raw['supersedes'] = ['sdr-activity-dfa-alpha1-v1']
    if mutation == 'generic': raw['id'] = 'sdr-other-dfa-v2'
    if mutation == 'stop-pin': value['baseline_stop_digest'] = 'sha256:'+'0'*64
    if mutation == 'digest': value['baseline_decision_digest'] = 'sha256:bad'
    if mutation == 'modalities': value['modalities'] = ['native_RR', True]
    if mutation == 'duplicate-parameter': raw['model_parameters'].append(raw['model_parameters'][-1])
    (science / 'decisions' / (DESIGNATED+'.yaml')).write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ValueError):
        load_science_registry(science)


@pytest.mark.parametrize('mutation', ['none', 'boolean', 'empty-activation', 'wrong-base', 'missing-denial', 'wrong-stop',
                                      'retimestamp', 'history-mode', 'history-bytes', 'index'])
def test_designated_authenticated_base_and_history_fail_closed(tmp_path, mutation):
    from analysis.science_admission_amendment import DESIGNATED, require_authenticated_amendment_base
    root, science, context, binding, _ = designated_case(tmp_path)
    if mutation == 'none': context = None
    if mutation == 'boolean': context = True
    if mutation == 'empty-activation': context = replace(context, validations={})
    if mutation == 'wrong-base': context = replace(context, base_sha=binding.reviewed_head_sha)
    if mutation in {'missing-denial', 'wrong-stop'}:
        proof = dict(context.validations[binding.envelope_digest])
        if mutation == 'missing-denial': proof.pop('baseline_guard_result')
        else: proof['admission_amendment'] = dict(proof['admission_amendment'], baseline_stop_digest='sha256:'+'0'*64)
        context = replace(context, validations={binding.envelope_digest:proof})
    if mutation == 'retimestamp':
        path = next((science / 'evidence').rglob('evidence-activity-dfa-alpha1-v1.yaml'))
        text = path.read_text(); import re
        path.write_text(re.sub(r'(?m)^reviewed_on:.*$', 'reviewed_on: 2026-10-08', text))
    if mutation in {'history-mode', 'history-bytes'}:
        path = next((science / 'approvals').glob('evidence-activity-dfa-alpha1-v1--*.yaml'))
        if mutation == 'history-mode': path.chmod(0o755)
        else: path.write_bytes(path.read_bytes()+b'\n# renewal or rewrite\n')
    if mutation == 'index': (science / 'REGISTRY.md').write_text('forged index\n')
    registry = load_science_registry(science)
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        require_authenticated_amendment_base(registry, context)


def test_designated_fixture_closure_is_semantic_and_keeps_evidence(tmp_path):
    import yaml
    from analysis.science_admission_amendment import DESIGNATED, prune_designated_fixture_closure
    from analysis.science_yaml import load_science_yaml
    _, science, _, _, _ = designated_case(tmp_path)
    shared = {p: p.read_bytes() for p in science.rglob('*') if p.is_file() and 'evidence-activity-dfa-alpha1-v1' in p.name}
    payload = load_science_yaml(next((science/'approvals').glob('sdr-activity-dfa-alpha1-v1--decision*.yaml')).read_text())
    payload['subject_id'] = DESIGNATED
    arbitrary = science/'approvals'/'arbitrary-accepted-filename.yaml'
    arbitrary.write_text(yaml.safe_dump(payload))
    prune_designated_fixture_closure(science)
    assert not arbitrary.exists() and not list(science.rglob(DESIGNATED+'.*'))
    load_science_registry(science)
    assert all(p.read_bytes() == content for p, content in shared.items())


def _designated_stop_context(science, context):
    from analysis.science_stop_github import StopContext
    from analysis.science_admission_amendment import BASELINE, BASELINE_STOP, BASELINE_CONTRACT
    manifest = dict(schema_version=1, purpose='stopped-maintenance', repository=context.repository,
        pull_request=context.pull_request, base_sha=context.base_sha, reviewed_head_sha=context.head_sha,
        diff_digest=diff_digest(context.repository_root, context.base_sha, context.head_sha),
        active_contract_digest=BASELINE_CONTRACT, subject_id=BASELINE, stop_digest=BASELINE_STOP,
        candidate_guard_result='denied', workflow_path=WORKFLOW_PATH, workflow_sha=context.base_sha,
        run_id=7, run_attempt=1, conclusion='success', required_jobs=[VALIDATION_JOB, PROBE_JOB])
    return StopContext(context.repository_root, context.repository, context.pull_request, context.base_sha,
                       context.head_sha, (), {BASELINE:manifest})


def test_designated_decision_only_acceptance_requires_real_baseline_denial_context(tmp_path):
    from analysis.science_admission_amendment import DESIGNATED
    from analysis.science_approval_workflow import _snapshot_tree
    root, science, context, _, _ = designated_case(tmp_path)
    registry = load_science_registry(science)
    decision = registry.decisions[DESIGNATED]
    role = ReviewRole.DECISION_APPROVER
    body = render_approval_comment_template(subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
        subject_id=DESIGNATED, subject_digest=science_decision_digest(decision), role=role,
        approval_statement=approval_statement_for_subject(registry,
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION, subject_id=DESIGNATED, role=role))
    comment = dict(id=90, body=body, user={'type':'User','login':'synthetic'},
        created_at='2026-10-08T00:00:00Z', html_url='https://github.com/praxys-run/praxys/pull/42#issuecomment-90')
    stopped = _designated_stop_context(science, context)
    snapshot = _snapshot_tree(science)
    with pytest.raises(ValueError, match='denial evidence'):
        approvals_from_github_comments(science, [comment], {'synthetic':'admin'},
                                      stop_context=replace(stopped, maintenance_evidence={}))
    assert _snapshot_tree(science) == snapshot
    approvals = approvals_from_github_comments(science, [comment], {'synthetic':'admin'}, stop_context=stopped)
    materialize_science_approvals(science, approvals, stop_context=stopped)
    accepted = load_science_registry(science).decisions[DESIGNATED]
    assert accepted.status.value == 'accepted' and accepted.artifact_policy.runtime_state.value == 'inactive'
    assert materialize_science_approvals(science, approvals, stop_context=stopped) == []


def test_designated_stopped_v2_cannot_project_or_authenticate(tmp_path):
    from analysis.science_admission_amendment import DESIGNATED
    from analysis.science_artifacts import load_science_approvals
    from analysis.science_implementation_stop import materialize_stop, stop_from_comment, render_stop_comment
    from scripts.check_projected_dfa_policy import synthetic_v2_registry
    root, _, _, binding, _ = designated_case(tmp_path)
    with synthetic_v2_registry(root, 'projected-active', binding.active_contract_digest) as (science, _):
        target_root = tmp_path/'stopped-v2'
        shutil.copytree(science, target_root/'data/science')
    git(target_root, 'init'); commit(target_root, 'synthetic V2 active')
    approval = next(a for a in load_science_approvals(target_root/'data/science')
                    if a.subject_id == DESIGNATED and a.role == ReviewRole.IMPLEMENTATION_REVIEWER)
    target=dict(schema_version=1, action='stop', repository=binding.repository, subject_id=DESIGNATED,
        active_contract_digest=approval.subject_digest, implementation_envelope_digest=approval.implementation_binding.envelope_digest)
    comment=dict(id=90, body=render_stop_comment(target), user={'type':'User','login':'synthetic'},
        created_at='2026-10-08T00:00:00Z', html_url='https://github.com/praxys-run/praxys/pull/1#issuecomment-90')
    materialize_stop(target_root, stop_from_comment(comment, 'admin', binding.repository))
    with pytest.raises(ValueError, match='terminally stopped'):
        project_active_registry(load_science_registry(target_root/'data/science'), DESIGNATED)
    from analysis.science_admission_amendment import require_authenticated_amendment_base
    with pytest.raises(ValueError, match='terminally stopped'):
        require_authenticated_amendment_base(load_science_registry(target_root/'data/science'), None)


def test_ordinary_successor_keeps_original_rejection(tmp_path):
    from analysis.science_admission_amendment import DESIGNATED
    import yaml
    _, science, _, _, raw = designated_case(tmp_path)
    raw['id'] = 'sdr-unrelated-proposal-v2'
    raw['model_parameters'].pop()
    raw['decision_review']['items'][0]['parameter_names'].remove('admission_amendment')
    (science/'decisions'/(DESIGNATED+'.yaml')).unlink()
    (science/'decisions'/'sdr-unrelated-proposal-v2.yaml').write_text(yaml.safe_dump(raw,sort_keys=False))
    with pytest.raises(ValueError, match='Successor activation'):
        project_active_registry(load_science_registry(science), raw['id'])


@pytest.mark.parametrize('mutation',['mixed','legacy-marker','unknown','duplicate','bool-schema','missing-role','evidence-renewal'])
def test_designated_composite_protocol_rejects_forged_or_partial_assertions(tmp_path,mutation):
    from analysis.science_activation import render_activation_comment,composite_approval_payloads
    from analysis.science_admission_amendment import DESIGNATED
    _,science,_,binding,_=designated_case(tmp_path)
    registry=load_science_registry(science)
    body=render_activation_comment(registry,DESIGNATED,binding)
    if mutation=='mixed': body+='\n<!-- praxys-science-activation:v1 {} -->'
    if mutation=='legacy-marker': body=body.replace('praxys-science-activation:v2','praxys-science-activation:v1')
    if mutation=='duplicate': body=body.replace('"schema_version":2','"schema_version":2,"schema_version":2')
    if mutation=='bool-schema': body=body.replace('"schema_version":2','"schema_version":true')
    if mutation=='unknown': body=body.replace('"schema_version":2','"schema_version":2,"authorized":true')
    if mutation in {'missing-role','evidence-renewal'}:
        prefix,encoded=body.split('<!-- praxys-science-activation:v2\n')
        payload=strict_json(encoded.split('\n-->')[0])
        if mutation=='missing-role': payload['approvals'].pop()
        else: payload['approvals'].append(dict(subject_kind='evidence_review',subject_id='evidence-activity-dfa-alpha1-v1',
            subject_digest='sha256:'+'0'*64,role='evidence_reviewer'))
        body=prefix+'<!-- praxys-science-activation:v2\n'+json.dumps(payload)+'\n-->'
    with pytest.raises(ValueError): composite_approval_payloads(body,registry)


@pytest.mark.parametrize('mutation',['missing-base-stop','candidate-base-stop','new-unrelated-history','index-mode'])
def test_designated_actual_base_stop_and_science_closure_are_not_candidate_authority(tmp_path,mutation):
    from analysis.science_admission_amendment import BASELINE,require_authenticated_amendment_base
    root,science,context,_,_=designated_case(tmp_path)
    if mutation=='index-mode': (science/'REGISTRY.md').chmod(0o755)
    if mutation=='new-unrelated-history': (science/'unapproved-history.txt').write_text('candidate assertion\n')
    if mutation in {'missing-base-stop','candidate-base-stop'}:
        # A different actual Git base without STOP cannot be repaired by a
        # candidate STOP or an asserted authority bit in local science data.
        relative='data/science/stops/'+BASELINE+'.yaml'
        stop=(root/relative).read_bytes()
        (root/relative).unlink()
        no_stop=commit(root,'synthetic candidate base lacks trusted STOP')
        (root/relative).write_bytes(stop)
        new_head=commit(root,'synthetic candidate-only STOP')
        context=replace(context,base_sha=no_stop,head_sha=new_head)
    with pytest.raises(ValueError): require_authenticated_amendment_base(load_science_registry(science),context)
