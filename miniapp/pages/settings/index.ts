import { setTabBarTheme } from '../../utils/tabbar';
import { apiDelete, apiGet, apiPost, apiPut } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { clearToken } from '../../utils/auth';
import {
  applyThemeChrome,
  getThemePreference,
  setThemePreference,
  themeClassName,
} from '../../utils/theme';
import type { ThemePref } from '../../utils/theme';
import type { IAppOption } from '../../app';
import { getLanguagePreference, setLanguagePreference } from '../../utils/share';
import { t, tFmt } from '../../utils/i18n';
import { copyUrlToClipboard } from '../../utils/markdown';
import { exportAndShareMyData } from '../../utils/data-rights';
import {
  beginManagedPlanRequest,
  formatWorkoutType,
  invalidateManagedPlanRequests,
  isPraxysOwned,
  isLatestManagedPlanRequest,
  managedPlanPreviewUrl,
  managedPlanState,
  managedPlanWindow,
  planTargetSelection,
} from '../../utils/managed-plan';
import type {
  FeedbackKind,
  FeedbackRequest,
  FeedbackResponse,
  PlanAdjustment,
  PlanAdjustmentHistoryResponse,
  PlanCleanupRequest,
  PlanCleanupResponse,
  PlanResponse,
  PlatformName,
  SettingsResponse,
  SettingsUpdate,
} from '../../types/api';
import type { ManagedPlanState } from '../../utils/managed-plan';
import { MINIAPP_BUILD_VERSION } from '../../utils/version';
import { feedbackPublicationConsent } from '../../utils/feedback';

const ADJUSTMENT_SOURCES = {
  plews: 'https://doi.org/10.1007/s00421-012-2354-4',
  kiviniemi: 'https://doi.org/10.1007/s00421-007-0552-2',
} as const;

function deviceTimeZone(): string | null {
  try {
    const value = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return value?.trim() || null;
  } catch {
    return null;
  }
}

function buildSettingsTr() {
  return {
    navTitle: t('Settings'),
    failedToLoad: t('Failed to load'),
    retry: t('Retry'),
    profile: t('Profile'),
    name: t('Name'),
    units: t('Units'),
    trainingBase: t('Training base'),
    connections: t('Connections'),
    manageOnWeb: t('Manage connections from the web app.'),
    noPlatformsHint: t(
      'No platforms connected. Manage supported connections from the web app.',
    ),
    thresholds: t('Thresholds'),
    thresholdsHint: t('Auto-detected from synced fitness data; override on the web.'),
    thresholdsEmpty: t(
      'No thresholds yet. Sync fitness data to auto-detect CP, LTHR, and pace — or enter values manually on the web.',
    ),
    theme: t('Theme'),
    themeAuto: t('Auto'),
    themeDark: t('Dark'),
    themeLight: t('Light'),
    language: t('Language'),
    languageAuto: t('Auto'),
    openOnWeb: t('Open Praxys on web'),
    exportData: t('Export my data'),
    exportingData: t('Exporting data…'),
    exportDataHint: t('Saves a JSON export and opens WeChat share options.'),
    exportDataFailed: t('Could not export data — please try again.'),
    sendFeedback: t('Send feedback'),
    feedbackBug: t('Bug report'),
    feedbackFeature: t('Feature request'),
    feedbackOther: t('General feedback'),
    feedbackPrompt: t('What happened, or what would you like to see?'),
    feedbackPublish: t('Publish a scrubbed text summary to Praxys’s external issue tracker'),
    feedbackPublishHelper: t('Optional. Praxys removes personal details before publication. Screenshots always remain private. You can send feedback without allowing publication.'),
    feedbackCancel: t('Cancel'),
    feedbackSubmit: t('Send feedback'),
    feedbackSubmitting: t('Sending…'),
    feedbackThanks: t('Thanks for the feedback!'),
    feedbackError: t("Couldn't send your feedback. Please try again."),
    feedbackRateLimited: t("You've sent several reports recently — please wait a few minutes before sending more."),
    feedbackAddPhotoTitle: t('Add a screenshot?'),
    feedbackAddPhotoContent: t('A screenshot helps us pinpoint the issue. It stays private.'),
    feedbackAddPhoto: t('Add photo'),
    feedbackSendWithout: t('Send without'),
    feedbackImageTooLarge: t('Image must be under 5 MB.'),
    signOut: t('Log out'),
    deleteAccount: t('Delete my account'),
    deleteAccountHint: t('Permanently remove your account, synced data, plans, settings, and encrypted credentials.'),
    deleteAccountTitle: t('Delete my account?'),
    deleteAccountContent: t('This permanently deletes your Praxys account and training data. Type DELETE to confirm.'),
    deleteAccountConfirm: t('Delete'),
    deleteAccountPlaceholder: t('Type DELETE here'),
    deleteAccountMismatch: t('Type DELETE to confirm.'),
    deleteAccountFailed: t("Couldn't delete your account. Please try again or contact support if it keeps failing."),
    switchAccount: t('Switch Praxys account'),
    switchAccountHint: t(
      'Unbind your WeChat profile from this Praxys account so you can sign in as a different user.',
    ),
    switchAccountFailed: t(
      "Couldn't unlink your account on the server. Try again in a moment, or sign out instead and contact support if it keeps failing.",
    ),
    connected: t('Connected'),
    syncNow: t('Sync now'),
    syncing: t('Syncing…'),
    syncStarted: t('Sync started in the background.'),
    syncFailed: t('Sync request failed. Try again from the web app if it persists.'),
    trainingBaseHint: t(
      'What metric Praxys uses to measure intensity. Power needs a compatible running-power source; Pace works with GPS activity data.',
    ),
    trainingBasePower: t('Power'),
    trainingBaseHr: t('Heart rate'),
    trainingBasePace: t('Pace'),
    planManagement: t('Plan management'),
    active: t('Active'),
    paused: t('Paused'),
    external: t('External'),
    activePlanner: t('Praxys is your active planner.'),
    pausedPlanner: t('Praxys owns the plan; delivery is paused.'),
    externalPlanner: t('Your external planner remains in control.'),
    activePlannerDetail: t(
      'Praxys automatically keeps its workouts in the next 14 days aligned with {targetLabel}.',
    ),
    pausedPlannerDetail: t(
      'The canonical Praxys plan is preserved. Existing target workouts stay in place until you resume or leave.',
    ),
    externalPlannerDetail: t(
      'Praxys can analyze this schedule, but it will not create, replace, or remove target workouts.',
    ),
    ownershipBoundary: t(
      'Praxys only changes workouts it created or you explicitly adopt. Manual workouts and workouts from another coach stay untouched. To avoid overlapping sessions, use one planner at a time.',
    ),
    managedWindow: t('14-day managed window'),
    noPraxysWorkouts: t(
      'No Praxys workouts are scheduled in this window. Future Praxys-created workouts will enter the rolling window automatically.',
    ),
    previewFailed: t('Could not load the managed-window preview.'),
    executionTarget: t('Execution target'),
    connectTarget: t('Choose an available delivery platform'),
    chooseTarget: t('Choose a delivery platform'),
    deliveryNotSupported: t('Workout delivery is not supported.'),
    accountNotEligible: t(
      'Workout delivery is not available for this account.',
    ),
    targetSelectionHint: t(
      'Selecting a target does not enable delivery. You will confirm the managed window next.',
    ),
    pausedTargetSelectionHint: t(
      'Change the target while delivery is paused. The new target takes effect only after you resume.',
    ),
    pauseToChangeTarget: t('Pause delivery to change the target.'),
    connectTargetHint: t(
      'Connect an activity platform from the web app to choose where workouts are delivered.',
    ),
    saveTarget: t('Save target'),
    savingTarget: t('Saving target…'),
    targetChanged: t('Execution target changed. Delivery remains paused.'),
    targetChangeFailed: t('Could not change the execution target'),
    switchCleanupTitle: t('Remove old deliveries before switching?'),
    switchCleanupDetail: t(
      'Praxys found future deliveries on the current target. Remove only Praxys-delivered workouts before switching.',
    ),
    switchCleanupBoundary: t(
      'Manual and other-coach workouts stay untouched. Delivery remains paused throughout.',
    ),
    switchCleanupRemaining: t(
      '{removed} deliveries are clear; {remaining} still need review before the target can change.',
    ),
    removeAndSwitch: t('Remove and switch'),
    reviewAndActivate: t('Review and activate'),
    reviewAndResume: t('Review and resume'),
    pauseDelivery: t('Pause delivery'),
    leaveManagedMode: t('Leave managed mode'),
    removeFutureDeliveries: t('Remove future Praxys deliveries'),
    retryCleanup: t('Retry cleanup'),
    cleanupIncomplete: t('Managed mode is off, but cleanup did not finish.'),
    removed: t('Removed'),
    remaining: t('Remaining'),
    retryPreview: t('Retry'),
    enabling: t('Enabling…'),
    pausing: t('Pausing…'),
    leaving: t('Leaving…'),
    removing: t('Removing…'),
    confirm: t('Confirm'),
    cancel: t('Cancel'),
    adoptTitle: t('Let Praxys manage this plan?'),
    resumeTitle: t('Resume managed delivery?'),
    confirmBoundary: t('Confirm the boundary before Praxys writes to {targetLabel}.'),
    canonicalBoundary: t(
      'Praxys becomes canonical for its own and explicitly adopted workouts.',
    ),
    manualBoundary: t(
      'Manual and other-coach workouts remain external and will not be edited or deleted.',
    ),
    plannerWarning: t(
      'Disable delivery from any other planner first. Two planners can create overlapping sessions.',
    ),
    garminTargetWarning: t(
      'Garmin workout delivery is duration-only. Workouts with power, pace, or heart-rate targets will stay blocked rather than lose their intended intensity.',
    ),
    stalePreview: t(
      'The managed window changed. Review the refreshed preview before enabling delivery.',
    ),
    enableFailed: t('Could not enable managed delivery'),
    pauseFailed: t('Could not pause delivery'),
    leaveTitle: t('Leave managed mode?'),
    keepFuture: t('Keep future workouts'),
    keepFutureDetail: t(
      'Recommended. Delivered workouts stay on the calendar; Praxys simply stops managing them.',
    ),
    removeFutureDetail: t(
      "Only workouts recorded in Praxys's delivery ledger are removed. Manual and other-coach workouts stay untouched.",
    ),
    leaveFailed: t('Could not leave managed mode'),
    cleanupFailed: t('Could not remove future delivered workouts'),
    done: t('Done'),
    automaticGuardrail: t('Automatic recovery guardrail'),
    on: t('On'),
    off: t('Off'),
    adoptBeforeAutomatic: t(
      'Adopt Praxys as your planner before enabling automatic changes. Coaching remains suggestion-only.',
    ),
    automaticEnabledDetail: t(
      "After a sync, Praxys may replace today's single Praxys-generated hard workout with rest only when same-day HRV crosses your personal caution band.",
    ),
    suggestionOnlyDetail: t(
      'Coaching is suggestion-only. Praxys will not change a workout from recovery signals.',
    ),
    reviewAndTurnOn: t('Review and turn on'),
    turnOff: t('Turn off'),
    turningOff: t('Turning off…'),
    whyConservative: t('Why this is conservative'),
    conservativeDetail: t(
      'This guardrail uses individualized HRV guidance and never loads activity intensity. The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions. Prior-day, missing, or inconsistent recovery; a completed activity; multiple Praxys workouts; or an uncertain target calendar keeps the plan unchanged. Load, sleep, and other caution signals remain suggestions.',
    ),
    recentAutomaticChanges: t('Recent automatic changes'),
    applied: t('Applied'),
    restored: t('Restored'),
    changedLater: t('Changed later'),
    currentHrvCaution: t('Current HRV crossed your personal caution band.'),
    restoreWorkout: t('Restore workout'),
    restoring: t('Restoring…'),
    unknownDate: t('Unknown date'),
    workout: t('Workout'),
    rest: t('Rest'),
    automaticConsentTitle: t('Turn on conservative plan changes?'),
    automaticConsentIntro: t(
      'This permission is separate from managed delivery. Review the exact boundary before opting in.',
    ),
    automaticConsentRule: t(
      "Only today's single Praxys-generated hard workout can become rest, and only for same-day individualized HRV below the caution band.",
    ),
    automaticConsentBoundary: t(
      'External, manual, and other-coach workouts are never changed. Uncertain or stale evidence makes no change.',
    ),
    automaticConsentUndo: t(
      'Every change is recorded here and can be restored while that exact workout version is still current.',
    ),
    keepSuggestionOnly: t('Keep suggestion-only'),
    turnOn: t('Turn on'),
    updateAutomaticFailed: t('Could not update automatic plan changes'),
    restoreWorkoutFailed: t('Could not restore the previous workout'),
    adjustmentHistoryFailed: t('Could not load automatic change history.'),
    timeZoneUnavailable: t(
      'Praxys could not determine your time zone. Check your device settings and try again.',
    ),
    evidenceTitle: t('Individualized HRV evidence'),
    evidenceDetail: t(
      'Praxys uses individualized HRV guidance from Plews et al. (2012) and Kiviniemi et al. (2007). The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions.',
    ),
    plewsSource: t('Plews et al. (2012) source'),
    kiviniemiSource: t('Kiviniemi et al. (2007) source'),
  };
}

type LanguagePref = 'auto' | 'en' | 'zh';

const MAX_FEEDBACK_IMAGE_BYTES = 5 * 1024 * 1024; // 5 MB — mirrors the server cap

/**
 * Optionally let the user attach one screenshot to a feedback report (issue
 * #337). Prompts first (opt-in), then picks a single image via wx.chooseMedia,
 * validates its size, and returns the base64 bytes for the JSON submit — the
 * server stores it privately and never publishes the raw image. Resolves null
 * when the user declines, cancels, or the image is too large.
 */
function pickFeedbackScreenshot(tr: ReturnType<typeof buildSettingsTr>): Promise<string | null> {
  return new Promise((resolve) => {
    wx.showModal({
      title: tr.feedbackAddPhotoTitle,
      content: tr.feedbackAddPhotoContent,
      confirmText: tr.feedbackAddPhoto,
      cancelText: tr.feedbackSendWithout,
      success: (res) => {
        if (!res.confirm) {
          resolve(null);
          return;
        }
        wx.chooseMedia({
          count: 1,
          mediaType: ['image'],
          sizeType: ['compressed', 'original'],
          sourceType: ['album', 'camera'],
          success: (media) => {
            const file = media.tempFiles && media.tempFiles[0];
            if (!file) {
              resolve(null);
              return;
            }
            if (file.size > MAX_FEEDBACK_IMAGE_BYTES) {
              wx.showToast({ title: tr.feedbackImageTooLarge, icon: 'none', duration: 2000 });
              resolve(null);
              return;
            }
            try {
              const b64 = wx.getFileSystemManager().readFileSync(file.tempFilePath, 'base64') as string;
              resolve(b64);
            } catch {
              resolve(null);
            }
          },
          fail: () => resolve(null),
        });
      },
      fail: () => resolve(null),
    });
  });
}

const WEB_URL = 'https://www.praxys.run';

// Always iterate the known threshold keys rather than whatever the
// backend returns verbatim. The raw config.thresholds dict includes meta
// fields like `source` that aren't thresholds and would otherwise render
// as bogus rows.
const KNOWN_THRESHOLDS = [
  'cp_watts',
  'lthr_bpm',
  'threshold_pace_sec_km',
  'max_hr_bpm',
  'rest_hr_bpm',
] as const;

function thresholdLabels(): Record<string, string> {
  return {
    cp_watts: t('CP'),
    lthr_bpm: t('LTHR'),
    threshold_pace_sec_km: t('Threshold pace'),
    max_hr_bpm: t('Max HR'),
    rest_hr_bpm: t('Resting HR'),
  };
}

const THRESHOLD_UNIT: Record<string, string> = {
  cp_watts: 'W',
  lthr_bpm: 'bpm',
  threshold_pace_sec_km: 'min/km',
  max_hr_bpm: 'bpm',
  rest_hr_bpm: 'bpm',
};

interface ProfileRow {
  label: string;
  value: string;
}

interface ConnectionRow {
  key: string;
  label: string;
}

interface ThresholdRow {
  key: string;
  label: string;
  display: string;
  hasOrigin: boolean;
  origin: string;
}

interface PlanPreviewRow {
  key: string;
  date: string;
  workoutType: string;
  details: string;
}

interface PlanAdjustmentRow {
  id: string;
  date: string;
  change: string;
  status: string;
  detail: string;
  canUndo: boolean;
}

interface PlanTargetOption {
  key: PlatformName;
  label: string;
  selectable: boolean;
  reason: string;
}

interface ThemeOption {
  key: ThemePref;
  label: string;
  className: string;
}

interface LanguageOption {
  key: LanguagePref;
  label: string;
  className: string;
}

interface SettingsState {
  themeClass: string;
  loading: boolean;
  errorMessage: string;
  hasResponse: boolean;
  theme: ThemePref;
  /** Human-readable label for the active theme, e.g. "Auto" or "Dark". */
  themeLabel: string;
  language: LanguagePref;
  /** Human-readable label for the active language, e.g. "Auto" or "中文". */
  languageLabel: string;

  profileRows: ProfileRow[];
  hasConnections: boolean;
  connectionRows: ConnectionRow[];

  hasThresholds: boolean;
  thresholdRows: ThresholdRow[];

  trainingBase: 'power' | 'hr' | 'pace';
  /** Human-readable label for the active training base, e.g. "Power". */
  trainingBaseLabel: string;

  planManagementState: ManagedPlanState;
  planStateLabel: string;
  planStateTitle: string;
  planStateDetail: string;
  planTargetOptions: PlanTargetOption[];
  configuredPlanTarget: PlatformName | '';
  configuredPlanTargetLabel: string;
  selectedPlanTarget: PlatformName | '';
  selectedPlanTargetLabel: string;
  planTargetChanged: boolean;
  configuredPlanTargetAvailable: boolean;
  configuredPlanTargetReason: string;
  planLoading: boolean;
  planPreviewError: string;
  hasPlanPreview: boolean;
  planWindowLabel: string;
  planPraxysCount: number;
  planExternalCount: number;
  planPreviewRows: PlanPreviewRow[];
  planPreviewMoreCount: number;
  planAction: string;
  planActionError: string;
  planCleanupPartial: boolean;
  planCleanupRemoved: number;
  planCleanupRemaining: number;
  planCleanupTarget: string;
  adjustmentEnabled: boolean;
  adjustmentAction: string;
  adjustmentError: string;
  adjustmentSupported: boolean;
  planAdjustmentRows: PlanAdjustmentRow[];

  webUrl: string;

  // Manual sync trigger UI state.
  syncing: boolean;
  syncMessage: string;
  exportingData: boolean;

  feedbackFormOpen: boolean;
  feedbackKind: FeedbackKind;
  feedbackMessage: string;
  feedbackPublicationConsent: boolean;
  feedbackSubmitting: boolean;
  feedbackError: string;

  appVersion: string;
}

interface TrainingBaseOption {
  key: 'power' | 'hr' | 'pace';
  label: string;
  className: string;
}

function readAppVersion(): string {
  // wx.getAccountInfoSync().miniProgram.version is only populated for
  // release builds. For develop/trial it always returns ''. CI stamps
  // the real CalVer into MINIAPP_BUILD_VERSION before each upload so
  // all three environments can show the full version string.
  try {
    const info = wx.getAccountInfoSync();
    const env = info.miniProgram.envVersion;
    const ver = MINIAPP_BUILD_VERSION || info.miniProgram.version;
    if (env === 'release') return ver ? `Praxys mp ${ver}` : '';
    if (env === 'develop') return ver ? `Praxys mp ${ver} (dev)` : '';
    // trial
    return ver ? `Praxys mp ${ver} (trial)` : '';
  } catch {
    return '';
  }
}

function themeLabelFor(pref: ThemePref): string {
  if (pref === 'dark') return t('Dark');
  if (pref === 'light') return t('Light');
  return t('Auto');
}

function languageLabelFor(pref: LanguagePref): string {
  if (pref === 'en') return 'English';
  if (pref === 'zh') return '中文';
  return t('Auto');
}

function trainingBaseLabelFor(base: string): string {
  if (base === 'power') return t('Power');
  if (base === 'hr') return t('Heart rate');
  return t('Pace');
}

function planStateCopy(
  state: ManagedPlanState,
  targetLabel: string,
): { label: string; title: string; detail: string } {
  const tr = buildSettingsTr();
  if (state === 'active') {
    return {
      label: tr.active,
      title: tr.activePlanner,
      detail: tr.activePlannerDetail.replace('{targetLabel}', targetLabel),
    };
  }
  if (state === 'paused') {
    return {
      label: tr.paused,
      title: tr.pausedPlanner,
      detail: tr.pausedPlannerDetail,
    };
  }
  return {
    label: tr.external,
    title: tr.externalPlanner,
    detail: tr.externalPlannerDetail,
  };
}

function formatPlanDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(
    getApp<IAppOption>().globalData.locale === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
}

function planTargetOptions(response: SettingsResponse): PlanTargetOption[] {
  const tr = buildSettingsTr();
  const options = response.plan_delivery_options
    ?? response.config.connections.map((platform) => ({
      platform,
      selectable: response.platform_capabilities[platform]?.plan === true,
      reason: response.platform_capabilities[platform]?.plan === true
        ? null
        : 'delivery_not_supported' as const,
    }));
  return options.map((option) => ({
    key: option.platform,
    label: formatPlatform(option.platform),
    selectable: option.selectable,
    reason: option.reason === 'account_not_eligible'
      ? tr.accountNotEligible
      : option.reason === 'delivery_not_supported'
        ? tr.deliveryNotSupported
        : '',
  }));
}

const initialData: SettingsState = {
  themeClass: getApp<IAppOption>().globalData.themeClass,
  loading: true,
  errorMessage: '',
  hasResponse: false,
  theme: 'auto',
  themeLabel: t('Auto'),
  language: 'auto',
  languageLabel: t('Auto'),
  profileRows: [],
  hasConnections: false,
  connectionRows: [],
  hasThresholds: false,
  thresholdRows: [],
  trainingBase: 'pace',
  trainingBaseLabel: t('Pace'),
  planManagementState: 'external',
  planStateLabel: t('External'),
  planStateTitle: '',
  planStateDetail: '',
  planTargetOptions: [],
  configuredPlanTarget: '',
  configuredPlanTargetLabel: t('Choose a delivery platform'),
  selectedPlanTarget: '',
  selectedPlanTargetLabel: t('Choose a delivery platform'),
  planTargetChanged: false,
  configuredPlanTargetAvailable: false,
  configuredPlanTargetReason: '',
  planLoading: true,
  planPreviewError: '',
  hasPlanPreview: false,
  planWindowLabel: '',
  planPraxysCount: 0,
  planExternalCount: 0,
  planPreviewRows: [],
  planPreviewMoreCount: 0,
  planAction: '',
  planActionError: '',
  planCleanupPartial: false,
  planCleanupRemoved: 0,
  planCleanupRemaining: 0,
  planCleanupTarget: '',
  adjustmentEnabled: false,
  adjustmentAction: '',
  adjustmentError: '',
  adjustmentSupported: false,
  planAdjustmentRows: [],
  webUrl: WEB_URL,
  syncing: false,
  syncMessage: '',
  exportingData: false,
  feedbackFormOpen: false,
  feedbackKind: 'other',
  feedbackMessage: '',
  feedbackPublicationConsent: false,
  feedbackSubmitting: false,
  feedbackError: '',
  appVersion: '',
};

function buildTrainingBaseOptions(active: string): TrainingBaseOption[] {
  const tr = buildSettingsTr();
  const map: { key: TrainingBaseOption['key']; label: string }[] = [
    { key: 'power', label: tr.trainingBasePower },
    { key: 'hr', label: tr.trainingBaseHr },
    { key: 'pace', label: tr.trainingBasePace },
  ];
  return map.map((m) => ({
    ...m,
    className:
      'settings-theme-option' +
      (m.key === active ? ' settings-theme-option--active' : ''),
  }));
}

function buildThemeOptions(active: ThemePref): ThemeOption[] {
  const themes: ThemePref[] = ['auto', 'dark', 'light'];
  return themes.map((th) => ({
    key: th,
    label: th === 'auto' ? t('Auto') : th === 'dark' ? t('Dark') : t('Light'),
    className:
      active === th
        ? 'settings-theme-opt settings-theme-opt--active'
        : 'settings-theme-opt',
  }));
}

function buildLanguageOptions(active: LanguagePref): LanguageOption[] {
  const langs: LanguagePref[] = ['auto', 'en', 'zh'];
  return langs.map((l) => ({
    key: l,
    // Language names render in their native script regardless of the
    // current UI locale — that's the universal convention so users can
    // identify their preferred tongue.
    label: l === 'auto' ? t('Auto') : l === 'en' ? 'English' : '中文',
    className:
      active === l
        ? 'settings-theme-opt settings-theme-opt--active'
        : 'settings-theme-opt',
  }));
}

function formatPlatform(key: string): string {
  return key.charAt(0).toUpperCase() + key.slice(1);
}

function formatThresholdDisplay(
  key: string,
  value: number | string | null,
  unit: string,
): string {
  if (value == null || value === '') return '—';
  if (unit === 'min/km' && typeof value === 'number') {
    const m = Math.floor(value / 60);
    const s = Math.round(value % 60);
    return `${m}:${String(s).padStart(2, '0')} /km`;
  }
  if (typeof value === 'number') {
    return `${Math.round(value)} ${unit}`.trim();
  }
  return `${value} ${unit}`.trim();
}

function buildSettingsState(response: SettingsResponse): Partial<SettingsState> {
  const { config, effective_thresholds } = response;
  const profileRows: ProfileRow[] = [
    { label: t('Name'), value: config.display_name || '—' },
    { label: t('Units'), value: t(config.unit_system) },
    { label: t('Training base'), value: trainingBaseLabelFor(config.training_base) },
  ];

  const connectionRows: ConnectionRow[] = config.connections.map((c) => ({
    key: c,
    label: formatPlatform(c),
  }));

  const thresholdRows: ThresholdRow[] = KNOWN_THRESHOLDS.map((k) => {
    const fromEffective = effective_thresholds?.[k];
    const rawConfig = config.thresholds?.[k];
    const value =
      fromEffective && fromEffective.value != null
        ? fromEffective.value
        : typeof rawConfig === 'number' || typeof rawConfig === 'string'
          ? rawConfig
          : null;
    const origin = fromEffective?.origin ?? 'none';
    const unit = THRESHOLD_UNIT[k] ?? '';
    return {
      key: k,
      label: thresholdLabels()[k] ?? k,
      display: formatThresholdDisplay(k, value, unit),
      hasOrigin: origin !== 'user' && origin !== 'none',
      origin: tFmt('from {0}', origin),
    };
  });

  const hasThresholds = thresholdRows.some((r) => r.display !== '—');

  const trainingBase = (config.training_base as 'power' | 'hr' | 'pace') ?? 'pace';
  const targets = planTargetOptions(response);
  const configuredTarget = config.plan_management.execution_target;
  const configuredOption = configuredTarget == null
    ? undefined
    : targets.find((target) => target.key === configuredTarget);
  const configuredTargetAvailable =
    configuredOption?.selectable === true;
  const managementState = managedPlanState(config.plan_management);
  const selectedTarget = planTargetSelection<PlatformName>(
    managementState,
    targets,
    null,
    config.preferences.activities ?? null,
    configuredTarget,
  ) ?? '';
  const selectedTargetLabel = selectedTarget
    ? formatPlatform(selectedTarget)
    : t('Choose a delivery platform');
  const stateCopy = planStateCopy(
    managementState,
    configuredTarget ? formatPlatform(configuredTarget) : selectedTargetLabel,
  );
  return {
    loading: false,
    errorMessage: '',
    hasResponse: true,
    profileRows,
    hasConnections: connectionRows.length > 0,
    connectionRows,
    hasThresholds,
    thresholdRows,
    trainingBase,
    trainingBaseLabel: trainingBaseLabelFor(trainingBase),
    planManagementState: managementState,
    planStateLabel: stateCopy.label,
    planStateTitle: stateCopy.title,
    planStateDetail: stateCopy.detail,
    planTargetOptions: targets,
    configuredPlanTarget: configuredTarget ?? '',
    configuredPlanTargetLabel: configuredTarget
      ? formatPlatform(configuredTarget)
      : t('Choose a delivery platform'),
    selectedPlanTarget: selectedTarget,
    selectedPlanTargetLabel: selectedTargetLabel,
    planTargetChanged: false,
    configuredPlanTargetAvailable: configuredTargetAvailable,
    configuredPlanTargetReason: configuredOption?.reason ?? '',
    adjustmentEnabled:
      config.plan_management.adjustment_policy === 'auto_conservative',
  };
}

function adjustmentStatusLabel(adjustment: PlanAdjustment): string {
  if (adjustment.status === 'undone') return t('Restored');
  if (adjustment.status === 'superseded') return t('Changed later');
  return t('Applied');
}

function buildPlanPreviewState(
  response: PlanResponse,
  history: PlanAdjustment[],
): Partial<SettingsState> {
  const praxysWorkouts = response.workouts.filter(isPraxysOwned);
  const externalWorkouts = response.workouts.filter(
    (workout) => !isPraxysOwned(workout),
  );
  const previewRows: PlanPreviewRow[] = praxysWorkouts.slice(0, 4).map((workout) => {
    const details: string[] = [];
    if (workout.duration_min != null) {
      details.push(`${Math.round(workout.duration_min)} min`);
    }
    if (workout.distance_km != null) {
      details.push(`${workout.distance_km} km`);
    }
    return {
      key: workout.canonical_id
        ?? workout.reconciliation?.id
        ?? `${workout.date}-${workout.workout_type}`,
      date: formatPlanDate(workout.date),
      workoutType: t(formatWorkoutType(workout.workout_type)),
      details: details.join(' · '),
    };
  });
  const adjustmentRows: PlanAdjustmentRow[] = history
    .slice(0, 5)
    .map((adjustment) => ({
      id: adjustment.id,
      date: adjustment.workout_date
        ? formatPlanDate(adjustment.workout_date)
        : t('Unknown date'),
      change: `${
        t(formatWorkoutType(adjustment.before.workout_type ?? t('Workout')))
      } \u2192 ${
        t(formatWorkoutType(adjustment.after.workout_type ?? t('Rest')))
      }`,
      status: adjustmentStatusLabel(adjustment),
      detail: t('Current HRV crossed your personal caution band.'),
      canUndo: adjustment.can_undo,
    }));
  return {
    planLoading: false,
    planPreviewError: '',
    hasPlanPreview: true,
    planWindowLabel: `${formatPlanDate(response.window.start)} – ${formatPlanDate(response.window.end)}`,
    planPraxysCount: praxysWorkouts.length,
    planExternalCount: externalWorkouts.length,
    planPreviewRows: previewRows,
    planPreviewMoreCount: Math.max(praxysWorkouts.length - previewRows.length, 0),
    adjustmentSupported: response.adjustments !== undefined,
    planAdjustmentRows: adjustmentRows,
  };
}

Page({
  data: { ...initialData, tr: buildSettingsTr() },

  onLoad() {
    const themePref = getThemePreference();
    const langPref = getLanguagePreference();
    this.setData({
      themeClass: themeClassName(),
      theme: themePref,
      themeLabel: themeLabelFor(themePref),
      language: langPref,
      languageLabel: languageLabelFor(langPref),
      tr: buildSettingsTr(),
      appVersion: readAppVersion(),
    });
    void this.refetch();
  },

  onShow() {
    applyThemeChrome();
    const pageState = this as unknown as Record<string, unknown>;
    if (pageState._hasShownOnce === true) {
      void this.refetch();
    }
    pageState._hasShownOnce = true;
  },

  onUnload() {
    invalidateManagedPlanRequests(this);
  },

  onRetry() {
    void this.refetch();
  },

  async refetch() {
    const requestGeneration = beginManagedPlanRequest(this);
    this.setData(this.data.hasResponse
      ? { errorMessage: '', planLoading: true }
      : { loading: true, errorMessage: '', planLoading: true });
    try {
      const response = await apiGet<SettingsResponse>('/api/settings');
      if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
      this.setData(buildSettingsState(response) as Record<string, unknown>);
      await this.refetchPlan(requestGeneration);
    } catch (e) {
      if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') {
        this.setData({ loading: false, planLoading: false });
        return;
      }
      const detail = err?.detail ?? String(e);
      this.setData({
        loading: false,
        planLoading: false,
        errorMessage: detail,
        hasResponse: false,
      });
    }
  },

  async refetchPlan(existingGeneration?: number) {
    const requestGeneration = existingGeneration
      ?? beginManagedPlanRequest(this);
    const pageState = this as unknown as Record<string, unknown>;
    this.setData({ planLoading: true, planPreviewError: '' });
    try {
      const response = await apiGet<PlanResponse>(managedPlanPreviewUrl());
      if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
      let history = response.adjustments ?? [];
      let adjustmentError = '';
      if (response.adjustments !== undefined) {
        try {
          const adjustmentHistory = await apiGet<PlanAdjustmentHistoryResponse>(
            '/api/plan/adjustments?limit=20', // i18n-allow
          );
          history = adjustmentHistory.items;
        } catch (historyFailure) {
          const apiError = historyFailure as Partial<ApiError>;
          if (apiError.code === 'UNAUTHENTICATED') throw historyFailure;
          adjustmentError = apiError.detail
            ?? (this.data.tr as ReturnType<typeof buildSettingsTr>)
              .adjustmentHistoryFailed;
        }
      }
      if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
      pageState._managedPlanPreview = response;
      this.setData({
        ...buildPlanPreviewState(
          response,
          history,
        ),
        adjustmentError,
      } as Record<string, unknown>);
    } catch (e) {
      if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') {
        this.setData({ planLoading: false });
        return;
      }
      pageState._managedPlanPreview = undefined;
      this.setData({
        planLoading: false,
        planPreviewError: err?.detail ?? String(e),
        hasPlanPreview: false,
        adjustmentSupported: false,
      });
    }
  },

  onPickPlanTarget(event: WechatMiniprogram.TouchEvent) {
    if (
      this.data.planManagementState === 'active'
      || this.data.planAction
      || this.data.planLoading
    ) {
      return;
    }
    const key = String(
      event.currentTarget.dataset.target ?? '',
    ) as PlatformName;
    const target = this.data.planTargetOptions.find(
      (option) => option.key === key && option.selectable,
    );
    if (!target) return;
    this.setData({
      selectedPlanTarget: target.key,
      selectedPlanTargetLabel: target.label,
      planTargetChanged:
        this.data.planManagementState === 'paused'
        && target.key !== this.data.configuredPlanTarget,
      planActionError: '',
    });
  },

  async onSavePlanTarget() {
    if (
      this.data.planManagementState !== 'paused'
      || !this.data.planTargetChanged
      || this.data.planAction
      || this.data.planLoading
    ) {
      return;
    }
    const target = this.data.selectedPlanTarget;
    const option = this.data.planTargetOptions.find(
      (candidate) => candidate.key === target && candidate.selectable,
    );
    if (!target || !option) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    let cleanupRequired = false;
    this.setData({ planAction: 'target', planActionError: '' });
    try {
      await apiPut('/api/settings', {
        plan_management: {
          execution_target: target,
          delivery_enabled: false,
        },
      } satisfies SettingsUpdate);
      await this.refetch();
      wx.showToast({
        title: tr.targetChanged,
        icon: 'success',
        duration: 1800,
      });
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      cleanupRequired = Boolean(
        err?.detail?.includes('Remove future Praxys deliveries from'),
      );
      if (!cleanupRequired) {
        this.setData({
          planActionError: err?.detail ?? tr.targetChangeFailed,
        });
      }
    } finally {
      this.setData({ planAction: '' });
    }
    if (cleanupRequired) this.confirmTargetSwitchCleanup(target);
  },

  confirmTargetSwitchCleanup(target: PlatformName) {
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    const currentTarget = this.data.configuredPlanTargetLabel;
    const nextTarget = formatPlatform(target);
    wx.showModal({
      title: tr.switchCleanupTitle,
      content: [
        tr.switchCleanupDetail,
        `${currentTarget} \u2192 ${nextTarget}`,
        tr.switchCleanupBoundary,
      ].join('\n\n'),
      confirmText: tr.removeAndSwitch,
      cancelText: tr.cancel,
      success: (result) => {
        if (result.confirm) void this.cleanupAndSwitchTarget(target);
      },
    });
  },

  async cleanupAndSwitchTarget(target: PlatformName) {
    if (
      this.data.planManagementState !== 'paused'
      || this.data.planAction
      || this.data.planLoading
    ) {
      return;
    }
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    let partialCleanup: PlanCleanupResponse | null = null;
    this.setData({ planAction: 'cleanup', planActionError: '' });
    try {
      const cleanup = await this.cleanupFuturePlanDeliveries(
        'switch_execution_target',
      );
      if (cleanup.status === 'partial') {
        partialCleanup = cleanup;
        this.setData({
          planActionError: tr.switchCleanupRemaining
            .replace('{removed}', String(cleanup.removed_count))
            .replace('{remaining}', String(cleanup.remaining_count)),
        });
      } else {
        await apiPut('/api/settings', {
          plan_management: {
            execution_target: target,
            delivery_enabled: false,
          },
        } satisfies SettingsUpdate);
        await this.refetch();
        wx.showToast({
          title: tr.targetChanged,
          icon: 'success',
          duration: 1800,
        });
      }
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      this.setData({
        planActionError: err?.detail ?? tr.targetChangeFailed,
      });
    } finally {
      this.setData({ planAction: '' });
    }
    if (partialCleanup) {
      wx.showModal({
        title: tr.cleanupIncomplete,
        content: tr.switchCleanupRemaining
          .replace('{removed}', String(partialCleanup.removed_count))
          .replace('{remaining}', String(partialCleanup.remaining_count)),
        confirmText: tr.retryCleanup,
        cancelText: tr.done,
        success: (result) => {
          if (result.confirm) void this.cleanupAndSwitchTarget(target);
        },
      });
    }
  },

  onReviewManagedPlan() {
    if (this.data.planAction || this.data.planLoading) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    if (this.data.planCleanupPartial) {
      this.setData({ planActionError: tr.cleanupIncomplete });
      return;
    }
    const mode = this.data.planManagementState === 'paused' ? 'resume' : 'adopt';
    const target = mode === 'resume'
      ? this.data.configuredPlanTarget
      : this.data.selectedPlanTarget;
    if (
      !target
      || (mode === 'resume' && !this.data.configuredPlanTargetAvailable)
    ) {
      wx.showToast({ title: tr.connectTarget, icon: 'none', duration: 1800 });
      return;
    }

    const pageState = this as unknown as Record<string, unknown>;
    const preview = pageState._managedPlanPreview as PlanResponse | undefined;
    const expectedWindow = managedPlanWindow();
    if (
      preview == null
      || preview.window.start !== expectedWindow.start
      || preview.window.end !== expectedWindow.end
    ) {
      this.setData({ planActionError: tr.stalePreview });
      void this.refetchPlan();
      return;
    }

    const targetLabel = formatPlatform(target);
    const content = [
      tr.confirmBoundary.replace('{targetLabel}', targetLabel),
      tr.canonicalBoundary,
      `${tr.managedWindow}: ${this.data.planWindowLabel}`,
      tFmt(
        '{0} Praxys · {1} external',
        this.data.planPraxysCount,
        this.data.planExternalCount,
      ),
      tr.manualBoundary,
      tr.plannerWarning,
      ...(target === 'garmin'
        ? [tr.garminTargetWarning]
        : []),
    ].join('\n\n');
    wx.showModal({
      title: mode === 'resume' ? tr.resumeTitle : tr.adoptTitle,
      content,
      confirmText: tr.confirm,
      cancelText: tr.cancel,
      success: (result) => {
        if (result.confirm) {
          void this.enableManagedPlan(mode, target, expectedWindow.start);
        }
      },
    });
  },

  async enableManagedPlan(
    mode: 'adopt' | 'resume',
    target: PlatformName,
    previewStart: string,
  ) {
    if (
      this.data.planAction
      || this.data.planLoading
      || this.data.planCleanupPartial
    ) {
      return;
    }
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    this.setData({ planAction: mode, planActionError: '' });
    const athleteTimezone = deviceTimeZone();
    const update: SettingsUpdate = {
      managed_plan_preview_start: previewStart,
      ...(athleteTimezone
        ? { source_options: { athlete_timezone: athleteTimezone } }
        : {}),
      plan_management: {
        mode: 'praxys',
        execution_target: target,
        delivery_enabled: true,
        ...(mode === 'adopt'
          ? { adjustment_policy: 'suggest_only' as const }
          : {}),
      },
    };
    try {
      await apiPut('/api/settings', update);
      await this.refetch();
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      this.setData({
        planActionError: err?.detail ?? tr.enableFailed,
      });
    } finally {
      this.setData({ planAction: '' });
    }
  },

  async onPauseManagedPlan() {
    if (this.data.planAction || this.data.planLoading) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    this.setData({ planAction: 'pause', planActionError: '' });
    try {
      await apiPut('/api/settings', {
        plan_management: { delivery_enabled: false },
      } satisfies SettingsUpdate);
      await this.refetch();
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      this.setData({ planActionError: err?.detail ?? tr.pauseFailed });
    } finally {
      this.setData({ planAction: '' });
    }
  },

  onReviewAutomaticAdjustment() {
    if (
      !this.data.adjustmentSupported
      || this.data.adjustmentAction
      || this.data.planLoading
    ) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    if (this.data.planManagementState === 'external') {
      wx.showToast({
        title: tr.adoptBeforeAutomatic,
        icon: 'none',
        duration: 2400,
      });
      return;
    }
    if (this.data.adjustmentEnabled) {
      void this.setAutomaticAdjustmentPolicy('suggest_only');
      return;
    }
    wx.showModal({
      title: tr.automaticConsentTitle,
      content: [
        tr.automaticConsentIntro,
        tr.automaticConsentRule,
        tr.automaticConsentBoundary,
        tr.automaticConsentUndo,
      ].join('\n\n'),
      confirmText: tr.turnOn,
      cancelText: tr.cancel,
      success: (result) => {
        if (result.confirm) {
          void this.setAutomaticAdjustmentPolicy('auto_conservative');
        }
      },
    });
  },

  async setAutomaticAdjustmentPolicy(
    policy: 'suggest_only' | 'auto_conservative',
  ) {
    if (!this.data.adjustmentSupported || this.data.adjustmentAction) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    const athleteTimezone = (
      policy === 'auto_conservative' ? deviceTimeZone() : null
    );
    if (policy === 'auto_conservative' && !athleteTimezone) {
      this.setData({ adjustmentError: tr.timeZoneUnavailable });
      return;
    }
    this.setData({
      adjustmentAction: policy === 'auto_conservative' ? 'enable' : 'disable',
      adjustmentError: '',
    });
    try {
      await apiPut('/api/settings', {
        ...(athleteTimezone
          ? { source_options: { athlete_timezone: athleteTimezone } }
          : {}),
        plan_management: { adjustment_policy: policy },
      } satisfies SettingsUpdate);
      await this.refetch();
    } catch (error) {
      const apiError = error as Partial<ApiError>;
      if (apiError.code === 'UNAUTHENTICATED') return;
      this.setData({
        adjustmentError: apiError.detail ?? tr.updateAutomaticFailed,
      });
    } finally {
      this.setData({ adjustmentAction: '' });
    }
  },

  async onUndoPlanAdjustment(event: WechatMiniprogram.TouchEvent) {
    if (!this.data.adjustmentSupported || this.data.adjustmentAction) return;
    const revisionId = String(event.currentTarget.dataset.id ?? '');
    if (!revisionId) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    this.setData({
      adjustmentAction: `undo:${revisionId}`,
      adjustmentError: '',
    });
    try {
      await apiPost(
        `/api/plan/adjustments/${encodeURIComponent(revisionId)}/undo`,
        {},
      );
      await this.refetch();
    } catch (error) {
      const apiError = error as Partial<ApiError>;
      if (apiError.code === 'UNAUTHENTICATED') return;
      if (apiError.status === 409) await this.refetch();
      this.setData({
        adjustmentError: apiError.detail ?? tr.restoreWorkoutFailed,
      });
    } finally {
      this.setData({ adjustmentAction: '' });
    }
  },

  onShowAdjustmentScience() {
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showModal({
      title: tr.evidenceTitle,
      content: tr.evidenceDetail,
      showCancel: false,
      confirmText: tr.done,
    });
  },

  onCopyAdjustmentSource(event: WechatMiniprogram.TouchEvent) {
    const key = String(
      event.currentTarget.dataset.source ?? '',
    ) as keyof typeof ADJUSTMENT_SOURCES;
    const url = ADJUSTMENT_SOURCES[key];
    if (url) copyUrlToClipboard(url);
  },

  onLeaveManagedPlan() {
    if (this.data.planAction || this.data.planLoading) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showActionSheet({
      itemList: [tr.keepFuture, tr.removeFutureDeliveries],
      success: (result) => {
        const removeFuture = result.tapIndex === 1;
        wx.showModal({
          title: tr.leaveTitle,
          content: removeFuture ? tr.removeFutureDetail : tr.keepFutureDetail,
          confirmText: tr.confirm,
          cancelText: tr.cancel,
          success: (confirmation) => {
            if (confirmation.confirm) {
              void this.runLeaveManagedPlan(removeFuture);
            }
          },
        });
      },
    });
  },

  async runLeaveManagedPlan(removeFuture: boolean) {
    if (this.data.planAction) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    let managedModeDisabled = false;
    let cleanupIncomplete = false;
    this.setData({
      planAction: 'leave',
      planActionError: '',
      planCleanupPartial: false,
    });
    try {
      await apiPut('/api/settings', {
        plan_management: {
          mode: 'external',
          delivery_enabled: false,
        },
      } satisfies SettingsUpdate);
      managedModeDisabled = true;
      if (removeFuture) {
        this.setData({ planAction: 'cleanup' });
        const cleanup = await this.cleanupFuturePlanDeliveries();
        cleanupIncomplete = cleanup.status === 'partial';
        this.setData({
          planCleanupPartial: cleanupIncomplete,
          planCleanupRemoved: cleanup.removed_count,
          planCleanupRemaining: cleanup.remaining_count,
          planCleanupTarget: cleanup.target
            ? formatPlatform(cleanup.target)
            : '',
        });
      }
      await this.refetch();
      if (!cleanupIncomplete) {
        wx.showToast({ title: tr.done, icon: 'success', duration: 1400 });
      }
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      if (managedModeDisabled) await this.refetch();
      const detail = err?.detail ?? tr.leaveFailed;
      this.setData({
        planActionError: managedModeDisabled
          ? `${tr.cleanupIncomplete} ${detail}`
          : detail,
      });
    } finally {
      this.setData({ planAction: '' });
    }
  },

  cleanupFuturePlanDeliveries(
    intent: 'leave_managed_mode' | 'switch_execution_target' =
      'leave_managed_mode',
  ): Promise<PlanCleanupResponse> {
    const cleanupRequest: PlanCleanupRequest = { scope: 'future', intent };
    return apiPost<PlanCleanupResponse>(
      '/api/plan/deliveries/cleanup',
      cleanupRequest,
    );
  },

  onRemoveFuturePlanDeliveries() {
    if (this.data.planAction || this.data.planLoading) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showModal({
      title: tr.removeFutureDeliveries,
      content: tr.removeFutureDetail,
      confirmText: tr.confirm,
      cancelText: tr.cancel,
      success: (result) => {
        if (result.confirm) void this.onRetryPlanCleanup();
      },
    });
  },

  async onRetryPlanCleanup() {
    if (
      this.data.planAction
      || this.data.planLoading
      || this.data.planManagementState !== 'external'
    ) {
      return;
    }
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    this.setData({ planAction: 'cleanup', planActionError: '' });
    try {
      const cleanup = await this.cleanupFuturePlanDeliveries();
      this.setData({
        planCleanupPartial: cleanup.status === 'partial',
        planCleanupRemoved: cleanup.removed_count,
        planCleanupRemaining: cleanup.remaining_count,
        planCleanupTarget: cleanup.target
          ? formatPlatform(cleanup.target)
          : '',
      });
      await this.refetchPlan();
      if (cleanup.status === 'complete') {
        wx.showToast({ title: tr.done, icon: 'success', duration: 1400 });
      }
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      this.setData({
        planActionError: `${tr.cleanupIncomplete} ${err?.detail ?? tr.cleanupFailed}`,
      });
    } finally {
      this.setData({ planAction: '' });
    }
  },

  async onPickLanguage() {
    const langKeys: LanguagePref[] = ['auto', 'en', 'zh'];
    wx.showActionSheet({
      itemList: [t('Auto'), 'English', '中文'],
      success: async (res) => {
        const next = langKeys[res.tapIndex];
        if (!next || next === this.data.language) return;
        setLanguagePreference(next);
        // Best-effort backend sync so the web app sees the same language.
        // Awaited (not fire-and-forget) so the reLaunch below doesn't
        // race with an in-flight request that gets cancelled when the
        // page tears down.
        try {
          await apiPut('/api/settings', { language: next });
        } catch (err) {
          // eslint-disable-next-line no-console
          console.warn('[settings] language backend sync failed:', err);
        }
        // Brutal-but-reliable: reLaunch to Me so every tab page
        // (and its custom-tab-bar Component instance) tears down and
        // rebuilds fresh in the new locale. The previous in-place
        // approach relied on each tab's `pageLifetimes.show` drift
        // check firing reliably across all five custom-tab-bar
        // instances, which Skyline doesn't always honor — labels
        // could stay stale on tabs the user hadn't visited since
        // the language change. The reLaunch approach mirrors what
        // the Login page does on locale switch and guarantees
        // every surface reads the new preference on first paint.
        wx.reLaunch({ url: '/pages/me/index' });
      },
    });
  },

  onPickTheme() {
    const themeKeys: ThemePref[] = ['auto', 'light', 'dark'];
    wx.showActionSheet({
      itemList: [t('Auto'), t('Light'), t('Dark')],
      success: (res) => {
        const next = themeKeys[res.tapIndex];
        if (!next || next === this.data.theme) return;
        setThemePreference(next);

        const newThemeClass = themeClassName();
        const newChartTheme: 'light' | 'dark' = newThemeClass === 'theme-light' ? 'light' : 'dark';

        // Update globalData — newly mounted pages read from here.
        getApp<IAppOption>().globalData.themeClass = newThemeClass;

        // Skyline: live-update all mounted pages without reLaunch.
        // No flash in Skyline (glass-easel renders the new theme
        // immediately without the WebView intermediate-frame artifact).
        const pages = getCurrentPages();
        for (const page of pages) {
          (page as WechatMiniprogram.Page.Instance<Record<string, unknown>, Record<string, unknown>>)
            .setData({ themeClass: newThemeClass, chartTheme: newChartTheme });
        }

        // Update the custom tab bar — it lives outside getCurrentPages()
        // so it needs a direct call via the Skyline-safe shim.
        setTabBarTheme(this, newThemeClass);

        applyThemeChrome();

        this.setData({
          theme: next,
          themeLabel: themeLabelFor(next),
          themeClass: newThemeClass,
        });
      },
    });
  },

  onBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/me/index' });
  },

  onCopyUrl() {
    wx.setClipboardData({ data: WEB_URL });
    wx.showToast({ title: t('URL copied'), icon: 'success', duration: 1500 });
  },

  async onExportData() {
    if (this.data.exportingData) return;
    this.setData({ exportingData: true });
    try {
      await exportAndShareMyData();
    } catch {
      wx.showToast({
        title: this.data.tr.exportDataFailed,
        icon: 'none',
        duration: 2000,
      });
    } finally {
      this.setData({ exportingData: false });
    }
  },

  /** Open the real Miniapp feedback form after category selection. */
  onSendFeedback() {
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    const kinds: FeedbackKind[] = ['bug', 'feature', 'other'];
    wx.showActionSheet({
      itemList: [tr.feedbackBug, tr.feedbackFeature, tr.feedbackOther],
      success: (sheet) => {
        const kind = kinds[sheet.tapIndex];
        if (!kind) return;
        this.setData({
          feedbackFormOpen: true,
          feedbackKind: kind,
          feedbackMessage: '',
          feedbackPublicationConsent: false,
          feedbackSubmitting: false,
          feedbackError: '',
        });
      },
    });
  },

  onFeedbackMessageInput(event: WechatMiniprogram.Input) {
    this.setData({
      feedbackMessage: String(event.detail.value ?? '').slice(0, 5000),
      feedbackError: '',
    });
  },

  onFeedbackPublicationChange(event: WechatMiniprogram.SwitchChange) {
    this.setData({
      feedbackPublicationConsent: event.detail.value,
      feedbackError: '',
    });
  },

  onCancelFeedback() {
    if (this.data.feedbackSubmitting) return;
    this.setData({
      feedbackFormOpen: false,
      feedbackMessage: '',
      feedbackPublicationConsent: false,
      feedbackError: '',
    });
  },

  async onSubmitFeedback() {
    if (this.data.feedbackSubmitting) return;
    const message = this.data.feedbackMessage.trim();
    if (!message) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    this.setData({ feedbackSubmitting: true, feedbackError: '' });
    try {
      const image = await pickFeedbackScreenshot(tr);
      const locale = getLanguagePreference();
      const body: FeedbackRequest = {
        kind: this.data.feedbackKind,
        message,
        context: {
          page: 'settings',
          app_version: MINIAPP_BUILD_VERSION,
          platform: 'wechat-miniapp',
          locale,
        },
        locale,
        images: image ? [image] : undefined,
        ...feedbackPublicationConsent(
          this.data.feedbackPublicationConsent,
        ),
      };
      await apiPost<FeedbackResponse>('/api/feedback', body);
      this.setData({
        feedbackFormOpen: false,
        feedbackMessage: '',
        feedbackPublicationConsent: false,
      });
      wx.showToast({
        title: tr.feedbackThanks,
        icon: 'success',
        duration: 1800,
      });
    } catch (error) {
      const apiError = error as Partial<ApiError>;
      if (apiError.code === 'UNAUTHENTICATED') return;
      this.setData({
        feedbackError: apiError.status === 429
          ? tr.feedbackRateLimited
          : apiError.detail ?? tr.feedbackError,
      });
    } finally {
      this.setData({ feedbackSubmitting: false });
    }
  },

  onDeleteAccount() {
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showModal({
      title: tr.deleteAccountTitle,
      content: tr.deleteAccountContent,
      editable: true,
      placeholderText: tr.deleteAccountPlaceholder,
      confirmText: tr.deleteAccountConfirm,
      cancelText: t('Cancel'),
      success: (res) => {
        if (!res.confirm) return;
        if ((res.content ?? '').trim() !== 'DELETE') {
          wx.showToast({ title: tr.deleteAccountMismatch, icon: 'none', duration: 1800 });
          return;
        }
        void this.runDeleteAccount();
      },
    });
  },

  async runDeleteAccount() {
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showLoading({ title: t('Deleting...'), mask: true });
    try {
      await apiDelete('/api/me');
      clearToken();
      wx.reLaunch({ url: '/pages/login/index' });
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      wx.showModal({
        title: tr.deleteAccountTitle,
        content: err?.detail ? `${tr.deleteAccountFailed}\n\n(${err.detail})` : tr.deleteAccountFailed,
        showCancel: false,
        confirmText: t('OK'),
      });
    } finally {
      wx.hideLoading();
    }
  },
  onSignOut() {
    clearToken();
    wx.reLaunch({ url: '/pages/login/index' });
  },

  /**
   * Persist a new training base via `PUT /api/settings`. The backend
   * recomputes thresholds + zones on the next page load, so we refetch
   * to pick up the cascaded effects (zone label set, threshold display
   * units, etc.). Race condition with another open client is fine —
   * server is the source of truth.
   */
  onPickTrainingBase() {
    const baseKeys: Array<'power' | 'hr' | 'pace'> = ['power', 'hr', 'pace'];
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showActionSheet({
      itemList: [t('Power'), t('Heart rate'), t('Pace')],
      success: async (res) => {
        const next = baseKeys[res.tapIndex];
        if (!next || next === this.data.trainingBase) return;
        const previous = this.data.trainingBase as 'power' | 'hr' | 'pace';
        // Optimistic UI update so the row reflects the choice immediately.
        this.setData({
          trainingBase: next,
          trainingBaseLabel: trainingBaseLabelFor(next),
        });
        try {
          await apiPut('/api/settings', { training_base: next });
          void this.refetch();
        } catch (e2) {
          const err = e2 as Partial<ApiError>;
          if (err?.code === 'UNAUTHENTICATED') return;
          this.setData({
            trainingBase: previous,
            trainingBaseLabel: trainingBaseLabelFor(previous),
            errorMessage: err?.detail ?? tr.failedToLoad,
          });
        }
      },
    });
  },

  /**
   * Kick off a sync against every connected platform (`POST /api/sync`).
   * The backend runs the actual sync in a BackgroundTasks job and the
   * mini program just confirms the request was accepted — refreshing
   * Today / Training afterwards picks up the new data once the job
   * completes. This mirrors the web Sync All button.
   */
  async onSyncAll() {
    if (this.data.syncing) return;
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    this.setData({ syncing: true, syncMessage: '' });
    try {
      await apiPost('/api/sync');
      this.setData({ syncing: false, syncMessage: tr.syncStarted });
      wx.showToast({ title: tr.syncStarted, icon: 'none', duration: 1800 });
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') return;
      this.setData({ syncing: false, syncMessage: err?.detail ?? tr.syncFailed });
    }
  },

  /**
   * Detach the current Praxys account from this WeChat profile so the user
   * can sign in as a different Praxys account, or test the first-run
   * onboarding flow without flashing the database. Calls the unlink
   * endpoint, clears the local JWT, then reLaunches to login — the next
   * `wx.login()` will return `needs_setup` and show the choose / link /
   * register UI.
   */
  onSwitchAccount() {
    wx.showModal({
      title: t('Switch Praxys account'),
      content: t(
        "This unlinks your WeChat profile from the current Praxys account. You'll be signed out and can sign in to a different account on next launch.",
      ),
      confirmText: t('Switch'),
      cancelText: t('Cancel'),
      success: (res) => {
        if (!res.confirm) return;
        void this.runSwitchAccount();
      },
    });
  },

  async runSwitchAccount() {
    const tr = this.data.tr as ReturnType<typeof buildSettingsTr>;
    wx.showLoading({ title: t('Unlinking…'), mask: true });
    let unlinkOk = false;
    let detail = '';
    try {
      await apiPost('/api/auth/wechat/unlink');
      unlinkOk = true;
    } catch (e) {
      const err = e as Partial<ApiError>;
      // 401 means the api-client is already redirecting to login. The
      // session is dead; treat this as success from the user's
      // perspective — they're being signed out anyway.
      if (err?.code === 'UNAUTHENTICATED') return;
      detail = err?.detail ?? String(e);
    } finally {
      wx.hideLoading();
    }

    if (!unlinkOk) {
      // Don't local-logout when the server still has the WeChat binding —
      // doing so leaves the user "signed out locally, bound on server",
      // which is exactly the bug the user reported. Surface a modal
      // explaining the failure and let them decide.
      wx.showModal({
        title: tr.switchAccount,
        content: detail ? `${tr.switchAccountFailed}\n\n(${detail})` : tr.switchAccountFailed,
        showCancel: false,
        confirmText: t('OK'),
      });
      return;
    }

    clearToken();
    wx.reLaunch({ url: '/pages/login/index' });
  },
});
