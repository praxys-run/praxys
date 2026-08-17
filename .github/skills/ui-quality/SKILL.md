---
name: ui-quality
description: >-
  Mandatory for any user-visible Praxys web or WeChat miniapp change, including
  components, pages, styling, copy, charts, forms, navigation, responsive
  behavior, accessibility, loading/error/empty states, and visual bug fixes.
  Routes implementation through Impeccable, Praxys brand context, rendered
  verification, parity checks, and PR evidence.
user-invocable: true
argument-hint: "[target path or route]"
---

# Praxys UI Quality Harness

Use this skill before editing any user-visible interface.

This is the mandatory rendered harness for the **Praxys Design** role:

- Product owns user value, priority, and product scope.
- Design owns the intended journey, interaction, visual language, content,
  accessibility, and complete state space.
- Engineering implements the accepted Product and Design artifacts.
- Quality independently verifies the exact rendered implementation.

The harness does not let one implementation agent silently fill all four roles.

## 1. Enter Impeccable

Load and follow `.github/skills/impeccable/SKILL.md`. Run once:

```bash
node .github/skills/impeccable/scripts/context.mjs --target <primary-target>
```

Choose the narrowest command that owns the task:

- New or materially reworked flow: `shape`, then the new-work flow.
- Visual or interaction defect: `adapt`, `clarify`, `harden`, `layout`, or the
  other directly matching playbook.
- Existing feature completion: `polish`.
- Technical assessment only: `audit`.

Bug fixes preserve the incumbent visual world. Do not redesign without an
explicit product decision. Load Impeccable's `craft-floor.md` immediately before
editing UI.

## 2. Ground in Praxys

Read `PRODUCT.md`, `DESIGN.md`, `docs/dev/design-system.md`, the target, and one
representative neighboring implementation. Apply the Field Lab system:

- interpret first; data supports a verdict rather than replacing it;
- green is action and cobalt is reasoning;
- warm paper and semantic tokens replace raw colors;
- every number uses `font-data`;
- scientific reasoning uses `ScienceNote`;
- light theme and outdoor legibility are first-class;
- web and miniapp match in capability and data semantics while using
  platform-native layouts.

## 3. Build the complete state space

Cover the applicable loading, empty, error, success, disabled, permission,
offline/slow, long-content, English, Simplified Chinese, keyboard/focus,
reduced-motion, touch-target, light, dark, mobile, and desktop states. Reuse the
design system; do not introduce one-off components or tokens when an owner
already exists.

## 4. Classify design-system impact

Before the final review, choose one disposition:

- Local implementation defect: fix it in this PR and record
  `none - existing design system already covers the change`.
- Clear missing reusable token, component, or rule: update `DESIGN.md`,
  `PRODUCT.md`, `docs/dev/design-system.md`, or `docs/brand/` in this PR and
  name the changed path.
- Product decision, broad migration, or genuinely out-of-scope design debt:
  file a `Design system gap` issue before ready-for-review and link it as
  `follow-up #123 - <gap>`.

Do not hide a system gap in `Exceptions`, a one-off token, or a broad
Impeccable suppression.

## 5. Inspect the rendered path

Run the real feature with sample data. Portable Local and Cloud agents use the
common Chrome DevTools MCP; Cloud Playwright may exist as an optional extension
but is not required by the portable path. Use the synthetic read-only
`praxys-local` MCP tools when product data semantics help the review, but never
treat API output as rendered verification. Inspect desktop and mobile together,
exercise the interaction with keyboard input, and check console output. Fix
findings in one batch and perform at most one confirmation pass.

If no browser tool is available, do not claim visual verification. Keep the PR
draft and record the limitation in the UI evidence.

## 6. Choose and store reviewer evidence

Store detailed captures locally by default under:

```text
test-screenshots/ui-quality/<branch-or-pr>/
```

`test-screenshots/` is gitignored. Keep native-resolution source screenshots,
recordings, and an optional `index.html` there; never commit them. A local HTML
gallery must link to the original assets rather than flatten full screens into
one downscaled raster storyboard.

Choose the smallest medium that explains the change:

| Change | Evidence |
|---|---|
| Static styling, copy, chart, or single-state change | Native-resolution screenshots |
| Responsive behavior or important loading, empty, error, or unsupported states | Screenshots for each materially different viewport/state |
| Navigation, forms, timing, animation, gestures, or a sequence that stills cannot explain | A focused 15-45 second video; prefer MP4 for publication, while browser-native WebM is acceptable locally |
| Material multi-step journey with important edge states | Short primary-journey video plus 2-3 edge-state screenshots |

Use synthetic data only. Do not capture credentials, tokens, personal training
data, raw feedback screenshots, or authenticated network archives. Do not add a
production dependency only to record evidence; use the available browser or
platform recorder, and fall back to screenshots when recording is unavailable.

Choose the handoff for the actual reviewer:

- Synchronous local review: keep evidence local, share the live URL and local
  gallery path in the active session, and keep credentials out of the PR.
- Asynchronous PR review: publish only the minimum useful recording or 2-3
  stills. Keep exhaustive state captures local or in a CI artifact.
- Persistent cloud preview or gallery: create one only when explicitly
  requested. Blob storage is for static evidence, not an interactive app.

## 7. Validate and hand off

Run the smallest relevant tests, web build, miniapp typecheck when applicable,
and:

```bash
python scripts/check_ui_quality.py --base origin/main --head HEAD --skip-evidence
```

Complete this exact PR section:

```markdown
## UI quality
- Impeccable: `polish web/src/...`
- Visual review: desktop 1440x900; mobile 390x844
- Primary journey: Goal -> plan preview -> readiness
- Reviewer handoff: local-only - `test-screenshots/ui-quality/pr-123/index.html`
- States checked: loading, empty, error, success, long EN/zh
- Accessibility: keyboard, focus, contrast, reduced motion, touch targets
- Design system impact: none - existing tokens and components cover this change
- Miniapp parity: updated / follow-up #123 / not applicable - reason
- Exceptions: none
```

Never fill the block with planned work or unverified claims. Impeccable findings
must be fixed or documented as a narrow, intentional exception approved by a
maintainer. Valid reviewer handoff prefixes are `local-only`, `PR media`,
`CI artifact`, `preview`, and `none`; every value needs a concrete explanation.
