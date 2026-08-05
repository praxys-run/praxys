"""Pure replay helpers for versioned agent decision policies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from analysis.agent_policy import AgentReadyFacts, evaluate_agent_ready


@dataclass(frozen=True)
class ReplayResult:
    """Aggregate replay score for a deterministic policy corpus."""

    total: int
    correct: int
    false_positives: int
    false_negatives: int

    @property
    def accuracy(self) -> float:
        """Return the fraction of replay cases classified correctly."""
        return self.correct / self.total if self.total else 0.0


@dataclass(frozen=True)
class ModelReplayResult:
    """Aggregate score for semantic model predictions."""

    total: int
    evaluated: int
    correct: int
    false_positives: int
    false_negatives: int
    unavailable: int

    @property
    def accuracy(self) -> float:
        """Return accuracy across model responses that were available."""
        return self.correct / self.evaluated if self.evaluated else 0.0


def replay_agent_ready_cases(cases: Iterable[dict[str, Any]]) -> ReplayResult:
    """Replay structured agent-ready cases without file or network I/O."""
    total = correct = false_positives = false_negatives = 0
    for case in cases:
        facts = AgentReadyFacts(**case["facts"])
        actual = evaluate_agent_ready(facts).eligible
        expected = bool(case["expected"])
        total += 1
        correct += int(actual == expected)
        false_positives += int(actual and not expected)
        false_negatives += int(expected and not actual)
    return ReplayResult(
        total=total,
        correct=correct,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


def replay_agent_eligibility_cases(
    cases: Iterable[dict[str, Any]],
    predict: Callable[[dict[str, Any]], bool | None],
) -> ModelReplayResult:
    """Score semantic agent-eligibility predictions without performing I/O."""
    total = evaluated = correct = false_positives = false_negatives = unavailable = 0
    for case in cases:
        expected = bool(case["expected_agent_eligible"])
        actual = predict(case)
        total += 1
        if actual is None:
            unavailable += 1
            continue
        evaluated += 1
        correct += int(actual == expected)
        false_positives += int(actual and not expected)
        false_negatives += int(expected and not actual)
    return ModelReplayResult(
        total=total,
        evaluated=evaluated,
        correct=correct,
        false_positives=false_positives,
        false_negatives=false_negatives,
        unavailable=unavailable,
    )
