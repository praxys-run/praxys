import type { IAppOption } from '../../../app';
import { apiDelete, apiGet, apiPost } from '../../../utils/api-client';
import type { ApiError } from '../../../utils/api-client';
import { detectLocale, t } from '../../../utils/i18n';
import {
  applyThemeChrome,
  chartColors,
  resolveTheme,
  themeClassName,
} from '../../../utils/theme';
import type {
  LabsEnvironmentExecution,
  LabsEnvironmentMutationError,
  LabsEnvironmentPreflightResponse,
  LabsEnvironmentResponseState,
  LabsEnvironmentWetBulbResponse,
} from '../../../types/api';

const CONSENT_VERSION = 'environment-response-consent-v1';
const STULL_SOURCE_URL = 'https://doi.org/10.1175/JAMC-D-11-0143.1';
type LabsMutationAction = 'enroll' | 'recompute';

interface LabsPrivateState {
  _labsPoll?: number;
  _labsIdempotencyKeys?: Partial<Record<LabsMutationAction, string>>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isLabsMutationError(
  value: unknown,
): value is LabsEnvironmentMutationError {
  if (!isRecord(value) || typeof value.code !== 'string') return false;
  if (value.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE') {
    return (
      isRecord(value.preflight)
      && typeof value.preflight.can_start_analysis === 'boolean'
      && typeof value.preflight.status === 'string'
    );
  }
  if (value.code === 'consent_version_stale') {
    return typeof value.current_consent_version === 'string';
  }
  if (value.code === 'LABS_ENVIRONMENT_NOT_ENROLLED') {
    return typeof value.message === 'string';
  }
  if (
    value.code === 'LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN'
    || value.code === 'LABS_ENVIRONMENT_RECOMPUTE_DAILY_LIMIT'
  ) {
    return (
      typeof value.message === 'string'
      && typeof value.available_at === 'string'
      && typeof value.retry_after_seconds === 'number'
    );
  }
  return false;
}

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
    cancelWithdraw: t('Cancel and withdraw'),
    availableTitle: t('Historical association; not predictively validated'),
    availableDetail: t('One or more research diagnostics did not support predictive interpretation. Read the curve only as a pattern in eligible past runs.'),
    availablePassedTitle: t('Passed research diagnostics; not a forecast'),
    availablePassedDetail: t('The chronological holdout and sensitivity checks passed, but this personal historical association is still not a clinical claim or future-condition forecast.'),
    curveTitle: t('Your historical environmental-response curve'),
    curveDetail: t('Relative modeled heart rate across your observed wet-bulb-proxy range, holding the fitted comparison at a common recorded-power reference.'),
    curveSeries: t('Relative modeled HR'),
    lowerSeries: t('Lower interval'),
    upperSeries: t('Upper interval'),
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
    retryExhaustedTitle: t('Analysis needs a manual retry'),
    recompute: t('Recompute'),
    recomputeResult: t('Recompute result'),
    retryQueuedTitle: t('Temporary service issue; retry queued'),
    workerRunningTitle: t('Analysis worker is running'),
    queuedTitle: t('Queued for the analysis worker'),
    requestSavedTitle: t('Analysis request saved'),
    retryDetail: t('A temporary infrastructure problem interrupted the previous attempt. Praxys kept the request and will retry automatically.'),
    runningDetail: t('The isolated worker is building the aggregate response from your eligible activity data.'),
    queuedDetail: t('Your request is stored durably and will run separately from the app.'),
    leavePageDetail: t('You can leave this page and return later. No action is needed while the analysis runs.'),
    attempt: t('Attempt'),
    recomputeCoolingDown: t('Recompute cooling down'),
    recomputeAvailableAgain: t('Recompute available again'),
    cooldownDetail: t('The cooldown prevents accidental repeat analysis.'),
    rollingLimitReached: t('Rolling recompute limit reached'),
    rollingLimitDetail: t('The rolling limit protects the shared analysis capacity from repeated requests.'),
    manualRecomputesRemaining: t('manual recomputes remaining'),
    hourRollingWindow: t('hour rolling window'),
    requestFailed: t('Request failed. Try again.'),
    networkError: t('Network error. Try again.'),
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
  analysis_retry_exhausted: () => t('The analysis worker could not complete the model after repeated infrastructure attempts.'),
  analysis_failed: () => t('The analysis did not finish successfully.'),
  provider_alignment_requires_full_analysis: () => t('Your history includes enough broad sample coverage, but the full analysis must confirm that power, heart rate, and Critical Power use one compatible Stryd regime.'),
};

function errorDetail(error: unknown): string {
  const apiError = error as ApiError;
  return apiError?.detail || t('Network error. Try again.');
}

function createIdempotencyKey(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatLocalDateTime(value: string | null | undefined): string {
  if (!value) return '';
  try {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '';
    return parsed.toLocaleString(detectLocale() === 'zh' ? 'zh-CN' : 'en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

function actionErrorDetail(
  error: unknown,
  tr: ReturnType<typeof buildLabsTr>,
): string {
  const apiError = error as ApiError;
  const detail = isLabsMutationError(apiError?.data)
    ? apiError.data
    : null;
  const availableAt = detail && 'available_at' in detail
    ? formatLocalDateTime(detail.available_at)
    : '';
  if (detail?.code === 'LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN') {
    return availableAt
      ? `${tr.recomputeCoolingDown} · ${tr.recomputeAvailableAgain}: ${availableAt}`
      : tr.recomputeCoolingDown;
  }
  if (detail?.code === 'LABS_ENVIRONMENT_RECOMPUTE_DAILY_LIMIT') {
    return availableAt
      ? `${tr.rollingLimitReached} · ${tr.recomputeAvailableAgain}: ${availableAt}`
      : tr.rollingLimitReached;
  }
  if (detail?.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE') {
    return t('The quick check found a data requirement that needs attention.');
  }
  if (detail?.code === 'consent_version_stale') {
    return t('The consent text changed. Review and confirm the current version.');
  }
  if (detail?.code === 'LABS_ENVIRONMENT_NOT_ENROLLED') {
    return t('Not enrolled');
  }
  return apiError?.detail || tr.requestFailed;
}

function executionPresentation(
  execution: LabsEnvironmentExecution,
  tr: ReturnType<typeof buildLabsTr>,
) {
  if (execution.job_status === 'retrying') {
    return {
      title: tr.retryQueuedTitle,
      detail: tr.retryDetail,
      retrying: true,
    };
  }
  if (execution.job_status === 'processing') {
    return {
      title: tr.workerRunningTitle,
      detail: tr.runningDetail,
      retrying: false,
    };
  }
  if (execution.job_status === 'dispatched') {
    return {
      title: tr.queuedTitle,
      detail: tr.queuedDetail,
      retrying: false,
    };
  }
  return {
    title: tr.requestSavedTitle,
    detail: tr.queuedDetail,
    retrying: false,
  };
}

function chartSeries(state: LabsEnvironmentResponseState) {
  const points = state.result?.aggregate_curve_points ?? [];
  const colors = chartColors();
  return [
    {
      label: t('Lower interval'),
      color: colors.tick,
      values: points.map((point) => point.relative_lower_bpm),
      dashed: true,
    },
    {
      label: t('Relative modeled HR'),
      color: colors.reasoning,
      values: points.map((point) => point.relative_hr_bpm),
    },
    {
      label: t('Upper interval'),
      color: colors.tick,
      values: points.map((point) => point.relative_upper_bpm),
      dashed: true,
    },
  ];
}

function deriveState(state: LabsEnvironmentResponseState) {
  const result = state.result;
  const tr = buildLabsTr();
  const execution = executionPresentation(state.execution, tr);
  const recompute = state.execution.recompute;
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
    retryExhausted: state.availability_reason?.code === 'analysis_retry_exhausted',
    processingTitle: execution.title,
    processingDetail: execution.detail,
    processingRetrying: execution.retrying,
    attemptCount: state.execution.attempt_count,
    recomputeAllowed: recompute.allowed,
    recomputeReason: recompute.reason ?? '',
    recomputeAvailableDisplay: formatLocalDateTime(recompute.available_at),
    recomputeRemaining: recompute.remaining_requests,
    recomputeWindowHours: recompute.window_hours,
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
    slopeDisplay: slope == null
      ? '—'
      : `${slope > 0 ? '+' : ''}${slope.toFixed(2)} bpm/°C`,
    intervalDisplay: interval?.length === 2
      ? `${Number(interval[0]).toFixed(2)}–${Number(interval[1]).toFixed(2)} bpm/°C`
      : '—',
    modelVersionDisplay: result?.model_version ?? state.model_version,
    chartDates: result?.aggregate_curve_points.map((point) => `${point.wet_bulb_c.toFixed(1)}°`) ?? [],
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
    retryExhausted: false,
    processingTitle: '',
    processingDetail: '',
    processingRetrying: false,
    attemptCount: 0,
    recomputeAllowed: false,
    recomputeReason: '',
    recomputeAvailableDisplay: '',
    recomputeRemaining: 0,
    recomputeWindowHours: 24,
    reasonMessage: '',
    supportId: '',
    activityCountDisplay: '—',
    segmentCountDisplay: '—',
    observedRangeDisplay: '—',
    observedDomain: null as number[] | null,
    slopeDisplay: '—',
    intervalDisplay: '—',
    modelVersionDisplay: '',
    chartDates: [] as string[],
    chartSeries: [] as Array<{
      label: string;
      color: string;
      values: number[];
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
    if (this.data.hasResponse && !this.data.loading) {
      void this.refetch();
    }
  },

  onHide() {
    const self = this as unknown as LabsPrivateState;
    if (self._labsPoll) clearTimeout(self._labsPoll);
  },

  onUnload() {
    const self = this as unknown as LabsPrivateState;
    if (self._labsPoll) clearTimeout(self._labsPoll);
  },

  async refetch() {
    const self = this as unknown as LabsPrivateState;
    if (self._labsPoll) clearTimeout(self._labsPoll);
    this.setData({ loading: true, errorMessage: '' });
    try {
      const [state, preflight] = await Promise.all([
        apiGet<LabsEnvironmentResponseState>('/api/labs/environment-response'),
        apiGet<LabsEnvironmentPreflightResponse>('/api/labs/environment-response/preflight'),
      ]);
      const previousState = this.data.state;
      const resetConsentControls = (
        (
          previousState != null
          && previousState.status !== 'not_enrolled'
          && state.status === 'not_enrolled'
        )
        || (
          previousState != null
          && previousState.consent_version !== state.consent_version
        )
      );
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
        ...(resetConsentControls
          ? {
              adultAttested: false,
              consentConfirmed: false,
            }
          : {}),
        ...deriveState(state),
      });
      if (
        ['queued', 'dispatched', 'processing', 'retrying'].includes(
          state.execution.job_status ?? '',
        )
      ) {
        self._labsPoll = setTimeout(() => this.refetch(), 4000) as unknown as number;
      } else if (
        !state.execution.recompute.allowed
        && ['cooldown', 'daily_limit'].includes(
          state.execution.recompute.reason ?? '',
        )
        && state.execution.recompute.retry_after_seconds != null
      ) {
        const retryDelayMs = Math.max(
          1000,
          state.execution.recompute.retry_after_seconds * 1000 + 250,
        );
        self._labsPoll = setTimeout(
          () => this.refetch(),
          retryDelayMs,
        ) as unknown as number;
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
    const privateState = this as unknown as LabsPrivateState;
    const keys = privateState._labsIdempotencyKeys ??= {};
    const idempotencyKey = keys.enroll ??= createIdempotencyKey();
    try {
      await apiPost<LabsEnvironmentResponseState>(
        '/api/labs/environment-response',
        {
          adult_attested: true,
          consent_version: this.data.state?.consent_version ?? CONSENT_VERSION,
        },
        { headers: { 'Idempotency-Key': idempotencyKey } },
      );
      delete keys.enroll;
      await this.refetch();
    } catch (error) {
      const status = (error as ApiError)?.status;
      if (status > 0 && status < 500) {
        delete keys.enroll;
      }
      this.setData({ actionError: actionErrorDetail(error, this.data.tr) });
      if (
        status === 409
        && (
          (error as ApiError)?.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE'
          || (error as ApiError)?.code === 'consent_version_stale'
          || (error as ApiError)?.code === 'LABS_ENVIRONMENT_NOT_ENROLLED'
        )
      ) {
        if (
          (error as ApiError)?.code === 'consent_version_stale'
          || (error as ApiError)?.code === 'LABS_ENVIRONMENT_NOT_ENROLLED'
        ) {
          this.setData({
            adultAttested: false,
            consentConfirmed: false,
          });
        }
        await this.refetch();
      }
    } finally {
      this.setData({ actionPending: false });
    }
  },

  async onRecompute() {
    if (this.data.preflightBlocked || !this.data.recomputeAllowed) return;
    this.setData({ actionPending: true, actionError: '' });
    const privateState = this as unknown as LabsPrivateState;
    const keys = privateState._labsIdempotencyKeys ??= {};
    const idempotencyKey = keys.recompute ??= createIdempotencyKey();
    try {
      await apiPost<LabsEnvironmentResponseState>(
        '/api/labs/environment-response/recompute',
        undefined,
        { headers: { 'Idempotency-Key': idempotencyKey } },
      );
      delete keys.recompute;
      await this.refetch();
    } catch (error) {
      const status = (error as ApiError)?.status;
      if (status > 0 && status < 500) {
        delete keys.recompute;
      }
      this.setData({ actionError: actionErrorDetail(error, this.data.tr) });
      if (status === 429) {
        await this.refetch();
      } else if (
        status === 409
        && (
          (error as ApiError)?.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE'
          || (error as ApiError)?.code === 'consent_version_stale'
          || (error as ApiError)?.code === 'LABS_ENVIRONMENT_NOT_ENROLLED'
        )
      ) {
        if ((error as ApiError)?.code === 'LABS_ENVIRONMENT_NOT_ENROLLED') {
          this.setData({
            adultAttested: false,
            consentConfirmed: false,
          });
        }
        await this.refetch();
      }
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
      let calculatorPositionText = '';
      if (result.wet_bulb_c != null && domain?.length === 2) {
        calculatorPositionText = result.wet_bulb_c < domain[0]
          ? this.data.tr.calculatorBelow
          : result.wet_bulb_c > domain[1]
            ? this.data.tr.calculatorAbove
            : this.data.tr.calculatorInside;
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
