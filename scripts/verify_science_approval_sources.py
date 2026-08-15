"""Verify that science approval changes have authenticated human sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.science_approval_workflow import (  # noqa: E402
    verify_science_approval_changes,
)


def main() -> int:
    """Verify approval artifacts, lifecycle transitions, and generated files."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-science-dir", type=Path, required=True)
    parser.add_argument("--head-science-dir", type=Path, required=True)
    parser.add_argument("--github-comments", type=Path, required=True)
    parser.add_argument("--github-permissions", type=Path, required=True)
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

    verify_science_approval_changes(
        args.base_science_dir,
        args.head_science_dir,
        comments,
        permissions,
    )
    print("Science approval sources and lifecycle transitions are verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
