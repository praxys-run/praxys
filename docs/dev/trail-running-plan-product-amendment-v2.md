# Trail-running managed-plan Product amendment v2

**Status:** proposed logical-contract successor/addendum; human Product review
required; runtime inactive.

**Authority boundary:** this amendment may authorize only a future inactive
implementation after human acceptance. It does not authorize a pilot,
owner-only exposure, production-data use, provider integration or delivery,
deployment, capability activation, catalog visibility, or wider rollout.

**Digest:** pending deterministic generation after the review text is frozen;
no digest is assigned or implied by this draft.

## Human decision sheet

The human Product reviewer should record **approve**, **revise**, or **reject**
for each choice. Approval of one row does not imply approval of another.

| # | Choice | Recommended Product decision |
| --- | --- | --- |
| 1 | Stable readiness result | Adopt the five canonical statuses, exhaustive namespaced reason catalog, deterministic precedence, complete matching-reason receipt, and separate `limited_modules`. |
| 2 | Versioned input contract | Adopt `trail_course_demand_v2` and `non_ultra_trail_constraints_v2`, strict known/unknown request values, server-stamped provenance, and revision-bound confirmation. |
| 3 | Course description | Adopt integer grade-share buckets, the six-value footing vocabulary, explicit hazard gates, and bounded environment, support, fueling, and gastrointestinal context without routes or free-text planning inputs. |
| 4 | Access and history | Require explicit training weekdays and terrain access while keeping the 42/21-day recent-history assessment server-derived. Treat planning duration as an athlete-confirmed range, not a prediction. |
| 5 | Block versus limit | Keep core readiness gates fail-closed, but allow ordinary grade, footing, environment, support, and fueling unknowns to limit only their named modules when all core gates pass. |
| 6 | Data and runtime boundary | Preserve reset, export, and deletion for the current goal; collect no value telemetry; forbid diagnosis, activity `avg_power`, road fallback, route/provider payloads, and any authority beyond inactive implementation. |

## Work Contract and shared decision fields

- **Classification:**
  `sha256:d0a83117e8cd681435229fb7fb2c8ddddf4ac8ad8acaba24590079ba1e200607`
- **Route:**
  `sha256:6a022077cd4d910007c63241ee7c4b98773cd587c92450c6acecc778943fe168`
- **ID:** `pdr-owner-non-ultra-trail-plan-v2-amendment`
- **Schema version:** logical-contract; the repository does not yet define a
  persisted Product Decision Record schema.
- **Decision type:** Product Decision Record successor/addendum.
- **Owner role:** Product.
- **Question:** Should Praxys replace the ambiguous v1 Trail readiness input
  and outcome surface with a strict v2 contract that remains useful when
  non-core context is unknown, without weakening course, history, access,
  hazard, data-rights, or runtime boundaries?
- **Options:** adopt v2 as proposed; retain v1 and patch individual failures;
  require every descriptive field before any proposal; or infer missing
  values and fall back to an existing plan family.
- **Recommendation:** adopt the bounded v2 behavior in this amendment for
  future inactive implementation only.
- **Rationale:** users need one stable verdict, every applicable reason, and a
  clear distinction between “no proposal” and “one module is limited.” Strict
  typed values and explicit confirmation prevent hidden defaults while still
  allowing a useful proposal when only non-core descriptive context is
  unknown.
- **Dependencies:** the accepted v1 Trail Evidence Reviews and inactive Science
  Decision Records; an independently accepted Science successor for any v2
  applicability or safety change; Design review of the resulting journey;
  Architecture review of canonical serialization and revision fences; Trust
  review of minimization, authorization, export, reset, and deletion; Quality
  verification of the exact implementation.
- **Review route:** human-review-required. Product neither approves this
  proposal nor selects a different route.
- **Outcome plan:** verify the inactive contract deterministically, then use
  only explicit owner-supplied dogfood feedback after a separately authorized
  activation. This amendment adds no value telemetry.
- **Digest:** generated later from the frozen artifact; deliberately absent
  from this proposal.

This document is an additive successor to
`trail-running-plan-product-proposal.md`. Where the two conflict, this v2
proposal describes the requested future behavior, but it has no authority
until human review accepts its exact frozen content.

## User problem, observed signal, and assumptions

### Observed signal

The authenticated owner is preparing for the Ninghai Trail Challenge on
2026-11-15 (24.7 km and 618 m stated ascent), wants the complete experience in
the Praxys UI, and prefers to improve it through their own dogfood use. The
owner found the Product and Experience documents easier to review than the
machine-oriented Science packets. That is a usability signal for the review
contract, not evidence that the proposed training policy is effective.

The current inactive implementation exposes v1 inputs and collapses many
different facts into a single result/detail pair. It can therefore hide
simultaneous next actions and can make a non-core missing value look equivalent
to a core readiness stop.

No broader demand, adoption rate, safety outcome, or efficacy signal is
claimed. No product-value telemetry exists for this proposed behavior.

### Assumptions to test later

- An owner can provide the bounded event and access fields without uploading a
  route, linking a course URL, or understanding the Science registry.
- One stable status plus a complete reason receipt is easier to act on than a
  long flat outcome enumeration.
- A proposal with explicitly limited grade, technical-terrain, environment, or
  fueling modules can still be useful when every core readiness gate passes.
- A confirmed planning-duration range is sufficient planning context without
  presenting a finish-time prediction.

These are Product hypotheses. They are not scientific findings or activation
criteria.

## Product options and trade-offs

### A. Adopt the strict v2 contract — recommended

Use two versioned schemas, five statuses, a closed reason catalog, complete
reason preservation, and independent module limits. This creates more input
work for the owner but makes every default, limit, and stop inspectable.

### B. Keep v1 and patch individual outcomes — not recommended

This is the smallest code change, but it preserves an unstable response
contract and continues to conflate course clarification, readiness, policy
availability, and validation.

### C. Require every course descriptor before a proposal — not recommended

This is simple and conservative, but it blocks useful organization when grade,
ordinary footing, environment, support, or fueling context is genuinely
unknown and the corresponding module can instead be omitted honestly.

### D. Infer unknowns or fall back to a road plan — rejected

This reduces input burden by manufacturing certainty. It would erase material
Trail distinctions, contradict the accepted boundary, and undermine trust.

## Minimum valuable v2 behavior

The minimum valuable behavior is a versioned, replayable readiness receipt
that can either authorize the existing bounded proposal envelope or explain
all reasons it cannot. It does not itself create, adopt, deliver, or activate a
plan.

### Canonical status contract

Every v2 evaluation returns exactly one top-level `status`:

1. `validation_failed`
2. `policy_unavailable`
3. `readiness_blocked`
4. `clarification_required`
5. `eligible_proposal`

This list is also the deterministic precedence from highest to lowest. A
malformed or non-replayable request cannot be presented as a meaningful policy
or readiness outcome. An unavailable policy outranks athlete readiness. A
confirmed stop outranks missing clarification. `eligible_proposal` is possible
only when no reason in a higher status matches.

The response also carries:

- `detail_reason`: the first matching reason inside the selected status,
  following the fixed catalog order below;
- `matching_reasons`: every matching `(status, detail_reason)` pair across all
  statuses, de-duplicated and ordered first by status precedence and then by
  catalog order; and
- `limited_modules`: a separate sorted set that never changes the top-level
  status or hides a matching reason.

The fully qualified, namespaced identity of a reason is
`<status>.<detail_reason>`. Clients must not construct new reason strings,
replace the full receipt with the first reason, or infer eligibility from an
empty module-limit list.

“Every matching reason” means every condition the server can safely evaluate.
A malformed value is never dereferenced merely to discover more reasons; the
receipt preserves all other independently evaluable matches.

### Exhaustive reason catalog

The following is the complete v2 Product catalog. Adding, removing, renaming,
or reclassifying a reason requires a successor Product decision and matching
specialist review.

| Status | Ordered `detail_reason` values | Product meaning |
| --- | --- | --- |
| `clarification_required` | `material_course_demand_unknown`; `assumption_confirmation_required`; `adult_scope_or_constraints_unconfirmed`; `training_constraints_missing`; `contradictory_input` | The owner can resolve or confirm required input; no proposal is returned. |
| `readiness_blocked` | `insufficient_recent_running_history`; `insufficient_comparable_trail_history`; `insufficient_descent_history`; `insufficient_terrain_access`; `current_symptom_stop`; `no_schedule_within_envelope` | Valid, confirmed input does not satisfy a current core readiness gate; no substitute plan is returned. |
| `policy_unavailable` | `policy_inactive`; `event_inside_unapproved_taper_window`; `unsupported_ultra_or_multiday`; `unsupported_population_or_intent`; `technical_features_outside_v2` | The requested use is outside the exact available policy or its current runtime state. `policy_inactive` is a detail reason here, never a sixth top-level status. |
| `validation_failed` | `invalid_field_value`; `schema_version_mismatch`; `deterministic_invariant_failed` | The request or result cannot be safely interpreted or replayed. |
| `eligible_proposal` | none | Core gates pass. Any non-core omissions are visible only through `limited_modules`. |

Authorization failures remain fail-closed before this Product result and do
not become readiness reasons. A private owner-only boundary must not be leaked
through this catalog.

### Limited modules

`limited_modules` is an unordered set serialized in deterministic sorted order.
It permits only these values:

- `grade_specificity`;
- `technical_terrain`;
- `environment_altitude`; and
- `fueling`.

Unknown grade distribution limits `grade_specificity`. Unknown ordinary
footing limits `technical_terrain`. Unknown altitude, temperature, humidity,
wind, or exposure limits `environment_altitude`. Unknown aid/support, fueling
practice, or non-diagnostic gastrointestinal experience limits `fueling`; v2
does not expose a separate aid-support training module.

A module limit means that module is omitted or remains descriptive. It never
authorizes a generic replacement, a hidden default, a dose increase, or a
claim that the missing module is unnecessary.

## Versioned request and confirmation contract

### Schema identities

- Course demand: `trail_course_demand_v2`.
- Athlete constraints: `non_ultra_trail_constraints_v2`.

Schema identity is exact. There is no “closest supported” interpretation. A v1
payload sent to a v2 boundary, an unknown field, a duplicate set member, a
wrong unit, or a mismatched schema produces
`validation_failed.schema_version_mismatch` or
`validation_failed.invalid_field_value` as applicable.

### Strict known/unknown values

Every reviewable input uses one of two shapes:

```text
{ state: known, value: <typed value> }
{ state: unknown }
```

`known` requires exactly one schema-valid value. `unknown` carries no value.
Missing state, `null`, empty string, sentinel numbers, guessed zero, `other`,
and client-provided arbitrary objects are invalid. The server response may add
provenance and revision metadata, but clients cannot submit or overwrite those
fields.

### Provenance and revision fence

The server stamps provenance from the authenticated write path. The client may
submit a value but may not label itself `course_entered`, `history_observed`,
or otherwise choose a more authoritative source. Grade distribution accepts
only server-stamped `athlete_entered` or `course_entered` provenance. It is
never inferred from a route, model, activity trace, or provider payload in v2.

Each mutation creates a new immutable course/constraint revision. Confirmation
names the exact revision being confirmed. Any value, state, or server-stamped
provenance change invalidates the previous confirmation. Readiness and a later
proposal bind the exact goal, course, constraint, history-snapshot, policy, and
generator revisions; a stale confirmation or source revision cannot be
silently rebound.

## `trail_course_demand_v2`

### Core confirmed course fields

The following are core: event identity, event date, distance, total ascent,
total descent, planning-duration range, scope, and the two hazard gates. They
must be valid, known, and bound to the confirmed course revision before
`eligible_proposal`.

Event identity is the existing server-stamped goal/event identifier. The v2
generator request does not accept a free-text event identity or source label.

Planning duration is a confirmed integer minute range with `minimum < maximum`.
It is the range the athlete wants Praxys to use for planning context. It is not
a finish-time prediction, forecast, feasibility verdict, or performance
promise.

Event format, distance family, and performance intent remain closed enums.
Unsupported ultra/multiday scope or population/intent produces the appropriate
`policy_unavailable` reason; it is not coerced into the non-ultra policy.

### Canonical grade-share buckets

Grade distribution is optional descriptive context. When known, it is exactly
five non-negative integer shares in basis points of course distance, and the
five integers must sum to `10000`:

| Bucket key | Exact grade boundary |
| --- | --- |
| `below_neg_10` | `g < -10%` |
| `neg_10_to_below_neg_3` | `-10% <= g < -3%` |
| `neg_3_to_below_pos_3` | `-3% <= g < 3%` |
| `pos_3_to_below_pos_10` | `3% <= g < 10%` |
| `pos_10_and_above` | `g >= 10%` |

These basis points describe the share of distance in each bucket; they are not
grade values. Boundary values belong only to the bucket shown above. The
distribution may carry only `athlete_entered` or `course_entered` provenance.
It is descriptive and must not be turned into a difficulty score, equivalent
road distance, finish-time adjustment, workout dose, or safety threshold.

Unknown grade is permitted only as `state: unknown` and adds
`grade_specificity` to `limited_modules`.

### Ordinary footing

Known footing is a non-empty unordered set containing only:

- `firm_smooth`;
- `loose_gravel`;
- `mud`;
- `rocks_or_roots`;
- `built_steps`; and
- `water_crossing`.

There is no `other`, difficulty score, ordering significance, or free-text
surface description. Duplicate or unknown values fail validation. Unknown
ordinary footing is allowed and limits `technical_terrain`.

When course footing is known, access and observed-history matching use exact
set containment, not similarity, synonyms, or model inference. Let `C` be the
known course-footing set, `A` accessible footing, and `H` recently observed
footing. `C` must be a subset of `A`; otherwise readiness includes
`readiness_blocked.insufficient_terrain_access`. `C` must also be a subset of
`H`; otherwise readiness includes
`readiness_blocked.insufficient_comparable_trail_history`.

### Hazard gates

`hands_assist` and `fixed_rope` are separate tri-state values: `yes`, `no`, or
`unknown`.

- `unknown` requires clarification and cannot be reduced to ordinary footing;
- `yes` is outside v2 and yields
  `policy_unavailable.technical_features_outside_v2`; and
- both must be confirmed `no` for `eligible_proposal`.

These gates are not technical-difficulty ratings and do not authorize a
diagnosis, skill assessment, or training dose.

### Bounded optional context

Optional context uses closed values only and may remain unknown:

- maximum altitude: a canonical metric integer from `-500` through `9000`
  meters;
- expected temperature band: `below_0_c`, `0_to_below_10_c`,
  `10_to_below_20_c`, `20_to_below_30_c`, or `30_c_and_above`;
- expected humidity: `low`, `moderate`, or `high`;
- wind exposure: `sheltered`, `mixed`, or `exposed`;
- sun exposure: `low`, `mixed`, or `exposed`;
- aid/support mode: `self_supported`, `organizer_aid`, or
  `organizer_aid_and_personal_crew`;
- aid interval: `none`, `below_5_km`, `5_to_below_10_km`, or
  `10_km_and_above`;
- fueling practice: `none`, `some`, or `repeated`; and
- gastrointestinal experience: `no_issue_reported` or `issue_reported`.

The gastrointestinal value is a non-diagnostic athlete report. It cannot be
presented as a condition, clearance, treatment need, or causal explanation.
These fields accept no notes, labels, URLs, units embedded in strings, or other
free text. Missing wind or exposure information limits
`environment_altitude`; it cannot be silently treated as sheltered. Missing
aid/support, fueling, or gastrointestinal context limits `fueling`; no fixed
fueling quantity follows from a known value.

## `non_ultra_trail_constraints_v2`

### Athlete-confirmed schedule and access

Core constraints are:

- explicit available weekdays as a unique set of ISO weekday integers `1..7`
  (`1` Monday, `7` Sunday);
- a strict boolean stating whether a nontechnical continuous three-minute
  uphill is accessible;
- a strict boolean stating whether controlled downhill terrain is accessible,
  with no duration estimate requested or implied;
- accessible footing as the same six-value unordered set used by the course;
- current adult/non-clinical scope and performance-intent confirmations; and
- the current symptom-stop response required by the accepted Science boundary.

Absent schedule input produces clarification. The planning-duration range is
owned by the confirmed course revision above. A complete schedule that cannot
fit the accepted envelope produces
`readiness_blocked.no_schedule_within_envelope`. A missing or false uphill or
downhill access boolean produces
`readiness_blocked.insufficient_terrain_access`; it never triggers a flat-road
replacement. If course footing is known, missing required footing from the
access set produces the same terrain-access block.

The downhill boolean intentionally has no minutes, distance, slope, speed, or
maximum-repeat field. Product does not turn “access exists” into a safe dose.

### Server-derived recent history

The client cannot submit, correct, or attest recent-history aggregates through
the planning request. The server derives the current owner-scoped aggregate
from accepted activity records and binds it to a source revision.

The v2 readiness receipt keeps the accepted 42-day comparable-history window
and 21-day recency check. It separately evaluates:

- recent running continuity;
- recent ascent exposure;
- recent descent exposure; and
- recently observed footing from the closed six-value vocabulary.

Missing recent running produces
`readiness_blocked.insufficient_recent_running_history`. Missing comparable
ascent/Trail context or known course footing not contained in observed recent
footing produces
`readiness_blocked.insufficient_comparable_trail_history`. Missing descent
exposure produces `readiness_blocked.insufficient_descent_history`.

History provenance is server-derived. It is not replaced by athlete-entered
claims, route geometry, provider summaries, or activity `avg_power`. When
intensity context is needed, the accepted Science contract continues to allow
only supported split/sample evidence; this Product amendment selects no new
intensity target.

## Core blockers versus module limits

The following are always core and cannot be converted into a module limit:

- event identity and date;
- distance, total ascent, and total descent;
- confirmed planning-duration range;
- supported population, format, distance family, and intent;
- current symptom-stop response;
- available schedule and accepted time/session envelope;
- nontechnical three-minute uphill access and controlled-downhill access;
- recent running, ascent, and descent history;
- `hands_assist` and `fixed_rope`; and
- exact schema, confirmation, source revision, and deterministic invariants.

Grade distribution and ordinary footing may be unknown and limit only
`grade_specificity` and `technical_terrain`. Environment/altitude may be
unknown and limit `environment_altitude`. Aid/support, fueling, and
gastrointestinal context may be unknown and limit `fueling`.

Known values do not automatically enable a module. Specialist Science limits,
accepted access/history matching, and deterministic validation still apply.
Product is deciding the user-value trade-off between block and limit, not a
biological dose.

## Data minimization and user control

The v2 planning contract does not collect or persist:

- GPS points, route files, polylines, maps, or inferred course geometry;
- course-source URLs or scraped course content;
- provider request/response payloads or device identifiers;
- free-text health, symptom, fueling, surface, or course narratives;
- diagnoses, medical clearance, or injury probability;
- activity `avg_power` as readiness or intensity evidence; or
- a road-equivalent distance, pace, load, or fallback plan.

The current goal must remain user-controllable in the Praxys UI:

- **Reset:** reset the current v2 course/constraint draft to explicit unknowns,
  invalidate its confirmation, and create a new revision. Reset does not
  rewrite source activities.
- **Export:** include the current goal, canonical entered values, server-stamped
  provenance, revisions, confirmations, readiness status, all matching
  reasons, limited modules, and any proposal/adoption records already covered
  by the account export contract.
- **Deletion:** remove the current goal's v2 drafts, confirmations, derived
  readiness snapshots, and proposal linkage under the accepted account/goal
  deletion contract. Failures remain visible and retryable according to Trust
  policy; Product does not define storage mechanics here.

Reset, export, and deletion are authenticated, owner-scoped actions. This
amendment does not create public sharing, course catalogs sourced from user
data, cross-user aggregates, or administrator access to planning content.

## Product promise and scenarios

### Product promise

Inside Praxys, the owner can see one stable readiness status, every applicable
reason, and every omitted module before deciding whether to review a bounded
proposal. Praxys never makes a missing value look known and never substitutes
a road plan.

Design owns how this appears in the UI and must preserve the accepted
Experience Specification's distinction between goal, readiness, proposal,
adoption, and provider delivery. This Product amendment does not dictate a
component, layout, color, or copy string.

### Representative scenarios

- **Core complete, grade unknown:** return `eligible_proposal`, include
  `grade_specificity`, and omit grade-specific behavior.
- **Core complete, footing unknown:** return `eligible_proposal`, include
  `technical_terrain`, and do not infer an easy surface.
- **Known rocky course, no rocky access:** include
  `readiness_blocked.insufficient_terrain_access`; preserve every other
  matching reason.
- **Known rocky course, access present, no recent rocky observation:** include
  `readiness_blocked.insufficient_comparable_trail_history`.
- **Hazard unknown:** return `clarification_required` with the material unknown
  and confirmation reason as applicable.
- **Fixed rope or hands-assist confirmed:** return `policy_unavailable` with
  `technical_features_outside_v2`.
- **Policy inactive and recent descent absent:** top-level status is
  `policy_unavailable`, primary detail is `policy_inactive`, and the complete
  reason receipt also preserves `insufficient_descent_history`.
- **Malformed grade total plus inactive policy:** top-level status is
  `validation_failed`; the receipt still preserves the policy reason if the
  request can be safely classified without interpreting the malformed value.
- **Course environment unknown:** permit eligibility only if core gates pass,
  include `environment_altitude`, and show no environment-specific dose.
- **Fueling or aid context unknown:** permit eligibility only if core gates
  pass, include `fueling`, and prescribe no quantity.

## Non-goals

- Changing the accepted 14-day proposal, seven-day reassessment, history, load,
  workout-template, taper, or intensity Science parameters.
- Declaring grade, footing, support, environment, or gastrointestinal values a
  safety score or performance predictor.
- Finish-time prediction, personal finish probability, diagnosis, clearance,
  rehabilitation, or treatment advice.
- Ultra, multiday, first-completion, pediatric, clinical, return-to-sport, or
  unsupported-intent planning.
- Route ingestion, route search, course scraping, provider data import, Garmin
  workout mapping, provider consent, or delivery.
- Automatic adoption, invitation, promotion, catalog exposure, owner pilot,
  deployment, activation, or production use.
- Value analytics, behavioral telemetry, experimentation, cross-user
  aggregation, or using one owner's dogfood as efficacy or safety evidence.

## Success, guardrails, and falsification

Because this amendment authorizes no runtime use or value telemetry, its
pre-activation success measures are deterministic verification and explicit
human comprehension, not adoption or retention metrics.

### Success measures

- Every valid test fixture produces one of the five statuses and only cataloged
  reason/module values.
- Reordered inputs, sets, and independent evaluator paths produce the same
  canonical status, reason order, limited-module order, and replay digest.
- Every matching reason remains available in the response while one stable
  status and primary detail provide the next action.
- Core unknowns and failed gates never yield `eligible_proposal`; non-core
  unknowns never become hidden defaults.
- The owner can reset, export, and delete the current goal through Praxys-owned
  controls in later independently verified UI work.
- A human reviewer can explain, from the readiness receipt, why the result is a
  block, clarification, unavailable policy, validation failure, or eligible
  proposal without reading a machine contract.

### Guardrail measures

The tolerated count is zero for:

- unknown-to-known coercion;
- missing or overwritten matching reasons;
- non-catalog status, detail, module, footing, or enum values;
- stale confirmation or source-revision acceptance;
- grade shares not summing to `10000` or boundary misclassification;
- athlete-provided recent-history aggregates or client-selected provenance;
- GPS, route, URL, provider-payload, diagnosis, free-text planning, or value
  telemetry collection;
- use of activity `avg_power`, road fallback, lossy Trail relabeling, automatic
  adoption, or provider delivery; and
- any visibility or activation beyond a separately authorized runtime change.

### Falsification conditions

Revise or reject this Product recommendation before activation if independent
verification shows that:

- the five-status model cannot preserve materially different next actions;
- module limits allow a session that the accepted Science contract requires to
  block;
- an ordinary unknown cannot be distinguished from a core unknown;
- strict structured inputs make the owner unable to describe the real event
  without adding sensitive free text or route data;
- reset, export, or deletion cannot remain complete and owner-scoped; or
- Architecture, Trust, Science, Design, or Quality identifies an unresolved
  constraint that this Product trade-off would override.

After a separately reviewed activation, Product may assess explicit owner
feedback through existing private feedback controls. No automatic value
telemetry is authorized by this amendment, and one owner's experience cannot
establish efficacy, safety, or general demand.

## Specialist authority and implementation handoff

- **Science** owns applicability, materiality, history and safety boundaries,
  and whether any module or generated workout remains inside accepted claims.
- **Architecture** owns canonical DTO serialization, revision and replay
  boundaries, concurrency, storage, and compatibility strategy.
- **Trust** owns data minimization, authorization, retention, reset/export/
  deletion enforcement, and sensitive-data handling.
- **Design** owns the complete Praxys UI journey, content, accessibility, and
  rendered distinction among status, reasons, and limited modules.
- **Engineering** may implement only the exact accepted inactive slice.
- **Quality** independently verifies the exact head and all status/reason,
  data-rights, privacy, and fail-closed scenarios.
- **Operations** owns any later deployment, configuration, observability, and
  rollback decision.

No specialist constraint is accepted merely because it is summarized here;
the corresponding role's reviewed artifact remains authoritative.

## Human Product decision requested

Approve, revise, or reject each of the six choices in the decision sheet. If
approved, the effect is limited to preparing a future inactive v2
implementation under the accepted specialist constraints. Acceptance does not
merge code, deploy, use production data, start dogfood, expose a catalog item,
activate a capability, or send anything to Garmin or another provider.
