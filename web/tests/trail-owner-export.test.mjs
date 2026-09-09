import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import test from 'node:test';

import { createTrailOwnerExportAction } from '../src/components/trail-course-review/owner-export.ts';

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const savedAccount = {
  user_config: {
    goal: {
      trail_plan: {
        value: 120,
        unknown: { state: 'unknown' },
        provenance: 'athlete_stated',
        revision: 'synthetic-saved-revision',
        confirmations: { 'section.event-duration': null },
      },
    },
  },
};
const savedBlob = () => new Blob([JSON.stringify(savedAccount)], { type: 'application/json' });
const okResponse = (header = 'attachment; filename="praxys-data-export-2026-09-05.json"') => ({
  ok: true,
  headers: { get: (name) => name === 'content-disposition' ? header : null },
  blob: async () => savedBlob(),
});

function harness(t, options = {}) {
  const events = [];
  const statuses = [];
  const requests = [];
  const blobs = [];
  const revoked = [];
  const anchors = [];
  let focused = 'menu-item';
  let action;
  const throwAt = (step) => {
    if (options.failAt === step) throw new Error(`synthetic private failure: ${step}`);
  };
  t.mock.method(globalThis, 'fetch', (url, init) => {
    events.push('fetch');
    requests.push({ url, init });
    options.onFetch?.(action);
    return options.fetch ? options.fetch(url, init) : Promise.resolve(okResponse());
  });
  t.mock.method(URL, 'createObjectURL', (blob) => {
    events.push('create-url');
    throwAt('create-url');
    blobs.push(blob);
    return 'blob:synthetic-owner-export';
  });
  t.mock.method(URL, 'revokeObjectURL', (url) => {
    events.push('revoke-url');
    revoked.push(url);
    throwAt('revoke-url');
  });
  const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: {
      createElement(tag) {
        events.push('create-anchor');
        throwAt('create-anchor');
        assert.equal(tag, 'a');
        const anchor = {
          href: '',
          download: '',
          click() {
            events.push('click');
            throwAt('click');
            options.onClick?.(action);
          },
          remove() {
            events.push('remove');
            throwAt('remove');
          },
        };
        anchors.push(anchor);
        return anchor;
      },
      body: {
        appendChild(anchor) {
          events.push('append');
          assert.ok(anchors.includes(anchor));
          throwAt('append');
        },
      },
    },
  });
  t.after(() => {
    if (originalDocument) Object.defineProperty(globalThis, 'document', originalDocument);
    else delete globalThis.document;
  });
  action = createTrailOwnerExportAction({
    getAuthHeaders() {
      events.push('headers');
      throwAt('headers');
      options.onHeaders?.(action);
      return { Authorization: 'Bearer synthetic-export-test' };
    },
    closeMenuAndFocus() {
      events.push('close');
      options.onClose?.(action);
      focused = 'more-actions';
      events.push('focus');
    },
    onStatusChange(status) {
      events.push(`status:${status}`);
      statuses.push(status);
      options.onStatus?.(action, status);
    },
  });
  return {
    action, events, statuses, requests, blobs, revoked, anchors,
    get focused() { return focused; },
    set focused(value) { focused = value; },
  };
}

test('export latches before reentrant activation, closes/focuses before GET, and stays busy through blob', async (t) => {
  const response = deferred();
  const blob = deferred();
  const pending = Object.freeze({ value: 999, revision: 'synthetic-pending-revision' });
  const pendingBefore = structuredClone(pending);
  const duplicate = (action) => { void action.run(); };
  const h = harness(t, {
    fetch: () => response.promise,
    onClose: duplicate,
    onHeaders: duplicate,
    onFetch: duplicate,
    onStatus: (action, status) => { if (status === 'preparing') duplicate(action); },
  });
  const running = h.action.run();
  for (const activation of ['pointer', 'keyboard', 'programmatic']) {
    await h.action.run({ type: activation, pending });
  }
  assert.deepEqual(h.events, ['status:preparing', 'close', 'focus', 'headers', 'fetch']);
  assert.equal(h.focused, 'more-actions');
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, '/api/me/export');
  assert.deepEqual(Object.keys(h.requests[0].init).sort(), ['headers', 'method', 'mode', 'redirect', 'signal']);
  assert.equal(h.requests[0].init.method, 'GET');
  assert.equal(h.requests[0].init.mode, 'same-origin');
  assert.equal(h.requests[0].init.redirect, 'error');
  assert.deepEqual(h.requests[0].init.headers, { Authorization: 'Bearer synthetic-export-test' });
  assert.equal(h.requests[0].init.signal.aborted, false);

  response.resolve({
    ...okResponse(),
    blob() { h.events.push('blob'); return blob.promise; },
  });
  await Promise.resolve();
  assert.equal(h.events.at(-1), 'blob');
  assert.deepEqual(h.statuses, ['preparing']);
  await h.action.run();
  assert.equal(h.requests.length, 1);
  h.focused = 'later-field';
  blob.resolve(savedBlob());
  await running;

  assert.deepEqual(h.statuses, ['preparing', 'success']);
  assert.equal(h.focused, 'later-field', 'completion must never restore focus');
  assert.equal(h.events.filter((event) => event === 'focus').length, 1);
  assert.deepEqual(h.events.slice(-7), [
    'create-url', 'create-anchor', 'append', 'click', 'remove', 'revoke-url', 'status:success',
  ]);
  assert.equal(h.anchors[0].href, 'blob:synthetic-owner-export');
  assert.equal(h.anchors[0].download, 'praxys-data-export-2026-09-05.json');
  assert.deepEqual(h.revoked, ['blob:synthetic-owner-export']);
  assert.deepEqual(JSON.parse(await h.blobs[0].text()), savedAccount);
  assert.deepEqual(pending, pendingBefore, 'pending page-memory edits stay untouched');
});

test('success releases the latch for a fresh user-requested account snapshot', async (t) => {
  const h = harness(t);
  await h.action.run();
  await h.action.run();
  assert.equal(h.requests.length, 2);
  assert.deepEqual(h.statuses, ['preparing', 'success', 'preparing', 'success']);
  assert.equal(h.revoked.length, 2);
});

for (const failure of [401, 403, 404, 428, 500, 'network', 'blob']) {
  test(`export failure ${failure} reports only closed state and permits retry`, async (t) => {
    let failing = true;
    const h = harness(t, {
      fetch: async () => {
        if (!failing) return okResponse();
        if (failure === 'network') throw new Error('private synthetic network detail');
        if (failure === 'blob') return {
          ...okResponse(),
          blob: async () => { throw new Error('private synthetic body detail'); },
        };
        return {
          ok: false,
          status: failure,
          json: () => assert.fail('must not read raw server errors'),
          text: () => assert.fail('must not read raw server errors'),
          blob: () => assert.fail('must not download a failed response'),
        };
      },
    });
    const first = h.action.run();
    h.focused = 'later-field';
    await first;
    assert.deepEqual(h.statuses, ['preparing', 'error']);
    assert.equal(h.focused, 'later-field');
    assert.deepEqual(h.blobs, []);
    failing = false;
    await h.action.run();
    assert.deepEqual(h.statuses, ['preparing', 'error', 'preparing', 'success']);
    assert.equal(h.requests.length, 2);
    assert.equal(h.revoked.length, 1);
  });
}

for (const [header, expected] of [
  ['attachment; filename="praxys-data-export-2026-09-05.json"', 'praxys-data-export-2026-09-05.json'],
  ['attachment; filename=praxys-data-export-2026-09-05.json', 'praxys-data-export-2026-09-05.json'],
  ['attachment; FILENAME = "praxys-data-export-2026-09-05.json"; size=123', 'praxys-data-export-2026-09-05.json'],
  [null, 'praxys-data-export.json'],
  ['attachment', 'praxys-data-export.json'],
  ['attachment; filename="trail-plan.json"', 'praxys-data-export.json'],
  ['attachment; filename="../praxys-data-export-2026-09-05.json"', 'praxys-data-export.json'],
  ['attachment; filename="private-praxys-data-export-2026-09-05.json"', 'praxys-data-export.json'],
  ['attachment; filename="praxys-data-export-2026-09-05.json.exe"', 'praxys-data-export.json'],
  ['attachment; filename="PRAXYS-data-export-2026-09-05.json"', 'praxys-data-export.json'],
  ['attachment; filename="praxys-data-export-2026-9-5.json"', 'praxys-data-export.json'],
  ['attachment; filename="praxys-data-export-２０２６-09-05.json"', 'praxys-data-export.json'],
  ['attachment; filename="praxys-data-export-2026-09-05.json\n"', 'praxys-data-export.json'],
  ['attachment; filename="praxys-data-export-2026-09-05.json"suffix', 'praxys-data-export.json'],
  ["attachment; filename*=UTF-8''praxys-data-export-2026-09-05.json", 'praxys-data-export.json'],
]) {
  test(`export filename is restricted to the account pattern: ${JSON.stringify(header)}`, async (t) => {
    const h = harness(t, { fetch: async () => okResponse(header) });
    await h.action.run();
    assert.equal(h.anchors[0].download, expected);
    assert.deepEqual(h.statuses, ['preparing', 'success']);
    assert.equal(h.revoked.length, 1);
  });
}

for (const step of ['headers', 'create-url', 'create-anchor', 'append', 'click', 'remove', 'revoke-url']) {
  test(`export cleans up and can retry after ${step} failure`, async (t) => {
    const options = { failAt: step };
    const h = harness(t, options);
    await h.action.run();
    assert.deepEqual(h.statuses, ['preparing', 'error']);
    const createdUrl = !['headers', 'create-url'].includes(step);
    assert.equal(h.revoked.length, createdUrl ? 1 : 0);
    if (['append', 'click', 'remove', 'revoke-url'].includes(step)) {
      assert.ok(h.events.includes('remove'));
    }
    options.failAt = null;
    await h.action.run();
    assert.deepEqual(h.statuses, ['preparing', 'error', 'preparing', 'success']);
    assert.equal(h.revoked.length, createdUrl ? 2 : 1);
  });
}

for (const phase of ['fetch', 'blob']) {
  test(`unmount cancellation during ${phase} neither downloads nor announces completion`, async (t) => {
    const wait = deferred();
    const h = harness(t, {
      fetch: () => phase === 'fetch'
        ? wait.promise
        : Promise.resolve({ ...okResponse(), blob: () => wait.promise }),
    });
    const running = h.action.run();
    await Promise.resolve();
    h.action.cancel();
    assert.equal(h.requests[0].init.signal.aborted, true);
    h.focused = 'another-page';
    wait.resolve(phase === 'fetch' ? okResponse() : savedBlob());
    await running;
    assert.deepEqual(h.statuses, ['preparing']);
    assert.deepEqual(h.blobs, []);
    assert.equal(h.focused, 'another-page');
  });
}

test('cancellation during anchor activation still removes the anchor and revokes its URL', async (t) => {
  const h = harness(t, { onClick: (action) => action.cancel() });
  await h.action.run();
  assert.deepEqual(h.statuses, ['preparing']);
  assert.deepEqual(h.events.slice(-3), ['click', 'remove', 'revoke-url']);
  assert.deepEqual(h.revoked, ['blob:synthetic-owner-export']);
});

test('source-only Lingui descriptors select exact active-locale export copy', async () => {
  // Use the installed Vite compiler and real React/Lingui hook in memory.
  // This checks source fallback, not catalog synchronization or rendered QA.
  const [{ transformSync }, { setupI18n }, { I18nProvider }, React, { renderToStaticMarkup }] = await Promise.all([
    import('@swc/core'),
    import('@lingui/core'),
    import('@lingui/react'),
    import('react'),
    import('react-dom/server'),
  ]);
  const source = await readFile(new URL('../src/components/trail-course-review/copy.tsx', import.meta.url), 'utf8');
  const { code } = transformSync(source, {
    filename: 'copy.tsx',
    jsc: {
      parser: { syntax: 'typescript', tsx: true },
      target: 'es2022',
      experimental: {
        plugins: [[createRequire(import.meta.url).resolve('@lingui/swc-plugin'), {
          descriptorFields: 'message',
        }]],
      },
    },
    module: { type: 'es6' },
  });
  const resolved = code.replace(
    /from (['"])([^'"]+)\1/g,
    (_match, _quote, specifier) => `from ${JSON.stringify(import.meta.resolve(specifier))}`,
  );
  const { useTrailCourseReviewCopy } = await import(
    `data:text/javascript;base64,${Buffer.from(resolved).toString('base64')}`
  );
  const amendment = await readFile(new URL('../../docs/dev/trail-running-plan-export-experience-amendment-v3.md', import.meta.url), 'utf8');
  const rows = [...amendment.matchAll(/^\| (Menu label|Supporting copy|Busy|Success|Error) \| \*\*(.+)\*\* \| \*\*(.+)\*\* \|$/gm)];
  const keys = ['export', 'exportSupport', 'exportBusy', 'exportSuccess', 'exportError'];
  assert.equal(rows.length, keys.length);
  for (const [locale, column] of [['en', 2], ['zh', 3]]) {
    const i18n = setupI18n({ locale, messages: { [locale]: {} } });
    let actual;
    function Probe() {
      actual = useTrailCourseReviewCopy().copy;
      return null;
    }
    renderToStaticMarkup(React.createElement(I18nProvider, { i18n }, React.createElement(Probe)));
    for (const [index, key] of keys.entries()) {
      assert.equal(actual[key], rows[index][column], `${locale}: ${key}`);
      assert.notEqual(actual[key], rows[index][column === 2 ? 3 : 2]);
    }
  }
});
