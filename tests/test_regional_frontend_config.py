"""Regression tests for the regional frontend delivery boundaries."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_edgeone_config_keeps_spa_and_security_rules_in_source_control() -> None:
    config = json.loads((ROOT / "web/edgeone.json").read_text(encoding="utf-8"))

    assert set(config) == {
        "buildCommand",
        "headers",
        "installCommand",
        "nodeVersion",
        "outputDirectory",
        "rewrites",
    }
    assert config["installCommand"] == "npm ci --legacy-peer-deps"
    assert config["buildCommand"] == "npm run build:edgeone"
    assert config["outputDirectory"] == "./dist"
    assert config["nodeVersion"] == "24.11.0"
    assert config["rewrites"] == [
        {"source": "/*", "destination": "/index.html"}
    ]
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
    private_routes = {
        "/login*",
        "/terms*",
        "/privacy*",
        "/status*",
        "/verify*",
        "/mcp/*",
        "/today*",
        "/setup*",
        "/training*",
        "/analysis*",
        "/goal*",
        "/history*",
        "/science*",
        "/labs*",
        "/settings*",
        "/admin*",
    }
    for route in private_routes:
        assert headers[route]["X-Robots-Tag"] == "noindex, nofollow"
    assert not (ROOT / "deploy/tencent/nginx-praxys.conf").exists()


def test_edgeone_artifact_is_stamped_without_mutating_the_azure_package() -> None:
    workflow = (
        ROOT / ".github/workflows/deploy-frontend-appservice.yml"
    ).read_text(encoding="utf-8")

    azure_stage = workflow.index("cp -r web/dist deploy-pkg/web/dist")
    china_build = workflow.index("npm --prefix web run build:edgeone")
    china_copy = workflow.index("cp -a web/dist/. edgeone-site/")
    azure_upload = workflow.index("- name: Upload Azure package")
    edgeone_upload = workflow.index("- name: Upload EdgeOne package")
    edgeone_preflight_upload = workflow.index(
        "- name: Upload EdgeOne preparation evidence"
    )
    evidence_finalize = workflow.index(
        "- name: Finalize frontend build evidence"
    )
    evidence_upload = workflow.index("- name: Upload frontend build evidence")

    assert azure_stage < china_build < china_copy
    assert (
        azure_upload
        < edgeone_upload
        < edgeone_preflight_upload
        < evidence_finalize
        < evidence_upload
    )
    assert "grep -R --binary-files=text" in workflow
    assert "The shared Azure build contains China-only metadata" in workflow
    assert "sha256sum --check SHA256SUMS" in workflow
    assert "frontend-edgeone-cn-${{ github.run_id }}" in workflow
    assert "for host in praxys.cn www.praxys.cn" in workflow
    assert "沪ICP备2025109616号-2" in workflow
    assert "Initialize frontend build evidence" in workflow
    assert "Finalize frontend build evidence" in workflow
    assert "azurePackagePresent" in workflow
    assert "edgeonePackagePresent" in workflow
    assert "edgeonePreflightSha256" in workflow
    assert "edgeone-unpublished-preflight.json" in workflow
    assert "validated-unpublished-preparation" in workflow
    assert "Upload frontend build evidence" in workflow
    assert "self-hosted" not in workflow
    assert "TENCENT_LIGHTHOUSE" not in workflow
    assert "nginx" not in workflow.lower()


def test_edgeone_git_integration_uses_checked_in_deterministic_builds() -> None:
    workflow = (
        ROOT / ".github/workflows/deploy-frontend-appservice.yml"
    ).read_text(encoding="utf-8")
    package = json.loads(
        (ROOT / "web/package.json").read_text(encoding="utf-8")
    )
    build_script = (ROOT / "web/scripts/build-edgeone.mjs").read_text(
        encoding="utf-8"
    )
    prepare_script = (
        ROOT / "web/scripts/prepare-edgeone-artifact.mjs"
    ).read_text(
        encoding="utf-8"
    )

    assert package["scripts"]["build:edgeone"] == (
        "node scripts/build-edgeone.mjs"
    )
    assert package["scripts"]["prepare:edgeone"] == (
        "node scripts/prepare-edgeone-artifact.mjs"
    )
    assert "VITE_API_URL: \"https://api.praxys.run\"" in build_script
    assert "VITE_APPINSIGHTS_CONNECTION_STRING: \"\"" in build_script
    assert "VITE_STATSIG_CLIENT_KEY: \"\"" in build_script
    assert "CN_PRIVACY_FLOOR_SHA must be configured" in build_script
    assert "CN_PREFLIGHT_OUTPUT" in build_script
    assert "stampChinaCompliance" in prepare_script
    assert "SHA256SUMS" in prepare_script
    assert "deployed_sha.txt" in prepare_script
    assert "EDGEONE_API_TOKEN" not in workflow
    assert "EDGEONE_CN_PROJECT_ID" not in workflow
    assert "EDGEONE_CN_DEPLOY_ENABLED" not in workflow
    assert "deploy_edgeone:" not in workflow
    assert "npx edgeone" not in workflow
    assert "makers deploy" not in workflow
    assert not (ROOT / "deploy/edgeone").exists()
    assert "azurePackageTreeSha256" in workflow
    assert "edgeoneConfigSha256" in workflow
    assert "Download independently built EdgeOne evidence" in workflow
    assert "cmp \\" in workflow
    assert '"https://${host}/SHA256SUMS"' in workflow
    assert '"https://${host}/healthz"' in workflow
    assert '"https://${host}/product"' in workflow
    assert "verify_manifest_asset" in workflow
    assert "verify_manifest_file" in workflow
    assert '"product/index.html"' in workflow
    assert "verifiedManifestAssetTypes" in workflow
    assert "vars.EDGEONE_CN_PUBLIC_VERIFY_ENABLED == 'true'" in workflow
    assert "^x-robots-tag: noindex, nofollow" in workflow


def test_china_privacy_floor_is_enforced_across_release_workflows() -> None:
    workflow_paths = (
        ".github/workflows/deploy-backend.yml",
        ".github/workflows/deploy-frontend-appservice.yml",
        ".github/workflows/miniapp-publish.yml",
    )
    for relative_path in workflow_paths:
        workflow = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "scripts/cn_release_preflight.py" in workflow
        assert "--lane" in workflow
        assert "vars.CN_PRIVACY_FLOOR_SHA" in workflow
        assert "github.sha" in workflow
        assert "release-evidence/cn-release-preflight.json" in workflow
        assert "checks: read" in workflow
        assert "pull-requests: read" in workflow
        assert "statuses: read" in workflow

    validator = (ROOT / "scripts/cn_release_preflight.py").read_text(
        encoding="utf-8"
    )
    assert "^[0-9a-f]{40}$" in validator
    assert "merge-base" in validator
    assert "candidate is not reachable from protected main" in validator
    assert "backend-tests" in validator
    assert "frontend-quality" in validator
    assert "selective-review-policy" in validator
    assert "candidateExactMatchCount" in validator
    assert "verify_disabled_runtime" in validator
    assert "runtime processing switches do not match the inactive-CN contract" in validator
    assert "rules/branches/main" in validator
    assert "latest required check" in validator
    assert "not exactly registry-authorized" in validator
    assert "terms_digest" in validator
    assert "api_contract_version" in validator

    config = (
        ROOT / "docs/ops/config-and-secrets.md"
    ).read_text(encoding="utf-8")
    runbook = (
        ROOT / "docs/ops/tencent-frontend.md"
    ).read_text(encoding="utf-8")
    assert "CN_PRIVACY_FLOOR_SHA" in config
    assert "miniapp-2026.08.2" in runbook
    assert "CLIENT_PRIVACY_UPDATE_REQUIRED" not in runbook
    assert "final operator-approved" in runbook


def test_cn_privacy_contract_version_matches_both_clients() -> None:
    runtime_boundary = (
        ROOT / "api/china_client_boundary.py"
    ).read_text(encoding="utf-8")
    web_boundary = (
        ROOT / "web/src/lib/client-boundary.ts"
    ).read_text(encoding="utf-8")
    miniapp_client = (
        ROOT / "miniapp/utils/api-client.ts"
    ).read_text(encoding="utf-8")

    assert 'CN_PRIVACY_CONTRACT_VERSION = "cn-privacy-v2"' in runtime_boundary
    for client in (web_boundary, miniapp_client):
        assert "CN_PRIVACY_CONTRACT_VERSION = 'cn-privacy-v2'" in client
        assert "'X-Praxys-Api-Contract': CN_PRIVACY_CONTRACT_VERSION" in client
        assert "cn-privacy-v1" not in client


def test_cn_release_registry_example_uses_current_inactive_contract() -> None:
    config = (
        ROOT / "docs/ops/config-and-secrets.md"
    ).read_text(encoding="utf-8")
    lines = config.splitlines()
    start = lines.index(
        "cat > /tmp/praxys-cn-approved-releases.json <<'JSON'"
    ) + 1
    end = lines.index("JSON", start)
    registry = json.loads(chr(10).join(lines[start:end]))

    assert len(registry) == 2
    for release in registry:
        assert release["notice_version"] == "2026.08.4"
        assert release["terms_digest"] == (
            "sha256:ce863ba3531157c50775509c8a8061654d24868cafe0b7f22ede02ca60c65aa1"
        )
        assert release["api_contract_version"] == "cn-privacy-v2"
        assert release["source_commit"] == "<40-char-protected-main-sha>"

    normalized = " ".join(config.split())
    assert "processing must not be enabled until" in normalized
    assert (
        "Activation remains a separately reviewed human-authorized operation "
        "with no implemented repository procedure."
    ) in normalized


def test_china_operations_decision_stays_blocked_and_orders_release() -> None:
    relative_path = "docs/ops/odr-2026-08-26-cn-provider-topology.md"
    decision = (ROOT / relative_path).read_text(encoding="utf-8")
    normalized = " ".join(decision.split())

    assert (
        "**Status:** **PROPOSED — BLOCKED PENDING INDEPENDENT AND HUMAN REVIEW**"
        in decision
    )
    assert "**Production authority:** None." in decision
    assert "**Decision date:** Not decided" in decision
    assert (
        "**review_route:** Pending. No retained independent Decision Review "
        "Router artifact"
        in normalized
    )
    assert "**digest:** **PENDING HUMAN ACCEPTANCE.**" in decision
    assert "sha256:ea5b438a17c6b0931f9e03a81606a55893e193438742364b8597e3b6dee34f8f" in decision
    assert "sha256:858b1429ea3e90b307923752d783f0ba9bc2665f978ddb2ef9381ddeae4216ab" in decision
    assert (
        "This section defines required evidence; **it is not Release Evidence"
        in decision
    )

    ordered_stages = (
        "Stage 0 — Merge the complete privacy floor",
        "Stage 1 — Set `CN_PRIVACY_FLOOR_SHA` after merge",
        "Stage 2 — Establish the disabled backend baseline",
        "Stage 3 — Deploy updated `.run` and prepare the `.cn` artifact",
        "Stage 4 — Validate the registry and prepare the Miniapp",
        "Stage 5 — Future separately authorized activation and provider cutover",
    )
    positions = [decision.index(stage) for stage in ordered_stages]
    assert positions == sorted(positions)

    assert "praxys.cn`, `www.praxys.cn` | EdgeOne Makers" in decision
    assert "praxys.run`, `www.praxys.run` | Cloudflare Free" in decision
    assert "`api.praxys.run` | DNS-only" in decision
    assert "request headers are release identifiers, not cryptographic" in (
        normalized
    )
    assert "`CN_PRIVACY_FLOOR_SHA` is an ancestry floor" in decision
    assert "no not-yet-created provider ID or registry authorization" in normalized
    assert "then construct the separately reviewed exact registry entry" in normalized
    assert "version `2026.08.2` or newer" in decision
    assert "The repository workflow can upload but cannot unpublish" in decision
    assert "requires separate, explicit operator authorization" in decision
    assert "No public China rollout may proceed" in decision

    linked_docs = (
        "docs/ops/README.md",
        "docs/ops/tencent-frontend.md",
        "docs/ops/deploy.md",
        "docs/ops/config-and-secrets.md",
        "docs/ops/environment.md",
        "docs/ops/cn-personal-information-impact-assessment.md",
    )
    for linked_path in linked_docs:
        linked = (ROOT / linked_path).read_text(encoding="utf-8")
        assert "odr-2026-08-26-cn-provider-topology.md" in linked

    handbook = (ROOT / "docs/ops/README.md").read_text(encoding="utf-8")
    assert "| Approved regional target |" not in handbook


def test_backend_workflow_keeps_privacy_controls_literal_disabled() -> None:
    workflow = (
        ROOT / ".github/workflows/deploy-backend.yml"
    ).read_text(encoding="utf-8")
    runbook = (
        ROOT / "docs/ops/tencent-frontend.md"
    ).read_text(encoding="utf-8")

    for literal in (
        'PRAXYS_DISABLE_CN_PROCESSING="true"',
        'PRAXYS_DISABLE_BACKGROUND_AI="false"',
        'PRAXYS_ENABLE_FEEDBACK_PUBLICATION="false"',
        'PRAXYS_DISABLE_FEEDBACK_PUBLICATION="true"',
    ):
        assert literal in workflow
    assert "PRAXYS_ENABLE_BACKGROUND_AI" not in workflow
    for variable in (
        "vars.PRAXYS_DISABLE_CN_PROCESSING",
        "vars.PRAXYS_DISABLE_BACKGROUND_AI",
        "vars.PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
        "vars.PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
    ):
        assert variable not in workflow

    assert "china_release_validation" in workflow
    assert "China candidate validation requires PRAXYS_CN_APPROVED_RELEASES" in workflow
    assert "Verify exact non-secret CN runtime settings" in workflow
    assert "Exact readback failed for ${name}" in workflow
    assert "Verify exact disabled China CORS boundary" in workflow
    assert "Disabled Azure CORS inventory is not the exact filing-free set" in workflow
    assert "https://praxys-frontend.azurewebsites.net" in workflow
    assert "sort == ($expected | sort)" in workflow
    assert "corsOrigins" in workflow
    assert "registry_sha256" in workflow
    assert "api_contract_version" in workflow
    assert "Guarded final China processing enable" not in workflow
    assert "PRAXYS_DISABLE_CN_PROCESSING=false" not in workflow
    assert "az webapp cors add" not in workflow
    assert "all six `X-Praxys-*` request" in (
        ROOT / "docs/ops/odr-2026-08-26-cn-provider-topology.md"
    ).read_text(encoding="utf-8")
    assert "x-praxys-policy-digest" in runbook
    assert "x-praxys-api-contract" in runbook
    assert "PRAXYS_DISABLE_CN_PROCESSING=true" in runbook

def test_runbook_preserves_provider_and_data_boundaries() -> None:
    runbook = (ROOT / "docs/ops/tencent-frontend.md").read_text(encoding="utf-8")
    normalized = " ".join(runbook.split())

    assert "praxys.cn / www.praxys.cn -> EdgeOne Makers" in normalized
    assert "praxys.run / www.praxys.run -> Cloudflare Free" in normalized
    assert "api.praxys.run -> Azure App Service trainsight-app" in normalized
    assert "Keep `api.praxys.run` DNS-only." in normalized
    assert "Cloudflare Origin CA" in normalized
    assert "App Service managed certificate" in normalized
    assert "Full (strict)" in normalized
    assert "does not itself create a public data path" in normalized
    assert "may not expose Auto Deploy or Preview switches" in normalized
    assert "deployment-history entry" in normalized
    assert "Do not use the ruleset admin bypass" in normalized
    assert "cross-border" in normalized
    assert (
        "Do not enable a geographic redirect during the initial cutover"
        in normalized
    )


def test_operations_docs_match_edgeone_git_and_monitoring_boundaries() -> None:
    deployment = (ROOT / "docs/deployment.md").read_text(encoding="utf-8")
    deploy_runbook = (ROOT / "docs/ops/deploy.md").read_text(encoding="utf-8")
    monitoring = (
        ROOT / "docs/ops/monitoring-and-alerts.md"
    ).read_text(encoding="utf-8")
    normalized_deployment = " ".join(deployment.split())
    normalized_monitoring = " ".join(monitoring.split())

    assert "protected EdgeOne environment" not in deployment
    assert "approve the protected environment" not in deploy_runbook
    assert "EdgeOne's repository-scoped, read-only native Git integration" in (
        normalized_deployment
    )
    assert "wt-praxys-run-apex" in monitoring
    assert "wt-praxys-cn-apex" in monitoring
    assert "wt-praxys-cn-www" in monitoring
    assert "praxys-feedback-ag" in monitoring
    assert (
        "Creating a missing pair moves it from `planned` to "
        "`provisioned-disabled`."
    ) in normalized_monitoring
    assert (
        "that reviewed transition is `provisioned-disabled` to `live`."
    ) in normalized_monitoring
    assert (
        "| `wt-praxys-run-apex` | live | `appi-trainsight` | "
        "`https://praxys.run/` |"
    ) in monitoring
    assert (
        "| `wt-praxys-cn-apex` | provisioned-disabled | "
        "`appi-trainsight` | `https://praxys.cn/` |"
    ) in monitoring
    assert (
        "| `wt-praxys-cn-www` | provisioned-disabled | "
        "`appi-trainsight` | `https://www.praxys.cn/` |"
    ) in monitoring
    assert "provisioned-disabled" in monitoring
    assert "WebtestLocationAvailabilityCriteria" in monitoring
    assert "--enabled false" in monitoring
    assert "enabled: false" in monitoring
    assert "enable_availability_pair wt-praxys-run-apex" in monitoring
    assert "if ! az monitor metrics alert update" in monitoring
    assert 'if ! az resource update --ids "$web_test_id"' in monitoring
    assert "--set properties.Enabled=true; then" in monitoring
    assert '--set properties.Enabled=false || rc=1' in monitoring
    assert '-n "$name" --enabled false || rc=1' in monitoring
    assert 'disable_availability_pair "$name" || true' in monitoring
    assert 'if ! test_enabled="$(az resource show' in monitoring
    assert '! alert_enabled="$(az monitor metrics alert show' in monitoring
    assert "--query properties.Enabled -o tsv" in monitoring
    assert "--query enabled -o tsv" in monitoring
    assert not any(
        line.startswith("provision_availability_pair wt-praxys-")
        for line in monitoring.splitlines()
    )
    for example in (
        "# provision_availability_pair wt-praxys-run-apex",
        "# provision_availability_pair wt-praxys-cn-apex",
        "# provision_availability_pair wt-praxys-cn-www",
    ):
        assert example in monitoring
    assert "native provider path is therefore blocked, not released" in deploy_runbook
    environment = (ROOT / "docs/ops/environment.md").read_text(encoding="utf-8")
    assert "both report `httpsOnly=true`" in environment
    assert "direct HTTP requests redirect to HTTPS" in environment



def test_cn_client_claims_and_artifacts_use_the_exact_full_source_sha() -> None:
    web_version = (ROOT / "web/src/lib/version.ts").read_text(encoding="utf-8")
    web_boundary = (ROOT / "web/src/lib/client-boundary.ts").read_text(encoding="utf-8")
    edgeone_build = (ROOT / "web/scripts/build-edgeone.mjs").read_text(encoding="utf-8")
    edgeone_prepare = (ROOT / "web/scripts/prepare-edgeone-artifact.mjs").read_text(encoding="utf-8")
    miniapp_workflow = (ROOT / ".github/workflows/miniapp-publish.yml").read_text(encoding="utf-8")
    runtime_boundary = (ROOT / "api/china_client_boundary.py").read_text(encoding="utf-8")

    assert "VITE_SOURCE_SHA" in web_version
    assert "X-Praxys-Source-Sha" in web_boundary
    assert "WEB_SOURCE_SHA" in web_boundary
    assert "VITE_SOURCE_SHA: sourceSha" in edgeone_build
    assert "^[0-9a-f]{40}$" in edgeone_prepare
    assert "$VERSION" in miniapp_workflow
    assert "${SOURCE_SHA}" in miniapp_workflow
    assert "release.source_commit == source_commit" in runtime_boundary


def test_release_metadata_is_never_interpolated_into_shell_source() -> None:
    for relative_path in (
        ".github/workflows/deploy-backend.yml",
        ".github/workflows/deploy-frontend-appservice.yml",
        ".github/workflows/miniapp-publish.yml",
    ):
        workflow = (ROOT / relative_path).read_text(encoding="utf-8")
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


def test_release_lane_matrix_preserves_run_and_fails_china_closed() -> None:
    backend = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    frontend = (ROOT / ".github/workflows/deploy-frontend-appservice.yml").read_text()
    miniapp = (ROOT / ".github/workflows/miniapp-publish.yml").read_text()
    edgeone_build = (ROOT / "web/scripts/build-edgeone.mjs").read_text()
    assert "lane=common" in backend
    assert "lane=china-client" in backend
    assert "--lane common" in frontend
    assert "--lane china-client" in miniapp
    assert "cn_release_preflight.py" in edgeone_build
    assert "--require-disabled-runtime" in edgeone_build
    assert "--prepare-unpublished-client" in edgeone_build
    assert "--skip-github-evidence" in edgeone_build
    assert "--require-disabled-runtime" in miniapp
    assert "EdgeOne privacy-floor preflight failed closed" in edgeone_build
    assert "if (!environment.GH_TOKEN)" not in edgeone_build
    assert "args.push(\"--skip-github-evidence\")" in edgeone_build
    assert "...process.env" not in edgeone_build
    assert "delete environment.GH_TOKEN" not in edgeone_build
    allowlist = edgeone_build[
        edgeone_build.index("for (const name of ["):
        edgeone_build.index("]) {", edgeone_build.index("for (const name of ["))
    ]
    for name in ("PATH", "CN_PRIVACY_FLOOR_SHA", "CN_PREFLIGHT_OUTPUT"):
        assert f"\"{name}\"" in allowlist
    for forbidden in ("GH_TOKEN", "GITHUB_TOKEN", "EDGEONE_API_TOKEN"):
        assert forbidden not in allowlist
    preflight = edgeone_build.index("runPrivacyFloorPreflight(environment)")
    build = edgeone_build.index("runWebBuild(environment)")
    assert preflight < build
    edgeone_stage = frontend[
        frontend.index("- name: Stage EdgeOne Git-build evidence"):
        frontend.index("- name: Upload Azure package")
    ]
    assert "GH_TOKEN:" not in edgeone_stage
    assert "prepared=false" in frontend
    assert "steps.edgeone_build.outputs.prepared == 'true'" in frontend


def test_backend_deploy_is_disabled_and_failure_safe() -> None:
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    disabled = workflow.index("Establish disabled China deployment state")
    deploy = workflow.index("Deploy to App Service")
    verified = workflow.index("Verify deployed backend cutover")
    recorded_restore = workflow.index("Restore and record disabled state")
    final_upload = workflow.index("Upload final backend CN deployment evidence")
    assert disabled < deploy < verified < recorded_restore < final_upload
    assert "PRAXYS_DISABLE_CN_PROCESSING=true" in workflow
    assert "PRAXYS_DISABLE_CN_PROCESSING=false" not in workflow
    assert "az webapp cors add" not in workflow
    assert "failure() && steps.azure_login.outcome == 'success'" in workflow
    assert "Finalize backend CN deployment evidence" in workflow
    assert "failed-before-azure-mutation" in workflow
    assert "failure-restore-unverified" in workflow
    assert "exact-disabled-match" in workflow
    assert "failureRestorationReadback" in workflow
    assert "corsOrigins" in workflow
    assert "chinaOrigins" not in workflow
    assert "      - 'alembic/**'" in workflow

def test_azure_oidc_deploys_are_protected_main_only_and_ids_are_validated() -> None:
    for relative in (".github/workflows/deploy-backend.yml", ".github/workflows/deploy-frontend-appservice.yml"):
        workflow = (ROOT / relative).read_text()
        assert "tags:" not in workflow
        assert "github.ref == 'refs/heads/main'" in workflow
        assert "Validate Azure deployment identifiers" in workflow
        assert "client-id: ${{ env.AZURE_CLIENT_ID }}" in workflow
        assert "AZURE_CLIENT_SECRET" not in workflow
        assert "publish-profile" not in workflow


def test_deploy_workflow_permissions_are_job_scoped() -> None:
    import yaml

    def load_workflow(relative_path: str) -> dict[str, object]:
        return yaml.load(
            (ROOT / relative_path).read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )

    frontend = load_workflow(
        ".github/workflows/deploy-frontend-appservice.yml"
    )
    backend = load_workflow(".github/workflows/deploy-backend.yml")

    assert "permissions" not in frontend
    assert frontend["jobs"]["test"]["permissions"] == {
        "contents": "read",
    }
    assert frontend["jobs"]["build"]["permissions"] == {
        "id-token": "write",
        "contents": "read",
        "checks": "read",
        "pull-requests": "read",
        "statuses": "read",
    }
    assert frontend["jobs"]["deploy_azure"]["permissions"] == {
        "id-token": "write",
        "contents": "read",
    }
    assert frontend["jobs"]["verify_edgeone_public"]["permissions"] == {
        "contents": "read",
    }

    assert "permissions" not in backend
    assert backend["jobs"]["test"]["permissions"] == {
        "contents": "read",
    }
    assert backend["jobs"]["deploy"]["permissions"] == {
        "id-token": "write",
        "contents": "read",
        "checks": "read",
        "pull-requests": "read",
        "statuses": "read",
        "actions": "read",
    }


def test_release_evidence_does_not_overclaim_github_history() -> None:
    validator = (ROOT / "scripts/cn_release_preflight.py").read_text()
    deploy = (ROOT / "docs/ops/deploy.md").read_text()
    for limitation in ("do not prove pre-merge completion timing", "do not prove absence of administrative bypass", "producer identity is not authenticated", "historical check semantics and permanent aggregation remain unresolved"):
        assert limitation in validator
    assert "Permanent aggregated Release Evidence storage" in deploy
    assert "blocked and not released" in deploy


def test_miniapp_upload_toolchain_is_lockfile_pinned() -> None:
    workflow = (ROOT / ".github/workflows/miniapp-publish.yml").read_text()
    package = json.loads((ROOT / "miniapp/package.json").read_text())

    assert "node-version: '24.11.0'" in workflow
    assert "npm install --no-save miniprogram-ci" not in workflow
    assert package["devDependencies"]["miniprogram-ci"] == "2.1.31"


def test_miniapp_package_excludes_development_only_metadata() -> None:
    config = json.loads((ROOT / "miniapp/project.config.json").read_text())
    workflow = (
        ROOT / ".github/workflows/miniapp-build.yml"
    ).read_text(encoding="utf-8")

    ignored = {
        (rule["type"], rule["value"])
        for rule in config["packOptions"]["ignore"]
    }
    expected = {
        ("file", "package-lock.json"),
        ("file", "package.json"),
        ("file", "tsconfig.json"),
        ("folder", "scripts"),
    }
    assert expected <= ignored
    for _, path in expected:
        assert f"--exclude='{path}'" in workflow
    assert "packaged-source proxy size" in workflow


def test_legal_bundle_changes_validate_and_publish_the_miniapp() -> None:
    miniapp_build = (
        ROOT / ".github/workflows/miniapp-build.yml"
    ).read_text(encoding="utf-8")
    miniapp_publish = (
        ROOT / ".github/workflows/miniapp-publish.yml"
    ).read_text(encoding="utf-8")
    premerge = (
        ROOT / ".github/workflows/ci-premerge.yml"
    ).read_text(encoding="utf-8")

    assert miniapp_build.count("web/src/lib/legal.ts") == 2
    assert miniapp_build.count("web/src/types/api.ts") == 2
    assert "web/src/lib/legal" in miniapp_publish
    assert "miniapp-legal:" in premerge
    assert "npm run typecheck" in premerge
    assert "types/api.ts" in premerge
    assert "utils/i18n-catalog.ts" in premerge
    assert "utils/legal.ts" in premerge
    assert "needs: [web-build, miniapp-legal, ui-quality]" in premerge


def test_backend_failure_restoration_reasserts_every_privacy_control() -> None:
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    start = workflow.index("- name: Restore and record disabled state after deployment failure")
    end = workflow.index("- name: Finalize backend CN deployment evidence", start)
    restoration = workflow[start:end]

    for literal in (
        "PRAXYS_DISABLE_CN_PROCESSING=true",
        "PRAXYS_DISABLE_BACKGROUND_AI=true",
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false",
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION=true",
    ):
        assert literal in restoration
    assert "read_setting" in restoration
    assert "failureRestorationReadback" in restoration
    assert "exact-disabled-match" in restoration
    assert "code rollback claim" in restoration


def test_key_vault_rsa_key_name_is_canonical_across_operations_docs() -> None:
    canonical = "trainsight-master-key"
    stale = "credential-encryption-key"
    for relative in (
        "docs/deployment.md",
        "docs/ops/README.md",
        "docs/ops/environment.md",
        "docs/ops/config-and-secrets.md",
        "docs/ops/disaster-recovery.md",
        "docs/ops/secret-rotation.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert canonical in text
        assert stale not in text
    vault = (ROOT / "db/crypto.py").read_text(encoding="utf-8")
    assert f'os.environ.get("KEY_VAULT_KEY_NAME", "{canonical}")' in vault


def test_proposed_trust_artifacts_bind_current_work_contract_without_approval() -> None:
    classification = "sha256:ea5b438a17c6b0931f9e03a81606a55893e193438742364b8597e3b6dee34f8f"
    route = "sha256:858b1429ea3e90b307923752d783f0ba9bc2665f978ddb2ef9381ddeae4216ab"
    for relative, pending_marker in (
        ("docs/ops/tdr-2026-08-26-cn-privacy-control-boundary.md", "Proposed"),
        (
            "docs/ops/cn-personal-information-impact-assessment.md",
            "PROPOSED — BLOCKED PENDING HUMAN LEGAL/PIPIA REVIEW",
        ),
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert classification in text
        assert route in text
        assert pending_marker in text
        assert "PENDING" in text.upper()


def test_miniapp_upload_evidence_is_initialized_and_retained_on_failure() -> None:
    workflow = (ROOT / ".github/workflows/miniapp-publish.yml").read_text(
        encoding="utf-8"
    )
    initialized = workflow.index("Initialize structured Miniapp upload evidence")
    uploaded = workflow.index("name: Upload to WeChat")
    finalized = workflow.index("Finalize structured Miniapp upload evidence")
    retained = workflow.index("name: Upload structured Miniapp evidence")
    assert initialized < uploaded < finalized < retained
    assert "id: upload_evidence_init" in workflow
    assert "id: wechat_upload" in workflow
    assert workflow.count(
        "always() && steps.upload_evidence_init.outcome == 'success'"
    ) == 2
    assert "pending-upload" in workflow
    assert "upload-failed" in workflow
    assert "upload-not-completed" in workflow
    assert "providerResponse: \"redacted\"" in workflow
    assert "Promotion and publication remain human-authorized provider actions." in workflow
