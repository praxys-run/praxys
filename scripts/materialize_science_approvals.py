"""Materialize explicit human science approvals into repository artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.science_approval_workflow import (  # noqa: E402
    approvals_from_github_comments,
    materialize_science_approvals,
)


def main() -> int:
    """Record verified approvals and regenerate their lifecycle artifacts."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--science-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "science",
    )
    parser.add_argument(
        "--github-comments",
        type=Path,
        required=True,
        help="JSON array returned by the GitHub issue-comments API",
    )
    parser.add_argument(
        "--github-permissions",
        type=Path,
        required=True,
        help="JSON object mapping GitHub login to repository permission",
    )
    args = parser.parse_args()

    comments = json.loads(
        args.github_comments.read_text(encoding="utf-8")
    )
    permissions = json.loads(
        args.github_permissions.read_text(encoding="utf-8")
    )
    if not isinstance(comments, list):
        parser.error("--github-comments must contain a JSON array")
    if not isinstance(permissions, dict):
        parser.error("--github-permissions must contain a JSON object")
    approvals = approvals_from_github_comments(
        args.science_dir,
        comments,
        permissions,
    )

    if not approvals:
        print("No eligible science approvals found.")
        return 0

    changed = materialize_science_approvals(
        args.science_dir,
        approvals,
    )
    if not changed:
        print("Science approvals are already materialized.")
        return 0
    print("Materialized science approvals:")
    for path in changed:
        print(f"- data/science/{path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
