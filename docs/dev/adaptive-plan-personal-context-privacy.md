# Adaptive plan personal-context privacy contract

**Status:** Accepted architecture contract; backend rollout in progress
**Parent:** #582  
**Depends on:** #584, #603, and #607  
**Version:** 1

## Purpose

Adaptive plans need to understand when execution diverges without inventing a
cause. Device data can show that a workout was missed or modified, but it
cannot show that the athlete was caring for a child, travelling, sick, short
on time, or simply chose not to train. Praxys may ask for that context only
when it can materially change a planning decision.

Personal context is optional private input, not a general athlete profile,
journal, medical record, analytics dimension, or source of cross-user
learning. This contract defines how Praxys may collect, use, explain, expire,
export, and delete it across web, miniapp, plugin, MCP, and future
user-delegated agents.

This document remains the production decision gate. Issues #610 through #612
implement the encrypted persistence, authenticated backend contract, and
bounded internal processing boundary, but no first-party capture UI or
production AI processing is enabled yet. The Privacy Policy and bilingual
product disclosure must be updated before either is enabled.

`api/personal_context_processing.py` is the only adaptive-plan path allowed to
prepare personal context for model use. It is intentionally separate from the
broad training-context assembler in `api/ai.py`. The module:

- loads only owner-, purpose-, lifecycle-, latest-version-, and
  purpose-confirmation-matched context;
- projects the structured allowlist `affected_dates`, `affected_days`,
  `available_equipment`, `available_terrain`,
  `maximum_available_minutes`, and `workout_status`;
- returns stable `clarification`, `no_change`, `insufficient_evidence`,
  `safety`, or `suggestion` codes without model-authored prose;
- bypasses AI for illness, pain/injury, and red-flag categories;
- requires current, exact Azure OpenAI consent before decrypting an
  AI-disclosed narrative or constructing a request;
- sends no owner ID, database context ID, generic training context, tool
  definition, or unconsented field;
- records separate payload-free deterministic and provider-use receipts; and
- logs only stable provider failure codes, never prompts, context values,
  identifiers, or model output.

The optional classifier returns only a strict code tuple and cannot mutate a
plan. It has no route, scheduler, or plan-mutation hook and defaults AI
processing off. Concrete suggestion generation, proposal persistence, and
production wiring remain later work and must pass the policy/provider
disclosure gate below.

A provider-use receipt marks initiation of an attempted disclosure, not a
successful model result. It is committed immediately before the external
request so a timeout or process failure cannot leave a disclosure without a
durable receipt, and the database write lock is not held across network I/O.
The private provider boundary suppresses OpenAI SDK request-body debug logs,
including when SDK debug logging is enabled.

## Decisions

1. Context is owned by one athlete and authorized for one explicit planning
   purpose.
2. Structured, bounded input is the default. Short narrative is optional and
   is retained for less time than structured context.
3. Deterministic processing is the default. AI processing requires separate,
   versioned, purpose-specific consent after naming the provider boundary.
4. Context access is narrower than plan access. Narrative access is narrower
   than structured-context access.
5. Context is never copied into generic agent traces, telemetry, logs, public
   trackers, repository fixtures, or cross-user training/evaluation data.
6. Deleting or excluding context invalidates active proposals that depended
   on it and deletes context-dependent private reasoning. Accepted workout
   changes remain as plan history, but their private rationale is removed.
7. Illness, pain, injury, and red-flag input stops performance optimization
   and enters the safety path; it is not used to diagnose or prescribe.
8. The first pilot is first-party and suggestion-only. It does not create a
   durable life profile or grant delegated agents narrative access.

## Non-goals

- Medical diagnosis, treatment, clearance, rehabilitation, or medical records
- A general diary, chat memory, or unrestricted personal profile
- Inferring family, employment, health, motivation, identity, or other
  sensitive facts from workout behavior
- Advertising, ranking, sale, data brokerage, or eligibility decisions
- Cross-user model training, prompt corpora, product evaluation, or policy
  learning from private context
- Silent collection by plugins, MCP clients, or user-delegated agents
- Accepting the draft science records from #607

## Terms

| Term | Meaning |
| --- | --- |
| Personal context | Athlete-stated information about a preference, temporary circumstance, or execution event that may change planning |
| Structured context | A value selected from an allowlisted category and bounded fields |
| Narrative | Optional athlete-authored free text attached to one context item |
| Purpose | The single planning operation allowed to use the item |
| Active use | Whether the item may influence a new assessment or proposal |
| Retention | How long data remains stored after it stops influencing decisions |
| AI processing | Sending a minimized representation to the configured AI provider |
| Derived trace | Private reasoning or proposal metadata that depends on a context item |
| Delegated actor | A plugin, MCP client, or user-authorized agent acting with explicit scopes |

## Privacy invariants

1. **Optional means optional.** Refusing context must produce `unknown`,
   clarification, no-change, or conservative handling, never a penalty.
2. **No guessed cause.** Observed execution and athlete-stated context remain
   separate evidence classes.
3. **One owner.** Every item has an owning-user foreign key with database and
   application-level account-deletion coverage.
4. **One purpose.** A purpose change requires a new consent decision; a prior
   answer is not silently reused.
5. **Minimum necessary.** The policy receives only fields allowlisted for its
   purpose, not the complete context store.
6. **Narrative is untrusted data.** It cannot issue instructions, expand
   permissions, select tools, cause URL retrieval, or override system,
   science, safety, privacy, or approval rules.
7. **No generic copies.** Logs and traces use opaque identifiers and bounded
   states, never payloads or reversible low-entropy hashes of payloads.
8. **Expiry is enforced on read.** Expired or withdrawn context cannot enter a
   new evidence snapshot even if a purge job has not yet removed its row.
9. **Deletion reaches derivatives.** Context withdrawal covers active
   proposals, private decision traces, provider-use receipts, caches, and
   generated explanations that depend on it.
10. **Plan facts survive privacy deletion.** Accepted workout revisions remain
    operational history without the deleted private rationale.
11. **No secondary learning.** Private context is excluded from telemetry,
    analytics, eval corpora, support exports, and cross-user model or policy
    improvement unless a future, separate opt-in contract is approved.
12. **Fail closed.** Authorization, consent, decryption, minimization, provider,
    or deletion failures cannot broaden collection or disclosure.

## Context classes

### Durable preference

A stable planning preference such as available training days, preferred
long-run day, time budget, terrain access, or equipment access.

- Reconfirm when adopting a new plan.
- Store only while useful and while the account exists.
- Do not use a preference to infer why a specific workout was missed.
- This class is outside the first pilot; existing explicit goal/settings
  fields remain the source of truth until a dedicated implementation ships.

### Temporary constraint

A circumstance with a bounded start and end, such as reduced availability,
travel, caregiving demand, schedule disruption, equipment limitation, or
temporary environmental constraint.

- `starts_at` and `expires_at` are required.
- The default active window is 14 days.
- The athlete may choose a shorter period or extend it up to 90 days.
- Continued use after 90 days requires a new confirmation.
- Health or pain categories enter the safety path rather than an ordinary
  performance-adjustment rule.

### Execution explanation

An optional explanation attached to one missed or modified workout.

- It describes the athlete's statement, not an established cause.
- It may inform the next checkpoint and the plan outcome review.
- It cannot by itself justify making up or increasing later training.
- `prefer_not_to_say` is a complete answer and preserves the cause as unknown.

## Purpose registry

Every context use selects exactly one allowlisted purpose.

| Purpose | Allowed input | Allowed output |
| --- | --- | --- |
| `plan_generation` | Confirmed durable preferences and active temporary constraints | Plan assumptions and a suggestion-only preview |
| `execution_interpretation` | One execution explanation and linked observed workout outcome | Clarification, no-change, or bounded interpretation |
| `plan_adjustment` | Active constraints, relevant execution explanations, and plan evidence | Suggestion-only workout/week/block/goal/pause proposal |
| `goal_review` | Active constraints explicitly confirmed for goal review | Qualitative feasibility update |
| `outcome_review` | Context retained through the plan and comparable outcome evidence | Ranked hypotheses with contrary evidence and unknowns |

An item authorized for `execution_interpretation` is not automatically
available to `plan_generation`, `goal_review`, or `outcome_review`.
The athlete may confirm a new purpose through a visible, versioned action.

## Minimum data contract

`PersonalContextItem` is a dedicated athlete-owned aggregate, not a JSON field
on `UserConfig`, `TrainingPlan`, or generic `AgentDecision`.

| Field | Requirement |
| --- | --- |
| `id` | Random opaque identifier |
| `owner_user_id` | Required FK to `users.id` with `ON DELETE CASCADE` |
| `version` | Monotonic item version |
| `kind` | `durable_preference`, `temporary_constraint`, or `execution_explanation` |
| `purpose` | One value from the purpose registry |
| `encrypted_payload` | Category, bounded structured fields, and optional narrative encrypted as one payload |
| `payload_schema_version` | Version used for validation and export |
| `source_actor_type` | First-party UI, plugin/MCP, delegated actor, or migration |
| `source_actor_id` | Opaque authenticated actor reference; never display name or email |
| `linked_subject_type` | Optional plan, workout, goal, or execution-event type |
| `linked_subject_id` | Opaque owner-checked subject reference |
| `processing_mode` | `deterministic_only` or `ai_allowed` |
| `consent_receipt_id` | Required when `processing_mode` is `ai_allowed` |
| `starts_at` | Start of permitted active use |
| `expires_at` | Required for temporary constraints and explanations |
| `narrative_purge_at` | Required when narrative exists |
| `purge_after` | Required for non-durable items |
| `state` | `active`, `expired`, `withdrawn`, or `deleting` |
| `supersedes_id` | Prior version when corrected |
| `created_at`, `updated_at` | Lifecycle timestamps |

The category is kept inside `encrypted_payload`: values such as illness,
caregiving, motivation, and employment schedule are themselves sensitive.
Only ownership, lifecycle, purpose, and opaque linkage metadata remain
queryable without decryption.

No payload hash enters a generic trace. The structured vocabulary has low
entropy and could be recovered through dictionary comparison.

## Allowlisted structured categories

The vocabulary records only what the plan needs to do next.

| Group | Categories | Permitted planning meaning |
| --- | --- | --- |
| Availability | `less_time`, `unavailable_day`, `schedule_conflict` | Reduce or move work within stated availability |
| Life constraint | `caregiving`, `travel` | Respect temporary time/location constraints without retaining details |
| Training state | `fatigue`, `motivation` | Ask or propose conservatively; do not diagnose |
| Safety boundary | `illness`, `pain_or_injury`, `red_flag_symptoms` | Stop ordinary optimization and enter safety handling |
| Environment | `weather`, `equipment_access` | Change location, modality, or timing when supported |
| Disclosure choice | `other`, `prefer_not_to_say` | Keep cause unknown; narrative remains optional |

Structured fields may include dates, affected training days, maximum available
minutes, available equipment/terrain, and whether a specific workout was
missed or modified. They must not ask for:

- a diagnosis, treatment, medication, clinician, or medical-document detail;
- a child's or family member's identity;
- employer, client, school, address, precise location, or travel itinerary;
- protected identity, financial, legal, or relationship details; or
- an explanation for `prefer_not_to_say`.

Narrative is capped at 280 characters in the first pilot. Clients state:
"Share only what changes your plan; avoid names, diagnoses, locations, and
other private details." This guidance reduces collection but does not replace
encryption, authorization, minimization, or deletion.

## Consent and processing modes

### Deterministic processing

`deterministic_only` is the default and needs no AI-provider disclosure.
An allowlisted policy may convert a structured constraint into:

- one clarification question;
- a no-change decision;
- an insufficient-evidence result;
- a conservative suggestion within an approved scope; or
- a safety escalation.

The loader must also verify the exact item version's purpose-confirmation
receipt before decrypting it for deterministic processing.

The optional narrative is not available to deterministic rules unless a
future parser and its purpose are separately reviewed.

### AI processing

AI processing is off for each item until the athlete explicitly enables it.
The consent surface must show:

- the exact purpose;
- that the configured Azure OpenAI service receives a minimized copy;
- which structured fields and whether narrative will be sent;
- that AI output may be wrong and cannot diagnose;
- the retention statement available from the configured provider contract;
- how to withdraw consent and delete the context; and
- the consent text version.

The consent receipt stores owner, item version, purpose, disclosed provider,
disclosed fields, consent-text version, decision, timestamp, and client. It
does not store the context payload.

Consent to general Terms, connecting a fitness provider, using AI insights,
or authorizing a plugin does not imply personal-context AI consent.

Withdrawing AI consent immediately blocks new provider calls. It does not
pretend to recall a request already processed by the provider; the disclosure
must state that limitation. Local provider-use receipts and generated private
reasoning are then deleted according to the withdrawal workflow.

### Provider request minimization

A dedicated context assembler, separate from the broad
`build_training_context()`, must:

1. load only active owner-matched item versions for the requested purpose;
2. verify the current consent receipt;
3. decrypt only those items;
4. project allowlisted fields;
5. exclude narrative unless separately disclosed and allowed;
6. label athlete statements as untrusted quoted data;
7. attach policy, prompt, and consent versions;
8. send the minimized request to the configured provider; and
9. append a private provider-use receipt without the payload.

Raw provider requests and responses must not be logged. A model cannot invoke
tools, retrieve URLs, write plans, or expand its context scope because of text
inside an athlete narrative.

If the provider is unavailable, consent is missing, or minimization fails,
Praxys uses the deterministic structured path when valid. Otherwise it returns
clarification, no-change, or insufficient evidence. It must not silently use a
different provider or send a broader payload.

## Authorization and actor matrix

Proposed scopes refine the architecture contract:

- `plan:context:read` - active structured context for an allowed purpose
- `plan:context:narrative:read` - narrative, separately granted
- `plan:context:write` - create or correct a previewed context item
- `plan:context:delete` - withdraw/delete an owned item
- `plan:context:ai-consent` - athlete-only AI-processing decision

| Actor | Structured read | Narrative read | Create/correct | Delete | AI consent |
| --- | --- | --- | --- | --- | --- |
| Athlete in first-party UI | Own items | Own items | Yes | Yes | Yes |
| First-party deterministic policy | Purpose-projected active fields | No | No | No | No |
| First-party planning AI | Purpose-projected with valid consent | Only if separately disclosed and consented | No | No | No |
| Plugin/MCP client | Token- and purpose-scoped, if granted | No by default | Explicit preview and athlete command only | Explicit athlete command only | No |
| Future user-delegated agent | Short-lived, purpose-scoped, if granted | Separate short-lived grant only | Explicit preview and athlete command only | No by default | No |
| Provider adapter | One minimized request | Only disclosed fields | No | No | No |
| Operator/admin | Lifecycle metadata by default | No | No | Recovery workflow only | No |
| Telemetry/evaluation | No | No | No | No | No |

Authentication or `plan:read` does not grant context access. A token cannot
grant itself a new scope. Delegations include owner, actor, purposes, item
kinds, operations, expiry, and revocation. The server evaluates scopes and
ownership on every request; clients cannot enforce this boundary themselves.

Context created through a delegated actor remains a preview until the athlete
confirms the exact structured fields, narrative, purpose, expiry, and
processing mode in a trusted Praxys surface. Prompt text such as "remember this
forever" has no authorization effect.

## Lifecycle

```text
draft preview -> athlete confirmed -> active -> expired -> purged
                                 \-> corrected -> successor active
                                 \-> withdrawn -> dependency cleanup -> purged
                                 \-> deleting -> dependency cleanup -> purged
```

- Draft previews are request-scoped and are not durable context.
- Confirmation creates version 1 and a purpose receipt.
- Correction creates a successor version; it does not rewrite the prior
  version in place.
- Only the latest active, non-expired version may enter a new evidence
  snapshot.
- Expiry blocks active use synchronously. Purge may occur asynchronously.
- Withdrawal blocks active use and provider calls synchronously, then starts
  dependency cleanup.
- Deletion reports success only after the primary context row and synchronous
  authorization/index references are removed. Asynchronous cleanup is tracked
  and retried visibly.

## Retention and deletion

| Data | Active-use default | Purge rule |
| --- | --- | --- |
| Durable preference | Until changed/deleted; reconfirm at plan adoption | On athlete deletion or account deletion |
| Temporary structured constraint | 14 days; athlete may choose up to 90 days | 30 days after expiry or withdrawal |
| Execution structured explanation | Through the active plan outcome review, at most 180 days | 30 days after plan closure or at 180 days, whichever comes first |
| Optional narrative | Same initial active window as its item | 30 days after capture or earlier withdrawal |
| Draft preview | Current authenticated request | End of request; never persisted |
| Context-dependent active proposal | Until proposal expiry | Immediately invalidate, then delete private rationale on context withdrawal |
| Context-dependent private decision trace | While its source context is retained | Delete with the source context |
| Accepted plan revision | Account lifetime | Keep workout before/after facts; remove deleted context references and rationale |
| Consent/provider-use receipt | While the item is retained | Delete with the item or account |
| Payload-free idempotency tombstone | Account lifetime | Clear item/lineage references with context; delete with account |

The initial pilot does not retain narrative through a long plan merely for a
future outcome review. After narrative purge, only the confirmed structured
category may remain within its own retention window.

### Item withdrawal

Within one serialized workflow:

1. mark the item `deleting` so reads and provider calls fail closed;
2. lock the owning plan/context write lane;
3. invalidate pending proposals whose evidence snapshot used the item;
4. delete generated private rationale, provider-use receipts, context-use
   links, cached prompts, and context-dependent decision/outcome traces;
5. remove context references from accepted revision display metadata while
   preserving the workout mutation;
6. delete every item version and consent receipt; and
7. retire the opaque command keys while clearing their item and lineage
   references, then commit a payload-free deletion result.

If cleanup fails, the item remains unusable in `deleting`, the athlete sees a
concrete failure state, and the operation is retried. The system must not
return a success-shaped response while dependencies remain readable.

### Account deletion

The implementation extends `api/account_deletion.py` so all context items,
consents, delegations, provider-use receipts, proposals, athlete-owned
decisions/outcomes, exports, and cleanup jobs are deleted for the primary and
demo users. The generic `AgentDecision.subject_ref` pattern is insufficient;
athlete planning traces require an explicit owning-user FK with
`ON DELETE CASCADE`.

Backups may age out under the documented operational backup schedule rather
than being rewritten in place. A restore must replay outstanding deletion
manifests before serving traffic. A manifest contains a random deletion job
identifier and completion state, not context payload or athlete narrative,
and is removed after the last affected backup expires.

### Export

The athlete export contains:

- current and retained prior item versions in a documented JSON schema;
- purposes, lifecycle dates, source actor type, and processing mode;
- consent decisions and disclosed provider fields;
- context-use receipts and linked proposal/revision identifiers; and
- deletion/expiry state.

The export does not include internal prompts, hidden chain-of-thought,
credentials, another user's data, or operator-only security metadata.
Payload-free idempotency tombstones are also excluded.

## Decision and provenance traces

An evidence snapshot may record an opaque context item ID and version,
`athlete_stated` evidence class, purpose, and allowed derived action category.
It must not duplicate the encrypted payload, narrative, or a reversible hash.

Every athlete-facing suggestion states:

- the observed execution facts;
- the athlete-stated context that was used, in athlete-controlled wording;
- the policy or AI-processing mode;
- the proposal rationale and uncertainty;
- what remains unknown;
- the no-change alternative; and
- controls to exclude the item, correct it, withdraw AI consent, or delete it.

Accepted plan revisions preserve the operational before/after diff and actor.
Their human-readable rationale references the context only while that context
is retained. After deletion it reads "Personal context removed by athlete";
the system does not keep a shadow summary.

## Telemetry, evaluation, and support

Permitted telemetry is limited to bounded operational states such as:

- context flow opened/completed/cancelled;
- item kind, without category or narrative;
- deterministic or AI processing mode;
- proposal accepted/rejected/deferred;
- deletion completed/failed; and
- coarse duration and failure domain.

Telemetry may use the repository's existing pseudonymous user hash but cannot
include context IDs, subject IDs, category, purpose details that reveal
sensitive content, narrative, prompt, model output, dates, or deletion reason.

Support tooling shows lifecycle metadata and cleanup status by default. An
operator cannot browse payloads. Any future break-glass access requires a
separate audited design with athlete notice and is outside this pilot.

Synthetic fixtures must be authored as synthetic categories, never copied
from production. Product evaluation uses predefined synthetic scenarios and
aggregate operational counts, not private context or model transcripts.

## Safety handling

`illness`, `pain_or_injury`, and `red_flag_symptoms` are routing categories,
not diagnoses. They may produce:

- a pause or reduced-demand suggestion;
- a focused question about whether the athlete wants to pause;
- a statement that Praxys cannot assess medical safety; and
- appropriate general advice to seek qualified care.

They cannot produce medical labels, treatment, clearance, return-to-sport
timelines, or a performance optimization that assumes the symptom is safe.
Narrative is not parsed to infer a diagnosis or severity.

## Threat model

| Threat | Example | Required mitigation |
| --- | --- | --- |
| Prompt injection | Narrative says to ignore rules, call a URL, or approve a plan | Treat narrative as quoted data; no tools; deterministic permissions and validation remain authoritative |
| Confused deputy | Plugin with `plan:read` requests private context | Separate server-enforced context and narrative scopes with owner/purpose checks |
| Silent collection | Agent turns conversation history into a durable profile | Preview plus explicit athlete confirmation; no durable write from prompt text |
| Purpose creep | Missed-workout reason later shapes an unrelated goal | Exact purpose registry; new consent for purpose change |
| Sensitive inference | System labels caregiving, illness, or motivation from behavior | Only athlete-selected categories; preserve unknowns |
| Provider over-disclosure | Broad training context and all notes enter a prompt | Dedicated minimizing assembler and field-level consent receipt |
| Logging leak | Prompt, narrative, or decrypted payload reaches logs/errors | No request/response logging; bounded error codes; automated secret/privacy tests |
| Low-entropy hash leak | Hash of `illness` reveals the category | No payload/category hashes in generic traces |
| Stale context | Expired travel constraint still reduces training | Enforce expiry synchronously on every read; purge is not the access boundary |
| Deletion gap | Context row is gone but proposal rationale remains | Dependency graph, serialized cleanup, visible failure, retry, and deletion tests |
| Immutable-ledger conflict | Private rationale is retained to preserve audit history | Preserve workout diff; delete context rationale and private decision traces |
| Cross-user leakage | Cache or query returns another athlete's context | Required owner FK, owner-filtered loaders, cache partitioning, isolation tests |
| Delegation replay | Revoked agent reuses an old context token | Short expiry, audience/purpose binding, revocation checks, idempotency |
| Concurrent mutation | Proposal is accepted while its context is deleted | Shared plan/context write lane and base-version revalidation |
| Backup resurrection | Deleted context returns after restore | Deletion manifest replay before traffic and documented backup expiry |
| Public disclosure | Context appears in feedback/GitHub issue | Structural exclusion; do not rely only on PII scrubbing |

## Failure semantics

| Failure | Required behavior |
| --- | --- |
| Missing context | Preserve `unknown`; clarify or use conservative no-change |
| Invalid/overlong input | Reject with a field error; do not truncate and store silently |
| Expired context | Exclude from new snapshots and show expired state |
| Decryption failure | Do not use or expose ciphertext; mark unavailable and alert operators without payload |
| Missing AI consent | Use valid deterministic path or return consent-required; never send |
| Provider unavailable | Deterministic path, clarification, no-change, or insufficient evidence |
| Unauthorized actor | Deny without revealing whether the item exists |
| Stale item version | Return conflict and current metadata; never overwrite |
| Deletion cleanup failure | Keep item unusable in `deleting`, show failure, and retry |
| Account deletion | Fail the overall deletion if database-owned context cannot be removed |

## Initial pilot

The first implementation is intentionally smaller than this complete contract.

### Included

- First-party web and miniapp capture
- One execution explanation for a missed or modified workout
- One temporary constraint with start/end dates and affected availability
- The allowlisted categories above
- Optional 280-character narrative
- `deterministic_only` by default
- Separate per-item AI opt-in with provider and field disclosure
- Clarification, no-change, insufficient-evidence, safety, and
  suggestion-only outputs
- Athlete inspect, correct, exclude, expire, withdraw, delete, and export
- Context use shown in the proposal

### Deferred

- Durable personal profiles or general memory
- Autonomous plan mutation
- Delegated-agent narrative access
- Silent context creation from chat
- Cross-plan or cross-user learning
- Location, calendar, email, or contact ingestion
- Medical details or return-to-sport recommendations
- Context-based personal success probabilities
- Reusing context for a new purpose without confirmation

Plugin, MCP, and user-delegated actors can detect that clarification is needed
and deep-link to the trusted confirmation flow. Context read/write scopes ship
only after the first-party lifecycle, isolation, deletion, and consent
controls pass review.

## Validation gates

Before production use:

- model and migration tests prove owner FKs and cascade behavior;
- API tests cover owner isolation, scope combinations, stale versions,
  idempotency, and non-enumerating authorization errors;
- account-deletion tests cover context, consents, proposals, decisions,
  outcomes, caches, exports, demo users, and restored backups;
- prompt snapshot tests prove field minimization and narrative/tool isolation;
- logging and telemetry tests reject payloads, categories, context IDs,
  prompts, and model responses;
- retention tests freeze time across expiry, narrative purge, plan closure,
  withdrawal, and retry;
- concurrency tests cover context deletion versus proposal generation and
  acceptance;
- web and miniapp use the UI quality harness for disclosure, loading, empty,
  error, expired, deleting, consent, and long bilingual states;
- plugin/MCP contract tests prove scope, purpose, expiry, and revocation;
- the Privacy Policy and Terms disclosure are reviewed in English and Chinese;
  and
- the threat model receives security and privacy review before enabling AI.

Pilot evaluation may retain aggregate counts of flow completion, proposal
response, deletion success, and failure domain. It must not retain context,
prompts, responses, or category-level cohorts.

## Implementation sequence

1. Add athlete-owned context, consent, use-receipt, and deletion-job models
   with migrations and account-deletion coverage.
2. Add lifecycle and purpose-projected data-layer functions; do not place
   context loading in `analysis/metrics.py`.
3. Add authenticated context commands, export, consent, and deletion APIs.
4. Add the deterministic policy projection and dedicated AI minimization
   assembler with fail-closed provider handling.
5. Add athlete-owned plan decision/proposal traces rather than reusing the
   unowned generic `AgentDecision` schema.
6. Build matching first-party web and miniapp capture, review, consent, and
   deletion experiences.
7. Run the narrow suggestion-only pilot and evaluate operational safety.
8. Consider plugin/MCP structured scopes only after first-party controls are
   stable; narrative delegation remains a separate review.

Any new encryption key, provider setting, retention job, backup behavior, or
Azure resource must update `docs/ops/` in the same implementation PR.

## Follow-up issue map

- #610 - Persistence, encryption, lifecycle, retention jobs, and account deletion
- #611 - Context API, export, consent receipts, and actor authorization
- #612 - Deterministic context projection and AI prompt minimization
- #613 - First-party web/miniapp capture and context management
- #614 - Suggestion-only adaptive pilot and evaluation
- #615 - Plugin/MCP structured access after pilot review
- Privacy Policy and bilingual provider disclosure before production
