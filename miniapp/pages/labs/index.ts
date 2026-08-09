import type { IAppOption } from '../../app';
import { apiGet } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { t } from '../../utils/i18n';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import type { LabsEnvironmentResponseState } from '../../types/api';

function statusLabel(
  state: LabsEnvironmentResponseState,
): string {
  if (state.status === 'available') return t('Result ready');
  if (state.status === 'queued' || state.status === 'processing') return t('Analyzing');
  if (state.enrolled) return t('Participating');
  return t('Open to check');
}

Page({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass || themeClassName(),
    tr: {
      navTitle: t('Praxys Labs'),
      intro: t('Choose voluntary experiments that help you inspect your own training history without turning early research into advice.'),
      availableExperiments: t('Available experiments'),
      experimentsDetail: t('Each experiment has its own consent, data requirements, limitations, and withdrawal controls.'),
      environmentTitle: t('Environmental response'),
      environmentDetail: t('Explore whether modeled heart rate varied with temperature and humidity at comparable recorded Stryd power in your eligible past runs.'),
      environmentBoundary: t('Historical association only · personal aggregate result · continuous Stryd samples required'),
      openExperiment: t('Open experiment'),
      failedToLoad: t('Labs could not load'),
      retry: t('Retry'),
    },
    loading: true,
    errorMessage: '',
    statusLabel: '',
  },

  onLoad() {
    this.refetch();
  },

  onShow() {
    applyThemeChrome();
  },

  async refetch() {
    this.setData({ loading: true, errorMessage: '' });
    try {
      const state = await apiGet<LabsEnvironmentResponseState>(
        '/api/labs/environment-response',
      );
      this.setData({
        loading: false,
        statusLabel: statusLabel(state),
      });
    } catch (error) {
      const detail = (error as ApiError)?.detail || t('Network error. Try again.');
      this.setData({ loading: false, errorMessage: detail });
    }
  },

  onRetry() {
    this.refetch();
  },

  onOpenEnvironment() {
    wx.navigateTo({ url: '/pages/labs/environment-response/index' });
  },
});
