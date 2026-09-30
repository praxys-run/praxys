# CI timing and test completeness

**Summary:** Retain complete-suite evidence and compare two isolated whole-file shards before changing the serial CI default.

**Use when:** Investigating slow PR feedback, runner usage, missing test execution, or comparing a proposed CI acceleration.

## Prerequisites

- Python 3.12 and the repository requirements, with the expected submodules initialized.
- GitHub CLI read access to Actions for remote timing collection. No deployment or write permissions are needed.
- Compare the same checked-out revision, package name/version fingerprint, Python/platform/architecture and submodule state. Dirty local measurements are diagnostic, not an immutable CI comparison.

## Steps

1. Run all backend tests through the same serial entry point as `ci-premerge.yml`:

   ```bash
   python scripts/ci_pytest.py --output-dir /tmp/praxys-pytest
   ```

   For a labelled local subset, add `-- tests/test_ci_pytest.py`. CI uses the full `tests/` default. The wrapper passes `-p scripts.ci_pytest_plugin` explicitly; it does not export pytest plugin options that could contaminate nested security-test subprocesses. Local shard inspection adds `--shard-count 2 --shard-index 0` (or `1`); each process collects the complete requested suite once and executes its assigned files sequentially.

2. Read `result.json` for revision/environment identity, requested paths, elapsed time, real child exit status, wrapper status and reporting errors. Read `phases.json` for every collected and selected node ID, setup/call/teardown durations, skip/xfail reasons, strict XPASS and collection skips/errors. `junit.xml` remains available to ordinary test-report tooling.

3. Collect run and rerun timing without changing GitHub state:

   ```bash
   python scripts/ci_metrics.py --repo praxys-run/praxys --run-id 123456 123457 --output /tmp/praxys-ci-metrics.json
   ```

   The collector reads all attempts and job pages. Summed job execution minutes are a runner-utilization proxy, **not exact billed minutes**. Cancelled jobs with complete timestamps count; absent/invalid/incomplete timing remains `null`, with the known partial total reported separately. First-attempt dispatch delay is creation to earliest job start, not per-job capacity queue. Rerun dispatch latency is unknown; time waiting for a human rerun is never classified as queue.

### Compare the two-shard candidate

PR events and ordinary manual runs remain **serial**. The manual `test_mode`
input supports `serial`, `sharded` and `compare`. Compare runs launch one serial
baseline plus exactly two isolated shard jobs at the same revision:

```bash
gh workflow run ci-premerge.yml --ref YOUR_REVIEWED_BRANCH -f test_mode=compare
```

`config/ci-test-weights.json` is checked in and versioned with the candidate.
Its 175 file weights are measured setup, call and teardown durations from serial
CI run 36660158527 at merge revision
`4133d4345aefbebfb27d9f246e45f6d46350402f`. They are scheduling hints, not runner-cost
or activation evidence. The planner assigns entire files
using longest estimated duration first, stable ties and the median positive
weight for new files. `test_pg_migration.py` and `test_activity_dfa.py` stay in one
shard because they can share a scratch database. There is no within-runner test
parallelism or selection filter; new tests automatically enter the full collection.

Each job uploads a unique `backend-pytest-RUN_ID-RUN_ATTEMPT-LABEL` artifact. The
existing `backend-tests` job requires matrix success, downloads only the current
run/attempt, and executes `scripts/verify_ci_pytest.py`. It rejects missing,
failed, cancelled, duplicate, all-skipped or incomplete executions. It checks
matching immutable checkout/runtime/package/submodule identities, matching full
node-ID sets, a disjoint complete two-shard union and actual phase execution for
every selected test. The serial baseline is validated separately, not added to
the two-shard union. Compare mode also requires equal runtime skips/xfails and
common module-collection skips/reasons; module skips observed by both collectors
are not counted as duplicate execution.

After the entire run completes, collect its job timings with `ci_metrics.py`.
Compare `python-tests (serial)` with the two `python-tests (shard-N)` jobs:
the longest shard job must be faster than the serial job and the **sum** of both
shard job execution seconds, including dependency installation and setup, must
be at most **1.05 times** the serial job seconds. Also inspect total workflow
runner usage and queue/dispatch delay. Missing or incomplete timing does not
qualify. Repeat noisy comparisons before a separate reviewed change enables the
default. The verifier emits coverage evidence only; no artifact or successful
benchmark automatically enables sharding.

## Verify

- The existing `python-tests` job ID and required `backend-tests`, `frontend-quality` and selective-review checks stay in place. All tests still run on every code PR; serial remains the default. The opt-in two-shard mode changes only which isolated runner executes each whole file. No xdist or dependency changes are introduced.
- Success requires the real pytest exit code to be zero, complete collection and execution reports, no unexpected deselection, no failed phases, at least one passing call, and readable phase/JUnit evidence. Missing reports fail visibly; import/collection failures retain their actual pytest exit codes.
- The workflow uploads execution evidence with `always()` and 30-day retention. A killed runner or SIGKILL can prevent final reports/upload; a partial or absent artifact is incomplete evidence, never a passing result.
- Unified PR CI and standalone main/manual Miniapp validation both invoke `scripts/check_miniapp_source.sh` from `miniapp/`. It preserves all seven page checks, four component checks, source-size exclusions, the 1500 KB warning and 2000 KB failure thresholds. Typecheck and generated-source drift checks remain required. The standalone workflow no longer duplicates PR validation.
- Translation automation dispatches the unified workflow once and waits for its exact generated head, including Miniapp validation. A failed or missing dispatch remains a failed translation-validation status; the separate selective-review-policy wait remains mandatory.

### Measured fixture change

On Python 3.12.3 / pytest 9.1.1 / PyYAML 6.0.3, one local focused run of the full science STOP and policy-probe files plus three deployment-workflow cases took **208.39s / 80 passed** before and **110.22s / 82 passed** after (47.1% less elapsed; two added isolation cases). All original node IDs and assertions remain. A separate readiness/parser/watchdog/signal check passed **97 tests in 37.85s**. These are local diagnostic measurements, not an end-to-end CI throughput claim.

The savings come from reusing real immutable STOP/layout preparation with independently copied files/Git objects, reusing expected observation dictionaries for pure schema mutations, and caching deployment YAML parsing while returning private documents. Real STOP races, atomicity, candidate subprocess isolation, every negative case, retry counts and watchdog/signal behavior remain exercised.

## Rollback / Recovery

- If evidence collection breaks, diagnose `result.json` errors and the pytest log; do not convert incomplete reporting to success or skip tests.
- Use manual `test_mode=serial` to diagnose a shard problem. The PR default already remains serial; do not bypass the strict aggregator to accept missing or changed coverage.
- Revert the shared Miniapp helper and its two callers together if necessary; preserve required page/component/size, typecheck and generated-source checks.
- A reviewed rollback can restore `python -m pytest tests/ -v`; required checks and the full suite remain mandatory.

## Related

- [Contributing: tests](../dev/contributing.md#testing)
- [Pre-merge workflow](../../.github/workflows/ci-premerge.yml)
- [Science implementation coverage](../../config/science-implementation-coverage.json)

Implementation impact: test harness and CI evidence only; operations gains this runbook and retained artifacts. Production data, analysis formulas, API/client behavior, migrations, scientific decisions and deployment settings are unchanged. Source-coverage registration keeps the new validation scripts and their regression tests governed.
