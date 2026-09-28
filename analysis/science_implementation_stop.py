"""Append-only, authenticated terminal stops for implementation subjects.

Recording a stop is distinct from deploying it. Later maintenance is checked
against the trusted base stop and authenticated isolated guard-denial evidence.
No candidate code is executed by this module or by the privileged verifier.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import tempfile
from typing import Any, Literal

from pydantic import AnyHttpUrl, Field, model_validator
import yaml

from analysis.evidence_registry import ArtifactRuntimeState, Identity, RecordId, RegistryModel
from analysis.science_artifacts import Digest, ReviewRole, build_policy_contract, digest_payload, load_science_approvals
from analysis.science_yaml import load_science_yaml

STOP_MARKER = 'praxys-science-stop:v1'
STOP_RE = re.compile(r'<!--\s*praxys-science-stop:v1\s*(\{.*?\})\s*-->', re.S)
STOP_STATEMENT = (
    'I explicitly stop the named implementation subject at the displayed active '
    'contract and implementation envelope digests. This is a terminal stop for '
    'this subject, preserves its scientific and approval history, and does not '
    'authorize replacement activation or code changes in the stop commit. '
    'The recorded stop takes operational effect only after the stopped release '
    'is deployed and observed.'
)


class ImplementationStop(RegistryModel):
    schema_version: Literal[1]
    action: Literal['stop']
    repository: str = Field(pattern=r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
    subject_id: RecordId
    active_contract_digest: Digest
    implementation_envelope_digest: Digest
    requested_by: Identity
    requested_at: datetime
    source_ref: AnyHttpUrl

    @model_validator(mode='after')
    def identified_source(self):
        if (not self.requested_by.startswith('github:')
                or self.requested_by.endswith('[bot]')
                or self.requested_at.tzinfo is None):
            raise ValueError('Implementation stop requires an identified human and timezone-aware source time')
        if not re.fullmatch(r'https://github\.com/' + re.escape(self.repository)
                            + r'/(?:pull|issues)/[1-9][0-9]*#issuecomment-[1-9][0-9]*', str(self.source_ref)):
            raise ValueError('Implementation stop source must be a comment in its exact repository')
        return self

    @property
    def stop_digest(self) -> str:
        return digest_payload(self.model_dump(mode='json'))

    @property
    def target(self) -> dict[str, Any]:
        return self.model_dump(mode='json', include={
            'schema_version', 'action', 'repository', 'subject_id',
            'active_contract_digest', 'implementation_envelope_digest',
        })


def render_stop_comment(target: dict[str, Any]) -> str:
    required = {'schema_version', 'action', 'repository', 'subject_id',
                'active_contract_digest', 'implementation_envelope_digest'}
    if set(target) != required or target['schema_version'] != 1 or target['action'] != 'stop':
        raise ValueError('Stop target must contain exactly the canonical stop fields')
    lines = ['Praxys implementation — **STOP**', '']
    lines += [f'- {key}: `{target[key]}`' for key in sorted(required)]
    lines += ['', f'> {STOP_STATEMENT}', '', f'<!-- {STOP_MARKER}',
              json.dumps(target, ensure_ascii=False, separators=(',', ':'), sort_keys=True), '-->']
    return '\n'.join(lines)


def stop_from_comment(comment, permission: str, repository: str) -> ImplementationStop:
    from analysis.science_activation import strict_json
    user = comment.get('user', {})
    login = user.get('login')
    if (user.get('type') != 'User' or not isinstance(login, str) or login.endswith('[bot]')
            or permission not in {'write', 'maintain', 'admin'}):
        raise ValueError('STOP requires current authorized human repository permission')
    body = str(comment.get('body', ''))
    matches = list(STOP_RE.finditer(body))
    if len(matches) != 1:
        raise ValueError('STOP requires exactly one explicit canonical source statement')
    target = strict_json(matches[0].group(1))
    if not isinstance(target, dict) or target.get('repository') != repository:
        raise ValueError('STOP repository mismatch')
    if body.strip() != render_stop_comment(target).strip():
        raise ValueError('STOP source does not match the complete canonical statement')
    return ImplementationStop.model_validate({**target, 'requested_by':'github:'+login,
        'requested_at':comment['created_at'], 'source_ref':comment['html_url']})


def stop_paths(subject_id: str) -> tuple[Path, Path]:
    return Path('stops') / f'{subject_id}.yaml', Path('generated/implementation-stops') / f'{subject_id}.md'


def render_stop_audit(stop: ImplementationStop) -> str:
    return '\n'.join([
        f'# Terminal implementation stop: {stop.subject_id}', '',
        f'- Stop digest: `{stop.stop_digest}`',
        f'- Contract digest: `{stop.active_contract_digest}`',
        f'- Implementation envelope: `{stop.implementation_envelope_digest}`',
        f'- Requested by: `{stop.requested_by}`',
        f'- Requested at: `{stop.requested_at.isoformat()}`',
        f'- Authenticated source: {stop.source_ref}', '',
        'This append-only record stops this subject. Its scientific records and approvals remain historical evidence.',
        'Source recording is not proof of deployment, worker drainage or global cessation.',
        'Never redeploy an older active release for this stopped subject.', '',
    ])


def load_implementation_stops(science_dir: Path) -> list[ImplementationStop]:
    directory = Path(science_dir) / 'stops'
    if directory.is_symlink():
        raise ValueError('Implementation stop directory cannot be a symlink')
    if not directory.exists():
        return []
    stops = []
    seen = set()
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Implementation stop cannot be a symlink')
        if not path.is_file():
            continue
        stop = ImplementationStop.model_validate(load_science_yaml(path.read_text()))
        if path != Path(science_dir) / stop_paths(stop.subject_id)[0] or stop.subject_id in seen:
            raise ValueError('Implementation stop path or duplicate subject is invalid')
        seen.add(stop.subject_id)
        stops.append(stop)
    return stops


def validate_stop_target(registry, stop: ImplementationStop) -> None:
    decision = registry.decisions.get(stop.subject_id)
    if (decision is None or decision.artifact_policy is None
            or decision.artifact_policy.runtime_state != ArtifactRuntimeState.ACTIVE):
        raise ValueError('STOP target must be the existing accepted active implementation')
    if build_policy_contract(registry, stop.subject_id).contract_digest != stop.active_contract_digest:
        raise ValueError('STOP target contract digest mismatch')
    matches = [approval for approval in load_science_approvals(registry.science_dir)
               if approval.subject_id == stop.subject_id and approval.role == ReviewRole.IMPLEMENTATION_REVIEWER
               and approval.implementation_binding is not None
               and approval.implementation_binding.envelope_digest == stop.implementation_envelope_digest
               and approval.implementation_binding.repository == stop.repository]
    if len(matches) != 1 or stop.requested_at.date() < matches[0].reviewed_on:
        raise ValueError('STOP target implementation envelope is not the trusted approved binding')
    source_pull = int(re.search(r'/(?:pull|issues)/([1-9][0-9]*)#', str(stop.source_ref)).group(1))
    if source_pull != matches[0].implementation_binding.pull_request:
        raise ValueError('STOP source must be on the original bound activation pull request')


def validate_registry_stops(registry) -> None:
    for stop in load_implementation_stops(registry.science_dir):
        validate_stop_target(registry, stop)


def require_not_stopped(registry, subject_id: str) -> None:
    # Terminal by subject, not by reviewer, filename or a replacement envelope.
    stops = load_implementation_stops(registry.science_dir)
    for stop in stops:
        validate_stop_target(registry, stop)
    if any(stop.subject_id == subject_id for stop in stops):
        raise ValueError('Implementation subject is terminally stopped')


def expected_stop_artifacts(registry) -> dict[Path, str]:
    return {stop_paths(stop.subject_id)[1]: render_stop_audit(stop)
            for stop in load_implementation_stops(registry.science_dir)}


def write_stop_files(science_dir: Path, stop: ImplementationStop) -> None:
    record, audit = stop_paths(stop.subject_id)
    for path, content in [(record, yaml.safe_dump(stop.model_dump(mode='json'), sort_keys=False)),
                          (audit, render_stop_audit(stop))]:
        destination = science_dir / path
        if destination.exists() and destination.read_text() != content:
            raise ValueError('Implementation STOP history cannot be overwritten')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding='utf-8', newline='\n')


def verify_stop_changes(base_registry, head_registry, *, repository_root: Path,
                        base_sha: str, authenticated: list[ImplementationStop]) -> list[ImplementationStop]:
    from analysis.science_activation import directory_tree, git_tree
    base_stops = load_implementation_stops(base_registry.science_dir)
    head_stops = load_implementation_stops(head_registry.science_dir)
    for old in base_stops:
        if old not in head_stops:
            raise ValueError('Implementation STOP history was removed or changed')
        for path in stop_paths(old.subject_id):
            if ((base_registry.science_dir / path).read_bytes() != (head_registry.science_dir / path).read_bytes()
                    or (base_registry.science_dir / path).stat().st_mode & 0o111 != (head_registry.science_dir / path).stat().st_mode & 0o111):
                raise ValueError('Implementation STOP history must remain byte-preserved')
    # Historical scientific source and approval bytes remain immutable after stop.
    for old in base_stops:
        decision = base_registry.decisions[old.subject_id]
        subjects = {old.subject_id, *decision.evidence_review_ids}
        historical = {base_registry.decision_paths[old.subject_id].relative_to(base_registry.science_dir),
                      Path('generated/contracts') / f'{old.subject_id}.json'}
        historical.update(base_registry.review_paths[identity].relative_to(base_registry.science_dir)
                          for identity in decision.evidence_review_ids)
        historical.update(Path('generated/review-packets') / f'{identity}.md' for identity in subjects
                          if (base_registry.science_dir / 'generated/review-packets' / f'{identity}.md').exists())
        for path in (base_registry.science_dir / 'approvals').glob('*.yaml'):
            raw = load_science_yaml(path.read_text())
            if raw.get('subject_id') in subjects:
                historical.add(path.relative_to(base_registry.science_dir))
        for path in historical:
            candidate = head_registry.science_dir / path
            if (not candidate.is_file() or (base_registry.science_dir / path).read_bytes() != candidate.read_bytes()
                    or (base_registry.science_dir / path).stat().st_mode & 0o111 != candidate.stat().st_mode & 0o111):
                raise ValueError('Stopped subject science and approval history must remain byte-preserved')
    added = [stop for stop in head_stops if stop not in base_stops]
    if not added:
        return []
    if len(added) != 1 or added[0] not in authenticated:
        raise ValueError('New STOP requires one authenticated exact source')
    stop = added[0]
    validate_stop_target(base_registry, stop)
    # Only these two new files may differ from the trusted base. Every old
    # science artifact, source file, mode and Gitlink remains identical.
    expected = git_tree(repository_root, base_sha)
    actual = directory_tree(head_registry.science_dir.parent.parent, expected, repository=repository_root)
    allowed = {str(Path('data/science') / path) for path in stop_paths(stop.subject_id)}
    changed = {path for path in set(expected) | set(actual) if expected.get(path) != actual.get(path)}
    if changed != allowed:
        raise ValueError(f'STOP commit must contain only its append-only record and audit: {sorted(changed)}')
    record, audit = stop_paths(stop.subject_id)
    if (head_registry.science_dir / record).read_text() != yaml.safe_dump(stop.model_dump(mode='json'), sort_keys=False):
        raise ValueError('STOP record is not the exact deterministic materialization')
    if any((head_registry.science_dir / path).stat().st_mode & 0o111 for path in (record, audit)):
        raise ValueError('STOP record and audit must be non-executable')
    if (head_registry.science_dir / audit).read_text() != render_stop_audit(stop):
        raise ValueError('STOP audit is not the exact trusted projection')
    return added


def materialize_stop(repository_root: Path, stop: ImplementationStop, *, recheck=None) -> list[Path]:
    from analysis.evidence_registry import load_science_registry
    from analysis.science_activation import directory_tree, git, git_tree
    from analysis.science_approval_workflow import _atomic_copy, _reject_symlinks, _verify_generated_state
    root = repository_root.resolve()
    science = root / 'data/science'
    _reject_symlinks(science)
    registry = load_science_registry(science)
    validate_stop_target(registry, stop)
    existing = load_implementation_stops(science)
    if stop in existing:
        _verify_generated_state(science)
        return []
    if existing and any(item.subject_id == stop.subject_id for item in existing):
        raise ValueError('Implementation subject already has an immutable terminal stop')
    revision = git(root, 'rev-parse', 'HEAD').decode().strip()
    template = git_tree(root, revision)
    if directory_tree(root, template, repository=root) != template:
        raise ValueError('STOP materialization requires an unchanged trusted-base checkout')
    _verify_generated_state(science)
    with tempfile.TemporaryDirectory(prefix='praxys-stop-') as temporary:
        staged = Path(temporary) / 'science'
        shutil.copytree(science, staged)
        write_stop_files(staged, stop)
        _verify_generated_state(staged)
        if recheck is not None:
            recheck()
        if (git(root, 'rev-parse', 'HEAD').decode().strip() != revision
                or directory_tree(root, template, repository=root) != template):
            raise ValueError('STOP checkout changed before publication')
        written = []
        try:
            for path in stop_paths(stop.subject_id):
                written.append(path)
                _atomic_copy(staged / path, science / path)
        except Exception:
            for path in written:
                (science / path).unlink(missing_ok=True)
            raise
    return list(stop_paths(stop.subject_id))
