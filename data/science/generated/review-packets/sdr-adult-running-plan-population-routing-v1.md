# Science decision review packet: Route first-completion, sparse-history, and masters plans without permanent labels

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-adult-running-plan-population-routing-v1`
- **Lifecycle:** `draft`
- **Model version:** `adult-running-plan-population-routing-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:87298990e39e3c1e0b632d03661cee4ffe37b92121e4395f7374c8b24d8b841d`
- **Contract digest:** `sha256:c2167596d846842bc73f65fccda75d232a1568f7f135ec0451bb32301410c04e`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Decide whether the six proposed population-routing boundaries are acceptable and whether exact plan values plus implementation should remain deferred. Approve the sheet as a unit or request changes by item ID. The evidence appendix and machine contract provide traceability; the eight items below are the actual decision.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `first-completion-family` — Let users choose completion goals without prior distance completion

- **Question:** Should first completion be a separate distance-specific policy family while goal selection remains available before that policy ships?
- **Proposed decision:** Yes. Prior completion of the goal distance is not required to record or select the goal. A first-completion route needs an independently accepted distance policy and cannot reuse a history-rich performance policy by reducing its dose. Performance intent without current direct capability remains unavailable or requires clarification rather than automatic coercion to completion intent.
- **Approval means:**
  - A user may select 5 km, 10 km, half-marathon, or marathon completion before being able to complete that distance.
  - First completion is an intent and current-capability route, not a permanent beginner identity.
  - Missing policy support preserves the goal and returns an honest unavailable result.
- **This does not authorize:**
  - Any first-completion schedule, capability identifier, workout, distance progression, or runtime route.
  - Automatic conversion between completion and performance intent.

<details><summary>Traceability: 2 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `population_routing_authority`, `first_completion_policy_family`
- **Evidence claims:** `eligibility.novice-recreational-different-evidence-family`, `eligibility.goal-relevant-current-capability-task-specific`, `population.beginner-evidence-family-not-permanent-identity`, `population.no-universal-beginner-schedule`

</details>

#### `sparse-history-and-returning` — Separate missing history, usable anchors, and return-to-consistency intent

- **Question:** Should sparse records remain an evidence state rather than proof of detraining, with returning-to-consistency requiring explicit or confirmed context?
- **Proposed decision:** Yes. A usable recent anchor may support only a separately accepted uncertainty-aware population route. No usable history yields readiness-only, while sparse history without a usable recent anchor yields insufficient_recent_history_anchor. Missing provider records do not prove training stopped. Return to consistency is user-selectable or athlete-confirmed. Observed continuity may refute an interruption but cannot establish a returning state. No return-to-consistency route can receive a dose-shaped schedule until its own policy is accepted.
- **Approval means:**
  - The router distinguishes data missingness, sparse history, interruption, and return intent.
  - No personal fitness-loss percentage is inferred from days without records.
  - Existing history-rich performance policies remain protected from silent scope expansion.
- **This does not authorize:**
  - A restart percentage, minimum history count, readiness test, retraining schedule, or automatic detraining estimate.
  - Medical rehabilitation or return-to-sport prescription.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `sparse_history_and_returning_routing`
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `population.sparse-history-not-detraining-proof`, `population.no-universal-returning-dose`

</details>

#### `masters-context` — Use age as context, never as automatic exclusion

- **Question:** Should masters or older runners remain in the matching distance and intent family, with optional age context and actual data modifying the route rather than a universal cutoff?
- **Proposed decision:** Yes. Masters status is not a separate base family and chronological age never blocks an otherwise supported adult route. Actual capability, history, training continuity, constraints, and observed or athlete-reported recovery carry the decision. No fixed age cutoff or recovery extension is accepted.
- **Approval means:**
  - Highly capable older runners are not excluded by age.
  - Missing optional age context disables only a future age-dependent modifier.
  - Recovery remains individual and feedback-aware rather than calendar-age based.
- **This does not authorize:**
  - A masters threshold, age score, recovery delay, reduced frequency, lower intensity, or modified progression value.
  - Medical screening or clearance.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `masters_context_modifier`
- **Evidence claims:** `eligibility.masters-age-change-not-automatic-exclusion`, `population.masters-context-not-age-exclusion`, `population.masters-recovery-not-fixed-delay`

</details>

#### `purpose-bound-profile` — Collect age, sex, or reproductive context only for an accepted purpose

- **Question:** Should physiological sex, gender identity, date of birth, menstrual context, and menopause remain non-mandatory unless a separately accepted dependent construct requires them?
- **Proposed decision:** Yes. Adult-scope confirmation remains required, but exact date of birth, age band, physiological sex, menstrual status, menopause, and gender identity are not global plan prerequisites. A future dependent model must disclose purpose, collect only the minimum necessary input, allow decline or unknown, preserve provenance, and disable only that adjustment when input is missing. Gender identity is not a training-dose variable, and unknown physiological sex never defaults to male.
- **Approval means:**
  - Profile collection follows evidence and purpose rather than convenience.
  - Provider-imported fields remain source-labelled candidates until confirmed.
  - Diagnosis-specific or reproductive constructs stay separate from general plan routing.
- **This does not authorize:**
  - A female, male, menstrual, menopausal, transgender, nonbinary, or gender-based plan family.
  - Hidden inference of sensitive traits, medical diagnosis, or mandatory disclosure.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `profile_inputs_and_missingness`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `population.sex-effects-are-construct-specific`, `population.no-general-sex-or-gender-plan-family`

</details>

#### `support-and-reassessment` — Keep strength and cross-training bounded and reuse the shared loop

- **Question:** Should strength and cycling remain optional support modules while every future population plan uses the same accepted adaptive reassessment semantics?
- **Proposed decision:** Yes. Strength may be an optional performance-support candidate without an injury-prevention guarantee. Cycling may be an optional load-modulation candidate without one-to-one equivalence to running. Exact dose and substitution remain policy-specific. Population plans depend on the shared adaptive contract and cannot define a second feedback or reassessment engine.
- **Approval means:**
  - Supporting modalities remain modular and evidence-bounded.
  - All distances and population routes share athlete-controlled feedback and reassessment semantics.
  - Reassessment remains source-labelled and non-causal.
- **This does not authorize:**
  - A strength frequency, cycling ratio, equivalent-impact formula, reassessment cadence, or automatic plan change.
  - A claim that one support module prevents injury for an individual.

<details><summary>Traceability: 2 contract groups, 2 evidence claims</summary>

- **Contract groups covered:** `supporting_modalities`, `shared_reassessment_dependency`
- **Evidence claims:** `population.strength-and-cross-training-bounded-support`, `eligibility.evidence-quality-no-personal-probability`

</details>

#### `adult-nonclinical-scope` — Preserve the adult nonclinical safety boundary

- **Question:** Should this population policy remain limited to adult nonclinical running goals and stop performance optimization on athlete-reported injury, acute illness, or red-flag symptoms?
- **Proposed decision:** Yes. Child and adolescent planning, injury rehabilitation, pregnancy-specific prescription, diagnosis, treatment, clearance, and return-to-sport remain unsupported. Athlete-reported injury, acute illness, or red-flag symptoms stop performance optimization without generating a medical plan. Historical intensity may use splits or samples, never activity-average power.
- **Approval means:**
  - Population expansion cannot weaken the existing safety boundary.
  - Unsupported medical or pediatric contexts return a typed stop or unavailable result.
  - Intensity evidence preserves the repository split-level invariant.
- **This does not authorize:**
  - Diagnosis, treatment, rehabilitation, pregnancy guidance, medical clearance, or a safety guarantee.
  - Activity-average-power intensity inference.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `safety_scope_boundary`
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `eligibility.evidence-quality-no-personal-probability`

</details>

### Decisions explicitly deferred

#### `exact-population-values` — Defer all exact population schedule and modifier values

- **Question:** Should exact completion, sparse-history, returning, masters, profile, strength, cross-training, and reassessment values remain unapproved?
- **Proposed decision:** Defer them. No reviewed evidence validates one cross-distance horizon, frequency, progression, run-walk ratio, long-run limit, intensity ceiling, anchor count, restart percentage, age cutoff, recovery delay, strength dose, cycling substitution, profile algorithm, or reassessment cadence.
- **Approval means:**
  - Every behavior-driving value remains literal not_accepted in the contract.
  - Future values require a versioned population and distance decision with validation.
- **This does not authorize:**
  - Inferring values from study protocols, common coaching practice, another distance, prose, or AI output.

<details><summary>Traceability: 1 contract group, 5 evidence claims</summary>

- **Contract groups covered:** `population_specific_numeric_prescription`
- **Evidence claims:** `population.no-universal-beginner-schedule`, `population.no-universal-returning-dose`, `population.masters-recovery-not-fixed-delay`, `population.strength-and-cross-training-bounded-support`, `population.no-general-sex-or-gender-plan-family`

</details>

#### `implementation-and-activation` — Defer implementation, pilot, rollout, and runtime activation

- **Question:** Should registry code, policy logic, APIs, clients, pilot criteria, and activation remain outside this science decision?
- **Proposed decision:** Defer them. This record defines only the inactive product boundary. Implementation needs exact route identifiers and deterministic fixtures, web and miniapp parity, privacy and deletion behavior, prospective evaluation, separate implementation review, and explicit runtime activation.
- **Approval means:**
  - Current capability discovery and plan generation remain unchanged.
  - Human science approval cannot be mistaken for shipped behavior.
- **This does not authorize:**
  - Code changes, user-facing claims, a pilot, a feature flag, rollout, or plan delivery.

<details><summary>Traceability: 1 contract group, 0 evidence claims</summary>

- **Contract groups covered:** `implementation_pilot_and_activation`
- **Evidence claims:** _None; product or lifecycle boundary only_

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve keeping all adult running goals selectable while routing plan generation by current intent, capability, history, and confirmed context. I approve first completion as a separate distance-specific policy family that does not require prior completion of that distance. I approve sparse history as a dynamic evidence state, return to consistency as an explicit or confirmed state, masters age as a non-excluding modifier, and physiological sex or reproductive context only as optional purpose-bound inputs for a separately accepted dependent construct. Gender identity is neither a plan-family selector nor a training-dose variable. I approve bounded strength and cycling support plus the shared adaptive reassessment dependency and the stated adult nonclinical safety scope. I agree that exact schedules, thresholds, capability identifiers, profile algorithms, implementation, pilot, rollout, and runtime activation remain deferred. This approval would not implement or activate a plan.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-adult-running-plan-population-routing-v1`
- Digest: `sha256:87298990e39e3c1e0b632d03661cee4ffe37b92121e4395f7374c8b24d8b841d`

> I approve keeping all adult running goals selectable while routing plan generation by current intent, capability, history, and confirmed context. I approve first completion as a separate distance-specific policy family that does not require prior completion of that distance. I approve sparse history as a dynamic evidence state, return to consistency as an explicit or confirmed state, masters age as a non-excluding modifier, and physiological sex or reproductive context only as optional purpose-bound inputs for a separately accepted dependent construct. Gender identity is neither a plan-family selector nor a training-dose variable. I approve bounded strength and cycling support plus the shared adaptive reassessment dependency and the stated adult nonclinical safety scope. I agree that exact schedules, thresholds, capability identifiers, profile algorithms, implementation, pilot, rollout, and runtime activation remain deferred. This approval would not implement or activate a plan.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:87298990e39e3c1e0b632d03661cee4ffe37b92121e4395f7374c8b24d8b841d","subject_id":"sdr-adult-running-plan-population-routing-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If accepted by digest-bound human reviewers, this inactive decision would keep every adult running goal selectable even when no accepted plan policy currently matches. First completion would be a distance-specific intent and capability family: prior completion of the goal distance would not be required to choose the goal, but an accepted history-rich performance policy could not be silently scaled down or reused. Sparse recorded history would remain a dynamic evidence state rather than proof of detraining. A runner with a usable recent anchor could enter only a separately accepted uncertainty-aware population route. No usable history would yield readiness-only, while sparse history without a usable recent anchor would yield insufficient_recent_history_anchor. Return to consistency would require athlete selection or confirmation, never an inference from missing records. Observed continuity could refute an interruption but could not establish a returning state. A return-to-consistency route would require its own accepted policy before any dose-shaped schedule. Masters or older age would modify an otherwise supported route through actual capability, history, recovery, constraints, and optional age context; it would not create automatic exclusion, a permanent identity, a universal age cutoff, or a fixed recovery delay. Physiological sex, menstrual or menopause context, and gender identity would not define a general plan family or mandatory profile. A future accepted dependent construct could request minimum-necessary, purpose-bound input, allow unknown or declined values, and never default unknown sex to male. Strength and cycling cross-training could appear only as bounded optional candidate modules, without an injury-prevention guarantee or one-to-one substitution rule. Every future population policy would use the accepted shared adaptive recommendation and reassessment contract rather than create a second feedback engine. Exact capability identifiers, horizons, weekly frequencies, progression, run-walk ratios, long-run values, intensity, restart dose, strength dose, cross-training substitution, age adjustment, recovery interval, reassessment cadence, implementation, pilot, rollout, and runtime activation remain explicitly not accepted. Existing accepted distance policies and current runtime behavior remain unchanged.

### Linked evidence

#### `eligibility.novice-recreational-different-evidence-family` — moderate

Novice runners have materially higher running-related injury incidence than recreational runners in the reviewed meta-analysis. This supports treating beginner runners as a separate evidence family rather than silently applying a policy reviewed for already-capable history-rich runners.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `videbaek-2015`
- **Limitations:** Injury definitions and runner classifications were heterogeneous.; The evidence does not define an exact beginner threshold or a personal injury probability.; Higher incidence does not validate a specific beginner plan.; Routing goal-distance-novel runners with beginners is a conservative Praxys guardrail that needs separate validation.

#### `eligibility.recent-history-anchor-without-universal-threshold` — moderate

Abrupt weekly or single-session distance increases are associated with higher running-related injury rates, while the reviewed evidence is heterogeneous and does not establish one universal safe increase. Recent consistency and recent longest-session history are therefore relevant eligibility dimensions, not validated prescription cutoffs.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `damsted-2019`, `frandsen-2025`, `correia-2024`
- **Limitations:** These studies do not establish causation or an individual safety threshold.; The weekly association was significant at 21 days but not later follow-up points.; The single-session cohort used self-reported injury outcomes and did not validate an automatic plan rule.; The umbrella review found only critically low or low-quality systematic reviews.

#### `eligibility.goal-relevant-current-capability-task-specific` — moderate

Current performance evidence is most interpretable when the task and protocol match the intended outcome. Fixed-distance time trials are generally more reliable than time-to-exhaustion tests, supporting an explicit goal-relevant current-capability axis rather than automatic substitution from a different test protocol.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `currell-2008`, `laursen-2007`
- **Limitations:** The sources do not make solo time trials and races automatically interchangeable.; They do not validate a universal baseline freshness cutoff.; They do not define Praxys capability-state labels or a cross-distance conversion.

#### `eligibility.masters-age-change-not-automatic-exclusion` — moderate

Endurance performance and training capacity change with age, while masters athletes and older adults can retain high capability and benefit from continued exercise. The reviewed evidence supports neither automatic exclusion by age nor a universal age cutoff or recovery rule.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `tanaka-2008`, `chodzko-zajko-2009`, `burtscher-2022`
- **Limitations:** Masters athletes are selected, trained populations and are not representative of every older runner.; The evidence does not define an age cutoff, recovery rule, or safe automatic plan.; Treating age as an uncertainty or recovery modifier is a Praxys guardrail that requires prospective validation.; Women and older women are underrepresented.

#### `eligibility.evidence-quality-no-personal-probability` — moderate

Running-injury evidence is heterogeneous and often low quality, while individual exercise-response classification is methodologically fragile unless measurement error and within-person variability are addressed. These limitations support explicit evidence-directness states and reject personal success probabilities or deterministic responder labels.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `correia-2024`, `bonafiglia-2021`
- **Limitations:** The exercise-response review was not a running-plan prediction study.; Low evidence quality does not make personalization impossible.; No source provides a calibrated plan-generation success probability.

#### `population.beginner-evidence-family-not-permanent-identity` — moderate

Novice and recreational runners are studied as distinct evidence populations, but their injury estimates depend strongly on exposure denominator, follow-up, and inconsistent cohort definitions. This supports separate evidence handling for first-completion planning, not a permanent beginner identity or an individual injury probability.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `videbaek-2015`, `fredette-2022`
- **Limitations:** The two reviews use different denominators and should not be read as a stable ranking of personal risk.; Study labels do not define when one person stops being a beginner.; The evidence does not validate a first-completion plan, duration, or schedule.; First-at-goal-distance and globally new-to-running are not established as the same physiological population.

#### `population.no-universal-beginner-schedule` — moderate

Reviewed running-program evidence does not establish one universal beginner duration, progression percentage, frequency, run-walk ratio, intensity pattern, or preconditioning schedule. A 10 percent progression program did not reduce injury, intensity-focused and volume-focused progression did not differ clearly in injury risk, and one named beginner program had substantial injury and non-completion.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `fredette-2022`, `buist-2008`, `ramskov-2018`, `relph-2023`
- **Limitations:** Null injury differences do not prove that all schedules are equivalent.; Run Clever lost many participants before the randomized comparison period and studied recreational rather than first-time runners.; Most Couch-to-5k participants were active and many had prior running experience.; Injury prevention is not the only outcome relevant to completion planning.; No reviewed trial validates one schedule across 5 km, 10 km, half-marathon, and marathon completion goals.

#### `population.sparse-history-not-detraining-proof` — moderate

Detraining is defined and studied as a known reduction or cessation of training. Sparse, missing, or provider-limited Praxys records do not by themselves establish that training stopped, how much capacity changed, or whether the runner is returning.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `zheng-2022`, `barbieri-2023`
- **Limitations:** The product conclusion about record missingness is an epistemic guardrail, not a tested intervention.; The reviews are not studies of consumer data completeness or provider outages.; Self-reported interruption may still require clarification about partial versus complete training.

#### `population.no-universal-returning-dose` — moderate

Training cessation can reduce cardiorespiratory fitness, with larger average effects after longer cessation, but effects vary by prior training, outcome, duration, and partial versus complete cessation. The reviewed evidence does not validate a universal restart percentage, weekly progression, preserved-capacity fraction, or return-to-consistency schedule.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `zheng-2022`, `barbieri-2023`
- **Limitations:** VO2max does not represent every dimension of running capacity or tissue tolerance.; Most evidence does not test recreational return-to-running prescriptions.; Partial reduction and complete cessation cannot be treated as equivalent.; The evidence cannot convert days without records into a personal loss percentage.

#### `population.masters-context-not-age-exclusion` — moderate

Endurance performance and VO2max generally decline with age, while masters athletes retain high capability and changes in training volume explain substantial variation in observed decline. Chronological age is therefore relevant context but does not establish a universal exclusion, a fixed masters cutoff, or a separate base plan family.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `tanaka-2008`, `burtscher-2022`, `vangsgaard-2026`
- **Limitations:** Reviews include highly trained athletes and cannot define a recreational automatic-plan adjustment.; Observational associations with training volume do not prove an optimal dose.; Published masters definitions often use age 35 or 40 for study or competition administration, not a biological threshold.; Women masters evidence is sparse and mostly cross-sectional.

#### `population.masters-recovery-not-fixed-delay` — low

Evidence on age and exercise recovery is limited and protocol-dependent. Trained older adults did not recover more slowly than younger trained adults in one downhill-running study, while a masters interval study showed that most runners recovered by 24 hours but a minority retained fatigue. This supports individual recovery context, not a universal age-based 24-, 48-, or 72-hour delay.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `fell-williams-2008`, `hayashi-2019`, `riazati-2022`
- **Limitations:** Samples were small and protocols were acute, laboratory-based, and sometimes deliberately muscle damaging.; Hayashi et al. combined men and women but did not establish sex-specific recovery rules.; Riazati et al. studied 20 runners and did not test a plan-level recovery intervention.; These studies do not define a weekly quality-session count or schedule.

#### `population.strength-and-cross-training-bounded-support` — moderate

Strength training can improve running performance in some trained runner protocols, but certainty ranges from very low to moderate and one self-directed first-marathon strength program did not reduce overuse injury or improve finish time. Running-cycling cross-training shows no clear short-term between-group performance difference, but the limited heterogeneous evidence does not establish interchangeability or a one-to-one substitution ratio.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `llanos-lagos-2024`, `toresdahl-2020`, `menges-2026`
- **Limitations:** Strength meta-analysis participants were mainly 17 to 40 years old and did not establish a masters-specific dose.; The first-marathon strength trial tested one low-burden self-directed program, not all strength training.; Cross-training evidence included only seven studies with old protocols and wide confidence intervals.; No reviewed source validates a universal strength frequency, cross-training share, or impact-load equivalence.

#### `population.sex-effects-are-construct-specific` — moderate

Overall running-injury rates were similar between female and male runners in the reviewed meta-analysis, while bone-stress and Achilles diagnoses differed. Average menstrual-cycle phase effects on exercise performance were trivial, heterogeneous, and low certainty. Physiological sex and reproductive context may therefore matter for a specifically accepted dependent construct, but do not supply one general running-plan rule.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `hollander-2021`, `mcnulty-2020`
- **Limitations:** Overall injury similarity does not erase diagnosis-specific or individual context.; Injury and menstrual-cycle studies do not test running-plan families.; Menstrual-cycle evidence was low quality and phase verification was inconsistent.; Diagnosis, rehabilitation, pregnancy, and medical treatment remain outside this review.

#### `population.no-general-sex-or-gender-plan-family` — low

The included evidence and dedicated searches do not validate a general female, male, nonbinary, transgender, menstrual, menopausal, or gender-identity-based running-plan family. Women masters evidence remains sparse and largely observational, and menopause-specific prescription remains unresolved. The identified transgender-women and nonbinary running studies describe performance under hormone-therapy or race-category contexts; they do not compare plan families, prescribe training dose, or establish gender identity as a causal dose modifier. Any future field or adjustment must be purpose-bound to a separately accepted construct and allow unknown or declined input.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `daly-2024`, `vangsgaard-2026`, `hollander-2021`, `mcnulty-2020`, `harper-2025`, `armstrong-2023`
- **Limitations:** Absence of validating evidence is not evidence that no subgroup-specific model could ever be useful.; The transgender-women study was small and heterogeneous, with partly retrospective self-reported training exposure and no comparative prescription.; The nonbinary race analysis was observational, represented only athletes choosing the nonbinary category, and probabilistically inferred natal sex when prior records were unavailable.; A descriptive performance association does not establish a causal training-response construct or justify collecting gender identity for dose selection.; Physiological sex, gender identity, menstrual status, menopause, symptoms, and energy availability are distinct constructs.; This claim does not define which future construct should be collected or how it should be modeled.

### Reviewed parameters

#### `population_routing_authority` — guardrail

- **Applies to:** adult running-goal capture and future plan capability discovery
- **Evidence claims:** `eligibility.novice-recreational-different-evidence-family`, `eligibility.goal-relevant-current-capability-task-specific`, `population.beginner-evidence-family-not-permanent-identity`
- **Rationale:** Goal choice, population applicability, generation, adoption, delivery, and runtime activation are separate authorities.
- **Exact value:**

```json
{
  "accepted_population_and_distance_policy_required": true,
  "active_behavior": false,
  "current_accepted_distance_policies_unchanged": true,
  "current_runtime_capability_registry_unchanged": true,
  "goal_capture_independent_from_plan_availability": true,
  "shared_adaptive_dependency": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
  "shared_router_dependency": "sdr-plan-generation-eligibility-safety-v1",
  "static_population_identity_allowed": false,
  "suggestion_only": true
}
```

#### `first_completion_policy_family` — guardrail

- **Applies to:** first-goal-distance completion and performance-intent clarification
- **Evidence claims:** `eligibility.novice-recreational-different-evidence-family`, `eligibility.goal-relevant-current-capability-task-specific`, `population.no-universal-beginner-schedule`
- **Rationale:** Completion is a valid goal before current distance capability exists, while a performance policy cannot be broadened by reducing its dose.
- **Exact value:**

```json
{
  "automatic_intent_coercion": false,
  "distance_specific_policy_required": true,
  "first_at_goal_distance_is_permanent_beginner_identity": false,
  "goal_intent": "completion",
  "history_rich_performance_policy_reuse": false,
  "no_matching_policy_result": "completion_policy_unavailable",
  "performance_without_current_direct_capability_result": "performance_policy_unavailable_or_clarification_required",
  "prior_goal_distance_completion_required": false,
  "route_state": "first_completion_policy_required"
}
```

#### `sparse_history_and_returning_routing` — guardrail

- **Applies to:** history sufficiency, interruption clarification, and return-to-consistency routing
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `population.sparse-history-not-detraining-proof`, `population.no-universal-returning-dose`
- **Rationale:** History completeness, interruption, current capability, and goal intent are distinct states and must not be collapsed into one inferred label.
- **Exact value:**

```json
{
  "existing_history_rich_policy_reuse_without_alignment": false,
  "history_states": {
    "history_rich": "continue_to_matching_distance_and_intent_policy",
    "no_usable_history": "readiness_only",
    "sparse_with_usable_recent_anchor": "uncertainty_aware_population_policy_required",
    "sparse_without_usable_recent_anchor": "insufficient_recent_history_anchor",
    "unknown": "clarification_required"
  },
  "observed_continuity_can_establish_returning_state": false,
  "observed_continuity_can_refute_interruption": true,
  "observed_record_missingness_establishes_interruption": false,
  "personal_detraining_loss_estimate_allowed": false,
  "returning_state_requires_athlete_confirmation": true,
  "returning_to_consistency_intent_auto_inferred": false,
  "returning_to_consistency_intent_user_selectable": true,
  "returning_to_consistency_route": "separate_accepted_consistency_policy_required",
  "sparse_history_establishes_detraining": false
}
```

#### `masters_context_modifier` — guardrail

- **Applies to:** every otherwise-supported adult distance and intent route
- **Evidence claims:** `eligibility.masters-age-change-not-automatic-exclusion`, `population.masters-context-not-age-exclusion`, `population.masters-recovery-not-fixed-delay`
- **Rationale:** Age changes population physiology, but capability, training continuity, and recovery vary enough that age alone cannot select or reject a plan.
- **Exact value:**

```json
{
  "automatic_age_exclusion": false,
  "fixed_age_based_recovery_extension": "none_defined",
  "missing_optional_age_context_result": "base_route_without_age_dependent_modifier",
  "route_inputs": [
    "current_goal_relevant_capability",
    "recent_history_and_continuity",
    "current_load_relative_to_self",
    "observed_or_athlete_reported_recovery",
    "athlete_stated_constraints",
    "optional_purpose_bound_age_context"
  ],
  "separate_base_policy_family": false,
  "study_or_competition_masters_label_is_person_identity": false,
  "universal_biological_age_cutoff": "none_defined"
}
```

#### `profile_inputs_and_missingness` — guardrail

- **Applies to:** profile, point-of-use clarification, and future dependent modifiers
- **Evidence claims:** `population.sex-effects-are-construct-specific`, `population.no-general-sex-or-gender-plan-family`, `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Physiological sex, reproductive context, and gender are distinct constructs. Collection follows an accepted purpose rather than becoming a blanket prerequisite.
- **Exact value:**

```json
{
  "adult_scope_confirmation_required": true,
  "age_band_globally_required": false,
  "exact_date_of_birth_globally_required": false,
  "future_field_requirements": [
    "separately_accepted_dependent_construct",
    "disclosed_product_purpose",
    "minimum_necessary_collection",
    "provenance",
    "correction",
    "deletion"
  ],
  "gender_identity_is_training_dose_input": false,
  "menstrual_or_menopause_context_globally_required": false,
  "missing_optional_field_disables_only_dependent_adjustment": true,
  "physiological_sex_globally_required": false,
  "provider_imported_profile_is_confirmed_truth": false,
  "provider_profile_requires_source_label_and_user_confirmation": true,
  "unknown_physiological_sex_default": "unknown",
  "user_may_decline_optional_fields": true
}
```

#### `supporting_modalities` — guardrail

- **Applies to:** future first-completion, sparse-history, returning, and masters modules
- **Evidence claims:** `population.strength-and-cross-training-bounded-support`
- **Rationale:** Supporting modalities may be useful, while reviewed evidence does not establish universal dose, equivalence, or injury prevention.
- **Exact value:**

```json
{
  "cycling_cross_training": {
    "one_to_one_running_substitution": false,
    "sport_specific_capability_evidence_replacement": false,
    "status": "optional_candidate_load_modulation_module",
    "universal_population_dose": false
  },
  "distance_and_population_policy_must_bound_any_module": true,
  "strength": {
    "individual_injury_prevention_guarantee": false,
    "possible_performance_support": true,
    "status": "optional_candidate_support_module",
    "universal_population_dose": false
  }
}
```

#### `shared_reassessment_dependency` — guardrail

- **Applies to:** every future managed population plan
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Population routing changes applicability, not the shared semantics for recommendation, athlete review, observation, and reassessment.
- **Exact value:**

```json
{
  "population_policy_may_define_second_feedback_engine": false,
  "reassessment_proves_individual_causality": false,
  "reassessment_requires_source_labelled_evidence": true,
  "shared_policy": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
  "shared_policy_runtime_state": "inactive",
  "universal_reassessment_cadence": "none_defined"
}
```

#### `safety_scope_boundary` — guardrail

- **Applies to:** population intake, capability routing, and historical intensity evidence
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Population coverage cannot turn a nonclinical performance policy into medical or pediatric guidance or weaken the split-level power invariant.
- **Exact value:**

```json
{
  "activity_average_power_allowed_for_intensity": false,
  "adult_scope_only": true,
  "athlete_reported_injury_acute_illness_or_red_flag_result": "stop_performance_optimization",
  "child_or_adolescent_route": "unsupported",
  "diagnosis_or_treatment": "unsupported",
  "injury_rehabilitation": "unsupported",
  "intensity_evidence_allowed": [
    "activity_splits",
    "activity_samples"
  ],
  "medical_clearance": "unsupported",
  "pregnancy_specific_prescription": "unsupported",
  "return_to_sport": "unsupported"
}
```

#### `population_specific_numeric_prescription` — guardrail

- **Applies to:** all population-specific plan generation and reassessment values
- **Evidence claims:** `population.no-universal-beginner-schedule`, `population.no-universal-returning-dose`, `population.masters-recovery-not-fixed-delay`, `population.strength-and-cross-training-bounded-support`, `population.no-general-sex-or-gender-plan-family`
- **Rationale:** The review supports routing boundaries and uncertainty, not one set of behavior-driving values across populations and distances.
- **Exact value:**

```json
{
  "cycling_substitution_ratio": "not_accepted",
  "first_completion_horizon_days": "not_accepted",
  "first_completion_intensity_distribution": "not_accepted",
  "first_completion_long_run_limit": "not_accepted",
  "first_completion_progression": "not_accepted",
  "first_completion_run_walk_ratio": "not_accepted",
  "first_completion_weekly_running_frequency": "not_accepted",
  "masters_age_cutoff": "not_accepted",
  "masters_frequency_or_intensity_adjustment": "not_accepted",
  "masters_recovery_extension": "not_accepted",
  "physiological_sex_or_reproductive_adjustment": "not_accepted",
  "reassessment_cadence_and_triggers": "not_accepted",
  "returning_progression": "not_accepted",
  "returning_restart_percentage": "not_accepted",
  "runtime_capability_identifiers": "not_accepted",
  "sparse_history_latest_run_days": "not_accepted",
  "sparse_history_minimum_anchor_sessions": "not_accepted",
  "sparse_history_minimum_anchor_weeks": "not_accepted",
  "strength_frequency_and_load": "not_accepted"
}
```

#### `implementation_pilot_and_activation` — guardrail

- **Applies to:** implementation, pilot, rollout, and runtime
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Science and product-boundary review are separate from implementation, prospective evaluation, rollout, delivery authority, and activation.
- **Exact value:**

```json
{
  "accepted_distance_policy_alignment": "not_accepted",
  "active_behavior": false,
  "api_contracts": "not_accepted",
  "capability_registry_mapping": "not_accepted",
  "comparator": "not_accepted",
  "implementation_approval": "not_accepted",
  "persistence_schema": "not_accepted",
  "pilot_population": "not_accepted",
  "plugin_and_mcp_contracts": "not_accepted",
  "policy_router_logic": "not_accepted",
  "primary_and_guardrail_metrics": "not_accepted",
  "profile_collection_and_privacy_operations": "not_accepted",
  "rollout": "not_accepted",
  "runtime_activation": "not_accepted",
  "sample_size_and_duration": "not_accepted",
  "science_note_and_localization": "not_accepted",
  "success_failure_and_rollback_thresholds": "not_accepted",
  "web_and_miniapp_clients": "not_accepted"
}
```

### Rejected alternatives

#### Require a user to have already completed the goal distance before allowing the goal

Goal intent is durable user choice. Current capability determines which policy may generate a plan, not whether the goal can be recorded.

#### Scale a history-rich performance policy down for first completion

Novice and first-completion populations have different applicability and injury evidence, while no reviewed source validates a universal scaled version of an accepted performance policy.

#### Treat missing or sparse Praxys records as proven detraining

Detraining studies require known training reduction or cessation. Provider missingness and unrecorded training remain unknown.

#### Use one restart percentage after any interruption

Detraining differs by prior training, outcome, duration, and whether training was reduced or stopped; no recreational restart formula was validated.

#### Create a separate masters plan family or block users at age 40

Competition and study definitions are administrative, not biological cutoffs. Highly capable older athletes and large training-related variation make automatic exclusion indefensible.

#### Add a fixed extra recovery day for every older runner

Direct trained-runner studies show protocol-specific and inter-individual recovery rather than a universal age delay.

#### Create female and male plan families and default unknown to male

Overall injury risk is similar, specific constructs differ, and no general sex-based plan family is validated. Unknown must remain unknown.

#### Require date of birth, physiological sex, menstrual status, or menopause before any plan

No reviewed source establishes that every field improves every plan. Collection must be purpose-bound and minimum necessary.

#### Treat strength as injury prevention or cycling as equivalent running

Evidence supports bounded candidate use but not an individual guarantee or universal substitution ratio.

#### Let each population policy define its own feedback engine

Duplicate semantics would drift across distances and clients and conflict with the accepted shared adaptive policy.

#### Implement the closest reasonable values now and validate later

Evidence and product-boundary approval do not establish exact values, implementation correctness, pilot safety, or runtime authority.

### Applicability

- Adult recreational running goals and future managed-plan capability discovery
- First-completion intent at any distance with a separately accepted distance policy
- Performance intent with current goal-relevant capability and population-appropriate history policy
- Sparse-history and nonclinical return-to-consistency routes after separate policy acceptance
- Masters and older runners as modifiers of otherwise-supported routes
- Web, WeChat miniapp, plugin, and MCP surfaces using the same route semantics

### User-facing claim limits

- Do not require prior goal-distance completion before allowing a completion goal.
- Do not describe first completion, sparse history, returning, or masters as permanent identities.
- Do not imply that missing records prove detraining or reveal a personal capacity-loss percentage.
- Do not promise that age, sex, gender, strength, cycling, or one program determines safety or success.
- Do not present a masters cutoff, recovery delay, restart percentage, or reassessment cadence as published.
- Do not default unknown physiological sex to male or imply that gender identity determines training dose.
- Explain when an optional profile field supports a specific accepted construct and what happens when it is unknown.
- Do not imply that strength prevents injury or that cycling is equivalent to running.
- Preserve the goal and provide an honest unavailable, clarification, readiness-only, or safety result when no policy matches.

### Safety implications

- Child and adolescent plans remain outside this adult policy.
- Injury rehabilitation, pregnancy-specific prescription, diagnosis, treatment, clearance, and return-to-sport remain unsupported.
- Athlete-reported injury, acute illness, or red-flag symptoms stop performance optimization without a success-shaped plan.
- No automatic catch-up, fixed progression, restart percentage, or age-based recovery rule.
- Historical intensity analysis uses activity splits or samples, never activity-average power.

### Privacy implications

- Exact date of birth, age band, physiological sex, menstrual status, menopause, and gender identity are not global plan prerequisites.
- Optional fields require an accepted purpose, minimum-necessary collection, visible provenance, correction, and deletion.
- Provider-imported profile values remain source-labelled candidates until user confirmation.
- Unknown and declined values remain distinct and never become male, average, or inferred.
- Do not infer reproductive, medical, or gender context from training behavior.

### Validation plan

- A digest-bound human evidence reviewer must accept, revise, or reject the new Evidence Review before this SDR can be accepted.
- A digest-bound human decision approver must review the eight-item decision sheet and exact inactive contract.
- Define exact future route identifiers and deterministic fixtures for first completion, sparse history with and without an anchor, explicit return-to-consistency, masters context, unknown profile fields, and unsupported safety scope.
- Verify goal capture remains available when no plan policy matches and no route silently changes completion or performance intent.
- Verify missing provider records never create an interruption, detraining percentage, sex default, masters exclusion, or medical inference.
- Verify every accepted population and distance policy reuses the shared adaptive recommendation and reassessment contract.
- Add registry, policy, API, web, miniapp, plugin, MCP, privacy, deletion, localization, and accessibility tests before implementation review.
- Predefine a prospective opt-in pilot with completion, adherence, usefulness, burden, abandonment, injury, adverse-event, and false-stop guardrails.
- Audit outcomes and route availability by age, sex where purpose-bound, history depth, return state, distance, intent, missingness, provider, language, and client.
- Require separate implementation review before runtime_state changes from inactive.

### Falsification conditions

- A user cannot record a completion goal until already capable of the distance.
- A first-completion, sparse-history, or returning route silently reuses a history-rich performance schedule.
- Missing records are interpreted as training cessation or converted to a personal loss percentage.
- Chronological age alone excludes a runner or adds a fixed recovery delay.
- Unknown physiological sex defaults to male or gender identity changes training dose.
- Optional profile fields block a supported base route without an accepted dependent construct.
- Strength is presented as injury prevention or cycling as one-to-one running replacement.
- A population policy creates a second feedback or reassessment engine.
- Any literal not_accepted value becomes runtime behavior through prose, convention, another distance, or AI inference.
- Web, miniapp, plugin, or MCP surfaces produce different route semantics for the same inputs.
- A future pilot shows unacceptable abandonment, burden, adverse events, subgroup disparity, or false-stop rates against predefined criteria.

### Decision notes

- This artifact-mode Decision proposal addresses issue #689 and remains draft and inactive.
- The new rigorous Evidence Review compares first-completion, sparse-history, returning-to-consistency, masters, strength, cross-training, physiological sex, reproductive context, and gender evidence through 2026-08-16.
- The proposed architecture is hybrid: first completion is a distance-specific policy family; sparse history is a dynamic evidence state; return to consistency is an explicit intent or confirmed state; masters is a non-excluding modifier; and sex or gender is not a general policy family.
- This decision does not rewrite the accepted 5 km, 10 km, half-marathon, marathon, baseline, eligibility, or adaptive records. Future implementation must align them explicitly before any new route can activate.
- All unresolved behavior-driving values are literal not_accepted. No implementation may infer a value from a study protocol, another distance, common coaching practice, prose, or AI output.
- Impact map: rigorous Evidence Review and complete PubMed search manifest -> generated evidence packet -> draft population SDR -> generated decision packet and inactive machine contract -> human evidence and decision review -> future distance and population policy decisions -> deterministic router and capability mapping -> persistence and API -> web, miniapp, plugin, and MCP parity -> ScienceNote and localization -> prospective opt-in pilot -> separate implementation review -> separately approved activation.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "Shared plan-generation eligibility and population route contract",
    "Future distance-specific first-completion policies",
    "Future sparse-history and return-to-consistency policies",
    "Future masters and purpose-bound profile modifiers",
    "Shared adaptive recommendation and reassessment dependency graph"
  ],
  "contract_digest": "sha256:c2167596d846842bc73f65fccda75d232a1568f7f135ec0451bb32301410c04e",
  "decision_id": "sdr-adult-running-plan-population-routing-v1",
  "decision_status": "draft",
  "decision_version": 1,
  "evidence_claim_ids": [
    "eligibility.novice-recreational-different-evidence-family",
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "eligibility.evidence-quality-no-personal-probability",
    "population.beginner-evidence-family-not-permanent-identity",
    "population.no-universal-beginner-schedule",
    "population.sparse-history-not-detraining-proof",
    "population.no-universal-returning-dose",
    "population.masters-context-not-age-exclusion",
    "population.masters-recovery-not-fixed-delay",
    "population.strength-and-cross-training-bounded-support",
    "population.sex-effects-are-construct-specific",
    "population.no-general-sex-or-gender-plan-family"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-adult-running-plan-population-routing-v1"
  ],
  "linked_evidence_digests": {
    "evidence-adult-running-plan-population-routing-v1": "sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8",
    "evidence-plan-generation-eligibility-safety-v1": "sha256:e884907d33783edc6cdb16fd5504f7f10b6d68f968bfe7cf87e3f024b5bda773"
  },
  "model_version": "adult-running-plan-population-routing-v1",
  "parameters": {
    "first_completion_policy_family": {
      "applies_to": "first-goal-distance completion and performance-intent clarification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.novice-recreational-different-evidence-family",
        "eligibility.goal-relevant-current-capability-task-specific",
        "population.no-universal-beginner-schedule"
      ],
      "value": {
        "automatic_intent_coercion": false,
        "distance_specific_policy_required": true,
        "first_at_goal_distance_is_permanent_beginner_identity": false,
        "goal_intent": "completion",
        "history_rich_performance_policy_reuse": false,
        "no_matching_policy_result": "completion_policy_unavailable",
        "performance_without_current_direct_capability_result": "performance_policy_unavailable_or_clarification_required",
        "prior_goal_distance_completion_required": false,
        "route_state": "first_completion_policy_required"
      }
    },
    "implementation_pilot_and_activation": {
      "applies_to": "implementation, pilot, rollout, and runtime",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "accepted_distance_policy_alignment": "not_accepted",
        "active_behavior": false,
        "api_contracts": "not_accepted",
        "capability_registry_mapping": "not_accepted",
        "comparator": "not_accepted",
        "implementation_approval": "not_accepted",
        "persistence_schema": "not_accepted",
        "pilot_population": "not_accepted",
        "plugin_and_mcp_contracts": "not_accepted",
        "policy_router_logic": "not_accepted",
        "primary_and_guardrail_metrics": "not_accepted",
        "profile_collection_and_privacy_operations": "not_accepted",
        "rollout": "not_accepted",
        "runtime_activation": "not_accepted",
        "sample_size_and_duration": "not_accepted",
        "science_note_and_localization": "not_accepted",
        "success_failure_and_rollback_thresholds": "not_accepted",
        "web_and_miniapp_clients": "not_accepted"
      }
    },
    "masters_context_modifier": {
      "applies_to": "every otherwise-supported adult distance and intent route",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "population.masters-context-not-age-exclusion",
        "population.masters-recovery-not-fixed-delay"
      ],
      "value": {
        "automatic_age_exclusion": false,
        "fixed_age_based_recovery_extension": "none_defined",
        "missing_optional_age_context_result": "base_route_without_age_dependent_modifier",
        "route_inputs": [
          "current_goal_relevant_capability",
          "recent_history_and_continuity",
          "current_load_relative_to_self",
          "observed_or_athlete_reported_recovery",
          "athlete_stated_constraints",
          "optional_purpose_bound_age_context"
        ],
        "separate_base_policy_family": false,
        "study_or_competition_masters_label_is_person_identity": false,
        "universal_biological_age_cutoff": "none_defined"
      }
    },
    "population_routing_authority": {
      "applies_to": "adult running-goal capture and future plan capability discovery",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.novice-recreational-different-evidence-family",
        "eligibility.goal-relevant-current-capability-task-specific",
        "population.beginner-evidence-family-not-permanent-identity"
      ],
      "value": {
        "accepted_population_and_distance_policy_required": true,
        "active_behavior": false,
        "current_accepted_distance_policies_unchanged": true,
        "current_runtime_capability_registry_unchanged": true,
        "goal_capture_independent_from_plan_availability": true,
        "shared_adaptive_dependency": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
        "shared_router_dependency": "sdr-plan-generation-eligibility-safety-v1",
        "static_population_identity_allowed": false,
        "suggestion_only": true
      }
    },
    "population_specific_numeric_prescription": {
      "applies_to": "all population-specific plan generation and reassessment values",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.no-universal-beginner-schedule",
        "population.no-universal-returning-dose",
        "population.masters-recovery-not-fixed-delay",
        "population.strength-and-cross-training-bounded-support",
        "population.no-general-sex-or-gender-plan-family"
      ],
      "value": {
        "cycling_substitution_ratio": "not_accepted",
        "first_completion_horizon_days": "not_accepted",
        "first_completion_intensity_distribution": "not_accepted",
        "first_completion_long_run_limit": "not_accepted",
        "first_completion_progression": "not_accepted",
        "first_completion_run_walk_ratio": "not_accepted",
        "first_completion_weekly_running_frequency": "not_accepted",
        "masters_age_cutoff": "not_accepted",
        "masters_frequency_or_intensity_adjustment": "not_accepted",
        "masters_recovery_extension": "not_accepted",
        "physiological_sex_or_reproductive_adjustment": "not_accepted",
        "reassessment_cadence_and_triggers": "not_accepted",
        "returning_progression": "not_accepted",
        "returning_restart_percentage": "not_accepted",
        "runtime_capability_identifiers": "not_accepted",
        "sparse_history_latest_run_days": "not_accepted",
        "sparse_history_minimum_anchor_sessions": "not_accepted",
        "sparse_history_minimum_anchor_weeks": "not_accepted",
        "strength_frequency_and_load": "not_accepted"
      }
    },
    "profile_inputs_and_missingness": {
      "applies_to": "profile, point-of-use clarification, and future dependent modifiers",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.sex-effects-are-construct-specific",
        "population.no-general-sex-or-gender-plan-family",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "adult_scope_confirmation_required": true,
        "age_band_globally_required": false,
        "exact_date_of_birth_globally_required": false,
        "future_field_requirements": [
          "separately_accepted_dependent_construct",
          "disclosed_product_purpose",
          "minimum_necessary_collection",
          "provenance",
          "correction",
          "deletion"
        ],
        "gender_identity_is_training_dose_input": false,
        "menstrual_or_menopause_context_globally_required": false,
        "missing_optional_field_disables_only_dependent_adjustment": true,
        "physiological_sex_globally_required": false,
        "provider_imported_profile_is_confirmed_truth": false,
        "provider_profile_requires_source_label_and_user_confirmation": true,
        "unknown_physiological_sex_default": "unknown",
        "user_may_decline_optional_fields": true
      }
    },
    "safety_scope_boundary": {
      "applies_to": "population intake, capability routing, and historical intensity evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "activity_average_power_allowed_for_intensity": false,
        "adult_scope_only": true,
        "athlete_reported_injury_acute_illness_or_red_flag_result": "stop_performance_optimization",
        "child_or_adolescent_route": "unsupported",
        "diagnosis_or_treatment": "unsupported",
        "injury_rehabilitation": "unsupported",
        "intensity_evidence_allowed": [
          "activity_splits",
          "activity_samples"
        ],
        "medical_clearance": "unsupported",
        "pregnancy_specific_prescription": "unsupported",
        "return_to_sport": "unsupported"
      }
    },
    "shared_reassessment_dependency": {
      "applies_to": "every future managed population plan",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "population_policy_may_define_second_feedback_engine": false,
        "reassessment_proves_individual_causality": false,
        "reassessment_requires_source_labelled_evidence": true,
        "shared_policy": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
        "shared_policy_runtime_state": "inactive",
        "universal_reassessment_cadence": "none_defined"
      }
    },
    "sparse_history_and_returning_routing": {
      "applies_to": "history sufficiency, interruption clarification, and return-to-consistency routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "population.sparse-history-not-detraining-proof",
        "population.no-universal-returning-dose"
      ],
      "value": {
        "existing_history_rich_policy_reuse_without_alignment": false,
        "history_states": {
          "history_rich": "continue_to_matching_distance_and_intent_policy",
          "no_usable_history": "readiness_only",
          "sparse_with_usable_recent_anchor": "uncertainty_aware_population_policy_required",
          "sparse_without_usable_recent_anchor": "insufficient_recent_history_anchor",
          "unknown": "clarification_required"
        },
        "observed_continuity_can_establish_returning_state": false,
        "observed_continuity_can_refute_interruption": true,
        "observed_record_missingness_establishes_interruption": false,
        "personal_detraining_loss_estimate_allowed": false,
        "returning_state_requires_athlete_confirmation": true,
        "returning_to_consistency_intent_auto_inferred": false,
        "returning_to_consistency_intent_user_selectable": true,
        "returning_to_consistency_route": "separate_accepted_consistency_policy_required",
        "sparse_history_establishes_detraining": false
      }
    },
    "supporting_modalities": {
      "applies_to": "future first-completion, sparse-history, returning, and masters modules",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.strength-and-cross-training-bounded-support"
      ],
      "value": {
        "cycling_cross_training": {
          "one_to_one_running_substitution": false,
          "sport_specific_capability_evidence_replacement": false,
          "status": "optional_candidate_load_modulation_module",
          "universal_population_dose": false
        },
        "distance_and_population_policy_must_bound_any_module": true,
        "strength": {
          "individual_injury_prevention_guarantee": false,
          "possible_performance_support": true,
          "status": "optional_candidate_support_module",
          "universal_population_dose": false
        }
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:87298990e39e3c1e0b632d03661cee4ffe37b92121e4395f7374c8b24d8b841d"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If accepted by digest-bound human reviewers, this inactive decision would keep every adult running goal selectable even when no accepted plan policy currently matches. First completion would be a distance-specific intent and capability family: prior completion of the goal distance would not be required to choose the goal, but an accepted history-rich performance policy could not be silently scaled down or reused. Sparse recorded history would remain a dynamic evidence state rather than proof of detraining. A runner with a usable recent anchor could enter only a separately accepted uncertainty-aware population route. No usable history would yield readiness-only, while sparse history without a usable recent anchor would yield insufficient_recent_history_anchor. Return to consistency would require athlete selection or confirmation, never an inference from missing records. Observed continuity could refute an interruption but could not establish a returning state. A return-to-consistency route would require its own accepted policy before any dose-shaped schedule. Masters or older age would modify an otherwise supported route through actual capability, history, recovery, constraints, and optional age context; it would not create automatic exclusion, a permanent identity, a universal age cutoff, or a fixed recovery delay. Physiological sex, menstrual or menopause context, and gender identity would not define a general plan family or mandatory profile. A future accepted dependent construct could request minimum-necessary, purpose-bound input, allow unknown or declined values, and never default unknown sex to male. Strength and cycling cross-training could appear only as bounded optional candidate modules, without an injury-prevention guarantee or one-to-one substitution rule. Every future population policy would use the accepted shared adaptive recommendation and reassessment contract rather than create a second feedback engine. Exact capability identifiers, horizons, weekly frequencies, progression, run-walk ratios, long-run values, intensity, restart dose, strength dose, cross-training substitution, age adjustment, recovery interval, reassessment cadence, implementation, pilot, rollout, and runtime activation remain explicitly not accepted. Existing accepted distance policies and current runtime behavior remain unchanged.",
  "affected_surfaces": {
    "apis": [
      "Future plan-capability discovery and route-reason fields",
      "Future goal-intent clarification and readiness-only responses",
      "Future purpose-bound profile-field requests and provenance"
    ],
    "clients": [
      "Future web Goal, Training, and managed-plan review experiences",
      "Future WeChat miniapp Goal, Training, and managed-plan parity",
      "Future plugin and MCP capability discovery with no hidden route expansion",
      "English and Chinese population-route, missingness, uncertainty, and safety copy"
    ],
    "models": [
      "Shared plan-generation eligibility and population route contract",
      "Future distance-specific first-completion policies",
      "Future sparse-history and return-to-consistency policies",
      "Future masters and purpose-bound profile modifiers",
      "Shared adaptive recommendation and reassessment dependency graph"
    ],
    "science_notes": [
      "Why first completion uses a separate policy family",
      "Why sparse records do not prove detraining",
      "Why age modifies context without automatic exclusion",
      "Why sex, gender, strength, and cross-training claims remain purpose-bound"
    ]
  },
  "applicability": [
    "Adult recreational running goals and future managed-plan capability discovery",
    "First-completion intent at any distance with a separately accepted distance policy",
    "Performance intent with current goal-relevant capability and population-appropriate history policy",
    "Sparse-history and nonclinical return-to-consistency routes after separate policy acceptance",
    "Masters and older runners as modifiers of otherwise-supported routes",
    "Web, WeChat miniapp, plugin, and MCP surfaces using the same route semantics"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-08-16",
  "decision_notes": [
    "This artifact-mode Decision proposal addresses issue #689 and remains draft and inactive.",
    "The new rigorous Evidence Review compares first-completion, sparse-history, returning-to-consistency, masters, strength, cross-training, physiological sex, reproductive context, and gender evidence through 2026-08-16.",
    "The proposed architecture is hybrid: first completion is a distance-specific policy family; sparse history is a dynamic evidence state; return to consistency is an explicit intent or confirmed state; masters is a non-excluding modifier; and sex or gender is not a general policy family.",
    "This decision does not rewrite the accepted 5 km, 10 km, half-marathon, marathon, baseline, eligibility, or adaptive records. Future implementation must align them explicitly before any new route can activate.",
    "All unresolved behavior-driving values are literal not_accepted. No implementation may infer a value from a study protocol, another distance, common coaching practice, prose, or AI output.",
    "Impact map: rigorous Evidence Review and complete PubMed search manifest -> generated evidence packet -> draft population SDR -> generated decision packet and inactive machine contract -> human evidence and decision review -> future distance and population policy decisions -> deterministic router and capability mapping -> persistence and API -> web, miniapp, plugin, and MCP parity -> ScienceNote and localization -> prospective opt-in pilot -> separate implementation review -> separately approved activation."
  ],
  "decision_review": {
    "approval_statement": "I approve keeping all adult running goals selectable while routing plan generation by current intent, capability, history, and confirmed context. I approve first completion as a separate distance-specific policy family that does not require prior completion of that distance. I approve sparse history as a dynamic evidence state, return to consistency as an explicit or confirmed state, masters age as a non-excluding modifier, and physiological sex or reproductive context only as optional purpose-bound inputs for a separately accepted dependent construct. Gender identity is neither a plan-family selector nor a training-dose variable. I approve bounded strength and cycling support plus the shared adaptive reassessment dependency and the stated adult nonclinical safety scope. I agree that exact schedules, thresholds, capability identifiers, profile algorithms, implementation, pilot, rollout, and runtime activation remain deferred. This approval would not implement or activate a plan.",
    "items": [
      {
        "approval_effect": [
          "A user may select 5 km, 10 km, half-marathon, or marathon completion before being able to complete that distance.",
          "First completion is an intent and current-capability route, not a permanent beginner identity.",
          "Missing policy support preserves the goal and returns an honest unavailable result."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Any first-completion schedule, capability identifier, workout, distance progression, or runtime route.",
          "Automatic conversion between completion and performance intent."
        ],
        "evidence_claim_ids": [
          "eligibility.novice-recreational-different-evidence-family",
          "eligibility.goal-relevant-current-capability-task-specific",
          "population.beginner-evidence-family-not-permanent-identity",
          "population.no-universal-beginner-schedule"
        ],
        "id": "first-completion-family",
        "parameter_names": [
          "population_routing_authority",
          "first_completion_policy_family"
        ],
        "proposed_decision": "Yes. Prior completion of the goal distance is not required to record or select the goal. A first-completion route needs an independently accepted distance policy and cannot reuse a history-rich performance policy by reducing its dose. Performance intent without current direct capability remains unavailable or requires clarification rather than automatic coercion to completion intent.",
        "question": "Should first completion be a separate distance-specific policy family while goal selection remains available before that policy ships?",
        "title": "Let users choose completion goals without prior distance completion"
      },
      {
        "approval_effect": [
          "The router distinguishes data missingness, sparse history, interruption, and return intent.",
          "No personal fitness-loss percentage is inferred from days without records.",
          "Existing history-rich performance policies remain protected from silent scope expansion."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A restart percentage, minimum history count, readiness test, retraining schedule, or automatic detraining estimate.",
          "Medical rehabilitation or return-to-sport prescription."
        ],
        "evidence_claim_ids": [
          "eligibility.recent-history-anchor-without-universal-threshold",
          "population.sparse-history-not-detraining-proof",
          "population.no-universal-returning-dose"
        ],
        "id": "sparse-history-and-returning",
        "parameter_names": [
          "sparse_history_and_returning_routing"
        ],
        "proposed_decision": "Yes. A usable recent anchor may support only a separately accepted uncertainty-aware population route. No usable history yields readiness-only, while sparse history without a usable recent anchor yields insufficient_recent_history_anchor. Missing provider records do not prove training stopped. Return to consistency is user-selectable or athlete-confirmed. Observed continuity may refute an interruption but cannot establish a returning state. No return-to-consistency route can receive a dose-shaped schedule until its own policy is accepted.",
        "question": "Should sparse records remain an evidence state rather than proof of detraining, with returning-to-consistency requiring explicit or confirmed context?",
        "title": "Separate missing history, usable anchors, and return-to-consistency intent"
      },
      {
        "approval_effect": [
          "Highly capable older runners are not excluded by age.",
          "Missing optional age context disables only a future age-dependent modifier.",
          "Recovery remains individual and feedback-aware rather than calendar-age based."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A masters threshold, age score, recovery delay, reduced frequency, lower intensity, or modified progression value.",
          "Medical screening or clearance."
        ],
        "evidence_claim_ids": [
          "eligibility.masters-age-change-not-automatic-exclusion",
          "population.masters-context-not-age-exclusion",
          "population.masters-recovery-not-fixed-delay"
        ],
        "id": "masters-context",
        "parameter_names": [
          "masters_context_modifier"
        ],
        "proposed_decision": "Yes. Masters status is not a separate base family and chronological age never blocks an otherwise supported adult route. Actual capability, history, training continuity, constraints, and observed or athlete-reported recovery carry the decision. No fixed age cutoff or recovery extension is accepted.",
        "question": "Should masters or older runners remain in the matching distance and intent family, with optional age context and actual data modifying the route rather than a universal cutoff?",
        "title": "Use age as context, never as automatic exclusion"
      },
      {
        "approval_effect": [
          "Profile collection follows evidence and purpose rather than convenience.",
          "Provider-imported fields remain source-labelled candidates until confirmed.",
          "Diagnosis-specific or reproductive constructs stay separate from general plan routing."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A female, male, menstrual, menopausal, transgender, nonbinary, or gender-based plan family.",
          "Hidden inference of sensitive traits, medical diagnosis, or mandatory disclosure."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "population.sex-effects-are-construct-specific",
          "population.no-general-sex-or-gender-plan-family"
        ],
        "id": "purpose-bound-profile",
        "parameter_names": [
          "profile_inputs_and_missingness"
        ],
        "proposed_decision": "Yes. Adult-scope confirmation remains required, but exact date of birth, age band, physiological sex, menstrual status, menopause, and gender identity are not global plan prerequisites. A future dependent model must disclose purpose, collect only the minimum necessary input, allow decline or unknown, preserve provenance, and disable only that adjustment when input is missing. Gender identity is not a training-dose variable, and unknown physiological sex never defaults to male.",
        "question": "Should physiological sex, gender identity, date of birth, menstrual context, and menopause remain non-mandatory unless a separately accepted dependent construct requires them?",
        "title": "Collect age, sex, or reproductive context only for an accepted purpose"
      },
      {
        "approval_effect": [
          "Supporting modalities remain modular and evidence-bounded.",
          "All distances and population routes share athlete-controlled feedback and reassessment semantics.",
          "Reassessment remains source-labelled and non-causal."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A strength frequency, cycling ratio, equivalent-impact formula, reassessment cadence, or automatic plan change.",
          "A claim that one support module prevents injury for an individual."
        ],
        "evidence_claim_ids": [
          "population.strength-and-cross-training-bounded-support",
          "eligibility.evidence-quality-no-personal-probability"
        ],
        "id": "support-and-reassessment",
        "parameter_names": [
          "supporting_modalities",
          "shared_reassessment_dependency"
        ],
        "proposed_decision": "Yes. Strength may be an optional performance-support candidate without an injury-prevention guarantee. Cycling may be an optional load-modulation candidate without one-to-one equivalence to running. Exact dose and substitution remain policy-specific. Population plans depend on the shared adaptive contract and cannot define a second feedback or reassessment engine.",
        "question": "Should strength and cycling remain optional support modules while every future population plan uses the same accepted adaptive reassessment semantics?",
        "title": "Keep strength and cross-training bounded and reuse the shared loop"
      },
      {
        "approval_effect": [
          "Population expansion cannot weaken the existing safety boundary.",
          "Unsupported medical or pediatric contexts return a typed stop or unavailable result.",
          "Intensity evidence preserves the repository split-level invariant."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Diagnosis, treatment, rehabilitation, pregnancy guidance, medical clearance, or a safety guarantee.",
          "Activity-average-power intensity inference."
        ],
        "evidence_claim_ids": [
          "eligibility.goal-relevant-current-capability-task-specific",
          "eligibility.evidence-quality-no-personal-probability"
        ],
        "id": "adult-nonclinical-scope",
        "parameter_names": [
          "safety_scope_boundary"
        ],
        "proposed_decision": "Yes. Child and adolescent planning, injury rehabilitation, pregnancy-specific prescription, diagnosis, treatment, clearance, and return-to-sport remain unsupported. Athlete-reported injury, acute illness, or red-flag symptoms stop performance optimization without generating a medical plan. Historical intensity may use splits or samples, never activity-average power.",
        "question": "Should this population policy remain limited to adult nonclinical running goals and stop performance optimization on athlete-reported injury, acute illness, or red-flag symptoms?",
        "title": "Preserve the adult nonclinical safety boundary"
      },
      {
        "approval_effect": [
          "Every behavior-driving value remains literal not_accepted in the contract.",
          "Future values require a versioned population and distance decision with validation."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Inferring values from study protocols, common coaching practice, another distance, prose, or AI output."
        ],
        "evidence_claim_ids": [
          "population.no-universal-beginner-schedule",
          "population.no-universal-returning-dose",
          "population.masters-recovery-not-fixed-delay",
          "population.strength-and-cross-training-bounded-support",
          "population.no-general-sex-or-gender-plan-family"
        ],
        "id": "exact-population-values",
        "parameter_names": [
          "population_specific_numeric_prescription"
        ],
        "proposed_decision": "Defer them. No reviewed evidence validates one cross-distance horizon, frequency, progression, run-walk ratio, long-run limit, intensity ceiling, anchor count, restart percentage, age cutoff, recovery delay, strength dose, cycling substitution, profile algorithm, or reassessment cadence.",
        "question": "Should exact completion, sparse-history, returning, masters, profile, strength, cross-training, and reassessment values remain unapproved?",
        "title": "Defer all exact population schedule and modifier values"
      },
      {
        "approval_effect": [
          "Current capability discovery and plan generation remain unchanged.",
          "Human science approval cannot be mistaken for shipped behavior."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Code changes, user-facing claims, a pilot, a feature flag, rollout, or plan delivery."
        ],
        "evidence_claim_ids": [],
        "id": "implementation-and-activation",
        "parameter_names": [
          "implementation_pilot_and_activation"
        ],
        "proposed_decision": "Defer them. This record defines only the inactive product boundary. Implementation needs exact route identifiers and deterministic fixtures, web and miniapp parity, privacy and deletion behavior, prospective evaluation, separate implementation review, and explicit runtime activation.",
        "question": "Should registry code, policy logic, APIs, clients, pilot criteria, and activation remain outside this science decision?",
        "title": "Defer implementation, pilot, rollout, and runtime activation"
      }
    ],
    "reviewer_task": "Decide whether the six proposed population-routing boundaries are acceptable and whether exact plan values plus implementation should remain deferred. Approve the sheet as a unit or request changes by item ID. The evidence appendix and machine contract provide traceability; the eight items below are the actual decision."
  },
  "evidence_claim_ids": [
    "eligibility.novice-recreational-different-evidence-family",
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "eligibility.evidence-quality-no-personal-probability",
    "population.beginner-evidence-family-not-permanent-identity",
    "population.no-universal-beginner-schedule",
    "population.sparse-history-not-detraining-proof",
    "population.no-universal-returning-dose",
    "population.masters-context-not-age-exclusion",
    "population.masters-recovery-not-fixed-delay",
    "population.strength-and-cross-training-bounded-support",
    "population.sex-effects-are-construct-specific",
    "population.no-general-sex-or-gender-plan-family"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-adult-running-plan-population-routing-v1"
  ],
  "falsification_conditions": [
    "A user cannot record a completion goal until already capable of the distance.",
    "A first-completion, sparse-history, or returning route silently reuses a history-rich performance schedule.",
    "Missing records are interpreted as training cessation or converted to a personal loss percentage.",
    "Chronological age alone excludes a runner or adds a fixed recovery delay.",
    "Unknown physiological sex defaults to male or gender identity changes training dose.",
    "Optional profile fields block a supported base route without an accepted dependent construct.",
    "Strength is presented as injury prevention or cycling as one-to-one running replacement.",
    "A population policy creates a second feedback or reassessment engine.",
    "Any literal not_accepted value becomes runtime behavior through prose, convention, another distance, or AI inference.",
    "Web, miniapp, plugin, or MCP surfaces produce different route semantics for the same inputs.",
    "A future pilot shows unacceptable abandonment, burden, adverse events, subgroup disparity, or false-stop rates against predefined criteria."
  ],
  "id": "sdr-adult-running-plan-population-routing-v1",
  "model_parameters": [
    {
      "applies_to": "adult running-goal capture and future plan capability discovery",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.novice-recreational-different-evidence-family",
        "eligibility.goal-relevant-current-capability-task-specific",
        "population.beginner-evidence-family-not-permanent-identity"
      ],
      "name": "population_routing_authority",
      "rationale": "Goal choice, population applicability, generation, adoption, delivery, and runtime activation are separate authorities.",
      "value": {
        "accepted_population_and_distance_policy_required": true,
        "active_behavior": false,
        "current_accepted_distance_policies_unchanged": true,
        "current_runtime_capability_registry_unchanged": true,
        "goal_capture_independent_from_plan_availability": true,
        "shared_adaptive_dependency": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
        "shared_router_dependency": "sdr-plan-generation-eligibility-safety-v1",
        "static_population_identity_allowed": false,
        "suggestion_only": true
      }
    },
    {
      "applies_to": "first-goal-distance completion and performance-intent clarification",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.novice-recreational-different-evidence-family",
        "eligibility.goal-relevant-current-capability-task-specific",
        "population.no-universal-beginner-schedule"
      ],
      "name": "first_completion_policy_family",
      "rationale": "Completion is a valid goal before current distance capability exists, while a performance policy cannot be broadened by reducing its dose.",
      "value": {
        "automatic_intent_coercion": false,
        "distance_specific_policy_required": true,
        "first_at_goal_distance_is_permanent_beginner_identity": false,
        "goal_intent": "completion",
        "history_rich_performance_policy_reuse": false,
        "no_matching_policy_result": "completion_policy_unavailable",
        "performance_without_current_direct_capability_result": "performance_policy_unavailable_or_clarification_required",
        "prior_goal_distance_completion_required": false,
        "route_state": "first_completion_policy_required"
      }
    },
    {
      "applies_to": "history sufficiency, interruption clarification, and return-to-consistency routing",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "population.sparse-history-not-detraining-proof",
        "population.no-universal-returning-dose"
      ],
      "name": "sparse_history_and_returning_routing",
      "rationale": "History completeness, interruption, current capability, and goal intent are distinct states and must not be collapsed into one inferred label.",
      "value": {
        "existing_history_rich_policy_reuse_without_alignment": false,
        "history_states": {
          "history_rich": "continue_to_matching_distance_and_intent_policy",
          "no_usable_history": "readiness_only",
          "sparse_with_usable_recent_anchor": "uncertainty_aware_population_policy_required",
          "sparse_without_usable_recent_anchor": "insufficient_recent_history_anchor",
          "unknown": "clarification_required"
        },
        "observed_continuity_can_establish_returning_state": false,
        "observed_continuity_can_refute_interruption": true,
        "observed_record_missingness_establishes_interruption": false,
        "personal_detraining_loss_estimate_allowed": false,
        "returning_state_requires_athlete_confirmation": true,
        "returning_to_consistency_intent_auto_inferred": false,
        "returning_to_consistency_intent_user_selectable": true,
        "returning_to_consistency_route": "separate_accepted_consistency_policy_required",
        "sparse_history_establishes_detraining": false
      }
    },
    {
      "applies_to": "every otherwise-supported adult distance and intent route",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "population.masters-context-not-age-exclusion",
        "population.masters-recovery-not-fixed-delay"
      ],
      "name": "masters_context_modifier",
      "rationale": "Age changes population physiology, but capability, training continuity, and recovery vary enough that age alone cannot select or reject a plan.",
      "value": {
        "automatic_age_exclusion": false,
        "fixed_age_based_recovery_extension": "none_defined",
        "missing_optional_age_context_result": "base_route_without_age_dependent_modifier",
        "route_inputs": [
          "current_goal_relevant_capability",
          "recent_history_and_continuity",
          "current_load_relative_to_self",
          "observed_or_athlete_reported_recovery",
          "athlete_stated_constraints",
          "optional_purpose_bound_age_context"
        ],
        "separate_base_policy_family": false,
        "study_or_competition_masters_label_is_person_identity": false,
        "universal_biological_age_cutoff": "none_defined"
      }
    },
    {
      "applies_to": "profile, point-of-use clarification, and future dependent modifiers",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.sex-effects-are-construct-specific",
        "population.no-general-sex-or-gender-plan-family",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "profile_inputs_and_missingness",
      "rationale": "Physiological sex, reproductive context, and gender are distinct constructs. Collection follows an accepted purpose rather than becoming a blanket prerequisite.",
      "value": {
        "adult_scope_confirmation_required": true,
        "age_band_globally_required": false,
        "exact_date_of_birth_globally_required": false,
        "future_field_requirements": [
          "separately_accepted_dependent_construct",
          "disclosed_product_purpose",
          "minimum_necessary_collection",
          "provenance",
          "correction",
          "deletion"
        ],
        "gender_identity_is_training_dose_input": false,
        "menstrual_or_menopause_context_globally_required": false,
        "missing_optional_field_disables_only_dependent_adjustment": true,
        "physiological_sex_globally_required": false,
        "provider_imported_profile_is_confirmed_truth": false,
        "provider_profile_requires_source_label_and_user_confirmation": true,
        "unknown_physiological_sex_default": "unknown",
        "user_may_decline_optional_fields": true
      }
    },
    {
      "applies_to": "future first-completion, sparse-history, returning, and masters modules",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.strength-and-cross-training-bounded-support"
      ],
      "name": "supporting_modalities",
      "rationale": "Supporting modalities may be useful, while reviewed evidence does not establish universal dose, equivalence, or injury prevention.",
      "value": {
        "cycling_cross_training": {
          "one_to_one_running_substitution": false,
          "sport_specific_capability_evidence_replacement": false,
          "status": "optional_candidate_load_modulation_module",
          "universal_population_dose": false
        },
        "distance_and_population_policy_must_bound_any_module": true,
        "strength": {
          "individual_injury_prevention_guarantee": false,
          "possible_performance_support": true,
          "status": "optional_candidate_support_module",
          "universal_population_dose": false
        }
      }
    },
    {
      "applies_to": "every future managed population plan",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "shared_reassessment_dependency",
      "rationale": "Population routing changes applicability, not the shared semantics for recommendation, athlete review, observation, and reassessment.",
      "value": {
        "population_policy_may_define_second_feedback_engine": false,
        "reassessment_proves_individual_causality": false,
        "reassessment_requires_source_labelled_evidence": true,
        "shared_policy": "sdr-adaptive-plan-feasibility-and-adjustment-v1",
        "shared_policy_runtime_state": "inactive",
        "universal_reassessment_cadence": "none_defined"
      }
    },
    {
      "applies_to": "population intake, capability routing, and historical intensity evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "safety_scope_boundary",
      "rationale": "Population coverage cannot turn a nonclinical performance policy into medical or pediatric guidance or weaken the split-level power invariant.",
      "value": {
        "activity_average_power_allowed_for_intensity": false,
        "adult_scope_only": true,
        "athlete_reported_injury_acute_illness_or_red_flag_result": "stop_performance_optimization",
        "child_or_adolescent_route": "unsupported",
        "diagnosis_or_treatment": "unsupported",
        "injury_rehabilitation": "unsupported",
        "intensity_evidence_allowed": [
          "activity_splits",
          "activity_samples"
        ],
        "medical_clearance": "unsupported",
        "pregnancy_specific_prescription": "unsupported",
        "return_to_sport": "unsupported"
      }
    },
    {
      "applies_to": "all population-specific plan generation and reassessment values",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.no-universal-beginner-schedule",
        "population.no-universal-returning-dose",
        "population.masters-recovery-not-fixed-delay",
        "population.strength-and-cross-training-bounded-support",
        "population.no-general-sex-or-gender-plan-family"
      ],
      "name": "population_specific_numeric_prescription",
      "rationale": "The review supports routing boundaries and uncertainty, not one set of behavior-driving values across populations and distances.",
      "value": {
        "cycling_substitution_ratio": "not_accepted",
        "first_completion_horizon_days": "not_accepted",
        "first_completion_intensity_distribution": "not_accepted",
        "first_completion_long_run_limit": "not_accepted",
        "first_completion_progression": "not_accepted",
        "first_completion_run_walk_ratio": "not_accepted",
        "first_completion_weekly_running_frequency": "not_accepted",
        "masters_age_cutoff": "not_accepted",
        "masters_frequency_or_intensity_adjustment": "not_accepted",
        "masters_recovery_extension": "not_accepted",
        "physiological_sex_or_reproductive_adjustment": "not_accepted",
        "reassessment_cadence_and_triggers": "not_accepted",
        "returning_progression": "not_accepted",
        "returning_restart_percentage": "not_accepted",
        "runtime_capability_identifiers": "not_accepted",
        "sparse_history_latest_run_days": "not_accepted",
        "sparse_history_minimum_anchor_sessions": "not_accepted",
        "sparse_history_minimum_anchor_weeks": "not_accepted",
        "strength_frequency_and_load": "not_accepted"
      }
    },
    {
      "applies_to": "implementation, pilot, rollout, and runtime",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "implementation_pilot_and_activation",
      "rationale": "Science and product-boundary review are separate from implementation, prospective evaluation, rollout, delivery authority, and activation.",
      "value": {
        "accepted_distance_policy_alignment": "not_accepted",
        "active_behavior": false,
        "api_contracts": "not_accepted",
        "capability_registry_mapping": "not_accepted",
        "comparator": "not_accepted",
        "implementation_approval": "not_accepted",
        "persistence_schema": "not_accepted",
        "pilot_population": "not_accepted",
        "plugin_and_mcp_contracts": "not_accepted",
        "policy_router_logic": "not_accepted",
        "primary_and_guardrail_metrics": "not_accepted",
        "profile_collection_and_privacy_operations": "not_accepted",
        "rollout": "not_accepted",
        "runtime_activation": "not_accepted",
        "sample_size_and_duration": "not_accepted",
        "science_note_and_localization": "not_accepted",
        "success_failure_and_rollback_thresholds": "not_accepted",
        "web_and_miniapp_clients": "not_accepted"
      }
    }
  ],
  "model_version": "adult-running-plan-population-routing-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Exact date of birth, age band, physiological sex, menstrual status, menopause, and gender identity are not global plan prerequisites.",
    "Optional fields require an accepted purpose, minimum-necessary collection, visible provenance, correction, and deletion.",
    "Provider-imported profile values remain source-labelled candidates until user confirmation.",
    "Unknown and declined values remain distinct and never become male, average, or inferred.",
    "Do not infer reproductive, medical, or gender context from training behavior."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Require a user to have already completed the goal distance before allowing the goal",
      "rationale": "Goal intent is durable user choice. Current capability determines which policy may generate a plan, not whether the goal can be recorded."
    },
    {
      "alternative": "Scale a history-rich performance policy down for first completion",
      "rationale": "Novice and first-completion populations have different applicability and injury evidence, while no reviewed source validates a universal scaled version of an accepted performance policy."
    },
    {
      "alternative": "Treat missing or sparse Praxys records as proven detraining",
      "rationale": "Detraining studies require known training reduction or cessation. Provider missingness and unrecorded training remain unknown."
    },
    {
      "alternative": "Use one restart percentage after any interruption",
      "rationale": "Detraining differs by prior training, outcome, duration, and whether training was reduced or stopped; no recreational restart formula was validated."
    },
    {
      "alternative": "Create a separate masters plan family or block users at age 40",
      "rationale": "Competition and study definitions are administrative, not biological cutoffs. Highly capable older athletes and large training-related variation make automatic exclusion indefensible."
    },
    {
      "alternative": "Add a fixed extra recovery day for every older runner",
      "rationale": "Direct trained-runner studies show protocol-specific and inter-individual recovery rather than a universal age delay."
    },
    {
      "alternative": "Create female and male plan families and default unknown to male",
      "rationale": "Overall injury risk is similar, specific constructs differ, and no general sex-based plan family is validated. Unknown must remain unknown."
    },
    {
      "alternative": "Require date of birth, physiological sex, menstrual status, or menopause before any plan",
      "rationale": "No reviewed source establishes that every field improves every plan. Collection must be purpose-bound and minimum necessary."
    },
    {
      "alternative": "Treat strength as injury prevention or cycling as equivalent running",
      "rationale": "Evidence supports bounded candidate use but not an individual guarantee or universal substitution ratio."
    },
    {
      "alternative": "Let each population policy define its own feedback engine",
      "rationale": "Duplicate semantics would drift across distances and clients and conflict with the accepted shared adaptive policy."
    },
    {
      "alternative": "Implement the closest reasonable values now and validate later",
      "rationale": "Evidence and product-boundary approval do not establish exact values, implementation correctness, pilot safety, or runtime authority."
    }
  ],
  "safety_implications": [
    "Child and adolescent plans remain outside this adult policy.",
    "Injury rehabilitation, pregnancy-specific prescription, diagnosis, treatment, clearance, and return-to-sport remain unsupported.",
    "Athlete-reported injury, acute illness, or red-flag symptoms stop performance optimization without a success-shaped plan.",
    "No automatic catch-up, fixed progression, restart percentage, or age-based recovery rule.",
    "Historical intensity analysis uses activity splits or samples, never activity-average power."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Route first-completion, sparse-history, and masters plans without permanent labels",
  "user_facing_claim_limits": [
    "Do not require prior goal-distance completion before allowing a completion goal.",
    "Do not describe first completion, sparse history, returning, or masters as permanent identities.",
    "Do not imply that missing records prove detraining or reveal a personal capacity-loss percentage.",
    "Do not promise that age, sex, gender, strength, cycling, or one program determines safety or success.",
    "Do not present a masters cutoff, recovery delay, restart percentage, or reassessment cadence as published.",
    "Do not default unknown physiological sex to male or imply that gender identity determines training dose.",
    "Explain when an optional profile field supports a specific accepted construct and what happens when it is unknown.",
    "Do not imply that strength prevents injury or that cycling is equivalent to running.",
    "Preserve the goal and provide an honest unavailable, clarification, readiness-only, or safety result when no policy matches."
  ],
  "validation_plan": [
    "A digest-bound human evidence reviewer must accept, revise, or reject the new Evidence Review before this SDR can be accepted.",
    "A digest-bound human decision approver must review the eight-item decision sheet and exact inactive contract.",
    "Define exact future route identifiers and deterministic fixtures for first completion, sparse history with and without an anchor, explicit return-to-consistency, masters context, unknown profile fields, and unsupported safety scope.",
    "Verify goal capture remains available when no plan policy matches and no route silently changes completion or performance intent.",
    "Verify missing provider records never create an interruption, detraining percentage, sex default, masters exclusion, or medical inference.",
    "Verify every accepted population and distance policy reuses the shared adaptive recommendation and reassessment contract.",
    "Add registry, policy, API, web, miniapp, plugin, MCP, privacy, deletion, localization, and accessibility tests before implementation review.",
    "Predefine a prospective opt-in pilot with completion, adherence, usefulness, burden, abandonment, injury, adverse-event, and false-stop guardrails.",
    "Audit outcomes and route availability by age, sex where purpose-bound, history depth, return state, distance, intent, missingness, provider, language, and client.",
    "Require separate implementation review before runtime_state changes from inactive."
  ],
  "version": 1
}
```

</details>
