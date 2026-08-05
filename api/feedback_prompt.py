"""Versioned prompts and response parsing for feedback triage."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


ACTIVE_TRIAGE_PROMPT_VERSION = "v1"
CHALLENGER_TRIAGE_PROMPT_VERSIONS = ("v2",)

_VALID_KINDS = {"bug", "feature", "other"}
_VALID_PRIORITIES = {"low", "medium", "high", "critical"}

_ELIGIBILITY_V1 = (
    "- Set agent_eligible=true ONLY for a bug that is a genuine, "
    "reproducible product DEFECT, specific and self-contained enough that a "
    "coding agent could reasonably attempt a fix from this report alone. Set "
    "it false for anything not clearly a defect we would act on: a feature "
    "request or idea, a how-to / support question, expected behavior or user "
    "error, a vague or unreproducible complaint, or anything needing human "
    "product judgment or more information. When kind is not bug, "
    "agent_eligible MUST be false. Default to false when unsure, and ALWAYS "
    "include the agent_eligible field.\n"
)

_ELIGIBILITY_V2 = (
    "- Treat priority and agent eligibility as independent decisions. Priority "
    "orders work; it MUST NOT decide whether a coding agent can attempt it. A "
    "low-priority bug can still be agent-eligible.\n"
    "- Set agent_eligible=true ONLY for a genuine, reproducible product DEFECT "
    "that is specific and self-contained enough for a coding agent to attempt "
    "a bounded fix from this report alone. Reproducible cosmetic UI defects "
    "such as overflow, clipping, spacing, or incorrect formatting are eligible "
    "when the affected surface and expected behavior are clear. This judgment "
    "does not authorize merge.\n"
    "- Set agent_eligible=false for a feature request or idea, a how-to or "
    "support question, expected behavior or user error, a vague or "
    "unreproducible complaint, or anything needing human product judgment or "
    "more information. When kind is not bug, agent_eligible MUST be false. "
    "Default to false when unsure, and ALWAYS include the agent_eligible field.\n"
)

_SYSTEM_PROMPT_V1 = (
    "You are a triage assistant for Praxys, an endurance-training analytics app. "
    "You convert a user's in-app feedback into a clean, actionable GitHub issue "
    "for an engineering team and AI coding agents.\n\n"
    "Rules:\n"
    "- The input has already been PII-scrubbed; if you still see anything that "
    "looks like personal data (emails, names, tokens, IPs), do NOT reproduce it.\n"
    "- Write a concise, specific issue title (<=80 chars, no trailing period).\n"
    "- Write a structured Markdown body with sections: a one-line summary, "
    "'Steps to reproduce' or 'Expected behavior' for bugs, 'Proposed change' "
    "for features, and an 'Environment' bullet list from the provided context.\n"
    "- Be factual; do not invent details the user didn't provide.\n"
    "- Classify the report as exactly one kind: bug, feature, or other.\n"
    "- The input is ALREADY PII-scrubbed (emails, tokens, keys, IPs, file "
    "paths, and long numbers are removed and shown as [redacted-*]). Set "
    "contains_sensitive=true ONLY if the report STILL clearly contains "
    "personal data, health details about an identifiable person, account or "
    "credential information, or private third-party info unsuitable for a "
    "public tracker. A normal product bug report or feature request is NOT "
    "sensitive — return false. Default to false, and ALWAYS include the "
    "contains_sensitive field in your response.\n"
    "- Assign a triage priority as exactly one of: low, medium, high, "
    "critical. Judge by user impact and urgency: critical = data loss, a "
    "security problem, or the app is unusable for many users; high = a core "
    "feature is broken or a workflow is blocked; medium = a limited or "
    "non-blocking bug, or a valuable feature request; low = minor polish, "
    "cosmetic issues, or nice-to-have ideas. Default to medium when unsure. "
    "ALWAYS include the priority field.\n"
    + _ELIGIBILITY_V1
    + "Respond with a JSON object: "
    "{\"kind\": str, \"title\": str, \"body\": str, "
    "\"contains_sensitive\": bool, \"priority\": str, "
    "\"agent_eligible\": bool}."
)

_SYSTEM_PROMPT_V2 = _SYSTEM_PROMPT_V1.replace(
    _ELIGIBILITY_V1,
    _ELIGIBILITY_V2,
    1,
)


@dataclass(frozen=True)
class TriageModelOutput:
    """Validated structured response from the feedback triage model."""

    kind: str
    title: str
    body: str
    contains_sensitive: bool
    priority: str | None
    agent_eligible: bool | None


def system_prompt(version: str = ACTIVE_TRIAGE_PROMPT_VERSION) -> str:
    """Return one versioned feedback-triage system prompt."""
    if version == "v1":
        return _SYSTEM_PROMPT_V1
    if version == "v2":
        return _SYSTEM_PROMPT_V2
    raise ValueError(f"Unsupported feedback triage prompt version: {version}")


def user_payload(
    *,
    version: str,
    kind: str,
    message: str,
    context: dict[str, Any],
    image_description: str | None = None,
) -> str:
    """Build the versioned, already-scrubbed model input."""
    payload: dict[str, Any] = {
        "reported_kind": kind,
        "message": message,
        "context": context,
    }
    if version == "v2" and image_description:
        payload["screenshot_description"] = image_description
    elif version != "v1" and version not in CHALLENGER_TRIAGE_PROMPT_VERSIONS:
        raise ValueError(f"Unsupported feedback triage prompt version: {version}")
    return json.dumps(payload, ensure_ascii=False)


def parse_model_output(
    result: Any,
    *,
    fallback_kind: str,
) -> TriageModelOutput | None:
    """Validate a model response using the production triage contract."""
    if not isinstance(result, dict) or not result:
        return None
    title = result.get("title")
    body = result.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        return None
    title = title.strip()
    body = body.strip()
    if not title or not body:
        return None

    candidate_kind = str(result.get("kind", "")).lower()
    kind = candidate_kind if candidate_kind in _VALID_KINDS else fallback_kind
    candidate_priority = str(result.get("priority", "")).strip().lower()
    priority = (
        candidate_priority if candidate_priority in _VALID_PRIORITIES else None
    )
    raw_agent_eligible = result.get("agent_eligible")
    agent_eligible = (
        raw_agent_eligible if isinstance(raw_agent_eligible, bool) else None
    )
    return TriageModelOutput(
        kind=kind,
        title=title,
        body=body,
        contains_sensitive=bool(result.get("contains_sensitive", True)),
        priority=priority,
        agent_eligible=agent_eligible,
    )


def resolve_challenger_prompt_version(raw: str | None) -> str | None:
    """Return a supported challenger version, otherwise keep it disabled."""
    normalized = (raw or "").strip().lower()
    if normalized in CHALLENGER_TRIAGE_PROMPT_VERSIONS:
        return normalized
    return None
