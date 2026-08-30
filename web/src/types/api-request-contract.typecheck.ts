import type {
  ContextPilotRunRequest,
  PersonalContextDraftRequest,
  PlanWorkoutUpdateRequest,
  ScopedPersonalContextAccessRequest,
  ScopedPersonalContextDraftRequest,
  WorkoutIntensityTarget,
  WorkoutStructureRepeatGroup,
  WorkoutStructureStep,
} from './api';

const payload = {
  category: 'less_time',
  fields: {},
} as const;

const unlinkedDraft: PersonalContextDraftRequest = {
  kind: 'temporary_constraint',
  purpose: 'plan_adjustment',
  payload,
};
const linkedDraft: PersonalContextDraftRequest = {
  kind: 'execution_explanation',
  purpose: 'execution_interpretation',
  payload,
  linked_subject_type: 'workout',
  linked_subject_id: 'workout-id',
};
// @ts-expect-error Linked subject type and id must be supplied together.
const incompleteLinkedDraft: PersonalContextDraftRequest = {
  kind: 'execution_explanation',
  purpose: 'execution_interpretation',
  payload,
  linked_subject_type: 'workout',
};
const scopedDraft: ScopedPersonalContextDraftRequest = {
  kind: 'temporary_constraint',
  purpose: 'plan_adjustment',
  payload,
};
const scopedAccess: ScopedPersonalContextAccessRequest = {
  audience: 'praxys-coach-plugin',
  purpose: 'execution_interpretation',
  kind: 'execution_explanation',
  access: ['read'],
};
const durableScopedAccess: ScopedPersonalContextAccessRequest = {
  audience: 'praxys-coach-plugin',
  purpose: 'goal_review',
  // @ts-expect-error Scoped clients cannot request durable preferences.
  kind: 'durable_preference',
  access: ['read'],
};
// @ts-expect-error The scoped purpose and context kind must be compatible.
const mismatchedScopedAccess: ScopedPersonalContextAccessRequest = {
  audience: 'praxys-coach-plugin',
  purpose: 'plan_generation',
  kind: 'execution_explanation',
  access: ['write'],
};
// @ts-expect-error Scoped previews use the same purpose-kind contract.
const mismatchedScopedDraft: ScopedPersonalContextDraftRequest = {
  kind: 'execution_explanation',
  purpose: 'goal_review',
  payload,
};
const scopedNarrativeDraft: ScopedPersonalContextDraftRequest = {
  kind: 'temporary_constraint',
  purpose: 'plan_adjustment',
  payload: {
    ...payload,
    // @ts-expect-error MCP drafts never accept narrative.
    narrative: 'not available to delegated clients',
  },
};

const syntheticPilot: ContextPilotRunRequest = {
  source: 'synthetic',
  scenario_id: 'availability-suggestion',
};
const optedInPilot: ContextPilotRunRequest = {
  source: 'opt_in',
  purpose: 'plan_adjustment',
  confirmed_opt_in: true,
};
const unconfirmedPilot: ContextPilotRunRequest = {
  source: 'opt_in',
  purpose: 'plan_adjustment',
  // @ts-expect-error Opted-in runs require an explicit true confirmation.
  confirmed_opt_in: false,
};

const absolutePowerTarget: WorkoutIntensityTarget = {
  metric: 'power',
  unit: 'watts',
  reference: 'absolute',
  min: 200,
};
const thresholdPaceTarget: WorkoutIntensityTarget = {
  metric: 'pace',
  unit: 'sec_per_km_delta',
  reference: 'threshold_pace',
  max: 15,
};
// @ts-expect-error Unit and reference must be the exact Python-supported tuple.
const mismatchedIntensityTuple: WorkoutIntensityTarget = {
  metric: 'power',
  unit: 'watts',
  reference: 'critical_power',
  min: 200,
};
// @ts-expect-error Every non-none intensity target needs a numeric bound.
const unboundedIntensityTarget: WorkoutIntensityTarget = {
  metric: 'heart_rate',
  unit: 'bpm',
  reference: 'absolute',
};
// @ts-expect-error Null placeholders do not satisfy the at-least-one-bound rule.
const nullIntensityTarget: WorkoutIntensityTarget = {
  metric: 'rpe',
  unit: 'scale_10',
  reference: 'perceived_exertion',
  min: null,
  max: null,
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
const structuredWorkoutUpdate: PlanWorkoutUpdateRequest = {
  expected_version: 'a'.repeat(64),
  workout_structure_version: 'v1',
  workout_structure: { steps: [] },
};
// @ts-expect-error Structure version and payload must be supplied together.
const mismatchedStructureUpdate: PlanWorkoutUpdateRequest = {
  expected_version: 'a'.repeat(64),
  workout_structure_version: 'v1',
};

void [
  unlinkedDraft,
  linkedDraft,
  incompleteLinkedDraft,
  scopedDraft,
  scopedAccess,
  durableScopedAccess,
  mismatchedScopedAccess,
  mismatchedScopedDraft,
  scopedNarrativeDraft,
  syntheticPilot,
  optedInPilot,
  unconfirmedPilot,
  absolutePowerTarget,
  thresholdPaceTarget,
  mismatchedIntensityTuple,
  unboundedIntensityTarget,
  nullIntensityTarget,
  wordedRestStep,
  namedRepeatGroup,
  semanticRepeatIsInvalid,
  structuredWorkoutUpdate,
  mismatchedStructureUpdate,
];
