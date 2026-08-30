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
