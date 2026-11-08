# Universal trail training: eight deliverables and session handoff

> **2026-09-14 successor review progress:** The new [P1 review entry and decision
> sheet](trail-running-program-review-sheet.md) contains separate new Evidence /
> SDR records, an inactive contract and concrete role drafts. Independent Science
> re-review is complete with no unresolved findings; complete 50 km prescriptions,
> required content acceptance and P1 acceptance remain incomplete.
> The text below retains the historical 2026-09-09 handoff context and does not
> extend old v3 verification to the new scope.

**Status: partial P1 progress; all downstream runtime capabilities remain
incomplete.** Owner: Engineering. This page records implementation impacts and
dependencies from Product and specialist handoffs; it is not self-acceptance or
independent verification. See the [Product handoff](trail-running-program-scope.md)
for scope and the [role review handoff](trail-running-program-review-handoff.md)
for open scientific and interface decisions.

## Tracking structure and existing work

The child Epic “Universal trail training: daily training and single-day race
preparation through 50 km” is [#797](https://github.com/praxys-run/praxys/issues/797),
under [#582](https://github.com/praxys-run/praxys/issues/582). P1–P8 map to
#798–#805 as the default eight issue / PR boundaries. One issue can produce
several independent scientific decisions. Each issue closes only when its own
acceptance criteria are met.

Read-only status check as of 2026-09-09:

- [#690](https://github.com/praxys-run/praxys/issues/690) /
  [#692](https://github.com/praxys-run/praxys/issues/692) remain open. The governed
  policy draft in [#759](https://github.com/praxys-run/praxys/pull/759) and inactive
  non-ultra core in [#776](https://github.com/praxys-run/praxys/pull/776) are merged.
  They are foundations, not a release of the new scope.
- [#691](https://github.com/praxys-run/praxys/issues/691) is linked to this 50 km
  research. Its longer-distance, 100-mile and multi-day requirements remain; the
  link or completion of this Epic does not close it.
- [#663](https://github.com/praxys-run/praxys/issues/663),
  [#662](https://github.com/praxys-run/praxys/issues/662) and
  [#664](https://github.com/praxys-run/praxys/issues/664) remain shared-lifecycle
  dependencies with their existing scopes and states.
- Road 10K in [#730](https://github.com/praxys-run/praxys/issues/730) remains
  inactive / default-hidden; #735 was the selected controlled runtime evaluation
  plan. On 2026-09-09 the user also selected Trail scope / review preparation.
  This extends the earlier planning statement that “#735 is the only active
  planning slice”. It does not complete #735, produce runtime evaluation
  findings, or change Road 10K status, runtime ordering or Trail runtime authority.

GitHub tracking established one native child Epic and eight native child issues.
Only identifiable tracking blocks were appended to #582/#730/#690/#692/#691;
their original bodies were preserved byte for byte. All new objects remained
open with designated labels and no assignees, `agent-ready`, review requests or
automatic merge. Publication checked for duplicates and read back each write;
identifiers came from actual creation results.

## P1–P8: scope, dependencies and closure conditions

| Deliverable | Scope and dependencies | Acceptance required in the same delivery |
| --- | --- | --- |
| **P1 Product and scientific rules** [#798](https://github.com/praxys-run/praxys/issues/798) | Persist this scope and successor Product / Evidence / SDR / Experience / Architecture / Trust decisions; reuse #690/#692 and link #691's 50 km research | Exact reviewable rules for daily use, first finish, 50 km, no gym, dual sessions and a complete cycle. Science supplies module-specific admission, dose, recovery, progression and feedback rationale. Close only after all required decisions undergo independent routing and acceptance with bound handoff versions |
| **P2 Multi-session calendar and workout structure** [#799](https://github.com/praxys-run/praxys/issues/799) | Depends on accepted P1 representation / architecture boundaries; align with #663/#662/#664. Same-day one running-type plus one strength session; structured exercises, sets / repetitions, load, rest, equipment and treadmill steps | Stable identities and independent completion, skipping and activity links. Ship read / write, adoption, modification, snapshots, revisions, export / delete and necessary client compatibility together. Preserve old schedules; never execute unknown new versions; zero provider delivery |
| **P3 Conditions, history and data rights** [#800](https://github.com/praxys-run/praxys/issues/800) | Depends on accepted P1 data, Science / Trust / Architecture rules; align versions with P2. Separate resources, equipment, familiarity, dates and provenance | Recurring rules and exact exceptions; daily resources have expiry. Do not confuse no device with no experience or infer actual descent / terrain from gym work. All new current values, snapshots, caches and retained copies support isolation, read, withdrawal, export and deletion |
| **P4 Joint scheduling across five modules** [#801](https://github.com/praxys-run/praxys/issues/801) | Depends on exact P1 prescriptions / budgets and P2/P3; reuse applicable basic-running logic and keep planning pure | Valid content or explicit limits for city, no mountain, no gym, beginner and familiar cases. Shared time / recovery, separate running and mechanical budgets. A zero median weekly vertical total from occasional mountain access must not reject all basic training. No guessed resources or stacked load; preserve road-running regressions |
| **P5 Daily and complete race-preparation cycles** [#802](https://github.com/praxys-run/praxys/issues/802) | Depends on P4 and accepted P1 daily / 50 km / stage rules; align with shared lifecycle and keep planning pure | Rolling 14 days, day-7 review, no invented event date, first-finish / performance branches, applicable progression, run / walk, fueling practice and taper. Include exactly 50 km and varied event demands. Goal changes and skipped sessions trigger neither automatic catch-up nor adoption |
| **P6 Generation and adoption API** [#803](https://github.com/praxys-run/praxys/issues/803) | Depends on P2–P5 and accepted Trust / Architecture; use existing plans, proposals and revisions | Authentication, exact condition / goal / history / Science / workout-structure versions, transactions and duplicate-request handling. Reject stale proposals after resource changes; replace only future uncompleted sessions. Complete rights, gate-off, unknown versions and zero provider calls; preserve AI availability and labeling semantics |
| **P7 Complete Web experience** [#804](https://github.com/praxys-run/praxys/issues/804) | Depends on P6 and accepted Experience; UI Quality / Impeccable | Complete setup → support → generation → review / edit → adoption → per-session feedback → review. Executable detail and gap semantics. Rendered EN/zh, desktop / mobile, keyboard, screen-reader, theme, long-content, offline / version-conflict acceptance. Compatible miniapp reads and Web editing guidance |
| **P8 Acceptance and gradual availability** [#805](https://github.com/praxys-run/praxys/issues/805) | Depends on P1–P7; release requires a separate Work Contract, independent review and Operations | Verify every universal-matrix case, frontend deployment / rollback evidence, Statsig rollout first to the user's account then wider based on results, and gate-off rights. Complete real Ninghai flow. Product Outcome distinguishes usability from efficacy evidence; Epic/#730 agree with production state |

Default dependency order: **P1 → P2/P3 → P4 → P5 → P6 → P7 → P8**.
P2/P3 infrastructure independent of training dose may be split into implementation
slices after its relevant acceptance boundaries are complete. This does not open
P4/P5 prescriptions or runtime entry points. Research and read-only checks may
run in parallel; code writes are serialized by the coordinator.

In this historical handoff, the draft PR contained the old v3 review foundation,
offline validator and universal-scope handoff, with no new universal training
generator. Open Science decisions block their dependent modules. Do not use
`Closes P1` or treat merging that PR as P1 completion or acceptance of a 50 km plan.

## Implementation Impact Map

| Layer | Existing / added in the historical PR | Downstream responsibility |
| --- | --- | --- |
| Science | Original v3 draft / inactive Evidence / SDR, generated contracts and offline validation; new research handoff without changing those parameters | P1 new-scope Evidence / SDR, explicit acceptance and contracts; preserve historical versions |
| Analysis | Preserve `analysis/trail_training_context.py` within its original offline scope; no code change in this handoff | P4/P5 pure planning with actual history, module budgets and joint scheduling; intensity uses splits / samples, not `avg_power` |
| Data / sync | No persistence, history or migration changes in this handoff | P2 stable session identities and version compatibility; P3 provenance and rights; reuse `db/sync_writer.py` for sync writes |
| API / plan system | No route, generation, adoption or calendar writes in this handoff | P6 thin routes, authenticated deps, shared proposals and transactions; reject client-asserted authority and avoid a parallel lifecycle |
| Web / miniapp | Experience handoff only, without component / copy changes or rendered claims | P2 necessary reader compatibility; P7 `useApi<T>`, strict types, UI Quality and actual rendering; native editing later |
| Trust / rights | No personal-data access, logging / telemetry or authorization changes in this handoff | P2/P3/P6 ship complete read / export / delete and isolation with their new data, never postponed to P8 |
| Operations / provider | No Statsig, credentials, delivery, release or runtime changes in this handoff | P8 existing gate, zero-delivery verification, release / rollback and same-PR `docs/ops/` updates |
| Verification | Old v3 results cover only the old scope; new documents and publication payload need separate independent checks | Verify each PR's exact diff; P8 runs the full matrix rather than relying on the earlier 3601 tests |

## Universal acceptance matrix

| User / resource / goal scenario | Expected result | Main deliverable |
| --- | --- | --- |
| Weekly mountain access with trail experience | Use confirmed dates and actual history; abundant resources cannot relax budgets | P3/P4 |
| Mountain access twice a month | Schedule only explicit dates, never infer them from monthly frequency | P3/P4 |
| No mountain access for 14 days, sufficient base | Executable city training and explicit actual-outdoor gaps | P4/P7 |
| No gym / specialized equipment | Accepted templates or module limits; gym is not a default admission requirement | P4 |
| Sufficient running base, missing descent history | No fabricated descent dose; applicable basic and strength work remains available | P3/P4 |
| No device records, reported experience | Preserve provenance and use an accepted supplementary / limited path; do not label the person as having never run | P3/P4 |
| Strength beginner / experienced | Distinct admission, dose, exercises and explanation | P4 |
| Unknown / incompatible treadmill capability | Request input or limit the module; do not default to 10% or convert machine levels to percentages | P3/P4/P7 |
| Same-day running and strength | Independent identity and completion, shared time / recovery; completing one does not complete the other | P2/P4/P6 |
| Daily training without an event | No invented event date; rolling review, no automatic extension of expired resources, reconfirmation under policy | P3/P5/P7 |
| First-finish / performance goal | Separate interpretation and accepted rules; do not retain the performance-only restriction | P5 |
| Exactly 50 km with varied ascent / terrain / duration | Assess new support boundaries using demands and history; the old 49,999 m cap cannot be presented as support | P1/P5 |
| Pre-race window | Accepted taper and pre-race arrangements; the old blanket pre-race block is not a complete cycle | P5 |
| Canceled mountain or gym access | Revalidate drafts, flag adopted affected sessions and replace future sessions only through explicit successor adoption | P6/P7 |
| Duplicate requests, concurrent adoption, resource changes | No duplicate sessions, stale adoption, completed-training loss or partial plan on failure | P6 |
| Other account / outside trial / unknown version / gate off | Consistent server authorization; existing owner content retains data rights | P6/P8 |
| Adoption and later tasks | Evidence of zero calls to every provider | P2/P6/P8 |
| Desktop / mobile, EN/zh, offline / conflicts | Actual rendering and interaction verification, not source inspection alone | P7/P8 |

These are product and engineering acceptance criteria, not applicability trials or
proof of efficacy or safety. Epic completion requires P1–P8, the full claimed
support matrix, required decision acceptance, independent verification and release
evidence. Ninghai is an intermediate validation path, not a substitute for other
populations and conditions.

## Session and version handoff

The main session owns Epic goals, accepted decisions, dependencies and progress.
By default each PR has an independent execution session / branch or worktree;
fixes for that PR stay in its original session. Independent high-risk verification
starts in a read-only thread without executor history. Coordinators dispatch
roles under the current Work Contract; a previous PR's invocation or approval
does not expand authority.

Every handoff records:

1. Epic / issue / PR URLs, exact scope, completion criteria and status; chat
   memory does not replace artifacts.
2. Accepted decision versions / digests and open questions, including the blocked
   module and responsible role.
3. Starting commit, branch, worktree and actual diff; existing uncommitted changes
   and files that must be preserved.
4. Input / output contracts, dependency completion, migration / compatibility and
   data-rights requirements.
5. Tests actually run, independent review findings, exact verified head, logs and
   uncovered areas.
6. The next authorized action and publication boundary; subtask preparation does
   not confer runtime or human approval authority.

The historical authorization covered persisting handoffs, creating / updating the
Epic and eight issues, and preparing / publishing a draft PR. Documents and
external payloads received bounded independent Decision Review consistency
review and Quality checks; the coordinator completed those GitHub tracking
writes. That delivery carried P1 review foundations and handoffs forward without
accepting new scientific parameters. PR2–P8 implementation, Science acceptance,
automatic task assignment and deployment were outside that action.

The old [v3 verification record](trail-running-plan-v3-verification.md), with
3601 passed / 1 skipped, describes a historical independent checkout. Its
temporary logs may no longer exist; it cannot establish the current exact
commit's result. Each new PR must run
`python scripts/agent_preflight.py --base origin/main` against the exact commit
in a clean isolated checkout and preserve that run's full log and Preflight head.
The source worktree's `paseo.json` is unrelated and must not be committed, hidden,
moved or deleted to satisfy the clean-worktree check.
