import { apiGet } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import type { Activity, HistoryResponse } from '../../types/api';
import { formatDistance, formatTime } from '../../utils/format';
import { detectLocale, t, tFmt } from '../../utils/i18n';

function translations() {
  return {
    failedToLoad: t('Failed to load'),
    loadingMore: t('Loading more…'),
    endOfActivities: t('End of activities'),
    noActivities: t('No activities found.'),
    splits: t('Splits'),
    more: t('more'),
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
  id: string;
  date: string;
  type: string;
  metrics: MetricRow[];
  hasSplits: boolean;
  splitCount: number;
  splitsDisplay: SplitRow[];
  hasMoreSplits: boolean;
  moreSplitsCount: number;
  expanded: boolean;
  tapHint: string;
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
  const formatted = raw
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
  return t(formatted);
}

function buildActivityRow(activity: Activity): ActivityRow {
  const metrics: MetricRow[] = [];
  if (activity.distance_km != null) {
    metrics.push({ label: t('km'), value: formatDistance(activity.distance_km) });
  }
  if (activity.duration_sec != null) {
    metrics.push({ label: t('time'), value: formatTime(activity.duration_sec) });
  }
  if (activity.avg_power != null) {
    metrics.push({ label: t('avg W'), value: `${activity.avg_power.toFixed(0)}` });
  }
  if (activity.avg_hr != null) {
    metrics.push({ label: t('avg HR'), value: `${activity.avg_hr.toFixed(0)}` });
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
    id: activity.activity_id,
    date: activity.date,
    type: formatActivityType(activity.activity_type),
    metrics,
    hasSplits: splits.length > 0,
    splitCount: splits.length,
    splitsDisplay,
    hasMoreSplits: splits.length > 20,
    moreSplitsCount: Math.max(0, splits.length - 20),
    expanded: false,
    tapHint: splits.length > 0 ? tFmt('Tap to view {0} splits', splits.length) : '',
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
        const newRows = response.activities.map(buildActivityRow);
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
