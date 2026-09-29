import type { IAppOption } from '../../app';
import type {
  Activity, ActivityDetailResponse, ActivityKilometerSplit, ActivityDetailSample,
  KilometerUnavailableReason, SplitData,
} from '../../types/api';
import { apiGet, type ApiError } from '../../utils/api-client';
import { elapsed, reading, recordedMetrics, type TraceKey } from '../../utils/activity-detail';
import { formatStoredPace } from '../../utils/format';
import { detectLocale, t } from '../../utils/i18n';
import { applyThemeChrome, resolveTheme, themeClassName } from '../../utils/theme';

interface MetricRow { label: string; value: string; unit: string }
interface SplitRow {
  number: number;
  numberLabel: string;
  distance: string;
  duration: string;
  pace: string;
  power: string;
  heart: string;
}
interface SavedRow { label: string; value: string }
interface MetricChoice { key: TraceKey; label: string }
interface OverlayChoice { key: TraceKey | ''; label: string }
interface DetailView {
  title: string;
  date: string;
  source: string;
  environmentSource: string;
  hasLapComparison: boolean;
  firstLapPace: string;
  lastLapPace: string;
  summary: MetricRow[];
  recordedSplits: SplitRow[];
  kilometerSplits: SplitRow[];
  saved: SavedRow[];
  savedCount: number;
  sampleCount: number;
  partial: boolean;
  sourceRows: string;
  sampleStartOnly: boolean;
  hasReferenceScores: boolean;
  kilometerReason: string;
}

function translations() {
  return {
    title: t('Activities'),
    back: t('All activities'),
    failed: t('Could not load this activity'),
    notFound: t('Activity unavailable'),
    notFoundDetail: t('This record is not available to this account.'),
    retryDetail: t('Check your connection and retry. No stale record is shown.'),
    retry: t('Retry'),
    firstLap: t('First lap'),
    lastLap: t('Last lap'),
    observation: t("This activity's saved record is ready to inspect."),
    comparisonScope: t('Source laps only · not an overall trend'),
    observationScope: t('Recorded activity · no lap comparison available'),
    timeline: t('Read the run over time'),
    primary: t('Primary recorded metric'),
    moreCurves: t('More curves'),
    otherMetrics: t('Other recorded metrics'),
    overlay: t('Overlay'),
    overlayUnavailable: t('Only one recorded metric; overlay unavailable.'),
    noSamples: t('No recorded metric curves'),
    noRows: t('No time-series samples were stored. Any available summaries and laps are shown below.'),
    noMetrics: t('This stream has no saved metric readings. Any available summaries and laps are shown below.'),
    seeSaved: t('View saved values'),
    axes: t('Axes show separate units; pace rises as seconds per km fall. Position compares shape, not magnitude.'),
    samples: t('Recorded sample rows'),
    reduced: t('Extrema shown; omitted points are not interpolated.'),
    gaps: t('Some intervals were not sampled; lines stop at gaps.'),
    missing: t('Missing metric readings and time gaps are shown as breaks, never filled in.'),
    sourceRows: t('Stream record source (not guaranteed per field)'),
    timeOrigin: t('Time is measured from the first stored sample; activity start time is unverified.'),
    segments: t('Review by split'),
    recorded: t('Recorded laps'),
    kilometers: t('Each kilometer'),
    lapScope: t('Source-recorded laps may be manual or automatic. No reliable timeline boundaries were saved, so these rows cannot jump to the chart.'),
    kmScope: t('Derived from continuous recorded distance. Boundaries use the first sample to reach each kilometer; not device laps.'),
    kmSummaryOnly: t('No sampled metric curves are available; these kilometer rows are for summary comparison only.'),
    kmUnavailable: t('Each kilometer unavailable:'),
    split: t('Split'),
    distance: t('Distance'),
    duration: t('Duration'),
    pace: t('Pace'),
    power: t('Power'),
    heart: t('Heart rate'),
    selectedKilometer: t('Kilometer'),
    returnToSplits: t('Back to split table'),
    records: t('Other saved values'),
    recordedCurves: t('Recorded curves'),
    wholeValues: t('Whole-activity values'),
    stream: t('Recorded stream · view chart'),
    whole: t('Whole-activity summary'),
    activitySource: t('Activity record source'),
    environmentSource: t('Environment record source'),
    fieldSource: t('Field sources for summary values are not independently verified.'),
    noneSaved: t('No additional saved values are available.'),
    reference: t('RSS and the source CP estimate are activity-level references, not sampled curves or a Praxys training verdict.'),
    unavailable: t('Source unavailable'),
    notRecorded: t('Not recorded'),
  };
}

function metricLabel(key: TraceKey): string {
  switch (key) {
    case 'power_watts': return t('Power');
    case 'hr_bpm': return t('Heart rate');
    case 'pace_sec_km': return t('Pace');
    case 'cadence_spm': return t('Cadence');
    case 'speed_ms': return t('Speed');
    case 'altitude_m': return t('Altitude');
    case 'grade_pct': return t('Grade');
    case 'temperature_c': return t('Temperature');
    case 'ground_time_ms': return t('Ground contact time');
    case 'oscillation_mm': return t('Vertical oscillation');
    case 'vertical_ratio': return t('Vertical ratio');
    case 'leg_spring_kn_m': return t('Leg spring stiffness');
    case 'form_power_watts': return t('Form power');
    case 'respiration_rate': return t('Respiration rate');
  }
}

function numberValue(value: number | null, unit = ''): string {
  return value != null && Number.isFinite(value) && value > 0 ? `${Math.round(value)}${unit}` : '—';
}

function paceValue(value: number | string | null): string {
  return value == null ? '—' : formatStoredPace(value);
}

function kilometerReason(code: KilometerUnavailableReason | null): string {
  switch (code) {
    case 'samples_unavailable': return t('No time-series samples are stored.');
    case 'distance_trace_unavailable': return t('No recorded distance trace is stored.');
    case 'distance_trace_incomplete': return t('The recorded distance trace has missing intervals.');
    case 'distance_trace_non_monotonic': return t('The recorded distance moves backward.');
    case 'distance_below_display_precision': return t("The activity is shorter than the table's 0.01 km resolution.");
    case 'start_time_unverified': return t('The activity start time cannot be verified.');
    case 'duration_alignment_unverified': return t('Recorded time and activity duration do not align.');
    case 'activity_distance_mismatch': return t('Recorded and summary distances do not match.');
    default: return '';
  }
}

function buildSplit(split: SplitData | ActivityKilometerSplit, recorded: boolean): SplitRow {
  const pace = recorded ? (split as SplitData).avg_pace_min_km : (split as ActivityKilometerSplit).pace_sec_km;
  const source = recorded ? split as SplitData : null;
  return {
    number: split.split_num,
    numberLabel: String(split.split_num).padStart(2, '0'),
    distance: split.distance_km != null ? split.distance_km.toFixed(2) : '—',
    duration: split.duration_sec != null ? elapsed(split.duration_sec) : '—',
    pace: paceValue(pace),
    power: numberValue(source?.avg_power ?? null, ' W'),
    heart: numberValue(source?.avg_hr ?? null, ' bpm'),
  };
}

function buildView(detail: ActivityDetailResponse, samples: ActivityDetailSample[]): DetailView {
  const activity: Activity = detail.activity;
  const locale = detectLocale();
  const first = activity.splits[0];
  const last = activity.splits[activity.splits.length - 1];
  const saved: SavedRow[] = [
    { label: t('Average power'), value: numberValue(activity.avg_power, ' W') },
    { label: t('Average heart rate'), value: numberValue(activity.avg_hr, ' bpm') },
    { label: t('Average pace'), value: paceValue(activity.avg_pace_min_km) },
    { label: t('Maximum power'), value: numberValue(activity.max_power, ' W') },
    { label: t('Maximum heart rate'), value: numberValue(activity.max_hr, ' bpm') },
    { label: t('Elevation gain'), value: numberValue(activity.elevation_gain_m, ' m') },
    { label: t('Temperature'), value: activity.temperature_c == null ? '—' : `${activity.temperature_c} °C` },
    { label: t('Relative humidity'), value: activity.relative_humidity_pct == null ? '—' : `${activity.relative_humidity_pct}%` },
    { label: 'RSS', value: numberValue(activity.rss) },
    { label: t('Source CP estimate'), value: numberValue(activity.cp_estimate, ' W') },
  ].filter((row) => row.value !== '—');

  const primarySummary = activity.avg_power != null && activity.avg_power > 0
    ? { label: t('Average power'), value: numberValue(activity.avg_power), unit: 'W' }
    : { label: t('Average heart rate'), value: numberValue(activity.avg_hr), unit: 'bpm' };
  return {
    title: (() => {
      switch (activity.activity_type.toLowerCase()) {
        case 'running': return t('Running');
        case 'trail_running': return t('Trail running');
        case 'walking': return t('Walking');
        case 'hiking': return t('Hiking');
        case 'cycling': return t('Cycling');
        case 'swimming': return t('Swimming');
        default: return activity.activity_type.replace(/_/g, ' ');
      }
    })(),
    date: new Date(`${activity.date}T12:00:00`).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
      year: 'numeric', month: 'long', day: 'numeric',
    }),
    source: activity.source || t('Source unavailable'),
    environmentSource: activity.environment_source || '',
    hasLapComparison: Boolean(first && last && first !== last
      && first.avg_pace_min_km && last.avg_pace_min_km
      && paceValue(first.avg_pace_min_km) !== '—' && paceValue(last.avg_pace_min_km) !== '—'),
    firstLapPace: first ? paceValue(first.avg_pace_min_km) : '—',
    lastLapPace: last ? paceValue(last.avg_pace_min_km) : '—',
    summary: [
      { label: t('Distance'), value: activity.distance_km != null && activity.distance_km > 0 ? activity.distance_km.toFixed(2) : '—', unit: 'km' },
      { label: t('Duration'), value: activity.duration_sec != null && activity.duration_sec > 0 ? elapsed(activity.duration_sec) : '—', unit: '' },
      { label: t('Average pace'), value: paceValue(activity.avg_pace_min_km).split(' ')[0], unit: '/km' },
      primarySummary,
    ],
    recordedSplits: activity.splits.map((split) => buildSplit(split, true)),
    kilometerSplits: detail.kilometer_splits.map((split) => buildSplit(split, false)),
    saved,
    savedCount: saved.length + recordedMetrics(samples).length,
    sampleCount: detail.sample_count,
    partial: activity.sample_coverage.state === 'partial',
    sourceRows: detail.sample_sources.join(', ') || '—',
    sampleStartOnly: detail.time_origin === 'sample_start',
    hasReferenceScores: activity.rss != null || activity.cp_estimate != null,
    kilometerReason: kilometerReason(detail.kilometer_unavailable_reason),
  };
}

Page({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass,
    theme: resolveTheme(),
    languageClass: detectLocale() === 'en' ? 'lang-en' : 'lang-zh',
    id: '',
    loading: true,
    errorMessage: '',
    notFound: false,
    response: null as ActivityDetailResponse | null,
    view: null as DetailView | null,
    tr: translations(),
    metrics: [] as MetricChoice[],
    featuredMetrics: [] as MetricChoice[],
    extraMetrics: [] as MetricChoice[],
    featuredExtra: null as MetricChoice | null,
    metricsExpanded: false,
    primary: '' as TraceKey | '',
    secondary: '' as TraceKey | '',
    primaryLabel: '',
    secondaryLabel: '',
    overlayOptions: [] as OverlayChoice[],
    overlayIndex: 0,
    splitMode: 'recorded' as 'recorded' | 'kilometers',
    selected: null as ActivityKilometerSplit | null,
    selectedText: '',
    rangeStart: 0,
    rangeEnd: 0,
    fullStart: 0,
    fullEnd: 0,
    cursor: 0,
    savedOpen: false,
    scrollTarget: '',
  },

  onLoad(options: Record<string, string>) {
    const id = decodeURIComponent(options.id || '');
    this.setData({ id });
    if (id) void this.fetchDetail(id);
    else this.setData({ loading: false, notFound: true });
  },

  onShow() {
    const languageClass = detectLocale() === 'en' ? 'lang-en' : 'lang-zh';
    if (languageClass !== this.data.languageClass) {
      this.setData({ languageClass, tr: translations() });
      if (this.data.id) void this.fetchDetail(this.data.id);
    }
    this.setData({ themeClass: themeClassName(), theme: resolveTheme() });
    applyThemeChrome();
  },

  onBack() {
    if (getCurrentPages().length > 1) wx.navigateBack();
    else wx.switchTab({ url: '/pages/analysis/index' });
  },

  onRetry() { if (this.data.id) void this.fetchDetail(this.data.id); },

  async fetchDetail(id: string) {
    this.setData({ loading: true, errorMessage: '', notFound: false, response: null, view: null });
    try {
      const response = await apiGet<ActivityDetailResponse>(`/api/history/${encodeURIComponent(id)}/detail`);
      const metrics = recordedMetrics(response.samples).map((key) => ({ key, label: metricLabel(key) }));
      const common = metrics.filter((metric) => ['power_watts', 'hr_bpm', 'pace_sec_km'].includes(metric.key));
      const featuredMetrics = common.length ? common : metrics.slice(0, 3);
      const extraMetrics = metrics.filter((metric) => !featuredMetrics.some((featured) => featured.key === metric.key));
      const desired = response.training_base === 'hr' ? 'hr_bpm' : response.training_base === 'pace' ? 'pace_sec_km' : 'power_watts';
      const primary = metrics.some((metric) => metric.key === desired) ? desired : metrics[0]?.key || '';
      const secondary = metrics.find((metric) => metric.key !== primary)?.key || '';
      const fullStart = response.samples[0]?.offset_sec ?? 0;
      const fullEnd = response.samples[response.samples.length - 1]?.offset_sec ?? 0;
      this.setData({
        loading: false,
        response,
        view: buildView(response, response.samples),
        metrics,
        featuredMetrics,
        extraMetrics,
        featuredExtra: null,
        metricsExpanded: false,
        primary,
        secondary,
        primaryLabel: primary ? metricLabel(primary) : '',
        secondaryLabel: secondary ? metricLabel(secondary) : '',
        overlayOptions: this.overlayChoices(metrics, primary),
        overlayIndex: secondary ? 1 : 0,
        fullStart, fullEnd, rangeStart: fullStart, rangeEnd: fullEnd, cursor: fullStart,
        splitMode: response.activity.splits.length ? 'recorded' : 'kilometers',
        selected: null, selectedText: '', savedOpen: false,
      });
    } catch (error) {
      const failure = error as Partial<ApiError>;
      if (failure.code === 'UNAUTHENTICATED') { this.setData({ loading: false }); return; }
      this.setData({
        loading: false,
        notFound: failure.status === 404,
        errorMessage: failure.status === 404 ? '' : t('Check your connection and retry. No stale record is shown.'),
      });
    }
  },

  overlayChoices(metrics: MetricChoice[], primary: TraceKey | ''): OverlayChoice[] {
    return [{ key: '', label: t('No overlay') }, ...metrics.filter((metric) => metric.key !== primary)];
  },

  onToggleMetrics() { this.setData({ metricsExpanded: !this.data.metricsExpanded }); },

  onPrimary(event: WechatMiniprogram.TouchEvent) {
    const key = String(event.currentTarget.dataset.key) as TraceKey;
    if (!this.data.metrics.some((metric) => metric.key === key)) return;
    const secondary = this.data.secondary === key ? '' : this.data.secondary;
    const options = this.overlayChoices(this.data.metrics, key);
    this.setData({ primary: key, secondary,
      featuredExtra: this.data.extraMetrics.find((metric) => metric.key === key) || null,
      primaryLabel: metricLabel(key), secondaryLabel: secondary ? metricLabel(secondary) : '', overlayOptions: options,
      overlayIndex: options.findIndex((option) => option.key === secondary) });
  },

  onOverlay(event: WechatMiniprogram.CustomEvent<{ value: string }>) {
    const index = Number(event.detail.value);
    const choice = this.data.overlayOptions[index];
    if (!choice) return;
    this.setData({ secondary: choice.key, secondaryLabel: choice.key ? metricLabel(choice.key) : '', overlayIndex: index });
  },

  onMode(event: WechatMiniprogram.TouchEvent) {
    const mode = String(event.currentTarget.dataset.mode);
    if (mode === 'kilometers' && !this.data.response?.kilometer_splits.length) return;
    if (mode === 'recorded' && !this.data.response?.activity.splits.length) return;
    if (mode === 'kilometers' || mode === 'recorded') this.setData({ splitMode: mode });
  },

  goTo(id: string) {
    this.setData({ scrollTarget: '' });
    wx.nextTick(() => this.setData({ scrollTarget: id }));
  },

  onSelectKilometer(event: WechatMiniprogram.TouchEvent) {
    if (!this.data.metrics.length) return;
    const number = Number(event.currentTarget.dataset.number);
    const selected = this.data.response?.kilometer_splits.find((split) => split.split_num === number);
    if (!selected) return;
    this.setData({
      selected,
      selectedText: `${t('Kilometer')} ${number} · ${selected.distance_km.toFixed(2)} km · ${elapsed(selected.duration_sec)} · ${paceValue(selected.pace_sec_km)}`,
      rangeStart: selected.start_offset_sec, rangeEnd: selected.end_offset_sec, cursor: selected.start_offset_sec,
    });
    this.goTo('activity-chart');
  },

  onReturnToSplit() {
    if (!this.data.selected) return;
    this.setData({ splitMode: 'kilometers' });
    this.goTo(`kilometer-${this.data.selected.split_num}`);
  },

  onChartRange(event: WechatMiniprogram.CustomEvent<{ start: number; end: number }>) {
    const start = Math.max(this.data.fullStart, Math.floor(event.detail.start));
    const end = Math.min(this.data.fullEnd, Math.ceil(event.detail.end));
    if (start >= end) return;
    this.setData({ rangeStart: start, rangeEnd: end,
      cursor: Math.max(start, Math.min(end, this.data.cursor)) });
  },

  onChartCursor(event: WechatMiniprogram.CustomEvent<{ offset: number }>) {
    const value = Math.round(event.detail.offset);
    this.setData({ cursor: Math.max(this.data.rangeStart, Math.min(this.data.rangeEnd, value)) });
  },

  onToggleSaved() { this.setData({ savedOpen: !this.data.savedOpen }); },
  onSeeSaved() { this.setData({ savedOpen: true }); this.goTo('activity-saved'); },

  onSavedMetric(event: WechatMiniprogram.TouchEvent) {
    const key = String(event.currentTarget.dataset.key) as TraceKey;
    if (!this.data.metrics.some((metric) => metric.key === key)) return;
    const options = this.overlayChoices(this.data.metrics, key);
    this.setData({ primary: key, primaryLabel: metricLabel(key), secondary: '', secondaryLabel: '', overlayOptions: options, overlayIndex: 0,
      featuredExtra: this.data.extraMetrics.find((metric) => metric.key === key) || null,
      metricsExpanded: true });
    this.goTo('activity-chart');
  },
});
