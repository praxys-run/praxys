# File the China website with public security

> **Summary:** Prepare and submit the post-launch public-security website
> filing for `praxys.cn`, then publish only the exact issued footer.
> **Use when:** The `.cn` site has first become publicly reachable, or the
> filing authority asks for corrections or footer verification.

This is separate from ICP filing. Under Articles 12 and 23 of the Measures for
the Security Protection Administration of the International Networking of
Computer Information Networks, the operator must complete the public-security
filing within 30 days after the network is formally connected. The official
filing entry point is the [National Internet Security Management Service
Platform](https://beian.mps.gov.cn/).

## Prerequisites

- `praxys.cn` and `www.praxys.cn` are publicly reachable over valid TLS.
- The launch record contains the exact first-public-access date, DNS answers,
  EdgeOne deployment ID, source SHA, and ICP number
  `沪ICP备2025109616号-2`.
- The operator has the filing-subject and responsible-person identity
  material, domain certificate, and current registrar and access-provider
  details. Keep identity documents and phone numbers outside the repository.
- A website security officer and reachable 24x7 emergency contact are
  designated with the identity material required by the platform. The
  platform recommends different people for those two contacts.

## Steps

1. Sign in to `https://beian.mps.gov.cn/` as the real filing subject and create
   the website filing.
2. Copy the website name and ICP details from the accepted ICP record. Enter
   `praxys.cn`, every publicly reachable subdomain, the actual IP addresses,
   access method, language, site/service type, registrar, access provider, and
   opening date from live provider evidence.
3. Upload only the requested identity, domain, and prior-approval materials.
   Do not guess the EdgeOne access-provider classification, registrar,
   interaction type, or other provider fields; use the platform lookup or get
   written values from Tencent/EdgeOne support.
4. Submit within 30 days of formal connectivity. Monitor the platform and the
   registered phone: the authority may request corrections, in-person identity
   verification, or an on-site inspection. Current platform guidance allows up
   to 30 calendar days for review.
5. Because the ICP record predates this launch, confirm with the responsible
   Shanghai public-security authority which date it wants in the "website
   opening date" field. Preserve evidence that the `.cn` site was previously
   unavailable and the exact first-public-access record.
6. After approval, open **My websites -> Details**, download the official icon,
   and copy the exact issued HTML, query URL, and `沪公网安备…号`. Create a
   separate reviewed frontend change; never invent a placeholder value.

## Verify

- The platform shows the filing as approved for the exact domain and subject.
- Every EdgeOne `.cn` route footer contains the platform-issued icon, number,
  and query link exactly once.
- The `.run` build contains no `.cn` public-security filing markup.
- Outside-in probes confirm both `.cn` hosts serve the issued footer.

## Rollback / Recovery

- For rejected/corrected filings, keep the issued-number change out of
  production until the platform supplies the final exact artifacts.
- If an already-issued footer change is wrong, remove only that incorrect
  public-security markup through protected `main`; do not replace it with a
  guessed number or unofficial icon.
- For a site takedown, follow [China web private alpha](./cn-web-private-alpha.md)
  and notify the filing authority when required.

## Related

- [China government publication of the governing measures, Articles 12 and
  23](https://www.gov.cn/gongbao/content/2011/content_1860856.htm)
- [National Internet Security Management Service
  Platform](https://beian.mps.gov.cn/)
- [Tencent public-security filing guide](https://cloud.tencent.com/document/product/243/19142)
- [Regional frontend delivery](./tencent-frontend.md)
- [China web private alpha](./cn-web-private-alpha.md)

---
_Last reviewed: 2026-08-30 · Owner: Operations / human filing subject_
