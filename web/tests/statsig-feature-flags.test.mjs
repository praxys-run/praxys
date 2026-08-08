import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('Statsig is fail-closed and follows authenticated identity changes', async () => {
  const [app, context] = await Promise.all([
    read('../src/App.tsx'),
    read('../src/contexts/StatsigContext.tsx'),
  ]);

  assert.match(app, /<AuthProvider>\s*<StatsigProvider>/);
  assert.match(
    context,
    /if \(!CLIENT_KEY \|\| isLoading \|\| !isAuthenticated \|\| !userId\)/,
  );
  assert.match(context, /FeatureFlagsContext\.Provider value=\{DISABLED_FLAGS\}/);
  assert.match(context, /updateUserAsync\(user\)/);
  assert.match(context, /ai_insights_enabled: identityIsCurrent && aiInsights/);
  assert.doesNotMatch(context, /JSON\.stringify\(left\)/);
  assert.match(context, /left\.userID === right\.userID/);
  assert.match(context, /left\.custom\?\.is_admin === right\.custom\?\.is_admin/);
  assert.match(context, /userID: userId/);
  assert.match(context, /is_admin: isAdmin/);
  assert.match(context, /is_demo: isDemo/);
});

test('AI cards retain deterministic fallback when the gate is off', async () => {
  const card = await read('../src/components/AiInsightsCard.tsx');

  assert.match(card, /useFeatureFlag\('ai_insights_enabled'\)/);
  assert.match(card, /shouldFetchInsight = fetchInsight && aiInsightsEnabled/);
  assert.match(card, /\{ enabled: shouldFetchInsight \}/);
  assert.match(card, /fallback\s*\?\s*\{/);
});

test('connection options and Stryd delivery control honor visibility gates', async () => {
  const [settings, setup, plan] = await Promise.all([
    read('../src/pages/Settings.tsx'),
    read('../src/pages/Setup.tsx'),
    read('../src/components/UpcomingPlanCard.tsx'),
  ]);

  assert.match(settings, /useFeatureFlag\('strava_connection_visible'\)/);
  assert.match(settings, /useFeatureFlag\('coros_connection_visible'\)/);
  assert.match(settings, /visiblePlatforms\.map/);
  assert.match(setup, /useFeatureFlag\('strava_connection_visible'\)/);
  assert.match(setup, /useFeatureFlag\('coros_connection_visible'\)/);
  assert.match(setup, /visiblePlatforms\.map/);
  assert.match(plan, /useFeatureFlag\('stryd_plan_push_visible'\)/);
  assert.match(plan, /featureVisibility\.stryd_plan_push_visible/);
  assert.match(plan, /if \(!strydPlanPushVisible\)/);
});
