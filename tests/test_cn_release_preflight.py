"""Focused tests for deterministic China release preflight."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import zipfile

import pytest

from api.china_client_boundary import (
    CN_PRIVACY_CONTRACT_VERSION,
    MINIMUM_MINIAPP_VERSION,
)
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from scripts import cn_release_preflight as preflight


def registry(release_id: str = "edgeone:deployment-123") -> str:
    source_commit = "a" * 40
    return json.dumps([{
        "channel": "cn-web",
        "client_version": source_commit[:12],
        "source_id": source_commit[:12],
        "source_commit": source_commit,
        "notice_version": TERMS_VERSION,
        "terms_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        "release_id": release_id,
    }])


def test_exact_sha_rejects_short_or_uppercase_values() -> None:
    assert preflight.exact_sha("candidate", "a" * 40) == "a" * 40
    with pytest.raises(ValueError, match="lowercase 40-character"):
        preflight.exact_sha("candidate", "a" * 12)
    with pytest.raises(ValueError, match="lowercase 40-character"):
        preflight.exact_sha("candidate", "A" * 40)


def test_source_miniapp_minimum_is_exact_calver() -> None:
    boundary = preflight.module_constants("api/china_client_boundary.py")
    assert boundary["MINIMUM_MINIAPP_VERSION"] == MINIMUM_MINIAPP_VERSION
    assert preflight.parse_calver(MINIMUM_MINIAPP_VERSION) == (2026, 8, 2)


def test_registry_validation_binds_current_contract_and_provider() -> None:
    releases, digest = preflight.validate_registry(registry(), disabled=True)
    assert releases[0]["source_commit"] == "a" * 40
    assert digest is not None and len(digest) == 64

    with pytest.raises(ValueError, match="provider ID"):
        preflight.validate_registry(registry("edgeone:bad\nid"), disabled=True)

    stale = json.loads(registry())
    stale[0]["notice_version"] = "2026.01.1"
    with pytest.raises(ValueError, match="notice version"):
        preflight.validate_registry(json.dumps(stale), disabled=True)


def _backend_deployment_evidence(
    candidate: str,
    floor: str,
    registry_digest: str,
    registry_count: int,
) -> dict[str, object]:
    registry_readback = {
        "checked": True,
        "exactBytesMatch": True,
        "entryCount": registry_count,
        "sha256": "sha256:" + registry_digest,
    }
    return {
        "schemaVersion": 1,
        "status": "validated",
        "workflowStatus": "success",
        "lane": "china-client",
        "chinaCapable": True,
        "candidateSha": candidate,
        "privacyFloorSha": floor,
        "releaseRegistry": {
            "sha256": registry_digest,
            "entryCount": registry_count,
        },
        "runtimeConfigurationReadback": {
            "status": "exact-match",
            "chinaCapable": True,
            "releaseRegistry": registry_readback,
        },
        "deployedRuntimeReadback": {
            "status": "exact-match",
            "chinaCapable": True,
            "deployedSourceSha": candidate,
            "readinessStatus": "ready",
            "postDeployConfiguration": {
                "checked": True,
                "status": "exact-match",
                "releaseRegistry": registry_readback,
            },
        },
    }


def _backend_evidence_archive(payload: dict[str, object]) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("cn-release-preflight.json", json.dumps(payload))
    return archive.getvalue()


def test_backend_validation_evidence_is_exact_and_digest_bound(monkeypatch) -> None:
    candidate = "a" * 40
    floor = "f" * 40
    registry_digest = "b" * 64
    payload = _backend_deployment_evidence(candidate, floor, registry_digest, 1)
    archive = _backend_evidence_archive(payload)
    digest = "sha256:" + hashlib.sha256(archive).hexdigest()

    monkeypatch.setenv("GITHUB_REPOSITORY", "praxys-run/praxys")
    monkeypatch.setenv("GH_TOKEN", "test-token")

    def fake_github_json(repository: str, path: str, token: str):
        assert repository == "praxys-run/praxys"
        assert token == "test-token"
        if path.startswith("actions/workflows/deploy-backend.yml/runs"):
            return {"workflow_runs": [{
                "id": 91,
                "run_attempt": 2,
                "head_sha": candidate,
                "event": "workflow_dispatch",
                "inputs": {"china_release_validation": "true"},
                "status": "completed",
                "conclusion": "success",
            }]}
        return {"artifacts": [{
            "id": 92,
            "name": "backend-cn-final-evidence-91-2",
            "expired": False,
            "digest": digest,
        }]}

    monkeypatch.setattr(preflight, "github_json", fake_github_json)
    monkeypatch.setattr(
        preflight,
        "github_artifact_bytes",
        lambda repository, artifact_id, token: archive,
    )

    result = preflight.verify_backend_validation_evidence(
        candidate,
        floor,
        registry_digest,
        1,
    )
    assert result == {
        "status": "exact-digest-bound-match",
        "workflowRunId": 91,
        "workflowRunAttempt": 2,
        "artifactId": 92,
        "artifactName": "backend-cn-final-evidence-91-2",
        "artifactDigest": digest,
    }

    monkeypatch.setattr(
        preflight,
        "github_artifact_bytes",
        lambda repository, artifact_id, token: archive + b"tampered",
    )
    with pytest.raises(ValueError, match="artifact digest"):
        preflight.verify_backend_validation_evidence(
            candidate,
            floor,
            registry_digest,
            1,
        )


def test_backend_validation_evidence_rejects_stale_candidate() -> None:
    payload = _backend_deployment_evidence(
        "a" * 40,
        "f" * 40,
        "b" * 64,
        1,
    )
    payload["candidateSha"] = "c" * 40

    with pytest.raises(ValueError, match="does not match the candidate"):
        preflight.validate_backend_deployment_evidence(
            payload,
            candidate="a" * 40,
            privacy_floor="f" * 40,
            registry_digest="b" * 64,
            registry_count=1,
        )


def test_empty_registry_is_allowed_only_while_processing_is_disabled() -> None:
    assert preflight.validate_registry("", disabled=True) == ([], None)
    with pytest.raises(ValueError, match="cannot be enabled"):
        preflight.validate_registry("", disabled=False)


def test_enabled_client_candidate_requires_exact_channel_registry_match() -> None:
    releases, _ = preflight.validate_registry(registry(), disabled=False)
    candidate = releases[0]["source_commit"]
    assert preflight.validate_candidate_authorization(
        releases,
        candidate,
        "cn-web",
        disabled=False,
        candidate_release_id="edgeone:deployment-123",
    ) == releases
    with pytest.raises(ValueError, match="not exactly registry-authorized"):
        preflight.validate_candidate_authorization(
            releases,
            "f" * 40,
            "cn-web",
            disabled=False,
            candidate_release_id="edgeone:deployment-123",
        )
    with pytest.raises(ValueError, match="not exactly registry-authorized"):
        preflight.validate_candidate_authorization(
            releases,
            "f" * 40,
            "cn-web",
            disabled=True,
            candidate_release_id="edgeone:deployment-123",
        )


def test_unpublished_edgeone_preparation_never_claims_authorization() -> None:
    preflight.validate_unpublished_preparation(
        "cn-web",
        disabled=True,
        candidate_release_id="",
    )
    with pytest.raises(ValueError, match="only for the China web client"):
        preflight.validate_unpublished_preparation(
            "wechat-miniapp",
            disabled=True,
            candidate_release_id="",
        )
    with pytest.raises(ValueError, match="remain disabled"):
        preflight.validate_unpublished_preparation(
            "cn-web",
            disabled=False,
            candidate_release_id="",
        )
    with pytest.raises(ValueError, match="cannot claim"):
        preflight.validate_unpublished_preparation(
            "cn-web",
            disabled=True,
            candidate_release_id="edgeone:deployment-123",
        )


def test_miniapp_candidate_version_must_exactly_match_registry() -> None:
    payload = json.loads(registry())
    payload[0].update({
        "channel": "wechat-miniapp",
        "client_version": "2026.08.2",
        "release_id": "wechat:robot-1:2026.08.2",
    })
    releases, _ = preflight.validate_registry(json.dumps(payload), disabled=True)
    candidate = releases[0]["source_commit"]

    assert preflight.validate_candidate_authorization(
        releases,
        candidate,
        "wechat-miniapp",
        disabled=True,
        candidate_version="2026.08.2",
        candidate_release_id="wechat:robot-1:2026.08.2",
    ) == releases
    with pytest.raises(ValueError, match="provider release ID is required"):
        preflight.validate_candidate_authorization(
            releases,
            candidate,
            "wechat-miniapp",
            disabled=True,
            candidate_version="2026.08.2",
        )
    with pytest.raises(ValueError, match="not exactly registry-authorized"):
        preflight.validate_candidate_authorization(
            releases,
            candidate,
            "wechat-miniapp",
            disabled=True,
            candidate_version="2026.08.2",
            candidate_release_id="wechat:robot-1:2026.08.3",
        )
    with pytest.raises(ValueError, match="not exactly registry-authorized"):
        preflight.validate_candidate_authorization(
            releases,
            candidate,
            "wechat-miniapp",
            disabled=True,
            candidate_version="2026.08.3",
            candidate_release_id="wechat:robot-1:2026.08.3",
        )


def test_miniapp_candidate_version_is_required_and_strict() -> None:
    payload = json.loads(registry())
    payload[0].update({
        "channel": "wechat-miniapp",
        "client_version": "2026.08.2",
        "release_id": "wechat:robot-1:2026.08.2",
    })
    releases, _ = preflight.validate_registry(json.dumps(payload), disabled=True)

    for invalid in ("", "2026.08.2-dev", "2026.13.1"):
        with pytest.raises(ValueError, match="exact CalVer"):
            preflight.validate_candidate_authorization(
                releases,
                releases[0]["source_commit"],
                "wechat-miniapp",
                disabled=True,
                candidate_version=invalid,
                candidate_release_id=f"wechat:robot-1:{invalid}",
            )


def miniapp_workflow_step(name: str) -> str:
    import yaml

    workflow = yaml.load(
        (preflight.ROOT / ".github/workflows/miniapp-publish.yml").read_text(
            encoding="utf-8"
        ),
        Loader=yaml.BaseLoader,
    )
    return next(
        step["run"]
        for step in workflow["jobs"]["publish"]["steps"]
        if step.get("name") == name
    )


def miniapp_meta_script() -> str:
    return miniapp_workflow_step("Decide robot + version")


def test_miniapp_main_gate_includes_release_version_source() -> None:
    gate = miniapp_workflow_step("Decide whether to publish")
    assert "api/china_client_boundary\\.py$" in gate


def run_miniapp_meta(tmp_path, ref: str, run_number: str = "42"):
    output = tmp_path / "github-output"
    completed = subprocess.run(
        ["bash", "-c", miniapp_meta_script()],
        cwd=preflight.ROOT,
        env={
            **os.environ,
            "GITHUB_SHA": "a" * 40,
            "GITHUB_REF": ref,
            "GITHUB_RUN_NUMBER": run_number,
            "GITHUB_OUTPUT": str(output),
            "MINIAPP_UTC_DATE": "2026.08.26",
        },
        capture_output=True,
        text=True,
    )
    values = {}
    if output.exists():
        values = dict(
            line.split("=", 1)
            for line in output.read_text(encoding="utf-8").splitlines()
        )
    return completed, values


def test_miniapp_workflow_keeps_release_and_dev_versions_distinct(
    tmp_path,
) -> None:
    main, main_values = run_miniapp_meta(tmp_path, "refs/heads/main")
    assert main.returncode == 0, main.stderr
    assert main_values == {
        "robot": "5",
        "lane": "main",
        "version": "2026.08.26.42-aaaaaaa",
        "desc": "main aaaaaaa",
        "provider_locator": (
            "wechat:robot-5:2026.08.26.42-aaaaaaa"
        ),
    }

    tag, tag_values = run_miniapp_meta(
        tmp_path, "refs/tags/miniapp-2026.08.2"
    )
    assert tag.returncode == 0, tag.stderr
    assert tag_values == {
        "robot": "1",
        "lane": "release",
        "version": "2026.08.2",
        "desc": "release 2026.08.2 (aaaaaaa)",
        "provider_locator": "wechat:robot-1:2026.08.2",
    }


def test_miniapp_workflow_rejects_nonmatching_tags_and_unsafe_dev_refs(
    tmp_path,
) -> None:
    for ref in (
        "refs/tags/miniapp-2026.13.1",
        "refs/heads/feature/unsafe",
    ):
        completed, values = run_miniapp_meta(tmp_path, ref)
        assert completed.returncode != 0
        assert values == {}

    invalid_run, values = run_miniapp_meta(
        tmp_path, "refs/heads/main", run_number="01"
    )
    assert invalid_run.returncode != 0
    assert values == {}


def test_latest_record_uses_failure_instead_of_historical_success() -> None:
    records = [
        {"id": 1, "state": "success", "updated_at": "2026-08-26T00:01:00Z"},
        {"id": 2, "state": "failure", "updated_at": "2026-08-26T00:02:00Z"},
    ]
    assert preflight.latest_record(records)["state"] == "failure"


def test_github_evidence_is_bound_to_candidate_and_reviewed_head(monkeypatch) -> None:
    candidate = "a" * 40
    head = "b" * 40
    monkeypatch.setenv("GITHUB_REPOSITORY", "praxys-run/praxys")
    monkeypatch.setenv("GH_TOKEN", "test-token")

    def fake_github_json(repository: str, path: str, token: str):
        assert repository == "praxys-run/praxys"
        assert token == "test-token"
        if path == "rules/branches/main?per_page=100":
            return [
                {"ruleset_id": 1, "type": "pull_request"},
                {"ruleset_id": 1, "type": "required_status_checks", "parameters": {"required_status_checks": [
                    {"context": "backend-tests"},
                    {"context": "frontend-quality"},
                    {"context": "selective-review-policy"},
                ]}},
            ]
        if path.startswith("commits/") and path.endswith("/pulls?per_page=100"):
            return [{
                "number": 42,
                "merged_at": "2026-08-26T00:00:00Z",
                "merge_commit_sha": candidate,
                "base": {"ref": "main"},
                "head": {"sha": head},
            }]
        if path.endswith("/check-runs?per_page=100"):
            return {"check_runs": [
                {"name": name, "id": index, "status": "completed", "conclusion": "success", "completed_at": "2026-08-26T00:01:00Z", "html_url": f"https://example.test/{index}"}
                for index, name in enumerate(preflight.REQUIRED_CHECKS, start=1)
            ]}
        return {"statuses": [{"context": preflight.REQUIRED_STATUS, "state": "success", "target_url": "https://example.test/status"}]}

    monkeypatch.setattr(preflight, "github_json", fake_github_json)
    evidence = preflight.verify_github(candidate)
    assert evidence["branchProtection"]["pullRequestRequired"] is True
    assert evidence["pullRequest"] == 42
    assert evidence["reviewedHeadSha"] == head
    assert [item["name"] for item in evidence["requiredChecks"]] == list(preflight.REQUIRED_CHECKS)



def test_latest_required_check_failure_cannot_be_hidden_by_old_success(
    monkeypatch,
) -> None:
    candidate = "c" * 40
    head = "d" * 40
    monkeypatch.setenv("GITHUB_REPOSITORY", "praxys-run/praxys")
    monkeypatch.setenv("GH_TOKEN", "test-token")

    def fake_github_json(repository: str, path: str, token: str):
        if path == "rules/branches/main?per_page=100":
            return [
                {"ruleset_id": 1, "type": "pull_request"},
                {"ruleset_id": 1, "type": "required_status_checks", "parameters": {"required_status_checks": [
                    {"context": "backend-tests"},
                    {"context": "frontend-quality"},
                    {"context": "selective-review-policy"},
                ]}},
            ]
        if path.endswith("/pulls?per_page=100"):
            return [{"number": 7, "merged_at": "2026-08-26T00:00:00Z", "merge_commit_sha": candidate, "base": {"ref": "main"}, "head": {"sha": head}}]
        if path.endswith("/check-runs?per_page=100"):
            return {"check_runs": [
                {"name": "backend-tests", "id": 1, "status": "completed", "conclusion": "success", "completed_at": "2026-08-26T00:01:00Z"},
                {"name": "backend-tests", "id": 2, "status": "completed", "conclusion": "failure", "completed_at": "2026-08-26T00:02:00Z"},
                {"name": "frontend-quality", "id": 3, "status": "completed", "conclusion": "success", "completed_at": "2026-08-26T00:02:00Z"},
            ]}
        return {"statuses": [{"context": "selective-review-policy", "state": "success", "updated_at": "2026-08-26T00:02:00Z"}]}

    monkeypatch.setattr(preflight, "github_json", fake_github_json)
    with pytest.raises(ValueError, match="latest required check backend-tests"):
        preflight.verify_github(candidate)


def test_github_request_uses_token_only_at_request_boundary(
    monkeypatch, capsys,
) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return io.BytesIO(b"{}")

    monkeypatch.setattr(preflight, "urlopen", fake_urlopen)
    assert preflight.github_json("praxys-run/praxys", "commits/test", "boundary-token") == {}
    assert captured == {
        "authorization": "Bear" + "er " + "boundary-" + "token",
        "timeout": 20,
    }
    output = capsys.readouterr()
    assert "boundary-token" not in output.out
    assert "boundary-token" not in output.err


def test_registry_rejects_source_commit_before_normalization() -> None:
    for invalid in ("A" * 40, "a" * 39, " " + ("a" * 40)):
        payload = json.loads(registry())
        payload[0]["source_commit"] = invalid
        with pytest.raises(ValueError, match="release (source_commit|registry values)"):
            preflight.validate_registry(json.dumps(payload), disabled=True)


def test_lane_matrix_keeps_common_provenance_independent_of_china_policy(
    monkeypatch, tmp_path,
) -> None:
    candidate = "a" * 40
    monkeypatch.setenv("CN_CANDIDATE_SHA", candidate)
    monkeypatch.delenv("CN_PRIVACY_FLOOR_SHA", raising=False)
    monkeypatch.delenv("PRAXYS_CN_APPROVED_RELEASES", raising=False)
    monkeypatch.setattr(
        preflight,
        "git",
        lambda *args: candidate if args == ("rev-parse", "HEAD") else "",
    )

    class Result:
        returncode = 0

    monkeypatch.setattr(preflight.subprocess, "run", lambda *args, **kwargs: Result())
    common_output = tmp_path / "common.json"
    monkeypatch.setattr(
        preflight.sys,
        "argv",
        ["cn_release_preflight.py", "--lane", "common", "--skip-github-evidence", "--output", str(common_output)],
    )
    assert preflight.main() == 0
    evidence = json.loads(common_output.read_text())
    assert evidence["chinaCapable"] is False
    assert "privacyFloorSha" not in evidence
    assert evidence["provenance"]["compatibilityEstablishedByAncestry"] is False

    china_output = tmp_path / "china.json"
    monkeypatch.setattr(
        preflight.sys,
        "argv",
        ["cn_release_preflight.py", "--lane", "china-client", "--skip-github-evidence", "--output", str(china_output)],
    )
    assert preflight.main() == 1
    assert not china_output.exists()


def test_disabled_runtime_readback_is_exact_and_fail_closed(monkeypatch) -> None:
    releases, digest = preflight.validate_registry(registry(), disabled=True)
    candidate = releases[0]["source_commit"]
    responses = {
        "/api/version": {
            "version": "2026.08.27.42-aaaaaaa",
            "source_sha": candidate,
        },
        "/api/health/ready": {
            "status": "ready",
            "china_processing": {
                "enabled": False,
                "disabled": True,
                "registry_configured": False,
                "approved_release_count": 0,
                "registry_sha256": None,
                "notice_version": TERMS_VERSION,
                "legal_digest": TERMS_CONTENT_DIGEST,
                "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
            },
            "optional_processing": {
                "background_ai_enabled": True,
                "background_ai_kill_switch": False,
                "feedback_publication_enabled": False,
                "feedback_publication_positive_enable": False,
                "feedback_publication_kill_switch": True,
            },
        },
    }
    monkeypatch.setattr(preflight, "http_json", responses.__getitem__)
    monkeypatch.setattr(preflight, "cors_allow_origin", lambda origin: None)

    evidence = preflight.verify_disabled_runtime(candidate, releases, digest)

    assert evidence["status"] == "exact-disabled-match"
    assert evidence["deployedSourceSha"] == candidate
    assert evidence["readinessStatus"] == "ready"
    assert evidence["registryEntryCount"] == 1
    ready = responses["/api/health/ready"]
    assert evidence["chinaProcessing"] == ready["china_processing"]
    assert evidence["backgroundAiAvailable"] is True
    assert evidence["backgroundAiKillSwitchActive"] is False
    assert evidence["feedbackPublicationDisabled"] is True
    assert "optionalProcessingDisabled" not in evidence
    assert evidence["optionalProcessing"] == ready["optional_processing"]
    responses["/api/health/ready"]["optional_processing"][
        "background_ai_kill_switch"
    ] = True
    with pytest.raises(ValueError, match="inactive-CN contract"):
        preflight.verify_disabled_runtime(candidate, releases, digest)


def test_registry_provider_ids_and_versions_are_channel_exact() -> None:
    wrong_provider = json.loads(registry())
    wrong_provider[0]["release_id"] = "wechat:release-1"
    with pytest.raises(ValueError, match="does not match its channel"):
        preflight.validate_registry(json.dumps(wrong_provider), disabled=True)

    miniapp = json.loads(registry())
    miniapp[0].update({
        "channel": "wechat-miniapp",
        "client_version": "2026.08.2-dev",
        "release_id": "wechat:robot-1:2026.08.2-dev",
    })
    with pytest.raises(ValueError, match="Miniapp release identity"):
        preflight.validate_registry(json.dumps(miniapp), disabled=True)

    wrong_locator = json.loads(registry())
    wrong_locator[0].update({
        "channel": "wechat-miniapp",
        "client_version": "2026.08.2",
        "release_id": "wechat:robot-5:2026.08.2",
    })
    with pytest.raises(ValueError, match="bind robot 1 and version"):
        preflight.validate_registry(
            json.dumps(wrong_locator),
            disabled=True,
        )


def test_registry_rejects_duplicate_provider_release_ids() -> None:
    payload = json.loads(registry())
    duplicate = dict(payload[0])
    duplicate.update({
        "client_version": "bbbbbbbbbbbb",
        "source_id": "bbbbbbbbbbbb",
        "source_commit": "b" * 40,
    })
    payload.append(duplicate)

    with pytest.raises(ValueError, match="provider release ID is duplicated"):
        preflight.validate_registry(json.dumps(payload), disabled=True)


def test_registry_rejects_coerced_extra_or_padded_provider_data() -> None:
    for mutate in (
        lambda item: item.update({"release_id": " edgeone:deployment-123"}),
        lambda item: item.update({"client_version": 20260801}),
        lambda item: item.update({"unexpected": "value"}),
    ):
        payload = json.loads(registry())
        mutate(payload[0])
        with pytest.raises(ValueError, match="release registry"):
            preflight.validate_registry(json.dumps(payload), disabled=True)


def test_fast_backend_deploy_restores_ai_before_exact_verification() -> None:
    import yaml

    workflow = yaml.load(
        (preflight.ROOT / ".github/workflows/deploy-backend.yml").read_text(
            encoding="utf-8"
        ),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["deploy"]["steps"]
    by_name = {step.get("name"): step for step in steps}
    names = [step.get("name") for step in steps]
    safe_name = "Establish disabled China deployment state"
    restore_name = "Restore ordinary AI availability for fast deploys"
    verify_name = "Verify exact non-secret CN runtime settings"

    assert (
        names.index(safe_name)
        < names.index(restore_name)
        < names.index(verify_name)
    )
    restore = by_name[restore_name]
    assert restore["if"] == "steps.mode.outputs.sync_config == 'false'"
    assert "PRAXYS_DISABLE_BACKGROUND_AI=false" in restore["run"]
    assert restore["run"].count("PRAXYS_DISABLE_BACKGROUND_AI") == 1
    for unchanged_control in (
        "PRAXYS_DISABLE_CN_PROCESSING",
        "PRAXYS_CN_APPROVED_RELEASES",
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
        "cors",
    ):
        assert unchanged_control not in restore["run"]

    failure_restore = by_name["Restore and record disabled state after deployment failure"]
    assert "PRAXYS_DISABLE_BACKGROUND_AI=true" in failure_restore["run"]


def test_backend_cutover_registry_is_limited_to_china_capable_lane(
    tmp_path,
) -> None:
    import yaml

    workflow = yaml.load(
        (preflight.ROOT / ".github/workflows/deploy-backend.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    step = next(
        item
        for item in workflow["jobs"]["deploy"]["steps"]
        if item.get("name") == "Verify deployed backend cutover"
    )
    setup = step["run"].split("expected_background_effective=false", 1)[0]
    env = {
        "PATH": os.environ["PATH"],
        "EXPECTED_CN_REGISTRY": "malformed-stale-registry",
        "EXPECTED_CN_DISABLED": "true",
        "EXPECTED_BACKGROUND_ENABLED": "false",
        "EXPECTED_BACKGROUND_DISABLED": "true",
        "EXPECTED_PUBLICATION_ENABLED": "false",
        "EXPECTED_PUBLICATION_DISABLED": "true",
    }

    ordinary = subprocess.run(
        ["bash", "-c", setup],
        cwd=tmp_path,
        env={**env, "CN_CAPABLE": "false"},
        capture_output=True,
        text=True,
    )
    assert ordinary.returncode == 0, ordinary.stderr

    china_capable = subprocess.run(
        ["bash", "-c", setup],
        cwd=tmp_path,
        env={**env, "CN_CAPABLE": "true"},
        capture_output=True,
        text=True,
    )
    assert china_capable.returncode != 0

    workflow_text = (
        preflight.ROOT / ".github/workflows/deploy-backend.yml"
    ).read_text()
    assert "runtimeConfigurationReadback" in workflow_text
    assert "deployedRuntimeReadback" in step["run"]
    assert "postDeployConfiguration" in step["run"]
    assert "az webapp config appsettings list" in step["run"]
    assert "Post-deploy registry bytes do not exactly match" in step["run"]
    assert "Post-deploy .cn CORS denial is not exact" in step["run"]
    assert "exactBytesMatch" in step["run"]
    assert "entryCount" in step["run"]
    assert "registrySha" in step["run"]
    miniapp_workflow = (
        preflight.ROOT / ".github/workflows/miniapp-publish.yml"
    ).read_text()
    assert "CN_CANDIDATE_VERSION: ${{ steps.meta.outputs.version }}" in miniapp_workflow
    assert "CN_CANDIDATE_RELEASE_ID: ${{ steps.meta.outputs.provider_locator }}" in miniapp_workflow
    assert miniapp_workflow.index("Decide robot + version") < miniapp_workflow.index(
        "Validate frozen CN release candidate"
    )
    assert "--require-backend-validation-evidence" in miniapp_workflow
    assert "actions: read" in miniapp_workflow



def test_azure_deployment_identifier_validation_matches_provider_boundaries(
    tmp_path,
) -> None:
    import yaml

    workflow_paths = (
        ".github/workflows/deploy-backend.yml",
        ".github/workflows/deploy-frontend-appservice.yml",
    )
    validation_steps: list[tuple[str, str]] = []
    for relative_path in workflow_paths:
        workflow = yaml.load(
            (preflight.ROOT / relative_path).read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                if step.get("name") == "Validate Azure deployment identifiers":
                    validation_steps.append((relative_path, step["run"]))

    assert len(validation_steps) == 3
    normalized_steps = {
        script.replace("AZURE_BACKEND_APP_NAME", "AZURE_APP_NAME").replace(
            "AZURE_FRONTEND_APP_NAME", "AZURE_APP_NAME"
        )
        for _, script in validation_steps
    }
    assert len(normalized_steps) == 1

    valid_pairs = (
        ("trainsight-app", "rg-trainsight"),
        ("A0", "r"),
        ("A" + ("-" * 58) + "9", "." + ("r" * 88) + "-"),
    )
    invalid_pairs = (
        ("-app", "rg"),
        ("app-", "rg"),
        ("a", "rg"),
        ("a" * 61, "rg"),
        ("app", "+rg"),
        ("app", "rg."),
        ("app", ""),
        ("app", "r" * 91),
    )
    base_env = {
        "PATH": os.environ["PATH"],
        "AZURE_CLIENT_ID": "123e4567-e89b-42d3-a456-426614174000",
        "AZURE_TENANT_ID": "123e4567-e89b-42d3-a456-426614174001",
        "AZURE_SUBSCRIPTION_ID": "123e4567-e89b-42d3-a456-426614174002",
    }
    for relative_path, script in validation_steps:
        app_variable = (
            "AZURE_BACKEND_APP_NAME"
            if relative_path.endswith("deploy-backend.yml")
            else "AZURE_FRONTEND_APP_NAME"
        )
        for app_name, resource_group in valid_pairs:
            result = subprocess.run(
                ["bash", "-c", script],
                cwd=tmp_path,
                env={
                    **base_env,
                    app_variable: app_name,
                    "AZURE_RESOURCE_GROUP": resource_group,
                },
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, result.stderr
        for app_name, resource_group in invalid_pairs:
            result = subprocess.run(
                ["bash", "-c", script],
                cwd=tmp_path,
                env={
                    **base_env,
                    app_variable: app_name,
                    "AZURE_RESOURCE_GROUP": resource_group,
                },
                capture_output=True,
                text=True,
            )
            assert result.returncode != 0


def test_backend_post_deploy_registry_digest_uses_readback_bytes() -> None:
    import yaml

    workflow = yaml.load(
        (
            preflight.ROOT / ".github/workflows/deploy-backend.yml"
        ).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    step = next(
        item
        for item in workflow["jobs"]["deploy"]["steps"]
        if item.get("name") == "Verify deployed backend cutover"
    )
    script = step["run"]

    assert 'actual_registry_canonical="$(jq -cS . <<< "${actual_registry}")"' in script
    assert "printf '%s' \"${actual_registry_canonical}\"" in script
    assert '[[ "${actual_registry_sha}" != "${expected_registry_sha}" ]]' in script
    assert "Post-deploy registry SHA-256 does not exactly match" in script
    assert '--arg registrySha "${actual_registry_sha}"' in script
    assert '--arg registrySha "${expected_registry_sha}"' not in script

    digest_block = script[
        script.index('actual_registry_canonical="$(jq -cS .'):
        script.index('cors_origins="$(', script.index('actual_registry_canonical='))
    ]
    simulation = f"verify_digest() {{\n{digest_block}\n}}\nverify_digest"
    _, expected_digest = preflight.validate_registry(registry(), disabled=True)
    assert expected_digest is not None
    environment = {
        "PATH": os.environ["PATH"],
        "actual_registry": registry(),
        "expected_registry_sha": f"sha256:{expected_digest}",
    }
    matching = subprocess.run(
        ["bash", "-c", simulation],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert matching.returncode == 0, matching.stderr

    mismatch = subprocess.run(
        ["bash", "-c", simulation],
        env={**environment, "expected_registry_sha": "sha256:" + ("0" * 64)},
        capture_output=True,
        text=True,
    )
    assert mismatch.returncode != 0
    assert "Post-deploy registry SHA-256 does not exactly match" in mismatch.stdout
