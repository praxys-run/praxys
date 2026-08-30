# Mainland China personal-information protection impact assessment

> **Status:** **DRAFT — EXACT HUMAN PIPIA ACCEPTANCE REQUIRED BEFORE ENABLE**
> **Summary:** Assessment record for the invite-only, web-only China private
> alpha and its overseas Azure processing.
> **Use when:** Deciding whether to enable or materially change the China web
> alpha, a recipient, data category, destination, or rights control.

## Assessment record

| Field | Value |
|---|---|
| Record ID | `PIPIA-CN-2026-08-25-01` |
| Version | `1.1-web-private-alpha` |
| Assessment date | 2026-08-29 |
| Operator / personal-information handler | Fei Tao |
| Rights contact | `support@praxys.run` |
| Service | Invite-only web private alpha at `praxys.cn` and `www.praxys.cn` |
| Decision | **Not accepted. Exact human acceptance and residual-risk decision are required before `launch-cn enable`.** |
| Residual risk | **Proposed Medium; human acceptance pending** |
| Review trigger | Before enable and on any scope, recipient, telemetry, destination, legal-basis, rights, or retention change |

This repository records the proposed boundary; it does not provide legal
advice or represent operator acceptance. A workflow result, protected
environment approval, source SHA, or artifact cannot substitute for an exact
human PIPIA decision.

## Exact assessed scope

The first release is:

- invite-only and web-only;
- no public signup;
- no Miniapp publication;
- no geographic redirect;
- no new browser/product telemetry;
- no proxy, SSR, EdgeOne function, mainland API, or mainland datastore;
- no change to `praxys.run` or `www.praxys.run`.

EdgeOne serves only static HTML, JavaScript, CSS, ICP markup, `healthz`, and
`deployed_sha.txt`. It receives no Praxys credentials, authenticated training
dataset, telemetry credential, or API request through Praxys configuration.
The browser calls the DNS-only `https://api.praxys.run` directly.

Account, authentication, provider credentials, sync, training/recovery data,
plans, PostgreSQL storage, essential backend monitoring, and Azure AI remain in Azure East Asia (Hong Kong SAR), except Azure AI model
processing, which is in **West US 3**. No mainland copy is introduced.

## Proposed processing basis

The draft proposes that core account, sync, storage, deterministic analysis,
plan, export, deletion, security, and reliability processing is necessary to
perform the training service requested by the invited individual. It proposes
reliance on PIPL Article 13(1)(2) and the applicable contract-necessity
cross-border provision rather than consent for that indivisible core service.

The human reviewer must independently accept or reject that interpretation,
especially for sensitive fitness, recovery, route, and credential data. The
service must give complete pre-processing notice and explain sensitive
categories, necessity, impact, overseas processing, recipients, retention,
and rights before personal processing.

Official sources:

- <https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm>
- <https://www.cac.gov.cn/2024-03/22/c_1712776611775634.htm>
- <https://www.cac.gov.cn/2024-03/22/c_1712776611649184.htm>

## Recipient and destination map

| Processor / recipient | Location | Assessed purpose and data |
|---|---|---|
| Tencent Cloud EdgeOne | Mainland China | Static public site delivery and ordinary provider delivery logs; no authenticated Praxys dataset, secrets, telemetry SDK, SSR, function, or API proxy |
| Microsoft Azure and subprocessors | East Asia, Hong Kong SAR | Account/authentication records, encrypted provider credentials, training/recovery data, goals/plans/settings, database/API execution, and minimized backend security/reliability telemetry |
| Microsoft Azure AI | West US 3 | Only minimized fields for current-Terms AI purposes and any purpose-bound optional private context; independently stopped by the Azure AI emergency switch |
| User-selected Garmin, Strava, Stryd, Oura, or COROS service | Provider-selected region | Only the connection and supported data transfer initiated by the user after just-in-time recipient notice |
| Configured mail service | Configured region | Invitation, verification, or requested service email |

WeChat/Miniapp is not part of this release. GitHub public issue publication,
browser App Insights, browser Statsig, and product-event telemetry are not
enabled for `.cn`.

## Data categories and necessity

| Category | Necessity / impact | Safeguards |
|---|---|---|
| Email and authentication records | Required for invited account access; compromise could enable account access | Password hashing, rate limiting, per-user authorization |
| Provider credentials | Required only for a connection the user activates; compromise could expose provider data | Envelope encryption, Key Vault wrapping, generation fencing, disconnect/delete |
| Activity, pace, power, route, heart rate, HRV, sleep, recovery | Required only by selected training/recovery functions; can reveal health, routine, or location | Sensitive-data treatment, encryption, account scope, no advertising or cross-user training |
| Goals, plans, settings, language | Required to configure requested service | Editable, exportable, account-scoped, deleted with account |
| Optional private plan context | Optional input to reduce guessing | Purpose/version/field minimization, expiry/deletion controls, current Terms |
| Support text/screenshots | Only when the user asks for support | Private storage; no automatic public China publication |
| Minimized request/security telemetry | Needed for abuse, outage, and deletion/reliability investigation | No intentional payload/credential/email; Hong Kong backend retention remains 30 days |

Active account data remains for the account lifetime. Account deletion removes
active rows and credentials. PostgreSQL PITR may retain encrypted deleted data
for up to 14 days. Any longer receipt/legal retention requires a separately
accepted schedule.

## Required safeguards before enable

- The exact human PIPIA decision and residual-risk acceptance are recorded
  outside the repository and referenced by the change record.
- `.cn` blocks personal processing until the current notice is acknowledged;
  current Terms acceptance remains digest-bound and append-only.
- Stale or missing client policy claims fail before ordinary personal routes;
  export, deletion, disconnect, and other bounded rights routes remain
  available.
- Provider connection dialogs identify the recipient, categories, purpose, and
  official privacy link before transfer.
- Browser App Insights, Statsig, and product events remain absent.
- `PRAXYS_DISABLE_BACKGROUND_AI=false` is explicitly verified for ordinary
  service; China workflows never change it.
- Backend telemetry stays minimized with 30-day component/workspace retention.
- CORS is exact base before launch or exact base plus the two `.cn` origins
  after launch. Disable preserves the latter for rights-route preflight; CORS
  is not processing authority.
- Both `.cn` hosts pass DNS, TLS, `healthz`, security headers, and serve a full
  SHA reachable from protected `main`.
- Outside-in availability tests and alerts exist and are enabled for launch.
- Invitations and shared Azure capacity remain bounded for the private alpha.

## Risk summary

| Risk | Proposed residual |
|---|---|
| Contract-necessity interpretation for sensitive training data | Medium; human decision required |
| Overseas legal access or processor compromise | Medium |
| Credential or route-data exposure | Medium-low after safeguards |
| Personal processing before current notice | Low after runtime and client gates |
| New recipient/telemetry scope creep | Low only while exact web-only boundary is enforced |
| Incomplete deletion because of encrypted backups/processors | Medium-low |
| Shared Azure capacity affects `.run` | Low for bounded alpha; monitor and pause invitations |

## Human acceptance checklist

The reviewer must record an explicit answer for each item:

1. Is the exact web-only scope above accurate?
2. Is the proposed legal basis accepted for each necessary category?
3. Are overseas destinations, Azure AI, and all recipients complete?
4. Are sensitive-data necessity, impact, and safeguards accepted?
5. Are notice, rights, retention, incident, and processor-contact arrangements
   sufficient?
6. Is proposed Medium residual risk accepted?
7. Are the exact protected-main artifact, EdgeOne domains/TLS, CORS, runtime
   settings, availability tests, and alerts verified?

Absent any answer, do not enable.

## Rollback / incident

Use `launch-cn.yml` `disable`, verify China disabled and one of the two exact
valid CORS sets, and preserve `.run` and the DNS-only API. Static EdgeOne takedown is manual. A
suspected personal-data or security incident is owned by Trust and follows the
incident runbook; mitigation/recovery claims require readback and public-host
verification.

## Related

- [cn-web-private-alpha.md](./cn-web-private-alpha.md)
- [tencent-frontend.md](./tencent-frontend.md)
- [incident-response.md](./incident-response.md)
- `api/china_client_boundary.py`
- `web/src/components/ChinaProcessingNoticeGate.tsx`

---
_Last reviewed: 2026-08-29 · Owner: human operator / Trust_
