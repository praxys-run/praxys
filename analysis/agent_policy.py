"""Pure decision policies used by the shared agent-loop substrate."""
from __future__ import annotations

from dataclasses import dataclass


AGENT_READY_POLICY_NAME = "change.agent_ready"
AGENT_READY_POLICY_VERSION = "agent-ready-v2"
AGENT_MIN_DETAIL_WORDS = 6
AGENT_MIN_DETAIL_ALNUM_CHARS = 16


@dataclass(frozen=True)
class AgentReadyFacts:
    """Structured inputs for the deterministic change-loop assignment gate."""

    kind: str
    gate_blocked: bool
    agent_eligible: bool
    detail_word_count: int
    detail_alnum_count: int


@dataclass(frozen=True)
class AgentReadyDecision:
    """Decision and stable reason emitted by the assignment gate."""

    eligible: bool
    reason: str


def message_detail_counts(message: str) -> tuple[int, int]:
    """Return language-aware detail counts without retaining message text."""
    return len(message.split()), sum(character.isalnum() for character in message)


def has_enough_detail(word_count: int, alnum_count: int) -> bool:
    """Return whether language-aware detail counts clear the assignment floor."""
    return (
        word_count >= AGENT_MIN_DETAIL_WORDS
        or alnum_count >= AGENT_MIN_DETAIL_ALNUM_CHARS
    )


def evaluate_agent_ready(facts: AgentReadyFacts) -> AgentReadyDecision:
    """Classify whether a triaged report may enter the coding-agent loop."""
    if facts.kind != "bug":
        return AgentReadyDecision(False, "not_bug")
    if facts.gate_blocked:
        return AgentReadyDecision(False, "sensitivity_gate")
    if not facts.agent_eligible:
        return AgentReadyDecision(False, "not_actionable")
    if not has_enough_detail(
        facts.detail_word_count,
        facts.detail_alnum_count,
    ):
        return AgentReadyDecision(False, "insufficient_detail")
    return AgentReadyDecision(True, "eligible")
