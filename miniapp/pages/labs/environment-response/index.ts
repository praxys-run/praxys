import type { IAppOption } from '../../../app';
import { apiDelete, apiGet, apiPost } from '../../../utils/api-client';
import type { ApiError } from '../../../utils/api-client';
import { t } from '../../../utils/i18n';
import {
  applyThemeChrome,
  resolveTheme,
  themeClassName,
} from '../../../utils/theme';
import type {
  LabsEnvironmentPreflightResponse,
  LabsEnvironmentResponseState,
  LabsEnvironmentWetBulbResponse,
} from '../../../types/api';

const CONSENT_VERSION = 'environment-response-consent-v1';
const STULL_SOURCE_URL = 'https://doi.org/10.1175/JAMC-D-11-0143.1';

function buildLabsTr() {
  return {
    navTitle: t('Environmental response'),
    intro: t('Voluntary experiments that help you inspect your own training history without turning early research into advice.'),
    failedToLoad: t('Labs could not load'),
    retry: t('Retry'),
    joinTitle: t('Join this personal experiment'),
    joinDetail: t('Praxys will analyze eligible past runs to see whether modeled heart rate varied with temperature-and-humidity conditions at comparable recorded Stryd power.'),
    personalOnly: t('Personal only'),
    personalOnlyDetail: t('Your result is not pooled with other users and is not donated to cohort research.'),
    aggregateStorage: t('Aggregate storage'),
    aggregateStorageDetail: t('Praxys stores curve points, uncertainty, counts, gates, versions, and timestamps—not routes, activity dates, raw samples, or per-activity research rows.'),
    withdrawAnytime: t('Withdraw anytime'),
    withdrawAnytimeDetail: t('Withdrawal immediately deletes experiment consent and the derived result. Your ordinary account activities remain unchanged.'),
    limitsTitle: t('What this can—and cannot—tell you'),
    limitsDetail: t('This is a retrospective historical association. It does not forecast a future run, prove that heat caused a heart-rate change, prescribe pace, measure adaptation or hydration, or assess heat safety.'),
    adultConsent: t('I confirm that I am 18 or older. Praxys records this attestation, not my birth date.'),
    experimentConsent: t('I understand the purpose, limits, storage, and withdrawal terms above and choose to participate in this experiment.'),
    joinAction: t('Join and analyze my history'),
    processingTitle: t('Analyzing your eligible history'),
    processingDetail: t('Praxys is checking Stryd provenance, fitting the aggregate model, and applying every release guardrail.'),
    cancelWithdraw: t('Cancel and withdraw'),
    availableTitle: t('Historical association; not predictively validated'),
    availableDetail: t('One or more research diagnostics did not support predictive interpretation. Read the curve only as a pattern in eligible past runs.'),
    availablePassedTitle: t('Passed research diagnostics; not a forecast'),
    availablePassedDetail: t('The chronological holdout and sensitivity checks passed, but this personal historical association is still not a clinical claim or future-condition forecast.'),
    curveTitle: t('Your historical environmental-response curve'),
    partialCurveTitle: t('Your partial historical environmental-response curve'),
    curveDetail: t('Relative modeled heart rate across your observed wet-bulb-proxy range, holding the fitted comparison at a common recorded-power reference.'),
    partialCurveDetail: t('Relative modeled heart rate is shown only in ranges with enough comparable-power evidence. Unsupported ranges remain blank and are never connected.'),
    curveSeries: t('Relative modeled HR'),
    lowerSeries: t('Lower interval'),
    upperSeries: t('Upper interval'),
    supportTitle: t('Comparable-power activity support'),
    supportMinimum: t('minimum 5 per range'),
    supported: t('Supported'),
    insufficientSupport: t('Insufficient support'),
    activitiesUnit: t('activities'),
    supportExplanation: t('Each activity counts once per range. A qualifying activity needs an accepted stable segment averaging 75–85% of its pre-activity Stryd Critical Power; raw sample points alone do not count.'),
    activities: t('Eligible activities'),
    segments: t('Stable segments'),
    observedRange: t('Observed proxy range'),
    slope: t('Historical slope'),
    interval: t('Bootstrap interval'),
    powerRegime: t('Power regime'),
    strydPowerRegime: t('Continuous Stryd sample power'),
    modelVersion: t('Model version'),
    chartBoundary: t('This curve is historical and non-causal. Wind, solar load, clothing, hydration, fatigue, and other unmeasured conditions can still differ between runs.'),
    stullSource: t('Stull (2011) source'),
    unavailableTitle: t('No curve is available yet'),
    staleTitle: t('Your result needs recomputing'),
    failedTitle: t('The analysis did not finish'),
    recompute: t('Recompute'),
    supportId: t('Support ID'),
    calculatorTitle: t('Wet-bulb proxy calculator'),
    calculatorDetail: t('Combine air temperature and relative humidity using the same Stull estimate as the experiment.'),
    temperature: t('Temperature (°C)'),
    humidity: t('Humidity (%)'),
    calculate: t('Calculate proxy'),
    calculatorResult: t('Estimated psychrometric wet-bulb proxy'),
    calculatorOutside: t('This combination is outside Praxys’s conservative Stull method domain.'),
    calculatorInside: t('This sits inside your displayed historical range.'),
    calculatorBelow: t('This is below your displayed historical range, so the curve does not extrapolate to it.'),
    calculatorAbove: t('This is above your displayed historical range, so the curve does not extrapolate to it.'),
    calculatorUnsupported: t('This falls in an unsupported historical range, so it is not marked on the curve.'),
    calculatorBoundary: t('This is a psychrometric estimate—not apparent temperature, outdoor WBGT, body temperature, or a heat-safety assessment.'),
    withdraw: t('Withdraw and delete result'),
    withdrawTitle: t('Withdraw from this experiment?'),
    withdrawDetail: t('Praxys will immediately delete your Labs consent and derived aggregate result. Your underlying account activities are not deleted.'),
    keepParticipating: t('Keep participating'),
    confirmWithdraw: t('Withdraw and delete'),
    actionFailed: t('Labs action failed'),
    preflightEligible: t('Enough source data to attempt the experiment'),
    preflightUncertain: t('Full analysis must confirm eligibility'),
    preflightIneligible: t('Not enough suitable data to start yet'),
    preflightEligibleDetail: t('This quick check only covers definite prerequisites. The full analysis can still return insufficient support, an unstable association, or no conclusion.'),
    preflightIneligibleDetail: t('Praxys stopped before consent or long-running analysis. Sync or collect the missing data, then retry this check.'),
    suitableActivities: t('Activities passing quick prerequisites'),
    minimum: t('minimum'),
  };
}

const REASON_KEYS: Record<string, () => string> = {
  incomplete_export: () => t('The available history could not be analyzed as one complete snapshot.'),
  stale_source_revision: () => t('Your source data changed while this result was being computed.'),
  stale_model_version: () => t('This result uses an earlier experiment model and needs to be run again.'),
  insufficient_activities: () => t('There are not enough eligible Stryd activities yet.'),
  insufficient_segments: () => t('There are not enough stable, comparable segments yet.'),
  insufficient_environmental_spread: () => t('Your eligible runs do not cover enough different temperature-and-humidity conditions.'),
  insufficient_holdout: () => t('There is not enough chronological history to evaluate whether the relationship holds later.'),
  insufficient_curve_bin_support: () => t('Some parts of the environmental range do not have enough independent activity support.'),
  insufficient_reference_power_overlap: () => t('The same comparable-power range is not represented across enough environmental conditions.'),
  missing_continuous_sample_power: () => t('Continuous Stryd sample power is missing from too much of the eligible history.'),
  missing_continuous_heart_rate: () => t('Continuous heart-rate samples are missing from too much of the eligible history.'),
  missing_temperature: () => t('Temperature is missing from too many otherwise eligible activities.'),
  missing_relative_humidity: () => t('Relative humidity is missing from too many otherwise eligible activities.'),
  missing_environment_pairing: () => t('Temperature and humidity are not both present on enough of the same activities.'),
  missing_provider_aligned_critical_power: () => t('A Stryd-aligned Critical Power value is required for this experiment.'),
  critical_power_provider_mismatch: () => t('The available Critical Power does not match the eligible Stryd power regime.'),
  insufficient_sample_coverage: () => t('The continuous sample coverage is too sparse for a stable comparison.'),
  insufficient_prerequisite_overlap: () => t('Enough activities exist overall, but the required environment, power, and heart-rate data do not overlap on enough of the same runs.'),
  mixed_power_regime: () => t('The eligible history crosses incompatible power-device or algorithm regimes.'),
  unsupported_power_provider: () => t('This first experiment currently supports continuous Stryd power only.'),
  unverified_garmin_wrist_power: () => t('Garmin wrist-power origin cannot yet be verified well enough for this experiment.'),
  bootstrap_unstable: () => t('The estimated direction changes too much when activities are resampled.'),
  sensitivity_unstable: () => t('Reasonable model variations do not preserve the same historical relationship.'),
  influential_activity: () => t('A single activity has too much influence on the result.'),
  prediction_unavailable: () => t('The chronological prediction check could not be evaluated, so Praxys withholds the fitted curve.'),
  analysis_failed: () => t('The analysis did not finish successfully.'),
  provider_alignment_requires_full_analysis: () => t('Your history includes enough broad sample coverage, but the full analysis must confirm that power, heart rate, and Critical Power use one compatible Stryd regime.'),
};

function errorDetail(error: unknown): string {
  const apiError = error as ApiError;
  return apiError?.detail || t('Network error. Try again.');
}

function chartSeries(state: LabsEnvironmentResponseState) {
  const points = state.result?.aggregate_curve_points ?? [];
  const bins = state.result?.eligibility_counts.curve_support_bins ?? [];
  const pointsByBin = new Map(
    points.map((point) => [point.support_bin_index, point]),
  );
  const values = <K extends 'relative_lower_bpm' | 'relative_hr_bpm' | 'relative_upper_bpm'>(
    key: K,
  ) => (
    bins.length
      ? bins.map((bin) => pointsByBin.get(bin.bin_index)?.[key] ?? null)
      : points.map((point) => point[key])
  );
  return [
    {
      label: t('Lower interval'),
      color: '#8b93a7',
      values: values('relative_lower_bpm'),
      dashed: true,
    },
    {
      label: t('Relative modeled HR'),
      color: '#2e71c6',
      values: values('relative_hr_bpm'),
    },
    {
      label: t('Upper interval'),
      color: '#8b93a7',
      values: values('relative_upper_bpm'),
      dashed: true,
    },
  ];
}

function deriveState(state: LabsEnvironmentResponseState) {
  const result = state.result;
  const counts = result?.eligibility_counts;
  const observed = counts?.observed_wet_bulb_domain_c
    ?? state.availability_reason?.observed_aggregate?.observed_wet_bulb_domain_c
    ?? null;
  const activityCount = counts?.eligible_activity_count
    ?? state.availability_reason?.observed_aggregate?.eligible_activity_count
    ?? null;
  const segmentCount = counts?.eligible_segment_count
    ?? state.availability_reason?.observed_aggregate?.eligible_segment_count
    ?? null;
  const interval = result?.aggregate_uncertainty.interval_bpm_per_c;
  const slope = result?.aggregate_uncertainty.estimate_bpm_per_c;
  const isAvailable =
    state.status === 'available'
    && result?.result_state === 'historical_association_only';
  const supportBins = counts?.curve_support_bins ?? [];
  const partialDomain = supportBins.some((bin) => !bin.supported);
  return {
    state,
    hasResponse: true,
    isNotEnrolled: state.status === 'not_enrolled',
    isProcessing: state.status === 'queued' || state.status === 'processing',
    isAvailable,
    predictionDiagnosticsPassed:
      result?.prediction_status === 'passed_research_diagnostics',
    isUnavailable: ['unavailable', 'failed', 'stale'].includes(state.status),
    isStale: state.status === 'stale',
    isFailed: state.status === 'failed',
    reasonMessage: state.availability_reason
      ? (REASON_KEYS[state.availability_reason.code]?.()
        ?? t('This result did not pass the experiment’s release guardrails.'))
      : '',
    supportId: state.availability_reason?.correlation_id ?? '',
    activityCountDisplay: activityCount == null ? '—' : String(activityCount),
    segmentCountDisplay: segmentCount == null ? '—' : String(segmentCount),
    observedRangeDisplay: observed?.length === 2
      ? `${observed[0].toFixed(1)}–${observed[1].toFixed(1)} °C`
      : '—',
    observedDomain: observed,
    displayedDomains: counts?.displayed_wet_bulb_domains_c ?? [],
    slopeDisplay: slope == null
      ? '—'
      : `${slope > 0 ? '+' : ''}${slope.toFixed(2)} bpm/°C`,
    intervalDisplay: interval?.length === 2
      ? `${Number(interval[0]).toFixed(2)}–${Number(interval[1]).toFixed(2)} bpm/°C`
      : '—',
    modelVersionDisplay: result?.model_version ?? state.model_version,
    partialDomain,
    supportBinsDisplay: supportBins.map((bin) => ({
      binIndex: bin.bin_index,
      range: `${bin.lower_wet_bulb_c.toFixed(1)}–${bin.upper_wet_bulb_c.toFixed(1)} °C`,
      activityCount: bin.reference_power_activity_count,
      supported: bin.supported,
    })),
    chartDates: supportBins.length
      ? supportBins.map((bin) => (
        `${((bin.lower_wet_bulb_c + bin.upper_wet_bulb_c) / 2).toFixed(1)}°`
      ))
      : result?.aggregate_curve_points.map((point) => `${point.wet_bulb_c.toFixed(1)}°`) ?? [],
    chartSeries: chartSeries(state),
  };
}

Page({
  data: {
    themeClass: getApp<IAppOption>().globalData.themeClass || themeClassName(),
    chartTheme: resolveTheme(),
    tr: buildLabsTr(),
    loading: true,
    hasResponse: false,
    errorMessage: '',
    state: null as LabsEnvironmentResponseState | null,
    preflight: null as LabsEnvironmentPreflightResponse | null,
    preflightLoading: true,
    preflightBlocked: false,
    preflightUncertain: false,
    preflightTitle: '',
    preflightDetail: '',
    preflightReason: '',
    preflightReadyActivityCount: 0,
    isNotEnrolled: false,
    isProcessing: false,
    isAvailable: false,
    predictionDiagnosticsPassed: false,
    isUnavailable: false,
    isStale: false,
    isFailed: false,
    reasonMessage: '',
    supportId: '',
    activityCountDisplay: '—',
    segmentCountDisplay: '—',
    observedRangeDisplay: '—',
    observedDomain: null as number[] | null,
    displayedDomains: [] as number[][],
    slopeDisplay: '—',
    intervalDisplay: '—',
    modelVersionDisplay: '',
    partialDomain: false,
    supportBinsDisplay: [] as Array<{
      binIndex: number;
      range: string;
      activityCount: number;
      supported: boolean;
    }>,
    chartDates: [] as string[],
    chartSeries: [] as Array<{
      label: string;
      color: string;
      values: (number | null)[];
      dashed?: boolean;
    }>,
    adultAttested: false,
    consentConfirmed: false,
    actionPending: false,
    actionError: '',
    temperatureInput: '25',
    humidityInput: '60',
    calculatorPending: false,
    calculatorResult: null as LabsEnvironmentWetBulbResponse | null,
    calculatorPositionText: '',
  },

  onLoad() {
    this.refetch();
  },

  onShow() {
    applyThemeChrome();
  },

  onHide() {
    const self = this as unknown as { _labsPoll?: number };
    if (self._labsPoll) clearTimeout(self._labsPoll);
  },

  onUnload() {
    const self = this as unknown as { _labsPoll?: number };
    if (self._labsPoll) clearTimeout(self._labsPoll);
  },

  async refetch() {
    const self = this as unknown as { _labsPoll?: number };
    if (self._labsPoll) clearTimeout(self._labsPoll);
    this.setData({ loading: true, errorMessage: '' });
    try {
      const [state, preflight] = await Promise.all([
        apiGet<LabsEnvironmentResponseState>('/api/labs/environment-response'),
        apiGet<LabsEnvironmentPreflightResponse>('/api/labs/environment-response/preflight'),
      ]);
      const preflightBlocked = !preflight.can_start_analysis;
      const preflightUncertain = preflight.status === 'needs_full_analysis';
      this.setData({
        loading: false,
        preflight,
        preflightLoading: false,
        preflightBlocked,
        preflightUncertain,
        preflightTitle: preflightBlocked
          ? this.data.tr.preflightIneligible
          : preflightUncertain
            ? this.data.tr.preflightUncertain
            : this.data.tr.preflightEligible,
        preflightDetail: preflightBlocked
          ? this.data.tr.preflightIneligibleDetail
          : this.data.tr.preflightEligibleDetail,
        preflightReason: preflight.reason_code
          ? (REASON_KEYS[preflight.reason_code]?.()
            ?? t('The quick check found a data requirement that needs attention.'))
          : '',
        preflightReadyActivityCount: Math.min(
          preflight.observed.complete_stryd_activity_count,
          preflight.observed.provider_aligned_cp_activity_count,
        ),
        ...deriveState(state),
      });
      if (state.status === 'queued' || state.status === 'processing') {
        self._labsPoll = setTimeout(() => this.refetch(), 4000) as unknown as number;
      }
    } catch (error) {
      this.setData({ loading: false, errorMessage: errorDetail(error) });
    }
  },

  onRetry() {
    this.refetch();
  },

  onToggleAdult() {
    this.setData({ adultAttested: !this.data.adultAttested });
  },

  onToggleConsent() {
    this.setData({ consentConfirmed: !this.data.consentConfirmed });
  },

  async onJoin() {
    if (
      !this.data.adultAttested
      || !this.data.consentConfirmed
      || this.data.preflightBlocked
    ) return;
    this.setData({ actionPending: true, actionError: '' });
    try {
      await apiPost<LabsEnvironmentResponseState>('/api/labs/environment-response', {
        adult_attested: true,
        consent_version: this.data.state?.consent_version ?? CONSENT_VERSION,
      });
      await this.refetch();
    } catch (error) {
      this.setData({ actionError: errorDetail(error) });
    } finally {
      this.setData({ actionPending: false });
    }
  },

  async onRecompute() {
    if (this.data.preflightBlocked) return;
    this.setData({ actionPending: true, actionError: '' });
    try {
      await apiPost<LabsEnvironmentResponseState>('/api/labs/environment-response/recompute');
      await this.refetch();
    } catch (error) {
      this.setData({ actionError: errorDetail(error) });
    } finally {
      this.setData({ actionPending: false });
    }
  },

  onWithdraw() {
    wx.showModal({
      title: this.data.tr.withdrawTitle,
      content: this.data.tr.withdrawDetail,
      confirmText: this.data.tr.confirmWithdraw,
      cancelText: this.data.tr.keepParticipating,
      confirmColor: '#d93a2c',
      success: (result) => {
        if (result.confirm) this.confirmWithdraw();
      },
    });
  },

  async confirmWithdraw() {
    this.setData({ actionPending: true, actionError: '' });
    try {
      await apiDelete<void>('/api/labs/environment-response');
      this.setData({
        adultAttested: false,
        consentConfirmed: false,
        calculatorResult: null,
        calculatorPositionText: '',
      });
      await this.refetch();
    } catch (error) {
      this.setData({ actionError: errorDetail(error) });
    } finally {
      this.setData({ actionPending: false });
    }
  },

  onTemperatureInput(event: WechatMiniprogram.Input) {
    this.setData({ temperatureInput: event.detail.value });
  },

  onHumidityInput(event: WechatMiniprogram.Input) {
    this.setData({ humidityInput: event.detail.value });
  },

  async onCalculate() {
    const temperature = Number(this.data.temperatureInput);
    const humidity = Number(this.data.humidityInput);
    if (!Number.isFinite(temperature) || !Number.isFinite(humidity)) {
      this.setData({ actionError: t('Enter numeric temperature and humidity values.') });
      return;
    }
    this.setData({ calculatorPending: true, actionError: '' });
    try {
      const result = await apiPost<LabsEnvironmentWetBulbResponse>(
        '/api/labs/environment-response/wet-bulb',
        { temperature_c: temperature, relative_humidity_pct: humidity },
      );
      const domain = this.data.observedDomain;
      const displayedDomains = this.data.displayedDomains;
      let calculatorPositionText = '';
      if (result.wet_bulb_c != null && domain?.length === 2) {
        const insideDisplayedDomain = displayedDomains.some(
          (displayedDomain) => (
            displayedDomain.length === 2
            && result.wet_bulb_c! >= displayedDomain[0]
            && result.wet_bulb_c! <= displayedDomain[1]
          ),
        );
        calculatorPositionText = insideDisplayedDomain
          ? this.data.tr.calculatorInside
          : result.wet_bulb_c < domain[0]
            ? this.data.tr.calculatorBelow
            : result.wet_bulb_c > domain[1]
              ? this.data.tr.calculatorAbove
              : this.data.tr.calculatorUnsupported;
      }
      this.setData({ calculatorResult: result, calculatorPositionText });
    } catch (error) {
      this.setData({ actionError: errorDetail(error) });
    } finally {
      this.setData({ calculatorPending: false });
    }
  },

  onCopyStullSource() {
    wx.setClipboardData({
      data: STULL_SOURCE_URL,
      success: () => {
        wx.showToast({ title: t('URL copied'), icon: 'success', duration: 1500 });
      },
      fail: () => {
        wx.showToast({ title: t('Copy failed'), icon: 'none', duration: 1500 });
      },
    });
  },
});
