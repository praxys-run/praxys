# Trail program — Trust Decision Record draft

2026-09-14 · **draft / inactive**. Trust proposal persisted by Engineering;
no collection, retention, authorization or runtime change is activated.

| Shared field | Value |
| --- | --- |
| id | `docs/dev/trail-running-program-trust-draft.md` — Trail context, identity and derivative-data rights |
| schema_version | Existing `logical-contract` shared fields; no new persistence or approval schema |
| decision_type | `trust-decision-record` |
| owner_role | Trust |
| question | Can bounded first-party planning context support proposals while preserving isolation, explicit adoption and complete derivative deletion? |
| options | Bounded context with complete derivative rights (recommended); indefinite snapshots / audit payloads; expanded administrator or MCP access |
| recommendation | Owner-filtered first-party access, closed inputs, server provenance, revision-fenced adoption and lifecycle-bound deletion of every copy |
| rationale | Limits cross-owner access, forged history, stale adoption, retention / restore resurrection and silent completed-training edits |
| dependencies | [Work Contract](trail-running-program-work-contract.json), [Science bindings](trail-running-program-review-bindings.md), [Architecture](trail-running-program-architecture-draft.md), [Product](trail-running-program-product-draft.md), [Experience](trail-running-program-experience-draft.md) |
| review_route | Independent allocation in [Decision Review](trail-running-program-decision-review.md); Trust does not accept this proposal |
| outcome_plan | Future independent Quality / Trust test actor isolation, TTL, cascades, races and zero calls; observe synthetic failures without private values |
| digest | Complete UTF-8 / LF file SHA-256 in the same-path row of [bindings](trail-running-program-review-bindings.md); any edit requires rebinding |

## Actors and input authority

| Actor / state | Proposed authority |
| --- | --- |
| Active non-demo first-party owner | Own lifecycle-bound read, edit, confirm, generate, explicit adopt, withdraw, reset, export and delete |
| Personal administrator | Same own rights; administrator flag adds no Trail content authority |
| Other owner, unauthenticated, inactive, demo, source fallback, MCP grant, support / administrator content surface | No Trail authority |
| First-party service | Purpose- and owner-bound work; never autonomous adoption |
| Existing account-deletion administrator | Existing authorized cascade only; no new content disclosure |
| Provider, telemetry or evaluation | No Trail payload |

Every lookup is owner-filtered; missing and cross-owner results use the same
private response. Gate-off or unknown schema disables generation / adoption
while preserving owner raw read / export / delete. Unknown payloads must not be
normalized and overwritten.

Closed input fields cover purpose / goal, resources, equipment, familiarity,
reported history and coarse feedback. Unknown, no connected records,
athlete-stated history and observed zero remain separate. Clients cannot supply
owner, observed history, provenance, policy or revision authority. The server
owns context / confirmation revisions, confirmation timestamps / expiry,
source / purpose bindings and purge deadlines. Proposals bind goal, context,
history, confirmation, Science decision / contract, generator / workout schema
and session content / completion revisions.

Apply Architecture's 8 resources, complete ISO weekdays, 14 overrides per rule,
daily 28-date default / today + 89-day cap, and event today + 365-day cap. Require
explicit confirmation per new 14-day proposal, expiring after 14 elapsed days
or the earliest dependent rule end. Edits, cancellation and source changes
invalidate it. These operational limits do not establish scientific safety.

Untrusted JSON is limited to 32 KiB uncompressed UTF-8, depth 8, 64 members per
object, 32 entries per array and 128 NFC Unicode scalars per string. Reject
duplicate or NFC-colliding keys, surrogates, unknown fields, booleans as numbers,
exponents, nonfinite values and coercion. Numeric tokens are at most 16 ASCII
characters; integers fit int32; decimals have absolute value at most 1,000,000
and at most two fractional digits. Closed errors never echo submitted values.

## Retention and deletion

| Data | Proposed deadline / behavior |
| --- | --- |
| Current context | Overwrite unproposed edits without history. Purge each expired rule's values 30 days after expiry; purge remaining context 30 days after the last rule expires, or 30 days after save when no valid rule exists. Reconfirmation extends neither validity nor retention. |
| Proposal bundles | At most 128 per owner across goals / states. Unadopted: 30 elapsed days from creation; adopted: 180 days from creation. Adoption never resets the clock. |
| Snapshots, receipts and payload audits | Inherit the earliest applicable source or bundle deadline, including every `PlanRevision.proposal_snapshot` copy. |
| Standalone minimized audit envelope | Opaque owner / job locator, closed operation / status and timestamps only. Delete 30 days after creation or earlier owner deletion; no payload, source references or reconstructable digest. |
| Restore deletion manifest | Private and payload-free; 14 days matching documented PITR. Replay deletion before serving restored data. Longer archives need a separate reviewed retention change. |
| Independent canonical workout facts | Existing owner / account lifecycle; remove private context and rationale on withdrawal. |

Prune expired bundles only. At 128 unexpired bundles, reject atomically with
`retention_capacity_reached`; never remove unexpired data to fit. Cleanup failure
blocks affected writes. Cleanup-pending cannot extend retention authority or
count as successful deletion. Future deployment must demonstrate backup expiry
and deletion replay.

Withdrawal immediately excludes selected sources / provenance from new
evaluation, invalidates dependent proposals and erases their values, references,
confirmations, private rationale and caches across context, bundles and revisions.
Delete an entire immutable bundle if its dependent content is indivisible.
Preserve independent source activities and canonical workout facts.

Reset replaces editable answers with unknown and invalidates confirmation. The
UI must state that retained proposals and activities remain. Scoped Trail / goal
deletion cascades through all owned Trail copies; account deletion also removes
independent sessions / activities under canonical rights. Never report success
while affected copies remain. Export includes current and retained context,
provenance, confirmation, individual sessions, proposals, receipts, revisions and
unknown schemas; excludes credentials and other owners.

## Adoption and external boundaries

Use stable owner-scoped session IDs, independent content / completion revisions
and actual instants / timezone. Dates do not merge sessions. Adoption rechecks
accepted Science spacing and all source / plan revisions under locks, replaces
only explicitly selected future uncompleted sessions atomically, and preserves
completed siblings. A concurrent completion or source edit rejects stale adoption.

No provider / credential / adapter / delivery extension. Existing Statsig
identity only; no new Trail attributes or training-value telemetry. Deterministic
outputs remain explicitly labelled. Future independent Quality / Trust must test
the actor matrix, cascades, TTL / capacity, opaque rights, concurrent adoption and
zero-call traps. First-50-km and other Science deferrals remain blocked.
