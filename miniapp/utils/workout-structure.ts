import type {
  UnitSystem,
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

export interface WorkoutEditorTargetInputs {
  min: string;
  max: string;
  minInvalid: boolean;
  maxInvalid: boolean;
}

export interface WorkoutEditorStep extends WorkoutStructureStep {
  /** Stable only for one editor session; stripped before every API request. */
  editorId: string;
  /** Raw drafts preserve partial signed/decimal input until blur or save. */
  targetInputs: WorkoutEditorTargetInputs;
}

export interface WorkoutEditorRepeat extends Omit<
  WorkoutStructureRepeatGroup,
  'steps'
> {
  /** Stable only for one editor session; stripped before every API request. */
  editorId: string;
  steps: WorkoutEditorStep[];
}

export type WorkoutEditorNode = WorkoutEditorStep | WorkoutEditorRepeat;

export interface WorkoutEditorStructureV1 {
  steps: WorkoutEditorNode[];
}

export interface RemovedWorkoutEditorNode {
  node: WorkoutEditorNode;
  previousStructure: WorkoutEditorStructureV1;
}

export interface RemoveWorkoutEditorNodeResult {
  structure: WorkoutEditorStructureV1;
  removed: RemovedWorkoutEditorNode | null;
}

let workoutEditorIdSequence = 0;
const KM_PER_MILE = 1.609344;
const METERS_PER_MILE = 1609.344;

function nextWorkoutEditorId(): string {
  workoutEditorIdSequence += 1;
  return `workout-editor-node-${workoutEditorIdSequence}`;
}

function targetInputsFor(
  target: WorkoutIntensityTarget,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorTargetInputs {
  const kind = targetKind(target);
  const formatBound = (value: number | null | undefined): string => {
    if (value == null) return '';
    if (kind === 'pace_absolute') {
      return formatWorkoutPaceInput(value, unitSystem);
    }
    if (kind === 'pace_threshold' && unitSystem === 'imperial') {
      return trimDecimal(value * KM_PER_MILE, 6);
    }
    return value.toString();
  };
  return {
    min: formatBound(target.min),
    max: formatBound(target.max),
    minInvalid: false,
    maxInvalid: false,
  };
}

function createWorkoutEditorStepFromCanonical(
  step: WorkoutStructureStep,
  createId: () => string,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStep {
  return {
    ...clone(step),
    editorId: createId(),
    targetInputs: targetInputsFor(step.target, unitSystem),
  };
}

function createWorkoutEditorNodeFromCanonical(
  node: WorkoutNode,
  createId: () => string,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorNode {
  if (node.type === 'step') {
    return createWorkoutEditorStepFromCanonical(node, createId, unitSystem);
  }
  return {
    ...clone(node),
    editorId: createId(),
    steps: node.steps.map((step) => (
      createWorkoutEditorStepFromCanonical(step, createId, unitSystem)
    )),
  };
}

/** Hydrate canonical workout data with stable, API-excluded editor state. */
export function createWorkoutEditorStructure(
  structure: WorkoutStructureV1,
  createId: () => string = nextWorkoutEditorId,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStructureV1 {
  return {
    steps: structure.steps.map((node) => (
      createWorkoutEditorNodeFromCanonical(node, createId, unitSystem)
    )),
  };
}

export function createWorkoutEditorStep(
  overrides: Partial<WorkoutStructureStep> = {},
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStep {
  return createWorkoutEditorStepFromCanonical(
    createStep(overrides),
    nextWorkoutEditorId,
    unitSystem,
  );
}

export function createWorkoutEditorRepeat(
  overrides: Partial<WorkoutStructureRepeatGroup> = {},
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorRepeat {
  return createWorkoutEditorNodeFromCanonical(
    createRepeat(overrides),
    nextWorkoutEditorId,
    unitSystem,
  ) as WorkoutEditorRepeat;
}

function serializeWorkoutEditorNode(node: WorkoutEditorNode): WorkoutNode {
  if (node.type === 'step') {
    const {
      editorId: _editorId,
      targetInputs: _targetInputs,
      ...step
    } = node;
    return clone(step) as WorkoutStructureStep;
  }
  const {
    editorId: _editorId,
    steps,
    ...repeat
  } = node;
  return {
    ...clone(repeat),
    steps: steps.map((step) => (
      serializeWorkoutEditorNode(step) as WorkoutStructureStep
    )),
  };
}

/** Return canonical API data with all editor identities and drafts removed. */
export function serializeWorkoutEditorStructure(
  structure: WorkoutEditorStructureV1,
): WorkoutStructureV1 {
  return {
    steps: structure.steps.map(serializeWorkoutEditorNode),
  };
}

function cloneWorkoutEditorStructure(
  structure: WorkoutEditorStructureV1,
): WorkoutEditorStructureV1 {
  return clone(structure);
}

export function workoutEditorNodePath(
  structure: WorkoutEditorStructureV1,
  editorId: string,
): WorkoutNodePath | null {
  for (let rootIndex = 0; rootIndex < structure.steps.length; rootIndex += 1) {
    const node = structure.steps[rootIndex];
    if (node.editorId === editorId) return [rootIndex];
    if (node.type !== 'repeat') continue;
    const childIndex = node.steps.findIndex(
      (step) => step.editorId === editorId,
    );
    if (childIndex >= 0) return [rootIndex, childIndex];
  }
  return null;
}

function workoutEditorNodesAtPath(
  structure: WorkoutEditorStructureV1,
  path: WorkoutNodePath,
): WorkoutEditorNode[] | null {
  if (path.length === 1) return structure.steps;
  const parent = structure.steps[path[0]];
  return parent?.type === 'repeat' ? parent.steps : null;
}

function workoutEditorNodeAtPath(
  structure: WorkoutEditorStructureV1,
  path: WorkoutNodePath,
): WorkoutEditorNode | null {
  return workoutEditorNodesAtPath(structure, path)?.[
    path[path.length - 1]
  ] ?? null;
}

export function updateWorkoutEditorStep(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  update: Partial<WorkoutStructureStep>,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return next;
  const step = workoutEditorNodeAtPath(next, path);
  if (!step || step.type !== 'step') return next;
  Object.assign(step, clone(update));
  if (update.target !== undefined) {
    step.targetInputs = targetInputsFor(step.target, unitSystem);
  }
  return next;
}

export function updateWorkoutEditorRepeat(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  update: Partial<Omit<WorkoutEditorRepeat, 'editorId'>>,
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path || path.length !== 1) return next;
  const repeat = next.steps[path[0]];
  if (!repeat || repeat.type !== 'repeat') return next;
  Object.assign(repeat, clone(update));
  return next;
}

export function insertWorkoutEditorNode(
  structure: WorkoutEditorStructureV1,
  targetEditorId: string,
  node: WorkoutNode,
  after: boolean,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, targetEditorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return next;
  const nodes = workoutEditorNodesAtPath(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1] + (after ? 1 : 0);
  nodes.splice(
    index,
    0,
    createWorkoutEditorNodeFromCanonical(
      node,
      nextWorkoutEditorId,
      unitSystem,
    ),
  );
  return next;
}

export function duplicateWorkoutEditorNode(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, editorId);
  if (!path) return cloneWorkoutEditorStructure(structure);
  const node = workoutEditorNodeAtPath(structure, path);
  return node
    ? insertWorkoutEditorNode(
        structure,
        editorId,
        serializeWorkoutEditorNode(node),
        true,
        unitSystem,
      )
    : cloneWorkoutEditorStructure(structure);
}

export function moveWorkoutEditorNode(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  direction: 'up' | 'down',
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return next;
  const nodes = workoutEditorNodesAtPath(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1];
  const destination = direction === 'up' ? index - 1 : index + 1;
  if (destination < 0 || destination >= nodes.length) return next;
  [nodes[index], nodes[destination]] = [nodes[destination], nodes[index]];
  return next;
}

export function removeWorkoutEditorNode(
  structure: WorkoutEditorStructureV1,
  editorId: string,
): RemoveWorkoutEditorNodeResult {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return { structure: next, removed: null };
  const nodes = workoutEditorNodesAtPath(next, path);
  if (!nodes) return { structure: next, removed: null };
  const [node] = nodes.splice(path[path.length - 1], 1);
  return node
    ? {
        structure: next,
        removed: {
          node,
          previousStructure: cloneWorkoutEditorStructure(structure),
        },
      }
    : { structure: next, removed: null };
}

export function restoreRemovedWorkoutEditorNode(
  _structure: WorkoutEditorStructureV1,
  removed: RemovedWorkoutEditorNode,
): WorkoutEditorStructureV1 {
  return cloneWorkoutEditorStructure(removed.previousStructure);
}

export function setWorkoutEditorTargetInput(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  bound: 'min' | 'max',
  value: string,
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return next;
  const step = workoutEditorNodeAtPath(next, path);
  if (!step || step.type !== 'step') return next;
  step.targetInputs[bound] = value;
  if (bound === 'min') step.targetInputs.minInvalid = false;
  else step.targetInputs.maxInvalid = false;
  return next;
}

const COMPLETE_DECIMAL = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function commitTargetInput(
  step: WorkoutEditorStep,
  bound: 'min' | 'max',
  unitSystem: UnitSystem = 'metric',
): boolean {
  const raw = step.targetInputs[bound].trim();
  const kind = targetKind(step.target);
  const pace = kind === 'pace_absolute' && raw !== ''
    ? parseWorkoutPaceInput(raw, unitSystem)
    : null;
  const valid = raw === ''
    || (kind === 'pace_absolute'
      ? pace !== null
      : COMPLETE_DECIMAL.test(raw));
  const displayValue = raw === ''
    ? undefined
    : kind === 'pace_absolute'
      ? pace ?? Number.NaN
      : Number(raw);
  const parsed = kind === 'pace_threshold'
    && unitSystem === 'imperial'
    && displayValue !== undefined
    ? displayValue / KM_PER_MILE
    : displayValue;
  const finite = parsed === undefined || Number.isFinite(parsed);
  if (!valid || !finite) {
    if (bound === 'min') step.targetInputs.minInvalid = true;
    else step.targetInputs.maxInvalid = true;
    return false;
  }
  const target = { ...step.target } as Record<string, unknown>;
  if (parsed === undefined) delete target[bound];
  else target[bound] = parsed;
  step.target = target as WorkoutIntensityTarget;
  if (bound === 'min') step.targetInputs.minInvalid = false;
  else step.targetInputs.maxInvalid = false;
  return true;
}

export function commitWorkoutEditorTargetInput(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  bound: 'min' | 'max',
  unitSystem: UnitSystem = 'metric',
): { structure: WorkoutEditorStructureV1; valid: boolean } {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return { structure: next, valid: false };
  const step = workoutEditorNodeAtPath(next, path);
  if (!step || step.type !== 'step') {
    return { structure: next, valid: false };
  }
  return {
    structure: next,
    valid: commitTargetInput(step, bound, unitSystem),
  };
}

export function commitAllWorkoutEditorTargetInputs(
  structure: WorkoutEditorStructureV1,
  unitSystem: UnitSystem = 'metric',
): { structure: WorkoutEditorStructureV1; valid: boolean } {
  const next = cloneWorkoutEditorStructure(structure);
  let valid = true;
  for (const node of next.steps) {
    const steps = node.type === 'step' ? [node] : node.steps;
    for (const step of steps) {
      if (step.target.metric === 'none') continue;
      valid = commitTargetInput(step, 'min', unitSystem) && valid;
      valid = commitTargetInput(step, 'max', unitSystem) && valid;
    }
  }
  return { structure: next, valid };
}

/** Resolve a backend compatibility path to the stable editor node it names. */
export function workoutEditorIdForCompatibilityPath(
  structure: WorkoutEditorStructureV1,
  path: string | null | undefined,
): string | null {
  const match = path?.match(
    /^steps\[(\d+)\](?:\.steps\[(\d+)\])?/,
  );
  if (!match) return null;
  const root = structure.steps[Number(match[1])];
  if (!root) return null;
  if (match[2] == null) return root.editorId;
  return root.type === 'repeat'
    ? root.steps[Number(match[2])]?.editorId ?? null
    : null;
}

export function validateWorkoutEditorStructure(
  structure: WorkoutEditorStructureV1,
  workoutType: string,
): StructureValidationCode | null {
  const hasInvalidInput = structure.steps.some((node) => {
    const steps = node.type === 'step' ? [node] : node.steps;
    return steps.some((step) => (
      step.targetInputs.minInvalid || step.targetInputs.maxInvalid
    ));
  });
  return hasInvalidInput
    ? 'target_input_invalid'
    : validate(serializeWorkoutEditorStructure(structure), workoutType);
}

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
  | 'target_input_invalid'
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
export function formatDeterministicDistance(
  meters: number,
  unitSystem: UnitSystem = 'metric',
): string {
  if (unitSystem === 'imperial') {
    if (meters < METERS_PER_MILE) {
      return `${trimDecimal(meters / 0.9144, 1)} yd`;
    }
    return `${trimDecimal(meters / METERS_PER_MILE, 3)} mi`;
  }
  if (meters < 1000) return `${meters} m`;
  const kilometers = (meters / 1000).toFixed(3).replace(/\.?0+$/, '');
  return `${kilometers} km`;
}

export function formatWorkoutDistanceInput(
  meters: number,
  unitSystem: UnitSystem = 'metric',
): { value: string; unit: 'm' | 'mi' } {
  return unitSystem === 'imperial'
    ? {
        value: trimDecimal(meters / METERS_PER_MILE, 4),
        unit: 'mi',
      }
    : { value: meters.toString(), unit: 'm' };
}

export function parseWorkoutDistanceInput(
  value: string,
  unitSystem: UnitSystem = 'metric',
): number | null {
  if (!COMPLETE_DECIMAL.test(value.trim())) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return Math.round(
    unitSystem === 'imperial' ? parsed * METERS_PER_MILE : parsed,
  );
}

export function formatWorkoutPaceInput(
  secondsPerKm: number,
  unitSystem: UnitSystem = 'metric',
): string {
  const visible = unitSystem === 'imperial'
    ? secondsPerKm * KM_PER_MILE
    : secondsPerKm;
  const roundedVisible = Math.round(visible * 1000) / 1000;
  const minutes = Math.floor(roundedVisible / 60);
  const seconds = roundedVisible - minutes * 60;
  const rawSeconds = trimDecimal(seconds, 3);
  const secondsText = seconds < 10 ? `0${rawSeconds}` : rawSeconds;
  return `${minutes}:${secondsText}`;
}

export function parseWorkoutPaceInput(
  value: string,
  unitSystem: UnitSystem = 'metric',
): number | null {
  const raw = value.trim();
  if (!raw) return null;
  const parts = raw.split(':');
  let visibleSeconds: number;
  if (parts.length === 1 && COMPLETE_DECIMAL.test(raw)) {
    visibleSeconds = Number(raw);
  } else if (parts.length === 2) {
    const minutes = Number(parts[0]);
    const seconds = Number(parts[1]);
    if (
      !Number.isInteger(minutes)
      || minutes < 0
      || !Number.isFinite(seconds)
      || seconds < 0
      || seconds >= 60
    ) return null;
    visibleSeconds = minutes * 60 + seconds;
  } else {
    return null;
  }
  if (!Number.isFinite(visibleSeconds) || visibleSeconds <= 0) return null;
  return unitSystem === 'imperial'
    ? visibleSeconds / KM_PER_MILE
    : visibleSeconds;
}

function trimDecimal(value: number, decimals: number): string {
  return value.toFixed(decimals).replace(/\.?0+$/, '');
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
