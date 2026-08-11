# API Reference

All endpoints are under the `/api/` prefix. The API server runs on `http://localhost:8000` by default.

**Authentication:** All data endpoints require `Authorization: Bearer <token>` in the request header. Tokens are obtained via `POST /api/auth/login`.

## Auth

### POST /api/auth/register

Register a new user.

- **First user** on a fresh DB becomes admin (no code, auto-verified).
- Email matching `PRAXYS_ADMIN_EMAIL` → admin (no code, auto-verified).
- A valid **invitation code** → normal user (auto-verified; invited users bypass the seat cap).
- **Open self-registration** (admin-enabled gate, under the committed-seat cap, no code) →
  created *unverified*; a verification link is emailed and the user cannot log in until they
  click it (see `POST /api/auth/verify`). If SMTP is not configured, the account is created
  verified instead.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "invitation_code": "TS-ABCD-1234",
  "accepted_terms": true,
  "website": ""
}
```

- `invitation_code` — optional; omit for the first user, `PRAXYS_ADMIN_EMAIL`, or an open sign-up.
- `accepted_terms` — **required** (`true`); the EULA gate.
- `website` — **honeypot**; must be empty. A non-empty value is treated as a bot and rejected.

**Response** (verified path — first user / admin email / invited):
```json
{ "id": "uuid-string", "email": "user@example.com", "is_superuser": false }
```

**Response** (open sign-up needing email verification):
```json
{ "verification_required": true, "email": "user@example.com" }
```

**Error codes:**
- `400 REGISTER_USER_ALREADY_EXISTS` — email already registered
- `400 REGISTER_TERMS_NOT_ACCEPTED` — `accepted_terms` was not `true`
- `400 REGISTER_INVALID_INVITATION` — code is invalid, used, expired, or revoked
- `400 REGISTER_FAILED` — honeypot tripped (or an opaque create failure)
- `403 REGISTER_CLOSED` — self-registration is disabled or the seat cap is reached

### POST /api/auth/login

Obtain a JWT access token. Uses FastAPI-Users auth backend.

**Request body** (form-encoded):
```
username=user@example.com&password=securepassword
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### GET /api/auth/me

Return the authenticated user's profile.

**Response:**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "is_superuser": true,
  "created_at": "2026-04-01T12:00:00"
}
```

### POST /api/auth/request-verify-token

Request (or re-send) an email-ownership verification link. Always returns `202` regardless of
whether the address exists (no account enumeration); sends an email only when SMTP is configured.

**Request body:** `{ "email": "user@example.com" }`

### POST /api/auth/verify

Consume a verification token (from the emailed link `…/verify?token=…`) and mark the account
verified, unblocking login.

**Request body:** `{ "token": "<token>" }`

Errors: `400 VERIFY_USER_ALREADY_VERIFIED`, `400 VERIFY_USER_BAD_TOKEN` (FastAPI-Users).

### GET /api/public/config

**Unauthenticated.** Minimal boot config for the login page.

**Response:** `{ "registration_open": true }`

- `registration_open` — effective state (admin flag **and** committed seats < cap). No counts or
  other operator data are exposed here.

## Admin

All admin endpoints require `is_superuser=True` on the authenticated user. Returns `403` otherwise.

### GET /api/admin/ops/summary

Privacy-safe operations overview. Query parameter `window` is one of `24h`, `7d`,
or `28d` (default `24h`). Every section includes `source`, `window`, `freshness`,
`as_of`, and an optional stable `reason` code (`section_refresh_failed`,
`azure_telemetry_not_configured`, `azure_sdk_unavailable`,
`azure_query_failed`, `azure_query_partial`, or `azure_query_timed_out`).

Database-backed attention/activity aggregates and live component health are
combined with aggregate-only telemetry from the trusted backend Application
Insights component: request/availability health, Azure alert instances,
Today/Decision Check/Coach value signals, durable agent decision/outcome
aggregates, sync reliability, systemic failure
clusters (at least five distinct users across systemic failure classes for one
platform within 15 minutes), and connection outcomes. The response contains no emails, user IDs or
pseudonyms, feedback text/screenshots, invitation codes, Coach comments, raw log
rows, or trace bodies. One failed section does not fail the whole response.
Responses are `private, no-store`; Azure-backed sections use a short server-side
cache and may explicitly report `freshness: "stale"`.

```json
{
  "generated_at": "2026-07-17T12:00:00+00:00",
  "window": "24h",
  "attention": {
    "source": "praxys_database", "window": "live", "freshness": "fresh",
    "as_of": "2026-07-17T12:00:00+00:00", "reason": null,
    "data": {
      "incident_counts": {"total": 1, "minor": 0, "major": 1, "critical": 0},
      "active_incidents": [{"id": 4, "title": "Elevated latency", "status": "investigating", "impact": "major", "started_at": "...", "updated_at": "..."}],
      "feedback": {"needs_review": 2, "failed": 1, "new": 3, "actionable": 3, "critical": 1, "high": 1, "total": 8}
    }
  },
  "service_health": {"source": "live_probe", "window": "live", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"overall": "operational", "components": [], "postgres_active_connections": 5, "postgres_max_connections": 100, "postgres_connection_utilization": 0.05}},
  "product_value": {"source": "praxys_database", "window": "rolling_1d_7d_30d", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"registered_users": 12, "dau": 4, "wau": 9, "mau": 11, "directional": true}},
  "agent_learning": {"source": "praxys_database", "window": "24h", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"decisions_total": 5, "outcomes_total": 9, "shadow_decisions": 1, "agent_ready_candidates": 3, "agent_ready_applied": 2, "human_overrides": 1, "merged_pull_requests": 2, "active_eval": {"evaluated": 2, "true_positives": 1, "true_negatives": 0, "false_positives": 0, "false_negatives": 1, "accuracy": 0.5}, "challenger_eval": {"evaluated": 2, "true_positives": 2, "true_negatives": 0, "false_positives": 0, "false_negatives": 0, "accuracy": 1.0}, "active_semantic_eval": {"evaluated": 2, "true_positives": 1, "true_negatives": 0, "false_positives": 0, "false_negatives": 1, "accuracy": 0.5}, "challenger_semantic_eval": {"evaluated": 2, "true_positives": 2, "true_negatives": 0, "false_positives": 0, "false_negatives": 0, "accuracy": 1.0}, "decision_policy_version": "agent-ready-v2", "review_policy_version": "selective-review-v2", "promoted_classes": [], "autonomy_level": "draft_with_review"}},
  "service_telemetry": {"source": "azure_monitor", "window": "24h", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"requests": 100, "failed_requests": 4, "server_errors": 2, "failed_request_rate": 0.04, "server_error_rate": 0.02, "p95_request_ms": 480.0, "availability_checks": 24, "failed_availability_checks": 1, "availability_rate": 0.9583, "p95_availability_ms": 210.0, "database_health_failures": 0}},
  "product_telemetry": {"source": "azure_monitor", "window": "28d", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"surfaces": [{"surface": "web", "app_users": 10, "today_users": 8, "today_reach_rate": 0.8, "decision_prompts": 6, "decision_responses": 4, "decision_response_rate": 0.6667, "reported_value_rate": 0.75, "repeated_users": 5, "repeated_rate": 0.625}], "coach": [{"insight_type": "daily_brief", "useful_votes": 7, "total_votes": 9, "useful_rate": 0.7778}]}},
  "azure_alerts": {"source": "azure_monitor", "window": "24h", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"total": 1, "firing": 0, "resolved": 1, "severity": {"sev0": 0, "sev1": 1, "sev2": 0, "sev3": 0, "sev4": 0}, "states": {"new": 1, "acknowledged": 0, "closed": 0}, "rules": [{"rule": "wt-praxys-api-health", "severity": "Sev1", "firing": 0, "resolved": 1, "last_changed_at": "..."}]}},
  "platform_health": {"source": "azure_monitor", "window": "24h", "freshness": "fresh", "as_of": "...", "reason": null, "data": {"sync": [{"platform": "garmin", "attempts": 6, "successes": 6, "failures": 0, "failure_rate": 0.0}], "systemic_affected_users": 0, "systemic_failures": [], "connections": []}},
  "links": {"users": "/admin/users", "feedback": "/admin/feedback", "incidents": "/admin/incidents", "communications": "/admin/communications", "public_status": "/status", "monitoring_docs": "...", "azure_alerts": "...", "azure_logs": "...", "telemetry_trust_issue": "..."}
}
```

`telemetry_trust_issue` is a temporary compatibility field for older frontend
bundles during backend-first rolling deployments.

### GET /api/admin/feedback

List feedback rows, optionally filtered by `status`. Each row includes the
admin-only raw message, scrubbed publication fields, linked GitHub issue, and a
privacy-safe `agent_readiness` object:

```json
{
  "decision_id": "uuid",
  "policy_name": "change.agent_ready",
  "policy_version": "agent-ready-v2",
  "prompt_version": "v1",
  "prompt_hash": "02885290c95ddf28",
  "model": "gpt-5.4",
  "mode": "active",
  "kind": "bug",
  "agent_eligible": false,
  "candidate": false,
  "applied": false,
  "reason": "not_actionable",
  "challenger": {
    "prompt_version": "v2",
    "available": true,
    "candidate": true,
    "reason": "eligible"
  },
  "adjudication": {
    "expected": true,
    "reason": "bounded_actionable_defect",
    "label_sync": "synced",
    "observed_at": "..."
  }
}
```

Priority is returned separately on the feedback row and is never an
agent-readiness input.

### PUT /api/admin/feedback/{id}/agent-ready-adjudication

Append maintainer ground truth for the latest decision and synchronize the
linked issue's `agent-ready` label when possible.

```json
{
  "decision_id": "the decision_id returned by GET /api/admin/feedback",
  "expected": true,
  "reason": "bounded_actionable_defect"
}
```

The decision ID is an optimistic-concurrency token: if retriage produced a
newer decision after the admin loaded the row, the endpoint returns `409` and
the admin must refresh before judging it.

Positive judgments require `bounded_actionable_defect`. Negative reasons are
`not_a_defect`, `insufficient_detail`, `needs_product_judgment`,
`sensitivity_or_privacy`, or `other`. The response includes `label_sync`:
`synced`, `failed`, `github_unavailable`, `not_linked`, `issue_not_open`, or
`repository_mismatch`.
The adjudication is persisted even when label synchronization fails.

### POST /api/admin/feedback/sync

Reconcile linked issue state, externally added `agent-ready`, and closing-PR
outcomes. Reads structured GitHub state only; it does not fetch issue or PR
text, and skips any stored issue URL that does not match the configured repo.
The response's `repository_mismatches` count makes those skipped rows visible.

### GET /api/admin/users

List all registered users.

**Response:**
```json
{
  "users": [
    {
      "id": "uuid-string",
      "email": "user@example.com",
      "is_active": true,
      "is_superuser": true,
      "created_at": "2026-04-01T12:00:00"
    }
  ]
}
```

### DELETE /api/admin/users/{id}

Delete a user and cascade-delete all their data (activities, splits, recovery, fitness, plans, connections, config). Cannot delete yourself.

**Response:**
```json
{ "status": "deleted", "email": "user@example.com" }
```

### PATCH /api/admin/users/{id}/role

Toggle admin role for a user. Cannot change your own role.

**Request body:**
```json
{ "is_superuser": true }
```

**Response:**
```json
{
  "id": "uuid-string",
  "email": "user@example.com",
  "is_superuser": true
}
```

### POST /api/admin/invitations

Generate a one-time invitation code (format: `TS-XXXX-XXXX`).

**Request body (optional):**
```json
{ "note": "For teammate Alice" }
```

**Response:**
```json
{ "code": "TS-A1B2-C3D4", "note": "For teammate Alice" }
```

### GET /api/admin/invitations

List all invitation codes with usage status.

**Response:**
```json
{
  "invitations": [
    {
      "id": 1,
      "code": "TS-A1B2-C3D4",
      "note": "For teammate Alice",
      "is_active": true,
      "created_at": "2026-04-01T12:00:00",
      "used_by": null,
      "used_at": null
    }
  ]
}
```

### DELETE /api/admin/invitations/{id}

Revoke an invitation code (cannot be used after this).

**Response:**
```json
{ "status": "revoked", "code": "TS-A1B2-C3D4" }
```

### POST /api/admin/demo-accounts

Create a read-only demo account that mirrors the creating admin's data. Demo users can browse all pages but cannot modify anything (403 on all write endpoints).

**Request:**
```json
{ "email": "demo@example.com", "password": "demo-pass" }
```

**Response:**
```json
{
  "id": "uuid",
  "email": "demo@example.com",
  "is_demo": true,
  "demo_of": "admin-user-id"
}
```

### GET /api/admin/config

Registration gate, seat cap, activity gauge, and email availability.

**Response:**
```json
{
  "registration": {
    "registration_open": true, "flag_enabled": true, "max_users": 100,
    "registered_users": 12, "outstanding_invitations": 3,
    "committed_seats": 15, "remaining": 85, "cap_reached": false
  },
  "activity": { "dau": 4, "wau": 9, "mau": 11, "total_users": 12 },
  "email_configured": true
}
```

### PATCH /api/admin/config

Toggle self-registration and/or set the seat cap. Both fields optional.

**Request:** `{ "registration_open": true, "registration_max_users": 100 }`

**Response:** same shape as `GET /api/admin/config`. `400` if `registration_max_users < 0`.

The **seat cap counts committed seats** = registered non-demo users **plus** outstanding
(active, unused, unexpired) invitation codes. Self-registration auto-closes when committed ≥ cap;
admin-issued invitations bypass it.

### GET /api/admin/waitlist

List waitlist signups (newest first), each with any issued invitation code.

**Response:**
```json
{
  "signups": [
    {
      "id": 1, "email": "lead@example.com", "note": "sub-3 marathon",
      "locale": "zh", "created_at": "2026-07-01T10:00:00+00:00",
      "invited_at": null, "invitation_id": null, "invitation_code": null
    }
  ]
}
```

### GET /api/admin/announcements

Return all system announcements, including inactive rows, for the communications
management route. Regular authenticated users continue to receive active rows only
from `GET /api/announcements`.

### POST /api/admin/waitlist/{id}/invite

Generate a 14-day invitation code for a waitlist signup, mark the row, and email the code + a
prefilled register link (when SMTP is configured). Re-inviting revokes the prior unused code.

**Response:**
```json
{
  "sent": true, "email_configured": true, "code": "TS-A1B2-C3D4",
  "email": "lead@example.com",
  "invite_url": "https://praxys.run/login?invite=TS-A1B2-C3D4",
  "expires_at": "2026-07-18T10:00:00+00:00"
}
```

## Today

### GET /api/today

Deterministic same-day training signal. `signal` is the sole authority for the
recommendation, reason, and alternatives; Today does not load or generate an
LLM `daily_brief`.

Recovery classification is HRV-based. The current HRV observation is excluded
from its own historical baseline; the default method requires seven preceding
valid observations. `rolling_days` and `baseline_days` are retained configuration
names, but they count valid observations rather than calendar days. Identical
historical observations have zero variance and therefore return
`classification_reason = "zero_variance"` instead of a normal classification.
An HRV reading from today or yesterday is current. Older HRV
is retained for provenance but sets `hrv_is_stale = true`, returns
`recovery_analysis.status = "insufficient_data"`, and cannot adjust the same-day
signal. Sleep, readiness, and resting heart rate remain available as separate
informational context when the source provides them. Recovery and plan frames use
one configured provider at a time rather than blending overlapping sources.

**Response:**
```json
{
  "as_of_date": "2026-04-08",
  "data_as_of": "2026-04-07T12:00:00Z",
  "coach_snapshot": "8f2c90a4d43818aaaf943b0f1a27c997",
  "signal": {
    "recommendation": "follow_plan|unscheduled|modify|reduce_intensity|easy|rest",
    "reason": "English fallback string",
    "reason_code": "stable_semantic_code",
    "reason_args": { "tsb": -18.2 },
    "alternatives": ["English fallback string"],
    "alternative_codes": [{ "code": "stable_semantic_code", "args": {} }],
    "recovery": { "tsb": 0.6, "hrv_ms": 59.0, "sleep_score": 82.0, "readiness": 76.0 },
    "plan": { "workout_type": "easy", "duration_min": "60", "..." : "..." }
  },
  "recovery_analysis": {
    "status": "fresh|normal|fatigued|insufficient_data",
    "hrv": { "today_ms": 59.0, "baseline_mean_ln": 3.87, "trend": "improving" },
    "sleep_score": 82.0,
    "readiness_score": 76.0,
    "resting_hr": 49.5,
    "rhr_trend": "low|stable|elevated",
    "latest_date": "2026-04-07",
    "is_stale": false,
    "hrv_latest_date": "2026-04-07",
    "hrv_is_stale": false,
    "classification_reason": "missing_hrv|insufficient_history|zero_variance|stale_hrv|null"
  },
  "last_activity": {
    "date": "2026-04-07",
    "activity_type": "running",
    "distance_km": 9.43,
    "duration_sec": 3233,
    "avg_power": 210.0,
    "avg_pace_min_km": "5:42",
    "rss": 64.8
  },
  "tsb_sparkline": { "dates": ["..."], "values": ["..."], "projected_dates": ["..."], "projected_values": ["..."] },
  "recovery_theory": { "id": "hrv_based", "name": "HRV-Based Recovery", "simple_description": "...", "params": {} },
  "upcoming": [
    { "date": "2026-04-11", "workout_type": "threshold", "duration_min": 65, "description": "..." }
  ],
  "week_load": { "week_label": "W15", "actual": 245.3, "planned": 280.0 },
  "heat_adaptation": {
    "stage": "insufficient_evidence|building|likely_adapted|maintaining|decaying",
    "confidence": "low|moderate|high",
    "confidence_basis": "data_coverage",
    "model_version": "heat-adaptation-v8",
    "next_action": "continue_normal_training",
    "today_restricted": false,
    "recent_conditions": {
      "qualifying_session_count": 2,
      "temperature_c": { "min": 29.0, "max": 33.0 },
      "relative_humidity_pct": { "min": 54.0, "max": 68.0 }
    },
    "cadence": [{ "date": "2026-04-08", "session_count": 1, "counted_session_count": 1, "effective_heat_minutes": 42 }],
    "sessions": []
  },
  "warnings": ["HRV rolling mean declining"],
  "training_base": "power",
  "display": { "threshold_abbrev": "CP", "threshold_unit": "W", "load_label": "RSS" }
}
```

`reason` and `alternatives` are deterministic English fallbacks. Clients should
localize the stable `reason_code` / `alternative_codes` and interpolate their
argument maps without changing the recommendation. `week_load` is `null` when no
current-week activity or plan load exists; `recovery_analysis`, `last_activity`,
and `recovery_theory` are also nullable. `signal.recovery.tsb` is `null` until the
account has one active CTL time constant of history. A null TSB is excluded from
same-day decisions and clients render it as unavailable rather than as a balanced
value of zero. The one-time-constant history gate and displayed TSB labels are
Praxys product estimates, not validated physiological cutoffs.

`heat_adaptation` is a qualitative evidence tracker. It prefers
timestamp-weighted sample power when it covers at least 90% of activity duration
and otherwise falls back to activity splits; sample gaps over five seconds do
not count toward coverage, and activity `avg_power` is never used for exposure
workload. The selected sample/split provider must be known and match
`cp_power_provider` because Garmin and Stryd running-power scales are not
interchangeable. For `cp_source: "activities"`, `cp_power_provider` is the
provider persisted with a provider-specific, running-only activity CP fit. The
fit uses the configured primary activity provider when present; otherwise it is
created only when the eligible activity set has one unambiguous provider.
Matching split provenance is required and cycling is excluded. Sessions expose
`power_provider`, `cp_source`, `cp_power_provider`, `power_source_alignment`,
`sample_coverage_ratio`, and `workload_evaluable` so clients can distinguish a
provider mismatch, unverified provenance, incomplete samples, and work that was
genuinely below threshold.

`recent_conditions` summarizes only qualifying sessions inside the active
14-day window. It is `null` when no current qualifying session exists, and
excluded or older observations cannot widen its temperature or humidity
range. It describes the recent training conditions represented by the model;
it is not a target climate and does not assess current weather. For
`maintaining` and `decaying`, the stage can come from an older qualifying
block, so `recent_conditions` must not be presented as that historical
block's condition range.

Environmental context is one provenance-tagged outdoor activity-summary
temperature/RH pair; treadmill and indoor summary weather are discarded.
Evidence uses the stronger of a Stull psychrometric wet-bulb ramp and a dry-bulb
ramp; the ramps are never added, and the result is not WBGT. The Stull proxy
assumes standard sea-level pressure and is returned as `null` outside its 5-99%
RH domain; the independent dry-bulb ramp can still contribute. Wind, solar
radiation, within-session weather, clothing, hydration state, and measured core
or skin temperature are excluded. The 18-26 C wet-bulb ramp, 30-40 C dry-bulb
ramp, max combination, 50% CP workload floor, five-second sample-interval gate,
90% sample-coverage gate, 30-effective-minute session gate, 14-day active
window, general 2-day/60-minute Building threshold, resumed-exposure
Reacclimating label, 7-day/420-minute Likely adapted threshold,
effective-minute weighting, retention through day 7, and decay after day 7
through day 28 are Praxys operational estimates, not validated physiological
cutoffs or a dose model.
Confidence describes evaluable data coverage, not the probability of individual
physiological adaptation. The status is not medical clearance or a current
heat-risk assessment, and restrictive `signal` recommendations replace its
normal-training action with `follow_today_signal`.

`coach_snapshot` is an opaque cache/source version retained for response
compatibility. It is not an insight identifier and clients should not use it to
request same-day prose.

## Training

### GET /api/training

Training analysis and diagnosis.

**Response:**
```json
{
  "diagnosis": {
    "lookback_weeks": 6,
    "volume": {
      "weekly_avg_km": 51.6,
      "trend": "stable",
      "weeks": ["2026-04-20", "2026-04-27", "2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25"],
      "weekly_km": [48.3, 52.1, 54.5, 49.2, 52.8, 52.7]
    },
    "consistency": { "total_sessions": 18, "weeks_with_gaps": 1, "longest_gap_days": 4 },
    "interval_power": {
      "max": 292,
      "avg_work": 237,
      "supra_cp_sessions": 6,
      "total_quality_sessions": 12,
      "data_available": true,
      "evidence_complete": true,
      "activities_with_intensity_data": 18,
      "activities_expected": 18
    },
    "distribution": [
      { "name": "Easy", "actual_pct": 72, "target_pct": 80 },
      { "name": "Threshold", "actual_pct": 15, "target_pct": 8 }
    ],
    "zone_ranges": [{ "name": "Easy", "lower": 0, "upper": 136, "unit": "W" }],
    "data_meta": { "distribution_resolution": "samples|splits|mixed|activity_averages|unavailable" },
    "diagnosis": [{ "type": "positive|warning|neutral", "message": "string" }],
    "suggestions": ["string"]
  },
  "fitness_fatigue": {
    "dates": ["2026-02-10", "..."],
    "ctl": [45.2, "..."],
    "atl": [52.1, "..."],
    "tsb": [-6.9, "..."],
    "projected_dates": ["..."],
    "projected_ctl": ["..."],
    "projected_tsb": ["..."]
  },
  "cp_trend": { "dates": ["..."], "values": ["..."] },
  "weekly_review": {
    "weeks": ["W10", "..."],
    "actual_load": ["..."],
    "planned_load": ["..."],
    "actual_estimated": false,
    "planned_estimated": false,
    "week_actual_estimated": [false, false],
    "week_planned_estimated": [false, true],
    "week_complete": [true, false]
  },
  "summary": {
    "current_tsb": -6.9,
    "distribution_match_pct": 83,
    "load_compliance_pct": 96
  },
  "heat_adaptation": {
    "stage": "likely_adapted",
    "confidence": "high",
    "confidence_basis": "data_coverage",
    "model_version": "heat-adaptation-v8",
    "exposure_days": 7,
    "effective_heat_minutes": 420,
    "recent_conditions": {
      "qualifying_session_count": 7,
      "temperature_c": { "min": 29.0, "max": 33.0 },
      "relative_humidity_pct": { "min": 54.0, "max": 68.0 }
    },
    "cadence": [{ "date": "2026-04-08", "session_count": 1, "counted_session_count": 1, "effective_heat_minutes": 42 }],
    "sessions": ["..."]
  },
  "workout_flags": [{ "date": "...", "flag": "good|bad", "reason": "..." }],
  "sleep_perf": {
    "pairs": [[85, 240.3], ["..."]],
    "metric_label": "Avg Power",
    "metric_unit": "W"
  },
  "training_base": "power",
  "display": { "..." : "..." },
  "data_meta": {
    "activity_count": 18,
    "data_days": 35,
    "cp_points": 4,
    "has_recovery": true,
    "load_time_constant_days": 42,
    "pmc_sufficient": false,
    "cp_trend_sufficient": true
  }
}
```

`summary` contains server-computed display metrics so web, miniapp, and legacy
dashboard consumers do not duplicate training formulas. `current_tsb` is `null`
until the account has one active CTL time constant of history.
`distribution_match_pct` is `null` unless every recent activity has at least 90%
duration coverage from split or timestamped sample intensity and every zone has
a target. Timestamped samples also require a median cadence of five seconds or
less. `load_compliance_pct` uses only completed weeks where both actual and
planned load have exact selected-base inputs and the plan target is positive.
It is `null` until at least two such weeks exist. A week is complete only after
Sunday has passed and daily load contains all seven Monday-through-Sunday dates.
`diagnosis.volume.weeks` is oldest-first and always aligns positionally with
`weekly_km`. Both arrays are empty when no recent distance history is available;
a non-empty all-zero series is valid recorded data and yields `weekly_avg_km: 0`.
Trend labels use a Praxys estimate that requires the newer half to differ from
the older half by more than 10%.
The result is a descriptive mean actual-to-planned load ratio, not a quality,
safety, recovery, or readiness score. `week_actual_estimated` and
`week_planned_estimated` provide the per-week provenance; estimated bars remain
visible but are excluded from the summary. Durationless `rest` and `off` plan
rows are exact zero load; other durationless rows remain estimated.
`load_time_constant_days` comes from the active load theory and controls
`pmc_sufficient`. Both the one-time-constant sufficiency gate and the two-week
minimum are Praxys product estimates rather than validated physiological cutoffs.

`heat_adaptation` has the same evidence and safety contract as the Today field,
but Training is the client surface for the longitudinal experience.
`recent_conditions` describes the current qualifying temperature and humidity
range. For Building and Likely adapted, it supplies the conditions behind the
current evidence. Maintaining and Decaying can inherit from an older block, so
clients explicitly separate that retained/fading stage from the current range.
`cadence` is the complete server-computed daily aggregate for the active
window; `sessions` remains a bounded latest-evidence ledger for progressive
disclosure. Clients keep the cadence, effective-minute mechanics, and
inclusion reasons behind an optional evidence disclosure.

When valid split-level intensity evidence is absent, `max`, `avg_work`,
`supra_cp_sessions`, and `total_quality_sessions` are `null`, and
`evidence_complete` is `false`. HR- and pace-based accounts may receive a coarse
`activity_averages` distribution for display, but it never qualifies for
`distribution_match_pct`. When no usable intensity exists, the distribution keeps
its stable array shape with zero placeholders and `distribution_resolution` is
`unavailable`; clients must not interpret those zeros as completed recovery-zone
time or zero quality work.

## Goal

### GET /api/goal

Race prediction and goal tracking.

**Response:**
```json
{
  "race_countdown": {
    "distance": "marathon",
    "distance_label": "Marathon",
    "mode": "race_date|cp_milestone|continuous|none",
    "current_cp": 247.8,
    "target_cp": 280.0,
    "predicted_time_sec": 13852,
    "target_time_sec": 10800,
    "cp_gap_watts": 70.0,
    "status": "on_track|close|behind|unlikely",
    "prediction_method": "critical_power|riegel|none",
    "prediction_theory": "Critical Power (Stryd Race Power)",
    "milestones": [{ "cp": 270, "marathon": "~3:50", "reached": false }],
    "reality_check": { "assessment": "...", "severity": "..." }
  },
  "cp_trend": { "dates": ["..."], "values": ["..."] },
  "cp_trend_data": { "direction": "improving|stable|falling", "slope_per_month": -3.9 },
  "latest_cp": 247.8,
  "training_base": "power",
  "display": { "..." : "..." }
}
```

> **Units.** `latest_cp`, `current_cp`, `target_cp`, `cp_trend.values` are in the user's
> base-native threshold unit (watts for power, bpm for HR, sec/km for pace).
> Pair with `display.threshold_unit` to format. `actual_load` / `planned_load`
> similarly carry RSS / TRIMP / rTSS depending on the training base; pair with
> `display.load_label`.

## History

### GET /api/history

Paginated activity history.

**Query params:**
- `limit` (int, 1-100, default 20)
- `offset` (int, default 0)
- `source` (optional provider name used as the duplicate-selection pivot)

**Response:**
```json
{
  "activities": [
    {
      "activity_id": "stryd-123",
      "date": "2026-04-07",
      "source": "stryd",
      "start_time": {
        "state": "available",
        "utc": "2026-04-07T22:14:00Z",
        "timezone": "UTC",
        "provenance": "activity_start_with_offset",
        "reason_codes": []
      },
      "distance_km": 9.43,
      "duration_sec": 3233,
      "temperature_c": 31.4,
      "relative_humidity_pct": 68.0,
      "environment_source": "stryd_activity_weather",
      "avg_power": 210.0,
      "max_power": 318.0,
      "avg_hr": 155,
      "max_hr": 172,
      "avg_pace_min_km": "5:42",
      "rss": 64.8,
      "environment": {
        "model_version": "environmental-performance-context-v2",
        "science_decision_id": "sdr-environmental-performance-v2",
        "state": "available",
        "temperature_c": 31.4,
        "relative_humidity_pct": 68.0,
        "source": "stryd_activity_weather",
        "wet_bulb_c": 26.6,
        "wet_bulb_method": "stull_psychrometric",
        "reason_codes": [],
        "science_sources": [
          {
            "id": "stull-2011",
            "url": "https://doi.org/10.1175/JAMC-D-11-0143.1"
          }
        ],
        "limitations": [
          "wind_unobserved",
          "solar_radiation_unobserved",
          "outdoor_wbgt_unavailable",
          "not_a_personal_performance_correction"
        ]
      },
      "sample_coverage": {
        "state": "available",
        "sample_count": 3234,
        "observed_duration_sec": 3233.0,
        "sample_coverage_ratio": 1.0,
        "power_coverage_ratio": 0.998,
        "heart_rate_coverage_ratio": 0.995,
        "gap_count": 0,
        "reason_codes": []
      },
      "provenance": {
        "activity_provider": "stryd",
        "sample_providers": ["stryd"],
        "power": {
          "state": "available",
          "providers": ["stryd"],
          "basis": "samples",
          "reason_codes": []
        },
        "heart_rate": {
          "state": "available",
          "providers": ["stryd"],
          "basis": "samples",
          "reason_codes": []
        }
      },
      "splits": [{
        "split_num": 1,
        "avg_power": 220,
        "duration_sec": 300,
        "power_source": "stryd"
      }]
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0,
  "source_filter": "stryd",
  "training_base": "power",
  "display": { "..." : "..." }
}
```

`start_time.utc` is emitted only when the stored value carries an offset/epoch
or timestamped activity samples provide an epoch fallback. A naive connector
timestamp is never silently relabeled as UTC. Missing time, weather, provider,
or stream inputs use `state` plus stable `reason_codes` rather than
success-shaped defaults.

Environmental context follows `sdr-environmental-performance-v2`. It accepts
only plausible values from dedicated connector weather provenance (air
temperature -20 to 50 C and relative humidity 0-100%). Synthesized activity
summary or arbitrary imported source labels remain unavailable and their
numeric values are withheld. The optional Stull result is a psychrometric
wet-bulb proxy under a standard sea-level-pressure assumption, never outdoor
WBGT. Wind and solar radiation are unobserved, and the context is not a safety
boundary, forecast, personal pace correction, or counterfactual performance
estimate. Dew point, vapor pressure, UI comparisons, and a separately
validated matched-sample personalization model are deferred from this first
API iteration; the user-facing comparison work remains tracked by issue #444.
`science_sources` retains the completed-activity environmental-context citation
subset governed by `sdr-environmental-performance-v2`; Labs-only personal-model
and statistical-method sources belong to the separate Labs methodology
surface. The abbreviated example above shows only the formula source.

## Activity analysis

These endpoints are owner-authenticated with the token subject itself. Unlike
dashboard read endpoints, demo accounts do not inherit another user's data.
Every query filters by `user_id`; activity IDs are not globally trusted.

### GET /api/analysis/activities/{activity_id}

Returns one owned activity, continuous stable-power segments, and predictor
context that was available before the activity.

Stable segments prefer timestamped `ActivitySample` rows. The v3 detector:

- excludes missing, zero, out-of-range power and sample gaps over 5 seconds;
- identifies regions with a trailing 60-second power CV at or below 5%;
- requires at least 180 seconds and whole-segment power CV at or below 7.5%;
- assigns each sample interval to at most one output segment, so adjacent
  stable windows cannot overlap or double-count observations;
- reports mean power, provider-aligned `%CP`, power CV, mean HR, HR slope in
  bpm/min, and first-half-normalized power/HR decoupling
  (`(EF_first - EF_second) / EF_first * 100`), with power and HR averaged over
  the identical HR-valid interval mask in each half;
- emits sample coverage, provider provenance, exclusions, parameters, and
  reason codes.

These detector thresholds are reproducible Praxys product estimates, not
physiological boundaries. HR decoupling is descriptive and does not establish
causality among heat, fatigue, hydration, or recovery. When samples are absent,
qualifying splits are returned with `status: "limited"` and
`stability_state: "not_evaluable"`; CV, HR slope, decoupling, and sample
coverage remain `null`.

Sample `source` is connector provenance. A platform may relay an external
sensor's power without identifying that sensor separately; Praxys therefore
fails closed on `%CP` when sample/split power cannot be aligned with the dated
CP provider.

Pre-activity context is causal by construction:

- CTL/ATL/TSB uses stored prior-activity load scores through the previous
  calendar day. Activities without the base-specific stored load or
  `load_score` fallback are excluded and counted in
  `missing_load_activity_count`. CTL and ATL then represent known-load lower
  bounds, while TSB is `null` because its bias direction is indeterminate;
  the context forces `state: "partial"` with
  `activity_load_observations_missing`. Missing-load tracking covers the whole
  prior history because EWMA influence decays asymptotically rather than at a
  hard cutoff;
- CP is the latest dated value strictly before the activity date, with source
  and power-provider provenance;
- recovery applies the activity-date cutoff before provider preference or
  fallback ranking, then selects that provider's latest eligible row. Because
  recovery has a date but no observation timestamp, downstream causal research
  must treat same-day recovery as temporally ambiguous; the heat-response
  validation accepts readiness only from a strictly earlier date within its
  configurable maximum lag (previous calendar day by default);
- heat-adaptation evidence ends on the previous calendar day.

Historical user-config revisions are not stored. Retrospective exports apply
the currently selected training base and provider preferences to dated,
previously stored observations, and record those choices in the payload/hash.

The response records `schema_version`, model versions (including
`environmental-performance-context-v2`), detector parameters, and a canonical
`record_hash`. It never includes credentials, precise GPS, or raw sample rows.

### GET /api/analysis/research-dataset

Builds the same record shape across a bounded history page.

**Query params:**
- `limit` (int, 1-50, default 20)
- `offset` (int, default 0)
- `source` (optional activity duplicate-selection pivot)

The response includes `activity-research-dataset-v1`, model versions,
pagination metadata, explicit cutoff semantics, privacy declarations, an opaque
owner-bound `export_snapshot_id`, and a SHA-256 `dataset_hash`. The snapshot ID
is derived from the analysis endpoint's existing per-user revision scopes plus
the response/model version. It is identical across `limit`/`offset` pages for
one revision and changes when relevant activity, split, sample, recovery,
fitness, or config state changes. It does not expose the user ID or revision
counters.

`export_snapshot_id` is part of the canonical dataset core covered by each
page's `dataset_hash`. `generated_at` remains excluded from the hash, so
unchanged inputs and model versions produce the same dataset hash. Records are
ordered by date descending with `activity_id` and source tie-breakers; split
arrays are ordered by split number and their serialized metric values. The
route ETag remains page-specific because its variant salt includes the request
pagination/filter parameters.

The route fences each page construction with the same page-independent
snapshot token before and immediately after all payload reads. If a relevant
write commits during construction, the page is discarded and the API returns
`409` with:

```json
{"detail":"ANALYSIS_EXPORT_SNAPSHOT_CHANGED_RESTART_EXPORT"}
```

That conflict response contains no research page or dataset hash. Exporters
must discard every page already collected and restart **all pages** from
offset zero; retrying only the failed page could still combine revisions.

Production research exports must fetch the complete bounded history, not only
the first page. Use `limit=50`, request offsets `0, 50, 100, ...`, keep the
same optional `source` value on every request, and stop when the next offset is
greater than or equal to the first page's `total`. Thus `total=182` requires
offsets `0`, `50`, `100`, and `150`, with 32 records on the last page. Save
each response as a separate private JSON file, outside the repository, and
never commit raw exports. Every page must have the exact same non-empty
`export_snapshot_id`; if it changes during collection, discard the pages and
restart the export from offset zero.

Pass every page to the offline CLI in offset order:

```powershell
python scripts\validate_heat_response.py `
  --input page-0000.json `
  --input page-0050.json `
  --input page-0100.json `
  --input page-0150.json `
  --format markdown
```

Repeated `--input` values create an
`activity-research-dataset-bundle-v1` only in memory. One prebuilt local bundle
is also accepted, but repeated inputs are preferred so no combined private raw
file is created. The validator verifies each page's API `dataset_hash`, checks
the shared snapshot/total/limit/filter/model/semantics/privacy contracts,
requires contiguous non-overlapping offsets and exact full coverage, and
rejects cross-page canonical activity duplicates. Missing or mismatched
snapshot IDs are rejected even when each page hash is otherwise valid. A single
page, including a legitimate empty export, must also carry a non-empty snapshot
ID. A single page remains complete only when `offset=0` and `total <= limit`; a
first page with `total > limit` cannot pass the decision-required
complete-export gate.

The private export can be evaluated locally with the research-only
[heat-response validation pipeline](heat-response-validation.md). That
pipeline does not add a personal estimate to this endpoint and does not alter
the accepted environmental-performance SDR.

## Labs environmental response

All endpoints are owner-authenticated. Demo accounts may read their state but
cannot enroll, recompute, or withdraw.

### GET /api/labs/environment-response

Returns the current consent version, enrollment and processing state,
privacy-safe availability reason, and any aggregate result. A result contains
only eligibility counts, five aggregate curve points, aggregate coefficient
uncertainty, gate statuses, model/source versions, power regime, prediction
diagnostic status, and timestamps. It never contains activity IDs, dates,
routes, GPS, sample rows, or per-activity values.

`result.eligibility_counts.workload_support` separates the personal display
rule from the common fitted-data domain. It reports the training-partition
median `%CP`, the median-centered personal display range, the common 65–95% CP
model-eligible range, and
`display_filter_applied_to_model_rows: false`. This is aggregate provenance,
not cohort-study consent; pooled contribution requires a separate contract.

`execution.job_status` exposes the durable lifecycle (`queued`, `dispatched`,
`processing`, `retrying`, or a terminal state), attempt count, retryability,
and request/dispatch timestamps. `execution.recompute` is the
server-authoritative cooldown/daily-limit policy used by both clients.
All absolute timestamps include a UTC offset.

### GET /api/labs/environment-response/preflight

Returns a non-persisted, aggregate-only prerequisite estimate before consent or
recomputation. `status` is `likely_eligible`, `ineligible`, or
`needs_full_analysis`; `can_start_analysis` is false only for a definite
blocker such as too few candidate activities, missing temperature/humidity,
missing continuous power/heart-rate samples, an unsupported power provider, or
missing provider-aligned Critical Power. Passing preflight never promises a
curve: stable-segment extraction, environmental support, chronological
holdout, bootstrap stability, and all other scientific release gates remain
part of the full analysis.

The sample prerequisite is intentionally only a necessary lower bound: an
activity must contain one continuous minimum-segment-duration power block using
the same bounded sample-gap rule as the full analysis, plus at least 80%
heart-rate observation coverage. It does not claim that the power block is
stable or that the heart-rate samples overlap the eventual selected segment.
Provider-aligned Critical Power counts only for activities occurring after a
positive dated Stryd CP estimate.

Enrollment and recomputation repeat this check server-side. A newly ineligible
request returns `409` with code `LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE` and the
same aggregate preflight payload, without changing consent or deleting an
existing result.

### POST /api/labs/environment-response/wet-bulb

Calculates the non-persisted Stull psychrometric wet-bulb proxy used by the
Labs calculator. The authenticated request accepts `temperature_c` and
`relative_humidity_pct`. The response returns the estimate, method identifier,
source URL, and whether the inputs are inside Praxys's conservative method
domain. A `null` estimate means the input combination is outside that domain.
This endpoint does not store its inputs or result, and the value is not WBGT,
apparent temperature, body temperature, or a heat-safety assessment.

### POST /api/labs/environment-response

Records explicit V1 consent and durably queues private processing.

```json
{
  "adult_attested": true,
  "consent_version": "environment-response-consent-v1"
}
```

The adult attestation is required because the reviewed evidence is adult-only;
no date of birth is collected. A stale consent version returns `409`. The
`202` response is the current durable state. Clients should send an
`Idempotency-Key` header (8-128 URL-safe identifier characters); replaying the
same key returns the original enrollment generation without repeating the
eligibility check. Repeating enrollment under unchanged active consent does
not enqueue another analysis. A superseded stored consent remains hidden until
the user explicitly accepts the current version.

The PostgreSQL outbox and Service Bus message contain only an opaque job UUID.
Owner ID, source revision, model version, and consent state remain in
PostgreSQL. Raw research pages are assembled in isolated worker memory and are
never persisted or returned. A periodic reconciler recovers expired execution
leases and republishes only the oldest globally runnable dispatch after its
30-minute worker-start lease, preventing a queue backlog from multiplying
messages.

### POST /api/labs/environment-response/recompute

Deletes the prior aggregate result and queues a fresh computation under the
existing current consent. Clients should send a mutation-specific
`Idempotency-Key`; a replay returns the original generation. PostgreSQL
enforces one active generation per user and experiment.

Manual recompute has a six-hour cooldown and accepts at most three requests in
any rolling 24-hour window. A blocked request returns `429`,
`Retry-After`, and structured detail containing
`LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN` or
`LABS_ENVIRONMENT_RECOMPUTE_DAILY_LIMIT`, the true later
`available_at` instant, and `retry_after_seconds`. When the user does not hold
current consent, returns `409` with structured detail code
`LABS_ENVIRONMENT_NOT_ENROLLED`; clients should invalidate both Labs state and
preflight state before offering the next action.

### DELETE /api/labs/environment-response

First records a restore-safe private withdrawal marker, then immediately
deletes active consent and aggregate results. A running computation rechecks
consent before writing, and active job/outbox records are cancelled, so
withdrawal cannot be followed by a late result publication. Replaying an old
enrollment idempotency key cannot recreate withdrawn consent. Returns `204`;
if the private marker cannot be stored, returns `503` without deleting consent
so the user can retry safely.

### GET /api/ai/context

Returns the structured dashboard summary used for AI plan generation. The
plugin MCP tool `get_training_context` is the remote/local wrapper over this
endpoint. It remains a coaching snapshot (recent sessions, current fitness,
recovery, and plan), not the analysis-ready research export above. The first
iteration deliberately keeps per-activity segment research behind the
owner-authenticated analysis API rather than adding an unbounded MCP sample
tool.

## Plan

### GET /api/plan

The user's plan within a window, plus stable per-workout execution-target
reconciliation.
`reconciliation` is authoritative and joins by durable canonical identity,
provider external ID, and normalized provider-content fingerprint. It never
collapses workouts by date, so manual or coach-authored workouts can coexist
with one or more Praxys workouts on the same day.

`sync_state` remains as a backward-compatible summary. `stryd_status` keeps the
legacy date-keyed pushed-workout shape; it includes outbound Praxys deliveries,
not target workouts accepted into the canonical plan.

**Query params:**
- `start` *(YYYY-MM-DD, default = today)* — window start.
- `end` *(YYYY-MM-DD, default = `start + 14 days`)* — window end. Inverted
  or longer-than-365-day windows return 400.

**Response:**
```json
{
  "workouts": [
    {
      "canonical_id": "f0219570-4bda-49df-86a7-1b73ad80af6c",
      "workout_version": "d8d5c9...64-hex-characters",
      "editable": true,
      "external_overlap": false,
      "date": "2026-04-11",
      "source": "ai",
      "owner": "praxys",
      "origin": "generated",
      "workout_type": "threshold",
      "duration_min": 65,
      "distance_km": 11.0,
      "power_min": 235,
      "power_max": 255,
      "hr_min": 158,
      "hr_max": 172,
      "pace_min": "04:00",
      "pace_max": "04:20",
      "description": "WU 10min, 2x20min @235-255W...",
      "sync_state": "mismatch",
      "reconciliation": {
        "id": "delivery:311ef6f2-c119-4bfd-a0e7-b697403bcb21@0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "state": "target_edited",
        "conflict": true,
        "target": "stryd",
        "external_id": "stryd_123",
        "match_basis": "external_id",
        "reason": "content_changed",
        "resolutions": ["restore_praxys", "accept_target"],
        "target_workout": {
          "date": "2026-04-11",
          "workout_type": "threshold",
          "planned_duration_min": 60,
          "workout_description": "Edited on Stryd"
        }
      }
    }
  ],
  "stryd_status": {
    "2026-04-11": { "workout_id": "stryd_123", "pushed_at": "...", "status": "pushed" }
  },
  "sync_target": "stryd",
  "window": { "start": "2026-04-11", "end": "2026-04-25" },
  "management": {
    "mutation_api_version": 1,
    "can_write": true,
    "minimum_date": "2026-04-11",
    "external_overlap_dates": []
  },
  "adjustments": [
    {
      "id": "7aa4d296-7022-41f9-8c53-3fd97d9e9895",
      "created_at": "2026-04-11T06:15:00Z",
      "status": "active",
      "can_undo": true,
      "workout_date": "2026-04-11",
      "before": { "canonical_id": "f0219570-4bda-49df-86a7-1b73ad80af6c", "workout_type": "threshold" },
      "after": { "canonical_id": "f0219570-4bda-49df-86a7-1b73ad80af6c", "workout_type": "rest" },
      "rule": {
        "id": "hrv_below_hard_to_rest",
        "version": "1",
        "classification": "product_estimate"
      },
      "reason_code": "hrv_below_hard",
      "evidence": { "hrv_latest_date": "2026-04-11" },
      "delivery": { "status": "complete" }
    }
  ]
}
```

`owner` is authoritative: `"praxys"` identifies a canonical workout managed by
Praxys, while `"external"` identifies a provider- or coach-owned workout.
`origin` is one of `generated`, `accepted_target`, `manual`, `imported`, or
`legacy` and describes how the current content entered that owner lane.
`source` is a deprecated `"ai" | "stryd" | "garmin"` compatibility field retained for
cached clients; new clients must not infer ownership or authorship from it.
Future Praxys rows also expose `workout_version`, the immutable content hash
required by canonical-ID update and delete requests, and `editable=true`.
External rows and past Praxys rows always return `editable=false`.
`management.mutation_api_version=1` advertises the canonical workout CRUD
contract; older APIs omit the object so clients can hide write controls during
rolling deployment. `management.can_write=false` makes the whole surface
read-only (including demo viewers whose reads resolve to a source account).
Authoring controls depend on that write capability and per-row editability;
execution-target connectivity gates delivery actions, not local plan editing.
`external_overlap=true` and `management.external_overlap_dates` identify only
dates containing both Praxys-owned and external workouts; generic delivery or
reconciliation failures do not imply a planner overlap. Before the first
authoritative calendar snapshot, the compatibility fallback suppresses target
rows already bound to a Praxys delivery and surfaces any remaining same-date
target rows as external.

The response ETag is salted by the athlete's current date, viewer write
capability, and requested window. The current date uses the persisted athlete
IANA timezone and falls back to UTC when none is valid. Revalidation therefore
cannot reuse yesterday's editability state or a writable source-account
representation for a read-only demo viewer.

Detailed reconciliation states are `matching`, `pending_observation`,
`not_delivered`, `target_only`, `target_edited`, `target_deleted`,
`canonical_changed`, and `delivery_failed`. Conflict responses advertise only
the currently safe explicit actions in `resolutions`.

The legacy `sync_state` maps matching/pending to `synced`, undelivered to
`not_synced`, and conflicts to `mismatch`.

`sync_target` is the configured and runtime-authorized execution target:
`"stryd"`, `"garmin"`, or `null`. Garmin is returned only while deployment and
rollout eligibility pass and its internal connection-generation fence matches.
Clients can hide the entire sync column when it is `null`.

`adjustments` is newest-first durable audit history filtered to the requested
workout-date window. `active` means the exact after-snapshot is still current,
`undone` means the user restored it, and `superseded` means a later edit makes
exact undo unsafe. `can_undo` is the authoritative action gate.

### Adaptive plan proposals

These authenticated endpoints provide the versioned, non-canonical proposal
boundary for starting an adaptive plan. They accept already-structured goal and
workout input only. They do **not** call an LLM, generate workouts, add new
planning claims, or change managed-delivery consent. Generation remains
unavailable until a human-accepted policy is implemented.

Proposal records are athlete-owned and immutable: editing creates a successor
proposal and marks the prior version superseded. Preview, rejection, stale
versions, expiry, validation failures, and cross-owner requests do not write
`training_plans` or provider-delivery state. Only exact-version adoption writes
Praxys-owned canonical workouts, preserving each proposal workout's
`canonical_id`, linking rows with `adaptive_plan_id`, appending a `PlanRevision`,
and triggering already-consented provider delivery after the canonical commit.

Common structured error `detail.code` values include
`PLAN_PROPOSAL_VALIDATION_FAILED`, `PLAN_PROPOSAL_UNSUPPORTED_FIELD`,
`PLAN_PROPOSAL_NOT_FOUND`, `PLAN_PROPOSAL_STALE`,
`PLAN_PROPOSAL_SUPERSEDED`, `PLAN_PROPOSAL_EXPIRED`,
`ADAPTIVE_PLAN_ACTIVE_EXISTS`, `ADAPTIVE_PLAN_VERSION_CONFLICT`, and
`PLAN_PROPOSAL_ALREADY_ADOPTED`.

Request-schema failures, including malformed proposal UUIDs and numeric bounds,
return HTTP 422 with `detail.code=PLAN_PROPOSAL_VALIDATION_FAILED` plus
privacy-minimized `errors` containing field paths and validation types.
Forbidden fields return HTTP 422
`detail.code=PLAN_PROPOSAL_UNSUPPORTED_FIELD`; rejected input values are not
reflected.

#### POST /api/plan/proposals

Create a draft proposal. The first proposal creates a new adaptive-plan
aggregate; after adoption, later drafts attach to that active aggregate when no
proposal is active. An expired replacement does not block a fresh draft. A user
may have only one `draft` or `active` adaptive plan and one active proposal at
a time.

```json
{
  "goal": {
    "goal_kind": "race",
    "target": { "distance": "10k", "target_label": "Spring 10K" },
    "horizon_start": "2026-04-11",
    "horizon_end": "2026-05-09"
  },
  "workouts": [
    {
      "date": "2026-04-12",
      "workout_type": "easy",
      "planned_duration_min": 45,
      "target_power_min": 190,
      "target_power_max": 220,
      "workout_description": "Aerobic run"
    }
  ],
  "idempotency_key": "client-generated-key",
  "origin": "api.plan.proposals",
  "policy_version": "structured-only-v1",
  "model_version": null,
  "science_version": null,
  "assumptions": [],
  "unknowns": [],
  "warnings": [],
  "alternatives": [],
  "expires_at": "2026-04-12T00:00:00"
}
```

Response includes `id`, `adaptive_plan_id`, exact `version`, `state`,
`base_plan_version`, normalized `workouts` with stable `canonical_id` values,
the aggregate `{ id, version, lifecycle, active_proposal_id }`, and the
immutable goal snapshot.

#### GET /api/plan/proposals/current

Return the authenticated athlete's active proposal and exact version, or 404
`PLAN_PROPOSAL_NOT_FOUND` when none exists.

#### POST /api/plan/proposals/{proposal_id}/edits

Create a successor proposal. The request body is the same as
`POST /api/plan/proposals` plus `expected_version`. The parent proposal must be
the active draft with that exact version; it is never modified in place.

#### POST /api/plan/proposals/{proposal_id}/reject

Reject an exact active proposal without canonical writes.

```json
{
  "expected_version": 2,
  "idempotency_key": "reject-key"
}
```

#### POST /api/plan/proposals/{proposal_id}/adopt

Atomically adopt an exact proposal version into the canonical plan lane.

```json
{
  "expected_proposal_version": 2,
  "expected_plan_version": 0,
  "idempotency_key": "adopt-key"
}
```

Adoption locks the athlete's plan-write lane, verifies ownership, state, expiry,
proposal version, and aggregate version, reruns deterministic validation, writes
the canonical Praxys workouts in one transaction, marks the goal acknowledged
and proposal adopted, increments the aggregate version, appends a linked
`PlanRevision`, bumps the plan revision counter, commits, and only then invokes
the existing managed-delivery trigger. Retrying with the same idempotency key is
safe and returns the original proposal, revision, and canonical workout
snapshots with `status=already_adopted`; it does not re-trigger delivery.
Delivery is a post-commit consequence and is not included in the response
body. Retrying an adopted proposal with a different key returns
`PLAN_PROPOSAL_ALREADY_ADOPTED`.

### POST /api/plan/workouts

Create one future Praxys-owned canonical workout. Multiple canonical workouts
may share a date. External provider rows are never replaced.

**Request body:**
```json
{
  "date": "2026-04-12",
  "workout_type": "easy",
  "planned_duration_min": 45,
  "planned_distance_km": 8.0,
  "target_power_min": 150,
  "target_power_max": 200,
  "target_hr_min": null,
  "target_hr_max": null,
  "target_pace_min": null,
  "target_pace_max": null,
  "workout_description": "Easy aerobic run"
}
```

**Response:** `201` with the created row plus `status="created"`,
`workout_version`, `revision_id`, `editable`, and the post-commit `delivery`
run summary. The summary publishes only `status`, `target`, `reason`, and
`items`. Past dates return `409 PLAN_HISTORY_IMMUTABLE`; invalid power or
heart-rate ordering returns `400 PLAN_TARGET_RANGE_INVALID`. Ordinary Pydantic
shape/range failures return 422.

### PUT /api/plan/workouts/{canonical_id}

Edit, reschedule, or convert one future caller-owned Praxys workout. The body
must include the exact `workout_version` returned by the latest list or
mutation response. A stale version returns `409 PLAN_VERSION_CONFLICT` with
the current version and does not write a revision. Unknown, external, and
other-user identities return the same user-scoped `404`.

**Request body:**
```json
{
  "expected_version": "d8d5c9...64-hex-characters",
  "date": "2026-04-13",
  "workout_type": "threshold",
  "planned_duration_min": 55,
  "planned_distance_km": null,
  "target_power_min": 235,
  "target_power_max": 255,
  "workout_description": "2 x 20 min"
}
```

All fields except `expected_version` are optional; omitted values retain their
current content while explicit `null` clears a nullable field. Changing `date`
reschedules the same `canonical_id` and clears its prior scheduled start time;
same-date note or target edits preserve that start time. Setting a recognized
rest/off type server-side clears duration, distance, power, heart-rate, pace,
and start-time targets regardless of which optional fields the client sends.
The response includes `status="updated"`, the resulting `workout_version`,
append-only `revision_id`, and delivery summary.

Structured update errors use `detail.code`: `PLAN_HISTORY_IMMUTABLE`,
`PLAN_TARGET_RANGE_INVALID`, `PLAN_WORKOUT_NOT_FOUND`,
`PLAN_VERSION_CONFLICT`, or the defensive `PLAN_NO_CHANGES`.
`PLAN_VERSION_CONFLICT` also includes `current_version`, while
`PLAN_HISTORY_IMMUTABLE` includes `minimum_date`, computed in the athlete's
configured timezone with a UTC fallback.

### DELETE /api/plan/workouts/{canonical_id}

Delete one future caller-owned canonical workout.

**Query params:** `expected_version=<64-hex-workout-version>`.

The endpoint applies the same ownership, history, and stale-version fences as
update. A successful response contains `status="deleted"`, `canonical_id`,
`date`, the deleted `workout_version`, `revision_id`, and delivery summary.
Provider-native and third-party workouts cannot be addressed by this route.
Structured delete errors are `PLAN_HISTORY_IMMUTABLE`,
`PLAN_WORKOUT_NOT_FOUND`, and `PLAN_VERSION_CONFLICT`.

### GET /api/plan/adjustments

Return up to 50 newest automatic plan changes, independent of the plan display
window.

**Query params:** `limit` *(1–50, default 20)*.

**Response:**
```json
{
  "items": [
    {
      "id": "7aa4d296-7022-41f9-8c53-3fd97d9e9895",
      "status": "active",
      "can_undo": true,
      "workout_date": "2026-04-11",
      "before": { "workout_type": "threshold", "planned_duration_min": 65 },
      "after": { "workout_type": "rest", "planned_duration_min": null },
      "reason_code": "hrv_below_hard",
      "citations": [
        {
          "label": "Plews et al. (2012)",
          "url": "https://doi.org/10.1007/s00421-012-2354-4"
        }
      ]
    }
  ]
}
```

### POST /api/plan/adjustments/{revision_id}/undo

Restore the exact before-snapshot of one caller-owned automatic adjustment.
The current canonical workout must still match that adjustment's after-version;
otherwise the endpoint returns `409` rather than overwriting a later plan edit.
An unknown or other-user revision returns `404`. Exact retries return
`already_undone` with the original undo revision. A new undo response includes
`delivery_audit_status` as `recorded` or `pending`; `pending` means the
canonical restore succeeded but its append-only delivery consequence still
needs recovery.

### POST /api/plan/push-stryd

Push only Praxys-owned plan rows to the Stryd calendar. Imported Stryd rows are
never eligible, even when they are the analytically preferred plan source.

The endpoint authenticates with the caller's encrypted Stryd
`UserConnection`; global environment credentials are never shared across
users. Missing or unreadable stored credentials return `400` with a reconnect
instruction, and a provider login rejection returns `502`. The only environment
fallback is local development with an explicit
`PRAXYS_STRYD_ENV_USER_ID=<authenticated-user-id>` pin.

Delivery identity is `(user, target, canonical workout key, provider-payload
fingerprint)`. The fingerprint covers the exact transformed request, including
CP-derived workout blocks. A second normalized fingerprint excludes volatile
provider UUIDs so target-side edits can be detected reliably. Retrying a
definite provider rejection appends an attempt to the same delivery row.
Ambiguous outcomes and edits to a Praxys-owned target workout require explicit
reconciliation. Retrying an already-synced payload returns its existing workout
ID without creating a duplicate.

Unowned Stryd workouts never block a create and are never deleted or replaced.
If a requested date contains multiple Praxys workouts, each durable canonical
workout is delivered independently and response entries include
`canonical_id` and `workout_type`. Clients performing a row-level action can
also send `canonical_ids`; the endpoint then delivers only matching workouts
on the requested dates. Omitting it preserves the date-level behavior.

**Request body:**
```json
{
  "workout_dates": ["2026-04-11"],
  "canonical_ids": ["4ac3254f-23cf-4f1f-a609-927f37d5e763"]
}
```

**Response:**
```json
{
  "results": [
    {
      "date": "2026-04-11",
      "canonical_id": "4ac3254f-23cf-4f1f-a609-927f37d5e763",
      "workout_type": "threshold",
      "status": "success",
      "workout_id": "stryd_123"
    }
  ]
}
```

### POST /api/plan/reconciliation/resolve

Apply one explicit conflict resolution. `reconciliation_id` is the opaque,
user-scoped conflict-generation ID returned by `GET /api/plan`. Retrying the
same successful ID returns its recorded result even after reconciliation state
has advanced; a later conflict receives a different opaque ID. Mutation
requests must send the complete opaque ID, including its generation token.

**Request body:**
```json
{
  "reconciliation_id": "delivery:311ef6f2-c119-4bfd-a0e7-b697403bcb21@0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "action": "restore_praxys"
}
```

Actions:
- `restore_praxys` — confirm/remove only the caller-owned prior target ID, then
  deliver the current canonical version. Delete-success/create-failure remains
  visible and retryable. If a stale external ID points to exactly matching
  normalized content, the ledger is rebound without an unnecessary provider
  write.
- `accept_target` — transactionally copy the stored normalized target workout
  into the canonical Praxys row, preserve target provenance in plan metadata,
  and append both a plan revision and import delivery event.

Both actions are idempotent for the same reconciliation subject and canonical
version. Account changes, stale/unowned delete candidates, and changed
observations return `409` instead of mutating either side. The opaque generation
also covers the complete target-calendar snapshot, so a concurrent sync that
introduces a newly matching workout invalidates the resolution before provider
I/O. If restore removal succeeds but recreation fails, the same ID can resume
only from its durable revision plus successful-removal attempt, and only while
every unrelated calendar observation remains unchanged.

### DELETE /api/plan/stryd-workout/{workout_id}

Remove a workout from Stryd calendar and transition its delivery-ledger row to
`removed`. Removal attempts remain auditable; a failed removal keeps the prior
successful delivery state. An interrupted removal can be retried after its lease
expires; attempt fencing prevents a late superseded result from undoing the
newer outcome. The workout ID must belong to the caller's delivery ledger;
unknown IDs return `404` before any Stryd request.

Removal uses the same caller-owned encrypted connection. Unknown IDs are
rejected before credentials are loaded. New deliveries also persist the
authenticated provider account identity, so reconnecting a different Stryd
account blocks deletion with `409`. Credential/authentication failures occur
before the provider attempt; provider and finalization failures remain explicit
and never return a success-shaped fallback. Migrated rows that predate stored
provider-account identity are verified against the live current-account
calendar before their first removal; a missing/moved ID requires reconciliation
instead of treating a cross-account `404` as success.

### POST /api/plan/deliveries/cleanup

Explicitly remove future workouts recorded in the caller's provider-neutral
delivery ledger. The caller must switch to external mode first; requests while
Praxys still owns the plan return `409`. This ordering disables new writes
before any provider cleanup starts, so an interrupted cleanup fails safe.
Every delete rechecks external mode, the unchanged execution target, an
actively connected provider, and the credential generation before touching the
provider.
Cleanup imports any legacy Stryd delivery snapshot before deciding that the
ledger is clear. A corrupt snapshot is quarantined with a durable unresolved
marker, so later retries continue returning `409` until valid legacy state is
imported through an explicitly authoritative recovery or the marker is
reviewed. Quarantine archives created by workers deployed before cleanup
existed are backfilled into the same fence. Routine files recreated by an older
worker remain non-authoritative; marker-aware compatibility dual-writes are
suppressed while unresolved.

**Request body:**
```json
{ "scope": "future" }
```

**Response:**
```json
{
  "status": "complete|partial",
  "target": "stryd",
  "window": { "start": "2026-04-11", "end": null },
  "removed_count": 3,
  "remaining_count": 1,
  "items": [
    {
      "canonical_id": "f0219570-4bda-49df-86a7-1b73ad80af6c",
      "workout_date": "2026-04-12",
      "external_id": "stryd_124",
      "status": "removed|already_absent|blocked|failed",
      "reason": null
    }
  ]
}
```

Every non-removed future ledger row appears in the result. Ledger-owned
workouts with a confirmed external ID are removal candidates, including an
expired in-progress removal lease; uncertain rows without an external ID remain
visible instead of producing a false `complete`. Manual workouts and workouts
owned by another planner have no Praxys delivery row and remain untouched.
If the stored execution target was cleared or changed, cleanup infers a single
outstanding ledger target. Deliveries spanning multiple targets return `409`
instead of silently skipping one target.
Busy, conflicted, account-mismatched, degraded-connection, or failed deliveries
remain `blocked`/`failed`; the response is `partial` and can be retried while
external mode remains active. `removed_count` counts both provider deletions
and rows confirmed already absent; inspect each item status when that
distinction matters.

### POST /api/plan/upload

Upload a Praxys-generated training plan as CSV text. The body is
`{"csv": "..."}`
where the CSV uses the columns `date,workout_type,planned_duration_min,
planned_distance_km,target_power_min,target_power_max,workout_description`.

**Query params:**
- `mode=replace` *(default)* — delete every future Praxys-owned plan row for the user,
  then insert the payload. Past rows survive. Used by full-plan generation
  (the AI training-plan skill writes a 28-day window).
- `mode=merge` — replace only the dates present in the payload; other
  Praxys-owned rows
  are preserved. Multiple workouts on one date are supported. Unique exact
  content matches retain their durable `canonical_id`; after those matches,
  one remaining old and new row on a date are treated as an unambiguous edit.
  Ambiguous same-date groups receive fresh identities rather than transferring
  delivery ownership by row order.

**Response:** `{ "status": "saved", "rows": <int>, "mode": "replace"|"merge",
"revision_id": "<uuid>", "delivery": { ... } }`

The plan-row mutation, cache-revision bump, and append-only `upload` revision
event (actor, origin, before snapshot, after snapshot) commit atomically.
Payload rows must be today or later. A CSV with no data rows returns `400`.

### PUT /api/plan/{date}

Upsert a single Praxys-owned plan workout for the given date (`YYYY-MM-DD`).
Replaces any existing Praxys-owned row(s) for that user and date with one new
row from the body; external rows and other dates are untouched. Prefer this
compatibility route for MCP/date-based clients; interactive clients should use
the canonical-ID endpoints above so stale edits fail closed. Past dates return
`409 PLAN_HISTORY_IMMUTABLE`.

**Request body:**
```json
{
  "workout_type": "easy",
  "planned_duration_min": 45,
  "planned_distance_km": 8.0,
  "target_power_min": 150,
  "target_power_max": 200,
  "workout_description": "Easy aerobic run"
}
```

**Response:** the upserted row (`id`, `canonical_id`, `date`,
`workout_type`, `planned_duration_min`, `planned_distance_km`,
`target_power_min`, `target_power_max`, `target_hr_min`, `target_hr_max`,
`target_pace_min`, `target_pace_max`, `workout_description`, deprecated
`source`, `owner`, `origin`, `workout_version`, `editable`, `status`,
`revision_id`, and `delivery`).

The row and its append-only `upsert` revision event commit atomically.

### DELETE /api/plan/{date}

Delete the Praxys-owned plan workout(s) for the given date (`YYYY-MM-DD`).
External workouts remain untouched. The operation is idempotent — deleting a
missing date returns `rows=0` and `delivery=null`.
Every request appends a `delete` revision event with its before snapshot and an
empty after snapshot; a real deletion and its event commit atomically.
Past dates return `409 PLAN_HISTORY_IMMUTABLE`; interactive clients should use
canonical-ID delete to avoid date-wide removal and enforce optimistic
concurrency.

**Response:** `{ "status": "deleted", "rows": <int>, "date": "YYYY-MM-DD",
"revision_id": "<uuid>", "delivery": { ... } | null }`.

After a successful upload, upsert, or real deletion commits, Praxys starts a
best-effort rolling-delivery pass. The plan mutation remains successful if the
provider is unavailable. External writes occur only when managed mode and delivery are already enabled.

## Settings

### GET /api/settings

Current configuration, platform capabilities, and detected thresholds.

**Response:**
```json
{
  "config": {
    "connections": ["garmin", "stryd", "oura"],
    "preferences": { "activities": "garmin", "recovery": "oura", "plan": "ai" },
    "plan_management": {
      "mode": "external",
      "execution_target": "stryd",
      "delivery_enabled": false,
      "adjustment_policy": "suggest_only"
    },
    "source_options": {
      "athlete_timezone": "America/Los_Angeles"
    },
    "training_base": "power",
    "thresholds": { "cp_watts": null, "lthr_bpm": null, "source": "auto" },
    "zones": { "power": [0.55, 0.75, 0.90, 1.05] },
    "goal": { "distance": "marathon", "target_time_sec": 10800 },
    "science": { "load": "banister_pmc", "zones": "coggan_5zone" }
  },
  "connection_statuses": {
    "garmin": "connected",
    "stryd": "auth_required",
    "oura": "connected"
  },
  "platform_capabilities": {
    "garmin": { "activities": true, "recovery": true, "fitness": true, "plan": false }
  },
  "plan_delivery_options": [
    { "platform": "garmin", "selectable": false, "reason": "account_not_eligible" },
    { "platform": "stryd", "selectable": true, "reason": null },
    { "platform": "strava", "selectable": false, "reason": "delivery_not_supported" }
  ],
  "detected_thresholds": {
    "cp_watts": { "value": 247.8, "source": "stryd" }
  },
  "effective_thresholds": {
    "cp_watts": { "value": 247.8, "origin": "auto (stryd)" }
  },
  "display": { "..." : "..." }
}
```

`config.connections` retains configured platforms in `error` or
`auth_required` so analytical preferences and execution-target intent remain
stable. `connection_statuses` is the live mutation gate; provider workout
actions require the selected target to be exactly `connected`.
`platform_capabilities` is the effective per-user capability map. Garmin's
`plan` value becomes true only while its hard deployment prerequisite, Statsig
eligibility, connected-account region, and registered adapter are all
available.

`plan_delivery_options` is the authoritative execution-target selector
contract. It includes every actively connected activity platform, including
platforms that cannot receive workouts. `selectable=true` means the platform
can be chosen now. Disabled options use the stable reason
`delivery_not_supported` or `account_not_eligible`; clients must describe the
account limitation without exposing the rollout provider. Recovery-only
platforms such as Oura are omitted.

### PUT /api/settings

Update settings (partial update).

**Request body:** Any subset of config fields:
```json
{
  "training_base": "hr",
  "goal": { "distance": "half_marathon", "target_time_sec": 5400 },
  "managed_plan_preview_start": "2026-07-31",
  "source_options": {
    "athlete_timezone": "America/Los_Angeles"
  },
  "plan_management": {
    "mode": "praxys",
    "execution_target": "garmin",
    "delivery_enabled": true,
    "adjustment_policy": "suggest_only"
  }
}
```

`plan_management.mode` is `external` or `praxys`. Praxys mode makes
Praxys-owned rows canonical. `execution_target` must be an actively connected
plan-capable platform with a registered delivery adapter.
`execution_target` is the durable user choice; setting
`delivery_enabled=true` confirms managed delivery and starts a best-effort
delivery pass for today through day 13. The same rolling pass runs after
committed plan mutations and on scheduler ticks. Repeated runs are idempotent;
target edits/deletions and uncertain provider outcomes block only the affected
workout. The settings UI sends `managed_plan_preview_start` with the reviewed
UTC delivery window and also persists the detected IANA timezone. Daily plan
views use the device-local calendar day so an athlete-local automatic change
remains visible across UTC midnight. The server accepts either the current
athlete-local date or the current UTC date for rolling client compatibility.
If the submitted date is no longer current, the update returns `409` without
enabling delivery; the immediate pass uses the same start date so it cannot
include an unreviewed day across a browser/server midnight boundary.
Retry backoff and calendar-observation ordering continue using the actual
execution timestamp.
Setting `delivery_enabled=false` pauses new writes and retries
immediately. Switching to `external` also pauses delivery but keeps workouts
already delivered to the target unless the user separately confirms
`POST /api/plan/deliveries/cleanup`.
Changing `execution_target` is rejected with `409` while any future,
non-removed delivery remains on another connector. The server imports legacy
Stryd push-status evidence before making that decision, so an older delivery
cannot be hidden by switching targets. The supported transition is to switch
to `external`, clean up the old connector's owned deliveries, and then select
the new target. Manual Stryd push requests are subject to the same target fence.
The selected target is retained across mixed-version workers even if an older
worker rewrites `plan_management` without the new field.

Selecting or resuming Garmin requires a connected account and operator
authorization:
`PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED=true` and the default-off Statsig
`garmin_plan_delivery_eligible` gate for the authenticated user. Otherwise the
API returns 409.
Statsig controls rollout eligibility only; it is not consent or durable
product state. Explicit execution-target selection remains in
`config.plan_management`. The server also stores a non-secret internal hash
binding Garmin writes to the current encrypted credential generation and
region. Selecting Garmin or explicitly resuming delivery refreshes that fence.
Reconnect, credential rotation, disconnect, or region change invalidates it
and pauses delivery. Changing region disconnects the old region and clears its
cached tokens; Garmin cannot be selected or resumed in the same request until
the new region reconnects.
Garmin cached sessions are isolated by both Praxys user and credential
generation. Interactive login stages tokens until encrypted credential
persistence succeeds. Manual and scheduled syncs recheck their captured
generation before provider work and before commit; credential rotation or
disconnect cancels a stale sync without changing the replacement connection's
status.

Garmin delivery uses undocumented consumer endpoints and advertises
`duration_only` fidelity. It accepts only running workouts that can be encoded
as a timed `no.target` step; power, pace, and heart-rate targets fail explicitly
instead of being degraded. Creation durably checkpoints Garmin's separate
template and scheduled-instance IDs. Removal unschedules only the exact
ledger-owned instance and retains the reusable template. A schedule discovered
only by calendar set difference is never adopted as owned; an uncertain
schedule request becomes an explicit reconciliation conflict. International and CN
mutation paths have not been live validated. Clients must present this risk and
reduced-fidelity disclosure before managed activation.

`adjustment_policy` is separately consented and defaults to `suggest_only`.
`auto_conservative` is accepted only in Praxys mode; leaving Praxys mode resets
it to `suggest_only`. Enabling it also requires
`source_options.athlete_timezone` to contain a valid IANA timezone name. The
clients persist their detected device timezone with the consent update; the
server uses that timezone to derive the athlete-local plan date and fails
closed when it is missing or invalid. Policy-only updates remain available
while an execution target is disconnected, so consent can always be revoked.
For rolling compatibility, a paused Praxys plan that already opted in ignores
the `suggest_only` placeholder sent by older clients during resume; policy
changes remain a separate settings action. In v1, a successful manual or
scheduled sync may replace
today's single Praxys-generated hard workout with rest only when same-day,
individualized HRV is below the personal lower caution band and the dedicated
HRV-only daily signal independently resolves to `hrv_below_hard`. The policy
never loads activity intensity and never changes manual, adopted, imported, or
external workouts. Missing, stale, internally inconsistent, or prior-day
recovery; an activity already recorded today; multiple Praxys plan rows;
changed canonical content; or missing/stale/pending/conflicting target evidence
fails closed without mutation. A target-calendar snapshot must cover the
athlete-local workout date, and its matching observation must come from that
latest snapshot. TSB, sleep, trends, and other caution signals remain
suggestions. Enabling the policy runs one immediate, post-commit evaluation;
delivery and audit recovery are pinned to the adjusted snapshot's workout
date. Results appear through the plan adjustment history endpoints.

Legacy `preferences.plan` remains supported as the external-mode analytical
source selector and may seed the execution target, but it never activates
managed mode or delivery.

**Response:**
```json
{
  "status": "ok",
  "config": { "..." : "..." },
  "display": { "..." : "..." },
  "connection_statuses": { "garmin": "connected" },
  "platform_capabilities": { "garmin": { "plan": true } },
  "plan_delivery_options": [
    { "platform": "garmin", "selectable": true, "reason": null }
  ]
}
```

The returned connection statuses are read after the post-commit delivery hook,
so clients can disable provider actions immediately if activation degraded the
connection.

### GET /api/settings/connections

Return connected platforms and their status. Credentials are never exposed.

**Response:**
```json
{
  "connections": {
    "garmin": {
      "status": "connected",
      "last_sync": "2026-04-10T08:30:00",
      "has_credentials": true
    },
    "stryd": {
      "status": "disconnected",
      "last_sync": null,
      "has_credentials": false
    }
  }
}
```

### POST /api/settings/connections/{platform}

Connect a platform by storing encrypted credentials. Platform must be one of: `garmin`, `stryd`, `oura`.

**Request body (Garmin/Stryd):**
```json
{
  "email": "user@example.com",
  "password": "platform-password",
  "is_cn": false
}
```

**Request body (Oura):**
```json
{
  "token": "oura-personal-access-token"
}
```

**Response:**
```json
{ "status": "connected", "platform": "garmin" }
```

### POST /api/settings/connections/garmin/login

Connect Garmin interactively. Unlike the generic endpoint above (which stores
credentials and defers login to the background sync), this validates the
credentials up front so an account with multi-factor authentication (MFA)
enabled can be prompted for its code. On success the credentials are persisted
and the OAuth tokens cached for future syncs.

**Request body:**
```json
{
  "email": "user@example.com",
  "password": "garmin-password",
  "is_cn": false
}
```

**Response (no MFA):**
```json
{ "status": "connected", "platform": "garmin" }
```

**Response (MFA required):** the client must follow up with the verification
code Garmin sends:
```json
{
  "status": "mfa_required",
  "platform": "garmin",
  "login_attempt_id": "opaque-server-attempt"
}
```

**Response (bad credentials / rate limited):**
```json
{ "status": "error", "message": "..." }
```

### POST /api/settings/connections/garmin/mfa

Complete a pending interactive Garmin login (see above) with the MFA
verification code and the opaque attempt ID returned by the login endpoint.
The pending login is process-local and expires after a few minutes; a wrong
code can be retried within that window.

**Request body:**
```json
{
  "code": "123456",
  "login_attempt_id": "opaque-server-attempt"
}
```

**Response:**
```json
{ "status": "connected", "platform": "garmin" }
```

A missing/expired pending login returns
`{ "status": "error", "message": "mfa_session_expired" }`.

### DELETE /api/settings/connections/{platform}

Disconnect a platform and delete stored credentials.

**Response:**
```json
{ "status": "disconnected", "platform": "garmin" }
```

## Science

### GET /api/science

Active theories, available options, fixed operational models, and
recommendations.

**Response:**
```json
{
  "active": {
    "load": { "id": "banister_pmc", "name": "Banister PMC", "..." : "..." },
    "zones": { "id": "coggan_5zone", "name": "Coggan 5-Zone", "..." : "..." },
    "heat": { "id": "praxys_heat_evidence", "name": "Praxys Heat Acclimatization Evidence", "..." : "..." }
  },
  "available": {
    "load": [{ "id": "banister_pmc", "..." : "..." }, { "id": "banister_ultra", "..." : "..." }],
    "zones": [{ "id": "coggan_5zone", "..." : "..." }, { "id": "polarized_3zone", "..." : "..." }]
  },
  "fixed_pillars": ["heat"],
  "label_sets": [{ "id": "standard", "name": "Standard" }],
  "recommendations": [
    { "pillar": "zones", "recommended_id": "coggan_5zone", "reason": "...", "confidence": 0.85 }
  ]
}
```

### PUT /api/science

Update theory selections.

Only selectable pillars (`load`, `recovery`, `prediction`, and `zones`) are
updated. Fixed pillars such as `heat` remain active even if a client includes
them in the request.

**Request body:**
```json
{
  "science": { "zones": "polarized_3zone" },
  "zone_labels": "standard"
}
```

## Adaptive-plan personal context

Personal context is optional athlete-owned input used for one explicit
planning purpose. Draft previews are request-only; confirmation creates an
encrypted immutable version and a purpose-confirmation receipt. Every response
uses `Cache-Control: private, no-store`.

First-party web and miniapp JWTs act as the athlete. Plugin and MCP access uses
server-authoritative opaque tokens instead of caller-supplied JWT claims. The
browser receives only random handoff state; the MCP client retains a separate
exchange secret and receives the bearer once, outside the deep link. Only
SHA-256 digests are stored.

An MCP login handoff expires after 10 minutes and exchanges for a 24-hour MCP
session. Personal-context access remains deny-by-default: that session creates
an immutable 10-minute request for one audience, purpose, kind, and read/write
combination. A first-party JWT must approve it before it can exchange for a
15-minute context token. The server checks owner, audience, purpose, kind,
expiry, revocation, and current account state on every use. Context tokens work
only on the scoped personal-context endpoints.
MCP sessions are not general account credentials: ordinary profile, export,
deletion, admin, and first-party personal-context routes require a first-party
JWT. The session retains the official plugin's pre-existing tools through a
fixed method-and-route allowlist for training summaries, settings and
connections, plan authoring/managed delivery, insights, and sync. Any new API
route remains denied until that public plugin contract is reviewed explicitly.
Unauthenticated handoff creation and exchange are independently IP-rate-limited,
and expired handoff/token rows are removed during subsequent handoff creation.

| Scope | Permission |
| --- | --- |
| `plan:context:read` | Read the minimum active structured projection for one purpose and kind |
| `plan:context:write` | Validate one structured request-scoped draft; consumed after one successful preview |

`plan:read` and an ordinary MCP session do not grant context access. Narrative,
delete, correction, confirmation, expiry, export, and AI-consent scopes are
never issued to plugin/MCP clients. Only the athlete may perform those durable
actions. A scoped write returns fixed deep links to `/training#plan-context`
and `/pages/training/index`; it never persists chat or context. The athlete
uses the existing first-party preview/confirm lifecycle, which preserves
canonical encryption, immutable versions, purpose receipts, ownership, and
provenance.

Scoped reads return only `kind`, `purpose`, structured `category` and `fields`,
and active-window timestamps. They omit narrative, item/lineage IDs, source
actor metadata, processing mode, consent/use receipts, and ciphertext.
The only delegated fields are `affected_dates`, `affected_days`,
`available_equipment`, `available_terrain`, `maximum_available_minutes`, and
`workout_status`; existing first-party-only extensions are filtered, and an
MCP preview containing an unknown or out-of-range field fails closed.

### MCP handoff endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/api/auth/mcp/handoffs` | Create opaque MCP login state plus a client-held exchange secret |
| `GET` | `/api/auth/mcp/handoffs/{state}` | First-party inspection of non-sensitive requested authority |
| `POST` | `/api/auth/mcp/handoffs/{state}/decision` | First-party approve or deny |
| `POST` | `/api/auth/mcp/handoffs/exchange` | One-time pending/approved exchange; never accepts an account JWT |
| `GET` | `/api/auth/mcp/me` | Resolve the current opaque MCP session |
| `POST` | `/api/personal-context/scoped-access/requests` | MCP session requests one bounded context grant |
| `POST` | `/api/personal-context/scoped-access/revoke` | Revoke the exact context token immediately |
| `GET` | `/api/personal-context/scoped/selection` | Return the minimum structured projection |
| `POST` | `/api/personal-context/scoped/preview` | Consume one write grant after a valid structured-only preview |

### Context endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/api/personal-context/preview` | First-party validation and normalization without persistence |
| `POST` | `/api/personal-context/confirm` | Confirm a draft and create version 1 |
| `GET` | `/api/personal-context` | Inspect retained versions; filter by `purpose`, `kind`, and `include_history`; set `include_narrative=true` to request retained narrative |
| `GET` | `/api/personal-context/{item_id}` | Inspect one retained version and, for the athlete, its private receipts; set `include_narrative=true` to request retained narrative |
| `POST` | `/api/personal-context/selection` | Select active context while non-destructively excluding item IDs; body field `include_narrative` requests retained narrative |
| `POST` | `/api/personal-context/{item_id}/correct` | Append an immutable corrected successor |
| `POST` | `/api/personal-context/{item_id}/ai-consent` | Grant, deny, or withdraw field-level AI processing consent |
| `POST` | `/api/personal-context/{item_id}/expire` | Stop one current version from influencing decisions |
| `DELETE` | `/api/personal-context/{item_id}?expected_version=N` | Delete the complete lineage and dependent private traces |
| `GET` | `/api/personal-context/export` | Export all retained versions, receipts, and linked revision IDs |
| `GET` | `/api/personal-context/pilot/scenarios` | List the five predefined synthetic pilot scenarios |
| `POST` | `/api/personal-context/pilot/runs` | Run a synthetic scenario or an explicitly opted-in athlete-context scenario |
| `GET` | `/api/personal-context/pilot/proposals/{proposal_id}` | Inspect one owner-scoped immutable pilot proposal |
| `POST` | `/api/personal-context/pilot/proposals/{proposal_id}/responses` | Athlete accepts, rejects, or defers one exact pending proposal |
| `GET` | `/api/personal-context/pilot/evaluation` | Admin-only aggregate operational report without private context or cohorts |

Confirmation, correction, and AI-consent requests require an opaque
`Idempotency-Key` header (8-128 letters, digits, `.`, `_`, `:`, or `-`).
An exact retry returns the original result with `replayed: true`; reusing a key
for different input returns `409
PERSONAL_CONTEXT_VERSION_OR_IDEMPOTENCY_CONFLICT`. Correction, consent, expiry,
and deletion use `expected_version` so a stale client cannot overwrite a newer
version. A payload-free command tombstone retains only the owner and opaque key
after deletion; its context references are cleared, and a delayed confirmation
retry returns `409` instead of recreating deleted private context.

**Preview and confirmation body:**

```json
{
  "kind": "temporary_constraint",
  "purpose": "plan_adjustment",
  "payload": {
    "category": "less_time",
    "fields": {
      "maximum_available_minutes": 30,
      "affected_days": ["monday", "wednesday"]
    },
    "narrative": "Optional, at most 280 characters"
  },
  "linked_subject_type": "plan",
  "linked_subject_id": "plan-canonical-id",
  "starts_at": "2026-08-09T09:00:00Z",
  "expires_at": "2026-08-23T09:00:00Z",
  "purge_after": "2026-09-22T09:00:00Z",
  "consent_text_version": "purpose-v1",
  "client": "web"
}
```

Omit `consent_text_version` and `client` for `/preview`. Supported kinds are
`durable_preference`, `temporary_constraint`, and `execution_explanation`.
Supported purposes are `plan_generation`, `execution_interpretation`,
`plan_adjustment`, `goal_review`, and `outcome_review`. Structured values are
bounded scalars or scalar arrays; unknown payload keys are rejected.

AI processing remains off until the athlete grants consent for an exact
version. `provider` is currently `azure_openai`; `disclosed_fields` uses
`category`, `fields`, `fields.<name>`, or `narrative`. Granting narrative
disclosure requires the item to contain a retained narrative.

### Suggestion-first context pilot

Pilot run and proposal-response commands require an `Idempotency-Key`. An
athlete-context run accepts only `execution_interpretation` or
`plan_adjustment` and requires `"source": "opt_in"` plus
`"confirmed_opt_in": true`. Opted-in runs may set `"allow_ai": true`; the
normal item-level Azure OpenAI consent and field-minimization checks still
apply. Synthetic runs select a scenario returned by the catalog, do not accept
`allow_ai`, and cannot be accepted.

Every run preserves the stable five-outcome contract: `clarification`,
`no_change`, `insufficient_evidence`, `safety`, or `suggestion`. The only
actionable v1 suggestion shortens one time-based, Praxys-generated workout to a
confirmed temporary availability limit. The current plan remains unchanged
until the athlete posts `{"response": "accept"}`. Accepted revisions expose
the existing exact-snapshot undo path; rejection and deferral are non-mutating.

The evaluation endpoint returns only aggregate operational counts and explicit
`not_measured` or `insufficient_evidence` states where subgroup, adverse, or
comparable outcome evidence does not exist. Completed proposal privacy scrubs
are counted; deletion failures are `not_measured` because privacy cleanup does
not retain pilot linkage. It excludes private prompts, values, free text,
identifiers, and context-category cohorts. See
[`adaptive-plan-context-pilot.md`](./adaptive-plan-context-pilot.md) for the
fixed scope, scenarios, falsification conditions, and expansion review gate.

`GET /api/me/export` now uses schema version 2 and embeds the same complete
context export under `personal_context`. Neither export includes idempotency
keys, internal prompts, credentials, deletion-job operator metadata, or
payload-free command tombstones, or another athlete's data.

## Sync

### GET /api/sync/status

Current sync status for all sources.

**Response:**
```json
{
  "garmin": { "status": "idle|syncing|done|error", "last_sync": "ISO timestamp", "error": null },
  "stryd": { "..." : "..." },
  "oura": { "..." : "..." }
}
```

### POST /api/sync/{source}

Trigger sync for a single source (garmin, stryd, oura). Runs in background.

**Request body (optional):**
```json
{ "from_date": "2025-01-01" }
```

### POST /api/sync

Trigger sync for all configured sources.

## Insights and product events

### GET /api/insights and GET /api/insights/{insight_type}

Returns durable model-generated insights for `training_review` and
`race_forecast`. The list endpoint always omits legacy `daily_brief` rows, and
`GET /api/insights/daily_brief` always returns `{"insight": null}`. Today clients
must render `/api/today.signal` instead.

### POST /api/insights

Pushes a durable insight from a CLI or MCP workflow. `training_review` and
`race_forecast` are accepted. A `daily_brief` push returns HTTP 410 with
`DAILY_BRIEF_DETERMINISTIC` so client prose can never replace the canonical
same-day signal.

### POST /api/insights/{insight_type}/feedback

Submit one vote for the exact generated Coach insight the authenticated user saw.
Uses the current user's id (not demo-source data) and supports `training_review`
or `race_forecast`. Feedback for `daily_brief` returns HTTP 410 with
`DAILY_BRIEF_DETERMINISTIC`.

**Request body:**
```json
{
  "vote": "up",
  "dataset_hash": "64-character SHA-256 hex digest",
  "comment": "Optional, at most 200 characters"
}
```

The current row's `meta.dataset_hash` must match. One submission is accepted per
`(user, insight_type, dataset_hash)`; repeats return `duplicate: true`, even if
that dataset disappears during regeneration and later becomes current again.
The durable `ai_insight_feedback` row and current `AiInsight.meta.feedback`
contain only `dataset_hash`, `vote`, and `submitted_at`. The raw comment is not
persisted; telemetry receives a scrubbed 120-character excerpt.
`GET /api/insights/{insight_type}` also returns server-derived
`feedback_allowed`; it is `false` for read-only demo views, where clients must
hide feedback controls.
**Response:**
```json
{
  "accepted": true,
  "duplicate": false,
  "feedback": {
    "dataset_hash": "...",
    "vote": "up",
    "submitted_at": "2026-07-12T08:30:00+00:00"
  }
}
```

Errors: `404 INSIGHT_NOT_FOUND`, `409 INSIGHT_FEEDBACK_UNVERSIONED`,
`409 INSIGHT_FEEDBACK_STALE`, `410 DAILY_BRIEF_DETERMINISTIC`,
`429 INSIGHT_FEEDBACK_RATE_LIMITED`.

### POST /api/product-events/today-feedback-claim

Reserve the account's Today Decision Check while the client renders it. The
request has no body and returns `{ "accepted": true, "duplicate": false }` when
the prompt may render. A duplicate response means another client has a recent
claim or the prompt was shown within the rolling seven-day cadence. Unconfirmed
claims stop blocking competing renders after two minutes and do not count as
prompt exposure unless a later submission backfills the lost confirmation.

After rendering, the client confirms exposure with `today_feedback_shown` on
`POST /api/product-events`.

### POST /api/product-events

Record an authenticated, privacy-safe product event from web or miniapp. The
server derives `user_id_hash` and timestamp. Extra fields are rejected.
`app_version` must be `develop`, a release CalVer (`YYYY.MM.MICRO`), or an
auto-deploy build (`YYYY.MM.DD.RUN-abcdef0`). Other free-form strings are
rejected so secrets cannot be smuggled into telemetry dimensions.

**Request body:**
```json
{
  "event_name": "today_feedback_submitted",
  "surface": "miniapp",
  "app_version": "2026.07.1",
  "response": "confirmed_plan"
}
```

Allowed events: `app_opened`, `today_brief_rendered`,
`today_reasoning_opened`, `today_feedback_shown`, and
`today_feedback_submitted`. `response` is required only for the submission event
and must be one of `changed_plan`, `confirmed_plan`, `not_helpful`, or
`not_training`.

**Response:** `{ "accepted": true, "duplicate": false }`. Identical lifecycle
events are short-window deduplicated. `today_feedback_shown` confirms a recent
render claim and persists the account-wide seven-day cadence. The first
`today_feedback_submitted` is accepted for a claimed or confirmed prompt
within that seven-day cadence. The two-minute lease limits competing renders;
it does not invalidate a prompt already visible to the user. A submission can
backfill a lost render confirmation, while later answers return
`duplicate: true`.

Errors: `409 PRODUCT_EVENT_PROMPT_NOT_CLAIMED`,
`409 PRODUCT_EVENT_PROMPT_NOT_RENDERED`, and
`429 PRODUCT_EVENT_RATE_LIMITED` after 60 requests per user per minute.

## Health

### GET /api/health

Unauthenticated health check.

**Response:**
```json
{ "status": "ok" }
```

## Common Response Fields

Every endpoint that returns training data includes:

- **`training_base`**: `"power"`, `"hr"`, or `"pace"` — the user's configured training base
- **`display`**: Dynamic labels and units for the active training base:
  - `threshold_label`: "Critical Power" / "Lactate Threshold HR" / "Threshold Pace"
  - `threshold_abbrev`: "CP" / "LTHR" / "T-Pace"
  - `threshold_unit`: "W" / "bpm" / "/km"
  - `load_label`: "RSS" / "TRIMP" / "rTSS"
  - `load_unit`: "" (empty string)
  - `intensity_metric`: "Power" / "Heart Rate" / "Pace"
  - `zone_names`: Zone name array from active theory
  - `trend_label`: "CP Trend" / "LTHR Trend" / "Pace Trend"
