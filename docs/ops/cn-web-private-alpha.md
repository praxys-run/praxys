# China public web launch

> **Summary:** Operations decision and launch checklist for the dormant public
> `praxys.cn` web surface and its shared Praxys backend.
> **Use when:** Checking, enabling, disabling, or recovering the China web
> launch.

**Status:** The operator accepted PIPIA `1.2-public-parity` and its overall
**Medium** residual risk on 2026-08-31. Production enablement remains human-only
and blocked until the implementation and live controls below are verified.

## Boundary

- `praxys.cn` and `www.praxys.cn` are a static EdgeOne Makers SPA built from
  protected `main`. The API, identity, datastore, sync, and Azure AI remain at
  `api.praxys.run` in the documented Azure regions.
- Public self-registration matches `.run`: both surfaces use the same global
  registration switch and seat cap. Invitations remain supported but are not
  required while registration is open.
- `.run` remains available and unchanged by `launch-cn.yml`. There is no API
  proxy, SSR, EdgeOne function, mainland API, or mainland datastore.
- The existing Miniapp continues to use `https://api.praxys.run`. Its robot 5
  protected-main development upload stays automatic; trial selection, review,
  and production publication remain manual in WeChat. `launch-cn.yml` neither
  uploads nor publishes it. New-account registration and platform setup remain
  on the open Web flow, then users bind that account in WeChat.
- Browser Application Insights and allowlisted product events follow the
  recorded minimized boundary. Browser Statsig remains absent from the `.cn`
  artifact pending [#754](https://github.com/praxys-run/praxys/issues/754).
- Geographic HTTP `302` is a post-stability provider operation. It preserves
  the path, drops query/fragment values, applies only to public pages, and never replaces DNS or redirects
  authenticated application routes.
- The static filing footer is `沪ICP备2025109616号-2`.

`PRAXYS_DISABLE_CN_PROCESSING` is the web processing authority. CORS is only
browser transport authority: it is not a privacy switch. The only valid CORS
sets are the base three origins, used before the first launch, and the same set
plus the two exact HTTPS `.cn` origins. After the first launch, disable and
compensation leave the `.cn` origins so authenticated export, deletion,
disconnect, sign-out, and other bounded rights routes can still preflight.

When web processing is disabled, the static `.cn` site, public
legal/status/support surfaces, and rights routes remain reachable. Ordinary
personal-data routes and China background work fail closed. Rights include
Labs experiment withdrawal as well as export, deletion, disconnect, and
sign-out.

Azure AI is independent. `launch-cn.yml` observes but never changes
`PRAXYS_DISABLE_BACKGROUND_AI`.

## Application controls

- Exact `.cn` origins are server-classified as `cn-web`; a browser header alone
  cannot claim the channel.
- A current `.run` Terms projection does not classify an existing user as a
  China user. `/api/auth/me` reports `terms_current=false` on `.cn` until the
  user explicitly acknowledges the current version/digest there. That action
  writes an append-only `cn-web` Terms receipt; no receipt is fabricated.
- The current notice version, legal digest, and API contract form the client
  compatibility tuple. Legacy source/version/release request headers are not
  authority.
- Rights requests receive validated server China context before their kill
  switch/Terms bypass, so they remain available and any explicit acceptance is
  recorded on the correct channel.
- Background sync, AI, adjustment, and managed-delivery mutations check current
  Terms/China receipt state and the live kill switch. Provider/calendar/plan
  mutations recheck immediately before mutation.
- Missing, blank, or malformed China or Miniapp switch configuration fails
  closed and readiness reports the effective disabled state.

## Human gates

Before `enable`, a human must:

1. Confirm that the accepted exact
   [`PIPIA-CN-2026-08-25-01`](./cn-personal-information-impact-assessment.md)
   remains applicable and that its listed live verification obligations are
   complete.
2. Approve the `china-production` environment for the exact run.
3. Ensure Azure trusts the exact environment OIDC subject.
4. Verify the one-time EdgeOne Git project/domain/DNS/TLS setup and outside-in
   monitoring.

No workflow result, SHA, summary, or artifact substitutes for the recorded
operator decision or for live verification of its controls.

## Workflow

Dispatch `.github/workflows/launch-cn.yml` from `main`:

```bash
gh workflow run launch-cn.yml --ref main -f action=status
gh workflow run launch-cn.yml --ref main -f action=enable
gh workflow run launch-cn.yml --ref main -f action=disable
```

- **status** has no environment and performs no mutation. Its run summary
  reports filtered settings, exact CORS, valid API readiness/version, `.run`,
  and both `.cn` hosts. Missing pre-DNS `.cn` hosts are warnings rather than
  empty healthy objects while processing is disabled. Once processing is
  enabled, unavailable `.cn` hosts or non-five-origin CORS fail the job.
  Invalid CORS or unhealthy core API/`.run` also fails. Status does not inspect
  GitHub environment protection, web tests, monitoring, or alerts.
- **enable** alone uses `china-production`. It requires the dispatch SHA to be
  current `main`; each API, `.run`, and EdgeOne component SHA may differ but
  must be a full SHA reachable from `origin/main`. It also requires healthy
  API/`.run`, an open effective global registration gate, enabled Azure AI,
  enabled Miniapp processing, production
  `service_bus` with a same-SHA verified Worker, valid CORS, and both `.cn` hosts serving
  `praxys-frontend-cn` with a compatible legal/API tuple, deployment-region
  marker, ICP footer, and security headers. From disabled it adds the two
  origins idempotently and enables the China switch. When already enabled it
  requires exact five-origin CORS and verifies without mutation. Both paths
  verify the final API, `.run`, and EdgeOne artifact SHAs, CORS preflight, and
  actual-response CORS on unauthenticated `401` and stale-client `428`.
- **disable** is an emergency main-branch action without an environment or
  frontend/API SHA dependency. It sets only
  `PRAXYS_DISABLE_CN_PROCESSING=true`, then verifies that setting, Azure AI,
  byte-for-byte CORS preservation and live readiness. Once the five-origin
  CORS set exists, it also verifies rights-route CORS; before the first launch,
  base-only CORS is valid and the summary records that rights CORS is not yet
  configured. It cancels an in-progress enable rather than waiting behind it.

Enable compensation sets China processing disabled only when that run started
disabled, and leaves either valid CORS set intact. A repeated or rejected
enable never disables an already healthy launch. GitHub logs and the run
summary are the workflow evidence; no custom evidence JSON or artifact is
produced.

## Backend deployment

Ordinary backend deployment has its own queue so emergency disable cannot be
replaced by a pending deploy. It does not write the China switch, CORS, or the
Azure AI emergency switch and does not probe EdgeOne. It captures those three
runtime values read-only and requires exact equality after deployment.
Readiness accepts either preserved China state, requires the exact deployed API
version/SHA, requires live China/AI booleans to match the preserved switch
values, preserves the current Miniapp processing state, and reports the final
China, Miniapp, and Azure AI state in the run summary.

## Rollback / recovery

1. Dispatch `disable`.
2. Verify the China switch is `true`, CORS is still one of the two exact valid
   sets, and Azure AI is unchanged.
3. If static content itself must disappear, manually unbind/disable both
   EdgeOne domains or change DNS. Repository workflows hold no EdgeOne
   credential.
4. Do not stop the shared API or `.run` for a China-only incident.

## Post-launch filing

Record the exact first-public-access time in the release evidence. Complete
the separate [public-security website filing](./cn-public-security-filing.md)
within 30 days of formal connectivity. Do not add a public-security number,
query URL, or icon until the platform issues the exact artifacts.

## Related

- [tencent-frontend.md](./tencent-frontend.md)
- [deploy.md](./deploy.md)
- [config-and-secrets.md](./config-and-secrets.md)
- [cn-personal-information-impact-assessment.md](./cn-personal-information-impact-assessment.md)
- [cn-public-security-filing.md](./cn-public-security-filing.md)

---
_Last reviewed: 2026-08-31 · Owner: Operations_
