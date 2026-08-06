# Heat-response validation pipeline

Issue #523 adds a research-only, offline analysis of the private
`activity-research-dataset-v1` export. It advances only the personal-response
validation portion of #444. It does not change accepted science records,
product behavior, API responses, or UI.

## Boundary

The accepted `sdr-environmental-performance-v1` still permits qualitative,
retrospective connector environmental context with explicit provenance. That
separate context is not a personal correction.

This pipeline cannot authorize a user-facing personal estimate. A real,
consented private-athlete run, human science review, and an accepted
superseding SDR with matched-sample and environmental-spread rules are still
required before API or UI productization.

## Input and privacy

Export `GET /api/analysis/research-dataset` to a private local JSON file, then
run:

```powershell
python scripts\validate_heat_response.py --input private-dataset.json
python scripts\validate_heat_response.py --input private-dataset.json --format markdown
python scripts\validate_heat_response.py --input private-dataset.json --format markdown --output heat-report.md
```

The script never fetches data. By default it writes only an aggregate report
to stdout. `--output` is the only report-file write. The **input contains
private activity IDs and dates** needed for duplicate detection and
chronological partitioning. The **report excludes activity IDs, dates, and
activity records**, and the CLI does not log raw records.

`dataset_hash` is required even for an empty export. Before analysis, the
validator recomputes the API's canonical dataset-core hash over every
top-level key except `dataset_hash` and `generated_at`, using JSON
`sort_keys=True`, separators `(",", ":")`, `ensure_ascii=True`, and the
`sha256:`-prefixed SHA-256 digest. Missing or stale hashes are rejected. A
legitimate API response with `records=[]`, `total=0`, and
`model_versions.heat_adaptation=[]` produces a normal privacy-safe withheld
report with insufficiency gates rather than an input error.

Pagination metadata is required. `total`, `limit`, and `offset` must be JSON
integers; `total` and `offset` must be non-negative, and `limit` must match the
API range of 1–50. The record count must equal
`min(limit, max(total - offset, 0))`, so a truncated first page is rejected
rather than analyzed as complete. Only exactly `offset=0` passes the first-page
gate. A valid nonzero page is reported unavailable because it would omit the
latest activities needed for the chronological holdout. The report states the
analyzed page's counts and does not imply that it covers the athlete's complete
history. Any pagination-valid page with zero records, including
`offset >= total`, may carry an empty heat-adaptation version manifest and
produces normal withheld gates rather than an input error.

## Eligible observations

`analysis/heat_response_validation.py` accepts only SAMPLE-derived stable
segments. It excludes:

- duplicate records after canonicalizing activity identity as
  `source + activity_id`;
- split fallback;
- invalid or unsupported connector environment provenance, including any
  environment context not governed by
  `sdr-environmental-performance-v1`;
- any wet-bulb value not labeled with the versioned Stull psychrometric
  method (a proxy, **not WBGT**);
- missing or invalid segment source/stability, mean power, mean %CP, mean HR,
  HR slope, HR-at-power decoupling, duration, start offset, sample coverage,
  power CV, power provider, or HR provider; `mixed`, `unknown`, and
  `unverified` provider sentinels can never satisfy provider consistency;
- unavailable, non-positive, undated, same-day/future, or
  provenance-incompatible pre-activity critical power, including any
  selection other than `latest_strictly_before_activity_date`;
- segment mean %CP that does not agree with mean watts divided by the dated
  critical power within the configured tolerance;
- provider-mismatch reason codes;
- unstable, low-coverage, short, warmup, or out-of-band segments.

Activity `avg_power` is never used.

Power-provider and HR-provider provenance is retained on each internal
eligible row. The report exposes only aggregate provider-combination labels
with activity and segment counts. A decision-required consistency gate fails
when more than one power/HR provider regime is present, so mixed sensor
regimes cannot reach `eligible_for_science_review`; a uniformly mixed or
otherwise unverified sentinel regime also fails rather than appearing
consistent. Environmental connector source is likewise retained internally
and reported only as aggregate source/activity/segment counts. A separate
decision-required gate requires one supported environmental connector source
for this bounded unstratified validation, so mixed Garmin/Coros/Stryd
environment sources withhold. No provider or source diagnostic includes
activity IDs or dates.

## Research model

The primary model is a deterministic within-athlete ridge regression for
steady-segment mean HR. Required predictors are:

- Stull psychrometric wet-bulb proxy;
- continuous mean %CP;
- elapsed/start offset;
- segment duration.

Coarse terrain, pre-activity TSB, and dated recovery readiness are selected
using **training rows only**, and only when training values are complete and
variable. A selected optional predictor that is missing in held-out rows
causes those evaluation rows to be excluded with aggregate counts and reason
codes; holdout sufficiency is checked again after exclusion. Missing values
are never silently imputed.

Recovery has only a calendar date, not a true observation timestamp. The
pipeline therefore accepts readiness only when the recovery source is a
supported non-empty connector, selection is exactly
`latest_on_or_before_activity_date`, the reason-code list is empty, and the
recovery date is strictly before the activity date and no older than the
configurable maximum lag (default: the previous calendar day only). Same-day,
stale, unsupported, or provenance-qualified recovery is not silently carried
forward or imputed. Aggregate dated, usable, stale, missing, source, lag-range,
coverage, and provenance-reason values are reported. If otherwise usable
training rows contain multiple recovery sources, readiness is omitted and an
informational provenance-consistency gate reports the aggregate mix. Recovery
completeness and source consistency remain non-decision gates: readiness may
be omitted from the model rather than blocking the whole research analysis.

The primary model never includes qualitative heat-adaptation stage and never
uses it to modify the acute heat slope. When every eligible activity has
correctly versioned previous-day context and both evidence groups have enough
training activities, a separate secondary interaction model is reported only
as an exploratory heterogeneity sensitivity. It cannot improve the #444
recommendation and must not be interpreted as an adaptation benefit or acute
heat discount. Its unavailability remains explicit.

The latest activities form a chronological activity-level holdout, so segments
from one activity cannot cross train/test. Reports include activity/segment
counts, actual train/test identity overlap, MAE/RMSE, the heat coefficient,
fixed-seed activity-cluster bootstrap percentile intervals, and coefficient
stability. The bootstrap interval is descriptive sensitivity only, not a
coverage guarantee. It is reported only after the configurable minimum number
and fraction of valid activity-cluster resamples is reached. Bootstrap and
permutation cluster order uses chronological date, deterministic observation
content, and source-record order rather than opaque activity ID text; changing
IDs alone does not change the aggregate report. Canonical `source +
activity_id` identity is still used to detect duplicate leakage.

After optional-predictor filtering, the evaluated holdout must also meet a
separate configurable environmental-spread estimate. This decision-required
gate reports candidate and evaluated holdout spread explicitly and withholds
science-review eligibility when the filtered holdout lacks contrast.

## Diagnostics and gates

Sensitivity analyses vary:

- %CP eligibility band;
- warmup/start-offset exclusion;
- minimum segment duration;
- wet bulb versus temperature-only heat representation;
- lower and higher critical-power assumptions (default: ±5%).

The negative control builds a deterministic fixed-seed distribution from
configurable repeated activity-level permutations, separately within train
and test. It requires a configurable minimum valid count and fraction. The
decision gate compares the observed holdout MAE margin and absolute heat
coefficient against the aggregate permutation distribution using predeclared,
estimate-labeled support fractions. It is descriptive falsification only, not
a causal test or personal correction. Permutation-method reference: Ernst,
<https://doi.org/10.1214/088342304000000396>.

Directional sign agreement includes temperature-only and every other
available heat representation. Only coefficient-magnitude ranges exclude
representations whose units or scales are not comparable to wet-bulb °C.

Sensitivity coverage is itself decision-required. The report counts all
planned variants, unavailable variant names, the available fraction, and the
effective configurable minimum count/fraction. Coefficient stability is
reported inconclusive and science-review eligibility is withheld when too few
planned variants are available; unavailable permissive variants are never
silently dropped from the denominator. The coefficient-stability gate is
`fail` only for evaluated instability after sufficient bootstrap and
sensitivity statistics exist; missing bootstrap or required sensitivity
coverage remains `unavailable`.

Eligibility for science review also requires configurable research
falsification choices: gross chronological-holdout error must stay below its
configured ceiling, and the primary model must be at least non-worse than (or
beat by the configured margin) both an otherwise-identical no-heat model and
the configured fraction of the activity-level permutation distribution, while
its absolute heat coefficient must be at least as extreme as the configured
fraction of permuted coefficients. Evaluated contradictions are reported as
`fail`; `unavailable` is reserved for controls that could not be evaluated.
Either status withholds the recommendation. These are model-performance
falsification choices, not physiological claims.

Minimum observations, segments, holdout size, training and evaluated-holdout
environmental spread, HR/HR slope/decoupling bounds, %CP consistency tolerance,
falsification margins and support fractions, bootstrap, permutation and
sensitivity coverage, coefficient-stability criteria, provider consistency,
and regularization settings are configurable **research estimates or method
choices**, not accepted product gates. Heat-adaptation availability and dated
recovery are informational. The only recommendations are:

- `withhold_personal_estimate`
- `eligible_for_science_review`

`eligible_for_science_review` means the aggregate analysis is ready for human
review. It does not mean validation succeeded and never means `ship`.

Ridge implementation: Hoerl and Kennard,
<https://doi.org/10.1080/00401706.1970.10488634>. Activity-cluster bootstrap
method reference: Davison and Hinkley,
<https://doi.org/10.1017/CBO9780511802843>.

## Validation

```powershell
python -m pytest tests\test_heat_response_validation.py tests\test_validate_heat_response_script.py
```

Tests use synthetic, non-personal records only.
