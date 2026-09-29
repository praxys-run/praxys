# Synthetic native activity-detail verification

These fixtures are solely for Tencent's registered miniapp automator in an
authorized, task-owned DevTools project window. The activity ID
`native-synthetic-running` and all readings are synthetic. The request mock
intercepts every `wx.request`: before setup and for every unhandled path it
returns 503; no live API requests are forwarded. Storage reads are also
intercepted before navigation, so no real token is read. Do not take a screenshot
or inspect page data before **both** mocks are installed.

Follow `.github/skills/wechat-devtools/SKILL.md` and the installed Tencent
automator/debugger skill; recheck the installed tool version and arguments.
Pass each JS file as the `functionDeclaration`/`fnSource` string to the
registered `automation_wx_api`/`automation_evaluate` tools. The Windows CLI
requires a single-line declaration: normalize each source with the exported
`normalizeFixtureSource` from `web/scripts/prepare-dfa-native-fixtures.mjs`,
write the generated strings only under `/tmp`, and pass setup arguments using
`--args-file` (for example `["normal","zh","light"]`). Do not edit the
DevTools Windows mirror.

After installing `request` and `getStorageSync` mocks, call setup and navigate
to `/pages/activity-detail/index?id=native-synthetic-running`. Available states
are `normal`, `sparse`, `single_metric`, `distance_only`, `no_samples`,
`not_found`, `server_error`, and `network_error`. To switch state, relaunch the login page while
mocks remain installed, set up the new state, then navigate to detail again.
For `server_error`, the 503 stands in for a failed fetch; it does not prove a
transport-level offline callback. `network_error` throws a synthetic offline
request failure and must be confirmed in this Tencent tool version. Prefer registered element/touch tools for
interaction evidence, not programmatic handler calls.

To finish: return to the login page with mocks active, remove only
`getApp().__activityDetailVerification`, restore the two mocked wx APIs,
then close **only** the window opened for this task. Do not clear real storage,
export network archives, preview, upload, or contact a real account.
