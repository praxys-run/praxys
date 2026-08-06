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
6. Run the feature with sample data and inspect the real interaction in one
   bounded desktop/mobile pass. Prefer Chrome DevTools MCP or another available
   browser tool; use keyboard navigation and inspect console errors. Fix the
   batch of findings, then perform at most one confirmation pass.
7. Run the smallest relevant tests plus `cd web && npm run build`, miniapp
   `npm run typecheck` when applicable, and:

   ```bash
   python scripts/check_ui_quality.py --base origin/main --head HEAD --skip-evidence
   ```

8. Include the exact `## UI quality` block from the PR template. Never claim a
   viewport, state, or accessibility check that was not actually performed. If
   rendered verification is unavailable, keep the PR draft and record the
   limitation.

Brand invariants are binding: green means action, cobalt means reasoning,
surfaces use warm-paper tokens, numbers use `font-data`, scientific explanations
use `ScienceNote`, cards are never nested, ambient card shadows and gradient
text are forbidden, and colored side rails thicker than 1px are forbidden.

Do not add a dependency only to complete design QA. The vendored Impeccable
skill and detector are the canonical mechanical layer. Supporting browser,
accessibility, API-contract, metric, or science reviewers are additive when
their scopes apply.
