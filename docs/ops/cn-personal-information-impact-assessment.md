# Mainland China personal-information protection impact assessment

> **Status:** **VERSION 1.3 ACCEPTED BY THE HUMAN OPERATOR ON 2026-09-04 — LIVE RELEASE VERIFICATION STILL REQUIRED BEFORE ENABLE**
> **Summary:** Assessment record for the public Praxys China web and WeChat
> surfaces, including overseas Azure processing, telemetry, recipients,
> sensitive information, rights, and accepted residual risks.
> **Use when:** Releasing or materially changing a China surface, recipient,
> data category, destination, telemetry path, legal basis, retention period,
> or rights control.

## Assessment record

| Field | Value |
|---|---|
| Record ID | `PIPIA-CN-2026-08-25-01` |
| Version | `1.3-feedback-publication` |
| Assessment date | 2026-09-04 |
| Acceptance date | 2026-09-04 |
| Operator / personal-information handler | Fei Tao |
| Rights contact | `support@praxys.run` |
| Service | Public registration on the Praxys web service at `praxys.cn` and `www.praxys.cn`; existing WeChat Miniapp |
| Decision | **The human operator accepted this exact `1.3-feedback-publication` assessment on 2026-09-04. Live control verification and production enablement remain separate human gates.** |
| Residual risk | **Medium; accepted by the human operator on 2026-09-04**; optional public feedback publication is Low–Medium after the controls below, while the overall China processing assessment remains Medium |
| Deferred, non-blocking risks | Browser Statsig remains disabled on `.cn` pending [#754](https://github.com/praxys-run/praxys/issues/754); restore-safe account deletion is tracked in [#755](https://github.com/praxys-run/praxys/issues/755) |
| Review trigger | Before any material change listed under [Immediate review or stop triggers](#immediate-review-or-stop-triggers) |
| Minimum record retention | Through 2029-09-04, and longer while the assessed processing continues or a dispute/investigation requires it |

This is the repository record of the operator's stated product and telemetry
decisions and acceptance of this exact assessment and its overall **Medium**
residual risk. It is not external legal advice. It does not assert
that EdgeOne, DNS, TLS, CORS, OIDC, runtime settings, monitoring, alerts, or a
particular deployed artifact have passed their separate live checks.

## Recorded scope

The first public release follows the existing `praxys.run` service unless a
narrow exception is stated here:

- public self-registration uses the same global registration switch and seat
  cap as `.run`; `.cn` is not invite-only;
- `praxys.cn` and `www.praxys.cn` serve a static EdgeOne SPA, while identity,
  API, datastore, sync, analysis, Azure AI, and telemetry processing continue
  through the existing Azure service at `https://api.praxys.run`;
- no `api.praxys.cn`, mainland API/datastore, API proxy, SSR, or EdgeOne
  function is introduced;
- the existing WeChat Miniapp remains supported against
  `https://api.praxys.run`; protected-main CI continues robot 5 development
  uploads, while trial selection, review submission, and production
  publication remain manual in WeChat; new-account registration and platform
  setup remain on the open web flow at `.run` or `.cn`, after which the user
  binds the account in WeChat;
- the `.cn` web artifact may send minimized browser Application Insights
  performance/request telemetry and the web and Miniapp may send the same
  allowlisted product events as `.run`; browser Statsig is the narrow exception
  and remains absent from `.cn` until #754 is completed and this assessment is
  updated;
- backend security, request, error, latency, queue, availability, and product
  telemetry remain enabled and minimized; and
- after both `.cn` hosts are stable, a separately verified geolocation rule may
  issue temporary HTTP `302` redirects from mainland visits to public `.run`
  pages, preserving the path and dropping the query/fragment. It must not be a DNS-only claim, a
  permanent redirect, or a redirect of authenticated application routes.

The China launch does not remove or degrade `.run`. Invitations may continue
to work, but are not a condition of `.cn` registration.

## Processing basis

The accepted assessment records that core account, authentication, sync, storage,
deterministic analysis, plans, export, deletion, security, reliability, and the
enumerated ordinary Azure AI purposes are necessary to enter into and perform
the training service requested by the individual. The selected basis is PIPL
Article 13(1)(2) together with the applicable contract-necessity cross-border
provision, rather than consent for an indivisible core service.

The service must still provide complete notice before personal processing and
prominently explain sensitive categories, necessity, impact, overseas
processing, recipients, retention, and rights. Supplying private plan context
and connecting any third-party provider remain optional user choices. Current
Terms acceptance and server runtime state govern ordinary Azure AI; during an
AI outage or emergency stop, AI-only features report unavailable while
separately labelled deterministic functions continue.

Official sources:

- [Personal Information Protection Law](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)
- [2024 cross-border data-flow provisions](https://www.cac.gov.cn/2024-03/22/c_1712776611775634.htm)
- [CAC questions and answers on the 2024 provisions](https://www.cac.gov.cn/2024-03/22/c_1712776611649184.htm)

## Processor and recipient map

| Processor / recipient | Location | Information and purpose | Proposed boundary |
|---|---|---|---|
| Tencent Cloud EdgeOne | Mainland China | Public static HTML, JavaScript, CSS, filing markup, and ordinary provider delivery logs | No authenticated training dataset, Praxys credential, SSR, function, or API proxy |
| Microsoft Azure and subprocessors | East Asia, Hong Kong SAR | Account/authentication records, encrypted provider credentials, training/recovery data, goals/plans/settings, database/API execution, support content, and minimized backend/browser/product telemetry | Core overseas processing; component-scoped controls and 30-day Application Insights/workspace retention |
| Microsoft Azure AI | West US 3, United States | Minimized fields for the ordinary AI purposes enumerated in the current Terms and purpose-bound optional private context | Current Terms, per-account/purpose/field isolation, and independent emergency stop |
| Tencent WeChat | Mainland China | Login codes, WeChat identifier, Miniapp delivery/runtime metadata | Only for Miniapp authentication and operation; authenticated product data continues directly to `api.praxys.run` |
| Configured mail service | Configured region | Destination address and requested verification or service-email content | Only for the requested email function |
| Garmin, Strava, Stryd, Oura, or COROS selected by the user | Provider-selected region | Authentication material and supported user-initiated data transfer | Optional connection after just-in-time recipient/category notice |
| Statsig service operated by Amplitude | Rules are downloaded from the service; backend evaluation occurs inside Praxys | Backend SDK downloads gate/config rules without user identity | User-event logging and SDK diagnostics stay disabled; browser Statsig remains absent from `.cn` pending #754 |
| GitHub, Inc. issue service and published service providers | Outside mainland China | A twice-scrubbed, independently privacy-reviewed text summary only after exact `feedback-publication-v2-public-github` permission for that submission, current account/Terms authority, safety review, and effective global switches | Destination is only public `praxys-run/praxys`; anyone may view and copy it; public issues may be retained long term; screenshots and image-derived descriptions, raw feedback, diagnostics, identity, and credentials remain private |

Provider legal entity and processing location may depend on the user's account
region. The connection dialog must identify the provider and current official
privacy/contact notice immediately before transfer.

## Data categories, necessity, and retention

| Category | Necessity / impact | Safeguards and retention |
|---|---|---|
| Email, WeChat identifier, and authentication records | Required for the selected account/login method; compromise could enable access | Password hashing, rate limiting, per-user authorization, account-lifetime active storage |
| Provider credentials | Required only for a connection the user activates | Envelope encryption, Key Vault wrapping, generation fencing, disconnect and account deletion |
| Activity, pace, power, route, heart rate, HRV, sleep, and recovery | Required only by selected training/recovery functions; may reveal health, routine, or location | Sensitive-data treatment, encryption, account scope, no advertising or cross-user training |
| Goals, plans, settings, and language | Required to configure requested service | Editable, exportable, account-scoped, deleted with the active account |
| Optional private plan context | Optional input to reduce guessing | Purpose/version/field minimization, expiry/deletion controls, current Terms |
| Support text and screenshots | Only when the user requests support | Private storage by default; exact v2 per-submission grant plus a separate fail-closed final privacy review for a scrubbed text summary; screenshots and image-derived descriptions never publish; public GitHub issues may be retained long term and are outside the private account-deletion path |
| Backend security/reliability and product telemetry | Detect abuse/failures and measure service behavior | Allowlisted fields, pseudonymous account hash where needed, no intentional raw training payload, credential, token, or email; 30-day Azure component/workspace retention |
| Browser Application Insights | Diagnose `.cn` page, dependency, and performance behavior | Page/dependency/performance scope; query/fragment stripping and no automatic exception capture on the regional artifact; no raw training content, feedback text, email, or raw account ID |
| Product events | Measure a bounded set of app/Today interactions | Allowlisted event names, surface, version, and bounded enums; backend derives a pseudonymous account hash and rejects extra fields |

Primary account and training rows remain while the account is active. Account
deletion immediately removes the active account, owned rows, credentials, and
covered private files. Azure PostgreSQL point-in-time recovery retains encrypted
snapshots for up to 14 days. A restore to a pre-deletion point can recreate the
deleted rows unless reconciliation runs before traffic resumes. The operator
accepts this **Medium-low residual risk for this launch**;
[#755](https://github.com/praxys-run/praxys/issues/755) owns the restore-safe
deletion fix and is explicitly non-blocking for the initial `.cn` launch.
Until it is complete, any restore must remain closed to traffic while the
operator reconciles deletions.

## Sensitive-personal-information assessment

Heart rate, HRV, sleep, recovery, precise routes, health/fitness inferences,
and provider authentication material are treated conservatively as sensitive
personal information.

- **Specific purpose:** provide the signal, analysis, forecast, plan,
  connection, or security function requested by the individual.
- **Necessity:** a category is not required for a feature that does not use it;
  users choose which providers to connect and whether to add private context.
- **Impact:** unauthorized disclosure could reveal health, routine, location,
  account access, or behavior and could cause material harm.
- **Controls:** encrypted transport/storage, per-user authorization, credential
  envelope encryption, purpose/field minimization, bounded telemetry, private
  screenshot storage, transfer/deletion fencing, export, disconnect, account
  deletion, and runtime emergency stops.

## Notice and receipt controls

- The `.cn` web boundary blocks ordinary personal requests until the current
  notice is acknowledged.
- Current Terms acceptance is append-only, version-and-digest bound, and
  channel-aware; an existing `.run` acceptance does not fabricate a `.cn`
  receipt.
- The Miniapp starts with the same current legal bundle and carries its
  server-classified channel plus the current compatibility tuple. Releases
  older than `2026.08.2` are rejected with
  `CLIENT_PRIVACY_UPDATE_REQUIRED`.
- Public legal/status/support routes and bounded rights routes remain available
  when ordinary processing is disabled or Terms are stale.
- Provider dialogs identify recipient, categories, purpose, and official
  privacy link before credentials or OAuth authorization leave Praxys.

## Accepted residual risks

| Risk | Accepted residual / disposition |
|---|---|
| Contract-necessity interpretation for sensitive training data | **Medium; accepted for this launch** |
| Overseas legal access or processor compromise | Medium |
| Credential or precise-route exposure | Medium-low after safeguards |
| Personal processing before current notice | Low after runtime/client gates |
| App Insights or product telemetry contains unexpected personal content | Low-medium; regional minimization and field allowlists require verification |
| Browser Statsig transmits raw identity or unnecessary attributes | Deferred; absent from `.cn`, tracked by #754, not a launch blocker |
| Account deletion is reversed by a PITR restore | **Medium-low; accepted for launch**, closed-traffic reconciliation, tracked by #755 |
| Shared Azure capacity affects `.run` or `.cn` | Low; monitor and disable affected China processing if needed |
| Geographic redirect loops, loses context, or disrupts sessions | Low while temporary, public-page-only, path-preserving, query-dropping, and verified |
| Authorized scrubbed feedback becomes broadly visible or persists beyond the user's expectation | **Low–Medium** after exact per-submission notice, twice-scrubbing, independent final-payload privacy review, screenshot-derived-text exclusion, App-authenticated reconciliation, one-candidate fencing, durable reconciliation, and public/overseas/long-retention copy |
| A timeout or crash creates a duplicate public issue | Low after the metadata-only outbox, committed random lease, exact marker/digest reconciliation, and the prohibition on retrying unknown outcomes |

## Mandatory controls and release evidence

Before `launch-cn enable`, Release Evidence must show the following. These are
verification obligations, not new product approvals:

- exact protected-main API, `.run`, and EdgeOne artifact provenance;
- current web/API legal version, digest, and China API contract;
- `.cn` pre-transfer notice blocking, current Terms receipts, rights-route
  availability, and provider just-in-time disclosure;
- public registration matching the effective global switch and seat cap;
- Miniapp processing enabled with complete WeChat credentials and a compatible
  `2026.08.2+` production release, or a narrowly documented launch ordering in
  which web enable does not falsely claim the Miniapp is already published;
  robot 5 development upload is not production evidence;
- `PRAXYS_DISABLE_BACKGROUND_AI=false` for ordinary service and the
  independent emergency-stop behavior tested;
- feedback publication remains ineffective until Release Evidence separately
  proves `PRAXYS_ENABLE_FEEDBACK_PUBLICATION=true`, the protected emergency
  control reads `PRAXYS_DISABLE_FEEDBACK_PUBLICATION=false`, the exact target
  is `praxys-run/praxys`, the GitHub App grant is limited to Issues read/write
  plus Pull requests read, current Terms and the exact
  `feedback-publication-v2-public-github` submission receipt are enforced, and
  the outbox/reconciler synthetic canary completes without a duplicate;
- ordinary deployment never writes the emergency-stop value, quiesces the
  positive switch until the exact new source SHA is verified, and cannot clear
  a concurrent stop; absent, malformed, or mismatched settings fail closed;
- no legacy v1 row is migrated, replayed, or made a candidate;
- browser Statsig absent from `.cn` and backend Statsig user logging and
  diagnostics disabled;
- regional App Insights URL minimization/exception suppression, allowlisted
  product events, exact telemetry component scope, and 30-day retention;
- exact `.cn` CORS origins, EdgeOne HTTPS, filing footer, security headers,
  health metadata, and both outside-in availability alerts;
- Labs API and worker authorization compatible with the selected execution
  mode and emergency-disable semantics; and
- tested export, disconnect, active account deletion, rollback, and the
  closed-traffic PITR deletion-reconciliation procedure linked to #755.

Geographic redirect is a post-stability operation. Enable it only after both
`.cn` hosts and the no-loop rollback path are verified.

## Immediate review or stop triggers

Stop the affected new processing and update this assessment before resuming if:

- a recipient, subprocessor, country/region, purpose, or personal-data category
  materially changes;
- the Azure AI region/purpose changes, current-Terms enforcement is bypassed,
  or its emergency stop fails;
- `.cn` browser Statsig is proposed for enablement, or backend Statsig begins
  transmitting identities, exposure events, or diagnostics;
- regional App Insights begins collecting exception payloads, unsanitized URL
  parameters, email, raw account IDs, training content, or feedback text;
- product events accept fields beyond the reviewed allowlist;
- feedback publication is enabled without exact per-submission authority;
- a screenshot, raw feedback/context, identity, redaction marker, ambiguous
  delivery, or non-allowlisted issue URL crosses the public boundary;
- a provider privacy notice, legal entity, or access method materially changes;
- a security incident, unauthorized disclosure, failed deletion, or regulator
  inquiry occurs;
- processing scale, legal guidance, or service design materially changes the
  selected contract-necessity analysis; or
- a child-directed service, medical purpose, advertising, data sale, or
  cross-user model training is introduced.

## Recorded operator decisions

On 2026-08-31, the operator stated and approved these bounded choices:

1. Open `.cn` registration and otherwise preserve `.run` behavior unless an
   identified risk requires a narrow difference.
2. Keep the existing Miniapp publication process: CI creates robot 5
   development builds, while production review/publication remain manual;
   continue using `api.praxys.run`.
3. Preserve ordinary Labs `service_bus` capability, with shared live
   processing authority enforced by the API and worker implementation.
4. Track restore-safe account deletion separately in #755 and accept the
   documented residual risk for this launch.
5. Keep browser Statsig out of `.cn` and track its minimization separately in
   #754; continue the other minimized system/product telemetry described here.
6. Proceed with temporary geographic redirect after `.cn` stability and
   provider-side verification.
7. Accept this exact `1.2-public-parity` assessment and its overall **Medium**
   residual risk for this launch.

On 2026-09-04, the operator separately accepted version
`1.3-feedback-publication`: restore the existing optional public-feedback path
for new v2 submissions on both domains only after repository implementation,
independent verification, later Release Evidence, and live readback. This does
not authorize legacy replay, deployment, a production canary, or clearing the
emergency stop in an ordinary deploy.

These decisions do not constitute live provider readback, a successful
deployment, or public-security filing completion.

## Rollback / incident

Use `launch-cn.yml` `disable`, verify China processing disabled and valid
CORS, and preserve `.run` plus the DNS-only API. Static EdgeOne takedown is
manual. Disable a faulty geolocation rule separately and verify both public
domains no longer loop. Personal-data/security incidents follow the incident
runbook and require readback before recovery is claimed.

For feedback publication, set and read back
`PRAXYS_DISABLE_FEEDBACK_PUBLICATION=true`, confirm effective publication is
false, stop new claims, and retain every outbox/attempt row for reconciliation.
Do not delete evidence, make unknown attempts pending, or replay any legacy
feedback as part of rollback.

## Related

- [cn-web-private-alpha.md](./cn-web-private-alpha.md)
- [tencent-frontend.md](./tencent-frontend.md)
- [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- [cn-public-security-filing.md](./cn-public-security-filing.md)
- [incident-response.md](./incident-response.md)
- `api/china_client_boundary.py`
- `web/src/components/ChinaProcessingNoticeGate.tsx`

---
_Version 1.3 feedback-publication scope accepted: 2026-09-04 · Owner: human operator / Trust · China core release verification completed: 2026-09-01 · feedback-publication live verification: pending_
