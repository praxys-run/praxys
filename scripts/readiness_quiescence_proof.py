"""Authenticate one bounded, nonsecret quiescence archive using public metadata.

The original ZIP is relayed as canonical base64 data. No credential, authenticated
fallback, extraction, artifact execution, history scan or single-use ledger exists.
"""
from __future__ import annotations

import base64
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile

REPOSITORY = 'praxys-run/praxys'
WORKFLOW = '.github/workflows/deploy-backend.yml'
SERVING_SOURCE = '00577ce859ff90bbdf50a90e8ba00c4822243ec4'
MEMBER = 'quiescence-proof.json'
ARTIFACT_PREFIX = 'readiness-quiescence'
MAX_ZIP = 8192
MAX_ENCODED = 4 * ((MAX_ZIP + 2) // 3)
MAX_PROOF = 2048
MAX_METADATA = 262144
QUIESCE = 'Quiesce feedback publication before deployment'
UPLOAD = 'Publish acknowledged pre-quiescence intent proof'
POST_QUIESCE = (
    'Validate production deployment settings',
    'Enforce backend telemetry trust boundary',
    'Sync App Service settings',
    'Cut over backend telemetry and alerts',
    'Wait for App Service deployment endpoint to settle',
    'Deploy to App Service',
    'Verify deployed backend cutover',
    'Restore reviewed feedback publication after verified cutover',
    'Set up source-policy observation interpreter after restoration',
    'Install source-policy observation dependencies after restoration',
    'Observe exact DFA policy after normal publication restoration',
)


def require(condition: bool) -> None:
    if not condition:
        raise ValueError('Quiescence proof rejected')


def positive_id(value: str) -> int:
    require(isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,19}', value) is not None)
    return int(value)


def strict_json(raw: bytes):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result)
            result[key] = value
        return result
    def constant(_value):
        raise ValueError('Non-finite JSON')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)


def expected_proof(target: str, run_id: int) -> dict:
    require(re.fullmatch(r'[0-9a-f]{40}', target) is not None)
    require(type(run_id) is int and run_id > 0)
    return {
        'schema_version': 1, 'purpose': 'readiness-quiescence-00577',
        'repository': REPOSITORY, 'workflow_path': WORKFLOW,
        'target_sha': target, 'producer_run_id': run_id, 'producer_run_attempt': 1,
        'serving_source_sha': SERVING_SOURCE, 'sync_config': True, 'protected_main': True,
        'original_positive': True, 'configured_positive': True,
        'disable_acknowledged': True, 'readback_positive': False,
    }


def create_proof(environment: dict[str, str]) -> Path:
    require(environment.get('GITHUB_REPOSITORY') == REPOSITORY)
    require(environment.get('GITHUB_EVENT_NAME') == 'push')
    require(environment.get('GITHUB_REF') == 'refs/heads/main')
    require(environment.get('GITHUB_RUN_ATTEMPT') == '1')
    require(environment.get('GITHUB_REF_PROTECTED') == 'true')
    for key in ('SYNC_CONFIG', 'ORIGINAL_FEEDBACK_PUBLICATION',
                'CONFIGURED_FEEDBACK_PUBLICATION', 'DISABLE_ACKNOWLEDGED'):
        require(environment.get(key) == 'true')
    require(environment.get('READBACK_POSITIVE') == 'false')
    require(environment.get('PRODUCER_SOURCE_SHA') == SERVING_SOURCE)
    proof = expected_proof(environment['GITHUB_SHA'], positive_id(environment['GITHUB_RUN_ID']))
    path = Path(environment['RUNNER_TEMP']) / MEMBER
    # Never overwrite a stale/manual file; only a completed write can be uploaded.
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(proof, sort_keys=True, separators=(',', ':')) + '\n')
    return path


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Metadata redirects are not accepted')


class PublicMetadata:
    """Fixed-repository anonymous HTTPS, independent of ambient tokens/proxies."""
    def __init__(self):
        self.deadline = time.monotonic() + 50
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def read(self, path: str):
        require(re.fullmatch(r'(?:branches/main|actions/runs/[1-9][0-9]{0,19}(?:/attempts/1/jobs\?per_page=100|/artifacts\?per_page=100)?|actions/artifacts/[1-9][0-9]{0,19})', path) is not None)
        remaining = self.deadline - time.monotonic()
        require(remaining > 0)
        request = Request(f'https://api.github.com/repos/{REPOSITORY}/{path}', headers={
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'praxys-readiness-proof', 'Cache-Control': 'no-cache',
        })
        with self.opener.open(request, timeout=min(10, remaining)) as response:
            require(response.getcode() == 200)
            length = response.headers.get('Content-Length')
            if length is not None:
                require(length.isdecimal() and int(length) <= MAX_METADATA)
            raw = response.read(MAX_METADATA + 1)
        require(len(raw) <= MAX_METADATA and time.monotonic() < self.deadline)
        if length is not None:
            require(len(raw) == int(length))
        return strict_json(raw)


def _collection(payload, key):
    require(isinstance(payload, dict) and isinstance(payload.get(key), list))
    values = payload[key]
    require(type(payload.get('total_count')) is int and payload['total_count'] == len(values) <= 100)
    require(all(isinstance(value, dict) for value in values))
    return values


def _one(values, name):
    matches = [value for value in values if value.get('name') == name]
    require(len(matches) == 1)
    return matches[0]


def _branch(branch, target):
    require(branch.get('name') == 'main' and branch.get('protected') is True)
    require(branch.get('commit', {}).get('sha') == target)


def _run(run, run_id, target):
    expected = {'id': run_id, 'event': 'push', 'head_branch': 'main',
                'path': WORKFLOW, 'head_sha': target, 'run_attempt': 1,
                'status': 'completed', 'conclusion': 'failure'}
    require(all(type(run.get(key)) is type(value) and run[key] == value for key, value in expected.items()))
    require(run.get('repository', {}).get('full_name') == REPOSITORY)
    require(run.get('head_repository', {}).get('full_name') == REPOSITORY)


def _jobs(payload, target):
    job = _one(_collection(payload, 'jobs'), 'deploy')
    require(job.get('status') == 'completed' and job.get('conclusion') == 'failure')
    require(job.get('head_sha') == target and isinstance(job.get('steps'), list))
    steps = job['steps']
    require(all(isinstance(step, dict) and type(step.get('number')) is int and step['number'] > 0 for step in steps))
    require(len({step['number'] for step in steps}) == len(steps))
    capture = _one(steps, 'Capture state preserved by deployment')
    quiesce, upload = _one(steps, QUIESCE), _one(steps, UPLOAD)
    for step, conclusion in ((capture, 'success'), (quiesce, 'failure'), (upload, 'success')):
        require(step.get('status') == 'completed' and step.get('conclusion') == conclusion)
        require(type(step.get('number')) is int and step['number'] > 0)
    require(capture['number'] < quiesce['number'] < upload['number'])
    for name in POST_QUIESCE:
        step = _one(steps, name)
        require(step.get('status') == 'completed' and step.get('conclusion') == 'skipped')
        require(type(step.get('number')) is int and step['number'] > upload['number'])
    # Source stamping/private-wheel preparation before quiescence is harmless;
    # it is deliberately not mistaken for App Service package deployment.


def _artifact(artifact, run_id, target):
    require(type(artifact.get('id')) is int and artifact['id'] > 0 and len(str(artifact['id'])) <= 20)
    require(artifact.get('name') == f'{ARTIFACT_PREFIX}-{run_id}-1')
    require(artifact.get('expired') is False)
    require(type(artifact.get('size_in_bytes')) is int and 0 < artifact['size_in_bytes'] <= MAX_ZIP)
    require(type(artifact.get('workflow_run', {}).get('id')) is int
            and artifact['workflow_run']['id'] == run_id)
    require(artifact.get('workflow_run', {}).get('head_sha') == target)
    require(isinstance(artifact.get('digest'), str)
            and re.fullmatch(r'sha256:[0-9a-f]{64}', artifact['digest']) is not None)
    return tuple(artifact[key] for key in ('id', 'name', 'expired', 'size_in_bytes', 'digest')) + (run_id, target)


def verify_proof(reader, encoded: str, *, producer_run: str, target: str, consumer_run: str) -> dict:
    run_id, consumer_id = positive_id(producer_run), positive_id(consumer_run)
    require(run_id != consumer_id)
    expected = expected_proof(target, run_id)
    require(isinstance(encoded, str) and 0 < len(encoded) <= MAX_ENCODED)
    raw = base64.b64decode(encoded, validate=True)
    require(0 < len(raw) <= MAX_ZIP and base64.b64encode(raw).decode('ascii') == encoded)
    _branch(reader.read('branches/main'), target)
    run_path = f'actions/runs/{run_id}'
    _run(reader.read(run_path), run_id, target)
    _jobs(reader.read(f'{run_path}/attempts/1/jobs?per_page=100'), target)
    artifacts = _collection(reader.read(f'{run_path}/artifacts?per_page=100'), 'artifacts')
    selected = _one(artifacts, f'{ARTIFACT_PREFIX}-{run_id}-1')
    _artifact(selected, run_id, target)
    artifact_path = f"actions/artifacts/{selected['id']}"
    artifact = reader.read(artifact_path)
    _artifact(artifact, run_id, target)
    require(_artifact(artifact, run_id, target) == _artifact(selected, run_id, target))
    # Authenticate the ORIGINAL archive bytes before inspecting its contents.
    require(artifact['digest'] == 'sha256:' + sha256(raw).hexdigest())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(archive.namelist() == [MEMBER])
        info = archive.infolist()[0]
        require(info.orig_filename == MEMBER and not info.is_dir())
        require(not info.flag_bits & 0x41 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
        require(stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG))
        require(0 < info.file_size <= MAX_PROOF and info.compress_size <= MAX_ZIP)
        proof = strict_json(archive.read(info))
    require(isinstance(proof, dict) and set(proof) == set(expected))
    require(all(type(proof[key]) is type(value) and proof[key] == value for key, value in expected.items()))
    # A rerun, expired/replaced artifact or changed main during admission denies.
    _run(reader.read(run_path), run_id, target)
    require(_artifact(reader.read(artifact_path), run_id, target) == _artifact(artifact, run_id, target))
    _branch(reader.read('branches/main'), target)
    return {'restore_positive': True, 'producer_run_id': run_id,
            'artifact_id': artifact['id'], 'artifact_digest': artifact['digest'], 'target_sha': target}


def main() -> int:
    try:
        if sys.argv[1:] == ['create']:
            create_proof(dict(os.environ))
        elif sys.argv[1:] == ['verify']:
            require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY)
            result = verify_proof(PublicMetadata(), os.environ.get('QUIESCENCE_PROOF_ZIP', ''),
                producer_run=os.environ.get('QUIESCENCE_PRODUCER_RUN', ''),
                target=os.environ.get('GITHUB_SHA', ''), consumer_run=os.environ.get('GITHUB_RUN_ID', ''))
            print(json.dumps(result, sort_keys=True))
        else:
            raise ValueError('Unsupported operation')
        return 0
    except Exception:
        print('Quiescence proof rejected; no credential fallback is available.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    def expired(_signum, _frame):
        raise TimeoutError('Proof deadline exceeded')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(55)
    raise SystemExit(main())
