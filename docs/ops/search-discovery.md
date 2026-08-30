# Search discovery and regional public domains

> **Summary:** Submit Praxys public pages to search engines, record a baseline,
> and cut over the future `praxys.cn` domain without splitting product truth.
> **Use when:** Launching or measuring public SEO/GEO pages, or preparing the
> ICP-approved mainland-China public hostname.

## Prerequisites

- Owner access to Google Search Console and Bing Webmaster Tools.
- DNS access for `praxys.run` and, after ICP approval, `praxys.cn`.
- A deployed frontend build where `/robots.txt`, `/sitemap.xml`, `/product`,
  `/faq`, and their `/zh` equivalents return `200`.

## Steps

1. Verify the public discovery surface before submission:

```bash
curl -fsS https://www.praxys.run/robots.txt
curl -fsS https://www.praxys.run/sitemap.xml
curl -fsS https://www.praxys.run/product | grep -F "<h1"
curl -fsS https://www.praxys.run/zh/faq | grep -F "<h1"
curl -sSI https://www.praxys.run/today | grep -i '^x-robots-tag: noindex'
```

2. Add the `https://www.praxys.run/` URL-prefix property in Google Search
   Console and Bing Webmaster Tools. Use DNS verification where possible.
   Submit `https://www.praxys.run/sitemap.xml`. Do not commit verification
   tokens; if a provider requires an HTML file, store only the provider-issued
   public verification file under `web/public/`.

3. Record the pre-launch baseline for these query groups:

| Group | Initial queries |
|---|---|
| Branded | `praxys`, `praxys endurance`, `praxys running` |
| Training decisions | `running readiness training decision`, `should I modify my run based on HRV` |
| Power and thresholds | `running critical power training zones`, `running power training analysis` |
| Plans and forecasts | `adaptive running training plan`, `science based race time prediction` |
| Recovery and data integration | `Garmin Oura training analysis` |

Record indexed public URLs, impressions, clicks, demo starts, and account
creation attributed to organic/referral traffic. Raw page views are diagnostic,
not a success metric.

4. Keep `www.praxys.run` canonical until the ICP-approved `praxys.cn` service
   has valid managed HTTPS, a verified EdgeOne Makers deployment, accepted
   filing/access and cross-border release evidence, and search-verifiable public
   pages. Do not publish `hreflang` or canonical links to an unavailable domain.

5. At the mainland launch, serve the same generated public HTML on
   `praxys.cn`. Use self-referencing canonicals for genuinely regional pages and
   reciprocal `hreflang` links between the international English URL and the
   mainland Simplified-Chinese URL. Do not enable Cloudflare's optional
   geographic `302` during the initial cutover. If later accepted, preserve
   path/query and never permanently redirect search crawlers solely from an
   IP-geolocation result.

6. Re-submit both sitemaps after the regional canonical/hreflang change and
   monitor duplicate-canonical and alternate-page reports for at least four
   weeks.

## Verify

- Search Console and Bing accept the sitemap without fetch errors.
- All six current public URLs are discoverable and return a unique `<title>`,
  canonical URL, primary `<h1>`, visible descriptive copy, and matching JSON-LD
  without JavaScript.
- Authenticated and operational routes return `X-Robots-Tag: noindex, nofollow`
  and are absent from the sitemap.
- Product and FAQ claims match shipped behavior, including managed-plan
  ownership boundaries.

## Rollback / Recovery

If a public page contains a wrong claim or canonical, remove it from the
sitemap, deploy the corrected page, and request re-indexing. If the
`praxys.cn` cutover produces duplicate or redirect errors, stop the regional
redirect, restore the last verified canonical/hreflang set, and keep
`www.praxys.run` as the canonical surface until the regional pages are stable.

## Related

- [`tencent-frontend.md`](./tencent-frontend.md)
- [`deploy.md`](./deploy.md)
- `web/public/seo-content.json`
- `web/scripts/generate-public-pages.mjs`
- `frontend_server/main.py`

---
_Last reviewed: 2026-08-20 · Owner: @dddtc2005_
