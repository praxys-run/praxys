# Trail-running managed-plan Trust decision v2

- **Artifact type:** Trust Decision Record
- **Owner role:** Trust
- **Status:** proposed; human-review-required; runtime inactive
- **Decision ID:** `tdr-owner-non-ultra-trail-plan-v2`
- **Work Contract classification:**
  `sha256:d0a83117e8cd681435229fb7fb2c8ddddf4ac8ad8acaba24590079ba1e200607`
- **Work Contract route:**
  `sha256:6a022077cd4d910007c63241ee7c4b98773cd587c92450c6acecc778943fe168`

## Decision requested

Approve, revise, or reject the Trust boundary for a future inactive Trail v2
implementation.

The proposed implementation may store one current owner draft, create
immutable proposal snapshots and a minimized proposal audit, evaluate
readiness, and show a pure internal Garmin compatibility summary. It must not
expose Trail data or authority through demo accounts, MCP, administrator
views, URLs, telemetry, logs, provider integrations, or cross-owner
identifiers.

This record depends on the exact accepted Product, Experience, Science, and
Architecture v2 decisions. A material dependency change requires Trust
re-review and digest rebinding.

## Human decision sheet

| # | Trust decision | Recommendation |
| --- | --- | --- |
| 1 | Owner isolation | Require an active, non-demo first-party authenticated owner for every Trail operation; provide no demo, MCP, administrator, or source-account fallback. |
| 2 | Input authority | Separate strict client request DTOs from server-owned provenance, history, revisions, and policy results. |
| 3 | Minimization and abuse bounds | Accept only the closed typed fields and exact structural limits below; collect no route, free text, provider data, or value telemetry. |
| 4 | Retention and data rights | Keep only the current mutable unproposed draft; retain proposal snapshots and audit under existing proposal/account policy; distinguish reset from erasure. |
| 5 | Sensitive context | Keep symptom and gastrointestinal input coarse, bounded, non-diagnostic, and unusable for clinical inference. |
| 6 | Leakage controls | Permit only closed navigation keys and low-cardinality operational logs containing no personal value, revision, identifier, or user hash. |
| 7 | Garmin boundary | Permit only a deterministic internal compatibility projection with zero credential, adapter, provider, consent, or delivery access. |
| 8 | Unknown versions and migration | Preserve unknown schemas for owner read/export but never execute them; require complete export/delete coverage for the additive audit migration. |

## Protected assets, actors, and threats

Protected assets are the current Trail draft, explicit unknown states,
server-owned provenance and revisions, confirmation bindings, minimized
history aggregates, immutable proposal snapshots, audit receipts,
symptom-stop and gastrointestinal context, cross-owner object existence, and
complete export/deletion. Browser history, logs, caches, metrics, Garmin
credentials, tokenstores, sessions, consent, provider identifiers, and
delivery ledgers are also protected boundaries.

The only authorized interactive actor is the active, non-demo owner using a
first-party Praxys viewer session. The API, database, evaluator, internal
compatibility matrix, export service, and deletion service enforce that
authority. Unauthenticated callers, another owner, demo viewers, MCP sessions
or grants, administrators, support users, browser extensions, and modified
clients have no Trail read or write authority. Existing whole-account
lifecycle administration may perform its already-authorized cascade without
exposing Trail content; it is not a Trail administration surface. Garmin and
other providers are not actors in this slice.

Threats include cross-owner reference and existence probing, demo-source
inheritance, an MCP/admin route being treated as consent, client-forged
provenance or revisions, stale-confirmation races, pathological request
payloads, planning values leaking into URLs/logs/caches, unnecessary draft
history, incomplete export or deletion, unknown schemas being partially
interpreted, health answers becoming clinical inference, and a Garmin preview
crossing into credential or provider access.

## Trust decision

### 1. Enforce first-party owner isolation on every operation

Every Trail read, save, reset, confirmation, readiness evaluation, proposal
creation/read, adoption-related read, export, goal deletion, and Garmin-summary
operation derives ownership solely from the active first-party authenticated
viewer.

Trail endpoints reject demo viewers before resolving `demo_of`; they are not
MCP-allowlisted and do not accept an MCP grant, administrator identity, owner
ID, or actor ID as authority. Every object lookup includes the authenticated
owner predicate. A missing or cross-owner object returns the same private
`404`, without disclosing existence or state. Authentication and legal-bundle
failures stay outside Product readiness results. Client hiding is not an
authorization boundary.

### 2. Separate client input from server authority

A request may carry only the exact schema identity, closed typed known/unknown
values, an allowed confirmation action, and an opaque server-issued
concurrency precondition. It cannot author provenance, source timestamp,
model, revision, history aggregate/hash, owner identity, policy result, module
availability, compatibility state, or audit metadata. Extra keys and coercion
fail validation.

The server stamps provenance and revisions only after owner-scoped validation.
Recent history remains server-derived. Each mutation and confirmation uses
owner-scoped locking and the exact revision precondition. Editing a value or
source invalidates its confirmation. Proposal creation locks and re-reads the
draft and plan, recomputes history and the composite revision, and creates
nothing when any binding changed. Confirmation means only “reviewed this
revision”; it is not truth, safety, eligibility, or medical attestation.

### 3. Apply exact structural anti-abuse limits

Before JSON parsing, a Trail v2 body is at most **32 KiB UTF-8**; compressed
bodies and malformed UTF-8 are rejected. After parsing:

- maximum nesting depth is **8**;
- each object has at most **64 members**;
- each array or set has at most **32 entries**;
- each string has at most **128 Unicode scalar values** after NFC
  normalization;
- duplicate object keys and set members are rejected;
- numeric tokens have at most **16 ASCII characters**;
- exponent notation and non-finite values are rejected; and
- before tighter field checks, integers fit signed 32-bit range and decimals
  have absolute value at most `1,000,000` with at most two fractional digits.

Canonicalization never logs rejected values. Product/Science field bounds
remain tighter where specified. These are abuse and operability bounds, not
training, safety, or biological thresholds.

### 4. Minimize collected and derived data

The slice may process or retain only normalized closed values, explicit
unknown states, server provenance, revisions and confirmations, minimized
history aggregates, immutable proposal content, and replay digests accepted by
its dependency decisions.

It does not collect, persist, copy into generic audit, or emit free-text
course/health/fueling narratives; GPS, routes, maps, inferred geometry or
course URLs; scraped content; provider payloads or identifiers; device IDs;
credentials or sessions; request bodies; diagnoses, clearance, injury or
performance probabilities; activity `avg_power`; entered-value analytics; or
a stable, pseudonymous, or hashed user identifier. Normal owner/proposal
foreign keys remain internal authorization and deletion locators, not
telemetry identities.

### 5. Define retention, reset, export, and erasure separately

Before a proposal, the only mutable Trail draft is the current namespace in
`UserConfig.goal`. A successful save atomically overwrites the previous
unproposed value, revision, and invalidated confirmation. It creates no draft
history, confirmation event stream, readiness snapshot, or value telemetry;
superseded values do not remain in application caches or generic audit.

Proposal creation may retain one exact immutable goal snapshot, proposal, and
minimized proposal-linked policy audit under existing proposal/account
retention. They commit or roll back together. The audit contains only closed
identifiers, minimized aggregates/window bounds, revisions, digests, and the
complete readiness receipt—never raw activities, request bodies, entered-value
telemetry, provider data, free text, or routes.

**Reset is not erasure.** Reset replaces current editable values with explicit
unknowns and invalidates confirmation; it does not delete source activities or
retained proposal snapshots/audits. The UI must say so.

Owner export includes the complete current draft/provenance/revisions/
confirmations, every retained immutable goal/proposal snapshot, and every
retained Trail policy audit and receipt. Goal deletion and account deletion
erase the current namespace and cascade through owned snapshots, audits,
indexes, and caches. No deletion reports complete while a known owned row or
cache remains. Failure rolls back or uses the repository’s explicit durable
cleanup-pending behavior without exposing values or internal errors. Unknown
schemas follow the same export and erasure rules.

### 6. Keep sensitive context coarse

The symptom request is a known boolean or explicit unknown stop signal. It asks
for no symptom, diagnosis, duration, severity, treatment, clearance, or free
text. A confirmed stop blocks planning; unknown requires clarification.

Gastrointestinal experience is limited to `no_plan_altering_issue`,
`plan_altering_issue`, or explicit unknown. It is optional module context, not
a diagnosis or causal explanation, and cannot create an intake prescription,
medical advice, risk score, or referral.

### 7. Keep navigation, logs, and telemetry data-free

Paths, query strings, fragments, titles, browser history, return-focus state,
deep links, analytics, and referrers may carry only closed route, section,
field, or reason-target keys. They never carry entered values, dates,
event/goal/proposal or owner IDs, revisions, digests, serialized DTOs,
provider IDs, or tokens. The authenticated route fetches state from the
server.

Trail logs and metrics contain only closed low-cardinality `action`, `status`,
and `reason` keys. They contain no body, value, source metadata, digest, object
identifier, URL, provider data, raw error, owner ID, email, or user hash. No
value telemetry or cross-user Trail aggregation is authorized.

### 8. Constrain Garmin to a pure internal summary

Only after an adopted canonical plan exists may the authenticated owner request
a Garmin compatibility summary. It reads only stored canonical workout
structures and a versioned internal matrix. It is deterministic and no-write,
returns closed `unverified` or `blocked` states and closed per-workout reasons,
and preserves `trail_running`.

The operation performs zero credential/tokenstore loads, connection/region/
device discovery, adapter or network invocation, provider reads or writes,
provider identifier access, consent reads or writes, delivery-ledger access,
compatibility persistence, scheduling, send, retry, replace, reconcile, or
delete. It cannot claim actual account, device, firmware, region, or provider
support. Any live check or delivery requires new Product, Architecture, Trust,
Operations, Quality, and human decisions.

### 9. Preserve unknown schemas without executing them

Authenticated owner read and export preserve an unknown Trail namespace as an
opaque value without normalization, coercion, evaluation, v2 rendering, or
overwrite. Capability evaluation reports unavailable/version mismatch;
readiness, generation, adoption, and Garmin projection are disabled. Normal
v2 writes cannot replace the namespace. Only explicit reset or deletion may
remove it. Logs record only the closed version-mismatch reason.

### 10. Make the audit migration fail closed

The proposal-linked audit table is additive and enforces owner/proposal
relationships. It performs no v1/future-schema backfill and creates no admin
read surface. The implementation adds it to export, goal deletion, and account
deletion in the same change. Code rollback preserves the table as unavailable
data. Database downgrade drops it only when empty; otherwise it refuses data
loss. Restore, retry, or migration never rebinds owner, provenance, or
revision.

## Required independent verification

Verification must cover every operation as owner, unauthenticated, inactive,
demo, MCP, admin, and second owner; forged provenance and stale races; every
structural limit; absence of forbidden data from persistence/export/logs;
draft overwrite and transactional proposal rollback; reset versus erasure;
complete export/deletion and cleanup failure; sensitive-context enums; URL and
referrer leakage; zero-call traps around every Garmin/provider accessor;
unknown-schema round-trip; SQLite/PostgreSQL migration behavior; and exact-head
Quality plus independent Trust review.

Any owner-isolation, deletion, Garmin-purity, provenance, or forbidden-data
failure is release-blocking. Owner-only status does not waive these checks.

## Rejected alternatives

Rejected alternatives are demo-source reads; MCP/admin Trail surfaces;
client-stamped provenance; append-only draft/readiness history; free text,
route or URL ingestion; values or identifiers in URLs; reset presented as
erasure; partial export/best-effort deletion; live Garmin preview; unknown
schema coercion; and value logging under hashed user identifiers.

## Consequences and handoff

The boundary intentionally permits fewer actors, less draft history, and no
live provider confirmation. Engineering owns implementation; Operations owns
later configuration, migration, deployment, and recovery; Quality verifies;
Trust independently reviews the exact implementation and does not approve its
own security-sensitive changes.

## Exact no-authority boundary

Approval authorizes only preparation and independent review of an **inactive,
undiscoverable, synthetic-data-verifiable implementation** conforming to all
accepted dependencies. It does not authorize implementation approval, merge,
deployment, production migration or data, dogfood, catalog visibility,
activation, adoption, MCP/admin/miniapp exposure, Garmin credential or
provider access, consent, delivery, or efficacy/safety/medical claims.

Later activation or provider work requires a new digest-bound Work Contract,
specialist review, independent verification, Decision Review, and explicit
human authority.

## Human Trust decision requested

Approve, revise, or reject the eight rows in the decision sheet and this exact
boundary. Trust proposes the record but does not approve it.
