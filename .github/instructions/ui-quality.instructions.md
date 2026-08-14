---
description: "Mandatory brand-aware UI flow for Praxys web and WeChat surfaces"
applyTo: "web/**,miniapp/**,DESIGN.md,PRODUCT.md,docs/brand/**,docs/dev/design-system.md"
---

# Praxys UI quality flow

Treat every user-visible change as an **Operate-mode** product design task, not
as styling after implementation.

1. Invoke the repository `ui-quality` skill before editing. It loads and follows
   `.github/skills/impeccable/SKILL.md`; run its context command exactly once for
   the primary target.
2. Read `PRODUCT.md`, `DESIGN.md`, `docs/dev/design-system.md`, the target, and a
   neighboring component that represents current visual truth.
3. For a bug fix or bounded feature, preserve the incumbent identity and use the
   narrowest fitting Impeccable command. Do not smuggle in a redesign. New or
   ambiguous surfaces start with `shape`; every implementation finishes with
   `polish`.
4. Build the complete path: loading, empty, error, success, disabled, permission,
   long-content, English, Simplified Chinese, keyboard/focus, reduced-motion,
   touch-target, light-theme, dark-theme, and responsive states as applicable.
5. Keep web and miniapp feature semantics aligned. Update both surfaces or link
   an explicit `miniapp parity gap` follow-up in the PR.
6. Classify every discovery: fix local defects now; update a clear missing
   reusable rule/token/component in the design source of truth; or file and
   link a `Design system gap` issue for a product decision, broad migration, or
   out-of-scope debt. Never hide the gap in a one-off or broad suppression.
7. Run the feature with sample data and inspect the real interaction in one
   bounded desktop/mobile pass. Prefer Chrome DevTools MCP; the cloud coding
   agent can use built-in Playwright. Praxys MCP may supply synthetic data
   semantics but never replaces rendered review. For WeChat on Windows + WSL2,
   use the repository skill only after the user approves foreground
   interruption; Tencent has no headless/no-focus simulator mode. Never replace
   registered tools with raw desktop focus, cursor, keyboard, mouse, or
   coordinate automation. Use keyboard navigation and inspect console errors.
   Fix the batch of findings, then perform at most one confirmation pass.
8. Store detailed captures locally under the gitignored
   `test-screenshots/ui-quality/<branch-or-pr>/` directory. Use
   native-resolution screenshots for static or state comparisons, a focused
   15-45 second video for sequence-dependent interactions, and both only for a
   material multi-step journey with important edge states. Prefer MP4 for
   publication; browser-native WebM is acceptable for local review. Never
   flatten full screens into a downscaled raster storyboard. Use synthetic data
   and keep credentials, personal training data, raw feedback screenshots, and
   authenticated network archives out of captures.
9. Match the handoff to the reviewer. For synchronous local review, share the
   live URL and local gallery path in the active session and upload nothing.
   For asynchronous PR review, publish only the minimum useful recording or
   2-3 stills; keep exhaustive evidence local or in a CI artifact. Create a
   persistent cloud preview or gallery only when explicitly requested.
10. Run the smallest relevant tests plus `cd web && npm run build`, miniapp
   `npm run typecheck` when applicable, and:

   ```bash
   python scripts/check_ui_quality.py --base origin/main --head HEAD --skip-evidence
   ```

11. Include the exact `## UI quality` block from the PR template, including the
    mandatory `Primary journey`, `Reviewer handoff`, and `Design system impact`
    fields. `Reviewer handoff` must start with `local-only`, `PR media`,
    `CI artifact`, `preview`, or `none`, followed by a concrete explanation.
    Never claim a viewport, state, accessibility check, or published artifact
    that was not actually performed. If rendered verification is unavailable,
    keep the PR draft and record the limitation.

Brand invariants are binding: green means action, cobalt means reasoning,
surfaces use warm-paper tokens, numbers use `font-data`, scientific explanations
use `ScienceNote`, cards are never nested, ambient card shadows and gradient
text are forbidden, and colored side rails thicker than 1px are forbidden.

Do not add a dependency only to complete design QA. The vendored Impeccable
skill and detector are the canonical mechanical layer. Supporting browser,
accessibility, API-contract, metric, or science reviewers are additive when
their scopes apply.
