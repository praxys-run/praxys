# Adaptive plan goal contracts

**Status:** Proposed in #603; not implemented

**Parent epic:** #582

**Architecture:** [Agent-native adaptive plan architecture](./adaptive-plan-architecture.md)

## Purpose

An adaptive plan needs an explicit definition of what it is trying to achieve.
The goal contract is the versioned agreement between the athlete and Praxys
that defines:

- the intended outcome;
- the evidence available at the start;
- what Praxys assumes and does not know;
- how feasibility and expectations are reassessed;
- what will count as outcome evidence; and
- how the result will be reviewed without inventing causality or blaming the
  athlete.

Completing a plan is not the same as achieving a goal. Following every workout
does not prove that the plan produced the intended adaptation, and missing
workouts does not by itself prove why a goal was missed.

This is a product and data contract. It does not approve test protocols,
training progression rules, feasibility thresholds, effect sizes, or
user-facing scientific claims. Those require the rigorous Evidence Review and
draft Science Decision Record that follow #603 in #582.

## Product decisions

1. **Every adopted plan has an exact goal version.** A plan cannot target a
   mutable settings dictionary.
2. **Intent is not yet a measurable goal.** "Improve my running" starts
   discovery but must resolve to an approved measurable goal contract before
   plan adoption.
3. **Success is defined before training starts.** Praxys cannot choose a more
   favorable outcome after seeing the result.
4. **A material goal change creates a successor.** The original target and its
   history remain intact.
5. **Expectations can change without changing the goal.** Praxys records that
   evidence has made the target more or less plausible; only the athlete can
   accept a changed target.
6. **Outcome can remain unknown.** Missing or weak evidence produces
   `indeterminate` or `not_evaluated`, not a guessed result.
7. **Objective and subjective evidence have different roles.** Athlete
   experience can qualify and explain an outcome but cannot silently replace a
   measurable target.
8. **No uncalibrated probability.** Praxys uses qualitative, explained
   feasibility categories until an individual probability has been
   prospectively validated and approved for the relevant population and use.
9. **Gap review is evidence review, not fault assignment.** It reports ranked
   hypotheses, contrary evidence, and unknowns.

## Goal contract aggregate

The logical contract below may be implemented across related tables. It is not
a requirement to store one unrestricted JSON document.

```text
GoalContract
  identity
    id
    user_id
    version
    supersedes_id?
    status
    created_at
    acknowledged_at?

  intent
    type
    purpose
    target
    target_date?
    review_horizon?

  starting_point
    baseline_evidence_snapshot_id?
    baseline_status
    baseline_observed_at?

  agreement
    success_criteria[]
    assumptions[]
    unknowns[]
    constraint_refs[]

  expectation
    current_assessment_id?
    initial_assessment_id?

  outcome
    status
    evidence_strength
    outcome_evidence_snapshot_id?
    evaluated_at?
    gap_review_id?
```

### Identity and ownership

- `id` is an opaque UUID.
- `user_id` is an explicit ownership foreign key with account-deletion
  behavior.
- `version` is monotonic within one goal lineage.
- `supersedes_id` points to the exact preceding material goal version.
- An adaptive plan references `goal_contract_id` and `goal_contract_version`.
- A goal contract cannot be transferred between athletes.

### Contract lifecycle

```text
intent -> draft -> assessable -> acknowledged -> active
   |        |          |             |           |
   +------> abandoned  +-----------> abandoned   +-> superseded
                                                 +-> completed
                                                 +-> ended
```

| State | Meaning |
| --- | --- |
| `intent` | The athlete has expressed a purpose, but Praxys cannot yet define measurable success. |
| `draft` | Target fields are being assembled; required inputs may be missing. |
| `assessable` | Required product fields exist and feasibility can be evaluated, possibly as insufficient evidence. |
| `acknowledged` | The athlete has reviewed the target, assumptions, risk, alternatives, and unknowns. |
| `active` | An adopted plan references this exact version. |
| `superseded` | The athlete accepted a material successor; linked historical plans retain this version. |
| `completed` | The review horizon or target event passed and an outcome was recorded or explicitly left indeterminate. |
| `ended` | The athlete ended the goal before its evaluation point. |
| `abandoned` | A non-active draft or intent was discarded. |

Acknowledgement records informed product consent. It does not make a target
scientifically supported and does not authorize Praxys to ignore a safety
boundary.

### Material versus non-material edits

A material edit creates a successor goal contract:

- goal type;
- target outcome or threshold;
- target date or review horizon;
- event distance or conditions relevant to the outcome;
- success criterion;
- accepted baseline when it materially changes interpretation; or
- an assumption that changes feasibility or plan structure.

Display labels, spelling corrections, and references to expired temporary
constraints may be updated without redefining success, but all writes remain
auditable.

When an active goal changes:

1. create and assess the successor;
2. show the old and new goal contract;
3. require athlete acknowledgement;
4. create a plan proposal against the successor;
5. retain the old plan and goal history; and
6. activate the successor only with the accepted plan revision.

## Goal types

### Goal-type matrix

| Type | Required target | Baseline | Primary outcome evidence | Subjective role | Unsupported or indeterminate examples |
| --- | --- | --- | --- | --- | --- |
| `race` | Event date, distance/type, and objective: finish, target time, or another approved event result | Recent relevant performance evidence or explicit `unavailable` | Verified or athlete-confirmed result from the target event | Race execution, conditions, perceived effort, symptoms, and context | Did not start, event changed/cancelled, result unavailable, incomparable course/conditions not modeled |
| `performance` | Approved metric, target value, protocol/equivalence class, and evaluation window | A comparable valid observation | Approved standardized test or defensible equivalent performance | Test validity, conditions, perceived effort, and reasons an attempt was invalid | Protocol mismatch, no valid attempt, stale baseline, metric not approved for planning |
| `consistency_base` | Bounded review horizon plus approved behavioral and/or sustainable-capacity criteria | Recent availability, activity history, and current sustainable capacity when available | Activity history for behavioral criteria; approved capacity evidence for physiological criteria | Sustainability, confidence, burden, pain/illness boundary, and fit with life | Tracking gap, shortened horizon, adherence without a defined capacity outcome |
| `general_improvement` | Athlete purpose plus selected measurable successor criteria | Depends on the selected successor | None while it remains an intent | Helps Praxys understand what "better" means | Cannot be adopted directly; remains `intent` until converted |

### Race goal

A race goal separates the event from the objective:

```text
event
  date
  distance_or_type
  course_or_condition_refs?  # only when supported

objective
  finish
  target_time
  approved_result_metric
```

A race date without a target time can support a finish goal or a
prepare-and-evaluate goal. It must not be represented as an implicit performance
target.

The target event result is the strongest outcome evidence when it is available
and comparable. Predictions, threshold trends, and test workouts are expectation
evidence; they do not replace the actual race outcome.

### Performance goal

A performance goal targets an approved measurable capability outside a
particular race result. It must name:

- the metric;
- target value and direction;
- approved protocol or equivalence class;
- baseline evidence;
- evaluation window; and
- invalidation conditions.

Examples might eventually include a standardized time trial or an approved
threshold estimate, but #603 does not approve any protocol or metric. A device
estimate is not automatically equivalent to a standardized performance test.

### Consistency/base goal

A consistency/base goal may combine:

- a **behavioral criterion**, such as completing an agreed sustainable
  frequency within a bounded horizon; and
- a **capacity criterion**, such as tolerating an approved sustainable weekly
  workload or long-run duration.

Behavioral success must be labeled behavioral. It cannot be presented as proof
of fitness improvement. A capacity or physiological claim requires approved
evidence and a valid baseline.

The contract should prefer ranges and sustainability over streaks. Illness,
injury, caregiving, travel, or changed availability may justify a successor
goal rather than turning real life into failure.

### General improvement intent

`general_improvement` is a discovery state, not an adoptable goal type. Praxys
asks what the athlete wants to become able to do and offers measurable
contracts, for example:

- prepare for a particular event;
- improve an approved test result;
- establish a sustainable training base; or
- return to a previously demonstrated capacity under an approved boundary.

If the athlete declines to select measurable success criteria, Praxys may offer
guidance without claiming to run a goal-achievement plan.

## Success criteria

Each criterion is immutable within a goal version:

```text
SuccessCriterion
  id
  kind                 # event_result | performance | behavior | capacity
  metric
  operator             # <= | >= | within | completed
  target
  unit
  evaluation_window
  protocol_id?
  evidence_requirement
  priority             # primary | supporting
  approved_science_decision_id?
```

Rules:

- Every assessable contract has exactly one primary criterion.
- Supporting criteria cannot override a failed primary criterion.
- Multiple primary objectives require separate goal contracts unless an
  approved composite outcome explicitly defines their relationship.
- Criterion units and direction are explicit.
- Outcome interpretation uses the criterion version acknowledged before the
  plan was adopted.
- A criterion requiring an unapproved protocol cannot advance beyond `draft`.

## Baseline contract

Baseline status is explicit:

| Status | Meaning |
| --- | --- |
| `current` | Evidence satisfies the approved recency and comparability policy. |
| `stale` | Evidence exists but is outside its approved recency boundary. |
| `incomparable` | Evidence uses a materially different protocol or conditions. |
| `missing` | No usable evidence exists. |
| `not_required` | The approved goal contract does not require a measured baseline. |
| `pending_test` | An approved baseline assessment has been proposed but not completed. |

The recency boundary and comparability rules are scientific parameters and are
not selected here.

Praxys may still assess a goal with missing evidence, but must return
`insufficient_evidence` and explain what would reduce uncertainty. It must not
manufacture a baseline from activity-average power or from an unrelated event.

## Feasibility and expectation assessments

An assessment is append-only and references the exact goal version and evidence
snapshot:

```text
GoalExpectationAssessment
  id
  goal_contract_id
  goal_contract_version
  trigger
  evidence_snapshot_id
  category
  confidence
  findings[]
  assumptions[]
  unknowns[]
  alternatives[]
  policy_version
  model_version?
  science_decision_ids[]
  created_at
```

### Categories

| Category | Product meaning |
| --- | --- |
| `insufficient_evidence` | Praxys cannot responsibly assess the target with current evidence. |
| `supported` | Current approved evidence does not reveal a material feasibility concern. This is not a guarantee. |
| `challenging` | The goal may be plausible, but important execution, progression, or uncertainty risks need explicit attention. |
| `aggressive` | Current evidence indicates a material gap or compressed horizon; warn before adoption and present safer alternatives. |
| `unsupported` | An approved policy says the requested target falls outside the supported planning boundary. Praxys must not generate a normal success-shaped plan for it. |

Thresholds between categories, their populations, and the allowed wording
require the Evidence Review and SDR. Until then, existing
`race_honesty_check()` output is legacy guidance, not an approved adaptive-plan
feasibility contract. Its hard-coded gap and time rules and causal language
must not be promoted into the new loop without review.

### Required presentation

Before adoption, show:

- the target and baseline;
- assessment category and confidence;
- supporting evidence;
- assumptions and material unknowns;
- the main risks;
- alternatives that preserve the athlete's purpose where possible;
- what additional evidence could improve the assessment; and
- the exact goal version the athlete is acknowledging.

Athletes may acknowledge `challenging` or `aggressive` goals if the approved
policy permits planning within that boundary. Acknowledgement does not override
`unsupported`.

### No personal probability by default

Do not show "you have a 70% chance" or an equivalent personal probability
unless the model has:

- a defined target population and outcome;
- prospective calibration;
- approved uncertainty and subgroup analysis;
- an accepted SDR for the claim; and
- ongoing drift and falsification monitoring.

Qualitative categories must also be evaluated, but they avoid false numerical
precision while the evidence base is incomplete.

## Ongoing expectation management

The goal remains unchanged when an expectation changes. Each reassessment
appends a new assessment linked to the previous one.

### Triggers

- scheduled weekly or block checkpoint;
- approved performance evidence;
- material planned-versus-completed stimulus divergence;
- interruption or changed availability;
- stale or corrected baseline evidence;
- athlete-requested reassessment;
- plan pause or resume; and
- approach to the target event or review horizon.

Workout-level observations should not repeatedly change the overall expectation
unless an approved policy identifies a material signal. This avoids turning
normal day-to-day variation into noisy warnings.

### Expectation change contract

Every changed assessment records:

- previous and current category;
- trigger;
- newly available or corrected evidence;
- unchanged evidence and contrary signals;
- whether confidence increased or decreased;
- plan implications;
- goal implications;
- a proposed action or explicit `no_change`; and
- whether an athlete clarification could materially change the assessment.

Possible actions include keeping the current plan, changing a workout/week/block,
pausing, reassessing after more evidence, or proposing a successor goal.

Praxys never silently edits the target to make status look better. A goal
change follows the successor workflow and requires athlete acknowledgement.

## Plan completion and goal outcome

Plan lifecycle and goal outcome are orthogonal:

```text
plan: active | paused | completed | ended
goal outcome: not_evaluated | achieved | partially_achieved |
              not_achieved | indeterminate
```

Examples:

- plan `completed`, goal `achieved`;
- plan `completed`, goal `not_achieved`;
- plan `ended`, goal `achieved` through an early event result;
- plan `completed`, goal `indeterminate` because no valid test occurred; or
- plan `ended`, goal `not_evaluated` because the horizon has not arrived.

### Outcome statuses

| Status | Meaning |
| --- | --- |
| `not_evaluated` | The evaluation point has not arrived, review has not run, or the athlete intentionally ended before evaluation. |
| `achieved` | Valid evidence satisfies the acknowledged primary criterion. |
| `partially_achieved` | An approved criterion defines meaningful partial attainment, or supporting outcomes improved while the primary target was not fully met. It is not an improvised consolation label. |
| `not_achieved` | Valid outcome evidence exists and does not satisfy the acknowledged primary criterion. |
| `indeterminate` | The evaluation point passed, but evidence is missing, invalid, incomparable, or too uncertain to classify. |

`partially_achieved` requires a criterion-specific rule approved before the
outcome review. Otherwise the primary criterion is either achieved,
not achieved, or indeterminate.

### Evidence strength

| Strength | Meaning |
| --- | --- |
| `direct` | Valid evidence measures the primary criterion under its approved outcome conditions. |
| `equivalent` | An approved equivalence rule maps a different observation to the criterion. |
| `supporting` | Evidence informs interpretation but cannot decide the primary outcome. |
| `subjective` | Athlete-reported experience or result not independently linked to a provider record. |
| `insufficient` | Evidence cannot support an outcome classification. |

For a race goal, a target-event result is normally direct evidence. A test
workout before or after the race is expectation or supporting evidence unless
an approved contract explicitly defines equivalence.

For a performance goal, only the named approved protocol or an approved
equivalent can be direct/equivalent evidence.

For consistency/base goals, activity records can directly measure behavioral
criteria. They are only supporting evidence for a physiological claim unless
the criterion names an approved capacity measure.

Athlete-reported evidence is valuable and may be the only available result, but
its source remains visible. Praxys does not pretend it was device-verified.

### Late evidence and corrections

An `indeterminate` outcome may be completed later when valid evidence arrives.
The earlier outcome assessment remains in history and is superseded, not
overwritten. Corrected provider data or athlete corrections follow the same
append-only pattern.

## Gap review

A gap review is required for `not_achieved` and offered for `partially_achieved`
or `indeterminate`.

```text
GoalGapReview
  observed_outcome
  original_expectation
  latest_acknowledged_expectation
  gap
  evidence_strength
  hypotheses[]
  unknowns[]
  questions[]
  next_step_implications[]
```

Each hypothesis contains:

```text
GapHypothesis
  category
  statement
  support[]
  contrary_evidence[]
  unknowns[]
  confidence
  claim_boundary
```

Allowed top-level categories:

- `initial_goal_calibration`;
- `plan_design`;
- `plan_execution`;
- `interruption_or_context`;
- `individual_response`;
- `event_or_test_execution`;
- `measurement_uncertainty`; and
- `unexplained`.

### Gap-review rules

- Rank only hypotheses supported by evidence.
- Include contrary evidence, not just confirming signals.
- Use `unexplained` when evidence cannot distinguish plausible causes.
- A missed workout is an observation, not proof of laziness, illness, or lack
  of motivation.
- Athlete-provided context is attributed as an athlete statement unless
  independently observed.
- Do not infer a diagnosis, treatment need, protected trait, or sensitive life
  circumstance.
- Do not infer that the plan caused improvement or failure from one athlete's
  before/after result.
- Separate plan adherence from delivered training stimulus and from outcome.
- Use split-level intensity evidence; never activity `avg_power`.
- Recommend a next assessment or safer planning choice when useful, but do not
  rewrite history.

The review should answer:

1. What outcome did we observe?
2. How did it differ from the agreed target and latest expectation?
3. What explanations have evidence?
4. What evidence argues against each explanation?
5. What remains unknown?
6. What should change, or be measured differently, next time?

## Surface and agent contracts

| Surface | Goal responsibility |
| --- | --- |
| Goal | Create and acknowledge the contract; show current target, baseline, feasibility, assumptions, unknowns, and version history. |
| Plan | Show the exact goal version the plan serves and how a proposed plan change affects expectation. |
| Insights | Explain expectation changes, checkpoint evidence, final outcome, and gap review. |
| Today | Show only goal context needed for today's decision; do not duplicate the full contract. |
| Activities | Supply and allow correction of execution/outcome evidence. |

Plugin, MCP, and future user-delegated agents use the same goal queries and
commands. They may help draft a target or request assessment, but cannot
acknowledge a goal or replace the athlete's target without an explicit
athlete-approved command.

Minimum logical capabilities:

- `get_goal_contract`;
- `draft_goal_contract`;
- `assess_goal_feasibility`;
- `acknowledge_goal_contract`;
- `propose_goal_change`;
- `record_goal_outcome`;
- `get_goal_gap_review`; and
- `correct_goal_outcome_evidence`.

Read, propose, acknowledge, and outcome-correction permissions remain separate.

## Legacy migration

Current configuration is a mutable dictionary:

```text
goal = {
  race_date,
  distance,
  target_time_sec
}
```

The current UI infers:

- race date present -> `race_date` display mode;
- target time without race date -> `cp_milestone` display mode; and
- neither -> `continuous` display mode.

These are display modes, not durable goal or outcome contracts.

### Additive migration

1. Keep current settings reads/writes while new contracts are introduced.
2. Project existing configuration into a migration draft:
   - race date present -> draft `race` contract;
   - target time without race date -> draft `performance` or race-time intent,
     requiring athlete confirmation of the intended outcome;
   - no date/time -> `general_improvement` intent.
3. Do not automatically mark projected drafts `acknowledged`.
4. Ask the athlete to confirm success criteria, baseline, horizon, and material
   assumptions before an adaptive plan adopts the contract.
5. Continue rendering the current Goal page until the new Goal experience is
   complete on web and miniapp.
6. Dual-read during migration, but write new adaptive plans only against the
   versioned contract.
7. Retire mutable goal updates only after first-party and agent clients use
   explicit goal commands.

Existing predictions and `race_honesty_check()` may be shown as legacy output
during migration, with their existing science notes and estimate caveats. They
must not be copied into the new feasibility or outcome ledger as if they were
approved goal-contract decisions.

## Privacy and deletion boundary

- Goal contracts are athlete-owned and deleted with the account.
- Goal purpose and subjective outcome may be sensitive; generic agent traces
  reference opaque IDs and allowlisted derived categories rather than copying
  narrative.
- Public analytics and evaluation corpora must not contain target dates, exact
  results, free text, or personal-context references.
- User-delegated agents receive only explicitly granted goal scopes.
- The later personal-context decision defines retention and AI-provider
  processing before context can become assessment evidence.

## Follow-up map

```text
goal contract (#603)
  -> rigorous feasibility/outcome Evidence Review
  -> draft SDR with category and evidence rules
  -> personal-context privacy and consent contract
  -> goal aggregate + version persistence
  -> pure feasibility and outcome evaluation
  -> goal query/command API
  -> Goal + Plan + Insights web/miniapp experiences
  -> plugin/MCP parity
  -> prospective calibration and outcome evaluation
```

## Decisions requiring product review

The proposal asks the product owner to confirm:

1. `general_improvement` is discovery intent and cannot directly adopt an
   outcome-promising plan.
2. Race, performance, and consistency/base are the first concrete goal types.
3. Plan completion and goal outcome remain independent.
4. `partially_achieved` is allowed only when defined before outcome review.
5. Missing or incomparable outcome evidence produces `indeterminate`, not
   failure.
6. Existing race/continuous settings become unacknowledged migration drafts.
7. Qualitative feasibility categories replace personal success probabilities
   until prospective calibration and science approval exist.

Approving this contract does not approve the scientific thresholds or protocols
that populate it.
