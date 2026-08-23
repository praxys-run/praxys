import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');
const interfaceBlock = (source, name) => {
  const match = source.match(new RegExp(`export interface ${name} \\{[\\s\\S]*?\\n\\}`));
  assert.ok(match, `missing ${name}`);
  return match[0];
};
const interfaceProperties = (block) => (
  [...block.matchAll(/^\s{2}([a-z0-9_]+)\??:/gm)].map((match) => match[1])
);

test('web goal page switches into the baseline pilot flow', async () => {
  const [page, panel] = await Promise.all([
    read('../src/pages/Goal.tsx'),
    read('../src/components/GoalBaselinePanel.tsx'),
  ]);

  assert.match(page, /data\.goal_kind === 'performance_5k' && data\.baseline/);
  assert.match(page, /enablePerformance10k=\{false\}/);
  assert.doesNotMatch(page, /enablePerformance10k && data\.goal_kind === 'performance_10k'/);
  assert.match(page, /<GoalBaselinePanel/);
  assert.match(panel, /Road10KHistoryConfirmationRequest/);
  assert.match(panel, /\/api\/goal\/baseline\/history\/confirm|\/api\/plan\/road-10k\/baseline\/history\/confirm/);
  assert.match(panel, /\/api\/goal\/baseline\/test/);
  assert.match(panel, /surface_or_protocol/);
  assert.match(panel, /assistance_status/);
  assert.match(panel, /measured_10k/);
  assert.match(panel, /no meaningful-change threshold/i);
  assert.match(panel, /maximal-effort|optional benchmark/i);
  assert.match(panel, /Arbitrary 5K segments|Passive fastest 10K splits/i);
  assert.match(panel, /className="border-t border-border pt-4"/);
  assert.match(panel, /invalidControlId/);
  assert.match(panel, /document\.getElementById\(invalidControlId\)\?\.focus/);
  assert.match(panel, /role="alert"/);
  const road10KPanel = panel.slice(
    panel.indexOf('function Road10KBaselinePanel'),
    panel.indexOf('function GoalBaseline5KPanel'),
  );
  assert.match(road10KPanel, /evidence: t`Status`/);
  assert.match(road10KPanel, /copy\.status\[baseline\.status\]/);
  assert.match(
    road10KPanel,
    /baseline\.guardrails\.baseline_current_through_completed_days/,
  );
  assert.doesNotMatch(road10KPanel, /copy\.status\.current/);
  assert.doesNotMatch(road10KPanel, /56-day/);
});

test('miniapp ships the same baseline semantics and endpoints', async () => {
  const [page, component, template, zhCatalog] = await Promise.all([
    read('../../miniapp/pages/goal/index.wxml'),
    read('../../miniapp/components/goal-baseline/index.ts'),
    read('../../miniapp/components/goal-baseline/index.wxml'),
    read('../src/locales/zh/messages.po'),
  ]);

  assert.match(page, /goalKind === 'performance_5k'[\s\S]*performance10kEnabled && goalKind === 'performance_10k'/);
  assert.match(page, /<goal-baseline/);
  assert.match(page, /id="goal-baseline-panel"/);
  assert.match(component, /Road10KHistoryConfirmationRequest/);
  assert.match(
    component,
    /baseline\.guardrails\.baseline_current_through_completed_days/,
  );
  assert.doesNotMatch(component, /The 56-day rule/);
  assert.match(component, /\/api\/goal\/baseline\/history\/confirm/);
  assert.match(component, /\/api\/plan\/road-10k\/baseline\/history\/confirm/);
  assert.match(component, /\/api\/goal\/baseline\/test/);
  assert.match(component, /surface_or_protocol/);
  assert.match(component, /assistance_status/);
  assert.match(component, /measured_10k/);
  assert.match(component, /candidateHint: t\('Retrieval is never qualification/);
  assert.match(component, /hasCandidates: candidateRows\.length > 0/);
  assert.match(component, /maximal-effort/i);
  assert.match(component, /copy\.protocolOptions/);
  assert.match(component, /copy\.assistanceOptions/);
  assert.match(zhCatalog, /检索到候选活动不代表其已合格/);
  assert.match(template, /wx:if="\{\{hasCandidates\}\}"/);
  assert.match(template, /isRoad10K \? copy\.benchmarkTitle : copy\.testTitle/);
  assert.match(template, /!isRoad10K && baseline\.test\.state === 'not_offered'/);
  assert.match(template, /aria-live="assertive"/);
});

test('web and miniapp share the generated baseline contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const required = [
    'performance_10k',
    'interface GoalBaselineResponse',
    'interface GoalBaselineMutationResponse',
    'interface Road10KHistoryConfirmationRequest',
    'goal_kind?: GoalKind',
    'baseline?: PerformanceGoalBaselineResponse',
    'optional_test_is_maximal_effort: true',
    'no_meaningful_change_threshold_yet: true',
  ];

  for (const marker of required) {
    assert.match(webTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(miniTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('web and miniapp expose the exact schema-v6 road 10K export contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const interfaceNames = [
    'UserDataExportRoad10KBaselineConfirmation',
    'UserDataExportRoad10KBaselineSnapshot',
    'UserDataExportRoad10KBaseline',
    'UserDataExportRoad10KTrainingPatternSnapshot',
    'UserDataExportRoad10KGeneration',
    'UserDataExportRoad10KPlanGeneration',
    'UserDataExportRoad10KOwnerReceipt',
    'UserDataExportRoad10KExposureReceipt',
    'UserDataExportRoad10KEvaluation',
    'UserDataExportRoad10KScreenshotReference',
    'UserDataExportRoad10KControl',
    'UserDataExportResponse',
  ];
  for (const name of interfaceNames) {
    assert.equal(interfaceBlock(webTypes, name), interfaceBlock(miniTypes, name));
  }

  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KBaselineConfirmation')),
    [
      'id',
      'lineage_id',
      'version',
      'supersedes_id',
      'goal_signature',
      'goal_snapshot',
      'activity_id',
      'response',
      'measured_10k',
      'elapsed_timing_confirmed',
      'completed_at',
      'elapsed_time_sec',
      'surface_or_protocol',
      'route_or_venue_identifier',
      'assistance_status',
      'source_provider',
      'created_at',
    ],
  );
  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KBaselineSnapshot')),
    [
      'id',
      'lineage_id',
      'version',
      'supersedes_id',
      'goal_signature',
      'goal_snapshot',
      'source_kind',
      'source_id',
      'provenance',
      'observed_date',
      'completed_at',
      'distance_km',
      'elapsed_time_sec',
      'measured_10k',
      'elapsed_timing_confirmed',
      'surface_or_protocol',
      'route_or_venue_identifier',
      'assistance_status',
      'source_provider',
      'qualification_status',
      'change_comparability',
      'invalidators',
      'created_at',
    ],
  );
  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KBaseline')),
    ['schema_version', 'exported_at', 'confirmations', 'snapshots'],
  );
  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KTrainingPatternSnapshot')),
    [
      'version',
      'schema_version',
      'policy_version',
      'usable_completed_weeks',
      'recent_modal_running_frequency',
      'recent_median_usable_weekly_minutes',
      'recent_maximum_usable_weekly_minutes',
      'recent_maximum_session_minutes',
      'recent_maximum_session_distance_km',
      'latest_run_date',
      'history_observation_count',
      'history_provenance_fingerprint',
      'intensity_observation_count',
      'intensity_provenance_fingerprint',
      'reserved_date_count',
      'reservation_fingerprint',
      'canonical_fingerprint',
      'created_at',
    ],
  );
  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KPlanGeneration')),
    ['schema_version', 'exported_at', 'training_pattern_snapshots', 'records'],
  );
  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KGeneration')),
    [
      'id',
      'proposal_id',
      'capability_id',
      'policy_version',
      'generator_version',
      'science_decision_id',
      'source_decision_digest',
      'contract_digest',
      'baseline_snapshot_id',
      'baseline_source',
      'source_goal_id',
      'source_goal_revision',
      'history_cutoff_completed_days',
      'training_pattern_snapshot_version',
      'event_context_snapshot_version',
      'active_zone_model_id',
      'active_zone_model_version',
      'normalized_constraints',
      'selected_template_ids',
      'source_revision',
      'deterministic_input_hash',
      'request_kind',
      'request_fingerprint',
      'predecessor_proposal_id',
      'predecessor_version',
      'result_code',
      'validation_reason_code',
      'created_at',
    ],
  );
  assert.deepEqual(
    interfaceProperties(interfaceBlock(webTypes, 'UserDataExportRoad10KControl')),
    [
      'schema_version',
      'exported_at',
      'owner_receipts',
      'exposure_receipts',
      'evaluations',
      'screenshot_references',
    ],
  );
  const response = interfaceBlock(webTypes, 'UserDataExportResponse');
  assert.match(response, /schema_version: 6;/);
  assert.match(response, /road_10k_baseline: UserDataExportRoad10KBaseline;/);
  assert.match(response, /road_10k_control: UserDataExportRoad10KControl;/);
  assert.match(response, /road_10k_plan_generation: UserDataExportRoad10KPlanGeneration;/);
  const eventContext = interfaceBlock(webTypes, 'Road10KEventContext');
  assert.equal(eventContext, interfaceBlock(miniTypes, 'Road10KEventContext'));
  assert.match(
    eventContext,
    /state: 'unconfirmed' \| 'confirmed_none' \| 'single_target' \| 'race_dense';/,
  );
  assert.doesNotMatch(
    interfaceNames.map((name) => interfaceBlock(webTypes, name)).join('\n'),
    /history_observation_ids/,
  );
});
