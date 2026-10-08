"""Designated DFA V2 content checks, separate from authenticated admission.

No fields are added to historical record/approval models. Runtime consistency
uses shipped data only; privileged callers separately bind the real Git base.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, model_validator

BASELINE = 'sdr-activity-dfa-alpha1-v1'
DESIGNATED = 'sdr-activity-dfa-alpha1-v2'
EVIDENCE = 'evidence-activity-dfa-alpha1-v1'
BASELINE_DECISION = 'sha256:3c43b0c3b3eae94bc07a40c27e159110d8ce815206d248e3aaef7ef6e9077288'
BASELINE_CONTRACT = 'sha256:0029c8753ba7c3a695ec7549ef41f39886280642d2fd70e7973b5022dba751d6'
BASELINE_ENVELOPE = 'sha256:facc27c7a4b51d2901b3fdfe55f2cb0c193f6a1aad12767abaf1d57aa74d2f2b'
EVIDENCE_DIGEST = 'sha256:dcb55292c89c9721fbf4d7133f94e34487e5de50efd4ffc94b36a5a7eff9a73f'
BASELINE_STOP = 'sha256:05c11e11adf6cec91d8a60d126364a6260287317c8872e43a365c0665790c944'
FROZEN_DIGEST = 'sha256:f36cf405cbf84aef9d04e6e52aa1600662ce0254de1b230d7372ff035ebede11'
FROZEN_GROUPS = ('window', 'rr_quality', 'time_alignment', 'dfa', 'context')
METHOD = 'dfa-alpha1-raw120-v1'
MANUAL_STATEMENT = 'dfa-source-attestation-v1'
MODALITIES = ['native_RR', 'recorded_ECG', 'single_native_running_session']
AMENDMENT_PARAMETER = 'admission_amendment'


class AdmissionAmendment(BaseModel):
    """Required exact pins; no defaults, coercion, extra keys or authority flag."""

    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: StrictInt
    kind: Literal['designated_activity_dfa_v2']
    baseline_subject: Literal['sdr-activity-dfa-alpha1-v1']
    baseline_version: StrictInt
    baseline_decision_digest: Literal[BASELINE_DECISION]
    baseline_contract_digest: Literal[BASELINE_CONTRACT]
    baseline_implementation_envelope: Literal[BASELINE_ENVELOPE]
    evidence_subject: Literal['evidence-activity-dfa-alpha1-v1']
    evidence_digest: Literal[EVIDENCE_DIGEST]
    baseline_stop_digest: Literal[BASELINE_STOP]
    frozen_group_value_digest: Literal[FROZEN_DIGEST]
    model_version: Literal[METHOD]
    manual_statement_revision: Literal[MANUAL_STATEMENT]
    modalities: list[StrictStr]

    @model_validator(mode='after')
    def exact_versions_and_modalities(self) -> 'AdmissionAmendment':
        if self.schema_version != 1 or self.baseline_version != 1 or self.modalities != MODALITIES:
            raise ValueError('Unsupported amendment version or modalities')
        return self


def prevalidate_amendment_record(raw: dict[str, Any]) -> None:
    """Check the reserved identity/value before the general record coercions."""
    identity = raw.get('id')
    parameters = raw.get('model_parameters', [])
    relevant = [p for p in parameters if isinstance(p, dict)
                and isinstance(p.get('name'), str)
                and p['name'].strip() == AMENDMENT_PARAMETER] if isinstance(parameters, list) else []
    reserved = isinstance(identity, str) and identity.strip() == DESIGNATED
    if not reserved and not relevant:
        return
    if (identity != DESIGNATED or type(raw.get('schema_version')) is not int
            or raw['schema_version'] != 1 or type(raw.get('version')) is not int
            or raw['version'] != 2 or raw.get('approval_mode') != 'artifact'
            or type(raw.get('supersedes')) is not list or raw['supersedes']
            or 'superseded_by' not in raw or raw['superseded_by'] is not None):
        raise ValueError('Only exact designated integer-V2 artifact amendment without supersession is supported')
    if len(relevant) != 1 or relevant[0]['name'] != AMENDMENT_PARAMETER:
        raise ValueError('Designated amendment requires exactly one canonical named parameter')
    AdmissionAmendment.model_validate(relevant[0].get('value'))


def amendment_value(decision: Any) -> AdmissionAmendment:
    """Read the existing parameter value without changing model serialization."""
    if (decision.id != DESIGNATED or type(decision.version) is not int or decision.version != 2
            or decision.approval_mode.value != 'artifact' or decision.supersedes
            or decision.superseded_by is not None):
        raise ValueError('Unsupported designated amendment identity or lifecycle')
    values = [p.value for p in decision.model_parameters if p.name == AMENDMENT_PARAMETER]
    if len(values) != 1:
        raise ValueError('Designated amendment requires one parameter value')
    return AdmissionAmendment.model_validate(values[0])


def validate_local_amendment(registry: Any, *, require_unstopped: bool = False) -> AdmissionAmendment:
    """Verify immutable shipped content; this never authenticates a GitHub base."""
    from analysis.science_artifacts import (
        ReviewRole, build_policy_contract, digest_payload, evidence_review_digest,
        load_science_approvals, science_decision_digest,
    )
    from analysis.science_implementation_stop import load_implementation_stops, validate_stop_target

    decision = registry.decisions[DESIGNATED]
    amendment = amendment_value(decision)
    baseline = registry.decisions.get(BASELINE)
    evidence = registry.evidence_reviews.get(EVIDENCE)
    if (baseline is None or evidence is None or baseline.status.value != 'accepted'
            or baseline.artifact_policy is None or baseline.artifact_policy.runtime_state.value != 'active'
            or science_decision_digest(baseline) != BASELINE_DECISION
            or evidence.status.value != 'accepted' or evidence_review_digest(evidence) != EVIDENCE_DIGEST):
        raise ValueError('Designated amendment baseline/evidence content or lifecycle mismatch')
    contract = build_policy_contract(registry, BASELINE)
    parameters = {p.name: p.value for p in decision.model_parameters}
    frozen = {name: parameters.get(name) for name in FROZEN_GROUPS}
    if (contract.contract_digest != BASELINE_CONTRACT or digest_payload(frozen) != FROZEN_DIGEST
            or decision.model_version != METHOD or baseline.model_version != METHOD
            or not isinstance(parameters.get('source'), dict)
            or parameters['source'].get('statement_version') != MANUAL_STATEMENT
            or decision.evidence_review_ids != [EVIDENCE]
            or decision.evidence_claim_ids != baseline.evidence_claim_ids
            or decision.affected_surfaces.models != baseline.affected_surfaces.models
            or contract.parameter_values['source']['statement_version'] != MANUAL_STATEMENT):
        raise ValueError('Designated amendment contract/method/numeric/evidence/model pins mismatch')
    if (contract.parameter_values['source']['required']
            != 'native_RR_and_recorded_ECG_and_activity_confirmation'
            or contract.parameter_values['activation']['source_scope']
            != 'single_native_running_session_exact_owner_recording'):
        raise ValueError('Baseline modalities or manual statement scope mismatch')
    approvals = load_science_approvals(registry.science_dir)
    matching = [a for a in approvals if a.subject_id == BASELINE
                and a.role == ReviewRole.IMPLEMENTATION_REVIEWER and a.implementation_binding is not None
                and a.implementation_binding.envelope_digest == BASELINE_ENVELOPE]
    if len(matching) != 1 or not any(a.subject_id == EVIDENCE and a.role == ReviewRole.EVIDENCE_REVIEWER
                                   and a.subject_digest == EVIDENCE_DIGEST for a in approvals):
        raise ValueError('Historical implementation or shared evidence approval is missing')
    stops = load_implementation_stops(registry.science_dir)
    historical = [s for s in stops if s.subject_id == BASELINE]
    if len(historical) != 1 or historical[0].stop_digest != BASELINE_STOP:
        raise ValueError('Actual pinned historical STOP is missing or differs')
    validate_stop_target(registry, historical[0])
    if require_unstopped and any(s.subject_id == DESIGNATED for s in stops):
        raise ValueError('Designated V2 is terminally stopped')
    return amendment


def validate_designated_registry(registry: Any) -> None:
    """Cross-validate designated data while keeping ordinary registries unchanged."""
    if DESIGNATED in registry.decisions:
        validate_local_amendment(registry)


def designated_relative_path(relative: Path) -> bool:
    """Identify only the designated record/artifact/approval/STOP closure."""
    parts = relative.parts
    if not parts:
        return False
    if parts[0] == 'approvals':
        return relative.name.startswith(DESIGNATED + '--') or relative.name.startswith('synthetic-' + DESIGNATED + '-')
    return relative.name in {DESIGNATED + '.yaml', DESIGNATED + '.md', DESIGNATED + '.json'}


def require_authenticated_amendment_base(registry: Any, context: Any) -> None:
    """Bind shipped consistency to a privileged authenticated exact PR/Git base.

    The context is supplied only by existing trusted readers. A candidate data
    flag, local STOP or synthetic projection cannot replace this check.
    """
    from analysis.science_activation import ActivationContext, git, git_tree
    from analysis.science_stop_github import StopContext

    from analysis.science_approval_workflow import _reject_symlinks
    _reject_symlinks(registry.science_dir)
    validate_local_amendment(registry, require_unstopped=True)
    if not isinstance(context, (ActivationContext, StopContext)):
        raise ValueError('Designated amendment requires authenticated exact-base context')
    root = Path(context.repository_root).resolve()
    if (context.repository != 'praxys-run/praxys'
            or git(root, 'rev-parse', 'HEAD').decode().strip() != context.head_sha):
        raise ValueError('Designated amendment authenticated source/head mismatch')
    expected = git_tree(root, context.base_sha)
    required_stop = 'data/science/stops/' + BASELINE + '.yaml'
    if required_stop not in expected:
        raise ValueError('Candidate STOP cannot supply amendment trusted-base admission')
    from analysis.evidence_registry import render_registry_index
    index = registry.science_dir / 'REGISTRY.md'
    if (not index.is_file() or index.is_symlink()
            or index.read_bytes() != render_registry_index(registry).encode('utf-8')
            or ('100755' if index.stat().st_mode & 0o111 else '100644') != expected.get('data/science/REGISTRY.md', ('100644', ''))[0]):
        raise ValueError('Designated admission requires exact derived registry index')
    if isinstance(context, ActivationContext):
        from analysis.science_activation import V2_PURPOSE, WORKFLOW_PATH, VALIDATION_JOB, PROBE_JOB, diff_digest, same_typed_value
        required = dict(schema_version=2, purpose=V2_PURPOSE, repository=context.repository,
                        pull_request=context.pull_request, base_sha=context.base_sha,
                        subject_id=DESIGNATED, baseline_guard_result='denied',
                        admission_amendment=amendment_value(registry.decisions[DESIGNATED]).model_dump(mode='json'),
                        workflow_path=WORKFLOW_PATH, conclusion='success', required_jobs=[VALIDATION_JOB, PROBE_JOB])
        allowed = set(required) | {'reviewed_head_sha', 'diff_digest', 'active_contract_digest', 'workflow_sha', 'run_id', 'run_attempt'}
        matching = [v for v in context.validations.values() if set(v) == allowed
                    and all(same_typed_value(v.get(k), value) for k, value in required.items())
                    and all(type(v.get(k)) is int and v[k] > 0 for k in ('run_id', 'run_attempt'))]
        if len(matching) != 1:
            raise ValueError('Designated admission requires authenticated exact V2 proof and separate actual V1 denial')
        proof = matching[0]
        git(root, 'merge-base', '--is-ancestor', context.base_sha, proof['reviewed_head_sha'])
        git(root, 'merge-base', '--is-ancestor', proof['reviewed_head_sha'], context.head_sha)
        git(root, 'merge-base', '--is-ancestor', proof['workflow_sha'], context.base_sha)
        if proof['diff_digest'] != diff_digest(root, context.base_sha, proof['reviewed_head_sha']):
            raise ValueError('Designated authenticated proof full diff mismatch')
    # Preserve every prior scientific byte/mode except the designated closure
    # and its separately validated derived registry index.
    for name, (mode, oid) in expected.items():
        if not name.startswith('data/science/'):
            continue
        relative = Path(name).relative_to('data/science')
        if relative == Path('REGISTRY.md') or designated_relative_path(relative):
            continue
        path = registry.science_dir / relative
        if (not path.is_file() or path.is_symlink()
                or path.read_bytes() != git(root, 'cat-file', 'blob', oid)
                or ('100755' if path.stat().st_mode & 0o111 else '100644') != mode):
            raise ValueError('Historical science/evidence/approval/STOP bytes or modes changed')
    for path in registry.science_dir.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(registry.science_dir)
        if 'data/science/' + relative.as_posix() not in expected and not designated_relative_path(relative):
            raise ValueError('Designated admission may add only its own science closure')
    if isinstance(context, StopContext):
        from analysis.science_implementation_stop import load_implementation_stops
        stop = next(s for s in load_implementation_stops(registry.science_dir) if s.subject_id == BASELINE)
        context.require_denial(stop)


def prune_designated_fixture_closure(science: Path) -> None:
    """Prune a disposable historical V1 closure before any registry load."""
    from analysis.science_yaml import load_science_yaml
    for path in science.rglob('*'):
        if not path.is_file():
            continue
        designated = designated_relative_path(path.relative_to(science))
        if path.suffix in {'.yaml', '.yml'}:
            raw = load_science_yaml(path.read_text())
            designated |= isinstance(raw, dict) and (raw.get('id') == DESIGNATED or raw.get('subject_id') == DESIGNATED)
        if designated:
            path.unlink()
