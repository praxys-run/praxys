import { setTabBarSelected } from '../../utils/tabbar';
import type { IAppOption } from '../../app';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import { detectLocale, t } from '../../utils/i18n';
import { apiGet } from '../../utils/api-client';
import type { SettingsResponse } from '../../types/api';
import { MINIAPP_BUILD_VERSION } from '../../utils/version';

function translations() {
  return {
    navTitle: t('Me'),
    accountData: t('Account & data'),
    settings: t('Settings'),
    settingsDetail: t(
      'Connections, thresholds, plan delivery, preferences, and account access.',
    ),
    explore: t('Explore'),
    science: t('Training Science'),
    scienceDetail: t('Browse the load / recovery / prediction / zone theories'),
    labs: t('Labs'),
    labsDetail: t('Explore voluntary experiments on your own training history'),
    experimental: t('Experimental'),
    about: t('About'),
    legal: t('Terms & Privacy'),
    legalDetail: t('Legal documents, privacy, and data rights.'),
  };
}

Page({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass,
    locale: detectLocale(),
    tr: translations(),
    appVersion: MINIAPP_BUILD_VERSION,
    showLabs: false,
  },

  onLoad() {
    this.setData({
      themeClass: themeClassName(),
      locale: detectLocale(),
      tr: translations(),
    });
  },

  onShow() {
    const themeClass = themeClassName();
    const locale = detectLocale();
    const patch: Record<string, unknown> = {};
    if (themeClass !== this.data.themeClass) patch.themeClass = themeClass;
    if (locale !== this.data.locale) {
      patch.locale = locale;
      patch.tr = translations();
    }
    if (Object.keys(patch).length > 0) this.setData(patch);
    applyThemeChrome();
    setTabBarSelected(this, 4);
    void this.refreshPrivateCapabilities();
  },

  async refreshPrivateCapabilities() {
    try {
      const settings = await apiGet<SettingsResponse>('/api/settings');
      const showLabs = Object.prototype.hasOwnProperty.call(
        settings.platform_capabilities,
        'stryd',
      );
      if (showLabs !== this.data.showLabs) this.setData({ showLabs });
    } catch (error) {
      console.warn('[me] private capability check failed:', error);
    }
  },

  onOpenSettings() {
    wx.navigateTo({ url: '/pages/settings/index' });
  },

  onOpenScience() {
    wx.navigateTo({ url: '/pages/science/index' });
  },

  onOpenLabs() {
    wx.navigateTo({ url: '/pages/labs/index' });
  },

  onOpenLegal() {
    wx.navigateTo({ url: '/pages/legal/index?kind=terms' }); // i18n-allow
  },
});
