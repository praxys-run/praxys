# I18n automation hardening

**Artifact roles:** Design Decision Record, Experience Specification,
Implementation Impact Map, and evaluation boundary for this change.

**Status:** implemented change candidate; human review remains required.

## Accepted product and design context

This change reuses the accepted product requirement in `PRODUCT.md` that
bilingual support is structural and product chrome follows the user's locale.
It does not introduce a language, product promise, scientific claim, or new
translation authority. `DESIGN.md` remains the content authority: technical
terms stay precise, action and reasoning keep their distinct meanings, and
Chinese product copy must read naturally without changing the underlying truth.
Science YAML is excluded from this automation until an accepted Science-owned
semantic and review contract exists.

The complete intended state space for generated Simplified Chinese copy is:

- new, existing, resurrected, and Lingui `fuzzy` entries;
- ICU placeholders, Lingui component tags, and multiline copy;
- ordinary UI, scientific interpretation, safety, privacy, and plan-authority
  content;
- canonical Web catalog plus generated WeChat catalog parity;
- successful, rejected, uncertain, malformed, over-budget, stale-head, failed
  dependency, and failed downstream-validation paths.

No rendered component or layout changes. The design-system impact is
`none - existing localization and typography rules cover the change`.

## Implementation impact map

- Translation client: import-smoke shared Azure client dependencies; the lean
  workflow cannot drift from `api.llm` imports.
- New translation: translate one source-proximity cluster, then run a separate
  semantic-faithfulness pass; structure, deterministic terms, and
  high-confidence meaning must all pass before write.
- Existing translation: review stable semantic clusters with bounded
  same-screen reference copy; shards and cost windows never split a cluster.
- Lingui state: treat `fuzzy` with a retained `msgstr` as unfinished and clear
  only the fuzzy flag after every gate accepts the replacement.
- Deterministic quality: validate scoped critical terms and safe source refs;
  model confidence cannot override checked-in terminology.
- Human judgment: route changed science, safety, privacy, and plan-authority
  text into a manifest; an empty manifest is not approval and generated PRs
  remain Draft.
- Web/WeChat parity: regenerate `miniapp/utils/i18n-catalog.ts` from the accepted
  PO catalog so both clients ship the same shared Chinese strings.
- PR lifecycle: use one branch per source SHA/run/attempt and bind validation to
  the API-read head, avoiding force-push accumulation and stale-head success.
- Validation: wait for Pre-merge CI and Miniapp build, publish one exact-head
  status, then dispatch the selective-review gate. That required status reads
  the same PR head and requires `translation-validation=success`.
- Recovery: deterministic catalog failure may create a red Draft so successful
  work is recoverable, but it cannot acquire a green exact-head status and the
  job still fails.

## Decision review handoff

The material decision is whether automation may merge or otherwise approve
Chinese catalog changes without human judgment. Recommendation: **no**. Keep
every generated PR draft, preserve `web/src/locales/**` as sensitive, and use
the deterministic/model gates only as defense in depth. The realistic
alternative—automatic approval after green checks—is deferred because the
current cohort includes corrected semantic regressions and has no five-sample,
seven-day clean evidence set. For users, this trades some translation latency
for protection of scientific, safety, privacy, and plan-authority meaning.

Review subject: `praxys-i18n-human-review-boundary-v1`. The immutable route
digest below binds this handoff; human authority is materialized only by a
maintainer reviewing the later generated catalog diff and marking its PR ready.

## Evaluation and policy boundary

The existing `translation-catalog-only` autonomy class remains unpromoted and
`web/src/locales/**` remains sensitive. This implementation does not deploy or
propose an autonomy increase. Generated PRs are an evidence-producing cohort
only after they reach a terminal outcome. The checked-in promotion floor remains
at least five completed PRs, seven observation days, zero human corrections,
zero PR-caused failures, zero reverts/reopens, and complete test-policy evidence.
Any future relaxation requires a separate Evaluation Report, replay/shadow
evidence, policy proposal, independent review, and an explicit policy change.

## Verification contract

- Unit tests cover prompt context, cluster selection/rotation, semantic and
  structural rejection, duplicate decisions, deterministic terms, `fuzzy`
  handling, source-path containment, human-review routing, and workflow status
  binding.
- `actionlint` validates the workflow.
- The deterministic catalog gate must pass the full active catalog.
- Miniapp typecheck regenerates and verifies the shared catalog.
- The repository UI gate records that no rendered UI source changed.
- A maintainer reviews the generated Draft diff and its manifest before marking
  it ready.

Routing evidence for this change:

- classification digest: `sha256:29cf7e410b957cba3781ff8421740e84ed9f0c1abeefc789279a0b24ad95e63d`
- route digest: `sha256:1bb956e1a7eab7e307adcac6b9bebd1dbff30936654d0e25f04d781e464855f2`
