import type { IAppOption } from '../../app';
import { apiGet } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { t } from '../../utils/i18n';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import type { LabsEnvironmentResponseState } from '../../types/api';
import type { LabsEnvironmentPreflightResponse } from '../../types/api';

const PREFLIGHT_REQUEST_TIMEOUT_MS = 15000;

function statusLabel(
  state: LabsEnvironmentResponseState,
  preflight: LabsEnvironmentPreflightResponse | null,
  preflightLoading: boolean,
  preflightError: boolean,
): string {
  if (state.status === 'available') return t('Result ready');
  if (state.status === 'queued' || state.status === 'processing') return t('Analyzing');
  if (state.enrolled) return t('Participating');
  if (preflightLoading) return t('Checking eligibility');
  if (preflightError) return t('Eligibility check unavailable');
  if (preflight?.status === 'ineligible') return t('Needs data');
  if (preflight?.status === 'needs_full_analysis') return t('Check required');
  return t('Ready to check');
}

function reasonLabel(preflight: LabsEnvironmentPreflightResponse | null): string {
  const reasons: Record<string, () => string> = {
    insufficient_activities: () => t('There are not enough eligible Stryd activities yet.'),
    missing_environment_pairing: () => t('Temperature and humidity are not both present on enough of the same activities.'),
    missing_continuous_sample_power: () => t('Continuous Stryd sample power is missing from too much of the eligible history.'),
    missing_continuous_heart_rate: () => t('Continuous heart-rate samples are missing from too much of the eligible history.'),
    insufficient_prerequisite_overlap: () => t('The required environment, power, and heart-rate data do not overlap on enough of the same runs.'),
    unsupported_power_provider: () => t('This first experiment currently supports continuous Stryd power only.'),
    missing_provider_aligned_critical_power: () => t('A Stryd-aligned Critical Power value is required for this experiment.'),
    missing_temperature: () => t('Temperature is missing from too many otherwise eligible activities.'),
    missing_relative_humidity: () => t('Relative humidity is missing from too many otherwise eligible activities.'),
    provider_alignment_requires_full_analysis: () => t('Your history includes enough broad sample coverage, but the full analysis must confirm that power, heart rate, and Critical Power use one compatible Stryd regime.'),
  };
  return preflight?.reason_code ? (reasons[preflight.reason_code]?.() ?? '') : '';
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
    reasonLabel: '',
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
        statusLabel: statusLabel(state, null, true, false),
        reasonLabel: '',
      });
      try {
        const preflight = await apiGet<LabsEnvironmentPreflightResponse>(
          '/api/labs/environment-response/preflight',
          { timeoutMs: PREFLIGHT_REQUEST_TIMEOUT_MS },
        );
        this.setData({
          statusLabel: statusLabel(state, preflight, false, false),
          reasonLabel: state.enrolled ? '' : reasonLabel(preflight),
        });
      } catch {
        this.setData({
          statusLabel: statusLabel(state, null, false, true),
          reasonLabel: '',
        });
      }
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
