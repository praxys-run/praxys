# DFA automatic-analysis rollout observation — 2026-10-03

**Summary:** Confirmed gate creation returned one exact-account rule; independent Quality review is pending.

**Use when:** Assessing the bounded rollout configuration, its evidence limits or owned-rule recovery.

## Prerequisites

Operations owns live configuration; Engineering records coordinator-supplied
evidence; fresh Quality independently verifies. The Runtime Work Contract includes Delivery:

- Classification: `sha256:729051f51f688519b1e998472ec5322df7e1834d9da459b9f6d23d6462d4d0f1`.
- Route: `sha256:915ed1ec34f9365f1e9a10d56f113baba0ec890399198838f9d78edac35d4eb6`.
- Exact project: `praxys`, ID `4yfDTkiVBIx43WaMmzkykr`.
- Exact gate: `dfa_alpha1_auto_analysis_enabled`.

## Steps

After actual trusted user confirmation of sending the one requesting account email
to Statsig and making the exact live write, Operations rechecked bounded context,
absence and schema. During 05:50:39–05:51:16 UTC on 2026-10-03, one `gate_create`
succeeded, followed by exact named-gate readback. Both returned `isError: false`
and no warnings. The Gate body matched the frozen proposal; the tool rationale
was revised to reflect confirmation, so complete tool arguments are not identical.
Omitted Target Apps were accepted and returned empty. No guessed app, retry,
update, launch or provider review bypass occurred.

The earlier 05:15:12–05:16:06 UTC attempt found ABSENT before and after automatic
approval review rejected the account-email transmission and live change because
it did not accept recovered write-authorization evidence. No mutation resulted
from that attempt. Its immutable evidence remains historical; actual user
confirmation resolved the write blocker. Authorized requests normally persist
across turns. The independent `human-review-required` allocation is a review
boundary, not write authorization or athlete processing consent.

## Verify

Coordinator-supplied exact provider readback records:

| Field | Returned value |
|---|---|
| Gate | `idType: userID`, `isEnabled: true`, status `In Progress`, type `TEMPORARY`, version `3` |
| Targeting | Exactly one rule, `passPercentage: 100`, one `email` / `any_case_sensitive` condition for the sole approved address; `environments: null` |
| Owned rule | ID and base ID `3hQJrq1ucskuwuLvnyWEdu` |
| Empty collections | `targetApps`, `holdoutIDs`, `tags`, `monitoringMetrics` |
| Provider defaults | `measureMetricLifts: true`, `store0100Exposures: false` |
| Review fields | Project production `reviewRequired: true`; gate `reviewSettings.requiredReview: false`; no review request returned |

Default OFF relies on reviewed provider new-gate and sole-allow-rule semantics.
Explicit `defaultValue` and override fields were omitted; no broader rule was
returned, but hidden-override absence was not separately proven. Distinct project
and gate review fields establish no provider approval. Target Apps omission was
accepted; no actual app name was guessed. Provider defaults above do not establish
SDK telemetry changes; this task enabled no SDK logging or telemetry.

Console creation/readback does not prove SDK delivery/evaluation or computation.
Coordinator-supplied boundaries remain: code undeployed, automatic v2 science
draft/inactive, no science signatures/activation, and processing consent unchanged.
Fresh Quality must independently assess this evidence and the documentation delta.
The raw email, credentials and provider snapshots are omitted from this document.

## Rollback / Recovery

No rollback was performed. After separate rollback authorization, Operations
freshly reads the full resource and removes or sets zero pass percentage only
on owned rule `3hQJrq1ucskuwuLvnyWEdu`, preserving unrelated fields/rules and
default OFF, retaining provider review, then reading back. Never delete the
referenced gate or restore a stale whole-gate snapshot. No visible CAS guarantee
exists for full-resource update; stop when safe preservation is unavailable.

## Related

- [DFA operations](activity-dfa-alpha1.md) and [configuration](config-and-secrets.md).
- [Statsig setup verification](../dev/codex-statsig-mcp-verification-20261003.md).
- Session-only confirmed execution: `/tmp/praxys-dfa-gate-execution-confirmed-20261003.json`; declared self-excluding content digest `sha256:4769e980a9f747b68ad629c644871abd16283dab87330aea9586c73abbcae0e5`, raw file SHA-256 `d4d599653ffecd841a454a6a29c8f5d69208095e4c442cdd7cace3888a4b8817`.
- Session-only original ODR: `/tmp/praxys-dfa-gate-plan-20261003.json`; declared content digest `sha256:b301108e2472193005e58f5f4b18aca2f530594a4d7fc809c54675b2e49f4e68`, raw file SHA-256 `a5fbb8a417b61f66f96a27daae0a6e26fa18901b1a7e9a40eb0d9d711878a644`.
- Session-only blocked execution: `/tmp/praxys-dfa-gate-execution-20261003.json`; declared content digest `sha256:9e628db785894f32bc70332b5aeb3a901ad4cb72697649d0add9bda5db53e9e6`, raw file SHA-256 `8fe3c72e8e44f270d966f894eb631230d6372ac5ad1ac5b586279f9bcf47a09b`.
- Frozen proposed payload digest: `sha256:74f10ddf18d74f1560bd681f58a21444b4b720cb95ea8eba43a8d341bed12468`; not a full confirmed-tool-arguments hash.

Session-only paths are not durable repository artifacts. Content digests exclude
`digest` and use sorted compact JSON; confirmed evidence additionally requires
`ensure_ascii=False` for its Chinese authorization strings. Raw hashes bind file bytes.
