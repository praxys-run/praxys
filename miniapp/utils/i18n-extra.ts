/**
 * Mini-program-local translation extras.
 *
 * The auto-synced `i18n-catalog.ts` only contains keys that web's source
 * tree marks for translation via lingui (`<Trans>` / `t\`...\``). Strings
 * unique to the mini program — login copy, switch-account modal,
 * tap-to-copy-URL hints, etc. — never get extracted on the web side and
 * therefore have no translations even though they're called via `t()`.
 *
 * Rather than hack the web catalog (which lingui-extract would clobber
 * on the next run) or hardcode locale switches throughout, we put them
 * here. `t()` in `i18n.ts` checks this map first, then falls through to
 * the auto-synced catalog, then falls back to the English key. So
 * lingui-driven strings stay single-sourced in web/, and mini-only
 * strings stay single-sourced here.
 *
 * Add a key only when:
 *   1. The string is genuinely mini-program-only (no equivalent on web)
 *   2. The key isn't already in `web/src/locales/zh/messages.po`
 *
 * Otherwise add the string to web's <Trans> usage and let the i18n
 * workflow translate it on the next run.
 *
 * The per-locale entries are split into per-section objects merged via
 * spread. Smaller object literals make duplicate-key bugs both easier to
 * spot when grepping AND impossible to land — adjacent sections live in
 * different objects, so any genuine duplicate is a clean spread-override
 * the section author can resolve, rather than a TS1117 surprise.
 */
import type { Locale } from './i18n-catalog';

// ---------------------------------------------------------------------------
// English passthroughs — keys map to themselves. Listing them keeps the
// typing symmetric and makes it obvious when a key was intentionally added
// here rather than pulled from web's lingui catalog.
// ---------------------------------------------------------------------------

const EN_AUTH = {
  // Legacy tagline retained for the share card / timeline copy and any
  // surface that still reads it. The login page itself uses the
  // canonical brand-guide tagline ("Sports science that meets you
  // where you are.") which is split into prefix/accent/suffix for the
  // green-accent rendering and lives in `buildLoginTr` rather than
  // here.
  'Train like a pro. Whatever your level.': 'Train like a pro. Whatever your level.',
  'Sign in with WeChat': 'Sign in with WeChat',
  'Signing you in…': 'Signing you in…',
  'Sign-in failed': 'Sign-in failed',
  'Sign-in code unavailable. Please try again.': 'Sign-in code unavailable. Please try again.',
  'WeChat sign-in is not configured on this server.': 'WeChat sign-in is not configured on this server.',
  'Your session expired. Please sign in again.': 'Your session expired. Please sign in again.',
  'Sign in to Praxys': 'Sign in to Praxys',
  'Link to Praxys': 'Link to Praxys',
  email: 'email',
  password: 'password',
  'Email and password are required': 'Email and password are required',
  // Old "Sign up at" footer copy retained for back-compat; the login
  // page itself now uses the explicit "New here?" / "Have an
  // invitation code?" rows below.
  'New here? Sign up at': 'New here? Sign up at',
  'New here?': 'New here?',
  'Have an invitation code?': 'Have an invitation code?',
  'Register on praxys.run': 'Register on praxys.run',
  'Then come back and sign in with WeChat above.':
    'Then come back and sign in with WeChat above.',
  'Back to sign in': 'Back to sign in',
  'tap to copy URL': 'tap to copy URL',
  'URL copied': 'URL copied',
  'Long press to save & share': 'Long press to save & share',
  Retry: 'Retry',
  OK: 'OK',
  Switch: 'Switch',
  Cancel: 'Cancel',
  'Switch Praxys account': 'Switch Praxys account',
  'Delete my account': 'Delete my account',
  'Delete my account?': 'Delete my account?',
  Delete: 'Delete',
  'Permanently remove your account, synced data, plans, settings, and encrypted credentials.':
    'Permanently remove your account, synced data, plans, settings, and encrypted credentials.',
  'This permanently deletes your Praxys account and training data. Type DELETE to confirm.':
    'This permanently deletes your Praxys account and training data. Type DELETE to confirm.',
  'Type DELETE here': 'Type DELETE here',
  'Type DELETE to confirm.': 'Type DELETE to confirm.',
  "Couldn't delete your account. Please try again or contact support if it keeps failing.":
    "Couldn't delete your account. Please try again or contact support if it keeps failing.",
  'Unlinking…': 'Unlinking…',
  // Login-page-only copy (waitlist + theme toggle aria + pillar copy).
  // These have no web equivalent — web's Login uses <Trans> on richer
  // JSX structures, while the miniapp builds plain-string segments
  // because Skyline can't render mid-string colour spans inside a
  // single text node.
  "Today's signal.": "Today's signal.",
  ' Go, modify, or rest.': ' Go, modify, or rest.',
  'Diagnosis & forecast': 'Diagnosis & forecast',
  ' you can verify.': ' you can verify.',
  'Cited science.': 'Cited science.',
  ' No hype.': ' No hype.',
  'Sub-3 marathon · 100K · stay healthy…': 'Sub-3 marathon · 100K · stay healthy…',
  // Waitlist success state — web's <Trans> bundles these into one
  // string with `<strong>` + mailto markup; the miniapp surfaces them
  // as a check + headline + detail trio so they need to live as
  // separate translatable keys.
  "You're on the list.": "You're on the list.",
  "We'll reach out from support@praxys.run when a slot opens.":
    "We'll reach out from support@praxys.run when a slot opens.",
  'Light theme': 'Light theme',
  'Dark theme': 'Dark theme',
  'System theme': 'System theme',
  // "Sync" the noun (sync source / button label) — separate from the
  // verb "Sync now". Mini program currently uses both interchangeably.
  Sync: 'Sync',
  'Sync now': 'Sync now',
  'Syncing…': 'Syncing…',
  'Sync started in the background.': 'Sync started in the background.',
  'Sync request failed. Try again from the web app if it persists.':
    'Sync request failed. Try again from the web app if it persists.',
  "Couldn't unlink your account on the server. Try again in a moment, or sign out instead and contact support if it keeps failing.":
    "Couldn't unlink your account on the server. Try again in a moment, or sign out instead and contact support if it keeps failing.",
};

const EN_GOAL = {
  'Use this': 'Use this',
  'Failed to switch theory': 'Failed to switch theory',
  'Change Goal': 'Change Goal',
  'Set Your Goal': 'Set Your Goal',
  'Goal type': 'Goal type',
  'Race Goal': 'Race Goal',
  'Train toward a specific race date': 'Train toward a specific race date',
  Continuous: 'Continuous',
  'Build fitness over time': 'Build fitness over time',
  Distance: 'Distance',
  'Race Date': 'Race Date',
  'Pick a date': 'Pick a date',
  'Target Time': 'Target Time',
  optional: 'optional',
  'Save Goal': 'Save Goal',
  'Saving…': 'Saving…',
  'Race date is required': 'Race date is required',
  'Invalid time format. Use H:MM:SS or H:MM': 'Invalid time format. Use H:MM:SS or H:MM',
  'Failed to save goal': 'Failed to save goal',
  '0:00:00 = no target time': '0:00:00 = no target time',
  'Leave blank to track predicted time only': 'Leave blank to track predicted time only',
  'What time are you working toward? Leave blank to track trend only':
    'What time are you working toward? Leave blank to track trend only',
  Comfortable: 'Comfortable',
  Stretch: 'Stretch',
  'Realistic targets': 'Realistic targets',
  'How this is calculated': 'How this is calculated',
  'Praxys Coach guidance': 'Praxys Coach guidance',
  "Today's recommendation is computed deterministically from your active recovery theory, recent training load, and scheduled workout. Praxys applies conservative product guardrails when fatigue or recovery signals conflict with the plan; these are coaching heuristics, not a medical diagnosis.": "Today's recommendation is computed deterministically from your active recovery theory, recent training load, and scheduled workout. Praxys applies conservative product guardrails when fatigue or recovery signals conflict with the plan; these are coaching heuristics, not a medical diagnosis.",
  'Copy source URL': 'Copy source URL',
  Predicted: 'Predicted',
  Target: 'Target',
  '+ Set target': '+ Set target',
  'CP trend': 'CP trend',
  Needed: 'Needed',
  Gap: 'Gap',
  'Source — tap to copy URL': 'Source — tap to copy URL',
  'Discussion — tap to copy URL': 'Discussion — tap to copy URL',
  'Ultra distance caveat': 'Ultra distance caveat',
  // Goal status badge values (API uses lowercase snake_case)
  on_track: 'On track',
  close: 'Close',
  behind: 'Behind',
  unlikely: 'Unlikely',
  unknown: '—',
  // Discard-edits modal
  'Discard changes?': 'Discard changes?',
  'Your goal edits will be lost.': 'Your goal edits will be lost.',
  Discard: 'Discard',
  'Keep editing': 'Keep editing',
  // Goal page science notes (default fallback when backend gives none)
  'Predicted using Stryd race power model (5K at 103.8% CP, marathon at 89.9% CP).':
    'Predicted using Stryd race power model (5K at 103.8% CP, marathon at 89.9% CP).',
  "Predicted using Riegel's formula (T₂ = T₁ × (D₂/D₁)^1.06), treating threshold pace as ~10K effort.":
    "Predicted using Riegel's formula (T₂ = T₁ × (D₂/D₁)^1.06), treating threshold pace as ~10K effort.",
  "Ultra distance power fractions (50K+) are estimates with limited research backing. Riegel's exponent is validated only up to marathon distance. Predictions beyond marathon carry significantly higher uncertainty due to factors like fueling, terrain, heat, and pacing strategy that dominate ultra performance but are not captured by power/pace models.":
    "Ultra distance power fractions (50K+) are estimates with limited research backing. Riegel's exponent is validated only up to marathon distance. Predictions beyond marathon carry significantly higher uncertainty due to factors like fueling, terrain, heat, and pacing strategy that dominate ultra performance but are not captured by power/pace models.",
  // Unified goal headline — one-sentence verdict rendered as plain text.
  // Web uses JSX <Trans> with <strong> spans; miniapp builds a plain string.
  '{0} days to race day. Today\'s prediction is {1} against a target of {2}.':
    '{0} days to race day. Today\'s prediction is {1} against a target of {2}.',
  '{0} days to race day. Today\'s prediction is {1}.':
    '{0} days to race day. Today\'s prediction is {1}.',
  'Building toward {0} {1}. Current {2} {3}{4}, need {5}{4}.':
    'Building toward {0} {1}. Current {2} {3}{4}, need {5}{4}.',
  'Building toward {0}. Current {1} {2}{3}, need {4}{3}.':
    'Building toward {0}. Current {1} {2}{3}, need {4}{3}.',
  'Today\'s {0} prediction is {1}. {2} is {3} at {4}.':
    'Today\'s {0} prediction is {1}. {2} is {3} at {4}.',
  'Today\'s {0} prediction is {1}. {2} is {3}.':
    'Today\'s {0} prediction is {1}. {2} is {3}.',
  '{0} is {1}. Add more activities for a race-time prediction.':
    '{0} is {1}. Add more activities for a race-time prediction.',
  // Strip cell labels — also in web zh catalog but mirrored here for EN completeness
  'Days left': 'Days left',
  'To target': 'To target',
  Direction: 'Direction',
  // Used as prefix in "current CP / current LTHR" strip labels
  current: 'current',
};

const EN_TODAY = {
  'Training base': 'Training base',
  Power: 'Power',
  'Heart rate': 'Heart rate',
  Pace: 'Pace',
  // Section heading for the warnings list. Lived in web's Today.tsx until
  // PR #238 redesigned the page and dropped the warnings block; miniapp's
  // pages/today still renders warnings, so the key lives here now.
  Warnings: 'Warnings',
  // Recovery status — must mirror RecoveryStatus in types/api.ts exactly.
  normal: 'Normal',
  fresh: 'Fresh',
  fatigued: 'Fatigued',
  insufficient_data: 'Insufficient data',
  // Volume trend values (volume.trend field in DiagnosisData)
  increasing: 'Increasing',
  decreasing: 'Decreasing',
  stable: 'Stable',
  'Weekly distance': 'Weekly distance',
  '{lookback}-week average · {average} km/week':
    '{lookback}-week average · {average} km/week',
  'What metric Praxys uses to measure intensity. Power needs Stryd; Pace works with anything that gives you GPS.':
    'What metric Praxys uses to measure intensity. Power needs Stryd; Pace works with anything that gives you GPS.',
  'Unbind your WeChat profile from this Praxys account so you can sign in as a different user.':
    'Unbind your WeChat profile from this Praxys account so you can sign in as a different user.',
  Splits: 'Splits',
  more: 'more',
  References: 'References',
  'Zone labels': 'Zone labels',
  'Currently using': 'Currently using',
  'latest estimate': 'latest estimate',
  'data points': 'data points',
  km: 'km',
  time: 'time',
  'avg W': 'avg W',
  'avg HR': 'avg HR',
  Peaked: 'Peaked',
  Fresh: 'Fresh',
  Neutral: 'Neutral',
  Fatigued: 'Fatigued',
  'Over-fatigued': 'Over-fatigued',
  'Zone distribution': 'Zone distribution',
  Rising: 'Rising',
  Falling: 'Falling',
  Flat: 'Flat',
  // Today / Training shared labels
  'Avg power': 'Avg power',
  'No data available yet.': 'No data available yet.',
  'No TSB data yet': 'No TSB data yet',
  HRV: 'HRV',
  'Upcoming workouts': 'Upcoming workouts',
  'Last activity': 'Last activity',
  Close: 'Close',
  // Today supporting-cell labels — technical handles, identical
  // across en/zh because they are the canonical short forms (web's
  // Today.tsx renders these as JSX literals for the same reason).
  'HRV (ln RMSSD)': 'HRV (ln RMSSD)',
  TSB: 'TSB',
  // Signal subtitles (Today page)
  'Follow Plan': 'Follow Plan',
  'Go Easy': 'Go Easy',
  'Adjust Workout': 'Adjust Workout',
  'Reduce Intensity': 'Reduce Intensity',
  'Recovery Day': 'Recovery Day',
  // Stale-data advisory. Mini program uses positional `{0}` placeholders
  // (tFmt) so the key differs from the web `{name}` form in
  // messages.po — this is the mini-only English passthrough used by
  // pages/today/index.ts:buildStalenessText.
  "Recovery data hasn't synced yet. Showing the latest reading from {0}.":
    "Recovery data hasn't synced yet. Showing the latest reading from {0}.",
  // Page-level data-staleness banner copy. Same shape as the web side
  // but uses positional `{0}` because tFmt only supports those.
  "Showing yesterday's snapshot. Last reading {0}.":
    "Showing yesterday's snapshot. Last reading {0}.",
  'No new HRV, sleep, or activity since.': 'No new HRV, sleep, or activity since.',
  'Show anyway': 'Show anyway',
  'From {0}': 'From {0}',
};

const EN_TRAINING = {
  'No training data yet. Sync Garmin / Stryd from the web app (Settings → Sync) to populate this view.':
    'No training data yet. Sync Garmin / Stryd from the web app (Settings → Sync) to populate this view.',
  Volume: 'Volume',
  'Weekly values': 'Weekly values',
  'Fitness & Fatigue': 'Fitness & Fatigue',
  Consistency: 'Consistency',
  Zones: 'Zones',
  Compliance: 'Compliance',
  'Long-term load (CTL)': 'Long-term load (CTL)',
  'Recent load (ATL)': 'Recent load (ATL)',
  'Load balance (TSB)': 'Load balance (TSB)',
  // Diagnosis section eyebrow — mini's reshape uses "Last N weeks"
  // as the right-hand context after the "DIAGNOSIS" label. Web's
  // Training surfaces "· last N weeks" inside a Trans block; mini
  // builds it from a positional template so the digit can be
  // interpolated without splitting the eyebrow into two text nodes.
  'Last {0} weeks': 'Last {0} weeks',
  // Training page interpolated copy
  '{0} km/week': '{0} km/week',
  'trend: {0}': 'trend: {0}',
  '{0} sessions · gaps ≥7d: {1} · longest: {2}d':
    '{0} sessions · gaps ≥7d: {1} · longest: {2}d',
  '{0} · {1}': '{0} · {1}',
  'Not included': 'Not included',
  "No recent activity reached the model's {0}-minute inclusion threshold.":
    "No recent activity reached the model's {0}-minute inclusion threshold.",
  '{0} · evidence': '{0} · evidence',
  '{current} / {target} days': '{current} / {target} days',
  '{current} / {target} min': '{current} / {target} min',
  'Likely-adapted threshold': 'Likely-adapted threshold',
  // Detail messages
  'Sync activities together with sleep data (Garmin, Oura, or similar) so we can pair them by date.':
    'Sync activities together with sleep data (Garmin, Oura, or similar) so we can pair them by date.',
  'Sync at least 2 weeks of data to compare planned vs actual training load.':
    'Sync at least 2 weeks of data to compare planned vs actual training load.',
  'Planned bars are estimated — your plan has no RSS targets for this base.':
    'Planned bars are estimated — your plan has no RSS targets for this base.',
};

// Praxys Coach receipt — progressive-disclosure toggle copy. Web's
// AiInsightsCard uses lingui ICU `{n, plural, one {# finding} other
// {# findings}}` blocks; mini's tFmt is positional only, so the noun
// stays plural at count=1 (minor grammar imperfection accepted in
// favour of simpler i18n).
const EN_COACH = {
  '{0} findings': '{0} findings',
  '{0} recommendations': '{0} recommendations',
  '{0} findings · {1} recommendations': '{0} findings · {1} recommendations',
};

const EN_HISTORY_SCIENCE = {
  // History page footers
  'Loading more…': 'Loading more…',
  'Tap to view {0} splits': 'Tap to view {0} splits',
  'End of activities': 'End of activities',
  '{0} total · showing {1}': '{0} total · showing {1}',
  // Science page intro / recommendation
  "Praxys's numbers come from published research. These are the theories currently powering your dashboard, plus the alternatives you could switch to on the web.":
    "Praxys's numbers come from published research. These are the theories currently powering your dashboard, plus the alternatives you could switch to on the web.",
  'Based on your training, we suggest': 'Based on your training, we suggest',
  'No active theory configured.': 'No active theory configured.',
  '{0} label sets available — switch on the web.':
    '{0} label sets available — switch on the web.',
};

const EN_SETTINGS = {
  Name: 'Name',
  // Unit system — must mirror UnitSystem in types/api.ts exactly.
  metric: 'Metric',
  imperial: 'Imperial',
  Connections: 'Connections',
  'Manage connections from the web app.': 'Manage connections from the web app.',
  "No platforms connected. Link Garmin / Stryd / Oura from the web app — their OAuth flows aren't supported in mini programs.":
    "No platforms connected. Link Garmin / Stryd / Oura from the web app — their OAuth flows aren't supported in mini programs.",
  'Auto-detected from synced fitness data; override on the web.':
    'Auto-detected from synced fitness data; override on the web.',
  'No thresholds yet. Sync Garmin / Stryd data to auto-detect CP, LTHR, and pace — or enter values manually on the web.':
    'No thresholds yet. Sync Garmin / Stryd data to auto-detect CP, LTHR, and pace — or enter values manually on the web.',
  'Browse the load / recovery / prediction / zone theories':
    'Browse the load / recovery / prediction / zone theories',
  'Open Praxys on web': 'Open Praxys on web',
  'Export my data on web': 'Export my data on web',
  'Data exports are downloaded from the Praxys web app.':
    'Data exports are downloaded from the Praxys web app.',
  'Open the web app to export your data.': 'Open the web app to export your data.',
  "This unlinks your WeChat profile from the current Praxys account. You'll be signed out and can sign in to a different account on next launch.":
    "This unlinks your WeChat profile from the current Praxys account. You'll be signed out and can sign in to a different account on next launch.",
  // Threshold labels
  CP: 'CP',
  LTHR: 'LTHR',
  'Threshold pace': 'Threshold pace',
  'Max HR': 'Max HR',
  'Resting HR': 'Resting HR',
  'from {0}': 'from {0}',
  // Feedback screenshot attachment (issue #337) — mini-only prompts.
  'Add a screenshot?': 'Add a screenshot?',
  'A screenshot helps us pinpoint the issue. It stays private.':
    'A screenshot helps us pinpoint the issue. It stays private.',
  'Add photo': 'Add photo',
  'Send without': 'Send without',
  'Image must be under 5 MB.': 'Image must be under 5 MB.',
  'Managed mode is off, but cleanup did not finish.':
    'Managed mode is off, but cleanup did not finish.',
  'Choose an available delivery platform':
    'Choose an available delivery platform',
  'Choose a delivery platform': 'Choose a delivery platform',
  'Connect an activity platform from the web app to choose where workouts are delivered.':
    'Connect an activity platform from the web app to choose where workouts are delivered.',
  Removed: 'Removed',
  Confirm: 'Confirm',
  'Keep future workouts': 'Keep future workouts',
  '{0} Praxys · {1} external': '{0} Praxys · {1} external',
  'Turn on': 'Turn on',
  'Individualized HRV evidence': 'Individualized HRV evidence',
  'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.':
    'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.',
  'Plews et al. (2012) source': 'Plews et al. (2012) source',
  'Kiviniemi et al. (2007) source': 'Kiviniemi et al. (2007) source',
};

const EN_NAV_CHARTS = {
  // Page titles (for nav-bar / custom-tab-bar)
  Today: 'Today',
  // Sleep perf metric label — API can return "Avg Pace" when base is pace
  'Avg Pace': 'Avg Pace',
  Training: 'Training',
  Activities: 'Activities',
  Goal: 'Goal',
  Settings: 'Settings',
  'Training Science': 'Training Science',
  'Training science': 'Training science',
  // Chart axis / series labels
  'Sleep Score': 'Sleep Score',
  'Sleep Score vs Avg Power': 'Sleep Score vs Avg Power',
  'Sleep Score vs {0}': 'Sleep Score vs {0}',
  'Avg Power': 'Avg Power',
  'Fitness (CTL)': 'Fitness (CTL)',
  'Fatigue (ATL)': 'Fatigue (ATL)',
  // Chart fallback messages
  'Not enough data': 'Not enough data',
  'No data': 'No data',
  // Scatter chart tooltip
  'Sleep {0} · {1}': 'Sleep {0} · {1}',
  // Mini-program-only Training-page strings — the web side has reworded
  // these into countdowns ("Need N more days") that need the
  // ``data_meta.data_days`` field, which the mini program's training pack
  // doesn't surface yet. Until the mini program adopts the countdown
  // wording, keep its existing messages here so check-i18n is happy.
  'Weekly Load Compliance': 'Weekly Load Compliance',
  'Not enough data for accurate fitness tracking': 'Not enough data for accurate fitness tracking',
  'Sync at least 6 weeks of activity data to see meaningful fitness, fatigue, and form curves.':
    'Sync at least 6 weeks of activity data to see meaningful fitness, fatigue, and form curves.',
  'Not enough data to show sleep vs performance':
    'Not enough data to show sleep vs performance',
  'Not enough data for weekly load comparison':
    'Not enough data for weekly load comparison',
};

const EN_HEAT = {
  '1 day ago': '1 day ago',
  '{0} days ago': '{0} days ago',
  '{formatted}: {included} included, {excluded} observed but not included, {minutes} effective min':
    '{formatted}: {included} included, {excluded} observed but not included, {minutes} effective min',
  'Power samples · {0}% coverage': 'Power samples · {0}% coverage',
  'Incomplete power samples · {0}% coverage': 'Incomplete power samples · {0}% coverage',
  Matched: 'Matched',
  Mismatch: 'Mismatch',
  Mixed: 'Mixed',
  Unverified: 'Unverified',
  'Observed, but not included because it stayed below {0} effective heat minutes.':
    'Observed, but not included because it stayed below {0} effective heat minutes.',
  '{0}°C · {1}% humidity': '{0}°C · {1}% humidity',
  '{0} · {1} humidity': '{0} · {1} humidity',
  '{0} effective min': '{0} effective min',
  'Select a day to inspect what entered the estimate.':
    'Select a day to inspect what entered the estimate.',
  'Based on {sessions} included sessions across {days} days in the last {window} days.':
    'Based on {sessions} included sessions across {days} days in the last {window} days.',
  '{0} included · {1} observed, not included':
    '{0} included · {1} observed, not included',
  '{0} days · {1} effective min': '{0} days · {1} effective min',
};

// ---------------------------------------------------------------------------
// Chinese translations — same key shape as the English passthroughs above,
// values translated.
// ---------------------------------------------------------------------------

const ZH_AUTH = {
  // Legacy share-card tagline (still consumed by share / timeline
  // copy). Login page proper uses the canonical brand-guide tagline
  // ("运动科学，知行合一。") split into prefix/accent/suffix in
  // `buildLoginTr`, which can't ride this catalog because each
  // segment must be its own coloured `<text>` node.
  'Train like a pro. Whatever your level.': '像专业选手一样训练，无论水平高低。',
  'Sign in with WeChat': '使用微信登录',
  'Signing you in…': '正在登录…',
  'Sign-in failed': '登录失败',
  'Sign-in code unavailable. Please try again.': '微信登录码暂不可用，请稍后重试。',
  'WeChat sign-in is not configured on this server.': '此服务器尚未配置微信登录。',
  'Your session expired. Please sign in again.': '会话已过期，请重新登录。',
  'Sign in to Praxys': '登录 Praxys',
  'Link to Praxys': '绑定 Praxys 账号',
  email: '邮箱',
  password: '密码',
  'Email and password are required': '请填写邮箱和密码',
  'New here? Sign up at': '没有账号？立即注册',
  'New here?': '没有账号？',
  'Have an invitation code?': '有邀请码？',
  'Register on praxys.run': '前往 praxys.run 注册',
  'Then come back and sign in with WeChat above.':
    '注册完成后，回到这里用微信登录。',
  'Back to sign in': '返回登录',
  'tap to copy URL': '点击复制链接',
  'URL copied': '链接已复制',
  'Long press to save & share': '长按保存并分享',
  Retry: '重试',
  OK: '好的',
  Switch: '切换',
  Cancel: '取消',
  'Switch Praxys account': '切换 Praxys 账号',
  'Delete my account': '删除账号',
  'Delete my account?': '删除账号？',
  Delete: '删除',
  'Permanently remove your account, synced data, plans, settings, and encrypted credentials.':
    '永久删除账号、已同步数据、计划、设置和加密凭据。',
  'This permanently deletes your Praxys account and training data. Type DELETE to confirm.':
    '这会永久删除 Praxys 账号和训练数据。输入 DELETE 确认。',
  'Type DELETE here': '在这里输入 DELETE',
  'Type DELETE to confirm.': '请输入 DELETE 确认。',
  "Couldn't delete your account. Please try again or contact support if it keeps failing.":
    '账号删除失败。请重试；如持续失败，请联系客服。',
  'Unlinking…': '正在解绑…',
  // Login-page-only zh copy. Omit second-person pronouns where natural;
  // use 你 rather than the overly formal 您 when one is needed.
  "Today's signal.": '今日信号。',
  ' Go, modify, or rest.': '按计划训练、调整或休息。',
  'Diagnosis & forecast': '诊断与预测',
  ' you can verify.': '经得起验证。',
  'Cited science.': '科学有据。',
  ' No hype.': '不靠噱头。',
  'Sub-3 marathon · 100K · stay healthy…': '全马破三 · 100K · 保持健康…',
  "You're on the list.": '你已进入候补名单。',
  "We'll reach out from support@praxys.run when a slot opens.":
    '有名额时，我们会通过 support@praxys.run 联系你。',
  'Light theme': '浅色主题',
  'Dark theme': '深色主题',
  'System theme': '跟随系统',
  Sync: '同步',
  'Sync now': '立即同步',
  'Syncing…': '同步中…',
  'Sync started in the background.': '已开始后台同步。',
  'Sync request failed. Try again from the web app if it persists.':
    '同步请求失败。如持续失败，请在网页端再试。',
  "Couldn't unlink your account on the server. Try again in a moment, or sign out instead and contact support if it keeps failing.":
    '服务器解绑失败。请稍后重试；如持续失败，请改为退出登录并联系客服。',
};

const ZH_GOAL = {
  'Use this': '使用此理论',
  'Failed to switch theory': '切换理论失败',
  'Change Goal': '调整目标',
  'Set Your Goal': '设置目标',
  'Goal type': '目标类型',
  'Race Goal': '比赛目标',
  'Train toward a specific race date': '围绕某场比赛备赛',
  Continuous: '持续提升',
  'Build fitness over time': '长期提升体能',
  Distance: '距离',
  'Race Date': '比赛日期',
  'Pick a date': '选择日期',
  'Target Time': '目标完赛时间',
  optional: '选填',
  'Save Goal': '保存目标',
  'Saving…': '保存中…',
  'Race date is required': '请填写比赛日期',
  'Invalid time format. Use H:MM:SS or H:MM': '时间格式无效。请使用 H:MM:SS 或 H:MM',
  'Failed to save goal': '保存目标失败',
  '0:00:00 = no target time': '0:00:00 = 不设目标时间',
  'Leave blank to track predicted time only': '留空则只追踪预测完赛时间',
  'What time are you working toward? Leave blank to track trend only':
    '目标完赛时间是多少？留空则只追踪趋势',
  Comfortable: '稳妥目标',
  Stretch: '挑战目标',
  'Realistic targets': '可行的目标',
  'How this is calculated': '计算方式',
  'Praxys Coach guidance': 'Praxys Coach 建议',
  "Today's recommendation is computed deterministically from your active recovery theory, recent training load, and scheduled workout. Praxys applies conservative product guardrails when fatigue or recovery signals conflict with the plan; these are coaching heuristics, not a medical diagnosis.": '今日建议根据当前恢复理论、近期训练负荷和计划训练按固定规则生成。当疲劳或恢复信号与计划冲突时，Praxys 会采用保守的保护规则。这些只是训练建议，不是医学诊断。',
  'Copy source URL': '复制来源链接',
  Predicted: '预计',
  Target: '目标',
  '+ Set target': '+ 设置目标',
  'CP trend': 'CP 趋势',
  Needed: '所需',
  Gap: '差距',
  'Source — tap to copy URL': '来源：轻触复制链接',
  'Discussion — tap to copy URL': '说明：轻触复制链接',
  'Ultra distance caveat': '超长距离说明',
  // Goal status badge values (lowercase API keys)
  on_track: '达标',
  close: '接近',
  behind: '落后',
  unlikely: '难以实现',
  unknown: '—',
  // Discard-edits modal
  'Discard changes?': '放弃修改？',
  'Your goal edits will be lost.': '当前修改将不会保存。',
  Discard: '放弃',
  'Keep editing': '继续编辑',
  // Science notes
  'Predicted using Stryd race power model (5K at 103.8% CP, marathon at 89.9% CP).':
    '按 Stryd 比赛功率模型预测（5K 取 103.8% CP，马拉松取 89.9% CP）。',
  "Predicted using Riegel's formula (T₂ = T₁ × (D₂/D₁)^1.06), treating threshold pace as ~10K effort.":
    '按 Riegel 公式预测（T₂ = T₁ × (D₂/D₁)^1.06），将阈值配速近似视为 10K 比赛强度。',
  "Ultra distance power fractions (50K+) are estimates with limited research backing. Riegel's exponent is validated only up to marathon distance. Predictions beyond marathon carry significantly higher uncertainty due to factors like fueling, terrain, heat, and pacing strategy that dominate ultra performance but are not captured by power/pace models.":
    '50K 及以上超长距离的功率比例为估算值，目前研究支持有限。Riegel 指数仅验证到马拉松距离。超过马拉松的预测不确定性会明显升高，因为补给、地形、高温和配速策略等因素对超马表现影响更大，而这些并未被功率/配速模型纳入。',
  // Unified goal headline zh translations
  '{0} days to race day. Today\'s prediction is {1} against a target of {2}.':
    '距比赛日还有 {0} 天。今日预测 {1}，目标 {2}。',
  '{0} days to race day. Today\'s prediction is {1}.':
    '距比赛日还有 {0} 天。今日预测 {1}。',
  'Building toward {0} {1}. Current {2} {3}{4}, need {5}{4}.':
    '目标是 {1} {0} 完赛。当前 {2} 为 {3}{4}，还需达到 {5}{4}。',
  'Building toward {0}. Current {1} {2}{3}, need {4}{3}.':
    '以 {0} 为目标。当前 {1} 为 {2}{3}，还需达到 {4}{3}。',
  'Today\'s {0} prediction is {1}. {2} is {3} at {4}.':
    '今日 {0} 预计成绩为 {1}。{2} 呈 {3}趋势，变化速率为 {4}。',
  'Today\'s {0} prediction is {1}. {2} is {3}.':
    '今日 {0} 预计成绩为 {1}。{2} 呈 {3}趋势。',
  '{0} is {1}. Add more activities for a race-time prediction.':
    '{0} 呈 {1}趋势。再同步一些活动，即可生成比赛时间预测。',
  'Days left': '剩余天数',
  'To target': '距目标',
  Direction: '趋势方向',
  current: '当前',
};

const ZH_TODAY = {
  'Training base': '训练基准',
  Power: '功率',
  'Heart rate': '心率',
  Pace: '配速',
  Warnings: '警告',
  // Recovery status — must mirror RecoveryStatus in types/api.ts exactly.
  normal: '正常',
  fresh: '恢复良好',
  fatigued: '疲劳',
  insufficient_data: '数据不足',
  // Volume trend values (volume.trend field in DiagnosisData)
  increasing: '上升中',
  decreasing: '下降中',
  stable: '平稳',
  'Weekly distance': '周里程',
  '{lookback}-week average · {average} km/week':
    '近 {lookback} 周平均 · {average} 公里/周',
  'What metric Praxys uses to measure intensity. Power needs Stryd; Pace works with anything that gives you GPS.':
    'Praxys 用这个指标衡量训练强度。功率需使用 Stryd；只要设备支持 GPS，即可使用配速。',
  'Unbind your WeChat profile from this Praxys account so you can sign in as a different user.':
    '解除微信与当前 Praxys 账号的绑定，以便切换到其他账号。',
  Splits: '分段',
  more: '更多',
  References: '参考文献',
  'Zone labels': '区间标签',
  'Currently using': '当前使用',
  'latest estimate': '最新估算',
  'data points': '个数据点',
  km: '公里',
  time: '时间',
  'avg W': '平均功率',
  'avg HR': '平均心率',
  Peaked: '巅峰状态',
  Fresh: '状态良好',
  Neutral: '状态平衡',
  Fatigued: '疲劳',
  'Over-fatigued': '过度疲劳',
  'Zone distribution': '区间分布',
  Rising: '上升',
  Falling: '下降',
  Flat: '持平',
  'Avg power': '平均功率',
  'No data available yet.': '暂无数据。',
  'No TSB data yet': '暂无负荷平衡（TSB）数据',
  HRV: 'HRV',
  'Upcoming workouts': '计划训练',
  'Last activity': '最近活动',
  Close: '关闭',
  // Today supporting-cell technical handles — kept untranslated so
  // the cell label matches what the user reads on the web Today
  // page. The cell value below the label disambiguates anyway
  // (today_ln value, signed TSB, etc.).
  'HRV (ln RMSSD)': 'HRV (ln RMSSD)',
  TSB: 'TSB',
  // Signal subtitles
  'Follow Plan': '按计划训练',
  'Go Easy': '轻松训练',
  'Adjust Workout': '调整训练',
  'Reduce Intensity': '降低强度',
  'Recovery Day': '恢复日',
  // Stale-data advisory. `{0}` is the localized reading-date chip
  // ("Apr 24" / "4月24日") supplied by tFmt.
  "Recovery data hasn't synced yet. Showing the latest reading from {0}.":
    '恢复数据尚未同步，当前显示最近一次读数（{0}）。',
  // Page-level data-staleness banner — anchored on data_as_of timestamp.
  // `{0}` is the localized "Sat 9:00 PM" / "周六 21:00" stamp.
  "Showing yesterday's snapshot. Last reading {0}.":
    '显示的是昨天的快照。最近一次读数 {0}。',
  'No new HRV, sleep, or activity since.': '此后无新的 HRV、睡眠或活动数据。',
  'Show anyway': '仍要查看',
  'From {0}': '数据截至 {0}',
};

const ZH_TRAINING = {
  'No training data yet. Sync Garmin / Stryd from the web app (Settings → Sync) to populate this view.':
    '暂无训练数据。请先在网页端的“设置 → 同步”中同步 Garmin / Stryd 数据。',
  Volume: '里程',
  'Weekly values': '每周数据',
  'Fitness & Fatigue': '体能与疲劳',
  Consistency: '训练频率',
  Zones: '区间',
  Compliance: '计划完成度',
  'Long-term load (CTL)': '长期负荷（CTL）',
  'Recent load (ATL)': '短期负荷（ATL）',
  'Load balance (TSB)': '负荷平衡（TSB）',
  'Last {0} weeks': '近 {0} 周',
  '{0} km/week': '{0} 公里/周',
  'trend: {0}': '趋势：{0}',
  '{0} sessions · gaps ≥7d: {1} · longest: {2}d':
    '{0} 次训练 · ≥7 天间隔：{1} 次 · 最长间隔：{2} 天',
  '{0} · {1}': '{0} · {1}',
  'Not included': '未纳入',
  "No recent activity reached the model's {0}-minute inclusion threshold.":
    '近期没有活动达到模型设定的 {0} 分钟纳入阈值。',
  '{0} · evidence': '{0} · 依据',
  '{current} / {target} days': '{current} / {target} 天',
  '{current} / {target} min': '{current} / {target} 分钟',
  'Likely-adapted threshold': '“可能已适应”阈值',
  'Sync activities together with sleep data (Garmin, Oura, or similar) so we can pair them by date.':
    '同时同步活动与睡眠数据（Garmin、Oura 或类似设备），以便按日期匹配。',
  'Sync at least 2 weeks of data to compare planned vs actual training load.':
    '至少同步 2 周数据，即可对比计划与实际训练负荷。',
  'Planned bars are estimated — your plan has no RSS targets for this base.':
    '计划负荷柱为估算值——当前训练基准下，训练计划未设置 RSS 目标。',
};

const ZH_COACH = {
  '{0} findings': '{0} 个要点',
  '{0} recommendations': '{0} 条建议',
  '{0} findings · {1} recommendations': '{0} 个要点 · {1} 条建议',
};

const ZH_HISTORY_SCIENCE = {
  'Loading more…': '正在加载更多…',
  'Tap to view {0} splits': '轻触查看 {0} 个分段',
  'End of activities': '已加载全部活动',
  '{0} total · showing {1}': '共 {0} 条 · 当前显示 {1}',
  "Praxys's numbers come from published research. These are the theories currently powering your dashboard, plus the alternatives you could switch to on the web.":
    'Praxys 的各项数据均有已发表研究作为依据。下面列出当前用于生成主页数据的理论，以及可在网页端切换的其他理论。',
  'Based on your training, we suggest': '根据近期训练，我们建议',
  'No active theory configured.': '尚未启用任何理论。',
  '{0} label sets available — switch on the web.':
    '共有 {0} 套区间标签方案，可在网页端切换。',
};

const ZH_SETTINGS = {
  Name: '姓名',
  // Unit system — must mirror UnitSystem in types/api.ts exactly.
  metric: '公制',
  imperial: '英制',
  Connections: '已连接平台',
  'Manage connections from the web app.': '已连接平台请前往网页端管理。',
  "No platforms connected. Link Garmin / Stryd / Oura from the web app — their OAuth flows aren't supported in mini programs.":
    '尚未连接平台。请前往网页端连接 Garmin / Stryd / Oura；小程序暂不支持这些平台的 OAuth 授权。',
  'Auto-detected from synced fitness data; override on the web.':
    '根据已同步的体能数据自动识别；如需调整，请前往网页端。',
  'No thresholds yet. Sync Garmin / Stryd data to auto-detect CP, LTHR, and pace — or enter values manually on the web.':
    '暂无阈值数据。同步 Garmin / Stryd 后可自动识别 CP、LTHR 和阈值配速，也可在网页端手动填写。',
  'Browse the load / recovery / prediction / zone theories': '浏览负荷、恢复、预测和区间理论',
  'Open Praxys on web': '在网页端打开 Praxys',
  'Export my data on web': '在网页端导出我的数据',
  'Data exports are downloaded from the Praxys web app.':
    '请在 Praxys 网页端下载数据导出文件。',
  'Open the web app to export your data.': '请在网页端导出数据。',
  "This unlinks your WeChat profile from the current Praxys account. You'll be signed out and can sign in to a different account on next launch.":
    '这会解除微信与当前 Praxys 账号的绑定并退出登录。下次打开时可登录其他账号。',
  // Threshold labels — preferred zh terminology per project conventions.
  CP: '阈值功率 (CP)',
  LTHR: 'LTHR',
  'Threshold pace': '阈值配速',
  'Max HR': '最大心率',
  'Resting HR': '静息心率',
  'from {0}': '来源：{0}',
  // Feedback screenshot attachment (issue #337) — mini-only prompts.
  'Add a screenshot?': '添加截图？',
  'A screenshot helps us pinpoint the issue. It stays private.':
    '截图有助于我们更快定位问题，仅供内部查看。',
  'Add photo': '添加图片',
  'Send without': '直接发送',
  'Image must be under 5 MB.': '图片不得超过 5 MB。',
  'Managed mode is off, but cleanup did not finish.':
    '托管模式已关闭，但清理未完成。',
  'Choose an available delivery platform': '请选择可用的训练下发平台',
  'Choose a delivery platform': '选择训练下发平台',
  'Connect an activity platform from the web app to choose where workouts are delivered.':
    '请先在网页端连接活动平台，再选择训练下发位置。',
  Removed: '已移除',
  Confirm: '确认',
  'Keep future workouts': '保留未来训练',
  '{0} Praxys · {1} external': 'Praxys 训练 {0} 个 · 外部训练 {1} 个',
  'Turn on': '启用',
  'Individualized HRV evidence': '个体化 HRV 依据',
  'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.':
    'Praxys 采用 Plews 等（2012）和 Kiviniemi 等（2007）的个体化 HRV 训练指导。具体警戒区间与改为休息日的规则属于保守的产品估算，并非诊断或经临床验证的处方。',
  'Plews et al. (2012) source': 'Plews 等（2012）来源',
  'Kiviniemi et al. (2007) source': 'Kiviniemi 等（2007）来源',
};

const ZH_NAV_CHARTS = {
  Today: '今日',
  'Avg Pace': '平均配速',
  Training: '训练',
  Activities: '活动',
  Goal: '目标',
  Settings: '设置',
  'Training Science': '训练科学',
  'Training science': '训练科学',
  'Sleep Score': '睡眠评分',
  'Sleep Score vs Avg Power': '睡眠评分与平均功率',
  'Sleep Score vs {0}': '睡眠评分与{0}',
  'Avg Power': '平均功率',
  'Fitness (CTL)': '体能（CTL）',
  'Fatigue (ATL)': '疲劳（ATL）',
  'Not enough data': '数据不足',
  'No data': '暂无数据',
  'Sleep {0} · {1}': '睡眠 {0} · {1}',
  // Mini-program-only Training-page strings — see EN_NAV_CHARTS for context.
  'Weekly Load Compliance': '周训练负荷完成度',
  'Not enough data for accurate fitness tracking': '数据不足，暂无法准确跟踪体能',
  'Sync at least 6 weeks of activity data to see meaningful fitness, fatigue, and form curves.':
    '至少同步 6 周活动数据，才能查看有参考价值的体能、疲劳和状态曲线。',
  'Not enough data to show sleep vs performance':
    '数据不足，暂无法显示睡眠与表现的关系',
  'Not enough data for weekly load comparison':
    '数据不足，暂无法对比每周负荷',
};

const ZH_HEAT = {
  '1 day ago': '1 天前',
  '{0} days ago': '{0} 天前',
  '{formatted}: {included} included, {excluded} observed but not included, {minutes} effective min':
    '{formatted}：纳入 {included} 次，已记录但未纳入 {excluded} 次，等效热暴露 {minutes} 分钟',
  'Power samples · {0}% coverage': '功率数据点 · 覆盖率 {0}%',
  'Incomplete power samples · {0}% coverage': '功率数据点不完整 · 覆盖率 {0}%',
  Matched: '匹配',
  Mismatch: '不匹配',
  Mixed: '混合',
  Unverified: '未验证',
  'Observed, but not included because it stayed below {0} effective heat minutes.':
    '已记录，但未纳入，因为等效热暴露时长未达到 {0} 分钟。',
  '{0}°C · {1}% humidity': '{0}°C · 湿度 {1}%',
  '{0} · {1} humidity': '{0} · 湿度 {1}',
  '{0} effective min': '等效热暴露 {0} 分钟',
  'Select a day to inspect what entered the estimate.':
    '选择一天，查看当天哪些训练被纳入估算。',
  'Based on {sessions} included sessions across {days} days in the last {window} days.':
    '基于过去 {window} 天内纳入的 {sessions} 次训练，分布在 {days} 个训练日。',
  '{0} included · {1} observed, not included':
    '纳入 {0} 次 · 已记录但未纳入 {1} 次',
  '{0} days · {1} effective min': '{0} 天 · 等效热暴露 {1} 分钟',
};

const EN_LABS = {
  'Praxys is checking Stryd provenance, fitting the aggregate model, and applying every release guardrail.':
    'Praxys is checking Stryd provenance, fitting the aggregate model, and applying every release guardrail.',
  'Relative modeled HR': 'Relative modeled HR',
  'Lower interval': 'Lower interval',
  'Upper interval': 'Upper interval',
  'minimum 5 per range': 'minimum 5 per range',
  activities: 'activities',
  'This sits inside your displayed historical range.':
    'This sits inside your displayed historical range.',
  'This is a psychrometric estimate—not apparent temperature, outdoor WBGT, body temperature, or a heat-safety assessment.':
    'This is a psychrometric estimate—not apparent temperature, outdoor WBGT, body temperature, or a heat-safety assessment.',
  'Network error. Try again.': 'Network error. Try again.',
  'Enter numeric temperature and humidity values.':
    'Enter numeric temperature and humidity values.',
  'Copy failed': 'Copy failed',
  'Explore voluntary experiments on your own training history':
    'Explore voluntary experiments on your own training history',
  'This curve is historical and non-causal. Wind, solar load, clothing, hydration, fatigue, and other unmeasured conditions can still differ between runs.':
    'This curve is historical and non-causal. Wind, solar load, clothing, hydration, fatigue, and other unmeasured conditions can still differ between runs.',
  'Stull (2011) source': 'Stull (2011) source',
};

const ZH_LABS = {
  'Praxys is checking Stryd provenance, fitting the aggregate model, and applying every release guardrail.':
    'Praxys 正在检查 Stryd 数据来源、拟合汇总模型，并应用全部发布门槛。',
  'Relative modeled HR': '相对模型心率',
  'Lower interval': '区间下界',
  'Upper interval': '区间上界',
  'minimum 5 per range': '每个区间至少 5 次',
  activities: '次活动',
  'This sits inside your displayed historical range.':
    '该值位于已显示的历史范围内。',
  'This is a psychrometric estimate—not apparent temperature, outdoor WBGT, body temperature, or a heat-safety assessment.':
    '这是干湿球湿球温度估算值，不是体感温度、室外 WBGT、体温或高温安全评估。',
  'Network error. Try again.': '网络错误，请重试。',
  'Enter numeric temperature and humidity values.':
    '请输入有效的温度和湿度数值。',
  'Copy failed': '复制失败',
  'Explore voluntary experiments on your own training history':
    '探索基于个人训练历史的自愿实验',
  'This curve is historical and non-causal. Wind, solar load, clothing, hydration, fatigue, and other unmeasured conditions can still differ between runs.':
    '此曲线仅表示历史关联，并不代表因果关系。不同跑步之间的风、太阳辐射、衣着、补水、疲劳和其他未测量条件仍可能不同。',
  'Stull (2011) source': 'Stull（2011）来源',
};

const EN_LEGAL = {
  // Legal / consent surfaces: the Terms & Privacy viewer (pages/legal) and the
  // login-page consent notices. Full page titles stay bracket-free; the short
  // doc names pick up 《》 in zh at the login call site (Chinese convention for
  // a cited document title), so they aren't decorated here.
  'Terms of Service': 'Terms of Service',
  'Terms of Service & EULA': 'Terms of Service & EULA',
  'Privacy Policy': 'Privacy Policy',
  'Effective': 'Effective',
  'Copied': 'Copied',
  'By signing in, you agree to our': 'By signing in, you agree to our',
  'I agree to the': 'I agree to the',
  'Please agree to the Terms and Privacy Policy first.':
    'Please agree to the Terms and Privacy Policy first.',
};

const ZH_LEGAL = {
  'Terms of Service': '服务条款',
  'Terms of Service & EULA': '服务条款与最终用户许可协议',
  'Privacy Policy': '隐私政策',
  'Effective': '生效日期',
  'Copied': '已复制',
  'By signing in, you agree to our': '登录即表示已阅读并同意',
  'I agree to the': '我已阅读并同意',
  'Please agree to the Terms and Privacy Policy first.':
    '请先阅读并同意《服务条款》与《隐私政策》。',
};

export const I18N_EXTRA: Record<Locale, Record<string, string>> = {
  en: {
    ...EN_AUTH,
    ...EN_GOAL,
    ...EN_TODAY,
    ...EN_TRAINING,
    ...EN_COACH,
    ...EN_HISTORY_SCIENCE,
    ...EN_SETTINGS,
    ...EN_NAV_CHARTS,
    ...EN_HEAT,
    ...EN_LABS,
    ...EN_LEGAL,
  },
  zh: {
    ...ZH_AUTH,
    ...ZH_GOAL,
    ...ZH_TODAY,
    ...ZH_TRAINING,
    ...ZH_COACH,
    ...ZH_HISTORY_SCIENCE,
    ...ZH_SETTINGS,
    ...ZH_NAV_CHARTS,
    ...ZH_HEAT,
    ...ZH_LABS,
    ...ZH_LEGAL,
  },
};
