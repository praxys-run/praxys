export const TRAIL_API_ENDPOINTS = {
  draft: '/api/plan/trail/draft',
  confirm: '/api/plan/trail/confirm',
  reset: '/api/plan/trail/reset',
  readiness: '/api/plan/trail/readiness',
} as const;

export const TRAIL_SCHEMA_IDS = {
  course: 'trail_course_demand_v2',
  constraints: 'non_ultra_trail_constraints_v2',
} as const;

export const TRAIL_EDITABLE_SECTION_KEYS = [
  'section.event-duration',
  'section.grade-footing',
  'section.training-access',
  'section.optional-context',
] as const;

export const TRAIL_SECTION_KEYS = [
  ...TRAIL_EDITABLE_SECTION_KEYS.slice(0, 3),
  'section.recent-experience',
  'section.optional-context',
  'section.policy-receipt',
] as const;

export const TRAIL_MODULE_KEYS = [
  'grade_specificity',
  'technical_terrain',
  'environment_altitude',
  'fueling',
] as const;

export const TRAIL_REASON_CODES = [
  'validation_failed.invalid_field_value',
  'validation_failed.schema_version_mismatch',
  'validation_failed.deterministic_invariant_failed',
  'policy_unavailable.policy_inactive',
  'policy_unavailable.event_inside_unapproved_taper_window',
  'policy_unavailable.unsupported_ultra_or_multiday',
  'policy_unavailable.unsupported_population_or_intent',
  'policy_unavailable.technical_features_outside_v2',
  'readiness_blocked.insufficient_recent_running_history',
  'readiness_blocked.insufficient_comparable_trail_history',
  'readiness_blocked.insufficient_descent_history',
  'readiness_blocked.insufficient_terrain_access',
  'readiness_blocked.current_symptom_stop',
  'readiness_blocked.no_schedule_within_envelope',
  'clarification_required.material_course_demand_unknown',
  'clarification_required.assumption_confirmation_required',
  'clarification_required.adult_scope_or_constraints_unconfirmed',
  'clarification_required.training_constraints_missing',
  'clarification_required.training_constraints_outside_history_envelope',
  'clarification_required.stale_confirmation_or_source_revision',
  'clarification_required.contradictory_input',
] as const;

export type TrailEditableSectionKey =
  (typeof TRAIL_EDITABLE_SECTION_KEYS)[number];
export type TrailSectionKey = (typeof TRAIL_SECTION_KEYS)[number];
export type TrailModuleKey = (typeof TRAIL_MODULE_KEYS)[number];
export type TrailReasonCode = (typeof TRAIL_REASON_CODES)[number];

export type TrailProvenance =
  | 'athlete_stated'
  | 'course_verified'
  | 'history_observed'
  | 'model_inferred'
  | 'explicit_assumption'
  | 'unknown';

interface TrailServerEnvelopeMetadata {
  provenance: TrailProvenance;
  source_revision: string;
  source_timestamp?: string;
  model_version?: string;
  assumption_confirmed_revision?: string;
}

export type TrailServerEnvelope<T> =
  | (TrailServerEnvelopeMetadata & { state: 'known'; value: T })
  | (TrailServerEnvelopeMetadata & { state: 'unknown'; value?: never });

export type TrailClientEnvelope<T> =
  | { state: 'known'; value: T }
  | { state: 'unknown'; value?: never };

export type TrailEventFormat = 'single_day' | 'multi_day';
export type TrailDistanceFamily = 'non_ultra' | 'ultra';
export type TrailPlanningIntent =
  | 'performance'
  | 'first_completion'
  | 'return_to_consistency';
export type TrailFooting =
  | 'firm_smooth'
  | 'loose_gravel'
  | 'mud'
  | 'rocks_or_roots'
  | 'built_steps'
  | 'water_crossing';
export type TrailSunExposure = 'low' | 'mixed' | 'high';
export type TrailWindExposure = 'sheltered' | 'mixed' | 'exposed';
export type TrailConditionsBasis =
  | 'organizer_information'
  | 'seasonal_expectation'
  | 'athlete_assumption';
export type TrailAidSupportMode =
  | 'organized_aid'
  | 'mixed'
  | 'self_supported';
export type TrailAidAvailability = 'none' | 'some_stations' | 'all_stations';
export type TrailMandatoryGear =
  | 'water_carry'
  | 'food_carry'
  | 'weather_shell'
  | 'lighting'
  | 'navigation_device'
  | 'other_required';
export type TrailIntakeForm =
  | 'none'
  | 'fluids_only'
  | 'carbohydrate_drink'
  | 'mixed_food_and_drink';
export type TrailGastrointestinalExperience =
  | 'no_plan_altering_issue'
  | 'plan_altering_issue';

export interface TrailPlanningDurationRange {
  minimum_min: number;
  maximum_min: number;
}

export interface TrailGradeDistribution {
  below_neg_10: number;
  neg_10_to_below_neg_3: number;
  neg_3_to_below_pos_3: number;
  pos_3_to_below_pos_10: number;
  pos_10_and_above: number;
}

export interface TrailOptionalContext<TEnvelope> {
  environment: {
    maximum_altitude_m: TEnvelope;
    temperature_min_c: TEnvelope;
    temperature_max_c: TEnvelope;
    humidity_min_pct: TEnvelope;
    humidity_max_pct: TEnvelope;
    sun_exposure: TEnvelope;
    wind_exposure: TEnvelope;
    conditions_basis: TEnvelope;
  };
  support: {
    aid_support_mode: TEnvelope;
    aid_station_count: TEnvelope;
    max_aid_station_gap_m: TEnvelope;
    water_availability: TEnvelope;
    food_availability: TEnvelope;
    mandatory_gear: TEnvelope;
  };
  fueling: {
    longest_practiced_duration_min: TEnvelope;
    practice_sessions_last_42_days: TEnvelope;
    intake_form: TEnvelope;
    gastrointestinal_experience: TEnvelope;
  };
}

export interface TrailServerOptionalContext {
  environment: {
    maximum_altitude_m: TrailServerEnvelope<number>;
    temperature_min_c: TrailServerEnvelope<number>;
    temperature_max_c: TrailServerEnvelope<number>;
    humidity_min_pct: TrailServerEnvelope<number>;
    humidity_max_pct: TrailServerEnvelope<number>;
    sun_exposure: TrailServerEnvelope<TrailSunExposure>;
    wind_exposure: TrailServerEnvelope<TrailWindExposure>;
    conditions_basis: TrailServerEnvelope<TrailConditionsBasis>;
  };
  support: {
    aid_support_mode: TrailServerEnvelope<TrailAidSupportMode>;
    aid_station_count: TrailServerEnvelope<number>;
    max_aid_station_gap_m: TrailServerEnvelope<number | null>;
    water_availability: TrailServerEnvelope<TrailAidAvailability>;
    food_availability: TrailServerEnvelope<TrailAidAvailability>;
    mandatory_gear: TrailServerEnvelope<TrailMandatoryGear[]>;
  };
  fueling: {
    longest_practiced_duration_min: TrailServerEnvelope<number>;
    practice_sessions_last_42_days: TrailServerEnvelope<number>;
    intake_form: TrailServerEnvelope<TrailIntakeForm>;
    gastrointestinal_experience:
      TrailServerEnvelope<TrailGastrointestinalExperience>;
  };
}

export interface TrailClientOptionalContext {
  environment: {
    maximum_altitude_m: TrailClientEnvelope<number>;
    temperature_min_c: TrailClientEnvelope<number>;
    temperature_max_c: TrailClientEnvelope<number>;
    humidity_min_pct: TrailClientEnvelope<number>;
    humidity_max_pct: TrailClientEnvelope<number>;
    sun_exposure: TrailClientEnvelope<TrailSunExposure>;
    wind_exposure: TrailClientEnvelope<TrailWindExposure>;
    conditions_basis: TrailClientEnvelope<TrailConditionsBasis>;
  };
  support: {
    aid_support_mode: TrailClientEnvelope<TrailAidSupportMode>;
    aid_station_count: TrailClientEnvelope<number>;
    max_aid_station_gap_m: TrailClientEnvelope<number | null>;
    water_availability: TrailClientEnvelope<TrailAidAvailability>;
    food_availability: TrailClientEnvelope<TrailAidAvailability>;
    mandatory_gear: TrailClientEnvelope<TrailMandatoryGear[]>;
  };
  fueling: {
    longest_practiced_duration_min: TrailClientEnvelope<number>;
    practice_sessions_last_42_days: TrailClientEnvelope<number>;
    intake_form: TrailClientEnvelope<TrailIntakeForm>;
    gastrointestinal_experience:
      TrailClientEnvelope<TrailGastrointestinalExperience>;
  };
}

export interface TrailCourseDemandResponse {
  schema_id: typeof TRAIL_SCHEMA_IDS.course;
  event_id: string;
  fields: {
    event_date: TrailServerEnvelope<string>;
    distance_meters: TrailServerEnvelope<number>;
    total_ascent_m: TrailServerEnvelope<number>;
    total_descent_m: TrailServerEnvelope<number>;
    planning_duration_range:
      TrailServerEnvelope<TrailPlanningDurationRange>;
    event_format: TrailServerEnvelope<TrailEventFormat>;
    distance_family: TrailServerEnvelope<TrailDistanceFamily>;
    planning_intent: TrailServerEnvelope<TrailPlanningIntent>;
    grade_distribution: TrailServerEnvelope<TrailGradeDistribution>;
    course_footing: TrailServerEnvelope<TrailFooting[]>;
    hands_assist: TrailServerEnvelope<boolean>;
    fixed_rope: TrailServerEnvelope<boolean>;
    optional_context: TrailServerOptionalContext;
  };
}

export interface TrailConstraintsResponse {
  schema_id: typeof TRAIL_SCHEMA_IDS.constraints;
  available_weekdays: TrailServerEnvelope<number[]>;
  weekly_time_limit_min: TrailServerEnvelope<number>;
  maximum_session_duration_min: TrailServerEnvelope<number>;
  unavailable_dates: TrailServerEnvelope<string[]>;
  preferred_longest_weekday: number | null;
  nontechnical_three_minute_uphill_access: TrailServerEnvelope<boolean>;
  controlled_downhill_access: TrailServerEnvelope<boolean>;
  accessible_footing: TrailServerEnvelope<TrailFooting[]>;
  adult_nonclinical_scope_confirmed: TrailServerEnvelope<boolean>;
  performance_intent_confirmed: TrailServerEnvelope<boolean>;
  current_symptom_stop: TrailServerEnvelope<boolean>;
}

export interface TrailDraftRequest {
  course_demand: {
    schema_id: typeof TRAIL_SCHEMA_IDS.course;
    fields: {
      event_date: TrailClientEnvelope<string>;
      distance_meters: TrailClientEnvelope<number>;
      total_ascent_m: TrailClientEnvelope<number>;
      total_descent_m: TrailClientEnvelope<number>;
      planning_duration_range:
        TrailClientEnvelope<TrailPlanningDurationRange>;
      event_format: TrailClientEnvelope<TrailEventFormat>;
      distance_family: TrailClientEnvelope<TrailDistanceFamily>;
      planning_intent: TrailClientEnvelope<TrailPlanningIntent>;
      grade_distribution: TrailClientEnvelope<TrailGradeDistribution>;
      course_footing: TrailClientEnvelope<TrailFooting[]>;
      hands_assist: TrailClientEnvelope<boolean>;
      fixed_rope: TrailClientEnvelope<boolean>;
      optional_context: TrailClientOptionalContext;
    };
  };
  constraints: {
    schema_id: typeof TRAIL_SCHEMA_IDS.constraints;
    available_weekdays: TrailClientEnvelope<number[]>;
    weekly_time_limit_min: TrailClientEnvelope<number>;
    maximum_session_duration_min: TrailClientEnvelope<number>;
    unavailable_dates: TrailClientEnvelope<string[]>;
    preferred_longest_weekday?: number;
    nontechnical_three_minute_uphill_access: TrailClientEnvelope<boolean>;
    controlled_downhill_access: TrailClientEnvelope<boolean>;
    accessible_footing: TrailClientEnvelope<TrailFooting[]>;
    adult_nonclinical_scope_confirmed: TrailClientEnvelope<boolean>;
    performance_intent_confirmed: TrailClientEnvelope<boolean>;
    current_symptom_stop: TrailClientEnvelope<boolean>;
  };
}

export interface TrailSectionConfirmation {
  section_key: TrailEditableSectionKey;
  current_revision: string;
  confirmed_revision: string | null;
}

export interface TrailRevisionBindings {
  course_revision: string;
  planning_context_revision: string;
  history_revision: string;
  composite_revision: string;
  section_confirmations: TrailSectionConfirmation[];
}

export interface TrailCurrentDraft {
  state: 'current';
  namespace_version: 1;
  course_demand: TrailCourseDemandResponse;
  constraints: TrailConstraintsResponse;
  revision_bindings: TrailRevisionBindings;
  composite_revision: string;
  reset_is_erasure?: false;
}

export interface TrailAbsentDraft {
  state: 'absent';
  composite_revision: string;
}

export interface TrailUnknownSchemaDraft {
  state: 'unknown_schema';
  namespace: unknown;
  composite_revision: string;
}

export type TrailDraftResponse =
  | TrailCurrentDraft
  | TrailAbsentDraft
  | TrailUnknownSchemaDraft;

export type TrailReadinessStatus =
  | 'validation_failed'
  | 'policy_unavailable'
  | 'readiness_blocked'
  | 'clarification_required'
  | 'eligible_proposal';

type TrailMatchingReasonFromCode<T extends TrailReasonCode> =
  T extends `${infer TStatus}.${infer TDetail}`
    ? { status: TStatus; detail_reason: TDetail }
    : never;

export type TrailMatchingReason = TrailMatchingReasonFromCode<TrailReasonCode>;

export type TrailModuleReasonTarget =
  | TrailReasonCode
  | 'course.grade_distribution'
  | 'course.course_footing'
  | 'course.optional_context.environment'
  | 'course.optional_context.support'
  | 'course.optional_context.fueling';

export interface TrailModuleAvailability {
  module: TrailModuleKey;
  state: 'not_evaluated' | 'available' | 'limited';
  reason_target: TrailModuleReasonTarget | null;
}

export interface TrailHistoryStatistics {
  usable_completed_weeks: number;
  recent_modal_running_frequency: number;
  recent_median_usable_weekly_minutes: number;
  recent_maximum_usable_weekly_minutes: number;
  recent_maximum_session_minutes: number;
  recent_median_usable_weekly_ascent_meters: number;
  recent_maximum_usable_weekly_ascent_meters: number;
  recent_median_usable_weekly_descent_meters: number;
  recent_maximum_usable_weekly_descent_meters: number;
  recent_maximum_session_ascent_meters: number;
  recent_maximum_session_descent_meters: number;
  latest_run_date: string | null;
  comparable_ascent_sessions_within_window: number;
  latest_comparable_ascent_session_date: string | null;
  comparable_descent_sessions_within_window: number;
  latest_comparable_descent_session_date: string | null;
  recently_observed_footing: TrailFooting[];
  observation_window_start: string | null;
  observation_window_end: string | null;
  source_revision_fingerprint: string;
  evaluator_schema_id: string;
}

export interface TrailReadinessReceipt {
  policy_version: string;
  generator_version: string;
  science_decision_id: string;
  contract_digest: string;
  source_decision_digest: string;
  ontology_version: string;
  ontology_decision_id: string;
  ontology_contract_digest: string;
  ontology_source_decision_digest: string;
  course_schema_id: typeof TRAIL_SCHEMA_IDS.course;
  constraint_schema_id: typeof TRAIL_SCHEMA_IDS.constraints;
  contract_runtime_state: 'inactive';
  inactive_dry_run: false;
  status: TrailReadinessStatus;
  detail_reason: string | null;
  matching_reasons: TrailMatchingReason[];
  module_availability: TrailModuleAvailability[];
  limited_modules: TrailModuleKey[];
  deterministic_input_hash: string;
  readiness_receipt_digest: string;
  revision_bindings: TrailRevisionBindings | null;
  plan: null;
  history_statistics: TrailHistoryStatistics;
}

export interface TrailReadinessResponse {
  draft: TrailCurrentDraft;
  readiness: TrailReadinessReceipt;
}

export interface TrailDeleteResponse {
  status: 'deleted' | 'absent';
  composite_revision: string;
}

export type TrailFixedFieldTarget =
  | 'field.event-date'
  | 'field.event-scope'
  | 'field.adult-performance-scope'
  | 'field.symptom-stop'
  | 'field.history-running'
  | 'field.history-comparable-trail'
  | 'field.history-descent';

export type TrailGenericActionTarget =
  | 'action.first-invalid-field'
  | 'action.first-unknown-core-field'
  | 'action.first-unconfirmed-assumption'
  | 'action.first-missing-training-field'
  | 'action.first-conflicting-field'
  | 'action.first-confirmed-hazard'
  | 'action.first-stale-section'
  | 'action.reload-supported-version'
  | 'action.retry-readiness'
  | 'action.review-history-envelope';

export type TrailFocusTarget =
  | TrailSectionKey
  | TrailFixedFieldTarget
  | TrailGenericActionTarget;
