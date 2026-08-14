# Science review packets and implementation contracts

Praxys separates what a human approves from what implementation code consumes
without maintaining two independent sources of truth.

## Model

An artifact-mode Evidence Review or SDR remains the canonical typed source.
Deterministic generation produces separate projections:

```text
canonical typed record
  ├─ review packet Markdown      human review surface
  └─ policy contract JSON        code consumption surface
```

Both projections carry stable SHA-256 digests. No generator interprets prose or
uses an LLM to derive contract values. Every behavior-driving contract field
comes directly from a typed SDR `model_parameters` entry and appears verbatim
in the review packet's exact-contract section.

Artifact-mode records declare:

```yaml
approval_mode: artifact
```

Artifact-mode SDRs also declare their runtime boundary:

```yaml
artifact_policy:
  runtime_state: inactive
```

`accepted` and `active` are different states. An accepted decision may remain
inactive until implementation, migration, validation, and rollout gates pass.

## Generated files

Run:

```bash
python scripts/generate_science_artifacts.py
```

The command owns:

```text
data/science/generated/review-packets/<record-id>.md
data/science/generated/contracts/<sdr-id>.json
```

Use `--check` in CI or review automation:

```bash
python scripts/generate_science_artifacts.py --check
```

Review packets contain the full question, method, claims, verification levels,
decision interpretation, exact parameters, rationale, applicability, safety
and privacy boundaries, validation/falsification plans, unresolved content,
and exact generated JSON contract. Canonical payloads are included in
collapsible sections so no reviewed field is hidden.

Contracts contain only typed implementation data:

- decision ID, version, lifecycle, and model version;
- runtime state and source-decision digest;
- linked Evidence Review digests and claim IDs;
- affected models;
- exact parameter values, classifications, claim links, and `applies_to`;
- a self-validating contract digest.

Runtime code loads contracts through
`analysis.science_artifacts.load_policy_contract()`. `require_active=True`
rejects a draft, non-accepted, inactive, stale, or unapproved contract.

## Role-scoped approvals

Artifact-mode records do not use the legacy unscoped `human_reviewers` field.
Each human attestation is a separate YAML file beneath
`data/science/approvals/` and binds one reviewer, role, scope, date, source
reference, and immutable digest:

```yaml
schema_version: 1
subject_kind: science_decision
subject_id: sdr-example-v1
subject_digest: sha256:...
reviewer: github:reviewer
role: decision_approver
reviewed_on: 2026-08-14
scopes:
  - decision_interpretation
  - parameters
  - applicability
  - claim_limits
  - safety_and_privacy
  - activation_boundary
source_ref: https://github.com/org/repo/pull/123#pullrequestreview-456
```

Roles are intentionally distinct:

| Role | Reviews | Required before |
|---|---|---|
| `evidence_reviewer` | Search method, evidence claims, citation verification, limitations and gaps | Artifact-mode Evidence Review acceptance |
| `decision_approver` | Interpretation, exact parameters, applicability, claim limits, safety/privacy, activation boundary | Artifact-mode SDR acceptance |
| `implementation_reviewer` | Contract mapping, runtime diff, validation | Contract activation |

Changing reviewed content changes its digest and makes the approval stale.
Changing an SDR from inactive to active changes both its decision and contract
digests, requiring renewed decision and implementation review.

## Review workflow

1. Create draft Evidence Review and SDR records with `approval_mode: artifact`.
2. Generate review packets and contracts.
3. Review the generated packet, not raw YAML syntax.
4. Correct the canonical record and regenerate until the packet is stable.
5. Record role-scoped approval against the displayed digest.
6. Atomically accept the record and add the approval artifact.
7. Keep the contract inactive until implementation review and rollout gates
   are complete.

Legacy records remain supported with `approval_mode: legacy`. New science
decision work should use artifact mode.
