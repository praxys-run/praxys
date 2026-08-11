import type { IAppOption } from '../../app';
import { apiPost } from '../../utils/api-client';
import { copyUrlToClipboard } from '../../utils/markdown';
import type { ApiError } from '../../utils/api-client';
import type {
  GoalBaselineCandidate,
  GoalBaselineMutationResponse,
  GoalBaselineResponse,
} from '../../types/api';
import { formatTime } from '../../utils/format';

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

function buildCopy(locale: 'en' | 'zh') {
  const zh = locale === 'zh';
  return {
    title: zh ? '5 公里基线试点' : '5K baseline pilot',
    current: zh ? '当前证据' : 'Current evidence',
    candidates: zh ? '历史候选活动' : 'History candidates',
    candidateHint: zh ? '候选检索永远不等于资格认定；只有完整活动、明确确认的测距与计时才可能成为基线。' : 'Retrieval is never qualification; only explicit confirmation can make a full activity count as baseline evidence.',
    segmentRule: zh ? '任意 5 公里片段、最佳分段、轻松跑或长跑中的快速段都不会成为基线。' : 'Arbitrary 5K segments, best splits, and fast sections inside easy, long, or mixed runs never count as baseline evidence.',
    noMeaningfulChange: zh ? '目前还没有可用的“有意义变化”阈值。' : 'There is no meaningful-change threshold yet.',
    pilotGuardrail: zh ? '42 天规则是 Praxys 试点护栏；可选测试是最大努力。' : 'The 42-day rule is a Praxys pilot guardrail; the optional test is maximal effort.',
    reviewCandidate: zh ? '确认这次活动' : 'Review this effort',
    reviewTest: zh ? '查看可选测试' : 'Review optional test',
    scheduleTest: zh ? '安排可选测试' : 'Schedule optional test',
    completeTest: zh ? '记录测试结果' : 'Record test result',
    stopTest: zh ? '停止这次测试' : 'Stop this test',
    noTestPath: zh ? '先不做测试' : 'Stay on the no-test path',
    status: {
      current: zh ? '当前' : 'Current',
      stale: zh ? '已过期' : 'Stale',
      incomparable: zh ? '待确认' : 'Needs review',
      missing: zh ? '缺少证据' : 'Missing evidence',
      not_required: zh ? '当前目标不需要' : 'Not required',
      pending_test: zh ? '测试待完成' : 'Test pending',
    },
    responseOptions: [
      zh ? '请选择' : 'Choose one',
      zh ? '测量好的 5 公里比赛' : 'Measured 5K race',
      zh ? '明确的 5 公里全力完成' : 'Intentional all-out complete 5K',
      zh ? '不是全力 5 公里' : 'Not an all-out 5K effort',
    ],
    yesNo: [zh ? '请选择' : 'Choose one', zh ? '是' : 'Yes', zh ? '否' : 'No'],
    confirmTitle: zh ? '确认这次活动' : 'Review this activity',
    confirmPurpose: zh ? '这次完整活动是什么？' : 'What was this full activity?',
    confirmMeasured: zh ? '是否是测量好的完整 5 公里？' : 'Was the full effort a measured 5K?',
    confirmTiming: zh ? '记录时间是否反映了无未解决暂停的耗时？' : 'Did the recorded time reflect elapsed timing with no unresolved pauses?',
    scheduleTitle: zh ? '安排日期' : 'Scheduled date',
    completeCandidate: zh ? '选择同步活动' : 'Choose a synced activity',
    completeProtocol: zh ? '是否按完整协议执行？' : 'Did you follow the exact protocol?',
    stopReason: zh ? '停止原因' : 'Stop reason',
    stopReasonLabels: [
      zh ? '请选择' : 'Choose one',
      zh ? '急性疾病' : 'Acute illness',
      zh ? '疼痛或伤病改变了跑步方式' : 'Pain or injury altered the run',
      zh ? '胸痛或压迫感' : 'Chest pain or pressure',
      zh ? '晕厥或接近晕厥' : 'Fainting or near-fainting',
      zh ? '异常严重气短' : 'Unusually severe breathlessness',
      zh ? '意识混乱或失去协调' : 'Confusion or loss of coordination',
      zh ? '其他红旗症状' : 'Another red-flag symptom',
      zh ? '已有医疗限制或临床建议不要做高强度测试' : 'A clinician or restriction already rules out vigorous testing',
      zh ? '恢复不足或显著疲劳未解决' : 'Recovery was inadequate or fatigue stayed unresolved',
      zh ? '天气、空气、交通、能见度或路面不安全' : 'Weather, air, traffic, visibility, or footing was unsafe',
    ],
    cancel: zh ? '取消' : 'Cancel',
    save: zh ? '保存' : 'Save',
    success: zh ? '已更新 5 公里基线。' : 'Updated the 5K baseline.',
    recordUnavailable: zh ? '当前没有可记录的同步候选活动。' : 'No synced candidate is available yet.',
  };
}

Component({
  properties: {
    baseline: { type: Object, value: null },
    goal: { type: Object, value: null },
    disabled: { type: Boolean, value: false },
  },
  data: {
    locale: (getApp<IAppOption>().globalData.locale ?? 'en') as 'en' | 'zh',
    copy: buildCopy((getApp<IAppOption>().globalData.locale ?? 'en') as 'en' | 'zh'),
    dialogMode: '',
    activeCandidateIndex: 0,
    responseIndex: 0,
    measuredIndex: 0,
    timingIndex: 0,
    scheduleDate: todayIso(),
    activityIndex: 0,
    protocolIndex: 0,
    stopReasonIndex: 0,
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
      const locale = this.data.locale as 'en' | 'zh';
      const candidateRows = next.candidates.map((candidate) => ({
        ...candidate,
        headline: `${candidate.observed_date} · ${candidate.distance_km != null ? candidate.distance_km.toFixed(2) : '—'} km · ${candidate.duration_sec ? formatTime(Math.round(candidate.duration_sec)) : '—'}`,
      }));
      const activityOptions = [locale === 'zh' ? '请选择' : 'Choose one', ...next.candidates.map((candidate) => `${candidate.observed_date} · ${candidate.distance_km != null ? candidate.distance_km.toFixed(2) : '—'} km`)];
      const evidenceText = next.evidence
        ? `${next.evidence.observed_date} · ${next.evidence.distance_km != null ? next.evidence.distance_km.toFixed(2) : '—'} km · ${next.evidence.elapsed_time_sec ? formatTime(Math.round(next.evidence.elapsed_time_sec)) : '—'}`
        : '';
      const alternativesText = (next.alternatives ?? []).join(' · ');
      this.setData({
        activityIndex: 0,
        scheduleDate: next.test.scheduled_workout?.date ?? todayIso(),
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
        this.setData({ saving: false, errorMessage: err?.detail ?? 'Request failed' });
      }
    },
  },
});
