# Science decision review packet: Morning Coach presentation of existing training evidence

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-morning-coach-evidence-presentation-v1`
- **Lifecycle:** `draft`
- **Model version:** `morning-coach-evidence-presentation-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:df51b53d081bbdfab78845fce94e1f531338635301ff4c47d364716b5a5b6b19`
- **Contract digest:** `sha256:e3c7838fa8fd2f9768cc59f8aa9512e708a0682ff9e348c1cedbe41545ac37a1`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Check faithful reuse of existing evidence and runtime boundaries.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `preserve-existing-science` — Preserve authoritative metrics and constrain presentation

- **Question:** Does Coach faithfully present existing eligible evidence?
- **Proposed decision:** Restrict model output to server-eligible identifiers, preserve canonical actions and metric provenance, and render all text on the server.
- **Approval means:**
  - Establishes the bounded presentation and validation specification.
- **This does not authorize:**
  - New formulas, clinical thresholds, prescriptions, or plan mutation.
  - Activation of any inactive science contract.

<details><summary>Traceability: 4 contract groups, 4 evidence claims</summary>

- **Contract groups covered:** `model_selection_boundary`, `observation_eligibility`, `action_boundary`, `presentation_boundary`
- **Evidence claims:** `load.hrv-guidance-limited`, `load.acwr-not-causal-threshold`, `outcome.single-indicator-insufficient`, `outcome.observations-not-causal-explanation`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> This record preserves existing scientific claims and formulas and bounds Coach presentation. It does not activate the shared managed-plan policy.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-morning-coach-evidence-presentation-v1`
- Digest: `sha256:df51b53d081bbdfab78845fce94e1f531338635301ff4c47d364716b5a5b6b19`

> This record preserves existing scientific claims and formulas and bounds Coach presentation. It does not activate the shared managed-plan policy.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:df51b53d081bbdfab78845fce94e1f531338635301ff4c47d364716b5a5b6b19","subject_id":"sdr-morning-coach-evidence-presentation-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

Present existing server-computed recovery, recent activity, seven-day training context, and today's plan through bounded server templates. Model selection may determine presentation emphasis only among eligible evidence, interpretation, and action identifiers. It cannot determine a new training prescription, alter the canonical Today signal, or infer clinical status, individual causality, or guaranteed performance.

### Linked evidence

#### `load.hrv-guidance-limited` — moderate

HRV-guided endurance training may improve some submaximal physiological outcomes, but reviewed pooled evidence did not establish a significant performance or VO2peak advantage over predefined training.

- **Evidence Review:** `evidence-adaptive-training-load-v1`
- **Sources:** `ducking-2021`
- **Limitations:** Only eight studies and 198 participants were included.; Devices, measurement routines, and training algorithms varied.; Results do not validate a universal daily HRV cutoff or exact action.

#### `load.acwr-not-causal-threshold` — moderate

Acute-to-chronic workload ratios have conceptual and statistical limitations and should not be treated as established causal injury-risk zones or automatic prescription thresholds.

- **Evidence Review:** `evidence-adaptive-training-load-v1`
- **Sources:** `impellizzeri-2020`
- **Limitations:** This methodological critique does not show that training history is irrelevant.; It does not validate an alternative universal load threshold.

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

#### `model_selection_boundary` — guardrail

- **Applies to:** daily_brief
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Keep scientific eligibility and visible meaning server-owned.
- **Exact value:**

```json
{
  "allowed_output": [
    "evidence_ids",
    "interpretation_ids",
    "action_ids"
  ],
  "candidate_scope": "authenticated_current_snapshot",
  "extra_fields": "reject",
  "incompatible_combinations": "reject",
  "model_numeric_values": "forbidden",
  "model_prose": "forbidden",
  "unknown_or_ineligible_ids": "reject"
}
```

#### `observation_eligibility` — guardrail

- **Applies to:** daily_brief
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Preserve existing observation validity and freshness semantics.
- **Exact value:**

```json
{
  "baseline": "reuse_existing_theory_and_formula",
  "current_recovery_age_days": [
    0,
    1
  ],
  "dates": "parseable_metric_specific_nonfuture",
  "freshness_basis": "server_as_of_date",
  "historical_context": "dated_and_not_presented_as_current_recovery",
  "stale_or_missing_recovery": "explicit_unavailability",
  "values": "finite_and_valid_for_existing_metric_contract"
}
```

#### `action_boundary` — guardrail

- **Applies to:** daily_brief
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Model presentation must not become a second decision engine.
- **Exact value:**

```json
{
  "allowed_actions": "server_eligible_and_consistent_with_canonical_today",
  "automatic_plan_mutation": "forbidden",
  "canonical_today_signal": "independently_authoritative",
  "intensity_evidence": "splits_or_samples_only",
  "invented_workouts_or_targets": "forbidden",
  "values_and_targets": "server_owned"
}
```

#### `presentation_boundary` — guardrail

- **Applies to:** daily_brief
- **Evidence claims:** _None; product rationale only_
- **Rationale:** Keep visible meaning coherent, attributable, and version-bound.
- **Exact value:**

```json
{
  "data_as_of": "source_only",
  "freshness_change_at_any_boundary": "fail_closed",
  "identity_binding": [
    "as_of_date",
    "source_snapshot",
    "content_version"
  ],
  "recovery_summary": "current_evidence_or_explicit_missingness",
  "theory_references": "structured_server_owned",
  "visible_text": "bilingual_server_templates"
}
```

### Rejected alternatives

#### Accept model-authored explanations or prescriptions.

Identifier selection cannot establish scientific eligibility or authority.

### Applicability

- Existing supported adult recreational-running training context.
- Presentation of already computed metrics and canonical training guidance.

### User-facing claim limits

- Recovery bands are Praxys coaching guardrails, not diagnostic cutoffs.
- No composite recovery score or clinical inference from sleep, HRV, and RHR.
- Seven-day load describes recorded training; it does not establish injury risk.
- Observed associations do not establish individual causality.
- No benefit, safety, or readiness guarantee.

### Safety implications

- Missing, invalid, stale, or incompatible evidence cannot authorize an action.
- Rest and caution recommendations cannot be overridden by presentation selection.

### Privacy implications

- Candidates and feedback remain scoped to the authenticated user.
- Feedback refers to the exact served content version and snapshot.

### Validation plan

- Verify current, normal, rest, no-plan, missing, and stale scenarios.
- Reject invalid IDs, prose, incompatible interpretations, and contradictory actions.
- Verify metric-specific dates, non-finite values, and unavailable baselines.
- Verify rollover and freshness races at generation, persistence, read, and feedback.
- Verify equivalent English and Chinese meaning on web and miniapp.

### Falsification conditions

- Coach changes the canonical training decision or invents a target.
- Missing or stale recovery is presented as normal or current.
- A selected identifier renders unsupported scientific meaning.
- Content or feedback survives a mismatched snapshot, date, or version.

### Decision notes

- Reuses accepted evidence without changing its lifecycle or claims.
- Existing hrv_based theory and canonical Today formulas remain authoritative.
- User-approved implementation scope is supplied by the parent Work Contract.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "daily_brief"
  ],
  "contract_digest": "sha256:e3c7838fa8fd2f9768cc59f8aa9512e708a0682ff9e348c1cedbe41545ac37a1",
  "decision_id": "sdr-morning-coach-evidence-presentation-v1",
  "decision_status": "draft",
  "decision_version": 1,
  "evidence_claim_ids": [
    "load.hrv-guidance-limited",
    "load.acwr-not-causal-threshold",
    "outcome.single-indicator-insufficient",
    "outcome.observations-not-causal-explanation"
  ],
  "evidence_review_ids": [
    "evidence-adaptive-training-load-v1",
    "evidence-plan-outcome-interpretation-v1"
  ],
  "linked_evidence_digests": {
    "evidence-adaptive-training-load-v1": "sha256:101f9e5b3a9eeed9d8777d0cef8cf56f332372568fed32ba812c4f969551d50f",
    "evidence-plan-outcome-interpretation-v1": "sha256:46026c614f9be03950e9e2d9f9e4bb6ef29d12f5882432105a5b522b7fb96956"
  },
  "model_version": "morning-coach-evidence-presentation-v1",
  "parameters": {
    "action_boundary": {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "allowed_actions": "server_eligible_and_consistent_with_canonical_today",
        "automatic_plan_mutation": "forbidden",
        "canonical_today_signal": "independently_authoritative",
        "intensity_evidence": "splits_or_samples_only",
        "invented_workouts_or_targets": "forbidden",
        "values_and_targets": "server_owned"
      }
    },
    "model_selection_boundary": {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "allowed_output": [
          "evidence_ids",
          "interpretation_ids",
          "action_ids"
        ],
        "candidate_scope": "authenticated_current_snapshot",
        "extra_fields": "reject",
        "incompatible_combinations": "reject",
        "model_numeric_values": "forbidden",
        "model_prose": "forbidden",
        "unknown_or_ineligible_ids": "reject"
      }
    },
    "observation_eligibility": {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "baseline": "reuse_existing_theory_and_formula",
        "current_recovery_age_days": [
          0,
          1
        ],
        "dates": "parseable_metric_specific_nonfuture",
        "freshness_basis": "server_as_of_date",
        "historical_context": "dated_and_not_presented_as_current_recovery",
        "stale_or_missing_recovery": "explicit_unavailability",
        "values": "finite_and_valid_for_existing_metric_contract"
      }
    },
    "presentation_boundary": {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "value": {
        "data_as_of": "source_only",
        "freshness_change_at_any_boundary": "fail_closed",
        "identity_binding": [
          "as_of_date",
          "source_snapshot",
          "content_version"
        ],
        "recovery_summary": "current_evidence_or_explicit_missingness",
        "theory_references": "structured_server_owned",
        "visible_text": "bilingual_server_templates"
      }
    }
  },
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:df51b53d081bbdfab78845fce94e1f531338635301ff4c47d364716b5a5b6b19"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "Present existing server-computed recovery, recent activity, seven-day training context, and today's plan through bounded server templates. Model selection may determine presentation emphasis only among eligible evidence, interpretation, and action identifiers. It cannot determine a new training prescription, alter the canonical Today signal, or infer clinical status, individual causality, or guaranteed performance.",
  "affected_surfaces": {
    "apis": [
      "api/deps.py",
      "api/ai.py",
      "api/routes/insights.py"
    ],
    "clients": [
      "web",
      "miniapp"
    ],
    "models": [
      "daily_brief"
    ],
    "science_notes": [
      "recovery",
      "load"
    ]
  },
  "applicability": [
    "Existing supported adult recreational-running training context.",
    "Presentation of already computed metrics and canonical training guidance."
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-10-10",
  "decision_notes": [
    "Reuses accepted evidence without changing its lifecycle or claims.",
    "Existing hrv_based theory and canonical Today formulas remain authoritative.",
    "User-approved implementation scope is supplied by the parent Work Contract."
  ],
  "decision_review": {
    "approval_statement": "This record preserves existing scientific claims and formulas and bounds Coach presentation. It does not activate the shared managed-plan policy.",
    "items": [
      {
        "approval_effect": [
          "Establishes the bounded presentation and validation specification."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "New formulas, clinical thresholds, prescriptions, or plan mutation.",
          "Activation of any inactive science contract."
        ],
        "evidence_claim_ids": [
          "load.hrv-guidance-limited",
          "load.acwr-not-causal-threshold",
          "outcome.single-indicator-insufficient",
          "outcome.observations-not-causal-explanation"
        ],
        "id": "preserve-existing-science",
        "parameter_names": [
          "model_selection_boundary",
          "observation_eligibility",
          "action_boundary",
          "presentation_boundary"
        ],
        "proposed_decision": "Restrict model output to server-eligible identifiers, preserve canonical actions and metric provenance, and render all text on the server.",
        "question": "Does Coach faithfully present existing eligible evidence?",
        "title": "Preserve authoritative metrics and constrain presentation"
      }
    ],
    "reviewer_task": "Check faithful reuse of existing evidence and runtime boundaries."
  },
  "evidence_claim_ids": [
    "load.hrv-guidance-limited",
    "load.acwr-not-causal-threshold",
    "outcome.single-indicator-insufficient",
    "outcome.observations-not-causal-explanation"
  ],
  "evidence_review_ids": [
    "evidence-adaptive-training-load-v1",
    "evidence-plan-outcome-interpretation-v1"
  ],
  "falsification_conditions": [
    "Coach changes the canonical training decision or invents a target.",
    "Missing or stale recovery is presented as normal or current.",
    "A selected identifier renders unsupported scientific meaning.",
    "Content or feedback survives a mismatched snapshot, date, or version."
  ],
  "id": "sdr-morning-coach-evidence-presentation-v1",
  "model_parameters": [
    {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "model_selection_boundary",
      "rationale": "Keep scientific eligibility and visible meaning server-owned.",
      "value": {
        "allowed_output": [
          "evidence_ids",
          "interpretation_ids",
          "action_ids"
        ],
        "candidate_scope": "authenticated_current_snapshot",
        "extra_fields": "reject",
        "incompatible_combinations": "reject",
        "model_numeric_values": "forbidden",
        "model_prose": "forbidden",
        "unknown_or_ineligible_ids": "reject"
      }
    },
    {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "observation_eligibility",
      "rationale": "Preserve existing observation validity and freshness semantics.",
      "value": {
        "baseline": "reuse_existing_theory_and_formula",
        "current_recovery_age_days": [
          0,
          1
        ],
        "dates": "parseable_metric_specific_nonfuture",
        "freshness_basis": "server_as_of_date",
        "historical_context": "dated_and_not_presented_as_current_recovery",
        "stale_or_missing_recovery": "explicit_unavailability",
        "values": "finite_and_valid_for_existing_metric_contract"
      }
    },
    {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "action_boundary",
      "rationale": "Model presentation must not become a second decision engine.",
      "value": {
        "allowed_actions": "server_eligible_and_consistent_with_canonical_today",
        "automatic_plan_mutation": "forbidden",
        "canonical_today_signal": "independently_authoritative",
        "intensity_evidence": "splits_or_samples_only",
        "invented_workouts_or_targets": "forbidden",
        "values_and_targets": "server_owned"
      }
    },
    {
      "applies_to": "daily_brief",
      "classification": "guardrail",
      "evidence_claim_ids": [],
      "name": "presentation_boundary",
      "rationale": "Keep visible meaning coherent, attributable, and version-bound.",
      "value": {
        "data_as_of": "source_only",
        "freshness_change_at_any_boundary": "fail_closed",
        "identity_binding": [
          "as_of_date",
          "source_snapshot",
          "content_version"
        ],
        "recovery_summary": "current_evidence_or_explicit_missingness",
        "theory_references": "structured_server_owned",
        "visible_text": "bilingual_server_templates"
      }
    }
  ],
  "model_version": "morning-coach-evidence-presentation-v1",
  "owners": [
    "team:praxys"
  ],
  "privacy_implications": [
    "Candidates and feedback remain scoped to the authenticated user.",
    "Feedback refers to the exact served content version and snapshot."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Accept model-authored explanations or prescriptions.",
      "rationale": "Identifier selection cannot establish scientific eligibility or authority."
    }
  ],
  "safety_implications": [
    "Missing, invalid, stale, or incompatible evidence cannot authorize an action.",
    "Rest and caution recommendations cannot be overridden by presentation selection."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Morning Coach presentation of existing training evidence",
  "user_facing_claim_limits": [
    "Recovery bands are Praxys coaching guardrails, not diagnostic cutoffs.",
    "No composite recovery score or clinical inference from sleep, HRV, and RHR.",
    "Seven-day load describes recorded training; it does not establish injury risk.",
    "Observed associations do not establish individual causality.",
    "No benefit, safety, or readiness guarantee."
  ],
  "validation_plan": [
    "Verify current, normal, rest, no-plan, missing, and stale scenarios.",
    "Reject invalid IDs, prose, incompatible interpretations, and contradictory actions.",
    "Verify metric-specific dates, non-finite values, and unavailable baselines.",
    "Verify rollover and freshness races at generation, persistence, read, and feedback.",
    "Verify equivalent English and Chinese meaning on web and miniapp."
  ],
  "version": 1
}
```

</details>
