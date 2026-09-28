"""Operate the cooperative local trial; failures leave the underlying task baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.agent_decision_trial import OutcomeEvent
from analysis.agent_decision_trial_cooperative import (
    DEFAULT_POLICY, CooperativeTrial, ReviewedDecision, canonical_store_path,
    load_cooperative_policy, new_task_key,
)
from analysis.agentic_task_routing import TaskRoute


def main() -> int:
    """Print JSON without automatically creating, resetting, or enrolling a cohort."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--test-policy", type=Path, help="Synthetic tests only; never a live alternate policy")
    parser.add_argument("--test-store", type=Path, help="Synthetic tests only; never a live alternate ledger")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "init", "new-task", "stop"):
        commands.add_parser(name)
    for name in ("admit", "card"):
        command = commands.add_parser(name)
        command.add_argument("--task-key", required=True)
        command.add_argument("--contract", type=Path, required=True)
        if name == "admit":
            command.add_argument("--resume", action="store_true")
        else:
            command.add_argument("--review", type=Path, required=True)
    outcome = commands.add_parser("outcome")
    outcome.add_argument("--task-key", required=True)
    outcome.add_argument("--event", type=Path, required=True, help="Coded OutcomeEvent JSON; no prose")
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("--review-digest", required=True, help="Reference to completed independent review")
    args = parser.parse_args()
    if bool(args.test_policy) != bool(args.test_store):
        parser.error("test policy and store must be supplied together")
    try:
        if args.command == "new-task":
            result = {"task_key": new_task_key(), "enrolled": False}
        else:
            policy = load_cooperative_policy(args.test_policy or DEFAULT_POLICY)
            path = args.test_store or canonical_store_path(args.repository, policy)
            trial = CooperativeTrial(path, policy)
            if args.command == "init":
                result = trial.initialize()
            elif args.command == "status":
                result = trial.status()
            elif args.command == "stop":
                result = trial.stop()
            elif args.command == "checkpoint":
                result = trial.checkpoint(args.review_digest)
            elif args.command == "outcome":
                event = OutcomeEvent.model_validate_json(args.event.read_text(encoding="utf-8"))
                result = trial.outcome(args.task_key, event)
            else:
                contract = TaskRoute.model_validate_json(args.contract.read_text(encoding="utf-8"))
                if args.command == "admit":
                    result = trial.admit(args.task_key, contract, resume=args.resume)
                else:
                    review = ReviewedDecision.model_validate_json(args.review.read_text(encoding="utf-8"))
                    result = trial.card(args.task_key, contract, review)
    except (OSError, ValueError, subprocess.SubprocessError):
        # Input may contain private text. Do not echo validation errors or paths.
        print(json.dumps({
            "reason": "unavailable_or_invalid", "presentation": "baseline",
            "enrolled": "unknown", "original_arm": "unknown", "card": None,
            "action": "continue underlying task; do not reset or reassign",
        }))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
