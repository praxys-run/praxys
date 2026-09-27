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

Release Evidence: **not deployed; science contract inactive**. No runtime activation
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
