"""Validate AI-native operations runbooks and their generated eval fixtures."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = ROOT / "docs" / "ops"
AI_DIR = OPS_DIR / "ai"
REGISTRY_PATH = AI_DIR / "tool-registry.yaml"
EVAL_DIR = AI_DIR / "evals"
BLOCK_PATTERN = re.compile(r"```ops-runbook\s*\n(.*?)\n```", re.DOTALL)
REQUIRED_TOP_LEVEL = {
    "version",
    "id",
    "autonomy",
    "summary",
    "signals",
    "actions",
    "routes",
}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Load the structured runbook tool and policy registry."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: registry must be a mapping")
    return data


def extract_runbook(path: Path) -> dict[str, Any] | None:
    """Return the single structured runbook block from a Markdown file."""
    matches = BLOCK_PATTERN.findall(path.read_text(encoding="utf-8"))
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"{path}: expected one ops-runbook block, found {len(matches)}")
    data = yaml.safe_load(matches[0])
    if not isinstance(data, dict):
        raise ValueError(f"{path}: ops-runbook block must be a mapping")
    return data


def _indexed(items: Any, field: str, context: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(items, list):
        errors.append(f"{context}: must be a list")
        return {}
    indexed: dict[str, Any] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{context}[{index}]: must be a mapping")
            continue
        item_id = item.get(field)
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"{context}[{index}].{field}: must be a non-empty string")
            continue
        if item_id in indexed:
            errors.append(f"{context}: duplicate {field} {item_id!r}")
        indexed[item_id] = item
    return indexed


def validate_runbook(
    runbook: dict[str, Any],
    registry: dict[str, Any],
    source: str,
) -> list[str]:
    """Validate references and policy boundaries in one runbook block."""
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL - runbook.keys()
    if missing:
        errors.append(f"{source}: missing fields: {', '.join(sorted(missing))}")

    if runbook.get("version") != registry.get("version"):
        errors.append(f"{source}: version must match registry version")
    if runbook.get("autonomy") != "bounded":
        errors.append(f"{source}: autonomy must be 'bounded'")

    tools = registry.get("tools", {})
    policies = set(registry.get("policies", []))
    if not isinstance(tools, dict):
        errors.append("registry tools must be a mapping")
        tools = {}

    signals = _indexed(runbook.get("signals"), "id", f"{source}.signals", errors)
    actions = _indexed(runbook.get("actions"), "id", f"{source}.actions", errors)
    routes = _indexed(runbook.get("routes"), "id", f"{source}.routes", errors)

    for signal_id, signal in signals.items():
        tool_id = signal.get("tool")
        tool = tools.get(tool_id)
        if not isinstance(tool, dict) or tool.get("kind") != "signal":
            errors.append(f"{source}.signals.{signal_id}: unknown signal tool {tool_id!r}")
        if signal.get("policy") != "observe":
            errors.append(f"{source}.signals.{signal_id}: policy must be 'observe'")
        if not isinstance(signal.get("command"), str) or not signal["command"].strip():
            errors.append(f"{source}.signals.{signal_id}: command is required")
        if not isinstance(signal.get("success"), dict):
            errors.append(f"{source}.signals.{signal_id}: success oracle is required")

    for action_id, action in actions.items():
        tool_id = action.get("tool")
        tool = tools.get(tool_id)
        if not isinstance(tool, dict) or tool.get("kind") != "action":
            errors.append(f"{source}.actions.{action_id}: unknown action tool {tool_id!r}")
        policy = action.get("policy")
        if policy not in policies:
            errors.append(f"{source}.actions.{action_id}: unknown policy {policy!r}")
        if policy != "autonomous-reversible":
            errors.append(
                f"{source}.actions.{action_id}: pilot actions must be autonomous-reversible"
            )
        if not isinstance(action.get("command"), str) or not action["command"].strip():
            errors.append(f"{source}.actions.{action_id}: command is required")

    for route_id, route in routes.items():
        observations = route.get("when")
        if not isinstance(observations, list) or not observations:
            errors.append(f"{source}.routes.{route_id}: when must be a non-empty list")
            observations = []
        for index, observation in enumerate(observations):
            if not isinstance(observation, dict):
                errors.append(f"{source}.routes.{route_id}.when[{index}]: must be a mapping")
                continue
            signal_id = observation.get("signal")
            if signal_id not in signals:
                errors.append(
                    f"{source}.routes.{route_id}.when[{index}]: "
                    f"unknown signal {signal_id!r}"
                )
            if observation.get("outcome") not in {"success", "failure"}:
                errors.append(
                    f"{source}.routes.{route_id}.when[{index}]: "
                    "outcome must be success or failure"
                )

        action_id = route.get("action")
        if action_id not in actions:
            errors.append(f"{source}.routes.{route_id}: unknown action {action_id!r}")
        verify = route.get("verify")
        if not isinstance(verify, list) or not verify:
            errors.append(f"{source}.routes.{route_id}: verify must be a non-empty list")
        else:
            for signal_id in verify:
                if signal_id not in signals:
                    errors.append(
                        f"{source}.routes.{route_id}: unknown verify signal {signal_id!r}"
                    )
        if route.get("on_failure") != "escalate":
            errors.append(f"{source}.routes.{route_id}: on_failure must be 'escalate'")
        if not isinstance(route.get("hypothesis"), str) or not route["hypothesis"].strip():
            errors.append(f"{source}.routes.{route_id}: hypothesis is required")

    return errors


def build_eval_fixture(runbook: dict[str, Any]) -> dict[str, Any]:
    """Generate deterministic route fixtures from a validated runbook."""
    cases = [
        {
            "id": route["id"],
            "observations": route["when"],
            "expected": {
                "action": route["action"],
                "verify": route["verify"],
                "on_failure": route["on_failure"],
            },
        }
        for route in runbook["routes"]
    ]
    return {
        "runbook": runbook["id"],
        "schema_version": runbook["version"],
        "cases": cases,
    }


def discover_runbooks() -> list[tuple[Path, dict[str, Any]]]:
    """Discover Markdown runbooks containing structured blocks."""
    discovered: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(OPS_DIR.glob("*.md")):
        runbook = extract_runbook(path)
        if runbook is not None:
            discovered.append((path, runbook))
    return discovered


def _fixture_text(fixture: dict[str, Any]) -> str:
    return json.dumps(fixture, indent=2, sort_keys=True) + "\n"


def validate_all(write_fixtures: bool = False) -> list[str]:
    """Validate all structured runbooks and check or write their fixtures."""
    registry = load_registry()
    errors: list[str] = []
    discovered = discover_runbooks()
    if not discovered:
        return ["no structured operations runbooks found"]

    for path, runbook in discovered:
        source = path.relative_to(ROOT).as_posix()
        runbook_errors = validate_runbook(runbook, registry, source)
        errors.extend(runbook_errors)
        if runbook_errors:
            continue

        fixture_path = EVAL_DIR / f"{runbook['id']}.json"
        expected = _fixture_text(build_eval_fixture(runbook))
        if write_fixtures:
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.write_text(expected, encoding="utf-8")
        elif not fixture_path.exists():
            errors.append(f"{source}: missing eval fixture {fixture_path.relative_to(ROOT)}")
        elif fixture_path.read_text(encoding="utf-8") != expected:
            errors.append(
                f"{source}: stale eval fixture; run "
                "python scripts/validate_ops_runbooks.py --write-fixtures"
            )
    return errors


def main() -> int:
    """Run the command-line validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-fixtures",
        action="store_true",
        help="Regenerate committed route evaluation fixtures.",
    )
    args = parser.parse_args()
    errors = validate_all(write_fixtures=args.write_fixtures)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Operations runbooks are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
