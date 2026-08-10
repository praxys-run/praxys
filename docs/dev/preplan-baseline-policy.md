# Pre-plan baseline policy decision brief

**Status:** Draft decision proposal for #640; not implemented

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

1. direct evidence is a valid result from the exact named 5 km time-trial
   protocol;
2. no different observation is approved as equivalent;
3. a dated measured 5 km road-race result is the strongest supporting
   observation, with its date shown but no automatic "recent" label;
4. shorter tests, critical-speed outputs, and device estimates remain
   supporting or incomparable; and
5. when direct evidence is missing or stale, offer one optional standardized
   outdoor 5 km time-trial pilot.

The selected test requires one field effort rather than a multi-trial model,
but its practical burden and acceptability are unvalidated. It is a maximal
effort, not a low-exertion test.

## Candidate matrix

| Candidate | Directness to the selected goal | Main limitation | Proposal |
| --- | --- | --- | --- |
| Exact same-protocol outdoor 5 km time trial | Measures the named criterion | Target-population repeatability and sensitivity remain unestablished | Pilot as direct evidence for this performance goal only |
| Measured 5 km road race | Same distance and output | Competition, course, timing, pacing, and environment differ | Strongest supporting evidence; not automatically equivalent |
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
- `incomparable`: an observation exists but protocol or material conditions do
  not match;
- `missing`: no usable observation exists;
- `pending_test`: an eligible optional test was proposed but not completed; and
- `not_required`: only a separately accepted goal policy says a measured
  baseline is unnecessary.

The 42-day transition applies only to direct same-protocol evidence. Supporting
race or surrogate observations show their date and age without an automatic
freshness label.

A recent result is not automatically comparable. The pilot records the exact
protocol, route version and direction, surface, elevation, elapsed timing and
pause behavior, footwear category, environment, warm-up and assistance,
performance intent, prior hard exercise, recovery, and deviations. It does not
apply an environmental time correction. A protocol mismatch, interruption,
non-maximal attempt, inadequate recovery, or unsafe condition invalidates or
downgrades the observation as specified in the SDR.

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

Declining or stopping testing is valid. Preserve the observed baseline status,
return `insufficient_evidence`, and offer a deferred time criterion or an
approved completion/consistency alternative. Never block the account, coerce a
retest, or show a personal success probability.

## Decisions requested from maintainers

1. Approve or reject the initial population and single 5 km outdoor
   elapsed-time performance-goal scope.
2. Approve or reject the evidence hierarchy: exact protocol is direct, no
   equivalent is approved, and a measured 5 km race is supporting.
3. Approve or reject the optional outdoor 5 km time trial as the one pilot
   candidate, explicitly acknowledging its maximal-effort burden and evidence
   gaps.
4. Approve or replace the 42-day Praxys freshness guardrail; do not relabel it
   as a published cutoff.
5. Approve or revise the comparability, stop, privacy, and no-test boundaries
   and the requirement for pre-registered precision criteria before any
   equivalence or meaningful-change decision.

Approval of this brief would approve a science-policy direction only. A
separate implementation decision must define the final protocol script, data
contract, explicit pilot opt-in, retention/access/export/deletion rules,
ingestion, telemetry and aggregate analytics, English/Chinese localization,
pilot operations, API/client parity, and tests.

## Future impact map

```text
Evidence Review -> SDR -> goal baseline policy
-> persistence/retention/access/export/deletion -> ingestion -> pure analysis
-> API contract -> web Goal/Plan/Insights + EN/zh localization
-> miniapp parity -> plugin/MCP proposal parity -> private telemetry/analytics
-> ScienceNote -> tests
-> prospective repeatability, subgroup, safety, and drift evaluation
```

No analysis, API, web, miniapp, or plugin behavior changes in #640.
