# Pre-plan baseline policy decision brief

**Status:** Draft Decision proposal for #640; not implemented or science-accepted

**Canonical records:**

- [Evidence Review](../../data/science/evidence/preplan-baseline-policy/evidence-preplan-baseline-policy-v1.yaml)
- [Science Decision Record](../../data/science/decisions/sdr-preplan-baseline-policy-v1.yaml)
- [Goal-contract states](./adaptive-plan-goal-contracts.md#baseline-contract)

This brief gives maintainers a bounded decision surface. The YAML records remain
canonical for search provenance, citations, claim appraisal, parameter
classification, and falsification details.

## Recommended first scope

Start only with self-coached adult recreational road runners who can already
complete 5 km and choose a **5 km outdoor elapsed-time performance goal**. Do
not extend the first policy to race-goal equivalence, trails, treadmills, other
distances, clinical testing, injury rehabilitation, or return to sport.

For that goal, the proposal is:

1. search existing athlete history before offering a new test;
2. a verified measured 5 km race or an explicitly athlete-confirmed
   intentional all-out 5 km effort may be **direct evidence of current 5 km
   capability** when distance, elapsed timing, effort intent, date, and
   provenance are sufficient;
3. never infer race or all-out intent from pace, power, ranking, or a fast
   split; a random 5 km segment or best split inside an easy, long, or
   mixed-purpose workout is not a baseline;
4. classify **directly comparable longitudinal change** separately:
   before/after claims require the same protocol and comparable route,
   environment, recovery, timing, and assistance conditions;
5. a different race or course may directly inform current capability while
   remaining supporting or incomparable for change;
6. shorter tests, critical-speed outputs, and device estimates remain
   supporting or incomparable; and
7. only when qualified history is missing, stale, or incomparable, offer one
   optional standardized outdoor 5 km time-trial pilot by explicit opt-in.

The selected test requires one field effort rather than a multi-trial model,
but its practical burden and acceptability are unvalidated. It is a maximal
effort, not a low-exertion test or an account prerequisite.

## History qualification and athlete confirmation

Implementation must make qualification auditable rather than silently
classifying arbitrary segments:

- Search complete activities and verified race results before proposing a new
  test.
- A verified measured race needs the observed date, measured 5 km distance,
  elapsed timing without unresolved pause/timing failure, and race provenance.
- A non-race effort additionally needs an explicit athlete confirmation that
  the complete 5 km was an intentional all-out performance effort.
- An absent or ambiguous confirmation is `insufficient_evidence`; pace, power,
  ranking, or "best split" status never substitutes for confirmation.
- Splits and samples may verify distance, elapsed timing, pauses,
  interruptions, and protocol/intensity context. They may not create or infer
  performance intent. Activity `avg_power` is prohibited.
- Store current-capability status separately from longitudinal-change
  comparability so a different race/course can inform current capability
  without becoming a directly comparable before/after result.

## Candidate matrix

| Candidate | Directness to the selected goal | Main limitation | Proposal |
| --- | --- | --- | --- |
| Verified measured 5 km road race in athlete history | Directly observes current 5 km capability | A different race/course may not be comparable for change | Direct for current capability; supporting or incomparable for longitudinal change unless protocol and material conditions match |
| Explicitly confirmed intentional all-out 5 km effort in athlete history | Directly observes current 5 km capability | Requires sufficient distance/timing metadata and explicit athlete intent | Direct for current capability; change claims still require same protocol and comparable conditions |
| Exact same-protocol outdoor 5 km time trial | Measures the named criterion | Target-population repeatability and sensitivity remain unestablished | Optional fallback pilot; direct for current capability and directly comparable for change only against the same protocol under comparable conditions |
| Random 5 km segment or best split inside another workout | Does not establish a complete intentional 5 km performance | Pace cannot establish purpose; mixed-workout context and timing may mislead | Never a baseline merely because it is fast; splits/samples verify protocol only |
| Cooper 12-minute or 1.5-mile test | Related running/fitness observation | Requires surrogate-to-5 km translation | Supporting only |
| Critical speed or running 3-minute all-out | Related protocol-derived capacity | Trial and model dependent; not clearly lower burden | Supporting only |
| Device VO2max, critical power, or critical speed | Convenient model estimate | Device and algorithm dependent | Supporting or incomparable; never automatic equivalence |
| No test | Honest when declined, unsafe, or unsuitable | Feasibility remains uncertain | Valid `insufficient_evidence` path |

No candidate permits activity `avg_power`; future intensity context must use
splits or samples.

## Freshness and state handling

The literature did not validate a universal 28-, 42-, or 56-day expiration
rule. The proposal uses **42 completed calendar days** as a pragmatic
versioned Praxys pilot guardrail:

- `current`: valid direct evidence no more than 42 days old and no material
  invalidator;
- `stale`: otherwise-valid direct evidence from day 43 onward, retained as
  history;
- `incomparable`: candidate history exists, but current-capability
  qualification metadata are insufficient or conflicting;
- `missing`: no usable observation exists;
- `pending_test`: an eligible optional test was proposed but not completed; and
- `not_required`: only a separately accepted goal policy says a measured
  baseline is unnecessary.

The 42-day transition applies to qualified direct current-capability evidence,
including verified races and explicitly confirmed all-out 5 km efforts.
Supporting or surrogate observations show their date and age without an
automatic freshness label. Longitudinal-change comparability is assessed
separately from freshness.

A recent result is not automatically comparable for change. Current-capability
qualification records date, verified distance, elapsed timing, race provenance
or explicit all-out intent, and unresolved pauses or timing failures.
Longitudinal comparison additionally records the exact protocol, route version
and direction, surface, elevation, footwear category, environment, warm-up and
assistance, prior hard exercise, recovery, and deviations. It does not apply an
environmental time correction. A protocol or material-condition mismatch may
leave the result direct for current capability while downgrading it to
supporting or incomparable for change.

No universal meaningful-change percentage is proposed. The protocol remains
without a change threshold until repeat testing estimates learning, absolute
error, and sensitivity.

## Safety and no-test path

Do not start, or stop, the performance test for illness, injury or pain altering
running, red-flag symptoms, a reported medical restriction or clinician advice
against vigorous testing, inadequate recovery or unresolved substantial
fatigue, or unsafe weather, air quality, traffic, visibility, footing, or
course conditions. Red-flag symptoms and reported restrictions use a distinct
non-diagnostic urgent safety exit rather than the ordinary declined-test path.
This is a performance-test boundary, not diagnosis, treatment, clearance, or
return-to-sport advice.

Declining, stopping, or being excluded for safety is valid. Preserve the
observed `missing`, `stale`, or `incomparable` status, return
`insufficient_evidence`, and offer a deferred time criterion or an approved
completion/consistency alternative. Never block the account, coerce a retest,
or show a personal success probability.

## Decisions requested from maintainers

1. **Maintainer product feedback approved** the bounded initial population and
   5 km outdoor elapsed-time performance-goal scope. This records product
   direction only; it is not science acceptance, and both canonical records
   remain draft with no human science reviewer.
2. Approve or revise the history-first evidence hierarchy: verified race or
   explicitly confirmed intentional all-out 5 km history may be direct for
   current capability; arbitrary workout segments are never baselines; and
   directly comparable change requires the same protocol and comparable
   conditions.
3. Approve or reject the optional outdoor 5 km time trial as fallback only
   when qualified history is missing, stale, or incomparable, with explicit
   opt-in and acknowledgment of its maximal-effort burden and evidence gaps.
4. Approve or replace the 42-day Praxys freshness guardrail; do not relabel it
   as a published cutoff.
5. Approve or revise the comparability, stop, privacy, and no-test boundaries
   and the requirement for pre-registered precision criteria before any
   equivalence or meaningful-change decision.

Maintainer approval of the bounded product scope does not accept the Evidence
Review or SDR. A separate human science review and implementation decision must
define the final history-search candidate unit, qualification metadata,
athlete-confirmation wording and ambiguous-response handling, protocol script,
data contract, explicit pilot opt-in, retention/access/export/deletion rules,
ingestion, telemetry and aggregate analytics, English/Chinese localization,
pilot operations, API/client parity, and tests.

## Future impact map

```text
Evidence Review -> SDR -> history-first goal baseline policy
-> persistence/retention/access/export/deletion -> ingestion -> pure analysis
-> API contract -> web Goal/Plan/Insights + EN/zh localization
-> miniapp parity -> plugin/MCP proposal parity -> private telemetry/analytics
-> ScienceNote -> tests
-> prospective repeatability, subgroup, safety, and drift evaluation
```

No analysis, API, web, miniapp, or plugin behavior changes in #640.
