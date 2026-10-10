# Morning Coach implementation handoff

Owner: Engineering. Initial HEAD: `39c8afa10d4937b61200e3f1a760746d799afbff`.
Work Contract route: `sha256:d7c5e77e834cc372e7a1aecc5127852816596881cf02a004d95317cac6b4113a`.
Decision Review `af198514-877b-4d47-a675-1a6aad598b16` returned
`human-review-required`, with authority satisfied by the supplied explicit user
authorization. This document records implementation, not independent approval.

## Governing artifacts

The parent supplied accepted logical Product `morning-coach-product`, Design
`morning-coach-design` / Experience `morning-coach-experience`, Architecture
`adr-morning-coach-snapshot-v1`, and Trust `tdr-morning-coach-restoration-v1`.
Engineering implements those boundaries. The exact proposed Science record is
persisted as `data/science/decisions/sdr-morning-coach-evidence-presentation-v1.yaml`,
draft/inactive. The existing accepted adaptive-load and outcome Evidence Reviews
are reused unchanged; the accepted adaptive-plan SDR stays runtime inactive.
No new formulas, clinical thresholds, managed-plan activation or mutation.

## Implementation impact map

| Area | Change and boundary |
| --- | --- |
| Recovery/data | `api/deps.py` rejects non-finite, undated, future, nonpositive HRV/RHR and invalid platform scores before existing formulas; preserves current observation dates and baseline exclusions. |
| Context | `api/ai.py` supplies RHR value/validity/date, supported trends, canonical action codes and source-only data freshness. |
| Server templates | `api/morning_coach.py` constructs eligible IDs before selection; renders all EN/zh daily text; rejects unknown/prose/contradictory selections. Summary is three concise sentences, with exact observations/dates and full modeled load in evidence. |
| Generation | Existing Azure runner restores daily eligibility on no-row sync/rollover. Input identity and content digest are separate. Failed selections are explicit unavailable content, never legacy/model prose. |
| Storage/caps | Existing `AiInsight` metadata stores version/provenance; private `_generation_budget` slot reserves cumulative daily attempts including failures. Daily reserves one provider call; multi-week types reserve two. SDK retries disabled for capped Coach calls. No tables/migration. |
| API consistency | Today brackets cached/bypassed/computed reads with fresh source/date/variant checks and conditional response validation. Daily list/individual reads require matching snapshot, provenance, template version and content digest. |
| Feedback | Fresh serialized write transaction; source revision lock precedes User lock; owner/date/source/content/terms/provider checks occur before new or duplicate votes and before commit. Existing storage and comment scrubbing retained. |
| Web | Shared `AiInsightsCard`: date, concise summary, visible key action, collapsed remaining detail, structured theory links, version-bound feedback, explicit status/retry and separately branded metrics. |
| Miniapp | Shared native `components/coach-receipt` replaces three page templates; matching typed contract, snapshot request, theory navigation and feedback identity. |
| Documentation | PRODUCT, DESIGN, design-system and API reference updated. |
| Operations | No deployment, credentials, infra or configuration changes. No production access, external post, plugin edit, push or PR. |

## Verification evidence

Developer verification is not fresh independent Quality. Synthetic browser data
uses real candidates/rendering/binding/persisted-provenance validation and route
serialization; model selection is simulated. No Azure calls are acceptance evidence.

- Morning Coach suite: 48 passed after concise-summary refinement.
- Routes/cache/ETag suite: 57 passed.
- Runner plus morning contract suite: 73 passed before the final summary refinement;
  the later focused suite covers that refinement.
- Wider context/generator/runner/packs run: 181 passed, one obsolete context-shape
  assertion found and updated for canonical reason/alternative codes. Its rerun
  plus existing recovery/integration tests passed (15 tests).
- Web build: 337 tests, TypeScript, Vite, PWA and public build checks passed.
- Miniapp: canonical types/catalog/legal sync, translation coverage and TypeScript passed.
- Science registry: full registry load passed; supplied SDR is draft/inactive.
- Receipt ESLint: passed after fixing its local render/effect state handling.
  Whole-web ESLint also reports unrelated existing errors; no blanket lint success.
- Full repository suite/preflight: final result is recorded in the Engineering
  handoff message; do not infer success from this list of targeted checks.

## UI quality

- Impeccable: `polish web/src/components/AiInsightsCard.tsx miniapp/components/coach-receipt`
- Visual review: desktop 1440x900; mobile 390x844, English/Chinese and light/dark
- Primary journey: Today -> key recommendation -> details -> theory links -> feedback comment/cancel; Analysis and Goal receipt comparison
- Reviewer handoff: local-only - `/tmp/praxys-morning-coach-qa/render/confirm-results.json` with original PNG captures beside it; live web `http://127.0.0.1:5176/today`
- States checked by Engineering: ready, missing, stale, AI unavailable. The attempted request-error capture was still loading and is not settled failure/retry evidence. Fresh Quality separately verified actual HTTP 503 and Refresh behavior.
- Accessibility: keyboard Enter expands disclosure, click closes, focus exercised, reduced motion enabled, no horizontal overflow; exhaustive screen-reader/contrast audit remains Quality work
- Design system impact: updated PRODUCT.md, DESIGN.md, docs/dev/design-system.md; one shared native receipt replaces page templates
- Miniapp parity: implementation/typecheck/i18n updated; native render blocked by Tencent authorization failure
- Exceptions: native rendered acceptance incomplete; no exception approval inferred

## Precise constraints and outstanding independent evidence

Daily model output has exactly evidence, interpretation and action ID arrays.
All required evidence is retained; model ordering emphasizes facts and supported
trends without choosing a second training decision. No plan remains no plan;
rest cannot acquire a workout. Every daily visible string/value is server-owned.
AI failure retains a concrete deterministic recommendation under Training metrics.
Seven-day recorded load has explicit date/coverage in details, not an injury-risk
interpretation. TSB is modeled load balance, not measured fatigue.

Snapshot identity binds owner, server date, all source revisions, plan visibility
and template version. Feedback digest additionally binds candidates, selected IDs,
ordering and complete rendered translations. Source mutation is assumed to use
existing revision writers; changing a consumed source must retain that invariant.
SQLite tests execute real serialized writes. PostgreSQL advisory/row-lock ordering
has static/test coverage but no live PostgreSQL concurrency execution in this task.

Tencent native opening returned `CONNECT_ERROR: wait WechatIDE authorization
timeout`; root's explicit recovery also returned `ok:false`, reason
`connect_failed`, no task ID. Do not retry until user authorization is supplied.
No successful simulator compile/render is claimed. Fresh independent Quality must
inspect the final exact commit without executor history and finish native rendered
QA when the environment is ready. Browser captures do not substitute for it.

`paseo.json` predates this work and remains untracked. It must not be deleted,
committed, excluded or hidden to obtain a clean preflight. Report its dirty-check
failure truthfully. Engineering retains sole source write ownership until handoff.


## Independent Quality repair

Fresh read-only Quality reviewed `d3b09136` and reported 26 independent Python
probes plus eight initial and five confirmation browser cases. Its actual
missing/stale/rest/no-plan fixtures, theory links, version payload and settled
503/Refresh checks are independent evidence, distinct from developer captures.

The follow-up repairs settle Coach loading into retryable failure when the current
Today or Analysis background dataset fetch fails; superseded failures still cannot
mutate the replacement request. A focused AST/transpile/VM regression exercises
both actual page methods. Shared web disclosure/Refresh/feedback controls use a
44px minimum target, native feedback controls use 88rpx, and Analysis preserves
the shared square web receipt. Native receipts remain rounded. Exact-head Quality
recheck follows the repair commit. The first preflight was deliberately stopped at
31% for this required repair, with no failures observed; its log is retained at
`/tmp/coach-preflight.log`. It is not a completed or passing preflight.
