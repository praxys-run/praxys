# Policy Change Proposal: Agent Invocation Control v1

- **id:** `policy-change-proposal-agent-invocation-control-v1`
- **schema_version:** `1`
- **artifact_type:** `policy-change-proposal`
- **artifact implementation status:** repository-native Markdown; not schema-backed
- **owner_role:** `meta-eval`
- **status:** Accepted for instrument/shadow implementation only
- **proposal_date:** `2026-08-20`
- **digest:** `sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6`

The digest above is the accepted proposal subject identifier supplied to and
approved by the human authority. It is not asserted to be a hash of this
rendered Markdown file.

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

## Proposal contract

- **question:** Should Praxys introduce deterministic agent-invocation admission
state and policy, and what may be activated on the evidence currently
available?
- **options:** Retain prompt-only safeguards; implement instrument/shadow
admission evaluation; or activate enforcement and native interception.
- **recommendation:** Implement only instrument mode followed by shadow mode
using the v1 identity, state, decision, reason-code, guard, and limit contracts
below. Keep actual dispatch behavior unchanged.
- **rationale:** Static routing is deterministic, but runtime invocation state
is not authoritative. The reported incident counts are unverified, direct
self-recursion is unproven, and no replay-backed batch supports enforcement or
autonomy promotion. Instrument/shadow operation is the bounded, reversible way
to establish evidence.
- **dependencies:**
  - `ER-2026-08-20-agent-invocation-control-v1`;
  - the digest-bound Work Contract above;
  - independent Decision Review Router outcome `human-review-required`;
  - the exact human approval recorded below; and
  - Architecture, Engineering, and Quality artifacts required by the Work
  Contract before any implementation is considered complete.
- **review_route:** `human-review-required`; approval is limited to
instrument/shadow implementation.
- **outcome_plan:** Observe at least five distinct root runs over at least seven
days, replay the bounded cases below, and require zero false blocks, escapes,
and human corrections before a separately reviewed enforcement decision.

## Scope of the accepted change

The proposal defines a versioned candidate admission contract. It does not
itself implement that contract or alter deployed policy. It introduces five
stable, opaque, non-content identities:

- **contract identity:** the validated Work Contract instance;
- **slot identity:** the bounded composed role slot within that contract;
- **generation identity:** one generation of work for that slot;
- **logical invocation identity:** one logical unit across its permitted
attempts; and
- **attempt identity:** one concrete execution attempt.

The identities must remain distinct and stable for their defined lifetimes.
They may not contain task, prompt, source-code, user, artifact, or free-form
text. Human-readable content must not be used as identity or persisted as
control state.

## Work Contract guard invariant

Every decision validates the authoritative digest-bound Work Contract first.
Caller-supplied role, loop, artifact, reviewer, classification, or route values
cannot override it. The guard may admit, report, or reject a mediated launch
according to the active mode, but it may never mutate role composition, loop
composition, required artifacts, reviewer assignment, or routing policy.

This proposal changes no role boundary, routing table, reviewer authority,
autonomy class, or operating-model version.

## Atomic admission decisions and stable reason codes

Each mediated admission evaluates the following as atomic decisions against a
consistent state snapshot. The v1 reason-code vocabulary is stable; meanings
must not be repurposed within v1.

| Decision | Stable reason code | Accepted meaning |
|---|---|---|
| Contract valid and all guards pass | `admit` | The mediated launch is within the candidate policy |
| Work Contract invalid or mismatched | `work_contract_invalid` | The authoritative Work Contract could not be validated |
| Kill switch active | `kill_switch_active` | Mediated launches are rejected by the candidate policy |
| Duplicate active | `duplicate_active` | The matching invocation is already active |
| Ancestry cycle | `ancestry_cycle` | The proposed ancestry repeats a stable ancestor identity |
| Ancestry depth | `ancestry_depth_limit` | The proposed launch exceeds the starting ancestry bound |
| Active per contract | `active_contract_limit` | The launch exceeds the active-invocation bound for the contract |
| Logical per contract | `logical_contract_limit` | The launch exceeds the logical-invocation bound for the contract |
| Retry fingerprint | `retry_fingerprint_limit` | The allowed retry for the same failure fingerprint is exhausted |
| Attempt count | `attempt_limit` | The logical invocation has exhausted its attempt bound |
| No progress | `no_progress` | Two identical terminal fingerprints establish no progress |
| Required state missing | `state_missing` | The explicitly initialized ledger is absent |
| Required state corrupt | `state_corrupt` | The ledger is structurally missing, incomplete, or damaged |
| Required state unsupported | `state_unsupported` | The readable ledger has an unsupported schema or policy version |

A reason code records a policy result, not task or error text. Instrument and
shadow modes may record an ordinary would-reject reason without blocking
dispatch. The explicit kill switch is the mode-independent exception: it
rejects mediated launches. Missing, corrupt, or unsupported state fails closed
only in a separately approved eventual enforce mode; in instrument/shadow it is visible
evidence and does not become enforcement.

## Starting limits

The accepted, untuned starting bounds are:

| Guard | Starting bound |
|---|---:|
| Maximum ancestry depth | 6 |
| Maximum active invocations per contract | 8 |
| Maximum logical invocations per contract | 32 |
| Maximum attempts per logical invocation | 3 |
| Retries for the same failure fingerprint | 1 |
| No-progress trigger | 2 identical terminal fingerprints |

Crossing a bound yields the corresponding stable decision reason. No agent may
tune these values under this approval. Bound changes require evidence and a
separate reviewed proposal.

## Privacy-minimized state

Persist only what is needed to evaluate and audit the candidate policy:
version identifiers and digests; the five opaque identities; bounded parent and
ancestry references; lifecycle state; bounded counters; opaque failure and
terminal fingerprints; stable reason codes; mode; and timing facts required to
measure latency.

Do not persist task or prompt content, source code, user data, artifact content,
model output, stack traces, or free-form error text. Reports must aggregate
privacy-safe outcomes and must distinguish mediated coverage from unknown
unmediated native activity.

## Modes, kill switch, and reversibility

1. **Instrument:** record the privacy-minimized identity and lifecycle facts;
ordinary policy results do not change dispatch.
2. **Shadow:** compute and record the exact candidate admit or reject result;
ordinary policy results do not change dispatch.
3. **Enforce:** not approved. If separately approved later, the mediated
launcher applies every admission decision and missing, corrupt, or
unsupported state fails closed.

The kill switch is independent of mode and rejects mediated launches. It is an
immediate stop path, not a claim of native interception. A later enforce
rollout must also preserve immediate demotion back to shadow or instrument.

No repository-owned cooperative guard may claim to intercept unmediated native
agent launches. Native launcher interception remains a separate decision.

## Replay and shadow observation plan

Before any enforcement proposal, replay at least the following cases against
the exact candidate policy and compare the result with reviewed expected
outcomes:

1. valid first invocation and clean terminal completion;
2. matching duplicate while active and a nonmatching concurrent invocation;
3. direct and indirect ancestry cycles;
4. ancestry at the starting limit and an attempted launch beyond it;
5. active counts at the starting limit and beyond it;
6. logical counts at the starting limit and beyond it;
7. three attempts and an attempted additional attempt;
8. one retry for a failure fingerprint and an attempted additional retry for
the same fingerprint;
9. two identical terminal fingerprints and an attempted further launch;
10. valid, mismatched, unavailable, missing-state, corrupt-state, and unsupported-state Work
Contract or control-state cases in every proposed mode; and
11. kill-switch inactive and active behavior.

Run instrument and then shadow across **at least five distinct root runs over
at least seven calendar days**. Reconcile candidate decisions with reviewed
outcomes. Measure corrections, overrides, missed and unnecessary escalations,
adverse outcomes, reverts, incidents, target and guardrail movement, review
effort, latency, mediated coverage, reason-code distribution, false blocks,
and escapes.

A later enforcement proposal requires **zero false blocks, zero policy escapes,
and zero human corrections** in the minimum observation window and replay
corpus. These thresholds are prerequisites, not automatic authorization.
Enforcement still requires independent review and human approval.

## Decision route and exact human approval

The independent Praxys Decision Review Router returned
`human-review-required` and recommended accepting only instrument/shadow
implementation.

Recorded human approval timestamp: `2026-08-20T23:38:10.880+08:00`

> I approve policy-change-proposal-agent-invocation-control-v1 at sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6 for instrument/shadow implementation only.

The proposer does not self-approve this policy. The approval is bound to the
proposal identifier and accepted subject digest, not to an asserted Markdown
file hash.

## Explicit deferrals

This proposal does not authorize or decide:

- actual enforcement;
- native launcher interception;
- autonomy promotion;
- tuning any starting limit after observation;
- operating-model version changes; or
- final implementation-bound Architecture Decision Record approval.

Each deferred item requires evidence from the observation plan and a separate
independent decision route. No successful single run can promote autonomy.
