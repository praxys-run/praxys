# Agentic loops — the self-improvement platform

**Status:** Active implementation. The **change loop** (#362, PR #373) is the
first instance. Durable decision/outcome records, a seed replay corpus, and
aggregate learning metrics are built; selective-review promotion remains tracked
in #377.
**Question:** How do AI agents run in *loops* — not one-shot pipelines — that
learn from outcomes to improve the Praxys product *and* its operations?

## TL;DR

- A **loop** is `sense → decide → act → observe → learn` (OODA). The *learn* edge
  — outcomes feeding back to change future behavior — is what makes it a loop and
  not a pipeline. Most "AI features" are pipelines; we want loops.
- There are **two levels**, and conflating them is the usual confusion:
  - **Inner loop** = one unit of work: *feedback → triage → agent drafts PR →
    independent merge policy routes it to human review or a promoted narrow
    auto-merge class → merge/reject.* **One PR ≈ one inner-loop iteration.** It
    acts; it does **not** learn.
  - **Outer loop** = the improvement loop. It watches *many* inner-loop outcomes
    and tunes the **policy** that drives the inner loop (prompts, thresholds,
    rubrics, model, runbooks). It runs periodically / every N outcomes — **not**
    per PR. **This is where "self-improve" lives.**
- It is not one loop but a **family** (change, incident, product/quality,
  meta/eval) — same shape, different signals and actuators.
- They share one **substrate**: trace log · outcome capture · eval corpus + replay
  · shadow→promote · policy-as-code + policy PRs · metrics + autonomy ladder.
  Building that substrate **once** — instead of per loop — is what makes the whole
  product + devops self-improving, rather than one clever automation.

## 1. Loops, not pipelines

```
        ┌─────────────────────────── learn (outer loop) ───────────────────────────┐
        │                                                                           │
   ┌────▼─────┐     ┌──────────┐     ┌────────┐     ┌───────────────┐     ┌─────────┴────────┐
   │  SENSE   │ ──▶ │  DECIDE  │ ──▶ │  ACT   │ ──▶ │    OBSERVE    │ ──▶ │  aggregate + tune │
   │ (signal) │     │ (policy) │     │ (agent)│     │ (outcome edge)│     │  policy (meta)    │
   └──────────┘     └──────────┘     └────────┘     └───────────────┘     └──────────────────┘
        └──────────────── inner loop: one unit of work (≈ one PR) ─────────────────┘
```

The **inner loop** runs once per work item and is stateless across items. The
**outer loop** closes the big arc: it reads the *observe* edge across many items
and edits the **policy** (the prompt / rubric / threshold / model / runbook) that
`DECIDE` uses next time. Without a captured *observe* edge, there is no outer loop
— you have a pipeline that never improves.

## 2. Loop granularity — "one PR, or many loops per PR?"

**One PR is one iteration of the *inner* loop.** Self-improvement is *not*
per-PR; it is the **outer** loop running over a *batch* of PRs/outcomes (e.g.
weekly, or every N drafts). So:

- Don't try to make a single PR "learn" from itself — that's just review.
- Do accumulate the outcomes of many PRs and let the outer loop propose a
  *policy* change (a PR against the prompt/rubric), which the next batch benefits
  from. Improvement compounds across iterations, not within one.

## 3. The loop family

Same OODA shape, different sensors and actuators:

| Loop | Sense | Decide (policy) | Act | Learns from |
|---|---|---|---|---|
| **Change** (built — #362) | user feedback | is this a real, actionable defect? (`agent_eligible`) | Copilot drafts a fix PR | merged without correction / corrected / rejected; post-merge reverts or reopens |
| **Incident** (Loop B — `praxys-ops-agent`) | alerts, telemetry anomalies, error spikes | RCA + severity + is it auto-mitigable? | mitigate (restart/rollback/scale/config) + draft postmortem + **hand a fix to the change loop** | MTTR, recurrence, did the mitigation hold |
| **Product / quality** | usage telemetry, feedback themes, funnels | what to build / fix next (prioritization) | draft specs/epics, sometimes prototype PRs | did the target metric move |
| **Meta / eval** | the agents' own outcomes | which policy/prompt/model is underperforming | open **policy PRs**, swap models, adjust thresholds | eval score, acceptance rate, precision |

The meta loop is special: its *product* is the other loops' policies. It is the
engine of "self-improvement."

## 4. The shared substrate (the actual "how")

Every decision point — triage `kind`, `agent_eligible`, priority, sensitivity,
RCA hypothesis, mitigation choice, prioritization — is a **policy**. Each policy
should run on the same six rails:

1. **Trace log.** Record every decision: privacy-minimized structured inputs, the
   *policy version*, the model, mode, and output. *Built:* generic append-only
   `AgentDecision` rows; Loop A stores hashes/counts/allowlisted context keys
   rather than duplicating feedback text.
2. **Outcome capture** (the feedback edge). A reconciler that records what the
   human/world actually did — PR merged/edited/rejected, issue close-reason, alert
   resolved/recurred. **This is the missing edge that makes shadow mode able to
   learn.** *Built:* generic append-only `AgentOutcome` rows record triage,
   admin override, explicit maintainer agent-ready adjudication, issue
   close/reopen, externally observed `agent-ready`, and closing-PR state.
   `change-loop-outcomes.md` remains the richer GitHub-native observer.
3. **Eval corpus + replay.** Labeled examples harvested from human corrections, +
   an offline/CI runner that *scores* a policy and blocks regressions when a
   prompt/threshold changes. *Built:* the structured, text-free deterministic
   corpus at `data/agent_evals/change/agent_ready.json`, the privacy-reviewed
   semantic corpus at `data/agent_evals/change/agent_eligibility.json`, and the
   replay/evaluation scripts. Pytest protects deterministic policy and corpus
   contracts; the semantic script calls the exact live prompt manually.
4. **Shadow → promote.** Run a candidate policy in *compute-but-don't-act* mode
   against live traffic, compare to the current policy **and** to eventual
   outcomes, and promote only if it wins. *Built for Loop A:* a versioned
   feedback-prompt challenger records its prediction without changing labels;
   Admin Feedback captures ground truth and Admin Operations compares active and
   challenger confusion matrices. The deterministic PR classifier remains
   default-off, and `scripts/validate_review_policy.py` blocks promotion without
   the checked-in completed-PR evidence bar.
5. **Policy-as-code + policy PRs.** The things agents tune — prompts, thresholds,
   `copilot-instructions.md`, runbooks — are versioned files. Improvement =
   the meta-agent opens a **PR** to change them, **gated by the eval harness +
   human review**. Auditable, revertible, never a hidden weight update. *Built
   for Loop A:* `change-loop-policy-tuner.md` can open a draft PR that modifies
   only the proposals file; it cannot edit deployed policy, approve, or merge.
6. **Metrics + an autonomy ladder.** Track acceptance rate, human-edit distance,
   MTTR, precision/recall, % autonomous vs escalated — and use them to move each
   task-type up or down the autonomy ladder (§5). *Today:* the 30-day observer
   reports lifecycle, readiness-CI attribution, corrections, test coverage, and
   reverts. *Built in part:* Admin Ops now shows durable decision/outcome counts
   and the versioned autonomy state from `config/agent-loop-policies.json`.
   Per-class promotion evidence lives in
   `data/agent_evals/change/review_promotion.json`.

## 5. Autonomy ladder & guardrails

Each task-type sits on a dial, raised **only** when the metrics in rail 6 justify
it, and always revertible:

```
suggest-only  →  draft-with-review  →  policy-gated auto-merge  →  autonomous(narrow)
```

The change loop is **selective-review capable but default-off**: an independent
risk policy routes sensitive or uncertain PRs to a human while a repeatedly
proven, explicitly promoted narrow class can merge without human review. The
implementation agent never decides that its own PR is safe. Promotion starts in
shadow mode and requires clean checks, no recorded corrections, enough
post-merge observation, and a fast kill switch.

**Non-negotiable guardrails** (apply to every loop):

- **Policy owns the merge/ship gate** — today that policy is maintainer
  controlled. A future no-review path must use an independent allowlisted policy;
  the implementation agent cannot self-approve or bypass required checks (see
  `docs/ops/change-loop.md`).
- **Scrub before any external surface** — anything user-derived passes
  `api/feedback_scrub.py` before it reaches a public issue/PR (the repo is public).
- **Least-privilege, ephemeral identities** — scoped tokens / OIDC, not standing
  creds (the ops-agent pattern).
- **Eval-gated policy changes + kill switch** — a policy PR must pass the replay
  eval; every loop has an off switch (shadow mode / disable workflow).
- **UI work enters the design harness** — any rendered web/miniapp change uses
  the repository `ui-quality` skill, Impeccable edit hooks, rendered evidence,
  durable design-system impact capture, and the deterministic
  `frontend-quality` gate. `backend-tests` remains a compatibility umbrella
  during branch-protection migration. Implementation agents cannot self-attest
  with placeholders or mark an unverified UI PR ready.

## 6. How it maps to the repos

- **`praxys-run/praxys` (this repo, public).** Hosts the **change loop** and the
  **product/quality loop**, and is the natural home for the **shared substrate**
  (telemetry, the decisions/outcomes store, the eval corpus, the policy files).
- **`praxys-run/praxys-ops-agent` (private).** Hosts the **incident loop**;
  consumes the same substrate. Event-triggered + ephemeral, acting on praxys via a
  scoped GitHub App + Azure OIDC.
- **Cross-loop edges** (the interesting part): the incident loop can *emit into*
  the change loop (an RCA that needs a code fix becomes an `agent-ready`-eligible
  issue); change-loop rejections and incident postmortems both feed the **eval
  corpus** the meta loop learns from.

## 7. Current state → gaps → phased rollout

**Have:** App Insights + `api/telemetry.py`; the change loop
(`api/feedback_triage.py`, `.github/workflows/assign-copilot.yml`,
`copilot-setup-steps.yml`); the shadow *primitive*; the issue-first 30-day outcome
observer; generic `AgentDecision` / `AgentOutcome` records; GitHub issue/closing
PR reconciliation; the checked-in replay corpus; Admin Ops learning aggregates;
`feedback_scrub` + private-by-construction guardrails; the ops-agent skeleton;
and the cross-agent UI quality harness (vendored Impeccable, Copilot/Claude
hooks, PR evidence, CI gate, and invariant review).

**Remaining generalization:** reuse these rails for incident and product loops,
grow privacy-safe eval corpora, and promote a narrow Loop A class only after it
accumulates the required clean evidence. No class is promoted at initial rollout.

**Phases** (tracked in **#377**):

- **Phase 0 — instrument (built).** The GitHub-native observer establishes the
  baseline; structured decision logging and durable outcome capture preserve the
  learn edge.
- **Phase 1 — eval (built for `change.agent_ready`).** A correction-derived seed
  corpus and replay CI gate protect the deterministic assignment policy.
- **Phase 2 — close the loop (built, default-off).** Shadow-classify
  `review-required` vs a named narrow candidate; validate promotions against
  completed outcomes; approve through an independent App; provide an immediate
  kill switch; and constrain the meta-agent to draft proposal PRs.

Start where signal is densest (the change loop's triage policy), prove the outer
loop end-to-end on that one policy, then generalize the substrate to the incident
and product loops.

## Glossary

- **Policy** — the tunable decision function at a `DECIDE` node (a prompt, rubric,
  threshold, or model choice). The unit the outer loop improves.
- **Inner / outer loop** — per-work-item execution vs the periodic improvement
  loop over many items.
- **Shadow mode** — compute a decision without acting, to measure a policy safely.
- **Policy PR** — a human-reviewed, eval-gated PR that changes a policy file.
- **Selective review** — an independent policy decides whether a PR needs human
  review; the implementation agent never decides its own eligibility.
- **Autonomy ladder** — suggest → draft-with-review → policy-gated auto-merge →
  narrow-autonomous.

## Related

- #362 — the change loop; **PR #373** — its implementation (+ shadow primitive,
  actionability gate). `docs/ops/change-loop.md` — the operator runbook.
- **#377** — the self-improvement platform tracker (the substrate above).
- `praxys-run/praxys-ops-agent` — the incident loop (Loop B).
- `docs/dev/architecture.md` — the (non-agentic) system architecture.