# Feedback triage alert (`needs_review`)

When in-app feedback can't be auto-filed safely (the AI sensitivity gate, a
scrubbed secret, or no LLM configured), the row is parked as `needs_review` for
an admin to approve. In-app, that surfaces as a badge on the Admin sidebar and a
sorted-to-top row in the Admin → User Feedback table.

For "admin isn't looking at the dashboard", wire an **Azure Monitor alert** that
emails when something needs review. **No application code is required** — the
backend already emits the signal; you just add the alert + action group.

## The signal

`api/telemetry.py::record_feedback(kind, status)` runs after every triage and at
submit time, emitting **`praxys.feedback`** with dimensions `kind` and `status`.
Status values: `new`, `triaged`, `needs_review`, `issue_created`, `failed`,
`rejected`. It lands as:

- a **customEvent** named `praxys.feedback` when `azure-monitor-events-extension`
  is installed, **or**
- a **customMetric** named `praxys.feedback` (the default) otherwise.

Requires `APPLICATIONINSIGHTS_CONNECTION_STRING` set on the App Service (it is in
prod). No PII is in telemetry — only `kind` + `status`.

## Alert query (KQL)

Robust against either emission shape:

```kql
union isfuzzy=true
  (customMetrics
    | where name == "praxys.feedback"
    | extend status = tostring(customDimensions.status)),
  (customEvents
    | where name == "praxys.feedback"
    | extend status = tostring(customDimensions.status))
| where status == "needs_review"
```

## Wire the alert (one-time, in the Azure portal)

1. **Application Insights resource -> Monitoring -> Alerts -> Create -> Alert rule.**
2. **Scope**: the Praxys Application Insights resource.
3. **Condition** -> *Custom log search*. Paste the KQL above.
   - Measurement: **Number of results**, **Aggregation granularity** 15 minutes.
   - Alert logic: **Greater than 0**, **Frequency of evaluation** 15 minutes.
   - (Optional) Split by `kind` if you want per-category emails.
4. **Actions** -> create/select an **Action group** with an **Email** action to
   your support / admin address (SMS, Teams, or a webhook also work here).
5. **Details**: severity Sev 3, name e.g. `praxys-feedback-needs-review`.
6. Create. Submit a test bug report that trips the gate (e.g. with no
   `AZURE_AI_ENDPOINT`, or paste a fake `sk-...` token) and confirm the email.

## Tuning

- The 15-minute window batches bursts into one notification. Widen for fewer,
  larger digests.
- To also catch publish failures, change the filter to
  `where status in ("needs_review", "failed")`.
- Prefer in-app email instead of an Azure alert? That's net-new infra (e.g.
  Azure Communication Services Email) — out of scope here.
