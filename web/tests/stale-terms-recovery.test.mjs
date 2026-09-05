import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  LEGAL_BUNDLE_RECOVERY_MARKER_KEY,
  LEGAL_BUNDLE_RECOVERY_MARKER_VALUE,
  clearLegalBundleRecoveryMarker,
  prepareLegalBundleRecovery,
  recoverTermsBundleMismatchResponse,
} from '../src/lib/legal-bundle-recovery.ts';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

function memoryStorage(initial = null, events = []) {
  let value = initial;
  return {
    getItem(key) {
      assert.equal(key, LEGAL_BUNDLE_RECOVERY_MARKER_KEY);
      events.push('read-marker');
      return value;
    },
    setItem(key, next) {
      assert.equal(key, LEGAL_BUNDLE_RECOVERY_MARKER_KEY);
      events.push('write-marker');
      value = next;
    },
    removeItem(key) {
      assert.equal(key, LEGAL_BUNDLE_RECOVERY_MARKER_KEY);
      events.push('clear-marker');
      value = null;
    },
  };
}

function recoveryEnvironment(overrides = {}) {
  const events = overrides.events ?? [];
  const registration = overrides.registration ?? {
    scope: 'https://www.praxys.run/',
    async update() {
      events.push('update-worker');
    },
  };
  return {
    online: true,
    origin: 'https://www.praxys.run',
    storage: memoryStorage(null, events),
    serviceWorker: {
      async getRegistration() {
        events.push('get-registration');
        return registration;
      },
    },
    timeoutMs: 50,
    ...overrides,
  };
}

test('only a 409 with an object detail carrying the exact mismatch code starts recovery', async () => {
  const matchedEvents = [];
  const matched = await recoverTermsBundleMismatchResponse(
    new Response(JSON.stringify({
      detail: {
        code: 'TERMS_BUNDLE_MISMATCH',
        terms_version: '2026.10.0',
        terms_digest: 'sha256:diagnostic-only',
      },
    }), { status: 409, headers: { 'Content-Type': 'application/json' } }),
    {
      environment: recoveryEnvironment({ events: matchedEvents }),
      onMismatch: () => matchedEvents.push('matched'),
    },
  );
  assert.deepEqual(matched, { matched: true, recovery: { action: 'reload' } });
  assert.deepEqual(matchedEvents, [
    'matched',
    'read-marker',
    'write-marker',
    'read-marker',
    'get-registration',
    'update-worker',
  ]);

  for (const [status, payload] of [
    [409, { code: 'TERMS_BUNDLE_MISMATCH' }],
    [409, { detail: 'TERMS_BUNDLE_MISMATCH' }],
    [409, { detail: { code: 'TERMS_ACCEPTANCE_REQUIRED' } }],
    [400, { detail: { code: 'TERMS_BUNDLE_MISMATCH' } }],
    [500, { detail: { code: 'TERMS_BUNDLE_MISMATCH' } }],
  ]) {
    const events = [];
    const result = await recoverTermsBundleMismatchResponse(
      new Response(JSON.stringify(payload), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
      {
        environment: recoveryEnvironment({ events }),
        onMismatch: () => events.push('matched'),
      },
    );
    assert.deepEqual(result, { matched: false });
    assert.deepEqual(events, []);
  }
});

test('recovery persists and reads back a data-free marker before updating the same-origin worker', async () => {
  const events = [];
  const result = await prepareLegalBundleRecovery(recoveryEnvironment({ events }));

  assert.deepEqual(result, { action: 'reload' });
  assert.deepEqual(events, [
    'read-marker',
    'write-marker',
    'read-marker',
    'get-registration',
    'update-worker',
  ]);
  assert.equal(LEGAL_BUNDLE_RECOVERY_MARKER_VALUE, 'attempted-v1');
});

test('the same-origin rule is identical across both public domain pairs', async () => {
  for (const origin of [
    'https://praxys.run',
    'https://www.praxys.run',
    'https://praxys.cn',
    'https://www.praxys.cn',
  ]) {
    let updates = 0;
    const result = await prepareLegalBundleRecovery(recoveryEnvironment({
      origin,
      registration: {
        scope: `${origin}/`,
        async update() { updates += 1; },
      },
    }));
    assert.deepEqual(result, { action: 'reload' });
    assert.equal(updates, 1);
  }
});

test('an existing episode marker prevents a second automatic reload', async () => {
  let registrations = 0;
  const result = await prepareLegalBundleRecovery(recoveryEnvironment({
    storage: memoryStorage(LEGAL_BUNDLE_RECOVERY_MARKER_VALUE),
    serviceWorker: {
      async getRegistration() {
        registrations += 1;
        return null;
      },
    },
  }));

  assert.deepEqual(result, { action: 'fallback', reason: 'already-attempted' });
  assert.equal(registrations, 0);
});

test('offline, unavailable storage, absent or cross-origin workers fail closed', async () => {
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({ online: false })),
    { action: 'fallback', reason: 'offline' },
  );
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({ storage: null })),
    { action: 'fallback', reason: 'marker-unavailable' },
  );
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      serviceWorker: { async getRegistration() { return null; } },
    })),
    { action: 'fallback', reason: 'no-registration' },
  );
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      registration: {
        scope: 'https://attacker.invalid/',
        async update() {},
      },
    })),
    { action: 'fallback', reason: 'cross-origin-registration' },
  );
});

test('marker readback, worker update failure, and timeout fail closed', async () => {
  const storage = memoryStorage();
  storage.setItem = () => {};
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({ storage })),
    { action: 'fallback', reason: 'marker-unavailable' },
  );

  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      registration: {
        scope: 'https://www.praxys.run/',
        async update() { throw new Error('update failed'); },
      },
    })),
    { action: 'fallback', reason: 'update-failed' },
  );

  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      registration: {
        scope: 'https://www.praxys.run/',
        async update() { return new Promise(() => {}); },
      },
      timeoutMs: 5,
    })),
    { action: 'fallback', reason: 'timeout' },
  );
});

test('successful acceptance clears the bounded recovery episode marker', () => {
  const events = [];
  clearLegalBundleRecoveryMarker(memoryStorage(
    LEGAL_BUNDLE_RECOVERY_MARKER_VALUE,
    events,
  ));
  assert.deepEqual(events, ['clear-marker']);
});

test('web gate exposes all recovery states while keeping acceptance explicit and rights available', async () => {
  const [auth, gate, miniapp] = await Promise.all([
    read('../src/hooks/useAuth.tsx'),
    read('../src/components/TermsGate.tsx'),
    read('../../miniapp/pages/login/index.ts'),
  ]);

  for (const state of [
    'ready',
    'submitting',
    'accepted',
    'updating',
    'reloading',
    'submit_error',
    'fallback',
  ]) {
    assert.ok(auth.includes(`'${state}'`) || gate.includes(`'${state}'`), state);
  }
  assert.match(auth, /recoverTermsBundleMismatchResponse\(res/);
  assert.doesNotMatch(auth, /apiError\.code === TERMS_BUNDLE_MISMATCH_CODE/);
  assert.match(auth, /setTermsCurrent\(false\)[\s\S]*onBundleMismatch/);
  assert.match(auth, /clearLegalBundleRecoveryMarker/);
  assert.match(
    auth,
    /terms_version: TERMS_VERSION,[\s\S]*terms_digest: TERMS_CONTENT_DIGEST/,
  );
  assert.doesNotMatch(auth, /terms_version:\s*apiError|terms_digest:\s*apiError/);
  assert.match(gate, /setAgreed\(false\)/);
  assert.match(gate, /aria-live="polite"/);
  assert.match(gate, /Export my data/);
  assert.match(gate, /Delete account/);
  assert.match(gate, /Sign out/);
  assert.match(gate, /Connected platforms/);
  assert.match(gate, /Refresh this page/);
  assert.doesNotMatch(miniapp, /legal-bundle-recovery|serviceWorker/);
});

test('admin retry copy names triage-only behavior without changing publication authority', async () => {
  const [admin, zhCatalog] = await Promise.all([
    read('../src/pages/admin/AdminFeedback.tsx'),
    read('../src/locales/zh/messages.po'),
  ]);

  assert.match(admin, /Re-run triage/);
  assert.match(admin, /Re-running triage…/);
  assert.match(admin, /refreshes analysis and routing/);
  assert.match(admin, /grants no publication permission/);
  assert.match(admin, /does not directly create a GitHub issue/);
  assert.match(admin, /already has current publication authorization/);
  assert.match(admin, /normal review and publication gates/);
  assert.doesNotMatch(admin, /Publication permission and GitHub issue state were unchanged/);
  assert.doesNotMatch(admin, /does not grant publication permission or create a GitHub issue/);
  assert.match(admin, /Agent-ready applies only to feedback already linked to a public GitHub issue/);
  assert.match(admin, /handleFeedbackAction\(item, 'retry'\)/);
  assert.match(admin, /external_publication_consent/);
  assert.match(zhCatalog, /此操作不会授予发布权限，也不会直接创建 GitHub Issue/);
  assert.match(zhCatalog, /已经具备当前发布授权的合格反馈，仍可能继续通过正常的审核与发布门禁/);
  assert.match(zhCatalog, /msgid "Re-running triage…"\s+msgstr "正在重新分析并分流…"/);
});
