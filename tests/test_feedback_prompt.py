"""Regression coverage for versioned feedback-triage prompts."""
from __future__ import annotations

import json

import pytest

from api import feedback_prompt
from db.agent_loop import canonical_json_hash


def test_active_prompt_preserves_production_fingerprint() -> None:
    """Extracting the prompt must not silently change active behavior."""
    assert feedback_prompt.ACTIVE_TRIAGE_PROMPT_VERSION == "v1"
    assert (
        canonical_json_hash(feedback_prompt.system_prompt("v1"))[:16]
        == "02885290c95ddf28"
    )


def test_challenger_separates_priority_from_agent_eligibility() -> None:
    """Low priority and bounded cosmetic defects remain agent-eligible."""
    prompt = feedback_prompt.system_prompt("v2").lower()
    assert "priority and agent eligibility as independent decisions" in prompt
    assert "low-priority bug can still be agent-eligible" in prompt
    assert "overflow, clipping, spacing, or incorrect formatting" in prompt
    assert "does not authorize merge" in prompt


def test_challenger_payload_adds_only_scrubbed_screenshot_evidence() -> None:
    """The active payload stays stable while v2 can use verified image context."""
    active = json.loads(
        feedback_prompt.user_payload(
            version="v1",
            kind="bug",
            message="Text overflows",
            context={"page": "/training"},
            image_description="A narrow calendar cell clips its status label.",
        )
    )
    challenger = json.loads(
        feedback_prompt.user_payload(
            version="v2",
            kind="bug",
            message="Text overflows",
            context={"page": "/training"},
            image_description="A narrow calendar cell clips its status label.",
        )
    )
    assert active == {
        "reported_kind": "bug",
        "message": "Text overflows",
        "context": {"page": "/training"},
    }
    assert challenger["screenshot_description"].startswith("A narrow calendar")


def test_model_output_parser_matches_production_contract() -> None:
    """Eligibility is trusted only with a usable title and body."""
    assert (
        feedback_prompt.parse_model_output(
            ["not", "an", "object"],
            fallback_kind="other",
        )
        is None
    )
    assert (
        feedback_prompt.parse_model_output(
            {"kind": "bug", "title": "", "body": "Body"},
            fallback_kind="other",
        )
        is None
    )
    parsed = feedback_prompt.parse_model_output(
        {
            "kind": "bug",
            "title": "Calendar text overflows",
            "body": "The status label leaves its day card.",
            "contains_sensitive": False,
            "priority": "low",
            "agent_eligible": True,
        },
        fallback_kind="other",
    )
    assert parsed is not None
    assert parsed.priority == "low"
    assert parsed.agent_eligible is True


def test_publication_privacy_review_is_separate_and_fail_closed() -> None:
    prompt = feedback_prompt.publication_privacy_review_prompt().lower()
    payload = json.loads(
        feedback_prompt.publication_privacy_review_payload(
            title="Calendar clips text",
            body="The calendar status leaves its card.",
        )
    )

    assert feedback_prompt.PUBLICATION_PRIVACY_REVIEW_VERSION == "v1"
    assert "final privacy reviewer" in prompt
    assert "unsure, return false" in prompt
    assert feedback_prompt.publication_privacy_review_digest().startswith("sha256:")
    assert payload == {
        "title": "Calendar clips text",
        "body": "The calendar status leaves its card.",
    }
    assert (
        feedback_prompt.parse_publication_privacy_review(
            {"safe_to_publish": True}
        )
        is True
    )
    assert (
        feedback_prompt.parse_publication_privacy_review(
            {"safe_to_publish": False}
        )
        is False
    )


@pytest.mark.parametrize(
    "result",
    (
        None,
        {},
        {"safe_to_publish": 0},
        {"safe_to_publish": "false"},
        {"safe_to_publish": True, "reason": "extra"},
    ),
)
def test_publication_privacy_review_rejects_non_exact_results(result) -> None:
    assert feedback_prompt.parse_publication_privacy_review(result) is None
