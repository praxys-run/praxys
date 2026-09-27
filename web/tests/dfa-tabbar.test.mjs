import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { setTabBarHidden, setTabBarSelected } from '../../miniapp/utils/tabbar.ts';

function analysisPage(mode) {
  let definition;
  const callbacks = [], updates = [];
  const tabBar = { data: { hidden: false }, setData(data) { updates.push({ ...data }); Object.assign(this.data, data); } };
  const modules = {
    '../../utils/tabbar': { setTabBarHidden, setTabBarSelected },
    '../../utils/i18n': { detectLocale: () => 'en', t: value => value },
    '../../utils/theme': { themeClassName: () => 'theme-light', applyThemeChrome() {} },
    '../../utils/heat-adaptation': { emptyHeatAdaptationView: () => ({}), HEAT_HISTORY_SCROLL_KEY: 'test-key', HEAT_HISTORY_SCROLL_TARGET: 'test-target' },
  };
  const source = readFileSync(new URL('../../miniapp/pages/analysis/index.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
  } }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'Page', 'getApp', 'wx', code)(
    name => modules[name] ?? {}, module, module.exports, value => { definition = value; },
    () => ({ globalData: { locale: 'en', themeClass: 'theme-light' } }),
    { getStorageSync: () => '' },
  );
  const page = {
    data: structuredClone(definition.data),
    setData(data) { Object.assign(this.data, data); },
    getTabBar(callback) { if (mode === 'sync') return tabBar; callbacks.push(callback); },
  };
  for (const [name, method] of Object.entries(definition)) if (typeof method === 'function') page[name] = method.bind(page);
  page.refetch = async () => {};
  const flush = (reverse = false) => {
    const pending = callbacks.splice(0);
    for (const callback of reverse ? pending.reverse() : pending) callback(tabBar);
  };
  const open = () => page.onOpenDFA({ detail: { activityId: 'dfa-synthetic-running', activityDate: '2026-09-27' } });
  return { page, tabBar, updates, flush, open };
}

for (const mode of ['sync', 'async']) {
  test(`actual Analysis lifecycle owns and restores its DFA tab bar (${mode})`, () => {
    const scene = analysisPage(mode);
    const { page, tabBar, flush, open } = scene;
    page.data.activeSection = 'activities';
    page.data.scrollIntoView = 'existing-list-position';
    page.onShow(); flush();
    assert.equal(tabBar.data.hidden, false);
    open(); flush();
    assert.equal(tabBar.data.hidden, true);
    page.onHide(); flush();
    assert.equal(tabBar.data.hidden, false);
    assert.equal(page.data.dfaActivityId, 'dfa-synthetic-running');
    page.onShow(); flush();
    assert.equal(tabBar.data.hidden, true);
    assert.equal(page.data.activeSection, 'activities');
    assert.equal(page.data.scrollIntoView, 'existing-list-position');
    page.onCloseDFA(); flush();
    assert.equal(tabBar.data.hidden, false);
    assert.equal(page.data.dfaActivityId, '');
    open(); flush();
    page.onUnload(); flush();
    assert.equal(tabBar.data.hidden, false);
  });
}

test('late Skyline callbacks use current DFA/page state after close, hide, show and unload', () => {
  const { page, tabBar, updates, flush, open } = analysisPage('async');
  open(); page.onCloseDFA(); flush(true);
  assert.equal(tabBar.data.hidden, false);
  assert.ok(updates.every(update => update.hidden === false));
  updates.length = 0;
  open(); page.onHide(); page.onShow(); flush(true);
  assert.equal(tabBar.data.hidden, true);
  assert.ok(updates.filter(update => 'hidden' in update).every(update => update.hidden === true));
  updates.length = 0;
  open(); page.onUnload(); flush(true);
  assert.equal(tabBar.data.hidden, false);
  assert.ok(updates.every(update => update.hidden === false));
});

test('DFA cleanup updates only its owning page tab-bar instance', () => {
  const owner = analysisPage('async'), other = analysisPage('sync');
  other.open();
  owner.open(); owner.page.onHide(); owner.flush(true);
  assert.equal(owner.tabBar.data.hidden, false);
  assert.equal(other.tabBar.data.hidden, true);
});
