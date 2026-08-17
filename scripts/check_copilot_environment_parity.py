"""Check Local and Cloud Copilot entry points, agents, and common tools."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.copilot_execution_parity import (
    load_execution_parity_config,
    read_live_cloud_configuration,
    validate_live_cloud_mcp,
    validate_static_execution_parity,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Praxys Local and Cloud Copilot execution parity."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also compare authenticated GitHub Cloud MCP settings.",
    )
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPOSITORY"),
        help="OWNER/REPO used with --live.",
    )
    return parser


def main() -> int:
    """Run static checks and the optional authenticated live drift check."""
    args = _parser().parse_args()
    config = load_execution_parity_config()
    errors = validate_static_execution_parity(config)
    if args.live:
        if not args.repo:
            errors.append("--live requires --repo or GITHUB_REPOSITORY")
        else:
            live_payload = read_live_cloud_configuration(args.repo)
            errors.extend(validate_live_cloud_mcp(live_payload, config))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    scope = "static and live" if args.live else "static"
    print(f"Copilot execution parity passed ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
