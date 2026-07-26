"""Validate selective-review promotions against checked-in outcome evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.review_policy import (  # noqa: E402
    class_policy_fingerprint,
    validate_promoted_classes,
)


POLICY_PATH = ROOT / "config" / "agent-loop-policies.json"
EVIDENCE_PATH = ROOT / "data" / "agent_evals" / "change" / "review_promotion.json"


def main() -> int:
    """Validate promoted classes and print a machine-readable summary."""
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    assessments = validate_promoted_classes(policy, evidence)
    selective = policy["change"]["selective_review"]
    print(
        json.dumps(
            {
                "promoted_classes": sorted(assessments),
                "eligible": True,
                "candidate_fingerprints": {
                    name: class_policy_fingerprint(selective, name)
                    for name in sorted(selective["candidate_classes"])
                },
                "assessments": {
                    name: {
                        "eligible": result.eligible,
                        "reasons": result.reasons,
                        "metrics": result.metrics,
                    }
                    for name, result in assessments.items()
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
