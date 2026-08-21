import type {
  ContextPilotRunRequest,
  PersonalContextAiConsentRequest,
  PersonalContextDraftRequest,
  PlanWorkoutUpdateRequest,
  Road10KOptInRequest,
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
  allow_ai: false,
};
// @ts-expect-error Synthetic runs cannot accept opted-in context fields.
const invalidSyntheticPilot: ContextPilotRunRequest = {
  source: 'synthetic',
  scenario_id: 'availability-suggestion',
  allow_ai: true,
};
const unconfirmedPilot: ContextPilotRunRequest = {
  source: 'opt_in',
  purpose: 'plan_adjustment',
  // @ts-expect-error Opted-in runs require an explicit true confirmation.
  confirmed_opt_in: false,
};

const grantedAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'granted',
  provider: 'azure_openai',
  consent_text_version: 'ai-v1',
  client: 'web',
};
const deniedAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'denied',
  consent_text_version: 'ai-v1',
  client: 'web',
};
const withdrawnAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'withdrawn',
  provider: null,
  consent_text_version: 'ai-v1',
  client: 'miniapp',
};
const webRoad10KOptIn: Road10KOptInRequest = {
  password: 'correct horse battery staple',
  notice_digest: 'a'.repeat(64),
  client: 'web',
};
const miniappRoad10KOptIn: Road10KOptInRequest = {
  password: 'correct horse battery staple',
  notice_digest: 'b'.repeat(64),
  client: 'miniapp',
};
void webRoad10KOptIn;
void miniappRoad10KOptIn;
// @ts-expect-error Every Road 10K opt-in client must submit server-verified reauthentication.
const invalidMiniappRoad10KOptIn: Road10KOptInRequest = {
  notice_digest: 'c'.repeat(64),
  client: 'miniapp',
};
// @ts-expect-error Granted consent requires the Azure OpenAI provider.
const invalidGrantedAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'granted',
  consent_text_version: 'ai-v1',
  client: 'web',
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
  invalidSyntheticPilot,
  unconfirmedPilot,
  grantedAiConsent,
  deniedAiConsent,
  withdrawnAiConsent,
  invalidGrantedAiConsent,
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
