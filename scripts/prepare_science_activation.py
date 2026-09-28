"""Prepare exact source-backed activation statements without publishing approval."""
from __future__ import annotations
import argparse
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.evidence_registry import ApprovalMode, load_science_registry
from analysis.science_activation import (
    ActivationContext, diff_digest, git, project_active_registry, render_implementation_comment, strict_json,
)
from analysis.science_activation_github import GitHubReader, fetch_validation, verify_pr
from analysis.science_artifacts import (
    ImplementationBinding, ReviewRole, ReviewSubjectKind, approval_statement_for_subject,
    build_policy_contract, digest_payload, evidence_review_digest, render_approval_comment_template,
    science_decision_digest,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--pull-request', type=int, required=True)
    parser.add_argument('--subject-id', default='sdr-activity-dfa-alpha1-v1')
    parser.add_argument('--validation-run', type=int, required=True)
    parser.add_argument('--validation-artifact', type=int, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    root = args.candidate.resolve()
    if args.output_dir.resolve().is_relative_to(root):
        parser.error('Review package must be outside the frozen candidate tree')
    reader = GitHubReader(args.repository)
    pr = reader.read(f'pulls/{args.pull_request}')
    base, head = pr['base']['sha'], pr['head']['sha']
    verify_pr(pr, args.repository, args.pull_request, base, head)
    if git(root, 'rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('Candidate checkout differs from current PR head')
    registry = load_science_registry(root / 'data/science')
    projected = project_active_registry(registry, args.subject_id)
    decision = projected.decisions[args.subject_id]
    contract = build_policy_contract(projected, args.subject_id)
    run = reader.read(f'actions/runs/{args.validation_run}')
    content = reader.read(f'actions/artifacts/{args.validation_artifact}/zip', binary=True)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.namelist() != ['validation.json'] or archive.getinfo('validation.json').file_size > 16384:
            raise ValueError('Invalid validation artifact layout')
        validation = strict_json(archive.read('validation.json').decode())
    binding = ImplementationBinding(version=1, repository=args.repository, pull_request=args.pull_request,
        base_sha=base, reviewed_head_sha=head, diff_digest=diff_digest(root, base, head),
        active_contract_digest=contract.contract_digest, validation_run_id=args.validation_run,
        validation_run_attempt=run['run_attempt'], validation_workflow_sha=run['head_sha'],
        validation_artifact_id=args.validation_artifact, validation_digest=digest_payload(validation))
    verified = fetch_validation(reader, binding, root)
    context = ActivationContext(root, args.repository, args.pull_request, base, head,
                                {binding.envelope_digest:verified})
    context.verify(binding, registry, args.subject_id)
    context.require_reviewed_tree(binding, root)
    statements = {}
    for evidence_id in decision.evidence_review_ids:
        review = projected.evidence_reviews[evidence_id]
        if review.approval_mode != ApprovalMode.ARTIFACT:
            continue
        role, kind = ReviewRole.EVIDENCE_REVIEWER, ReviewSubjectKind.EVIDENCE_REVIEW
        statements[f'{evidence_id}--{role.value}.md'] = render_approval_comment_template(
            subject_kind=kind, subject_id=evidence_id, subject_digest=evidence_review_digest(review), role=role,
            approval_statement=approval_statement_for_subject(projected, subject_kind=kind, subject_id=evidence_id, role=role))
    role, kind = ReviewRole.DECISION_APPROVER, ReviewSubjectKind.SCIENCE_DECISION
    statements[f'{args.subject_id}--{role.value}.md'] = render_approval_comment_template(
        subject_kind=kind, subject_id=args.subject_id, subject_digest=science_decision_digest(decision), role=role,
        approval_statement=approval_statement_for_subject(projected, subject_kind=kind, subject_id=args.subject_id, role=role))
    statements[f'{args.subject_id}--implementation_reviewer.md'] = render_implementation_comment(args.subject_id, binding)
    verify_pr(reader.read(f'pulls/{args.pull_request}'), args.repository, args.pull_request, base, head)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, body in statements.items():
        (args.output_dir / name).write_text(body + '\n')
    (args.output_dir / 'binding.json').write_text(json.dumps(binding.model_dump(mode='json'), indent=2, sort_keys=True)+'\n')
    (args.output_dir / 'validation.json').write_text(json.dumps(verified, indent=2, sort_keys=True)+'\n')
    print(f'Prepared {len(statements)} exact role statements. No approval was published or materialized.')
    print(f'Envelope: {binding.envelope_digest}')


if __name__ == '__main__':
    main()
