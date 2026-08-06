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

Run the real feature with sample data. Prefer Chrome DevTools MCP; the GitHub
Copilot cloud agent also has Playwright available by default. Use the synthetic
read-only `praxys-local` MCP tools when product data semantics help the review,
but never treat API output as rendered verification. Inspect desktop and mobile
together, exercise the interaction with keyboard input, and check console
output. Fix findings in one batch and perform at most one confirmation pass.

If no browser tool is available, do not claim visual verification. Keep the PR
draft and record the limitation in the UI evidence.

## 6. Validate and hand off

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
- States checked: loading, empty, error, success, long EN/zh
- Accessibility: keyboard, focus, contrast, reduced motion, touch targets
- Design system impact: none - existing tokens and components cover this change
- Miniapp parity: updated / follow-up #123 / not applicable - reason
- Exceptions: none
```

Never fill the block with planned work or unverified claims. Impeccable findings
must be fixed or documented as a narrow, intentional exception approved by a
maintainer.
