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
    CodexLocalMcpExtensions,
    CodexDispatchFacts,
    CodexTreeNode,
    evaluate_codex_cleanup,
    evaluate_codex_dispatch as _evaluate_codex_dispatch,
    filtered_command_environment,
    load_local_mcp_extensions,
    load_runtime_parity_config,
    validate_static_runtime_parity,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID = "ctr_" + ("1" * 32)
SLOT_ID = "slt_" + ("2" * 32)
REVISION_KEY = "git:" + ("3" * 40)


def _dispatch_facts(**overrides: object) -> CodexDispatchFacts:
    payload: dict[str, object] = {
        "dispatch_class": "write_serial",
        "coordinator_role": "praxys-change-loop",
        "contract_id": CONTRACT_ID,
        "slot_id": SLOT_ID,
        "revision_key": REVISION_KEY,
        "logical_work_state": "inactive",
        "target_role": "engineering",
    }
    payload.update(overrides)
    return CodexDispatchFacts.model_validate(payload)


def evaluate_codex_dispatch(facts: CodexDispatchFacts):
    return _evaluate_codex_dispatch(facts, load_runtime_parity_config())


@pytest.mark.parametrize(
    ("facts", "action", "reason_code"),
    [
        (
            _dispatch_facts(
                dispatch_class="read_parallel",
                target_role="quality",
                capacity_available=True,
                independent=True,
                reviewer_is_distinct_from_executor=True,
                reviewer_history="fresh",
            ),
            "spawn",
            "read_parallel_authorized",
        ),
        (
            _dispatch_facts(
                dispatch_class="read_parallel",
                target_role="quality",
                capacity_available=True,
                independent=False,
                reviewer_is_distinct_from_executor=True,
                reviewer_history="fresh",
            ),
            "reject",
            "read_parallel_requires_independent_read_only_work",
        ),
        (
            _dispatch_facts(
                dispatch_class="write_serial",
                target_role="engineering",
                capacity_available=True,
                prerequisites_complete=True,
                serial_peer_absence_confirmed=False,
            ),
            "queue",
            "prerequisite_or_serial_peer_active",
        ),
        (
            _dispatch_facts(
                dispatch_class="dependency_serial",
                target_role="product",
                capacity_available=True,
                prerequisites_complete=False,
                serial_peer_absence_confirmed=True,
            ),
            "queue",
            "prerequisite_or_serial_peer_active",
        ),
        (
            _dispatch_facts(
                dispatch_class="write_serial",
                target_role="engineering",
                capacity_available=True,
                prerequisites_complete=True,
                serial_peer_absence_confirmed=True,
            ),
            "spawn",
            "serial_dispatch_authorized",
        ),
    ],
)
def test_codex_dispatch_matrix(
    facts: CodexDispatchFacts,
    action: str,
    reason_code: str,
) -> None:
    decision = evaluate_codex_dispatch(facts)

    assert decision.action == action
    assert decision.reason_code == reason_code


def test_active_codex_logical_work_routes_follow_up_before_capacity_check() -> None:
    decision = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="write_serial",
            target_role="engineering",
            logical_work_state="active",
            existing_target_available=True,
            native_target_id="agent-engineering",
            capacity_available=False,
            serial_peer_absence_confirmed=False,
        )
    )

    assert decision.action == "follow_up"
    assert decision.reason_code == "logical_work_already_active"

    unknown_target = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="write_serial",
            target_role="engineering",
            logical_work_state="active",
            existing_target_available=False,
        )
    )
    assert unknown_target.action == "queue"
    assert unknown_target.reason_code == "active_work_target_unavailable"


def test_codex_capacity_exhaustion_queues_without_replacement() -> None:
    decision = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="read_parallel",
            target_role="quality",
            capacity_available=False,
            independent=True,
            reviewer_is_distinct_from_executor=True,
            reviewer_history="fresh",
        )
    )

    assert decision.action == "queue"
    assert decision.reason_code == "capacity_unavailable"

    unknown_capacity = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="write_serial",
            target_role="engineering",
            prerequisites_complete=True,
            serial_peer_absence_confirmed=True,
        )
    )
    assert unknown_capacity.action == "queue"
    assert unknown_capacity.reason_code == "capacity_unavailable"


def test_codex_reviewer_cannot_inherit_executor_history() -> None:
    decision = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="read_parallel",
            target_role="quality",
            capacity_available=True,
            independent=True,
            reviewer_is_distinct_from_executor=True,
            reviewer_history="inherits-executor",
        )
    )

    assert decision.action == "reject"
    assert decision.reason_code == "reviewer_thread_must_be_fresh"

    writable = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="dependency_serial",
            target_role="engineering",
            capacity_available=True,
            reviewer_is_distinct_from_executor=True,
            reviewer_history="fresh",
        )
    )
    assert writable.action == "queue"
    assert writable.reason_code == "prerequisite_or_serial_peer_active"

    same_actor = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="dependency_serial",
            target_role="quality",
            capacity_available=True,
            reviewer_is_distinct_from_executor=False,
            reviewer_history="fresh",
        )
    )
    assert same_actor.action == "reject"
    assert same_actor.reason_code == "reviewer_thread_must_be_fresh"

    fresh = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="dependency_serial",
            target_role="quality",
            capacity_available=True,
            reviewer_is_distinct_from_executor=True,
            reviewer_history="fresh",
            prerequisites_complete=True,
            serial_peer_absence_confirmed=True,
        )
    )
    assert fresh.action == "spawn"
    assert fresh.reason_code == "serial_dispatch_authorized"


@pytest.mark.parametrize(
    "target_role",
    [
        "product",
        "design",
        "engineering",
        "architecture",
        "science",
        "operations",
        "meta-eval",
    ],
)
def test_codex_read_parallel_rejects_every_write_capable_adapter(
    target_role: str,
) -> None:
    states = (
        {"logical_work_state": "inactive", "capacity_available": True},
        {"logical_work_state": "inactive", "capacity_available": False},
        {"logical_work_state": "unknown", "capacity_available": True},
        {"logical_work_state": "active"},
        {
            "logical_work_state": "active",
            "existing_target_available": True,
            "native_target_id": "agent-existing",
        },
    )
    for state in states:
        decision = evaluate_codex_dispatch(
            _dispatch_facts(
                dispatch_class="read_parallel",
                target_role=target_role,
                independent=True,
                **state,
            )
        )

        assert decision.action == "reject"
        assert decision.reason_code == (
            "read_parallel_requires_independent_read_only_work"
        )


@pytest.mark.parametrize(
    "target_role",
    ["praxys-orchestrator", "praxys-change-loop"],
)
def test_codex_read_parallel_rejects_transitive_writer_coordinators(
    target_role: str,
) -> None:
    decision = evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="read_parallel",
            target_role=target_role,
            capacity_available=True,
            independent=True,
        )
    )

    assert decision.action == "reject"
    assert decision.reason_code == (
        "read_parallel_requires_independent_read_only_work"
    )


def test_codex_dispatch_derives_read_only_from_supplied_adapter_contract() -> None:
    config = load_runtime_parity_config()
    quality = next(
        adapter for adapter in config.agent_adapters if adapter.id == "quality"
    )
    widened_quality = quality.model_copy(
        update={
            "sandbox_mode": "workspace-write",
            "write_scope": "accepted-artifacts",
        }
    )
    widened = config.model_copy(
        update={
            "agent_adapters": [
                widened_quality if adapter.id == "quality" else adapter
                for adapter in config.agent_adapters
            ]
        }
    )

    decision = _evaluate_codex_dispatch(
        _dispatch_facts(
            dispatch_class="read_parallel",
            target_role="quality",
            capacity_available=True,
            independent=True,
            reviewer_is_distinct_from_executor=True,
            reviewer_history="fresh",
        ),
        widened,
    )

    assert decision.action == "reject"
    assert decision.reason_code == (
        "read_parallel_requires_independent_read_only_work"
    )


def test_codex_unknown_work_replacement_and_identity_fail_closed() -> None:
    unknown = evaluate_codex_dispatch(
        _dispatch_facts(
            logical_work_state="unknown",
            capacity_available=True,
            prerequisites_complete=True,
            serial_peer_absence_confirmed=True,
        )
    )
    assert unknown.action == "queue"
    assert unknown.reason_code == "logical_work_state_unknown"

    replacement = evaluate_codex_dispatch(
        _dispatch_facts(
            replacement_requested=True,
            replacement_already_consumed=True,
            replacement_source_lost=True,
            capacity_available=True,
            prerequisites_complete=True,
            serial_peer_absence_confirmed=True,
        )
    )
    assert replacement.action == "reject"
    assert replacement.reason_code == "replacement_not_authorized"

    chained = evaluate_codex_dispatch(
        _dispatch_facts(
            replacement_requested=True,
            replacement_source_terminal=True,
            replacement_source_was_replacement=True,
            capacity_available=True,
            prerequisites_complete=True,
            serial_peer_absence_confirmed=True,
        )
    )
    assert chained.action == "reject"
    assert chained.reason_code == "replacement_not_authorized"

    with pytest.raises(ValidationError):
        _dispatch_facts(contract_id="not-a-contract")
    with pytest.raises(ValidationError):
        _dispatch_facts(revision_key="HEAD")
    with pytest.raises(ValidationError):
        _dispatch_facts(
            capacity_available="yes",
            prerequisites_complete="true",
            serial_peer_absence_confirmed=1,
        )


def test_codex_cleanup_is_leaf_first_and_unknown_tree_is_incomplete() -> None:
    decision = evaluate_codex_cleanup(
        "parent",
        [
            CodexTreeNode(
                native_target_id="parent",
                parent_target_id=None,
                active=True,
            ),
            CodexTreeNode(
                native_target_id="child",
                parent_target_id="parent",
                active=True,
            ),
            CodexTreeNode(
                native_target_id="leaf",
                parent_target_id="child",
                active=True,
            ),
        ],
    )
    assert decision.action == "interrupt"
    assert decision.native_target_ids == ["leaf", "child"]

    unavailable = evaluate_codex_cleanup("parent", None)
    assert unavailable.action == "record_incomplete"
    assert unavailable.reason_code == "tree_state_unavailable"

    cycle = evaluate_codex_cleanup(
        "parent",
        [
            CodexTreeNode(
                native_target_id="parent",
                parent_target_id="child",
                active=True,
            ),
            CodexTreeNode(
                native_target_id="child",
                parent_target_id="parent",
                active=True,
            ),
        ],
    )
    assert cycle.action == "record_incomplete"
    assert cycle.reason_code == "tree_state_invalid"

    disconnected = evaluate_codex_cleanup(
        "parent",
        [
            CodexTreeNode(
                native_target_id="parent",
                parent_target_id=None,
                active=True,
            ),
            CodexTreeNode(
                native_target_id="other-root",
                parent_target_id=None,
                active=True,
            ),
        ],
    )
    assert disconnected.action == "record_incomplete"
    assert disconnected.reason_code == "tree_state_invalid"

    with pytest.raises(ValidationError):
        CodexTreeNode.model_validate(
            {
                "native_target_id": "child",
                "parent_target_id": "parent",
                "active": "yes",
            }
        )


def test_codex_cleanup_selects_non_root_subtree_from_complete_tree() -> None:
    decision = evaluate_codex_cleanup(
        "parent",
        [
            CodexTreeNode(
                native_target_id="root",
                parent_target_id=None,
                active=True,
            ),
            CodexTreeNode(
                native_target_id="parent",
                parent_target_id="root",
                active=True,
            ),
            CodexTreeNode(
                native_target_id="child",
                parent_target_id="parent",
                active=True,
            ),
            CodexTreeNode(
                native_target_id="leaf",
                parent_target_id="child",
                active=True,
            ),
            CodexTreeNode(
                native_target_id="sibling",
                parent_target_id="root",
                active=True,
            ),
        ],
    )

    assert decision.action == "interrupt"
    assert decision.native_target_ids == ["leaf", "child"]


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

    assert config.schema_version == 2
    assert config.parity_version == "praxys-agent-runtime-parity-v2"
    assert config.status == "implementation-candidate"
    assert validate_static_runtime_parity(config) == []
    assert config.approval.subject_digest == (
        "sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc"
    )
    assert config.approval.proposal_digest == (
        "sha256:47a829962a21e17833feac0c3473ecb749c7b7e0ce4bff3aa2611ee1a92de8cd"
    )
    assert config.lifecycle_approval.subject_digest == (
        "sha256:dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43"
    )
    assert config.lifecycle_approval.proposal_digest == (
        "sha256:8fdc118d5447dc3b8797eefe7cf045f9c70ba257a0cafa38efe6d94c743f4ce3"
    )
    assert config.lifecycle_approval.digest_bound_human_approval_claimed is False
    assert config.lifecycle_approval.decision_review_route == "human-review-required"
    assert config.lifecycle_approval.exact_subject_human_approval_status == "pending"
    assert config.approved_work_contract.classification_digest == (
        "sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd"
    )
    assert config.approved_work_contract.route_digest == (
        "sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2"
    )
    assert config.codex_adapter.credentials_in_repository is False
    assert config.codex_adapter.separate_worktree_per_concurrent_task is True
    assert config.lifecycle_profiles.logical_work_key_fields == [
        "contract_id",
        "slot_id",
        "revision_key",
    ]
    assert config.lifecycle_profiles.codex.max_concurrent_threads_per_session == 4
    assert config.lifecycle_profiles.codex.copilot_native_protocol == "forbidden"
    assert config.lifecycle_profiles.copilot.contract_path == (
        "config/agent-invocation-control.json"
    )


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


def test_codex_local_mcp_extensions_are_exact_and_non_portable() -> None:
    config = load_runtime_parity_config()
    extensions = load_local_mcp_extensions()
    adapters = {adapter.id: adapter for adapter in config.agent_adapters}

    assert extensions.approval.subject_digest == (
        "sha256:0dfb8bcf46df787aa75575e03ff02f19ae40c1df2f8cddde37095c34fa6e987d"
    )
    assert set(extensions.mcp_extensions) == {
        "microsoft-learn",
        "azure-mcp",
    }
    microsoft = extensions.mcp_extensions["microsoft-learn"]
    azure = extensions.mcp_extensions["azure-mcp"]
    assert microsoft.root_enabled is False
    assert set(microsoft.role_enablement) == {
        "architecture",
        "engineering",
        "operations",
        "trust",
    }
    assert microsoft.enabled_tools == [
        "microsoft_docs_search",
        "microsoft_docs_fetch",
        "microsoft_code_sample_search",
    ]
    assert azure.root_enabled is False
    assert azure.role_enablement == ["operations"]
    assert azure.environment_forwarding == []
    assert azure.enabled_tools == [
        "azmcp_subscription_list",
        "azmcp_group_list",
    ]
    assert "@azure/mcp@2.0.5" in azure.args
    assert "--read-only" in azure.args
    assert "--tool" in azure.args
    assert "azure-mcp" not in adapters["engineering"].mcp_servers
    assert "azure-mcp" not in config.portable_mcp_servers
    assert "azure-mcp" in config.excluded_mcp_servers


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

    for server_id in (
        "chrome-devtools",
        "praxys-local",
        "microsoft-learn",
        "azure-mcp",
    ):
        assert servers[server_id]["enabled"] is False
    for server_id in ("chrome-devtools", "praxys-local", "azure-mcp"):
        assert servers[server_id]["transport"]["env_vars"] == []
    assert servers["chrome-devtools"]["transport"]["args"][1] == (
        "chrome-devtools-mcp@1.6.0"
    )
    assert servers["praxys-local"]["transport"]["args"] == [
        "scripts/run_praxys_mcp.cjs",
        "local",
    ]
    assert servers["microsoft-learn"]["transport"]["url"] == (
        "https://learn.microsoft.com/api/mcp"
    )
    assert servers["azure-mcp"]["transport"]["args"] == [
        "-y",
        "@azure/mcp@2.0.5",
        "server",
        "start",
        "--mode",
        "all",
        "--read-only",
        "--tool",
        "azmcp_subscription_list",
        "--tool",
        "azmcp_group_list",
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
    assert details["mcp servers"] == "4"
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


def test_lifecycle_subject_or_proposal_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    lifecycle_subject = (
        repository / "docs/dev/codex-subagent-lifecycle-decision-v2.json"
    )
    lifecycle_subject.write_text(
        lifecycle_subject.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )
    assert "lifecycle decision subject digest differs from contract" in errors

    repository = _copy_runtime_fixture(tmp_path / "proposal")
    lifecycle_proposal = (
        repository / "docs/dev/policy-change-proposal-codex-subagent-lifecycle-v2.md"
    )
    lifecycle_proposal.write_text(
        lifecycle_proposal.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )
    assert "lifecycle policy proposal digest differs from contract" in errors


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("dispatch_profiles", "default"), "background_independent_immediate_no_poll"),
        (("enforcement_approved",), True),
        (("approved_modes",), ["instrument", "shadow", "enforce"]),
        (("limits", "maximum_active_per_contract"), 1000),
    ],
)
def test_copilot_lifecycle_profile_drift_fails_closed(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    copilot = repository / "config/agent-invocation-control.json"
    payload = json.loads(copilot.read_text(encoding="utf-8"))
    target: dict[str, object] = payload
    for key in path[:-1]:
        child = target[key]
        assert isinstance(child, dict)
        target = child
    target[path[-1]] = value
    copilot.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Copilot lifecycle profile drifts from #745 contract" in errors


def test_invalid_copilot_lifecycle_profile_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    copilot = repository / "config/agent-invocation-control.json"
    copilot.write_text("not-json", encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Copilot lifecycle profile is invalid" in errors


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
        ).replace(
            'enabled_tools = ["azmcp_subscription_list", "azmcp_group_list"]',
            'enabled_tools = ["*"]',
        ),
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex project config differs from the runtime contract" in errors


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload["mcp_extensions"]["azure-mcp"].update(
                {"role_enablement": ["operations", "engineering"]}
            ),
            "Azure MCP must remain Operations-only",
        ),
        (
            lambda payload: payload["mcp_extensions"]["azure-mcp"].update(
                {"environment_forwarding": ["AZURE_CLIENT_ID"]}
            ),
            "must forward no environment",
        ),
        (
            lambda payload: payload["mcp_extensions"]["azure-mcp"].update(
                {"root_enabled": True}
            ),
            "Input should be False",
        ),
    ],
)
def test_codex_local_extension_contract_rejects_scope_widening(
    mutation, message: str
) -> None:
    payload = json.loads(
        (ROOT / "config/codex-local-mcp-extensions.json").read_text(
            encoding="utf-8"
        )
    )
    mutation(payload)

    with pytest.raises(ValidationError, match=message):
        CodexLocalMcpExtensions.model_validate(payload)


def test_extension_subject_digest_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    subject = (
        repository
        / "docs/dev/codex-microsoft-mcp-extension-decision-v1.json"
    )
    subject.write_text(subject.read_text(encoding="utf-8") + "\n")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "approved MCP extension subject digest differs from contract" in errors


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("@azure/mcp@2.0.5", "@azure/mcp@3.0.0-beta.39"),
        ('        "--read-only",\n', ""),
        (
            '"azmcp_group_list"\n      ],',
            '"azmcp_group_list", "azmcp_monitor_workspace_log_query"\n      ],',
        ),
        (
            '"environment_forwarding": [],',
            '"environment_forwarding": ["AZURE_CLIENT_ID"],',
        ),
    ],
)
def test_azure_extension_version_tool_flag_or_env_drift_fails_closed(
    tmp_path: Path, old: str, new: str
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/codex-local-mcp-extensions.json"
    original = contract.read_text(encoding="utf-8")
    mutated = original.replace(old, new, 1)
    assert mutated != original
    contract.write_text(mutated, encoding="utf-8")

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert errors
    assert any(
        "extension" in error.lower() or "environment" in error.lower()
        for error in errors
    )


def test_extra_codex_local_extension_is_rejected() -> None:
    payload = json.loads(
        (ROOT / "config/codex-local-mcp-extensions.json").read_text(
            encoding="utf-8"
        )
    )
    payload["mcp_extensions"]["unexpected"] = dict(
        payload["mcp_extensions"]["microsoft-learn"]
    )

    with pytest.raises(
        ValidationError, match="extension inventory must remain exact"
    ):
        CodexLocalMcpExtensions.model_validate(payload)


def test_extension_wildcard_tool_is_rejected() -> None:
    payload = json.loads(
        (ROOT / "config/codex-local-mcp-extensions.json").read_text(
            encoding="utf-8"
        )
    )
    payload["mcp_extensions"]["microsoft-learn"]["enabled_tools"] = ["*"]

    with pytest.raises(ValidationError, match="wildcard MCP tools"):
        CodexLocalMcpExtensions.model_validate(payload)


def test_operations_is_the_only_adapter_with_azure_mcp(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    engineering = repository / ".codex/agents/engineering.toml"
    azure = (repository / ".codex/agents/operations.toml").read_text(
        encoding="utf-8"
    ).split("[mcp_servers.azure-mcp]", 1)[1]
    engineering.write_text(
        engineering.read_text(encoding="utf-8")
        + "\n[mcp_servers.azure-mcp]"
        + azure,
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex agent adapter differs from contract: engineering" in errors


def test_codex_thread_limit_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    project_config = repository / ".codex/config.toml"
    project_config.write_text(
        project_config.read_text(encoding="utf-8").replace(
            "max_concurrent_threads_per_session = 4",
            "max_concurrent_threads_per_session = 8",
        ),
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex project config differs from the runtime contract" in errors


def test_codex_lifecycle_guidance_drift_fails_closed(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    coordinator = repository / ".codex/agents/praxys-orchestrator.toml"
    coordinator.write_text(
        coordinator.read_text(encoding="utf-8").replace(
            "serialize writes and dependency chains",
            "run writes and dependency chains in parallel",
        ),
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert (
        "Codex lifecycle guidance drifts from contract: praxys-orchestrator"
        in errors
    )


def test_codex_non_coordinator_dispatch_boundary_fails_closed(
    tmp_path: Path,
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    entry = repository / "AGENTS.md"
    entry.write_text(
        entry.read_text(encoding="utf-8").replace(
            "Only Praxys Orchestrator and Praxys Change Loop may dispatch Codex "
            "child agents.",
            "Any Praxys role may dispatch Codex child agents.",
        ),
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex non-coordinator dispatch boundary is missing" in errors


def test_codex_cannot_drop_copilot_protocol_prohibition(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    coordinator = repository / ".codex/agents/praxys-change-loop.toml"
    coordinator.write_text(
        coordinator.read_text(encoding="utf-8").replace(
            "`native_read`, ",
            "",
        ),
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert (
        "Codex Copilot-protocol prohibition is incomplete: praxys-change-loop"
        in errors
    )


def test_codex_lifecycle_schema_rejects_parallel_write_profile(
    tmp_path: Path,
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["lifecycle_profiles"]["codex"]["dispatch_classes"] = [
        "read_parallel",
        "write_parallel",
        "dependency_serial",
    ]
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        _load_fixture_config(repository)


def test_codex_lifecycle_schema_rejects_policy_widening(tmp_path: Path) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["lifecycle_profiles"]["codex"][
        "max_concurrent_threads_per_session"
    ] = 8
    payload["lifecycle_profiles"]["codex"][
        "copilot_native_protocol"
    ] = "allowed"
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        _load_fixture_config(repository)


def test_runtime_parity_v1_reader_refuses_lifecycle_v2_contract(
    tmp_path: Path,
) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    contract = repository / "config/agent-runtime-parity.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    payload["parity_version"] = "praxys-agent-runtime-parity-v1"
    contract.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        _load_fixture_config(repository)


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
