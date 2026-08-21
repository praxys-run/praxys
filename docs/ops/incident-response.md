# Incident response — service degraded or down

> **Summary:** First-response triage for "the app is down / erroring".
> **Use when:** Health checks fail, users report outages, or alerts fire.

```ops-runbook
version: 1
id: incident-response
autonomy: bounded
summary: Restore backend or frontend availability with reversible restarts.
signals:
  - id: api-health
    tool: http.get
    policy: observe
    command: curl -fsS --connect-timeout 5 --max-time 15 https://api.praxys.run/api/health
    success:
      stdout_contains: '"status":"ok"'
  - id: api-ready
    tool: http.get
    policy: observe
    command: curl -fsS --connect-timeout 5 --max-time 15 https://api.praxys.run/api/health/ready
    success:
      exit_code: 0
  - id: frontend-health
    tool: http.get
    policy: observe
    command: curl -fsS --connect-timeout 5 --max-time 15 https://www.praxys.run/healthz
    success:
      exit_code: 0
  - id: backend-state
    tool: azure.appservice.show
    policy: observe
    command: az webapp show -n trainsight-app -g rg-trainsight --query state -o tsv
    success:
      stdout_equals: Running
actions:
  - id: restart-backend
    tool: azure.appservice.restart
    policy: autonomous-reversible
    command: az webapp restart -n trainsight-app -g rg-trainsight
    rationale: Clears a failed or wedged API process without changing data or configuration.
  - id: restart-frontend
    tool: azure.appservice.restart
    policy: autonomous-reversible
    command: az webapp restart -n praxys-frontend -g rg-trainsight
    rationale: Recycles the static frontend host without changing data or configuration.
routes:
  - id: backend-unhealthy
    when:
      - signal: api-health
        outcome: failure
    hypothesis: The backend process is stopped, crashed, or wedged.
    action: restart-backend
    verify:
      - api-health
      - api-ready
    on_failure: escalate
  - id: frontend-unhealthy
    when:
      - signal: api-health
        outcome: success
      - signal: frontend-health
        outcome: failure
    hypothesis: The frontend App Service is stopped or unhealthy while the API is available.
    action: restart-frontend
    verify:
      - frontend-health
    on_failure: escalate
  - id: database-unready
    when:
      - signal: api-health
        outcome: success
      - signal: api-ready
        outcome: failure
    hypothesis: The API process is live but cannot reach the database.
    action: restart-backend
    verify:
      - api-ready
      - api-health
    on_failure: escalate
```

The structured block permits only reversible App Service restarts. PostgreSQL
restart, restore, rollback, configuration changes, and data operations require
human approval even when the prose below recommends them.

## Severity and ownership

| Severity | Definition | Handling |
|---|---|---|
| SEV-1 | Broad service outage, active data-loss risk, or authentication unavailable for most users. | The operator receiving the `praxys-feedback-ag` action-group alert owns first response; publish a status incident and escalate to `@dddtc2005` before any destructive or data-changing action. |
| SEV-2 | Material degradation or one platform failing for multiple users while core service remains usable. | Operator investigates during the current operating window and escalates if the blast radius grows or no safe mitigation exists. |
| SEV-3 | Isolated user issue, non-urgent defect, or alert requiring follow-up but no active service impact. | Track in GitHub and handle through the normal change loop. |

There is no staffed 24x7 rotation yet. The Azure action group is the routing
source of truth; private contact details stay in Azure rather than this public
repository. If the owner cannot be reached, preserve data, avoid non-reversible
actions, update the status page, and leave the incident escalated.

## Quick triage

```bash
curl -s --connect-timeout 5 --max-time 15 https://api.praxys.run/api/health      # expect {"status":"ok"}
curl -s --connect-timeout 5 --max-time 15 https://api.praxys.run/api/version     # which build is live?
curl -s --connect-timeout 5 --max-time 15 -o /dev/null -w "%{http_code}\n" https://www.praxys.run/healthz   # expect 200
```

| Symptom | Likely area | Go to |
|---|---|---|
| `/api/health` fails / 5xx | backend down or crashing | **Backend** below |
| `/healthz` fails, API ok | frontend host | **Frontend** below |
| Both ok, data stale for some users | sync stuck | [sync-troubleshooting.md](./sync-troubleshooting.md) |
| Started right after a deploy | bad release | [deploy.md](./deploy.md) → Rollback |
| `/api/health` ok **but pages 500** | DB unreachable (readiness masks it) | **Database** below |
| Errors mention DB / disk / connection slots | Postgres / migration | **Database** below |

## Backend (`trainsight-app`)

```bash
az webapp show -n trainsight-app -g rg-trainsight --query state -o tsv   # Running?
az webapp log tail -n trainsight-app -g rg-trainsight                    # live logs
az webapp restart -n trainsight-app -g rg-trainsight                     # first lever
```

App Insights (Logs blade) — recent failures + the known Garmin storm signal:
```kql
exceptions | where timestamp > ago(1h) | summarize count() by type, outerMessage | top 20 by count_
AppTraces | where timestamp > ago(2h)
  | where Message has "All login strategies exhausted" or Message has "IP rate limited by Garmin"
```

## Frontend delivery

```bash
# Current public frontend and Azure origin
curl -fsS --connect-timeout 5 --max-time 15 https://www.praxys.run/healthz
az webapp show -n praxys-frontend -g rg-trainsight --query state -o tsv
az webapp restart -n praxys-frontend -g rg-trainsight
```

After the regional cutover has accepted Release Evidence, add the provider
checks below to the first-response path:

```bash
curl -fsSI --connect-timeout 5 --max-time 15 https://www.praxys.run/ | grep -i '^cf-ray:'
curl -fsS --connect-timeout 5 --max-time 15 https://praxys.cn/deployed_sha.txt
curl -fsS --connect-timeout 5 --max-time 15 https://praxys.cn/ | grep -F '沪ICP备2025109616号-2'
```

At that point, if `.run` fails but the Azure origin is healthy, inspect
Cloudflare before restarting App Service. If `.cn` fails, inspect `praxys-cn`
in EdgeOne; an Azure restart cannot repair it. See
[tencent-frontend.md](./tencent-frontend.md).

## Database (`praxys-pg`, Postgres)

Liveness `/api/health` returns 200 even when the DB is down — **check
readiness**, which runs a real `SELECT 1`:

```bash
curl -s --connect-timeout 5 --max-time 15 https://api.praxys.run/api/health/ready   # ready 200  vs  503 {"database":"error"}
```

A 503 here means the app can't reach Postgres. Most often it's **connection
exhaustion**, not a server outage.

### Connection exhaustion (the 2026-07-05 outage)

**Signature:** readiness 503; App Insights `exceptions` show
`OperationalError ... FATAL: remaining connection slots are reserved for roles
with the SUPERUSER attribute`. The Burstable **B1ms** server has
`max_connections=50` with ~15 reserved → only **~35 usable by the app**. Near
that ceiling new app logins are refused and every data endpoint 500s.

**Diagnose** (`$PG` = the praxys-pg resource ID):

```bash
az postgres flexible-server show -g rg-trainsight -n praxys-pg --query state -o tsv   # usually "Ready" — it is a client-side connection problem
az monitor metrics list --resource "$PG" --metric active_connections --interval PT1M --aggregation Maximum --query "value[0].timeseries[0].data[-10:]" -o json   # pegged near 50?
az monitor app-insights query --app appi-praxys-backend --analytics-query "exceptions | where timestamp > ago(1h) | where outerMessage has 'remaining connection slots' | count"
```

**Mitigate — in order:**

1. `az webapp restart -n trainsight-app -g rg-trainsight`. **Often does NOT
   help:** connections abandoned by prior container cycles linger idle
   server-side and survive an app restart. Watch `active_connections`; if it
   doesn't drop within a minute, go to step 2.
2. **Restart Postgres** — the decisive lever; hard-resets every backend:
   ```bash
   az postgres flexible-server restart -g rg-trainsight -n praxys-pg
   ```
   ~1 min of DB downtime, acceptable when the service is already fully down. You
   **can't** surgically `pg_terminate_backend()` — only superuser-reserved slots
   remain, so even an Entra-admin login is refused. Verify readiness → 200 and
   `active_connections` drops below ~15.

**Prevent / root cause:** abandoned SQLAlchemy pools pile up as idle "zombie"
backends across container recycles (worsened by a per-tick `init_db()` that
rebuilt the pool). Fixed by disposing engines on shutdown + idempotent
`init_db()` (`db/session.py`), `alwaysOn=true` (fewer recycles), and the
`praxys-pg-connections-high` early-warning alert. Budget + tuning:
[config-and-secrets.md](./config-and-secrets.md).

### Corruption / bad migration

- A boot crash-loop citing the DB is usually a bad migration — check boot logs
  (`az webapp log tail`) for `init_db` / Alembic errors.
- Corruption suspected → [backup-and-restore.md](./backup-and-restore.md).

## Escalate / rollback

- Bad deploy → revert on `main` or re-tag a good build ([deploy.md](./deploy.md)).
- Can't resolve quickly → restart buys time; restore from backup if data is at risk.

## Verify

Health endpoints green; error rate back to baseline in App Insights; spot-check a
user dashboard.

## Related

- [deploy.md](./deploy.md) · [sync-troubleshooting.md](./sync-troubleshooting.md) · [monitoring-and-alerts.md](./monitoring-and-alerts.md)

---
_Last reviewed: 2026-08-06 · Owner: @dddtc2005_

## Road 10K control incident

Treat any authority/schema mismatch, cap mismatch, provider-fence access,
owner isolation issue, unauthorized enrollment/adoption, deletion or restore
failure, or screenshot upload as a zero-tolerance incident.  The server
denies the affected boundary; Operations may apply the independent kill or
pause authority, but no client, cache, environment toggle, or application
writer can resume it.  Preserve adopted plans unchanged.

For deletion or restore failures, keep the payload-free marker, block
readiness, and replay before traffic.  Do not reconstruct counts from logs or
retain raw owner data.  Escalation, live alerts, actor binding, and production
purge scheduling remain deferred until a separate Operations decision.
