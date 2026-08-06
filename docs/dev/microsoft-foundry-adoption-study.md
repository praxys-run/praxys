# Microsoft Foundry adoption study

**Status:** Study and isolated incident-loop proof of concept complete;
production decisions recorded below.
**Evidence date:** 2026-08-06.

## Decision

| Workload | Decision | Why |
|---|---|---|
| Change loop | Keep the current GitHub reviewer plus deterministic approval gate. Retain a Foundry review-only hybrid as a future option. | The current gate binds authorization to trusted GitHub state, exact refs, an independent App, required checks, revocation, and kill switches. A model that reviews and authorizes its own merge weakens that separation. |
| Incident loop | Keep the production runtime external and ephemeral. Use the Foundry project Responses API and cloud evaluation selectively; do not productionize the Hosted-agent PoC. | Hosted preserved the safety boundary and added excellent traces, but did not improve investigation quality, cost about 6.7x the direct model-only batch under the conservative 15-minute session assumption, and added preview-specific protocol, evaluation, session-accounting, and deployment complexity. |
| Azure SRE Agent | Do not create one in the production subscription for this PoC. Keep it in the incident-platform comparison. | Current documentation lists a subscription-scoped Monitoring Contributor role in its standard permission set, and the service's minimum active-flow allocation is 500 AAUs. That does not meet the isolation and hard-exposure requirements without a dedicated non-production subscription and a proven per-thread cost guard. |
| Coach insights | Keep the current direct call. Consider a future offline A/B of Foundry Responses plus cloud evaluation, but do not add a persisted agent. | The workload is stateless, tool-free, schema-constrained, cached, capped, transaction-safe, fallback-safe, and already inexpensive. The incident PoC showed evaluation value, not evidence that a persisted runtime improves one-shot generation quality. |

The PoC was not a production migration. It ran only fixture-backed shadow-mode
cases with dedicated telemetry and no mutation permissions.

## Current baselines

### Foundry project

- Reuse `rg-trainsight` / `praxys-ai-resource` / `praxys-ai` in `westus3`.
- The project was healthy before the PoC. The PoC temporarily added one
  `gpt-5.4-mini` deployment, one Hosted agent, dedicated telemetry connections,
  and cloud evaluation definitions; the account and project themselves remain
  the user's reusable Foundry foundation.
- `gpt-5.4-mini` Global Standard is available.
- The regional quota meter reported 150 of 3,000 thousand tokens/minute already
  allocated for `gpt-5.4-mini`, leaving ample headroom for a small deployment.
- The signed-in Azure identity inherits Owner, User Access Administrator, and
  Foundry User. The PoC agent itself must receive only the narrower roles it
  needs.
- Foundry and Azure SRE Agent MCP discovery currently fails to resolve the
  authenticated tenant even though Azure CLI access works. The implementation
  must use a supported CLI/SDK fallback until that credential path is fixed.

### Change loop

The current design deliberately separates three functions:

1. GitHub Copilot drafts a PR.
2. `praxys-invariant-review` supplies read-only model evidence.
3. `selective-review.yml` and `analysis/review_policy.py` make a deterministic
   decision from trusted GitHub state; an independent GitHub App is the only
   identity that can approve and enable normal auto-merge.

The gate re-reads and binds:

- repository, base ref, base SHA, and head SHA;
- draft/ready state and the ready-for-review head;
- required checks and strict-base behavior;
- complete changed-file inventory and sensitive paths;
- linked `agent-ready` issue provenance;
- requested changes and stale approval invalidation;
- runtime enablement and kill switch; and
- App identity before approval, auto-merge, or stale-state cleanup.

Targeted review-policy tests pass: **24 passed**.

Complete workflow history at the evidence date:

| Workflow | Runs | Success | Failure | Cancelled | Skipped | Action required |
|---|---:|---:|---:|---:|---:|---:|
| Change loop outcomes | 7 | 4 | 3 | 0 | 0 | 0 |
| Change loop policy tuner | 1 | 1 | 0 | 0 | 0 | 0 |
| CI failure doctor | 273 | 19 | 2 | 0 | 246 | 6 |
| Praxys invariant review | 217 | 194 | 14 | 5 | 0 | 4 |
| Selective review gate | 584 | 370 | 66 | 144 | 0 | 4 |

The cancellation volume is expected from per-PR `cancel-in-progress`
concurrency; the gate's final state is still fail-closed and head-specific.

### Coach insights

The current implementation is:

- one direct Azure OpenAI call per generated insight;
- strict bilingual JSON validation;
- content-addressable caching;
- a per-user daily cap;
- revision and transaction race protection;
- deterministic product fallback; and
- token, run, error, and durable feedback telemetry.

Observed `appi-praxys-backend` totals over 28 days:

| Insight | Generated | Hash match | Prompt tokens | Completion tokens |
|---|---:|---:|---:|---:|
| Training review | 95 | 178 | 290,942 | 90,813 |
| Race forecast | 10 | 263 | 13,056 | 7,465 |
| **Total** | **105** | **441** | **303,998** | **98,278** |

No operator-actionable Coach errors or Coach votes were recorded in the same
window. Azure OpenAI dependency latency is not currently attributable per
insight in Application Insights; the PoC must record end-to-end latency
explicitly.

At public Global Standard prices:

- `gpt-5.4`: about **USD 2.23 per 28 days** for this observed workload.
- `gpt-5.4-mini`: about **USD 0.67 per 28 days** for the same token counts.

Cost is therefore not a reason to introduce a persisted Coach agent.

### Incident loop

`praxys-run/praxys-ops-agent` currently provides:

- a framework-free bounded tool loop;
- `SHADOW` mode;
- deterministic green/yellow/red action policy;
- runbook-match confidence proxies rather than model self-confidence;
- duplicate evidence-query suppression;
- step-budget escalation;
- PII-scrubbed, budgeted evidence;
- a Case timeline; and
- declarative policy fixtures.

Final PoC validation:

- **29 focused pytest tests passed**.
- **12 policy expectations passed** across restart recovery, PostgreSQL pool
  exhaustion, and database-corruption escalation.
- Red actions and missing-runbook actions escalate; no fixture executes a
  mitigation.

## Review and approval gate comparison

The comparison must distinguish review quality from merge authorization.

| Property | Current GitHub gate | Pure Foundry review/merge agent | Hybrid Foundry evidence |
|---|---|---|---|
| Reviewer | Read-only Agentic Workflow | Foundry agent | Foundry agent |
| Authorizer | Deterministic workflow plus independent GitHub App | Same agent or its write connector | Existing deterministic workflow plus independent App |
| Input binding | Exact base/head refs and trusted GitHub state | Template-dependent; not yet proven | Structured verdict must include exact repo, PR, base, head, policy version, and expiry |
| TOCTOU handling | Re-evaluates refs and runtime controls before approval and merge | Must be built and proven | Existing re-evaluation remains authoritative |
| Revocation | Explicit stale review/auto-merge cleanup and issue-event guard | Template-dependent | Existing cleanup remains authoritative |
| Prompt injection effect | Can affect a comment, not authorization | Can become a merge-authority risk | Can affect evidence; deterministic policy still fails closed |
| Failure behavior | Human review required | Depends on agent/connector design | Human review required |
| Portability | Python/JSON/YAML/GitHub primitives | Foundry and connector specific | Verdict contract is portable; traces are Foundry-specific |

### Template finding

The exact portal card described as a PR review-and-merge assistant could not be
exported from the target tenant:

- the browser identity available to the automation session is not a member of
  that Azure tenant;
- Foundry MCP tenant discovery fails; and
- the Microsoft GitHub organization requires SAML authorization for the current
  GitHub token.

The public `microsoft-foundry/foundry-samples` repository does include a
`resilient-approval-gate` Hosted-agent sample, but it is **not** a PR reviewer:
it contains no GitHub integration or pull-request/merge logic. It demonstrates
the safer opposite pattern—human approval of a plan and every irreversible
step, durable checkpoints, and at-most-once side effects.

No official source inspected in this study demonstrated all of Praxys's
required merge controls: exact-SHA authorization, trusted-state re-read,
independent identity, stale approval revocation, kill-switch recheck, and
fail-closed cleanup.

### Gate conclusion

- **Current gate:** production choice.
- **Hybrid:** credible future enhancement if Foundry review quality materially
  exceeds the current invariant reviewer. Foundry output remains untrusted
  evidence.
- **Pure Foundry merge agent:** rejected for production authorization unless a
  disposable-repository benchmark proves zero false approvals and equivalent
  exact-ref/revocation controls. It was not selected for the one PoC.

## Incident platform comparison

| Property | Direct / Container App Job | Foundry Responses | Foundry Hosted agent | Azure SRE Agent |
|---|---|---|---|---|
| Runtime | Praxys-owned ephemeral process | Praxys-owned process | Foundry-managed custom container | Microsoft-managed always-on SRE service |
| Existing investigator reuse | Full | Full | Full behind a thin adapter | Partial; custom agent/tools/hooks must translate it |
| Trigger | Azure Monitor → dispatch/job | Same | `Invocations` adapter | Native incident response plans |
| Pre-action policy | Existing Python gate | Existing Python gate | Existing Python gate inside hosted code | Must prove `PreToolUse` covers every action path |
| Identity | Per-run OIDC | Per-run OIDC plus Foundry data-plane access | Dedicated agent identity | Standing UAMI; documented Monitoring Contributor and optional OBO |
| State | Case plus external store | Same | Session/task state plus Case | Product threads and persistent memory |
| Evaluation | Local fixtures | Local plus Foundry project evaluation | Foundry traces, datasets, evaluators, and version comparison | Thread insights and audit; batch replay is less explicit |
| Cold start | Job cold start | Job cold start | Scale-to-zero Hosted cold start | Always on |
| Standing cost | None | None | None while scaled to zero | 4 AAUs/hour |
| Portability | Highest | High | Medium | Lowest |

### Azure SRE Agent findings

Strengths:

- purpose-built Azure incident plans and alert routing;
- built-in Azure operational expertise and tools;
- custom agents, Python tools, MCP, hooks, memory, schedules, and proactive
  analysis;
- Review and Autonomous modes;
- isolated tool sandboxes, action audit, and per-thread AAU reporting; and
- no cold start.

Blocking or material concerns for Praxys:

- USD 0.10/AAU and 4 AAUs/hour of fixed always-on flow: about **USD 292/month**
  before active investigation usage;
- stopping the agent does not stop the fixed charge; deletion does;
- the minimum active-flow allocation is 500 AAUs, representing USD 50 of
  possible active use even though it is not prepaid;
- standard permissions document a subscription-scoped Monitoring Contributor
  role for alert lifecycle operations;
- OBO can temporarily use an administrator's permissions;
- current US deployment is cross-region from `westus3`;
- product-managed tools, subagents, memory, and alternate paths make exact
  equivalence with Praxys's pre-tool policy a proof obligation; and
- persistent product state and connectors increase lock-in and teardown work.

The previous incident ADR's roughly USD 200/month estimate is outdated, but its
control-plane conclusion remains valid. SRE Agent becomes more compelling if
Praxys needs continuous proactive operations across several services and can
use enough built-in functionality to justify the fixed floor.

## Coach runtime comparison

| Property | Current Chat Completions | Foundry Responses | Persisted prompt agent |
|---|---|---|---|
| Stateless one-shot fit | Excellent | Excellent | Poor |
| Existing JSON/fallback/cache controls | Native | Preserved | Preserved only through extra application glue |
| Tools or memory needed | No | No | No current need |
| Managed evaluation | Limited | Strong | Strong |
| Operational surface | Smallest | Small | Larger: agent versions, configuration, possible state |
| Expected cost reason to move | None | None; quality/evaluation only | None |

Use Foundry Responses only if its trace/evaluation workflow produces enough
quality-management value to justify a client and deployment migration. Do not
add an agent resource merely to wrap the same prompt.

## Pre-PoC weighted scorecard

Weights emphasize safety and authorization because both compared loops can
write to operational systems:

| Dimension | Weight |
|---|---:|
| Functional fit | 12 |
| Safety boundary | 18 |
| Authorization locus | 12 |
| Trigger/integration | 8 |
| Identity/data boundary | 10 |
| Evaluation/observability | 10 |
| Delivery/operations | 8 |
| Managed-product leverage | 5 |
| Latency/reliability | 5 |
| Cost | 6 |
| Portability | 3 |
| Reversibility | 3 |

Scores are 1–5 and evidence-backed:

| Workload | Candidate | Weighted score |
|---|---|---:|
| Change | Current GitHub gate | **4.45** |
| Change | Foundry evidence + deterministic gate | 4.30 |
| Change | Pure Foundry review/merge gate | 2.82 |
| Incident | Foundry Hosted agent | **4.49** |
| Incident | External runtime + Foundry Responses | 4.36 |
| Incident | Direct / Container App Job | 4.06 |
| Incident | Azure SRE Agent | 3.15 |
| Coach | Foundry Responses | **4.71** |
| Coach | Current direct call | 4.60 |
| Coach | Persisted prompt agent | 3.69 |

The highest absolute score was Coach Responses, but it improves the current
option by only 0.11 and does not justify an agent-runtime PoC. The incident
Hosted option improves the direct design by 0.43 and clears every selection
gate:

1. it uses multiple needed platform capabilities;
2. deterministic policy remains structural;
3. a checked-in fixture corpus exists;
4. the run can be fully synthetic and isolated;
5. projected spend fits USD 25; and
6. the adapter can be removed to return to the direct brain.

## Selected PoC contract

The incident PoC must:

- live in `praxys-run/praxys-ops-agent`;
- reuse the investigator, policy, toolbelt, Case, and fixtures;
- add a thin versioned `Invocations` adapter;
- add a Foundry Responses brain as the non-hosted control;
- use `gpt-5.4-mini` unless capability testing rejects it;
- run only fixture-backed read/proposal tools in `SHADOW`;
- execute no Azure or GitHub mutation;
- use dedicated Application Insights;
- compare direct, Responses, and Hosted results on the same cases;
- record root-cause/action correctness, escalation, schema validity, steps,
  tokens, latency, trace completeness, and cost;
- stop new paid runs at USD 20 estimated spend; and
- remain below USD 25 observed spend.

Azure SRE Agent remains a documented comparison unless a dedicated
non-production subscription and a strict per-thread AAU guard become available.

## Incident PoC implementation

The PoC was built on a local `copilot/foundry-incident-poc` branch in the
private `praxys-run/praxys-ops-agent` repository. It was not promoted as
production code. It added:

- a Python 3.13 Hosted agent using Invocations protocol 2.0.0;
- a strict versioned fixture-only request/response contract;
- `gpt-5.4-mini` through both Chat Completions and the Foundry project Responses
  API;
- the existing investigator, deterministic policy table, runbook allowlists,
  shadow mode, and Case output;
- a four-evidence-query ceiling, duplicate evidence/action suppression, and
  offered-tool enforcement;
- seven synthetic safety fixtures;
- dedicated `appi-praxys-ai-poc` / `law-praxys-ai-poc` telemetry;
- a filtered USD 25 budget with 50%, 80%, and forecasted 100% notifications;
- a persistent application-side cost/session ledger; and
- a teardown manifest covering sessions, versions, connections, model,
  telemetry, roles, and budget.

The agent had no production credentials, production data, GitHub write
permission, Azure mutation tool, or live mode. Every proposed action reported
`executed=false`.

## Measured results

### Runtime comparison

The table uses the final seven-case corpus. Direct durations are measured around
each complete investigator call. Hosted latency is the application request
duration from Application Insights and excludes session creation/warm-up.

| Variant | Deterministic result | Model calls | Input / output tokens | Estimated model cost | Latency |
|---|---:|---:|---:|---:|---:|
| Direct Chat Completions | **7/7** | 26 | 19,603 / 2,204 | USD 0.02462 | 113.95 s batch; 16.28 s/case |
| Foundry project Responses | **5/7** on the timed batch; both false holds passed on immediate targeted retry; an earlier final-policy batch was 7/7 | 24 | 13,239 / 2,247 | USD 0.02004 | 90.91 s batch; 12.99 s/case |
| Foundry Hosted v5 | **7/7** | 22 | 12,246 / 2,194 | USD 0.01906 model + USD 0.10780 conservative Hosted compute = **USD 0.12686** | 4.57 s mean request; 5.34 s p50; 6.24 s p95; seven isolated requests spanned 172.65 s |
| Foundry cloud eval against Hosted v5 | **7/7**, all task-adherence scores 1.0 | 23 target calls | 12,797 / 2,293 target tokens | USD 0.01992 target model; **USD 0.75810** conservative target + judge + seven-session reserve | 436 s end to end |

The two Responses failures were safe false holds: the model identified the
correct root cause but escalated instead of proposing the documented restart.
Both cases passed when rerun immediately. No run proposed an unauthorized
action, executed an action, or converted ambiguity into permission. This is
useful evidence that the deterministic policy owns safety, while model/runtime
outputs still need reliability evaluation.

### Cloud evaluation and telemetry

The first `azd ai agent eval run` attempt serialized each JSON fixture as a chat
message. The Invocations endpoint correctly rejected all seven requests because
the body was not a JSON object. The supported SDK path required a freeform
`input_messages` object. Two additional preview integration details were found:

- Foundry injects a transport `session_id` into Invocations evaluation bodies.
  The adapter now validates and removes that transport field before strict
  business-contract validation.
- Placeholder substitution coerced `"1.0"` to numeric `1`; the schema version
  and shadow mode therefore use literal values in the evaluation template.

The corrected cloud run produced:

- 7 successful top-level request traces and 0 failures;
- 45 dependency rows and 90 trace rows across all 7 operations at query time;
- exactly 7 application completion logs and 0 error-severity trace rows; and
- exported Foundry report identifiers:
  `eval_52e0ac001da54d2c8ca0280a763f2e35` /
  `evalrun_f45a423c21ae4121a47fd076f049161c`.

The built-in evaluator is quality evidence only. It does not replace the
deterministic fixture evaluator or authorize any mitigation. The remote
evaluation definition was deleted after the result was exported.

### Cost and guardrail findings

- The reconciled application ledger estimated **USD 1.25936** for all
  development, failed integration attempts, direct controls, Hosted runs, and
  cloud evaluation.
- Azure Cost Management was throttled during the final query, and the legacy
  consumption API had not yet received any same-day usage rows. Provider-billed
  actuals were therefore still delayed at the evidence cutoff.
- The USD 20 stop-new-work threshold and USD 25 absolute envelope were never
  approached.
- The initial ledger counted one session per cloud-evaluation run. Foundry
  actually created one Hosted conversation per dataset row. Reconciliation
  raised the observed session count from 21 to **28**, exceeding the planned
  24-session fuse even though spend remained low. The guard now reserves and
  records batch session fan-out before submission; no more Hosted runs are
  permitted by the corrected ledger.

This accounting defect is a meaningful Hosted-operations finding: platform
fan-out must be modeled as billable work, not inferred from the number of
client-side API calls.

### Operational burden

Five immutable Hosted versions were needed to reach the final result. The PoC
also exposed:

- Foundry/Azure MCP authentication selecting the wrong tenant while authenticated
  `azd`, Azure CLI, and SDK calls worked;
- an `azd` Invocations evaluation mapping gap requiring a small SDK runner;
- service-injected transport metadata and template type coercion;
- cloud evaluation creating one Hosted session per row;
- preview SDK type definitions lagging supported service discriminators;
- an account-level Application Insights connection reporting
  `isSharedToAll=true` despite a private request; and
- more deployment, session, connection, telemetry, evaluation, and teardown
  state than the external runtime.

These are manageable for a platform team, but they outweigh Hosted's managed
runtime benefit at current Praxys incident volume.

## Final production decision

### Change loop

Keep the GitHub-native implementation and independent deterministic
authorization gate. Foundry may supply read-only review evidence later, but it
must never approve or merge from its own judgment.

### Incident loop

Do **not** promote the Hosted PoC. Keep the investigator and policy engine in an
external ephemeral process, with the planned Container App Job as the production
runtime. Prefer the Foundry project Responses API over Chat Completions when its
lower token use, unified project identity, and evaluation integration are useful,
but retain the direct adapter as a reversible control.

Instrument the external runtime with GenAI OpenTelemetry conventions and use
Foundry cloud **trace or precomputed-dataset evaluation**. This captures the
strongest managed capability demonstrated by the PoC without coupling every
incident to Hosted session lifecycle.

The bounded shadow-provider implementation and promotion gate are tracked in
[`praxys-ops-agent#6`](https://github.com/praxys-run/praxys-ops-agent/issues/6).

Reconsider Hosted when Praxys needs managed multi-session state, autoscaling,
version rollout, or custom protocol hosting often enough to offset the added
preview surface. Reconsider Azure SRE Agent only in a dedicated non-production
subscription and only if proactive cross-service operations can justify its
fixed monthly floor.

### Coach insights

Keep the current direct, stateless implementation. If Coach quality work needs a
managed eval loop, first run an offline privacy-safe A/B between the current call
and Foundry Responses. Do not create a persisted prompt agent without a concrete
state or tool requirement.

## Teardown result

Retain the existing `praxys-ai-resource` account and `praxys-ai` project as the
user-created Foundry foundation. After evidence export, the PoC Hosted agent and
all sessions/versions, five cloud evaluation definitions, both telemetry
connections, `gpt-5.4-mini` deployment, dedicated Application Insights and Log
Analytics resources, their resource-scoped roles, and `budget-praxys-ai-poc`
were deleted.

Negative inventory verification returned zero PoC agents, evaluations,
connections, model deployments, telemetry resources, and budgets. The retained
Foundry account remained `Succeeded`, and the project endpoint remained
accessible. No production runtime depends on the deleted resources.

## Sources

- [Microsoft Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview)
- [Hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Foundry runtime components](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/runtime-components)
- [Foundry Responses API](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/responses-api)
- [Foundry cloud evaluation](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/cloud-evaluation)
- [Foundry Agent Service pricing](https://azure.microsoft.com/en-us/pricing/details/foundry-agent-service/)
- [Official resilient approval-gate sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/invocations/resilient-approval-gate)
- [Azure SRE Agent overview](https://learn.microsoft.com/en-us/azure/sre-agent/overview)
- [Azure SRE Agent pricing](https://learn.microsoft.com/en-us/azure/sre-agent/pricing-billing)
- [Azure SRE Agent permissions](https://learn.microsoft.com/en-us/azure/sre-agent/permissions)
- [Azure SRE Agent run modes](https://learn.microsoft.com/en-us/azure/sre-agent/run-modes)
- [Azure SRE Agent command hooks](https://learn.microsoft.com/en-us/azure/sre-agent/command-hooks)
- [Azure SRE Agent incident response](https://learn.microsoft.com/en-us/azure/sre-agent/incident-response)
- [Azure SRE Agent supported regions](https://learn.microsoft.com/en-us/azure/sre-agent/supported-regions)
- [Azure SRE Agent usage monitoring](https://learn.microsoft.com/en-us/azure/sre-agent/monitor-agent-usage)
- `docs/dev/agentic-loops.md`
- `docs/ops/change-loop.md`
- `praxys-run/praxys-ops-agent/docs/architecture.md`
- `praxys-run/praxys-ops-agent/docs/adr/0004-loop-b-build-own-incident-agent.md`
- `praxys-run/praxys-ops-agent/docs/adr/0007-bounded-autonomy-and-severity.md`
- `praxys-run/praxys-ops-agent/docs/adr/0009-loop-b-lean-build-holmesgpt-informed.md`
