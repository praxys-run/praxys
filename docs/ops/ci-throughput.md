# CI timing and test completeness

**Summary:** Retain serial full-suite evidence and remove repeated immutable test preparation before changing CI concurrency.

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

   For a labelled local subset, add `-- tests/test_ci_pytest.py`. CI uses the full `tests/` default. The wrapper passes `-p scripts.ci_pytest_plugin` explicitly; it does not export pytest plugin options that could contaminate nested security-test subprocesses.

2. Read `result.json` for revision/environment identity, requested paths, elapsed time, real child exit status, wrapper status and reporting errors. Read `phases.json` for every collected and selected node ID, setup/call/teardown durations, skip/xfail reasons, strict XPASS and collection skips/errors. `junit.xml` remains available to ordinary test-report tooling.

3. Collect run and rerun timing without changing GitHub state:

   ```bash
   python scripts/ci_metrics.py --repo praxys-run/praxys --run-id 123456 123457 --output /tmp/praxys-ci-metrics.json
   ```

   The collector reads all attempts and job pages. Summed job execution minutes are a runner-utilization proxy, **not exact billed minutes**. Cancelled jobs with complete timestamps count; absent/invalid/incomplete timing remains `null`, with the known partial total reported separately. First-attempt dispatch delay is creation to earliest job start, not per-job capacity queue. Rerun dispatch latency is unknown; time waiting for a human rerun is never classified as queue.

## Verify

- The existing serial `python-tests` job and required downstream contexts stay in place; all tests still run on every code PR. No test selection, additional runners, xdist or dependency changes are introduced here.
- Success requires the real pytest exit code to be zero, complete collection and execution reports, no unexpected deselection, no failed phases, at least one passing call, and readable phase/JUnit evidence. Missing reports fail visibly; import/collection failures retain their actual pytest exit codes.
- The workflow uploads `backend-pytest-RUN_ID-RUN_ATTEMPT` with `always()` and 30-day retention. A killed runner or SIGKILL can prevent final reports/upload; a partial or absent artifact is incomplete evidence, never a passing result.
- Before future parallelization, demonstrate complete, disjoint test coverage at one immutable revision and environment, a shorter critical path, and no more than 5% increase in **summed complete CI job execution minutes**, including repeated setup. Repeat noisy comparisons. This change does not activate shards.

### Measured fixture change

On Python 3.12.3 / pytest 9.1.1 / PyYAML 6.0.3, one local focused run of the full science STOP and policy-probe files plus three deployment-workflow cases took **208.39s / 80 passed** before and **110.22s / 82 passed** after (47.1% less elapsed; two added isolation cases). All original node IDs and assertions remain. A separate readiness/parser/watchdog/signal check passed **97 tests in 37.85s**. These are local diagnostic measurements, not an end-to-end CI throughput claim.

The savings come from reusing real immutable STOP/layout preparation with independently copied files/Git objects, reusing expected observation dictionaries for pure schema mutations, and caching deployment YAML parsing while returning private documents. Real STOP races, atomicity, candidate subprocess isolation, every negative case, retry counts and watchdog/signal behavior remain exercised.

## Rollback / Recovery

- If evidence collection breaks, diagnose `result.json` errors and the pytest log; do not convert incomplete reporting to success or skip tests.
- Revert the wrapper/upload workflow change and fixture optimization through a reviewed repository change to restore `python -m pytest tests/ -v`. Required checks and the full suite remain mandatory.

## Related

- [Contributing: tests](../dev/contributing.md#testing)
- [Pre-merge workflow](../../.github/workflows/ci-premerge.yml)
- [Science implementation coverage](../../config/science-implementation-coverage.json)

Implementation impact: test harness and CI evidence only; operations gains this runbook and retained artifacts. Production data, analysis formulas, API/client behavior, migrations, scientific decisions and deployment settings are unchanged. Source-coverage registration keeps the new validation scripts and their regression tests governed.
