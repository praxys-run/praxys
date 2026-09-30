import type { Activity, ActivityDetailResponse } from '@/types/api';
import { availableTraces } from './activity-trace';

export function knownRecordSource(source: string | null | undefined): string | null {
  switch (source?.trim().toLowerCase()) {
    case 'garmin': return 'Garmin';
    case 'stryd': return 'Stryd';
    case 'oura': return 'Oura';
    case 'strava': return 'Strava';
    case 'coros': return 'COROS';
    case 'garmin_activity_weather': return 'Garmin activity weather';
    case 'stryd_activity_weather': return 'Stryd activity weather';
    default: return null;
  }
}

export function heroSummaryKeys(activity: Activity): string[] {
  return ['distance_km', 'duration_sec', 'avg_pace_min_km',
    activity.avg_power != null && activity.avg_power > 0 ? 'avg_power' : 'avg_hr'];
}

export function hasRecordedGaps(detail: ActivityDetailResponse): boolean {
  if (detail.activity.sample_coverage.state === 'partial') return true;
  return availableTraces(detail.samples).some((metric) => detail.samples.some((sample, index) =>
    sample[metric] == null || (index > 0 && sample[`${metric}_break`])));
}
