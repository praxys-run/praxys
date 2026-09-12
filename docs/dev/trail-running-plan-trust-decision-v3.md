# Trail v3 Trust decision

**Status: draft Trust Decision Record; owner: Trust.**
ID: `tdr-trail-review-context-candidate-v3`.
This records the proposed boundary for the authorized review-only slice under
the [exact Work Contract](trail-running-plan-v3-exact-work-contract.json).
It grants no production, pilot, approval or provider authority and does not
change v2 authentication or rights behavior.

## Input and provenance

The offline parser accepts only bounded UTF-8 JSON with exact closed schema
keys. Before interpretation: at most 32 KiB, depth eight (root is depth one),
64 fields/object, 32 entries/array, and 128 Unicode codepoints/string after NFC.
Reject invalid UTF-8, Unicode surrogates, duplicate keys including NFC collisions,
extra fields, nonfinite numbers, exponent notation and boolean numeric values.
Numeric tokens have at most 16 ASCII characters; integers fit signed int32,
decimals have absolute value at most 1,000,000 and at most two fractional digits.
Tighter field limits apply afterward. Errors contain only closed first-party
reasons and keys, never the rejected values, raw exceptions or client paths.

The [Architecture structure](trail-running-plan-architecture-decision-v3.md)
defines ISO weekdays, full known/unknown envelopes and confirmed-only dependency
resolution. Client input may not author owner/provenance/history/revisions,
receipts, policy results, kilograms/1RM, raw activities, GPS/routes, free-text
locations, provider IDs or calendar IDs. Trusted today/event dates are injected
separately. Only a future first-party history service may stamp observed data;
unknown, no recorded exposure, athlete-stated and measured zero remain distinct.
Resources and gym familiarity cannot confer observed exercise dose.

## Future actor and gate boundary

Every future Trail action must derive an active, non-demo first-party owner from
the authenticated session and constrain all object lookups by owner. A demo
source account, MCP grant, client owner ID, admin flag or support role grants no
Trail content access. An administrator using their ordinary first-party account
retains ordinary rights to their **own** data; the flag neither grants access
to another person's Trail data nor removes personal rights. This is an explicit
v3 proposal and does not amend the current v2 implementation in this package.

Future feature exposure reuses the installed Statsig SDK with only its existing
user identity. Do not add Trail attributes, entered values, history, event,
resource or health data to Statsig or telemetry. No actual Statsig configuration
or persistence is created here. Gate-off and unsupported schema states disable
generation/adoption but preserve raw owner read, export and delete.

## Future retention and rights acceptance matrix

| Storage/surface | Required rights behavior before runtime use |
| --- | --- |
| Current Trail namespace | Owner raw read/export/delete; edits replace current draft and invalidate confirmation |
| Immutable goal snapshot | Include in export and goal/account deletion cascade |
| Proposal and proposal snapshot | Preserve exact adopted version; export and cascade owned data |
| Proposal-linked audit/receipt | Minimized first-party fields; atomic creation; complete export/delete |
| `PlanRevision.proposal_snapshot` | Audit every retained nested Trail copy; export and erase consistently |
| Caches/indexes | Invalidate replaced values and erase owned retained copies; no stale exposed data |
| Expired or unknown schema | Opaque raw read/export/delete, no forced normalization or execution |

Reset replaces current editable context and invalidates its confirmation; it is
not deletion of retained proposals, audits, revision snapshots or activities.
Deletion must not report completion while a known retained Trail copy remains;
use atomic rollback or the repository's explicit cleanup-pending behavior.
Resource cancellation marks affected adopted future work; it does not silently
rewrite completed training or adopt a replacement. Every future mutation and
adoption requires owner-scoped version and revision checks.

Garmin and every provider remain outside this slice: zero credential/tokenstore,
connection, adapter, network, provider identifier, consent, delivery ledger,
scheduling, send, replacement, retry or reconciliation access. No provider
compatibility projection or export implementation is added by the v3 validator.

## Required independent future verification

Quality and independent Trust must test owner/second-owner/unauthenticated/
inactive/demo/MCP/admin scenarios; own-admin ordinary rights; hidden versus
cross-owner object responses; gate-off and unknown-schema raw rights; complete
snapshot/audit/PlanRevision/cache cascades; reset distinction; stale revision
and adoption races; atomic generation; absence of value logging or Statsig
attributes; and zero-call provider traps. These actor/privacy integration checks
are future acceptance obligations, not claims of tests run in this package.

The current executable checks are only the pure untrusted-input and candidate
boundaries. Human review of these drafts cannot replace independent verification,
complete implementation, later activation attestation or release authority.
