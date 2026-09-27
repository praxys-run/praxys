# Garmin Connect IQ archives

Original FIT files live in `garmin_fit_snapshots.raw_fit` in the existing
private SQL database: PostgreSQL BYTEA, SQLite BLOB. They are not stored in the
repository, a public bucket, or ephemeral application files. Backups contain
both original bytes and the larger decoded projection tables. Account deletion
explicitly removes all five archive/job tables for that user; backup expiry
continues to follow the existing retention/restore policy.

## Scheduling and recovery

The existing sync scheduler runs one Connect IQ batch per tick after normal
sync work. A batch discovers at most one page of 100 activities over the
requested inclusive date range and processes at most ten activity originals.
Calls use the existing 0.5-second Garmin delay. Jobs rotate by last update;
one running job per owner is enforced by a partial unique SQL index. A
600-second tokenized lease and conditional claim protect multiple app workers.
Expired claims are recovered on subsequent ticks. A restart needs no in-memory
job state. Disabling the existing scheduler also pauses these jobs.

Daily Garmin activity discovery queues missing originals regardless of Connect
IQ field recognition. Deployment does not start a whole-history backfill.
Historical work starts only through the authenticated backfill API. Original
archive work does not run historical recovery or AI recommendations.

Status is `queued`, `running`, `retry`, `paused`, `complete`,
`completed_with_errors`, or `cancelled`. Individual activities distinguish
`unavailable`, `download_failed`, and `parse_failed`. Transport failures retry
with the existing 1-hour exponential backoff up to 24 hours, shared with the
connection's next-retry deadline. Authentication or account/generation changes
pause work; reconnecting does not silently resume old tasks. The owner calls
`/resume`; the worker checks the immutable Garmin profile identity before
reading activities. A different account is refused. Cancellation, inactive or
deleted users, expired leases, connection changes and loss of Terms/channel
processing authorization prevent stale workers committing archive data.

To reparse locally after a parser upgrade, use the owner's archive reparse
endpoint. It requires no Garmin connection and retains the previous successful
projection when parsing fails. Raw originals are committed before parsing in
the background download path, so process failure cannot discard a completed
download. Retrying an already retained original reuses its bytes.

## Capacity and diagnostics

Guardrails are 64 MiB downloaded/decompressed originals, 128 ZIP entries,
2,000,000 FIT frames, 16,384 descriptor generations, 120 seconds parsing and
120 seconds streamed download. ZIP paths are never extracted to disk. Large or
malformed inputs fail explicitly and require operator investigation; they are
not silently truncated. Parsing stores batches of 128 frames. Original and
JSON projection storage can differ greatly; budget backup/database capacity
using measured table sizes, not FIT bytes alone. Metadata-only logs identify
job status/error codes; never log payloads, credentials, filenames or FIT data.

PostgreSQL operators can inspect existing database size instrumentation or run
read-only SQL in the approved database console:

```sql
SELECT status, count(*) FROM garmin_connectiq_jobs GROUP BY status;
SELECT status, count(*) FROM garmin_connectiq_items GROUP BY status;
SELECT relname, pg_total_relation_size(relid) AS bytes
FROM pg_catalog.pg_statio_user_tables
WHERE relname LIKE 'garmin_fit_%' OR relname LIKE 'garmin_connectiq_%';
```

No new alert/config/secret or infrastructure resource is created. The standard
backup and restore procedure covers the new SQL tables. Verify original SHA-256
and parsed-version counts after restore. For rollback, stop the existing
scheduler and roll back application code while retaining the additive tables;
do not downgrade/drop archive tables unless permanent data loss is intended
and separately authorized.

## Complete account exports

The account export endpoint streams the complete document, including all FIT
parse versions and actual frame values. It reads one archive JSON chunk at a
time instead of constructing the full archive history in application memory.
Long histories can still produce large downloads and hold a read transaction
for the duration of the stream; plan bandwidth and database connection capacity
accordingly. The original-file links are additional conveniences, not substitutes
for the exported frame values.

Transient original-download failures leave their activity queued for retry,
with a nonzero attempt count and sanitized `download_failed` error. Successful
retry clears the error. `/items` distinguishes never-attempted entries from
these retrying entries. The original transport bypasses upstream error-body
rendering, reads no error JSON/text, closes failed responses, and performs the
normal single 401 token-refresh retry using the authenticated Garmin session.
The adapter depends on the pinned-range client's authentication primitives;
revalidate its transport tests before changing garminconnect versions.
