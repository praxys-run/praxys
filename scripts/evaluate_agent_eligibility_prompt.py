"""Evaluate one versioned feedback prompt against the semantic corpus."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from analysis.agent_replay import replay_agent_eligibility_cases  # noqa: E402
from api import feedback_prompt, llm  # noqa: E402
from db.agent_loop import canonical_json_hash  # noqa: E402


CORPUS = ROOT / "data" / "agent_evals" / "change" / "agent_eligibility.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prompt-version",
        required=True,
        choices=(
            feedback_prompt.ACTIVE_TRIAGE_PROMPT_VERSION,
            *feedback_prompt.CHALLENGER_TRIAGE_PROMPT_VERSIONS,
        ),
    )
    parser.add_argument("--model", default=llm.INSIGHT_MODEL)
    return parser.parse_args()


def main() -> int:
    """Run the live model against privacy-reviewed semantic examples."""
    args = _parse_args()
    client = llm.get_automation_client()
    if client is None:
        print("Azure OpenAI is not configured", file=sys.stderr)
        return 2

    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = payload["cases"]
    predictions: dict[str, bool | None] = {}

    def predict(case: dict[str, Any]) -> bool | None:
        result = llm.chat_json(
            client,
            system=feedback_prompt.system_prompt(args.prompt_version),
            user=feedback_prompt.user_payload(
                version=args.prompt_version,
                kind=case["reported_kind"],
                message=case["message"],
                context=case.get("context") or {},
                image_description=case.get("image_description"),
            ),
            model=args.model,
            max_completion_tokens=1200,
            temperature=0.0,
            insight_type="feedback_triage_eval",
        )
        parsed = feedback_prompt.parse_model_output(
            result,
            fallback_kind=case["reported_kind"],
        )
        actual = parsed.agent_eligible if parsed is not None else None
        predictions[case["id"]] = actual
        return actual

    result = replay_agent_eligibility_cases(cases, predict)
    mismatches = [
        {
            "id": case["id"],
            "expected": bool(case["expected_agent_eligible"]),
            "actual": predictions[case["id"]],
        }
        for case in cases
        if predictions[case["id"]] is not None
        and predictions[case["id"]]
        != bool(case["expected_agent_eligible"])
    ]
    unavailable_cases = [
        case["id"] for case in cases if predictions[case["id"]] is None
    ]
    print(
        json.dumps(
            {
                "prompt_family": payload["prompt_family"],
                "prompt_version": args.prompt_version,
                "prompt_hash": canonical_json_hash(
                    feedback_prompt.system_prompt(args.prompt_version)
                )[:16],
                "model": args.model,
                "total": result.total,
                "evaluated": result.evaluated,
                "correct": result.correct,
                "accuracy": result.accuracy,
                "false_positives": result.false_positives,
                "false_negatives": result.false_negatives,
                "unavailable": result.unavailable,
                "mismatches": mismatches,
                "unavailable_cases": unavailable_cases,
            },
            sort_keys=True,
        )
    )
    return int(
        result.unavailable > 0
        or result.false_positives > 0
        or result.false_negatives > 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
