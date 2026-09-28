# Activity DFA α1 implementation verification

Owner: Engineering execution evidence with separately identified Root native
observations, supplied to independent Quality, Trust and Science. This document
records performed checks and findings; it does not approve implementation,
activate science, claim deployment or establish complete native acceptance.
Approved contextual specification: [implementation contract](activity-dfa-alpha1-implementation.md).
First reviewed implementation: `9b0ddf7dc6fe3b7816e70f2ce9b4902ff959f865`.

## Independent findings addressed

| Reviewer boundary | Finding and resulting behavior | Regression evidence |
| --- | --- | --- |
| Quality / Science | Native HRV field0 could accept uint32 or malformed definitions. Consumed fields now use native message/field IDs, exact base types and structural sizes; duplicate RR/provenance definitions fail closed. Native compressed record-header timestamps remain supported. | Wrong RR uint32/signed/float/odd/zero/duplicate; wrong provenance base/array; developer names time/manufacturer/product/product_name cannot override native fields; compressed timestamp. |
| Trust / Science | A native Polar handle could change H10↔OH1 without invalidation. Identity aggregation now merges missing information, canonicalizes H10/Polar H10, and rejects contradictory native Polar model names. | Both transition directions, intermediate missing metadata, aliases and split manufacturer/name enrichment. |
| Trust | Rights export suppressed retained numbers when processing or numerical policy became unavailable. Export checks source/owner/expiry/erasure separately and retains historical numerical results plus original revision/provenance. | Processing withdrawal with computational authority deliberately forbidden; ordinary method update; source revocation still removes dependent results. |
| Quality | A surviving source confirmation plus expired cache could trigger automatic computation on opening. First-entry automatic work is now preparation only; retained proof requires explicit Analyse/Recalculate. | Actual compiled web and miniapp components with sole input, proof and latest_run:null; no POST until user action. |
| Quality | Miniapp comparator could relabel HR as power while loading. Dependent rows/series clear before awaiting context. Fresh metadata also clears obsolete active/result state. | Actual component with HR120, delayed Power response, empty interim rows, final Power250. |
| Quality / Trust | Withdrawing processing could hide Cancel together with numbers. Web separates fresh owner action metadata from numerical eligibility; both clients retain Cancel for active owner work. | Actual web/miniapp component tests: withdrawn processing, hidden numbers, exactly one cancellation POST. |
| Science | Local offsets were based on gathered packets but membership could borrow other same-chain intervals. Counts, QC, DFA, RR HR, support and original index diagnostics now use only complete intervals in those exact gathered packets. | Identical reviewed generator: +10s gap339scheduled/314valid/zero crossing; slow4s/hour drift with1s or10s anchors337/337; detected40s gap never bridges. |
| Science | Original search provenance had been reduced to DOI lookup. Restored exact Europe PMC queries, screening limits and PMCID/PMID verification from the original Science handoff. | Strict registry and generated contract/packet checks; all records remain draft/inactive with no signatures. |
| Design verification | Local picker items also needed44px targets. DFA SelectItems use min-h-11 without a global Select change. | Client type/lint checks; final rendered confirmation remains independent. |

The exact boundary tests also cover199/200complete beats,117599/117600ms support,
5000/5001ms local-offset width, private500error headers, resource limits, source
confirmation forgery, queue limits, lease recovery, restore-safe reparse, and
in-flight cancellation/revocation/deletion/reparse before publication.

## Executed checks

- Combined changed-surface suite: **203 passed** with real PostgreSQL enabled:
  `tests/test_activity_dfa.py tests/test_garmin_connectiq.py tests/test_data_export.py
  tests/test_account_deletion.py tests/test_evidence_registry.py tests/test_science_artifacts.py`.
  Command prefix: `DFA_TEST_DATABASE_URL=<isolated local PG URL>
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/praxys-stryd-evidence/python python3 -m pytest`.
  Includes the actual PostgreSQL global-slot claim and multi-session
  revocation-before-publication race; not merely sequential stale-worker checks.
- Added native compressed timestamp regression: passed in the subsequent DFA run
  (**73 passed, one optional PG test skipped** on that specific SQLite-only run).
- Web production build: **290 tests passed**, TypeScript/Vite/public-build checks
  passed. The subsequently added registered-native-fixture contract test passed;
  focused `web/tests/activity-dfa.test.mjs`: **9 passed**.
- Miniapp `npm run typecheck`: generated types/shared navigation/i18n/legal sync,
  translation coverage and TypeScript passed. Targeted web ESLint passed.
- Scientific generators `generate_science_artifacts.py --check` and
  `generate_science_registry_index.py --check` validate the exact draft packet and
  inactive contract; they do not constitute signed scientific approval.
- Actual PostgreSQL16 database `praxys_dfa_test` on a local socket was upgraded to
  `b4d5f6a70819`; no production credentials/provider API was used. SQLite creation
  and foreign-key account deletion regression passed.

Local logs: `/tmp/dfa-review-backend.log`, `/tmp/dfa-review-tests.log`,
`/tmp/dfa-web-build.log`, `/tmp/dfa-mini-check.log`, `/tmp/dfa-pg-migration.log`.
These logs are local evidence and are not shipped application artifacts.

## Private feasibility observation

The user-authorized private FIT was decoded and computed in memory only; no raw
file, beat/alpha series, device identifier or private screenshot was copied into
this repository. The corrected path yielded3timer blocks,812scheduled windows,
650valid windows, and actual selected-RR support **0.9811266143911439**.

Before exact gathered membership, the same file yielded0.9817064114391144 actual
support. Eight still-valid windows had narrower interval membership after the
fix; the support union decreased2514ms. The earlier whole-window-support value
0.9824723247 is not the shipped support definition. These observations demonstrate
input/numerical feasibility, not physiological accuracy, cross-device validation
or a production latency guarantee. Independent Science confirmed this final
observation at `ccd354e19b0f74d702116004ffeca05fedf4d041`.

## Remaining review and runtime boundaries

- The earlier Quality, Trust and Science confirmations and bounded
  desktop/mobile/EN/zh/theme browser pass are recorded below. A subsequent named
  Quality audit identified the header contrast defect described in the final
  section. Its local correction and Root's rendered confirmation are recorded
  there; independent repair confirmation follows the committed preflight.
- [Native fixture instructions](../../tests/fixtures/dfa/README.md) and registered
  automator function sources are prepared from installed WeChat skill0.3.11.
  No simulator/foreground call or Windows mirror was created in this preparation.
  The later bounded native pass is recorded below. Authorized miniapp work may
  launch registered DevTools without a separate foreground question; Node
  component/fixture tests do not replace rendered evidence.
- Science evidence/decision/implementation signatures, runtime activation and
  deployment remain unperformed. No accepted/active status or human approval was
  fabricated. Retained raw FIT and additive tables remain available for rollback.

## Narrow review confirmation and delayed manufacturer correction

At `9e0c2a785765a084fde95e549ce79071b6b6b01d`, the independent Quality
confirmation supplied through the Delivery Loop reported all its earlier findings
resolved:74 DFA tests with actual PostgreSQL,9 actual client/fixture tests, client
types, and the exact timing probes passed. Trust confirmed the export and native
field fixes, then identified one remaining case in the original source boundary:
`(unknown manufacturer, OH1) → (unknown manufacturer, H10) → (Polar, no name)`.

The source reader now retains every normalized nonempty native model name for each
recording-local handle. Once Polar manufacturer123 is established, incompatible
names cause rejection even when they preceded the manufacturer metadata. The H10 /
Polar H10 aliases remain one identity; missing fields enrich rather than erase
history. An unrelated watch's optical capability or model names do not establish
RR source and do not reject an otherwise eligible H10.

Engineering's narrow regression command:
`python3 -m pytest tests/test_activity_dfa.py -k 'polar or watch_native or source_identity' -q`
with the existing local fitdecode PYTHONPATH: **15 passed,67 deselected**. Both
transition directions, delayed manufacturer, alias/missing-field enrichment and
unrelated watch metadata were exercised through synthetic native FIT messages.
No UI or UI/native fixture file changed in this correction. Trust's narrow final
confirmation and original Science final verification subsequently passed at the
revision recorded below; this evidence is not a release or runtime activation claim.


## Final specialist confirmations

- **Quality**, at `9e0c2a785765a084fde95e549ce79071b6b6b01d`: all earlier
  findings resolved;74 DFA tests with actual PostgreSQL,9 actual client/component
  tests, both-client types and exact timing probes passed. The subsequent change
  was limited to Polar source-name history, backend tests and this evidence.
- **Trust**, at `ccd354e19b0f74d702116004ffeca05fedf4d041`: all three findings
  resolved (strict native provenance, retained rights export, delayed Polar model
  history);14 focused verification checks passed.
- **Science**, at `ccd354e19b0f74d702116004ffeca05fedf4d041`: exact numerical/
  timing fixtures, gathered-packet membership, beat counts, actual support union,
  original-index provenance, source interpretation and contract digest checks
  passed. The private file retained812 scheduled/650 valid windows and actual
  support0.9811266143911439; the2514ms reduction involved8 narrower valid windows.
  Exact Europe PMC/PMCID/PMID provenance was confirmed. This independent agent
  review does not replace the formal evidence/decision/implementation signatures.

All scientific records and their generated contract remain **draft/inactive**.
No deployment, runtime activation, human signature or real-device physiological
validation is claimed.

## Initial rendered browser evidence

Root coordinated a real Paseo browser pass using only the synthetic API fixture.
This was an available runtime browser extension; the portable Chrome DevTools MCP
was unavailable. CSS viewports were1440×900 desktop and390×844 mobile, with English
and Chinese in light/dark themes. The application and native fixture trees were
unchanged from the Quality-reviewed9e0c2a7 revision through ccd354e1:

- `web/src`: `20f89790c69e4d98af4d6c87f6d5f30105364b62`
- `miniapp`: `cf0d53340ff4df69b5af956fd6f2f625881ca85f`
- `tests/fixtures/dfa`: `5e51f7b474a810bbcbd3bfe9a58d33b385f24e33`

The ignored browser fixture was corrected to use separate preparation/computation
run IDs, matching the real immutable API rows. No tracked application code changed
for that fixture correction. The final browser pass checked:

- Prepare → unchecked source confirmation → calculation; source/date/model labels,
  localized pickers and explicit selection when multiple inputs exist.
- The real range control measured760×44px desktop and335.2×44px mobile. Keyboard
  ArrowRight moved120→125s; PageDown selected725s and Enter committed the page jump.
  Gaps remained visible, alpha axis values used two decimals, and no horizontal
  overflow appeared at the tested viewports.
- Dark body explanatory text and chart-axis contrast measured15.26:1 after the
  local token fix. That measurement did not cover the header description/date;
  the later audit found their contrast insufficient. Stale results exposed Recalculate with zero charts;
  inactive processing exposed zero charts; unsupported providers had clear copy.
- Delete/revoke invoked the actual DOM handlers with the exact DELETE and metadata
  GET requests only; focus/reopen did not issue a recreating POST. Footer controls
  used DOM clicks when the browser's text snapshot was truncated.
- No application console errors remained after the synthetic fixture stabilized.
  Native browser keyboard behavior and element focus were exercised. No physical
  touchscreen, screen-reader device or WeChat simulator pass is claimed.

Reviewer handoff is **local-only**: [original-resolution gallery](../../test-screenshots/ui-quality/dfa-alpha1/index.html).
Final captures in that ignored directory are `final-confirmation-desktop-zh.png`,
`final-result-desktop-zh.png`, `final-result-mobile-dark-zh.png`,
`final-chart-mobile-dark-zh.png`, and `final-deleted-mobile-en.png`. The gallery
links to the originals and distinguishes `first-*` pre-fix captures. Nothing was
uploaded or published.

## UI quality

- Impeccable: `audit web/src/components/ActivityDFA.tsx` performed by independent
  Quality; `polish web/src/components/ActivityDFA.tsx` used for the local header
  contrast correction, preserving the existing Field Lab design.
- Visual review: desktop1440×900; mobile390×844; EN/zh; light/dark.
- Primary journey: Activity → DFA preparation → source confirmation → window review
  → delete/revoke, with synthetic data only.
- Reviewer handoff: local-only — `test-screenshots/ui-quality/dfa-alpha1/index.html`.
- States checked: preparation, confirmation, calculation, complete, gaps, missing/
  unsupported input, multiple versions, stale/inactive result and deletion.
- Accessibility: native browser keyboard/focus,44px control targets, measured dark
  text/axis contrast and no overflow; device screen-reader/touch testing unperformed.
- Design system impact: none — existing tokens, sheet, inputs and chart patterns.
- Miniapp parity: implementation, types, i18n and actual component lifecycle tests
  passed; the subsequent registered native pass and its limits are recorded below.
- Exceptions: Chrome DevTools MCP unavailable (Paseo browser used); native canvas,
  physical gesture and screen-reader-device coverage remain incomplete.

## Named audit and header contrast correction

At `688b33636e4c8602699c0556031b2230cdb41cc7`, independent Quality performed
`Impeccable audit web/src/components/ActivityDFA.tsx` using the five final gallery
PNGs, current source and recorded interactions. Its sole blocking finding was
normal14px header description/date text atRGB(109,114,125) onRGB(14,17,26),
contrast **3.909:1**, visible in `final-result-mobile-dark-zh.png`.

The earlier15.26:1 measurement applied to body explanatory text and chart axes,
not this header. The DFA-owned description now wraps both text and date in the
existing `dark:text-foreground` semantic utility. Shared `MetricDetailSheet`
defaults, global tokens, light styling, text, date formatting and backend behavior
are unchanged. No test asserting a CSS class string was added; rendered computed
colors and contrast are the relevant regression evidence.

The narrow execution checks passed: targeted ESLint, Web291tests plus TypeScript/
Vite/public build, miniapp type/navigation/i18n/legal generation and TypeScript,
UI detector with `--skip-evidence`, and diff checks. Two Lingui extractions were
byte-identical and produced no catalog changes.

Root completed the bounded header confirmation in the actual Paseo browser at
CSS390×844 and1440×900, Chinese dark theme. Description and date both remained14px;
their computedRGB(228,232,239) against dialogRGB(13,18,27) yielded WCAG contrast
**15.26433276563108:1**. Neither viewport had horizontal overflow. Desktop light
preserved the same inherited `oklch(0.45 0.02 264)` on parent, description and date.
No application console errors appeared; Vite/React information and a diagnostic
canvas-readback performance hint were not application errors.

Original-resolution captures are `final-header-mobile-dark-zh.png` (488×1055) and
`final-header-desktop-dark-zh.png` (1800×1125) in the same local gallery. It links
both and labels the earlier result captures as before the header correction.
This confirmation covers the header fix only; it is not another full journey or
native WeChat pass. Backend, scientific, source, privacy and miniapp application
trees were unchanged by this correction. The existing isolated PostgreSQL
service was restored for the final full preflight; its evidence is reported in
the immutable-head handoff.

The required full committed-head preflight is the next verification step. Its
immutable HEAD, command and output will be reported in the handoff after execution,
without rewriting this file merely to insert a self-referential commit hash.


## Registered native verification and foreground authorization

The user explicitly authorized miniapp use and removal of the extra foreground
permission gate. The wrapper and canonical instructions now treat authorized
miniapp work as sufficient for visible DevTools. Tencent readiness, login,
client/token, pending-task and sensitive-action confirmations remain intact.
The bounded policy record is
[wechat-foreground-task-authorization-v1](wechat-foreground-task-authorization-v1.md).
Independent wrapper verification passed 10 tests plus 17 bridge/real-rsync
scenarios; the fixture formatter passed 20 focused tests, including output-path
alias protection. Independent modal lifecycle review passed 24 focused checks
plus callback/page-ownership probes.

Root used installed Tencent skill 0.3.11 through `scripts/wechatide`, one
task-owned window and a dedicated generated mirror. Request and storage mocks
served synthetic data only, with no forwarding fallback, real credentials,
provider request, upload or production debug route. Native WXML compilation
succeeded. Logical viewport was 390×844; the original tool-produced PNGs are
192×413 or 149×321 display captures, not native-size phone screenshots. They
support coarse layout inspection, not native-size readability or contrast claims.

The native pass found and fixed three local layout/lifecycle defects: unsupported
`inset` sizing became explicit edges with the incumbent 88vh sheet, Close now has
a 44px target below the native capsule, and the panel hides/restores its owning
custom tab bar using current state even after delayed callbacks. Measured overlay
was 390×844; sheet top 101.3 / height 742.8; Chinese Close 49×44 at (324.5,126.3),
below capsule bottom 83. An actual tap at the former tab-bar position stayed on
Analysis; actual Close restored the bar and preserved the single synthetic
activity. Reopening preserved the existing activity flow.

Performed checks, with native taps distinguished from fixture setup:

- Actual checkbox and Confirm taps: unchecked preparation became a complete
  result with 120 planned windows. Context handler setup switched RR heart rate,
  power 250 and pace. An actual Next tap after official ScrollViewContext setup
  selected offset 120 / pageIndex 1, 120 rows, first window ID 120 and retained power.
- Actual Delete All taps: scope stated that FIT remains; result/rows/job cleared,
  and explicit refresh made zero additional POSTs.
- Matching initial-state captures: complete/en/dark; withdrawn/en/dark;
  expired/en/light; multiple/zh/light; no_valid/zh/dark. Expired retained one
  confirmation with no run and no POST. Multiple inputs remained unselected
  with no POST. No-valid completed with 120 null-window rows and the explicit
  “没有窗口通过分析检查。” explanation.
- Withdrawn processing hid results while preserving the active owner job.
  An actual Cancel tap issued exactly one cancellation POST, then status became
  cancelled, active=false and rows 0. The post-cancel PNG retained an earlier
  frame and is excluded from passing visual evidence.
- Actual source-revocation taps showed the confirmation/dependent-result scope
  while retaining original activity records. Confirm sent one DELETE, followed
  by metadata GET; confirmation/run/results cleared. Explicit refresh was GET
  only with total POST 0. This native fixture had null alpha windows; populated
  numerical revocation is covered by the separate Web, component and SQL tests.

Same-page fixture resets and some post-action screenshots retained old frames
although runtime data and geometry changed. Those images are excluded from
passing visual evidence. `simulator_open_page` also reported success without
proving the runtime login route; registered `automation_navigate reLaunch` and
a route guard were used for cleanup and the final narrow confirmation. No
application defect was inferred from these adapter mismatches. Official
ScrollViewContext positioned the viewport; physical/gesture scrolling was not
verified. Native taps establish handler/request behavior, separately from PNGs.

The native console explicitly reported:

> [Component] <canvas>: 开发者工具暂未支持 Skyline 下的 canvas 组件调试，请先到真机上预览调试。

The shared line-chart already documents this platform limitation. Both canvas
plots remain unverified on a real device. No renderer change was made to evade
it. Physical gestures, screen-reader behavior, focus and larger text remain
unverified. Science stays draft/inactive; no deployment or full native acceptance
is implied.

Independent native Quality checked image/source hashes and identified one P2:
active+stale rendered the same status paragraph twice. The separate stale notice
now renders only when `!active`; cancellation and wording are unchanged.
Existing 13 focused client tests passed. The narrow registered compile and
actual open/capture showed processing=false, active=true, hidden results, two
copy elements (one processing notice plus one status) and no duplicate paragraph.
The final screenshot is `native-withdrawn-fixed-en-dark.png`, 149×321; SHA256
`d18550e1c0451e28a7691b0cf1ebfbf17265a7e90aeae24e4a67e19b2af44e75`.

Detailed local evidence: `test-screenshots/ui-quality/dfa-alpha1/index.html`,
`native-cold-evidence.json`, `cold-*-capture.png`, and the final withdrawn PNG.
The gallery labels earlier geometry/list evidence and excluded stale captures.
No evidence image was committed or published. Mocks were restored after returning
to the guarded login route; only the task-owned window was closed.

Independent native Quality subsequently confirmed this P2 resolved against the
exact WXML SHA256 `58be926f9dad60b4e627c0683cecb91430da81b7e9f1c828ae2825692a021230`
and final image hash above. The reviewer inspected source and the frozen PNG; it
did not rerun native tools or certify complete native acceptance. Final teardown
confirmed login, removed the synthetic fixture, restored both mocks and closed
only task window `s0`.

## Runtime admission limitation in final cleanup

After native Quality supplied the single duplicated-status finding, resuming the
existing Engineering thread returned `agent thread limit reached`. Completed
leaf cleanup and retry did not restore admission. The Delivery coordinator
queued that continuation and remained read-only. Root applied the already
specified one-condition UI correction and factual fixture/evidence updates,
then performed the final execution checks. Independent review remains separate.
This fallback is recorded as incomplete role separation under the native-thread
profile; it is not an approved policy exception or a runtime parity claim.
The foreground permission change has its own prior user authorization and
independent policy review; it does not authorize this runtime substitution.


Before final commit, Web extraction was unchanged and the production build
passed 306 tests, TypeScript, Vite and public-output validation. Miniapp generated
types/navigation/i18n/legal checks and TypeScript passed. Science artifact and
registry generators, static adapter conformance and diff checks passed. The
required committed-head full preflight is reported with its exact head and
counts in the PR handoff; these preparatory checks do not replace it.

## PR #839 merge repair review — 2026-09-28

The independent whole-patch review of `5b8148a93a1def57589d7a38ee3e8ac8f889c509`
confirmed four findings. The fresh coordinator reused Work Contract
`wc-dfa-merge-20260928`; one Engineering writer repaired them. Independent Quality
and Trust reviewed the frozen repair patch with SHA256
`ca5eb7ed3fe0170c9bbca3947e95ea103f714bbbb91277c4ed5b44b26c24d223` before this
factual evidence addition and final preparation.

- Quality closed Q1: an exceptional completed Future is detached before its
  result is consumed; subsequent ticks resume claiming work. Background erasure
  replay advances a cursor with at most 20 stored records per tick.
- Quality closed Q2: registered native taps revoked retained proof after result
  expiry and while processing/science was inactive. Each sequence issued DELETE
  then GET, cleared the proof and issued no POST. Multiple recordings started
  unselected; invoking the actual picker handler selected the matching proof.
  This handler check does not establish a physical picker gesture.
- Trust closed T1: cancellation returned metadata only across all seven run
  states with authority/currentness/storage checks forced unavailable. Actual
  middleware tests confirmed ordinary GET blocked with 428 or 503 while cancel
  returned 200 without numerical payloads. Retry replays pending deletion first.
- Trust closed T2: eight concurrent DELETE requests produced one manifest; eight
  concurrent replay/deletion operations after new work produced two distinct
  cutoffs. Cross-owner reads returned 404 and no-op erasure created no manifest.
  Fake-Blob checks verified owner-prefix listing and wrong-owner rejection;
  live Blob was not exercised. Pending restore requests, request-before-SQL
  ordering, later-created work and 14-day completed retention remain covered.

Engineering's consolidated synthetic checks passed 168 tests, including the
actual PostgreSQL 16 lifecycle/recovery cases, ConnectIQ, export and China
boundary regressions. Independent Quality passed 95 backend tests with no skips
and the isolated PostgreSQL database enabled, 12 actual-component client tests,
miniapp typecheck and native WXML compilation. Operations found no additional
blocker and confirmed the updated rollback/recovery documentation. These scoped
reviews do not substitute for final immutable-head checks or Decision Review.

Quality's original tool PNGs are 149×321 for a logical 390×844 viewport and support
coarse layout inspection only. The local gallery is
`test-screenshots/ui-quality/dfa-alpha1/quality-repair/index.html`; the detailed
review is `/tmp/dfa-pr839-merge-review/quality-repair/verification.json`.
Source stayed unchanged during native verification. Quality removed the synthetic
fixture, restored request/storage mocks and closed only task window `s0`.
Real-phone canvas drawing, gesture scrolling, screen readers and larger text
remain unverified. Science remains draft/inactive, without fabricated signatures.
Design system impact: none — existing tokens and components cover this repair.

The prior Engineering continuation target was subsequently confirmed unavailable
(`not_found`). The old coordinator admitted one non-chaining replacement, but
native spawn failed at the thread limit without returning a target or executing
any repair. A fresh managed workspace-write coordinator restored capacity and
admitted the sole Engineering writer for this batch, with independent read-only
Quality and Trust. This continuation does not retroactively make the earlier
runtime substitution conformant; no Full Access switch or policy exception is
claimed. Existing user authorization covers merge and ordinary main-triggered
rollout, while scientific activation and manual provider publication remain
separate. Final commit/check/Decision Review evidence belongs in the immutable
handoff rather than a self-referential hash in this document.
