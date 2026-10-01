# Science decision review packet: Bounded raw RR DFA alpha1 for a single running activity

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-activity-dfa-alpha1-v1`
- **Lifecycle:** `accepted`
- **Model version:** `dfa-alpha1-raw120-v1`
- **Runtime state:** `active`
- **Decision digest:** `sha256:3c43b0c3b3eae94bc07a40c27e159110d8ce815206d248e3aaef7ef6e9077288`
- **Contract digest:** `sha256:0029c8753ba7c3a695ec7549ef41f39886280642d2fd70e7973b5022dba751d6`
- **Required decision role:** `decision_approver`
- **Decision approval:** `github:dddtc2005` on `2026-10-01` ([source](https://github.com/praxys-run/praxys/pull/869#issuecomment-5929471354))
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** `github:dddtc2005` on `2026-10-01` ([source](https://github.com/praxys-run/praxys/pull/869#issuecomment-5929471354))

## Your task

Review the fixed raw method, source applicability, conservative guardrails and deferred physiology claims.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `raw-method` — Raw ECG RR method and claim boundaries

- **Question:** Is the bounded descriptive method acceptable within its stated limitations?
- **Proposed decision:** Adopt the specified uncorrected120-second double-direction DFA recipe with the listed source/time/QC guardrails and defer physiological threshold claims.
- **Approval means:**
  - Accept the specified scientific interpretation and parameters after authenticated digest-bound approval.
- **This does not authorize:**
  - Runtime activation, deployment, device accuracy certification, training or medical decisions.

<details><summary>Traceability: 8 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `window`, `rr_quality`, `time_alignment`, `dfa`, `source`, `context`, `claim_limits`, `activation`
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> Approve only the named science decision and displayed digest, including its bounded descriptive interpretation, parameters, applicability, claim limits and activation boundary. Decision approval alone does not authorize runtime activation.

- **Decision approval:** `github:dddtc2005` on `2026-10-01` ([source](https://github.com/praxys-run/praxys/pull/869#issuecomment-5929471354))

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-activity-dfa-alpha1-v1`
- Digest: `sha256:3c43b0c3b3eae94bc07a40c27e159110d8ce815206d248e3aaef7ef6e9077288`

> Approve only the named science decision and displayed digest, including its bounded descriptive interpretation, parameters, applicability, claim limits and activation boundary. Decision approval alone does not authorize runtime activation.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:3c43b0c3b3eae94bc07a40c27e159110d8ce815206d248e3aaef7ef6e9077288","subject_id":"sdr-activity-dfa-alpha1-v1","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

Native ECG chest-strap RR can support descriptive post-run short-scale DFA when source, timer alignment and conservative uncorrected-RR QC pass. Results characterize supported windows only; no personal threshold, fatigue diagnosis or training prescription is inferred. Runtime use requires an accepted decision and implementation approval bound to the active contract, reviewed code diff and validation evidence.

### Linked evidence

#### `dfa.recording-artifacts` — moderate

DFA alpha1 is sensitive to RR artifacts and recording/processing choices; raw ECG-derived intervals require explicit quality checks.

- **Evidence Review:** `evidence-activity-dfa-alpha1-v1`
- **Sources:** `rogers-artifacts-2021`, `schaffarczyk-h10-2022`
- **Limitations:** Neither source validates every registered sensor or the complete Praxys pipeline.; Passing these checks does not prove absence of artifacts.

#### `dfa.short-scale-method` — low

Short-scale DFA over beat intervals is used in exercise research, including running; a 120-second window and scales4–16 are a research-informed analysis recipe.

- **Evidence Review:** `evidence-activity-dfa-alpha1-v1`
- **Sources:** `rogers-artifacts-2021`, `van-rassel-running-2024`
- **Limitations:** The running paper was examined at abstract level only.; Praxys uses raw intervals without correction; it does not claim equivalence to Kubios or another application.; Window timing, minimum beats and quality cutoffs are engineering guardrails.

#### `dfa.threshold-transfer-limited` — low

Agreement between HRV-derived and physiological thresholds is protocol-dependent; this observational running feature cannot identify individual training thresholds from fixed alpha1 cutoffs.

- **Evidence Review:** `evidence-activity-dfa-alpha1-v1`
- **Sources:** `van-rassel-running-2024`, `olieslagers-cycling-2026`
- **Limitations:** Cycling findings do not automatically transfer to continuous running.; No prospective individual threshold or training-prescription validation of the Praxys method exists.

### Reviewed parameters

#### `window` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "min_complete_rr": 200,
  "min_rr_coverage_ms": 117600,
  "seconds": 120,
  "short_block": "report_without_windows",
  "step_seconds": 5
}
```

#### `rr_quality` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "correction": "none",
  "invalid_raw": 65535,
  "minimum_neighbors": 5,
  "neighbor_each_side": 5,
  "range_ms": [
    250,
    2000
  ],
  "reject": "any_suspect_or_incomplete",
  "relative_median_deviation": 0.2,
  "resampling": "none",
  "trim": "trailing_invalid_only",
  "zero_or_interior_invalid": "break_chain"
}
```

#### `time_alignment` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "adjacent_offset_gap_ms": 2000,
  "anchors": "file_order_record_or_primary_timer_boundary",
  "audit": "original_nonpadding_interval_indices_and_local_offset",
  "epoch": "1989-12-31T00:00:00Z",
  "expansion_ms": 1000,
  "local_offset": "clamped_median_packet_midpoint_minus_cumulative_rr",
  "max_anchor_width_ms": 30000,
  "max_local_offset_width_ms": 5000,
  "window_membership": "complete_intervals_from_exact_gathered_packets_only"
}
```

#### `dfa` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "atypical_bounds": [
    0,
    2
  ],
  "boxes": "forward_backward_nonoverlapping_keep_duplicates",
  "clip": false,
  "detrend": "linear_OLS_with_intercept",
  "display_decimals": 2,
  "fluctuation": "sqrt_mean_all_residual_squares",
  "minimum_fluctuation_ms": 1e-12,
  "profile": "cumulative_demeaned_rr_float64",
  "r2": "audit_only_null_zero_variance",
  "scales": [
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16
  ],
  "slope": "equal_weight_OLS_log_F_log_n"
}
```

#### `source` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "direct_native_rr_source_reference": false,
  "garmin_manufacturer": 1,
  "garmin_products": [
    1743,
    1752,
    2327,
    3299,
    3300,
    4130,
    4446,
    4606
  ],
  "identity_change": "ineligible",
  "optical_or_contradictory": "ineligible",
  "polar_manufacturer": 123,
  "polar_native_names": [
    "H10",
    "Polar H10"
  ],
  "required": "native_RR_and_recorded_ECG_and_activity_confirmation",
  "statement_version": "dfa-source-attestation-v1"
}
```

#### `context` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "gates_alpha": false,
  "heart_rate": "60000/mean_RR_ms",
  "max_forward_hold_seconds": 2,
  "min_field_support_seconds": 96,
  "negative_or_nonfinite": "missing",
  "pace": "1000/time_weighted_mean_speed_m_s",
  "power": "time_weighted_mean_stored_precedence",
  "sample_clock": "Unix_seconds",
  "zero": "retained"
}
```

#### `claim_limits` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "coverage": "availability_not_accuracy",
  "diagnosis": false,
  "individual_thresholds": false,
  "kubios_equivalence": false,
  "overall_score": false,
  "threshold_lines": false,
  "time_alignment": "estimated",
  "training_changes": false
}
```

#### `activation` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** User-approved conservative Praxys method contract; published support does not validate these complete operational choices.
- **Exact value:**

```json
{
  "automatic_background_admission": false,
  "contract": "signed_active_only",
  "method_version": "dfa-alpha1-raw120-v1",
  "source_scope": "single_native_running_session_exact_owner_recording"
}
```

### Rejected alternatives

#### Infer RR from sampled BPM or AlphaHRV developer alpha fields.

Neither supplies the required raw beat sequence.

#### Apply universal0.75/0.5 physiological thresholds or silently correct artifacts.

Unsupported transfer and processing differences would widen the approved claim.

### Applicability

- Exactly one native running FIT session with retained raw RR and compatible ECG metadata.
- Per-activity factual owner confirmation; no automatic source assurance in native v1.
- Existing Garmin-platform archive adapter, device-neutral pure core.

### User-facing claim limits

- Label estimated time alignment and source confirmed by you.
- No accuracy percentage, zero-artifact claim, physiological threshold, whole-activity score or medical inference.
- At least200 complete intervals excludes some low-heart-rate windows without implying sensor failure.

### Safety implications

- Descriptive post-run analysis does not clear exercise safety or change training.

### Privacy implications

- Owner-only results and activity confirmations; no serials, raw RR duplication or numeric telemetry.
- Revocation, source deletion, reparse, retention, export and restore manifests follow the approved Trust contract.

### Validation plan

- Independent numerical reference absolute error<=1e-9.
- Synthetic native FIT, timing/QC boundaries, source attestations, deletion races and both-client accessibility.
- Cross-device physiological claims require new prospective evidence and review.

### Falsification conditions

- Any optical or known contradictory source accepted.
- Numerical implementation disagrees with the fixed double-direction method.
- Users interpret availability or alpha as accuracy, fatigue diagnosis or an individual threshold.

### Decision notes

- The initial implementation adopted the user-approved plan contextually and remained draft/inactive without formal evidence, decision or implementation signatures. Activation requires separately recorded, source-verified approvals for the exact final reviewed artifacts.
- Full implementation contract: docs/dev/activity-dfa-alpha1-implementation.md.
- Window membership is limited to complete unchanged RR intervals in the exact gathered packets used for local offset bounds; it never borrows intervals from other packets in the same chain. Actual selected-RR support remains the reported union.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "analysis/activity_dfa.py",
    "sync/rr_recording.py"
  ],
  "contract_digest": "sha256:0029c8753ba7c3a695ec7549ef41f39886280642d2fd70e7973b5022dba751d6",
  "decision_id": "sdr-activity-dfa-alpha1-v1",
  "decision_status": "accepted",
  "decision_version": 1,
  "evidence_claim_ids": [
    "dfa.recording-artifacts",
    "dfa.short-scale-method",
    "dfa.threshold-transfer-limited"
  ],
  "evidence_review_ids": [
    "evidence-activity-dfa-alpha1-v1"
  ],
  "linked_evidence_digests": {
    "evidence-activity-dfa-alpha1-v1": "sha256:dcb55292c89c9721fbf4d7133f94e34487e5de50efd4ffc94b36a5a7eff9a73f"
  },
  "model_version": "dfa-alpha1-raw120-v1",
  "parameters": {
    "activation": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "automatic_background_admission": false,
        "contract": "signed_active_only",
        "method_version": "dfa-alpha1-raw120-v1",
        "source_scope": "single_native_running_session_exact_owner_recording"
      }
    },
    "claim_limits": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "coverage": "availability_not_accuracy",
        "diagnosis": false,
        "individual_thresholds": false,
        "kubios_equivalence": false,
        "overall_score": false,
        "threshold_lines": false,
        "time_alignment": "estimated",
        "training_changes": false
      }
    },
    "context": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "gates_alpha": false,
        "heart_rate": "60000/mean_RR_ms",
        "max_forward_hold_seconds": 2,
        "min_field_support_seconds": 96,
        "negative_or_nonfinite": "missing",
        "pace": "1000/time_weighted_mean_speed_m_s",
        "power": "time_weighted_mean_stored_precedence",
        "sample_clock": "Unix_seconds",
        "zero": "retained"
      }
    },
    "dfa": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "atypical_bounds": [
          0,
          2
        ],
        "boxes": "forward_backward_nonoverlapping_keep_duplicates",
        "clip": false,
        "detrend": "linear_OLS_with_intercept",
        "display_decimals": 2,
        "fluctuation": "sqrt_mean_all_residual_squares",
        "minimum_fluctuation_ms": 1e-12,
        "profile": "cumulative_demeaned_rr_float64",
        "r2": "audit_only_null_zero_variance",
        "scales": [
          4,
          5,
          6,
          7,
          8,
          9,
          10,
          11,
          12,
          13,
          14,
          15,
          16
        ],
        "slope": "equal_weight_OLS_log_F_log_n"
      }
    },
    "rr_quality": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "correction": "none",
        "invalid_raw": 65535,
        "minimum_neighbors": 5,
        "neighbor_each_side": 5,
        "range_ms": [
          250,
          2000
        ],
        "reject": "any_suspect_or_incomplete",
        "relative_median_deviation": 0.2,
        "resampling": "none",
        "trim": "trailing_invalid_only",
        "zero_or_interior_invalid": "break_chain"
      }
    },
    "source": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "direct_native_rr_source_reference": false,
        "garmin_manufacturer": 1,
        "garmin_products": [
          1743,
          1752,
          2327,
          3299,
          3300,
          4130,
          4446,
          4606
        ],
        "identity_change": "ineligible",
        "optical_or_contradictory": "ineligible",
        "polar_manufacturer": 123,
        "polar_native_names": [
          "H10",
          "Polar H10"
        ],
        "required": "native_RR_and_recorded_ECG_and_activity_confirmation",
        "statement_version": "dfa-source-attestation-v1"
      }
    },
    "time_alignment": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "adjacent_offset_gap_ms": 2000,
        "anchors": "file_order_record_or_primary_timer_boundary",
        "audit": "original_nonpadding_interval_indices_and_local_offset",
        "epoch": "1989-12-31T00:00:00Z",
        "expansion_ms": 1000,
        "local_offset": "clamped_median_packet_midpoint_minus_cumulative_rr",
        "max_anchor_width_ms": 30000,
        "max_local_offset_width_ms": 5000,
        "window_membership": "complete_intervals_from_exact_gathered_packets_only"
      }
    },
    "window": {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "min_complete_rr": 200,
        "min_rr_coverage_ms": 117600,
        "seconds": 120,
        "short_block": "report_without_windows",
        "step_seconds": 5
      }
    }
  },
  "runtime_state": "active",
  "schema_version": 1,
  "source_decision_digest": "sha256:3c43b0c3b3eae94bc07a40c27e159110d8ce815206d248e3aaef7ef6e9077288"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "Native ECG chest-strap RR can support descriptive post-run short-scale DFA when source, timer alignment and conservative uncorrected-RR QC pass. Results characterize supported windows only; no personal threshold, fatigue diagnosis or training prescription is inferred. Runtime use requires an accepted decision and implementation approval bound to the active contract, reviewed code diff and validation evidence.",
  "affected_surfaces": {
    "apis": [
      "/api/activities/{activity_id}/dfa-alpha1"
    ],
    "clients": [
      "web History",
      "miniapp Analysis activities"
    ],
    "models": [
      "analysis/activity_dfa.py",
      "sync/rr_recording.py"
    ],
    "science_notes": [
      "Post-run DFA method and guardrails"
    ]
  },
  "applicability": [
    "Exactly one native running FIT session with retained raw RR and compatible ECG metadata.",
    "Per-activity factual owner confirmation; no automatic source assurance in native v1.",
    "Existing Garmin-platform archive adapter, device-neutral pure core."
  ],
  "artifact_policy": {
    "runtime_state": "active"
  },
  "decision_date": "2026-09-27",
  "decision_notes": [
    "The initial implementation adopted the user-approved plan contextually and remained draft/inactive without formal evidence, decision or implementation signatures. Activation requires separately recorded, source-verified approvals for the exact final reviewed artifacts.",
    "Full implementation contract: docs/dev/activity-dfa-alpha1-implementation.md.",
    "Window membership is limited to complete unchanged RR intervals in the exact gathered packets used for local offset bounds; it never borrows intervals from other packets in the same chain. Actual selected-RR support remains the reported union."
  ],
  "decision_review": {
    "approval_statement": "Approve only the named science decision and displayed digest, including its bounded descriptive interpretation, parameters, applicability, claim limits and activation boundary. Decision approval alone does not authorize runtime activation.",
    "items": [
      {
        "approval_effect": [
          "Accept the specified scientific interpretation and parameters after authenticated digest-bound approval."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Runtime activation, deployment, device accuracy certification, training or medical decisions."
        ],
        "evidence_claim_ids": [
          "dfa.recording-artifacts",
          "dfa.short-scale-method",
          "dfa.threshold-transfer-limited"
        ],
        "id": "raw-method",
        "parameter_names": [
          "window",
          "rr_quality",
          "time_alignment",
          "dfa",
          "source",
          "context",
          "claim_limits",
          "activation"
        ],
        "proposed_decision": "Adopt the specified uncorrected120-second double-direction DFA recipe with the listed source/time/QC guardrails and defer physiological threshold claims.",
        "question": "Is the bounded descriptive method acceptable within its stated limitations?",
        "title": "Raw ECG RR method and claim boundaries"
      }
    ],
    "reviewer_task": "Review the fixed raw method, source applicability, conservative guardrails and deferred physiology claims."
  },
  "evidence_claim_ids": [
    "dfa.recording-artifacts",
    "dfa.short-scale-method",
    "dfa.threshold-transfer-limited"
  ],
  "evidence_review_ids": [
    "evidence-activity-dfa-alpha1-v1"
  ],
  "falsification_conditions": [
    "Any optical or known contradictory source accepted.",
    "Numerical implementation disagrees with the fixed double-direction method.",
    "Users interpret availability or alpha as accuracy, fatigue diagnosis or an individual threshold."
  ],
  "id": "sdr-activity-dfa-alpha1-v1",
  "model_parameters": [
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "window",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "min_complete_rr": 200,
        "min_rr_coverage_ms": 117600,
        "seconds": 120,
        "short_block": "report_without_windows",
        "step_seconds": 5
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "rr_quality",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "correction": "none",
        "invalid_raw": 65535,
        "minimum_neighbors": 5,
        "neighbor_each_side": 5,
        "range_ms": [
          250,
          2000
        ],
        "reject": "any_suspect_or_incomplete",
        "relative_median_deviation": 0.2,
        "resampling": "none",
        "trim": "trailing_invalid_only",
        "zero_or_interior_invalid": "break_chain"
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "time_alignment",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "adjacent_offset_gap_ms": 2000,
        "anchors": "file_order_record_or_primary_timer_boundary",
        "audit": "original_nonpadding_interval_indices_and_local_offset",
        "epoch": "1989-12-31T00:00:00Z",
        "expansion_ms": 1000,
        "local_offset": "clamped_median_packet_midpoint_minus_cumulative_rr",
        "max_anchor_width_ms": 30000,
        "max_local_offset_width_ms": 5000,
        "window_membership": "complete_intervals_from_exact_gathered_packets_only"
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "dfa",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "atypical_bounds": [
          0,
          2
        ],
        "boxes": "forward_backward_nonoverlapping_keep_duplicates",
        "clip": false,
        "detrend": "linear_OLS_with_intercept",
        "display_decimals": 2,
        "fluctuation": "sqrt_mean_all_residual_squares",
        "minimum_fluctuation_ms": 1e-12,
        "profile": "cumulative_demeaned_rr_float64",
        "r2": "audit_only_null_zero_variance",
        "scales": [
          4,
          5,
          6,
          7,
          8,
          9,
          10,
          11,
          12,
          13,
          14,
          15,
          16
        ],
        "slope": "equal_weight_OLS_log_F_log_n"
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "source",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "direct_native_rr_source_reference": false,
        "garmin_manufacturer": 1,
        "garmin_products": [
          1743,
          1752,
          2327,
          3299,
          3300,
          4130,
          4446,
          4606
        ],
        "identity_change": "ineligible",
        "optical_or_contradictory": "ineligible",
        "polar_manufacturer": 123,
        "polar_native_names": [
          "H10",
          "Polar H10"
        ],
        "required": "native_RR_and_recorded_ECG_and_activity_confirmation",
        "statement_version": "dfa-source-attestation-v1"
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "context",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "gates_alpha": false,
        "heart_rate": "60000/mean_RR_ms",
        "max_forward_hold_seconds": 2,
        "min_field_support_seconds": 96,
        "negative_or_nonfinite": "missing",
        "pace": "1000/time_weighted_mean_speed_m_s",
        "power": "time_weighted_mean_stored_precedence",
        "sample_clock": "Unix_seconds",
        "zero": "retained"
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "claim_limits",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "coverage": "availability_not_accuracy",
        "diagnosis": false,
        "individual_thresholds": false,
        "kubios_equivalence": false,
        "overall_score": false,
        "threshold_lines": false,
        "time_alignment": "estimated",
        "training_changes": false
      }
    },
    {
      "applies_to": "post-run DFA alpha1 v1",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "activation",
      "rationale": "User-approved conservative Praxys method contract; published support does not validate these complete operational choices.",
      "value": {
        "automatic_background_admission": false,
        "contract": "signed_active_only",
        "method_version": "dfa-alpha1-raw120-v1",
        "source_scope": "single_native_running_session_exact_owner_recording"
      }
    }
  ],
  "model_version": "dfa-alpha1-raw120-v1",
  "owners": [
    "agent:science"
  ],
  "privacy_implications": [
    "Owner-only results and activity confirmations; no serials, raw RR duplication or numeric telemetry.",
    "Revocation, source deletion, reparse, retention, export and restore manifests follow the approved Trust contract."
  ],
  "rejected_alternatives": [
    {
      "alternative": "Infer RR from sampled BPM or AlphaHRV developer alpha fields.",
      "rationale": "Neither supplies the required raw beat sequence."
    },
    {
      "alternative": "Apply universal0.75/0.5 physiological thresholds or silently correct artifacts.",
      "rationale": "Unsupported transfer and processing differences would widen the approved claim."
    }
  ],
  "safety_implications": [
    "Descriptive post-run analysis does not clear exercise safety or change training."
  ],
  "schema_version": 1,
  "supersedes": [],
  "title": "Bounded raw RR DFA alpha1 for a single running activity",
  "user_facing_claim_limits": [
    "Label estimated time alignment and source confirmed by you.",
    "No accuracy percentage, zero-artifact claim, physiological threshold, whole-activity score or medical inference.",
    "At least200 complete intervals excludes some low-heart-rate windows without implying sensor failure."
  ],
  "validation_plan": [
    "Independent numerical reference absolute error<=1e-9.",
    "Synthetic native FIT, timing/QC boundaries, source attestations, deletion races and both-client accessibility.",
    "Cross-device physiological claims require new prospective evidence and review."
  ],
  "version": 1
}
```

</details>
