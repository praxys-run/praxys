"""Background triage for user feedback: scrub → classify → publish.

Pipeline (runs as a FastAPI ``BackgroundTask`` after the submit returns):

1. Load the :class:`db.models.Feedback` row in its *own* DB session — the
   request session is closed by the time a background task runs. (Same
   transaction-ownership pattern as :mod:`api.insights_runner`.)
2. Deterministically scrub the raw message + context (:mod:`api.feedback_scrub`).
3. If Azure OpenAI is configured, ask the model to turn the scrubbed report
   into a clean issue title + structured markdown body and to confirm the
   ``kind``. The model only ever sees already-scrubbed text. When the model
   is unavailable, a deterministic rule-based title/body is used instead.
4. Run the final title + body through the scrubber *again* (we never trust the
   model as the sole redactor for a public repo).
5. If GitHub is configured, open an issue (labeled so an agent can pick it up)
   and record the number/url. Otherwise leave the row ``triaged`` for an admin
   to promote from the Admin page.

Nothing here raises: a failure marks the row ``failed`` with a short error and
returns. The submit endpoint already returned 200 to the user.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from analysis.agent_policy import (
    AGENT_READY_POLICY_NAME,
    AGENT_READY_POLICY_VERSION,
    AgentReadyFacts,
    evaluate_agent_ready,
    has_enough_detail,
    message_detail_counts,
)
from api import (
    feedback_scrub,
    feedback_storage,
    feedback_vision,
    github_issues,
    llm,
    telemetry,
)
from db.agent_loop import (
    canonical_json_hash,
    record_decision,
    record_outcome,
)

logger = logging.getLogger(__name__)

# Stable English labels the frontend / agents key off. Kind → GitHub label.
_KIND_LABEL = {"bug": "bug", "feature": "enhancement", "other": "feedback"}
_VALID_KINDS = set(_KIND_LABEL)

# Triage priority buckets the LLM assigns (low → critical). Kept as a stable
# English set the admin UI / GitHub labels key off.
_VALID_PRIORITIES = {"low", "medium", "high", "critical"}

_TRIAGE_MODEL = llm.INSIGHT_MODEL


def _autofile_without_ai() -> bool:
    """Whether to auto-file to the public tracker when the LLM gate is absent.

    Off by default: with no AI to judge residual sensitivity, holding for an
    admin is the safe choice for a public repo. An operator who accepts the
    scrub-only risk can set PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI=true.
    """
    return (os.environ.get("PRAXYS_FEEDBACK_AUTOFILE_WITHOUT_AI", "") or "").lower() in ("1", "true", "yes")


def _gate_blocks_publish(
    *,
    used_llm: bool,
    llm_flag: bool,
    body: str,
    has_image: bool = False,
    image_sensitive: Optional[bool] = None,
) -> bool:
    """Decide whether to withhold a report from auto-opening a public issue.

    Blocks when: (a) the scrubber removed a key/token — a strong signal the
    user pasted a secret; (b) an attached screenshot was flagged sensitive by
    the vision model, or is present but could not be vision-verified
    (``image_sensitive is None``) — an unread image is unsafe to auto-publish;
    (c) the LLM judged the text report still sensitive; or (d) there is no LLM
    verdict and the operator hasn't opted into scrub-only auto-filing. Blocked
    rows are parked as ``needs_review`` for an admin.
    """
    if "[redacted-key]" in body or "[redacted-token]" in body:
        return True
    if has_image and (image_sensitive is None or image_sensitive):
        return True
    if used_llm:
        return bool(llm_flag)
    return not _autofile_without_ai()


# --- The change loop (a.k.a. Loop A, issue #362) ---------------------------
#
# The ``agent-ready`` label is the SOLE trigger for the workflow that assigns an
# issue to the GitHub Copilot coding agent
# (``.github/workflows/assign-copilot.yml``). Triage tags a report only when it
# is a genuine, actionable *bug*: features are assist-not-act (a human
# green-lights those), and a report the model judges works-as-intended, a
# support question, or too vague is NOT actionable. The sensitivity gate must
# not have withheld it (a needs_review/sensitive report is never auto-assigned),
# and it must carry enough detail for a drafted fix to work from. Autonomy is
# drafting the fix; merge stays human (branch protection).
AGENT_READY_LABEL = "agent-ready"

def _agent_ready_shadow() -> bool:
    """Shadow mode: compute the agent-ready decision but never apply the label.

    Lets us measure the change loop's precision on real feedback before we
    trust it to auto-assign. Enable with PRAXYS_AGENT_READY_SHADOW=true.
    """
    return (os.environ.get("PRAXYS_AGENT_READY_SHADOW", "") or "").lower() in ("1", "true", "yes")


def _decision_locale(locale: str | None) -> str:
    """Reduce client locale input to a privacy-safe language bucket."""
    normalized = (locale or "").strip().lower().replace("_", "-")
    if normalized == "zh" or normalized.startswith("zh-"):
        return "zh"
    if normalized == "en" or normalized.startswith("en-"):
        return "en"
    return "other"


def _has_enough_detail(message: str) -> bool:
    """Whether a report says enough for a coding agent to attempt a fix."""
    word_count, alnum_count = message_detail_counts((message or "").strip())
    return has_enough_detail(word_count, alnum_count)


def _qualifies_for_agent(
    *, kind: str, gate_blocked: bool, agent_eligible: Optional[bool], message: str
) -> bool:
    """Whether an auto-filed report should be tagged ``agent-ready``.

    True only for a *bug* the sensitivity gate did not withhold, that the triage
    model judged a genuine, actionable defect (``agent_eligible``), and that has
    enough detail. ``agent_eligible is None`` means no model verdict (LLM
    unavailable) -> never auto-assign; that path is parked for an admin anyway.
    Features, ``other``, gated, not-actionable, and low-detail reports never
    qualify: autonomy drafts a fix, never ships it, and never acts on a
    sensitive or not-really-a-bug report (issue #362).
    """
    word_count, alnum_count = message_detail_counts((message or "").strip())
    return evaluate_agent_ready(
        AgentReadyFacts(
            kind=kind,
            gate_blocked=gate_blocked,
            agent_eligible=bool(agent_eligible),
            detail_word_count=word_count,
            detail_alnum_count=alnum_count,
        )
    ).eligible


def _system_prompt() -> str:
    return (
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
        "- Set agent_eligible=true ONLY for a bug that is a genuine, "
        "reproducible product DEFECT, specific and self-contained enough that a "
        "coding agent could reasonably attempt a fix from this report alone. Set "
        "it false for anything not clearly a defect we would act on: a feature "
        "request or idea, a how-to / support question, expected behavior or user "
        "error, a vague or unreproducible complaint, or anything needing human "
        "product judgment or more information. When kind is not bug, "
        "agent_eligible MUST be false. Default to false when unsure, and ALWAYS "
        "include the agent_eligible field.\n"
        "Respond with a JSON object: "
        "{\"kind\": str, \"title\": str, \"body\": str, "
        "\"contains_sensitive\": bool, \"priority\": str, "
        "\"agent_eligible\": bool}."
    )


def _user_payload(kind: str, message: str, context: dict) -> str:
    import json

    return json.dumps(
        {"reported_kind": kind, "message": message, "context": context},
        ensure_ascii=False,
    )


def _rule_based(kind: str, message: str, context: dict) -> tuple[str, str]:
    """Deterministic fallback title + body when the LLM is unavailable."""
    first_line = (message.strip().splitlines() or [""])[0]
    title = (first_line[:77] + "...") if len(first_line) > 80 else (first_line or f"User {kind}")
    label = {"bug": "Bug report", "feature": "Feature request"}.get(kind, "Feedback")
    lines = [f"**{label}** submitted via in-app feedback.", "", "## Report", message.strip(), ""]
    if context:
        lines.append("## Environment")
        for key, val in context.items():
            lines.append(f"- **{key}**: {val}")
        lines.append("")
    return title, "\n".join(lines)


def _publish_footer(feedback_id: int, user_id: Optional[str]) -> str:
    """Audit footer. Identifies the submitter by a non-reversible hash only."""
    who = telemetry.hash_user_id(user_id) if user_id else "anonymous"
    return (
        "\n\n---\n"
        f"_Auto-filed from Praxys in-app feedback (id `{feedback_id}`, "
        f"reporter `{who}`). PII-scrubbed before publication._"
    )


def triage_and_publish(feedback_id: int, *, _session: Optional[Session] = None) -> dict:
    """Triage one feedback row and publish it. Returns a small status dict.

    Args:
        feedback_id: PK of the :class:`db.models.Feedback` row to process.
        _session: Test-only injected session; otherwise a fresh ``SessionLocal``
            is opened and owned by this function.
    """
    from db.models import AgentDecision, Feedback
    from db.session import SessionLocal

    owns_session = _session is None
    db = _session or (SessionLocal() if SessionLocal is not None else None)
    if db is None:
        logger.error("triage_and_publish: DB not initialized")
        return {"status": "error", "reason": "db_uninitialized"}

    row = None
    issue: dict | None = None
    decision_id: str | None = None
    decision_kwargs: dict | None = None
    try:
        row = (
            db.query(Feedback)
            .filter(Feedback.id == feedback_id)
            .with_for_update()
            .first()
        )
        if row is None:
            logger.warning("triage_and_publish: feedback %s not found", feedback_id)
            return {"status": "error", "reason": "not_found"}
        if row.status not in ("new", "failed"):
            # Idempotent: don't re-publish an already-handled row.
            return {"status": "skipped", "reason": row.status}

        reported_kind = row.kind if row.kind in _VALID_KINDS else "other"
        kind = reported_kind
        clean_message = feedback_scrub.scrub_text(row.message)
        clean_context = feedback_scrub.scrub_context(row.context_json)

        # --- Screenshot vision triage (issue #337) ---
        # Load any attached screenshots, ask the vision model for a scrubbed
        # description + sensitivity verdict, and record both on the row. The raw
        # image is NEVER folded into the issue — only the scrubbed description
        # plus an "in the admin console" reference. image_flag stays None when a
        # screenshot is present but couldn't be vision-verified, which the gate
        # treats as unsafe to auto-publish.
        image_keys = list(row.image_keys or [])
        image_section = ""
        used_vision = False
        image_flag: Optional[bool] = None
        if image_keys:
            loaded = []
            for key in image_keys:
                got = feedback_storage.load_image(key)
                if got is not None:
                    loaded.append(got)
            vision = feedback_vision.analyze_images(loaded) if loaded else None
            if vision is not None:
                used_vision = True
                description = feedback_scrub.scrub_text(vision["description"])
                image_flag = bool(vision["sensitive"])
                row.image_description = description
                row.image_sensitive = image_flag
                image_section = (
                    f"\n\n## Screenshot\n{description}\n\n"
                    f"_{len(image_keys)} screenshot(s) attached — view in the Praxys "
                    f"admin console (feedback id {feedback_id}). The image itself is "
                    f"not published here._"
                )
            else:
                # No vision verdict (model unavailable or call failed). Reference
                # the attachment but publish no image-derived text; the gate holds
                # the row for admin review.
                row.image_sensitive = None
                image_section = (
                    f"\n\n## Screenshot\n_{len(image_keys)} screenshot(s) attached — "
                    f"view in the Praxys admin console (feedback id {feedback_id}). "
                    f"Not analysed (no vision model); image not published here._"
                )

        used_llm = False
        llm_flag = False
        priority: Optional[str] = None
        agent_eligible: Optional[bool] = None
        client = llm.get_client()
        title = body = None
        if client is not None:
            result = llm.chat_json(
                client,
                system=_system_prompt(),
                user=_user_payload(kind, clean_message, clean_context),
                model=_TRIAGE_MODEL,
                max_completion_tokens=1200,
                # Deterministic: triage/classification shouldn't vary run-to-run.
                # Low temperature minimises the rare false-positive sensitivity
                # flip that parks benign reports.
                temperature=0.0,
                insight_type="feedback_triage",
            )
            if result and isinstance(result.get("title"), str) and isinstance(result.get("body"), str):
                maybe_title = result["title"].strip()
                maybe_body = result["body"].strip()
                # Only trust the model when it actually produced content. Empty
                # title/body would otherwise drop the user's report and publish a
                # contentless issue; treat it as "no usable LLM output" so the
                # rule-based fallback (which carries the real message) runs and
                # the gate falls back to its fail-safe no-LLM path.
                if maybe_title and maybe_body:
                    title = maybe_title
                    body = maybe_body
                    llm_kind = str(result.get("kind", "")).lower()
                    if llm_kind in _VALID_KINDS:
                        kind = llm_kind
                    # Missing field → treat as sensitive (fail safe).
                    llm_flag = bool(result.get("contains_sensitive", True))
                    llm_priority = str(result.get("priority", "")).strip().lower()
                    if llm_priority in _VALID_PRIORITIES:
                        priority = llm_priority
                    # Genuine, actionable defect? Only a real bool verdict counts;
                    # a missing/invalid field stays None (fail safe -> no assign).
                    if isinstance(result.get("agent_eligible"), bool):
                        agent_eligible = result["agent_eligible"]
                    used_llm = True

        if not title or not body:
            title, body = _rule_based(kind, clean_message, clean_context)

        # Fold the (already-scrubbed) screenshot description into the body so it
        # too passes through the final scrub below (belt-and-suspenders).
        if image_section:
            body = body + image_section

        # Belt-and-suspenders: never trust the model as the sole redactor.
        title = feedback_scrub.scrub_text(title)[:120] or f"User {kind}"
        body = feedback_scrub.scrub_text(body) + _publish_footer(feedback_id, row.user_id)

        labels = [_KIND_LABEL[kind], "feedback"]
        if used_llm:
            labels.append("ai-triaged")
        if priority:
            labels.append(f"priority: {priority}")
        if image_keys:
            labels.append("screenshot")

        # Decide the sensitivity gate once: it both routes the row (publish vs
        # park for admin) and gates the change-loop agent-ready label below, so a
        # withheld report can never be tagged for the coding agent (issue #362).
        gate_blocked = _gate_blocks_publish(
            used_llm=used_llm,
            llm_flag=llm_flag,
            body=body,
            has_image=bool(image_keys),
            image_sensitive=image_flag,
        )
        # The change loop (issue #362): tag a genuine, actionable bug so the
        # labeled-issue workflow hands it to the Copilot coding agent. Never for
        # a gated (sensitive/needs_review) report, a feature, a not-actionable
        # report, or a low-detail one -- and because it is gated on gate_blocked
        # it never lands in ai_labels for a parked row, so a later admin
        # "approve" cannot auto-assign it either. Shadow mode computes the same
        # decision but withholds the label so we can measure precision first.
        detail_word_count, detail_alnum_count = message_detail_counts(clean_message)
        agent_ready_decision = evaluate_agent_ready(
            AgentReadyFacts(
                kind=kind,
                gate_blocked=gate_blocked,
                agent_eligible=bool(agent_eligible),
                detail_word_count=detail_word_count,
                detail_alnum_count=detail_alnum_count,
            )
        )
        shadow = _agent_ready_shadow()
        if agent_ready_decision.eligible and not shadow:
            labels.append(AGENT_READY_LABEL)
        logger.info(
            "change-loop agent-ready decision for feedback %s: "
            "candidate=%s applied=%s shadow=%s reason=%s",
            feedback_id,
            agent_ready_decision.eligible,
            AGENT_READY_LABEL in labels,
            shadow,
            agent_ready_decision.reason,
        )

        row.kind = kind
        row.priority = priority
        row.ai_title = title
        row.ai_body = body
        row.ai_labels = labels

        decision_kwargs = {
            "loop": "change",
            "subject_type": "feedback",
            "subject_ref": str(feedback_id),
            "policy_name": AGENT_READY_POLICY_NAME,
            "policy_version": AGENT_READY_POLICY_VERSION,
            "prompt_version": (
                canonical_json_hash(_system_prompt())[:16] if used_llm else None
            ),
            "model": _TRIAGE_MODEL if used_llm else "rule-based",
            "mode": "shadow" if shadow else "active",
            "input_data": {
                "reported_kind": reported_kind,
                "locale": _decision_locale(row.locale),
                "message_sha256": canonical_json_hash(clean_message),
                "detail_word_count": detail_word_count,
                "detail_alnum_count": detail_alnum_count,
                "context_keys": sorted(clean_context),
                "has_image": bool(image_keys),
                "image_description_sha256": (
                    canonical_json_hash(row.image_description)
                    if row.image_description
                    else None
                ),
                "image_sensitive": row.image_sensitive,
            },
            "output_data": {
                "kind": kind,
                "priority": priority,
                "contains_sensitive": llm_flag if used_llm else None,
                "agent_eligible": agent_eligible,
                "gate_blocked": gate_blocked,
                "agent_ready_candidate": agent_ready_decision.eligible,
                "agent_ready_requested": AGENT_READY_LABEL in labels,
                "agent_ready_applied": False,
                "agent_ready_reason": agent_ready_decision.reason,
                "labels": labels,
                "used_llm": used_llm,
                "used_vision": used_vision,
            },
        }
        decision = record_decision(db, **decision_kwargs)
        decision_id = decision.id

        if not github_issues.is_configured():
            # No GitHub configured — scrubbed + classified, awaiting manual
            # promotion from the Admin page.
            row.status = "triaged"
            row.error = None
            outcome_type = "triaged_without_publish"
        elif gate_blocked:
            # The report may still carry sensitive content — don't auto-open a
            # public issue. Park it for an admin to review / approve.
            row.status = "needs_review"
            row.error = None
            outcome_type = "held_for_review"
        else:
            issue = github_issues.create_issue(title=title, body=body, labels=labels)
            if issue and issue.get("number"):
                row.github_issue_number = issue["number"]
                row.github_issue_url = issue.get("url")
                row.status = "issue_created"
                row.error = None
                outcome_type = "github_issue_created"
                if AGENT_READY_LABEL in labels:
                    applied_output = {
                        **decision.output_json,
                        "agent_ready_applied": True,
                    }
                    decision.output_json = applied_output
                    decision_kwargs["output_data"] = applied_output
            else:
                row.status = "failed"
                row.error = "github_publish_failed"
                outcome_type = "github_publish_failed"

        outcome_payload = {"status": row.status}
        if row.github_issue_number is not None:
            outcome_payload.update(
                {
                    "issue_number": row.github_issue_number,
                    "issue_url": row.github_issue_url,
                }
            )
        record_outcome(
            db,
            decision_id=decision.id,
            outcome_type=outcome_type,
            source="github" if outcome_type.startswith("github_") else "triage",
            payload=outcome_payload,
            dedupe_key=outcome_type,
        )

        db.commit()
        telemetry.record_feedback(kind=kind, status=row.status)
        return {
            "status": row.status,
            "kind": kind,
            "used_llm": used_llm,
            "used_vision": used_vision,
            "agent_ready": bool(
                (decision.output_json or {}).get("agent_ready_applied")
            ),
        }

    except Exception as exc:
        logger.exception("triage_and_publish failed for feedback %s", feedback_id)
        try:
            # If create_issue already opened a GitHub issue but the commit
            # failed, persist issue_created so a later retry can't file a
            # duplicate. Roll back the broken transaction and re-load the row
            # before writing the terminal state.
            db.rollback()
            recovered = db.query(Feedback).filter(Feedback.id == feedback_id).first()
            if recovered is not None:
                if issue and issue.get("number"):
                    recovered.github_issue_number = issue["number"]
                    recovered.github_issue_url = issue.get("url")
                    recovered.status = "issue_created"
                    recovered.error = None
                    outcome_type = "github_issue_created"
                else:
                    recovered.status = "failed"
                    recovered.error = "triage_exception"
                    outcome_type = "triage_failed"
                decision = (
                    db.query(AgentDecision)
                    .filter(AgentDecision.id == decision_id)
                    .first()
                    if decision_id
                    else None
                )
                if decision is None and decision_kwargs is not None:
                    decision = record_decision(db, **decision_kwargs)
                    decision_id = decision.id
                if decision is not None and decision.id == decision_id:
                    payload = {
                        "status": recovered.status,
                        "error_type": type(exc).__name__,
                    }
                    if recovered.github_issue_number is not None:
                        payload.update(
                            {
                                "issue_number": recovered.github_issue_number,
                                "issue_url": recovered.github_issue_url,
                            }
                        )
                    record_outcome(
                        db,
                        decision_id=decision.id,
                        outcome_type=outcome_type,
                        source=(
                            "github"
                            if outcome_type == "github_issue_created"
                            else "triage"
                        ),
                        payload=payload,
                        dedupe_key=outcome_type,
                    )
                db.commit()
                telemetry.record_feedback(kind=recovered.kind, status=recovered.status)
                return {"status": recovered.status}
        except Exception:
            db.rollback()
        return {"status": "failed"}
    finally:
        if owns_session:
            db.close()
