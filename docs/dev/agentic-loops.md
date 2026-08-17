# Agentic loops — the self-improvement platform

**Status:** Active shared substrate. The **change loop** (#362, PR #373) is the
first implemented instance. The versioned role/loop/control-plane contract is
defined in `agentic-operating-model.md`; selective-review promotion remains
tracked in #377.
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
- It is not one loop but a **family** (product, science, design, delivery,
  runtime, incident, meta/eval) — same shape, different objects, signals, and
  actuators.
- A loop's **object is not a person**. It is the state being improved: evidence
  claims, a product promise, repository behavior, production health, or the
  agent policies themselves. Humans and agents are operators, approvers,
  signal sources, or beneficiaries.
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

## 3. Roles operate; loops learn

Agents are decision-owning roles. Loops improve objects. The Work Router binds
roles into a loop instance through lead, contributor, independent-reviewer,
executor, verifier, observer, and human-authority slots.

The initial roles are Product, Design, Engineering, Architecture, Quality,
Science, Trust, Operations, and Meta/Eval. Traditional job names are an
evolvable starting taxonomy, not a permanent ontology. A role exists because it
owns recurring decisions, durable artifacts, independence requirements, and
outcome measures—not because it maps to a directory or technology.

API, frontend, backend, data, and integration work are Engineering
capabilities. Quality verifies the current change; Meta/Eval improves the agent
system across many completed changes. Architecture is trigger-based rather than
a mandatory gate for local code choices.

See [`agentic-operating-model.md`](agentic-operating-model.md) and
`config/agentic-operating-model.json` for the authoritative role, artifact,
loop, router, and evolution contracts.

## 4. The loop family

Same OODA shape, different sensors and actuators:

| Loop | Sense | Decide (policy) | Act | Learns from |
|---|---|---|---|---|
| **Product** | user problem, feedback, telemetry, strategy, accepted constraints | what user value Praxys should provide, for whom, and with which trade-offs | Product Decision Record and accepted implementation slice | target/guardrail metrics, adoption, abandonment, corrections |
| **Science** | bounded science question, new research, challenged claim | what evidence supports, does not support, and with what uncertainty | Evidence Review and Science Decision Record | source corrections, later evidence, reviewer corrections, post-launch falsification |
| **Design** | accepted product intent, experience defects, design-system gaps | what journey, interaction, content, accessibility, and visual system should deliver the intent | Design Decision, Experience Specification, rendered review | completion, errors, accessibility findings, confusion, repeated design defects |
| **Delivery** (first implementation — #362) | accepted decision, user feedback, defect, incident handoff | how to implement accepted behavior safely | Engineering produces a tested PR; Quality verifies it | correction, required checks, reverts, reopens, regressions |
| **Runtime** | release candidate, config change, monitoring or capacity need | how to deploy, observe, recover, and roll back | release, runtime configuration, monitoring, runbooks | availability, latency, alerts, rollback, operator correction |
| **Incident** (Loop B — `praxys-ops-agent`) | alerts, telemetry anomalies, error spikes | RCA + severity + is it auto-mitigable? | mitigate (restart/rollback/scale/config) + draft postmortem + **hand a fix to the change loop** | MTTR, recurrence, did the mitigation hold |
| **Meta / eval** | completed agent decisions and outcomes | which role, prompt, model, route, or autonomy policy is underperforming | Evaluation Report and policy PR | correction, escalation quality, adverse outcomes, replay, human effort |

The meta loop is special: its *product* is the other loops' policies. It is the
engine of "self-improvement."

The primary handoff is:

```text
user signal -> Work Router -> Product loop
-> Science / Design / Trust / Architecture decisions when triggered
-> Decision Review Router -> Delivery loop -> Quality verification
-> Runtime loop -> product and meta outcomes
```

See [`product-decision-loop.md`](product-decision-loop.md) for the Product-loop
specialization.

## 5. The shared substrate (the actual "how")

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
   task-type up or down the autonomy ladder (§6). *Today:* the 30-day observer
   reports lifecycle, readiness-CI attribution, corrections, test coverage, and
   reverts. *Built in part:* Admin Ops now shows durable decision/outcome counts
   and the versioned autonomy state from `config/agent-loop-policies.json`.
   Per-class promotion evidence lives in
   `data/agent_evals/change/review_promotion.json`.

## 6. Autonomy ladder, review routing, and guardrails

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

The same substrate also owns the control plane. The Work Router selects the
loop, role slots, triggered decisions, and required artifacts. The Decision
Review Router independently chooses:

```text
agent-resolved | agent-reviewed | human-review-required | blocked
```

Its objective is to minimize human attention subject to quality, safety,
reversibility, and authenticated authority. The proposer cannot select its own
review route or review its own decision; an executor cannot verify its own
high-risk work; routers cannot approve. New product promises, material value
trade-offs, sensitive-data collection, safety/privacy boundaries, irreversible
actions, unresolved agent disagreement, and out-of-policy decisions remain
default-human. The model lives in `config/agentic-operating-model.json`; review
autonomy lives in `config/agent-loop-policies.json`. The `agent-reviewed` route
is also default-off until a class is explicitly listed with independent
reviewer and deterministic-validation requirements; no class is currently
listed.

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
  `frontend-quality` gate. It is independent from the required `backend-tests`
  context within the unified pre-merge workflow. Implementation agents cannot
  self-attest with placeholders or mark an unverified UI PR ready.

## 7. How it maps to the repos

- **`praxys-run/praxys` (this repo, public).** Hosts the Product, Science,
  Design, Delivery, Runtime, and Meta/Eval contracts and the **shared substrate**
  (telemetry, the decisions/outcomes store, the eval corpus, the policy files).
- **`praxys-run/praxys-ops-agent` (private).** Hosts the **incident loop**;
  consumes the same substrate. Event-triggered + ephemeral, acting on praxys via a
  scoped GitHub App + Azure OIDC.
- **Cross-loop edges** (the interesting part): the Product loop consumes
  bounded Science, Design, Trust, and Architecture decisions and emits an
  accepted implementation slice into the Delivery loop.
  The incident loop can *emit into*
  the change loop (an RCA that needs a code fix becomes an `agent-ready`-eligible
  issue); change-loop rejections and incident postmortems both feed the **eval
  corpus** the meta loop learns from.

## 8. Current state → gaps → phased rollout

**Have:** App Insights + `api/telemetry.py`; the change loop
(`api/feedback_triage.py`, `.github/workflows/assign-copilot.yml`,
`copilot-setup-steps.yml`); the shadow *primitive*; the issue-first 30-day outcome
observer; generic `AgentDecision` / `AgentOutcome` records; GitHub issue/closing
PR reconciliation; the checked-in replay corpus; Admin Ops learning aggregates;
`feedback_scrub` + private-by-construction guardrails; the ops-agent skeleton;
and the cross-agent UI quality harness (vendored Impeccable, Copilot/Claude
hooks, PR evidence, CI gate, and invariant review).

**Defined but not yet promoted:** the nine role manifests, Work Router,
independent Decision Review Router, shared decision-record contract, and
human-attention policy. The control plane is specification-only and
default-human for judgment classes.

**Remaining generalization:** persist the first Product Decision Record, run
population routing through the role-composed workflow, capture corrections and
outcomes, reuse the rails across loops, and promote a narrow class only after it
accumulates the required clean evidence.

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
- **Decision review routing** — an independent policy allocates a decision to
  agent resolution, independent agent review, bounded human review, or a block.
- **Role** — a bounded owner of recurring decision classes and durable
  artifacts.
- **Capability / subagent** — a specialization inside a role without separate
  authority unless explicitly promoted.
- **Work routing** — selection of the object, primary loop, role slots,
  triggered decisions, and required artifacts before execution.
- **Autonomy ladder** — suggest → draft-with-review → policy-gated auto-merge →
  narrow-autonomous.

## Related

- #362 — the change loop; **PR #373** — its implementation (+ shadow primitive,
  actionability gate). `docs/ops/change-loop.md` — the operator runbook.
- **#377** — the self-improvement platform tracker (the substrate above).
- `praxys-run/praxys-ops-agent` — the incident loop (Loop B).
- `docs/dev/microsoft-foundry-adoption-study.md` — Foundry runtime, evaluation,
  Coach-insight, and cost decisions for the change and incident loops.
- `docs/dev/architecture.md` — the (non-agentic) system architecture.
- `docs/dev/agentic-operating-model.md` — authoritative role, loop, artifact,
  router, and role-evolution model.
