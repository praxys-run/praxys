import type { ReactNode } from 'react';
import {
  TRAIL_REASON_CODES,
  TRAIL_SCHEMA_IDS,
  type TrailClientEnvelope,
  type TrailCurrentDraft,
  type TrailDraftRequest,
  type TrailDraftResponse,
  type TrailEditableSectionKey,
  type TrailFixedFieldTarget,
  type TrailFocusTarget,
  type TrailProvenance,
  type TrailReasonCode,
  type TrailSectionKey,
  type TrailServerEnvelope,
} from '@/types/trail-plan';
import {
  decimalEnvelopeFromExplicitInput,
  durationEnvelopeFromExplicitInputs,
  gradeEnvelopeFromExplicitInputs,
  integerEnvelopeFromExplicitInput,
  known,
  metresEnvelopeFromExplicitKilometres,
  unknown,
} from './transitions';
import { parseTrailDraftResponse } from './validation';

export { known, parseGradeBasisPoints, unknown } from './transitions';

export const GRADE_KEYS = [
  'below_neg_10',
  'neg_10_to_below_neg_3',
  'neg_3_to_below_pos_3',
  'pos_3_to_below_pos_10',
  'pos_10_and_above',
] as const;

export const REVISION_PATTERN = /^sha256:[0-9a-f]{64}$/;

export const SECTION_ELEMENT_IDS: Record<TrailSectionKey, string> = {
  'section.event-duration': 'trail-section-event-duration',
  'section.grade-footing': 'trail-section-grade-footing',
  'section.training-access': 'trail-section-training-access',
  'section.recent-experience': 'trail-section-recent-experience',
  'section.optional-context': 'trail-section-optional-context',
  'section.policy-receipt': 'trail-policy-receipt',
};

export const FIELD_ELEMENT_IDS: Record<TrailFixedFieldTarget, string> = {
  'field.event-date': 'trail-event-date',
  'field.event-scope': 'trail-event-format',
  'field.adult-performance-scope': 'trail-adult-scope',
  'field.symptom-stop': 'trail-symptom-stop',
  'field.history-running': 'trail-history-running',
  'field.history-comparable-trail': 'trail-history-ascent',
  'field.history-descent': 'trail-history-descent',
};

export const FIELD_TARGET_SECTIONS: Record<TrailFixedFieldTarget, TrailSectionKey> = {
  'field.event-date': 'section.event-duration',
  'field.event-scope': 'section.event-duration',
  'field.adult-performance-scope': 'section.training-access',
  'field.symptom-stop': 'section.training-access',
  'field.history-running': 'section.recent-experience',
  'field.history-comparable-trail': 'section.recent-experience',
  'field.history-descent': 'section.recent-experience',
};

export const MODULE_LIMIT_TARGETS: Readonly<Record<string, TrailFocusTarget>> = {
  'course.grade_distribution': 'section.grade-footing',
  'course.course_footing': 'section.grade-footing',
  'course.optional_context.environment': 'section.optional-context',
  'course.optional_context.support': 'section.optional-context',
  'course.optional_context.fueling': 'section.optional-context',
};

export type GradeKey = (typeof GRADE_KEYS)[number];

export type NumericInputKey =
  | 'distanceKm'
  | 'totalAscentM'
  | 'totalDescentM'
  | 'planningMinimumHours'
  | 'planningMinimumMinutes'
  | 'planningMaximumHours'
  | 'planningMaximumMinutes'
  | 'gradeBelowNeg10'
  | 'gradeNeg10ToNeg3'
  | 'gradeNearLevel'
  | 'gradePos3ToPos10'
  | 'gradePos10AndAbove'
  | 'weeklyHours'
  | 'weeklyMinutes'
  | 'sessionHours'
  | 'sessionMinutes'
  | 'maximumAltitudeM'
  | 'temperatureMinimumC'
  | 'temperatureMaximumC'
  | 'humidityMinimumPct'
  | 'humidityMaximumPct'
  | 'aidStationCount'
  | 'aidStationGapKm'
  | 'fuelingHours'
  | 'fuelingMinutes'
  | 'fuelingSessions';

export type NumericInputs = Record<NumericInputKey, string>;

export type OpenSections = Record<TrailSectionKey, boolean>;

export type OptionalGroup = 'environment' | 'support' | 'fueling';

export interface ValidationIssue {
  id: string;
  target: TrailFocusTarget;
  section: TrailEditableSectionKey;
}
export interface ReasonCopy {
  finding: string;
  effect: string;
  target: TrailFocusTarget;
  action: string;
}

export interface Option<T extends string | number> {
  value: T;
  label: string;
}


export const EMPTY_NUMERIC_INPUTS: NumericInputs = {
  distanceKm: '',
  totalAscentM: '',
  totalDescentM: '',
  planningMinimumHours: '',
  planningMinimumMinutes: '',
  planningMaximumHours: '',
  planningMaximumMinutes: '',
  gradeBelowNeg10: '',
  gradeNeg10ToNeg3: '',
  gradeNearLevel: '',
  gradePos3ToPos10: '',
  gradePos10AndAbove: '',
  weeklyHours: '',
  weeklyMinutes: '',
  sessionHours: '',
  sessionMinutes: '',
  maximumAltitudeM: '',
  temperatureMinimumC: '',
  temperatureMaximumC: '',
  humidityMinimumPct: '',
  humidityMaximumPct: '',
  aidStationCount: '',
  aidStationGapKm: '',
  fuelingHours: '',
  fuelingMinutes: '',
  fuelingSessions: '',
};

export function projectEnvelope<T>(
  envelope: TrailServerEnvelope<T>,
): TrailClientEnvelope<T> {
  return envelope.state === 'known' ? known(envelope.value) : unknown<T>();
}

export function emptyDraftRequest(): TrailDraftRequest {
  return {
    course_demand: {
      schema_id: TRAIL_SCHEMA_IDS.course,
      fields: {
        event_date: unknown(),
        distance_meters: unknown(),
        total_ascent_m: unknown(),
        total_descent_m: unknown(),
        planning_duration_range: unknown(),
        event_format: unknown(),
        distance_family: unknown(),
        planning_intent: unknown(),
        grade_distribution: unknown(),
        course_footing: unknown(),
        hands_assist: unknown(),
        fixed_rope: unknown(),
        optional_context: {
          environment: {
            maximum_altitude_m: unknown(),
            temperature_min_c: unknown(),
            temperature_max_c: unknown(),
            humidity_min_pct: unknown(),
            humidity_max_pct: unknown(),
            sun_exposure: unknown(),
            wind_exposure: unknown(),
            conditions_basis: unknown(),
          },
          support: {
            aid_support_mode: unknown(),
            aid_station_count: unknown(),
            max_aid_station_gap_m: unknown(),
            water_availability: unknown(),
            food_availability: unknown(),
            mandatory_gear: unknown(),
          },
          fueling: {
            longest_practiced_duration_min: unknown(),
            practice_sessions_last_42_days: unknown(),
            intake_form: unknown(),
            gastrointestinal_experience: unknown(),
          },
        },
      },
    },
    constraints: {
      schema_id: TRAIL_SCHEMA_IDS.constraints,
      available_weekdays: unknown(),
      weekly_time_limit_min: unknown(),
      maximum_session_duration_min: unknown(),
      unavailable_dates: unknown(),
      nontechnical_three_minute_uphill_access: unknown(),
      controlled_downhill_access: unknown(),
      accessible_footing: unknown(),
      adult_nonclinical_scope_confirmed: unknown(),
      performance_intent_confirmed: unknown(),
      current_symptom_stop: unknown(),
    },
  };
}

export function requestFromDraft(draft: TrailDraftResponse): TrailDraftRequest {
  if (draft.state !== 'current') return emptyDraftRequest();
  const fields = draft.course_demand.fields;
  const constraints = draft.constraints;
  return {
    course_demand: {
      schema_id: TRAIL_SCHEMA_IDS.course,
      fields: {
        event_date: projectEnvelope(fields.event_date),
        distance_meters: projectEnvelope(fields.distance_meters),
        total_ascent_m: projectEnvelope(fields.total_ascent_m),
        total_descent_m: projectEnvelope(fields.total_descent_m),
        planning_duration_range: projectEnvelope(fields.planning_duration_range),
        event_format: projectEnvelope(fields.event_format),
        distance_family: projectEnvelope(fields.distance_family),
        planning_intent: projectEnvelope(fields.planning_intent),
        grade_distribution: projectEnvelope(fields.grade_distribution),
        course_footing: projectEnvelope(fields.course_footing),
        hands_assist: projectEnvelope(fields.hands_assist),
        fixed_rope: projectEnvelope(fields.fixed_rope),
        optional_context: {
          environment: {
            maximum_altitude_m: projectEnvelope(
              fields.optional_context.environment.maximum_altitude_m,
            ),
            temperature_min_c: projectEnvelope(
              fields.optional_context.environment.temperature_min_c,
            ),
            temperature_max_c: projectEnvelope(
              fields.optional_context.environment.temperature_max_c,
            ),
            humidity_min_pct: projectEnvelope(
              fields.optional_context.environment.humidity_min_pct,
            ),
            humidity_max_pct: projectEnvelope(
              fields.optional_context.environment.humidity_max_pct,
            ),
            sun_exposure: projectEnvelope(
              fields.optional_context.environment.sun_exposure,
            ),
            wind_exposure: projectEnvelope(
              fields.optional_context.environment.wind_exposure,
            ),
            conditions_basis: projectEnvelope(
              fields.optional_context.environment.conditions_basis,
            ),
          },
          support: {
            aid_support_mode: projectEnvelope(
              fields.optional_context.support.aid_support_mode,
            ),
            aid_station_count: projectEnvelope(
              fields.optional_context.support.aid_station_count,
            ),
            max_aid_station_gap_m: projectEnvelope(
              fields.optional_context.support.max_aid_station_gap_m,
            ),
            water_availability: projectEnvelope(
              fields.optional_context.support.water_availability,
            ),
            food_availability: projectEnvelope(
              fields.optional_context.support.food_availability,
            ),
            mandatory_gear: projectEnvelope(
              fields.optional_context.support.mandatory_gear,
            ),
          },
          fueling: {
            longest_practiced_duration_min: projectEnvelope(
              fields.optional_context.fueling.longest_practiced_duration_min,
            ),
            practice_sessions_last_42_days: projectEnvelope(
              fields.optional_context.fueling.practice_sessions_last_42_days,
            ),
            intake_form: projectEnvelope(
              fields.optional_context.fueling.intake_form,
            ),
            gastrointestinal_experience: projectEnvelope(
              fields.optional_context.fueling.gastrointestinal_experience,
            ),
          },
        },
      },
    },
    constraints: {
      schema_id: TRAIL_SCHEMA_IDS.constraints,
      available_weekdays: projectEnvelope(constraints.available_weekdays),
      weekly_time_limit_min: projectEnvelope(constraints.weekly_time_limit_min),
      maximum_session_duration_min: projectEnvelope(
        constraints.maximum_session_duration_min,
      ),
      unavailable_dates: projectEnvelope(constraints.unavailable_dates),
      ...(constraints.preferred_longest_weekday === null
        ? {}
        : { preferred_longest_weekday: constraints.preferred_longest_weekday }),
      nontechnical_three_minute_uphill_access: projectEnvelope(
        constraints.nontechnical_three_minute_uphill_access,
      ),
      controlled_downhill_access: projectEnvelope(
        constraints.controlled_downhill_access,
      ),
      accessible_footing: projectEnvelope(constraints.accessible_footing),
      adult_nonclinical_scope_confirmed: projectEnvelope(
        constraints.adult_nonclinical_scope_confirmed,
      ),
      performance_intent_confirmed: projectEnvelope(
        constraints.performance_intent_confirmed,
      ),
      current_symptom_stop: projectEnvelope(constraints.current_symptom_stop),
    },
  };
}

function decimalText(value: number): string {
  return Number.isFinite(value) ? String(value) : '';
}

function meterKilometreText(value: number): string {
  return decimalText(value / 1000);
}

function durationParts(value: number): readonly [string, string] {
  return [String(Math.floor(value / 60)), String(value % 60)] as const;
}

export function numericInputsFromDraft(draft: TrailDraftResponse): NumericInputs {
  if (draft.state !== 'current') return { ...EMPTY_NUMERIC_INPUTS };
  const fields = draft.course_demand.fields;
  const constraints = draft.constraints;
  const optional = fields.optional_context;
  const duration = fields.planning_duration_range.state === 'known'
    ? fields.planning_duration_range.value
    : null;
  const minimumDuration = duration
    ? durationParts(duration.minimum_min)
    : ['', ''] as const;
  const maximumDuration = duration
    ? durationParts(duration.maximum_min)
    : ['', ''] as const;
  const weekly = constraints.weekly_time_limit_min.state === 'known'
    ? durationParts(constraints.weekly_time_limit_min.value)
    : ['', ''] as const;
  const session = constraints.maximum_session_duration_min.state === 'known'
    ? durationParts(constraints.maximum_session_duration_min.value)
    : ['', ''] as const;
  const fueling = optional.fueling.longest_practiced_duration_min.state === 'known'
    ? durationParts(optional.fueling.longest_practiced_duration_min.value)
    : ['', ''] as const;
  const grade = fields.grade_distribution.state === 'known'
    ? fields.grade_distribution.value
    : null;
  return {
    distanceKm: fields.distance_meters.state === 'known'
      ? meterKilometreText(fields.distance_meters.value)
      : '',
    totalAscentM: fields.total_ascent_m.state === 'known'
      ? String(fields.total_ascent_m.value)
      : '',
    totalDescentM: fields.total_descent_m.state === 'known'
      ? String(fields.total_descent_m.value)
      : '',
    planningMinimumHours: minimumDuration[0],
    planningMinimumMinutes: minimumDuration[1],
    planningMaximumHours: maximumDuration[0],
    planningMaximumMinutes: maximumDuration[1],
    gradeBelowNeg10: grade ? decimalText(grade.below_neg_10 / 100) : '',
    gradeNeg10ToNeg3: grade
      ? decimalText(grade.neg_10_to_below_neg_3 / 100)
      : '',
    gradeNearLevel: grade
      ? decimalText(grade.neg_3_to_below_pos_3 / 100)
      : '',
    gradePos3ToPos10: grade
      ? decimalText(grade.pos_3_to_below_pos_10 / 100)
      : '',
    gradePos10AndAbove: grade
      ? decimalText(grade.pos_10_and_above / 100)
      : '',
    weeklyHours: weekly[0],
    weeklyMinutes: weekly[1],
    sessionHours: session[0],
    sessionMinutes: session[1],
    maximumAltitudeM: optional.environment.maximum_altitude_m.state === 'known'
      ? String(optional.environment.maximum_altitude_m.value)
      : '',
    temperatureMinimumC: optional.environment.temperature_min_c.state === 'known'
      ? decimalText(optional.environment.temperature_min_c.value)
      : '',
    temperatureMaximumC: optional.environment.temperature_max_c.state === 'known'
      ? decimalText(optional.environment.temperature_max_c.value)
      : '',
    humidityMinimumPct: optional.environment.humidity_min_pct.state === 'known'
      ? decimalText(optional.environment.humidity_min_pct.value)
      : '',
    humidityMaximumPct: optional.environment.humidity_max_pct.state === 'known'
      ? decimalText(optional.environment.humidity_max_pct.value)
      : '',
    aidStationCount: optional.support.aid_station_count.state === 'known'
      ? String(optional.support.aid_station_count.value)
      : '',
    aidStationGapKm:
      optional.support.max_aid_station_gap_m.state === 'known'
      && optional.support.max_aid_station_gap_m.value !== null
        ? meterKilometreText(optional.support.max_aid_station_gap_m.value)
        : '',
    fuelingHours: fueling[0],
    fuelingMinutes: fueling[1],
    fuelingSessions:
      optional.fueling.practice_sessions_last_42_days.state === 'known'
        ? String(optional.fueling.practice_sessions_last_42_days.value)
        : '',
  };
}

function cloneDraftRequest(request: TrailDraftRequest): TrailDraftRequest {
  const optional = request.course_demand.fields.optional_context;
  return {
    course_demand: {
      ...request.course_demand,
      fields: {
        ...request.course_demand.fields,
        optional_context: {
          environment: { ...optional.environment },
          support: { ...optional.support },
          fueling: { ...optional.fueling },
        },
      },
    },
    constraints: { ...request.constraints },
  };
}

export function buildValidatedRequest(
  request: TrailDraftRequest,
  inputs: NumericInputs,
): { request: TrailDraftRequest; issues: ValidationIssue[] } {
  const next = cloneDraftRequest(request);
  const fields = next.course_demand.fields;
  const constraints = next.constraints;
  const optional = fields.optional_context;
  const issues: ValidationIssue[] = [];
  const add = (
    id: string,
    target: TrailFocusTarget,
    section: TrailEditableSectionKey,
  ) => issues.push({ id, target, section });

  if (fields.event_date.state === 'known'
    && !/^\d{4}-\d{2}-\d{2}$/.test(fields.event_date.value)) {
    add('event-date', 'field.event-date', 'section.event-duration');
  }

  if (fields.distance_meters.state === 'known' || inputs.distanceKm !== '') {
    const value = metresEnvelopeFromExplicitKilometres(inputs.distanceKm, 1, 49999);
    if (value.state === 'unknown') add('distance', 'section.event-duration', 'section.event-duration');
    else fields.distance_meters = value;
  }
  if (fields.total_ascent_m.state === 'known' || inputs.totalAscentM !== '') {
    const value = integerEnvelopeFromExplicitInput(inputs.totalAscentM, 0, 20000);
    if (value.state === 'unknown') add('ascent', 'section.event-duration', 'section.event-duration');
    else fields.total_ascent_m = value;
  }
  if (fields.total_descent_m.state === 'known' || inputs.totalDescentM !== '') {
    const value = integerEnvelopeFromExplicitInput(inputs.totalDescentM, 0, 20000);
    if (value.state === 'unknown') add('descent', 'section.event-duration', 'section.event-duration');
    else fields.total_descent_m = value;
  }
  if (fields.planning_duration_range.state === 'known' || [
    inputs.planningMinimumHours,
    inputs.planningMinimumMinutes,
    inputs.planningMaximumHours,
    inputs.planningMaximumMinutes,
  ].some((value) => value !== '')) {
    const minimum = durationEnvelopeFromExplicitInputs(
      inputs.planningMinimumHours,
      inputs.planningMinimumMinutes,
      1,
      1440,
    );
    const maximum = durationEnvelopeFromExplicitInputs(
      inputs.planningMaximumHours,
      inputs.planningMaximumMinutes,
      1,
      1440,
    );
    if (minimum.state === 'unknown'
      || maximum.state === 'unknown'
      || minimum.value >= maximum.value) {
      add('planning-duration', 'section.event-duration', 'section.event-duration');
    } else {
      fields.planning_duration_range = known({
        minimum_min: minimum.value,
        maximum_min: maximum.value,
      });
    }
  }

  const rawGrade = [
    inputs.gradeBelowNeg10,
    inputs.gradeNeg10ToNeg3,
    inputs.gradeNearLevel,
    inputs.gradePos3ToPos10,
    inputs.gradePos10AndAbove,
  ] as const;
  if (fields.grade_distribution.state === 'known'
    || rawGrade.some((value) => value !== '')) {
    const grade = gradeEnvelopeFromExplicitInputs(rawGrade);
    if (grade.state === 'unknown') {
      add('grade-distribution', 'section.grade-footing', 'section.grade-footing');
    } else {
      fields.grade_distribution = grade;
    }
  }
  if (fields.course_footing.state === 'known' && fields.course_footing.value.length === 0) {
    add('course-footing', 'section.grade-footing', 'section.grade-footing');
  }

  let weekly: number | null = null;
  if (constraints.weekly_time_limit_min.state === 'known'
    || inputs.weeklyHours !== ''
    || inputs.weeklyMinutes !== '') {
    const value = durationEnvelopeFromExplicitInputs(
      inputs.weeklyHours,
      inputs.weeklyMinutes,
      1,
      10080,
    );
    if (value.state === 'unknown') {
      add('weekly-time', 'section.training-access', 'section.training-access');
    } else {
      weekly = value.value;
      constraints.weekly_time_limit_min = value;
    }
  }
  if (constraints.maximum_session_duration_min.state === 'known'
    || inputs.sessionHours !== ''
    || inputs.sessionMinutes !== '') {
    const session = durationEnvelopeFromExplicitInputs(
      inputs.sessionHours,
      inputs.sessionMinutes,
      1,
      1440,
    );
    if (session.state === 'unknown'
      || (weekly !== null && session.value > weekly)) {
      add('session-time', 'section.training-access', 'section.training-access');
    } else {
      constraints.maximum_session_duration_min = session;
    }
  }
  if (constraints.available_weekdays.state === 'known'
    && constraints.available_weekdays.value.length === 0) {
    add('available-days', 'section.training-access', 'section.training-access');
  }
  if (constraints.accessible_footing.state === 'known'
    && constraints.accessible_footing.value.length === 0) {
    add('accessible-footing', 'section.training-access', 'section.training-access');
  }
  if (
    constraints.preferred_longest_weekday !== undefined
    && constraints.available_weekdays.state === 'known'
    && !constraints.available_weekdays.value.includes(
      constraints.preferred_longest_weekday,
    )
  ) {
    add('preferred-day', 'section.training-access', 'section.training-access');
  }

  if (optional.environment.maximum_altitude_m.state === 'known'
    || inputs.maximumAltitudeM !== '') {
    const value = integerEnvelopeFromExplicitInput(inputs.maximumAltitudeM, -500, 9000);
    if (value.state === 'unknown') add('maximum-altitude', 'section.optional-context', 'section.optional-context');
    else optional.environment.maximum_altitude_m = value;
  }
  const decimalOptional = [
    ['temperatureMinimumC', 'temperature_min_c', -30, 55],
    ['temperatureMaximumC', 'temperature_max_c', -30, 55],
    ['humidityMinimumPct', 'humidity_min_pct', 0, 100],
    ['humidityMaximumPct', 'humidity_max_pct', 0, 100],
  ] as const;
  for (const [inputKey, fieldKey, minimum, maximum] of decimalOptional) {
    const envelope = optional.environment[fieldKey];
    if (envelope.state !== 'known' && inputs[inputKey] === '') continue;
    const value = decimalEnvelopeFromExplicitInput(inputs[inputKey], 2, minimum, maximum);
    if (value.state === 'unknown') add(fieldKey, 'section.optional-context', 'section.optional-context');
    else optional.environment[fieldKey] = value;
  }
  const temperatureMinimum = optional.environment.temperature_min_c;
  const temperatureMaximum = optional.environment.temperature_max_c;
  if (
    temperatureMinimum.state === 'known'
    && temperatureMaximum.state === 'known'
    && temperatureMinimum.value > temperatureMaximum.value
  ) {
    add('temperature-range', 'section.optional-context', 'section.optional-context');
  }
  const humidityMinimum = optional.environment.humidity_min_pct;
  const humidityMaximum = optional.environment.humidity_max_pct;
  if (
    humidityMinimum.state === 'known'
    && humidityMaximum.state === 'known'
    && humidityMinimum.value > humidityMaximum.value
  ) {
    add('humidity-range', 'section.optional-context', 'section.optional-context');
  }
  if (optional.support.aid_station_count.state === 'known'
    || inputs.aidStationCount !== '') {
    const value = integerEnvelopeFromExplicitInput(inputs.aidStationCount, 0, 50);
    if (value.state === 'unknown') add('aid-count', 'section.optional-context', 'section.optional-context');
    else optional.support.aid_station_count = value;
  }
  if (
    inputs.aidStationGapKm !== ''
    || (optional.support.max_aid_station_gap_m.state === 'known'
      && optional.support.max_aid_station_gap_m.value !== null)
  ) {
    const value = metresEnvelopeFromExplicitKilometres(inputs.aidStationGapKm, 100, 50000);
    if (value.state === 'unknown') add('aid-gap', 'section.optional-context', 'section.optional-context');
    else optional.support.max_aid_station_gap_m = value;
  }
  if (optional.fueling.longest_practiced_duration_min.state === 'known'
    || inputs.fuelingHours !== ''
    || inputs.fuelingMinutes !== '') {
    const value = durationEnvelopeFromExplicitInputs(
      inputs.fuelingHours,
      inputs.fuelingMinutes,
      0,
      1440,
    );
    if (value.state === 'unknown') add('fueling-duration', 'section.optional-context', 'section.optional-context');
    else optional.fueling.longest_practiced_duration_min = value;
  }
  if (optional.fueling.practice_sessions_last_42_days.state === 'known'
    || inputs.fuelingSessions !== '') {
    const value = integerEnvelopeFromExplicitInput(inputs.fuelingSessions, 0, 84);
    if (value.state === 'unknown') add('fueling-sessions', 'section.optional-context', 'section.optional-context');
    else optional.fueling.practice_sessions_last_42_days = value;
  }
  return { request: next, issues };
}


export type CourseFields = TrailDraftRequest['course_demand']['fields'];
export type CourseEnvelopeKey = Exclude<keyof CourseFields, 'optional_context'>;
export type ConstraintFields = TrailDraftRequest['constraints'];
export type ConstraintEnvelopeKey = Exclude<
  keyof ConstraintFields,
  'schema_id' | 'preferred_longest_weekday'
>;

export function replaceCourseField<K extends CourseEnvelopeKey>(
  request: TrailDraftRequest,
  key: K,
  value: CourseFields[K],
): TrailDraftRequest {
  return {
    ...request,
    course_demand: {
      ...request.course_demand,
      fields: {
        ...request.course_demand.fields,
        [key]: value,
      },
    },
  };
}

export function replaceConstraintField<K extends ConstraintEnvelopeKey>(
  request: TrailDraftRequest,
  key: K,
  value: ConstraintFields[K],
): TrailDraftRequest {
  return {
    ...request,
    constraints: {
      ...request.constraints,
      [key]: value,
    },
  };
}

export function replaceOptionalField(
  request: TrailDraftRequest,
  group: OptionalGroup,
  key: string,
  value: TrailClientEnvelope<unknown>,
): TrailDraftRequest {
  const optional = request.course_demand.fields.optional_context;
  const groupFields = optional[group] as unknown as Record<
    string,
    TrailClientEnvelope<unknown>
  >;
  return {
    ...request,
    course_demand: {
      ...request.course_demand,
      fields: {
        ...request.course_demand.fields,
        optional_context: {
          ...optional,
          [group]: {
            ...groupFields,
            [key]: value,
          },
        },
      },
    },
  } as TrailDraftRequest;
}

export function setOptionalGroupUnknown(
  request: TrailDraftRequest,
  group: OptionalGroup,
): TrailDraftRequest {
  const keys: Record<OptionalGroup, readonly string[]> = {
    environment: [
      'maximum_altitude_m',
      'temperature_min_c',
      'temperature_max_c',
      'humidity_min_pct',
      'humidity_max_pct',
      'sun_exposure',
      'wind_exposure',
      'conditions_basis',
    ],
    support: [
      'aid_support_mode',
      'aid_station_count',
      'max_aid_station_gap_m',
      'water_availability',
      'food_availability',
      'mandatory_gear',
    ],
    fueling: [
      'longest_practiced_duration_min',
      'practice_sessions_last_42_days',
      'intake_form',
      'gastrointestinal_experience',
    ],
  };
  return keys[group].reduce(
    (current, key) => replaceOptionalField(current, group, key, unknown()),
    request,
  );
}

export function sectionConfirmation(
  draft: TrailDraftResponse,
  sectionKey: TrailEditableSectionKey,
) {
  if (draft.state !== 'current') return null;
  return draft.revision_bindings.section_confirmations.find(
    (item) => item.section_key === sectionKey,
  ) ?? null;
}

export function currentDraftFromResponse(value: unknown): TrailCurrentDraft | null {
  const candidate = parseTrailDraftResponse(value);
  return candidate?.state === 'current' ? candidate : null;
}

export function reasonCodeOf(status: string, detailReason: string): TrailReasonCode | null {
  const candidate = `${status}.${detailReason}`;
  return (TRAIL_REASON_CODES as readonly string[]).includes(candidate)
    ? candidate as TrailReasonCode
    : null;
}

export function formatIsoDate(value: string | null, locale: string): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return '—';
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

export function localIsoDate(offsetDays = 0): string {
  const value = new Date();
  value.setHours(12, 0, 0, 0);
  value.setDate(value.getDate() + offsetDays);
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function provenanceMeta(
  envelope: TrailServerEnvelope<unknown> | null,
  labels: Record<TrailProvenance, string>,
  modelLabel: string,
): ReactNode {
  if (!envelope) return null;
  return (
    <span className="break-words">
      {labels[envelope.provenance]}
      {envelope.provenance === 'model_inferred' && envelope.model_version
        ? ` · ${modelLabel} ${envelope.model_version}`
        : ''}
    </span>
  );
}
