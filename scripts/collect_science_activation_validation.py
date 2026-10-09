"""Construct validation evidence on a separate trusted collector runner."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.evidence_registry import load_science_registry
from analysis.science_activation import (
    VALIDATION_JOB, PROBE_JOB, WORKFLOW_PATH, V2_PURPOSE, diff_digest, git, project_active_registry,
)
from analysis.science_activation_github import GitHubReader, verify_jobs, verify_pr
from analysis.science_artifacts import build_policy_contract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = os.environ['GITHUB_REPOSITORY']
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    inputs = event['inputs']
    head = inputs['candidate_sha']
    number = int(inputs['pull_request'])
    reader = GitHubReader(repository)
    pr = reader.read(f'pulls/{number}')
    base = pr['base']['sha']
    verify_pr(pr, repository, number, base, head)
    if git(args.candidate, 'rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('Collector candidate checkout mismatch')
    git(args.candidate, 'merge-base', '--is-ancestor', base, head)
    workflow_sha = os.environ['GITHUB_SHA']
    git(args.candidate, 'merge-base', '--is-ancestor', workflow_sha, base)
    run_id, attempt = int(os.environ['GITHUB_RUN_ID']), int(os.environ['GITHUB_RUN_ATTEMPT'])
    jobs = reader.pages(f'actions/runs/{run_id}/attempts/{attempt}/jobs', 'jobs')
    verify_jobs(jobs, [VALIDATION_JOB, PROBE_JOB])
    registry = load_science_registry(args.candidate / 'data/science')
    purpose = inputs.get('purpose', 'activation')
    if purpose == V2_PURPOSE:
        for job in jobs:
            if job.get('name') in (VALIDATION_JOB, PROBE_JOB) and (type(job.get('id')) is not int
                    or job['id'] <= 0 or type(job.get('run_id')) is not int
                    or job['run_id'] != run_id or job.get('status') != 'completed'):
                raise ValueError('V2 collector requires authenticated completed exact-run job identities')
        if len({job['id'] for job in jobs if job.get('name') in (VALIDATION_JOB, PROBE_JOB)}) != 2:
            raise ValueError('V2 collector job identities must be distinct')
        from analysis.science_admission_amendment import DESIGNATED, require_authenticated_amendment_base, amendment_value
        if inputs['subject_id'] != DESIGNATED:
            raise ValueError('V2 collector requires designated subject')
        projected = project_active_registry(registry, DESIGNATED)
        contract = build_policy_contract(projected, DESIGNATED)
        stop_fields = dict(purpose=V2_PURPOSE, baseline_guard_result='denied',
                           admission_amendment=amendment_value(registry.decisions[DESIGNATED]).model_dump(mode='json'))
    elif purpose == 'activation':
        projected = project_active_registry(registry, inputs['subject_id'])
        contract = build_policy_contract(projected, inputs['subject_id'])
        stop_fields = {}
    elif purpose == 'stopped-maintenance':
        from analysis.science_implementation_stop import load_implementation_stops
        stops = [stop for stop in load_implementation_stops(registry.science_dir)
                 if stop.subject_id == inputs['subject_id']]
        if len(stops) != 1:
            raise ValueError('Candidate does not preserve a terminal stop')
        stop = stops[0]
        # The stopped artifact must already exist, byte-identical, on trusted base.
        relative = f'data/science/stops/{stop.subject_id}.yaml'
        if git(args.candidate, 'show', base + ':' + relative) != git(args.candidate, 'show', head + ':' + relative):
            raise ValueError('Candidate cannot supply its own maintenance-unlocking stop')
        contract = build_policy_contract(registry, inputs['subject_id'])
        stop_fields = {'purpose':'stopped-maintenance', 'stop_digest':stop.stop_digest,
                       'candidate_guard_result':'denied'}
    else:
        raise ValueError('Unsupported validation purpose')
    if contract.contract_digest != inputs['active_contract_digest']:
        raise ValueError('Collector projected contract differs from dispatched exact digest')
    manifest = {
        'schema_version': 2 if purpose == V2_PURPOSE else 1, 'repository': repository, 'pull_request': number,
        'base_sha': base, 'reviewed_head_sha': head,
        'diff_digest': diff_digest(args.candidate, base, head),
        'active_contract_digest': contract.contract_digest,
        'subject_id': inputs['subject_id'], 'workflow_path': WORKFLOW_PATH,
        'workflow_sha': workflow_sha, 'run_id': run_id, 'run_attempt': attempt,
        'conclusion': 'success', 'required_jobs': [VALIDATION_JOB, PROBE_JOB], **stop_fields,
    }
    if purpose == V2_PURPOSE:
        from analysis.science_activation import ActivationContext, directory_tree, git_tree
        tree = git_tree(args.candidate, head)
        if directory_tree(args.candidate, tree, repository=args.candidate) != tree:
            raise ValueError('V2 collector candidate files differ from exact reviewed head')
        context = ActivationContext(args.candidate.resolve(), repository, number, base, head, {'collector': manifest})
        require_authenticated_amendment_base(registry, context)
    verify_pr(reader.read(f'pulls/{number}'), repository, number, base, head)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
