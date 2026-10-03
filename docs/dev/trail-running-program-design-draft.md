# Trail program — Design Decision Record draft

2026-09-14 · **draft / inactive**. Design's proposal is persisted by Engineering.
No UI implementation or rendered acceptance is claimed.

| Shared field | Value |
| --- | --- |
| id | `docs/dev/trail-running-program-design-draft.md` — Conditions, coverage and explicit adoption journey |
| schema_version | Existing `logical-contract` shared fields; no new machine or approval schema |
| decision_type | `design-decision-record` |
| owner_role | Design |
| question | How can runners understand supported training and adopt executable sessions without mistaking partial coverage for complete race preparation? |
| options | Preset-first automatic calendar; explicit conditions → coverage → proposal → adoption (recommended); unrestricted full-cycle editor |
| recommendation | Extend Goal / Training and TrailCourseReview with explicit provenance, separate support / inclusion / scheduling states and independent sibling sessions |
| rationale | Makes constraints actionable without inventing capacity, history, dates or unsupported future prescriptions |
| dependencies | [Work Contract](trail-running-program-work-contract.json), [Product](trail-running-program-product-draft.md), [Science bindings](trail-running-program-review-bindings.md), [Architecture](trail-running-program-architecture-draft.md), [Trust](trail-running-program-trust-draft.md), [Experience](trail-running-program-experience-draft.md) |
| review_route | Independent Router allocation in [Decision Review](trail-running-program-decision-review.md); no self-acceptance |
| outcome_plan | Future journey success, correct coverage understanding, executable sessions and no completion loss; no new value telemetry |
| digest | Complete UTF-8 / LF file SHA-256, resolved by this path in [bindings](trail-running-program-review-bindings.md); edits require rebinding |

## Experience direction

Adult runners often use a phone while arranging training. Use Operate mode and
the existing Field Lab language: warm paper, green action, cobalt reasoning,
`font-data`, flat sections, ScienceNote and incumbent controls / dialogs /
comparisons. Design read Product / Design / design-system context and the
TrailCourseReview / ScienceNote source. Impeccable context ran once for
TrailCourseReview; shape was planning-only. No new design-system primitive is
proposed, and no browser or miniapp rendering was performed for this change.

The [Experience Specification](trail-running-program-experience-draft.md)
defines the journey, copy pairs, constraints, session anatomy, state behavior
and future rendered matrix. Presets are editable starting points, never evidence
of ability or confirmation. Five coverage rows expose precise Science boundaries
before generation. Users explicitly adopt an exact replacement set; scheduling
is shown only after server success. Completed siblings remain independently
visible and unchanged.

The interface must show the remaining first-50-km, long-run, descent, technical,
performance, full event nutrition and environment blockers. A roadmap expresses
future review obligations. Neither roadmap nor qualified module implies
complete race preparation. Operational bounds and deletion consequences remain
understandable in EN / zh, including gate-off and unknown-version owner rights.

Future P7 acceptance requires actual desktop / mobile, theme, locale,
accessibility, failure-state and miniapp compatibility evidence against the
accepted versions. This source/context work does not satisfy that gate.
