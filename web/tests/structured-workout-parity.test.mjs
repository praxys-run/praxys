import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web and miniapp expose the same structured editing capabilities', async () => {
  const [
    webEditor,
    webStructureEditor,
    miniController,
    miniTemplate,
    webTypes,
    miniTypes,
  ] = (
    await Promise.all([
      read('../src/components/WorkoutPlanEditor.tsx'),
      read('../src/components/WorkoutStructureEditor.tsx'),
      read('../../miniapp/components/managed-plan/index.ts'),
      read('../../miniapp/components/managed-plan/index.wxml'),
      read('../src/types/api.ts'),
      read('../../miniapp/types/api.ts'),
    ])
  );

  for (const marker of [
    'WorkoutStructureEditor',
    'workout_structure_version: \'v1\'',
    '/api/plan/workouts/compatibility',
    'previousNonRestStructure',
    'Convert to structured steps',
    'Plan activity',
    'Workout purpose',
    "'unsupported'",
  ]) {
    assert.match(webEditor, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }

  for (const marker of [
    'editorStructured',
    'onStructuredAction',
    'onStructuredPhaseChange',
    'onStructuredTerminationChange',
    'onStructuredTargetChange',
    'onUndoStructuredDelete',
    'onConvertLegacyToStructured',
    'onDuplicateWorkout',
    'editorLastNonRestStructure',
    'editorUnsupportedStructure',
    '_compatibilityRequestId',
    '/api/plan/workouts/compatibility',
    'setCustomTabBarHidden',
  ]) {
    assert.match(miniController, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  for (const marker of [
    'bindtap="onStructuredAction"',
    'bindtap="onAddStructuredRepeat"',
    'bindtap="onUndoStructuredDelete"',
    'bindtap="onDuplicateWorkout"',
    'managed-plan__editor-scroll',
    'env(safe-area-inset-bottom)',
  ]) {
    const source = marker.includes('safe-area')
      ? await read('../../miniapp/components/managed-plan/index.scss')
      : miniTemplate;
    assert.match(source, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  assert.doesNotMatch(
    miniTemplate,
    /type="digit"[^>]*data-field="target(?:Min|Max)"/,
  );
  assert.match(
    miniTemplate,
    /<scroll-view[\s\S]{0,200}class="managed-plan__editor-scroll"/,
  );
  assert.match(
    miniTemplate,
    /<\/scroll-view>\s*<view class="managed-plan__editor-bottom">/,
  );
  assert.match(
    miniController,
    /openWorkoutEditor\([\s\S]{0,200}setCustomTabBarHidden\(true\)/,
  );
  assert.match(
    miniController,
    /onCloseEditor\(\)[\s\S]{0,200}setCustomTabBarHidden\(false\)/,
  );
  assert.match(miniController, /editorWorkoutType:\s*workoutType,/);
  assert.match(webStructureEditor, /step="any"/);

  assert.ok(miniTypes.endsWith(webTypes));
  assert.match(webTypes, /interface WorkoutProviderCompatibility/);
  assert.match(webTypes, /interface PlanWorkoutCompatibilityResponse/);
  const updateValues = webTypes.match(
    /interface PlanWorkoutUpdateValues \{[\s\S]*?\n\}/,
  )?.[0] ?? '';
  assert.match(updateValues, /activity_type\?: PlanActivityType;/);
  assert.doesNotMatch(updateValues, /activity_type\?: PlanActivityType \| null/);
});

test('miniapp totals retain repeat semantics and mark manual work unknown', async () => {
  const mini = await import(
    '../../miniapp/utils/workout-structure.ts'
  );
  const structure = {
    steps: [{
      type: 'repeat',
      repetitions: 3,
      steps: [{
        type: 'step',
        phase: 'work',
        termination: { type: 'time', seconds: 120 },
        target: { metric: 'none', unit: 'none', reference: 'none' },
      }],
    }],
  };
  assert.deepEqual(mini.summarize(structure).duration, {
    certainty: 'deterministic',
    seconds: 360,
  });
  assert.equal(mini.summarize({
    steps: [{
      type: 'step',
      phase: 'work',
      termination: { type: 'manual' },
      target: { metric: 'none', unit: 'none', reference: 'none' },
    }],
  }).duration.certainty, 'unknown');
  assert.throws(() => mini.synthesizeFromFlat({
    workoutType: 'easy',
    duration: 30,
    distance: null,
    powerMin: null,
    powerMax: null,
    hrMin: null,
    hrMax: null,
    paceMin: 'not a pace',
    paceMax: null,
  }));
});

test('miniapp validation and exact formatting match the portable contract', async () => {
  const mini = await import(
    '../../miniapp/utils/workout-structure.ts'
  );
  const step = {
    type: 'step',
    phase: 'work',
    termination: { type: 'time', seconds: 60 },
    target: {
      metric: 'rpe',
      unit: 'scale_10',
      reference: 'perceived_exertion',
      min: 11,
    },
  };

  assert.equal(mini.validate({
    steps: [{
      type: 'repeat',
      repetitions: 101,
      steps: [step],
    }],
  }, 'interval'), 'repeat_count_invalid');
  assert.equal(mini.validate({
    steps: [{
      type: 'repeat',
      repetitions: 2,
      steps: [],
    }],
  }, 'interval'), 'repeat_steps_required');
  assert.equal(mini.validate({ steps: [step] }, 'interval'), 'target_out_of_range');
  assert.equal(mini.formatDeterministicDuration(90), '1:30');
  assert.equal(mini.formatDeterministicDistance(1), '1 m');

  const pace = mini.deriveFlat({
    steps: [{
      ...step,
      target: {
        metric: 'pace',
        unit: 'sec_per_km',
        reference: 'absolute',
        min: 320.5,
        max: 321.5,
      },
    }],
  });
  assert.equal(pace.target_pace_min, '05:20');
  assert.equal(pace.target_pace_max, '05:22');
});
