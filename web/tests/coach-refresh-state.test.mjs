import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';

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
