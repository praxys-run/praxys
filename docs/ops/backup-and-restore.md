# Backup & restore the database

> **Summary:** Take a consistent backup of the SQLite database and restore it.
> **Use when:** Before a risky migration/deploy, on a schedule, or to recover
> from data loss / corruption.

## Which database?

The app is dual-backend (see [postgres-migration.md](./postgres-migration.md)):
after the #360 cutover the store is **Azure Database for PostgreSQL** and the
Postgres section below applies; before it (or in a SQLite-only deployment) use
the **Legacy: SQLite** section.

## Postgres: managed backups + PITR (#349)

Flexible Server provides **automated backups + point-in-time restore** when
provisioned with `--backup-retention <days>` (7-35; the migration runbook uses
14). This is the primary, always-on backup - the thing whose absence turned the
2026-07-03 SQLite corruption into a near-total-data-loss event.

> **Tier limitation:** `praxys-pg` is **Burstable** (B1ms), which does **not**
> support customer *on-demand* backups - `az postgres flexible-server backup
> create` returns `CustomerOnDemandBackupCannotBePerformedOnBurstableServer`.
> So PITR is the backup mechanism on this tier; there are no named pre-deploy /
> scheduled snapshots. (Named on-demand snapshots need a General Purpose /
> Memory Optimized tier.)

**Restore points without on-demand backup:**
- **Before a risky change / deploy:** note the current UTC time and rely on PITR
  to restore to that instant. PITR is continuous, so any second in the 14-day
  window is a restore point - no explicit snapshot needed.
- **Off-Azure / long-retention copy:** a logical `pg_dump` (see *Portable /
  off-Azure copy* below). Geo-redundant backup is **off** on this server (can
  only be set at create time), so an off-site `pg_dump` is the region-loss
  protection - tracked as a follow-up.

**Restore (PITR)** clones the server to a new server at a chosen instant:

```bash
az postgres flexible-server restore \
  --resource-group rg-trainsight \
  --name praxys-pg-restored \
  --source-server praxys-pg \
  --restore-time "2026-07-03T09:00:00Z"
# Verify the clone, then repoint PRAXYS_DATABASE_URL at it and re-deploy.
```

After any restore, start the backend before reopening traffic. Privacy
deletions are written first to the private Blob container configured by
`PRAXYS_FEEDBACK_BLOB_*`, then applied to the database:

- Labs withdrawal markers use `labs-deletions/` (local
  `DATA_DIR/labs_deletion_tombstones`).
- Adaptive-plan personal-context manifests use
  `personal-context-deletions/` (local
  `DATA_DIR/personal_context_deletion_manifests`). They contain only opaque
  owner/item/job identifiers, cleanup operation, timestamps, and completion
  state; never context payload, category, or narrative.

Startup replays both marker sets before serving traffic and retains them for
the same 14-day PITR window. Labs consent/results whose timestamps predate a
withdrawal are deleted again while a newer re-consent is preserved.
Personal-context replay reapplies owner, lineage, version, and narrative
deletions before running overdue expiry and purge work. Scoped lineage,
version, and narrative markers affect only rows created no later than the
recorded request. Account-deletion markers remove all restored context for the
owner, including context created during the live deletion window. Startup fails
closed if configured private Blob storage cannot be read or an overdue privacy
deletion cannot complete.
Database-backed external cleanup obligations are also replayed before traffic:
for every account deletion they re-delete any legacy Garmin tokenstore from
both the active and migration-quarantine roots and remove legacy plan-status
files. A pending or failed replay keeps startup
closed; inspect logs for the cleanup kind only (account identifiers and paths
must not be logged), repair the storage/permission fault, and restart. This is
limited to external local artifacts; complete pre-deletion PostgreSQL PITR
reconciliation remains tracked by #755.
Before cutover, verify that withdrawn Labs experiments and deleted personal
context remain absent.

**Portable / off-Azure copy** (optional long-retention archive, or a future
Tencent COS move) uses a logical dump - run it from inside the trust boundary
(App Service SSH or an Azure job in the VNet), not GitHub runners:

```bash
pg_dump "postgresql://.../praxys?sslmode=require" -Fc -f praxys-$(date -u +%Y%m%d).dump
pg_restore -d "postgresql://.../praxys_new?sslmode=require" praxys-YYYYMMDD.dump
```

## Legacy: SQLite (until the #360 cutover)

## What & where

The whole app state is one SQLite file: **`trainsight.db`** at
`DATA_DIR=/home/data` on the backend App Service `trainsight-app`. `/home` is
Azure App Service **persistent** storage (survives restarts/redeploys). There is
no separate managed DB — back up this file.

## Prerequisites

- `az` CLI logged in (Contributor on `rg-trainsight`).
- App Service SCM (Kudu) access — publishing creds:
  `az webapp deployment list-publishing-credentials -n trainsight-app -g rg-trainsight`.

## Steps — backup

A hot file copy can tear (SQLite WAL). Take a **consistent snapshot** with
`.backup`, then retrieve it.

```bash
# 1. SSH into the running container
az webapp ssh -n trainsight-app -g rg-trainsight
#    inside the container:
cd /home/data
sqlite3 trainsight.db ".backup '/home/data/backup-$(date -u +%Y%m%dT%H%M%SZ).db'"
exit

# 2. Download the snapshot via the Kudu VFS API (basic auth = publishing creds)
#    List: https://trainsight-app.scm.azurewebsites.net/api/vfs/data/
curl -u '<scm-user>:<scm-pass>' \
  "https://trainsight-app.scm.azurewebsites.net/api/vfs/data/backup-<ts>.db" \
  -o backup-<ts>.db
```

Store the snapshot off-box (e.g. the `perfbaselines-archive` blob on
`stperftrainsight`, or your own secure storage). Keep at least the last N daily
snapshots.

## Steps — restore

```bash
# 1. Stop the app so nothing writes mid-restore
az webapp stop -n trainsight-app -g rg-trainsight

# 2. Upload the snapshot over the live file via Kudu VFS (PUT). Also remove any
#    stale WAL sidecars so the restored .db isn't reconciled against old WAL.
curl -u '<scm-user>:<scm-pass>' -X PUT --data-binary @backup-<ts>.db \
  "https://trainsight-app.scm.azurewebsites.net/api/vfs/data/trainsight.db?recursive=false" \
  -H "If-Match: *"
# (delete trainsight.db-wal / -shm via the same VFS API if present)

# 3. Start; init_db() runs its additive migrations on boot
az webapp start -n trainsight-app -g rg-trainsight
```

## Verify

`curl -s https://api.praxys.run/api/health` → `ok`; log in and confirm recent
data is present. Check `az webapp log tail` for migration errors on boot.

## Rollback / Recovery

Keep the pre-restore file (download it before overwriting) so a bad restore is
itself reversible. If the app won't boot, restore the previous-known-good
snapshot.

## Recover from corruption (no snapshot)

If `az webapp log tail` shows `sqlite3.DatabaseError: database disk image is
malformed` and you have **no backup**, salvage the live file with SQLite's
`.recover` (it parses the b-tree pages directly and rebuilds a clean DB,
skipping unreadable pages). Run inside `az webapp ssh` (or the Kudu console):

```bash
cd /home/data
ts=$(date -u +%Y%m%dT%H%M%SZ)
# 1. Preserve the corrupt triplet (reversible if recovery goes wrong)
cp -v trainsight.db "trainsight.db.corrupt.$ts"
[ -f trainsight.db-wal ] && cp -v trainsight.db-wal "trainsight.db-wal.corrupt.$ts"
[ -f trainsight.db-shm ] && cp -v trainsight.db-shm "trainsight.db-shm.corrupt.$ts"

# 2. Salvage into a fresh file (non-destructive)
sqlite3 trainsight.db ".recover" 2>recover.err | sqlite3 trainsight.rebuilt.db
sqlite3 trainsight.rebuilt.db "PRAGMA integrity_check;"   # want: ok
sqlite3 trainsight.rebuilt.db "SELECT count(*) FROM activities;"  # sanity

# 3. Stop the app so nothing writes, then swap in the rebuilt file
az webapp stop -n trainsight-app -g rg-trainsight    # from your workstation
mv trainsight.db "trainsight.db.corrupt.main.$ts"
rm -f trainsight.db-wal trainsight.db-shm            # stale sidecars
mv trainsight.rebuilt.db trainsight.db
az webapp start -n trainsight-app -g rg-trainsight   # init_db() re-adds any missing columns
```

If the container lacks the `sqlite3` CLI, run the same `.recover` from the app
venv's Python, or `apt-get install -y sqlite3` (you're root in the SSH shell).

## Prevent corruption

`trainsight.db` sits on Azure Files (SMB). Two rules keep it safe (both enforced
in code / docs as of the WAL-corruption incident):

1. **No WAL on `/home`.** SQLite WAL needs a shared-memory index (`-shm`) that
   does not work over a network filesystem — it corrupts the file. `db/session.py`
   pins `journal_mode=DELETE` + `synchronous=FULL` for exactly this reason; do
   not switch back to WAL while the DB is on Azure Files.
2. **One writer.** Run the backend with a **single** gunicorn worker so there is
   only one process writing the SQLite file — multiple worker processes over SMB
   is the other half of the corruption trigger. Set the startup command to e.g.
   `gunicorn -k uvicorn.workers.UvicornWorker -w 1 -b 0.0.0.0:8000 api.main:app`
   (`az webapp config set --startup-file "…"`). Scale out via App Service
   instances only if you first move off SQLite (managed DB) or a WAL-safe store.

**Take a snapshot before every risky deploy** (this incident had no backup):
`sqlite3 trainsight.db ".backup '/home/data/backups/pre-deploy-<ts>.db'"`.

## Deferred operator decision

The managed Postgres retention remains 14 days and PITR is the current recovery
mechanism. A timed production restore drill is intentionally not performed by a
documentation or CI change: it provisions a billable clone and requires an
operator-selected maintenance window plus production access. Record the start
time, restored timestamp, readiness time, data checks, and cleanup time here
when that window is approved; until then the RTO is **unvalidated**, not
estimated.

## Related

- [disaster-recovery.md](./disaster-recovery.md) · [deploy.md](./deploy.md) · `db/session.py` (`init_db`, `_SQLITE_PRAGMAS`)

## Road 10K deletion replay boundary

Road evaluation and private-object deletion uses a payload-free private marker
plus a matching database obligation. The destructive database transaction
commits the obligation; startup probes marker storage only while a committed
obligation exists. Missing storage, a missing or malformed matching marker, or
a failed delete keeps readiness closed. Prepared markers without a committed
obligation are ignored, completed obligations are immutable, and empty
withdrawals do not create markers.

Evaluation expiry remains fixed at no more than 30 days from creation. The purge
primitive is unscheduled, and this change performs no purge or live restore.
Never run the destructive Road migration downgrade after any receipt, slot, or
obligation exists.

A database snapshot older than a deletion may also predate its database
obligation. Therefore repository tests do not prove post-restore reconciliation.
Before any future traffic, a separately authorized live restore drill must
reconcile current obligations with private markers and verify that evaluation
and screenshot data does not reappear. Until then this is release-only evidence
and restore safety is unvalidated.

---
_Last reviewed: 2026-08-22 · Owner: @dddtc2005_
