import { apiPost } from '../../utils/api-client';
import { copyUrlToClipboard } from '../../utils/markdown';
import type { ApiError } from '../../utils/api-client';
import type {
  GoalBaselineCandidate,
  GoalBaselineMutationResponse,
  GoalBaselineResponse,
  PlanGenerationPurposeSelection,
  Road10KAssistanceStatus,
  Road10KBaselineCandidate,
  Road10KBaselineMutationResponse,
  Road10KBaselineResponse,
  Road10KHistoryConfirmationRequest,
  Road10KSurfaceOrProtocol,
} from '../../types/api';
import { formatTime } from '../../utils/format';
import { t, tFmt } from '../../utils/i18n';

const STOP_REASONS = [
  'acute_illness',
  'injury_or_pain_altering_running',
  'chest_pain_or_pressure',
  'fainting_or_near_fainting',
  'unusual_severe_breathlessness',
  'confusion_or_loss_of_coordination',
  'other_red_flag_symptom',
  'known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing',
  'self_reported_inadequate_recovery_or_unresolved_substantial_fatigue',
  'unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course',
] as const;
const ROAD_10K_PROTOCOL_VALUES: readonly Road10KSurfaceOrProtocol[] = [
  'organized_outdoor_road_10k_race',
  'standardized_outdoor_road_10k_time_trial',
  'standardized_track_10k_time_trial',
] as const;
const ROAD_10K_ASSISTANCE_VALUES: readonly Road10KAssistanceStatus[] = [
  'unassisted',
  'assisted',
  'unknown_or_unreported',
] as const;

type BaselineResponse = GoalBaselineResponse | Road10KBaselineResponse;
type BaselineCandidate = GoalBaselineCandidate | Road10KBaselineCandidate;
type MutationResponse = GoalBaselineMutationResponse | Road10KBaselineMutationResponse;

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function isRoad10KBaseline(
  baseline: BaselineResponse | null,
): baseline is Road10KBaselineResponse {
  return Boolean(baseline && 'contract_digest' in baseline);
}

function build5kCopy() {
  return {
    title: t('5K baseline pilot'),
    current: t('Current evidence'),
    candidates: t('History candidates'),
    candidateHint: t('Retrieval is never qualification; only a full activity with explicit distance, timing, and purpose confirmation can become a baseline.'),
    guardrail: t('The 42-day rule is a Praxys pilot guardrail, not a physiological cutoff.'),
    segmentRule: t('Arbitrary 5K segments, best splits, or fast sections inside easy, long, or mixed runs never count as baseline evidence.'),
    noMeaningfulChange: t('There is no meaningful-change threshold yet.'),
    pilotScope: t('This pilot is only for adults who already can complete 5 km.'),
    scienceDescription: t('Qualified 5 km history comes first. The 42-day freshness rule, the optional maximal-effort outdoor 5 km test, and the no-meaningful-change warning are Praxys pilot guardrails, not published universal cutoffs.'),
    testHint: t('This is a maximal-effort test, and the no-test path always stays available.'),
    testTitle: t('Optional 5K pilot test'),
    benchmarkTitle: t('Optional 5K pilot test'),
    benchmarkHint: t('This is a maximal-effort test, and the no-test path always stays available.'),
    reviewCandidate: t('Review this effort'),
    changeCandidate: t('Change confirmation'),
    reviewTest: t('Review optional test'),
    scheduleTest: t('Schedule optional test'),
    completeTest: t('Record test result'),
    stopTest: t('Stop this test'),
    noTestPath: t('Stay on the no-test path'),
    status: {
      current: t('Current'),
      stale: t('Stale'),
      incomparable: t('Needs review'),
      missing: t('Missing evidence'),
      not_required: t('Not required'),
      pending_test: t('Test pending'),
    },
    headline: {
      current: t('History first: you already have usable current 5K evidence.'),
      stale: t('You have older 5K evidence. Praxys keeps it visible and can optionally offer a new pilot test.'),
      incomparable: t('Praxys found candidate 5K efforts, but they are not qualified yet.'),
      missing: t('Praxys has not found qualified 5K history yet.'),
      not_required: t('The current goal is outside this 5K baseline pilot.'),
      pending_test: t('The optional 5K pilot test is in progress.'),
    },
    reviewState: {
      needs_confirmation: t('Needs confirmation'),
      qualified: t('Qualified'),
      excluded: t('Excluded'),
      distance_unverified: t('Distance not verified'),
      timing_unresolved: t('Timing needs review'),
    },
    responseOptions: [
      t('Choose one'),
      t('Measured 5K race'),
      t('Intentional all-out complete 5K'),
      t('Not an all-out 5K effort'),
    ],
    yesNo: [t('Choose one'), t('Yes'), t('No')],
    protocolOptions: [t('Choose one')],
    assistanceOptions: [t('Choose one')],
    confirmTitle: t('Review this activity'),
    confirmPurpose: t('What was this full activity?'),
    confirmMeasured: t('Was the full effort a measured 5K?'),
    confirmTiming: t('Did the recorded time reflect elapsed timing with no unresolved pauses?'),
    protocolLabel: t('Which accepted surface or protocol matched this effort?'),
    routeLabel: t('Route or venue identifier'),
    assistanceLabel: t('Assistance status'),
    scheduleTitle: t('Scheduled date'),
    completeCandidate: t('Choose a synced activity'),
    completeProtocol: t('Did you follow the exact protocol?'),
    stopReason: t('Stop reason'),
    stopReasonLabels: [
      t('Choose one'),
      t('Acute illness'),
      t('Pain or injury altered the run'),
      t('Chest pain or pressure'),
      t('Fainting or near-fainting'),
      t('Unusually severe breathlessness'),
      t('Confusion or loss of coordination'),
      t('Another red-flag symptom'),
      t('A clinician or restriction already rules out vigorous testing'),
      t('Recovery was inadequate or fatigue stayed unresolved'),
      t('Weather, air, traffic, visibility, or footing was unsafe'),
    ],
    alternatives: {
      noTestPath: t('Continue without a test'),
      completionGoal: t('Use a completion or consistency goal'),
      optional10kBenchmark: t('Choose an optional 10K benchmark date'),
      manualTraining: t('Keep training manually for now'),
    },
    cancel: t('Cancel'),
    save: t('Save'),
    success: t('Updated the 5K baseline.'),
    sourceLabel: t('Source'),
    recordUnavailable: t('No synced candidate is available yet.'),
    requestFailed: t('Request failed'),
  };
}

function build10kCopy(baseline: Road10KBaselineResponse) {
  const freshnessDays = (
    baseline.guardrails.baseline_current_through_completed_days
  );
  return {
    title: t('10K direct baseline'),
    current: t('Current evidence'),
    candidates: t('History candidates'),
    candidateHint: t('Retrieval is never qualification; only a full activity with explicit distance, timing, accepted protocol, route or venue, and all-out or race confirmation can become a direct 10K baseline.'),
    guardrail: tFmt(
      'The {0}-day rule is a reviewed guardrail, not a physiological cutoff.',
      freshnessDays,
    ),
    segmentRule: t('Passive fastest 10K splits, best laps, or hard sections inside longer runs never count as direct 10K baseline evidence.'),
    noMeaningfulChange: t('Only current direct 10K race or explicit all-out 10K history can qualify.'),
    pilotScope: t('Full activity only.'),
    scienceDescription: tFmt(
      'Only current direct 10K race or explicit all-out 10K history can qualify. Qualification keeps the accepted protocol, route or venue, assistance status, provider, and authoritative completion time attached to the evidence. The {0}-day freshness guardrail and the optional benchmark path are reviewed product boundaries, not published universal cutoffs.',
      freshnessDays,
    ),
    testHint: t('Choose and date an optional benchmark in the Training plan preview if you want one. Praxys never auto-schedules it.'),
    testTitle: t('Optional 10K benchmark'),
    benchmarkTitle: t('Optional 10K benchmark'),
    benchmarkHint: t('Choose and date an optional benchmark in the Training plan preview if you want one. Praxys never auto-schedules it.'),
    reviewCandidate: t('Review this effort'),
    changeCandidate: t('Change confirmation'),
    reviewTest: t('Review this effort'),
    scheduleTest: t('Schedule optional test'),
    completeTest: t('Record test result'),
    stopTest: t('Stop this test'),
    noTestPath: t('Keep training manually for now'),
    status: {
      current: t('Current'),
      stale: t('Stale'),
      incomparable: t('Needs review'),
      missing: t('Missing evidence'),
      not_required: t('Not required'),
      pending_test: t('Not required'),
    },
    headline: {
      current: t('You already have usable current 10K evidence.'),
      stale: t('You have older 10K evidence. Praxys keeps it visible, but new planning stays readiness-only until you refresh it.'),
      incomparable: t('Praxys found candidate 10K efforts, but they are not qualified yet.'),
      missing: t('Praxys has not found qualified 10K history yet.'),
      not_required: t('The current goal is outside this direct 10K baseline flow.'),
      pending_test: t('The current goal is outside this direct 10K baseline flow.'),
    },
    reviewState: {
      needs_confirmation: t('Needs confirmation'),
      qualified: t('Qualified'),
      excluded: t('Excluded'),
      distance_unverified: t('Distance not verified'),
      timing_unresolved: t('Timing needs review'),
    },
    responseOptions: [
      t('Choose one'),
      t('Measured 10K race'),
      t('Intentional all-out complete 10K'),
      t('Not a direct 10K baseline'),
    ],
    yesNo: [t('Choose one'), t('Yes'), t('No')],
    protocolOptions: [
      t('Choose one'),
      t('Organized outdoor road 10K race'),
      t('Standardized outdoor road 10K time trial'),
      t('Standardized track 10K time trial'),
    ],
    assistanceOptions: [
      t('Choose one'),
      t('Unassisted'),
      t('Assisted'),
      t('Unknown or unreported'),
    ],
    confirmTitle: t('Review this activity'),
    confirmPurpose: t('What was this full activity?'),
    confirmMeasured: t('Was the full effort a measured 10K?'),
    confirmTiming: t('Did the recorded time reflect elapsed timing with no unresolved pauses?'),
    protocolLabel: t('Which accepted surface or protocol matched this effort?'),
    routeLabel: t('Route or venue identifier'),
    assistanceLabel: t('Assistance status'),
    scheduleTitle: t('Scheduled date'),
    completeCandidate: t('Choose a synced activity'),
    completeProtocol: t('Did you follow the exact protocol?'),
    stopReason: t('Stop reason'),
    stopReasonLabels: [t('Choose one')],
    alternatives: {
      noTestPath: t('Continue without a test'),
      completionGoal: t('Use a completion or consistency goal'),
      optional10kBenchmark: t('Choose an optional 10K benchmark date'),
      manualTraining: t('Keep training manually for now'),
    },
    cancel: t('Cancel'),
    save: t('Save'),
    success: t('Updated the 10K baseline.'),
    sourceLabel: t('Source'),
    recordUnavailable: t('No synced candidate is available yet.'),
    requestFailed: t('Request failed'),
  };
}

function buildCopy(baseline: BaselineResponse | null) {
  return isRoad10KBaseline(baseline)
    ? build10kCopy(baseline)
    : build5kCopy();
}

function candidateResponseIndex(candidate: BaselineCandidate): number {
  return candidate.confirmation_response === 'race'
    ? 1
    : candidate.confirmation_response === 'intentional_all_out'
      ? 2
      : candidate.confirmation_response === 'not_all_out'
        ? 3
        : 0;
}

function road10kProtocolIndex(
  value: Road10KSurfaceOrProtocol | null | undefined,
): number {
  const index = ROAD_10K_PROTOCOL_VALUES.indexOf(value ?? 'organized_outdoor_road_10k_race');
  return value == null || index < 0 ? 0 : index + 1;
}

function road10kAssistanceIndex(
  value: Road10KAssistanceStatus | null | undefined,
): number {
  const index = ROAD_10K_ASSISTANCE_VALUES.indexOf(value ?? 'unassisted');
  return value == null || index < 0 ? 0 : index + 1;
}

Component({
  properties: {
    baseline: { type: Object, value: null },
    goal: { type: Object, value: null },
    purpose: { type: Object, value: null },
    disabled: { type: Boolean, value: false },
  },
  data: {
    copy: buildCopy(null),
    isRoad10K: false,
    dialogMode: '',
    activeCandidateIndex: 0,
    responseIndex: 0,
    measuredIndex: 0,
    timingIndex: 0,
    protocolIndex: 0,
    routeOrVenue: '',
    assistanceIndex: 0,
    scheduleDate: todayIso(),
    activityIndex: 0,
    protocolFollowedIndex: 0,
    stopReasonIndex: 0,
    hasCandidates: false,
    candidateRows: [] as Array<Record<string, unknown>>,
    activityOptions: [] as string[],
    evidenceText: '',
    evidenceMeta: '' as string,
    scheduledDateDisplay: '',
    alternativesText: '',
    saving: false,
    errorMessage: '',
    notice: '',
  },
  observers: {
    baseline(next: BaselineResponse | null) {
      if (!next) return;
      const road10k = isRoad10KBaseline(next);
      const copy = buildCopy(next);
      const candidateRows = next.candidates.map((candidate) => ({
        ...candidate,
        headline: `${candidate.observed_date} · ${candidate.distance_km != null ? candidate.distance_km.toFixed(2) : '—'} km · ${candidate.duration_sec ? formatTime(Math.round(candidate.duration_sec)) : '—'}`,
        reviewLabel: copy.reviewState[candidate.review_state],
      }));
      const evidenceText = next.evidence
        ? `${next.evidence.observed_date} · ${next.evidence.distance_km != null ? next.evidence.distance_km.toFixed(2) : '—'} km · ${next.evidence.elapsed_time_sec ? formatTime(Math.round(next.evidence.elapsed_time_sec)) : '—'}`
        : '';
      const evidenceMeta = road10k && next.evidence
        ? [
          next.evidence.surface_or_protocol
            ? copy.protocolOptions[
              road10kProtocolIndex(next.evidence.surface_or_protocol)
            ]
            : '',
          next.evidence.route_or_venue_identifier ?? '',
          next.evidence.assistance_status
            ? copy.assistanceOptions[
              road10kAssistanceIndex(next.evidence.assistance_status)
            ]
            : '',
          next.evidence.source_provider === 'garmin'
            ? 'Garmin'
            : next.evidence.source_provider === 'stryd'
              ? 'Stryd'
              : next.evidence.source_provider === 'strava'
                ? 'Strava'
                : next.evidence.source_provider ?? '',
        ].filter(Boolean).join(' · ')
        : '';
      const alternativesText = road10k
        ? (next.alternatives ?? []).map((alternative) => (
          alternative === 'optional_10k_benchmark'
            ? copy.alternatives.optional10kBenchmark
            : alternative === 'manual_training'
              ? copy.alternatives.manualTraining
              : alternative
        )).join(' · ')
        : (next.alternatives ?? []).map((alternative) => (
          alternative === 'no_test_path'
            ? copy.alternatives.noTestPath
            : alternative === 'completion_or_consistency_goal'
              ? copy.alternatives.completionGoal
              : alternative
        )).join(' · ');
      this.setData({
        copy,
        isRoad10K: road10k,
        activityIndex: 0,
        scheduleDate: !road10k && 'test' in next ? next.test.scheduled_workout?.date ?? todayIso() : todayIso(),
        hasCandidates: candidateRows.length > 0,
        candidateRows,
        activityOptions: [copy.yesNo[0], ...next.candidates.map((candidate) => `${candidate.observed_date} · ${candidate.distance_km != null ? candidate.distance_km.toFixed(2) : '—'} km`)],
        evidenceText,
        evidenceMeta,
        scheduledDateDisplay: !road10k && 'test' in next ? next.test.scheduled_workout?.date ?? '' : '',
        alternativesText,
      });
    },
  },
  methods: {
    openConfirm(e: WechatMiniprogram.TouchEvent) {
      const index = Number(e.currentTarget.dataset.index ?? 0);
      const baseline = this.properties.baseline as BaselineResponse | null;
      const candidate = baseline?.candidates?.[index] as BaselineCandidate | undefined;
      if (!candidate) return;
      const road10k = isRoad10KBaseline(baseline);
      const road10kCandidate = candidate as Road10KBaselineCandidate;
      const goalBaselineCandidate = candidate as GoalBaselineCandidate;
      this.setData({
        dialogMode: 'confirm',
        activeCandidateIndex: index,
        responseIndex: candidateResponseIndex(candidate),
        measuredIndex: road10k
          ? road10kCandidate.measured_10k_confirmed == null ? 0 : road10kCandidate.measured_10k_confirmed ? 1 : 2
          : goalBaselineCandidate.measured_5k_confirmed == null ? 0 : goalBaselineCandidate.measured_5k_confirmed ? 1 : 2,
        timingIndex: candidate.elapsed_timing_confirmed == null ? 0 : candidate.elapsed_timing_confirmed ? 1 : 2,
        protocolIndex: road10k ? road10kProtocolIndex(road10kCandidate.surface_or_protocol) : 0,
        routeOrVenue: road10k ? (road10kCandidate.route_or_venue_identifier ?? '') : '',
        assistanceIndex: road10k ? road10kAssistanceIndex(road10kCandidate.assistance_status) : 0,
        errorMessage: '',
      });
    },
    openOffer() { if (!this.data.isRoad10K) this.setData({ dialogMode: 'offer', errorMessage: '' }); },
    openSchedule() { if (!this.data.isRoad10K) this.setData({ dialogMode: 'schedule', errorMessage: '' }); },
    openComplete() {
      if (!this.data.isRoad10K) {
        this.setData({ dialogMode: 'complete', errorMessage: '', activityIndex: 0, measuredIndex: 0, timingIndex: 0, protocolFollowedIndex: 0 });
      }
    },
    openStop() { if (!this.data.isRoad10K) this.setData({ dialogMode: 'stop', errorMessage: '', stopReasonIndex: 0 }); },
    closeDialog() { if (!this.data.saving) this.setData({ dialogMode: '', errorMessage: '' }); },
    onResponseChange(e: WechatMiniprogram.PickerChange) { this.setData({ responseIndex: Number(e.detail.value) }); },
    onMeasuredChange(e: WechatMiniprogram.PickerChange) { this.setData({ measuredIndex: Number(e.detail.value) }); },
    onTimingChange(e: WechatMiniprogram.PickerChange) { this.setData({ timingIndex: Number(e.detail.value) }); },
    onProtocolChange(e: WechatMiniprogram.PickerChange) { this.setData({ protocolIndex: Number(e.detail.value) }); },
    onRouteInput(e: WechatMiniprogram.Input) { this.setData({ routeOrVenue: String(e.detail.value ?? '') }); },
    onAssistanceChange(e: WechatMiniprogram.PickerChange) { this.setData({ assistanceIndex: Number(e.detail.value) }); },
    onScheduleDate(e: WechatMiniprogram.PickerChange) { this.setData({ scheduleDate: String(e.detail.value) }); },
    onActivityChange(e: WechatMiniprogram.PickerChange) { this.setData({ activityIndex: Number(e.detail.value) }); },
    onProtocolFollowedChange(e: WechatMiniprogram.PickerChange) { this.setData({ protocolFollowedIndex: Number(e.detail.value) }); },
    onStopReasonChange(e: WechatMiniprogram.PickerChange) { this.setData({ stopReasonIndex: Number(e.detail.value) }); },
    async submitConfirm() {
      const baseline = this.properties.baseline as BaselineResponse | null;
      const candidate = baseline?.candidates?.[this.data.activeCandidateIndex] as BaselineCandidate | undefined;
      if (!candidate) return;
      if (this.data.isRoad10K) {
        const response = ['race', 'intentional_all_out', 'not_all_out'][this.data.responseIndex - 1] as Road10KHistoryConfirmationRequest['response'] | undefined;
        const directQualificationClaim = response === 'race' || response === 'intentional_all_out';
        if (
          !response
          || this.data.measuredIndex === 0
          || this.data.timingIndex === 0
          || this.data.assistanceIndex === 0
          || (
            directQualificationClaim
            && (
              this.data.protocolIndex === 0
              || !String(this.data.routeOrVenue || '').trim()
            )
          )
        ) {
          this.setData({ errorMessage: this.data.copy.yesNo[0] });
          return;
        }
        const body: Road10KHistoryConfirmationRequest = {
          activity_id: candidate.activity_id,
          response,
          measured_10k: this.data.measuredIndex === 1,
          elapsed_timing_confirmed: this.data.timingIndex === 1,
          assistance_status: ROAD_10K_ASSISTANCE_VALUES[this.data.assistanceIndex - 1],
        };
        if (directQualificationClaim) {
          body.surface_or_protocol = ROAD_10K_PROTOCOL_VALUES[this.data.protocolIndex - 1];
          body.route_or_venue_identifier = String(this.data.routeOrVenue).trim();
        }
        await this.runMutation('/api/plan/road-10k/baseline/history/confirm', body);
        return;
      }
      if (this.data.responseIndex === 0 || this.data.measuredIndex === 0 || this.data.timingIndex === 0) {
        this.setData({ errorMessage: this.data.copy.yesNo[0] });
        return;
      }
      await this.runMutation('/api/goal/baseline/history/confirm', {
        activity_id: candidate.activity_id,
        response: ['race', 'intentional_all_out', 'not_all_out'][this.data.responseIndex - 1],
        measured_5k: this.data.measuredIndex === 1,
        elapsed_timing_confirmed: this.data.timingIndex === 1,
      });
    },
    async submitOffer() { if (!this.data.isRoad10K) await this.runMutation('/api/goal/baseline/test', { action: 'offer' }); },
    async submitDecline() { if (!this.data.isRoad10K) await this.runMutation('/api/goal/baseline/test', { action: 'decline' }); },
    async submitSchedule() {
      if (!this.data.isRoad10K) {
        await this.runMutation('/api/goal/baseline/test', { action: 'schedule', scheduled_date: this.data.scheduleDate });
      }
    },
    async submitComplete() {
      if (this.data.isRoad10K) return;
      const baseline = this.properties.baseline as GoalBaselineResponse | null;
      if (this.data.activityIndex === 0 || this.data.measuredIndex === 0 || this.data.timingIndex === 0 || this.data.protocolFollowedIndex === 0) {
        this.setData({ errorMessage: this.data.copy.yesNo[0] });
        return;
      }
      const candidate = baseline?.candidates?.[this.data.activityIndex - 1] as GoalBaselineCandidate | undefined;
      if (!candidate) {
        this.setData({ errorMessage: this.data.copy.recordUnavailable });
        return;
      }
      await this.runMutation('/api/goal/baseline/test', {
        action: 'complete',
        activity_id: candidate.activity_id,
        measured_5k: this.data.measuredIndex === 1,
        elapsed_timing_confirmed: this.data.timingIndex === 1,
        protocol_followed: this.data.protocolFollowedIndex === 1,
      });
    },
    onCopyScienceSource() {
      const baseline = this.properties.baseline as BaselineResponse | null;
      const source = baseline?.science_note?.citations?.[0]?.url;
      if (source) copyUrlToClipboard(source);
    },
    async submitStop() {
      if (this.data.isRoad10K) return;
      if (this.data.stopReasonIndex === 0) {
        this.setData({ errorMessage: this.data.copy.yesNo[0] });
        return;
      }
      await this.runMutation('/api/goal/baseline/test', {
        action: 'stop',
        reason_code: STOP_REASONS[this.data.stopReasonIndex - 1],
      });
    },
    async runMutation(path: string, body: Record<string, unknown> | Road10KHistoryConfirmationRequest) {
      this.setData({ saving: true, errorMessage: '', notice: '' });
      try {
        const purpose = this.properties.purpose as PlanGenerationPurposeSelection | null;
        await apiPost<MutationResponse>(path, purpose
          ? { ...body, purpose }
          : body, {
          headers: { 'Idempotency-Key': `${Date.now()}-${Math.random()}` },
        });
        this.setData({ saving: false, dialogMode: '', notice: this.data.copy.success });
        this.triggerEvent('refresh');
      } catch (e) {
        const err = e as Partial<ApiError>;
        this.setData({ saving: false, errorMessage: err?.detail ?? this.data.copy.requestFailed });
      }
    },
  },
});
