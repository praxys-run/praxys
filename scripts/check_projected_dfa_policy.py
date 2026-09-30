"""Synthetic-only projected activation check; never produces real approvals.

Prepares candidate data with trusted code, never importing candidate modules.
The CLI delegates candidate execution and completion to the bounded controller.
"""
from contextlib import contextmanager
from datetime import date
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
    with tempfile.TemporaryDirectory(prefix='synthetic-dfa-policy-') as temporary:
        root = Path(temporary) / 'science'
        shutil.copytree(candidate / 'data/science', root)
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
            review = review.model_copy(update={'reviewed_on': date.today()})
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
                           role=role.value, reviewed_on=date.today().isoformat(),
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


def main():
    # Backward-compatible CLI delegates completion to the trusted controller.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.run_science_policy_probe import main as controlled_probe
    controlled_probe('activation')


if __name__ == '__main__':
    main()
