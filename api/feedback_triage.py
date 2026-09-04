"""Background triage for user feedback: scrub → classify → durable enqueue.

Pipeline (runs as a FastAPI ``BackgroundTask`` after the submit returns):

1. Load the :class:`db.models.Feedback` row in its *own* DB session — the
   request session is closed by the time a background task runs. (Same
   transaction-ownership pattern as :mod:`api.insights_runner`.)
2. Deterministically scrub the raw message + context (:mod:`api.feedback_scrub`).
3. If Azure OpenAI is configured, ask the model to turn the scrubbed report
   into a clean issue title + structured markdown body and to confirm the
   ``kind``. The model only ever sees already-scrubbed text. When the model
   is unavailable, a deterministic rule-based title/body is used instead.
4. Run the final title + body through the scrubber *again*, then require a
   separate fail-closed privacy review of that exact public candidate.
5. Atomically enqueue eligible v2 submissions. The publication worker owns all
   GitHub calls, leases, fencing, and ambiguous-result reconciliation.

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
    feedback_prompt,
    feedback_publication,
    feedback_scrub,
    feedback_storage,
    feedback_vision,
    github_issues,
    llm,
    telemetry,
)
from api.optional_processing import (
    background_ai_authorized,
    feedback_has_publication_consent,
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

_TRIAGE_MODEL = llm.INSIGHT_MODEL


def _contains_redaction_marker(value: object) -> bool:
    return "[redacted" in str(value).casefold()


def _gate_blocks_publish(
    *,
    used_llm: bool,
    llm_flag: bool,
    title: str = "",
    body: str,
    pre_model_redaction: bool = False,
    has_image: bool = False,
    image_sensitive: Optional[bool] = None,
    privacy_review_safe: Optional[bool] = None,
) -> bool:
    """Decide whether to withhold a report from auto-opening a public issue.

    Blocks when: (a) either scrub pass emitted a redaction marker; (b) the
    authoring model judged the report sensitive; (c) the separate final-payload
    privacy reviewer did not return an exact safe verdict; (d) a screenshot is
    sensitive or could not be privately verified; or (e) there is no usable
    authoring-model result. Screenshot-derived text itself is never public.
    """
    output = title + "\n" + body
    if pre_model_redaction or _contains_redaction_marker(output):
        return True
    if has_image and (image_sensitive is None or image_sensitive):
        return True
    if used_llm:
        return bool(llm_flag) or privacy_review_safe is not True
    # Missing, malformed, or unavailable AI sensitivity output is never enough
    # authority for automatic publication to the public repository.
    return True


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


def _challenger_prompt_version() -> str | None:
    """Return the configured shadow-only triage prompt version."""
    raw = os.environ.get("PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION", "")
    version = feedback_prompt.resolve_challenger_prompt_version(raw)
    if raw.strip() and version is None:
        logger.error(
            "Unsupported PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION=%r; "
            "challenger evaluation disabled",
            raw,
        )
    return version


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
    """Return the active production prompt without changing its fingerprint."""
    return feedback_prompt.system_prompt(
        feedback_prompt.ACTIVE_TRIAGE_PROMPT_VERSION
    )


def _user_payload(kind: str, message: str, context: dict) -> str:
    """Return the active production payload shape."""
    return feedback_prompt.user_payload(
        version=feedback_prompt.ACTIVE_TRIAGE_PROMPT_VERSION,
        kind=kind,
        message=message,
        context=context,
    )


def _call_triage_model(
    client: object,
    *,
    prompt_version: str,
    kind: str,
    message: str,
    context: dict,
    image_description: str | None,
    insight_type: str,
) -> feedback_prompt.TriageModelOutput | None:
    """Call and validate one version of the feedback triage prompt."""
    result = llm.chat_json(
        client,
        system=feedback_prompt.system_prompt(prompt_version),
        user=feedback_prompt.user_payload(
            version=prompt_version,
            kind=kind,
            message=message,
            context=context,
            image_description=image_description,
        ),
        model=_TRIAGE_MODEL,
        max_completion_tokens=1200,
        temperature=0.0,
        insight_type=insight_type,
    )
    return feedback_prompt.parse_model_output(
        result,
        fallback_kind=kind,
    )


def _call_publication_privacy_model(
    client: object,
    *,
    title: str,
    body: str,
) -> bool | None:
    """Independently review the final scrubbed public payload, fail closed."""
    result = llm.chat_json(
        client,
        system=feedback_prompt.publication_privacy_review_prompt(),
        user=feedback_prompt.publication_privacy_review_payload(
            title=title,
            body=body,
        ),
        model=_TRIAGE_MODEL,
        max_completion_tokens=80,
        temperature=0.0,
        insight_type="feedback_publication_privacy_review",
    )
    return feedback_prompt.parse_publication_privacy_review(result)


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


def triage_and_publish(feedback_id: int, *, _session: Optional[Session] = None) -> dict:
    """Triage one feedback row and publish it. Returns a small status dict.

    Args:
        feedback_id: PK of the :class:`db.models.Feedback` row to process.
        _session: Test-only injected session; otherwise a fresh ``SessionLocal``
            is opened and owned by this function.
    """
    from db.models import AgentDecision, Feedback
    from db.session import SessionLocal, begin_serialized_write

    owns_session = _session is None
    db = _session or (SessionLocal() if SessionLocal is not None else None)
    if db is None:
        logger.error("triage_and_publish: DB not initialized")
        return {"status": "error", "reason": "db_uninitialized"}

    row = None
    decision_id: str | None = None
    decision_kwargs: dict | None = None
    try:
        if not db.in_transaction():
            begin_serialized_write(db)
        owner_id = feedback_publication.feedback_owner_id(db, feedback_id)
        if owner_id is None:
            db.rollback()
            logger.warning("triage_and_publish: feedback not found")
            return {"status": "error", "reason": "not_found"}
        owner = feedback_publication.lock_feedback_user(db, owner_id)
        if owner is None or not owner.is_active:
            db.rollback()
            return {"status": "skipped", "reason": "account_unavailable"}
        row = feedback_publication.lock_feedback(db, feedback_id)
        if row is None:
            db.rollback()
            logger.warning("triage_and_publish: feedback not found")
            return {"status": "error", "reason": "not_found"}
        if str(row.user_id) != owner_id:
            db.rollback()
            return {"status": "skipped", "reason": "account_changed"}
        if row.status not in ("new", "failed"):
            # Idempotent: don't re-publish an already-handled row.
            current_status = str(row.status)
            db.rollback()
            return {"status": "skipped", "reason": current_status}

        reported_kind = row.kind if row.kind in _VALID_KINDS else "other"
        kind = reported_kind
        clean_message = feedback_scrub.scrub_text(row.message)
        clean_context = feedback_scrub.scrub_context(row.context_json)
        pre_model_redaction = _contains_redaction_marker(
            clean_message
        ) or _contains_redaction_marker(clean_context)

        # --- Screenshot vision triage (issue #337) ---
        # Load any attached screenshots, ask the vision model for a scrubbed
        # description + sensitivity verdict, and record both on the private row
        # for admin handling. Neither the raw image nor any image-derived text is
        # folded into the public issue. This keeps a vision false negative from
        # becoming a second route around the text-only privacy review.
        image_keys = list(row.image_keys or [])
        allow_background_ai = background_ai_authorized(
            db,
            user_id=row.user_id,
        )
        used_vision = False
        image_flag: Optional[bool] = None
        if image_keys:
            loaded = []
            for key in image_keys:
                got = feedback_storage.load_image(
                    key,
                    provenance=row.image_storage_provenance,
                )
                if got is not None:
                    loaded.append(got)
            vision = (
                feedback_vision.analyze_images(loaded)
                if loaded and allow_background_ai
                else None
            )
            if vision is not None:
                used_vision = True
                description = feedback_scrub.scrub_text(vision["description"])
                image_flag = bool(vision["sensitive"])
                row.image_description = description
                row.image_sensitive = image_flag
            else:
                # No vision verdict (model unavailable or call failed). The
                # screenshot remains private and cannot influence public text.
                row.image_description = None
                row.image_sensitive = None

        used_llm = False
        llm_flag = False
        priority: Optional[str] = None
        agent_eligible: Optional[bool] = None
        challenger_version = _challenger_prompt_version()
        challenger_output: feedback_prompt.TriageModelOutput | None = None
        client = llm.get_client() if allow_background_ai else None
        title = body = None
        if client is not None:
            active_output = _call_triage_model(
                client,
                prompt_version=feedback_prompt.ACTIVE_TRIAGE_PROMPT_VERSION,
                kind=kind,
                message=clean_message,
                context=clean_context,
                image_description=None,
                insight_type="feedback_triage",
            )
            if active_output is not None:
                title = active_output.title
                body = active_output.body
                kind = active_output.kind
                llm_flag = active_output.contains_sensitive
                priority = active_output.priority
                agent_eligible = active_output.agent_eligible
                used_llm = True
            if challenger_version is not None:
                challenger_output = _call_triage_model(
                    client,
                    prompt_version=challenger_version,
                    kind=reported_kind,
                    message=clean_message,
                    context=clean_context,
                    image_description=row.image_description,
                    insight_type="feedback_triage_challenger",
                )

        if not title or not body:
            title, body = _rule_based(kind, clean_message, clean_context)

        # Belt-and-suspenders: never trust the model as the sole redactor.
        title = feedback_scrub.scrub_text(title)[:120] or f"User {kind}"
        body = feedback_scrub.scrub_text(body)

        privacy_review_safe: Optional[bool] = None
        privacy_review_attempted = False
        final_has_redaction = pre_model_redaction or _contains_redaction_marker(
            title + "\n" + body
        )
        if (
            used_llm
            and not llm_flag
            and not final_has_redaction
            and client is not None
            and feedback_has_publication_consent(row)
            and not owner.is_demo
        ):
            privacy_review_attempted = True
            privacy_review_safe = _call_publication_privacy_model(
                client,
                title=title,
                body=body,
            )

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
            title=title,
            body=body,
            pre_model_redaction=pre_model_redaction,
            has_image=bool(image_keys),
            image_sensitive=image_flag,
            privacy_review_safe=privacy_review_safe,
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
        challenger_data: dict | None = None
        if challenger_version is not None:
            challenger_available = (
                challenger_output is not None
                and challenger_output.agent_eligible is not None
            )
            challenger_decision = (
                evaluate_agent_ready(
                    AgentReadyFacts(
                        kind=challenger_output.kind,
                        gate_blocked=gate_blocked,
                        agent_eligible=bool(challenger_output.agent_eligible),
                        detail_word_count=detail_word_count,
                        detail_alnum_count=detail_alnum_count,
                    )
                )
                if challenger_available and challenger_output is not None
                else None
            )
            challenger_data = {
                "prompt_version": challenger_version,
                "prompt_hash": canonical_json_hash(
                    feedback_prompt.system_prompt(challenger_version)
                )[:16],
                "model": _TRIAGE_MODEL,
                "available": challenger_available,
                "kind": (
                    challenger_output.kind if challenger_output is not None else None
                ),
                "agent_eligible": (
                    challenger_output.agent_eligible
                    if challenger_output is not None
                    else None
                ),
                "agent_ready_candidate": (
                    challenger_decision.eligible
                    if challenger_decision is not None
                    else None
                ),
                "agent_ready_reason": (
                    challenger_decision.reason
                    if challenger_decision is not None
                    else None
                ),
            }
        shadow = _agent_ready_shadow()
        if agent_ready_decision.eligible and not shadow:
            labels.append(AGENT_READY_LABEL)
        logger.info(
            "change-loop agent-ready decision: "
            "candidate=%s applied=%s shadow=%s reason=%s",
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
                "detail_word_count": detail_word_count,
                "detail_alnum_count": detail_alnum_count,
                "context_keys": sorted(clean_context),
                "has_image": bool(image_keys),
                "image_sensitive": row.image_sensitive,
            },
            "output_data": {
                "kind": kind,
                "priority": priority,
                "contains_sensitive": llm_flag if used_llm else None,
                "publication_privacy_review_version": (
                    feedback_prompt.PUBLICATION_PRIVACY_REVIEW_VERSION
                    if privacy_review_attempted
                    else None
                ),
                "publication_privacy_review_policy_digest": (
                    feedback_prompt.publication_privacy_review_digest()
                    if privacy_review_attempted
                    else None
                ),
                "publication_privacy_review_attempted": privacy_review_attempted,
                "publication_privacy_review_safe": privacy_review_safe,
                "agent_eligible": agent_eligible,
                "gate_blocked": gate_blocked,
                "agent_ready_candidate": agent_ready_decision.eligible,
                "agent_ready_requested": AGENT_READY_LABEL in labels,
                "agent_ready_applied": False,
                "agent_ready_reason": agent_ready_decision.reason,
                "labels": labels,
                "used_llm": used_llm,
                "used_vision": used_vision,
                "active_prompt_version": (
                    feedback_prompt.ACTIVE_TRIAGE_PROMPT_VERSION
                ),
                "challenger": challenger_data,
            },
        }
        decision = record_decision(db, **decision_kwargs)
        decision_id = decision.id

        if owner.is_demo and (
            feedback_has_publication_consent(row)
            or row.publication_status == "unavailable"
        ):
            # Demo accounts can retain private feedback, but no persisted or
            # legacy grant may progress toward an external publication.
            row.status = "triaged"
            row.publication_status = "unavailable"
            row.error = None
            outcome_type = "publication_unavailable"
        elif not feedback_has_publication_consent(row):
            # Private submission is a complete outcome. Neither an admin nor a
            # later config change may turn it into a publication candidate.
            row.status = "triaged"
            row.publication_status = "private"
            row.error = None
            outcome_type = "triaged_private"
        elif gate_blocked:
            # The report may still carry sensitive content — don't auto-open a
            # public issue. Park it for an admin to review / approve.
            row.status = "needs_review"
            row.publication_status = (
                "manual_required"
                if feedback_has_publication_consent(row)
                else "private"
            )
            row.error = None
            outcome_type = "held_for_review"
        else:
            row.status = "triaged"
            outbox = feedback_publication.enqueue_publication(
                db,
                feedback_id,
                locked_user=owner,
                locked_feedback=row,
            )
            if outbox is None and row.publication_status == "manual_required":
                outcome_type = "held_for_review"
            elif outbox is None:
                outcome_type = "publication_unavailable"
            else:
                outcome_type = "publication_queued"

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
            source="publication" if outcome_type.startswith("publication_") else "triage",
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
        logger.error("triage_and_publish failed")
        try:
            db.rollback()
            begin_serialized_write(db)
            recovered_owner_id = feedback_publication.feedback_owner_id(
                db,
                feedback_id,
            )
            recovered_owner = (
                feedback_publication.lock_feedback_user(db, recovered_owner_id)
                if recovered_owner_id is not None
                else None
            )
            if recovered_owner is None or not recovered_owner.is_active:
                db.rollback()
                return {"status": "failed"}
            recovered = feedback_publication.lock_feedback(db, feedback_id)
            if recovered is not None:
                recovered.status = "failed"
                recovered.error = "triage_exception"
                if recovered_owner.is_demo:
                    recovered.publication_status = (
                        "unavailable"
                        if feedback_has_publication_consent(recovered)
                        else "private"
                    )
                else:
                    recovered.publication_status = (
                        "manual_required"
                        if feedback_has_publication_consent(recovered)
                        else "private"
                    )
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
                    record_outcome(
                        db,
                        decision_id=decision.id,
                        outcome_type=outcome_type,
                        source="triage",
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


def triage_and_wake_publication(feedback_id: int) -> dict:
    """Triage one row, then give the durable worker an immediate wakeup."""
    result = triage_and_publish(feedback_id)
    feedback_publication.safe_wake_publication_queue(limit=1)
    return result
