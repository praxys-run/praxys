# Mainland China personal-information protection impact assessment

> **Status:** **DRAFT — BLOCKED PENDING HUMAN LEGAL/PIPIA REVIEW**
> **Summary:** Draft assessment for the proposed authenticated `praxys.cn` service,
> including overseas processing, sensitive personal information, recipients,
> necessity, safeguards, and residual risk.
> **Use when:** Releasing or changing the China service, a recipient, a data
> category, an overseas destination, optional AI, telemetry, or a user-rights
> control.

## Assessment record

| Field | Value |
|---|---|
| Record ID | `PIPIA-CN-2026-08-25-01` |
| Version | `1.0` |
| Assessment date | 2026-08-25 |
| Operator / personal-information handler | Fei Tao |
| Rights contact | `support@praxys.run` |
| Service | Authenticated Praxys web service at `praxys.cn` and `www.praxys.cn`; WeChat mini program |
| Decision | **Blocked draft; no approval or residual-risk acceptance recorded** |
| Residual risk | **Medium** — principally the interpretation of contract necessity for a training service that handles sensitive fitness and recovery data |
| Proposed minimum record retention | Through 2029-08-25, and longer while the assessed processing continues or a dispute/investigation requires it; not accepted |
| Next scheduled review | 2027-08-25, or immediately on any trigger below |

### Authoritative documentation Work Contract

- Task: `artifact-reconciliation`; primary object `repository-behavior`; loop
  `delivery`; no nested loop or risk trigger; decision review `false`.
- Classification digest:
  `sha256:ea5b438a17c6b0931f9e03a81606a55893e193438742364b8597e3b6dee34f8f`
- Route digest:
  `sha256:858b1429ea3e90b307923752d783f0ba9bc2665f978ddb2ef9381ddeae4216ab`

This routing metadata bounds the documentation reconciliation; it does not
grant authority, approve this assessment, or authorize production processing.

## 结论摘要

Praxys 的账号、同步、存储、训练计算和必要运维由 Microsoft Azure 在中国大陆
境外处理；本评估生效时主要托管区域为 East Asia（中国香港特别行政区）。
本评估建议认定，该核心境外处理是订立和履行用户主动请求的训练服务合同所严格
必需，依据《个人信息保护法》第十三条第一款第二项，并适用《促进和规范数据跨境
流动规定》第五条第一项。本次核心处理不以同意为依据，但必须在处理前完成充分
告知，并对敏感个人信息的必要性、影响和保护措施作显著说明。

该解释存在中等剩余风险。本评估建议运营者仅在以下控制全部生效后接受该风险：

- `.cn` 网页和小程序在任何个人信息请求前展示版本化告知；
- 服务端以精确版本与内容摘要记录不可覆盖的条款收据；
- 用户主动连接第三方平台前展示接收方、信息类别和官方隐私链接；
- 浏览器分析、产品事件、自动后台 AI 和反馈境外发布在中国发布路径关闭；
- 可选 Azure AI 只允许具有独立、明确、可撤回授权的用途；
- 服务端 Statsig 仅下载规则并在 Praxys 内本地判断，关闭用户日志和 SDK 诊断；
- 香港后台必要遥测最小化并保留 30 天；
- 用户可导出、断开连接和删除账号。

This draft proposes an operator compliance judgment. No operator decision,
legal/PIPIA approval, residual-risk acceptance, or external legal advice is
recorded here.

## Scope and processing decision

The assessment proposes coverage for a future first public authenticated China
release; no such release or processing activation is evidenced here. The static
frontend is delivered from Tencent Cloud EdgeOne, while authenticated API,
database, credential, storage, and essential monitoring services remain in
Azure East Asia (Hong Kong SAR). The service is invitation/private-alpha
software, not medical care, and does not sell personal information or use it
for advertising.

The assessment proposes the following basis for operator acceptance:

1. Core account, sync, storage, deterministic analysis, plan, export, deletion,
   security, and reliability processing is strictly necessary to enter into and
   perform the service requested by the individual.
2. This core path relies on Article 13(1)(2) of the Personal Information
   Protection Law and Article 5(1) of the 2024 Provisions on Promoting and
   Regulating Cross-Border Data Flows. It does not rely on consent.
3. The service still gives the complete pre-processing notice required by the
   PIPL, explains sensitive categories and their impact, and preserves rights
   channels.
4. Optional overseas AI is outside the core basis. It remains off unless the
   exact purpose, fields, destination, and current context version have a
   separate, revocable authorization.

Official sources:

- [Personal Information Protection Law](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)
- [2024 cross-border data-flow provisions](https://www.cac.gov.cn/2024-03/22/c_1712776611775634.htm)
- [CAC questions and answers on the 2024 provisions](https://www.cac.gov.cn/2024-03/22/c_1712776611649184.htm)
- [CAC 2026 questions and answers on separate consent under Article 39](https://www.cac.gov.cn/2026-07/24/c_1786638883119336.htm)

## Processing and recipient map

| Processor / recipient | Location | Information and purpose | Release decision |
|---|---|---|---|
| Tencent Cloud EdgeOne | Mainland China | Public static HTML, JavaScript, CSS, ICP footer, and ordinary delivery logs. It does not receive the authenticated training dataset from Praxys. | Required for the filed China frontend. |
| Microsoft Corporation, Azure affiliates, and subprocessors | Azure East Asia, Hong Kong SAR | Account/contact identifiers, authentication records, encrypted provider credentials, synced training/recovery data, goals, plans, settings, support content, storage, database, API execution, and minimized security/reliability telemetry. | Proposed core overseas processing under contract necessity, pending final operator approval. Microsoft requests: <https://aka.ms/privacyresponseother>. |
| Tencent WeChat | Mainland China | Login code and WeChat identifier for mini-program authentication. | Required only when the user chooses WeChat authentication. |
| Tencent Exmail / WeCom mail service | Mainland China | Destination address and verification, invitation, or requested service-email content. | Required only for the requested email function. |
| Garmin International, Inc. or the Garmin entity selected by account region | Region selected by the user; may be outside mainland China | Authentication details and supported activity, route, recovery, and fitness retrieval. | Optional, user-directed connection. Current notice: <https://www.garmin.com/en-US/privacy/connect/>. |
| Strava, Inc. | United States and other locations in its policy | OAuth/application authorization and activity, route, pace, heart-rate, and related retrieval. | Optional, user-directed connection. Current notice: <https://www.strava.com/legal/privacy>. |
| Athlete Architect LLC (Stryd) | United States and other locations in its policy | Authentication details, running power, activities, Critical Power, and supported plan exchange. | Optional, user-directed connection. Current notice: <https://www.stryd.com/privacy>. |
| Oura Health Oy / Ouraring Inc. | Finland, United States, and other locations in its policy | User-created token and supported sleep, HRV, readiness, and recovery retrieval. | Optional, user-directed connection. Current notice: <https://ouraring.com/privacy-policy>. |
| COROS Wearables, Inc. or the COROS entity selected by account region | Selected account region; may be outside mainland China | Authentication details and supported activities, sleep, HRV, fitness, and training-load retrieval. | Optional, user-directed connection. Current notice: <https://coros.com/privacy>. |
| Microsoft Azure AI | West US 3, United States | Only the minimized fields disclosed for an independently authorized optional purpose. | The dirty-tree controls default this off and require positive enable plus a separately clear kill switch. No live production readback was performed. |
| Statsig service operated by Amplitude | Rules are downloaded from the service; user evaluation occurs inside Praxys | The backend SDK downloads gate/config rules without user identity. `disable_all_logging` and `disable_diagnostics` prevent user exposure events, account identifiers, email, targeting attributes, and training values from being sent. | Not a recipient of China-user personal information under this configuration. Browser Statsig is absent from the `.cn` artifact. |
| GitHub issue service | Outside mainland China | The feedback pipeline could publish scrubbed text in other deployments. | The dirty-tree controls require positive enable and a separately clear publication kill switch, defaulting off. No live production readback was performed; private feedback is intended to remain in Praxys for admin handling. |

The legal entity responsible for a connected provider can vary by the region
the user selects. The connection dialog therefore identifies the provider and
links its current official privacy/contact notice immediately before the user
starts the transfer. Provider-policy drift is a mandatory review trigger.

## Data-category necessity

| Category | Why it is needed | If omitted | Safeguards / retention |
|---|---|---|---|
| Email or WeChat identifier | Create, verify, authenticate, recover, and administer the account | Account or selected login method cannot operate | Passwords are hashed; auth is rate-limited; kept for account lifetime, then deleted subject to short backup/legal records |
| Provider authentication material | Authenticate the connection the user activates and retrieve only that user's data | That provider connection cannot operate | Per-user encrypted storage; Key Vault-wrapped keys; generation fencing; removed on disconnect/account deletion |
| Activities, time, distance, pace, power, and route | Show history and compute the requested training analysis, load, forecast, and plan context | Dependent history, analysis, and forecast features cannot operate | Per-user authorization; encrypted transport/storage; route data is used only when supplied by an activated provider |
| Heart rate, HRV, sleep, recovery, readiness, and related inferences | Produce recovery and training signals requested by the user | Recovery-dependent signals and recommendations cannot operate | Treated as sensitive personal information; purpose-limited computation; no advertising or cross-user model training |
| Goals, thresholds, plans, settings, and language | Configure the requested service and make outputs intelligible | Personalized service cannot operate correctly | Account-scoped access; editable and exportable; deleted with account |
| Optional private plan context | Avoid guessing in a bounded plan decision | Deterministic service remains available with less context | Encrypted; expiry and deletion schedule shown in product; optional notes deleted after 30 days; AI separately authorized |
| Support text and screenshots | Respond to a support or defect report initiated by the user | Praxys may be unable to investigate the report | Screenshots remain private; external issue publication and background AI/vision are disabled for launch |
| Request/route/status timing, coarse client/network data, and pseudonymous account hash | Detect abuse, diagnose outages, preserve security, and verify deletion/reliability | Material security and availability failures become difficult to detect | No intentional raw training payload, credential, token, or email; backend component and workspace retention are 30 days; IP masking remains enabled |

Primary account and training rows remain while the account is active. Account
deletion removes active rows and connected credentials. Azure PostgreSQL
point-in-time recovery can retain deleted content in encrypted backups for up
to 14 days before expiry. Deletion receipts and legally required records may
be retained longer without retaining the active training dataset.

## Sensitive-personal-information assessment

Heart rate, HRV, sleep, recovery, precise activity routes, health/fitness
inferences, and provider authentication material are treated conservatively as
sensitive personal information.

- **Specific purpose:** provide the signal, analysis, forecast, plan,
  connection, or security function requested by the individual.
- **Sufficient necessity:** the service does not require a category for a
  feature that does not use it; users choose which providers to connect.
- **Impact:** unauthorized disclosure could reveal health, routine, location,
  account-access, or behavior patterns and could cause discrimination,
  stalking, account compromise, embarrassment, or other material harm.
- **Controls:** encrypted transport and storage, per-user authorization,
  credential envelope encryption, no public screenshot storage, bounded logs,
  no `.cn` browser telemetry, optional-AI separation, data export, disconnect,
  and account deletion.

## Notice and receipt design

The China processing notice is an acknowledgement of disclosure, not consent
to the core processing:

1. The `.cn` web boundary is outside `AuthProvider`; module prefetch and auth
   restoration both fail closed until the current notice version is stored.
2. The mini-program starts on the notice stage and its API client blocks every
   request until the current version is stored. Every subsequent request
   carries the stamped Miniapp version, stamped full source SHA, and notice
   version.
3. Public product, FAQ, Terms, Privacy, and Status pages remain available
   without personal-data traffic.
4. After authentication, the dirty tree records each exact Terms
   version-and-digest acceptance in an append-only receipt table and updates
   `terms_version` / `terms_accepted_at` only as a current projection. The web
   Terms gate and the mini-program explicit accept-or-sign-out stage enforce
   the current bundle without treating the core Privacy notice as consent. The
   API returns `428 TERMS_ACCEPTANCE_REQUIRED` for ordinary personal-data
   routes while preserving bounded rights routes for stale-policy users.
5. A provider connection is itself a user-directed action and now includes a
   just-in-time recipient/category/privacy notice before credentials or OAuth
   authorization are sent.

The API also rejects any personal request from a `.cn` artifact without its
stamped source SHA and current notice version. WeChat traffic must identify
Miniapp `2026.08.1` or newer and its stamped full source SHA; official
`wx.request` traffic is additionally identified by the platform-managed
`servicewechat.com` Referer. This keeps cached notice-incapable clients from
using an account-wide web receipt as a substitute for the Miniapp notice.

The implemented append-only ledger currently records Terms-bundle acceptance;
it does not establish an accepted standalone China-notice receipt or retention
policy. Whether a distinct channel notice receipt is legally required remains a
Trust/legal decision. Registration atomicity and rights-only login authority
also remain unresolved and must not be inferred from the current route guards.

## Risk analysis

| Risk | Inherent impact | Controls | Residual |
|---|---|---|---|
| Contract-necessity interpretation is challenged for a training service or sensitive categories | High | Exact feature necessity, optional provider choice, no advertising, complete notice, PIPIA, export/delete, and immediate review triggers | **Medium — pending operator acceptance** |
| Overseas legal access or processor compromise | High | Hong Kong core region, encryption, managed identity, Key Vault, per-user authorization, minimal telemetry, processor review | Medium |
| Credentials enable unauthorized provider access | High | Per-user envelope encryption, generation fencing, no shared credential settings, disconnect/delete controls | Medium-low |
| Personal traffic starts before notice | High | Web provider ordering, auth-prefetch guard, auth-restoration guard, Miniapp network guard, versioned local acknowledgement, runtime source/build headers, API rejection of stale clients, and server Terms receipt gate | Low |
| Provider receives more data than expected or changes region/entity | High | User selects connection, just-in-time disclosure, official policy link, supported-category limits, disconnect | Medium |
| Optional/background AI runs without specific authority | High | Production background-AI kill switch, per-purpose consent receipts for private context, deterministic fallback | Low |
| Feedback reaches a foreign/public tracker | High | Private storage, deterministic scrub, production publication kill switch, no background vision/AI | Low |
| Telemetry contains sensitive payload or persists too long | High | No intentional payload/credential/email fields, pseudonymous hashes, IP masking, 30-day backend retention, `.cn` browser telemetry disabled | Low-medium |
| Statsig gate evaluation discloses user identity | Medium | Server-side local evaluation; all SDK user logging and diagnostics disabled; `.cn` browser SDK absent | Low |
| Deletion is incomplete because of backups or processors | High | Active deletion workflow, 14-day PostgreSQL PITR expiry, deletion records, processor coordination, user rights channel | Medium-low |

## Alternatives considered

| Alternative | Proposed disposition |
|---|---|
| Separate consent for all core processing | Rejected for this release. It would misstate the selected legal basis and imply that the account/sync service could continue after withdrawal when it cannot. Optional AI still uses separate authorization. |
| Public information-only `.cn` site | Proposed rejection because the assessed product is the complete authenticated service; final Product/operator authority is pending. |
| Immediate mainland-local API/database rebuild | Not selected for this release due material migration, security, and operational risk. It remains a risk-reduction option if the current legal basis or performance becomes unacceptable. |
| Disable Statsig globally | Rejected because it would fail closed and remove private Stryd and controlled delivery capabilities. Local evaluation with logging and diagnostics disabled preserves the control without user-data egress. |
| Require external counsel before launch | This draft does not propose it as a prerequisite. Final legal/operator review may require specialist advice, especially when a trigger below increases uncertainty. |

## Current draft safeguards and missing evidence

The dirty tree implements a fail-closed China boundary, ordinary `.run` deploys
that leave China disabled and omit `.cn` CORS, an exact registry shape, workflow
readback/CORS-denial/evidence steps, version-and-digest-bound append-only Terms
receipts, bounded stale-policy rights routes, dual optional-processing switches
defaulted off, and account deletion that fails closed on private feedback
screenshot deletion while preserving locators for retry. Registry entries bind
channel/version, 12-character source ID, exact 40-character protected-`main`
commit, current notice/digest/API contract, and provider locator/ID. The
Miniapp production locator is exactly `wechat:robot-1:<version>`; it is
deterministic robot/version evidence rather than a provider-generated opaque
ID. Robot 5 synthetic development versions are never registry authority.

No live provider query or upload-success evidence, runtime readback, DNS/TLS
cutover, permanent Release Evidence store, alert provisioning, or rollback
rehearsal occurred. Export coverage and streaming are blocked by separate
human Product, Architecture, and Trust decisions. Registration atomicity,
rights-only login authority, background-worker kill-switch lifecycle/source
semantics, legal/PIPIA approval, registry lifecycle authority, production
activation, and provider evidence remain unresolved.

## Mandatory controls and release evidence

Before public DNS cutover, Release Evidence must show:

- human acceptance of the
  [proposed China Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md);
- policy version `2026.08.3` in web, API, and mini-program;
- pre-transfer web and mini-program request blocking;
- `CN_PRIVACY_FLOOR_SHA` set to the first protected-main revision containing
  the runtime client boundary and server Terms gate;
- `.cn` source-SHA/notice headers match one exact registry entry, while
  separate served-artifact evidence matches the retained source; replayable
  headers are identifiers, not artifact attestation;
- Miniapp `2026.08.1` or newer mapped to its full source SHA and deterministic
  `wechat:robot-1:<version>` locator, with separate retained upload-success
  evidence and missing/older clients rejected;
- personal-data endpoints returning `428 TERMS_ACCEPTANCE_REQUIRED` before the
  current account receipt and succeeding after explicit acceptance;
- provider just-in-time disclosure in both web connection surfaces;
- `PRAXYS_DISABLE_BACKGROUND_AI=true`;
- `PRAXYS_DISABLE_FEEDBACK_PUBLICATION=true`;
- Statsig server `disable_all_logging=true` and
  `disable_diagnostics=true`;
- `.cn` browser App Insights, Statsig, and product events absent/disabled;
- backend Application Insights and `log-trainsight` retention at 30 days;
- exact `.cn` CORS origins only;
- EdgeOne HTTPS, ICP footer, source SHA, and manifest evidence;
- live outside-in checks and action-group alerts for both `.cn` hosts;
- independently verified account export, provider disconnect, and
  account-deletion paths; export coverage/streaming cannot be marked complete
  until the separate human decisions are recorded.

## Immediate review or stop triggers

Stop the affected new processing until this assessment is updated when any of
the following occurs:

- a new recipient, subprocessor, country/region, purpose, or personal-data
  category;
- optional AI becomes automatic, its model region changes, or a purpose loses
  its durable authorization;
- Statsig user logging/diagnostics are enabled or evaluation moves out of
  process;
- feedback publication is enabled;
- a provider privacy notice, legal entity, or access method materially changes;
- a security incident, unauthorized disclosure, failed deletion, or regulator
  inquiry;
- processing scale, legal guidance, or service design makes the Article 5
  contract-necessity exemption unavailable or materially uncertain;
- a child-directed service, medical purpose, advertising purpose, data sale, or
  cross-user model training is introduced.

If the exemption no longer applies, keep the processing disabled until the
required security assessment, standard contract, certification, consent, or
localization path has been selected and completed.

## Approval

**Operator decision:** BLOCKED — PENDING FINAL HUMAN REVIEW
**Proposed residual risk:** Medium
**Proposed operator:** Fei Tao
**Assessment draft date:** 2026-08-25

## Related implementation and operations evidence

- `web/src/lib/china-processing.ts`
- `web/src/components/ChinaProcessingNoticeGate.tsx`
- `web/src/components/PlatformConnectionNotice.tsx`
- `miniapp/utils/china-processing.ts`
- `miniapp/utils/api-client.ts`
- `miniapp/utils/data-rights.ts`
- `api/china_client_boundary.py`
- `api/legal_receipts.py`
- `api/optional_processing.py`
- `api/data_export.py`
- `api/statsig_client.py`
- `.github/workflows/deploy-backend.yml`
- [../dev/adr-2026-08-26-cn-client-provenance-and-receipt-semantics.md](../dev/adr-2026-08-26-cn-client-provenance-and-receipt-semantics.md)
- [tdr-2026-08-26-cn-privacy-control-boundary.md](./tdr-2026-08-26-cn-privacy-control-boundary.md)
- [odr-2026-08-26-cn-provider-topology.md](./odr-2026-08-26-cn-provider-topology.md)
- [tencent-frontend.md](./tencent-frontend.md)
- [config-and-secrets.md](./config-and-secrets.md)
- [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- [incident-response.md](./incident-response.md)

---
_Drafted: 2026-08-25 · Reconciled: 2026-08-27 · Owner: @dddtc2005 ·
Human approval: PENDING_
