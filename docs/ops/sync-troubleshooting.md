# Sync troubleshooting

> **Summary:** Diagnose and recover stuck platform syncs (Garmin / Stryd / Oura).
> **Use when:** A user's dashboard data or managed workouts stop updating, or a
> connection card shows `auth_required`.

Domain detail lives in [`docs/dev/gotchas.md`](../dev/gotchas.md) → "Garmin sync";
this is the operational quick-path.

## #1 cause: the Garmin auth gate (`auth_required`)

By far the most common incident. Garmin/Cloudflare bot-detection trips the
headless login; the connection goes to the **`auth_required`** terminal state and
the scheduler stops retrying that user (by design — PR #256). **Do not "fix" it
with code or retries** — every fresh attempt from the App Service IP feeds the
bot score and keeps the gate hot.

**Confirm it's this:**
```kql
AppTraces | where timestamp > ago(24h)
  | where Message has "All login strategies exhausted" or Message has "IP rate limited by Garmin"
```
Or run `python scripts/garmin_diagnose.py login` — non-JSON HTML with
`challenges.cloudflare.com` = the same gate.

**Recovery (what to tell the user):**
1. Sign in at `connect.garmin.com` in a real desktop browser, complete any CAPTCHA
   (clears the account-level flag).
2. **Wait** — the per-(IP, account) gate decays on its own over hours to a day or
   two **as long as the scheduler stays parked** (it does in `auth_required`).
3. Click **Reconnect** in Praxys Settings. Success clears the backoff and the
   scheduler resumes; if it still fails, wait another half-day and retry.

Do **not** build an interactive CAPTCHA relay — Cloudflare keys on TLS
fingerprint/account history, not JS signals (closed PR #257).

## Garmin CN quirks

- `garmin.com` ≠ `garmin.cn` — separate accounts; region is captured at connect.
  To change region the user disconnects + reconnects with the other account.
- Individual CN endpoints 400/404 even on healthy accounts (LTHR, some training
  status). Each endpoint has its own try/except + a 5-strike circuit breaker, so
  one failure doesn't sink the sync. LTHR may need manual entry.
- Scheduled-workout calendar reads use the same region-routed client but remain
  read-only. `Garmin workout calendar fetch failed` means a month could not be
  read; `Garmin workout calendar payload was unavailable` means the
  undocumented response no longer matched the verified `calendarItems` shape.
  Both preserve the last complete snapshot instead of inferring deletions.
  Garmin delivery remains unavailable: the
  [#484 feasibility study](../studies/garmin-workout-delivery-feasibility.md)
  rejected production consumer-API writes, and #485 is blocked pending the
  official Training API contract.

## Per-user token store (security-critical)

Tokens live at `sync/.garmin_tokens/<user_id>/`. This per-user isolation is
load-bearing — `garminconnect` loads whatever tokens it finds without validating
the account, so a shared dir would cross-leak sessions. `clear_garmin_tokens()`
runs on rotate/disconnect/delete and must propagate `OSError`. **Never** share or
relocate this store.

## Reading sync health

All per-source failures log at `warning`+ (debug once hid CN failures for months).
Aggregate warnings fire at ≥ max(3, total/2) failures; HRV/sleep circuit-break
after 5 consecutive. Check `az webapp log tail -n trainsight-app -g rg-trainsight`.

## Managed-plan delivery is paused or stuck

Rolling delivery shares the background scheduler and the target's
`UserConnection`, but it remains default-off. Confirm these conditions before
investigating the provider:

1. `user_config.plan_management` has `mode=praxys`,
   `delivery_enabled=true`, and the expected `execution_target`.
2. The target connection is `connected`. Credential decode failures move it to
   `auth_required`; reconnecting is the recovery path.
3. Search logs for `Managed delivery blocked`, `Managed removal failed`, or
   `Managed replacement blocked`. The logged category is safe to use for
   triage; provider credentials and payloads are never logged.
4. Inspect `plan_delivery_attempts.response` for `managed_delivery=true`,
   `error_category`, and `retryable`.

HTTP 429 creates and idempotent removals use durable exponential retry (15
minutes initially, capped at 6 hours and 5 failed automatic attempts).
Timeouts, HTTP 408/5xx creates, target edits/deletions, and account mismatches do
not auto-retry because the provider outcome or ownership is unresolved. Resolve
the affected workout through plan reconciliation instead of deleting unrelated
target workouts. Pausing delivery or switching to external mode takes effect
before the next write and intentionally keeps already-delivered workouts.

## Verify

After recovery: trigger a sync (Settings → Sync, or `POST /api/sync`), confirm the
connection card leaves `auth_required` and new activities/recovery rows appear.
A healthy Garmin read also has no calendar warning and refreshes only
Garmin-sourced external plan observations inside its bounded window. It never
writes to Garmin. For managed plans, confirm the next scheduler tick creates
only missing Praxys-owned workouts inside the 14-day horizon.

For users who separately enabled conservative automatic adjustment, search for
`Plan adjustment for user=` after the sync completion log. `adjusted` means the
canonical mutation committed; provider delivery may still report its own
best-effort outcome. `suggestion`, `no_change`, and `disabled` are successful
fail-closed decisions, not sync failures. An exception is logged as
`Post-sync plan adjustment failed` and intentionally does not change the
platform sync result. `Plan adjustment delivery audit remains pending` means
the canonical change committed but its append-only delivery-consequence event
did not; the next evaluation of the same still-current adjustment retries that
audit path.

## Related

- [incident-response.md](./incident-response.md) · `docs/dev/gotchas.md` · `scripts/garmin_diagnose.py`

---
_Last reviewed: 2026-08-02 · Owner: @dddtc2005_
