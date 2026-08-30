"""Codex CLI and Copilot CLI runtime-adapter parity contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from analysis.agent_runtime_parity import (
    AgentRuntimeParity,
    filtered_command_environment,
    load_runtime_parity_config,
    validate_static_runtime_parity,
)


ROOT = Path(__file__).resolve().parents[1]


def _copy_runtime_fixture(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    shutil.copytree(
        ROOT,
        repository,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
        ),
    )
    return repository


def _load_fixture_config(repository: Path) -> AgentRuntimeParity:
    return load_runtime_parity_config(
        repository / "config" / "agent-runtime-parity.json"
    )


def test_static_runtime_parity_matches_canonical_control_plane() -> None:
    config = load_runtime_parity_config()

    assert config.status == "implementation-candidate"
    assert validate_static_runtime_parity(config) == []
    assert config.approval.subject_digest == (
        "sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc"
    )
    assert config.approval.proposal_digest == (
        "sha256:47a829962a21e17833feac0c3473ecb749c7b7e0ce4bff3aa2611ee1a92de8cd"
    )
    assert config.approved_work_contract.classification_digest == (
        "sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd"
    )
    assert config.approved_work_contract.route_digest == (
        "sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2"
    )
    assert config.codex_adapter.credentials_in_repository is False
    assert config.codex_adapter.separate_worktree_per_concurrent_task is True


def test_codex_adapter_has_bounded_roles_tools_and_environment() -> None:
    config = load_runtime_parity_config()
    adapters = {adapter.id: adapter for adapter in config.agent_adapters}

    assert {adapter.id for adapter in config.agent_adapters} >= {
        "praxys-orchestrator",
        "work-router",
        "decision-review-router",
        "praxys-change-loop",
        "engineering",
        "quality",
        "trust",
    }
    assert [
        adapter.id
        for adapter in config.agent_adapters
        if adapter.write_scope == "implementation"
    ] == ["engineering"]
    for adapter_id in (
        "praxys-orchestrator",
        "work-router",
        "decision-review-router",
        "praxys-change-loop",
        "quality",
        "trust",
    ):
        assert adapters[adapter_id].sandbox_mode == "read-only"
        assert adapters[adapter_id].write_scope == "none"
    assert set(config.portable_mcp_servers) == {
        "chrome-devtools",
        "praxys-local",
    }
    assert set(config.excluded_mcp_servers) == {
        "azure-mcp",
        "statsig",
        "praxys-dev-test",
    }
    for server in config.portable_mcp_servers.values():
        assert "*" not in server.enabled_tools
    assert {
        "--headless",
        "--isolated",
        "--redact-network-headers",
    } <= set(config.portable_mcp_servers["chrome-devtools"].args)
    assert {
        "AWS_*",
        "AZURE_*",
        "ARM_*",
        "OPENAI_*",
        "GITHUB_TOKEN",
        "DATABASE_URL",
        "GARMIN_*",
        "STRAVA_*",
    } <= set(config.credential_environment_excludes)


def _isolated_codex_environment(tmp_path: Path) -> dict[str, str]:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects."{ROOT.as_posix()}"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    environment = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "NO_COLOR")
        if name in os.environ
    }
    environment["CODEX_HOME"] = str(codex_home)
    return environment


def test_codex_native_cli_loads_project_mcp_projection(tmp_path: Path) -> None:
    if shutil.which("codex") is None:
        pytest.skip("Codex CLI is not installed in this test environment")
    completed = subprocess.run(
        ["codex", "mcp", "list", "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=_isolated_codex_environment(tmp_path),
        timeout=30,
    )
    servers = {
        server["name"]: server
        for server in json.loads(completed.stdout)
    }

    for server_id in ("chrome-devtools", "praxys-local"):
        assert servers[server_id]["enabled"] is False
        assert servers[server_id]["transport"]["env_vars"] == []
    assert servers["chrome-devtools"]["transport"]["args"][1] == (
        "chrome-devtools-mcp@1.6.0"
    )
    assert servers["praxys-local"]["transport"]["args"] == [
        "scripts/run_praxys_mcp.cjs",
        "local",
    ]


def test_codex_native_cli_loads_agents_hooks_and_skills(tmp_path: Path) -> None:
    if shutil.which("codex") is None:
        pytest.skip("Codex CLI is not installed in this test environment")
    completed = subprocess.run(
        ["codex", "doctor", "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=_isolated_codex_environment(tmp_path),
        timeout=30,
    )
    report = json.loads(completed.stdout)
    details = report["checks"]["config.load"]["details"]

    assert details["config.toml parse"] == "ok"
    assert details["mcp servers"] == "2"
    assert details.get("startup warnings", "0") == "0"
    assert details.get("startup warning hooks", "0") == "0"
    assert details.get("startup warning skills", "0") == "0"


def test_credential_environment_names_are_filtered_without_values() -> None:
    config = load_runtime_parity_config()
    environment = {
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "AZURE_CLIENT_ID": "not-a-real-value",
        "AWS_PROFILE": "not-a-real-value",
        "OPENAI_API_KEY": "not-a-real-value",
        "DATABASE_URL": "not-a-real-value",
        "GARMIN_PASSWORD": "not-a-real-value",
        "CUSTOM_SECRET": "not-a-real-value",
        "COPILOT_ASSIGN_TOKEN": "not-a-real-value",
    }

    filtered = filtered_command_environment(environment, config)

    assert filtered == {"PATH": "/usr/bin", "LANG": "C.UTF-8"}


def test_subject_digest_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    subject = repository / "docs/dev/codex-copilot-runtime-parity-decision-v1.json"
    subject.write_text(
        subject.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "approved decision subject digest differs from runtime contract" in errors


def test_contract_cannot_drop_approved_parity_requirement(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["required_parity"].pop()
    contract.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "required parity differs from approved subject" in errors


def test_contract_cannot_drift_from_approved_work_contract(
    tmp_path: Path,
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["approved_work_contract"]["route_digest"] = (
        "sha256:" + ("0" * 64)
    )
    contract.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Work Contract differs from approved subject" in errors


def test_contract_cannot_rebind_the_human_approval(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["approval"]["subject_digest"] = "sha256:" + ("0" * 64)
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValidationError,
        match="subject digest differs from the approved v1 subject",
    ):
        _load_fixture_config(repository)


def test_decision_review_policy_weakening_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    policy = repository / "config/agent-loop-policies.json"
    payload = json.loads(policy.read_text(encoding="utf-8"))
    payload["decision_autonomy"]["independence"][
        "executor_may_verify_own_high_risk_work"
    ] = True
    policy.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "decision-review independence policy was weakened" in errors


def test_approval_tokens_without_the_approved_proposal_fail_closed(
    tmp_path: Path,
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    proposal = (
        repository
        / "docs/dev/policy-change-proposal-codex-copilot-runtime-parity-v1.md"
    )
    proposal.write_text(
        "policy-change-proposal-codex-copilot-runtime-parity-v1\n"
        "sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc\n",
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "approved policy proposal digest differs from runtime contract" in errors


def test_codex_mcp_or_environment_widening_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    project_config = repository / ".codex/config.toml"
    project_config.write_text(
        project_config.read_text(encoding="utf-8").replace(
            '"AZURE_*" = "exclude"',
            '"AZURE_*" = "include"',
        )
        + '\n[mcp_servers.azure-mcp]\ncommand = "npx"\n',
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex project config differs from the runtime contract" in errors


def test_agent_reference_or_sandbox_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    engineering = repository / ".codex/agents/engineering.toml"
    engineering.write_text(
        engineering.read_text(encoding="utf-8")
        .replace(
            ".github/agents/engineering.agent.md",
            ".github/agents/trust.agent.md",
        )
        .replace(
            'sandbox_mode = "workspace-write"',
            'sandbox_mode = "read-only"',
        ),
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex agent adapter differs from contract: engineering" in errors


def test_read_only_role_scope_widening_is_rejected(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    trust = next(
        adapter
        for adapter in payload["agent_adapters"]
        if adapter["id"] == "trust"
    )
    trust["sandbox_mode"] = "workspace-write"
    trust["write_scope"] = "accepted-artifacts"
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError, match="trust must remain read-only"):
        _load_fixture_config(repository)


def test_agent_mcp_scope_must_match_canonical_manifest(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    product = next(
        adapter
        for adapter in payload["agent_adapters"]
        if adapter["id"] == "product"
    )
    product["mcp_servers"].append("chrome-devtools")
    contract.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert (
        "Codex agent MCP scope drifts from canonical manifest: product"
        in errors
    )


def test_hook_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    hook = repository / ".codex/hooks.json"
    payload = json.loads(hook.read_text(encoding="utf-8"))
    payload["hooks"]["PostToolUse"][0]["hooks"][0]["command"] = "true"
    hook.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex hook manifest differs from the runtime contract" in errors


def test_skill_alias_escape_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    alias = repository / ".agents/skills/ui-quality"
    alias.unlink()
    os.symlink("../../../../outside", alias)

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex skill target differs from contract: ui-quality" in errors
    assert "Codex skill target escapes or drifts: ui-quality" in errors


def test_legacy_copilot_drift_remains_a_failure(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    cloud = repository / "config/copilot-cloud-mcp.json"
    payload = json.loads(cloud.read_text(encoding="utf-8"))
    payload["mcpServers"].pop("praxys-local")
    cloud.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert any(error.startswith("legacy Copilot parity:") for error in errors)
