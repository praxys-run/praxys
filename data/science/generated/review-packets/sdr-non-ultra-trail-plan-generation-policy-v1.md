# Science decision review packet: Use a history-anchored 14-day non-ultra trail performance block

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-non-ultra-trail-plan-generation-policy-v1`
- **Lifecycle:** `draft`
- **Model version:** `non-ultra-trail-plan-generation-policy-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:afc9fecefd55c699a8fdf3d3ab885968c7f7981fadbcba7bf09494fdfcdcd606`
- **Contract digest:** `sha256:534d292e7e770fff6c9078ef2adf1d1b881cb226d510a839013a170365184973`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the narrow population, course-specific modular policy, reversible fourteen-day generator guardrails, and hard scientific boundaries should be accepted while taper and the listed unsupported scope remain deferred.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `narrow-course-matched-scope` — Accept the narrow history-rich course-matched scope

- **Question:** Should the policy apply only to nonclinical adults with stable recent history, comparable exposure, performance intent, confirmed constraints, and a complete accepted trail course-demand tuple?
- **Proposed decision:** Accept that narrow scope and return typed unavailable results for first-completion, sparse-history, ultra, multi-day, clinical, or materially unknown contexts.
- **Approval means:**
  - A future generator may be designed only inside this tuple.
  - Goal capture remains independent from generator availability.
- **This does not authorize:**
  - A schedule, threshold, implementation, pilot, or activation.

<details><summary>Traceability: 3 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `trail_policy_scope_and_dependencies`, `trail_policy_required_inputs`, `trail_policy_typed_outcomes`
- **Evidence claims:** `non-ultra-trail.course-specific-policy-required`, `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.goal-relevant-current-capability-task-specific`

</details>

#### `modular-specificity` — Accept a conditional modular trail policy

- **Question:** Should terrain specificity, ascent, descent, hiking, strength, taper, fueling, and environment remain separate modules enabled only by matching evidence and access?
- **Proposed decision:** Accept the modular structure without selecting an exact dose or claiming one module is universally required or superior.
- **Approval means:**
  - Missing module-specific context may limit that module without inventing equivalence.
  - Ascent and descent exposure remain separately reviewable.
- **This does not authorize:**
  - A fixed weekly mix, vertical target, downhill dose, hiking threshold, or strength prescription.

<details><summary>Traceability: 2 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `trail_policy_modular_structure`, `trail_policy_evidence_use`
- **Evidence claims:** `non-ultra-trail.uphill-downhill-require-distinct-handling`, `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.taper-direction-indirect`, `non-ultra-trail.fueling-duration-and-practice-context`

</details>

#### `hard-science-boundaries` — Accept hard safety, intensity, and athlete-control boundaries

- **Question:** Should the policy prohibit road fallback, target-gap dose escalation, catch-up, universal equivalence, activity-average-power intensity, diagnosis, and personal finish or injury guarantees?
- **Proposed decision:** Accept those prohibitions and require athlete review and exact-version adoption before any canonical plan or provider delivery.
- **Approval means:**
  - Deterministic validation remains authoritative.
  - Splits or samples, not activity-average power, supply historical intensity evidence.
- **This does not authorize:**
  - Medical clearance, an individual probability, or automatic mutation or delivery.

<details><summary>Traceability: 1 contract group, 5 evidence claims</summary>

- **Contract groups covered:** `trail_policy_hard_boundaries`
- **Evidence claims:** `non-ultra-trail.hr-and-road-pace-not-sole-targets`, `non-ultra-trail.injury-fatigue-no-safe-dose`, `non-ultra-trail.observed-load-does-not-prove-prescription`, `eligibility.fixed-progression-and-acwr-not-safety-laws`, `eligibility.current-symptoms-support-stop-not-clearance`

</details>

#### `initial-generator-guardrails` — Accept the reversible early-block generator values

- **Question:** Are the fourteen-day execution window, seven-day review, bounded history qualification, no-initial-load-progression construction, targetless controlled-uphill template, intensity spacing, and course-exposure caps compatible with the evidence when labelled as Praxys guardrails rather than published prescriptions?
- **Proposed decision:** Accept those values for an early, history-anchored block only. Require deterministic replay and prospectively evaluate exclusions, edits, withdrawals, and invariant failures before any wider scope.
- **Approval means:**
  - Engineering may prepare an inactive deterministic generator inside the exact reviewed envelope.
  - The first owner can receive early rolling blocks while event-near taper remains unavailable.
- **This does not authorize:**
  - Biological optimality, progression above history, taper, a fixed fueling or strength dose, implementation acceptance, rollout, or activation.

<details><summary>Traceability: 7 contract groups, 6 evidence claims</summary>

- **Contract groups covered:** `trail_policy_execution_and_reassessment`, `trail_policy_history_guardrails`, `trail_policy_schedule_construction`, `trail_policy_workout_templates`, `trail_policy_intensity_and_spacing`, `trail_policy_course_exposure_caps`, `trail_policy_runtime_evaluation`
- **Evidence claims:** `non-ultra-trail.course-specific-policy-required`, `non-ultra-trail.uphill-downhill-require-distinct-handling`, `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.taper-direction-indirect`, `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.fixed-progression-and-acwr-not-safety-laws`

</details>

### Decisions explicitly deferred

#### `exact-generation-values-deferred` — Defer taper, progression, fixed dose, and broader scope

- **Question:** Should progression above recent exposure, taper, back-to-back sessions, fixed fueling, hiking or strength doses, and universal target zones remain unaccepted?
- **Proposed decision:** Keep every remaining value literal not_accepted until a successor decision compares reversible options and validation evidence.
- **Approval means:**
  - The early-block implementation cannot silently expand into event-near or higher-load planning.
- **This does not authorize:**
  - Inferring values from road policies, study protocols, common practice, or AI output.

<details><summary>Traceability: 2 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `trail_policy_event_and_taper`, `trail_policy_deferred_scope`
- **Evidence claims:** `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.injury-fatigue-no-safe-dose`, `non-ultra-trail.taper-direction-indirect`, `non-ultra-trail.fueling-duration-and-practice-context`

</details>

#### `implementation-rollout-deferred` — Defer implementation, owner pilot, Garmin, and activation

- **Question:** Should storage, APIs, clients, an owner-only pilot, Garmin mapping, rollout, monitoring, and runtime activation remain outside this SDR?
- **Proposed decision:** Keep runtime inactive and require accepted Product, Design, implementation, verification, and Operations authority.
- **Approval means:**
  - Science approval alone cannot expose or execute a trail plan.
- **This does not authorize:**
  - User visibility, data collection, plan generation, adoption, provider dispatch, deployment, or activation.

<details><summary>Traceability: 1 contract group, 0 evidence claims</summary>

- **Contract groups covered:** `trail_policy_non_science_authority`
- **Evidence claims:** _None; product or lifecycle boundary only_

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve the narrow history-rich adult non-ultra trail performance scope, exact trail_course_demand_v1 matching, conditional terrain/downhill/ strength/fueling modules, suggestion-only athlete control, and typed fail-closed outcomes. I approve keeping uphill and downhill distinct and prohibiting road fallback, universal vertical conversion, fixed safe dose, activity-average-power intensity use, and personal finish or safety guarantees. I also approve the fourteen-day block, seven-day review, history qualification, no-initial-load-progression schedule, one controlled quality exposure, seventy-five-percent low-intensity floor, and course- exposure caps as labelled reversible Praxys guardrails. This authorizes only a separately reviewed inactive implementation. It does not approve taper, progression above history, fixed fueling or strength dose, an owner-only pilot, provider delivery, rollout, deployment, or activation.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-non-ultra-trail-plan-generation-policy-v1`
- Digest: `sha256:afc9fecefd55c699a8fdf3d3ab885968c7f7981fadbcba7bf09494fdfcdcd606`

> I approve the narrow history-rich adult non-ultra trail performance scope, exact trail_course_demand_v1 matching, conditional terrain/downhill/ strength/fueling modules, suggestion-only athlete control, and typed fail-closed outcomes. I approve keeping uphill and downhill distinct and prohibiting road fallback, universal vertical conversion, fixed safe dose, activity-average-power intensity use, and personal finish or safety guarantees. I also approve the fourteen-day block, seven-day review, history qualification, no-initial-load-progression schedule, one controlled quality exposure, seventy-five-percent low-intensity floor, and course- exposure caps as labelled reversible Praxys guardrails. This authorizes only a separately reviewed inactive implementation. It does not approve taper, progression above history, fixed fueling or strength dose, an owner-only pilot, provider delivery, rollout, deployment, or activation.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:afc9fecefd55c699a8fdf3d3ab885968c7f7981fadbcba7bf09494fdfcdcd606","subject_id":"sdr-non-ultra-trail-plan-generation-policy-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If its ontology dependency and this evidence and decision are separately accepted, Praxys may prepare a deterministic, suggestion-only policy for nonclinical adults with stable recent history, comparable trail exposure, performance intent, an athlete-confirmed trail_course_demand_v1, and explicit schedule constraints. Matching is course-specific. Uphill, downhill, technical terrain, expected duration, environment, support, terrain access, and fueling practice remain distinct inputs. Missing material inputs yield a typed no-plan or bounded alternative, never a road fallback. Trail-specific, strength, hiking, taper, and fueling modules remain conditional and uncertainty-labelled. The proposed first block commits fourteen calendar days, reviews after seven completed days, uses eight completed history weeks, requires four usable weeks and recent direct hilly or trail exposure, never plans above recent median weekly duration or corresponding ascent/descent exposure, and allows at most one nonconsecutive controlled quality exposure per seven-day unit. These values are reversible Praxys guardrails rather than published optima or safety laws. Taper, progression above history, fixed fueling, hiking or strength dose, back-to-back sessions, and universal HR, pace, power, or RPE targets remain unaccepted. No personal finish probability or safety guarantee is accepted. Science acceptance would authorize only a separately reviewed inactive implementation inside these bounds; owner-only rollout, provider delivery, and runtime activation remain separate decisions.

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

#### `non-ultra-trail.course-specific-policy-required` — moderate

Trail performance and training demand are course-specific and multifactorial. A policy must match an explicit course-demand vector and comparable exposure rather than distance, level pace, or one physiological marker alone.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `de-waal-2021-performance-review`, `pastor-2022-distance-determinants`, `bjorklund-2019-short-trail`
- **Limitations:** Associations and prediction models do not establish causal training dose.; The reviewed courses and populations are heterogeneous.

#### `non-ultra-trail.uphill-downhill-require-distinct-handling` — moderate

Uphill and downhill running have materially different metabolic, mechanical, cardiovascular, and neuromuscular profiles. Training history and proposed exposure should therefore preserve ascent, descent, grade, and technical context separately.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `bjorklund-2019-short-trail`, `lemire-2021-downhill-fatigue`, `lemire-2022-slope-energy-cost`
- **Limitations:** Small studies at specific grades do not establish universal progression.; Comparable oxygen uptake does not imply comparable mechanical cost.

#### `non-ultra-trail.hr-and-road-pace-not-sole-targets` — low

Heart rate can lag or fail to reflect rapid slope-dependent changes, and level-running pace does not preserve trail mechanical demand. Neither should be the sole driver of a hilly or technical prescription.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `born-2017-hilly-intensity`, `lemire-2022-slope-energy-cost`
- **Limitations:** This does not prohibit contextual athlete-specific HR or pace use.; No reviewed evidence validates one universal trail RPE, power, HR, or pace equivalence.

#### `non-ultra-trail.training-specificity-promising-not-prescriptive` — low

Trail-specific and multimodal training can be plausible modules, but the reviewed interventions are too small and heterogeneous to establish a universal session mix, weekly frequency, vertical dose, or superiority over road training.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `drum-2023-trail-road-rct`, `panthong-2026-masters-training`
- **Limitations:** The trail-versus-road study found no significant group-by-time interactions.; The masters trial does not define a universal plan or transfer to every age and course.

#### `non-ultra-trail.injury-fatigue-no-safe-dose` — low

Trail racing is associated with heterogeneous injury, illness, muscular, and neuromuscular stress observations, but current evidence does not establish a universal injury-preventive plan, safe downhill dose, recovery interval, or progression percentage.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `viljoen-2022-risk-factors`, `garcia-valiente-2026-damage-review`
- **Limitations:** Associations do not establish causality or individual safety.; Race biomarkers cannot be converted into medical clearance or training readiness.

#### `non-ultra-trail.observed-load-does-not-prove-prescription` — very_low

Observed trail workload and pacing associations may inform descriptive context, but they do not validate ACWR zones, fixed taper behavior, activity-average-power intensity, or an individual causal prescription.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `matos-2020-load-profiles`
- **Limitations:** Small observational male sample and heterogeneous events.; Correlation and group averages do not select individual dose.

#### `non-ultra-trail.taper-direction-indirect` — moderate

Broader endurance evidence supports a pre-event reduction in training volume while generally retaining intensity and frequency, but it does not validate one trail-specific taper duration, reduction percentage, or personal performance gain.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `wang-2023`
- **Limitations:** Mixed sports and protocols rather than direct non-ultra trail trials.; Subgroup estimates cannot be treated as an individual optimum.

#### `non-ultra-trail.fueling-duration-and-practice-context` — moderate

During-exercise carbohydrate strategy depends on expected duration and tolerance, and practice can reduce gastrointestinal problems in some endurance contexts. Distance alone does not select a fueling prescription.

- **Evidence Review:** `evidence-non-ultra-trail-plan-generation-policy-v1`
- **Sources:** `burke-2011`, `martinez-2023`
- **Limitations:** Numeric guidance is not trail-course specific.; Practice does not guarantee tolerance or performance for an individual.

#### `eligibility.recent-history-anchor-without-universal-threshold` — moderate

Abrupt weekly or single-session distance increases are associated with higher running-related injury rates, while the reviewed evidence is heterogeneous and does not establish one universal safe increase. Recent consistency and recent longest-session history are therefore relevant eligibility dimensions, not validated prescription cutoffs.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `damsted-2019`, `frandsen-2025`, `correia-2024`
- **Limitations:** These studies do not establish causation or an individual safety threshold.; The weekly association was significant at 21 days but not later follow-up points.; The single-session cohort used self-reported injury outcomes and did not validate an automatic plan rule.; The umbrella review found only critically low or low-quality systematic reviews.

#### `eligibility.fixed-progression-and-acwr-not-safety-laws` — moderate

A novice-running program based on the 10 percent rule did not reduce running-related injury compared with a standard program, and acute-to- chronic workload-ratio zones lack established causal support for individual training recommendations. Neither should be used as a universal plan-generation safety law.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `buist-2008`, `impellizzeri-2020`
- **Limitations:** The trial does not show that every faster progression is safe.; Injury outcomes do not determine an optimal performance progression.; The critique does not make recent training history irrelevant or validate a replacement threshold.

#### `eligibility.goal-relevant-current-capability-task-specific` — moderate

Current performance evidence is most interpretable when the task and protocol match the intended outcome. Fixed-distance time trials are generally more reliable than time-to-exhaustion tests, supporting an explicit goal-relevant current-capability axis rather than automatic substitution from a different test protocol.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `currell-2008`, `laursen-2007`
- **Limitations:** The sources do not make solo time trials and races automatically interchangeable.; They do not validate a universal baseline freshness cutoff.; They do not define Praxys capability-state labels or a cross-distance conversion.

#### `eligibility.current-symptoms-support-stop-not-clearance` — low

Current signs and symptoms are relevant before vigorous exercise. This supports a conservative, non-medical fail-closed stop before a vigorous plan or maximal field-test path, but does not support diagnosis, treatment, clearance, or return-to-sport advice.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `riebe-2015`
- **Limitations:** The source is not a validation study of Praxys symptom wording or automatic generation.; Absence of a reported symptom does not establish that vigorous exercise is risk-free.; The policy cannot infer a medical state from training behavior.

### Reviewed parameters

#### `trail_policy_scope_and_dependencies` — guardrail

- **Applies to:** non-ultra-trail-plan-generation-policy-v1
- **Evidence claims:** `non-ultra-trail.course-specific-policy-required`, `eligibility.goal-relevant-current-capability-task-specific`
- **Rationale:** The narrow tuple avoids transferring sparse trail evidence into ultra, first-completion, medical, or materially different contexts.
- **Exact value:**

```json
{
  "clinical_or_return_to_sport": false,
  "distance_family": "non_ultra",
  "event_format": "single_day",
  "intent": "performance",
  "minimum_age_years": 18,
  "requires_accepted_ontology": "sdr-trail-running-goal-ontology-v1",
  "requires_course_demand_schema": "trail_course_demand_v1",
  "suggestion_only": true
}
```

#### `trail_policy_required_inputs` — guardrail

- **Applies to:** capability matching and readiness
- **Evidence claims:** `non-ultra-trail.course-specific-policy-required`, `non-ultra-trail.uphill-downhill-require-distinct-handling`, `eligibility.recent-history-anchor-without-universal-threshold`
- **Rationale:** History anchors exposure without manufacturing a universal threshold; course and access inputs determine whether specificity is feasible.
- **Exact value:**

```json
{
  "conditional": [
    "technical_terrain_history",
    "altitude_and_environment_history",
    "hiking_exposure",
    "strength_exposure",
    "fueling_practice_experience"
  ],
  "material_unknown_behavior": "typed_no_plan_or_limited_module",
  "required": [
    "athlete_confirmed_trail_course_demand_v1",
    "stable_recent_running_history",
    "comparable_recent_ascent_exposure",
    "comparable_recent_descent_exposure",
    "available_training_days_and_limits",
    "accessible_training_terrain",
    "current_symptom_stop"
  ]
}
```

#### `trail_policy_execution_and_reassessment` — guardrail

- **Applies to:** early non-ultra trail rolling proposals
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `non-ultra-trail.course-specific-policy-required`
- **Rationale:** Fourteen days is the Product-selected minimum complete two-unit experience and seven days is an advisory review point. Neither value is a biological optimum; both are reversible workflow guardrails.
- **Exact value:**

```json
{
  "advisory_reassessment_after_completed_days": 7,
  "automatic_overwrite_of_adopted_future_days": false,
  "automatic_successor_adoption": false,
  "biological_optimum_claim": false,
  "calendar_schedule_unit_days": 7,
  "committed_proposal_days": 14,
  "continued_goal_horizon_requires_successor": true,
  "each_successor_requires_fresh_history_course_and_constraints": true,
  "proposal_end_inclusive": true
}
```

#### `trail_policy_history_guardrails` — guardrail

- **Applies to:** owner-scoped readiness history
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `non-ultra-trail.course-specific-policy-required`, `non-ultra-trail.uphill-downhill-require-distinct-handling`
- **Rationale:** The counts prevent a history-rich policy from extrapolating from sparse or non-comparable records. They are conservative pilot qualifications, not safety, adaptation, or readiness thresholds.
- **Exact value:**

```json
{
  "comparable_hilly_or_trail_sessions_within_completed_days": {
    "count": 2,
    "window": 42
  },
  "latest_comparable_hilly_or_trail_session_within_completed_days": 21,
  "latest_run_within_completed_days": 10,
  "minimum_running_sessions_per_usable_week": 3,
  "minimum_usable_completed_weeks": 4,
  "qualifying_activity_requires": [
    "outdoor_running_or_trail_running",
    "positive_duration_and_distance",
    "usable_elevation_gain_and_loss_or_explicit_unknown",
    "source_timestamp"
  ],
  "recent_history_lookback_completed_weeks": 8,
  "sparse_or_stale_result": "insufficient_comparable_trail_history",
  "thresholds_are_published_biological_laws": false,
  "unknown_descent_or_terrain_cannot_satisfy_comparable_exposure": true
}
```

#### `trail_policy_schedule_construction` — guardrail

- **Applies to:** deterministic early-block schedule
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `non-ultra-trail.training-specificity-promising-not-prescriptive`
- **Rationale:** Median, maximum, and athlete caps organize existing exposure without automatic progression. One quality session is a conservative Product choice for the first block, not a universal optimum.
- **Exact value:**

```json
{
  "below_minimum_result": "no_schedule_within_envelope",
  "easy_and_longest_easy_allocation": {
    "automatic_longest_easy_increase": false,
    "preferred_longest_easy_day_used_when_available": true,
    "quality_minutes_allocated_first": true,
    "remaining_minutes_distributed_across_non_quality_days": true
  },
  "no_schedule_result": "no_schedule_within_envelope",
  "non_taper_progression_above_recent_median": false,
  "quality_sessions_per_7_day_unit": 1,
  "requested_above_maximum_result": "clarification_required",
  "selected_running_days_per_7_day_unit": {
    "deterministic_value": "minimum_of_available_days_recent_modal_days_and_policy_maximum",
    "maximum": 6,
    "minimum": 3
  },
  "session_duration_hard_cap": "minimum_of_recent_maximum_completed_session_and_athlete_limit",
  "target_time_gap_may_raise_load": false,
  "weekly_running_minutes_hard_cap": "minimum_of_recent_maximum_usable_weekly_minutes_and_athlete_limit",
  "weekly_running_minutes_target": "minimum_of_recent_median_usable_weekly_minutes_and_athlete_limit"
}
```

#### `trail_policy_workout_templates` — guardrail

- **Applies to:** eligible early-block quality session
- **Evidence claims:** `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.hr-and-road-pace-not-sole-targets`, `non-ultra-trail.uphill-downhill-require-distinct-handling`
- **Rationale:** This transparent, targetless controlled-uphill template provides one deterministic trail-specific stimulus without claiming universal target zones or prescribing downhill speed. Its exact durations are reversible Product guardrails.
- **Exact value:**

```json
{
  "controlled_quality": {
    "steps": [
      {
        "duration_minutes": 10,
        "intended_intensity": "low",
        "kind": "step",
        "phase": "warmup"
      },
      {
        "kind": "repeat",
        "repetitions": 4,
        "steps": [
          {
            "duration_minutes": 3,
            "intended_intensity": "controlled_uphill_effort",
            "kind": "step",
            "phase": "work"
          },
          {
            "duration_minutes": 2,
            "intended_intensity": "low",
            "kind": "step",
            "phase": "recovery"
          }
        ]
      },
      {
        "duration_minutes": 8,
        "intended_intensity": "low",
        "kind": "step",
        "phase": "cooldown"
      }
    ],
    "template_id": "trail-controlled-uphill-quality-v1",
    "total_planned_minutes": 38
  },
  "downhill_recovery_may_be_prescribed": false,
  "easy": "duration_only_with_optional_accessible_terrain_category",
  "exact_hr_pace_power_or_rpe_target": false,
  "longest_easy": "duration_only_with_observed_duration_and_course_exposure_caps",
  "target_expression": "duration_phase_and_effort_label_only",
  "template_must_fit_history_constraint_and_exposure_caps": true,
  "template_optimum_claim": false,
  "work_step_requires_accessible_non_technical_uphill": true
}
```

#### `trail_policy_intensity_and_spacing` — guardrail

- **Applies to:** all planned running minutes
- **Evidence claims:** `non-ultra-trail.hr-and-road-pace-not-sole-targets`, `non-ultra-trail.training-specificity-promising-not-prescriptive`
- **Rationale:** The low-intensity floor, one-quality ceiling, and spacing rule are conservative pilot choices for a no-progression block, not published universal thresholds.
- **Exact value:**

```json
{
  "activity_average_power_allowed": false,
  "consecutive_quality_running_days_allowed": false,
  "historical_intensity_source_priority": [
    "activity_splits",
    "activity_samples"
  ],
  "low_intensity_fraction_is_optimum_claim": false,
  "maximum_quality_exposures_per_7_day_unit": 1,
  "minimum_intervening_easy_rest_or_non_running_days": 1,
  "minimum_planned_low_intensity_running_minutes_fraction": 0.75,
  "missed_quality_makeup_allowed": false,
  "quality_exposures_include": [
    "controlled_quality_template",
    "confirmed_race_or_maximal_effort"
  ],
  "reduce_or_remove_quality_before_adding_minutes": true
}
```

#### `trail_policy_course_exposure_caps` — guardrail

- **Applies to:** early-block terrain and vertical exposure
- **Evidence claims:** `non-ultra-trail.uphill-downhill-require-distinct-handling`, `non-ultra-trail.injury-fatigue-no-safe-dose`, `eligibility.fixed-progression-and-acwr-not-safety-laws`
- **Rationale:** Separate observed ascent, descent, and terrain caps avoid inventing a conversion or progression while enabling course-relevant organization.
- **Exact value:**

```json
{
  "automatic_vertical_progression": false,
  "high_speed_or_maximal_downhill_repeats": false,
  "road_or_flat_substitution_claimed_equivalent": false,
  "session_ascent_hard_cap": "recent_maximum_completed_session_ascent",
  "session_descent_hard_cap": "recent_maximum_completed_session_descent",
  "technicality": "no_more_difficult_than_recently_observed_and_currently_accessible_category",
  "unknown_descent_or_technicality_result": "clarification_or_limited_module",
  "weekly_ascent_hard_cap": "recent_maximum_usable_weekly_ascent",
  "weekly_ascent_target": "no_more_than_recent_median_usable_weekly_ascent",
  "weekly_descent_hard_cap": "recent_maximum_usable_weekly_descent",
  "weekly_descent_target": "no_more_than_recent_median_usable_weekly_descent"
}
```

#### `trail_policy_event_and_taper` — guardrail

- **Applies to:** dated trail goals
- **Evidence claims:** `non-ultra-trail.taper-direction-indirect`
- **Rationale:** General endurance evidence is insufficient to select a trail-specific taper here. Early blocks remain usable while the event-near path fails closed pending a successor decision.
- **Exact value:**

```json
{
  "event_day_generated_as_training_workout": false,
  "event_or_race_counts_as_quality_and_load": true,
  "imported_event_must_be_athlete_confirmed": true,
  "taper_implementation": "not_accepted",
  "target_more_than_14_days_after_start": "normal_14_day_rolling_proposal",
  "target_within_14_days_of_start": "event_inside_unapproved_taper_window"
}
```

#### `trail_policy_typed_outcomes` — guardrail

- **Applies to:** readiness and generation responses
- **Evidence claims:** `trail-ontology.course-demand-is-multidimensional`
- **Rationale:** Typed failures remain useful and honest without returning a success-shaped road schedule or erasing the athlete's goal.
- **Exact value:**

```json
{
  "candidate_success": "eligible_proposal",
  "goal_remains_recorded": true,
  "limited_modules": [
    "environment_module_limited",
    "fueling_module_limited",
    "technicality_module_limited"
  ],
  "no_plan": [
    "ontology_not_accepted",
    "policy_inactive",
    "course_clarification_required",
    "material_course_demand_unknown",
    "insufficient_comparable_history",
    "insufficient_terrain_access",
    "adult_scope_or_constraints_unconfirmed",
    "current_symptom_stop",
    "unsupported_ultra_or_multiday",
    "validation_failed"
  ],
  "road_fallback": false
}
```

#### `trail_policy_modular_structure` — guardrail

- **Applies to:** future deterministic generator envelope
- **Evidence claims:** `non-ultra-trail.uphill-downhill-require-distinct-handling`, `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.taper-direction-indirect`, `non-ultra-trail.fueling-duration-and-practice-context`
- **Rationale:** Modular handling preserves distinct demands and uncertainty without claiming one universal trail schedule.
- **Exact value:**

```json
{
  "module_requires_matching_input": true,
  "modules": [
    "readiness_and_history",
    "easy_and_aerobic",
    "ascent_specificity",
    "descent_and_neuromuscular_exposure",
    "technical_terrain",
    "hiking",
    "strength",
    "longest_session_and_fueling_practice",
    "taper",
    "environment_and_altitude",
    "reassessment_and_outcome"
  ],
  "unavailable_module_may_be_silently_replaced": false
}
```

#### `trail_policy_evidence_use` — guardrail

- **Applies to:** module selection and ScienceNote claims
- **Evidence claims:** `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.injury-fatigue-no-safe-dose`, `non-ultra-trail.observed-load-does-not-prove-prescription`, `non-ultra-trail.taper-direction-indirect`, `non-ultra-trail.fueling-duration-and-practice-context`
- **Rationale:** This distinguishes evidence-supported directions from exact prescriptions the sources do not establish.
- **Exact value:**

```json
{
  "fueling": "expected_duration_and_practice_context_only",
  "hiking": "conditional_candidate_module",
  "injury_and_fatigue_findings": "safety_context_only",
  "observed_load_associations": "descriptive_only",
  "strength_and_multimodal": "conditional_candidate_module",
  "taper": "indirect_direction_only",
  "trail_specificity": "conditional_candidate_module"
}
```

#### `trail_policy_hard_boundaries` — guardrail

- **Applies to:** all future policy and implementation surfaces
- **Evidence claims:** `non-ultra-trail.hr-and-road-pace-not-sole-targets`, `non-ultra-trail.injury-fatigue-no-safe-dose`, `eligibility.fixed-progression-and-acwr-not-safety-laws`, `eligibility.current-symptoms-support-stop-not-clearance`
- **Rationale:** These boundaries prevent unsupported inference, hidden load escalation, medical claims, and authority expansion.
- **Exact value:**

```json
{
  "activity_average_power_valid_for_intensity": false,
  "canonical_adoption_requires_explicit_athlete_action": true,
  "diagnosis_or_clearance": false,
  "heart_rate_or_level_pace_may_be_sole_hilly_controller": false,
  "missed_work_may_create_catch_up": false,
  "performance_injury_or_safety_guarantee": false,
  "personal_finish_probability": false,
  "provider_delivery_requires_separate_explicit_consent": true,
  "road_policy_fallback": false,
  "target_gap_may_raise_dose": false,
  "universal_ascent_descent_equivalence": false,
  "universal_distance_vertical_conversion": false,
  "valid_intensity_sources": [
    "activity_splits",
    "activity_samples"
  ]
}
```

#### `trail_policy_deferred_scope` — guardrail

- **Applies to:** scope outside the early rolling block
- **Evidence claims:** `non-ultra-trail.training-specificity-promising-not-prescriptive`, `non-ultra-trail.injury-fatigue-no-safe-dose`, `non-ultra-trail.taper-direction-indirect`, `non-ultra-trail.fueling-duration-and-practice-context`
- **Rationale:** The accepted early-block values remain deliberately narrow; these higher-load, event-near, fixed-dose, and target-specific behaviors need a successor decision.
- **Exact value:**

```json
{
  "back_to_back_sessions": "not_accepted",
  "fueling_amount_or_frequency": "not_accepted",
  "hiking_threshold_or_dose": "not_accepted",
  "hr_pace_power_or_rpe_targets": "not_accepted",
  "outcome_window_or_meaningful_change": "not_accepted",
  "progression_above_recent_typical_load": "not_accepted",
  "recovery_interval": "not_accepted",
  "strength_frequency_or_dose": "not_accepted",
  "taper_duration_and_reduction": "not_accepted",
  "technical_terrain_dose": "not_accepted",
  "vertical_or_downhill_progression_above_recent_history": "not_accepted"
}
```

#### `trail_policy_runtime_evaluation` — guardrail

- **Applies to:** inactive dry run and separately authorized owner pilot
- **Evidence claims:** `non-ultra-trail.injury-fatigue-no-safe-dose`, `eligibility.fixed-progression-and-acwr-not-safety-laws`
- **Rationale:** Zero-tolerance deterministic failures and a conservative edit threshold make the reversible owner pilot observable without turning one athlete's process data into efficacy or safety evidence.
- **Exact value:**

```json
{
  "dry_run": {
    "deterministic_invariant_breach_tolerance": 0,
    "replay_mismatch_tolerance": 0,
    "unsupported_or_material_unknown_plan_tolerance": 0
  },
  "efficacy_or_safety_claim_from_process_pilot": false,
  "owner_only_pilot": {
    "major_edit_definition": "session_duration_or_vertical_change_over_twenty_percent_or_two_scheduled_days_changed",
    "maximum_major_edit_fraction": 0.3,
    "serious_plausibly_related_report_pause_threshold": 1
  },
  "pause_or_revise_when_threshold_crossed": true
}
```

#### `trail_policy_non_science_authority` — guardrail

- **Applies to:** work outside Science authority
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Product, Design, Engineering, Quality, Operations, and provider decisions require their own linked artifacts and authority.
- **Exact value:**

```json
{
  "deployment": "not_accepted",
  "garmin_mapping": "not_accepted",
  "implementation_review": "required",
  "owner_only_pilot": "not_accepted",
  "product_visibility": "not_accepted",
  "runtime_activation": "not_accepted"
}
```

### Rejected alternatives

#### Copy a road 10K, half-marathon, or marathon schedule and add elevation

Road policies do not preserve descent, grade, technicality, terrain access, hiking, or trail-specific mechanical exposure.

#### Use distance plus ascent to select a complete trail plan

Material course, environment, support, expected-duration, access, and history dimensions would remain unknown.

#### Use one universal weekly elevation or downhill progression

Current intervention and injury evidence does not validate such a safe or optimal individual dose.

#### Use heart rate, road pace, ACWR, or activity-average power as the sole controller

Slope-specific metabolic and mechanical demands and evidence limitations make those unsupported sole representations.

#### Let an LLM choose the schedule and validate it afterward

Post-hoc validation cannot make unsupported assumptions or values accepted and cannot broaden the deterministic capability envelope.

### Applicability

- Adults with stable recent, comparable running and trail exposure
- Single-day non-ultra trail performance intent
- Complete accepted trail_course_demand_v1 and explicit training constraints
- Suggestion-only plan proposals and scientific claim limits

### User-facing claim limits

- Do not present the policy as a road plan adjusted for elevation.
- Do not claim one universal vertical, descent, technicality, hiking, strength, long-run, taper, or fueling dose.
- Do not use heart rate, road pace, ACWR, or activity-average power as a sole or safety-validating controller.
- Do not show a personal finish probability, target guarantee, injury-prevention guarantee, diagnosis, or clearance.

### Safety implications

- Current symptoms stop performance optimization and route outside this nonclinical policy.
- Missing material course demand, history, or terrain access fails closed or limits only a separately supported module.
- No catch-up, target-gap load escalation, fixed progression law, or road fallback is allowed.
- Downhill and technical exposure must stay within separately approved history-anchored bounds.

### Privacy implications

- Persist only normalized course-demand, constraint, and aggregate history snapshots needed for deterministic replay.
- Do not copy raw activities, samples, route files, free text, provider payloads, or target values into generic telemetry.
- Owner-scoped goal, proposal, adoption, export, deletion, and account-deletion paths remain mandatory.

### Validation plan

- Validate the exact fourteen-day generator parameters and generated contract digest before human review.
- Replay capability matching across missingness, terrain-access, course, history, environment, and support boundaries.
- Unit-test history qualification, schedule allocation, targetless quality-template steps, low-intensity fraction, quality spacing, and separate ascent/descent/technicality caps.
- Compare every generated exposure only with owner-scoped immutable history snapshots using splits or samples for intensity.
- Verify proposals cannot mutate canonical workouts or provider calendars before exact athlete adoption and separate delivery consent.
- Dry-run before owner access, then prospectively observe typed outcomes, edits, adoption, withdrawal, validation failures, and adverse signals only after separate owner-pilot authority.

### Falsification conditions

- A trail proposal is generated from distance/ascent alone, from an inactive contract, or through a road fallback.
- An exact value outside the accepted early-block guardrails is inferred despite literal not_accepted status.
- Uphill and downhill are collapsed, terrain access is ignored, or an unsupported module is silently substituted.
- A generated block exceeds recent median weekly duration, corresponding recent ascent/descent exposure, session caps, one quality exposure, or the seventy-five-percent low-intensity floor.
- Activity-average power, ACWR, road pace, or heart rate is treated as a safe sole prescription controller.
- A proposal implies personal finish probability, safety, injury prevention, diagnosis, or medical clearance.
- Runtime behavior is exposed before accepted Product/Design decisions, implementation review, and activation authority.

### Decision notes

- This artifact-mode decision addresses issue #692 and remains draft and inactive.
- It depends on separate acceptance of sdr-trail-running-goal-ontology-v1.
- Work Contract classification digest: sha256:55c4da66e7f504dd0d40c681c2a006fdbe7079c0cd06de43cb95802e679f78f5.
- Work Contract route digest: sha256:2f237b07f7a41582707e1a647e69aa634749c487c258b555c559f80f98cfc160.
- The fourteen-day window, seven-day review, history counts, session template, schedule limits, course-exposure caps, and evaluation thresholds are reversible Product guardrails proposed in docs/dev/trail-running-plan-product-proposal.md; they are not published biological optima or safety laws.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "inactive non-ultra trail deterministic early-block policy and generator",
    "trail course-demand and history snapshot matching"
  ],
  "contract_digest": "sha256:534d292e7e770fff6c9078ef2adf1d1b881cb226d510a839013a170365184973",
  "decision_id": "sdr-non-ultra-trail-plan-generation-policy-v1",
  "decision_status": "draft",
  "decision_version": 1,
  "evidence_claim_ids": [
    "trail-ontology.course-demand-is-multidimensional",
    "trail-ontology.uphill-downhill-demands-differ",
    "trail-ontology.technicality-and-downhill-vary-performance",
    "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
    "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose",
    "non-ultra-trail.course-specific-policy-required",
    "non-ultra-trail.uphill-downhill-require-distinct-handling",
    "non-ultra-trail.hr-and-road-pace-not-sole-targets",
    "non-ultra-trail.training-specificity-promising-not-prescriptive",
    "non-ultra-trail.injury-fatigue-no-safe-dose",
    "non-ultra-trail.observed-load-does-not-prove-prescription",
    "non-ultra-trail.taper-direction-indirect",
    "non-ultra-trail.fueling-duration-and-practice-context",
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.fixed-progression-and-acwr-not-safety-laws",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.current-symptoms-support-stop-not-clearance"
  ],
  "evidence_review_ids": [
    "evidence-trail-running-goal-ontology-v1",
    "evidence-non-ultra-trail-plan-generation-policy-v1",
    "evidence-plan-generation-eligibility-safety-v1"
  ],
  "linked_evidence_digests": {
    "evidence-non-ultra-trail-plan-generation-policy-v1": "sha256:51e9349704d969b6524b947311a04e585477cffd7071254a9d2859690d87d78e",
    "evidence-plan-generation-eligibility-safety-v1": "sha256:e884907d33783edc6cdb16fd5504f7f10b6d68f968bfe7cf87e3f024b5bda773",
    "evidence-trail-running-goal-ontology-v1": "sha256:60f0e785e4fc2b4226fed3bb30750191195cffbb0236b4a81d34431c0002c87a"
  },
  "model_version": "non-ultra-trail-plan-generation-policy-v1",
  "parameters": {
    "trail_policy_course_exposure_caps": {
      "applies_to": "early-block terrain and vertical exposure",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.uphill-downhill-require-distinct-handling",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "eligibility.fixed-progression-and-acwr-not-safety-laws"
      ],
      "value": {
        "automatic_vertical_progression": false,
        "high_speed_or_maximal_downhill_repeats": false,
        "road_or_flat_substitution_claimed_equivalent": false,
        "session_ascent_hard_cap": "recent_maximum_completed_session_ascent",
        "session_descent_hard_cap": "recent_maximum_completed_session_descent",
        "technicality": "no_more_difficult_than_recently_observed_and_currently_accessible_category",
        "unknown_descent_or_technicality_result": "clarification_or_limited_module",
        "weekly_ascent_hard_cap": "recent_maximum_usable_weekly_ascent",
        "weekly_ascent_target": "no_more_than_recent_median_usable_weekly_ascent",
        "weekly_descent_hard_cap": "recent_maximum_usable_weekly_descent",
        "weekly_descent_target": "no_more_than_recent_median_usable_weekly_descent"
      }
    },
    "trail_policy_deferred_scope": {
      "applies_to": "scope outside the early rolling block",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "non-ultra-trail.taper-direction-indirect",
        "non-ultra-trail.fueling-duration-and-practice-context"
      ],
      "value": {
        "back_to_back_sessions": "not_accepted",
        "fueling_amount_or_frequency": "not_accepted",
        "hiking_threshold_or_dose": "not_accepted",
        "hr_pace_power_or_rpe_targets": "not_accepted",
        "outcome_window_or_meaningful_change": "not_accepted",
        "progression_above_recent_typical_load": "not_accepted",
        "recovery_interval": "not_accepted",
        "strength_frequency_or_dose": "not_accepted",
        "taper_duration_and_reduction": "not_accepted",
        "technical_terrain_dose": "not_accepted",
        "vertical_or_downhill_progression_above_recent_history": "not_accepted"
      }
    },
    "trail_policy_event_and_taper": {
      "applies_to": "dated trail goals",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.taper-direction-indirect"
      ],
      "value": {
        "event_day_generated_as_training_workout": false,
        "event_or_race_counts_as_quality_and_load": true,
        "imported_event_must_be_athlete_confirmed": true,
        "taper_implementation": "not_accepted",
        "target_more_than_14_days_after_start": "normal_14_day_rolling_proposal",
        "target_within_14_days_of_start": "event_inside_unapproved_taper_window"
      }
    },
    "trail_policy_evidence_use": {
      "applies_to": "module selection and ScienceNote claims",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "non-ultra-trail.observed-load-does-not-prove-prescription",
        "non-ultra-trail.taper-direction-indirect",
        "non-ultra-trail.fueling-duration-and-practice-context"
      ],
      "value": {
        "fueling": "expected_duration_and_practice_context_only",
        "hiking": "conditional_candidate_module",
        "injury_and_fatigue_findings": "safety_context_only",
        "observed_load_associations": "descriptive_only",
        "strength_and_multimodal": "conditional_candidate_module",
        "taper": "indirect_direction_only",
        "trail_specificity": "conditional_candidate_module"
      }
    },
    "trail_policy_execution_and_reassessment": {
      "applies_to": "early non-ultra trail rolling proposals",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "non-ultra-trail.course-specific-policy-required"
      ],
      "value": {
        "advisory_reassessment_after_completed_days": 7,
        "automatic_overwrite_of_adopted_future_days": false,
        "automatic_successor_adoption": false,
        "biological_optimum_claim": false,
        "calendar_schedule_unit_days": 7,
        "committed_proposal_days": 14,
        "continued_goal_horizon_requires_successor": true,
        "each_successor_requires_fresh_history_course_and_constraints": true,
        "proposal_end_inclusive": true
      }
    },
    "trail_policy_hard_boundaries": {
      "applies_to": "all future policy and implementation surfaces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.hr-and-road-pace-not-sole-targets",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "eligibility.current-symptoms-support-stop-not-clearance"
      ],
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "canonical_adoption_requires_explicit_athlete_action": true,
        "diagnosis_or_clearance": false,
        "heart_rate_or_level_pace_may_be_sole_hilly_controller": false,
        "missed_work_may_create_catch_up": false,
        "performance_injury_or_safety_guarantee": false,
        "personal_finish_probability": false,
        "provider_delivery_requires_separate_explicit_consent": true,
        "road_policy_fallback": false,
        "target_gap_may_raise_dose": false,
        "universal_ascent_descent_equivalence": false,
        "universal_distance_vertical_conversion": false,
        "valid_intensity_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    "trail_policy_history_guardrails": {
      "applies_to": "owner-scoped readiness history",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "non-ultra-trail.course-specific-policy-required",
        "non-ultra-trail.uphill-downhill-require-distinct-handling"
      ],
      "value": {
        "comparable_hilly_or_trail_sessions_within_completed_days": {
          "count": 2,
          "window": 42
        },
        "latest_comparable_hilly_or_trail_session_within_completed_days": 21,
        "latest_run_within_completed_days": 10,
        "minimum_running_sessions_per_usable_week": 3,
        "minimum_usable_completed_weeks": 4,
        "qualifying_activity_requires": [
          "outdoor_running_or_trail_running",
          "positive_duration_and_distance",
          "usable_elevation_gain_and_loss_or_explicit_unknown",
          "source_timestamp"
        ],
        "recent_history_lookback_completed_weeks": 8,
        "sparse_or_stale_result": "insufficient_comparable_trail_history",
        "thresholds_are_published_biological_laws": false,
        "unknown_descent_or_terrain_cannot_satisfy_comparable_exposure": true
      }
    },
    "trail_policy_intensity_and_spacing": {
      "applies_to": "all planned running minutes",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.hr-and-road-pace-not-sole-targets",
        "non-ultra-trail.training-specificity-promising-not-prescriptive"
      ],
      "value": {
        "activity_average_power_allowed": false,
        "consecutive_quality_running_days_allowed": false,
        "historical_intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "low_intensity_fraction_is_optimum_claim": false,
        "maximum_quality_exposures_per_7_day_unit": 1,
        "minimum_intervening_easy_rest_or_non_running_days": 1,
        "minimum_planned_low_intensity_running_minutes_fraction": 0.75,
        "missed_quality_makeup_allowed": false,
        "quality_exposures_include": [
          "controlled_quality_template",
          "confirmed_race_or_maximal_effort"
        ],
        "reduce_or_remove_quality_before_adding_minutes": true
      }
    },
    "trail_policy_modular_structure": {
      "applies_to": "future deterministic generator envelope",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.uphill-downhill-require-distinct-handling",
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.taper-direction-indirect",
        "non-ultra-trail.fueling-duration-and-practice-context"
      ],
      "value": {
        "module_requires_matching_input": true,
        "modules": [
          "readiness_and_history",
          "easy_and_aerobic",
          "ascent_specificity",
          "descent_and_neuromuscular_exposure",
          "technical_terrain",
          "hiking",
          "strength",
          "longest_session_and_fueling_practice",
          "taper",
          "environment_and_altitude",
          "reassessment_and_outcome"
        ],
        "unavailable_module_may_be_silently_replaced": false
      }
    },
    "trail_policy_non_science_authority": {
      "applies_to": "work outside Science authority",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "deployment": "not_accepted",
        "garmin_mapping": "not_accepted",
        "implementation_review": "required",
        "owner_only_pilot": "not_accepted",
        "product_visibility": "not_accepted",
        "runtime_activation": "not_accepted"
      }
    },
    "trail_policy_required_inputs": {
      "applies_to": "capability matching and readiness",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.course-specific-policy-required",
        "non-ultra-trail.uphill-downhill-require-distinct-handling",
        "eligibility.recent-history-anchor-without-universal-threshold"
      ],
      "value": {
        "conditional": [
          "technical_terrain_history",
          "altitude_and_environment_history",
          "hiking_exposure",
          "strength_exposure",
          "fueling_practice_experience"
        ],
        "material_unknown_behavior": "typed_no_plan_or_limited_module",
        "required": [
          "athlete_confirmed_trail_course_demand_v1",
          "stable_recent_running_history",
          "comparable_recent_ascent_exposure",
          "comparable_recent_descent_exposure",
          "available_training_days_and_limits",
          "accessible_training_terrain",
          "current_symptom_stop"
        ]
      }
    },
    "trail_policy_runtime_evaluation": {
      "applies_to": "inactive dry run and separately authorized owner pilot",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "eligibility.fixed-progression-and-acwr-not-safety-laws"
      ],
      "value": {
        "dry_run": {
          "deterministic_invariant_breach_tolerance": 0,
          "replay_mismatch_tolerance": 0,
          "unsupported_or_material_unknown_plan_tolerance": 0
        },
        "efficacy_or_safety_claim_from_process_pilot": false,
        "owner_only_pilot": {
          "major_edit_definition": "session_duration_or_vertical_change_over_twenty_percent_or_two_scheduled_days_changed",
          "maximum_major_edit_fraction": 0.3,
          "serious_plausibly_related_report_pause_threshold": 1
        },
        "pause_or_revise_when_threshold_crossed": true
      }
    },
    "trail_policy_schedule_construction": {
      "applies_to": "deterministic early-block schedule",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "non-ultra-trail.training-specificity-promising-not-prescriptive"
      ],
      "value": {
        "below_minimum_result": "no_schedule_within_envelope",
        "easy_and_longest_easy_allocation": {
          "automatic_longest_easy_increase": false,
          "preferred_longest_easy_day_used_when_available": true,
          "quality_minutes_allocated_first": true,
          "remaining_minutes_distributed_across_non_quality_days": true
        },
        "no_schedule_result": "no_schedule_within_envelope",
        "non_taper_progression_above_recent_median": false,
        "quality_sessions_per_7_day_unit": 1,
        "requested_above_maximum_result": "clarification_required",
        "selected_running_days_per_7_day_unit": {
          "deterministic_value": "minimum_of_available_days_recent_modal_days_and_policy_maximum",
          "maximum": 6,
          "minimum": 3
        },
        "session_duration_hard_cap": "minimum_of_recent_maximum_completed_session_and_athlete_limit",
        "target_time_gap_may_raise_load": false,
        "weekly_running_minutes_hard_cap": "minimum_of_recent_maximum_usable_weekly_minutes_and_athlete_limit",
        "weekly_running_minutes_target": "minimum_of_recent_median_usable_weekly_minutes_and_athlete_limit"
      }
    },
    "trail_policy_scope_and_dependencies": {
      "applies_to": "non-ultra-trail-plan-generation-policy-v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.course-specific-policy-required",
        "eligibility.goal-relevant-current-capability-task-specific"
      ],
      "value": {
        "clinical_or_return_to_sport": false,
        "distance_family": "non_ultra",
        "event_format": "single_day",
        "intent": "performance",
        "minimum_age_years": 18,
        "requires_accepted_ontology": "sdr-trail-running-goal-ontology-v1",
        "requires_course_demand_schema": "trail_course_demand_v1",
        "suggestion_only": true
      }
    },
    "trail_policy_typed_outcomes": {
      "applies_to": "readiness and generation responses",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional"
      ],
      "value": {
        "candidate_success": "eligible_proposal",
        "goal_remains_recorded": true,
        "limited_modules": [
          "environment_module_limited",
          "fueling_module_limited",
          "technicality_module_limited"
        ],
        "no_plan": [
          "ontology_not_accepted",
          "policy_inactive",
          "course_clarification_required",
          "material_course_demand_unknown",
          "insufficient_comparable_history",
          "insufficient_terrain_access",
          "adult_scope_or_constraints_unconfirmed",
          "current_symptom_stop",
          "unsupported_ultra_or_multiday",
          "validation_failed"
        ],
        "road_fallback": false
      }
    },
    "trail_policy_workout_templates": {
      "applies_to": "eligible early-block quality session",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.hr-and-road-pace-not-sole-targets",
        "non-ultra-trail.uphill-downhill-require-distinct-handling"
      ],
      "value": {
        "controlled_quality": {
          "steps": [
            {
              "duration_minutes": 10,
              "intended_intensity": "low",
              "kind": "step",
              "phase": "warmup"
            },
            {
              "kind": "repeat",
              "repetitions": 4,
              "steps": [
                {
                  "duration_minutes": 3,
                  "intended_intensity": "controlled_uphill_effort",
                  "kind": "step",
                  "phase": "work"
                },
                {
                  "duration_minutes": 2,
                  "intended_intensity": "low",
                  "kind": "step",
                  "phase": "recovery"
                }
              ]
            },
            {
              "duration_minutes": 8,
              "intended_intensity": "low",
              "kind": "step",
              "phase": "cooldown"
            }
          ],
          "template_id": "trail-controlled-uphill-quality-v1",
          "total_planned_minutes": 38
        },
        "downhill_recovery_may_be_prescribed": false,
        "easy": "duration_only_with_optional_accessible_terrain_category",
        "exact_hr_pace_power_or_rpe_target": false,
        "longest_easy": "duration_only_with_observed_duration_and_course_exposure_caps",
        "target_expression": "duration_phase_and_effort_label_only",
        "template_must_fit_history_constraint_and_exposure_caps": true,
        "template_optimum_claim": false,
        "work_step_requires_accessible_non_technical_uphill": true
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:afc9fecefd55c699a8fdf3d3ab885968c7f7981fadbcba7bf09494fdfcdcd606"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If its ontology dependency and this evidence and decision are separately accepted, Praxys may prepare a deterministic, suggestion-only policy for nonclinical adults with stable recent history, comparable trail exposure, performance intent, an athlete-confirmed trail_course_demand_v1, and explicit schedule constraints. Matching is course-specific. Uphill, downhill, technical terrain, expected duration, environment, support, terrain access, and fueling practice remain distinct inputs. Missing material inputs yield a typed no-plan or bounded alternative, never a road fallback. Trail-specific, strength, hiking, taper, and fueling modules remain conditional and uncertainty-labelled. The proposed first block commits fourteen calendar days, reviews after seven completed days, uses eight completed history weeks, requires four usable weeks and recent direct hilly or trail exposure, never plans above recent median weekly duration or corresponding ascent/descent exposure, and allows at most one nonconsecutive controlled quality exposure per seven-day unit. These values are reversible Praxys guardrails rather than published optima or safety laws. Taper, progression above history, fixed fueling, hiking or strength dose, back-to-back sessions, and universal HR, pace, power, or RPE targets remain unaccepted. No personal finish probability or safety guarantee is accepted. Science acceptance would authorize only a separately reviewed inactive implementation inside these bounds; owner-only rollout, provider delivery, and runtime activation remain separate decisions.",
  "affected_surfaces": {
    "apis": [
      "future trail readiness, alternatives, generate, regenerate, and adoption routes",
      "plan-generation capability discovery"
    ],
    "clients": [
      "future web, miniapp, plugin, and MCP trail plan-start flows"
    ],
    "models": [
      "inactive non-ultra trail deterministic early-block policy and generator",
      "trail course-demand and history snapshot matching"
    ],
    "science_notes": [
      "Why trail plans match course demand rather than distance alone",
      "Why uphill, downhill, terrain access, and fueling practice are separate"
    ]
  },
  "applicability": [
    "Adults with stable recent, comparable running and trail exposure",
    "Single-day non-ultra trail performance intent",
    "Complete accepted trail_course_demand_v1 and explicit training constraints",
    "Suggestion-only plan proposals and scientific claim limits"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-09-01",
  "decision_notes": [
    "This artifact-mode decision addresses issue #692 and remains draft and inactive.",
    "It depends on separate acceptance of sdr-trail-running-goal-ontology-v1.",
    "Work Contract classification digest: sha256:55c4da66e7f504dd0d40c681c2a006fdbe7079c0cd06de43cb95802e679f78f5.",
    "Work Contract route digest: sha256:2f237b07f7a41582707e1a647e69aa634749c487c258b555c559f80f98cfc160.",
    "The fourteen-day window, seven-day review, history counts, session template, schedule limits, course-exposure caps, and evaluation thresholds are reversible Product guardrails proposed in docs/dev/trail-running-plan-product-proposal.md; they are not published biological optima or safety laws."
  ],
  "decision_review": {
    "approval_statement": "I approve the narrow history-rich adult non-ultra trail performance scope, exact trail_course_demand_v1 matching, conditional terrain/downhill/ strength/fueling modules, suggestion-only athlete control, and typed fail-closed outcomes. I approve keeping uphill and downhill distinct and prohibiting road fallback, universal vertical conversion, fixed safe dose, activity-average-power intensity use, and personal finish or safety guarantees. I also approve the fourteen-day block, seven-day review, history qualification, no-initial-load-progression schedule, one controlled quality exposure, seventy-five-percent low-intensity floor, and course- exposure caps as labelled reversible Praxys guardrails. This authorizes only a separately reviewed inactive implementation. It does not approve taper, progression above history, fixed fueling or strength dose, an owner-only pilot, provider delivery, rollout, deployment, or activation.",
    "items": [
      {
        "approval_effect": [
          "A future generator may be designed only inside this tuple.",
          "Goal capture remains independent from generator availability."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A schedule, threshold, implementation, pilot, or activation."
        ],
        "evidence_claim_ids": [
          "non-ultra-trail.course-specific-policy-required",
          "eligibility.recent-history-anchor-without-universal-threshold",
          "eligibility.goal-relevant-current-capability-task-specific"
        ],
        "id": "narrow-course-matched-scope",
        "parameter_names": [
          "trail_policy_scope_and_dependencies",
          "trail_policy_required_inputs",
          "trail_policy_typed_outcomes"
        ],
        "proposed_decision": "Accept that narrow scope and return typed unavailable results for first-completion, sparse-history, ultra, multi-day, clinical, or materially unknown contexts.",
        "question": "Should the policy apply only to nonclinical adults with stable recent history, comparable exposure, performance intent, confirmed constraints, and a complete accepted trail course-demand tuple?",
        "title": "Accept the narrow history-rich course-matched scope"
      },
      {
        "approval_effect": [
          "Missing module-specific context may limit that module without inventing equivalence.",
          "Ascent and descent exposure remain separately reviewable."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A fixed weekly mix, vertical target, downhill dose, hiking threshold, or strength prescription."
        ],
        "evidence_claim_ids": [
          "non-ultra-trail.uphill-downhill-require-distinct-handling",
          "non-ultra-trail.training-specificity-promising-not-prescriptive",
          "non-ultra-trail.taper-direction-indirect",
          "non-ultra-trail.fueling-duration-and-practice-context"
        ],
        "id": "modular-specificity",
        "parameter_names": [
          "trail_policy_modular_structure",
          "trail_policy_evidence_use"
        ],
        "proposed_decision": "Accept the modular structure without selecting an exact dose or claiming one module is universally required or superior.",
        "question": "Should terrain specificity, ascent, descent, hiking, strength, taper, fueling, and environment remain separate modules enabled only by matching evidence and access?",
        "title": "Accept a conditional modular trail policy"
      },
      {
        "approval_effect": [
          "Deterministic validation remains authoritative.",
          "Splits or samples, not activity-average power, supply historical intensity evidence."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Medical clearance, an individual probability, or automatic mutation or delivery."
        ],
        "evidence_claim_ids": [
          "non-ultra-trail.hr-and-road-pace-not-sole-targets",
          "non-ultra-trail.injury-fatigue-no-safe-dose",
          "non-ultra-trail.observed-load-does-not-prove-prescription",
          "eligibility.fixed-progression-and-acwr-not-safety-laws",
          "eligibility.current-symptoms-support-stop-not-clearance"
        ],
        "id": "hard-science-boundaries",
        "parameter_names": [
          "trail_policy_hard_boundaries"
        ],
        "proposed_decision": "Accept those prohibitions and require athlete review and exact-version adoption before any canonical plan or provider delivery.",
        "question": "Should the policy prohibit road fallback, target-gap dose escalation, catch-up, universal equivalence, activity-average-power intensity, diagnosis, and personal finish or injury guarantees?",
        "title": "Accept hard safety, intensity, and athlete-control boundaries"
      },
      {
        "approval_effect": [
          "Engineering may prepare an inactive deterministic generator inside the exact reviewed envelope.",
          "The first owner can receive early rolling blocks while event-near taper remains unavailable."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Biological optimality, progression above history, taper, a fixed fueling or strength dose, implementation acceptance, rollout, or activation."
        ],
        "evidence_claim_ids": [
          "non-ultra-trail.course-specific-policy-required",
          "non-ultra-trail.uphill-downhill-require-distinct-handling",
          "non-ultra-trail.training-specificity-promising-not-prescriptive",
          "non-ultra-trail.taper-direction-indirect",
          "eligibility.recent-history-anchor-without-universal-threshold",
          "eligibility.fixed-progression-and-acwr-not-safety-laws"
        ],
        "id": "initial-generator-guardrails",
        "parameter_names": [
          "trail_policy_execution_and_reassessment",
          "trail_policy_history_guardrails",
          "trail_policy_schedule_construction",
          "trail_policy_workout_templates",
          "trail_policy_intensity_and_spacing",
          "trail_policy_course_exposure_caps",
          "trail_policy_runtime_evaluation"
        ],
        "proposed_decision": "Accept those values for an early, history-anchored block only. Require deterministic replay and prospectively evaluate exclusions, edits, withdrawals, and invariant failures before any wider scope.",
        "question": "Are the fourteen-day execution window, seven-day review, bounded history qualification, no-initial-load-progression construction, targetless controlled-uphill template, intensity spacing, and course-exposure caps compatible with the evidence when labelled as Praxys guardrails rather than published prescriptions?",
        "title": "Accept the reversible early-block generator values"
      },
      {
        "approval_effect": [
          "The early-block implementation cannot silently expand into event-near or higher-load planning."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Inferring values from road policies, study protocols, common practice, or AI output."
        ],
        "evidence_claim_ids": [
          "non-ultra-trail.training-specificity-promising-not-prescriptive",
          "non-ultra-trail.injury-fatigue-no-safe-dose",
          "non-ultra-trail.taper-direction-indirect",
          "non-ultra-trail.fueling-duration-and-practice-context"
        ],
        "id": "exact-generation-values-deferred",
        "parameter_names": [
          "trail_policy_event_and_taper",
          "trail_policy_deferred_scope"
        ],
        "proposed_decision": "Keep every remaining value literal not_accepted until a successor decision compares reversible options and validation evidence.",
        "question": "Should progression above recent exposure, taper, back-to-back sessions, fixed fueling, hiking or strength doses, and universal target zones remain unaccepted?",
        "title": "Defer taper, progression, fixed dose, and broader scope"
      },
      {
        "approval_effect": [
          "Science approval alone cannot expose or execute a trail plan."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "User visibility, data collection, plan generation, adoption, provider dispatch, deployment, or activation."
        ],
        "evidence_claim_ids": [],
        "id": "implementation-rollout-deferred",
        "parameter_names": [
          "trail_policy_non_science_authority"
        ],
        "proposed_decision": "Keep runtime inactive and require accepted Product, Design, implementation, verification, and Operations authority.",
        "question": "Should storage, APIs, clients, an owner-only pilot, Garmin mapping, rollout, monitoring, and runtime activation remain outside this SDR?",
        "title": "Defer implementation, owner pilot, Garmin, and activation"
      }
    ],
    "reviewer_task": "Decide whether the narrow population, course-specific modular policy, reversible fourteen-day generator guardrails, and hard scientific boundaries should be accepted while taper and the listed unsupported scope remain deferred."
  },
  "evidence_claim_ids": [
    "trail-ontology.course-demand-is-multidimensional",
    "trail-ontology.uphill-downhill-demands-differ",
    "trail-ontology.technicality-and-downhill-vary-performance",
    "trail-ontology.heart-rate-and-road-pace-are-insufficient-alone",
    "trail-ontology.training-and-injury-evidence-does-not-set-safe-dose",
    "non-ultra-trail.course-specific-policy-required",
    "non-ultra-trail.uphill-downhill-require-distinct-handling",
    "non-ultra-trail.hr-and-road-pace-not-sole-targets",
    "non-ultra-trail.training-specificity-promising-not-prescriptive",
    "non-ultra-trail.injury-fatigue-no-safe-dose",
    "non-ultra-trail.observed-load-does-not-prove-prescription",
    "non-ultra-trail.taper-direction-indirect",
    "non-ultra-trail.fueling-duration-and-practice-context",
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.fixed-progression-and-acwr-not-safety-laws",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.current-symptoms-support-stop-not-clearance"
  ],
  "evidence_review_ids": [
    "evidence-trail-running-goal-ontology-v1",
    "evidence-non-ultra-trail-plan-generation-policy-v1",
    "evidence-plan-generation-eligibility-safety-v1"
  ],
  "falsification_conditions": [
    "A trail proposal is generated from distance/ascent alone, from an inactive contract, or through a road fallback.",
    "An exact value outside the accepted early-block guardrails is inferred despite literal not_accepted status.",
    "Uphill and downhill are collapsed, terrain access is ignored, or an unsupported module is silently substituted.",
    "A generated block exceeds recent median weekly duration, corresponding recent ascent/descent exposure, session caps, one quality exposure, or the seventy-five-percent low-intensity floor.",
    "Activity-average power, ACWR, road pace, or heart rate is treated as a safe sole prescription controller.",
    "A proposal implies personal finish probability, safety, injury prevention, diagnosis, or medical clearance.",
    "Runtime behavior is exposed before accepted Product/Design decisions, implementation review, and activation authority."
  ],
  "id": "sdr-non-ultra-trail-plan-generation-policy-v1",
  "model_parameters": [
    {
      "applies_to": "non-ultra-trail-plan-generation-policy-v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.course-specific-policy-required",
        "eligibility.goal-relevant-current-capability-task-specific"
      ],
      "name": "trail_policy_scope_and_dependencies",
      "rationale": "The narrow tuple avoids transferring sparse trail evidence into ultra, first-completion, medical, or materially different contexts.",
      "value": {
        "clinical_or_return_to_sport": false,
        "distance_family": "non_ultra",
        "event_format": "single_day",
        "intent": "performance",
        "minimum_age_years": 18,
        "requires_accepted_ontology": "sdr-trail-running-goal-ontology-v1",
        "requires_course_demand_schema": "trail_course_demand_v1",
        "suggestion_only": true
      }
    },
    {
      "applies_to": "capability matching and readiness",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.course-specific-policy-required",
        "non-ultra-trail.uphill-downhill-require-distinct-handling",
        "eligibility.recent-history-anchor-without-universal-threshold"
      ],
      "name": "trail_policy_required_inputs",
      "rationale": "History anchors exposure without manufacturing a universal threshold; course and access inputs determine whether specificity is feasible.",
      "value": {
        "conditional": [
          "technical_terrain_history",
          "altitude_and_environment_history",
          "hiking_exposure",
          "strength_exposure",
          "fueling_practice_experience"
        ],
        "material_unknown_behavior": "typed_no_plan_or_limited_module",
        "required": [
          "athlete_confirmed_trail_course_demand_v1",
          "stable_recent_running_history",
          "comparable_recent_ascent_exposure",
          "comparable_recent_descent_exposure",
          "available_training_days_and_limits",
          "accessible_training_terrain",
          "current_symptom_stop"
        ]
      }
    },
    {
      "applies_to": "early non-ultra trail rolling proposals",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "non-ultra-trail.course-specific-policy-required"
      ],
      "name": "trail_policy_execution_and_reassessment",
      "rationale": "Fourteen days is the Product-selected minimum complete two-unit experience and seven days is an advisory review point. Neither value is a biological optimum; both are reversible workflow guardrails.",
      "value": {
        "advisory_reassessment_after_completed_days": 7,
        "automatic_overwrite_of_adopted_future_days": false,
        "automatic_successor_adoption": false,
        "biological_optimum_claim": false,
        "calendar_schedule_unit_days": 7,
        "committed_proposal_days": 14,
        "continued_goal_horizon_requires_successor": true,
        "each_successor_requires_fresh_history_course_and_constraints": true,
        "proposal_end_inclusive": true
      }
    },
    {
      "applies_to": "owner-scoped readiness history",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "non-ultra-trail.course-specific-policy-required",
        "non-ultra-trail.uphill-downhill-require-distinct-handling"
      ],
      "name": "trail_policy_history_guardrails",
      "rationale": "The counts prevent a history-rich policy from extrapolating from sparse or non-comparable records. They are conservative pilot qualifications, not safety, adaptation, or readiness thresholds.",
      "value": {
        "comparable_hilly_or_trail_sessions_within_completed_days": {
          "count": 2,
          "window": 42
        },
        "latest_comparable_hilly_or_trail_session_within_completed_days": 21,
        "latest_run_within_completed_days": 10,
        "minimum_running_sessions_per_usable_week": 3,
        "minimum_usable_completed_weeks": 4,
        "qualifying_activity_requires": [
          "outdoor_running_or_trail_running",
          "positive_duration_and_distance",
          "usable_elevation_gain_and_loss_or_explicit_unknown",
          "source_timestamp"
        ],
        "recent_history_lookback_completed_weeks": 8,
        "sparse_or_stale_result": "insufficient_comparable_trail_history",
        "thresholds_are_published_biological_laws": false,
        "unknown_descent_or_terrain_cannot_satisfy_comparable_exposure": true
      }
    },
    {
      "applies_to": "deterministic early-block schedule",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "non-ultra-trail.training-specificity-promising-not-prescriptive"
      ],
      "name": "trail_policy_schedule_construction",
      "rationale": "Median, maximum, and athlete caps organize existing exposure without automatic progression. One quality session is a conservative Product choice for the first block, not a universal optimum.",
      "value": {
        "below_minimum_result": "no_schedule_within_envelope",
        "easy_and_longest_easy_allocation": {
          "automatic_longest_easy_increase": false,
          "preferred_longest_easy_day_used_when_available": true,
          "quality_minutes_allocated_first": true,
          "remaining_minutes_distributed_across_non_quality_days": true
        },
        "no_schedule_result": "no_schedule_within_envelope",
        "non_taper_progression_above_recent_median": false,
        "quality_sessions_per_7_day_unit": 1,
        "requested_above_maximum_result": "clarification_required",
        "selected_running_days_per_7_day_unit": {
          "deterministic_value": "minimum_of_available_days_recent_modal_days_and_policy_maximum",
          "maximum": 6,
          "minimum": 3
        },
        "session_duration_hard_cap": "minimum_of_recent_maximum_completed_session_and_athlete_limit",
        "target_time_gap_may_raise_load": false,
        "weekly_running_minutes_hard_cap": "minimum_of_recent_maximum_usable_weekly_minutes_and_athlete_limit",
        "weekly_running_minutes_target": "minimum_of_recent_median_usable_weekly_minutes_and_athlete_limit"
      }
    },
    {
      "applies_to": "eligible early-block quality session",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.hr-and-road-pace-not-sole-targets",
        "non-ultra-trail.uphill-downhill-require-distinct-handling"
      ],
      "name": "trail_policy_workout_templates",
      "rationale": "This transparent, targetless controlled-uphill template provides one deterministic trail-specific stimulus without claiming universal target zones or prescribing downhill speed. Its exact durations are reversible Product guardrails.",
      "value": {
        "controlled_quality": {
          "steps": [
            {
              "duration_minutes": 10,
              "intended_intensity": "low",
              "kind": "step",
              "phase": "warmup"
            },
            {
              "kind": "repeat",
              "repetitions": 4,
              "steps": [
                {
                  "duration_minutes": 3,
                  "intended_intensity": "controlled_uphill_effort",
                  "kind": "step",
                  "phase": "work"
                },
                {
                  "duration_minutes": 2,
                  "intended_intensity": "low",
                  "kind": "step",
                  "phase": "recovery"
                }
              ]
            },
            {
              "duration_minutes": 8,
              "intended_intensity": "low",
              "kind": "step",
              "phase": "cooldown"
            }
          ],
          "template_id": "trail-controlled-uphill-quality-v1",
          "total_planned_minutes": 38
        },
        "downhill_recovery_may_be_prescribed": false,
        "easy": "duration_only_with_optional_accessible_terrain_category",
        "exact_hr_pace_power_or_rpe_target": false,
        "longest_easy": "duration_only_with_observed_duration_and_course_exposure_caps",
        "target_expression": "duration_phase_and_effort_label_only",
        "template_must_fit_history_constraint_and_exposure_caps": true,
        "template_optimum_claim": false,
        "work_step_requires_accessible_non_technical_uphill": true
      }
    },
    {
      "applies_to": "all planned running minutes",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.hr-and-road-pace-not-sole-targets",
        "non-ultra-trail.training-specificity-promising-not-prescriptive"
      ],
      "name": "trail_policy_intensity_and_spacing",
      "rationale": "The low-intensity floor, one-quality ceiling, and spacing rule are conservative pilot choices for a no-progression block, not published universal thresholds.",
      "value": {
        "activity_average_power_allowed": false,
        "consecutive_quality_running_days_allowed": false,
        "historical_intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "low_intensity_fraction_is_optimum_claim": false,
        "maximum_quality_exposures_per_7_day_unit": 1,
        "minimum_intervening_easy_rest_or_non_running_days": 1,
        "minimum_planned_low_intensity_running_minutes_fraction": 0.75,
        "missed_quality_makeup_allowed": false,
        "quality_exposures_include": [
          "controlled_quality_template",
          "confirmed_race_or_maximal_effort"
        ],
        "reduce_or_remove_quality_before_adding_minutes": true
      }
    },
    {
      "applies_to": "early-block terrain and vertical exposure",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.uphill-downhill-require-distinct-handling",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "eligibility.fixed-progression-and-acwr-not-safety-laws"
      ],
      "name": "trail_policy_course_exposure_caps",
      "rationale": "Separate observed ascent, descent, and terrain caps avoid inventing a conversion or progression while enabling course-relevant organization.",
      "value": {
        "automatic_vertical_progression": false,
        "high_speed_or_maximal_downhill_repeats": false,
        "road_or_flat_substitution_claimed_equivalent": false,
        "session_ascent_hard_cap": "recent_maximum_completed_session_ascent",
        "session_descent_hard_cap": "recent_maximum_completed_session_descent",
        "technicality": "no_more_difficult_than_recently_observed_and_currently_accessible_category",
        "unknown_descent_or_technicality_result": "clarification_or_limited_module",
        "weekly_ascent_hard_cap": "recent_maximum_usable_weekly_ascent",
        "weekly_ascent_target": "no_more_than_recent_median_usable_weekly_ascent",
        "weekly_descent_hard_cap": "recent_maximum_usable_weekly_descent",
        "weekly_descent_target": "no_more_than_recent_median_usable_weekly_descent"
      }
    },
    {
      "applies_to": "dated trail goals",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.taper-direction-indirect"
      ],
      "name": "trail_policy_event_and_taper",
      "rationale": "General endurance evidence is insufficient to select a trail-specific taper here. Early blocks remain usable while the event-near path fails closed pending a successor decision.",
      "value": {
        "event_day_generated_as_training_workout": false,
        "event_or_race_counts_as_quality_and_load": true,
        "imported_event_must_be_athlete_confirmed": true,
        "taper_implementation": "not_accepted",
        "target_more_than_14_days_after_start": "normal_14_day_rolling_proposal",
        "target_within_14_days_of_start": "event_inside_unapproved_taper_window"
      }
    },
    {
      "applies_to": "readiness and generation responses",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "trail-ontology.course-demand-is-multidimensional"
      ],
      "name": "trail_policy_typed_outcomes",
      "rationale": "Typed failures remain useful and honest without returning a success-shaped road schedule or erasing the athlete's goal.",
      "value": {
        "candidate_success": "eligible_proposal",
        "goal_remains_recorded": true,
        "limited_modules": [
          "environment_module_limited",
          "fueling_module_limited",
          "technicality_module_limited"
        ],
        "no_plan": [
          "ontology_not_accepted",
          "policy_inactive",
          "course_clarification_required",
          "material_course_demand_unknown",
          "insufficient_comparable_history",
          "insufficient_terrain_access",
          "adult_scope_or_constraints_unconfirmed",
          "current_symptom_stop",
          "unsupported_ultra_or_multiday",
          "validation_failed"
        ],
        "road_fallback": false
      }
    },
    {
      "applies_to": "future deterministic generator envelope",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.uphill-downhill-require-distinct-handling",
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.taper-direction-indirect",
        "non-ultra-trail.fueling-duration-and-practice-context"
      ],
      "name": "trail_policy_modular_structure",
      "rationale": "Modular handling preserves distinct demands and uncertainty without claiming one universal trail schedule.",
      "value": {
        "module_requires_matching_input": true,
        "modules": [
          "readiness_and_history",
          "easy_and_aerobic",
          "ascent_specificity",
          "descent_and_neuromuscular_exposure",
          "technical_terrain",
          "hiking",
          "strength",
          "longest_session_and_fueling_practice",
          "taper",
          "environment_and_altitude",
          "reassessment_and_outcome"
        ],
        "unavailable_module_may_be_silently_replaced": false
      }
    },
    {
      "applies_to": "module selection and ScienceNote claims",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "non-ultra-trail.observed-load-does-not-prove-prescription",
        "non-ultra-trail.taper-direction-indirect",
        "non-ultra-trail.fueling-duration-and-practice-context"
      ],
      "name": "trail_policy_evidence_use",
      "rationale": "This distinguishes evidence-supported directions from exact prescriptions the sources do not establish.",
      "value": {
        "fueling": "expected_duration_and_practice_context_only",
        "hiking": "conditional_candidate_module",
        "injury_and_fatigue_findings": "safety_context_only",
        "observed_load_associations": "descriptive_only",
        "strength_and_multimodal": "conditional_candidate_module",
        "taper": "indirect_direction_only",
        "trail_specificity": "conditional_candidate_module"
      }
    },
    {
      "applies_to": "all future policy and implementation surfaces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.hr-and-road-pace-not-sole-targets",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "eligibility.current-symptoms-support-stop-not-clearance"
      ],
      "name": "trail_policy_hard_boundaries",
      "rationale": "These boundaries prevent unsupported inference, hidden load escalation, medical claims, and authority expansion.",
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "canonical_adoption_requires_explicit_athlete_action": true,
        "diagnosis_or_clearance": false,
        "heart_rate_or_level_pace_may_be_sole_hilly_controller": false,
        "missed_work_may_create_catch_up": false,
        "performance_injury_or_safety_guarantee": false,
        "personal_finish_probability": false,
        "provider_delivery_requires_separate_explicit_consent": true,
        "road_policy_fallback": false,
        "target_gap_may_raise_dose": false,
        "universal_ascent_descent_equivalence": false,
        "universal_distance_vertical_conversion": false,
        "valid_intensity_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    {
      "applies_to": "scope outside the early rolling block",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.training-specificity-promising-not-prescriptive",
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "non-ultra-trail.taper-direction-indirect",
        "non-ultra-trail.fueling-duration-and-practice-context"
      ],
      "name": "trail_policy_deferred_scope",
      "rationale": "The accepted early-block values remain deliberately narrow; these higher-load, event-near, fixed-dose, and target-specific behaviors need a successor decision.",
      "value": {
        "back_to_back_sessions": "not_accepted",
        "fueling_amount_or_frequency": "not_accepted",
        "hiking_threshold_or_dose": "not_accepted",
        "hr_pace_power_or_rpe_targets": "not_accepted",
        "outcome_window_or_meaningful_change": "not_accepted",
        "progression_above_recent_typical_load": "not_accepted",
        "recovery_interval": "not_accepted",
        "strength_frequency_or_dose": "not_accepted",
        "taper_duration_and_reduction": "not_accepted",
        "technical_terrain_dose": "not_accepted",
        "vertical_or_downhill_progression_above_recent_history": "not_accepted"
      }
    },
    {
      "applies_to": "inactive dry run and separately authorized owner pilot",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "non-ultra-trail.injury-fatigue-no-safe-dose",
        "eligibility.fixed-progression-and-acwr-not-safety-laws"
      ],
      "name": "trail_policy_runtime_evaluation",
      "rationale": "Zero-tolerance deterministic failures and a conservative edit threshold make the reversible owner pilot observable without turning one athlete's process data into efficacy or safety evidence.",
      "value": {
        "dry_run": {
          "deterministic_invariant_breach_tolerance": 0,
          "replay_mismatch_tolerance": 0,
          "unsupported_or_material_unknown_plan_tolerance": 0
        },
        "efficacy_or_safety_claim_from_process_pilot": false,
        "owner_only_pilot": {
          "major_edit_definition": "session_duration_or_vertical_change_over_twenty_percent_or_two_scheduled_days_changed",
          "maximum_major_edit_fraction": 0.3,
          "serious_plausibly_related_report_pause_threshold": 1
        },
        "pause_or_revise_when_threshold_crossed": true
      }
    },
    {
      "applies_to": "work outside Science authority",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "trail_policy_non_science_authority",
      "rationale": "Product, Design, Engineering, Quality, Operations, and provider decisions require their own linked artifacts and authority.",
      "value": {
        "deployment": "not_accepted",
        "garmin_mapping": "not_accepted",
        "implementation_review": "required",
        "owner_only_pilot": "not_accepted",
        "product_visibility": "not_accepted",
        "runtime_activation": "not_accepted"
      }
    }
  ],
  "model_version": "non-ultra-trail-plan-generation-policy-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Persist only normalized course-demand, constraint, and aggregate history snapshots needed for deterministic replay.",
    "Do not copy raw activities, samples, route files, free text, provider payloads, or target values into generic telemetry.",
    "Owner-scoped goal, proposal, adoption, export, deletion, and account-deletion paths remain mandatory."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Copy a road 10K, half-marathon, or marathon schedule and add elevation",
      "rationale": "Road policies do not preserve descent, grade, technicality, terrain access, hiking, or trail-specific mechanical exposure."
    },
    {
      "alternative": "Use distance plus ascent to select a complete trail plan",
      "rationale": "Material course, environment, support, expected-duration, access, and history dimensions would remain unknown."
    },
    {
      "alternative": "Use one universal weekly elevation or downhill progression",
      "rationale": "Current intervention and injury evidence does not validate such a safe or optimal individual dose."
    },
    {
      "alternative": "Use heart rate, road pace, ACWR, or activity-average power as the sole controller",
      "rationale": "Slope-specific metabolic and mechanical demands and evidence limitations make those unsupported sole representations."
    },
    {
      "alternative": "Let an LLM choose the schedule and validate it afterward",
      "rationale": "Post-hoc validation cannot make unsupported assumptions or values accepted and cannot broaden the deterministic capability envelope."
    }
  ],
  "safety_implications": [
    "Current symptoms stop performance optimization and route outside this nonclinical policy.",
    "Missing material course demand, history, or terrain access fails closed or limits only a separately supported module.",
    "No catch-up, target-gap load escalation, fixed progression law, or road fallback is allowed.",
    "Downhill and technical exposure must stay within separately approved history-anchored bounds."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Use a history-anchored 14-day non-ultra trail performance block",
  "user_facing_claim_limits": [
    "Do not present the policy as a road plan adjusted for elevation.",
    "Do not claim one universal vertical, descent, technicality, hiking, strength, long-run, taper, or fueling dose.",
    "Do not use heart rate, road pace, ACWR, or activity-average power as a sole or safety-validating controller.",
    "Do not show a personal finish probability, target guarantee, injury-prevention guarantee, diagnosis, or clearance."
  ],
  "validation_plan": [
    "Validate the exact fourteen-day generator parameters and generated contract digest before human review.",
    "Replay capability matching across missingness, terrain-access, course, history, environment, and support boundaries.",
    "Unit-test history qualification, schedule allocation, targetless quality-template steps, low-intensity fraction, quality spacing, and separate ascent/descent/technicality caps.",
    "Compare every generated exposure only with owner-scoped immutable history snapshots using splits or samples for intensity.",
    "Verify proposals cannot mutate canonical workouts or provider calendars before exact athlete adoption and separate delivery consent.",
    "Dry-run before owner access, then prospectively observe typed outcomes, edits, adoption, withdrawal, validation failures, and adverse signals only after separate owner-pilot authority."
  ],
  "version": 1
}
```

</details>
