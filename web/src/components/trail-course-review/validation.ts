import {
  TRAIL_EDITABLE_SECTION_KEYS,
  TRAIL_MODULE_KEYS,
  TRAIL_REASON_CODES,
  TRAIL_SCHEMA_IDS,
  type TrailDraftResponse,
  type TrailDeleteResponse,
  type TrailReadinessResponse,
} from '../../types/trail-plan.ts';

const SHA256_PATTERN = /^sha256:[0-9a-f]{64}$/;
const ABSENT_TRAIL_PLAN_REVISION = 'sha256:8adaaec35fb1a6ff05f212e69fc57c9e41bceaa30b65b95a8b3f90120ef5a321';
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const STATUS_PRECEDENCE = [
  'validation_failed',
  'policy_unavailable',
  'readiness_blocked',
  'clarification_required',
  'eligible_proposal',
] as const;
const EXPECTED_METADATA = {
  policy_version: 'non-ultra-trail-plan-generation-policy-v2',
  generator_version: 'non-ultra-trail-deterministic-generator-v2',
  science_decision_id: 'sdr-non-ultra-trail-plan-generation-policy-v2',
  contract_digest: 'sha256:1952421299cb59ddfea00115b6824d3116bd6e5f9175741916aa6f1015f8f9f9',
  source_decision_digest: 'sha256:9e4eef184a94d3f646b9483b569a4751ab2a9939ac509e55b888af6548c888fe',
  ontology_version: 'trail-course-demand-v2',
  ontology_decision_id: 'sdr-trail-running-goal-ontology-v2',
  ontology_contract_digest: 'sha256:0d3e4056e081e07bb52cbda15fc161ff9584a50f25f97f39fd513e1dad404c9c',
  ontology_source_decision_digest: 'sha256:363d5970c2ad6f7d4a18ced426d4a2996aef3ff116e6a6b112232c9eccaeeca1',
  course_schema_id: TRAIL_SCHEMA_IDS.course,
  constraint_schema_id: TRAIL_SCHEMA_IDS.constraints,
  contract_runtime_state: 'inactive',
} as const;
const READINESS_KEYS = [
  ...Object.keys(EXPECTED_METADATA),
  'inactive_dry_run',
  'status',
  'detail_reason',
  'matching_reasons',
  'module_availability',
  'limited_modules',
  'deterministic_input_hash',
  'readiness_receipt_digest',
  'revision_bindings',
  'plan',
  'history_statistics',
] as const;
const HISTORY_NUMBER_KEYS = [
  'usable_completed_weeks',
  'recent_modal_running_frequency',
  'recent_median_usable_weekly_minutes',
  'recent_maximum_usable_weekly_minutes',
  'recent_maximum_session_minutes',
  'recent_median_usable_weekly_ascent_meters',
  'recent_maximum_usable_weekly_ascent_meters',
  'recent_median_usable_weekly_descent_meters',
  'recent_maximum_usable_weekly_descent_meters',
  'recent_maximum_session_ascent_meters',
  'recent_maximum_session_descent_meters',
  'comparable_ascent_sessions_within_window',
  'comparable_descent_sessions_within_window',
] as const;
const HISTORY_DATE_KEYS = [
  'latest_run_date',
  'latest_comparable_ascent_session_date',
  'latest_comparable_descent_session_date',
  'observation_window_start',
  'observation_window_end',
] as const;
const FOOTING = new Set([
  'firm_smooth',
  'loose_gravel',
  'mud',
  'rocks_or_roots',
  'built_steps',
  'water_crossing',
]);
const PROVENANCE = new Set([
  'athlete_stated',
  'course_verified',
  'history_observed',
  'model_inferred',
  'explicit_assumption',
  'unknown',
]);
const ENVELOPE_KEYS = new Set([
  'state',
  'provenance',
  'source_revision',
  'value',
  'source_timestamp',
  'model_version',
  'assumption_confirmed_revision',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isRealIsoDate(value: unknown): value is string {
  if (typeof value !== 'string' || !ISO_DATE_PATTERN.test(value)) return false;
  const [year, month, day] = value.split('-').map(Number);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  return year >= 1 && year <= 9999
    && month >= 1
    && month <= 12
    && day >= 1
    && daysInMonth !== undefined
    && day <= daysInMonth;
}

function isoDayDifference(later: string, earlier: string): number {
  return (Date.parse(`${later}T00:00:00Z`) - Date.parse(`${earlier}T00:00:00Z`))
    / 86_400_000;
}

function isTimezoneAwareIsoTimestamp(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-](\d{2}):(\d{2}))$/.exec(value);
  if (!match || !isRealIsoDate(match[1])) return false;
  const hour = Number(match[2]);
  const minute = Number(match[3]);
  const second = Number(match[4]);
  if (hour > 23 || minute > 59 || second > 59) return false;
  if (match[5] !== 'Z') {
    const offsetHour = Number(match[6]);
    const offsetMinute = Number(match[7]);
    if (offsetHour > 23 || offsetMinute > 59) return false;
  }
  return true;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  return actual.length === wanted.length
    && actual.every((key, index) => key === wanted[index]);
}

function isInteger(value: unknown, minimum: number, maximum: number): boolean {
  return Number.isInteger(value) && Number(value) >= minimum && Number(value) <= maximum;
}

function isFiniteNumber(value: unknown, minimum: number, maximum: number): boolean {
  return typeof value === 'number'
    && Number.isFinite(value)
    && value >= minimum
    && value <= maximum;
}

function isClosedString(value: unknown, allowed: readonly string[]): boolean {
  return typeof value === 'string' && allowed.includes(value);
}

function isClosedSet(
  value: unknown,
  allowed: ReadonlySet<string>,
  allowEmpty: boolean,
): boolean {
  return Array.isArray(value)
    && (allowEmpty || value.length > 0)
    && new Set(value).size === value.length
    && value.every((item) => typeof item === 'string' && allowed.has(item));
}

function isServerEnvelope(
  value: unknown,
  knownValue: (candidate: unknown) => boolean,
): boolean {
  if (!isRecord(value)
    || Object.keys(value).some((key) => !ENVELOPE_KEYS.has(key))
    || (value.state !== 'known' && value.state !== 'unknown')
    || typeof value.provenance !== 'string'
    || !PROVENANCE.has(value.provenance)
    || typeof value.source_revision !== 'string'
    || !SHA256_PATTERN.test(value.source_revision)) return false;
  if (value.source_timestamp !== undefined && !isTimezoneAwareIsoTimestamp(value.source_timestamp)) {
    return false;
  }
  if (value.model_version !== undefined
    && (typeof value.model_version !== 'string'
      || value.model_version.length === 0
      || value.model_version.length > 128)) return false;
  if (value.assumption_confirmed_revision !== undefined
    && (typeof value.assumption_confirmed_revision !== 'string'
      || !SHA256_PATTERN.test(value.assumption_confirmed_revision))) return false;
  if (value.state === 'unknown' && value.provenance !== 'unknown') return false;
  if (value.state === 'known' && value.provenance === 'unknown') return false;
  if (value.provenance === 'model_inferred'
    && (typeof value.model_version !== 'string' || value.model_version.length === 0)) {
    return false;
  }
  return value.state === 'known'
    ? Object.hasOwn(value, 'value') && knownValue(value.value)
    : !Object.hasOwn(value, 'value');
}

function isOptionalContext(value: unknown): boolean {
  if (!isRecord(value) || !hasExactKeys(value, ['environment', 'support', 'fueling'])
    || !isRecord(value.environment)
    || !hasExactKeys(value.environment, [
      'maximum_altitude_m',
      'temperature_min_c',
      'temperature_max_c',
      'humidity_min_pct',
      'humidity_max_pct',
      'sun_exposure',
      'wind_exposure',
      'conditions_basis',
    ])
    || !isRecord(value.support)
    || !hasExactKeys(value.support, [
      'aid_support_mode',
      'aid_station_count',
      'max_aid_station_gap_m',
      'water_availability',
      'food_availability',
      'mandatory_gear',
    ])
    || !isRecord(value.fueling)
    || !hasExactKeys(value.fueling, [
      'longest_practiced_duration_min',
      'practice_sessions_last_42_days',
      'intake_form',
      'gastrointestinal_experience',
    ])) return false;
  const environment = value.environment;
  const support = value.support;
  const fueling = value.fueling;
  if (isRecord(environment.temperature_min_c)
    && isRecord(environment.temperature_max_c)
    && environment.temperature_min_c.state === 'known'
    && environment.temperature_max_c.state === 'known'
    && Number(environment.temperature_min_c.value) > Number(environment.temperature_max_c.value)) {
    return false;
  }
  if (isRecord(environment.humidity_min_pct)
    && isRecord(environment.humidity_max_pct)
    && environment.humidity_min_pct.state === 'known'
    && environment.humidity_max_pct.state === 'known'
    && Number(environment.humidity_min_pct.value) > Number(environment.humidity_max_pct.value)) {
    return false;
  }
  if (isRecord(environment.conditions_basis)
    && environment.conditions_basis.state === 'known') {
    const isAssumption = environment.conditions_basis.value === 'athlete_assumption';
    if (isAssumption !== (environment.conditions_basis.provenance === 'explicit_assumption')) {
      return false;
    }
  }
  return isServerEnvelope(environment.maximum_altitude_m, (item) => isInteger(item, -500, 9000))
    && isServerEnvelope(environment.temperature_min_c, (item) => isFiniteNumber(item, -30, 55))
    && isServerEnvelope(environment.temperature_max_c, (item) => isFiniteNumber(item, -30, 55))
    && isServerEnvelope(environment.humidity_min_pct, (item) => isFiniteNumber(item, 0, 100))
    && isServerEnvelope(environment.humidity_max_pct, (item) => isFiniteNumber(item, 0, 100))
    && isServerEnvelope(environment.sun_exposure, (item) => isClosedString(item, ['low', 'mixed', 'high']))
    && isServerEnvelope(environment.wind_exposure, (item) => isClosedString(item, ['sheltered', 'mixed', 'exposed']))
    && isServerEnvelope(environment.conditions_basis, (item) => isClosedString(item, [
      'organizer_information',
      'seasonal_expectation',
      'athlete_assumption',
    ]))
    && isServerEnvelope(support.aid_support_mode, (item) => isClosedString(item, [
      'organized_aid',
      'mixed',
      'self_supported',
    ]))
    && isServerEnvelope(support.aid_station_count, (item) => isInteger(item, 0, 50))
    && isServerEnvelope(support.max_aid_station_gap_m, (item) => item === null || isInteger(item, 100, 50000))
    && isServerEnvelope(support.water_availability, (item) => isClosedString(item, ['none', 'some_stations', 'all_stations']))
    && isServerEnvelope(support.food_availability, (item) => isClosedString(item, ['none', 'some_stations', 'all_stations']))
    && isServerEnvelope(support.mandatory_gear, (item) => isClosedSet(item, new Set([
      'water_carry',
      'food_carry',
      'weather_shell',
      'lighting',
      'navigation_device',
      'other_required',
    ]), true))
    && isServerEnvelope(fueling.longest_practiced_duration_min, (item) => isInteger(item, 0, 1440))
    && isServerEnvelope(fueling.practice_sessions_last_42_days, (item) => isInteger(item, 0, 84))
    && isServerEnvelope(fueling.intake_form, (item) => isClosedString(item, [
      'none',
      'fluids_only',
      'carbohydrate_drink',
      'mixed_food_and_drink',
    ]))
    && isServerEnvelope(fueling.gastrointestinal_experience, (item) => isClosedString(item, [
      'no_plan_altering_issue',
      'plan_altering_issue',
    ]));
}

function isCurrentDraft(value: Record<string, unknown>): boolean {
  const allowedRootKeys = new Set([
    'state',
    'namespace_version',
    'course_demand',
    'constraints',
    'revision_bindings',
    'composite_revision',
    'reset_is_erasure',
  ]);
  if (Object.keys(value).some((key) => !allowedRootKeys.has(key))
    || value.state !== 'current'
    || value.namespace_version !== 1
    || typeof value.composite_revision !== 'string'
    || !SHA256_PATTERN.test(value.composite_revision)
    || (value.reset_is_erasure !== undefined && value.reset_is_erasure !== false)
    || !isRevisionBindings(value.revision_bindings, value.composite_revision)
    || !isRecord(value.course_demand)
    || !hasExactKeys(value.course_demand, ['schema_id', 'event_id', 'fields'])
    || value.course_demand.schema_id !== TRAIL_SCHEMA_IDS.course
    || typeof value.course_demand.event_id !== 'string'
    || value.course_demand.event_id.length === 0
    || value.course_demand.event_id.length > 128
    || !isRecord(value.course_demand.fields)
    || !hasExactKeys(value.course_demand.fields, [
      'event_date',
      'distance_meters',
      'total_ascent_m',
      'total_descent_m',
      'planning_duration_range',
      'event_format',
      'distance_family',
      'planning_intent',
      'grade_distribution',
      'course_footing',
      'hands_assist',
      'fixed_rope',
      'optional_context',
    ])) return false;
  const fields = value.course_demand.fields;
  const grade = (item: unknown) => isRecord(item)
    && hasExactKeys(item, [
      'below_neg_10',
      'neg_10_to_below_neg_3',
      'neg_3_to_below_pos_3',
      'pos_3_to_below_pos_10',
      'pos_10_and_above',
    ])
    && Object.values(item).every((share) => isInteger(share, 0, 10000))
    && Object.values(item).reduce<number>((sum, share) => sum + Number(share), 0) === 10000;
  const duration = (item: unknown) => isRecord(item)
    && hasExactKeys(item, ['minimum_min', 'maximum_min'])
    && isInteger(item.minimum_min, 1, 1440)
    && isInteger(item.maximum_min, 1, 1440)
    && Number(item.minimum_min) < Number(item.maximum_min);
  if (!isServerEnvelope(fields.event_date, isRealIsoDate)
    || !isServerEnvelope(fields.distance_meters, (item) => isInteger(item, 1, 49999))
    || !isServerEnvelope(fields.total_ascent_m, (item) => isInteger(item, 0, 20000))
    || !isServerEnvelope(fields.total_descent_m, (item) => isInteger(item, 0, 20000))
    || !isServerEnvelope(fields.planning_duration_range, duration)
    || !isServerEnvelope(fields.event_format, (item) => isClosedString(item, ['single_day', 'multi_day']))
    || !isServerEnvelope(fields.distance_family, (item) => isClosedString(item, ['non_ultra', 'ultra']))
    || !isServerEnvelope(fields.planning_intent, (item) => isClosedString(item, [
      'performance',
      'first_completion',
      'return_to_consistency',
    ]))
    || !isServerEnvelope(fields.grade_distribution, grade)
    || !isServerEnvelope(fields.course_footing, (item) => isClosedSet(item, FOOTING, false))
    || !isServerEnvelope(fields.hands_assist, (item) => typeof item === 'boolean')
    || !isServerEnvelope(fields.fixed_rope, (item) => typeof item === 'boolean')
    || !isOptionalContext(fields.optional_context)
    || !isRecord(value.constraints)
    || !hasExactKeys(value.constraints, [
      'schema_id',
      'available_weekdays',
      'weekly_time_limit_min',
      'maximum_session_duration_min',
      'unavailable_dates',
      'preferred_longest_weekday',
      'nontechnical_three_minute_uphill_access',
      'controlled_downhill_access',
      'accessible_footing',
      'adult_nonclinical_scope_confirmed',
      'performance_intent_confirmed',
      'current_symptom_stop',
    ])
    || value.constraints.schema_id !== TRAIL_SCHEMA_IDS.constraints) return false;
  if (isRecord(fields.grade_distribution)
    && fields.grade_distribution.state === 'known'
    && !['athlete_stated', 'course_verified'].includes(String(fields.grade_distribution.provenance))) {
    return false;
  }
  const constraints = value.constraints;
  if (isRecord(constraints.weekly_time_limit_min)
    && isRecord(constraints.maximum_session_duration_min)
    && constraints.weekly_time_limit_min.state === 'known'
    && constraints.maximum_session_duration_min.state === 'known'
    && Number(constraints.maximum_session_duration_min.value)
      > Number(constraints.weekly_time_limit_min.value)) return false;
  if (constraints.preferred_longest_weekday !== null
    && isRecord(constraints.available_weekdays)
    && constraints.available_weekdays.state === 'known'
    && (!Array.isArray(constraints.available_weekdays.value)
      || !constraints.available_weekdays.value.includes(constraints.preferred_longest_weekday))) {
    return false;
  }
  return isServerEnvelope(constraints.available_weekdays, (item) => Array.isArray(item)
      && item.length > 0
      && new Set(item).size === item.length
      && item.every((day) => isInteger(day, 1, 7))
      && item.every((day, index) => index === 0 || Number(item[index - 1]) < Number(day)))
    && isServerEnvelope(constraints.weekly_time_limit_min, (item) => isInteger(item, 1, 10080))
    && isServerEnvelope(constraints.maximum_session_duration_min, (item) => isInteger(item, 1, 1440))
    && isServerEnvelope(constraints.unavailable_dates, (item) => Array.isArray(item)
      && item.length <= 14
      && new Set(item).size === item.length
      && item.every(isRealIsoDate)
      && item.every((date, index) => index === 0 || String(item[index - 1]) < String(date)))
    && (constraints.preferred_longest_weekday === null
      || isInteger(constraints.preferred_longest_weekday, 1, 7))
    && isServerEnvelope(constraints.nontechnical_three_minute_uphill_access, (item) => typeof item === 'boolean')
    && isServerEnvelope(constraints.controlled_downhill_access, (item) => typeof item === 'boolean')
    && isServerEnvelope(constraints.accessible_footing, (item) => isClosedSet(item, FOOTING, false))
    && isServerEnvelope(constraints.adult_nonclinical_scope_confirmed, (item) => typeof item === 'boolean')
    && isServerEnvelope(constraints.performance_intent_confirmed, (item) => typeof item === 'boolean')
    && isServerEnvelope(constraints.current_symptom_stop, (item) => typeof item === 'boolean');
}

export function parseTrailDraftResponse(value: unknown): TrailDraftResponse | null {
  if (!isRecord(value) || typeof value.composite_revision !== 'string'
    || !SHA256_PATTERN.test(value.composite_revision)) return null;
  if (value.state === 'absent') {
    return hasExactKeys(value, ['state', 'composite_revision'])
      ? value as unknown as TrailDraftResponse
      : null;
  }
  if (value.state === 'unknown_schema') {
    return hasExactKeys(value, ['state', 'namespace', 'composite_revision'])
      ? value as unknown as TrailDraftResponse
      : null;
  }
  return value.state === 'current' && isCurrentDraft(value)
    ? value as unknown as TrailDraftResponse
    : null;
}

export function parseTrailDeleteResponse(value: unknown): TrailDeleteResponse | null {
  if (!isRecord(value)
    || !hasExactKeys(value, ['status', 'composite_revision'])
    || (value.status !== 'deleted' && value.status !== 'absent')
    || value.composite_revision !== ABSENT_TRAIL_PLAN_REVISION) return null;
  return value as unknown as TrailDeleteResponse;
}

function isRevisionBindings(value: unknown, expectedComposite: string): boolean {
  if (!isRecord(value) || !hasExactKeys(value, [
    'course_revision',
    'planning_context_revision',
    'history_revision',
    'composite_revision',
    'section_confirmations',
  ])) return false;
  if (value.composite_revision !== expectedComposite) return false;
  for (const key of [
    'course_revision',
    'planning_context_revision',
    'history_revision',
    'composite_revision',
  ]) {
    if (typeof value[key] !== 'string' || !SHA256_PATTERN.test(value[key])) return false;
  }
  if (!Array.isArray(value.section_confirmations)) return false;
  const seen = new Set<string>();
  for (const item of value.section_confirmations) {
    if (!isRecord(item) || !hasExactKeys(item, [
      'section_key',
      'current_revision',
      'confirmed_revision',
    ])) return false;
    if (!(TRAIL_EDITABLE_SECTION_KEYS as readonly string[]).includes(String(item.section_key))) {
      return false;
    }
    if (seen.has(String(item.section_key))) return false;
    seen.add(String(item.section_key));
    if (typeof item.current_revision !== 'string' || !SHA256_PATTERN.test(item.current_revision)) {
      return false;
    }
    if (item.confirmed_revision !== null
      && (typeof item.confirmed_revision !== 'string'
        || !SHA256_PATTERN.test(item.confirmed_revision))) return false;
  }
  return seen.size === TRAIL_EDITABLE_SECTION_KEYS.length;
}

function isHistoryStatistics(value: unknown): boolean {
  if (!isRecord(value) || !hasExactKeys(value, [
    ...HISTORY_NUMBER_KEYS,
    ...HISTORY_DATE_KEYS,
    'recently_observed_footing',
    'source_revision_fingerprint',
    'evaluator_schema_id',
  ])) return false;
  for (const key of HISTORY_NUMBER_KEYS) {
    if (!Number.isInteger(value[key]) || Number(value[key]) < 0) return false;
  }
  if (Number(value.usable_completed_weeks) > 8) return false;
  for (const key of HISTORY_DATE_KEYS) {
    if (value[key] !== null
      && !isRealIsoDate(value[key])) return false;
  }
  if (!Array.isArray(value.recently_observed_footing)) return false;
  const footing = value.recently_observed_footing;
  if (new Set(footing).size !== footing.length
    || footing.some((item) => typeof item !== 'string' || !FOOTING.has(item))) return false;
  if (value.evaluator_schema_id !== 'trail-running-history-statistics-v2') return false;
  const start = value.observation_window_start;
  const end = value.observation_window_end;
  if (typeof start !== 'string' || typeof end !== 'string') return false;
  const observationDays = isoDayDifference(end, start);
  if (!Number.isInteger(observationDays)
    || observationDays < 55
    || observationDays > 61) return false;
  if (typeof start === 'string' && typeof end === 'string') {
    for (const dateKey of [
      'latest_run_date',
      'latest_comparable_ascent_session_date',
      'latest_comparable_descent_session_date',
    ]) {
      const date = value[dateKey];
      if (typeof date === 'string' && (date < start || date > end)) return false;
    }
    for (const dateKey of [
      'latest_comparable_ascent_session_date',
      'latest_comparable_descent_session_date',
    ]) {
      const date = value[dateKey];
      if (typeof date === 'string') {
        const completedDaysBeforeEnd = isoDayDifference(end, date);
        if (!Number.isInteger(completedDaysBeforeEnd)
          || completedDaysBeforeEnd < 0
          || completedDaysBeforeEnd > 41) return false;
      }
    }
  }
  if ((Number(value.comparable_ascent_sessions_within_window) === 0)
    !== (value.latest_comparable_ascent_session_date === null)) return false;
  if ((Number(value.comparable_descent_sessions_within_window) === 0)
    !== (value.latest_comparable_descent_session_date === null)) return false;
  if (Number(value.recent_median_usable_weekly_minutes)
      > Number(value.recent_maximum_usable_weekly_minutes)
    || Number(value.recent_maximum_session_minutes)
      > Number(value.recent_maximum_usable_weekly_minutes)
    || Number(value.recent_median_usable_weekly_ascent_meters)
      > Number(value.recent_maximum_usable_weekly_ascent_meters)
    || Number(value.recent_maximum_session_ascent_meters)
      > Number(value.recent_maximum_usable_weekly_ascent_meters)
    || Number(value.recent_median_usable_weekly_descent_meters)
      > Number(value.recent_maximum_usable_weekly_descent_meters)
    || Number(value.recent_maximum_session_descent_meters)
      > Number(value.recent_maximum_usable_weekly_descent_meters)) return false;
  return typeof value.source_revision_fingerprint === 'string'
    && SHA256_PATTERN.test(value.source_revision_fingerprint)
    && typeof value.evaluator_schema_id === 'string';
}

export function parseTrailReadinessResponse(
  value: unknown,
  expectedCompositeRevision: string,
): TrailReadinessResponse | null {
  if (!SHA256_PATTERN.test(expectedCompositeRevision)
    || !isRecord(value)
    || !hasExactKeys(value, ['draft', 'readiness'])
    || !isRecord(value.readiness)
    || !hasExactKeys(value.readiness, READINESS_KEYS)) return null;
  const draft = parseTrailDraftResponse(value.draft);
  if (!draft || draft.state !== 'current'
    || draft.composite_revision !== expectedCompositeRevision) return null;

  const readiness = value.readiness;
  for (const [key, expected] of Object.entries(EXPECTED_METADATA)) {
    if (readiness[key] !== expected) return null;
  }
  if (readiness.inactive_dry_run !== false || readiness.plan !== null) return null;
  if (typeof readiness.deterministic_input_hash !== 'string'
    || !SHA256_PATTERN.test(readiness.deterministic_input_hash)
    || typeof readiness.readiness_receipt_digest !== 'string'
    || !SHA256_PATTERN.test(readiness.readiness_receipt_digest)
    || !isRevisionBindings(readiness.revision_bindings, expectedCompositeRevision)
    || !isHistoryStatistics(readiness.history_statistics)) return null;
  const draftBindings = draft.revision_bindings as unknown as Record<string, unknown>;
  const readinessBindings = readiness.revision_bindings as Record<string, unknown>;
  for (const key of [
    'course_revision',
    'planning_context_revision',
    'history_revision',
    'composite_revision',
  ]) {
    if (draftBindings[key] !== readinessBindings[key]) return null;
  }
  if (JSON.stringify(draftBindings.section_confirmations)
    !== JSON.stringify(readinessBindings.section_confirmations)) return null;
  if (!(readinessBindings.section_confirmations as unknown[]).every((item) =>
    isRecord(item) && item.confirmed_revision === item.current_revision)) return null;
  const conditionsBasis = draft.course_demand.fields.optional_context.environment.conditions_basis;
  if (conditionsBasis.provenance === 'explicit_assumption'
    && conditionsBasis.assumption_confirmed_revision !== conditionsBasis.source_revision) {
    return null;
  }

  if (typeof readiness.status !== 'string'
    || !(STATUS_PRECEDENCE as readonly string[]).includes(readiness.status)) return null;
  const status = readiness.status;
  if (status !== 'policy_unavailable'
    || readiness.detail_reason !== 'policy_inactive') return null;
  const matching = readiness.matching_reasons;
  if (!Array.isArray(matching)) return null;
  const codes: string[] = [];
  for (const reason of matching) {
    if (!isRecord(reason)
      || !hasExactKeys(reason, ['status', 'detail_reason'])
      || typeof reason.status !== 'string'
      || typeof reason.detail_reason !== 'string') return null;
    const code = `${reason.status}.${reason.detail_reason}`;
    if (!(TRAIL_REASON_CODES as readonly string[]).includes(code)) return null;
    codes.push(code);
  }
  if (new Set(codes).size !== codes.length) return null;
  const indexes = codes.map((code) => (TRAIL_REASON_CODES as readonly string[]).indexOf(code));
  if (indexes.some((index, position) => position > 0 && index <= indexes[position - 1])) {
    return null;
  }

  if (typeof readiness.detail_reason !== 'string') return null;
  const primaryReason = `${status}.${readiness.detail_reason}`;
  if (!(TRAIL_REASON_CODES as readonly string[]).includes(primaryReason)
    || codes[0] !== primaryReason) return null;

  const history = readiness.history_statistics as Record<string, unknown>;
  const historyEnd = String(history.observation_window_end);
  const requiredHistoryReasons: string[] = [];
  const latestRun = history.latest_run_date;
  const insufficientRecentRunning = Number(history.usable_completed_weeks) < 4
    || typeof latestRun !== 'string'
    || isoDayDifference(historyEnd, latestRun) > 9;
  if (insufficientRecentRunning) {
    requiredHistoryReasons.push('readiness_blocked.insufficient_recent_running_history');
  }
  const latestAscent = history.latest_comparable_ascent_session_date;
  const courseFooting = draft.course_demand.fields.course_footing;
  const observedFooting = history.recently_observed_footing as string[];
  const footingMismatch = courseFooting.state === 'known'
    && courseFooting.value.some((footing) => !observedFooting.includes(footing));
  const insufficientComparableHistory = Number(history.comparable_ascent_sessions_within_window) < 2
    || typeof latestAscent !== 'string'
    || isoDayDifference(historyEnd, latestAscent) > 20
    || footingMismatch;
  if (insufficientComparableHistory) {
    requiredHistoryReasons.push('readiness_blocked.insufficient_comparable_trail_history');
  }
  const latestDescent = history.latest_comparable_descent_session_date;
  const insufficientDescentHistory = Number(history.comparable_descent_sessions_within_window) < 2
    || typeof latestDescent !== 'string'
    || isoDayDifference(historyEnd, latestDescent) > 20;
  if (insufficientDescentHistory) {
    requiredHistoryReasons.push('readiness_blocked.insufficient_descent_history');
  }
  if (requiredHistoryReasons.some((reason) => !codes.includes(reason))) return null;
  if (codes.includes('readiness_blocked.insufficient_recent_running_history')
    !== insufficientRecentRunning) return null;
  if (codes.includes('readiness_blocked.insufficient_comparable_trail_history')
    !== insufficientComparableHistory) return null;
  if (codes.includes('readiness_blocked.insufficient_descent_history')
    !== insufficientDescentHistory) return null;

  if (!Array.isArray(readiness.module_availability)
    || readiness.module_availability.length !== TRAIL_MODULE_KEYS.length) return null;
  for (const [index, module] of readiness.module_availability.entries()) {
    if (!isRecord(module)
      || !hasExactKeys(module, ['module', 'state', 'reason_target'])
      || module.module !== TRAIL_MODULE_KEYS[index]
      || !['not_evaluated', 'available', 'limited'].includes(String(module.state))) return null;
    if (module.state !== 'not_evaluated'
      || module.reason_target !== primaryReason) return null;
  }

  if (!Array.isArray(readiness.limited_modules)
    || readiness.limited_modules.some((item) => typeof item !== 'string')) return null;
  if (readiness.limited_modules.length !== 0) return null;
  return value as unknown as TrailReadinessResponse;
}
