"""Prepare or materialize one exact human STOP using trusted-main code.

This command never creates a GitHub comment, pushes a branch, opens a PR or
executes candidate code. The maintainer uses the ordinary protected PR workflow.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from analysis.evidence_registry import load_science_registry
from analysis.science_activation import directory_tree, git, git_tree
from analysis.science_activation_github import GitHubReader
from analysis.science_artifacts import ReviewRole, load_science_approvals
from analysis.science_implementation_stop import materialize_stop, render_stop_comment
from analysis.science_stop_github import fetch_stop_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--subject-id', default='sdr-activity-dfa-alpha1-v1')
    parser.add_argument('--comment-id', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    reader = GitHubReader(args.repository)
    main_sha = reader.read('git/ref/heads/main')['object']['sha']
    root = args.candidate.resolve()
    for checkout in (PROJECT_ROOT, root):
        if git(checkout, 'rev-parse', 'HEAD').decode().strip() != main_sha:
            raise ValueError('STOP command requires trusted current-main code and a candidate branch at that same base')
        expected = git_tree(checkout, main_sha)
        if directory_tree(checkout, expected, repository=checkout) != expected:
            raise ValueError('STOP command requires clean trusted-main source and candidate trees')
    registry = load_science_registry(root / 'data/science')
    approvals = [a for a in load_science_approvals(registry.science_dir)
                 if a.subject_id == args.subject_id and a.role == ReviewRole.IMPLEMENTATION_REVIEWER]
    if len(approvals) != 1:
        raise ValueError('STOP target must have exactly one current implementation binding')
    approval = approvals[0]
    target = dict(schema_version=1, action='stop', repository=args.repository, subject_id=args.subject_id,
                  active_contract_digest=approval.subject_digest,
                  implementation_envelope_digest=approval.implementation_binding.envelope_digest)
    if args.comment_id is None:
        if args.output is None or args.output.resolve().is_relative_to(root) or args.output.resolve().is_relative_to(PROJECT_ROOT):
            parser.error('--output outside both source trees is required to prepare the exact STOP statement')
        args.output.write_text(render_stop_comment(target)+'\n')
        print('Prepared exact STOP statement only. No stop was published or recorded.')
        print(f'After explicit human approval, transcribe it to original activation PR #{approval.implementation_binding.pull_request}.')
        return
    stop = fetch_stop_source(reader, args.comment_id)
    if stop.target != target:
        raise ValueError('Authenticated STOP is not the exact current trusted target')
    def recheck():
        if (reader.read('git/ref/heads/main')['object']['sha'] != main_sha
                or any(git(checkout, 'rev-parse', 'HEAD').decode().strip() != main_sha
                       for checkout in (PROJECT_ROOT, root))):
            raise ValueError('Trusted main changed before STOP materialization')
        if fetch_stop_source(reader, args.comment_id) != stop:
            raise ValueError('STOP source or permission changed before publication')
    changed = materialize_stop(root, stop, recheck=recheck)
    print('Recorded source STOP only; commit the exact stop-only diff through the ordinary protected PR workflow.')
    for path in changed:
        print('data/science/'+path.as_posix())


if __name__ == '__main__':
    main()
