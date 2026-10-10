import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { setTabBarHidden, setTabBarSelected } from '../../miniapp/utils/tabbar.ts';

function analysisPage(mode) {
  let definition;
  const callbacks = [], updates = [], navigations = [];
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
    { getStorageSync: () => '', navigateTo: ({url}) => navigations.push(url) },
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
  return { page, tabBar, updates, navigations, flush, open };
}

for (const mode of ['sync','async']) {
  test(`DFA shortcut opens full native report and preserves Analysis state (${mode})`, () => {
    const scene=analysisPage(mode);
    scene.page.data.activeSection='activities';
    scene.page.data.scrollIntoView='existing-list-position';
    scene.page.onShow(); scene.flush(); scene.open(); scene.flush();
    assert.deepEqual(scene.navigations,['/pages/activity-detail/index?id=dfa-synthetic-running&section=dfa']);
    assert.equal(scene.tabBar.data.hidden,false);
    assert.equal(scene.page.data.activeSection,'activities');
    assert.equal(scene.page.data.scrollIntoView,'existing-list-position');
    assert.equal(scene.page.data.dfaActivityId,'');
  });
}
