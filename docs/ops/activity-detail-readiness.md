# Assess activity-detail release readiness

> **Summary:** Record the authorized activity-detail release handoff, local evidence and pending live verification; not yet deployed.
> **Use when:** Reviewing activity-detail resource costs, activity identifiers in telemetry, or the remaining release gates.

## Prerequisites

- Existing approved A report experience and readiness contract
  `sha256:2cf83f88e3cc213d3040ea35af808559830141aa77ce1c40ec161a5607c4792f`.
- Independent Decision Review assigned `agent-resolved` only for local
  existing-boundary conformance. Independent local Quality, Trust and Operations
  assessments are complete; no accepted production SLO or Release Evidence follows.
- The completed readiness pass used synthetic local data. The release handoff
  below records subsequent user authorization; parent coordinates execution and
  independent verification. This documentation pass performs no live actions.

## Operations release handoff — 2026-09-29

**Status: authorized / not yet deployed.** The user's exact release instruction
on 2026-09-29 is: “没事，你就直接上线吧。回头我再测试这部分”. This authorizes
the existing approved A report release with phone testing afterwards. It does
not establish successful deployment, native rendering, production capacity or
production log minimization.

The active `/tmp/activity-detail-release-contract.json` binds classification
`sha256:b1c479b28194ddd656ede4fa7c0487da7647c08efccd6c75718ecf3825beb311`
and route
`sha256:f1a3b1563d51fa95d9d7c524f3ab1ba006a84db47a5abce4a627f062ced35a18`:
Runtime primary, Delivery nested, Operations lead, Trust contributor,
Operations/Engineering executors, independent Quality verifier and required
Decision Review. The readiness contract above remains prior evidence.

Operations records the existing authorized choice: release through the supported
repository lanes and complete deferred phone checks afterwards. Waiting for
phone evidence was the earlier alternative; the user has resolved that timing
choice. No new product, privacy, configuration, capacity or SLO decision is
proposed. This Operations-owned handoff does not assign its own review route or
accept another role's artifact.

### Release plan and parent responsibilities

1. Parent delegates Engineering packaging, full preflight, PR, required checks
   and protected-main merge. Parent reports `main` at `994d4ded`, with only the
   web lockfile newer than workspace HEAD `394a0778`; Engineering must reconcile
   that delta and bind the final source SHA and applicable evidence before
   release. Prior local passes below are not a full preflight of that future SHA.
2. Parent executes/observes `deploy-backend.yml` and
   `deploy-frontend-appservice.yml` through protected `main`, following
   [deploy.md](deploy.md). Deploy and verify the API before declaring the new
   Web experience usable. Preserve required checks, branch/environment protection
   and workflow configuration gates. Existing EdgeOne native Git delivery is a
   separate provider result; this task introduces no China launch, DNS or
   provider-gate override.
3. Miniapp uses `miniapp-publish.yml`: protected-main robot 5 development upload,
   or robot 1 candidate upload from a `miniapp-*` tag reachable from protected
   `main`. Record which lane and candidate version ran. Provider promotion to
   trial, review submission and publication remain manual; upload success is
   not publication. Preserve Tencent login/authorization gates.
4. Parent returns this handoff and the final candidate evidence to independent
   Decision Review. Recognize the quoted existing human release authorization;
   do not request it again or manufacture a new approval. Review contract/scope
   consistency and retained branch/provider gates without reopening A or a broad
   scan. Operations does not select the route. Missing native evidence remains
   an explicitly deferred check, not a new approval blocker.

### Release Evidence — pending live execution

- **Parent-reported pre-release observation:** API version `059c8f1`, health and
  readiness healthy, all switches normal. This role has not repeated the read;
  it is the old live baseline, not evidence of this release.
- **Prior local baseline:** 103 backend tests, nine focused browser telemetry
  tests, full 319-test Web build, Miniapp typecheck and bounded independent
  Trust/Quality/Operations passes are recorded below and in the impact map.
  Historical static adapter conformance is not a new run or measured parity.
- **TODO(parent/Operations):** record merged full SHA, workflow run URLs,
  completion times and per-surface results; read back API version/source SHA,
  health/readiness, frontend health and deployed SHA against the actual artifact.
  Verify preserved China/Miniapp/AI emergency switches and feedback publication
  restoration against the pre-release state, using workflow summaries.
- **TODO(independent Quality, parent-coordinated):** record live authenticated
  history/detail smoke, owner/demo isolation and `private, no-store` responses
  using an authorized account; do not publish tokens or activity identifiers.
- **TODO(Operations):** observe PostgreSQL latency, errors, memory/headroom and
  effective platform/proxy/Azure log minimization and 30-day retention within
  authorized access. Local SQLite measurements and memory exporters cannot
  certify these. No production SLO or capacity pass is claimed.
- **TODO(user/Quality, after release):** iPhone Skyline Canvas curves, dual axes,
  gaps, touch selection/drag/zoom/split navigation and VoiceOver. Installed
  DevTools cannot supply this evidence. Keep the result unverified until tested.

Record failures or unavailable observations per surface; never relabel them as
success. Cooperative trial status is **baseline / unenrolled** because the task
key is missing; no new trial entry or cohort-success claim is made.

## Steps

### Engineering packaging evidence — 2026-09-29

The parent reports the previous main Miniapp upload failed in GitHub run
`36518568792` with provider error `80051`: source package `2208 KB` exceeded
the `2 MB` limit. The release packaging fix in
`miniapp/scripts/sync-i18n.cjs` omits English catalog entries whose value is
already their key, preserving prototype-reserved keys where inherited lookup
would change the fallback. The runtime's existing `I18N_EXTRA` precedence and
`catalog[key] ?? key` fallback remain unchanged.

Measured generated TypeScript size for the same current PO inputs:
**528,204 → 261,112 UTF-8 bytes**, saving **267,092 bytes**. English goes from
3,028 explicit entries to one non-identity translation; all 3,028 Chinese
entries remain. These are source-file measurements, not a provider package
measurement or a claim that the next upload fits. No assets, routes, features
or subpackages were removed or rearranged.

Engineering's four `web/tests/miniapp-i18n.test.mjs` regression tests pass:
the real translation runtime resolves every current key and named/positional
placeholder identically, including Miniapp override precedence, missing and
unsupported messages, locale fallback and prototype-sensitive keys.
`npm --prefix miniapp run check-i18n` passes without detector changes; Chinese
coverage, structure, glossary and drift checks remain intact. The existing
rendered experience and phone deferral above still apply.

The final committed source SHA, complete preflight result and log location are
bound in the release PR and Engineering handoff after isolated-worktree checks.
Parent coordinates fresh independent Quality for this packaging delta and must
record the actual supported Miniapp upload result and provider package size.
Only a successful provider upload establishes package acceptance; it does not
establish native rendering, promotion or publication.

### Local checks

1. Run the focused regression suite with the interpreter containing dependencies:

   ```bash
   PYTHON_DOTENV_DISABLED=1 /usr/bin/python3 -m pytest tests/test_activity_detail_streaming.py tests/test_activity_analysis_api.py tests/test_activity_telemetry.py tests/test_telemetry.py -q
   npm --prefix web run build
   /usr/bin/python3 scripts/check_agent_runtime_parity.py
   git diff --check
   ```

2. Inspect `tests/fixtures/activity-detail/streaming/README.md` for original-module
   provenance. Window count and `yield_per(512)` share one owner-scoped statement;
   the application retains bucket candidates/segment state instead of raw sample
   arrays. Kilometer output and source provenance may still grow with required
   output. Database window execution, scanning and CPU remain input-dependent.

3. Review the existing synthetic benchmark evidence. The unchanged local harness
   `/tmp/praxys_activity_density_benchmark.py` measures TestClient/SQLite,
   14 fields and 72 km, first single then two concurrent requests in one process.
   `/tmp/activity-detail-capacity-run.py` varies only duration/sample count and
   swaps the original module for baseline runs. Longer fixtures keep 72 km;
   these are resource probes, not physiological observations. All returned the
   full raw count, with identical display counts before/after: 1,945 / 1,974 / 1,910.

   | Samples | Implementation | Single seconds | Dual seconds | Peak RSS single / dual MiB |
   |---:|---|---:|---|---:|
   | 43,201 | Baseline | 2.51 | 2.62 / 3.76 | 297 / 356 |
   | 43,201 | Streaming (final source) | 1.62 | 3.60 / 3.63 | 234 / 283 |
   | 86,401 | Baseline | 3.10 | 6.06 / 7.41 | 398 / 560 |
   | 86,401 | Streaming (final source) | 3.76 | 6.38 / 6.24 | 265 / 366 |
   | 172,801 | Baseline | 8.73 | 10.68 / 15.33 | 576 / 814 |
   | 172,801 | Streaming (final source) | 5.81 | 14.53 / 14.71 | 304 / 476 |

   Independent Quality ran each duration once, sequentially, against final source.
   Memory and maximum concurrent latency improve against baseline at all three
   sizes in this run; **24-hour single latency worsens** (3.10 → 3.76 seconds).
   All requests returned 200 with complete sample counts and unchanged display
   counts. One SQLite run per size establishes neither statistical improvement
   nor production capacity; RSS still grows and does not establish constant
   whole-process memory.
   Final logs: `/tmp/activity-detail-quality-final-capacity-43200.log`,
   `/tmp/activity-detail-quality-final-capacity-86400.log`, and
   `/tmp/activity-detail-quality-final-capacity-172800.log`.
   Baselines remain unchanged. Historical pre-final-source results and the
   superseded 24/48-hour concurrent-regression inference are archived in
   `/tmp/activity-detail-capacity-after.log` and
   `/tmp/activity-detail-capacity-{baseline,streaming}-{86400,172800}.log`;
   the 12-hour baseline is `/tmp/activity-detail-capacity-before.log`.
   Earlier 1.34-second reports are historical observations, not this baseline or
   current acceptance evidence; the earlier 314-web/27-API counts likewise
   describe the historical implementation pass.

4. Treat proposed 43,201-point budgets (single ≤1.5 s, maximum dual ≤3.5 s,
   process peak ≤300/375 MiB respectively) as **draft local regression thresholds,
   not accepted production SLOs**. Final 12-hour single/maximum-dual latency of
   1.62/3.63 seconds exceeds both proposed latency thresholds. Local Operations
   evidence gaps are filled; production resource budgets and exact deployed-artifact
   PostgreSQL capacity/headroom remain unverified before release. No local
   PostgreSQL binary or Docker socket is available; that evidence is absent.

5. Review telemetry minimization evidence. Browser initialization retains China
   acknowledgement and exception restrictions and applies activity templates in
   both regions, including method-prefixed dependency names, URL/data/target,
   referrers, properties and SDK operation names. Local tests exercise the actual
   SDK with an in-memory channel, plus registered initializer envelopes; no
   browser export goes to Azure. Request URLs/navigation, timing, status and
   correlation remain intact.

6. `tests/test_activity_telemetry.py` uses the installed Azure configure API with
   trace/log exporters replaced by memory collectors, metrics/live counters
   disabled in the harness, synthetic connection metadata and loopback Uvicorn.
   The old configuration reproduces identifier emission; the corrected
   `api/main.py` / `api/activity_telemetry.py` setup removes it from all captured
   spans and access/exported logs for 200/401/404/405/500 and encoded/malformed
   paths. The hook does not mutate ASGI scope. The installed Azure distro ignores
   hooks inside `instrumentation_options`; explicit FastAPI instrumentation is
   used after disabling only its distro auto-registration. Existing valid detail
   responses retain owner isolation and `private, no-store`, including errors.

## Verify

- Final executor run: 103 backend tests, nine focused browser telemetry tests,
  and the full web build (319 tests, TypeScript, Vite/PWA and public artifact
  checks) pass. Static adapter conformance and patch whitespace checks pass.
  Logs: `/tmp/activity-detail-final-backend.log`,
  `/tmp/activity-detail-web-telemetry.log`, `/tmp/activity-detail-web-build.log`.
- Independent Trust and Quality reviewed all 14 entries of snapshot
  `sha256:95103de2ddc889e4f4a3437098acb4ddea549cb1a2636b9c8020ce3a908e4ed9`.
  Quality independently passed 103 backend and nine focused web tests, 12 complete
  baseline response comparisons, 2,000 kilometer and 10 display differential cases.
  No additional functional findings. Its earlier concurrent-regression inference
  is superseded by the final-source measurements above; production acceptance
  remains outside this local assessment.
  Reports: `/tmp/activity-detail-{trust,quality}-review.md`.
- Trust initially withheld its local pass for accepted browser aliases `/HISTORY/…` and
  `/%68istory/…` bypassing the literal prefix. The narrow follow-up safely decodes
  a matching candidate once, matches static prefixes case-insensitively, emits
  canonical lowercase templates, tolerates malformed escapes and returns
  unmatched values unchanged. Navigation, requests and streaming stay unchanged.
  Existing pure, registered-initializer and actual SDK cases now cover aliases in
  both regions. All nine focused web tests pass. Four encoded API prefixes return
  200 in the existing Uvicorn/FastAPI capture with no identifier leakage; both
  backend telemetry tests pass without a backend production-code change.
- Final independent reviews are complete in
  `/tmp/activity-detail-quality-final-review.md`,
  `/tmp/activity-detail-trust-final-review.md`, and
  `/tmp/activity-detail-operations-final-review.md`. Trust resolves the medium
  alias finding with no residual local must-fix; Quality passes nine web and two
  backend telemetry tests plus the final-source benchmarks. Operations confirms
  bounded local evidence gaps are filled. No local alias/Quality/Trust review is
  pending; live evidence remains pending and phone checks are deferred under the
  subsequent release authorization above.
- All 14 reviewed fingerprints matched
  `sha256:ab876b2cba72ca74f3f12235272512679806476be190bc4166103d789f1e6f7a`
  before this documentation-only closeout. The unchanged 10-file code-only
  manifest `/tmp/activity-detail-ready-code.sha256` has digest
  `sha256:acbd123837d8c94b66330ab0630de89046535945ee8199db7fbea598edae050f`.
  These independent conclusions apply to that code; this document records them
  without claiming the new documentation bytes were independently reviewed.
- Alias follow-up executor checks: nine focused browser tests, two backend
  telemetry tests, the full 319-test web build, TypeScript/Vite/PWA/public checks,
  changed-file ESLint and patch whitespace checks pass. No streaming changes,
  full backend rerun or new benchmark. Logs:
  `/tmp/activity-detail-alias-{web,backend,build,lint}.log`.
- Platform, proxy and Azure-ingested production logs have **not** been inspected.
  A Uvicorn application logger filter does not control those channels. Inspect
  effective deployment logging only under the appropriate Operations authority.
- `scripts/appinsights_boundary.sh` sets backend Application Insights and linked
  workspace retention to 30 days and checks it in preflight. This is repository
  configuration evidence; live effective settings and retained data remain
  unobserved. No recipients, collection or retention expansion is proposed.
- iPhone remains the concrete deferred device check: Skyline Canvas curves, dual axes,
  missing-data gaps, touch selection/drag/zoom/split navigation and VoiceOver.
  Native evidence's unchanged 26-file manifest matches `1adaf4bd…`; the installed
  DevTools cannot render Skyline Canvas. Parent handles the phone handoff.

## Rollback / Recovery

- No deployment or production configuration changed in this pass. Preserve
  the user's existing activity implementation, `paseo.json` and stash.
- A future rollback must be coordinated by Operations: reverting these code
  changes restores input-proportional Python allocations and activity-identifier
  telemetry emission. Do not treat that as an acceptable privacy recovery by
  default; retain the minimization boundary when addressing regressions.
- On failed health/SHA checks, privacy/isolation regression or sustained runtime
  degradation, parent coordinates a protected-main revert or forward fix and
  repository workflow execution. Retain telemetry minimization, owner/demo
  isolation, `private, no-store` and the service-worker cache contract; a blanket
  return to `059c8f1` is not presumed privacy-safe. Preserve migration history
  and emergency controls. Miniapp candidate upload does not replace the live
  release; any published-version recovery follows the manual provider lane.
  Recheck exact SHA, health, controls and the affected privacy boundary before
  claiming recovery.
- Do not introduce raw-row truncation, new activity limits, concurrency limits
  or new client states to meet an unaccepted threshold.

## Related

- [Implementation impact and exact Product handoff](../dev/activity-detail-implementation-impact.md)
- [Trust draft](../dev/activity-detail-trust-decision.md)
- [Monitoring and alerts](monitoring-and-alerts.md)
- [Deployment](deploy.md)

_Last reviewed: 2026-09-29 · Owner: Operations (release authorized; not yet deployed; live/device evidence pending)_
