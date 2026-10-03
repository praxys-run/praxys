# Activity DFA α1 implementation contract

Status: user-approved implementation specification, 2026-09-27. This record
mechanically preserves the approved contextual Product, Science, Design,
Architecture, Trust and Operations decisions; Engineering does not independently
approve them. Signed scientific activation, independent verification and release
evidence remain separate requirements. No scientific signature is inferred from
this document.

- Delivery contract: `dfa-alpha1-delivery-v1`.
- Approved plan subject: `sha256:1a0e7ac98c071d837ed52f0c3a0cdb39d4ac14c33cfe2f3755afa27d7f3501a6`.
- Delivery route: `sha256:9a990a4df2b3854d28678cb57c53910f7b365646320d52e3af2f47566238a108`.
- FIT archival prerequisite: [PR #838](https://github.com/praxys-run/praxys/pull/838),
  local commit `d7b35179f0883491e8381e8e53dc990c4f6a7b9e`. Integration in this
  checkout does not claim upstream deployment.

## Product decision — owner: Product

Provide post-run DFA α1 for a single running activity with eligible ECG chest
strap RR. Show supported portions, excluded windows and RR heart rate with
optional pace/power. No overall α1 score, threshold detection, fatigue/intensity
verdict, training changes, cross-activity comparison, live feature, file upload or
new connector. Core input is device-neutral; v1 consumes existing Garmin-platform
FIT archives. AlphaHRV installation and its developer α1 fields are irrelevant
to native RR eligibility.

The exact owner/account/activity archive must contain one native running session;
running subtypes are accepted, multisession/multisport/nonrunning or contradictory
types are not. No approximate-time association or ActivitySample.source inference.

## Science decision and evidence boundaries — owner: Science

Method `dfa-alpha1-raw120-v1`; SDR `sdr-activity-dfa-alpha1-v1`.
Native uint16 HRV time values are authoritative milliseconds, float64 arithmetic.
Trim only trailing invalid 0xFFFF/None padding. Ignore all-padding packets;
interior invalids/zero/structural corruption break chains. Positive intervals
always contribute time. Mark <250 or >2000 ms as suspect. Compare each interval
to the median of up to five preceding and five following range-valid neighbors
within its chain, excluding itself: fewer than five neighbors is incomplete QC;
relative deviation >20% is suspect. Reject windows containing suspect/incomplete
intervals; never remove/interpolate/correct/resample beats or apply smoothness
priors.

Each timer-active block schedules trailing 120-second windows every five seconds,
ending at start+120s+k*5s and no later than stop. At least 200 complete intervals
and 117600 ms (98%) selected coverage are required. Low heart rate may fail the
beat minimum without implying sensor failure.

Use paired ordered primary timer events and FIT epoch 1989-12-31 UTC. Pauses,
source discontinuities and time reversals break chains. For each packet nearest
file-order record timestamps (or block boundary) produce [a,b], width 0..30000ms.
Let C be cumulative RR at packet end; its unexpanded offset interval is
[a-C,b-C]. Adjacent interval distance >2000ms adds a break; gradual drift does not.
For each window [w0,w1], gather packets where b>=w0 and a<=w1. Reject no packets
or multiple chains. Set L=max(a-C-1000), U=min(b-C+1000); reject L>U or U-L>5000.
Offset is median((a+b)/2-C) clamped to [L,U]. It only determines complete interval
membership in the exact gathered packets only; retain unchanged RR and original interval references. Save offset
diagnostics, not a claimed precise permanent beat timeline. Label alignment as
estimated, and bounds as consistency guardrails, not physiological confidence.

Demean and integrate RR once. For each integer scale n=4..16, q=floor(N/n),
starts are {j*n, N-(j+1)*n | j=0..q-1}; retain duplicates between directions.
OLS linear detrending includes intercept. F(n) is sqrt of the mean residual
squares across all boxes in both directions. Alpha is equal-weight OLS slope of
ln F against ln n. F<=1e-12ms or any nonfinite result invalidates the window.
Never clip alpha; <0 or >2 adds atypical_value without diagnosis. R² is audit-only,
null for zero log-F variance, roundoff clamped to [0,1]. Full API precision, two
UI decimals. No 0.75/0.5 lines, personal threshold or Kubios-equivalence claim.

All scheduled windows enter the success-rate denominator. Separately report the
union of valid window support divided by timer duration and short blocks; neither
is accuracy. RR HR is 60000/mean RR. Optional exact-activity existing samples hold
forward at most two seconds to the next sample; finite nonnegative values only,
zero retained. Each overlay needs 96s support independently. Power is weighted
mean; pace is 1000/weighted mean speed, null at mean speed<=0. Missing overlays
never gate alpha. Preserve stored power precedence.

120-second windows and 4..16-beat scales have literature support; exact QC, timing
and minimum-beat values are Praxys guardrails. Say no issues detected by these
checks, never zero artifacts. Evidence includes:

- https://doi.org/10.3390/s21030821 (artifact/device study, full text examined).
- https://doi.org/10.3390/s22176536 (H10 validation, full text examined).
- https://doi.org/10.1007/s00421-024-05592-2 (running, abstract examined).
- https://doi.org/10.14814/phy2.70777 (cycling, full text examined).
- https://doi.org/10.1186/s40798-024-00768-8 (mixed HRVT methods; no direct
  validation of this complete implementation).

Private local feasibility: a 560436-byte FIT yielded 11085 RR, 812 scheduled
windows, 794 timing passes and 650 timing+QC passes. This is not complete numerical
or physiological validation; do not publish/copy the private fixture. Native RR
without AlphaHRV is accepted by content; an app-disabled real recording remains
unverified.

## Source and privacy decision — owner: Trust, scientific boundary: Science

Native FIT RR lacks direct sensor association in v1. Require compatible recorded
ECG metadata plus per-activity owner confirmation. Initial registry: manufacturer
1 product 1743,1752,2327,3299,3300,4130,4446,4606; manufacturer 123 product_name H10
or Polar H10 after ASCII trim/case normalization. This is sensor-type support,
not per-model accuracy certification. No nickname/user text/generic HR matching.
Watch optical capability alone is not evidence of optical RR. Known optical,
mixed or contradictory RR cannot be overridden.

Unchecked statement `dfa-source-attestation-v1`:
“本次活动记录全程以所选 ECG 心率胸带作为逐搏间期来源，未切换至其他 RR 传感器或光学心率。”
Display “来源由你确认” / “Source confirmed by you”. Bind owner/activity/provider
account/snapshot/SHA/parse/parser, recording-local sensor reference, server evidence
digest, relevant source-rule fingerprint, statement version and server timestamp.
Store no serial/Bluetooth address/raw metadata in DFA tables. Confirmation survives
result expiry, has no independent TTL, and is renewed after reparse/relevant source
evidence change; unrelated registry additions or math/QC changes do not invalidate
it. Changing selected sensor revokes prior proof and dependent runs atomically.

First-party owner only, no MCP expansion/demo redirection. Compute needs active
non-demo user, current legal/channel receipts and existing background-processing
authority, but no live provider connection. Rights cancellation/revocation/deletion
and export survive stopped processing/stale terms. Recheck authority/input/proof
during work and final publication. Serialize owner lifecycle; publish by conditional
UPDATE of existing generation+lease, never upsert deleted work. Reparse cancels
pending work and stales results. Source revocation/contradiction hides or deletes
numbers; ordinary obsolete math results may remain until expiry but are not shown
by default.

Account/source erasure removes derived rows and confirmations. Export includes
retained result/proof/provenance/diagnostics, not leases or duplicated raw RR.
Use existing private storage for payload-free deletion manifests: operation UUID,
owner, target scope/id, cutoff, reason, requested/completed timestamps. Persist
requested before SQL erase and completed after commit. Pending manifests never
expire; completed retention covers existing 14-day backups. Replay before reads,
compute and complete DFA export; failure closes those surfaces, not deletion.

## Architecture decision — owner: Architecture

`RRRecordingReader.list_inputs(owner, activity)` and `iter_recording(ref)` pin
provider/owner/account/activity/snapshot/parse/SHA/parser version. Only exact
Garmin-source activities are offered by the current adapter. Multiple inputs
require explicit choice. Selectively decode retained raw_fit using fitdecode
0.11.0, processor=None, strict CRC and errors; check SQL byte length before blob
hydration and SHA after it. Keep needed RR/timer/anchor/device frames in memory
with file-order references. Do not read full archived JSON or make provider calls.

Exactly three tables: activity_dfa_runs (immutable digest/input/method/proof,
phase/generation/state/attempt/lease/progress/diagnostic/bounded result),
activity_dfa_confirmations (independent evidence), activity_dfa_execution_slot
(singleton global lease). Preparation has no confirmation and finishes awaiting
confirmation or unavailable. Confirmed computation is a separate immutable run.
Statuses queued/running/awaiting_source_confirmation/complete/unavailable/failed/
cancelled; freshness current/stale is separate. Complete may have zero valid
windows with explicit availability explanation.

API lifecycle dispatcher, one-thread executor per worker and at most one pending
submission; SQL coordinates one global lease-valid execution. Explicit POST wakes
it, every five seconds reconciles. GET/sync/reparse never enqueue. One active run
per owner, global active admission cap20 (429). Lease180s renewed15s, token and
generation fence publication. One automatic expired-lease recovery; deterministic
input errors need explicit retry with expected_generation. Closing client does not
cancel. Expired lease cannot guarantee one physical thread, only one publisher.

Bounds: raw64MiB, elapsed48h, RR200000, frames250000, result8MiB, cooperative
execution120s, SQL30s. Explicit error, never truncation. Owner quota256MiB reserves
8MiB per active run under lock; evict oldest completed cache first, never proof/raw/
active work. Actual terminal size replaces reservation; recovery reuses it.
Prepare/unavailable retention24h, result up to30d from completion (no read refresh),
failed/cancelled7d. Hourly and admission cleanup. No new service/config/Statsig gate.

Prefix `/api/activities/{activity_id}/dfa-alpha1`:

| Method/path | Contract |
| --- | --- |
| GET base | metadata candidates, catalog_revision, valid proof/latest run |
| POST base | input(provider,snapshot_id,parse_id), catalog_revision, optional source_confirmation_id; 202 active/new, 200 cached terminal |
| GET /runs/{id} | offset/limit(default120,max1000), ordered windows with null failures retained |
| POST /source-confirmations | run_id,sensor_ref,evidence_digest,statement_version,confirmed:true |
| GET /runs/{id}/context | same page, required result_revision, optional expected_samples_revision |
| POST /runs/{id}/retry | expected_generation |
| POST /runs/{id}/cancel | owner cancellation |
| DELETE /source-confirmations/{id} | proof and dependents |
| DELETE base | activity DFA data only |

All responses private,no-store; no ETag/304. Server SQL caches exact versions.
Window fields include boundaries, nullable alpha/reasons, counts, timing/coverage,
index refs, RR HR/R². Global method/source/summary fields. Context revisions bind
result+samples+overlay version+page; reread changed samples once, otherwise409;
clients never combine pages from different revisions.

## Experience specification — owner: Design

Web History independent DFA button even without splits; wide MetricDetailSheet
(desktop right/mobile bottom). Miniapp Analysis→Activities parity native panel.
Preserve list/split state on close. Reopen/focus refresh metadata before numbers.
Explicit first entry may prepare sole input; multiple inputs require selection.
GET/poll never enqueue, stale/expired data requires explicit recalculate. Checkbox
unchecked; select among sensors. Saved confirmation + failed submit retries only
compute. Poll visible running states3s first minute then10s; respect Retry-After,
stop hidden/failed/terminal. Show real stage, not invented percentage.

Differentiate archive waiting, missing RR, unsupported source/type, no valid windows,
limits, failed/cancelled. Coverage/qualification precedes alpha. Default RR HR plus
one optional pace/power comparator; details and ScienceNote. Whole-activity quality
navigation distinguishes supported/unsupported/timer-paused spans without alpha
aggregation or hiding small gaps. Detail graph and accessible table use120 scheduled
windows per page, no downsampling/gap bridging; previous/next/time jump/individual
window access. Revision-bound navigation includes elapsed/timer blocks/support
union/page anchors. 44px targets, EN/zh, themes, keyboard/screenreader/touch.
Delete/revoke explains scope, clears caches, stops requests and fences late replies;
only explicit action re-prepares.

## Implementation impact map and verification

| Area | Implementation responsibility |
| --- | --- |
| Data | Exact archive reader; three-table additive SQLite/PostgreSQL migration; no sync-provider extension |
| Analysis | Pure selective RR extraction, timer alignment, QC, DFA, overlay/support computation |
| API | Thin authenticated routes, bounded executor/SQL leases, owner lifecycle/proof/version fencing |
| Rights | Existing auth/channel exceptions, account export/delete, reparse invalidation, private restore manifests |
| Clients | Typed useApi contracts, web ActivityCard/sheet, miniapp activity panel, science/copy/parity |
| Operations | Dispatcher/retention/replay runbook, no numeric/device telemetry; existing rollback retaining additive tables |
| Tests | Synthetic FIT, independent numerical reference, queue/race/privacy/migration/API/rendered parity |

Stages: contextual records → numerical core and independent reference → persistence/
API/lifecycle → both clients → independent specialist/Quality verification → reviewed
release/signed SDR activation. Engineering's own checks do not replace independent
verification. No deployment or activation is claimed by implementation.

Acceptance includes ≤1e-9 independent DFA error; constant/white/integrated/reversed
signals, unit/offset/R² boundaries; padding/interior errors/range/QC/200-beat/98%
boundaries; drift/jump/smart-recording/pause/no bridging; no-AlphaHRV and missing-RR
fixtures; registry/forged/stale/mixed-source confirmations; multiworker lease and
cancel/delete/reparse races; limits/quota; owner/account/demo/MCP/rights boundaries;
export/manifests/restores; overlay zeros/gaps/revisions; all UI states/long recordings/
themes/i18n/accessibility; SQLite/PostgreSQL migration and regression suites.

## Contextual decision metadata

These logical records all use schema_version1 and bind the approved plan subject
above. Judgment review route: human-review-required, satisfied by the user’s explicit
approval of the immutable plan subject. The later agent-resolved route covers
contract consistency and implementation authorization only; it does not approve
Product, Trust or Science judgments or replace signed scientific lifecycle records. Recommendation is the user-selected option below.

| ID / decision_type / owner | Question; options and selected recommendation | Dependencies; rationale; outcome_plan |
| --- | --- | --- |
| pdr-activity-dfa-v1 / product / Product | Post-run supported-window inspection or automatic physiological prescription? Inspect supported windows. | Evidence/SDR and source eligibility; provide bounded useful analysis; observe completion and user comprehension without numeric telemetry. |
| ddr-activity-dfa-v1 / design / Design | Whole-activity numeric downsampling or coverage navigation plus120-window details? Coverage navigation and detailed pages. | Product/source/quality states; preserve gaps and readable data; independent desktop/mobile/i18n/accessibility verification. |
| adr-activity-dfa-v1 / architecture / Architecture | Read large archived JSON or selectively decode retained raw FIT? Decode original locally. | PR838 immutable archives; avoid105× projection amplification; monitor aggregate execution duration and failures. |
| tdr-activity-dfa-v1 / trust / Trust | Reject ambiguous recorded ECG attribution or allow purpose-bound owner confirmation? Recorded compatible sensor plus per-activity attestation. | Versioned source evidence, owner lifecycle, private restore manifests; broader eligible archive coverage without asserting measured provenance; verify isolation/deletion/reparse/restore. |
| odr-activity-dfa-v1 / operations / Operations | New distributed queue service or bounded API worker with SQL lease? Existing API lifecycle and singleton lease. | Additive migration and signed active science contract; reversible deployment without new service/config; monitor aggregate states, recoveries, reasons and120s budget. |

Engineering pins both the complete parameter-map fingerprint and the exact active
science contract digest on each immutable run. Changed science contracts cannot
reuse or publish old results; source confirmations remain independent of numerical
method versions. RR index references are original non-padding interval ordinals,
including skipped, invalid and out-of-timer intervals, not renumbered retained data.

The first-party rights transports permit only DFA cancel/delete/revoke before a
current China notice; neither compute nor result reads receive that exception.
Account-level export/deletion remain under existing data-rights routes. A TermsGate
or stopped-processing screen may prevent entering the analysis panel, but does not
remove authenticated data-rights endpoint authority.

## Implementation evidence and release state

Historical premerge Release Evidence (2026-09-27): **not deployed; science contract inactive**. No runtime activation
or signed human approval was materialized. New Evidence Review/SDR and generated
review packets preserve Science ownership and explicit missing approval stages.

Local checks: independent numerical reference40variants max absolute error5.55e-15;
synthetic native FIT and API/lifecycle suites; existing ConnectIQ/export regressions;
SQLite and actual PostgreSQL16 migration; both client typechecks and translations.
The private local full pipeline probe (no private fixture/output copied) produced
3timer blocks,812scheduled,650valid,18alignment and144QC exclusions in1.457s; actual
selected-interval support0.9817064 before the gathered-packet membership correction.
The corrected implementation retains812scheduled/650valid, with actual selected-RR
support0.9811266144 (2514ms less union support across8narrowed valid windows).
These are implementation feasibility observations,
not physiological accuracy or production latency guarantees.

Design system impact: none — existing Field Lab tokens, responsive metric sheet,
native panel and line-chart are reused; optional numeric x positions preserve real
pause widths without changing existing chart consumers. Existing Analysis fitness
series literal-color hook findings predate this patch; no new literal series colors
were introduced. Native controls use min-height44px, retaining the approved minimum on narrow viewports.
Rendered evidence and independent specialist verification are recorded separately.


## PR #839 merge repair impact map — 2026-09-28

The `wc-dfa-merge-20260928` Delivery contract repairs four independently confirmed
findings while retaining the accepted decisions above:

- Dispatcher: detach a completed Future before consuming its exception so later
  ticks can replay, reconcile and claim work; bound background erasure replay to
  20 stored records per tick with a cursor retained across ticks.
- API and rights: cancellation returns metadata only for every run state and
  needs no private-storage read; retry replays owner erasure requests first.
- Storage and lifecycle: isolate replay to the current owner's hashed prefix,
  reject creation for arbitrary nonexistent targets, reuse covering retained
  deletion requests, and give later-created work a new cutoff. Legacy UUID
  manifests, indefinitely pending requests, request-before-SQL ordering and
  14-day completed retention remain supported. No schema or datastore changes.
- Miniapp: retain the selected snapshot/parse confirmation for revocation after
  result expiry, separately from a saved attestation awaiting compute submission.
  Multiple recordings still require selection and no automatic POST is added.
  Rights controls remain usable when science or processing is inactive.
- Operations: document ordinary merge-triggered rollout, asynchronous DFA replay,
  owner recovery checks and the migration graph required by rollback builds.

Focused regressions cover these boundaries with synthetic data. Full committed-head
preflight, independent Quality/Trust review, native retained-proof evidence and
Decision Review disposition are separate coordinator-owned evidence. These edits
neither activate the science contract nor claim phone drawing, gesture,
screen-reader or larger-text acceptance. Design system impact: none — existing
components and tokens cover this local implementation repair.

## DFA source and foreground clarity repair — 2026-10-02

The accepted `ddr-dfa-clarity-refresh-20261002` supersedes only the source
confirmation presentation in the experience specification above. Its digest is
`sha256:b0f6a8f5be306fb2b0f592e18c2469d5f857ebfa6f3b397939e8b360564d5a63`;
Delivery contract `wc-dfa-ux-20261002` binds classification
`sha256:e36ab7436e66e774d67c42da71c9892be286c6562c504988f577e48cda9c4d30`
and route
`sha256:c022991c4db14340a5cc592072dc27a267206da93657b4fdca8a3a5f83bf7929`.
The independent Decision Review route for that accepted design is agent-resolved.
This local implementation does not approve or independently verify itself.

| Area | Repair impact |
| --- | --- |
| Web and miniapp | Ref-stable duplicate-model Entry/记录 ordinals; one deliberate whole-recording/no-switch confirmation action; exact v1 statement in associated source disclosure; source/proof retry and foreground state retained. |
| Client freshness | Coalesced catalog validation conceals old numerical content while retaining the result frame. Full selected input, latest run identity/status/freshness/result revision/proof, current confirmations, policy and processing authority govern reuse; the candidates-only catalog revision is insufficient. Changed or unavailable metadata fails closed. Hidden/terminal polling and late replies remain fenced. |
| Explanation | Trailing 120-second windows every five seconds overlap; one interval may affect several windows. Reason counts describe affected windows and can overlap. Complete beats and interval coverage are labelled. Supported time is a time union, distinct from the valid-window fraction. Null gaps remain unbridged. |
| Translation and tests | Updated locale-only EN/zh copy and generated miniapp catalog; actual-component regressions exercise duplicates, deliberate proof creation, saved submission retry, foreground reuse/concealment, changed metadata/authority and late close replies. |
| Data, analysis, API, operations, migration | No changes. `raw120-v1`, source evidence bindings, confirmation statement version, QC, thresholds, retention and sync admission remain the accepted policies above. |

DFA remains an explicit activity analysis. Synchronization archives source
recordings; it does not enqueue DFA work. Initial eligible single-recording entry
may prepare source evidence under the existing contract. Only deliberate owner
confirmation authorizes a source proof, and only an explicit analysis/retry action
submits confirmed computation. Foreground validation and GET/poll never recompute.
The server persists completed result cache entries for at most 30 days from
completion, subject to quota eviction and invalidation; reads do not extend that
period. Source confirmation is retained separately. A saved confirmation after a
failed compute submission retries computation without another factual assertion;
expired results require explicit recalculation.

Design-system disposition: the accepted design authorizes a local DFA exception to
Checkbox + Label for this factual source confirmation only. Existing Field Lab
components, tokens and responsive sheet/native panel remain in use. This does not
change processing, legal or deletion confirmation patterns.

Engineering validation: focused actual-component suite 18/18; `web/npm run build`
(full web tests, TypeScript, Vite and public-build isolation) passed; miniapp
`npm run typecheck` with generated types/translations/legal sync and translation
coverage passed; the UI quality gate passed with explicit working-patch
`--changed-file` paths, not a committed-head preflight. Numerical backend tests
were not rerun because numerical behavior is unchanged. Independent Quality owns
acceptance and release confidence.

Rendered evidence is limited to the explicitly authorized optional synthetic
Paseo fallback, using the actual web component and a temporary in-memory fixture
at `http://localhost:5173/`. It is not portable Chrome DevTools conformance. In the
EN/light DOM interaction check (1440×900 requested through Paseo; DOM viewport dimensions were not independently asserted during this transition), a focused time control and scroll offset
300 were preserved, result height stayed 1148.24px, pending data was visually
concealed with summary accessibility suppression and a nonnumeric range status,
and coalesced focus/visibility produced exactly one metadata GET without a POST.
The source frame restored after validation. A subsequent zh/dark source disclosure DOM check revealed the exact v1 statement and caused no POST. Its actual viewport was 1280×800 despite a preceding 390×844 resize request; mobile viewport acceptance is therefore pending. Screenshot capture returned
`screenshot_no_frame` (tab had not painted); no screenshot-based visual acceptance,
contrast or full screen-reader acceptance is claimed. WeChat native screenshots
remain pending: the required non-sandbox desktop/readiness/authorization path was
not completed, and no business WeChat call was made. Component tests and typecheck
establish native code parity, not simulator or phone-rendered acceptance.

### Independent Quality findings and bounded repair

Independent Quality rejected candidate patch
`sha256:c684953d5de7663662aaf3cb7512aa51ba77af8b38dbc7ae56269f84ada3cad3`:
a source or recording choice during foreground validation could cancel the only
pending validation and leave the panel checking indefinitely; checking text
could overlap the retained source heading; a long selected duplicate label could
clip its entry ordinal. The replacement patch guards web callbacks, including a
callback retained by an already-open picker, while verification or catalog
validation is pending. Native source and recording handlers likewise reject
pending picker replies, with native pickers disabled during checking. Selection
remains intact, the current validation completes, and choices resume afterward.
Both clients reserve a separate status row; the web selected source value wraps
without a line clamp and its trigger grows with the text.

Four additional actual-component regressions cover pending source and recording
callbacks in both clients, unchanged selection and coalesced requests, validation
completion, restored usability and absence of automatic confirmation/computation.
The focused DFA, native-fixture and tabbar suite passes 37/37 (DFA component suite
22/22); native typecheck and translation coverage pass. The required replacement
web build and final working-patch checks are recorded in the replacement
Engineering handoff. No extra executor rendered or screenshot acceptance is
claimed. Fresh independent Quality owns the targeted actual-render confirmation
of these three fixes and the retained safety behavior. Its earlier fallback used
installed Python Playwright/Chromium with synthetic fixtures; the common Chrome,
native simulator, OS screen-reader and measured-contrast limitations remain.

## Automatic source branch and inline activity details — 2026-10-02

Delivery Work Contract `wc-dfa-auto-inline-20261002` binds classification
`sha256:1f80b1e4ff20a296d77cc15154af9d8826ea75e8d9726f2be624eb6292c11cff`
and deterministic route
`sha256:a45599ca884e6edfe42e642bddbf2026d027776c58081de6e35ec91f59892904`.
Independent Decision Review authorized default-OFF local implementation and
synthetic checks. This section supersedes the earlier dedicated DFA sheet,
user-facing window paging and manual-only scheduling descriptions. It preserves
v1 numerical behavior, explicit factual confirmation and the foreground selector
race repairs. Engineering does not approve source policy or scientific activation.

Accepted implementation artifact SHA-256 bindings:

| Owner | Digest |
| --- | --- |
| Product | `42f4927aa9e8d49c1ea29592e0895d14af1fa6659cdfcc8e41b6161c736957cc` |
| Architecture | `c974b95495379bfae98d12437792540ce089f2a201eb7d660b90d5d46b63c61d` |
| Design | `f8fe45dba5f6c39621f95014a0b1a4070ec41961785a02ffdefc0c39d810c04b` |
| Operations | `62d0699756071c27e838b68a84ab4bf56b00d182356c9c09e7e48fb15a9e2cfd` |
| Trust | `a57be2109884f0944e4fc1c21b75b090a4c6368cd7fbe8dd861937c4e3d5203c` |

The draft/inactive v2 scientific source decision has contract digest
`sha256:c74a05be3ece8b3d95f6ff53e5b32fc8d885f51b9a0732b75975d7bf1d8faba1`
and full parameter digest
`sha256:7085fa6e244569be475e6908576d0abfc63f957c8fdda73a52d24488b08718a3`.
Its frozen numerical parameter groups retain digest
`sha256:f36cf405cbf84aef9d04e6e52aa1600662ce0254de1b230d7372ff035ebede11`.
The generated contract and review packet remain inactive with no signatures.
Unknown external HR, unverified optical identities and local wrist diagnostics
remain unresolved; no positive optical deny mapping is invented.

| Area | Implementation impact |
| --- | --- |
| Provider/data | Actual successful ConnectIQ provider completion writes a metadata receipt in the existing sync-writer transaction. Duplicate snapshots deduplicate; history, maintenance reparse, metadata GET, TTL expiry and quota eviction do not enqueue. Native diagnostics are projection-only additions that preserve v1 evidence digests. |
| Source/analysis | Pure all-candidate source inventory requires compatible native ECG identities and transports. Automatic preparation produces a typed immutable metadata proof, then a separate proof-bound compute run. User-confirmed and metadata-inferred branches remain distinct. Numerical formulas, QC and `raw120-v1` stay unchanged. |
| API/runtime | Existing server Statsig wrapper evaluates `dfa_alpha1_auto_analysis_enabled`, failing OFF. Automatic admission, claim, execution and publication require gate and signed-active v2 policy; OFF pauses and releases the lease. Existing authenticated bounded worker/lease/quota contracts remain. Completed current automatic reads survive gate OFF. |
| Rights | Durable activity suppression and monotonic generations fence late provider receipts, retry, deletion and restore replay. Cancel/delete/withdraw stop automatic work; explicit catalog/generation-bound reauthorization makes no factual assertion. New routes remain owner-scoped and cancellation is metadata-only. Account export/delete include the new records. |
| Migration | Add metadata-proof, provider-receipt and rights-state tables plus run branch/generation columns. Preserve existing manual rows and lease fences. Proofs are immutable. Unsafe schema downgrade refuses removal of suppression; use a compatible rollback binary. |
| Web | One activity-detail sheet contains summary, inline DFA and every split. Opening/focus validation uses GET only. Full original-window plot uses elapsed time, separate timer-block lines and null gaps, range controls, zoom/pan/reset and exact-window details. Internal chunking remains bounded and revision-bound. |
| Miniapp | Registered activity-detail page owns one scroll surface and receives the full activity through EventChannel. Inline native DFA matches source/rights/range semantics, uses bounded setData chunks and retains list/tabbar state. Coordinator resolved the native page as contract-consistent. |
| Operations | Gate is declared false in every environment, with Console provisioning/readback still an Operations obligation. Runbooks cover admission, pause, rights, migration, retention and compatible rollback. No live provisioning, alert creation, release or deployment occurred. |

Executor checks: the full backend run had 3756 passes, eight failures and seven
skips. All eight failures were patch-connected: one Alembic fixture setup, two
science shipped-set/index assertions, generated native type parity, the head
assertion, and three historical plan rollback boundaries. Repairs preserve the
original pre-auto rollback assertions; a separate new-head regression proves
unsafe DFA downgrade refusal. Targeted reruns passed (141 DFA/automatic/writer/
Statsig tests, five migration regressions, three registry/parity tests, four source
proof checks, and four final lifecycle regressions; their documented skips remain).
The full backend suite was not repeated after these bounded repairs. Final web
build passed all 323 tests, TypeScript, Vite and public-build isolation; focused
client checks passed 41/41. Native typecheck, generated types/catalog/legal sync
and translation coverage passed. Canonical science generation checks passed. Fresh SQLite and PostgreSQL16 full-graph migration checks passed for the final constraints, immutable-proof trigger and unsafe-downgrade refusal.
The working UI gate explicitly includes all 33 tracked and new task-owned UI
paths; a tracked-only diff would omit new detail/plot/native files.

Actual-source synthetic Playwright/Chromium evidence is local at
`test-screenshots/ui-quality/dfa-auto-inline-20261002/`: nine screenshots,
`primary-journey.webm` and `report.json`. Desktop EN/light is 1440×900 and mobile
zh/dark is 390×844. Manual, waiting, inferred complete, user-confirmed complete,
source disclosure and zero-valid-window states rendered without page/console
errors or Vite overlay. Opening each state made zero POSTs. Zoom and reset changed
only range; foreground validation concealed numbers while preserving time-control
focus and restored the result. The final selector correction confirms visible
truthful inferred-source wording and exactly 31 reachable split rows. The earlier
zero inferred-label count came from exact text-node matching against combined
source/time-alignment text; the earlier 151-row split count included 120 DFA rows.
These were harness selectors; no product fix was needed.

## UI quality

- Impeccable: `clarify` and `harden` inline DFA within the accepted Design artifact; detector reports no findings.
- Visual review: executor inspected synthetic desktop 1440×900 EN/light and mobile 390×844 zh/dark; independent Quality acceptance pending.
- Primary journey: activity detail → inferred source and coverage → original-window plot → range/zoom/pan/reset → window details.
- Reviewer handoff: local-only — `test-screenshots/ui-quality/dfa-auto-inline-20261002/report.json`, original PNGs and `primary-journey.webm`; live synthetic URL `http://localhost:5173/`.
- States checked: manual, waiting, inferred complete, confirmed complete, foreground checking/restored, source disclosure, zero-valid windows, long recording and 31 splits; additional error/stale/rights races covered by focused component/API tests.
- Accessibility: keyboard range input, retained focus, pending numerical accessibility suppression and reduced-motion browser setting checked; OS screen-reader and measured contrast acceptance remain pending.
- Design system impact: none — existing Field Lab tokens and components cover the inline composition and local factual-confirmation exception.
- Miniapp parity: implemented and static checks passed; simulator/phone/back-navigation rendering remains pending.
- Exceptions: portable Chrome DevTools was unavailable, so the explicitly authorized installed Python Playwright/Chromium fallback used isolated synthetic fixtures. The canonical Windows Nightly installation check returned `cli_unavailable` because its CLI invocation split an unquoted `D:\Program Files...` path after a WSL UNC working-directory warning. Installer policy requires stopping before business calls; no native project window was opened, no Tencent gate was bypassed, and no native screenshot acceptance is claimed.

Fresh independent Quality and Trust review the complete frozen patch separately.
The future Product Outcome Record and Meta/Eval batch observation remain routed
obligations; executor checks do not complete them or establish release confidence.

### Independent r1 findings and serialized r2 repair

Fresh Quality and Trust required changes to frozen r1
`sha256:886b6fb17e945935802c5c28e33b7531d13b5d730af110c8061b4e757d6ccd9c`.
The coordinator resumed the same Engineering slot for one bounded repair batch.
Root explicitly accepted a durable owner restore fence inside the existing rights
boundary, subject to independent replacement-patch review.

- T1: a retained activity-deletion marker covered creation timestamps but ignored
  later reauthorization. Marker reuse now also requires the current suppressed
  rights generation. Withdrawal after reauthorization creates a new durable
  suppression generation; repeating that same withdrawal remains idempotent and
  bounded. Stale manual submissions cannot reuse the earlier generation.
- T2: owner replay only removed cutoff work and dropped SQL suppression state.
  The existing rights table now reserves the empty activity key for an immutable
  owner-erasure fence. Activity paths cannot address that key, strict bodies
  cannot override their path target and versioned activity manifests reject it.
  The private owner marker never expires; replay reconstructs the fence for a
  restored active owner and removes all that owner's DFA source/result records,
  including later-created/restored records. Per-activity generations remain
  monotonic. Owner suppression blocks catalog, admission, claim, execution,
  publication and source/result export independently of gate/science/legal
  projections. Export still accounts for scoped payload-free rights states;
  ordinary owners retain the existing complete receipt/proof/rights export.
  Missing owners cause no FK insertion. Live account deletion explicitly removes
  SQL rights rows, including when SQLite FK enforcement is OFF, and retains the
  private marker for restore replay. No new table or schema constraint is needed;
  the existing nonnullable string key and nonnegative generation constraints
  support the reserved owner row.
- T3: the source predicate filtered descriptor rows before merging native handles.
  It now merges every partial native fact before relevance and identity checks.
  Early name-only contradictions cannot vanish; manufacturer/transport/class
  plus later product-only facts can complete the same compatible ECG identity.
  The v2 evidence digest binds the entire sanitized native inventory. Existing v1
  sensor/evidence digests, separate ANT+/BLE handles, ECG registry, source policy
  bindings and numerical/QC groups remain unchanged. No optical mapping is added.
- Q1: a late native run GET could replace the private whole-window cache before
  the epoch/visibility fence. Original windows and context commit only after the
  current epoch, visibility, exact full input, source, authority, rights,
  method/contract and result/sample/overlay revision checks. Every window consumer
  requires cache bindings that match the accepted current run and authority.
  An old response after a newer foreground result cannot repopulate old values.
- Q2: native entry with multiple recordings did not select/load a matching saved
  automatic result. Entry now binds that exact validated recording unless a valid
  deliberate choice exists. Choosing its matching recording loads the saved run
  with GET only; open, focus and picker selection never submit computation.

New original regressions cover erase → reauthorize → erase with no newer run;
owner replay → genuinely later provider completion; restored newer-than-cutoff
results; non-expiring cleanup; generation-reset/reauthorization refusal; scoped
export and foreign-owner preservation; claim/execution/publication fences; absent
owner and unaddressable empty-key/body targets; live deletion with FK ON/OFF;
actual native FIT partial-name contradiction and product-only completion; old
native run and sample replies after a fresh result; multiple-input saved automatic
entry/picker selection; and cache input/proof/rights/method/authority mismatches.

One pre-existing direct `showResult` fixture was corrected to provide its real
catalog, selected input and source proof, as a displayed result must have valid
source/authority context. Its original comparator concealment and late-response
assertions remain intact; no source, authority or epoch guard was weakened.
Quality's original external actual-component reproducer
`/tmp/dfa-quality-native-races.cjs` was rerun unchanged: multiple-record entry now
loads `new` with `hasResult:true`, and the old-reply race retains alpha `0.90`
before and after the range change. Output is
`/tmp/dfa-auto-r2-original-native-repro.json`.

These are executor regression observations. Independent Quality and Trust must
review the complete r2 patch and rerun the original findings before acceptance.
The web visual composition did not change in this repair; the earlier synthetic
web captures remain applicable to that composition. Native behavior changed and
is covered by the actual-component reproducers and typecheck; actual WeChat
rendering remains unavailable under the previously documented installer block.
No extra native business call, live gate change, science signature or release
claim was made.

Final r2 executor checks passed: 33 automatic/source/rights/migration tests;
95 DFA/account-delete/export compatibility tests (five documented skips);
PostgreSQL lease/read-timeout regression; 46 focused client tests; full web build
with 328 tests, TypeScript, Vite and public-build isolation; native generated
sync/i18n/typecheck; canonical science generation and unchanged frozen numerical
group digest; explicit all-33-owned-UI-path working gate and `git diff --check`.
The two live-delete FK ON/OFF regressions are included in the final 33-test run.
No second full backend suite or new rendered-native acceptance is claimed.

### Independent r2 source findings and serialized r3 repair

Fresh r2 Trust confirmed the deletion/owner-restore repairs and required two
remaining source fixes against patch
`sha256:a9ff3723c88aa592fcc20c685564233b35c7e31eb2452d49b08f1e673e960eb4`.
The same Engineering slot implements the root-authorized complete-native boundary.
Genuine v1 sensor/evidence representation remains unchanged; its legacy digest
cannot establish current native integrity or override actual contradictions.

S1: complete native identity integrity now guards both branches before building a
recording and guards manual submission, confirmation, retry, execution,
conditional publication and current catalog/window/overview/context reads. Native
name-only contradictions remain visible after later descriptor enrichment. A
historical genuine owner statement and unchanged legacy sensor digest cannot make
such a recording current. S2: HR relevance is sticky across every original native
descriptor and accumulated partial facts. A prior unknown ANT+ HR descriptor does
not disappear when its later transport/class is overwritten. Unknown or ambiguous
transport/class still permits genuine manual clarification when the existing ECG
prerequisite is present; it cannot authorize automatic inference. Coherent partial
native identities and separate supported ANT+/BLE handles remain supported.

Authorized current source checks use exact retained owner/input/SHA and a native
message23-only projection: no RR/sample projection, numerical work or provider
call. Existing64MiB/250000-frame limits remain; cooperative inspection shares the
existing30s read deadline. A 128-entry summary-only volatile cache binds full
owner/account/activity/snapshot/SHA/parse/parser and implementation identity. It
stores only outcome/digest summaries, never FIT, RR, samples or device inventory.
Owner/rights/current input and historical proof checks precede reuse. Errors close
current processing/display; this cache supplies no export assurance or retention
refresh.

Observed hard native contradiction uses the existing payload-free private
snapshot/source-changed protocol before clearing dependent SQL numbers. All
records for that owner's immutable snapshot receive generation/lease fences.
Durable failure retains the payload and an enforceable SQL negative; when no run
exists, a terminal zero-payload metadata fact in the existing run table preserves
the pending observation. It never queues computation. Pending negatives survive
HTTP rollback, process-cache loss, TTL/quota cleanup and fresh-session rights
export. Bounded dispatcher/owner preflights reconcile durability without FIT
hydration, then erase source dependents. Completed source markers preserve the
accepted14-day restore window without read-refresh. Old backups cannot restore
numbers/proofs before replay; current gates prevent later proof or publication
for the contradicted input. Unrelated snapshots retain their contents. Only an
actual native observation creates this negative discriminator; generic proof-
mismatch diagnostics do not invalidate an otherwise coherent snapshot.

Two fresh independent export Decision Review routes resolved contract consistency
as agent-resolved. Subjects are
`/tmp/dfa-auto-inline-export-boundary-checkpoint-20261002-r3.md`
(`sha256:cff779ff32d45a3d5e707f72cb2ebb89f83ca0197176eeb1dc75643b429b42f4`)
and `/tmp/dfa-auto-inline-export-disclosure-boundary-20261002-r3.md`
(`sha256:5804832657816f41c85c66a1348d386b30c68157611eda364b89f8ca93c78a33`).
UNKNOWN retained-number portability remains metadata-only under exact historical
input/proof/rights checks. Export preserves historical assurance and adds bounded
machine-only `current_native_integrity` with state `UNKNOWN`, reason
`not_inspected_for_rights_export` and retained exact input bindings. It describes
only the assurance supplied by this export, independently of record/method
freshness; it grants no current processing/display permission. Known negatives
are withheld before UNKNOWN. Export calls no native/FIT/RR/sample/provider reader,
computation or renewed computational authority. Serialized shape changed and was
checked through JSON encoding and affected export tests; external-consumer
compatibility beyond those checks is unmeasured. No new UI copy/interaction or
source/science policy was introduced.

Executor evidence:141 affected source/manual/automatic lifecycle tests passed,
with five PostgreSQL cases deselected for the SQLite batch;18 latest original,
durability/restore/rollback/cache/late-publication regressions passed; five
export/account-delete compatibility checks,46 client checks and the PostgreSQL
lease/read-timeout regression passed. Canonical science generators remain current;
all frozen numerical groups and digest remain unchanged, with v2 draft/inactive.
Two initial legitimate manual-retry regressions required binding the explicitly
reauthorized generation only after both expected generations and authority pass;
stale/rejected retries cannot rebind or enqueue. Account deletion now flushes and
synchronizes removal of the transient rights fence for autoflush-disabled sessions.
The legacy source fixtures were corrected to select the exact contradictory FIT
SHA rather than the store's older coherent archive; original assertions were not
weakened. Genuine historical confirmations are created through the original
statement endpoint under a temporary pre-r3 integrity-gap fixture, then current
checks inspect the unchanged exact native FIT.

The r3 UI composition is unchanged from r2. Existing rendered evidence remains
historical; no new r3 rendered acceptance is claimed. Native simulator/device/OS
reader/contrast and the earlier unattributed browser404 remain recorded limits.
Final exact-patch Quality and Trust review, Operations release and future outcome
observations remain separate. No second full backend run, activation, signature,
Console change, commit, push, PR or deployment occurred.

### Independent r3 Q3/T3 findings and minimal r4 correction

Fresh independent Quality/Trust required changes to r3
`sha256:c261cd42166192b64e249f292182c569b0289acc209729adfe61846d22abe85c`.
The original source/owner/deletion fixes passed independently; this correction
changes only private bookkeeping isolation and retry validation binding.

Q3: the fallback negative fact previously flushed with queued defaults before its
terminal state was assigned. It now initializes unavailable/stale/private-native-
bookkeeping/source-contradiction fields before add or autoflush. A distinct private
progress discriminator is excluded from latest analysis, owned/public metadata,
exported runs, claim/execution, active admission and quota/eviction accounting.
Pending bookkeeping is retained across TTL cleanup until metadata-only durable
reconciliation/erasure completes. It has zero payload/reservation and no lease;
it never participates in the active-owner unique constraint. The existing table
and scientific method/registry remain unchanged.

T3: correct-generation retry previously assigned ORM run authority tentatively;
the independent native observer could commit it while rejecting the retry.
Validation now uses an immutable effective-generation context after both expected
generations and owner/processing authority pass. Stored run authority is assigned
only after source/current checks and reservation accept the retry. The observer
can still commit its independent native negative/generation fence; rejection does
not bind the old run to the new global reauthorization intent or enqueue work.

Exact regressions use native SHA
`80e26bb6174ab51996d5ff0e953afc4b6aa1ece969716bb3dbde932e4955d10b`,
genuine historical endpoint-issued proof and zero remaining same-snapshot runs.
With an unrelated queued or running owner job and private-journal failure, the
catalog observation inserts its private fact directly terminal, exposes no latest
analysis, preserves the other job/lease/accounting, survives rollback/fresh-session
and expired cleanup, and fails closed on next GET/export without FIT hydration.
Recovery erases the fact/proof while leaving the unrelated job unchanged.
The retry regression starts with a genuinely confirmed queued compute run,
cancels it, reauthorizes global generation2, supplies both correct expected
generations and observes native contradiction during journal failure. After409
and rollback, a fresh session retains stored run rights generation0 plus the
independent pending negative and zero queued work. Valid reauthorized retries
continue to pass. Test setup uses a rolled-back terminal-state quota probe rather
than attempting reservation while an unrelated owner job remains active.

Executor checks: five original Q3/T3/positive-retry cases and all51 existing
automatic/source/durable tests pass; affected export/account compatibility,
canonical inactive science/numerical parity, complete diff and owned UI gate are
recorded in the final r4 handoff. No broad full-suite/build/browser repetition or
new rendered acceptance is claimed. UI files, all source classification/QC/math,
export disclosure semantics, inactive science/default-OFF gate and prior native/
reader/contrast/browser404 limitations remain unchanged. Fresh exact-r4 independent
Quality/Trust verification is still required.
