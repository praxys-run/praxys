# Incident ir-dfa-readiness-recovery-20260928

Owner: Operations. Status: **Open — recovery not verified**.
Severity: provisional **SEV-2**, for material readiness degradation and interrupted
feedback-publication restoration. Broad outage and data loss are not established.
The root cause remains unresolved; DB/pool waits are not excluded.

## Observations and chronology (UTC, 2026-09-28)

| Time | Evidence |
| --- | --- |
| 08:23:12 | PR842 protected-squash merged as `bafd1714df108747758bd58273578be3613b7bd0`, from reviewed `233ab6ef`; no admin bypass. |
| 08:23:42 | Backend run `36397049771`, job `108845823440`, completed feedback quiescence. |
| 08:25:24 | Existing configuration reconciliation completed. |
| 08:36:08–08:45:06 | Cutover verification exited 1. Feedback restoration and DFA observation were skipped. The retained sanitized failure excerpt contains only the exit result; the recorded log hash covers the entire deployment job log. |
| 08:41:50 | Version and liveness returned HTTP 200 with source `bafd1714`. |
| 08:43:33 | Readiness exceeded a 10-second client deadline. |
| 08:49:54 | Labs run `36397049795` passed its prerequisite step and later completed SUCCESS. Proposed cancellation was not executed after state advanced. |
| 08:51:59 | Version returned 200 in 0.425s; readiness timed out in 8.363s, matching the workflow's 8-second budget. |

Aggregate-only telemetry for 08:36–08:52:15 recorded 74 completed readiness
requests, all HTTP 200, maximum 182520 ms and p95 approximately 166929 ms. Older
readiness p95 was 69 ms. Recorded dependency maximum 2743 ms does not account for
uninstrumented waits and does not localize the cause. These facts support a
readiness-specific latency problem, not proof of a particular DB or parser cause.

Configured/original feedback-positive intent `true` was independently verified
from the failed run and repository configuration. There is **no subsequent live
positive-control readback** in this record. The last completed quiescence set
positive enable false; restoration was skipped because cutover failed before the
restoration step and its trap were entered.

Miniapp upload was skipped; Azure frontend deployment was not triggered. No retry,
cancellation, rollback, manual restart/setting change, activation, STOP assertion
or athlete-data access was executed by the recovery coordination at this point.
The failed workflow's existing cutover code contains its own restart fallback;
this record does not imply that operator/agent recovery executed another restart.

## Evidence anchors

- Failed backend: [run 36397049771](https://github.com/praxys-run/praxys/actions/runs/36397049771), job 108845823440.
- Labs: [run 36397049795](https://github.com/praxys-run/praxys/actions/runs/36397049795).
- Preserved release receipt `/tmp/dfa-pr842-release-evidence.json`, SHA256
  `848896b5255ca748bae8ccc6ab465a406c61e882daf4379babcc0cb70b1b1f7f`.
  Earlier failed receipt revisions remain historical evidence; do not overwrite
  their chronology with a recovery claim.
- Entire deployment job log SHA256 (only its sanitized failure line is retained
  in the release receipt):
  `2f01448a935cc404e794d5beff8a91d26a8d436f87941a74654f04c548eb3191`.
- Local timing `/tmp/dfa-readiness-local-timing.json`, SHA256
  `48ffa74e1dfb4d4a4c4f08e0fa4c00d981b56fe1048210a75b3cb33df7c93edc`:
  unchanged guard 1.00–1.13s; process-local safe-C counterfactual 0.09–0.13s,
  equal parsed registry/digest and duplicate rejection. Approximately 98.8% of
  profiled guard time was YAML loading. **Local evidence is not production proof.**

The exact old PR839 source was independently verified on a separate synthetic
PostgreSQL database for startup/state/rights preservation and real inactive guard
denial. Its immediate rerun path is nevertheless blocked by current readiness;
`sync_config=false` would also capture current positive false rather than the
verified original true. No blind old-source rollback is authorized.

## Accepted recovery and authority boundary

[ODR, Architecture and Trust boundaries](../../dev/dfa-readiness-recovery/decisions.md)
and the [recovery Work Contract](../../dev/dfa-readiness-recovery/work-contract.json)
require a protected parser/transport correction, independent review and ordinary
release checks. Engineering is the sole source writer. Operations owns rollout.
The enclosing activation contract stays separate; no activation candidate or
human science signature is created by this incident work.

First allow ordinary automatic deployment of the reviewed repair. Only after its
terminal failure before package/App Service deployment, while exact old `bafd1714`
still serves and deployment/Labs queues are terminal, may Operations consume
**one** incident dispatch with `recover_dfa_cutover_842=true`, `sync_config=true`,
main ref and verified configured/original feedback-positive intent true. Failure
or ambiguous completion consumes the authorization; no rerun/re-dispatch. Record
the run ID (or explicitly unknown if completion cannot be resolved).

**One distinct dispatch is an Operations authorization/receipt constraint, not
technical prevention of every privileged new dispatch.** The workflow rejects
rerun attempts and checks exact prerequisites before quiescence mutation. There
is no additional ledger, secret, privilege or automatic recovery dispatch.

Verification Evidence: pending fresh independent review of frozen repair.
Release Evidence: pending repaired-source deployment and observations.
Incident recovery dispatch run ID: not dispatched; conditional authorization unused.

## Closure criteria

Close only after the reviewed repair SHA is deployed, ordinary readiness/control
cutover passes, verified original positive-enable intent is restored while
respecting the negative kill switch, and no-store DFA `policy_active:false` /
`contract_digest:null` is observed at the repair SHA. Record workflow results,
observation times, remaining limitations and the authorization outcome. A merged
PR, local speedup, liveness 200, or readiness 200 without the complete required
state does not close this incident.

## PR845 deployment and diagnostic follow-up

Status remains **Open**. PR845 was protected-squash merged at 2026-09-28 11:04:41 UTC
as 00577ce859ff90bbdf50a90e8ba00c4822243ec4. Ordinary deployment 36413476542 failed
pre-package quiescence; the conditionally authorized incident run 36414310829
consumed its one dispatch. It passed prequiescence 11:13:37, deployed 11:26:41 and
passed normal cutover 11:33:05, then timed out restoring feedback at 11:41:12.
DFA policy observation was skipped. Job 108901663736 log SHA256:
`236560126913ed25632e1d9521f589a812faa435bbc1ae15451cdf10c82da9d4`.

Operations' later bounded diagnostic sample (11:47:41–11:48:03UTC) returned 200 in
18.257s, no-store, ready, DFA false/null and feedback positive=true/kill=false/
effective=true. This is point-in-time diagnostic evidence, not 8s acceptance or
proof that the interrupted restoration trap completed. Plan CPU 71–100%, mostly
96–100%, and memory 69–85% (max 86%) cover two apps/no slots; neither establishes a
per-process cause. Completed readiness telemetry remains slow despite the parser
mitigation. Database, filesystem, policy validation and contention costs remain
unresolved.

`readiness-timing-deadline-v1` adds bounded instrumentation and truthful restoration
deadlines, without caching, pool changes, scientific changes or timeout expansion.
The new exact 00577/default-false predeployment option is source preparation only;
final delivery review must separately authorize any dispatch after ordinary
pre-package automatic failure and terminal queues. The consumed 842 allowance is
not additive. No recovery, activation, rollout or incident closure is claimed.
