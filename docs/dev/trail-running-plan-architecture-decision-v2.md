# Trail-running managed-plan Architecture decision v2

- **Artifact type:** Architecture Decision Record
- **Owner role:** Architecture
- **Status:** proposed; human-review-required; runtime inactive
- **Work Contract classification:**
  `sha256:d0a83117e8cd681435229fb7fb2c8ddddf4ac8ad8acaba24590079ba1e200607`
- **Work Contract route:**
  `sha256:6a022077cd4d910007c63241ee7c4b98773cd587c92450c6acecc778943fe168`
- **Decision ID:** `adr-owner-non-ultra-trail-plan-v2`
- **Decision horizon:** through the first reviewed inactive v2 implementation,
  or until a successor changes its storage, provider, or revision boundary
- **Authority boundary:** this record proposes architecture only. It does not
  approve implementation, merge, deployment, production data, owner dogfood,
  capability visibility, activation, adoption, or Garmin delivery.

## Decision requested

Keep Trail v2 inside the existing Praxys application, database, adaptive-plan
proposal lifecycle, and authenticated UI. Add strict versioned DTOs, a
server-owned revision fence, one proposal-linked policy audit row, and a pure
internal Garmin compatibility projection. Do not add a service, datastore,
route ingestion path, provider session, or second plan lifecycle.

This decision depends on human acceptance of the exact Product and Experience
v2 artifacts. If either changes materially, this record must be reviewed and
rebound before Engineering starts.

## Context and constraints

The current pure Trail core is unreachable and has no Trail API or editor. The
existing architecture already provides `UserConfig.goal`, immutable
`AdaptivePlanGoalSnapshot` and `PlanProposal` records, owner-scoped
authentication, capability discovery, data export, and account deletion.
Reusing these boundaries is cheaper to operate and safer to roll back than a
new service or parallel plan store.

Reviewer findings require the architecture to resolve these ambiguities before
implementation:

- requests must not let clients claim server provenance or observed history;
- hazards must use the same known/unknown envelope as other reviewable facts;
- schedule capacity needs explicit time and exception fields, not weekdays
  alone;
- course, planning context, and observed history must not share one mutable
  revision;
- an empty `limited_modules` list must not be rendered as “Included”;
- navigation state must not copy personal values or concurrency tokens into a
  URL or browser history; and
- a Garmin preview must not become an accidental credential or provider-I/O
  path.

## Decision

### 1. Preserve the current application boundary

Implement v2 as modules in the existing analysis, API, database, Web, and
managed-plan layers. The pure evaluator remains free of database, HTTP,
provider, clock, locale, and UI dependencies. API orchestration loads and
validates owner-scoped state, calls the pure evaluator, and persists only at
the proposal boundary.

No new process, queue, cache, database, blob store, or provider integration is
authorized. The capability registry stays inactive and undiscoverable unless
a later, separately reviewed activation changes that state.

### 2. Separate request DTOs from server response DTOs

Define strict request DTOs for `trail_course_demand_v2` and
`non_ultra_trail_constraints_v2`. Every DTO forbids unknown keys and coercion.
Reviewable factual values have exactly one request shape:

```json
{"state":"known","value":"<strict typed value>"}
```

or:

```json
{"state":"unknown"}
```

`known` must contain `value`; `unknown` must not. Missing states, `null`, empty
sentinels, strings for numbers or booleans, and extra metadata fail validation.
The one Product-approved nullable aid-gap meaning remains a typed known value,
not a third envelope state.

`hands_assist` and `fixed_rope` use this same envelope with a strict boolean
value. The UI maps Yes/No/Not sure to known `true`, known `false`, or unknown;
the API does not accept a separate `yes|no|unknown` wire type.

Request DTOs have no provenance, field revision, source timestamp, source
model, history hash, provider identifier, or actor field. The server response
uses a different type that adds server-stamped provenance and opaque revision
metadata. A client may echo a server-issued revision only as a concurrency
precondition; it cannot create or modify that revision or provenance.

### 3. Use one canonical representation

The wire and persisted contract accepts one unit per value: meters for
distance/elevation, minutes for duration, Celsius for temperature, percentage
points for humidity, ISO dates, and ISO weekday integers `1..7`. UI hours,
kilometres, and percentages are presentation conversions only.

Grade shares are five integer basis-point values, each `0..10000`, whose sum is
exactly `10000`. Sets must already be unique and serialize in canonical enum or
numeric order. Objects are serialized with sorted keys. Decimal inputs are
parsed losslessly, allow at most two fractional digits, and serialize as
normalized base-10 numbers without exponent notation or insignificant zeros.
Non-finite values are invalid. Digests use UTF-8 canonical JSON and SHA-256;
locale labels and display formatting never enter a digest.

### 4. Impose structural anti-abuse limits

Before JSON parsing, each Trail v2 request is limited to **32 KiB UTF-8** and
compressed request bodies are rejected. From the root object, maximum nesting
depth is **8**. An object has at most **64 members**, an array or set at most
**32 entries**, and a string at most **128 Unicode scalar values** after NFC
normalization. Enum and schema identifiers retain their tighter DTO limits.

Numeric tokens are at most **16 ASCII characters**, cannot use exponent
notation, and must fit signed 32-bit integer range or absolute decimal value
`<= 1,000,000` before the tighter field-domain checks run. Duplicate JSON keys
are rejected. Duplicate set members are rejected rather than silently removed.

These limits are reversible Product/Engineering abuse and operability
guardrails. They are not biological, medical, course-difficulty, eligibility,
or training-science thresholds. The chosen values are well above the closed
v2 payload's legitimate maximum while bounding parser, validation, logging,
and canonicalization work.

### 5. Complete the planning-context DTO

The schedule portion of `non_ultra_trail_constraints_v2` contains:

- a non-empty unique set of available ISO weekdays `1..7`, or explicit
  unknown;
- `weekly_time_limit_min`, a strict positive integer or explicit unknown;
- `maximum_session_duration_min`, a strict positive integer or explicit
  unknown, not greater than the weekly limit;
- `unavailable_dates`, a known, possibly empty, sorted set of at most **14**
  unique ISO dates, all inside the requested 14-day horizon; and
- optional `preferred_longest_weekday`; omission means no preference, while a
  supplied value must be an available ISO weekday. `null` is invalid.

No time value or unavailable date is inferred from a calendar provider. A
schedule that is complete but cannot fit policy constraints is a readiness
block; it is not rewritten into a smaller or road plan.

### 6. Split revision ownership

The server issues four opaque `sha256:` revisions:

- `course_revision` covers canonical current course values plus server-stamped
  field provenance and source metadata, but not confirmation state;
- `planning_context_revision` covers schedule, access, scope, intent,
  symptom-stop, and optional-context values plus their server metadata, but not
  confirmation state;
- `history_revision` covers only the owner-scoped, policy-minimized aggregates,
  observation windows, accepted activity source revisions, and evaluator
  schema; and
- `composite_revision` hashes the three revisions, the canonical map of current
  section-confirmation bindings, exact course/constraint schema IDs,
  policy/Science contract digests, and generator version.

Each editable section has a value-and-source server revision included in its
parent aggregate. Confirmation stores a fixed section key and that exact
revision; it does not change the revision it confirms. An edit or server-source
change makes the prior binding stale, so the composite changes without a
self-referential confirmation hash.

Mutation and confirmation endpoints use authenticated row locking plus an
`If-Match` precondition. Readiness is no-write. Proposal creation locks and
re-reads the current draft and plan, recomputes history and the composite
revision, and refuses any mismatch before it creates immutable records. An
idempotent replay may return the existing proposal only when its complete
fingerprint matches.

### 7. Store only current drafts until a proposal exists

The only mutable Trail course and planning draft lives in a versioned namespace
inside `UserConfig.goal`. Saving a new value overwrites the old draft value,
revision, and confirmation state atomically. Praxys does not retain prior draft
values, a confirmation event stream, or standalone readiness snapshots.

An immutable `AdaptivePlanGoalSnapshot` is created only in the same transaction
as a `PlanProposal`. It contains the exact canonical course and planning values
used for that proposal. The proposal remains non-canonical until adoption under
the existing adaptive-plan lifecycle.

A proposal-linked Trail policy audit row stores only:

- owner and proposal foreign keys;
- schema, policy, generator, Science decision, and contract identifiers;
- course, planning-context, history, and composite revisions;
- privacy-minimized history aggregates and observation-window bounds;
- canonical input, output, and receipt digests;
- the complete readiness receipt, including all matching reasons and module
  availability; and
- idempotency/request fingerprint and creation time.

It stores no raw activities, GPS, route, free text, provider payload, provider
ID, credential, or device state. The audit row and immutable snapshot are part
of owner data export and goal/account deletion. Standalone readiness calls do
not write an audit row.

### 8. Make module availability explicit

Readiness returns every one of the four closed module keys in an authoritative
`module_availability` object. Each value is exactly:

- `not_evaluated`: a core, validation, or policy condition prevented a safe
  module decision;
- `available`: the module may be considered by generation, but is not yet
  included; or
- `limited`: the accepted input requires that module to be omitted or remain
  descriptive, with the matching reason reference.

`limited_modules` may remain only as a sorted redundant projection of keys
whose status is `limited`. Clients must not infer “Included” from its absence.
Actual inclusion exists only in an immutable proposal, where each module is
explicitly `included` or `omitted` and references the readiness receipt.
`limited` cannot become `included`; `available` need not become `included`.

This corrects a semantic conflict in the proposed Experience v2 receipt.
Design must rebind its readiness labels before implementation; Architecture
does not choose the replacement copy or layout.

### 9. Keep navigation data-free

The application route is fixed. URL paths, query strings, fragments, browser
history, return-focus state, and deep links may carry only closed route,
section, field, or reason-target keys. They never carry entered values,
unknown states, revisions, digests, dates, event IDs, owner IDs, proposal IDs,
tokens, provider IDs, or serialized DTOs. The authenticated page fetches its
current state from the server.

API reason targets are closed keys, not arbitrary URLs. Web maps them to known
focus targets. This preserves refresh/navigation without turning history,
analytics, logs, or referrers into a planning-data channel.

### 10. Require owner authorization everywhere

Every read, save, reset, confirmation, readiness, proposal, proposal read,
adoption-related read, export, deletion, and Garmin-preview operation derives
the owner from the authenticated principal. User identity is not accepted as
request authority. Cross-owner objects return the repository's private
not-found response and do not disclose existence.

### 11. Bound Garmin to a pure internal projection

The post-adoption Garmin preview reads only the authenticated owner's stored
canonical plan/workout structures and a versioned internal compatibility
matrix. It is a deterministic, no-write projection that may report only
internal `unverified` or `blocked` compatibility and per-workout reasons.

The preview loads no Garmin credential or tokenstore, invokes no adapter,
performs no provider or network I/O, reads or emits no provider workout/device
ID, schedules nothing, and writes no consent, delivery, retry, ledger, or
provider state. It cannot prove device support. Connect, send, reconcile,
replace, and delete remain outside this decision.

### 12. Preserve unknown schemas without executing them

An authenticated read or export preserves a stored Trail namespace whose
schema ID is unknown to the running code as an opaque value. The code reports
`policy_unavailable`/version mismatch and offers no readiness, generation,
adoption, or Garmin projection. It must not coerce, partially normalize,
silently drop, or overwrite that namespace.

Reset or deletion may remove it through the owner-scoped data-rights path.
Normal v2 writes never accept an unknown schema. This permits a safe code
rollback or mixed backup restore without treating future data as current.

## Persistence migration and rollback

Use an expand-first migration: add the proposal-linked Trail audit table and
its owner/proposal constraints without rewriting `UserConfig.goal`, existing
goals, plans, or proposals. There is no v1-to-v2 value backfill. Any existing
Trail v1 or unknown namespace remains readable/exportable but unavailable for
generation until the owner explicitly creates a v2 draft.

Before activation, rollback removes the inactive endpoints and registry entry
while preserving v2 goal JSON as unknown data. Retain the new empty or populated
audit table across a code rollback. A database downgrade may drop it only when
it contains zero rows; otherwise export plus separately authorized destructive
data loss is required. No automatic downgrade deletes audit evidence.

If proposal persistence fails, the snapshot, proposal, and audit row roll back
together. If the exact composite revision changes, the client must fetch and
confirm current state; no migration or retry silently rebinds it.

## Consequences and trade-offs

- Reusing the monolith and adaptive-plan lifecycle minimizes operations and
  makes the inactive slice readily removable.
- Separate revisions prevent unrelated history refreshes from masquerading as
  course edits, at the cost of more explicit concurrency handling.
- Overwriting unproposed drafts minimizes sensitive retention, but removes
  draft history and undo across saves.
- A proposal-linked audit row makes replay and review inspectable without raw
  activity duplication, at the cost of one table and export/delete work.
- Strict bounds and closed DTOs reject some forward-compatible client input;
  explicit schema negotiation is preferred to ambiguous coercion.
- A pure Garmin projection is safe to implement inactive, but cannot claim
  real account, device, region, or provider compatibility.

## Rejected alternatives

- **New Trail service or datastore:** rejected; it duplicates owner auth,
  proposal lifecycle, deletion, export, and recovery without current scale or
  isolation evidence.
- **Append every edit/readiness result:** rejected; it retains unnecessary
  personal planning history before the owner creates a proposal.
- **One source revision:** rejected; course, schedule, and activity history
  have different writers and invalidation cadence.
- **Client-stamped provenance or athlete-entered history:** rejected; it makes
  server evidence spoofable and breaks replay authority.
- **Infer inclusion from `limited_modules`:** rejected; absence of a limitation
  does not prove a generator selected a module.
- **Put state in URLs or browser history:** rejected; it leaks values and makes
  stale concurrency tokens replayable outside the authenticated fetch path.
- **Live Garmin check for preview:** rejected; it crosses credential, consent,
  availability, and provider-state boundaries not authorized here.
- **Coerce v1/unknown schemas into v2:** rejected; defaults would manufacture
  confirmation, provenance, or meaning.

## Implementation impact map and handoff

- **Engineering:** versioned DTOs and orchestration in `api/`; pure canonical
  evaluation in `analysis/`; current draft namespace and transactional
  proposal/audit persistence in `db/`; inactive capability registration only.
- **Database:** additive audit-table migration, owner/proposal constraints, and
  atomic snapshot/proposal/audit creation; no draft-history table.
- **Web:** authenticated course ledger, closed navigation keys, explicit
  concurrency handling, and module availability semantics after Design rebind.
- **Miniapp:** honest unavailable/Web handoff only; no partial editor.
- **Garmin:** internal compatibility-matrix projection only; no change to the
  provider adapter or credentials.
- **Trust:** independently review minimization, owner authorization, opaque
  unknown-schema retention, URL leakage, export, reset, and deletion.
- **Operations:** review migration, rollback, readiness, and inactive feature
  configuration; no deployment or activation follows from this ADR.
- **Quality:** independently verify canonical replay, payload limits, duplicate
  rejection, revision races, transaction rollback, owner isolation, data
  rights, unknown-schema behavior, navigation leakage, and zero Garmin I/O.

## Review and verification triggers

A successor Architecture review is required for a new service/datastore,
route/provider ingestion, draft-history retention, a different payload bound,
schema coercion, client-authored evidence, cross-user data, background jobs,
provider I/O, a second proposal lifecycle, material scale pressure, or an
irreversible migration. Product, Science, Trust, Design, Operations, and
Quality retain their own authority; this ADR cannot approve their decisions or
its implementation.

## Human Architecture decision requested

Approve, revise, or reject this exact proposed boundary. Approval would permit
Engineering to prepare only an inactive implementation after every prerequisite
decision is accepted and rebound. It would not authorize merge, deployment,
production data, owner exposure, catalog visibility, capability activation,
plan adoption, Garmin access, or delivery.
