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

async function renderCoach({ status = 'unavailable', error = null, loading = false, aiAvailable = true, stale = false, insight = null, snapshot = 'synthetic', responseSnapshot = 'synthetic', contentVersion, regenerate = false } = {}) {
  const source = await readFile(new URL('../src/components/AiInsightsCard.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const modules = {
    '@/hooks/useApi': { useApi: () => ({
      data: { content_status: status, ai_available: aiAvailable, snapshot: responseSnapshot, insight, content_version: contentVersion },
      error, loading, stale, refetch: async () => {},
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

test('server freshness, snapshot, version and failed reads still exclude Coach content', async () => {
  for (const state of [
    { status: 'stale' }, { status: 'unavailable' }, { aiAvailable: false }, { error: 'HTTP 503' },
    { snapshot: 'replacement' },
    { insight: { ...readyInsight, content_version: 'old' } },
  ]) {
    const html = await renderCoach({ status: 'ready', insight: readyInsight, ...state });
    assert.doesNotMatch(html, /Current Coach summary/);
    assert.match(html, /Synthetic training metrics/);
  }
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
      syncFailed: target.data.coachSyncFailed, fallback: metrics,
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
    assert.equal(target.data.coachResponse, null);
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
