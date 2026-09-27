# Stryd Connect IQ archive coverage

## Accepted behavior and decision attribution

The user explicitly approved the full Stryd Connect IQ implementation plan in
this conversation, including private SQL storage of original FIT bytes,
independent Garmin/Stryd records, owner APIs/export, and resumable historical
collection. Existing analysis source preference, power selection, and UI stay
unchanged. This document records that approval; it is not a fabricated
artifact-digest approval or an approval by Engineering.

Work Contract: `sha256:ff144a716655fcdd74fe0aa80929fa00b69b149c0d5010b3fdc6dd4acfa7de6e`.
Praxys Change Loop coordinated these read-only role contributions:

- Product `/root/stryd_product_record` transcribed the approved promise: retain
  every developer-field occurrence actually present in obtainable originals;
  distinguish acquisition completeness, interpretation coverage, unavailable
  originals, and failed parsing. No new product approval was created.
- Architecture `/root/stryd_architecture` proposed tenant/account/activity/hash
  snapshots, ordered native/developer frames and descriptor generations,
  independent pinned parsing, atomic activation, bounded durable work, explicit
  export/deletion, and additive SQLite/PostgreSQL compatibility.
- Trust `/root/stryd_trust` required owner reads, write-access mutation guards,
  encrypted credentials outside task payloads, current generation/account/Terms/
  active-user/channel/cancel/lease fences, bounded inputs, and sanitized errors.
  The approved SQL storage choice supersedes its alternative blob proposal.
- Independent Decision Review Router `/root/review_stryd_decision` returned
  `human-review-required`, with the human slot already satisfied by the user's
  exact plan approval. No new human authorization is asserted here.

Engineering executes; fresh Quality and Trust instances review the completed
patch independently. There is no Operations role or deployment authorization
in this Work Contract. The operations runbook documents the implementation.

## Implementation impact map

| Area | Change and invariant |
| --- | --- |
| Data | Five private SQL tables: original snapshots, parse versions, chunks, durable jobs and activity checkpoints. Sync upserts remain in `db/sync_writer.py`. |
| Parser | `fitdecode==0.11.0` independent of COROS `fitparse`; every frame has index, byte offset and exact base64 bytes. Ordered fields retain types, raw values, metadata references, units and optional interpretations. |
| Analysis | No writes to existing analytical sample/split fields; existing Garmin/Stryd power precedence remains unchanged. |
| API | Owner-only catalog, fixed-parse pagination, structured export, original download, offline reparse, and create/query/resume/cancel backfills. No MCP allowlist expansion. |
| Clients | No web or miniapp changes. |
| Operations | Existing scheduler consumes bounded batches, applies provider backoff, and resumes expired durable claims. Storage/backup load grows with raw plus decoded data. |
| Migration | Additive Alembic revision `0a1b2c3d4e5f`; SQLite create_all includes the same tables. BYTEA/BLOB selected by SQLAlchemy LargeBinary. |
| Privacy | Archive/projection/checkpoint rows are explicitly included in account deletion; account export includes caller-only values and authenticated original URLs. |

## Source evidence and mapping limits

The mapping registry is supported by public real FIT samples from
[GoldenCheetah](https://github.com/GoldenCheetah/GoldenCheetah), pinned commit
`f12e72296b50e4e8215e9ff90764922629a56659`:

| Source | SHA-256 | Observed application |
| --- | --- | --- |
| `test/roundtrip/Fr955v19.28andStryd.fit` | `3c4bf0fbf982d88d1384da1ab6edfa16f2d5cb1b295e405233a214b585f224f2` | Power Zone `18fb2cf0-1a4b-430d-ad66-988c847421f4`, version 143 |
| `test/runs/StrydPower-mutiple-float-values.zip` (container) | `52962e156a7d9f3d373c36b5cce4a994d522fc239cb4eb6ad027d1f42468a9d3` | Legacy `660a581e-5301-460c-8f2f-034c8b6dc90f`, version 50 |
| FIT inside that ZIP | `5d9c0e4652686f2b046488a4f4cfa6db341edce17cb185fce0ece2b8025bee3d` | Legacy Stryd plus another developer application with overlapping field numbers |

Real activity/GPS measurements are not committed. The checked-in
`tests/fixtures/connectiq/stryd-field-metadata.json` contains only field
metadata; synthetic fixtures exercise values and protocol edges. Both actual
files passed strict CRC and reconstruct byte-for-byte from projected raw
frames in local implementation checks. Power Zone: 12,862 frames, 28,074
developer occurrences, 15 descriptors. Legacy sample: 1,519 frames, 12,978
occurrences across both apps, 15 descriptors.

| Scope | Exact observed Stryd mappings |
| --- | --- |
| Both apps, record | 0 power, 2 cadence, 3 ground contact time, 4 vertical oscillation, 8 form power, 9 leg spring stiffness |
| Legacy, record | 7 elevation |
| Power Zone, record | 11 air power, 15 humidity, 16 temperature |
| Power Zone, lap | 10 average power |
| Power Zone, session | 99 critical power, 100 baseline humidity, 101 baseline temperature, 17 weight, 18 height |

Mapping requires the application UUID, message scope, field number and observed
unit. Unknown apps/fields/units remain retained and uninterpreted. New Stryd
versions are collected without a whitelist; their semantics are not claimed as
verified. No paired real Garmin JSON was available. Source FIT descriptors
support these mappings; they do not establish all future Stryd field semantics
or the scientific validity of device estimates.

## API and encoding contract

Base prefix is `/api`. All reads resolve the authenticated caller rather than
demo data redirection. Mutations additionally reject demo identities.

- `GET /activities/{activity_id}/connectiq`: acquisition status plus snapshots,
  active parse identifiers, catalog and latest parsing failure.
- `GET /activities/{activity_id}/connectiq/messages?parse_id=...&offset=0&limit=128`:
  up to 512 frames, fixed immutable parse version, `next_offset` or null.
- `GET /activities/{activity_id}/connectiq/export?parse_id=...`: streamed JSON.
- `GET /activities/{activity_id}/connectiq/original/{snapshot_id}`: exact FIT bytes,
  private/no-store, safe generated filename and hash ETag.
- `POST /activities/{activity_id}/connectiq/original/{snapshot_id}/reparse`:
  reparse retained bytes without Garmin access; atomically activate only success.
- `POST /sync/garmin/connectiq-backfills`: JSON `from_date` and `to_date`, inclusive,
  no future dates; returns HTTP 202 and job progress.
- `GET /sync/garmin/connectiq-backfills/{job_id}` and POST suffixes `/resume`,
  `/cancel`: durable progress and explicit lifecycle controls.

Typed values use `{type,value}`: integers are decimal strings, floats use Python
hex notation (including non-finite strings), byte values are base64, arrays
contain typed elements, and invalid decoded values use type `invalid` with null.
Raw frame bytes remain authoritative for invalid sentinels and unsupported
metadata. Field arrays preserve duplicate names and timestamps. Native values
are preserved too; Stryd normalization does not replace Garmin fields.

An original may be stored while parsing failed. Such a result is never marked
complete. Previous successful versions remain readable if a later reparse
fails. Parser/resource limits yield explicit failure; there is no silent
truncation. Account export schema version is 7.

Job checkpoints are available through
`GET /sync/garmin/connectiq-backfills/{job_id}/items?offset=0&limit=100`
(maximum 200 per page). Each entry identifies the activity, status, attempts,
snapshot and sanitized failure code. For example, an authenticated first-party
client can POST `{"from_date":"2025-01-01","to_date":"2025-12-31"}` to create a
year backfill, poll its returned job ID, and page through `/items` to identify
missing originals. Use a returned `parse_id` for every subsequent messages or
export request to keep pagination fixed even after reparse.

## Independent review and repair record

Independent Quality and Trust reviewed candidate
`bab693defc42f664e19ada3fd111fe0a67adb256`. They found four defects, which this
revision repairs; this record does not assert approval of the revised patch:

- Quality: whole-account export eagerly loaded every FIT frame and parse
  version. It now streams the complete JSON document through lazy snapshot,
  version and 128-frame-chunk iterators. Every value/version remains included;
  the output is not replaced by a link manifest. Tests exercise lazy chunk
  loads, multiple complete versions and byte-for-byte reconstruction.
- Quality: transient original-download failures lacked activity checkpoints.
  A fenced attempt count and sanitized `download_failed` code now commit before
  job retry/backoff. The item remains queued for automatic retry; successful
  retry clears its error. A timeout-to-success scheduler test checks both states.
- Trust: the upstream request wrapper consumed/logged error bodies before the
  archive size limit applied. The bounded original adapter now uses the client's
  authenticated session/header/refresh primitives, never reads HTTP error bodies,
  closes every response and retains a single 401 refresh retry. Tests cover
  large error responses, redirects, 401/404/410/429/503 and refresh success.
- Trust: cancellation during login was checked only after the next profile
  request. Fresh authority checks now precede that request and discovery, with
  transaction locks released before network calls. The regression asserts no
  profile request occurs after a login-time cancellation.

Root's isolated PostgreSQL 16.15 environment exercised additive migration
upgrade/downgrade and 15 existing archive, API, deletion, lease, generation,
Terms, and reparse scenarios successfully. Engineering also reran those 15
scenario functions against the repaired code. This is local scratch-database
evidence, not a production migration or deployment claim. The revised candidate
still requires the same independent reviewers to verify its new commit.

Repair validation: 244 focused/regression tests passed, followed by 34 focused
export/repair tests after the final frame-serialization optimization. The
isolated PostgreSQL rerun passed 18 scenarios, including the three new lazy
export, transient-retry, and login-cancellation cases. A local `tracemalloc`
measurement streamed the real 333,889-byte Power Zone fixture's complete
42,159,220-byte JSON archive with 9,512,778 peak tracked Python bytes in 5.91
seconds. This is a single-fixture implementation measurement, not a production
capacity guarantee; the existing non-Connect-IQ export builders retain their
prior memory behavior.
