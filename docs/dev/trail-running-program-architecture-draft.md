# Trail program — Architecture Decision Record draft

2026-09-14 · **draft / inactive**. Architecture's proposal is persisted by
Engineering. These are operational bounds, not scientific dose thresholds.

| Shared field | Value |
| --- | --- |
| id | `docs/dev/trail-running-program-architecture-draft.md` — Trail program aggregate and revision contract |
| schema_version | Existing `logical-contract` shared fields; no production schema, migration or approval format allocated |
| decision_type | `architecture-decision-record` |
| owner_role | Architecture |
| question | How can resources, rolling proposals and independent daily sessions extend the existing owner-scoped plan lifecycle without stale adoption or unbounded retained data? |
| options | Extend the existing aggregate (recommended); separate service / lifecycle; date-based identity and annual executable plans |
| recommendation | Use the existing monolith, immutable proposals, stable session identities, explicit revision fences and bounded retention |
| rationale | Reuses lifecycle and rights; prevents date collisions, stale annual prescriptions, completed-session loss and duplicate stores |
| dependencies | [Work Contract](trail-running-program-work-contract.json), [Science and exact bindings](trail-running-program-review-bindings.md), [Product](trail-running-program-product-draft.md), [Trust](trail-running-program-trust-draft.md), [Experience](trail-running-program-experience-draft.md) |
| review_route | Independent Router allocation in [Decision Review](trail-running-program-decision-review.md); no acceptance claimed |
| outcome_plan | Future independent Quality checks below; observe stale-adoption, completion-loss and retention failures without private value telemetry |
| digest | SHA-256 of this complete UTF-8 / LF file, recorded by path in [bindings](trail-running-program-review-bindings.md); changes require rebinding |

## Context and proposal bounds

Daily resources default to 28 inclusive athlete-local dates from trusted today,
with explicit validity capped at today + 89 days. Event-bound rules end by the
event, at most today + 365 days. There is no automatic extension. Allow at most
8 unique resources, complete ISO weekday patterns and 14 sorted unique date
overrides per rule. Expired raw records retain owner rights until their purge.

Keep `context_revision`, `confirmed_revision`, server `confirmed_at` and
`confirmation_expires_at` distinct. Each new 14-day proposal needs explicit
confirmation, expiring after 14 elapsed days or the earliest dependent rule's
local validity end. Edits, cancellation and source changes invalidate it;
day-seven review extends neither validity nor confirmation. Resolve each
workout's resource and date against confirmed rules. Expired, unavailable and
unknown are different states.

A race roadmap may describe at most 365 days of stages, gaps and review
obligations; it is not an executable annual plan. Daily training has no invented
event date. Generate one proposal with at most 14 consecutive local dates and
28 sessions; read-only expansion is at most 56 dates. Reject oversized requests
atomically without truncation or chained generation. A later block needs fresh
history, resources, policy and review. This does not resolve incomplete Science.

## Identity, compatibility and transactions

Server-issued owner-scoped `workout_id` survives rescheduling and content
revision. New sessions receive new IDs. `workout_revision` binds content;
`completion_revision` separately fences completion. Keep activity type, purpose
tags, local date, IANA timezone, order and optional scheduled instants separate.
Dual sessions require unambiguous start and end instants, including DST handling,
to check Science's actual elapsed interval. IDs govern independent feedback,
completion, activity links and deletion; dates and tags never merge sessions or
duplicate load.

Bind each proposal to its ID / version, base plan version, purpose provenance,
goal snapshot / revision, context and confirmation, history snapshot / revision,
Science decision and contract digests, generator version, workout schema, and
each replaced session's content and completion revisions. Science progression
also retains original admission lineage, immutable references and unique adopted
transitions; proposal, history or goal revisions cannot reset scientific budgets
or reselect the familiar template. Bind the corrected fields named in the
[independent review](trail-running-program-independent-science-review.md).

Preserve known `WorkoutV1` reads. Structured strength and treadmill steps require
reader capability. Group a date as an array; do not flatten dual sessions or
interpret prose as executable instructions. Web and miniapp must both read two
independent sessions before dual writes enable. Unsupported clients receive
explicit update guidance for affected plans. Unknown schemas remain opaque raw
read / export / delete, unavailable for interpretation, edit, completion,
generation or adoption. Gate-off preserves rights. Production schema IDs wait
for acceptance.

Generation atomically creates the snapshot, proposal and audit after locked
revision checks. Adoption is an explicit exact-version action with unexpired
proposal, current policy / confirmation and all revision fences. One transaction
writes the specified future uncompleted replacements, appends the revision and
updates plan / proposal. Concurrent completion or source edit rejects the whole
action. Completed sessions and siblings persist. Idempotency uses exact owner
and fingerprint. Resource edits mark affected adopted work for review; they do
not automatically replace it.

## Retention, rights and recovery

Keep only current context / confirmation before generation, without an edit
stream. A proposal bundle contains goal / context snapshots, minimized history
receipt, audit and all nested revision copies. Retain at most 128 bundles per
owner across states and goals. Unadopted bundles expire 30 elapsed days after
creation; adopted bundles 180 days after creation. Adoption never restarts the
clock. Delete only expired bundles to make room, atomically with all linked
copies; never evict unexpired bundles. At capacity reject
`retention_capacity_reached` and preserve export / delete. Cleanup failure blocks
affected new writes.

The reconciled [Trust proposal](trail-running-program-trust-draft.md) supplies
current-context expiry, earliest-source deadlines, minimized audit TTL and
restore deletion replay. No dangling-reference exception preserves payload
indefinitely. Expired private proposal / context data is removed while
independently owned canonical sessions and completed training remain. Rights
traverse goals, context, sessions, bundles, audits, revisions, caches and opaque
schemas. Reset is not deletion. Provider calls remain zero.

Costs are capability negotiation, complete rights traversal and bounded replay.
Rollback disables new writes while preserving raw rights; it does not
down-convert unknown data. Future Quality must cover DST, independent dual
visibility, deadlines / capacity / cascade failures, adoption races, atomic
rollback, gate-off / unknown rights and zero-provider traps. Operations owns
future cleanup, backup-expiry demonstration and recovery rollout.
