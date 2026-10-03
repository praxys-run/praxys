import { apiGet } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import type { Activity, HistoryResponse } from '../../types/api';
import { formatDistance, formatTime, formatStoredPace } from '../../utils/format';
import { detectLocale, t, tFmt } from '../../utils/i18n';

function translations() {
  return {
    detail: t('View details'),
    failedToLoad: t('Failed to load'),
    loadingMore: t('Loading more…'),
    endOfActivities: t('End of activities'),
    noActivities: t('No activities found.'),
    splits: t('Recorded splits'),
    more: t('more'),
    viewReport: t('View report'),
  };
}

const PAGE_SIZE = 20;

interface MetricRow {
  label: string;
  value: string;
}

interface SplitRow {
  num: string;
  cells: string[];
}

interface ActivityRow {
  activity: Activity;
  id: string;
  detailAvailable: boolean;
  date: string;
  activityDate: string;
  detailUrl: string;
  glyph: string;
  secondaryMetrics: MetricRow[];
  type: string;
  metrics: MetricRow[];
  hasSplits: boolean;
  splitCount: number;
  splitsDisplay: SplitRow[];
  hasMoreSplits: boolean;
  moreSplitsCount: number;
  expanded: boolean;
}

interface ActivityHistoryState {
  locale: 'en' | 'zh';
  loading: boolean;
  loadingMore: boolean;
  errorMessage: string;
  activities: ActivityRow[];
  total: number;
  hasActivities: boolean;
  hasReachedEnd: boolean;
  totalLine: string;
  offset: number;
  tr: ReturnType<typeof translations>;
}

function formatActivityType(raw: string): string {
  switch (raw.toLowerCase()) {
    case 'running': return t('Running');
    case 'trail_running': return t('Trail running');
    case 'walking': return t('Walking');
    case 'hiking': return t('Hiking');
    case 'cycling': return t('Cycling');
    case 'swimming': return t('Swimming');
    default: return raw.replace(/_/g, ' ');
  }
}

function buildActivityRow(activity: Activity, detailAvailable: boolean): ActivityRow {
  const metrics: MetricRow[] = [];
  if (activity.distance_km != null) {
    metrics.push({ label: t('km'), value: formatDistance(activity.distance_km) });
  }
  if (activity.duration_sec != null) {
    metrics.push({ label: t('time'), value: formatTime(activity.duration_sec) });
  }
  if (activity.avg_pace_min_km != null) {
    metrics.push({ label: t('Pace'), value: formatStoredPace(activity.avg_pace_min_km) });
  }
  const secondaryMetrics: MetricRow[] = [];
  if (activity.avg_power != null) {
    secondaryMetrics.push({ label: t('avg W'), value: `${activity.avg_power.toFixed(0)}` });
  }
  if (activity.avg_hr != null) {
    secondaryMetrics.push({ label: t('avg HR'), value: `${activity.avg_hr.toFixed(0)}` });
  }

  const splits = activity.splits ?? [];
  const splitsDisplay: SplitRow[] = splits.slice(0, 20).map((split) => {
    const cells: string[] = [];
    if (split.distance_km != null) cells.push(formatDistance(split.distance_km));
    if (split.duration_sec != null) cells.push(formatTime(split.duration_sec));
    if (split.avg_power != null) cells.push(`${split.avg_power.toFixed(0)} W`);
    return { num: `#${split.split_num}`, cells };
  });

  return {
    activity,
    id: activity.activity_id,
    detailAvailable,
    date: new Date(activity.date).toLocaleDateString(detectLocale() === 'zh' ? 'zh-CN' : 'en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
    activityDate: activity.date,
    detailUrl: `/pages/activity-detail/index?id=${encodeURIComponent(activity.activity_id)}`,
    glyph: activity.activity_type === 'cycling' ? 'bike' : activity.activity_type === 'swimming' ? 'waves'
      : ['hiking', 'trail_running'].includes(activity.activity_type) ? 'mountain'
        : ['running', 'walking'].includes(activity.activity_type) ? 'footprints' : 'activity',
    secondaryMetrics,
    type: formatActivityType(activity.activity_type),
    metrics,
    hasSplits: splits.length > 0,
    splitCount: splits.length,
    splitsDisplay,
    hasMoreSplits: splits.length > 20,
    moreSplitsCount: Math.max(0, splits.length - 20),
    expanded: false,
  };
}

Component({
  options: { addGlobalClass: true },

  properties: {
    tabbed: {
      type: Boolean as BooleanConstructor,
      value: false,
    },
  },

  data: {
    locale: detectLocale(),
    loading: true,
    loadingMore: false,
    errorMessage: '',
    activities: [],
    total: 0,
    hasActivities: false,
    hasReachedEnd: false,
    totalLine: '',
    offset: 0,
    tr: translations(),
  } as ActivityHistoryState,

  lifetimes: {
    attached() {
      this.setData({
        locale: detectLocale(),
        tr: translations(),
      });
      void this.refresh();
    },
  },

  pageLifetimes: {
    show() {
      const locale = detectLocale();
      if (locale !== this.data.locale) {
        this.setData({ locale, tr: translations() });
        void this.refresh();
      }
    },
  },

  methods: {
    onDetail(event: WechatMiniprogram.TouchEvent) {
      const row=this.data.activities.find(v=>v.id===String(event.currentTarget.dataset.id));
      if(row)this.triggerEvent('detail',{activity:row.activity});
    },
    refresh(): Promise<void> {
      return this.fetchPage(0, true);
    },

    loadMore() {
      if (this.data.loadingMore || this.data.loading) return;
      if (this.data.activities.length >= this.data.total) return;
      void this.fetchPage(this.data.offset, false);
    },

    onRetry() {
      void this.refresh();
    },

    toggleExpand(event: WechatMiniprogram.TouchEvent) {
      const id = String(event.currentTarget.dataset.id ?? '');
      if (!id) return;
      const selected = (this.data.activities as ActivityRow[]).find(
        (activity) => activity.id === id,
      );
      if (!selected?.hasSplits) return;
      const activities = (this.data.activities as ActivityRow[]).map((activity) =>
        activity.id === id
          ? { ...activity, expanded: !activity.expanded }
          : activity,
      );
      this.setData({ activities });
    },

    openDetail(event: WechatMiniprogram.TouchEvent) {
      const id = String(event.currentTarget.dataset.id ?? '');
      if (!id || !(this.data.activities as ActivityRow[]).some(
        (activity) => activity.id === id && activity.detailAvailable,
      )) return;
      wx.navigateTo({ url: `/pages/activity-detail/index?id=${encodeURIComponent(id)}` });
    },

    async fetchPage(nextOffset: number, replace: boolean): Promise<void> {
      this.setData(
        replace
          ? { loading: true, errorMessage: '' }
          : { loadingMore: true, errorMessage: '' },
      );
      try {
        const response = await apiGet<HistoryResponse>(
          `/api/history?limit=${PAGE_SIZE}&offset=${nextOffset}`,
        );
        const newRows = response.activities.map((activity) =>
          buildActivityRow(activity, response.activity_detail_available),
        );
        const activities: ActivityRow[] = replace
          ? newRows
          : [...(this.data.activities as ActivityRow[]), ...newRows];
        const offset = nextOffset + response.activities.length;
        this.setData({
          loading: false,
          loadingMore: false,
          activities,
          total: response.total,
          hasActivities: activities.length > 0,
          hasReachedEnd: activities.length >= response.total && response.total > 0,
          totalLine: tFmt('{0} total · showing {1}', response.total, activities.length),
          offset,
        });
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        if (apiError?.code === 'UNAUTHENTICATED') {
          this.setData({ loading: false, loadingMore: false });
          return;
        }
        this.setData({
          loading: false,
          loadingMore: false,
          errorMessage: apiError?.detail ?? String(error),
        });
      }
    },
  },
});
