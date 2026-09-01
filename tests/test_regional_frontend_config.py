"""Static regression tests for regional delivery and launch operations."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github/workflows"
BASE_CORS = {
    "https://praxys.run",
    "https://www.praxys.run",
    "https://praxys-frontend.azurewebsites.net",
}
CN_CORS = {"https://praxys.cn", "https://www.praxys.cn"}
OBSOLETE = {
    "CN_PRIVACY_FLOOR_SHA",
    "PRAXYS_CN_APPROVED_RELEASES",
    "cn_release_preflight",
    "china_release_validation",
}


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _workflow(relative: str) -> dict[str, object]:
    return yaml.load(_text(relative), Loader=yaml.BaseLoader)


def test_workflow_yaml_is_valid() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(parsed, dict), path


def test_launch_actions_and_environment_authority_are_separate() -> None:
    parsed = _workflow(".github/workflows/launch-cn.yml")
    workflow = _text(".github/workflows/launch-cn.yml")
    inputs = parsed["on"]["workflow_dispatch"]["inputs"]
    assert inputs["action"]["type"] == "choice"
    assert inputs["action"]["options"] == ["status", "enable", "disable"]
    assert set(inputs) == {"action"}

    jobs = parsed["jobs"]
    assert set(jobs) == {"guard", "status", "enable", "disable"}
    assert "environment" not in jobs["guard"]
    assert "environment" not in jobs["status"]
    assert jobs["enable"]["environment"] == "china-production"
    assert "environment" not in jobs["disable"]
    assert "inputs.action == 'status'" in jobs["status"]["if"]
    assert "inputs.action == 'enable'" in jobs["enable"]["if"]
    assert "inputs.action == 'disable'" in jobs["disable"]["if"]
    assert '[[ "${GITHUB_REF}" != "refs/heads/main" ]]' in workflow
    assert "inputs.action == 'status'" in parsed["concurrency"]["group"]
    assert parsed["concurrency"]["cancel-in-progress"] == (
        "${{ inputs.action == 'disable' }}"
    )
    for name in ("status", "enable", "disable"):
        assert jobs[name]["needs"] == "guard"
    assert "Read-only: no setting" in workflow


def test_launch_enable_binds_current_main_but_disable_is_emergency() -> None:
    workflow = _text(".github/workflows/launch-cn.yml")
    assert workflow.count(
        'gh api "repos/${GITHUB_REPOSITORY}/branches/main"'
    ) == 1
    assert 'test "${GITHUB_SHA}" = "${current}"' in workflow
    assert "expected_main_sha" not in workflow
    assert "fetch-depth: 0" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "refs/remotes/origin/main" in workflow
    assert workflow.count("require_main_ancestor") >= 4
    enable = workflow[workflow.index("  enable:") : workflow.index("  disable:")]
    assert 'api.praxys.run/api/version | jq -r .source_sha)" \\\n            = "${GITHUB_SHA}"' not in enable
    assert '"https://${host}/deployed_sha.txt" | tr -d \'\\r\\n\')" \\\n              = "${GITHUB_SHA}"' not in enable
    disable = workflow[workflow.index("  disable:") :]
    assert "/api/version" not in disable
    assert "china-production" not in disable


def test_launch_exact_cors_preconditions_verification_and_compensation() -> None:
    workflow = _text(".github/workflows/launch-cn.yml")
    parsed = _workflow(".github/workflows/launch-cn.yml")
    assert set(json.loads(parsed["env"]["BASE_CORS"])) == BASE_CORS
    assert set(json.loads(parsed["env"]["CN_CORS"])) == CN_CORS
    assert "sort == ($base | sort) or sort == ($enabled | sort)" in workflow
    assert "Verify enable preconditions" in workflow
    assert "Verify enabled boundary" in workflow
    assert "PRAXYS_DISABLE_CN_PROCESSING=false" in workflow
    assert "az webapp cors add" in workflow
    assert workflow.count("Compensate failed or cancelled") == 1
    assert workflow.count("PRAXYS_DISABLE_CN_PROCESSING=true") == 2
    assert "steps.before.outputs.started_disabled == 'true'" in workflow
    assert "started_disabled=${cn_disabled}" in workflow
    assert "cors_state=${cors_state}" in workflow
    assert 'if [[ "${CORS_STATE}" == "base" ]]' in workflow
    assert "Enable China web processing from disabled" in workflow
    assert "az webapp cors remove" not in workflow
    assert "CLIENT_PRIVACY_UPDATE_REQUIRED" in workflow
    assert 'test "${code}" = 401' in workflow
    assert 'test "${code}" = 428' in workflow
    assert "Access-Control-Request-Headers:" in workflow
    assert '[[ "${code}" == "200" || "${code}" == "204" ]]' in workflow
    assert "scripts/verify_cors_response.sh" in workflow
    assert workflow.count(
        'bash scripts/verify_cors_response.sh "${actual}" "${origin}"'
    ) == 1
    assert "${stale_headers}" in workflow
    assert ".china_processing.disabled == true" in workflow
    assert "https://${host}/login" in workflow
    assert "grep -F '<div id=\"root\">'" in workflow
    assert "grep -F '<div id=\"root\"></div>'" not in workflow
    assert "https://${host}${asset_path}" in workflow
    assert "content-type" in workflow
    assert "CORS and Azure AI were unchanged" in workflow
    disable = workflow[workflow.index("  disable:") :]
    conditional_rights = disable.index(
        'if jq -e --argjson enabled "${enabled_cors}"'
    )
    rights_probe = disable.index(
        "for origin in https://praxys.cn https://www.praxys.cn"
    )
    summary = disable.index("Rights-route CORS: ${rights_cors}.")
    assert conditional_rights < rights_probe < summary
    assert "rights_cors=not-configured" in disable
    assert "rights_cors=verified" in disable


def test_launch_preserves_run_parity_and_reports_required_state() -> None:
    workflow = _text(".github/workflows/launch-cn.yml")
    assert "PRAXYS_DISABLE_BACKGROUND_AI=" not in workflow
    assert "--settings PRAXYS_DISABLE_BACKGROUND_AI" not in workflow
    assert workflow.count("PRAXYS_DISABLE_BACKGROUND_AI") >= 4
    assert "test \"$(read_setting PRAXYS_DISABLE_BACKGROUND_AI)\" = false" in workflow
    assert "background_ai_enabled == true" in workflow
    assert ".registration_open == true" in workflow
    assert "PRAXYS_LABS_EXECUTION_MODE" in workflow
    assert '"${labs_mode}" == "inline"' in workflow
    assert '"${labs_mode}" == "service_bus"' in workflow
    assert (
        'test "$(read_setting PRAXYS_DISABLE_MINIAPP_PROCESSING)" = false'
        in workflow
    )
    assert "required_status_checks" not in workflow
    assert "check-runs" not in workflow
    assert "upload-artifact" not in workflow
    assert "launch-cn-evidence" not in workflow
    assert "api_version" in workflow
    assert "api_ready" in workflow
    assert "core_valid" in workflow
    assert "cors_coherent" in workflow
    assert "cn_hosts_valid_when_enabled" in workflow
    assert "DNS is not available yet" in workflow
    assert "printf '{}'" not in workflow
    for host in CN_CORS:
        assert host in workflow


def test_backend_deploy_is_state_preserving_and_serialized() -> None:
    workflow = _text(".github/workflows/deploy-backend.yml")
    parsed = _workflow(".github/workflows/deploy-backend.yml")
    assert parsed["concurrency"]["group"] == "praxys-backend-deploy"
    assert (
        _workflow(".github/workflows/launch-cn.yml")["concurrency"]["group"]
        != parsed["concurrency"]["group"]
    )
    assert "--settings PRAXYS_DISABLE_CN_PROCESSING" not in workflow
    assert "az webapp cors add" not in workflow
    assert "az webapp cors remove" not in workflow
    assert "praxys-frontend-cn" not in workflow
    assert "praxys.cn" not in workflow
    assert "Capture coherent China state" not in workflow
    assert "Restore compatible captured China state" not in workflow
    assert "Leave China disabled after deployment failure" not in workflow
    assert "--settings PRAXYS_DISABLE_BACKGROUND_AI" not in workflow
    assert "PRAXYS_DISABLE_BACKGROUND_AI=" not in workflow
    assert "china_processing.enabled | type" in workflow
    assert ".miniapp_processing.disabled == $expectedMiniappDisabled" in workflow
    assert "Wait for frontend protected-main provenance" not in workflow
    assert "Capture state preserved by deployment" in workflow
    assert "EXPECTED_CN_DISABLED" in workflow
    assert "EXPECTED_AI_DISABLED" in workflow
    assert "EXPECTED_CORS" in workflow
    assert '.china_processing.disabled == $expectedCnDisabled' in workflow
    assert '.china_processing.enabled == ($expectedCnDisabled | not)' in workflow
    assert "background_ai_kill_switch\n                   == $expectedAiDisabled" in workflow
    assert "background_ai_enabled\n                   == ($expectedAiDisabled | not)" in workflow


def test_backend_config_preserves_miniapp_and_wechat_secrets() -> None:
    workflow = _text(".github/workflows/deploy-backend.yml")
    assert 'PRESERVED_MINIAPP_CONFIGURED' in workflow
    assert 'app_settings+=("PRAXYS_DISABLE_MINIAPP_PROCESSING=false")' in workflow
    assert "PRAXYS_DISABLE_MINIAPP_PROCESSING=${PRESERVED_MINIAPP_DISABLED}" not in workflow
    assert "vars.PRAXYS_DISABLE_MINIAPP_PROCESSING" not in workflow
    assert "Set both WeChat Miniapp secrets or neither." in workflow
    assert 'if [[ -n "${WECHAT_MINIAPP_APPID}"' in workflow
    assert 'app_settings+=(' in workflow
    settings_call = workflow.split(
        "az webapp config appsettings set", 1
    )[1].split("az webapp config set", 1)[0]
    assert '--settings "${app_settings[@]}"' in settings_call
    assert 'WECHAT_MINIAPP_APPID="${WECHAT_MINIAPP_APPID}"' not in settings_call
    assert 'WECHAT_MINIAPP_SECRET="${WECHAT_MINIAPP_SECRET}"' not in settings_call
    assert '"${PRAXYS_LABS_EXECUTION_MODE}" == "inline"' in workflow
    assert '"${PRAXYS_LABS_EXECUTION_MODE}" == "disabled"' in workflow
    assert '"${PRAXYS_LABS_EXECUTION_MODE}" == "service_bus"' in workflow
    assert "az servicebus namespace list" in workflow
    assert "PRAXYS_LABS_SERVICE_BUS_FQDN=${LABS_SERVICE_BUS_FQDN}" in workflow
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "China processing enabled" in workflow
    assert "Miniapp processing enabled" in workflow
    assert "Azure AI emergency stop" in workflow
    assert "      - 'alembic/**'" in workflow
    assert "scripts/appinsights_boundary.sh backend-cutover" in workflow
    assert "PRAXYS_DATABASE_URL" in workflow
    assert "SCM_DO_BUILD_DURING_DEPLOYMENT" in workflow
    assert "--always-on true" in workflow


def test_frontend_keeps_run_first_and_edgeone_build_simple() -> None:
    workflow = _text(".github/workflows/deploy-frontend-appservice.yml")
    edge_build_script = _text("web/scripts/build-edgeone.mjs")
    edge_metadata = _text("web/scripts/prepare-edgeone-artifact.mjs")
    azure_copy = workflow.index("cp -r web/dist deploy-pkg/web/dist")
    edge_build = workflow.index("npm --prefix web run build:edgeone")
    assert azure_copy < edge_build
    assert "The shared Azure build contains China-only metadata" in workflow
    assert "frontend-edgeone-cn-${{ github.run_id }}" not in workflow
    assert "Upload optional EdgeOne inspection artifact" not in workflow
    assert "verify_edgeone_public:" not in workflow
    assert "SHA256SUMS" not in workflow
    assert "manifest" not in workflow.lower()
    assert "preflight" not in workflow.lower()
    assert "registry" not in workflow.lower()
    assert "production authorization" not in workflow.lower()
    assert "EDGEONE_API_TOKEN" not in workflow
    assert "deploy_edgeone:" not in workflow
    assert "npx edgeone" not in workflow
    assert "VITE_API_URL: \"https://api.praxys.run\"" in edge_build_script
    assert "EdgeOne requires VITE_APPINSIGHTS_CONNECTION_STRING" in edge_build_script
    assert "VITE_APPINSIGHTS_CONNECTION_STRING: regionalAppInsights" in edge_build_script
    assert 'VITE_STATSIG_CLIENT_KEY: ""' in edge_build_script
    assert "stampChinaCompliance" in edge_metadata
    assert "deployed_sha.txt" in edge_metadata
    assert "'healthz'" in edge_metadata
    from api.china_client_boundary import CN_PRIVACY_CONTRACT_VERSION
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION

    for value in (
        TERMS_VERSION,
        TERMS_CONTENT_DIGEST,
        CN_PRIVACY_CONTRACT_VERSION,
    ):
        assert value in edge_metadata
    for token in OBSOLETE:
        assert token not in edge_build_script
        assert token not in edge_metadata
    assert "SHA256SUMS" not in edge_build_script + edge_metadata


def test_edgeone_public_verification_is_owned_by_launch_workflow() -> None:
    workflow = _text(".github/workflows/deploy-frontend-appservice.yml")
    assert "verify_edgeone_public:" not in workflow
    launch = _text(".github/workflows/launch-cn.yml")
    assert 'service == "praxys-frontend-cn"' in launch
    assert 'name="praxys-deployment-region" content="cn"' in launch
    assert "沪ICP备2025109616号-2" in launch


def test_miniapp_is_decoupled_from_china_web_launch() -> None:
    workflow = _text(".github/workflows/miniapp-publish.yml")
    assert not any(token in workflow for token in OBSOLETE)
    assert "launch-cn" not in workflow
    assert "china-production" not in workflow
    assert "robot=\"5\"" in workflow
    assert "robot=\"1\"" in workflow
    assert "git merge-base --is-ancestor" in workflow
    assert "refs/remotes/origin/main" in workflow
    assert workflow.index("Require release tag commit on main") < (
        workflow.index("Write upload key")
    )
    assert "Promotion and publication remain human-authorized provider actions." in workflow
    assert "node-version: '24.11.0'" in workflow
    package = json.loads(_text("miniapp/package.json"))
    assert package["devDependencies"]["miniprogram-ci"] == "2.1.31"


def test_obsolete_ceremony_is_removed_from_owned_operations_scope() -> None:
    assert not (ROOT / "scripts/cn_release_preflight.py").exists()
    assert not (ROOT / "tests/test_cn_release_preflight.py").exists()

    owned = [
        ".github/workflows/launch-cn.yml",
        ".github/workflows/deploy-backend.yml",
        ".github/workflows/deploy-frontend-appservice.yml",
        ".github/workflows/miniapp-publish.yml",
        "docs/ops/README.md",
        "docs/ops/environment.md",
        "docs/ops/deploy.md",
        "docs/ops/config-and-secrets.md",
        "docs/ops/tencent-frontend.md",
        "docs/ops/monitoring-and-alerts.md",
        "docs/ops/cn-personal-information-impact-assessment.md",
        "docs/ops/cn-web-private-alpha.md",
        "docs/dev/api-reference.md",
        ".env.example",
    ]
    combined = "\n".join(_text(path) for path in owned)
    for token in OBSOLETE:
        assert token not in combined


def test_launch_is_the_only_cn_state_writer_and_docs_keep_five_origins() -> None:
    cn_setting_write = "PRAXYS_DISABLE_CN_PROCESSING="
    writers = {
        path.name
        for path in WORKFLOWS.glob("*.yml")
        if cn_setting_write in path.read_text(encoding="utf-8")
        and "--settings" in path.read_text(encoding="utf-8")
    }
    assert writers == {"launch-cn.yml"}

    tencent = _text("docs/ops/tencent-frontend.md")
    for origin in BASE_CORS | CN_CORS:
        assert origin in tencent
    assert '["https://praxys.cn", "https://www.praxys.cn"]' not in tencent


def test_protected_main_oidc_and_job_scoped_permissions_remain() -> None:
    backend = _workflow(".github/workflows/deploy-backend.yml")
    frontend = _workflow(".github/workflows/deploy-frontend-appservice.yml")
    launch = _workflow(".github/workflows/launch-cn.yml")
    assert "permissions" not in backend
    assert "permissions" not in frontend
    assert "permissions" not in launch
    assert backend["jobs"]["test"]["permissions"] == {"contents": "read"}
    assert backend["jobs"]["deploy"]["permissions"]["id-token"] == "write"
    assert frontend["jobs"]["test"]["permissions"] == {"contents": "read"}
    assert frontend["jobs"]["build"]["permissions"]["id-token"] == "write"
    assert frontend["jobs"]["deploy_azure"]["permissions"] == {
        "id-token": "write",
        "contents": "read",
    }
    assert launch["jobs"]["status"]["permissions"]["id-token"] == "write"
    assert launch["jobs"]["guard"]["permissions"] == {
        "contents": "read"
    }
    assert launch["jobs"]["enable"]["permissions"]["id-token"] == "write"
    assert launch["jobs"]["disable"]["permissions"]["id-token"] == "write"

    for relative in (
        ".github/workflows/deploy-backend.yml",
        ".github/workflows/deploy-frontend-appservice.yml",
        ".github/workflows/launch-cn.yml",
    ):
        workflow = _text(relative)
        assert "azure/login@v3" in workflow
        assert "AZURE_CLIENT_SECRET" not in workflow
        assert "publish-profile" not in workflow
        assert "client-id:" in workflow


def test_edgeone_config_keeps_static_security_boundary() -> None:
    config = json.loads(_text("web/edgeone.json"))
    assert config["installCommand"] == "npm ci --legacy-peer-deps"
    assert config["buildCommand"] == "npm run build:edgeone"
    assert config["outputDirectory"] == "./dist"
    assert config["nodeVersion"] == "24.11.0"
    assert config["rewrites"] == [{"source": "/*", "destination": "/index.html"}]
    headers = {
        rule["source"]: {
            header["key"]: header["value"] for header in rule["headers"]
        }
        for rule in config["headers"]
    }
    assert headers["/*"] == {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }
    assert headers["/assets/*"]["Cache-Control"] == (
        "public, max-age=31536000, immutable"
    )
    for route in ("/login*", "/today*", "/settings*", "/admin*"):
        assert headers[route]["X-Robots-Tag"] == "noindex, nofollow"


def test_cors_response_verifier_uses_exact_values_and_tokens(tmp_path) -> None:
    verifier = ROOT / "scripts/verify_cors_response.sh"
    headers = tmp_path / "headers"
    valid = (
        "HTTP/2 204\r\n"
        "Access-Control-Allow-Origin: https://praxys.cn\r\n"
        "Access-Control-Allow-Methods: OPTIONS, GET\r\n"
        "Access-Control-Allow-Methods: POST\r\n"
        "Access-Control-Allow-Headers: authorization, content-type\r\n"
        "Access-Control-Allow-Headers: x-praxys-client, "
        "x-praxys-notice-version, x-praxys-policy-digest, "
        "x-praxys-api-contract\r\n"
    )
    headers.write_text(valid, encoding="utf-8")
    command = [
        "bash",
        str(verifier),
        str(headers),
        "https://praxys.cn",
        "GET",
        "authorization",
        "content-type",
        "x-praxys-client",
        "x-praxys-notice-version",
        "x-praxys-policy-digest",
        "x-praxys-api-contract",
    ]
    assert subprocess.run(command, check=False).returncode == 0
    actual_command = command[:4]
    assert subprocess.run(actual_command, check=False).returncode == 0

    # Fetch permits Access-Control-Allow-Methods to be omitted for a
    # CORS-safelisted method, even when request headers trigger a preflight.
    without_methods = valid.replace(
        "Access-Control-Allow-Methods: OPTIONS, GET\r\n", ""
    ).replace("Access-Control-Allow-Methods: POST\r\n", "")
    headers.write_text(without_methods, encoding="utf-8")
    assert subprocess.run(command, check=False).returncode == 0

    non_safelisted_command = command.copy()
    non_safelisted_command[4] = "PUT"
    assert subprocess.run(non_safelisted_command, check=False).returncode != 0

    wrong_method = without_methods.replace(
        "Access-Control-Allow-Origin: https://praxys.cn\r\n",
        "Access-Control-Allow-Origin: https://praxys.cn\r\n"
        "Access-Control-Allow-Methods: PUT\r\n",
    )
    headers.write_text(wrong_method, encoding="utf-8")
    assert subprocess.run(command, check=False).returncode != 0

    for invalid in (
        valid.replace(
            "https://praxys.cn\r\n",
            "https://praxys.cn.evil.example\r\n",
        ),
        valid.replace("OPTIONS, GET", "OPTIONS, TARGET"),
        valid.replace("x-praxys-client,", "x-praxys-client-extra,"),
        valid.replace("content-type\r\n", "content-type-extra\r\n"),
        valid.replace(
            "Access-Control-Allow-Origin: https://praxys.cn\r\n",
            "Access-Control-Allow-Origin: https://praxys.cn\r\n"
            "Access-Control-Allow-Origin: https://praxys.cn\r\n",
        ),
        valid.replace(
            "Access-Control-Allow-Origin: https://praxys.cn\r\n",
            "Access-Control-Allow-Origin: https://praxys.cn\r\n"
            "Access-Control-Allow-Origin: https://www.praxys.cn\r\n",
        ),
    ):
        headers.write_text(invalid, encoding="utf-8")
        assert subprocess.run(command, check=False).returncode != 0

    for invalid_actual in (
        valid.replace(
            "https://praxys.cn\r\n",
            "https://praxys.cn.evil.example\r\n",
        ),
        valid.replace(
            "Access-Control-Allow-Origin: https://praxys.cn\r\n",
            "Access-Control-Allow-Origin: https://praxys.cn\r\n"
            "Access-Control-Allow-Origin: https://praxys.cn\r\n",
        ),
        valid.replace(
            "Access-Control-Allow-Origin: https://praxys.cn\r\n",
            "Access-Control-Allow-Origin: https://praxys.cn\r\n"
            "Access-Control-Allow-Origin: https://www.praxys.cn\r\n",
        ),
    ):
        headers.write_text(invalid_actual, encoding="utf-8")
        assert subprocess.run(actual_command, check=False).returncode != 0


def test_material_non_cn_invariants_remain_covered() -> None:
    backend = _text(".github/workflows/deploy-backend.yml")
    assert "d5ecc8c14beafe1cf2df6e5021b0bee71094b15cf14dfc039f0652c8c9c030e4" in backend
    assert "STRYD_CLIENT_WHEEL_B64" in backend

    miniapp_build = _text(".github/workflows/miniapp-build.yml")
    miniapp_publish = _text(".github/workflows/miniapp-publish.yml")
    assert miniapp_build.count("web/src/lib/legal.ts") == 2
    assert miniapp_build.count("web/src/types/api.ts") == 2
    assert "web/src/lib/legal" in miniapp_publish
    assert "pending-upload" in miniapp_publish
    assert "upload-failed" in miniapp_publish
    assert "providerResponse: \"redacted\"" in miniapp_publish

    canonical = "trainsight-master-key"
    for relative in (
        "docs/deployment.md",
        "docs/ops/README.md",
        "docs/ops/environment.md",
        "docs/ops/config-and-secrets.md",
        "docs/ops/disaster-recovery.md",
        "docs/ops/secret-rotation.md",
    ):
        assert canonical in _text(relative)
    assert (
        f'os.environ.get("KEY_VAULT_KEY_NAME", "{canonical}")'
        in _text("db/crypto.py")
    )


def test_release_metadata_is_not_interpolated_into_literal_shell() -> None:
    for relative in (
        ".github/workflows/launch-cn.yml",
        ".github/workflows/deploy-backend.yml",
        ".github/workflows/deploy-frontend-appservice.yml",
        ".github/workflows/miniapp-publish.yml",
    ):
        workflow = _text(relative)
        in_literal_run = False
        run_indent = 0
        for line in workflow.splitlines():
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if stripped == "run: |":
                in_literal_run = True
                run_indent = indent
                continue
            if in_literal_run and stripped and indent <= run_indent:
                in_literal_run = False
            if in_literal_run:
                assert "${{" not in line
