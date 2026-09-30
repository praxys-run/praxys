"""Compatibility boundaries between gh-aw sources, generated locks, and runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from scripts.compile_agentic_workflows import (
    INFO_STEP, WORKFLOWS, preserve_all_info_retention, preserve_info_retention, verify_compiler,
)


ROOT = Path(__file__).resolve().parents[1]
ACTION_SHA = "924af5fdc64061cfbf66fb584c8b07e2ac230c60"
DETECTOR_DIGESTS = (
    "b4ecda6a8f1ee09913c40b58e5e9d3337d2173618d41b1bfdef9207e4e7959b9",
    "f6260a0f9ad72bcb67c7af19c4ce262ca34e2c3d5ccbf912832a8bd277200904",
)


def workflow(name: str) -> tuple[str, dict]:
    """Load the actual generated workflow without YAML 1.1 boolean coercion."""
    source = (ROOT / ".github/workflows" / f"{name}.lock.yml").read_text()
    return source, yaml.load(source, Loader=yaml.BaseLoader)


@pytest.mark.parametrize("name", WORKFLOWS)
def test_compiler_runtime_and_manifest_are_coherent(name: str) -> None:
    source, document = workflow(name)
    metadata = json.loads(source.splitlines()[0].split(": ", 1)[1])
    manifest = json.loads(source.splitlines()[1].split(": ", 1)[1])
    assert metadata["compiler_version"] == "v0.89.21"
    assert metadata["strict"] is True
    assert metadata["agent_model"] == "gpt-5.4"
    pin = json.loads((ROOT / ".github/aw/actions-lock.json").read_text())
    assert pin["entries"]["github/gh-aw-actions/setup@v0.89.21"]["sha"] == ACTION_SHA
    runtime = next(a for a in manifest["actions"] if a["repo"] == "github/gh-aw-actions/setup")
    assert runtime["sha"] == ACTION_SHA and runtime["version"] == "v0.89.21"
    for job in document["jobs"].values():
        assert "copilot-requests" not in job.get("permissions", {})
        for step in job.get("steps", []):
            if step.get("uses", "").startswith("github/gh-aw-actions/setup@"):
                assert step["uses"] == "github/gh-aw-actions/setup@" + ACTION_SHA


@pytest.mark.parametrize("name", WORKFLOWS)
def test_gateway_identifier_is_wired_and_excluded_from_agent(name: str) -> None:
    source, document = workflow(name)
    steps = document["jobs"]["agent"]["steps"]
    gateway = next(s for s in steps if s.get("id") == "start-mcp-gateway")
    assert 'MCP_GATEWAY_AGENT_ID=$(openssl rand -base64 45' in gateway["run"]
    assert 'echo "::add-mask::${MCP_GATEWAY_AGENT_ID}"' in gateway["run"]
    assert '"agentId": "${MCP_GATEWAY_AGENT_ID}"' in gateway["run"]
    assert '"apiKey"' not in gateway["run"]
    execute = next(s for s in steps if s.get("name") == "Execute GitHub Copilot CLI")
    assert "--exclude-env MCP_GATEWAY_AGENT_ID" in execute["run"]
    assert "--exclude-env COPILOT_GITHUB_TOKEN" in execute["run"]
    assert "--exclude-env GH_TOKEN" in execute["run"]
    assert "GH_AW_NETWORK_ISOLATION: 'true'" in source


@pytest.mark.parametrize("name", WORKFLOWS)
def test_detector_requires_verified_install_and_preserves_warn_mode(name: str) -> None:
    _, document = workflow(name)
    steps = document["jobs"]["detection"]["steps"]
    install = next(s for s in steps if s.get("id") == "threat_detect_install")
    assert "install_threat_detect_binary.sh\" v0.5.2" in install["run"]
    for arch, digest in zip(("amd64", "arm64"), DETECTOR_DIGESTS):
        assert f"--sha256-{arch} {digest}" in install["run"]
    execute = next(s for s in steps if s.get("id") == "detection_agentic_execution")
    assert "steps.threat_detect_install.outcome == 'success'" in execute["if"]
    conclude = next(s for s in steps if s.get("id") == "detection_conclusion")
    assert conclude["env"]["THREAT_DETECT_INSTALL_OUTCOME"] == "${{ steps.threat_detect_install.outcome }}"
    assert conclude["env"]["GH_AW_DETECTION_CONTINUE_ON_ERROR"] == "true"


@pytest.mark.parametrize("name", WORKFLOWS)
def test_telemetry_routing_guard_and_info_lifetime_are_preserved(name: str) -> None:
    source, document = workflow(name)
    assert document["env"]["OTEL_EXPORTER_OTLP_ENDPOINT"] == "${{ vars.GH_AW_DEFAULT_OTLP_ENDPOINT }}"
    assert document["env"]["OTEL_EXPORTER_OTLP_HEADERS"] == "${{ secrets.GH_AW_DEFAULT_OTLP_HEADERS }}"
    assert document["env"]["GH_AW_OTLP_IF_MISSING"] == "ignore"
    assert "secrets.GH_AW_DEFAULT_OTLP_ENDPOINT" not in source
    assert json.loads(document["env"]["GH_AW_OTLP_ENDPOINTS"]) == [{
        "url": "${{ vars.GH_AW_DEFAULT_OTLP_ENDPOINT }}",
        "headers": "${{ secrets.GH_AW_DEFAULT_OTLP_HEADERS }}",
    }]
    steps = document["jobs"]["agent"]["steps"]
    guard_index = next(i for i, s in enumerate(steps) if s.get("name") == "Verify configured telemetry credentials")
    guard = steps[guard_index]
    assert guard["run"] == 'bash "${RUNNER_TEMP}/gh-aw/actions/check_otlp_default_credentials.sh"'
    assert guard.get("continue-on-error", "false") == "false"
    assert "if" not in guard
    for name_after_guard in ("Configure Git credentials", "Execute GitHub Copilot CLI"):
        index = next(i for i, s in enumerate(steps) if s.get("name") == name_after_guard)
        assert guard_index < index
        assert "if" not in steps[index]
    uploads = document["jobs"]["activation"]["steps"]
    for artifact in ("info", "activation"):
        step = next(s for s in uploads if s.get("with", {}).get("name") == artifact)
        assert step["with"]["retention-days"] == "1"


def test_info_override_changes_only_retention_and_rejects_contract_drift() -> None:
    original = "jobs:\n  activation:\n    steps:\n" + INFO_STEP
    expected = original + "          retention-days: 1\n"
    assert preserve_info_retention(original) == expected
    assert preserve_info_retention(expected) == expected
    for changed in (
        original.replace("name: info", "name: unrelated"),
        original + INFO_STEP,
        expected.replace("retention-days: 1", "retention-days: 7"),
        original.replace("aw_info.json", "different.json"),
        original + "          overwrite: true\n",
    ):
        with pytest.raises(ValueError):
            preserve_info_retention(changed)


def test_retention_validates_all_targets_before_writing(tmp_path: Path) -> None:
    original = "jobs:\n  activation:\n    steps:\n" + INFO_STEP
    paths = tuple(tmp_path / f"{name}.lock.yml" for name in WORKFLOWS)
    for path in paths:
        path.write_text(original)
    paths[-1].write_text(original.replace("aw_info.json", "different.json"))
    before = [path.read_bytes() for path in paths]
    with pytest.raises(ValueError):
        preserve_all_info_retention(paths)
    assert [path.read_bytes() for path in paths] == before


def test_unverified_compiler_is_rejected_before_execution(tmp_path: Path) -> None:
    compiler = tmp_path / "unverified"
    compiler.write_text("#!/bin/sh\nexit 0\n")
    with pytest.raises(ValueError, match="digest"):
        verify_compiler(compiler)


@pytest.mark.parametrize("name", WORKFLOWS)
def test_actual_guard_step_propagates_helper_failure(name: str, tmp_path: Path) -> None:
    _, document = workflow(name)
    guard = next(s for s in document["jobs"]["agent"]["steps"] if s.get("name") == "Verify configured telemetry credentials")
    actions = tmp_path / "gh-aw/actions"
    actions.mkdir(parents=True)
    (actions / "check_otlp_default_credentials.sh").write_text("#!/bin/bash\nexit 17\n")
    result = subprocess.run(
        ["bash", "-e", "-c", guard["run"]],
        env={**os.environ, "RUNNER_TEMP": str(tmp_path)},
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 17
