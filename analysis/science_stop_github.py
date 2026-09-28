"""Authenticate terminal-stop sources and isolated maintenance evidence."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable, Mapping
from urllib.parse import quote

from analysis.science_activation import COLLECTOR_JOB, VALIDATION_JOB, PROBE_JOB, WORKFLOW_PATH, diff_digest, git
from analysis.science_activation_github import GitHubReader, verify_jobs, verify_pr
from analysis.science_implementation_stop import (
    ImplementationStop, load_implementation_stops, stop_from_comment, validate_stop_target,
)


@dataclass(frozen=True)
class StopContext:
    repository_root: Path
    repository: str
    pull_request: int
    base_sha: str
    head_sha: str
    authenticated_stops: tuple[ImplementationStop, ...]
    maintenance_evidence: Mapping[str, dict]
    recheck: Callable[[], None] | None = None

    def require_denial(self, stop: ImplementationStop) -> None:
        manifest = self.maintenance_evidence.get(stop.subject_id)
        if manifest is None:
            raise ValueError('Stopped governed maintenance requires authenticated isolated actual-guard denial evidence')
        required = {
            'schema_version':1, 'purpose':'stopped-maintenance', 'repository':self.repository,
            'pull_request':self.pull_request, 'base_sha':self.base_sha, 'reviewed_head_sha':self.head_sha,
            'diff_digest':diff_digest(self.repository_root, self.base_sha, self.head_sha),
            'active_contract_digest':stop.active_contract_digest, 'subject_id':stop.subject_id,
            'stop_digest':stop.stop_digest, 'candidate_guard_result':'denied',
            'workflow_path':WORKFLOW_PATH, 'conclusion':'success', 'required_jobs':[VALIDATION_JOB, PROBE_JOB],
        }
        if (set(manifest) != set(required) | {'workflow_sha', 'run_id', 'run_attempt'}
                or any(manifest.get(key) != value for key, value in required.items())):
            raise ValueError('Stopped maintenance validation target, revision or result mismatch')


def fetch_stop_source(reader: GitHubReader, comment_id: int) -> ImplementationStop:
    comment = reader.read(f'issues/comments/{comment_id}')
    if comment.get('id') != comment_id:
        raise ValueError('STOP source comment identity mismatch')
    user = comment.get('user', {})
    login = user.get('login')
    if user.get('type') != 'User' or not isinstance(login, str) or login.endswith('[bot]'):
        raise ValueError('STOP source must identify a human')
    permission = reader.read(f'collaborators/{quote(login, safe="")}/permission')['permission']
    return stop_from_comment(comment, permission, reader.repository)


def source_id(stop: ImplementationStop) -> int:
    match = re.search(r'#issuecomment-([1-9][0-9]*)$', str(stop.source_ref))
    if match is None:
        raise ValueError('STOP source is not an immutable comment identity')
    return int(match.group(1))


def _read_validation_artifact(reader, artifact):
    from hashlib import sha256
    import io
    import zipfile
    from analysis.science_activation import strict_json
    if artifact.get('expired') is not False or artifact.get('size_in_bytes', 0) > 65536:
        raise ValueError('Stopped-maintenance artifact retention or size is invalid')
    raw = reader.read(f"actions/artifacts/{artifact['id']}/zip", binary=True)
    if artifact.get('digest') != 'sha256:' + sha256(raw).hexdigest():
        raise ValueError('Stopped-maintenance artifact digest mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.namelist() != ['validation.json'] or archive.getinfo('validation.json').file_size > 16384:
            raise ValueError('Stopped-maintenance artifact layout is invalid')
        return strict_json(archive.read('validation.json').decode())


def find_denial_evidence(reader, root: Path, base: str, head: str, number: int, stop: ImplementationStop):
    workflow = quote(WORKFLOW_PATH.rsplit('/', 1)[1], safe='')
    runs = reader.read(f'actions/workflows/{workflow}/runs?event=workflow_dispatch&status=success&per_page=30')['workflow_runs']
    for run in runs:
        if (run.get('path') != WORKFLOW_PATH or run.get('head_branch') != 'main'
                or run.get('event') != 'workflow_dispatch' or run.get('conclusion') != 'success'
                or run.get('repository', {}).get('full_name') != reader.repository
                or run.get('head_repository', {}).get('full_name') != reader.repository):
            continue
        artifacts = reader.pages(f"actions/runs/{run['id']}/artifacts", 'artifacts')
        expected_name = f"science-activation-validation-{run['id']}-{run['run_attempt']}"
        for artifact in artifacts:
            if artifact.get('name') != expected_name:
                continue
            manifest = _read_validation_artifact(reader, artifact)
            if (manifest.get('purpose') != 'stopped-maintenance'
                    or manifest.get('repository') != reader.repository
                    or manifest.get('pull_request') != number
                    or manifest.get('base_sha') != base or manifest.get('reviewed_head_sha') != head
                    or manifest.get('subject_id') != stop.subject_id or manifest.get('stop_digest') != stop.stop_digest):
                continue
            if (manifest.get('run_id') != run['id'] or manifest.get('run_attempt') != run['run_attempt']
                    or manifest.get('workflow_sha') != run['head_sha']
                    or artifact.get('workflow_run', {}).get('id') != run['id']
                    or artifact.get('workflow_run', {}).get('head_sha') != run['head_sha']):
                raise ValueError('Stopped-maintenance producer or attempt mismatch')
            git(root, 'merge-base', '--is-ancestor', run['head_sha'], base)
            jobs = reader.pages(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", 'jobs')
            verify_jobs(jobs, [VALIDATION_JOB, PROBE_JOB, COLLECTOR_JOB])
            return manifest
    raise ValueError('Run the trusted stopped-maintenance validation workflow for this exact PR head first')


def authenticated_stop_context(base_science_dir: Path, head_science_dir: Path, *, repository: str | None,
                               pull_request: int | None) -> StopContext | None:
    from analysis.science_approval_workflow import _reject_symlinks
    _reject_symlinks(base_science_dir)
    _reject_symlinks(head_science_dir)
    base_stops = load_implementation_stops(base_science_dir)
    head_stops = load_implementation_stops(head_science_dir)
    if not base_stops and not head_stops:
        return None
    if not repository or not pull_request:
        raise ValueError('STOP verification requires explicit authenticated repository/PR context')
    root = head_science_dir.resolve().parent.parent
    reader = GitHubReader(repository)
    pr = reader.read(f'pulls/{pull_request}')
    base, head = pr['base']['sha'], pr['head']['sha']
    verify_pr(pr, repository, pull_request, base, head)
    if git(root, 'rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('STOP candidate head changed')
    if git(base_science_dir.resolve().parent.parent, 'rev-parse', 'HEAD').decode().strip() != base:
        raise ValueError('STOP trusted-base snapshot changed')
    sources = []
    for stop in head_stops:
        if stop not in base_stops:
            if stop.repository != repository:
                raise ValueError('STOP source belongs to another repository')
            actual = fetch_stop_source(reader, source_id(stop))
            if actual != stop:
                raise ValueError('STOP artifact does not match fresh authenticated source')
            sources.append(actual)
    evidence = {}
    # Only a stop already in trusted base can unlock a later governed change.
    from analysis.science_activation import governed_changes
    for stop in base_stops:
        if governed_changes(base_science_dir.parent.parent, head_science_dir.parent.parent, stop.subject_id):
            evidence[stop.subject_id] = find_denial_evidence(reader, root, base, head, pull_request, stop)
    def recheck():
        verify_pr(reader.read(f'pulls/{pull_request}'), repository, pull_request, base, head)
        for stop in sources:
            if fetch_stop_source(reader, source_id(stop)) != stop:
                raise ValueError('STOP source or permission changed before verification finished')
        for stop in base_stops:
            if stop.subject_id in evidence and find_denial_evidence(reader, root, base, head, pull_request, stop) != evidence[stop.subject_id]:
                raise ValueError('Stopped-maintenance validation changed during verification')
    return StopContext(root, repository, pull_request, base, head, tuple(sources), evidence, recheck)
