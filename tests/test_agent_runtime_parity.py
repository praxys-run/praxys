"""Static regressions for sandbox, credentials, scientific separation and MCP grants."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
import pytest
from pydantic import ValidationError
from analysis.agent_runtime_parity import (
    AgentRuntimeParity, CodexLocalMcpExtensions, filtered_command_environment,
    load_local_mcp_extensions, load_runtime_parity_config, validate_static_runtime_parity,
)
ROOT = Path(__file__).resolve().parents[1]


def _copy_runtime_fixture(tmp_path: Path) -> Path:
    # Only static inputs, never the repository's databases, node_modules or private files.
    repository = tmp_path / "repository"
    for relative in ["config", ".codex", ".github/agents", ".github/skills", ".github/hooks", ".github/workflows", "docs/dev", ".agents"]:
        shutil.copytree(ROOT / relative, repository / relative, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    for relative in ["AGENTS.md", "CLAUDE.md", "PRODUCT.md", ".mcp.json", ".github/copilot-instructions.md",  "docs/ops/README.md"]:
        if (ROOT / relative).is_file():
            target = repository / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
    return repository



def _load_fixture_config(repository: Path) -> AgentRuntimeParity:
    return load_runtime_parity_config(
        repository / "config" / "agent-runtime-parity.json"
    )


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
    assert "azure-mcp" not in adapters["praxys-orchestrator"].mcp_servers
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
    engineering = repository / ".codex/agents/praxys-orchestrator.toml"
    azure = (repository / ".codex/agents/operations.toml").read_text(
        encoding="utf-8"
    ).split("[mcp_servers.azure-mcp]", 1)[1].split("[mcp_servers.statsig]", 1)[0]
    engineering.write_text(
        engineering.read_text(encoding="utf-8")
        + "\n[mcp_servers.azure-mcp]"
        + azure,
        encoding="utf-8",
    )

    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )

    assert "Codex agent adapter differs from contract: praxys-orchestrator" in errors


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


def test_statsig_extension_exact_scope_and_immutable_predecessors() -> None:
    from analysis.agent_runtime_parity import load_statsig_mcp_extension
    extension=load_statsig_mcp_extension()
    config=load_runtime_parity_config()
    assert extension.mcp_extension.enabled_tools==["get_context","gate_read","gate_create","gate_update"]
    assert extension.mcp_extension.role_enablement==["operations"]
    assert {a.id for a in config.agent_adapters}-{"operations"} <= set(extension.mcp_extension.role_explicit_disable)
    assert extension.binding.exact_digest_human_approval_claimed is False
    assert "statsig" in config.excluded_mcp_servers and "statsig" not in config.portable_mcp_servers
    assert set(load_local_mcp_extensions().mcp_extensions)=={"microsoft-learn","azure-mcp"}
    root=tomllib.loads((ROOT/".codex/config.toml").read_text())
    assert root["mcp_servers"]["statsig"]=={"url":"https://api.statsig.com/v3/mcp","auth":"oauth","enabled":True,"required":False,"enabled_tools":["get_context","gate_read","gate_create","gate_update"],"default_tools_approval_mode":"prompt"}
    for adapter in config.agent_adapters:
        payload=tomllib.loads((ROOT/adapter.codex_path).read_text())
        assert payload["mcp_servers"]["statsig"]=={**root["mcp_servers"]["statsig"],"enabled":adapter.id=="operations"}


@pytest.mark.parametrize("section,key,value",[
    ("mcp_extension","url","https://api.statsig.com/v1/mcp"),
    ("mcp_extension","authentication","api-key"),
    ("mcp_extension","required",True),
    ("mcp_extension","root_enabled",False),
    ("mcp_extension","enabled_tools",["get_context","gate_read","gate_update"]),
    ("mcp_extension","enabled_tools",["*"]),
    ("mcp_extension","enabled_tools",["get_context","gate_read","gate_create","gate_update","api_write"]),
    ("mcp_extension","role_enablement",["engineering"]),
    ("mcp_extension","role_explicit_disable",[]),
    ("mcp_extension","default_tools_approval_mode","auto"),
    ("mcp_extension","environment_forwarding",["STATSIG_SECRET"]),
    ("mcp_extension","bearer_token_environment_variable","STATSIG_TOKEN"),
    ("mcp_extension","headers_in_repository",True),
    ("mcp_extension","http_headers",{"Authorization":"synthetic-only"}),
    ("mcp_extension","oauth_scopes",["all"]),
    ("binding","subject_digest","sha256:"+"0"*64),
    ("binding","proposal_digest","sha256:"+"0"*64),
    ("binding","subject_path","../outside.json"),
    ("binding","exact_digest_human_approval_claimed",True),
])
def test_statsig_strict_contract_rejects_drift(section,key,value) -> None:
    from analysis.agent_runtime_parity import CodexStatsigMcpExtension
    payload=json.loads((ROOT/"config/codex-statsig-mcp-extension.json").read_text())
    payload[section][key]=value
    with pytest.raises(ValueError):CodexStatsigMcpExtension.model_validate(payload)


@pytest.mark.parametrize("relative",[
    "docs/dev/codex-statsig-mcp-extension-decision-public-projection-v1.json",
    "docs/dev/policy-change-proposal-codex-statsig-mcp-extension-public-projection-v1.md",
    "docs/dev/evaluation-report-codex-statsig-mcp-extension-v1.md",
    "docs/dev/architecture-decision-record-codex-statsig-mcp-extension-v1.md",
    "docs/dev/trust-decision-record-codex-statsig-mcp-extension-public-projection-v1.md",
    "docs/dev/evaluation-report-codex-statsig-public-projection-v1.md",
])
def test_statsig_original_artifact_byte_drift_fails_closed(tmp_path,relative) -> None:
    repository=_copy_runtime_fixture(tmp_path)
    path=repository/relative;path.write_bytes(path.read_bytes()+b"\n")
    errors=validate_static_runtime_parity(_load_fixture_config(repository),root=repository)
    assert any("Statsig immutable artifact byte digest differs" in e for e in errors)


@pytest.mark.parametrize("case",["missing","malformed","extra-field"])
def test_statsig_contract_absence_or_malformed_fails_closed(tmp_path,case) -> None:
    repository=_copy_runtime_fixture(tmp_path);path=repository/"config/codex-statsig-mcp-extension.json"
    if case=="missing":path.unlink()
    elif case=="malformed":path.write_text("{broken")
    else:
        data=json.loads(path.read_text());data["approval"]={"human_approved_at":"invented"};path.write_text(json.dumps(data))
    errors=validate_static_runtime_parity(_load_fixture_config(repository),root=repository)
    assert any("invalid Codex Statsig MCP extension contract" in e for e in errors)


@pytest.mark.parametrize("path,replacement",[
    (".codex/config.toml",('auth = "oauth"','auth = "api-key"')),
    (".codex/config.toml",('default_tools_approval_mode = "prompt"','default_tools_approval_mode = "auto"')),
    (".codex/config.toml",('required = false','required = true')),
    (".codex/config.toml",('enabled_tools = ["get_context", "gate_read", "gate_create", "gate_update"]','enabled_tools = ["get_context", "gate_read", "gate_create", "gate_update", "api_destructive"]')),
    (".codex/config.toml",('auth = "oauth"','auth = "oauth"\nhttp_headers = {Authorization = "synthetic-only"}')),
    (".codex/config.toml",('auth = "oauth"','auth = "oauth"\nbearer_token_env_var = "STATSIG_TOKEN"')),
    (".codex/config.toml",('auth = "oauth"','auth = "oauth"\nenv_vars = ["STATSIG_TOKEN"]')),
    (".codex/config.toml",('auth = "oauth"','auth = "oauth"\ntools.gate_update.approval_mode = "auto"')),
    (".codex/agents/praxys-orchestrator.toml",('enabled = false','enabled = true')),
    (".codex/agents/quality.toml",('enabled = false','enabled = 0')),
])
def test_statsig_native_projection_rejects_credentials_scope_or_prompt_drift(tmp_path,path,replacement) -> None:
    repository=_copy_runtime_fixture(tmp_path);target=repository/path
    text=target.read_text();prefix,stanza=text.rsplit("[mcp_servers.statsig]",1)
    assert replacement[0] in stanza;stanza=stanza.replace(*replacement,1)
    target.write_text(prefix+"[mcp_servers.statsig]"+stanza)
    assert validate_static_runtime_parity(_load_fixture_config(repository),root=repository)


def test_statsig_omitted_child_disable_and_id_collision_fail_closed(tmp_path) -> None:
    repository=_copy_runtime_fixture(tmp_path);target=repository/".codex/agents/quality.toml"
    target.write_text(target.read_text().split("[mcp_servers.statsig]")[0])
    errors=validate_static_runtime_parity(_load_fixture_config(repository),root=repository)
    assert any("Codex agent adapter differs from contract: quality" in e for e in errors)
    config=_load_fixture_config(repository)
    collided=config.model_copy(update={"portable_mcp_servers":{**config.portable_mcp_servers,"statsig":next(iter(config.portable_mcp_servers.values()))}})
    assert any("Statsig MCP ID collides" in e for e in validate_static_runtime_parity(collided,root=repository))


def test_codex_statsig_get_is_parser_only_and_secret_free(tmp_path) -> None:
    if shutil.which("codex") is None:pytest.skip("Codex CLI unavailable")
    result=subprocess.run(["codex","mcp","get","statsig","--json"],cwd=ROOT,env=_isolated_codex_environment(tmp_path),check=True,capture_output=True,text=True,timeout=30)
    payload=json.loads(result.stdout)
    assert payload["enabled"] is True
    assert payload["enabled_tools"]==["get_context","gate_read","gate_create","gate_update"]
    assert payload["transport"]["url"]=="https://api.statsig.com/v3/mcp"
    for name in ("bearer_token_env_var","http_headers","env_http_headers"):
        assert payload["transport"].get(name) in (None,{})


@pytest.mark.parametrize("key,value", [
    ("proposal_id", "policy-change-proposal-codex-statsig-mcp-extension-v1"),
    ("proposal_path", "docs/dev/policy-change-proposal-codex-statsig-mcp-extension-v1.md"),
    ("subject_id", "codex-statsig-mcp-extension-decision-v1"),
    ("subject_path", "docs/dev/codex-statsig-mcp-extension-decision-v1.json"),
    ("proposal_digest", "sha256:680b2ed4bffa2feb063e0c1b64b64245b736af410a905f39b63dfbfc5a0c8139"),
    ("subject_digest", "sha256:5d2eff8ab7743bbbcd4d709ab28826f03a54457553f3e83c6274644d761c0fc6"),
    ("authorized_scope", "merge-and-default-branch-activation-only"),
])
def test_statsig_public_projection_rejects_historical_rebinding(key, value) -> None:
    from analysis.agent_runtime_parity import CodexStatsigMcpExtension
    payload = json.loads((ROOT / "config/codex-statsig-mcp-extension.json").read_text())
    payload["binding"][key] = value
    with pytest.raises(ValueError):
        CodexStatsigMcpExtension.model_validate(payload)


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("mutation", ["digest", "escaping-path", "extra-field"])
def test_statsig_public_projection_support_rebinding_fails_closed(index, mutation) -> None:
    from analysis.agent_runtime_parity import CodexStatsigMcpExtension
    payload = json.loads((ROOT / "config/codex-statsig-mcp-extension.json").read_text())
    record = payload["supporting_artifacts"][index]
    if mutation == "digest":
        record["digest"] = "sha256:" + "0" * 64
    elif mutation == "escaping-path":
        record["path"] = "../outside.md"
    else:
        record["approval"] = "invented"
    with pytest.raises(ValueError):
        CodexStatsigMcpExtension.model_validate(payload)


def test_statsig_public_projection_exact_pins_and_historical_support() -> None:
    from analysis.agent_runtime_parity import load_statsig_mcp_extension
    extension = load_statsig_mcp_extension()
    assert extension.extension_version == "praxys-codex-statsig-mcp-extension-public-projection-v1"
    assert extension.binding.subject_id == "codex-statsig-mcp-extension-decision-public-projection-v1"
    assert extension.binding.subject_digest == "sha256:e3a8b7b81725470e653710d03958c90ce1839f855a8a98e3308e79820a8398e6"
    assert extension.binding.proposal_id == "policy-change-proposal-codex-statsig-mcp-extension-public-projection-v1"
    assert extension.binding.proposal_digest == "sha256:d20726456dc9bc7ce52c372959c18de3308fd22a1b64c2f1effcd07a6a2078fe"
    assert [(a.path, a.digest) for a in extension.supporting_artifacts] == [
        ("docs/dev/evaluation-report-codex-statsig-mcp-extension-v1.md", "sha256:c340b12fe6b4fbc72530de2399ff7b03a1c522f26d401e1db3416c287e3147b3"),
        ("docs/dev/architecture-decision-record-codex-statsig-mcp-extension-v1.md", "sha256:fe240f5feeae71c3f257cdba6e4ee9707b8e259ef09cd20d6c99f4c59d169deb"),
        ("docs/dev/trust-decision-record-codex-statsig-mcp-extension-public-projection-v1.md", "sha256:1ea94595b99465c3d4456bbe3c504c51ec126774e8e17bc2496dd9688c776beb"),
        ("docs/dev/evaluation-report-codex-statsig-public-projection-v1.md", "sha256:4df991a55b17993d53ef8255cc89a3ac46b2deedaac45181c2dd6003c6bc0ecf"),
    ]


@pytest.mark.parametrize("relative", [
    "docs/dev/codex-statsig-mcp-extension-decision-public-projection-v1.json",
    "docs/dev/policy-change-proposal-codex-statsig-mcp-extension-public-projection-v1.md",
    "docs/dev/evaluation-report-codex-statsig-mcp-extension-v1.md",
    "docs/dev/architecture-decision-record-codex-statsig-mcp-extension-v1.md",
    "docs/dev/trust-decision-record-codex-statsig-mcp-extension-public-projection-v1.md",
    "docs/dev/evaluation-report-codex-statsig-public-projection-v1.md",
])
def test_statsig_public_projection_artifact_escape_fails_closed(tmp_path, relative) -> None:
    repository = _copy_runtime_fixture(tmp_path)
    path = repository / relative
    outside = tmp_path / "outside-record"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    errors = validate_static_runtime_parity(_load_fixture_config(repository), root=repository)
    assert any("missing/escaping Statsig immutable artifact" in error for error in errors)


@pytest.mark.parametrize("section,key,value", [
    (None, "schema_version", True),
    (None, "schema_version", 1.0),
    ("binding", "exact_digest_human_approval_claimed", 0),
    ("binding", "exact_digest_human_approval_claimed", 0.0),
])
def test_statsig_scalar_aliases_fail_through_model_loader_and_static_check(
    tmp_path, section, key, value
) -> None:
    from analysis.agent_runtime_parity import (
        CodexStatsigMcpExtension,
        load_statsig_mcp_extension,
    )
    repository = _copy_runtime_fixture(tmp_path)
    path = repository / "config/codex-statsig-mcp-extension.json"
    payload = json.loads(path.read_text())
    target = payload if section is None else payload[section]
    target[key] = value
    with pytest.raises(ValueError):
        CodexStatsigMcpExtension.model_validate(payload)
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_statsig_mcp_extension(path)
    errors = validate_static_runtime_parity(
        _load_fixture_config(repository), root=repository
    )
    assert any("invalid Codex Statsig MCP extension contract" in error for error in errors)


def test_current_adapter_contract_passes_without_legacy_approval_rebinding():
    config = load_runtime_parity_config()
    assert config.schema_version == 3
    assert validate_static_runtime_parity(config) == []
    assert {a.id for a in config.agent_adapters} == {"praxys-orchestrator", "quality", "operations"}
    assert "approval" not in config.model_dump()
    assert "lifecycle_profiles" not in config.model_dump()


@pytest.mark.parametrize("old,new", [
    ('sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'),
    ('Do not spawn agents', 'May spawn agents'),
])
def test_reviewer_cannot_gain_write_or_dispatch_permission(tmp_path, old, new):
    repository = _copy_runtime_fixture(tmp_path)
    path = repository / ".codex/agents/quality.toml"
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new))
    assert validate_static_runtime_parity(_load_fixture_config(repository), root=repository)


def test_contract_cannot_turn_reviewer_into_executor():
    payload = load_runtime_parity_config().model_dump()
    reviewer = next(a for a in payload["agent_adapters"] if a["id"] == "quality")
    reviewer.update(sandbox_mode="workspace-write", write_scope="implementation")
    with pytest.raises(ValidationError, match="write scope"):
        AgentRuntimeParity.model_validate(payload)


def test_hook_and_skill_escape_are_rejected(tmp_path):
    repository = _copy_runtime_fixture(tmp_path)
    hook = repository / ".codex/hooks.json"
    payload = json.loads(hook.read_text())
    payload["hooks"]["PostToolUse"][0]["hooks"][0]["command"] = "true"
    hook.write_text(json.dumps(payload))
    alias = repository / ".agents/skills/ui-quality"
    alias.unlink()
    alias.symlink_to(tmp_path / "outside")
    errors = validate_static_runtime_parity(_load_fixture_config(repository), root=repository)
    assert "Codex hook differs from contract" in errors
    assert "skill alias escapes or differs: ui-quality" in errors


def test_retired_agent_cannot_reappear_silently(tmp_path):
    repository = _copy_runtime_fixture(tmp_path)
    source = repository / ".codex/agents/quality.toml"
    shutil.copy2(source, repository / ".codex/agents/work-router.toml")
    errors = validate_static_runtime_parity(_load_fixture_config(repository), root=repository)
    assert "Codex agent file set differs from runtime contract" in errors


def test_portable_cloud_tool_scope_drift_is_still_rejected(tmp_path):
    repository = _copy_runtime_fixture(tmp_path)
    path = repository / "config/copilot-cloud-mcp.json"
    payload = json.loads(path.read_text())
    payload["mcpServers"].pop("praxys-local")
    path.write_text(json.dumps(payload))
    assert validate_static_runtime_parity(_load_fixture_config(repository), root=repository)


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
    assert details["mcp servers"] == "5"
    assert details.get("startup warnings", "0") == "0"
    assert details.get("startup warning hooks", "0") == "0"
    assert details.get("startup warning skills", "0") == "0"
