"""Read-only GitHub authentication of activation validation and live PR state."""
from __future__ import annotations

from hashlib import sha256
import io
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

from analysis.science_activation import (
    ActivationContext, COLLECTOR_JOB, VALIDATION_JOB, PROBE_JOB, WORKFLOW_PATH,
    COMPOSITE_MARKER, V2_COMPOSITE_MARKER, git, implementation_envelope, strict_json,
)
from analysis.science_artifacts import ImplementationBinding, digest_payload


class _NoCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        if urlparse(new_url).scheme != 'https':
            raise ValueError('Activation evidence redirects must use HTTPS')
        redirected = super().redirect_request(request, fp, code, message, headers, new_url)
        if urlparse(request.full_url).netloc != urlparse(new_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


class GitHubReader:
    def __init__(self, repository: str):
        if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) is None:
            raise ValueError('GitHub repository must be an exact owner/name')
        self.repository = repository
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not self.token:
            raise ValueError('Authenticated read-only GitHub token is required')

    def read(self, path: str, *, binary=False):
        request = Request('https://api.github.com/repos/' + self.repository + '/' + path,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Accept': 'application/vnd.github+json',
                                   'X-GitHub-Api-Version': '2022-11-28'})
        with build_opener(_NoCredentialRedirect()).open(request, timeout=30) as response:
            data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError('GitHub response exceeds activation evidence bound')
        return data if binary else strict_json(data.decode())

    def pages(self, path: str, key=None):
        result = []
        for page in range(1, 101):
            data = self.read(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
            values = data[key] if key else data
            result.extend(values)
            if len(values) < 100:
                return result
        raise ValueError('GitHub pagination exceeds activation evidence bound')


def verify_pr(pr, repository: str, number: int, base_sha: str, head_sha: str):
    if (pr.get('number') != number or pr.get('state') != 'open'
            or pr['base']['ref'] != 'main'
            or pr['base']['repo']['full_name'] != repository
            or pr['head']['repo']['full_name'] != repository
            or pr['base']['sha'] != base_sha or pr['head']['sha'] != head_sha):
        raise ValueError('Activation pull request identity or base/head changed')


def verify_jobs(jobs, required):
    for name in required:
        matches = [job for job in jobs if job.get('name') == name]
        if len(matches) != 1 or matches[0].get('conclusion') != 'success':
            raise ValueError(f'Activation validation required job did not succeed: {name}')


def fetch_validation(reader: GitHubReader, binding: ImplementationBinding, repository_root: Path):
    run = reader.read(f'actions/runs/{binding.validation_run_id}')
    if (run.get('repository', {}).get('full_name') != binding.repository
            or run.get('head_repository', {}).get('full_name') != binding.repository
            or run.get('event') != 'workflow_dispatch' or run.get('head_branch') != 'main'
            or run.get('path') != WORKFLOW_PATH
            or run.get('head_sha') != binding.validation_workflow_sha
            or run.get('run_attempt') != binding.validation_run_attempt
            or run.get('conclusion') != 'success'):
        raise ValueError('Validation workflow identity, revision, attempt or outcome mismatch')
    git(repository_root, 'merge-base', '--is-ancestor', binding.validation_workflow_sha, binding.base_sha)
    jobs = reader.pages(f'actions/runs/{binding.validation_run_id}/attempts/{binding.validation_run_attempt}/jobs', 'jobs')
    verify_jobs(jobs, [VALIDATION_JOB, PROBE_JOB, COLLECTOR_JOB])
    artifact = reader.read(f'actions/artifacts/{binding.validation_artifact_id}')
    expected_name = f'science-activation-validation-{binding.validation_run_id}-{binding.validation_run_attempt}'
    if (artifact.get('name') != expected_name or artifact.get('expired') is not False
            or artifact.get('workflow_run', {}).get('id') != binding.validation_run_id
            or artifact.get('workflow_run', {}).get('head_sha') != binding.validation_workflow_sha
            or artifact.get('size_in_bytes', 0) > 65536):
        raise ValueError('Validation artifact identity or retention mismatch')
    content = reader.read(f'actions/artifacts/{binding.validation_artifact_id}/zip', binary=True)
    if artifact.get('digest') != 'sha256:' + sha256(content).hexdigest():
        raise ValueError('Validation artifact archive digest mismatch')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if archive.namelist() != ['validation.json'] or archive.getinfo('validation.json').file_size > 16384:
            raise ValueError('Validation artifact must contain only bounded validation.json')
        validation = strict_json(archive.read('validation.json').decode())
    if digest_payload(validation) != binding.validation_digest:
        raise ValueError('Validation content digest mismatch')
    from analysis.science_activation import V2_PURPOSE
    if isinstance(validation, dict) and validation.get('purpose') == V2_PURPOSE:
        # Strict V2 metadata bindings supplement the unchanged legacy protocol.
        if (type(run.get('id')) is not int or run['id'] != binding.validation_run_id
                or type(artifact.get('id')) is not int or artifact['id'] != binding.validation_artifact_id
                or type(run.get('run_attempt')) is not int
                or type(artifact.get('workflow_run', {}).get('id')) is not int):
            raise ValueError('V2 artifact/run identity types or values mismatch')
        expected_jobs = [VALIDATION_JOB, PROBE_JOB, COLLECTOR_JOB]
        for job in jobs:
            if job.get('name') in expected_jobs and (type(job.get('id')) is not int
                    or job['id'] <= 0 or type(job.get('run_id')) is not int
                    or job['run_id'] != binding.validation_run_id
                    or job.get('status') != 'completed'):
                raise ValueError('V2 jobs must be completed authenticated exact-run jobs')
        job_ids = [job['id'] for job in jobs if job.get('name') in expected_jobs]
        if len(set(job_ids)) != len(expected_jobs):
            raise ValueError('V2 authenticated job identities must be distinct')
    return validation


def authenticated_context(science_dir: Path, comments, permissions, *, repository: str | None, pull_request: int | None):
    """Refresh identity/source, validation and exact PR snapshot before writes."""
    from analysis.science_approval_workflow import _reject_symlinks
    _reject_symlinks(science_dir)
    if not any(any(marker in str(c.get('body', '')) for marker in
                   ('praxys-science-implementation:v1', COMPOSITE_MARKER, V2_COMPOSITE_MARKER)) for c in comments):
        return None, comments, permissions
    if not repository or not pull_request:
        raise ValueError('Activation requires explicit repository and pull request')
    reader = GitHubReader(repository)
    comments = reader.pages(f'issues/{pull_request}/comments')
    permissions = {}
    for comment in comments:
        user = comment.get('user', {})
        login = user.get('login')
        if user.get('type') == 'User' and isinstance(login, str) and not login.endswith('[bot]'):
            permissions[login] = reader.read(f'collaborators/{quote(login, safe="")}/permission')['permission']
    pr = reader.read(f'pulls/{pull_request}')
    base_sha, head_sha = pr['base']['sha'], pr['head']['sha']
    verify_pr(pr, repository, pull_request, base_sha, head_sha)
    root = science_dir.resolve().parent.parent
    if git(root, 'rev-parse', 'HEAD').decode().strip() != head_sha:
        raise ValueError('Checked-out activation head is stale')
    validations = {}
    for comment in comments:
        if permissions.get(comment.get('user', {}).get('login')) not in {'write', 'maintain', 'admin'}:
            continue
        payload = implementation_envelope(str(comment.get('body', '')))
        if payload:
            binding = ImplementationBinding.model_validate(payload['implementation_binding'])
            if binding.repository != repository or binding.pull_request != pull_request:
                raise ValueError('Approval belongs to another repository or PR')
            validations[binding.envelope_digest] = fetch_validation(reader, binding, root)
    original_comments = comments
    original_permissions = dict(permissions)
    def recheck():
        verify_pr(reader.read(f'pulls/{pull_request}'), repository, pull_request, base_sha, head_sha)
        if reader.pages(f'issues/{pull_request}/comments') != original_comments:
            raise ValueError('Approval source changed during activation materialization')
        for login, permission in original_permissions.items():
            if reader.read(f'collaborators/{quote(login, safe="")}/permission')['permission'] != permission:
                raise ValueError('Reviewer permission changed during activation materialization')
        for comment in original_comments:
            if original_permissions.get(comment.get('user', {}).get('login')) not in {'write', 'maintain', 'admin'}:
                continue
            payload = implementation_envelope(str(comment.get('body', '')))
            if payload:
                binding = ImplementationBinding.model_validate(payload['implementation_binding'])
                if fetch_validation(reader, binding, root) != validations[binding.envelope_digest]:
                    raise ValueError('Validation changed during activation materialization')
    context = ActivationContext(root, repository, pull_request, base_sha, head_sha, validations, recheck)
    verify_pr(reader.read(f'pulls/{pull_request}'), repository, pull_request, base_sha, head_sha)
    return context, comments, permissions
