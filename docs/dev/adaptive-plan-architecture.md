# Agent-native adaptive plan architecture

**Status:** Proposed in #584; not implemented  
**Parent epic:** #582  
**Foundation:** #474, #520, and PR #569

## Purpose

Praxys plans must be agent-native rather than bound to one interface. Web,
miniapp, the Praxys plugin, MCP clients, and future user-delegated agents are
clients of one canonical planning domain. They may present different
experiences, but they must share plan identity, evidence, permissions,
proposals, revisions, delivery state, and outcomes.

The plan is not just a collection of dated workouts. It is a living,
goal-directed aggregate that records:

- what the athlete is trying to achieve;
- what Praxys currently believes and does not know;
- the current schedule and planning phase;
- proposed and accepted changes;
- why each decision was made;
- what was delivered to an execution platform; and
- what happened afterward.

This document defines the architecture boundary. It does not choose scientific
adjustment rules, collect personal context, or authorize broader automatic
mutation.

This is a direction-setting contract, not an attempt to predict every useful
detail before athletes use the lifecycle. Implementation should ship in
observable, reversible increments, begin with suggestion-only behavior, and
use real athlete experience to identify where the aggregate, permissions, and
interactions need revision. Iteration must still preserve privacy, science,
consent, audit, and compatibility invariants; learning from use is not
permission to silently broaden data collection or autonomy.

## Invariants

1. **One canonical domain.** Interfaces do not implement independent planners.
2. **Observe and propose before mutating.** An agent cannot write a plan merely
   because it can read the athlete's data.
3. **Facts, statements, inferences, and unknowns remain distinct.** Praxys must
   ask when an unknown would materially change a decision.
4. **Accepted changes are versioned.** Every mutation has an authenticated
   actor, base version, idempotency key, immutable revision, and consequence.
5. **Consent is scoped.** Read, propose, approve, mutate, and deliver are
   separate capabilities. An agent cannot grant itself approval.
6. **Science and safety gate actions.** Generative output cannot bypass
   deterministic validation, accepted science decisions, or medical
   boundaries.
7. **Private context is not telemetry.** Raw athlete narrative is not copied
   into generic agent traces, logs, analytics, public trackers, or evaluation
   corpora.
8. **Canonical state survives delivery failure.** Provider failure changes
   delivery state, not the accepted Praxys plan.
9. **No causal invention.** Post-plan analysis may rank supported hypotheses;
   it must preserve contrary evidence and unknowns.
10. **Current behavior remains compatible.** Existing workout CRUD, revisions,
    rolling delivery, and reconciliation continue during migration.

## Existing foundation

| Existing contract | Role in the adaptive architecture |
| --- | --- |
| `TrainingPlan` | Canonical or external workout row. Praxys-owned rows remain the executable schedule, but are not the plan aggregate. |
| `canonical_id` | Stable identity for an individual canonical workout. |
| `PlanRevision` | Append-only mutation and delivery-consequence ledger. Remains authoritative for accepted workout changes. |
| `PlanDelivery` / `PlanDeliveryAttempt` | Provider-neutral current delivery state and append-only attempt history. |
| Target calendar snapshot and reconciliation | Observation of execution-platform state and explicit conflict resolution. |
| `plan_management` config | Existing ownership, execution target, delivery consent, and conservative-adjustment consent. |
| `analysis/plan_adjustments.py` | Example of a pure, bounded decision policy. It is not a general adaptive planner. |
| Canonical workout APIs | Existing optimistic, ownership-fenced workout mutation path. |
| MCP managed-plan tools | Existing interface over authoring, lifecycle, delivery, and reconciliation. |
| `AgentDecision` / `AgentOutcome` | Reusable trace pattern, but not yet safe as the athlete-plan ledger because `AgentDecision` has no athlete ownership foreign key or account-deletion relationship. |

The adaptive layer adds an aggregate above these contracts. It does not replace
provider adapters or make platform calendars canonical.

## Domain boundaries

### Adaptive plan aggregate

`AdaptivePlan` is the aggregate root. Its persistent contract needs:

- opaque plan ID and owning user ID;
- explicit primary discipline (`running` or `trail_running`), never inferred;
- goal-contract ID and goal-contract version;
- purpose, start, target/end date, and planning horizon;
- lifecycle status;
- current phase or block;
- monotonic aggregate version;
- current autonomy policy and consent version;
- active schedule/proposal references;
- outcome-contract ID and completion state; and
- creation, activation, pause, completion, and end timestamps.

The aggregate owns lifecycle and accepted intent. `TrainingPlan` rows remain the
workout schedule owned by an active aggregate. A future additive foreign key
associates Praxys-owned workout rows with their plan without changing
`canonical_id`.

Only one active adaptive plan may own a user's future Praxys workout lane.
Draft and completed plans may coexist. External workouts remain observations
and never silently join the aggregate.

### Goal contract

A versioned goal contract defines what success can mean before plan generation:

- goal type: race, performance, consistency/base, or another approved type;
- target and target date, when applicable;
- baseline evidence and freshness;
- objective outcome evidence;
- permitted subjective evidence;
- feasibility assessment version; and
- assumptions and unresolved inputs.

Changing a material goal creates a new goal-contract version and forces
reassessment. It does not rewrite the original plan intent.

The proposed goal types, lifecycle, feasibility assessment, outcome evidence,
gap review, and legacy migration are specified in
[`adaptive-plan-goal-contracts.md`](./adaptive-plan-goal-contracts.md). That
contract is a product proposal under #603; its scientific thresholds and test
protocols remain blocked on the subsequent Evidence Review and draft SDR.

### Evidence snapshot

Every assessment or proposal references an immutable logical evidence snapshot.
The snapshot records identifiers, source revisions, observation windows, and
privacy-minimized derived signals. It does not duplicate raw activities,
recovery rows, workout splits, or personal narrative.

Evidence is classified as:

- `observed`: device, activity, recovery, or calendar evidence;
- `athlete_stated`: optional context explicitly supplied by the athlete;
- `inferred`: a versioned model interpretation;
- `assumed`: an explicit planning assumption; or
- `unknown`: a material unresolved question.

Intensity evidence always uses activity splits or samples, never activity
`avg_power`.

### Plan proposal

`PlanProposal` is immutable and non-canonical. It contains:

- plan ID and base aggregate version;
- explicit plan discipline plus per-workout `activity_type`;
- proposal scope: plan, block, week, workout, goal, pause, resume, or end;
- proposed before/after snapshots or a typed patch;
- versioned workout structure (`v1`) instead of description-derived intervals;
- evidence-snapshot and decision references;
- rationale, uncertainty, trade-offs, and affected goal expectation;
- policy, model, prompt, and science-decision versions;
- required approval and allowed responses;
- expiry and supersession state; and
- proposing actor and origin.

A proposal can be accepted, edited into a successor, rejected, deferred,
expired, or superseded. None of those states mutates the plan except acceptance.

### Plan-generation capability registry

Every interface discovers automatic generation through one authenticated,
versioned capability registry rather than selecting a planner from hard-coded
client conditions. The registry:

- contains accepted generation policies only;
- resolves the authenticated athlete's current normalized goal on the backend;
- returns the exact policy, generator, science decision, constraint-schema,
  horizon, reassessment cadence, and policy-specific action paths;
- publishes a versioned purpose contract for each capability;
- treats the current Goal as a default when it matches, not as a mandatory
  binding for every plan;
- supports an explicitly selected capability-owned purpose only when the
  accepted capability permits it;
- returns `no_accepted_policy` when no reviewed policy matches instead of
  repurposing another distance or population policy; and
- keeps the existing typed policy endpoints compatible while web, miniapp,
  plugin, MCP, and future agents share the same discovery contract.

Draft Evidence Reviews, draft SDRs, roadmap intent, and unsupported populations
never make a capability available. Adding a capability requires its own accepted
science decision plus deterministic validation and client support for the named
constraint schema.

### Plan-purpose provenance

Plan purpose is resolved before readiness and remains part of every subsequent
source fence, audit, proposal, and immutable goal snapshot:

- `current_goal` references the owner-scoped current Goal by stable ID and
  exact content revision;
- `capability` uses the accepted capability's own bounded goal contract without
  modifying or linking the Goal page; and
- `unlinked` is available only when the accepted capability explicitly permits
  a base plan with no goal contract.

The current Goal is the client default only when an accepted capability matches
it. Unsupported current Goals remain unchanged while the athlete may choose a
separate accepted purpose. A material edit to a linked Goal marks the active
plan or draft `reassessment_required`; independent plans remain independent.
Legacy snapshots without provenance are reported as `legacy_unknown` rather
than guessed into a current link.

The mutable current Goal keeps one owner-scoped ID. Its revision hashes only
the normalized plan-relevant fields: goal kind, distance, target time, and race
date. Equivalent aliases, casing, empty values, and zero/null target values
normalize before hashing; display labels and unrelated metadata never trigger
plan reassessment.

After a meaningful Goal edit, the settings write returns an authoritative
Goal-plan impact so web and miniapp present the same decision. Settings reads
and capability discovery expose the same outstanding impact after reload. A
client may dismiss it for the current in-memory visit, but dismissal does not
erase the authoritative `reassessment_required` state.

- **Review and update** enters the existing successor-proposal flow. Canonical
  workouts do not change until the athlete adopts an exact proposal.
- **Keep current plan** preserves the canonical workouts and delivery state,
  creates an acknowledged capability-owned successor goal snapshot, supersedes
  the linked historical snapshot without mutating it, rejects any unexpired
  stale draft, expires an elapsed draft, and records an idempotent append-only
  plan revision.
- **Decide later** leaves `reassessment_required` active. The current plan and
  delivery continue; nothing pauses silently.

If the new Goal has no accepted policy, automatic successor generation remains
unavailable. The athlete can keep the current plan independently or manage
workouts manually; Praxys never repurposes another policy. Independent and
`legacy_unknown` plans do not gain inferred Goal linkage.

Each keep decision is fenced by both the current Goal revision and the exact
immutable linked plan-goal snapshot. That snapshot ID identifies the
reconciliation episode, preventing an old idempotent response from being
replayed if the same plan is later linked again and a prior Goal revision
recurs. An expired successor draft is recorded as expired, not user-rejected.

### Structured workout contract v1

Proposal workouts and canonical `TrainingPlan` rows carry a versioned
`workout_structure` alongside compatibility flat fields. The structure is
authoritative; flat duration, distance, and targets are projections derived
only when Praxys can do so without inventing missing information.

- `discipline` is the adaptive plan's primary lane (`running` or
  `trail_running`).
- `activity_type` is per workout and stays separate from `workout_type`
  (`running`, `trail_running`, `cycling`, `strength`, `rest`, etc.).
- Non-rest workouts need at least one executable step. Rest workouts may use
  `{"steps": []}` and must not retain executable steps.
- Step semantics are the fixed portable set `warmup`, `work`, `recovery`,
  `rest`, `cooldown`, and `other`. Warm-up and cool-down steps are optional
  and have no positional requirement. A `repeat` is a structural group, never
  a step semantic.
- A step may carry a user-defined `label` of at most 80 characters and
  user-defined coaching `instructions` of at most 1000 characters. A repeat
  group may carry a user-defined `label` of at most 80 characters. Praxys
  trims leading and trailing whitespace, treats blank-only optional wording
  as absent, rejects overflow rather than truncating it, and otherwise retains
  the normalized canonical wording exactly.
- Step terminations are `time`, `distance`, `open`, or `manual`.
- Intensity targets are typed. Valid combinations are:
  `none`; power in `watts` or `%CP`; heart rate in `bpm` or `%LTHR`; pace in
  `sec_per_km` or threshold-relative `sec_per_km_delta`; and `RPE` on a
  10-point scale.

Rows with both structure fields absent remain legacy-flat. A version without a
payload, a payload without a version, or an unknown version is not flat and
must fail closed. Flat editors may update notes and other non-structural fields
without resubmitting the authoritative structure; any changed flat projection
must match the projection derived from that structure. Entering rest replaces
an authoritative structure with empty v1, while leaving an authoritative rest
row explicitly synthesizes and validates a new executable v1 structure.

Provider dispatch follows the same distinction. Stryd translates only
non-empty v1 time steps/repeats whose phases map to warmup, work, recovery, or
cooldown and whose targets are power-based. The connector has no verified
lossless mapping for step/group labels or step instructions, so any structured
workout containing that wording is rejected with the existing provider-request
unsupported path; it is never sent with wording silently removed. The portable
`rest` phase is also rejected because Stryd cannot distinguish it losslessly
from recovery. Distance/open/manual terminations, `other` phases, non-power
targets, provider-specific modifiers, malformed pairs, and unknown versions
are rejected instead of flattened. Garmin currently accepts only genuinely
flat running rows and rejects every structured workout. For reconciliation,
Stryd track, treadmill, and unknown surfaces are also unrepresentable because
the canonical activity contract can round-trip only road running and trail
running. Garmin calendar summaries are not acceptable target snapshots until
their authoritative template steps have a lossless provider-neutral
translation.

Example interval workout:

```json
{
  "discipline": "trail_running",
  "activity_type": "trail_running",
  "workout_type": "interval",
  "workout_structure_version": "v1",
  "workout_structure": {
    "steps": [
      {
        "type": "step",
        "phase": "warmup",
        "label": "Trail warm-up",
        "instructions": "Stay relaxed on the first climb.",
        "termination": { "type": "time", "seconds": 900 },
        "target": {
          "metric": "power",
          "unit": "percent_cp",
          "reference": "critical_power",
          "min": 65,
          "max": 75
        }
      },
      {
        "type": "repeat",
        "label": "Main set",
        "repetitions": 4,
        "steps": [
          {
            "type": "step",
            "phase": "work",
            "label": "Uphill power",
            "instructions": "Run tall with quick feet and quiet shoulders.",
            "termination": { "type": "time", "seconds": 240 },
            "target": {
              "metric": "power",
              "unit": "percent_cp",
              "reference": "critical_power",
              "min": 95,
              "max": 100
            }
          },
          {
            "type": "step",
            "phase": "recovery",
            "label": "Float down",
            "instructions": "Keep moving without chasing pace.",
            "termination": { "type": "time", "seconds": 180 },
            "target": {
              "metric": "power",
              "unit": "percent_cp",
              "reference": "critical_power",
              "min": 60,
              "max": 65
            }
          }
        ]
      },
      {
        "type": "step",
        "phase": "cooldown",
        "label": "Easy finish",
        "instructions": "Let effort fall naturally.",
        "termination": { "type": "time", "seconds": 600 },
        "target": {
          "metric": "power",
          "unit": "percent_cp",
          "reference": "critical_power",
          "min": 60,
          "max": 70
        }
      }
    ]
  }
}
```

### Accepted revision

Accepting a proposal is one transaction:

1. verify the actor and `plan:approve` permission;
2. lock the user/plan write lane;
3. compare the proposal base version with the active aggregate version;
4. rerun deterministic validation and safety gates;
5. apply aggregate and workout changes;
6. increment the aggregate version;
7. append `PlanRevision` records linked to the proposal and decision;
8. commit canonical state; and
9. schedule delivery consequences after the canonical commit.

If the base version is stale, acceptance fails with a structured conflict. The
agent must reassess; it must not silently rebase its own proposal.

### Outcome

`PlanOutcome` links an expected effect or goal contract to later evidence. It
supports:

- proposal accepted, edited, rejected, or deferred;
- workout execution, modification, or non-completion;
- checkpoint expectation change;
- race result or standardized performance test;
- base/consistency capacity result;
- athlete assessment; and
- plan completion or early ending.

An outcome records what was observed, not a causal verdict. Gap analysis stores
ranked hypotheses with supporting evidence, contrary evidence, and unknowns.

## Lifecycle state machine

```text
                           reject
                     +----------------+
                     |                v
draft ---> proposed -+-> active <--> paused
  |                       |  ^          |
  | abandon               |  | accept   | resume with reassessment
  v                       v  |          v
ended                 replanning ------+
                          |
                          +-----------> active
                          |
                          +-----------> ended

active -------------------------------> completed
paused -------------------------------> ended
```

`replanning` does not invalidate the accepted schedule. The active version stays
canonical until a successor proposal is accepted.

| Command | From | To | Approval and consequence |
| --- | --- | --- | --- |
| Create draft | none | `draft` | Athlete request or explicitly authorized authoring client; no delivery. |
| Present for adoption | `draft` | `proposed` | Feasibility, validation, assumptions, and warnings must be attached. |
| Adopt | `proposed` | `active` | Athlete approval; creates initial accepted revision and may start separately consented delivery. |
| Reject draft | `proposed` | `ended` | Athlete action; preserves proposal history without future workouts. |
| Request reassessment | `active` | `replanning` | Athlete, checkpoint policy, or authorized proposing agent; no canonical mutation. |
| Accept revision | `replanning` or `active` | `active` | Athlete approval by default; applies an exact proposal against its base version. |
| Pause | `active` or `replanning` | `paused` | Athlete approval, except a separately approved safety guardrail may halt delivery while requesting confirmation. |
| Resume | `paused` | `replanning` | Always reassess stale schedule and current state before returning to `active`. |
| Complete | `active` | `completed` | Goal-specific outcome review is created or explicitly marked pending. |
| End early | `draft`, `proposed`, `active`, `replanning`, or `paused` | `ended` | Athlete approval; future delivery cleanup is an explicit separate consequence. |

Terminal plans are immutable except for adding late outcome observations or
privacy/account-deletion processing.

## Per-athlete agentic loop

```text
sense -> understand -> evaluate -> propose -> approve/act -> observe -> repeat
```

### Triggers

- plan creation or goal change;
- completed, modified, or missed workout;
- successful data sync;
- athlete context addition, correction, expiry, or deletion;
- daily safety signal;
- weekly or block checkpoint;
- stale baseline or goal-feasibility evidence;
- pause, resume, or material delivery conflict; and
- plan target date or completion.

Triggering the loop does not imply generating a proposal. `no_change`,
`clarification_required`, `insufficient_evidence`, and `escalate` are valid
decisions.

### Sense

Load through bounded data-layer functions:

- active plan and exact aggregate version;
- goal contract and latest feasibility assessment;
- canonical workouts and immutable revision history;
- activities and split-level execution evidence;
- recovery observations and freshness;
- delivery/reconciliation state;
- active athlete-context references permitted for this purpose; and
- prior decisions and linked outcomes.

Produce an evidence snapshot before model reasoning.

### Understand

Build a typed context that keeps observed facts, athlete statements, inferences,
assumptions, and unknowns separate. If two plausible explanations imply
different actions, return one focused clarification question rather than
selecting a cause.

### Evaluate

Run deterministic scientific and safety policies first. A model may synthesize
their output, identify patterns, and compare options, but it cannot weaken a
guardrail. Evaluation returns:

- current assessment;
- goal expectation and whether it changed;
- supported risks and uncertainties;
- missing information;
- permissible action scopes; and
- policy/model/science versions.

Any personal success probability must be prospectively calibrated before it is
shown. Until then, use explained feasibility bands and evidence gaps.

### Propose

Create an immutable proposal or a no-change/clarification decision. Every
proposal includes a before/after diff, evidence, rationale, uncertainty,
trade-offs, and expected goal effect.

### Approve and act

Suggestions are the default. Athlete approval commits the proposal through the
canonical command service. A separately consented automatic policy may approve
only its allowlisted action, evidence conditions, and scope. The proposing
agent cannot expand that policy or approve itself.

### Observe

Attach later outcomes to the decision and proposal. A single workout is usually
too weak to validate a planning policy; checkpoint and plan-level outcomes
accumulate without asserting causality.

## Command and query surface

Names below describe capabilities, not final HTTP paths or MCP tool names.

### Queries

| Capability | Result |
| --- | --- |
| `get_plan_state` | Aggregate, goal contract, phase, schedule summary, active proposal, delivery state, and version. |
| `get_plan_evidence` | Purpose-bounded evidence references, classifications, freshness, and unknowns. |
| `get_plan_revisions` | Accepted mutations, actors, linked proposals, and consequences. |
| `get_plan_outcomes` | Checkpoint and terminal outcomes with evidence strength and unresolved gaps. |
| `assess_plan` | Read-only current evaluation; never writes a proposal or plan. |

### Proposal commands

| Capability | Effect |
| --- | --- |
| `draft_plan` | Creates a non-canonical draft against a goal contract. |
| `propose_plan_adoption` | Validates a draft and presents feasibility, assumptions, and warnings. |
| `propose_plan_change` | Creates a scoped immutable diff against an exact active version. |
| `request_plan_context` | Creates a purpose-bounded optional question; does not infer an answer. |
| `defer_plan_proposal` | Keeps canonical state unchanged and records when reassessment is useful. |
| `reject_plan_proposal` | Keeps canonical state unchanged and records a bounded reason when supplied. |

### Canonical commands

| Capability | Effect |
| --- | --- |
| `adopt_plan` | Activates an approved initial version. |
| `accept_plan_proposal` | Applies one exact proposal transactionally. |
| `update_plan_workout` | Existing direct workout control, recorded as a manual accepted revision. |
| `undo_plan_revision` | Restores only when the expected after-state is still current. |
| `pause_plan` / `resume_plan` | Changes lifecycle through reassessment rules. |
| `end_plan` / `complete_plan` | Closes future planning and starts outcome review. |
| `resolve_plan_delivery_conflict` | Uses existing opaque reconciliation identity and allowlisted actions. |

Direct workout editing remains available. It supersedes stale proposals that
touch the same plan version or workout rather than merging them silently.

## Permission model

Proposed scopes:

- `plan:read`
- `plan:context:read`
- `plan:context:write`
- `plan:propose`
- `plan:approve`
- `plan:mutate`
- `plan:deliver`
- `plan:admin`

| Actor | Read | Propose | Approve | Mutate | Deliver |
| --- | --- | --- | --- | --- | --- |
| Athlete through first-party UI | Own plan | Yes | Yes | Via approved commands | Via separate delivery consent |
| First-party planning agent | Purpose-bounded | Yes | No | No | No |
| Current conservative adjustment policy | Bounded evidence | One allowlisted action | Only under separate exact consent | Exact allowlisted mutation | Existing managed-delivery policy |
| Praxys plugin/MCP agent | Token-scoped | If granted | No by default; athlete confirmation required | Only explicit athlete command with scope | If separately granted |
| Future user-delegated agent | Token-scoped and purpose-bounded | If granted | No by default | Only explicit delegated command with expiry and scope | If separately granted |
| Provider adapter | Required delivery projection | No | No | No canonical mutation | One configured target |
| Operator/admin | Operational metadata only by default | No | No | Recovery tools only | Recovery tools only |

Authentication does not imply every scope. Context access is narrower than plan
read access, and free-text context requires an explicit purpose and retention
contract. The complete context classes, lifecycle, AI-processing boundary,
retention rules, and delegated-actor matrix are defined in
[`adaptive-plan-personal-context-privacy.md`](./adaptive-plan-personal-context-privacy.md).

## Decision, revision, and outcome traces

The ledgers answer different questions:

| Ledger | Question |
| --- | --- |
| Agent decision | What assessment or proposal did a versioned policy produce from a bounded evidence snapshot? |
| Plan proposal | What non-canonical change was offered to the athlete? |
| Plan revision | What canonical mutation was accepted and committed? |
| Delivery attempt | What happened when the accepted plan was projected to a provider? |
| Agent/plan outcome | What was later observed about the decision, execution, or goal? |

An athlete planning decision may use the existing `AgentDecision` pattern only
after the schema has an explicit owning-user foreign key with account-deletion
behavior. A string `subject_ref` is not an ownership or privacy boundary.

Allowed decision trace content:

- opaque plan, proposal, evidence-snapshot, and policy identifiers;
- source revision counters and time windows;
- allowlisted derived categories or numeric signals approved for the policy;
- hashes of bounded inputs;
- model, prompt, policy, and science-decision versions;
- output type, scope, confidence category, and uncertainty category; and
- links to later proposal, revision, and outcome records.

Disallowed generic trace content:

- raw athlete narrative or context answers;
- activity descriptions or location traces;
- credentials, provider payloads, or screenshots;
- unrestricted LLM prompts containing athlete data; and
- medical diagnoses or inferred sensitive traits.

Deleting an account must cascade through plan aggregates, proposals, decisions,
context references, revisions, deliveries, and outcomes. Aggregated product
evaluation may retain only records proven non-identifying under the separately
approved privacy contract.

## Logical event taxonomy

These are durable domain event types, not a requirement to add a message broker.
Existing append-only tables may carry them where their ownership fits.

### Observation

- `plan.evidence_snapshotted`
- `plan.execution_observed`
- `plan.context_requested`
- `plan.context_supplied`
- `plan.context_expired`
- `plan.delivery_conflict_observed`

### Decision and proposal

- `plan.assessed`
- `plan.no_change_decided`
- `plan.clarification_required`
- `plan.proposal_created`
- `plan.proposal_deferred`
- `plan.proposal_rejected`
- `plan.proposal_expired`
- `plan.proposal_superseded`

### Canonical mutation

- `plan.adopted`
- `plan.revised`
- `plan.workout_manually_changed`
- `plan.revision_undone`
- `plan.paused`
- `plan.resumed`
- `plan.completed`
- `plan.ended`

### Consequence and outcome

- `plan.delivery_requested`
- `plan.delivery_succeeded`
- `plan.delivery_failed`
- `plan.checkpoint_observed`
- `plan.goal_outcome_observed`
- `plan.gap_review_created`

Every event has an owning user, plan ID, actor, origin, idempotency key or
fingerprint, policy/schema version, and timestamp.

## Failure semantics

| Condition | Required behavior |
| --- | --- |
| Stale aggregate/proposal version | Return a structured conflict; supersede or reassess. Never silently rebase. |
| Missing or stale evidence | Return insufficient evidence, request context, or keep the plan unchanged. |
| Ambiguous reason for divergence | Ask a focused optional question; do not infer motive, illness, or constraint. |
| LLM unavailable | Preserve deterministic evaluation and manual plan management; do not return a success-shaped invented proposal. |
| Science or safety gate fails | Reject the proposal with the governing policy and evidence reference. |
| Provider disconnected or write fails | Keep canonical acceptance, record failed consequence, surface retry/reconnect state. |
| Proposal expires | Keep canonical state and require reassessment against a new evidence snapshot. |
| Duplicate command | Return the prior idempotent result without a second mutation or delivery. |
| Personal context inaccessible or deleted | Reassess without it and mark the relevant assumption unknown. |
| Terminal outcome unavailable | Mark outcome pending or unknown; do not substitute adherence as proof of success. |

## Product surface boundaries

| Surface | Primary job | Agentic-loop role |
| --- | --- | --- |
| Today | Decide today's action | Immediate observation and bounded daily decision |
| Training | Manage future intent and accepted changes | Proposals, approvals, canonical revisions, lifecycle, and delivery |
| Analysis | Understand progress, risk, and gaps | Evaluation, expectation change, checkpoint and outcome explanation |
| Goal | Define the objective and feasibility contract | Goal versioning, assumptions, and success criteria |
| Activities | Inspect what occurred | Raw execution evidence and correction |

Analysis can initiate `propose_plan_change`, but Training owns review and
application of the canonical diff. Web exposes Training and Analysis as separate
top-level routes. Miniapp exposes Training and Analysis as separate primary tabs;
Analysis keeps its source Activities behind an in-page switch so the constrained
five-item tab bar can reserve Me for settings and secondary tools.

Plugin and MCP experiences may combine these jobs conversationally, but tool
calls still respect the same query/command and permission boundaries.

## Compatibility and migration

1. **Decision records first.** Approve goal, science, privacy, and authorization
   contracts before storing new athlete context or enabling new mutations.
2. **Add the aggregate in shadow.** Create additive plan identity and lifecycle
   storage, then project existing Praxys-owned workouts and
   `plan_management.mode` into a compatible active-plan view.
3. **Associate current workouts.** Add nullable plan ownership to canonical
   workout rows; backfill without changing `canonical_id`, source, origin, or
   provider identity.
4. **Add read-only assessment.** Expose aggregate/evidence queries and run the
   loop in shadow or suggestion-only mode.
5. **Add immutable proposals.** Persist proposals and athlete-scoped decisions;
   do not mutate plans.
6. **Route acceptance through existing writes.** Reuse the canonical workout
   mutation, revision, delivery, and reconciliation fences inside an aggregate
   transaction.
7. **Split Plan and Insights experiences.** Move current plan management and
   training interpretation without changing underlying semantics.
8. **Add lifecycle and outcomes.** Pause/resume/replan/complete plus
   goal-specific outcome contracts.
9. **Expand automation last.** Promote only narrow policies with explicit
   consent, prospective evaluation, audit, undo, and a kill switch.

Existing `/api/plan` and workout mutation contracts remain supported until all
first-party and plugin clients use aggregate-aware versions. Delivery adapters
continue to consume canonical workouts, not model prose or private context.

## Follow-up implementation map

```text
architecture (#584)
  -> goal contracts
  -> rigorous Evidence Review + draft SDR
  -> privacy/context + delegated authorization contract
  -> aggregate and proposal data model
  -> bounded data loaders and pure evaluation policies
  -> orchestration and athlete-scoped decision/outcome ledger
  -> API query/command contracts
  -> Plan + Insights web/miniapp experiences
  -> plugin/MCP tools over the same contracts
  -> delivery/reconciliation integration
  -> prospective evaluation and policy promotion
```

Expected implementation surfaces:

- `db/models.py` and account deletion for aggregate, proposal, ownership, and
  athlete-scoped trace relationships;
- `analysis/data_loader.py` for bounded evidence loading;
- pure evaluation functions under `analysis/`;
- `api/deps.py` and thin routes for aggregate queries and commands;
- `api/managed_plan_ops.py`, plan revisions, delivery, and reconciliation for
  accepted consequences;
- `web/src/types/api.ts`, Plan and Insights routes, and matching miniapp pages;
- plugin MCP tools that call the same API contracts; and
- tests for state transitions, permissions, privacy, idempotency, concurrency,
  undo, deletion, parity, and failure states.

## Human decisions still required

- Goal types, success criteria, and when a standardized test is appropriate.
- Accepted science boundaries for feasibility, progression, interruption,
  adaptation, and outcome interpretation.
- Whether the narrow personal-context pilot defined in
  [`adaptive-plan-personal-context-privacy.md`](./adaptive-plan-personal-context-privacy.md)
  is expanded to durable profiles or delegated narrative access.
- Whether the generic agent ledger is extended with athlete ownership or a
  dedicated plan-decision ledger is introduced.
- Exact automation classes eligible for consent and prospective evaluation.
- Final Plan/Insights navigation on web and miniapp after rendered UX review.

No architecture decision here authorizes a scientific claim, sensitive-data
collection, or autonomous behavior. Those remain draft decisions until the
required human review is complete.
