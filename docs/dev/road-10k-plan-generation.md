# Road 10K plan generation implementation

## Accepted runtime contract

- Capability id: `outdoor_road_10k_performance_v1`
- Policy version: `road-10k-plan-generation-policy-v2`
- Generator version: `road-10k-deterministic-generator-v1`
- Science decision id: `sdr-road-10k-plan-generation-policy-v2`
- Contract digest: `sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496`
- Source decision digest: `sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad`
- Runtime state: **mechanically inactive and hidden**. This revision has no activation path; authority binding is parsing-only and cannot authorize a capability.

## Machine-contract mapping

| Contract concern | Runtime owner |
| --- | --- |
| Capability registration / discovery | `api/plan_generation_capabilities.py` |
| Direct 10K baseline qualification | `analysis/road_10k_baseline.py` + `api/road_10k_baseline.py` |
| Deterministic schedule generation | `analysis/road_10k_plan_generation.py` |
| Proposal persistence / replay / adoption revalidation | `api/road_10k_plan_generation.py` |
| Append-only audit tables | `db/models.py` + road 10K migration and merge-head snapshot migration |
| Canonical client request / response types | `web/src/types/api.ts` |
| Miniapp generated copy of canonical types | `miniapp/types/api.ts` via `miniapp/scripts/sync-types.cjs` |

## Inactive gate and safe fallback behavior

While the capability stays inactive:

- `PUT /api/settings` rejects new `performance_10k` goal writes with `GOAL_KIND_UNAVAILABLE`.
- Existing stored `performance_10k` config is preserved in the database, but `/api/settings`, `/api/goal`, and `/api/plan/generation/capabilities` all fall back to honest generic race/continuous presentation instead of leaking the inactive goal kind to clients.
- Web and miniapp mount no Road opt-in surface and reject the Road constraint schema even if stale discovery data contains it.
- The mounted route dependency fails closed with 404 before authentication or Road side effects; it is not an activation path.
- Road access, opt-in, readiness, generation, regeneration, and baseline routes return a private 404 before request-side effects.

Future activation authority, signer rotation, and signed-file-versus-database design are unresolved and intentionally absent.

## Required inputs and accepted baseline metadata

Direct 10K qualification keeps these persisted fields attached to the confirmation and snapshot rows:

- authoritative `completed_at` from the synced activity
- authoritative `elapsed_time_sec` from the synced activity
- synced `distance_km` metadata from the full activity (retained for provenance, never as a ± window cutoff)
- exact accepted `surface_or_protocol`
- exact `route_or_venue_identifier`
- explicit race / all-out intent (`response`)
- `assistance_status` (`unassisted | assisted | unknown_or_unreported`)
- `source_provider`

Qualification fails closed unless the response, timing, measured-distance confirmation, and accepted protocol line up with one of the reviewed direct-baseline forms:

1. `organized_outdoor_road_10k_race`
2. `standardized_outdoor_road_10k_time_trial`
3. `standardized_track_10k_time_trial`

`assistance_status` is required persisted metadata but is **not** an accept/reject policy by value.

## Inputs used by deterministic generation

Generation binds the reviewed input set into `Road10KGenerationInput`:

- policy / decision / digest identifiers
- current-goal or separate-purpose selection
- direct-baseline snapshot id, source, and evidence date
- eight completed weeks of running history
- split/sample `intensity_sources` provenance per activity
- reserved dates and athlete-stated constraints
- an ephemeral `v1:<sha256>` training-pattern reference and the reviewed event-context version

Readiness computes that training-pattern reference without writing. Generate
and regenerate recompute it under the owner plan-write lock and persist only
the matching aggregate snapshot in the proposal transaction. The generator
never uses activity `avg_power` for intensity provenance.

## Outputs, typed failures, and schedule rules

Success responses use the existing typed codes:

- `eligible_rolling_proposal`
- `eligible_taper_proposal`

Fail-closed readiness outcomes remain typed, including:

- `missing_or_stale_direct_baseline`
- `insufficient_recent_history`
- `limited_near_term_guidance`
- `limited_guidance_event_conflict`
- `adult_scope_or_constraints_unconfirmed`
- `contradictory_input`
- `no_schedule_within_envelope`
- `validation_failed`

Runtime responses map every accepted 10K result code to the contract-backed
typed fields `route_state`, `plan_returned`, and the applicable
`adoption_required`, `goal_remains_recorded`, or
`limited_guidance_returned` booleans. The web and miniapp plan-start flows use
those fields instead of prefix-matching success strings.

Notable reviewed implementation details:

- taper eligibility is anchored only to `(target_date - block_start).days`
- targets 8-14 days after block start produce taper proposals truncated to event eve
- targets >14 days remain normal rolling proposals
- every generated workout carries a truthful maximum-distance ceiling derived from `recent_maximum_session_distance_km`
- the proposal stays duration-based; it does **not** invent pace, power, or distance targets for easy / longest-easy / quality sessions
- `template_ids` only expose contract-backed quality template ids actually used in the generated block

## Provenance, audit, replay, and adoption revalidation

Append-only audit rows keep only the reviewed replay surface:

- selected purpose and goal revision fence
- baseline snapshot id + source
- owner-resolved immutable training-pattern snapshot reference
- normalized constraints
- selected quality template ids
- deterministic input hash / source revision
- stable result code + validation reason code

The dedicated training-pattern table stores exactly the seven reviewed history
aggregates (including latest-run date), bounded history/intensity/reservation
counts and fingerprints, schema/policy identifiers, canonical fingerprint,
owner, reference, and timestamp. It has no JSON column or raw-payload escape
hatch. It never stores activity ids, workout rows, reservation dates, targets,
samples, or narrative text. Database constraints make `(owner, version)`
idempotent, and database triggers reject updates while allowing owner deletion.

Idempotent replay reads only the immutable proposal, exact owner-scoped
training-pattern snapshot, and exact owner-scoped baseline snapshot. It never
rereads `Activity`, so source correction or deletion cannot rewrite history.
Missing, cross-owner, legacy, or invalid references fail closed with
`ROAD_10K_REGENERATE_REQUIRED`.

Adoption validates those persisted references first, then re-runs the current
server-derived input boundary. Any change to split/sample provenance, baseline
evidence, history, reservations, event context, or constraints changes the
source revision and requires regeneration. Managed delivery also rejects this
inactive policy at the delivery-service boundary, even if a caller bypasses the
route-level post-adoption trigger fence.

## Web and miniapp semantics

- Web is the canonical API-type source: `web/src/types/api.ts`
- Miniapp types are generated; do not hand-edit `miniapp/types/api.ts`
- The direct-10K confirm UI collects protocol, route/venue, assistance, timing, and measured-distance confirmation
- The 10K path exposes an optional benchmark note only; it does not reuse the 5K pilot-test UI
- Miniapp plan-start constructs the exact `Road10KConstraintsRequest` shape (`adult_confirmed`, `current_symptom_stop`, weekdays, weekly limit, max-session limit, unavailable dates, preferred longest-easy day, benchmark date`) and accepts `eligible_*` readiness / proposal unions

## Privacy-safe runtime and meta-eval signals

Allowed stable telemetry remains limited to:

- readiness / generation result codes
- validation reason codes
- policy / generator / decision versions
- proposal adoption / rejection / successor events

Do **not** add raw athlete text, workout payload bodies, target values, personal-context contents, or identifying cohort slices to telemetry.

## Explicit non-goals

This implementation intentionally does **not**:

- activate or roll out the road 10K capability
- add runtime config or ops changes
- change accepted science artifacts, digests, or SDR decisions
- auto-schedule the optional benchmark
- add pace / power / distance targets to duration-only workouts
- broaden accepted direct-baseline protocols beyond the reviewed organized road-race and standardized road/track time-trial forms
