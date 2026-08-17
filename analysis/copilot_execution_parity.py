"""Static and live parity checks for Local and Cloud Copilot execution."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import subprocess
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CONFIG_PATH = _ROOT / "config" / "copilot-execution-parity.json"
_CLOUD_CONFIGURATION_API_VERSION = "2026-03-10"


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _require_repository_path(value: str, label: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be repository-relative")


class ParityRecord(BaseModel):
    """Strict immutable base model for execution-parity records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CommonMcpServer(ParityRecord):
    """One MCP server whose allowed tools are common to both runtimes."""

    required_tools: list[str] = Field(min_length=1)
    allowed_live_env: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tools(self) -> "CommonMcpServer":
        """Keep the portable tool set deterministic."""
        _require_unique(self.required_tools, "required MCP tools")
        return self


class EnvironmentAdapter(ParityRecord):
    """Repository-owned adapter for one Copilot execution environment."""

    mcp_config_path: str
    entry_instruction_paths: list[str] = Field(min_length=1)
    entry_method: str = Field(min_length=1)
    setup_workflow_path: str | None = None
    assignment_workflow_path: str | None = None
    parity_workflow_path: str | None = None
    setup_markers: list[str] = Field(default_factory=list)
    parity_markers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_adapter(self) -> "EnvironmentAdapter":
        """Keep adapter path and marker lists deterministic."""
        for label, path in (
            ("mcp_config_path", self.mcp_config_path),
            *(
                ("entry_instruction_path", instruction_path)
                for instruction_path in self.entry_instruction_paths
            ),
            ("setup_workflow_path", self.setup_workflow_path),
            ("assignment_workflow_path", self.assignment_workflow_path),
            ("parity_workflow_path", self.parity_workflow_path),
        ):
            if path is not None:
                _require_repository_path(path, label)
        _require_unique(
            self.entry_instruction_paths,
            "entry_instruction_paths",
        )
        _require_unique(self.setup_markers, "setup_markers")
        _require_unique(self.parity_markers, "parity_markers")
        return self


class ExecutionLimitation(ParityRecord):
    """One explicit boundary where exact environment parity is impossible."""

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    environments: list[Literal["local", "cloud"]] = Field(min_length=1)
    behavior: str = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_environments(self) -> "ExecutionLimitation":
        """Reject duplicated environment labels."""
        _require_unique(self.environments, "limitation environments")
        return self


class CopilotExecutionParity(ParityRecord):
    """Versioned common-capability and environment-adapter contract."""

    schema_version: Literal[1]
    parity_version: str = Field(min_length=1)
    status: Literal["active"]
    orchestrator_agent_path: str
    orchestrator_agent_slug: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    routing_config_path: str
    portable_agent_paths: list[str] = Field(min_length=1)
    common_builtin_tools: list[str] = Field(min_length=1)
    common_mcp_servers: dict[str, CommonMcpServer] = Field(min_length=1)
    local: EnvironmentAdapter
    cloud: EnvironmentAdapter
    limitations: list[ExecutionLimitation] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_parity(self) -> "CopilotExecutionParity":
        """Require unique portable agents, tools, and limitation IDs."""
        _require_unique(self.portable_agent_paths, "portable_agent_paths")
        _require_unique(self.common_builtin_tools, "common_builtin_tools")
        _require_unique(
            [limitation.id for limitation in self.limitations],
            "limitation IDs",
        )
        _require_repository_path(
            self.orchestrator_agent_path,
            "orchestrator_agent_path",
        )
        _require_repository_path(
            self.routing_config_path,
            "routing_config_path",
        )
        for path in self.portable_agent_paths:
            _require_repository_path(path, "portable_agent_path")
        if self.orchestrator_agent_path not in self.portable_agent_paths:
            raise ValueError("orchestrator must be a portable agent")
        return self


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _agent_tools(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    try:
        _, frontmatter, _ = raw.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"invalid agent frontmatter: {path}") from exc
    metadata = yaml.safe_load(frontmatter)
    tools = metadata.get("tools", [])
    if not isinstance(tools, list) or not all(
        isinstance(tool, str) for tool in tools
    ):
        raise ValueError(f"invalid agent tools: {path}")
    return tools


def _server_tools(payload: dict[str, object], server_id: str) -> set[str]:
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict) or server_id not in servers:
        return set()
    server = servers[server_id]
    if not isinstance(server, dict):
        return set()
    tools = server.get("tools")
    if not isinstance(tools, list):
        return set()
    return {
        tool
        for tool in tools
        if isinstance(tool, str)
    }


def validate_static_execution_parity(
    config: CopilotExecutionParity,
    *,
    root: Path = _ROOT,
) -> list[str]:
    """Return repository parity violations without accessing GitHub settings."""
    errors: list[str] = []
    required_paths = [
        config.orchestrator_agent_path,
        config.routing_config_path,
        config.local.mcp_config_path,
        config.cloud.mcp_config_path,
        *config.portable_agent_paths,
        *config.local.entry_instruction_paths,
        *config.cloud.entry_instruction_paths,
    ]
    if config.cloud.setup_workflow_path is not None:
        required_paths.append(config.cloud.setup_workflow_path)
    if config.cloud.assignment_workflow_path is not None:
        required_paths.append(config.cloud.assignment_workflow_path)
    if config.cloud.parity_workflow_path is not None:
        required_paths.append(config.cloud.parity_workflow_path)
    for relative_path in required_paths:
        if not (root / relative_path).is_file():
            errors.append(f"missing parity path: {relative_path}")
    if errors:
        return errors

    local_mcp = _load_json(root / config.local.mcp_config_path)
    cloud_mcp = _load_json(root / config.cloud.mcp_config_path)
    cloud_servers = cloud_mcp.get("mcpServers")
    common_server_ids = set(config.common_mcp_servers)
    if (
        not isinstance(cloud_servers, dict)
        or set(cloud_servers) != common_server_ids
    ):
        errors.append(
            "cloud MCP server set differs from common capability contract"
        )
    for server_id, server in config.common_mcp_servers.items():
        expected = set(server.required_tools)
        local_tools = _server_tools(local_mcp, server_id)
        cloud_tools = _server_tools(cloud_mcp, server_id)
        if local_tools != expected:
            errors.append(
                f"local {server_id} tools differ from common contract"
            )
        if cloud_tools != expected:
            errors.append(
                f"cloud {server_id} tools differ from common contract"
            )

    allowed_builtins = set(config.common_builtin_tools)
    common_servers = set(config.common_mcp_servers)
    for relative_path in config.portable_agent_paths:
        for tool in _agent_tools(root / relative_path):
            if tool in allowed_builtins:
                continue
            if "/" not in tool:
                errors.append(
                    f"{relative_path} uses non-portable tool {tool}"
                )
                continue
            server_id, tool_name = tool.split("/", 1)
            if server_id not in common_servers:
                errors.append(
                    f"{relative_path} uses environment-specific server "
                    f"{server_id}"
                )
            elif (
                tool_name != "*"
                and tool_name
                not in config.common_mcp_servers[server_id].required_tools
            ):
                errors.append(
                    f"{relative_path} uses non-portable MCP tool {tool}"
                )

    for adapter_name, adapter in (
        ("local", config.local),
        ("cloud", config.cloud),
    ):
        for instruction_path in adapter.entry_instruction_paths:
            content = (root / instruction_path).read_text(encoding="utf-8")
            if config.orchestrator_agent_slug not in content.lower():
                errors.append(
                    f"{adapter_name} entry instructions omit orchestrator: "
                    f"{instruction_path}"
                )

    if config.cloud.setup_workflow_path is not None:
        setup = (root / config.cloud.setup_workflow_path).read_text(
            encoding="utf-8"
        )
        for marker in config.cloud.setup_markers:
            if marker not in setup:
                errors.append(f"cloud setup omits marker: {marker}")
    if config.cloud.assignment_workflow_path is not None:
        assignment = (
            root / config.cloud.assignment_workflow_path
        ).read_text(encoding="utf-8")
        marker = f"customAgent={config.orchestrator_agent_slug}"
        if marker not in assignment:
            errors.append(
                f"cloud assignment does not select {marker}"
            )
    if config.cloud.parity_workflow_path is not None:
        parity_workflow = (
            root / config.cloud.parity_workflow_path
        ).read_text(encoding="utf-8")
        for marker in config.cloud.parity_markers:
            if marker not in parity_workflow:
                errors.append(f"cloud parity workflow omits marker: {marker}")
    return errors


def validate_live_cloud_mcp(
    live_payload: dict[str, object],
    config: CopilotExecutionParity,
    *,
    root: Path = _ROOT,
) -> list[str]:
    """Compare live Cloud MCP settings with the checked-in semantic contract."""
    errors: list[str] = []
    declared = _load_json(root / config.cloud.mcp_config_path)
    live_mcp = live_payload.get("mcp_configuration", live_payload)
    if not isinstance(live_mcp, dict):
        return ["live cloud MCP payload is not an object"]
    declared_servers = declared.get("mcpServers")
    live_servers = live_mcp.get("mcpServers")
    if not isinstance(declared_servers, dict) or not isinstance(
        live_servers,
        dict,
    ):
        return ["cloud MCP payload is missing mcpServers"]
    if set(live_servers) != set(declared_servers):
        errors.append("live cloud MCP server set differs from repository config")

    for server_id, declared_server in declared_servers.items():
        live_server = live_servers.get(server_id)
        common_server = config.common_mcp_servers.get(server_id)
        if common_server is None:
            errors.append(
                f"repository cloud config has non-portable server: {server_id}"
            )
            continue
        if not isinstance(declared_server, dict) or not isinstance(
            live_server,
            dict,
        ):
            errors.append(f"invalid live MCP server: {server_id}")
            continue
        for field in ("type", "command", "args", "tools"):
            if live_server.get(field) != declared_server.get(field):
                errors.append(
                    f"live cloud {server_id}.{field} differs from repository"
                )
        live_env = live_server.get("env", {})
        if live_env is None:
            live_env = {}
        if not isinstance(live_env, dict):
            errors.append(f"live cloud {server_id}.env is not an object")
            continue
        allowed_env = common_server.allowed_live_env
        if live_env != allowed_env:
            errors.append(
                f"live cloud {server_id}.env differs from allowed override"
            )
    return errors


def read_live_cloud_configuration(repository: str) -> dict[str, object]:
    """Read the authenticated repository Cloud agent configuration via gh."""
    completed = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            f"X-GitHub-Api-Version: {_CLOUD_CONFIGURATION_API_VERSION}",
            f"repos/{repository}/copilot/cloud-agent/configuration",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned a non-object Cloud configuration")
    return payload


def load_execution_parity_config(
    path: str | Path | None = None,
) -> CopilotExecutionParity:
    """Load the checked-in Local and Cloud execution-parity contract."""
    if path is None:
        return _load_default_execution_parity_config()
    return CopilotExecutionParity.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def _load_default_execution_parity_config() -> CopilotExecutionParity:
    """Load the default execution-parity contract once per process."""
    return CopilotExecutionParity.model_validate_json(
        _DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    )
