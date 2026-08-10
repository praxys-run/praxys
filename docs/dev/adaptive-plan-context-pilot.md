# Suggestion-first adaptive-plan context pilot

**Policy version:** `suggestion-context-pilot-v1`
**Privacy contract:** [Adaptive plan personal-context privacy](./adaptive-plan-personal-context-privacy.md)

## Reviewed scope

The pilot accepts only:

- a confirmed missed/modified-workout explanation for
  `execution_interpretation`; or
- a confirmed temporary availability constraint for `plan_adjustment`.

Each athlete-context run requires an explicit `confirmed_opt_in` request.
Synthetic runs use one of five predefined, non-sensitive scenarios. The pilot
does not create profiles, reuse context for another purpose, change retention,
or expose delegated-agent access.

The policy returns exactly one of `clarification`, `no_change`,
`insufficient_evidence`, `safety`, or `suggestion`. It never diagnoses, treats,
infers a cause, estimates an individual success probability, or guarantees an
outcome.

## Only actionable proposal

The first policy can shorten one future, time-based, Praxys-generated workout
to one athlete-confirmed maximum available duration. It fails closed when:

- the affected dates or duration limit are missing or conflict;
- more than one workout requires a choice;
- the workout is external, manual, distance-based, or lacks duration;
- the exact context version expired, changed, or was deleted; or
- the exact workout snapshot changed after proposal creation.

A run only writes a non-canonical `PlanRevision` proposal event. Acceptance is
available only to the authenticated athlete and creates a canonical
`context_pilot_accept` revision against the exact before snapshot. The existing
`POST /api/plan/adjustments/{revision_id}/undo` path performs an exact-snapshot
reversal. Rejection and deferral never mutate the plan. Context deletion marks
a pending proposal invalid and scrubs its private references; accepted workout
facts remain while private context references are removed.

Missed or modified workouts never trigger catch-up work. The comparator is
always explicit: keep the current plan unchanged.

## Synthetic scenarios

| Scenario | Expected outcome |
| --- | --- |
| `ambiguity-clarification` | Focused workout-selection clarification |
| `missed-no-change` | Explicit no-change; catch-up remains disabled |
| `missing-evidence` | Insufficient evidence |
| `safety-boundary` | Performance optimization blocked |
| `availability-suggestion` | Non-accepting synthetic proposal preview |

Synthetic proposals cannot be accepted and never touch an athlete plan.

## Operational evaluation

The admin-only evaluation reports aggregate run, outcome, proposal-response,
reversal, completed proposal-privacy-scrub, and processing-failure counts. It
also reports bounded schema/privacy, safety, and policy-version checks.
Deletion failures remain `not_measured` because the deletion-job contract does
not retain a pilot linkage after privacy cleanup; unrelated context jobs are
never attributed to this pilot.

The report never emits user IDs, context IDs, purposes, categories, dates,
prompts, private values, free text, model output, or context-category cohorts.
Subgroup and adverse-outcome evidence are explicitly `not_measured`; deletion
and no-change outcome comparisons use `insufficient_evidence` until applicable
observations exist. These states must not be upgraded by inference.

## Falsification and expansion gates

The operational report treats any non-athlete acceptance, safety proposal,
stored private-payload schema violation, or unexpected policy version as an
observed falsification. Worse outcomes versus no-change remain unmeasured
without comparable outcome evidence.

Any new input class, action, automation, retention rule, provider behavior, or
policy version requires a new maintainer review. Scientific behavior also
requires an accepted successor science decision where applicable. This pilot
contains no silent promotion or autonomous mutation path.
