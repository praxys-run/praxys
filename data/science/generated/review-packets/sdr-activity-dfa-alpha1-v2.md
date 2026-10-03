# Science decision review packet: Conditional automatic raw DFA admission with metadata-inferred source

> Start with the decision sheet. The audit appendix preserves every code-consumed field, but it is not the reviewer's primary task.

- **Record:** `sdr-activity-dfa-alpha1-v2`
- **Lifecycle:** `draft`
- **Model version:** `dfa-alpha1-raw120-v1`
- **Runtime state:** `inactive`
- **Decision digest:** `sha256:80776068bcf39de5383743bdf419f7c84c7494a6fc82fd023240d00bc2aefee4`
- **Contract digest:** `sha256:c74a05be3ece8b3d95f6ff53e5b32fc8d885f51b9a0732b75975d7bf1d8faba1`
- **Required decision role:** `decision_approver`
- **Decision approval:** _Pending_
- **Required activation role:** `implementation_reviewer`
- **Implementation approval:** _Pending_

## Your task

Review only unchanged baseline inheritance and narrow source/admission amendment. Product user-value approval is already recorded separately; implementation activation remains a different approval role.

Choose one outcome:

1. **Approve the decision sheet as a unit.** This accepts both the proposed decisions and the explicit deferrals below.
2. **Request changes by item ID.** Do this when any proposal, effect, or non-authorization is unclear or wrong.

Do not approve merely because the audit appendix looks reasonable or because you found no obvious problem while skimming it.

## Decision sheet

### Proposed decisions to approve

#### `unchanged-method` — Retain complete numerical baseline

- **Question:** Retain complete numerical baseline?
- **Proposed decision:** Keep exact dfa-alpha1-raw120-v1 formula, constants, quality and timing.
- **Approval means:**
  - Accept only the named scientific/source interpretation after authenticated digest-bound decision approval.
- **This does not authorize:**
  - Runtime activation, gate enablement, deployment, fabricated human source statements or changed numerical QC.

<details><summary>Traceability: 5 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `window`, `rr_quality`, `time_alignment`, `dfa`, `context`
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`

</details>

#### `inferred-source` — Admit narrow metadata-inferred ECG-type/model source

- **Question:** Admit narrow metadata-inferred ECG-type/model source?
- **Proposed decision:** Accept branch-specific user_confirmed versus metadata_inferred assurance and the all-candidate/same-ECG-rule metadata predicate, with unknown versus contradiction outcomes.
- **Approval means:**
  - Accept only the named scientific/source interpretation after authenticated digest-bound decision approval.
- **This does not authorize:**
  - Runtime activation, gate enablement, deployment, fabricated human source statements or changed numerical QC.

<details><summary>Traceability: 4 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `source`, `source_assurance`, `automatic_source`, `claim_limits`
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`

</details>

#### `conditional-admission` — Default-off conditional automatic admission and immutable bindings

- **Question:** Default-off conditional automatic admission and immutable bindings?
- **Proposed decision:** Allow automatic completed-sync computation only under a separately active source contract, gate and authority; preserve independent manual v1path until an approved lifecycle migration.
- **Approval means:**
  - Accept only the named scientific/source interpretation after authenticated digest-bound decision approval.
- **This does not authorize:**
  - Runtime activation, gate enablement, deployment, fabricated human source statements or changed numerical QC.

<details><summary>Traceability: 2 contract groups, 3 evidence claims</summary>

- **Contract groups covered:** `activation`, `binding_and_versions`
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`

</details>

## Approval statement

A decision approval bound to the displayed digest attests:

> Approve the displayed source/admission decision digest only; this does not activate runtime or enable the server gate.

- **Decision approval:** _Pending_

### Decision approval

Approve in this GitHub comment format or in an authenticated agent session. For session approval, the agent mirrors this exact statement to the human-authenticated PR comment before automation records the YAML and lifecycle transition.

```markdown
Praxys science approval — **APPROVE**

- Role: `decision_approver`
- Subject: `sdr-activity-dfa-alpha1-v2`
- Digest: `sha256:80776068bcf39de5383743bdf419f7c84c7494a6fc82fd023240d00bc2aefee4`

> Approve the displayed source/admission decision digest only; this does not activate runtime or enable the server gate.

<!-- praxys-science-approval:v1
{"role":"decision_approver","subject_digest":"sha256:80776068bcf39de5383743bdf419f7c84c7494a6fc82fd023240d00bc2aefee4","subject_id":"sdr-activity-dfa-alpha1-v2","subject_kind":"science_decision"}
-->
```

## Audit appendix

<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>

### Accepted interpretation

DRAFT INACTIVE PROPOSAL: preserve the complete dfa-alpha1-raw120-v1 numerical method. Conditionally allow automatic completed-sync analysis under an independently active source/admission contract and default-off server gate, using metadata_inferred source assurance for the specified recorded ECG-type/model predicate. Such recordings compute without a per-activity human assertion. Manual owner-confirmed analysis remains a distinct branch; neither inference nor flag evaluation proves per-interval sensor provenance or individual accuracy.

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
- **Rationale:** The supported modality/model registry is unchanged. Manual source assurance retains a factual per-activity owner statement. Automatic source assurance is a narrow metadata inference and must not assert measured per-beat attribution.
- **Exact value:**

```json
{
  "automatic_required": "native_RR_and_all_recorded_HR_candidates_same_compatible_ECG_rule_and_interpretable_external_transport",
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
  "manual_required": "native_RR_and_recorded_ECG_and_activity_confirmation",
  "optical_or_contradictory": "positive_optical_RR_or_known_external_optical_or_identity_source_contradiction_ineligible",
  "polar_manufacturer": 123,
  "polar_native_names": [
    "H10",
    "Polar H10"
  ],
  "required": "native_RR_and_recorded_ECG_and_branch_specific_assurance",
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
- **Rationale:** Preserve all physiological claim limits and distinguish source evidence categories. Source inference is a Product/Science guardrail, not a measured accuracy effect.
- **Exact value:**

```json
{
  "coverage": "availability_not_accuracy",
  "diagnosis": false,
  "individual_thresholds": false,
  "kubios_equivalence": false,
  "metadata_inference_proves_per_interval_source": false,
  "overall_score": false,
  "source_assurance": "branch_specific_user_confirmed_or_metadata_inferred",
  "threshold_lines": false,
  "time_alignment": "estimated",
  "training_changes": false
}
```

#### `activation` — guardrail

- **Applies to:** post-run DFA alpha1 v1
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** Conditional admission amendment for the approved Product scope. Actual generated runtime state remains inactive; the gate alone cannot authorize inference or activate science. Keep manual v1 contract authority distinct until an approved migration.
- **Exact value:**

```json
{
  "automatic_background_admission": true,
  "automatic_condition": "default_off_server_gate_and_active_signed_v2_contract_and_current_metadata_predicate_and_owner_processing_authority",
  "automatic_contract_id": "sdr-activity-dfa-alpha1-v2",
  "automatic_scope": "newly_completed_sync_only",
  "contract": "signed_active_only",
  "historical_backfill": false,
  "manual_contract_id": "sdr-activity-dfa-alpha1-v1",
  "method_version": "dfa-alpha1-raw120-v1",
  "numerical_method_unchanged": true,
  "source_scope": "single_native_running_session_exact_owner_recording"
}
```

#### `source_assurance` — guardrail

- **Applies to:** conditional automatic admission only; no numerical change
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** Metadata inference is not human confirmation or direct native RR source attribution. Never populate a confirmation table by automation.
- **Exact value:**

```json
{
  "allowed": [
    "user_confirmed",
    "metadata_inferred"
  ],
  "direct_rr_sensor_fk": false,
  "metadata_inferred_confirmation_id": null,
  "metadata_inferred_human_confirmation": false,
  "metadata_inferred_requires": "immutable_typed_metadata_proof_bound_to_exact_recording_and_source_rule",
  "metadata_projection_version": "rr-native-source-metadata-v2",
  "public_sensor_identity": "recording_local_opaque_handles_and_compatible_model_labels",
  "published_signal_accuracy": false,
  "user_confirmed_requires": "immutable_factual_owner_confirmation_bound_to_exact_recording_and_sensor_rule"
}
```

#### `automatic_source` — guardrail

- **Applies to:** conditional automatic admission only; no numerical change
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** Same-model all-candidate modality inference is deliberately broader than one physical-sensor certainty and remains honestly labelled. It can complete ordinary single-strap and same-model ANT+/BLE inventories without inventing physical identity. Unknown competing sources require clarification; positive contradictions cannot be overridden.
- **Exact value:**

```json
{
  "acceptable_transport_class_pairs": [
    {
      "device_type": 120,
      "label": "ANT_PLUS_heart_rate",
      "source_type": 1
    },
    {
      "device_type": 1,
      "label": "BLE_heart_rate",
      "source_type": 3
    }
  ],
  "candidate_selection": "all_recorded_native_external_HR_handles_and_explicit_local_wrist_HR_inventory",
  "compatible_registry": "unchanged_v1_Garmin_products_or_Polar_native_H10_identity",
  "different_compatible_models": "source_unresolved",
  "eligible": "one_or_more_coherent_external_HR_handles_all_registered_ECG_and_same_compatibility_rule",
  "explicit_local_wrist_HR_inventory": "source_unresolved_not_proven_optical_RR",
  "explicit_local_wrist_HR_pair": {
    "device_type": 10,
    "outcome": "source_unresolved_inventory_not_RR_assignment",
    "source_type": 5
  },
  "generic_watch_optical_capability": "does_not_block",
  "known_optical_external_HR_identity": "ineligible",
  "missing_or_uninterpretable_transport_class": "source_unresolved",
  "multiple_same_model_transport_handles": "eligible_as_ECG_type_model_inference_preserve_each_handle_no_physical_merge",
  "ordinary_raw_QC_or_gap_failures": "unchanged_numerical_window_rules_no_global_source_diagnosis",
  "positive_RR_source_switch_or_mixed_source_evidence": "ineligible",
  "provenance_claim": "recorded_compatible_ECG_type_model_inferred_not_per_beat_source_verified",
  "provider": "garmin",
  "require_current_archive_parse_hash": true,
  "require_explicit_recording_local_handle": true,
  "rr_field": "native_hrv78_time0_only",
  "rule_version": "dfa-native-ecg-metadata-v1",
  "same_handle_identity_contradiction": "ineligible",
  "session": "exactly_one_native_running_session",
  "unknown_external_HR_identity": "source_unresolved"
}
```

#### `binding_and_versions` — guardrail

- **Applies to:** conditional automatic admission only; no numerical change
- **Evidence claims:** `dfa.recording-artifacts`, `dfa.short-scale-method`, `dfa.threshold-transfer-limited`
- **Rationale:** Distinct immutable source and contract digests prevent inferred/manual authority mixing while the full fixed numerical recipe remains unchanged. Trust/Architecture own lifecycle persistence and rights fences.
- **Exact value:**

```json
{
  "frozen_parameter_digest": "sha256:f36cf405cbf84aef9d04e6e52aa1600662ce0254de1b230d7372ff035ebede11",
  "frozen_parameter_groups": [
    "window",
    "rr_quality",
    "time_alignment",
    "dfa",
    "context"
  ],
  "gate_off_automatic_execution_or_publication": false,
  "idempotency_includes": [
    "exact_recording_ref",
    "source_assurance",
    "source_evidence_digest",
    "source_rule_version",
    "numerical_method_version",
    "science_contract_digest",
    "metadata_projection_version"
  ],
  "manual_statement_version": "dfa-source-attestation-v1",
  "metadata_projection_version": "rr-native-source-metadata-v2",
  "numerical_method_version": "dfa-alpha1-raw120-v1",
  "revalidate_at": [
    "admission",
    "execution",
    "publication"
  ],
  "source_rule_version": "dfa-native-ecg-metadata-v1",
  "view_focus_poll_starts_work": false
}
```

### Rejected alternatives

#### Infer RR from sampled BPM or AlphaHRV developer alpha fields.

Neither supplies the required raw beat sequence.

#### Apply universal0.75/0.5 physiological thresholds or silently correct artifacts.

Unsupported transfer and processing differences would widen the approved claim.

### Applicability

- Exactly one native running FIT session under the existing Garmin archive adapter with unchanged raw RR timing/QC; source qualification is branch-specific.
- Automatic: each explicitly recorded external HR handle has coherent ANT+/HR or BLE/HR metadata and an unchanged supported ECG compatibility rule; all candidates share that rule, including same-model separate radio handles.
- Unknown external HR, missing transport/class, different supported ECG models or explicit local wrist-HR inventory produce source_unresolved; ordinary watch optical capability does not.
- Known external optical identity, source-handle identity contradiction or positive mixed/switching source evidence remains ineligible.
- Source assurance is a modality/model inference from recording metadata, never a guarantee of the exact physical or per-interval native RR source.

### User-facing claim limits

- Metadata-inferred output: Source inferred from recording metadata; no source confirmed by you or verified-source label.
- User-confirmed output: preserve the existing factual owner-confirmation label and exact statement revision.
- Same-model multiple recorded handles may represent radio connections or separate devices; do not merge physical identities or promise one strap.
- Preserve estimated time alignment, availability-not-accuracy, no overall score, no threshold lines, no individual threshold, no diagnosis/training change or cross-app equivalence.

### Safety implications

- Descriptive post-run analysis does not clear exercise safety or change training.

### Privacy implications

- Owner-only inferred proof and result; no automatic human confirmation row, serial/address persistence, private raw metadata duplication or RR/source data in gate telemetry.
- Source evidence binding, deletion/revocation/reparse/restore, processing consent, feature-gate fences and retained proof schema require the separate Trust/Architecture acceptance.

### Validation plan

- Golden numeric fixture outputs under v1manual and v2automatic are identical except typed assurance/provenance metadata; frozen numerical parameter digest must match.
- Synthetic native FIT source matrix: eligible oneANT+ECG, oneBLEECG, twoANT+/BLEsame-model handles without physical merge, repeated coherent handle descriptions, generic optically capable watch plus supported externalECG.
- Source-unresolved cases: differentcompatibleECGmodels, unknowncompetingexternalHR, missing source_type/device_type/index, explicit localwhr inventory, ambiguous handle transport reuse.
- Ineligible cases: positively knownexternalopticalHRidentity, samehandle identitycontradiction, positiveoptical/external switching or mixedRRsourceevidence.
- Positive source inference completes automatic numerical phase without any Confirmation row, per-activity click or confirmed:true. Baseline raw QC can still produce no_valid_windows or timing failures truthfully.
- GateOFF, failing gate wrapper or inactive/wrong science contract never admit/execute/publishautomaticresults; manual existing authority remains independent.
- Independent Science/Trust/Quality review tests exact source-proof binding and stale/input/gate/rights fences before production activation.

### Falsification conditions

- Automation fabricates a factual owner confirmation or labels metadata_inferred as user_confirmed/verified.
- Known contradictory/optical source admitted; ambiguous inventory silently claimed to be physically one sensor or direct native RR provenance.
- A positive eligible metadata predicate invariably requires another manual confirmation/start rather than completing.
- Any numerical/QC/formula/timing/coverage correction changes under this source-only amendment.
- DefaultOFF, inactive science or processing/gate revocation permits new automatic work/publication.

### Decision notes

- PDR logical digest sha256:086c52e80679e9d0a89a6f28ba70bda7d351076ed4c8933b77e32ca8b6f2501c verified. User Product implementation approval does not originate scientific signatures.
- Work classification sha256:1f80b1e4ff20a296d77cc15154af9d8826ea75e8d9726f2be624eb6292c11cff;route sha256:a45599ca884e6edfe42e642bddbf2026d027776c58081de6e35ec91f59892904.
- Existing v1EvidenceReview and SDR are draft/inactive here. This proposed v2 successor uses no active supersession links; baseline is not rewritten.
- Transitional strategy: manual uses its separately active v1contract; automatic requires separately active v2contract and servergate. If an eventual approved lifecycle supersedes v1, atomically migrate manual lookup to v2user_confirmed branch and all v1links before disabling v1; no partialtransition.
- Reuse existing baselineEvidenceReview; source inference parameters are explicit operational guardrails, not new published physiological validation. Five reviewed papers/source limits in the earlier research bundle remain contextual.
- The3%/5%corrected-method candidate record is a different inactive research object and is excluded from this amendment.
- SDK metadata facts re-used from coordinator verification: global78time has no RR-sensor FK; source_type/device_type is source inventory. Localwhr presence is not proven optical RR; dive_settings source fields do not establish running provenance.
- Inventory-only optical capability or localwhr device presence does not constitute positive optical-RR contradiction; new v2 source-group wording clarifies that distinction. Existing v1manual record remains unchanged.

</details>

<details><summary>Exact machine contract — code consumption audit</summary>

```json
{
  "affected_models": [
    "analysis/activity_dfa.py",
    "sync/rr_recording.py"
  ],
  "contract_digest": "sha256:c74a05be3ece8b3d95f6ff53e5b32fc8d885f51b9a0732b75975d7bf1d8faba1",
  "decision_id": "sdr-activity-dfa-alpha1-v2",
  "decision_status": "draft",
  "decision_version": 2,
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
        "automatic_background_admission": true,
        "automatic_condition": "default_off_server_gate_and_active_signed_v2_contract_and_current_metadata_predicate_and_owner_processing_authority",
        "automatic_contract_id": "sdr-activity-dfa-alpha1-v2",
        "automatic_scope": "newly_completed_sync_only",
        "contract": "signed_active_only",
        "historical_backfill": false,
        "manual_contract_id": "sdr-activity-dfa-alpha1-v1",
        "method_version": "dfa-alpha1-raw120-v1",
        "numerical_method_unchanged": true,
        "source_scope": "single_native_running_session_exact_owner_recording"
      }
    },
    "automatic_source": {
      "applies_to": "conditional automatic admission only; no numerical change",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "acceptable_transport_class_pairs": [
          {
            "device_type": 120,
            "label": "ANT_PLUS_heart_rate",
            "source_type": 1
          },
          {
            "device_type": 1,
            "label": "BLE_heart_rate",
            "source_type": 3
          }
        ],
        "candidate_selection": "all_recorded_native_external_HR_handles_and_explicit_local_wrist_HR_inventory",
        "compatible_registry": "unchanged_v1_Garmin_products_or_Polar_native_H10_identity",
        "different_compatible_models": "source_unresolved",
        "eligible": "one_or_more_coherent_external_HR_handles_all_registered_ECG_and_same_compatibility_rule",
        "explicit_local_wrist_HR_inventory": "source_unresolved_not_proven_optical_RR",
        "explicit_local_wrist_HR_pair": {
          "device_type": 10,
          "outcome": "source_unresolved_inventory_not_RR_assignment",
          "source_type": 5
        },
        "generic_watch_optical_capability": "does_not_block",
        "known_optical_external_HR_identity": "ineligible",
        "missing_or_uninterpretable_transport_class": "source_unresolved",
        "multiple_same_model_transport_handles": "eligible_as_ECG_type_model_inference_preserve_each_handle_no_physical_merge",
        "ordinary_raw_QC_or_gap_failures": "unchanged_numerical_window_rules_no_global_source_diagnosis",
        "positive_RR_source_switch_or_mixed_source_evidence": "ineligible",
        "provenance_claim": "recorded_compatible_ECG_type_model_inferred_not_per_beat_source_verified",
        "provider": "garmin",
        "require_current_archive_parse_hash": true,
        "require_explicit_recording_local_handle": true,
        "rr_field": "native_hrv78_time0_only",
        "rule_version": "dfa-native-ecg-metadata-v1",
        "same_handle_identity_contradiction": "ineligible",
        "session": "exactly_one_native_running_session",
        "unknown_external_HR_identity": "source_unresolved"
      }
    },
    "binding_and_versions": {
      "applies_to": "conditional automatic admission only; no numerical change",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "frozen_parameter_digest": "sha256:f36cf405cbf84aef9d04e6e52aa1600662ce0254de1b230d7372ff035ebede11",
        "frozen_parameter_groups": [
          "window",
          "rr_quality",
          "time_alignment",
          "dfa",
          "context"
        ],
        "gate_off_automatic_execution_or_publication": false,
        "idempotency_includes": [
          "exact_recording_ref",
          "source_assurance",
          "source_evidence_digest",
          "source_rule_version",
          "numerical_method_version",
          "science_contract_digest",
          "metadata_projection_version"
        ],
        "manual_statement_version": "dfa-source-attestation-v1",
        "metadata_projection_version": "rr-native-source-metadata-v2",
        "numerical_method_version": "dfa-alpha1-raw120-v1",
        "revalidate_at": [
          "admission",
          "execution",
          "publication"
        ],
        "source_rule_version": "dfa-native-ecg-metadata-v1",
        "view_focus_poll_starts_work": false
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
        "metadata_inference_proves_per_interval_source": false,
        "overall_score": false,
        "source_assurance": "branch_specific_user_confirmed_or_metadata_inferred",
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
        "automatic_required": "native_RR_and_all_recorded_HR_candidates_same_compatible_ECG_rule_and_interpretable_external_transport",
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
        "manual_required": "native_RR_and_recorded_ECG_and_activity_confirmation",
        "optical_or_contradictory": "positive_optical_RR_or_known_external_optical_or_identity_source_contradiction_ineligible",
        "polar_manufacturer": 123,
        "polar_native_names": [
          "H10",
          "Polar H10"
        ],
        "required": "native_RR_and_recorded_ECG_and_branch_specific_assurance",
        "statement_version": "dfa-source-attestation-v1"
      }
    },
    "source_assurance": {
      "applies_to": "conditional automatic admission only; no numerical change",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "value": {
        "allowed": [
          "user_confirmed",
          "metadata_inferred"
        ],
        "direct_rr_sensor_fk": false,
        "metadata_inferred_confirmation_id": null,
        "metadata_inferred_human_confirmation": false,
        "metadata_inferred_requires": "immutable_typed_metadata_proof_bound_to_exact_recording_and_source_rule",
        "metadata_projection_version": "rr-native-source-metadata-v2",
        "public_sensor_identity": "recording_local_opaque_handles_and_compatible_model_labels",
        "published_signal_accuracy": false,
        "user_confirmed_requires": "immutable_factual_owner_confirmation_bound_to_exact_recording_and_sensor_rule"
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
  "runtime_state": "inactive",
  "schema_version": 1,
  "source_decision_digest": "sha256:80776068bcf39de5383743bdf419f7c84c7494a6fc82fd023240d00bc2aefee4"
}
```

</details>

<details><summary>Implementation approval — not part of decision approval</summary>

Runtime activation remains fail-closed until implementation approval can bind both the active contract digest and the exact reviewed code diff/validation evidence. Evidence or decision approval cannot fill this role.

</details>

<details><summary>Exact reviewed decision payload</summary>

```json
{
  "accepted_interpretation": "DRAFT INACTIVE PROPOSAL: preserve the complete dfa-alpha1-raw120-v1 numerical method. Conditionally allow automatic completed-sync analysis under an independently active source/admission contract and default-off server gate, using metadata_inferred source assurance for the specified recorded ECG-type/model predicate. Such recordings compute without a per-activity human assertion. Manual owner-confirmed analysis remains a distinct branch; neither inference nor flag evaluation proves per-interval sensor provenance or individual accuracy.",
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
    "Exactly one native running FIT session under the existing Garmin archive adapter with unchanged raw RR timing/QC; source qualification is branch-specific.",
    "Automatic: each explicitly recorded external HR handle has coherent ANT+/HR or BLE/HR metadata and an unchanged supported ECG compatibility rule; all candidates share that rule, including same-model separate radio handles.",
    "Unknown external HR, missing transport/class, different supported ECG models or explicit local wrist-HR inventory produce source_unresolved; ordinary watch optical capability does not.",
    "Known external optical identity, source-handle identity contradiction or positive mixed/switching source evidence remains ineligible.",
    "Source assurance is a modality/model inference from recording metadata, never a guarantee of the exact physical or per-interval native RR source."
  ],
  "artifact_policy": {
    "runtime_state": "inactive"
  },
  "decision_date": "2026-10-02",
  "decision_notes": [
    "PDR logical digest sha256:086c52e80679e9d0a89a6f28ba70bda7d351076ed4c8933b77e32ca8b6f2501c verified. User Product implementation approval does not originate scientific signatures.",
    "Work classification sha256:1f80b1e4ff20a296d77cc15154af9d8826ea75e8d9726f2be624eb6292c11cff;route sha256:a45599ca884e6edfe42e642bddbf2026d027776c58081de6e35ec91f59892904.",
    "Existing v1EvidenceReview and SDR are draft/inactive here. This proposed v2 successor uses no active supersession links; baseline is not rewritten.",
    "Transitional strategy: manual uses its separately active v1contract; automatic requires separately active v2contract and servergate. If an eventual approved lifecycle supersedes v1, atomically migrate manual lookup to v2user_confirmed branch and all v1links before disabling v1; no partialtransition.",
    "Reuse existing baselineEvidenceReview; source inference parameters are explicit operational guardrails, not new published physiological validation. Five reviewed papers/source limits in the earlier research bundle remain contextual.",
    "The3%/5%corrected-method candidate record is a different inactive research object and is excluded from this amendment.",
    "SDK metadata facts re-used from coordinator verification: global78time has no RR-sensor FK; source_type/device_type is source inventory. Localwhr presence is not proven optical RR; dive_settings source fields do not establish running provenance.",
    "Inventory-only optical capability or localwhr device presence does not constitute positive optical-RR contradiction; new v2 source-group wording clarifies that distinction. Existing v1manual record remains unchanged."
  ],
  "decision_review": {
    "approval_statement": "Approve the displayed source/admission decision digest only; this does not activate runtime or enable the server gate.",
    "items": [
      {
        "approval_effect": [
          "Accept only the named scientific/source interpretation after authenticated digest-bound decision approval."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Runtime activation, gate enablement, deployment, fabricated human source statements or changed numerical QC."
        ],
        "evidence_claim_ids": [
          "dfa.recording-artifacts",
          "dfa.short-scale-method",
          "dfa.threshold-transfer-limited"
        ],
        "id": "unchanged-method",
        "parameter_names": [
          "window",
          "rr_quality",
          "time_alignment",
          "dfa",
          "context"
        ],
        "proposed_decision": "Keep exact dfa-alpha1-raw120-v1 formula, constants, quality and timing.",
        "question": "Retain complete numerical baseline?",
        "title": "Retain complete numerical baseline"
      },
      {
        "approval_effect": [
          "Accept only the named scientific/source interpretation after authenticated digest-bound decision approval."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Runtime activation, gate enablement, deployment, fabricated human source statements or changed numerical QC."
        ],
        "evidence_claim_ids": [
          "dfa.recording-artifacts",
          "dfa.short-scale-method",
          "dfa.threshold-transfer-limited"
        ],
        "id": "inferred-source",
        "parameter_names": [
          "source",
          "source_assurance",
          "automatic_source",
          "claim_limits"
        ],
        "proposed_decision": "Accept branch-specific user_confirmed versus metadata_inferred assurance and the all-candidate/same-ECG-rule metadata predicate, with unknown versus contradiction outcomes.",
        "question": "Admit narrow metadata-inferred ECG-type/model source?",
        "title": "Admit narrow metadata-inferred ECG-type/model source"
      },
      {
        "approval_effect": [
          "Accept only the named scientific/source interpretation after authenticated digest-bound decision approval."
        ],
        "disposition": "approve",
        "does_not_authorize": [
          "Runtime activation, gate enablement, deployment, fabricated human source statements or changed numerical QC."
        ],
        "evidence_claim_ids": [
          "dfa.recording-artifacts",
          "dfa.short-scale-method",
          "dfa.threshold-transfer-limited"
        ],
        "id": "conditional-admission",
        "parameter_names": [
          "activation",
          "binding_and_versions"
        ],
        "proposed_decision": "Allow automatic completed-sync computation only under a separately active source contract, gate and authority; preserve independent manual v1path until an approved lifecycle migration.",
        "question": "Default-off conditional automatic admission and immutable bindings?",
        "title": "Default-off conditional automatic admission and immutable bindings"
      }
    ],
    "reviewer_task": "Review only unchanged baseline inheritance and narrow source/admission amendment. Product user-value approval is already recorded separately; implementation activation remains a different approval role."
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
    "Automation fabricates a factual owner confirmation or labels metadata_inferred as user_confirmed/verified.",
    "Known contradictory/optical source admitted; ambiguous inventory silently claimed to be physically one sensor or direct native RR provenance.",
    "A positive eligible metadata predicate invariably requires another manual confirmation/start rather than completing.",
    "Any numerical/QC/formula/timing/coverage correction changes under this source-only amendment.",
    "DefaultOFF, inactive science or processing/gate revocation permits new automatic work/publication."
  ],
  "id": "sdr-activity-dfa-alpha1-v2",
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
      "rationale": "The supported modality/model registry is unchanged. Manual source assurance retains a factual per-activity owner statement. Automatic source assurance is a narrow metadata inference and must not assert measured per-beat attribution.",
      "value": {
        "automatic_required": "native_RR_and_all_recorded_HR_candidates_same_compatible_ECG_rule_and_interpretable_external_transport",
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
        "manual_required": "native_RR_and_recorded_ECG_and_activity_confirmation",
        "optical_or_contradictory": "positive_optical_RR_or_known_external_optical_or_identity_source_contradiction_ineligible",
        "polar_manufacturer": 123,
        "polar_native_names": [
          "H10",
          "Polar H10"
        ],
        "required": "native_RR_and_recorded_ECG_and_branch_specific_assurance",
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
      "rationale": "Preserve all physiological claim limits and distinguish source evidence categories. Source inference is a Product/Science guardrail, not a measured accuracy effect.",
      "value": {
        "coverage": "availability_not_accuracy",
        "diagnosis": false,
        "individual_thresholds": false,
        "kubios_equivalence": false,
        "metadata_inference_proves_per_interval_source": false,
        "overall_score": false,
        "source_assurance": "branch_specific_user_confirmed_or_metadata_inferred",
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
      "rationale": "Conditional admission amendment for the approved Product scope. Actual generated runtime state remains inactive; the gate alone cannot authorize inference or activate science. Keep manual v1 contract authority distinct until an approved migration.",
      "value": {
        "automatic_background_admission": true,
        "automatic_condition": "default_off_server_gate_and_active_signed_v2_contract_and_current_metadata_predicate_and_owner_processing_authority",
        "automatic_contract_id": "sdr-activity-dfa-alpha1-v2",
        "automatic_scope": "newly_completed_sync_only",
        "contract": "signed_active_only",
        "historical_backfill": false,
        "manual_contract_id": "sdr-activity-dfa-alpha1-v1",
        "method_version": "dfa-alpha1-raw120-v1",
        "numerical_method_unchanged": true,
        "source_scope": "single_native_running_session_exact_owner_recording"
      }
    },
    {
      "applies_to": "conditional automatic admission only; no numerical change",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "source_assurance",
      "rationale": "Metadata inference is not human confirmation or direct native RR source attribution. Never populate a confirmation table by automation.",
      "value": {
        "allowed": [
          "user_confirmed",
          "metadata_inferred"
        ],
        "direct_rr_sensor_fk": false,
        "metadata_inferred_confirmation_id": null,
        "metadata_inferred_human_confirmation": false,
        "metadata_inferred_requires": "immutable_typed_metadata_proof_bound_to_exact_recording_and_source_rule",
        "metadata_projection_version": "rr-native-source-metadata-v2",
        "public_sensor_identity": "recording_local_opaque_handles_and_compatible_model_labels",
        "published_signal_accuracy": false,
        "user_confirmed_requires": "immutable_factual_owner_confirmation_bound_to_exact_recording_and_sensor_rule"
      }
    },
    {
      "applies_to": "conditional automatic admission only; no numerical change",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "automatic_source",
      "rationale": "Same-model all-candidate modality inference is deliberately broader than one physical-sensor certainty and remains honestly labelled. It can complete ordinary single-strap and same-model ANT+/BLE inventories without inventing physical identity. Unknown competing sources require clarification; positive contradictions cannot be overridden.",
      "value": {
        "acceptable_transport_class_pairs": [
          {
            "device_type": 120,
            "label": "ANT_PLUS_heart_rate",
            "source_type": 1
          },
          {
            "device_type": 1,
            "label": "BLE_heart_rate",
            "source_type": 3
          }
        ],
        "candidate_selection": "all_recorded_native_external_HR_handles_and_explicit_local_wrist_HR_inventory",
        "compatible_registry": "unchanged_v1_Garmin_products_or_Polar_native_H10_identity",
        "different_compatible_models": "source_unresolved",
        "eligible": "one_or_more_coherent_external_HR_handles_all_registered_ECG_and_same_compatibility_rule",
        "explicit_local_wrist_HR_inventory": "source_unresolved_not_proven_optical_RR",
        "explicit_local_wrist_HR_pair": {
          "device_type": 10,
          "outcome": "source_unresolved_inventory_not_RR_assignment",
          "source_type": 5
        },
        "generic_watch_optical_capability": "does_not_block",
        "known_optical_external_HR_identity": "ineligible",
        "missing_or_uninterpretable_transport_class": "source_unresolved",
        "multiple_same_model_transport_handles": "eligible_as_ECG_type_model_inference_preserve_each_handle_no_physical_merge",
        "ordinary_raw_QC_or_gap_failures": "unchanged_numerical_window_rules_no_global_source_diagnosis",
        "positive_RR_source_switch_or_mixed_source_evidence": "ineligible",
        "provenance_claim": "recorded_compatible_ECG_type_model_inferred_not_per_beat_source_verified",
        "provider": "garmin",
        "require_current_archive_parse_hash": true,
        "require_explicit_recording_local_handle": true,
        "rr_field": "native_hrv78_time0_only",
        "rule_version": "dfa-native-ecg-metadata-v1",
        "same_handle_identity_contradiction": "ineligible",
        "session": "exactly_one_native_running_session",
        "unknown_external_HR_identity": "source_unresolved"
      }
    },
    {
      "applies_to": "conditional automatic admission only; no numerical change",
      "classification": "guardrail",
      "evidence_claim_ids": [
        "dfa.recording-artifacts",
        "dfa.short-scale-method",
        "dfa.threshold-transfer-limited"
      ],
      "name": "binding_and_versions",
      "rationale": "Distinct immutable source and contract digests prevent inferred/manual authority mixing while the full fixed numerical recipe remains unchanged. Trust/Architecture own lifecycle persistence and rights fences.",
      "value": {
        "frozen_parameter_digest": "sha256:f36cf405cbf84aef9d04e6e52aa1600662ce0254de1b230d7372ff035ebede11",
        "frozen_parameter_groups": [
          "window",
          "rr_quality",
          "time_alignment",
          "dfa",
          "context"
        ],
        "gate_off_automatic_execution_or_publication": false,
        "idempotency_includes": [
          "exact_recording_ref",
          "source_assurance",
          "source_evidence_digest",
          "source_rule_version",
          "numerical_method_version",
          "science_contract_digest",
          "metadata_projection_version"
        ],
        "manual_statement_version": "dfa-source-attestation-v1",
        "metadata_projection_version": "rr-native-source-metadata-v2",
        "numerical_method_version": "dfa-alpha1-raw120-v1",
        "revalidate_at": [
          "admission",
          "execution",
          "publication"
        ],
        "source_rule_version": "dfa-native-ecg-metadata-v1",
        "view_focus_poll_starts_work": false
      }
    }
  ],
  "model_version": "dfa-alpha1-raw120-v1",
  "owners": [
    "agent:science"
  ],
  "privacy_implications": [
    "Owner-only inferred proof and result; no automatic human confirmation row, serial/address persistence, private raw metadata duplication or RR/source data in gate telemetry.",
    "Source evidence binding, deletion/revocation/reparse/restore, processing consent, feature-gate fences and retained proof schema require the separate Trust/Architecture acceptance."
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
  "title": "Conditional automatic raw DFA admission with metadata-inferred source",
  "user_facing_claim_limits": [
    "Metadata-inferred output: Source inferred from recording metadata; no source confirmed by you or verified-source label.",
    "User-confirmed output: preserve the existing factual owner-confirmation label and exact statement revision.",
    "Same-model multiple recorded handles may represent radio connections or separate devices; do not merge physical identities or promise one strap.",
    "Preserve estimated time alignment, availability-not-accuracy, no overall score, no threshold lines, no individual threshold, no diagnosis/training change or cross-app equivalence."
  ],
  "validation_plan": [
    "Golden numeric fixture outputs under v1manual and v2automatic are identical except typed assurance/provenance metadata; frozen numerical parameter digest must match.",
    "Synthetic native FIT source matrix: eligible oneANT+ECG, oneBLEECG, twoANT+/BLEsame-model handles without physical merge, repeated coherent handle descriptions, generic optically capable watch plus supported externalECG.",
    "Source-unresolved cases: differentcompatibleECGmodels, unknowncompetingexternalHR, missing source_type/device_type/index, explicit localwhr inventory, ambiguous handle transport reuse.",
    "Ineligible cases: positively knownexternalopticalHRidentity, samehandle identitycontradiction, positiveoptical/external switching or mixedRRsourceevidence.",
    "Positive source inference completes automatic numerical phase without any Confirmation row, per-activity click or confirmed:true. Baseline raw QC can still produce no_valid_windows or timing failures truthfully.",
    "GateOFF, failing gate wrapper or inactive/wrong science contract never admit/execute/publishautomaticresults; manual existing authority remains independent.",
    "Independent Science/Trust/Quality review tests exact source-proof binding and stale/input/gate/rights fences before production activation."
  ],
  "version": 2
}
```

</details>
