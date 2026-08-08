# Baseline: 2026-08-08 — China frontend delivery topology

**Purpose:** compare three ways of serving the same Praxys frontend to a
mainland-China user:

1. Azure App Service East Asia directly.
2. EdgeOne Global (excluding mainland China), with Azure as origin.
3. Tencent Lighthouse in mainland China, while the authenticated API remains
   on Azure East Asia.

**Frontend build:** `4fa29422775bd0065bfe3e8e4c900201b8f785ed` on both Azure
and Tencent.

**Probe:** operator PC in Shanghai on China Unicom, with the company private
network disabled and `praxys.run` routed directly rather than through the
router's Singapore proxy.

**Method:** sitespeed.io 39.5.0 in Docker, Chrome 146, three iterations per
scenario/device cell. Tables contain the analyzer's representative median
values. Desktop and 390 × 844 mobile emulation were both measured.

## Delivery paths

| Label | Frontend path | API path |
|---|---|---|
| Direct Azure | Shanghai → Azure East Asia App Service | Shanghai → Azure East Asia |
| EdgeOne | Shanghai → EdgeOne Singapore → Azure East Asia | Shanghai → Azure East Asia |
| Tencent | Shanghai → Tencent mainland Lighthouse | Shanghai → Azure East Asia |

EdgeOne resolved to Singapore anycast addresses during the test. Hashed assets
were cache hits, while HTML used origin revalidation. The API hostname was not
behind EdgeOne.

## Same-build comparison

### S1 — Cold first load, Today page via login

| Frontend | Device | FCP | LCP | HTML TTFB | Static KB | API p50 | API p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| Direct Azure | Desktop | 2008 ms | 2008 ms | 397 ms | 677.9 | 167 ms | 1148 ms |
| Direct Azure | Mobile | 1972 ms | 1972 ms | 400 ms | 677.8 | 243 ms | 2187 ms |
| EdgeOne | Desktop | 2556 ms | 2556 ms | 961 ms | 679.4 | 328 ms | 1661 ms |
| EdgeOne | Mobile | 2620 ms | 2620 ms | 962 ms | 679.2 | 254 ms | 1018 ms |
| Tencent + gzip | Desktop | 664 ms | **664 ms** | 26 ms | 741.1 | 2134 ms | 3917 ms |
| Tencent + gzip | Mobile | 1548 ms | **1548 ms** | 27 ms | 741.1 | 1661 ms | 5012 ms |

Tencent reduced LCP versus direct Azure by 67% on desktop and 22% on mobile.
The API tail varied substantially during the Tencent run, but the page still
painted sooner because the static shell arrived locally.

### S2 — Today to Training navigation

| Frontend | Device | FCP | LCP | HTML TTFB | Static KB | API p50 | API p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| Direct Azure | Desktop | 588 ms | 1300 ms | 6 ms | 165.7 | 155 ms | 585 ms |
| Direct Azure | Mobile | 436 ms | 804 ms | 7 ms | 165.7 | 162 ms | 790 ms |
| EdgeOne | Desktop | 544 ms | 3008 ms | 10 ms | 166.0 | 172 ms | 1014 ms |
| EdgeOne | Mobile | 436 ms | 836 ms | 7 ms | 166.0 | 149 ms | 471 ms |
| Tencent + gzip | Desktop | 464 ms | **1204 ms** | 18 ms | 166.8 | 385 ms | 817 ms |
| Tencent + gzip | Mobile | 280 ms | **724 ms** | 19 ms | 166.8 | 407 ms | 595 ms |

S2 begins after login and shell loading, so its document timing mostly measures
an in-app transition. Tencent was 7% faster than direct Azure on desktop and
10% faster on mobile in the compressed follow-up run. The smaller gap confirms
that moving only the frontend cannot eliminate an API-bound wait.

### S3 — Warm repeat Today

| Frontend | Device | LCP | HTML TTFB | Static KB | API p50 | API p95 |
|---|---|---:|---:|---:|---:|---:|
| Direct Azure | Desktop | 688 ms | 9 ms | 0.4 | 167 ms | 920 ms |
| Direct Azure | Mobile | 636 ms | 7 ms | 0.4 | 159 ms | 643 ms |
| EdgeOne | Desktop | **672 ms** | 8 ms | 0.4 | 141 ms | 412 ms |
| EdgeOne | Mobile | **620 ms** | 7 ms | 0.4 | 151 ms | 418 ms |

The warm result supports the operator's manual perception that EdgeOne can feel
faster during normal repeat use. Cached static assets avoid the slow
Singapore-to-Azure origin leg, although the measured LCP advantage was only
16 ms on both devices and is within normal run-to-run noise.

No Tencent S3 result is reported. Direct HTTP by IP is not a secure context, so
service-worker/PWA behavior would not be comparable with the production HTTPS
paths.

### S4 — Anonymous landing page

| Frontend | Device | FCP | LCP | HTML TTFB | Static KB |
|---|---|---:|---:|---:|---:|
| Direct Azure | Desktop | 1804 ms | 1924 ms | 413 ms | 1753.0 |
| Direct Azure | Mobile | 1652 ms | 1772 ms | 435 ms | 1753.1 |
| EdgeOne | Desktop | 2820 ms | 3020 ms | 1605 ms | 631.0 |
| EdgeOne | Mobile | 6588 ms | 6884 ms | 5285 ms | 631.0 |
| Tencent + gzip | Desktop | 1340 ms | **1340 ms** | 32 ms | 626.0 |
| Tencent + gzip | Mobile | 540 ms | **704 ms** | 26 ms | 626.0 |

Tencent reduced landing LCP versus direct Azure by 30% on desktop and 60% on
mobile.
EdgeOne transferred fewer bytes than direct Azure but lost more time waiting
for HTML revalidation through Singapore. Its mobile result also had a severe
tail, reinforcing that three runs establish direction rather than a stable SLA.

## Tencent compression experiment

The first Tencent run exposed an Nginx configuration defect: `gzip on` was
present globally, but the useful MIME types remained commented out. JavaScript
and CSS therefore crossed the Lighthouse bandwidth cap uncompressed.

| Scenario | Device | Without gzip LCP | With gzip LCP | Change |
|---|---|---:|---:|---:|
| Cold Today | Desktop | 4308 ms | 664 ms | **-85%** |
| Cold Today | Mobile | 3668 ms | 1548 ms | **-58%** |
| Landing | Desktop | 4620 ms | 1340 ms | **-71%** |
| Landing | Mobile | 4464 ms | 704 ms | **-84%** |

The main JavaScript response fell from 402,243 bytes to 136,855 bytes on the
wire. Its direct transfer time fell from approximately 460 ms to 73 ms. This
baseline therefore updates the committed Tencent Nginx configuration to
compress JavaScript, CSS, JSON, XML, SVG, and text responses.

## Interpretation

- **Cold path:** the mainland static origin was fastest in every median cell
  after compression, despite the API remaining in Azure.
- **Warm path:** EdgeOne was equal or faster in this sample because browser and
  edge caches removed most origin work.
- **EdgeOne Global excluding mainland:** this probe reached Singapore, so cold
  HTML paid a China → Singapore → Azure East Asia detour.
- **Do not generalize to every mainland ISP:** this is one Shanghai China
  Unicom probe and three iterations per cell. The result is directional, not a
  nationwide SLA.
- **Do not treat the Tencent HTTP test as production validation:** public
  cutover still requires ICP approval, a certificate-valid hostname, HTTPS
  origin service, and a repeat S3 test.

## Reproduction notes

The canonical login scripts had stale generated element IDs. This baseline
changes them to stable semantic selectors:

```text
input[type="email"]
input[type="password"]
```

Direct Azure was forced to the App Service address while preserving
`www.praxys.run` Host/SNI. Tencent was accessed by IP over HTTP because its
Nginx listener did not yet have a certificate-valid 443 virtual host. The
Tencent-only browser profile disabled web-security for the API CORS test and
disabled Chrome HTTPS upgrades; otherwise Chrome first attempted the nonexistent
HTTPS IP endpoint and introduced an artificial three-second fallback timeout.

The Tencent HTTP run also disabled video post-processing because sitespeed's
visual-metrics frame renaming failed on the Windows Docker bind mount. Native
browser FCP, LCP, TTFB, CLS, and TBT remained available.

## Raw artifacts

HARs are intentionally not committed because authenticated captures contain
bearer tokens. The operator-session archive contains:

- `perf-edgeone-control-current/`
- `perf-edgeone-after/`
- `perf-mainland-http-final/`
- `perf-mainland-gzip/`

Derived summaries:

- `fixed-azure-control-summary.md`
- `fixed-edgeone-route-summary.md`
- `fixed-mainland-uncompressed-summary.md`
- `fixed-mainland-gzip-summary.md`
- `fixed-mainland-gzip-s2-summary.md`
