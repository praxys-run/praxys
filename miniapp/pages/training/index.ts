import { setTabBarSelected } from '../../utils/tabbar';
import type { IAppOption } from '../../app';
import {
  HEAT_HISTORY_SCROLL_KEY,
  HEAT_HISTORY_SCROLL_TARGET,
} from '../../utils/heat-adaptation';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import { detectLocale, t } from '../../utils/i18n';

function buildTrainingTr() {
  return {
    navTitle: t('Training'),
    planManagement: t('Plan management'),
    planDescription: t('Start, review, and adjust the plan Praxys manages for you.'),
  };
}

interface TrainingState {
  themeClass: string;
  languageClass: string;
  refreshing: boolean;
  tr: ReturnType<typeof buildTrainingTr>;
}

interface RefreshableComponent {
  refresh?: () => Promise<void>;
}

interface PageMethods extends WechatMiniprogram.IAnyObject {
  onScrollRefresh(): void;
}

function hasLegacyHeatTarget(): boolean {
  try {
    return wx.getStorageSync<string>(HEAT_HISTORY_SCROLL_KEY)
      === HEAT_HISTORY_SCROLL_TARGET;
  } catch {
    return false;
  }
}

Page<TrainingState, PageMethods>({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass,
    languageClass: detectLocale() === 'en' ? 'lang-en' : 'lang-zh',
    refreshing: false,
    tr: buildTrainingTr(),
  },

  onLoad(options: Record<string, string | undefined>) {
    this.setData({
      themeClass: themeClassName(),
      languageClass: detectLocale() === 'en' ? 'lang-en' : 'lang-zh',
      tr: buildTrainingTr(),
    });
    const pageState = this as unknown as Record<string, unknown>;
    pageState._locale = getApp<IAppOption>().globalData.locale;
    if (options.metric === 'heat' || options.detail === HEAT_HISTORY_SCROLL_TARGET) {
      try {
        wx.setStorageSync(HEAT_HISTORY_SCROLL_KEY, HEAT_HISTORY_SCROLL_TARGET);
      } catch {
        // Analysis still remains reachable through the visible page action.
      }
    }
  },

  onShow() {
    const themeClass = themeClassName();
    if (themeClass !== this.data.themeClass) {
      this.setData({ themeClass });
    }
    const pageState = this as unknown as Record<string, unknown>;
    const locale = getApp<IAppOption>().globalData.locale;
    if (locale !== pageState._locale) {
      pageState._locale = locale;
      this.setData({
        languageClass: locale === 'en' ? 'lang-en' : 'lang-zh',
        tr: buildTrainingTr(),
      });
    }
    applyThemeChrome();
    setTabBarSelected(this, 1);
    const isReturning = pageState._hasShown === true;
    pageState._hasShown = true;
    if (isReturning) {
      const planStart = this.selectComponent(
        '#training-plan-start',
      ) as unknown as RefreshableComponent | null;
      void planStart?.refresh?.();
    }
    if (hasLegacyHeatTarget() && pageState._openingLegacyAnalysis !== true) {
      pageState._openingLegacyAnalysis = true;
      wx.switchTab({
        url: '/pages/analysis/index',
        complete: () => {
          pageState._openingLegacyAnalysis = false;
        },
      });
    }
  },

  async onScrollRefresh() {
    this.setData({ refreshing: true });
    const planStart = this.selectComponent(
      '#training-plan-start',
    ) as unknown as RefreshableComponent | null;
    const managedPlan = this.selectComponent(
      '#training-managed-plan',
    ) as unknown as RefreshableComponent | null;
    const personalContext = this.selectComponent(
      '#training-personal-context',
    ) as unknown as RefreshableComponent | null;
    try {
      const road10k = this.selectComponent(
        '#training-road-10k',
      ) as unknown as RefreshableComponent | null;
      await Promise.all([
        road10k?.refresh?.() ?? Promise.resolve(),
        planStart?.refresh?.() ?? Promise.resolve(),
        managedPlan?.refresh?.() ?? Promise.resolve(),
        personalContext?.refresh?.() ?? Promise.resolve(),
      ]);
    } finally {
      this.setData({ refreshing: false });
    }
  },
});
