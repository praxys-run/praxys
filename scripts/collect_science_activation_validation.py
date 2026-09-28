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
    VALIDATION_JOB, WORKFLOW_PATH, diff_digest, git, project_active_registry,
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
    verify_jobs(jobs, [VALIDATION_JOB])
    registry = load_science_registry(args.candidate / 'data/science')
    projected = project_active_registry(registry, inputs['subject_id'])
    contract = build_policy_contract(projected, inputs['subject_id'])
    if contract.contract_digest != inputs['active_contract_digest']:
        raise ValueError('Collector projected contract differs from dispatched exact digest')
    manifest = {
        'schema_version': 1, 'repository': repository, 'pull_request': number,
        'base_sha': base, 'reviewed_head_sha': head,
        'diff_digest': diff_digest(args.candidate, base, head),
        'active_contract_digest': contract.contract_digest,
        'subject_id': inputs['subject_id'], 'workflow_path': WORKFLOW_PATH,
        'workflow_sha': workflow_sha, 'run_id': run_id, 'run_attempt': attempt,
        'conclusion': 'success', 'required_jobs': [VALIDATION_JOB],
    }
    verify_pr(reader.read(f'pulls/{number}'), repository, number, base, head)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
