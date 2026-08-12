import type {
  WorkoutIntensityTarget,
  WorkoutStructureRepeatGroup,
  WorkoutStructureStep,
  WorkoutStructureV1,
  WorkoutTermination,
} from '../types/api';

export type WorkoutNode = WorkoutStructureStep | WorkoutStructureRepeatGroup;
export type WorkoutNodePath = [number] | [number, number];
export type TargetKind =
  | 'none'
  | 'power_watts'
  | 'power_cp'
  | 'heart_rate_bpm'
  | 'heart_rate_lthr'
  | 'pace_absolute'
  | 'pace_threshold'
  | 'rpe';

export const PHASE_VALUES = [
  'warmup',
  'work',
  'recovery',
  'rest',
  'cooldown',
  'other',
] as const;

export const TARGET_KINDS: TargetKind[] = [
  'none',
  'power_watts',
  'power_cp',
  'heart_rate_bpm',
  'heart_rate_lthr',
  'pace_absolute',
  'pace_threshold',
  'rpe',
];

const TARGETS: Record<TargetKind, WorkoutIntensityTarget> = {
  none: { metric: 'none', unit: 'none', reference: 'none' },
  power_watts: {
    metric: 'power',
    unit: 'watts',
    reference: 'absolute',
    min: 1,
  },
  power_cp: {
    metric: 'power',
    unit: 'percent_cp',
    reference: 'critical_power',
    min: 1,
  },
  heart_rate_bpm: {
    metric: 'heart_rate',
    unit: 'bpm',
    reference: 'absolute',
    min: 1,
  },
  heart_rate_lthr: {
    metric: 'heart_rate',
    unit: 'percent_lthr',
    reference: 'lthr',
    min: 1,
  },
  pace_absolute: {
    metric: 'pace',
    unit: 'sec_per_km',
    reference: 'absolute',
    min: 1,
  },
  pace_threshold: {
    metric: 'pace',
    unit: 'sec_per_km_delta',
    reference: 'threshold_pace',
    min: 0,
  },
  rpe: {
    metric: 'rpe',
    unit: 'scale_10',
    reference: 'perceived_exertion',
    min: 1,
  },
};

export function createStep(
  overrides: Partial<WorkoutStructureStep> = {},
): WorkoutStructureStep {
  return {
    type: 'step',
    phase: 'other',
    termination: { type: 'open' },
    target: { metric: 'none', unit: 'none', reference: 'none' },
    ...clone(overrides),
  };
}

export function createRepeat(
  overrides: Partial<WorkoutStructureRepeatGroup> = {},
): WorkoutStructureRepeatGroup {
  return {
    type: 'repeat',
    repetitions: 2,
    steps: [createStep()],
    ...clone(overrides),
  };
}

export function cloneStructure(
  structure: WorkoutStructureV1,
): WorkoutStructureV1 {
  return clone(structure);
}

export function targetKind(target: WorkoutIntensityTarget): TargetKind {
  return TARGET_KINDS.find((kind) => {
    const candidate = TARGETS[kind];
    return candidate.metric === target.metric
      && candidate.unit === target.unit
      && candidate.reference === target.reference;
  }) ?? 'none';
}

export function targetForKind(kind: TargetKind): WorkoutIntensityTarget {
  return clone(TARGETS[kind]);
}

export function updateStep(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
  update: Partial<WorkoutStructureStep>,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const step = nodeAt(next, path);
  if (!step || step.type !== 'step') return next;
  Object.assign(step, clone(update));
  return next;
}

export function updateRepeat(
  structure: WorkoutStructureV1,
  rootIndex: number,
  update: Partial<WorkoutStructureRepeatGroup>,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const repeat = next.steps[rootIndex];
  if (!repeat || repeat.type !== 'repeat') return next;
  Object.assign(repeat, clone(update));
  return next;
}

export function insertNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
  node: WorkoutNode,
  after: boolean,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const nodes = siblingsAt(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1] + (after ? 1 : 0);
  nodes.splice(index, 0, clone(node));
  return next;
}

export function duplicateNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): WorkoutStructureV1 {
  const node = nodeAt(structure, path);
  return node
    ? insertNode(structure, path, node, true)
    : cloneStructure(structure);
}

export function moveNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
  direction: 'up' | 'down',
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const nodes = siblingsAt(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1];
  const destination = direction === 'up' ? index - 1 : index + 1;
  if (destination < 0 || destination >= nodes.length) return next;
  [nodes[index], nodes[destination]] = [nodes[destination], nodes[index]];
  return next;
}

export interface RemovedNode {
  node: WorkoutNode;
  parentIndex: number | null;
  index: number;
  previousStructure: WorkoutStructureV1;
}

export function removeNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): { structure: WorkoutStructureV1; removed: RemovedNode | null } {
  const next = cloneStructure(structure);
  const nodes = siblingsAt(next, path);
  if (!nodes) return { structure: next, removed: null };
  const index = path[path.length - 1];
  const [node] = nodes.splice(index, 1);
  return node
    ? {
        structure: next,
        removed: {
          node,
          parentIndex: path.length === 2 ? path[0] : null,
          index,
          previousStructure: cloneStructure(structure),
        },
      }
    : { structure: next, removed: null };
}

export function restoreNode(
  _structure: WorkoutStructureV1,
  removed: RemovedNode,
): WorkoutStructureV1 {
  return cloneStructure(removed.previousStructure);
}

export interface StructureSummary {
  duration: { certainty: 'deterministic'; seconds: number } | { certainty: 'unknown' };
  distance: { certainty: 'deterministic'; meters: number } | { certainty: 'unknown' };
  load: { certainty: 'estimated' | 'unknown' };
  executableSteps: number;
}

export type StructureValidationCode =
  | 'non_rest_requires_step'
  | 'rest_cannot_have_steps'
  | 'repeat_count_invalid'
  | 'repeat_steps_required'
  | 'repeat_label_too_long'
  | 'step_label_too_long'
  | 'step_instructions_too_long'
  | 'time_termination_invalid'
  | 'distance_termination_invalid'
  | 'target_combination_invalid'
  | 'target_bound_missing'
  | 'target_range_invalid'
  | 'target_out_of_range';

export function summarize(
  structure: WorkoutStructureV1,
): StructureSummary {
  const steps = expandSteps(structure);
  let seconds = 0;
  let meters = 0;
  let durationKnown = true;
  let distanceKnown = true;
  for (const step of steps) {
    if (step.termination.type === 'time') {
      seconds += step.termination.seconds;
      distanceKnown = false;
    } else if (step.termination.type === 'distance') {
      meters += step.termination.meters;
      durationKnown = false;
    } else {
      durationKnown = false;
      distanceKnown = false;
    }
  }
  return {
    duration: durationKnown
      ? { certainty: 'deterministic', seconds }
      : { certainty: 'unknown' },
    distance: distanceKnown
      ? { certainty: 'deterministic', meters }
      : { certainty: 'unknown' },
    load: durationKnown && steps.length > 0
      && steps.every((step) => step.target.metric !== 'none')
      ? { certainty: 'estimated' }
      : { certainty: 'unknown' },
    executableSteps: steps.length,
  };
}

/** Format an exact integer-second total without rounding it to minutes. */
export function formatDeterministicDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(
      remainder,
    ).padStart(2, '0')}`;
  }
  return `${minutes}:${String(remainder).padStart(2, '0')}`;
}

/** Format an exact integer-meter total without displaying rounded zero km. */
export function formatDeterministicDistance(meters: number): string {
  if (meters < 1000) return `${meters} m`;
  const kilometers = (meters / 1000).toFixed(3).replace(/\.?0+$/, '');
  return `${kilometers} km`;
}

export function deriveFlat(
  structure: WorkoutStructureV1,
): {
  planned_duration_min: number | null;
  planned_distance_km: number | null;
  target_power_min: number | null;
  target_power_max: number | null;
  target_hr_min: number | null;
  target_hr_max: number | null;
  target_pace_min: string | null;
  target_pace_max: string | null;
} {
  const steps = expandSteps(structure);
  const summary = summarize(structure);
  const fields: {
    planned_duration_min: number | null;
    planned_distance_km: number | null;
    target_power_min: number | null;
    target_power_max: number | null;
    target_hr_min: number | null;
    target_hr_max: number | null;
    target_pace_min: string | null;
    target_pace_max: string | null;
  } = {
    planned_duration_min: summary.duration.certainty === 'deterministic'
      ? round(summary.duration.seconds / 60, 3)
      : null,
    planned_distance_km: summary.distance.certainty === 'deterministic'
      ? round(summary.distance.meters / 1000, 3)
      : null,
    target_power_min: null,
    target_power_max: null,
    target_hr_min: null,
    target_hr_max: null,
    target_pace_min: null,
    target_pace_max: null,
  };
  const signatures = steps.map((step) => targetSignature(step.target));
  if (!signatures.length || signatures.some((value) => value === null)) {
    return fields;
  }
  const [first] = signatures;
  if (!first || signatures.some(
    (value) => JSON.stringify(value) !== JSON.stringify(first),
  )) return fields;
  if (first.metric === 'power') {
    fields.target_power_min = first.min;
    fields.target_power_max = first.max;
  } else if (first.metric === 'heart_rate') {
    fields.target_hr_min = first.min;
    fields.target_hr_max = first.max;
  } else if (first.metric === 'pace') {
    fields.target_pace_min = formatPace(first.min);
    fields.target_pace_max = formatPace(first.max);
  }
  return fields;
}

export function synthesizeFromFlat(input: {
  workoutType: string;
  duration: number | null;
  distance: number | null;
  powerMin: number | null;
  powerMax: number | null;
  hrMin: number | null;
  hrMax: number | null;
  paceMin: string | null;
  paceMax: string | null;
}): WorkoutStructureV1 {
  if (isRest(input.workoutType)) return { steps: [] };
  if (input.duration && input.distance) {
    throw new Error('Choose either a duration or a distance before converting to steps.');
  }
  const termination: WorkoutTermination = input.duration
    ? { type: 'time', seconds: Math.round(input.duration * 60) }
    : input.distance
      ? { type: 'distance', meters: Math.round(input.distance * 1000) }
      : { type: 'open' };
  const target = flatTarget(input);
  return {
    steps: [createStep({ phase: 'other', termination, target })],
  };
}

export function validate(
  structure: WorkoutStructureV1,
  workoutType: string,
): StructureValidationCode | null {
  for (const node of structure.steps) {
    if (node.type !== 'repeat') continue;
    if (
      !Number.isInteger(node.repetitions)
      || node.repetitions < 1
      || node.repetitions > 100
    ) return 'repeat_count_invalid';
    if (!node.steps.length) return 'repeat_steps_required';
    if ((node.label?.trim().length ?? 0) > 80) {
      return 'repeat_label_too_long';
    }
  }
  const steps = expandSteps(structure);
  if (!isRest(workoutType) && !steps.length) {
    return 'non_rest_requires_step';
  }
  if (isRest(workoutType) && steps.length) {
    return 'rest_cannot_have_steps';
  }
  for (const step of steps) {
    if ((step.label?.trim().length ?? 0) > 80) {
      return 'step_label_too_long';
    }
    if ((step.instructions?.trim().length ?? 0) > 1000) {
      return 'step_instructions_too_long';
    }
    if (
      step.termination.type === 'time'
      && (!Number.isInteger(step.termination.seconds)
        || step.termination.seconds < 1
        || step.termination.seconds > 86400)
    ) return 'time_termination_invalid';
    if (
      step.termination.type === 'distance'
      && (!Number.isInteger(step.termination.meters)
        || step.termination.meters < 1
        || step.termination.meters > 1000000)
    ) return 'distance_termination_invalid';
    if (step.target.metric === 'none') {
      if (step.target.min != null || step.target.max != null) {
        return 'target_combination_invalid';
      }
      continue;
    }
    const kind = targetKind(step.target);
    const expected = TARGETS[kind];
    if (
      kind === 'none'
      || expected.metric !== step.target.metric
      || expected.unit !== step.target.unit
      || expected.reference !== step.target.reference
    ) {
      return 'target_combination_invalid';
    }
    if (
      step.target.min == null
      && step.target.max == null
    ) {
      return 'target_bound_missing';
    }
    const bounds: Record<Exclude<TargetKind, 'none'>, [number, number]> = {
      power_watts: [0, 5000],
      power_cp: [0, 300],
      heart_rate_bpm: [0, 300],
      heart_rate_lthr: [0, 200],
      pace_absolute: [0, 7200],
      pace_threshold: [-7200, 7200],
      rpe: [0, 10],
    };
    const [minimum, maximum] = bounds[kind];
    if ([step.target.min, step.target.max].some((value) => (
      value != null
      && (!Number.isFinite(value) || value < minimum || value > maximum)
    ))) return 'target_out_of_range';
    if (
      step.target.min != null
      && step.target.max != null
      && step.target.min > step.target.max
    ) return 'target_range_invalid';
  }
  return null;
}

function siblingsAt(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): WorkoutNode[] | null {
  return path.length === 1
    ? structure.steps
    : childSteps(structure, path[0]);
}

function childSteps(
  structure: WorkoutStructureV1,
  rootIndex: number,
): WorkoutStructureStep[] | null {
  const node = structure.steps[rootIndex];
  return node?.type === 'repeat' ? node.steps : null;
}

function nodeAt(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): WorkoutNode | null {
  return siblingsAt(structure, path)?.[path[path.length - 1]] ?? null;
}

function expandSteps(structure: WorkoutStructureV1): WorkoutStructureStep[] {
  const result: WorkoutStructureStep[] = [];
  for (const node of structure.steps) {
    if (node.type === 'step') {
      result.push(node);
    } else {
      for (let repeat = 0; repeat < node.repetitions; repeat += 1) {
        result.push(...node.steps);
      }
    }
  }
  return result;
}

function targetSignature(
  target: WorkoutIntensityTarget,
): {
  metric: 'none' | 'power' | 'heart_rate' | 'pace';
  min: number | null;
  max: number | null;
} | null {
  const combo = `${target.metric}:${target.unit}:${target.reference}`;
  if (combo === 'none:none:none') {
    return { metric: 'none', min: null, max: null };
  }
  if (combo === 'power:watts:absolute') {
    return { metric: 'power', min: target.min ?? null, max: target.max ?? null };
  }
  if (combo === 'heart_rate:bpm:absolute') {
    return {
      metric: 'heart_rate',
      min: target.min ?? null,
      max: target.max ?? null,
    };
  }
  if (combo === 'pace:sec_per_km:absolute') {
    return { metric: 'pace', min: target.min ?? null, max: target.max ?? null };
  }
  return null;
}

function flatTarget(input: {
  powerMin: number | null;
  powerMax: number | null;
  hrMin: number | null;
  hrMax: number | null;
  paceMin: string | null;
  paceMax: string | null;
}): WorkoutIntensityTarget {
  const paceMin = parsePace(input.paceMin);
  const paceMax = parsePace(input.paceMax);
  const invalidPace = (
    Boolean(input.paceMin?.trim()) && paceMin === null
  ) || (
    Boolean(input.paceMax?.trim()) && paceMax === null
  );
  if (invalidPace) {
    throw new Error('Enter pace as minutes:seconds before converting.');
  }
  const families = [
    input.powerMin !== null || input.powerMax !== null,
    input.hrMin !== null || input.hrMax !== null,
    paceMin !== null || paceMax !== null,
  ].filter(Boolean).length;
  if (families > 1) {
    throw new Error('Choose one target metric before converting to steps.');
  }
  if (input.powerMin !== null || input.powerMax !== null) {
    return bounds(
      { metric: 'power', unit: 'watts', reference: 'absolute' },
      input.powerMin,
      input.powerMax,
    );
  }
  if (input.hrMin !== null || input.hrMax !== null) {
    return bounds(
      { metric: 'heart_rate', unit: 'bpm', reference: 'absolute' },
      input.hrMin,
      input.hrMax,
    );
  }
  if (paceMin !== null || paceMax !== null) {
    return bounds(
      { metric: 'pace', unit: 'sec_per_km', reference: 'absolute' },
      paceMin,
      paceMax,
    );
  }
  return { metric: 'none', unit: 'none', reference: 'none' };
}

function bounds(
  base: Record<string, string>,
  min: number | null,
  max: number | null,
): WorkoutIntensityTarget {
  return {
    ...base,
    ...(min !== null ? { min } : {}),
    ...(max !== null ? { max } : {}),
  } as WorkoutIntensityTarget;
}

function parsePace(value: string | null): number | null {
  const text = value?.trim() ?? '';
  if (!text) return null;
  const [minutesText, secondsText, extra] = text.split(':');
  const minutes = Number(minutesText);
  const seconds = Number(secondsText);
  if (
    extra !== undefined
    || !Number.isInteger(minutes)
    || !Number.isFinite(seconds)
    || minutes < 0
    || seconds < 0
    || seconds >= 60
  ) return null;
  const total = minutes * 60 + seconds;
  return total > 0 ? total : null;
}

function formatPace(value: number | null): string | null {
  if (value === null) return null;
  const rounded = roundHalfEven(value);
  return `${String(Math.floor(rounded / 60)).padStart(2, '0')}:${String(
    rounded % 60,
  ).padStart(2, '0')}`;
}

function roundHalfEven(value: number): number {
  const lower = Math.floor(value);
  const fraction = value - lower;
  const tolerance = Number.EPSILON * Math.max(1, Math.abs(value)) * 2;
  if (Math.abs(fraction - 0.5) <= tolerance) {
    return lower % 2 === 0 ? lower : lower + 1;
  }
  return Math.round(value);
}

function isRest(value: string): boolean {
  return ['rest', 'off'].includes(value.trim().toLowerCase());
}

function round(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
