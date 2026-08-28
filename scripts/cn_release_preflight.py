#!/usr/bin/env python3
"""Validate a frozen China-capable release candidate without changing state."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parent.parent
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SOURCE_ID_RE = re.compile(r"^[0-9a-f]{12}$")
PROVIDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CALVER_RE = re.compile(r"^([0-9]{4})\.([0-9]{2})\.([0-9]{1,4})$")
API_VERSION_RE = re.compile(
    r"^(?:\d{4}\.(?:0[1-9]|1[0-2])\.\d{1,4}|"
    r"\d{4}\.(?:0[1-9]|1[0-2])\.(?:0[1-9]|[12]\d|3[01])"
    r"\.\d+-[0-9a-f]{7})$"
)
CN_API_BASE = "https://api.praxys.run"
REQUIRED_CHECKS = ("backend-tests", "frontend-quality")
REQUIRED_STATUS = "selective-review-policy"


def exact_sha(name: str, value: str) -> str:
    if SHA_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be one lowercase 40-character SHA")
    return value


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def module_constants(relative_path: str) -> dict[str, Any]:
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            try:
                values[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return values


def parse_calver(value: str) -> tuple[int, int, int] | None:
    match = CALVER_RE.fullmatch(value)
    if match is None:
        return None
    year, month, micro = (int(part) for part in match.groups())
    if not 1 <= month <= 12:
        return None
    return year, month, micro


def strict_bool(name: str, raw: str, default: bool) -> bool:
    if not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{name} must be true or false")


def validate_registry(raw: str, disabled: bool) -> tuple[list[dict[str, str]], str | None]:
    if not raw.strip():
        if not disabled:
            raise ValueError("China processing cannot be enabled without a release registry")
        return [], None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("release registry must be valid JSON") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("release registry must be a non-empty list")

    legal = module_constants("api/legal.py")
    boundary = module_constants("api/china_client_boundary.py")
    terms_version = legal.get("TERMS_VERSION")
    terms_digest = legal.get("TERMS_CONTENT_DIGEST")
    contract = boundary.get("CN_PRIVACY_CONTRACT_VERSION")
    minimum_version = boundary.get("MINIMUM_MINIAPP_VERSION")
    if not isinstance(minimum_version, str):
        raise ValueError("Miniapp minimum version is unreadable")
    minimum = parse_calver(minimum_version)
    if minimum is None:
        raise ValueError(
            "Miniapp minimum version must be an exact three-part CalVer"
        )
    if not all(isinstance(value, str) and value for value in (terms_version, terms_digest, contract)):
        raise ValueError("current privacy contract constants are unreadable")

    releases: list[dict[str, str]] = []
    identities: set[tuple[str, str, str]] = set()
    provider_release_ids: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("release registry entries must be objects")
        release_fields = {
            "channel", "client_version", "source_id", "source_commit",
            "notice_version", "terms_digest", "api_contract_version", "release_id",
        }
        if set(item) != release_fields:
            raise ValueError("release registry entry fields must exactly match schema")
        if not all(isinstance(item[name], str) for name in release_fields):
            raise ValueError("release registry values must be strings")
        if any(item[name] != item[name].strip() for name in release_fields):
            raise ValueError("release registry values must not contain surrounding whitespace")
        release = {name: item[name] for name in release_fields}
        raw_source_commit = release["source_commit"]
        if SHA_RE.fullmatch(raw_source_commit) is None:
            raise ValueError(
                "release source_commit must be one raw lowercase 40-character SHA"
            )
        channel = release["channel"]
        if channel not in {"cn-web", "wechat-miniapp"}:
            raise ValueError("release channel is invalid")
        if SOURCE_ID_RE.fullmatch(release["source_id"]) is None:
            raise ValueError("release source_id must be 12 lowercase hex characters")
        if SHA_RE.fullmatch(release["source_commit"]) is None:
            raise ValueError("release source_commit must be one lowercase 40-character SHA")
        if not release["source_commit"].startswith(release["source_id"]):
            raise ValueError("release source_id must prefix source_commit")
        release_id = release["release_id"]
        if PROVIDER_ID_RE.fullmatch(release_id) is None:
            raise ValueError("release provider ID is invalid")
        expected_prefix = "edgeone:" if channel == "cn-web" else "wechat:"
        if not release_id.startswith(expected_prefix) or len(release_id) == len(expected_prefix):
            raise ValueError("release provider ID does not match its channel")
        if release["notice_version"] != terms_version:
            raise ValueError("release notice version is not current")
        if release["terms_digest"] != str(terms_digest).lower():
            raise ValueError("release legal digest is not current")
        if release["api_contract_version"] != contract:
            raise ValueError("release API contract is not current")
        if channel == "cn-web":
            if release["client_version"] != release["source_id"]:
                raise ValueError("China web release identity is invalid")
        else:
            version = parse_calver(release["client_version"])
            if version is None or minimum is None or version < minimum:
                raise ValueError("Miniapp release identity is invalid")
            if (
                release_id
                != f"wechat:robot-1:{release['client_version']}"
            ):
                raise ValueError(
                    "Miniapp provider locator must bind robot 1 and version"
                )
        identity = (channel, release["client_version"], release["source_id"])
        if identity in identities:
            raise ValueError("release identity is duplicated")
        identities.add(identity)
        if release_id in provider_release_ids:
            raise ValueError("provider release ID is duplicated")
        provider_release_ids.add(release_id)
        releases.append(release)

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return releases, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_candidate_authorization(
    releases: list[dict[str, str]],
    candidate: str,
    channel: str,
    disabled: bool,
    candidate_version: str = "",
    candidate_release_id: str = "",
) -> list[dict[str, str]]:
    if channel not in {"", "cn-web", "wechat-miniapp"}:
        raise ValueError("candidate channel is invalid")
    if channel == "wechat-miniapp" and parse_calver(candidate_version) is None:
        raise ValueError("Miniapp candidate version must be an exact CalVer")
    if channel and not candidate_release_id:
        raise ValueError("candidate provider release ID is required")
    matches = [
        release for release in releases
        if release["source_commit"] == candidate
        and (not channel or release["channel"] == channel)
        and (
            channel != "wechat-miniapp"
            or release["client_version"] == candidate_version
        )
        and (
            not candidate_release_id
            or release["release_id"] == candidate_release_id
        )
    ]
    if not matches:
        raise ValueError(
            "China-capable candidate is not exactly registry-authorized"
        )
    return matches


def validate_unpublished_preparation(
    channel: str,
    disabled: bool,
    candidate_release_id: str,
) -> None:
    if channel != "cn-web":
        raise ValueError(
            "unpublished preparation is supported only for the China web client"
        )
    if not disabled:
        raise ValueError(
            "unpublished preparation requires China processing to remain disabled"
        )
    if candidate_release_id:
        raise ValueError(
            "unpublished preparation cannot claim a provider release ID"
        )


def http_json(path: str) -> dict[str, Any]:
    request = Request(
        CN_API_BASE + path,
        headers={"Cache-Control": "no-cache", "User-Agent": "praxys-cn-release-preflight"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise ValueError(f"runtime readback failed for {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"runtime readback for {path} must be an object")
    return payload


def cors_allow_origin(origin: str) -> str | None:
    request = Request(
        CN_API_BASE + "/api/health/ready",
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": (
                "x-praxys-client,x-praxys-client-version,"
                "x-praxys-source-sha,x-praxys-notice-version,"
                "x-praxys-policy-digest,x-praxys-api-contract"
            ),
            "Cache-Control": "no-cache",
            "User-Agent": "praxys-cn-release-preflight",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return response.headers.get("Access-Control-Allow-Origin")
    except HTTPError as exc:
        return exc.headers.get("Access-Control-Allow-Origin")
    except URLError as exc:
        raise ValueError(f"CORS readback failed for {origin}") from exc


def verify_disabled_runtime(
    candidate: str,
    releases: list[dict[str, str]],
    registry_digest: str | None,
    *,
    require_registry: bool = True,
) -> dict[str, Any]:
    if require_registry and (not releases or registry_digest is None):
        raise ValueError("disabled runtime readback requires an exact release registry")
    version = http_json("/api/version")
    ready = http_json("/api/health/ready")
    api_version = version.get("version")
    source_sha = version.get("source_sha")
    if not isinstance(api_version, str) or API_VERSION_RE.fullmatch(api_version) is None:
        raise ValueError("deployed API version is not an exact supported version")
    if source_sha != candidate:
        raise ValueError("deployed API source SHA does not equal the candidate")
    expected_china = {
        "enabled": False,
        "disabled": True,
        "registry_configured": False,
        "approved_release_count": 0,
        "registry_sha256": None,
    }
    china = ready.get("china_processing")
    if not isinstance(china, dict) or any(
        china.get(name) != value for name, value in expected_china.items()
    ):
        raise ValueError("runtime China settings do not exactly match the disabled candidate")
    legal = module_constants("api/legal.py")
    boundary = module_constants("api/china_client_boundary.py")
    if (
        china.get("notice_version") != legal.get("TERMS_VERSION")
        or china.get("legal_digest") != legal.get("TERMS_CONTENT_DIGEST")
        or china.get("api_contract_version") != boundary.get("CN_PRIVACY_CONTRACT_VERSION")
    ):
        raise ValueError("runtime privacy contract does not exactly match the candidate")
    optional = ready.get("optional_processing")
    expected_optional = {
        "background_ai_enabled": True,
        "background_ai_kill_switch": False,
        "feedback_publication_enabled": False,
        "feedback_publication_positive_enable": False,
        "feedback_publication_kill_switch": True,
    }
    if optional != expected_optional:
        raise ValueError("runtime processing switches do not match the inactive-CN contract")
    if ready.get("status") != "ready":
        raise ValueError("deployed API readiness is not ready")
    denied_origins = ("https://praxys.cn", "https://www.praxys.cn")
    for origin in denied_origins:
        if cors_allow_origin(origin) is not None:
            raise ValueError(f"disabled CORS boundary unexpectedly allows {origin}")
    compared_china = {
        **expected_china,
        "notice_version": china["notice_version"],
        "legal_digest": china["legal_digest"],
        "api_contract_version": china["api_contract_version"],
    }
    return {
        "status": "exact-disabled-match",
        "apiVersion": api_version,
        "deployedSourceSha": source_sha,
        "readinessStatus": ready["status"],
        "registryEntryCount": len(releases),
        "registrySha256": (
            "sha256:" + registry_digest
            if registry_digest is not None
            else None
        ),
        "chinaProcessingDisabled": True,
        "backgroundAiAvailable": expected_optional["background_ai_enabled"],
        "backgroundAiKillSwitchActive": expected_optional[
            "background_ai_kill_switch"
        ],
        "feedbackPublicationDisabled": not expected_optional[
            "feedback_publication_enabled"
        ],
        "chinaProcessing": compared_china,
        "optionalProcessing": expected_optional,
        "corsDeniedOrigins": list(denied_origins),
    }

def github_json(repository: str, path: str, token: str) -> Any:
    request = Request(
        f"https://api.github.com/repos/{repository}/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Author" + "ization": "Bear" + "er " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "praxys-cn-release-preflight",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError) as exc:
        raise ValueError(f"GitHub evidence request failed for {path}") from exc


class _ArtifactRedirectHandler(HTTPRedirectHandler):
    """Follow GitHub artifact redirects without forwarding its API token."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.headers.pop("Authorization", None)
            redirected.unredirected_hdrs.pop("Authorization", None)
        return redirected


def github_artifact_bytes(repository: str, artifact_id: int, token: str) -> bytes:
    request = Request(
        f"https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip",
        headers={
            "Accept": "application/vnd.github+json",
            "Author" + "ization": "Bear" + "er " + token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "praxys-cn-release-preflight",
        },
    )
    try:
        with build_opener(_ArtifactRedirectHandler()).open(
            request,
            timeout=20,
        ) as response:
            payload = response.read(5_000_001)
    except (HTTPError, URLError) as exc:
        raise ValueError("backend validation artifact download failed") from exc
    if len(payload) > 5_000_000:
        raise ValueError("backend validation artifact is too large")
    return payload


def validate_backend_deployment_evidence(
    payload: object,
    *,
    candidate: str,
    privacy_floor: str,
    registry_digest: str,
    registry_count: int,
) -> None:
    """Validate exact successful backend evidence for a Miniapp candidate."""

    if not isinstance(payload, dict):
        raise ValueError("backend validation evidence must be an object")
    release_registry = payload.get("releaseRegistry")
    runtime_config = payload.get("runtimeConfigurationReadback")
    deployed = payload.get("deployedRuntimeReadback")
    if not all(
        isinstance(value, dict)
        for value in (release_registry, runtime_config, deployed)
    ):
        raise ValueError("backend validation evidence is incomplete")
    expected_registry_digest = "sha256:" + registry_digest
    if (
        payload.get("schemaVersion") != 1
        or payload.get("status") != "validated"
        or payload.get("workflowStatus") != "success"
        or payload.get("lane") != "china-client"
        or payload.get("chinaCapable") is not True
        or payload.get("candidateSha") != candidate
        or payload.get("privacyFloorSha") != privacy_floor
        or release_registry.get("sha256") != registry_digest
        or release_registry.get("entryCount") != registry_count
    ):
        raise ValueError("backend validation evidence does not match the candidate")
    runtime_registry = runtime_config.get("releaseRegistry")
    post_config = deployed.get("postDeployConfiguration")
    post_registry = (
        post_config.get("releaseRegistry")
        if isinstance(post_config, dict)
        else None
    )
    if not isinstance(runtime_registry, dict) or not isinstance(post_registry, dict):
        raise ValueError("backend registry readback evidence is missing")
    for readback in (runtime_registry, post_registry):
        if (
            readback.get("checked") is not True
            or readback.get("exactBytesMatch") is not True
            or readback.get("entryCount") != registry_count
            or readback.get("sha256") != expected_registry_digest
        ):
            raise ValueError("backend registry readback does not exactly match")
    if (
        runtime_config.get("status") != "exact-match"
        or runtime_config.get("chinaCapable") is not True
        or deployed.get("status") != "exact-match"
        or deployed.get("chinaCapable") is not True
        or deployed.get("deployedSourceSha") != candidate
        or deployed.get("readinessStatus") != "ready"
        or post_config.get("checked") is not True
        or post_config.get("status") != "exact-match"
    ):
        raise ValueError("backend deployment readback does not exactly match")


def verify_backend_validation_evidence(
    candidate: str,
    privacy_floor: str,
    registry_digest: str,
    registry_count: int,
) -> dict[str, Any]:
    """Fetch and digest-bind exact backend validation evidence from GitHub."""

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None or not token:
        raise ValueError("GitHub repository and token are required for backend evidence")
    runs_payload = github_json(
        repository,
        "actions/workflows/deploy-backend.yml/runs"
        f"?head_sha={candidate}&status=success&per_page=100",
        token,
    )
    runs = runs_payload.get("workflow_runs", []) if isinstance(runs_payload, dict) else []
    candidates = [
        run for run in runs
        if isinstance(run, dict)
        and run.get("head_sha") == candidate
        and run.get("event") == "workflow_dispatch"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and isinstance(run.get("id"), int)
        and not isinstance(run.get("id"), bool)
        and isinstance(run.get("run_attempt"), int)
        and not isinstance(run.get("run_attempt"), bool)
    ]
    if not candidates:
        raise ValueError("no successful exact-SHA backend validation run exists")
    run = max(candidates, key=lambda item: int(item["id"]))
    run_id = int(run["id"])
    run_attempt = int(run["run_attempt"])
    artifacts_payload = github_json(
        repository,
        f"actions/runs/{run_id}/artifacts?per_page=100",
        token,
    )
    artifacts = artifacts_payload.get("artifacts", []) if isinstance(artifacts_payload, dict) else []
    expected_name = f"backend-cn-final-evidence-{run_id}-{run_attempt}"
    matches = [
        artifact for artifact in artifacts
        if isinstance(artifact, dict)
        and artifact.get("name") == expected_name
        and artifact.get("expired") is False
    ]
    if len(matches) != 1:
        raise ValueError("exact backend validation artifact is unavailable")
    artifact = matches[0]
    artifact_id = artifact.get("id")
    artifact_digest = artifact.get("digest")
    if (
        not isinstance(artifact_id, int)
        or isinstance(artifact_id, bool)
        or not isinstance(artifact_digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_digest) is None
    ):
        raise ValueError("backend validation artifact identity is invalid")
    archive = github_artifact_bytes(repository, artifact_id, token)
    actual_digest = "sha256:" + hashlib.sha256(archive).hexdigest()
    if actual_digest != artifact_digest:
        raise ValueError("backend validation artifact digest does not match")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            files = [item for item in bundle.infolist() if not item.is_dir()]
            if (
                len(files) != 1
                or Path(files[0].filename).name != "cn-release-preflight.json"
                or files[0].file_size > 1_000_000
            ):
                raise ValueError("backend validation artifact contents are invalid")
            payload = json.loads(bundle.read(files[0]))
    except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise ValueError("backend validation artifact is invalid") from exc
    validate_backend_deployment_evidence(
        payload,
        candidate=candidate,
        privacy_floor=privacy_floor,
        registry_digest=registry_digest,
        registry_count=registry_count,
    )
    return {
        "status": "exact-digest-bound-match",
        "workflowRunId": run_id,
        "workflowRunAttempt": run_attempt,
        "artifactId": artifact_id,
        "artifactName": expected_name,
        "artifactDigest": artifact_digest,
    }


def latest_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return max(
        records,
        key=lambda item: (
            str(item.get("updated_at") or item.get("completed_at") or item.get("started_at") or ""),
            int(item.get("id") or 0),
        ),
    )


def verify_github(candidate: str) -> dict[str, Any]:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None or not token:
        raise ValueError("GitHub repository and token are required for provenance evidence")
    branch_rules = github_json(repository, "rules/branches/main?per_page=100", token)
    required_contexts: set[str] = set()
    pull_request_required = False
    rule_ids: list[int] = []
    for rule in branch_rules:
        if isinstance(rule.get("ruleset_id"), int):
            rule_ids.append(rule["ruleset_id"])
        if rule.get("type") == "pull_request":
            pull_request_required = True
        if rule.get("type") == "required_status_checks":
            for check in rule.get("parameters", {}).get("required_status_checks", []):
                context = check.get("context")
                if isinstance(context, str):
                    required_contexts.add(context)
    expected_contexts = {*REQUIRED_CHECKS, REQUIRED_STATUS}
    if not pull_request_required or not expected_contexts.issubset(required_contexts):
        raise ValueError("protected main rules do not require the accepted pull-request checks")

    pulls = github_json(repository, f"commits/{candidate}/pulls?per_page=100", token)
    matches = [pr for pr in pulls if pr.get("merged_at") and pr.get("merge_commit_sha") == candidate and pr.get("base", {}).get("ref") == "main"]
    if len(matches) != 1:
        raise ValueError("candidate must map to exactly one merged main pull request")
    pull = matches[0]
    pull_number = pull.get("number")
    if not isinstance(pull_number, int) or isinstance(pull_number, bool) or pull_number <= 0:
        raise ValueError("pull request provider ID is invalid")
    head_sha = exact_sha("pull request head SHA", str(pull.get("head", {}).get("sha", "")))
    check_payload = github_json(repository, f"commits/{head_sha}/check-runs?per_page=100", token)
    runs = check_payload.get("check_runs", [])
    check_evidence = []
    for name in REQUIRED_CHECKS:
        run = latest_record([item for item in runs if item.get("name") == name])
        if run is None or run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ValueError(f"latest required check {name} is not successful for the reviewed head")
        check_id = run.get("id")
        if not isinstance(check_id, int) or isinstance(check_id, bool) or check_id <= 0:
            raise ValueError(f"required check {name} provider ID is invalid")
        check_evidence.append({"name": name, "id": check_id, "conclusion": "success", "url": run.get("html_url")})
    status_payload = github_json(repository, f"commits/{head_sha}/status?per_page=100", token)
    status = latest_record([item for item in status_payload.get("statuses", []) if item.get("context") == REQUIRED_STATUS])
    if status is None or status.get("state") != "success":
        raise ValueError(f"latest required status {REQUIRED_STATUS} is not successful for the reviewed head")
    return {
        "branchProtection": {"pullRequestRequired": True, "requiredContexts": sorted(required_contexts), "rulesetIds": sorted(set(rule_ids))},
        "pullRequest": pull_number,
        "reviewedHeadSha": head_sha,
        "requiredChecks": check_evidence,
        "requiredStatus": {"context": REQUIRED_STATUS, "state": "success", "url": status.get("target_url")},
        "evidenceLimitations": [
            "current API records do not prove pre-merge completion timing",
            "current API records do not prove absence of administrative bypass",
            "producer identity is not authenticated by this preflight",
            "historical check semantics and permanent aggregation remain unresolved",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--lane",
        choices=("common", "china-client"),
        default="china-client",
        help="Require China-only floor/registry policy only for China-capable lanes.",
    )
    parser.add_argument("--skip-github-evidence", action="store_true")
    parser.add_argument(
        "--require-backend-validation-evidence",
        action="store_true",
        help="Require exact digest-bound successful backend deployment evidence.",
    )
    parser.add_argument(
        "--require-disabled-runtime",
        action="store_true",
        help="Require exact deployed disabled settings, CORS, readiness, and SHA.",
    )
    parser.add_argument(
        "--prepare-unpublished-client",
        action="store_true",
        help=(
            "Validate a disabled China web artifact before a provider release "
            "ID exists. This never grants registry authorization."
        ),
    )
    args = parser.parse_args()
    try:
        if args.prepare_unpublished_client and (
            args.lane != "china-client" or not args.require_disabled_runtime
        ):
            raise ValueError(
                "unpublished preparation requires the China client lane "
                "and disabled-runtime readback"
            )
        if args.require_backend_validation_evidence and (
            args.lane != "china-client"
            or args.prepare_unpublished_client
            or not args.require_disabled_runtime
        ):
            raise ValueError(
                "backend validation evidence is valid only for a published "
                "China client candidate"
            )
        candidate = exact_sha("candidate SHA", os.environ.get("CN_CANDIDATE_SHA", ""))
        if exact_sha("checked out SHA", git("rev-parse", "HEAD")) != candidate:
            raise ValueError("checked out commit does not equal the frozen candidate SHA")
        git("cat-file", "-e", f"{candidate}^{{commit}}")
        if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", candidate, "origin/main"]).returncode != 0:
            raise ValueError("candidate is not reachable from protected main")

        china_capable = args.lane == "china-client"
        evidence: dict[str, Any] = {
            "schemaVersion": 1,
            "status": (
                "validated-unpublished-preparation"
                if args.prepare_unpublished_client
                else "validated"
            ),
            "lane": args.lane,
            "chinaCapable": china_capable,
            "candidateSha": candidate,
            "protectedMainRef": "origin/main",
            "provenance": {
                "candidateReachableFromProtectedMain": True,
                "compatibilityEstablishedByAncestry": False,
            },
        }
        if china_capable:
            floor = exact_sha("privacy floor SHA", os.environ.get("CN_PRIVACY_FLOOR_SHA", ""))
            if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", floor, candidate]).returncode != 0:
                raise ValueError("candidate predates the configured privacy floor")
            disabled = strict_bool("PRAXYS_DISABLE_CN_PROCESSING", os.environ.get("PRAXYS_DISABLE_CN_PROCESSING", ""), True)
            releases, registry_digest = validate_registry(os.environ.get("PRAXYS_CN_APPROVED_RELEASES", ""), disabled)
            if (
                not args.prepare_unpublished_client
                and (not releases or registry_digest is None)
            ):
                raise ValueError("China-capable lane requires an exact release registry")
            candidate_channel = os.environ.get("CN_CANDIDATE_CHANNEL", "").strip()
            candidate_version = os.environ.get("CN_CANDIDATE_VERSION", "").strip()
            candidate_release_id = os.environ.get(
                "CN_CANDIDATE_RELEASE_ID",
                "",
            ).strip()
            if args.prepare_unpublished_client:
                validate_unpublished_preparation(
                    candidate_channel,
                    disabled,
                    candidate_release_id,
                )
                candidate_matches: list[dict[str, str]] = []
            else:
                candidate_matches = validate_candidate_authorization(
                    releases,
                    candidate,
                    candidate_channel,
                    disabled,
                    candidate_version,
                    candidate_release_id,
                )
            legal = module_constants("api/legal.py")
            boundary = module_constants("api/china_client_boundary.py")
            evidence.update({
                "privacyFloorSha": floor,
                "privacyContract": {
                    "noticeVersion": legal["TERMS_VERSION"],
                    "legalDigest": legal["TERMS_CONTENT_DIGEST"],
                    "apiContractVersion": boundary["CN_PRIVACY_CONTRACT_VERSION"],
                },
                "releaseRegistry": {
                    "configured": bool(releases),
                    "entryCount": len(releases),
                    "sha256": registry_digest,
                    "candidateChannel": candidate_channel or None,
                    "candidateVersion": candidate_version or None,
                    "candidateProviderReleaseId": (
                        candidate_release_id or None
                    ),
                    "candidateExactMatchCount": len(candidate_matches),
                    "authorizationStatus": (
                        "not-authorized-unpublished-preparation"
                        if args.prepare_unpublished_client
                        else "exact-registry-match"
                    ),
                },
                "chinaProcessingDisabled": disabled,
            })
            if args.require_disabled_runtime:
                if not disabled:
                    raise ValueError("runtime readback is restricted to disabled processing")
                evidence["runtimeReadback"] = verify_disabled_runtime(
                    candidate,
                    releases,
                    registry_digest,
                    require_registry=not args.prepare_unpublished_client,
                )
            if args.require_backend_validation_evidence:
                if registry_digest is None:
                    raise ValueError("backend evidence requires an exact release registry")
                evidence["backendValidationEvidence"] = (
                    verify_backend_validation_evidence(
                        candidate,
                        floor,
                        registry_digest,
                        len(releases),
                    )
                )
        elif args.require_disabled_runtime:
            raise ValueError("runtime readback is valid only for a China-capable lane")
        if not args.skip_github_evidence:
            evidence["protectedMainEvidence"] = verify_github(candidate)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (KeyError, OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"CN release preflight failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
