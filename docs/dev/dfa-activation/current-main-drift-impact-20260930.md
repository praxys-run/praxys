# DFA activation current-main drift impact — 2026-09-30

Owner: Engineering execution evidence. Status: implementation review pending;
not independent Verification Evidence and not science, release, or rollback
approval.

This review compares the prior activation base
`994d4ded39316615a6aa119265de8e2ef5dde301` with trusted main
`0c82ce26a23856c09f620708a23cb80380b9c555`. Exactly 34 files named by
`config/science-implementation-coverage.json` changed. No DFA numerical,
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

Rollback preparation uses preferred inactive source
`8dcd9b4f2905e29376f9e17126ca3bd2b6720342`, backend run `36445536979`, attempt 1,
with rerun deadline `2026-10-28T15:41:49Z`. A rerun rebuilds source, not a retained
package. `sync_config=false` means missing current/original feedback-positive intent
is a blocker, not an inferred setting. Independent synthetic PostgreSQL and rights
verification and Operations eligibility checks remain required; no live rollback is
claimed.
