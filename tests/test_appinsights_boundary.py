"""Static contracts for the frontend/backend Application Insights boundary."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_MAP = ROOT / ".github" / "azure-observability.env"
BACKEND_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-backend.yml"
FRONTEND_WORKFLOW = (
    ROOT / ".github" / "workflows" / "deploy-frontend-appservice.yml"
)
BOUNDARY_SCRIPT = ROOT / "scripts" / "appinsights_boundary.sh"


def _resource_names() -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in RESOURCE_MAP.read_text(encoding="utf-8").splitlines()
        if line
    )


def test_appinsights_resources_are_distinct() -> None:
    """Browser and backend telemetry must resolve to different components."""
    resources = _resource_names()

    assert resources["FRONTEND_APPINSIGHTS_NAME"]
    assert resources["BACKEND_APPINSIGHTS_NAME"]
    assert (
        resources["FRONTEND_APPINSIGHTS_NAME"]
        != resources["BACKEND_APPINSIGHTS_NAME"]
    )


def test_backend_workflow_enforces_server_only_ingestion() -> None:
    """The backend workflow owns routing and rejects local-auth drift."""
    workflow = BACKEND_WORKFLOW.read_text(encoding="utf-8")
    script = BOUNDARY_SCRIPT.read_text(encoding="utf-8")

    assert "vars.APPLICATIONINSIGHTS_CONNECTION_STRING" not in workflow
    assert "backend-preflight" in workflow
    assert "backend-cutover" in workflow
    assert "properties.DisableLocalAuth=true" in script
    assert "properties.DisableIpMasking=false" in script
    assert 'readonly BACKEND_RETENTION_DAYS=30' in script
    assert 'properties.RetentionInDays="${BACKEND_RETENTION_DAYS}"' in script
    assert '--retention-time "${BACKEND_RETENTION_DAYS}"' in script
    assert "properties.WorkspaceResourceId" in script
    assert "enableLogAccessUsingOnlyResourcePermissions" in script
    assert "Wait for frontend protected-main provenance" not in workflow
    assert "deploy-frontend-appservice.yml/runs" not in workflow
    assert "Determine deployment mode" in workflow
    assert "sync_config:" in workflow
    assert "steps.mode.outputs.sync_config == 'true'" in workflow
    assert "scripts/appinsights_boundary\\.sh" in workflow
    assert "Wait for App Service deployment endpoint to settle" in workflow
    assert "sleep 90" in workflow
    assert "az webapp log deployment list" in workflow
    assert "stable_probes >= 3" in workflow
    assert "timeout-minutes: 8" in workflow
    assert "timeout 20s az webapp" in workflow
    assert "      - 'tests/**'" not in workflow
    assert "PRAXYS_EXPECTED_API_VERSION" in workflow
    assert "Verify deployed backend cutover" in workflow
    assert "deployment_ready()" in workflow
    assert "az webapp restart" in workflow
    assert ".version == $version and .source_sha == $sha" in workflow
    assert '.status == "ready"' in workflow
    assert '.china_processing.disabled == $expectedCnDisabled' in workflow
    assert '.china_processing.enabled == ($expectedCnDisabled | not)' in workflow
    assert "background_ai_kill_switch\n                   == $expectedAiDisabled" in workflow
    assert "background_ai_enabled\n                   == ($expectedAiDisabled | not)" in workflow
    assert "group: praxys-backend-deploy" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "github.ref == 'refs/heads/main' && inputs.run_tests == true" in workflow
    assert "tags:" not in workflow
    assert (
        "needs.test.result == 'success' || "
        "needs.test.result == 'skipped'"
    ) in workflow
    assert "Monitoring Metrics Publisher" in script
    assert "Monitoring Reader" in script
    assert "userAssignedIdentities" in script
    assert "[?name=='AZURE_CLIENT_ID'].value | [0]" in script
    assert "PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID" in script
    assert "--setting-names PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID" in script
    assert "forged_browser_probe" in script
    assert "rollback_cutover" in script
    assert "rollback-to-frontend" in script
    assert "recreate_scheduled_alert" in script
    assert "del(.createdWithApiVersion)" in script
    assert "praxys-db-health-unhealthy" in script
    assert "praxys-managed-plan-provider-failures" in script
    assert "praxys-managed-plan-defects" in script
    assert "praxys-feedback-ag" in script
    assert "support@praxys.run" in script
    assert "ensure_managed_plan_alerts" in script
    assert ".enabled == true" in script
    assert ".emailReceivers[]?" in script
    assert "Skipping missing deployment-owned managed-plan alert during rollback" in script
    assert "active_alert_names" in script
    assert 'failure_domain in ("provider", "provider_auth")' in script
    assert 'failure_domain == "praxys"' in script
    assert "affected_users >= 5" in script
    assert 'evaluationFrequency: "PT15M"' in script
    assert "wt-praxys-api-health" in script
    cutover = script.split("telemetry_cutover()", 1)[1]
    backend_branch, frontend_branch = cutover.split("frontend)", 1)
    frontend_branch = frontend_branch.split(";;", 1)[0]
    assert "verify_resource_context_access" in backend_branch
    assert "verify_resource_context_access" not in frontend_branch


def test_frontend_workflow_resolves_only_frontend_ingestion() -> None:
    """The browser build must never receive the backend connection string."""
    workflow = FRONTEND_WORKFLOW.read_text(encoding="utf-8")

    assert "vars.VITE_APPINSIGHTS_CONNECTION_STRING" not in workflow
    assert "frontend-resolve" in workflow
    assert "_deployed_sha.txt" in workflow
    assert 'printf \'%s\\n\' "${GITHUB_SHA}"' in workflow
    assert "group: deploy-frontend-production" in workflow
    assert "cancel-in-progress: false" in workflow


def test_boundary_script_has_valid_bash_syntax() -> None:
    """The deployment guard must remain parseable by the Actions Bash shell."""
    if os.name == "nt":
        pytest.skip("Windows resolves bash to WSL; Actions validation runs on Linux")
    subprocess.run(["bash", "-n", str(BOUNDARY_SCRIPT)], check=True)


def test_feedback_publication_alert_transition_scenarios_are_backend_only() -> None:
    """Cutover/rollback policy never enables publication alerts on frontend."""
    command = f'''
source "{BOUNDARY_SCRIPT}"
BACKEND_AI_ID="/subscriptions/test/backend"
FRONTEND_AI_ID="/subscriptions/test/frontend"
feedback_alert_action backend "$FRONTEND_AI_ID" true
feedback_alert_action frontend "$BACKEND_AI_ID" true
feedback_alert_action restore "$FRONTEND_AI_ID" true
feedback_alert_action restore "$BACKEND_AI_ID" false
'''
    result = subprocess.run(
        ["bash", "-c", command],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == [
        "backend-enabled",
        "delete",
        "delete",
        "backend-preserve-disabled",
    ]


def test_feedback_publication_alert_lifecycle_is_pinned_after_auth_rejection() -> None:
    script = BOUNDARY_SCRIPT.read_text(encoding="utf-8")
    preflight = script.split("backend_preflight()", 1)[1].split(
        "frontend_resolve()", 1
    )[0]
    assert preflight.index("verify_anonymous_ingestion_rejected") < preflight.index(
        'ensure_feedback_publication_alerts "${BACKEND_AI_ID}"'
    )
    assert "is_feedback_publication_alert" in script
    assert "delete_feedback_publication_alerts" in script
    assert "Skipping missing feedback-publication alert" in script
    assert 'feedback_alert_action frontend' in script
    assert 'feedback_alert_action restore' in script
    assert 'if [[ "${BASH_SOURCE[0]}" == "$0" ]]' in script


@pytest.mark.parametrize(
    ("scenario", "expected_success"),
    [
        ("missing", True),
        ("lookup_error", False),
        ("verify_lookup_error", False),
        ("subscription_not_found", False),
        ("verify_subscription_not_found", False),
        ("raw_status_three", False),
        ("verify_raw_status_three", False),
        ("delete_error", False),
        ("still_present", False),
    ],
)
def test_feedback_alert_absence_is_verified_fail_closed(
    scenario: str,
    expected_success: bool,
) -> None:
    command = f'''
source "{BOUNDARY_SCRIPT}"
AZURE_RESOURCE_GROUP="rg-test"
SCENARIO="{scenario}"
az() {{
  if [[ "$1 $2" == "resource show" ]]; then
    case "$SCENARIO" in
      missing) echo "ResourceNotFound" >&2; return 3 ;;
      lookup_error|verify_lookup_error)
        echo "control plane unavailable" >&2; return 42 ;;
      subscription_not_found|verify_subscription_not_found)
        echo "Subscription 'deadbeef' not found" >&2; return 1 ;;
      raw_status_three|verify_raw_status_three)
        echo "control plane unavailable" >&2; return 3 ;;
      *) echo "/subscriptions/test/alerts/praxys-feedback"; return 0 ;;
    esac
  fi
  if [[ "$1 $2 $3" == "rest --method delete" ]]; then
    if [[ "$SCENARIO" == "delete_error" ]]; then
      echo "delete denied" >&2
      return 42
    fi
    return 0
  fi
  echo "unexpected az invocation: $*" >&2
  return 44
}}
case "$SCENARIO" in
  missing)
    delete_feedback_publication_alerts && verify_feedback_publication_alerts_absent ;;
  still_present|verify_lookup_error|verify_subscription_not_found|verify_raw_status_three)
    verify_feedback_publication_alerts_absent ;;
  *)
    delete_feedback_publication_alerts ;;
esac
'''
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is expected_success, result.stderr


def test_frontend_cutover_verifies_feedback_alert_absence() -> None:
    script = BOUNDARY_SCRIPT.read_text(encoding="utf-8")
    cutover = script.split("telemetry_cutover()", 1)[1]
    assert "verify_feedback_publication_alerts_absent" in cutover
    assert "resolve_scheduled_alert_id" in script
