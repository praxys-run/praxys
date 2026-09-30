"""Static contracts for the frontend/backend Application Insights boundary."""
from __future__ import annotations

import json
import os
import subprocess
import sys
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
    assert 'readonly WORKSPACE_RESOURCE_API_VERSION="2025-02-01"' in script
    assert '--retention-time' not in script
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


SUBSCRIPTION = "11111111-2222-3333-4444-555555555555"
WORKSPACE_ID = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-test/"
    "providers/Microsoft.OperationalInsights/workspaces/log-test"
)
FRONTEND_ID = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-test/"
    "providers/Microsoft.Insights/components/appi-frontend"
)
BACKEND_ID = FRONTEND_ID.replace("appi-frontend", "appi-backend")
FRONTEND_CONNECTION = "InstrumentationKey=frontend-secret-canary;IngestionEndpoint=https://frontend.invalid/"
BACKEND_CONNECTION = "InstrumentationKey=backend-secret-canary;IngestionEndpoint=https://backend.invalid/"


@pytest.fixture
def execute_boundary(tmp_path):
    """Run real helper/callers; Azure, HTTP and unrelated alerts are local fakes."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.jsonl"
    github_env = tmp_path / "github-env"
    program = f"#!{sys.executable}\n" + r'''
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with Path(os.environ['FAKE_LOG']).open('a') as stream:
    stream.write(json.dumps({'command': name, 'args': args}) + '\n')
def arg(flag):
    return args[args.index(flag) + 1]
workspace = os.environ['FAKE_WORKSPACE_ID']
frontend = os.environ['FAKE_FRONTEND_ID']
backend = os.environ['FAKE_BACKEND_ID']
if name == 'curl':
    print(os.environ.get('FAKE_PROBE_STATUS', '401'))
elif args[:2] == ['resource', 'patch']:
    if os.environ.get('FAKE_PATCH_FAIL') == 'true':
        raise SystemExit(42)
    if '--output' not in args or arg('--output') != 'none':
        print('unexpected-unmasked-resource-response-canary')
elif args[:2] == ['resource', 'update']:
    pass
elif args[:4] == ['monitor', 'log-analytics', 'workspace', 'show']:
    query = arg('--query')
    if query == 'id': print(workspace)
    elif query == 'retentionInDays': print(os.environ.get('FAKE_WORKSPACE_RETENTION', '30'))
    elif query == 'features.enableLogAccessUsingOnlyResourcePermissions':
        print(os.environ.get('FAKE_CONTEXT_ACCESS', 'true'))
    else: raise SystemExit(91)
elif args[:2] == ['resource', 'show']:
    query = arg('--query')
    if '--name' in args:
        print(frontend if arg('--name') == 'appi-frontend' else backend)
    elif query == 'properties.WorkspaceResourceId':
        print(os.environ.get('FAKE_LINKED_WORKSPACE', workspace))
    elif query == 'properties.DisableLocalAuth':
        key = 'FAKE_FRONTEND_AUTH' if arg('--ids') == frontend else 'FAKE_BACKEND_AUTH'
        print(os.environ.get(key, 'false' if arg('--ids') == frontend else 'true'))
    elif query == 'properties.DisableIpMasking':
        print(os.environ.get('FAKE_DISABLE_IP_MASKING', 'false'))
    elif query == 'properties.RetentionInDays':
        print(os.environ.get('FAKE_COMPONENT_RETENTION', '30'))
    elif query == 'properties.ConnectionString':
        print(os.environ['FAKE_FRONTEND_CONNECTION'] if arg('--ids') == frontend
              else os.environ['FAKE_BACKEND_CONNECTION'])
    else: raise SystemExit(92)
elif args[:3] == ['webapp', 'identity', 'show']:
    print(json.dumps({'principalId': 'synthetic-principal'}))
elif args[:4] == ['webapp', 'config', 'appsettings', 'list']:
    print('' if "name=='AZURE_CLIENT_ID'" in arg('--query') else backend)
elif args[:3] == ['role', 'assignment', 'list']:
    key = 'FAKE_PUBLISHER_COUNT' if 'Monitoring Metrics Publisher' in arg('--query') else 'FAKE_READER_COUNT'
    print(os.environ.get(key, '1'))
else:
    raise SystemExit(93)
'''
    for name in ("az", "curl"):
        executable = bin_dir / name
        executable.write_text(program)
        executable.chmod(0o755)

    def run(caller, **overrides):
        env = dict(
            os.environ, PATH=f"{bin_dir}:/usr/bin:/bin", FAKE_LOG=str(log),
            GITHUB_ENV=str(github_env), AZURE_SUBSCRIPTION_ID=SUBSCRIPTION,
            AZURE_RESOURCE_GROUP="rg-test", LOG_ANALYTICS_WORKSPACE="log-test",
            FRONTEND_APPINSIGHTS_NAME="appi-frontend", BACKEND_APPINSIGHTS_NAME="appi-backend",
            FAKE_WORKSPACE_ID=WORKSPACE_ID, FAKE_FRONTEND_ID=FRONTEND_ID,
            FAKE_BACKEND_ID=BACKEND_ID, FAKE_FRONTEND_CONNECTION=FRONTEND_CONNECTION,
            FAKE_BACKEND_CONNECTION=BACKEND_CONNECTION,
        )
        env.update(overrides)
        command = f'''
source "{BOUNDARY_SCRIPT}"
ensure_feedback_publication_alerts() {{
  printf '{{"command":"feedback-alerts","args":["%s"]}}\\n' "$1" >> "$FAKE_LOG"
}}
ensure_managed_plan_alerts() {{
  printf '{{"command":"managed-alerts","args":["%s"]}}\\n' "$1" >> "$FAKE_LOG"
}}
{caller}
'''
        result = subprocess.run(
            ["bash", "-c", command], env=env, cwd=tmp_path,
            capture_output=True, text=True, timeout=10,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        output = github_env.read_text() if github_env.exists() else ""
        return result, calls, output

    return run


@pytest.mark.parametrize("caller", ["backend_preflight", "frontend_resolve"])
def test_workspace_retention_patch_has_exact_target_and_minimal_numeric_properties(execute_boundary, caller):
    result, calls, output = execute_boundary(caller)
    assert result.returncode == 0, result.stderr
    patches = [call for call in calls if call["args"][:2] == ["resource", "patch"]]
    assert len(patches) == 1
    args = patches[0]["args"]
    assert args == [
        "resource", "patch", "--ids", WORKSPACE_ID, "--api-version", "2025-02-01",
        "--properties", '{"retentionInDays":30}', "--output", "none",
    ]
    properties = json.loads(args[args.index("--properties") + 1])
    assert properties == {"retentionInDays": 30}
    assert type(properties["retentionInDays"]) is int
    component_writes = [call for call in calls if call["args"][:2] == ["resource", "update"]]
    assert len(component_writes) == 1
    assert calls.index(patches[0]) < calls.index(component_writes[0])
    component_args = component_writes[0]["args"]
    assert "properties.DisableIpMasking=false" in component_args
    assert "properties.RetentionInDays=30" in component_args
    assert component_args[-2:] == ["--output", "none"]
    assert component_args[component_args.index("--ids") + 1] == (
        BACKEND_ID if caller == "backend_preflight" else FRONTEND_ID
    )
    assert not any(call["args"][:4] == ["monitor", "log-analytics", "workspace", "update"] for call in calls)
    expected_connection = BACKEND_CONNECTION if caller == "backend_preflight" else FRONTEND_CONNECTION
    other_connection = FRONTEND_CONNECTION if caller == "backend_preflight" else BACKEND_CONNECTION
    # The existing GitHub mask directive is the only permitted secret-bearing stdout.
    assert result.stdout.splitlines() == [f"::add-mask::{expected_connection}"]
    assert other_connection not in result.stdout + result.stderr + output
    assert expected_connection not in result.stderr
    assert expected_connection in output
    if caller == "backend_preflight":
        assert "properties.DisableLocalAuth=true" in component_args
        probe = next(call for call in calls if call["command"] == "curl")
        feedback = next(call for call in calls if call["command"] == "feedback-alerts")
        assert calls.index(probe) < calls.index(feedback)
        assert feedback["args"] == [BACKEND_ID]
        assert f"BACKEND_APPINSIGHTS_RESOURCE_ID={BACKEND_ID}" in output
    else:
        assert not any("DisableLocalAuth=" in arg for arg in component_args)
        assert output == f"VITE_APPINSIGHTS_CONNECTION_STRING={FRONTEND_CONNECTION}\n"


@pytest.mark.parametrize("caller", ["backend_preflight", "frontend_resolve"])
def test_workspace_patch_preserves_existing_selected_subscription_usage(execute_boundary, caller):
    result, calls, _ = execute_boundary(caller, AZURE_SUBSCRIPTION_ID="")
    assert result.returncode == 0, result.stderr
    patch = next(call for call in calls if call["args"][:2] == ["resource", "patch"])
    assert patch["args"][patch["args"].index("--ids") + 1] == WORKSPACE_ID


@pytest.mark.parametrize("caller", ["backend_preflight", "frontend_resolve"])
def test_workspace_patch_failure_stops_before_component_changes(execute_boundary, caller):
    result, calls, output = execute_boundary(caller, FAKE_PATCH_FAIL="true")
    assert result.returncode == 42
    assert sum(call["args"][:2] == ["resource", "patch"] for call in calls) == 1
    assert not any(call["args"][:2] == ["resource", "update"] for call in calls)
    assert output == ""
    assert "secret-canary" not in result.stdout + result.stderr


@pytest.mark.parametrize("caller", ["backend_preflight", "frontend_resolve"])
@pytest.mark.parametrize("workspace", [
    "", "not-an-id", WORKSPACE_ID + "/tables/table", WORKSPACE_ID + "?api-version=wrong",
    WORKSPACE_ID.replace("Microsoft.OperationalInsights", "Microsoft.Insights"),
    WORKSPACE_ID.replace("rg-test", "rg-other"), WORKSPACE_ID.replace("log-test", "log-other"),
    WORKSPACE_ID.replace(SUBSCRIPTION, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
])
def test_workspace_patch_rejects_invalid_or_different_resource(execute_boundary, caller, workspace):
    result, calls, output = execute_boundary(caller, FAKE_WORKSPACE_ID=workspace)
    assert result.returncode != 0
    assert not any(call["args"][:2] in (["resource", "patch"], ["resource", "update"]) for call in calls)
    assert output == ""


@pytest.mark.parametrize("caller", ["backend_preflight", "frontend_resolve"])
@pytest.mark.parametrize("setting,value", [
    ("FAKE_WORKSPACE_RETENTION", ""), ("FAKE_WORKSPACE_RETENTION", "90"),
    ("FAKE_COMPONENT_RETENTION", ""), ("FAKE_COMPONENT_RETENTION", "90"),
    ("FAKE_DISABLE_IP_MASKING", ""), ("FAKE_DISABLE_IP_MASKING", "true"),
    ("FAKE_BACKEND_AUTH", ""), ("FAKE_BACKEND_AUTH", "false"),
    ("FAKE_LINKED_WORKSPACE", ""),
    ("FAKE_LINKED_WORKSPACE", WORKSPACE_ID.replace("log-test", "log-other")),
])
def test_existing_boundary_readbacks_still_fail_closed(execute_boundary, caller, setting, value):
    result, _, output = execute_boundary(caller, **{setting: value})
    assert result.returncode != 0
    assert output == ""
    assert "secret-canary" not in result.stdout + result.stderr


@pytest.mark.parametrize("caller,setting,value", [
    ("frontend_resolve", "FAKE_FRONTEND_AUTH", "true"),
    ("backend_preflight", "FAKE_CONTEXT_ACCESS", "false"),
    ("backend_preflight", "FAKE_CONTEXT_ACCESS", ""),
    ("backend_preflight", "FAKE_PUBLISHER_COUNT", "0"),
    ("backend_preflight", "FAKE_READER_COUNT", "0"),
    ("backend_preflight", "FAKE_PROBE_STATUS", "200"),
])
def test_existing_authentication_and_permissions_still_block_release(execute_boundary, caller, setting, value):
    result, _, output = execute_boundary(caller, **{setting: value})
    assert result.returncode != 0
    assert output == ""
    assert "secret-canary" not in result.stdout + result.stderr
