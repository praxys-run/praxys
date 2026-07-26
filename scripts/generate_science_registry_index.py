"""Generate the human-readable science evidence registry index."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.evidence_registry import (  # noqa: E402
    load_science_registry,
    render_registry_index,
)


def main() -> int:
    """Write the registry index, or verify that the checked-in copy is current."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when REGISTRY.md is stale",
    )
    args = parser.parse_args()

    target = PROJECT_ROOT / "data" / "science" / "REGISTRY.md"
    expected = render_registry_index(load_science_registry())
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    if args.check:
        if current != expected:
            print(
                "data/science/REGISTRY.md is stale; run "
                "python scripts/generate_science_registry_index.py",
                file=sys.stderr,
            )
            return 1
        return 0

    target.write_text(expected, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
