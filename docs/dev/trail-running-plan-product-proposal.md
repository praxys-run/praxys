# Trail-running managed-plan product proposal

**Status:** proposed logical-contract handoff; human Product review required.
**Primary use case:** owner-only preparation for the Ninghai Trail Challenge on
2026-11-15, 24.7 km with 618 m stated ascent, performance intent.

This record does not mark a Product decision accepted, activate a capability,
collect production data, or authorize implementation. Product Decision Records
remain a logical contract in the current operating model; this document does
not invent a new persistence or approval schema.

## Work Contract

- Classification: sha256:55c4da66e7f504dd0d40c681c2a006fdbe7079c0cd06de43cb95802e679f78f5
- Route: sha256:2f237b07f7a41582707e1a647e69aa634749c487c258b555c559f80f98cfc160
- Primary loop: Science
- Nested loops: Product, Design, Delivery
- Review route: human-review-required

## Shared decision fields

- **ID:** pdr-owner-non-ultra-trail-plan-v1
- **Owner role:** Product
- **Question:** Should Praxys expose a governed, history-anchored non-ultra
  trail performance plan to the owner first, beginning with Ninghai, while
  every later user joins explicitly from a visible catalog?
- **Dependencies:** the draft trail ontology and non-ultra trail Evidence
  Reviews and SDRs. Each must be accepted and implementation-approved before
  runtime activation.
- **Recommendation:** approve the minimum valuable slice below as reversible
  Product guardrails, implement it inactive, and activate it only for the
  authenticated owner after independent verification.
- **Outcome plan:** observe course clarification, readiness, proposal review,
  edits, adoption, withdrawal, and validation failures. One owner cannot
  establish efficacy or safety.

## User problem and known state

Praxys can version, adopt, and deliver workouts, but it cannot turn a trail
race into a governed plan. A distance-only road template would discard descent,
grade, technicality, environment, support, terrain access, and recent downhill
exposure. A hand-authored plan would unblock one athlete but bypass the path
future users need.

Known for the first use case:

- event date: 2026-11-15;
- distance: 24.7 km;
- stated ascent: 618 m;
- intent: race as well as possible;
- evidence source: existing owner-scoped Praxys training data;
- client: Web creation, review, and exact-version adoption.

Still unknown until the owner or a verified course source resolves it:

- expected finish-time range;
- total descent and grade distribution;
- technicality and surface mix;
- maximum altitude and expected heat, humidity, wind, and exposure;
- aid stations, mandatory equipment, and external support;
- available training terrain and schedule constraints;
- recent downhill and technical-terrain exposure;
- fueling and gastrointestinal-practice history.

The descriptive ascent ratio is about 25.0 m/km. It is not a difficulty score,
equivalence, or substitute for the unknown fields.

## Options

### A. Owner-only governed rolling plan — recommended

Capture trail_course_demand_v1, use existing owner history, return a
deterministic 14-day proposal, require exact review and adoption, and reassess
after seven completed days. Start with no automatic load increase.

### B. Hand-build one Ninghai plan — rejected

This is faster to display but bypasses governed generation, deterministic
replay, proposal provenance, and later-user scalability.

### C. Adapt an existing road policy — rejected

This silently invents equivalence and loses material trail demands.

### D. Wait for a universal trail prescription — rejected

A reversible, transparent owner pilot can provide value without claiming
biological optimality.

## Minimum valuable slice

### Capability and access

- Capability ID: non_ultra_trail_performance_v1.
- Constraint schema: non_ultra_trail_constraints_v1.
- Course schema: trail_course_demand_v1.
- Discipline remains trail_running through goal, proposal, plan, and delivery
  compatibility checks.
- Production access starts owner-only. The backend repeats the owner gate at
  discovery, readiness, generate, regenerate, read, edit, adopt, withdraw, and
  delivery-preview boundaries.
- The capability remains absent from non-owner discovery during the pilot.
- Later Trail policies appear in the authenticated catalog only after their
  own accepted policy and verified implementation. Users actively join;
  Praxys sends no invitations, auto-enrolment, or promotional exposure.

### Reversible Product guardrails

These are Product choices, not published biological thresholds:

| Guardrail | Proposed value | Product reason |
| --- | --- | --- |
| Committed proposal | 14 calendar days | Two weekly units are useful without pretending to prescribe the full race horizon. |
| Advisory reassessment | after 7 completed days | New completed history may shape a successor without rewriting an adopted block. |
| History lookback | 8 completed weeks | A bounded window already proven operational in managed-plan code. |
| Minimum usable history | 4 completed weeks with at least 3 running sessions each | Prevents a history-rich policy from extrapolating from sparse records. |
| Latest run | within 10 completed days | A reversible current-history cutoff, not a biological law. |
| Comparable trail exposure | at least 2 qualifying outdoor hilly/trail sessions in 42 days, including 1 in 21 days | Requires recent direct exposure without claiming race readiness. |
| Running days | 3–6 per seven-day unit, never above recent modal frequency or stated availability | Organizes existing behavior without a frequency jump. |
| Planned minutes | no more than the lower of recent median usable-week minutes and athlete limit | The first block does not automatically progress load. |
| Hard minutes cap | no more than the lower of recent maximum usable-week minutes and athlete limit | Preserves an observed upper boundary. |
| Session cap | no more than the lower of recent completed maximum and stated session limit | Avoids inventing a longer session. |
| Quality exposure | at most 1 per seven-day unit | Keeps the first slice conservative and auditable. |
| Low-intensity share | at least 75% of planned running minutes | A conservative organization guardrail, not a universal optimum. |
| Quality spacing | at least 1 intervening easy, rest, or non-running day | Prevents stacking and catch-up. |
| Ascent and descent | no weekly value above its recent median and no session above its corresponding recent maximum in the first block | Creates no automatic vertical progression. |
| Technical terrain | only an accessible category observed recently | An unavailable category produces a limited module, not a road substitution. |
| Downhill practice | controlled exposure inside recent descent history; no maximal or high-speed descent repeats | Preserves the mechanical-risk boundary. |
| Taper | unavailable in the first slice | Requires a separate generator-ready decision before the event-near window. |

The generator may allocate easy running, one controlled uphill or rolling-trail
quality session, one longest easy trail session within observed duration and
vertical caps, and optional already-practiced strength or fueling modules. It
may not prescribe a new terrain category, new exercise, exact fueling amount,
maximal test, or unobserved downhill dose. Target-time gap never raises load.

### Typed readiness results

Success is eligible_rolling_proposal. Other outcomes preserve the goal and
identify the next action:

- course_clarification_required;
- material_course_demand_unknown;
- insufficient_recent_history;
- insufficient_comparable_trail_history;
- insufficient_terrain_access;
- adult_scope_or_constraints_unconfirmed;
- current_symptom_stop;
- event_inside_unapproved_taper_window;
- unsupported_ultra_or_multiday;
- contradictory_input;
- no_schedule_within_envelope;
- policy_inactive;
- validation_failed.

There is no success-shaped fallback, road policy, automatic test, or invented
course value.

### Proposal, adoption, and Garmin delivery

- Readiness and generation never create canonical workouts.
- The proposal shows versions, knowns, unknowns, assumptions, module limits,
  and why each session fits current history and course demand.
- Editing or regeneration creates an immutable successor proposal.
- Adoption requires the exact proposal version, current source revision, and
  athlete action; it atomically creates canonical workouts.
- Provider delivery is a separate preview and consent step after adoption.
- Garmin account availability, integration capability, and per-workout
  compatibility are distinct. Unsupported workouts become non-retryable
  blocked_unsupported; canonical structure is never flattened or discarded.
- trail_running is never silently changed to running. Garmin mapping requires
  upload, template readback, calendar, device, and activity-return verification
  for the relevant region and device profile.

## Scenarios

- **Complete Ninghai input:** show a 14-day proposal, explain no-progression
  caps, allow bounded edits/regeneration, and require exact adoption.
- **Course details missing:** ask only for material fields. If unresolved,
  return a typed no-plan or limited module; never select a road plan.
- **Terrain access insufficient:** identify the unsupported demand class and
  preserve the goal without pretending flat running is equivalent.
- **Sparse or stale history:** explain the missing condition without inferring
  detraining, scheduling a maximal test, or using a beginner policy.
- **Garmin incompatibility:** keep the canonical Praxys plan and point to each
  blocking workout or field; offer no lossy send.

## Value hypothesis

If the owner can see which course demands and recent exposures drive a bounded
proposal, they can begin useful race-specific organization while retaining
enough trust to edit, reject, or withhold delivery. This is falsified if
material unknowns are guessed, major edits are routine, or the owner bypasses
the governed flow to create the plan manually.

## Non-goals

- A complete 75-day schedule adopted at once.
- Ultra, multi-day, first-completion, sparse-history, return-to-run, clinical,
  rehabilitation, pediatric, or pregnancy-specific planning.
- Personal finish probability, target guarantee, injury-prevention claim, or
  medical clearance.
- Universal vertical, downhill, hiking, strength, taper, fueling, HR, pace,
  power, or RPE prescriptions.
- Automatic adoption, provider delivery, invitation, promotion, or broad
  availability.
- Treating owner-only process observations as evidence of efficacy.

## Outcome and guardrail measures

Target signals:

- the owner completes material clarification without hidden defaults;
- identical normalized inputs replay identically;
- a Web proposal can be reviewed, edited or regenerated, and adopted;
- generated duration and vertical exposure stay inside accepted caps;
- proposal, adopted plan, and provider-delivery state are distinguishable.

Guardrails:

- zero road fallbacks, silent discipline downgrades, cross-owner reads,
  stale-version adoptions, pre-adoption calendar writes, or replay mismatches;
- zero plans for material unknowns, symptom stops, unsupported populations, or
  the unapproved taper window;
- pause on one plausibly related serious adverse report;
- revisit guardrails when more than 30% of proposed sessions need material
  edits. Process thresholds do not establish efficacy or personal safety.

## Human Product decision requested

Approve, revise, or reject this bounded recommendation:

> Offer the accepted non-ultra Trail policy first to the authenticated owner,
> using a 14-day, seven-day-reviewed, no-initial-load-escalation generator that
> requires complete course demand and recent comparable exposure. Preserve
> typed no-plan outcomes, exact athlete adoption, separate provider consent,
> and no invitations or broad visibility. Treat every exact value above as a
> reversible Product guardrail, not published science. This approval does not
> accept the Science records, implementation, runtime activation, Garmin
> mapping, or deployment.
