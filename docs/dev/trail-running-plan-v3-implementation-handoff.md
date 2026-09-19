# Trail v3 implementation impact map and handoff

> Historical scope and execution status are preserved below. The authorized
> successor tracking/draft-PR work is recorded in the
> [universal Trail program handoff](trail-running-program-delivery.md).
> This earlier record does not cover same-day sessions, daily mode, 50 km or a full cycle.

**Status: draft review-package implementation; runtime inactive.**
Owner: Engineering. This is implementation evidence, not independent Quality,
specialist acceptance or human approval. The parent coordinator owns the fresh
Quality and Decision Review handoff. No commit, push, merge or deployment is
authorized or performed by this implementation record.

## Governing inputs

The [exact Work Contract](trail-running-plan-v3-exact-work-contract.json) has
classification `sha256:d2b15692d6d8db1b897b750ce30d6418e9a62e1acf683a4e88fce8f4a7851668`
and route `sha256:172191b42862f63e1368bb23496cb773b1fb7a8e8cd5e1ed2c413b080a5adb72`.
Product leads; Science, Design, Architecture and Trust contribute; Engineering
executes; independent Quality verifies. Decision Review remains required.

Inputs are the Product/Design/Architecture/Trust v3 drafts linked from the
[Chinese review sheet](trail-running-plan-v3-review-sheet.md), the new incremental
Evidence Review, and the two draft/inactive Science contracts. Their canonical
source and contract digests are recorded in that sheet and compiler pins.
Only the new ontology's structural calendar, anti-abuse numeric and activity/
resource mapping fields were aligned to the supplied Architecture/Trust drafts.
No new scientific dose was originated by Engineering.

## Impact map

| Layer | Implemented in this package | Remaining implementation |
| --- | --- | --- |
| Science artifacts | New Evidence Review/manifest, two draft SDRs, generated contracts/packets/index; inherited v2 bytes unchanged | Human exact-content review; any revised policy must regenerate/rebind |
| Analysis | Explicit canonical compiler; immutable context; bounded raw parser; date resource resolver; exact local module/collection checks | General running qualification, course materiality, observed outdoor budgets, full scheduler and stop/taper handling |
| Data and pipeline | No DB, migration, sync or history changes | Genuine descent/footing observations and coverage; versioned provenance; no inferred zero or ascent-to-descent conversion |
| API/service | No route, capability, generator or production DTO wiring | Owner actor fences, schema negotiation, revision-bound save/confirm/generate/adopt and transactional snapshots/audit |
| Workouts/storage | Separate offline candidate schema and explicit goal/actual activity | Versioned strength/treadmill workout storage, `WorkoutV1` compatibility, calendar/export/PlanRevision semantics; one workout/day |
| Web/miniapp | Experience specification only; existing UI untouched | Accepted component implementation, bilingual complete states, Web continuation for miniapp, rendered/accessibility verification |
| Trust/rights | Closed pure input and receipt boundary only | Current namespace, goal snapshot, proposal, audit, `PlanRevision.proposal_snapshot`, caches and unknown-schema read/export/delete; reset distinction |
| Operations/providers | No runtime configuration, Statsig change, deployment or provider I/O | Existing-SDK owner gate, disabled-state rights, activation attestation, rollout/rollback evidence and verified provider fence |
| Tests | Pure parser/resource/template/compiler regressions plus existing science and Trail suites | Independent Quality and future authenticated/storage/race/provider/rendered acceptance |

## Exact local meaning of validation

`validate_training_context` accepts raw text/bytes with a separately injected
trusted calendar and compiled review contract. Missing values remain explicit
unknowns; malformed known values fail. Invalid new/edit context returns a closed
receipt with no context. Expired stored rights do not use this new/edit parser.

`resolve_resource_availability` evaluates one rule per kind on requested dates,
with whole-value date overrides. It expands at most 14 proposal or 56 review
days while retaining an event-length rule. Presets imply no availability.

Single and collection candidate checks bind exact date, resource, template and
activity mapping; gym validates every exercise/set/rep/rest/load rule and reserved
duration, and treadmill validates every step plus machine capability. A template
ID also resolves the SDR warmup and execution cues; this is not a production
workout serializer. Collections add duplicate-day and simultaneous novel gym/
incline rejection. They do not search dates, replace training or qualify history.

All `review_valid` receipts contain `offline_review_only`, `runtime_inactive`,
`history_and_course_not_evaluated`, `schedule_and_exposure_budgets_not_evaluated`
and `adoption_not_authorized`. A local candidate mismatch is `review_invalid`;
future proposal composition must translate missing module prerequisites into
the accepted limited/omitted experience without presenting a complete plan.
This receipt cannot satisfy a runtime readiness or adoption gate.

## Future dependency sequence

1. Review and accept the exact new Product/Design/Science/Architecture/Trust
   boundaries via Decision Review. Revisions change the bound digests; no v2
   approval is reused and no predecessor is automatically superseded.
2. Add source coverage for real descent/footing and separate observed, stated,
   unknown and no-recorded exposure. Implement course/history/applicability and
   all overlapping outdoor budget windows. Do not claim gym/treadmill equivalence.
3. Implement the joint scheduler and versioned stored workout contract with
   running-only intensity accounting, time reserves, all spacing, single-session
   days, history caps and explicit unplaced content when capacity is insufficient.
4. Implement owner-isolated persistence, versioned current context, immutable
   generation snapshot/proposal/audit transaction, exact revision adoption
   fences, resource-change invalidation and successor adoption affecting only
   future uncompleted work. Include all rights surfaces and unknown schemas.
5. Implement the accepted UI and test rendered desktop/mobile, English/Chinese,
   accessibility and edge states through UI Quality/Impeccable. Do not treat a
   source specification or API fixture as visual verification.
6. Independently verify actor, history/schedule, snapshot/adoption races, data
   rights, gate-off behavior and zero provider calls. Reuse existing Statsig
   identity only; no Trail attributes, value telemetry or implicit gate enablement.
7. Obtain exact activation attestation and Operations release/rollback evidence
   under the required later Work Contract. A review-package acceptance is not
   an activation switch, owner pilot or production-data authorization.

The authorized future Product outcome is a completed owner 14-day generate/adopt
journey and seven-day review with active feedback on unexecutable sessions;
efficacy and safety conclusions are outside that observation.

## Development verification record

Engineering runs the new context/candidate tests plus evidence registry,
generated science artifacts, science approval workflow, existing non-ultra core,
Trail service/routes and general workout regressions. Exact commands/results
are recorded below. These are executor development checks; independent Quality
evidence is separately owned.

On 2026-09-08, using the shared repository Python environment:

- `pytest tests/test_trail_training_context.py tests/test_evidence_registry.py
  tests/test_science_artifacts.py tests/test_science_approval_workflow.py
  tests/test_non_ultra_trail_plan_generation.py tests/test_plan_workout_structure.py
  -q`: **232 passed**. A later compiler malformed-YAML rejection case is covered
  by the final targeted rerun.
- `pytest tests/test_trail_plan_service.py tests/test_trail_plan_routes.py
  tests/test_trail_api_contract_fixture.py tests/test_plan_generation_capabilities.py
  tests/test_outdoor_5k_plan_generation.py tests/test_road_10k_plan_generation.py
  -q`: **172 passed**, with existing deprecation warnings.
- Initial implementation targeted `pytest tests/test_trail_training_context.py
  -q`: **103 passed** after malformed-source hardening. At that revision the
  combined selected scope had 405 distinct cases; reruns are not additional
  independent evidence. The later Quality-requested changes are recorded below.
- Both generated science artifacts/index `--check` commands and `git diff
  --check` passed. No UI runtime or independent Quality pass is claimed here.

`generate_science_artifacts.py --check` and
`generate_science_registry_index.py --check` must pass after final artifact edits.

## Independent Quality findings and executor correction

The parent coordinator reported fresh independent Quality as
**CHANGES_REQUESTED**, with two P2 compiler-boundary findings:

1. Deeply nested canonical YAML or generated JSON could escape as a built-in
   `RecursionError` instead of the closed `contract_unavailable` error.
2. The shared canonical loader's Pydantic normalization could accept raw
   `schema_version: true` or `decision_version: "3"` / `3.0`, preserving the
   expected normalized digest despite the wrong raw types.

Engineering changed only the new compiler and its tests. Compilation now reads
the generated JSON strictly, rejects duplicate keys (including NFC collisions)
and nonfinite numbers, and compares the complete raw and canonical JSON trees
with exact Python types before checking the pins. Float parsing also rejects
decimal information lost to binary-float rounding. Recursion and numeric-parser
errors are converted to the same closed error without source content. The shared
loader, v2 files, Science SDRs, generated scientific artifacts and all scientific
digests are unchanged.

Regression cases reproduce deep YAML/JSON, coercion in both new contracts,
duplicates/NFC collisions, nonfinite and extreme numeric tokens, concealed
float rounding and unchanged raw positive contracts. These are executor
development checks. Independent Quality must re-review the corrected version;
the initial review's other checks do not constitute acceptance of this correction.
The parent coordinator stopped the earlier full-preflight snapshot (exit 130)
and will recreate it; no result from that interrupted run is claimed here.

Correction verification on 2026-09-08: final `pytest
tests/test_trail_training_context.py -q` **121 passed** in 33.56 seconds.
Generated science artifacts/index `--check` and `git diff --check` also passed.
The corrected compiler SHA-256 is
`45ab399ed5e3a978be5cfa36f92d6b4bd65b94f4edd8da675e8fce1711d056d6`.

The user's untracked `paseo.json` is retained. v2 source/approval/contracts,
API/frontend/provider/deploy files must remain byte-stable. Future work must not
hide that file or turn this draft package into a release claim.
