---
name: wechat-devtools
description: >-
  Use for Praxys WeChat miniapp compilation, simulator automation, screenshots,
  console/network diagnostics, preview, and upload. Bridges a WSL2 agent to the
  Windows Nightly WeChat DevTools and delegates tool semantics to Tencent's
  installed wechatide-skill.
user-invocable: true
argument-hint: "[miniapp task]"
---

# WeChat DevTools

Use this skill whenever a miniapp task needs rendered verification, simulator
interaction, runtime diagnostics, preview, or upload. It complements the
repository `ui-quality` skill; it does not replace the required product,
accessibility, state, parity, or PR-evidence review.

## Load the authoritative upstream skill

Tencent ships the canonical skill inside the installed Nightly DevTools. Do not
copy or edit that directory in this repository.

```bash
skill_root="$(scripts/wechatide --print-skill-root)"
```

Read `${skill_root}/SKILL.md`, then read only the scene and references it routes
the current task to. Tool names and parameters come from the installed skill,
especially `${skill_root}/wechatide-tools/references/tools.yaml`; never invent
them.

All upstream commands written as `wechatide ...` must be executed as:

```bash
scripts/wechatide ...
```

The wrapper selects the separately installed `*-nightly` build and invokes the
Windows CLI. WeChat DevTools rejects WSL UNC project roots, so when a command
receives the repository `miniapp/` path the wrapper first synchronizes it to a
generated Windows-side mirror, then passes that local Windows path. The WSL
repository remains the only source of truth; never edit the mirror.

Tencent exposes no headless, background, or no-focus mode for simulator work.
Even `liteMode` opens a visible simulator, and the first call for a client name
may open an authorization window. The wrapper therefore refuses to launch the
Windows CLI by default. After the user explicitly approves foreground
interruption, scope permission to each required command:

```bash
WECHATIDE_ALLOW_FOREGROUND=1 scripts/wechatide ...
```

Do not export `WECHATIDE_ALLOW_FOREGROUND` for the shell, put it in `.env`, or
enable it merely to satisfy rendered evidence. The local-only
`--print-skill-root`, `--sync-project`, and `--print-project-root` operations do
not launch DevTools and remain available without permission.

Never bypass the installed skill with direct Windows desktop automation such
as `SetForegroundWindow`, `SwitchToThisWindow`, cursor positioning, synthetic
mouse events, or coordinate clicks outside the registered `wechatide` tools.
If an interaction cannot be completed through the upstream automation scene
without taking over the desktop, either schedule a user-approved session or
leave rendered verification incomplete. For guaranteed isolation, use a
dedicated Windows session or VM; WSL2 alone shares the user's Windows desktop.

Use `miniprogram-ci` for supported GUI-free build, preview, and upload work.
It does not provide simulator interaction, screenshots, or console/network
inspection. `miniprogram-automator.connect()` can reuse an existing automation
WebSocket, but Tencent does not guarantee that simulator operations will avoid
raising the window, and the current `wechatide-skill` does not expose that
connection mode.

Set `WECHATIDE_INSTALL_ROOT` to an explicit WSL path only when Nightly is
installed outside the normal Tencent directory. Set
`WECHATIDE_PROJECT_MIRROR` only when the generated mirror needs a different
Windows-mounted location.

## Praxys project

The miniapp project root is:

```text
<repository root>/miniapp
```

Before opening it, confirm `miniapp/project.config.json` exists and has a valid
non-tourist `appid`, as required by the upstream skill. Pass the absolute WSL
path; the wrapper synchronizes and converts it. To prepare or inspect the
mirror explicitly:

```bash
scripts/wechatide --sync-project
scripts/wechatide --print-project-root
```

Use the stable client name `Copilot` for authorization:

```bash
scripts/wechatide -c Copilot check_wechatide_status --skill-version <version>
```

Read `<version>` from the installed upstream `SKILL.md`; do not hardcode it.
Complete the upstream status, login, token, approval, and asynchronous-task
gates before invoking business tools. Never store a CLI access token in the
repository or print it in logs.

`check_wechatide_status` is logically read-only but still requires client
authorization, so its first call can open DevTools. Treat it as foreground
capable. Do not probe the special authorization command with
`wechatide auth -h`; that route starts authorization instead of behaving like
ordinary tool help. Read the installed readiness documentation for its
contract.

## Verification boundary

For miniapp UI changes, use the simulator tools to open the affected page,
exercise the interaction, capture synthetic-data screenshots, and inspect
console/network output. A simulator refresh alone is not compilation proof;
follow the upstream compiler scene and still run `cd miniapp && npm run
typecheck`.

Preview, upload, cloud writes, destructive project operations, login, and
authorization remain user-gated exactly as documented by the upstream skill.
