import { setTabBarSelected } from '../../utils/tabbar';
import type { IAppOption } from '../../app';
import { apiGet, apiPost, apiPut } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import type {
  GoalResponse,
  GoalPlanImpact,
  GoalPlanKeepResponse,
  AiInsight,
  AiInsightFinding,
  InsightFeedbackVote,
  PlanGenerationCapabilitiesResponse,
  PlanGenerationPurposeSelection,
  PlanIntent,
  PlanRoutingOption,
  SettingsUpdateResponse,
} from '../../types/api';
import { formatTime, formatPace } from '../../utils/format';
import { applyThemeChrome, themeClassName } from '../../utils/theme';
import {
  buildShareMessage,
  buildTimelineMessage,
  detectShareLocale,
  getShareMessage,
} from '../../utils/share';
import { copyUrlToClipboard } from '../../utils/markdown';
import { t, tFmt } from '../../utils/i18n';
import { coachToggleLabel, fetchInsight, insightFeedbackState, localizedInsight } from '../../utils/insights';

// ---- Editor distance choices (unchanged) ----
type DistanceKey = '5k' | '10k' | 'half' | 'marathon' | '50k' | '50mi' | '100k' | '100mi';

interface DistanceChoice {
  key: DistanceKey;
  label: string;
  placeholder: string;
}

// ---- Coach receipt types (mirrors today page local types) ----
interface CoachFindingRow {
  id: string;
  marker: string;
  tone: AiInsightFinding['type'];
  text: string;
}

interface CoachRecRow {
  index: string;
  text: string;
}

interface CoachReceipt {
  stamp: string;
  headline: string;
  hasFindings: boolean;
  findings: CoachFindingRow[];
  hasRecommendations: boolean;
  recommendations: CoachRecRow[];
}

interface CoachTranslations {
  mark: string;
  aria: string;
  findings: string;
  recommendations: string;
}

// ---- Strip cell ----
interface StripCell {
  id: string;
  label: string;
  value: string;
  sub: string;
  accent: string;
}

// ---- Series payload for CP trend chart ----
interface SeriesPayload {
  label: string;
  color: string;
  values: (number | null)[];
  fill?: boolean;
}

// ---- Editor snapshot ----
interface EditorSnapshot {
  type: 'race' | 'continuous' | 'performance_5k' | 'performance_10k';
  distanceIndex: number;
  raceDate: string;
  targetTimeSec: number;
}

// ---- Science-note URL constants ----
const SCIENCE_POWER_URL = 'https://help.stryd.com/en/articles/6879547-race-power-calculator';
const SCIENCE_PACE_URL =
  'https://runningwritings.com/2024/01/critical-speed-guide-for-runners.html';
const SCIENCE_ULTRA_URL =
  'https://runningwritings.com/2024/01/critical-speed-guide-for-runners.html';
const ULTRA_DISTANCES = new Set(['50k', '50mi', '100k', '100mi']);

// ---- Translations ----

function buildGoalTr() {
  const locale = (getApp<IAppOption>().globalData.locale ?? 'en') as 'en' | 'zh';
  const zh = locale === 'zh';
  return {
    navTitle: t('Goal'),
    failedToLoad: t('Failed to load'),
    howCalculated: t('How this is calculated'),
    ultraCaveat: t('Ultra distance caveat'),
    sourceTapCopy: t('Source — tap to copy URL'),
    discussionTapCopy: t('Discussion — tap to copy URL'),
    cpTrend: t('CP trend'),
    realisticTargets: t('Realistic alternative targets'),
    comfortable: t('Comfortable'),
    stretch: t('Stretch'),
    changeGoal: t('Change Goal'),
    editorTitle: t('Set Your Goal'),
    goalType: t('Goal type'),
    raceGoal: t('Race Goal'),
    raceGoalDesc: t('Train toward a specific race date'),
    continuousGoal: t('Continuous'),
    continuousGoalDesc: t('Build fitness over time'),
    performanceGoal: zh ? '5 公里表现' : '5K performance',
    performanceGoalDesc: zh ? '先用历史基线，再决定是否需要可选试点测试' : 'Use history first, then decide whether the optional pilot test is needed',
    performance10kGoal: zh ? '10 公里表现' : '10K performance',
    performance10kGoalDesc: zh ? '先用直接 10 公里历史，再决定是否需要可选基准日期' : 'Use direct 10K history first, then decide whether to choose an optional benchmark date',
    distance: t('Distance'),
    raceDate: t('Race Date'),
    pickDate: t('Pick a date'),
    targetTime: t('Target Time'),
    optional: t('optional'),
    cancel: t('Cancel'),
    save: t('Save Goal'),
    saving: t('Saving…'),
    raceDateRequired: t('Race date is required'),
    failedToSave: t('Failed to save goal'),
    targetTimeHint: t('0:00:00 = no target time'),
    discardConfirm: t('Discard'),
    keepEditing: t('Keep editing'),
    discardPrompt: t('Discard changes?'),
    planStartTitle: t('Start a training plan'),
    planIntentQuestion: t('What should this plan help you do?'),
    planIntentDetail: t('Choose explicitly. Praxys combines that intent with the current distance, active policies, and available evidence.'),
    finishDistance: t('Finish this distance'),
    finishDistanceDetail: t('Prepare to complete the selected distance.'),
    improvePerformance: t('Improve performance'),
    improvePerformanceDetail: t('Use current evidence to work toward a faster result.'),
    rebuildConsistency: t('Rebuild consistency'),
    rebuildConsistencyDetail: t('Return to regular training without guessing what missing records mean.'),
    planCandidate: t('Plan candidate'),
    planCandidateDescription: t('An active policy matches this intent and distance.'),
    planCandidateCurrentDetail: t('This candidate uses the intent already stated by your current Goal. Scope and safety still need confirmation before Praxys creates a proposal.'),
    planCandidateSeparateDetail: t('This candidate uses a separate plan purpose and does not change your current Goal. Scope and safety still need confirmation before Praxys creates a proposal.'),
    readinessFirst: t('Readiness first'),
    readinessDescription: t('An active policy matches, but current evidence is not sufficient or fresh enough for a proposal.'),
    readinessCurrentDetail: t('Review the existing history-first readiness path before asking Praxys to create a proposal.'),
    readinessSeparateDetail: t('Open the readiness path for this separate plan purpose. Your current Goal remains unchanged.'),
    policyUnavailable: t('Policy unavailable'),
    policyUnavailableDescription: t('No active automatic policy matches this intent and distance yet.'),
    policyUnavailableDetail: t('Keep the Goal, choose another intent, or manage workouts manually. Praxys will not borrow a policy from another distance or population.'),
    chooseIntent: t('Choose intent'),
    chooseIntentDescription: t('Goal distance alone does not tell Praxys which outcome matters.'),
    chooseIntentDetail: t('Choose whether this plan should support completion, performance, or a return to consistency. You can correct the choice at any time.'),
    planStartLoadFailed: t('Could not load the accepted plan-generation policies.'),
    planStartLoadFailedDetail: t('Retry the policy check before choosing a route. Praxys will not infer availability from the current Goal alone.'),
    planStartUpdateRequired: t('Update required'),
    planStartUpdateRequiredDescription: t('This plan route uses an accepted policy that this client does not recognize yet.'),
    planStartUpdateRequiredDetail: t('Update the client before opening a preview. Praxys will not guess how to collect or submit policy inputs.'),
    policyCheckFailed: t('Policy check failed'),
    openPlanPreview: t('Open plan preview'),
    reviewReadiness: t('Review readiness'),
    manageWorkouts: t('Manage workouts'),
    retryPolicyCheck: t('Retry policy check'),
    whyRoutesSeparate: t('Why these routes stay separate'),
    hideRouteReasoning: t('Hide routing explanation'),
    routeScienceDetail: t('First completion, performance improvement, and return to consistency use different evidence boundaries. Praxys does not treat missing records as proof of detraining or use one universal beginner or restart schedule.'),
    goalPlanTitle: t('Your Goal changed. Should your plan change too?'),
    goalPlanDraftDescription: t('The open proposal was built for your previous Goal and can no longer be adopted. Review a fresh proposal now or decide later.'),
    goalPlanSuccessorDescription: t('Your current plan was built for your previous Goal. Review a successor proposal, keep this plan as an independent plan, or decide later.'),
    goalPlanUnsupportedDescription: t('There is no approved automatic plan policy for this Goal yet. Praxys will not repurpose another policy. Keep the current plan independent, manage workouts manually, or decide later.'),
    goalPlanContinuity: t('Until you adopt a replacement, your current workouts and delivery continue unchanged.'),
    planDecisionNotSaved: t('Plan decision not saved'),
    decideLater: t('Decide later'),
    keepCurrentPlan: t('Keep current plan'),
    keepingPlan: t('Keeping plan…'),
    reviewAndUpdatePlan: t('Review and update plan'),
    managePlan: t('Manage plan'),
    keepPlanFailed: t('Could not keep the current plan. Reload and try again.'),
    unexpectedPlanState: t('The plan decision returned an unexpected state. Reload and try again.'),
  };
}

interface PlanRoutePresentation {
  state: GoalState['planCapabilityState'];
  description: string;
  detail: string;
  badge: string;
}

function buildPlanRoutePresentation(
  route: PlanRoutingOption | PlanGenerationCapabilitiesResponse['routing'] | null,
  supportedCapabilityIds: string[],
  tr: ReturnType<typeof buildGoalTr>,
): PlanRoutePresentation {
  if (
    route?.capability_id
    && !supportedCapabilityIds.includes(route.capability_id)
  ) {
    return {
      state: 'update_required',
      description: tr.planStartUpdateRequiredDescription,
      detail: tr.planStartUpdateRequiredDetail,
      badge: tr.planStartUpdateRequired,
    };
  }
  switch (route?.state) {
    case 'plan_candidate':
      return {
        state: 'plan_candidate',
        description: tr.planCandidateDescription,
        detail: route.purpose_source === 'capability'
          ? tr.planCandidateSeparateDetail
          : tr.planCandidateCurrentDetail,
        badge: tr.planCandidate,
      };
    case 'readiness_only':
      return {
        state: 'readiness_only',
        description: tr.readinessDescription,
        detail: route.purpose_source === 'capability'
          ? tr.readinessSeparateDetail
          : tr.readinessCurrentDetail,
        badge: tr.readinessFirst,
      };
    case 'policy_unavailable':
      return {
        state: 'policy_unavailable',
        description: tr.policyUnavailableDescription,
        detail: tr.policyUnavailableDetail,
        badge: tr.policyUnavailable,
      };
    case 'clarification_required':
    default:
      return {
        state: 'clarification_required',
        description: tr.chooseIntentDescription,
        detail: tr.chooseIntentDetail,
        badge: tr.chooseIntent,
      };
  }
}

function goalPlanImpactKey(impact: GoalPlanImpact): string {
  return [
    impact.plan_goal_snapshot_id,
    impact.current_goal_revision,
  ].join(':');
}

function buildCoachTr(): CoachTranslations {
  return {
    mark: 'PRAXYS COACH',
    aria: t('Praxys Coach insight'),
    findings: t('Findings'),
    recommendations: t('Recommendations'),
  };
}

// ---- GoalState ----

interface GoalState {
  themeClass: string;
  chartTheme: 'light' | 'dark';
  loading: boolean;
  errorMessage: string;
  hasResponse: boolean;
  refreshing: boolean;

  goalEyebrow: string;
  goalHeadline: string;
  showStatusBadge: boolean;
  statusText: string;
  statusAccent: string;
  stripCells: StripCell[];
  showRealisticTargets: boolean;
  rdComfortable: string;
  rdStretch: string;
  hasRationale: boolean;
  rationaleText: string;

  hasCoach: boolean;
  aiUnavailable: boolean;
  aiUnavailableText: string;
  coach: CoachReceipt | null;
  coachTr: CoachTranslations | null;
  /** Findings + recommendations are progressively disclosed; default
   *  collapsed so the receipt reads as headline-first. Mirrors web's
   *  AiInsightsCard. */
  detailsOpen: boolean;
  /** Pre-computed toggle button label — `{N} findings · {M} recs` when
   *  collapsed, "Hide details" when expanded. Empty string hides the
   *  toggle entirely (zero findings + zero recs). */
  coachToggleLabel: string;
  coachDatasetHash: string;
  coachFeedbackVote: InsightFeedbackVote | '';

  hasCpTrend: boolean;
  cpTrendDates: string[];
  cpTrendSeries: SeriesPayload[];
  cpTrendReferenceY: number | null;
  cpTrendUnit: string;

  notePredictionText: string;
  notePredictionUrl: string;
  notePredictionExpanded: boolean;
  hasUltraNote: boolean;
  noteUltraText: string;
  noteUltraUrl: string;
  noteUltraExpanded: boolean;

  editorOpen: boolean;
  goalKind: GoalResponse['goal_kind'] | '';
  goal: GoalResponse['goal'] | null;
  baseline: GoalResponse['baseline'] | null;
  planCapabilityState:
    | 'loading'
    | 'plan_candidate'
    | 'readiness_only'
    | 'clarification_required'
    | 'policy_unavailable'
    | 'error'
    | 'update_required';
  planCapabilityDescription: string;
  planCapabilityDetail: string;
  planCapabilityBadge: string;
  planIntent: PlanIntent | '';
  planCurrentGoalId: string;
  planCurrentGoalRevision: string;
  planRoutingOptions: PlanRoutingOption[];
  planSupportedCapabilityIds: string[];
  planRoutingReasoningOpen: boolean;
  planRoutingScrollTarget: string;
  goalPlanImpact: GoalPlanImpact | null;
  goalPlanDecisionBusy: boolean;
  goalPlanDecisionError: string;
  performance10kEnabled: boolean;

  editorType: 'race' | 'continuous' | 'performance_5k' | 'performance_10k';
  editorDistanceLabels: string[];
  editorDistanceIndex: number;
  editorRaceDate: string;
  editorTodayIso: string;
  editorTimeRange: string[][];
  editorTimeParts: number[];
  editorTargetDisplay: string;
  editorError: string;
  editorSaving: boolean;
  editorDirty: boolean;
  editorConfirmDiscard: boolean;
}

// ---- Distance helpers ----

function buildDistanceChoices(): DistanceChoice[] {
  return [
    { key: '5k', label: t('5K'), placeholder: 'e.g. 20:00' },
    { key: '10k', label: t('10K'), placeholder: 'e.g. 42:00' },
    { key: 'half', label: t('Half'), placeholder: 'e.g. 1:30:00' },
    { key: 'marathon', label: t('Marathon'), placeholder: 'e.g. 3:00:00' },
    { key: '50k', label: t('50K'), placeholder: 'e.g. 4:30:00' },
    { key: '50mi', label: t('50 Mi'), placeholder: 'e.g. 8:00:00' },
    { key: '100k', label: t('100K'), placeholder: 'e.g. 12:00:00' },
    { key: '100mi', label: t('100 Mi'), placeholder: 'e.g. 24:00:00' },
  ];
}

function todayIso(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

function buildTimeRange(): string[][] {
  const hours = Array.from({ length: 48 }, (_, i) => `${i}h`);
  const minutes = Array.from({ length: 60 }, (_, i) => `${String(i).padStart(2, '0')}m`);
  const seconds = Array.from({ length: 60 }, (_, i) => `${String(i).padStart(2, '0')}s`);
  return [hours, minutes, seconds];
}

function secondsToTimeParts(sec: number | null | undefined): [number, number, number] {
  if (!sec || sec <= 0) return [0, 0, 0];
  const h = Math.min(47, Math.floor(sec / 3600));
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return [h, m, s];
}

function timePartsToSeconds(parts: number[]): number {
  const [h = 0, m = 0, s = 0] = parts;
  return h * 3600 + m * 60 + s;
}

function timePartsToDisplay(parts: number[]): string {
  const [h = 0, m = 0, s = 0] = parts;
  if (h === 0 && m === 0 && s === 0) return '—';
  return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// ---- Formatting / severity ----

function formatThreshold(value: number, unit: string): string {
  if (unit === '/km') return formatPace(value);
  return `${Math.round(value)}`;
}

function severityAccent(severity: string): string {
  switch (severity) {
    case 'on_track': return 'ts-primary';
    case 'close': return 'ts-warning';
    case 'behind':
    case 'unlikely': return 'ts-destructive';
    default: return '';
  }
}

function statusBadgeText(status: string): string {
  return t(status).toUpperCase();
}

// ---- Science note helpers ----

const defaultPowerNote = () =>
  t('Predicted using Stryd race power model (5K at 103.8% CP, marathon at 89.9% CP).');
const defaultPaceNote = () =>
  t("Predicted using Riegel's formula (T₂ = T₁ × (D₂/D₁)^1.06), treating threshold pace as ~10K effort.");
const ultraNoteText = () =>
  t(
    "Ultra distance power fractions (50K+) are estimates with limited research backing. " +
      "Riegel's exponent is validated only up to marathon distance. Predictions beyond marathon " +
      'carry significantly higher uncertainty due to factors like fueling, terrain, heat, and pacing ' +
      'strategy that dominate ultra performance but are not captured by power/pace models.',
  );

interface PredictionNote { text: string; url: string; }

function predictionNote(response: GoalResponse): PredictionNote {
  const pred = response.science_notes?.prediction;
  if (pred?.description) {
    const url = pred.citations?.[0]?.url;
    return {
      text: pred.description,
      url: url || (response.training_base === 'power' ? SCIENCE_POWER_URL : SCIENCE_PACE_URL),
    };
  }
  if (response.training_base === 'power') {
    return { text: defaultPowerNote(), url: SCIENCE_POWER_URL };
  }
  return { text: defaultPaceNote(), url: SCIENCE_PACE_URL };
}

// ---- Coach receipt builder ----

function timeAgo(isoDate: string, locale: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  if (Number.isNaN(diffMs)) return '';
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return locale === 'zh' ? `${diffMin}分钟前` : `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return locale === 'zh' ? `${diffH}小时前` : `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  return locale === 'zh' ? `${diffD}天前` : `${diffD}d ago`;
}

function buildCoachReceipt(insight: AiInsight, locale: 'en' | 'zh'): CoachReceipt {
  const view = localizedInsight(insight, locale);
  const findings: CoachFindingRow[] = view.findings.map((f, i) => ({
    id: `${i}`,
    marker: f.type === 'positive' ? '[+]' : f.type === 'warning' ? '[!]' : '[·]',
    tone: f.type,
    text: f.text,
  }));
  const recommendations: CoachRecRow[] = view.recommendations.map((r, i) => ({
    index: `${i + 1}`,
    text: r,
  }));
  return {
    stamp: insight.generated_at ? timeAgo(insight.generated_at, locale) : '',
    headline: view.headline,
    hasFindings: findings.length > 0,
    findings,
    hasRecommendations: recommendations.length > 0,
    recommendations,
  };
}

// ---- Eyebrow builder ----

function buildGoalEyebrow(
  rc: GoalResponse['race_countdown'],
  mode: string,
  distLabel: string,
  hasTimeTarget: boolean,
): string {
  const modeLabel =
    mode === 'race_date' ? t('Race') : mode === 'cp_milestone' ? t('Goal') : t('Tracking');

  if (mode === 'race_date') {
    const parts = [modeLabel];
    if (rc.race_date) parts.push(rc.race_date);
    if (hasTimeTarget && rc.target_time_sec) parts.push(formatTime(rc.target_time_sec));
    return parts.join(' · ');
  }
  if (mode === 'cp_milestone') {
    const goalLabel =
      hasTimeTarget && rc.target_time_sec
        ? `${formatTime(rc.target_time_sec)} ${distLabel}`
        : distLabel;
    return `${modeLabel} · ${goalLabel}`;
  }
  return `${modeLabel} · ${distLabel}`;
}

// ---- Headline builder ----

function buildGoalHeadline(
  rc: GoalResponse['race_countdown'],
  mode: string,
  currentCp: number | null,
  targetCp: number | null,
  unit: string,
  abbrev: string,
  isPace: boolean,
  distLabel: string,
): string {
  if (mode === 'race_date') {
    const days = rc.days_left ?? 0;
    const predicted =
      rc.predicted_time_sec != null ? formatTime(rc.predicted_time_sec) : '—';
    const hasTimeTarget = rc.target_time_sec != null && rc.target_time_sec > 0;
    if (hasTimeTarget) {
      return tFmt(
        '{0} days to race day. Today\'s prediction is {1} against a target of {2}.',
        `${days}`, predicted, formatTime(rc.target_time_sec as number),
      );
    }
    return tFmt('{0} days to race day. Today\'s prediction is {1}.', `${days}`, predicted);
  }

  if (mode === 'cp_milestone') {
    const currentStr = currentCp != null ? formatThreshold(currentCp, unit) : '—';
    const targetStr = targetCp != null ? formatThreshold(targetCp, unit) : '—';
    const hasTimeTarget = rc.target_time_sec != null && rc.target_time_sec > 0;
    if (hasTimeTarget) {
      return tFmt(
        'Building toward {0} {1}. Current {2} {3}{4}, need {5}{4}.',
        formatTime(rc.target_time_sec as number), distLabel, abbrev, currentStr, unit, targetStr,
      );
    }
    return tFmt(
      'Building toward {0}. Current {1} {2}{3}, need {4}{3}.',
      distLabel, abbrev, currentStr, unit, targetStr,
    );
  }

  // continuous / none
  const predicted = rc.predicted_time_sec != null ? formatTime(rc.predicted_time_sec) : null;
  const trend = rc.cp_trend_summary;
  const dirLabel = trend
    ? trend.direction === 'rising'
      ? t('Rising').toLowerCase()
      : trend.direction === 'falling'
        ? t('Falling').toLowerCase()
        : t('Flat').toLowerCase()
    : t('Flat').toLowerCase();

  let slopeStr: string | null = null;
  if (trend && trend.slope_per_month !== 0) {
    const sign = trend.slope_per_month > 0 ? '+' : '';
    const formatted = isPace
      ? formatPace(Math.abs(trend.slope_per_month))
      : trend.slope_per_month.toFixed(1);
    slopeStr = `${sign}${formatted}${unit}/mo`;
  }

  if (predicted && slopeStr) {
    return tFmt(
      'Today\'s {0} prediction is {1}. {2} is {3} at {4}.',
      distLabel, predicted, abbrev, dirLabel, slopeStr,
    );
  }
  if (predicted) {
    return tFmt(
      'Today\'s {0} prediction is {1}. {2} is {3}.',
      distLabel, predicted, abbrev, dirLabel,
    );
  }
  return tFmt('{0} is {1}. Add more activities for a race-time prediction.', abbrev, dirLabel);
}

// ---- Strip cells builder ----

function buildStripCells(
  rc: GoalResponse['race_countdown'],
  mode: string,
  currentCp: number | null,
  unit: string,
  abbrev: string,
  isPace: boolean,
  distLabel: string,
): StripCell[] {
  const cells: StripCell[] = [];
  const rCheck = rc.reality_check;
  const targetCp = rc.target_cp ?? null;
  const hasTimeTarget = rc.target_time_sec != null && rc.target_time_sec > 0;

  if (mode === 'race_date') {
    cells.push({
      id: 'days', label: t('Days left'),
      value: rc.days_left != null ? `${rc.days_left}` : '—', sub: '', accent: '',
    });
    cells.push({
      id: 'predicted', label: t('Predicted'),
      value: rc.predicted_time_sec != null ? formatTime(rc.predicted_time_sec) : '—',
      sub: distLabel, accent: '',
    });
    if (hasTimeTarget) {
      cells.push({
        id: 'target', label: t('Target'),
        value: formatTime(rc.target_time_sec as number), sub: distLabel, accent: '',
      });
    }
    cells.push({
      id: 'current_cp', label: `${t('current')} ${abbrev}`,
      value: currentCp != null ? formatThreshold(currentCp, unit) : '—', sub: unit, accent: '',
    });
    if (rCheck.needed_cp != null) {
      cells.push({
        id: 'needed_cp', label: `${t('Needed')} ${abbrev}`,
        value: formatThreshold(rCheck.needed_cp, unit), sub: unit, accent: '',
      });
    }
    if (rCheck.cp_gap_watts != null) {
      cells.push({
        id: 'gap', label: t('Gap'),
        value: `${rCheck.cp_gap_watts > 0 ? '+' : ''}${
          isPace
            ? formatPace(Math.abs(rCheck.cp_gap_watts))
            : Math.round(rCheck.cp_gap_watts)
        }`,
        sub: unit, accent: severityAccent(rCheck.severity),
      });
    }
  } else if (mode === 'cp_milestone') {
    const gap = currentCp != null && targetCp != null ? targetCp - currentCp : null;
    cells.push({
      id: 'gap', label: t('Gap'),
      value: gap != null
        ? `${gap > 0 ? '+' : ''}${formatThreshold(Math.abs(gap), unit)}`
        : '—',
      sub: unit,
      accent: gap == null ? '' : gap > 0 ? 'ts-warning' : 'ts-primary',
    });
    cells.push({
      id: 'predicted', label: t('Predicted'),
      value: rc.predicted_time_sec != null ? formatTime(rc.predicted_time_sec) : '—',
      sub: distLabel, accent: '',
    });
    cells.push({
      id: 'to_target', label: t('To target'),
      value: rc.estimated_months != null ? rc.estimated_months.toFixed(1) : '—',
      sub: rc.estimated_months != null ? t('months') : '',
      accent: '',
    });
  } else {
    // continuous / none
    const trend = rc.cp_trend_summary;
    cells.push({
      id: 'current_cp', label: `${t('current')} ${abbrev}`,
      value: currentCp != null ? formatThreshold(currentCp, unit) : '—', sub: unit, accent: '',
    });
    const dirLabel = trend
      ? trend.direction === 'rising' ? t('Rising')
        : trend.direction === 'falling' ? t('Falling') : t('Flat')
      : t('Flat');
    let slopeSub = '';
    if (trend && trend.slope_per_month !== 0) {
      const sign = trend.slope_per_month > 0 ? '+' : '';
      const formatted = isPace
        ? formatPace(Math.abs(trend.slope_per_month))
        : trend.slope_per_month.toFixed(1);
      slopeSub = `${sign}${formatted}${unit}/mo`;
    }
    cells.push({
      id: 'direction', label: t('Direction'),
      value: dirLabel, sub: slopeSub, accent: severityAccent(rCheck.severity),
    });
    if (rc.predicted_time_sec != null) {
      cells.push({
        id: 'predicted_cont', label: t('Predicted'),
        value: formatTime(rc.predicted_time_sec), sub: distLabel, accent: '',
      });
    }
  }
  return cells;
}

// ---- Full render state builder ----

function buildGoalState(
  response: GoalResponse,
  insight: AiInsight | null,
  aiAvailable: boolean,
  locale: 'en' | 'zh',
  themeClass: string,
): Partial<GoalState> {
  const rc = response.race_countdown;
  const goalKind = response.goal_kind ?? (response.goal?.eligible ? 'performance_5k' : (rc.race_date ? 'race' : 'continuous'));
  const rCheck = rc.reality_check;
  const display = response.display;
  const unit = display?.threshold_unit ?? 'W';
  const abbrev = display?.threshold_abbrev ?? 'CP';
  const isPace = unit === '/km';
  const currentCp = response.latest_cp;
  const targetCp = rc.target_cp ?? null;
  const distLabel = t(rc.distance_label ?? 'Marathon');
  const hasTimeTarget = rc.target_time_sec != null && rc.target_time_sec > 0;
  const mode = rc.mode;

  const trend = response.cp_trend;
  const hasCpTrend = !!trend && trend.values.length >= 2;

  const note = predictionNote(response);
  const isUltra = !!rc.distance && ULTRA_DISTANCES.has(rc.distance);

  let coach: CoachReceipt | null = null;
  try {
    if (insight) coach = buildCoachReceipt(insight, locale);
  } catch (e) {
    console.warn('[goal] coach receipt build failed; suppressing:', e);
  }
  const hasCoach = coach != null;
  const feedbackState = hasCoach
    ? insightFeedbackState(insight)
    : { datasetHash: '', vote: '' as InsightFeedbackVote | '' };
  const coachDatasetHash = feedbackState.datasetHash;
  const coachFeedbackVote = feedbackState.vote;
  // Reset detailsOpen on every refetch — receipt content has changed
  // (different findings/recs from the new race_forecast row), so a
  // prior expanded state would surface a stale-looking detail block.
  const detailsOpen = false;
  const coachLabel = coach
    ? coachToggleLabel(
        coach.findings.length,
        coach.recommendations.length,
        detailsOpen,
      )
    : '';

  const severity = rCheck.severity;
  const showStatusBadge = severity !== 'unknown';

  const goalEyebrow = buildGoalEyebrow(rc, mode, distLabel, hasTimeTarget);
  const goalHeadline = buildGoalHeadline(rc, mode, currentCp, targetCp, unit, abbrev, isPace, distLabel);
  const stripCells = buildStripCells(rc, mode, currentCp, unit, abbrev, isPace, distLabel);

  const showRealisticTargets =
    mode === 'race_date' &&
    !!rCheck.realistic_targets &&
    (severity === 'behind' || severity === 'unlikely');

  return {
    themeClass,
    goalKind,
    goal: response.goal ?? null,
    baseline: response.baseline ?? null,
    loading: false,
    errorMessage: '',
    hasResponse: true,

    goalEyebrow,
    goalHeadline,
    showStatusBadge,
    statusText: statusBadgeText(severity),
    statusAccent: severityAccent(severity),
    stripCells,
    showRealisticTargets,
    rdComfortable: rCheck.realistic_targets
      ? formatTime(rCheck.realistic_targets.comfortable)
      : '',
    rdStretch: rCheck.realistic_targets ? formatTime(rCheck.realistic_targets.stretch) : '',
    hasRationale: !hasCoach && !!rCheck.trend_note,
    rationaleText: rCheck.trend_note ?? '',

    hasCoach,
    aiUnavailable: !aiAvailable,
    aiUnavailableText: t('Azure AI insights are temporarily unavailable. Synced data and deterministic training metrics remain available.'),
    coach,
    coachTr: hasCoach ? buildCoachTr() : null,
    detailsOpen,
    coachToggleLabel: coachLabel,
    coachDatasetHash,
    coachFeedbackVote,

    hasCpTrend,
    cpTrendDates: hasCpTrend ? trend.dates : [],
    cpTrendSeries: hasCpTrend
      ? [{ label: abbrev, color: '#00ff87', values: trend.values, fill: true }]
      : [],
    cpTrendReferenceY: targetCp,
    cpTrendUnit: isPace ? '' : unit,

    notePredictionText: note.text,
    notePredictionUrl: note.url,
    hasUltraNote: isUltra,
    noteUltraText: isUltra ? ultraNoteText() : '',
  };
}

// ---- Initial page data ----

const DISTANCE_CHOICES = buildDistanceChoices();

const initialData: GoalState = {
  themeClass: getApp<IAppOption>().globalData.themeClass,
  chartTheme: 'light',
  loading: true,
  errorMessage: '',
  hasResponse: false,
  refreshing: false,

  goalEyebrow: '',
  goalHeadline: '',
  showStatusBadge: false,
  statusText: '',
  statusAccent: '',
  stripCells: [],
  showRealisticTargets: false,
  rdComfortable: '',
  rdStretch: '',
  hasRationale: false,
  rationaleText: '',

  hasCoach: false,
  aiUnavailable: false,
  aiUnavailableText: '',
  coach: null,
  coachTr: null,
  detailsOpen: false,
  coachToggleLabel: '',
  coachDatasetHash: '',
  coachFeedbackVote: '',

  hasCpTrend: false,
  cpTrendDates: [],
  cpTrendSeries: [],
  cpTrendReferenceY: null,
  cpTrendUnit: '',

  notePredictionText: '',
  notePredictionUrl: '',
  notePredictionExpanded: false,
  hasUltraNote: false,
  noteUltraText: '',
  noteUltraUrl: SCIENCE_ULTRA_URL,
  noteUltraExpanded: false,

  goalKind: '',
  goal: null,
  baseline: null,
  planCapabilityState: 'loading',
  planCapabilityDescription: '',
  planCapabilityDetail: '',
  planCapabilityBadge: '',
  planIntent: '',
  planCurrentGoalId: '',
  planCurrentGoalRevision: '',
  planRoutingOptions: [],
  planSupportedCapabilityIds: [],
  planRoutingReasoningOpen: false,
  planRoutingScrollTarget: '',
  goalPlanImpact: null,
  goalPlanDecisionBusy: false,
  goalPlanDecisionError: '',
  performance10kEnabled: false,

  editorOpen: false,
  editorType: 'race',
  editorDistanceLabels: DISTANCE_CHOICES.map((d) => d.label),
  editorDistanceIndex: 3,
  editorRaceDate: '',
  editorTodayIso: todayIso(),
  editorTimeRange: buildTimeRange(),
  editorTimeParts: [0, 0, 0],
  editorTargetDisplay: '—',
  editorError: '',
  editorSaving: false,
  editorDirty: false,
  editorConfirmDiscard: false,
};

// ---- Page ----

Page({
  data: { ...initialData, tr: buildGoalTr() },

  onLoad() {
    const tc = themeClassName();
    this.setData({ themeClass: tc, chartTheme: tc === 'theme-light' ? 'light' : 'dark', tr: buildGoalTr() });
    const pageState = this as unknown as Record<string, unknown>;
    pageState._locale = getApp<IAppOption>().globalData.locale;
    void this.refetch();
  },

  onShow() {
    const tc = themeClassName();
    if (tc !== this.data.themeClass) {
      this.setData({ themeClass: tc, chartTheme: tc === 'theme-light' ? 'light' : 'dark' });
    }
    const curLocale = getApp<IAppOption>().globalData.locale;
    const pgMut = this as unknown as Record<string, unknown>;
    const returningToTab = pgMut._hasShownOnce === true;
    pgMut._hasShownOnce = true;
    let localeChanged = false;
    if (curLocale !== pgMut._locale) {
      pgMut._locale = curLocale;
      localeChanged = true;
      this.setData({ tr: buildGoalTr() });
    }
    if (returningToTab || localeChanged) {
      void this.refetch();
    }
    applyThemeChrome();
    setTabBarSelected(this, 3);
  },

  onShareAppMessage() {
    const locale = detectShareLocale();
    const eyebrow = (this.data.goalEyebrow as string) || '';
    const headline = (this.data.goalHeadline as string) || '';
    const title = eyebrow && headline ? `${eyebrow} — ${headline}` : headline || eyebrow;
    if (title) return buildShareMessage(title.slice(0, 100), '/pages/goal/index');
    return getShareMessage(locale, '/pages/goal/index');
  },

  onShareTimeline() {
    const locale = detectShareLocale();
    const eyebrow = (this.data.goalEyebrow as string) || '';
    const fallback =
      locale === 'zh' ? '像专业选手一样训练，无论水平高低。' : 'Train like a pro. Whatever your level.';
    return buildTimelineMessage(eyebrow || fallback);
  },
  onOpenPlanManagement() {
    const route = (this.data.planRoutingOptions as PlanRoutingOption[]).find(
      (option) => option.intent === this.data.planIntent,
    ) ?? null;
    const canHandoff = Boolean(
      route
      && (
        route.state === 'plan_candidate'
        || route.state === 'readiness_only'
      )
      && route.capability_id
      && route.purpose_source,
    );
    getApp<IAppOption>().globalData.pendingPlanStartPurpose = canHandoff
      ? {
        capability_id: route?.capability_id ?? '',
        source: route?.purpose_source ?? 'capability',
        expected_goal_id: route?.purpose_source === 'current_goal'
          ? this.data.planCurrentGoalId || null
          : null,
        expected_goal_revision: route?.purpose_source === 'current_goal'
          ? this.data.planCurrentGoalRevision || null
          : null,
      } satisfies PlanGenerationPurposeSelection
      : null;
    wx.switchTab({ url: '/pages/training/index' });
  },

  onReviewGoalPlan() {
    if (this.data.goalPlanDecisionBusy) return;
    const impact = this.data.goalPlanImpact as GoalPlanImpact | null;
    const pageState = this as unknown as Record<string, unknown>;
    pageState._dismissedGoalPlanImpactKey = impact
      ? goalPlanImpactKey(impact)
      : null;
    this.setData({
      goalPlanImpact: null,
      goalPlanDecisionError: '',
    });
    if (impact?.can_generate_successor) {
      getApp<IAppOption>().globalData.pendingPlanStartPurpose = null;
      this.setData({ planRoutingScrollTarget: '' }, () => {
        this.setData({ planRoutingScrollTarget: 'plan-routing' });
      });
      return;
    }
    wx.switchTab({ url: '/pages/training/index' });
  },

  onDeferGoalPlan() {
    if (this.data.goalPlanDecisionBusy) return;
    const impact = this.data.goalPlanImpact as GoalPlanImpact | null;
    const pageState = this as unknown as Record<string, unknown>;
    pageState._dismissedGoalPlanImpactKey = impact
      ? goalPlanImpactKey(impact)
      : null;
    this.setData({
      goalPlanImpact: null,
      goalPlanDecisionError: '',
    });
  },

  async onKeepGoalPlan() {
    const impact = this.data.goalPlanImpact as GoalPlanImpact | null;
    if (
      !impact
      || !impact.can_keep_current_plan
      || this.data.goalPlanDecisionBusy
    ) {
      return;
    }
    const tr = this.data.tr as ReturnType<typeof buildGoalTr>;
    this.setData({
      goalPlanDecisionBusy: true,
      goalPlanDecisionError: '',
    });
    try {
      const result = await apiPost<GoalPlanKeepResponse>(
        `/api/plan/${impact.adaptive_plan_id}/goal-reconciliation/keep-current`,
        {
          expected_goal_revision: impact.current_goal_revision,
          expected_goal_snapshot_id: impact.plan_goal_snapshot_id,
          idempotency_key:
            `goal-plan-keep:${impact.plan_goal_snapshot_id}`,
        },
      );
      if (result.link_status !== 'independent') {
        throw new Error(tr.unexpectedPlanState);
      }
      this.setData({
        goalPlanImpact: null,
        goalPlanDecisionBusy: false,
        goalPlanDecisionError: '',
      });
      void this.refetch();
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') {
        this.setData({ goalPlanDecisionBusy: false });
        return;
      }
      this.setData({
        goalPlanDecisionBusy: false,
        goalPlanDecisionError: e instanceof Error
          ? e.message
          : err?.detail ?? tr.keepPlanFailed,
      });
    }
  },

  onRetryPlanCapability() {
    void this.refetch();
  },

  onSelectPlanIntent(e: WechatMiniprogram.TouchEvent) {
    const intent = String(e.currentTarget.dataset.intent || '') as PlanIntent;
    const route = (this.data.planRoutingOptions as PlanRoutingOption[]).find(
      (option) => option.intent === intent,
    ) ?? null;
    if (!route) return;
    const presentation = buildPlanRoutePresentation(
      route,
      this.data.planSupportedCapabilityIds as string[],
      this.data.tr as ReturnType<typeof buildGoalTr>,
    );
    const pageState = this as unknown as Record<string, unknown>;
    pageState._planIntentGoalRevision = this.data.planCurrentGoalRevision;
    this.setData({
      planIntent: intent,
      planCapabilityState: presentation.state,
      planCapabilityDescription: presentation.description,
      planCapabilityDetail: presentation.detail,
      planCapabilityBadge: presentation.badge,
    });
  },

  onTogglePlanRoutingReasoning() {
    this.setData({
      planRoutingReasoningOpen: !this.data.planRoutingReasoningOpen,
    });
  },

  onScrollRefresh() {
    this.setData({ refreshing: true });
    void this.refetch().finally(() => this.setData({ refreshing: false }));
  },

  onRetry() { void this.refetch(); },

  /**
   * Tap-toggle the Coach Receipt's findings + recommendations. Only
   * surfaces when there's something to disclose; the WXML guards on
   * `coachToggleLabel`. Recompute the label so "{N} findings · {M}
   * recs" flips to "Hide details" without a re-render of the rest
   * of the receipt body.
   */
  onToggleCoachDetails() {
    const next = !this.data.detailsOpen;
    const coach = this.data.coach;
    if (!coach) return;
    const label = coachToggleLabel(
      coach.findings.length,
      coach.recommendations.length,
      next,
    );
    this.setData({ detailsOpen: next, coachToggleLabel: label });
  },

  toggleNotePrediction() {
    this.setData({ notePredictionExpanded: !this.data.notePredictionExpanded });
  },

  toggleNoteUltra() {
    this.setData({ noteUltraExpanded: !this.data.noteUltraExpanded });
  },

  onTapPredictionSource() {
    if (this.data.notePredictionUrl) copyUrlToClipboard(this.data.notePredictionUrl as string);
  },

  onTapUltraSource() {
    if (this.data.noteUltraUrl) copyUrlToClipboard(this.data.noteUltraUrl as string);
  },

  onOpenEditor() {
    const freshTr = buildGoalTr();
    this.setData({ tr: freshTr });
    const cached = (this.data as { _response?: GoalResponse })._response;
    const goal = ((cached?.goal ?? cached?.race_countdown) ?? null) as
      | { goal_kind?: GoalResponse['goal_kind']; distance?: string | null; race_date?: string | null; target_time_sec?: number | null }
      | null;
    const distanceKey = (goal?.distance as DistanceKey | undefined) ?? 'marathon';
    const idx = Math.max(0, DISTANCE_CHOICES.findIndex((d) => d.key === distanceKey));
    const editorType: 'race' | 'continuous' | 'performance_5k' | 'performance_10k' = goal?.goal_kind === 'performance_5k'
      ? 'performance_5k'
      : goal?.goal_kind === 'performance_10k' && this.data.performance10kEnabled
        ? 'performance_10k'
        : (goal?.race_date ? 'race' : 'continuous');
    const targetTimeSec =
      goal?.target_time_sec && goal.target_time_sec > 0 ? goal.target_time_sec : 0;
    const timeParts = secondsToTimeParts(targetTimeSec);
    const editorRaceDate = goal?.race_date ?? '';
    (this.data as { _editorInitial?: EditorSnapshot })._editorInitial = {
      type: editorType, distanceIndex: idx, raceDate: editorRaceDate, targetTimeSec,
    };
    this.setData({
      editorOpen: true, editorType, editorDistanceIndex: idx, editorRaceDate,
      editorTodayIso: todayIso(), editorTimeParts: timeParts,
      editorTargetDisplay: timePartsToDisplay(timeParts),
      editorError: '', editorSaving: false, editorDirty: false, editorConfirmDiscard: false,
    });
  },

  onCloseEditor() {
    if (this.data.editorSaving) return;
    if (!this.data.editorDirty) {
      this.setData({ editorOpen: false, editorError: '', editorConfirmDiscard: false });
      return;
    }
    this.setData({ editorConfirmDiscard: true });
  },

  onDiscardConfirm() {
    this.setData({ editorOpen: false, editorError: '', editorConfirmDiscard: false });
  },

  onDiscardKeep() { this.setData({ editorConfirmDiscard: false }); },

  onPickEditorType(e: WechatMiniprogram.TouchEvent) {
    const type = e.currentTarget.dataset.type as 'race' | 'continuous' | 'performance_5k' | 'performance_10k' | undefined;
    if (!type) return;
    if (type === 'performance_10k' && !this.data.performance10kEnabled) return;
    this.setData({
      editorType: type,
      ...(type === 'performance_5k'
        ? { editorDistanceIndex: 0 }
        : type === 'performance_10k'
          ? { editorDistanceIndex: 1 }
          : {}),
    });
    this.recomputeEditorDirty();
  },

  onPickEditorDistance(e: WechatMiniprogram.PickerChange) {
    if (this.data.editorType === 'performance_5k' || this.data.editorType === 'performance_10k') return;
    const idx = Number(e.detail.value);
    if (Number.isNaN(idx)) return;
    this.setData({ editorDistanceIndex: idx });
    this.recomputeEditorDirty();
  },

  onPickEditorRaceDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ editorRaceDate: String(e.detail.value) });
    this.recomputeEditorDirty();
  },

  onPickEditorTargetTime(e: WechatMiniprogram.PickerChange) {
    const parts = (e.detail.value as number[]) || [0, 0, 0];
    this.setData({ editorTimeParts: parts, editorTargetDisplay: timePartsToDisplay(parts) });
    this.recomputeEditorDirty();
  },

  recomputeEditorDirty() {
    const snap = (this.data as { _editorInitial?: EditorSnapshot })._editorInitial;
    if (!snap) return;
    const dirty =
      (this.data.editorType as string) !== snap.type ||
      (this.data.editorDistanceIndex as number) !== snap.distanceIndex ||
      (this.data.editorRaceDate as string) !== snap.raceDate ||
      timePartsToSeconds(this.data.editorTimeParts as number[]) !== snap.targetTimeSec;
    if (dirty !== this.data.editorDirty) this.setData({ editorDirty: dirty });
  },

  async onSaveEditor() {
    if (!this.data.editorDirty || this.data.editorSaving) return;
    const tr = this.data.tr as ReturnType<typeof buildGoalTr>;
    const editorType = this.data.editorType as 'race' | 'continuous' | 'performance_5k' | 'performance_10k';
    const editorDistanceIndex = this.data.editorDistanceIndex as number;
    const editorRaceDate = this.data.editorRaceDate as string;
    if (editorType === 'race' && !editorRaceDate) {
      this.setData({ editorError: tr.raceDateRequired });
      return;
    }
    const targetTimeSec = timePartsToSeconds(this.data.editorTimeParts as number[]);
    this.setData({ editorSaving: true, editorError: '' });
    const distance = editorType === 'performance_5k'
      ? '5k'
      : editorType === 'performance_10k'
        ? '10k'
        : (DISTANCE_CHOICES[editorDistanceIndex]?.key ?? 'marathon');
    try {
      const settingsResponse = await apiPut<SettingsUpdateResponse>(
        '/api/settings',
        {
          goal: {
            goal_kind: editorType,
            race_date: editorType === 'race' || editorType === 'performance_10k'
              ? editorRaceDate
              : '',
            distance,
            target_time_sec: targetTimeSec,
          },
        },
      );
      if (settingsResponse.goal_plan_impact) {
        const pageState = this as unknown as Record<string, unknown>;
        pageState._dismissedGoalPlanImpactKey = null;
      }
      this.setData({
        editorOpen: false,
        editorSaving: false,
        goalPlanImpact: settingsResponse.goal_plan_impact,
        goalPlanDecisionBusy: false,
        goalPlanDecisionError: '',
      });
      void this.refetch();
    } catch (e) {
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') {
        this.setData({ editorSaving: false });
        return;
      }
      this.setData({ editorSaving: false, editorError: err?.detail ?? tr.failedToSave });
    }
  },

  onCoachFeedbackStale() {
    void this.refetch();
  },

  async refetch() {
    const pageState = this as unknown as Record<string, unknown>;
    const previousRequestId = typeof pageState._refetchRequestId === 'number'
      ? pageState._refetchRequestId
      : 0;
    const requestId = previousRequestId + 1;
    pageState._refetchRequestId = requestId;
    this.setData({ loading: true, errorMessage: '' });
    const tr = this.data.tr as ReturnType<typeof buildGoalTr>;
    try {
      const locale = (getApp<IAppOption>().globalData.locale ?? 'en') as 'en' | 'zh';
      const [response, insightResponse, capabilityResult] = await Promise.all([
        apiGet<GoalResponse>('/api/goal'),
        fetchInsight('race_forecast').catch((e) => {
          const fe = e as Partial<ApiError>;
          if (fe?.code === 'UNAUTHENTICATED') throw e;
          console.warn('[goal] race_forecast fetch failed; suppressing coach receipt:', e);
          return { insight: null, ai_available: false };
        }),
        apiGet<PlanGenerationCapabilitiesResponse>(
          '/api/plan/generation/capabilities',
        )
          .then((data) => ({ data, error: '' }))
          .catch((error: unknown) => {
            const apiError = error as Partial<ApiError>;
            return {
              data: null,
              error: apiError.detail ?? tr.planStartLoadFailed,
            };
          }),
      ]);
      if (pageState._refetchRequestId !== requestId) return;
      const discovery = capabilityResult.data;
      const serverGoalPlanImpact = discovery
        ? discovery.goal_plan_impact
        : (this.data.goalPlanImpact as GoalPlanImpact | null);
      const goalPlanImpact = (
        serverGoalPlanImpact
        && goalPlanImpactKey(serverGoalPlanImpact)
          !== pageState._dismissedGoalPlanImpactKey
      )
        ? serverGoalPlanImpact
        : null;
      const supportedCapabilityIds = discovery?.capabilities.filter(
        (item) => [
          'outdoor_road_5k_constraints_v1',
          'outdoor_road_10k_constraints_v1',
        ].includes(item.constraint_schema_id),
      ).map((item) => item.id) ?? [];
      const routing = discovery?.routing ?? null;
      const currentGoalId = discovery?.current_goal?.id ?? '';
      const currentGoalRevision = discovery?.current_goal?.revision ?? '';
      const selectedIntentGoalRevision = typeof pageState._planIntentGoalRevision === 'string'
        ? pageState._planIntentGoalRevision
        : '';
      const explicitIntent = selectedIntentGoalRevision === currentGoalRevision
        ? this.data.planIntent
        : '';
      if (selectedIntentGoalRevision !== currentGoalRevision) {
        pageState._planIntentGoalRevision = '';
      }
      const planIntent = (
        explicitIntent
        || routing?.intent
        || ''
      ) as PlanIntent | '';
      const selectedRoute = planIntent
        ? routing?.options.find((option) => option.intent === planIntent) ?? null
        : routing;
      let presentation: PlanRoutePresentation;
      if (capabilityResult.error) {
        presentation = {
          state: 'error',
          description: tr.planStartLoadFailed,
          detail: capabilityResult.error || tr.planStartLoadFailedDetail,
          badge: tr.policyCheckFailed,
        };
      } else {
        presentation = buildPlanRoutePresentation(
          selectedRoute,
          supportedCapabilityIds,
          tr,
        );
      }
      this.setData({
        ...(buildGoalState(
          response,
          insightResponse.insight,
          insightResponse.ai_available,
          locale,
          this.data.themeClass,
        ) as Record<string, unknown>),
        planCapabilityState: presentation.state,
        planCapabilityDescription: presentation.description,
        planCapabilityDetail: presentation.detail,
        planCapabilityBadge: presentation.badge,
        planIntent,
        planCurrentGoalId: currentGoalId,
        planCurrentGoalRevision: currentGoalRevision,
        planRoutingOptions: routing?.options ?? [],
        planSupportedCapabilityIds: supportedCapabilityIds,
        performance10kEnabled: supportedCapabilityIds.includes(
          'outdoor_road_10k_performance_v1',
        ),
        goalPlanImpact,
        _response: response,
      } as Record<string, unknown>);
    } catch (e) {
      if (pageState._refetchRequestId !== requestId) return;
      const err = e as Partial<ApiError>;
      if (err?.code === 'UNAUTHENTICATED') {
        this.setData({ loading: false });
        return;
      }
      this.setData({ loading: false, errorMessage: err?.detail ?? tr.failedToLoad, hasResponse: false });
    }
  },
});
