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
    /if \(!CLIENT_KEY \|\| isLoading \|\| !isAuthenticated \|\| !userId\)/,
  );
  assert.match(context, /updateUserAsync\(user\)/);
  assert.doesNotMatch(context, /useFeatureGate/);
  assert.doesNotMatch(context, /JSON\.stringify\(left\)/);
  assert.match(context, /left\.userID === right\.userID/);
  assert.match(context, /left\.custom\?\.is_admin === right\.custom\?\.is_admin/);
  assert.match(context, /userID: userId/);
  assert.match(context, /is_admin: isAdmin/);
  assert.match(context, /is_demo: isDemo/);
});
