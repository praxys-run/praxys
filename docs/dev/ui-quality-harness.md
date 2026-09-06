# UI Quality Harness

Praxys treats UI work as a product-quality change, not a final styling pass.
The harness gives GitHub Copilot, the Copilot coding agent, Claude Code, and
human contributors one brand-aware path from task intake to PR review.

In the agentic operating model, Product owns user value, Design owns the
experience, Engineering implements accepted artifacts, and Quality verifies the
exact rendered change. This harness is the mandatory rendered Design and
verification path; it does not make UI implementation a separate top-level role.

## Enforcement layers

| Layer | Repository owner | What it guarantees |
|---|---|---|
| Task routing | `.github/skills/ui-quality/SKILL.md` | Every user-visible change enters the same Impeccable-led flow. |
| Path instructions | `.github/instructions/ui-quality.instructions.md` | Copilot receives the flow whenever it edits web, miniapp, or design-governance paths. |
| Product context | `PRODUCT.md`, `DESIGN.md`, `docs/dev/design-system.md` | Agents design for the Field Lab, two-track semantics, outdoor use, and bilingual clients. |
| Edit-time feedback | `.github/hooks/impeccable.json`, `.claude/settings.json` | Mechanical design drift is surfaced immediately after UI edits. |
| Shared detector policy | `.impeccable/config.json` | Web plus miniapp WXML/WXSS use the same detector and reviewed exceptions. |
| PR gate | `scripts/check_ui_quality.py` in `frontend-quality` | Changed UI files must pass Impeccable and the PR must contain completed review evidence. |
| Independent review | `praxys-invariant-review.md` | Ready PRs receive a separate Praxys-specific brand and UI invariant review. |

`frontend-quality` is the domain check for the web build and UI harness.
It is required independently from `backend-tests`; both report from the unified
`Pre-merge CI` workflow so UI validation is not presented as a backend test.

## What triggers the harness

Use it for any user-visible web or miniapp change: components, pages, CSS/WXSS,
WXML, forms, navigation, charts, copy, localization, accessibility, responsive
behavior, state handling, assets, and visual bug fixes. Use it when changing the
shared product or design direction too, even when no rendered file changes.

API types, build tooling, tests, and generated client files do not trigger the
rendered-UI evidence gate by themselves. If they accompany a rendered change,
the rendered files trigger it.

## Agent flow

1. Invoke `ui-quality` before editing.
2. Load the vendored Impeccable skill and run its context command once for the
   primary target.
3. Read `PRODUCT.md`, `DESIGN.md`, `docs/dev/design-system.md`, the target, and a
   representative neighboring implementation.
4. Choose the narrowest Impeccable command. A bounded bug fix preserves the
   incumbent visual world; a new or materially changed flow starts with
   `shape`; the implementation ends with `polish`.
5. Implement the full state space that applies: loading, empty, error, success,
   disabled, permission, long content, EN/zh, keyboard/focus, reduced motion,
   touch targets, light/dark, mobile/desktop, and slow/offline behavior.
6. Preserve web/miniapp feature and data semantics. Platform-native layout may
   differ; capability may not drift silently.
7. Classify design-system impact: fix a local defect now; update a clear missing
   reusable rule/token/component in the source of truth; or file a linked
   `Design system gap` issue for a broad decision or out-of-scope migration.
8. Run the real feature with sample data. Portable Local and Cloud agents use
   the common Chrome DevTools MCP; Cloud Playwright is optional. For a
   local miniapp change on Windows + WSL2, invoke `wechat-devtools` and inspect
   the affected page in the WeChat simulator, including screenshots and
   console/network output. Praxys MCP may provide synthetic data semantics but
   does not replace rendered review. Fix findings in one batch, then do at most
   one confirmation pass.
9. Choose reviewer evidence using the policy below, keeping detailed captures
   local by default.
10. Run targeted tests, builds/typechecks, and the local gate. Complete the PR
   evidence before marking the PR ready.

If browser automation is unavailable, the contributor must not claim rendered
verification. An agent keeps the PR draft and records the limitation.

## Reviewer evidence and local storage

Detailed review media is local-first. Store native-resolution source files
under:

```text
test-screenshots/ui-quality/<branch-or-pr>/
```

The parent directory is gitignored. A useful local bundle contains clearly
named screenshots or recordings plus an optional `index.html` that links to the
original files. Do not flatten desktop screens into a single raster storyboard:
PR columns and full-page screenshot helpers can silently downscale it until the
UI copy is unreadable.

Choose the smallest medium that preserves the behavior under review:

| Change | Preferred evidence |
|---|---|
| Static styling, copy, chart, or one stable state | Native-resolution screenshots |
| Responsive differences or loading, empty, error, permission, or unsupported states | Screenshots for each materially different viewport/state |
| Multi-page navigation, forms, timing, animation, gestures, or progressive state | Focused 15-45 second video; prefer MP4 for publication, while browser-native WebM is acceptable locally |
| Material multi-step journey plus important edge states | Short primary-journey video and 2-3 edge-state screenshots |

Use synthetic data only. Captures must not contain credentials, access tokens,
personal training data, raw feedback screenshots, or authenticated HAR/network
archives. Do not add a product dependency only to record evidence. Use the
available Chrome DevTools or WeChat recorder; if recording is unavailable,
capture the sequence as native-resolution stills.

The review audience determines publication:

- **Synchronous local review:** share the live URL and local gallery path in the
  active agent session. Keep credentials in that session and upload no media.
- **Asynchronous PR review:** publish only the minimum useful evidence: one
  short recording, 2-3 stills, or both for a material journey. Keep the
  exhaustive state set local or in a CI artifact.
- **Persistent cloud review:** create an authenticated preview or static
  gallery only when explicitly requested. Blob storage can host static media
  but is not an interactive application preview.

The PR remains a concise decision record. `Primary journey` tells reviewers
what path matters; `Reviewer handoff` says where the evidence lives without
requiring public media. Valid handoff modes are `local-only`, `PR media`,
`CI artifact`, `preview`, and `none`, each followed by a concrete explanation.

The repository does not vendor Tencent's DevTools skill. The
`wechat-devtools` wrapper reads the authoritative copy from a separately
installed Nightly build and uses `scripts/wechatide` to cross the WSL2/Windows
process boundary. Because DevTools rejects WSL UNC project roots, the wrapper
synchronizes `miniapp/` to a generated Windows-side mirror before project
operations; the WSL repository remains authoritative. Stable WeChat DevTools
remains separate and is not selected by default.

Tencent provides no headless or no-focus simulator mode. The wrapper blocks
Windows CLI launch by default; after explicit user approval, prefix each
required invocation with `WECHATIDE_ALLOW_FOREGROUND=1`. Do not export the
permission globally. For uninterrupted local work, schedule the rendered pass
or use a separate Windows session/VM.
Direct Windows focus, cursor, mouse-event, or coordinate automation is not an
acceptable substitute for the registered `wechatide` tools.

## Brand floor

The full source of truth is `DESIGN.md`. The high-frequency invariants are:

- interpret first; charts and metrics support a recommendation or verdict;
- green means action, cobalt means reasoning;
- warm-paper and semantic tokens replace raw colors;
- every numeric value uses `font-data`;
- scientific explanations use `ScienceNote`;
- light theme and outdoor legibility are first-class;
- cards are not nested, ambient card shadows are forbidden, gradient text is
  forbidden, and colored side rails thicker than 1px are forbidden.

## Local validation

For a web change:

```bash
cd web
npm run build
cd ..
python scripts/check_ui_quality.py --base origin/main --head HEAD --skip-evidence
```

For a miniapp change, also run:

```bash
cd miniapp
npm run typecheck
```

The local gate intentionally skips PR-body evidence. CI reads the live PR body
and requires:

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

Placeholders, planned checks, `not run`, and unexplained `N/A` values fail the
gate. Image-only UI changes still require evidence even though the mechanical
detector has no source file to scan.

## Design-system discoveries

The PR field is a decision record, not a free-form note:

- `none - <reason>` means the existing system already defines the correct
  reusable behavior and the PR simply follows it.
- `updated in this PR - <changed path>` requires a change to `DESIGN.md`,
  `docs/dev/design-system.md`, `PRODUCT.md`, or `docs/brand/`.
- `follow-up #123 - <gap>` requires an already-filed issue created from
  `.github/ISSUE_TEMPLATE/design-system-gap.yml`.

Use the current PR for a clear missing token, shared component, interaction
rule, accessibility rule, or documentation correction. Use a follow-up only
when the decision is product-level, the migration is materially broader than
the feature, or the correct reusable abstraction is not yet clear. `Exceptions`
does not waive this classification, and broad Impeccable suppressions are not a
substitute for design-system ownership.

## Browser and product MCP tools

The GitHub Copilot cloud agent may include Playwright, but portable Praxys
agents use the same pinned Chrome DevTools MCP in Local and Cloud. Chrome runs
headless and isolated, opts out of
usage statistics and CrUX lookups, redacts network headers, and exposes only
the interaction, screenshot, console, network, emulation, and Lighthouse tools
used by this flow.

Committed `.mcp.json` files are not the cloud agent's repository MCP settings.
After the setup workflow is merged, an administrator must copy
`config/copilot-cloud-mcp.json` into **Settings → Copilot → MCP servers**. That
cloud configuration adds Chrome DevTools plus only read-only tools from the
synthetic `praxys-local` profile. It deliberately excludes `praxys-dev-test`,
production authentication, provider connections, sync, and plan mutations.
`copilot-setup-steps.yml` initializes the plugin submodule, installs its MCP
runtime, verifies Chrome, prepares the synthetic sample-data sandbox, and
symlinks a `praxys-local-mcp` command to the launcher in the workspace. Cloud
MCP processes do not reliably inherit the repository root, `GITHUB_WORKSPACE`,
or configured Python-selection environment, so the launcher resolves its own
symlink to find the repository and selects the interpreter prepared by
`actions/setup-python`. Setup also verifies the exact FastMCP import used by
the pinned plugin runtime. The cloud payload must use that installed launcher
rather than invoke the repository Python module directly.

Use Chrome DevTools to judge the portable rendered experience. Use
`praxys-local` only to inspect the product's sample-data semantics or expected
view payloads.

## Change-loop coding agents

The Copilot coding agent reads `.github/copilot-instructions.md` and the
path-specific UI instructions from the default branch. The committed Copilot
hook invokes the vendored detector after edits, and
`copilot-setup-steps.yml` provides Node, Python, backend dependencies, and web
dependencies before the agent starts.

For an `agent-ready` issue that touches UI, the agent must:

- keep the PR draft while the rendered review or evidence is incomplete;
- keep the raw screenshot and every image-derived description on the private
  admin path; public issues contain only independently privacy-reviewed text;
- complete the UI evidence and pass `frontend-quality` (plus the compatibility
  `backend-tests` context) before the ready handoff;
- accept the independent invariant review as review evidence, not as permission
  to self-approve or merge.

## Maintaining Impeccable

The canonical vendored copy is `.github/skills/impeccable/`. The small Claude
skill points to that copy so detector and playbook versions cannot drift between
agents. It is sourced from `pbakaus/impeccable` under Apache-2.0; keep the
vendored `LICENSE` and `NOTICE.md` with it. Update the vendor intentionally with
the Impeccable CLI, review the vendor diff, and rerun:

```bash
python -m pytest tests/test_ui_quality_harness.py
node .github/skills/impeccable/scripts/context.mjs --target web/src
python scripts/check_ui_quality.py --changed-file web/src/pages/Today.tsx --skip-evidence
```

Shared detector exceptions belong in `.impeccable/config.json` and must be
narrow. Use Impeccable's `hooks ignore-*` flow instead of hand-writing a broad
suppression. Developer consent and hook cache files are local and gitignored.

Do not commit screenshots made from personal training data. Use synthetic sample
data and keep ad-hoc captures in ignored paths.
