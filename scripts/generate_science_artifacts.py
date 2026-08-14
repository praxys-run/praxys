"""Generate human review packets and machine science contracts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.evidence_registry import load_science_registry  # noqa: E402
from analysis.science_artifacts import sync_science_artifacts  # noqa: E402


def main() -> int:
    """Write generated science artifacts or verify checked-in copies."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when generated artifacts are stale",
    )
    args = parser.parse_args()

    registry = load_science_registry()
    stale = sync_science_artifacts(registry, check=args.check)
    if args.check and stale:
        print(
            "Generated science artifacts are stale:\n"
            + "\n".join(f"- data/science/{path.as_posix()}" for path in stale)
            + "\nRun python scripts/generate_science_artifacts.py",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
