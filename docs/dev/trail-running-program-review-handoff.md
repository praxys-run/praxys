# Universal trail training: role review handoff

> **2026-09-14 successor review progress:** The new [P1 review entry and decision
> sheet](trail-running-program-review-sheet.md) contains separate new Evidence /
> SDR records, an inactive contract and concrete role drafts. Independent Science
> re-review is complete with no unresolved findings; complete 50 km prescriptions,
> required content acceptance and P1 acceptance remain incomplete.
> The specialist handoffs below retain their historical 2026-09-09 context and do
> not extend old v3 verification to the new scope.

## English authoring correction — 2026-09-20

The user requires repository documents and GitHub issue / PR content to be in
English. Chinese may be used in the session or temporary review material only.
This correction translates the six affected documents in the current PR and
prepares an English Issue #798 update. It preserves scientific values, claims,
deferrals, approval states and historical facts; it does not translate unrelated
repository content or change runtime, UI, scientific or agent policy.

The bounded correction Work Contract is `c815_english_20260920`, starting from
commit `6937a59a5364d7cc5946aeb77519efb482d38391`, with base
`53aee759fcf7cadb20bb061b40065e799edfad75`. Classification:
`sha256:893eaa8aab240dd9dbdc9048389feb9711a9bd47439b1d92ad2f82b3cc4a11ba`.
Delivery route:
`sha256:28d3b9453e5e841ecb7dc0a8ba6e454e06a330c6b2178edd69ebb3c49eaa6229`.
Engineering executes and independent Quality verifies this presentation change;
the correction introduces no decision-policy change of its own.

The [parent P1 Work Contract](trail-running-program-work-contract.json) remains
unchanged. Its Decision Review and human-content-acceptance obligations still
apply. Translated Product and Experience subjects require refreshed file hashes
and affected independent review, recorded in the [bindings](trail-running-program-review-bindings.md)
and [routing record](trail-running-program-decision-review.md). Old hashes remain
historical evidence, not current subject bindings. All Science source, generated
and approval artifacts remain unchanged. The [review entry](trail-running-program-review-sheet.md)
presents one bounded Evidence Review decision first, stages later decisions and
provides optional audit links; readers need not open every link.

## Historical specialist handoffs — 2026-09-09

**Status: draft specialist handoffs.** Engineering preserves each role's
responsibilities and uncertainty. This historical handoff added no accepted
prescription, formal Science registry artifact or approval attestation. See
[product scope](trail-running-program-scope.md) for direction and the
[eight deliverables](trail-running-program-delivery.md) for dependencies. These
handoffs require independent review against the exact successor decisions.

## Science: scope and scientific prerequisites

Science performed a read-only incremental check in this round. “Shared
dependency / scope extension” below denotes scientific dependency layers, not
P1–P8 numbering or Product's delivery priorities.

| Successor scope | Reusable evidence and existing coverage | Research and exact policy gaps | Dependency layer |
| --- | --- | --- | --- |
| Reuse of a general road-running base | de Waal 2021 and existing running evidence support the relevance of basic aerobic capacity; v3 has candidates for basic running and specialized gaps | Shared capability, history eligibility, volume and intensity boundaries; do not directly transfer an entire road plan or performance prediction | Shared dependency |
| Daily training without an event | Accepted `sdr-plan-generation-eligibility-safety-v1` can record `continuous_development` and an optional goal date; this only separates goal capture from policy | No-event applicability, rolling goals, review and outcome interpretation; do not invent a race to bypass v3's event-date requirement | Shared dependency |
| Downhill-related strength | S1/S2/S4 provide limited positive laboratory-transfer evidence; existing strength reviews support resistance training; v3's four exercises are an introduction | Eccentric / isometric purpose, exercises, initial exposure, load selection, progression and feedback; distinguish damage markers, strength recovery and actual downhill performance without equivalence or injury-prevention claims | Shared dependency |
| No gym | Currier 2026 supports several resistance forms, including home / band training, without proving arbitrary bodyweight combinations equivalent | Separate venue and capability; define equipment alternatives, exercises, adjustable load and missingness. v3 still requires `gym_strength` | Shared dependency |
| Stairs / treadmill | S3 supports eccentric stimulus and repeated-exposure response from stepping down; S1 supports distinct descent demands; v3 only has a 0 / 2% positive-incline candidate | Study steps, actual descent and negative treadmill separately; actual equipment capability, exposure and fallback rules. Specialized apparatus cannot directly supply ordinary-stair dose or equivalent descent metres | Shared dependency |
| Two sessions on one day | Blagrove 2018 and others support concurrent running / strength scheduling without a universal safe gap; v3's one-session limit is an interface / product constraint | Pairing, order, spacing, timezone / date, cross-session fatigue and total time; constrain aerobic and mechanical exposure separately without equivalent-minute offsets | Shared dependency |
| First finish | The accepted adult-population SDR distinguishes first finish from a performance goal with sufficient history; exact finish-oriented schedules remain `not_accepted` | Separate new runners, first trail races and first target distances; baseline admission, run / walk, long-duration training and exit criteria, rather than merely shrinking a performance plan | Scope extension |
| 50 km | Multidimensional event-demand evidence is reusable; the existing Trail distance field ends at 49,999 metres | New distance / duration scope and long-duration, fueling, environment and fatigue policy. 50 km is not a physiological cliff, but exceeds the existing contract; specific research was incomplete in this round | Scope extension |
| Continued progression | The accepted adaptive SDR supports observation, feedback and review semantics without accepting exact progression / dose; v3's first block does not increase load automatically | Progression variables, triggers, conflicting signals, restart, cross-module totals and stopping. Fixed percentages or ACWR ranges are not proof of safety | Scope extension |
| Run / walk or hiking, fueling and taper | Existing evidence supports considering expected duration and tolerance for fueling; broad endurance taper evidence supports the direction; v2/v3 exact doses are unaccepted | Separate policies for switching, fueling amount / practice, taper onset and load types; do not directly import ratios, frequency or percentages from other populations | Scope extension |

One deliverable may produce several independent SDR decisions; different
populations and doses need not be bundled into one approval. Future Evidence
Reviews separately verify baseline capability, laboratory descent transfer and
actual trail outcomes. New SDRs define applicability, inputs, candidate-value
classification, combinations, unknown handling and falsification conditions.
Where research supplies no unique dose, a reasoned Praxys guardrail may be
proposed but must not be presented as a published value.

### Targeted source checks and search record for this round

| Source | Access actually used | Bounded conclusion supported |
| --- | --- | --- |
| S1 Bontemps et al., 2020, DOI [10.1007/s40279-020-01355-z](https://doi.org/10.1007/s40279-020-01355-z), PMID 33037592, [PMC7674385](https://pmc.ncbi.nlm.nih.gov/articles/PMC7674385/) | Relevant full-text sections on search methods, preconditioning, adaptation and conclusions | Descent exposure and some eccentric preconditioning can reduce some later responses; heterogeneous studies do not establish a universal prescription |
| S2 Eston et al., 1996, DOI [10.1080/02640419608727714](https://doi.org/10.1080/02640419608727714), PMID 8887208 | Original abstract / metadata plus the secondary review in S1 | Small trial in 10 men: isokinetic knee-extensor eccentric preconditioning reduced some later treadmill-downhill strength loss, soreness and CK. It does not validate ordinary squats or outdoor trail performance |
| S3 Paschalis et al., 2013, DOI [10.1371/journal.pone.0056218](https://doi.org/10.1371/journal.pone.0056218), PMID 23437093, [PMC3578864](https://pmc.ncbi.nlm.nih.gov/articles/PMC3578864/) | Relevant full-text methods, results and discussion | Descending on specialized bidirectional step apparatus can produce substantial mechanical / muscle-damage responses despite low heart rate, reduced after repeat exposure. Actual trail performance was not validated |
| S4 Lima et al., 2018, DOI [10.1016/j.humov.2018.05.002](https://doi.org/10.1016/j.humov.2018.05.002), PMID 29751254 | Original abstract / metadata | **Isometric leg-press** preconditioning improved some soreness and strength recovery, not running economy; this was not an eccentric trial |

On 2026-09-09 Science read Europe PMC index records and public PMC full text using
isolated, unauthenticated Chrome DevTools MCP. No formal research record or
parameter was added. The exact query endpoint was
`https://www.ebi.ac.uk/europepmc/webservices/rest/search`, with public parameters
`format=json&resultType=core`:

```text
Q1 TITLE_ABS:("downhill running") AND TITLE_ABS:(eccentric OR strength) AND TITLE_ABS:(preconditioning OR prophylactic OR prior OR protection)
   36 hits; first 25 returned. Output was partly truncated; targeted source checking only, not exhaustive screening.
Q2 TITLE_ABS:("stair descending") AND TITLE_ABS:(training OR muscle OR strength)
   27 hits; initially 25 returned, then pageSize=100 retrieved title metadata for all 27.
Q3 TITLE:("downhill running") AND TITLE_ABS:(review)
   4 hits; abstract metadata returned for all 4.
Q4 EXT_ID:23437093 OR EXT_ID:27501719 OR EXT_ID:29751254
   3 hits; abstract metadata returned for all 3.
Q5 DOI:10.1080/02640419608727714
   1 hit; Eston's original abstract metadata checked.
```

Earlier sources retain their verification levels in the [v3 Evidence
Review](../../data/science/evidence/trail-training-resource-adaptation/evidence-trail-training-resource-adaptation-v1.yaml);
those searches were not rerun. The de Waal 2021 Europe PMC abstract check
(DOI [10.1123/ijspp.2020-0812](https://doi.org/10.1123/ijspp.2020-0812)) came from
an independent parent-coordinator handoff; all 7 hits were retrieved. It was not
one of Science's Q1–Q5 above and is not claimed as new full-text verification or
a registered Evidence Review.

Science requires preserving accepted v2 and draft / inactive v3 originals and
digests. New scope requires separate successor evidence and decisions; old
`non_ultra` acceptance cannot confer authority. Source checks, parameter review,
implementation verification and runtime activation are separate steps.
**Completing this scope handoff still does not meet P1's closure criteria.**

## Design: experience decision and specification draft

Owner: Design. Retain course review and the Field Lab visual system; this round
contains no UI implementation or rendered evidence.

- Distinguish daily / race entry and first-finish / performance race intent.
  Without a race, invent no date; 50 km support remains subject to Science rules.
- Three presets only help fill the form; gym is optional. Independently confirm
  resources, equipment, familiarity, experience and dates. Show confirmed,
  tentative, unavailable and unknown separately; do not derive dates from a
  monthly frequency description.
- Before generation show supported modules / gaps; afterward show actual inclusion
  or omissions and reasons; after adoption show scheduling. Module purpose does
  not mean acquired ability or a false “race preparation complete” state.
- Preserve setup, support, generation, review / edit, explicit adoption, feedback
  and review. Race mode shows stages / next priorities; daily mode shows rolling
  training. Each session explains actual type, purpose, steps, equipment and
  accepted dose / rest.
- Use the standard zh localization for “treadmill” consistently; keep incline
  percentages separate from machine levels. Do not default to at least 10% or
  convert without evidence. Same-day running / strength use two cards and
  independent completion; remove the four-day interface limit inferred from one
  session per day.
- Resource changes require revalidating old proposals. Flag affected adopted
  sessions; replace future uncompleted work only after explicit successor adoption.
  Preserve completed work, explain capacity limitations individually and add no
  automatic catch-up.
- Cover missing history / equipment, capacity or module limits, unavailable
  rollout, unknown versions and save failures. Offline edits remain unsaved in
  memory; reconnect compares server versions and resolves conflicts without
  falsely reporting successful save or adoption.
- Retain warm paper, green actions, cobalt explanations, data typography and
  ScienceNote without new visual primitives. Future P7 uses UI Quality /
  Impeccable to verify EN/zh, desktop / mobile, themes, long content, keyboard,
  screen reader, touch and offline conflicts.
- Web launches first; miniapp supports compatible reading and explicit Web-editing
  guidance without losing dual sessions. Gate-off preserves reading and rights.

## Architecture: contract and atomic-delivery draft

Owner: Architecture. These are future implementation dependencies; no production
schema or migration version has been allocated.

- Goals explicitly distinguish race / daily. Daily uses rolling windows, training
  goals and time-limited resources, without inventing an event or extending
  conditions indefinitely.
- Each session has a stable independent identity; date only schedules it. Separate
  actual type, multiple purpose tags, order and independent completion. New
  strength / treadmill structures preserve WorkoutV1 interpretation and old-plan
  reads.
- Sum time; manage running volume, vertical exposure, strength and recovery
  separately, without unsupported minute or descent-metre conversions.
- Proposals bind goal, conditions, history, Science and workout versions; adoption
  rechecks them. Resource changes invalidate drafts, while adopted work changes
  through successors.
- P2 ships identity, new-structure read / write, adoption, completion, modification,
  snapshots, revisions, export and necessary client compatibility together. P3
  ships provenance, confirmation versions, authorization, withdrawal, export and
  deletion together. These integrity obligations cannot wait until P8.
- P4/P5 are pure planning without runtime entry points. P6 unifies 14/7
  orchestration and adoption transactions; P7 completes Web; P8 owns release
  preparation.

## Trust: data, authorization and availability draft

Owner: Trust. Authorization to create tracking material and a draft PR does not
mean acceptance of new Science, personal-data collection or activation.

- Every object derives its owner from the authenticated session; each user accesses
  only their own data. Clients cannot assert provenance, observed facts or version
  authority. Strictly bounded inputs distinguish sparse records, reports,
  confirmed absence and actual zero; reports do not become observations.
- Gym fields are optional. 50 km includes 50,000 metres; the old 49,999 m cap cannot
  claim support. Daily-resource validity, reconfirmation, full-cycle batch limits
  and snapshot retention rules must be frozen in their corresponding contract
  reviews.
- Same-day sessions have independent IDs, order and versions. Preserve completed
  sessions; future sessions change only through explicit adoption.
- Rights cover each session, current conditions, goals, proposals, PlanRevision,
  audits and caches. Unknown schemas are not executed but retain raw read,
  export and delete. Reset is not deletion; gate-off does not remove rights.
- Reuse server-side Statsig with existing identity only, adding no training, race,
  resource or health attributes or value telemetry. No SDK, configuration, data
  collection or production-state change in this round.
- Zero provider access / delivery. Adoption and later scheduling must not reach
  credential, connection, adapter, send, replacement, retry or reconciliation paths.

Independent Quality must check actors, unknown versions, version conflicts,
duplicate adoption, rights cascades and zero provider calls against the later
exact implementation. Engineering's development checks do not replace that
verification. Deployment and runtime configuration route separately to Operations
in P8.
