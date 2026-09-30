import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { transformSync } from '@swc/core';
import * as React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { getChartColors } from '../src/lib/chart-theme.ts';
import { activityFixture, allMetricFixture } from './helpers/activity-fixture.mjs';
import { markupTree, markupNodes, textContent, renderLocalized } from './helpers/trail-component-harness.mjs';

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL('../src/', import.meta.url));

function components(detail) {
  const cache = new Map();
  const load = (relative) => {
    let filename = path.resolve(root, relative);
    if (!existsSync(filename)) filename = ['.tsx', '.ts'].map((ext) => filename + ext).find(existsSync);
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    const { code } = transformSync(readFileSync(filename, 'utf8'), {
      filename, jsc: { parser: { syntax: 'typescript', tsx: filename.endsWith('.tsx') }, target: 'es2022',
        transform: { react: { runtime: 'automatic' } },
        experimental: { plugins: [[require.resolve('@lingui/swc-plugin'), { descriptorFields: 'message' }]] } },
      module: { type: 'commonjs' },
    });
    new Function('require', 'module', 'exports', code)((specifier) => {
      if (specifier.endsWith('.css')) return {};
      if (specifier === '@/contexts/LocaleContext') return { useLocale: () => ({ locale: 'en' }) };
      if (specifier === '@/hooks/useChartColors') return { useChartColors: () => getChartColors(false) };
      if (specifier === '@/hooks/useApi') return { useApi: () => ({ data: detail, loading: false, error: null }) };
      if (specifier.startsWith('@/')) return load(specifier.slice(2));
      if (specifier.startsWith('.')) return load(path.resolve(path.dirname(filename), specifier));
      return require(specifier);
    }, module, module.exports);
    return module.exports;
  };
  return load;
}

function render(Component, props = {}) {
  return markupTree(renderLocalized(React.createElement(MemoryRouter, null, React.createElement(Component, props))));
}
const tagged = (node, tag) => markupNodes(node, (child) => child.tag === tag);
const withClass = (node, name) => markupNodes(node, (child) => (child.attributes.class ?? '').split(' ').includes(name));

test('history uses one native report link whose name includes facts; split and DFA controls are siblings', () => {
  const detail = activityFixture();
  const card = render(components(detail)('components/ActivityCard').default, { activity: detail.activity, activityDetailAvailable: true });
  const [link] = tagged(card, 'a');
  assert.equal(tagged(card, 'a').length, 1);
  assert.equal(link.attributes.href, '/history/native-synthetic-running');
  assert.equal(link.attributes['aria-label'], undefined);
  for (const fact of ['Running', 'Sep 27, 2026', 'Distance 3.3 km', 'Duration 22:00', 'Pace 6:40 /km', 'View report']) assert.ok(textContent(link).includes(fact), fact);
  assert.equal(tagged(link, 'button').length, 0);
  assert.deepEqual(tagged(card, 'button').map(textContent), ['Recorded splits (2)', 'DFA α1']);
  assert.equal(tagged(card, 'button')[0].attributes['aria-expanded'], 'false');
});

test('history dates and secondary facts use readable dark text while keeping compact hierarchy', () => {
  const detail = activityFixture();
  for (const activityDetailAvailable of [true, false]) {
    const card = render(components(detail)('components/ActivityCard').default, { activity: detail.activity, activityDetailAvailable });
    const textNodes = withClass(card, 'text-muted-foreground').filter((node) => node.tag !== 'svg');
    assert.equal(textNodes.length, 2);
    for (const node of textNodes) {
      const classes = node.attributes.class.split(' ');
      assert.ok(classes.includes('dark:text-foreground'), textContent(node));
      assert.ok(classes.includes('text-xs'), textContent(node));
      assert.ok(!classes.includes('font-semibold'), textContent(node));
    }
    assert.ok(textContent(textNodes[0]).includes('Sep 27, 2026'));
    for (const fact of ['234 W', '147 bpm', '12 m', 'RSS 42', 'CP 250 W']) {
      assert.ok(textContent(textNodes[1]).includes(fact), fact);
    }
  }
});

test('demo history preserves factual body and independent secondary controls without a report link', () => {
  const detail = activityFixture();
  const card = render(components(detail)('components/ActivityCard').default, { activity: detail.activity, activityDetailAvailable: false });
  assert.equal(tagged(card, 'a').length, 0);
  assert.ok(!textContent(card).includes('View report'));
  assert.ok(textContent(card).includes('3.3 km'));
  assert.equal(tagged(card, 'button').length, 2);
});

test('additional summaries count displayed fields, deduplicate hero keys and contain only static definition rows', () => {
  const detail = activityFixture();
  const page = render(components(detail)('pages/ActivityDetail').default);
  const records = tagged(page, 'details').find((node) => node.attributes.id === 'activity-records');
  assert.equal(textContent(tagged(records, 'summary')[0]), 'Additional summaries (8)');
  assert.equal(tagged(records, 'dl').length, 1);
  assert.equal(tagged(records, 'dt').length, 8);
  assert.equal(tagged(records, 'dd').length, 8);
  assert.equal(tagged(records, 'button').length + tagged(records, 'a').length, 0);
  assert.ok(!textContent(records).includes('Average power'));
  assert.ok(!textContent(records).includes('Average pace'));
  assert.ok(textContent(records).includes('Average heart rate147 bpm'));
  assert.equal(markupNodes(records, (node) => 'tabindex' in node.attributes).length, 0);
  assert.ok(textContent(records).includes('Source reference; not a training assessment.'));
});

test('heart-rate hero and zero additional fields have no duplicate summaries or dead shortcut', () => {
  const detail = activityFixture('no_samples');
  for (const key of ['avg_power', 'max_power', 'max_hr', 'elevation_gain_m', 'temperature_c', 'relative_humidity_pct', 'rss', 'cp_estimate']) detail.activity[key] = null;
  const page = render(components(detail)('pages/ActivityDetail').default);
  assert.ok(textContent(page).includes('Average heart rate147bpm'));
  assert.equal(markupNodes(page, (node) => node.attributes.id === 'activity-records').length, 0);
  assert.ok(!textContent(page).includes('View summaries'));
  assert.equal(tagged(page, 'details').length, 1);
});

test('observation requires two actual valid endpoint paces; no fallback or source duplication', () => {
  for (const count of [0, 1, 2]) {
    const detail = activityFixture();
    detail.activity.splits = detail.activity.splits.slice(0, count);
    const page = render(components(detail)('pages/ActivityDetail').default);
    assert.equal(withClass(page, 'activity-report__observation').length, count === 2 ? 1 : 0);
    assert.ok(!textContent(page).includes('saved record is ready'));
    assert.ok(!textContent(page).includes('Read the run over time'));
    if (count === 2) {
      assert.ok(textContent(page).includes('First recorded split'));
      assert.ok(textContent(page).includes('Not an overall trend'));
      assert.ok(!textContent(withClass(page, 'activity-report__observation')[0]).includes('Garmin'));
    }
  }
  const detail = activityFixture();
  detail.activity.splits[1].avg_pace_min_km = 'invalid';
  assert.equal(withClass(render(components(detail)('pages/ActivityDetail').default), 'activity-report__observation').length, 0);
});

test('all fourteen metrics stay available in the top chooser and overlay with no bottom curve inventory', () => {
  const page = render(components(allMetricFixture())('pages/ActivityDetail').default);
  const extras = markupNodes(page, (node) => node.attributes.id === 'activity-extra-metrics')[0];
  assert.equal(tagged(extras, 'button').length, 11);
  assert.equal(tagged(page, 'option').length, 14);
  const names = tagged(extras, 'button').map(textContent);
  for (const label of ['Cadence', 'Speed', 'Altitude', 'Grade', 'Temperature', 'Ground contact time', 'Vertical oscillation', 'Vertical ratio', 'Leg spring stiffness', 'Form power', 'Respiration rate']) assert.ok(names.includes(label), label);
  assert.equal(withClass(page, 'activity-report__record-list').length, 0);
});

test('one collapsed disclosure scopes friendly source names and preserves distinct weather provenance', () => {
  const detail = activityFixture();
  detail.sample_sources = ['garmin', 'stryd', 'unknown'];
  const page = render(components(detail)('pages/ActivityDetail').default);
  const info = withClass(page, 'activity-report__data-info')[0];
  assert.equal(info.attributes.open, undefined);
  assert.equal(textContent(tagged(info, 'summary')[0]), 'Data information');
  assert.ok(textContent(info).includes('Same as activity record, Stryd, Unrecognized source name'));
  assert.ok(textContent(info).includes('Environment recordsGarmin activity weather'));
  assert.ok(!textContent(info).includes('garmin_activity_weather'));
  detail.activity.source = null;
  detail.sample_sources = ['unknown'];
  detail.activity.environment_source = null;
  const missing = render(components(detail)('pages/ActivityDetail').default);
  assert.ok(!textContent(missing).includes('Same as activity record'));
  assert.ok(textContent(missing).includes('Source unavailable'));
});

test('gap, reduced-display and time-origin constraints stay outside collapsed notes', () => {
  const detail = activityFixture('sparse');
  detail.sample_count = 60;
  detail.time_origin = 'sample_start';
  const page = render(components(detail)('pages/ActivityDetail').default);
  const statuses = withClass(page, 'activity-trace__foot')[0];
  for (const copy of ['Gaps in recorded data', 'Reduced display', 'Time from first sample; activity start unverified']) assert.ok(textContent(statuses).includes(copy));
  assert.equal(tagged(statuses, 'details').length, 0);
  assert.ok(textContent(page).includes('The recorded distance trace has missing intervals.'));
});

test('miniapp executes matching summary, source and independent-disclosure view data', async () => {
  const detail = activityFixture();
  let definition;
  const load = components(detail);
  const filename = path.resolve(root, '../../miniapp/pages/activity-detail/index.ts');
  const { code } = transformSync(readFileSync(filename, 'utf8'), {
    filename, jsc: { parser: { syntax: 'typescript' }, target: 'es2022' }, module: { type: 'commonjs' },
  });
  new Function('require', 'Page', 'getApp', 'exports', code)((specifier) => {
    if (specifier.endsWith('/api-client')) return { apiGet: async () => detail };
    if (specifier.endsWith('/i18n')) return { t: (value) => value, tNamed: (value, args) => value.replace('{count}', args.count), detectLocale: () => 'en' };
    if (specifier.endsWith('/theme')) return { resolveTheme: () => 'light' };
    return load(path.resolve(path.dirname(filename), specifier));
  }, (value) => { definition = value; }, () => ({ globalData: { themeClass: '' } }), {});
  const page = { ...definition, data: { ...definition.data }, setData(values) { Object.assign(this.data, values); } };
  await page.fetchDetail(detail.activity.activity_id);
  assert.equal(page.data.view.savedCount, 8);
  assert.equal(page.data.view.sourceRows, 'Stryd');
  assert.equal(page.data.view.environmentSource, 'Garmin activity weather');
  assert.equal(page.data.savedOpen, false);
  assert.equal(page.data.dataOpen, false);
  page.data.cursor = 390;
  page.data.rangeStart = 390;
  page.onToggleData();
  page.onToggleSaved();
  assert.equal(page.data.cursor, 390);
  assert.equal(page.data.rangeStart, 390);
  assert.equal(page.data.dataOpen, true);
  assert.equal(page.data.savedOpen, true);
  assert.equal(page.data.view.saved.some((row) => ['avg_power', 'avg_pace_min_km'].includes(row.key)), false);
});

test('miniapp history keeps native navigation, split preview and DFA dispatch independent for owner and demo', async () => {
  const detail = activityFixture();
  const filename = path.resolve(root, '../../miniapp/components/activity-history/index.ts');
  const template = readFileSync(filename.replace('.ts', '.wxml'), 'utf8');
  assert.match(template, /<navigator wx:if="\{\{item.detailAvailable\}\}" url="\{\{item.detailUrl\}\}">/);
  assert.doesNotMatch(template.match(/<navigator[\s\S]*?<\/navigator>/)[0], /<button/);
  assert.doesNotMatch(template.match(/<view wx:for="\{\{activities\}\}"[^>]+>/)[0], /bindtap|aria-role/);
  for (const allowed of [true, false]) {
    let definition;
    const navigations = [];
    const events = [];
    const load = components(detail);
    const { code } = transformSync(readFileSync(filename, 'utf8'), {
      filename, jsc: { parser: { syntax: 'typescript' }, target: 'es2022' }, module: { type: 'commonjs' },
    });
    new Function('require', 'Component', 'wx', 'exports', code)((specifier) => {
      if (specifier.endsWith('/api-client')) return { apiGet: async (url) => {
        assert.equal(url, '/api/history?limit=20&offset=0');
        return { activities: [detail.activity], total: 1, activity_detail_available: allowed };
      } };
      if (specifier.endsWith('/i18n')) return { t: (value) => value, tFmt: (value) => value, detectLocale: () => 'en' };
      return load(path.resolve(path.dirname(filename), specifier));
    }, (value) => { definition = value; }, { navigateTo: (value) => navigations.push(value) }, {});
    const history = { ...definition.methods, data: { ...definition.data },
      setData(values) { Object.assign(this.data, values); },
      triggerEvent(...args) { events.push(args); },
    };
    await history.refresh();
    assert.equal(history.data.activities[0].detailAvailable, allowed);
    assert.ok(history.data.activities[0].metrics.some((metric) => metric.value === '6:40 /km'));
    const event = { currentTarget: { dataset: { id: detail.activity.activity_id, date: detail.activity.date } } };
    history.toggleExpand(event);
    assert.equal(history.data.activities[0].expanded, true);
    assert.equal(navigations.length, 0);
    history.onDFA(event);
    assert.equal(events[0][0], 'dfa');
    assert.equal(events[0][1].activityDate, detail.activity.date);
    assert.equal(navigations.length, 0);
    history.openDetail(event);
    assert.equal(navigations.length, allowed ? 1 : 0);
    assert.equal(history.data.activities[0].expanded, true);
  }
});

test('distance-only and single-time data retain real limits without dead chart actions', () => {
  const distance = render(components(activityFixture('distance_only'))('pages/ActivityDetail').default);
  assert.equal(withClass(distance, 'activity-trace__svg').length, 0);
  assert.equal(tagged(withClass(distance, 'activity-report__table')[0], 'button').length, 0);
  const detail = activityFixture('single_metric');
  detail.samples = detail.samples.slice(0, 1);
  detail.sample_count = 1;
  const single = render(components(detail)('pages/ActivityDetail').default);
  assert.ok(textContent(single).includes('Only one recorded time; cursor unavailable.'));
  assert.ok(textContent(single).includes('Minimum readable interval reached'));
  assert.ok(!textContent(single).includes('Independent axes'));
  const slider = tagged(single, 'input').find((node) => node.attributes.type === 'range');
  assert.ok('disabled' in slider.attributes);
});
