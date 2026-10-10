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
committed, excluded or hidden to obtain a clean preflight. Report that original-worktree limitation truthfully. Root may run the unchanged
preflight in a separate clean checkout of the identical immutable commit; that
result remains distinct from the original worktree and is pending at handoff. Engineering retains sole source write ownership until handoff.


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


## Main integration and full-suite artifact repair

The user authorized merging `origin/main` at
`8f0f5dbb1600d16cc811c19898efbc9439134d2a` into this branch. Merge
`7bb86ee72d9639cfba910e1684cefdbb19676b80` preserves Coach commits and applies
the new single-session AGENTS policy. Earlier role/route references above are
historical task context, not additional current orchestration requirements.

The full preflight at `20cc81c8` completed pytest in 30m44s with 4,582 passed,
62 skipped, 13 failures and 59 setup errors. It stopped at pytest; no full
preflight pass is claimed. Log: `/tmp/coach-preflight-repair.log`.

Confirmed causes and repairs:

- Register the supplied draft SDR in the expected decision set and generated
  registry index; generate its missing review packet and inactive JSON contract
  with the existing scripts. Existing accepted records are unchanged.
- Update four telemetry assertions for the restored third insight type and
  cumulative reserved attempts; a rejected daily response consumes budget.
- Make the disposable designated-science fixture independent of global
  `core.autocrlf=true`. Its copied CRLF baseline was normalized by Git into LF
  blobs, causing strict historical-byte failures and dependent setup errors.
  Set `core.autocrlf=false` only inside that temporary fixture before its first
  commit. Do not weaken production byte/digest checks or rewrite source records.
- Root restored the exact pinned plugin checkout. The previously missing-file
  personal-context MCP test passed on rerun; no plugin source/gitlink changed.

The morning SDR remains draft/inactive. Its generated review packet is
`data/science/generated/review-packets/sdr-morning-coach-evidence-presentation-v1.md`;
its machine contract is in `data/science/generated/contracts/` with digest
`sha256:e3c7838fa8fd2f9768cc59f8aa9512e708a0682ff9e348c1cedbe41545ac37a1`.
No acceptance, activation or human approval was materialized. Final check results
and source ownership release are stated in the session handoff.


Final validation ownership: after this repair commit and explicit writer release,
root will create a separate clean `/tmp` checkout of the same immutable commit,
prepare pinned dependencies/submodule, and run unchanged
`agent_preflight.py --base origin/main`. The original `paseo.json` remains
untracked and untouched; no exclusion, stash, deletion or hidden change is used.
No completed final preflight result is asserted by this implementation record.


Repair verification before commit: registry/artifacts/telemetry/restored-plugin
checks passed 109 tests. The three affected science lifecycle suites completed
with 207 passed and one failure in 10m02s: the fresh source verifier clones HEAD,
so it could not see the still-uncommitted new packet/contract. That exact verifier
must be rerun after committing this generated-artifact repair. All prior designated
activation errors passed with the disposable fixture's local line-ending fix.
Static runtime/Copilot parity and both generated-artifact/index checks passed.
