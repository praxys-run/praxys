"""Vision triage for feedback screenshots (issue #337).

Given the user's attached screenshot(s), a vision-capable Azure OpenAI model:

  (a) extracts a factual, PII-free, debugging-focused description of what's shown
      (which screen, the affected component, visible error text, what looks
      broken) for the private admin support path. Neither that description nor
      the raw image leaves the private plane (issue #337), and
  (b) flags whether the image contains sensitive content (faces, emails, names,
      health / performance data) — a verdict that feeds the same sensitivity
      gate as the text path in :mod:`api.feedback_triage`.

The raw image and derived description are NEVER published. When no vision model
is configured (:func:`api.llm.get_client` returns None) this returns ``None``
and the triage step treats the unanalysed image as unsafe, parking the report
for admin review.
"""
from __future__ import annotations

import base64
import logging
import os

from api import llm

logger = logging.getLogger(__name__)

# Reuse the reasoning deployment by default — the gpt-5.x / gpt-4o families are
# multimodal. Override with PRAXYS_VISION_MODEL if the vision deployment differs.
VISION_MODEL = os.environ.get("PRAXYS_VISION_MODEL", llm.INSIGHT_MODEL)

# Defensive cap on images sent to the model (the route already enforces
# MAX_IMAGE_COUNT before anything is stored).
_MAX_VISION_IMAGES = 3


def _system_prompt() -> str:
    return (
        "You are a vision triage assistant for Praxys, an endurance-training "
        "analytics app. A user attached one or more screenshots to a bug report. "
        "Look at the image(s) and:\n"
        "- Write a THOROUGH, factual description of what the screenshot shows, "
        "written so an authorized support engineer can diagnose the problem "
        "from the private admin view. Capture: which screen / page / route; the "
        "specific UI component or element affected; any visible error text, "
        "codes, or stack traces (transcribe verbatim EXCEPT personal data — see "
        "below); and exactly what looks wrong or broken (layout, rendering, "
        "empty / incorrect state, styling). Be specific and complete on technical "
        "detail; never invent anything not visible.\n"
        "- Do NOT transcribe personal data. If you see an email, a person's name, "
        "a face, or the user's own health / training numbers, refer to them "
        "generically (e.g. 'the user's email', 'a profile photo') — never copy "
        "the value into your description.\n"
        "- Set contains_sensitive=true if the image shows any of: a human face, an "
        "email address, a person's name, or personal health / performance data "
        "(heart rate, power, weight, training history tied to an identifiable "
        "person). A generic error dialog or an empty / broken chart is NOT "
        "sensitive.\n"
        "Respond with a JSON object: "
        "{\"description\": str, \"contains_sensitive\": bool}."
    )


def _to_data_url(data: bytes, content_type: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{content_type};base64,{b64}"


def analyze_images(images: list[tuple[bytes, str]]) -> dict | None:
    """Describe + sensitivity-flag screenshot(s). Returns a dict or ``None``.

    Args:
        images: ``(bytes, content_type)`` for each screenshot.

    Returns:
        ``{"description": str, "sensitive": bool}`` on success, or ``None`` when
        no vision model is configured, the call fails, or the sensitivity field
        is not a native JSON boolean.
    """
    if not images:
        return None
    client = llm.get_client()
    if client is None:
        return None
    data_urls = [_to_data_url(d, ct) for d, ct in images[:_MAX_VISION_IMAGES] if d]
    if not data_urls:
        return None
    result = llm.chat_json(
        client,
        system=_system_prompt(),
        user=(
            "Describe the attached screenshot(s) and flag sensitivity per the "
            f"rules. There are {len(data_urls)} image(s)."
        ),
        model=VISION_MODEL,
        # Richer budget: the description helps an authorized support engineer
        # diagnose the private screenshot without copying it to a public issue.
        max_completion_tokens=1200,
        # Deterministic: triage/classification shouldn't vary run-to-run.
        temperature=0.0,
        images=data_urls,
        insight_type="feedback_vision",
    )
    if not result or not isinstance(result.get("description"), str):
        return None
    description = result["description"].strip()
    if not description:
        return None
    raw_sensitive = result.get("contains_sensitive")
    if not isinstance(raw_sensitive, bool):
        return None
    return {
        "description": description,
        "sensitive": raw_sensitive,
    }
