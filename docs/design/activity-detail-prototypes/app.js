import {
  formatReading,
  formatTime,
  getSeries,
  metricDefinitions,
  readingAt,
  scenarios,
  splitAt,
} from './data.js?rev=20260928-field-lab';

const variants = [
  { id: 'report', short: 'A', title: '跑后报告', description: '已选方向 · 沿时间回看，叠加曲线，默认用表格对照分段。', bestFor: '想快速回想这场运动的人', caution: '多条曲线分轨细看仍不如 B 直接。' },
  { id: 'console', short: 'B', title: '数据工作台', description: '叠加走势，也能按独立曲线核对；游标始终同步。', bestFor: '希望交叉核对数据的人', caution: '数据密度较高，需要克制默认显示量。' },
  { id: 'chapters', short: 'C', title: '分段节奏簿', description: '先选设备圈或公里段，再看该段的叠加曲线。', bestFor: '习惯按每一段复盘的人', caution: '没有分段的活动需要清晰的退化路径。' },
];

const params = new URLSearchParams(window.location.search);
const initialVariant = variants.find((variant) => variant.id === params.get('v'))?.id ?? null;
const initialScenario = Object.hasOwn(scenarios, params.get('sample')) ? params.get('sample') : 'full';
const state = {
  variant: initialVariant,
  scenario: initialScenario,
  embed: params.get('embed') === '1',
  metric: 'power',
  overlay: null,
  splitMode: 'laps',
  reportLayout: params.get('layout') === 'cards' ? 'cards' : 'table',
  reportSkin: params.get('skin') === 'original' ? 'original' : 'field-lab',
  reportTheme: params.get('theme') === 'dark' ? 'dark' : 'light',
  range: null,
  selectedSplit: null,
  cursor: 0,
  metricsOpen: false,
  recordsOpen: false,
};

const app = document.getElementById('app');
const activity = scenarios[state.scenario];
state.metric = activity.streams.power ? 'power' : Object.keys(activity.streams)[0] ?? null;
state.overlay = activity.streams.heartRate && state.metric !== 'heartRate' ? 'heartRate' : null;
state.range = { start: 0, end: activity.duration };
if (state.variant === 'chapters' && activity.splits.length) {
  state.selectedSplit = 0;
  state.range = { start: activity.splits[0].start, end: activity.splits[0].end };
}
state.cursor = (state.range.start + state.range.end) / 2;

function pageLink(variant, scenario = state.scenario, embed = false, skin = state.reportSkin) {
  const search = new URLSearchParams();
  if (variant) search.set('v', variant);
  if (scenario !== 'full') search.set('sample', scenario);
  if (variant === 'report' && state.reportLayout === 'cards') search.set('layout', 'cards');
  if (variant === 'report' && skin === 'original') search.set('skin', 'original');
  if (variant === 'report' && skin === 'field-lab' && state.reportTheme === 'dark') search.set('theme', 'dark');
  if (embed) search.set('embed', '1');
  const query = search.toString();
  return `./${query ? `?${query}` : ''}`;
}

function icon(name) {
  const paths = {
    arrow: '<path d="M4 12h15m-6-6 6 6-6 6"/>',
    back: '<path d="M20 12H5m6-6-6 6 6 6"/>',
    expand: '<path d="M4 10V4h6m4 16h6v-6M4 4l6 6m10 10-6-6"/>',
    minus: '<path d="M5 12h14"/>',
    plus: '<path d="M5 12h14M12 5v14"/>',
    sliders: '<path d="M4 7h16M4 17h16M9 4v6m6 4v6"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
  };
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
}

function navigation() {
  if (state.embed) return '';
  return `
    <header class="preview-bar">
      <a class="preview-brand" href="${pageLink(null)}" aria-label="返回三个设计方向">${state.variant === 'report' && state.reportSkin === 'field-lab' ? '<span class="preview-wordmark">Pra<span>x</span>ys</span>' : 'PRAXYS'} <span class="preview-brand-context">／ 活动设计实验</span></a>
      <nav class="preview-switch" aria-label="设计方向">
        <a href="${pageLink(null)}" class="${!state.variant ? 'is-active' : ''}" ${!state.variant ? 'aria-current="page"' : ''} aria-label="三版对比"><span class="preview-nav-full">三版对比</span><span class="preview-nav-short" aria-hidden="true">对比</span></a>
        ${variants.map((variant) => `<a href="${pageLink(variant.id)}" class="${state.variant === variant.id ? 'is-active' : ''}" ${state.variant === variant.id ? 'aria-current="page"' : ''} aria-label="${variant.short} · ${variant.title}"><span class="preview-nav-full">${variant.short} · ${variant.title}</span><span class="preview-nav-short" aria-hidden="true">${variant.short}</span></a>`).join('')}
      </nav>
      <label class="preview-sample">活动样本
        <select data-scenario aria-label="选择演示活动">
          ${Object.values(scenarios).map((scenario) => `<option value="${scenario.id}" ${state.scenario === scenario.id ? 'selected' : ''}>${scenario.label}</option>`).join('')}
        </select>
      </label>
    </header>${state.variant === 'report' ? `
    <div class="report-preview-switch">
      <div role="group" aria-label="A 版视觉对照">
        <button type="button" data-action="report-skin" data-skin="field-lab" aria-pressed="${state.reportSkin === 'field-lab'}">Praxys 品牌版</button>
        <button type="button" data-action="report-skin" data-skin="original" aria-pressed="${state.reportSkin === 'original'}">原 A 视觉</button>
      </div>
      ${state.reportSkin === 'field-lab' ? `<button type="button" class="report-preview-theme" data-action="report-theme" aria-pressed="${state.reportTheme === 'dark'}">${state.reportTheme === 'dark' ? '切换浅色' : '切换深色'}</button>` : ''}
    </div>` : ''}`;
}

function syntheticNotice(short = false) {
  return `<span class="synthetic-notice" aria-label="合成数据，仅供设计比较">${short ? '合成数据' : '合成数据 · 仅供设计比较'}</span>`;
}

function reportObservation() {
  if (!activity.splits.length) return '仅保存整场汇总；没有逐时采样或来源分圈。';
  return `来源设备圈：首圈 <span class="font-data">${activity.splits[0].pace}/km</span> → 末圈 <span class="font-data">${activity.splits.at(-1).pace}/km</span>`;
}

function fieldLabObservation() {
  if (!activity.splits.length) {
    const description = Object.keys(activity.streams).length
      ? '没有来源设备圈；仍可沿时间查看已保存的逐时采样。'
      : '这场活动只有整场汇总，没有逐时采样或来源分圈。';
    return `<div class="report-lead"><p>${description}</p><span>数据依据 · ${activity.source} 活动记录</span></div>`;
  }
  const first = activity.splits[0];
  const last = activity.splits.at(-1);
  if (activity.splits.length < 2 || !first.pace || !last.pace) {
    return `<div class="report-lead"><p>已保存活动记录，但没有足够的有效设备圈配速可对照。</p><span>数据依据 · ${activity.source} 来源记录</span></div>`;
  }
  return `<div class="report-lead"><p>来源设备圈从首圈 <strong class="font-data">${first.pace}</strong> 到末圈 <strong class="font-data">${last.pace}</strong> <span class="font-data">/km</span>。</p><span>不代表全程趋势 · 来源 ${activity.source}</span></div>`;
}

function overview() {
  return `
    <dl class="overview-stats">
      <div><dt>距离</dt><dd>${activity.distance}<small>km</small></dd></div>
      <div><dt>时长</dt><dd>${formatTime(activity.duration)}</dd></div>
      <div><dt>平均配速</dt><dd>${activity.averagePace}<small>/km</small></dd></div>
      <div><dt>${activity.averagePower ? '平均功率' : '平均心率'}</dt><dd>${activity.averagePower ?? activity.averageHeartRate}<small>${activity.averagePower ? 'W' : 'bpm'}</small></dd></div>
    </dl>`;
}

function timeScope() {
  if (state.selectedSplit != null) return `${state.splitMode === 'distance' ? '公里' : '设备圈'} ${String(state.selectedSplit + 1).padStart(2, '0')}`;
  if (state.range.start !== 0 || state.range.end !== activity.duration) return '自选区间';
  return '全程';
}

function visibleSplits() {
  return state.splitMode === 'distance' ? activity.distanceSplits : activity.splits;
}

function metricPicker() {
  const available = Object.keys(activity.streams);
  if (!available.length) return '';
  const quickKeys = ['power', 'heartRate', 'pace'].filter((key) => activity.streams[key]);
  if (!quickKeys.includes(state.metric)) quickKeys.push(state.metric);
  const metricGroups = [...new Set(available.map((key) => metricDefinitions[key].group))];
  return `
    <div class="metric-picker" role="group" aria-label="选择主曲线指标">
      ${quickKeys.map((key) => `<button class="metric-chip ${key === state.metric ? 'is-active' : ''}" data-action="metric" data-metric="${key}" aria-pressed="${key === state.metric}">${metricDefinitions[key].label}</button>`).join('')}
      <button class="metric-more ${state.metricsOpen ? 'is-active' : ''}" data-action="toggle-metrics" aria-expanded="${state.metricsOpen}">${icon('sliders')} 全部曲线 <span class="font-data">${available.length}</span></button>
    </div>
    ${state.metricsOpen ? `<div class="metric-drawer" aria-label="已记录的曲线指标">
      ${metricGroups.map((group) => `<div class="metric-drawer-group"><span class="drawer-heading">${group}</span><div class="metric-drawer-items">${available.filter((key) => metricDefinitions[key].group === group).map((key) => `<button data-action="metric" data-metric="${key}" class="drawer-choice ${state.metric === key ? 'is-active' : ''}" aria-pressed="${state.metric === key}"><span>${metricDefinitions[key].label}</span><small>${activity.streams[key].source} · ${activity.streams[key].coverage}</small></button>`).join('')}</div></div>`).join('')}
    </div>` : ''}`;
}

function overlayExplanation() {
  return `左右独立刻度 · 同一时间轴；只比走势，不比数值大小${state.metric === 'pace' || state.overlay === 'pace' ? '。配速越小越快，向上表示提速' : ''}`;
}

function overlayPicker(showExplanation = true) {
  if (!state.metric) return '';
  const available = Object.keys(activity.streams).filter((key) => key !== state.metric);
  if (!available.length) return '<p class="overlay-unavailable" role="status">只有一条逐时曲线，暂无可叠加的对照指标。</p>';
  return `<div class="overlay-controls"><label>叠加对照
    <select data-overlay aria-label="选择叠加曲线"><option value="" ${!state.overlay ? 'selected' : ''}>不叠加</option>
      ${available.map((key) => `<option value="${key}" ${state.overlay === key ? 'selected' : ''}>${metricDefinitions[key].label} · ${metricDefinitions[key].unit}</option>`).join('')}
    </select></label>${showExplanation ? `<span>${overlayExplanation()}</span>` : ''}</div>`;
}

function pathFor(points, xFor, yFor, closeAt = null) {
  const paths = [];
  let sequence = [];
  for (const point of [...points, { value: null }]) {
    if (point.value != null) {
      sequence.push(point);
      continue;
    }
    if (sequence.length > 1) {
      const vertices = sequence.map((entry, index) => `${index ? 'L' : 'M'}${xFor(entry.time).toFixed(2)} ${yFor(entry.value).toFixed(2)}`).join(' ');
      const closure = closeAt == null ? '' : ` L${xFor(sequence.at(-1).time).toFixed(2)} ${closeAt} L${xFor(sequence[0].time).toFixed(2)} ${closeAt} Z`;
      paths.push(vertices + closure);
    }
    sequence = [];
  }
  return paths.join(' ');
}

function chartPlot(metricKey, options = {}) {
  const definition = metricDefinitions[metricKey];
  const range = options.range ?? state.range;
  const compact = Boolean(options.compact);
  const isOverview = Boolean(options.full);
  const scope = isOverview ? '全程概览' : timeScope();
  const height = compact ? 104 : 230;
  const width = 800;
  const top = compact ? 12 : 19;
  const bottom = compact ? 20 : 34;
  const points = getSeries(activity, metricKey).filter((point) => point.time >= range.start && point.time <= range.end);
  const observed = points.filter((point) => point.value != null);

  if (!activity.streams[metricKey] || !observed.length) {
    return `<div class="chart-empty ${compact ? 'chart-empty--compact' : ''}" role="status"><strong>${definition.label}没有可显示的采样</strong><span>此活动只能查看已保存的汇总记录；不会补画推测曲线。</span></div>`;
  }

  const axisFor = (samples) => {
    const values = samples.map((point) => point.value);
    const observedMin = Math.min(...values);
    const observedMax = Math.max(...values);
    const padding = Math.max(1, (observedMax - observedMin) * 0.18);
    return { min: observedMin - padding, max: observedMax + padding };
  };
  const axis = axisFor(observed);
  const comparisonKey = compact || state.overlay === metricKey || !activity.streams[state.overlay] ? null : state.overlay;
  const comparisonPoints = comparisonKey ? getSeries(activity, comparisonKey).filter((point) => point.time >= range.start && point.time <= range.end) : [];
  const comparisonSamples = comparisonPoints.filter((point) => point.value != null);
  const comparisonAxis = comparisonSamples.length ? axisFor(comparisonSamples) : null;
  const xFor = (time) => (time - range.start) / (range.end - range.start) * width;
  const yFor = (value, bounds, key) => top + (key === 'pace' ? (value - bounds.min) : (bounds.max - value)) / (bounds.max - bounds.min) * (height - top - bottom);
  const guide = [0.25, 0.5, 0.75].map((fraction) => `<line x1="0" x2="${width}" y1="${(top + (height - top - bottom) * fraction).toFixed(1)}" y2="${(top + (height - top - bottom) * fraction).toFixed(1)}" class="chart-grid-line"/>`).join('');
  const splits = visibleSplits();
  const splitRules = splits.length > 8 ? '' : splits
    .filter((split) => split.end > range.start && split.end < range.end)
    .map((split) => `<line x1="${xFor(split.end).toFixed(1)}" x2="${xFor(split.end).toFixed(1)}" y1="${top}" y2="${height - bottom}" class="chart-split-line"/>`).join('');
  const line = pathFor(points, xFor, (value) => yFor(value, axis, metricKey));
  const fill = compact || comparisonKey ? '' : `<path class="chart-area" d="${pathFor(points, xFor, (value) => yFor(value, axis, metricKey), height - bottom)}"/>`;
  const selectedTime = Math.max(range.start, Math.min(range.end, state.cursor));
  const selectedValue = readingAt(activity, metricKey, selectedTime);
  const comparisonValue = comparisonKey ? readingAt(activity, comparisonKey, selectedTime) : null;
  const cursorX = (selectedTime - range.start) / (range.end - range.start) * 100;
  const dotY = selectedValue == null ? 50 : yFor(selectedValue, axis, metricKey) / height * 100;
  const comparisonDotY = comparisonValue == null || !comparisonAxis ? 50 : yFor(comparisonValue, comparisonAxis, comparisonKey) / height * 100;
  const primaryTop = metricKey === 'pace' ? axis.min : axis.max;
  const primaryBottom = metricKey === 'pace' ? axis.max : axis.min;
  const comparisonTop = comparisonAxis && (comparisonKey === 'pace' ? comparisonAxis.min : comparisonAxis.max);
  const comparisonBottom = comparisonAxis && (comparisonKey === 'pace' ? comparisonAxis.max : comparisonAxis.min);

  return `
    <div class="trace ${compact ? 'trace--compact' : ''} tone-${definition.tone}">
      <div class="trace-heading"><div><strong>${definition.label}${comparisonKey ? ` × ${metricDefinitions[comparisonKey].label}` : ''}</strong><span>${scope} · ${comparisonKey ? '独立纵轴 · 同步游标' : `${activity.streams[metricKey].source} · 覆盖 ${activity.streams[metricKey].coverage}`}</span></div>${comparisonKey ? '' : `<div class="trace-current"><strong data-inline-reading="${metricKey}">${formatReading(metricKey, selectedValue)}</strong><small>${definition.unit}</small></div>`}</div>
      ${comparisonKey ? `<div class="trace-legend" role="group" aria-label="同一时刻的叠加读数">
        ${[metricKey, comparisonKey].map((key, index) => `<span class="legend-item tone-${metricDefinitions[key].tone}"><i class="legend-line ${index ? 'legend-line--secondary' : ''}" aria-hidden="true"></i><span>${index ? '右轴' : '左轴'} · ${metricDefinitions[key].label}<small>${activity.streams[key].source} · ${activity.streams[key].coverage}</small></span><strong data-inline-reading="${key}">${formatReading(key, index ? comparisonValue : selectedValue)}</strong><small>${metricDefinitions[key].unit}</small></span>`).join('')}
      </div>` : ''}
      <div class="plot-interactive ${comparisonKey ? 'plot-interactive--overlay' : ''}" data-chart ${isOverview ? 'data-full-index' : ''} data-metric="${metricKey}" data-start="${range.start}" data-end="${range.end}" data-min="${axis.min}" data-max="${axis.max}" ${comparisonAxis ? `data-overlay-min="${comparisonAxis.min}" data-overlay-max="${comparisonAxis.max}"` : ''} data-top="${top}" data-bottom="${bottom}" data-height="${height}" tabindex="0" role="${isOverview ? 'button' : 'group'}" aria-label="${isOverview ? '全程索引，点击曲线跳到对应分段，方向键切换分段' : `${definition.label}${comparisonKey ? `左轴与${metricDefinitions[comparisonKey].label}右轴叠加，独立刻度，同一时间轴；` : '曲线，'}${metricKey === 'pace' || comparisonKey === 'pace' ? '配速越小越快；' : ''}点击查看读数，拖选局部；按左右方向键移动时间`}">
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
          ${guide}${splitRules}${fill}<path class="chart-stroke" d="${line}"/>
          ${comparisonAxis ? `<path class="chart-stroke chart-stroke--comparison tone-${metricDefinitions[comparisonKey].tone}" d="${pathFor(comparisonPoints, xFor, (value) => yFor(value, comparisonAxis, comparisonKey))}"/>` : ''}
        </svg>
        <span class="chart-crosshair" style="left:${cursorX}%" data-crosshair></span>
        <span class="chart-point" style="left:${cursorX}%;top:${dotY}%" data-dot data-dot-metric="${metricKey}" ${selectedValue == null ? 'hidden' : ''}></span>
        ${comparisonKey ? `<span class="chart-point chart-point--comparison tone-${metricDefinitions[comparisonKey].tone}" style="left:${cursorX}%;top:${comparisonDotY}%" data-dot data-dot-metric="${comparisonKey}" ${comparisonValue == null || !comparisonAxis ? 'hidden' : ''}></span>` : ''}
        <span class="chart-brush" data-brush hidden></span>
        ${compact ? '' : `<span class="axis-label axis-label--top axis-label--primary tone-${definition.tone}">${formatReading(metricKey, primaryTop)} <small>${definition.unit}</small></span><span class="axis-label axis-label--bottom axis-label--primary tone-${definition.tone}">${formatReading(metricKey, primaryBottom)} <small>${definition.unit}</small></span>
        ${comparisonAxis ? `<span class="axis-label axis-label--top axis-label--comparison tone-${metricDefinitions[comparisonKey].tone}">${formatReading(comparisonKey, comparisonTop)} <small>${metricDefinitions[comparisonKey].unit}</small></span><span class="axis-label axis-label--bottom axis-label--comparison tone-${metricDefinitions[comparisonKey].tone}">${formatReading(comparisonKey, comparisonBottom)} <small>${metricDefinitions[comparisonKey].unit}</small></span>` : ''}`}
      </div>
      <div class="trace-axis"><span>${formatTime(range.start)}</span><span>${compact ? `游标 <span data-inline-time>${formatTime(state.cursor)}</span>` : comparisonKey && !comparisonAxis ? '这一段的对照曲线无采样' : state.variant === 'report' ? '竖线 = 当前时刻' : '拖选放大 · 点击读数'}</span><span>${formatTime(range.end)}</span></div>
    </div>`;
}

function zoomControls({ labelInChart = false } = {}) {
  const span = state.range.end - state.range.start;
  const canExpand = span > Math.min(180, activity.duration / 6);
  const isZoomed = state.range.start !== 0 || state.range.end !== activity.duration;
  return `<div class="zoom-controls" role="group" aria-label="曲线缩放">
        <button data-action="zoom-in" ${canExpand ? '' : 'disabled'} title="以当前游标为中心放大" aria-label="放大局部曲线">${icon('plus')}${labelInChart ? '<span>放大</span>' : ''}</button>
        <button data-action="zoom-out" ${isZoomed ? '' : 'disabled'} title="返回全程" aria-label="返回全程曲线">${icon('expand')}<span>全程</span></button>
      </div>`;
}

function timelineControls({ report = false } = {}) {
  if (!Object.keys(activity.streams).length) return '';
  const span = state.range.end - state.range.start;
  const position = Math.max(0, Math.min(1000, (state.cursor - state.range.start) / span * 1000));
  const slider = report
    ? `<div class="timeline-slider timeline-slider--report"><div class="timeline-meta"><label for="report-time-scrubber">时刻游标 · 同步读数</label><output for="report-time-scrubber" data-cursor-time>${formatTime(state.cursor)}</output></div><input id="report-time-scrubber" type="range" min="0" max="1000" value="${Math.round(position)}" data-scrubber aria-describedby="report-cursor-help" aria-valuetext="${formatTime(state.cursor)}"/></div>`
    : `<div class="timeline-slider"><span>游标</span><input type="range" min="0" max="1000" value="${Math.round(position)}" data-scrubber aria-label="查看某一时刻的读数" aria-valuetext="${formatTime(state.cursor)}"/><output data-cursor-time>${formatTime(state.cursor)}</output></div>`;
  return `<div class="timeline-controls${report ? ' timeline-controls--report' : ''}">${slider}${report ? '' : zoomControls()}</div>`;
}

function inspector() {
  const available = Object.keys(activity.streams);
  if (!available.length) return '<p class="inspector-unavailable">没有逐时采样；仅保留概要指标。</p>';
  const keys = [state.metric, state.overlay, 'heartRate', 'pace'].filter((key, index, all) => key && activity.streams[key] && all.indexOf(key) === index).slice(0, 4);
  return `
    <div class="inspector-now"><span>游标时间</span><strong data-cursor-time>${formatTime(state.cursor)}</strong></div>
    <dl class="inspector-values">${keys.map((key) => `<div><dt>${metricDefinitions[key].label}</dt><dd><span data-cursor-reading="${key}">${formatReading(key, readingAt(activity, key, state.cursor))}</span><small>${metricDefinitions[key].unit}</small></dd></div>`).join('')}</dl>
    <p class="inspector-source">${activity.sampleDescription}</p>`;
}

function reportSplitTable(splits) {
  const isSourceLap = state.splitMode === 'laps';
  const hasPower = isSourceLap && splits.some((split) => split.power != null);
  const hasHeartRate = isSourceLap && splits.some((split) => split.heartRate != null);
  return `<div class="report-split-table-wrap"><table class="report-split-table">
    <caption class="sr-only">${isSourceLap ? '设备圈' : '每公里'}分段对照；选择一行查看该段曲线</caption>
    <thead><tr><th scope="col">分段</th><th scope="col" class="split-table-distance">距离 <small>km</small></th><th scope="col">用时</th><th scope="col">配速 <small>/km</small></th>${hasPower ? '<th scope="col" class="split-table-extra">均功率 <small>W</small></th>' : ''}${hasHeartRate ? '<th scope="col" class="split-table-extra">均心率 <small>bpm</small></th>' : ''}</tr></thead>
    <tbody>${splits.map((split) => {
      const number = String(split.index + 1).padStart(2, '0');
      const title = isSourceLap ? `设备圈 ${number}` : `第 ${number} 公里`;
      return `<tr class="${state.selectedSplit === split.index ? 'is-active' : ''}" data-action="split" data-index="${split.index}">
        <th scope="row"><button type="button" data-action="split" data-index="${split.index}" aria-current="${state.selectedSplit === split.index}" aria-label="查看${title}的曲线"><span class="split-table-label">${isSourceLap ? '设备圈' : '第'} <span class="font-data">${number}</span>${isSourceLap ? '' : ' 公里'}</span><small class="split-table-subtitle">${isSourceLap ? `${split.title} · ` : ''}<span class="font-data">${formatTime(split.start)}–${formatTime(split.end)}</span></small><small class="split-table-mobile-detail"><span class="font-data">${split.distance.toFixed(1)} km</span>${hasPower && split.power != null ? `<span class="font-data">功率 ${split.power} W</span>` : ''}${hasHeartRate && split.heartRate != null ? `<span class="font-data">心率 ${split.heartRate} bpm</span>` : ''}</small></button></th>
        <td class="split-table-distance font-data">${split.distance.toFixed(1)}</td>
        <td class="font-data">${formatTime(split.seconds)}</td><td class="font-data split-table-pace">${split.pace}</td>
        ${hasPower ? `<td class="split-table-extra font-data">${split.power ?? '—'}</td>` : ''}${hasHeartRate ? `<td class="split-table-extra font-data">${split.heartRate ?? '—'}</td>` : ''}
      </tr>`;
    }).join('')}</tbody>
  </table></div><p class="split-table-note">点击任一行，在上方查看该段曲线。${isSourceLap ? '功率、心率仅显示来源圈已有的汇总值。' : '公里段按距离轨迹切分；没有独立的每公里功率或心率汇总，不推算显示。'}</p>`;
}

function splitSelector(style) {
  if (!activity.splits.length) return '<div class="split-empty">没有来源分圈，也没有可计算公里段的逐时距离；仍可查看已保存的汇总指标。</div>';
  const splits = visibleSplits();
  return `<div class="split-modes"><div class="split-mode-switch" role="group" aria-label="分段依据">
    <button data-action="split-mode" data-mode="laps" aria-pressed="${state.splitMode === 'laps'}" class="${state.splitMode === 'laps' ? 'is-active' : ''}">设备圈 <span class="font-data">${activity.splits.length}</span></button>
    <button data-action="split-mode" data-mode="distance" aria-pressed="${state.splitMode === 'distance'}" class="${state.splitMode === 'distance' ? 'is-active' : ''}" ${activity.distanceSplits.length ? '' : 'disabled'}>每公里 <span class="font-data">${activity.distanceSplits.length || '—'}</span></button>
  </div><p class="split-mode-note">${state.splitMode === 'distance' ? '按合成距离轨迹每 1 km 切分，末段保留剩余距离；不是设备圈。' : '来源分圈示例；原始记录未区分自动圈或手动圈，章节名称仅为演示。'}${activity.distanceSplits.length ? '' : ' 没有逐时距离轨迹，不能计算每公里。'}</p></div>
  ${style === 'report' && state.reportLayout === 'table' ? reportSplitTable(splits) : `<div class="split-selector split-selector--${style} ${state.splitMode === 'distance' ? 'split-selector--distance' : ''}" role="group" aria-label="按${state.splitMode === 'distance' ? '每公里' : '设备圈'}查看曲线">
    ${splits.map((split) => `<button data-action="split" data-index="${split.index}" class="split-option ${state.selectedSplit === split.index ? 'is-active' : ''}" aria-pressed="${state.selectedSplit === split.index}">
      <span class="split-number">${String(split.index + 1).padStart(2, '0')}</span>
      <span class="split-name">${split.title}<small>${formatTime(split.start)}–${formatTime(split.end)}</small></span>
      <span class="split-distance">${split.distance.toFixed(1)}<small>km</small></span>
      <span class="split-pace">${split.pace}<small>/km</small></span>
      <span class="split-arrow">${icon('arrow')}</span>
    </button>`).join('')}
  </div>`}`;
}

function recordsPanel() {
  const grouped = new Map();
  for (const [key, stream] of Object.entries(activity.streams)) {
    const definition = metricDefinitions[key];
    const group = grouped.get(definition.group) ?? [];
    group.push({ label: definition.label, value: stream.value, unit: definition.unit, source: stream.source, metricKey: key });
    grouped.set(definition.group, group);
  }
  for (const summary of activity.summaries) {
    const group = grouped.get(summary.group) ?? [];
    group.push(summary);
    grouped.set(summary.group, group);
  }
  const allCount = activity.summaries.length + Object.keys(activity.streams).length;
  return `<details class="records" id="all-records" ${state.recordsOpen ? 'open' : ''}>
    <summary><span>查看全部 <span class="font-data">${allCount}</span> 项记录 <small>按来源与有无采样归类</small></span>${icon('chevron')}</summary>
    <p class="records-help">只有标记为「可看曲线」的指标有采样；其余是活动汇总。未采集的指标不补值，不展示定位坐标。</p>
    <div class="record-groups">${[...grouped.entries()].map(([group, entries]) => `<section class="record-group"><h3>${group}</h3><div class="record-rows">${entries.map((entry) => entry.metricKey
      ? `<button class="record-row record-row--link" data-action="metric" data-metric="${entry.metricKey}" aria-label="查看${entry.label}曲线"><span>${entry.label}<small>${entry.source} · 可看曲线</small></span><strong>${entry.value} <small>${entry.unit}</small></strong>${icon('arrow')}</button>`
      : `<div class="record-row"><span>${entry.label}<small>${entry.source} · 仅汇总</small>${entry.description ? `<small class="record-description">${entry.description}</small>` : ''}</span><strong>${entry.value} <small>${entry.unit}</small></strong></div>`).join('')}</div></section>`).join('')}</div>
  </details>`;
}

function reportSamplingNote() {
  if (!state.metric) return '';
  const sources = [state.metric, state.overlay].filter((key) => key && activity.streams[key]);
  return `<p class="report-sampling-note">${sources.map((key) => `${metricDefinitions[key].label} ${activity.streams[key].source} · 覆盖 ${activity.streams[key].coverage}`).join(' / ')}。${activity.reportSampleNote ?? activity.sampleDescription}</p>`;
}

function reportEmpty() {
  const count = activity.summaries.length;
  return `<div class="report-empty"><div role="status"><strong>没有逐时采样</strong><p>不能查看某一刻或分段曲线；这场活动仍保存了整场指标。</p></div><a href="#all-records">查看已保存的 <span class="font-data">${count}</span> 项指标 ${icon('arrow')}</a></div>`;
}

function reportView() {
  const split = state.selectedSplit == null ? null : visibleSplits()[state.selectedSplit];
  const selectedLabel = split ? `${state.splitMode === 'distance' ? '第' : '设备圈'} ${String(split.index + 1).padStart(2, '0')}${state.splitMode === 'distance' ? ' 公里' : ''}` : '';
  const branded = state.reportSkin === 'field-lab';
  return `
    <main class="demo-page report-page${state.metric ? '' : ' report-page--summary'}" id="content">
      <div class="report-masthead"><a href="${pageLink(null)}" class="back-link">${icon('back')} 返回设计对比</a><span>${branded ? '分析 / 活动记录' : 'PRAXYS / ACTIVITY'}</span></div>
      <header class="report-title"><div><div class="report-title-line"><h1>${activity.name}</h1>${syntheticNotice(true)}</div><p>${branded ? `<span class="font-data">${activity.date}</span> · <span class="font-data">${activity.started}</span>` : `${activity.date} · ${activity.started}`} 出发 · ${activity.type}</p></div></header>
      ${branded ? fieldLabObservation() : `<div class="report-rule"><span>${reportObservation()}</span><span>${activity.source} · 示例</span></div>`}
      ${overview()}
      <section class="report-primary" aria-label="活动曲线">
        <div class="report-section-title"><div><h2>${state.metric ? '沿着时间，读一遍' : '已保存的整场记录'}</h2></div></div>
        ${split ? `<div class="report-selection" data-report-selection tabindex="-1"><div><strong class="font-data">${selectedLabel}</strong><span class="font-data">${split.distance.toFixed(1)} km · 用时 ${formatTime(split.seconds)} · 配速 ${split.pace}/km</span></div><button type="button" data-action="return-splits">${icon('back')} 返回分段${state.reportLayout === 'table' ? '表' : '卡片'}</button></div>` : ''}
        ${metricPicker()}${overlayPicker(false)}
        <div class="report-graph">${state.metric ? chartPlot(state.metric) : reportEmpty()}${state.metric ? `<div class="report-zoom">${zoomControls({ labelInChart: true })}</div>` : ''}${timelineControls({ report: true })}${state.metric ? `<p class="report-axis-note" id="report-cursor-help">时刻游标是图中的竖线，也可在下方滑动：定位某一刻，同步查看已有读数；拖选曲线或点「放大」才改变时间范围${state.overlay ? `。${overlayExplanation()}` : ''}</p>` : ''}${reportSamplingNote()}</div>
      </section>
      ${activity.splits.length ? `<section class="report-splits" id="split-review"><div class="report-section-title"><div><h2>按段回看</h2><p>设备圈与每公里是两种切法；点任一段，放大上方同一条时间轴。</p></div><div class="report-layout-switch" role="group" aria-label="分段呈现方式"><button type="button" data-action="report-layout" data-layout="table" aria-pressed="${state.reportLayout === 'table'}" class="${state.reportLayout === 'table' ? 'is-active' : ''}">表格对照</button><button type="button" data-action="report-layout" data-layout="cards" aria-pressed="${state.reportLayout === 'cards'}" class="${state.reportLayout === 'cards' ? 'is-active' : ''}">原卡片</button></div></div>${splitSelector('report')}</section>` : ''}
      <section class="report-records"><div class="report-section-title"><div><h2>${state.metric ? '其余记录' : '所有已存指标'}</h2><p>${state.metric ? '曲线、来源与只有汇总值的指标放在一起，但不混为同一种证据。' : '这里只有整场汇总；仍可核对每项指标与数据来源。'}</p></div></div>${recordsPanel()}</section>
      <footer class="demo-foot">设计原型 · 所有数字与曲线均为合成示例 · 无 GPS、无 AI 评价</footer>
    </main>`;
}

function consoleView() {
  const available = Object.keys(activity.streams);
  const featured = [state.overlay, 'heartRate', 'pace', 'power'].filter((key, index, keys) => key && key !== state.metric && activity.streams[key] && keys.indexOf(key) === index).slice(0, 2);
  return `
    <main class="demo-page console-page" id="content">
      <div class="console-frame">
        <aside class="console-rail"><a href="${pageLink(null)}" class="console-logo" aria-label="返回设计对比">P<span>·</span></a><span class="rail-caption">活动 / 01</span><div class="rail-line"></div><span class="rail-side-label">每个读数，都有出处</span><a href="${pageLink(null)}" class="rail-back" aria-label="返回设计对比">${icon('back')}</a></aside>
        <div class="console-main">
          <header class="console-header"><div class="console-head-top"><a href="${pageLink(null)}" class="console-back">${icon('back')} 三版对比</a>${syntheticNotice()}</div><div class="console-heading"><div><h1>${activity.name}</h1><p>${activity.date} / ${activity.started} / ${activity.source}</p></div><span class="console-index">RUN / ${activity.id === 'full' ? '001' : activity.id === 'sparse' ? '002' : '003'}</span></div></header>
          <div class="console-summary">${overview()}</div>
          <div class="console-board"><div class="console-traces"><div class="console-section-head"><div><h2>信号对照</h2><span>两条叠加对照 · 下方分轨核对 · 同步游标</span></div><span class="console-status">${available.length ? `${available.length} 条可用曲线` : '仅有概要记录'}</span></div>
            ${metricPicker()}${overlayPicker()}
            ${state.metric ? `<div class="console-overlay">${chartPlot(state.metric)}</div>${featured.length ? `<div class="stacked-traces">${featured.map((key) => chartPlot(key, { compact: true })).join('')}</div>` : ''}${timelineControls()}` : '<div class="chart-empty" role="status"><strong>没有逐时采样</strong><span>此活动只有汇总值；曲线和同步读数不可用。</span></div>'}
            <div class="console-records"><div class="console-mobile-splits"><h3>按段回看</h3>${splitSelector('console')}</div>${recordsPanel()}</div>
          </div><aside class="console-inspector"><div class="console-aside-heading"><h2>时刻检查器</h2><span>LIVE READOUT</span></div>${inspector()}<div class="console-divide"></div><h3>区间索引</h3>${splitSelector('console')}</aside></div>
          <footer class="demo-foot">合成数据 · 指标来源为原型字段示意 · 不提供训练建议</footer>
        </div>
      </div>
    </main>`;
}

function chaptersView() {
  const selected = state.selectedSplit == null ? null : visibleSplits()[state.selectedSplit];
  const hasStreams = Object.keys(activity.streams).length > 0;
  const selectionTitle = selected ? selected.title : hasStreams ? '全程细看' : '仅有汇总';
  const selectionNumber = selected ? String(selected.index + 1).padStart(2, '0') : '全';
  const splitSummary = selected
    ? `距离 ${selected.distance.toFixed(1)} km · 配速 ${selected.pace} /km${selected.power != null ? ` · 功率 ${selected.power} W` : ''}`
    : hasStreams ? '曲线已回到整个活动范围。拖选或点分段继续细看。' : '没有分段与逐时采样，只能查看已保存的汇总指标。';
  const fullRange = { start: 0, end: activity.duration };
  return `
    <main class="demo-page chapters-page" id="content">
      <header class="chapters-head"><div class="chapters-top"><a href="${pageLink(null)}">${icon('back')} 返回三版对比</a>${syntheticNotice()}</div><h1>${activity.name}</h1><div class="chapters-meta"><span>${activity.date} · ${activity.started}</span><span>${activity.distance} km / ${formatTime(activity.duration)}</span><span>${activity.source}</span></div></header>
      <div class="chapters-deck"><div class="chapters-contents"><div class="chapters-contents-head"><h2>${activity.splits.length ? '把一场跑步拆开读' : '这一场，只能看全程'}</h2><p>${activity.splits.length ? '先选分段依据，再放大这段的采样记录。' : '没有分段记录；已保存的汇总指标仍可查看。'}</p></div>${splitSelector('chapters')}<a class="chapters-all" href="#all-records">查看全部记录 ${icon('arrow')}</a></div>
        <section class="chapters-focus" aria-label="分段曲线"><div class="focus-header"><div><span class="focus-number">${selectionNumber}</span><div><h2>${selectionTitle}</h2><p>${splitSummary}</p></div></div>${selected ? `<button data-action="zoom-out" aria-label="返回全程曲线">看全程 ${icon('expand')}</button>` : ''}</div>
          <div class="focus-chart">${metricPicker()}${overlayPicker()}${state.metric ? chartPlot(state.metric) : '<div class="chart-empty" role="status"><strong>没有逐时采样</strong><span>本次仅有汇总数据，不能展示分段内的曲线。</span></div>'}${timelineControls()}</div>
          <div class="focus-readout">${inspector()}</div>
          ${state.metric && visibleSplits().length ? `<div class="focus-overview"><div><strong>全程索引</strong><span>点曲线跳到对应${state.splitMode === 'distance' ? '公里段' : '设备圈'} · 方向键切换</span></div>${chartPlot(state.metric, { compact: true, range: fullRange, full: true })}</div>` : ''}
        </section>
      </div>
      <div class="chapters-records">${recordsPanel()}</div>
      <footer class="demo-foot">所有指标和曲线均为合成示例 · 无定位数据 · 无 AI 推断</footer>
    </main>`;
}

function galleryView() {
  return `<main class="gallery-page" id="content"><header class="gallery-intro"><div><h1>同一场跑步，<br />三种读法<span class="gallery-period">.</span></h1><p>活动详情设计探索。三版使用相同的合成数据；区别不在换色，而在先看什么、怎样走到局部。</p></div><div class="gallery-context"><span>示例 / ${activity.name}</span><strong>${activity.distance} km <i>·</i> ${formatTime(activity.duration)}</strong><small>${syntheticNotice()}</small></div></header>
    <div class="gallery-compare" aria-label="三个设计方向">${variants.map((variant) => `<article class="gallery-option gallery-option--${variant.id}"><div class="gallery-option-head"><span class="variant-letter">${variant.short}</span><div><h2>${variant.title}</h2><p>${variant.description}</p></div></div><div class="gallery-preview"><iframe src="${pageLink(variant.id, state.scenario, true)}" title="${variant.title} 手机视图预览" aria-hidden="true" tabindex="-1" loading="lazy"></iframe><span>真实移动布局预览</span></div><div class="gallery-option-foot"><dl><div><dt>更适合</dt><dd>${variant.bestFor}</dd></div><div><dt>需要权衡</dt><dd>${variant.caution}</dd></div></dl><a href="${pageLink(variant.id)}">打开交互原型 ${icon('arrow')}</a></div></article>`).join('')}</div>
    <div class="gallery-instructions"><p>A 已选为下一步方向，默认展示 Praxys Field Lab 品牌版；A 顶部可直接与原视觉对照，不改变选中的曲线或分段。B、C 保留供参考。小窗展示对应的手机布局。</p><p>试试曲线叠加、时刻游标、表格分段以及不同数据覆盖情况；这些是合成数据实验，不接账户，也不会修改正式活动页。</p></div>
    <footer class="demo-foot">PRAXYS · 活动详情设计实验 · 三版均为可丢弃原型</footer></main>`;
}

function render(focusSelector = null) {
  state.recordsOpen = app.querySelector('#all-records')?.open ?? state.recordsOpen;
  document.body.className = `${state.variant ?? 'gallery'}-theme${state.variant === 'report' && state.reportSkin === 'field-lab' ? ` report-theme--field-lab${state.reportTheme === 'dark' ? ' is-dark' : ''}` : ''}${state.embed ? ' embedded' : ''}`;
  document.title = `${variants.find((variant) => variant.id === state.variant)?.title ?? '三版设计对比'} · 活动详情设计实验 | Praxys`;
  app.innerHTML = `${navigation()}${state.variant === 'report' ? reportView() : state.variant === 'console' ? consoleView() : state.variant === 'chapters' ? chaptersView() : galleryView()}<span class="sr-only" aria-live="polite" id="chart-live"></span>`;
  if (focusSelector) app.querySelector(focusSelector)?.focus();
}

function focusVisible(selector) {
  [...app.querySelectorAll(selector)].find((element) => element.getClientRects().length)?.focus();
}

function announceCursor() {
  const liveRegion = document.getElementById('chart-live');
  if (!liveRegion) return;
  const reading = state.metric ? readingAt(activity, state.metric, state.cursor) : null;
  const comparison = state.overlay && state.overlay !== state.metric ? `，${metricDefinitions[state.overlay].label} ${formatReading(state.overlay, readingAt(activity, state.overlay, state.cursor))} ${metricDefinitions[state.overlay].unit}` : '';
  liveRegion.textContent = `${formatTime(state.cursor)}，${state.metric ? metricDefinitions[state.metric].label : '读数'} ${state.metric ? `${formatReading(state.metric, reading)} ${metricDefinitions[state.metric].unit}` : '不可用'}${comparison}`;
}

function syncReadouts(announce = false) {
  for (const output of app.querySelectorAll('[data-cursor-time]')) output.textContent = formatTime(state.cursor);
  for (const output of app.querySelectorAll('[data-inline-time]')) output.textContent = formatTime(state.cursor);
  for (const output of app.querySelectorAll('[data-cursor-reading], [data-inline-reading]')) {
    const metricKey = output.dataset.cursorReading ?? output.dataset.inlineReading;
    output.textContent = formatReading(metricKey, readingAt(activity, metricKey, state.cursor));
  }
  for (const chart of app.querySelectorAll('[data-chart]')) {
    const start = Number(chart.dataset.start);
    const end = Number(chart.dataset.end);
    const fraction = Math.max(0, Math.min(1, (state.cursor - start) / (end - start)));
    const visible = state.cursor >= start && state.cursor <= end;
    const crosshair = chart.querySelector('[data-crosshair]');
    crosshair.style.left = `${fraction * 100}%`;
    crosshair.hidden = !visible;
    for (const dot of chart.querySelectorAll('[data-dot]')) {
      const value = readingAt(activity, dot.dataset.dotMetric, state.cursor);
      const comparison = dot.dataset.dotMetric !== chart.dataset.metric;
      const min = Number(comparison ? chart.dataset.overlayMin : chart.dataset.min);
      const max = Number(comparison ? chart.dataset.overlayMax : chart.dataset.max);
      dot.hidden = !visible || value == null || (comparison && !chart.hasAttribute('data-overlay-min'));
      dot.style.left = `${fraction * 100}%`;
      if (!dot.hidden) {
        const graphHeight = Number(chart.dataset.height);
        const top = Number(chart.dataset.top);
        const bottom = Number(chart.dataset.bottom);
        const fractionY = dot.dataset.dotMetric === 'pace' ? (value - min) / (max - min) : (max - value) / (max - min);
        dot.style.top = `${(top + fractionY * (graphHeight - top - bottom)) / graphHeight * 100}%`;
      }
    }
  }
  const scrubber = app.querySelector('[data-scrubber]');
  if (scrubber) {
    scrubber.value = String(Math.round((state.cursor - state.range.start) / (state.range.end - state.range.start) * 1000));
    scrubber.setAttribute('aria-valuetext', formatTime(state.cursor));
  }
  if (announce) announceCursor();
}

function updateRange(start, end, selectedSplit = null) {
  state.range = { start: Math.max(0, start), end: Math.min(activity.duration, end) };
  state.selectedSplit = selectedSplit;
  state.cursor = (state.range.start + state.range.end) / 2;
  render();
}

app.addEventListener('change', (event) => {
  if (event.target.matches('[data-scenario]')) window.location.href = pageLink(state.variant, event.target.value);
  if (event.target.matches('[data-overlay]')) {
    state.overlay = event.target.value || null;
    render('[data-overlay]');
  }
});

app.addEventListener('click', (event) => {
  if (event.target.closest('a[href="#all-records"]')) {
    const records = app.querySelector('#all-records');
    if (records) {
      event.preventDefault();
      records.open = true;
      state.recordsOpen = true;
      records.scrollIntoView({ behavior: 'instant', block: 'start' });
      records.querySelector('summary')?.focus({ preventScroll: true });
    }
    return;
  }
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const { action } = button.dataset;
  if (action === 'report-skin') {
    state.reportSkin = button.dataset.skin;
    window.history.replaceState(null, '', pageLink('report', state.scenario, state.embed));
    render(`[data-action="report-skin"][data-skin="${state.reportSkin}"]`);
  } else if (action === 'report-theme') {
    state.reportTheme = state.reportTheme === 'dark' ? 'light' : 'dark';
    window.history.replaceState(null, '', pageLink('report', state.scenario, state.embed));
    render('[data-action="report-theme"]');
  } else if (action === 'metric') {
    const previousMetric = state.metric;
    state.metric = button.dataset.metric;
    if (state.overlay === state.metric) state.overlay = previousMetric;
    state.metricsOpen = false;
    render(`[data-action="metric"][data-metric="${state.metric}"]`);
    if (button.classList.contains('record-row')) app.querySelector('[data-chart]')?.focus();
  } else if (action === 'toggle-metrics') {
    state.metricsOpen = !state.metricsOpen;
    render('[data-action="toggle-metrics"]');
  } else if (action === 'report-layout') {
    state.reportLayout = button.dataset.layout;
    window.history.replaceState(null, '', pageLink('report', state.scenario, state.embed));
    render(`[data-action="report-layout"][data-layout="${state.reportLayout}"]`);
  } else if (action === 'split-mode') {
    if (button.dataset.mode === 'distance' && !activity.distanceSplits.length) return;
    state.splitMode = button.dataset.mode;
    if (state.variant === 'chapters' && visibleSplits().length) {
      updateRange(visibleSplits()[0].start, visibleSplits()[0].end, 0);
    } else {
      updateRange(0, activity.duration);
    }
    focusVisible(`[data-action="split-mode"][data-mode="${state.splitMode}"]`);
  } else if (action === 'split') {
    const split = visibleSplits()[Number(button.dataset.index)];
    if (!split) return;
    updateRange(split.start, split.end, split.index);
    if (state.variant === 'report') {
      app.querySelector('.report-primary')?.scrollIntoView({ behavior: 'instant', block: 'start' });
      app.querySelector('[data-report-selection]')?.focus({ preventScroll: true });
    } else {
      focusVisible(`[data-action="split"][data-index="${split.index}"]`);
    }
  } else if (action === 'return-splits') {
    const trigger = app.querySelector(`.report-splits button[data-action="split"][data-index="${state.selectedSplit}"]`);
    trigger?.scrollIntoView({ behavior: 'instant', block: 'center' });
    trigger?.focus({ preventScroll: true });
  } else if (action === 'zoom-in') {
    const half = (state.range.end - state.range.start) / 4;
    const start = Math.max(state.range.start, state.cursor - half);
    const end = Math.min(state.range.end, state.cursor + half);
    updateRange(start, end);
    app.querySelector('[data-action="zoom-in"]')?.focus();
  } else if (action === 'zoom-out') {
    updateRange(0, activity.duration);
    app.querySelector('[data-action="zoom-out"]')?.focus();
  }
});

app.addEventListener('input', (event) => {
  if (!event.target.matches('[data-scrubber]')) return;
  const fraction = Number(event.target.value) / 1000;
  state.cursor = state.range.start + fraction * (state.range.end - state.range.start);
  syncReadouts(true);
});

let brushStart = null;

function timeAtPointer(chart, clientX) {
  const bounds = chart.getBoundingClientRect();
  const fraction = Math.max(0, Math.min(1, (clientX - bounds.left) / bounds.width));
  return Number(chart.dataset.start) + fraction * (Number(chart.dataset.end) - Number(chart.dataset.start));
}

app.addEventListener('pointerdown', (event) => {
  const chart = event.target.closest('[data-chart]');
  if (!chart) return;
  brushStart = { chart, x: event.clientX, time: timeAtPointer(chart, event.clientX) };
  chart.setPointerCapture?.(event.pointerId);
  if (chart.hasAttribute('data-full-index')) return;
  state.cursor = brushStart.time;
  syncReadouts();
});

app.addEventListener('pointermove', (event) => {
  const chart = event.target.closest('[data-chart]');
  if (!chart || chart.hasAttribute('data-full-index')) return;
  state.cursor = timeAtPointer(chart, event.clientX);
  syncReadouts();
  if (brushStart?.chart !== chart || Math.abs(event.clientX - brushStart.x) < 12) return;
  const bounds = chart.getBoundingClientRect();
  const start = Math.max(0, Math.min(1, (Math.min(event.clientX, brushStart.x) - bounds.left) / bounds.width));
  const end = Math.max(0, Math.min(1, (Math.max(event.clientX, brushStart.x) - bounds.left) / bounds.width));
  const brush = chart.querySelector('[data-brush]');
  brush.hidden = false;
  brush.style.left = `${start * 100}%`;
  brush.style.width = `${(end - start) * 100}%`;
});

app.addEventListener('pointerup', (event) => {
  if (!brushStart) return;
  const { chart, x, time } = brushStart;
  brushStart = null;
  if (chart.hasAttribute('data-full-index')) {
    if (Math.abs(event.clientX - x) > 12) return;
    const split = splitAt(activity, timeAtPointer(chart, event.clientX), state.splitMode);
    if (!split) return;
    updateRange(split.start, split.end, split.index);
    app.querySelector('[data-full-index]')?.focus({ preventScroll: true });
    return;
  }
  if (Math.abs(event.clientX - x) > 20) {
    const end = timeAtPointer(chart, event.clientX);
    if (Math.abs(end - time) >= 90) {
      updateRange(Math.min(time, end), Math.max(time, end));
      app.querySelector('[data-chart]')?.focus();
      return;
    }
  }
  chart.querySelector('[data-brush]').hidden = true;
  state.cursor = timeAtPointer(chart, event.clientX);
  syncReadouts(true);
});

app.addEventListener('pointercancel', () => {
  brushStart?.chart.querySelector('[data-brush]')?.setAttribute('hidden', '');
  brushStart = null;
});

app.addEventListener('keydown', (event) => {
  const chart = event.target.closest('[data-chart]');
  if (!chart) return;
  if (chart.hasAttribute('data-full-index')) {
    const splits = visibleSplits();
    const current = state.selectedSplit ?? splitAt(activity, state.cursor, state.splitMode)?.index ?? 0;
    let next = current;
    if (event.key === 'ArrowRight') next = Math.min(splits.length - 1, current + 1);
    else if (event.key === 'ArrowLeft') next = Math.max(0, current - 1);
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = splits.length - 1;
    else if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    const split = splits[next];
    updateRange(split.start, split.end, split.index);
    app.querySelector('[data-full-index]')?.focus({ preventScroll: true });
    return;
  }
  const start = Number(chart.dataset.start);
  const end = Number(chart.dataset.end);
  const step = (end - start) / 40;
  if (event.key === 'ArrowRight') state.cursor = Math.min(end, state.cursor + step);
  else if (event.key === 'ArrowLeft') state.cursor = Math.max(start, state.cursor - step);
  else if (event.key === 'Home') state.cursor = start;
  else if (event.key === 'End') state.cursor = end;
  else return;
  event.preventDefault();
  syncReadouts(true);
});

render();
