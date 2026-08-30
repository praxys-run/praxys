# Disaster recovery - rebuild from scratch

> **Summary:** Recreate the whole Praxys deployment in a fresh resource group /
> subscription and restore data.
> **Use when:** The resource group is lost, a region is unavailable, or you're
> standing up a parallel environment.

This runbook is a checklist that chains the others - it doesn't duplicate them.

## Recovery objectives

- **RPO** (max acceptable data loss):
  - **Postgres (post-#360):** ~5 min - Flexible Server point-in-time restore
    replays to any instant within the `--backup-retention` window (14 days).
  - **SQLite (legacy):** the backup cadence (pre-deploy + daily on-demand
    snapshots), so up to ~24h between scheduled snapshots.
- **RTO** (max acceptable downtime) = provisioning + restore time.
  No target is claimed until a timed restore drill is run; the current RTO is
  explicitly **unvalidated**. The drill requires an operator-approved Azure
  maintenance window because it creates and verifies replacement resources.

## Steps

1. **Provision infra.** Follow `docs/deployment.md` -> *Azure Setup (One-Time)*:
   resource group, App Service plan + the two sites (`trainsight-app`,
   `praxys-frontend`), Key Vault `kv-trainsight`, App Insights, managed identity
   + RBAC. For the database, provision the PostgreSQL Flexible Server per
   [postgres-migration.md](./postgres-migration.md) (or restore it in step 5).
   Resource names + IDs: [environment.md](./environment.md).
2. **Re-create the master key.** Key Vault RSA key `trainsight-master-key`. If
   this is a *new* key (old vault unrecoverable), previously-encrypted platform
   credentials can't be decrypted - users must reconnect platforms. Restoring the
   *same* vault/key preserves them.
3. **Wire CI + config.** GitHub OIDC federated credential + Actions
   secrets/variables ([config-and-secrets.md](./config-and-secrets.md)),
   including `PRAXYS_DATABASE_URL` / `PRAXYS_DB_AUTH` / `PRAXYS_PG_SERVER` when on
   Postgres.
4. **Deploy.** Push `main` (or run `deploy-backend.yml` / `deploy-frontend-appservice.yml`).
5. **Restore data.**
   - **Postgres:** PITR-restore the server (`az postgres flexible-server
     restore ...`) or reload from a `pg_dump`, then point `PRAXYS_DATABASE_URL`
     at it. See [backup-and-restore.md](./backup-and-restore.md).
   - **SQLite (legacy):** put the latest `trainsight.db` snapshot in place
     ([backup-and-restore.md](./backup-and-restore.md)).
6. **Restore delivery layers.** Point the current `api.praxys.run` and
   `www.praxys.run` records to the replacement sites and restore valid
   certificates. If the regional topology has accepted Release Evidence and
   been cut over, keep the API DNS-only, restore Cloudflare's `.run` origin
   records with `Full (strict)`, and restore/deploy `praxys-cn` independently.
   Follow [tencent-frontend.md](./tencent-frontend.md); never copy the ICP
   footer into `.run`.

## Verify

Health endpoints green (incl. `/api/health/ready`); a known user can log in and
see their historical data; a sync succeeds.

## Related

- `docs/deployment.md` (the authoritative build steps) · [postgres-migration.md](./postgres-migration.md)
  · [backup-and-restore.md](./backup-and-restore.md) · [config-and-secrets.md](./config-and-secrets.md)
  · [secret-rotation.md](./secret-rotation.md)

---
_Last reviewed: 2026-08-20 · Owner: @dddtc2005_
