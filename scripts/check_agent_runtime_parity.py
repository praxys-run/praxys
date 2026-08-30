"""Check the Codex and Copilot adapters against one canonical contract."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.agent_runtime_parity import (
    load_runtime_parity_config,
    validate_static_runtime_parity,
)


def main() -> int:
    """Report all deterministic runtime-adapter violations."""
    config = load_runtime_parity_config()
    errors = validate_static_runtime_parity(config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Codex/Copilot runtime parity contract passed (static).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
