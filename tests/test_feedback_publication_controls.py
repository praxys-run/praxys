"""Static guardrails for feedback-publication operations and legal parity."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_dfa_recovery_workflow import execute_restoration, steps


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


@pytest.mark.parametrize('desired,kill,scenario', [
    (True, False, 'success'), (True, True, 'success'),
    (False, False, 'success'), (False, True, 'success'),
    (True, False, 'wrong_source'), (True, False, 'curl_18'),
    (True, False, 'curl_28'), (True, False, 'ambiguous_cleanup'),
])
def test_deploy_quiesces_v1_until_exact_v2_cutover_is_verified(
    execute_restoration, desired: bool, kill: bool, scenario: str,
) -> None:
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
    stages = steps()
    for name in (
        'Deploy to App Service', 'Verify deployed backend cutover',
        'Restore reviewed feedback publication after verified cutover',
    ):
        # GitHub's default success() dependency must not become an always-run
        # step or permit an earlier deployment/cutover failure to be ignored.
        assert stages[name].get('if', 'success()') == 'success()'
        assert stages[name].get('continue-on-error', 'false') == 'false'
    restoration = stages['Restore reviewed feedback publication after verified cutover']
    assert restoration['env']['DESIRED_FEEDBACK_PUBLICATION'] == (
        '${{ steps.quiesce.outputs.recovery_restore || '
        'steps.preserved.outputs.feedback_publication_restore }}'
    )

    # Execute the actual extracted controller with the existing bounded fixture;
    # its implementation language/function names are not the safety contract.
    plan = {}
    if scenario == 'wrong_source':
        plan = {'version': [{'body': {'version': 'synthetic-version', 'source_sha': '0' * 40}}]}
    elif scenario.startswith('curl_'):
        # The fixture still supplies a valid-looking current readiness body.
        plan = {'readiness': [{'exit': int(scenario.removeprefix('curl_'))}]}
    elif scenario == 'ambiguous_cleanup':
        plan = {'settings_read': [{'exit': 1}, {}],
                'disable_write': [{'exit': 124, 'applied': True}]}
    result, calls, output, _, _ = execute_restoration(desired=desired, kill=kill, plan=plan)
    writes = [call for call in calls if call['operation'] in {'restore_write', 'disable_write'}]
    assert writes[0]['operation'] == 'restore_write'
    assert f'PRAXYS_ENABLE_FEEDBACK_PUBLICATION={str(desired).lower()}' in writes[0]['args']
    assert all(not arg.startswith('PRAXYS_DISABLE_FEEDBACK_PUBLICATION=')
               for call in writes for arg in call['args'])
    observed = dict(line.split('=', 1) for line in output.splitlines())
    if scenario == 'success':
        assert result.returncode == 0, result.stderr + result.stdout
        assert len(writes) == 1
        assert observed == {'observation': 'verified', 'positive': str(desired).lower(),
                            'kill_switch': str(kill).lower(), 'enabled': str(desired and not kill).lower()}
    else:
        assert result.returncode != 0
        assert len(writes) == 2 and writes[1]['operation'] == 'disable_write'
        assert 'PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false' in writes[1]['args']
        assert observed['observation'] != 'verified'
        assert observed['positive'] == observed['kill_switch'] == observed['enabled'] == 'unknown'
        if scenario == 'ambiguous_cleanup':
            assert result.returncode == 1  # Preserve the original settings-read failure.
            assert observed['observation'] == 'unknown'
        else:
            assert observed['observation'] == 'control_plane_only'


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
