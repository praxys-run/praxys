"""Local and Cloud Copilot execution-parity contracts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from analysis.copilot_execution_parity import (
    CopilotExecutionParity,
    load_execution_parity_config,
    read_live_cloud_configuration,
    validate_live_cloud_mcp,
    validate_static_execution_parity,
)


ROOT = Path(__file__).resolve().parents[1]


def test_portable_agents_use_only_common_capabilities() -> None:
    config = load_execution_parity_config()

    assert config.status == "active"
    assert config.orchestrator_agent_slug == "praxys-orchestrator"
    assert validate_static_execution_parity(config) == []
    assert {
        limitation.id
        for limitation in config.limitations
    } >= {
        "cloud-settings-external-state",
        "production-credentials-and-mutations",
        "wechat-desktop-simulator",
        "local-user-tool-extensions",
        "automatic-cloud-trigger-coverage",
        "default-branch-activation",
        "external-source-access",
    }


def test_local_and_cloud_mcp_tools_match_the_common_contract() -> None:
    config = load_execution_parity_config()
    local = json.loads((ROOT / config.local.mcp_config_path).read_text())
    cloud = json.loads((ROOT / config.cloud.mcp_config_path).read_text())

    assert set(cloud["mcpServers"]) == set(config.common_mcp_servers)
    for server_id, server in config.common_mcp_servers.items():
        expected = set(server.required_tools)
        assert set(local["mcpServers"][server_id]["tools"]) == expected
        assert set(cloud["mcpServers"][server_id]["tools"]) == expected


def test_live_cloud_config_allows_only_declared_environment_hint() -> None:
    config = load_execution_parity_config()
    cloud = json.loads(
        (ROOT / config.cloud.mcp_config_path).read_text(encoding="utf-8")
    )
    live_servers = json.loads(json.dumps(cloud["mcpServers"]))
    live_servers["praxys-local"]["env"] = {
        "PRAXYS_MCP_USE_CURRENT_PYTHON": "1"
    }
    payload = {"mcp_configuration": {"mcpServers": live_servers}}

    assert validate_live_cloud_mcp(payload, config) == []

    live_servers["praxys-local"]["env"]["UNDECLARED"] = "1"
    assert validate_live_cloud_mcp(payload, config) == [
        "live cloud praxys-local.env differs from allowed override"
    ]


def test_live_cloud_read_uses_the_versioned_github_api() -> None:
    completed = type(
        "Completed",
        (),
        {"stdout": '{"mcp_configuration": {"mcpServers": {}}}'},
    )()

    with patch(
        "analysis.copilot_execution_parity.subprocess.run",
        return_value=completed,
    ) as run:
        payload = read_live_cloud_configuration("praxys-run/praxys")

    assert payload == {"mcp_configuration": {"mcpServers": {}}}
    assert run.call_args.args[0] == [
        "gh",
        "api",
        "-H",
        "X-GitHub-Api-Version: 2026-03-10",
        "repos/praxys-run/praxys/copilot/cloud-agent/configuration",
    ]
    assert run.call_args.kwargs == {
        "check": True,
        "capture_output": True,
        "text": True,
    }


def test_parity_workflow_covers_static_and_live_drift() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "copilot-environment-parity.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert 'cron: "17 5 * * 1"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "pip install -r requirements.txt" in workflow
    assert "if: github.event_name != 'pull_request'" in workflow
    assert "needs: static-parity" in workflow
    assert "GH_TOKEN: ${{ secrets.COPILOT_ASSIGN_TOKEN }}" in workflow
    assert "COPILOT_ASSIGN_TOKEN is required" in workflow
    assert "--live" in workflow
    assert '--repo "$GITHUB_REPOSITORY"' in workflow


def test_parity_contract_rejects_paths_outside_the_repository() -> None:
    payload = json.loads(
        (
            ROOT / "config" / "copilot-execution-parity.json"
        ).read_text(encoding="utf-8")
    )
    payload["cloud"]["mcp_config_path"] = "../external.json"

    with pytest.raises(ValidationError, match="repository-relative"):
        CopilotExecutionParity.model_validate(payload)
