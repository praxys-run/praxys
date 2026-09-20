import assert from 'node:assert/strict';
import test from 'node:test';
import { resolvePublicRoute } from '../src/lib/public-route.ts';

test('public document locale is stable before boot and has an explicit English entry', () => {
  assert.deepEqual(resolvePublicRoute('/', true), { page: 'home', locale: 'zh' });
  assert.deepEqual(resolvePublicRoute('/', false), { page: 'home', locale: 'en' });
  for (const china of [true, false]) {
    assert.deepEqual(resolvePublicRoute('/en/', china), { page: 'home', locale: 'en' });
    assert.deepEqual(resolvePublicRoute('/zh', china), { page: 'home', locale: 'zh' });
    assert.deepEqual(resolvePublicRoute('/zh/product/', china), { page: 'product', locale: 'zh' });
    assert.deepEqual(resolvePublicRoute('/faq', china), { page: 'faq', locale: 'en' });
  }
});

test('private and legal routes can never select a marketing document', () => {
  for (const path of ['/today', '/settings', '/login', '/privacy', '/terms', '/verify', '/mcp/authorize', '/admin/users', '/zh/unknown']) {
    assert.equal(resolvePublicRoute(path, true), null, path);
    assert.equal(resolvePublicRoute(path, false), null, path);
  }
});
