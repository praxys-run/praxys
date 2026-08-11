# Pre-plan baseline policy decision brief

**Status:** Accepted science policy; approved by `@dddtc2005` on 2026-08-10.
Issue #654 implements the first bounded API, persistence, web, and miniapp flow for
`performance_5k` goals while broader validation, precision, and expansion work
remain pending.

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

For that goal, the accepted policy is:

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
   remaining supporting when change comparability is incomplete without a
   known material mismatch, or incomparable when a mismatch is material;
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

| Candidate | Directness to the selected goal | Main limitation | Accepted policy |
| --- | --- | --- | --- |
| Verified measured 5 km road race in athlete history | Directly observes current 5 km capability | A different race/course may not be comparable for change | Direct for current capability; supporting only when comparability is incomplete without a known material mismatch, and incomparable when mismatch is material |
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
rule. The accepted policy uses **42 completed calendar days** as a pragmatic
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
environmental time correction. A protocol or material-condition mismatch may leave the result direct for
current capability while making it incomparable for change. Supporting
classification is reserved for incomplete change-comparability evidence when
no material mismatch is known.

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

## Current implementation notes

The first shipped implementation keeps the scope deliberately narrow:

- A dedicated `performance_5k` goal kind activates the history-first baseline
  flow. Existing race and continuous goals remain outside this pilot and return
  `not_required`.
- Candidate retrieval remains **full-activity only** and surfaces recent
  near-5 km complete running activities for athlete review. Retrieval never
  qualifies evidence by itself.
- The current implementation uses a conservative **±0.25 km** near-5 km
  review window for full-activity candidates. This is an implementation
  heuristic for review, not a reviewed equivalence rule, and remains pending
  prospective validation.
- The UI states that the pilot is only for adults who already can complete
  5 km. The repository does not yet store a dedicated profile field to enforce
  that population boundary automatically at account level.
- Qualification requires explicit athlete confirmation of measured distance,
  elapsed timing without unresolved pauses, and either measured-race provenance
  or intentional all-out effort.
- Optional-test writes are explicit and auditable: offer, schedule, decline,
  stop, and complete/invalidated actions persist versioned records and any
  schedule uses the canonical workout/revision/delivery lane.
- Export, account deletion, and aggregate-only admin evaluation include the
  goal-baseline confirmation, snapshot, assessment, and optional-test records.

The implementation does **not** add a meaningful-change threshold, cross-route
comparability correction, personal success probability, or any automatic intent
classification from pace, power, ranking, or fast segments.

## Accepted bounded decisions

GitHub maintainer `@dddtc2005` accepted the Evidence Review and SDR on
2026-08-10 through five separate bounded decisions:

1. Adults aged 18 years or older who are recreational road runners already able
   to complete 5 km, with standardized outdoor road 5 km elapsed-time
   performance goals, are the initial scope. The policy is history-first;
   testing is not mandatory.
2. Qualified measured 5 km races or athlete-confirmed intentional all-out 5 km
   efforts establish current capability. Only sufficiently comparable
   same-protocol results measure longitudinal change. Random workout segments
   never qualify. Other tests and device estimates are supporting or
   incomparable, not equivalent.
3. A standardized outdoor 5 km time trial is optional only when qualified
   history is missing, stale, or incomparable. It is maximal-effort,
   safety-screened, opt-in, and never required.
4. Qualified evidence is current through 42 completed days and stale from day
   43. This is a versioned Praxys pilot guardrail, not a published biological
   cutoff. Stale evidence is retained and does not block use.
5. Material route, protocol, environment, or recovery mismatch is
   incomparable. Illness, injury, red flags, inadequate recovery, or unsafe
   conditions stop testing. Collection is minimal-data and opt-in. Declining
   or stopping yields insufficient evidence rather than blocked use.
   Expansion requires pre-registered validation and a new reviewed policy.

The lifecycle reviewer approved these policy boundaries; the reviewer did not
independently reproduce the searches, duplicate extraction, or obtain full
text beyond the verification levels recorded in the Evidence Review. The
method limits and unresolved evidence gaps therefore remain in force.

Acceptance does not define or ship application behavior. A separate
implementation issue and reviewed PR must define the final history-search
candidate unit, qualification metadata, athlete-confirmation wording and
ambiguous-response handling, protocol script, data contract, pilot opt-in,
retention/access/export/deletion rules, ingestion, telemetry and aggregate
analytics, English/Chinese localization, pilot operations, API/client parity,
and tests under this accepted policy.

## Future impact map

```text
Evidence Review -> SDR -> history-first goal baseline policy
-> persistence/retention/access/export/deletion -> ingestion -> pure analysis
-> API contract -> web Goal/Plan/Insights + EN/zh localization
-> miniapp parity -> plugin/MCP proposal parity -> private telemetry/analytics
-> ScienceNote -> tests
-> prospective repeatability, subgroup, safety, and drift evaluation
```

No analysis, API, web, miniapp, or plugin behavior changes in PR #641.
