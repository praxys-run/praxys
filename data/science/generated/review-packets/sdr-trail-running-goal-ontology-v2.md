# Science decision review packet: Define the strict v2 Trail course-demand and constraint envelope

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-trail-running-goal-ontology-v2`
- **Lifecycle:** `draft`
- **Model version:** `trail-course-demand-v2`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:73dd653f8637004ff2ab3a754c3e775225eaf9faa79ccc52c97de3c3dbbf0b7c`
- **Contract digest:** `sha256:1297f713b992822335978dac92cfaa9b968b092d4ff6869ad73baa3d94ee2e7a`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the six proposed v2 ontology actions preserve the accepted v1 evidence, uncertainty, safety, and privacy boundaries while making the inactive input contract deterministic enough to implement. Approve the sheet as a unit or request changes by item ID.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `strict-value-provenance-envelope` — Adopt explicit field states and server-owned provenance

- **Question:** Should every reviewable v2 field use an exact known-or-unknown envelope while provenance, source metadata, and history hashes remain server-owned and revision-bound?
- **Proposed decision:** Accept the closed envelope, provenance categories, field-specific provenance restrictions, immutable revisions, and confirmation invalidation rules as operational guardrails.
- **Approval means:**
  - Missing values cannot be represented as zero, empty text, or a client-selected source.
  - Readiness and proposals can bind the exact confirmed source revisions used.
- **This does not authorize:**
  - Source scraping, route inference, model truth claims, or automatic confirmation.

<details><summary>Traceability: 2 contract groups, 1 evidence claim</summary>

- **Contract groups covered:** `trail_field_provenance`, `trail_revision_and_confirmation`
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`

</details>

#### `core-course-and-planning-context` — Adopt the v2 core course tuple and planning-duration range

- **Question:** Should event identity, date, distance, ascent, descent, scope, intent, hazard gates, and a confirmed planning-duration range be core inputs?
- **Proposed decision:** Require those typed fields and treat planning duration only as athlete-confirmed planning context, never as a finish-time prediction.
- **Approval means:**
  - Distance and ascent alone cannot select a Trail policy.
  - A material core unknown prevents an eligible proposal.
- **This does not authorize:**
  - A finish-time estimate, feasibility verdict, performance promise, or course equivalence.

<details><summary>Traceability: 2 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `trail_course_demand_schema`, `trail_planning_duration_range`
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.duration-and-fueling-practice-are-context`

</details>

#### `descriptive-course-and-access-vocabularies` — Adopt descriptive grade, footing, hazard, and terrain-access DTOs

- **Question:** Should v2 use the exact five signed-grade share buckets, six unordered footing flags, two known-or-unknown boolean hazard fields, and bounded schedule plus uphill/downhill/footing access fields?
- **Proposed decision:** Accept these closed DTOs and exact set-containment rules as deterministic descriptions, not as technicality scores or doses.
- **Approval means:**
  - Grade boundaries and footing matching replay identically.
  - Course footing cannot be approximated by synonyms or a road category.
- **This does not authorize:**
  - Route-derived grade, a technical score, downhill dose, or terrain equivalence.

<details><summary>Traceability: 3 contract groups, 2 evidence claims</summary>

- **Contract groups covered:** `trail_grade_distribution`, `trail_footing_and_hazard_contract`, `trail_training_constraints_schema`
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.technicality-and-downhill-vary-performance`

</details>

#### `bounded-context-and-materiality` — Adopt bounded optional context and exact block-versus-limit rules

- **Question:** Should environment, altitude, aid, equipment, fueling, and gastrointestinal context use closed bounded shapes, with only named non-core unknowns limiting dependent modules?
- **Proposed decision:** Accept the bounded shapes, exact core/limited mapping, sorted module vocabulary, and course-footing containment against access and observed history.
- **Approval means:**
  - Optional unknowns remain visible without becoming hidden defaults.
  - A known mismatch still blocks the affected core access or history gate.
- **This does not authorize:**
  - An environment, altitude, equipment, fueling, gastrointestinal, or safety prescription.

<details><summary>Traceability: 3 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `trail_optional_context_shapes`, `trail_unknown_and_materiality_policy`, `trail_distinct_demand_invariants`
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.environment-and-altitude-are-distinct-context`, `trail-ontology.duration-and-fueling-practice-are-context`

</details>

#### `science-safety-and-privacy-boundary` — Preserve the accepted nonclinical, intensity, claim, and privacy limits

- **Question:** Should v2 preserve the adult nonclinical scope, symptom stop, split/sample intensity provenance, minimum normalized storage, and all prohibitions on personal guarantees and sensitive planning payloads?
- **Proposed decision:** Carry the accepted v1 boundaries forward unchanged and apply them to every v2 field, receipt, and later implementation surface.
- **Approval means:**
  - Activity-average power cannot satisfy intensity provenance.
  - Route, GPS, free-text, diagnosis, and provider payloads remain outside the contract.
- **This does not authorize:**
  - Diagnosis, clearance, treatment, injury prevention, safety assurance, or personal performance prediction.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `trail_science_safety_and_privacy_boundary`
- **Evidence claims:** `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`

</details>

### Decisions explicitly deferred

#### `unresolved-values-and-authority-deferred` — Keep dose, scoring, equivalence, provider, and activation decisions deferred

- **Question:** Should every technicality score, route inference, dose, progression, equivalence, prediction, provider, rollout, and activation behavior remain unaccepted?
- **Proposed decision:** Preserve literal not_accepted values and the inactive role boundary until separate specialist and human review authorizes a successor.
- **Approval means:**
  - Exact DTO validation cannot silently become scientific prescription or runtime authority.
- **This does not authorize:**
  - Any behavior listed as not_accepted or any lifecycle transition for v1.

<details><summary>Traceability: 2 contract groups, 1 evidence claim</summary>

- **Contract groups covered:** `trail_exact_values`, `trail_non_science_authority_boundary`
- **Evidence claims:** `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve trail_course_demand_v2 and non_ultra_trail_constraints_v2 as strict revision-bound Trail planning envelopes: explicit known or unknown fields, server-owned provenance, separate ascent and descent, descriptive signed-grade shares, closed footing and known-or-unknown boolean hazard fields, exact footing containment, bounded schedule and optional context, and fail-closed core materiality. I approve the exact DTO values only as reversible Praxys operational guardrails, not as published biological findings, difficulty or safety scores, doses, equivalences, or predictions. This approval authorizes only preparation and review of a separately reviewed inactive implementation bound to this exact decision and contract. It does not approve lifecycle supersession, merge, deployment, production data use, dogfood, catalog visibility, provider behavior, delivery, or runtime activation.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-trail-running-goal-ontology-v2`
- Digest: `sha256:73dd653f8637004ff2ab3a754c3e775225eaf9faa79ccc52c97de3c3dbbf0b7c`

> I approve trail_course_demand_v2 and non_ultra_trail_constraints_v2 as strict revision-bound Trail planning envelopes: explicit known or unknown fields, server-owned provenance, separate ascent and descent, descriptive signed-grade shares, closed footing and known-or-unknown boolean hazard fields, exact footing containment, bounded schedule and optional context, and fail-closed core materiality. I approve the exact DTO values only as reversible Praxys operational guardrails, not as published biological findings, difficulty or safety scores, doses, equivalences, or predictions. This approval authorizes only preparation and review of a separately reviewed inactive implementation bound to this exact decision and contract. It does not approve lifecycle supersession, merge, deployment, production data use, dogfood, catalog visibility, provider behavior, delivery, or runtime activation.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:73dd653f8637004ff2ab3a754c3e775225eaf9faa79ccc52c97de3c3dbbf0b7c","subject_id":"sdr-trail-running-goal-ontology-v2","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If separately accepted by the decision approver, this successor would keep every accepted v1 science and safety boundary while defining trail_course_demand_v2 and non_ultra_trail_constraints_v2 as strict, provider-neutral, revision-bound data contracts. Reviewable fields carry an explicit known value or explicit unknown state; the server, never the client, stamps provenance and source revisions. Core course, scope, hazard, schedule, terrain-access, symptom, and recent-history gates fail closed. Unknown grade, ordinary course footing, environment, support, or fueling context can limit only their named module after all core gates pass. Five signed-grade basis-point buckets, six unordered footing flags, known-or- unknown boolean hazard fields, exact footing set containment, bounded schedule capacity, and bounded optional context are reversible Praxys operational guardrails, not validated difficulty scores, training doses, equivalence formulas, predictions, or safety thresholds. No route, GPS, free-text planning, provider payload, activity-average power, road fallback, personal performance prediction, or runtime behavior is accepted.

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

#### `trail-ontology.environment-and-altitude-are-distinct-context` — low

Heat exposure depends on multiple environmental and athlete factors, while acute altitude can reduce aerobic capacity in controlled endurance protocols. Expected environment and maximum altitude are therefore distinct context dimensions; the evidence does not validate a personal trail pace correction, acclimation schedule, or safety threshold.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `periard-2021`, `wehrlin-2006-altitude`
- **Limitations:** The evidence is not a direct validation of a trail-course matching schema.; Controlled acute-altitude findings do not establish self-paced trail performance effects.; Heat response varies with metabolic rate, clothing, wind, solar load, acclimation, and individual context.

#### `trail-ontology.duration-and-fueling-practice-are-context` — moderate

Endurance carbohydrate strategy varies with expected exercise duration, feeding opportunity, and prior tolerance. Repeated feeding practice may reduce gastrointestinal problems in some protocols, but distance alone does not establish a personal fueling amount, timing rule, tolerance, or performance benefit.

- **Evidence Review:** `evidence-trail-running-goal-ontology-v1`
- **Sources:** `burke-2011`, `martinez-2023`
- **Limitations:** The evidence is broader endurance evidence rather than a trail-course ontology validation.; Reviewed protocols, carbohydrate forms, event durations, and populations vary.; Practice does not guarantee individual gastrointestinal tolerance or performance.

### Reviewed parameters

#### `trail_course_demand_schema` — guardrail

- **Applies to:** trail_course_demand_v2
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.uphill-downhill-demands-differ`
- **Rationale:** The evidence supports explicit distinct dimensions; field names, types, units, and the core/limited representation are reversible Praxys DTO choices selected to make missingness and replay unambiguous.
- **Exact value:**

```json
{
  "event_identity": {
    "client_writable": false,
    "field": "event_id",
    "materiality": "core",
    "type": "server_owned_identifier"
  },
  "fields": {
    "aid_and_support": {
      "envelope": "known_or_unknown",
      "limited_module": "fueling",
      "materiality": "limited",
      "type": "bounded_object"
    },
    "course_footing": {
      "envelope": "known_or_unknown",
      "limited_module": "technical_terrain",
      "materiality": "limited_with_core_matching_when_known",
      "type": "nonempty_unordered_closed_set"
    },
    "distance_family": {
      "allowed": [
        "non_ultra"
      ],
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "closed_enum"
    },
    "distance_meters": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "maximum": 49999,
      "minimum": 1,
      "type": "integer",
      "unit": "meters"
    },
    "environment_and_altitude": {
      "envelope": "known_or_unknown",
      "limited_module": "environment_altitude",
      "materiality": "limited",
      "type": "bounded_object"
    },
    "event_date": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "iso_date"
    },
    "event_format": {
      "allowed": [
        "single_day"
      ],
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "closed_enum"
    },
    "fixed_rope": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "strict_boolean"
    },
    "fueling_and_gastrointestinal_context": {
      "envelope": "known_or_unknown",
      "limited_module": "fueling",
      "materiality": "limited",
      "type": "bounded_object"
    },
    "grade_distribution": {
      "envelope": "known_or_unknown",
      "limited_module": "grade_specificity",
      "materiality": "limited",
      "type": "five_bucket_basis_point_object"
    },
    "hands_assist": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "strict_boolean"
    },
    "planning_duration_range": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "integer_range",
      "unit": "minutes"
    },
    "planning_intent": {
      "allowed": [
        "performance"
      ],
      "envelope": "known_or_unknown",
      "materiality": "core",
      "type": "closed_enum"
    },
    "total_ascent_m": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "maximum": 20000,
      "minimum": 0,
      "type": "integer",
      "unit": "meters"
    },
    "total_descent_m": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "maximum": 20000,
      "minimum": 0,
      "type": "integer",
      "unit": "meters"
    }
  },
  "schema_id": "trail_course_demand_v2",
  "strict_unknown_fields_rejected": true
}
```

#### `trail_field_provenance` — guardrail

- **Applies to:** every reviewable v2 course, constraint, and history field
- **Evidence claims:** _None; product rationale only_
- **Rationale:** A strict server-owned provenance envelope prevents client-selected trust, hidden defaults, and stale source metadata. These are operational integrity controls, not published scientific values.
- **Exact value:**

```json
{
  "assumption_requires_revision_bound_confirmation": true,
  "client_may_submit_history_hash": false,
  "client_may_submit_model_version": false,
  "client_may_submit_provenance": false,
  "client_may_submit_source_revision": false,
  "client_may_submit_source_timestamp": false,
  "field_restrictions": {
    "athlete_assumption_conditions": [
      "explicit_assumption"
    ],
    "event_id": "server_owned",
    "grade_distribution": [
      "athlete_stated",
      "course_verified",
      "unknown"
    ],
    "recent_history": [
      "history_observed"
    ]
  },
  "inferred_requires_server_model_version": true,
  "request_envelope": {
    "arbitrary_object_invalid": true,
    "empty_string_invalid": true,
    "guessed_zero_invalid": true,
    "known": {
      "exact_keys": [
        "state",
        "value"
      ],
      "schema_valid_value_required": true,
      "state_literal": "known"
    },
    "missing_state_invalid": true,
    "null_invalid_except_explicit_aid_gap_case": true,
    "numeric_values_must_be_finite": true,
    "sentinel_number_invalid": true,
    "unknown": {
      "exact_keys": [
        "state"
      ],
      "state_literal": "unknown",
      "value_forbidden": true
    }
  },
  "server_stamped_provenance_allowed": [
    "athlete_stated",
    "course_verified",
    "history_observed",
    "model_inferred",
    "explicit_assumption",
    "unknown"
  ],
  "unknown_is_preserved": true
}
```

#### `trail_planning_duration_range` — guardrail

- **Applies to:** trail_course_demand_v2 core confirmation
- **Evidence claims:** `trail-ontology.duration-and-fueling-practice-are-context`
- **Rationale:** Expected duration is relevant context, while the exact range shape is a reversible Product DTO and cannot be presented as a prediction.
- **Exact value:**

```json
{
  "athlete_confirmed": true,
  "feasibility_verdict": false,
  "field": "planning_duration_range",
  "finish_time_prediction": false,
  "minimum_and_maximum_each": {
    "maximum": 1440,
    "minimum": 1
  },
  "minimum_strictly_less_than_maximum": true,
  "performance_promise": false,
  "purpose": "planning_context",
  "unit": "integer_minutes"
}
```

#### `trail_grade_distribution` — guardrail

- **Applies to:** known grade_distribution in trail_course_demand_v2
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`
- **Rationale:** Literature supports keeping signed grade demand explicit but does not validate these exact bins. The half-open intervals and basis-point sum are reversible deterministic description guardrails only.
- **Exact value:**

```json
{
  "allowed_provenance": [
    "athlete_stated",
    "course_verified"
  ],
  "buckets": {
    "below_neg_10": {
      "interval": "g < -10%",
      "upper_bound_percent": -10,
      "upper_inclusive": false
    },
    "neg_10_to_below_neg_3": {
      "interval": "-10% <= g < -3%",
      "lower_bound_percent": -10,
      "lower_inclusive": true,
      "upper_bound_percent": -3,
      "upper_inclusive": false
    },
    "neg_3_to_below_pos_3": {
      "interval": "-3% <= g < 3%",
      "lower_bound_percent": -3,
      "lower_inclusive": true,
      "upper_bound_percent": 3,
      "upper_inclusive": false
    },
    "pos_10_and_above": {
      "interval": "g >= 10%",
      "lower_bound_percent": 10,
      "lower_inclusive": true
    },
    "pos_3_to_below_pos_10": {
      "interval": "3% <= g < 10%",
      "lower_bound_percent": 3,
      "lower_inclusive": true,
      "upper_bound_percent": 10,
      "upper_inclusive": false
    }
  },
  "descriptive_only": true,
  "difficulty_score": false,
  "each_share_minimum": 0,
  "each_share_type": "integer",
  "equivalence_or_prediction_input": false,
  "exact_sum": 10000,
  "known_value_exact_keys": [
    "below_neg_10",
    "neg_10_to_below_neg_3",
    "neg_3_to_below_pos_3",
    "pos_3_to_below_pos_10",
    "pos_10_and_above"
  ],
  "ordering_semantic": false,
  "route_or_model_inference": false,
  "safety_threshold": false,
  "unit": "basis_points_of_course_distance",
  "workout_dose_input": false
}
```

#### `trail_footing_and_hazard_contract` — guardrail

- **Applies to:** course, access, and observed-history footing plus v2 hazard gates
- **Evidence claims:** `trail-ontology.technicality-and-downhill-vary-performance`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`
- **Rationale:** Footing and hazards must remain explicit, but the exact vocabulary and gates are Product-selected operational categories rather than validated technicality or safety scores.
- **Exact value:**

```json
{
  "hazard_gates": {
    "fixed_rope": {
      "eligible_value": "known_false",
      "envelope": "known_or_unknown",
      "known_true_result": "policy_unavailable.technical_features_outside_v2",
      "known_value_type": "strict_boolean",
      "unknown_result": "clarification_required.material_course_demand_unknown"
    },
    "hands_assist": {
      "eligible_value": "known_false",
      "envelope": "known_or_unknown",
      "known_true_result": "policy_unavailable.technical_features_outside_v2",
      "known_value_type": "strict_boolean",
      "unknown_result": "clarification_required.material_course_demand_unknown"
    },
    "reducible_to_ordinary_footing": false,
    "technical_skill_or_safety_score": false
  },
  "ordinary_footing": {
    "allowed": [
      "firm_smooth",
      "loose_gravel",
      "mud",
      "rocks_or_roots",
      "built_steps",
      "water_crossing"
    ],
    "difficulty_score": false,
    "duplicates_invalid": true,
    "free_text_allowed": false,
    "other_value_allowed": false,
    "type": "nonempty_unordered_set",
    "unknown_members_invalid": true
  }
}
```

#### `trail_training_constraints_schema` — guardrail

- **Applies to:** non_ultra_trail_constraints_v2 and owner-scoped readiness
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`
- **Rationale:** Schedule and terrain access must be explicit and recent history must remain server-derived. The exact closed DTO is an operational guardrail; it does not establish a safe terrain dose.
- **Exact value:**

```json
{
  "client_may_submit_or_attest_history": false,
  "client_reviewable_fields": {
    "accessible_footing": {
      "envelope": "known_or_unknown",
      "materiality": "core_when_course_footing_known",
      "missing_required_member_result": "readiness_blocked.insufficient_terrain_access",
      "type": "nonempty_unordered_closed_set",
      "vocabulary": "trail_footing_and_hazard_contract.ordinary_footing.allowed"
    },
    "adult_nonclinical_scope_confirmed": {
      "envelope": "known_or_unknown",
      "false_result": "policy_unavailable.unsupported_population_or_intent",
      "materiality": "core",
      "required_value_for_eligibility": true,
      "type": "strict_boolean",
      "unknown_result": "clarification_required.adult_scope_or_constraints_unconfirmed"
    },
    "available_weekdays": {
      "allowed_iso_weekdays": [
        1,
        2,
        3,
        4,
        5,
        6,
        7
      ],
      "envelope": "known_or_unknown",
      "materiality": "core",
      "minimum_members": 1,
      "type": "unique_unordered_set",
      "unknown_result": "clarification_required.training_constraints_missing"
    },
    "controlled_downhill_access": {
      "duration_distance_grade_speed_or_repeat_fields_allowed": false,
      "envelope": "known_or_unknown",
      "false_result": "readiness_blocked.insufficient_terrain_access",
      "materiality": "core",
      "type": "strict_boolean",
      "unknown_result": "clarification_required.training_constraints_missing"
    },
    "current_symptom_stop": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "stop_value": true,
      "true_result": "readiness_blocked.current_symptom_stop",
      "type": "strict_boolean",
      "unknown_result": "clarification_required.training_constraints_missing"
    },
    "maximum_session_duration_min": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "maximum": 1440,
      "minimum": 1,
      "not_greater_than": "weekly_time_limit_min",
      "type": "integer",
      "unknown_result": "clarification_required.training_constraints_missing"
    },
    "nontechnical_three_minute_uphill_access": {
      "envelope": "known_or_unknown",
      "false_result": "readiness_blocked.insufficient_terrain_access",
      "materiality": "core",
      "type": "strict_boolean",
      "unknown_result": "clarification_required.training_constraints_missing"
    },
    "performance_intent_confirmed": {
      "envelope": "known_or_unknown",
      "false_result": "policy_unavailable.unsupported_population_or_intent",
      "materiality": "core",
      "required_value_for_eligibility": true,
      "type": "strict_boolean",
      "unknown_result": "clarification_required.adult_scope_or_constraints_unconfirmed"
    },
    "preferred_longest_weekday": {
      "allowed": [
        1,
        2,
        3,
        4,
        5,
        6,
        7
      ],
      "conflict_result": "clarification_required.contradictory_input",
      "omitted_means_no_preference": true,
      "type": "optional_iso_weekday",
      "when_present_must_be_in": "available_weekdays"
    },
    "unavailable_dates": {
      "all_dates_within_requested_14_day_horizon": true,
      "empty_known_set_allowed": true,
      "envelope": "known_or_unknown",
      "materiality": "core",
      "maximum_members": 14,
      "type": "sorted_unique_iso_date_set",
      "unknown_result": "clarification_required.training_constraints_missing"
    },
    "weekly_time_limit_min": {
      "envelope": "known_or_unknown",
      "materiality": "core",
      "maximum": 10080,
      "minimum": 1,
      "type": "integer",
      "unknown_result": "clarification_required.training_constraints_missing"
    }
  },
  "history_provenance": "history_observed",
  "schema_id": "non_ultra_trail_constraints_v2",
  "server_derived_history_fields": [
    "recent_running_continuity",
    "recent_ascent_exposure",
    "recent_descent_exposure",
    "recently_observed_footing"
  ]
}
```

#### `trail_optional_context_shapes` — guardrail

- **Applies to:** optional v2 course context only
- **Evidence claims:** `trail-ontology.environment-and-altitude-are-distinct-context`, `trail-ontology.duration-and-fueling-practice-are-context`
- **Rationale:** Environment and fueling are relevant context, while every exact bound and enum is a reversible minimization and validation choice. None establishes an exposure, equipment, fueling, gastrointestinal, or safety prescription.
- **Exact value:**

```json
{
  "aid_and_support": {
    "aid_station_count": {
      "maximum": 50,
      "minimum": 0,
      "type": "integer"
    },
    "aid_support_mode": {
      "known_allowed": [
        "organized_aid",
        "mixed",
        "self_supported"
      ]
    },
    "food_availability": {
      "known_allowed": [
        "none",
        "some_stations",
        "all_stations"
      ],
      "unknown_uses_field_envelope": true
    },
    "mandatory_gear": {
      "allowed": [
        "water_carry",
        "food_carry",
        "weather_shell",
        "lighting",
        "navigation_device",
        "other_required"
      ],
      "other_required_has_no_label_or_free_text": true,
      "type": "unordered_closed_set"
    },
    "max_aid_station_gap_km": {
      "maximum": 50,
      "minimum": 0.1,
      "null_allowed_only_for": "no_applicable_gap",
      "type": "finite_number"
    },
    "water_availability": {
      "known_allowed": [
        "none",
        "some_stations",
        "all_stations"
      ],
      "unknown_uses_field_envelope": true
    }
  },
  "environment_and_altitude": {
    "conditions_basis": {
      "athlete_assumption_provenance": "explicit_assumption",
      "athlete_assumption_requires_confirmation": true,
      "known_allowed": [
        "organizer_information",
        "seasonal_expectation",
        "athlete_assumption"
      ]
    },
    "humidity_range_pct": {
      "maximum": 100,
      "minimum": 0,
      "minimum_may_equal_maximum": true,
      "type": "finite_number_range"
    },
    "maximum_altitude_m": {
      "maximum": 9000,
      "minimum": -500,
      "type": "integer"
    },
    "sun_exposure": {
      "known_allowed": [
        "low",
        "mixed",
        "high"
      ],
      "unknown_uses_field_envelope": true
    },
    "temperature_range_c": {
      "maximum": 55,
      "minimum": -30,
      "minimum_may_equal_maximum": true,
      "type": "finite_number_range"
    },
    "wind_exposure": {
      "known_allowed": [
        "sheltered",
        "mixed",
        "exposed"
      ],
      "unknown_uses_field_envelope": true
    }
  },
  "fixed_prescription_from_known_context": false,
  "fueling_and_gastrointestinal_context": {
    "gastrointestinal_experience": {
      "known_allowed": [
        "no_plan_altering_issue",
        "plan_altering_issue"
      ],
      "non_diagnostic": true,
      "unknown_uses_field_envelope": true
    },
    "intake_form": {
      "known_allowed": [
        "none",
        "fluids_only",
        "carbohydrate_drink",
        "mixed_food_and_drink"
      ]
    },
    "longest_practiced_duration_min": {
      "maximum": 1440,
      "minimum": 0,
      "type": "integer"
    },
    "practice_sessions_last_42_days": {
      "maximum": 84,
      "minimum": 0,
      "type": "integer"
    }
  },
  "notes_labels_urls_provider_ids_or_embedded_unit_strings_allowed": false
}
```

#### `trail_unknown_and_materiality_policy` — guardrail

- **Applies to:** v2 capability matching and readiness receipts
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`, `trail-ontology.technicality-and-downhill-vary-performance`
- **Rationale:** This exact Product-selected block-versus-limit mapping keeps material missingness visible without manufacturing certainty or broadening the accepted Science scope.
- **Exact value:**

```json
{
  "bounded_alternative_requires_separate_review": true,
  "core_fields": [
    "event_id",
    "event_date",
    "distance_meters",
    "total_ascent_m",
    "total_descent_m",
    "planning_duration_range",
    "event_format",
    "distance_family",
    "planning_intent",
    "hands_assist",
    "fixed_rope",
    "adult_nonclinical_scope_confirmed",
    "performance_intent_confirmed",
    "current_symptom_stop",
    "available_weekdays",
    "weekly_time_limit_min",
    "maximum_session_duration_min",
    "unavailable_dates",
    "preferred_longest_weekday_consistency_when_present",
    "nontechnical_three_minute_uphill_access",
    "controlled_downhill_access",
    "accessible_footing_when_course_footing_known",
    "recent_running_continuity",
    "recent_ascent_exposure",
    "recent_descent_exposure",
    "recently_observed_footing_when_course_footing_known"
  ],
  "known_value_automatically_enables_module": false,
  "limited_module_may_substitute_generic_or_road_behavior": false,
  "limited_modules_sorted_allowed": [
    "environment_altitude",
    "fueling",
    "grade_specificity",
    "technical_terrain"
  ],
  "limited_unknown_mapping": {
    "aid_and_support": "fueling",
    "course_footing": "technical_terrain",
    "environment_and_altitude": "environment_altitude",
    "fueling_and_gastrointestinal_context": "fueling",
    "grade_distribution": "grade_specificity"
  },
  "material_unknown_result": [
    "clarification_required",
    "policy_unavailable"
  ],
  "unknown_defaults_to_easy": false,
  "unknown_defaults_to_nontechnical": false,
  "unknown_defaults_to_road": false,
  "unknown_defaults_to_zero": false
}
```

#### `trail_distinct_demand_invariants` — guardrail

- **Applies to:** v2 course, access, history, and intensity boundaries
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.technicality-and-downhill-vary-performance`, `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone`
- **Rationale:** Distinct demands follow the evidence; exact set containment is a deterministic conservative matching guardrail, not a validated safety or similarity model.
- **Exact value:**

```json
{
  "activity_average_power_allowed": false,
  "ascent_and_descent_separate": true,
  "downhill_history_required_when_descent_material": true,
  "footing_set_containment": {
    "access_failure_reason": "readiness_blocked.insufficient_terrain_access",
    "access_requirement": "C subset_of A",
    "accessible_set_symbol": "A",
    "applies_only_when_course_footing_known": true,
    "course_set_symbol": "C",
    "history_failure_reason": "readiness_blocked.insufficient_comparable_trail_history",
    "history_requirement": "C subset_of H",
    "observed_history_set_symbol": "H",
    "similarity_synonyms_or_model_inference_allowed": false
  },
  "grade_distribution_descriptive_only": true,
  "heart_rate_alone_sufficient_for_hilly_intensity": false,
  "level_pace_alone_sufficient_for_hilly_intensity": false,
  "technicality_score_allowed": false,
  "universal_distance_vertical_equivalence": false
}
```

#### `trail_revision_and_confirmation` — guardrail

- **Applies to:** every v2 mutation, readiness receipt, and later proposal
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Exact revisions prevent stale confirmation from silently acquiring new meaning. This is an operational replay and user-control guardrail.
- **Exact value:**

```json
{
  "confirm_all_allowed": false,
  "confirmation_invalidated_by": [
    "value_change",
    "known_unknown_state_change",
    "server_stamped_source_change",
    "source_revision_change"
  ],
  "confirmation_is_truth_safety_or_eligibility_attestation": false,
  "confirmation_scope": "exact_visible_field_or_section_revision",
  "mutation_creates_new_immutable_revision": true,
  "proposal_binds_same_exact_revisions": true,
  "readiness_binds_exact_revisions": [
    "goal",
    "course",
    "constraints",
    "history_snapshot",
    "policy",
    "generator"
  ],
  "stale_confirmation_rebound_allowed": false,
  "stale_source_revision_rebound_allowed": false
}
```

#### `trail_science_safety_and_privacy_boundary` — guardrail

- **Applies to:** all v2 science, storage, API, client, audit, and deletion surfaces
- **Evidence claims:** `trail-ontology.heart-rate-and-road-pace-are-insufficient-alone`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`
- **Rationale:** These preserve the accepted v1 nonclinical, intensity, claim, and minimization boundaries while making the v2 storage exclusion explicit.
- **Exact value:**

```json
{
  "activity_average_power_valid_for_intensity": false,
  "authenticated_owner_scoped_reset_export_and_deletion_required": true,
  "diagnosis_treatment_clearance_or_return_to_sport": false,
  "forbidden_collection_or_persistence": [
    "gps_points",
    "route_files",
    "polylines",
    "maps",
    "inferred_course_geometry",
    "course_source_urls",
    "scraped_course_content",
    "provider_request_or_response_payloads",
    "provider_account_activity_or_workout_ids",
    "device_identifiers",
    "free_text_health_symptom_fueling_surface_or_course_narratives",
    "diagnoses_or_medical_clearance",
    "injury_probability",
    "activity_average_power",
    "road_equivalent_distance_pace_or_load"
  ],
  "generic_audit_or_telemetry_may_copy_sensitive_payloads": false,
  "inferred_and_athlete_stated_fields_correctable_and_deletable": true,
  "minimum_age_years": 18,
  "minimum_normalized_storage_only": true,
  "nonclinical_only": true,
  "performance_injury_or_safety_guarantee": false,
  "permitted_persisted_categories": [
    "canonical_field_values_and_unknown_states",
    "server_stamped_provenance",
    "source_and_field_or_section_revisions",
    "confirmations",
    "owner_scoped_history_snapshot_reference_and_hash",
    "readiness_and_proposal_binding_digests"
  ],
  "personal_finish_probability": false,
  "suggestion_only": true,
  "symptom_stop_required": true,
  "valid_intensity_sources": [
    "activity_splits",
    "activity_samples"
  ]
}
```

#### `trail_exact_values` — guardrail

- **Applies to:** unresolved ontology and prescription values
- **Evidence claims:** `trail-ontology.uphill-downhill-demands-differ`, `trail-ontology.training-and-injury-evidence-does-not-set-safe-dose`
- **Rationale:** The accepted evidence supports explicit dimensions but not universal scoring, inference, equivalence, prediction, progression, or dose. Only the closed validation DTO is proposed here.
- **Exact value:**

```json
{
  "core_and_limited_materiality": "operational_guardrail_only",
  "course_domain_bounds": "product_scope_and_operability_guardrail_only",
  "distance_vertical_conversion": "not_accepted",
  "downhill_progression": "not_accepted",
  "environment_or_altitude_dose": "not_accepted",
  "finish_time_prediction": "not_accepted",
  "footing_vocabulary": "descriptive_operational_guardrail_only",
  "fueling_amount_or_frequency": "not_accepted",
  "optional_context_bounds": "operational_guardrail_only",
  "planning_duration_range_shape": "operational_guardrail_only",
  "road_trail_equivalence": "not_accepted",
  "route_or_provider_inference": "not_accepted",
  "schedule_capacity_bounds": "product_scope_and_operability_guardrail_only",
  "signed_grade_buckets": "descriptive_operational_guardrail_only",
  "technical_terrain_dose": "not_accepted",
  "technicality_score": "not_accepted",
  "vertical_progression": "not_accepted"
}
```

#### `trail_non_science_authority_boundary` — guardrail

- **Applies to:** all work outside the Science role
- **Evidence claims:** _None; product rationale only_
- **Rationale:** A Science successor cannot originate or widen Product, Design, Engineering, Trust, Operations, provider, rollout, or activation authority.
- **Exact value:**

```json
{
  "deployment": "not_accepted",
  "implementation_review": "required",
  "lifecycle_supersession": "not_accepted",
  "owner_only_dogfood": "not_accepted",
  "product_and_experience_dependency": "human_acceptance_required",
  "product_visibility_or_catalog": "not_accepted",
  "production_data_use": "not_accepted",
  "provider_mapping_or_delivery": "not_accepted",
  "runtime_activation": "not_accepted",
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

#### Keep the ambiguous v1 object fields and let each caller interpret them

Caller-specific interpretation would make missingness, provenance, materiality, and replay nondeterministic.

#### Infer grade, footing, or technical demand from a route or provider payload

v2 does not collect those payloads, and the evidence does not validate a universal inference or technicality score.

#### Require every optional course descriptor before any proposal

Core-versus-limited materiality can preserve uncertainty without hiding it or inventing a dependent module.

#### Treat an unknown or inaccessible Trail field as ordinary road running

That would erase course-specific demand and violate the accepted no-road- fallback boundary.

### Applicability

- Adult nonclinical single-day non-ultra Trail performance goal representation
- Strict provider-neutral course and athlete-constraint capture before capability matching
- Server-derived owner-scoped recent-history context
- Evidence, uncertainty, claim limits, safety, and privacy boundaries only

### User-facing claim limits

- Do not claim the exact v2 DTO, bins, footing vocabulary, bounds, or materiality map is scientifically optimal or validated as a safety rule.
- Do not claim planning duration is a finish-time prediction, feasibility verdict, or performance promise.
- Do not claim distance and ascent alone describe Trail demand or present a universal road-equivalent distance, grade, ascent, or descent conversion.
- Do not present unknown footing, hazard, environment, support, fueling, or gastrointestinal context as known, easy, safe, or average.
- Do not present a technicality score, personal finish probability, performance guarantee, injury-prevention guarantee, diagnosis, treatment, or clearance.

### Safety implications

- Every core unknown or failed gate prevents an eligible proposal; only named non-core unknowns can limit a dependent module.
- Uphill, downhill, ordinary footing, hazards, altitude, heat, support, and fueling context remain distinct when applicable.
- Hands-assist or fixed-rope use stays outside v2; unknown hazard gates require clarification.
- Current symptoms stop performance optimization without creating a diagnosis.
- Intensity provenance uses activity splits or samples, never activity-average power.

### Privacy implications

- Collect and persist only normalized typed values, explicit unknown states, server provenance, revisions, confirmations, and owner-scoped replay references.
- Do not ingest GPS, routes, maps, source URLs, scraped content, provider payloads or identifiers, device identifiers, or free-text planning narratives.
- Reset invalidates confirmation and creates a new revision; export and deletion include the current owner-scoped v2 state under existing data-rights controls.
- No public sharing, cross-user aggregate, administrator planning access, or value telemetry is authorized.

### Validation plan

- Validate every closed enum, set, integer, finite number, range relation, explicit unknown state, and field-specific provenance rule deterministically.
- Boundary-test all five signed-grade intervals and require nonnegative integer shares summing exactly to 10000.
- Replay reordered footing and weekday sets and verify one canonical digest; reject duplicates, unknown members, synonyms, and free text.
- Verify exact course-footing containment against both accessible and observed-history sets and preserve the distinct access and history failures.
- Mutate every field value, state, and server source revision and verify the prior confirmation and readiness binding becomes stale.
- Exercise every core unknown and limited unknown and verify no road policy, hidden default, provider behavior, or success-shaped plan is selected.
- Generate the matching review packet and inactive machine contract and bind any later approval to their exact digests.

### Falsification conditions

- A malformed or stale v2 value is treated as confirmed, or client-provided provenance or history is accepted.
- A grade share falls into two buckets, the five shares do not total 10000, or grade becomes a difficulty, dose, equivalence, or prediction input.
- Footing comparison uses order, similarity, synonyms, inference, or a road category instead of exact set containment.
- A core unknown yields eligible_proposal, or a limited unknown silently enables or substitutes a module.
- Ascent and descent collapse, route or provider data enters the contract, free text is retained, or activity-average power drives intensity.
- A personal safety, finish, or performance claim appears, or the generated contract becomes active without separate implementation review and activation authority.

### Decision notes

- Decision Proposal mode; this record is draft and inactive and adds no Evidence Review or scientific claim.
- Proposed predecessor transition: after separate digest-bound human approval and coordinated lifecycle review, this record may replace sdr-trail-running-goal-ontology-v1; no supersession link is active in this draft.
- The accepted evidence remains sufficient only because every new exact value is classified as a reversible operational guardrail rather than a published biological rule.
- Product dependency: docs/dev/trail-running-plan-product-amendment-v2.md.
- Experience dependency: docs/dev/trail-running-plan-experience-amendment-v2.md.
- Architecture dependency: docs/dev/trail-running-plan-architecture-decision-v2.md.
- Trust dependency: docs/dev/trail-running-plan-trust-decision-v2.md.
- This revision incorporates the bounded Product correction at repository commit 81c58c1b; it does not approve that role-owned artifact.
- Work Contract classification digest: sha256:d0a83117e8cd681435229fb7fb2c8ddddf4ac8ad8acaba24590079ba1e200607.
- Work Contract route digest: sha256:6a022077cd4d910007c63241ee7c4b98773cd587c92450c6acecc778943fe168.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "trail_course_demand_v2 ontology",
    "non_ultra_trail_constraints_v2 input and confirmation envelope",
    "future v2 Trail capability matching contract"
  ],
  "contract_digest": "sha256:1297f713b992822335978dac92cfaa9b968b092d4ff6869ad73baa3d94ee2e7a",
  "decision_id": "sdr-trail-running-goal-ontology-v2",
  "decision_status": "draft",
  "decision_version": 2,
  "evidence_claim_ids": [
    "trail-ontology.course-demand-is-multidimensional",
    "trail-ontology.uphill-downhill-demands-differ",
    "trail-ontology.technicality-and-downhill-vary-performance",
    "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
    "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose",
    "trail-ontology.environment-and-altitude-are-distinct-context",
    "trail-ontology.duration-and-fueling-practice-are-context"
  ],
  "evidence_review_ids": [
    "evidence-trail-running-goal-ontology-v1"
  ],
  "linked_evidence_digests": {
    "evidence-trail-running-goal-ontology-v1": "sha256:60f0e785e4fc2b4226fed3bb30750191195cffbb0236b4a81d34431c0002c87a"
  },
  "model_version": "trail-course-demand-v2",
  "parameters": {
    "trail_course_demand_schema": {
      "applies_to": "trail_course_demand_v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.uphill-downhill-demands-differ"
      ],
      "value": {
        "event_identity": {
          "client_writable": false,
          "field": "event_id",
          "materiality": "core",
          "type": "server_owned_identifier"
        },
        "fields": {
          "aid_and_support": {
            "envelope": "known_or_unknown",
            "limited_module": "fueling",
            "materiality": "limited",
            "type": "bounded_object"
          },
          "course_footing": {
            "envelope": "known_or_unknown",
            "limited_module": "technical_terrain",
            "materiality": "limited_with_core_matching_when_known",
            "type": "nonempty_unordered_closed_set"
          },
          "distance_family": {
            "allowed": [
              "non_ultra"
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "closed_enum"
          },
          "distance_meters": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 49999,
            "minimum": 1,
            "type": "integer",
            "unit": "meters"
          },
          "environment_and_altitude": {
            "envelope": "known_or_unknown",
            "limited_module": "environment_altitude",
            "materiality": "limited",
            "type": "bounded_object"
          },
          "event_date": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "iso_date"
          },
          "event_format": {
            "allowed": [
              "single_day"
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "closed_enum"
          },
          "fixed_rope": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "strict_boolean"
          },
          "fueling_and_gastrointestinal_context": {
            "envelope": "known_or_unknown",
            "limited_module": "fueling",
            "materiality": "limited",
            "type": "bounded_object"
          },
          "grade_distribution": {
            "envelope": "known_or_unknown",
            "limited_module": "grade_specificity",
            "materiality": "limited",
            "type": "five_bucket_basis_point_object"
          },
          "hands_assist": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "strict_boolean"
          },
          "planning_duration_range": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "integer_range",
            "unit": "minutes"
          },
          "planning_intent": {
            "allowed": [
              "performance"
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "closed_enum"
          },
          "total_ascent_m": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 20000,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          },
          "total_descent_m": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 20000,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          }
        },
        "schema_id": "trail_course_demand_v2",
        "strict_unknown_fields_rejected": true
      }
    },
    "trail_distinct_demand_invariants": {
      "applies_to": "v2 course, access, history, and intensity boundaries",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.technicality-and-downhill-vary-performance",
        "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone"
      ],
      "value": {
        "activity_average_power_allowed": false,
        "ascent_and_descent_separate": true,
        "downhill_history_required_when_descent_material": true,
        "footing_set_containment": {
          "access_failure_reason": "readiness_blocked.insufficient_terrain_access",
          "access_requirement": "C subset_of A",
          "accessible_set_symbol": "A",
          "applies_only_when_course_footing_known": true,
          "course_set_symbol": "C",
          "history_failure_reason": "readiness_blocked.insufficient_comparable_trail_history",
          "history_requirement": "C subset_of H",
          "observed_history_set_symbol": "H",
          "similarity_synonyms_or_model_inference_allowed": false
        },
        "grade_distribution_descriptive_only": true,
        "heart_rate_alone_sufficient_for_hilly_intensity": false,
        "level_pace_alone_sufficient_for_hilly_intensity": false,
        "technicality_score_allowed": false,
        "universal_distance_vertical_equivalence": false
      }
    },
    "trail_exact_values": {
      "applies_to": "unresolved ontology and prescription values",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "value": {
        "core_and_limited_materiality": "operational_guardrail_only",
        "course_domain_bounds": "product_scope_and_operability_guardrail_only",
        "distance_vertical_conversion": "not_accepted",
        "downhill_progression": "not_accepted",
        "environment_or_altitude_dose": "not_accepted",
        "finish_time_prediction": "not_accepted",
        "footing_vocabulary": "descriptive_operational_guardrail_only",
        "fueling_amount_or_frequency": "not_accepted",
        "optional_context_bounds": "operational_guardrail_only",
        "planning_duration_range_shape": "operational_guardrail_only",
        "road_trail_equivalence": "not_accepted",
        "route_or_provider_inference": "not_accepted",
        "schedule_capacity_bounds": "product_scope_and_operability_guardrail_only",
        "signed_grade_buckets": "descriptive_operational_guardrail_only",
        "technical_terrain_dose": "not_accepted",
        "technicality_score": "not_accepted",
        "vertical_progression": "not_accepted"
      }
    },
    "trail_field_provenance": {
      "applies_to": "every reviewable v2 course, constraint, and history field",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "assumption_requires_revision_bound_confirmation": true,
        "client_may_submit_history_hash": false,
        "client_may_submit_model_version": false,
        "client_may_submit_provenance": false,
        "client_may_submit_source_revision": false,
        "client_may_submit_source_timestamp": false,
        "field_restrictions": {
          "athlete_assumption_conditions": [
            "explicit_assumption"
          ],
          "event_id": "server_owned",
          "grade_distribution": [
            "athlete_stated",
            "course_verified",
            "unknown"
          ],
          "recent_history": [
            "history_observed"
          ]
        },
        "inferred_requires_server_model_version": true,
        "request_envelope": {
          "arbitrary_object_invalid": true,
          "empty_string_invalid": true,
          "guessed_zero_invalid": true,
          "known": {
            "exact_keys": [
              "state",
              "value"
            ],
            "schema_valid_value_required": true,
            "state_literal": "known"
          },
          "missing_state_invalid": true,
          "null_invalid_except_explicit_aid_gap_case": true,
          "numeric_values_must_be_finite": true,
          "sentinel_number_invalid": true,
          "unknown": {
            "exact_keys": [
              "state"
            ],
            "state_literal": "unknown",
            "value_forbidden": true
          }
        },
        "server_stamped_provenance_allowed": [
          "athlete_stated",
          "course_verified",
          "history_observed",
          "model_inferred",
          "explicit_assumption",
          "unknown"
        ],
        "unknown_is_preserved": true
      }
    },
    "trail_footing_and_hazard_contract": {
      "applies_to": "course, access, and observed-history footing plus v2 hazard gates",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.technicality-and-downhill-vary-performance",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "value": {
        "hazard_gates": {
          "fixed_rope": {
            "eligible_value": "known_false",
            "envelope": "known_or_unknown",
            "known_true_result": "policy_unavailable.technical_features_outside_v2",
            "known_value_type": "strict_boolean",
            "unknown_result": "clarification_required.material_course_demand_unknown"
          },
          "hands_assist": {
            "eligible_value": "known_false",
            "envelope": "known_or_unknown",
            "known_true_result": "policy_unavailable.technical_features_outside_v2",
            "known_value_type": "strict_boolean",
            "unknown_result": "clarification_required.material_course_demand_unknown"
          },
          "reducible_to_ordinary_footing": false,
          "technical_skill_or_safety_score": false
        },
        "ordinary_footing": {
          "allowed": [
            "firm_smooth",
            "loose_gravel",
            "mud",
            "rocks_or_roots",
            "built_steps",
            "water_crossing"
          ],
          "difficulty_score": false,
          "duplicates_invalid": true,
          "free_text_allowed": false,
          "other_value_allowed": false,
          "type": "nonempty_unordered_set",
          "unknown_members_invalid": true
        }
      }
    },
    "trail_grade_distribution": {
      "applies_to": "known grade_distribution in trail_course_demand_v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ"
      ],
      "value": {
        "allowed_provenance": [
          "athlete_stated",
          "course_verified"
        ],
        "buckets": {
          "below_neg_10": {
            "interval": "g < -10%",
            "upper_bound_percent": -10,
            "upper_inclusive": false
          },
          "neg_10_to_below_neg_3": {
            "interval": "-10% <= g < -3%",
            "lower_bound_percent": -10,
            "lower_inclusive": true,
            "upper_bound_percent": -3,
            "upper_inclusive": false
          },
          "neg_3_to_below_pos_3": {
            "interval": "-3% <= g < 3%",
            "lower_bound_percent": -3,
            "lower_inclusive": true,
            "upper_bound_percent": 3,
            "upper_inclusive": false
          },
          "pos_10_and_above": {
            "interval": "g >= 10%",
            "lower_bound_percent": 10,
            "lower_inclusive": true
          },
          "pos_3_to_below_pos_10": {
            "interval": "3% <= g < 10%",
            "lower_bound_percent": 3,
            "lower_inclusive": true,
            "upper_bound_percent": 10,
            "upper_inclusive": false
          }
        },
        "descriptive_only": true,
        "difficulty_score": false,
        "each_share_minimum": 0,
        "each_share_type": "integer",
        "equivalence_or_prediction_input": false,
        "exact_sum": 10000,
        "known_value_exact_keys": [
          "below_neg_10",
          "neg_10_to_below_neg_3",
          "neg_3_to_below_pos_3",
          "pos_3_to_below_pos_10",
          "pos_10_and_above"
        ],
        "ordering_semantic": false,
        "route_or_model_inference": false,
        "safety_threshold": false,
        "unit": "basis_points_of_course_distance",
        "workout_dose_input": false
      }
    },
    "trail_non_science_authority_boundary": {
      "applies_to": "all work outside the Science role",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "deployment": "not_accepted",
        "implementation_review": "required",
        "lifecycle_supersession": "not_accepted",
        "owner_only_dogfood": "not_accepted",
        "product_and_experience_dependency": "human_acceptance_required",
        "product_visibility_or_catalog": "not_accepted",
        "production_data_use": "not_accepted",
        "provider_mapping_or_delivery": "not_accepted",
        "runtime_activation": "not_accepted",
        "science_authority": [
          "evidence",
          "applicability",
          "uncertainty",
          "claim_limits",
          "safety_scope"
        ]
      }
    },
    "trail_optional_context_shapes": {
      "applies_to": "optional v2 course context only",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.environment-and-altitude-are-distinct-context",
        "trail-ontology.duration-and-fueling-practice-are-context"
      ],
      "value": {
        "aid_and_support": {
          "aid_station_count": {
            "maximum": 50,
            "minimum": 0,
            "type": "integer"
          },
          "aid_support_mode": {
            "known_allowed": [
              "organized_aid",
              "mixed",
              "self_supported"
            ]
          },
          "food_availability": {
            "known_allowed": [
              "none",
              "some_stations",
              "all_stations"
            ],
            "unknown_uses_field_envelope": true
          },
          "mandatory_gear": {
            "allowed": [
              "water_carry",
              "food_carry",
              "weather_shell",
              "lighting",
              "navigation_device",
              "other_required"
            ],
            "other_required_has_no_label_or_free_text": true,
            "type": "unordered_closed_set"
          },
          "max_aid_station_gap_km": {
            "maximum": 50,
            "minimum": 0.1,
            "null_allowed_only_for": "no_applicable_gap",
            "type": "finite_number"
          },
          "water_availability": {
            "known_allowed": [
              "none",
              "some_stations",
              "all_stations"
            ],
            "unknown_uses_field_envelope": true
          }
        },
        "environment_and_altitude": {
          "conditions_basis": {
            "athlete_assumption_provenance": "explicit_assumption",
            "athlete_assumption_requires_confirmation": true,
            "known_allowed": [
              "organizer_information",
              "seasonal_expectation",
              "athlete_assumption"
            ]
          },
          "humidity_range_pct": {
            "maximum": 100,
            "minimum": 0,
            "minimum_may_equal_maximum": true,
            "type": "finite_number_range"
          },
          "maximum_altitude_m": {
            "maximum": 9000,
            "minimum": -500,
            "type": "integer"
          },
          "sun_exposure": {
            "known_allowed": [
              "low",
              "mixed",
              "high"
            ],
            "unknown_uses_field_envelope": true
          },
          "temperature_range_c": {
            "maximum": 55,
            "minimum": -30,
            "minimum_may_equal_maximum": true,
            "type": "finite_number_range"
          },
          "wind_exposure": {
            "known_allowed": [
              "sheltered",
              "mixed",
              "exposed"
            ],
            "unknown_uses_field_envelope": true
          }
        },
        "fixed_prescription_from_known_context": false,
        "fueling_and_gastrointestinal_context": {
          "gastrointestinal_experience": {
            "known_allowed": [
              "no_plan_altering_issue",
              "plan_altering_issue"
            ],
            "non_diagnostic": true,
            "unknown_uses_field_envelope": true
          },
          "intake_form": {
            "known_allowed": [
              "none",
              "fluids_only",
              "carbohydrate_drink",
              "mixed_food_and_drink"
            ]
          },
          "longest_practiced_duration_min": {
            "maximum": 1440,
            "minimum": 0,
            "type": "integer"
          },
          "practice_sessions_last_42_days": {
            "maximum": 84,
            "minimum": 0,
            "type": "integer"
          }
        },
        "notes_labels_urls_provider_ids_or_embedded_unit_strings_allowed": false
      }
    },
    "trail_planning_duration_range": {
      "applies_to": "trail_course_demand_v2 core confirmation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.duration-and-fueling-practice-are-context"
      ],
      "value": {
        "athlete_confirmed": true,
        "feasibility_verdict": false,
        "field": "planning_duration_range",
        "finish_time_prediction": false,
        "minimum_and_maximum_each": {
          "maximum": 1440,
          "minimum": 1
        },
        "minimum_strictly_less_than_maximum": true,
        "performance_promise": false,
        "purpose": "planning_context",
        "unit": "integer_minutes"
      }
    },
    "trail_revision_and_confirmation": {
      "applies_to": "every v2 mutation, readiness receipt, and later proposal",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "confirm_all_allowed": false,
        "confirmation_invalidated_by": [
          "value_change",
          "known_unknown_state_change",
          "server_stamped_source_change",
          "source_revision_change"
        ],
        "confirmation_is_truth_safety_or_eligibility_attestation": false,
        "confirmation_scope": "exact_visible_field_or_section_revision",
        "mutation_creates_new_immutable_revision": true,
        "proposal_binds_same_exact_revisions": true,
        "readiness_binds_exact_revisions": [
          "goal",
          "course",
          "constraints",
          "history_snapshot",
          "policy",
          "generator"
        ],
        "stale_confirmation_rebound_allowed": false,
        "stale_source_revision_rebound_allowed": false
      }
    },
    "trail_science_safety_and_privacy_boundary": {
      "applies_to": "all v2 science, storage, API, client, audit, and deletion surfaces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "authenticated_owner_scoped_reset_export_and_deletion_required": true,
        "diagnosis_treatment_clearance_or_return_to_sport": false,
        "forbidden_collection_or_persistence": [
          "gps_points",
          "route_files",
          "polylines",
          "maps",
          "inferred_course_geometry",
          "course_source_urls",
          "scraped_course_content",
          "provider_request_or_response_payloads",
          "provider_account_activity_or_workout_ids",
          "device_identifiers",
          "free_text_health_symptom_fueling_surface_or_course_narratives",
          "diagnoses_or_medical_clearance",
          "injury_probability",
          "activity_average_power",
          "road_equivalent_distance_pace_or_load"
        ],
        "generic_audit_or_telemetry_may_copy_sensitive_payloads": false,
        "inferred_and_athlete_stated_fields_correctable_and_deletable": true,
        "minimum_age_years": 18,
        "minimum_normalized_storage_only": true,
        "nonclinical_only": true,
        "performance_injury_or_safety_guarantee": false,
        "permitted_persisted_categories": [
          "canonical_field_values_and_unknown_states",
          "server_stamped_provenance",
          "source_and_field_or_section_revisions",
          "confirmations",
          "owner_scoped_history_snapshot_reference_and_hash",
          "readiness_and_proposal_binding_digests"
        ],
        "personal_finish_probability": false,
        "suggestion_only": true,
        "symptom_stop_required": true,
        "valid_intensity_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    "trail_training_constraints_schema": {
      "applies_to": "non_ultra_trail_constraints_v2 and owner-scoped readiness",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "value": {
        "client_may_submit_or_attest_history": false,
        "client_reviewable_fields": {
          "accessible_footing": {
            "envelope": "known_or_unknown",
            "materiality": "core_when_course_footing_known",
            "missing_required_member_result": "readiness_blocked.insufficient_terrain_access",
            "type": "nonempty_unordered_closed_set",
            "vocabulary": "trail_footing_and_hazard_contract.ordinary_footing.allowed"
          },
          "adult_nonclinical_scope_confirmed": {
            "envelope": "known_or_unknown",
            "false_result": "policy_unavailable.unsupported_population_or_intent",
            "materiality": "core",
            "required_value_for_eligibility": true,
            "type": "strict_boolean",
            "unknown_result": "clarification_required.adult_scope_or_constraints_unconfirmed"
          },
          "available_weekdays": {
            "allowed_iso_weekdays": [
              1,
              2,
              3,
              4,
              5,
              6,
              7
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "minimum_members": 1,
            "type": "unique_unordered_set",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "controlled_downhill_access": {
            "duration_distance_grade_speed_or_repeat_fields_allowed": false,
            "envelope": "known_or_unknown",
            "false_result": "readiness_blocked.insufficient_terrain_access",
            "materiality": "core",
            "type": "strict_boolean",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "current_symptom_stop": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "stop_value": true,
            "true_result": "readiness_blocked.current_symptom_stop",
            "type": "strict_boolean",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "maximum_session_duration_min": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 1440,
            "minimum": 1,
            "not_greater_than": "weekly_time_limit_min",
            "type": "integer",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "nontechnical_three_minute_uphill_access": {
            "envelope": "known_or_unknown",
            "false_result": "readiness_blocked.insufficient_terrain_access",
            "materiality": "core",
            "type": "strict_boolean",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "performance_intent_confirmed": {
            "envelope": "known_or_unknown",
            "false_result": "policy_unavailable.unsupported_population_or_intent",
            "materiality": "core",
            "required_value_for_eligibility": true,
            "type": "strict_boolean",
            "unknown_result": "clarification_required.adult_scope_or_constraints_unconfirmed"
          },
          "preferred_longest_weekday": {
            "allowed": [
              1,
              2,
              3,
              4,
              5,
              6,
              7
            ],
            "conflict_result": "clarification_required.contradictory_input",
            "omitted_means_no_preference": true,
            "type": "optional_iso_weekday",
            "when_present_must_be_in": "available_weekdays"
          },
          "unavailable_dates": {
            "all_dates_within_requested_14_day_horizon": true,
            "empty_known_set_allowed": true,
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum_members": 14,
            "type": "sorted_unique_iso_date_set",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "weekly_time_limit_min": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 10080,
            "minimum": 1,
            "type": "integer",
            "unknown_result": "clarification_required.training_constraints_missing"
          }
        },
        "history_provenance": "history_observed",
        "schema_id": "non_ultra_trail_constraints_v2",
        "server_derived_history_fields": [
          "recent_running_continuity",
          "recent_ascent_exposure",
          "recent_descent_exposure",
          "recently_observed_footing"
        ]
      }
    },
    "trail_unknown_and_materiality_policy": {
      "applies_to": "v2 capability matching and readiness receipts",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.technicality-and-downhill-vary-performance"
      ],
      "value": {
        "bounded_alternative_requires_separate_review": true,
        "core_fields": [
          "event_id",
          "event_date",
          "distance_meters",
          "total_ascent_m",
          "total_descent_m",
          "planning_duration_range",
          "event_format",
          "distance_family",
          "planning_intent",
          "hands_assist",
          "fixed_rope",
          "adult_nonclinical_scope_confirmed",
          "performance_intent_confirmed",
          "current_symptom_stop",
          "available_weekdays",
          "weekly_time_limit_min",
          "maximum_session_duration_min",
          "unavailable_dates",
          "preferred_longest_weekday_consistency_when_present",
          "nontechnical_three_minute_uphill_access",
          "controlled_downhill_access",
          "accessible_footing_when_course_footing_known",
          "recent_running_continuity",
          "recent_ascent_exposure",
          "recent_descent_exposure",
          "recently_observed_footing_when_course_footing_known"
        ],
        "known_value_automatically_enables_module": false,
        "limited_module_may_substitute_generic_or_road_behavior": false,
        "limited_modules_sorted_allowed": [
          "environment_altitude",
          "fueling",
          "grade_specificity",
          "technical_terrain"
        ],
        "limited_unknown_mapping": {
          "aid_and_support": "fueling",
          "course_footing": "technical_terrain",
          "environment_and_altitude": "environment_altitude",
          "fueling_and_gastrointestinal_context": "fueling",
          "grade_distribution": "grade_specificity"
        },
        "material_unknown_result": [
          "clarification_required",
          "policy_unavailable"
        ],
        "unknown_defaults_to_easy": false,
        "unknown_defaults_to_nontechnical": false,
        "unknown_defaults_to_road": false,
        "unknown_defaults_to_zero": false
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:73dd653f8637004ff2ab3a754c3e775225eaf9faa79ccc52c97de3c3dbbf0b7c"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If separately accepted by the decision approver, this successor would keep every accepted v1 science and safety boundary while defining trail_course_demand_v2 and non_ultra_trail_constraints_v2 as strict, provider-neutral, revision-bound data contracts. Reviewable fields carry an explicit known value or explicit unknown state; the server, never the client, stamps provenance and source revisions. Core course, scope, hazard, schedule, terrain-access, symptom, and recent-history gates fail closed. Unknown grade, ordinary course footing, environment, support, or fueling context can limit only their named module after all core gates pass. Five signed-grade basis-point buckets, six unordered footing flags, known-or- unknown boolean hazard fields, exact footing set containment, bounded schedule capacity, and bounded optional context are reversible Praxys operational guardrails, not validated difficulty scores, training doses, equivalence formulas, predictions, or safety thresholds. No route, GPS, free-text planning, provider payload, activity-average power, road fallback, personal performance prediction, or runtime behavior is accepted.",
  "affected_surfaces": {
    "apis": [
      "future inactive Trail course, constraint, confirmation, and readiness contracts"
    ],
    "clients": [
      "future inactive Praxys Web Trail course-ledger experience",
      "future unavailable miniapp Trail setup handoff"
    ],
    "models": [
      "trail_course_demand_v2 ontology",
      "non_ultra_trail_constraints_v2 input and confirmation envelope",
      "future v2 Trail capability matching contract"
    ],
    "science_notes": [
      "Why Trail demand needs more than distance and ascent",
      "Why grade shares and footing flags are descriptive operational guardrails",
      "Why planning duration is context rather than a prediction"
    ]
  },
  "applicability": [
    "Adult nonclinical single-day non-ultra Trail performance goal representation",
    "Strict provider-neutral course and athlete-constraint capture before capability matching",
    "Server-derived owner-scoped recent-history context",
    "Evidence, uncertainty, claim limits, safety, and privacy boundaries only"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-09-04",
  "decision_notes": [
    "Decision Proposal mode; this record is draft and inactive and adds no Evidence Review or scientific claim.",
    "Proposed predecessor transition: after separate digest-bound human approval and coordinated lifecycle review, this record may replace sdr-trail-running-goal-ontology-v1; no supersession link is active in this draft.",
    "The accepted evidence remains sufficient only because every new exact value is classified as a reversible operational guardrail rather than a published biological rule.",
    "Product dependency: docs/dev/trail-running-plan-product-amendment-v2.md.",
    "Experience dependency: docs/dev/trail-running-plan-experience-amendment-v2.md.",
    "Architecture dependency: docs/dev/trail-running-plan-architecture-decision-v2.md.",
    "Trust dependency: docs/dev/trail-running-plan-trust-decision-v2.md.",
    "This revision incorporates the bounded Product correction at repository commit 81c58c1b; it does not approve that role-owned artifact.",
    "Work Contract classification digest: sha256:d0a83117e8cd681435229fb7fb2c8ddddf4ac8ad8acaba24590079ba1e200607.",
    "Work Contract route digest: sha256:6a022077cd4d910007c63241ee7c4b98773cd587c92450c6acecc778943fe168."
  ],
  "decision_review": {
    "approval_statement": "I approve trail_course_demand_v2 and non_ultra_trail_constraints_v2 as strict revision-bound Trail planning envelopes: explicit known or unknown fields, server-owned provenance, separate ascent and descent, descriptive signed-grade shares, closed footing and known-or-unknown boolean hazard fields, exact footing containment, bounded schedule and optional context, and fail-closed core materiality. I approve the exact DTO values only as reversible Praxys operational guardrails, not as published biological findings, difficulty or safety scores, doses, equivalences, or predictions. This approval authorizes only preparation and review of a separately reviewed inactive implementation bound to this exact decision and contract. It does not approve lifecycle supersession, merge, deployment, production data use, dogfood, catalog visibility, provider behavior, delivery, or runtime activation.",
    "items": [
      {
        "approval_effect": [
          "Missing values cannot be represented as zero, empty text, or a client-selected source.",
          "Readiness and proposals can bind the exact confirmed source revisions used."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Source scraping, route inference, model truth claims, or automatic confirmation."
        ],
        "evidence_claim_ids": [
          "trail-ontology.course-demand-is-multidimensional"
        ],
        "id": "strict-value-provenance-envelope",
        "parameter_names": [
          "trail_field_provenance",
          "trail_revision_and_confirmation"
        ],
        "proposed_decision": "Accept the closed envelope, provenance categories, field-specific provenance restrictions, immutable revisions, and confirmation invalidation rules as operational guardrails.",
        "question": "Should every reviewable v2 field use an exact known-or-unknown envelope while provenance, source metadata, and history hashes remain server-owned and revision-bound?",
        "title": "Adopt explicit field states and server-owned provenance"
      },
      {
        "approval_effect": [
          "Distance and ascent alone cannot select a Trail policy.",
          "A material core unknown prevents an eligible proposal."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A finish-time estimate, feasibility verdict, performance promise, or course equivalence."
        ],
        "evidence_claim_ids": [
          "trail-ontology.course-demand-is-multidimensional",
          "trail-ontology.uphill-downhill-demands-differ",
          "trail-ontology.duration-and-fueling-practice-are-context"
        ],
        "id": "core-course-and-planning-context",
        "parameter_names": [
          "trail_course_demand_schema",
          "trail_planning_duration_range"
        ],
        "proposed_decision": "Require those typed fields and treat planning duration only as athlete-confirmed planning context, never as a finish-time prediction.",
        "question": "Should event identity, date, distance, ascent, descent, scope, intent, hazard gates, and a confirmed planning-duration range be core inputs?",
        "title": "Adopt the v2 core course tuple and planning-duration range"
      },
      {
        "approval_effect": [
          "Grade boundaries and footing matching replay identically.",
          "Course footing cannot be approximated by synonyms or a road category."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Route-derived grade, a technical score, downhill dose, or terrain equivalence."
        ],
        "evidence_claim_ids": [
          "trail-ontology.uphill-downhill-demands-differ",
          "trail-ontology.technicality-and-downhill-vary-performance"
        ],
        "id": "descriptive-course-and-access-vocabularies",
        "parameter_names": [
          "trail_grade_distribution",
          "trail_footing_and_hazard_contract",
          "trail_training_constraints_schema"
        ],
        "proposed_decision": "Accept these closed DTOs and exact set-containment rules as deterministic descriptions, not as technicality scores or doses.",
        "question": "Should v2 use the exact five signed-grade share buckets, six unordered footing flags, two known-or-unknown boolean hazard fields, and bounded schedule plus uphill/downhill/footing access fields?",
        "title": "Adopt descriptive grade, footing, hazard, and terrain-access DTOs"
      },
      {
        "approval_effect": [
          "Optional unknowns remain visible without becoming hidden defaults.",
          "A known mismatch still blocks the affected core access or history gate."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "An environment, altitude, equipment, fueling, gastrointestinal, or safety prescription."
        ],
        "evidence_claim_ids": [
          "trail-ontology.course-demand-is-multidimensional",
          "trail-ontology.environment-and-altitude-are-distinct-context",
          "trail-ontology.duration-and-fueling-practice-are-context"
        ],
        "id": "bounded-context-and-materiality",
        "parameter_names": [
          "trail_optional_context_shapes",
          "trail_unknown_and_materiality_policy",
          "trail_distinct_demand_invariants"
        ],
        "proposed_decision": "Accept the bounded shapes, exact core/limited mapping, sorted module vocabulary, and course-footing containment against access and observed history.",
        "question": "Should environment, altitude, aid, equipment, fueling, and gastrointestinal context use closed bounded shapes, with only named non-core unknowns limiting dependent modules?",
        "title": "Adopt bounded optional context and exact block-versus-limit rules"
      },
      {
        "approval_effect": [
          "Activity-average power cannot satisfy intensity provenance.",
          "Route, GPS, free-text, diagnosis, and provider payloads remain outside the contract."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Diagnosis, clearance, treatment, injury prevention, safety assurance, or personal performance prediction."
        ],
        "evidence_claim_ids": [
          "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
          "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
        ],
        "id": "science-safety-and-privacy-boundary",
        "parameter_names": [
          "trail_science_safety_and_privacy_boundary"
        ],
        "proposed_decision": "Carry the accepted v1 boundaries forward unchanged and apply them to every v2 field, receipt, and later implementation surface.",
        "question": "Should v2 preserve the adult nonclinical scope, symptom stop, split/sample intensity provenance, minimum normalized storage, and all prohibitions on personal guarantees and sensitive planning payloads?",
        "title": "Preserve the accepted nonclinical, intensity, claim, and privacy limits"
      },
      {
        "approval_effect": [
          "Exact DTO validation cannot silently become scientific prescription or runtime authority."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Any behavior listed as not_accepted or any lifecycle transition for v1."
        ],
        "evidence_claim_ids": [
          "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
        ],
        "id": "unresolved-values-and-authority-deferred",
        "parameter_names": [
          "trail_exact_values",
          "trail_non_science_authority_boundary"
        ],
        "proposed_decision": "Preserve literal not_accepted values and the inactive role boundary until separate specialist and human review authorizes a successor.",
        "question": "Should every technicality score, route inference, dose, progression, equivalence, prediction, provider, rollout, and activation behavior remain unaccepted?",
        "title": "Keep dose, scoring, equivalence, provider, and activation decisions deferred"
      }
    ],
    "reviewer_task": "Decide whether the six proposed v2 ontology actions preserve the accepted v1 evidence, uncertainty, safety, and privacy boundaries while making the inactive input contract deterministic enough to implement. Approve the sheet as a unit or request changes by item ID."
  },
  "evidence_claim_ids": [
    "trail-ontology.course-demand-is-multidimensional",
    "trail-ontology.uphill-downhill-demands-differ",
    "trail-ontology.technicality-and-downhill-vary-performance",
    "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
    "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose",
    "trail-ontology.environment-and-altitude-are-distinct-context",
    "trail-ontology.duration-and-fueling-practice-are-context"
  ],
  "evidence_review_ids": [
    "evidence-trail-running-goal-ontology-v1"
  ],
  "falsification_conditions": [
    "A malformed or stale v2 value is treated as confirmed, or client-provided provenance or history is accepted.",
    "A grade share falls into two buckets, the five shares do not total 10000, or grade becomes a difficulty, dose, equivalence, or prediction input.",
    "Footing comparison uses order, similarity, synonyms, inference, or a road category instead of exact set containment.",
    "A core unknown yields eligible_proposal, or a limited unknown silently enables or substitutes a module.",
    "Ascent and descent collapse, route or provider data enters the contract, free text is retained, or activity-average power drives intensity.",
    "A personal safety, finish, or performance claim appears, or the generated contract becomes active without separate implementation review and activation authority."
  ],
  "id": "sdr-trail-running-goal-ontology-v2",
  "model_parameters": [
    {
      "applies_to": "trail_course_demand_v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.uphill-downhill-demands-differ"
      ],
      "name": "trail_course_demand_schema",
      "rationale": "The evidence supports explicit distinct dimensions; field names, types, units, and the core/limited representation are reversible Praxys DTO choices selected to make missingness and replay unambiguous.",
      "value": {
        "event_identity": {
          "client_writable": false,
          "field": "event_id",
          "materiality": "core",
          "type": "server_owned_identifier"
        },
        "fields": {
          "aid_and_support": {
            "envelope": "known_or_unknown",
            "limited_module": "fueling",
            "materiality": "limited",
            "type": "bounded_object"
          },
          "course_footing": {
            "envelope": "known_or_unknown",
            "limited_module": "technical_terrain",
            "materiality": "limited_with_core_matching_when_known",
            "type": "nonempty_unordered_closed_set"
          },
          "distance_family": {
            "allowed": [
              "non_ultra"
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "closed_enum"
          },
          "distance_meters": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 49999,
            "minimum": 1,
            "type": "integer",
            "unit": "meters"
          },
          "environment_and_altitude": {
            "envelope": "known_or_unknown",
            "limited_module": "environment_altitude",
            "materiality": "limited",
            "type": "bounded_object"
          },
          "event_date": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "iso_date"
          },
          "event_format": {
            "allowed": [
              "single_day"
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "closed_enum"
          },
          "fixed_rope": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "strict_boolean"
          },
          "fueling_and_gastrointestinal_context": {
            "envelope": "known_or_unknown",
            "limited_module": "fueling",
            "materiality": "limited",
            "type": "bounded_object"
          },
          "grade_distribution": {
            "envelope": "known_or_unknown",
            "limited_module": "grade_specificity",
            "materiality": "limited",
            "type": "five_bucket_basis_point_object"
          },
          "hands_assist": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "strict_boolean"
          },
          "planning_duration_range": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "integer_range",
            "unit": "minutes"
          },
          "planning_intent": {
            "allowed": [
              "performance"
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "type": "closed_enum"
          },
          "total_ascent_m": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 20000,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          },
          "total_descent_m": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 20000,
            "minimum": 0,
            "type": "integer",
            "unit": "meters"
          }
        },
        "schema_id": "trail_course_demand_v2",
        "strict_unknown_fields_rejected": true
      }
    },
    {
      "applies_to": "every reviewable v2 course, constraint, and history field",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "trail_field_provenance",
      "rationale": "A strict server-owned provenance envelope prevents client-selected trust, hidden defaults, and stale source metadata. These are operational integrity controls, not published scientific values.",
      "value": {
        "assumption_requires_revision_bound_confirmation": true,
        "client_may_submit_history_hash": false,
        "client_may_submit_model_version": false,
        "client_may_submit_provenance": false,
        "client_may_submit_source_revision": false,
        "client_may_submit_source_timestamp": false,
        "field_restrictions": {
          "athlete_assumption_conditions": [
            "explicit_assumption"
          ],
          "event_id": "server_owned",
          "grade_distribution": [
            "athlete_stated",
            "course_verified",
            "unknown"
          ],
          "recent_history": [
            "history_observed"
          ]
        },
        "inferred_requires_server_model_version": true,
        "request_envelope": {
          "arbitrary_object_invalid": true,
          "empty_string_invalid": true,
          "guessed_zero_invalid": true,
          "known": {
            "exact_keys": [
              "state",
              "value"
            ],
            "schema_valid_value_required": true,
            "state_literal": "known"
          },
          "missing_state_invalid": true,
          "null_invalid_except_explicit_aid_gap_case": true,
          "numeric_values_must_be_finite": true,
          "sentinel_number_invalid": true,
          "unknown": {
            "exact_keys": [
              "state"
            ],
            "state_literal": "unknown",
            "value_forbidden": true
          }
        },
        "server_stamped_provenance_allowed": [
          "athlete_stated",
          "course_verified",
          "history_observed",
          "model_inferred",
          "explicit_assumption",
          "unknown"
        ],
        "unknown_is_preserved": true
      }
    },
    {
      "applies_to": "trail_course_demand_v2 core confirmation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.duration-and-fueling-practice-are-context"
      ],
      "name": "trail_planning_duration_range",
      "rationale": "Expected duration is relevant context, while the exact range shape is a reversible Product DTO and cannot be presented as a prediction.",
      "value": {
        "athlete_confirmed": true,
        "feasibility_verdict": false,
        "field": "planning_duration_range",
        "finish_time_prediction": false,
        "minimum_and_maximum_each": {
          "maximum": 1440,
          "minimum": 1
        },
        "minimum_strictly_less_than_maximum": true,
        "performance_promise": false,
        "purpose": "planning_context",
        "unit": "integer_minutes"
      }
    },
    {
      "applies_to": "known grade_distribution in trail_course_demand_v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ"
      ],
      "name": "trail_grade_distribution",
      "rationale": "Literature supports keeping signed grade demand explicit but does not validate these exact bins. The half-open intervals and basis-point sum are reversible deterministic description guardrails only.",
      "value": {
        "allowed_provenance": [
          "athlete_stated",
          "course_verified"
        ],
        "buckets": {
          "below_neg_10": {
            "interval": "g < -10%",
            "upper_bound_percent": -10,
            "upper_inclusive": false
          },
          "neg_10_to_below_neg_3": {
            "interval": "-10% <= g < -3%",
            "lower_bound_percent": -10,
            "lower_inclusive": true,
            "upper_bound_percent": -3,
            "upper_inclusive": false
          },
          "neg_3_to_below_pos_3": {
            "interval": "-3% <= g < 3%",
            "lower_bound_percent": -3,
            "lower_inclusive": true,
            "upper_bound_percent": 3,
            "upper_inclusive": false
          },
          "pos_10_and_above": {
            "interval": "g >= 10%",
            "lower_bound_percent": 10,
            "lower_inclusive": true
          },
          "pos_3_to_below_pos_10": {
            "interval": "3% <= g < 10%",
            "lower_bound_percent": 3,
            "lower_inclusive": true,
            "upper_bound_percent": 10,
            "upper_inclusive": false
          }
        },
        "descriptive_only": true,
        "difficulty_score": false,
        "each_share_minimum": 0,
        "each_share_type": "integer",
        "equivalence_or_prediction_input": false,
        "exact_sum": 10000,
        "known_value_exact_keys": [
          "below_neg_10",
          "neg_10_to_below_neg_3",
          "neg_3_to_below_pos_3",
          "pos_3_to_below_pos_10",
          "pos_10_and_above"
        ],
        "ordering_semantic": false,
        "route_or_model_inference": false,
        "safety_threshold": false,
        "unit": "basis_points_of_course_distance",
        "workout_dose_input": false
      }
    },
    {
      "applies_to": "course, access, and observed-history footing plus v2 hazard gates",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.technicality-and-downhill-vary-performance",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "name": "trail_footing_and_hazard_contract",
      "rationale": "Footing and hazards must remain explicit, but the exact vocabulary and gates are Product-selected operational categories rather than validated technicality or safety scores.",
      "value": {
        "hazard_gates": {
          "fixed_rope": {
            "eligible_value": "known_false",
            "envelope": "known_or_unknown",
            "known_true_result": "policy_unavailable.technical_features_outside_v2",
            "known_value_type": "strict_boolean",
            "unknown_result": "clarification_required.material_course_demand_unknown"
          },
          "hands_assist": {
            "eligible_value": "known_false",
            "envelope": "known_or_unknown",
            "known_true_result": "policy_unavailable.technical_features_outside_v2",
            "known_value_type": "strict_boolean",
            "unknown_result": "clarification_required.material_course_demand_unknown"
          },
          "reducible_to_ordinary_footing": false,
          "technical_skill_or_safety_score": false
        },
        "ordinary_footing": {
          "allowed": [
            "firm_smooth",
            "loose_gravel",
            "mud",
            "rocks_or_roots",
            "built_steps",
            "water_crossing"
          ],
          "difficulty_score": false,
          "duplicates_invalid": true,
          "free_text_allowed": false,
          "other_value_allowed": false,
          "type": "nonempty_unordered_set",
          "unknown_members_invalid": true
        }
      }
    },
    {
      "applies_to": "non_ultra_trail_constraints_v2 and owner-scoped readiness",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "name": "trail_training_constraints_schema",
      "rationale": "Schedule and terrain access must be explicit and recent history must remain server-derived. The exact closed DTO is an operational guardrail; it does not establish a safe terrain dose.",
      "value": {
        "client_may_submit_or_attest_history": false,
        "client_reviewable_fields": {
          "accessible_footing": {
            "envelope": "known_or_unknown",
            "materiality": "core_when_course_footing_known",
            "missing_required_member_result": "readiness_blocked.insufficient_terrain_access",
            "type": "nonempty_unordered_closed_set",
            "vocabulary": "trail_footing_and_hazard_contract.ordinary_footing.allowed"
          },
          "adult_nonclinical_scope_confirmed": {
            "envelope": "known_or_unknown",
            "false_result": "policy_unavailable.unsupported_population_or_intent",
            "materiality": "core",
            "required_value_for_eligibility": true,
            "type": "strict_boolean",
            "unknown_result": "clarification_required.adult_scope_or_constraints_unconfirmed"
          },
          "available_weekdays": {
            "allowed_iso_weekdays": [
              1,
              2,
              3,
              4,
              5,
              6,
              7
            ],
            "envelope": "known_or_unknown",
            "materiality": "core",
            "minimum_members": 1,
            "type": "unique_unordered_set",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "controlled_downhill_access": {
            "duration_distance_grade_speed_or_repeat_fields_allowed": false,
            "envelope": "known_or_unknown",
            "false_result": "readiness_blocked.insufficient_terrain_access",
            "materiality": "core",
            "type": "strict_boolean",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "current_symptom_stop": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "stop_value": true,
            "true_result": "readiness_blocked.current_symptom_stop",
            "type": "strict_boolean",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "maximum_session_duration_min": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 1440,
            "minimum": 1,
            "not_greater_than": "weekly_time_limit_min",
            "type": "integer",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "nontechnical_three_minute_uphill_access": {
            "envelope": "known_or_unknown",
            "false_result": "readiness_blocked.insufficient_terrain_access",
            "materiality": "core",
            "type": "strict_boolean",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "performance_intent_confirmed": {
            "envelope": "known_or_unknown",
            "false_result": "policy_unavailable.unsupported_population_or_intent",
            "materiality": "core",
            "required_value_for_eligibility": true,
            "type": "strict_boolean",
            "unknown_result": "clarification_required.adult_scope_or_constraints_unconfirmed"
          },
          "preferred_longest_weekday": {
            "allowed": [
              1,
              2,
              3,
              4,
              5,
              6,
              7
            ],
            "conflict_result": "clarification_required.contradictory_input",
            "omitted_means_no_preference": true,
            "type": "optional_iso_weekday",
            "when_present_must_be_in": "available_weekdays"
          },
          "unavailable_dates": {
            "all_dates_within_requested_14_day_horizon": true,
            "empty_known_set_allowed": true,
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum_members": 14,
            "type": "sorted_unique_iso_date_set",
            "unknown_result": "clarification_required.training_constraints_missing"
          },
          "weekly_time_limit_min": {
            "envelope": "known_or_unknown",
            "materiality": "core",
            "maximum": 10080,
            "minimum": 1,
            "type": "integer",
            "unknown_result": "clarification_required.training_constraints_missing"
          }
        },
        "history_provenance": "history_observed",
        "schema_id": "non_ultra_trail_constraints_v2",
        "server_derived_history_fields": [
          "recent_running_continuity",
          "recent_ascent_exposure",
          "recent_descent_exposure",
          "recently_observed_footing"
        ]
      }
    },
    {
      "applies_to": "optional v2 course context only",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.environment-and-altitude-are-distinct-context",
        "trail-ontology.duration-and-fueling-practice-are-context"
      ],
      "name": "trail_optional_context_shapes",
      "rationale": "Environment and fueling are relevant context, while every exact bound and enum is a reversible minimization and validation choice. None establishes an exposure, equipment, fueling, gastrointestinal, or safety prescription.",
      "value": {
        "aid_and_support": {
          "aid_station_count": {
            "maximum": 50,
            "minimum": 0,
            "type": "integer"
          },
          "aid_support_mode": {
            "known_allowed": [
              "organized_aid",
              "mixed",
              "self_supported"
            ]
          },
          "food_availability": {
            "known_allowed": [
              "none",
              "some_stations",
              "all_stations"
            ],
            "unknown_uses_field_envelope": true
          },
          "mandatory_gear": {
            "allowed": [
              "water_carry",
              "food_carry",
              "weather_shell",
              "lighting",
              "navigation_device",
              "other_required"
            ],
            "other_required_has_no_label_or_free_text": true,
            "type": "unordered_closed_set"
          },
          "max_aid_station_gap_km": {
            "maximum": 50,
            "minimum": 0.1,
            "null_allowed_only_for": "no_applicable_gap",
            "type": "finite_number"
          },
          "water_availability": {
            "known_allowed": [
              "none",
              "some_stations",
              "all_stations"
            ],
            "unknown_uses_field_envelope": true
          }
        },
        "environment_and_altitude": {
          "conditions_basis": {
            "athlete_assumption_provenance": "explicit_assumption",
            "athlete_assumption_requires_confirmation": true,
            "known_allowed": [
              "organizer_information",
              "seasonal_expectation",
              "athlete_assumption"
            ]
          },
          "humidity_range_pct": {
            "maximum": 100,
            "minimum": 0,
            "minimum_may_equal_maximum": true,
            "type": "finite_number_range"
          },
          "maximum_altitude_m": {
            "maximum": 9000,
            "minimum": -500,
            "type": "integer"
          },
          "sun_exposure": {
            "known_allowed": [
              "low",
              "mixed",
              "high"
            ],
            "unknown_uses_field_envelope": true
          },
          "temperature_range_c": {
            "maximum": 55,
            "minimum": -30,
            "minimum_may_equal_maximum": true,
            "type": "finite_number_range"
          },
          "wind_exposure": {
            "known_allowed": [
              "sheltered",
              "mixed",
              "exposed"
            ],
            "unknown_uses_field_envelope": true
          }
        },
        "fixed_prescription_from_known_context": false,
        "fueling_and_gastrointestinal_context": {
          "gastrointestinal_experience": {
            "known_allowed": [
              "no_plan_altering_issue",
              "plan_altering_issue"
            ],
            "non_diagnostic": true,
            "unknown_uses_field_envelope": true
          },
          "intake_form": {
            "known_allowed": [
              "none",
              "fluids_only",
              "carbohydrate_drink",
              "mixed_food_and_drink"
            ]
          },
          "longest_practiced_duration_min": {
            "maximum": 1440,
            "minimum": 0,
            "type": "integer"
          },
          "practice_sessions_last_42_days": {
            "maximum": 84,
            "minimum": 0,
            "type": "integer"
          }
        },
        "notes_labels_urls_provider_ids_or_embedded_unit_strings_allowed": false
      }
    },
    {
      "applies_to": "v2 capability matching and readiness receipts",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional",
        "trail-ontology.technicality-and-downhill-vary-performance"
      ],
      "name": "trail_unknown_and_materiality_policy",
      "rationale": "This exact Product-selected block-versus-limit mapping keeps material missingness visible without manufacturing certainty or broadening the accepted Science scope.",
      "value": {
        "bounded_alternative_requires_separate_review": true,
        "core_fields": [
          "event_id",
          "event_date",
          "distance_meters",
          "total_ascent_m",
          "total_descent_m",
          "planning_duration_range",
          "event_format",
          "distance_family",
          "planning_intent",
          "hands_assist",
          "fixed_rope",
          "adult_nonclinical_scope_confirmed",
          "performance_intent_confirmed",
          "current_symptom_stop",
          "available_weekdays",
          "weekly_time_limit_min",
          "maximum_session_duration_min",
          "unavailable_dates",
          "preferred_longest_weekday_consistency_when_present",
          "nontechnical_three_minute_uphill_access",
          "controlled_downhill_access",
          "accessible_footing_when_course_footing_known",
          "recent_running_continuity",
          "recent_ascent_exposure",
          "recent_descent_exposure",
          "recently_observed_footing_when_course_footing_known"
        ],
        "known_value_automatically_enables_module": false,
        "limited_module_may_substitute_generic_or_road_behavior": false,
        "limited_modules_sorted_allowed": [
          "environment_altitude",
          "fueling",
          "grade_specificity",
          "technical_terrain"
        ],
        "limited_unknown_mapping": {
          "aid_and_support": "fueling",
          "course_footing": "technical_terrain",
          "environment_and_altitude": "environment_altitude",
          "fueling_and_gastrointestinal_context": "fueling",
          "grade_distribution": "grade_specificity"
        },
        "material_unknown_result": [
          "clarification_required",
          "policy_unavailable"
        ],
        "unknown_defaults_to_easy": false,
        "unknown_defaults_to_nontechnical": false,
        "unknown_defaults_to_road": false,
        "unknown_defaults_to_zero": false
      }
    },
    {
      "applies_to": "v2 course, access, history, and intensity boundaries",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.technicality-and-downhill-vary-performance",
        "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone"
      ],
      "name": "trail_distinct_demand_invariants",
      "rationale": "Distinct demands follow the evidence; exact set containment is a deterministic conservative matching guardrail, not a validated safety or similarity model.",
      "value": {
        "activity_average_power_allowed": false,
        "ascent_and_descent_separate": true,
        "downhill_history_required_when_descent_material": true,
        "footing_set_containment": {
          "access_failure_reason": "readiness_blocked.insufficient_terrain_access",
          "access_requirement": "C subset_of A",
          "accessible_set_symbol": "A",
          "applies_only_when_course_footing_known": true,
          "course_set_symbol": "C",
          "history_failure_reason": "readiness_blocked.insufficient_comparable_trail_history",
          "history_requirement": "C subset_of H",
          "observed_history_set_symbol": "H",
          "similarity_synonyms_or_model_inference_allowed": false
        },
        "grade_distribution_descriptive_only": true,
        "heart_rate_alone_sufficient_for_hilly_intensity": false,
        "level_pace_alone_sufficient_for_hilly_intensity": false,
        "technicality_score_allowed": false,
        "universal_distance_vertical_equivalence": false
      }
    },
    {
      "applies_to": "every v2 mutation, readiness receipt, and later proposal",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "trail_revision_and_confirmation",
      "rationale": "Exact revisions prevent stale confirmation from silently acquiring new meaning. This is an operational replay and user-control guardrail.",
      "value": {
        "confirm_all_allowed": false,
        "confirmation_invalidated_by": [
          "value_change",
          "known_unknown_state_change",
          "server_stamped_source_change",
          "source_revision_change"
        ],
        "confirmation_is_truth_safety_or_eligibility_attestation": false,
        "confirmation_scope": "exact_visible_field_or_section_revision",
        "mutation_creates_new_immutable_revision": true,
        "proposal_binds_same_exact_revisions": true,
        "readiness_binds_exact_revisions": [
          "goal",
          "course",
          "constraints",
          "history_snapshot",
          "policy",
          "generator"
        ],
        "stale_confirmation_rebound_allowed": false,
        "stale_source_revision_rebound_allowed": false
      }
    },
    {
      "applies_to": "all v2 science, storage, API, client, audit, and deletion surfaces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "name": "trail_science_safety_and_privacy_boundary",
      "rationale": "These preserve the accepted v1 nonclinical, intensity, claim, and minimization boundaries while making the v2 storage exclusion explicit.",
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "authenticated_owner_scoped_reset_export_and_deletion_required": true,
        "diagnosis_treatment_clearance_or_return_to_sport": false,
        "forbidden_collection_or_persistence": [
          "gps_points",
          "route_files",
          "polylines",
          "maps",
          "inferred_course_geometry",
          "course_source_urls",
          "scraped_course_content",
          "provider_request_or_response_payloads",
          "provider_account_activity_or_workout_ids",
          "device_identifiers",
          "free_text_health_symptom_fueling_surface_or_course_narratives",
          "diagnoses_or_medical_clearance",
          "injury_probability",
          "activity_average_power",
          "road_equivalent_distance_pace_or_load"
        ],
        "generic_audit_or_telemetry_may_copy_sensitive_payloads": false,
        "inferred_and_athlete_stated_fields_correctable_and_deletable": true,
        "minimum_age_years": 18,
        "minimum_normalized_storage_only": true,
        "nonclinical_only": true,
        "performance_injury_or_safety_guarantee": false,
        "permitted_persisted_categories": [
          "canonical_field_values_and_unknown_states",
          "server_stamped_provenance",
          "source_and_field_or_section_revisions",
          "confirmations",
          "owner_scoped_history_snapshot_reference_and_hash",
          "readiness_and_proposal_binding_digests"
        ],
        "personal_finish_probability": false,
        "suggestion_only": true,
        "symptom_stop_required": true,
        "valid_intensity_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    {
      "applies_to": "unresolved ontology and prescription values",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.uphill-downhill-demands-differ",
        "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose"
      ],
      "name": "trail_exact_values",
      "rationale": "The accepted evidence supports explicit dimensions but not universal scoring, inference, equivalence, prediction, progression, or dose. Only the closed validation DTO is proposed here.",
      "value": {
        "core_and_limited_materiality": "operational_guardrail_only",
        "course_domain_bounds": "product_scope_and_operability_guardrail_only",
        "distance_vertical_conversion": "not_accepted",
        "downhill_progression": "not_accepted",
        "environment_or_altitude_dose": "not_accepted",
        "finish_time_prediction": "not_accepted",
        "footing_vocabulary": "descriptive_operational_guardrail_only",
        "fueling_amount_or_frequency": "not_accepted",
        "optional_context_bounds": "operational_guardrail_only",
        "planning_duration_range_shape": "operational_guardrail_only",
        "road_trail_equivalence": "not_accepted",
        "route_or_provider_inference": "not_accepted",
        "schedule_capacity_bounds": "product_scope_and_operability_guardrail_only",
        "signed_grade_buckets": "descriptive_operational_guardrail_only",
        "technical_terrain_dose": "not_accepted",
        "technicality_score": "not_accepted",
        "vertical_progression": "not_accepted"
      }
    },
    {
      "applies_to": "all work outside the Science role",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "trail_non_science_authority_boundary",
      "rationale": "A Science successor cannot originate or widen Product, Design, Engineering, Trust, Operations, provider, rollout, or activation authority.",
      "value": {
        "deployment": "not_accepted",
        "implementation_review": "required",
        "lifecycle_supersession": "not_accepted",
        "owner_only_dogfood": "not_accepted",
        "product_and_experience_dependency": "human_acceptance_required",
        "product_visibility_or_catalog": "not_accepted",
        "production_data_use": "not_accepted",
        "provider_mapping_or_delivery": "not_accepted",
        "runtime_activation": "not_accepted",
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
  "model_version": "trail-course-demand-v2",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Collect and persist only normalized typed values, explicit unknown states, server provenance, revisions, confirmations, and owner-scoped replay references.",
    "Do not ingest GPS, routes, maps, source URLs, scraped content, provider payloads or identifiers, device identifiers, or free-text planning narratives.",
    "Reset invalidates confirmation and creates a new revision; export and deletion include the current owner-scoped v2 state under existing data-rights controls.",
    "No public sharing, cross-user aggregate, administrator planning access, or value telemetry is authorized."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Keep the ambiguous v1 object fields and let each caller interpret them",
      "rationale": "Caller-specific interpretation would make missingness, provenance, materiality, and replay nondeterministic."
    },
    {
      "alternative": "Infer grade, footing, or technical demand from a route or provider payload",
      "rationale": "v2 does not collect those payloads, and the evidence does not validate a universal inference or technicality score."
    },
    {
      "alternative": "Require every optional course descriptor before any proposal",
      "rationale": "Core-versus-limited materiality can preserve uncertainty without hiding it or inventing a dependent module."
    },
    {
      "alternative": "Treat an unknown or inaccessible Trail field as ordinary road running",
      "rationale": "That would erase course-specific demand and violate the accepted no-road- fallback boundary."
    }
  ],
  "safety_implications": [
    "Every core unknown or failed gate prevents an eligible proposal; only named non-core unknowns can limit a dependent module.",
    "Uphill, downhill, ordinary footing, hazards, altitude, heat, support, and fueling context remain distinct when applicable.",
    "Hands-assist or fixed-rope use stays outside v2; unknown hazard gates require clarification.",
    "Current symptoms stop performance optimization without creating a diagnosis.",
    "Intensity provenance uses activity splits or samples, never activity-average power."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Define the strict v2 Trail course-demand and constraint envelope",
  "user_facing_claim_limits": [
    "Do not claim the exact v2 DTO, bins, footing vocabulary, bounds, or materiality map is scientifically optimal or validated as a safety rule.",
    "Do not claim planning duration is a finish-time prediction, feasibility verdict, or performance promise.",
    "Do not claim distance and ascent alone describe Trail demand or present a universal road-equivalent distance, grade, ascent, or descent conversion.",
    "Do not present unknown footing, hazard, environment, support, fueling, or gastrointestinal context as known, easy, safe, or average.",
    "Do not present a technicality score, personal finish probability, performance guarantee, injury-prevention guarantee, diagnosis, treatment, or clearance."
  ],
  "validation_plan": [
    "Validate every closed enum, set, integer, finite number, range relation, explicit unknown state, and field-specific provenance rule deterministically.",
    "Boundary-test all five signed-grade intervals and require nonnegative integer shares summing exactly to 10000.",
    "Replay reordered footing and weekday sets and verify one canonical digest; reject duplicates, unknown members, synonyms, and free text.",
    "Verify exact course-footing containment against both accessible and observed-history sets and preserve the distinct access and history failures.",
    "Mutate every field value, state, and server source revision and verify the prior confirmation and readiness binding becomes stale.",
    "Exercise every core unknown and limited unknown and verify no road policy, hidden default, provider behavior, or success-shaped plan is selected.",
    "Generate the matching review packet and inactive machine contract and bind any later approval to their exact digests."
  ],
  "version": 2
}
```

</details>
