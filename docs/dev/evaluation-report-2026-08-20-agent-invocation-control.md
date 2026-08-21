# Evaluation Report ER-2026-08-20-agent-invocation-control-v1

- **id:** `ER-2026-08-20-agent-invocation-control-v1`
- **schema_version:** `1`
- **artifact_type:** `evaluation-report`
- **artifact implementation status:** repository-native Markdown; not schema-backed
- **owner_role:** `meta-eval`
- **status:** Accepted
- **report_date:** `2026-08-20`
- **evaluated subject:** `policy-change-proposal-agent-invocation-control-v1`
- **accepted subject digest:** `sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6`

The accepted subject digest identifies the proposal reviewed and approved by the
human authority. It is not asserted to be the hash of this rendered Markdown
file or of this Evaluation Report.

## Work Contract binding

- **routing_version:** `praxys-task-routing-v1`
- **operating_model_version:** `praxys-agentic-operating-model-v1`
- **primary_object:** `agent-system`
- **impacts:** `[repository-change, agent-policy-or-autonomy, architecture-boundary]`
- **risk_triggers:** `[irreversible-or-high-blast-radius-action, out-of-policy-or-out-of-distribution-decision]`
- **classification_digest:** `sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2`
- **primary_loop:** `meta-eval`
- **nested_loops:** `[delivery]`
- **lead:** `meta-eval`
- **contributors:** `[architecture]`
- **executor:** `engineering`
- **verifier:** `quality`
- **required_artifacts:** `[evaluation-report, implementation-impact-map, implementation-change, verification-evidence, policy-change-proposal, architecture-decision-record]`
- **decision_review:** required
- **route_digest:** `sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51`

The composition is Meta/Eval-led, with Architecture contributing the
cross-cutting boundary, Engineering responsible for any later accepted
implementation, and Quality independently responsible for verification. This
report does not replace current-change verification.

## Question and recommendation

**Question:** Does available evidence justify deterministic agent-invocation
control, enforcement, a routing or role change, or an autonomy promotion?

**Recommendation:** Accept only a bounded instrument-then-shadow
implementation of the separately identified proposal. Do not activate
blocking enforcement, claim native launcher interception, tune the starting
bounds, change the operating-model version, change role or routing authority,
or promote autonomy on this evidence.

## Evaluated baseline and evidence limits

Praxys has deterministic static task routing: an enumerated classification is
composed into a digest-bound Work Contract. That is not runtime invocation
admission. No authoritative runtime state currently establishes root run,
parent, attempt, budget, active-loop, or progress identity and lifecycle.
Consequently, no reliable denominator exists for native invocations, duplicate
active work, retries, cycles, escapes, or completed root runs.

The supplied incident narrative reports the following aggregate observations:

| Reported item | Count | Evidence status | Permitted interpretation |
|---|---:|---|---|
| Conversation turns | 810 | Unverified | Context volume only; not a completed-decision population |
| Calls | 1,735 | Unverified | Call volume only; invocation types and denominator are not authoritative |
| Starts | 19 | Unverified | Candidate starts only; runtime identity and lifecycle are absent |
| Near-duplicate launches | 7 | Unverified | Candidate anomaly signal only; intent, parentage, and active overlap are unproven |

The counts were not produced by an authoritative runtime ledger and cannot be
used to calculate rates. Direct self-recursion is not proven. Near-duplicate
launches do not by themselves prove a cycle, duplicate-active execution,
policy escape, or adverse outcome.

Prompt-only instructions may discourage duplicate work, recursion, or excess
launches, but they are advisory and do not constitute deterministic
interception or enforcement.

## Outcome and review measures

No verified batch of completed decisions with privacy-safe outcome edges was
available. The accepted report therefore records insufficiency rather than
manufacturing rates or treating the reported volume as promotion evidence.

| Measure required by Meta/Eval | Accepted result |
|---|---|
| Corrections | Not authoritatively captured or attributable |
| Overrides | Not authoritatively captured or attributable |
| Missed escalations | Not measurable without routed decision and outcome state |
| Unnecessary escalations | Not measurable without routed decision and outcome state |
| Adverse outcomes | None verified from the supplied counts; absence is not evidence of zero |
| Reverts | Not linked to the reported invocation observations |
| Incidents | No verified incident count or causal attribution |
| Target or guardrail movement | No measured baseline or movement |
| Review effort | Not measured |
| Decision and execution latency | Not measured |
| False blocks or policy escapes | Not measurable before instrument/shadow comparison |

These gaps prevent autonomy promotion and prevent a defensible enforcement
decision. They justify privacy-minimized instrumentation and shadow evaluation
only.

## Candidate-policy replay and shadow status

No authoritative event stream exists on which to run a valid historical replay
or live shadow comparison. The proposal is therefore not a promoted policy and
this report makes no claim that the candidate outperforms the current state.
The accepted next step creates the evidence needed to compare the current
prompt-only baseline with deterministic hypothetical admission decisions while
leaving actual dispatch unchanged.

The observation corpus must cover at least these cases:

1. a valid first logical invocation;
2. a duplicate invocation while the matching invocation is active;
3. an ancestry cycle and ancestry at and beyond the starting depth limit;
4. active invocations at and beyond the per-contract limit;
5. logical invocations at and beyond the per-contract limit;
6. attempts at and beyond the per-logical-invocation limit;
7. a first retry and an additional retry with the same failure fingerprint;
8. two identical terminal fingerprints followed by another proposed launch;
9. a valid Work Contract, a mismatched Work Contract, and an unavailable one;
10. missing, corrupt, and unsupported control state in instrument, shadow, and
hypothetical enforce modes; and
11. kill-switch activation, confirming that mediated launches are rejected while
ordinary instrument/shadow would-reject results do not block dispatch and
unmediated native activity remains outside coverage.

Until these cases are replayed and shadow outcomes are reconciled to reviewed
outcomes, the comparison result is `insufficient-evidence`.

## Observation plan and enforcement evidence bar

Instrument mode must first collect privacy-minimized identity, lifecycle,
decision, reason-code, and timing facts. Shadow mode must then compute the
candidate result without blocking dispatch. Evidence must be aggregated across
**at least five distinct root runs observed over at least seven calendar days**.
This is a minimum observation window, not automatic evidence of sufficiency.

For the replay cases and observed root runs, record:

- mediated coverage and the unknown unmediated-traffic limitation;
- hypothetical admits and denials by stable reason code;
- duplicate-active, ancestry, limit, retry, attempt, and no-progress outcomes;
- corrections, overrides, missed and unnecessary escalations;
- adverse outcomes, reverts, and incidents;
- target and guardrail movement;
- reviewer effort and decision or execution latency; and
- state-missing, state-corrupt, state-unsupported, recovery, and kill-switch
outcomes.

A later enforcement proposal requires reconciled replay and shadow evidence
showing **zero false blocks, zero policy escapes, and zero human corrections**
in that minimum window. It must then receive separate independent decision
review and human approval. Meeting the numeric bar does not itself authorize
enforcement or bound tuning.

## Decision route and authorization

The independent Praxys Decision Review Router returned
`human-review-required` and recommended accepting instrument/shadow
implementation only.

Recorded human approval timestamp: `2026-08-20T23:38:10.880+08:00`

> I approve policy-change-proposal-agent-invocation-control-v1 at sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6 for instrument/shadow implementation only.

This approval binds the proposal subject and digest. It does not approve this
Markdown file by its rendered-file hash and does not authorize any deferred
decision.

## Conclusions and explicit deferrals

- Deterministic static routing exists; authoritative runtime invocation state
does not.
- The reported counts and seven near-duplicates remain unverified.
- Direct self-recursion remains unproven.
- Prompt-only safeguards are not deterministic enforcement.
- No role, routing, reviewer-authority, or autonomy change is justified.
- Instrument then shadow is the only accepted rollout scope.

Explicitly deferred pending evidence and separate review:

- actual enforcement;
- native launcher interception;
- autonomy promotion;
- tuning any accepted starting bound;
- operating-model version changes; and
- final implementation-bound Architecture Decision Record approval.
