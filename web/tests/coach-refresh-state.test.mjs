import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

async function renderCoach({ status = 'unavailable', error = null, loading = false, aiAvailable = true } = {}) {
  const source = await readFile(new URL('../src/components/AiInsightsCard.tsx', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const modules = {
    '@/hooks/useApi': { useApi: () => ({
      data: { content_status: status, ai_available: aiAvailable, snapshot: 'synthetic' },
      error, loading, stale: false, refetch: async () => {},
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
    '@/components/ui/button': { Button: ({ variant, ...props }) => React.createElement('button', props) },
  };
  const sandbox = { exports: {}, require: name => modules[name] ?? require(name) };
  vm.runInNewContext(code, sandbox);
  return renderToStaticMarkup(React.createElement(sandbox.exports.default, {
    insightType: 'daily_brief', snapshot: 'synthetic',
    fallback: { headline: 'Synthetic training metrics' },
  }));
}

test('failed generation preserves metrics and explains retry without a read-only refresh', async () => {
  const html = await renderCoach();
  assert.match(html, /Sync your data to try again/);
  assert.match(html, /Synthetic training metrics/);
  assert.doesNotMatch(html, /<button/);
});

test('refresh stays actionable for pending, stale and failed reads, but not provider outages or loading', async () => {
  for (const state of [{ status: 'pending' }, { status: 'stale' }, { error: 'HTTP 503' }]) {
    const html = await renderCoach(state);
    assert.match(html, /<button[^>]*cursor-pointer[^>]*>Refresh<\/button>/);
    assert.match(html, /min-h-11 min-w-11/);
  }
  assert.doesNotMatch(await renderCoach({ aiAvailable: false }), /<button/);
  assert.doesNotMatch(await renderCoach({ loading: true }), /<button/);
});

test('miniapp refresh has the same failure, outage and loading semantics', async () => {
  const wxml = await readFile(new URL('../../miniapp/components/coach-receipt/index.wxml', import.meta.url), 'utf8');
  const condition = wxml.match(/wx:if="{{([^}]+)}}"[^>]+bindtap="refresh"/)?.[1];
  assert.ok(condition);
  const visible = values => vm.runInNewContext(condition, {
    loading: false, failed: false,
    response: { ai_available: true, content_status: 'unavailable' },
    ...values,
  });
  assert.equal(visible({}), false);
  assert.equal(visible({ failed: true }), true);
  assert.equal(visible({ response: { ai_available: true, content_status: 'stale' } }), true);
  assert.equal(visible({ response: { ai_available: false } }), false);
  assert.equal(visible({ loading: true, failed: true }), false);
});

async function loadRefetch(pageName, apiGet) {
  const filename = new URL(`../../miniapp/pages/${pageName}/index.ts`, import.meta.url);
  const source = await readFile(filename, 'utf8');
  const ast = ts.createSourceFile(filename.pathname, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  let method;
  function walk(node) {
    if (ts.isCallExpression(node) && node.expression.getText(ast) === 'Page') {
      method = node.arguments[0].properties.find(property => property.name?.getText(ast) === 'refetch');
    }
    ts.forEachChild(node, walk);
  }
  walk(ast);
  assert.ok(method, 'Exercise the actual page refetch method');
  const code = ts.transpileModule(`globalThis.refetch = ({${method.getText(ast)}}).refetch`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = {
    console: { warn() {} }, apiGet,
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
