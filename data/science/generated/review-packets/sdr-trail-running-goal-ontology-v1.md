# Science decision review packet: Represent trail goals with an explicit course-demand vector

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-trail-running-goal-ontology-v1`
- **Lifecycle:** `superseded`
- **Model version:** `trail-course-demand-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:cb53936289927d0f5f73268b5b6468e17a5b771532e2eaeee5c5c8781e541774`
- **Contract digest:** `sha256:e341c379d8f60a27ee5919beab4800721c96b79458c861237d6e14800cdcd752`
- **Required decision role:** `decision_approver`
- **Decision approval:** `github:dddtc2005` on `2026-09-03` ([source](https://github.com/praxys-run/praxys/pull/759#issuecomment-5527639012))
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the four proposed ontology and safety boundaries should be accepted while the two implementation and numeric decisions remain deferred. Approve the sheet as a unit or request changes by item ID.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `course-demand-schema` — Accept the versioned course-demand dimensions

- **Question:** Should every trail capability match trail_course_demand_v1 rather than a distance-only goal?
- **Proposed decision:** Require typed expected duration, distance, ascent, descent, grade distribution, technicality, altitude, environment, support, terrain access, downhill exposure, and fueling-practice fields with explicit provenance and unknown states.
- **Approval means:**
  - Trail goals retain the course dimensions needed for policy matching.
  - Course-derived, athlete-stated, observed, inferred, assumed, and unknown values remain distinguishable.
- **This does not authorize:**
  - A plan, dose, automatic route inference, implementation, or activation.

<details><summary>Traceability: 2 contract groups, 2 evidence claims</summary>

- **Contract groups covered:** `trail_course_demand_schema`, `trail_field_provenance`
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.uphill-downhill-demands-differ`

</details>

#### `material-unknowns` — Fail closed on material unknowns

- **Question:** Should a material unknown block the dependent capability match rather than be defaulted or replaced by a road assumption?
- **Proposed decision:** Return clarification_required when the athlete or verified course source can resolve the field, otherwise policy_unavailable or a separately reviewed bounded alternative. Never silently use a road plan.
- **Approval means:**
  - Known values remain usable without erasing uncertainty.
  - Material missingness is visible and action-oriented.
- **This does not authorize:**
  - Treating an unknown as zero, average, easy, road, or nontechnical.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `trail_unknown_and_materiality_policy`
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.technicality-and-downhill-vary-performance`

</details>

#### `distinct-slope-demands` — Preserve uphill, downhill, and technical demand separately

- **Question:** Should elevation loss, grade distribution, technicality, and downhill exposure remain distinct rather than being inferred from total gain?
- **Proposed decision:** Keep those dimensions separate and require exact policy support when any is material.
- **Approval means:**
  - Capability matching cannot collapse ascent and descent into one vertical number.
  - Heart rate or level pace cannot be the sole intensity representation for hilly demand.
- **This does not authorize:**
  - A universal ascent/descent equivalence, hiking threshold, or technicality dose.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `trail_distinct_demand_invariants`
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.technicality-and-downhill-vary-performance`, `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone`

</details>

#### `safety-claim-boundary` — Accept nonclinical claim and safety limits

- **Question:** Should the ontology prohibit medical inference, individual safety or finish guarantees, and activity-average-power intensity use?
- **Proposed decision:** Preserve those prohibitions and use activity splits or samples for any future intensity interpretation.
- **Approval means:**
  - Trail planning remains adult, nonclinical, suggestion-only, and uncertainty-aware.
- **This does not authorize:**
  - Diagnosis, treatment, clearance, injury prevention, finish probability, or performance guarantee.

<details><summary>Traceability: 1 contract group, 1 evidence claim</summary>

- **Contract groups covered:** `trail_science_and_safety_boundary`
- **Evidence claims:** `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`

</details>

### Decisions explicitly deferred

#### `exact-values-deferred` — Defer all exact ontology thresholds and conversions

- **Question:** Should grade bins, technicality scores, materiality thresholds, freshness windows, equivalence formulas, and safe progression values remain unaccepted?
- **Proposed decision:** Keep every exact behavior-driving threshold and conversion literal not_accepted until separately reviewed.
- **Approval means:**
  - Future policies must select and validate their own bounded values.
- **This does not authorize:**
  - Inferring, defaulting, or implementing any exact value.

<details><summary>Traceability: 2 contract groups, 2 evidence claims</summary>

- **Contract groups covered:** `trail_unknown_and_materiality_policy`, `trail_exact_values`
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`

</details>

#### `non-science-decisions-deferred` — Defer product, design, implementation, rollout, and delivery

- **Question:** Should all product visibility, interaction, storage, generator, provider, pilot, rollout, and activation choices stay outside this SDR?
- **Proposed decision:** Keep the contract inactive and require linked role-owned decisions and implementation review.
- **Approval means:**
  - Science constrains later work without assuming its authority.
- **This does not authorize:**
  - User exposure, data writes, plan generation, Garmin mapping, deployment, or activation.

<details><summary>Traceability: 1 contract group, 0 evidence claims</summary>

- **Contract groups covered:** `trail_non_science_authority_boundary`
- **Evidence claims:** _None; product or lifecycle boundary only_

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve trail_course_demand_v1 as the required science boundary for trail capability matching, including explicit field provenance and unknown states, separate uphill and downhill representation, and fail- closed behavior for material unknowns. I approve the prohibition on road fallback, universal distance/elevation conversion, activity-average-power intensity use, and personal performance or safety guarantees. This does not approve a generator, numeric dose, implementation, rollout, provider mapping, or runtime activation.

- **Decision approval:** `github:dddtc2005` on `2026-09-03` ([source](https://github.com/praxys-run/praxys/pull/759#issuecomment-5527639012))

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-trail-running-goal-ontology-v1`
- Digest: `sha256:cb53936289927d0f5f73268b5b6468e17a5b771532e2eaeee5c5c8781e541774`

> I approve trail_course_demand_v1 as the required science boundary for trail capability matching, including explicit field provenance and unknown states, separate uphill and downhill representation, and fail- closed behavior for material unknowns. I approve the prohibition on road fallback, universal distance/elevation conversion, activity-average-power intensity use, and personal performance or safety guarantees. This does not approve a generator, numeric dose, implementation, rollout, provider mapping, or runtime activation.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:cb53936289927d0f5f73268b5b6468e17a5b771532e2eaeee5c5c8781e541774","subject_id":"sdr-trail-running-goal-ontology-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If separately accepted by the evidence reviewer and decision approver, this record would define trail_course_demand_v1 as a science-owned ontology for exact capability matching. A trail goal records expected duration, distance, elevation gain and loss, grade distribution, technicality, maximum altitude, environmental demand, aid and external support, accessible training terrain, recent downhill exposure, and fueling-practice experience with source and uncertainty. Distance, gain, and event date alone are insufficient. Material unknowns produce clarification_required or policy_unavailable; they never select a road policy or invent equivalence. The record does not select thresholds, plan dose, a generator, product visibility, rollout, or Garmin behavior, and runtime remains inactive.

### Linked evidence

#### `trail-ontology.course-demand-is-multidimensional` — moderate

Trail-running performance and exposure are course-specific and multifactorial. Distance alone does not preserve elevation, grade, surface, technicality, altitude, environment, event format, or support.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `scheer-2020-off-road-definition`, `de-waal-2021-performance-review`, `pastor-2022-distance-determinants`, `scheer-2019-threshold-prediction`
- **Limitations:** The literature does not provide one validated machine-readable schema.; Performance associations do not establish individual plan dose.

#### `trail-ontology.uphill-downhill-demands-differ` — moderate

Uphill and downhill running impose different metabolic, biomechanical, and neuromuscular demands; total elevation gain cannot stand in for descent exposure or grade distribution.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `minetti-2002`, `bjorklund-2019-short-trail`, `lemire-2021-downhill-fatigue`, `lemire-2022-slope-energy-cost`
- **Limitations:** Studies use small, selected samples and specific grades.; Results do not validate a universal vertical conversion or progression rate.

#### `trail-ontology.technicality-and-downhill-vary-performance` — low

Technical terrain and downhill sections can materially change between- runner performance and mechanical exposure, so technicality and descent cannot be inferred safely from distance and gain alone.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `bjorklund-2019-short-trail`, `de-waal-2021-performance-review`, `genitrini-2024-race-stage`
- **Limitations:** Technicality measurement is inconsistent across studies.; The evidence does not establish an exact technical-terrain training dose.

#### `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone` — low

Rapidly changing slope can decouple heart rate and level-running pace from the metabolic and mechanical demands of hilly running; neither is a sufficient sole representation of course demand or training intensity.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `born-2017-hilly-intensity`, `lemire-2022-slope-energy-cost`
- **Limitations:** Small studies do not invalidate athlete-specific heart-rate or pace context in all settings.; NIRS findings do not authorize a consumer prescription.

#### `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose` — low

Direct trail-training evidence is small, and trail-injury evidence is heterogeneous and substantially observational. Neither establishes a universal safe downhill, vertical, technical-terrain, or weekly progression dose, an individualized injury probability, or an injury-prevention guarantee.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `drum-2023-trail-road-rct`, `viljoen-2022-risk-factors`
- **Limitations:** The randomized study found no significant group-by-time interactions.; Observational injury associations do not establish causal prevention rules.; This absence of a validated universal dose does not show that every exposure is equally appropriate.

### Reviewed parameters

#### `trail_course_demand_schema` — guardrail

- **Applies to:** trail_course_demand_v1
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.uphill-downhill-demands-differ`
- **Rationale:** The schema keeps evidence-relevant dimensions distinct; exact rubrics and materiality thresholds remain deferred.
- **Exact value:**

```json
{
  "fields": {
    "aid_and_support": {
      "material": true,
      "type": "object",
      "unit": "event_support_model"
    },
    "distance_meters": {
      "material": true,
      "minimum": 1,
      "type": "integer",
      "unit": "meters"
    },
    "elevation_gain_meters": {
      "material": true,
      "minimum": 0,
      "type": "integer",
      "unit": "meters"
    },
    "elevation_loss_meters": {
      "material": true,
      "minimum": 0,
      "type": "integer",
      "unit": "meters"
    },
    "environmental_demand": {
      "material": "conditional",
      "type": "object",
      "unit": "observed_or_expected_conditions"
    },
    "expected_duration_seconds": {
      "material": true,
      "minimum": 1,
      "type": "integer",
      "unit": "seconds"
    },
    "fueling_practice_experience": {
      "material": "conditional",
      "type": "categorical_object",
      "unit": "versioned_rubric"
    },
    "grade_distribution": {
      "material": true,
      "type": "object",
      "unit": "percent_of_course"
    },
    "maximum_altitude_meters": {
      "material": "conditional",
      "type": "integer",
      "unit": "meters_above_sea_level"
    },
    "recent_downhill_exposure": {
      "material": true,
      "type": "object",
      "unit": "observed_exposure_summary"
    },
    "technicality": {
      "material": true,
      "type": "categorical_object",
      "unit": "versioned_rubric"
    },
    "training_terrain_access": {
      "material": true,
      "type": "object",
      "unit": "accessible_demand_classes"
    }
  },
  "schema_id": "trail_course_demand_v1"
}
```

#### `trail_field_provenance` — guardrail

- **Applies to:** every trail_course_demand_v1 field
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Facts, statements, inferences, assumptions, and unknowns must not be collapsed because they carry different decision confidence.
- **Exact value:**

```json
{
  "allowed": [
    "course_verified",
    "athlete_stated",
    "history_observed",
    "model_inferred",
    "explicit_assumption",
    "unknown"
  ],
  "assumed_requires_athlete_confirmation": true,
  "inferred_requires_model_version": true,
  "source_timestamp_required_when_applicable": true,
  "unknown_is_preserved": true
}
```

#### `trail_unknown_and_materiality_policy` — guardrail

- **Applies to:** trail capability matching
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.technicality-and-downhill-vary-performance`
- **Rationale:** Failing closed prevents missing course data from becoming an implicit easier-course or road assumption while allowing explicit modular limits.
- **Exact value:**

```json
{
  "exact_materiality_thresholds": "not_accepted",
  "material_unknown_result": [
    "clarification_required",
    "policy_unavailable",
    "bounded_alternative_only_when_separately_reviewed"
  ],
  "module_specific_unknown_may_limit_only_dependent_module": true,
  "unknown_defaults_to_road": false,
  "unknown_defaults_to_zero": false
}
```

#### `trail_distinct_demand_invariants` — guardrail

- **Applies to:** trail ontology and future policy matching
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.technicality-and-downhill-vary-performance`, `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone`
- **Rationale:** Uphill, downhill, and technical terrain have different demands that one scalar or level-running signal cannot preserve.
- **Exact value:**

```json
{
  "ascent_and_descent_separate": true,
  "downhill_history_required_when_descent_material": true,
  "grade_distribution_required_when_material": true,
  "heart_rate_alone_sufficient_for_hilly_intensity": false,
  "level_pace_alone_sufficient_for_hilly_intensity": false,
  "technicality_required_when_material": true,
  "universal_distance_vertical_equivalence": false
}
```

#### `trail_science_and_safety_boundary` — guardrail

- **Applies to:** future trail capability decisions
- **Evidence claims:** `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`
- **Rationale:** Injury and training evidence does not establish a safe individual dose; the repository intensity invariant also excludes activity-average power.
- **Exact value:**

```json
{
  "activity_average_power_valid_for_intensity": false,
  "diagnosis_or_clearance": false,
  "minimum_age_years": 18,
  "nonclinical_only": true,
  "performance_or_injury_guarantee": false,
  "personal_finish_probability": false,
  "symptom_stop_required": true,
  "valid_intensity_sources": [
    "activity_splits",
    "activity_samples"
  ]
}
```

#### `trail_exact_values` — guardrail

- **Applies to:** unresolved ontology and future generation values
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`
- **Rationale:** The evidence supports keeping dimensions explicit, not universal numeric values or prescriptions.
- **Exact value:**

```json
{
  "distance_vertical_conversion": "not_accepted",
  "downhill_progression": "not_accepted",
  "grade_bins": "not_accepted",
  "history_freshness": "not_accepted",
  "materiality_thresholds": "not_accepted",
  "road_trail_equivalence": "not_accepted",
  "technical_terrain_dose": "not_accepted",
  "technicality_rubric": "not_accepted",
  "vertical_progression": "not_accepted"
}
```

#### `trail_non_science_authority_boundary` — guardrail

- **Applies to:** all non-science work
- **Evidence claims:** _None; product rationale only_
- **Rationale:** This SDR cannot authorize role-owned product, experience, implementation, rollout, or provider decisions.
- **Exact value:**

```json
{
  "deferred_to_design": [
    "clarification_journey",
    "review_experience",
    "accessibility",
    "copy"
  ],
  "deferred_to_engineering": [
    "storage",
    "api",
    "generator",
    "clients",
    "provider_delivery"
  ],
  "deferred_to_operations": [
    "owner_gate",
    "rollout",
    "activation",
    "monitoring"
  ],
  "deferred_to_product": [
    "visibility",
    "catalog",
    "opt_in",
    "outcome_metrics"
  ],
  "science_authority": [
    "evidence",
    "applicability",
    "uncertainty",
    "claim_limits",
    "safety_scope"
  ]
}
```

### Rejected alternatives

#### Represent a trail race with distance, ascent, and date only

This loses descent, grade, technicality, altitude, environment, support, expected duration, terrain access, and relevant prior exposure.

#### Convert trail distance and elevation into a road-equivalent distance

The reviewed evidence shows nonlinear and distinct slope-specific demands and does not validate one universal equivalence.

#### Treat missing technicality or descent as easy or zero

That would turn unknown course demand into an unsupported low-risk claim.

#### Let a generator or AI fill material unknowns

Generated assumptions cannot replace athlete confirmation or a verified course source and cannot broaden a reviewed capability.

### Applicability

- Adult nonclinical single-day trail-running goal representation
- Course-demand capture and exact capability matching before generation
- Evidence, uncertainty, claim limits, and safety scope only

### User-facing claim limits

- Do not claim distance and ascent alone describe trail demand.
- Do not claim a universal road-equivalent distance or ascent/descent conversion.
- Do not present unknown technicality, descent, environment, or support as easy, zero, or average.
- Do not present a personal finish probability, performance guarantee, injury-prevention guarantee, diagnosis, or clearance.

### Safety implications

- Missing material modifiers fail closed or return a separately reviewed bounded alternative.
- Uphill, downhill, technical terrain, altitude, and heat require distinct handling when material.
- Current symptoms stop performance optimization without creating a diagnosis.
- Intensity uses activity splits or samples, never activity-average power.

### Privacy implications

- Store the minimum normalized field value, provenance, uncertainty, and source reference needed for replay.
- Do not copy raw route files, activity samples, free text, or provider payloads into generic audit or telemetry.
- Athlete-stated and inferred fields remain correctable and deletable under existing account controls.

### Validation plan

- Validate every field type, unit, source category, and explicit unknown state deterministically.
- Replay matching with each material field unknown and verify no road policy or success-shaped plan is selected.
- Verify ascent and descent changes alter the course-demand digest independently.
- Verify activity-average power cannot satisfy intensity provenance.
- Generate matching review packet and inactive machine contract and bind later approvals to their exact digests.

### Falsification conditions

- A trail capability matches on distance alone or silently selects a road policy.
- An unknown material field is treated as zero, average, easy, nontechnical, or confirmed.
- Ascent and descent are collapsed or one universal conversion is presented as established.
- Activity-average power drives intensity or a personal safety, finish, or performance guarantee is shown.
- The generated contract becomes active without separate implementation review and activation authority.

### Decision notes

- This artifact-mode decision addresses issue #690 and remains draft and inactive.
- Work Contract classification digest: sha256:55c4da66e7f504dd0d40c681c2a006fdbe7079c0cd06de43cb95802e679f78f5.
- Work Contract route digest: sha256:2f237b07f7a41582707e1a647e69aa634749c487c258b555c559f80f98cfc160.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "trail_course_demand_v1 ontology",
    "trail capability matching contract"
  ],
  "contract_digest": "sha256:e341c379d8f60a27ee5919beab4800721c96b79458c861237d6e14800cdcd752",
  "decision_id": "sdr-trail-running-goal-ontology-v1",
  "decision_status": "superseded",
  "decision_version": 1,
  "evidence_claim_ids": [
    "trail-ontology.course-demand-is-multidimensional",
    "trail-ontology.uphill-downhill-demands-differ",
    "trail-ontology.technicality-and-downhill-vary-performance",
    "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
    "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
  ],
  "evidence_review_ids": [
    "evidence-trail-running-goal-ontology-v1"
  ],
  "linked_evidence_digests": {
    "evidence-trail-running-goal-ontology-v1": "sha256:60f0e785e4fc2b4226fed3bb30750191195cffbb0236b4a81d34431c0002c87a"
  },
  "model_version": "trail-course-demand-v1",
  "parameters": {
    "trail_course_demand_schema": {
      "applies_to": "trail_course_demand_v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.uphill-downhill-demands-differ"
      ],
      "value": {
        "fields": {
          "aid_and_support": {
            "material": true,
            "type": "object",
            "unit": "event_support_model"
          },
          "distance_meters": {
            "material": true,
            "minimum": 1,
            "type": "integer",
            "unit": "meters"
          },
          "elevation_gain_meters": {
            "material": true,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          },
          "elevation_loss_meters": {
            "material": true,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          },
          "environmental_demand": {
            "material": "conditional",
            "type": "object",
            "unit": "observed_or_expected_conditions"
          },
          "expected_duration_seconds": {
            "material": true,
            "minimum": 1,
            "type": "integer",
            "unit": "seconds"
          },
          "fueling_practice_experience": {
            "material": "conditional",
            "type": "categorical_object",
            "unit": "versioned_rubric"
          },
          "grade_distribution": {
            "material": true,
            "type": "object",
            "unit": "percent_of_course"
          },
          "maximum_altitude_meters": {
            "material": "conditional",
            "type": "integer",
            "unit": "meters_above_sea_level"
          },
          "recent_downhill_exposure": {
            "material": true,
            "type": "object",
            "unit": "observed_exposure_summary"
          },
          "technicality": {
            "material": true,
            "type": "categorical_object",
            "unit": "versioned_rubric"
          },
          "training_terrain_access": {
            "material": true,
            "type": "object",
            "unit": "accessible_demand_classes"
          }
        },
        "schema_id": "trail_course_demand_v1"
      }
    },
    "trail_distinct_demand_invariants": {
      "applies_to": "trail ontology and future policy matching",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.technicality-and-downhill-vary-performance",
        "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone"
      ],
      "value": {
        "ascent_and_descent_separate": true,
        "downhill_history_required_when_descent_material": true,
        "grade_distribution_required_when_material": true,
        "heart_rate_alone_sufficient_for_hilly_intensity": false,
        "level_pace_alone_sufficient_for_hilly_intensity": false,
        "technicality_required_when_material": true,
        "universal_distance_vertical_equivalence": false
      }
    },
    "trail_exact_values": {
      "applies_to": "unresolved ontology and future generation values",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "value": {
        "distance_vertical_conversion": "not_accepted",
        "downhill_progression": "not_accepted",
        "grade_bins": "not_accepted",
        "history_freshness": "not_accepted",
        "materiality_thresholds": "not_accepted",
        "road_trail_equivalence": "not_accepted",
        "technical_terrain_dose": "not_accepted",
        "technicality_rubric": "not_accepted",
        "vertical_progression": "not_accepted"
      }
    },
    "trail_field_provenance": {
      "applies_to": "every trail_course_demand_v1 field",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "allowed": [
          "course_verified",
          "athlete_stated",
          "history_observed",
          "model_inferred",
          "explicit_assumption",
          "unknown"
        ],
        "assumed_requires_athlete_confirmation": true,
        "inferred_requires_model_version": true,
        "source_timestamp_required_when_applicable": true,
        "unknown_is_preserved": true
      }
    },
    "trail_non_science_authority_boundary": {
      "applies_to": "all non-science work",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "deferred_to_design": [
          "clarification_journey",
          "review_experience",
          "accessibility",
          "copy"
        ],
        "deferred_to_engineering": [
          "storage",
          "api",
          "generator",
          "clients",
          "provider_delivery"
        ],
        "deferred_to_operations": [
          "owner_gate",
          "rollout",
          "activation",
          "monitoring"
        ],
        "deferred_to_product": [
          "visibility",
          "catalog",
          "opt_in",
          "outcome_metrics"
        ],
        "science_authority": [
          "evidence",
          "applicability",
          "uncertainty",
          "claim_limits",
          "safety_scope"
        ]
      }
    },
    "trail_science_and_safety_boundary": {
      "applies_to": "future trail capability decisions",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "diagnosis_or_clearance": false,
        "minimum_age_years": 18,
        "nonclinical_only": true,
        "performance_or_injury_guarantee": false,
        "personal_finish_probability": false,
        "symptom_stop_required": true,
        "valid_intensity_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    "trail_unknown_and_materiality_policy": {
      "applies_to": "trail capability matching",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.technicality-and-downhill-vary-performance"
      ],
      "value": {
        "exact_materiality_thresholds": "not_accepted",
        "material_unknown_result": [
          "clarification_required",
          "policy_unavailable",
          "bounded_alternative_only_when_separately_reviewed"
        ],
        "module_specific_unknown_may_limit_only_dependent_module": true,
        "unknown_defaults_to_road": false,
        "unknown_defaults_to_zero": false
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:cb53936289927d0f5f73268b5b6468e17a5b771532e2eaeee5c5c8781e541774"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If separately accepted by the evidence reviewer and decision approver, this record would define trail_course_demand_v1 as a science-owned ontology for exact capability matching. A trail goal records expected duration, distance, elevation gain and loss, grade distribution, technicality, maximum altitude, environmental demand, aid and external support, accessible training terrain, recent downhill exposure, and fueling-practice experience with source and uncertainty. Distance, gain, and event date alone are insufficient. Material unknowns produce clarification_required or policy_unavailable; they never select a road policy or invent equivalence. The record does not select thresholds, plan dose, a generator, product visibility, rollout, or Garmin behavior, and runtime remains inactive.",
  "affected_surfaces": {
    "apis": [
      "future plan-generation capability discovery and readiness contracts"
    ],
    "clients": [
      "future web, miniapp, plugin, and MCP trail goal clients"
    ],
    "models": [
      "trail_course_demand_v1 ontology",
      "trail capability matching contract"
    ],
    "science_notes": [
      "Why trail demand needs more than distance and ascent",
      "Why uphill and downhill are represented separately"
    ]
  },
  "applicability": [
    "Adult nonclinical single-day trail-running goal representation",
    "Course-demand capture and exact capability matching before generation",
    "Evidence, uncertainty, claim limits, and safety scope only"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-09-01",
  "decision_notes": [
    "This artifact-mode decision addresses issue #690 and remains draft and inactive.",
    "Work Contract classification digest: sha256:55c4da66e7f504dd0d40c681c2a006fdbe7079c0cd06de43cb95802e679f78f5.",
    "Work Contract route digest: sha256:2f237b07f7a41582707e1a647e69aa634749c487c258b555c559f80f98cfc160."
  ],
  "decision_review": {
    "approval_statement": "I approve trail_course_demand_v1 as the required science boundary for trail capability matching, including explicit field provenance and unknown states, separate uphill and downhill representation, and fail- closed behavior for material unknowns. I approve the prohibition on road fallback, universal distance/elevation conversion, activity-average-power intensity use, and personal performance or safety guarantees. This does not approve a generator, numeric dose, implementation, rollout, provider mapping, or runtime activation.",
    "items": [
      {
        "approval_effect": [
          "Trail goals retain the course dimensions needed for policy matching.",
          "Course-derived, athlete-stated, observed, inferred, assumed, and unknown values remain distinguishable."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A plan, dose, automatic route inference, implementation, or activation."
        ],
        "evidence_claim_ids": [
          "trail-ontology.course-demand-is-multidimensional",
          "trail-ontology.uphill-downhill-demands-differ"
        ],
        "id": "course-demand-schema",
        "parameter_names": [
          "trail_course_demand_schema",
          "trail_field_provenance"
        ],
        "proposed_decision": "Require typed expected duration, distance, ascent, descent, grade distribution, technicality, altitude, environment, support, terrain access, downhill exposure, and fueling-practice fields with explicit provenance and unknown states.",
        "question": "Should every trail capability match trail_course_demand_v1 rather than a distance-only goal?",
        "title": "Accept the versioned course-demand dimensions"
      },
      {
        "approval_effect": [
          "Known values remain usable without erasing uncertainty.",
          "Material missingness is visible and action-oriented."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Treating an unknown as zero, average, easy, road, or nontechnical."
        ],
        "evidence_claim_ids": [
          "trail-ontology.course-demand-is-multidimensional",
          "trail-ontology.technicality-and-downhill-vary-performance"
        ],
        "id": "material-unknowns",
        "parameter_names": [
          "trail_unknown_and_materiality_policy"
        ],
        "proposed_decision": "Return clarification_required when the athlete or verified course source can resolve the field, otherwise policy_unavailable or a separately reviewed bounded alternative. Never silently use a road plan.",
        "question": "Should a material unknown block the dependent capability match rather than be defaulted or replaced by a road assumption?",
        "title": "Fail closed on material unknowns"
      },
      {
        "approval_effect": [
          "Capability matching cannot collapse ascent and descent into one vertical number.",
          "Heart rate or level pace cannot be the sole intensity representation for hilly demand."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A universal ascent/descent equivalence, hiking threshold, or technicality dose."
        ],
        "evidence_claim_ids": [
          "trail-ontology.uphill-downhill-demands-differ",
          "trail-ontology.technicality-and-downhill-vary-performance",
          "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone"
        ],
        "id": "distinct-slope-demands",
        "parameter_names": [
          "trail_distinct_demand_invariants"
        ],
        "proposed_decision": "Keep those dimensions separate and require exact policy support when any is material.",
        "question": "Should elevation loss, grade distribution, technicality, and downhill exposure remain distinct rather than being inferred from total gain?",
        "title": "Preserve uphill, downhill, and technical demand separately"
      },
      {
        "approval_effect": [
          "Trail planning remains adult, nonclinical, suggestion-only, and uncertainty-aware."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Diagnosis, treatment, clearance, injury prevention, finish probability, or performance guarantee."
        ],
        "evidence_claim_ids": [
          "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
        ],
        "id": "safety-claim-boundary",
        "parameter_names": [
          "trail_science_and_safety_boundary"
        ],
        "proposed_decision": "Preserve those prohibitions and use activity splits or samples for any future intensity interpretation.",
        "question": "Should the ontology prohibit medical inference, individual safety or finish guarantees, and activity-average-power intensity use?",
        "title": "Accept nonclinical claim and safety limits"
      },
      {
        "approval_effect": [
          "Future policies must select and validate their own bounded values."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Inferring, defaulting, or implementing any exact value."
        ],
        "evidence_claim_ids": [
          "trail-ontology.uphill-downhill-demands-differ",
          "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
        ],
        "id": "exact-values-deferred",
        "parameter_names": [
          "trail_unknown_and_materiality_policy",
          "trail_exact_values"
        ],
        "proposed_decision": "Keep every exact behavior-driving threshold and conversion literal not_accepted until separately reviewed.",
        "question": "Should grade bins, technicality scores, materiality thresholds, freshness windows, equivalence formulas, and safe progression values remain unaccepted?",
        "title": "Defer all exact ontology thresholds and conversions"
      },
      {
        "approval_effect": [
          "Science constrains later work without assuming its authority."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "User exposure, data writes, plan generation, Garmin mapping, deployment, or activation."
        ],
        "evidence_claim_ids": [],
        "id": "non-science-decisions-deferred",
        "parameter_names": [
          "trail_non_science_authority_boundary"
        ],
        "proposed_decision": "Keep the contract inactive and require linked role-owned decisions and implementation review.",
        "question": "Should all product visibility, interaction, storage, generator, provider, pilot, rollout, and activation choices stay outside this SDR?",
        "title": "Defer product, design, implementation, rollout, and delivery"
      }
    ],
    "reviewer_task": "Decide whether the four proposed ontology and safety boundaries should be accepted while the two implementation and numeric decisions remain deferred. Approve the sheet as a unit or request changes by item ID."
  },
  "evidence_claim_ids": [
    "trail-ontology.course-demand-is-multidimensional",
    "trail-ontology.uphill-downhill-demands-differ",
    "trail-ontology.technicality-and-downhill-vary-performance",
    "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
    "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
  ],
  "evidence_review_ids": [
    "evidence-trail-running-goal-ontology-v1"
  ],
  "falsification_conditions": [
    "A trail capability matches on distance alone or silently selects a road policy.",
    "An unknown material field is treated as zero, average, easy, nontechnical, or confirmed.",
    "Ascent and descent are collapsed or one universal conversion is presented as established.",
    "Activity-average power drives intensity or a personal safety, finish, or performance guarantee is shown.",
    "The generated contract becomes active without separate implementation review and activation authority."
  ],
  "id": "sdr-trail-running-goal-ontology-v1",
  "model_parameters": [
    {
      "applies_to": "trail_course_demand_v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.uphill-downhill-demands-differ"
      ],
      "name": "trail_course_demand_schema",
      "rationale": "The schema keeps evidence-relevant dimensions distinct; exact rubrics and materiality thresholds remain deferred.",
      "value": {
        "fields": {
          "aid_and_support": {
            "material": true,
            "type": "object",
            "unit": "event_support_model"
          },
          "distance_meters": {
            "material": true,
            "minimum": 1,
            "type": "integer",
            "unit": "meters"
          },
          "elevation_gain_meters": {
            "material": true,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          },
          "elevation_loss_meters": {
            "material": true,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          },
          "environmental_demand": {
            "material": "conditional",
            "type": "object",
            "unit": "observed_or_expected_conditions"
          },
          "expected_duration_seconds": {
            "material": true,
            "minimum": 1,
            "type": "integer",
            "unit": "seconds"
          },
          "fueling_practice_experience": {
            "material": "conditional",
            "type": "categorical_object",
            "unit": "versioned_rubric"
          },
          "grade_distribution": {
            "material": true,
            "type": "object",
            "unit": "percent_of_course"
          },
          "maximum_altitude_meters": {
            "material": "conditional",
            "type": "integer",
            "unit": "meters_above_sea_level"
          },
          "recent_downhill_exposure": {
            "material": true,
            "type": "object",
            "unit": "observed_exposure_summary"
          },
          "technicality": {
            "material": true,
            "type": "categorical_object",
            "unit": "versioned_rubric"
          },
          "training_terrain_access": {
            "material": true,
            "type": "object",
            "unit": "accessible_demand_classes"
          }
        },
        "schema_id": "trail_course_demand_v1"
      }
    },
    {
      "applies_to": "every trail_course_demand_v1 field",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "trail_field_provenance",
      "rationale": "Facts, statements, inferences, assumptions, and unknowns must not be collapsed because they carry different decision confidence.",
      "value": {
        "allowed": [
          "course_verified",
          "athlete_stated",
          "history_observed",
          "model_inferred",
          "explicit_assumption",
          "unknown"
        ],
        "assumed_requires_athlete_confirmation": true,
        "inferred_requires_model_version": true,
        "source_timestamp_required_when_applicable": true,
        "unknown_is_preserved": true
      }
    },
    {
      "applies_to": "trail capability matching",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.technicality-and-downhill-vary-performance"
      ],
      "name": "trail_unknown_and_materiality_policy",
      "rationale": "Failing closed prevents missing course data from becoming an implicit easier-course or road assumption while allowing explicit modular limits.",
      "value": {
        "exact_materiality_thresholds": "not_accepted",
        "material_unknown_result": [
          "clarification_required",
          "policy_unavailable",
          "bounded_alternative_only_when_separately_reviewed"
        ],
        "module_specific_unknown_may_limit_only_dependent_module": true,
        "unknown_defaults_to_road": false,
        "unknown_defaults_to_zero": false
      }
    },
    {
      "applies_to": "trail ontology and future policy matching",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.technicality-and-downhill-vary-performance",
        "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone"
      ],
      "name": "trail_distinct_demand_invariants",
      "rationale": "Uphill, downhill, and technical terrain have different demands that one scalar or level-running signal cannot preserve.",
      "value": {
        "ascent_and_descent_separate": true,
        "downhill_history_required_when_descent_material": true,
        "grade_distribution_required_when_material": true,
        "heart_rate_alone_sufficient_for_hilly_intensity": false,
        "level_pace_alone_sufficient_for_hilly_intensity": false,
        "technicality_required_when_material": true,
        "universal_distance_vertical_equivalence": false
      }
    },
    {
      "applies_to": "future trail capability decisions",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "name": "trail_science_and_safety_boundary",
      "rationale": "Injury and training evidence does not establish a safe individual dose; the repository intensity invariant also excludes activity-average power.",
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "diagnosis_or_clearance": false,
        "minimum_age_years": 18,
        "nonclinical_only": true,
        "performance_or_injury_guarantee": false,
        "personal_finish_probability": false,
        "symptom_stop_required": true,
        "valid_intensity_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    {
      "applies_to": "unresolved ontology and future generation values",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "name": "trail_exact_values",
      "rationale": "The evidence supports keeping dimensions explicit, not universal numeric values or prescriptions.",
      "value": {
        "distance_vertical_conversion": "not_accepted",
        "downhill_progression": "not_accepted",
        "grade_bins": "not_accepted",
        "history_freshness": "not_accepted",
        "materiality_thresholds": "not_accepted",
        "road_trail_equivalence": "not_accepted",
        "technical_terrain_dose": "not_accepted",
        "technicality_rubric": "not_accepted",
        "vertical_progression": "not_accepted"
      }
    },
    {
      "applies_to": "all non-science work",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "trail_non_science_authority_boundary",
      "rationale": "This SDR cannot authorize role-owned product, experience, implementation, rollout, or provider decisions.",
      "value": {
        "deferred_to_design": [
          "clarification_journey",
          "review_experience",
          "accessibility",
          "copy"
        ],
        "deferred_to_engineering": [
          "storage",
          "api",
          "generator",
          "clients",
          "provider_delivery"
        ],
        "deferred_to_operations": [
          "owner_gate",
          "rollout",
          "activation",
          "monitoring"
        ],
        "deferred_to_product": [
          "visibility",
          "catalog",
          "opt_in",
          "outcome_metrics"
        ],
        "science_authority": [
          "evidence",
          "applicability",
          "uncertainty",
          "claim_limits",
          "safety_scope"
        ]
      }
    }
  ],
  "model_version": "trail-course-demand-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Store the minimum normalized field value, provenance, uncertainty, and source reference needed for replay.",
    "Do not copy raw route files, activity samples, free text, or provider payloads into generic audit or telemetry.",
    "Athlete-stated and inferred fields remain correctable and deletable under existing account controls."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Represent a trail race with distance, ascent, and date only",
      "rationale": "This loses descent, grade, technicality, altitude, environment, support, expected duration, terrain access, and relevant prior exposure."
    },
    {
      "alternative": "Convert trail distance and elevation into a road-equivalent distance",
      "rationale": "The reviewed evidence shows nonlinear and distinct slope-specific demands and does not validate one universal equivalence."
    },
    {
      "alternative": "Treat missing technicality or descent as easy or zero",
      "rationale": "That would turn unknown course demand into an unsupported low-risk claim."
    },
    {
      "alternative": "Let a generator or AI fill material unknowns",
      "rationale": "Generated assumptions cannot replace athlete confirmation or a verified course source and cannot broaden a reviewed capability."
    }
  ],
  "safety_implications": [
    "Missing material modifiers fail closed or return a separately reviewed bounded alternative.",
    "Uphill, downhill, technical terrain, altitude, and heat require distinct handling when material.",
    "Current symptoms stop performance optimization without creating a diagnosis.",
    "Intensity uses activity splits or samples, never activity-average power."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Represent trail goals with an explicit course-demand vector",
  "user_facing_claim_limits": [
    "Do not claim distance and ascent alone describe trail demand.",
    "Do not claim a universal road-equivalent distance or ascent/descent conversion.",
    "Do not present unknown technicality, descent, environment, or support as easy, zero, or average.",
    "Do not present a personal finish probability, performance guarantee, injury-prevention guarantee, diagnosis, or clearance."
  ],
  "validation_plan": [
    "Validate every field type, unit, source category, and explicit unknown state deterministically.",
    "Replay matching with each material field unknown and verify no road policy or success-shaped plan is selected.",
    "Verify ascent and descent changes alter the course-demand digest independently.",
    "Verify activity-average power cannot satisfy intensity provenance.",
    "Generate matching review packet and inactive machine contract and bind later approvals to their exact digests."
  ],
  "version": 1
}
```

</details>
