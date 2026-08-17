"""Render a deterministic Praxys work contract from bounded task traits."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.agentic_task_routing import (
    TaskClassification,
    load_task_routing_config,
    route_task,
)


def _parser() -> argparse.ArgumentParser:
    config = load_task_routing_config()
    parser = argparse.ArgumentParser(
        description=(
            "Route one classified Praxys task through the checked-in "
            "agentic operating model."
        )
    )
    parser.add_argument(
        "--primary-object",
        required=True,
        choices=list(config.primary_objects),
    )
    parser.add_argument(
        "--impact",
        action="append",
        default=[],
        choices=list(config.impacts),
    )
    parser.add_argument(
        "--risk-trigger",
        action="append",
        default=[],
        choices=config.risk_triggers,
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    return parser


def _markdown(route: object) -> str:
    payload = route.model_dump()

    def values(key: str) -> str:
        items = payload[key]
        return ", ".join(items) if items else "none"

    loop_agents = ", ".join(
        f"{loop_id} -> {path}"
        for loop_id, path in payload["loop_agents"].items()
    )
    return "\n".join(
        [
            "# Praxys Work Contract",
            "",
            f"- Route digest: `{payload['route_digest']}`",
            f"- Classification digest: `{payload['classification_digest']}`",
            f"- Primary object: `{payload['classification']['primary_object']}`",
            f"- Primary loop: `{payload['primary_loop']}`",
            f"- Nested loops: {values('nested_loops')}",
            f"- Loop agents: {loop_agents}",
            f"- Lead role: `{payload['lead_role']}`",
            f"- Contributors: {values('contributor_roles')}",
            f"- Executors: {values('executor_roles')}",
            f"- Verifiers: {values('verifier_roles')}",
            f"- Outcome observers: {values('outcome_observer_roles')}",
            f"- Required input artifacts: {values('required_input_artifacts')}",
            f"- Required output artifacts: {values('required_artifacts')}",
            f"- Outcome artifacts: {values('outcome_artifacts')}",
            f"- Risk triggers: {values('risk_triggers')}",
            f"- Decision review agent: `{payload['decision_review_agent']}`",
            "- Decision review required: "
            f"`{str(payload['decision_review_required']).lower()}`",
        ]
    )


def main() -> int:
    """Parse bounded traits and print the canonical work contract."""
    args = _parser().parse_args()
    route = route_task(
        TaskClassification(
            primary_object=args.primary_object,
            impacts=args.impact,
            risk_triggers=args.risk_trigger,
        )
    )
    if args.format == "markdown":
        print(_markdown(route))
    else:
        print(route.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
