import type { ActivityDetailSample } from '../../types/api';
import { closestSample, elapsed, metricUnit, reading, type TraceKey } from '../../utils/activity-detail';
import { formatStoredPace } from '../../utils/format';
import { chartColors, type ResolvedTheme } from '../../utils/theme';
import { t } from '../../utils/i18n';

type CanvasContext = WechatMiniprogram.CanvasRenderingContext.CanvasRenderingContext2D;
const QUERY_RUN = 'exec' as const;
const PADDING = 44;
const TOP = 27;
const BOTTOM = 182;

function color(metric: TraceKey, theme: ResolvedTheme): string {
  const palette = chartColors(theme);
  switch (metric) {
    case 'power_watts': case 'form_power_watts': return palette.activityPower;
    case 'hr_bpm': return palette.activityHeart;
    case 'pace_sec_km': return palette.activityPace;
    case 'cadence_spm': return palette.activityCadence;
    case 'speed_ms': return palette.activitySpeed;
    case 'altitude_m': case 'grade_pct': return palette.activityTerrain;
    case 'temperature_c': return palette.activityWeather;
    case 'ground_time_ms': case 'oscillation_mm': case 'vertical_ratio': case 'leg_spring_kn_m':
      return palette.activityDynamics;
    case 'respiration_rate': return palette.activityBreathing;
  }
}

function scaleDomain(points: ActivityDetailSample[], metric: TraceKey): [number, number] | null {
  const values = points.map((point) => point[metric]).filter((value): value is number => value != null);
  if (!values.length) return null;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const padding = Math.max((high - low) * .12, metric === 'pace_sec_km' ? 5 : 3);
  return [metric === 'altitude_m' || metric === 'grade_pct' || metric === 'temperature_c'
    ? low - padding : Math.max(0, low - padding), high + padding];
}

function chartTranslations() {
  return {
    leftAxis: t('Left axis'),
    rightAxis: t('Right axis'),
    cursor: t('Time cursor · recorded readings'),
    zoomIn: t('Zoom in'),
    zoomOut: t('Zoom out'),
    fullRun: t('Full run'),
    notSampled: t('Not sampled'),
    emptyWindow: t('No readings in this interval; zoom out.'),
    independentAxes: t('Independent axes'),
    paceDirection: t('Pace: faster ↑'),
    singleTime: t('Only one recorded time; cursor unavailable.'),
    minimumWindow: t('Minimum readable interval reached'),
  };
}

Component({
  properties: {
    languageClass: { type: String as StringConstructor, value: 'lang-zh' },
    samples: { type: Array as ArrayConstructor, value: [] as ActivityDetailSample[] },
    primary: { type: String as StringConstructor, value: 'power_watts' },
    secondary: { type: String as StringConstructor, value: '' },
    primaryLabel: { type: String as StringConstructor, value: '' },
    secondaryLabel: { type: String as StringConstructor, value: '' },
    rangeStart: { type: Number as NumberConstructor, value: 0 },
    rangeEnd: { type: Number as NumberConstructor, value: 0 },
    fullStart: { type: Number as NumberConstructor, value: 0 },
    fullEnd: { type: Number as NumberConstructor, value: 0 },
    cursor: { type: Number as NumberConstructor, value: 0 },
    theme: { type: String as StringConstructor, value: 'light' },
  },

  data: {
    ready: false,
    primaryValue: '—',
    secondaryValue: '—',
    cursorTime: '—',
    leftTime: '0:00',
    rightTime: '0:00',
    primaryColor: '',
    secondaryColor: '',
    canZoom: false,
    isFull: true,
    emptyWindow: false,
    dragFrom: null as number | null,
    dragTo: null as number | null,
    tr: chartTranslations(),
    _drawToken: 0,
    _rect: null as { left: number; width: number } | null,
    _touch: null as { x: number; y: number } | null,
  },

  lifetimes: {
    ready() {
      this.setData({ ready: true, tr: chartTranslations() });
      wx.nextTick(() => this.drawChart());
    },
  },

  observers: {
    'languageClass': function () {
      if (!this.data.ready) return;
      this.setData({ tr: chartTranslations() });
      wx.nextTick(() => this.drawChart());
    },
    'samples, primary, secondary, rangeStart, rangeEnd, cursor, theme': function () {
      if (!this.data.ready) return;
      wx.nextTick(() => this.drawChart());
    },
  },

  methods: {
    chartTime(clientX: number, rect: { left: number; width: number }): number {
      const relative = Math.max(PADDING, Math.min(rect.width - PADDING, clientX - rect.left));
      const fraction = (relative - PADDING) / Math.max(1, rect.width - 2 * PADDING);
      return this.data.rangeStart + fraction * (this.data.rangeEnd - this.data.rangeStart);
    },

    measurePlot(onMeasured?: (rect: { left: number; width: number }) => void) {
      const query = wx.createSelectorQuery().in(this);
      const selector = query.select('#activity-trace-canvas').boundingClientRect();
      (selector as unknown as Record<string, (callback: (result: unknown[]) => void) => void>)[QUERY_RUN]((result) => {
        const rect = result?.[0] as { left: number; width: number } | null;
        if (!rect || !rect.width) return;
        this.data._rect = rect;
        onMeasured?.(rect);
      });
    },

    onTouchStart(event: WechatMiniprogram.TouchEvent) {
      const touch = event.touches?.[0];
      if (!touch) return;
      this.data._touch = { x: touch.clientX, y: touch.clientY };
      this.measurePlot();
    },

    onTouchMove(event: WechatMiniprogram.TouchEvent) {
      const touch = event.touches?.[0];
      const start = this.data._touch;
      const rect = this.data._rect;
      if (!touch || !start || !rect) return;
      const horizontal = Math.abs(touch.clientX - start.x);
      const vertical = Math.abs(touch.clientY - start.y);
      if (horizontal < 18 || horizontal <= vertical * 1.2) return;
      this.setData({ dragFrom: this.chartTime(start.x, rect), dragTo: this.chartTime(touch.clientX, rect) });
      wx.nextTick(() => this.drawChart());
    },

    onTouchEnd(event: WechatMiniprogram.TouchEvent) {
      const touch = event.changedTouches?.[0];
      const start = this.data._touch;
      this.data._touch = null;
      if (!touch || !start) return;
      const finish = (rect: { left: number; width: number }) => {
        const dx = Math.abs(touch.clientX - start.x);
        const dy = Math.abs(touch.clientY - start.y);
        const from = this.chartTime(start.x, rect);
        const to = this.chartTime(touch.clientX, rect);
        if (dx > 20 && dx > dy * 1.2 && Math.abs(to - from) >= 30) {
          this.triggerEvent('range', {
            start: Math.floor(Math.min(from, to)),
            end: Math.ceil(Math.max(from, to)),
          });
        } else if (dx < 20 && dy < 20) {
          this.triggerEvent('cursor', { offset: Math.round(to) });
        }
        this.setData({ dragFrom: null, dragTo: null });
      };
      if (this.data._rect) finish(this.data._rect);
      else this.measurePlot(finish);
    },

    onSliderChange(event: WechatMiniprogram.CustomEvent<{ value: number }>) {
      this.triggerEvent('cursor', { offset: event.detail.value });
    },

    onZoomIn() { this.zoom(.5); },
    onZoomOut() { this.zoom(2); },
    onFullRun() { this.triggerEvent('range', { start: this.data.fullStart, end: this.data.fullEnd }); },

    zoom(factor: number) {
      const { fullStart, fullEnd, rangeStart, rangeEnd } = this.data;
      const span = Math.min(fullEnd - fullStart, Math.max(30, (rangeEnd - rangeStart) * factor));
      const center = Math.max(rangeStart, Math.min(rangeEnd, this.data.cursor));
      const lower = factor < 1 ? rangeStart : fullStart;
      const upper = factor < 1 ? rangeEnd : fullEnd;
      const start = Math.max(lower, Math.min(upper - span, center - span / 2));
      this.triggerEvent('range', { start: Math.floor(start), end: Math.ceil(start + span) });
    },

    drawChart() {
      const samples = this.data.samples as ActivityDetailSample[];
      const primary = this.data.primary as TraceKey;
      const secondary = this.data.secondary as TraceKey | '';
      const { rangeStart, rangeEnd, cursor } = this.data;
      const visible = samples.filter((point) => point.offset_sec >= rangeStart && point.offset_sec <= rangeEnd);
      const nearest = closestSample(samples, cursor, primary);
      const sampled = nearest && nearest.offset_sec >= rangeStart && nearest.offset_sec <= rangeEnd ? nearest : null;
      const theme = this.data.theme as ResolvedTheme;
      const update = {
        primaryValue: reading(sampled, primary),
        secondaryValue: secondary ? reading(sampled, secondary) : '—',
        cursorTime: sampled ? elapsed(sampled.offset_sec) : this.data.tr.notSampled,
        leftTime: elapsed(rangeStart),
        rightTime: elapsed(rangeEnd),
        primaryColor: color(primary, theme),
        secondaryColor: secondary ? color(secondary, theme) : '',
        canZoom: rangeEnd - rangeStart >= 60,
        isFull: rangeStart === this.data.fullStart && rangeEnd === this.data.fullEnd,
        emptyWindow: !visible.some((point) => point[primary] != null || (secondary && point[secondary] != null)),
      };
      this.setData(update);
      const drawToken = ++this.data._drawToken;
      const query = wx.createSelectorQuery().in(this);
      const selector = query.select('#activity-trace-canvas').fields({ node: true, size: true });
      (selector as unknown as Record<string, (callback: (result: unknown[]) => void) => void>)[QUERY_RUN]((result) => {
        if (drawToken !== this.data._drawToken) return;
        const entry = result?.[0] as { node: WechatMiniprogram.Canvas; width: number; height: number } | null;
        if (!entry?.node || !entry.width) return;
        const context = entry.node.getContext('2d') as unknown as CanvasContext | null;
        if (!context) return;
        const windowInfo: { pixelRatio?: number } = typeof wx.getWindowInfo === 'function'
          ? wx.getWindowInfo() : wx.getSystemInfoSync();
        const dpr = windowInfo.pixelRatio || 1;
        entry.node.width = entry.width * dpr;
        entry.node.height = entry.height * dpr;
        context.setTransform(1, 0, 0, 1, 0, 0);
        context.scale(dpr, dpr);

        const plotWidth = Math.max(1, entry.width - 2 * PADDING);
        const atX = (time: number) => PADDING + (time - rangeStart) / Math.max(1, rangeEnd - rangeStart) * plotWidth;
        const palette = chartColors(theme);
        context.strokeStyle = palette.grid;
        context.lineWidth = 1;
        for (const position of [TOP, (TOP + BOTTOM) / 2, BOTTOM]) {
          context.beginPath();
          context.moveTo(PADDING, position);
          context.lineTo(entry.width - PADDING, position);
          context.stroke();
        }
        const drawLine = (metric: TraceKey, dashed: boolean) => {
          const domain = scaleDomain(visible, metric);
          if (!domain) return;
          const atY = (value: number) => {
            const position = (value - domain[0]) / (domain[1] - domain[0]);
            return metric === 'pace_sec_km' ? TOP + position * (BOTTOM - TOP) : BOTTOM - position * (BOTTOM - TOP);
          };
          context.strokeStyle = color(metric, theme);
          context.fillStyle = color(metric, theme);
          context.lineWidth = 2;
          context.setLineDash(dashed ? [6, 4] : []);
          context.beginPath();
          let previous: ActivityDetailSample | null = null;
          let runLength = 0;
          let lonePoint: { x: number; y: number } | null = null;
          const singletons: { x: number; y: number }[] = [];
          const endRun = () => {
            if (runLength === 1 && lonePoint) singletons.push(lonePoint);
            runLength = 0;
          };
          for (const point of visible) {
            const value = point[metric];
            if (value == null) { endRun(); previous = null; continue; }
            const x = atX(point.offset_sec);
            const y = atY(value);
            if (!previous || point[`${metric}_break`]) {
              endRun();
              context.moveTo(x, y);
              lonePoint = { x, y };
              runLength = 1;
            } else {
              context.lineTo(x, y);
              runLength += 1;
            }
            previous = point;
          }
          endRun();
          context.stroke();
          context.setLineDash([]);
          for (const point of singletons) {
            context.beginPath();
            context.arc(point.x, point.y, 3, 0, Math.PI * 2);
            context.fill();
          }
          if (sampled?.[metric] != null) {
            context.beginPath();
            context.arc(atX(sampled.offset_sec), atY(sampled[metric]!), 3.5, 0, Math.PI * 2);
            context.fill();
          }
          context.font = '10px monospace';
          context.textBaseline = 'middle';
          context.textAlign = dashed ? 'right' : 'left';
          const axisLabel = (value: number) => metric === 'pace_sec_km'
            ? formatStoredPace(value) : `${Number(value.toFixed(metric === 'speed_ms' || metric === 'leg_spring_kn_m' ? 1 : 0))} ${metricUnit(metric)}`;
          context.fillText(axisLabel(metric === 'pace_sec_km' ? domain[0] : domain[1]),
            dashed ? entry.width - PADDING : PADDING, 15);
          context.fillText(axisLabel(metric === 'pace_sec_km' ? domain[1] : domain[0]),
            dashed ? entry.width - PADDING : PADDING, BOTTOM + 12);
        };
        drawLine(primary, false);
        if (secondary) drawLine(secondary, true);
        if (this.data.dragFrom != null && this.data.dragTo != null) {
          context.fillStyle = palette.planned;
          context.fillRect(atX(Math.min(this.data.dragFrom, this.data.dragTo)), TOP,
            Math.abs(atX(this.data.dragFrom) - atX(this.data.dragTo)), BOTTOM - TOP);
        }
        context.strokeStyle = palette.tick;
        context.lineWidth = 1;
        context.beginPath();
        context.moveTo(atX(cursor), TOP);
        context.lineTo(atX(cursor), BOTTOM);
        context.stroke();
      });
    },
  },
});
