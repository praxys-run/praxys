import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRequire } from 'node:module';
import { createDailyCoachRefetchInterval, needsCoachSnapshotRefresh } from '../src/lib/coach-refresh.ts';

const require = createRequire(import.meta.url);

async function renderCoach({ status = 'unavailable', error = null, errorStatus = null, loading = false, aiAvailable = true, stale = false, insight = null, snapshot = 'synthetic', responseSnapshot = 'synthetic', contentVersion, regenerate = false } = {}) {
  const source = await readFile(new URL('../src/components/AiInsightsCard.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const response = { content_status: status, ai_available: aiAvailable, snapshot: responseSnapshot, insight, content_version: contentVersion };
  const modules = {
    '@/hooks/useApi': { getAuthCacheScope: () => 'synthetic-account', useApi: () => ({
      data: response,
      error, errorStatus, loading, stale, refetch: async () => {},
    }) },
    '@lingui/core/macro': { msg: strings => strings.join('') },
    '@lingui/react/macro': {
      useLingui: () => ({ i18n: { _: value => value } }),
      Trans: ({ children }) => children,
      Plural: () => null,
    },
    '@/contexts/LocaleContext': { useLocale: () => ({ locale: 'en' }) },
    'react-router-dom': { Link: ({ children }) => children },
    '@/lib/science-links': { linkifyScienceTerms: text => text },
    '@/lib/coach-refresh': { createDailyCoachRefetchInterval, needsCoachSnapshotRefresh },
    '@/components/ui/button': { Button: ({ variant, ...props }) => React.createElement('button', props) },
  };
  const sandbox = { exports: {}, require: name => modules[name] ?? require(name) };
  vm.runInNewContext(code, sandbox);
  return renderToStaticMarkup(React.createElement(sandbox.exports.default, {
    insightType: 'daily_brief', snapshot,
    fallback: { headline: 'Synthetic training metrics' },
    onRegenerate: regenerate ? async () => {} : undefined,
  }));
}

const readyInsight = {
  snapshot: 'synthetic', content_version: 'morning-coach-v2',
  generated_at: '2026-10-13T14:45:00Z', as_of_date: '2026-10-14',
  feedback_allowed: true,
  headline: 'Current Coach summary', summary: 'Synthetic recovery observations.',
  findings: [], recommendations: ['Follow the planned session.'], meta: {},
  translations: { en: {
    headline: 'Current Coach summary', summary: 'Synthetic recovery observations.',
    findings: [], recommendations: ['Follow the planned session.'],
  } },
};

test('query cache expiry does not erase a snapshot-matched Coach result', async () => {
  const html = await renderCoach({ status: 'ready', stale: true, insight: readyInsight });
  assert.match(html, /Current Coach summary/);
  assert.match(html, /Follow the planned session/);
  assert.doesNotMatch(html, /waiting for a current analysis/);
});

test('the server rendering version remains authoritative across application updates', async () => {
  const insight = { ...readyInsight, content_version: 'morning-coach-v3' };
  assert.match(await renderCoach({ status: 'ready', insight, contentVersion: 'morning-coach-v3' }), /Current Coach summary/);
  assert.doesNotMatch(await renderCoach({ status: 'ready', insight, contentVersion: 'morning-coach-v2' }), /Current Coach summary/);
});

test('unverified stale content, outages, mismatched snapshots and revoked access still exclude Coach', async () => {
  for (const state of [
    { status: 'stale' }, { status: 'unavailable' }, { aiAvailable: false },
    ...[401, 403, 428].map(errorStatus => ({ error: 'Access denied', errorStatus })),
    { snapshot: 'replacement' },
    { insight: { ...readyInsight, content_version: 'old' } },
  ]) {
    const html = await renderCoach({ status: 'ready', insight: readyInsight, ...state });
    assert.doesNotMatch(html, /Current Coach summary/);
    assert.match(html, /Synthetic training metrics/);
  }
});

test('verified historical Coach survives date, snapshot and renderer-version changes with its generation time', async () => {
  const html = await renderCoach({ status: 'stale', contentVersion: 'morning-coach-v3',
    insight: { ...readyInsight, snapshot: 'previous', feedback_allowed: false } });
  assert.match(html, /Current Coach summary/);
  assert.match(html, /Previous insight/);
  assert.match(html, /Generated/);
  assert.match(html, /Showing the previous insight/);
  assert.doesNotMatch(html, /needs an updated analysis/);
  assert.match(html, /13\/10\/2026/);
  assert.doesNotMatch(html, /14\/10\/2026/);
  assert.doesNotMatch(html, /Was this helpful/);
});

test('a transient refresh failure or loading state retains the last verified Coach instead of replacing it', async () => {
  for (const state of [{ error: 'HTTP 503' }, { loading: true }, { regenerate: true }]) {
    const html = await renderCoach({ status: 'ready', insight: readyInsight, ...state });
    assert.match(html, /Current Coach summary/);
    assert.doesNotMatch(html, /Synthetic training metrics/);
    assert.match(html, /Generated/);
  }
});

test('a failed historical read offers refresh, not an unnecessary new generation', async () => {
  const html = await renderCoach({ status: 'stale', error: 'HTTP 503', regenerate: true,
    insight: { ...readyInsight, snapshot: 'previous', feedback_allowed: false } });
  assert.match(html, /Current Coach summary/);
  assert.match(html, />Refresh<\/button>/);
  assert.doesNotMatch(html, />Sync now<\/button>/);
});

test('mounted Coach retains content across snapshot revalidation, replaces it on success, and isolates accounts', async () => {
  const source = await readFile(new URL('../src/components/AiInsightsCard.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const slots = [];
  let cursor = 0;
  let changed = false;
  let scope = 'first-account';
  let state = { data: { content_status: 'ready', ai_available: true, snapshot: 'synthetic', insight: readyInsight } };
  const modules = {
    react: {
      useState(initial) {
        const index = cursor++;
        if (!(index in slots)) slots[index] = initial;
        return [slots[index], value => { slots[index] = value; changed = true; }];
      },
      useRef(initial) {
        const index = cursor++;
        return slots[index] ??= { current: initial };
      },
      useMemo: fn => fn(), useEffect() {}, useLayoutEffect() {},
    },
    '@/hooks/useApi': { getAuthCacheScope: () => scope, useApi: () => state },
    '@lingui/core/macro': { msg: strings => strings.join('') },
    '@lingui/react/macro': { Trans: ({ children }) => children, Plural: () => null, useLingui: () => ({ i18n: { _: value => value } }) },
    '@/contexts/LocaleContext': { useLocale: () => ({ locale: 'en' }) },
    'react-router-dom': { Link: ({ children }) => children },
    '@/lib/science-links': { linkifyScienceTerms: text => text },
    '@/lib/coach-refresh': { createDailyCoachRefetchInterval, needsCoachSnapshotRefresh },
    '@/components/ui/button': { Button: ({ variant, ...props }) => React.createElement('button', props) },
  };
  const sandbox = { exports: {}, require: name => modules[name] ?? require(name) };
  vm.runInNewContext(code, sandbox);
  const render = snapshot => {
    let tree;
    for (let pass = 0; pass < 10; pass += 1) {
      cursor = 0; changed = false;
      tree = sandbox.exports.default({ insightType: 'daily_brief', snapshot });
      if (!changed) return renderToStaticMarkup(tree);
    }
    throw new Error('Coach did not settle');
  };
  assert.match(render('synthetic'), /Current Coach summary/);
  state = { data: null, loading: true };
  assert.match(render('next'), /Current Coach summary/);
  assert.match(render('next'), /Previous insight/);
  state = { data: null, error: 'Network interrupted' };
  assert.match(render('next'), /Current Coach summary/);
  const replacement = { ...readyInsight, snapshot: 'next',
    translations: { en: { ...readyInsight.translations.en, headline: 'New successful analysis' } } };
  state = { data: { content_status: 'ready', ai_available: true, snapshot: 'next', insight: replacement } };
  assert.match(render('next'), /New successful analysis/);
  assert.doesNotMatch(render('next'), /Current Coach summary/);
  state = { data: null, loading: true };
  scope = 'second-account';
  assert.doesNotMatch(render('next'), /New successful analysis|Current Coach summary/);
  scope = 'first-account';
  assert.doesNotMatch(render('next'), /New successful analysis/);
});

test('Today sync rereads the mounted Coach even when the training snapshot is unchanged', async () => {
  const source = await readFile(new URL('../src/pages/Today.tsx', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('Today.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let handler;
  function walk(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'handleSyncNow') handler = node.initializer;
    ts.forEachChild(node, walk);
  }
  walk(ast);
  assert.ok(handler);
  const events = [];
  const sandbox = {
    setTimeout: resolve => resolve(),
    setSyncing: value => events.push(['syncing', value]),
    setSyncError() {},
    getAuthHeaders: () => ({}),
    apiFetch: async url => ({ ok: true, json: async () => ({ garmin: { status: 'done' } }) }),
    refetch: async () => events.push(['today']),
    queryClient: { invalidateQueries: async options => {
      assert.equal(options.type, 'active');
      assert.equal(options.predicate({ queryKey: ['/api/insights/daily_brief?snapshot=unchanged', 'current-account'] }), true);
      assert.equal(options.predicate({ queryKey: ['/api/insights/training_review', 'current-account'] }), false);
      events.push(['coach']);
    } },
  };
  const code = ts.transpileModule(`globalThis.handle = ${handler.getText(ast)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(code, sandbox);
  await sandbox.handle();
  assert.deepEqual(events, [['syncing', true], ['today'], ['coach'], ['syncing', false]]);
});

test('failed generation preserves metrics and explains retry without a read-only refresh', async () => {
  const html = await renderCoach();
  assert.match(html, /Sync your data to try again/);
  assert.match(html, /Synthetic training metrics/);
  assert.doesNotMatch(html, /<button/);
});

test('refresh stays actionable for pending, stale and failed reads, but not provider outages or loading', async () => {
  for (const state of [{ status: 'pending' }, { status: 'stale', responseSnapshot: 'replacement' }, { error: 'HTTP 503' }]) {
    const html = await renderCoach(state);
    assert.match(html, /<button[^>]*cursor-pointer[^>]*>Refresh<\/button>/);
    assert.match(html, /min-h-11 min-w-11/);
  }
  assert.doesNotMatch(await renderCoach({ aiAvailable: false }), /<button/);
  assert.doesNotMatch(await renderCoach({ loading: true }), /<button/);
});

test('same-snapshot outdated content offers explicit generation instead of a read-only refresh', async () => {
  const html = await renderCoach({ status: 'stale', regenerate: true });
  assert.match(html, /needs an updated analysis/);
  assert.match(html, />Sync now<\/button>/);
  assert.doesNotMatch(html, />Refresh<\/button>/);
});

test('miniapp refresh has the same failure, outage and loading semantics', async () => {
  const wxml = await readFile(new URL('../../miniapp/components/coach-receipt/index.wxml', import.meta.url), 'utf8');
  const condition = wxml.match(/wx:(?:if|elif)="{{([^}]+)}}"[^>]+bindtap="refresh"/)?.[1];
  assert.ok(condition);
  const visible = values => vm.runInNewContext(condition, {
    loading: false, failed: false, regenerating: false, needsGeneration: true,
    response: { ai_available: true, content_status: 'unavailable' },
    ...values,
  });
  assert.equal(visible({}), false);
  assert.equal(visible({ failed: true }), true);
  assert.equal(visible({ response: { ai_available: true, content_status: 'stale' }, needsGeneration: false }), true);
  assert.equal(visible({ response: { ai_available: false } }), false);
  assert.equal(visible({ loading: true, failed: true }), false);
});

async function loadRefetch(pageName, apiGet, { methodName = 'refetch', apiPost } = {}) {
  const filename = new URL(`../../miniapp/pages/${pageName}/index.ts`, import.meta.url);
  const source = await readFile(filename, 'utf8');
  const ast = ts.createSourceFile(filename.pathname, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  let method;
  function walk(node) {
    if (ts.isCallExpression(node) && node.expression.getText(ast) === 'Page') {
      method = node.arguments[0].properties.find(property => property.name?.getText(ast) === methodName);
    }
    ts.forEachChild(node, walk);
  }
  walk(ast);
  assert.ok(method, 'Exercise the actual page method');
  const code = ts.transpileModule(`globalThis.refetch = ({${method.getText(ast)}}).${methodName}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = {
    console: { warn() {} }, apiGet, apiPost, setTimeout: resolve => resolve(),
    fetchInsight: async () => ({ insight: null, ai_available: true, content_status: 'pending' }),
  };
  vm.runInNewContext(code, context);
  return context.refetch;
}

function page() {
  return {
    data: { hasResponse: true, coachLoading: false, coachResponse: { content_status: 'ready' }, coachFailed: false },
    setData(patch) { Object.assign(this.data, patch); },
  };
}

test('miniapp rejected sync retains metrics, shows failure and allows an explicit retry', async () => {
  let rejectSync = true;
  let statusReads = 0;
  let refreshes = 0;
  const sync = await loadRefetch('today', async () => {
    statusReads += 1;
    return { garmin: { status: 'done' } };
  }, { methodName: 'onStaleSyncNow', apiPost: async () => {
    if (rejectSync) throw { code: 'HTTP_ERROR', status: 503 };
  } });
  const target = page();
  const metrics = { headline: 'Cached synthetic metrics', findings: [], recommendations: [] };
  target.data.coach = metrics;
  target.refetch = async () => { refreshes += 1; };
  await sync.call(target);
  assert.equal(target.data.coachSyncFailed, true);
  assert.equal(target.data.staleSyncing, false);
  assert.equal(target.data.hasResponse, true);
  assert.equal(target.data.coach, metrics);
  assert.equal(statusReads, 0);
  assert.equal(refreshes, 0);

  const source = await readFile(new URL('../../miniapp/components/coach-receipt/index.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  let component;
  const sandbox = { exports: {}, Component: value => { component = value; }, require: name => {
    if (name === '../../utils/i18n') return { t: text => text, detectLocale: () => 'en' };
    if (name === '../../utils/insights') return {
      coachToggleLabel: () => '', insightFeedbackState: () => ({}), localizedInsight: () => null,
    };
    throw new Error(`Unexpected module ${name}`);
  } };
  vm.runInNewContext(code, sandbox);
  const receipt = {
    data: { ...target.data, loading: false, regenerating: false, insightType: 'daily_brief', snapshot: 'synthetic',
      syncFailed: target.data.coachSyncFailed, failed: false, fallback: metrics,
      response: { content_status: 'stale', snapshot: 'synthetic', ai_available: true }, canRegenerate: true },
    setData(patch) { Object.assign(this.data, patch); },
  };
  component.methods.rebuild.call(receipt);
  assert.equal(receipt.data.statusText, "Couldn't sync data. Try again.");
  assert.equal(receipt.data.receipt, metrics);
  const wxml = await readFile(new URL('../../miniapp/components/coach-receipt/index.wxml', import.meta.url), 'utf8');
  const condition = wxml.match(/wx:if="{{([^}]+)}}"[^>]+bindtap="regenerate"/)?.[1];
  assert.ok(condition);
  assert.equal(vm.runInNewContext(condition, { ...receipt.data, needsGeneration: false }), true);
  const todayWxml = await readFile(new URL('../../miniapp/pages/today/index.wxml', import.meta.url), 'utf8');
  assert.match(todayWxml, /sync-failed="{{coachSyncFailed}}"/);

  rejectSync = false;
  await sync.call(target);
  assert.equal(target.data.coachSyncFailed, false);
  assert.equal(target.data.staleSyncing, false);
  assert.equal(statusReads, 1);
  assert.equal(refreshes, 1);
});

for (const name of ['today', 'analysis']) {
  test(`${name}: failed background dataset refresh settles Coach and retains metrics`, async () => {
    const refetch = await loadRefetch(name, async () => { throw { code: 'NETWORK_ERROR', detail: 'Synthetic failure' }; });
    const target = page();
    await refetch.call(target, { background: true });
    assert.equal(target.data.hasResponse, true);
    assert.equal(target.data.coachResponse?.content_status ?? null, name === 'today' ? 'ready' : null);
    assert.equal(target.data.coachLoading, false);
    assert.equal(target.data.coachFailed, true);
  });

  test(`${name}: superseded fetch failure cannot settle the replacement request`, async () => {
    let reject;
    const refetch = await loadRefetch(name, () => new Promise((_, fail) => { reject = fail; }));
    const target = page();
    const pending = refetch.call(target, { background: true });
    target._refetchRequestId += 1;
    const replacement = { content_status: 'ready' };
    target.setData({ coachResponse: replacement, coachLoading: true, coachFailed: false });
    reject({ code: 'NETWORK_ERROR', detail: 'Obsolete failure' });
    await pending;
    assert.equal(target.data.coachResponse, replacement);
    assert.equal(target.data.coachLoading, true);
    assert.equal(target.data.coachFailed, false);
  });
}

for (const status of [401, 403, 428]) {
  test(`miniapp Today clears retained Coach when refresh revokes access (${status})`, async () => {
    const refetch = await loadRefetch('today', async () => { throw { status }; });
    for (const background of [false, true]) {
      const target = page();
      await refetch.call(target, { background });
      assert.equal(target.data.coachResponse, null);
      assert.equal(target.data.hasResponse, false);
      assert.equal(target.data.coachFailed, true);
    }
  });
}

test('miniapp foreground refresh failure keeps the parent page and its historical Coach visible with read-only retry', async () => {
  const refetch = await loadRefetch('today', async () => {
    throw { code: 'NETWORK_ERROR', detail: 'Synthetic failure' };
  });
  const target = page();
  const historical = { content_status: 'stale', ai_available: true, insight: { ...readyInsight, feedback_allowed: false } };
  target.data.coachResponse = historical;
  await refetch.call(target);
  assert.equal(target.data.hasResponse, true);
  assert.equal(target.data.loading, false);
  assert.equal(target.data.errorMessage, '');
  assert.equal(target.data.coachResponse, historical);
  assert.equal(target.data.coachFailed, true);
  assert.equal(target.data.coachLoading, false);
  const pageWxml = await readFile(new URL('../../miniapp/pages/today/index.wxml', import.meta.url), 'utf8');
  const blockingConditions = [...pageWxml.matchAll(/<block wx:(?:if|elif)="{{([^}]+)}}">/g)].slice(0, 3);
  assert.equal(blockingConditions.length, 3);
  assert.ok(blockingConditions.every(([, condition]) => !vm.runInNewContext(condition, target.data)));
  const receiptWxml = await readFile(new URL('../../miniapp/components/coach-receipt/index.wxml', import.meta.url), 'utf8');
  const refreshCondition = receiptWxml.match(/wx:elif="{{([^}]+)}}"[^>]+bindtap="refresh"/)?.[1];
  assert.ok(refreshCondition);
  assert.equal(vm.runInNewContext(refreshCondition, {
    loading: target.data.coachLoading, failed: target.data.coachFailed, regenerating: false,
    response: historical, needsGeneration: true,
  }), true);

  const empty = page();
  empty.data.hasResponse = false;
  empty.data.coachResponse = null;
  await refetch.call(empty);
  assert.equal(empty.data.hasResponse, false);
  assert.equal(empty.data.errorMessage, 'Synthetic failure');
});

test('historical Coach keeps polling so a successful replacement can appear without another sync', () => {
  const interval = createDailyCoachRefetchInterval();
  assert.equal(interval({ state: { data: { content_status: 'stale', ai_available: true, insight: readyInsight }, error: null } }), 60_000);
  assert.equal(interval({ state: { data: { content_status: 'stale', ai_available: true, insight: null }, error: null } }), false);
});

test('miniapp receipt retains verified historical content and timestamp through loading and failed refresh', async () => {
  const source = await readFile(new URL('../../miniapp/components/coach-receipt/index.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  let definition;
  const sandbox = { exports: {}, Component: value => { definition = value; }, require: name => {
    if (name === '../../utils/i18n') return { t: text => text, detectLocale: () => 'en' };
    if (name === '../../utils/insights') return {
      coachToggleLabel: () => '', localizedInsight: insight => insight.translations.en,
      insightFeedbackState: insight => ({ datasetHash: insight?.feedback_allowed ? insight.meta.dataset_hash : '', vote: '' }),
    };
    throw new Error(`Unexpected module ${name}`);
  } };
  vm.runInNewContext(code, sandbox);
  const originalRefs = [{ pillar: 'load', theory_id: 'original', label: 'Original method' }];
  const component = {
    data: {
      ...definition.data, insightType: 'daily_brief', snapshot: 'synthetic',
      response: { ai_available: true, snapshot: 'synthetic', content_status: 'stale', content_version: 'morning-coach-v3',
        insight: { ...readyInsight, snapshot: 'previous', feedback_allowed: false, theory_refs: originalRefs,
          meta: { dataset_hash: 'a'.repeat(64) } } },
    },
    setData(patch) { Object.assign(this.data, patch); },
  };
  for (const state of [{}, { loading: true }, { loading: false, failed: true }]) {
    Object.assign(component.data, state);
    definition.methods.rebuild.call(component);
    assert.equal(component.data.receipt.headline, readyInsight.headline);
    assert.equal(component.data.previousInsight, true);
    assert.match(component.data.receipt.stamp, /13\/10\/2026/);
    assert.equal(component.data.datasetHash, '');
    assert.equal(component.data.refs, originalRefs);
  }
  component.data.response = { ai_available: false, content_status: 'unavailable', insight: null };
  definition.methods.rebuild.call(component);
  assert.equal(component.data.isAi, false);
});
