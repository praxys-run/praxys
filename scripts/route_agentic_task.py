"""Summarize Praxys task risk without dispatching agents or requesting approval."""

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
            "Summarize one classified Praxys task using the checked-in "
            "single-session policy."
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
    return "\n".join([
        "# Praxys execution summary",
        "",
        f"- Mode: {payload['execution_mode']}",
        f"- Executor: {payload['executor_agent']}",
        f"- Reviewer: {payload['reviewer_agent'] or 'none'}",
        f"- Context: {', '.join(payload['contexts']) or 'repository conventions'}",
        f"- Check existing authority for: {', '.join(payload['authority_checks']) or 'none'}",
        f"- Policy/output digest: {payload['route_digest']}",
        "",
        "Authority checks are not approval requests or grants. Reuse existing scoped authorization.",
    ])


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
