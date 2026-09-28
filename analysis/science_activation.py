"""Exact implementation envelopes and deterministic activation projection.

Only trusted callers supply authenticated GitHub validation metadata. No helper
executes candidate code or interprets arbitrary paths as an approval exclusion.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from typing import Any, Callable, Mapping

from analysis.evidence_registry import (
    ApprovalMode, ArtifactRuntimeState, RecordStatus, ScienceRegistry,
)
from analysis.science_artifacts import (
    ImplementationBinding, ReviewRole, ReviewSubjectKind, build_policy_contract,
    digest_payload,
)

WORKFLOW_PATH = '.github/workflows/science-activation-validation.yml'
VALIDATION_JOB = 'Synthetic activation validation'
COLLECTOR_JOB = 'Collect immutable activation validation'
IMPLEMENTATION_STATEMENT = (
    'I approve activation of the named implementation contract at the displayed '
    'active contract digest, bound to the displayed reviewed code revision and '
    'exact diff digest, and validation evidence digest. This approval covers '
    'contract mapping, runtime changes and validation within the decision’s '
    'stated applicability and claim limits.'
)
MARKER = 'praxys-science-implementation:v1'
MARKER_RE = re.compile(r'<!--\s*praxys-science-implementation:v1\s*(\{.*?\})\s*-->', re.S)


def strict_json(text: str) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique)


def project_active_registry(registry: ScienceRegistry, subject_id: str) -> ScienceRegistry:
    """Project only lifecycle; scientific content must already be reviewed."""
    decision = registry.decisions[subject_id]
    if decision.approval_mode != ApprovalMode.ARTIFACT or decision.artifact_policy is None:
        raise ValueError('Activation requires artifact-mode science')
    if decision.version != 1 or decision.supersedes:
        raise ValueError('Successor activation requires an explicit coordinated lifecycle patch')
    if decision.status not in {RecordStatus.DRAFT, RecordStatus.ACCEPTED}:
        raise ValueError('Activation cannot revive a superseded decision')
    decisions = dict(registry.decisions)
    decisions[subject_id] = decision.model_copy(update={
        'status': RecordStatus.ACCEPTED,
        'artifact_policy': decision.artifact_policy.model_copy(update={
            'runtime_state': ArtifactRuntimeState.ACTIVE,
        }),
    })
    reviews = dict(registry.evidence_reviews)
    for review_id in decision.evidence_review_ids:
        review = reviews[review_id]
        if review.status == RecordStatus.DRAFT:
            if review.approval_mode != ApprovalMode.ARTIFACT or review.version != 1 or review.supersedes:
                raise ValueError('Activation cannot infer evidence successor acceptance')
            reviews[review_id] = review.model_copy(update={'status': RecordStatus.ACCEPTED})
    return replace(registry, decisions=decisions, evidence_reviews=reviews)


def implementation_payload(body: str) -> dict[str, Any] | None:
    matches = list(MARKER_RE.finditer(body))
    if MARKER not in body:
        return None
    if len(matches) != 1:
        raise ValueError('Implementation approval must contain exactly one valid marker')
    raw = strict_json(matches[0].group(1))
    required = {'subject_kind', 'subject_id', 'subject_digest', 'role', 'implementation_binding'}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError('Implementation approval marker fields are invalid')
    if raw['subject_kind'] != ReviewSubjectKind.IMPLEMENTATION_CONTRACT.value or raw['role'] != ReviewRole.IMPLEMENTATION_REVIEWER.value:
        raise ValueError('Implementation marker requires implementation role and subject')
    binding = ImplementationBinding.model_validate(raw['implementation_binding'])
    if raw['subject_digest'] != binding.active_contract_digest:
        raise ValueError('Implementation subject and envelope contract differ')
    if body.strip() != render_implementation_comment(raw['subject_id'], binding).strip():
        raise ValueError('Implementation comment must match the exact canonical statement')
    return raw


def render_implementation_comment(subject_id: str, binding: ImplementationBinding) -> str:
    raw = {
        'subject_kind': ReviewSubjectKind.IMPLEMENTATION_CONTRACT.value,
        'subject_id': subject_id,
        'subject_digest': binding.active_contract_digest,
        'role': ReviewRole.IMPLEMENTATION_REVIEWER.value,
        'implementation_binding': binding.model_dump(mode='json'),
    }
    lines = ['Praxys science approval — **APPROVE**', '',
             '- Role: `implementation_reviewer`', f'- Subject: `{subject_id}`',
             f'- Active contract: `{binding.active_contract_digest}`',
             f'- Envelope digest: `{binding.envelope_digest}`']
    lines += [f'- {key}: `{value}`' for key, value in binding.model_dump(mode='json').items()]
    lines += ['', f'> {IMPLEMENTATION_STATEMENT}', '', f'<!-- {MARKER}',
              json.dumps(raw, ensure_ascii=False, separators=(',', ':'), sort_keys=True), '-->']
    return '\n'.join(lines)


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout


def diff_digest(root: Path, base: str, head: str) -> str:
    patch = git(root, '-c', 'core.quotePath=true', 'diff', '--no-ext-diff', '--no-textconv',
                '--binary', '--full-index', '--no-renames', base, head, '--')
    return 'sha256:' + sha256(patch).hexdigest()


def git_tree(root: Path, revision: str) -> dict[str, tuple[str, str]]:
    entries = {}
    for record in git(root, 'ls-tree', '-rz', revision).split(b'\0'):
        if not record:
            continue
        metadata, path = record.split(b'\t', 1)
        mode, _, oid = metadata.decode().split()
        entries[path.decode()] = (mode, oid)
    return entries


def directory_tree(root: Path, template: Mapping[str, tuple[str, str]], *, repository: Path) -> dict[str, tuple[str, str]]:
    paths = set(template)
    # Science ledger files can be newly generated by deterministic replay.
    paths.update(str(p.relative_to(root)) for p in (root / 'data/science').rglob('*') if p.is_file() or p.is_symlink())
    if (root / '.git').exists():
        paths.update(p.decode() for p in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p)
        paths.update(p.decode() for p in git(root, 'ls-files', '-z').split(b'\0') if p)
    result = {}
    for path in sorted(paths):
        candidate = root / path
        original_mode, original_oid = template.get(path, ('100644', ''))
        if original_mode == '160000':
            # Gitlinks bind their immutable object ID, never submodule contents.
            if (root / '.git').exists():
                tracked = git(root, 'ls-files', '-s', '--', path).decode().split()
                if tracked:
                    result[path] = (tracked[0], tracked[1])
            else:
                result[path] = (original_mode, original_oid)
            continue
        if candidate.is_symlink():
            content = str(candidate.readlink()).encode()
            mode = '120000'
        elif candidate.is_file():
            content = candidate.read_bytes()
            mode = '100755' if candidate.stat().st_mode & 0o111 else '100644'
        else:
            continue
        oid = subprocess.run(['git', '-C', str(repository), 'hash-object', '--stdin'], input=content,
                             check=True, capture_output=True).stdout.decode().strip()
        result[path] = (mode, oid)
    return result


@dataclass(frozen=True)
class ActivationContext:
    repository_root: Path
    repository: str
    pull_request: int
    base_sha: str
    head_sha: str
    # Only the trusted GitHub collector/verifier may populate this mapping.
    validations: Mapping[str, Mapping[str, Any]]
    recheck: Callable[[], None] | None = None

    def verify(self, binding: ImplementationBinding, registry: ScienceRegistry, subject_id: str) -> ScienceRegistry:
        if (binding.repository, binding.pull_request, binding.base_sha) != (self.repository, self.pull_request, self.base_sha):
            raise ValueError('Implementation approval repository/PR/base mismatch')
        git(self.repository_root, 'merge-base', '--is-ancestor', binding.base_sha, binding.reviewed_head_sha)
        git(self.repository_root, 'merge-base', '--is-ancestor', binding.reviewed_head_sha, self.head_sha)
        if diff_digest(self.repository_root, binding.base_sha, binding.reviewed_head_sha) != binding.diff_digest:
            raise ValueError('Implementation code diff digest mismatch')
        projected = project_active_registry(registry, subject_id)
        if build_policy_contract(projected, subject_id).contract_digest != binding.active_contract_digest:
            raise ValueError('Implementation active contract digest mismatch')
        validation = self.validations.get(binding.envelope_digest)
        if validation is None or digest_payload(validation) != binding.validation_digest:
            raise ValueError('Missing or stale authenticated implementation validation')
        expected = {
            'schema_version': 1, 'repository': binding.repository, 'pull_request': binding.pull_request,
            'base_sha': binding.base_sha, 'reviewed_head_sha': binding.reviewed_head_sha,
            'diff_digest': binding.diff_digest, 'active_contract_digest': binding.active_contract_digest,
            'subject_id': subject_id, 'workflow_path': WORKFLOW_PATH,
            'workflow_sha': binding.validation_workflow_sha, 'run_id': binding.validation_run_id,
            'run_attempt': binding.validation_run_attempt, 'conclusion': 'success',
            'required_jobs': [VALIDATION_JOB],
        }
        if dict(validation) != expected:
            raise ValueError('Implementation validation producer, revision or outcome mismatch')
        return projected

    def require_reviewed_tree(self, binding: ImplementationBinding, root: Path) -> None:
        expected = git_tree(self.repository_root, binding.reviewed_head_sha)
        if directory_tree(root, expected, repository=self.repository_root) != expected:
            raise ValueError('Activation input differs from the exact reviewed preapproval tree')

    def verify_replay(self, binding: ImplementationBinding, approvals, candidate_root: Path) -> None:
        from analysis.science_approval_workflow import materialize_science_approvals
        template = git_tree(self.repository_root, binding.reviewed_head_sha)
        with tempfile.TemporaryDirectory(prefix='praxys-activation-replay-') as temp:
            replay_root = Path(temp)
            archive = git(self.repository_root, 'archive', binding.reviewed_head_sha)
            with tarfile.open(fileobj=io.BytesIO(archive)) as source:
                source.extractall(replay_root, filter='data')
            materialize_science_approvals(replay_root / 'data/science', approvals, activation_context=self)
            expected = directory_tree(replay_root, template, repository=self.repository_root)
        actual = directory_tree(candidate_root, template, repository=self.repository_root)
        if actual != expected:
            changed = sorted(path for path in set(actual) | set(expected) if actual.get(path) != expected.get(path))
            raise ValueError(f'Candidate differs from exact activation replay: {changed}')


def verify_governed_maintenance(base_registry, head_registry) -> None:
    """Keep existing activation fixed on trusted, explicitly enumerated files.

    Renewal is deliberately unsupported. The trusted base manifest is not read
    from candidate data, so a PR cannot remove its own review coverage.
    """
    from analysis.science_artifacts import load_science_approvals
    policy_path = Path(__file__).resolve().parents[1] / 'config/science-implementation-coverage.json'
    policy = strict_json(policy_path.read_text())
    if policy.get('schema_version') != 1:
        raise ValueError('Unsupported implementation coverage manifest')
    base_root = base_registry.science_dir.resolve().parent.parent
    head_root = head_registry.science_dir.resolve().parent.parent
    base_approvals = load_science_approvals(base_registry.science_dir)
    for subject_id, decision in base_registry.decisions.items():
        if decision.artifact_policy is None or decision.artifact_policy.runtime_state != ArtifactRuntimeState.ACTIVE:
            continue
        paths = policy['contracts'].get(subject_id)
        if not paths:
            raise ValueError('Active contract has no trusted implementation coverage')
        if not any(a.subject_id == subject_id and a.role == ReviewRole.IMPLEMENTATION_REVIEWER for a in base_approvals):
            raise ValueError('Active contract has no implementation binding')
        def content(root, path):
            target = root / path
            if target.is_symlink():
                return ('symlink', str(target.readlink()))
            if not target.exists():
                return None
            return (target.stat().st_mode & 0o111, target.read_bytes())
        changed = [path for path in paths if content(base_root, path) != content(head_root, path)]
        if changed:
            raise ValueError(f'Active implementation governed files changed; separately reviewed renewal is required: {changed}')
