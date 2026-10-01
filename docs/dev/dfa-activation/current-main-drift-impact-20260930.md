# DFA activation current-main drift impact — 2026-09-30

Owner: Engineering execution evidence. Status: implementation review pending;
not independent Verification Evidence and not science, release, or rollback
approval.

This review compares the prior activation base
`994d4ded39316615a6aa119265de8e2ef5dde301` with trusted main
`0c82ce26a23856c09f620708a23cb80380b9c555`. Exactly 34 files named by
`config/science-implementation-coverage.json` changed. The reviewed current-main
coverage file digest is
`sha256:f9b3c8e619661616f31a2f4dc6b4144b3dc7469e71b7022f230a39298fd9a4ae`;
the separate `proposal-checksums.sha256` remains the historical PR842 snapshot.
No DFA numerical,
parser, source-eligibility, runtime guard, approval materializer, database model,
route, dispatcher, storage, rights, or STOP production module changed.

| Governed file | Semantic impact on bounded DFA activation |
| --- | --- |
| `.github/workflows/ci-premerge.yml` | Replaces the backend command with auditable serial/sharded execution artifacts and a same-run completeness verifier; default remains serial and the verifier explicitly does not authorize activation. |
| `.github/workflows/miniapp-build.yml` | Moves PR validation to unified pre-merge CI and reuses the same miniapp source/type checks on main/manual runs; no publish or upload behavior is added. |
| `api/main.py` | Adds activity-detail no-store middleware and privacy-safe activity telemetry instrumentation. The matcher excludes DFA paths; DFA privacy middleware, dispatcher startup and guard behavior are unchanged. Shared-process import risk still requires full regression. |
| `config/ci-test-weights.json` | Adds measured scheduling weights and preserves the DFA/PostgreSQL affinity group. It changes test scheduling only, never test selection or runtime policy. |
| `config/science-implementation-coverage.json` | Adds the new CI evidence, shard and miniapp-source files to governed coverage. It widens future integrity protection without changing the contract or parameters. |
| `miniapp/components/activity-history/index.scss` | Restyles activity rows and explicit actions for the activity-detail journey. The DFA action remains a separate 44px-or-larger control. |
| `miniapp/components/activity-history/index.ts` | Adds activity-detail navigation and display formatting. DFA continues to receive the unchanged activity ID and raw activity date through a dedicated field. |
| `miniapp/components/activity-history/index.wxml` | Separates report navigation, recorded-split expansion and the DFA button, avoiding nested activation or automatic POST behavior. |
| `miniapp/package-lock.json` | Regenerates the lock for the declared miniapp tooling update; application DFA code and fixture source are unchanged. |
| `miniapp/package.json` | Updates `miniprogram-ci` from 2.1.31 to 2.1.48. It affects build/upload tooling only; this activation does not upload or repair packaging. |
| `miniapp/types/api.ts` | Adds activity-detail response types and `activity_detail_available`; existing DFA contracts remain unchanged. |
| `miniapp/utils/i18n-catalog.ts` | Regenerates from canonical PO files and compacts identity English entries. DFA Chinese translations are preserved; English continues to fall back to the message ID. |
| `requirements.txt` | Updates Garmin, Alembic, PyJWT, OpenAI and Playwright minimums/pins. None defines DFA math or policy, but shared Python dependency drift requires complete backend and migration checks. |
| `scripts/check_miniapp_source.sh` | Centralizes page/component presence and package-size proxy checks; no app behavior or upload is performed. |
| `scripts/ci_metrics.py` | Adds read-only GitHub run timing collection; no GitHub mutation or activation authority. |
| `scripts/ci_pytest.py` | Adds fail-closed complete pytest execution evidence, identity and phase reporting. |
| `scripts/ci_pytest_plugin.py` | Adds the explicitly loaded collection/phase recorder; nested pytest does not inherit it. |
| `scripts/ci_shards.py` | Adds deterministic whole-file scheduling with DFA/PostgreSQL affinity; it cannot deselect coverage. |
| `scripts/verify_ci_pytest.py` | Requires same-head, same-run, clean, complete artifacts and marks `activation_authorized:false`. |
| `tests/test_ci_metrics.py` | Covers read-only timing and missing/ambiguous attempt evidence. |
| `tests/test_ci_pytest.py` | Covers real subprocess result capture and fail-closed incomplete evidence. |
| `tests/test_ci_shards.py` | Covers complete/disjoint shard union, serial equivalence and required-context wiring. |
| `tests/test_dfa_recovery_workflow.py` | Caches immutable workflow YAML per process and atomically publishes the synthetic clock. The merged branch also retains the actual-controller publication-race regression; production workflow deadlines and predicates are unchanged. |
| `tests/test_miniapp_source_check.py` | Covers the shared miniapp source guard and confirms both workflows invoke identical checks. |
| `tests/test_science_implementation_coverage.py` | Requires every new CI evidence/source file to remain in DFA governed coverage. |
| `tests/test_science_policy_probe.py` | Reuses trusted prepared expectations through deep copies while keeping candidate execution fresh; strict observation/provenance assertions are unchanged. |
| `tests/test_science_stop_github.py` | Reuses independently copied Git templates, preserving modes, symlinks and isolated Git objects; STOP source, artifact and history rejection semantics are unchanged. |
| `web/package-lock.json` | Regenerates the lock for declared web dependency updates; validation must use `npm ci` and the production build. |
| `web/package.json` | Updates React, router, Lingui, Base UI, query, telemetry and build-tool versions. DFA component source is unchanged, but shared client-runtime drift requires the production build and component tests. |
| `web/src/components/ActivityCard.tsx` | Redesigns the activity summary and adds report navigation. The DFA button remains explicit and separate, using the unchanged activity ID/date and no automatic request. |
| `web/src/hooks/useAuth.tsx` | Clears React Query state on login/logout/invalid restore, preventing cross-session cached DFA metadata from surviving account transitions. Authorization remains server authoritative. |
| `web/src/locales/en/messages.po` | Adds activity-detail strings and refreshed source references; audited DFA English message IDs/text are unchanged. |
| `web/src/locales/zh/messages.po` | Adds reviewed activity-detail translations; audited DFA Chinese translations and claim limits are unchanged. |
| `web/src/types/api.ts` | Adds activity-detail response types and `activity_detail_available`; existing DFA API types remain unchanged. |

Conclusion: current-main drift does not change the approved DFA method, claims,
eligibility, activation boundary or rights behavior. It does change shared process,
client-runtime, dependency and required-CI context, so the old validation run cannot
be reused. The merged head requires fresh generators, complete backend/preflight,
web/miniapp build/type/i18n checks, trusted-main frozen activation validation, and
fresh independent specialist and Quality review. Evidence Review and SDR remain
draft, and runtime remains inactive.

## Final main refresh to `3067bcba`

After the first frozen-head preflight, trusted main advanced from `0c82ce26` to
`3067bcba6ecd22d29fab612fd58b3960b987c5b2` through PR #867. The 13-file delta
changes only task-completion guidance, role manifests, routing descriptions,
agent-loop policy, the change-loop runbook and routing tests. Its intersection
with the DFA governed-file manifest is empty. Routing descriptions are explicitly
excluded from classification and route digests; the new tests preserve triggered
Science, Design, Trust, Architecture, Operations and Quality obligations.

The branch merged this exact main revision normally at
`a7c17824499b360522e9deaaec89dcbac072933e`. No conflict resolution or DFA file
edit was required. This refresh adds no DFA science, runtime, API, client,
dependency, migration, workflow or production behavior. It invalidates the old
head's final-preflight claim solely because evidence is SHA-bound, so the refreshed
head still requires current parity, routing/science checks, clean generators and a
new final preflight.

## Lifecycle-test prerequisite and final base `ac1bfd37`

PR #853 subsequently received authenticated source comment `5924024414` and
materialized head `092ec3b43c197f8fcab93ffd0d299adbadac0df0`. Its
post-materialization Pre-merge CI run `36809913896` failed because
`tests/test_activity_dfa.py` and `tests/test_health_ready.py` still assumed the
checked-in science policy was always inactive. The materialized guard correctly
accepted active contract
`sha256:0029c8753ba7c3a695ec7549ef41f39886280642d2fd70e7973b5022dba751d6`;
the failure was deterministic lifecycle-test debt, not a runtime, algorithm,
parameter, claim or policy regression. Preserve that head, comment and failed run
as immutable history; do not rerun or relabel them.

PR #868 changed only those two tests to construct isolated draft/inactive,
accepted/inactive and accepted/active lifecycle states, including target-STOP
isolation. After protected checks and invariant review passed, it squash-merged as
`ac1bfd37cd1c79064b3920bee33c689f106f1c58`. This repairs the acceptance
harness only. It changes no science artifact, numerical method, parameter,
runtime/API behavior, client, workflow, dependency, migration, production setting
or PostgreSQL state.

The merge produced bounded release evidence, not a production cutover. Labs run
`36822621006` built and published the exact source tag and `latest` at OCI
digest
`sha256:b3986b3116cd56f01975e74f2356ea4f04093b6caa88513630a61593fa0402a3`,
then deploy job `110241989344` stopped at the API-SHA guard before Azure login or
actions; the existing worker remained unchanged. No backend deployment ran for
the squash. A public sample at `2026-10-01T06:24:24Z` still reported API source
`3067bcba6ecd22d29fab612fd58b3960b987c5b2`, ready/database healthy, unchanged
AI and feedback state, and DFA false/null. Miniapp run `36822620989` performed
no upload. This evidence establishes neither byte identity nor the prior
`latest` target or any transition from it.

This replacement preapproval starts from exact protected main
`ac1bfd37cd1c79064b3920bee33c689f106f1c58`. PR #853's comment, validation,
implementation envelope and materialized approval files are PR/base/head-bound
and do not transfer. A new trusted validation run, envelope and exact
source-backed human package remain pending. Evidence Review and SDR remain draft,
`reviewed_on` remains null, and runtime remains inactive.

Rollback preparation defaults to inactive PR839 source
`9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2`, backend run `36367840399`, deploy job
`108757706180`, attempt 1, with rerun deadline `2026-10-28T01:55:43Z`. Its
`sync_config=false` path skipped settings synchronization and telemetry cutover while
capture/quiesce/deploy/restore succeeded, so a rerun captures and restores the
current feedback value and preserves current production `false`. Old readiness has
no `dfa_policy`; verification binds exact source SHA and readiness/database evidence
to the completed exact-source synthetic PostgreSQL startup/state/rights and real
inactive-guard evidence in
`docs/ops/incidents/ir-dfa-readiness-recovery-20260928.md` lines 56–60. That record
also preserves the historical no-blind-rollback boundary. No fresh exact-`9e703444`
test receipt was produced. Operations must recheck run retention, attempt
eligibility and deployment/Labs queue state immediately before use. This is the
viable preserve-`false` default, not fresh Quality recertification, a retained
package or a live rollback claim.

The newer source `8dcd9b4f2905e29376f9e17126ca3bd2b6720342`, backend run
`36445536979`, attempt 1, remains an alternative until
`2026-10-28T15:41:49Z`. It used `sync_config=true`; settings synchronization and
telemetry cutover ran, so rerunning it would select configured repository intent
`PRAXYS_ENABLE_FEEDBACK_PUBLICATION=true` and may change current production
`false` to `true`. It requires explicit separate authority for that reconciliation
or a separately validated preserve-`false` route. An ordinary activation-only push
changes no deployment/configuration path, uses `sync_config=false`, preserves the
captured current `false`, and may activate DFA without changing feedback. These
facts prove neither an outage nor permission to flip settings. Fresh Quality
byte-identity evidence is scoped only to the newer source's actually compared
migration, DFA, rights and dependency surfaces. Its task-local comparison archive
is `/tmp/praxys-dfa-activation-20260930.E4E4cL/quality-rollback-8dcd.6TEkta/source.tar`,
SHA256 `348559b39acbdd11c45c2c050787fa620f9fafb7db9ff28925281ac11889b93c`;
it does not transfer to `9e703444`, attest deployed package/runtime settings or
constitute a live rollback rehearsal.
