import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web plan management uses canonical identity and version fences', async () => {
  const [plan, editor] = await Promise.all([
    read('../src/components/UpcomingPlanCard.tsx'),
    read('../src/components/WorkoutPlanEditor.tsx'),
  ]);

  assert.match(plan, /\/api\/plan\/workouts/);
  assert.match(plan, /expected_version: workout\.workout_version/);
  assert.match(plan, /code === 'PLAN_VERSION_CONFLICT'/);
  assert.match(plan, /code === 'PLAN_HISTORY_IMMUTABLE'/);
  assert.match(plan, /isPraxysOwned\(workout\)/);
  assert.match(plan, /workout\.editable === true/);
  assert.match(plan, /workout\.external_overlap/);
  assert.match(plan, /isRestWorkoutType\(workout\.workout_type\)/);
  assert.match(plan, /disabled=\{editDisabled\}/);
  assert.match(plan, /clearRowError\(workoutKey\(workout\)\)/);
  assert.match(plan, /navigateWindow/);
  assert.match(plan, /Use one planner at a time/);
  assert.match(editor, /Saving will reschedule this workout/);
  assert.match(editor, /Heart-rate minimum/);
  assert.match(editor, /Pace maximum/);
  assert.match(editor, /id: 'plan-workout-duration'/);
  assert.match(editor, /step: 'any'/);
  assert.match(editor, /Convert to rest/);
  assert.match(editor, /Delete this workout\?/);
  assert.match(editor, /workout_structure_version: 'v1'/);
  assert.match(editor, /Convert to structured steps/);
  assert.match(editor, /\/api\/plan\/workouts\/compatibility/);
  assert.match(plan, /seedWorkout/);
  assert.match(plan, /trail_running: t`Trail running`/);
  assert.match(plan, /purposeLabels/);
});

test('miniapp exposes the same canonical workout operations', async () => {
  const [controller, template] = await Promise.all([
    read('../../miniapp/components/managed-plan/index.ts'),
    read('../../miniapp/components/managed-plan/index.wxml'),
  ]);

  assert.match(controller, /apiPost<PlanWorkoutMutationResponse>/);
  assert.match(controller, /apiPut<PlanWorkoutMutationResponse>/);
  assert.match(controller, /apiDelete<PlanWorkoutDeleteResponse>/);
  assert.match(controller, /expected_version: this\.data\.editorExpectedVersion/);
  assert.match(controller, /apiError\.code === 'PLAN_VERSION_CONFLICT'/);
  assert.match(controller, /apiError\.code === 'PLAN_HISTORY_IMMUTABLE'/);
  assert.match(controller, /workout\.editable !== true/);
  assert.match(controller, /candidate\.external_overlap/);
  assert.match(template, /bindtap="onAddWorkout"/);
  assert.match(template, /bindtap="onPreviousWindow"/);
  assert.match(template, /bindtap="onNextWindow"/);
  assert.match(template, /bindtap="onEditWorkout"/);
  assert.match(template, /item\.editDisabled \|\| refreshing \|\| editorSaving/);
  assert.match(template, /bindtap="onConvertToRest"/);
  assert.match(template, /bindtap="onDeleteWorkout"/);
});

test('web and miniapp share the generated mutation contract', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const required = [
    'workout_version?: string',
    'editable?: boolean',
    'mutation_api_version: 1',
    'type PlanMutationErrorCode',
    'minimum_date?: string',
    'interface PlanUploadResponse',
    'interface PlanDayDeleteResponse',
    'type OptionalWorkoutStructureFields',
    'type PlanWorkoutWriteFields',
    'interface PlanWorkoutDeleteResponse',
  ];

  for (const marker of required) {
    assert.match(webTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(miniTypes, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});
