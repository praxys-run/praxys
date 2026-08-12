import assert from 'node:assert/strict';
import test from 'node:test';

import {
  commitAllWorkoutEditorTargetInputs,
  commitWorkoutEditorTargetInput,
  createWorkoutEditorStructure,
  createRepeatGroup,
  createStructuredStep,
  deriveFlatFieldsFromStructure,
  duplicateWorkoutEditorNode,
  duplicateWorkoutNode,
  formatDeterministicDistance,
  formatDeterministicDuration,
  insertWorkoutEditorNode,
  insertWorkoutNode,
  moveWorkoutEditorNode,
  moveWorkoutNode,
  removeWorkoutEditorNode,
  removeWorkoutNode,
  restoreRemovedWorkoutEditorNode,
  restoreRemovedWorkoutNode,
  serializeWorkoutEditorStructure,
  setWorkoutEditorTargetInput,
  summarizeWorkoutStructure,
  synthesizeStructureFromFlat,
} from '../src/lib/workout-structure.ts';

function timeStep(phase, seconds, target = {
  metric: 'none',
  unit: 'none',
  reference: 'none',
}) {
  return createStructuredStep({
    phase,
    termination: { type: 'time', seconds },
    target,
  });
}

test('structured editor tree actions preserve repeats, labels, and instructions', () => {
  const warmup = timeStep('warmup', 900);
  const work = {
    ...timeStep('work', 180, {
      metric: 'rpe',
      unit: 'scale_10',
      reference: 'perceived_exertion',
      min: 8,
      max: 9,
    }),
    label: 'Uphill effort',
    instructions: 'Run tall with quick feet.',
  };
  const recovery = {
    ...timeStep('recovery', 120),
    label: 'Float downhill',
  };
  const cooldown = timeStep('cooldown', 600);
  const mainSet = createRepeatGroup({
    label: 'Hill set',
    repetitions: 6,
    steps: [work, recovery],
  });

  let structure = { steps: [warmup, mainSet, cooldown] };
  structure = insertWorkoutNode(
    structure,
    [1, 1],
    timeStep('rest', 30),
    'after',
  );
  structure = duplicateWorkoutNode(structure, [1, 0]);
  structure = moveWorkoutNode(structure, [1, 2], 'up');

  assert.equal(structure.steps[1].type, 'repeat');
  const repeated = structure.steps[1];
  assert.equal(repeated.label, 'Hill set');
  assert.equal(repeated.steps.length, 4);
  assert.equal(repeated.steps[0].label, 'Uphill effort');
  assert.equal(repeated.steps[2].instructions, 'Run tall with quick feet.');

  const removed = removeWorkoutNode(structure, [1, 3]);
  assert.equal(removed.structure.steps[1].type, 'repeat');
  assert.equal(removed.removed?.node.type, 'step');
  assert.deepEqual(removed.path, [1, 3]);
});

test('structure totals stay deterministic only when every termination supports them', () => {
  const structured = {
    steps: [
      timeStep('warmup', 900),
      createRepeatGroup({
        repetitions: 6,
        steps: [
          timeStep('work', 180),
          timeStep('recovery', 120),
        ],
      }),
      timeStep('cooldown', 600),
    ],
  };
  const summary = summarizeWorkoutStructure(structured);
  const flat = deriveFlatFieldsFromStructure(structured);

  assert.deepEqual(summary.duration, {
    certainty: 'deterministic',
    seconds: 3300,
  });
  assert.equal(summary.distance.certainty, 'unknown');
  assert.equal(summary.load.certainty, 'unknown');
  assert.equal(flat.planned_duration_min, 55);

  const open = {
    steps: [
      timeStep('warmup', 300),
      createStructuredStep({
        phase: 'work',
        termination: { type: 'manual' },
        target: { metric: 'none', unit: 'none', reference: 'none' },
      }),
    ],
  };
  assert.equal(
    summarizeWorkoutStructure(open).duration.certainty,
    'unknown',
  );
  assert.equal(
    summarizeWorkoutStructure(open).distance.certainty,
    'unknown',
  );
});

test('legacy flat workouts convert only when the athlete explicitly requests it', () => {
  const structure = synthesizeStructureFromFlat({
    workoutType: 'threshold',
    durationMinutes: 42,
    distanceKm: null,
    powerMin: 220,
    powerMax: 250,
    hrMin: null,
    hrMax: null,
    paceMin: null,
    paceMax: null,
  });

  assert.deepEqual(structure.steps, [{
    type: 'step',
    phase: 'other',
    termination: { type: 'time', seconds: 2520 },
    target: {
      metric: 'power',
      unit: 'watts',
      reference: 'absolute',
      min: 220,
      max: 250,
    },
  }]);
});

test('undo restores the deleted tree instead of guessing a moved repeat parent', () => {
  const original = {
    steps: [
      createRepeatGroup({
        label: 'A',
        steps: [timeStep('work', 60)],
      }),
      createRepeatGroup({
        label: 'B',
        steps: [timeStep('recovery', 60)],
      }),
    ],
  };
  const removed = removeWorkoutNode(original, [0, 0]);
  assert.ok(removed.removed);
  const reordered = moveWorkoutNode(removed.structure, [0], 'down');

  assert.deepEqual(
    restoreRemovedWorkoutNode(reordered, removed.removed),
    original,
  );
});

test('stable editor identities keep repeated moves on the same logical node', () => {
  let editor = createWorkoutEditorStructure({
    steps: [
      { ...timeStep('work', 60), label: 'A' },
      { ...timeStep('work', 60), label: 'B' },
      { ...timeStep('work', 60), label: 'C' },
    ],
  });
  const cId = editor.steps[2].editorId;

  editor = moveWorkoutEditorNode(editor, cId, 'up');
  editor = moveWorkoutEditorNode(editor, cId, 'up');

  assert.deepEqual(editor.steps.map((node) => node.label), ['C', 'A', 'B']);
  assert.equal(editor.steps[0].editorId, cId);
});

test('editor identities survive undo while inserts and duplicates get new ids', () => {
  let editor = createWorkoutEditorStructure({
    steps: [
      { ...timeStep('work', 60), label: 'A' },
      { ...timeStep('work', 60), label: 'B' },
    ],
  });
  const aId = editor.steps[0].editorId;
  const bId = editor.steps[1].editorId;

  editor = duplicateWorkoutEditorNode(editor, bId);
  assert.notEqual(editor.steps[2].editorId, bId);
  editor = insertWorkoutEditorNode(
    editor,
    aId,
    { ...timeStep('recovery', 30), label: 'inserted' },
    'after',
  );
  assert.ok(![aId, bId].includes(editor.steps[1].editorId));

  const removed = removeWorkoutEditorNode(editor, bId);
  assert.ok(removed.removed);
  const restored = restoreRemovedWorkoutEditorNode(
    removed.structure,
    removed.removed,
  );
  assert.equal(restored.steps.find((node) => node.label === 'B')?.editorId, bId);
});

test('raw target drafts commit on blur and never enter serialized API payloads', () => {
  let editor = createWorkoutEditorStructure({
    steps: [timeStep('work', 60, {
      metric: 'power',
      unit: 'percent_cp',
      reference: 'critical_power',
      min: 95,
      max: 100,
    })],
  });
  const nodeId = editor.steps[0].editorId;

  editor = setWorkoutEditorTargetInput(editor, nodeId, 'min', '-');
  assert.equal(editor.steps[0].targetInputs.min, '-');
  assert.equal(serializeWorkoutEditorStructure(editor).steps[0].target.min, 95);
  editor = setWorkoutEditorTargetInput(editor, nodeId, 'min', '.');
  assert.equal(editor.steps[0].targetInputs.min, '.');
  assert.equal(serializeWorkoutEditorStructure(editor).steps[0].target.min, 95);
  editor = setWorkoutEditorTargetInput(editor, nodeId, 'min', '95.');
  assert.equal(editor.steps[0].targetInputs.min, '95.');
  assert.equal(serializeWorkoutEditorStructure(editor).steps[0].target.min, 95);
  editor = setWorkoutEditorTargetInput(editor, nodeId, 'min', '95.5');
  const committed = commitWorkoutEditorTargetInput(
    editor,
    nodeId,
    'min',
  );

  assert.equal(committed.valid, true);
  assert.equal(committed.structure.steps[0].target.min, 95.5);
  const payload = {
    workout_structure: serializeWorkoutEditorStructure(committed.structure),
  };
  assert.doesNotMatch(JSON.stringify(payload), /editorId|targetInputs/);
});

test('hydrated finite scientific notation remains valid when saved untouched', () => {
  const editor = createWorkoutEditorStructure({
    steps: [timeStep('work', 60, {
      metric: 'power',
      unit: 'percent_cp',
      reference: 'critical_power',
      min: 1e-7,
      max: 1,
    })],
  });

  assert.equal(editor.steps[0].targetInputs.min, '1e-7');
  const committed = commitAllWorkoutEditorTargetInputs(editor);
  assert.equal(committed.valid, true);
  assert.equal(
    serializeWorkoutEditorStructure(committed.structure).steps[0].target.min,
    1e-7,
  );
});

test('exact totals retain seconds and meters without rounded claims', () => {
  assert.equal(formatDeterministicDuration(90), '1:30');
  assert.equal(formatDeterministicDuration(1), '0:01');
  assert.equal(formatDeterministicDistance(1), '1 m');
  assert.equal(formatDeterministicDistance(1234), '1.234 km');
});

test('pace flat projections use the backend half-even rounding contract', () => {
  const projected = deriveFlatFieldsFromStructure({
    steps: [timeStep('work', 60, {
      metric: 'pace',
      unit: 'sec_per_km',
      reference: 'absolute',
      min: 320.5,
      max: 321.5,
    })],
  });

  assert.equal(projected.target_pace_min, '05:20');
  assert.equal(projected.target_pace_max, '05:22');
});
