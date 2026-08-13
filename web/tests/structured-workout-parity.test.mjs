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
    miniStyles,
    webTypes,
    miniTypes,
    webSlider,
  ] = (
    await Promise.all([
      read('../src/components/WorkoutPlanEditor.tsx'),
      read('../src/components/WorkoutStructureEditor.tsx'),
      read('../../miniapp/components/managed-plan/index.ts'),
      read('../../miniapp/components/managed-plan/index.wxml'),
      read('../../miniapp/components/managed-plan/index.scss'),
      read('../src/types/api.ts'),
      read('../../miniapp/types/api.ts'),
      read('../src/components/ui/slider.tsx'),
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
    'loading && config == null',
    'initialUnitSystem',
    "'unsupported'",
  ]) {
    assert.match(webEditor, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }

  for (const marker of [
    'editorStructured',
    'onStructuredAction',
    'onStructuredTargetBlur',
    'onStructuredDistanceBlur',
    'onStructuredPhaseChange',
    'onStructuredTerminationChange',
    'onStructuredTargetChange',
    'onStructuredRangeChange',
    'onSelectStructuredNode',
    'onSelectCompatibilityReason',
    'onUndoStructuredDelete',
    'onConvertLegacyToStructured',
    'onDuplicateWorkout',
    'editorLastNonRestStructure',
    'editorUnsupportedStructure',
    '_compatibilityRequestId',
    '/api/plan/workouts/compatibility',
    'setCustomTabBarHidden',
    'selectedStructureView',
    'workoutEditorIdForCompatibilityPath',
    'compatibilityData',
    'editorSelectedCompatibility',
    'editorOtherCompatibility',
    'selectStructuredNode',
    'scrollEditorToNode',
    'scrollIntoView',
  ]) {
    assert.match(miniController, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  for (const marker of [
    'bindtap="onStructuredAction"',
    'bindtap="onSelectStructuredNode"',
    'bindtap="onSelectCompatibilityReason"',
    'id="managed-plan-inspector-{{node.editorId}}"',
    'bindtap="onAddStructuredRepeat"',
    'bindtap="onUndoStructuredDelete"',
    'bindtap="onDuplicateWorkout"',
    'bindchanging="onStructuredRangeChange"',
    'data-field="durationHours"',
    'data-field="durationMinutes"',
    'data-field="durationSeconds"',
    'data-field="distanceValue"',
    'bindblur="onStructuredDistanceBlur"',
    'value="{{node.durationHours}}"',
    'value="{{node.durationMinutes}}"',
    'value="{{node.durationSeconds}}"',
    'value="{{node.distanceValue}}"',
    'wx:if="{{node.sliderEnabled}}"',
    'min="{{node.sliderMinimum}}"',
    'max="{{node.sliderMaximum}}"',
    'step="{{node.sliderStep}}"',
    'value="{{node.sliderLow}}"',
    'value="{{node.sliderHigh}}"',
    '{{node.distanceUnit}}',
    'managed-plan__profile-map',
    'managed-plan__outline-list',
    'managed-plan__compatibility-provider--{{editorSelectedCompatibility.tone}}',
    'bindtap="onToggleOtherCompatibility"',
    'managed-plan__editor-scroll',
    'env(safe-area-inset-bottom)',
  ]) {
    const source = marker.includes('safe-area')
      ? miniStyles
      : miniTemplate;
    assert.match(source, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
  const targetInputs = miniTemplate.match(
    /<input[^>]*data-field="target(?:Min|Max)"[^>]*\/>/g,
  ) ?? [];
  assert.equal(targetInputs.length, 2);
  for (const input of targetInputs) {
    assert.match(input, /type="text"/);
    assert.match(input, /data-editor-id=/);
    assert.match(input, /bindblur="onStructuredTargetBlur"/);
    assert.doesNotMatch(input, /type="(?:number|digit)"/);
  }
  assert.match(miniTemplate, /wx:key="editorId"/);
  assert.match(miniTemplate, /data-editor-id="{{node\.editorId}}"/);
  assert.doesNotMatch(miniTemplate, /data-editor-id="{{child\.editorId}}"/);
  assert.doesNotMatch(miniTemplate, /node\.durationParts/);
  assert.doesNotMatch(miniTemplate, /node\.termination\.distanceInput/);
  assert.doesNotMatch(miniTemplate, /node\.slider\./);
  assert.match(
    miniStyles,
    /\.managed-plan__timeline\s*\{[^}]*height:\s*\d+rpx;/,
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
  assert.match(miniController, /setWorkoutEditorTargetInput/);
  assert.match(miniController, /commitWorkoutEditorTargetInput/);
  assert.match(miniController, /serializeWorkoutEditorStructure/);
  assert.match(miniController, /editorStructureView:\s*selectedStructureView/);
  assert.match(miniController, /const tone:\s*CompatibilityView\['tone'\]/);
  assert.match(webStructureEditor, /value=\{step\.targetInputs\[bound\]\}/);
  assert.match(webStructureEditor, /type="text"/);
  assert.match(webStructureEditor, /onBlur=\{\(\) => onBlur/);
  assert.match(webStructureEditor, /Workout profile/);
  assert.match(webStructureEditor, /Workout order/);
  assert.match(webStructureEditor, /RangeSlider/);
  assert.match(
    webStructureEditor,
    /onValueChange=\{\(values, bound\) => onRange/,
  );
  assert.match(webStructureEditor, /workoutEditorIdForCompatibilityPath/);
  assert.match(webSlider, /focus-within:ring-3/);

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
  assert.equal(mini.formatDeterministicDistance(1609.344, 'imperial'), '1 mi');
  assert.equal(mini.parseWorkoutDistanceInput('0.25', 'imperial'), 402);
  assert.equal(mini.formatWorkoutPaceInput(300, 'metric'), '5:00');
  const seventeenMinuteMile = mini.parseWorkoutPaceInput(
    '17:00',
    'imperial',
  );
  assert.equal(
    mini.formatWorkoutPaceInput(seventeenMinuteMile, 'imperial'),
    '17:00',
  );
  assert.ok(Math.abs(
    mini.parseWorkoutPaceInput('8:02.803', 'imperial') - 300,
  ) < 0.001);

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

test('miniapp compatibility paths resolve to stable editor selections', async () => {
  const mini = await import(
    '../../miniapp/utils/workout-structure.ts'
  );
  const editor = mini.createWorkoutEditorStructure({
    steps: [{
      type: 'repeat',
      repetitions: 3,
      steps: [{
        type: 'step',
        phase: 'work',
        termination: { type: 'time', seconds: 60 },
        target: { metric: 'none', unit: 'none', reference: 'none' },
      }],
    }],
  });

  assert.equal(
    mini.workoutEditorIdForCompatibilityPath(
      editor,
      'steps[0].steps[0].target',
    ),
    editor.steps[0].steps[0].editorId,
  );
});

test('miniapp editor identities and raw target drafts stay editor-only', async () => {
  const mini = await import(
    '../../miniapp/utils/workout-structure.ts'
  );
  const step = (label, target) => ({
    type: 'step',
    phase: 'work',
    label,
    termination: { type: 'time', seconds: 60 },
    target,
  });
  let editor = mini.createWorkoutEditorStructure({
    steps: [
      step('A', { metric: 'none', unit: 'none', reference: 'none' }),
      step('B', { metric: 'none', unit: 'none', reference: 'none' }),
      step('C', { metric: 'none', unit: 'none', reference: 'none' }),
    ],
  });
  const cId = editor.steps[2].editorId;
  editor = mini.moveWorkoutEditorNode(editor, cId, 'up');
  editor = mini.moveWorkoutEditorNode(editor, cId, 'up');
  assert.deepEqual(editor.steps.map((node) => node.label), ['C', 'A', 'B']);
  assert.equal(editor.steps[0].editorId, cId);

  const cases = [
    {
      target: {
        metric: 'power',
        unit: 'percent_cp',
        reference: 'critical_power',
        min: 95,
      },
      raw: '95.5',
      value: 95.5,
    },
    {
      target: {
        metric: 'rpe',
        unit: 'scale_10',
        reference: 'perceived_exertion',
        min: 7,
      },
      raw: '7.5',
      value: 7.5,
    },
    {
      target: {
        metric: 'pace',
        unit: 'sec_per_km_delta',
        reference: 'threshold_pace',
        min: 0,
      },
      raw: '-10',
      value: -10,
    },
  ];
  for (const item of cases) {
    let targetEditor = mini.createWorkoutEditorStructure({
      steps: [step('target', item.target)],
    });
    const id = targetEditor.steps[0].editorId;
    for (const partial of ['-', '.', `${item.raw}.`]) {
      targetEditor = mini.setWorkoutEditorTargetInput(
        targetEditor,
        id,
        'min',
        partial,
      );
      assert.equal(targetEditor.steps[0].targetInputs.min, partial);
      assert.equal(
        mini.serializeWorkoutEditorStructure(targetEditor).steps[0].target.min,
        item.target.min,
      );
    }
    targetEditor = mini.setWorkoutEditorTargetInput(
      targetEditor,
      id,
      'min',
      item.raw,
    );
    const committed = mini.commitWorkoutEditorTargetInput(
      targetEditor,
      id,
      'min',
    );
    assert.equal(committed.valid, true);
    assert.equal(committed.structure.steps[0].target.min, item.value);
    assert.doesNotMatch(
      JSON.stringify(mini.serializeWorkoutEditorStructure(committed.structure)),
      /editorId|targetInputs/,
    );
  }

  const tiny = mini.createWorkoutEditorStructure({
    steps: [step('tiny', {
      metric: 'power',
      unit: 'percent_cp',
      reference: 'critical_power',
      min: 1e-7,
      max: 1,
    })],
  });
  assert.equal(tiny.steps[0].targetInputs.min, '1e-7');
  const committedTiny = mini.commitAllWorkoutEditorTargetInputs(tiny);
  assert.equal(committedTiny.valid, true);
  assert.equal(
    mini.serializeWorkoutEditorStructure(
      committedTiny.structure,
    ).steps[0].target.min,
    1e-7,
  );
});
