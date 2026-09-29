import type { ActivityDetailSample } from '@/types/api';
import type { ChartColors } from '@/lib/chart-theme';

export const TRACE_KEYS = [
  'power_watts', 'hr_bpm', 'pace_sec_km', 'cadence_spm', 'speed_ms',
  'altitude_m', 'grade_pct', 'temperature_c', 'ground_time_ms',
  'oscillation_mm', 'vertical_ratio', 'leg_spring_kn_m',
  'form_power_watts', 'respiration_rate',
] as const;
export type TraceKey = typeof TRACE_KEYS[number];

export function traceUnit(metric: TraceKey): string {
  switch (metric) {
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

export function traceColor(metric: TraceKey, palette: ChartColors): string {
  switch (metric) {
    case 'power_watts': case 'form_power_watts': return palette.activityPower;
    case 'hr_bpm': return palette.activityHeart;
    case 'pace_sec_km': return palette.activityPace;
    case 'cadence_spm': return palette.activityCadence;
    case 'speed_ms': return palette.activitySpeed;
    case 'altitude_m': case 'grade_pct': return palette.activityTerrain;
    case 'temperature_c': return palette.activityWeather;
    case 'ground_time_ms': case 'oscillation_mm': case 'vertical_ratio': case 'leg_spring_kn_m':
      return palette.activityDynamics;
    case 'respiration_rate': return palette.activityBreathing;
  }
}

export function availableTraces(samples: ActivityDetailSample[]): TraceKey[] {
  return TRACE_KEYS.filter((key) => samples.some((point) => point[key] != null));
}

export function formatElapsed(seconds: number): string {
  const rounded = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const remaining = String(rounded % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${remaining}` : `${minutes}:${remaining}`;
}

export function zoomTraceViewport(
  viewport: [number, number], cursor: number, full: [number, number], factor: number, minimumSeconds: number,
): [number, number] {
  const span = Math.min(full[1] - full[0], Math.max(minimumSeconds, (viewport[1] - viewport[0]) * factor));
  const center = Math.max(viewport[0], Math.min(viewport[1], cursor));
  const lower = factor < 1 ? viewport[0] : full[0];
  const upper = factor < 1 ? viewport[1] : full[1];
  const start = Math.max(lower, Math.min(upper - span, center - span / 2));
  return [Math.floor(start), Math.ceil(start + span)];
}

export function closestRecordedSample(
  samples: ActivityDetailSample[],
  offset: number,
  primary: TraceKey,
): ActivityDetailSample | null {
  if (!samples.length || offset < samples[0].offset_sec || offset > samples[samples.length - 1].offset_sec) {
    return null;
  }
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
  if (Math.min(offset - before.offset_sec, after.offset_sec - offset) > (after[`${primary}_break`] ? 2 : 5)) return null;
  return offset - before.offset_sec <= after.offset_sec - offset ? before : after;
}

export function traceSegments(
  samples: ActivityDetailSample[],
  metric: TraceKey,
  start: number,
  end: number,
): ActivityDetailSample[][] {
  const segments: ActivityDetailSample[][] = [];
  let current: ActivityDetailSample[] = [];
  for (const point of samples) {
    if (point.offset_sec < start || point.offset_sec > end) continue;
    if (point[metric] == null) {
      if (current.length) segments.push(current);
      current = [];
      continue;
    }
    if (point[`${metric}_break`] && current.length) {
      segments.push(current);
      current = [];
    }
    current.push(point);
  }
  if (current.length) segments.push(current);
  return segments;
}

export function traceDomain(segments: ActivityDetailSample[][], metric: TraceKey): [number, number] {
  const values = segments.flatMap((segment) => segment.map((point) => point[metric]).filter(
    (value): value is number => value != null,
  ));
  if (!values.length) return [0, 1];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const padding = Math.max((high - low) * 0.12, metric === 'pace_sec_km' ? 5 : 3);
  return [metric === 'altitude_m' || metric === 'grade_pct' || metric === 'temperature_c'
    ? low - padding : Math.max(0, low - padding), high + padding];
}
