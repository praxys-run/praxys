# Task completion guidance v1

## Evaluation Report and Policy Change Proposal

Logical artifacts: `evaluation-report-task-completion-v1` and
`policy-change-proposal-task-completion-v1`, owned by Meta/Eval. This document
records the accepted handoff; it creates no approval schema or authority.

One reviewed dependency-maintenance session began with 15 PRs and a user
request to handle all open PRs; the user later corrected the process to serial
merges. Missing post-merge evidence for #850 held eight
remaining PRs. A real publication failure in #837 led to recovery #864 and an
expanded resource-group audit; frontend, certificate, and workspace history
also became blockers. After the user requested a simpler path, the remaining
eight merged with required CI and independent Quality while incidents were
handled separately; #864 was eventually closed. This is one descriptive,
correlated observation, not proof of a causal speedup or that every hold was
unnecessary. No savings, rates, or autonomy promotion follow from it.

The objective is to complete the authorized task while preserving safety,
specialist decisions, independent Quality, and effective GitHub controls.
The accepted proposal has six changes:

1. State completion evidence and non-goals in the Work Router handoff; limit
   scope expansion to acceptance, causal safety dependencies, or new user scope.
2. Require causal, scoped blockers and explicit unblock conditions, including
   bounded diagnostic holds under credible uncertainty.
3. Give one loop coordinator active progress ownership and bound specialist
   questions/artifacts/exits without removing required roles.
4. Reuse explicit batch authority within action/risk scope, retain immutable
   approval boundaries, and serialize main refresh, CI, and authorized merges.
5. Use sufficient current evidence, with a narrow native bot dependency
   CI-based path and normal final preflight for authored repairs.
6. Name the owner, completion signal, and next action for waits; reassess
   repeated no-evidence checkpoints without empty progress or time-only loss.

The independent Decision Review Router returned `human-review-required` and
recommended this bounded proposal. The coordinator recorded existing explicit
user authorization for implementation and a reviewable PR, with standing merge
intent still subject to Quality, current CI, branch rules, and final scope
review. This is not a hash-bound approval and does not transfer any such
approval. New dependency, security, runtime, or architecture behavior reroutes.

Classification digest:
`sha256:0ad9318cbabe89b8918297e022d356e47ca4d91510fdb983761ba44a53a0e8e5`.
Route digest:
`sha256:02ae5b927772915aa703344217dd7092151f847719fe05a9d72d43dd6f92949b`.
These identify the Work Contract, not an approval subject. No immutable review
reference was supplied with the logical handoff; independent Quality evidence
must identify the actual reviewed patch/head before release.

Non-goals: new services, ledgers, roles, schema migrations, tools/permissions,
autonomy promotion, lifecycle changes, CI/readiness script changes, or changes
to the decision-card trial. Default-human judgment, empty promotion lists,
hash-specific approvals, and existing effective GitHub gates remain intact.

## Implementation Impact Map and Change

Engineering implements shared `task_completion` guidance in the existing loop
policy, short directives in Work Router, Orchestrator, Change Loop, Quality,
Decision Review Router, and Operations, plus aligned developer/Copilot/Operations
guidance.
Task-routing descriptions clarify action-specific causality and actual automatic
deployment; role contributions, artifacts, schemas, and algorithms are unchanged.
Classification and route digests for identical inputs stay unchanged because
descriptions are excluded; the edited config file hashes do change. Existing routing tests exercise ordinary delivery and preserved
specialist obligations. Static runtime parity checks the unchanged adapters.

Data, analysis metrics, APIs, clients, production configuration, migrations,
workflows, and runtime tooling have no implementation changes. There is no UI
change. The Operations runbook describes the validation boundary without
changing deployment or incident authority. Engineering's focused test results
are execution evidence; independent Quality owns Verification Evidence.

## Expected manual replay and observation

These are expected coordinator behaviors for manual replay, not automated
enforcement or claims that a live replay has passed. Deterministic tests cover
classification-to-contract behavior, not whether a model applies this guidance.

| Case | Expected behavior |
| --- | --- |
| Documentation task discovers an unrelated certificate issue | Record a separate finding; keep the accepted completion boundary unless a causal dependency is established. |
| A queued merge would trigger the failing publication path | Name the shared hazard and hold affected actions; retain Operations and any Trust requirements. |
| Missing deployment evidence may conceal that shared hazard | Hold the implicated action for a bounded diagnostic, with owner, evidence needed, and unblock condition; do not assume safety. |
| A mandatory input, authority, or required CI result is missing or failing | Block its affected action without requiring proof of production harm; unrelated evidence debt cannot hold the queue. |
| Native bot dependency PR refreshed mechanically against main | Verify provenance/delta, current CI, specialists, and independent Quality; record actual head/base evidence and obey effective gates. |
| Bot PR needs authored workflow/generated/conflict repair, or provenance is unknown | Use normal final preflight; prior CI cannot validate the repaired SHA. |
| Batch authority unchanged, or a hash-bound subject changes | Reuse the scoped batch authorization in the first case; never transfer immutable approval in the second. |
| Child/CI wait repeats without new evidence | Reassess owner and dependency, retain the runtime completion signal, and do not duplicate queues or infer loss from time. |
| New science, design, trust, architecture, or deployment effect appears | Reclassify and retain its required specialist artifacts and independent review. |

Meta/Eval should observe subsequent human corrections, unnecessary and missed
holds, authority escapes/reverts, review effort, and latency. These are future
measurement obligations, not evidence already gathered or implementation
blockers. Dependencies remain the accepted six changes, independent Decision
Review, Engineering implementation, and independent Quality.

## Rollback

Suspend the changed guidance on a missed hazard, authority escape, or harmful
application; retain safety gates and obtain independent review of the
correction. Revert this patch's shared policy section, role directives,
description clarifications, and aligned documentation together if needed.
Preserve unrelated work and existing runtime/approval controls. Observation of
one successful task cannot promote autonomy or establish measured parity.
