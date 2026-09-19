# Trail v3 Architecture decision

**Status: draft Architecture Decision Record; owner: Architecture.**
ID: `adr-trail-review-context-candidate-v3`.
Scope is the [exact Work Contract](trail-running-plan-v3-exact-work-contract.json):
a review package and independent offline candidate validator. No production
`WorkoutV1` extension, v2 loader change, service, persistence or runtime wiring.

## Compiler and pure validation boundary

`analysis/trail_training_context.py` explicitly compiles both new contracts using
`load_policy_contract(require_active=False)`. The canonical loader rebuilds the
contract from the current SDR/evidence and rejects staleness. The v3 compiler
also requires exact schema, IDs, versions, models, source/contract digests,
complete parameter sets and draft/inactive lifecycle. Missing fields and
unreviewed lifecycle changes fail closed. Importing the module compiles nothing.

The SDR `model_parameters` remain the only candidate-value source. Pinned
digests identify that source; a separate policy JSON or duplicate clinical
constant table in Python is not introduced. Compiled parameter maps are deeply
immutable. Compilation is the filesystem boundary; validation is pure, with
injected `TrustedCalendar` and no wall clock, DB, network, Statsig, provider,
history loader or generator.

The entry points are `compile_review_contract`, `validate_training_context`,
`resolve_resource_availability`, `validate_workout_candidate` and the bounded
collection check `validate_workout_candidates`. They return typed context or
review receipts, never runtime eligibility, a plan or adoption authority.
`review_valid` means only that the named local checks passed. Every receipt
states that history/course, complete scheduling/exposure budgets and adoption
were not evaluated. Existing v2 contracts and execution remain isolated.

## Resource context structure

Top-level exact keys are `schema_version`, `preset`, `resources`,
`gym_familiarity`, `equipment`, `treadmill_incline_capability`.
Each resource appears at most once (maximum eight rules), with exact fields:

```json
{"kind":"flat_running","effective_from":"2026-09-08","effective_until":"2026-11-15","weekly_pattern":[{"weekday":1,"availability":{"state":"known","value":"confirmed"}}],"date_overrides":[]}
```

The abbreviated example must contain all seven weekly entries to validate.
Weekdays are sorted, unique ISO 1–7 (Monday–Sunday). `availability` is exactly
`{"state":"known","value":"confirmed|tentative|unavailable"}` or
`{"state":"unknown"}`. Each rule permits at most 14 sorted unique dated
overrides within its validity. Overrides replace the whole weekly availability,
including unknown. Only confirmed can satisfy a workout dependency; missing
resource or a date outside rule validity resolves to unknown.

New/edit validity starts on or after trusted today and ends at most 365 days
after today, inclusive, never after a known event date. Thus the 68-day interval
from September 8 to November 15 is valid. Store rules through the event, expand
at most 56 days per review call and 14 days per proposal call. Those expansion
limits are not storage horizons. An expired stored record is still raw-readable,
exportable and deletable by a future rights path; it must not be fed through
new/edit validation merely to read it.

Gym familiarity is known `not_practiced`/`practiced_before` or unknown. Equipment
is a known sorted unique closed set of at most eight items or unknown. Incline
capability is a known min/max pair or unknown; -30 to 40%, ordered, at most two
decimals is a structural device-description range, not a training prescription.
The updated **new** ontology carries these exact structural rules, numeric abuse
limits, and the closed activity/resource mapping below. Scientific doses did
not change during this alignment.

## Candidate wire and capability boundaries

| Module | Allowed resource | Actual activity | Goal activity |
| --- | --- | --- | --- |
| basic_running | flat_running, treadmill supporting level running | running | trail_running |
| gym_strength | gym_strength | strength | trail_running |
| treadmill_intro | treadmill with compatible known incline range | running | trail_running |
| observed_outdoor_trail | nontechnical_uphill, controlled_downhill, technical_terrain | trail_running | trail_running |

The mapping is explicit in the candidate fields and SDR; stairs or technical
resources cannot pass as basic running to bypass outdoor checks. Basic and
outdoor candidates have the named easy template, duration and empty structured
step/exercise lists. Their personal running and outdoor caps are **not checked
by this slice**. The outdoor form cannot become an executable prescription
until observed descent, footing, dose storage and budget checks exist.

Gym candidates bind exact familiarity-specific exercises, sets/reps/rest,
load-choice rule and reserved duration. Their template also carries the warmup
and form cues. Treadmill candidates bind every exact step and total from the SDR
and a confirmed resource on the date. Level treadmill is a distinct basic
template; positive incline requires the dedicated template. Collections check
one workout/day and prohibit simultaneous new gym introduction and positive
incline in the block. They do not claim complete scheduler validation.

## Future implementation dependencies

Versioned stored workout support must preserve structured strength/treadmill
content and actual activity types while remaining compatible with existing
plans, exports and `PlanRevision.proposal_snapshot`. Do not flatten a run plus
gym onto one day under the current one-workout/day API. Real descent and footing
need first-party observed provenance; missing DB fields cannot become zero.

Generation must atomically bind context/course/history revisions, goal and
proposal snapshots and audit. Adoption must recheck those bindings and exact
version, write only explicitly accepted future uncompleted work, and preserve
completed training. Resource edits invalidate drafts and mark adopted impacts.
Unknown schemas remain opaque for rights and unavailable for execution.

Owner authorization, full rights coverage, gate/provider fences, UI implementation
and rendered verification, independent Quality and Operations release/rollback
evidence all remain future work. This review package is not a one-switch
activation. See the [implementation handoff](trail-running-plan-v3-implementation-handoff.md).
