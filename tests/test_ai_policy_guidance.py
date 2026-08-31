"""Static regressions for the mandatory Azure AI/outage documentation contract."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_primary_guidance_keeps_ai_mandatory_and_deterministic_output_separate() -> None:
    agents = _read("AGENTS.md")
    claude = _read("CLAUDE.md")
    design = _read("docs/dev/design-system.md")

    assert "not an optional enhancement" in agents
    assert "AI-only features report unavailable" in agents
    assert "deterministic content is never presented as AI" in agents

    assert "mandatory ordinary-production capability" in claude
    assert "AI-only features explicitly report unavailable" in claude
    assert "Never present deterministic output as Coach/AI output" in claude

    assert "explicit AI unavailability" in design
    assert "separately labelled companion" in design
    assert "never a Coach/AI fallback or AI output" in design

    for stale_claim in (
        "AI remains optional with deterministic fallbacks",
        "AI features are always optional",
        "LLM insight runner falls back to rule-based prose",
        "durable AI insights with rule-based fallbacks",
    ):
        assert stale_claim not in agents
        assert stale_claim not in claude
        assert stale_claim not in design


def test_operations_guidance_preserves_ai_stop_and_disables_publication() -> None:
    environment = _read("docs/ops/environment.md")
    config = _read("docs/ops/config-and-secrets.md")

    assert "observe and preserve that explicit setting" in environment
    assert "feedback publication remains separately controlled" in environment
    assert "It never toggles Azure AI" in config
    assert "`PRAXYS_DISABLE_BACKGROUND_AI=false`" in config
    assert "`PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false`" in config
    assert "`PRAXYS_DISABLE_FEEDBACK_PUBLICATION=true`" in config
    assert "exact per-submission publication" in config
    assert "four optional-processing controls" not in config
    assert "five fixed non-secret privacy settings" not in config
