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
  'Hide routing explanation': 'Hide routing explanation',
  'This client does not recognize the selected policy input contract and will not guess how to create a plan.':
    'This client does not recognize the selected policy input contract and will not guess how to create a plan.',
  'Use this': 'Use this',
  'Failed to switch theory': 'Failed to switch theory',
  'Change Goal': 'Change Goal',
  'Set Your Goal': 'Set Your Goal',
  'Goal type': 'Goal type',
  'Race Goal': 'Race Goal',
  'Train toward a specific race date': 'Train toward a specific race date',
  Continuous: 'Continuous',
  'Build fitness over time': 'Build fitness over time',
  '10K performance': '10K performance',
  'Optional benchmark': 'Optional benchmark',
  'Choose and date an optional benchmark only if you want one. Praxys never auto-schedules it.':
    'Choose and date an optional benchmark only if you want one. Praxys never auto-schedules it.',
  'This proposal uses an accepted goal contract without changing or linking to the Goal page.':
    'This proposal uses an accepted goal contract without changing or linking to the Goal page.',
  'Tell Praxys if a current symptom stop applies. The policy will stop this plan path and return only bounded guidance.':
    'Tell Praxys if a current symptom stop applies. The policy will stop this plan path and return only bounded guidance.',
  'Only current direct 10K race or explicit all-out 10K history can qualify.':
    'Only current direct 10K race or explicit all-out 10K history can qualify.',
  'The {0}-day rule is a reviewed guardrail, not a physiological cutoff.':
    'The {0}-day rule is a reviewed guardrail, not a physiological cutoff.',
  'Only current direct 10K race or explicit all-out 10K history can qualify. Qualification keeps the accepted protocol, route or venue, assistance status, provider, and authoritative completion time attached to the evidence. The {0}-day freshness guardrail and the optional benchmark path are reviewed product boundaries, not published universal cutoffs.':
    'Only current direct 10K race or explicit all-out 10K history can qualify. Qualification keeps the accepted protocol, route or venue, assistance status, provider, and authoritative completion time attached to the evidence. The {0}-day freshness guardrail and the optional benchmark path are reviewed product boundaries, not published universal cutoffs.',
  'Full activity only.': 'Full activity only.',
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
  'Choose a synced activity': 'Choose a synced activity',
  'Did you follow the exact protocol?': 'Did you follow the exact protocol?',
  'Stop reason': 'Stop reason',
  'No synced candidate is available yet.': 'No synced candidate is available yet.',
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

const EN_ROAD_10K = {
  'Review invitation': 'Review invitation',
  'Not now': 'Not now',
  'Leave rollout': 'Leave rollout',
  'Continue to sign in': 'Continue to sign in',
  'Rollout status: On hold': 'Rollout status: On hold',
  'Rollout status: Paused': 'Rollout status: Paused',
  'Rollout status: Ended': 'Rollout status: Ended',
  'Rollout status: Left rollout': 'Rollout status: Left rollout',
  'Your proposal will become read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.':
    'Your proposal will become read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.',
  'You left the Road 10K rollout. Your proposal is read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.':
    'You left the Road 10K rollout. Your proposal is read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.',
  'Your rollout access ended': 'Your rollout access ended',
  'Your proposal, if any, is now a read-only receipt and cannot be adopted or regenerated. An adopted plan is unchanged and remains manageable in Training.':
    'Your proposal, if any, is now a read-only receipt and cannot be adopted or regenerated. An adopted plan is unchanged and remains manageable in Training.',
  'Join rollout': 'Join rollout',
  'Join the Road 10K rollout?': 'Join the Road 10K rollout?',
  'This is a limited, default-off process pilot for one deterministic 14-day outdoor road 10K proposal. Joining the rollout does not create or adopt a plan.':
    'This is a limited, default-off process pilot for one deterministic 14-day outdoor road 10K proposal. Joining the rollout does not create or adopt a plan.',
  'Praxys checks your existing Goal, direct 10K baseline, recent running history, and confirmed scheduling constraints under the accepted Road 10K rules.':
    'Praxys checks your existing Goal, direct 10K baseline, recent running history, and confirmed scheduling constraints under the accepted Road 10K rules.',
  'This does not promise faster performance, injury prevention, medical safety, diagnosis, treatment, clearance, or a personal result.':
    'This does not promise faster performance, injury prevention, medical safety, diagnosis, treatment, clearance, or a personal result.',
  'No AI chooses or adopts the plan. Nothing is sent to a training provider. Nothing changes until you explicitly adopt the exact proposal.':
    'No AI chooses or adopts the plan. Nothing is sent to a training provider. Nothing changes until you explicitly adopt the exact proposal.',
  'The exact data used, access roles, retention, private feedback handling, export, and deletion terms appear in the current data notice below.':
    'The exact data used, access roles, retention, private feedback handling, export, and deletion terms appear in the current data notice below.',
  'You can leave the rollout, export your data, or delete your account. Leaving the rollout does not pause or end an adopted plan.':
    'You can leave the rollout, export your data, or delete your account. Leaving the rollout does not pause or end an adopted plan.',
  'I understand and want to join this Road 10K rollout.':
    'I understand and want to join this Road 10K rollout.',
  'Try a Road 10K plan proposal': 'Try a Road 10K plan proposal',
  'You’re invited to a limited process pilot. Joining lets Praxys check whether it can create one deterministic 14-day outdoor road 10K proposal for you. Joining does not create or adopt a plan.':
    'You’re invited to a limited process pilot. Joining lets Praxys check whether it can create one deterministic 14-day outdoor road 10K proposal for you. Joining does not create or adopt a plan.',
  'Rollout status: Enrolled': 'Rollout status: Enrolled',
  'Plan status: No Road 10K plan': 'Plan status: No Road 10K plan',
  'No Road 10K proposal has been created. Check the current status to continue.':
    'No Road 10K proposal has been created. Check the current status to continue.',
  'Screenshots are unavailable until private deletion and restore handling are verified.':
    'Screenshots are unavailable until private deletion and restore handling are verified.',
  'Joining the Road 10K rollout…': 'Joining the Road 10K rollout…',
  'Praxys could not complete this action. Nothing changed.':
    'Praxys could not complete this action. Nothing changed.',
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
  'What metric Praxys uses to measure intensity. Power needs a compatible running-power source; Pace works with GPS activity data.':
    'What metric Praxys uses to measure intensity. Power needs a compatible running-power source; Pace works with GPS activity data.',
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
  'Add step': 'Add step',
  'Add repeat': 'Add repeat',
  'Compare other providers': 'Compare other providers',
  'Delivery blocked': 'Delivery blocked',
  'No training data yet. Sync a connected platform from the web app (Settings → Sync) to populate this view.':
    'No training data yet. Sync a connected platform from the web app (Settings → Sync) to populate this view.',
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
  'No platforms connected. Manage supported connections from the web app.':
    'No platforms connected. Manage supported connections from the web app.',
  'Auto-detected from synced fitness data; override on the web.':
    'Auto-detected from synced fitness data; override on the web.',
  'No thresholds yet. Sync fitness data to auto-detect CP, LTHR, and pace — or enter values manually on the web.':
    'No thresholds yet. Sync fitness data to auto-detect CP, LTHR, and pace — or enter values manually on the web.',
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
  '{removed} deliveries are clear; {remaining} still need review before the target can change.':
    '{removed} deliveries are clear; {remaining} still need review before the target can change.',
  'Turn on': 'Turn on',
  'Individualized HRV evidence': 'Individualized HRV evidence',
  'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.':
    'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.',
  'Plews et al. (2012) source': 'Plews et al. (2012) source',
  'Kiviniemi et al. (2007) source': 'Kiviniemi et al. (2007) source',
};

const EN_ME = {
  Me: 'Me',
  'Observed training': 'Observed training',
  'Account & data': 'Account & data',
  'Connections, thresholds, plan delivery, preferences, and account access.':
    'Connections, thresholds, plan delivery, preferences, and account access.',
  Explore: 'Explore',
  Experimental: 'Experimental',
  About: 'About',
  'Terms & Privacy': 'Terms & Privacy',
  'Legal documents, privacy, and data rights.':
    'Legal documents, privacy, and data rights.',
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
  'Hide routing explanation': '收起路径说明',
  'This client does not recognize the selected policy input contract and will not guess how to create a plan.':
    '此客户端无法识别所选政策的输入约定，因此不会猜测如何创建计划。',
  'Use this': '使用此理论',
  'Failed to switch theory': '切换理论失败',
  'Change Goal': '调整目标',
  'Set Your Goal': '设置目标',
  'Goal type': '目标类型',
  'Race Goal': '比赛目标',
  'Train toward a specific race date': '围绕某场比赛备赛',
  Continuous: '持续提升',
  'Build fitness over time': '长期提升体能',
  '10K performance': '10 公里表现',
  'Optional benchmark': '可选基准测试',
  'Choose and date an optional benchmark only if you want one. Praxys never auto-schedules it.':
    '仅在你确实需要时才选择并填写可选基准日期。Praxys 绝不会自动安排。',
  'This proposal uses an accepted goal contract without changing or linking to the Goal page.':
    '这个提案使用已接受的目标合同，不会修改或绑定 Goal 页面。',
  'Tell Praxys if a current symptom stop applies. The policy will stop this plan path and return only bounded guidance.':
    '如果当前存在症状停止条件，请告诉 Praxys。该策略会停止这条计划路径，只返回有边界的指导。',
  'Only current direct 10K race or explicit all-out 10K history can qualify.':
    '只有当前有效的 10K 比赛成绩或明确的全力 10K 历史，才能合格。',
  'The {0}-day rule is a reviewed guardrail, not a physiological cutoff.':
    '{0} 天规则是经过审查的护栏，不是生理学截止线。',
  'Only current direct 10K race or explicit all-out 10K history can qualify. Qualification keeps the accepted protocol, route or venue, assistance status, provider, and authoritative completion time attached to the evidence. The {0}-day freshness guardrail and the optional benchmark path are reviewed product boundaries, not published universal cutoffs.':
    '只有当前有效的 10K 比赛成绩或明确的全力 10K 历史，才能合格。合格证据会保留已接受的协议、路线或场地、辅助情况、数据来源，以及权威完成时间。{0} 天新鲜度规则和可选基准路径都是经过审查的产品边界，不是普适发表的阈值。',
  'Full activity only.': '仅限完整活动。',
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
  'Choose a synced activity': '选择已同步的活动',
  'Did you follow the exact protocol?': '是否完整执行了测试流程？',
  'Stop reason': '停止原因',
  'No synced candidate is available yet.': '目前没有可记录的已同步候选活动。',
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

const ZH_ROAD_10K = {
  'Review invitation': '查看邀请',
  'Not now': '暂不',
  'Leave rollout': '退出试点',
  'Continue to sign in': '继续登录',
  'Rollout status: On hold': '试点状态：审核中',
  'Rollout status: Paused': '试点状态：已暂停',
  'Rollout status: Ended': '试点状态：已结束',
  'Rollout status: Left rollout': '试点状态：已退出',
  'Your proposal will become read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.':
    '你的提案将变为只读，无法采纳或重新生成。任何已采纳计划都会保留在训练中，不会暂停或结束。你仍可导出数据或删除账号。试点数据按当前说明处理。',
  'You left the Road 10K rollout. Your proposal is read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.':
    '你已退出公路 10K 试点。你的提案为只读，无法采纳或重新生成。任何已采纳计划都会保留在训练中，不会暂停或结束。你仍可导出数据或删除账号。试点数据按当前说明处理。',
  'Your rollout access ended': '你的试点访问权限已结束',
  'Your proposal, if any, is now a read-only receipt and cannot be adopted or regenerated. An adopted plan is unchanged and remains manageable in Training.':
    '如有提案，它现在仅作为只读记录，无法采纳或重新生成。已采纳的计划保持不变，仍可在训练中管理。',
  'Join rollout': '加入试点',
  'Join the Road 10K rollout?': '加入公路 10K 试点？',
  'This is a limited, default-off process pilot for one deterministic 14-day outdoor road 10K proposal. Joining the rollout does not create or adopt a plan.':
    '这是一项默认关闭的有限流程试点，用于生成一个确定性的 14 天户外公路 10K 提案。加入试点不会创建或采纳计划。',
  'Praxys checks your existing Goal, direct 10K baseline, recent running history, and confirmed scheduling constraints under the accepted Road 10K rules.':
    'Praxys 会按已接受的公路 10K 规则，检查你现有的目标、直接 10K 基准、近期跑步历史和已确认的日程限制。',
  'This does not promise faster performance, injury prevention, medical safety, diagnosis, treatment, clearance, or a personal result.':
    '此试点不承诺更快成绩、预防损伤、医疗安全、诊断、治疗、许可或个人结果。',
  'No AI chooses or adopts the plan. Nothing is sent to a training provider. Nothing changes until you explicitly adopt the exact proposal.':
    'AI 不会选择或采纳计划。任何内容都不会发送给训练服务提供商。在你明确采纳确切提案前，不会发生任何更改。',
  'The exact data used, access roles, retention, private feedback handling, export, and deletion terms appear in the current data notice below.':
    '下方当前数据说明列出了确切的数据使用、访问、保留、私密反馈处理、导出和删除条款。',
  'You can leave the rollout, export your data, or delete your account. Leaving the rollout does not pause or end an adopted plan.':
    '你可以退出试点、导出数据或删除账号。退出试点不会暂停或结束已采纳计划。',
  'I understand and want to join this Road 10K rollout.':
    '我已了解，并希望加入此公路 10K 试点。',
  'Try a Road 10K plan proposal': '试用公路 10K 计划提案',
  'You’re invited to a limited process pilot. Joining lets Praxys check whether it can create one deterministic 14-day outdoor road 10K proposal for you. Joining does not create or adopt a plan.':
    '你受邀参加一项有限流程试点。加入后，Praxys 可检查是否能为你创建一个确定性的 14 天户外公路 10K 提案。加入不会创建或采纳计划。',
  'Rollout status: Enrolled': '试点状态：已加入',
  'Plan status: No Road 10K plan': '计划状态：没有公路 10K 计划',
  'No Road 10K proposal has been created. Check the current status to continue.':
    '尚未创建公路 10K 提案。请检查当前状态后继续。',
  'Screenshots are unavailable until private deletion and restore handling are verified.':
    '在私密删除和恢复处理完成验证前，截图不可用。',
  'Joining the Road 10K rollout…': '正在加入公路 10K 试点…',
  'Praxys could not complete this action. Nothing changed.':
    'Praxys 无法完成此操作。没有任何内容发生更改。',
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
  'What metric Praxys uses to measure intensity. Power needs a compatible running-power source; Pace works with GPS activity data.':
    'Praxys 用这个指标衡量训练强度。功率需要兼容的跑步功率数据源；配速可使用 GPS 活动数据。',
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
  'Add step': '添加步骤',
  'Add repeat': '添加重复组',
  'Compare other providers': '比较其他平台',
  'Delivery blocked': '交付受阻',
  'No training data yet. Sync a connected platform from the web app (Settings → Sync) to populate this view.':
    '暂无训练数据。请先在网页端的“设置 → 同步”中同步已连接的平台。',
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
  'No platforms connected. Manage supported connections from the web app.':
    '尚未连接平台。请前往网页端管理可用连接。',
  'Auto-detected from synced fitness data; override on the web.':
    '根据已同步的体能数据自动识别；如需调整，请前往网页端。',
  'No thresholds yet. Sync fitness data to auto-detect CP, LTHR, and pace — or enter values manually on the web.':
    '暂无阈值数据。同步体能数据后可自动识别 CP、LTHR 和阈值配速，也可在网页端手动填写。',
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
  '{removed} deliveries are clear; {remaining} still need review before the target can change.':
    '已清除 {removed} 项下发；仍有 {remaining} 项需要处理，完成后才能更换执行平台。',
  'Turn on': '启用',
  'Individualized HRV evidence': '个体化 HRV 依据',
  'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.':
    'Praxys 采用 Plews 等（2012）和 Kiviniemi 等（2007）的个体化 HRV 训练指导。具体警戒区间与改为休息日的规则属于保守的产品估算，并非诊断或经临床验证的处方。',
  'Plews et al. (2012) source': 'Plews 等（2012）来源',
  'Kiviniemi et al. (2007) source': 'Kiviniemi 等（2007）来源',
};

const ZH_ME = {
  Me: '我的',
  'Observed training': '训练观察',
  'Account & data': '账号与数据',
  'Connections, thresholds, plan delivery, preferences, and account access.':
    '管理平台连接、训练阈值、计划下发、偏好与账号访问。',
  Explore: '探索',
  Experimental: '实验功能',
  About: '关于',
  'Terms & Privacy': '条款与隐私',
  'Legal documents, privacy, and data rights.':
    '查看法律文件、隐私说明与数据权利。',
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
  activity: 'activity',
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
  activity: '次活动',
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

const EN_PRIVATE_CONTEXT = {
  Manage: 'Manage',
  'I confirm this purpose and expiry': 'I confirm this purpose and expiry',
  'Manage private context': 'Manage private context',
  'Private context JSON copied': 'Private context JSON copied',
  'You can withdraw before any later request. Withdrawal cannot recall a request the provider already processed.':
    'You can withdraw before any later request. Withdrawal cannot recall a request the provider already processed.',
};

const ZH_PRIVATE_CONTEXT = {
  Manage: '管理',
  'I confirm this purpose and expiry': '我已确认上述用途和期限',
  'Manage private context': '管理计划个性化信息',
  'Private context JSON copied': '计划个性化信息 JSON 已复制',
  'You can withdraw before any later request. Withdrawal cannot recall a request the provider already processed.':
    '后续请求发送前可随时撤回；已经由 AI 服务处理的请求无法撤回。',
};

const EN_PLAN_START = {
  'Current Goal': 'Current Goal',
  'Unlinked base plan': 'Unlinked base plan',
  'The current Goal has no accepted automatic policy. Keep it unchanged, or choose an accepted separate purpose.':
    'The current Goal has no accepted automatic policy. Keep it unchanged, or choose an accepted separate purpose.',
  'This proposal uses an accepted 5K goal contract without changing or linking to the Goal page.':
    'This proposal uses an accepted 5K goal contract without changing or linking to the Goal page.',
  'A draft exists for another plan purpose. Return to that purpose to review or reject it first.':
    'A draft exists for another plan purpose. Return to that purpose to review or reject it first.',
  'Adoption is paused until the linked Goal is reassessed.':
    'Adoption is paused until the linked Goal is reassessed.',
  'This pilot is available only for the supported outdoor road 5K performance goal.':
    'This pilot is available only for the supported outdoor road 5K performance goal.',
  'For adult, self-coached recreational outdoor-road 5K runners. This is not a diagnosis, clearance, or performance guarantee.':
    'For adult, self-coached recreational outdoor-road 5K runners. This is not a diagnosis, clearance, or performance guarantee.',
  'Tell Praxys if a safety stop applies. The policy will stop this path and show its bounded alternatives.':
    'Tell Praxys if a safety stop applies. The policy will stop this path and show its bounded alternatives.',
  'Select availability, then give the same supported session limit for every selected day.':
    'Select availability, then give the same supported session limit for every selected day.',
  'Time limit (minutes)': 'Time limit (minutes)',
  'Refresh proposal': 'Refresh proposal',
  ready: 'ready',
  'Needs clarification': 'Needs clarification',
  Ready: 'Ready',
  Draft: 'Draft',
  Superseded: 'Superseded',
  Adopted: 'Adopted',
  'Baseline source': 'Baseline source',
  'History cutoff': 'History cutoff',
  'Event state': 'Event state',
  Templates: 'Templates',
  'No event selected': 'No event selected',
  'Single target': 'Single target',
  'Event conflict': 'Event conflict',
  'Controlled threshold quality': 'Controlled threshold quality',
  '10K-specific interval quality': '10K-specific interval quality',
  'usable completed weeks; latest run': 'usable completed weeks; latest run',
  'Use the accepted outdoor 5K policy': 'Use the accepted outdoor 5K policy',
  'Use baseline or consistency guidance': 'Use baseline or consistency guidance',
  'Defer plan generation': 'Defer plan generation',
  'Use non-medical safety guidance': 'Use non-medical safety guidance',
  'Refresh the qualified 5K baseline': 'Refresh the qualified 5K baseline',
  'Revise the target time or date': 'Revise the target time or date',
  'Build more consistent running first': 'Build more consistent running first',
  'Revise stated availability': 'Revise stated availability',
  'Review the history-anchored block': 'Review the history-anchored block',
  'Refresh policy metadata': 'Refresh policy metadata',
  'Keep training manually': 'Keep training manually',
  'Confirm adult scope': 'Confirm adult scope',
  'Confirm direct 10K history': 'Confirm direct 10K history',
  'Choose an optional 10K benchmark': 'Choose an optional 10K benchmark',
  'Keep one target date': 'Keep one target date',
  'Decline the optional benchmark': 'Decline the optional benchmark',
  'Wait for post-target reassessment': 'Wait for post-target reassessment',
  'Revise the constraints': 'Revise the constraints',
  'Review before adopting': 'Review before adopting',
  'Keep the current plan until adoption': 'Keep the current plan until adoption',
  'This proposal cannot mutate the canonical plan. Review readiness and create a new proposal when you are ready.':
    'This proposal cannot mutate the canonical plan. Review readiness and create a new proposal when you are ready.',
  'A preview checks current evidence and constraints. It is a proposal, not yet your plan.':
    'A preview checks current evidence and constraints. It is a proposal, not yet your plan.',
  Science: 'Science',
};

const ZH_PLAN_START = {
  'Current Goal': '当前目标',
  'Unlinked base plan': '未关联基础计划',
  'The current Goal has no accepted automatic policy. Keep it unchanged, or choose an accepted separate purpose.':
    '当前目标暂无已接受的自动计划政策。可保留目标不变，或选择已接受的独立计划用途。',
  'This proposal uses an accepted 5K goal contract without changing or linking to the Goal page.':
    '此提案使用已接受的 5 公里目标约定，不会更改或关联目标页。',
  'A draft exists for another plan purpose. Return to that purpose to review or reject it first.':
    '另一项计划用途已有草稿。请返回该用途，先审核或拒绝现有草稿。',
  'Adoption is paused until the linked Goal is reassessed.':
    '重新评估关联目标前，暂时无法采纳。',
  'This pilot is available only for the supported outdoor road 5K performance goal.':
    '此试点仅适用于受支持的户外公路 5 公里表现目标。',
  'For adult, self-coached recreational outdoor-road 5K runners. This is not a diagnosis, clearance, or performance guarantee.':
    '面向成年、自主训练的休闲户外公路 5 公里跑者。这不是诊断、健康许可或表现保证。',
  'Tell Praxys if a safety stop applies. The policy will stop this path and show its bounded alternatives.':
    '如果存在安全停止条件，请告知 Praxys。政策将停止此路径并显示其限定的替代方案。',
  'Select availability, then give the same supported session limit for every selected day.':
    '选择可用日期，然后为每个选定日期填写相同的受支持单次训练上限。',
  'Time limit (minutes)': '时间上限（分钟）',
  'Refresh proposal': '刷新提案',
  ready: '就绪',
  'Needs clarification': '需要补充信息',
  Ready: '就绪',
  Draft: '草稿',
  Superseded: '已被新版本替代',
  Adopted: '已采纳',
  'Baseline source': '基线来源',
  'History cutoff': '历史窗口',
  'Event state': '赛事状态',
  Templates: '训练模板',
  'No event selected': '未选择赛事',
  'Single target': '单一目标',
  'Event conflict': '赛事安排冲突',
  'Controlled threshold quality': '可控阈值质量课',
  '10K-specific interval quality': '10 公里专项间歇质量课',
  'usable completed weeks; latest run': '个可用完整周；最近跑步',
  'Use the accepted outdoor 5K policy': '使用已接受的户外公路 5 公里政策',
  'Use baseline or consistency guidance': '查看基线或持续性指引',
  'Defer plan generation': '暂缓生成计划',
  'Use non-medical safety guidance': '查看非医疗安全指引',
  'Refresh the qualified 5K baseline': '更新已合格的 5 公里基线',
  'Revise the target time or date': '调整目标时间或日期',
  'Build more consistent running first': '先积累更稳定的跑步训练',
  'Revise stated availability': '调整已填写的可用日期',
  'Review the history-anchored block': '审核按历史训练锚定的训练块',
  'Refresh policy metadata': '刷新政策信息',
  'Keep training manually': '继续手动管理训练',
  'Confirm adult scope': '确认成年适用范围',
  'Confirm direct 10K history': '确认直接 10 公里历史证据',
  'Choose an optional 10K benchmark': '选择可选的 10 公里基准测试',
  'Keep one target date': '只保留一个目标日期',
  'Decline the optional benchmark': '不安排可选基准测试',
  'Wait for post-target reassessment': '等待目标结束后的重新评估',
  'Revise the constraints': '调整限制条件',
  'Review before adopting': '采纳前先审核',
  'Keep the current plan until adoption': '采纳前继续执行当前计划',
  'This proposal cannot mutate the canonical plan. Review readiness and create a new proposal when you are ready.':
    '此提案无法更改规范计划。准备好后请复核准备情况并创建新提案。',
  'A preview checks current evidence and constraints. It is a proposal, not yet your plan.':
    '预览会核查当前证据和限制条件。它只是提案，尚未成为你的计划。',
  Science: '科学',
};

export const I18N_EXTRA: Record<Locale, Record<string, string>> = {
  en: {
    ...EN_AUTH,
    ...EN_GOAL,
    ...EN_ROAD_10K,
    ...EN_TODAY,
    ...EN_TRAINING,
    ...EN_COACH,
    ...EN_HISTORY_SCIENCE,
    ...EN_SETTINGS,
    ...EN_ME,
    ...EN_NAV_CHARTS,
    ...EN_HEAT,
    ...EN_LABS,
    ...EN_LEGAL,
    ...EN_PRIVATE_CONTEXT,
    ...EN_PLAN_START,
  },
  zh: {
    ...ZH_AUTH,
    ...ZH_GOAL,
    ...ZH_ROAD_10K,
    ...ZH_TODAY,
    ...ZH_TRAINING,
    ...ZH_COACH,
    ...ZH_HISTORY_SCIENCE,
    ...ZH_SETTINGS,
    ...ZH_ME,
    ...ZH_NAV_CHARTS,
    ...ZH_HEAT,
    ...ZH_LABS,
    ...ZH_LEGAL,
    ...ZH_PRIVATE_CONTEXT,
    ...ZH_PLAN_START,
  },
};
