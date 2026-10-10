# The change loop (Loop A) — auto-draft bug fixes with the Copilot coding agent

> **Summary:** How a qualifying bug report is tagged `agent-ready` and handed to
> the GitHub Copilot coding agent to draft a fix PR, plus the one-time setup and
> the knobs that control quality and safety.
> **Use when:** Enabling / operating / tuning the change loop, or debugging "I
> labeled an issue `agent-ready` but Copilot was never assigned".

Praxys defines seven object-improvement loops. This runbook covers the
GitHub-native **Delivery loop** entry for qualifying bugs: feedback -> routed
Work Contract -> drafted fix PR. Production incident execution still lives in
the private `praxys-run/praxys-ops-agent` repo; the public Operations role can
classify and hand off an Incident task without receiving production
credentials.

## How it works

```
feedback triage (api/feedback_triage.py)  ──adds `agent-ready` for a qualifying bug──┐
a maintainer manually adds `agent-ready`  ───────────────────────────────────────────┤
                                                                                      ▼
                          .github/workflows/assign-copilot.yml  ──assigns──▶  Praxys Orchestrator
                                                                                      │ opens
                                                                                      ▼
                          deterministic Work Contract ──▶ Delivery / Change Loop
                                                                                      │ opens
                                                                                      ▼
                    draft PR ──▶ checks + outcome observer ──▶ policy-controlled merge gate
```

`agent-ready` is the **sole trigger**; a bare issue-open never fires. Triage adds
it only when **all** of these hold (`_qualifies_for_agent` in
`api/feedback_triage.py`):

1. **It is a bug** — features are assist-not-act; `other` never qualifies.
2. **The model judged it actionable** (`agent_eligible`) — a genuine, reproducible
   *defect*, not a feature idea, a how-to / support question, expected behavior /
   user error, or a vague complaint. This is where a "user called it a bug but we
   would not" report is filtered out: the triage LLM reclassifies the `kind` **and**
   sets `agent_eligible=false`. Without an LLM verdict (no `AZURE_AI_ENDPOINT`)
   the report is parked for an admin anyway, so it is never auto-assigned.
3. **The sensitivity gate did not withhold it** — a `needs_review`/sensitive
   report is never tagged, and because the tag is gated on this, it never even
   lands in `ai_labels`, so a later admin *approve* cannot auto-assign it either.
4. **It has enough detail** — a cheap language-aware floor beneath the model
   verdict: whitespace-delimited words or Unicode alphanumeric characters for
   scripts such as Chinese.

**Priority is not an eligibility input.** Priority orders accepted work by
impact and urgency; `agent-ready` answers only whether Copilot can make a
bounded attempt. A reproducible low-priority cosmetic defect such as overflow,
clipping, spacing, or incorrect formatting can therefore be agent-ready.

The feedback bot can add several labels in one batch, and GitHub emits one
`issues.labeled` event for each label. Duplicate suppression is scoped to the
eligible assignment job, so a later unrelated label cannot cancel an
`agent-ready` assignment before it starts.

**Backlog escape hatch:** a `backlog` or `later` label makes an issue ineligible
even if it is a bug (the workflow skips it). **Today, merge is
maintainer-controlled** — the coding agent drafts and never decides whether its
own PR can merge. The target state is selective review: a separate risk policy
can eventually route repeatedly proven narrow changes to policy-owned auto-merge,
while sensitive, broad, uncertain, or failing changes still require a human.

The assignment uses GitHub's agent-assignment API with
`customAgent=praxys-orchestrator`, so every eligible issue starts with the
checked-in `.github/agents/praxys-orchestrator.agent.md` profile. The
main session implements and verifies directly, with one fresh read-only
Quality review for material risk. See [session policy](agent-session-policy.md).

Agent-authored Copilot PRs stay draft until the final preflight command and
validated head SHA are recorded and the required branch checks pass.
`.github/workflows/copilot-pr-readiness.yml` automatically
returns a ready PR to draft when either condition is missing, and any new commit
also invalidates the prior ready handoff. Draft Copilot PRs may truthfully mark
rendered UI evidence pending; strict evidence validation resumes when the PR is
marked ready. This is especially important for miniapp work when the cloud
session lacks a WeChat DevTools/Skyline runtime: a human completes that rendered
review, updates the PR body, waits for draft CI, and then marks the PR ready.

For task coordination, follow `task_completion` in
`config/agent-loop-policies.json`. The main session owns progress;
holds name the action, evidence, causal hazard, scope, and unblock condition.
Hold a whole queue only for a shared hazard, including actual deployment side
effects. Credible uncertainty permits a bounded diagnostic hold with an owner.
Missing mandatory acceptance, authority, or evidence dependencies block the
affected action without proof of production harm; unrelated evidence debt
cannot hold the queue.
An unrelated incident stays with its own owner while authorized actions without
that hazard continue. Active waits name their job/owner, completion signal, and
next action; elapsed time does not authorize replacement or cancellation.

### Native session lifecycle

The runtime owns thread identity, reuse, completion and cancellation. Only the
main session dispatches bounded independent work. Custom invocation ledgers and
the decision-card trial are retired; their private data remains untouched.
There is no per-task provisioning, admission or review-router call.

### Shadow mode

Set `PRAXYS_AGENT_READY_SHADOW=true` (App Service setting) to compute the
`agent-ready` decision and log it **without** applying the label — nothing is
auto-assigned. Use it to measure precision on real feedback before trusting the
loop, then unset to go live. Decisions are logged and persisted as structured
`AgentDecision` rows with policy/model/mode metadata and privacy-minimized input
facts.

### Challenger prompt

Set `PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION=v2` to run a second,
temperature-zero semantic judgment on the same scrubbed report. The challenger
is shadow-only: it never changes labels, assignments, publication, or the active
decision. Its prediction and prompt fingerprint are stored inside the active
`AgentDecision`, so outcomes stay attached to the exact production decision they
judged.

The v2 challenger explicitly separates priority from readiness and treats
bounded, reproducible cosmetic UI defects as eligible. It also receives the
verified, scrubbed screenshot description when present; the active v1 prompt
retains its historical message/context payload and pinned fingerprint.

`PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION` is optional and deploy-managed.
Blank disables the extra model call; unknown versions fail closed. See
[config-and-secrets.md](./config-and-secrets.md).

### Screenshots (how the agent "sees" them)

Feedback screenshots are **private by construction** (issue #337): the raw image
stays in Blob storage and only its key lands on the row — it is **never** put in
the (public) GitHub issue, and the coding agent has no path to it (no Azure
credential, and giving it one would pipe potentially-PII image bytes into a
public-repo agent).

The vision model (`api/feedback_vision.py`) may write a private, scrubbed
description for the admin console, but neither that description nor the image
is copied into the public issue. Sensitive or unverified screenshots continue
to park the report for review. A public-repo coding agent therefore receives
only the independently privacy-reviewed text report; screenshot-dependent or
pixel-precise defects must be handled by a human who can view the private image
in the admin console.

**Do not** build a second path (an MCP tool or credential) that hands the agent the
raw image or its derived description — that would breach the #337 invariant for
a public repo. Keep screenshot evidence on the private admin path instead.

### Maintainer adjudication

Admin → Feedback exposes the active decision, optional challenger, and latest
maintainer verdict separately from priority. Record one of:

- **Should be agent-ready — bounded actionable defect**; or
- **Should not be agent-ready** with a stable reason (`not a defect`,
  `insufficient detail`, `needs product judgment`, `sensitivity/privacy`, or
  `other`). Sensitivity/privacy can block readiness; ordinary implementation
  risk does not, because agent-ready authorizes only a reviewed draft.

The verdict is appended as an `agent_ready_adjudicated` `AgentOutcome`. It is
the evaluation ground truth and is persisted even when GitHub label
synchronization fails. A positive verdict adds `agent-ready` when the linked
issue is open; a negative verdict removes it. Existing Copilot assignments or
PRs are not closed automatically. The UI submits the exact displayed decision
ID and receives `409` if retriage made it stale. Label mutation also requires
the stored GitHub issue URL to match the currently configured repository, so a
repository switch cannot target an unrelated issue with the same number.

A sensitivity-gated report has no public issue. Review and publish it first,
then adjudicate readiness if appropriate. Admin → Operations shows active and
challenger confusion matrices plus a prompt-semantic slice. That slice includes
only detailed, ungated reports adjudicated as a bounded defect, not a defect, or
needing product judgment; it excludes evidence/privacy-gate and `other`
verdicts so prompt changes are not scored against decisions they do not own.

## Prerequisites

- Repo admin (to enable the coding agent, create labels, set branch protection).
- `gh` CLI authenticated (`gh auth status`).
- Before operating explicit invocation-ledger migration, bind the action to an
  exact reviewed artifact and satisfy the linked-worktree quiescence and
  pre-state requirements in the claim-ownership ODR, plus the predecessor ODR
  for any v1 backfill. Repository implementation approval is not migration
  authority.

## Steps

### 1. Enable the Copilot coding agent for the repo

Repo (or org) admin: **Settings → Copilot → Coding agent** → enable. Verify it is
assignable — the bot must appear as `copilot-swe-agent`:

```bash
gh api graphql -f query='query($o:String!,$n:String!){
  repository(owner:$o,name:$n){ suggestedActors(capabilities:[CAN_BE_ASSIGNED], first:100){
    nodes{ login } } } }' -F o=dddtc2005 -F n=praxys \
  --jq '.data.repository.suggestedActors.nodes[].login' | grep copilot-swe-agent
```

### 2. Create the labels

```bash
gh label create agent-ready -c 1D76DB -d "Trigger: hand this issue to the Copilot coding agent (change loop)" -R praxys-run/praxys
gh label create backlog     -c 5319E7 -d "Deferred; ineligible for auto-assign even if a bug" -R praxys-run/praxys
```

The workflow also honours an existing `later` label as a backlog synonym.

### 3. Configure the assignment token (REQUIRED for auto-assign)

**Agent assignment needs a user token — the built-in `GITHUB_TOKEN` cannot do
it.** The GraphQL API rejects a GitHub App installation token with
`FORBIDDEN: Assigning agents is not supported with GitHub App installation
tokens` (issue #400). Without `COPILOT_ASSIGN_TOKEN` the workflow now fails
*loudly* (it comments on the issue) instead of silently leaving it unassigned.

Create a **fine-grained PAT**, least-privilege:

- **Resource owner:** `praxys-run`; **Repository access:** *Only select
  repositories* → `praxys` (this repo only).
- **Permissions:** *Issues → Read and write* and
  *Copilot agent settings → Read*.
- **Expiration:** set one (e.g. 90 days) and calendar a rotation.

Then store it and re-run:

```bash
gh secret set COPILOT_ASSIGN_TOKEN -R praxys-run/praxys   # paste the PAT when prompted
```

Manual assignment via the GitHub UI keeps working without this token (it uses
your user session). The additional read permission lets the weekly
`copilot-environment-parity.yml` job compare the live Cloud MCP setting with
the reviewed repository contract.

### 4. Verify Local/Cloud execution parity

The authoritative common capabilities and limitations are
`config/copilot-execution-parity.json`; the reviewed Cloud MCP payload is
`config/copilot-cloud-mcp.json`.

```bash
python scripts/check_copilot_environment_parity.py
python scripts/check_copilot_environment_parity.py \
  --live \
  --repo praxys-run/praxys
```

The first command is repository-only. The second calls the versioned GitHub
Cloud-agent configuration API and requires the token permission above.
`.github/workflows/copilot-environment-parity.yml` runs static validation on
matching pull requests and live drift validation weekly and on relevant
`main` pushes.

If drift is detected, repair the repository setting from
`config/copilot-cloud-mcp.json` or update the reviewed contract in a PR. Do not
weaken an agent's required evidence because a tool is unavailable; keep the
affected PR draft or block the loop.

### 5. Confirm branch protection on `main`

Protect `main` so the coding agent cannot ship or bypass checks:

- **Require a pull request before merging.**
- **Require status checks to pass** — `backend-tests` and `frontend-quality`
  from `.github/workflows/ci-premerge.yml`. The former covers backend pytest;
  the latter combines the web production build and UI harness. They are
  independent required contexts in one workflow.

Repository ruleset `default` (id `15208143`) requires a pull request and
squash-only merge, and blocks branch deletion and non-fast-forward updates. Its
`required_approving_review_count` is `0`: human review is encouraged for risky,
security-sensitive, or science-affecting changes, but it is not a mandatory
merge gate for the solo-maintainer workflow. The ruleset requires
`backend-tests` and `selective-review-policy` against the latest `main`; classic
branch protection also keeps `backend-tests` required with admin enforcement.
Both contexts are required in classic branch protection. Keep their job names
stable when changing workflow structure.

The ruleset retains an `Always` bypass for the repository-role admin. Normal
green PRs do not need that bypass now that no approval is required; keep it as a
maintainer capability and never grant it to the coding agent. Any future
policy-owned auto-merge path must remain independently allowlisted and
check-gated rather than reusing this broad bypass, and the implementation agent
must not label its own PR as eligible.

```bash
gh api repos/praxys-run/praxys/branches/main/protection --jq '{checks:.required_status_checks}'
gh api repos/praxys-run/praxys/rulesets --jq '.[] | {id,name,enforcement}'
```

Verify the required contexts with:

```bash
gh api repos/praxys-run/praxys/branches/main/protection/required_status_checks
```

### 6. Operate the GitHub Agentic Workflows layer

The coding agent still owns implementation. Four repository-level
[GitHub Agentic Workflows](https://github.com/github/gh-aw) add bounded judgment
around it:

| Source workflow | Trigger | Safe output |
|---|---|---|
| `change-loop-outcomes.md` | Weekly or manual | Replaces the previous issue-first 30-day lifecycle/quality report, or no-op |
| `change-loop-policy-tuner.md` | Weekly or manual | One bounded draft policy proposal, or no-op |
| `ci-failure-doctor.md` | Failed/timed-out PR validation workflow, or manual | One deduplicated PR diagnosis comment, or no-op |
| `praxys-invariant-review.md` | Successful `Pre-merge CI` run for a same-repo, open, non-draft PR; or manual dispatch | One Praxys-specific science, contract, parity, privacy, native-Chinese, or operations invariant comment; or no-op |

The editable `.md` files and generated `.lock.yml` files both live in
`.github/workflows/`. The agents run read-only through GitHub Copilot's hosted
`gpt-5.4` model. Inference authenticates with the personal fine-grained PAT in
the `COPILOT_GITHUB_TOKEN` Actions secret, so usage is charged against that
token owner's Copilot AI credits rather than the Praxys Azure OpenAI resource.

Repository writes happen only through the declared, capped `safe-outputs`, and
each workflow also carries per-run and daily AI-credit caps. No-op,
missing-tool, incomplete-run, and workflow-failure reports remain in Actions
summaries rather than opening auxiliary repository issues. The workflows use
the short-lived `GITHUB_TOKEN` for repository operations and
`COPILOT_GITHUB_TOKEN` only for model inference. Do not add
`copilot-requests: write`: that switches inference to organization billing and
causes gh-aw to ignore the personal token. No Azure identity, endpoint variable,
or model API key is required.

The four generated workflow locks and `.github/aw/actions-lock.json` use gh-aw
`v0.89.21` and runtime actions
`924af5fdc64061cfbf66fb584c8b07e2ac230c60`. Regenerate them together; a Dependabot
change to only `uses:` pins can leave incompatible compiler/runtime interfaces.
This runtime uses Copilot CLI 1.0.87, AWF 0.28.23, MCP gateway 0.4.25,
GitHub MCP server 1.12.2, and threat-detect 0.5.2. Container images retain their
compiler-provided digest pins. The configured inference model remains `gpt-5.4`.
The compiler's model-alias inventory is runtime dependency data, not authorization
to change the configured model, budgets, roles, or safe-output permissions.

Use the official `github/gh-aw` release's **Linux amd64** compiler (WSL is
supported). Verify its SHA256 against the release asset metadata and
`checksums.txt`: `1c74ff5fc28b1891d32b67f4348a9b7f750946b6d4a721e909187a848868016b`.
The repository wrapper verifies those exact bytes before execution:

```bash
python scripts/compile_agentic_workflows.py --compiler /path/to/gh-aw-v0.89.21
/path/to/gh-aw-v0.89.21 validate --no-check-update
```

The wrapper invokes the strict full-repository compile with purge and the
`praxys-run/praxys` schedule seed. It then preserves `retention-days: 1` on
exactly the activation job's `info` upload in each lock. Upstream v0.89.21 emits
that duplicate of `aw_info.json` without a retention setting, although the
existing `activation` artifact has a one-day limit. The wrapper validates all
four exact upload actions and paths before applying any adjustment, accepts an
existing one-day setting, and rejects other values or changed structure. It
makes no other change to generated output. Run the wrapper twice and compare
bytes when validating reproducibility. A future compiler update needs fresh
provenance/interface review; do not bypass its digest or strict validation.
Report unavailable linters or container validation separately from successful
compilation. Do not run `gh aw init` over this repository: initialization must
not replace the repository's Python/Node setup or canonical agent configuration.

#### Telemetry and execution boundaries

The four Markdown sources explicitly retain the existing telemetry destination:
`vars.GH_AW_DEFAULT_OTLP_ENDPOINT`, authenticated with
`secrets.GH_AW_DEFAULT_OTLP_HEADERS`. An identically named endpoint **secret**
cannot override that variable. An empty endpoint disables export. The existing
credential-check helper rejects a configured endpoint without headers and does
not print credential values. Explicit OTLP configuration suppresses the
compiler's automatic default check, so each source declares that same helper
as a custom setup step. It now runs after checkout, GitHub Enterprise setup and
cache setup, and before Git credential configuration, PR checkout, gateway
startup and inference. GitHub Enterprise setup already receives its existing
read-scoped GitHub token; this is not a claim that the check precedes every
credential use. Earlier setup helpers are pinned runtime code and do not run
checked-out workflow code or restored cache executables. Review this order if
source setup steps change. Missing credentials fail the step and subsequent
normal-success steps remain blocked.

Gateway authentication uses a freshly randomized, log-masked
`MCP_GATEWAY_AGENT_ID`, matching the generated `agentId` configuration and its
output consumers. It remains excluded from the inference container environment.
The upstream `gateway-api-key` output is a compatibility alias, not a second
credential. Keep credential exclusions, network isolation, mount boundaries,
read-only agent permissions, token steering and capped safe outputs intact.

Threat-detect 0.5.2 is installed only after verifying the compiler-pinned SHA256
for the selected architecture: amd64
`b4ecda6a8f1ee09913c40b58e5e9d3337d2173618d41b1bfdef9207e4e7959b9`, arm64
`f6260a0f9ad72bcb67c7af19c4ce262ca34e2c3d5ccbf912832a8bd277200904`.
Detection execution requires installation success; the conclusion receives the
installation outcome. Existing detector warning mode is retained. Installation
failure prevents an unverified binary from running but produces a warning in
that mode; this does **not** mean detector unavailability blocks every safe
output. Never disable the detector, remove verification, or describe warning
mode as a strict release gate.

#### Daily credits and artifacts

The runtime scans a complete rolling 24-hour workflow history, using authoritative
run IDs, attempt IDs and timestamps. It counts AI credits, including supported
legacy explicit credit records and model-priced token records. Raw per-response
credit deltas take precedence over overlapping summaries/cumulative totals;
matching request IDs are deduplicated and conflicting records reject. Component
coverage includes agent, detection and evals; retained successful jobs from a
failed-only rerun must still be covered by their original producer artifacts.
New scan observations replace the old daily cache format: old cache records
cannot authorize a new scan. History-listing or run-metadata failures, and
per-run resolution errors carrying an HTTP status, fail activation instead of
silently skipping the daily check. Numeric source budgets remain unchanged.

These rules have explicit compatibility limits. Some all-missing failed-agent
and failed-evals records retain upstream's zero-accounting assumption. That is
not proof of zero spend, a known legacy version, or a positively established
pre-inference failure. Positive recoverable historical usage must be counted.
Separately, per-run accounting resolution errors without an HTTP status may
charge the configured per-run maximum with a warning, even when a network or
SDK exception originated in an API call. History-listing/metadata failures and
HTTP-status errors do not use that fallback. Manual/command-driven bypass behavior is inherited from
the earlier runtime; this upgrade does not grant additional dispatch authority.
Do not describe all missing data as a blocking failure or all zero records as
measured zero usage.

| Artifact | Contents and disclosure | Retention/redaction boundary |
|---|---|---|
| `activation` and new `info` | `aw_info.json`: engine/model/runtime versions, workflow/repository/actor/ref/SHA, run/attempt IDs, allowed domains, feature flags and optional dispatch context; activation also includes the existing prompt/context files | Both explicitly one day. The metadata file is not made private or scrubbed by log masking; review any optional dispatch context before use. |
| `aic-usage-scan-v2` | Version/coverage version, repository/workflow/run/attempt IDs, creation/update/observation timestamps and numeric credits; no prompt, response, token or header fields are emitted by the scan-entry constructor | Three days in Actions; observations older than 48 hours are ignored on read and must still match the live 24-hour listing. This is a field-limited record, not general-purpose redaction. |
| `agent`, `agent-output-fallback`, `detection`, `usage` | Existing logs/safe outputs plus execution state and token-usage records; the fallback now carries additional accounting files | Existing artifact access/default retention applies unless the generated step says otherwise. Agent artifact upload follows existing secret-redaction steps; masking a log value does not scrub every artifact. Do not insert credentials or user feedback into metadata/accounting files. |

Before rollout, validate generated contracts, both checksum pins, telemetry
failure/disable behavior, artifact contents and retention, account for mixed old
and new usage, and have independent Quality review the exact head. A safe-output
workflow can create comments/issues or a bounded draft policy proposal; successful
compilation alone is not live execution evidence or dispatch authorization.
Operations records any separately authorized bounded smoke run or natural-run
observations, including detector warnings and safe-output outcomes. Roll back the
coherent source/lock/action-cache change together; changing only the runtime pin
reintroduces interface skew.

## Tuning the agent (quality knobs)

- **Repo-wide instructions (the "prompt"):** the issue body *is* the task prompt;
  durable guidance lives in `.github/copilot-instructions.md` ("Coding-agent
  guidance") — always add a test, run `pytest`, follow the 7-step metric
  checklist, keep metrics pure, never weaken scrub / tokenstore invariants, and
  keep the PR draft until the implementation/tests/final diff are stable. A code
  push after the first ready handoff returns the PR to draft before more work.
  Edit there rather than stuffing per-issue boilerplate into the public tracker.
- **Executing session:** `.github/agents/praxys-orchestrator.agent.md`
  completes the task directly. Domain skills provide relevant knowledge; one
  independent Quality review covers material risks. Operations retains its
  separately authorized local tool boundary.
- **Deterministic final preflight:** after committing the implementation, the
  agent runs `python scripts/agent_preflight.py --base origin/main`. The command
  selects backend, web, Lingui, miniapp, and UI checks from the actual PR diff
  and refuses a dirty worktree. Generated catalogs must be committed and the
  command rerun before review.
  An unchanged native Dependabot dependency update may use the narrow CI-based
  path in `task_completion.bot_dependency_ci_path`, with at most a reviewed
  mechanical refresh against current main. Verify provider provenance and
  history, dependency-only delta, current required CI, specialists, and
  independent Quality. Only native dependency manifests/lockfiles and bot
  action-reference bumps qualify; authored code/workflow/generated changes,
  conflict repairs, and unknown provenance require final preflight. Record the
  actual evidence and head/base, never an unrun local check. Effective GitHub
  gates remain binding: this guidance changes no readiness script, required
  check, branch rule, or merge authority.
- **Environment:** `.github/workflows/copilot-setup-steps.yml` initializes the
  plugin submodule, preinstalls Python + backend/Praxys MCP deps and Node/web,
  verifies Chrome DevTools MCP, prepares the synthetic local Praxys sandbox,
  installs the workspace-resolving `praxys-local-mcp` cloud launcher, and
  bootstraps a throwaway `.env`. The agent can run `pytest`, `npm`, browser
  review, and read-only product-context tools deterministically instead of
  rediscovering the toolchain. Because Linux `npm install` can rewrite
  platform-specific lock metadata, setup restores and verifies
  `web/package-lock.json` before handing control to the agent. It only takes
  effect once on the default branch.
- **UI quality harness:** a user-visible web/miniapp change must invoke
  `.github/skills/ui-quality/SKILL.md`, which routes through the vendored
  Impeccable skill and the Praxys brand context. The committed Copilot hook
  surfaces mechanical findings after edits. Before the ready handoff the agent
  must inspect the rendered desktop/mobile path, complete the PR's
  `## UI quality` evidence (including design-system impact), and pass
  `scripts/check_ui_quality.py`. CI reports this as the independent required
  `frontend-quality` context. Portable Local and Cloud agents use the same
  pinned Chrome DevTools and read-only synthetic `praxys-local` tools. A
  browser-less agent leaves the PR draft rather than claiming verification.
  Full operation: `docs/dev/ui-quality-harness.md`.
- **Model selection:** which LLM the coding agent uses is an **org/repo Copilot
  setting** (Settings → Copilot → Coding agent), not a per-assignment parameter —
  do not try to pin a model in `assign-copilot.yml`. Pick it in settings.
- **PR evidence refresh:** `Backend CI` listens for pull-request `edited`
  events, so correcting the PR body after rendered review reruns the UI evidence
  gate without requiring an empty source commit.

## Self-improvement

The change loop is meant to get better across iterations. Every triage decision
now writes an append-only `AgentDecision`; triage results, admin overrides,
issue close/reopen state, externally observed `agent-ready`, and closing-PR
state write append-only `AgentOutcome` rows. The records contain hashes, counts,
allowlisted context keys, policy/model versions, and public GitHub identifiers
only — never raw feedback or screenshot bytes.

The admin **Sync from GitHub** action performs the issue/closing-PR
reconciliation. The feedback GitHub App therefore needs **Issues: read/write**
and **Pull requests: read**. It selects no issue/PR titles, bodies, comments,
commits, reviews, or authors.

The weekly observer starts from every `agent-ready` issue, tracks assignment and
PR latency, excludes explicit smoke tests from quality totals, measures CI only
after the first review handoff, attributes failures to the PR vs
baseline/infrastructure, and records correction rounds, missing tests, reverts,
and reopens. Its report remains the richer GitHub-native period view.

For human-added `agent-ready` labels, the observer checks comments immediately
around the label event. An explicit maintainer statement that triage missed the
issue and the label was manually restored is counted as `manual-recovery`, even
when the explanation follows the label.

The workflow has a 20-minute runtime ceiling. Evidence gathering stops after 12
minutes so the agent retains time to classify the evidence, write cache memory,
and emit the report. Unresolved fields stay `unknown`; do not trade explicit
limitations for an exhaustive search that produces no report.

CI attribution uses check-run output, annotations, and job-step metadata only.
The observer does not download raw workflow/job logs, and pre-readiness failures
remain context rather than triggering an attribution investigation.

The deterministic assignment policy is versioned as `change.agent_ready` and
protected by a checked-in, text-free replay corpus:

```bash
python scripts/replay_agent_policy.py
```

The LLM semantic judgment has a separate, privacy-reviewed corpus at
`data/agent_evals/change/agent_eligibility.json`. Compare an active or
challenger prompt against the live deployment with:

```bash
python scripts/evaluate_agent_eligibility_prompt.py --prompt-version v2
```

The script uses the exact production prompt and payload builder, reports
false-positive/false-negative counts, and fails on a mismatch or unavailable
model response. Corpus examples are synthetic or maintainer-reviewed
paraphrases; never paste raw private feedback into the public repository.

Prompt promotion is deliberately reviewed rather than environment-driven:

1. Run the semantic corpus against both active and challenger versions.
2. Enable the challenger and deploy; it remains non-acting.
3. Adjudicate a representative live batch in Admin → Feedback, including
   bounded defects, non-defects, and cases needing product judgment. Do not
   promote from a single correction or synthetic cases alone.
4. Compare prompt-semantic accuracy and FP/FN counts in Admin → Operations.
   Investigate every offline mismatch reported by case ID.
5. Promote only through a reviewed code PR that changes the active prompt
   version and pins its new fingerprint in tests. The challenger setting alone
   can never promote or act.

Those outcomes train both triage precision and draft quality. They also feed the
default-off `review-required | auto-merge-candidate` policy:

- `analysis/review_policy.py` is the pure classifier and promotion evaluator.
- The committed enforcement model is
  `deterministic-required-status`: `backend-tests` and
  `selective-review-policy` are required against the latest base. AI reviews
  and the dedicated App approval are defense-in-depth evidence, not the merge
  authority.
- `data/agent_evals/change/review_promotion.json` stores text-free completed-PR
  evidence. Each bucket is bound to the exact class/sensitive-path/check policy
  fingerprint, and duplicate PR numbers cannot inflate the sample.
- `scripts/validate_review_policy.py` blocks unsupported promotions.
- The required `backend-tests` CI path runs that validator on every PR.
- `selective-review.yml` evaluates same-repo Copilot PRs from trusted
  default-branch code. It requires a closing issue that still has `agent-ready`
  plus the trusted Copilot assignment/cross-reference lifecycle that created the
  PR. It denies non-`main` bases, incomplete/truncated file inventories,
  sensitive paths, missing checks, draft PRs, post-ready commits, requested
  changes, unpromoted classes, and missing tests where applicable.
- `docs/science/**` and the normative science workflow in
  `docs/dev/contributing.md` are sensitive paths denied from the
  `documentation-only` candidate class. Scientific contribution guidance cannot
  become policy-owned auto-merge work through a future documentation-class
  promotion; CODEOWNERS routes it to the current science owner. This prevents
  policy-owned auto-merge, but the current zero-approval ruleset does not
  independently enforce an approving review.
- `web/src/locales/**` is also sensitive. The current catalogs mix ordinary UI
  strings with scientific claims, so no translation-only PR can enter a future
  policy-owned auto-merge path until scientific copy has an independently
  protected surface.
- Evaluation happens before App-token creation. Disabled, unpromoted, sensitive,
  and otherwise review-required PRs finish successfully without App
  configuration. A token is required only for an exact enabled candidate or for
  cleanup of bot-authored stale policy state.
- A qualifying PR receives a defense-in-depth approval from the review-policy
  App, then normal squash auto-merge is enabled. The App never bypasses the
  ruleset or checks.
- Every reevaluation first marks the PR head's `selective-review-policy` status
  pending. It becomes successful only after the run safely revokes stale state
  or completes approval/auto-merge setup; failures remain merge-blocking.
- `selective-review-issue-guard.yml` re-dispatches linked open PRs when the
  issue is closed, reopened, relabeled, or reassigned; a no-longer-qualifying
  PR has policy auto-merge disabled and receives a blocking App review.
- `change-loop-policy-tuner.md` can edit only the proposals JSON and can create
  only a draft PR; it cannot edit deployed policy, approve, or merge. Before it
  drafts, it must inspect the current evaluator and tests, prove an unresolved
  file/symbol-level gap, and use evidence from the active policy semantics (or
  an explicit replay against them). Already-enforced, superseded, stale, or
  deliberately rejected suggestions produce no PR.

The initial `promoted_classes` list is empty. Runtime is independently default
off through `PRAXYS_SELECTIVE_REVIEW_ENABLED`. For rollback, set
`PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH=true`, then dispatch the workflow with
`selective-review-emergency-stop.yml`; it first fails the required policy status
on every affected head, cancels and waits for in-flight gate runs, and
reasserts the barrier on current heads before replacing policy approval with a
blocking review and disabling pending auto-merge through the verified App
identity. The ordinary gate rechecks the kill switch before publishing success.
Foreign bot ownership, a merge race, or incomplete cleanup remains failed
rather than reporting success.
Per-PR evaluation uses per-PR concurrency, so unrelated events cannot discard a
revocation. The gate refuses autonomy unless the effective main-branch rules
require both `backend-tests` and `selective-review-policy` and make those checks
strict against the latest `main`. The ruleset deliberately requires zero
approvals for the solo-maintainer workflow.
Provisioning and promotion steps:
[setup-review-policy-app.md](./setup-review-policy-app.md).

## Security & abuse resistance

An automated, agent-driven flow is itself a target: attackers scan public repos
for agentic signals (bot-filed issues, `agent-ready` / `copilot` labels, Copilot
PRs) and inject at the human/agent seams — hoping a maintainer who trusts the
automation applies a malicious "patch", or that an LLM agent obeys instructions
hidden in issue text. Defenses, in layers:

**Structural (the load-bearing ones):**

- **Only a Copilot draft PR is a legitimate fix.** It comes from the
  `copilot-swe-agent` bot on a `copilot/*` branch, reviewable line-by-line. A
  zip / "patched build" / diff attached by a non-collaborator is **never** our
  flow — do not download, unzip, run, or apply it.
- **The merge path is policy-owned** (§4). Before selective review is
  provisioned, a maintainer decides whether a green PR is ready; human review is
  strongly expected for risky, security-sensitive, or science-affecting changes
  but is not imposed universally. Under selective review, unpromoted, sensitive,
  ambiguous, or unstable PRs require a human merge decision, while only a proven
  narrow class can receive the independent policy App's defense-in-depth
  approval. The coding agent never self-approves or receives a bypass.
- **The trigger is write-gated.** `agent-ready` can only be added by the triage
  bot or a maintainer — a drive-by account cannot start the loop. Keep it that
  way (don't let automation add the label from untrusted input).
- **Least-privilege, expiring token** for assignment (§3); the agent runs in
  GitHub's sandbox with its firewall on — don't disable it.
- **Treat `.github/**` changes as high risk.** Keep CODEOWNERS as an ownership
  signal and obtain human review before merging workflow or policy changes; pin
  actions, keep `permissions:` minimal, and never expose secrets to fork/PR code.

**Treat all user-supplied text as untrusted (prompt-injection):** issue bodies,
comments, and screenshot-derived text can carry "ignore your instructions…"
payloads. The agent's task is the *vetted issue body*, not the comment thread;
`.github/copilot-instructions.md` tells it never to follow instructions embedded
in issue/PR/comment content, never to add dependencies/URLs or touch
secrets/auth/sync on a whim, and never to fetch or apply external attachments.
Everything user-derived still passes `api/feedback_scrub.py` before it is
published.

**Detective:** watch for a brand-new account (age < a few days, 0 repos)
commenting on a bot-filed / `agent-ready` issue within seconds, or any
attachment (esp. `.zip` / binaries) from a non-collaborator. Consider
`Settings → Moderation → Interaction limits` → *Limit to existing users* when a
wave hits (feedback is filed in-app, so external GitHub participation is minimal
and the cost is low).

**Responsive — malicious-contribution runbook:**

1. **Do not** download / open the attachment. Assume it is hostile.
2. Hide the comment: `minimizeComment(classifier: SPAM)` (or *Hide → Spam* in the
   UI).
3. Lock the issue: `gh issue lock <n> --reason spam`.
4. Block the account (needs the `user` scope: `gh auth refresh -s user` then
   `gh api --method PUT /user/blocks/<login>`, or *Block* on their profile).
5. **Report** the account/comment to GitHub (web UI — no API).
6. Assign the legitimate flow (Copilot) so a trusted draft PR replaces the vacuum
   the attacker aimed for. A *working* auto-assign is itself a mitigation: the
   faster a real `copilot/*` PR appears, the less plausible a fake "patch" looks.

## Verify

- Label a **qualifying bug** `agent-ready` → the `Change loop — assign
  agent-ready issues to Copilot` workflow runs and the issue gets
  `copilot-swe-agent` as an assignee using the `praxys-change-loop` custom
  agent; a draft PR follows.
- Mark a Copilot PR ready without the recorded final preflight or with a failing
  required check → `Copilot PR readiness guard` returns it to draft.
- Push a new commit to a ready Copilot PR → the readiness guard returns it to
  draft until validation is rerun on the new head.
- A **feature**, a **not-actionable** bug, a `backlog`/`later` bug, or a
  `needs_review`/sensitive report is never auto-assigned.
- Shadow mode on → no label is applied, but the decision is durably recorded
  with its policy/model/mode and privacy-minimized inputs.
- Challenger v2 on → active behavior is unchanged; each new decision records
  the challenger prediction and Admin Operations can compare both against
  maintainer adjudications.
- Admin Feedback records a positive or negative readiness verdict even if
  GitHub label synchronization is unavailable; priority is never offered as a
  verdict reason.
- `python scripts/replay_agent_policy.py` reports 100% on the checked-in corpus.
- `python scripts/evaluate_agent_eligibility_prompt.py --prompt-version v2`
  reports the semantic corpus score when Azure OpenAI credentials are available.
- Admin **Feedback → Sync from GitHub** records issue transitions, manual
  `agent-ready` recovery, and closing-PR state without fetching tracker text.
- Admin **Operations → Agent learning** shows aggregate decision/outcome counts
  and `draft-with-review` while no class is promoted.
- `python scripts/validate_review_policy.py` succeeds; with the committed empty
  allowlist, a manual `Selective review gate` run reports `review-required`.
- `gh aw validate --no-check-update` succeeds and the policy tuner lock contains
  an exclusive `allowed-files` restriction for
  `config/agent-loop-policy-proposals.json`.
- A web build failure makes `frontend-quality` fail without misreporting
  `backend-tests` when pytest passes.
- A rendered web/miniapp change with an Impeccable finding, placeholder UI
  evidence, missing desktop/mobile review, invalid design-system impact, or
  unexplained miniapp parity fails `frontend-quality` and the compatibility
  required context.
- Invocation-ledger fixtures prove exact base-v1, lifecycle-v1, full-v1, and
  v2 migration to ledger 3; ownerless `read_claimed` sources are refused;
  concurrent initializers all succeed without false corruption; ordinary
  commands refuse ledgers 1 and 2; a second v3 init is a no-op; JSON-schema-1
  requests are refused; and the immutable released-v1 validator freshly
  opening v3 reports `state_unsupported`.
- Native-read fixtures prove canonical `rcl_*` generation, deterministic
  domain-separated fingerprinting, absence of raw tokens from the ledger/WAL,
  same-token retry, different-token and cross-row refusal, commit-then-raise
  and rollback-then-raise reconciliation, invalidation precedence, one-shot
  observation, fail-closed ambiguous observation, and fingerprint retention
  through invalidation and every terminal path.
- Injected pre-commit failures preserve the source logical schema, metadata,
  and rows. Unknown objects, changed constraints, partial auxiliary layouts,
  non-WAL sources, ambiguous historical rows, and conflicting auxiliary rows
  are refused without opportunistic repair.
- A manual `Change loop outcomes` run reports explicit operational tests
  separately, starts the feedback cohort from `agent-ready` issue timelines, and
  does not count `action_required` or a corroborated baseline failure as an agent
  code failure. Allow up to 20 minutes; a successful run creates the replacement
  report before closing the older report.
- `gh aw validate` succeeds.
- From `main`, a manual invariant review reaches GitHub Copilot:

  ```bash
  gh workflow run praxys-invariant-review.lock.yml \
    --ref main \
    -f pr_number=<PR_NUMBER>
  ```

- `gh aw trial` installs the workflow and captures safe outputs in an isolated
  private repository. Resolve the source to an absolute path before running it;
  trial mode changes its working directory after cloning the isolated host
  repository.

```powershell
$workflow = (Resolve-Path .github\workflows\praxys-invariant-review.md).Path
gh aw trial $workflow `
  --clone-repo praxys-run/praxys `
  --append "TRIAL CONTEXT (trusted operator input): review pull request 429 in praxys-run/praxys. Keep all safe outputs in trial capture mode." `
  --delete-host-repo-after
```

```bash
gh run list --workflow=assign-copilot.yml -R praxys-run/praxys --limit 5
```

## Rollback / Recovery

- **Pause the loop:** disable the workflow (`Actions → Change loop … → ⋯ →
  Disable`) or delete `.github/workflows/assign-copilot.yml`. Triage still *adds*
  the label, but nothing acts on it. Or set `PRAXYS_AGENT_READY_SHADOW=true` to
  stop tagging without disabling anything.
- **Pause only the observer layer:** disable the relevant generated
  `.lock.yml` workflow in Actions. To remove it permanently, delete both its
  source `.md` and generated `.lock.yml`; the assignment/coding flow continues.
- **Un-assign Copilot:** `gh issue edit <n> --remove-assignee copilot-swe-agent`
  and remove the `agent-ready` label.
- **Retired local bookkeeping:** private invocation/trial ledgers are retained
  but are no longer used. Do not reset them or re-enroll tasks. Revert the session
  policy/adapters together if needed; restoring code does not authorize a new
  trial or broaden tool permissions.

## Related

- Trigger source: `api/feedback_triage.py` (`_qualifies_for_agent`, `_agent_ready_shadow`).
- Workflows: `.github/workflows/assign-copilot.yml`,
  `.github/workflows/copilot-setup-steps.yml`,
  `.github/workflows/change-loop-outcomes.md`,
  `.github/workflows/ci-failure-doctor.md`,
  `.github/workflows/praxys-invariant-review.md`.
- Agent guidance: `.github/copilot-instructions.md`.
- Historical invocation-ledger records (retired; not current procedures):
  [ODR-2026-08-31-agent-native-read-claim-ownership](./odr-2026-08-31-agent-native-read-claim-ownership.md),
  [TDR-2026-08-31-agent-native-read-claim-ownership](./tdr-2026-08-31-agent-native-read-claim-ownership.md),
  and predecessor
  [ODR-2026-08-30-agent-invocation-ledger-v2](./odr-2026-08-30-agent-invocation-ledger-v2.md).
- Secrets / flags: [config-and-secrets.md](./config-and-secrets.md)
  (`COPILOT_ASSIGN_TOKEN`, `PRAXYS_AGENT_READY_SHADOW`,
  `PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION`).
- Issue-filing setup: [setup-github-app.md](./setup-github-app.md).
- Design: praxys-run/praxys#362 (the change loop); #361 (backend pytest gate); #377 (self-improvement).

---
_Last reviewed: 2026-08-30 · Owner: @dddtc2005_
