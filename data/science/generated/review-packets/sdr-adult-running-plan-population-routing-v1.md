# Science decision review packet: Bound scientific applicability for adult running-plan populations

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-adult-running-plan-population-routing-v1`
- **Lifecycle:** `draft`
- **Model version:** `adult-running-plan-population-routing-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:e0db9989e767f5f2bbc6ab858830427f60bd045e72a7cd46ed9e38a16b349bfb`
- **Contract digest:** `sha256:934390730001bd44625a9cbeb1e45da34a09d45af613db8f3965ed130475d0d7`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Review the six scientific applicability boundaries and the two explicit deferrals below. Approve the sheet as a unit or request changes by item ID. Do not treat this Science review as a Product, Design, Trust, Architecture, Delivery, pilot, rollout, or activation decision.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `first-completion-applicability` — Bound first-completion applicability

- **Question:** Does the evidence distinguish novice and first-completion applicability from history-rich performance applicability without establishing a universal schedule or permanent identity?
- **Proposed decision:** Yes. Treat novice and first-completion evidence as a distinct applicability family. The reviewed evidence establishes neither one universal schedule nor a permanent beginner identity.
- **Approval means:**
  - The scientific contract records a distinct evidence and applicability family.
  - Universal schedules and permanent identities remain unsupported.
- **This does not authorize:**
  - A universal schedule or permanent identity claim.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `first_completion_applicability`
- **Evidence claims:** `eligibility.novice-recreational-different-evidence-family`, `population.beginner-evidence-family-not-permanent-identity`, `population.no-universal-beginner-schedule`

</details>

#### `history-detraining-inference` — Limit history and detraining inference

- **Question:** Do sparse or missing records establish cessation or detraining, and does detraining evidence establish one restart dose?
- **Proposed decision:** No. Sparse or missing records do not prove cessation or detraining. Detraining evidence does not establish a universal restart dose.
- **Approval means:**
  - Record missingness remains insufficient evidence of cessation or detraining.
  - No universal restart dose is scientifically accepted.
- **This does not authorize:**
  - A cessation or detraining conclusion from missingness or a universal restart dose.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `history_and_detraining_inference`
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `population.sparse-history-not-detraining-proof`, `population.no-universal-returning-dose`

</details>

#### `masters-applicability` — Bound masters applicability

- **Question:** Does age establish a universal exclusion, cutoff, or fixed recovery delay for adult running plans?
- **Proposed decision:** No. Age is relevant context, but the reviewed evidence establishes no universal age exclusion, biological cutoff, or fixed recovery delay.
- **Approval means:**
  - Age remains scientifically relevant context.
  - Universal age exclusions, cutoffs, and fixed recovery delays remain unsupported.
- **This does not authorize:**
  - A universal exclusion, cutoff, or fixed recovery claim based on age.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `masters_applicability`
- **Evidence claims:** `eligibility.masters-age-change-not-automatic-exclusion`, `population.masters-context-not-age-exclusion`, `population.masters-recovery-not-fixed-delay`

</details>

#### `construct-specific-profile-evidence` — Keep profile evidence construct-specific

- **Question:** Does evidence about sex, reproductive context, menopause, transgender/nonbinary populations, or gender identity validate a general plan family or universal dose rule?
- **Proposed decision:** No. These are distinct constructs with construct-specific evidence. The review validates neither a general plan family nor a universal dose rule for any combined profile category.
- **Approval means:**
  - Scientific claims remain tied to the construct actually studied.
  - General profile-based plan families and universal dose rules remain unsupported.
- **This does not authorize:**
  - Combining distinct constructs into a general family or universal dose claim.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `construct_specific_profile_evidence`
- **Evidence claims:** `population.sex-effects-are-construct-specific`, `population.no-general-sex-or-gender-plan-family`

</details>

#### `strength-cross-training-evidence` — Bound strength and cross-training evidence

- **Question:** Does the reviewed strength or cycling evidence establish injury prevention, equivalence to running, or a universal dose?
- **Proposed decision:** No. Strength and cycling evidence is bounded. It does not establish an injury-prevention guarantee, running equivalence, or a universal dose.
- **Approval means:**
  - Strength and cycling claims remain within the reviewed evidence.
  - Injury prevention, equivalence, and universal dose remain unsupported.
- **This does not authorize:**
  - An injury-prevention, running-equivalence, or universal-dose claim.

<details><summary>Traceability: 1 contract group, 1 evidence claim</summary>

- **Contract groups covered:** `strength_and_cross_training_evidence`
- **Evidence claims:** `population.strength-and-cross-training-bounded-support`

</details>

#### `adult-nonclinical-scope` — Preserve adult nonclinical scope

- **Question:** Should this evidence decision remain limited to adult nonclinical planning and split- or sample-level intensity evidence?
- **Proposed decision:** Yes. Pediatric planning, diagnosis, treatment, rehabilitation, pregnancy-specific prescription, clearance, and return-to-sport remain outside scope. Activity-average power is not valid intensity evidence; use activity splits or samples.
- **Approval means:**
  - The scientific applicability boundary remains adult and nonclinical.
  - The split-level power invariant remains explicit.
- **This does not authorize:**
  - Medical or pediatric guidance, a safety guarantee, or any runtime response.

<details><summary>Traceability: 1 contract group, 0 evidence claims</summary>

- **Contract groups covered:** `adult_nonclinical_scope`
- **Evidence claims:** _None; product or lifecycle boundary only_

</details>

### Decisions explicitly deferred

#### `all-exact-values` — Defer all exact values

- **Question:** Should every exact schedule, threshold, restart, age, recovery, profile, strength, and cycling value remain unaccepted?
- **Proposed decision:** Yes. Keep every exact value literal not_accepted. Study protocols, common practice, another population, prose, or AI output do not supply a universal value.
- **Approval means:**
  - Every listed exact value remains visibly unresolved.
  - Future values require separately reviewed evidence and decisions.
- **This does not authorize:**
  - Inferring, defaulting, or implementing any exact value.

<details><summary>Traceability: 1 contract group, 5 evidence claims</summary>

- **Contract groups covered:** `exact_values`
- **Evidence claims:** `population.no-universal-beginner-schedule`, `population.no-universal-returning-dose`, `population.masters-recovery-not-fixed-delay`, `population.strength-and-cross-training-bounded-support`, `population.no-general-sex-or-gender-plan-family`

</details>

#### `all-non-science-decisions` — Defer all non-Science decisions

- **Question:** Should Product, Design, Trust, Architecture, implementation, pilot, rollout, and activation decisions remain outside this Science record?
- **Proposed decision:** Yes. Defer Product promises, goal and intent behavior, route semantics, metrics, and pilot choices; Design clarification and confirmation experiences; Trust profile-data and privacy behavior; Architecture feedback-system and contract choices; and Delivery implementation, client behavior, rollout, and activation. Each requires its own linked decision and human review.
- **Approval means:**
  - The Science contract remains limited to evidence, uncertainty, claim limits, and safety scope.
  - Later role-owned outputs remain explicit structured handoffs.
- **This does not authorize:**
  - Any Product, Design, Trust, Architecture, Delivery, pilot, rollout, activation, or runtime choice.

<details><summary>Traceability: 1 contract group, 0 evidence claims</summary>

- **Contract groups covered:** `non_science_authority_boundary`
- **Evidence claims:** _None; product or lifecycle boundary only_

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve only these inactive scientific boundaries: first-completion applicability is distinct from history-rich performance applicability; sparse or missing records do not prove cessation or detraining; age is relevant without establishing a universal exclusion, cutoff, or fixed recovery delay; sex, reproductive, menopause, transgender/nonbinary, and gender evidence remains construct-specific; strength and cycling evidence remains bounded; and scope remains adult, nonclinical, and split-level for intensity. I agree that all exact values remain not_accepted and that every Product, Design, Trust, Architecture, implementation, pilot, rollout, and activation decision remains outside Science authority and deferred to a linked decision with human review. This approval would not implement or activate behavior.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-adult-running-plan-population-routing-v1`
- Digest: `sha256:e0db9989e767f5f2bbc6ab858830427f60bd045e72a7cd46ed9e38a16b349bfb`

> I approve only these inactive scientific boundaries: first-completion applicability is distinct from history-rich performance applicability; sparse or missing records do not prove cessation or detraining; age is relevant without establishing a universal exclusion, cutoff, or fixed recovery delay; sex, reproductive, menopause, transgender/nonbinary, and gender evidence remains construct-specific; strength and cycling evidence remains bounded; and scope remains adult, nonclinical, and split-level for intensity. I agree that all exact values remain not_accepted and that every Product, Design, Trust, Architecture, implementation, pilot, rollout, and activation decision remains outside Science authority and deferred to a linked decision with human review. This approval would not implement or activate behavior.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:e0db9989e767f5f2bbc6ab858830427f60bd045e72a7cd46ed9e38a16b349bfb","subject_id":"sdr-adult-running-plan-population-routing-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If accepted by digest-bound human review, this inactive Science decision would establish only evidence applicability, uncertainty, claim limits, and safety scope. Novice and first-completion populations are a distinct evidence and applicability family from history-rich performance populations; the evidence establishes neither a universal schedule nor a permanent identity. Sparse or missing records do not prove cessation or detraining, and detraining evidence does not establish a universal restart dose. Age is relevant context, but the evidence establishes no universal age exclusion, cutoff, or fixed recovery delay. Evidence concerning physiological sex, reproductive context, menopause, transgender and nonbinary people, and gender identity is construct-specific and validates neither a general plan family nor a universal dose rule. Strength and cycling evidence is bounded and does not establish injury prevention, running equivalence, or a universal dose. The scope remains adult and nonclinical, and historical intensity evidence must use splits or samples rather than activity-average power. All exact values remain not_accepted. Product promises, route semantics, interaction and profile-data behavior, system architecture, metrics, implementation, pilot, rollout, and activation are outside Science authority and remain deferred to linked Product, Design, Trust, Architecture, and Delivery decisions.

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

#### `eligibility.masters-age-change-not-automatic-exclusion` — moderate

Endurance performance and training capacity change with age, while masters athletes and older adults can retain high capability and benefit from continued exercise. The reviewed evidence supports neither automatic exclusion by age nor a universal age cutoff or recovery rule.

- **Evidence Review:** `evidence-plan-generation-eligibility-safety-v1`
- **Sources:** `tanaka-2008`, `chodzko-zajko-2009`, `burtscher-2022`
- **Limitations:** Masters athletes are selected, trained populations and are not representative of every older runner.; The evidence does not define an age cutoff, recovery rule, or safe automatic plan.; Treating age as an uncertainty or recovery modifier is a Praxys guardrail that requires prospective validation.; Women and older women are underrepresented.

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

#### `first_completion_applicability` — guardrail

- **Applies to:** scientific applicability for novice and first-completion evidence
- **Evidence claims:** `eligibility.novice-recreational-different-evidence-family`, `population.beginner-evidence-family-not-permanent-identity`, `population.no-universal-beginner-schedule`
- **Rationale:** The evidence distinguishes applicability families without validating a universal schedule or permanent personal category.
- **Exact value:**

```json
{
  "novice_and_first_completion_distinct_from_history_rich_performance": true,
  "permanent_identity_established": false,
  "universal_schedule_established": false
}
```

#### `history_and_detraining_inference` — guardrail

- **Applies to:** scientific inference from sparse or missing training records
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `population.sparse-history-not-detraining-proof`, `population.no-universal-returning-dose`
- **Rationale:** Missingness is not a known reduction or cessation exposure, and reviewed detraining studies do not validate one restart prescription.
- **Exact value:**

```json
{
  "detraining_evidence_establishes_universal_restart_dose": false,
  "sparse_or_missing_records_establish_cessation": false,
  "sparse_or_missing_records_establish_detraining": false
}
```

#### `masters_applicability` — guardrail

- **Applies to:** scientific applicability for masters and older adults
- **Evidence claims:** `eligibility.masters-age-change-not-automatic-exclusion`, `population.masters-context-not-age-exclusion`, `population.masters-recovery-not-fixed-delay`
- **Rationale:** Age is relevant to population context, but the evidence does not establish a universal exclusion, cutoff, or fixed recovery delay.
- **Exact value:**

```json
{
  "age_is_relevant_context": true,
  "fixed_age_based_recovery_delay_established": false,
  "universal_age_cutoff_established": false,
  "universal_age_exclusion_established": false
}
```

#### `construct_specific_profile_evidence` — guardrail

- **Applies to:** scientific claims involving sex, reproductive, menopause, transgender/nonbinary, or gender constructs
- **Evidence claims:** `population.sex-effects-are-construct-specific`, `population.no-general-sex-or-gender-plan-family`
- **Rationale:** Construct-specific findings cannot be combined into a general profile category, plan family, or universal dose rule.
- **Exact value:**

```json
{
  "constructs": [
    "physiological_sex",
    "reproductive_context",
    "menopause",
    "transgender_and_nonbinary",
    "gender_identity"
  ],
  "evidence_is_construct_specific": true,
  "general_plan_family_validated": false,
  "universal_dose_rule_validated": false
}
```

#### `strength_and_cross_training_evidence` — guardrail

- **Applies to:** scientific claims about strength and cycling cross-training
- **Evidence claims:** `population.strength-and-cross-training-bounded-support`
- **Rationale:** Reviewed strength and cycling evidence does not establish injury prevention, equivalence to running, or one universal dose.
- **Exact value:**

```json
{
  "cycling_evidence_is_bounded": true,
  "injury_prevention_established": false,
  "running_equivalence_established": false,
  "strength_evidence_is_bounded": true,
  "universal_dose_established": false
}
```

#### `adult_nonclinical_scope` — guardrail

- **Applies to:** safety scope and historical intensity evidence
- **Evidence claims:** _None; product rationale only_
- **Rationale:** The decision is bounded to adult nonclinical planning and preserves the repository split-level power invariant.
- **Exact value:**

```json
{
  "activity_average_power_valid_for_intensity": false,
  "adult_nonclinical_scope_only": true,
  "medical_or_rehabilitation_prescription_within_scope": false,
  "pediatric_planning_within_scope": false,
  "pregnancy_specific_prescription_within_scope": false,
  "valid_intensity_evidence_sources": [
    "activity_splits",
    "activity_samples"
  ]
}
```

#### `exact_values` — guardrail

- **Applies to:** all exact values within this scientific topic
- **Evidence claims:** `population.no-universal-beginner-schedule`, `population.no-universal-returning-dose`, `population.masters-recovery-not-fixed-delay`, `population.strength-and-cross-training-bounded-support`, `population.no-general-sex-or-gender-plan-family`
- **Rationale:** The evidence establishes boundaries and uncertainty, not universal behavior-driving values.
- **Exact value:**

```json
{
  "age_based_recovery_delay": "not_accepted",
  "age_cutoff": "not_accepted",
  "cycling_substitution_ratio": "not_accepted",
  "first_completion_schedule": "not_accepted",
  "history_sufficiency_thresholds": "not_accepted",
  "restart_dose": "not_accepted",
  "sex_reproductive_menopause_or_gender_dose_rule": "not_accepted",
  "strength_dose": "not_accepted"
}
```

#### `non_science_authority_boundary` — guardrail

- **Applies to:** authority and structured handoffs for later human-reviewed decisions
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Science constrains later decisions but cannot choose value, experience, privacy, architecture, implementation, pilot, rollout, or activation.
- **Exact value:**

```json
{
  "required_future_handoffs": {
    "architecture": "Shared feedback-system and cross-domain contract choices.",
    "delivery": "API, web, miniapp, plugin, MCP, rollout, activation, and all other implementation behavior.",
    "design": "Clarification, confirmation, and other interaction behavior.",
    "product": "Product promises, goal availability, intent policy, route semantics, outcome metrics, and pilot choices.",
    "trust": "Profile collection, provenance, correction, deletion, retention, and privacy behavior."
  },
  "science_authority": [
    "evidence_applicability",
    "uncertainty",
    "claim_limits",
    "safety_scope"
  ]
}
```

### Rejected alternatives

#### Collapse novice or first-completion evidence into history-rich performance evidence

The reviewed populations and applicability differ, while no universal schedule or permanent identity is established.

#### Treat sparse or missing records as proven cessation or detraining

Record missingness does not establish the exposure studied in detraining research, and the evidence does not yield a universal restart dose.

#### Use chronological age as a universal exclusion, cutoff, or recovery delay

Age is relevant context, but capability and recovery vary and no universal behavior-driving value was validated.

#### Turn sex, reproductive, menopause, transgender/nonbinary, or gender evidence into one plan family

These are distinct constructs, and the evidence does not validate a general family or universal dose rule.

#### Claim strength prevents injury or cycling is equivalent to running

The evidence supports only bounded conclusions and no universal dose, equivalence, or individual injury-prevention guarantee.

#### Let Science choose the Product response or implementation

Evidence constrains later choices but does not own product promises, interaction, privacy, architecture, delivery, pilot, rollout, or activation decisions.

### Applicability

- Adult nonclinical recreational running-plan evidence and applicability review
- Novice and first-completion, sparse-history, masters, profile-construct, strength, and cycling evidence
- Scientific claim limits and exact-value uncertainty only

### User-facing claim limits

- Do not present novice or first-completion status as a permanent identity or claim one universal schedule.
- Do not claim sparse or missing records prove cessation, detraining, or a personal restart dose.
- Do not present a universal age exclusion, cutoff, or fixed recovery delay as established evidence.
- Do not generalize construct-specific sex, reproductive, menopause, transgender/nonbinary, or gender evidence into a plan family or dose rule.
- Do not claim strength prevents injury, cycling is equivalent to running, or either has a universal dose.

### Safety implications

- This evidence decision is limited to adult nonclinical planning.
- Pediatric planning, diagnosis, treatment, rehabilitation, pregnancy-specific prescription, clearance, and return-to-sport are outside scope.
- Historical intensity evidence uses activity splits or samples, never activity-average power.

### Privacy implications

- The evidence establishes no universal profile-data prerequisite or default.
- Profile collection, provenance, correction, deletion, retention, and privacy behavior are outside Science authority and require linked Trust, Product, and Design decisions.

### Validation plan

- A digest-bound human reviewer must accept, revise, or reject this eight-item Science-only decision sheet.
- Verify the approved Evidence content digest remains sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8.
- Verify the machine contract contains the six scientific boundaries, literal not_accepted exact values, and no Product-owned behavior fields.
- Verify the two deferrals map later Product, Design, Trust, Architecture, and Delivery handoffs without creating their records or schemas.
- Verify generated packets, machine contract, and registry index are deterministic and runtime_state remains inactive.

### Falsification conditions

- The Science contract selects a Product promise, route result, goal or intent behavior, confirmation interaction, profile-data behavior, feedback-system choice, metric, implementation, pilot, rollout, or activation.
- Sparse or missing records are treated as proof of cessation or detraining.
- A universal age exclusion, cutoff, fixed recovery delay, general profile plan family, injury-prevention claim, or running-equivalence claim is presented as established.
- Any exact value differs from literal not_accepted.
- Activity-average power is accepted for intensity analysis.
- The generated contract becomes active or runtime behavior changes.

### Decision notes

- This artifact-mode Science decision addresses issue #689 and remains draft and inactive.
- The Evidence Review is immutable in this iteration and remains bound to approved digest sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8.
- Product, Design, Trust, Architecture, and Delivery outputs are structured handoffs for later human review; this iteration creates none of those records or schemas.
- Implementation impact map: this SDR, its generated decision packet and machine contract, the regenerated evidence packet and registry index, and targeted deterministic tests only; runtime and accepted upstream science remain unchanged.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "Science evidence applicability and claim-limit contract",
    "Science-only human decision sheet"
  ],
  "contract_digest": "sha256:934390730001bd44625a9cbeb1e45da34a09d45af613db8f3965ed130475d0d7",
  "decision_id": "sdr-adult-running-plan-population-routing-v1",
  "decision_status": "draft",
  "decision_version": 1,
  "evidence_claim_ids": [
    "eligibility.novice-recreational-different-evidence-family",
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.masters-age-change-not-automatic-exclusion",
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
    "adult_nonclinical_scope": {
      "applies_to": "safety scope and historical intensity evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "adult_nonclinical_scope_only": true,
        "medical_or_rehabilitation_prescription_within_scope": false,
        "pediatric_planning_within_scope": false,
        "pregnancy_specific_prescription_within_scope": false,
        "valid_intensity_evidence_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    "construct_specific_profile_evidence": {
      "applies_to": "scientific claims involving sex, reproductive, menopause, transgender/nonbinary, or gender constructs",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.sex-effects-are-construct-specific",
        "population.no-general-sex-or-gender-plan-family"
      ],
      "value": {
        "constructs": [
          "physiological_sex",
          "reproductive_context",
          "menopause",
          "transgender_and_nonbinary",
          "gender_identity"
        ],
        "evidence_is_construct_specific": true,
        "general_plan_family_validated": false,
        "universal_dose_rule_validated": false
      }
    },
    "exact_values": {
      "applies_to": "all exact values within this scientific topic",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.no-universal-beginner-schedule",
        "population.no-universal-returning-dose",
        "population.masters-recovery-not-fixed-delay",
        "population.strength-and-cross-training-bounded-support",
        "population.no-general-sex-or-gender-plan-family"
      ],
      "value": {
        "age_based_recovery_delay": "not_accepted",
        "age_cutoff": "not_accepted",
        "cycling_substitution_ratio": "not_accepted",
        "first_completion_schedule": "not_accepted",
        "history_sufficiency_thresholds": "not_accepted",
        "restart_dose": "not_accepted",
        "sex_reproductive_menopause_or_gender_dose_rule": "not_accepted",
        "strength_dose": "not_accepted"
      }
    },
    "first_completion_applicability": {
      "applies_to": "scientific applicability for novice and first-completion evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.novice-recreational-different-evidence-family",
        "population.beginner-evidence-family-not-permanent-identity",
        "population.no-universal-beginner-schedule"
      ],
      "value": {
        "novice_and_first_completion_distinct_from_history_rich_performance": true,
        "permanent_identity_established": false,
        "universal_schedule_established": false
      }
    },
    "history_and_detraining_inference": {
      "applies_to": "scientific inference from sparse or missing training records",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "population.sparse-history-not-detraining-proof",
        "population.no-universal-returning-dose"
      ],
      "value": {
        "detraining_evidence_establishes_universal_restart_dose": false,
        "sparse_or_missing_records_establish_cessation": false,
        "sparse_or_missing_records_establish_detraining": false
      }
    },
    "masters_applicability": {
      "applies_to": "scientific applicability for masters and older adults",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "population.masters-context-not-age-exclusion",
        "population.masters-recovery-not-fixed-delay"
      ],
      "value": {
        "age_is_relevant_context": true,
        "fixed_age_based_recovery_delay_established": false,
        "universal_age_cutoff_established": false,
        "universal_age_exclusion_established": false
      }
    },
    "non_science_authority_boundary": {
      "applies_to": "authority and structured handoffs for later human-reviewed decisions",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "required_future_handoffs": {
          "architecture": "Shared feedback-system and cross-domain contract choices.",
          "delivery": "API, web, miniapp, plugin, MCP, rollout, activation, and all other implementation behavior.",
          "design": "Clarification, confirmation, and other interaction behavior.",
          "product": "Product promises, goal availability, intent policy, route semantics, outcome metrics, and pilot choices.",
          "trust": "Profile collection, provenance, correction, deletion, retention, and privacy behavior."
        },
        "science_authority": [
          "evidence_applicability",
          "uncertainty",
          "claim_limits",
          "safety_scope"
        ]
      }
    },
    "strength_and_cross_training_evidence": {
      "applies_to": "scientific claims about strength and cycling cross-training",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.strength-and-cross-training-bounded-support"
      ],
      "value": {
        "cycling_evidence_is_bounded": true,
        "injury_prevention_established": false,
        "running_equivalence_established": false,
        "strength_evidence_is_bounded": true,
        "universal_dose_established": false
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:e0db9989e767f5f2bbc6ab858830427f60bd045e72a7cd46ed9e38a16b349bfb"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If accepted by digest-bound human review, this inactive Science decision would establish only evidence applicability, uncertainty, claim limits, and safety scope. Novice and first-completion populations are a distinct evidence and applicability family from history-rich performance populations; the evidence establishes neither a universal schedule nor a permanent identity. Sparse or missing records do not prove cessation or detraining, and detraining evidence does not establish a universal restart dose. Age is relevant context, but the evidence establishes no universal age exclusion, cutoff, or fixed recovery delay. Evidence concerning physiological sex, reproductive context, menopause, transgender and nonbinary people, and gender identity is construct-specific and validates neither a general plan family nor a universal dose rule. Strength and cycling evidence is bounded and does not establish injury prevention, running equivalence, or a universal dose. The scope remains adult and nonclinical, and historical intensity evidence must use splits or samples rather than activity-average power. All exact values remain not_accepted. Product promises, route semantics, interaction and profile-data behavior, system architecture, metrics, implementation, pilot, rollout, and activation are outside Science authority and remain deferred to linked Product, Design, Trust, Architecture, and Delivery decisions.",
  "affected_surfaces": {
    "apis": [],
    "clients": [],
    "models": [
      "Science evidence applicability and claim-limit contract",
      "Science-only human decision sheet"
    ],
    "science_notes": [
      "First-completion applicability and permanent-identity limits",
      "Missing-record and detraining inference limits",
      "Age, profile-construct, strength, and cycling claim limits"
    ]
  },
  "applicability": [
    "Adult nonclinical recreational running-plan evidence and applicability review",
    "Novice and first-completion, sparse-history, masters, profile-construct, strength, and cycling evidence",
    "Scientific claim limits and exact-value uncertainty only"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-08-16",
  "decision_notes": [
    "This artifact-mode Science decision addresses issue #689 and remains draft and inactive.",
    "The Evidence Review is immutable in this iteration and remains bound to approved digest sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8.",
    "Product, Design, Trust, Architecture, and Delivery outputs are structured handoffs for later human review; this iteration creates none of those records or schemas.",
    "Implementation impact map: this SDR, its generated decision packet and machine contract, the regenerated evidence packet and registry index, and targeted deterministic tests only; runtime and accepted upstream science remain unchanged."
  ],
  "decision_review": {
    "approval_statement": "I approve only these inactive scientific boundaries: first-completion applicability is distinct from history-rich performance applicability; sparse or missing records do not prove cessation or detraining; age is relevant without establishing a universal exclusion, cutoff, or fixed recovery delay; sex, reproductive, menopause, transgender/nonbinary, and gender evidence remains construct-specific; strength and cycling evidence remains bounded; and scope remains adult, nonclinical, and split-level for intensity. I agree that all exact values remain not_accepted and that every Product, Design, Trust, Architecture, implementation, pilot, rollout, and activation decision remains outside Science authority and deferred to a linked decision with human review. This approval would not implement or activate behavior.",
    "items": [
      {
        "approval_effect": [
          "The scientific contract records a distinct evidence and applicability family.",
          "Universal schedules and permanent identities remain unsupported."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A universal schedule or permanent identity claim."
        ],
        "evidence_claim_ids": [
          "eligibility.novice-recreational-different-evidence-family",
          "population.beginner-evidence-family-not-permanent-identity",
          "population.no-universal-beginner-schedule"
        ],
        "id": "first-completion-applicability",
        "parameter_names": [
          "first_completion_applicability"
        ],
        "proposed_decision": "Yes. Treat novice and first-completion evidence as a distinct applicability family. The reviewed evidence establishes neither one universal schedule nor a permanent beginner identity.",
        "question": "Does the evidence distinguish novice and first-completion applicability from history-rich performance applicability without establishing a universal schedule or permanent identity?",
        "title": "Bound first-completion applicability"
      },
      {
        "approval_effect": [
          "Record missingness remains insufficient evidence of cessation or detraining.",
          "No universal restart dose is scientifically accepted."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A cessation or detraining conclusion from missingness or a universal restart dose."
        ],
        "evidence_claim_ids": [
          "eligibility.recent-history-anchor-without-universal-threshold",
          "population.sparse-history-not-detraining-proof",
          "population.no-universal-returning-dose"
        ],
        "id": "history-detraining-inference",
        "parameter_names": [
          "history_and_detraining_inference"
        ],
        "proposed_decision": "No. Sparse or missing records do not prove cessation or detraining. Detraining evidence does not establish a universal restart dose.",
        "question": "Do sparse or missing records establish cessation or detraining, and does detraining evidence establish one restart dose?",
        "title": "Limit history and detraining inference"
      },
      {
        "approval_effect": [
          "Age remains scientifically relevant context.",
          "Universal age exclusions, cutoffs, and fixed recovery delays remain unsupported."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A universal exclusion, cutoff, or fixed recovery claim based on age."
        ],
        "evidence_claim_ids": [
          "eligibility.masters-age-change-not-automatic-exclusion",
          "population.masters-context-not-age-exclusion",
          "population.masters-recovery-not-fixed-delay"
        ],
        "id": "masters-applicability",
        "parameter_names": [
          "masters_applicability"
        ],
        "proposed_decision": "No. Age is relevant context, but the reviewed evidence establishes no universal age exclusion, biological cutoff, or fixed recovery delay.",
        "question": "Does age establish a universal exclusion, cutoff, or fixed recovery delay for adult running plans?",
        "title": "Bound masters applicability"
      },
      {
        "approval_effect": [
          "Scientific claims remain tied to the construct actually studied.",
          "General profile-based plan families and universal dose rules remain unsupported."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Combining distinct constructs into a general family or universal dose claim."
        ],
        "evidence_claim_ids": [
          "population.sex-effects-are-construct-specific",
          "population.no-general-sex-or-gender-plan-family"
        ],
        "id": "construct-specific-profile-evidence",
        "parameter_names": [
          "construct_specific_profile_evidence"
        ],
        "proposed_decision": "No. These are distinct constructs with construct-specific evidence. The review validates neither a general plan family nor a universal dose rule for any combined profile category.",
        "question": "Does evidence about sex, reproductive context, menopause, transgender/nonbinary populations, or gender identity validate a general plan family or universal dose rule?",
        "title": "Keep profile evidence construct-specific"
      },
      {
        "approval_effect": [
          "Strength and cycling claims remain within the reviewed evidence.",
          "Injury prevention, equivalence, and universal dose remain unsupported."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "An injury-prevention, running-equivalence, or universal-dose claim."
        ],
        "evidence_claim_ids": [
          "population.strength-and-cross-training-bounded-support"
        ],
        "id": "strength-cross-training-evidence",
        "parameter_names": [
          "strength_and_cross_training_evidence"
        ],
        "proposed_decision": "No. Strength and cycling evidence is bounded. It does not establish an injury-prevention guarantee, running equivalence, or a universal dose.",
        "question": "Does the reviewed strength or cycling evidence establish injury prevention, equivalence to running, or a universal dose?",
        "title": "Bound strength and cross-training evidence"
      },
      {
        "approval_effect": [
          "The scientific applicability boundary remains adult and nonclinical.",
          "The split-level power invariant remains explicit."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Medical or pediatric guidance, a safety guarantee, or any runtime response."
        ],
        "evidence_claim_ids": [],
        "id": "adult-nonclinical-scope",
        "parameter_names": [
          "adult_nonclinical_scope"
        ],
        "proposed_decision": "Yes. Pediatric planning, diagnosis, treatment, rehabilitation, pregnancy-specific prescription, clearance, and return-to-sport remain outside scope. Activity-average power is not valid intensity evidence; use activity splits or samples.",
        "question": "Should this evidence decision remain limited to adult nonclinical planning and split- or sample-level intensity evidence?",
        "title": "Preserve adult nonclinical scope"
      },
      {
        "approval_effect": [
          "Every listed exact value remains visibly unresolved.",
          "Future values require separately reviewed evidence and decisions."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Inferring, defaulting, or implementing any exact value."
        ],
        "evidence_claim_ids": [
          "population.no-universal-beginner-schedule",
          "population.no-universal-returning-dose",
          "population.masters-recovery-not-fixed-delay",
          "population.strength-and-cross-training-bounded-support",
          "population.no-general-sex-or-gender-plan-family"
        ],
        "id": "all-exact-values",
        "parameter_names": [
          "exact_values"
        ],
        "proposed_decision": "Yes. Keep every exact value literal not_accepted. Study protocols, common practice, another population, prose, or AI output do not supply a universal value.",
        "question": "Should every exact schedule, threshold, restart, age, recovery, profile, strength, and cycling value remain unaccepted?",
        "title": "Defer all exact values"
      },
      {
        "approval_effect": [
          "The Science contract remains limited to evidence, uncertainty, claim limits, and safety scope.",
          "Later role-owned outputs remain explicit structured handoffs."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Any Product, Design, Trust, Architecture, Delivery, pilot, rollout, activation, or runtime choice."
        ],
        "evidence_claim_ids": [],
        "id": "all-non-science-decisions",
        "parameter_names": [
          "non_science_authority_boundary"
        ],
        "proposed_decision": "Yes. Defer Product promises, goal and intent behavior, route semantics, metrics, and pilot choices; Design clarification and confirmation experiences; Trust profile-data and privacy behavior; Architecture feedback-system and contract choices; and Delivery implementation, client behavior, rollout, and activation. Each requires its own linked decision and human review.",
        "question": "Should Product, Design, Trust, Architecture, implementation, pilot, rollout, and activation decisions remain outside this Science record?",
        "title": "Defer all non-Science decisions"
      }
    ],
    "reviewer_task": "Review the six scientific applicability boundaries and the two explicit deferrals below. Approve the sheet as a unit or request changes by item ID. Do not treat this Science review as a Product, Design, Trust, Architecture, Delivery, pilot, rollout, or activation decision."
  },
  "evidence_claim_ids": [
    "eligibility.novice-recreational-different-evidence-family",
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.masters-age-change-not-automatic-exclusion",
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
    "The Science contract selects a Product promise, route result, goal or intent behavior, confirmation interaction, profile-data behavior, feedback-system choice, metric, implementation, pilot, rollout, or activation.",
    "Sparse or missing records are treated as proof of cessation or detraining.",
    "A universal age exclusion, cutoff, fixed recovery delay, general profile plan family, injury-prevention claim, or running-equivalence claim is presented as established.",
    "Any exact value differs from literal not_accepted.",
    "Activity-average power is accepted for intensity analysis.",
    "The generated contract becomes active or runtime behavior changes."
  ],
  "id": "sdr-adult-running-plan-population-routing-v1",
  "model_parameters": [
    {
      "applies_to": "scientific applicability for novice and first-completion evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.novice-recreational-different-evidence-family",
        "population.beginner-evidence-family-not-permanent-identity",
        "population.no-universal-beginner-schedule"
      ],
      "name": "first_completion_applicability",
      "rationale": "The evidence distinguishes applicability families without validating a universal schedule or permanent personal category.",
      "value": {
        "novice_and_first_completion_distinct_from_history_rich_performance": true,
        "permanent_identity_established": false,
        "universal_schedule_established": false
      }
    },
    {
      "applies_to": "scientific inference from sparse or missing training records",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "population.sparse-history-not-detraining-proof",
        "population.no-universal-returning-dose"
      ],
      "name": "history_and_detraining_inference",
      "rationale": "Missingness is not a known reduction or cessation exposure, and reviewed detraining studies do not validate one restart prescription.",
      "value": {
        "detraining_evidence_establishes_universal_restart_dose": false,
        "sparse_or_missing_records_establish_cessation": false,
        "sparse_or_missing_records_establish_detraining": false
      }
    },
    {
      "applies_to": "scientific applicability for masters and older adults",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "population.masters-context-not-age-exclusion",
        "population.masters-recovery-not-fixed-delay"
      ],
      "name": "masters_applicability",
      "rationale": "Age is relevant to population context, but the evidence does not establish a universal exclusion, cutoff, or fixed recovery delay.",
      "value": {
        "age_is_relevant_context": true,
        "fixed_age_based_recovery_delay_established": false,
        "universal_age_cutoff_established": false,
        "universal_age_exclusion_established": false
      }
    },
    {
      "applies_to": "scientific claims involving sex, reproductive, menopause, transgender/nonbinary, or gender constructs",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.sex-effects-are-construct-specific",
        "population.no-general-sex-or-gender-plan-family"
      ],
      "name": "construct_specific_profile_evidence",
      "rationale": "Construct-specific findings cannot be combined into a general profile category, plan family, or universal dose rule.",
      "value": {
        "constructs": [
          "physiological_sex",
          "reproductive_context",
          "menopause",
          "transgender_and_nonbinary",
          "gender_identity"
        ],
        "evidence_is_construct_specific": true,
        "general_plan_family_validated": false,
        "universal_dose_rule_validated": false
      }
    },
    {
      "applies_to": "scientific claims about strength and cycling cross-training",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.strength-and-cross-training-bounded-support"
      ],
      "name": "strength_and_cross_training_evidence",
      "rationale": "Reviewed strength and cycling evidence does not establish injury prevention, equivalence to running, or one universal dose.",
      "value": {
        "cycling_evidence_is_bounded": true,
        "injury_prevention_established": false,
        "running_equivalence_established": false,
        "strength_evidence_is_bounded": true,
        "universal_dose_established": false
      }
    },
    {
      "applies_to": "safety scope and historical intensity evidence",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "adult_nonclinical_scope",
      "rationale": "The decision is bounded to adult nonclinical planning and preserves the repository split-level power invariant.",
      "value": {
        "activity_average_power_valid_for_intensity": false,
        "adult_nonclinical_scope_only": true,
        "medical_or_rehabilitation_prescription_within_scope": false,
        "pediatric_planning_within_scope": false,
        "pregnancy_specific_prescription_within_scope": false,
        "valid_intensity_evidence_sources": [
          "activity_splits",
          "activity_samples"
        ]
      }
    },
    {
      "applies_to": "all exact values within this scientific topic",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "population.no-universal-beginner-schedule",
        "population.no-universal-returning-dose",
        "population.masters-recovery-not-fixed-delay",
        "population.strength-and-cross-training-bounded-support",
        "population.no-general-sex-or-gender-plan-family"
      ],
      "name": "exact_values",
      "rationale": "The evidence establishes boundaries and uncertainty, not universal behavior-driving values.",
      "value": {
        "age_based_recovery_delay": "not_accepted",
        "age_cutoff": "not_accepted",
        "cycling_substitution_ratio": "not_accepted",
        "first_completion_schedule": "not_accepted",
        "history_sufficiency_thresholds": "not_accepted",
        "restart_dose": "not_accepted",
        "sex_reproductive_menopause_or_gender_dose_rule": "not_accepted",
        "strength_dose": "not_accepted"
      }
    },
    {
      "applies_to": "authority and structured handoffs for later human-reviewed decisions",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "non_science_authority_boundary",
      "rationale": "Science constrains later decisions but cannot choose value, experience, privacy, architecture, implementation, pilot, rollout, or activation.",
      "value": {
        "required_future_handoffs": {
          "architecture": "Shared feedback-system and cross-domain contract choices.",
          "delivery": "API, web, miniapp, plugin, MCP, rollout, activation, and all other implementation behavior.",
          "design": "Clarification, confirmation, and other interaction behavior.",
          "product": "Product promises, goal availability, intent policy, route semantics, outcome metrics, and pilot choices.",
          "trust": "Profile collection, provenance, correction, deletion, retention, and privacy behavior."
        },
        "science_authority": [
          "evidence_applicability",
          "uncertainty",
          "claim_limits",
          "safety_scope"
        ]
      }
    }
  ],
  "model_version": "adult-running-plan-population-routing-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "The evidence establishes no universal profile-data prerequisite or default.",
    "Profile collection, provenance, correction, deletion, retention, and privacy behavior are outside Science authority and require linked Trust, Product, and Design decisions."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Collapse novice or first-completion evidence into history-rich performance evidence",
      "rationale": "The reviewed populations and applicability differ, while no universal schedule or permanent identity is established."
    },
    {
      "alternative": "Treat sparse or missing records as proven cessation or detraining",
      "rationale": "Record missingness does not establish the exposure studied in detraining research, and the evidence does not yield a universal restart dose."
    },
    {
      "alternative": "Use chronological age as a universal exclusion, cutoff, or recovery delay",
      "rationale": "Age is relevant context, but capability and recovery vary and no universal behavior-driving value was validated."
    },
    {
      "alternative": "Turn sex, reproductive, menopause, transgender/nonbinary, or gender evidence into one plan family",
      "rationale": "These are distinct constructs, and the evidence does not validate a general family or universal dose rule."
    },
    {
      "alternative": "Claim strength prevents injury or cycling is equivalent to running",
      "rationale": "The evidence supports only bounded conclusions and no universal dose, equivalence, or individual injury-prevention guarantee."
    },
    {
      "alternative": "Let Science choose the Product response or implementation",
      "rationale": "Evidence constrains later choices but does not own product promises, interaction, privacy, architecture, delivery, pilot, rollout, or activation decisions."
    }
  ],
  "safety_implications": [
    "This evidence decision is limited to adult nonclinical planning.",
    "Pediatric planning, diagnosis, treatment, rehabilitation, pregnancy-specific prescription, clearance, and return-to-sport are outside scope.",
    "Historical intensity evidence uses activity splits or samples, never activity-average power."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Bound scientific applicability for adult running-plan populations",
  "user_facing_claim_limits": [
    "Do not present novice or first-completion status as a permanent identity or claim one universal schedule.",
    "Do not claim sparse or missing records prove cessation, detraining, or a personal restart dose.",
    "Do not present a universal age exclusion, cutoff, or fixed recovery delay as established evidence.",
    "Do not generalize construct-specific sex, reproductive, menopause, transgender/nonbinary, or gender evidence into a plan family or dose rule.",
    "Do not claim strength prevents injury, cycling is equivalent to running, or either has a universal dose."
  ],
  "validation_plan": [
    "A digest-bound human reviewer must accept, revise, or reject this eight-item Science-only decision sheet.",
    "Verify the approved Evidence content digest remains sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8.",
    "Verify the machine contract contains the six scientific boundaries, literal not_accepted exact values, and no Product-owned behavior fields.",
    "Verify the two deferrals map later Product, Design, Trust, Architecture, and Delivery handoffs without creating their records or schemas.",
    "Verify generated packets, machine contract, and registry index are deterministic and runtime_state remains inactive."
  ],
  "version": 1
}
```

</details>
