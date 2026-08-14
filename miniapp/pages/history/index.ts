import type { IAppOption } from '../../app';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import { detectLocale, t } from '../../utils/i18n';

interface ActivityHistoryComponent {
  refresh(): Promise<void>;
  loadMore(): void;
}

Page({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass,
    languageClass: detectLocale() === 'en' ? 'lang-en' : 'lang-zh',
    refreshing: false,
    navTitle: t('Activities'),
  },

  onLoad() {
    const themeClass = themeClassName();
    this.setData({
      themeClass,
      languageClass: detectLocale() === 'en' ? 'lang-en' : 'lang-zh',
      navTitle: t('Activities'),
    });
  },

  onShow() {
    const themeClass = themeClassName();
    this.setData({
      themeClass,
      languageClass: detectLocale() === 'en' ? 'lang-en' : 'lang-zh',
      navTitle: t('Activities'),
    });
    applyThemeChrome();
  },

  onBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/analysis/index' });
  },

  onScrollRefresh() {
    this.setData({ refreshing: true });
    const history = this.selectComponent(
      '#legacy-activity-history',
    ) as unknown as ActivityHistoryComponent | null;
    void (history?.refresh() ?? Promise.resolve()).finally(() => {
      this.setData({ refreshing: false });
    });
  },

  onScrollToBottom() {
    const history = this.selectComponent(
      '#legacy-activity-history',
    ) as unknown as ActivityHistoryComponent | null;
    history?.loadMore();
  },
});
