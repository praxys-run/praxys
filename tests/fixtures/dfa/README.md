# Synthetic native DFA verification

These function-source fixtures are for Tencent's registered automator tools. They
contain no athlete data, tokens, provider calls or production debug routes. They
exercise the existing `pages/analysis/index` and `dfa-analysis` component. The initial preparation did not create a Windows mirror or simulator window.
The subsequent bounded native pass is recorded in
[implementation verification](../../../docs/dev/activity-dfa-alpha1-verification.md);
it does not establish real-device chart drawing or complete native acceptance.

## Authority and preparation

Read the repository `wechat-devtools` skill and the installed Nightly skill first:
`/mnt/d/Program Files (x86)/Tencent/微信web开发者工具-nightly/resources/app.asar.unpacked/wechatide-skill`.
This fixture was prepared against installed version **0.3.11**, specifically the
root/automator/debugger instructions and `wechatide-tools/references/tools.yaml`.
Recheck installed version/schema if the tool has since updated.

For authorized miniapp work, use `scripts/wechatide -c Copilot ...` in the
required non-sandbox desktop-capable shell without a separate foreground
question or environment opt-in. Honor explicit user restrictions; reuse one
project window and close only task-owned windows at the end. Complete the installed status/login/token gates:
`check_wechatide_status --skill-version 0.3.11`. Never place credentials in these
fixtures or read an existing token store. If an authorization or other asynchronous
operation is pending, follow the installed pending-task protocol before proceeding.
Use the existing valid project AppID; do not replace it with a tourist ID. The
wrapper owns any eventual project synchronization; do not edit its Windows mirror.

The project argument is this checkout's absolute `miniapp/` path. Do not capture
screenshots or inspect data until the synthetic request/storage mocks below are
installed. Begin at the existing login page with no authentication action. All
subsequent requests are intercepted, including unrelated routes (closed503).

## Prepare the Windows CLI sources

Installed Nightly skill 0.3.11 passed a tiny one-line 503 request mock, but sending
the original multiline function through the Windows `.cmd` boundary returned
`Unexpected token ')'`. The equivalent single-line full request function
(6794 bytes) installed through the registered tool. Generate these copies with
the existing web TypeScript dependency; keep the readable sources unchanged:

```bash
node web/scripts/prepare-dfa-native-fixtures.mjs --output-dir /tmp/dfa-native-sources
```

The helper handles only the four named fixtures. It parses one ordinary named
JavaScript function, removes comments with the TypeScript printer, preserves
literal/template/regex spans, collapses layout whitespace and checks the parsed
structure again. Generated files have no trailing newline; the command reports
source/output hashes and sizes. Physical line breaks inside literals/templates,
unsupported source shapes, NUL or sources over 64 KiB fail instead of being
silently rewritten. This is a fixture formatter, not a general-purpose minifier
or a change to PowerShell/Tencent transport. Node equivalence tests cover all
synthetic states and the four exported function behaviors; native evidence is
still recorded separately.

The installed 0.3.11 CLI also rejects literal `--args` with
`INPUT_ERROR deprecated_args`, despite the schema's `args` field. For every
array argument below, write the array as JSON to a file and pass `--args-file`.
Do not build a shell command by interpolating JavaScript or JSON strings.

## Registered tool sequence

Use the exact registered tools and field names below. Function fields are strings:
read the generated single-line files and pass them as a structured argument or a `subprocess` argument,
not by constructing a shell command. For example, within authorized miniapp work:

```python
from pathlib import Path
import subprocess

root = Path.cwd()
source = Path('/tmp/dfa-native-sources/native-request-mock.js').read_text()
subprocess.run([
    str(root / 'scripts/wechatide'), '-c', 'Copilot', 'automation_wx_api',
    '--project', str(root / 'miniapp'), '--action', 'mock', '--method', 'request',
    '--function-declaration', source,
], check=True)
```

For the setup array, the verified CLI recipe is:

```python
import json

arguments = Path('/tmp/dfa-native-setup-args.json')
arguments.write_text(json.dumps(['prepare', 'zh', 'light']))
subprocess.run([
    str(root / 'scripts/wechatide'), '-c', 'Copilot', 'automation_evaluate',
    '--project', str(root / 'miniapp'),
    '--fn-source', Path('/tmp/dfa-native-sources/native-setup.js').read_text(),
    '--args-file', str(arguments),
], check=True)
```

1. Install `automation_wx_api` with `action=mock`, `method=request`,
   `functionDeclaration=<generated native-request-mock.js>`. The fixture has no forwarding
   fallback and returns503 until its synthetic state is initialized.
2. Install `automation_wx_api` with `action=mock`, `method=getStorageSync`,
   `functionDeclaration=<generated native-storage-mock.js>`. This suppresses token reads and
   supplies only the current checked-in notice version and synthetic locale/theme.
   If `TERMS_VERSION` changed, update the fixture's version before execution;
   never create a real receipt or persist storage as part of this check.
3. Call `automation_evaluate` with `fnSource=<generated native-setup.js>` and
   `--args-file` containing `["prepare","zh","light"]`. Alternatives: `complete`, `expired`,
   `multiple`, `unavailable`, `no_valid`, `withdrawn`; locales `en`/`zh`, themes
   `light`/`dark`. State exists only on `getApp().__dfaVerification`.
4. Use `automation_navigate`, `action=switchTab`,
   `url=/pages/analysis/index`. Unrelated Analysis requests receive synthetic503;
   this is deliberate and does not contact a backend.
5. Use `automation_page_action`, `action=callMethod`,
   `method=onObservedSectionChange`,
   `--args-file` containing `[{"currentTarget":{"dataset":{"value":"activities"}}}]`.
   The real activity-history component loads one synthetic running activity.
   Inspect with `action=querySelectorAll`, `selector=.activity-history__dfa`.
   If a page-state setup is needed, the registered alternative is
   `action=setData`, `patch='{"activeSection":"activities"}'` (patch is a JSON
   **string**, not an invented object argument).
6. Use `automation_element_action`, `action=tap`,
   `selector=.activity-history__dfa`, `waitForSelector=.activity-history__dfa`.
   With `prepare`, the real panel checks the recording, reaches source confirmation
   after two polls and starts unchecked. Tap the native checkbox then the confirm
   button; the same production handlers reach the synthetic complete result.
   Discover actual selectors with `automation_page_action querySelectorAll` rather
   than guessing or using desktop coordinates.
7. Read a bounded component state using `automation_evaluate`,
   `fnSource=<generated native-component-action.js>`, `--args-file` containing
   `["state"]`. For actions with a value, the file contains `[action,value]`. The fixture resolves the existing Skyline component by `#analysis-dfa`; it refuses
   any component whose activity ID is not `dfa-synthetic-running`. Controlled
   setup actions are `comparator` with0/1/2, `source-check` with a boolean,
   `confirm`, `revoke`, `delete`, `erase`, `cancel`, and `refresh`. Prefer registered
   element taps for gesture/accessibility verification; helper calls are state
   setup/diagnostics, not evidence that native touch interaction passed.
8. Capture via `simulator_screenshot`, `waitForSelector=dfa-analysis`,
   `optimize=false`; omitting `path` returns a temporary PNG at the tool-reported dimensions.
   Preserve that original without upscaling and record the logical viewport
   separately: this pass returned149×321 and192×413 captures for390×844 layouts.
   Copy only this synthetic output to the ignored
   `test-screenshots/ui-quality/dfa-alpha1/` evidence directory. Console
   diagnosis uses `get_simulator_console --command 'grep -i error'`. Review network
   only for synthetic paths; do not export an authenticated network archive.

## Required scenarios and teardown

- Complete: English/Chinese, light/dark, narrow mobile, no horizontal overflow;
  120 scheduled windows/page, visible gaps, true pause width, accessible values.
- Prepare: checkbox starts unchecked; explicit confirmation; close/reopen retains
  server state. No numerical result before source assurance.
- Expired: one retained proof and no cached run; opening makes **no POST**. Only
  pressing Analyse/Recalculate starts computation. Inspect only the synthetic
  `getApp().__dfaVerification.requests` method/path ledger if needed.
- Comparator: switch HR→Power/Pace; old dependent values clear while loading. The
  deterministic Node component test separately holds the context promise open.
- Withdrawn: numerical charts remain hidden, but the active owner job can cancel.
- Revoke/delete: scope is shown, confirmation required, result disappears and a
  refresh does not recreate work. The fixture itself never contacts SQL.

For each new fixture state, close the current panel, use registered
`automation_navigate action=reLaunch url=/pages/login/index` while mocks remain
active, and verify that runtime route before setup. Reinstall mocks if the
runtime restarted, apply `native-setup`, navigate to Analysis and re-enter
through the existing activity button. Inspect state and the actual PNG together;
reject any stale frame. Simple same-page fixture reset/reopen and some
post-action captures retained earlier frames in this tool version. Do not count
a fixture change as scientific activation or real-device validation.

At the end, close the panel (`automation_page_action callMethod onCloseDFA`), then
use `automation_navigate action=reLaunch url=/pages/login/index` while the
no-token storage/request mocks remain active. Verify the runtime route is
`pages/login/index`: `simulator_open_page` returning success alone did not prove
runtime navigation in the installed tool. Remove only `getApp().__dfaVerification` using controlled evaluate. Restore
`getStorageSync` and `request` with `automation_wx_api action=restore method=...`
when the runtime is idle. Do not clear personal storage, save tokens, upload,
preview, change AppID or trigger synchronization. Record any adapter/runtime
mismatch and stop the affected native pass; Node fixture tests do not prove the
installed simulator's mock transport or rendering behavior.
