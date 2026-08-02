# Garmin Workout Delivery Feasibility

Study date: 2026-08-02  
Issue: [#484](https://github.com/praxys-run/praxys/issues/484)

## Decision

**Do not enable production Garmin workout writes through the undocumented
Garmin Connect consumer endpoints.** Keep
`PLATFORM_CAPABILITIES["garmin"]["plan"]` false and keep #485 blocked.

The consumer API is technically capable of uploading a workout template,
scheduling it, updating it, unscheduling it, and deleting it. It does not yet
meet Praxys's managed-plan guarantees:

- one logical delivery requires two non-idempotent POSTs;
- Garmin assigns separate template and scheduled-instance IDs, while the
  current delivery contract durably owns only one provider ID;
- a timeout between either side effect and its ledger commit can create an
  unowned template or duplicate schedule;
- international and China hosts share source-level paths, but no public or
  Praxys live evidence verifies workout writes on `garmin.cn`;
- power/pace/heart-rate target values and device rendering have not been
  round-tripped on either region;
- the endpoints, response contracts, compatibility policy, and rate limits
  are undocumented.

The supported production path is Garmin's official
[Training API](https://developer.garmin.com/gc-developer-program/training-api/).
It is designed to publish structured workouts and training plans to Garmin
Connect after user consent. Praxys should apply to the
[Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/overview/)
and retarget #485 to that contract after approval. Garmin states that the
program uses OAuth 2.0, is for business use, and has no licensing or
maintenance fee, although some commercial metrics may carry separate terms
([program FAQ](https://developer.garmin.com/gc-developer-program/program-faq/)).

A controlled consumer-API test may still be useful as an explicitly
unsupported fallback study. Passing it would reduce technical uncertainty; it
would not make the private API a supported production integration.

## Study boundary

This was a credential-free, non-mutating source and contract review. No Garmin
account was accessed, no workout was written, and no personal response payload
was captured.

Evidence reviewed:

- Praxys's installed `garminconnect` 0.3.6 and current delivery/reconciliation
  contracts;
- immutable `python-garminconnect` 0.3.6 and 0.3.8 source;
- upstream release notes and unit tests;
- a public scheduled-workout response fixture and a public schedule-response
  example;
- Garmin's public Developer Program, Training API, and FAQ pages.

Reproduce the installed-version check from the repository root:

```powershell
.venv\Scripts\python.exe -c "from importlib.metadata import version; print(version('garminconnect'))"
```

The result used for this study was `0.3.6`, matching the repository constraint
`garminconnect>=0.3.6,<0.4.0` in
[`requirements.txt`](../../requirements.txt).

## Consumer API capability

### Version matrix

| Operation | 0.3.6 installed | 0.3.8 latest | Consumer endpoint |
|---|---:|---:|---|
| List/get templates | Yes | Yes | `GET /workout-service/workouts`, `GET /workout-service/workout/{workoutId}` |
| Upload template | Yes | Yes | `POST /workout-service/workout` |
| Update template in place | No | Yes, added in 0.3.7 | `PUT /workout-service/workout/{workoutId}` |
| Delete template | Yes | Yes | `DELETE /workout-service/workout/{workoutId}` |
| Read month calendar | Yes | Yes | `GET /calendar-service/year/{year}/month/{month-1}` |
| Get scheduled instance | Yes | Yes | `GET /workout-service/schedule/{scheduleId}` |
| Schedule template | Yes | Yes | `POST /workout-service/schedule/{workoutId}` with `{"date":"YYYY-MM-DD"}` |
| Unschedule instance | Yes | Yes | `DELETE /workout-service/schedule/{scheduleId}` |

Immutable source:

- 0.3.6 template operations:
  [`eb5015f`](https://github.com/cyberjunky/python-garminconnect/blob/eb5015fda2737ed817fe0e2514a26db1f75f070b/garminconnect/__init__.py#L2745-L2793)
- 0.3.6 calendar operations:
  [`eb5015f`](https://github.com/cyberjunky/python-garminconnect/blob/eb5015fda2737ed817fe0e2514a26db1f75f070b/garminconnect/__init__.py#L2937-L2989)
- 0.3.8 in-place update:
  [`e4e9748`](https://github.com/cyberjunky/python-garminconnect/blob/e4e9748cf3fa62f997e77171addee3acc333232c/garminconnect/__init__.py#L2867-L2894)
- [`0.3.7` release notes](https://github.com/cyberjunky/python-garminconnect/releases/tag/0.3.7)
  introducing `update_workout()`

If a future implementation uses in-place update, the minimum dependency must
move to 0.3.7 and every existing 0.3.x authentication workaround must be
revalidated before deployment. Version 0.3.8 did not change workout semantics;
its workout-related changes were demo and documentation fixes
([release notes](https://github.com/cyberjunky/python-garminconnect/releases/tag/0.3.8)).

### Two provider identities

Garmin separates a reusable workout template from a placement on the calendar:

1. `upload_workout()` returns a template `workoutId`.
2. `schedule_workout()` returns a `workoutScheduleId`.
3. The monthly calendar represents that scheduled instance as `id` and also
   includes its template `workoutId`.
4. `unschedule_workout()` requires the scheduled-instance ID.
5. `delete_workout()` requires the template ID.

The schedule response shape is shown in
[upstream issue #290](https://github.com/cyberjunky/python-garminconnect/issues/290#issuecomment-3378304457).
The month-calendar pairing is independently present in the immutable
[`scheduled_workouts.json`](https://github.com/kgabryje/garmin-mcp/blob/1d4c72732d5f37cb9df4fa7545c32a6450bf3cc9/tests/fixtures/scheduled_workouts.json)
fixture used by #262.

Praxys correctly uses the scheduled instance `id` as
`PlanTargetWorkout.external_id`. A future delivery ledger must use that same
schedule ID as `PlanDelivery.external_id` so reconciliation remains an exact
join. It must durably store the template ID as a second, provider-opaque
reference. A composite string in `external_id` is not acceptable because it
would no longer match the calendar observation.

### Structured-workout fidelity

`garminconnect` 0.3.8 models running workout segments, executable and repeat
steps, time/distance end conditions, and target-type constants:

- schema and target constants:
  [`workout.py`](https://github.com/cyberjunky/python-garminconnect/blob/e4e9748cf3fa62f997e77171addee3acc333232c/garminconnect/workout.py#L29-L214)
- time, distance, recovery, cooldown, and repeat builders:
  [`workout.py`](https://github.com/cyberjunky/python-garminconnect/blob/e4e9748cf3fa62f997e77171addee3acc333232c/garminconnect/workout.py#L303-L466)

That proves request-shape support, not end-to-end fidelity. The public helper
functions accept a target-type object but do not provide a validated builder
for absolute lower/upper power, pace, or heart-rate values. Praxys must verify
the exact fields, units, round-trip response, and device display. This matters
especially for running power because Garmin-native and Stryd power scales are
not interchangeable.

Until those tests pass, a Garmin adapter must reject an unsupported shape with
an explicit `unsupported_workout_shape` result. It must not silently turn a
power-targeted interval workout into a generic timed workout and call that a
successful sync.

## Region, authentication, and failure behavior

### International and China routing

`Garmin(is_cn=True)` selects `garmin.cn`; the lower-level client derives SSO,
Connect API, mobile, portal, and DI-token hosts from that domain:

- region selection:
  [`garminconnect/__init__.py`](https://github.com/cyberjunky/python-garminconnect/blob/e4e9748cf3fa62f997e77171addee3acc333232c/garminconnect/__init__.py#L559-L564)
- domain-derived hosts:
  [`garminconnect/client.py`](https://github.com/cyberjunky/python-garminconnect/blob/e4e9748cf3fa62f997e77171addee3acc333232c/garminconnect/client.py#L188-L201)

Therefore the workout paths have source-level parity. This is not live parity.
Praxys has previously observed endpoint-specific 400/404 and response-shape
differences on Garmin China. Existing live CN validation covers portal
authentication and profile/settings reads, not workout calendar CRUD.

Any future adapter must reuse the existing per-user tokenstore, region
selection, portal-login workaround, and account fence. It must not introduce a
second Garmin login path.

### Retries and ambiguous outcomes

The library's 5xx/network retry decorator wraps read helpers, not the raw
`client.post()`, `put()`, or `delete()` used by workout mutations. The
lower-level client does replay any request once after a 401 token refresh, maps
404 separately, and otherwise raises a generic connection error for HTTP
failures:

[`garminconnect/client.py`](https://github.com/cyberjunky/python-garminconnect/blob/e4e9748cf3fa62f997e77171addee3acc333232c/garminconnect/client.py#L1338-L1432)

Consequences for an adapter:

- never automatically retry an upload or schedule after a timeout, disconnect,
  or 5xx response;
- reconcile first, using the intended date, exact payload fingerprint, durable
  provider references, and account fence;
- classify the mutation path's generic `API Error 429` as a provider rate
  limit and stop the batch;
- use conservative pacing and normal scheduler backoff; do not discover a
  rate limit by stress-testing a real account;
- treat an ambiguous or duplicate match as a visible conflict.

## Fit against Praxys managed-plan guarantees

| Guarantee | Consumer API status | Required before reconsideration |
|---|---|---|
| Create on an intended date | Operations exist | Live upload + schedule + calendar round-trip |
| Preserve unrelated workouts | Achievable | Delete only a ledger-owned schedule ID and template ID |
| Idempotent retries | Not achieved | Durable intermediate checkpoints and read-before-retry recovery |
| Replace transparently | API exists in 0.3.7 | Live update fidelity, or audited unschedule/delete/create staging |
| Remove only Praxys work | Not achieved with one ID | Persist both IDs and verify both against the same account |
| Recover partial create | Not achieved | Persist template ID before scheduling and expose partial state |
| Reconcile unknown schedule outcome | Partially achievable | Retain template ID in normalized calendar evidence |
| Preserve structured intensity | Unverified | Round-trip target values and confirm device rendering |
| International support | Source-level only | Controlled live lifecycle |
| China support | Source-level only | Separate controlled CN lifecycle |
| Stable supported integration | No | Use official Training API |

The current provider-neutral protocol returns one `external_id` only after
`create_workout()` finishes, and later calls `delete_workout(external_id)`.
That is sufficient for Stryd's one-object create/delete lifecycle but cannot
durably represent Garmin's template-then-schedule state machine. The
`PlanDeliveryAttempt.response` JSON is not enough: removal passes only the
ledger's single external ID to the adapter.

## Contract required for any consumer-API fallback

If a human explicitly accepts the unsupported integration risk and all live
gates below pass, #485 must first make these provider-neutral changes:

1. Add durable provider references to a delivery, preferably a generic JSON
   mapping such as `{"template_id": "...", "schedule_id": "..."}`. Keep
   `external_id` equal to `schedule_id`.
2. Let an adapter checkpoint confirmed intermediate references while an
   attempt remains in progress. The service must commit `template_id`
   immediately after upload and before schedule.
3. Carry confirmed references on outcome-unknown and removal errors so a
   later reconciliation can resume cleanup without guessing.
4. Preserve Garmin `workoutId` in normalized target evidence alongside the
   scheduled `external_id`.
5. Before removal, verify the observed schedule ID, stored template ID,
   provider account, date, and content fingerprint. Unschedule first; delete
   the template only when the ledger proves Praxys created it and no other
   schedule still references it.
6. On an uncertain upload, search for one exact account-fenced template using
   a deterministic Praxys marker plus the full payload fingerprint. Zero
   matches permits a retry; one exact match may be adopted; multiple matches
   become a conflict. A name or marker alone never grants delete ownership.
7. Keep region-specific capability gates. International and CN enablement are
   independent.
8. Add explicit reduced-fidelity status if the product ever permits a safe
   fallback. The default is to block, not degrade silently.

The existing confirmed-delete-then-create replacement behavior may remain, but
both halves must use these checkpoints. Adopting Garmin's in-place PUT instead
would require a separate provider-neutral replacement contract and its own
unknown-outcome reconciliation; it should not be hidden inside `create_workout`.

## Controlled live test gate

Run this only with explicit human approval against one international test
account and one China test account. Use synthetic names, a safe future date,
and no personal target values. Keep credentials and raw responses outside the
repository. Pace requests; do not perform a rate-limit stress test.

| Step | Required assertion |
|---|---|
| Authenticate | Existing portal flow returns the expected account fence |
| Upload | Response contains one positive `workoutId` |
| Get template | Full step tree round-trips with exact duration and target units |
| Schedule | Response contains one positive `workoutScheduleId` and intended date |
| Read month | Item `id` equals schedule ID; `workoutId` equals template ID |
| Get schedule | Response repeats both identities and the intended date |
| Duplicate probe | A second same-template/same-date schedule is either rejected or returned as a separately identifiable instance; clean it explicitly |
| Update | On 0.3.7+, PUT preserves template and schedule IDs and updates the calendar/device representation |
| Unschedule | Exact scheduled instance disappears while an unrelated same-date workout remains |
| Delete template | Exact template becomes 404 and unrelated templates remain |
| Cleanup | No synthetic template or scheduled instance remains, even after a failed assertion |

Repeat the same lifecycle independently on `.com` and `.cn`; success in one
region does not enable the other. Any ambiguous identity, cleanup failure,
silent target conversion, CAPTCHA/rate-limit escalation, or region-specific
shape difference keeps that region no-go.

## Next actions

1. Apply for Garmin Connect Developer Program access and request the Training
   API contract.
2. Keep #485 in backlog until the official API can be mapped, or until a human
   explicitly chooses the unsupported fallback and both live matrices pass.
3. Continue #486's provider-neutral observability and recovery hardening; it
   remains useful for Stryd and for a future official Garmin adapter.

## References

- Garmin Training API:
  <https://developer.garmin.com/gc-developer-program/training-api/>
- Garmin Connect Developer Program overview:
  <https://developer.garmin.com/gc-developer-program/overview/>
- Garmin Connect Developer Program FAQ:
  <https://developer.garmin.com/gc-developer-program/program-faq/>
- `python-garminconnect` 0.3.6:
  <https://github.com/cyberjunky/python-garminconnect/releases/tag/0.3.6>
- `python-garminconnect` 0.3.7:
  <https://github.com/cyberjunky/python-garminconnect/releases/tag/0.3.7>
- `python-garminconnect` 0.3.8:
  <https://github.com/cyberjunky/python-garminconnect/releases/tag/0.3.8>
- Schedule response example:
  <https://github.com/cyberjunky/python-garminconnect/issues/290#issuecomment-3378304457>
- Calendar response fixture:
  <https://github.com/kgabryje/garmin-mcp/blob/1d4c72732d5f37cb9df4fa7545c32a6450bf3cc9/tests/fixtures/scheduled_workouts.json>
