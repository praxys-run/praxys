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

class FakeEventSource {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }

  dispatch(type) {
    for (const listener of [...(this.listeners.get(type) ?? [])]) {
      if (typeof listener === 'function') listener({ type });
      else listener.handleEvent({ type });
    }
  }

  listenerCount(type) {
    return this.listeners.get(type)?.size ?? 0;
  }
}

class FakeWorker extends FakeEventSource {
  constructor(scriptURL, state) {
    super();
    this.scriptURL = scriptURL;
    this.state = state;
  }

  transition(state) {
    this.state = state;
    this.dispatch('statechange');
  }
}

class FakeRegistration extends FakeEventSource {
  constructor({ scope, active, events, updateImpl }) {
    super();
    this.scope = scope;
    this.active = active;
    this.installing = null;
    this.waiting = null;
    this.events = events;
    this.updateImpl = updateImpl;
  }

  async update() {
    this.events.push('update-worker');
    await this.updateImpl(this);
  }

  discover(worker) {
    this.installing = worker;
    this.dispatch('updatefound');
  }
}

class FakeServiceWorkerContainer extends FakeEventSource {
  constructor({ controller, events, registration }) {
    super();
    this.controller = controller;
    this.events = events;
    this.registration = registration;
  }

  async getRegistration() {
    this.events.push('get-registration');
    return this.registration;
  }

  claim(worker) {
    this.controller = worker;
    this.dispatch('controllerchange');
  }
}

function recoveryHarness(overrides = {}) {
  const events = overrides.events ?? [];
  const origin = overrides.origin ?? 'https://www.praxys.run';
  const oldWorker = new FakeWorker(`${origin}/sw.js`, 'activated');
  const replacement = new FakeWorker(`${origin}/sw.js`, 'installing');
  let container;
  const updateImpl = overrides.updateImpl ?? (async (registration) => {
    registration.discover(replacement);
    queueMicrotask(() => {
      replacement.transition('activated');
      container.claim(replacement);
    });
  });
  const registration = new FakeRegistration({
    scope: overrides.scope ?? `${origin}/`,
    active: oldWorker,
    events,
    updateImpl,
  });
  container = new FakeServiceWorkerContainer({
    controller: oldWorker,
    events,
    registration,
  });
  const environment = {
    online: true,
    origin,
    storage: memoryStorage(null, events),
    serviceWorker: container,
    timeoutMs: 50,
    ...(overrides.environment ?? {}),
  };
  return {
    environment,
    events,
    oldWorker,
    replacement,
    registration,
    container,
  };
}

function recoveryEnvironment(overrides = {}) {
  return recoveryHarness(overrides).environment;
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

test('reload waits for replacement activation and controller handoff, then cleans listeners', async () => {
  let harness;
  harness = recoveryHarness({
    updateImpl: async (registration) => {
      registration.discover(harness.replacement);
    },
  });
  let settled = false;
  const pending = prepareLegalBundleRecovery(harness.environment)
    .then((result) => {
      settled = true;
      return result;
    });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(settled, false);

  harness.replacement.transition('activated');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(settled, false, 'activation alone must not permit reload');

  harness.container.claim(harness.replacement);
  assert.deepEqual(await pending, { action: 'reload' });
  assert.equal(harness.registration.listenerCount('updatefound'), 0);
  assert.equal(harness.replacement.listenerCount('statechange'), 0);
  assert.equal(harness.container.listenerCount('controllerchange'), 0);
});

test('synchronous activation and control before update resolves cannot lose the handoff', async () => {
  let harness;
  harness = recoveryHarness({
    updateImpl: async (registration) => {
      registration.discover(harness.replacement);
      harness.replacement.transition('activated');
      harness.container.claim(harness.replacement);
    },
  });
  assert.deepEqual(
    await prepareLegalBundleRecovery(harness.environment),
    { action: 'reload' },
  );
  assert.equal(harness.registration.listenerCount('updatefound'), 0);
  assert.equal(harness.replacement.listenerCount('statechange'), 0);
  assert.equal(harness.container.listenerCount('controllerchange'), 0);
});

test('no replacement, redundant activation, and control timeout remain fail closed', async () => {
  const noReplacement = recoveryHarness({ updateImpl: async () => {} });
  assert.deepEqual(
    await prepareLegalBundleRecovery(noReplacement.environment),
    { action: 'fallback', reason: 'no-replacement' },
  );

  let redundant;
  redundant = recoveryHarness({
    updateImpl: async (registration) => {
      registration.discover(redundant.replacement);
      redundant.replacement.transition('redundant');
    },
  });
  assert.deepEqual(
    await prepareLegalBundleRecovery(redundant.environment),
    { action: 'fallback', reason: 'activation-failed' },
  );

  let controlTimeout;
  controlTimeout = recoveryHarness({
    environment: { timeoutMs: 5 },
    updateImpl: async (registration) => {
      registration.discover(controlTimeout.replacement);
      controlTimeout.replacement.transition('activated');
    },
  });
  assert.deepEqual(
    await prepareLegalBundleRecovery(controlTimeout.environment),
    { action: 'fallback', reason: 'control-timeout' },
  );
  assert.equal(controlTimeout.registration.listenerCount('updatefound'), 0);
  assert.equal(controlTimeout.replacement.listenerCount('statechange'), 0);
  assert.equal(controlTimeout.container.listenerCount('controllerchange'), 0);
});

test('replacement activation timeout is distinct and removes every listener', async () => {
  let harness;
  harness = recoveryHarness({
    environment: { timeoutMs: 5 },
    updateImpl: async (registration) => {
      registration.discover(harness.replacement);
    },
  });
  assert.deepEqual(
    await prepareLegalBundleRecovery(harness.environment),
    { action: 'fallback', reason: 'activation-timeout' },
  );
  assert.equal(harness.registration.listenerCount('updatefound'), 0);
  assert.equal(harness.replacement.listenerCount('statechange'), 0);
  assert.equal(harness.container.listenerCount('controllerchange'), 0);
});

test('the same-origin rule is identical across both public domain pairs', async () => {
  for (const origin of [
    'https://praxys.run',
    'https://www.praxys.run',
    'https://praxys.cn',
    'https://www.praxys.cn',
  ]) {
    const harness = recoveryHarness({ origin });
    const result = await prepareLegalBundleRecovery(harness.environment);
    assert.deepEqual(result, { action: 'reload' });
    assert.equal(harness.events.filter((event) => event === 'update-worker').length, 1);
  }
});

test('an existing episode marker prevents a second automatic reload', async () => {
  let registrations = 0;
  const result = await prepareLegalBundleRecovery(recoveryEnvironment({
    environment: {
      storage: memoryStorage(LEGAL_BUNDLE_RECOVERY_MARKER_VALUE),
      serviceWorker: {
        async getRegistration() {
          registrations += 1;
          return null;
        },
      },
    },
  }));

  assert.deepEqual(result, { action: 'fallback', reason: 'already-attempted' });
  assert.equal(registrations, 0);
});

test('offline, unavailable storage, absent or cross-origin workers fail closed', async () => {
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      environment: { online: false },
    })),
    { action: 'fallback', reason: 'offline' },
  );
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      environment: { storage: null },
    })),
    { action: 'fallback', reason: 'marker-unavailable' },
  );
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      environment: {
        serviceWorker: { async getRegistration() { return null; } },
      },
    })),
    { action: 'fallback', reason: 'no-registration' },
  );
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      scope: 'https://attacker.invalid/',
    })),
    { action: 'fallback', reason: 'cross-origin-registration' },
  );
});

test('marker readback, worker update failure, and timeout fail closed', async () => {
  const storage = memoryStorage();
  storage.setItem = () => {};
  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      environment: { storage },
    })),
    { action: 'fallback', reason: 'marker-unavailable' },
  );

  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      updateImpl: async () => { throw new Error('update failed'); },
    })),
    { action: 'fallback', reason: 'update-failed' },
  );

  assert.deepEqual(
    await prepareLegalBundleRecovery(recoveryEnvironment({
      updateImpl: async () => new Promise(() => {}),
      environment: { timeoutMs: 5 },
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
  assert.equal(auth.match(/window\.location\.reload\(\)/g)?.length, 1);
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
  assert.match(gate, /initialFocus=\{\(\) => document\.getElementById\(TERMS_GATE_TITLE_ID\)\}/);
  assert.match(gate, /<DialogTitle[\s\S]*id=\{TERMS_GATE_TITLE_ID\}[\s\S]*tabIndex=\{-1\}/);
  assert.match(gate, /onKeyDownCapture=\{handleDialogKeyDown\}/);
  assert.match(gate, /fallbackAlertRef[\s\S]*focus\(\{ preventScroll: true \}\)/);
  assert.match(gate, /role="status"[\s\S]*aria-live="polite"/);
  assert.match(gate, /role="alert"/);
  assert.match(gate, /min-h-11/);
  assert.match(gate, /min-w-11/);
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
