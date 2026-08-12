import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web and miniapp expose the same structured editing capabilities', async () => {
  const [webEditor, miniController, miniTemplate, webTypes, miniTypes] = (
    await Promise.all([
      read('../src/components/WorkoutPlanEditor.tsx'),
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
    '/api/plan/workouts/compatibility',
  ]) {
    assert.match(miniController, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  for (const marker of [
    'bindtap="onStructuredAction"',
    'bindtap="onAddStructuredRepeat"',
    'bindtap="onUndoStructuredDelete"',
    'bindtap="onDuplicateWorkout"',
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

  assert.ok(miniTypes.endsWith(webTypes));
  assert.match(webTypes, /interface WorkoutProviderCompatibility/);
  assert.match(webTypes, /interface PlanWorkoutCompatibilityResponse/);
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
