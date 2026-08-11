import { apiPost } from '../../utils/api-client';
import { copyUrlToClipboard } from '../../utils/markdown';
import type { ApiError } from '../../utils/api-client';
import type {
  GoalBaselineCandidate,
  GoalBaselineMutationResponse,
  GoalBaselineResponse,
} from '../../types/api';
import { formatTime } from '../../utils/format';
import { t } from '../../utils/i18n';

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

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function buildCopy() {
  return {
    title: t('5K baseline pilot'),
    current: t('Current evidence'),
    candidates: t('History candidates'),
    candidateHint: t('Retrieval is never qualification; only a full activity with explicit distance, timing, and purpose confirmation can become a baseline.'),
    segmentRule: t('Arbitrary 5K segments, best splits, or fast sections inside easy, long, or mixed runs never count as baseline evidence.'),
    noMeaningfulChange: t('There is no meaningful-change threshold yet.'),
    pilotGuardrail: t('The 42-day rule is a Praxys pilot guardrail, not a physiological cutoff.'),
    pilotScope: t('This pilot is only for adults who already can complete 5 km.'),
    scienceDescription: t('Qualified 5 km history comes first. The 42-day freshness rule, the optional maximal-effort outdoor 5 km test, and the no-meaningful-change warning are Praxys pilot guardrails, not published universal cutoffs.'),
    testHint: t('This is a maximal-effort test, and the no-test path always stays available.'),
    testTitle: t('Optional 5K pilot test'),
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
    confirmTitle: t('Review this activity'),
    confirmPurpose: t('What was this full activity?'),
    confirmMeasured: t('Was the full effort a measured 5K?'),
    confirmTiming: t('Did the recorded time reflect elapsed timing with no unresolved pauses?'),
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
    },
    cancel: t('Cancel'),
    save: t('Save'),
    success: t('Updated the 5K baseline.'),
    sourceLabel: t('Source'),
    recordUnavailable: t('No synced candidate is available yet.'),
    requestFailed: t('Request failed'),
  };
}

Component({
  properties: {
    baseline: { type: Object, value: null },
    goal: { type: Object, value: null },
    disabled: { type: Boolean, value: false },
  },
  data: {
    copy: buildCopy(),
    dialogMode: '',
    activeCandidateIndex: 0,
    responseIndex: 0,
    measuredIndex: 0,
    timingIndex: 0,
    scheduleDate: todayIso(),
    activityIndex: 0,
    protocolIndex: 0,
    stopReasonIndex: 0,
    hasCandidates: false,
    candidateRows: [] as Array<Record<string, unknown>>,
    activityOptions: [] as string[],
    evidenceText: '',
    scheduledDateDisplay: '',
    alternativesText: '',
    saving: false,
    errorMessage: '',
    notice: '',
  },
  observers: {
    baseline(next: GoalBaselineResponse | null) {
      if (!next) return;
      const copy = buildCopy();
      const candidateRows = next.candidates.map((candidate) => ({
        ...candidate,
        headline: `${candidate.observed_date} · ${candidate.distance_km != null ? candidate.distance_km.toFixed(2) : '—'} km · ${candidate.duration_sec ? formatTime(Math.round(candidate.duration_sec)) : '—'}`,
        reviewLabel: copy.reviewState[candidate.review_state],
      }));
      const activityOptions = [copy.yesNo[0], ...next.candidates.map((candidate) => `${candidate.observed_date} · ${candidate.distance_km != null ? candidate.distance_km.toFixed(2) : '—'} km`)];
      const evidenceText = next.evidence
        ? `${next.evidence.observed_date} · ${next.evidence.distance_km != null ? next.evidence.distance_km.toFixed(2) : '—'} km · ${next.evidence.elapsed_time_sec ? formatTime(Math.round(next.evidence.elapsed_time_sec)) : '—'}`
        : '';
      const alternativesText = (next.alternatives ?? []).map((alternative) => (
        alternative === 'no_test_path'
          ? copy.alternatives.noTestPath
          : alternative === 'completion_or_consistency_goal'
            ? copy.alternatives.completionGoal
            : alternative
      )).join(' · ');
      this.setData({
        copy,
        activityIndex: 0,
        scheduleDate: next.test.scheduled_workout?.date ?? todayIso(),
        hasCandidates: candidateRows.length > 0,
        candidateRows,
        activityOptions,
        evidenceText,
        scheduledDateDisplay: next.test.scheduled_workout?.date ?? '',
        alternativesText,
      });
    },
  },
  methods: {
    openConfirm(e: WechatMiniprogram.TouchEvent) {
      const index = Number(e.currentTarget.dataset.index ?? 0);
      const candidates = (this.properties.baseline as GoalBaselineResponse | null)?.candidates ?? [];
      const candidate = candidates[index];
      if (!candidate) return;
      const responseIndex = candidate.confirmation_response === 'race'
        ? 1
        : candidate.confirmation_response === 'not_all_out'
          ? 3
          : candidate.confirmation_response === 'intentional_all_out'
            ? 2
            : 0;
      this.setData({
        dialogMode: 'confirm',
        activeCandidateIndex: index,
        responseIndex,
        measuredIndex: candidate.measured_5k_confirmed == null ? 0 : candidate.measured_5k_confirmed ? 1 : 2,
        timingIndex: candidate.elapsed_timing_confirmed == null ? 0 : candidate.elapsed_timing_confirmed ? 1 : 2,
        errorMessage: '',
      });
    },
    openOffer() { this.setData({ dialogMode: 'offer', errorMessage: '' }); },
    openSchedule() { this.setData({ dialogMode: 'schedule', errorMessage: '' }); },
    openComplete() { this.setData({ dialogMode: 'complete', errorMessage: '', activityIndex: 0, measuredIndex: 0, timingIndex: 0, protocolIndex: 0 }); },
    openStop() { this.setData({ dialogMode: 'stop', errorMessage: '', stopReasonIndex: 0 }); },
    closeDialog() { if (!this.data.saving) this.setData({ dialogMode: '', errorMessage: '' }); },
    onResponseChange(e: WechatMiniprogram.PickerChange) { this.setData({ responseIndex: Number(e.detail.value) }); },
    onMeasuredChange(e: WechatMiniprogram.PickerChange) { this.setData({ measuredIndex: Number(e.detail.value) }); },
    onTimingChange(e: WechatMiniprogram.PickerChange) { this.setData({ timingIndex: Number(e.detail.value) }); },
    onScheduleDate(e: WechatMiniprogram.PickerChange) { this.setData({ scheduleDate: String(e.detail.value) }); },
    onActivityChange(e: WechatMiniprogram.PickerChange) { this.setData({ activityIndex: Number(e.detail.value) }); },
    onProtocolChange(e: WechatMiniprogram.PickerChange) { this.setData({ protocolIndex: Number(e.detail.value) }); },
    onStopReasonChange(e: WechatMiniprogram.PickerChange) { this.setData({ stopReasonIndex: Number(e.detail.value) }); },
    async submitConfirm() {
      const baseline = this.properties.baseline as GoalBaselineResponse | null;
      const candidate = baseline?.candidates?.[this.data.activeCandidateIndex] as GoalBaselineCandidate | undefined;
      if (!candidate) return;
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
    async submitOffer() { await this.runMutation('/api/goal/baseline/test', { action: 'offer' }); },
    async submitDecline() { await this.runMutation('/api/goal/baseline/test', { action: 'decline' }); },
    async submitSchedule() {
      await this.runMutation('/api/goal/baseline/test', { action: 'schedule', scheduled_date: this.data.scheduleDate });
    },
    async submitComplete() {
      const baseline = this.properties.baseline as GoalBaselineResponse | null;
      if (this.data.activityIndex === 0 || this.data.measuredIndex === 0 || this.data.timingIndex === 0 || this.data.protocolIndex === 0) {
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
        protocol_followed: this.data.protocolIndex === 1,
      });
    },
    onCopyScienceSource() {
      const baseline = this.properties.baseline as GoalBaselineResponse | null;
      const source = baseline?.science_note?.citations?.[0]?.url;
      if (source) copyUrlToClipboard(source);
    },
    async submitStop() {
      if (this.data.stopReasonIndex === 0) {
        this.setData({ errorMessage: this.data.copy.yesNo[0] });
        return;
      }
      await this.runMutation('/api/goal/baseline/test', {
        action: 'stop',
        reason_code: STOP_REASONS[this.data.stopReasonIndex - 1],
      });
    },
    async runMutation(path: string, body: Record<string, unknown>) {
      this.setData({ saving: true, errorMessage: '', notice: '' });
      try {
        await apiPost<GoalBaselineMutationResponse>(path, body, {
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
