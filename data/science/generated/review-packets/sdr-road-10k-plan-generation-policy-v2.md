# Science decision review packet: Generator-ready adult outdoor road 10 km performance policy

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-road-10k-plan-generation-policy-v2`
- **Lifecycle:** `accepted`
- **Model version:** `road-10k-plan-generation-policy-v2`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad`
- **Contract digest:** `sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496`
- **Required decision role:** `decision_approver`
- **Decision approval:** `github:dddtc2005` on `2026-08-18` ([source](https://github.com/praxys-run/praxys/pull/733#issuecomment-5327908194))
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Review the six proposed inactive policy decisions and the two explicit deferrals below. Approve the decision sheet as a unit or request changes by item ID. The exact contract is included in the audit appendix. This review does not approve implementation or runtime activation.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `supported-capability` — Accept the exact supported capability and readiness contract

- **Question:** Should V2 remain limited to the stated adult, currently capable, history-rich outdoor-road 10 km performance tuple and require the listed direct baseline, recent history, event, symptom, and constraint inputs?
- **Proposed decision:** Accept that exact tuple and its fail-closed input contract. Preserve every valid Goal when the policy does not match, and never manufacture eligibility from predictions, sparse records, another distance, a permanent runner label, or missing demographic context.
- **Approval means:**
  - The exact 10 km performance capability tuple becomes an accepted inactive decision input.
  - Missing, stale, contradictory, unsupported, and symptom-stop states remain typed non-success outcomes.
  - The predecessor and shared policy dependencies remain explicit.
- **This does not authorize:**
  - Any generator implementation, registry activation, plan adoption, or provider delivery.
  - First-completion, return-to-consistency, sparse-history, other-surface, or clinical planning.

<details><summary>Traceability: 4 contract groups, 6 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_activation_and_dependencies`, `road_10k_v2_capability_tuple`, `road_10k_v2_required_inputs`, `road_10k_v2_readiness_and_missingness`
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `eligibility.goal-relevant-current-capability-task-specific`, `eligibility.current-symptoms-support-stop-not-clearance`, `population.sparse-history-not-detraining-proof`, `road-10k-baseline.same-distance-direct-capability`, `road-10k-baseline.freshness-cutoff-not-validated`

</details>

#### `rolling-execution` — Accept the fourteen-day rolling execution contract

- **Question:** Should the first generator commit fourteen days, show an advisory reassessment after seven completed days, and require explicit adoption before a successor changes future adopted days?
- **Proposed decision:** Accept fourteen days as the minimum valuable reversible product window and seven days as an advisory review cadence. Treat both as operational guardrails rather than physiological claims.
- **Approval means:**
  - Dated and undated goals may receive a bounded rolling proposal.
  - Material changes can produce a successor candidate without silently overwriting adopted days.
- **This does not authorize:**
  - Automatic progression, automatic successor adoption, or a claim that fourteen or seven days is biologically optimal.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_execution_window_and_reassessment`
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `road-10k-plan.volume-frequency-associated-not-prescriptive`, `road-10k-plan.individual-outcomes-require-error-aware-validation`

</details>

#### `deterministic-schedule` — Accept the initial deterministic schedule and templates

- **Question:** Should V2 use one quality session in each seven-day unit, history-capped easy running, at least seventy-five percent low-intensity minutes, and the exact two versioned 10 km quality templates?
- **Proposed decision:** Accept the simplest useful schedule: one quality session per week, alternating threshold and 10 km interval templates across a normal fourteen-day proposal, with all duration and load bounded by recent completed history and athlete-stated constraints.
- **Approval means:**
  - A future deterministic generator has complete schedule, allocation, intensity, spacing, and template inputs.
  - Exact template IDs and steps become reviewable guardrails with deterministic replay.
- **This does not authorize:**
  - Describing the templates as evidence-backed optima.
  - Copying 5 km templates, adding a second planned quality session, or exceeding history and constraint caps.

<details><summary>Traceability: 3 contract groups, 5 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_schedule_construction`, `road_10k_v2_workout_templates`, `road_10k_v2_intensity_quality_and_spacing`
- **Evidence claims:** `road-10k-plan.task-specific-capability-not-single-marker`, `road-10k-plan.mostly-low-intensity-no-universal-winner`, `road-10k-plan.one-to-two-quality-sessions-indirect`, `road-10k-plan.volume-frequency-associated-not-prescriptive`, `road-10k-plan.fixed-progression-not-safety-law`

</details>

#### `event-and-taper` — Accept bounded event, benchmark, and taper routing

- **Question:** Should full proposals remain limited to confirmed-none and single-target event states, use the accepted indirect taper range for a confirmed primary event eight to fourteen days away, and return limited guidance for race-dense or shorter-horizon cases?
- **Proposed decision:** Accept that boundary. Never auto-schedule a benchmark, treat every race or maximal effort as quality and load, and stop the generated schedule before the event.
- **Approval means:**
  - Undated goals can roll without a forced benchmark.
  - A confirmed primary event may receive one deterministic taper path.
  - Race-dense and very short horizons remain fail-closed.
- **This does not authorize:**
  - Automatic event confirmation or priority, race-dense optimization, or a promised taper benefit.

<details><summary>Traceability: 1 contract group, 3 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_event_benchmark_and_taper`
- **Evidence claims:** `road-10k-plan.taper-volume-reduction-supported`, `road-10k-baseline.same-distance-direct-capability`, `road-10k-plan.one-to-two-quality-sessions-indirect`

</details>

#### `hard-boundaries` — Accept honest outcomes and hard control boundaries

- **Question:** Should the generator preserve typed non-success outcomes, avoid demographic modifiers and personal probabilities, require explicit adoption, constrain AI to explanation, and record only minimized replay and audit data?
- **Proposed decision:** Accept those boundaries. Unknown age beyond adult confirmation, sex, gender, reproductive context, symptoms, events, and constraints may not be defaulted or inferred into eligibility or dose.
- **Approval means:**
  - Runtime outcomes remain honest and deterministic.
  - Consent, privacy, missingness, and AI authority remain bounded.
- **This does not authorize:**
  - Medical inference, sensitive-trait inference, personal success or injury probability, auto-adoption, or content logging.

<details><summary>Traceability: 4 contract groups, 7 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_typed_outcomes`, `road_10k_v2_demographic_and_claim_limits`, `road_10k_v2_consent_ai_and_state`, `road_10k_v2_privacy_and_audit`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `eligibility.masters-age-change-not-automatic-exclusion`, `population.masters-context-not-age-exclusion`, `population.sex-effects-are-construct-specific`, `population.no-general-sex-or-gender-plan-family`, `road-10k-plan.individual-outcomes-require-error-aware-validation`, `road-10k-plan.symptom-based-test-stop-boundary`

</details>

#### `evaluation-gates` — Accept the predeclared runtime evaluation gates

- **Question:** Should dry-run and opt-in rollout pause or revisit the policy when the stated deterministic, exclusion, edit, taper, subgroup, symptom, benchmark, or serious-event thresholds are crossed?
- **Proposed decision:** Accept the thresholds as reversible pilot decision rules. They do not establish efficacy or medical safety.
- **Approval means:**
  - Runtime learning has explicit pause and revision triggers before activation.
  - Cross-capability learning can be compared without success-shaped interpretation.
- **This does not authorize:**
  - A claim that the policy improves performance, prevents injury, or is safe for an individual.

<details><summary>Traceability: 1 contract group, 2 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_runtime_evaluation`
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-10k-plan.individual-outcomes-require-error-aware-validation`

</details>

### Decisions explicitly deferred

#### `broader-capabilities` — Defer broader dose, population, and automation choices

- **Question:** Should two-quality weeks, progression, mandatory long runs, race-dense optimization, other populations, exact power or pace targets, automatic benchmarks, personal probabilities, and AI planning authority remain unaccepted?
- **Proposed decision:** Yes. Keep every listed capability explicitly not accepted until its own evidence, Product rationale, science decision, and review are complete.
- **Approval means:**
  - The contract exposes rather than hides every deferred capability.
  - Implementation cannot infer a deferred value from V1, 5 km behavior, prose, or AI output.
- **This does not authorize:**
  - Any deferred capability or fallback policy.

<details><summary>Traceability: 1 contract group, 4 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_deferred_scope`
- **Evidence claims:** `road-10k-plan.one-to-two-quality-sessions-indirect`, `road-10k-plan.volume-frequency-associated-not-prescriptive`, `road-10k-plan.fixed-progression-not-safety-law`, `road-10k-plan.individual-outcomes-require-error-aware-validation`

</details>

#### `implementation-and-activation` — Defer implementation and runtime activation

- **Question:** Should generator code, API and client behavior, capability registration, rollout, adoption, and delivery remain outside this science approval?
- **Proposed decision:** Yes. Keep the generated contract inactive. Require separate implementation review bound to the exact code diff and validation evidence before any activation.
- **Approval means:**
  - Science acceptance remains separate from implementation and activation.
- **This does not authorize:**
  - Code changes, runtime availability, plan adoption, provider delivery, or publication.

<details><summary>Traceability: 1 contract group, 0 evidence claims</summary>

- **Contract groups covered:** `road_10k_v2_implementation_and_activation`
- **Evidence claims:** _None; product or lifecycle boundary only_

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> I approve this inactive road 10 km performance policy as one bounded generator contract: the history-rich adult outdoor-road scope and typed readiness inputs; a fourteen-day committed proposal with a seven-day advisory reassessment and explicit successor adoption; one quality session per seven-day unit using the exact versioned 10 km templates; confirmed-none and single-target event handling with a bounded taper and race-dense limited guidance; the stated claim, demographic, consent, AI, privacy, and audit limits; and the predeclared runtime evaluation gates. I agree that broader dose, race-density, population, targeting, automation, and activation choices remain deferred. I understand that every exact schedule and template value is a Praxys guardrail rather than a published optimum, and that this approval does not implement or activate behavior.

- **Decision approval:** `github:dddtc2005` on `2026-08-18` ([source](https://github.com/praxys-run/praxys/pull/733#issuecomment-5327908194))

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-road-10k-plan-generation-policy-v2`
- Digest: `sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad`

> I approve this inactive road 10 km performance policy as one bounded generator contract: the history-rich adult outdoor-road scope and typed readiness inputs; a fourteen-day committed proposal with a seven-day advisory reassessment and explicit successor adoption; one quality session per seven-day unit using the exact versioned 10 km templates; confirmed-none and single-target event handling with a bounded taper and race-dense limited guidance; the stated claim, demographic, consent, AI, privacy, and audit limits; and the predeclared runtime evaluation gates. I agree that broader dose, race-density, population, targeting, automation, and activation choices remain deferred. I understand that every exact schedule and template value is a Praxys guardrail rather than a published optimum, and that this approval does not implement or activate behavior.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad","subject_id":"sdr-road-10k-plan-generation-policy-v2","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

If accepted by a digest-bound human decision approver, this SDR would supersede the accepted but generator-incomplete V1 boundary with one inactive, generator-ready policy for adult outdoor-road 10 km performance intent. The supported pattern remains currently capable, history-rich, within-recent load, and free of current symptom-stop inputs. A deterministic proposal would commit fourteen athlete-local calendar days, present an advisory reassessment after seven completed days, and require explicit adoption before any successor replaces future adopted days. The initial schedule would use one quality session in each seven-day unit, never exceed recent typical load or athlete-stated constraints, preserve at least seventy-five percent low-intensity running minutes, and use only the two versioned 10 km quality templates defined here. Confirmed-none and single-target event states could receive a full proposal; race-dense, unsupported, stale, missing, contradictory, or symptom-stop states would fail closed to typed readiness, clarification, limited-guidance, or unavailable outcomes. The fourteen-day window, seven-day advisory cadence, one-quality choice, exact template steps, allocation rules, and pilot thresholds are transparent Praxys product guardrails, not published optima. This decision would not implement or activate a generator, adopt or deliver a plan, schedule a benchmark automatically, create a personal probability, or authorize first-completion, return-to-consistency, sparse-history, clinical, trail, marathon, or ultra planning.

### Linked evidence

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

#### `population.sparse-history-not-detraining-proof` — moderate

Detraining is defined and studied as a known reduction or cessation of training. Sparse, missing, or provider-limited Praxys records do not by themselves establish that training stopped, how much capacity changed, or whether the runner is returning.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `zheng-2022`, `barbieri-2023`
- **Limitations:** The product conclusion about record missingness is an epistemic guardrail, not a tested intervention.; The reviews are not studies of consumer data completeness or provider outages.; Self-reported interruption may still require clarification about partial versus complete training.

#### `population.masters-context-not-age-exclusion` — moderate

Endurance performance and VO2max generally decline with age, while masters athletes retain high capability and changes in training volume explain substantial variation in observed decline. Chronological age is therefore relevant context but does not establish a universal exclusion, a fixed masters cutoff, or a separate base plan family.

- **Evidence Review:** `evidence-adult-running-plan-population-routing-v1`
- **Sources:** `tanaka-2008`, `burtscher-2022`, `vangsgaard-2026`
- **Limitations:** Reviews include highly trained athletes and cannot define a recreational automatic-plan adjustment.; Observational associations with training volume do not prove an optimal dose.; Published masters definitions often use age 35 or 40 for study or competition administration, not a biological threshold.; Women masters evidence is sparse and mostly cross-sectional.

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

#### `road-10k-plan.task-specific-capability-not-single-marker` — low

Ten-kilometre performance is related to sustainable threshold-associated running speed and interacting aerobic determinants, but no single marker defines an individual 10 km plan. This supports a 10 km-specific task and baseline contract while rejecting automatic transfer from a 5 km policy or a single physiological estimate.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `kumagai-1982`, `stoa-2020`
- **Limitations:** The Kumagai cohort included minors and cannot directly authorize an adult product policy.; Neither study tested an automatic plan generator or exact workout prescription.; Threshold percentage alone did not determine threshold velocity in the adult study.; The sources do not establish a 5 km-to-10 km conversion or one causal training target.

#### `road-10k-plan.mostly-low-intensity-no-universal-winner` — moderate

The reviewed direct and broader endurance evidence supports a majority of training at low intensity and does not establish one universally superior polarized, focused, pyramidal, or threshold distribution for recreational 10 km performance.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `munoz-2014`, `festa-2020`, `campos-2022`, `oliveira-2024`
- **Limitations:** Studies used different zone definitions, interventions, and outcomes.; The direct 10 km controlled study did not establish a significant universal winner.; The evidence does not validate one exact percentage for every athlete.; The focused-training study used a 2 km performance outcome rather than 10 km.

#### `road-10k-plan.one-to-two-quality-sessions-indirect` — low

A narrative review of recreational endurance running generally recommends one to two high-intensity interval sessions per week with more moderate- and low-intensity continuous running. This is indirect support for a conservative 10 km product ceiling, not a universal biological threshold.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `boullosa-2020`
- **Limitations:** The source is a narrative review with heterogeneous studies.; It does not compare exactly one versus two sessions for 10 km outcomes.; It does not define spacing, duration, taxonomy, or a safety threshold.

#### `road-10k-plan.volume-frequency-associated-not-prescriptive` — low

Weekly training distance, training frequency, training duration, and prior race experience are associated with recreational 10 km performance, but the reviewed evidence is observational and does not establish universal weekly dose, frequency, or mandatory long-run prescriptions.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `suwankan-2024`, `vickers-2016`
- **Limitations:** Associations do not establish causation or an individual prescription.; Self-selection, prior fitness, and training experience can confound the findings.; The evidence supplies no safe weekly kilometres, minutes, frequency range, or long-run percentage.; The dedicated long-run search found no direct randomized recreational 10 km prescription trial.

#### `road-10k-plan.fixed-progression-not-safety-law` — moderate

A novice-running program based on the 10 percent rule did not reduce running-related injury compared with a standard program, and acute-to- chronic workload-ratio zones lack established causal support for individual training recommendations. Neither should govern a 10 km plan as a safety law.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `buist-2008`, `impellizzeri-2020`
- **Limitations:** The trial does not show that every faster progression is safe.; Injury outcomes do not define optimal 10 km performance progression.; The critique does not make training history irrelevant or validate a replacement threshold.

#### `road-10k-plan.taper-volume-reduction-supported` — moderate

Across mixed endurance sports, tapering can improve time-trial performance. The strongest reviewed strategy reduced volume by 41 to 60 percent while maintaining intensity and frequency; 8 to 14 days produced the largest duration subgroup effect, with improvement also reported for other durations up to 21 days.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `wang-2023`
- **Limitations:** Sports, performance levels, and event distances were mixed.; The analysis does not validate a universal recreational 10 km taper.; Taper effects depend on prior training and interactions among load variables.

#### `road-10k-baseline.same-distance-direct-capability` — moderate

A qualified same-distance 10 km race or intentional all-out effort is the most task-direct current-capability evidence. Fixed-distance time trials are generally more reliable than time-to-exhaustion tests, and one amateur-runner study found good agreement and reproducibility among a simulated 10 km track time trial, threshold-derived speeds, and official 10 km race speed.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `currell-2008`, `laursen-2007`, `ribeiro-2020`
- **Limitations:** Agreement does not make every road race and solo time trial interchangeable.; Threshold-derived speeds remain supporting rather than direct elapsed-time evidence.; The studies do not define Praxys qualification metadata, freshness, or automatic equivalence.

#### `road-10k-baseline.freshness-cutoff-not-validated` — low

Some cardiorespiratory and endurance adaptations can change during fewer than four weeks of insufficient training, with outcome- and training- status-dependent timing and magnitude. This does not validate a universal 28-, 42-, 56-, or other fixed-day 10 km baseline-expiry cutoff.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `mujika-2000`
- **Limitations:** The review is narrative and trained athletes are overrepresented.; Training gain, detraining, illness, and contextual change need not follow the same time course.; A bounded search cannot establish that no protocol-specific freshness evidence exists.

#### `road-10k-plan.individual-outcomes-require-error-aware-validation` — moderate

Group-average training effects cannot establish an individual 10 km response, goal-achievement probability, or meaningful change without accounting for measurement error, within-person variability, and a predeclared protocol-specific worthwhile-change rule.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `bonafiglia-2021`
- **Limitations:** The review was not a 10 km plan or prediction study.; It supplies no target, progression, session-count, or probability threshold.

#### `road-10k-plan.symptom-based-test-stop-boundary` — low

Current signs and symptoms are relevant before vigorous exercise. This supports a conservative stop before an optional maximal 10 km test or vigorous plan path, but does not validate diagnosis, treatment, clearance, or return-to-sport advice.

- **Evidence Review:** `evidence-road-10k-plan-generation-policy-v1`
- **Sources:** `riebe-2015`
- **Limitations:** The guidance is not a validation study of a self-administered 10 km test.; Passing a screen does not make maximal exercise risk-free.; Praxys-specific wording and routing remain product guardrails.

### Reviewed parameters

#### `road_10k_v2_activation_and_dependencies` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** V2 is a proposed successor contract, not runtime authority. Acceptance, implementation review, capability registration, and rollout are separate gates.
- **Exact value:**

```json
{
  "active_behavior": false,
  "capability_registry_entry_default_enabled": false,
  "decision_approval_artifact_required": true,
  "implementation_approval_artifact_required_before_activation": true,
  "linked_evidence_required_status": "accepted",
  "predecessor_decision": {
    "proposed_lifecycle_after_v2_acceptance": "superseded",
    "required_status_before_v2_acceptance": "accepted",
    "sdr_id": "sdr-road-10k-plan-generation-policy-v1"
  },
  "shared_dependencies": [
    {
      "required_status": "accepted",
      "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
    },
    {
      "required_status": "accepted",
      "sdr_id": "sdr-adult-running-plan-population-routing-v1"
    }
  ]
}
```

#### `road_10k_v2_capability_tuple` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `road-10k-plan.task-specific-capability-not-single-marker`
- **Rationale:** The tuple matches one evidence and Product slice rather than distance alone. A valid Goal remains recorded when the tuple does not match.
- **Exact value:**

```json
{
  "activity_types": [
    "running"
  ],
  "adult_scope": "confirmed",
  "capability_id": "outdoor_road_10k_performance_v1",
  "capability_pattern": "currently_capable",
  "current_symptoms": "absent",
  "discipline": "running",
  "distance": "10k",
  "distance_m": 10000,
  "goal_kinds": [
    "performance_10k"
  ],
  "history_pattern": "stable",
  "load_pattern": "within_recent",
  "permanent_runner_identity_used": false,
  "plan_intent": "performance",
  "primary_outcome": "elapsed_time",
  "race_dense_full_proposal_supported": false,
  "supported_event_states": [
    "confirmed_none",
    "single_target"
  ],
  "supported_purpose_sources": [
    "current_goal",
    "capability"
  ],
  "surface": "outdoor_road",
  "target_date_optional": true,
  "target_time_optional": true,
  "unlinked_purpose_supported": false
}
```

#### `road_10k_v2_required_inputs` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `road-10k-baseline.same-distance-direct-capability`, `road-10k-plan.volume-frequency-associated-not-prescriptive`
- **Rationale:** These fields make the accepted history-rich pattern replayable while minimizing private context. Exact history counts remain product guardrails rather than published eligibility thresholds.
- **Exact value:**

```json
{
  "conditional_versioned_inputs": [
    "active_athlete_zone_model_id_and_version"
  ],
  "constraint_schema_id": "outdoor_road_10k_constraints_v1",
  "direct_baseline_required_metadata": [
    "completed_at",
    "elapsed_time_seconds",
    "distance_m",
    "surface_or_protocol",
    "route_or_venue_identifier",
    "intentional_all_out_or_race_flag",
    "assistance_status",
    "source_provider"
  ],
  "free_text_narrative_required": false,
  "historical_intensity_source_priority": [
    "activity_splits",
    "activity_samples"
  ],
  "latest_run_within_completed_days": 10,
  "minimum_runs_per_usable_week": 3,
  "minimum_usable_completed_weeks": 4,
  "prohibited_historical_intensity_source": [
    "activity_avg_power"
  ],
  "recent_history_lookback_completed_weeks": 8,
  "required_versioned_inputs": [
    "policy_version",
    "science_decision_id",
    "contract_digest",
    "generator_version",
    "athlete_local_today",
    "proposal_start_date",
    "plan_purpose_source",
    "source_goal_id_and_revision_when_current_goal",
    "normalized_goal",
    "adult_scope_confirmation",
    "current_symptom_stop_state",
    "direct_10k_baseline_snapshot",
    "recent_completed_running_history",
    "current_training_pattern_snapshot",
    "confirmed_event_context_snapshot",
    "available_running_weekdays",
    "athlete_stated_weekly_time_limit",
    "athlete_stated_single_session_time_limit",
    "unavailable_dates",
    "preferred_longest_easy_weekday_if_any"
  ]
}
```

#### `road_10k_v2_readiness_and_missingness` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.current-symptoms-support-stop-not-clearance`, `population.sparse-history-not-detraining-proof`, `road-10k-baseline.same-distance-direct-capability`, `road-10k-baseline.freshness-cutoff-not-validated`, `road-10k-plan.symptom-based-test-stop-boundary`
- **Rationale:** Same-distance evidence is most direct, but the freshness boundary and optional test workflow are explicit reversible guardrails. Missingness cannot be reinterpreted as detraining or eligibility.
- **Exact value:**

```json
{
  "accepted_direct_baseline_order": [
    "organized_outdoor_road_10k_race_with_elapsed_time",
    "explicit_all_out_standardized_outdoor_road_or_track_10k_time_trial"
  ],
  "adult_scope_unconfirmed_result": "clarification_required",
  "baseline_current_through_completed_days": 56,
  "baseline_stale_from_completed_days": 57,
  "contradictory_constraints_result": "clarification_required",
  "current_symptom_stop_result": "safety_stop",
  "excluded_as_direct_baseline": [
    "five_k_result_or_conversion",
    "race_prediction",
    "passive_fastest_10k_split",
    "threshold_or_lactate_speed_alone",
    "critical_power_or_critical_velocity_alone",
    "activity_average_power",
    "vendor_readiness_or_race_score"
  ],
  "missing_or_stale_baseline_result": "readiness_only",
  "missing_or_stale_history_result": "readiness_only",
  "optional_baseline_test": {
    "automatic_scheduling": false,
    "explicit_athlete_choice_required": true,
    "no_test_alternative": "remain_readiness_only",
    "shared_safety_eligibility_required": true
  },
  "sparse_or_missing_records_establish_detraining": false,
  "unsupported_distance_surface_or_intent_result": "policy_unavailable"
}
```

#### `road_10k_v2_execution_window_and_reassessment` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.recent-history-anchor-without-universal-threshold`, `road-10k-plan.volume-frequency-associated-not-prescriptive`, `road-10k-plan.individual-outcomes-require-error-aware-validation`
- **Rationale:** No reviewed source validates an exact execution window. Fourteen days is the Product-selected minimum complete two-unit experience; seven days is an advisory review point. Both remain falsifiable workflow guardrails.
- **Exact value:**

```json
{
  "advisory_reassessment_after_completed_days": 7,
  "automatic_overwrite_of_adopted_future_days": false,
  "automatic_successor_adoption": false,
  "biological_optimum_claim": false,
  "calendar_schedule_unit_days": 7,
  "committed_proposal_days": 14,
  "dated_goal_planning_horizon": "through_confirmed_primary_event",
  "each_successor_requires": [
    "fresh_eligibility_evaluation",
    "updated_completed_history",
    "updated_event_context",
    "updated_training_pattern_snapshot",
    "explicit_review_and_adoption"
  ],
  "fixed_goal_horizon_required": false,
  "no_automatic_progression_between_reassessments": true,
  "proposal_end_inclusive": true,
  "successor_candidate_triggers": [
    "seven_completed_days",
    "new_or_changed_confirmed_event",
    "material_training_pattern_change",
    "new_qualified_10k_baseline",
    "changed_availability_or_constraint",
    "athlete_requested_review"
  ],
  "undated_goal_planning_horizon": "rolling_until_athlete_changes_or_ends_goal"
}
```

#### `road_10k_v2_schedule_construction` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `road-10k-plan.one-to-two-quality-sessions-indirect`, `road-10k-plan.volume-frequency-associated-not-prescriptive`, `road-10k-plan.fixed-progression-not-safety-law`
- **Rationale:** One quality session per week is a conservative Product choice within the indirect one-to-two ceiling. Median, maximum, and constraint caps prevent the first generator from prescribing progression above observed dose.
- **Exact value:**

```json
{
  "below_minimum_result": "readiness_only",
  "easy_and_longest_easy_allocation": {
    "automatic_longest_easy_increase": false,
    "integer_remainder_priority": [
      "preferred_longest_easy_day",
      "chronological_day_order"
    ],
    "longest_easy_designation_optional": true,
    "quality_template_minutes_are_allocated_first": true,
    "remaining_minutes_distributed_evenly_across_non_quality_runs": true
  },
  "event_or_benchmark_replaces_planned_quality_in_same_unit": true,
  "no_schedule_result": "readiness_only_no_schedule_within_envelope",
  "non_taper_progression_above_recent_median": false,
  "normal_two_unit_quality_order": {
    "first_unit": "controlled_threshold_quality",
    "second_unit": "ten_k_specific_interval_quality"
  },
  "quality_sessions_per_7_day_unit": 1,
  "requested_above_maximum_result": "clarification_required",
  "schedule_must_satisfy_all_history_constraint_intensity_and_spacing_rules": true,
  "selected_running_days_per_7_day_unit": {
    "deterministic_value": "minimum_of_available_days_recent_modal_days_and_policy_maximum",
    "maximum": 6,
    "minimum": 3
  },
  "session_distance_hard_cap": "recent_maximum_completed_session_distance",
  "session_duration_hard_cap": "minimum_of_recent_maximum_completed_session_minutes_and_athlete_stated_session_limit",
  "target_time_gap_may_raise_load": false,
  "weekly_running_minutes_hard_cap": "minimum_of_recent_maximum_usable_weekly_minutes_and_athlete_stated_weekly_limit",
  "weekly_running_minutes_target": "minimum_of_recent_median_usable_weekly_minutes_and_athlete_stated_weekly_limit"
}
```

#### `road_10k_v2_workout_templates` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `road-10k-plan.task-specific-capability-not-single-marker`, `road-10k-plan.one-to-two-quality-sessions-indirect`, `road-10k-plan.mostly-low-intensity-no-universal-winner`
- **Rationale:** The reviewed literature supports broad quality-session families but does not validate these exact repeats or recoveries. The templates are transparent, versioned Product guardrails chosen for deterministic implementation and prospective evaluation.
- **Exact value:**

```json
{
  "easy_template": "duration_only",
  "generic_five_k_or_ten_k_pace_conversion": false,
  "generic_percent_of_threshold_or_critical_power": false,
  "inherited_from_outdoor_5k": false,
  "longest_easy_template": "duration_only",
  "target_expression_priority": [
    "current_athlete_specific_active_zone_model",
    "duration_and_session_type_only"
  ],
  "template_must_fit_session_and_weekly_caps": true,
  "template_optimum_claim": false,
  "templates": [
    {
      "steps": [
        {
          "duration_minutes": 10,
          "intended_intensity": "low",
          "kind": "step",
          "phase": "warmup"
        },
        {
          "kind": "repeat",
          "repetitions": 3,
          "steps": [
            {
              "duration_minutes": 5,
              "intended_intensity": "controlled_threshold",
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
          "duration_minutes": 10,
          "intended_intensity": "low",
          "kind": "step",
          "phase": "cooldown"
        }
      ],
      "template_id": "road-10k-controlled-threshold-quality-v1",
      "total_planned_minutes": 41,
      "workout_type": "controlled_threshold_quality"
    },
    {
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
              "intended_intensity": "ten_k_specific",
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
          "duration_minutes": 10,
          "intended_intensity": "low",
          "kind": "step",
          "phase": "cooldown"
        }
      ],
      "template_id": "road-10k-specific-interval-quality-v1",
      "total_planned_minutes": 40,
      "workout_type": "ten_k_specific_interval_quality"
    }
  ]
}
```

#### `road_10k_v2_intensity_quality_and_spacing` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `road-10k-plan.mostly-low-intensity-no-universal-winner`, `road-10k-plan.one-to-two-quality-sessions-indirect`
- **Rationale:** Mostly low-intensity training and one-to-two quality sessions have bounded support. Seventy-five percent, one initial quality exposure, and the spacing rules are conservative guardrails rather than universal thresholds.
- **Exact value:**

```json
{
  "activity_average_power_allowed_for_intensity_analysis": false,
  "consecutive_quality_running_days_allowed": false,
  "denominator": "all_planned_running_minutes",
  "historical_intensity_source_priority": [
    "activity_splits",
    "activity_samples"
  ],
  "low_intensity_optimum_claim": false,
  "maximum_total_quality_exposures_per_7_day_unit": 1,
  "minimum_intervening_easy_rest_or_non_running_days": 1,
  "minimum_planned_low_intensity_running_minutes_fraction": 0.75,
  "missed_quality_makeup_allowed": false,
  "numerator": "minutes_with_intended_low_intensity",
  "quality_exposures_include": [
    "planned_quality_template",
    "confirmed_race",
    "athlete_scheduled_10k_benchmark"
  ],
  "quality_work_minutes_count_as_low_intensity": false,
  "reduce_or_remove_quality_before_adding_minutes": true,
  "warmup_recovery_and_cooldown_use_actual_intended_intensity": true
}
```

#### `road_10k_v2_event_benchmark_and_taper` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `road-10k-plan.taper-volume-reduction-supported`, `road-10k-baseline.same-distance-direct-capability`, `road-10k-plan.one-to-two-quality-sessions-indirect`
- **Rationale:** The taper range is indirect mixed-endurance evidence. The exact fifty-percent path, event cutoff, and race-dense fallback are deterministic Product guardrails.
- **Exact value:**

```json
{
  "confirmed_none": {
    "full_rolling_proposal_allowed": true,
    "optional_10k_benchmark": {
      "athlete_selects_and_confirms_date": true,
      "automatic_scheduling": false,
      "counts_as_quality_and_load": true
    }
  },
  "every_race_or_maximal_effort": {
    "counts_as_quality_session": true,
    "counts_as_training_load": true,
    "requires_spacing_validation": true
  },
  "imported_event_must_be_athlete_confirmed": true,
  "race_dense": {
    "full_proposal_allowed": false,
    "result": "readiness_only_limited_guidance_event_conflict"
  },
  "single_target": {
    "target_8_to_14_days_after_start": "taper_proposal_truncated_to_event_eve",
    "target_fewer_than_8_days_after_start": "limited_near_term_guidance",
    "target_more_than_14_days_after_start": "normal_14_day_rolling_proposal"
  },
  "taper": {
    "direct_recreational_road_10k_validation": false,
    "event_day_reserved_not_generated_as_training_workout": true,
    "event_elapsed_time_included_in_planned_training_minutes": false,
    "evidence_population": "mixed_endurance_athletes",
    "maintain_intensity_exposure_without_adding_quality": true,
    "maintain_recent_frequency_when_constraints_allow": true,
    "no_makeup_or_extra_sharpening": true,
    "personal_performance_gain_claim": false,
    "planned_volume_reduction_fraction": 0.5,
    "reference_schedule": "matching_non_taper_schedule_for_same_dates",
    "supported_window_days_before_event": {
      "maximum": 14,
      "minimum": 8
    }
  }
}
```

#### `road_10k_v2_typed_outcomes` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.goal-relevant-current-capability-task-specific`, `eligibility.current-symptoms-support-stop-not-clearance`, `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** Every non-success state remains explicit, preserves the Goal, and avoids borrowing another policy or returning a success-shaped default.
- **Exact value:**

```json
{
  "outcomes": {
    "adult_scope_or_constraints_unconfirmed": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "clarification_required"
    },
    "contradictory_input": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "clarification_required"
    },
    "eligible_rolling_proposal": {
      "adoption_required": true,
      "plan_returned": true,
      "route_state": "plan_candidate"
    },
    "eligible_taper_proposal": {
      "adoption_required": true,
      "plan_returned": true,
      "route_state": "plan_candidate"
    },
    "insufficient_recent_history": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    },
    "limited_guidance_event_conflict": {
      "goal_remains_recorded": true,
      "limited_guidance_returned": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    },
    "limited_near_term_guidance": {
      "goal_remains_recorded": true,
      "limited_guidance_returned": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    },
    "missing_or_stale_direct_baseline": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    },
    "no_schedule_within_envelope": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    },
    "safety_stop": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    },
    "unsupported_intent_distance_surface_or_population": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "policy_unavailable"
    },
    "validation_failed": {
      "goal_remains_recorded": true,
      "plan_returned": false,
      "route_state": "readiness_only"
    }
  },
  "success_shaped_fallback_allowed": false,
  "unknown_policy_or_schema_version_result": "policy_unavailable",
  "unsupported_distance_fallback": "none"
}
```

#### `road_10k_v2_demographic_and_claim_limits` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.masters-age-change-not-automatic-exclusion`, `eligibility.evidence-quality-no-personal-probability`, `population.masters-context-not-age-exclusion`, `population.sex-effects-are-construct-specific`, `population.no-general-sex-or-gender-plan-family`, `road-10k-plan.individual-outcomes-require-error-aware-validation`
- **Rationale:** The reviewed evidence does not validate general age, sex, gender, or target-gap dose rules. Adult scope is confirmed without creating hidden demographic defaults or personal probabilities.
- **Exact value:**

```json
{
  "adult_confirmation_required": true,
  "age_based_dose_modifier": false,
  "causal_plan_benefit_claim": "disabled",
  "exact_age_required": false,
  "gender_based_dose_modifier": false,
  "gender_identity_required": false,
  "medical_diagnosis_clearance_or_treatment": "disabled",
  "personal_adaptation_probability": "disabled",
  "personal_goal_achievement_probability": "disabled",
  "personal_injury_probability": "disabled",
  "physiological_sex_required": false,
  "reproductive_or_pregnancy_context_inferred": false,
  "sex_based_dose_modifier": false,
  "target_time_may": [
    "label_the_goal",
    "compute_a_descriptive_gap_to_qualified_baseline"
  ],
  "target_time_may_not": [
    "increase_frequency",
    "increase_weekly_minutes",
    "lengthen_longest_session",
    "add_quality",
    "override_history_or_symptom_stops"
  ],
  "unknown_demographic_default_allowed": false
}
```

#### `road_10k_v2_consent_ai_and_state` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-10k-plan.individual-outcomes-require-error-aware-validation`
- **Rationale:** Athlete control and deterministic authority are required regardless of whether optional AI explanation is available.
- **Exact value:**

```json
{
  "explicit_adoption_required": true,
  "generator_may_not": [
    "write_or_overwrite_adopted_plan_without_consent",
    "deliver_or_publish_without_consent",
    "schedule_a_missed_workout_makeup",
    "infer_why_a_workout_was_missed",
    "auto_schedule_a_benchmark",
    "confirm_or_change_event_priority"
  ],
  "no_ai_provider_result": "deterministic_result_remains_complete",
  "optional_ai_may": [
    "explain_a_deterministic_result",
    "compare_policy_valid_alternatives",
    "improve_non_authoritative_language"
  ],
  "optional_ai_may_not": [
    "widen_eligibility",
    "invent_missing_context",
    "select_deferred_values",
    "change_template_steps",
    "override_deterministic_validation",
    "approve_adopt_deliver_or_activate"
  ],
  "proposal_is_noncanonical_until_adoption": true,
  "regeneration_creates_versioned_successor": true
}
```

#### `road_10k_v2_privacy_and_audit` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`
- **Rationale:** The generator needs replay provenance, not broad personal context or content telemetry. Stable codes support evaluation without exposing the proposal or athlete values.
- **Exact value:**

```json
{
  "audit_fields": [
    "capability_id",
    "policy_version",
    "science_decision_id",
    "source_decision_digest",
    "contract_digest",
    "generator_version",
    "source_goal_id_and_revision",
    "baseline_snapshot_id_and_source",
    "history_cutoff_and_observation_ids",
    "training_pattern_snapshot_version",
    "event_context_snapshot_version",
    "active_zone_model_id_and_version_when_used",
    "normalized_constraints",
    "selected_template_ids",
    "deterministic_input_hash"
  ],
  "deterministic_replay_required": true,
  "narrative_text_required": false,
  "purpose_bounded_context_only": true,
  "sensitive_trait_inference_allowed": false,
  "telemetry_allowed": [
    "stable_readiness_code",
    "stable_generation_result_code",
    "stable_validation_reason_code",
    "policy_and_generator_version",
    "proposal_adoption_rejection_or_successor_event"
  ],
  "telemetry_prohibited": [
    "athlete_text",
    "workout_payload",
    "target_values",
    "personal_context_values",
    "small_or_identifying_cohort_slices"
  ]
}
```

#### `road_10k_v2_runtime_evaluation` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `eligibility.evidence-quality-no-personal-probability`, `road-10k-plan.individual-outcomes-require-error-aware-validation`
- **Rationale:** These are predeclared reversible rollout rules, not evidence of efficacy or personal safety. Zero-tolerance deterministic failures pause the path.
- **Exact value:**

```json
{
  "dry_run": {
    "deterministic_invariant_breach_tolerance": 0,
    "maximum_single_guardrail_exclusion_fraction": 0.5,
    "replay_mismatch_tolerance": 0,
    "subgroup_exclusion_gap_trigger": {
      "absolute_percentage_points": 20,
      "minimum_cases_per_group": 30
    },
    "unsupported_or_stale_plan_tolerance": 0
  },
  "efficacy_claim_from_process_pilot_allowed": false,
  "evaluate_by": [
    "running_frequency",
    "age_band_when_available_without_default",
    "sex_when_available_and_purpose_permitted_without_default",
    "provider_and_missingness_pattern",
    "dated_vs_undated_goal",
    "taper_vs_non_taper"
  ],
  "opt_in_pilot": {
    "major_edit_definition": {
      "absolute_planned_minutes_change_fraction_greater_than": 0.2,
      "evaluation_window": "one_14_day_committed_proposal",
      "or_scheduled_running_days_changed_at_least": 2
    },
    "maximum_major_edit_fraction": 0.3,
    "maximum_optional_baseline_test_stop_or_noncompletion_fraction": 0.1,
    "maximum_quality_template_rejection_or_major_edit_fraction": 0.3,
    "maximum_symptom_stop_fraction": 0.1,
    "maximum_taper_vs_non_taper_rejection_or_major_edit_gap": 0.15,
    "serious_adverse_events_triggering_immediate_pause": 1
  },
  "pause_or_revise_when_threshold_crossed": true
}
```

#### `road_10k_v2_deferred_scope` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** `road-10k-plan.one-to-two-quality-sessions-indirect`, `road-10k-plan.volume-frequency-associated-not-prescriptive`, `road-10k-plan.fixed-progression-not-safety-law`, `road-10k-plan.individual-outcomes-require-error-aware-validation`
- **Rationale:** Each item needs separate evidence and Product review. V2 cannot fill any deferred choice from another distance, a runner identity, prose, or AI.
- **Exact value:**

```json
{
  "ai_schedule_or_policy_authority": "not_accepted",
  "automatic_benchmark_scheduling": "not_accepted",
  "demographic_dose_modifiers": "not_accepted",
  "exact_generic_power_or_pace_targets": "not_accepted",
  "first_10k_completion": "not_accepted",
  "full_race_dense_schedule_optimization": "not_accepted",
  "mandatory_or_progressive_long_run": "not_accepted",
  "pediatric_clinical_rehabilitation_or_pregnancy_specific_planning": "not_accepted",
  "personal_success_injury_or_adaptation_probability": "not_accepted",
  "progression_above_recent_typical_load": "not_accepted",
  "return_to_consistency": "not_accepted",
  "sparse_history_generation": "not_accepted",
  "treadmill_trail_cross_country_or_multisport": "not_accepted",
  "two_planned_quality_sessions_per_week": "not_accepted"
}
```

#### `road_10k_v2_implementation_and_activation` — guardrail

- **Applies to:** road-10k-plan-generation-policy-v2
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Science acceptance supplies an inactive contract only. Engineering, implementation review, product release, and operations remain separate authorities.
- **Exact value:**

```json
{
  "activation_requires_separate_rollout_decision": true,
  "api_behavior_change_in_this_decision": false,
  "capability_registration_in_this_decision": false,
  "generator_implementation_in_this_decision": false,
  "implementation_review_must_bind": [
    "exact_reviewed_code_diff",
    "generated_contract_digest",
    "deterministic_validation_evidence",
    "api_web_and_miniapp_parity_evidence"
  ],
  "proposal_adoption_or_delivery_change_in_this_decision": false,
  "runtime_state_after_science_acceptance": "inactive",
  "web_or_miniapp_availability_change_in_this_decision": false
}
```

### Rejected alternatives

#### Implement directly from the accepted V1 boundary

V1 deliberately leaves the execution window and exact workout templates unresolved. Delivery may not fill those values from convention or code.

#### Commit only seven days

Seven days is highly reversible but does not provide the smallest complete two-unit 10 km experience and would create unnecessary review and adoption churn. No source establishes it as biologically superior.

#### Copy the 5 km twenty-eight-day block and templates

The 5 km horizon, history, session, and exact template guardrails are distance-specific and cannot authorize a 10 km policy.

#### Use up to two planned quality sessions whenever history permits

Two is an indirect ceiling, not a requirement. The first capability chooses one planned quality session per week to reduce complexity and event-conflict risk while runtime evidence is absent.

#### Generate a full plan for race-dense calendars

No accepted event-priority, taper, and recovery algorithm resolves multiple material events without guessing athlete intent.

#### Use target-time gap, age, sex, or permanent runner level to select dose

The evidence does not validate personal dose escalation or a general demographic or identity-based plan family.

#### Let AI choose missing schedules or templates

AI cannot create evidence, confirm context, choose deferred product values, weaken deterministic validation, approve, adopt, or activate a plan.

### Applicability

- Adults aged 18 years or older with confirmed nonclinical plan scope
- Self-coached runners with current direct outdoor-road 10 km capability
- Stable recent running history satisfying the versioned V2 history guardrails
- Current load within recent observed history and athlete-stated constraints
- Explicit outdoor-road 10 km performance intent
- Confirmed-none or single-target event context
- Dated or undated goals, with undated goals using rolling proposals
- Split- or sample-level intensity evidence when historical intensity is used
- Suggestion-only, deterministic, explicitly adopted noncanonical proposals

### User-facing claim limits

- Describe fourteen days, seven days, one quality session, exact templates, history counts, freshness, frequency, intensity share, taper, and evaluation thresholds as Praxys guardrails.
- Do not describe the exact templates, window, cadence, or allocation algorithm as published or optimal.
- Do not promise goal achievement, performance improvement, injury prevention, medical safety, or an individualized probability.
- Do not describe missing records as detraining or interruption.
- Do not describe age, sex, gender, or runner level as a permanent identity or general dose rule.
- Explain that races and benchmarks consume quality and load and that race-dense routing remains unavailable.
- Explain direct baseline evidence, indirect taper evidence, missingness, assumptions, alternatives, and the explicit adoption boundary.

### Safety implications

- Current injury, illness, or concerning symptom inputs stop generation without diagnosis, treatment, or clearance.
- Never use activity average power for intensity analysis; use splits or samples.
- Do not exceed recent median or maximum weekly minutes, recent longest completed session, recent completed distance, or athlete-stated time limits.
- Preserve at least seventy-five percent planned low-intensity minutes and at most one total quality exposure per seven-day unit.
- Treat every confirmed race or athlete-scheduled maximal benchmark as quality and load.
- Do not compress, stack, or make up missed quality work.
- Do not automatically schedule a maximal 10 km test or benchmark.
- Pause after a serious plausibly related event or any deterministic invariant breach.

### Privacy implications

- Collect only fields required for plan-generation eligibility, scheduling, replay, and consent.
- Keep provider-imported events and profile fields unconfirmed until the athlete confirms their use.
- Do not infer sex, gender, reproductive context, health state, event priority, or reasons for missed training.
- Keep athlete text, workout payloads, target values, and personal context out of generic logs and telemetry.
- Preserve source provenance, purpose, correction, revocation, and deletion behavior for every consumed field.

### Validation plan

- Validate the generated V2 contract and packet digests before human review.
- Unit-test the exact capability tuple, purpose sources, direct-baseline hierarchy, 56-day freshness guardrail, eight-week history, and typed missingness outcomes.
- Unit-test fourteen-day scheduling, the seven-day advisory reassessment, explicit successor adoption, and no overwrite of adopted future days.
- Unit-test every template step, total duration, template ID, one-quality-per-unit rule, low-intensity fraction, quality spacing, and no 5 km template import.
- Unit-test history and athlete caps, deterministic allocation and tie-breaking, event replacement of quality, and no progression above recent median load.
- Unit-test dated, undated, single-target, eight-to-fourteen-day taper, shorter-horizon, benchmark, and race-dense paths.
- Unit-test age and sex missingness without defaults, no target-gap dose escalation, no personal probability, and split-level intensity enforcement.
- Replay identical normalized inputs and versions to require identical hashes, workouts, findings, and reason codes.
- Dry-run against privacy-safe historical fixtures before capability registration and compare exclusions, subgroup gaps, edits, and invariant failures.
- Require API-contract, science, privacy, web/miniapp parity, rendered UI, and deterministic preflight review during implementation.

### Falsification conditions

- Reject the implementation if any unsupported distance, intent, surface, population, stale input, symptom stop, or race-dense conflict returns a plan.
- Reject the implementation if identical normalized inputs and versions produce different hashes, template selections, schedules, or outcomes.
- Reject the implementation if any generated week exceeds history or athlete caps, drops below seventy-five percent low-intensity minutes, schedules more than one quality exposure, stacks quality, or uses activity average power.
- Reject the implementation if it borrows a 5 km template, changes an exact template without a new version, auto-schedules a benchmark, or overwrites adopted future days.
- Revisit the fourteen-day window, seven-day cadence, one-quality choice, or exact templates when the predeclared exclusion, subgroup, rejection, or major-edit thresholds are crossed.
- Pause the optional baseline-test path when stop or noncompletion exceeds ten percent or after one plausibly related serious event.
- Pause the taper path when its rejection or major-edit rate exceeds the non-taper rate by more than fifteen percentage points.
- Reject user-facing claims that imply an optimal schedule, personal probability, medical safety, injury prevention, or guaranteed improvement.

### Decision notes

- This artifact-mode successor proposal addresses issue #731 and remains draft and inactive.
- Existing accepted Evidence Reviews remain authoritative; focused verification on 2026-08-18 found no source validating an exact execution window, reassessment cadence, or deterministic template for this population. No evidence claims or citation metadata were changed.
- Independent Product review recommended the fourteen-day window, seven-day advisory reassessment, one quality session per week, exact 10 km templates, and race-dense limited guidance as the minimum valuable reversible slice. Those values remain Product guardrails and require human Product judgment; this Science record only evaluates their compatibility with the evidence and claim boundaries.
- The proposed lifecycle transition is not active in this draft. After exact digest-bound human approval, V1 and V2 must be transitioned atomically with reciprocal supersession links, generated artifacts, and the registry update.
- Human review should use the generated packet rather than raw YAML. The packet contains the decision sheet, exact inactive contract, and copyable approval marker.
- Impact map: accepted Evidence Reviews -> proposed V2 SDR -> generated decision packet and inactive contract -> human Product and Science decisions -> coordinated V1 supersession -> future pure generator -> shared API router -> web and miniapp parity -> ScienceNote and localization -> dry-run -> opt-in rollout and Runtime/Meta-Eval.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "road-10k-plan-generation-policy-v2",
    "future road-10k-deterministic-generator-v1",
    "shared adult-running plan-purpose and capability router"
  ],
  "contract_digest": "sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496",
  "decision_id": "sdr-road-10k-plan-generation-policy-v2",
  "decision_status": "accepted",
  "decision_version": 2,
  "evidence_claim_ids": [
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "eligibility.current-symptoms-support-stop-not-clearance",
    "eligibility.evidence-quality-no-personal-probability",
    "population.sparse-history-not-detraining-proof",
    "population.masters-context-not-age-exclusion",
    "population.sex-effects-are-construct-specific",
    "population.no-general-sex-or-gender-plan-family",
    "road-10k-plan.task-specific-capability-not-single-marker",
    "road-10k-plan.mostly-low-intensity-no-universal-winner",
    "road-10k-plan.one-to-two-quality-sessions-indirect",
    "road-10k-plan.volume-frequency-associated-not-prescriptive",
    "road-10k-plan.fixed-progression-not-safety-law",
    "road-10k-plan.taper-volume-reduction-supported",
    "road-10k-baseline.same-distance-direct-capability",
    "road-10k-baseline.freshness-cutoff-not-validated",
    "road-10k-plan.individual-outcomes-require-error-aware-validation",
    "road-10k-plan.symptom-based-test-stop-boundary"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-adult-running-plan-population-routing-v1",
    "evidence-road-10k-plan-generation-policy-v1"
  ],
  "linked_evidence_digests": {
    "evidence-adult-running-plan-population-routing-v1": "sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8",
    "evidence-plan-generation-eligibility-safety-v1": "sha256:e884907d33783edc6cdb16fd5504f7f10b6d68f968bfe7cf87e3f024b5bda773",
    "evidence-road-10k-plan-generation-policy-v1": "sha256:10be20a87f8301b633babc2735759fdbbb7cd32abdced0090541281106cb4008"
  },
  "model_version": "road-10k-plan-generation-policy-v2",
  "parameters": {
    "road_10k_v2_activation_and_dependencies": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "active_behavior": false,
        "capability_registry_entry_default_enabled": false,
        "decision_approval_artifact_required": true,
        "implementation_approval_artifact_required_before_activation": true,
        "linked_evidence_required_status": "accepted",
        "predecessor_decision": {
          "proposed_lifecycle_after_v2_acceptance": "superseded",
          "required_status_before_v2_acceptance": "accepted",
          "sdr_id": "sdr-road-10k-plan-generation-policy-v1"
        },
        "shared_dependencies": [
          {
            "required_status": "accepted",
            "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
          },
          {
            "required_status": "accepted",
            "sdr_id": "sdr-adult-running-plan-population-routing-v1"
          }
        ]
      }
    },
    "road_10k_v2_capability_tuple": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-10k-plan.task-specific-capability-not-single-marker"
      ],
      "value": {
        "activity_types": [
          "running"
        ],
        "adult_scope": "confirmed",
        "capability_id": "outdoor_road_10k_performance_v1",
        "capability_pattern": "currently_capable",
        "current_symptoms": "absent",
        "discipline": "running",
        "distance": "10k",
        "distance_m": 10000,
        "goal_kinds": [
          "performance_10k"
        ],
        "history_pattern": "stable",
        "load_pattern": "within_recent",
        "permanent_runner_identity_used": false,
        "plan_intent": "performance",
        "primary_outcome": "elapsed_time",
        "race_dense_full_proposal_supported": false,
        "supported_event_states": [
          "confirmed_none",
          "single_target"
        ],
        "supported_purpose_sources": [
          "current_goal",
          "capability"
        ],
        "surface": "outdoor_road",
        "target_date_optional": true,
        "target_time_optional": true,
        "unlinked_purpose_supported": false
      }
    },
    "road_10k_v2_consent_ai_and_state": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "value": {
        "explicit_adoption_required": true,
        "generator_may_not": [
          "write_or_overwrite_adopted_plan_without_consent",
          "deliver_or_publish_without_consent",
          "schedule_a_missed_workout_makeup",
          "infer_why_a_workout_was_missed",
          "auto_schedule_a_benchmark",
          "confirm_or_change_event_priority"
        ],
        "no_ai_provider_result": "deterministic_result_remains_complete",
        "optional_ai_may": [
          "explain_a_deterministic_result",
          "compare_policy_valid_alternatives",
          "improve_non_authoritative_language"
        ],
        "optional_ai_may_not": [
          "widen_eligibility",
          "invent_missing_context",
          "select_deferred_values",
          "change_template_steps",
          "override_deterministic_validation",
          "approve_adopt_deliver_or_activate"
        ],
        "proposal_is_noncanonical_until_adoption": true,
        "regeneration_creates_versioned_successor": true
      }
    },
    "road_10k_v2_deferred_scope": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.fixed-progression-not-safety-law",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "value": {
        "ai_schedule_or_policy_authority": "not_accepted",
        "automatic_benchmark_scheduling": "not_accepted",
        "demographic_dose_modifiers": "not_accepted",
        "exact_generic_power_or_pace_targets": "not_accepted",
        "first_10k_completion": "not_accepted",
        "full_race_dense_schedule_optimization": "not_accepted",
        "mandatory_or_progressive_long_run": "not_accepted",
        "pediatric_clinical_rehabilitation_or_pregnancy_specific_planning": "not_accepted",
        "personal_success_injury_or_adaptation_probability": "not_accepted",
        "progression_above_recent_typical_load": "not_accepted",
        "return_to_consistency": "not_accepted",
        "sparse_history_generation": "not_accepted",
        "treadmill_trail_cross_country_or_multisport": "not_accepted",
        "two_planned_quality_sessions_per_week": "not_accepted"
      }
    },
    "road_10k_v2_demographic_and_claim_limits": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "eligibility.evidence-quality-no-personal-probability",
        "population.masters-context-not-age-exclusion",
        "population.sex-effects-are-construct-specific",
        "population.no-general-sex-or-gender-plan-family",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "value": {
        "adult_confirmation_required": true,
        "age_based_dose_modifier": false,
        "causal_plan_benefit_claim": "disabled",
        "exact_age_required": false,
        "gender_based_dose_modifier": false,
        "gender_identity_required": false,
        "medical_diagnosis_clearance_or_treatment": "disabled",
        "personal_adaptation_probability": "disabled",
        "personal_goal_achievement_probability": "disabled",
        "personal_injury_probability": "disabled",
        "physiological_sex_required": false,
        "reproductive_or_pregnancy_context_inferred": false,
        "sex_based_dose_modifier": false,
        "target_time_may": [
          "label_the_goal",
          "compute_a_descriptive_gap_to_qualified_baseline"
        ],
        "target_time_may_not": [
          "increase_frequency",
          "increase_weekly_minutes",
          "lengthen_longest_session",
          "add_quality",
          "override_history_or_symptom_stops"
        ],
        "unknown_demographic_default_allowed": false
      }
    },
    "road_10k_v2_event_benchmark_and_taper": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.taper-volume-reduction-supported",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-plan.one-to-two-quality-sessions-indirect"
      ],
      "value": {
        "confirmed_none": {
          "full_rolling_proposal_allowed": true,
          "optional_10k_benchmark": {
            "athlete_selects_and_confirms_date": true,
            "automatic_scheduling": false,
            "counts_as_quality_and_load": true
          }
        },
        "every_race_or_maximal_effort": {
          "counts_as_quality_session": true,
          "counts_as_training_load": true,
          "requires_spacing_validation": true
        },
        "imported_event_must_be_athlete_confirmed": true,
        "race_dense": {
          "full_proposal_allowed": false,
          "result": "readiness_only_limited_guidance_event_conflict"
        },
        "single_target": {
          "target_8_to_14_days_after_start": "taper_proposal_truncated_to_event_eve",
          "target_fewer_than_8_days_after_start": "limited_near_term_guidance",
          "target_more_than_14_days_after_start": "normal_14_day_rolling_proposal"
        },
        "taper": {
          "direct_recreational_road_10k_validation": false,
          "event_day_reserved_not_generated_as_training_workout": true,
          "event_elapsed_time_included_in_planned_training_minutes": false,
          "evidence_population": "mixed_endurance_athletes",
          "maintain_intensity_exposure_without_adding_quality": true,
          "maintain_recent_frequency_when_constraints_allow": true,
          "no_makeup_or_extra_sharpening": true,
          "personal_performance_gain_claim": false,
          "planned_volume_reduction_fraction": 0.5,
          "reference_schedule": "matching_non_taper_schedule_for_same_dates",
          "supported_window_days_before_event": {
            "maximum": 14,
            "minimum": 8
          }
        }
      }
    },
    "road_10k_v2_execution_window_and_reassessment": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "value": {
        "advisory_reassessment_after_completed_days": 7,
        "automatic_overwrite_of_adopted_future_days": false,
        "automatic_successor_adoption": false,
        "biological_optimum_claim": false,
        "calendar_schedule_unit_days": 7,
        "committed_proposal_days": 14,
        "dated_goal_planning_horizon": "through_confirmed_primary_event",
        "each_successor_requires": [
          "fresh_eligibility_evaluation",
          "updated_completed_history",
          "updated_event_context",
          "updated_training_pattern_snapshot",
          "explicit_review_and_adoption"
        ],
        "fixed_goal_horizon_required": false,
        "no_automatic_progression_between_reassessments": true,
        "proposal_end_inclusive": true,
        "successor_candidate_triggers": [
          "seven_completed_days",
          "new_or_changed_confirmed_event",
          "material_training_pattern_change",
          "new_qualified_10k_baseline",
          "changed_availability_or_constraint",
          "athlete_requested_review"
        ],
        "undated_goal_planning_horizon": "rolling_until_athlete_changes_or_ends_goal"
      }
    },
    "road_10k_v2_implementation_and_activation": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "activation_requires_separate_rollout_decision": true,
        "api_behavior_change_in_this_decision": false,
        "capability_registration_in_this_decision": false,
        "generator_implementation_in_this_decision": false,
        "implementation_review_must_bind": [
          "exact_reviewed_code_diff",
          "generated_contract_digest",
          "deterministic_validation_evidence",
          "api_web_and_miniapp_parity_evidence"
        ],
        "proposal_adoption_or_delivery_change_in_this_decision": false,
        "runtime_state_after_science_acceptance": "inactive",
        "web_or_miniapp_availability_change_in_this_decision": false
      }
    },
    "road_10k_v2_intensity_quality_and_spacing": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.mostly-low-intensity-no-universal-winner",
        "road-10k-plan.one-to-two-quality-sessions-indirect"
      ],
      "value": {
        "activity_average_power_allowed_for_intensity_analysis": false,
        "consecutive_quality_running_days_allowed": false,
        "denominator": "all_planned_running_minutes",
        "historical_intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "low_intensity_optimum_claim": false,
        "maximum_total_quality_exposures_per_7_day_unit": 1,
        "minimum_intervening_easy_rest_or_non_running_days": 1,
        "minimum_planned_low_intensity_running_minutes_fraction": 0.75,
        "missed_quality_makeup_allowed": false,
        "numerator": "minutes_with_intended_low_intensity",
        "quality_exposures_include": [
          "planned_quality_template",
          "confirmed_race",
          "athlete_scheduled_10k_benchmark"
        ],
        "quality_work_minutes_count_as_low_intensity": false,
        "reduce_or_remove_quality_before_adding_minutes": true,
        "warmup_recovery_and_cooldown_use_actual_intended_intensity": true
      }
    },
    "road_10k_v2_privacy_and_audit": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "audit_fields": [
          "capability_id",
          "policy_version",
          "science_decision_id",
          "source_decision_digest",
          "contract_digest",
          "generator_version",
          "source_goal_id_and_revision",
          "baseline_snapshot_id_and_source",
          "history_cutoff_and_observation_ids",
          "training_pattern_snapshot_version",
          "event_context_snapshot_version",
          "active_zone_model_id_and_version_when_used",
          "normalized_constraints",
          "selected_template_ids",
          "deterministic_input_hash"
        ],
        "deterministic_replay_required": true,
        "narrative_text_required": false,
        "purpose_bounded_context_only": true,
        "sensitive_trait_inference_allowed": false,
        "telemetry_allowed": [
          "stable_readiness_code",
          "stable_generation_result_code",
          "stable_validation_reason_code",
          "policy_and_generator_version",
          "proposal_adoption_rejection_or_successor_event"
        ],
        "telemetry_prohibited": [
          "athlete_text",
          "workout_payload",
          "target_values",
          "personal_context_values",
          "small_or_identifying_cohort_slices"
        ]
      }
    },
    "road_10k_v2_readiness_and_missingness": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.current-symptoms-support-stop-not-clearance",
        "population.sparse-history-not-detraining-proof",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-baseline.freshness-cutoff-not-validated",
        "road-10k-plan.symptom-based-test-stop-boundary"
      ],
      "value": {
        "accepted_direct_baseline_order": [
          "organized_outdoor_road_10k_race_with_elapsed_time",
          "explicit_all_out_standardized_outdoor_road_or_track_10k_time_trial"
        ],
        "adult_scope_unconfirmed_result": "clarification_required",
        "baseline_current_through_completed_days": 56,
        "baseline_stale_from_completed_days": 57,
        "contradictory_constraints_result": "clarification_required",
        "current_symptom_stop_result": "safety_stop",
        "excluded_as_direct_baseline": [
          "five_k_result_or_conversion",
          "race_prediction",
          "passive_fastest_10k_split",
          "threshold_or_lactate_speed_alone",
          "critical_power_or_critical_velocity_alone",
          "activity_average_power",
          "vendor_readiness_or_race_score"
        ],
        "missing_or_stale_baseline_result": "readiness_only",
        "missing_or_stale_history_result": "readiness_only",
        "optional_baseline_test": {
          "automatic_scheduling": false,
          "explicit_athlete_choice_required": true,
          "no_test_alternative": "remain_readiness_only",
          "shared_safety_eligibility_required": true
        },
        "sparse_or_missing_records_establish_detraining": false,
        "unsupported_distance_surface_or_intent_result": "policy_unavailable"
      }
    },
    "road_10k_v2_required_inputs": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-plan.volume-frequency-associated-not-prescriptive"
      ],
      "value": {
        "conditional_versioned_inputs": [
          "active_athlete_zone_model_id_and_version"
        ],
        "constraint_schema_id": "outdoor_road_10k_constraints_v1",
        "direct_baseline_required_metadata": [
          "completed_at",
          "elapsed_time_seconds",
          "distance_m",
          "surface_or_protocol",
          "route_or_venue_identifier",
          "intentional_all_out_or_race_flag",
          "assistance_status",
          "source_provider"
        ],
        "free_text_narrative_required": false,
        "historical_intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "latest_run_within_completed_days": 10,
        "minimum_runs_per_usable_week": 3,
        "minimum_usable_completed_weeks": 4,
        "prohibited_historical_intensity_source": [
          "activity_avg_power"
        ],
        "recent_history_lookback_completed_weeks": 8,
        "required_versioned_inputs": [
          "policy_version",
          "science_decision_id",
          "contract_digest",
          "generator_version",
          "athlete_local_today",
          "proposal_start_date",
          "plan_purpose_source",
          "source_goal_id_and_revision_when_current_goal",
          "normalized_goal",
          "adult_scope_confirmation",
          "current_symptom_stop_state",
          "direct_10k_baseline_snapshot",
          "recent_completed_running_history",
          "current_training_pattern_snapshot",
          "confirmed_event_context_snapshot",
          "available_running_weekdays",
          "athlete_stated_weekly_time_limit",
          "athlete_stated_single_session_time_limit",
          "unavailable_dates",
          "preferred_longest_easy_weekday_if_any"
        ]
      }
    },
    "road_10k_v2_runtime_evaluation": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "value": {
        "dry_run": {
          "deterministic_invariant_breach_tolerance": 0,
          "maximum_single_guardrail_exclusion_fraction": 0.5,
          "replay_mismatch_tolerance": 0,
          "subgroup_exclusion_gap_trigger": {
            "absolute_percentage_points": 20,
            "minimum_cases_per_group": 30
          },
          "unsupported_or_stale_plan_tolerance": 0
        },
        "efficacy_claim_from_process_pilot_allowed": false,
        "evaluate_by": [
          "running_frequency",
          "age_band_when_available_without_default",
          "sex_when_available_and_purpose_permitted_without_default",
          "provider_and_missingness_pattern",
          "dated_vs_undated_goal",
          "taper_vs_non_taper"
        ],
        "opt_in_pilot": {
          "major_edit_definition": {
            "absolute_planned_minutes_change_fraction_greater_than": 0.2,
            "evaluation_window": "one_14_day_committed_proposal",
            "or_scheduled_running_days_changed_at_least": 2
          },
          "maximum_major_edit_fraction": 0.3,
          "maximum_optional_baseline_test_stop_or_noncompletion_fraction": 0.1,
          "maximum_quality_template_rejection_or_major_edit_fraction": 0.3,
          "maximum_symptom_stop_fraction": 0.1,
          "maximum_taper_vs_non_taper_rejection_or_major_edit_gap": 0.15,
          "serious_adverse_events_triggering_immediate_pause": 1
        },
        "pause_or_revise_when_threshold_crossed": true
      }
    },
    "road_10k_v2_schedule_construction": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.fixed-progression-not-safety-law"
      ],
      "value": {
        "below_minimum_result": "readiness_only",
        "easy_and_longest_easy_allocation": {
          "automatic_longest_easy_increase": false,
          "integer_remainder_priority": [
            "preferred_longest_easy_day",
            "chronological_day_order"
          ],
          "longest_easy_designation_optional": true,
          "quality_template_minutes_are_allocated_first": true,
          "remaining_minutes_distributed_evenly_across_non_quality_runs": true
        },
        "event_or_benchmark_replaces_planned_quality_in_same_unit": true,
        "no_schedule_result": "readiness_only_no_schedule_within_envelope",
        "non_taper_progression_above_recent_median": false,
        "normal_two_unit_quality_order": {
          "first_unit": "controlled_threshold_quality",
          "second_unit": "ten_k_specific_interval_quality"
        },
        "quality_sessions_per_7_day_unit": 1,
        "requested_above_maximum_result": "clarification_required",
        "schedule_must_satisfy_all_history_constraint_intensity_and_spacing_rules": true,
        "selected_running_days_per_7_day_unit": {
          "deterministic_value": "minimum_of_available_days_recent_modal_days_and_policy_maximum",
          "maximum": 6,
          "minimum": 3
        },
        "session_distance_hard_cap": "recent_maximum_completed_session_distance",
        "session_duration_hard_cap": "minimum_of_recent_maximum_completed_session_minutes_and_athlete_stated_session_limit",
        "target_time_gap_may_raise_load": false,
        "weekly_running_minutes_hard_cap": "minimum_of_recent_maximum_usable_weekly_minutes_and_athlete_stated_weekly_limit",
        "weekly_running_minutes_target": "minimum_of_recent_median_usable_weekly_minutes_and_athlete_stated_weekly_limit"
      }
    },
    "road_10k_v2_typed_outcomes": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "value": {
        "outcomes": {
          "adult_scope_or_constraints_unconfirmed": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "clarification_required"
          },
          "contradictory_input": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "clarification_required"
          },
          "eligible_rolling_proposal": {
            "adoption_required": true,
            "plan_returned": true,
            "route_state": "plan_candidate"
          },
          "eligible_taper_proposal": {
            "adoption_required": true,
            "plan_returned": true,
            "route_state": "plan_candidate"
          },
          "insufficient_recent_history": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "limited_guidance_event_conflict": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "limited_near_term_guidance": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "missing_or_stale_direct_baseline": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "no_schedule_within_envelope": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "safety_stop": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "unsupported_intent_distance_surface_or_population": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "policy_unavailable"
          },
          "validation_failed": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          }
        },
        "success_shaped_fallback_allowed": false,
        "unknown_policy_or_schema_version_result": "policy_unavailable",
        "unsupported_distance_fallback": "none"
      }
    },
    "road_10k_v2_workout_templates": {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.task-specific-capability-not-single-marker",
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.mostly-low-intensity-no-universal-winner"
      ],
      "value": {
        "easy_template": "duration_only",
        "generic_five_k_or_ten_k_pace_conversion": false,
        "generic_percent_of_threshold_or_critical_power": false,
        "inherited_from_outdoor_5k": false,
        "longest_easy_template": "duration_only",
        "target_expression_priority": [
          "current_athlete_specific_active_zone_model",
          "duration_and_session_type_only"
        ],
        "template_must_fit_session_and_weekly_caps": true,
        "template_optimum_claim": false,
        "templates": [
          {
            "steps": [
              {
                "duration_minutes": 10,
                "intended_intensity": "low",
                "kind": "step",
                "phase": "warmup"
              },
              {
                "kind": "repeat",
                "repetitions": 3,
                "steps": [
                  {
                    "duration_minutes": 5,
                    "intended_intensity": "controlled_threshold",
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
                "duration_minutes": 10,
                "intended_intensity": "low",
                "kind": "step",
                "phase": "cooldown"
              }
            ],
            "template_id": "road-10k-controlled-threshold-quality-v1",
            "total_planned_minutes": 41,
            "workout_type": "controlled_threshold_quality"
          },
          {
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
                    "intended_intensity": "ten_k_specific",
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
                "duration_minutes": 10,
                "intended_intensity": "low",
                "kind": "step",
                "phase": "cooldown"
              }
            ],
            "template_id": "road-10k-specific-interval-quality-v1",
            "total_planned_minutes": 40,
            "workout_type": "ten_k_specific_interval_quality"
          }
        ]
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "If accepted by a digest-bound human decision approver, this SDR would supersede the accepted but generator-incomplete V1 boundary with one inactive, generator-ready policy for adult outdoor-road 10 km performance intent. The supported pattern remains currently capable, history-rich, within-recent load, and free of current symptom-stop inputs. A deterministic proposal would commit fourteen athlete-local calendar days, present an advisory reassessment after seven completed days, and require explicit adoption before any successor replaces future adopted days. The initial schedule would use one quality session in each seven-day unit, never exceed recent typical load or athlete-stated constraints, preserve at least seventy-five percent low-intensity running minutes, and use only the two versioned 10 km quality templates defined here. Confirmed-none and single-target event states could receive a full proposal; race-dense, unsupported, stale, missing, contradictory, or symptom-stop states would fail closed to typed readiness, clarification, limited-guidance, or unavailable outcomes. The fourteen-day window, seven-day advisory cadence, one-quality choice, exact template steps, allocation rules, and pilot thresholds are transparent Praxys product guardrails, not published optima. This decision would not implement or activate a generator, adopt or deliver a plan, schedule a benchmark automatically, create a personal probability, or authorize first-completion, return-to-consistency, sparse-history, clinical, trail, marathon, or ultra planning.",
  "affected_surfaces": {
    "apis": [
      "future authenticated 10 km readiness, alternatives, generate, and regenerate endpoints",
      "shared capability discovery and purpose selection",
      "future proposal persistence and adoption validation"
    ],
    "clients": [
      "generated human SDR review packet and inactive machine contract",
      "future web 10 km readiness, proposal, taper, limited-guidance, adoption, and successor states",
      "future miniapp feature, type, state, write, i18n, and consent parity",
      "future plugin and MCP capability discovery and proposal parity"
    ],
    "models": [
      "road-10k-plan-generation-policy-v2",
      "future road-10k-deterministic-generator-v1",
      "shared adult-running plan-purpose and capability router"
    ],
    "science_notes": [
      "Explain direct versus indirect evidence and every exact Product guardrail.",
      "Show baseline source, history cutoff, event state, template version, assumptions, unknowns, risks, alternatives, and adoption boundary."
    ]
  },
  "applicability": [
    "Adults aged 18 years or older with confirmed nonclinical plan scope",
    "Self-coached runners with current direct outdoor-road 10 km capability",
    "Stable recent running history satisfying the versioned V2 history guardrails",
    "Current load within recent observed history and athlete-stated constraints",
    "Explicit outdoor-road 10 km performance intent",
    "Confirmed-none or single-target event context",
    "Dated or undated goals, with undated goals using rolling proposals",
    "Split- or sample-level intensity evidence when historical intensity is used",
    "Suggestion-only, deterministic, explicitly adopted noncanonical proposals"
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-08-18",
  "decision_notes": [
    "This artifact-mode successor proposal addresses issue #731 and remains draft and inactive.",
    "Existing accepted Evidence Reviews remain authoritative; focused verification on 2026-08-18 found no source validating an exact execution window, reassessment cadence, or deterministic template for this population. No evidence claims or citation metadata were changed.",
    "Independent Product review recommended the fourteen-day window, seven-day advisory reassessment, one quality session per week, exact 10 km templates, and race-dense limited guidance as the minimum valuable reversible slice. Those values remain Product guardrails and require human Product judgment; this Science record only evaluates their compatibility with the evidence and claim boundaries.",
    "The proposed lifecycle transition is not active in this draft. After exact digest-bound human approval, V1 and V2 must be transitioned atomically with reciprocal supersession links, generated artifacts, and the registry update.",
    "Human review should use the generated packet rather than raw YAML. The packet contains the decision sheet, exact inactive contract, and copyable approval marker.",
    "Impact map: accepted Evidence Reviews -> proposed V2 SDR -> generated decision packet and inactive contract -> human Product and Science decisions -> coordinated V1 supersession -> future pure generator -> shared API router -> web and miniapp parity -> ScienceNote and localization -> dry-run -> opt-in rollout and Runtime/Meta-Eval."
  ],
  "decision_review": {
    "approval_statement": "I approve this inactive road 10 km performance policy as one bounded generator contract: the history-rich adult outdoor-road scope and typed readiness inputs; a fourteen-day committed proposal with a seven-day advisory reassessment and explicit successor adoption; one quality session per seven-day unit using the exact versioned 10 km templates; confirmed-none and single-target event handling with a bounded taper and race-dense limited guidance; the stated claim, demographic, consent, AI, privacy, and audit limits; and the predeclared runtime evaluation gates. I agree that broader dose, race-density, population, targeting, automation, and activation choices remain deferred. I understand that every exact schedule and template value is a Praxys guardrail rather than a published optimum, and that this approval does not implement or activate behavior.",
    "items": [
      {
        "approval_effect": [
          "The exact 10 km performance capability tuple becomes an accepted inactive decision input.",
          "Missing, stale, contradictory, unsupported, and symptom-stop states remain typed non-success outcomes.",
          "The predecessor and shared policy dependencies remain explicit."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Any generator implementation, registry activation, plan adoption, or provider delivery.",
          "First-completion, return-to-consistency, sparse-history, other-surface, or clinical planning."
        ],
        "evidence_claim_ids": [
          "eligibility.recent-history-anchor-without-universal-threshold",
          "eligibility.goal-relevant-current-capability-task-specific",
          "eligibility.current-symptoms-support-stop-not-clearance",
          "population.sparse-history-not-detraining-proof",
          "road-10k-baseline.same-distance-direct-capability",
          "road-10k-baseline.freshness-cutoff-not-validated"
        ],
        "id": "supported-capability",
        "parameter_names": [
          "road_10k_v2_activation_and_dependencies",
          "road_10k_v2_capability_tuple",
          "road_10k_v2_required_inputs",
          "road_10k_v2_readiness_and_missingness"
        ],
        "proposed_decision": "Accept that exact tuple and its fail-closed input contract. Preserve every valid Goal when the policy does not match, and never manufacture eligibility from predictions, sparse records, another distance, a permanent runner label, or missing demographic context.",
        "question": "Should V2 remain limited to the stated adult, currently capable, history-rich outdoor-road 10 km performance tuple and require the listed direct baseline, recent history, event, symptom, and constraint inputs?",
        "title": "Accept the exact supported capability and readiness contract"
      },
      {
        "approval_effect": [
          "Dated and undated goals may receive a bounded rolling proposal.",
          "Material changes can produce a successor candidate without silently overwriting adopted days."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Automatic progression, automatic successor adoption, or a claim that fourteen or seven days is biologically optimal."
        ],
        "evidence_claim_ids": [
          "eligibility.recent-history-anchor-without-universal-threshold",
          "road-10k-plan.volume-frequency-associated-not-prescriptive",
          "road-10k-plan.individual-outcomes-require-error-aware-validation"
        ],
        "id": "rolling-execution",
        "parameter_names": [
          "road_10k_v2_execution_window_and_reassessment"
        ],
        "proposed_decision": "Accept fourteen days as the minimum valuable reversible product window and seven days as an advisory review cadence. Treat both as operational guardrails rather than physiological claims.",
        "question": "Should the first generator commit fourteen days, show an advisory reassessment after seven completed days, and require explicit adoption before a successor changes future adopted days?",
        "title": "Accept the fourteen-day rolling execution contract"
      },
      {
        "approval_effect": [
          "A future deterministic generator has complete schedule, allocation, intensity, spacing, and template inputs.",
          "Exact template IDs and steps become reviewable guardrails with deterministic replay."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Describing the templates as evidence-backed optima.",
          "Copying 5 km templates, adding a second planned quality session, or exceeding history and constraint caps."
        ],
        "evidence_claim_ids": [
          "road-10k-plan.task-specific-capability-not-single-marker",
          "road-10k-plan.mostly-low-intensity-no-universal-winner",
          "road-10k-plan.one-to-two-quality-sessions-indirect",
          "road-10k-plan.volume-frequency-associated-not-prescriptive",
          "road-10k-plan.fixed-progression-not-safety-law"
        ],
        "id": "deterministic-schedule",
        "parameter_names": [
          "road_10k_v2_schedule_construction",
          "road_10k_v2_workout_templates",
          "road_10k_v2_intensity_quality_and_spacing"
        ],
        "proposed_decision": "Accept the simplest useful schedule: one quality session per week, alternating threshold and 10 km interval templates across a normal fourteen-day proposal, with all duration and load bounded by recent completed history and athlete-stated constraints.",
        "question": "Should V2 use one quality session in each seven-day unit, history-capped easy running, at least seventy-five percent low-intensity minutes, and the exact two versioned 10 km quality templates?",
        "title": "Accept the initial deterministic schedule and templates"
      },
      {
        "approval_effect": [
          "Undated goals can roll without a forced benchmark.",
          "A confirmed primary event may receive one deterministic taper path.",
          "Race-dense and very short horizons remain fail-closed."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Automatic event confirmation or priority, race-dense optimization, or a promised taper benefit."
        ],
        "evidence_claim_ids": [
          "road-10k-plan.taper-volume-reduction-supported",
          "road-10k-baseline.same-distance-direct-capability",
          "road-10k-plan.one-to-two-quality-sessions-indirect"
        ],
        "id": "event-and-taper",
        "parameter_names": [
          "road_10k_v2_event_benchmark_and_taper"
        ],
        "proposed_decision": "Accept that boundary. Never auto-schedule a benchmark, treat every race or maximal effort as quality and load, and stop the generated schedule before the event.",
        "question": "Should full proposals remain limited to confirmed-none and single-target event states, use the accepted indirect taper range for a confirmed primary event eight to fourteen days away, and return limited guidance for race-dense or shorter-horizon cases?",
        "title": "Accept bounded event, benchmark, and taper routing"
      },
      {
        "approval_effect": [
          "Runtime outcomes remain honest and deterministic.",
          "Consent, privacy, missingness, and AI authority remain bounded."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Medical inference, sensitive-trait inference, personal success or injury probability, auto-adoption, or content logging."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "eligibility.masters-age-change-not-automatic-exclusion",
          "population.masters-context-not-age-exclusion",
          "population.sex-effects-are-construct-specific",
          "population.no-general-sex-or-gender-plan-family",
          "road-10k-plan.individual-outcomes-require-error-aware-validation",
          "road-10k-plan.symptom-based-test-stop-boundary"
        ],
        "id": "hard-boundaries",
        "parameter_names": [
          "road_10k_v2_typed_outcomes",
          "road_10k_v2_demographic_and_claim_limits",
          "road_10k_v2_consent_ai_and_state",
          "road_10k_v2_privacy_and_audit"
        ],
        "proposed_decision": "Accept those boundaries. Unknown age beyond adult confirmation, sex, gender, reproductive context, symptoms, events, and constraints may not be defaulted or inferred into eligibility or dose.",
        "question": "Should the generator preserve typed non-success outcomes, avoid demographic modifiers and personal probabilities, require explicit adoption, constrain AI to explanation, and record only minimized replay and audit data?",
        "title": "Accept honest outcomes and hard control boundaries"
      },
      {
        "approval_effect": [
          "Runtime learning has explicit pause and revision triggers before activation.",
          "Cross-capability learning can be compared without success-shaped interpretation."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "A claim that the policy improves performance, prevents injury, or is safe for an individual."
        ],
        "evidence_claim_ids": [
          "eligibility.evidence-quality-no-personal-probability",
          "road-10k-plan.individual-outcomes-require-error-aware-validation"
        ],
        "id": "evaluation-gates",
        "parameter_names": [
          "road_10k_v2_runtime_evaluation"
        ],
        "proposed_decision": "Accept the thresholds as reversible pilot decision rules. They do not establish efficacy or medical safety.",
        "question": "Should dry-run and opt-in rollout pause or revisit the policy when the stated deterministic, exclusion, edit, taper, subgroup, symptom, benchmark, or serious-event thresholds are crossed?",
        "title": "Accept the predeclared runtime evaluation gates"
      },
      {
        "approval_effect": [
          "The contract exposes rather than hides every deferred capability.",
          "Implementation cannot infer a deferred value from V1, 5 km behavior, prose, or AI output."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Any deferred capability or fallback policy."
        ],
        "evidence_claim_ids": [
          "road-10k-plan.one-to-two-quality-sessions-indirect",
          "road-10k-plan.volume-frequency-associated-not-prescriptive",
          "road-10k-plan.fixed-progression-not-safety-law",
          "road-10k-plan.individual-outcomes-require-error-aware-validation"
        ],
        "id": "broader-capabilities",
        "parameter_names": [
          "road_10k_v2_deferred_scope"
        ],
        "proposed_decision": "Yes. Keep every listed capability explicitly not accepted until its own evidence, Product rationale, science decision, and review are complete.",
        "question": "Should two-quality weeks, progression, mandatory long runs, race-dense optimization, other populations, exact power or pace targets, automatic benchmarks, personal probabilities, and AI planning authority remain unaccepted?",
        "title": "Defer broader dose, population, and automation choices"
      },
      {
        "approval_effect": [
          "Science acceptance remains separate from implementation and activation."
        ],
        "disposition": "defer",
        "does_not_authorize": [
          "Code changes, runtime availability, plan adoption, provider delivery, or publication."
        ],
        "evidence_claim_ids": [],
        "id": "implementation-and-activation",
        "parameter_names": [
          "road_10k_v2_implementation_and_activation"
        ],
        "proposed_decision": "Yes. Keep the generated contract inactive. Require separate implementation review bound to the exact code diff and validation evidence before any activation.",
        "question": "Should generator code, API and client behavior, capability registration, rollout, adoption, and delivery remain outside this science approval?",
        "title": "Defer implementation and runtime activation"
      }
    ],
    "reviewer_task": "Review the six proposed inactive policy decisions and the two explicit deferrals below. Approve the decision sheet as a unit or request changes by item ID. The exact contract is included in the audit appendix. This review does not approve implementation or runtime activation."
  },
  "evidence_claim_ids": [
    "eligibility.recent-history-anchor-without-universal-threshold",
    "eligibility.goal-relevant-current-capability-task-specific",
    "eligibility.masters-age-change-not-automatic-exclusion",
    "eligibility.current-symptoms-support-stop-not-clearance",
    "eligibility.evidence-quality-no-personal-probability",
    "population.sparse-history-not-detraining-proof",
    "population.masters-context-not-age-exclusion",
    "population.sex-effects-are-construct-specific",
    "population.no-general-sex-or-gender-plan-family",
    "road-10k-plan.task-specific-capability-not-single-marker",
    "road-10k-plan.mostly-low-intensity-no-universal-winner",
    "road-10k-plan.one-to-two-quality-sessions-indirect",
    "road-10k-plan.volume-frequency-associated-not-prescriptive",
    "road-10k-plan.fixed-progression-not-safety-law",
    "road-10k-plan.taper-volume-reduction-supported",
    "road-10k-baseline.same-distance-direct-capability",
    "road-10k-baseline.freshness-cutoff-not-validated",
    "road-10k-plan.individual-outcomes-require-error-aware-validation",
    "road-10k-plan.symptom-based-test-stop-boundary"
  ],
  "evidence_review_ids": [
    "evidence-plan-generation-eligibility-safety-v1",
    "evidence-adult-running-plan-population-routing-v1",
    "evidence-road-10k-plan-generation-policy-v1"
  ],
  "falsification_conditions": [
    "Reject the implementation if any unsupported distance, intent, surface, population, stale input, symptom stop, or race-dense conflict returns a plan.",
    "Reject the implementation if identical normalized inputs and versions produce different hashes, template selections, schedules, or outcomes.",
    "Reject the implementation if any generated week exceeds history or athlete caps, drops below seventy-five percent low-intensity minutes, schedules more than one quality exposure, stacks quality, or uses activity average power.",
    "Reject the implementation if it borrows a 5 km template, changes an exact template without a new version, auto-schedules a benchmark, or overwrites adopted future days.",
    "Revisit the fourteen-day window, seven-day cadence, one-quality choice, or exact templates when the predeclared exclusion, subgroup, rejection, or major-edit thresholds are crossed.",
    "Pause the optional baseline-test path when stop or noncompletion exceeds ten percent or after one plausibly related serious event.",
    "Pause the taper path when its rejection or major-edit rate exceeds the non-taper rate by more than fifteen percentage points.",
    "Reject user-facing claims that imply an optimal schedule, personal probability, medical safety, injury prevention, or guaranteed improvement."
  ],
  "id": "sdr-road-10k-plan-generation-policy-v2",
  "model_parameters": [
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_10k_v2_activation_and_dependencies",
      "rationale": "V2 is a proposed successor contract, not runtime authority. Acceptance, implementation review, capability registration, and rollout are separate gates.",
      "value": {
        "active_behavior": false,
        "capability_registry_entry_default_enabled": false,
        "decision_approval_artifact_required": true,
        "implementation_approval_artifact_required_before_activation": true,
        "linked_evidence_required_status": "accepted",
        "predecessor_decision": {
          "proposed_lifecycle_after_v2_acceptance": "superseded",
          "required_status_before_v2_acceptance": "accepted",
          "sdr_id": "sdr-road-10k-plan-generation-policy-v1"
        },
        "shared_dependencies": [
          {
            "required_status": "accepted",
            "sdr_id": "sdr-plan-generation-eligibility-safety-v1"
          },
          {
            "required_status": "accepted",
            "sdr_id": "sdr-adult-running-plan-population-routing-v1"
          }
        ]
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "road-10k-plan.task-specific-capability-not-single-marker"
      ],
      "name": "road_10k_v2_capability_tuple",
      "rationale": "The tuple matches one evidence and Product slice rather than distance alone. A valid Goal remains recorded when the tuple does not match.",
      "value": {
        "activity_types": [
          "running"
        ],
        "adult_scope": "confirmed",
        "capability_id": "outdoor_road_10k_performance_v1",
        "capability_pattern": "currently_capable",
        "current_symptoms": "absent",
        "discipline": "running",
        "distance": "10k",
        "distance_m": 10000,
        "goal_kinds": [
          "performance_10k"
        ],
        "history_pattern": "stable",
        "load_pattern": "within_recent",
        "permanent_runner_identity_used": false,
        "plan_intent": "performance",
        "primary_outcome": "elapsed_time",
        "race_dense_full_proposal_supported": false,
        "supported_event_states": [
          "confirmed_none",
          "single_target"
        ],
        "supported_purpose_sources": [
          "current_goal",
          "capability"
        ],
        "surface": "outdoor_road",
        "target_date_optional": true,
        "target_time_optional": true,
        "unlinked_purpose_supported": false
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-plan.volume-frequency-associated-not-prescriptive"
      ],
      "name": "road_10k_v2_required_inputs",
      "rationale": "These fields make the accepted history-rich pattern replayable while minimizing private context. Exact history counts remain product guardrails rather than published eligibility thresholds.",
      "value": {
        "conditional_versioned_inputs": [
          "active_athlete_zone_model_id_and_version"
        ],
        "constraint_schema_id": "outdoor_road_10k_constraints_v1",
        "direct_baseline_required_metadata": [
          "completed_at",
          "elapsed_time_seconds",
          "distance_m",
          "surface_or_protocol",
          "route_or_venue_identifier",
          "intentional_all_out_or_race_flag",
          "assistance_status",
          "source_provider"
        ],
        "free_text_narrative_required": false,
        "historical_intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "latest_run_within_completed_days": 10,
        "minimum_runs_per_usable_week": 3,
        "minimum_usable_completed_weeks": 4,
        "prohibited_historical_intensity_source": [
          "activity_avg_power"
        ],
        "recent_history_lookback_completed_weeks": 8,
        "required_versioned_inputs": [
          "policy_version",
          "science_decision_id",
          "contract_digest",
          "generator_version",
          "athlete_local_today",
          "proposal_start_date",
          "plan_purpose_source",
          "source_goal_id_and_revision_when_current_goal",
          "normalized_goal",
          "adult_scope_confirmation",
          "current_symptom_stop_state",
          "direct_10k_baseline_snapshot",
          "recent_completed_running_history",
          "current_training_pattern_snapshot",
          "confirmed_event_context_snapshot",
          "available_running_weekdays",
          "athlete_stated_weekly_time_limit",
          "athlete_stated_single_session_time_limit",
          "unavailable_dates",
          "preferred_longest_easy_weekday_if_any"
        ]
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.current-symptoms-support-stop-not-clearance",
        "population.sparse-history-not-detraining-proof",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-baseline.freshness-cutoff-not-validated",
        "road-10k-plan.symptom-based-test-stop-boundary"
      ],
      "name": "road_10k_v2_readiness_and_missingness",
      "rationale": "Same-distance evidence is most direct, but the freshness boundary and optional test workflow are explicit reversible guardrails. Missingness cannot be reinterpreted as detraining or eligibility.",
      "value": {
        "accepted_direct_baseline_order": [
          "organized_outdoor_road_10k_race_with_elapsed_time",
          "explicit_all_out_standardized_outdoor_road_or_track_10k_time_trial"
        ],
        "adult_scope_unconfirmed_result": "clarification_required",
        "baseline_current_through_completed_days": 56,
        "baseline_stale_from_completed_days": 57,
        "contradictory_constraints_result": "clarification_required",
        "current_symptom_stop_result": "safety_stop",
        "excluded_as_direct_baseline": [
          "five_k_result_or_conversion",
          "race_prediction",
          "passive_fastest_10k_split",
          "threshold_or_lactate_speed_alone",
          "critical_power_or_critical_velocity_alone",
          "activity_average_power",
          "vendor_readiness_or_race_score"
        ],
        "missing_or_stale_baseline_result": "readiness_only",
        "missing_or_stale_history_result": "readiness_only",
        "optional_baseline_test": {
          "automatic_scheduling": false,
          "explicit_athlete_choice_required": true,
          "no_test_alternative": "remain_readiness_only",
          "shared_safety_eligibility_required": true
        },
        "sparse_or_missing_records_establish_detraining": false,
        "unsupported_distance_surface_or_intent_result": "policy_unavailable"
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.recent-history-anchor-without-universal-threshold",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "name": "road_10k_v2_execution_window_and_reassessment",
      "rationale": "No reviewed source validates an exact execution window. Fourteen days is the Product-selected minimum complete two-unit experience; seven days is an advisory review point. Both remain falsifiable workflow guardrails.",
      "value": {
        "advisory_reassessment_after_completed_days": 7,
        "automatic_overwrite_of_adopted_future_days": false,
        "automatic_successor_adoption": false,
        "biological_optimum_claim": false,
        "calendar_schedule_unit_days": 7,
        "committed_proposal_days": 14,
        "dated_goal_planning_horizon": "through_confirmed_primary_event",
        "each_successor_requires": [
          "fresh_eligibility_evaluation",
          "updated_completed_history",
          "updated_event_context",
          "updated_training_pattern_snapshot",
          "explicit_review_and_adoption"
        ],
        "fixed_goal_horizon_required": false,
        "no_automatic_progression_between_reassessments": true,
        "proposal_end_inclusive": true,
        "successor_candidate_triggers": [
          "seven_completed_days",
          "new_or_changed_confirmed_event",
          "material_training_pattern_change",
          "new_qualified_10k_baseline",
          "changed_availability_or_constraint",
          "athlete_requested_review"
        ],
        "undated_goal_planning_horizon": "rolling_until_athlete_changes_or_ends_goal"
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.fixed-progression-not-safety-law"
      ],
      "name": "road_10k_v2_schedule_construction",
      "rationale": "One quality session per week is a conservative Product choice within the indirect one-to-two ceiling. Median, maximum, and constraint caps prevent the first generator from prescribing progression above observed dose.",
      "value": {
        "below_minimum_result": "readiness_only",
        "easy_and_longest_easy_allocation": {
          "automatic_longest_easy_increase": false,
          "integer_remainder_priority": [
            "preferred_longest_easy_day",
            "chronological_day_order"
          ],
          "longest_easy_designation_optional": true,
          "quality_template_minutes_are_allocated_first": true,
          "remaining_minutes_distributed_evenly_across_non_quality_runs": true
        },
        "event_or_benchmark_replaces_planned_quality_in_same_unit": true,
        "no_schedule_result": "readiness_only_no_schedule_within_envelope",
        "non_taper_progression_above_recent_median": false,
        "normal_two_unit_quality_order": {
          "first_unit": "controlled_threshold_quality",
          "second_unit": "ten_k_specific_interval_quality"
        },
        "quality_sessions_per_7_day_unit": 1,
        "requested_above_maximum_result": "clarification_required",
        "schedule_must_satisfy_all_history_constraint_intensity_and_spacing_rules": true,
        "selected_running_days_per_7_day_unit": {
          "deterministic_value": "minimum_of_available_days_recent_modal_days_and_policy_maximum",
          "maximum": 6,
          "minimum": 3
        },
        "session_distance_hard_cap": "recent_maximum_completed_session_distance",
        "session_duration_hard_cap": "minimum_of_recent_maximum_completed_session_minutes_and_athlete_stated_session_limit",
        "target_time_gap_may_raise_load": false,
        "weekly_running_minutes_hard_cap": "minimum_of_recent_maximum_usable_weekly_minutes_and_athlete_stated_weekly_limit",
        "weekly_running_minutes_target": "minimum_of_recent_median_usable_weekly_minutes_and_athlete_stated_weekly_limit"
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.task-specific-capability-not-single-marker",
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.mostly-low-intensity-no-universal-winner"
      ],
      "name": "road_10k_v2_workout_templates",
      "rationale": "The reviewed literature supports broad quality-session families but does not validate these exact repeats or recoveries. The templates are transparent, versioned Product guardrails chosen for deterministic implementation and prospective evaluation.",
      "value": {
        "easy_template": "duration_only",
        "generic_five_k_or_ten_k_pace_conversion": false,
        "generic_percent_of_threshold_or_critical_power": false,
        "inherited_from_outdoor_5k": false,
        "longest_easy_template": "duration_only",
        "target_expression_priority": [
          "current_athlete_specific_active_zone_model",
          "duration_and_session_type_only"
        ],
        "template_must_fit_session_and_weekly_caps": true,
        "template_optimum_claim": false,
        "templates": [
          {
            "steps": [
              {
                "duration_minutes": 10,
                "intended_intensity": "low",
                "kind": "step",
                "phase": "warmup"
              },
              {
                "kind": "repeat",
                "repetitions": 3,
                "steps": [
                  {
                    "duration_minutes": 5,
                    "intended_intensity": "controlled_threshold",
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
                "duration_minutes": 10,
                "intended_intensity": "low",
                "kind": "step",
                "phase": "cooldown"
              }
            ],
            "template_id": "road-10k-controlled-threshold-quality-v1",
            "total_planned_minutes": 41,
            "workout_type": "controlled_threshold_quality"
          },
          {
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
                    "intended_intensity": "ten_k_specific",
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
                "duration_minutes": 10,
                "intended_intensity": "low",
                "kind": "step",
                "phase": "cooldown"
              }
            ],
            "template_id": "road-10k-specific-interval-quality-v1",
            "total_planned_minutes": 40,
            "workout_type": "ten_k_specific_interval_quality"
          }
        ]
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.mostly-low-intensity-no-universal-winner",
        "road-10k-plan.one-to-two-quality-sessions-indirect"
      ],
      "name": "road_10k_v2_intensity_quality_and_spacing",
      "rationale": "Mostly low-intensity training and one-to-two quality sessions have bounded support. Seventy-five percent, one initial quality exposure, and the spacing rules are conservative guardrails rather than universal thresholds.",
      "value": {
        "activity_average_power_allowed_for_intensity_analysis": false,
        "consecutive_quality_running_days_allowed": false,
        "denominator": "all_planned_running_minutes",
        "historical_intensity_source_priority": [
          "activity_splits",
          "activity_samples"
        ],
        "low_intensity_optimum_claim": false,
        "maximum_total_quality_exposures_per_7_day_unit": 1,
        "minimum_intervening_easy_rest_or_non_running_days": 1,
        "minimum_planned_low_intensity_running_minutes_fraction": 0.75,
        "missed_quality_makeup_allowed": false,
        "numerator": "minutes_with_intended_low_intensity",
        "quality_exposures_include": [
          "planned_quality_template",
          "confirmed_race",
          "athlete_scheduled_10k_benchmark"
        ],
        "quality_work_minutes_count_as_low_intensity": false,
        "reduce_or_remove_quality_before_adding_minutes": true,
        "warmup_recovery_and_cooldown_use_actual_intended_intensity": true
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.taper-volume-reduction-supported",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-plan.one-to-two-quality-sessions-indirect"
      ],
      "name": "road_10k_v2_event_benchmark_and_taper",
      "rationale": "The taper range is indirect mixed-endurance evidence. The exact fifty-percent path, event cutoff, and race-dense fallback are deterministic Product guardrails.",
      "value": {
        "confirmed_none": {
          "full_rolling_proposal_allowed": true,
          "optional_10k_benchmark": {
            "athlete_selects_and_confirms_date": true,
            "automatic_scheduling": false,
            "counts_as_quality_and_load": true
          }
        },
        "every_race_or_maximal_effort": {
          "counts_as_quality_session": true,
          "counts_as_training_load": true,
          "requires_spacing_validation": true
        },
        "imported_event_must_be_athlete_confirmed": true,
        "race_dense": {
          "full_proposal_allowed": false,
          "result": "readiness_only_limited_guidance_event_conflict"
        },
        "single_target": {
          "target_8_to_14_days_after_start": "taper_proposal_truncated_to_event_eve",
          "target_fewer_than_8_days_after_start": "limited_near_term_guidance",
          "target_more_than_14_days_after_start": "normal_14_day_rolling_proposal"
        },
        "taper": {
          "direct_recreational_road_10k_validation": false,
          "event_day_reserved_not_generated_as_training_workout": true,
          "event_elapsed_time_included_in_planned_training_minutes": false,
          "evidence_population": "mixed_endurance_athletes",
          "maintain_intensity_exposure_without_adding_quality": true,
          "maintain_recent_frequency_when_constraints_allow": true,
          "no_makeup_or_extra_sharpening": true,
          "personal_performance_gain_claim": false,
          "planned_volume_reduction_fraction": 0.5,
          "reference_schedule": "matching_non_taper_schedule_for_same_dates",
          "supported_window_days_before_event": {
            "maximum": 14,
            "minimum": 8
          }
        }
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.goal-relevant-current-capability-task-specific",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_10k_v2_typed_outcomes",
      "rationale": "Every non-success state remains explicit, preserves the Goal, and avoids borrowing another policy or returning a success-shaped default.",
      "value": {
        "outcomes": {
          "adult_scope_or_constraints_unconfirmed": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "clarification_required"
          },
          "contradictory_input": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "clarification_required"
          },
          "eligible_rolling_proposal": {
            "adoption_required": true,
            "plan_returned": true,
            "route_state": "plan_candidate"
          },
          "eligible_taper_proposal": {
            "adoption_required": true,
            "plan_returned": true,
            "route_state": "plan_candidate"
          },
          "insufficient_recent_history": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "limited_guidance_event_conflict": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "limited_near_term_guidance": {
            "goal_remains_recorded": true,
            "limited_guidance_returned": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "missing_or_stale_direct_baseline": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "no_schedule_within_envelope": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "safety_stop": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          },
          "unsupported_intent_distance_surface_or_population": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "policy_unavailable"
          },
          "validation_failed": {
            "goal_remains_recorded": true,
            "plan_returned": false,
            "route_state": "readiness_only"
          }
        },
        "success_shaped_fallback_allowed": false,
        "unknown_policy_or_schema_version_result": "policy_unavailable",
        "unsupported_distance_fallback": "none"
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.masters-age-change-not-automatic-exclusion",
        "eligibility.evidence-quality-no-personal-probability",
        "population.masters-context-not-age-exclusion",
        "population.sex-effects-are-construct-specific",
        "population.no-general-sex-or-gender-plan-family",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "name": "road_10k_v2_demographic_and_claim_limits",
      "rationale": "The reviewed evidence does not validate general age, sex, gender, or target-gap dose rules. Adult scope is confirmed without creating hidden demographic defaults or personal probabilities.",
      "value": {
        "adult_confirmation_required": true,
        "age_based_dose_modifier": false,
        "causal_plan_benefit_claim": "disabled",
        "exact_age_required": false,
        "gender_based_dose_modifier": false,
        "gender_identity_required": false,
        "medical_diagnosis_clearance_or_treatment": "disabled",
        "personal_adaptation_probability": "disabled",
        "personal_goal_achievement_probability": "disabled",
        "personal_injury_probability": "disabled",
        "physiological_sex_required": false,
        "reproductive_or_pregnancy_context_inferred": false,
        "sex_based_dose_modifier": false,
        "target_time_may": [
          "label_the_goal",
          "compute_a_descriptive_gap_to_qualified_baseline"
        ],
        "target_time_may_not": [
          "increase_frequency",
          "increase_weekly_minutes",
          "lengthen_longest_session",
          "add_quality",
          "override_history_or_symptom_stops"
        ],
        "unknown_demographic_default_allowed": false
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "name": "road_10k_v2_consent_ai_and_state",
      "rationale": "Athlete control and deterministic authority are required regardless of whether optional AI explanation is available.",
      "value": {
        "explicit_adoption_required": true,
        "generator_may_not": [
          "write_or_overwrite_adopted_plan_without_consent",
          "deliver_or_publish_without_consent",
          "schedule_a_missed_workout_makeup",
          "infer_why_a_workout_was_missed",
          "auto_schedule_a_benchmark",
          "confirm_or_change_event_priority"
        ],
        "no_ai_provider_result": "deterministic_result_remains_complete",
        "optional_ai_may": [
          "explain_a_deterministic_result",
          "compare_policy_valid_alternatives",
          "improve_non_authoritative_language"
        ],
        "optional_ai_may_not": [
          "widen_eligibility",
          "invent_missing_context",
          "select_deferred_values",
          "change_template_steps",
          "override_deterministic_validation",
          "approve_adopt_deliver_or_activate"
        ],
        "proposal_is_noncanonical_until_adoption": true,
        "regeneration_creates_versioned_successor": true
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability"
      ],
      "name": "road_10k_v2_privacy_and_audit",
      "rationale": "The generator needs replay provenance, not broad personal context or content telemetry. Stable codes support evaluation without exposing the proposal or athlete values.",
      "value": {
        "audit_fields": [
          "capability_id",
          "policy_version",
          "science_decision_id",
          "source_decision_digest",
          "contract_digest",
          "generator_version",
          "source_goal_id_and_revision",
          "baseline_snapshot_id_and_source",
          "history_cutoff_and_observation_ids",
          "training_pattern_snapshot_version",
          "event_context_snapshot_version",
          "active_zone_model_id_and_version_when_used",
          "normalized_constraints",
          "selected_template_ids",
          "deterministic_input_hash"
        ],
        "deterministic_replay_required": true,
        "narrative_text_required": false,
        "purpose_bounded_context_only": true,
        "sensitive_trait_inference_allowed": false,
        "telemetry_allowed": [
          "stable_readiness_code",
          "stable_generation_result_code",
          "stable_validation_reason_code",
          "policy_and_generator_version",
          "proposal_adoption_rejection_or_successor_event"
        ],
        "telemetry_prohibited": [
          "athlete_text",
          "workout_payload",
          "target_values",
          "personal_context_values",
          "small_or_identifying_cohort_slices"
        ]
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "eligibility.evidence-quality-no-personal-probability",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "name": "road_10k_v2_runtime_evaluation",
      "rationale": "These are predeclared reversible rollout rules, not evidence of efficacy or personal safety. Zero-tolerance deterministic failures pause the path.",
      "value": {
        "dry_run": {
          "deterministic_invariant_breach_tolerance": 0,
          "maximum_single_guardrail_exclusion_fraction": 0.5,
          "replay_mismatch_tolerance": 0,
          "subgroup_exclusion_gap_trigger": {
            "absolute_percentage_points": 20,
            "minimum_cases_per_group": 30
          },
          "unsupported_or_stale_plan_tolerance": 0
        },
        "efficacy_claim_from_process_pilot_allowed": false,
        "evaluate_by": [
          "running_frequency",
          "age_band_when_available_without_default",
          "sex_when_available_and_purpose_permitted_without_default",
          "provider_and_missingness_pattern",
          "dated_vs_undated_goal",
          "taper_vs_non_taper"
        ],
        "opt_in_pilot": {
          "major_edit_definition": {
            "absolute_planned_minutes_change_fraction_greater_than": 0.2,
            "evaluation_window": "one_14_day_committed_proposal",
            "or_scheduled_running_days_changed_at_least": 2
          },
          "maximum_major_edit_fraction": 0.3,
          "maximum_optional_baseline_test_stop_or_noncompletion_fraction": 0.1,
          "maximum_quality_template_rejection_or_major_edit_fraction": 0.3,
          "maximum_symptom_stop_fraction": 0.1,
          "maximum_taper_vs_non_taper_rejection_or_major_edit_gap": 0.15,
          "serious_adverse_events_triggering_immediate_pause": 1
        },
        "pause_or_revise_when_threshold_crossed": true
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.fixed-progression-not-safety-law",
        "road-10k-plan.individual-outcomes-require-error-aware-validation"
      ],
      "name": "road_10k_v2_deferred_scope",
      "rationale": "Each item needs separate evidence and Product review. V2 cannot fill any deferred choice from another distance, a runner identity, prose, or AI.",
      "value": {
        "ai_schedule_or_policy_authority": "not_accepted",
        "automatic_benchmark_scheduling": "not_accepted",
        "demographic_dose_modifiers": "not_accepted",
        "exact_generic_power_or_pace_targets": "not_accepted",
        "first_10k_completion": "not_accepted",
        "full_race_dense_schedule_optimization": "not_accepted",
        "mandatory_or_progressive_long_run": "not_accepted",
        "pediatric_clinical_rehabilitation_or_pregnancy_specific_planning": "not_accepted",
        "personal_success_injury_or_adaptation_probability": "not_accepted",
        "progression_above_recent_typical_load": "not_accepted",
        "return_to_consistency": "not_accepted",
        "sparse_history_generation": "not_accepted",
        "treadmill_trail_cross_country_or_multisport": "not_accepted",
        "two_planned_quality_sessions_per_week": "not_accepted"
      }
    },
    {
      "applies_to": "road-10k-plan-generation-policy-v2",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "road_10k_v2_implementation_and_activation",
      "rationale": "Science acceptance supplies an inactive contract only. Engineering, implementation review, product release, and operations remain separate authorities.",
      "value": {
        "activation_requires_separate_rollout_decision": true,
        "api_behavior_change_in_this_decision": false,
        "capability_registration_in_this_decision": false,
        "generator_implementation_in_this_decision": false,
        "implementation_review_must_bind": [
          "exact_reviewed_code_diff",
          "generated_contract_digest",
          "deterministic_validation_evidence",
          "api_web_and_miniapp_parity_evidence"
        ],
        "proposal_adoption_or_delivery_change_in_this_decision": false,
        "runtime_state_after_science_acceptance": "inactive",
        "web_or_miniapp_availability_change_in_this_decision": false
      }
    }
  ],
  "model_version": "road-10k-plan-generation-policy-v2",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Collect only fields required for plan-generation eligibility, scheduling, replay, and consent.",
    "Keep provider-imported events and profile fields unconfirmed until the athlete confirms their use.",
    "Do not infer sex, gender, reproductive context, health state, event priority, or reasons for missed training.",
    "Keep athlete text, workout payloads, target values, and personal context out of generic logs and telemetry.",
    "Preserve source provenance, purpose, correction, revocation, and deletion behavior for every consumed field."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Implement directly from the accepted V1 boundary",
      "rationale": "V1 deliberately leaves the execution window and exact workout templates unresolved. Delivery may not fill those values from convention or code."
    },
    {
      "alternative": "Commit only seven days",
      "rationale": "Seven days is highly reversible but does not provide the smallest complete two-unit 10 km experience and would create unnecessary review and adoption churn. No source establishes it as biologically superior."
    },
    {
      "alternative": "Copy the 5 km twenty-eight-day block and templates",
      "rationale": "The 5 km horizon, history, session, and exact template guardrails are distance-specific and cannot authorize a 10 km policy."
    },
    {
      "alternative": "Use up to two planned quality sessions whenever history permits",
      "rationale": "Two is an indirect ceiling, not a requirement. The first capability chooses one planned quality session per week to reduce complexity and event-conflict risk while runtime evidence is absent."
    },
    {
      "alternative": "Generate a full plan for race-dense calendars",
      "rationale": "No accepted event-priority, taper, and recovery algorithm resolves multiple material events without guessing athlete intent."
    },
    {
      "alternative": "Use target-time gap, age, sex, or permanent runner level to select dose",
      "rationale": "The evidence does not validate personal dose escalation or a general demographic or identity-based plan family."
    },
    {
      "alternative": "Let AI choose missing schedules or templates",
      "rationale": "AI cannot create evidence, confirm context, choose deferred product values, weaken deterministic validation, approve, adopt, or activate a plan."
    }
  ],
  "safety_implications": [
    "Current injury, illness, or concerning symptom inputs stop generation without diagnosis, treatment, or clearance.",
    "Never use activity average power for intensity analysis; use splits or samples.",
    "Do not exceed recent median or maximum weekly minutes, recent longest completed session, recent completed distance, or athlete-stated time limits.",
    "Preserve at least seventy-five percent planned low-intensity minutes and at most one total quality exposure per seven-day unit.",
    "Treat every confirmed race or athlete-scheduled maximal benchmark as quality and load.",
    "Do not compress, stack, or make up missed quality work.",
    "Do not automatically schedule a maximal 10 km test or benchmark.",
    "Pause after a serious plausibly related event or any deterministic invariant breach."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Generator-ready adult outdoor road 10 km performance policy",
  "user_facing_claim_limits": [
    "Describe fourteen days, seven days, one quality session, exact templates, history counts, freshness, frequency, intensity share, taper, and evaluation thresholds as Praxys guardrails.",
    "Do not describe the exact templates, window, cadence, or allocation algorithm as published or optimal.",
    "Do not promise goal achievement, performance improvement, injury prevention, medical safety, or an individualized probability.",
    "Do not describe missing records as detraining or interruption.",
    "Do not describe age, sex, gender, or runner level as a permanent identity or general dose rule.",
    "Explain that races and benchmarks consume quality and load and that race-dense routing remains unavailable.",
    "Explain direct baseline evidence, indirect taper evidence, missingness, assumptions, alternatives, and the explicit adoption boundary."
  ],
  "validation_plan": [
    "Validate the generated V2 contract and packet digests before human review.",
    "Unit-test the exact capability tuple, purpose sources, direct-baseline hierarchy, 56-day freshness guardrail, eight-week history, and typed missingness outcomes.",
    "Unit-test fourteen-day scheduling, the seven-day advisory reassessment, explicit successor adoption, and no overwrite of adopted future days.",
    "Unit-test every template step, total duration, template ID, one-quality-per-unit rule, low-intensity fraction, quality spacing, and no 5 km template import.",
    "Unit-test history and athlete caps, deterministic allocation and tie-breaking, event replacement of quality, and no progression above recent median load.",
    "Unit-test dated, undated, single-target, eight-to-fourteen-day taper, shorter-horizon, benchmark, and race-dense paths.",
    "Unit-test age and sex missingness without defaults, no target-gap dose escalation, no personal probability, and split-level intensity enforcement.",
    "Replay identical normalized inputs and versions to require identical hashes, workouts, findings, and reason codes.",
    "Dry-run against privacy-safe historical fixtures before capability registration and compare exclusions, subgroup gaps, edits, and invariant failures.",
    "Require API-contract, science, privacy, web/miniapp parity, rendered UI, and deterministic preflight review during implementation."
  ],
  "version": 2
}
```

</details>
