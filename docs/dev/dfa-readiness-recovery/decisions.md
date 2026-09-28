# Bounded PR842 readiness recovery decisions

Task: `dfa-readiness-recovery-20260928`. Status: accepted implementation boundaries
transcribed by Engineering from routed coordinator/specialist returns; independent
verification and operational recovery are pending. This is not Engineering
approval of its own work.

The [deterministic Work Contract](work-contract.json) classifies a production
incident: classification `sha256:f320f595646b4f824af4112cd2041986e3cfdc8d9e70942df2e098b7cae07f39`,
route `sha256:5c9a4fe0850e0cf9861aa01fd8e74bd566d153474e24ad6a3097c3bf05f09f40`.
Operations leads the incident and runtime work; Engineering is the sole source
executor through Change Loop; Quality independently verifies. Architecture and
Trust own their boundaries below. The enclosing DFA activation contract
`sha256:7ec2e25bfe445b976dd0b626def424af5861a3bd65d68ab17122421d4bb1c999`
and its error/review history remain preserved in `../dfa-activation/`.

## Architecture decision — accepted implementation boundary

Optimize only the existing strict YAML parser by selecting `CSafeLoader` when
available. Retain the same custom duplicate-key mapping constructor, merge
flattening, safe constructors and every registry, approval and STOP validator.
Fallback to `SafeLoader` is allowed only when the C backend is unavailable,
never after parse/validation rejection. No cache, schema, dependency or scientific
policy changes. Local timing establishes substantial avoidable parser overhead;
it does not establish the sole production cause or exclude DB/pool waits.

The deployed readiness path remains the actual policy guard. There is no liveness
substitute, mocked runtime result or optimistic readiness. Fresh Science must
confirm unchanged scientific records and canonical behavior within the enclosing
activation task.

## Trust decision — accepted implementation boundary

Parser backend parity must cover types, malformed/unsafe tags, flat/nested/equal
key duplicates, YAML merge duplicates and all tracked scientific records. Failure
continues to propagate through the existing fail-closed guard. No authority,
source verification, approval scope or terminal STOP validation is removed.

The recovery option is a typed, default-false workflow-dispatch input. Its main,
event, config-sync, configured-intent and exact serving-source guards precede
quiescence mutation. Repeated GitHub run attempts fail before mutation. **The
single distinct dispatch limit is Operations authorization plus a recorded
incident receipt, not technical prevention of every privileged new dispatch.**
No new permission, secret, cross-run ledger or automated dispatch is introduced.

## Operations decision odr-dfa-readiness-recovery-20260928

Engineering implements the following exact bounded option in the protected
backend workflow; only Operations may decide and execute its use:

- `recover_dfa_cutover_842`: workflow-dispatch-only boolean, default `false`.
- Require main ref, `sync_config=true`, configured/original feedback-positive
  intent exactly `true`, and the currently serving `/api/version.source_sha`
  exactly `bafd1714df108747758bd58273578be3613b7bd0`.
- Predeployment quiescence only: connect timeout 5 seconds, total request timeout
  210 seconds, at most two sequential complete readiness attempts, one 5-second
  gap, and a 9-minute step deadline. No nested retry. Every existing readiness,
  false positive-enable, boolean kill-switch and false effective-publication
  predicate remains required.
- Ordinary push/default transport and every post-repair 8-second gate remain
  unchanged. First allow the ordinary automatic corrected deployment.
- One explicit incident dispatch is permitted only after terminal automatic
  failure before package/App Service deployment, with old `bafd1714` still
  serving and deployment/Labs queues terminal. No opt-in if automatic deployment
  succeeds. Record the dispatch run ID; failure or ambiguous completion consumes
  authorization. No rerun or second dispatch.
- Normal repaired-source cutover must pass before existing restoration of the
  verified configured/original positive intent `true`, respecting the negative
  kill switch. Then observe the repair SHA and no-store actual DFA false/null.

The explicit recovery entry does not repair settings by force, waive readiness,
rerun old PR839 blindly, or authorize DFA activation/STOP. The prior Engineering
240-second discussion was a proposal; the approved boundary is the 210-second
contract above.

## Decision Review and artifact obligations

Decision Review accepted this bounded protected recovery under existing human
consent; no generic repeated permission question is required. Independent
Trust/Architecture/Quality/Science and Operations review the frozen correction
before final preflight/CI and protected release. Engineering does not dispatch,
merge or independently approve this change.

The [Incident Record](../../ops/incidents/ir-dfa-readiness-recovery-20260928.md)
remains open. Verification Evidence and Release Evidence are pending outputs;
actual immutable reports and workflow references must distinguish local tests,
production observation and recovery completion. Do not add a report-only source
commit after final checks merely to restate external evidence.


## Admission and exit criteria

Entry: fresh trusted main `bafd1714df108747758bd58273578be3613b7bd0`, existing
human consent, the exact deterministic recovery contract above, and the accepted
specialist transport/parser boundaries. The isolated writer branch preserves the
original checkout, plugin gitlink and earlier capability/recovery evidence.

Engineering exit: one committed frozen correction with meaningful focused checks,
unchanged science records and canonical artifacts, and the same-batch incident/
operations documentation. Independent reviewers then close findings before final
preflight and required CI. Operations release and incident closure follow their
separate predicates; a source handoff is not production recovery.
