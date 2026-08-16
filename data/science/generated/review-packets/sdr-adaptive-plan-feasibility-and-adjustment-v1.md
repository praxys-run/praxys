# Science decision review packet: Require actionable, feedback-aware recommendations across managed plans

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-adaptive-plan-feasibility-and-adjustment-v1`
- **Lifecycle:** `accepted`
- **Model version:** `adaptive-plan-policy-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:b2108b70a45355a5f4c0a189cadfc3f6d33980daf0e5efa0db17a7d6e652e1c2`
- **Contract digest:** `sha256:d9a56e6e799ebc1097bbc0b908f15d1e2db29ebc0d4df13b8e31a253d97f315b`
- **Required decision role:** `decision_approver`
- **Decision approval:** `github:dddtc2005` on `2026-08-16` ([source](https://github.com/praxys-run/praxys/pull/714#issuecomment-5307168334))
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the five proposed shared product boundaries are acceptable and whether the three implementation areas should remain explicitly deferred. Approve the sheet as a unit or request changes by item ID. The audit appendix is traceability, not the primary review task.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `actionable-position` — Require a concrete recommendation, not disclaimer-only output

- **Question:** Should every accepted safe managed-plan route return a concrete, reviewable position with a next action and required reasoning fields?
- **Proposed decision:** Require an actionable position. A change proposal, justified no-change, focused clarification, insufficient-evidence result, unsupported-route result, or safety stop must state the next step. For supported safe routes, caveats or data summaries alone are not a valid product result.
- **Approval means:**
  - Every managed-plan result has a typed position and concrete next step.
  - The recommendation exposes athlete-specific rationale, applicable science, expected signal, uncertainty, and feedback request.
  - Feasibility terms align with the existing goal-contract vocabulary without implying a probability.
- **This does not authorize:**
  - Any category threshold, personal probability, workout, dose, schedule, implementation, or activation.
  - A success-shaped plan when the route is unsupported, unsafe, or lacks required evidence.

<details><summary>Traceability: 4 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `managed_plan_policy_scope`, `actionable_recommendation_contract`, `goal_feasibility_semantics`, `proposal_outcomes`
- **Evidence claims:** `feasibility.group-evidence-not-personal-probability`, `feasibility.calibration-required`, `load.structured-training-bounded-benefit`, `outcome.single-indicator-insufficient`

</details>

#### `bounded-science` — Use science as bounded candidate context, not a personal rule

- **Question:** Should accepted science and distance policies constrain candidate strategies while the recommendation distinguishes evidence from inference, assumption, athlete report, and unknowns?
- **Proposed decision:** Use accepted population findings and distance-specific policies to define candidate strategies and constraints. Require each recommendation to show the evidence class and exact science references. Do not promote one cohort result, theory, or observed response into a universal rule, permanent identity, or personal causal claim.
- **Approval means:**
  - Distance policies provide task-specific candidate context without duplicating the shared loop.
  - Recommendation reasoning remains source-labelled and inspectable.
  - Historical intensity evidence remains split- or sample-based.
- **This does not authorize:**
  - Choosing a candidate strategy with an unreviewed algorithm or LLM judgment.
  - Using activity average power, a permanent responder label, or a population association as an individual prescription.

<details><summary>Traceability: 3 contract groups, 6 evidence claims</summary>

- **Contract groups covered:** `candidate_strategy_evidence_boundary`, `recommendation_reasoning_contract`, `intensity_evidence_source`
- **Evidence claims:** `feasibility.error-aware-response-classification`, `feasibility.no-permanent-responder-label`, `load.hrv-guidance-limited`, `load.acwr-not-causal-threshold`, `field-test.protocol-validity-reliability-sensitivity`, `outcome.observations-not-causal-explanation`

</details>

#### `athlete-controlled-loop` — Accept one athlete-controlled feedback and reassessment loop

- **Question:** Should every managed plan use one versioned sense-select-propose-review-observe-reassess loop with immutable evidence and proposal traces?
- **Proposed decision:** Accept the shared loop stages and athlete responses. Proposals remain non-canonical until exact adoption; an edit creates a successor. Completed training, plan divergence, athlete choices, perceived response, recovery or symptom reports, availability, and comparable outcomes may inform reassessment without proving causality.
- **Approval means:**
  - Recommendation, adoption, observation, and reassessment are traceable and replayable.
  - Athlete adoption, edit, rejection, and deferral remain distinct from model output.
  - Comparable protocols and measurement uncertainty govern direct outcome interpretation.
- **This does not authorize:**
  - An exact feedback weight, reassessment trigger, meaningful-change threshold, or automatic plan mutation.
  - Treating adherence or one outcome as proof that the plan caused the result.

<details><summary>Traceability: 7 contract groups, 9 evidence claims</summary>

- **Contract groups covered:** `recommendation_loop_state_machine`, `athlete_authority_and_consent`, `observation_and_feedback_contract`, `reassessment_contract`, `comparable_outcome_protocol_required`, `meaningful_change_policy`, `causal_gap_explanation`
- **Evidence claims:** `feasibility.error-aware-response-classification`, `detraining.short-term-system-specific`, `detraining.partial-not-complete-cessation`, `field-test.protocol-validity-reliability-sensitivity`, `field-test.running-reliability-and-sensitivity-underreported`, `field-test.critical-speed-protocol-dependent`, `outcome.subjective-monitoring-adds-signal`, `outcome.single-indicator-insufficient`, `outcome.observations-not-causal-explanation`

</details>

#### `hard-boundaries` — Accept safety, epistemic, learning, and privacy boundaries

- **Question:** Should personal probabilities, catch-up, ACWR zones, fixed detraining loss, permanent responder labels, unreviewed online learning, medical optimization, and hidden sensitive inference remain prohibited?
- **Proposed decision:** Keep those prohibitions. Athlete-reported injury, acute illness, or red-flag symptoms stop performance optimization. Feedback can inform a future human-reviewed policy but cannot change runtime weights, rules, or autonomy. Context stays optional, purpose-limited, correctable, and deletable.
- **Approval means:**
  - The shared loop cannot convert uncertainty into false precision or hidden automation.
  - Safety stops remain separate from performance adaptation.
  - Feedback and decision traces retain provenance without storing unrestricted sensitive narrative.
- **This does not authorize:**
  - Diagnosis, treatment, medical clearance, return-to-sport prescription, or a safety guarantee.
  - Runtime self-training, inferred sensitive traits, or permanent physiological profiling.

<details><summary>Traceability: 7 contract groups, 6 evidence claims</summary>

- **Contract groups covered:** `feasibility_probability`, `missed_session_catch_up`, `acwr_prescription_thresholds`, `fixed_detraining_loss_per_day`, `medical_stop_boundary`, `online_learning_and_policy_updates`, `privacy_and_traceability`
- **Evidence claims:** `feasibility.calibration-required`, `feasibility.no-permanent-responder-label`, `load.ten-percent-rule-not-safety-law`, `load.acwr-not-causal-threshold`, `detraining.short-term-system-specific`, `outcome.observations-not-causal-explanation`

</details>

#### `shared-policy-alignment` — Keep recommendation and feedback semantics shared across plans

- **Question:** Should one shared contract govern all managed-plan recommendation and feedback semantics while accepted distance records remain unchanged until explicit successor or implementation alignment?
- **Proposed decision:** Accept one shared contract. Existing accepted 5 km, 10 km, half-marathon, baseline, eligibility, and marathon decisions retain their history. Each requires the mapped successor or implementation alignment before shared runtime governance; no distance policy may silently create a second feedback engine.
- **Approval means:**
  - New managed-plan policies depend on the shared contract instead of duplicating it.
  - Existing accepted records remain auditable and are not rewritten by this decision.
  - Marathon keeps its already-declared shared dependency.
- **This does not authorize:**
  - Rewriting an accepted SDR, changing shipped 5 km behavior, or activating any distance policy.
  - Treating cross-distance scientific findings as interchangeable dose or schedule rules.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `accepted_policy_alignment_gate`
- **Evidence claims:** `feasibility.group-evidence-not-personal-probability`, `outcome.observations-not-causal-explanation`

</details>

### Decisions explicitly deferred

#### `defer-selection-and-update` — Keep selection, feedback weighting, triggers, and thresholds open

- **Question:** Should exact candidate ranking, feedback weighting, reassessment triggers, feasibility cut points, and meaningful-change thresholds remain unresolved?
- **Proposed decision:** Keep every mapped value literally not accepted. A later reviewed decision must define one narrow deterministic policy and its population, inputs, comparator, error handling, and falsification plan.
- **Approval means:**
  - The shared contract defines required semantics without pretending an optimal update algorithm is known.
  - Future policy work can be reviewed as explicit behavior rather than inferred from prose.
- **This does not authorize:**
  - Filling any value from common coaching practice, another distance, model output, or AI.
  - Updating the policy from observed feedback without a successor decision.

<details><summary>Traceability: 5 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `goal_feasibility_semantics`, `meaningful_change_policy`, `strategy_selection_algorithm`, `feedback_weighting_algorithm`, `reassessment_trigger_algorithm`
- **Evidence claims:** `feasibility.error-aware-response-classification`, `feasibility.calibration-required`, `load.hrv-guidance-limited`, `field-test.running-reliability-and-sensitivity-underreported`

</details>

#### `defer-distance-rules-and-autonomy` — Keep distance-specific generation and autonomy open

- **Question:** Should workout selection, dose, schedule, progression, recovery, fueling, environment, and any automatic adoption permission remain separate decisions?
- **Proposed decision:** Keep distance-specific generation values and autonomy expansion unresolved. Distance policies must provide accepted candidate rules and safety constraints; this shared contract does not choose their values.
- **Approval means:**
  - Recommendation semantics can be reviewed independently from distance-specific prescriptions.
  - Suggestion-first remains the only accepted autonomy mode.
- **This does not authorize:**
  - A workout, plan horizon, progression, target, automatic adoption, provider delivery, or autonomous goal change.
  - Inheriting a rule from another distance or training base.

<details><summary>Traceability: 2 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `distance_specific_generation_rules`, `autonomy_expansion_policy`
- **Evidence claims:** `load.structured-training-bounded-benefit`, `load.ten-percent-rule-not-safety-law`, `detraining.reduced-dose-maintenance`

</details>

#### `defer-implementation-and-activation` — Keep implementation, pilot criteria, and activation open

- **Question:** Should persistence, APIs, clients, pilot thresholds, implementation approval, rollout, and runtime activation remain outside this decision?
- **Proposed decision:** Keep the contract inactive. Require a reviewed deterministic mapping, web and miniapp parity, plugin and MCP parity, privacy controls, prospective pilot design, and separate implementation approval before any runtime use.
- **Approval means:**
  - Human evidence and decision review can complete without shipping behavior.
  - Runtime code cannot consume this contract as active.
- **This does not authorize:**
  - Database, API, analysis, UI, plugin, MCP, telemetry, model, rollout, or activation changes.
  - Claiming benefit, safety, or personalization efficacy before prospective evaluation.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `implementation_pilot_and_activation`
- **Evidence claims:** `feasibility.calibration-required`, `outcome.observations-not-causal-explanation`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve one shared inactive managed-plan recommendation contract. For an accepted safe route, Praxys must take a concrete and reviewable position, explain why it fits the athlete, identify the applicable science, state the expected signal and uncertainty, and request the feedback needed for reassessment. I approve science and distance-specific findings only as bounded candidate context, not universal personal rules, probabilities, or permanent runner identities. I approve the athlete-controlled sense-propose-review-observe-reassess loop, typed no-change and non-generation outcomes, comparable-outcome and causal limits, safety stops, source provenance, privacy, and the prohibition on disclaimer-only output and unreviewed online learning. I approve keeping these semantics shared across all managed plans while preserving accepted records until coordinated successor alignment. I agree that exact selection, weighting, thresholds, triggers, distance-specific dose and schedules, autonomy, implementation, pilot criteria, and runtime activation remain deferred. This approval would not approve implementation or activate the contract.

- **Decision approval:** `github:dddtc2005` on `2026-08-16` ([source](https://github.com/praxys-run/praxys/pull/714#issuecomment-5307168334))

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-adaptive-plan-feasibility-and-adjustment-v1`
- Digest: `sha256:b2108b70a45355a5f4c0a189cadfc3f6d33980daf0e5efa0db17a7d6e652e1c2`

> I approve one shared inactive managed-plan recommendation contract. For an accepted safe route, Praxys must take a concrete and reviewable position, explain why it fits the athlete, identify the applicable science, state the expected signal and uncertainty, and request the feedback needed for reassessment. I approve science and distance-specific findings only as bounded candidate context, not universal personal rules, probabilities, or permanent runner identities. I approve the athlete-controlled sense-propose-review-observe-reassess loop, typed no-change and non-generation outcomes, comparable-outcome and causal limits, safety stops, source provenance, privacy, and the prohibition on disclaimer-only output and unreviewed online learning. I approve keeping these semantics shared across all managed plans while preserving accepted records until coordinated successor alignment. I agree that exact selection, weighting, thresholds, triggers, distance-specific dose and schedules, autonomy, implementation, pilot criteria, and runtime activation remain deferred. This approval would not approve implementation or activate the contract.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:b2108b70a45355a5f4c0a189cadfc3f6d33980daf0e5efa0db17a7d6e652e1c2","subject_id":"sdr-adaptive-plan-feasibility-and-adjustment-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If accepted by a digest-bound human decision approver, this inactive shared policy would require every Praxys-owned managed-plan route to take a concrete, reviewable position instead of returning only caveats, disclaimers, or data summaries. When an accepted route is safe and supported, the result must state the next action, why it fits the athlete's current evidence, which accepted science constrains the recommendation, the expected signal, material uncertainty, and what feedback will inform reassessment. A justified no-change decision is an actionable position when it explains what remains supported and what to observe next. Clarification, insufficient-evidence, unsupported-route, and safety-stop results must also provide a concrete next step without inventing a success-shaped plan. Distance and intent policies supply accepted candidate strategies, constraints, and task-specific evidence; this shared policy owns recommendation, athlete review, observation, feedback, reassessment, and outcome semantics so each distance does not build a second adaptive engine. Scientific findings and population evidence remain bounded candidate context and qualitative initial priors, not universal personal prescriptions, calibrated probabilities, or permanent runner identities. Proposals remain suggestion-first, immutable, source-labelled, editable, rejectable, and non-canonical until the athlete adopts an exact version. Later training, athlete feedback, recovery or symptom reports, and comparable outcomes may update the evidence state and trigger a new versioned reassessment; they do not prove individual causality or authorize runtime self-modification. Personal probabilities, permanent responder labels, automatic missed-session catch-up, ACWR prescription zones, fixed detraining loss, activity-average-power intensity inference, medical diagnosis, unreviewed online learning, and hidden sensitive inference remain prohibited. Exact strategy selection, weighting, thresholds, triggers, distance-specific dose and schedule, autonomy, pilot criteria, implementation, and runtime activation remain explicitly not accepted.

### Linked evidence

#### `feasibility.group-evidence-not-personal-probability` — high

Group-average exercise response and population associations do not by themselves estimate one athlete's probability of attaining a goal.

- **Evidence Review:** `evidence-individual-goal-feasibility-v1`
- **Sources:** `bonafiglia-2021`, `atkinson-2015`, `renwick-2024`, `xiao-ren-2025`
- **Limitations:** The review was not specific to race-goal prediction.; This boundary does not identify which qualitative category is appropriate.; It does not show that individual response differences never exist.

#### `feasibility.error-aware-response-classification` — high

Individual response classification should account for random measurement error, within-person variability, and a meaningful-change threshold; zero-based thresholds inflate apparent response rates.

- **Evidence Review:** `evidence-individual-goal-feasibility-v1`
- **Sources:** `bonafiglia-2021`, `atkinson-2015`, `renwick-2024`, `xiao-ren-2025`
- **Limitations:** Meaningful-change thresholds are outcome and protocol specific.; Classification after one plan does not identify an intrinsic responder trait.; Failure to detect heterogeneity does not prove that no person-by-protocol interaction exists.

#### `feasibility.no-permanent-responder-label` — high

One observed training response does not support assigning a permanent responder or non-responder identity because measurement error, within-person variation, protocol choice, and context can contribute to the observed change.

- **Evidence Review:** `evidence-individual-goal-feasibility-v1`
- **Sources:** `bonafiglia-2021`, `renwick-2024`, `xiao-ren-2025`
- **Limitations:** The reviewed evidence does not establish that all athletes respond identically.; Behavioral fit, constraints, and within-person state may still justify changing how a strategy is delivered.; This claim does not validate a specific adaptive selection algorithm.

#### `feasibility.calibration-required` — high

A numerical individual prediction requires a defined outcome, representative development data, validation, and reported calibration as well as discrimination before it can support a personal probability.

- **Evidence Review:** `evidence-individual-goal-feasibility-v1`
- **Sources:** `collins-2015`
- **Limitations:** TRIPOD is reporting guidance and does not validate a Praxys model.; No reviewed source provides running-goal probability thresholds.

#### `load.structured-training-bounded-benefit` — low

Structured endurance training can improve recreational-running performance, but the reviewed evidence does not establish one universally superior intensity distribution or periodization model.

- **Evidence Review:** `evidence-adaptive-training-load-v1`
- **Sources:** `munoz-2014`
- **Limitations:** The primary between-group performance difference was not significant.; A favorable polarized result came from a smaller adherence-defined subset.; One study cannot define an adaptive plan policy.

#### `load.hrv-guidance-limited` — moderate

HRV-guided endurance training may improve some submaximal physiological outcomes, but reviewed pooled evidence did not establish a significant performance or VO2peak advantage over predefined training.

- **Evidence Review:** `evidence-adaptive-training-load-v1`
- **Sources:** `ducking-2021`
- **Limitations:** Only eight studies and 198 participants were included.; Devices, measurement routines, and training algorithms varied.; Results do not validate a universal daily HRV cutoff or exact action.

#### `load.ten-percent-rule-not-safety-law` — moderate

A progression program based on the 10 percent rule did not reduce running-related injury compared with a standard program in the reviewed novice-runner randomized trial.

- **Evidence Review:** `evidence-adaptive-training-load-v1`
- **Sources:** `buist-2008`
- **Limitations:** This does not show that every faster progression is safe.; Injury outcome evidence does not determine optimal performance progression.

#### `load.acwr-not-causal-threshold` — moderate

Acute-to-chronic workload ratios have conceptual and statistical limitations and should not be treated as established causal injury-risk zones or automatic prescription thresholds.

- **Evidence Review:** `evidence-adaptive-training-load-v1`
- **Sources:** `impellizzeri-2020`
- **Limitations:** This methodological critique does not show that training history is irrelevant.; It does not validate an alternative universal load threshold.

#### `detraining.short-term-system-specific` — moderate

Less than four weeks of insufficient training can reduce some cardiorespiratory and endurance adaptations, but the time course and magnitude differ by outcome, cessation versus reduction, and prior training status.

- **Evidence Review:** `evidence-short-interruption-detraining-v1`
- **Sources:** `mujika-2000`, `barbieri-2023`
- **Limitations:** The review does not establish a fixed loss per day.; Highly trained athletes are overrepresented.; The evidence does not define an individual return progression.

#### `detraining.reduced-dose-maintenance` — low

Reduced training frequency or volume may preserve endurance for a period when sufficient intensity is maintained, but athlete-specific evidence is limited and this is not equivalent to complete cessation.

- **Evidence Review:** `evidence-short-interruption-detraining-v1`
- **Sources:** `spiering-2021`, `barbieri-2023`
- **Limitations:** The review states that data are insufficient for athletes.; It does not support a universal minimum dose or return rule.

#### `detraining.partial-not-complete-cessation` — very_low

Stopping one training component while continuing running is not evidence about the effect of stopping all endurance training.

- **Evidence Review:** `evidence-short-interruption-detraining-v1`
- **Sources:** `berryman-2021`
- **Limitations:** Eight participants and no control group; Running continued while explosive-strength training stopped; The study cannot define general interruption or return policy

#### `field-test.protocol-validity-reliability-sensitivity` — moderate

A performance test used to detect change should match the target performance and establish protocol-specific validity, reliability, and sensitivity; time trials are generally more reliable than time-to-exhaustion protocols.

- **Evidence Review:** `evidence-running-field-tests-v1`
- **Sources:** `currell-2008`, `benhammou-2024`
- **Limitations:** Exact error depends on sport, distance, protocol, and population.; The review does not define one preferred running test for Praxys.; Many runner-test studies do not report repeatability or sensitivity.

#### `field-test.running-reliability-and-sensitivity-underreported` — moderate

Running-test validity is more often reported than test-retest reliability or sensitivity, so a valid construct alone is insufficient to classify an individual change as meaningful.

- **Evidence Review:** `evidence-running-field-tests-v1`
- **Sources:** `benhammou-2024`
- **Limitations:** The review does not validate one universal test or minimal detectable change.; The included methods and runner backgrounds were heterogeneous.; Abstract access limits detailed appraisal of individual study quality.

#### `field-test.vo2-estimate-not-direct-performance` — moderate

Distance- and time-based walk/run tests can estimate cardiorespiratory fitness, but the resulting score is an estimate rather than a direct laboratory measure or a complete measure of goal performance.

- **Evidence Review:** `evidence-running-field-tests-v1`
- **Sources:** `mayorga-vega-2016`
- **Limitations:** Results combine diverse ages and protocols.; Estimated VO2max is not equivalent to race-goal completion.

#### `field-test.critical-speed-protocol-dependent` — moderate

Field critical-speed assessment can be reliable under specified conditions, but protocol, trial selection, mathematical model, and environment constrain interpretation and comparability.

- **Evidence Review:** `evidence-running-field-tests-v1`
- **Sources:** `lipkova-2025`, `nimmerichter-2017`
- **Limitations:** The Nimmerichter sample included 16 trained athletes.; A treadmill-derived estimate is not interchangeable with a track time trial.; The 2025 systematic review is recent and includes heterogeneous protocols.

#### `outcome.subjective-monitoring-adds-signal` — moderate

Subjective self-reported well-being measures can detect training-related changes and may add information not captured by common objective measures.

- **Evidence Review:** `evidence-plan-outcome-interpretation-v1`
- **Sources:** `saw-2016`
- **Limitations:** Measures and sports were heterogeneous.; Subjective response does not establish the cause of a plan outcome.; The review does not validate sensitive free-text collection.

#### `outcome.single-indicator-insufficient` — moderate

Exercise response is heterogeneous across indicators, modalities, and intervention durations, so one physiological indicator should not be treated as a complete account of an individual's plan outcome.

- **Evidence Review:** `evidence-plan-outcome-interpretation-v1`
- **Sources:** `ardavani-2021`
- **Limitations:** Heterogeneity was ubiquitous across analyses.; Other indicators did not reach statistical significance in pooled analysis.; The review does not prescribe a product outcome framework.

#### `outcome.observations-not-causal-explanation` — low

Observed monitoring and response indicators describe what changed but do not, without an appropriate causal design, establish why one athlete achieved or missed a goal.

- **Evidence Review:** `evidence-plan-outcome-interpretation-v1`
- **Sources:** `saw-2016`, `ardavani-2021`
- **Limitations:** This is an epistemic boundary inferred from non-causal evidence.; A ranked hypothesis can guide future observation but is not a diagnosis.; Athlete-reported context may be relevant without proving causation.

### Reviewed parameters

#### `managed_plan_policy_scope` — guardrail

- **Applies to:** every Praxys-owned managed-plan policy and client
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Recommendation and feedback semantics are cross-cutting product behavior. Distance and intent policies remain responsible for accepted task-specific candidates and constraints.
- **Exact value:**

```json
{
  "applies_to": "all_praxys_owned_managed_plans",
  "disciplines": [
    "running",
    "trail_running"
  ],
  "distance_policies_must_not_duplicate_shared_loop": true,
  "distance_policies_supply": [
    "eligibility",
    "candidate_strategies",
    "task_specific_constraints",
    "task_specific_evidence"
  ],
  "intents": [
    "race",
    "performance",
    "consistency_base",
    "approved_future_intents"
  ],
  "shared_semantics": [
    "recommendation",
    "athlete_review",
    "observation",
    "feedback",
    "reassessment",
    "outcome_interpretation"
  ],
  "surfaces": [
    "web",
    "miniapp",
    "plugin",
    "mcp"
  ]
}
```

#### `actionable_recommendation_contract` — guardrail

- **Applies to:** recommendation and no-plan result contracts
- **Evidence claims:** `feasibility.group-evidence-not-personal-probability`, `feasibility.calibration-required`, `outcome.single-indicator-insufficient`
- **Rationale:** This is Praxys's positive product-value contract. It does not assert that one algorithm is biologically optimal; it requires safe uncertainty to shape a useful position instead of replacing it.
- **Exact value:**

```json
{
  "clarification_requires_one_focused_question": true,
  "data_summary_only_output_allowed": false,
  "disclaimer_only_output_allowed": false,
  "insufficient_evidence_requires_concrete_next_evidence_action": true,
  "justified_no_change_is_actionable": true,
  "required_fields": [
    "next_action",
    "athlete_specific_rationale",
    "applicable_science",
    "expected_signal",
    "uncertainty",
    "feedback_request"
  ],
  "safety_stop_requires_concrete_non_diagnostic_next_step": true,
  "supported_safe_route_requires_actionable_position": true,
  "unsupported_route_requires_supported_alternative_or_honest_stop": true
}
```

#### `candidate_strategy_evidence_boundary` — guardrail

- **Applies to:** candidate strategy registry and recommendation reasoning
- **Evidence claims:** `feasibility.group-evidence-not-personal-probability`, `feasibility.no-permanent-responder-label`, `load.structured-training-bounded-benefit`, `load.hrv-guidance-limited`
- **Rationale:** The reviewed evidence constrains overclaiming and candidate applicability but does not validate a universal strategy-selection algorithm.
- **Exact value:**

```json
{
  "accepted_science_role": "constrain_candidate_set_and_explain_applicability",
  "athlete_observations_role": "update_current_state_and_test_fit_within_reviewed_policy",
  "candidate_prior_is_personal_probability": false,
  "distance_policy_role": "supply_task_specific_candidates_and_constraints",
  "one_observed_response_creates_permanent_identity": false,
  "population_association_becomes_personal_rule": false,
  "population_findings_role": "bounded_candidate_context_and_qualitative_initial_prior",
  "unaccepted_source_may_drive_behavior": false
}
```

#### `recommendation_reasoning_contract` — guardrail

- **Applies to:** recommendation, clarification, no-change, and outcome explanations
- **Evidence claims:** `feasibility.error-aware-response-classification`, `outcome.subjective-monitoring-adds-signal`, `outcome.observations-not-causal-explanation`
- **Rationale:** These fields make the recommendation inspectable and keep observation, inference, assumption, and unknowns distinct.
- **Exact value:**

```json
{
  "applicable_science_requires_exact_record_and_claim_references": true,
  "athlete_specific_rationale_must_name_relevant_current_evidence": true,
  "causal_language_without_causal_design": false,
  "evidence_classes": [
    "observed",
    "athlete_stated",
    "inferred",
    "assumed",
    "unknown"
  ],
  "expected_signal_must_state_supporting_and_contrary_observations": true,
  "feedback_request_must_be_purpose_bounded": true,
  "no_change_must_explain_what_remains_supported_and_what_to_observe": true,
  "uncertainty_must_name_material_unknowns": true
}
```

#### `goal_feasibility_semantics` — guardrail

- **Applies to:** managed-plan goal feasibility and expectation assessments
- **Evidence claims:** `feasibility.group-evidence-not-personal-probability`, `feasibility.calibration-required`
- **Rationale:** The names align with the existing goal-contract proposal. The vocabulary is a product guardrail; exact cut points remain unresolved.
- **Exact value:**

```json
{
  "categories": {
    "aggressive": "material_gap_or_compressed_horizon_requires_warning_and_alternatives",
    "challenging": "plausible_with_material_execution_or_uncertainty_risks",
    "insufficient_evidence": "current_evidence_cannot_responsibly_assess_target",
    "supported": "no_material_concern_found_under_current_accepted_policy",
    "unsupported": "outside_an_accepted_planning_boundary"
  },
  "category_is_personal_probability": false,
  "category_thresholds": "not_accepted",
  "confidence_style": "qualitative_and_explained",
  "unsupported_allows_normal_success_shaped_plan": false
}
```

#### `recommendation_loop_state_machine` — guardrail

- **Applies to:** adaptive-plan decision, proposal, revision, and outcome traces
- **Evidence claims:** `outcome.observations-not-causal-explanation`
- **Rationale:** The loop is a product architecture and audit boundary, not a published physiological algorithm.
- **Exact value:**

```json
{
  "adoption_commits_one_exact_version": true,
  "athlete_edit_creates_successor_proposal": true,
  "deferral_preserves_canonical_plan": true,
  "deterministic_replay_required": true,
  "evidence_snapshot_is_immutable": true,
  "observation_does_not_rewrite_prior_decision": true,
  "proposal_is_immutable_and_non_canonical": true,
  "reassessment_appends_a_new_versioned_decision": true,
  "rejection_preserves_canonical_plan": true,
  "stages": [
    "sense",
    "select_candidate_strategy",
    "propose",
    "athlete_review",
    "observe",
    "reassess"
  ]
}
```

#### `athlete_authority_and_consent` — guardrail

- **Applies to:** proposal review, goal change, pause, resume, and end flows
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Explicit athlete control keeps early policy behavior observable, reversible, and separate from future autonomy decisions.
- **Exact value:**

```json
{
  "allowed_responses": [
    "adopt",
    "edit_into_successor",
    "reject",
    "defer"
  ],
  "athlete_constraints_are_authoritative": true,
  "default_mode": "athlete_approved_suggestions",
  "goal_change_requires_successor_and_acknowledgement": true,
  "pause_or_end_requires_explicit_athlete_action_or_separate_safety_policy": true,
  "proposal_is_canonical_before_adoption": false,
  "rejection_reason_optional": true
}
```

#### `observation_and_feedback_contract` — guardrail

- **Applies to:** execution, context, checkpoint, and terminal outcome evidence
- **Evidence claims:** `feasibility.no-permanent-responder-label`, `outcome.subjective-monitoring-adds-signal`, `outcome.single-indicator-insufficient`, `outcome.observations-not-causal-explanation`
- **Rationale:** Multiple source-labelled observations can reduce uncertainty without becoming proof of cause or a permanent physiological profile.
- **Exact value:**

```json
{
  "adherence_proves_adaptation": false,
  "athlete_feedback_proves_causality": false,
  "feedback_creates_permanent_responder_label": false,
  "feedback_may_inform_versioned_reassessment": true,
  "minimum_necessary_structured_context_preferred": true,
  "observation_classes": [
    "completed_training",
    "planned_vs_completed_divergence",
    "athlete_edit_rejection_or_deferral",
    "perceived_response",
    "recovery_or_symptom_report",
    "changed_availability",
    "comparable_checkpoint_or_goal_outcome"
  ],
  "one_workout_usually_sufficient_to_validate_policy": false,
  "provenance_classes": [
    "observed",
    "athlete_stated",
    "inferred",
    "assumed",
    "unknown"
  ]
}
```

#### `reassessment_contract` — guardrail

- **Applies to:** workout, week, block, goal, pause, resume, and outcome reassessment
- **Evidence claims:** `detraining.short-term-system-specific`, `field-test.protocol-validity-reliability-sensitivity`, `outcome.observations-not-causal-explanation`
- **Rationale:** Reassessment should explain what changed and preserve contrary evidence, rather than turning every observation into a plan mutation.
- **Exact value:**

```json
{
  "required_comparison": [
    "prior_position",
    "new_or_corrected_evidence",
    "unchanged_evidence",
    "contrary_signals",
    "expected_vs_observed_signal",
    "current_unknowns",
    "goal_implication",
    "plan_implication"
  ],
  "result_must_reference_policy_model_and_science_versions": true,
  "result_types": [
    "propose_change",
    "no_change",
    "clarification_required",
    "insufficient_evidence",
    "safety_stop",
    "unsupported_route"
  ],
  "silent_rebase_or_plan_rewrite_allowed": false,
  "smallest_supported_scope_preferred": true,
  "stale_proposal_requires_new_evidence_snapshot": true
}
```

#### `proposal_outcomes` — guardrail

- **Applies to:** managed-plan recommendation API and client states
- **Evidence claims:** `feasibility.group-evidence-not-personal-probability`, `outcome.single-indicator-insufficient`
- **Rationale:** Typed outcomes let the product remain useful and honest without silently converting uncertainty or unsupported scope into a normal plan.
- **Exact value:**

```json
{
  "every_type_requires_next_action": true,
  "every_type_requires_reason_and_uncertainty": true,
  "success_shaped_fallback_for_unavailable_route": false,
  "types": {
    "clarification_required": "one_focused_optional_question",
    "insufficient_evidence": "no_invented_action_and_one_concrete_evidence_step",
    "no_change": "keep_current_plan_with_reason_and_next_observation",
    "propose_change": "reviewable_non_canonical_diff",
    "safety_stop": "stop_performance_optimization_without_diagnosis",
    "unsupported_route": "preserve_goal_and_offer_supported_alternative_or_honest_stop"
  }
}
```

#### `feasibility_probability` — guardrail

- **Applies to:** feasibility and recommendation claims
- **Evidence claims:** `feasibility.calibration-required`
- **Rationale:** No reviewed source validates a Praxys personal goal-achievement probability.
- **Exact value:**

```json
{
  "personal_probability_enabled": false,
  "prerequisite_before_future_enablement": [
    "defined_population_and_outcome",
    "representative_development_data",
    "prospective_calibration",
    "external_validation",
    "subgroup_and_drift_monitoring",
    "accepted_successor_decision",
    "implementation_approval"
  ]
}
```

#### `missed_session_catch_up` — guardrail

- **Applies to:** interruption and planned-versus-completed handling
- **Evidence claims:** `load.ten-percent-rule-not-safety-law`, `detraining.short-term-system-specific`
- **Rationale:** A missed session does not reveal why it was missed or the athlete's current capacity, and no universal catch-up rule is validated.
- **Exact value:**

```json
{
  "automatic_compression": false,
  "automatic_doubling": false,
  "missed_session_alone_reveals_cause_or_capacity": false,
  "proportional_replacement": false,
  "reassessment_may_propose_smallest_supported_change": true
}
```

#### `acwr_prescription_thresholds` — guardrail

- **Applies to:** load evidence and proposal triggers
- **Evidence claims:** `load.acwr-not-causal-threshold`
- **Rationale:** Workload history can remain descriptive, but ratio zones are not established causal safety thresholds.
- **Exact value:**

```json
{
  "automatic_prescription_trigger_allowed": false,
  "causal_risk_zone_allowed": false,
  "descriptive_history_allowed": true
}
```

#### `fixed_detraining_loss_per_day` — guardrail

- **Applies to:** interruption assessment and return proposals
- **Evidence claims:** `detraining.short-term-system-specific`, `detraining.reduced-dose-maintenance`, `detraining.partial-not-complete-cessation`
- **Rationale:** Detraining differs by outcome, prior training, and whether training was reduced or stopped.
- **Exact value:**

```json
{
  "enabled": false,
  "one_system_represents_all_capacity": false,
  "total_cessation_equals_partial_reduction": false
}
```

#### `comparable_outcome_protocol_required` — guardrail

- **Applies to:** baseline, checkpoint, and terminal outcome comparison
- **Evidence claims:** `field-test.protocol-validity-reliability-sensitivity`, `field-test.running-reliability-and-sensitivity-underreported`, `field-test.vo2-estimate-not-direct-performance`, `field-test.critical-speed-protocol-dependent`
- **Rationale:** Validity alone does not establish repeatability, sensitivity, or equivalence for one athlete's change.
- **Exact value:**

```json
{
  "cross_protocol_change_is_direct_evidence": false,
  "device_estimate_is_automatically_equivalent": false,
  "direct_change_evidence_requires": [
    "same_or_accepted_equivalent_protocol",
    "documented_conditions",
    "protocol_specific_reliability",
    "protocol_specific_sensitivity_or_error_boundary"
  ],
  "unlike_environment_is_automatically_equivalent": false
}
```

#### `meaningful_change_policy` — guardrail

- **Applies to:** response classification and outcome evaluation
- **Evidence claims:** `feasibility.error-aware-response-classification`, `field-test.protocol-validity-reliability-sensitivity`, `field-test.running-reliability-and-sensitivity-underreported`
- **Rationale:** Measurement error and sensitivity vary by outcome, protocol, and population; exact thresholds require separate validation.
- **Exact value:**

```json
{
  "exact_protocol_thresholds": "not_accepted",
  "rule": "protocol_specific_and_error_aware",
  "universal_percentage_allowed": false,
  "zero_based_responder_threshold_allowed": false
}
```

#### `medical_stop_boundary` — guardrail

- **Applies to:** context intake, recommendation, proposal, and reassessment
- **Evidence claims:** _None; product rationale only_
- **Rationale:** This is a product safety stop outside the performance-planning evidence, not a medical decision algorithm.
- **Exact value:**

```json
{
  "athlete_reported_states": [
    "injury",
    "acute_illness",
    "red_flag_symptoms"
  ],
  "diagnosis_or_treatment_allowed": false,
  "next_step": "stop_performance_optimization_and_show_appropriate_non_diagnostic_guidance",
  "performance_optimization_continues": false,
  "return_to_sport_prescription_allowed": false
}
```

#### `causal_gap_explanation` — guardrail

- **Applies to:** checkpoint, terminal outcome, and plan gap review
- **Evidence claims:** `outcome.observations-not-causal-explanation`
- **Rationale:** Observations may support hypotheses and future tests but not definitive individual causal attribution.
- **Exact value:**

```json
{
  "adherence_as_causal_proof_allowed": false,
  "definitive_individual_cause_allowed": false,
  "diagnosis_allowed": false,
  "future_testable_question_allowed": true,
  "output": "ranked_hypotheses_with_contrary_evidence_and_unknowns"
}
```

#### `intensity_evidence_source` — guardrail

- **Applies to:** historical intensity evidence and recommendation rationale
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Activity-average power is diluted by warmup, cooldown, and recovery and cannot support interval-intensity interpretation.
- **Exact value:**

```json
{
  "activity_average_power_allowed": false,
  "allowed": [
    "activity_splits",
    "activity_samples"
  ],
  "missing_split_or_sample_evidence_result": "intensity_inference_unavailable"
}
```

#### `online_learning_and_policy_updates` — guardrail

- **Applies to:** policy, model, prompt, and autonomy updates
- **Evidence claims:** `feasibility.no-permanent-responder-label`, `outcome.observations-not-causal-explanation`
- **Rationale:** Feedback is evidence for reassessment and future policy research, not permission for unreviewed online learning.
- **Exact value:**

```json
{
  "feedback_may_support_future_human_reviewed_successor": true,
  "permanent_responder_profile_from_feedback": false,
  "runtime_autonomy_expansion_from_feedback": false,
  "runtime_prompt_authority_expansion_from_feedback": false,
  "runtime_rule_updates_from_feedback": false,
  "runtime_weight_updates_from_feedback": false,
  "successor_requires": [
    "versioned_evidence",
    "accepted_science_decision",
    "deterministic_validation",
    "implementation_approval"
  ]
}
```

#### `privacy_and_traceability` — guardrail

- **Applies to:** context, evidence snapshots, recommendations, and decision traces
- **Evidence claims:** `outcome.subjective-monitoring-adds-signal`, `outcome.observations-not-causal-explanation`
- **Rationale:** Optional context can improve interpretation only when its purpose, provenance, correction, access, and deletion boundaries are explicit.
- **Exact value:**

```json
{
  "account_deletion_covers_context_and_derived_adaptive_traces": true,
  "athlete_can_correct_exclude_and_delete_context": true,
  "decision_trace_requires": [
    "owning_user",
    "evidence_snapshot",
    "proposal_or_position",
    "policy_model_and_science_versions",
    "source_revisions",
    "later_outcome_links"
  ],
  "minimum_necessary_structured_context_preferred": true,
  "personal_context_optional": true,
  "purpose_limited_collection": true,
  "raw_free_text_in_generic_decision_trace_allowed": false,
  "sensitive_trait_inference_allowed": false,
  "source_provenance_visible": true
}
```

#### `accepted_policy_alignment_gate` — guardrail

- **Applies to:** science lifecycle, implementation mapping, and managed-plan activation
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Accepted records cannot be silently rewritten. The map preserves history while making future shared-loop alignment explicit.
- **Exact value:**

```json
{
  "accepted_records_remain_unchanged_in_this_decision": true,
  "accepted_records_requiring_successor_or_explicit_implementation_alignment": [
    "sdr-preplan-baseline-policy-v1",
    "sdr-outdoor-5k-plan-generation-policy-v1",
    "sdr-road-10k-plan-generation-policy-v1",
    "sdr-road-half-marathon-plan-generation-policy-v1"
  ],
  "new_managed_plan_policy_requires_shared_dependency": true,
  "no_distance_policy_may_define_a_second_feedback_engine": true,
  "records_already_naming_this_shared_policy": [
    "sdr-plan-generation-eligibility-safety-v1",
    "sdr-road-marathon-plan-generation-policy-v1"
  ],
  "shared_runtime_governance_before_alignment": false
}
```

#### `strategy_selection_algorithm` — guardrail

- **Applies to:** candidate selection policy
- **Evidence claims:** `load.hrv-guidance-limited`, `feasibility.no-permanent-responder-label`
- **Rationale:** The reviewed evidence does not validate a Praxys-specific algorithm for selecting among candidate strategies.
- **Exact value:**

```json
{
  "candidate_ranking": "not_accepted",
  "context_interactions": "not_accepted",
  "exploration_or_experiment_assignment": "not_accepted",
  "model_or_llm_role": "not_accepted",
  "tie_breaking": "not_accepted"
}
```

#### `feedback_weighting_algorithm` — guardrail

- **Applies to:** evidence evaluation and reassessment
- **Evidence claims:** `outcome.subjective-monitoring-adds-signal`, `outcome.single-indicator-insufficient`
- **Rationale:** Multiple signals may inform reassessment, but no reviewed source defines their Praxys-specific weights or conflict resolution.
- **Exact value:**

```json
{
  "athlete_report_weight": "not_accepted",
  "contradictory_signal_resolution": "not_accepted",
  "missingness_handling": "not_accepted",
  "observation_weights": "not_accepted",
  "recency_decay": "not_accepted"
}
```

#### `reassessment_trigger_algorithm` — guardrail

- **Applies to:** reassessment scheduler and event handling
- **Evidence claims:** `detraining.short-term-system-specific`, `field-test.running-reliability-and-sensitivity-underreported`
- **Rationale:** The shared loop defines trigger categories but not exact timing or thresholds.
- **Exact value:**

```json
{
  "availability_change_threshold": "not_accepted",
  "checkpoint_threshold": "not_accepted",
  "goal_expectation_change_threshold": "not_accepted",
  "recovery_or_symptom_threshold": "not_accepted",
  "scheduled_cadence": "not_accepted",
  "workout_divergence_threshold": "not_accepted"
}
```

#### `distance_specific_generation_rules` — guardrail

- **Applies to:** plan generation and distance-specific recommendation candidates
- **Evidence claims:** `load.structured-training-bounded-benefit`, `load.ten-percent-rule-not-safety-law`, `detraining.reduced-dose-maintenance`
- **Rationale:** These values remain owned by separately accepted distance, intent, and context policies.
- **Exact value:**

```json
{
  "dose": "not_accepted",
  "environment_altitude": "not_accepted",
  "fueling_hydration": "not_accepted",
  "intensity_distribution": "not_accepted",
  "long_run": "not_accepted",
  "plan_horizon": "not_accepted",
  "progression": "not_accepted",
  "recovery": "not_accepted",
  "return_after_interruption": "not_accepted",
  "schedule": "not_accepted",
  "taper": "not_accepted",
  "workout_selection": "not_accepted"
}
```

#### `autonomy_expansion_policy` — guardrail

- **Applies to:** proposal approval, canonical mutation, and provider delivery
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Any automatic action requires a separate exact consent, scope, evidence, implementation, and revocation decision.
- **Exact value:**

```json
{
  "automatic_adoption_scope": "not_accepted",
  "automatic_goal_change": false,
  "automatic_pause_or_resume": "not_accepted",
  "automatic_provider_delivery": "not_accepted",
  "consent_model": "not_accepted",
  "current_default": "suggestion_only",
  "expiry_and_revocation": "not_accepted"
}
```

#### `implementation_pilot_and_activation` — guardrail

- **Applies to:** implementation, pilot, rollout, and runtime
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Evidence and decision acceptance are separate from implementation, prospective evaluation, rollout, and activation.
- **Exact value:**

```json
{
  "active_behavior": false,
  "analysis_mapping": "not_accepted",
  "api_contracts": "not_accepted",
  "comparator": "not_accepted",
  "implementation_approval": "not_accepted",
  "persistence_schema": "not_accepted",
  "pilot_population": "not_accepted",
  "plugin_and_mcp_contracts": "not_accepted",
  "primary_and_guardrail_metrics": "not_accepted",
  "privacy_operations": "not_accepted",
  "rollout": "not_accepted",
  "runtime_activation": "not_accepted",
  "sample_size_and_duration": "not_accepted",
  "science_note_and_localization": "not_accepted",
  "success_failure_and_rollback_thresholds": "not_accepted",
  "web_and_miniapp_clients": "not_accepted"
}
```

### Rejected alternatives

#### Return caveats, disclaimers, or data summaries without a concrete next action.

Praxys exists to interpret evidence into a reviewable position. Safety and uncertainty must shape the action, not replace product value when a safe supported route exists.

#### Let each distance policy define its own recommendation and feedback loop.

Duplicated semantics would drift across web, miniapp, plugin, MCP, and distance policies and make athlete decisions and feedback incomparable.

#### Present a numerical probability that an individual athlete will achieve the goal.

No prospectively calibrated and externally validated Praxys prediction model exists for the target population and supported goal types.

#### Present qualitative feasibility categories as published scientific thresholds.

The reviewed research supports uncertainty boundaries, not the product vocabulary or category cut points.

#### Assign a permanent responder or non-responder profile from one plan outcome.

Measurement error, within-person variation, protocol, and context can contribute to an observed response; one plan does not establish an intrinsic identity.

#### Automatically make up, double, compress, or proportionally replace missed sessions.

No reviewed evidence validates a universal catch-up rule, and schedule interruption does not reveal the athlete's reason or current capacity.

#### Use acute-to-chronic workload ratio zones or the 10 percent rule as causal safety limits.

The workload ratio has causal and statistical limitations, while the reviewed novice-runner trial did not show lower injury incidence from a 10 percent progression program.

#### Infer a fixed percentage of fitness loss or return capacity from days missed.

Detraining differs by physiological system, training history, and whether training was reduced or stopped.

#### Compare unlike tests, environments, or model estimates as direct evidence of improvement.

Test validity, reliability, sensitivity, and prediction error are protocol specific.

#### Explain a goal miss from adherence, physiology, or athlete context alone.

These observations can inform hypotheses but do not establish individual causation without an appropriate prospective design.

#### Let feedback automatically update runtime strategy weights, rules, prompts, or autonomy.

Observations can support future reviewed policy changes but do not authorize an unreviewed online-learning system.

#### Continue performance-plan adaptation through illness, injury, or red-flag symptoms.

Medical assessment and return-to-sport decisions are outside this performance-planning evidence and require an explicit safety boundary.

### Applicability

- All Praxys-owned managed plans after their distance, intent, capability, history, and safety routes are separately accepted
- Adult self-coached runners and trail runners within the accepted policy that supplies candidate strategies
- Web, WeChat miniapp, plugin, and MCP surfaces using the same managed-plan contract
- Suggestion-first recommendation, athlete review, observation, reassessment, and outcome interpretation
- Direct performance interpretation only when baseline and outcome protocols are comparable

### User-facing claim limits

- Do not return only disclaimers or data summaries when a supported safe route can take an actionable position.
- Do not promise or guarantee goal achievement.
- Do not show an individual success probability until a prospectively calibrated and externally validated model is accepted.
- Label feasibility categories, candidate priors, adjustment scopes, and triggers as Praxys guidance rather than published thresholds.
- Distinguish what was observed, athlete-stated, inferred, assumed, and unknown.
- Do not call one plan result a permanent responder or non-responder identity.
- Do not imply that adherence proves adaptation or plan effectiveness.
- Do not imply that HRV, workload ratio, or one response metric dictates a workout.
- Do not call different protocols or environments equivalent direct evidence.
- Present post-plan reasons as ranked hypotheses, never diagnosis or established individual causation.
- Explain when a no-change, clarification, insufficient-evidence, unsupported-route, or safety-stop result is the concrete next action.

### Safety implications

- Illness, injury, and red-flag symptoms stop performance optimization rather than triggering an automated return prescription.
- No automatic doubling, catch-up, or compressed replacement of missed work.
- Every position identifies uncertainty and the next safe action.
- Goal, pause, resume, end, and plan-change proposals remain non-canonical until explicitly adopted under an accepted authority policy.
- Unsupported or unsafe routes never return a normal success-shaped plan.

### Privacy implications

- Personal context is optional, purpose-limited, and private to the athlete's plan.
- Store structured minimum-necessary context separately from free text where possible.
- Show what context informed each recommendation and allow correction, exclusion, and deletion.
- Do not infer sensitive medical, family, employment, or identity details from behavior.
- Do not store unrestricted athlete narrative in generic decision traces.
- Athlete context and adaptive traces follow account deletion, retention, access, and export controls.

### Validation plan

- Human evidence review must accept, revise, or reject all five Evidence Reviews before this decision can be accepted.
- Human decision review must approve the decision sheet and inactive contract separately from implementation.
- Define one narrow deterministic suggestion-only policy with a versioned identifier, immutable evidence snapshot, and replay fixture.
- Predefine candidate strategies, outcome, comparable protocol, meaningful-change rule, safety events, and no-change comparator.
- Verify every supported safe fixture produces an actionable position with all required reasoning fields.
- Verify every clarification, insufficient-evidence, unsupported-route, and safety fixture produces a concrete next step without a success-shaped fallback.
- Add registry, policy, API-contract, web, miniapp, plugin, MCP, privacy, deletion, and client-state tests for every implemented boundary.
- Prospectively evaluate recommendation precision, usefulness, athlete adoption, edits, rejection, reversals, adverse events, and goal outcomes without updating runtime rules from those observations.
- Audit performance by sex, age, training history, goal type, distance, training base, missingness, language, surface, and data-provider provenance.
- Calibrate any future numerical feasibility model and validate it externally before exposing probabilities.
- Require an approved successor SDR for each algorithm, threshold, distance-policy alignment, or additional autonomous permission.
- Require separate implementation review before changing runtime_state from inactive.

### Falsification conditions

- A supported safe route returns only caveats, disclaimers, or data without a concrete next action.
- Web, miniapp, plugin, or MCP surfaces produce different recommendation or athlete-decision semantics for the same policy input.
- A category is interpreted as a calibrated probability or guarantee despite the claim limits.
- One observed result creates a permanent responder identity or silently changes future policy weights.
- Repeated comparable tests show changes within measurement noise while Praxys labels them meaningful.
- Prospective evaluation finds that the policy worsens goal outcomes, athlete burden, or safety events versus the predefined comparator.
- A recommendation, proposal, or reassessment cannot be reproduced from its versioned evidence, policy, model, and science inputs.
- Context deletion fails to remove the athlete's private plan context or derived adaptive traces.
- A policy applies catch-up, workload-ratio, fixed detraining, activity-average-power, or causal-explanation rules that this decision disables.
- A distance policy implements a second recommendation or feedback engine instead of the shared contract.

### Decision notes

- This artifact-mode Decision proposal upgrades the merged #607 draft for issue #713 and remains draft and inactive.
- The five Evidence Reviews were rerun through 2026-08-16, converted to artifact mode, and bound to complete PubMed search manifests. Four more direct 2023-2025 reviews were added; no sixth Evidence Review is required.
- The positive actionable recommendation requirement is a Praxys product guardrail supported by PRODUCT.md. The scientific evidence constrains candidate use, measurement, uncertainty, and causal claims; it does not prove this loop or any update algorithm is optimal.
- Human review must use the generated packets rather than raw YAML. The decision packet begins with five proposed approvals and three explicit deferrals and embeds the exact inactive machine contract.
- Accepted 5 km, 10 km, half-marathon, baseline, eligibility, and marathon records are not rewritten here. Their successor or implementation alignment is mapped before shared runtime governance.
- All unresolved behavior-driving values are literal `not_accepted`; no implementation may infer a value from source findings, another distance, common coaching practice, prose, or AI output.
- Impact map: five draft Evidence Reviews and search manifests -> generated evidence packets -> draft shared SDR -> generated decision packet and inactive contract -> human evidence and decision review -> coordinated accepted-policy alignment -> future deterministic policy mapping -> persistence and API -> web, miniapp, plugin, and MCP parity -> ScienceNote and localization -> offline replay and privacy validation -> prospective opt-in pilot -> separate implementation review -> separately approved activation.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "adaptive-plan goal feasibility and expectation contract",
    "shared managed-plan recommendation policy",
    "adaptive-plan proposal, athlete decision, and revision trace",
    "adaptive-plan observation, reassessment, outcome, and gap review",
    "managed-plan capability registry and distance-policy dependency graph"
  ],
  "contract_digest": "sha256:d9a56e6e799ebc1097bbc0b908f15d1e2db29ebc0d4df13b8e31a253d97f315b",
  "decision_id": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
  "decision_status": "accepted",
  "decision_version": 1,
  "evidence_claim_ids": [
    "feasibility.group-evidence-not-personal-probability",
    "feasibility.error-aware-response-classification",
    "feasibility.no-permanent-responder-label",
    "feasibility.calibration-required",
    "load.structured-training-bounded-benefit",
    "load.hrv-guidance-limited",
    "load.ten-percent-rule-not-safety-law",
    "load.acwr-not-causal-threshold",
    "detraining.short-term-system-specific",
    "detraining.reduced-dose-maintenance",
    "detraining.partial-not-complete-cessation",
    "field-test.protocol-validity-reliability-sensitivity",
    "field-test.running-reliability-and-sensitivity-underreported",
    "field-test.vo2-estimate-not-direct-performance",
    "field-test.critical-speed-protocol-dependent",
    "outcome.subjective-monitoring-adds-signal",
    "outcome.single-indicator-insufficient",
    "outcome.observations-not-causal-explanation"
  ],
  "evidence_review_ids": [
    "evidence-individual-goal-feasibility-v1",
    "evidence-adaptive-training-load-v1",
    "evidence-short-interruption-detraining-v1",
    "evidence-running-field-tests-v1",
    "evidence-plan-outcome-interpretation-v1"
  ],
  "linked_evidence_digests": {
    "evidence-adaptive-training-load-v1": "sha256:101f9e5b3a9eeed9d8777d0cef8cf56f332372568fed32ba812c4f969551d50f",
    "evidence-individual-goal-feasibility-v1": "sha256:68dabbd3bed068c2829d6b77d9b0ee2503e8ae3874b745d2b61f5420680b94ba",
    "evidence-plan-outcome-interpretation-v1": "sha256:46026c614f9be03950e9e2d9f9e4bb6ef29d12f5882432105a5b522b7fb96956",
    "evidence-running-field-tests-v1": "sha256:734d2abf59bab4b371ff8dbf5db1ae39ce5c9d82ae85593a66063687ea664ccc",
    "evidence-short-interruption-detraining-v1": "sha256:a68cb7a7655e1980c0ecd8cf7dfb737015b000ea9609572e460fabd13e932fb9"
  },
  "model_version": "adaptive-plan-policy-v1",
  "parameters": {
    "accepted_policy_alignment_gate": {
      "applies_to": "science lifecycle, implementation mapping, and managed-plan activation",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "accepted_records_remain_unchanged_in_this_decision": true,
        "accepted_records_requiring_successor_or_explicit_implementation_alignment": [
          "sdr-preplan-baseline-policy-v1",
          "sdr-outdoor-5k-plan-generation-policy-v1",
          "sdr-road-10k-plan-generation-policy-v1",
          "sdr-road-half-marathon-plan-generation-policy-v1"
        ],
        "new_managed_plan_policy_requires_shared_dependency": true,
        "no_distance_policy_may_define_a_second_feedback_engine": true,
        "records_already_naming_this_shared_policy": [
          "sdr-plan-generation-eligibility-safety-v1",
          "sdr-road-marathon-plan-generation-policy-v1"
        ],
        "shared_runtime_governance_before_alignment": false
      }
    },
    "actionable_recommendation_contract": {
      "applies_to": "recommendation and no-plan result contracts",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "feasibility.calibration-required",
        "outcome.single-indicator-insufficient"
      ],
      "value": {
        "clarification_requires_one_focused_question": true,
        "data_summary_only_output_allowed": false,
        "disclaimer_only_output_allowed": false,
        "insufficient_evidence_requires_concrete_next_evidence_action": true,
        "justified_no_change_is_actionable": true,
        "required_fields": [
          "next_action",
          "athlete_specific_rationale",
          "applicable_science",
          "expected_signal",
          "uncertainty",
          "feedback_request"
        ],
        "safety_stop_requires_concrete_non_diagnostic_next_step": true,
        "supported_safe_route_requires_actionable_position": true,
        "unsupported_route_requires_supported_alternative_or_honest_stop": true
      }
    },
    "acwr_prescription_thresholds": {
      "applies_to": "load evidence and proposal triggers",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.acwr-not-causal-threshold"
      ],
      "value": {
        "automatic_prescription_trigger_allowed": false,
        "causal_risk_zone_allowed": false,
        "descriptive_history_allowed": true
      }
    },
    "athlete_authority_and_consent": {
      "applies_to": "proposal review, goal change, pause, resume, and end flows",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "allowed_responses": [
          "adopt",
          "edit_into_successor",
          "reject",
          "defer"
        ],
        "athlete_constraints_are_authoritative": true,
        "default_mode": "athlete_approved_suggestions",
        "goal_change_requires_successor_and_acknowledgement": true,
        "pause_or_end_requires_explicit_athlete_action_or_separate_safety_policy": true,
        "proposal_is_canonical_before_adoption": false,
        "rejection_reason_optional": true
      }
    },
    "autonomy_expansion_policy": {
      "applies_to": "proposal approval, canonical mutation, and provider delivery",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "automatic_adoption_scope": "not_accepted",
        "automatic_goal_change": false,
        "automatic_pause_or_resume": "not_accepted",
        "automatic_provider_delivery": "not_accepted",
        "consent_model": "not_accepted",
        "current_default": "suggestion_only",
        "expiry_and_revocation": "not_accepted"
      }
    },
    "candidate_strategy_evidence_boundary": {
      "applies_to": "candidate strategy registry and recommendation reasoning",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "feasibility.no-permanent-responder-label",
        "load.structured-training-bounded-benefit",
        "load.hrv-guidance-limited"
      ],
      "value": {
        "accepted_science_role": "constrain_candidate_set_and_explain_applicability",
        "athlete_observations_role": "update_current_state_and_test_fit_within_reviewed_policy",
        "candidate_prior_is_personal_probability": false,
        "distance_policy_role": "supply_task_specific_candidates_and_constraints",
        "one_observed_response_creates_permanent_identity": false,
        "population_association_becomes_personal_rule": false,
        "population_findings_role": "bounded_candidate_context_and_qualitative_initial_prior",
        "unaccepted_source_may_drive_behavior": false
      }
    },
    "causal_gap_explanation": {
      "applies_to": "checkpoint, terminal outcome, and plan gap review",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "adherence_as_causal_proof_allowed": false,
        "definitive_individual_cause_allowed": false,
        "diagnosis_allowed": false,
        "future_testable_question_allowed": true,
        "output": "ranked_hypotheses_with_contrary_evidence_and_unknowns"
      }
    },
    "comparable_outcome_protocol_required": {
      "applies_to": "baseline, checkpoint, and terminal outcome comparison",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "field-test.protocol-validity-reliability-sensitivity",
        "field-test.running-reliability-and-sensitivity-underreported",
        "field-test.vo2-estimate-not-direct-performance",
        "field-test.critical-speed-protocol-dependent"
      ],
      "value": {
        "cross_protocol_change_is_direct_evidence": false,
        "device_estimate_is_automatically_equivalent": false,
        "direct_change_evidence_requires": [
          "same_or_accepted_equivalent_protocol",
          "documented_conditions",
          "protocol_specific_reliability",
          "protocol_specific_sensitivity_or_error_boundary"
        ],
        "unlike_environment_is_automatically_equivalent": false
      }
    },
    "distance_specific_generation_rules": {
      "applies_to": "plan generation and distance-specific recommendation candidates",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.structured-training-bounded-benefit",
        "load.ten-percent-rule-not-safety-law",
        "detraining.reduced-dose-maintenance"
      ],
      "value": {
        "dose": "not_accepted",
        "environment_altitude": "not_accepted",
        "fueling_hydration": "not_accepted",
        "intensity_distribution": "not_accepted",
        "long_run": "not_accepted",
        "plan_horizon": "not_accepted",
        "progression": "not_accepted",
        "recovery": "not_accepted",
        "return_after_interruption": "not_accepted",
        "schedule": "not_accepted",
        "taper": "not_accepted",
        "workout_selection": "not_accepted"
      }
    },
    "feasibility_probability": {
      "applies_to": "feasibility and recommendation claims",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.calibration-required"
      ],
      "value": {
        "personal_probability_enabled": false,
        "prerequisite_before_future_enablement": [
          "defined_population_and_outcome",
          "representative_development_data",
          "prospective_calibration",
          "external_validation",
          "subgroup_and_drift_monitoring",
          "accepted_successor_decision",
          "implementation_approval"
        ]
      }
    },
    "feedback_weighting_algorithm": {
      "applies_to": "evidence evaluation and reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.subjective-monitoring-adds-signal",
        "outcome.single-indicator-insufficient"
      ],
      "value": {
        "athlete_report_weight": "not_accepted",
        "contradictory_signal_resolution": "not_accepted",
        "missingness_handling": "not_accepted",
        "observation_weights": "not_accepted",
        "recency_decay": "not_accepted"
      }
    },
    "fixed_detraining_loss_per_day": {
      "applies_to": "interruption assessment and return proposals",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "detraining.short-term-system-specific",
        "detraining.reduced-dose-maintenance",
        "detraining.partial-not-complete-cessation"
      ],
      "value": {
        "enabled": false,
        "one_system_represents_all_capacity": false,
        "total_cessation_equals_partial_reduction": false
      }
    },
    "goal_feasibility_semantics": {
      "applies_to": "managed-plan goal feasibility and expectation assessments",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "feasibility.calibration-required"
      ],
      "value": {
        "categories": {
          "aggressive": "material_gap_or_compressed_horizon_requires_warning_and_alternatives",
          "challenging": "plausible_with_material_execution_or_uncertainty_risks",
          "insufficient_evidence": "current_evidence_cannot_responsibly_assess_target",
          "supported": "no_material_concern_found_under_current_accepted_policy",
          "unsupported": "outside_an_accepted_planning_boundary"
        },
        "category_is_personal_probability": false,
        "category_thresholds": "not_accepted",
        "confidence_style": "qualitative_and_explained",
        "unsupported_allows_normal_success_shaped_plan": false
      }
    },
    "implementation_pilot_and_activation": {
      "applies_to": "implementation, pilot, rollout, and runtime",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "active_behavior": false,
        "analysis_mapping": "not_accepted",
        "api_contracts": "not_accepted",
        "comparator": "not_accepted",
        "implementation_approval": "not_accepted",
        "persistence_schema": "not_accepted",
        "pilot_population": "not_accepted",
        "plugin_and_mcp_contracts": "not_accepted",
        "primary_and_guardrail_metrics": "not_accepted",
        "privacy_operations": "not_accepted",
        "rollout": "not_accepted",
        "runtime_activation": "not_accepted",
        "sample_size_and_duration": "not_accepted",
        "science_note_and_localization": "not_accepted",
        "success_failure_and_rollback_thresholds": "not_accepted",
        "web_and_miniapp_clients": "not_accepted"
      }
    },
    "intensity_evidence_source": {
      "applies_to": "historical intensity evidence and recommendation rationale",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "activity_average_power_allowed": false,
        "allowed": [
          "activity_splits",
          "activity_samples"
        ],
        "missing_split_or_sample_evidence_result": "intensity_inference_unavailable"
      }
    },
    "managed_plan_policy_scope": {
      "applies_to": "every Praxys-owned managed-plan policy and client",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "applies_to": "all_praxys_owned_managed_plans",
        "disciplines": [
          "running",
          "trail_running"
        ],
        "distance_policies_must_not_duplicate_shared_loop": true,
        "distance_policies_supply": [
          "eligibility",
          "candidate_strategies",
          "task_specific_constraints",
          "task_specific_evidence"
        ],
        "intents": [
          "race",
          "performance",
          "consistency_base",
          "approved_future_intents"
        ],
        "shared_semantics": [
          "recommendation",
          "athlete_review",
          "observation",
          "feedback",
          "reassessment",
          "outcome_interpretation"
        ],
        "surfaces": [
          "web",
          "miniapp",
          "plugin",
          "mcp"
        ]
      }
    },
    "meaningful_change_policy": {
      "applies_to": "response classification and outcome evaluation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.error-aware-response-classification",
        "field-test.protocol-validity-reliability-sensitivity",
        "field-test.running-reliability-and-sensitivity-underreported"
      ],
      "value": {
        "exact_protocol_thresholds": "not_accepted",
        "rule": "protocol_specific_and_error_aware",
        "universal_percentage_allowed": false,
        "zero_based_responder_threshold_allowed": false
      }
    },
    "medical_stop_boundary": {
      "applies_to": "context intake, recommendation, proposal, and reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "athlete_reported_states": [
          "injury",
          "acute_illness",
          "red_flag_symptoms"
        ],
        "diagnosis_or_treatment_allowed": false,
        "next_step": "stop_performance_optimization_and_show_appropriate_non_diagnostic_guidance",
        "performance_optimization_continues": false,
        "return_to_sport_prescription_allowed": false
      }
    },
    "missed_session_catch_up": {
      "applies_to": "interruption and planned-versus-completed handling",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.ten-percent-rule-not-safety-law",
        "detraining.short-term-system-specific"
      ],
      "value": {
        "automatic_compression": false,
        "automatic_doubling": false,
        "missed_session_alone_reveals_cause_or_capacity": false,
        "proportional_replacement": false,
        "reassessment_may_propose_smallest_supported_change": true
      }
    },
    "observation_and_feedback_contract": {
      "applies_to": "execution, context, checkpoint, and terminal outcome evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.no-permanent-responder-label",
        "outcome.subjective-monitoring-adds-signal",
        "outcome.single-indicator-insufficient",
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "adherence_proves_adaptation": false,
        "athlete_feedback_proves_causality": false,
        "feedback_creates_permanent_responder_label": false,
        "feedback_may_inform_versioned_reassessment": true,
        "minimum_necessary_structured_context_preferred": true,
        "observation_classes": [
          "completed_training",
          "planned_vs_completed_divergence",
          "athlete_edit_rejection_or_deferral",
          "perceived_response",
          "recovery_or_symptom_report",
          "changed_availability",
          "comparable_checkpoint_or_goal_outcome"
        ],
        "one_workout_usually_sufficient_to_validate_policy": false,
        "provenance_classes": [
          "observed",
          "athlete_stated",
          "inferred",
          "assumed",
          "unknown"
        ]
      }
    },
    "online_learning_and_policy_updates": {
      "applies_to": "policy, model, prompt, and autonomy updates",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.no-permanent-responder-label",
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "feedback_may_support_future_human_reviewed_successor": true,
        "permanent_responder_profile_from_feedback": false,
        "runtime_autonomy_expansion_from_feedback": false,
        "runtime_prompt_authority_expansion_from_feedback": false,
        "runtime_rule_updates_from_feedback": false,
        "runtime_weight_updates_from_feedback": false,
        "successor_requires": [
          "versioned_evidence",
          "accepted_science_decision",
          "deterministic_validation",
          "implementation_approval"
        ]
      }
    },
    "privacy_and_traceability": {
      "applies_to": "context, evidence snapshots, recommendations, and decision traces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.subjective-monitoring-adds-signal",
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "account_deletion_covers_context_and_derived_adaptive_traces": true,
        "athlete_can_correct_exclude_and_delete_context": true,
        "decision_trace_requires": [
          "owning_user",
          "evidence_snapshot",
          "proposal_or_position",
          "policy_model_and_science_versions",
          "source_revisions",
          "later_outcome_links"
        ],
        "minimum_necessary_structured_context_preferred": true,
        "personal_context_optional": true,
        "purpose_limited_collection": true,
        "raw_free_text_in_generic_decision_trace_allowed": false,
        "sensitive_trait_inference_allowed": false,
        "source_provenance_visible": true
      }
    },
    "proposal_outcomes": {
      "applies_to": "managed-plan recommendation API and client states",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "outcome.single-indicator-insufficient"
      ],
      "value": {
        "every_type_requires_next_action": true,
        "every_type_requires_reason_and_uncertainty": true,
        "success_shaped_fallback_for_unavailable_route": false,
        "types": {
          "clarification_required": "one_focused_optional_question",
          "insufficient_evidence": "no_invented_action_and_one_concrete_evidence_step",
          "no_change": "keep_current_plan_with_reason_and_next_observation",
          "propose_change": "reviewable_non_canonical_diff",
          "safety_stop": "stop_performance_optimization_without_diagnosis",
          "unsupported_route": "preserve_goal_and_offer_supported_alternative_or_honest_stop"
        }
      }
    },
    "reassessment_contract": {
      "applies_to": "workout, week, block, goal, pause, resume, and outcome reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "detraining.short-term-system-specific",
        "field-test.protocol-validity-reliability-sensitivity",
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "required_comparison": [
          "prior_position",
          "new_or_corrected_evidence",
          "unchanged_evidence",
          "contrary_signals",
          "expected_vs_observed_signal",
          "current_unknowns",
          "goal_implication",
          "plan_implication"
        ],
        "result_must_reference_policy_model_and_science_versions": true,
        "result_types": [
          "propose_change",
          "no_change",
          "clarification_required",
          "insufficient_evidence",
          "safety_stop",
          "unsupported_route"
        ],
        "silent_rebase_or_plan_rewrite_allowed": false,
        "smallest_supported_scope_preferred": true,
        "stale_proposal_requires_new_evidence_snapshot": true
      }
    },
    "reassessment_trigger_algorithm": {
      "applies_to": "reassessment scheduler and event handling",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "detraining.short-term-system-specific",
        "field-test.running-reliability-and-sensitivity-underreported"
      ],
      "value": {
        "availability_change_threshold": "not_accepted",
        "checkpoint_threshold": "not_accepted",
        "goal_expectation_change_threshold": "not_accepted",
        "recovery_or_symptom_threshold": "not_accepted",
        "scheduled_cadence": "not_accepted",
        "workout_divergence_threshold": "not_accepted"
      }
    },
    "recommendation_loop_state_machine": {
      "applies_to": "adaptive-plan decision, proposal, revision, and outcome traces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "adoption_commits_one_exact_version": true,
        "athlete_edit_creates_successor_proposal": true,
        "deferral_preserves_canonical_plan": true,
        "deterministic_replay_required": true,
        "evidence_snapshot_is_immutable": true,
        "observation_does_not_rewrite_prior_decision": true,
        "proposal_is_immutable_and_non_canonical": true,
        "reassessment_appends_a_new_versioned_decision": true,
        "rejection_preserves_canonical_plan": true,
        "stages": [
          "sense",
          "select_candidate_strategy",
          "propose",
          "athlete_review",
          "observe",
          "reassess"
        ]
      }
    },
    "recommendation_reasoning_contract": {
      "applies_to": "recommendation, clarification, no-change, and outcome explanations",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.error-aware-response-classification",
        "outcome.subjective-monitoring-adds-signal",
        "outcome.observations-not-causal-explanation"
      ],
      "value": {
        "applicable_science_requires_exact_record_and_claim_references": true,
        "athlete_specific_rationale_must_name_relevant_current_evidence": true,
        "causal_language_without_causal_design": false,
        "evidence_classes": [
          "observed",
          "athlete_stated",
          "inferred",
          "assumed",
          "unknown"
        ],
        "expected_signal_must_state_supporting_and_contrary_observations": true,
        "feedback_request_must_be_purpose_bounded": true,
        "no_change_must_explain_what_remains_supported_and_what_to_observe": true,
        "uncertainty_must_name_material_unknowns": true
      }
    },
    "strategy_selection_algorithm": {
      "applies_to": "candidate selection policy",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.hrv-guidance-limited",
        "feasibility.no-permanent-responder-label"
      ],
      "value": {
        "candidate_ranking": "not_accepted",
        "context_interactions": "not_accepted",
        "exploration_or_experiment_assignment": "not_accepted",
        "model_or_llm_role": "not_accepted",
        "tie_breaking": "not_accepted"
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:b2108b70a45355a5f4c0a189cadfc3f6d33980daf0e5efa0db17a7d6e652e1c2"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If accepted by a digest-bound human decision approver, this inactive shared policy would require every Praxys-owned managed-plan route to take a concrete, reviewable position instead of returning only caveats, disclaimers, or data summaries. When an accepted route is safe and supported, the result must state the next action, why it fits the athlete's current evidence, which accepted science constrains the recommendation, the expected signal, material uncertainty, and what feedback will inform reassessment. A justified no-change decision is an actionable position when it explains what remains supported and what to observe next. Clarification, insufficient-evidence, unsupported-route, and safety-stop results must also provide a concrete next step without inventing a success-shaped plan. Distance and intent policies supply accepted candidate strategies, constraints, and task-specific evidence; this shared policy owns recommendation, athlete review, observation, feedback, reassessment, and outcome semantics so each distance does not build a second adaptive engine. Scientific findings and population evidence remain bounded candidate context and qualitative initial priors, not universal personal prescriptions, calibrated probabilities, or permanent runner identities. Proposals remain suggestion-first, immutable, source-labelled, editable, rejectable, and non-canonical until the athlete adopts an exact version. Later training, athlete feedback, recovery or symptom reports, and comparable outcomes may update the evidence state and trigger a new versioned reassessment; they do not prove individual causality or authorize runtime self-modification. Personal probabilities, permanent responder labels, automatic missed-session catch-up, ACWR prescription zones, fixed detraining loss, activity-average-power intensity inference, medical diagnosis, unreviewed online learning, and hidden sensitive inference remain prohibited. Exact strategy selection, weighting, thresholds, triggers, distance-specific dose and schedule, autonomy, pilot criteria, implementation, and runtime activation remain explicitly not accepted.",
  "affected_surfaces": {
    "apis": [
      "Future managed-plan assessment and recommendation endpoint",
      "Future plan proposal, edit, reject, defer, and adoption endpoints",
      "Future context request, observation, reassessment, and outcome endpoints",
      "Future shared contract discovery and provenance fields"
    ],
    "clients": [
      "Web Today, Training, Analysis, Goal, and managed-plan review experiences",
      "WeChat miniapp Today, Training, Analysis, Goal, and managed-plan parity",
      "Praxys plugin and MCP read/propose flows with athlete-controlled mutation",
      "English and Chinese recommendation, uncertainty, feedback, and safety copy"
    ],
    "models": [
      "adaptive-plan goal feasibility and expectation contract",
      "shared managed-plan recommendation policy",
      "adaptive-plan proposal, athlete decision, and revision trace",
      "adaptive-plan observation, reassessment, outcome, and gap review",
      "managed-plan capability registry and distance-policy dependency graph"
    ],
    "science_notes": [
      "Why this recommendation fits the current athlete evidence",
      "Applicable science, candidate-strategy limits, and expected signal",
      "Goal feasibility methodology and probability limits",
      "Feedback, reassessment, comparable outcomes, and causal limits"
    ]
  },
  "applicability": [
    "All Praxys-owned managed plans after their distance, intent, capability, history, and safety routes are separately accepted",
    "Adult self-coached runners and trail runners within the accepted policy that supplies candidate strategies",
    "Web, WeChat miniapp, plugin, and MCP surfaces using the same managed-plan contract",
    "Suggestion-first recommendation, athlete review, observation, reassessment, and outcome interpretation",
    "Direct performance interpretation only when baseline and outcome protocols are comparable"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-08-16",
  "decision_notes": [
    "This artifact-mode Decision proposal upgrades the merged #607 draft for issue #713 and remains draft and inactive.",
    "The five Evidence Reviews were rerun through 2026-08-16, converted to artifact mode, and bound to complete PubMed search manifests. Four more direct 2023-2025 reviews were added; no sixth Evidence Review is required.",
    "The positive actionable recommendation requirement is a Praxys product guardrail supported by PRODUCT.md. The scientific evidence constrains candidate use, measurement, uncertainty, and causal claims; it does not prove this loop or any update algorithm is optimal.",
    "Human review must use the generated packets rather than raw YAML. The decision packet begins with five proposed approvals and three explicit deferrals and embeds the exact inactive machine contract.",
    "Accepted 5 km, 10 km, half-marathon, baseline, eligibility, and marathon records are not rewritten here. Their successor or implementation alignment is mapped before shared runtime governance.",
    "All unresolved behavior-driving values are literal `not_accepted`; no implementation may infer a value from source findings, another distance, common coaching practice, prose, or AI output.",
    "Impact map: five draft Evidence Reviews and search manifests -> generated evidence packets -> draft shared SDR -> generated decision packet and inactive contract -> human evidence and decision review -> coordinated accepted-policy alignment -> future deterministic policy mapping -> persistence and API -> web, miniapp, plugin, and MCP parity -> ScienceNote and localization -> offline replay and privacy validation -> prospective opt-in pilot -> separate implementation review -> separately approved activation."
  ],
  "decision_review": {
    "approval_statement": "I approve one shared inactive managed-plan recommendation contract. For an accepted safe route, Praxys must take a concrete and reviewable position, explain why it fits the athlete, identify the applicable science, state the expected signal and uncertainty, and request the feedback needed for reassessment. I approve science and distance-specific findings only as bounded candidate context, not universal personal rules, probabilities, or permanent runner identities. I approve the athlete-controlled sense-propose-review-observe-reassess loop, typed no-change and non-generation outcomes, comparable-outcome and causal limits, safety stops, source provenance, privacy, and the prohibition on disclaimer-only output and unreviewed online learning. I approve keeping these semantics shared across all managed plans while preserving accepted records until coordinated successor alignment. I agree that exact selection, weighting, thresholds, triggers, distance-specific dose and schedules, autonomy, implementation, pilot criteria, and runtime activation remain deferred. This approval would not approve implementation or activate the contract.",
    "items": [
      {
        "approval_effect": [
          "Every managed-plan result has a typed position and concrete next step.",
          "The recommendation exposes athlete-specific rationale, applicable science, expected signal, uncertainty, and feedback request.",
          "Feasibility terms align with the existing goal-contract vocabulary without implying a probability."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Any category threshold, personal probability, workout, dose, schedule, implementation, or activation.",
          "A success-shaped plan when the route is unsupported, unsafe, or lacks required evidence."
        ],
        "evidence_claim_ids": [
          "feasibility.group-evidence-not-personal-probability",
          "feasibility.calibration-required",
          "load.structured-training-bounded-benefit",
          "outcome.single-indicator-insufficient"
        ],
        "id": "actionable-position",
        "parameter_names": [
          "managed_plan_policy_scope",
          "actionable_recommendation_contract",
          "goal_feasibility_semantics",
          "proposal_outcomes"
        ],
        "proposed_decision": "Require an actionable position. A change proposal, justified no-change, focused clarification, insufficient-evidence result, unsupported-route result, or safety stop must state the next step. For supported safe routes, caveats or data summaries alone are not a valid product result.",
        "question": "Should every accepted safe managed-plan route return a concrete, reviewable position with a next action and required reasoning fields?",
        "title": "Require a concrete recommendation, not disclaimer-only output"
      },
      {
        "approval_effect": [
          "Distance policies provide task-specific candidate context without duplicating the shared loop.",
          "Recommendation reasoning remains source-labelled and inspectable.",
          "Historical intensity evidence remains split- or sample-based."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Choosing a candidate strategy with an unreviewed algorithm or LLM judgment.",
          "Using activity average power, a permanent responder label, or a population association as an individual prescription."
        ],
        "evidence_claim_ids": [
          "feasibility.error-aware-response-classification",
          "feasibility.no-permanent-responder-label",
          "load.hrv-guidance-limited",
          "load.acwr-not-causal-threshold",
          "field-test.protocol-validity-reliability-sensitivity",
          "outcome.observations-not-causal-explanation"
        ],
        "id": "bounded-science",
        "parameter_names": [
          "candidate_strategy_evidence_boundary",
          "recommendation_reasoning_contract",
          "intensity_evidence_source"
        ],
        "proposed_decision": "Use accepted population findings and distance-specific policies to define candidate strategies and constraints. Require each recommendation to show the evidence class and exact science references. Do not promote one cohort result, theory, or observed response into a universal rule, permanent identity, or personal causal claim.",
        "question": "Should accepted science and distance policies constrain candidate strategies while the recommendation distinguishes evidence from inference, assumption, athlete report, and unknowns?",
        "title": "Use science as bounded candidate context, not a personal rule"
      },
      {
        "approval_effect": [
          "Recommendation, adoption, observation, and reassessment are traceable and replayable.",
          "Athlete adoption, edit, rejection, and deferral remain distinct from model output.",
          "Comparable protocols and measurement uncertainty govern direct outcome interpretation."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "An exact feedback weight, reassessment trigger, meaningful-change threshold, or automatic plan mutation.",
          "Treating adherence or one outcome as proof that the plan caused the result."
        ],
        "evidence_claim_ids": [
          "feasibility.error-aware-response-classification",
          "detraining.short-term-system-specific",
          "detraining.partial-not-complete-cessation",
          "field-test.protocol-validity-reliability-sensitivity",
          "field-test.running-reliability-and-sensitivity-underreported",
          "field-test.critical-speed-protocol-dependent",
          "outcome.subjective-monitoring-adds-signal",
          "outcome.single-indicator-insufficient",
          "outcome.observations-not-causal-explanation"
        ],
        "id": "athlete-controlled-loop",
        "parameter_names": [
          "recommendation_loop_state_machine",
          "athlete_authority_and_consent",
          "observation_and_feedback_contract",
          "reassessment_contract",
          "comparable_outcome_protocol_required",
          "meaningful_change_policy",
          "causal_gap_explanation"
        ],
        "proposed_decision": "Accept the shared loop stages and athlete responses. Proposals remain non-canonical until exact adoption; an edit creates a successor. Completed training, plan divergence, athlete choices, perceived response, recovery or symptom reports, availability, and comparable outcomes may inform reassessment without proving causality.",
        "question": "Should every managed plan use one versioned sense-select-propose-review-observe-reassess loop with immutable evidence and proposal traces?",
        "title": "Accept one athlete-controlled feedback and reassessment loop"
      },
      {
        "approval_effect": [
          "The shared loop cannot convert uncertainty into false precision or hidden automation.",
          "Safety stops remain separate from performance adaptation.",
          "Feedback and decision traces retain provenance without storing unrestricted sensitive narrative."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Diagnosis, treatment, medical clearance, return-to-sport prescription, or a safety guarantee.",
          "Runtime self-training, inferred sensitive traits, or permanent physiological profiling."
        ],
        "evidence_claim_ids": [
          "feasibility.calibration-required",
          "feasibility.no-permanent-responder-label",
          "load.ten-percent-rule-not-safety-law",
          "load.acwr-not-causal-threshold",
          "detraining.short-term-system-specific",
          "outcome.observations-not-causal-explanation"
        ],
        "id": "hard-boundaries",
        "parameter_names": [
          "feasibility_probability",
          "missed_session_catch_up",
          "acwr_prescription_thresholds",
          "fixed_detraining_loss_per_day",
          "medical_stop_boundary",
          "online_learning_and_policy_updates",
          "privacy_and_traceability"
        ],
        "proposed_decision": "Keep those prohibitions. Athlete-reported injury, acute illness, or red-flag symptoms stop performance optimization. Feedback can inform a future human-reviewed policy but cannot change runtime weights, rules, or autonomy. Context stays optional, purpose-limited, correctable, and deletable.",
        "question": "Should personal probabilities, catch-up, ACWR zones, fixed detraining loss, permanent responder labels, unreviewed online learning, medical optimization, and hidden sensitive inference remain prohibited?",
        "title": "Accept safety, epistemic, learning, and privacy boundaries"
      },
      {
        "approval_effect": [
          "New managed-plan policies depend on the shared contract instead of duplicating it.",
          "Existing accepted records remain auditable and are not rewritten by this decision.",
          "Marathon keeps its already-declared shared dependency."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Rewriting an accepted SDR, changing shipped 5 km behavior, or activating any distance policy.",
          "Treating cross-distance scientific findings as interchangeable dose or schedule rules."
        ],
        "evidence_claim_ids": [
          "feasibility.group-evidence-not-personal-probability",
          "outcome.observations-not-causal-explanation"
        ],
        "id": "shared-policy-alignment",
        "parameter_names": [
          "accepted_policy_alignment_gate"
        ],
        "proposed_decision": "Accept one shared contract. Existing accepted 5 km, 10 km, half-marathon, baseline, eligibility, and marathon decisions retain their history. Each requires the mapped successor or implementation alignment before shared runtime governance; no distance policy may silently create a second feedback engine.",
        "question": "Should one shared contract govern all managed-plan recommendation and feedback semantics while accepted distance records remain unchanged until explicit successor or implementation alignment?",
        "title": "Keep recommendation and feedback semantics shared across plans"
      },
      {
        "approval_effect": [
          "The shared contract defines required semantics without pretending an optimal update algorithm is known.",
          "Future policy work can be reviewed as explicit behavior rather than inferred from prose."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Filling any value from common coaching practice, another distance, model output, or AI.",
          "Updating the policy from observed feedback without a successor decision."
        ],
        "evidence_claim_ids": [
          "feasibility.error-aware-response-classification",
          "feasibility.calibration-required",
          "load.hrv-guidance-limited",
          "field-test.running-reliability-and-sensitivity-underreported"
        ],
        "id": "defer-selection-and-update",
        "parameter_names": [
          "goal_feasibility_semantics",
          "meaningful_change_policy",
          "strategy_selection_algorithm",
          "feedback_weighting_algorithm",
          "reassessment_trigger_algorithm"
        ],
        "proposed_decision": "Keep every mapped value literally not accepted. A later reviewed decision must define one narrow deterministic policy and its population, inputs, comparator, error handling, and falsification plan.",
        "question": "Should exact candidate ranking, feedback weighting, reassessment triggers, feasibility cut points, and meaningful-change thresholds remain unresolved?",
        "title": "Keep selection, feedback weighting, triggers, and thresholds open"
      },
      {
        "approval_effect": [
          "Recommendation semantics can be reviewed independently from distance-specific prescriptions.",
          "Suggestion-first remains the only accepted autonomy mode."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "A workout, plan horizon, progression, target, automatic adoption, provider delivery, or autonomous goal change.",
          "Inheriting a rule from another distance or training base."
        ],
        "evidence_claim_ids": [
          "load.structured-training-bounded-benefit",
          "load.ten-percent-rule-not-safety-law",
          "detraining.reduced-dose-maintenance"
        ],
        "id": "defer-distance-rules-and-autonomy",
        "parameter_names": [
          "distance_specific_generation_rules",
          "autonomy_expansion_policy"
        ],
        "proposed_decision": "Keep distance-specific generation values and autonomy expansion unresolved. Distance policies must provide accepted candidate rules and safety constraints; this shared contract does not choose their values.",
        "question": "Should workout selection, dose, schedule, progression, recovery, fueling, environment, and any automatic adoption permission remain separate decisions?",
        "title": "Keep distance-specific generation and autonomy open"
      },
      {
        "approval_effect": [
          "Human evidence and decision review can complete without shipping behavior.",
          "Runtime code cannot consume this contract as active."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Database, API, analysis, UI, plugin, MCP, telemetry, model, rollout, or activation changes.",
          "Claiming benefit, safety, or personalization efficacy before prospective evaluation."
        ],
        "evidence_claim_ids": [
          "feasibility.calibration-required",
          "outcome.observations-not-causal-explanation"
        ],
        "id": "defer-implementation-and-activation",
        "parameter_names": [
          "implementation_pilot_and_activation"
        ],
        "proposed_decision": "Keep the contract inactive. Require a reviewed deterministic mapping, web and miniapp parity, plugin and MCP parity, privacy controls, prospective pilot design, and separate implementation approval before any runtime use.",
        "question": "Should persistence, APIs, clients, pilot thresholds, implementation approval, rollout, and runtime activation remain outside this decision?",
        "title": "Keep implementation, pilot criteria, and activation open"
      }
    ],
    "reviewer_task": "Decide whether the five proposed shared product boundaries are acceptable and whether the three implementation areas should remain explicitly deferred. Approve the sheet as a unit or request changes by item ID. The audit appendix is traceability, not the primary review task."
  },
  "evidence_claim_ids": [
    "feasibility.group-evidence-not-personal-probability",
    "feasibility.error-aware-response-classification",
    "feasibility.no-permanent-responder-label",
    "feasibility.calibration-required",
    "load.structured-training-bounded-benefit",
    "load.hrv-guidance-limited",
    "load.ten-percent-rule-not-safety-law",
    "load.acwr-not-causal-threshold",
    "detraining.short-term-system-specific",
    "detraining.reduced-dose-maintenance",
    "detraining.partial-not-complete-cessation",
    "field-test.protocol-validity-reliability-sensitivity",
    "field-test.running-reliability-and-sensitivity-underreported",
    "field-test.vo2-estimate-not-direct-performance",
    "field-test.critical-speed-protocol-dependent",
    "outcome.subjective-monitoring-adds-signal",
    "outcome.single-indicator-insufficient",
    "outcome.observations-not-causal-explanation"
  ],
  "evidence_review_ids": [
    "evidence-individual-goal-feasibility-v1",
    "evidence-adaptive-training-load-v1",
    "evidence-short-interruption-detraining-v1",
    "evidence-running-field-tests-v1",
    "evidence-plan-outcome-interpretation-v1"
  ],
  "falsification_conditions": [
    "A supported safe route returns only caveats, disclaimers, or data without a concrete next action.",
    "Web, miniapp, plugin, or MCP surfaces produce different recommendation or athlete-decision semantics for the same policy input.",
    "A category is interpreted as a calibrated probability or guarantee despite the claim limits.",
    "One observed result creates a permanent responder identity or silently changes future policy weights.",
    "Repeated comparable tests show changes within measurement noise while Praxys labels them meaningful.",
    "Prospective evaluation finds that the policy worsens goal outcomes, athlete burden, or safety events versus the predefined comparator.",
    "A recommendation, proposal, or reassessment cannot be reproduced from its versioned evidence, policy, model, and science inputs.",
    "Context deletion fails to remove the athlete's private plan context or derived adaptive traces.",
    "A policy applies catch-up, workload-ratio, fixed detraining, activity-average-power, or causal-explanation rules that this decision disables.",
    "A distance policy implements a second recommendation or feedback engine instead of the shared contract."
  ],
  "id": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
  "model_parameters": [
    {
      "applies_to": "every Praxys-owned managed-plan policy and client",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "managed_plan_policy_scope",
      "rationale": "Recommendation and feedback semantics are cross-cutting product behavior. Distance and intent policies remain responsible for accepted task-specific candidates and constraints.",
      "value": {
        "applies_to": "all_praxys_owned_managed_plans",
        "disciplines": [
          "running",
          "trail_running"
        ],
        "distance_policies_must_not_duplicate_shared_loop": true,
        "distance_policies_supply": [
          "eligibility",
          "candidate_strategies",
          "task_specific_constraints",
          "task_specific_evidence"
        ],
        "intents": [
          "race",
          "performance",
          "consistency_base",
          "approved_future_intents"
        ],
        "shared_semantics": [
          "recommendation",
          "athlete_review",
          "observation",
          "feedback",
          "reassessment",
          "outcome_interpretation"
        ],
        "surfaces": [
          "web",
          "miniapp",
          "plugin",
          "mcp"
        ]
      }
    },
    {
      "applies_to": "recommendation and no-plan result contracts",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "feasibility.calibration-required",
        "outcome.single-indicator-insufficient"
      ],
      "name": "actionable_recommendation_contract",
      "rationale": "This is Praxys's positive product-value contract. It does not assert that one algorithm is biologically optimal; it requires safe uncertainty to shape a useful position instead of replacing it.",
      "value": {
        "clarification_requires_one_focused_question": true,
        "data_summary_only_output_allowed": false,
        "disclaimer_only_output_allowed": false,
        "insufficient_evidence_requires_concrete_next_evidence_action": true,
        "justified_no_change_is_actionable": true,
        "required_fields": [
          "next_action",
          "athlete_specific_rationale",
          "applicable_science",
          "expected_signal",
          "uncertainty",
          "feedback_request"
        ],
        "safety_stop_requires_concrete_non_diagnostic_next_step": true,
        "supported_safe_route_requires_actionable_position": true,
        "unsupported_route_requires_supported_alternative_or_honest_stop": true
      }
    },
    {
      "applies_to": "candidate strategy registry and recommendation reasoning",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "feasibility.no-permanent-responder-label",
        "load.structured-training-bounded-benefit",
        "load.hrv-guidance-limited"
      ],
      "name": "candidate_strategy_evidence_boundary",
      "rationale": "The reviewed evidence constrains overclaiming and candidate applicability but does not validate a universal strategy-selection algorithm.",
      "value": {
        "accepted_science_role": "constrain_candidate_set_and_explain_applicability",
        "athlete_observations_role": "update_current_state_and_test_fit_within_reviewed_policy",
        "candidate_prior_is_personal_probability": false,
        "distance_policy_role": "supply_task_specific_candidates_and_constraints",
        "one_observed_response_creates_permanent_identity": false,
        "population_association_becomes_personal_rule": false,
        "population_findings_role": "bounded_candidate_context_and_qualitative_initial_prior",
        "unaccepted_source_may_drive_behavior": false
      }
    },
    {
      "applies_to": "recommendation, clarification, no-change, and outcome explanations",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.error-aware-response-classification",
        "outcome.subjective-monitoring-adds-signal",
        "outcome.observations-not-causal-explanation"
      ],
      "name": "recommendation_reasoning_contract",
      "rationale": "These fields make the recommendation inspectable and keep observation, inference, assumption, and unknowns distinct.",
      "value": {
        "applicable_science_requires_exact_record_and_claim_references": true,
        "athlete_specific_rationale_must_name_relevant_current_evidence": true,
        "causal_language_without_causal_design": false,
        "evidence_classes": [
          "observed",
          "athlete_stated",
          "inferred",
          "assumed",
          "unknown"
        ],
        "expected_signal_must_state_supporting_and_contrary_observations": true,
        "feedback_request_must_be_purpose_bounded": true,
        "no_change_must_explain_what_remains_supported_and_what_to_observe": true,
        "uncertainty_must_name_material_unknowns": true
      }
    },
    {
      "applies_to": "managed-plan goal feasibility and expectation assessments",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "feasibility.calibration-required"
      ],
      "name": "goal_feasibility_semantics",
      "rationale": "The names align with the existing goal-contract proposal. The vocabulary is a product guardrail; exact cut points remain unresolved.",
      "value": {
        "categories": {
          "aggressive": "material_gap_or_compressed_horizon_requires_warning_and_alternatives",
          "challenging": "plausible_with_material_execution_or_uncertainty_risks",
          "insufficient_evidence": "current_evidence_cannot_responsibly_assess_target",
          "supported": "no_material_concern_found_under_current_accepted_policy",
          "unsupported": "outside_an_accepted_planning_boundary"
        },
        "category_is_personal_probability": false,
        "category_thresholds": "not_accepted",
        "confidence_style": "qualitative_and_explained",
        "unsupported_allows_normal_success_shaped_plan": false
      }
    },
    {
      "applies_to": "adaptive-plan decision, proposal, revision, and outcome traces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.observations-not-causal-explanation"
      ],
      "name": "recommendation_loop_state_machine",
      "rationale": "The loop is a product architecture and audit boundary, not a published physiological algorithm.",
      "value": {
        "adoption_commits_one_exact_version": true,
        "athlete_edit_creates_successor_proposal": true,
        "deferral_preserves_canonical_plan": true,
        "deterministic_replay_required": true,
        "evidence_snapshot_is_immutable": true,
        "observation_does_not_rewrite_prior_decision": true,
        "proposal_is_immutable_and_non_canonical": true,
        "reassessment_appends_a_new_versioned_decision": true,
        "rejection_preserves_canonical_plan": true,
        "stages": [
          "sense",
          "select_candidate_strategy",
          "propose",
          "athlete_review",
          "observe",
          "reassess"
        ]
      }
    },
    {
      "applies_to": "proposal review, goal change, pause, resume, and end flows",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "athlete_authority_and_consent",
      "rationale": "Explicit athlete control keeps early policy behavior observable, reversible, and separate from future autonomy decisions.",
      "value": {
        "allowed_responses": [
          "adopt",
          "edit_into_successor",
          "reject",
          "defer"
        ],
        "athlete_constraints_are_authoritative": true,
        "default_mode": "athlete_approved_suggestions",
        "goal_change_requires_successor_and_acknowledgement": true,
        "pause_or_end_requires_explicit_athlete_action_or_separate_safety_policy": true,
        "proposal_is_canonical_before_adoption": false,
        "rejection_reason_optional": true
      }
    },
    {
      "applies_to": "execution, context, checkpoint, and terminal outcome evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.no-permanent-responder-label",
        "outcome.subjective-monitoring-adds-signal",
        "outcome.single-indicator-insufficient",
        "outcome.observations-not-causal-explanation"
      ],
      "name": "observation_and_feedback_contract",
      "rationale": "Multiple source-labelled observations can reduce uncertainty without becoming proof of cause or a permanent physiological profile.",
      "value": {
        "adherence_proves_adaptation": false,
        "athlete_feedback_proves_causality": false,
        "feedback_creates_permanent_responder_label": false,
        "feedback_may_inform_versioned_reassessment": true,
        "minimum_necessary_structured_context_preferred": true,
        "observation_classes": [
          "completed_training",
          "planned_vs_completed_divergence",
          "athlete_edit_rejection_or_deferral",
          "perceived_response",
          "recovery_or_symptom_report",
          "changed_availability",
          "comparable_checkpoint_or_goal_outcome"
        ],
        "one_workout_usually_sufficient_to_validate_policy": false,
        "provenance_classes": [
          "observed",
          "athlete_stated",
          "inferred",
          "assumed",
          "unknown"
        ]
      }
    },
    {
      "applies_to": "workout, week, block, goal, pause, resume, and outcome reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "detraining.short-term-system-specific",
        "field-test.protocol-validity-reliability-sensitivity",
        "outcome.observations-not-causal-explanation"
      ],
      "name": "reassessment_contract",
      "rationale": "Reassessment should explain what changed and preserve contrary evidence, rather than turning every observation into a plan mutation.",
      "value": {
        "required_comparison": [
          "prior_position",
          "new_or_corrected_evidence",
          "unchanged_evidence",
          "contrary_signals",
          "expected_vs_observed_signal",
          "current_unknowns",
          "goal_implication",
          "plan_implication"
        ],
        "result_must_reference_policy_model_and_science_versions": true,
        "result_types": [
          "propose_change",
          "no_change",
          "clarification_required",
          "insufficient_evidence",
          "safety_stop",
          "unsupported_route"
        ],
        "silent_rebase_or_plan_rewrite_allowed": false,
        "smallest_supported_scope_preferred": true,
        "stale_proposal_requires_new_evidence_snapshot": true
      }
    },
    {
      "applies_to": "managed-plan recommendation API and client states",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.group-evidence-not-personal-probability",
        "outcome.single-indicator-insufficient"
      ],
      "name": "proposal_outcomes",
      "rationale": "Typed outcomes let the product remain useful and honest without silently converting uncertainty or unsupported scope into a normal plan.",
      "value": {
        "every_type_requires_next_action": true,
        "every_type_requires_reason_and_uncertainty": true,
        "success_shaped_fallback_for_unavailable_route": false,
        "types": {
          "clarification_required": "one_focused_optional_question",
          "insufficient_evidence": "no_invented_action_and_one_concrete_evidence_step",
          "no_change": "keep_current_plan_with_reason_and_next_observation",
          "propose_change": "reviewable_non_canonical_diff",
          "safety_stop": "stop_performance_optimization_without_diagnosis",
          "unsupported_route": "preserve_goal_and_offer_supported_alternative_or_honest_stop"
        }
      }
    },
    {
      "applies_to": "feasibility and recommendation claims",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.calibration-required"
      ],
      "name": "feasibility_probability",
      "rationale": "No reviewed source validates a Praxys personal goal-achievement probability.",
      "value": {
        "personal_probability_enabled": false,
        "prerequisite_before_future_enablement": [
          "defined_population_and_outcome",
          "representative_development_data",
          "prospective_calibration",
          "external_validation",
          "subgroup_and_drift_monitoring",
          "accepted_successor_decision",
          "implementation_approval"
        ]
      }
    },
    {
      "applies_to": "interruption and planned-versus-completed handling",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.ten-percent-rule-not-safety-law",
        "detraining.short-term-system-specific"
      ],
      "name": "missed_session_catch_up",
      "rationale": "A missed session does not reveal why it was missed or the athlete's current capacity, and no universal catch-up rule is validated.",
      "value": {
        "automatic_compression": false,
        "automatic_doubling": false,
        "missed_session_alone_reveals_cause_or_capacity": false,
        "proportional_replacement": false,
        "reassessment_may_propose_smallest_supported_change": true
      }
    },
    {
      "applies_to": "load evidence and proposal triggers",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.acwr-not-causal-threshold"
      ],
      "name": "acwr_prescription_thresholds",
      "rationale": "Workload history can remain descriptive, but ratio zones are not established causal safety thresholds.",
      "value": {
        "automatic_prescription_trigger_allowed": false,
        "causal_risk_zone_allowed": false,
        "descriptive_history_allowed": true
      }
    },
    {
      "applies_to": "interruption assessment and return proposals",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "detraining.short-term-system-specific",
        "detraining.reduced-dose-maintenance",
        "detraining.partial-not-complete-cessation"
      ],
      "name": "fixed_detraining_loss_per_day",
      "rationale": "Detraining differs by outcome, prior training, and whether training was reduced or stopped.",
      "value": {
        "enabled": false,
        "one_system_represents_all_capacity": false,
        "total_cessation_equals_partial_reduction": false
      }
    },
    {
      "applies_to": "baseline, checkpoint, and terminal outcome comparison",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "field-test.protocol-validity-reliability-sensitivity",
        "field-test.running-reliability-and-sensitivity-underreported",
        "field-test.vo2-estimate-not-direct-performance",
        "field-test.critical-speed-protocol-dependent"
      ],
      "name": "comparable_outcome_protocol_required",
      "rationale": "Validity alone does not establish repeatability, sensitivity, or equivalence for one athlete's change.",
      "value": {
        "cross_protocol_change_is_direct_evidence": false,
        "device_estimate_is_automatically_equivalent": false,
        "direct_change_evidence_requires": [
          "same_or_accepted_equivalent_protocol",
          "documented_conditions",
          "protocol_specific_reliability",
          "protocol_specific_sensitivity_or_error_boundary"
        ],
        "unlike_environment_is_automatically_equivalent": false
      }
    },
    {
      "applies_to": "response classification and outcome evaluation",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.error-aware-response-classification",
        "field-test.protocol-validity-reliability-sensitivity",
        "field-test.running-reliability-and-sensitivity-underreported"
      ],
      "name": "meaningful_change_policy",
      "rationale": "Measurement error and sensitivity vary by outcome, protocol, and population; exact thresholds require separate validation.",
      "value": {
        "exact_protocol_thresholds": "not_accepted",
        "rule": "protocol_specific_and_error_aware",
        "universal_percentage_allowed": false,
        "zero_based_responder_threshold_allowed": false
      }
    },
    {
      "applies_to": "context intake, recommendation, proposal, and reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "medical_stop_boundary",
      "rationale": "This is a product safety stop outside the performance-planning evidence, not a medical decision algorithm.",
      "value": {
        "athlete_reported_states": [
          "injury",
          "acute_illness",
          "red_flag_symptoms"
        ],
        "diagnosis_or_treatment_allowed": false,
        "next_step": "stop_performance_optimization_and_show_appropriate_non_diagnostic_guidance",
        "performance_optimization_continues": false,
        "return_to_sport_prescription_allowed": false
      }
    },
    {
      "applies_to": "checkpoint, terminal outcome, and plan gap review",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.observations-not-causal-explanation"
      ],
      "name": "causal_gap_explanation",
      "rationale": "Observations may support hypotheses and future tests but not definitive individual causal attribution.",
      "value": {
        "adherence_as_causal_proof_allowed": false,
        "definitive_individual_cause_allowed": false,
        "diagnosis_allowed": false,
        "future_testable_question_allowed": true,
        "output": "ranked_hypotheses_with_contrary_evidence_and_unknowns"
      }
    },
    {
      "applies_to": "historical intensity evidence and recommendation rationale",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "intensity_evidence_source",
      "rationale": "Activity-average power is diluted by warmup, cooldown, and recovery and cannot support interval-intensity interpretation.",
      "value": {
        "activity_average_power_allowed": false,
        "allowed": [
          "activity_splits",
          "activity_samples"
        ],
        "missing_split_or_sample_evidence_result": "intensity_inference_unavailable"
      }
    },
    {
      "applies_to": "policy, model, prompt, and autonomy updates",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "feasibility.no-permanent-responder-label",
        "outcome.observations-not-causal-explanation"
      ],
      "name": "online_learning_and_policy_updates",
      "rationale": "Feedback is evidence for reassessment and future policy research, not permission for unreviewed online learning.",
      "value": {
        "feedback_may_support_future_human_reviewed_successor": true,
        "permanent_responder_profile_from_feedback": false,
        "runtime_autonomy_expansion_from_feedback": false,
        "runtime_prompt_authority_expansion_from_feedback": false,
        "runtime_rule_updates_from_feedback": false,
        "runtime_weight_updates_from_feedback": false,
        "successor_requires": [
          "versioned_evidence",
          "accepted_science_decision",
          "deterministic_validation",
          "implementation_approval"
        ]
      }
    },
    {
      "applies_to": "context, evidence snapshots, recommendations, and decision traces",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.subjective-monitoring-adds-signal",
        "outcome.observations-not-causal-explanation"
      ],
      "name": "privacy_and_traceability",
      "rationale": "Optional context can improve interpretation only when its purpose, provenance, correction, access, and deletion boundaries are explicit.",
      "value": {
        "account_deletion_covers_context_and_derived_adaptive_traces": true,
        "athlete_can_correct_exclude_and_delete_context": true,
        "decision_trace_requires": [
          "owning_user",
          "evidence_snapshot",
          "proposal_or_position",
          "policy_model_and_science_versions",
          "source_revisions",
          "later_outcome_links"
        ],
        "minimum_necessary_structured_context_preferred": true,
        "personal_context_optional": true,
        "purpose_limited_collection": true,
        "raw_free_text_in_generic_decision_trace_allowed": false,
        "sensitive_trait_inference_allowed": false,
        "source_provenance_visible": true
      }
    },
    {
      "applies_to": "science lifecycle, implementation mapping, and managed-plan activation",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "accepted_policy_alignment_gate",
      "rationale": "Accepted records cannot be silently rewritten. The map preserves history while making future shared-loop alignment explicit.",
      "value": {
        "accepted_records_remain_unchanged_in_this_decision": true,
        "accepted_records_requiring_successor_or_explicit_implementation_alignment": [
          "sdr-preplan-baseline-policy-v1",
          "sdr-outdoor-5k-plan-generation-policy-v1",
          "sdr-road-10k-plan-generation-policy-v1",
          "sdr-road-half-marathon-plan-generation-policy-v1"
        ],
        "new_managed_plan_policy_requires_shared_dependency": true,
        "no_distance_policy_may_define_a_second_feedback_engine": true,
        "records_already_naming_this_shared_policy": [
          "sdr-plan-generation-eligibility-safety-v1",
          "sdr-road-marathon-plan-generation-policy-v1"
        ],
        "shared_runtime_governance_before_alignment": false
      }
    },
    {
      "applies_to": "candidate selection policy",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.hrv-guidance-limited",
        "feasibility.no-permanent-responder-label"
      ],
      "name": "strategy_selection_algorithm",
      "rationale": "The reviewed evidence does not validate a Praxys-specific algorithm for selecting among candidate strategies.",
      "value": {
        "candidate_ranking": "not_accepted",
        "context_interactions": "not_accepted",
        "exploration_or_experiment_assignment": "not_accepted",
        "model_or_llm_role": "not_accepted",
        "tie_breaking": "not_accepted"
      }
    },
    {
      "applies_to": "evidence evaluation and reassessment",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "outcome.subjective-monitoring-adds-signal",
        "outcome.single-indicator-insufficient"
      ],
      "name": "feedback_weighting_algorithm",
      "rationale": "Multiple signals may inform reassessment, but no reviewed source defines their Praxys-specific weights or conflict resolution.",
      "value": {
        "athlete_report_weight": "not_accepted",
        "contradictory_signal_resolution": "not_accepted",
        "missingness_handling": "not_accepted",
        "observation_weights": "not_accepted",
        "recency_decay": "not_accepted"
      }
    },
    {
      "applies_to": "reassessment scheduler and event handling",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "detraining.short-term-system-specific",
        "field-test.running-reliability-and-sensitivity-underreported"
      ],
      "name": "reassessment_trigger_algorithm",
      "rationale": "The shared loop defines trigger categories but not exact timing or thresholds.",
      "value": {
        "availability_change_threshold": "not_accepted",
        "checkpoint_threshold": "not_accepted",
        "goal_expectation_change_threshold": "not_accepted",
        "recovery_or_symptom_threshold": "not_accepted",
        "scheduled_cadence": "not_accepted",
        "workout_divergence_threshold": "not_accepted"
      }
    },
    {
      "applies_to": "plan generation and distance-specific recommendation candidates",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "load.structured-training-bounded-benefit",
        "load.ten-percent-rule-not-safety-law",
        "detraining.reduced-dose-maintenance"
      ],
      "name": "distance_specific_generation_rules",
      "rationale": "These values remain owned by separately accepted distance, intent, and context policies.",
      "value": {
        "dose": "not_accepted",
        "environment_altitude": "not_accepted",
        "fueling_hydration": "not_accepted",
        "intensity_distribution": "not_accepted",
        "long_run": "not_accepted",
        "plan_horizon": "not_accepted",
        "progression": "not_accepted",
        "recovery": "not_accepted",
        "return_after_interruption": "not_accepted",
        "schedule": "not_accepted",
        "taper": "not_accepted",
        "workout_selection": "not_accepted"
      }
    },
    {
      "applies_to": "proposal approval, canonical mutation, and provider delivery",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "autonomy_expansion_policy",
      "rationale": "Any automatic action requires a separate exact consent, scope, evidence, implementation, and revocation decision.",
      "value": {
        "automatic_adoption_scope": "not_accepted",
        "automatic_goal_change": false,
        "automatic_pause_or_resume": "not_accepted",
        "automatic_provider_delivery": "not_accepted",
        "consent_model": "not_accepted",
        "current_default": "suggestion_only",
        "expiry_and_revocation": "not_accepted"
      }
    },
    {
      "applies_to": "implementation, pilot, rollout, and runtime",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "implementation_pilot_and_activation",
      "rationale": "Evidence and decision acceptance are separate from implementation, prospective evaluation, rollout, and activation.",
      "value": {
        "active_behavior": false,
        "analysis_mapping": "not_accepted",
        "api_contracts": "not_accepted",
        "comparator": "not_accepted",
        "implementation_approval": "not_accepted",
        "persistence_schema": "not_accepted",
        "pilot_population": "not_accepted",
        "plugin_and_mcp_contracts": "not_accepted",
        "primary_and_guardrail_metrics": "not_accepted",
        "privacy_operations": "not_accepted",
        "rollout": "not_accepted",
        "runtime_activation": "not_accepted",
        "sample_size_and_duration": "not_accepted",
        "science_note_and_localization": "not_accepted",
        "success_failure_and_rollback_thresholds": "not_accepted",
        "web_and_miniapp_clients": "not_accepted"
      }
    }
  ],
  "model_version": "adaptive-plan-policy-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Personal context is optional, purpose-limited, and private to the athlete's plan.",
    "Store structured minimum-necessary context separately from free text where possible.",
    "Show what context informed each recommendation and allow correction, exclusion, and deletion.",
    "Do not infer sensitive medical, family, employment, or identity details from behavior.",
    "Do not store unrestricted athlete narrative in generic decision traces.",
    "Athlete context and adaptive traces follow account deletion, retention, access, and export controls."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Return caveats, disclaimers, or data summaries without a concrete next action.",
      "rationale": "Praxys exists to interpret evidence into a reviewable position. Safety and uncertainty must shape the action, not replace product value when a safe supported route exists."
    },
    {
      "alternative": "Let each distance policy define its own recommendation and feedback loop.",
      "rationale": "Duplicated semantics would drift across web, miniapp, plugin, MCP, and distance policies and make athlete decisions and feedback incomparable."
    },
    {
      "alternative": "Present a numerical probability that an individual athlete will achieve the goal.",
      "rationale": "No prospectively calibrated and externally validated Praxys prediction model exists for the target population and supported goal types."
    },
    {
      "alternative": "Present qualitative feasibility categories as published scientific thresholds.",
      "rationale": "The reviewed research supports uncertainty boundaries, not the product vocabulary or category cut points."
    },
    {
      "alternative": "Assign a permanent responder or non-responder profile from one plan outcome.",
      "rationale": "Measurement error, within-person variation, protocol, and context can contribute to an observed response; one plan does not establish an intrinsic identity."
    },
    {
      "alternative": "Automatically make up, double, compress, or proportionally replace missed sessions.",
      "rationale": "No reviewed evidence validates a universal catch-up rule, and schedule interruption does not reveal the athlete's reason or current capacity."
    },
    {
      "alternative": "Use acute-to-chronic workload ratio zones or the 10 percent rule as causal safety limits.",
      "rationale": "The workload ratio has causal and statistical limitations, while the reviewed novice-runner trial did not show lower injury incidence from a 10 percent progression program."
    },
    {
      "alternative": "Infer a fixed percentage of fitness loss or return capacity from days missed.",
      "rationale": "Detraining differs by physiological system, training history, and whether training was reduced or stopped."
    },
    {
      "alternative": "Compare unlike tests, environments, or model estimates as direct evidence of improvement.",
      "rationale": "Test validity, reliability, sensitivity, and prediction error are protocol specific."
    },
    {
      "alternative": "Explain a goal miss from adherence, physiology, or athlete context alone.",
      "rationale": "These observations can inform hypotheses but do not establish individual causation without an appropriate prospective design."
    },
    {
      "alternative": "Let feedback automatically update runtime strategy weights, rules, prompts, or autonomy.",
      "rationale": "Observations can support future reviewed policy changes but do not authorize an unreviewed online-learning system."
    },
    {
      "alternative": "Continue performance-plan adaptation through illness, injury, or red-flag symptoms.",
      "rationale": "Medical assessment and return-to-sport decisions are outside this performance-planning evidence and require an explicit safety boundary."
    }
  ],
  "safety_implications": [
    "Illness, injury, and red-flag symptoms stop performance optimization rather than triggering an automated return prescription.",
    "No automatic doubling, catch-up, or compressed replacement of missed work.",
    "Every position identifies uncertainty and the next safe action.",
    "Goal, pause, resume, end, and plan-change proposals remain non-canonical until explicitly adopted under an accepted authority policy.",
    "Unsupported or unsafe routes never return a normal success-shaped plan."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Require actionable, feedback-aware recommendations across managed plans",
  "user_facing_claim_limits": [
    "Do not return only disclaimers or data summaries when a supported safe route can take an actionable position.",
    "Do not promise or guarantee goal achievement.",
    "Do not show an individual success probability until a prospectively calibrated and externally validated model is accepted.",
    "Label feasibility categories, candidate priors, adjustment scopes, and triggers as Praxys guidance rather than published thresholds.",
    "Distinguish what was observed, athlete-stated, inferred, assumed, and unknown.",
    "Do not call one plan result a permanent responder or non-responder identity.",
    "Do not imply that adherence proves adaptation or plan effectiveness.",
    "Do not imply that HRV, workload ratio, or one response metric dictates a workout.",
    "Do not call different protocols or environments equivalent direct evidence.",
    "Present post-plan reasons as ranked hypotheses, never diagnosis or established individual causation.",
    "Explain when a no-change, clarification, insufficient-evidence, unsupported-route, or safety-stop result is the concrete next action."
  ],
  "validation_plan": [
    "Human evidence review must accept, revise, or reject all five Evidence Reviews before this decision can be accepted.",
    "Human decision review must approve the decision sheet and inactive contract separately from implementation.",
    "Define one narrow deterministic suggestion-only policy with a versioned identifier, immutable evidence snapshot, and replay fixture.",
    "Predefine candidate strategies, outcome, comparable protocol, meaningful-change rule, safety events, and no-change comparator.",
    "Verify every supported safe fixture produces an actionable position with all required reasoning fields.",
    "Verify every clarification, insufficient-evidence, unsupported-route, and safety fixture produces a concrete next step without a success-shaped fallback.",
    "Add registry, policy, API-contract, web, miniapp, plugin, MCP, privacy, deletion, and client-state tests for every implemented boundary.",
    "Prospectively evaluate recommendation precision, usefulness, athlete adoption, edits, rejection, reversals, adverse events, and goal outcomes without updating runtime rules from those observations.",
    "Audit performance by sex, age, training history, goal type, distance, training base, missingness, language, surface, and data-provider provenance.",
    "Calibrate any future numerical feasibility model and validate it externally before exposing probabilities.",
    "Require an approved successor SDR for each algorithm, threshold, distance-policy alignment, or additional autonomous permission.",
    "Require separate implementation review before changing runtime_state from inactive."
  ],
  "version": 1
}
```

</details>
