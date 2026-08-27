# ODR-2026-08-26-cn-provider-topology

- **Status:** **PROPOSED — BLOCKED PENDING INDEPENDENT AND HUMAN REVIEW**
- **Proposal date:** 2026-08-26
- **Reconciled:** 2026-08-27
- **Decision date:** Not decided
- **Artifact implementation status:** logical-contract Markdown proposal
  reconciled to frozen implementation commit
  `635e5042dbb1f083bd8b6093a6d8488228b6a558`; not an accepted or schema-backed
  decision record
- **Owner role:** Operations
- **Production authority:** None. This proposal does not authorize setting a
  production variable, publishing a Miniapp release, deploying enforcement,
  changing CORS or DNS, or stopping a service.

## Decision record

- **id:** `ODR-2026-08-26-cn-provider-topology`
- **schema_version:** `1`
- **decision_type:** `operations-decision-record`
- **owner_role:** `Operations`
- **question:** Should Praxys operate the first authenticated China release
  with static `.cn` delivery on Tencent EdgeOne, `.run` delivery through
  Cloudflare to Azure, and one DNS-only Azure API/data plane, and what staged
  rollout, rollback floor, emergency stop, monitoring, and release-evidence
  contract must constrain that topology?
- **options:**
  1. Keep the current Azure-hosted `.run` service only and defer authenticated
     `.cn` and Miniapp launch.
  2. Use the proposed split frontend topology while retaining the shared Azure
     East Asia (Hong Kong SAR) API and data plane.
  3. Build a mainland-local API and data plane before launch.
  4. Proxy the shared API through EdgeOne or Cloudflare.
- **recommendation:** Conditionally adopt option 2 only after human acceptance
  of this record and every gate below. Until then, option 1 remains the
  effective production state. Do not use option 4: `api.praxys.run` remains
  DNS-only and neither frontend provider becomes an API or authenticated-data
  intermediary. Option 3 remains a future risk-reduction alternative, not part
  of this rollout.
- **rationale:** The split topology keeps build secrets and authenticated data
  out of the static `.cn` host, preserves the existing Azure identity,
  database, credential, and monitoring controls, and makes frontend entry
  points reversible through provider and DNS controls. It also introduces a
  cross-border processing decision, two frontend providers, a shared API
  failure domain, manual WeChat promotion, and a one-way privacy rollback
  floor. Those consequences require staged activation and authenticated human
  authority.
- **dependencies:**
  - Final operator acceptance of
    [`PIPIA-CN-2026-08-25-01`](./cn-personal-information-impact-assessment.md).
  - Architecture and Trust decision handoffs for the provider, shared API, and
    cross-border boundaries.
  - Independent Quality verification of the exact merged tree and release
    journey.
  - Protected-`main` merge of the complete privacy-capable change, after which
    the exact full `CN_PRIVACY_FLOOR_SHA` can be known. This dependency blocks
    only China-capable validation/release, not ordinary filing-free `.run`
    deployment.
  - A permanent approved store for aggregated Release Evidence; 90-day GitHub
    artifacts are inputs, not the durable record.
- **review_route:** Pending. No retained independent Decision Review Router
  artifact accepts this ODR. The documentation-reconciliation Work Contract
  records `decision_review: false` for that documentation task only; it does
  not decide this Operations proposal or grant production authority.
- **outcome_plan:** If accepted, execute the ordered stages below with a hold
  after each stage, retain the exact Release Evidence, observe availability,
  latency, capacity, privacy-floor rejection, and provider signals, and either
  proceed, hold, or disable the China entry points without crossing the
  rollback floor.
- **digest:** **PENDING HUMAN ACCEPTANCE.** No immutable accepted decision
  digest exists. Acceptance must cite this file at an exact merged commit and
  the exact full privacy-floor SHA; a branch name or this proposal date is not
  an acceptance identifier.

## Authoritative Delivery Work Contract linkage

This proposed Operations record is an artifact dependency of the current
authoritative Work Contract. The linkage is exact and durable, but does not
accept this record, grant production authority, or record a Decision Review
outcome:

- **classification_digest:**
  `sha256:ea5b438a17c6b0931f9e03a81606a55893e193438742364b8597e3b6dee34f8f`
- **route_digest:**
  `sha256:858b1429ea3e90b307923752d783f0ba9bc2665f978ddb2ef9381ddeae4216ab`

The frozen branch has a passing repository agent preflight and an independent
Trust implementation review with no high-confidence blocker. Architecture
acceptance, human Trust/PIPIA acceptance, final merged-tree and provider
journey verification, and permanent Release Evidence remain unresolved. This
Operations proposal does not substitute for them.

## Reconciled implementation and evidence boundary

Frozen implementation commit
`635e5042dbb1f083bd8b6093a6d8488228b6a558` implements fail-closed China
defaults, ordinary `.run` deploys that omit `.cn` CORS, exact registry
validation, runtime readback and CORS-denial logic, workflow evidence
artifacts, digest-bound append-only Terms receipts, registration compensation,
bounded stale-policy rights routes, per-user background Terms checks,
purpose-specific optional-processing authorization, and fail-closed private
feedback screenshot deletion. The repository agent preflight passed on this
commit. These are verified draft safeguards only.

No live provider query or Miniapp upload evidence, runtime readback, DNS/TLS
cutover, permanent Release Evidence store, alert provisioning, or rollback
rehearsal occurred. Export completeness and streaming remain blocked by
separate Product, Architecture, and Trust decisions. Legal/PIPIA approval,
receipt/deletion retention, registry lifecycle authority, production and
emergency authority, and provider/live-runtime evidence remain unresolved.

## Proposed provider topology

| Surface | Provider path | Runtime and data boundary | Operational constraint |
|---|---|---|---|
| `praxys.cn`, `www.praxys.cn` | EdgeOne Makers project `praxys-cn`, global area with mainland availability | Static HTML, JavaScript, CSS, filing metadata, and ordinary edge delivery logs only | Protected `main`, read-only repository grant, no build secrets, managed HTTPS, exact source/manifest evidence |
| `praxys.run`, `www.praxys.run` | Cloudflare Free → Azure App Service `praxys-frontend` | Cloudflare proxies only the filing-free international frontend | `Full (strict)`; proxy one hostname at a time; no `Cache Everything` rule |
| `api.praxys.run` | DNS-only → Azure App Service `trainsight-app` | Shared authentication, API execution, credentials, database access, and essential telemetry in Azure East Asia (Hong Kong SAR) | Never proxy through Cloudflare or EdgeOne; exact `.cn` browser CORS origins only after enforcement is verified |
| WeChat Miniapp | Tencent WeChat distribution → `api.praxys.run` | WeChat supplies login/distribution services; authenticated Praxys processing remains on the shared Azure API | Proposed production floor `2026.08.1` or newer, mapped to the full source SHA and deterministic `wechat:robot-1:<version>` locator; actual upload/publication evidence remains required |
| Primary data | Azure Database for PostgreSQL `praxys-pg` and existing Azure dependencies | No mainland-local application database or regional API replica is introduced | Existing backup, deletion, encryption, and 30-day backend telemetry boundaries remain in force |

EdgeOne and Cloudflare are separate frontend delivery providers, not regional
application failover. The API, database, sync, credentials, and optional
processing remain a shared failure domain. A Git-triggered EdgeOne build is not
a public release while the `.cn` custom domains remain unbound.

### Client and deployment floor semantics

- The `.cn` web artifact sends `cn-web`, a 12-character client/build version,
  the exact 40-character source SHA, and the current notice/digest/API-contract
  tuple. The Miniapp sends `wechat-miniapp`, CalVer, the exact 40-character
  source SHA, and the same current legal/API tuple. The registry separately
  binds the 12-character `source_id` to that full commit.
- The API rejects notice-incapable `.cn` and detected WeChat clients before
  personal routes. It also independently requires the current server-side
  Terms receipt.
- These request headers are release identifiers, not cryptographic
  attestation. Authentic source provenance comes from the protected-main
  history, workflow artifacts, EdgeOne deployment record, and WeChat release
  record.
- `CN_PRIVACY_FLOOR_SHA` is an ancestry floor. It blocks deployment of a commit
  before the floor, but it does not prove that a descendant has not reverted a
  control. Required CI, review, and exact release checks must continue to
  verify the current tree.

## Capacity and reliability constraints

- This proposal adds no API, database, or App Service capacity and no
  deployment slot. Azure rollback remains a new deployment of a known-good
  descendant.
- The initial release remains within the existing invitation/private-alpha
  scope. Expanding traffic or adding a geographic redirect is a separate
  decision.
- Existing API readiness, database-health, PostgreSQL connection, Today
  latency, sync/provider, and availability alerts remain the capacity and
  reliability guardrails. This record creates no new SLO.
- The `.cn` availability pairs must move together from
  `provisioned-disabled` to `live` only when their public hosts are ready.
  San Jose and Hong Kong outside-in samples are required before the rollout
  hold can clear.
- A readiness failure, manifest/source mismatch, Sev 1 availability signal,
  accepted stale client, rejected current Miniapp, unexpected CORS origin, or
  unresolved capacity alert stops progression. Operations records the signal
  and chooses hold or rollback; success is never inferred from DNS propagation
  alone.

## Proposed staged rollout

Every stage is a hold point. Stage 0 is repository preparation under normal
protected-branch authority. Ordinary filing-free `.run` backend and Azure
frontend deployment remains operable with fixed disabled privacy controls;
China-capable validation, EdgeOne artifact preparation, and Miniapp publication
remain floor/registry gated. **Stages 1–5 are production actions and none is
authorized while this record remains PROPOSED — PENDING HUMAN ACCEPTANCE.**

### Stage 0 — Merge the complete privacy floor

1. Merge the reviewed, complete privacy-capable change through protected
   `main`. Do not preconfigure the floor to an unmerged branch or abbreviated
   SHA.
2. The ordinary backend and Azure frontend lanes may deploy `.run` with China
   processing and optional external processing fixed disabled and `.cn` CORS
   absent. EdgeOne unpublished preparation fails closed while the exact floor
   and disabled-runtime evidence are absent; registry-authorized China
   validation and Miniapp publication additionally require the exact registry.
   Do not bypass those China gates.
3. Record the exact full protected-`main` merge SHA. EdgeOne may attempt that commit through its Git integration, but its
   China preflight remains blocked until the exact floor and disabled-runtime
   evidence exist. Preparation is not registry authorization; do not bind
   public domains or accept it as released.

### Stage 1 — Set `CN_PRIVACY_FLOOR_SHA` after merge

1. Obtain the still-pending human decisions, including acceptance that cites
   this record at the merged commit and the exact floor SHA.
2. Set `CN_PRIVACY_FLOOR_SHA` to that first complete privacy-capable
   protected-`main` commit, then read it back and verify that it is a
   40-character SHA and an ancestor of every candidate.
3. Keep that value as the rollback floor. Advancing it narrows recovery and
   requires a new accepted decision; clearing or lowering it is not rollback.
4. Do not rerun backend or frontend deployment yet.

### Stage 2 — Establish the disabled backend baseline

1. Deploy the protected-`main` backend candidate through the ordinary lane,
   retaining all five fixed privacy switches, disabled `.cn` CORS, readiness,
   privacy contract, API version, and deployed source SHA.
2. Do not populate a `cn-web` registry entry yet: its exact provider deployment
   ID does not exist until EdgeOne completes Stage 3.
3. Verify China non-rights processing remains disabled and rights routes remain
   available. This baseline cannot set the kill switch false or add `.cn`
   CORS.

### Stage 3 — Deploy updated `.run` and prepare the `.cn` artifact

1. Dispatch `deploy-frontend-appservice.yml` from protected `main`.
2. Verify the current Terms and Privacy content, rights-only stale-Terms
   actions, and the quiet provider notice for every supported connector on
   `praxys.run`.
3. The Azure `.run` deployment remains independent of the China floor. EdgeOne
   artifact preparation additionally requires the exact floor and matching
   disabled backend runtime readback, but no not-yet-created provider ID or
   registry authorization; otherwise it is skipped fail closed.
4. Record the Azure deployment receipt and the independent EdgeOne
   source/config/manifest/preflight digests. After EdgeOne creates the disabled
   candidate, retain its exact provider deployment ID and successful provider
   status, then construct the separately reviewed exact registry entry. Keep
   `.cn` custom domains unbound and `.cn` CORS absent.

### Stage 4 — Validate the registry and prepare the Miniapp

1. Manually dispatch `deploy-backend.yml` from protected `main` with
   `china_release_validation=true` and configuration reconciliation enabled.
   Require exact registry bytes and digest/count, all five fixed privacy
   switches, disabled `.cn` CORS, readiness, privacy contract, API version, and
   deployed source SHA. Verify stale or unlisted clients remain rejected.
2. Create `miniapp-2026.08.1` at the exact disabled backend candidate commit.
   The upload workflow requires the same floor, registry, disabled runtime,
   readiness, CORS denial, and deployed backend SHA evidence before upload.
3. Record the full source SHA, workflow run and attempt, robot 1 upload result,
   strict version/ref metadata, and deterministic
   `wechat:robot-1:<version>` provider locator. The locator is robot-and-version
   evidence, not a provider-generated opaque ID; retain separate evidence that
   the upload actually succeeded.
4. Promote to 体验版 and submit for review only under the still-pending human
   production authority. Do not publish or activate processing based on an
   upload artifact alone.
5. Confirm the candidate carries the expected source and policy tuple, direct
   data export/account deletion rights, and the reviewed `.run` connector
   handoff.

### Stage 5 — Future separately authorized activation and provider cutover

This stage is intentionally not implemented by the ordinary deploy workflows.
It requires a separately reviewed, human-authorized operation. Any future
accepted procedure must:

1. Add only `https://praxys.cn` and `https://www.praxys.cn` to Azure App Service
   CORS, verify both preflights include all six `X-Praxys-*` request headers,
   and reject HTTP, wildcard, preview, and unrelated origins.
2. Bind the two `.cn` custom domains to the accepted EdgeOne deployment, wait
   for managed HTTPS, verify source/manifest/filing evidence, then enable each
   `.cn` availability test and alert as a pair.
3. Enable `EDGEONE_CN_PUBLIC_VERIFY_ENABLED` only after both names resolve to
   the accepted project, then retain the successful public verification
   artifact.
4. Migrate `.run` authoritative DNS to Cloudflare only with the saved zone and
   DNSSEC sequence in [`tencent-frontend.md`](./tencent-frontend.md), proxy
   `www` and apex one at a time with `Full (strict)`, and keep
   `api.praxys.run` DNS-only.
5. Keep geographic redirect enablement outside this launch.

No current workflow sets `PRAXYS_DISABLE_CN_PROCESSING=false`, adds `.cn` CORS,
publishes a Miniapp, binds DNS, or grants acceptance.

## Rollback floor and recovery

The public release makes the privacy boundary a one-way floor:

- Backend, frontend, and Miniapp deployment candidates must descend from
  `CN_PRIVACY_FLOOR_SHA`.
- An EdgeOne rollback candidate must have retained source/manifest evidence and
  descend from the floor.
- A Miniapp rollback candidate must be version `2026.08.1` or newer and have a
  retained full-source-SHA/deterministic-locator mapping plus upload-success
  evidence.
- A protected-main revert may restore behavior only when the resulting commit
  retains all floor controls and passes current verification. Ancestry alone
  is insufficient.
- Never remove, lower, or bypass the floor; re-tag a pre-floor commit; select a
  notice-incapable EdgeOne deployment; or restore an older Miniapp as a
  temporary mitigation.

For an ordinary application defect, deploy a verified known-good descendant or
merge a forward fix through protected `main`. There are no Azure deployment
slots. For an EdgeOne defect, select only a known-good floor-compatible
deployment and then converge protected `main`. For a Cloudflare frontend
defect, follow the certificate-safe gray-cloud sequence in the regional
runbook. If no floor-compatible artifact is healthy, disable the affected
China entry points rather than crossing the floor.

## Emergency disable path

This is a human-directed incident path, not standing authorization:

1. Freeze promotions and deployment reruns, retain `CN_PRIVACY_FLOOR_SHA`, open
   an incident record, and preserve the current provider/workflow evidence.
2. For `.cn` web exposure, remove the two `.cn` CORS origins and disable or
   unbind the EdgeOne custom-domain/DNS route under operator control. Verify
   both the intended unavailability and the absence of `.cn` CORS. CORS or DNS
   alone does not revoke tokens and cannot stop a non-browser API client.
3. For Miniapp exposure, use the confirmed WeChat operator suspension or
   withdrawal path. The repository workflow can upload but cannot unpublish a
   public release; the exact emergency platform control must be rehearsed and
   recorded before launch.
4. Preserve `.run` and the shared API where safe. Set
   `PRAXYS_DISABLE_CN_PROCESSING=true` to stop non-rights China-client
   processing at the shared API while preserving export, deletion, provider
   disconnect, and private feedback-image access. If harmful processing can
   still continue through a channel outside that classified boundary, stopping
   `trainsight-app` is the fail-closed last resort. It affects every region and
   requires separate, explicit operator authorization at incident time.
5. Verify mitigation from outside the provider, keep the relevant monitoring
   state consistent with the intentional disablement, and do not claim
   mitigation or recovery until the observed state matches the incident
   decision.
6. Recover only with an accepted forward fix or known-good floor-compatible
   artifact, then repeat the staged CORS, public-host, monitoring, and evidence
   checks.

## Monitoring and Release Evidence contract

This section defines required evidence; **it is not Release Evidence and makes
no deployment claim**.

The final aggregated record must identify:

- the accepted ODR artifact commit/digest, accepted Architecture and Trust
  records, final operator-approved PIPIA, and authenticated release
  authorization;
- `CN_PRIVACY_FLOOR_SHA`, the exact deployed backend/frontend SHAs, workflow
  run IDs/attempts/conclusions, API version/readiness, and effective
  non-secret privacy settings;
- Miniapp tag/version, full source SHA, 12-character registry source ID, deterministic
  `wechat:robot-1:<version>` locator, retained robot 1 upload-success evidence,
  and WeChat review/publication status, plus positive
  `2026.08.1` and negative older/missing-client checks;
- Azure frontend package receipt, EdgeOne project/deployment IDs, protected
  source SHA, GitHub and served manifest digests, public deployed SHA, and
  known-good rollback deployment;
- exact CORS inventory and preflight results, DNS answers, nameservers,
  certificate issuer/expiry, Cloudflare zone/SSL mode, EdgeOne custom-domain
  state, and proof that `api.praxys.run` stayed DNS-only;
- resource IDs and enabled state for each outside-in web-test/alert pair,
  successful San Jose/Hong Kong samples, API health/readiness, and relevant
  backend request, latency, database, sync, and provider-alert observations;
- the approved rollback candidates and evidence that each respects both the
  commit and Miniapp floors; and
- the permanent evidence location and retention. GitHub's 90-day artifacts
  and short-lived job logs are supporting inputs only.

Because `.cn` browser telemetry and Miniapp product events are intentionally
disabled, Operations must use outside-in checks and minimized backend
telemetry. The current implementation has no dedicated
`CLIENT_PRIVACY_UPDATE_REQUIRED` metric; synthetic response checks provide
release proof, while aggregate backend `428`, `4xx`, `5xx`, readiness, and
latency observations provide live guardrails. If code-specific live rejection
alerting is required for acceptance, Engineering must add a privacy-safe signal
and Quality must verify it before cutover.

## Unresolved human gates and blockers

| Gate | Current state |
|---|---|
| Operations decision | **PROPOSED — PENDING HUMAN ACCEPTANCE**; no accepted digest |
| Decision routing | Authoritative documentation Work Contract records `decision_review: false`; this is not acceptance or production authority |
| Architecture boundary | Required Architecture Decision Record/handoff is not accepted |
| Trust and cross-border boundary | Independent review found no high-confidence implementation blocker at `635e5042dbb1f083bd8b6093a6d8488228b6a558`; Trust Decision Record acceptance and the `PIPIA-CN-2026-08-25-01` operator decision remain pending |
| Exact release verification | Repository agent preflight passed for the frozen branch commit; independent evidence for the final merged tree and provider journey does not yet exist, and no live provider query, upload-success query, or runtime readback was performed |
| Production authority boundary | No production-environment approval gate or activation workflow is accepted or implemented; repository variables cannot substitute for authenticated human authority |
| Registry lifecycle / receipt authority | Exact registry validation and append-only Terms receipts exist at the frozen implementation commit, but no accepted registry lifecycle schema/authority, legal values, or receipt-retention decision exists |
| Privacy floor | Exact SHA is unknowable until merge; `CN_PRIVACY_FLOOR_SHA` must remain unset until the accepted post-merge gate |
| Miniapp | No `2026.08.1` public release or upload success is recorded; `wechat:robot-1:<version>` is only a deterministic locator, and the source mapping plus rehearsed emergency suspension path remain pending |
| Monitoring | Workflow safeguards and evidence shapes exist, but no alert provisioning, `.cn` live samples, or action-group verification occurred |
| Provider cutover | `.cn` CORS, EdgeOne public domains, Cloudflare/DNS/DNSSEC, certificates, and public verification are pending |
| Release Evidence retention | Permanent approved evidence store/location is not recorded |
| Shared API stop | `PRAXYS_DISABLE_CN_PROCESSING` exists but has not been rehearsed or authorized for production use; global stop still needs separate incident-time authority |

No public China rollout may proceed while any required gate remains unresolved.

## Related

- [`tencent-frontend.md`](./tencent-frontend.md)
- [`deploy.md`](./deploy.md)
- [`config-and-secrets.md`](./config-and-secrets.md)
- [`environment.md`](./environment.md)
- [`monitoring-and-alerts.md`](./monitoring-and-alerts.md)
- [`cn-personal-information-impact-assessment.md`](./cn-personal-information-impact-assessment.md)
- [`../dev/adr-2026-08-26-cn-client-provenance-and-receipt-semantics.md`](../dev/adr-2026-08-26-cn-client-provenance-and-receipt-semantics.md)
- [`tdr-2026-08-26-cn-privacy-control-boundary.md`](./tdr-2026-08-26-cn-privacy-control-boundary.md)
- `.github/workflows/deploy-backend.yml`
- `.github/workflows/deploy-frontend-appservice.yml`
- `.github/workflows/miniapp-publish.yml`

---
_Proposed: 2026-08-26 · Owner: Operations · Acceptance: PENDING_
