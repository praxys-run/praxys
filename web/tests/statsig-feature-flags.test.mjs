import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('Statsig provider waits for authenticated identity changes', async () => {
  const [app, context] = await Promise.all([
    read('../src/App.tsx'),
    read('../src/contexts/StatsigContext.tsx'),
  ]);

  assert.match(app, /<AuthProvider>\s*<StatsigProvider>/);
  assert.match(
    context,
    /if \(\s*!isBrowserTelemetryAllowed\(Boolean\(CLIENT_KEY\)\)\s*\|\| isLoading\s*\|\| !isAuthenticated\s*\|\| !userId\s*\)/,
  );
  assert.match(context, /updateUserAsync\(user\)/);
  assert.doesNotMatch(context, /useFeatureGate/);
  assert.doesNotMatch(context, /JSON\.stringify\(left\)/);
  assert.match(context, /left\.userID === right\.userID/);
  assert.match(context, /left\.custom\?\.is_admin === right\.custom\?\.is_admin/);
  assert.match(context, /userID: userId/);
  assert.match(context, /is_admin: isAdmin/);
  assert.match(context, /is_demo: isDemo/);
  assert.match(context, /email\?\.toLowerCase\(\)\.startsWith\('wechat:'\)/);
});

test('settings remain compatible with an older backend response', async () => {
  const context = await read('../src/contexts/SettingsContext.tsx');

  assert.match(context, /data\.plan_delivery_options !== undefined/);
  assert.match(context, /data\.config\.connections\.map/);
  assert.match(context, /platform_capabilities\[platform\]\?\.plan === true/);
  assert.match(
    context,
    /setPlanDeliveryOptions\(planDeliveryOptionsFromResponse\(data\)\)/,
  );
});
