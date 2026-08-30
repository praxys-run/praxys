# Evaluation Report ER-2026-08-20-agent-invocation-control-v1

- **id:** `ER-2026-08-20-agent-invocation-control-v1`
- **schema_version:** `1`
- **artifact_type:** `evaluation-report`
- **artifact implementation status:** repository-native Markdown; not schema-backed
- **owner_role:** `meta-eval`
- **status:** Accepted 2026-08-20 baseline; bounded 2026-08-29 lifecycle
  correction authorized; 2026-08-30 ledger-v2 correction digest-approved for
  implementation
- **report_date:** `2026-08-20`
- **latest iteration date:** `2026-08-30`
- **evaluated subject:** `policy-change-proposal-agent-invocation-control-v1`
- **accepted baseline subject digest:** `sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6`

The accepted baseline subject digest identifies the proposal reviewed and
approved by the human authority on 2026-08-20. The bounded correction has
explicit semantic user authority; no new digest-bound approval is asserted or
fabricated. The accepted baseline digest is not asserted to be the hash of this
rendered Markdown file or of this Evaluation Report.

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

## 2026-08-29 Meta/Eval iteration

### Route, authority, and scope

This iteration remains bound to classification digest
`sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2`
and route digest
`sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51`
from the exact Work Contract above. After the upstream investigation, the user
explicitly authorized the bounded PR improvement with “好，那根据这个改进一下这个PR？”
and then “继续没做完的工作”. Meta/Eval treats that as sufficient semantic
authority for deterministic implementation. The independent Decision Review
route for that implementation is `agent-resolved`. No digest-bound approval,
activation, replay execution, shadow observation, or independent Quality
verification is claimed.

The 2026-08-20 approval remains accurate history and covers only its original
instrument/shadow subject. It does not extend to the 2026-08-29 successor
subject by implication; the later authority is semantic and bounded to the
behaviors stated in the implementation request. No one-off lifecycle invocation
identifiers are recorded in this durable report.

### Privacy-safe upstream evidence

As of 2026-08-29, four relevant community reports on GitHub's official Copilot
CLI tracker provide upstream context. They are not maintainer-confirmed root
causes or fixes:

| Public issue | Privacy-safe signal | Evaluation boundary |
|---|---|---|
| https://github.com/github/copilot-cli/issues/4533 | Parallel subagent fan-out is associated with terminal or completion-event hangs; sequential execution was reported not to reproduce the original case. | Public reports support a cooperative serialization mitigation, not causal proof or a repository runtime fix. |
| https://github.com/github/copilot-cli/issues/3350 | Some background `general-purpose` agents were reported to remain running without completion notification. | The historical workaround of replacing them with parallel `explore` agents is not current Praxys policy because it conflicts with the direct-sibling bound. |
| https://github.com/github/copilot-cli/issues/4225 | A sole background subagent was reported to leave the coordinator stuck in a working state until manual cancellation. | Background labeling cannot be treated as proof that coordinator work is independent or non-blocking. |
| https://github.com/github/copilot-cli/issues/2595 | Community reports describe agent lifecycle or completion-state inconsistency around task handling. | This supports explicit identity and lifecycle boundaries, not a claim about one native defect or fix. |

WSL2 is one reproducing environment but is not established as causal. Reports
also span other environments, and environment correlation is not cause. The
published release notes for `1.0.81` and `1.0.82-1` declare no relevant fix.
That does not prove that no fix exists. The expansion is therefore framed only
as a repository-owned,
manifest-coordinated cooperative mitigation. It cannot fix terminal event
consumption, native completion delivery, coordinator scheduling, native task
state, process disposal, or shutdown behavior.

### Aggregate outcomes and limits

The available evidence is an upstream issue set, not a privacy-safe Praxys
batch of completed decisions. It has no common invocation ledger, denominator,
or reviewed outcome edge. No rates are computed and no individual prompt,
repository, user, task, output, stack trace, or local path is retained here.

| Required Meta/Eval measure | 2026-08-29 result |
|---|---|
| Corrections | No authoritative Praxys batch; not measurable |
| Overrides | No authoritative Praxys batch; not measurable |
| Missed escalations | No routed-decision denominator; not measurable |
| Unnecessary escalations | No routed-decision denominator; not measurable |
| Adverse outcomes | Four community-reported upstream risk signals; no attributable Praxys adverse-outcome count |
| Reverts | None linked to an evaluated Praxys policy batch |
| Incidents | Public issue reports are not reclassified as Praxys incidents |
| Target or guardrail movement | No pre/post deployment or policy baseline |
| Review effort | This drafting iteration does not establish an operational review-effort measure |
| Decision and execution latency | No comparable mediated sample |
| False blocks and policy escapes | Not measurable before implementation, replay, and shadow reconciliation |
| Mediated coverage | No expanded-policy runtime exists; native and unmediated coverage remains unknown |

These gaps prohibit an autonomy promotion, enforcement proposal, runtime-fix
claim, or activation recommendation. A cooperative policy draft can still be justified because it is narrow and
preserves the existing observation and human-authority gates. The later ledger
format migration is transactionally reversible before commit but requires a
separately authorized state-reset procedure after successful migration.

### Candidate-policy replay and shadow comparison

At the time of this evaluation draft no executable expansion had been
authorized. The later semantic authorization permits implementation, but no
runtime replay, live shadow result, or independent verification is claimed
here. The following remains a pre-verification case comparison; `expected` is
not `verified`.

| Case | Accepted baseline | Expanded subject expected result |
|---|---|---|
| First direct child under a parent | Existing admission and lifecycle guards apply | Admit when all existing guards pass |
| Second direct child while the first is active under the same parent | No explicit narrow parent-sibling serialization | Do not launch; serialize until the first direct child is terminal |
| Direct children under unrelated parents | Contract-wide bounds apply | No global serialization; each narrow parent scope is evaluated independently |
| Child launches one nested child | Existing ancestry and depth rules apply | Preserve sequential nesting under the child parent scope and existing depth-six bound |
| Ordinary invocation mode | Native sync or background choice is not frozen by the accepted policy | Sync is the default |
| Background with concrete independent immediate parent work | Existing contract-wide bounds apply | Eligible only when that provenance is recorded and all existing bounds pass |
| Background followed by idle wait, status checks, or polling | One-read and no-poll lifecycle rules partly constrain reads | Ineligible; no speculative launch, idle waiting, status checking, or polling |
| Completion notification received | One claimed read | Exactly one claimed and performed read, then permanent refusal |
| Completion notification unavailable | Stop rather than poll | Same boundary preserved |
| Session shutdown, resume, or context replacement | Prior binding remains otherwise usable | Invalidate the exact old binding permanently without registry lookup, polling, loss, replacement, or relaunch |
| External rebind or rediscovery | No accepted native exact-match capability | Deferred; do not infer, search, guess, or rebind |
| Kill switch or cooperative-call removal | Existing immediate mediated stop or rollback path | Same immediate reversibility preserved |

Later implementation evidence must include focused tests for every row and for
provenance, privacy rejection, replacement limits, Local and Cloud parity, and
rollback. Independent Quality must verify the exact implementation revision;
this report does not replace that verification. Runtime replay and shadow
observation must still cover at least five distinct root runs over at least
seven calendar days and aggregate all outcome measures named in the accepted
baseline. The zero-false-block, zero-policy-escape, and zero-human-correction
thresholds remain prerequisites rather than automatic authorization.

### Evaluation conclusion

The bounded successor is preferable to either preserving unspecified
sibling/background behavior or waiting without mitigation for an upstream fix.
The narrowest-parent scope avoids a global lock, sequential nesting preserves
necessary delegation, sync default reduces exposure, and the restricted
background exception preserves useful concurrency only when the caller begins
concrete independent work immediately. Session invalidation, one-read behavior, privacy-minimized provenance, leaf-first
recovery, tests, documentation parity, and immediate reversibility form one
indivisible approval subject.

No separate successor digest was used for the 2026-08-29 lifecycle correction.
The later ledger-format correction is separately bound to
`sha256:5bd8d04069ef3cca0043087cd53e12d6e72de9847cf9431394e85690b6094875`.
Independent Quality verification of the corrected tree is still required and
is not claimed here.

No distinct recurring authority class emerges from this iteration. Meta/Eval
continues to own policy evaluation, Engineering would execute only an accepted
later change, Quality remains independently responsible for current-change
verification, and the Decision Review Router and human authority retain their
existing boundaries. No role is created, merged, or retired.

Explicitly deferred:

- activation, release, and merge;
- parallel direct siblings, unbounded background work, polling, repeated reads,
  automatic replacement, and automatic relaunch;
- native runtime repair, launcher interception, cancellation, global
  enforcement, and claims of complete native coverage;
- ledger schema 3 or a changed v2 target, online/mixed-version migration,
  context epochs, keyed/native ID schemes, generalized aliasing, registry
  rediscovery, and external rebind;
- autonomy promotion, starting-bound tuning, operating-model changes, and role,
  route, or reviewer-authority changes; and
- any later enforcement decision until complete replay and shadow evidence,
  independent review, and human approval exist.

## 2026-08-30 ledger-format correction iteration

### Trigger and corrected premise

The final independent code-review specialist found two medium-severity
correctness defects:

1. explicit init inspected optional tables before taking the SQLite write lock,
   so concurrent first upgrades could act on stale layout observations and
   falsely report corruption; and
2. the expanded exact-set layout remained stamped ledger schema 1, so the
   released v1 client reported a valid expanded ledger as corrupt.

The second finding disproved the prior compatibility premise. This iteration
does not revisit lifecycle, dispatch, native-binding, identity, autonomy, or
policy behavior; it corrects the on-disk discriminator and migration boundary.

### Revised Work Contract and authority

- primary object: `agent-system`
- impacts: `repository-change`, `production-operation`,
  `architecture-boundary`
- risk trigger: `irreversible-or-high-blast-radius-action`
- primary loop: `meta-eval`
- nested loops: `delivery`, `runtime`
- contributors: Architecture
- executors: Engineering and Operations
- verifier: Quality
- classification digest:
  `sha256:b61f63ea33961a3bcc25c29d784e6f561182d5dde55e7de1ae57290e46a9ed7b`
- route digest:
  `sha256:154558e84addacee607eea915bcc9eac23e899292061bbf36d675b7eddfda086`

Architecture selected the same-path ledger schema 2 correction over a sidecar
that could split control authority. A separate Architecture reviewer returned
PASS on the exact decision artifact. Decision Review returned
`human-review-required`; the authenticated maintainer approved artifact
SHA-256
`5bd8d04069ef3cca0043087cd53e12d6e72de9847cf9431394e85690b6094875`.

Meta/Eval accepts outcome observation as a review overlay on its existing
primary-loop lead role. The deterministic route format has no separate observer
slot for this contract, so no route digest or routing configuration is changed.

### Outcome observation

After implementation and any separately authorized retained-ledger operation,
observe:

- migration result by exact source layout and concurrent/single initializer;
- false-corruption numerator and independently established valid-layout
  denominator, with a zero guardrail;
- lock wait, write-transaction duration, total explicit-init duration, and
  quiescence duration;
- failed migration, ambiguous commit, destructive reset, state-loss, or
  untracked-native-work incidents;
- review rounds, material corrections, active review effort, calendar latency,
  and maintainer decision latency; and
- any dispatch/fan-out change only when evidence links it to migration or
  recovery. The ledger correction itself does not change fan-out policy.

Operations Release Evidence owns exact-artifact and privacy-safe migration
facts. Operations Incident Records own real failures or resets. This Evaluation
Report aggregates outcomes without adding a ledger table, metadata key, prompt,
source, user content, raw public agent ID, or free-form diagnostic field.

No retained ledger migration, destructive reset, release, or post-merge
observation has occurred in this iteration. One successful fixture migration
would not establish a rate or autonomy-promotion claim.
