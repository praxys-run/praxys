# Science review packets and implementation contracts

Praxys separates what a human approves from what implementation code consumes
without maintaining two independent sources of truth.

## Model

An artifact-mode Evidence Review or SDR remains the canonical typed source.
Deterministic generation produces separate projections:

```text
canonical typed record
  ├─ review packet Markdown
  │    ├─ decision sheet         primary human review surface
  │    └─ audit appendix         evidence, parameters, exact contract
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

They must also define an action-oriented `decision_review` manifest. Each item
states the question, proposed decision, effect of approval, what remains
unauthorized, and the exact contract groups it covers:

```yaml
decision_review:
  reviewer_task: >
    Approve the decision sheet as a unit or request changes by item ID.
  approval_statement: >
    I approve the proposed decisions and explicit deferrals as one inactive
    science decision. I am not approving implementation or activation.
  items:
    - id: supported-scope
      title: Accept the supported population and goal scope
      disposition: approve
      question: Should this policy cover the stated training pattern?
      proposed_decision: Accept the bounded scope.
      approval_effect:
        - The mapped routing groups become accepted decision inputs.
      does_not_authorize:
        - Any unresolved schedule or dose.
      parameter_names:
        - example_goal_tuple
        - example_supported_pattern
      evidence_claim_ids:
        - example.scope-supported
```

Every `model_parameters` group must appear in at least one decision-review
item. This makes hidden machine behavior a schema error rather than a reviewer
discovery problem.

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

Evidence packets contain the full question, method, claims, verification
levels, and limitations. Decision packets begin with the reviewer's task and a
short decision sheet separated into proposed approvals and explicit deferrals.
The reviewer approves the sheet as a unit or requests changes by item ID.
Evidence details, exact parameters, alternatives, claim limits, safety/privacy,
validation/falsification, the machine contract, and canonical payload remain
available in collapsed audit appendices.

The appendix guarantees completeness; it is not a substitute for a clear
decision sheet and reviewers must not approve merely because they found no
obvious issue while skimming it.

Contracts contain only typed implementation data:

- decision ID, version, lifecycle, and model version;
- runtime state and source-decision digest;
- linked Evidence Review digests and claim IDs;
- affected models;
- exact parameter values, classifications, claim links, and `applies_to`;
- a self-validating contract digest.

Runtime code loads contracts through
`analysis.science_artifacts.load_policy_contract()`. `require_active=True`
rejects a draft, non-accepted, inactive, stale, unapproved, or terminally stopped
contract. A stopped contract retains its historical accepted/active payload; the
append-only stop controls effective runtime admission.

## Role-scoped approvals

Artifact-mode records do not use the legacy unscoped `human_reviewers` field.
Each human attestation is stored as a YAML file beneath
`data/science/approvals/` and binds one reviewer, role, scope, date, source
reference, and immutable digest. Reviewers do not edit this YAML. They approve
the displayed digest in an authenticated GitHub PR comment. When approval is
given in a local/remote agent session, the agent mirrors the exact statement to
GitHub using the human's authenticated identity; an agent or trusted workflow
then materializes the record:

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
| `decision_approver` | Explicit decision sheet, mapped parameters, deferrals, applicability, claim limits, safety/privacy, activation boundary | Artifact-mode SDR acceptance |
| `implementation_reviewer` | Contract mapping, runtime diff, validation | Contract activation |

Changing reviewed content changes its digest and makes the approval stale.
Changing an SDR from inactive to active changes both its decision and contract
digests, requiring renewed decision and implementation review.
The implementation role requires schema version 2 and an implementation binding.
Contract-only implementation attestations remain invalid. The binding includes
repository/PR, frozen base/head, exact Git tree delta, final active contract and
independently produced validation workflow/run/attempt/artifact/content digest.

### What counts as approval

Approval must be an explicit human decision against the exact displayed digest:

- identify the evidence, decision, or implementation role;
- identify the subject record and immutable digest;
- make the packet's approval statement, or an unambiguous equivalent;
- come from an authenticated source that identifies the reviewer;
- preserve a durable source URL in the generated approval artifact.

GitHub comments are verified against repository `write`, `maintain`, or `admin`
permission and bot identities are rejected. Local and remote approvals still
count as the human decision, but the agent must mirror them to this verifiable
GitHub source before changing lifecycle state. This is bookkeeping performed by
the agent, not another review requested from the human.

Agents and CI may transcribe a qualifying approval; they may not infer one from
"looks fine", silence, a skimmed packet, or their own recommendation. Evidence
and decision approval never imply implementation approval or runtime
activation.

### Automatic materialization

The packet includes a copyable `praxys-science-approval:v1` comment marker.
`.github/workflows/science-approval-ledger.yml` reads comments on
same-repository science PRs, verifies human repository permission, runs only
the trusted materializer from `main`, and commits deterministic lifecycle files
back with the independently configured policy GitHub App. It never executes
pull-request code. The required `selective-review-policy` gate independently
re-verifies every new approval artifact against the source comment and checks
the trusted generated packets/contracts before merge.

The materializer verifies the current digest, applies linked evidence and
decision transitions atomically, regenerates packets/contracts/indexes, and
leaves `runtime_state` unchanged unless a separately source-verified implementation
approval binds its projected accepted/active contract and exact implementation. A stale digest, unverified artifact, tampered
packet, or accepted decision whose linked evidence remains draft fails without
modifying the working tree.

The automatic ledger handles first-version acceptance only. A successor record
requires an agent-prepared coordinated patch that marks predecessors
`superseded`, adds reciprocal links, and updates governed references atomically.
`supersedes` links are normalized as lifecycle metadata in review digests, so
that approved scientific content does not become stale when this explicit
transition is applied; the ledger never guesses the predecessor.

Implementation materialization is supported only with a complete authenticated
code-and-validation binding and exact deterministic tree replay. The inactive
capability must land on trusted main before a separate activation PR can use it.
See [bounded activation preparation](dfa-activation/decisions.md). A contract
digest alone remains insufficient; no default review authority changes.

## Review workflow

1. Create draft Evidence Review and SDR records with `approval_mode: artifact`.
2. Generate review packets and contracts.
3. For an SDR, review the decision sheet first. Approve it as a unit or request
   changes by item ID; do not infer a decision from the audit appendix.
4. Use the audit appendix only to investigate evidence, mappings, and exact
   machine values.
5. Correct the canonical record and regenerate until the packet is stable.
6. Give explicit approval against the displayed digest in GitHub or an
   authenticated agent session; the agent mirrors session approval to the
   canonical GitHub comment without asking the human to edit YAML.
7. Let the agent/workflow atomically materialize the role-scoped artifact and
   accepted lifecycle transition; do not hand-edit approval YAML.
8. Keep the contract inactive until implementation review and rollout gates
   are complete.

Legacy records remain supported with `approval_mode: legacy`. New science
decision work should use artifact mode.


### Implementation validation and replay

The trusted-main `science-activation-validation.yml` workflow takes one frozen
same-repository PR revision and projected active contract digest. Candidate
regression and the authoritative actual-policy probe run in separate fresh
GitHub-hosted jobs, each checking out the pinned trusted and candidate revisions
and installing the trusted dependency set. The probe never consumes regression
workspace files, environment, caches or artifacts. Neither job has approval-write
credentials, production secrets or persisted checkout credentials. A third trusted
collector recomputes the code diff and contract and requires successful metadata
from both regression and probe jobs; admission independently requires both jobs
and the collector. Its bounded JSON artifact
identifies repository/PR, base/head, contract, trusted workflow revision, run and
attempt. The implementation statement displays every envelope field and its
canonical SHA-256 digest. The workflow is validation evidence, not human approval.

The ledger refreshes GitHub comments, reviewer permissions, PR/base/head and
validation identity before writing. Its candidate tree must equal the reviewed
preapproval tree, then equal exact replay of the three role approvals. No path
class is broadly excluded from this initial comparison. Identical retries are
idempotent; unexplained code, generated, mode or ledger changes fail. Duplicate
JSON/YAML keys and science symlinks fail instead of hiding ambiguous content.

After activation, the trusted file manifest in
`config/science-implementation-coverage.json` conservatively gates subsequent
implementation maintenance. It includes shared dependency files in full; edits
inside them cannot land while active, even for another feature. First record the
authenticated terminal stop on trusted base, then use separately reviewed stopped
maintenance with actual-guard denial evidence. This capability does not renew the
subject. No history is overwritten
and no science-version increment is fabricated for a code-only change.

After the trusted validation run succeeds, prepare the concrete review package
without writing approval comments or candidate files:

```bash
python scripts/prepare_science_activation.py \
  --candidate /path/to/frozen-checkout --repository praxys-run/praxys \
  --pull-request PR_NUMBER --validation-run RUN_ID \
  --validation-artifact ARTIFACT_ID --output-dir /tmp/dfa-exact-review-package
```

The output contains the exact evidence, active-decision and implementation
statements, binding and authenticated validation manifest. Only after the human
makes those displayed assertions may an agent transcribe them to GitHub. The
existing general authorization to enable the feature does not invent an
unseen exact-digest statement or assert personal literature review.

### Atomic activation source and terminal stop

The generated `approval.md` is **one canonical composite comment** containing all
three role assertions and their exact digests. Obtain one explicit human response
covering those displayed assertions, then transcribe that complete comment once.
Do not split it into successive evidence/decision/implementation comments:
independent v1 evidence acceptance could otherwise advance the reviewed head.
Incomplete, conflicting, duplicate or extra composite assertions fail before any
ledger publication. Existing independent v1 approvals remain supported.

Whole shared files—including `api/main.py`, `api/deps.py`, requirements, client
API types, global EN/zh catalogs and package locks—are guarded while active.
Even unrelated edits within those files are blocked. The corrected manifest also
checks enumerated import-name alternatives; it does not freeze all API additions.

Subsequent maintenance checks protect enumerated source files only. Changes
elsewhere in the application can affect DFA behavior, including through imports
or shared process state. Such changes require ordinary impact review and renewed
specialist review when they affect the approved implementation; the file guard
does not determine semantic independence.

A terminal STOP is a separate explicit human action against the original active
contract and implementation envelope, recorded by trusted-main tooling beneath
`data/science/stops/` with its generated audit. A stop-only PR cannot include code
or other science changes. Only a stop already present in trusted base permits
later governed maintenance, and that maintenance must supply authenticated
isolated actual-candidate denial evidence. Old scientific and approval history
remains byte-preserved at its original paths and executable modes, including
recursively loaded `.yaml` and `.yml` approvals. Another approval cannot revive
the stopped subject.
There is no renewal/enable switch in this capability. See the operational steps
in [DFA operations](../ops/activity-dfa-alpha1.md).

The diff digest uses canonical `praxys-git-tree-diff-v1`: sorted changed paths,
before/after Git object identities and modes, and SHA-256 of every complete changed
blob. Gitlinks retain their exact commit identities. This binds additions,
removals, renames as delete/add, content and modes without depending on local diff
algorithms, hunk context, display prefixes or text-conversion drivers.
