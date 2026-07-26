"""Replay checked-in agent policy cases and fail on deterministic regression."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.agent_policy import (  # noqa: E402
    AGENT_READY_POLICY_NAME,
    AGENT_READY_POLICY_VERSION,
)
from analysis.agent_replay import replay_agent_ready_cases  # noqa: E402


CORPUS = ROOT / "data" / "agent_evals" / "change" / "agent_ready.json"


def main() -> int:
    """Run the checked-in change-loop replay corpus."""
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    if payload["policy_name"] != AGENT_READY_POLICY_NAME:
        raise ValueError("Replay corpus policy name does not match production")
    if payload["policy_version"] != AGENT_READY_POLICY_VERSION:
        raise ValueError("Replay corpus policy version does not match production")
    result = replay_agent_ready_cases(payload["cases"])
    print(
        json.dumps(
            {
                "policy": payload["policy_name"],
                "version": payload["policy_version"],
                "total": result.total,
                "correct": result.correct,
                "accuracy": result.accuracy,
                "false_positives": result.false_positives,
                "false_negatives": result.false_negatives,
            },
            sort_keys=True,
        )
    )
    return int(result.correct != result.total)


if __name__ == "__main__":
    raise SystemExit(main())
