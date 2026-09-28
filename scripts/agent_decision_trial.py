"""Display the inert decision-card trial policy without enrolling any tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.agent_decision_trial import load_trial_policy, policy_digest


def main() -> int:
    """Fail loudly if the repository manifest is corrupt or unexpectedly active."""
    argparse.ArgumentParser(
        description="Inspect the disabled decision-card trial; cannot enroll tasks."
    ).parse_args()
    try:
        policy = load_trial_policy()
    except (OSError, ValueError) as error:
        print(f"trial unavailable: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "cohort_id": policy.cohort_id,
        "policy_digest": policy_digest(policy),
        "status": policy.status,
        "can_enroll": False,
        "reason": "trusted entrypoint and shared store not installed",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
