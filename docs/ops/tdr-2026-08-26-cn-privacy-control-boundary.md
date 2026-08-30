# TDR-2026-08-26-cn-privacy-control-boundary

- **Status:** **Proposed — implementation verified; blocked pending human
  review and production evidence**
- **Proposal date:** 2026-08-26
- **Reconciled:** 2026-08-27
- **Decision date:** Not decided
- **Owner role:** Trust
- **Artifact scope:** Logical-contract proposal only
- **Production authority:** None. This record does not approve the PIPIA,
  release topology, deployment, Miniapp publication, CORS, DNS, runtime
  configuration, or production-data processing.

## Decision record

- **id:** `TDR-2026-08-26-cn-privacy-control-boundary`
- **decision_type:** `trust-decision-record`
- **owner_role:** `Trust`
- **question:** What security and privacy controls must hold before Praxys may
  operate the `.cn` web and WeChat Miniapp channels against the shared overseas
  API?
- **recommendation:** Preserve a channel-based boundary, make accepted release
  identity and legal receipts server-authoritative, keep privacy rights
  available without new Terms acceptance, and fail closed for Azure AI emergencies and independently authorized external
  feedback publication.
- **review state:** An independent Trust review of implementation commit
  `635e5042dbb1f083bd8b6093a6d8488228b6a558` found no high-confidence
  Trust implementation blocker or security vulnerability for the dormant,
  fail-closed baseline. Human acceptance and production approval are not
  recorded. The implementation review becomes stale after any Trust-relevant
  change.
- **routing metadata:** Reconciled to authoritative Work Contract task
  `artifact-reconciliation`; the contract records `decision_review: false`.
  This linkage imports no Trust approval or production authority.
- **classification digest:**
  `sha256:ea5b438a17c6b0931f9e03a81606a55893e193438742364b8597e3b6dee34f8f`
- **route digest:**
  `sha256:858b1429ea3e90b307923752d783f0ba9bc2665f978ddb2ef9381ddeae4216ab`
- **implementation evidence:** Commit
  `635e5042dbb1f083bd8b6093a6d8488228b6a558` over
  `740dd72cc6eacc33cf19218b1158a27ca91f09bf`; the repository agent preflight
  passed on that frozen implementation.
- **record digest:** Pending human acceptance of this proposed decision.

## Residual authority blockers

Frozen implementation commit `635e5042dbb1f083bd8b6093a6d8488228b6a558`
implements deterministic workflow guards, exact runtime readback and `.cn`
CORS-denial checks, evidence artifacts, an exact release-registry parser,
digest-bound append-only Terms receipts, registration compensation, bounded
rights access, per-user current-Terms checks, a centralized AI emergency stop, and exact
per-submission feedback-publication authorization. Those are verified draft safeguards, not an accepted
production gate, registry lifecycle authority, legal decision, provider
release, or activation procedure. No live provider query or runtime readback,
DNS/TLS cutover, permanent Release Evidence store, alert provisioning, or
rollback rehearsal occurred.

Human review is still required for the final legal basis and PIPIA, the
channel-versus-person interpretation, acceptance of sensitive cross-border and
shared-API residual risk, receipt/deletion retention, and production or
emergency authority. Export coverage and streaming remain blocked by separate
Product, Architecture, and Trust decisions. Registry lifecycle, permanent
evidence retention, and provider/live-runtime evidence remain unresolved
release prerequisites.

## Scope

The control applies to known Praxys delivery channels:

- `cn-web`, identified by the exact Praxys `.cn` browser origins; and
- `wechat-miniapp`, identified by the WeChat authentication routes and
  platform-managed Miniapp transport signals.

It does not classify a person by nationality, citizenship, residence, IP
geolocation, locale, provider region, or current physical location. Direct API
clients and `.run` are separate channels and must not be silently described as
covered by the `.cn` or Miniapp disclosure control.

Client headers are untrusted identifiers. They cannot authenticate a person,
authorize an account, select credentials, or prove that reviewed code is
running.

## Current draft implementation boundary

Frozen implementation commit
`635e5042dbb1f083bd8b6093a6d8488228b6a558` defaults the China client boundary
off. Ordinary `.run` deploys write `PRAXYS_DISABLE_CN_PROCESSING=true`, keep
China processing disabled while ordinary Azure AI availability is expressed by
releasing its negative emergency stop, preserve that stop's exact pre-deploy
operator state, keep feedback publication disabled, remove `.cn` CORS, and
include exact readback/evidence steps. The exact registry
schema binds channel/version, a 12-character source ID, an exact 40-character
protected-`main` commit, the current notice version and legal digest, API
contract, and provider locator/ID.
For production Miniapp candidates the locator is deterministically
`wechat:robot-1:<version>`; it is not a provider-generated opaque release ID.
Robot 5 uses synthetic development versions and is never registry authority.

Terms acceptance is bound to the exact version and digest and recorded in an
append-only receipt table; bounded export, disconnect, deletion, sign-out, and
owned-feedback-image routes remain available to stale-policy users. Account
deletion fails closed if private feedback screenshot deletion fails and retains
its locators for retry. Ordinary Azure AI is an enumerated service condition,
not optional processing; it requires current Terms and the server-owned negative
emergency switch; no client opt-out or positive-purpose boolean is authority.
External feedback publication retains its independent positive enable, kill
switch, and exact per-submission consent. These statements describe
repository behavior only, not accepted policy, a deployed state, or live
verification.

## Required controls

### Approved client releases

Every known China-channel request that can begin personal-data processing must
match one exact server-owned active release entry. The entry binds at least:

- channel;
- client build/version;
- client-visible source identifier and full protected-`main` source commit;
- current notice and policy-bundle version/content digest;
- reviewed artifact and provider locator/ID; for Miniapp the locator is exactly
  `wechat:robot-1:<version>` and upload success needs separate retained evidence; and
- active, disabled, revoked, or superseded lifecycle state.

Well-formed but unlisted identifiers, version ranges, wildcard sources, and
mere descent from a floor commit fail closed. The request tuple identifies an
entry; it is not authorization.

### China processing emergency control

A deployment-wide negative kill switch must stop ordinary `.cn` and Miniapp
personal-data processing without disabling authenticated export, provider
disconnect, account deletion, sign-out, public legal/support content, or
incident/status information. The disabled response must be explicit,
non-cacheable, observable, and rehearsed before launch.

### Legal receipts

Terms acceptance and Privacy read acknowledgement must be submitted with the
exact displayed policy version and canonical content digest. The API rejects a
missing or mismatched tuple without updating the account.

Receipt evidence is append-only and records the authenticated subject,
server timestamp, action, version, content digest, locale, and server-classified
channel. For an approved China client it also records the registry-bound client
version, source SHA, notice version, and provider release identifier. Mutable
`users` fields may remain a current projection but are not the evidence ledger.
Account deletion removes or pseudonymizes receipts according to the accepted
retention decision; no retention exception is authorized here.

The local pre-transfer China notice remains client-instance scoped. A Terms
receipt from another channel cannot prove that the local notice preceded the
first transfer.

### Rights without coercion

Current Terms acceptance and a client upgrade must not be prerequisites for:

- authenticated data export;
- provider disconnect;
- account deletion;
- local sign-out; or
- access to the Privacy Policy and support channel.

The middleware and Terms gate must use exact method/path allowlists. Rights
routes still require authentication and per-account authorization, never invoke
Azure AI or external feedback publication, and must not expose credentials. The Miniapp must provide
a usable export path for WeChat-only accounts rather than only copying a web
login URL.

### Azure AI and external publication

Ordinary Azure AI processing requires a current Terms receipt and the
server-owned negative emergency switch to be released. The switch defaults to
the stopped state when missing, blank, or malformed and is checked before each
provider path. Activating it does not activate China processing, which remains
independently registry-gated and globally disabled. An AI stop does not fail
core readiness or stop sync and deterministic metrics; AI-only functions report
unavailable and deterministic output is not branded as AI.

External feedback publication remains a separate optional action. It requires
the publication enable, a clear publication kill switch, and the exact
per-submission grant. Terms acceptance never grants publication, and screenshots
remain private.

### Data export — policy and completeness blocked

The frozen implementation has a caller-owned JSON export and tests, but its
coverage and streaming strategy are not accepted or complete. Separate human
Product, Architecture, and Trust decisions must define the required inventory,
binary asset path, scale/streaming boundary, and completion standard. Subject
to those decisions, maintain a model-to-rights inventory and export
caller-owned personal information, including account/contact data, non-secret
connection metadata, activity samples, feedback, AI insight records, and legal
receipts. Never export passwords, hashes, access tokens, provider credentials,
encryption material, internal authorization secrets, or another user's data.
Any binary asset not included directly must be explicitly identified with a
usable rights path rather than silently omitted.

### Provider disclosure continuity

Every provider-connection journey originating from `.cn` or the Miniapp must
show the same quiet just-in-time recipient/category/overseas-processing
disclosure. A Miniapp handoff must not route to a surface that suppresses that
notice.

### Release provenance and operations

Production candidates must be exact commits reachable from protected `main`,
pass required checks for the frozen tree, and map to retained artifact and
provider-release evidence. Current-workflow ancestry checks are not an
irreversible control: historical reruns and direct provider actions remain
outside them unless credentials are moved to protected environments and old
credential paths are revoked.

Launch evidence must include positive and negative CORS tests, effective
runtime-setting readback, monitor/action-group samples, old-client rejection,
rights-path success, approved rollback candidates, and emergency-disable
rehearsal. Evidence retention must outlive ordinary CI artifact expiry.

## Human-only decisions

This proposal does not decide:

- whether contract necessity is the accepted legal basis for the disclosed
  core overseas processing;
- whether the PIPIA's residual risk is accepted;
- the final channel-versus-person legal interpretation;
- receipt retention after account deletion;
- whether the shared global API blast radius is acceptable; or
- production rollout, DNS, CORS, WeChat review, or emergency authority.

Those decisions require an authenticated operator or other named human
authority bound to the final content digest and protected-main release.

## Implementation gates

- **Draft implemented and verified:** exact server-owned registry validation,
  China kill switch, version/digest-bound append-only Terms receipts,
  registration compensation and retry safety, bounded stale-policy rights
  routes, per-user background Terms checks, centralized Azure AI runtime/Terms authorization and independent
  per-submission publication consent, protected-main workflow safeguards, runtime/CORS
  readback logic, and evidence artifacts.
- **Not accepted or complete:** registry lifecycle authority, receipt and
  deletion-evidence retention, export coverage/streaming, and the permanent
  Release Evidence store.
- **No live evidence:** provider query/upload success, DNS/TLS cutover, runtime
  readback, alert provisioning, or rollback rehearsal.
- **Human blocked:** corrected PIPIA/legal decision, Architecture and Trust
  boundaries, registry authority, production activation, and provider
  evidence.

## Verification gates

Independent Quality and Trust verification must demonstrate:

- unknown but well-formed client source/build tuples are rejected;
- a disabled/revoked release is rejected;
- malformed or absent AI-stop settings cannot enable Azure AI calls;
- missing or stale policy version/digest cannot create a receipt;
- multiple accepted receipts remain as immutable history;
- stale clients can export, disconnect, delete, sign out, and reach legal
  support without accepting updated Terms;
- export is owner-isolated and excludes every credential-shaped field;
- Miniapp users can obtain an export without a web password;
- `.cn` and Miniapp provider handoffs preserve the disclosure;
- candidates are reachable from protected `main`; and
- the emergency control stops ordinary processing while rights remain
  available.

Until every applicable implementation, human-decision, and verification gate
is complete, China processing remains blocked and option 1 in the Operations
record remains effective. The authoritative documentation Work Contract does
not require decision review; that routing fact is not approval of this TDR.
