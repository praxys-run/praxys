# WeChat foreground policy: bounded accepted handoff

Stable contract ID: wc-wechat-foreground-20260927

User instruction: “PR 838也合并了，可以rebase过来。允许使用小程序。btw, 这个限制也可以取消了”. This directly follows a question about the repository's extra foreground-only permission requirement.

Work Contract: primary agent-system; impacts repository-change, agent-policy-or-autonomy, trust-boundary; risk triggers security-or-privacy-boundary, out-of-policy-or-out-of-distribution-decision; primary loop meta-eval, nested delivery; lead Meta/Eval; contributor Trust; executor Engineering; fresh independent verifier Quality. Required artifacts: evaluation-report, policy-change-proposal, trust-decision-record, implementation-impact-map, implementation-change, verification-evidence. No outcome artifacts. Decision review required.

Classification digest: sha256:8b187aabec94a62819d5c8067f886916bfa520961fc7e56cc08d2895f2791c46

Route digest: sha256:60201e7633a1f2c080c1458ae41f32ece889226b4a3ec1b076dfb2c6a83c2960

## Evaluation Report ER-wechat-foreground-2026-09-27-v1

Owner: Meta/Eval (/root/wechat_foreground_policy). Implementation status: logical-contract. Status: bounded evaluation complete; population outcome evidence unavailable. Observed checkout: df34f2d9b80fbfe1d3641942d9b1db3cbd041e42.

The coordinator supplies one explicit user correction: “允许使用小程序。btw, 这个限制也可以取消了”, following a question about separate foreground permission. Repository inspection confirms scripts/wechatide:93–102 blocks Windows CLI calls solely when WECHATIDE_ALLOW_FOREGROUND lacks an accepted value. Tencent readiness, authorization, and sensitive-action requirements are separately documented.

This supports proposing the requested local policy correction. Completed-decision counts, elapsed review effort, interruption frequency, adverse outcomes, reverts, and incident rates are unknown. No empirical autonomy or runtime-parity promotion is justified.

Tabletop comparison, without native execution:

- Authorized simulator validation; variable unset: current extra approval plus variable becomes proceeding through Tencent readiness gates.
- Explicit prohibition of visible tools: do not launch under either policy.
- Incomplete login/client/token authorization: complete upstream authorization under either policy.
- Preview/upload/cloud write/destructive operation: preserve upstream confirmations under either policy.
- Raw desktop automation required: unsupported; verification incomplete under either policy.
- No native simulator in cloud: native evidence pending and PR draft under either policy.

Expected benefit is removal of redundant permission requests. That benefit remains a hypothesis until subsequent tasks provide observations.

## Policy Change Proposal wechat-foreground-task-authorization-v1

Owner: Meta/Eval. Required artifact type: policy-change-proposal (repository-native); supplied inline for coordinator review and later repository-native inclusion. Status when proposed: proposed, not self-approved. Dependency: Evaluation Report above, followed by Trust boundaries and independent Decision Review.

Recommended rule:

“An authorized miniapp task may launch visible WeChat DevTools through the repository wrapper without separate foreground permission or a per-command foreground environment variable. Honor explicit user restrictions. Complete Tencent’s required readiness, login, client/token authorization, asynchronous-task protocol, and sensitive-action confirmations.”

Engineering edit boundary:

- Remove the standalone foreground refusal block from scripts/wechatide.
- Align .github/skills/wechat-devtools/SKILL.md, AGENTS.md, .github/copilot-instructions.md, .github/agents/praxys-change-loop.agent.md, .github/instructions/ui-quality.instructions.md, docs/skills.md, docs/dev/ui-quality-harness.md.
- Update only foreground-permission wording in config/copilot-execution-parity.json and docs/dev/copilot-execution-parity.md; retain unavailable-cloud-runtime and draft-evidence boundaries.
- Update examples/guidance in tests/fixtures/dfa/README.md.
- Align the additional current guidance at docs/dev/activity-dfa-alpha1-verification.md:80 while preserving historical facts.

Preserve Tencent installed schemas and authorization/confirmation gates; valid AppID, credential secrecy and synthetic verification; dedicated generated mirror, source ownership, sync protections and no mirror edits; registered tools only and no raw Win32 focus/cursor/keyboard/mouse/coordinate automation; bounded project-window reuse/cleanup without closing unrelated user windows; truthful compilation/rendering evidence and incomplete status when capabilities are absent; existing role separation, review classes, tool allowlists and autonomy-promotion policy.

Alternatives: retaining the current gate conflicts with the user correction; removing wider authorization controls exceeds its scope.

Independent Quality should verify wrapper dispatch without the variable, retained failure/protection paths, documentation consistency, shell syntax and scripts/check_agent_runtime_parity.py. Native validation remains separate evidence.

Immediate stop path: an explicit user prohibition stops further native calls. Authorization bypass, credential exposure, destructive mirror behavior or unwanted desktop interaction triggers containment and review. Reverting this bounded patch restores the prior gate.

Observe subsequent tasks for repeated permission questions, user corrections, desktop interruptions, confirmation bypasses, incomplete verification and elapsed effort. Broader autonomy claims require configured batch/observation thresholds.

Meta/Eval performed no edits or native tools and did not self-approve.

## Trust Decision Record TDR-wechat-foreground-2026-09-27-v1

Owner: Trust (/root/wechat_foreground_trust). Status when supplied: proposed specialist contribution pending independent Decision Review. Subject: wechat-foreground-task-authorization-v1 under this Work Contract.

Trust supports removing the separate foreground opt-in and variable for authorized miniapp tasks subject to these constraints. The existing wrapper gate controls desktop interruption; Tencent separately enforces client authorization, login and applicable tokens. Removing the gate does not itself grant those capabilities.

Assets: desktop session, authenticated DevTools state, athlete data, credentials, Windows project files. Boundaries: task authorization → registered tools → DevTools; repo → generated mirror; simulator state → captured evidence. Failure modes: unwanted activation, unrelated-window interference, personal-data capture, confusing launch permission with publishing/data-mutation authority.

Required constraints:

- Authorized miniapp work may launch visible registered tools through the wrapper without another foreground question. Explicit user restrictions remain binding.
- Preserve Tencent readiness, client authorization, login, applicable token checks and pending confirmations. Foreground authorization does not authorize upload/cloud/destructive operations or bypasses.
- Preserve dedicated mirror path, marker refusal and exclusions; checkout remains authoritative.
- Registered tools only; preserve no raw Windows focus/cursor/mouse/keyboard/coordinate automation.
- Reuse one project window; close only task-owned windows; preserve pre-existing/unrelated windows.
- Synthetic simulator evidence only. For DFA install request/storage mocks before inspection; preserve teardown and no-backend-call constraints. No tokens, authenticated network archives or personal data in evidence. Upstream docs cannot override repo/role credential restrictions.

Quality: verify unset-variable dispatch preferably using isolated bridge stub; inspect unchanged mirror/argument safeguards; check policy wording and static parity. Native evidence identifies tested build and actual scenarios. Cloud cannot supply local desktop evidence; historical preparation remains truthful.

Residual risk: visible DevTools can interrupt the shared desktop. This correction accepts that effect within authorized miniapp work; it establishes neither desktop isolation nor broader autonomy.

Trust reviewed repository and installed Tencent skill 0.3.11 read-only. No edits, native calls, credential access, implementation approval or runtime verification performed.

## Independent Decision Review

Router: /root/wechat_foreground_decision. Route: human-review-required. Human authority is already satisfied for this precise change by the quoted contextual user instruction; no repeat permission question is needed.

Reason: unpromoted agent-policy/security boundary with empty agent_reviewed_classes. This router supplies no approval itself. The user supplies the required choice. No signed or artifact-bound human approval has been materialized.

Allocation: Meta/Eval owns proposal/observations; Trust owns controls; Engineering implements; fresh read-only Quality without executor history independently verifies the resulting patch. The existing user occupies the human-authority slot.

Deferred: implementation acceptance, native evidence and measured outcomes. No autonomy promotion, runtime-parity claim, publishing permission or future scope expansion follows.

Router-reported immutable reviewed-evidence digest: sha256:a7ff24c946a280055119d8cd5a22e01d8d66133553c431628370ab278a5d84c0. It hashes the exact proposal paragraph supplied to that router in the parent message, UTF-8 without trailing newline; it is NOT the digest of this assembled handoff and is NOT a human signature.

Engineering may proceed within the bounded instruction; independent Quality verifies dispatch, safeguards, docs, syntax and static runtime conformance.

## Coordination

Root continues separately authorized DFA native validation and owns local synthetic evidence. Existing PR839 stays draft; no merge, science activation, deployment or reviewer requests. Preserve original untracked paseo.json and exact plugin gitlink. No code freeze until native fixture/transport issues are resolved or precisely evidenced; batch all preparatory generation/build checks before final committed-head preflight.

## Implementation Impact Map IIM-wechat-foreground-2026-09-27-v1

Owner: Engineering. Status: implementation prepared for independent Quality;
not implementation acceptance or a self-approved policy decision. The preceding
records preserve their original owners, supplied statuses and decision sources.
The contextual user instruction satisfies only the precise human-choice boundary
reported by the independent router; no human signature or autonomy promotion is
inferred from this repository record.

Input revision: `df34f2d9b80fbfe1d3641942d9b1db3cbd041e42`.

| Surface | Bounded implementation | Preserved boundary / verification |
| --- | --- | --- |
| `scripts/wechatide` | Remove only the standalone foreground opt-in refusal. | WSL/install/bridge checks, mounted dedicated mirror and marker refusal, exclusions, argument conversion and process exit propagation remain intact. Isolated stub regression exercises dispatch and failure paths. |
| Canonical skill and role/UI instructions | Replace separate foreground permission with authorized-task scope and explicit-user-restriction checks. | Tencent readiness/login/client/token/pending/sensitive-action gates, registered tools, no raw desktop automation, task-owned window cleanup, synthetic evidence and credential restrictions remain. |
| Copilot execution parity config/doc | Change only the foreground-permission wording. | Missing cloud simulator still requires local evidence and a draft PR; no runtime-parity promotion. |
| DFA native fixture README and current verification guidance | Remove obsolete foreground question/variable examples; preserve historical preparation and browser facts. | No fixture logic or rendered-success claim changes. Root owns the separate native investigation. |
| Repository-native decision record | Mechanically persist supplied ER, proposal, TDR and independent route above, plus this impact map. | Supplied owner/status and digest meanings remain explicit; Quality owns implementation verification. |
| Application/backend/science/runtime configuration | No implementation changes. | Existing source, authorization, scientific activation, deployment and plugin boundaries remain unchanged. |

Execution evidence for this bounded patch is reported in the coordinator handoff:
Bash syntax, isolated wrapper tests, skill validation and static runtime parity.
These checks do not replace independent Quality or prove native simulator behavior.
The temporary test copy redirects only the host PowerShell executable and mounted-
drive prefix to isolated paths; the real guard and argument logic run without any
Windows process or GUI. Native transport failures remain separate evidence and do
not authorize changing fixture logic without a reproduced cause.

## Independent verification VE-wechat-foreground-quality-20260927-v1

Owner: independent Quality. Subsequent finding: **no unresolved policy blocker**
at immutable patch
`7912cef62400e1764d11ec9fcc78cc2a38aeaf676b16cc7d6bad1cccc1c57c07`.
The Delivery coordinator supplied this terminal verification after the original
records above; their supplied statuses and contextual authority remain historical.

Quality independently checked all 14 file hashes and reverse applicability,
ran 10 repository wrapper regressions plus 17 temporary bridge/real-rsync
scenarios, and verified shell syntax, diff checks, static runtime parity and
reproduced routing. It confirmed the generic skill validator's pre-existing
incompatibility with the two canonical Copilot metadata fields; metadata was
preserved. These results verify the bounded policy implementation, not broader
autonomy, measured runtime parity or native simulator behavior. Later native
fixture compatibility work is separately verified under DFA delivery.
