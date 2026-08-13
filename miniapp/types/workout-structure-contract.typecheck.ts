import type {
  WorkoutIntensityTarget,
  WorkoutStructureRepeatGroup,
  WorkoutStructureStep,
} from './api';

const supported: WorkoutIntensityTarget[] = [
  {
    metric: 'power',
    unit: 'percent_cp',
    reference: 'critical_power',
    min: 90,
    max: 100,
  },
  {
    metric: 'heart_rate',
    unit: 'percent_lthr',
    reference: 'lthr',
    max: 95,
  },
  {
    metric: 'pace',
    unit: 'sec_per_km',
    reference: 'absolute',
    min: 240,
  },
];

// @ts-expect-error Cross-paired units and references are not supported.
const mismatched: WorkoutIntensityTarget = {
  metric: 'pace',
  unit: 'sec_per_km',
  reference: 'threshold_pace',
  min: 0,
};

// @ts-expect-error Non-none targets require at least one numeric bound.
const missingBounds: WorkoutIntensityTarget = {
  metric: 'power',
  unit: 'watts',
  reference: 'absolute',
};

const wordedRestStep: WorkoutStructureStep = {
  type: 'step',
  phase: 'rest',
  label: 'Full recovery',
  instructions: 'Stand easy and reset before the next effort.',
  termination: { type: 'time', seconds: 60 },
  target: {
    metric: 'none',
    unit: 'none',
    reference: 'none',
  },
};
const namedRepeatGroup: WorkoutStructureRepeatGroup = {
  type: 'repeat',
  label: 'Main set',
  repetitions: 3,
  steps: [wordedRestStep],
};
const semanticRepeatIsInvalid: WorkoutStructureStep = {
  type: 'step',
  // @ts-expect-error Repeat is structural, never a step semantic.
  phase: 'repeat',
  termination: { type: 'time', seconds: 60 },
  target: {
    metric: 'none',
    unit: 'none',
    reference: 'none',
  },
};

void [
  supported,
  mismatched,
  missingBounds,
  wordedRestStep,
  namedRepeatGroup,
  semanticRepeatIsInvalid,
];
