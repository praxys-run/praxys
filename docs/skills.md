# CLI and Repository Skills

Praxys has two skill surfaces:

- **Athlete-facing plugin skills** provide access to shipped training features
  through Claude Code and Copilot CLI. No web UI is needed.
- **Repository developer skills** guide maintainers through implementation and
  evidence work. They are not exposed as athlete coaching features.

## Developer science research

`science-research` is the repository-owned skill at
`.github/skills/science-research/SKILL.md`. It is auto-discoverable by Copilot
and has a thin Claude Code entry point at
`.claude/skills/praxys-science-research-claude/SKILL.md`. Invoke the Claude entry point
directly as `praxys-science-research-claude`; its distinct name prevents a
second project-skill discovery match while it delegates to the same canonical
policy.

Use it to research a bounded science question, verify literature metadata and
claim limits, update a versioned Evidence Review, or prepare a draft Science
Decision Record (SDR) and product impact map. It has two explicit modes:

- **Research-only** updates evidence in draft form without changing accepted
  product behavior.
- **Decision proposal** adds a draft SDR, alternatives, claim boundaries,
  validation plan, and implementation/reviewer map for human review.

It preserves historical records, requires search provenance and source
verification levels, and never accepts or merges science on an agent's behalf.

This is deliberately separate from the athlete-facing `/science` plugin skill.
`/science` remains browse/select only for shipped theories; it does not
research literature or change Evidence Reviews, SDRs, formulas, or product
behavior.

## Developer WeChat DevTools

`wechat-devtools` is the repository-owned integration at
`.github/skills/wechat-devtools/SKILL.md`, with a thin Claude Code entry point
at `.claude/skills/wechat-devtools/SKILL.md`. It is used for miniapp
compilation, simulator automation, screenshots, console/network diagnostics,
preview, and upload.

The repository intentionally does not copy Tencent's skill. On Windows + WSL2,
`scripts/wechatide` finds the separately installed `*-nightly` WeChat DevTools,
invokes its Windows CLI, and synchronizes `miniapp/` to a generated local
Windows mirror because DevTools rejects WSL UNC project roots. The WSL
repository remains the only source of truth. Agents load the authoritative
`wechatide-skill` from that installation, so DevTools upgrades update the tool
contract without a stale vendored copy. Stable DevTools remains separate.

Tencent provides no headless or no-focus simulator mode. To prevent accidental
desktop interruption, `scripts/wechatide` refuses to launch the Windows CLI
unless the user has approved foreground use and that one invocation is
prefixed with `WECHATIDE_ALLOW_FOREGROUND=1`. Do not export it globally.
Guaranteed isolation requires a separate Windows session or VM; WSL2 shares
the user's desktop. Supported non-simulator build, preview, and upload work
should use
[`miniprogram-ci`](https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html).
Tencent's
[DevTools CLI](https://developers.weixin.qq.com/miniprogram/dev/devtools/cli.html)
and
[`miniprogram-automator`](https://developers.weixin.qq.com/miniprogram/dev/devtools/auto/automator.html)
do not promise focus preservation.

The first `Copilot` connection requires authorization in Nightly DevTools.
Login, CLI access tokens, previews/uploads, cloud writes, and destructive
operations remain subject to Tencent's interactive approval gates.

## Athlete-facing plugin requirements

- [Claude Code](https://claude.com/claude-code) or [GitHub Copilot CLI](https://githubnext.com/projects/copilot-cli/)
- Python 3.11+ in the repository `.venv`, with both dependency sets installed:
  `python -m pip install -r requirements.txt -r plugins/praxys/mcp-server/requirements.txt`
- A Praxys account for cloud profiles; local mode bootstraps synthetic data

## Plugin Installation

Skills live in the public
[`praxys-run/praxys-coach-plugin`](https://github.com/praxys-run/praxys-coach-plugin)
repository (MIT) and are vendored here as `plugins/praxys/`.

**GitHub Copilot CLI:**

```bash
copilot plugin marketplace add praxys-run/praxys-coach-plugin
copilot plugin install praxys@praxys-coach
```

**Claude Code:**

```
/plugin marketplace add github:praxys-run/praxys-coach-plugin
/plugin install praxys
```

Run the installed `praxys` server's `login` tool once, then verify the normal
production account with `whoami`.

Local developers should clone with `--recurse-submodules` or run:

```bash
git submodule update --init plugins/praxys
```

## MCP development profiles

Praxys development deliberately separates three identities:

| Server | Data and identity | Purpose |
|---|---|---|
| `praxys` | Production API, default `~/.praxys/token` | Normal personal account |
| `praxys-dev-test` | Production API, `~/.praxys/profiles/dev-test/token` | Dedicated test user and real-provider validation |
| `praxys-local` | `.praxys-local/trainsight.db`, deterministic synthetic user | Offline-safe feature and managed-plan development |

The installed plugin provides `praxys`. The repository `.mcp.json` adds the
other two through `scripts/run_praxys_mcp.cjs`, a dependency-free Node shim
that invokes the project `.venv` directly before
`scripts/run_praxys_mcp.py` loads the submodule server. This avoids relying on
whether the MCP host exposes Python as `python`, `python3`, or `py`.
Test harnesses without a project virtualenv can set `PRAXYS_MCP_PYTHON` to an
absolute interpreter path with the project dependencies installed.

Restart the CLI after changing `.mcp.json` or updating the plugin submodule.
Use `/mcp` or `/env` to confirm the servers loaded, then call each server's
`whoami`.

### Production test profiles

`praxys-dev-test` sets `PRAXYS_PROFILE=dev-test`. Named profiles never read the
default or legacy token, so logging into the test user cannot replace the
normal production account. `logout` removes only the selected profile.

On first use:

1. Call `praxys-dev-test.login`.
2. Sign in with the dedicated Praxys test user, not a personal account.
3. Call `praxys-dev-test.whoami` and confirm the expected internal user ID for
   server-authoritative eligibility checks.
4. Connect dedicated provider accounts through the web Settings flow; Garmin
   MFA is interactive and should not be bootstrapped through MCP credentials.
5. Run `get_connections`, `get_settings`, and `get_managed_plan_status` before
   mutation tests.

Maintain test accounts as a capability matrix. Features requiring a real
provider must use dedicated provider accounts and extend the matrix rather than
borrowing a personal account. At minimum, keep separate identities for Garmin
international and Garmin China validation when both regions are exercised.
Never commit emails, passwords, JWTs, provider credentials, or user IDs.

Garmin writes remain globally disabled. An approved validation deployment must
enable the hard deployment prerequisite, and the default-off Statsig
`garmin_plan_delivery_eligible` gate may then admit a dedicated test user;
durable Garmin execution-target selection and a matching
account-generation/region fence are still required.

Additional production test profiles can reuse the launcher:

```json
"praxys-garmin-cn-test": {
  "command": "node",
  "args": [
    "scripts/run_praxys_mcp.cjs",
    "remote-profile",
    "garmin-cn-test"
  ]
}
```

### Deterministic local profile

`praxys-local` explicitly sets `PRAXYS_LOCAL=1`, clears ambient database and
provider-credential settings, and pins `PRAXYS_USER_ID` to
`migrated-user-00000001`. On first start it:

- creates the ignored `.praxys-local/` sandbox;
- generates a local encryption key inside that sandbox;
- copies all tracked Garmin, Stryd, Oura, and Praxys-plan sample data;
- creates the synthetic `local@praxys.dev` user and SQLite schema.

Subsequent starts preserve local MCP writes. Fixture changes reset the
repository-owned sandbox automatically. Reset it manually without starting an
MCP process:

```bash
python -m scripts.run_praxys_mcp local --reset --prepare-only
```

Set `PRAXYS_LOCAL_MCP_DATA_DIR` to use another sandbox. The launcher refuses a
non-empty directory unless it contains the Praxys MCP ownership marker, and it
always verifies that the resolved database is SQLite inside that directory.

Most local tools call the application's Python data and route helpers directly,
so no backend or login is required. `trigger_sync` is the exception: provider
sync still needs the authenticated local API and real credentials. Use a
production test profile for real-provider validation.

## MCP Tools

The plugin server exposes 28 tools in both remote and local modes:

| Tool | Description |
|------|-------------|
| `get_daily_brief` | Today's training signal, recovery, upcoming workouts |
| `get_training_review` | Zone distribution, fitness/fatigue, diagnosis, suggestions |
| `get_race_forecast` | Race prediction, goal feasibility, threshold trend |
| `get_training_context` | Coaching snapshot for AI plan generation; wraps `GET /api/ai/context` |
| `get_settings` | Current user settings and display config |
| `update_settings` | Update training base, thresholds, zones, goal, science |
| `get_sync_settings` / `set_sync_frequency` | Read or update scheduler cadence |
| `get_connections` | Connected platforms and their status |
| `connect_platform` | Store encrypted credentials for a platform |
| `disconnect_platform` | Remove a platform connection |
| `save_training_plan` | Author canonical Praxys workouts |
| `push_training_plan` | Backward-compatible authoring alias |
| `get_managed_plan_status` | Inspect ownership, delivery, and conflicts |
| `adopt_managed_plan` / `leave_managed_plan` | Enter or leave Praxys-managed mode |
| `pause_managed_plan` / `resume_managed_plan` | Pause or resume delivery |
| `cleanup_managed_plan_deliveries` | Remove future Praxys-owned deliveries |
| `resolve_managed_plan_conflict` | Apply a server-approved conflict action |
| `update_training_day` / `delete_training_day` | Edit canonical plan days |
| `push_training_insights` | Persist generated coaching insights |
| `trigger_sync` | Sync data from connected platforms |
| `get_sync_status` | Check sync status per platform |
| `login` / `whoami` / `logout` | Manage the active auth profile |

`PRAXYS_LOCAL=1` selects direct local mode. Otherwise the server uses the
production API unless `PRAXYS_URL` explicitly overrides it.

`get_training_context` is intentionally a bounded coaching snapshot, not a
raw research export. Analysis-ready per-activity environment, stream coverage,
stable-power segments, dated recovery, and leakage-safe pre-run context are
served by the owner-authenticated `/api/analysis/activities/{activity_id}` and
`/api/analysis/research-dataset` endpoints. The v1 MCP surface does not expose
raw samples or precise GPS; see `docs/dev/api-reference.md` for detector
semantics and limitations.

## Available Athlete-Facing Skills

### /setup

Configure connections, training base, thresholds, and goals.

**When to use:** First-time setup, adding a new data source, changing your goal, switching training base.

**Examples:**
- "Connect my Garmin account"
- "Set my goal to sub-3 marathon"
- "Switch to HR-based training"
- "Set my CP to 250 watts"

### /science

Browse and select training science theories across 4 pillars.

**When to use:** Choosing between zone frameworks, understanding different load models, switching prediction methods.

This skill explains and selects shipped theories only. Maintainers researching
evidence or proposing a product interpretation use the repository
`science-research` skill instead.

**Examples:**
- "What zone theories are available?"
- "Explain Coggan 5-zone vs Seiler polarized"
- "Switch to the Riegel prediction model"
- "How does HRV-based recovery work?"

### /sync-data

Sync training data from Garmin, Stryd, and/or Oura Ring.

**When to use:** Pulling latest data, backfilling history, checking sync status.

**Examples:**
- "Sync my data"
- "Pull garmin data from last month"
- "Sync everything except oura"

### /daily-brief

Today's training signal with recovery status and upcoming workouts.

**When to use:** Start of the day, deciding whether to train, checking recovery.

**Examples:**
- "What should I do today?"
- "Am I recovered enough to train?"
- "Show me today's brief"

If data is stale (not synced today), the skill automatically syncs first.

### /training-review

Multi-week training analysis with diagnosis and suggestions.

**When to use:** Weekly check-in, understanding training gaps, checking zone balance.

**Examples:**
- "How's my training going?"
- "Why isn't my CP improving?"
- "Check my zone distribution"
- "Give me a training review for the last 8 weeks"

### /training-plan

Generate a personalized 4-week AI training plan.

**When to use:** Starting a new training block, plan expired, changing goals.

**Examples:**
- "Generate a training plan"
- "Plan my next 4 weeks"
- "My plan is stale, regenerate it"

The skill generates the plan, validates it, shows it for review, and saves to the database on approval.

### /race-forecast

Race time prediction and goal feasibility.

**When to use:** Checking progress toward a race goal, comparing prediction methods.

**Examples:**
- "Can I hit sub-3?"
- "What's my predicted marathon time?"
- "How much CP do I need for my goal?"

### /add-metric

Scaffold a new training metric end-to-end (7-step guide).

**When to use:** Adding a new computed metric, prediction, or insight to the dashboard.

**Examples:**
- "Add a new efficiency metric"
- "Scaffold a pace decay metric"
- "I want to add a new insight to the dashboard"

## How Skills Work

Skills are defined in `plugins/praxys/skills/` — each skill has a `SKILL.md` file with instructions that Claude Code and Copilot CLI auto-discover when the plugin is installed.

Skills that need training data call the MCP tools listed above. The MCP server handles mode detection (remote vs local) transparently, so the same skill works whether you are connected to a cloud deployment or running locally.

### Architecture

```
User invokes /daily-brief
    → Claude Code reads plugins/praxys/skills/daily-brief/SKILL.md
    → Skill instructions tell the AI to call get_daily_brief MCP tool
    → MCP server (plugins/praxys/mcp-server/server.py) handles the call:
        Remote mode: GET /api/today (with JWT auth)
        Local mode:  Direct Python import → get_dashboard_data()
    → JSON response returned to the AI
    → AI formats the data as a readable brief
```

### Plugin Structure

```
plugins/praxys/
  plugin.json          Plugin manifest (name, version, component directories)
  .mcp.json            MCP server configuration
  skills/              8 skill directories (auto-discovered)
    setup/SKILL.md
    science/SKILL.md
    sync-data/SKILL.md
    daily-brief/SKILL.md
    training-review/SKILL.md
    training-plan/SKILL.md
    race-forecast/SKILL.md
    add-metric/SKILL.md
  hooks/               Event hooks (e.g., session-start)
  mcp-server/          MCP server implementation
    server.py          Dual-mode tool handlers
    auth.py            JWT token management
```
