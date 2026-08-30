# Verification Evidence: Agent Lifecycle Hardening

- **artifact_type:** `verification-evidence`
- **owner_role:** `quality`
- **verification_date:** `2026-08-31`
- **verdict:** PASS for bounded repository implementation
- **reviewed_repository:** `praxys-run/praxys`
- **reviewed_branch:** `copilot/fix-agent-lifecycle-management`
- **reviewed_implementation_commit:**
  `f93de664fee30091c8b2178d9fa04446a74adcaa`
- **reviewed_implementation_tree:**
  `4f038d748070ed92079ad7b2bcc9f34e22c6fd69`
- **implementation_parent:**
  `984c8c084080f089686c51e455bb4d6db80b15f2`
- **locally_observed_pr_base:**
  `origin/main` at `78d80d82ee63b4e0b343b4e05b80c56f372510f6`
- **draft_pr:** `#745`

## Independence and scope

Praxys Quality independently inspected and tested the exact implementation
commit above. It made no implementation edit, commit, push, retained-ledger
mutation, deployment, release, pull-request state change, or merge decision.
Engineering conclusions and prior test results were not treated as sufficient
evidence.

Independent general code review reported no significant issue. Independent
Trust implementation review returned PASS for repository conformance only.
Neither review authorized retained-ledger migration, reset, restore,
deployment, release, merge, or autonomy expansion.

This evidence covers repository-owned cooperative mediation. Native, platform,
user, and otherwise unmediated calls remain outside repository authority and
observability.

## Work Contract

Independent routing reproduced:

- routing version `praxys-task-routing-v1`
- operating-model version `praxys-agentic-operating-model-v1`
- primary object `repository-behavior`
- impacts `repository-change`, `production-operation`,
  `architecture-boundary`, and `trust-boundary`
- risk triggers `security-or-privacy-boundary`,
  `irreversible-or-high-blast-radius-action`, and
  `out-of-policy-or-out-of-distribution-decision`
- classification digest
  `sha256:e3c17d24f3e95a7629a8a86d7454e1cd2e5dbf94b32011c6beaa596408de3ac9`
- route digest
  `sha256:d44577261f0413c0df43f34a13d18e4f84a9fd1c7aea6cdb9ab089724fd9b132`
- Delivery primary loop and Runtime nested loop
- Architecture and Trust contributors
- Engineering and Operations executors
- Quality verifier
- human review required for the bounded decision

The authenticated maintainer approved repository implementation only against
the exact decision artifacts below. Quality recomputed and matched every
digest:

- Architecture:
  `a78541c75bad209abff2bbcce99ce5599d8b142d04f4b0c50cd1dd86559d8fd9`
- Trust:
  `ad464cbd41f8375ce684f80bb35117c6ddf98783d2ee4d7817f23a4693844847`
- Operations:
  `013b94dc6de8276dea82abcb38dbb38bb89d5be9ea69a2efc3c852e3d06c512a`
- predecessor ledger-v2 ADR:
  `5bd8d04069ef3cca0043087cd53e12d6e72de9847cf9431394e85690b6094875`

## Acceptance matrix

| Area | Result | Independent evidence |
|---|---|---|
| Versioned contract | PASS | JSON requests and responses use schema 2, policy remains `agent-invocation-control-v1`, the stable path is unchanged, and the exact SQLite target is schema 3 with one claim column and one partial unique index. JSON-schema-1 requests and old binaries are refused. |
| Claim identity | PASS | `read_claim` identities are canonical lowercase `rcl_<32 hex>` values generated with `secrets.token_hex(16)`. Malformed, missing, uppercase, short, fingerprint-shaped, and wrong-kind values fail closed. |
| Token privacy | PASS | The mediator stores only `sha256:<SHA-256("praxys/read-claim/v1\0" || canonical token)>`. The raw token is absent from database and WAL evidence and is not echoed by claim, observation, or error responses. The sole output exception is successful token creation. |
| Existing authorization | PASS | Every claim and observation still requires the exact attempt, native alias, and public task-result ID. The claim token proves operation ownership only and never replaces tuple validation or caller authority. |
| Claim atomicity and races | PASS | `BEGIN IMMEDIATE`, expected-state update predicates, constant-time fingerprint comparison, and the partial unique index allow one owner. Same-token/same-row races resolve as one logical claim; different-token/same-row and same-token/cross-row races allow one winner and fail the other closed. |
| Commit ambiguity | PASS | Commit-then-raise and rollback-then-raise rerun the same claim algorithm once with the same token in a fresh transaction. Durable invalidation, observation, or terminalization takes precedence; no state-only ownership inference remains. |
| Physical read boundary | PASS | Cooperative manifests require one caller-held token, prohibit replacement-token generation after uncertainty, and require the caller to know whether the physical read already ran. An idempotent claim acknowledgement never permits a second physical read. |
| Observation | PASS | Observation requires `read_claimed`, the exact tuple, and the same claim token. It remains one-shot. Token mismatch cannot create loss, replacement eligibility, cleanup, recovery, or another terminal effect. An ambiguous observation commit fails closed without fabricated replay. |
| Fingerprint retention | PASS | Tests preserve the same fingerprint through found, lost, succeeded, failed, recovered, abort, shutdown, failure, orphaning, and invalidation. Pre-claim states reject non-null fingerprints and `read_claimed` rejects null ownership. |
| Migration | PASS | Explicit `init` migrates exact recognized v1 directly to v3 and exact v2 to v3. It never commits an intermediate v2, preserves supported rows with null historical fingerprints, refuses every ownerless `read_claimed` source, and leaves ordinary commands unable to migrate. |
| Admission fault path | PASS | A known kill-switch, duplicate, illegal-transition, or direct-sibling rejection remains `launch_authorized=false` when its audit insert or commit fails or becomes ambiguous. Replaying a recorded lifecycle rejection also remains fail-closed. |
| Scope containment | PASS | No application database, API, authentication, athlete-data, dependency, provider, sync, deployment, infrastructure, native runtime, policy bound, role authority, reviewer authority, or autonomy setting changed. |

## Independent commands and results

Quality used the repository virtual environment and `TZ=UTC`.

```text
TZ=UTC /home/feitao/src/tf-personal-pensieve/praxys/.venv/bin/python \
  -m pytest tests/test_agentic_invocation_control.py -q
```

Result: `263 passed`, exit 0.

Quality also ran the agent policy, preflight, operating-model, routing,
execution-parity, and decision-agent regression modules.

Result: `42 passed`, exit 0.

Quality repeated all three claim-race scenarios for ten rounds.

Result: all 30 race executions passed.

Quality independently injected durable observation and terminalization between
an ambiguous claim commit and reconciliation.

Result: the later refusal won and no read authorization was inferred.

Quality created only temporary ledgers and inspected their metadata, column
order, and index SQL.

Result: policy v1, ledger schema 3, the exact claim column, and the exact
partial unique index matched.

```text
git diff --check f93de664^ f93de664
```

Result: no output, exit 0.

## Prior blocker disposition

The earlier fail-open admission fault was corrected: storage failure cannot
turn a known hard rejection into permission to launch.

The earlier state-only native-read reconciliation was removed. Caller-owned
claim identity now distinguishes an ambiguous caller from a concurrent winner,
while invalidation, observation, and terminal state remain authoritative.

## Limitations and pending evidence

- The ledger is local to one Git common directory and has no cross-machine
  authority.
- The shared retained ledger was not opened, initialized, migrated, reset, or
  modified. Quality observed its existing modification time as
  `2026-08-29 22:00:44 +08:00`, before this verification.
- No native registry lookup, cancellation, write, external rebind, polling, or
  global interception exists.
- No retained-ledger migration, restore, reset, deployment, release, merge, or
  branch-protection bypass was performed or authorized.
- Final UTC preflight and required GitHub checks remain pending.
- The commit containing this evidence must receive an exact-head verification
  before the ready-for-review handoff.

## Release recommendation

PASS for proceeding to an exact-head verification of the evidence commit,
repository final preflight, and required GitHub checks. This is not approval
for retained-ledger operation, activation, enforcement, autonomy promotion,
release, or merge.
