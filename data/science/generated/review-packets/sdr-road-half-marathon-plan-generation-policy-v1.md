# Science decision review packet: History-anchored adult outdoor road half-marathon performance policy

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-road-half-marathon-plan-generation-policy-v1`
- **Lifecycle:** `draft`
- **Model version:** `road-half-marathon-plan-generation-policy-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:8b578c26dc6ed33eaed91c881edb68de4693a657f370d37e98d96ef04e35ed68`
- **Contract digest:** `sha256:a1d99a0b562d2b5a04ae5057793dd915e486c7dc5f3667e26aff197210942afe`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the four proposed policy boundaries are acceptable and whether the four listed implementation areas should remain explicitly deferred. Approve the sheet as a unit, or request changes by item ID. The exact contract is an audit appendix, not the primary review task.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `supported-scope` — Accept the narrow V1 population and goal scope

- **Question:** Should V1 recognize adult outdoor-road half-marathon performance goals only when current direct capability, stable history, within-recent load, event context, and symptom-stop inputs match the stated pattern?
- **Proposed decision:** Accept that narrow pattern, preserve every user's goal when no route matches, and use typed no-plan or limited-guidance outcomes instead of silently substituting another distance or intent.
- **Approval means:**
  - The half-marathon performance pattern becomes an accepted policy boundary.
  - First-completion, sparse-history, trail, treadmill, clinical, marathon, and ultra cases remain separate policies.
  - A future implementation may expose these typed outcomes only after separate implementation approval.
- **This does not authorize:**
  - Any generated workout, schedule, target-time guarantee, or automatic benchmark.
  - Runtime activation, plan adoption, delivery, or publication.

<details><summary>Traceability: 5 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `road_half_marathon_activation_and_dependency`, `road_half_marathon_goal_tuple`, `road_half_marathon_supported_training_pattern`, `road_half_marathon_event_context`, `road_half_marathon_typed_outcomes`
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `eligibility.current-symptoms-support-stop-not-clearance`, `eligibility.masters-age-change-not-automatic-exclusion`, `road-half-marathon.task-specific-capability-is-multifactor`

</details>

#### `evidence-use` — Accept how population evidence may and may not be used

- **Question:** Should the reviewed volume, longest-run, taper, fueling, and prediction findings be retained as bounded evidence context rather than converted into personal thresholds or prescriptions?
- **Proposed decision:** Accept the reported source findings and their uncertainty labels for explanation and later validation, while prohibiting personal probability, causal plan-benefit, universal dose, and distance-only fueling claims.
- **Approval means:**
  - Published findings may support review notes, uncertainty, and future validation design.
  - Before/after outcomes require comparable protocols and remain descriptive rather than causal.
- **This does not authorize:**
  - Treating 32 km per week, a 21 km long run, taper ranges, or fueling ranges as eligibility or prescription.
  - A personal success probability, injury probability, responder label, or medically safe claim.

<details><summary>Traceability: 5 contract groups, 5 evidence claims</summary>

- **Contract groups covered:** `road_half_marathon_published_volume_and_long_run_findings`, `road_half_marathon_published_taper_findings`, `road_half_marathon_published_fueling_findings`, `road_half_marathon_protocol_comparability_and_outcomes`, `road_half_marathon_user_facing_uncertainty`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-half-marathon.volume-and-long-run-are-associative`, `road-half-marathon.taper-is-indirectly-supported`, `road-half-marathon.fueling-and-gut-practice-supported`, `road-half-marathon.direct-field-baseline-preferred-with-error`

</details>

#### `hard-boundaries` — Accept conservative safety, consent, and automation boundaries

- **Question:** Should Praxys prohibit automatic maximal half-marathon baseline tests, target-gap dose escalation, generic progression laws, activity-average-power intensity analysis, missed-workout makeup, unpracticed race fueling, sensitive inference, and AI authority expansion?
- **Proposed decision:** Accept those prohibitions and keep every future plan suggestion-only, athlete-editable, explicitly adopted, auditable, and subordinate to symptom stops and deterministic validation.
- **Approval means:**
  - Direct capability cannot be manufactured from predictions or passive segments.
  - AI cannot invent missing context, select deferred rules, approve, activate, adopt, or deliver a plan.
  - Athlete constraints, consent, privacy, and symptom stops remain hard boundaries.
- **This does not authorize:**
  - The unresolved numeric or algorithmic parts of the same contract groups.
  - Medical diagnosis, clearance, treatment, or inference of sensitive context.

<details><summary>Traceability: 9 contract groups, 5 evidence claims</summary>

- **Contract groups covered:** `road_half_marathon_direct_baseline_hierarchy`, `road_half_marathon_target_and_short_horizon_routing`, `road_half_marathon_history_anchored_load_and_long_run`, `road_half_marathon_intensity_structure`, `road_half_marathon_recovery_boundary`, `road_half_marathon_selected_taper_guardrail`, `road_half_marathon_fueling_practice_policy`, `road_half_marathon_suggestion_only_state_transition`, `road_half_marathon_privacy_and_audit`
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `eligibility.current-symptoms-support-stop-not-clearance`, `road-half-marathon.direct-field-baseline-preferred-with-error`, `road-half-marathon.exact-long-run-dose-unproven`, `road-half-marathon.recovery-spacing-unresolved`

</details>

#### `mostly-low-structure` — Accept a mostly-low-intensity organizational boundary

- **Question:** Should any future V1 plan use a mostly-low-intensity structure while leaving the exact low-intensity percentage, quality-session count, distribution model, and workout mix unresolved?
- **Proposed decision:** Accept only the broad mostly-low organizational boundary, based on indirect mixed-distance endurance evidence, without claiming one universally superior polarized, pyramidal, threshold, or race-pace distribution.
- **Approval means:**
  - A future implementation must organize more work as low intensity than as threshold or high intensity.
  - The boundary must remain labelled as indirect to adult road half-marathon planning.
- **This does not authorize:**
  - A low-intensity percentage, quality-session ceiling, exact spacing, or named distribution model.
  - Any use of activity-average power for intensity analysis.

<details><summary>Traceability: 1 contract group, 1 evidence claim</summary>

- **Contract groups covered:** `road_half_marathon_intensity_structure`
- **Evidence claims:** `road-half-marathon.intensity-distribution-no-universal-winner`

</details>

### Decisions explicitly deferred

#### `defer-baseline-history` — Defer baseline qualification and history sufficiency

- **Question:** Should exact direct-result qualification, freshness, history counts, lookback, and reassessment cadence remain unresolved?
- **Proposed decision:** Keep these values and algorithms unaccepted until a later decision can compare options and validation consequences.
- **Approval means:**
  - Missing or stale capability and insufficient history remain typed readiness limitations.
  - No implementation may copy 5 km or 10 km thresholds or invent defaults.
- **This does not authorize:**
  - A distance tolerance, result expiry, minimum week/run count, or fixed reassessment cadence.
  - An automatic maximal half-marathon baseline test.

<details><summary>Traceability: 4 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `road_half_marathon_direct_baseline_hierarchy`, `road_half_marathon_baseline_freshness`, `road_half_marathon_recent_history_inputs`, `road_half_marathon_planning_and_reassessment`
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.goal-relevant-current-capability-task-specific`, `road-half-marathon.direct-field-baseline-preferred-with-error`

</details>

#### `defer-dose-taper` — Defer training dose, session structure, recovery, and taper

- **Question:** Should frequency, progression, long-run dose, intensity distribution, quality spacing, short-horizon handling, taper, and event-minute accounting remain unresolved?
- **Proposed decision:** Keep every exact schedule and dose choice unaccepted; retain only the approved hard prohibitions and source findings.
- **Approval means:**
  - Future research or product review must select each value explicitly.
  - A near target date cannot trigger catch-up or hidden dose escalation.
- **This does not authorize:**
  - A weekly frequency range, low-intensity percentage, quality count, long-run share, or progression rate.
  - An execution window, workout template, taper percentage/window, recovery interval, or event-minute formula.

<details><summary>Traceability: 5 contract groups, 5 evidence claims</summary>

- **Contract groups covered:** `road_half_marathon_target_and_short_horizon_routing`, `road_half_marathon_history_anchored_load_and_long_run`, `road_half_marathon_intensity_structure`, `road_half_marathon_recovery_boundary`, `road_half_marathon_selected_taper_guardrail`
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `road-half-marathon.exact-long-run-dose-unproven`, `road-half-marathon.intensity-distribution-no-universal-winner`, `road-half-marathon.recovery-spacing-unresolved`, `road-half-marathon.taper-is-indirectly-supported`

</details>

#### `defer-fueling` — Defer product fueling rules

- **Question:** Should product duration bands, intake ranges or caps, carbohydrate loading thresholds, and exact prompts remain unresolved?
- **Proposed decision:** Keep the product rules unaccepted while retaining only the approved evidence-use limits, prior-practice requirement, and distance-only automation prohibition.
- **Approval means:**
  - Fueling guidance cannot route from the half-marathon label alone.
  - Future rules must consider expected duration, prior practice, tolerance, and athlete preference.
- **This does not authorize:**
  - A 90-minute product threshold or a 30 to 60 grams-per-hour personal prescription.
  - A new race-day strategy without practice and athlete choice.

<details><summary>Traceability: 1 contract group, 1 evidence claim</summary>

- **Contract groups covered:** `road_half_marathon_fueling_practice_policy`
- **Evidence claims:** `road-half-marathon.fueling-and-gut-practice-supported`

</details>

#### `defer-pilot-activation` — Defer pilot thresholds and all remaining open decisions

- **Question:** Should statistical go/no-go thresholds, safety pause thresholds, exact workouts, and every catalogued open decision remain unresolved before implementation or activation?
- **Proposed decision:** Keep the contract inactive and require separately reviewed values, implementation mapping, deterministic replay, and an opt-in pilot protocol before runtime use.
- **Approval means:**
  - Deterministic invariant and replay tolerance remain zero.
  - All statistical, schedule, and rollout thresholds remain explicit future decisions.
- **This does not authorize:**
  - Implementing unresolved values, marking the capability available, or running a pilot.
  - Treating this science decision approval as implementation or activation approval.

<details><summary>Traceability: 3 contract groups, 2 evidence claims</summary>

- **Contract groups covered:** `road_half_marathon_planning_and_reassessment`, `road_half_marathon_validation_and_pilot_thresholds`, `road_half_marathon_open_decisions`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-half-marathon.subgroup-dose-rules-unproven`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve the supported scope, evidence-use limits, and hard safety and control boundaries below, including a mostly-low-intensity organizational boundary without an exact distribution. I also agree that baseline/history rules, training dose and taper, fueling rules, and pilot thresholds remain deferred. I understand this decision stays inactive and does not approve implementation or runtime activation.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-road-half-marathon-plan-generation-policy-v1`
- Digest: `sha256:8b578c26dc6ed33eaed91c881edb68de4693a657f370d37e98d96ef04e35ed68`

> I approve the supported scope, evidence-use limits, and hard safety and control boundaries below, including a mostly-low-intensity organizational boundary without an exact distribution. I also agree that baseline/history rules, training dose and taper, fueling rules, and pilot thresholds remain deferred. I understand this decision stays inactive and does not approve implementation or runtime activation.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:8b578c26dc6ed33eaed91c881edb68de4693a657f370d37e98d96ef04e35ed68","subject_id":"sdr-road-half-marathon-plan-generation-policy-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If accepted by a digest-bound decision approver, this SDR would authorize only an inactive-by-default policy boundary for adult outdoor road half-marathon performance intent with current direct half-marathon capability, stable recent history, within-recent load, confirmed event context, and absent current symptom-stop inputs. The goal could have an optional target time and date and would remain recorded when no generator route matches. Population evidence would inform uncertainty, taper, and fueling communication without creating a personal success probability. This draft does not select a direct-baseline qualification algorithm, baseline freshness window, minimum history counts, frequency envelope, exact volume progression, low-intensity percentage, quality-session ceiling, long-run share or distance, hard-session spacing, taper prescription or accounting, execution window, fueling duration or intake rules, workout templates, aggressive short-horizon alternative, or pilot thresholds. It does not activate a generator or authorize beginner, sparse-history, clinical, trail, marathon, or ultra planning.

### Linked evidence

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

#### `eligibility.evidence-quality-no-personal-probability` — moderate

Running-injury evidence is heterogeneous and often low quality, while individual exercise-response classification is methodologically fragile unless measurement error and within-person variability are addressed. These limitations support explicit evidence-directness states and reject personal success probabilities or deterministic responder labels.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `correia-2024`, `bonafiglia-2021`
- **Limitations:** The exercise-response review was not a running-plan prediction study.; Low evidence quality does not make personalization impossible.; No source provides a calibrated plan-generation success probability.

#### `eligibility.masters-age-change-not-automatic-exclusion` — moderate

Endurance performance and training capacity change with age, while masters athletes and older adults can retain high capability and benefit from continued exercise. The reviewed evidence supports neither automatic exclusion by age nor a universal age cutoff or recovery rule.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `tanaka-2008`, `chodzko-zajko-2009`, `burtscher-2022`
- **Limitations:** Masters athletes are selected, trained populations and are not representative of every older runner.; The evidence does not define an age cutoff, recovery rule, or safe automatic plan.; Treating age as an uncertainty or recovery modifier is a Praxys guardrail that requires prospective validation.; Women and older women are underrepresented.

#### `road-half-marathon.task-specific-capability-is-multifactor` — low

Half-marathon performance and pacing reflect multiple interacting training, physiological, anthropometric, biomechanical, age, and sex factors rather than one marker. This supports task-specific capability matching but not a universal durability score or single-marker gate.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `ogueta-alday-2018`, `gomez-molina-2017`, `nikolaidis-2019-ljubljana`, `cuk-2019-vienna`
- **Limitations:** Predictor studies do not establish causal training prescriptions; Direct durability mechanisms and individual thresholds were not validated; Male-heavy samples limit subgroup transfer

#### `road-half-marathon.volume-and-long-run-are-associative` — moderate

Higher recent weekly running volume and longer single-run exposure are associated with faster half-marathon finish time and less pace decline, but the observational evidence does not establish a universal weekly dose, frequency, longest-run minimum, or injury-safe prescription.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `fokkema-2020`
- **Limitations:** Self-reported training exposure; Categorical observational comparisons rather than randomized dose response; No causal proof of safety, optimality, or progression rate

#### `road-half-marathon.taper-is-indirectly-supported` — moderate

Mixed-endurance evidence supports reducing training volume while maintaining intensity and usually frequency before a key event, with the strongest pooled subgroup signal around 8 to 14 days. The evidence does not validate one half-marathon-specific taper template or personal gain.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `wang-2023`
- **Limitations:** Mixed sports and event distances; Not a direct adult road half-marathon taper trial set; Heterogeneous prior training and protocols

#### `road-half-marathon.fueling-and-gut-practice-supported` — moderate

Carbohydrate intake during exercise is supported around half-marathon-duration efforts, with small amounts or mouth rinse useful around one hour and 30 to 60 grams per hour supported for longer endurance exercise. Practicing intake can reduce gastrointestinal discomfort and carbohydrate malabsorption, but tolerance and race duration remain individual and gut-training performance effects are uncertain.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `burke-2011`, `burke-2019-iaaf`, `martinez-2023`, `podlogar-2022`
- **Limitations:** Most numeric guidance is broader endurance evidence rather than half-marathon-only evidence; Expected duration varies substantially within the same race distance; No universal carbohydrate-loading rule applies to every half-marathon runner

#### `road-half-marathon.direct-field-baseline-preferred-with-error` — low

Recent same-task or closely comparable field performance is more direct for half-marathon capability than laboratory markers or multivariable predictions alone. Even validated prediction models retain meaningful error and do not support a personal success probability.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `alvero-cruz-2019`, `nikolaidis-knechtle-2023-hm-predictors`, `gomez-molina-2017`
- **Limitations:** Small or male-only samples; Field-test equations are not universal replacements for same-task results; Prediction error remains material for an individual goal

#### `road-half-marathon.exact-long-run-dose-unproven` — low

Meaningful longest-run exposure is associated with half-marathon performance, but no reviewed randomized evidence establishes an exact longest-run share of weekly volume, exact ceiling, mandatory distance, or universal progression rule.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `fokkema-2020`
- **Limitations:** One categorical observational half-marathon study anchors the direct evidence; A longest run above race distance cannot be generalized as a requirement; Injury non-association in the cohort is not a safety guarantee

#### `road-half-marathon.intensity-distribution-no-universal-winner` — moderate

Mostly-low-intensity organization with some threshold, interval, or race-specific work is broadly supported, but direct and mixed-distance evidence does not establish one universally superior polarized, pyramidal, threshold-heavy, quality-session count, or race-pace distribution for half-marathon planning. In the cited 10 km trial, both groups improved and the primary between-group difference was not statistically significant.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `munoz-2014`, `campos-2022`, `rosenblat-2025`, `boullosa-2020`
- **Limitations:** Different zone definitions, event distances, and sports; No direct adult road half-marathon intervention establishes an exact distribution; One to two quality sessions per week remains an indirect coaching-oriented recommendation; The cited 5.0 versus 3.6 percent trial changes did not differ significantly in the primary comparison

#### `road-half-marathon.recovery-spacing-unresolved` — low

Direct evidence does not establish one optimal recovery strategy or exact spacing rule between half-marathon training sessions. Post-race studies suggest different outcomes may recover over roughly one to three days and that higher-intensity recovery running can delay recovery, but these findings do not define a universal schedule rule.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `li-2024`, `wang-2025-hm-recovery`, `zhou-2026-hm-mri-recovery`
- **Limitations:** Small direct half-marathon samples; Outcomes differ across biomechanics, proprioception, and MRI markers; Post-race recovery does not directly prescribe routine training-session spacing

#### `road-half-marathon.subgroup-dose-rules-unproven` — low

Women and older adults are represented in large half-marathon pacing and performance datasets, but direct training-response and prediction studies remain male-heavy. Observed age or sex differences do not establish subgroup-specific automatic training doses.

- **Evidence Review:** `evidence-road-half-marathon-plan-generation-policy-v1`
- **Sources:** `leyk-2007`, `nikolaidis-2019-ljubljana`, `cuk-2019-vienna`, `gomez-molina-2017`, `alvero-cruz-2019`, `nikolaidis-knechtle-2023-hm-predictors`
- **Limitations:** Observational pacing and participation data do not establish dose response; Direct predictor studies are predominantly male; Unknown sex or age cannot be converted into a hidden default

### Reviewed parameters

#### `road_half_marathon_activation_and_dependency` — guardrail

- **Applies to:** policy lifecycle and capability registry
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Draft science, generated artifacts, and review packets do not activate product behavior. Acceptance, implementation review, exact unresolved guardrails, deterministic validation, and rollout remain separate gates.
- **Exact value:**

```json
{
  "active_behavior": false,
  "capability_registry_entry_default_enabled": false,
  "decision_approval_artifact_required": true,
  "distance_policy_required_status_before_activation": "accepted",
  "evidence_review_required_status_before_activation": "accepted",
  "generator_api_web_miniapp_plugin_and_mcp_activation_in_this_record": false,
  "implementation_approval_artifact_required": true,
  "shared_policy_dependency": {
    "required_status_before_activation": "accepted",
    "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
  }
}
```

#### `road_half_marathon_goal_tuple` — guardrail

- **Applies to:** goal normalization and distance-policy selection
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `road-half-marathon.task-specific-capability-is-multifactor`
- **Rationale:** Goal choice remains durable and independent from generator availability. This distance policy is limited to current performance intent and cannot be scaled down to completion or sparse-history populations.
- **Exact value:**

```json
{
  "goal_intent": "performance",
  "goal_kind": "distance_half_marathon",
  "no_event_goal_may_remain_recorded": true,
  "primary_outcome": "elapsed_time",
  "separate_policy_variants": [
    "first_half_marathon_completion",
    "sparse_history_half_marathon",
    "treadmill_half_marathon",
    "trail_half_marathon",
    "multisport_run_leg",
    "marathon_or_ultra",
    "medically_directed_rehabilitation",
    "pregnancy_specific_planning"
  ],
  "sport": "running",
  "surface": "outdoor_road",
  "target_date_optional": true,
  "target_time_optional": true
}
```

#### `road_half_marathon_supported_training_pattern` — guardrail

- **Applies to:** shared pattern routing
- **Evidence claims:** `eligibility.current-symptoms-support-stop-not-clearance`, `eligibility.masters-age-change-not-automatic-exclusion`, `road-half-marathon.subgroup-dose-rules-unproven`
- **Rationale:** V1 matches a time-bounded evidence pattern rather than a recreational, serious, professional, elite, female, male, or masters identity.
- **Exact value:**

```json
{
  "adult_scope": "confirmed",
  "capability_pattern": "currently_capable",
  "current_symptoms": "absent",
  "event_context": [
    "confirmed_none",
    "single_target",
    "race_dense"
  ],
  "evidence_directness": [
    "direct",
    "supporting"
  ],
  "explicit_exclusions": [
    "adult_scope_unconfirmed",
    "first_half_marathon_completion_requires_separate_policy",
    "sparse_interrupted_or_missing_history",
    "current_injury_illness_or_concerning_symptoms",
    "rehabilitation_return_to_sport_or_medical_clearance",
    "pregnancy_specific_prescription",
    "unresolved_material_event_context",
    "unsupported_surface_distance_or_intent"
  ],
  "history_pattern": "stable",
  "load_pattern": "within_recent",
  "permanent_runner_identity_used": false,
  "race_dense_requires_resolved_conflicts": true
}
```

#### `road_half_marathon_direct_baseline_hierarchy` — guardrail

- **Applies to:** baseline qualification
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `road-half-marathon.task-specific-capability-is-multifactor`, `road-half-marathon.direct-field-baseline-preferred-with-error`
- **Rationale:** Same-task field evidence is most direct. Prediction, physiology, and shorter-distance performance may support context but retain meaningful individual error and cannot silently authorize generation.
- **Exact value:**

```json
{
  "accepted_evidence_order": [
    "organized_outdoor_road_half_marathon_with_elapsed_time",
    "athlete_confirmed_standardized_outdoor_road_half_marathon_time_trial"
  ],
  "allowed_assistance_statuses": "not_accepted",
  "allowed_surface_values": "not_accepted",
  "automatic_maximal_baseline_test": "prohibited",
  "baseline_qualification_algorithm": "not_accepted",
  "direct_current_capability_required": true,
  "distance_match_tolerance_m": "not_accepted",
  "excluded_as_direct": [
    "shorter_race_conversion",
    "marathon_or_ultra_split",
    "passive_fastest_half_marathon_segment",
    "personal_best_without_source_activity",
    "activity_average_power",
    "vendor_readiness_or_race_score"
  ],
  "missing_direct_result_outcome": "insufficient_direct_half_marathon_baseline",
  "required_metadata": [
    "completed_at",
    "elapsed_time_seconds",
    "measured_distance_m",
    "route_or_event_identifier",
    "surface",
    "assistance_status",
    "source_provider",
    "race_or_intentional_time_trial_flag"
  ],
  "standardized_time_trial_protocol": "not_accepted",
  "supporting_only": [
    "cooper_test",
    "current_vo2max_or_vvo2max",
    "current_threshold_or_critical_speed",
    "weekly_training_distance",
    "recent_longest_run",
    "race_forecast_with_error",
    "split_or_sample_pacing_distribution"
  ]
}
```

#### `road_half_marathon_baseline_freshness` — guardrail

- **Applies to:** capability freshness
- **Evidence claims:** `road-half-marathon.direct-field-baseline-preferred-with-error`
- **Rationale:** No reviewed source validates a half-marathon result expiry threshold. Selecting one is a product guardrail that must be reviewed separately before activation.
- **Exact value:**

```json
{
  "exact_current_through_completed_days": "not_accepted",
  "missing_or_stale_outcome": "readiness_only",
  "no_biological_expiry_claim": true,
  "required_before_activation": true,
  "stale_boundary": "not_accepted"
}
```

#### `road_half_marathon_recent_history_inputs` — guardrail

- **Applies to:** history-rich qualification
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `road-half-marathon.volume-and-long-run-are-associative`, `road-half-marathon.exact-long-run-dose-unproven`
- **Rationale:** History must anchor the runner's own exposure, but the review does not establish universal counts. Exact qualification remains visible rather than inheriting 5 km or 10 km values.
- **Exact value:**

```json
{
  "disallowed_intensity_source": [
    "activity_avg_power"
  ],
  "exact_lookback_weeks": "not_accepted",
  "history_qualification_algorithm": "not_accepted",
  "intensity_source_priority": [
    "activity_splits",
    "activity_samples"
  ],
  "latest_run_freshness_days": "not_accepted",
  "minimum_runs_per_usable_week": "not_accepted",
  "minimum_usable_weeks": "not_accepted",
  "required_observations": [
    "completed_weekly_running_minutes_and_distance",
    "completed_running_days_per_week",
    "recent_longest_run_duration_and_distance",
    "quality_session_and_event_density",
    "recent_load_relative_to_self",
    "availability_and_single_session_constraints",
    "prior_half_marathon_count_when_known"
  ],
  "unresolved_history_outcome": "insufficient_history_anchor"
}
```

#### `road_half_marathon_planning_and_reassessment` — guardrail

- **Applies to:** proposal horizon and reassessment
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.fixed-progression-and-acwr-not-safety-laws`, `road-half-marathon.volume-and-long-run-are-associative`
- **Rationale:** No reviewed evidence establishes an exact half-marathon plan horizon or reassessment cadence. Rolling context and explicit triggers are retained, while the committed execution window remains an open decision.
- **Exact value:**

```json
{
  "automatic_progression_between_reassessments": false,
  "each_reassessment_requires": [
    "fresh_shared_eligibility",
    "updated_history_and_longest_run",
    "updated_event_context",
    "updated_dynamic_pattern_snapshot",
    "updated_fueling_practice_context",
    "explicit_review_before_replacing_adopted_future_days"
  ],
  "exact_calendar_reassessment_cadence": "not_accepted",
  "exact_committed_execution_window_days": "not_accepted",
  "fixed_full_block_days": "none_defined",
  "fixed_horizon_eligibility_gate": false,
  "reassessment_triggers": [
    "new_or_changed_confirmed_event",
    "material_training_pattern_change",
    "new_qualified_half_marathon_result",
    "changed_availability_or_constraint",
    "changed_fueling_tolerance_or_practice",
    "completed_target_event",
    "athlete_requested_review"
  ],
  "target_date_required": false
}
```

#### `road_half_marathon_target_and_short_horizon_routing` — guardrail

- **Applies to:** target communication and short-horizon routing
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-half-marathon.direct-field-baseline-preferred-with-error`
- **Rationale:** Prediction error is material and no personal probability or compressed catch-up policy is validated. A short horizon limits the claim and available states rather than invalidating the athlete's goal.
- **Exact value:**

```json
{
  "aggressive_or_catch_up_variant": "not_accepted",
  "near_event_supported_states": [
    "readiness_only",
    "maintain",
    "taper_after_taper_guardrail_acceptance",
    "limited_guidance"
  ],
  "personal_goal_achievement_probability": "disabled",
  "personal_injury_probability": "disabled",
  "short_horizon_invalidates_goal": false,
  "target_gap_dose_escalation": "prohibited",
  "target_time_may": [
    "label_goal",
    "compute_descriptive_gap_to_direct_baseline",
    "select_uncertainty_copy"
  ],
  "target_time_may_not": [
    "increase_weekly_volume",
    "increase_frequency",
    "lengthen_longest_run",
    "add_quality",
    "weaken_history_or_safety_rules"
  ]
}
```

#### `road_half_marathon_event_context` — guardrail

- **Applies to:** event calendar and schedule conflicts
- **Evidence claims:** `road-half-marathon.recovery-spacing-unresolved`, `road-half-marathon.taper-is-indirectly-supported`, `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Event priority and dense-calendar behavior remain product guardrails. Confirmed events nevertheless consume load and quality capacity, and a maximal half-marathon benchmark is never silently created.
- **Exact value:**

```json
{
  "confirmed_primary_event_may_trigger_taper_only_after_taper_guardrail_acceptance": true,
  "every_race_or_maximal_effort": {
    "counts_as_quality_session": true,
    "counts_as_training_load": true,
    "requires_recovery_reassessment": true
  },
  "imported_event_must_be_athlete_confirmed": true,
  "no_event_performance_goal": {
    "automatic_half_marathon_benchmark": "prohibited",
    "goal_remains_recorded": true,
    "rolling_policy_before_activation": "readiness_only"
  },
  "shared_event_states_consumed": [
    "confirmed_none",
    "single_target",
    "race_dense"
  ],
  "unresolved_race_dense_outcome": "limited_guidance_event_conflict"
}
```

#### `road_half_marathon_published_volume_and_long_run_findings` — published

- **Applies to:** evidence display and guardrail rationale
- **Evidence claims:** `road-half-marathon.volume-and-long-run-are-associative`
- **Rationale:** Values reproduce the direct observational study and are not eligibility thresholds or prescriptions.
- **Exact value:**

```json
{
  "causal_dose_or_safety_established": false,
  "longest_run_category_associated_with_faster_time_km_more_than": 21,
  "longest_run_finish_time_coefficient_minutes": -3.87,
  "observational_only": true,
  "study_population": "adult_recreational_half_marathon_runners",
  "weekly_distance_category_associated_with_faster_time_km_more_than": 32,
  "weekly_distance_finish_time_coefficient_minutes": -4.19
}
```

#### `road_half_marathon_history_anchored_load_and_long_run` — guardrail

- **Applies to:** weekly exposure and longest-run boundary
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `road-half-marathon.volume-and-long-run-are-associative`, `road-half-marathon.exact-long-run-dose-unproven`
- **Rationale:** The direct evidence is associative. V1 must not convert population bins into requirements. Proposed self-history caps are deliberately surfaced for review rather than presented as proven optimal progression.
- **Exact value:**

```json
{
  "acwr_prescription_zone_used": false,
  "athlete_availability_and_single_session_limits_are_hard_caps": true,
  "automatic_long_run_progression": false,
  "exact_long_run_distance_or_duration": "not_accepted",
  "exact_long_run_share_of_weekly_volume": "not_accepted",
  "exact_weekly_progression": "not_accepted",
  "mandatory_long_run": false,
  "observed_32_km_week_or_21_km_long_run_used_as_minimum": false,
  "planned_longest_run_may_not_exceed_recent_completed_maximum": "proposed_guardrail_for_review",
  "planned_weekly_exposure_may_not_exceed_recent_completed_maximum": "proposed_guardrail_for_review",
  "target_gap_may_raise_load": false,
  "ten_percent_rule_used": false
}
```

#### `road_half_marathon_intensity_structure` — guardrail

- **Applies to:** session structure and intensity analysis
- **Evidence claims:** `road-half-marathon.intensity-distribution-no-universal-winner`, `road-half-marathon.recovery-spacing-unresolved`
- **Rationale:** Evidence supports mostly-low organization and some quality work without one universal distribution, quality count, or template. Nonconsecutive placement is a proposed conservative guardrail requiring explicit review.
- **Exact value:**

```json
{
  "activity_average_power_allowed": false,
  "allowed_session_categories": [
    "easy",
    "longest_easy",
    "controlled_threshold",
    "half_marathon_specific_or_race_pace",
    "interval",
    "confirmed_event"
  ],
  "consecutive_quality_running_days_allowed": "proposed_false_for_review",
  "exact_low_intensity_fraction": "not_accepted",
  "exact_session_mix": "not_accepted",
  "exact_step_templates": "not_accepted",
  "generic_percent_of_threshold_or_critical_power_targets": false,
  "intensity_source_priority": [
    "activity_splits",
    "activity_samples"
  ],
  "maximum_quality_sessions_per_7_day_unit": "not_accepted",
  "mostly_low_intensity_structure_required": true
}
```

#### `road_half_marathon_recovery_boundary` — guardrail

- **Applies to:** recovery and quality spacing
- **Evidence claims:** `road-half-marathon.recovery-spacing-unresolved`, `eligibility.current-symptoms-support-stop-not-clearance`
- **Rationale:** Recovery evidence varies by measure and post-race behavior. The policy rejects one exact spacing law and uses reassessment rather than automatically scheduling recovery intensity or missed-session makeup.
- **Exact value:**

```json
{
  "completed_half_marathon_requires_pattern_and_recovery_reassessment": true,
  "event_or_benchmark_counts_as_quality_and_load": true,
  "exact_hours_between_quality_sessions": "not_accepted",
  "high_intensity_recovery_run_automatically_scheduled": false,
  "missed_quality_makeup_allowed": false,
  "symptoms_override_recovery_schedule": true,
  "universal_one_to_three_day_recovery_rule": false
}
```

#### `road_half_marathon_published_taper_findings` — published

- **Applies to:** taper evidence
- **Evidence claims:** `road-half-marathon.taper-is-indirectly-supported`
- **Rationale:** These values reproduce the reviewed meta-analysis and remain explicitly indirect to adult road half-marathon planning.
- **Exact value:**

```json
{
  "direct_adult_road_half_marathon_validation": false,
  "evidence_population": "mixed_endurance_athletes",
  "maintain_frequency": true,
  "maintain_intensity": true,
  "strongest_duration_subgroup_days": {
    "maximum": 14,
    "minimum": 8
  },
  "strongest_volume_reduction_percent": {
    "maximum": 60,
    "minimum": 41
  }
}
```

#### `road_half_marathon_selected_taper_guardrail` — guardrail

- **Applies to:** event taper selection
- **Evidence claims:** `road-half-marathon.taper-is-indirectly-supported`
- **Rationale:** The evidence range is useful but does not select one half-marathon template. The exact product guardrail is intentionally left for human review.
- **Exact value:**

```json
{
  "exact_frequency_rule": "not_accepted",
  "exact_intensity_exposure": "not_accepted",
  "exact_taper_window_days": "not_accepted",
  "exact_volume_reduction_percent": "not_accepted",
  "no_extra_sharpening_or_makeup": true,
  "personal_performance_gain_claim": "prohibited",
  "pre_event_training_minutes_accounting": "not_accepted",
  "required_before_taper_activation": true,
  "target_event_elapsed_time_included_in_training_minutes": "not_accepted"
}
```

#### `road_half_marathon_published_fueling_findings` — published

- **Applies to:** fueling evidence display only
- **Evidence claims:** `road-half-marathon.fueling-and-gut-practice-supported`
- **Rationale:** Values reproduce broader-endurance source findings for evidence display. They are not product duration bands, intake minima or maxima, or an automatic half-marathon fueling prescription.
- **Exact value:**

```json
{
  "direct_half_marathon_dose_validation": false,
  "gut_training": {
    "carbohydrate_malabsorption_reduction_reported_percent": {
      "high": 54,
      "low": 45
    },
    "gastrointestinal_discomfort_reduction_reported_percent": 47
  },
  "source_guidance": {
    "around_one_hour": {
      "small_amount_or_carbohydrate_mouth_rinse_supported": true
    },
    "glycogen_loading": {
      "source_boundary_minutes": 90,
      "source_statement": "not_recommended_for_events_shorter_than_boundary"
    },
    "longer_endurance_exercise": {
      "reported_carbohydrate_grams_per_hour": {
        "high": 60,
        "low": 30
      }
    }
  }
}
```

#### `road_half_marathon_fueling_practice_policy` — guardrail

- **Applies to:** fueling-practice context and user communication
- **Evidence claims:** `road-half-marathon.fueling-and-gut-practice-supported`
- **Rationale:** The product must not turn general sports-nutrition ranges into a hidden individualized prescription. Product duration branches, intake ranges/caps, loading thresholds, and exact prompts remain review decisions.
- **Exact value:**

```json
{
  "athlete_may_decline_optional_profile_or_tolerance_detail": true,
  "automatic_carbohydrate_loading_from_distance_label": "prohibited",
  "exact_duration_bands_and_prompts": "not_accepted",
  "fueling_prompt_is_medical_or_dietetic_treatment": false,
  "missing_optional_detail_effect": "generic_uncertainty_only",
  "new_race_day_strategy_without_practice": "prohibited",
  "product_carbohydrate_grams_per_hour_range_or_cap": "not_accepted",
  "product_during_exercise_duration_bands": "not_accepted",
  "product_glycogen_loading_duration_threshold": "not_accepted",
  "published_findings_are_runtime_routing_rules": false,
  "required_inputs": [
    "expected_event_duration_band",
    "prior_during_run_carbohydrate_practice",
    "prior_gastrointestinal_tolerance_or_issue",
    "athlete_preference"
  ]
}
```

#### `road_half_marathon_protocol_comparability_and_outcomes` — guardrail

- **Applies to:** post-plan evaluation
- **Evidence claims:** `road-half-marathon.direct-field-baseline-preferred-with-error`, `road-half-marathon.task-specific-capability-is-multifactor`, `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Same distance alone does not establish comparable conditions or causal plan benefit. Evaluation separates observed outcome, execution, context, and unresolved causal hypotheses.
- **Exact value:**

```json
{
  "causal_plan_effect_claim": "prohibited",
  "direct_before_after_claim_requires": [
    "comparable_half_marathon_distance_and_result_type",
    "known_route_or_event",
    "known_surface",
    "known_assistance_status",
    "known_environment_context_when_available",
    "no_material_protocol_change"
  ],
  "missing_comparability_outcome": "descriptive_context_only",
  "personal_responder_classification": "prohibited",
  "supporting_post_plan_inputs": [
    "split_level_pacing_and_pace_decline",
    "adherence_and_edit_burden",
    "fueling_practice_and_gastrointestinal_response",
    "recovery_response",
    "weekly_volume_frequency_and_longest_run_change"
  ]
}
```

#### `road_half_marathon_typed_outcomes` — guardrail

- **Applies to:** future API and client outcome contract
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `eligibility.current-symptoms-support-stop-not-clearance`, `road-half-marathon.direct-field-baseline-preferred-with-error`
- **Rationale:** Typed outcomes preserve goal intent while the draft and unresolved implementation guardrails keep every plan path inactive.
- **Exact value:**

```json
{
  "current_runtime_state": "policy_inactive",
  "outcomes": {
    "adult_scope_unconfirmed": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "contradictory_input": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "eligible_future_policy_pattern": {
      "goal_remains_recorded": true,
      "plan_returned_while_inactive": false,
      "review_packet_available": true
    },
    "insufficient_direct_half_marathon_baseline": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "insufficient_history_anchor": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "intent_requires_separate_policy": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "limited_guidance_event_conflict": {
      "goal_remains_recorded": true,
      "limited_guidance_returned": true,
      "plan_returned": false
    },
    "safety_stop": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "unresolved_event_context": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "unresolved_policy_guardrail": {
      "goal_remains_recorded": true,
      "plan_returned": false
    }
  },
  "unknown_values_are_not_false_or_zero": true,
  "unsupported_distance_fallback": "none"
}
```

#### `road_half_marathon_suggestion_only_state_transition` — guardrail

- **Applies to:** proposal and adoption state
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Deterministic validation, role-scoped human approval, and athlete consent remain separate authority boundaries.
- **Exact value:**

```json
{
  "AI_may_not": [
    "broaden_eligibility",
    "invent_capability_history_event_profile_or_safety_context",
    "choose_unaccepted_guardrails",
    "override_deterministic_validation",
    "create_human_approval_artifacts",
    "activate_adopt_deliver_or_publish"
  ],
  "generated_state_after_future_activation": "proposed",
  "generator_may_not": [
    "adopt_or_deliver_without_consent",
    "overwrite_adopted_future_days",
    "auto_schedule_a_half_marathon_benchmark",
    "auto_change_event_priority",
    "schedule_missed_workout_makeup",
    "infer_missed_workout_reason",
    "invent_fueling_tolerance"
  ],
  "user_may": [
    "review",
    "edit",
    "reject",
    "explicitly_adopt"
  ]
}
```

#### `road_half_marathon_privacy_and_audit` — guardrail

- **Applies to:** audit and privacy
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Future generation must remain reproducible without inferring or exposing sensitive explanations.
- **Exact value:**

```json
{
  "minimum_necessary_inputs_only": true,
  "no_inference_of": [
    "diagnosis",
    "injury_cause",
    "pregnancy_status",
    "mental_state",
    "missed_training_reason",
    "gastrointestinal_diagnosis"
  ],
  "no_publication_of": [
    "raw_health_data",
    "private_activity_data",
    "inferred_sensitive_context"
  ],
  "replay_record_must_include": [
    "shared_and_distance_policy_versions",
    "decision_and_contract_digests",
    "goal_record_state",
    "dynamic_pattern_snapshot",
    "confirmed_event_context",
    "profile_and_fueling_field_provenance",
    "baseline_source",
    "history_cutoff_and_inputs",
    "unresolved_guardrail_versions",
    "typed_outcome",
    "proposal_hash"
  ]
}
```

#### `road_half_marathon_validation_and_pilot_thresholds` — guardrail

- **Applies to:** offline validation and future opt-in pilot
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-half-marathon.direct-field-baseline-preferred-with-error`, `road-half-marathon.subgroup-dose-rules-unproven`
- **Rationale:** Zero deterministic invariant tolerance is an engineering requirement. Statistical go/no-go and safety pause thresholds need a separate reviewed pilot protocol rather than being copied from another distance.
- **Exact value:**

```json
{
  "deterministic_invariant_breach_tolerance": 0,
  "deterministic_replay_mismatch_tolerance": 0,
  "dry_run_metrics_required": [
    "eligibility_and_no_plan_rates",
    "each_guardrail_exclusion_rate",
    "subgroup_missingness_and_exclusion_gaps",
    "proposal_edit_and_rejection_burden",
    "fueling_prompt_acceptance_and_tolerance_missingness",
    "event_conflicts_and_recovery_exits"
  ],
  "exact_dry_run_go_no_go_thresholds": "not_accepted",
  "exact_prospective_pause_thresholds": "not_accepted",
  "prospective_pilot_metrics_required": [
    "adoption_and_edit_distance",
    "adherence_burden",
    "quality_and_event_stacking",
    "symptom_stops_and_adverse_events",
    "fueling_tolerance",
    "comparable_half_marathon_outcomes",
    "withdrawal"
  ]
}
```

#### `road_half_marathon_user_facing_uncertainty` — guardrail

- **Applies to:** future English and Simplified Chinese review and product copy
- **Evidence claims:** `road-half-marathon.volume-and-long-run-are-associative`, `road-half-marathon.taper-is-indirectly-supported`, `road-half-marathon.fueling-and-gut-practice-supported`, `road-half-marathon.subgroup-dose-rules-unproven`
- **Rationale:** The review surface must distinguish direct findings, broader-endurance transfer, unresolved guardrails, and product choices from certainty.
- **Exact value:**

```json
{
  "always_show": [
    "current_policy_is_draft_and_inactive",
    "proposal_not_guarantee",
    "direct_associative_and_indirect_evidence_boundaries",
    "exact_unaccepted_guardrails",
    "baseline_source_and_prediction_error",
    "current_dynamic_pattern",
    "confirmed_event_context",
    "fueling_duration_and_tolerance_assumptions",
    "missing_profile_fields_and_specific_effects",
    "risks_unknowns_and_alternatives",
    "typed_no_plan_reason"
  ],
  "forbidden_copy": [
    "scientifically_optimal_half_marathon_plan",
    "safe_because_within_recent_history",
    "guaranteed_goal_time",
    "personal_success_or_injury_probability",
    "medically_cleared",
    "required_32_km_week",
    "required_overdistance_long_run",
    "automatic_carb_loading"
  ]
}
```

#### `road_half_marathon_open_decisions` — guardrail

- **Applies to:** human decision review
- **Evidence claims:** `road-half-marathon.volume-and-long-run-are-associative`, `road-half-marathon.exact-long-run-dose-unproven`, `road-half-marathon.intensity-distribution-no-universal-winner`, `road-half-marathon.recovery-spacing-unresolved`, `road-half-marathon.taper-is-indirectly-supported`, `road-half-marathon.fueling-and-gut-practice-supported`
- **Rationale:** The review packet must make every unresolved behavior-driving choice explicit. None may be inferred by implementation or hidden in prose.
- **Exact value:**

```json
{
  "aggressive_short_horizon_variant": "not_accepted",
  "baseline_freshness_days": "not_accepted",
  "direct_baseline_qualification_algorithm": "not_accepted",
  "exact_workout_templates": "not_accepted",
  "execution_window_and_reassessment_cadence": "not_accepted",
  "frequency_envelope": "not_accepted",
  "fueling_duration_bands_and_prompts": "not_accepted",
  "fueling_intake_range_or_cap": "not_accepted",
  "fueling_loading_duration_threshold": "not_accepted",
  "long_run_share_distance_and_ceiling": "not_accepted",
  "low_intensity_floor": "not_accepted",
  "minimum_history_counts": "not_accepted",
  "pilot_go_no_go_thresholds": "not_accepted",
  "quality_session_ceiling_and_spacing": "not_accepted",
  "selected_taper_guardrail": "not_accepted",
  "taper_training_minutes_accounting": "not_accepted",
  "weekly_progression_rule": "not_accepted"
}
```

### Rejected alternatives

#### Copy the accepted 5 km or 10 km policy and replace the distance label

Half-marathon durability, longest-run exposure, target duration, fueling, recovery, and event demands differ materially. Existing distance guardrails are not universal evidence and cannot be silently inherited.

#### Require more than 32 km per week or a longest run above 21 km

Those thresholds describe observational categories associated with performance in one cohort. They do not establish causal eligibility, safety, or an optimal prescription.

#### Use a predicted half-marathon time as direct current capability

Field and laboratory models retain meaningful individual error and are predominantly male. They may support context but cannot manufacture a direct same-task result or personal probability.

#### Schedule a maximal half-marathon benchmark when direct evidence is missing

A maximal half-marathon is burdensome and the review did not validate an automatic benchmark workflow. Missing direct capability remains a typed readiness limitation until a separate policy is accepted.

#### Select a universal polarized, pyramidal, threshold, or race-pace distribution

Mixed-distance evidence supports multiple organizations and no universal winner. Exact distribution and session templates remain product choices.

#### Use an aggressive catch-up block when the target is near

No reviewed evidence validates target-gap dose escalation, compressed progression, automatic makeup, or a universal short-horizon salvage plan.

#### Apply one fueling prescription to every half-marathon

Expected duration and gastrointestinal tolerance vary substantially. Distance alone does not determine carbohydrate-loading or intake needs.

#### Let AI fill missing policy values or infer athlete context

AI cannot repair missing evidence, verify events or profile fields, broaden eligibility, create approvals, or provide deterministic replay.

### Applicability

- Adult scope confirmed by the accepted shared router
- Current direct outdoor road half-marathon capability
- Stable recent history and within-recent load pattern
- Performance intent with optional target time and target date
- Confirmed-none, single-target, or conflict-resolved race-dense event context
- Suggestion-only future behavior after all open guardrails and implementation reviews are accepted
- Evidence cohorts include recreational and amateur runners without assigning a permanent identity

### User-facing claim limits

- This draft is an evidence and product-decision boundary, not a usable half-marathon generator, optimal plan, safety guarantee, medical advice, or goal-time guarantee.
- Observed 32 km weekly volume and over-21 km longest-run categories must not be presented as requirements, safe thresholds, or optimal doses.
- Taper and fueling values must be labelled as broader-endurance evidence with half-marathon-specific uncertainty.
- Target time and indirect predictions may describe uncertainty but may not create a personal success probability or justify higher dose.
- Missing optional age, sex, or fueling-tolerance detail affects only the dependent communication or feature and never silently defaults to male.
- No 5 km or 10 km count, percentage, window, template, or progression rule is accepted for half-marathon use through this record.

### Safety implications

- Current concerning symptoms, illness, injury, rehabilitation, return-to-sport, medical-clearance, pregnancy-specific, or contradictory safety context stops the vigorous-plan path without diagnosis or treatment.
- Completing a half-marathon, staying within recent history, or lacking symptoms does not establish medical clearance or guarantee freedom from harm.
- No maximal half-marathon benchmark is automatically proposed when direct capability is missing or stale.
- Confirmed races and maximal efforts count as quality and load; unresolved dense-event conflicts prevent a full proposal.
- No target-gap escalation, catch-up, ten-percent rule, ACWR prescription zone, high-intensity recovery prescription, or activity-average-power intensity analysis is allowed.

### Privacy implications

- Use only the authenticated athlete's minimum necessary goal, activity, event, profile, constraints, fueling-practice, and optional symptom context.
- Provider fields remain source-labelled candidates until their purpose is disclosed and the athlete confirms or corrects them.
- Do not infer or publish diagnosis, injury cause, pregnancy status, gastrointestinal diagnosis, mental state, missed-training reason, or external life circumstance.

### Validation plan

- Registry validation must prove exact Evidence Review and claim links, globally unique IDs, draft lifecycle validity, parameter classifications, exact citation verification notes, and inactive artifact policy.
- Artifact validation must prove that the generated Evidence Review and SDR packets carry current digests and that the exact machine contract embedded in the SDR packet matches the generated JSON contract.
- Tests must lock the exact supported tuple, current-capability and stable- history patterns, official distance, direct-baseline hierarchy, event accounting, activity-split/sample boundary, and typed no-plan states.
- Tests must prove every behavior-driving open choice remains `not_accepted`, no 5 km or 10 km numeric rule is inherited, and runtime state remains inactive without evidence, decision, and implementation approval artifacts.
- Before activation, separately reviewed decisions must select direct baseline qualification and freshness, history qualification, load and long-run caps, intensity and quality structure, taper and event-minute accounting, fueling duration/intake rules and prompts, execution windows, exact templates, and pilot thresholds.
- Offline dry runs must report exclusion, missingness, event conflict, edit/rejection burden, subgroup gaps, fueling-context availability, and deterministic replay without publishing private athlete data.
- A prospective opt-in pilot must predeclare adoption, adherence, edit distance, quality stacking, symptom and adverse-event exits, fueling tolerance, comparable outcomes, withdrawal, and human go/no-go thresholds.

### Falsification conditions

- Reject the policy if any implementation emits a plan while the contract is draft or inactive, consumes an unapproved parameter, or omits a code-consumed field from the human review packet.
- Reject routing if a shorter-distance conversion, prediction, threshold, activity-average power, or passive segment is treated as direct current half-marathon capability.
- Reject schedule mapping if observational 32 km or 21 km categories become universal eligibility or dose requirements.
- Reject target routing if a short horizon invalidates the goal, increases dose, schedules catch-up, or produces a personal probability.
- Reject fueling behavior if distance alone triggers carbohydrate loading or a new race-day intake strategy without prior practice and consent.
- Pause future activation after any deterministic invariant or replay breach, unconfirmed event use, quality/load event omission, unsupported population, hidden demographic default, symptom-stop override, or approval-digest mismatch.
- Revise or reject candidate guardrails when predeclared dry-run or pilot thresholds are breached; those thresholds are themselves not accepted by this draft.

### Decision notes

- This artifact-mode decision proposal addresses issue #688 and remains draft and inactive.
- Human review should use the generated packet rather than raw YAML. The packet includes the exact machine contract and digest-bound approval templates.
- The core proposed scope is history-rich, currently capable adult outdoor road half-marathon performance planning; completion and sparse-history policies remain separate.
- Direct evidence supports task-specific capability, observational volume and longest-run associations, and error-aware target communication. Taper, intensity distribution, recovery, and fueling transfer from broader endurance evidence with explicit limits.
- Every unresolved schedule, dose, taper, fueling, and pilot choice is encoded as `not_accepted`; implementation may not infer a value.
- Impact map: draft Evidence Review -> generated evidence packet -> draft SDR -> generated decision packet and inactive contract -> role-scoped approvals -> future pure routing and policy implementation -> API -> web and miniapp parity -> ScienceNote and localization -> offline validation -> opt-in pilot.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "road-half-marathon-plan-generation-policy-v1",
    "shared dynamic training-pattern and confirmed event snapshots"
  ],
  "contract_digest": "sha256:a1d99a0b562d2b5a04ae5057793dd915e486c7dc5f3667e26aff197210942afe",
  "decision_id": "sdr-road-half-marathon-plan-generation-policy-v1",
  "decision_status": "draft",
  "decision_version": 1,
  "evidence_claim_ids": [
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.fixed-progression-and-acwr-not-safety-laws",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.current-symptoms-support-stop-not-clearance",
    "eligibility.evidence-quality-no-personal-probability",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "road-half-marathon.task-specific-capability-is-multifactor",
    "road-half-marathon.volume-and-long-run-are-associative",
    "road-half-marathon.taper-is-indirectly-supported",
    "road-half-marathon.fueling-and-gut-practice-supported",
    "road-half-marathon.direct-field-baseline-preferred-with-error",
    "road-half-marathon.exact-long-run-dose-unproven",
    "road-half-marathon.intensity-distribution-no-universal-winner",
    "road-half-marathon.recovery-spacing-unresolved",
    "road-half-marathon.subgroup-dose-rules-unproven"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-road-half-marathon-plan-generation-policy-v1"
  ],
  "linked_evidence_digests": {
    "evidence-plan-generation-eligibility-safety-v1": "sha256:e884907d33783edc6cdb16fd5504f7f10b6d68f968bfe7cf87e3f024b5bda773",
    "evidence-road-half-marathon-plan-generation-policy-v1": "sha256:22a2df413eb204395db0444fe1b97a7b7bf42e58010ee614dea30945b9eb14e9"
  },
  "model_version": "road-half-marathon-plan-generation-policy-v1",
  "parameters": {
    "road_half_marathon_activation_and_dependency": {
      "applies_to": "policy lifecycle and capability registry",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "active_behavior": false,
        "capability_registry_entry_default_enabled": false,
        "decision_approval_artifact_required": true,
        "distance_policy_required_status_before_activation": "accepted",
        "evidence_review_required_status_before_activation": "accepted",
        "generator_api_web_miniapp_plugin_and_mcp_activation_in_this_record": false,
        "implementation_approval_artifact_required": true,
        "shared_policy_dependency": {
          "required_status_before_activation": "accepted",
          "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
        }
      }
    },
    "road_half_marathon_baseline_freshness": {
      "applies_to": "capability freshness",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "value": {
        "exact_current_through_completed_days": "not_accepted",
        "missing_or_stale_outcome": "readiness_only",
        "no_biological_expiry_claim": true,
        "required_before_activation": true,
        "stale_boundary": "not_accepted"
      }
    },
    "road_half_marathon_direct_baseline_hierarchy": {
      "applies_to": "baseline qualification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-half-marathon.task-specific-capability-is-multifactor",
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "value": {
        "accepted_evidence_order": [
          "organized_outdoor_road_half_marathon_with_elapsed_time",
          "athlete_confirmed_standardized_outdoor_road_half_marathon_time_trial"
        ],
        "allowed_assistance_statuses": "not_accepted",
        "allowed_surface_values": "not_accepted",
        "automatic_maximal_baseline_test": "prohibited",
        "baseline_qualification_algorithm": "not_accepted",
        "direct_current_capability_required": true,
        "distance_match_tolerance_m": "not_accepted",
        "excluded_as_direct": [
          "shorter_race_conversion",
          "marathon_or_ultra_split",
          "passive_fastest_half_marathon_segment",
          "personal_best_without_source_activity",
          "activity_average_power",
          "vendor_readiness_or_race_score"
        ],
        "missing_direct_result_outcome": "insufficient_direct_half_marathon_baseline",
        "required_metadata": [
          "completed_at",
          "elapsed_time_seconds",
          "measured_distance_m",
          "route_or_event_identifier",
          "surface",
          "assistance_status",
          "source_provider",
          "race_or_intentional_time_trial_flag"
        ],
        "standardized_time_trial_protocol": "not_accepted",
        "supporting_only": [
          "cooper_test",
          "current_vo2max_or_vvo2max",
          "current_threshold_or_critical_speed",
          "weekly_training_distance",
          "recent_longest_run",
          "race_forecast_with_error",
          "split_or_sample_pacing_distribution"
        ]
      }
    },
    "road_half_marathon_event_context": {
      "applies_to": "event calendar and schedule conflicts",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.recovery-spacing-unresolved",
        "road-half-marathon.taper-is-indirectly-supported",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "confirmed_primary_event_may_trigger_taper_only_after_taper_guardrail_acceptance": true,
        "every_race_or_maximal_effort": {
          "counts_as_quality_session": true,
          "counts_as_training_load": true,
          "requires_recovery_reassessment": true
        },
        "imported_event_must_be_athlete_confirmed": true,
        "no_event_performance_goal": {
          "automatic_half_marathon_benchmark": "prohibited",
          "goal_remains_recorded": true,
          "rolling_policy_before_activation": "readiness_only"
        },
        "shared_event_states_consumed": [
          "confirmed_none",
          "single_target",
          "race_dense"
        ],
        "unresolved_race_dense_outcome": "limited_guidance_event_conflict"
      }
    },
    "road_half_marathon_fueling_practice_policy": {
      "applies_to": "fueling-practice context and user communication",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.fueling-and-gut-practice-supported"
      ],
      "value": {
        "athlete_may_decline_optional_profile_or_tolerance_detail": true,
        "automatic_carbohydrate_loading_from_distance_label": "prohibited",
        "exact_duration_bands_and_prompts": "not_accepted",
        "fueling_prompt_is_medical_or_dietetic_treatment": false,
        "missing_optional_detail_effect": "generic_uncertainty_only",
        "new_race_day_strategy_without_practice": "prohibited",
        "product_carbohydrate_grams_per_hour_range_or_cap": "not_accepted",
        "product_during_exercise_duration_bands": "not_accepted",
        "product_glycogen_loading_duration_threshold": "not_accepted",
        "published_findings_are_runtime_routing_rules": false,
        "required_inputs": [
          "expected_event_duration_band",
          "prior_during_run_carbohydrate_practice",
          "prior_gastrointestinal_tolerance_or_issue",
          "athlete_preference"
        ]
      }
    },
    "road_half_marathon_goal_tuple": {
      "applies_to": "goal normalization and distance-policy selection",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-half-marathon.task-specific-capability-is-multifactor"
      ],
      "value": {
        "goal_intent": "performance",
        "goal_kind": "distance_half_marathon",
        "no_event_goal_may_remain_recorded": true,
        "primary_outcome": "elapsed_time",
        "separate_policy_variants": [
          "first_half_marathon_completion",
          "sparse_history_half_marathon",
          "treadmill_half_marathon",
          "trail_half_marathon",
          "multisport_run_leg",
          "marathon_or_ultra",
          "medically_directed_rehabilitation",
          "pregnancy_specific_planning"
        ],
        "sport": "running",
        "surface": "outdoor_road",
        "target_date_optional": true,
        "target_time_optional": true
      }
    },
    "road_half_marathon_history_anchored_load_and_long_run": {
      "applies_to": "weekly exposure and longest-run boundary",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.exact-long-run-dose-unproven"
      ],
      "value": {
        "acwr_prescription_zone_used": false,
        "athlete_availability_and_single_session_limits_are_hard_caps": true,
        "automatic_long_run_progression": false,
        "exact_long_run_distance_or_duration": "not_accepted",
        "exact_long_run_share_of_weekly_volume": "not_accepted",
        "exact_weekly_progression": "not_accepted",
        "mandatory_long_run": false,
        "observed_32_km_week_or_21_km_long_run_used_as_minimum": false,
        "planned_longest_run_may_not_exceed_recent_completed_maximum": "proposed_guardrail_for_review",
        "planned_weekly_exposure_may_not_exceed_recent_completed_maximum": "proposed_guardrail_for_review",
        "target_gap_may_raise_load": false,
        "ten_percent_rule_used": false
      }
    },
    "road_half_marathon_intensity_structure": {
      "applies_to": "session structure and intensity analysis",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.intensity-distribution-no-universal-winner",
        "road-half-marathon.recovery-spacing-unresolved"
      ],
      "value": {
        "activity_average_power_allowed": false,
        "allowed_session_categories": [
          "easy",
          "longest_easy",
          "controlled_threshold",
          "half_marathon_specific_or_race_pace",
          "interval",
          "confirmed_event"
        ],
        "consecutive_quality_running_days_allowed": "proposed_false_for_review",
        "exact_low_intensity_fraction": "not_accepted",
        "exact_session_mix": "not_accepted",
        "exact_step_templates": "not_accepted",
        "generic_percent_of_threshold_or_critical_power_targets": false,
        "intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "maximum_quality_sessions_per_7_day_unit": "not_accepted",
        "mostly_low_intensity_structure_required": true
      }
    },
    "road_half_marathon_open_decisions": {
      "applies_to": "human decision review",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.exact-long-run-dose-unproven",
        "road-half-marathon.intensity-distribution-no-universal-winner",
        "road-half-marathon.recovery-spacing-unresolved",
        "road-half-marathon.taper-is-indirectly-supported",
        "road-half-marathon.fueling-and-gut-practice-supported"
      ],
      "value": {
        "aggressive_short_horizon_variant": "not_accepted",
        "baseline_freshness_days": "not_accepted",
        "direct_baseline_qualification_algorithm": "not_accepted",
        "exact_workout_templates": "not_accepted",
        "execution_window_and_reassessment_cadence": "not_accepted",
        "frequency_envelope": "not_accepted",
        "fueling_duration_bands_and_prompts": "not_accepted",
        "fueling_intake_range_or_cap": "not_accepted",
        "fueling_loading_duration_threshold": "not_accepted",
        "long_run_share_distance_and_ceiling": "not_accepted",
        "low_intensity_floor": "not_accepted",
        "minimum_history_counts": "not_accepted",
        "pilot_go_no_go_thresholds": "not_accepted",
        "quality_session_ceiling_and_spacing": "not_accepted",
        "selected_taper_guardrail": "not_accepted",
        "taper_training_minutes_accounting": "not_accepted",
        "weekly_progression_rule": "not_accepted"
      }
    },
    "road_half_marathon_planning_and_reassessment": {
      "applies_to": "proposal horizon and reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-half-marathon.volume-and-long-run-are-associative"
      ],
      "value": {
        "automatic_progression_between_reassessments": false,
        "each_reassessment_requires": [
          "fresh_shared_eligibility",
          "updated_history_and_longest_run",
          "updated_event_context",
          "updated_dynamic_pattern_snapshot",
          "updated_fueling_practice_context",
          "explicit_review_before_replacing_adopted_future_days"
        ],
        "exact_calendar_reassessment_cadence": "not_accepted",
        "exact_committed_execution_window_days": "not_accepted",
        "fixed_full_block_days": "none_defined",
        "fixed_horizon_eligibility_gate": false,
        "reassessment_triggers": [
          "new_or_changed_confirmed_event",
          "material_training_pattern_change",
          "new_qualified_half_marathon_result",
          "changed_availability_or_constraint",
          "changed_fueling_tolerance_or_practice",
          "completed_target_event",
          "athlete_requested_review"
        ],
        "target_date_required": false
      }
    },
    "road_half_marathon_privacy_and_audit": {
      "applies_to": "audit and privacy",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "minimum_necessary_inputs_only": true,
        "no_inference_of": [
          "diagnosis",
          "injury_cause",
          "pregnancy_status",
          "mental_state",
          "missed_training_reason",
          "gastrointestinal_diagnosis"
        ],
        "no_publication_of": [
          "raw_health_data",
          "private_activity_data",
          "inferred_sensitive_context"
        ],
        "replay_record_must_include": [
          "shared_and_distance_policy_versions",
          "decision_and_contract_digests",
          "goal_record_state",
          "dynamic_pattern_snapshot",
          "confirmed_event_context",
          "profile_and_fueling_field_provenance",
          "baseline_source",
          "history_cutoff_and_inputs",
          "unresolved_guardrail_versions",
          "typed_outcome",
          "proposal_hash"
        ]
      }
    },
    "road_half_marathon_protocol_comparability_and_outcomes": {
      "applies_to": "post-plan evaluation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.direct-field-baseline-preferred-with-error",
        "road-half-marathon.task-specific-capability-is-multifactor",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "causal_plan_effect_claim": "prohibited",
        "direct_before_after_claim_requires": [
          "comparable_half_marathon_distance_and_result_type",
          "known_route_or_event",
          "known_surface",
          "known_assistance_status",
          "known_environment_context_when_available",
          "no_material_protocol_change"
        ],
        "missing_comparability_outcome": "descriptive_context_only",
        "personal_responder_classification": "prohibited",
        "supporting_post_plan_inputs": [
          "split_level_pacing_and_pace_decline",
          "adherence_and_edit_burden",
          "fueling_practice_and_gastrointestinal_response",
          "recovery_response",
          "weekly_volume_frequency_and_longest_run_change"
        ]
      }
    },
    "road_half_marathon_published_fueling_findings": {
      "applies_to": "fueling evidence display only",
      "classification": "published",
      "evidence_claim_ids": [
        "road-half-marathon.fueling-and-gut-practice-supported"
      ],
      "value": {
        "direct_half_marathon_dose_validation": false,
        "gut_training": {
          "carbohydrate_malabsorption_reduction_reported_percent": {
            "high": 54,
            "low": 45
          },
          "gastrointestinal_discomfort_reduction_reported_percent": 47
        },
        "source_guidance": {
          "around_one_hour": {
            "small_amount_or_carbohydrate_mouth_rinse_supported": true
          },
          "glycogen_loading": {
            "source_boundary_minutes": 90,
            "source_statement": "not_recommended_for_events_shorter_than_boundary"
          },
          "longer_endurance_exercise": {
            "reported_carbohydrate_grams_per_hour": {
              "high": 60,
              "low": 30
            }
          }
        }
      }
    },
    "road_half_marathon_published_taper_findings": {
      "applies_to": "taper evidence",
      "classification": "published",
      "evidence_claim_ids": [
        "road-half-marathon.taper-is-indirectly-supported"
      ],
      "value": {
        "direct_adult_road_half_marathon_validation": false,
        "evidence_population": "mixed_endurance_athletes",
        "maintain_frequency": true,
        "maintain_intensity": true,
        "strongest_duration_subgroup_days": {
          "maximum": 14,
          "minimum": 8
        },
        "strongest_volume_reduction_percent": {
          "maximum": 60,
          "minimum": 41
        }
      }
    },
    "road_half_marathon_published_volume_and_long_run_findings": {
      "applies_to": "evidence display and guardrail rationale",
      "classification": "published",
      "evidence_claim_ids": [
        "road-half-marathon.volume-and-long-run-are-associative"
      ],
      "value": {
        "causal_dose_or_safety_established": false,
        "longest_run_category_associated_with_faster_time_km_more_than": 21,
        "longest_run_finish_time_coefficient_minutes": -3.87,
        "observational_only": true,
        "study_population": "adult_recreational_half_marathon_runners",
        "weekly_distance_category_associated_with_faster_time_km_more_than": 32,
        "weekly_distance_finish_time_coefficient_minutes": -4.19
      }
    },
    "road_half_marathon_recent_history_inputs": {
      "applies_to": "history-rich qualification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.exact-long-run-dose-unproven"
      ],
      "value": {
        "disallowed_intensity_source": [
          "activity_avg_power"
        ],
        "exact_lookback_weeks": "not_accepted",
        "history_qualification_algorithm": "not_accepted",
        "intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "latest_run_freshness_days": "not_accepted",
        "minimum_runs_per_usable_week": "not_accepted",
        "minimum_usable_weeks": "not_accepted",
        "required_observations": [
          "completed_weekly_running_minutes_and_distance",
          "completed_running_days_per_week",
          "recent_longest_run_duration_and_distance",
          "quality_session_and_event_density",
          "recent_load_relative_to_self",
          "availability_and_single_session_constraints",
          "prior_half_marathon_count_when_known"
        ],
        "unresolved_history_outcome": "insufficient_history_anchor"
      }
    },
    "road_half_marathon_recovery_boundary": {
      "applies_to": "recovery and quality spacing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.recovery-spacing-unresolved",
        "eligibility.current-symptoms-support-stop-not-clearance"
      ],
      "value": {
        "completed_half_marathon_requires_pattern_and_recovery_reassessment": true,
        "event_or_benchmark_counts_as_quality_and_load": true,
        "exact_hours_between_quality_sessions": "not_accepted",
        "high_intensity_recovery_run_automatically_scheduled": false,
        "missed_quality_makeup_allowed": false,
        "symptoms_override_recovery_schedule": true,
        "universal_one_to_three_day_recovery_rule": false
      }
    },
    "road_half_marathon_selected_taper_guardrail": {
      "applies_to": "event taper selection",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.taper-is-indirectly-supported"
      ],
      "value": {
        "exact_frequency_rule": "not_accepted",
        "exact_intensity_exposure": "not_accepted",
        "exact_taper_window_days": "not_accepted",
        "exact_volume_reduction_percent": "not_accepted",
        "no_extra_sharpening_or_makeup": true,
        "personal_performance_gain_claim": "prohibited",
        "pre_event_training_minutes_accounting": "not_accepted",
        "required_before_taper_activation": true,
        "target_event_elapsed_time_included_in_training_minutes": "not_accepted"
      }
    },
    "road_half_marathon_suggestion_only_state_transition": {
      "applies_to": "proposal and adoption state",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "AI_may_not": [
          "broaden_eligibility",
          "invent_capability_history_event_profile_or_safety_context",
          "choose_unaccepted_guardrails",
          "override_deterministic_validation",
          "create_human_approval_artifacts",
          "activate_adopt_deliver_or_publish"
        ],
        "generated_state_after_future_activation": "proposed",
        "generator_may_not": [
          "adopt_or_deliver_without_consent",
          "overwrite_adopted_future_days",
          "auto_schedule_a_half_marathon_benchmark",
          "auto_change_event_priority",
          "schedule_missed_workout_makeup",
          "infer_missed_workout_reason",
          "invent_fueling_tolerance"
        ],
        "user_may": [
          "review",
          "edit",
          "reject",
          "explicitly_adopt"
        ]
      }
    },
    "road_half_marathon_supported_training_pattern": {
      "applies_to": "shared pattern routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "road-half-marathon.subgroup-dose-rules-unproven"
      ],
      "value": {
        "adult_scope": "confirmed",
        "capability_pattern": "currently_capable",
        "current_symptoms": "absent",
        "event_context": [
          "confirmed_none",
          "single_target",
          "race_dense"
        ],
        "evidence_directness": [
          "direct",
          "supporting"
        ],
        "explicit_exclusions": [
          "adult_scope_unconfirmed",
          "first_half_marathon_completion_requires_separate_policy",
          "sparse_interrupted_or_missing_history",
          "current_injury_illness_or_concerning_symptoms",
          "rehabilitation_return_to_sport_or_medical_clearance",
          "pregnancy_specific_prescription",
          "unresolved_material_event_context",
          "unsupported_surface_distance_or_intent"
        ],
        "history_pattern": "stable",
        "load_pattern": "within_recent",
        "permanent_runner_identity_used": false,
        "race_dense_requires_resolved_conflicts": true
      }
    },
    "road_half_marathon_target_and_short_horizon_routing": {
      "applies_to": "target communication and short-horizon routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "value": {
        "aggressive_or_catch_up_variant": "not_accepted",
        "near_event_supported_states": [
          "readiness_only",
          "maintain",
          "taper_after_taper_guardrail_acceptance",
          "limited_guidance"
        ],
        "personal_goal_achievement_probability": "disabled",
        "personal_injury_probability": "disabled",
        "short_horizon_invalidates_goal": false,
        "target_gap_dose_escalation": "prohibited",
        "target_time_may": [
          "label_goal",
          "compute_descriptive_gap_to_direct_baseline",
          "select_uncertainty_copy"
        ],
        "target_time_may_not": [
          "increase_weekly_volume",
          "increase_frequency",
          "lengthen_longest_run",
          "add_quality",
          "weaken_history_or_safety_rules"
        ]
      }
    },
    "road_half_marathon_typed_outcomes": {
      "applies_to": "future API and client outcome contract",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "value": {
        "current_runtime_state": "policy_inactive",
        "outcomes": {
          "adult_scope_unconfirmed": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "contradictory_input": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "eligible_future_policy_pattern": {
            "goal_remains_recorded": true,
            "plan_returned_while_inactive": false,
            "review_packet_available": true
          },
          "insufficient_direct_half_marathon_baseline": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "insufficient_history_anchor": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "intent_requires_separate_policy": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "limited_guidance_event_conflict": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false
          },
          "safety_stop": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "unresolved_event_context": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "unresolved_policy_guardrail": {
            "goal_remains_recorded": true,
            "plan_returned": false
          }
        },
        "unknown_values_are_not_false_or_zero": true,
        "unsupported_distance_fallback": "none"
      }
    },
    "road_half_marathon_user_facing_uncertainty": {
      "applies_to": "future English and Simplified Chinese review and product copy",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.taper-is-indirectly-supported",
        "road-half-marathon.fueling-and-gut-practice-supported",
        "road-half-marathon.subgroup-dose-rules-unproven"
      ],
      "value": {
        "always_show": [
          "current_policy_is_draft_and_inactive",
          "proposal_not_guarantee",
          "direct_associative_and_indirect_evidence_boundaries",
          "exact_unaccepted_guardrails",
          "baseline_source_and_prediction_error",
          "current_dynamic_pattern",
          "confirmed_event_context",
          "fueling_duration_and_tolerance_assumptions",
          "missing_profile_fields_and_specific_effects",
          "risks_unknowns_and_alternatives",
          "typed_no_plan_reason"
        ],
        "forbidden_copy": [
          "scientifically_optimal_half_marathon_plan",
          "safe_because_within_recent_history",
          "guaranteed_goal_time",
          "personal_success_or_injury_probability",
          "medically_cleared",
          "required_32_km_week",
          "required_overdistance_long_run",
          "automatic_carb_loading"
        ]
      }
    },
    "road_half_marathon_validation_and_pilot_thresholds": {
      "applies_to": "offline validation and future opt-in pilot",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-half-marathon.direct-field-baseline-preferred-with-error",
        "road-half-marathon.subgroup-dose-rules-unproven"
      ],
      "value": {
        "deterministic_invariant_breach_tolerance": 0,
        "deterministic_replay_mismatch_tolerance": 0,
        "dry_run_metrics_required": [
          "eligibility_and_no_plan_rates",
          "each_guardrail_exclusion_rate",
          "subgroup_missingness_and_exclusion_gaps",
          "proposal_edit_and_rejection_burden",
          "fueling_prompt_acceptance_and_tolerance_missingness",
          "event_conflicts_and_recovery_exits"
        ],
        "exact_dry_run_go_no_go_thresholds": "not_accepted",
        "exact_prospective_pause_thresholds": "not_accepted",
        "prospective_pilot_metrics_required": [
          "adoption_and_edit_distance",
          "adherence_burden",
          "quality_and_event_stacking",
          "symptom_stops_and_adverse_events",
          "fueling_tolerance",
          "comparable_half_marathon_outcomes",
          "withdrawal"
        ]
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:8b578c26dc6ed33eaed91c881edb68de4693a657f370d37e98d96ef04e35ed68"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If accepted by a digest-bound decision approver, this SDR would authorize only an inactive-by-default policy boundary for adult outdoor road half-marathon performance intent with current direct half-marathon capability, stable recent history, within-recent load, confirmed event context, and absent current symptom-stop inputs. The goal could have an optional target time and date and would remain recorded when no generator route matches. Population evidence would inform uncertainty, taper, and fueling communication without creating a personal success probability. This draft does not select a direct-baseline qualification algorithm, baseline freshness window, minimum history counts, frequency envelope, exact volume progression, low-intensity percentage, quality-session ceiling, long-run share or distance, hard-session spacing, taper prescription or accounting, execution window, fueling duration or intake rules, workout templates, aggressive short-horizon alternative, or pilot thresholds. It does not activate a generator or authorize beginner, sparse-history, clinical, trail, marathon, or ultra planning.",
  "affected_surfaces": {
    "apis": [
      "future authenticated half-marathon capability and typed proposal endpoints",
      "future event, fueling-practice, and confirmation inputs"
    ],
    "clients": [
      "generated human Evidence Review and SDR packets",
      "future web half-marathon goal, readiness, event, fueling, proposal, consent, and no-plan states",
      "future miniapp feature, write, type, state, i18n, and consent parity",
      "future plugin and MCP capability discovery and proposal parity"
    ],
    "models": [
      "road-half-marathon-plan-generation-policy-v1",
      "shared dynamic training-pattern and confirmed event snapshots"
    ],
    "science_notes": [
      "Explain direct, associative, and broader-endurance evidence separately.",
      "Show every unresolved guardrail, baseline source, event state, fueling assumption, risk, and alternative."
    ]
  },
  "applicability": [
    "Adult scope confirmed by the accepted shared router",
    "Current direct outdoor road half-marathon capability",
    "Stable recent history and within-recent load pattern",
    "Performance intent with optional target time and target date",
    "Confirmed-none, single-target, or conflict-resolved race-dense event context",
    "Suggestion-only future behavior after all open guardrails and implementation reviews are accepted",
    "Evidence cohorts include recreational and amateur runners without assigning a permanent identity"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-08-14",
  "decision_notes": [
    "This artifact-mode decision proposal addresses issue #688 and remains draft and inactive.",
    "Human review should use the generated packet rather than raw YAML. The packet includes the exact machine contract and digest-bound approval templates.",
    "The core proposed scope is history-rich, currently capable adult outdoor road half-marathon performance planning; completion and sparse-history policies remain separate.",
    "Direct evidence supports task-specific capability, observational volume and longest-run associations, and error-aware target communication. Taper, intensity distribution, recovery, and fueling transfer from broader endurance evidence with explicit limits.",
    "Every unresolved schedule, dose, taper, fueling, and pilot choice is encoded as `not_accepted`; implementation may not infer a value.",
    "Impact map: draft Evidence Review -> generated evidence packet -> draft SDR -> generated decision packet and inactive contract -> role-scoped approvals -> future pure routing and policy implementation -> API -> web and miniapp parity -> ScienceNote and localization -> offline validation -> opt-in pilot."
  ],
  "decision_review": {
    "approval_statement": "I approve the supported scope, evidence-use limits, and hard safety and control boundaries below, including a mostly-low-intensity organizational boundary without an exact distribution. I also agree that baseline/history rules, training dose and taper, fueling rules, and pilot thresholds remain deferred. I understand this decision stays inactive and does not approve implementation or runtime activation.",
    "items": [
      {
        "approval_effect": [
          "The half-marathon performance pattern becomes an accepted policy boundary.",
          "First-completion, sparse-history, trail, treadmill, clinical, marathon, and ultra cases remain separate policies.",
          "A future implementation may expose these typed outcomes only after separate implementation approval."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Any generated workout, schedule, target-time guarantee, or automatic benchmark.",
          "Runtime activation, plan adoption, delivery, or publication."
        ],
        "evidence_claim_ids": [
          "eligibility.goal-relevant-current-capability-task-specific",
          "eligibility.current-symptoms-support-stop-not-clearance",
          "eligibility.masters-age-change-not-automatic-exclusion",
          "road-half-marathon.task-specific-capability-is-multifactor"
        ],
        "id": "supported-scope",
        "parameter_names": [
          "road_half_marathon_activation_and_dependency",
          "road_half_marathon_goal_tuple",
          "road_half_marathon_supported_training_pattern",
          "road_half_marathon_event_context",
          "road_half_marathon_typed_outcomes"
        ],
        "proposed_decision": "Accept that narrow pattern, preserve every user's goal when no route matches, and use typed no-plan or limited-guidance outcomes instead of silently substituting another distance or intent.",
        "question": "Should V1 recognize adult outdoor-road half-marathon performance goals only when current direct capability, stable history, within-recent load, event context, and symptom-stop inputs match the stated pattern?",
        "title": "Accept the narrow V1 population and goal scope"
      },
      {
        "approval_effect": [
          "Published findings may support review notes, uncertainty, and future validation design.",
          "Before/after outcomes require comparable protocols and remain descriptive rather than causal."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Treating 32 km per week, a 21 km long run, taper ranges, or fueling ranges as eligibility or prescription.",
          "A personal success probability, injury probability, responder label, or medically safe claim."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "road-half-marathon.volume-and-long-run-are-associative",
          "road-half-marathon.taper-is-indirectly-supported",
          "road-half-marathon.fueling-and-gut-practice-supported",
          "road-half-marathon.direct-field-baseline-preferred-with-error"
        ],
        "id": "evidence-use",
        "parameter_names": [
          "road_half_marathon_published_volume_and_long_run_findings",
          "road_half_marathon_published_taper_findings",
          "road_half_marathon_published_fueling_findings",
          "road_half_marathon_protocol_comparability_and_outcomes",
          "road_half_marathon_user_facing_uncertainty"
        ],
        "proposed_decision": "Accept the reported source findings and their uncertainty labels for explanation and later validation, while prohibiting personal probability, causal plan-benefit, universal dose, and distance-only fueling claims.",
        "question": "Should the reviewed volume, longest-run, taper, fueling, and prediction findings be retained as bounded evidence context rather than converted into personal thresholds or prescriptions?",
        "title": "Accept how population evidence may and may not be used"
      },
      {
        "approval_effect": [
          "Direct capability cannot be manufactured from predictions or passive segments.",
          "AI cannot invent missing context, select deferred rules, approve, activate, adopt, or deliver a plan.",
          "Athlete constraints, consent, privacy, and symptom stops remain hard boundaries."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "The unresolved numeric or algorithmic parts of the same contract groups.",
          "Medical diagnosis, clearance, treatment, or inference of sensitive context."
        ],
        "evidence_claim_ids": [
          "eligibility.fixed-progression-and-acwr-not-safety-laws",
          "eligibility.current-symptoms-support-stop-not-clearance",
          "road-half-marathon.direct-field-baseline-preferred-with-error",
          "road-half-marathon.exact-long-run-dose-unproven",
          "road-half-marathon.recovery-spacing-unresolved"
        ],
        "id": "hard-boundaries",
        "parameter_names": [
          "road_half_marathon_direct_baseline_hierarchy",
          "road_half_marathon_target_and_short_horizon_routing",
          "road_half_marathon_history_anchored_load_and_long_run",
          "road_half_marathon_intensity_structure",
          "road_half_marathon_recovery_boundary",
          "road_half_marathon_selected_taper_guardrail",
          "road_half_marathon_fueling_practice_policy",
          "road_half_marathon_suggestion_only_state_transition",
          "road_half_marathon_privacy_and_audit"
        ],
        "proposed_decision": "Accept those prohibitions and keep every future plan suggestion-only, athlete-editable, explicitly adopted, auditable, and subordinate to symptom stops and deterministic validation.",
        "question": "Should Praxys prohibit automatic maximal half-marathon baseline tests, target-gap dose escalation, generic progression laws, activity-average-power intensity analysis, missed-workout makeup, unpracticed race fueling, sensitive inference, and AI authority expansion?",
        "title": "Accept conservative safety, consent, and automation boundaries"
      },
      {
        "approval_effect": [
          "A future implementation must organize more work as low intensity than as threshold or high intensity.",
          "The boundary must remain labelled as indirect to adult road half-marathon planning."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A low-intensity percentage, quality-session ceiling, exact spacing, or named distribution model.",
          "Any use of activity-average power for intensity analysis."
        ],
        "evidence_claim_ids": [
          "road-half-marathon.intensity-distribution-no-universal-winner"
        ],
        "id": "mostly-low-structure",
        "parameter_names": [
          "road_half_marathon_intensity_structure"
        ],
        "proposed_decision": "Accept only the broad mostly-low organizational boundary, based on indirect mixed-distance endurance evidence, without claiming one universally superior polarized, pyramidal, threshold, or race-pace distribution.",
        "question": "Should any future V1 plan use a mostly-low-intensity structure while leaving the exact low-intensity percentage, quality-session count, distribution model, and workout mix unresolved?",
        "title": "Accept a mostly-low-intensity organizational boundary"
      },
      {
        "approval_effect": [
          "Missing or stale capability and insufficient history remain typed readiness limitations.",
          "No implementation may copy 5 km or 10 km thresholds or invent defaults."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A distance tolerance, result expiry, minimum week/run count, or fixed reassessment cadence.",
          "An automatic maximal half-marathon baseline test."
        ],
        "evidence_claim_ids": [
          "eligibility.recent-history-anchor-without-universal-threshold",
          "eligibility.goal-relevant-current-capability-task-specific",
          "road-half-marathon.direct-field-baseline-preferred-with-error"
        ],
        "id": "defer-baseline-history",
        "parameter_names": [
          "road_half_marathon_direct_baseline_hierarchy",
          "road_half_marathon_baseline_freshness",
          "road_half_marathon_recent_history_inputs",
          "road_half_marathon_planning_and_reassessment"
        ],
        "proposed_decision": "Keep these values and algorithms unaccepted until a later decision can compare options and validation consequences.",
        "question": "Should exact direct-result qualification, freshness, history counts, lookback, and reassessment cadence remain unresolved?",
        "title": "Defer baseline qualification and history sufficiency"
      },
      {
        "approval_effect": [
          "Future research or product review must select each value explicitly.",
          "A near target date cannot trigger catch-up or hidden dose escalation."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A weekly frequency range, low-intensity percentage, quality count, long-run share, or progression rate.",
          "An execution window, workout template, taper percentage/window, recovery interval, or event-minute formula."
        ],
        "evidence_claim_ids": [
          "eligibility.fixed-progression-and-acwr-not-safety-laws",
          "road-half-marathon.exact-long-run-dose-unproven",
          "road-half-marathon.intensity-distribution-no-universal-winner",
          "road-half-marathon.recovery-spacing-unresolved",
          "road-half-marathon.taper-is-indirectly-supported"
        ],
        "id": "defer-dose-taper",
        "parameter_names": [
          "road_half_marathon_target_and_short_horizon_routing",
          "road_half_marathon_history_anchored_load_and_long_run",
          "road_half_marathon_intensity_structure",
          "road_half_marathon_recovery_boundary",
          "road_half_marathon_selected_taper_guardrail"
        ],
        "proposed_decision": "Keep every exact schedule and dose choice unaccepted; retain only the approved hard prohibitions and source findings.",
        "question": "Should frequency, progression, long-run dose, intensity distribution, quality spacing, short-horizon handling, taper, and event-minute accounting remain unresolved?",
        "title": "Defer training dose, session structure, recovery, and taper"
      },
      {
        "approval_effect": [
          "Fueling guidance cannot route from the half-marathon label alone.",
          "Future rules must consider expected duration, prior practice, tolerance, and athlete preference."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A 90-minute product threshold or a 30 to 60 grams-per-hour personal prescription.",
          "A new race-day strategy without practice and athlete choice."
        ],
        "evidence_claim_ids": [
          "road-half-marathon.fueling-and-gut-practice-supported"
        ],
        "id": "defer-fueling",
        "parameter_names": [
          "road_half_marathon_fueling_practice_policy"
        ],
        "proposed_decision": "Keep the product rules unaccepted while retaining only the approved evidence-use limits, prior-practice requirement, and distance-only automation prohibition.",
        "question": "Should product duration bands, intake ranges or caps, carbohydrate loading thresholds, and exact prompts remain unresolved?",
        "title": "Defer product fueling rules"
      },
      {
        "approval_effect": [
          "Deterministic invariant and replay tolerance remain zero.",
          "All statistical, schedule, and rollout thresholds remain explicit future decisions."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Implementing unresolved values, marking the capability available, or running a pilot.",
          "Treating this science decision approval as implementation or activation approval."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "road-half-marathon.subgroup-dose-rules-unproven"
        ],
        "id": "defer-pilot-activation",
        "parameter_names": [
          "road_half_marathon_planning_and_reassessment",
          "road_half_marathon_validation_and_pilot_thresholds",
          "road_half_marathon_open_decisions"
        ],
        "proposed_decision": "Keep the contract inactive and require separately reviewed values, implementation mapping, deterministic replay, and an opt-in pilot protocol before runtime use.",
        "question": "Should statistical go/no-go thresholds, safety pause thresholds, exact workouts, and every catalogued open decision remain unresolved before implementation or activation?",
        "title": "Defer pilot thresholds and all remaining open decisions"
      }
    ],
    "reviewer_task": "Decide whether the four proposed policy boundaries are acceptable and whether the four listed implementation areas should remain explicitly deferred. Approve the sheet as a unit, or request changes by item ID. The exact contract is an audit appendix, not the primary review task."
  },
  "evidence_claim_ids": [
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.fixed-progression-and-acwr-not-safety-laws",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.current-symptoms-support-stop-not-clearance",
    "eligibility.evidence-quality-no-personal-probability",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "road-half-marathon.task-specific-capability-is-multifactor",
    "road-half-marathon.volume-and-long-run-are-associative",
    "road-half-marathon.taper-is-indirectly-supported",
    "road-half-marathon.fueling-and-gut-practice-supported",
    "road-half-marathon.direct-field-baseline-preferred-with-error",
    "road-half-marathon.exact-long-run-dose-unproven",
    "road-half-marathon.intensity-distribution-no-universal-winner",
    "road-half-marathon.recovery-spacing-unresolved",
    "road-half-marathon.subgroup-dose-rules-unproven"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-road-half-marathon-plan-generation-policy-v1"
  ],
  "falsification_conditions": [
    "Reject the policy if any implementation emits a plan while the contract is draft or inactive, consumes an unapproved parameter, or omits a code-consumed field from the human review packet.",
    "Reject routing if a shorter-distance conversion, prediction, threshold, activity-average power, or passive segment is treated as direct current half-marathon capability.",
    "Reject schedule mapping if observational 32 km or 21 km categories become universal eligibility or dose requirements.",
    "Reject target routing if a short horizon invalidates the goal, increases dose, schedules catch-up, or produces a personal probability.",
    "Reject fueling behavior if distance alone triggers carbohydrate loading or a new race-day intake strategy without prior practice and consent.",
    "Pause future activation after any deterministic invariant or replay breach, unconfirmed event use, quality/load event omission, unsupported population, hidden demographic default, symptom-stop override, or approval-digest mismatch.",
    "Revise or reject candidate guardrails when predeclared dry-run or pilot thresholds are breached; those thresholds are themselves not accepted by this draft."
  ],
  "id": "sdr-road-half-marathon-plan-generation-policy-v1",
  "model_parameters": [
    {
      "applies_to": "policy lifecycle and capability registry",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_half_marathon_activation_and_dependency",
      "rationale": "Draft science, generated artifacts, and review packets do not activate product behavior. Acceptance, implementation review, exact unresolved guardrails, deterministic validation, and rollout remain separate gates.",
      "value": {
        "active_behavior": false,
        "capability_registry_entry_default_enabled": false,
        "decision_approval_artifact_required": true,
        "distance_policy_required_status_before_activation": "accepted",
        "evidence_review_required_status_before_activation": "accepted",
        "generator_api_web_miniapp_plugin_and_mcp_activation_in_this_record": false,
        "implementation_approval_artifact_required": true,
        "shared_policy_dependency": {
          "required_status_before_activation": "accepted",
          "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
        }
      }
    },
    {
      "applies_to": "goal normalization and distance-policy selection",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-half-marathon.task-specific-capability-is-multifactor"
      ],
      "name": "road_half_marathon_goal_tuple",
      "rationale": "Goal choice remains durable and independent from generator availability. This distance policy is limited to current performance intent and cannot be scaled down to completion or sparse-history populations.",
      "value": {
        "goal_intent": "performance",
        "goal_kind": "distance_half_marathon",
        "no_event_goal_may_remain_recorded": true,
        "primary_outcome": "elapsed_time",
        "separate_policy_variants": [
          "first_half_marathon_completion",
          "sparse_history_half_marathon",
          "treadmill_half_marathon",
          "trail_half_marathon",
          "multisport_run_leg",
          "marathon_or_ultra",
          "medically_directed_rehabilitation",
          "pregnancy_specific_planning"
        ],
        "sport": "running",
        "surface": "outdoor_road",
        "target_date_optional": true,
        "target_time_optional": true
      }
    },
    {
      "applies_to": "shared pattern routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "road-half-marathon.subgroup-dose-rules-unproven"
      ],
      "name": "road_half_marathon_supported_training_pattern",
      "rationale": "V1 matches a time-bounded evidence pattern rather than a recreational, serious, professional, elite, female, male, or masters identity.",
      "value": {
        "adult_scope": "confirmed",
        "capability_pattern": "currently_capable",
        "current_symptoms": "absent",
        "event_context": [
          "confirmed_none",
          "single_target",
          "race_dense"
        ],
        "evidence_directness": [
          "direct",
          "supporting"
        ],
        "explicit_exclusions": [
          "adult_scope_unconfirmed",
          "first_half_marathon_completion_requires_separate_policy",
          "sparse_interrupted_or_missing_history",
          "current_injury_illness_or_concerning_symptoms",
          "rehabilitation_return_to_sport_or_medical_clearance",
          "pregnancy_specific_prescription",
          "unresolved_material_event_context",
          "unsupported_surface_distance_or_intent"
        ],
        "history_pattern": "stable",
        "load_pattern": "within_recent",
        "permanent_runner_identity_used": false,
        "race_dense_requires_resolved_conflicts": true
      }
    },
    {
      "applies_to": "baseline qualification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-half-marathon.task-specific-capability-is-multifactor",
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "name": "road_half_marathon_direct_baseline_hierarchy",
      "rationale": "Same-task field evidence is most direct. Prediction, physiology, and shorter-distance performance may support context but retain meaningful individual error and cannot silently authorize generation.",
      "value": {
        "accepted_evidence_order": [
          "organized_outdoor_road_half_marathon_with_elapsed_time",
          "athlete_confirmed_standardized_outdoor_road_half_marathon_time_trial"
        ],
        "allowed_assistance_statuses": "not_accepted",
        "allowed_surface_values": "not_accepted",
        "automatic_maximal_baseline_test": "prohibited",
        "baseline_qualification_algorithm": "not_accepted",
        "direct_current_capability_required": true,
        "distance_match_tolerance_m": "not_accepted",
        "excluded_as_direct": [
          "shorter_race_conversion",
          "marathon_or_ultra_split",
          "passive_fastest_half_marathon_segment",
          "personal_best_without_source_activity",
          "activity_average_power",
          "vendor_readiness_or_race_score"
        ],
        "missing_direct_result_outcome": "insufficient_direct_half_marathon_baseline",
        "required_metadata": [
          "completed_at",
          "elapsed_time_seconds",
          "measured_distance_m",
          "route_or_event_identifier",
          "surface",
          "assistance_status",
          "source_provider",
          "race_or_intentional_time_trial_flag"
        ],
        "standardized_time_trial_protocol": "not_accepted",
        "supporting_only": [
          "cooper_test",
          "current_vo2max_or_vvo2max",
          "current_threshold_or_critical_speed",
          "weekly_training_distance",
          "recent_longest_run",
          "race_forecast_with_error",
          "split_or_sample_pacing_distribution"
        ]
      }
    },
    {
      "applies_to": "capability freshness",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "name": "road_half_marathon_baseline_freshness",
      "rationale": "No reviewed source validates a half-marathon result expiry threshold. Selecting one is a product guardrail that must be reviewed separately before activation.",
      "value": {
        "exact_current_through_completed_days": "not_accepted",
        "missing_or_stale_outcome": "readiness_only",
        "no_biological_expiry_claim": true,
        "required_before_activation": true,
        "stale_boundary": "not_accepted"
      }
    },
    {
      "applies_to": "history-rich qualification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.exact-long-run-dose-unproven"
      ],
      "name": "road_half_marathon_recent_history_inputs",
      "rationale": "History must anchor the runner's own exposure, but the review does not establish universal counts. Exact qualification remains visible rather than inheriting 5 km or 10 km values.",
      "value": {
        "disallowed_intensity_source": [
          "activity_avg_power"
        ],
        "exact_lookback_weeks": "not_accepted",
        "history_qualification_algorithm": "not_accepted",
        "intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "latest_run_freshness_days": "not_accepted",
        "minimum_runs_per_usable_week": "not_accepted",
        "minimum_usable_weeks": "not_accepted",
        "required_observations": [
          "completed_weekly_running_minutes_and_distance",
          "completed_running_days_per_week",
          "recent_longest_run_duration_and_distance",
          "quality_session_and_event_density",
          "recent_load_relative_to_self",
          "availability_and_single_session_constraints",
          "prior_half_marathon_count_when_known"
        ],
        "unresolved_history_outcome": "insufficient_history_anchor"
      }
    },
    {
      "applies_to": "proposal horizon and reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-half-marathon.volume-and-long-run-are-associative"
      ],
      "name": "road_half_marathon_planning_and_reassessment",
      "rationale": "No reviewed evidence establishes an exact half-marathon plan horizon or reassessment cadence. Rolling context and explicit triggers are retained, while the committed execution window remains an open decision.",
      "value": {
        "automatic_progression_between_reassessments": false,
        "each_reassessment_requires": [
          "fresh_shared_eligibility",
          "updated_history_and_longest_run",
          "updated_event_context",
          "updated_dynamic_pattern_snapshot",
          "updated_fueling_practice_context",
          "explicit_review_before_replacing_adopted_future_days"
        ],
        "exact_calendar_reassessment_cadence": "not_accepted",
        "exact_committed_execution_window_days": "not_accepted",
        "fixed_full_block_days": "none_defined",
        "fixed_horizon_eligibility_gate": false,
        "reassessment_triggers": [
          "new_or_changed_confirmed_event",
          "material_training_pattern_change",
          "new_qualified_half_marathon_result",
          "changed_availability_or_constraint",
          "changed_fueling_tolerance_or_practice",
          "completed_target_event",
          "athlete_requested_review"
        ],
        "target_date_required": false
      }
    },
    {
      "applies_to": "target communication and short-horizon routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "name": "road_half_marathon_target_and_short_horizon_routing",
      "rationale": "Prediction error is material and no personal probability or compressed catch-up policy is validated. A short horizon limits the claim and available states rather than invalidating the athlete's goal.",
      "value": {
        "aggressive_or_catch_up_variant": "not_accepted",
        "near_event_supported_states": [
          "readiness_only",
          "maintain",
          "taper_after_taper_guardrail_acceptance",
          "limited_guidance"
        ],
        "personal_goal_achievement_probability": "disabled",
        "personal_injury_probability": "disabled",
        "short_horizon_invalidates_goal": false,
        "target_gap_dose_escalation": "prohibited",
        "target_time_may": [
          "label_goal",
          "compute_descriptive_gap_to_direct_baseline",
          "select_uncertainty_copy"
        ],
        "target_time_may_not": [
          "increase_weekly_volume",
          "increase_frequency",
          "lengthen_longest_run",
          "add_quality",
          "weaken_history_or_safety_rules"
        ]
      }
    },
    {
      "applies_to": "event calendar and schedule conflicts",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.recovery-spacing-unresolved",
        "road-half-marathon.taper-is-indirectly-supported",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_half_marathon_event_context",
      "rationale": "Event priority and dense-calendar behavior remain product guardrails. Confirmed events nevertheless consume load and quality capacity, and a maximal half-marathon benchmark is never silently created.",
      "value": {
        "confirmed_primary_event_may_trigger_taper_only_after_taper_guardrail_acceptance": true,
        "every_race_or_maximal_effort": {
          "counts_as_quality_session": true,
          "counts_as_training_load": true,
          "requires_recovery_reassessment": true
        },
        "imported_event_must_be_athlete_confirmed": true,
        "no_event_performance_goal": {
          "automatic_half_marathon_benchmark": "prohibited",
          "goal_remains_recorded": true,
          "rolling_policy_before_activation": "readiness_only"
        },
        "shared_event_states_consumed": [
          "confirmed_none",
          "single_target",
          "race_dense"
        ],
        "unresolved_race_dense_outcome": "limited_guidance_event_conflict"
      }
    },
    {
      "applies_to": "evidence display and guardrail rationale",
      "classification": "published",
      "evidence_claim_ids": [
        "road-half-marathon.volume-and-long-run-are-associative"
      ],
      "name": "road_half_marathon_published_volume_and_long_run_findings",
      "rationale": "Values reproduce the direct observational study and are not eligibility thresholds or prescriptions.",
      "value": {
        "causal_dose_or_safety_established": false,
        "longest_run_category_associated_with_faster_time_km_more_than": 21,
        "longest_run_finish_time_coefficient_minutes": -3.87,
        "observational_only": true,
        "study_population": "adult_recreational_half_marathon_runners",
        "weekly_distance_category_associated_with_faster_time_km_more_than": 32,
        "weekly_distance_finish_time_coefficient_minutes": -4.19
      }
    },
    {
      "applies_to": "weekly exposure and longest-run boundary",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.exact-long-run-dose-unproven"
      ],
      "name": "road_half_marathon_history_anchored_load_and_long_run",
      "rationale": "The direct evidence is associative. V1 must not convert population bins into requirements. Proposed self-history caps are deliberately surfaced for review rather than presented as proven optimal progression.",
      "value": {
        "acwr_prescription_zone_used": false,
        "athlete_availability_and_single_session_limits_are_hard_caps": true,
        "automatic_long_run_progression": false,
        "exact_long_run_distance_or_duration": "not_accepted",
        "exact_long_run_share_of_weekly_volume": "not_accepted",
        "exact_weekly_progression": "not_accepted",
        "mandatory_long_run": false,
        "observed_32_km_week_or_21_km_long_run_used_as_minimum": false,
        "planned_longest_run_may_not_exceed_recent_completed_maximum": "proposed_guardrail_for_review",
        "planned_weekly_exposure_may_not_exceed_recent_completed_maximum": "proposed_guardrail_for_review",
        "target_gap_may_raise_load": false,
        "ten_percent_rule_used": false
      }
    },
    {
      "applies_to": "session structure and intensity analysis",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.intensity-distribution-no-universal-winner",
        "road-half-marathon.recovery-spacing-unresolved"
      ],
      "name": "road_half_marathon_intensity_structure",
      "rationale": "Evidence supports mostly-low organization and some quality work without one universal distribution, quality count, or template. Nonconsecutive placement is a proposed conservative guardrail requiring explicit review.",
      "value": {
        "activity_average_power_allowed": false,
        "allowed_session_categories": [
          "easy",
          "longest_easy",
          "controlled_threshold",
          "half_marathon_specific_or_race_pace",
          "interval",
          "confirmed_event"
        ],
        "consecutive_quality_running_days_allowed": "proposed_false_for_review",
        "exact_low_intensity_fraction": "not_accepted",
        "exact_session_mix": "not_accepted",
        "exact_step_templates": "not_accepted",
        "generic_percent_of_threshold_or_critical_power_targets": false,
        "intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "maximum_quality_sessions_per_7_day_unit": "not_accepted",
        "mostly_low_intensity_structure_required": true
      }
    },
    {
      "applies_to": "recovery and quality spacing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.recovery-spacing-unresolved",
        "eligibility.current-symptoms-support-stop-not-clearance"
      ],
      "name": "road_half_marathon_recovery_boundary",
      "rationale": "Recovery evidence varies by measure and post-race behavior. The policy rejects one exact spacing law and uses reassessment rather than automatically scheduling recovery intensity or missed-session makeup.",
      "value": {
        "completed_half_marathon_requires_pattern_and_recovery_reassessment": true,
        "event_or_benchmark_counts_as_quality_and_load": true,
        "exact_hours_between_quality_sessions": "not_accepted",
        "high_intensity_recovery_run_automatically_scheduled": false,
        "missed_quality_makeup_allowed": false,
        "symptoms_override_recovery_schedule": true,
        "universal_one_to_three_day_recovery_rule": false
      }
    },
    {
      "applies_to": "taper evidence",
      "classification": "published",
      "evidence_claim_ids": [
        "road-half-marathon.taper-is-indirectly-supported"
      ],
      "name": "road_half_marathon_published_taper_findings",
      "rationale": "These values reproduce the reviewed meta-analysis and remain explicitly indirect to adult road half-marathon planning.",
      "value": {
        "direct_adult_road_half_marathon_validation": false,
        "evidence_population": "mixed_endurance_athletes",
        "maintain_frequency": true,
        "maintain_intensity": true,
        "strongest_duration_subgroup_days": {
          "maximum": 14,
          "minimum": 8
        },
        "strongest_volume_reduction_percent": {
          "maximum": 60,
          "minimum": 41
        }
      }
    },
    {
      "applies_to": "event taper selection",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.taper-is-indirectly-supported"
      ],
      "name": "road_half_marathon_selected_taper_guardrail",
      "rationale": "The evidence range is useful but does not select one half-marathon template. The exact product guardrail is intentionally left for human review.",
      "value": {
        "exact_frequency_rule": "not_accepted",
        "exact_intensity_exposure": "not_accepted",
        "exact_taper_window_days": "not_accepted",
        "exact_volume_reduction_percent": "not_accepted",
        "no_extra_sharpening_or_makeup": true,
        "personal_performance_gain_claim": "prohibited",
        "pre_event_training_minutes_accounting": "not_accepted",
        "required_before_taper_activation": true,
        "target_event_elapsed_time_included_in_training_minutes": "not_accepted"
      }
    },
    {
      "applies_to": "fueling evidence display only",
      "classification": "published",
      "evidence_claim_ids": [
        "road-half-marathon.fueling-and-gut-practice-supported"
      ],
      "name": "road_half_marathon_published_fueling_findings",
      "rationale": "Values reproduce broader-endurance source findings for evidence display. They are not product duration bands, intake minima or maxima, or an automatic half-marathon fueling prescription.",
      "value": {
        "direct_half_marathon_dose_validation": false,
        "gut_training": {
          "carbohydrate_malabsorption_reduction_reported_percent": {
            "high": 54,
            "low": 45
          },
          "gastrointestinal_discomfort_reduction_reported_percent": 47
        },
        "source_guidance": {
          "around_one_hour": {
            "small_amount_or_carbohydrate_mouth_rinse_supported": true
          },
          "glycogen_loading": {
            "source_boundary_minutes": 90,
            "source_statement": "not_recommended_for_events_shorter_than_boundary"
          },
          "longer_endurance_exercise": {
            "reported_carbohydrate_grams_per_hour": {
              "high": 60,
              "low": 30
            }
          }
        }
      }
    },
    {
      "applies_to": "fueling-practice context and user communication",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.fueling-and-gut-practice-supported"
      ],
      "name": "road_half_marathon_fueling_practice_policy",
      "rationale": "The product must not turn general sports-nutrition ranges into a hidden individualized prescription. Product duration branches, intake ranges/caps, loading thresholds, and exact prompts remain review decisions.",
      "value": {
        "athlete_may_decline_optional_profile_or_tolerance_detail": true,
        "automatic_carbohydrate_loading_from_distance_label": "prohibited",
        "exact_duration_bands_and_prompts": "not_accepted",
        "fueling_prompt_is_medical_or_dietetic_treatment": false,
        "missing_optional_detail_effect": "generic_uncertainty_only",
        "new_race_day_strategy_without_practice": "prohibited",
        "product_carbohydrate_grams_per_hour_range_or_cap": "not_accepted",
        "product_during_exercise_duration_bands": "not_accepted",
        "product_glycogen_loading_duration_threshold": "not_accepted",
        "published_findings_are_runtime_routing_rules": false,
        "required_inputs": [
          "expected_event_duration_band",
          "prior_during_run_carbohydrate_practice",
          "prior_gastrointestinal_tolerance_or_issue",
          "athlete_preference"
        ]
      }
    },
    {
      "applies_to": "post-plan evaluation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.direct-field-baseline-preferred-with-error",
        "road-half-marathon.task-specific-capability-is-multifactor",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_half_marathon_protocol_comparability_and_outcomes",
      "rationale": "Same distance alone does not establish comparable conditions or causal plan benefit. Evaluation separates observed outcome, execution, context, and unresolved causal hypotheses.",
      "value": {
        "causal_plan_effect_claim": "prohibited",
        "direct_before_after_claim_requires": [
          "comparable_half_marathon_distance_and_result_type",
          "known_route_or_event",
          "known_surface",
          "known_assistance_status",
          "known_environment_context_when_available",
          "no_material_protocol_change"
        ],
        "missing_comparability_outcome": "descriptive_context_only",
        "personal_responder_classification": "prohibited",
        "supporting_post_plan_inputs": [
          "split_level_pacing_and_pace_decline",
          "adherence_and_edit_burden",
          "fueling_practice_and_gastrointestinal_response",
          "recovery_response",
          "weekly_volume_frequency_and_longest_run_change"
        ]
      }
    },
    {
      "applies_to": "future API and client outcome contract",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "road-half-marathon.direct-field-baseline-preferred-with-error"
      ],
      "name": "road_half_marathon_typed_outcomes",
      "rationale": "Typed outcomes preserve goal intent while the draft and unresolved implementation guardrails keep every plan path inactive.",
      "value": {
        "current_runtime_state": "policy_inactive",
        "outcomes": {
          "adult_scope_unconfirmed": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "contradictory_input": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "eligible_future_policy_pattern": {
            "goal_remains_recorded": true,
            "plan_returned_while_inactive": false,
            "review_packet_available": true
          },
          "insufficient_direct_half_marathon_baseline": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "insufficient_history_anchor": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "intent_requires_separate_policy": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "limited_guidance_event_conflict": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false
          },
          "safety_stop": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "unresolved_event_context": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "unresolved_policy_guardrail": {
            "goal_remains_recorded": true,
            "plan_returned": false
          }
        },
        "unknown_values_are_not_false_or_zero": true,
        "unsupported_distance_fallback": "none"
      }
    },
    {
      "applies_to": "proposal and adoption state",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_half_marathon_suggestion_only_state_transition",
      "rationale": "Deterministic validation, role-scoped human approval, and athlete consent remain separate authority boundaries.",
      "value": {
        "AI_may_not": [
          "broaden_eligibility",
          "invent_capability_history_event_profile_or_safety_context",
          "choose_unaccepted_guardrails",
          "override_deterministic_validation",
          "create_human_approval_artifacts",
          "activate_adopt_deliver_or_publish"
        ],
        "generated_state_after_future_activation": "proposed",
        "generator_may_not": [
          "adopt_or_deliver_without_consent",
          "overwrite_adopted_future_days",
          "auto_schedule_a_half_marathon_benchmark",
          "auto_change_event_priority",
          "schedule_missed_workout_makeup",
          "infer_missed_workout_reason",
          "invent_fueling_tolerance"
        ],
        "user_may": [
          "review",
          "edit",
          "reject",
          "explicitly_adopt"
        ]
      }
    },
    {
      "applies_to": "audit and privacy",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_half_marathon_privacy_and_audit",
      "rationale": "Future generation must remain reproducible without inferring or exposing sensitive explanations.",
      "value": {
        "minimum_necessary_inputs_only": true,
        "no_inference_of": [
          "diagnosis",
          "injury_cause",
          "pregnancy_status",
          "mental_state",
          "missed_training_reason",
          "gastrointestinal_diagnosis"
        ],
        "no_publication_of": [
          "raw_health_data",
          "private_activity_data",
          "inferred_sensitive_context"
        ],
        "replay_record_must_include": [
          "shared_and_distance_policy_versions",
          "decision_and_contract_digests",
          "goal_record_state",
          "dynamic_pattern_snapshot",
          "confirmed_event_context",
          "profile_and_fueling_field_provenance",
          "baseline_source",
          "history_cutoff_and_inputs",
          "unresolved_guardrail_versions",
          "typed_outcome",
          "proposal_hash"
        ]
      }
    },
    {
      "applies_to": "offline validation and future opt-in pilot",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-half-marathon.direct-field-baseline-preferred-with-error",
        "road-half-marathon.subgroup-dose-rules-unproven"
      ],
      "name": "road_half_marathon_validation_and_pilot_thresholds",
      "rationale": "Zero deterministic invariant tolerance is an engineering requirement. Statistical go/no-go and safety pause thresholds need a separate reviewed pilot protocol rather than being copied from another distance.",
      "value": {
        "deterministic_invariant_breach_tolerance": 0,
        "deterministic_replay_mismatch_tolerance": 0,
        "dry_run_metrics_required": [
          "eligibility_and_no_plan_rates",
          "each_guardrail_exclusion_rate",
          "subgroup_missingness_and_exclusion_gaps",
          "proposal_edit_and_rejection_burden",
          "fueling_prompt_acceptance_and_tolerance_missingness",
          "event_conflicts_and_recovery_exits"
        ],
        "exact_dry_run_go_no_go_thresholds": "not_accepted",
        "exact_prospective_pause_thresholds": "not_accepted",
        "prospective_pilot_metrics_required": [
          "adoption_and_edit_distance",
          "adherence_burden",
          "quality_and_event_stacking",
          "symptom_stops_and_adverse_events",
          "fueling_tolerance",
          "comparable_half_marathon_outcomes",
          "withdrawal"
        ]
      }
    },
    {
      "applies_to": "future English and Simplified Chinese review and product copy",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.taper-is-indirectly-supported",
        "road-half-marathon.fueling-and-gut-practice-supported",
        "road-half-marathon.subgroup-dose-rules-unproven"
      ],
      "name": "road_half_marathon_user_facing_uncertainty",
      "rationale": "The review surface must distinguish direct findings, broader-endurance transfer, unresolved guardrails, and product choices from certainty.",
      "value": {
        "always_show": [
          "current_policy_is_draft_and_inactive",
          "proposal_not_guarantee",
          "direct_associative_and_indirect_evidence_boundaries",
          "exact_unaccepted_guardrails",
          "baseline_source_and_prediction_error",
          "current_dynamic_pattern",
          "confirmed_event_context",
          "fueling_duration_and_tolerance_assumptions",
          "missing_profile_fields_and_specific_effects",
          "risks_unknowns_and_alternatives",
          "typed_no_plan_reason"
        ],
        "forbidden_copy": [
          "scientifically_optimal_half_marathon_plan",
          "safe_because_within_recent_history",
          "guaranteed_goal_time",
          "personal_success_or_injury_probability",
          "medically_cleared",
          "required_32_km_week",
          "required_overdistance_long_run",
          "automatic_carb_loading"
        ]
      }
    },
    {
      "applies_to": "human decision review",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-half-marathon.volume-and-long-run-are-associative",
        "road-half-marathon.exact-long-run-dose-unproven",
        "road-half-marathon.intensity-distribution-no-universal-winner",
        "road-half-marathon.recovery-spacing-unresolved",
        "road-half-marathon.taper-is-indirectly-supported",
        "road-half-marathon.fueling-and-gut-practice-supported"
      ],
      "name": "road_half_marathon_open_decisions",
      "rationale": "The review packet must make every unresolved behavior-driving choice explicit. None may be inferred by implementation or hidden in prose.",
      "value": {
        "aggressive_short_horizon_variant": "not_accepted",
        "baseline_freshness_days": "not_accepted",
        "direct_baseline_qualification_algorithm": "not_accepted",
        "exact_workout_templates": "not_accepted",
        "execution_window_and_reassessment_cadence": "not_accepted",
        "frequency_envelope": "not_accepted",
        "fueling_duration_bands_and_prompts": "not_accepted",
        "fueling_intake_range_or_cap": "not_accepted",
        "fueling_loading_duration_threshold": "not_accepted",
        "long_run_share_distance_and_ceiling": "not_accepted",
        "low_intensity_floor": "not_accepted",
        "minimum_history_counts": "not_accepted",
        "pilot_go_no_go_thresholds": "not_accepted",
        "quality_session_ceiling_and_spacing": "not_accepted",
        "selected_taper_guardrail": "not_accepted",
        "taper_training_minutes_accounting": "not_accepted",
        "weekly_progression_rule": "not_accepted"
      }
    }
  ],
  "model_version": "road-half-marathon-plan-generation-policy-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Use only the authenticated athlete's minimum necessary goal, activity, event, profile, constraints, fueling-practice, and optional symptom context.",
    "Provider fields remain source-labelled candidates until their purpose is disclosed and the athlete confirms or corrects them.",
    "Do not infer or publish diagnosis, injury cause, pregnancy status, gastrointestinal diagnosis, mental state, missed-training reason, or external life circumstance."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Copy the accepted 5 km or 10 km policy and replace the distance label",
      "rationale": "Half-marathon durability, longest-run exposure, target duration, fueling, recovery, and event demands differ materially. Existing distance guardrails are not universal evidence and cannot be silently inherited."
    },
    {
      "alternative": "Require more than 32 km per week or a longest run above 21 km",
      "rationale": "Those thresholds describe observational categories associated with performance in one cohort. They do not establish causal eligibility, safety, or an optimal prescription."
    },
    {
      "alternative": "Use a predicted half-marathon time as direct current capability",
      "rationale": "Field and laboratory models retain meaningful individual error and are predominantly male. They may support context but cannot manufacture a direct same-task result or personal probability."
    },
    {
      "alternative": "Schedule a maximal half-marathon benchmark when direct evidence is missing",
      "rationale": "A maximal half-marathon is burdensome and the review did not validate an automatic benchmark workflow. Missing direct capability remains a typed readiness limitation until a separate policy is accepted."
    },
    {
      "alternative": "Select a universal polarized, pyramidal, threshold, or race-pace distribution",
      "rationale": "Mixed-distance evidence supports multiple organizations and no universal winner. Exact distribution and session templates remain product choices."
    },
    {
      "alternative": "Use an aggressive catch-up block when the target is near",
      "rationale": "No reviewed evidence validates target-gap dose escalation, compressed progression, automatic makeup, or a universal short-horizon salvage plan."
    },
    {
      "alternative": "Apply one fueling prescription to every half-marathon",
      "rationale": "Expected duration and gastrointestinal tolerance vary substantially. Distance alone does not determine carbohydrate-loading or intake needs."
    },
    {
      "alternative": "Let AI fill missing policy values or infer athlete context",
      "rationale": "AI cannot repair missing evidence, verify events or profile fields, broaden eligibility, create approvals, or provide deterministic replay."
    }
  ],
  "safety_implications": [
    "Current concerning symptoms, illness, injury, rehabilitation, return-to-sport, medical-clearance, pregnancy-specific, or contradictory safety context stops the vigorous-plan path without diagnosis or treatment.",
    "Completing a half-marathon, staying within recent history, or lacking symptoms does not establish medical clearance or guarantee freedom from harm.",
    "No maximal half-marathon benchmark is automatically proposed when direct capability is missing or stale.",
    "Confirmed races and maximal efforts count as quality and load; unresolved dense-event conflicts prevent a full proposal.",
    "No target-gap escalation, catch-up, ten-percent rule, ACWR prescription zone, high-intensity recovery prescription, or activity-average-power intensity analysis is allowed."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "History-anchored adult outdoor road half-marathon performance policy",
  "user_facing_claim_limits": [
    "This draft is an evidence and product-decision boundary, not a usable half-marathon generator, optimal plan, safety guarantee, medical advice, or goal-time guarantee.",
    "Observed 32 km weekly volume and over-21 km longest-run categories must not be presented as requirements, safe thresholds, or optimal doses.",
    "Taper and fueling values must be labelled as broader-endurance evidence with half-marathon-specific uncertainty.",
    "Target time and indirect predictions may describe uncertainty but may not create a personal success probability or justify higher dose.",
    "Missing optional age, sex, or fueling-tolerance detail affects only the dependent communication or feature and never silently defaults to male.",
    "No 5 km or 10 km count, percentage, window, template, or progression rule is accepted for half-marathon use through this record."
  ],
  "validation_plan": [
    "Registry validation must prove exact Evidence Review and claim links, globally unique IDs, draft lifecycle validity, parameter classifications, exact citation verification notes, and inactive artifact policy.",
    "Artifact validation must prove that the generated Evidence Review and SDR packets carry current digests and that the exact machine contract embedded in the SDR packet matches the generated JSON contract.",
    "Tests must lock the exact supported tuple, current-capability and stable- history patterns, official distance, direct-baseline hierarchy, event accounting, activity-split/sample boundary, and typed no-plan states.",
    "Tests must prove every behavior-driving open choice remains `not_accepted`, no 5 km or 10 km numeric rule is inherited, and runtime state remains inactive without evidence, decision, and implementation approval artifacts.",
    "Before activation, separately reviewed decisions must select direct baseline qualification and freshness, history qualification, load and long-run caps, intensity and quality structure, taper and event-minute accounting, fueling duration/intake rules and prompts, execution windows, exact templates, and pilot thresholds.",
    "Offline dry runs must report exclusion, missingness, event conflict, edit/rejection burden, subgroup gaps, fueling-context availability, and deterministic replay without publishing private athlete data.",
    "A prospective opt-in pilot must predeclare adoption, adherence, edit distance, quality stacking, symptom and adverse-event exits, fueling tolerance, comparable outcomes, withdrawal, and human go/no-go thresholds."
  ],
  "version": 1
}
```

</details>
