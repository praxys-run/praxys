import type {
  UnitSystem,
  WorkoutIntensityTarget,
  WorkoutStructureRepeatGroup,
  WorkoutStructureStep,
  WorkoutStructureV1,
  WorkoutTermination,
} from '@/types/api';

export type WorkoutNode = WorkoutStructureStep | WorkoutStructureRepeatGroup;
export type WorkoutNodePath = readonly [number] | readonly [number, number];
export type WorkoutMoveDirection = 'up' | 'down';
export type WorkoutInsertPosition = 'before' | 'after';

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
    ...cloneNode(step),
    editorId: createId(),
    targetInputs: targetInputsFor(step.target, unitSystem),
  } as WorkoutEditorStep;
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
    ...node,
    editorId: createId(),
    steps: node.steps.map((step) => (
      createWorkoutEditorStepFromCanonical(step, createId, unitSystem)
    )),
  };
}

/** Hydrate canonical workout data with stable, non-serializable editor state. */
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
    createStructuredStep(overrides),
    nextWorkoutEditorId,
    unitSystem,
  );
}

export function createWorkoutEditorRepeat(
  overrides: Partial<WorkoutStructureRepeatGroup> = {},
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorRepeat {
  return createWorkoutEditorNodeFromCanonical(
    createRepeatGroup(overrides),
    nextWorkoutEditorId,
    unitSystem,
  ) as WorkoutEditorRepeat;
}

function serializeWorkoutEditorNode(node: WorkoutEditorNode): WorkoutNode {
  if (node.type === 'step') {
    const step = { ...node };
    Reflect.deleteProperty(step, 'editorId');
    Reflect.deleteProperty(step, 'targetInputs');
    return cloneNode(step as WorkoutStructureStep);
  }
  const repeat = {
    ...node,
    steps: node.steps.map((step) => (
      serializeWorkoutEditorNode(step) as WorkoutStructureStep
    )),
  };
  Reflect.deleteProperty(repeat, 'editorId');
  return repeat;
}

/** Return the canonical API structure, explicitly dropping all editor state. */
export function serializeWorkoutEditorStructure(
  structure: WorkoutEditorStructureV1,
): WorkoutStructureV1 {
  return {
    steps: structure.steps.map(serializeWorkoutEditorNode),
  };
}

function cloneWorkoutEditorNode(node: WorkoutEditorNode): WorkoutEditorNode {
  if (node.type === 'step') {
    return {
      ...node,
      termination: { ...node.termination },
      target: { ...node.target } as WorkoutIntensityTarget,
      targetInputs: { ...node.targetInputs },
    };
  }
  return {
    ...node,
    steps: node.steps.map((step) => (
      cloneWorkoutEditorNode(step) as WorkoutEditorStep
    )),
  };
}

function cloneWorkoutEditorStructure(
  structure: WorkoutEditorStructureV1,
): WorkoutEditorStructureV1 {
  return {
    steps: structure.steps.map(cloneWorkoutEditorNode),
  };
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
  Object.assign(step, cloneValue(update));
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
  Object.assign(repeat, cloneValue(update));
  return next;
}

export function insertWorkoutEditorNode(
  structure: WorkoutEditorStructureV1,
  targetEditorId: string,
  node: WorkoutNode,
  position: WorkoutInsertPosition,
  unitSystem: UnitSystem = 'metric',
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, targetEditorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return next;
  const nodes = workoutEditorNodesAtPath(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1];
  nodes.splice(
    position === 'before' ? index : index + 1,
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
        'after',
        unitSystem,
      )
    : cloneWorkoutEditorStructure(structure);
}

export function moveWorkoutEditorNode(
  structure: WorkoutEditorStructureV1,
  editorId: string,
  direction: WorkoutMoveDirection,
): WorkoutEditorStructureV1 {
  const path = workoutEditorNodePath(structure, editorId);
  const next = cloneWorkoutEditorStructure(structure);
  if (!path) return next;
  const nodes = workoutEditorNodesAtPath(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1];
  const replacementIndex = direction === 'up' ? index - 1 : index + 1;
  if (replacementIndex < 0 || replacementIndex >= nodes.length) return next;
  [nodes[index], nodes[replacementIndex]] = [
    nodes[replacementIndex],
    nodes[index],
  ];
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
): string[] {
  const hasInvalidInput = structure.steps.some((node) => {
    const steps = node.type === 'step' ? [node] : node.steps;
    return steps.some((step) => (
      step.targetInputs.minInvalid || step.targetInputs.maxInvalid
    ));
  });
  return [
    ...(hasInvalidInput ? ['Enter a complete target number.'] : []),
    ...validateWorkoutStructure(
      serializeWorkoutEditorStructure(structure),
      workoutType,
    ),
  ];
}

export interface WorkoutStructureFlatFields {
  planned_duration_min: number | null;
  planned_distance_km: number | null;
  target_power_min: number | null;
  target_power_max: number | null;
  target_hr_min: number | null;
  target_hr_max: number | null;
  target_pace_min: string | null;
  target_pace_max: string | null;
}

export type WorkoutTotal =
  | { certainty: 'deterministic'; seconds: number }
  | { certainty: 'unknown' };

export type WorkoutDistanceTotal =
  | { certainty: 'deterministic'; meters: number }
  | { certainty: 'unknown' };

export interface WorkoutStructureSummary {
  duration: WorkoutTotal;
  distance: WorkoutDistanceTotal;
  /** A certainty label, never an invented physiological load value. */
  load: { certainty: 'estimated' | 'unknown' };
  executableSteps: number;
}

export interface RemovedWorkoutNode {
  node: WorkoutNode;
  parentPath: readonly [number] | null;
  index: number;
  previousStructure: WorkoutStructureV1;
}

export interface RemoveWorkoutNodeResult {
  structure: WorkoutStructureV1;
  removed: RemovedWorkoutNode | null;
  path: WorkoutNodePath | null;
}

const TARGET_COMBINATIONS = {
  none: {
    metric: 'none',
    unit: 'none',
    reference: 'none',
  },
  power_watts: {
    metric: 'power',
    unit: 'watts',
    reference: 'absolute',
  },
  power_cp: {
    metric: 'power',
    unit: 'percent_cp',
    reference: 'critical_power',
  },
  heart_rate_bpm: {
    metric: 'heart_rate',
    unit: 'bpm',
    reference: 'absolute',
  },
  heart_rate_lthr: {
    metric: 'heart_rate',
    unit: 'percent_lthr',
    reference: 'lthr',
  },
  pace_absolute: {
    metric: 'pace',
    unit: 'sec_per_km',
    reference: 'absolute',
  },
  pace_threshold: {
    metric: 'pace',
    unit: 'sec_per_km_delta',
    reference: 'threshold_pace',
  },
  rpe: {
    metric: 'rpe',
    unit: 'scale_10',
    reference: 'perceived_exertion',
  },
} as const;

export type WorkoutTargetKind = keyof typeof TARGET_COMBINATIONS;

export const WORKOUT_TARGET_KINDS = Object.keys(
  TARGET_COMBINATIONS,
) as WorkoutTargetKind[];

export function targetKind(target: WorkoutIntensityTarget): WorkoutTargetKind {
  const match = WORKOUT_TARGET_KINDS.find((kind) => {
    const candidate = TARGET_COMBINATIONS[kind];
    return candidate.metric === target.metric
      && candidate.unit === target.unit
      && candidate.reference === target.reference;
  });
  return match ?? 'none';
}

export function targetForKind(kind: WorkoutTargetKind): WorkoutIntensityTarget {
  const target = TARGET_COMBINATIONS[kind];
  if (kind === 'none') {
    return { metric: 'none', unit: 'none', reference: 'none' };
  }
  const defaults: Record<Exclude<WorkoutTargetKind, 'none'>, number> = {
    power_watts: 1,
    power_cp: 1,
    heart_rate_bpm: 1,
    heart_rate_lthr: 1,
    pace_absolute: 1,
    pace_threshold: 0,
    rpe: 1,
  };
  return {
    ...target,
    min: defaults[kind],
  } as WorkoutIntensityTarget;
}

export function createStructuredStep(
  overrides: Partial<WorkoutStructureStep> = {},
): WorkoutStructureStep {
  return {
    type: 'step',
    phase: 'other',
    termination: { type: 'open' },
    target: { metric: 'none', unit: 'none', reference: 'none' },
    ...cloneValue(overrides),
  };
}

export function createRepeatGroup(
  overrides: Partial<WorkoutStructureRepeatGroup> = {},
): WorkoutStructureRepeatGroup {
  return {
    type: 'repeat',
    repetitions: 2,
    steps: [createStructuredStep()],
    ...cloneValue(overrides),
  };
}

export function insertWorkoutNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
  node: WorkoutNode,
  position: WorkoutInsertPosition,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const target = nodeArrayAtPath(next, path);
  if (!target) return next;
  const index = path[path.length - 1];
  const insertionIndex = position === 'before' ? index : index + 1;
  target.splice(insertionIndex, 0, cloneNode(node));
  return next;
}

export function duplicateWorkoutNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): WorkoutStructureV1 {
  const node = workoutNodeAtPath(structure, path);
  return node
    ? insertWorkoutNode(structure, path, node, 'after')
    : cloneStructure(structure);
}

export function moveWorkoutNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
  direction: WorkoutMoveDirection,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const nodes = nodeArrayAtPath(next, path);
  if (!nodes) return next;
  const index = path[path.length - 1];
  const replacementIndex = direction === 'up' ? index - 1 : index + 1;
  if (replacementIndex < 0 || replacementIndex >= nodes.length) return next;
  [nodes[index], nodes[replacementIndex]] = [
    nodes[replacementIndex],
    nodes[index],
  ];
  return next;
}

export function removeWorkoutNode(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): RemoveWorkoutNodeResult {
  const next = cloneStructure(structure);
  const nodes = nodeArrayAtPath(next, path);
  if (!nodes) {
    return { structure: next, removed: null, path: null };
  }
  const index = path[path.length - 1];
  const [node] = nodes.splice(index, 1);
  if (!node) return { structure: next, removed: null, path: null };
  return {
    structure: next,
    removed: {
      node,
      parentPath: path.length === 2 ? [path[0]] : null,
      index,
      previousStructure: cloneStructure(structure),
    },
    path: [...path] as WorkoutNodePath,
  };
}

export function restoreRemovedWorkoutNode(
  _structure: WorkoutStructureV1,
  removed: RemovedWorkoutNode,
): WorkoutStructureV1 {
  return cloneStructure(removed.previousStructure);
}

export function updateWorkoutStep(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
  update: Partial<WorkoutStructureStep>,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const step = workoutNodeAtPath(next, path);
  if (!step || step.type !== 'step') return next;
  Object.assign(step, cloneValue(update));
  return next;
}

export function updateWorkoutRepeat(
  structure: WorkoutStructureV1,
  rootIndex: number,
  update: Partial<WorkoutStructureRepeatGroup>,
): WorkoutStructureV1 {
  const next = cloneStructure(structure);
  const node = next.steps[rootIndex];
  if (!node || node.type !== 'repeat') return next;
  Object.assign(node, cloneValue(update));
  return next;
}

export function summarizeWorkoutStructure(
  structure: WorkoutStructureV1,
): WorkoutStructureSummary {
  const steps = expandWorkoutSteps(structure);
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

  const allTargeted = steps.length > 0
    && steps.every((step) => step.target.metric !== 'none');
  return {
    duration: durationKnown
      ? { certainty: 'deterministic', seconds }
      : { certainty: 'unknown' },
    distance: distanceKnown
      ? { certainty: 'deterministic', meters }
      : { certainty: 'unknown' },
    // This certainty deliberately carries no numerical load model. A typed
    // target plus exact duration is enough to label the profile estimated;
    // a training-load score belongs to the analysis layer, not this editor.
    load: durationKnown && allTargeted
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

/** Format a canonical distance termination for the athlete's unit system. */
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

/** Convert a visible distance termination back to canonical integer meters. */
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

/** Format canonical seconds-per-kilometre as an editable M:SS pace. */
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

/** Parse an editable M:SS pace into canonical seconds per kilometre. */
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

export function deriveFlatFieldsFromStructure(
  structure: WorkoutStructureV1,
): WorkoutStructureFlatFields {
  const steps = expandWorkoutSteps(structure);
  const summary = summarizeWorkoutStructure(structure);
  const result: WorkoutStructureFlatFields = {
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
  if (!steps.length) return result;

  const signatures = steps.map((step) => (
    projectableTargetSignature(step.target)
  ));
  if (signatures.some((signature) => signature === null)) return result;
  const [signature] = signatures;
  if (!signature || signatures.some(
    (candidate) => JSON.stringify(candidate) !== JSON.stringify(signature),
  )) {
    return result;
  }
  const [metric, minimum, maximum] = signature;
  if (metric === 'power') {
    result.target_power_min = minimum;
    result.target_power_max = maximum;
  } else if (metric === 'heart_rate') {
    result.target_hr_min = minimum;
    result.target_hr_max = maximum;
  } else if (metric === 'pace') {
    result.target_pace_min = formatPace(minimum);
    result.target_pace_max = formatPace(maximum);
  }
  return result;
}

export function synthesizeStructureFromFlat({
  workoutType,
  durationMinutes,
  distanceKm,
  powerMin,
  powerMax,
  hrMin,
  hrMax,
  paceMin,
  paceMax,
}: {
  workoutType: string;
  durationMinutes: number | null;
  distanceKm: number | null;
  powerMin: number | null;
  powerMax: number | null;
  hrMin: number | null;
  hrMax: number | null;
  paceMin: string | null;
  paceMax: string | null;
}): WorkoutStructureV1 {
  if (isRestWorkoutType(workoutType)) return { steps: [] };
  const duration = finiteNonnegative(durationMinutes);
  const distance = finiteNonnegative(distanceKm);
  if (duration && distance) {
    throw new Error(
      'Choose either a duration or a distance before converting to steps.',
    );
  }
  const termination: WorkoutTermination = duration
    ? { type: 'time', seconds: Math.round(duration * 60) }
    : distance
      ? { type: 'distance', meters: Math.round(distance * 1000) }
      : { type: 'open' };
  if (
    (termination.type === 'time' && termination.seconds < 1)
    || (termination.type === 'distance' && termination.meters < 1)
  ) {
    throw new Error('The selected termination is too small to convert.');
  }
  return {
    steps: [createStructuredStep({
      phase: 'other',
      termination,
      target: targetFromFlat({
        powerMin,
        powerMax,
        hrMin,
        hrMax,
        paceMin,
        paceMax,
      }),
    })],
  };
}

export function validateWorkoutStructure(
  structure: WorkoutStructureV1,
  workoutType: string,
): string[] {
  const errors: string[] = [];
  const steps = expandWorkoutSteps(structure);
  if (!isRestWorkoutType(workoutType) && !steps.length) {
    errors.push('Add at least one executable step for a non-rest workout.');
  }
  if (isRestWorkoutType(workoutType) && steps.length) {
    errors.push('A rest workout cannot contain executable steps.');
  }
  structure.steps.forEach((node, rootIndex) => {
    if (node.type === 'repeat') {
      if (!node.steps.length) {
        errors.push(`Repeat ${rootIndex + 1} needs at least one step.`);
      }
      if (!Number.isInteger(node.repetitions)
        || node.repetitions < 1
        || node.repetitions > 100) {
        errors.push(`Repeat ${rootIndex + 1} must repeat from 1 to 100 times.`);
      }
    }
  });
  steps.forEach((step, index) => {
    const label = step.label?.trim() ?? '';
    const instructions = step.instructions?.trim() ?? '';
    if (label.length > 80) {
      errors.push(`Step ${index + 1} label must be 80 characters or fewer.`);
    }
    if (instructions.length > 1000) {
      errors.push(
        `Step ${index + 1} instructions must be 1000 characters or fewer.`,
      );
    }
    errors.push(...validateTermination(step.termination, index));
    errors.push(...validateTarget(step.target, index));
  });
  return errors;
}

function expandWorkoutSteps(structure: WorkoutStructureV1): WorkoutStructureStep[] {
  const expanded: WorkoutStructureStep[] = [];
  for (const node of structure.steps) {
    if (node.type === 'step') {
      expanded.push(node);
      continue;
    }
    for (let count = 0; count < node.repetitions; count += 1) {
      expanded.push(...node.steps);
    }
  }
  return expanded;
}

function nodeArrayAtPath(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): WorkoutNode[] | null {
  if (path.length === 1) return structure.steps;
  return repeatChildren(structure, path[0]);
}

function repeatChildren(
  structure: WorkoutStructureV1,
  rootIndex: number,
): WorkoutStructureStep[] | null {
  const node = structure.steps[rootIndex];
  return node?.type === 'repeat' ? node.steps : null;
}

function workoutNodeAtPath(
  structure: WorkoutStructureV1,
  path: WorkoutNodePath,
): WorkoutNode | null {
  const nodes = nodeArrayAtPath(structure, path);
  return nodes?.[path[path.length - 1]] ?? null;
}

function cloneStructure(structure: WorkoutStructureV1): WorkoutStructureV1 {
  return {
    steps: structure.steps.map(cloneNode),
  };
}

function cloneNode(node: WorkoutNode): WorkoutNode {
  if (node.type === 'step') {
    return {
      ...node,
      termination: { ...node.termination },
      target: { ...node.target } as WorkoutIntensityTarget,
    };
  }
  return {
    ...node,
    steps: node.steps.map(cloneNode) as WorkoutStructureStep[],
  };
}

function cloneValue<T>(value: T): T {
  if (value === undefined || value === null) return value;
  return structuredClone(value);
}

function projectableTargetSignature(
  target: WorkoutIntensityTarget,
): ['none' | 'power' | 'heart_rate' | 'pace', number | null, number | null] | null {
  const combo = `${target.metric}:${target.unit}:${target.reference}`;
  if (combo === 'none:none:none') return ['none', null, null];
  if (combo === 'power:watts:absolute') {
    return ['power', target.min ?? null, target.max ?? null];
  }
  if (combo === 'heart_rate:bpm:absolute') {
    return ['heart_rate', target.min ?? null, target.max ?? null];
  }
  if (combo === 'pace:sec_per_km:absolute') {
    return ['pace', target.min ?? null, target.max ?? null];
  }
  return null;
}

function formatPace(value: number | null): string | null {
  if (value === null) return null;
  const rounded = roundHalfEven(value);
  const minutes = Math.floor(rounded / 60);
  const seconds = rounded % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds
    .toString()
    .padStart(2, '0')}`;
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

function targetFromFlat({
  powerMin,
  powerMax,
  hrMin,
  hrMax,
  paceMin,
  paceMax,
}: {
  powerMin: number | null;
  powerMax: number | null;
  hrMin: number | null;
  hrMax: number | null;
  paceMin: string | null;
  paceMax: string | null;
}): WorkoutIntensityTarget {
  const hasPower = powerMin !== null || powerMax !== null;
  const hasHr = hrMin !== null || hrMax !== null;
  const parsedPaceMin = parsePace(paceMin);
  const parsedPaceMax = parsePace(paceMax);
  const hasPace = parsedPaceMin !== null || parsedPaceMax !== null;
  if ([hasPower, hasHr, hasPace].filter(Boolean).length > 1) {
    throw new Error('Choose one target metric before converting to steps.');
  }
  if (hasPower) {
    return boundedTarget(
      { metric: 'power', unit: 'watts', reference: 'absolute' },
      powerMin,
      powerMax,
    );
  }
  if (hasHr) {
    return boundedTarget(
      { metric: 'heart_rate', unit: 'bpm', reference: 'absolute' },
      hrMin,
      hrMax,
    );
  }
  if (hasPace) {
    return boundedTarget(
      { metric: 'pace', unit: 'sec_per_km', reference: 'absolute' },
      parsedPaceMin,
      parsedPaceMax,
    );
  }
  if ((paceMin?.trim() || paceMax?.trim()) && !hasPace) {
    throw new Error('Enter pace as minutes:seconds before converting.');
  }
  return { metric: 'none', unit: 'none', reference: 'none' };
}

function boundedTarget(
  target: Omit<Exclude<WorkoutIntensityTarget, {
    metric: 'none';
  }>, 'min' | 'max'>,
  min: number | null,
  max: number | null,
): WorkoutIntensityTarget {
  if (min === null && max === null) {
    throw new Error('A target needs at least one bound.');
  }
  return {
    ...target,
    ...(min !== null ? { min } : {}),
    ...(max !== null ? { max } : {}),
  } as WorkoutIntensityTarget;
}

function parsePace(value: string | null): number | null {
  const text = value?.trim() ?? '';
  if (!text) return null;
  const parts = text.split(':');
  if (parts.length !== 2) return null;
  const minutes = Number(parts[0]);
  const seconds = Number(parts[1]);
  if (!Number.isInteger(minutes) || !Number.isFinite(seconds)
    || minutes < 0 || seconds < 0 || seconds >= 60) {
    return null;
  }
  const result = minutes * 60 + seconds;
  return result > 0 ? result : null;
}

function finiteNonnegative(value: number | null): number | null {
  if (value === null || !Number.isFinite(value) || value < 0) return null;
  return value;
}

function isRestWorkoutType(value: string): boolean {
  return ['rest', 'off'].includes(value.trim().toLowerCase());
}

function round(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

function validateTermination(
  termination: WorkoutTermination,
  stepIndex: number,
): string[] {
  if (
    termination.type === 'time'
    && (!Number.isInteger(termination.seconds)
      || termination.seconds < 1
      || termination.seconds > 86_400)
  ) {
    return [`Step ${stepIndex + 1} needs time from 1 to 86400 seconds.`];
  }
  if (
    termination.type === 'distance'
    && (!Number.isInteger(termination.meters)
      || termination.meters < 1
      || termination.meters > 1_000_000)
  ) {
    return [`Step ${stepIndex + 1} needs distance from 1 to 1000000 meters.`];
  }
  return [];
}

function validateTarget(
  target: WorkoutIntensityTarget,
  stepIndex: number,
): string[] {
  if (target.metric === 'none') return [];
  if (target.min == null && target.max == null) {
    return [`Step ${stepIndex + 1} target needs a minimum or maximum.`];
  }
  const bounds: Record<WorkoutTargetKind, readonly [number, number]> = {
    none: [0, 0],
    power_watts: [0, 5000],
    power_cp: [0, 300],
    heart_rate_bpm: [0, 300],
    heart_rate_lthr: [0, 200],
    pace_absolute: [0, 7200],
    pace_threshold: [-7200, 7200],
    rpe: [0, 10],
  };
  const [minimum, maximum] = bounds[targetKind(target)];
  for (const value of [target.min, target.max]) {
    if (
      value != null
      && (!Number.isFinite(value) || value < minimum || value > maximum)
    ) {
      return [
        `Step ${stepIndex + 1} target must stay between ${minimum} and ${maximum}.`,
      ];
    }
  }
  if (
    target.min != null
    && target.max != null
    && target.min > target.max
  ) {
    return [`Step ${stepIndex + 1} target minimum cannot exceed maximum.`];
  }
  return [];
}
