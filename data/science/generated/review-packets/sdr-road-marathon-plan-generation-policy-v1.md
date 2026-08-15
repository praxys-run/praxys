# Science decision review packet: History-anchored adult outdoor road-marathon performance policy

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-road-marathon-plan-generation-policy-v1`
- **Lifecycle:** `draft`
- **Model version:** `road-marathon-plan-generation-policy-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:ffb7864995d0825713667c816f5d4c1255695fdf579857ca79c24e91c63c50f0`
- **Contract digest:** `sha256:8314b326744c7a3c7e87974e28ff818b6557c1cf31ac1576a100b8413510de8e`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the four proposed boundaries are acceptable and whether the five listed implementation areas should remain explicitly deferred. Approve the sheet as a unit or request changes by item ID. The audit appendix is traceability, not the primary review task.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `narrow-modular-scope` — Accept the narrow population tuple and modular boundary

- **Question:** Should V1 recognize only currently-capable adults with stable recent history, within-recent load, road-marathon performance intent, and confirmed event context, while preserving goals when no route matches?
- **Proposed decision:** Accept that narrow tuple and the eight-module boundary. Keep first-marathon/completion, sparse-history, returning or clinical, pregnancy-specific, trail, ultra, and unsupported contexts in separate policies. A no-event rolling preparation or simulation route requires a separately accepted completion or benchmark policy.
- **Approval means:**
  - The narrow performance tuple and eight-module policy structure become reviewable boundaries.
  - Goal capture remains available when this policy is unavailable or inactive.
  - Typed no-plan and limited-guidance outcomes preserve the athlete's goal without substituting another policy.
- **This does not authorize:**
  - A plan length, generated schedule, automatic marathon benchmark, implementation, or activation.
  - Reusing a shorter-distance numeric rule or treating a cohort label as a permanent runner identity.

<details><summary>Traceability: 5 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `road_marathon_activation_and_dependency`, `road_marathon_goal_and_event_tuple`, `road_marathon_supported_training_pattern`, `road_marathon_modular_policy_structure`, `road_marathon_typed_outcomes_and_suggestion_only_state`
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `eligibility.masters-age-change-not-automatic-exclusion`, `road-marathon.task-specific-capability-baseline-multifactorial`

</details>

#### `evidence-use` — Accept bounded use of population findings and uncertainty

- **Question:** Should the reviewed marathon and broader-endurance findings be retained only as source findings, qualitative context, and future validation inputs rather than personal probabilities or causal prescriptions?
- **Proposed decision:** Retain the observed prediction error, volume and longest-run associations, durability, training-intensity distribution, taper, carbohydrate, gut-tolerance, fluid, sodium, environment, and altitude findings with their directness and uncertainty labels.
- **Approval means:**
  - Published findings may appear in review notes, source explanations, and validation design.
  - Outcome comparisons remain descriptive and require comparable protocols and context.
- **This does not authorize:**
  - Turning any reported category, coefficient, percentage, correlation, or subgroup observation into an individual rule.
  - A personal success, injury, safety, responder, hydration, fueling, or environmental probability.

<details><summary>Traceability: 8 contract groups, 11 evidence claims</summary>

- **Contract groups covered:** `road_marathon_published_volume_and_long_run_findings`, `road_marathon_published_durability_findings`, `road_marathon_published_intensity_distribution_findings`, `road_marathon_published_taper_findings`, `road_marathon_published_fueling_and_gut_findings`, `road_marathon_published_fluid_and_sodium_findings`, `road_marathon_published_environment_and_altitude_findings`, `road_marathon_reassessment_and_outcome_policy`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-marathon.volume-frequency-longest-run-associative`, `road-marathon.durability-relevant-no-field-cutoff`, `road-marathon.marathon-tid-mostly-low-observational`, `road-marathon.taper-support-exact-parameters-uncertain`, `road-marathon.pacing-prediction-retains-individual-error`, `road-marathon.carbohydrate-support-contextual`, `road-marathon.gut-training-tolerance-not-universal`, `road-marathon.fluid-sodium-needs-variable`, `road-marathon.altitude-capacity-no-personal-correction`, `environment.no-universal-personal-correction`

</details>

#### `hard-boundaries` — Accept hard control, consent, data, and automation boundaries

- **Question:** Should every future proposal remain athlete-editable and explicitly adopted, with no automatic maximal marathon test, target-gap escalation, catch-up, activity-average-power intensity analysis, hidden demographic default, unconfirmed imported context, or AI authority expansion?
- **Proposed decision:** Accept those prohibitions. Require direct confirmed capability, source-labelled inputs, activity splits or samples for intensity, deterministic validation, symptom stops, minimum-necessary data, and separate evidence, decision, implementation, and activation authority.
- **Approval means:**
  - Missing module-specific context disables or degrades only the dependent module rather than blocking otherwise eligible independent plan modules.
  - Eligibility, safety, capability, history, or unresolved event conflicts may still produce a typed no-plan result.
  - AI may explain reviewable inputs but cannot choose unresolved values, approve, activate, adopt, deliver, or publish.
  - Athlete constraints and consent remain authoritative.
- **This does not authorize:**
  - Any unresolved numeric or algorithmic value in the same contract groups.
  - Medical diagnosis, treatment, clearance, sensitive inference, or a safety guarantee.

<details><summary>Traceability: 12 contract groups, 7 evidence claims</summary>

- **Contract groups covered:** `road_marathon_profile_and_source_provenance`, `road_marathon_direct_baseline_hierarchy`, `road_marathon_readiness_and_history_qualification`, `road_marathon_history_anchored_load_policy`, `road_marathon_long_run_and_durability_policy`, `road_marathon_intensity_and_race_specific_policy`, `road_marathon_taper_and_recovery_policy`, `road_marathon_fueling_and_hydration_policy`, `road_marathon_environment_and_altitude_policy`, `road_marathon_reassessment_and_outcome_policy`, `road_marathon_typed_outcomes_and_suggestion_only_state`, `road_marathon_validation_privacy_and_open_decisions`
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `eligibility.current-symptoms-support-stop-not-clearance`, `eligibility.evidence-quality-no-personal-probability`, `road-marathon.task-specific-capability-baseline-multifactorial`, `road-marathon.pacing-prediction-retains-individual-error`, `road-marathon.fluid-sodium-needs-variable`, `heat-safety.separate-from-adaptation`

</details>

#### `adaptive-evidence-informed-loop` — Accept an actionable individualized recommendation and feedback loop

- **Question:** Should V1 require Praxys to take an actionable, science-grounded position for a supported safe route, treat theories and findings as candidate strategies rather than universal rules, and use athlete feedback and observed outcomes to reassess later recommendations?
- **Proposed decision:** Require a future supported implementation to recommend what the athlete should do next, explain why it fits the athlete and which evidence applies, state the expected response and uncertainty, and ask for the feedback needed for reassessment. Use mostly-low organization, durability, fueling practice, and environmental findings as candidate context rather than mandatory templates. Preserve safety stops while prohibiting disclaimer-only output for a supported safe route.
- **Approval means:**
  - A supported safe route must return an actionable recommendation, athlete-specific rationale, expected signal, uncertainty, and feedback request.
  - Scientific theories and findings may bound and rank candidate strategies but may not become permanent runner identities or universal personal rules.
  - Completed training, adherence, edits, rejection, reported response, recovery, symptoms, and comparable outcomes must be available to reassess the next proposal.
  - Safety boundaries may pause or narrow a recommendation, but ordinary uncertainty may not replace product value with disclaimers.
- **This does not authorize:**
  - A fixed intensity distribution, mandatory mostly-low pattern, exact strategy-selection or feedback-update algorithm, race-specific workout, or distance-only nutrition rule.
  - Ungoverned online learning, a causal responder label, medical treatment, personal environmental correction, acclimation schedule, or safety guarantee.

<details><summary>Traceability: 13 contract groups, 10 evidence claims</summary>

- **Contract groups covered:** `road_marathon_modular_policy_structure`, `road_marathon_published_durability_findings`, `road_marathon_long_run_and_durability_policy`, `road_marathon_published_intensity_distribution_findings`, `road_marathon_intensity_and_race_specific_policy`, `road_marathon_published_fueling_and_gut_findings`, `road_marathon_fueling_and_hydration_policy`, `road_marathon_published_fluid_and_sodium_findings`, `road_marathon_published_environment_and_altitude_findings`, `road_marathon_environment_and_altitude_policy`, `road_marathon_reassessment_and_outcome_policy`, `road_marathon_typed_outcomes_and_suggestion_only_state`, `road_marathon_validation_privacy_and_open_decisions`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-marathon.durability-relevant-no-field-cutoff`, `road-marathon.marathon-tid-mostly-low-observational`, `road-marathon.pacing-prediction-retains-individual-error`, `road-marathon.carbohydrate-support-contextual`, `road-marathon.gut-training-tolerance-not-universal`, `road-marathon.fluid-sodium-needs-variable`, `road-marathon.altitude-capacity-no-personal-correction`, `environment.heat-balance-multifactor`, `heat-adaptation.repeated-exposure`

</details>

### Decisions explicitly deferred

#### `defer-baseline-history` — Defer qualification, freshness, history counts, and capability algorithm

- **Question:** Should exact direct-result qualification, freshness, distance and event validation, lookback, minimum history counts, and current-load qualification remain unresolved?
- **Proposed decision:** Keep every baseline and history algorithm unaccepted until a later decision compares options, missingness, and validation consequences.
- **Approval means:**
  - Missing or unconfirmed capability returns capability_confirmation_required.
  - Insufficient stable recent history returns insufficient_history.
- **This does not authorize:**
  - A result expiry, distance tolerance, event qualification rule, minimum week or run count, or automatic maximal marathon test.
  - A shorter-distance conversion as direct current marathon capability.

<details><summary>Traceability: 2 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `road_marathon_direct_baseline_hierarchy`, `road_marathon_readiness_and_history_qualification`
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.goal-relevant-current-capability-task-specific`, `road-marathon.task-specific-capability-baseline-multifactorial`, `road-marathon.pacing-prediction-retains-individual-error`

</details>

#### `defer-dose-specific-work` — Defer plan length, dose, long-run, intensity, and race-specific work

- **Question:** Should plan length, frequency, progression, volume, long-run distance/duration/share/cap, durability cutoff, marathon-pace or race-specific work, quality ceiling and spacing, exact workouts, strategy selection, and feedback-driven update rules remain unresolved?
- **Proposed decision:** Keep every dose, schedule, strategy-selection, and feedback-update value unaccepted. Retain the approved individualized recommendation loop and hard prohibitions without pretending the exact algorithm has been selected.
- **Approval means:**
  - A future decision must select and validate each behavior-driving value and adaptation rule explicitly.
  - Target gap and missed sessions cannot create escalation or catch-up.
- **This does not authorize:**
  - A plan horizon, weekly frequency or volume, progression, long-run prescription, quality count, spacing, session mix, workout template, or hidden adaptation rule.
  - A mandatory mostly-low pattern, durability score, or activity-average-power intensity rule.

<details><summary>Traceability: 3 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `road_marathon_history_anchored_load_policy`, `road_marathon_long_run_and_durability_policy`, `road_marathon_intensity_and_race_specific_policy`
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `road-marathon.volume-frequency-longest-run-associative`, `road-marathon.durability-relevant-no-field-cutoff`, `road-marathon.marathon-tid-mostly-low-observational`

</details>

#### `defer-taper-recovery` — Defer taper, event accounting, recovery, and reassessment cadence

- **Question:** Should taper window and reduction, intensity and frequency handling, short-horizon alternative, event-minute accounting, recovery spacing, reassessment cadence, and fixed outcome windows remain unresolved?
- **Proposed decision:** Keep exact taper, recovery, reassessment, and outcome timing unaccepted while preserving the no-makeup and post-event reassessment boundaries.
- **Approval means:**
  - A completed marathon triggers reassessment without claiming general readiness.
  - Observational taper effects remain source findings only.
- **This does not authorize:**
  - A three-week taper prescription, fixed percentage reduction, recovery interval, event-minute formula, or meaningful-change window.
  - Treating renal recovery as medical clearance or general training readiness.

<details><summary>Traceability: 2 contract groups, 2 evidence claims</summary>

- **Contract groups covered:** `road_marathon_taper_and_recovery_policy`, `road_marathon_reassessment_and_outcome_policy`
- **Evidence claims:** `road-marathon.taper-support-exact-parameters-uncertain`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`

</details>

#### `defer-fueling-hydration-environment` — Defer fueling, hydration, environmental, and altitude values

- **Question:** Should loading, duration, intake, fluid, sodium, gut-training numbers and prompts, plus environmental and altitude corrections and acclimation schedules, remain unresolved?
- **Proposed decision:** Keep every behavior-driving nutrition, hydration, environmental, and altitude value unaccepted. Require practiced context and complete environmental inputs before any future dependent suggestion, while preserving independent plan modules when that context is missing.
- **Approval means:**
  - Missing fueling context returns fueling_module_limited while otherwise eligible independent plan modules remain available.
  - Missing material environmental context returns environment_module_limited while otherwise eligible independent plan modules remain available.
- **This does not authorize:**
  - A distance-only intake, fluid, sodium, loading, sweat, or gut-training rule.
  - A personal pace correction, finish-time correction, or altitude acclimation schedule.

<details><summary>Traceability: 2 contract groups, 8 evidence claims</summary>

- **Contract groups covered:** `road_marathon_fueling_and_hydration_policy`, `road_marathon_environment_and_altitude_policy`
- **Evidence claims:** `road-marathon.carbohydrate-support-contextual`, `road-marathon.gut-training-tolerance-not-universal`, `road-marathon.fluid-sodium-needs-variable`, `road-marathon.altitude-capacity-no-personal-correction`, `environment.full-wbgt-inputs`, `environment.no-universal-personal-correction`, `heat-adaptation.repeated-exposure`, `heat-safety.separate-from-adaptation`

</details>

#### `defer-secondary-rollout` — Defer target risk, race density, subgroup, outcomes, pilot, implementation, and activation

- **Question:** Should target-risk thresholds, race-density and priority rules, subgroup dose modifiers, outcome windows and meaningful-change thresholds, pilot criteria, implementation mapping, and activation remain unresolved?
- **Proposed decision:** Keep the contract inactive and require separate human review of every secondary rule, deterministic implementation mapping, and opt-in pilot threshold before runtime use.
- **Approval means:**
  - Deterministic invariant and replay tolerance remain zero.
  - Every statistical, subgroup, event-density, outcome, implementation, and activation choice remains explicit future work.
- **This does not authorize:**
  - Implementing unresolved values, advertising capability, starting a pilot, or activating any runtime surface.
  - Treating science decision approval as implementation or activation approval.

<details><summary>Traceability: 3 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `road_marathon_supported_training_pattern`, `road_marathon_reassessment_and_outcome_policy`, `road_marathon_validation_privacy_and_open_decisions`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `eligibility.masters-age-change-not-automatic-exclusion`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve the narrow currently-capable adult outdoor road-marathon performance scope, bounded evidence use, hard suggestion-only and athlete-control boundaries, and an actionable individualized evidence-informed recommendation loop. Scientific theories and findings are candidate strategies and priors rather than universal personal rules; mostly-low organization is not mandatory. Athlete feedback and observed outcomes must inform reassessment of later recommendations. Missing fueling, hydration, or environmental context degrades only the dependent module rather than blocking independent plan modules. I agree that baseline and history qualification, all dose, strategy-selection, feedback-update and race-specific work, taper and recovery, fueling, hydration and environment numbers, and secondary rollout choices remain deferred. This approval would not approve implementation, runtime activation, a plan length, or any unresolved value.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-road-marathon-plan-generation-policy-v1`
- Digest: `sha256:ffb7864995d0825713667c816f5d4c1255695fdf579857ca79c24e91c63c50f0`

> I approve the narrow currently-capable adult outdoor road-marathon performance scope, bounded evidence use, hard suggestion-only and athlete-control boundaries, and an actionable individualized evidence-informed recommendation loop. Scientific theories and findings are candidate strategies and priors rather than universal personal rules; mostly-low organization is not mandatory. Athlete feedback and observed outcomes must inform reassessment of later recommendations. Missing fueling, hydration, or environmental context degrades only the dependent module rather than blocking independent plan modules. I agree that baseline and history qualification, all dose, strategy-selection, feedback-update and race-specific work, taper and recovery, fueling, hydration and environment numbers, and secondary rollout choices remain deferred. This approval would not approve implementation, runtime activation, a plan length, or any unresolved value.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:ffb7864995d0825713667c816f5d4c1255695fdf579857ca79c24e91c63c50f0","subject_id":"sdr-road-marathon-plan-generation-policy-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If accepted by a digest-bound human decision approver, this SDR would authorize only an inactive policy boundary for adults aged 18 years or older with current direct outdoor road-marathon capability, stable recent history that anchors their own exposure, within-recent load, performance intent, optional target time or date, and athlete-confirmed event context. Goal capture remains independent from generator availability. Missing optional age, sex, or profile modifiers disable only dependent adjustments and never default to male; imported profile and event data remain source-labelled until athlete confirmation. The proposed policy is suggestion-only and modular: entry/readiness; history/load; long-run/durability; intensity/race-specific work; fueling/hydration practice; taper/recovery; environment/altitude; and reassessment/outcomes. Missing fueling, hydration, or environmental context disables or degrades only the dependent module and does not block otherwise eligible independent plan modules. For a supported safe route, a future implementation must take an actionable position rather than return disclaimer-only output. It must use applicable scientific theories and findings as bounded candidate strategies and initial priors, select and explain a proposal from the athlete's confirmed current data, and observe athlete feedback and outcomes before reassessing the next proposal. Population associations and source findings may support that reasoning and validation but not personal probability, causal dose, or target-gap escalation. No plan length, baseline algorithm, history count, weekly frequency, progression, volume, long-run dose, intensity distribution, strategy-selection or feedback-update algorithm, race-specific dose, workout, taper, recovery, fueling, hydration, environment, altitude, race-density, subgroup, outcome, pilot, implementation, or activation rule is selected. No 5 km, 10 km, or half-marathon numeric rule is inherited. This proposal does not authorize first-marathon or completion intent, sparse history, returning, clinical, rehabilitation, pregnancy-specific, trail, ultra, or unsupported contexts. A no-event rolling preparation or simulation route requires a separately accepted completion or benchmark policy and may not invent an automatic maximal marathon simulation.

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

#### `road-marathon.task-specific-capability-baseline-multifactorial` — low

Road-marathon capability and performance are multifactorial. Recent athlete-confirmed same-task history is the most direct available baseline for this policy, while anthropometric, training, physiological, pacing, and course-specific models retain unexplained variation and do not establish one universal qualification threshold.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `nikolaidis-2021-athens-marathon`, `schmid-2012-female-marathon`, `salinero-2017-marathon-prediction`, `swain-2020-marathon-pacing`
- **Limitations:** Prediction models do not establish causal training prescriptions or eligibility cutoffs.; The Athens model is male, single-course, and internally split rather than externally generalizable.; The female model includes 29 runners and does not establish a general threshold.; Same-task history can still be stale, contextually different, or incomplete.

#### `road-marathon.volume-frequency-longest-run-associative` — moderate

Weekly volume, training frequency, and longest-run exposure are associated with marathon performance and pacing, but the reviewed observational evidence does not validate exact individual weekly volume, frequency, longest-run, progression, or safety prescriptions.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `fokkema-2020`, `swain-2020-marathon-pacing`
- **Limitations:** Training exposure was observational and partly self-reported.; Categories do not establish causality, optimality, progression, or injury safety.; A longest run above 35 kilometres was not significantly better than 30 to 35 kilometres in the reviewed cohort.; Associations cannot be converted into entry gates or individual dose.

#### `road-marathon.durability-relevant-no-field-cutoff` — very_low

Fatigue resistance and running-economy durability are relevant marathon concepts, and one small cross-sectional male study associated regular long runs and higher volume with less running-economy deterioration. The evidence does not validate a standardized product-ready field, protocol, cutoff, or mandatory long-run rule.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `zanini-2026-durability`
- **Limitations:** Cross-sectional design cannot establish that changing volume or long runs causes improved durability.; The sample included 26 men and does not validate subgroup transfer.; The abstract does not provide a product-ready field-test qualification rule.

#### `road-marathon.marathon-tid-mostly-low-observational` — low

Direct marathon training-intensity-distribution data describe greater zone-one volume among faster runners and pyramidal organization in more than 80 percent of the fastest group across 151,813 marathons from 119,452 runners. The observational, zone-definition-dependent analysis does not establish an individual low-intensity percentage, session count, spacing rule, race-specific dose, or causal optimum.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `muniz-pumares-2025-marathon-tid`
- **Limitations:** Observational training data cannot establish causal superiority.; Zone definitions and data quality affect classification.; Performance groups are evidence cohorts rather than permanent runner identities.; Abstract-bounded extraction cannot support exact schedule parameters.

#### `road-marathon.taper-support-exact-parameters-uncertain` — moderate

Disciplined pre-race volume reduction is associated with better marathon performance, while mixed-endurance taper evidence more strongly supports reduced volume with maintained intensity and frequency. Exact marathon taper window, reduction, intensity exposure, frequency, accounting, and personal benefit remain uncertain.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `smyth-lawlor-2021`, `hug-2014-marathon-taper`, `wang-2023`
- **Limitations:** The marathon taper study is observational and cannot prove a fixed benefit.; Mixed sports and distances make the meta-analysis indirect to road-marathon automation.; Autonomic findings do not select a performance taper template.; No source validates one personal taper percentage or guaranteed gain.

#### `road-marathon.pacing-prediction-retains-individual-error` — low

Marathon pacing and prediction models retain material individual error. Raw-training critical-speed estimation did not prove that source sessions were maximal, and model output cannot create a personal success probability or justify target-gap dose escalation.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `smyth-muniz-pumares-2020`, `nikolaidis-2021-athens-marathon`, `schmid-2012-female-marathon`, `salinero-2017-marathon-prediction`, `swain-2020-marathon-pacing`
- **Limitations:** Models use different populations, courses, inputs, and validation approaches.; Raw sessions were not proven maximal efforts.; Group error does not calibrate one athlete's success probability.; Prediction does not establish readiness, safety, or a training dose.

#### `road-marathon.carbohydrate-support-contextual` — moderate

Acute carbohydrate feeding supports prolonged endurance performance at population level, but loading and during-exercise intake depend on event duration, practiced tolerance, feeding opportunity, environment, and athlete context. The marathon distance label alone does not validate an exact personal loading or intake rule.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `ramos-campo-2024`, `burke-2011`, `podlogar-2022`
- **Limitations:** Protocols, exercise duration, carbohydrate form, and baseline nutrition vary.; Broader endurance evidence is not a marathon-only prescription.; Population ergogenic effects do not establish an individual minimum, maximum, or guarantee.

#### `road-marathon.gut-training-tolerance-not-universal` — low

Repeated feeding practice or gut-training may reduce gastrointestinal discomfort and carbohydrate malabsorption in some endurance athletes, but protocols are heterogeneous and no universal schedule, dose, guaranteed adaptation, or race-day tolerance exists.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `martinez-2023`, `podlogar-2022`
- **Limitations:** Few heterogeneous protocols support the numeric findings.; Tolerance improvement is not guaranteed and may not transfer to race context.; No source selects one automated marathon gut-training protocol.

#### `road-marathon.fluid-sodium-needs-variable` — moderate

Fluid and sodium needs vary within and between athletes and contexts. Both inadequate replacement and overdrinking matter, including exercise-associated hyponatremia risk. No distance-only millilitres-per- hour, sodium, body-mass-loss, or replacement rule is safe or validated for individualized marathon automation.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `mcdermott-2017-fluid`, `hew-butler-2015-eah`, `baker-2017-sweat`
- **Limitations:** Position and consensus statements bound safety but do not validate one product prescription.; Sweat rate and sodium concentration vary by method, athlete, environment, and acclimation.; Medical diagnosis and treatment remain outside this performance policy.

#### `road-marathon.altitude-capacity-no-personal-correction` — moderate

Acute altitude reduces aerobic capacity and fixed-speed endurance in controlled conditions, while hypoxic adaptation evidence does not validate an individualized marathon altitude correction or acclimation schedule. Chamber findings must not be converted into a personal race time or pace adjustment.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `wehrlin-2006-altitude`, `bonetti-hopkins-2009`
- **Limitations:** Fixed-speed time to exhaustion is not self-paced marathon performance.; Acute chamber exposure does not define race-course altitude effects.; The hypoxia meta-analysis does not select an individual marathon acclimation schedule.

#### `road-marathon.recovery-subgroup-outcome-rules-unvalidated` — very_low

Post-marathon recovery, subgroup-specific dose changes, race-density thresholds, and fixed outcome windows remain unvalidated for automation. Renal recovery findings after a marathon concern one physiological domain and do not establish general readiness, workout spacing, or medical clearance.

- **Evidence Review:** `evidence-road-marathon-plan-generation-policy-v1`
- **Sources:** `hernando-2022-marathon-recovery`, `schmid-2012-female-marathon`, `fokkema-2020`
- **Limitations:** Renal recovery is not a general readiness measure.; Prediction and observational cohort differences do not establish subgroup dose modifiers.; No reviewed source validates one race-priority threshold, reassessment cadence, or meaningful-change window.

#### `environment.heat-balance-multifactor` — high

Exercise heat balance depends on air temperature, ambient water-vapor pressure, air movement, radiant load, clothing, body characteristics, and metabolic heat production; no single weather value captures all pathways.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `cramer-jay-2016`, `periard-2021`
- **Limitations:** Reviews synthesize mechanisms rather than one field-effect coefficient; Actual heat transfer depends on clothing, posture, morphology, and work rate

#### `environment.relative-humidity-insufficient` — high

Relative humidity must be interpreted with air temperature because evaporative capacity depends on the water-vapor pressure gradient between skin and ambient air; relative humidity alone is not a complete measure of evaporative constraint.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `cramer-jay-2016`, `periard-2021`
- **Limitations:** Field magnitude still depends on wind, clothing, sweating, and metabolic heat

#### `environment.wbgt-population-performance` — moderate

In 1,258 elite endurance races, WBGT predicted performance better than air temperature alone; the observed optimal WBGT and performance slopes are population and discipline associations, not personal correction factors.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `mantzios-2022`
- **Limitations:** Observational decision-tree analysis does not establish causality; Weather stations averaged 8.9 km from venues with substantial variation; Results differ by discipline and should not be applied to trail, cycling, or intervals without validation

#### `environment.temperature-nonlinear` — moderate

Across roughly 1.79 million marathon performances, the temperature-performance relationship was nonlinear, optimal temperature differed by performance level, and slowing and withdrawals increased above the optimum.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `el-helou-2012`
- **Limitations:** Observational race-level evidence; Single race-time weather measurements do not capture within-race variation; Separate factor analyses may not resolve temperature-humidity interactions; Road-marathon findings are not a universal training or trail correction

#### `environment.marathon-wbgt-performance-level` — moderate

Across seven North American marathons, performance slowed progressively as race-level WBGT increased from 5 to 25 degrees C, and slower finishing populations were affected more than faster runners; these are population-level road-marathon associations, not personal corrections.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `ely-2007`
- **Limitations:** Retrospective observational race analysis cannot establish an individual causal effect; Place-based groups are not matched personal observations; PubMed abstract checked; full text was not reviewed in this rapid review; The result must not become a universal pace coefficient or counterfactual finish time

#### `environment.full-wbgt-inputs` — high

A validated outdoor WBGT model requires air temperature, moisture or dew point, wind speed, solar radiation, and the required pressure assumptions to model natural wet-bulb and globe temperatures; temperature and relative humidity alone are insufficient.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `liljegren-2008`
- **Limitations:** Solar radiation and wind inputs are not always available; Validation sites were primarily U.S. industrial locations; WBGT context does not prove an individual performance or illness response

#### `environment.no-universal-personal-correction` — moderate

Environmental performance effects vary by discipline, performance level, acclimation, and data method; the reviewed evidence does not support one universal personal heat-adjustment coefficient.

- **Evidence Review:** `evidence-environmental-performance-v1`
- **Sources:** `mantzios-2022`, `el-helou-2012`, `baillot-2021`
- **Limitations:** Absence of a universal coefficient does not rule out validated discipline-specific or personal models

#### `heat-adaptation.repeated-exposure` — high

Repeated exercise-heat exposure over roughly one to two weeks produces meaningful thermoregulatory, cardiovascular, perceptual, and performance adaptations; protocol duration and response magnitude vary.

- **Evidence Review:** `evidence-heat-adaptation-v1`
- **Sources:** `nielsen-1993`, `racinais-2015`, `tyler-2016`, `kelly-2023`
- **Limitations:** Protocols and environmental conditions are heterogeneous; Evidence remains predominantly male despite newer female-specific synthesis; A population protocol does not confirm adaptation in one athlete; No included source validates a wearable-derived exposure score

#### `heat-safety.separate-from-adaptation` — moderate

Evidence of prior adaptation is not medical clearance or a current heat-illness risk assessment; exertional heat-illness prevention, recognition, immediate cooling, and emergency response require separate safety guidance.

- **Evidence Review:** `evidence-heat-adaptation-v1`
- **Sources:** `casa-2015`
- **Limitations:** Clinical position statement rather than a performance study; The 2017 erratum must be consulted before using corrected numeric details

### Reviewed parameters

#### `road_marathon_activation_and_dependency` — guardrail

- **Applies to:** policy lifecycle and capability discovery
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Draft records, generated packets, and a science decision cannot activate product behavior. Evidence, decision, implementation, and runtime authority remain distinct.
- **Exact value:**

```json
{
  "active_behavior": false,
  "capability_registry_entry_default_enabled": false,
  "decision_approval_artifact_required": true,
  "distance_decision_required_status_before_activation": "accepted",
  "distance_evidence_required_status_before_activation": "accepted",
  "evidence_review_approval_artifact_required": true,
  "generator_api_web_miniapp_plugin_and_mcp_activation_in_this_record": false,
  "implementation_approval_artifact_required": true,
  "runtime_state": "inactive",
  "shared_policy_dependency": {
    "required_status_before_activation": "accepted",
    "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
  }
}
```

#### `road_marathon_goal_and_event_tuple` — guardrail

- **Applies to:** goal normalization and marathon policy selection
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `road-marathon.task-specific-capability-baseline-multifactorial`
- **Rationale:** Goal choice is durable user state. This policy is a narrow capability, intent, surface, and evidence route rather than the definition of a valid goal.
- **Exact value:**

```json
{
  "event_context_must_be_athlete_confirmed": true,
  "goal_capture_independent_from_generator_availability": true,
  "goal_intent": "performance",
  "goal_kind": "distance_marathon",
  "no_event_goal": {
    "automatic_maximal_marathon_simulation": "prohibited",
    "goal_remains_recorded": true,
    "rolling_preparation_or_simulation_requires_separately_accepted_completion_or_benchmark_policy": true
  },
  "primary_outcome": "elapsed_time",
  "separate_policy_variants": [
    "first_marathon_or_completion_intent",
    "sparse_or_missing_history",
    "returning_after_interruption",
    "clinical_rehabilitation_or_return_to_sport",
    "pregnancy_specific_planning",
    "trail_marathon",
    "ultramarathon",
    "unsupported_surface_event_or_context"
  ],
  "sport": "running",
  "surface": "outdoor_road",
  "target_date_optional": true,
  "target_time_optional": true,
  "unavailable_policy_result": "goal_recorded_plan_policy_unavailable"
}
```

#### `road_marathon_supported_training_pattern` — guardrail

- **Applies to:** shared eligibility and distance-policy routing
- **Evidence claims:** `eligibility.current-symptoms-support-stop-not-clearance`, `eligibility.masters-age-change-not-automatic-exclusion`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`
- **Rationale:** The route matches a time-bounded evidence pattern rather than a permanent recreational, amateur, female, male, faster, elite, or masters identity.
- **Exact value:**

```json
{
  "adult_scope": "confirmed",
  "capability_pattern": "current_direct_outdoor_road_marathon",
  "cohort_labels_are_permanent_runner_identities": false,
  "current_concerning_symptoms": "absent",
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
    "capability_unconfirmed",
    "first_marathon_or_completion_intent",
    "sparse_interrupted_or_missing_history",
    "outside_recent_load_pattern",
    "current_injury_illness_or_concerning_symptoms",
    "clinical_rehabilitation_return_to_sport_or_medical_clearance",
    "pregnancy_specific_prescription",
    "unresolved_material_event_conflict",
    "unsupported_surface_distance_or_intent"
  ],
  "history_pattern": "stable_recent",
  "intent_pattern": "performance",
  "load_pattern": "within_recent",
  "race_dense_requires_resolved_conflicts": true
}
```

#### `road_marathon_profile_and_source_provenance` — guardrail

- **Applies to:** profile, event, and missing-data handling
- **Evidence claims:** `eligibility.masters-age-change-not-automatic-exclusion`, `eligibility.evidence-quality-no-personal-probability`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`
- **Rationale:** Optional modifiers cannot become hidden demographic assumptions or unnecessary eligibility barriers. Athlete confirmation and field-level provenance preserve accuracy and control.
- **Exact value:**

```json
{
  "adult_scope_confirmation_required": true,
  "imported_profile_and_event_fields": {
    "may_not_overwrite_athlete_confirmed_value": true,
    "missing_is_unknown_not_false": true,
    "remain_source_labelled_until_athlete_confirmation": true
  },
  "minimum_necessary_inputs_only": true,
  "missing_optional_modifier_effect": "disable_dependent_adjustment_only",
  "optional_modifier_fields": [
    "age_or_age_band",
    "sex",
    "profile_attributes",
    "prior_marathon_count",
    "environmental_history",
    "fueling_and_gastrointestinal_history"
  ],
  "unknown_sex_defaults_to_male": false
}
```

#### `road_marathon_direct_baseline_hierarchy` — guardrail

- **Applies to:** direct capability confirmation
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `road-marathon.task-specific-capability-baseline-multifactorial`, `road-marathon.pacing-prediction-retains-individual-error`
- **Rationale:** Same-task confirmed history is most direct. Predictions and supporting markers retain material individual error and cannot silently qualify a runner or trigger a maximal marathon effort.
- **Exact value:**

```json
{
  "accepted_assistance_statuses": "not_accepted",
  "accepted_event_qualification": "not_accepted",
  "automatic_maximal_marathon_baseline_test": "prohibited",
  "baseline_freshness_completed_days": "not_accepted",
  "baseline_qualification_algorithm": "not_accepted",
  "direct_current_capability_required": true,
  "distance_match_tolerance_m": "not_accepted",
  "excluded_as_direct": [
    "shorter_distance_conversion",
    "critical_speed_prediction",
    "passive_marathon_segment_within_ultra",
    "unconfirmed_provider_personal_best",
    "activity_average_power",
    "vendor_readiness_or_race_score",
    "policy_generated_maximal_marathon_simulation"
  ],
  "missing_or_unconfirmed_outcome": "capability_confirmation_required",
  "preferred_direct_evidence": [
    "athlete_confirmed_official_or_organized_outdoor_road_marathon_result"
  ],
  "required_metadata": [
    "completed_at",
    "elapsed_time_seconds",
    "measured_distance_m",
    "route_or_event_identifier",
    "surface",
    "assistance_status",
    "source_provider",
    "athlete_confirmation_state"
  ],
  "supporting_only": [
    "shorter_distance_race_result",
    "critical_speed_or_threshold",
    "current_vo2max_or_vvo2max",
    "weekly_training_volume_and_frequency",
    "recent_longest_run",
    "marathon_prediction_with_error",
    "split_or_sample_pacing_distribution"
  ]
}
```

#### `road_marathon_readiness_and_history_qualification` — guardrail

- **Applies to:** readiness and history-rich qualification
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.fixed-progression-and-acwr-not-safety-laws`, `road-marathon.volume-frequency-longest-run-associative`
- **Rationale:** Recent history must anchor the athlete's own exposure, but the literature does not establish universal counts or a safe-load algorithm. Intensity requires split-level or sample-level evidence.
- **Exact value:**

```json
{
  "disallowed_intensity_source": [
    "activity_avg_power"
  ],
  "exact_history_lookback_weeks": "not_accepted",
  "insufficient_history_outcome": "insufficient_history",
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
    "recovery_and_symptom_stop_state"
  ],
  "stable_history_qualification_algorithm": "not_accepted",
  "within_recent_load_qualification_algorithm": "not_accepted"
}
```

#### `road_marathon_modular_policy_structure` — guardrail

- **Applies to:** policy composition and review
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`
- **Rationale:** Modular boundaries keep missing context and unaccepted values local and visible. They prevent one opaque schedule from hiding unsupported behavior.
- **Exact value:**

```json
{
  "disclaimer_only_output_allowed_for_supported_safe_route": false,
  "each_module_must_declare": [
    "required_inputs",
    "missingness_effect",
    "evidence_or_guardrail_provenance",
    "athlete_editability",
    "typed_outcome"
  ],
  "feedback_loop_stages": [
    "sense_current_state",
    "select_candidate_strategy",
    "propose_reviewable_action",
    "athlete_review_edit_reject_or_adopt",
    "observe_completion_response_and_outcome",
    "reassess_next_recommendation"
  ],
  "missing_context_disables_or_degrades_dependent_module_only": true,
  "missing_context_may_block_independent_modules": false,
  "modules": [
    "entry_readiness",
    "history_load",
    "long_run_durability",
    "intensity_race_specific_work",
    "fueling_hydration_practice",
    "taper_recovery",
    "environment_altitude",
    "reassessment_outcomes"
  ],
  "plan_length_selected": false,
  "recommendation_must_declare": [
    "next_action",
    "athlete_specific_rationale",
    "scientific_basis_and_applicability",
    "expected_response_or_signal",
    "uncertainty",
    "feedback_needed_for_reassessment"
  ],
  "scientific_evidence_roles": [
    "bound_candidate_strategies",
    "inform_initial_prior",
    "explain_athlete_specific_recommendation",
    "define_expected_and_contradictory_signals"
  ],
  "supported_route_must_take_actionable_position": true,
  "unresolved_dependent_module_preserves_goal_record": true,
  "unresolved_module_cannot_be_filled_by_another_distance_policy": true
}
```

#### `road_marathon_published_volume_and_long_run_findings` — published

- **Applies to:** evidence display and future validation design
- **Evidence claims:** `road-marathon.volume-frequency-longest-run-associative`
- **Rationale:** These values reproduce source findings for explanation and validation. They are not minima, maxima, targets, safe thresholds, or causal doses.
- **Exact value:**

```json
{
  "eligibility_or_prescription_established": false,
  "frequency_and_experience_association_descriptive_only": true,
  "longest_run_findings": {
    "above_35_km_vs_30_to_35": {
      "significantly_better": false
    },
    "below_25_km": {
      "confidence_interval_minutes": {
        "high": 21.55,
        "low": 5.34
      },
      "finish_time_coefficient_minutes": 13.44
    }
  },
  "observational_only": true,
  "study_population": "adult_recreational_marathon_entrants",
  "weekly_volume_findings": {
    "above_65_km_per_week_vs_40_to_65": {
      "confidence_interval_minutes": {
        "high": -5.72,
        "low": -22.47
      },
      "finish_time_coefficient_minutes": -14.09
    },
    "below_40_km_per_week_vs_40_to_65": {
      "confidence_interval_minutes": {
        "high": 12.48,
        "low": 0.18
      },
      "finish_time_coefficient_minutes": 6.33
    }
  }
}
```

#### `road_marathon_history_anchored_load_policy` — guardrail

- **Applies to:** plan horizon and weekly exposure
- **Evidence claims:** `eligibility.fixed-progression-and-acwr-not-safety-laws`, `road-marathon.volume-frequency-longest-run-associative`, `road-marathon.pacing-prediction-retains-individual-error`
- **Rationale:** Population associations and prediction error do not choose an individual plan length, frequency, volume, or progression. Athlete constraints cap future suggestions but do not prove an optimal dose.
- **Exact value:**

```json
{
  "acwr_prescription_zone_used": false,
  "athlete_availability_is_hard_cap": true,
  "current_load_comparison_method": "not_accepted",
  "missed_workout_catch_up_allowed": false,
  "plan_length_days": "not_accepted",
  "shorter_distance_numeric_rules_inherited": false,
  "target_gap_may_raise_load": false,
  "ten_percent_rule_used": false,
  "weekly_progression_rule": "not_accepted",
  "weekly_running_frequency_range": "not_accepted",
  "weekly_volume_target_or_range": "not_accepted"
}
```

#### `road_marathon_published_durability_findings` — published

- **Applies to:** durability evidence context
- **Evidence claims:** `road-marathon.durability-relevant-no-field-cutoff`
- **Rationale:** The values are descriptive source findings from a small male cross-sectional sample and cannot define an automated cutoff or dose.
- **Exact value:**

```json
{
  "causal_or_field_cutoff_established": false,
  "design": "cross_sectional",
  "longest_run_correlation_with_deterioration": -0.67,
  "running_economy_deterioration_percent": {
    "better_durability_group": 3.1,
    "lower_durability_group": 6.0
  },
  "study_population": "26_performance_matched_well_trained_men",
  "training_volume_correlation_with_deterioration": -0.48
}
```

#### `road_marathon_long_run_and_durability_policy` — guardrail

- **Applies to:** long-run and durability module
- **Evidence claims:** `road-marathon.volume-frequency-longest-run-associative`, `road-marathon.durability-relevant-no-field-cutoff`
- **Rationale:** Durability and long-run history are relevant descriptive context, but no reviewed source selects a standardized field cutoff or exact long-run prescription.
- **Exact value:**

```json
{
  "durability_field_cutoff": "not_accepted",
  "durability_field_protocol": "not_accepted",
  "durability_score_used_for_eligibility_or_dose": false,
  "exact_long_run_cap": "not_accepted",
  "exact_long_run_distance": "not_accepted",
  "exact_long_run_duration": "not_accepted",
  "exact_long_run_frequency": "not_accepted",
  "exact_long_run_share_of_weekly_volume": "not_accepted",
  "mandatory_overdistance_run": false,
  "regular_long_run_is_qualitative_context": true
}
```

#### `road_marathon_published_intensity_distribution_findings` — published

- **Applies to:** intensity-distribution evidence context
- **Evidence claims:** `road-marathon.marathon-tid-mostly-low-observational`
- **Rationale:** The direct marathon dataset describes population organization. It does not choose one athlete's percentage, session count, spacing, or workout mix.
- **Exact value:**

```json
{
  "causal_optimum_or_individual_dose_established": false,
  "faster_runners_accumulated_more_zone_one_volume": true,
  "fastest_group_pyramidal_distribution_percent": {
    "greater_than": 80
  },
  "marathons_analysed": 151813,
  "observational": true,
  "runners_analysed": 119452,
  "zone_definition_dependent": true
}
```

#### `road_marathon_intensity_and_race_specific_policy` — guardrail

- **Applies to:** intensity and race-specific work module
- **Evidence claims:** `road-marathon.marathon-tid-mostly-low-observational`, `road-marathon.durability-relevant-no-field-cutoff`, `road-marathon.pacing-prediction-retains-individual-error`
- **Rationale:** Mostly-low organization is a common observational pattern and one candidate prior, not a universal rule. The athlete's confirmed current pattern, constraints, goal, evidence applicability, and observed response must shape future organization. Every exact selection, update, distribution, race-specific exposure, session count, spacing rule, and workout remains a separate decision.
- **Exact value:**

```json
{
  "activity_avg_power_allowed": false,
  "durability_used_as_descriptive_context_only": true,
  "exact_feedback_adjustment_algorithm": "not_accepted",
  "exact_hours_or_days_between_quality_sessions": "not_accepted",
  "exact_low_intensity_fraction": "not_accepted",
  "exact_session_mix": "not_accepted",
  "exact_strategy_selection_algorithm": "not_accepted",
  "exact_workout_templates": "not_accepted",
  "individualized_training_organization_required": true,
  "intensity_source_priority": [
    "activity_splits",
    "activity_samples"
  ],
  "marathon_pace_or_race_specific_dose": "not_accepted",
  "maximum_quality_sessions_per_7_day_unit": "not_accepted",
  "missed_quality_makeup_allowed": false,
  "mostly_low_intensity_organization_required": false,
  "mostly_low_organization_is_candidate_scientific_prior": true,
  "organization_must_be_reassessed_from_feedback": true,
  "organization_selection_inputs": [
    "athlete_confirmed_recent_training_pattern",
    "current_capability_and_load_pattern",
    "goal_intent_and_event_context",
    "availability_constraints_and_preferences",
    "applicable_scientific_theories_and_findings",
    "observed_response_and_athlete_feedback"
  ],
  "race_specific_work_may_be_a_future_module": true,
  "scientific_pattern_is_permanent_runner_identity": false,
  "selected_distribution_model": "not_accepted",
  "target_gap_may_add_quality": false
}
```

#### `road_marathon_published_taper_findings` — published

- **Applies to:** taper evidence context
- **Evidence claims:** `road-marathon.taper-support-exact-parameters-uncertain`
- **Rationale:** The marathon result is observational and the pooled values are indirect. They remain source findings rather than the selected product taper.
- **Exact value:**

```json
{
  "marathon_observational_finding": {
    "causal_or_fixed_personal_benefit": false,
    "median_benefit_percent_vs_minimal_taper": 2.6,
    "median_benefit_seconds_vs_minimal_taper": 332.4,
    "strict_taper_duration_weeks": 3
  },
  "mixed_endurance_meta_analysis": {
    "direct_road_marathon_validation": false,
    "duration_8_to_14_days_standardized_mean_difference": {
      "confidence_interval": {
        "high": -0.19,
        "low": -2.75
      },
      "estimate": -1.47
    },
    "maintain_frequency": true,
    "maintain_intensity": true,
    "time_trial_standardized_mean_difference": {
      "confidence_interval": {
        "high": -0.23,
        "low": -0.68
      },
      "estimate": -0.45
    },
    "volume_reduction_41_to_60_percent_standardized_mean_difference": {
      "confidence_interval": {
        "high": -0.3,
        "low": -1.23
      },
      "estimate": -0.77
    }
  }
}
```

#### `road_marathon_taper_and_recovery_policy` — guardrail

- **Applies to:** taper and recovery module
- **Evidence claims:** `road-marathon.taper-support-exact-parameters-uncertain`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`, `eligibility.current-symptoms-support-stop-not-clearance`
- **Rationale:** Taper and recovery evidence does not select one schedule, accounting method, readiness interval, or short-horizon alternative.
- **Exact value:**

```json
{
  "completed_marathon_requires_recovery_and_pattern_reassessment": true,
  "exact_frequency_rule": "not_accepted",
  "exact_intensity_exposure": "not_accepted",
  "exact_taper_window_days": "not_accepted",
  "exact_volume_reduction_percent": "not_accepted",
  "no_extra_sharpening_or_makeup": true,
  "personal_taper_gain_claim": "prohibited",
  "post_marathon_recovery_interval": "not_accepted",
  "pre_event_training_minutes_accounting": "not_accepted",
  "renal_recovery_defines_general_readiness": false,
  "return_to_quality_or_long_run_rule": "not_accepted",
  "short_horizon_alternative": "not_accepted",
  "target_event_elapsed_time_included_in_training_minutes": "not_accepted"
}
```

#### `road_marathon_published_fueling_and_gut_findings` — published

- **Applies to:** fueling and gut-practice evidence context
- **Evidence claims:** `road-marathon.carbohydrate-support-contextual`, `road-marathon.gut-training-tolerance-not-universal`
- **Rationale:** The values reproduce bounded source findings. They do not define product duration bands, intake, loading, prompts, or guaranteed tolerance.
- **Exact value:**

```json
{
  "acute_carbohydrate_supports_prolonged_endurance_performance_at_population_level": true,
  "direct_distance_only_marathon_prescription": false,
  "gut_training_findings": {
    "carbohydrate_malabsorption_reduction_percent": {
      "high": 54,
      "low": 45
    },
    "gastrointestinal_discomfort_reduction_percent": 47
  },
  "loading_and_intake_are_contextual": true,
  "universal_protocol_or_guaranteed_adaptation": false
}
```

#### `road_marathon_fueling_and_hydration_policy` — guardrail

- **Applies to:** fueling, hydration, and practice module
- **Evidence claims:** `road-marathon.carbohydrate-support-contextual`, `road-marathon.gut-training-tolerance-not-universal`, `road-marathon.fluid-sodium-needs-variable`
- **Rationale:** Practiced fueling is a qualitative boundary. Exact intake, loading, gut-training, fluid, sodium, sweat, and prompt rules require separate review and athlete context.
- **Exact value:**

```json
{
  "carbohydrate_loading_rule": "not_accepted",
  "distance_only_routing_allowed": false,
  "during_exercise_intake_rule": "not_accepted",
  "fluid_millilitres_per_hour_rule": "not_accepted",
  "fueling_prompt_content_and_timing": "not_accepted",
  "gut_training_protocol": "not_accepted",
  "hydration_prompt_content_and_timing": "not_accepted",
  "medical_or_dietetic_treatment_claim": false,
  "missing_context_blocks_independent_plan_modules": false,
  "missing_material_context_outcome": "fueling_module_limited",
  "new_race_day_strategy_without_practice": "prohibited",
  "practiced_strategy_required_before_race_day_suggestion": true,
  "required_context": [
    "expected_event_duration_context",
    "prior_carbohydrate_practice",
    "prior_gastrointestinal_tolerance_or_issue",
    "fluid_and_sodium_practice",
    "environment_context",
    "athlete_preference"
  ],
  "sodium_rule": "not_accepted",
  "sweat_or_body_mass_loss_rule": "not_accepted"
}
```

#### `road_marathon_published_fluid_and_sodium_findings` — published

- **Applies to:** fluid and sodium evidence context
- **Evidence claims:** `road-marathon.fluid-sodium-needs-variable`
- **Rationale:** The position, consensus, and variability review support a contextual safety boundary rather than one personal replacement prescription.
- **Exact value:**

```json
{
  "both_under_replacement_and_overdrinking_matter": true,
  "distance_only_millilitres_per_hour_or_sodium_rule_validated": false,
  "exercise_associated_hyponatremia_is_a_separate_safety_boundary": true,
  "fluid_needs_vary_with_athlete_and_context": true,
  "sweat_rate_and_sodium_show_intra_and_interindividual_variability": true
}
```

#### `road_marathon_published_environment_and_altitude_findings` — published

- **Applies to:** environment and altitude evidence context
- **Evidence claims:** `road-marathon.altitude-capacity-no-personal-correction`, `environment.heat-balance-multifactor`, `environment.relative-humidity-insufficient`, `environment.wbgt-population-performance`, `environment.temperature-nonlinear`, `environment.marathon-wbgt-performance-level`, `environment.no-universal-personal-correction`, `heat-adaptation.repeated-exposure`, `heat-safety.separate-from-adaptation`
- **Rationale:** The source findings establish descriptive environmental and acute capacity context. They do not define a personal pace, time, safety, or acclimation rule.
- **Exact value:**

```json
{
  "acute_altitude_chamber_findings_per_1000_m": {
    "fixed_speed_time_to_exhaustion_change_percent": -14.5,
    "vo2max_change_percent": -6.3
  },
  "altitude_findings_are_marathon_corrections": false,
  "environmental_heat_context": {
    "heat_balance_is_multifactorial": true,
    "marathon_temperature_and_wbgt_findings_are_population_associations": true,
    "relative_humidity_alone_is_insufficient": true,
    "universal_personal_correction_validated": false
  },
  "heat_adaptation_is_repeated_exposure_context_not_clearance": true,
  "individualized_acclimation_schedule_validated": false
}
```

#### `road_marathon_environment_and_altitude_policy` — guardrail

- **Applies to:** environment and altitude module
- **Evidence claims:** `road-marathon.altitude-capacity-no-personal-correction`, `environment.full-wbgt-inputs`, `environment.no-universal-personal-correction`, `heat-adaptation.repeated-exposure`, `heat-safety.separate-from-adaptation`
- **Rationale:** Complete, source-labelled context is required before future dependent explanation. No reviewed source selects an individualized correction, adjustment, or acclimation schedule.
- **Exact value:**

```json
{
  "altitude_acclimation_schedule": "not_accepted",
  "environmental_plan_adjustment_rule": "not_accepted",
  "heat_acclimation_schedule": "not_accepted",
  "heat_adaptation_used_as_medical_clearance": false,
  "incomplete_material_context_outcome": "environment_module_limited",
  "missing_context_blocks_independent_plan_modules": false,
  "personal_altitude_pace_or_finish_time_correction": "not_accepted",
  "personal_temperature_or_wbgt_correction": "not_accepted",
  "population_coefficient_used_as_personal_counterfactual": false,
  "required_environment_inputs_when_available": [
    "air_temperature",
    "atmospheric_moisture_or_vapor_pressure",
    "wind",
    "solar_or_radiant_load",
    "altitude_or_elevation_profile",
    "source_time_location_and_confidence"
  ],
  "weather_or_course_data_must_remain_source_labelled": true
}
```

#### `road_marathon_reassessment_and_outcome_policy` — guardrail

- **Applies to:** reassessment and outcomes module
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-marathon.pacing-prediction-retains-individual-error`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`, `environment.no-universal-personal-correction`
- **Rationale:** The product must close the loop from recommendation through athlete feedback and observed outcomes into the next reassessment. No reviewed source selects the exact feedback weighting, update rule, cadence, fixed outcome window, meaningful-change threshold, race-priority algorithm, or causal attribution.
- **Exact value:**

```json
{
  "absence_of_improvement_proves_nonresponse": false,
  "causal_plan_effect_claim": "prohibited",
  "direct_before_after_claim_requires": [
    "comparable_distance_and_result_type",
    "known_route_or_event",
    "known_surface_and_assistance",
    "known_environment_when_available",
    "no_material_protocol_change"
  ],
  "exact_calendar_reassessment_cadence": "not_accepted",
  "exact_feedback_weighting_and_update_algorithm": "not_accepted",
  "exact_post_marathon_outcome_window": "not_accepted",
  "feedback_inputs": [
    "completed_sessions_and_adherence",
    "athlete_edits_rejections_and_preferences",
    "perceived_effort_and_reported_response",
    "recovery_and_symptom_context",
    "split_or_sample_level_training_response",
    "comparable_event_or_field_outcomes"
  ],
  "feedback_loop_required": true,
  "meaningful_change_threshold": "not_accepted",
  "next_recommendation_must_record_response_to_feedback": true,
  "outcome_comparability_algorithm": "not_accepted",
  "personal_responder_classification": "prohibited",
  "race_priority_and_conflict_resolution_rule": "not_accepted",
  "reassessment_triggers": [
    "new_or_changed_confirmed_event",
    "new_qualified_marathon_result",
    "material_training_pattern_change",
    "completed_training_and_adherence_change",
    "athlete_edit_rejection_or_reported_response",
    "recovery_or_symptom_change",
    "completed_marathon_or_maximal_event",
    "changed_availability_or_constraint",
    "changed_fueling_hydration_or_environment_context",
    "athlete_requested_review"
  ],
  "renal_recovery_used_as_general_readiness": false,
  "supporting_outcomes": [
    "split_level_pacing_and_pace_decline",
    "adherence_edit_and_rejection_burden",
    "fueling_and_gastrointestinal_response",
    "hydration_context_and_issues",
    "recovery_response",
    "weekly_volume_frequency_longest_run_and_quality_change"
  ]
}
```

#### `road_marathon_typed_outcomes_and_suggestion_only_state` — guardrail

- **Applies to:** future API and client state contract
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `eligibility.current-symptoms-support-stop-not-clearance`, `road-marathon.pacing-prediction-retains-individual-error`
- **Rationale:** Typed outcomes preserve goal intent and make missing context or authority explicit without replacing product value with disclaimers. A supported safe route must take an actionable position; proposal, athlete adoption, observation, reassessment, delivery, and activation remain distinct states.
- **Exact value:**

```json
{
  "AI_may_not": [
    "broaden_eligibility",
    "invent_capability_history_event_profile_or_safety_context",
    "choose_unaccepted_values",
    "override_deterministic_validation",
    "create_human_approval_artifacts",
    "activate_adopt_deliver_or_publish"
  ],
  "athlete_may": [
    "review",
    "edit",
    "reject",
    "explicitly_consent_to_adopt"
  ],
  "current_runtime_outcome": "plan_policy_inactive",
  "disclaimer_only_response_allowed_for_supported_safe_route": false,
  "future_generated_state_after_activation": "proposed",
  "generator_may_not": [
    "adopt_or_deliver_without_consent",
    "overwrite_adopted_future_days",
    "auto_schedule_a_maximal_marathon",
    "auto_change_event_priority",
    "schedule_missed_workout_makeup",
    "invent_fueling_hydration_or_environment_context"
  ],
  "no_plan_or_limited_outcome_must_include_actionable_resolution_path": true,
  "outcomes": {
    "capability_confirmation_required": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "environment_module_limited": {
      "degraded_modules": [
        "environment_altitude"
      ],
      "goal_remains_recorded": true,
      "plan_returned": true
    },
    "fueling_module_limited": {
      "degraded_modules": [
        "fueling_hydration_practice"
      ],
      "goal_remains_recorded": true,
      "plan_returned": true
    },
    "goal_recorded_plan_policy_unavailable": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "implementation_review_required": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "insufficient_history": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "limited_guidance_only": {
      "goal_remains_recorded": true,
      "limited_guidance_returned": true,
      "plan_returned": false
    },
    "plan_policy_inactive": {
      "goal_remains_recorded": true,
      "plan_returned": false
    },
    "unresolved_event_conflict": {
      "goal_remains_recorded": true,
      "plan_returned": false
    }
  },
  "recommendation_must_include": [
    "next_action",
    "athlete_specific_rationale",
    "scientific_basis_and_applicability",
    "expected_response_or_signal",
    "uncertainty",
    "feedback_request"
  ],
  "supported_safe_route_must_return_actionable_recommendation": true
}
```

#### `road_marathon_validation_privacy_and_open_decisions` — guardrail

- **Applies to:** validation, privacy, implementation, and rollout
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `eligibility.masters-age-change-not-automatic-exclusion`, `road-marathon.recovery-subgroup-outcome-rules-unvalidated`, `road-marathon.fluid-sodium-needs-variable`
- **Rationale:** Deterministic integrity is an engineering requirement. Statistical, subgroup, event-density, outcome, implementation, and activation choices need separate reviewed protocols and minimum-necessary private data. The loop must remain versioned, replayable, and reviewable rather than become hidden online learning.
- **Exact value:**

```json
{
  "deterministic_invariant_breach_tolerance": 0,
  "deterministic_replay_mismatch_tolerance": 0,
  "dry_run_metrics_required": [
    "eligibility_and_each_typed_outcome_rate",
    "actionable_recommendation_coverage_for_supported_safe_routes",
    "recommendation_reasoning_expected_signal_and_feedback_completeness",
    "missingness_and_source_confirmation",
    "event_conflict_and_race_density",
    "subgroup_exclusion_and_edit_gaps",
    "proposal_edit_rejection_and_adoption_burden",
    "feedback_to_next_proposal_traceability",
    "fueling_hydration_and_environment_context_availability",
    "quality_event_and_long_run_stacking",
    "deterministic_replay"
  ],
  "exact_dry_run_go_no_go_thresholds": "not_accepted",
  "exact_prospective_pause_thresholds": "not_accepted",
  "implementation_mapping": "not_accepted",
  "no_inference_of": [
    "diagnosis",
    "injury_cause",
    "pregnancy_status",
    "mental_state",
    "missed_training_reason",
    "gastrointestinal_diagnosis",
    "hydration_or_sodium_diagnosis"
  ],
  "no_publication_of": [
    "raw_health_data",
    "private_activity_data",
    "inferred_sensitive_context"
  ],
  "outcome_windows_and_meaningful_change_thresholds": "not_accepted",
  "prospective_metrics_required": [
    "adoption_and_edit_distance",
    "adherence_and_burden",
    "recommendation_change_after_athlete_feedback",
    "symptom_stops_and_adverse_events",
    "fueling_and_gastrointestinal_tolerance",
    "hydration_issues",
    "comparable_marathon_outcomes",
    "withdrawal"
  ],
  "race_density_and_priority_thresholds": "not_accepted",
  "replay_record_must_include": [
    "policy_versions_and_contract_digests",
    "goal_record_state",
    "capability_and_history_sources",
    "split_or_sample_intensity_sources",
    "confirmed_event_context",
    "profile_fueling_hydration_and_environment_provenance",
    "unresolved_parameter_versions",
    "typed_outcome",
    "proposal_hash",
    "recommendation_hypothesis_and_expected_signal",
    "athlete_feedback_and_observed_outcome",
    "reassessment_reason",
    "change_from_prior_proposal"
  ],
  "runtime_activation_criteria": "not_accepted",
  "subgroup_dose_modifiers": "not_accepted",
  "target_risk_thresholds": "not_accepted",
  "unreviewed_online_learning_allowed": false
}
```

### Rejected alternatives

#### Copy a 5 km, 10 km, or half-marathon policy and replace the distance label

Marathon duration, direct capability, long-run durability, fueling, hydration, taper, recovery, environment, and event demands differ. Existing numeric guardrails are policy-specific and not universal evidence.

#### Generate a performance plan for first-marathon or completion intent

Current direct same-task capability and stable history define this proposal. Completion and sparse-history populations need separately reviewed policies.

#### Treat a prediction, critical speed, or shorter race as direct marathon capability

Models retain material individual error and do not manufacture same-task history, personal probability, or readiness.

#### Schedule a maximal marathon simulation when direct capability is missing

A maximal simulation is burdensome and is not validated here. A no-event rolling preparation or benchmark route requires a separately accepted completion or benchmark policy.

#### Convert observed volume, longest-run, durability, or taper values into prescriptions

The direct findings are observational, cross-sectional, or indirect and do not establish an optimal or safe individual dose.

#### Select a universal pyramidal distribution or marathon-pace dose

The direct dataset is observational and zone-definition dependent. It does not establish a causal percentage, session count, spacing, or workout mix.

#### Escalate dose to close a target-time gap or make up missed work

Prediction error and population associations cannot justify compressed progression, catch-up, or hidden dose escalation.

#### Use one marathon fueling, fluid, or sodium rule

Duration, prior practice, tolerance, sweat response, environment, and athlete preference vary; both inadequate replacement and overdrinking matter.

#### Apply an altitude or weather coefficient to personal marathon pace

Acute chamber effects and population weather associations are not individualized corrections or acclimation schedules.

#### Let AI fill missing context or choose deferred values

AI cannot repair missing evidence, confirm athlete inputs, broaden eligibility, create approvals, activate runtime, or replace deterministic review.

### Applicability

- Adults aged 18 years or older with adult scope confirmed
- Current direct athlete-confirmed outdoor road-marathon capability
- Stable recent running history and within-recent load
- Performance intent with optional target time or date
- Athlete-confirmed event context with unresolved conflicts excluded from a full proposal
- Suggestion-only future behavior after every unresolved value and implementation review is accepted
- Cohort labels describe evidence populations and never permanent runner identities

### User-facing claim limits

- When implemented and separately activated for a supported safe route, Praxys must recommend a concrete next action with an athlete-specific rationale, applicable science, an expected signal, uncertainty, and a request for the feedback that can change the next recommendation. It may not substitute a list of disclaimers for that product value.
- Scientific theories and research findings are bounded candidate strategies and priors. They inform an individualized proposal and its explanation; observed athlete response informs reassessment without proving personal causality or a permanent responder type.
- This draft is an evidence and decision proposal, not a usable marathon generator, optimal plan, safety guarantee, medical advice, target-time guarantee, or personal probability.
- Fokkema volume and longest-run categories, durability correlations, training-intensity distributions, taper effects, gut-tolerance findings, and altitude chamber effects are source findings only.
- No plan length or 5 km, 10 km, or half-marathon numeric rule is accepted for marathon use through this record.
- Missing optional age, sex, profile, fueling, hydration, or environmental detail affects only the dependent adjustment and unknown sex never defaults to male.
- No-event rolling preparation or simulation requires a separately accepted completion or benchmark policy and cannot silently create a maximal marathon.
- Environmental and altitude context may explain uncertainty but cannot produce a personal pace, finish-time, acclimation, or safety correction.

### Safety implications

- Current concerning symptoms, illness, injury, rehabilitation, return-to-sport, medical-clearance, pregnancy-specific, or contradictory safety context stops the vigorous-plan path without diagnosis or treatment.
- Prior marathon completion, within-recent history, renal recovery, practiced fueling, or heat adaptation does not establish medical clearance or guarantee freedom from harm.
- No maximal marathon benchmark, target-gap escalation, catch-up, fixed progression law, ACWR prescription zone, distance-only hydration rule, or activity-average-power intensity analysis is allowed.
- Both inadequate replacement and overdrinking matter; medical hydration, sodium, heat-illness, or hyponatremia diagnosis and treatment remain outside this performance policy.
- Confirmed races and maximal efforts must count as quality and load, and unresolved event conflicts prevent a full proposal.

### Privacy implications

- Use only the authenticated athlete's minimum necessary goal, activity, event, profile, constraints, fueling, hydration, environment, and optional symptom context.
- Provider-imported profile, event, weather, and course fields remain source-labelled candidates until the athlete confirms or corrects them.
- Do not infer or publish diagnosis, injury cause, pregnancy status, gastrointestinal or hydration diagnosis, mental state, missed-training reason, or external life circumstance.

### Validation plan

- Registry validation must prove the exact draft Evidence Review and claim links, globally consistent citation metadata, rigorous verification notes, four approve and five defer items, complete parameter coverage, literal `not_accepted` deferrals, and inactive artifact policy.
- Artifact validation must prove that generated Evidence Review and SDR packets carry current digests and that the exact inactive machine contract embedded in the SDR packet matches the generated JSON contract.
- Tests must lock the narrow population tuple, modular structure, direct baseline hierarchy, goal-policy separation, no-event benchmark boundary, source-labelled profile and event data, module-local missing-context degradation, actionable recommendation contract, athlete feedback loop, typed outcomes, and activity-split/sample intensity rule.
- Tests must prove no plan length or shorter-distance numeric rule is inherited and that key observed values remain published source findings, not guardrail values.
- Tests must prove mostly-low organization is a candidate prior rather than a mandatory template, supported safe routes cannot return disclaimer-only output, and every proposal records the expected signal and feedback needed for the next reassessment.
- Before implementation, separate human decisions must select every baseline, history, dose, long-run, durability, intensity, race-specific, taper, recovery, fueling, hydration, environment, altitude, reassessment, subgroup, outcome, pilot, and activation value.
- Offline dry runs must report exclusions, missingness, source confirmation, event conflicts, subgroup gaps, actionable recommendation coverage, reasoning and feedback-request completeness, edit and rejection burden, feedback-to-next-proposal traceability, fueling, hydration and environment context, quality and event stacking, and deterministic replay without publishing private athlete data.
- A prospective opt-in pilot must predeclare human-reviewed go/no-go and pause thresholds before any activation.

### Falsification conditions

- Reject the product behavior if an otherwise supported safe route returns disclaimers, caveats, or data summaries without a concrete next action, athlete-specific rationale, expected signal, uncertainty, and feedback request.
- Reject the policy if any implementation emits a plan while the decision or contract is draft or inactive, consumes an unaccepted value, or omits a code-consumed field from the human review packet.
- Reject routing if prediction, critical speed, shorter-distance conversion, passive segment, unconfirmed provider result, or activity average power is treated as direct current marathon capability or intensity evidence.
- Reject schedule mapping if observational source categories, durability correlations, pyramidal prevalence, taper effects, or target gap become eligibility or dose rules, or if mostly-low organization becomes a mandatory template rather than one candidate prior.
- Reject the feedback loop if athlete completion, edits, rejection, reported response, recovery, symptoms, or comparable outcomes cannot be traced into reassessment of the next proposal, or if an unreviewed online learner changes policy outside the versioned contract.
- Reject no-event routing if it creates a maximal marathon simulation without a separately accepted completion or benchmark policy.
- Reject fueling or hydration behavior if distance alone selects loading, intake, fluid, sodium, gut-training, or race-day strategy.
- Reject modular routing if missing fueling, hydration, or environmental context blocks otherwise eligible independent plan modules or is replaced with an invented value.
- Reject environmental behavior if population weather or chamber altitude findings become a personal correction, acclimation schedule, clearance, or guarantee.
- Pause future activation after any deterministic invariant or replay breach, symptom-stop override, hidden demographic default, unconfirmed source use, unresolved event conflict, unsupported population, consent bypass, or approval-digest mismatch.

### Decision notes

- This artifact-mode Decision proposal addresses issue #687 and remains draft and inactive.
- Human review must use the generated packet rather than raw YAML. The packet includes the exact inactive machine contract and digest-bound approval templates.
- First-marathon or completion intent, sparse history, returning, clinical, rehabilitation, pregnancy-specific, trail, ultra, and unsupported contexts require separate policies.
- All unresolved behavior-driving values are literal `not_accepted`; no implementation may infer a value from source findings, another distance, prose, or AI output.
- Impact map: draft Evidence Review -> generated evidence packet -> draft SDR -> generated decision packet and inactive contract -> human evidence and decision review -> future implementation review -> future pure policy mapping -> actionable proposal -> athlete review and adoption -> observed response and feedback -> reassessment -> API -> web and miniapp parity -> ScienceNote and localization -> offline validation -> opt-in pilot -> separately approved activation.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "road-marathon-plan-generation-policy-v1",
    "shared dynamic training-pattern and confirmed event snapshots"
  ],
  "contract_digest": "sha256:8314b326744c7a3c7e87974e28ff818b6557c1cf31ac1576a100b8413510de8e",
  "decision_id": "sdr-road-marathon-plan-generation-policy-v1",
  "decision_status": "draft",
  "decision_version": 1,
  "evidence_claim_ids": [
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.fixed-progression-and-acwr-not-safety-laws",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.current-symptoms-support-stop-not-clearance",
    "eligibility.evidence-quality-no-personal-probability",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "road-marathon.task-specific-capability-baseline-multifactorial",
    "road-marathon.volume-frequency-longest-run-associative",
    "road-marathon.durability-relevant-no-field-cutoff",
    "road-marathon.marathon-tid-mostly-low-observational",
    "road-marathon.taper-support-exact-parameters-uncertain",
    "road-marathon.pacing-prediction-retains-individual-error",
    "road-marathon.carbohydrate-support-contextual",
    "road-marathon.gut-training-tolerance-not-universal",
    "road-marathon.fluid-sodium-needs-variable",
    "road-marathon.altitude-capacity-no-personal-correction",
    "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
    "environment.heat-balance-multifactor",
    "environment.relative-humidity-insufficient",
    "environment.wbgt-population-performance",
    "environment.temperature-nonlinear",
    "environment.marathon-wbgt-performance-level",
    "environment.full-wbgt-inputs",
    "environment.no-universal-personal-correction",
    "heat-adaptation.repeated-exposure",
    "heat-safety.separate-from-adaptation"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-road-marathon-plan-generation-policy-v1",
    "evidence-environmental-performance-v1",
    "evidence-heat-adaptation-v1"
  ],
  "linked_evidence_digests": {
    "evidence-environmental-performance-v1": "sha256:0c6050c934241e32872ae884d6ffcc109e522ccc6eb00ee41426d9aa5da25a87",
    "evidence-heat-adaptation-v1": "sha256:adcdfdc74c95d4da3138545036254a1d8611222b6ad564c4c26e7af137b45ced",
    "evidence-plan-generation-eligibility-safety-v1": "sha256:e884907d33783edc6cdb16fd5504f7f10b6d68f968bfe7cf87e3f024b5bda773",
    "evidence-road-marathon-plan-generation-policy-v1": "sha256:aea18a24864ad6c65f3dc5798015eee56bf8fed2b8a2a414c687161da5846dee"
  },
  "model_version": "road-marathon-plan-generation-policy-v1",
  "parameters": {
    "road_marathon_activation_and_dependency": {
      "applies_to": "policy lifecycle and capability discovery",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "active_behavior": false,
        "capability_registry_entry_default_enabled": false,
        "decision_approval_artifact_required": true,
        "distance_decision_required_status_before_activation": "accepted",
        "distance_evidence_required_status_before_activation": "accepted",
        "evidence_review_approval_artifact_required": true,
        "generator_api_web_miniapp_plugin_and_mcp_activation_in_this_record": false,
        "implementation_approval_artifact_required": true,
        "runtime_state": "inactive",
        "shared_policy_dependency": {
          "required_status_before_activation": "accepted",
          "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
        }
      }
    },
    "road_marathon_direct_baseline_hierarchy": {
      "applies_to": "direct capability confirmation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-marathon.task-specific-capability-baseline-multifactorial",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "value": {
        "accepted_assistance_statuses": "not_accepted",
        "accepted_event_qualification": "not_accepted",
        "automatic_maximal_marathon_baseline_test": "prohibited",
        "baseline_freshness_completed_days": "not_accepted",
        "baseline_qualification_algorithm": "not_accepted",
        "direct_current_capability_required": true,
        "distance_match_tolerance_m": "not_accepted",
        "excluded_as_direct": [
          "shorter_distance_conversion",
          "critical_speed_prediction",
          "passive_marathon_segment_within_ultra",
          "unconfirmed_provider_personal_best",
          "activity_average_power",
          "vendor_readiness_or_race_score",
          "policy_generated_maximal_marathon_simulation"
        ],
        "missing_or_unconfirmed_outcome": "capability_confirmation_required",
        "preferred_direct_evidence": [
          "athlete_confirmed_official_or_organized_outdoor_road_marathon_result"
        ],
        "required_metadata": [
          "completed_at",
          "elapsed_time_seconds",
          "measured_distance_m",
          "route_or_event_identifier",
          "surface",
          "assistance_status",
          "source_provider",
          "athlete_confirmation_state"
        ],
        "supporting_only": [
          "shorter_distance_race_result",
          "critical_speed_or_threshold",
          "current_vo2max_or_vvo2max",
          "weekly_training_volume_and_frequency",
          "recent_longest_run",
          "marathon_prediction_with_error",
          "split_or_sample_pacing_distribution"
        ]
      }
    },
    "road_marathon_environment_and_altitude_policy": {
      "applies_to": "environment and altitude module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.altitude-capacity-no-personal-correction",
        "environment.full-wbgt-inputs",
        "environment.no-universal-personal-correction",
        "heat-adaptation.repeated-exposure",
        "heat-safety.separate-from-adaptation"
      ],
      "value": {
        "altitude_acclimation_schedule": "not_accepted",
        "environmental_plan_adjustment_rule": "not_accepted",
        "heat_acclimation_schedule": "not_accepted",
        "heat_adaptation_used_as_medical_clearance": false,
        "incomplete_material_context_outcome": "environment_module_limited",
        "missing_context_blocks_independent_plan_modules": false,
        "personal_altitude_pace_or_finish_time_correction": "not_accepted",
        "personal_temperature_or_wbgt_correction": "not_accepted",
        "population_coefficient_used_as_personal_counterfactual": false,
        "required_environment_inputs_when_available": [
          "air_temperature",
          "atmospheric_moisture_or_vapor_pressure",
          "wind",
          "solar_or_radiant_load",
          "altitude_or_elevation_profile",
          "source_time_location_and_confidence"
        ],
        "weather_or_course_data_must_remain_source_labelled": true
      }
    },
    "road_marathon_fueling_and_hydration_policy": {
      "applies_to": "fueling, hydration, and practice module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.carbohydrate-support-contextual",
        "road-marathon.gut-training-tolerance-not-universal",
        "road-marathon.fluid-sodium-needs-variable"
      ],
      "value": {
        "carbohydrate_loading_rule": "not_accepted",
        "distance_only_routing_allowed": false,
        "during_exercise_intake_rule": "not_accepted",
        "fluid_millilitres_per_hour_rule": "not_accepted",
        "fueling_prompt_content_and_timing": "not_accepted",
        "gut_training_protocol": "not_accepted",
        "hydration_prompt_content_and_timing": "not_accepted",
        "medical_or_dietetic_treatment_claim": false,
        "missing_context_blocks_independent_plan_modules": false,
        "missing_material_context_outcome": "fueling_module_limited",
        "new_race_day_strategy_without_practice": "prohibited",
        "practiced_strategy_required_before_race_day_suggestion": true,
        "required_context": [
          "expected_event_duration_context",
          "prior_carbohydrate_practice",
          "prior_gastrointestinal_tolerance_or_issue",
          "fluid_and_sodium_practice",
          "environment_context",
          "athlete_preference"
        ],
        "sodium_rule": "not_accepted",
        "sweat_or_body_mass_loss_rule": "not_accepted"
      }
    },
    "road_marathon_goal_and_event_tuple": {
      "applies_to": "goal normalization and marathon policy selection",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-marathon.task-specific-capability-baseline-multifactorial"
      ],
      "value": {
        "event_context_must_be_athlete_confirmed": true,
        "goal_capture_independent_from_generator_availability": true,
        "goal_intent": "performance",
        "goal_kind": "distance_marathon",
        "no_event_goal": {
          "automatic_maximal_marathon_simulation": "prohibited",
          "goal_remains_recorded": true,
          "rolling_preparation_or_simulation_requires_separately_accepted_completion_or_benchmark_policy": true
        },
        "primary_outcome": "elapsed_time",
        "separate_policy_variants": [
          "first_marathon_or_completion_intent",
          "sparse_or_missing_history",
          "returning_after_interruption",
          "clinical_rehabilitation_or_return_to_sport",
          "pregnancy_specific_planning",
          "trail_marathon",
          "ultramarathon",
          "unsupported_surface_event_or_context"
        ],
        "sport": "running",
        "surface": "outdoor_road",
        "target_date_optional": true,
        "target_time_optional": true,
        "unavailable_policy_result": "goal_recorded_plan_policy_unavailable"
      }
    },
    "road_marathon_history_anchored_load_policy": {
      "applies_to": "plan horizon and weekly exposure",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-marathon.volume-frequency-longest-run-associative",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "value": {
        "acwr_prescription_zone_used": false,
        "athlete_availability_is_hard_cap": true,
        "current_load_comparison_method": "not_accepted",
        "missed_workout_catch_up_allowed": false,
        "plan_length_days": "not_accepted",
        "shorter_distance_numeric_rules_inherited": false,
        "target_gap_may_raise_load": false,
        "ten_percent_rule_used": false,
        "weekly_progression_rule": "not_accepted",
        "weekly_running_frequency_range": "not_accepted",
        "weekly_volume_target_or_range": "not_accepted"
      }
    },
    "road_marathon_intensity_and_race_specific_policy": {
      "applies_to": "intensity and race-specific work module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.marathon-tid-mostly-low-observational",
        "road-marathon.durability-relevant-no-field-cutoff",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "value": {
        "activity_avg_power_allowed": false,
        "durability_used_as_descriptive_context_only": true,
        "exact_feedback_adjustment_algorithm": "not_accepted",
        "exact_hours_or_days_between_quality_sessions": "not_accepted",
        "exact_low_intensity_fraction": "not_accepted",
        "exact_session_mix": "not_accepted",
        "exact_strategy_selection_algorithm": "not_accepted",
        "exact_workout_templates": "not_accepted",
        "individualized_training_organization_required": true,
        "intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "marathon_pace_or_race_specific_dose": "not_accepted",
        "maximum_quality_sessions_per_7_day_unit": "not_accepted",
        "missed_quality_makeup_allowed": false,
        "mostly_low_intensity_organization_required": false,
        "mostly_low_organization_is_candidate_scientific_prior": true,
        "organization_must_be_reassessed_from_feedback": true,
        "organization_selection_inputs": [
          "athlete_confirmed_recent_training_pattern",
          "current_capability_and_load_pattern",
          "goal_intent_and_event_context",
          "availability_constraints_and_preferences",
          "applicable_scientific_theories_and_findings",
          "observed_response_and_athlete_feedback"
        ],
        "race_specific_work_may_be_a_future_module": true,
        "scientific_pattern_is_permanent_runner_identity": false,
        "selected_distribution_model": "not_accepted",
        "target_gap_may_add_quality": false
      }
    },
    "road_marathon_long_run_and_durability_policy": {
      "applies_to": "long-run and durability module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.volume-frequency-longest-run-associative",
        "road-marathon.durability-relevant-no-field-cutoff"
      ],
      "value": {
        "durability_field_cutoff": "not_accepted",
        "durability_field_protocol": "not_accepted",
        "durability_score_used_for_eligibility_or_dose": false,
        "exact_long_run_cap": "not_accepted",
        "exact_long_run_distance": "not_accepted",
        "exact_long_run_duration": "not_accepted",
        "exact_long_run_frequency": "not_accepted",
        "exact_long_run_share_of_weekly_volume": "not_accepted",
        "mandatory_overdistance_run": false,
        "regular_long_run_is_qualitative_context": true
      }
    },
    "road_marathon_modular_policy_structure": {
      "applies_to": "policy composition and review",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
      ],
      "value": {
        "disclaimer_only_output_allowed_for_supported_safe_route": false,
        "each_module_must_declare": [
          "required_inputs",
          "missingness_effect",
          "evidence_or_guardrail_provenance",
          "athlete_editability",
          "typed_outcome"
        ],
        "feedback_loop_stages": [
          "sense_current_state",
          "select_candidate_strategy",
          "propose_reviewable_action",
          "athlete_review_edit_reject_or_adopt",
          "observe_completion_response_and_outcome",
          "reassess_next_recommendation"
        ],
        "missing_context_disables_or_degrades_dependent_module_only": true,
        "missing_context_may_block_independent_modules": false,
        "modules": [
          "entry_readiness",
          "history_load",
          "long_run_durability",
          "intensity_race_specific_work",
          "fueling_hydration_practice",
          "taper_recovery",
          "environment_altitude",
          "reassessment_outcomes"
        ],
        "plan_length_selected": false,
        "recommendation_must_declare": [
          "next_action",
          "athlete_specific_rationale",
          "scientific_basis_and_applicability",
          "expected_response_or_signal",
          "uncertainty",
          "feedback_needed_for_reassessment"
        ],
        "scientific_evidence_roles": [
          "bound_candidate_strategies",
          "inform_initial_prior",
          "explain_athlete_specific_recommendation",
          "define_expected_and_contradictory_signals"
        ],
        "supported_route_must_take_actionable_position": true,
        "unresolved_dependent_module_preserves_goal_record": true,
        "unresolved_module_cannot_be_filled_by_another_distance_policy": true
      }
    },
    "road_marathon_profile_and_source_provenance": {
      "applies_to": "profile, event, and missing-data handling",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "eligibility.evidence-quality-no-personal-probability",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
      ],
      "value": {
        "adult_scope_confirmation_required": true,
        "imported_profile_and_event_fields": {
          "may_not_overwrite_athlete_confirmed_value": true,
          "missing_is_unknown_not_false": true,
          "remain_source_labelled_until_athlete_confirmation": true
        },
        "minimum_necessary_inputs_only": true,
        "missing_optional_modifier_effect": "disable_dependent_adjustment_only",
        "optional_modifier_fields": [
          "age_or_age_band",
          "sex",
          "profile_attributes",
          "prior_marathon_count",
          "environmental_history",
          "fueling_and_gastrointestinal_history"
        ],
        "unknown_sex_defaults_to_male": false
      }
    },
    "road_marathon_published_durability_findings": {
      "applies_to": "durability evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.durability-relevant-no-field-cutoff"
      ],
      "value": {
        "causal_or_field_cutoff_established": false,
        "design": "cross_sectional",
        "longest_run_correlation_with_deterioration": -0.67,
        "running_economy_deterioration_percent": {
          "better_durability_group": 3.1,
          "lower_durability_group": 6.0
        },
        "study_population": "26_performance_matched_well_trained_men",
        "training_volume_correlation_with_deterioration": -0.48
      }
    },
    "road_marathon_published_environment_and_altitude_findings": {
      "applies_to": "environment and altitude evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.altitude-capacity-no-personal-correction",
        "environment.heat-balance-multifactor",
        "environment.relative-humidity-insufficient",
        "environment.wbgt-population-performance",
        "environment.temperature-nonlinear",
        "environment.marathon-wbgt-performance-level",
        "environment.no-universal-personal-correction",
        "heat-adaptation.repeated-exposure",
        "heat-safety.separate-from-adaptation"
      ],
      "value": {
        "acute_altitude_chamber_findings_per_1000_m": {
          "fixed_speed_time_to_exhaustion_change_percent": -14.5,
          "vo2max_change_percent": -6.3
        },
        "altitude_findings_are_marathon_corrections": false,
        "environmental_heat_context": {
          "heat_balance_is_multifactorial": true,
          "marathon_temperature_and_wbgt_findings_are_population_associations": true,
          "relative_humidity_alone_is_insufficient": true,
          "universal_personal_correction_validated": false
        },
        "heat_adaptation_is_repeated_exposure_context_not_clearance": true,
        "individualized_acclimation_schedule_validated": false
      }
    },
    "road_marathon_published_fluid_and_sodium_findings": {
      "applies_to": "fluid and sodium evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.fluid-sodium-needs-variable"
      ],
      "value": {
        "both_under_replacement_and_overdrinking_matter": true,
        "distance_only_millilitres_per_hour_or_sodium_rule_validated": false,
        "exercise_associated_hyponatremia_is_a_separate_safety_boundary": true,
        "fluid_needs_vary_with_athlete_and_context": true,
        "sweat_rate_and_sodium_show_intra_and_interindividual_variability": true
      }
    },
    "road_marathon_published_fueling_and_gut_findings": {
      "applies_to": "fueling and gut-practice evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.carbohydrate-support-contextual",
        "road-marathon.gut-training-tolerance-not-universal"
      ],
      "value": {
        "acute_carbohydrate_supports_prolonged_endurance_performance_at_population_level": true,
        "direct_distance_only_marathon_prescription": false,
        "gut_training_findings": {
          "carbohydrate_malabsorption_reduction_percent": {
            "high": 54,
            "low": 45
          },
          "gastrointestinal_discomfort_reduction_percent": 47
        },
        "loading_and_intake_are_contextual": true,
        "universal_protocol_or_guaranteed_adaptation": false
      }
    },
    "road_marathon_published_intensity_distribution_findings": {
      "applies_to": "intensity-distribution evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.marathon-tid-mostly-low-observational"
      ],
      "value": {
        "causal_optimum_or_individual_dose_established": false,
        "faster_runners_accumulated_more_zone_one_volume": true,
        "fastest_group_pyramidal_distribution_percent": {
          "greater_than": 80
        },
        "marathons_analysed": 151813,
        "observational": true,
        "runners_analysed": 119452,
        "zone_definition_dependent": true
      }
    },
    "road_marathon_published_taper_findings": {
      "applies_to": "taper evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.taper-support-exact-parameters-uncertain"
      ],
      "value": {
        "marathon_observational_finding": {
          "causal_or_fixed_personal_benefit": false,
          "median_benefit_percent_vs_minimal_taper": 2.6,
          "median_benefit_seconds_vs_minimal_taper": 332.4,
          "strict_taper_duration_weeks": 3
        },
        "mixed_endurance_meta_analysis": {
          "direct_road_marathon_validation": false,
          "duration_8_to_14_days_standardized_mean_difference": {
            "confidence_interval": {
              "high": -0.19,
              "low": -2.75
            },
            "estimate": -1.47
          },
          "maintain_frequency": true,
          "maintain_intensity": true,
          "time_trial_standardized_mean_difference": {
            "confidence_interval": {
              "high": -0.23,
              "low": -0.68
            },
            "estimate": -0.45
          },
          "volume_reduction_41_to_60_percent_standardized_mean_difference": {
            "confidence_interval": {
              "high": -0.3,
              "low": -1.23
            },
            "estimate": -0.77
          }
        }
      }
    },
    "road_marathon_published_volume_and_long_run_findings": {
      "applies_to": "evidence display and future validation design",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.volume-frequency-longest-run-associative"
      ],
      "value": {
        "eligibility_or_prescription_established": false,
        "frequency_and_experience_association_descriptive_only": true,
        "longest_run_findings": {
          "above_35_km_vs_30_to_35": {
            "significantly_better": false
          },
          "below_25_km": {
            "confidence_interval_minutes": {
              "high": 21.55,
              "low": 5.34
            },
            "finish_time_coefficient_minutes": 13.44
          }
        },
        "observational_only": true,
        "study_population": "adult_recreational_marathon_entrants",
        "weekly_volume_findings": {
          "above_65_km_per_week_vs_40_to_65": {
            "confidence_interval_minutes": {
              "high": -5.72,
              "low": -22.47
            },
            "finish_time_coefficient_minutes": -14.09
          },
          "below_40_km_per_week_vs_40_to_65": {
            "confidence_interval_minutes": {
              "high": 12.48,
              "low": 0.18
            },
            "finish_time_coefficient_minutes": 6.33
          }
        }
      }
    },
    "road_marathon_readiness_and_history_qualification": {
      "applies_to": "readiness and history-rich qualification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-marathon.volume-frequency-longest-run-associative"
      ],
      "value": {
        "disallowed_intensity_source": [
          "activity_avg_power"
        ],
        "exact_history_lookback_weeks": "not_accepted",
        "insufficient_history_outcome": "insufficient_history",
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
          "recovery_and_symptom_stop_state"
        ],
        "stable_history_qualification_algorithm": "not_accepted",
        "within_recent_load_qualification_algorithm": "not_accepted"
      }
    },
    "road_marathon_reassessment_and_outcome_policy": {
      "applies_to": "reassessment and outcomes module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-marathon.pacing-prediction-retains-individual-error",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
        "environment.no-universal-personal-correction"
      ],
      "value": {
        "absence_of_improvement_proves_nonresponse": false,
        "causal_plan_effect_claim": "prohibited",
        "direct_before_after_claim_requires": [
          "comparable_distance_and_result_type",
          "known_route_or_event",
          "known_surface_and_assistance",
          "known_environment_when_available",
          "no_material_protocol_change"
        ],
        "exact_calendar_reassessment_cadence": "not_accepted",
        "exact_feedback_weighting_and_update_algorithm": "not_accepted",
        "exact_post_marathon_outcome_window": "not_accepted",
        "feedback_inputs": [
          "completed_sessions_and_adherence",
          "athlete_edits_rejections_and_preferences",
          "perceived_effort_and_reported_response",
          "recovery_and_symptom_context",
          "split_or_sample_level_training_response",
          "comparable_event_or_field_outcomes"
        ],
        "feedback_loop_required": true,
        "meaningful_change_threshold": "not_accepted",
        "next_recommendation_must_record_response_to_feedback": true,
        "outcome_comparability_algorithm": "not_accepted",
        "personal_responder_classification": "prohibited",
        "race_priority_and_conflict_resolution_rule": "not_accepted",
        "reassessment_triggers": [
          "new_or_changed_confirmed_event",
          "new_qualified_marathon_result",
          "material_training_pattern_change",
          "completed_training_and_adherence_change",
          "athlete_edit_rejection_or_reported_response",
          "recovery_or_symptom_change",
          "completed_marathon_or_maximal_event",
          "changed_availability_or_constraint",
          "changed_fueling_hydration_or_environment_context",
          "athlete_requested_review"
        ],
        "renal_recovery_used_as_general_readiness": false,
        "supporting_outcomes": [
          "split_level_pacing_and_pace_decline",
          "adherence_edit_and_rejection_burden",
          "fueling_and_gastrointestinal_response",
          "hydration_context_and_issues",
          "recovery_response",
          "weekly_volume_frequency_longest_run_and_quality_change"
        ]
      }
    },
    "road_marathon_supported_training_pattern": {
      "applies_to": "shared eligibility and distance-policy routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
      ],
      "value": {
        "adult_scope": "confirmed",
        "capability_pattern": "current_direct_outdoor_road_marathon",
        "cohort_labels_are_permanent_runner_identities": false,
        "current_concerning_symptoms": "absent",
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
          "capability_unconfirmed",
          "first_marathon_or_completion_intent",
          "sparse_interrupted_or_missing_history",
          "outside_recent_load_pattern",
          "current_injury_illness_or_concerning_symptoms",
          "clinical_rehabilitation_return_to_sport_or_medical_clearance",
          "pregnancy_specific_prescription",
          "unresolved_material_event_conflict",
          "unsupported_surface_distance_or_intent"
        ],
        "history_pattern": "stable_recent",
        "intent_pattern": "performance",
        "load_pattern": "within_recent",
        "race_dense_requires_resolved_conflicts": true
      }
    },
    "road_marathon_taper_and_recovery_policy": {
      "applies_to": "taper and recovery module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.taper-support-exact-parameters-uncertain",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
        "eligibility.current-symptoms-support-stop-not-clearance"
      ],
      "value": {
        "completed_marathon_requires_recovery_and_pattern_reassessment": true,
        "exact_frequency_rule": "not_accepted",
        "exact_intensity_exposure": "not_accepted",
        "exact_taper_window_days": "not_accepted",
        "exact_volume_reduction_percent": "not_accepted",
        "no_extra_sharpening_or_makeup": true,
        "personal_taper_gain_claim": "prohibited",
        "post_marathon_recovery_interval": "not_accepted",
        "pre_event_training_minutes_accounting": "not_accepted",
        "renal_recovery_defines_general_readiness": false,
        "return_to_quality_or_long_run_rule": "not_accepted",
        "short_horizon_alternative": "not_accepted",
        "target_event_elapsed_time_included_in_training_minutes": "not_accepted"
      }
    },
    "road_marathon_typed_outcomes_and_suggestion_only_state": {
      "applies_to": "future API and client state contract",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "value": {
        "AI_may_not": [
          "broaden_eligibility",
          "invent_capability_history_event_profile_or_safety_context",
          "choose_unaccepted_values",
          "override_deterministic_validation",
          "create_human_approval_artifacts",
          "activate_adopt_deliver_or_publish"
        ],
        "athlete_may": [
          "review",
          "edit",
          "reject",
          "explicitly_consent_to_adopt"
        ],
        "current_runtime_outcome": "plan_policy_inactive",
        "disclaimer_only_response_allowed_for_supported_safe_route": false,
        "future_generated_state_after_activation": "proposed",
        "generator_may_not": [
          "adopt_or_deliver_without_consent",
          "overwrite_adopted_future_days",
          "auto_schedule_a_maximal_marathon",
          "auto_change_event_priority",
          "schedule_missed_workout_makeup",
          "invent_fueling_hydration_or_environment_context"
        ],
        "no_plan_or_limited_outcome_must_include_actionable_resolution_path": true,
        "outcomes": {
          "capability_confirmation_required": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "environment_module_limited": {
            "degraded_modules": [
              "environment_altitude"
            ],
            "goal_remains_recorded": true,
            "plan_returned": true
          },
          "fueling_module_limited": {
            "degraded_modules": [
              "fueling_hydration_practice"
            ],
            "goal_remains_recorded": true,
            "plan_returned": true
          },
          "goal_recorded_plan_policy_unavailable": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "implementation_review_required": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "insufficient_history": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "limited_guidance_only": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false
          },
          "plan_policy_inactive": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "unresolved_event_conflict": {
            "goal_remains_recorded": true,
            "plan_returned": false
          }
        },
        "recommendation_must_include": [
          "next_action",
          "athlete_specific_rationale",
          "scientific_basis_and_applicability",
          "expected_response_or_signal",
          "uncertainty",
          "feedback_request"
        ],
        "supported_safe_route_must_return_actionable_recommendation": true
      }
    },
    "road_marathon_validation_privacy_and_open_decisions": {
      "applies_to": "validation, privacy, implementation, and rollout",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
        "road-marathon.fluid-sodium-needs-variable"
      ],
      "value": {
        "deterministic_invariant_breach_tolerance": 0,
        "deterministic_replay_mismatch_tolerance": 0,
        "dry_run_metrics_required": [
          "eligibility_and_each_typed_outcome_rate",
          "actionable_recommendation_coverage_for_supported_safe_routes",
          "recommendation_reasoning_expected_signal_and_feedback_completeness",
          "missingness_and_source_confirmation",
          "event_conflict_and_race_density",
          "subgroup_exclusion_and_edit_gaps",
          "proposal_edit_rejection_and_adoption_burden",
          "feedback_to_next_proposal_traceability",
          "fueling_hydration_and_environment_context_availability",
          "quality_event_and_long_run_stacking",
          "deterministic_replay"
        ],
        "exact_dry_run_go_no_go_thresholds": "not_accepted",
        "exact_prospective_pause_thresholds": "not_accepted",
        "implementation_mapping": "not_accepted",
        "no_inference_of": [
          "diagnosis",
          "injury_cause",
          "pregnancy_status",
          "mental_state",
          "missed_training_reason",
          "gastrointestinal_diagnosis",
          "hydration_or_sodium_diagnosis"
        ],
        "no_publication_of": [
          "raw_health_data",
          "private_activity_data",
          "inferred_sensitive_context"
        ],
        "outcome_windows_and_meaningful_change_thresholds": "not_accepted",
        "prospective_metrics_required": [
          "adoption_and_edit_distance",
          "adherence_and_burden",
          "recommendation_change_after_athlete_feedback",
          "symptom_stops_and_adverse_events",
          "fueling_and_gastrointestinal_tolerance",
          "hydration_issues",
          "comparable_marathon_outcomes",
          "withdrawal"
        ],
        "race_density_and_priority_thresholds": "not_accepted",
        "replay_record_must_include": [
          "policy_versions_and_contract_digests",
          "goal_record_state",
          "capability_and_history_sources",
          "split_or_sample_intensity_sources",
          "confirmed_event_context",
          "profile_fueling_hydration_and_environment_provenance",
          "unresolved_parameter_versions",
          "typed_outcome",
          "proposal_hash",
          "recommendation_hypothesis_and_expected_signal",
          "athlete_feedback_and_observed_outcome",
          "reassessment_reason",
          "change_from_prior_proposal"
        ],
        "runtime_activation_criteria": "not_accepted",
        "subgroup_dose_modifiers": "not_accepted",
        "target_risk_thresholds": "not_accepted",
        "unreviewed_online_learning_allowed": false
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:ffb7864995d0825713667c816f5d4c1255695fdf579857ca79c24e91c63c50f0"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If accepted by a digest-bound human decision approver, this SDR would authorize only an inactive policy boundary for adults aged 18 years or older with current direct outdoor road-marathon capability, stable recent history that anchors their own exposure, within-recent load, performance intent, optional target time or date, and athlete-confirmed event context. Goal capture remains independent from generator availability. Missing optional age, sex, or profile modifiers disable only dependent adjustments and never default to male; imported profile and event data remain source-labelled until athlete confirmation. The proposed policy is suggestion-only and modular: entry/readiness; history/load; long-run/durability; intensity/race-specific work; fueling/hydration practice; taper/recovery; environment/altitude; and reassessment/outcomes. Missing fueling, hydration, or environmental context disables or degrades only the dependent module and does not block otherwise eligible independent plan modules. For a supported safe route, a future implementation must take an actionable position rather than return disclaimer-only output. It must use applicable scientific theories and findings as bounded candidate strategies and initial priors, select and explain a proposal from the athlete's confirmed current data, and observe athlete feedback and outcomes before reassessing the next proposal. Population associations and source findings may support that reasoning and validation but not personal probability, causal dose, or target-gap escalation. No plan length, baseline algorithm, history count, weekly frequency, progression, volume, long-run dose, intensity distribution, strategy-selection or feedback-update algorithm, race-specific dose, workout, taper, recovery, fueling, hydration, environment, altitude, race-density, subgroup, outcome, pilot, implementation, or activation rule is selected. No 5 km, 10 km, or half-marathon numeric rule is inherited. This proposal does not authorize first-marathon or completion intent, sparse history, returning, clinical, rehabilitation, pregnancy-specific, trail, ultra, or unsupported contexts. A no-event rolling preparation or simulation route requires a separately accepted completion or benchmark policy and may not invent an automatic maximal marathon simulation.",
  "affected_surfaces": {
    "apis": [
      "future authenticated marathon capability and typed proposal endpoints",
      "future athlete feedback, observation, and reassessment inputs",
      "future event, profile, fueling, hydration, and environment confirmation inputs"
    ],
    "clients": [
      "generated human Evidence Review and SDR packets",
      "generated inactive machine contract",
      "future web marathon goal, readiness, event, context, proposal, consent, and no-plan states",
      "future miniapp feature, write, type, state, i18n, and consent parity",
      "future plugin and MCP capability discovery and proposal parity"
    ],
    "models": [
      "road-marathon-plan-generation-policy-v1",
      "shared dynamic training-pattern and confirmed event snapshots"
    ],
    "science_notes": [
      "Explain direct, associative, cross-sectional, abstract-bounded, and indirect evidence separately.",
      "Show what to do next, why it fits this athlete, the applicable science, expected signal, uncertainty, and what feedback can change the next recommendation.",
      "Show unresolved values, baseline source, event state, context provenance, risk, and alternatives without replacing the recommendation with disclaimers."
    ]
  },
  "applicability": [
    "Adults aged 18 years or older with adult scope confirmed",
    "Current direct athlete-confirmed outdoor road-marathon capability",
    "Stable recent running history and within-recent load",
    "Performance intent with optional target time or date",
    "Athlete-confirmed event context with unresolved conflicts excluded from a full proposal",
    "Suggestion-only future behavior after every unresolved value and implementation review is accepted",
    "Cohort labels describe evidence populations and never permanent runner identities"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-08-15",
  "decision_notes": [
    "This artifact-mode Decision proposal addresses issue #687 and remains draft and inactive.",
    "Human review must use the generated packet rather than raw YAML. The packet includes the exact inactive machine contract and digest-bound approval templates.",
    "First-marathon or completion intent, sparse history, returning, clinical, rehabilitation, pregnancy-specific, trail, ultra, and unsupported contexts require separate policies.",
    "All unresolved behavior-driving values are literal `not_accepted`; no implementation may infer a value from source findings, another distance, prose, or AI output.",
    "Impact map: draft Evidence Review -> generated evidence packet -> draft SDR -> generated decision packet and inactive contract -> human evidence and decision review -> future implementation review -> future pure policy mapping -> actionable proposal -> athlete review and adoption -> observed response and feedback -> reassessment -> API -> web and miniapp parity -> ScienceNote and localization -> offline validation -> opt-in pilot -> separately approved activation."
  ],
  "decision_review": {
    "approval_statement": "I approve the narrow currently-capable adult outdoor road-marathon performance scope, bounded evidence use, hard suggestion-only and athlete-control boundaries, and an actionable individualized evidence-informed recommendation loop. Scientific theories and findings are candidate strategies and priors rather than universal personal rules; mostly-low organization is not mandatory. Athlete feedback and observed outcomes must inform reassessment of later recommendations. Missing fueling, hydration, or environmental context degrades only the dependent module rather than blocking independent plan modules. I agree that baseline and history qualification, all dose, strategy-selection, feedback-update and race-specific work, taper and recovery, fueling, hydration and environment numbers, and secondary rollout choices remain deferred. This approval would not approve implementation, runtime activation, a plan length, or any unresolved value.",
    "items": [
      {
        "approval_effect": [
          "The narrow performance tuple and eight-module policy structure become reviewable boundaries.",
          "Goal capture remains available when this policy is unavailable or inactive.",
          "Typed no-plan and limited-guidance outcomes preserve the athlete's goal without substituting another policy."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A plan length, generated schedule, automatic marathon benchmark, implementation, or activation.",
          "Reusing a shorter-distance numeric rule or treating a cohort label as a permanent runner identity."
        ],
        "evidence_claim_ids": [
          "eligibility.goal-relevant-current-capability-task-specific",
          "eligibility.masters-age-change-not-automatic-exclusion",
          "road-marathon.task-specific-capability-baseline-multifactorial"
        ],
        "id": "narrow-modular-scope",
        "parameter_names": [
          "road_marathon_activation_and_dependency",
          "road_marathon_goal_and_event_tuple",
          "road_marathon_supported_training_pattern",
          "road_marathon_modular_policy_structure",
          "road_marathon_typed_outcomes_and_suggestion_only_state"
        ],
        "proposed_decision": "Accept that narrow tuple and the eight-module boundary. Keep first-marathon/completion, sparse-history, returning or clinical, pregnancy-specific, trail, ultra, and unsupported contexts in separate policies. A no-event rolling preparation or simulation route requires a separately accepted completion or benchmark policy.",
        "question": "Should V1 recognize only currently-capable adults with stable recent history, within-recent load, road-marathon performance intent, and confirmed event context, while preserving goals when no route matches?",
        "title": "Accept the narrow population tuple and modular boundary"
      },
      {
        "approval_effect": [
          "Published findings may appear in review notes, source explanations, and validation design.",
          "Outcome comparisons remain descriptive and require comparable protocols and context."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Turning any reported category, coefficient, percentage, correlation, or subgroup observation into an individual rule.",
          "A personal success, injury, safety, responder, hydration, fueling, or environmental probability."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "road-marathon.volume-frequency-longest-run-associative",
          "road-marathon.durability-relevant-no-field-cutoff",
          "road-marathon.marathon-tid-mostly-low-observational",
          "road-marathon.taper-support-exact-parameters-uncertain",
          "road-marathon.pacing-prediction-retains-individual-error",
          "road-marathon.carbohydrate-support-contextual",
          "road-marathon.gut-training-tolerance-not-universal",
          "road-marathon.fluid-sodium-needs-variable",
          "road-marathon.altitude-capacity-no-personal-correction",
          "environment.no-universal-personal-correction"
        ],
        "id": "evidence-use",
        "parameter_names": [
          "road_marathon_published_volume_and_long_run_findings",
          "road_marathon_published_durability_findings",
          "road_marathon_published_intensity_distribution_findings",
          "road_marathon_published_taper_findings",
          "road_marathon_published_fueling_and_gut_findings",
          "road_marathon_published_fluid_and_sodium_findings",
          "road_marathon_published_environment_and_altitude_findings",
          "road_marathon_reassessment_and_outcome_policy"
        ],
        "proposed_decision": "Retain the observed prediction error, volume and longest-run associations, durability, training-intensity distribution, taper, carbohydrate, gut-tolerance, fluid, sodium, environment, and altitude findings with their directness and uncertainty labels.",
        "question": "Should the reviewed marathon and broader-endurance findings be retained only as source findings, qualitative context, and future validation inputs rather than personal probabilities or causal prescriptions?",
        "title": "Accept bounded use of population findings and uncertainty"
      },
      {
        "approval_effect": [
          "Missing module-specific context disables or degrades only the dependent module rather than blocking otherwise eligible independent plan modules.",
          "Eligibility, safety, capability, history, or unresolved event conflicts may still produce a typed no-plan result.",
          "AI may explain reviewable inputs but cannot choose unresolved values, approve, activate, adopt, deliver, or publish.",
          "Athlete constraints and consent remain authoritative."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Any unresolved numeric or algorithmic value in the same contract groups.",
          "Medical diagnosis, treatment, clearance, sensitive inference, or a safety guarantee."
        ],
        "evidence_claim_ids": [
          "eligibility.fixed-progression-and-acwr-not-safety-laws",
          "eligibility.current-symptoms-support-stop-not-clearance",
          "eligibility.evidence-quality-no-personal-probability",
          "road-marathon.task-specific-capability-baseline-multifactorial",
          "road-marathon.pacing-prediction-retains-individual-error",
          "road-marathon.fluid-sodium-needs-variable",
          "heat-safety.separate-from-adaptation"
        ],
        "id": "hard-boundaries",
        "parameter_names": [
          "road_marathon_profile_and_source_provenance",
          "road_marathon_direct_baseline_hierarchy",
          "road_marathon_readiness_and_history_qualification",
          "road_marathon_history_anchored_load_policy",
          "road_marathon_long_run_and_durability_policy",
          "road_marathon_intensity_and_race_specific_policy",
          "road_marathon_taper_and_recovery_policy",
          "road_marathon_fueling_and_hydration_policy",
          "road_marathon_environment_and_altitude_policy",
          "road_marathon_reassessment_and_outcome_policy",
          "road_marathon_typed_outcomes_and_suggestion_only_state",
          "road_marathon_validation_privacy_and_open_decisions"
        ],
        "proposed_decision": "Accept those prohibitions. Require direct confirmed capability, source-labelled inputs, activity splits or samples for intensity, deterministic validation, symptom stops, minimum-necessary data, and separate evidence, decision, implementation, and activation authority.",
        "question": "Should every future proposal remain athlete-editable and explicitly adopted, with no automatic maximal marathon test, target-gap escalation, catch-up, activity-average-power intensity analysis, hidden demographic default, unconfirmed imported context, or AI authority expansion?",
        "title": "Accept hard control, consent, data, and automation boundaries"
      },
      {
        "approval_effect": [
          "A supported safe route must return an actionable recommendation, athlete-specific rationale, expected signal, uncertainty, and feedback request.",
          "Scientific theories and findings may bound and rank candidate strategies but may not become permanent runner identities or universal personal rules.",
          "Completed training, adherence, edits, rejection, reported response, recovery, symptoms, and comparable outcomes must be available to reassess the next proposal.",
          "Safety boundaries may pause or narrow a recommendation, but ordinary uncertainty may not replace product value with disclaimers."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A fixed intensity distribution, mandatory mostly-low pattern, exact strategy-selection or feedback-update algorithm, race-specific workout, or distance-only nutrition rule.",
          "Ungoverned online learning, a causal responder label, medical treatment, personal environmental correction, acclimation schedule, or safety guarantee."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "road-marathon.durability-relevant-no-field-cutoff",
          "road-marathon.marathon-tid-mostly-low-observational",
          "road-marathon.pacing-prediction-retains-individual-error",
          "road-marathon.carbohydrate-support-contextual",
          "road-marathon.gut-training-tolerance-not-universal",
          "road-marathon.fluid-sodium-needs-variable",
          "road-marathon.altitude-capacity-no-personal-correction",
          "environment.heat-balance-multifactor",
          "heat-adaptation.repeated-exposure"
        ],
        "id": "adaptive-evidence-informed-loop",
        "parameter_names": [
          "road_marathon_modular_policy_structure",
          "road_marathon_published_durability_findings",
          "road_marathon_long_run_and_durability_policy",
          "road_marathon_published_intensity_distribution_findings",
          "road_marathon_intensity_and_race_specific_policy",
          "road_marathon_published_fueling_and_gut_findings",
          "road_marathon_fueling_and_hydration_policy",
          "road_marathon_published_fluid_and_sodium_findings",
          "road_marathon_published_environment_and_altitude_findings",
          "road_marathon_environment_and_altitude_policy",
          "road_marathon_reassessment_and_outcome_policy",
          "road_marathon_typed_outcomes_and_suggestion_only_state",
          "road_marathon_validation_privacy_and_open_decisions"
        ],
        "proposed_decision": "Require a future supported implementation to recommend what the athlete should do next, explain why it fits the athlete and which evidence applies, state the expected response and uncertainty, and ask for the feedback needed for reassessment. Use mostly-low organization, durability, fueling practice, and environmental findings as candidate context rather than mandatory templates. Preserve safety stops while prohibiting disclaimer-only output for a supported safe route.",
        "question": "Should V1 require Praxys to take an actionable, science-grounded position for a supported safe route, treat theories and findings as candidate strategies rather than universal rules, and use athlete feedback and observed outcomes to reassess later recommendations?",
        "title": "Accept an actionable individualized recommendation and feedback loop"
      },
      {
        "approval_effect": [
          "Missing or unconfirmed capability returns capability_confirmation_required.",
          "Insufficient stable recent history returns insufficient_history."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A result expiry, distance tolerance, event qualification rule, minimum week or run count, or automatic maximal marathon test.",
          "A shorter-distance conversion as direct current marathon capability."
        ],
        "evidence_claim_ids": [
          "eligibility.recent-history-anchor-without-universal-threshold",
          "eligibility.goal-relevant-current-capability-task-specific",
          "road-marathon.task-specific-capability-baseline-multifactorial",
          "road-marathon.pacing-prediction-retains-individual-error"
        ],
        "id": "defer-baseline-history",
        "parameter_names": [
          "road_marathon_direct_baseline_hierarchy",
          "road_marathon_readiness_and_history_qualification"
        ],
        "proposed_decision": "Keep every baseline and history algorithm unaccepted until a later decision compares options, missingness, and validation consequences.",
        "question": "Should exact direct-result qualification, freshness, distance and event validation, lookback, minimum history counts, and current-load qualification remain unresolved?",
        "title": "Defer qualification, freshness, history counts, and capability algorithm"
      },
      {
        "approval_effect": [
          "A future decision must select and validate each behavior-driving value and adaptation rule explicitly.",
          "Target gap and missed sessions cannot create escalation or catch-up."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A plan horizon, weekly frequency or volume, progression, long-run prescription, quality count, spacing, session mix, workout template, or hidden adaptation rule.",
          "A mandatory mostly-low pattern, durability score, or activity-average-power intensity rule."
        ],
        "evidence_claim_ids": [
          "eligibility.fixed-progression-and-acwr-not-safety-laws",
          "road-marathon.volume-frequency-longest-run-associative",
          "road-marathon.durability-relevant-no-field-cutoff",
          "road-marathon.marathon-tid-mostly-low-observational"
        ],
        "id": "defer-dose-specific-work",
        "parameter_names": [
          "road_marathon_history_anchored_load_policy",
          "road_marathon_long_run_and_durability_policy",
          "road_marathon_intensity_and_race_specific_policy"
        ],
        "proposed_decision": "Keep every dose, schedule, strategy-selection, and feedback-update value unaccepted. Retain the approved individualized recommendation loop and hard prohibitions without pretending the exact algorithm has been selected.",
        "question": "Should plan length, frequency, progression, volume, long-run distance/duration/share/cap, durability cutoff, marathon-pace or race-specific work, quality ceiling and spacing, exact workouts, strategy selection, and feedback-driven update rules remain unresolved?",
        "title": "Defer plan length, dose, long-run, intensity, and race-specific work"
      },
      {
        "approval_effect": [
          "A completed marathon triggers reassessment without claiming general readiness.",
          "Observational taper effects remain source findings only."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A three-week taper prescription, fixed percentage reduction, recovery interval, event-minute formula, or meaningful-change window.",
          "Treating renal recovery as medical clearance or general training readiness."
        ],
        "evidence_claim_ids": [
          "road-marathon.taper-support-exact-parameters-uncertain",
          "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
        ],
        "id": "defer-taper-recovery",
        "parameter_names": [
          "road_marathon_taper_and_recovery_policy",
          "road_marathon_reassessment_and_outcome_policy"
        ],
        "proposed_decision": "Keep exact taper, recovery, reassessment, and outcome timing unaccepted while preserving the no-makeup and post-event reassessment boundaries.",
        "question": "Should taper window and reduction, intensity and frequency handling, short-horizon alternative, event-minute accounting, recovery spacing, reassessment cadence, and fixed outcome windows remain unresolved?",
        "title": "Defer taper, event accounting, recovery, and reassessment cadence"
      },
      {
        "approval_effect": [
          "Missing fueling context returns fueling_module_limited while otherwise eligible independent plan modules remain available.",
          "Missing material environmental context returns environment_module_limited while otherwise eligible independent plan modules remain available."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A distance-only intake, fluid, sodium, loading, sweat, or gut-training rule.",
          "A personal pace correction, finish-time correction, or altitude acclimation schedule."
        ],
        "evidence_claim_ids": [
          "road-marathon.carbohydrate-support-contextual",
          "road-marathon.gut-training-tolerance-not-universal",
          "road-marathon.fluid-sodium-needs-variable",
          "road-marathon.altitude-capacity-no-personal-correction",
          "environment.full-wbgt-inputs",
          "environment.no-universal-personal-correction",
          "heat-adaptation.repeated-exposure",
          "heat-safety.separate-from-adaptation"
        ],
        "id": "defer-fueling-hydration-environment",
        "parameter_names": [
          "road_marathon_fueling_and_hydration_policy",
          "road_marathon_environment_and_altitude_policy"
        ],
        "proposed_decision": "Keep every behavior-driving nutrition, hydration, environmental, and altitude value unaccepted. Require practiced context and complete environmental inputs before any future dependent suggestion, while preserving independent plan modules when that context is missing.",
        "question": "Should loading, duration, intake, fluid, sodium, gut-training numbers and prompts, plus environmental and altitude corrections and acclimation schedules, remain unresolved?",
        "title": "Defer fueling, hydration, environmental, and altitude values"
      },
      {
        "approval_effect": [
          "Deterministic invariant and replay tolerance remain zero.",
          "Every statistical, subgroup, event-density, outcome, implementation, and activation choice remains explicit future work."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Implementing unresolved values, advertising capability, starting a pilot, or activating any runtime surface.",
          "Treating science decision approval as implementation or activation approval."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "eligibility.masters-age-change-not-automatic-exclusion",
          "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
        ],
        "id": "defer-secondary-rollout",
        "parameter_names": [
          "road_marathon_supported_training_pattern",
          "road_marathon_reassessment_and_outcome_policy",
          "road_marathon_validation_privacy_and_open_decisions"
        ],
        "proposed_decision": "Keep the contract inactive and require separate human review of every secondary rule, deterministic implementation mapping, and opt-in pilot threshold before runtime use.",
        "question": "Should target-risk thresholds, race-density and priority rules, subgroup dose modifiers, outcome windows and meaningful-change thresholds, pilot criteria, implementation mapping, and activation remain unresolved?",
        "title": "Defer target risk, race density, subgroup, outcomes, pilot, implementation, and activation"
      }
    ],
    "reviewer_task": "Decide whether the four proposed boundaries are acceptable and whether the five listed implementation areas should remain explicitly deferred. Approve the sheet as a unit or request changes by item ID. The audit appendix is traceability, not the primary review task."
  },
  "evidence_claim_ids": [
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.fixed-progression-and-acwr-not-safety-laws",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.current-symptoms-support-stop-not-clearance",
    "eligibility.evidence-quality-no-personal-probability",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "road-marathon.task-specific-capability-baseline-multifactorial",
    "road-marathon.volume-frequency-longest-run-associative",
    "road-marathon.durability-relevant-no-field-cutoff",
    "road-marathon.marathon-tid-mostly-low-observational",
    "road-marathon.taper-support-exact-parameters-uncertain",
    "road-marathon.pacing-prediction-retains-individual-error",
    "road-marathon.carbohydrate-support-contextual",
    "road-marathon.gut-training-tolerance-not-universal",
    "road-marathon.fluid-sodium-needs-variable",
    "road-marathon.altitude-capacity-no-personal-correction",
    "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
    "environment.heat-balance-multifactor",
    "environment.relative-humidity-insufficient",
    "environment.wbgt-population-performance",
    "environment.temperature-nonlinear",
    "environment.marathon-wbgt-performance-level",
    "environment.full-wbgt-inputs",
    "environment.no-universal-personal-correction",
    "heat-adaptation.repeated-exposure",
    "heat-safety.separate-from-adaptation"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-road-marathon-plan-generation-policy-v1",
    "evidence-environmental-performance-v1",
    "evidence-heat-adaptation-v1"
  ],
  "falsification_conditions": [
    "Reject the product behavior if an otherwise supported safe route returns disclaimers, caveats, or data summaries without a concrete next action, athlete-specific rationale, expected signal, uncertainty, and feedback request.",
    "Reject the policy if any implementation emits a plan while the decision or contract is draft or inactive, consumes an unaccepted value, or omits a code-consumed field from the human review packet.",
    "Reject routing if prediction, critical speed, shorter-distance conversion, passive segment, unconfirmed provider result, or activity average power is treated as direct current marathon capability or intensity evidence.",
    "Reject schedule mapping if observational source categories, durability correlations, pyramidal prevalence, taper effects, or target gap become eligibility or dose rules, or if mostly-low organization becomes a mandatory template rather than one candidate prior.",
    "Reject the feedback loop if athlete completion, edits, rejection, reported response, recovery, symptoms, or comparable outcomes cannot be traced into reassessment of the next proposal, or if an unreviewed online learner changes policy outside the versioned contract.",
    "Reject no-event routing if it creates a maximal marathon simulation without a separately accepted completion or benchmark policy.",
    "Reject fueling or hydration behavior if distance alone selects loading, intake, fluid, sodium, gut-training, or race-day strategy.",
    "Reject modular routing if missing fueling, hydration, or environmental context blocks otherwise eligible independent plan modules or is replaced with an invented value.",
    "Reject environmental behavior if population weather or chamber altitude findings become a personal correction, acclimation schedule, clearance, or guarantee.",
    "Pause future activation after any deterministic invariant or replay breach, symptom-stop override, hidden demographic default, unconfirmed source use, unresolved event conflict, unsupported population, consent bypass, or approval-digest mismatch."
  ],
  "id": "sdr-road-marathon-plan-generation-policy-v1",
  "model_parameters": [
    {
      "applies_to": "policy lifecycle and capability discovery",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_marathon_activation_and_dependency",
      "rationale": "Draft records, generated packets, and a science decision cannot activate product behavior. Evidence, decision, implementation, and runtime authority remain distinct.",
      "value": {
        "active_behavior": false,
        "capability_registry_entry_default_enabled": false,
        "decision_approval_artifact_required": true,
        "distance_decision_required_status_before_activation": "accepted",
        "distance_evidence_required_status_before_activation": "accepted",
        "evidence_review_approval_artifact_required": true,
        "generator_api_web_miniapp_plugin_and_mcp_activation_in_this_record": false,
        "implementation_approval_artifact_required": true,
        "runtime_state": "inactive",
        "shared_policy_dependency": {
          "required_status_before_activation": "accepted",
          "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
        }
      }
    },
    {
      "applies_to": "goal normalization and marathon policy selection",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-marathon.task-specific-capability-baseline-multifactorial"
      ],
      "name": "road_marathon_goal_and_event_tuple",
      "rationale": "Goal choice is durable user state. This policy is a narrow capability, intent, surface, and evidence route rather than the definition of a valid goal.",
      "value": {
        "event_context_must_be_athlete_confirmed": true,
        "goal_capture_independent_from_generator_availability": true,
        "goal_intent": "performance",
        "goal_kind": "distance_marathon",
        "no_event_goal": {
          "automatic_maximal_marathon_simulation": "prohibited",
          "goal_remains_recorded": true,
          "rolling_preparation_or_simulation_requires_separately_accepted_completion_or_benchmark_policy": true
        },
        "primary_outcome": "elapsed_time",
        "separate_policy_variants": [
          "first_marathon_or_completion_intent",
          "sparse_or_missing_history",
          "returning_after_interruption",
          "clinical_rehabilitation_or_return_to_sport",
          "pregnancy_specific_planning",
          "trail_marathon",
          "ultramarathon",
          "unsupported_surface_event_or_context"
        ],
        "sport": "running",
        "surface": "outdoor_road",
        "target_date_optional": true,
        "target_time_optional": true,
        "unavailable_policy_result": "goal_recorded_plan_policy_unavailable"
      }
    },
    {
      "applies_to": "shared eligibility and distance-policy routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
      ],
      "name": "road_marathon_supported_training_pattern",
      "rationale": "The route matches a time-bounded evidence pattern rather than a permanent recreational, amateur, female, male, faster, elite, or masters identity.",
      "value": {
        "adult_scope": "confirmed",
        "capability_pattern": "current_direct_outdoor_road_marathon",
        "cohort_labels_are_permanent_runner_identities": false,
        "current_concerning_symptoms": "absent",
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
          "capability_unconfirmed",
          "first_marathon_or_completion_intent",
          "sparse_interrupted_or_missing_history",
          "outside_recent_load_pattern",
          "current_injury_illness_or_concerning_symptoms",
          "clinical_rehabilitation_return_to_sport_or_medical_clearance",
          "pregnancy_specific_prescription",
          "unresolved_material_event_conflict",
          "unsupported_surface_distance_or_intent"
        ],
        "history_pattern": "stable_recent",
        "intent_pattern": "performance",
        "load_pattern": "within_recent",
        "race_dense_requires_resolved_conflicts": true
      }
    },
    {
      "applies_to": "profile, event, and missing-data handling",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "eligibility.evidence-quality-no-personal-probability",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
      ],
      "name": "road_marathon_profile_and_source_provenance",
      "rationale": "Optional modifiers cannot become hidden demographic assumptions or unnecessary eligibility barriers. Athlete confirmation and field-level provenance preserve accuracy and control.",
      "value": {
        "adult_scope_confirmation_required": true,
        "imported_profile_and_event_fields": {
          "may_not_overwrite_athlete_confirmed_value": true,
          "missing_is_unknown_not_false": true,
          "remain_source_labelled_until_athlete_confirmation": true
        },
        "minimum_necessary_inputs_only": true,
        "missing_optional_modifier_effect": "disable_dependent_adjustment_only",
        "optional_modifier_fields": [
          "age_or_age_band",
          "sex",
          "profile_attributes",
          "prior_marathon_count",
          "environmental_history",
          "fueling_and_gastrointestinal_history"
        ],
        "unknown_sex_defaults_to_male": false
      }
    },
    {
      "applies_to": "direct capability confirmation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-marathon.task-specific-capability-baseline-multifactorial",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "name": "road_marathon_direct_baseline_hierarchy",
      "rationale": "Same-task confirmed history is most direct. Predictions and supporting markers retain material individual error and cannot silently qualify a runner or trigger a maximal marathon effort.",
      "value": {
        "accepted_assistance_statuses": "not_accepted",
        "accepted_event_qualification": "not_accepted",
        "automatic_maximal_marathon_baseline_test": "prohibited",
        "baseline_freshness_completed_days": "not_accepted",
        "baseline_qualification_algorithm": "not_accepted",
        "direct_current_capability_required": true,
        "distance_match_tolerance_m": "not_accepted",
        "excluded_as_direct": [
          "shorter_distance_conversion",
          "critical_speed_prediction",
          "passive_marathon_segment_within_ultra",
          "unconfirmed_provider_personal_best",
          "activity_average_power",
          "vendor_readiness_or_race_score",
          "policy_generated_maximal_marathon_simulation"
        ],
        "missing_or_unconfirmed_outcome": "capability_confirmation_required",
        "preferred_direct_evidence": [
          "athlete_confirmed_official_or_organized_outdoor_road_marathon_result"
        ],
        "required_metadata": [
          "completed_at",
          "elapsed_time_seconds",
          "measured_distance_m",
          "route_or_event_identifier",
          "surface",
          "assistance_status",
          "source_provider",
          "athlete_confirmation_state"
        ],
        "supporting_only": [
          "shorter_distance_race_result",
          "critical_speed_or_threshold",
          "current_vo2max_or_vvo2max",
          "weekly_training_volume_and_frequency",
          "recent_longest_run",
          "marathon_prediction_with_error",
          "split_or_sample_pacing_distribution"
        ]
      }
    },
    {
      "applies_to": "readiness and history-rich qualification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-marathon.volume-frequency-longest-run-associative"
      ],
      "name": "road_marathon_readiness_and_history_qualification",
      "rationale": "Recent history must anchor the athlete's own exposure, but the literature does not establish universal counts or a safe-load algorithm. Intensity requires split-level or sample-level evidence.",
      "value": {
        "disallowed_intensity_source": [
          "activity_avg_power"
        ],
        "exact_history_lookback_weeks": "not_accepted",
        "insufficient_history_outcome": "insufficient_history",
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
          "recovery_and_symptom_stop_state"
        ],
        "stable_history_qualification_algorithm": "not_accepted",
        "within_recent_load_qualification_algorithm": "not_accepted"
      }
    },
    {
      "applies_to": "policy composition and review",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated"
      ],
      "name": "road_marathon_modular_policy_structure",
      "rationale": "Modular boundaries keep missing context and unaccepted values local and visible. They prevent one opaque schedule from hiding unsupported behavior.",
      "value": {
        "disclaimer_only_output_allowed_for_supported_safe_route": false,
        "each_module_must_declare": [
          "required_inputs",
          "missingness_effect",
          "evidence_or_guardrail_provenance",
          "athlete_editability",
          "typed_outcome"
        ],
        "feedback_loop_stages": [
          "sense_current_state",
          "select_candidate_strategy",
          "propose_reviewable_action",
          "athlete_review_edit_reject_or_adopt",
          "observe_completion_response_and_outcome",
          "reassess_next_recommendation"
        ],
        "missing_context_disables_or_degrades_dependent_module_only": true,
        "missing_context_may_block_independent_modules": false,
        "modules": [
          "entry_readiness",
          "history_load",
          "long_run_durability",
          "intensity_race_specific_work",
          "fueling_hydration_practice",
          "taper_recovery",
          "environment_altitude",
          "reassessment_outcomes"
        ],
        "plan_length_selected": false,
        "recommendation_must_declare": [
          "next_action",
          "athlete_specific_rationale",
          "scientific_basis_and_applicability",
          "expected_response_or_signal",
          "uncertainty",
          "feedback_needed_for_reassessment"
        ],
        "scientific_evidence_roles": [
          "bound_candidate_strategies",
          "inform_initial_prior",
          "explain_athlete_specific_recommendation",
          "define_expected_and_contradictory_signals"
        ],
        "supported_route_must_take_actionable_position": true,
        "unresolved_dependent_module_preserves_goal_record": true,
        "unresolved_module_cannot_be_filled_by_another_distance_policy": true
      }
    },
    {
      "applies_to": "evidence display and future validation design",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.volume-frequency-longest-run-associative"
      ],
      "name": "road_marathon_published_volume_and_long_run_findings",
      "rationale": "These values reproduce source findings for explanation and validation. They are not minima, maxima, targets, safe thresholds, or causal doses.",
      "value": {
        "eligibility_or_prescription_established": false,
        "frequency_and_experience_association_descriptive_only": true,
        "longest_run_findings": {
          "above_35_km_vs_30_to_35": {
            "significantly_better": false
          },
          "below_25_km": {
            "confidence_interval_minutes": {
              "high": 21.55,
              "low": 5.34
            },
            "finish_time_coefficient_minutes": 13.44
          }
        },
        "observational_only": true,
        "study_population": "adult_recreational_marathon_entrants",
        "weekly_volume_findings": {
          "above_65_km_per_week_vs_40_to_65": {
            "confidence_interval_minutes": {
              "high": -5.72,
              "low": -22.47
            },
            "finish_time_coefficient_minutes": -14.09
          },
          "below_40_km_per_week_vs_40_to_65": {
            "confidence_interval_minutes": {
              "high": 12.48,
              "low": 0.18
            },
            "finish_time_coefficient_minutes": 6.33
          }
        }
      }
    },
    {
      "applies_to": "plan horizon and weekly exposure",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.fixed-progression-and-acwr-not-safety-laws",
        "road-marathon.volume-frequency-longest-run-associative",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "name": "road_marathon_history_anchored_load_policy",
      "rationale": "Population associations and prediction error do not choose an individual plan length, frequency, volume, or progression. Athlete constraints cap future suggestions but do not prove an optimal dose.",
      "value": {
        "acwr_prescription_zone_used": false,
        "athlete_availability_is_hard_cap": true,
        "current_load_comparison_method": "not_accepted",
        "missed_workout_catch_up_allowed": false,
        "plan_length_days": "not_accepted",
        "shorter_distance_numeric_rules_inherited": false,
        "target_gap_may_raise_load": false,
        "ten_percent_rule_used": false,
        "weekly_progression_rule": "not_accepted",
        "weekly_running_frequency_range": "not_accepted",
        "weekly_volume_target_or_range": "not_accepted"
      }
    },
    {
      "applies_to": "durability evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.durability-relevant-no-field-cutoff"
      ],
      "name": "road_marathon_published_durability_findings",
      "rationale": "The values are descriptive source findings from a small male cross-sectional sample and cannot define an automated cutoff or dose.",
      "value": {
        "causal_or_field_cutoff_established": false,
        "design": "cross_sectional",
        "longest_run_correlation_with_deterioration": -0.67,
        "running_economy_deterioration_percent": {
          "better_durability_group": 3.1,
          "lower_durability_group": 6.0
        },
        "study_population": "26_performance_matched_well_trained_men",
        "training_volume_correlation_with_deterioration": -0.48
      }
    },
    {
      "applies_to": "long-run and durability module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.volume-frequency-longest-run-associative",
        "road-marathon.durability-relevant-no-field-cutoff"
      ],
      "name": "road_marathon_long_run_and_durability_policy",
      "rationale": "Durability and long-run history are relevant descriptive context, but no reviewed source selects a standardized field cutoff or exact long-run prescription.",
      "value": {
        "durability_field_cutoff": "not_accepted",
        "durability_field_protocol": "not_accepted",
        "durability_score_used_for_eligibility_or_dose": false,
        "exact_long_run_cap": "not_accepted",
        "exact_long_run_distance": "not_accepted",
        "exact_long_run_duration": "not_accepted",
        "exact_long_run_frequency": "not_accepted",
        "exact_long_run_share_of_weekly_volume": "not_accepted",
        "mandatory_overdistance_run": false,
        "regular_long_run_is_qualitative_context": true
      }
    },
    {
      "applies_to": "intensity-distribution evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.marathon-tid-mostly-low-observational"
      ],
      "name": "road_marathon_published_intensity_distribution_findings",
      "rationale": "The direct marathon dataset describes population organization. It does not choose one athlete's percentage, session count, spacing, or workout mix.",
      "value": {
        "causal_optimum_or_individual_dose_established": false,
        "faster_runners_accumulated_more_zone_one_volume": true,
        "fastest_group_pyramidal_distribution_percent": {
          "greater_than": 80
        },
        "marathons_analysed": 151813,
        "observational": true,
        "runners_analysed": 119452,
        "zone_definition_dependent": true
      }
    },
    {
      "applies_to": "intensity and race-specific work module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.marathon-tid-mostly-low-observational",
        "road-marathon.durability-relevant-no-field-cutoff",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "name": "road_marathon_intensity_and_race_specific_policy",
      "rationale": "Mostly-low organization is a common observational pattern and one candidate prior, not a universal rule. The athlete's confirmed current pattern, constraints, goal, evidence applicability, and observed response must shape future organization. Every exact selection, update, distribution, race-specific exposure, session count, spacing rule, and workout remains a separate decision.",
      "value": {
        "activity_avg_power_allowed": false,
        "durability_used_as_descriptive_context_only": true,
        "exact_feedback_adjustment_algorithm": "not_accepted",
        "exact_hours_or_days_between_quality_sessions": "not_accepted",
        "exact_low_intensity_fraction": "not_accepted",
        "exact_session_mix": "not_accepted",
        "exact_strategy_selection_algorithm": "not_accepted",
        "exact_workout_templates": "not_accepted",
        "individualized_training_organization_required": true,
        "intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "marathon_pace_or_race_specific_dose": "not_accepted",
        "maximum_quality_sessions_per_7_day_unit": "not_accepted",
        "missed_quality_makeup_allowed": false,
        "mostly_low_intensity_organization_required": false,
        "mostly_low_organization_is_candidate_scientific_prior": true,
        "organization_must_be_reassessed_from_feedback": true,
        "organization_selection_inputs": [
          "athlete_confirmed_recent_training_pattern",
          "current_capability_and_load_pattern",
          "goal_intent_and_event_context",
          "availability_constraints_and_preferences",
          "applicable_scientific_theories_and_findings",
          "observed_response_and_athlete_feedback"
        ],
        "race_specific_work_may_be_a_future_module": true,
        "scientific_pattern_is_permanent_runner_identity": false,
        "selected_distribution_model": "not_accepted",
        "target_gap_may_add_quality": false
      }
    },
    {
      "applies_to": "taper evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.taper-support-exact-parameters-uncertain"
      ],
      "name": "road_marathon_published_taper_findings",
      "rationale": "The marathon result is observational and the pooled values are indirect. They remain source findings rather than the selected product taper.",
      "value": {
        "marathon_observational_finding": {
          "causal_or_fixed_personal_benefit": false,
          "median_benefit_percent_vs_minimal_taper": 2.6,
          "median_benefit_seconds_vs_minimal_taper": 332.4,
          "strict_taper_duration_weeks": 3
        },
        "mixed_endurance_meta_analysis": {
          "direct_road_marathon_validation": false,
          "duration_8_to_14_days_standardized_mean_difference": {
            "confidence_interval": {
              "high": -0.19,
              "low": -2.75
            },
            "estimate": -1.47
          },
          "maintain_frequency": true,
          "maintain_intensity": true,
          "time_trial_standardized_mean_difference": {
            "confidence_interval": {
              "high": -0.23,
              "low": -0.68
            },
            "estimate": -0.45
          },
          "volume_reduction_41_to_60_percent_standardized_mean_difference": {
            "confidence_interval": {
              "high": -0.3,
              "low": -1.23
            },
            "estimate": -0.77
          }
        }
      }
    },
    {
      "applies_to": "taper and recovery module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.taper-support-exact-parameters-uncertain",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
        "eligibility.current-symptoms-support-stop-not-clearance"
      ],
      "name": "road_marathon_taper_and_recovery_policy",
      "rationale": "Taper and recovery evidence does not select one schedule, accounting method, readiness interval, or short-horizon alternative.",
      "value": {
        "completed_marathon_requires_recovery_and_pattern_reassessment": true,
        "exact_frequency_rule": "not_accepted",
        "exact_intensity_exposure": "not_accepted",
        "exact_taper_window_days": "not_accepted",
        "exact_volume_reduction_percent": "not_accepted",
        "no_extra_sharpening_or_makeup": true,
        "personal_taper_gain_claim": "prohibited",
        "post_marathon_recovery_interval": "not_accepted",
        "pre_event_training_minutes_accounting": "not_accepted",
        "renal_recovery_defines_general_readiness": false,
        "return_to_quality_or_long_run_rule": "not_accepted",
        "short_horizon_alternative": "not_accepted",
        "target_event_elapsed_time_included_in_training_minutes": "not_accepted"
      }
    },
    {
      "applies_to": "fueling and gut-practice evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.carbohydrate-support-contextual",
        "road-marathon.gut-training-tolerance-not-universal"
      ],
      "name": "road_marathon_published_fueling_and_gut_findings",
      "rationale": "The values reproduce bounded source findings. They do not define product duration bands, intake, loading, prompts, or guaranteed tolerance.",
      "value": {
        "acute_carbohydrate_supports_prolonged_endurance_performance_at_population_level": true,
        "direct_distance_only_marathon_prescription": false,
        "gut_training_findings": {
          "carbohydrate_malabsorption_reduction_percent": {
            "high": 54,
            "low": 45
          },
          "gastrointestinal_discomfort_reduction_percent": 47
        },
        "loading_and_intake_are_contextual": true,
        "universal_protocol_or_guaranteed_adaptation": false
      }
    },
    {
      "applies_to": "fueling, hydration, and practice module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.carbohydrate-support-contextual",
        "road-marathon.gut-training-tolerance-not-universal",
        "road-marathon.fluid-sodium-needs-variable"
      ],
      "name": "road_marathon_fueling_and_hydration_policy",
      "rationale": "Practiced fueling is a qualitative boundary. Exact intake, loading, gut-training, fluid, sodium, sweat, and prompt rules require separate review and athlete context.",
      "value": {
        "carbohydrate_loading_rule": "not_accepted",
        "distance_only_routing_allowed": false,
        "during_exercise_intake_rule": "not_accepted",
        "fluid_millilitres_per_hour_rule": "not_accepted",
        "fueling_prompt_content_and_timing": "not_accepted",
        "gut_training_protocol": "not_accepted",
        "hydration_prompt_content_and_timing": "not_accepted",
        "medical_or_dietetic_treatment_claim": false,
        "missing_context_blocks_independent_plan_modules": false,
        "missing_material_context_outcome": "fueling_module_limited",
        "new_race_day_strategy_without_practice": "prohibited",
        "practiced_strategy_required_before_race_day_suggestion": true,
        "required_context": [
          "expected_event_duration_context",
          "prior_carbohydrate_practice",
          "prior_gastrointestinal_tolerance_or_issue",
          "fluid_and_sodium_practice",
          "environment_context",
          "athlete_preference"
        ],
        "sodium_rule": "not_accepted",
        "sweat_or_body_mass_loss_rule": "not_accepted"
      }
    },
    {
      "applies_to": "fluid and sodium evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.fluid-sodium-needs-variable"
      ],
      "name": "road_marathon_published_fluid_and_sodium_findings",
      "rationale": "The position, consensus, and variability review support a contextual safety boundary rather than one personal replacement prescription.",
      "value": {
        "both_under_replacement_and_overdrinking_matter": true,
        "distance_only_millilitres_per_hour_or_sodium_rule_validated": false,
        "exercise_associated_hyponatremia_is_a_separate_safety_boundary": true,
        "fluid_needs_vary_with_athlete_and_context": true,
        "sweat_rate_and_sodium_show_intra_and_interindividual_variability": true
      }
    },
    {
      "applies_to": "environment and altitude evidence context",
      "classification": "published",
      "evidence_claim_ids": [
        "road-marathon.altitude-capacity-no-personal-correction",
        "environment.heat-balance-multifactor",
        "environment.relative-humidity-insufficient",
        "environment.wbgt-population-performance",
        "environment.temperature-nonlinear",
        "environment.marathon-wbgt-performance-level",
        "environment.no-universal-personal-correction",
        "heat-adaptation.repeated-exposure",
        "heat-safety.separate-from-adaptation"
      ],
      "name": "road_marathon_published_environment_and_altitude_findings",
      "rationale": "The source findings establish descriptive environmental and acute capacity context. They do not define a personal pace, time, safety, or acclimation rule.",
      "value": {
        "acute_altitude_chamber_findings_per_1000_m": {
          "fixed_speed_time_to_exhaustion_change_percent": -14.5,
          "vo2max_change_percent": -6.3
        },
        "altitude_findings_are_marathon_corrections": false,
        "environmental_heat_context": {
          "heat_balance_is_multifactorial": true,
          "marathon_temperature_and_wbgt_findings_are_population_associations": true,
          "relative_humidity_alone_is_insufficient": true,
          "universal_personal_correction_validated": false
        },
        "heat_adaptation_is_repeated_exposure_context_not_clearance": true,
        "individualized_acclimation_schedule_validated": false
      }
    },
    {
      "applies_to": "environment and altitude module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-marathon.altitude-capacity-no-personal-correction",
        "environment.full-wbgt-inputs",
        "environment.no-universal-personal-correction",
        "heat-adaptation.repeated-exposure",
        "heat-safety.separate-from-adaptation"
      ],
      "name": "road_marathon_environment_and_altitude_policy",
      "rationale": "Complete, source-labelled context is required before future dependent explanation. No reviewed source selects an individualized correction, adjustment, or acclimation schedule.",
      "value": {
        "altitude_acclimation_schedule": "not_accepted",
        "environmental_plan_adjustment_rule": "not_accepted",
        "heat_acclimation_schedule": "not_accepted",
        "heat_adaptation_used_as_medical_clearance": false,
        "incomplete_material_context_outcome": "environment_module_limited",
        "missing_context_blocks_independent_plan_modules": false,
        "personal_altitude_pace_or_finish_time_correction": "not_accepted",
        "personal_temperature_or_wbgt_correction": "not_accepted",
        "population_coefficient_used_as_personal_counterfactual": false,
        "required_environment_inputs_when_available": [
          "air_temperature",
          "atmospheric_moisture_or_vapor_pressure",
          "wind",
          "solar_or_radiant_load",
          "altitude_or_elevation_profile",
          "source_time_location_and_confidence"
        ],
        "weather_or_course_data_must_remain_source_labelled": true
      }
    },
    {
      "applies_to": "reassessment and outcomes module",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-marathon.pacing-prediction-retains-individual-error",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
        "environment.no-universal-personal-correction"
      ],
      "name": "road_marathon_reassessment_and_outcome_policy",
      "rationale": "The product must close the loop from recommendation through athlete feedback and observed outcomes into the next reassessment. No reviewed source selects the exact feedback weighting, update rule, cadence, fixed outcome window, meaningful-change threshold, race-priority algorithm, or causal attribution.",
      "value": {
        "absence_of_improvement_proves_nonresponse": false,
        "causal_plan_effect_claim": "prohibited",
        "direct_before_after_claim_requires": [
          "comparable_distance_and_result_type",
          "known_route_or_event",
          "known_surface_and_assistance",
          "known_environment_when_available",
          "no_material_protocol_change"
        ],
        "exact_calendar_reassessment_cadence": "not_accepted",
        "exact_feedback_weighting_and_update_algorithm": "not_accepted",
        "exact_post_marathon_outcome_window": "not_accepted",
        "feedback_inputs": [
          "completed_sessions_and_adherence",
          "athlete_edits_rejections_and_preferences",
          "perceived_effort_and_reported_response",
          "recovery_and_symptom_context",
          "split_or_sample_level_training_response",
          "comparable_event_or_field_outcomes"
        ],
        "feedback_loop_required": true,
        "meaningful_change_threshold": "not_accepted",
        "next_recommendation_must_record_response_to_feedback": true,
        "outcome_comparability_algorithm": "not_accepted",
        "personal_responder_classification": "prohibited",
        "race_priority_and_conflict_resolution_rule": "not_accepted",
        "reassessment_triggers": [
          "new_or_changed_confirmed_event",
          "new_qualified_marathon_result",
          "material_training_pattern_change",
          "completed_training_and_adherence_change",
          "athlete_edit_rejection_or_reported_response",
          "recovery_or_symptom_change",
          "completed_marathon_or_maximal_event",
          "changed_availability_or_constraint",
          "changed_fueling_hydration_or_environment_context",
          "athlete_requested_review"
        ],
        "renal_recovery_used_as_general_readiness": false,
        "supporting_outcomes": [
          "split_level_pacing_and_pace_decline",
          "adherence_edit_and_rejection_burden",
          "fueling_and_gastrointestinal_response",
          "hydration_context_and_issues",
          "recovery_response",
          "weekly_volume_frequency_longest_run_and_quality_change"
        ]
      }
    },
    {
      "applies_to": "future API and client state contract",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "road-marathon.pacing-prediction-retains-individual-error"
      ],
      "name": "road_marathon_typed_outcomes_and_suggestion_only_state",
      "rationale": "Typed outcomes preserve goal intent and make missing context or authority explicit without replacing product value with disclaimers. A supported safe route must take an actionable position; proposal, athlete adoption, observation, reassessment, delivery, and activation remain distinct states.",
      "value": {
        "AI_may_not": [
          "broaden_eligibility",
          "invent_capability_history_event_profile_or_safety_context",
          "choose_unaccepted_values",
          "override_deterministic_validation",
          "create_human_approval_artifacts",
          "activate_adopt_deliver_or_publish"
        ],
        "athlete_may": [
          "review",
          "edit",
          "reject",
          "explicitly_consent_to_adopt"
        ],
        "current_runtime_outcome": "plan_policy_inactive",
        "disclaimer_only_response_allowed_for_supported_safe_route": false,
        "future_generated_state_after_activation": "proposed",
        "generator_may_not": [
          "adopt_or_deliver_without_consent",
          "overwrite_adopted_future_days",
          "auto_schedule_a_maximal_marathon",
          "auto_change_event_priority",
          "schedule_missed_workout_makeup",
          "invent_fueling_hydration_or_environment_context"
        ],
        "no_plan_or_limited_outcome_must_include_actionable_resolution_path": true,
        "outcomes": {
          "capability_confirmation_required": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "environment_module_limited": {
            "degraded_modules": [
              "environment_altitude"
            ],
            "goal_remains_recorded": true,
            "plan_returned": true
          },
          "fueling_module_limited": {
            "degraded_modules": [
              "fueling_hydration_practice"
            ],
            "goal_remains_recorded": true,
            "plan_returned": true
          },
          "goal_recorded_plan_policy_unavailable": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "implementation_review_required": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "insufficient_history": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "limited_guidance_only": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false
          },
          "plan_policy_inactive": {
            "goal_remains_recorded": true,
            "plan_returned": false
          },
          "unresolved_event_conflict": {
            "goal_remains_recorded": true,
            "plan_returned": false
          }
        },
        "recommendation_must_include": [
          "next_action",
          "athlete_specific_rationale",
          "scientific_basis_and_applicability",
          "expected_response_or_signal",
          "uncertainty",
          "feedback_request"
        ],
        "supported_safe_route_must_return_actionable_recommendation": true
      }
    },
    {
      "applies_to": "validation, privacy, implementation, and rollout",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "road-marathon.recovery-subgroup-outcome-rules-unvalidated",
        "road-marathon.fluid-sodium-needs-variable"
      ],
      "name": "road_marathon_validation_privacy_and_open_decisions",
      "rationale": "Deterministic integrity is an engineering requirement. Statistical, subgroup, event-density, outcome, implementation, and activation choices need separate reviewed protocols and minimum-necessary private data. The loop must remain versioned, replayable, and reviewable rather than become hidden online learning.",
      "value": {
        "deterministic_invariant_breach_tolerance": 0,
        "deterministic_replay_mismatch_tolerance": 0,
        "dry_run_metrics_required": [
          "eligibility_and_each_typed_outcome_rate",
          "actionable_recommendation_coverage_for_supported_safe_routes",
          "recommendation_reasoning_expected_signal_and_feedback_completeness",
          "missingness_and_source_confirmation",
          "event_conflict_and_race_density",
          "subgroup_exclusion_and_edit_gaps",
          "proposal_edit_rejection_and_adoption_burden",
          "feedback_to_next_proposal_traceability",
          "fueling_hydration_and_environment_context_availability",
          "quality_event_and_long_run_stacking",
          "deterministic_replay"
        ],
        "exact_dry_run_go_no_go_thresholds": "not_accepted",
        "exact_prospective_pause_thresholds": "not_accepted",
        "implementation_mapping": "not_accepted",
        "no_inference_of": [
          "diagnosis",
          "injury_cause",
          "pregnancy_status",
          "mental_state",
          "missed_training_reason",
          "gastrointestinal_diagnosis",
          "hydration_or_sodium_diagnosis"
        ],
        "no_publication_of": [
          "raw_health_data",
          "private_activity_data",
          "inferred_sensitive_context"
        ],
        "outcome_windows_and_meaningful_change_thresholds": "not_accepted",
        "prospective_metrics_required": [
          "adoption_and_edit_distance",
          "adherence_and_burden",
          "recommendation_change_after_athlete_feedback",
          "symptom_stops_and_adverse_events",
          "fueling_and_gastrointestinal_tolerance",
          "hydration_issues",
          "comparable_marathon_outcomes",
          "withdrawal"
        ],
        "race_density_and_priority_thresholds": "not_accepted",
        "replay_record_must_include": [
          "policy_versions_and_contract_digests",
          "goal_record_state",
          "capability_and_history_sources",
          "split_or_sample_intensity_sources",
          "confirmed_event_context",
          "profile_fueling_hydration_and_environment_provenance",
          "unresolved_parameter_versions",
          "typed_outcome",
          "proposal_hash",
          "recommendation_hypothesis_and_expected_signal",
          "athlete_feedback_and_observed_outcome",
          "reassessment_reason",
          "change_from_prior_proposal"
        ],
        "runtime_activation_criteria": "not_accepted",
        "subgroup_dose_modifiers": "not_accepted",
        "target_risk_thresholds": "not_accepted",
        "unreviewed_online_learning_allowed": false
      }
    }
  ],
  "model_version": "road-marathon-plan-generation-policy-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Use only the authenticated athlete's minimum necessary goal, activity, event, profile, constraints, fueling, hydration, environment, and optional symptom context.",
    "Provider-imported profile, event, weather, and course fields remain source-labelled candidates until the athlete confirms or corrects them.",
    "Do not infer or publish diagnosis, injury cause, pregnancy status, gastrointestinal or hydration diagnosis, mental state, missed-training reason, or external life circumstance."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Copy a 5 km, 10 km, or half-marathon policy and replace the distance label",
      "rationale": "Marathon duration, direct capability, long-run durability, fueling, hydration, taper, recovery, environment, and event demands differ. Existing numeric guardrails are policy-specific and not universal evidence."
    },
    {
      "alternative": "Generate a performance plan for first-marathon or completion intent",
      "rationale": "Current direct same-task capability and stable history define this proposal. Completion and sparse-history populations need separately reviewed policies."
    },
    {
      "alternative": "Treat a prediction, critical speed, or shorter race as direct marathon capability",
      "rationale": "Models retain material individual error and do not manufacture same-task history, personal probability, or readiness."
    },
    {
      "alternative": "Schedule a maximal marathon simulation when direct capability is missing",
      "rationale": "A maximal simulation is burdensome and is not validated here. A no-event rolling preparation or benchmark route requires a separately accepted completion or benchmark policy."
    },
    {
      "alternative": "Convert observed volume, longest-run, durability, or taper values into prescriptions",
      "rationale": "The direct findings are observational, cross-sectional, or indirect and do not establish an optimal or safe individual dose."
    },
    {
      "alternative": "Select a universal pyramidal distribution or marathon-pace dose",
      "rationale": "The direct dataset is observational and zone-definition dependent. It does not establish a causal percentage, session count, spacing, or workout mix."
    },
    {
      "alternative": "Escalate dose to close a target-time gap or make up missed work",
      "rationale": "Prediction error and population associations cannot justify compressed progression, catch-up, or hidden dose escalation."
    },
    {
      "alternative": "Use one marathon fueling, fluid, or sodium rule",
      "rationale": "Duration, prior practice, tolerance, sweat response, environment, and athlete preference vary; both inadequate replacement and overdrinking matter."
    },
    {
      "alternative": "Apply an altitude or weather coefficient to personal marathon pace",
      "rationale": "Acute chamber effects and population weather associations are not individualized corrections or acclimation schedules."
    },
    {
      "alternative": "Let AI fill missing context or choose deferred values",
      "rationale": "AI cannot repair missing evidence, confirm athlete inputs, broaden eligibility, create approvals, activate runtime, or replace deterministic review."
    }
  ],
  "safety_implications": [
    "Current concerning symptoms, illness, injury, rehabilitation, return-to-sport, medical-clearance, pregnancy-specific, or contradictory safety context stops the vigorous-plan path without diagnosis or treatment.",
    "Prior marathon completion, within-recent history, renal recovery, practiced fueling, or heat adaptation does not establish medical clearance or guarantee freedom from harm.",
    "No maximal marathon benchmark, target-gap escalation, catch-up, fixed progression law, ACWR prescription zone, distance-only hydration rule, or activity-average-power intensity analysis is allowed.",
    "Both inadequate replacement and overdrinking matter; medical hydration, sodium, heat-illness, or hyponatremia diagnosis and treatment remain outside this performance policy.",
    "Confirmed races and maximal efforts must count as quality and load, and unresolved event conflicts prevent a full proposal."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "History-anchored adult outdoor road-marathon performance policy",
  "user_facing_claim_limits": [
    "When implemented and separately activated for a supported safe route, Praxys must recommend a concrete next action with an athlete-specific rationale, applicable science, an expected signal, uncertainty, and a request for the feedback that can change the next recommendation. It may not substitute a list of disclaimers for that product value.",
    "Scientific theories and research findings are bounded candidate strategies and priors. They inform an individualized proposal and its explanation; observed athlete response informs reassessment without proving personal causality or a permanent responder type.",
    "This draft is an evidence and decision proposal, not a usable marathon generator, optimal plan, safety guarantee, medical advice, target-time guarantee, or personal probability.",
    "Fokkema volume and longest-run categories, durability correlations, training-intensity distributions, taper effects, gut-tolerance findings, and altitude chamber effects are source findings only.",
    "No plan length or 5 km, 10 km, or half-marathon numeric rule is accepted for marathon use through this record.",
    "Missing optional age, sex, profile, fueling, hydration, or environmental detail affects only the dependent adjustment and unknown sex never defaults to male.",
    "No-event rolling preparation or simulation requires a separately accepted completion or benchmark policy and cannot silently create a maximal marathon.",
    "Environmental and altitude context may explain uncertainty but cannot produce a personal pace, finish-time, acclimation, or safety correction."
  ],
  "validation_plan": [
    "Registry validation must prove the exact draft Evidence Review and claim links, globally consistent citation metadata, rigorous verification notes, four approve and five defer items, complete parameter coverage, literal `not_accepted` deferrals, and inactive artifact policy.",
    "Artifact validation must prove that generated Evidence Review and SDR packets carry current digests and that the exact inactive machine contract embedded in the SDR packet matches the generated JSON contract.",
    "Tests must lock the narrow population tuple, modular structure, direct baseline hierarchy, goal-policy separation, no-event benchmark boundary, source-labelled profile and event data, module-local missing-context degradation, actionable recommendation contract, athlete feedback loop, typed outcomes, and activity-split/sample intensity rule.",
    "Tests must prove no plan length or shorter-distance numeric rule is inherited and that key observed values remain published source findings, not guardrail values.",
    "Tests must prove mostly-low organization is a candidate prior rather than a mandatory template, supported safe routes cannot return disclaimer-only output, and every proposal records the expected signal and feedback needed for the next reassessment.",
    "Before implementation, separate human decisions must select every baseline, history, dose, long-run, durability, intensity, race-specific, taper, recovery, fueling, hydration, environment, altitude, reassessment, subgroup, outcome, pilot, and activation value.",
    "Offline dry runs must report exclusions, missingness, source confirmation, event conflicts, subgroup gaps, actionable recommendation coverage, reasoning and feedback-request completeness, edit and rejection burden, feedback-to-next-proposal traceability, fueling, hydration and environment context, quality and event stacking, and deterministic replay without publishing private athlete data.",
    "A prospective opt-in pilot must predeclare human-reviewed go/no-go and pause thresholds before any activation."
  ],
  "version": 1
}
```

</details>
