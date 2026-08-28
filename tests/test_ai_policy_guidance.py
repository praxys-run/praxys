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


def test_operations_guidance_keeps_ai_available_and_publication_disabled() -> None:
    environment = _read("docs/ops/environment.md")
    config = _read("docs/ops/config-and-secrets.md")

    assert "leaves ordinary\n  Azure AI available" in environment
    assert "External feedback publication remains\n  fixed disabled" in environment
    assert "four fixed runtime settings" in config
    assert "optional_processing.background_ai_enabled=true" in config
    assert "feedback-publication enablement `false`" in config
    assert "four optional-processing controls" not in config
    assert "five fixed non-secret privacy settings" not in config
