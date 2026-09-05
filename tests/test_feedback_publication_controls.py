"""Static guardrails for feedback-publication operations and legal parity."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_ordinary_deploy_preserves_emergency_stop() -> None:
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()

    assert "read_setting PRAXYS_DISABLE_FEEDBACK_PUBLICATION" in workflow
    assert '--settings "PRAXYS_DISABLE_FEEDBACK_PUBLICATION=' not in workflow
    assert (
        'PRAXYS_ENABLE_FEEDBACK_PUBLICATION: '
        "${{ vars.PRAXYS_ENABLE_FEEDBACK_PUBLICATION || 'false' }}"
    ) in workflow
    assert "PRAXYS_DISABLE_FEEDBACK_PUBLICATION=${" not in workflow


def test_deploy_quiesces_v1_until_exact_v2_cutover_is_verified() -> None:
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()

    quiesce = workflow.index("- name: Quiesce feedback publication")
    deploy = workflow.index("- name: Deploy to App Service")
    verify = workflow.index("- name: Verify deployed backend cutover")
    restore = workflow.index(
        "- name: Restore reviewed feedback publication after verified cutover"
    )

    assert quiesce < deploy < verify < restore
    assert (
        '--settings "PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false"'
        in workflow[quiesce:deploy]
    )
    assert "https://api.praxys.run/api/health/ready" in workflow[quiesce:deploy]
    assert "feedback_publication_positive_enable" in workflow[quiesce:deploy]
    assert "PRAXYS_EXPECTED_API_SOURCE_SHA" in workflow[verify:restore]
    assert (
        '"PRAXYS_ENABLE_FEEDBACK_PUBLICATION=${DESIRED_FEEDBACK_PUBLICATION}"'
        in workflow[restore:]
    )
    assert "leave_disabled_on_failure" in workflow[restore:]
    assert "restoration_verified=true" in workflow[restore:]


def test_publication_alerts_are_actionable_and_have_an_action_group() -> None:
    script = (ROOT / "scripts/appinsights_boundary.sh").read_text()
    inventory = (ROOT / "docs/ops/monitoring-and-alerts.md").read_text()

    for name in (
        "praxys-feedback-publication-config-provider",
        "praxys-feedback-publication-aging",
    ):
        assert name in script
        assert name in inventory
    assert 'name == "praxys.feedback_publication"' in script
    assert 'status in ("config_failure", "provider_failure")' in script
    assert 'status in ("queue_aged", "unknown_aged")' in script
    assert 'actionGroups: [$action_group_id]' in script
    assert 'readonly OPERATIONS_ACTION_GROUP="praxys-feedback-ag"' in script


def test_pipia_and_legal_bundle_record_public_github_boundary() -> None:
    pipia = (
        ROOT / "docs/ops/cn-personal-information-impact-assessment.md"
    ).read_text()
    legal = (ROOT / "web/src/lib/legal.ts").read_text()

    assert "`1.3-feedback-publication`" in pipia
    assert "feedback-publication-v2-public-github" in pipia
    for text in (pipia, legal):
        normalized = text.casefold()
        assert "praxys-run/praxys" in normalized
        assert "outside mainland china" in normalized
        assert "retained long term" in normalized
        assert "screenshots" in normalized
