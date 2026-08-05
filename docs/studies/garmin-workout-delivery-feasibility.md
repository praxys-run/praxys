# Garmin Workout Delivery Feasibility

- Study date: 2026-08-02
- Implementation decision updated: 2026-08-03
- Issues: [#484](https://github.com/praxys-run/praxys/issues/484),
  [#485](https://github.com/praxys-run/praxys/issues/485)

## Decision

**Keep Garmin consumer-API writes disabled by default. Permit them only when an
operator-controlled deployment gate and explicit per-user experimental consent
are both active. Do not advertise them as a supported platform capability.**
`PLATFORM_CAPABILITIES["garmin"]["plan"]` remains false. Production keeps
`PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED=false` until both controlled international
and China lifecycle matrices pass. Dedicated validation users may be admitted
individually through the default-empty
`PRAXYS_GARMIN_PLAN_DELIVERY_PILOT_USER_IDS` allowlist without exposing other
production users; an approved isolated validation deployment may instead
enable the global gate. The settings API enables the effective per-user
capability only after one operator authorization path is active and consent is
bound to the current encrypted credential generation and Garmin region.

The fallback is deliberately narrower than the operations exposed by
`garminconnect`:

- only duration-conditioned running workouts with `no.target` are accepted;
- power, pace, and heart-rate targets are rejected rather than silently
  degraded;
- the template and scheduled-instance IDs are checkpointed independently;
- an uncertain upload may resume only after exact template reconciliation;
  an uncertain schedule is never adopted or replayed automatically;
- removal unschedules only the exact ledger-owned scheduled instance and
  retains the reusable template, because a user may have scheduled it manually
  elsewhere;
- writes are paced, and ambiguous identity or observation remains a visible
  conflict;
- safe upload recovery scans at most 500 existing templates. Delivery is
  rejected before mutation when the library is already at that ceiling, with
  an instruction to remove unused templates in Garmin Connect. If the ceiling
  is reached only after a possible upload, the outcome remains fenced as
  unknown and is never retried automatically;
- reconnecting, rotating credentials, or disconnecting revokes consent;
- interactive reconnect commits that revocation and pauses delivery before
  any tokenstore mutation;
  changing Garmin region additionally disconnects the old region and requires
  a fresh login before consent can be granted again.

This resolves the ledger and replay hazards identified in the original study,
but it does not make Garmin's consumer API stable or supported. International
and China hosts still have only source-level write parity; no Praxys live write
matrix has been completed. The endpoints, response contracts, compatibility
policy, and rate limits remain undocumented.

The supported production path is Garmin's official
[Training API](https://developer.garmin.com/gc-developer-program/training-api/).
It is designed to publish structured workouts and training plans to Garmin
Connect after user consent. Praxys should apply to the
[Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/overview/)
and retarget #485 to that contract after approval. Garmin states that the
program uses OAuth 2.0, is for business use, and has no licensing or
maintenance fee, although some commercial metrics may carry separate terms
([program FAQ](https://developer.garmin.com/gc-developer-program/program-faq/)).

Garmin's official Training API remains the preferred long-term integration.
Praxys should apply when program access is available and replace the
experimental adapter without changing the provider-neutral ownership ledger.
A controlled consumer-API lifecycle test would reduce technical uncertainty;
passing it would not make the private API supported.

## Study boundary

The research and implementation were credential-free and non-mutating. No
Garmin account was accessed, no workout was written, and no personal response
payload was captured. Adapter behavior is covered with deterministic fake
provider fixtures; those tests do not claim live endpoint or device fidelity.

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

Praxys uses the scheduled instance `id` as both
`PlanTargetWorkout.external_id` and `PlanDelivery.external_id`, preserving an
exact reconciliation join. The template ID is stored separately in bounded
provider references. A composite string in `external_id` is not acceptable
because it would no longer match the calendar observation.

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

Until those tests pass, the Garmin adapter rejects unsupported shapes with
`unsupported_workout_shape`. It does not silently turn a power-targeted
interval workout into a generic timed workout and call that a successful sync.

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

The adapter reuses the existing region selection, portal-login workaround, and
account fence. Tokenstores are additionally scoped to the encrypted credential
generation. Interactive login stages tokens until that credential generation
is durably stored; background sync rechecks the same generation before
provider work and every commit. Rotation cannot therefore rebind an in-flight
old Garmin session to the replacement connection. The adapter does not
introduce a second Garmin login path.

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
- classify both Garmin's dedicated too-many-requests exception and a generic
  `API Error 429` as a provider rate limit and stop the batch;
- use conservative pacing and normal scheduler backoff; do not discover a
  rate limit by stress-testing a real account;
- treat an ambiguous or duplicate match as a visible conflict.

## Fit against Praxys managed-plan guarantees

| Guarantee | Consumer API status | Required before reconsideration |
|---|---|---|
| Create on an intended date | Operations exist | Live upload + schedule + calendar round-trip |
| Preserve unrelated workouts | Implemented, not live-validated | Unschedule only the ledger-owned schedule; retain templates |
| Idempotent retries | Implemented, not live-validated | Durable intent/template/schedule checkpoints plus exact recovery |
| Replace transparently | Conservative delete/create staging | Live lifecycle validation |
| Remove only Praxys work | Implemented with both IDs | Live same-template/multiple-schedule validation |
| Recover partial create | Implemented | Live timeout and propagation-delay validation |
| Reconcile unknown schedule outcome | Implemented | Live response-shape validation |
| Preserve structured intensity | Duration-only | Round-trip target values before expanding fidelity |
| International support | Source-level only | Controlled live lifecycle |
| China support | Source-level only | Separate controlled CN lifecycle |
| Stable supported integration | No | Use official Training API |

The provider-neutral protocol now carries bounded `provider_references` on the
delivery and target observation. Garmin keeps the scheduled instance as
`external_id` and stores template/schedule IDs separately. Adapter mutation
hooks recheck the connection and plan boundary immediately before each provider
effect, then durably checkpoint confirmed identities while the attempt remains
in progress.

## Implemented fallback contract

1. Before upload, persist the deterministic marker, payload fingerprint, and
   complete preexisting template-ID set, including an explicitly empty set.
   The semantic fingerprint includes target type, zone, and exact target
   values so materially different power or pace prescriptions cannot collide.
2. After upload, checkpoint `template_id` before scheduling.
3. Before schedule, checkpoint preexisting schedule IDs for that template/date.
4. After schedule, checkpoint `schedule_id` as both provider reference and
   delivery `external_id` before post-write verification.
5. Checkpoint `upload_started` and `schedule_started`, then re-run the
   connection/consent guard immediately before their respective provider
   calls. A crashed template checkpoint may resume only before schedule
   starts; a started schedule without a confirmed ID becomes a conflict.
6. Resume from confirmed checkpoints. A checkpointed schedule that is not yet
   visible fails closed instead of being replayed.
7. Recover an uncertain upload only when exactly one newly created
   marker-and-full-fingerprint template match exists. A schedule seen only by
   set difference is never claimed because the user may have manually reused
   the retained template. Reject any returned schedule ID that was present
   before the request. If Garmin returns an unexpected date, directly verify
   the returned ID and template, then checkpoint it only as an unowned
   conflict candidate. Explicit reconciliation must establish ownership before
   adoption or removal. `restore_praxys` never adopts a Garmin fingerprint
   candidate unless its external ID equals the delivery's exact durable
   schedule identity (`schedule_id` or delivery `external_id`); other
   candidates require the explicit target-adoption action.
8. Preserve `workoutId` in normalized Garmin calendar evidence and fence every
   observation with the immutable Garmin `userProfileId`, Praxys user, and
   region. Keep the pre-existing display-name-derived account hash as the
   reconciliation key during rolling deployment; the private profile fence is
   the mutation-safety identity. A matching immutable profile reference may
   bridge a display-name-derived key change, while a different immutable
   profile always fails closed. Persist that identity on the complete calendar
   snapshot as well as each row, so an empty snapshot cannot infer absence for
   a different same-display-name profile.
9. Before removal, verify that the exact schedule still references the stored
   template; unschedule only that instance. Templates are intentionally
   retained to avoid affecting manually reused schedules. Scheduled-date
   changes classify as target edits and must be removed by exact owned ID
   before the canonical date is recreated. Confirmed absence likewise checks
   the exact schedule ID when known, otherwise the intended date plus full
   content fingerprint; a matching retained template on another date is not
   evidence that the owned schedule still exists.
10. Keep static Garmin plan capability false. Effective capability requires
   the default-off operator gate plus current connection-bound consent and
   reports `fidelity: duration_only`.
11. Persist the selected execution target outside the legacy settings JSON for
   mixed-worker safety. Import legacy Stryd status before any target switch and
   reject the switch while future, non-removed deliveries remain on another
   connector; manual Stryd writes apply the same just-in-time target fence.
12. Bind each completed interactive login's in-memory serialized OAuth bundle
    to an opaque, server-generated login-attempt ID. Return that ID to the
    client and require it when completing MFA. Encrypt the matching bundle in
    the same generation-fenced transaction as its credentials; concurrent
    login attempts cannot consume or replace one another's session.
13. Bound full-library template recovery to 500 entries. At-limit detection
    before upload is an actionable, non-retryable rejection. Exhaustion after
    a possible upload remains an unknown outcome so automatic retries cannot
    create duplicates.
14. Treat a confirmed 401 as connection authentication failure. Treat a
    confirmed 429 as account-level backoff: stop the remaining rolling batch
    instead of retrying every workout against the active rate limit.
15. Serialize each user's complete rolling pass across workers and fence
    connection-success bookkeeping against newer auth/rate-limit state.

Confirmed-delete-then-create replacement uses these checkpoints for both
halves. Adopting Garmin's in-place PUT instead would require a separate
provider-neutral replacement contract and its own unknown-outcome
reconciliation; it must not be hidden inside `create_workout`.

## Controlled live test gate

Run this only with explicit human approval against one international test
account and one China test account. Use synthetic names, a safe future date,
and no personal target values. Keep credentials and raw responses outside the
repository. Pace requests; do not perform a rate-limit stress test.

| Step | Required assertion |
|---|---|
| Authenticate | Existing portal flow returns immutable `userProfileId` |
| Upload | Response contains one positive `workoutId` |
| Get template | One timed `no.target` step round-trips with exact duration |
| Schedule | Response contains one positive `workoutScheduleId` and intended date |
| Read month | Item `id` equals schedule ID; `workoutId` equals template ID |
| Get schedule | Response repeats both identities and the intended date |
| Duplicate probe | A second same-template/same-date schedule is either rejected or returned as a separately identifiable instance; clean it explicitly |
| Unschedule | Exact scheduled instance disappears while an unrelated same-date workout remains |
| Retain template | Exact template remains available and no unrelated template changes |
| Device | Scheduled workout renders as duration-only without inferred intensity |
| Cleanup | No synthetic scheduled instance remains, even after a failed assertion |

Repeat the same lifecycle independently on `.com` and `.cn`; success in one
region does not enable the other. Any ambiguous identity, cleanup failure,
silent target conversion, CAPTCHA/rate-limit escalation, or region-specific
shape difference keeps that region no-go.

## Next actions

1. Keep the production operator gate off until both controlled regional
   matrices pass; retain independent per-user opt-in afterward.
2. Run the controlled international and CN matrices only with explicit human
   approval and dedicated test accounts.
3. Apply for Garmin Connect Developer Program access when available and request
   the Training API contract.
4. Retarget the adapter to the official API when approved; preserve the current
   provider-neutral IDs, account fencing, and reconciliation semantics.

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
