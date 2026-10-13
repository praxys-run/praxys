import type { RecoveryAnalysis, TrainingSignal } from '../types/api';

export type TodayAdviceKey = TrainingSignal['recommendation']
  | 'unscheduled_go' | 'unscheduled_easy' | 'unscheduled_rest' | 'unscheduled_unknown';

/** Present the existing guidance separately from whether a workout is scheduled. */
export function todayAdviceKey(signal: TrainingSignal, recovery: RecoveryAnalysis | null | undefined): TodayAdviceKey {
  if (signal.recommendation !== 'unscheduled') return signal.recommendation;
  if (signal.reason_code === 'unscheduled_hrv_caution') return 'unscheduled_rest';
  if (signal.reason_code === 'unscheduled_high_load') return 'unscheduled_easy';
  if (signal.reason_code === 'unscheduled_open'
      && (recovery?.status === 'normal' || recovery?.status === 'fresh')
      && recovery.hrv && Number.isFinite(recovery.hrv.today_ms) && (recovery.hrv.today_ms ?? 0) > 0
      && !recovery.hrv_is_stale && !recovery.classification_reason) {
    return 'unscheduled_go';
  }
  return 'unscheduled_unknown';
}
