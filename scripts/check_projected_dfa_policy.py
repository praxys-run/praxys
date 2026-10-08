"""Synthetic-only projected activation check; never produces real approvals.

Prepares candidate data with trusted code, never importing candidate modules.
The CLI delegates candidate execution and completion to the bounded controller.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import tempfile

@contextmanager
def synthetic_active_registry(candidate: Path, subject: str, expected: str | None, *, fresh_hypothetical=False):
    """Yield a disposable, schema-valid synthetic registry for real guard tests."""
    from analysis import science_artifacts as artifacts
    from analysis.evidence_registry import load_science_registry, render_registry_index
    from analysis.science_activation import project_active_registry
    import yaml

    if subject != 'sdr-activity-dfa-alpha1-v1':
        raise ValueError('This bounded producer validates descriptive activity DFA only')
    reviewed_on = datetime.now(timezone.utc).date()
    with tempfile.TemporaryDirectory(prefix='synthetic-dfa-policy-') as temporary:
        root = Path(temporary) / 'science'
        shutil.copytree(candidate / 'data/science', root)
        from analysis.science_admission_amendment import prune_designated_fixture_closure
        prune_designated_fixture_closure(root)
        # This is a fresh hypothetical test lifecycle, never a continuation of
        # a repository stop. Actual stopped candidates are separately exercised
        # unmodified by check_stopped_dfa_policy.py and the trusted collector.
        if fresh_hypothetical:
            shutil.rmtree(root / 'stops', ignore_errors=True)
            shutil.rmtree(root / 'generated/implementation-stops', ignore_errors=True)
        registry = load_science_registry(root)
        projected = project_active_registry(registry, subject)
        contract = artifacts.build_policy_contract(projected, subject)
        if expected is not None and contract.contract_digest != expected:
            raise ValueError('Projected active contract mismatch')
        expected = contract.contract_digest
        decision = projected.decisions[subject]
        subjects = []
        for review_id in decision.evidence_review_ids:
            review = projected.evidence_reviews[review_id]
            if review.approval_mode.value != 'artifact':
                continue
            review = review.model_copy(update={'reviewed_on': reviewed_on})
            projected.review_paths[review_id].write_text(yaml.safe_dump(review.model_dump(mode='json'), sort_keys=False))
            subjects.append((artifacts.ReviewSubjectKind.EVIDENCE_REVIEW, review_id,
                             artifacts.evidence_review_digest(review), artifacts.ReviewRole.EVIDENCE_REVIEWER))
        projected.decision_paths[subject].write_text(yaml.safe_dump(decision.model_dump(mode='json'), sort_keys=False))
        subjects.append((artifacts.ReviewSubjectKind.SCIENCE_DECISION, subject,
                         artifacts.science_decision_digest(decision), artifacts.ReviewRole.DECISION_APPROVER))
        subjects.append((artifacts.ReviewSubjectKind.IMPLEMENTATION_CONTRACT, subject,
                         expected, artifacts.ReviewRole.IMPLEMENTATION_REVIEWER))
        for kind, identity, digest, role in subjects:
            payload = dict(schema_version=1, subject_kind=kind.value, subject_id=identity,
                           subject_digest=digest, reviewer='github:synthetic-validation-only',
                           role=role.value, reviewed_on=reviewed_on.isoformat(),
                           scopes=[s.value for s in artifacts.required_review_scopes(role)],
                           source_ref='https://github.com/praxys-run/praxys/issues/1#issuecomment-1')
            if role == artifacts.ReviewRole.IMPLEMENTATION_REVIEWER:
                payload.update(schema_version=2, implementation_binding=dict(
                    version=1, repository='praxys-run/praxys', pull_request=1,
                    base_sha='0' * 40, reviewed_head_sha='1' * 40,
                    diff_digest='sha256:' + '0' * 64, active_contract_digest=expected,
                    validation_run_id=1, validation_run_attempt=1,
                    validation_workflow_sha='0' * 40, validation_artifact_id=1,
                    validation_digest='sha256:' + '1' * 64))
            approval = artifacts.ScienceApproval.model_validate(payload)
            path = root / 'approvals' / f'synthetic-{identity}-{role.value}.yaml'
            path.parent.mkdir(exist_ok=True)
            path.write_text(yaml.safe_dump(approval.model_dump(mode='json', exclude_none=True)))
        active = load_science_registry(root)
        artifacts.sync_science_artifacts(active, check=False)
        (root / 'REGISTRY.md').write_text(render_registry_index(active))
        yield root, contract



@contextmanager
def synthetic_v2_registry(candidate: Path, phase: str, expected: str):
    """V2-only hypothetical lifecycle; actual V1 STOP/evidence stay untouched."""
    from analysis import science_artifacts as artifacts
    from analysis.evidence_registry import load_science_registry, render_registry_index
    from analysis.science_activation import project_active_registry
    from analysis.science_admission_amendment import DESIGNATED, validate_local_amendment
    from analysis.science_yaml import load_science_yaml
    import yaml
    if phase not in {'draft', 'accepted-inactive', 'projected-active'}:
        raise ValueError('Unsupported designated synthetic phase')
    with tempfile.TemporaryDirectory(prefix='synthetic-v2-policy-') as temporary:
        root = Path(temporary) / 'science'
        shutil.copytree(candidate / 'data/science', root, symlinks=True)
        registry = load_science_registry(root)
        validate_local_amendment(registry, require_unstopped=True)
        active = project_active_registry(registry, DESIGNATED)
        contract = artifacts.build_policy_contract(active, DESIGNATED)
        if contract.contract_digest != expected:
            raise ValueError('Projected V2 contract mismatch')
        for path in (root / 'approvals').rglob('*.yaml'):
            if load_science_yaml(path.read_text()).get('subject_id') == DESIGNATED:
                path.unlink()
        decision = registry.decisions[DESIGNATED]
        from analysis.evidence_registry import RecordStatus, ArtifactRuntimeState
        decision = decision.model_copy(update={'status': RecordStatus.DRAFT if phase == 'draft' else RecordStatus.ACCEPTED,
            'artifact_policy': decision.artifact_policy.model_copy(update={'runtime_state':
                ArtifactRuntimeState.ACTIVE if phase == 'projected-active' else ArtifactRuntimeState.INACTIVE})})
        registry.decision_paths[DESIGNATED].write_text(yaml.safe_dump(decision.model_dump(mode='json'), sort_keys=False))
        roles = [] if phase == 'draft' else [artifacts.ReviewRole.DECISION_APPROVER]
        if phase == 'projected-active':
            roles.append(artifacts.ReviewRole.IMPLEMENTATION_REVIEWER)
        for role in roles:
            implementation = role == artifacts.ReviewRole.IMPLEMENTATION_REVIEWER
            payload = dict(schema_version=2 if implementation else 1,
                subject_kind='implementation_contract' if implementation else 'science_decision',
                subject_id=DESIGNATED, subject_digest=expected if implementation else artifacts.science_decision_digest(decision),
                reviewer='github:synthetic-validation-only', role=role.value,
                reviewed_on=datetime.now(timezone.utc).date().isoformat(),
                scopes=[s.value for s in artifacts.required_review_scopes(role)],
                source_ref='https://github.com/praxys-run/praxys/issues/1#issuecomment-1')
            if implementation:
                payload['implementation_binding'] = dict(version=1, repository='praxys-run/praxys', pull_request=1,
                    base_sha='0'*40, reviewed_head_sha='1'*40, diff_digest='sha256:'+'0'*64,
                    active_contract_digest=expected, validation_run_id=1, validation_run_attempt=1,
                    validation_workflow_sha='0'*40, validation_artifact_id=1, validation_digest='sha256:'+'1'*64)
            approval = artifacts.ScienceApproval.model_validate(payload)
            (root / 'approvals' / f'synthetic-{DESIGNATED}-{role.value}.yaml').write_text(
                yaml.safe_dump(approval.model_dump(mode='json', exclude_none=True), sort_keys=False))
        projected = load_science_registry(root)
        artifacts.sync_science_artifacts(projected, check=False)
        (root / 'REGISTRY.md').write_text(render_registry_index(projected))
        yield root, contract

def main():
    # Backward-compatible CLI delegates completion to the trusted controller.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.run_science_policy_probe import main as controlled_probe
    controlled_probe('activation')


if __name__ == '__main__':
    main()
