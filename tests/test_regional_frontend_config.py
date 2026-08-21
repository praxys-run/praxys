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
    evidence_finalize = workflow.index(
        "- name: Finalize frontend build evidence"
    )
    evidence_upload = workflow.index("- name: Upload frontend build evidence")

    assert azure_stage < china_build < china_copy
    assert azure_upload < edgeone_upload < evidence_finalize < evidence_upload
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
    assert "VITE_API_URL: 'https://api.praxys.run'" in build_script
    assert "VITE_APPINSIGHTS_CONNECTION_STRING: ''" in build_script
    assert "VITE_STATSIG_CLIENT_KEY: ''" in build_script
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
    assert "verifiedManifestAssetTypes" in workflow
    assert "vars.EDGEONE_CN_PUBLIC_VERIFY_ENABLED == 'true'" in workflow
    assert "^x-robots-tag: noindex, nofollow" in workflow


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
    assert "EdgeOne `Auto Deploy` off" in normalized
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

    assert "protected EdgeOne environment" not in deployment
    assert "approve the protected environment" not in deploy_runbook
    assert "EdgeOne's repository-scoped, read-only native Git integration" in (
        normalized_deployment
    )
    assert "wt-praxys-run-apex" in monitoring
    assert "wt-praxys-cn-apex" in monitoring
    assert "wt-praxys-cn-www" in monitoring
    assert "praxys-feedback-ag" in monitoring
    assert "A planned row becomes live" in monitoring
