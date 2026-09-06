import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

import {
  TRAIL_API_ENDPOINTS,
  TRAIL_EDITABLE_SECTION_KEYS,
  TRAIL_MODULE_KEYS,
  TRAIL_REASON_CODES,
  TRAIL_SCHEMA_IDS,
  TRAIL_SECTION_KEYS,
} from '../src/types/trail-plan.ts';
import {
  applyUnknownIntent,
  decimalEnvelopeFromExplicitInput,
  durationEnvelopeFromExplicitInputs,
  gradeEnvelopeFromExplicitInputs,
  integerEnvelopeFromExplicitInput,
  known,
  metresEnvelopeFromExplicitKilometres,
  toggleEnvelopeMember,
  unknown,
} from '../src/components/trail-course-review/transitions.ts';
import {
  parseTrailDraftResponse,
  parseTrailDeleteResponse,
  parseTrailReadinessResponse,
} from '../src/components/trail-course-review/validation.ts';
import {
  INITIAL_PRIVATE_TRAIL_DRAFT_STATE,
  reducePrivateTrailDraftState,
} from '../src/components/trail-course-review/private-draft-state.ts';
import {
  TrailMutationResponseError,
  TrailTransportError,
  classifyTrailMutationFailure,
  preservesPendingTrailEdits,
  requestTrailMutation,
} from '../src/components/trail-course-review/mutation-error.ts';
import {
  EMPTY_NUMERIC_INPUTS,
  clearOptionalGroupNumericInputs,
  clearPlanningDurationNumericInputs,
  buildValidatedRequest,
  numericInputsFromDraft,
  reapplyPendingTrailEdits,
  requestFromDraft,
} from '../src/components/trail-course-review/model.ts';
import {
  bindTrailOwnerScopeInvalidation,
  isCurrentTrailOperation,
  runTrailConfirmationCallback,
} from '../src/components/trail-course-review/operation-fence.ts';
import { ApiTimeoutError } from '../src/lib/request-timeout.ts';
import { handleUnauthorizedSession } from '../src/lib/auth-session.ts';
import { tokenCacheScope } from '../src/lib/auth-cache-scope.ts';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

const TRAIL_IMPLEMENTATION_PATHS = [
  '../src/components/TrailCourseReview.tsx',
  '../src/components/trail-course-review/controls.tsx',
  '../src/components/trail-course-review/copy.tsx',
  '../src/components/trail-course-review/model.ts',
  '../src/components/trail-course-review/mutation-error.ts',
  '../src/components/trail-course-review/operation-fence.ts',
  '../src/components/trail-course-review/owner-export.ts',
  '../src/components/trail-course-review/private-draft-request.ts',
  '../src/components/trail-course-review/private-draft-state.ts',
  '../src/components/trail-course-review/states.tsx',
  '../src/components/trail-course-review/transitions.ts',
  '../src/components/trail-course-review/use-private-draft.ts',
  '../src/components/trail-course-review/validation.ts',
];

const readTrailImplementation = async () => (
  await Promise.all(TRAIL_IMPLEMENTATION_PATHS.map(read))
).join('\n');

const EXPECTED_REASONS = [
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
];

const SHA_A = `sha256:${'a'.repeat(64)}`;
const SHA_B = `sha256:${'b'.repeat(64)}`;
const SHA_C = `sha256:${'c'.repeat(64)}`;
const SHA_D = `sha256:${'d'.repeat(64)}`;
const SECTION_CONFIRMATIONS = TRAIL_EDITABLE_SECTION_KEYS.map((sectionKey) => ({
  section_key: sectionKey,
  current_revision: SHA_D,
  confirmed_revision: SHA_D,
}));
const REVISION_BINDINGS = {
  course_revision: SHA_A,
  planning_context_revision: SHA_B,
  history_revision: SHA_C,
  composite_revision: SHA_D,
  section_confirmations: SECTION_CONFIRMATIONS,
};

function inactiveReadinessResponse() {
  const unknownValue = () => ({
    state: 'unknown',
    provenance: 'unknown',
    source_revision: SHA_A,
  });
  return {
    draft: {
      state: 'current',
      namespace_version: 1,
      course_demand: {
        schema_id: TRAIL_SCHEMA_IDS.course,
        event_id: 'synthetic-event',
        fields: {
          event_date: unknownValue(),
          distance_meters: unknownValue(),
          total_ascent_m: unknownValue(),
          total_descent_m: unknownValue(),
          planning_duration_range: unknownValue(),
          event_format: unknownValue(),
          distance_family: unknownValue(),
          planning_intent: unknownValue(),
          grade_distribution: unknownValue(),
          course_footing: unknownValue(),
          hands_assist: unknownValue(),
          fixed_rope: unknownValue(),
          optional_context: {
            environment: {
              maximum_altitude_m: unknownValue(),
              temperature_min_c: unknownValue(),
              temperature_max_c: unknownValue(),
              humidity_min_pct: unknownValue(),
              humidity_max_pct: unknownValue(),
              sun_exposure: unknownValue(),
              wind_exposure: unknownValue(),
              conditions_basis: unknownValue(),
            },
            support: {
              aid_support_mode: unknownValue(),
              aid_station_count: unknownValue(),
              max_aid_station_gap_m: unknownValue(),
              water_availability: unknownValue(),
              food_availability: unknownValue(),
              mandatory_gear: unknownValue(),
            },
            fueling: {
              longest_practiced_duration_min: unknownValue(),
              practice_sessions_last_42_days: unknownValue(),
              intake_form: unknownValue(),
              gastrointestinal_experience: unknownValue(),
            },
          },
        },
      },
      constraints: {
        schema_id: TRAIL_SCHEMA_IDS.constraints,
        available_weekdays: unknownValue(),
        weekly_time_limit_min: unknownValue(),
        maximum_session_duration_min: unknownValue(),
        unavailable_dates: unknownValue(),
        preferred_longest_weekday: null,
        nontechnical_three_minute_uphill_access: unknownValue(),
        controlled_downhill_access: unknownValue(),
        accessible_footing: unknownValue(),
        adult_nonclinical_scope_confirmed: unknownValue(),
        performance_intent_confirmed: unknownValue(),
        current_symptom_stop: unknownValue(),
      },
      revision_bindings: structuredClone(REVISION_BINDINGS),
      composite_revision: SHA_D,
    },
    readiness: {
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
      inactive_dry_run: false,
      status: 'policy_unavailable',
      detail_reason: 'policy_inactive',
      matching_reasons: [{
        status: 'policy_unavailable',
        detail_reason: 'policy_inactive',
      }],
      module_availability: TRAIL_MODULE_KEYS.map((module) => ({
        module,
        state: 'not_evaluated',
        reason_target: 'policy_unavailable.policy_inactive',
      })),
      limited_modules: [],
      deterministic_input_hash: SHA_A,
      readiness_receipt_digest: SHA_B,
      revision_bindings: structuredClone(REVISION_BINDINGS),
      plan: null,
      history_statistics: {
        usable_completed_weeks: 4,
        recent_modal_running_frequency: 4,
        recent_median_usable_weekly_minutes: 180,
        recent_maximum_usable_weekly_minutes: 210,
        recent_maximum_session_minutes: 90,
        recent_median_usable_weekly_ascent_meters: 500,
        recent_maximum_usable_weekly_ascent_meters: 650,
        recent_median_usable_weekly_descent_meters: 500,
        recent_maximum_usable_weekly_descent_meters: 650,
        recent_maximum_session_ascent_meters: 300,
        recent_maximum_session_descent_meters: 300,
        latest_run_date: '2026-09-03',
        comparable_ascent_sessions_within_window: 2,
        latest_comparable_ascent_session_date: '2026-09-01',
        comparable_descent_sessions_within_window: 2,
        latest_comparable_descent_session_date: '2026-09-01',
        recently_observed_footing: ['firm_smooth'],
        observation_window_start: '2026-07-10',
        observation_window_end: '2026-09-03',
        source_revision_fingerprint: SHA_C,
        evaluator_schema_id: 'trail-running-history-statistics-v2',
      },
    },
  };
}

test('Trail constants close the inactive v2 API, section, module, and reason contracts', () => {
  assert.deepEqual(TRAIL_API_ENDPOINTS, {
    draft: '/api/plan/trail/draft',
    confirm: '/api/plan/trail/confirm',
    reset: '/api/plan/trail/reset',
    readiness: '/api/plan/trail/readiness',
  });
  assert.deepEqual(TRAIL_SCHEMA_IDS, {
    course: 'trail_course_demand_v2',
    constraints: 'non_ultra_trail_constraints_v2',
  });
  assert.deepEqual(TRAIL_EDITABLE_SECTION_KEYS, [
    'section.event-duration',
    'section.grade-footing',
    'section.training-access',
    'section.optional-context',
  ]);
  assert.deepEqual(TRAIL_SECTION_KEYS, [
    'section.event-duration',
    'section.grade-footing',
    'section.training-access',
    'section.recent-experience',
    'section.optional-context',
    'section.policy-receipt',
  ]);
  assert.deepEqual(TRAIL_MODULE_KEYS, [
    'grade_specificity',
    'technical_terrain',
    'environment_altitude',
    'fueling',
  ]);
  assert.deepEqual(TRAIL_REASON_CODES, EXPECTED_REASONS);
  assert.equal(new Set(TRAIL_REASON_CODES).size, 21);
});

test('the private implementation uses an isolated draft read and exact revision-fenced mutations', async () => {
  const [implementation, route] = await Promise.all([
    readTrailImplementation(),
    read('../../api/routes/trail_plan.py'),
  ]);

  assert.match(implementation, /usePrivateTrailDraft/);
  assert.match(implementation, /requestPrivateTrailDraft/);
  assert.match(implementation, /apiFetcher<unknown>/);
  assert.match(implementation, /method: 'PUT'/);
  assert.match(implementation, /method: 'POST'/);
  assert.match(implementation, /method: kind === 'reset' \? 'POST' : 'DELETE'/);
  assert.match(implementation, /'If-Match': serverDraft\.composite_revision/);
  assert.match(implementation, /'If-Match': draft\.composite_revision/);
  assert.match(implementation, /section_key: sectionKey/);
  assert.match(implementation, /section_revision: confirmation\.current_revision/);
  assert.match(implementation, /TRAIL_API_ENDPOINTS\.readiness/);
  assert.match(implementation, /createTrailOwnerExportAction/);
  assert.match(route, /@router\.get\("\/draft"/);
  assert.match(route, /@router\.post\("\/confirm"/);
  assert.match(route, /@router\.post\("\/reset"/);
  assert.match(route, /@router\.delete\("\/draft"/);
  assert.match(route, /@router\.post\("\/readiness"/);
  assert.doesNotMatch(implementation, /If-None-Match|If-Unmodified-Since/);
});

test('the Trail review remains unreachable and carries no provider or browser persistence surface', async () => {
  const [implementation, component, app, training, sidebar, registry, apiMain, miniapp] = await Promise.all([
    readTrailImplementation(),
    read('../src/components/TrailCourseReview.tsx'),
    read('../src/App.tsx'),
    read('../src/pages/Training.tsx'),
    read('../src/components/AppSidebar.tsx'),
    read('../src/components/platform-registry.ts'),
    read('../../api/main.py'),
    read('../../miniapp/app.json'),
  ]);

  for (const registeredSurface of [app, training, sidebar, registry, miniapp, apiMain]) {
    assert.doesNotMatch(
      registeredSurface,
      /TrailCourseReview|trail-course-review|trail\/course-review/,
    );
  }
  assert.doesNotMatch(apiMain, /include_router\([^\n]*trail_plan/);
  assert.match(component, /\.\/trail-course-review\/controls/);
  assert.match(component, /\.\/trail-course-review\/copy/);
  assert.match(component, /\.\/trail-course-review\/model/);
  assert.match(component, /\.\/trail-course-review\/states/);
  assert.match(component, /\.\/trail-course-review\/use-private-draft/);
  assert.match(component, /\.\/trail-course-review\/validation/);
  const sourcePaths = await readdir(new URL('../src/', import.meta.url), {
    recursive: true,
  });
  const otherSourceFiles = sourcePaths.filter((path) => {
    const normalized = path.replaceAll('\\', '/');
    return /\.[cm]?[jt]sx?$/.test(normalized)
      && normalized !== 'components/TrailCourseReview.tsx'
      && !normalized.startsWith('components/trail-course-review/');
  });
  for (const path of otherSourceFiles) {
    const source = await read(`../src/${path.replaceAll('\\', '/')}`);
    assert.doesNotMatch(
      source,
      /TrailCourseReview|components\/trail-course-review/,
      `${path} must not import or register the inactive Trail review`,
    );
  }
  assert.doesNotMatch(implementation, /localStorage|sessionStorage/);
  assert.doesNotMatch(implementation, /useApi<|useQuery|useQueryClient|queryKey/);
  assert.match(implementation, /controllerRef\.current\?\.abort\(\)/);
  assert.doesNotMatch(implementation, /dataRef/);
  assert.equal((component.match(/onReplaceRemote\(next\)/g) ?? []).length, 3);
  assert.match(component, /onClearRemote\(\);\s*await onRefetch\(\)/);
  assert.match(implementation, /onClearData\(\);\s*await onReload\(\)/);
  assert.doesNotMatch(implementation, /void on(?:Reload|Refetch)\(\);/);
  assert.match(implementation, /void onReload\(\)\.catch\(\(\) => undefined\)/);
  assert.match(implementation, /void onRefetch\(\)\.catch\(\(\) => undefined\)/);
  assert.doesNotMatch(implementation, /pushState|replaceState|location\.hash|URLSearchParams/);
  assert.doesNotMatch(implementation, /encodeURIComponent|\/plan\/trail\/\$\{/);
  assert.doesNotMatch(implementation, /garmin|provider|credential|tokenstore|consent/i);
  assert.doesNotMatch(implementation, /TRAIL_API_ENDPOINTS\.(?:send|schedule|reconcile|connect)/);
  assert.match(implementation, /window\.location\.assign\('\/training'\)/);
  assert.match(implementation, /href="\/goal"/);
});

test('unknown fields stay unknown until an explicit value is entered', async () => {
  const unknownEnum = unknown();
  assert.strictEqual(applyUnknownIntent(unknownEnum, false), unknownEnum);
  assert.deepEqual(applyUnknownIntent(known('single_day'), true), unknown());
  assert.deepEqual(
    toggleEnvelopeMember(unknown(), 'rocks_or_roots', false),
    known(['rocks_or_roots']),
  );
  assert.deepEqual(integerEnvelopeFromExplicitInput('', 0, 10), unknown());
  assert.deepEqual(integerEnvelopeFromExplicitInput('0', 0, 10), known(0));
  assert.deepEqual(decimalEnvelopeFromExplicitInput('1.', 2, 0, 10), unknown());
  assert.deepEqual(decimalEnvelopeFromExplicitInput('1.25', 2, 0, 10), known(1.25));
  assert.deepEqual(metresEnvelopeFromExplicitKilometres('', 100, 50000), unknown());
  assert.deepEqual(metresEnvelopeFromExplicitKilometres('0.1', 100, 50000), known(100));
  assert.deepEqual(durationEnvelopeFromExplicitInputs('1', '', 1, 1440), unknown());
  assert.deepEqual(durationEnvelopeFromExplicitInputs('1', '30', 1, 1440), known(90));
  assert.deepEqual(
    gradeEnvelopeFromExplicitInputs(['25', '', '', '', '']),
    unknown(),
    'one entered grade band must not synthesize zeroes for the other four',
  );
  assert.deepEqual(
    gradeEnvelopeFromExplicitInputs(['10', '15', '50', '15', '10']),
    known({
      below_neg_10: 1000,
      neg_10_to_below_neg_3: 1500,
      neg_3_to_below_pos_3: 5000,
      pos_3_to_below_pos_10: 1500,
      pos_10_and_above: 1000,
    }),
  );
  const controls = await read('../src/components/trail-course-review/controls.tsx');
  const component = await read('../src/components/TrailCourseReview.tsx');
  assert.doesNotMatch(controls, /options\[0\]/);
  assert.doesNotMatch(component, /neg_3_to_below_pos_3:\s*10000/);
  assert.doesNotMatch(component, /known\((?:0|1|100)\)|known\(\{\s*minimum_min/);
});

test('private draft state drops prior values on begin, failure, replacement, and clear', () => {
  const first = { state: 'absent', composite_revision: SHA_A };
  const second = { state: 'absent', composite_revision: SHA_B };
  const loaded = reducePrivateTrailDraftState(
    INITIAL_PRIVATE_TRAIL_DRAFT_STATE,
    { type: 'success', data: first },
  );
  assert.strictEqual(loaded.data, first);
  const begun = reducePrivateTrailDraftState(loaded, { type: 'begin' });
  assert.equal(begun.data, null);
  const failed = reducePrivateTrailDraftState(loaded, {
    type: 'failure',
    message: 'failed',
    status: 503,
  });
  assert.deepEqual(failed, {
    data: null,
    loading: false,
    error: 'failed',
    errorStatus: 503,
  });
  const replaced = reducePrivateTrailDraftState(loaded, {
    type: 'success',
    data: second,
  });
  assert.strictEqual(replaced.data, second);
  assert.notStrictEqual(replaced.data, first);
  assert.equal(reducePrivateTrailDraftState(loaded, { type: 'clear' }).data, null);
});

test('mutation failures preserve pending intent only for stale, typed transport, and actual 5xx', () => {
  const pending = reducePrivateTrailDraftState(
    INITIAL_PRIVATE_TRAIL_DRAFT_STATE,
    { type: 'success', data: { state: 'absent', composite_revision: SHA_A } },
  );
  const stale = new TrailMutationResponseError('stale', 412);
  assert.equal(stale.status, 412);
  assert.equal(preservesPendingTrailEdits(stale), true);
  const afterStale = preservesPendingTrailEdits(stale)
    ? pending
    : reducePrivateTrailDraftState(pending, {
        type: 'failure', message: stale.message, status: stale.status,
      });
  assert.strictEqual(afterStale.data, pending.data);

  const unavailable = new TrailMutationResponseError('unavailable', 503);
  assert.equal(preservesPendingTrailEdits(unavailable), true);
  const afterUnavailable = preservesPendingTrailEdits(unavailable)
    ? pending
    : reducePrivateTrailDraftState(pending, {
        type: 'failure', message: unavailable.message, status: unavailable.status,
      });
  assert.strictEqual(afterUnavailable.data, pending.data);

  assert.equal(classifyTrailMutationFailure(stale), 'stale');
  assert.equal(classifyTrailMutationFailure(unavailable), 'retryable');
  assert.equal(classifyTrailMutationFailure(new TrailTransportError()), 'retryable');
  for (const status of [401, 403, 404, 428, 400, 409, 422]) {
    const failure = new TrailMutationResponseError('closed', status);
    assert.equal(classifyTrailMutationFailure(failure), 'hard');
    assert.equal(preservesPendingTrailEdits(failure), false);
  }
  for (const unclassified of [
    new Error('generic'),
    new TypeError('not proof of transport'),
    new ApiTimeoutError(),
    { status: 503 },
    { message: 'Failed to fetch' },
    null,
  ]) {
    assert.equal(classifyTrailMutationFailure(unclassified), 'hard');
    assert.equal(preservesPendingTrailEdits(unclassified), false);
  }
});

test('only rejection at the exact transport boundary becomes a typed transport failure', async () => {
  const controller = new AbortController();
  await assert.rejects(
    requestTrailMutation(
      async () => { throw new Error('private transport detail'); },
      '/api/plan/trail/draft',
      { method: 'PUT' },
      controller.signal,
    ),
    TrailTransportError,
  );
  controller.abort();
  await assert.rejects(
    requestTrailMutation(
      async () => { throw new Error('abort detail'); },
      '/api/plan/trail/draft',
      { method: 'PUT' },
      controller.signal,
    ),
    { name: 'TrailOperationCancelledError' },
  );
});

test('unknown duration and optional-group actions clear every related numeric buffer', () => {
  const populated = Object.fromEntries(
    Object.keys(EMPTY_NUMERIC_INPUTS).map((key) => [key, '9']),
  );
  const planning = clearPlanningDurationNumericInputs(populated);
  for (const key of [
    'planningMinimumHours',
    'planningMinimumMinutes',
    'planningMaximumHours',
    'planningMaximumMinutes',
  ]) {
    assert.equal(planning[key], '');
  }
  assert.equal(planning.distanceKm, '9');

  const environment = clearOptionalGroupNumericInputs(populated, 'environment');
  for (const key of [
    'maximumAltitudeM',
    'temperatureMinimumC',
    'temperatureMaximumC',
    'humidityMinimumPct',
    'humidityMaximumPct',
  ]) {
    assert.equal(environment[key], '');
  }
  assert.equal(environment.aidStationCount, '9');

  const support = clearOptionalGroupNumericInputs(populated, 'support');
  assert.equal(support.aidStationCount, '');
  assert.equal(support.aidStationGapKm, '');
  assert.equal(support.fuelingHours, '9');

  const fueling = clearOptionalGroupNumericInputs(populated, 'fueling');
  assert.equal(fueling.fuelingHours, '');
  assert.equal(fueling.fuelingMinutes, '');
  assert.equal(fueling.fuelingSessions, '');
  assert.equal(fueling.maximumAltitudeM, '9');
});

test('stale restore reapplies only intentional field edits onto the validated latest draft', () => {
  const base = structuredClone(inactiveReadinessResponse().draft);
  base.course_demand.fields.optional_context.environment.sun_exposure = {
    state: 'known',
    value: 'low',
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  base.course_demand.fields.optional_context.environment.wind_exposure = {
    state: 'known',
    value: 'sheltered',
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  base.course_demand.fields.planning_duration_range = {
    state: 'known',
    value: { minimum_min: 120, maximum_min: 180 },
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  const parsedBase = parseTrailDraftResponse(base);
  assert.equal(parsedBase?.state, 'current');

  const latest = structuredClone(base);
  latest.composite_revision = SHA_C;
  latest.revision_bindings.composite_revision = SHA_C;
  latest.course_demand.fields.optional_context.environment.wind_exposure = {
    state: 'known',
    value: 'exposed',
    provenance: 'course_verified',
    source_revision: SHA_B,
  };
  const parsedLatest = parseTrailDraftResponse(latest);
  assert.equal(parsedLatest?.state, 'current');

  const pendingRequest = requestFromDraft(parsedBase);
  pendingRequest.course_demand.fields.optional_context.environment.sun_exposure = unknown();
  const pendingInputs = {
    ...numericInputsFromDraft(parsedBase),
    planningMinimumHours: '',
    planningMinimumMinutes: '',
    planningMaximumHours: '',
    planningMaximumMinutes: '',
  };
  pendingRequest.course_demand.fields.planning_duration_range = unknown();

  const restored = reapplyPendingTrailEdits(
    parsedBase,
    pendingRequest,
    pendingInputs,
    parsedLatest,
  );
  assert.equal(
    restored.request.course_demand.fields.optional_context.environment.sun_exposure.state,
    'unknown',
  );
  assert.equal(
    restored.request.course_demand.fields.optional_context.environment.wind_exposure.value,
    'exposed',
    'an unrelated same-group server edit must survive restore',
  );
  assert.equal(
    restored.request.course_demand.fields.planning_duration_range.state,
    'unknown',
  );
  assert.deepEqual(
    [
      restored.numericInputs.planningMinimumHours,
      restored.numericInputs.planningMinimumMinutes,
      restored.numericInputs.planningMaximumHours,
      restored.numericInputs.planningMaximumMinutes,
    ],
    ['', '', '', ''],
  );
  assert.deepEqual(
    [...restored.dirtySections].sort(),
    ['section.event-duration', 'section.optional-context'],
  );
});

test('stale restore applies nullable and unknown numeric envelopes with their buffers atomically', () => {
  const knownNullBase = structuredClone(inactiveReadinessResponse().draft);
  knownNullBase.course_demand.fields.optional_context.support.max_aid_station_gap_m = {
    state: 'known',
    value: null,
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  const knownNullParsed = parseTrailDraftResponse(knownNullBase);
  assert.equal(knownNullParsed?.state, 'current');

  const latestKnownGap = structuredClone(knownNullBase);
  latestKnownGap.composite_revision = SHA_C;
  latestKnownGap.revision_bindings.composite_revision = SHA_C;
  latestKnownGap.course_demand.fields.optional_context.support.max_aid_station_gap_m = {
    state: 'known',
    value: 2000,
    provenance: 'course_verified',
    source_revision: SHA_B,
  };
  const latestKnownGapParsed = parseTrailDraftResponse(latestKnownGap);
  assert.equal(latestKnownGapParsed?.state, 'current');

  const unknownGapRequest = requestFromDraft(knownNullParsed);
  unknownGapRequest.course_demand.fields.optional_context.support.max_aid_station_gap_m = unknown();
  const unknownGapInputs = numericInputsFromDraft(knownNullParsed);
  const restoredUnknownGap = reapplyPendingTrailEdits(
    knownNullParsed,
    unknownGapRequest,
    unknownGapInputs,
    latestKnownGapParsed,
  );
  assert.equal(
    restoredUnknownGap.request.course_demand.fields.optional_context.support
      .max_aid_station_gap_m.state,
    'unknown',
  );
  assert.equal(restoredUnknownGap.numericInputs.aidStationGapKm, '');
  assert.equal(
    buildValidatedRequest(
      restoredUnknownGap.request,
      restoredUnknownGap.numericInputs,
    ).request.course_demand.fields.optional_context.support.max_aid_station_gap_m.state,
    'unknown',
  );

  const unknownBase = structuredClone(inactiveReadinessResponse().draft);
  const unknownBaseParsed = parseTrailDraftResponse(unknownBase);
  assert.equal(unknownBaseParsed?.state, 'current');
  const knownNullRequest = requestFromDraft(unknownBaseParsed);
  knownNullRequest.course_demand.fields.optional_context.support.max_aid_station_gap_m =
    known(null);
  const restoredKnownNull = reapplyPendingTrailEdits(
    unknownBaseParsed,
    knownNullRequest,
    numericInputsFromDraft(unknownBaseParsed),
    latestKnownGapParsed,
  );
  assert.deepEqual(
    restoredKnownNull.request.course_demand.fields.optional_context.support
      .max_aid_station_gap_m,
    known(null),
  );
  assert.equal(restoredKnownNull.numericInputs.aidStationGapKm, '');
  assert.deepEqual(
    buildValidatedRequest(
      restoredKnownNull.request,
      restoredKnownNull.numericInputs,
    ).request.course_demand.fields.optional_context.support.max_aid_station_gap_m,
    known(null),
  );
});

test('stale restore clears all associated planning and fueling duration buffers', () => {
  const base = structuredClone(inactiveReadinessResponse().draft);
  base.course_demand.fields.planning_duration_range = {
    state: 'known',
    value: { minimum_min: 120, maximum_min: 180 },
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  base.course_demand.fields.optional_context.fueling.longest_practiced_duration_min = {
    state: 'known',
    value: 90,
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  const parsedBase = parseTrailDraftResponse(base);
  assert.equal(parsedBase?.state, 'current');

  const latest = structuredClone(base);
  latest.composite_revision = SHA_C;
  latest.revision_bindings.composite_revision = SHA_C;
  latest.course_demand.fields.planning_duration_range.value = {
    minimum_min: 240,
    maximum_min: 300,
  };
  latest.course_demand.fields.optional_context.fueling.longest_practiced_duration_min.value =
    180;
  const parsedLatest = parseTrailDraftResponse(latest);
  assert.equal(parsedLatest?.state, 'current');

  const pendingRequest = requestFromDraft(parsedBase);
  pendingRequest.course_demand.fields.planning_duration_range = unknown();
  pendingRequest.course_demand.fields.optional_context.fueling
    .longest_practiced_duration_min = unknown();
  const pendingInputs = numericInputsFromDraft(parsedBase);
  for (const key of [
    'planningMinimumHours',
    'planningMinimumMinutes',
    'planningMaximumHours',
    'planningMaximumMinutes',
    'fuelingHours',
    'fuelingMinutes',
  ]) {
    pendingInputs[key] = '';
  }

  const restored = reapplyPendingTrailEdits(
    parsedBase,
    pendingRequest,
    pendingInputs,
    parsedLatest,
  );
  assert.equal(restored.request.course_demand.fields.planning_duration_range.state, 'unknown');
  assert.equal(
    restored.request.course_demand.fields.optional_context.fueling
      .longest_practiced_duration_min.state,
    'unknown',
  );
  for (const key of [
    'planningMinimumHours',
    'planningMinimumMinutes',
    'planningMaximumHours',
    'planningMaximumMinutes',
    'fuelingHours',
    'fuelingMinutes',
  ]) {
    assert.equal(restored.numericInputs[key], '', key);
  }
});

test('operation fences reject every stale owner, request, revision, edit, and lifetime callback', () => {
  const started = {
    lifetime: 3,
    ownerScope: 'owner-a',
    requestId: 7,
    revision: SHA_A,
    editGeneration: 11,
  };
  assert.equal(isCurrentTrailOperation(started, { ...started }), true);
  for (const changed of [
    { lifetime: 4 },
    { ownerScope: 'owner-b' },
    { requestId: 8 },
    { revision: SHA_B },
    { editGeneration: 12 },
  ]) {
    assert.equal(isCurrentTrailOperation(started, { ...started, ...changed }), false);
  }
});

test('owner-scope loss invalidates a never-settling request even when navigation is vetoed', async () => {
  const values = new Map([['praxys-auth-token', 'owner-a-token']]);
  const previousStorage = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  const target = new EventTarget();
  let invalidations = 0;
  const currentScope = () => tokenCacheScope(
    globalThis.localStorage.getItem('praxys-auth-token'),
  );
  const initialScope = currentScope();
  const stop = bindTrailOwnerScopeInvalidation(
    target,
    initialScope,
    currentScope,
    () => { invalidations += 1; },
  );
  target.addEventListener('beforeunload', (event) => event.preventDefault());
  const neverSettles = new Promise(() => {});
  try {
    handleUnauthorizedSession(() => {
      const event = new Event('beforeunload', { cancelable: true });
      assert.equal(target.dispatchEvent(event), false);
      assert.equal(event.defaultPrevented, true);
    });
    assert.equal(currentScope(), 'anonymous');
    assert.equal(invalidations, 1);
    assert.equal(
      await Promise.race([neverSettles, Promise.resolve('request-still-pending')]),
      'request-still-pending',
    );
    target.dispatchEvent(new Event('storage'));
    assert.equal(invalidations, 1);
  } finally {
    stop();
    if (previousStorage === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previousStorage;
  }

  const component = await read('../src/components/TrailCourseReview.tsx');
  assert.match(component, /bindTrailOwnerScopeInvalidation\(\s*window,/);
  assert.match(component, /ownerExport\.cancel\(\)/);
  assert.match(component, /setRequest\(emptyDraftRequest\(\)\)/);
  assert.match(component, /setNumericInputs\(\{ \.\.\.EMPTY_NUMERIC_INPUTS \}\)/);
  assert.match(component, /setDirtySections\(new Set\(\)\)/);
  assert.match(component, /setReadiness\(null\)/);
  assert.match(component, /setLatestDraft\(null\)/);
  assert.match(component, /setStaleConflict\(false\)/);
  assert.match(component, /onClearRemote\(\)/);
});

test('confirmation callback rejects pending intent synchronously across sections', async () => {
  const pendingRef = { current: false };
  const confirmed = [];
  const confirm = async (sectionKey) => { confirmed.push(sectionKey); };
  const invoke = (sectionKey) => runTrailConfirmationCallback(
    sectionKey,
    () => false,
    () => pendingRef.current,
    confirm,
  );

  pendingRef.current = true;
  assert.equal(invoke('section.event-duration'), undefined);
  assert.deepEqual(confirmed, []);

  pendingRef.current = false;
  await invoke('section.event-duration');
  assert.deepEqual(confirmed, ['section.event-duration']);

  const component = await read('../src/components/TrailCourseReview.tsx');
  assert.match(
    component,
    /serverDraft\.state !== 'current'\s*\|\| pendingRef\.current\s*\|\| dirtySections\.size > 0/,
  );
  assert.equal((component.match(/onConfirm=\{handleConfirmSection\}/g) ?? []).length, 4);
});

test('stale and ambiguous writes preserve explicit recovery without generic retry', async () => {
  const [component, copy] = await Promise.all([
    read('../src/components/TrailCourseReview.tsx'),
    read('../src/components/trail-course-review/copy.tsx'),
  ]);
  assert.match(component, /classifyTrailMutationFailure\(error\)/);
  assert.match(component, /disposition === 'stale'/);
  assert.match(component, /disposition === 'retryable'/);
  assert.match(component, /staleConflict/);
  assert.match(component, /copy\.reviewLatest/);
  assert.match(component, /copy\.restorePending/);
  assert.match(component, /const discardPending = useCallback/);
  assert.match(component, /onClick=\{discardPending\}/);
  assert.match(component, /copy\.discardPending/);
  assert.match(copy, /t`Discard pending changes`/);
  assert.match(copy, /t`放弃待保存更改`/);
  assert.match(component, /!latestDraft[\s\S]{0,80}latestDraft\.state === 'unknown_schema'/);
  assert.doesNotMatch(component, /disposition === 'retryable'[\s\S]{0,220}onRefetch/);
  assert.match(component, /onClick=\{\(\) => \{ void ownerExport\.run\(\); \}\}/);
  assert.doesNotMatch(`${component}\n${copy}`, /exportUnavailable/);
});

test('owner export delegates close-time focus restoration to the mounted Base UI menu', async () => {
  const component = await read('../src/components/TrailCourseReview.tsx');
  const exportSetup = component.slice(
    component.indexOf('const [ownerExport]'),
    component.indexOf('const pending ='),
  );
  assert.doesNotMatch(component, /import \{ flushSync \} from 'react-dom'/);
  assert.match(component, /getAuthHeaders/);
  assert.match(exportSetup, /createTrailOwnerExportAction\(\{/);
  assert.match(exportSetup, /getAuthHeaders,/);
  assert.match(exportSetup, /onStatusChange: setExportStatus/);
  assert.match(exportSetup, /setExportMenuClosing\(true\);\s*setMoreActionsOpen\(false\)/);
  assert.doesNotMatch(exportSetup, /moreActionsRef\.current\?\.focus\(\)|requestAnimationFrame|setTimeout/);
  assert.match(exportSetup, /ownerExport\.cancel\(\)/);
  assert.doesNotMatch(exportSetup, /onRefetch|onReplaceRemote|setRequest|setDirtySections|JSON\.stringify/);
  assert.match(component, /<DropdownMenu open=\{moreActionsOpen\} onOpenChange=\{handleMoreActionsOpenChange\}>/);
  assert.match(component, /ref=\{moreActionsRef\}/);
  assert.match(component, /finalFocus=\{exportMenuClosing \? moreActionsRef : undefined\}/);
  assert.match(component, /if \(open\) setExportMenuClosing\(false\)/);
  assert.match(component, /<DropdownMenuItem\s+disabled=\{exportStatus === 'preparing'\}\s+aria-busy=\{exportStatus === 'preparing'\}\s+closeOnClick=\{false\}/);
  assert.match(component, /exportStatus === 'preparing' \? copy\.exportBusy : copy\.export/);
  assert.match(component, /copy\.exportSupport/);
  assert.match(component, /<div role="status" aria-live="polite" aria-atomic="true">/);
  assert.match(component, /exportStatus === 'preparing' \|\| exportStatus === 'success'/);
  assert.match(component, /exportStatus === 'preparing' \? copy\.exportBusy : copy\.exportSuccess/);
  assert.match(component, /exportStatus === 'error' \? \(\s*<Alert role="alert"[\s\S]*?copy\.exportError/);
});

test('owner export copy matches frozen v3 through normal locale-only Lingui descriptors', async () => {
  const [copy, amendment] = await Promise.all([
    read('../src/components/trail-course-review/copy.tsx'),
    read('../../docs/dev/trail-running-plan-export-experience-amendment-v3.md'),
  ]);
  const pairs = [
    ['export', 'Export my Trail plan data', '导出我的越野计划数据'],
    ['exportSupport', 'Download your Praxys account data export. It includes the current saved Trail course review—values and unknowns, provenance, revisions, and confirmations—and any retained Trail proposal snapshots, audits, and receipts. Unsaved changes on this page are not included.', '下载 Praxys 账号数据导出文件，其中包含当前已保存的越野赛道核对中的值与未知项、来源信息、版本和确认状态，以及已保留的越野提案快照、审计记录和回执（如有）。本页面尚未保存的更改不会包含在内。'],
    ['exportBusy', 'Preparing export…', '正在准备导出…'],
    ['exportSuccess', 'Your data export is downloading.', '正在下载数据导出文件。'],
    ['exportError', "We couldn't export your data. Try again.", '暂时无法导出数据，请重试。'],
  ];
  for (const [key, english, chinese] of pairs) {
    const descriptor = copy.match(new RegExp(`${key}: l\\(\\s*t\`([^\`]+)\`,\\s*t\`([^\`]+)\`,?\\s*\\)`));
    assert.ok(descriptor, `${key} must use the incumbent locale-only copy hook`);
    assert.deepEqual(descriptor.slice(1), [english, chinese]);
    assert.ok(amendment.includes(`**${english}**`));
    assert.ok(amendment.includes(`**${chinese}**`));
  }
  assert.match(copy, /\(english: string, chinese: string\) => isZh \? chinese : english/);
  assert.doesNotMatch(copy, /i18n\.load|loadAndActivate/);
});

test('Trail delete responses accept only the exact absent revision receipt', () => {
  const absentRevision = 'sha256:8adaaec35fb1a6ff05f212e69fc57c9e41bceaa30b65b95a8b3f90120ef5a321';
  assert.deepEqual(parseTrailDeleteResponse({
    status: 'deleted',
    composite_revision: absentRevision,
  }), {
    status: 'deleted',
    composite_revision: absentRevision,
  });
  for (const value of [
    { status: 'deleted', composite_revision: SHA_A },
    { status: 'absent', composite_revision: absentRevision, leaked: 'value' },
    { status: 'complete', composite_revision: absentRevision },
    { status: 'deleted' },
  ]) {
    assert.equal(parseTrailDeleteResponse(value), null);
  }
});

test('the unknown-schema delete path uses the same closed response parser', async () => {
  const states = await read('../src/components/trail-course-review/states.tsx');
  assert.match(states, /kind === 'delete'/);
  assert.match(states, /parseTrailDeleteResponse\(payload\)/);
  assert.match(states, /throw new Error\('The Trail deletion response was not recognized\.'\)/);
  assert.equal(parseTrailDeleteResponse({
    status: 'deleted',
    composite_revision: 'sha256:8adaaec35fb1a6ff05f212e69fc57c9e41bceaa30b65b95a8b3f90120ef5a321',
    private_payload: { value: 'must-not-pass' },
  }), null);
});

test('readiness validation accepts only the exact inactive contract receipt', () => {
  const valid = inactiveReadinessResponse();
  assert.notEqual(parseTrailDraftResponse(valid.draft), null);
  assert.notEqual(parseTrailReadinessResponse(valid, SHA_D), null);

  const confirmedAssumption = inactiveReadinessResponse();
  confirmedAssumption.draft.course_demand.fields.optional_context.environment.conditions_basis = {
    state: 'known',
    value: 'athlete_assumption',
    provenance: 'explicit_assumption',
    source_revision: SHA_A,
    assumption_confirmed_revision: SHA_A,
  };
  assert.notEqual(parseTrailReadinessResponse(confirmedAssumption, SHA_D), null);

  for (const spuriousReason of [
    'insufficient_comparable_trail_history',
    'insufficient_descent_history',
  ]) {
    const spurious = inactiveReadinessResponse();
    spurious.readiness.matching_reasons.push({
      status: 'readiness_blocked',
      detail_reason: spuriousReason,
    });
    assert.equal(parseTrailReadinessResponse(spurious, SHA_D), null);
  }

  const footingMismatch = inactiveReadinessResponse();
  footingMismatch.draft.course_demand.fields.course_footing = {
    state: 'known',
    value: ['rocks_or_roots'],
    provenance: 'athlete_stated',
    source_revision: SHA_A,
  };
  footingMismatch.readiness.matching_reasons.push({
    status: 'readiness_blocked',
    detail_reason: 'insufficient_comparable_trail_history',
  });
  assert.notEqual(parseTrailReadinessResponse(footingMismatch, SHA_D), null);

  const invalidCases = [
    (value) => { value.readiness.contract_runtime_state = 'active'; },
    (value) => { value.readiness.inactive_dry_run = true; },
    (value) => { value.readiness.plan = {}; },
    (value) => { value.readiness.contract_digest = SHA_A; },
    (value) => { value.readiness.status = 'ready'; },
    (value) => {
      value.readiness.status = 'eligible_proposal';
      value.readiness.detail_reason = null;
      value.readiness.matching_reasons = [];
      value.readiness.module_availability = TRAIL_MODULE_KEYS.map((module) => ({
        module,
        state: 'available',
        reason_target: null,
      }));
    },
    (value) => { value.readiness.matching_reasons = [{ status: 'future', detail_reason: 'reason' }]; },
    (value) => { value.readiness.matching_reasons = [
      { status: 'policy_unavailable', detail_reason: 'policy_inactive' },
      { status: 'policy_unavailable', detail_reason: 'policy_inactive' },
    ]; },
    (value) => { value.readiness.module_availability.pop(); },
    (value) => { value.readiness.module_availability[1].module = 'grade_specificity'; },
    (value) => { value.readiness.module_availability[0].state = 'available'; },
    (value) => { value.readiness.module_availability[0].reason_target = 'course.course_footing'; },
    (value) => { value.readiness.limited_modules = ['grade_specificity']; },
    (value) => { value.readiness.revision_bindings.history_revision = SHA_D; },
    (value) => { delete value.readiness.history_statistics.latest_run_date; },
    (value) => {
      value.draft.course_demand.fields.optional_context.environment.temperature_min_c = {
        state: 'known', value: 30, provenance: 'athlete_stated', source_revision: SHA_A,
      };
      value.draft.course_demand.fields.optional_context.environment.temperature_max_c = {
        state: 'known', value: 20, provenance: 'athlete_stated', source_revision: SHA_A,
      };
    },
    (value) => {
      value.draft.constraints.weekly_time_limit_min = {
        state: 'known', value: 100, provenance: 'athlete_stated', source_revision: SHA_A,
      };
      value.draft.constraints.maximum_session_duration_min = {
        state: 'known', value: 200, provenance: 'athlete_stated', source_revision: SHA_A,
      };
    },
    (value) => {
      value.draft.constraints.available_weekdays = {
        state: 'known', value: [1], provenance: 'athlete_stated', source_revision: SHA_A,
      };
      value.draft.constraints.preferred_longest_weekday = 2;
    },
    (value) => {
      value.draft.course_demand.fields.grade_distribution = {
        state: 'known',
        value: {
          below_neg_10: 1000,
          neg_10_to_below_neg_3: 1000,
          neg_3_to_below_pos_3: 6000,
          pos_3_to_below_pos_10: 1000,
          pos_10_and_above: 1000,
        },
        provenance: 'model_inferred',
        source_revision: SHA_A,
        model_version: 'forbidden-grade-model',
      };
    },
    (value) => {
      value.draft.course_demand.fields.optional_context.environment.conditions_basis = {
        state: 'known',
        value: 'athlete_assumption',
        provenance: 'explicit_assumption',
        source_revision: SHA_A,
      };
    },
    (value) => { value.readiness.history_statistics.evaluator_schema_id = 'future-history'; },
    (value) => { value.readiness.history_statistics.usable_completed_weeks = 9; },
    (value) => { value.readiness.history_statistics.usable_completed_weeks = 3; },
    (value) => {
      value.readiness.history_statistics.observation_window_start = '2026-09-04';
      value.readiness.history_statistics.observation_window_end = '2026-09-03';
    },
    (value) => {
      value.readiness.history_statistics.comparable_ascent_sessions_within_window = 0;
    },
    (value) => {
      value.readiness.history_statistics.latest_comparable_ascent_session_date = '2026-08-01';
    },
    (value) => {
      value.draft.course_demand.fields.event_date = {
        state: 'known', value: '2026-02-30', provenance: 'athlete_stated', source_revision: SHA_A,
      };
    },
    (value) => {
      value.draft.course_demand.fields.event_date = {
        state: 'known',
        value: '2026-11-15',
        provenance: 'athlete_stated',
        source_revision: SHA_A,
        source_timestamp: '2026-09-04T12:00:00',
      };
    },
    (value) => {
      value.draft.course_demand.fields.event_date = {
        state: 'known',
        value: '2026-11-15',
        provenance: 'athlete_stated',
        source_revision: SHA_A,
        source_timestamp: '2026-02-30T12:00:00+08:00',
      };
    },
    (value) => {
      value.draft.course_demand.fields.event_date = {
        state: 'known',
        value: '2026-11-15',
        provenance: 'athlete_stated',
        source_revision: SHA_A,
        model_version: '',
      };
    },
    (value) => {
      value.readiness.matching_reasons.push({
        status: 'readiness_blocked',
        detail_reason: 'insufficient_recent_running_history',
      });
    },
    (value) => { delete value.draft.course_demand.fields.optional_context.support; },
  ];
  for (const mutate of invalidCases) {
    const candidate = inactiveReadinessResponse();
    mutate(candidate);
    assert.equal(parseTrailReadinessResponse(candidate, SHA_D), null);
  }
  assert.equal(parseTrailReadinessResponse(valid, SHA_A), null);
});

test('all five ordered ledger sections and only four server confirmations are implemented', async () => {
  const [component, implementation] = await Promise.all([
    read('../src/components/TrailCourseReview.tsx'),
    readTrailImplementation(),
  ]);
  const sectionTitles = [
    'Event & planning duration',
    'Grade & footing',
    'When and where you can train',
    'Recent experience',
    'Conditions, support, and fueling',
  ];
  for (const title of sectionTitles) assert.match(implementation, new RegExp(title.replaceAll('&', '\\&')));
  const renderedSectionOrder = [
    'section.event-duration',
    'section.grade-footing',
    'section.training-access',
    'section.recent-experience',
    'section.optional-context',
  ].map((section) => component.indexOf(`sectionKey="${section}"`));
  assert.ok(renderedSectionOrder.every((position) => position >= 0));
  assert.deepEqual(renderedSectionOrder, [...renderedSectionOrder].sort((a, b) => a - b));
  assert.equal((component.match(/<ConfirmBar\b/g) ?? []).length, 4);
  assert.doesNotMatch(implementation, /Confirm all|确认全部/);
  assert.match(component, /'section\.optional-context': false/);
  assert.match(component, /optionalOpened/);
  assert.match(component, /read-only|只读/);

  const requiredFields = [
    'event_date', 'distance_meters', 'total_ascent_m', 'total_descent_m',
    'planning_duration_range', 'event_format', 'distance_family',
    'planning_intent', 'grade_distribution', 'course_footing', 'hands_assist',
    'fixed_rope', 'available_weekdays', 'weekly_time_limit_min',
    'maximum_session_duration_min', 'unavailable_dates',
    'preferred_longest_weekday', 'nontechnical_three_minute_uphill_access',
    'controlled_downhill_access', 'accessible_footing',
    'adult_nonclinical_scope_confirmed', 'performance_intent_confirmed',
    'current_symptom_stop', 'maximum_altitude_m', 'temperature_min_c',
    'temperature_max_c', 'humidity_min_pct', 'humidity_max_pct',
    'sun_exposure', 'wind_exposure', 'conditions_basis', 'aid_support_mode',
    'aid_station_count', 'max_aid_station_gap_m', 'water_availability',
    'food_availability', 'mandatory_gear', 'longest_practiced_duration_min',
    'practice_sessions_last_42_days', 'intake_form',
    'gastrointestinal_experience',
  ];
  for (const field of requiredFields) assert.match(implementation, new RegExp(`\\b${field}\\b`));
});

test('reason and module rendering is exhaustive, natural-language only, and fail closed', async () => {
  const component = await readTrailImplementation();
  for (const code of EXPECTED_REASONS) {
    assert.match(component, new RegExp(`['"]${code.replaceAll('.', '\\.')}['"]`));
  }
  for (const phrase of [
    'Finding', 'Effect', 'Next action',
    'Grade-specific training', 'Technical terrain',
    'Environment and altitude', 'Fueling practice',
    'Not evaluated', 'Available', 'Limited',
  ]) {
    assert.match(component, new RegExp(phrase));
  }
  assert.match(component, /reasonCodeOf/);
  assert.match(component, /hasUnknownReason/);
  assert.match(component, /did not provide a safe destination/);
  assert.match(component, /MODULE_LIMIT_TARGETS/);
  assert.doesNotMatch(component, />\s*\{reason\.code\}\s*</);
  assert.doesNotMatch(component, />\s*\{readiness\.status\}\s*</);
  assert.doesNotMatch(component, />\s*\{reason\.detail_reason\}\s*</);
});

test('Lingui locale-only copy includes the accepted English and Simplified Chinese contracts', async () => {
  const component = await readTrailImplementation();
  assert.match(component, /useLingui/);
  assert.match(component, /i18n\.locale\.toLowerCase\(\)\.startsWith\('zh'\)/);
  assert.match(component, /t`Review Trail event`/);
  assert.match(component, /t`核对越野赛事`/);
  assert.match(component, /t`Describe the course and where you can train\. Praxys will keep unknowns visible\.`/);
  assert.match(component, /t`填写赛道情况和可训练条件。Praxys 会明确保留未知项。`/);
  assert.match(component, /t`I don't know yet`/);
  assert.match(component, /t`目前不确定`/);
  assert.match(component, /t`Offline\. Changes are kept only on this page and have not been saved\.`/);
  assert.match(component, /t`当前离线。更改仅保留在此页面，尚未保存。`/);
  assert.match(component, /Reset replaces the current editable answers with unknowns/);
  assert.match(component, /重置会把当前可编辑回答改为未知/);
  assert.doesNotMatch(component, /Review Trail event\s*\/\s*核对越野赛事/);
});

test('state, accessibility, and responsive markers cover the approved workbench contract', async () => {
  const component = await readTrailImplementation();
  for (const marker of [
    'TrailCourseReviewSkeleton', 'unknown_schema', 'errorStatus', 'status === 404',
    'memory-only-unsaved', 'beforeunload', 'navigator.onLine', 'slowAction',
    'validationIssues', 'staleConflict', 'Review latest version',
    'Restore pending changes', 'Discard pending changes', 'aria-live',
    'aria-busy', 'aria-atomic', 'tabIndex={-1}', 'role="group"',
    'motion-reduce', 'min-h-11', 'break-words', 'font-data',
    'lg:grid-cols-', 'lg:sticky', 'Collapsible',
  ]) {
    assert.match(component, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.match(component, /status === 412/);
  assert.match(component, /requestAnimationFrame\(\(\) => errorSummaryRef\.current\?\.focus\(\)\)/);
  assert.match(component, /aria-describedby=\{invalidMessage \? `\$\{id\}-error` : undefined\}/);
  assert.match(component, /<Label htmlFor=\{id\}[^>]*>\{hoursLabel\}<\/Label>/);
  assert.match(component, /<Label htmlFor=\{`\$\{id\}-minutes`\}[^>]*>\{minutesLabel\}<\/Label>/);
  assert.match(component, /closeLabel=\{isZh \? t`关闭` : t`Close`\}/);
  assert.match(component, /recent_maximum_usable_weekly_minutes/);
  assert.match(component, /recent_maximum_session_minutes/);
  assert.doesNotMatch(component, /className="order-2 min-w-0 lg:order-1"/);
  assert.doesNotMatch(component, /className="order-1 min-w-0 border/);
  assert.match(component, /requestAnimationFrame\(\(\) => receiptErrorRef\.current\?\.focus\(\)\)/);
  assert.doesNotMatch(component, /<(?:button|input|select)\b/);
  assert.doesNotMatch(component, /shadow-(?:sm|md|lg|xl|2xl)|bg-gradient|border-l-[2-9]/);
});

test('types preserve strict unknown envelopes and closed response targets', async () => {
  const types = await read('../src/types/trail-plan.ts');
  assert.match(types, /\{ state: 'known'; value: T \}/);
  assert.match(types, /\{ state: 'unknown'; value\?: never \}/);
  assert.match(types, /namespace: unknown/);
  assert.match(types, /TrailMatchingReasonFromCode<T extends TrailReasonCode>/);
  assert.match(types, /TrailModuleReasonTarget/);
  assert.match(types, /'course\.optional_context\.fueling'/);
  assert.match(types, /plan: null/);
  assert.match(types, /inactive_dry_run: false/);
  assert.doesNotMatch(types, /\bany\b/);
});
