import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { tokenCacheScope } from '../src/lib/auth-cache-scope.ts';
import { initialDashboardUrl } from '../src/lib/dashboard-prefetch.ts';

test('prefetches the authenticated cold-load dashboard route', () => {
  assert.equal(initialDashboardUrl('/today', true), '/api/today');
  assert.equal(initialDashboardUrl('/analysis', true), '/api/training');
  const trainingUrl = initialDashboardUrl('/training', true);
  assert.match(
    trainingUrl,
    /^\/api\/plan\?start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}$/,
  );
  const trainingWindow = new URL(trainingUrl, 'https://www.praxys.run');
  const start = Date.parse(trainingWindow.searchParams.get('start'));
  const end = Date.parse(trainingWindow.searchParams.get('end'));
  assert.equal((end - start) / 86_400_000, 27);
  assert.equal(initialDashboardUrl('/', true), '/api/today');
  assert.equal(initialDashboardUrl('/today', false), null);
  assert.equal(initialDashboardUrl('/today', true, false), null);
  assert.equal(initialDashboardUrl('/training', true, false), null);
  assert.equal(initialDashboardUrl('/analysis', true, false), null);
  assert.equal(initialDashboardUrl('/settings', true), null);
});

test('scopes cached API data to the active authentication token', () => {
  assert.equal(tokenCacheScope(null), 'anonymous');
  assert.equal(tokenCacheScope('token-a'), tokenCacheScope('token-a'));
  assert.notEqual(tokenCacheScope('token-a'), tokenCacheScope('token-b'));
  assert.doesNotMatch(tokenCacheScope('secret-token'), /secret-token/);
});

test('setup status shares React Query requests across consumers', async () => {
  const source = await readFile(
    new URL('../src/hooks/useSetupStatus.ts', import.meta.url),
    'utf8',
  );

  assert.match(source, /queryKey: \['setup', 'connections', authScope\]/);
  assert.match(source, /queryKey: \['setup', 'sync-status', authScope\]/);
  assert.doesNotMatch(source, /Promise\.all\(\[/);
});

test('daily pages use the app freshness policy instead of forced focus fetches', async () => {
  const sources = await Promise.all(
    ['Today.tsx', 'Training.tsx', 'Analysis.tsx'].map((name) =>
      readFile(new URL(`../src/pages/${name}`, import.meta.url), 'utf8'),
    ),
  );

  for (const source of sources) {
    assert.doesNotMatch(source, /refetchOnMount:\s*'always'/);
    assert.doesNotMatch(source, /refetchOnWindowFocus:\s*'always'/);
  }
});

test('keeps chart code off the initial Today preload path', async () => {
  const [appSource, viteSource] = await Promise.all([
    readFile(new URL('../src/App.tsx', import.meta.url), 'utf8'),
    readFile(new URL('../vite.config.ts', import.meta.url), 'utf8'),
  ]);

  assert.match(appSource, /const loadTraining = \(\) => import\('\.\/pages\/Training'\)/);
  assert.match(appSource, /const loadAnalysis = \(\) => import\('\.\/pages\/Analysis'\)/);
  assert.match(appSource, /requestIdleCallback\(/);
  assert.match(appSource, /cancelIdleCallback\(idleCallbackId\)/);
  assert.match(viteSource, /context\.hostType !== 'html'/);
  assert.match(viteSource, /!dependency\.includes\('recharts-'\)/);
});
