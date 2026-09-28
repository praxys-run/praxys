# Decision-card trial v1 — default-off proposal

**Status: not authorized or active.** This is a temporary proposal to learn
whether a shorter *human-facing* decision request saves attention without
losing quality. It does not reduce roles, contracts, tests, reviewer
independence, or human authority. No old PRs or tasks are rerun.

The task's Work Contract remains the source of routing and is produced **before**
any future trial admission. This *disabled implementation task* has Work
Contract classification
`sha256:b8d54c328ddbe16925d05bdee8fe1f948d87834bccb568aad42076a167ff08d5`
and route
`sha256:331cc2010c522a3d0277a002d6e9b0f8b38fbcc629a827b37bbe4b203fb5394e`.
It does not include `production-operation`: no runtime entry or rollout is
changed. These digests do not bind an enrolled future task or grant approval;
live activation must be classified and routed separately. The trial manifest
lives in `config/agent-decision-card-trial.json`.

## What this change actually delivers

- A checked-in **disabled** policy; `python3 scripts/agent_decision_trial.py`
  reports its digest and `can_enroll: false`. It cannot activate by changing
  the JSON flag or passing a CLI option.
- Pure transition logic for a single 16-task cohort, an eight-task checkpoint,
  sticky A/B assignment, a monotonic stop, coded append-only outcomes, and a
  candidate card renderer. Unit tests simulate a protected atomic store; they
  are **not** evidence that one exists or that any runtime was enrolled.
- No calls from an agent runtime, Copilot assignment workflow, Paseo launcher,
  or PR workflow; no private storage, credentials, telemetry, protection-rule
  changes, enrollment, or candidate decision cards in live work. Baseline
  behavior stays unchanged. Existing Git-common-dir invocation control is not
  a cross-checkout trial store.

This is a first implementation slice, not a claim that future sessions are
already compelled to join. A native CLI/Paseo session that bypasses a trusted
entrypoint cannot be covered by repository instructions alone.

## Proposed protocol — not permission to run

| Boundary | Proposed rule |
|---|---|
| Unit | One new user task, keyed by a stable opaque ID, not a session, agent, or PR. Retries keep the original assignment; no candidate without an authenticated receipt. |
| Eligibility | Only the versioned primary objects in the policy, with no risk triggers or excluded Science, Trust, incident, Operations, architecture, or autonomy impact. Excluded and bypassed tasks remain outside the trial, not counted A successes. |
| A/B | Alternate the less-filled arm. A retains the existing presentation. B may render **one** compact card for a fully evidenced `human-review-required` decision; absent or blocked decisions cannot be turned into approval requests. |
| Counting | One **trusted shared atomic** cohort record for all enrolled entries. Assignment 8 sets `checkpoint_due`, halting new admissions until an independently authenticated review is recorded. Assignment 16 closes admissions permanently and requires final evaluation. Unfinished and no-PR attempts still occupy a slot. |
| Stop | Immediately halt B and new admissions on a critical omission, privacy exposure, authorization/review bypass, serious regression, or unreliable records. Preserve original assignments and outcomes, and send affected work through baseline human/Quality review. Never reset the counter to retry. |

The renderer requires a matching subject/evidence digest and all material
fields: question, recommendation, trade-off, authority scope, reason a human
must decide, rejection consequence, deferred decisions, evidence references,
and any known dissent. It renders a request, **not** approval. Its typed input
and digest comparison check structure and freshness only; an executing agent
could fabricate both values. Independent review must authenticate provenance
before any real card is shown. No card is generated for tasks without an
actual human decision.

## Evidence and privacy for a later activation

Before enabling anything, Architecture and Operations must verify **one**
controlled entrypoint and a restricted, atomic, durable cohort store with
authenticated admissions, checkpoint reviewers, and a protected kill switch.
Cloud, Local, and Paseo must not share a quota unless the same store and
runtime dispatch have each been verified end to end. A possible private
Azure-Blob/ETag design is not an installed or authorized resource. The broker
must reject lost or ambiguous writes without B exposure, bind the frozen
policy and Work Contract digests, and observe failed and abandoned no-PR runs.

Trust must approve a minimal, restricted record: opaque HMAC-derived task key,
entrypoint, pinned policy and contract digests, original arm, and coded outcome
events, with nullable PR/head references and measured effort only when real.
Do not persist task content, prompts, feedback, screenshots, credentials,
session URLs, or free-form logs; public reports contain only safe aggregates.
Specify a verified deletion schedule for receipts, joins, logs, and backups
before activation (proposed: final review plus a 30-day correction window,
with a 90-day outer limit after closure). Set an absolute cohort expiry at
activation so low task volume cannot leave it open indefinitely.

For a managed PR, a **trusted, always-reporting, head-bound required check**
must verify the protected enrollment and current validation evidence without
running PR-head code. Ordinary unmanaged PRs need a trusted exemption. Check
effective branch rules and obtain separate explicit authority before changing
their required statuses. Today's Copilot-only readiness check, PR-body claims,
and unprotected local SQLite do not establish that guarantee. No agent may
auto-approve or merge this trial policy.

## What to measure and when

Meta/Eval owns prospective comparison by **original assignment**, retaining
failures, fallback from B, no-PR tasks, and still-open outcomes. Both arms
retain the same Quality, CI, preflight, specialists, and human decision paths.
Record real human *active* reading/clarifying/approval minutes and whether a
human can accurately restate the decision; mark missing data `unknown`, and
no-decision tasks `not applicable`. Compare correction rounds, overrulings,
missed escalations, regressions, incidents, checks, model/provider mix, and
attributable cost only when observable.

At 8, independently review safety, record completeness, and comparability
before resuming. At 16, close, verify outcomes, and recommend: retain A,
adopt B, run one *new* single-factor trial, or insufficient evidence. The
screening hopes are ≥25% lower median human active time, ≥90% accurate
restatement, and **zero critical omissions**; 16 assignments cannot establish
long-run quality equivalence. Insufficient evidence means retire the trial
and keep the baseline, not add roles or stretch the cap.

## Decision and release boundary

Meta/Eval owns this **unapproved Policy Change Proposal** and the pretrial
Evaluation Report (current evidence cannot establish the card's benefit).
Architecture's proposed boundary is one authenticated, atomic store rather
than the existing local invocation ledger. Trust's proposed boundary is
privacy-minimal provenance and a trusted head-specific PR signal. Operations'
proposed boundary is one verified entry with checkpoint recovery and rollback.
Engineering owns this inert implementation; independent Quality must verify
the exact committed head. The Operations Decision Record and Release Evidence
for any *live* entry, and the eight-/sixteen-task Evaluation Reports, remain
future obligations, not completed artifacts. There is no approval for
activation or a protected-branch change in this document.

Ask the independent Decision Review Router again after the exact proposal,
Architecture/Trust/Operations decisions, trusted-entry tests, and independent
Quality evidence exist. Present the human only a bounded choice about the
exact digest and PR head: merge inert mechanics, authorize a named single-entry
trial after prerequisites, or keep the trial off. A later activation is a
**separate decision** even if the inert code is merged.
