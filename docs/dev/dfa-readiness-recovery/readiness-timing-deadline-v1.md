# Readiness timing and restoration deadlines v1

Owner/executor: Engineering. Base: `00577ce859ff90bbdf50a90e8ba00c4822243ec4`.
Work Contract: `dfa-readiness-recovery-20260928`, route
`5c9a4fe0850e0cf9861aa01fd8e74bd566d153474e24ad6a3097c3bf05f09f40`.
This implementation records the root coordinator's accepted Architecture, Trust,
Operations and Decision Review boundaries. Acceptance of these boundaries is not
independent verification of this code or permission to dispatch/deploy it.

## Problem and limits

PR845 deployed, but its single incident dispatch timed out restoring feedback.
A later diagnostic readiness sample took 18.257 seconds and returned ready,
DFA false/null and feedback positive=true/kill=false/effective=true. This is not
normal eight-second acceptance. Reported plan CPU was 71–100%, mostly 96–100%,
across exactly two applications with no slots; it does not identify a process or
cause. The incident remains open. Parser acceleration is not sufficient recovery.

The change measures the existing readiness path and corrects restoration deadline
accounting, transport checks and failure reporting. It changes no cache, database
pool, science record, approval, formula, dependency, client or publication intent.
It adds no alert or invocation-control change. No test proves production recovery.

## Accepted Architecture and Trust boundaries

A small async adapter makes exactly one existing Starlette `run_in_threadpool`
call with its default limiter/cancellation semantics. All synchronous work,
including session creation, explicit acquisition, queries, authority comparison
and finally-close, remains in the same worker. Explicit `Session.connection()`
measures the existing lazy checkout; it does not acquire a second connection or
issue an extra query. Existing readiness exception boundaries, 503s, response
shape, no-store header and real uncached policy guard remain.

Nine fixed stages are measured: dispatch_queue, db_init, db_acquire, db_select,
shared_authority, db_close, controls, dfa_policy and handler_total. Wall time uses
a monotonic clock; CPU uses the current worker's thread clock only for dfa_policy
and handler_total. At most eleven scalar observations are passed in one best-effort
telemetry helper call (normally ten, without db_init). Dispatch timing is not
an event-loop-lag measurement; acquisition includes pre-ping and reconnect work,
not only pool waiting. Instrument creation, clock and recording failures discard
telemetry without changing readiness. The request path never initializes or
flushes an exporter, performs telemetry network I/O, sleeps or retries.

Only allowlisted stage/clock/outcome/parser labels are emitted through
`api/telemetry.py`. No user hashes, identifiers, request headers, settings,
exceptions, SQL, file paths, policy contents or result data enter these signals.
The pre-created SDK histogram performs local aggregation; existing asynchronous
export remains responsible for delivery. An arbitrarily broken SDK cannot be
promised incapable of blocking, and missing telemetry is not health evidence.

## Accepted Operations boundaries

Restoration retains the 480-second outer step, normal eight-second curl probes,
source/version and every current configuration/runtime predicate. A monotonic
absolute work deadline is 360 seconds. Cleanup is at most 105 seconds and cannot
extend beyond second 465, leaving 15 seconds before the outer runner limit.
Command startup, parsing, outputs and termination grace consume these budgets.
An independent controller watchdog covers Python work and cleanup; an outer
465-second process watchdog also covers interpreter startup. Command groups,
nonblocking bounded capture and TERM/KILL cleanup handle children retaining pipes.

Azure writes are capped at 45 seconds plus two seconds termination grace; reads
at 20 plus two; curl remains eight with at most two seconds grace. A command must
fit in its remaining phase budget including local bookkeeping reserve. At most
36 restoration attempts and five-second inter-attempt sleeps remain. Predicates
and output writes are bounded subprocesses too. No provider body/error is logged.

Success requires a successful setting write, fresh authoritative configuration,
successful version/readiness transports with exact existing predicates, and a
successful output write. Failure cleanup runs once, only changes positive enable
to false and preserves the original failure/signal. A failed/timed-out write is
remotely ambiguous: subsequent samples do not settle an outstanding conflicting
operation. `verified_disabled` requires current false configuration, exact source,
normal eight-second ready/false state and no unresolved write ambiguity.
Configuration-only evidence is `control_plane_only`; all other incomplete or
ambiguous evidence is `unknown`. Neither is successful restoration. The workflow
summary reports unknown after a failed step rather than stale cutover values;
bounded controller diagnostics distinguish completed cleanup observations.
SIGKILL/runner loss can still interrupt cleanup: absent proof means unknown.

## Separate diagnostic delivery preparation

`recover_readiness_timing_00577` is a distinct default-false option. Before any
quiescence mutation it requires workflow_dispatch, main, attempt 1, sync_config,
configured and originally captured positive intent=true, and currently serving
exact source `00577ce859ff90bbdf50a90e8ba00c4822243ec4`. Selecting it with the old
PR842 option is rejected. Predeployment transport alone permits two sequential
210-second complete requests, one five-second gap and a nine-minute step.
Normal postdeployment eight-second gates remain unchanged.

Ordinary automatic deployment must be attempted first. A later dispatch requires
separate final delivery authority, terminal automatic failure before package
execution and clear backend/Labs queues, with a distinct immediate receipt.
Failure or ambiguity consumes that dispatch; no rerun/redispatch is implicit.
Single use is an operational authorization/receipt limit, not a global technical
ledger. Quiescence may interrupt the currently sampled restored publication.
The consumed PR842 allowance cannot be reused. This source preparation grants
no merge, dispatch, deployment, recovery or activation authority.

## Implementation impact and coverage consequence

- API: adapter/timing only; exact public response and real guards retained.
- Database: explicit timing of existing checkout, same queries/connection and
  worker ownership; no schema, pool, timeout or migration change.
- Telemetry: one bounded local histogram and inventory; no new alert provisioning.
- Workflow: deadlines, command-tree handling, strict transport and truthful
  failure observation; distinct guarded predeployment option only.
- Tests: real extracted shell, real jq, fake clock/commands and shortened real
  watchdog cases; readiness concurrency/cancellation/closure/privacy coverage.
- Operations: signal interpretation, incident chronology and release limits.

**Whole-file maintenance consequence:** adding `api/telemetry.py` and
`tests/test_telemetry.py` to the DFA implementation coverage manifest binds the
whole files, including unrelated telemetry edits. After activation, governed
maintenance therefore requires the supported terminal STOP before those edits
(or another explicitly supported reviewed path). This is not semantic isolation
or a claim that complete dependency closure has been solved. The isolated science
validation adds only `tests/test_telemetry.py`; authority and producer rules do not
change.

## Verification status

Engineering focused checks and the exact frozen source receipt are supplied to
fresh independent reviewers. Final committed-head preflight and required CI must
follow closure of their findings. No executor test is independent approval.

The earlier `proposal-checksums.sha256` remains the historical PR845 proposal
record at base 00577. The new exact-head external freeze receipt binds this revision;
prior source evidence is not relabelled.
