# Labs environmental-response V1 contract

Status: **accepted implementation contract** for issue #590. This document
authorizes only the bounded implementation described below; the feature has
not shipped.

## Product purpose

The first Praxys Labs experiment may help any explicitly opted-in user explore
whether
heart rate in eligible past runs varied with the Stull psychrometric wet-bulb
proxy at comparable recorded running power.

The experiment is retrospective and descriptive. It is not a future-run
forecast, personal physiological coefficient, performance correction,
heat-adaptation score, training prescription, or heat-safety assessment.

## Proposed first-user experience

1. Explain the purpose, adult evidence boundary, required data, limitations,
   persistence, withdrawal, and deletion behavior before opt-in.
2. Record the experiment ID, consent-text version, and consent time.
3. Compute from a complete owner-scoped snapshot using one verified
   same-provider, same-device/algorithm-era SAMPLE-derived power regime and
   heart-rate segments.
4. Show the fitted curve only when the prespecified model, provenance, central
   environmental domain, five support bins, reference-power overlap,
   uncertainty, sensitivity, and leave-one-activity-out gates pass.
5. Show activity and segment counts, observed environmental range, uncertainty,
   model version, and chronological prediction status.
6. If association stability passes and prediction is evaluated but does not
   pass, label the result
   **Historical association; not predictively validated**.
7. If prediction is unavailable or unevaluable, withhold the fitted line.
8. Let the user withdraw and delete the derived result.

## Curve meaning

The chart answers:

> In eligible past runs, how did modeled heart rate vary across estimated
> temperature-and-humidity conditions at comparable recorded power?

It does not answer:

- What will heart rate be in the next run?
- How many beats per minute does heat cause?
- How much slower should the athlete run?
- Is the athlete adapted, hydrated, or safe?
- What would the activity have been in different weather?

The proposed X-axis label is **Stull psychrometric wet-bulb proxy (°C)**.
Psychrometric wet bulb is not apparent temperature, natural wet bulb, outdoor
WBGT, or a direct body measurement.

## Display states

| State | Meaning | Display |
|---|---|---|
| Not enrolled | No experiment processing | Consent explanation |
| Processing | Aggregate result is being computed | Progress and cancellation |
| Insufficient data | Required activities, segments, spread, overlap, or provenance are absent | Coverage explanation; no line |
| Unstable association | Direction or uncertainty is not robust | Coverage and limitation explanation; no fitted line |
| Historical association only | All descriptive gates pass; evaluated prediction does not pass | Curve plus prominent non-predictive label |
| Prediction unavailable | Predictive controls could not be evaluated | Coverage explanation; no fitted line |
| Predictively validated | Reserved for a future decision | Not available in V1 |
| Stale | Source revision or model version changed | Recompute prompt; hide current claim |
| Withdrawn | Consent and derived result deleted | Enrollment explanation |

## Power eligibility

V1 initially supports:

- continuous Stryd samples with Stryd-aligned critical power;

Garmin native **wrist-only** continuous power is an explicit candidate regime,
not currently qualified. A standard Garmin power field is not enough to prove
wrist-only origin; Smart/accessory-ambiguous activities remain ineligible. The
Garmin path must add continuous sample power plus per-activity source, device,
and algorithm/firmware continuity, then pass separate repeatability,
chronological, and human science review before it can produce a curve.

When more than one provider regime is eventually qualified, Praxys produces
separate labeled results. It never pools watts or coefficients and never picks
the provider that produces the strongest curve.

Pace and grade-adjusted pace are excluded from V1. Equal pace does not establish
equal effort across wind, surface, fatigue, heat-related pacing, and grade, and
no reviewed evidence defines a defensible `within X%` elevation threshold.

## Availability explanations

Every non-result state returns structured, privacy-safe diagnostics:

- stable reason code and category;
- plain-language user explanation;
- observed aggregate value and required guardrail when applicable;
- whether the user can act on it;
- suggested next action;
- analysis stage, provider regime, model version, and a support correlation ID.

The initial reason taxonomy includes:

- incomplete export or stale source revision;
- insufficient eligible activities, segments, environmental spread, holdout,
  curve-bin support, or reference-power overlap;
- missing continuous sample power;
- missing continuous heart-rate samples;
- missing activity temperature;
- missing activity relative humidity;
- missing provider-aligned critical power;
- unsupported, mixed, or unverified power provenance;
- Garmin wrist-only source not verified;
- device or algorithm era changed;
- critical-power provider mismatch;
- insufficient sample coverage;
- unstable bootstrap, sensitivity, or leave-one-activity-out result;
- prediction unavailable;
- adult eligibility not confirmed;
- processing failure.

User messages never include activity IDs, dates, routes, or per-activity values.
Authenticated diagnostic logs may include stage names, aggregate counts,
provider labels, model version, and the correlation ID, but retain the same
identity exclusions. A processing failure is shown as an error with the support
ID rather than being converted into an insufficient-data result.

## Privacy contract

V1 is personal-only:

- opt-in is separate from normal Praxys processing;
- no cross-user contribution or benchmarking;
- participation is available to all users only through explicit opt-in;
- analysis requires an explicit 18-plus attestation because the reviewed
  evidence is adult-only; no birth date is collected;
- connector-provided historical environmental fields only; no weather or route
  enrichment;
- no sale, disclosure, advertising use, or unrelated model training;
- persist only aggregate curve points, uncertainty, eligibility counts, gate
  statuses, experiment/model versions, source revision, and timestamps;
- do not persist activity IDs, dates, routes, precise GPS, sample rows, or
  per-activity research rows in the Labs result;
- keep exports and per-activity details out of logs, analytics, traces, and
  client payloads;
- put only owner ID, experiment ID, model version, and source revision in queue
  payloads;
- keep raw exports and research rows only in worker memory or encrypted
  temporary storage that expires within 24 hours;
- do not retain raw exports or research rows in caches;
- withdrawal deletes experiment consent and derived results, while underlying
  account activities remain governed by ordinary account controls;
- cancellation removes queued work, and running work must re-check consent
  before persisting;
- active deletion is immediate; encrypted production backups expire within the
  existing 14-day PostgreSQL retention window and restored systems must reapply
  deletion tombstones;
- rejoining requires new consent and recomputation.

Optional cohort contribution remains a separate decision in #591.

## Approval boundary

The governing records are:

- `evidence-personal-environment-response-v1` — accepted;
- `sdr-environmental-performance-v2` — accepted.

`sdr-environmental-performance-v1` is superseded. Human approval was recorded
from `github:dddtc2005` after review of PR #594 on 2026-08-08.
