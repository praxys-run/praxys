import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { tokenCacheScope } from '../src/lib/auth-cache-scope.ts';
import { initialDashboardUrl } from '../src/lib/dashboard-prefetch.ts';

test('prefetches the authenticated cold-load dashboard route', () => {
  assert.equal(initialDashboardUrl('/today', true), '/api/today');
  assert.equal(initialDashboardUrl('/training', true), '/api/training');
  assert.equal(initialDashboardUrl('/', true), '/api/today');
  assert.equal(initialDashboardUrl('/today', false), null);
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
    ['Today.tsx', 'Training.tsx'].map((name) =>
      readFile(new URL(`../src/pages/${name}`, import.meta.url), 'utf8'),
    ),
  );

  for (const source of sources) {
    assert.doesNotMatch(source, /refetchOnMount:\s*'always'/);
    assert.doesNotMatch(source, /refetchOnWindowFocus:\s*'always'/);
  }
});
