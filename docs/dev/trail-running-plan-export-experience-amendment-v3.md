# Trail owner-export Experience supplement v3

**Status:** proposed Design Decision Record and Experience Specification
supplement; `human-review-required`. It has no authority until a human approves
the exact file digest. No implementation or rendered verification is claimed.

## Contract and dependency binding

- **Work Contract:** `pr776-trail-export-conformance-v3`
- **Role slot:** `design-amendment`
- **Revision:** `git:d89bd28234a10835caa8a82b8b6f68c56a6f74fb+trust-followup`
- **Classification:** `sha256:b0fb3575cea2d298ba990d40c8fde9d775e7456418e8625a7955346693ef3754`
- **Route:** `sha256:be35cb32d5d0ec7cd86295c07d6281dcb1104a016fa12fdbc0075f81e8832406`
- **Artifact ID:** `ddr-trail-export-conformance-v3-supplement`
- **Owner role:** Design
- **Implementation status:** `logical-contract`
- **Product dependency:** `sha256:d029b72ec58ee1a04a0035412367bb80cf498dff2a74d85d0e5bb2a63d781bbc`
- **Experience dependency:** `sha256:3e30519aa68199916c226c2306360c4911c6aeeec4f0fb40bf2da6dce9197e1f`
- **Trust dependency:** `sha256:f3241d753cbb76d16d0908ddef29417f6af967da5fc8e3014aac054244e2627c`

This supplement resolves only the Trail owner-export interaction and the CJK
identity quality rule. All other dependency behavior remains unchanged.

## Exact locale-only copy

| Purpose | English | Simplified Chinese |
| --- | --- | --- |
| Menu label | **Export my Trail plan data** | **导出我的越野计划数据** |
| Supporting copy | **Download your Praxys account data export. It includes the current saved Trail course review—values and unknowns, provenance, revisions, and confirmations—and any retained Trail proposal snapshots, audits, and receipts. Unsaved changes on this page are not included.** | **下载 Praxys 账号数据导出文件，其中包含当前已保存的越野赛道核对中的值与未知项、来源信息、版本和确认状态，以及已保留的越野提案快照、审计记录和回执（如有）。本页面尚未保存的更改不会包含在内。** |
| Busy | **Preparing export…** | **正在准备导出…** |
| Success | **Your data export is downloading.** | **正在下载数据导出文件。** |
| Error | **We couldn't export your data. Try again.** | **暂时无法导出数据，请重试。** |

The menu displays only the active locale. The supporting copy describes the
authenticated account export, not a Trail-only file, and distinguishes saved
server state from unsaved page-memory changes.

## Interaction and privacy contract

1. The enabled item performs an authenticated, same-origin
   `GET /api/me/export`. It sends no body, query parameter, owner identifier,
   Trail value, or pending-state payload; it does not autosave or serialize
   pending edits.
2. A synchronous in-flight latch is acquired before the request. While held,
   duplicate pointer, keyboard, and programmatic activation is ignored and the
   item exposes its busy state.
3. Activation closes the menu and immediately returns focus to the **More
   actions / 更多操作** trigger. Request completion announces status without
   moving focus; no late callback may steal focus.
4. Busy and success are polite live-status messages. Error is an alert. No copy
   exposes raw HTTP status, server response, exception, log, identifier, or
   internal detail.
5. A successful response starts the existing account-data download and revokes
   its object URL after use. Accept a server filename only when it matches
   `praxys-data-export-YYYY-MM-DD.json`; otherwise use
   `praxys-data-export.json`. Never label the file as Trail-only.
6. Any future change that can retain a Trail proposal snapshot, audit, or
   receipt adds complete authenticated owner-export coverage and integration
   tests in that same change. Storage cannot precede export coverage.

## CJK identity quality requirement

An identical Simplified Chinese translation is allowed only when the source
contains CJK and this deterministic procedure succeeds:

1. Strip recognized placeholders, markup, URLs, and email addresses.
2. Strip exact-boundary, case-sensitive occurrences of only `Praxys`, `API`,
   and `v2`.
3. Require that no ASCII Latin letter remains. ASCII digits may remain.
4. Run every other placeholder, canonical-term, forbidden-term, typography,
   protected-token, semantic, fuzzy, coverage, and human-review rule normally.

Minimum positive tests are CJK-only identity, `Praxys 请继续`, and
`未启用的越野 API 使用 v2。`. Minimum negative tests require
`请 click Continue` and any other unlisted Latin token to fail; `Praxys 请您重试`
must still fail the existing forbidden-term rule.

## Boundary, verification, and human decision

The Trail runtime remains inactive, unregistered, and unreachable. This
supplement authorizes no implementation, provider action, production data,
merge, deployment, activation, preview exposure, or dogfood. Design-system
impact is `none`; existing menu, status, alert, focus, and locale patterns apply.

After human acceptance, Engineering may implement only this bounded contract.
Quality independently verifies EN/zh copy, duplicate activation, focus, live
announcements, error privacy, filename validation, URL revocation,
saved-versus-pending behavior, and complete synthetic export coverage. Human
approval of the exact digest authorizes only that future inactive implementation
and does not approve merge, release, or activation.
