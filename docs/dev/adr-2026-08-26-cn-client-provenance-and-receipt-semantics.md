# ADR-2026-08-26-cn-client-provenance-and-receipt-semantics

- **Status:** **Proposed — pending independent and human review**
- **Proposal date:** 2026-08-26
- **Reconciled:** 2026-08-27
- **Decision date:** Not decided
- **Owner role:** Architecture
- **Artifact scope:** Logical-contract proposal only
- **Implementation status:** Draft safeguards are frozen at commit
  `635e5042dbb1f083bd8b6093a6d8488228b6a558` and passed the repository agent
  preflight, but are not merged, accepted, deployed, or live evidence. This
  document is not production evidence.
- **Production authority:** None. This record does not authorize a merge,
  migration, registry entry, credential use, deployment, Miniapp publication,
  DNS or CORS change, enforcement switch, or production-data operation.

## Decision record

- **id:** `ADR-2026-08-26-cn-client-provenance-and-receipt-semantics`
- **decision_type:** `architecture-decision-record`
- **owner_role:** `Architecture`
- **question:** What long-lived logical contract must distinguish the China
  release channels, approved client provenance, policy acceptance, processing
  notice acknowledgement, and background work without treating client metadata
  as identity or attestation?
- **recommendation:** Adopt the channel, approved-release registry,
  compatibility-tuple, and append-only receipt contracts below, using the
  existing API and primary PostgreSQL boundary. Add no service or datastore.
- **review state:** No independent approval or human acceptance is recorded.
  Architecture proposes this record and cannot approve it.
- **routing metadata:** Reconciled to authoritative Work Contract task
  `artifact-reconciliation`; the contract records `decision_review: false`.
  This linkage does not accept this ADR or grant production authority.
- **classification digest:**
  `sha256:893eaa8aab240dd9dbdc9048389feb9711a9bd47439b1d92ad2f82b3cc4a11ba`
- **route digest:**
  `sha256:28d3b9453e5e841ecb7dc0a8ba6e454e06a330c6b2178edd69ebb3c49eaa6229`
- **implementation evidence:** Commit
  `635e5042dbb1f083bd8b6093a6d8488228b6a558` over
  `740dd72cc6eacc33cf19218b1158a27ca91f09bf`.
- **record digest:** **Unresolved** pending independent Architecture and human
  acceptance of this proposal.

Values present in another proposed or pending artifact are not imported as
authority here. They must be independently reproduced and reviewed before an
accepted revision may cite them.

## Residual authority blockers

Frozen implementation commit `635e5042dbb1f083bd8b6093a6d8488228b6a558`
contains deterministic deployment safeguards, runtime readback logic,
exact-registry validation, CORS-denial checks, evidence-artifact generation,
digest-bound append-only Terms receipts, registration compensation, bounded
rights access, per-user background Terms checks, and purpose-specific optional
processing authorization. Those are verified draft implementation facts, not
accepted architecture policy or live evidence. No live provider query or
runtime readback, DNS/TLS cutover, permanent Release Evidence store, alert
provisioning, or rollback rehearsal occurred.

Human decisions remain required for legal and PIPIA approval, acceptance of the
shared-API and sensitive cross-border residual risk, receipt/deletion
retention, and production or emergency authority. Registry lifecycle,
provider/live-runtime evidence, and permanent evidence retention remain
unresolved release prerequisites. Export coverage and streaming remain blocked
by separate Product, Architecture, and Trust decisions and must not be
described as complete.

## Context and evidence boundary

Frozen implementation commit
`635e5042dbb1f083bd8b6093a6d8488228b6a558` implements:

- a `.cn` web channel identified as `cn-web`;
- a WeChat Miniapp channel identified as `wechat-miniapp`;
- client version, exact full source revision, and notice-version request
  headers;
- a local pre-transfer notice gate;
- an account-level server Terms/Privacy receipt;
- a source-ancestry deployment floor; and
- production negative switches for background AI and feedback publication.

Those changes are implementation facts, not evidence that controls are merged,
approved, released, or operating. The frozen commit implements an exact
environment-backed release registry. Each entry binds channel and client
version, a 12-character source ID, the exact 40-character protected-`main`
commit, current notice version and legal digest, API contract version, and a
provider locator/ID. Miniapp entries require the deterministic locator
`wechat:robot-1:<version>`. Robot 5 uses synthetic development versions and can
never authorize a registry entry. This implemented shape is not the accepted
append-only lifecycle registry proposed below.

The frozen commit also implements version-and-digest-bound, append-only Terms
acceptance receipts while retaining mutable user fields as projections. Stale
users retain bounded rights routes. Registration compensates if receipt
persistence fails. Scheduled/background processing rechecks current Terms per
user. Optional background AI and external feedback publication require both
operational enablement and purpose-specific authorization; admin review cannot
create publication consent. Account deletion fails closed on private feedback
screenshot deletion and preserves screenshot locators for retry. Neither the
receipt implementation nor the current legal version/digest is human-approved
by this ADR. Exact released source revisions, actual provider
upload/deployment success, accepted registry lifecycle authority, and a
permanent Release Evidence location remain unresolved.

## Constraints, horizon, reversibility, and affected systems

### Constraints

- Classification is by Praxys delivery channel, never by nationality,
  citizenship, IP geolocation, residence, account locale, or a person's
  current physical location.
- Request headers identify a claimed release; they do not attest to code,
  device, platform, person, or location.
- Authentication, authorization, per-user isolation, and encrypted provider
  credentials remain server-authoritative and independent of this contract.
- A notice acknowledgement is evidence that a disclosure was presented and
  read; it is not consent for core processing or optional AI.
- Rights to export, disconnect, and delete must not be conditioned on accepting
  updated service terms.
- The existing API and PostgreSQL architecture is preserved. No new service,
  regional API, database, or identity plane is selected.

### Time horizon

The near-term horizon is a staged first release of the `.cn` web and WeChat
Miniapp channels. The long-lived surface is the versioned compatibility tuple,
approved-release registry, receipt semantics, route classes, and rollback
floor. Field meanings cannot be repurposed within a schema version.

### Reversibility

Additive schema, shadow evaluation, and dual writes are reversible before
enforcement. Approved-release and receipt events are append-only while
retained; rollback disables readers or writes compensating status events
rather than deleting history. After a privacy-capable client is public,
rollback cannot restore a notice-incapable release. Operations must deploy a
known-good compatible descendant or disable the affected channel.

### Affected systems

The contract crosses the web client, Miniapp, API request boundary, account
policy gate, provider-credential flows, background jobs, PostgreSQL,
protected-branch build workflows, release evidence, and Operations controls.
It does not make a product-priority, legal-basis, Trust, Quality, or production
operations decision.

## Decision

### 1. Classify the release channel, not the person

`cn-web` and `wechat-miniapp` are release-channel identifiers. They describe
which Praxys artifact and disclosure journey originated a request.

- A request from the `.cn` web deployment is evaluated as `cn-web` even when
  the user is outside mainland China.
- A WeChat Miniapp request is evaluated as `wechat-miniapp` regardless of the
  user's nationality or location.
- Access to another Praxys channel from a mainland-China IP does not
  automatically reclassify the person or account.
- Account language, phone country code, provider region, browser timezone,
  GPS, citizenship, and IP-derived location must not participate in this
  classification.

Known `.cn` origin or WeChat transport/route signals require a matching channel
claim and approved compatibility tuple. Missing or conflicting metadata in a
known channel fails closed. Such origin, Referer, user-agent, route, and header
signals remain replayable identifiers, not proof of a genuine client.

### 2. Require a server-authoritative approved-release registry

Format checks, an abbreviated SHA, a CalVer floor, and an ancestry floor are
necessary release hygiene but are insufficient provenance. The API must
resolve every protected China-channel request against an approved-release
registry.

Each immutable approved-release record binds:

1. channel;
2. compatibility-contract schema version;
3. client build/version identifier;
4. client-visible source identifier;
5. exact full protected-`main` source commit;
6. built-artifact digest;
7. API contract version;
8. notice version and content digest;
9. Terms and Privacy bundle version and content digest;
10. provider release locator/ID (for a Miniapp, exactly the deterministic
    `wechat:robot-1:<version>` locator, never an opaque provider-generated ID);
11. approval/release-evidence reference; and
12. lifecycle event: proposed, approved, disabled, revoked, or superseded.

Approval and lifecycle changes are append-only events. An approved entry must
refer to one exact artifact and one exact public release. Ranges, wildcard
SHAs, “version or newer,” branch names, and syntactically valid but unlisted
values cannot authorize a request.

An abbreviated source identifier is permitted only as a lookup key when the
registry maps it unambiguously to one full commit. It is never provenance by
itself. A descendant of a privacy-floor commit is not automatically approved;
the exact descendant tree and artifact still require verification.

### 3. Use one explicit compatibility tuple

Every China-channel client request that can start personal-data traffic must
carry this versioned runtime tuple:

```text
T = (
  contract_schema,
  channel,
  client_version,
  source_id,
  api_contract_version,
  notice_version,
  notice_content_digest,
  policy_bundle_version,
  policy_bundle_content_digest
)
```

The API accepts `T` only when it exactly selects one active approved-release
record. The registry, not the request, supplies the full source commit,
artifact digest, platform/deployment release ID, and approval evidence.

The web build may use a source-derived build identifier and the Miniapp may use
CalVer, but the API must not infer provenance from either format. Changing any
tuple member creates a distinct compatibility claim. A valid tuple can be
copied by an arbitrary client, so matching it never authenticates a user,
authorizes an account, or proves execution of the reviewed artifact.

### 4. Bind receipts to immutable content, not a version label alone

Every receipted presentation must have an immutable content manifest. Its
digest is `sha256:` followed by 64 lowercase hexadecimal characters computed
over the canonical UTF-8 bytes of the versioned manifest. The manifest binds
document identity, locale, version, exact presented action wording, and the
ordered digests of the Terms, Privacy Policy, and China processing notice
included in that presentation.

The canonicalization procedure and manifest schema must be versioned and
shared by build, API, and verification tooling. Changing content without
changing the applicable digest is a build failure. Reusing a version with a
different digest is an incompatible release, not an update in place.

Actual manifest and content digest values are unresolved in this proposal and
must not be inferred from filenames, version constants, or the implementation
commit.

The server receipt ledger is append-only. A receipt event contains at least:

- server-generated receipt ID and server timestamp;
- authenticated account subject;
- receipt kind and action (`accepted` or `acknowledged-read`);
- scope (`account` or `client-channel`);
- channel when client-channel scoped;
- document/manifest version and content digest;
- locale presented;
- approved-release record ID when a client presentation is involved; and
- superseded/corrected event reference when applicable.

Clients cannot supply the account subject, server timestamp, approval state, or
canonical digest. Mutable account fields may remain as a cache or projection,
but they are not the evidence record.

### 5. Keep account-wide and client-specific receipts distinct

| Receipt | Scope | May satisfy | Must not satisfy |
|---|---|---|---|
| Terms acceptance plus Privacy read acknowledgement | Account-wide, exact policy bundle version/digest | The current account policy gate on any compatible client | The pre-transfer notice on a new client/channel; optional-purpose consent |
| China processing notice read acknowledgement | Client-channel, exact notice version/digest | Evidence for that account and channel after authentication | Another channel; account Terms acceptance; optional AI or marketing |
| Local pre-transfer acknowledgement | This browser storage/session or Miniapp installation/launch | Permitting that client instance to start its first personal-data request | Durable account evidence or another device/client |
| Optional-purpose authorization | Account and exact purpose/context/recipient/field set | Only the named optional processing | Core processing, another purpose, or a future changed context |

The local gate remains mandatory because the server cannot retrospectively
prove that notice preceded the first authentication transfer. After the
account is resolved, the client-specific acknowledgement is recorded
server-side against the approved release. A server receipt from another device
must not suppress the local pre-transfer gate on a fresh installation.

A receipt from `cn-web` cannot satisfy `wechat-miniapp`, or vice versa, even
when both display text with the same version. Conversely, a current
account-wide Terms/Privacy receipt may be reused across channels because it
records the account's policy action, provided each channel independently
satisfies its notice and release contracts.

Corrections, supersession, withdrawal, and revocation are new events. No
receipt row is overwritten. Append-only behavior does not override an accepted
erasure or retention decision: account deletion must delete or pseudonymize
receipt data as required by the approved Trust/retention policy while retaining
only a separately justified minimal deletion receipt.

### 6. Apply explicit surface semantics

| Surface | Required semantics |
|---|---|
| Public legal, product, status, and health surfaces | No account receipt. They must not initiate personal-data traffic. |
| Anonymous demo | Exempt only when all data is synthetic, no account/token is used, and no personal request, telemetry, sync, or background job starts. “Demo” is not a route-name bypass. |
| Authenticated or personalized demo | Treated as ordinary personal processing and subject to the full channel, release, notice, account, authorization, and credential contracts. |
| Authentication/bootstrap and pre-account collection | A compatible approved client and local pre-transfer notice are required for China channels. Account-wide receipt is not yet applicable. Only bounded bootstrap, policy, receipt, sign-out, and rights operations may proceed. |
| Ordinary account, sync, analysis, or plan request | Exact active compatibility tuple, local/client-channel notice, current account-wide policy receipt, authentication, and per-account authorization are all required. |
| Provider OAuth or credential submission | All ordinary requirements plus a just-in-time provider recipient/category notice. Credentials enter only the authenticated API credential plane, never the static frontend, release registry, or receipt payload. |
| Export, provider disconnect, account deletion, and sign-out | Must remain reachable without accepting updated Terms. Export, disconnect, and deletion still require authentication, per-account authorization, a compatible China client and pre-transfer notice, or an independently approved rights channel. They cannot invoke optional processing. |
| Background processing | A notice or Terms receipt is not purpose authorization. Enqueue records the triggering channel/release and applicable account/purpose state; execution rechecks account existence, deletion/cancellation fences, current required account policy, and any purpose-specific authorization before external transfer or persistence. |

If no approved client can complete export or deletion, an independently
verified support or rights path must remain available. The system must not
coerce policy acceptance as the price of account exit.

Optional AI remains separately authorized and off by default. China notice,
Terms acceptance, a source header, or an approved release cannot enable it.
Background AI and external feedback-publication switches remain fail-closed
until separately accepted Operations and Trust decisions authorize a change.
Deletion revokes credentials, cancels or fences queued work, and discards late
writes.

### 7. Enforce protected-main and credential-plane boundaries

An approved release must be built from an exact commit reachable from the
current protected `main` history. Tag, manual-dispatch, provider-build, and
abbreviated-SHA paths must not bypass that proof. An ancestry floor prevents
pre-floor deployment but does not prove that a descendant retained a control;
required CI and independent verification must inspect the exact tree and
artifact.

Registry approval requires:

- protected-branch review and required checks for source and contract changes;
- a credentialed, audited release action distinct from client self-report;
- exact full commit, artifact digest, workflow run/attempt, and provider release
  mapping;
- protected production-environment credentials; and
- an append-only disable/revoke path.

Client metadata remains outside the credential plane. It must never:

- create or recover a session;
- choose an account or bypass row ownership;
- unlock, select, or decrypt provider credentials;
- weaken generation fencing or token revocation;
- authorize an OAuth callback or provider write; or
- substitute for CORS, authentication, authorization, or platform release
  review.

Static `.cn` delivery receives no API, database, provider, deployment, or
registry-write credential. The API validates account and credential authority
after the channel compatibility boundary and again at every sensitive
operation.

## Staged migration

No stage is authorized by this proposed record.

1. **Freeze the contract.** Obtain independent and human acceptance; complete
   Trust, Operations, and Quality handoffs; inventory every API and background
   entry point; freeze canonical manifests; independently compute content
   digests; and define the permanent release-evidence location.
2. **Add storage and observe.** Add append-only receipt and approved-release
   entities to the existing PostgreSQL boundary, plus read projections and
   audit events. Dual-write new account receipts and evaluate tuples in shadow
   mode. Existing version-only rows are marked `legacy-version-only`; no digest
   is invented and no production request is newly rejected.
3. **Release capable clients.** Build from protected `main`, verify exact
   artifacts, publish clients that send the complete tuple and store
   digest-bound local acknowledgements, then create approved registry events
   only for the exact publicly available releases.
4. **Enforce client compatibility.** After current-client positive tests and
   stale, missing, syntactically valid-but-unlisted, ambiguous-prefix, and
   cross-channel negative tests pass, enforce exact registry lookup for known
   China channels. Keep account-policy reads in dual mode.
5. **Make the receipt ledger authoritative.** Reconcile independently verified
   legacy receipts where possible; require a fresh action where a version
   cannot be bound to exact content; then switch account and channel receipt
   reads to the append-only ledger/projection.
6. **Retire compatibility fallback.** Remove version-only acceptance only after
   the rollback window, rights-path validation, retained migration evidence,
   and a separately reviewed production hold point.

Deploying rejecting backend behavior before a compatible public client and its
approved registry record is available is prohibited. An observe-only backend
can precede the clients; backend-first enforcement cannot.

## Rollback

- Before enforcement, disable shadow reads or dual writes while preserving
  recorded events for diagnosis.
- Never down-migrate by deleting receipt or release history. A prior compatible
  application version may read an established projection while a forward fix
  is prepared.
- Revoke or disable a bad release with a new registry event. Do not edit or
  delete its approval record.
- After public activation, deploy only a verified, approved release that
  preserves the notice/content contract and privacy floor. A pre-capability
  client is not an emergency rollback.
- If no compatible client or backend is healthy, disable the affected China
  entry point and preserve export/deletion through the approved rights path.
- Rollback cannot enable optional/background processing, lower the protected
  source floor, accept an unregistered tuple, or grant credential-plane
  authority to client metadata.

## Alternatives considered

### Format-only headers, minimum versions, and local storage

Rejected. Format-only matching would allow an arbitrary well-formed source
identifier or unreviewed descendant and a version-only local value could not
prove which content was shown. The frozen implementation has moved beyond this
alternative by requiring an exact registry match and digest-bound Terms
receipts, but that draft implementation is neither accepted lifecycle
authority nor live proof.

### Backend-first enforcement

Rejected. Rejecting before compatible clients are publicly available can lock
out authentication, export, and deletion and leaves no valid release to add to
the registry. Additive shadow support may land first, but enforcement follows
verified client publication and registry approval.

### Nationality, IP, residence, locale, or person-location classification

Rejected. These signals are inaccurate, privacy-expanding, and unrelated to
which disclosure-capable artifact initiated the transfer. They would turn a
release contract into person profiling.

### One account-wide receipt for every client and purpose

Rejected. It permits a web action to bypass the Miniapp's pre-transfer notice
and conflates disclosure acknowledgement, contract acceptance, and optional
consent.

### New provenance/receipt service or datastore

Rejected for this horizon. It adds availability, recovery, privacy, migration,
and operating cost without evidence that the existing API and PostgreSQL
boundary is insufficient.

## Consequences

The selected contract provides exact content binding, auditable release
approval, cross-client policy reuse without cross-client notice bypass, and a
staged path from the current version-only controls. It also adds database
migrations, registry operations, release-manifest generation, client payload
fields, route classification, and independent release verification.

It does not provide cryptographic client attestation. A malicious client can
replay an approved tuple. The security boundary therefore remains
authentication, authorization, credential isolation, server-side purpose
checks, and protected release operations. Strong device or binary attestation
would be a separate Architecture and Trust decision.

## Exact implementation prerequisites

Engineering must not claim conformance until all of the following exist:

1. A versioned canonical-manifest specification and independently reproduced
   SHA-256 digests for every presented locale and policy/notice bundle.
2. An append-only approved-release registry with the fields and state events
   defined above, backed by the existing authoritative API/PostgreSQL boundary.
3. Append-only account and client-channel receipt events, insert-only
   application permissions, server timestamps, immutable projections, and a
   migration that labels rather than fabricates legacy digest provenance.
4. A complete, default-deny route and worker inventory classifying public,
   bootstrap, ordinary personal, credential, rights, and background surfaces.
5. Exact tuple production in both web and Miniapp clients and exact registry
   lookup in the API; syntax, CalVer ordering, or commit ancestry alone cannot
   accept a request.
6. A per-client local gate keyed by notice version and content digest, followed
   by authenticated recording of the channel receipt.
7. Account-wide Terms acceptance and Privacy-read actions bound to the exact
   policy-bundle digest, with mutable account columns demoted to projections.
8. Export, disconnect, deletion, sign-out, and an independent fallback rights
   path that work without new Terms acceptance and cannot expose another
   account.
9. Background-job enqueue provenance, execution-time authorization/deletion
   fences, late-write rejection, and fail-closed optional-processing switches.
10. Provider connection notices before credential/OAuth transfer, with all
    credential operations remaining in the authenticated encrypted backend
    plane.
11. Protected-`main`, tag, manual-dispatch, production-environment, full-SHA,
    artifact-digest, and provider-release checks that cannot be satisfied by a
    client header or ancestry floor alone.
12. Accepted retention and erasure rules for policy receipts, channel
    receipts, release records, and minimal deletion evidence.
13. A permanent approved Release Evidence store; short-lived workflow
    artifacts and logs are supporting inputs only.
14. Independent Architecture/Trust review, bounded human review and acceptance,
    Operations rollout authority, and independent Quality evidence for the
    exact merged tree. None is supplied by this proposal.

## Verification prerequisites

Quality must independently verify the exact merged commit and artifacts:

- **Classification:** `.cn` and Miniapp channel tests across user locations;
  proof that nationality, IP geolocation, locale, timezone, GPS, and residence
  do not affect classification; fail-closed conflict and missing-signal cases.
- **Registry:** reject arbitrary well-formed SHAs, unlisted descendants,
  ambiguous prefixes, disabled releases, version ranges, copied cross-channel
  tuples, and a mismatch in each tuple field; accept only the exact active
  record.
- **Non-attestation:** replaying a valid tuple without valid authentication
  cannot read data, select an account, access credentials, or perform a write.
- **Content:** independently reproduce every digest; mutate each document and
  action label to prove the build/lookup fails; reject same-version,
  different-digest content.
- **Receipts:** prove insert-only behavior, server time and subject authority,
  account-wide policy reuse, channel isolation, fresh-install local gating,
  correction/supersession events, concurrency/idempotency, and no fabricated
  legacy digest.
- **Routes:** prove public and wholly synthetic demo surfaces create no
  personal traffic; authenticated demos are gated; ordinary personal routes
  default deny; stale-policy accounts can still export, disconnect, delete,
  and sign out without cross-account access.
- **Background work:** prove optional work cannot be authorized by notice or
  Terms receipts; deletion/cancellation and changed authorization fence queued
  jobs and discard late writes; production negative switches fail closed.
- **Credential plane:** verify no secret enters static artifacts, headers,
  receipts, registry payloads, or logs; provider transfer begins only after the
  just-in-time notice and server authorization.
- **Migration:** exercise empty, legacy-only, mixed, and fully migrated
  accounts; interrupted dual writes; projection rebuild; rollback without
  history loss; and forced fresh acknowledgement when content cannot be
  independently mapped.
- **Release path:** verify protected-main reachability, exact full source SHA,
  artifact digest, workflow run/attempt, provider locator/ID plus separate
  provider-success evidence, registry approval, source-floor retention, and permanent evidence
  aggregation.
- **Outside-in journey:** verify current and stale `.cn` web artifacts and
  Miniapp releases, first-request ordering, policy update, export, disconnect,
  deletion, CORS, channel disablement, and recovery from outside the providers.

Passing current repository tests would not establish live or independent
verification. No build, test, deployment check, provider query, runtime query,
or outside-in verification was run for this documentation reconciliation.

## Handoffs

- **Engineering:** produce the implementation impact map, schema and API
  changes, migration tooling, clients, route inventory, and tests without
  broadening this proposed contract.
- **Operations:** own registry promotion credentials, protected-environment
  controls, staged rollout, permanent Release Evidence, monitoring, disablement,
  and rollback.
- **Trust:** decide receipt retention/erasure, review cross-border and
  credential boundaries, optional-purpose authorization, threat model, and the
  explicit non-attestation limit.
- **Quality:** independently verify every prerequisite above and issue release
  confidence for the exact merged tree and released artifacts.

## Review triggers

Return to Architecture and independent review before:

- adding a release channel, service, datastore, regional API, or identity
  plane;
- changing tuple or receipt field meanings or digest canonicalization;
- accepting ranges, wildcard releases, mutable approvals, or client-generated
  authority;
- using nationality, IP, residence, or person location;
- making a client receipt account-global or using it for optional consent;
- requiring updated Terms acceptance for export or deletion;
- enabling automatic optional AI or external feedback publication;
- adding cryptographic device/binary attestation; or
- performing an incompatible or destructive receipt/registry migration.

---
_Proposed: 2026-08-26 · Owner: Architecture · Independent review: PENDING ·
Human acceptance: PENDING_
