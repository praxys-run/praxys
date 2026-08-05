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
  available independently of experimental writes. `Garmin workout calendar
  fetch failed` means a month could not be
  read; `Garmin workout calendar payload was unavailable` means the
  undocumented response no longer matched the verified `calendarItems` shape.
  Both preserve the last complete snapshot instead of inferring deletions.
- Garmin consumer-API delivery is an unsupported, duration-only experiment and
  is off by default. It requires explicit connection- and region-bound consent
  in Settings. Reconnect, credential rotation, or disconnect invalidates
  consent. A legacy connection with no mirrored region must reconnect before
  consent can be granted. Region change disconnects the old region, clears its
  token cache, and requires a fresh login. Interactive reconnect first commits
  consent revocation, a delivery pause, and `disconnected` status, then mutates
  the tokenstore; an interrupted login therefore stays fail-closed. No
  international or CN live write
  matrix has been completed; do not enable or repair consent administratively.
  See the
  [feasibility decision](../studies/garmin-workout-delivery-feasibility.md).

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
`UserConnection`, but remains default-off. Each run refreshes the execution
target calendar, reconciles ownership, and then considers only Praxys-owned
ledger rows in a 14-day horizon. Manual workouts and workouts from another coach
are observations/conflicts, never mutation candidates.

Start in **Admin → Operations → Managed plan delivery**. The aggregate separates
enabled/paused athletes, durable delivery states, retry exhaustion, and stuck
in-flight attempts. The operator queue is pseudonymous and intentionally omits
email, raw user id, provider account/workout ids, canonical ids, workout
date/content, credentials, and raw errors.
It shows only the latest authoritative version for each canonical workout.
Failed managed removals remain visible even though their delivery row safely
returns to `synced` until deletion succeeds.

### Diagnose

1. Confirm the managed-plan aggregate shows the athlete as adopted and delivery
   enabled. If the athlete intentionally paused or left managed mode, do not
   override that policy.
2. Use the queue's failure domain:
   - **Provider authentication**: ask the athlete to reconnect the execution
     target. Credential rotation changes the connection generation and fences
     every stale delivery attempt.
   - **Provider failure**: check the provider status and the
     `praxys-managed-plan-provider-failures` alert. One athlete's bad credential
     is not systemic; five affected athletes for one target in 15 minutes pages.
   - **Praxys defect**: use the `praxys-managed-plan-defects` alert and inspect
     safe `praxys.managed_plan` category/action/reason dimensions.
   - **Ownership conflict / uncertain provider outcome**: the athlete must use
     plan reconciliation. Never force replay.
   - **Experimental Garmin policy**: confirm the connection is healthy and ask
     the athlete to review and re-enable consent in Settings. Never copy the
     consent hash or enable it directly in the database. Unsupported target
     shapes require choosing Stryd or revising the canonical workout; do not
     strip target data to force a Garmin write.
3. If needed, search logs for `Managed delivery blocked`, `Managed removal
   failed`, or `Managed replacement blocked`. Logged categories are bounded;
   provider credentials and payloads are never logged.

### Recover

Automatic retry is durable: 15 minutes initially, exponential backoff capped at
6 hours, with at most five failed automatic attempts after the last success.
For a queue item marked **recoverable**, choose **Reconcile and replay**, read
the inline safety statement, then confirm:

1. The backend checks the queue's exact delivery version under the per-user plan
   write lock. A changed row returns HTTP 409 and refreshes the queue.
2. It fetches a fresh provider calendar before any mutation and recovers an
   expired in-flight attempt from observed provider state.
3. It allows one retry-limit/backoff override only for the selected delivery,
   latest attempt, state, and operation. All ownership, provider-account,
   connection-generation, canonical-version, pause, and target gates still
   apply.
4. It appends `managed_recovery_requested` and
   `managed_recovery_completed` audit revisions. Equivalent requests within the
   lease are idempotent/busy; do not submit repeatedly.

Do **not** edit `plan_deliveries` or `plan_delivery_attempts` by hand. Do not
mark a provider write successful from a log line, and do not replay
`provider_outcome_unknown`, target edits/deletions, account mismatches, or
non-managed failures. Those states are intentionally non-replayable because a
blind create/remove could duplicate or delete someone else's workout.

### Pause, leave, cleanup, and rollback

- **Pause** stops before the next provider write and keeps delivered workouts.
  Resume starts with fresh calendar reconciliation.
- **Leave managed mode** also keeps delivered workouts by default. If the
  athlete explicitly requests cleanup, the cleanup endpoint removes only
  future ledger-owned workouts; external/manual workouts remain untouched.
  Failed cleanup stays visible and retryable through its normal guarded path.
- **Application rollback** never deletes canonical plans: they remain in the
  Praxys database. Delivery uniqueness, attempt leases, provider-calendar
  refresh, account/ownership checks, and the frozen legacy `ai:` compatibility
  namespace prevent old/new workers from creating duplicate target workouts.
  Roll back code through the normal deployment workflow; do not roll back by
  deleting ledger rows.

## Verify

After recovery: trigger a sync (Settings → Sync, or `POST /api/sync`), confirm the
connection card leaves `auth_required` and new activities/recovery rows appear.
A healthy Garmin read also has no calendar warning and refreshes only
Garmin-sourced external plan observations inside its bounded window. Calendar
sync alone never grants write consent. For managed plans, confirm the next
scheduler tick creates only missing Praxys-owned workouts inside the 14-day
horizon. For an athlete who explicitly enabled experimental Garmin delivery,
also confirm each delivered row has one visible scheduled instance and that
unrelated/manual workouts are unchanged; retained Praxys templates are
intentional.

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

For an operator recovery, refresh Admin Operations and confirm the selected row
left the queue or moved to an explicitly athlete-resolved conflict. Confirm the
append-only request/completion revisions exist and that the provider calendar
contains at most one ledger-owned copy. Verify any manual or other-coach workout
that shared the calendar is unchanged.

## Related

- [incident-response.md](./incident-response.md) · `docs/dev/gotchas.md` · `scripts/garmin_diagnose.py`

---
_Last reviewed: 2026-08-02 · Owner: @dddtc2005_
