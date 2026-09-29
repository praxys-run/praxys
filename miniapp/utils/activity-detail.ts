import type { ActivityDetailSample } from '../types/api';
import { formatStoredPace } from './format';

export const TRACE_KEYS = [
  'power_watts', 'hr_bpm', 'pace_sec_km', 'cadence_spm', 'speed_ms',
  'altitude_m', 'grade_pct', 'temperature_c', 'ground_time_ms',
  'oscillation_mm', 'vertical_ratio', 'leg_spring_kn_m',
  'form_power_watts', 'respiration_rate',
] as const;
export type TraceKey = typeof TRACE_KEYS[number];

export function recordedMetrics(samples: ActivityDetailSample[]): TraceKey[] {
  return TRACE_KEYS.filter((key) => samples.some((point) => point[key] != null));
}

export function elapsed(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor(value % 3600 / 60);
  const secondsPart = String(value % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${secondsPart}` : `${minutes}:${secondsPart}`;
}

export function reading(point: ActivityDetailSample | null, key: TraceKey): string {
  const value = point?.[key];
  return value == null ? '—' : key === 'pace_sec_km'
    ? formatStoredPace(value) : `${Number(value.toFixed(key === 'speed_ms' || key === 'leg_spring_kn_m' ? 2 : 0))} ${metricUnit(key)}`;
}

export function metricUnit(key: TraceKey): string {
  switch (key) {
    case 'power_watts': case 'form_power_watts': return 'W';
    case 'hr_bpm': return 'bpm';
    case 'pace_sec_km': return '/km';
    case 'cadence_spm': return 'spm';
    case 'speed_ms': return 'm/s';
    case 'altitude_m': return 'm';
    case 'grade_pct': case 'vertical_ratio': return '%';
    case 'temperature_c': return '°C';
    case 'ground_time_ms': return 'ms';
    case 'oscillation_mm': return 'mm';
    case 'leg_spring_kn_m': return 'kN/m';
    case 'respiration_rate': return 'breaths/min';
  }
}

export function closestSample(
  samples: ActivityDetailSample[], offset: number, metric: TraceKey,
): ActivityDetailSample | null {
  if (!samples.length || offset < samples[0].offset_sec || offset > samples[samples.length - 1].offset_sec) return null;
  let left = 0;
  let right = samples.length - 1;
  while (left < right) {
    const middle = Math.floor((left + right) / 2);
    if (samples[middle].offset_sec < offset) left = middle + 1;
    else right = middle;
  }
  const after = samples[left];
  if (after.offset_sec === offset) return after;
  const before = samples[left - 1];
  if (!before) return null;
  if (Math.min(offset - before.offset_sec, after.offset_sec - offset) > (after[`${metric}_break`] ? 2 : 5)) return null;
  return offset - before.offset_sec <= after.offset_sec - offset ? before : after;
}
