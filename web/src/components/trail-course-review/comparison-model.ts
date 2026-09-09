import type { TrailClientEnvelope, TrailDraftRequest, TrailDraftResponse } from '@/types/trail-plan';
import type { useTrailCourseReviewCopy } from './copy';
import {
  NUMERIC_INPUT_KEYS_BY_ENVELOPE,
  known,
  numericInputsFromDraft,
  reapplyPendingTrailEdits,
  requestFromDraft,
  type ConstraintEnvelopeKey,
  type CourseEnvelopeKey,
  type NumericInputs,
  type OptionalGroup,
} from './model';

export type ComparisonLabels = ReturnType<typeof useTrailCourseReviewCopy>;
type CopyKey = keyof ComparisonLabels['copy'];
type OptionalFields = TrailDraftRequest['course_demand']['fields']['optional_context'];
type OptionalFieldKey = {
  [Group in OptionalGroup]: `optional.${Group}.${keyof OptionalFields[Group] & string}`;
}[OptionalGroup];
export type ComparisonFieldKey =
  | `course.${CourseEnvelopeKey}`
  | `constraints.${ConstraintEnvelopeKey | 'preferred_longest_weekday'}`
  | OptionalFieldKey;
type OptionKey = keyof Pick<ComparisonLabels,
  | 'eventFormatOptions' | 'distanceFamilyOptions' | 'planningIntentOptions'
  | 'footingOptions' | 'weekdayOptions' | 'sunOptions' | 'windOptions'
  | 'conditionsOptions' | 'supportOptions' | 'availabilityOptions'
  | 'gearOptions' | 'intakeOptions' | 'gutOptions'>;
type Display =
  | { kind: 'number'; unit?: 'km' | 'm' | '°C' | '%' }
  | { kind: 'duration' | 'planning-range' | 'grade' | 'boolean' | 'date' | 'dates' }
  | { kind: 'choice'; options: OptionKey }
  | { kind: 'set'; options: OptionKey; emptyLabel?: 'noEquipment' };
export interface ComparisonFieldDefinition {
  label: CopyKey;
  display: Display;
  issues?: readonly string[];
}

// Closed, exhaustive editable-field projection in ledger order. Source metadata,
// identity, revision bindings and observed history are intentionally not fields.
export const TRAIL_COMPARISON_FIELDS = {
  'course.event_date': { label: 'eventDate', display: { kind: 'date' }, issues: ['event-date'] },
  'course.distance_meters': { label: 'raceDistance', display: { kind: 'number', unit: 'km' }, issues: ['distance'] },
  'course.total_ascent_m': { label: 'totalAscent', display: { kind: 'number', unit: 'm' }, issues: ['ascent'] },
  'course.total_descent_m': { label: 'totalDescent', display: { kind: 'number', unit: 'm' }, issues: ['descent'] },
  'course.planning_duration_range': { label: 'planningMinimum', display: { kind: 'planning-range' }, issues: ['planning-duration'] },
  'course.event_format': { label: 'eventFormat', display: { kind: 'choice', options: 'eventFormatOptions' } },
  'course.distance_family': { label: 'distanceCategory', display: { kind: 'choice', options: 'distanceFamilyOptions' } },
  'course.planning_intent': { label: 'planningGoal', display: { kind: 'choice', options: 'planningIntentOptions' } },
  'course.grade_distribution': { label: 'gradeDistribution', display: { kind: 'grade' }, issues: ['grade-distribution'] },
  'course.course_footing': { label: 'footing', display: { kind: 'set', options: 'footingOptions' }, issues: ['course-footing'] },
  'course.hands_assist': { label: 'hands', display: { kind: 'boolean' } },
  'course.fixed_rope': { label: 'rope', display: { kind: 'boolean' } },
  'constraints.available_weekdays': { label: 'availableDays', display: { kind: 'set', options: 'weekdayOptions' }, issues: ['available-days'] },
  'constraints.weekly_time_limit_min': { label: 'weeklyTime', display: { kind: 'duration' }, issues: ['weekly-time'] },
  'constraints.maximum_session_duration_min': { label: 'longestSession', display: { kind: 'duration' }, issues: ['session-time'] },
  'constraints.unavailable_dates': { label: 'unavailableDates', display: { kind: 'dates' } },
  'constraints.preferred_longest_weekday': { label: 'preferredDay', display: { kind: 'choice', options: 'weekdayOptions' }, issues: ['preferred-day'] },
  'constraints.nontechnical_three_minute_uphill_access': { label: 'uphillAccess', display: { kind: 'boolean' } },
  'constraints.controlled_downhill_access': { label: 'downhillAccess', display: { kind: 'boolean' } },
  'constraints.accessible_footing': { label: 'trainingFooting', display: { kind: 'set', options: 'footingOptions' }, issues: ['accessible-footing'] },
  'constraints.adult_nonclinical_scope_confirmed': { label: 'adultScope', display: { kind: 'boolean' } },
  'constraints.performance_intent_confirmed': { label: 'performanceScope', display: { kind: 'boolean' } },
  'constraints.current_symptom_stop': { label: 'symptoms', display: { kind: 'boolean' } },
  'optional.environment.maximum_altitude_m': { label: 'maximumAltitude', display: { kind: 'number', unit: 'm' }, issues: ['maximum-altitude'] },
  'optional.environment.temperature_min_c': { label: 'minimumTemperature', display: { kind: 'number', unit: '°C' }, issues: ['temperature_min_c', 'temperature-range'] },
  'optional.environment.temperature_max_c': { label: 'maximumTemperature', display: { kind: 'number', unit: '°C' }, issues: ['temperature_max_c', 'temperature-range'] },
  'optional.environment.humidity_min_pct': { label: 'minimumHumidity', display: { kind: 'number', unit: '%' }, issues: ['humidity_min_pct', 'humidity-range'] },
  'optional.environment.humidity_max_pct': { label: 'maximumHumidity', display: { kind: 'number', unit: '%' }, issues: ['humidity_max_pct', 'humidity-range'] },
  'optional.environment.sun_exposure': { label: 'sunExposure', display: { kind: 'choice', options: 'sunOptions' } },
  'optional.environment.wind_exposure': { label: 'windExposure', display: { kind: 'choice', options: 'windOptions' } },
  'optional.environment.conditions_basis': { label: 'conditionsBasis', display: { kind: 'choice', options: 'conditionsOptions' } },
  'optional.support.aid_support_mode': { label: 'supportSetup', display: { kind: 'choice', options: 'supportOptions' } },
  'optional.support.aid_station_count': { label: 'aidCount', display: { kind: 'number' }, issues: ['aid-count'] },
  'optional.support.max_aid_station_gap_m': { label: 'aidGap', display: { kind: 'number', unit: 'km' }, issues: ['aid-gap'] },
  'optional.support.water_availability': { label: 'water', display: { kind: 'choice', options: 'availabilityOptions' } },
  'optional.support.food_availability': { label: 'food', display: { kind: 'choice', options: 'availabilityOptions' } },
  'optional.support.mandatory_gear': { label: 'requiredEquipment', display: { kind: 'set', options: 'gearOptions', emptyLabel: 'noEquipment' } },
  'optional.fueling.longest_practiced_duration_min': { label: 'fuelingDuration', display: { kind: 'duration' }, issues: ['fueling-duration'] },
  'optional.fueling.practice_sessions_last_42_days': { label: 'fuelingSessions', display: { kind: 'number' }, issues: ['fueling-sessions'] },
  'optional.fueling.intake_form': { label: 'intake', display: { kind: 'choice', options: 'intakeOptions' } },
  'optional.fueling.gastrointestinal_experience': { label: 'gutIssue', display: { kind: 'choice', options: 'gutOptions' } },
} as const satisfies Record<ComparisonFieldKey, ComparisonFieldDefinition>;

/** Read only a closed editable field, never its server-owned source metadata. */
export function trailComparisonFieldValue(
  request: TrailDraftRequest,
  key: ComparisonFieldKey,
): TrailClientEnvelope<unknown> | undefined {
  if (key === 'constraints.preferred_longest_weekday') {
    const value = request.constraints.preferred_longest_weekday;
    return value === undefined ? undefined : known(value);
  }
  const [area, field, leaf] = key.split('.');
  if (area === 'course') return request.course_demand.fields[field as CourseEnvelopeKey];
  if (area === 'constraints') return request.constraints[field as ConstraintEnvelopeKey];
  const group = request.course_demand.fields.optional_context[field as OptionalGroup];
  return (group as Record<string, TrailClientEnvelope<unknown>>)[leaf];
}

export interface ComparisonSnapshot {
  request: TrailDraftRequest;
  numericInputs: NumericInputs;
}
interface ComparisonRow {
  key: ComparisonFieldKey;
  pending: boolean;
  changedOnServer: boolean;
}
interface TrailComparison {
  latest: ComparisonSnapshot;
  restored: ReturnType<typeof reapplyPendingTrailEdits>;
  rows: ComparisonRow[];
}

/** Project the local/server field union; the existing helper alone owns reapply. */
export function buildTrailComparison(
  baseDraft: TrailDraftResponse,
  pendingRequest: TrailDraftRequest,
  pendingInputs: NumericInputs,
  latestDraft: TrailDraftResponse | null,
): TrailComparison | null {
  if (!latestDraft || latestDraft.state === 'unknown_schema'
    || baseDraft.state === 'unknown_schema') return null;
  const baseRequest = requestFromDraft(baseDraft);
  const baseInputs = numericInputsFromDraft(baseDraft);
  const latest: ComparisonSnapshot = {
    request: requestFromDraft(latestDraft),
    numericInputs: numericInputsFromDraft(latestDraft),
  };
  const restored = reapplyPendingTrailEdits(baseDraft, pendingRequest, pendingInputs, latestDraft);
  const rows: ComparisonRow[] = [];
  for (const key of Object.keys(TRAIL_COMPARISON_FIELDS) as ComparisonFieldKey[]) {
    const baseValue = JSON.stringify(trailComparisonFieldValue(baseRequest, key));
    const pending = JSON.stringify(trailComparisonFieldValue(pendingRequest, key)) !== baseValue
      || (NUMERIC_INPUT_KEYS_BY_ENVELOPE[key] ?? [])
        .some((input) => pendingInputs[input] !== baseInputs[input]);
    const changedOnServer = JSON.stringify(trailComparisonFieldValue(latest.request, key)) !== baseValue;
    if (pending || changedOnServer) rows.push({ key, pending, changedOnServer });
  }
  return { latest, restored, rows };
}
