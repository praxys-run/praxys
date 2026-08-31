import type {
  ContextPilotRunRequest,
  PersonalContextDraftRequest,
  PlanGenerationPurposeSelection,
  PlanWorkoutUpdateRequest,
  Road10KActionResponse,
  Road10KOutcomeResponse,
  Road10KProposalGoalSnapshot,
  ScopedPersonalContextAccessRequest,
  ScopedPersonalContextDraftRequest,
  WorkoutIntensityTarget,
  WorkoutStructureRepeatGroup,
  WorkoutStructureStep,
} from './api';

const currentGoalPurpose: PlanGenerationPurposeSelection = {
  capability_id: 'outdoor_road_10k_performance_v1',
  source: 'current_goal',
  expected_goal_id: '11111111-1111-1111-1111-111111111111',
  expected_goal_revision: 'a'.repeat(64),
};
const capabilityPurpose: PlanGenerationPurposeSelection = {
  capability_id: 'outdoor_road_10k_performance_v1',
  source: 'capability',
  expected_goal_id: null,
  expected_goal_revision: null,
};
// @ts-expect-error Current-Goal purpose requires non-null provenance.
const invalidCurrentGoalPurpose: PlanGenerationPurposeSelection = {
  capability_id: 'outdoor_road_10k_performance_v1',
  source: 'current_goal',
  expected_goal_id: null,
  expected_goal_revision: null,
};
// @ts-expect-error Capability purpose cannot claim mutable Goal provenance.
const invalidCapabilityPurpose: PlanGenerationPurposeSelection = {
  capability_id: 'outdoor_road_10k_performance_v1',
  source: 'capability',
  expected_goal_id: '11111111-1111-1111-1111-111111111111',
  expected_goal_revision: 'a'.repeat(64),
};

const roadOutcomeCommon = {
  policy_version: 'road-10k-plan-generation-policy-v2',
  generator_version: 'road-10k-deterministic-generator-v1',
  science_decision_id: 'sdr-road-10k-plan-generation-policy-v2',
  contract_digest: 'sha256:contract',
  source_decision_digest: 'sha256:decision',
  deterministic_input_hash: 'a'.repeat(64),
  event_context: {
    snapshot_version: 'road-10k-event-context-v1',
    state: 'confirmed_none' as const,
    goal_target_date: null,
    benchmark_date: null,
    target_date: null,
    target_source: null,
  },
  history_statistics: {
    usable_completed_weeks: 8,
    recent_modal_running_frequency: 4,
    recent_median_usable_weekly_minutes: 180,
    recent_maximum_usable_weekly_minutes: 210,
    recent_maximum_session_minutes: 70,
    recent_maximum_session_distance_km: 12,
    latest_run_date: '2026-08-20',
  },
  failed_rule_id: null,
  observed_or_stated_reason: null,
  uncertainty_or_missing_field: null,
  alternatives: [],
};
const roadPlanCandidate: Road10KOutcomeResponse = {
  ...roadOutcomeCommon,
  code: 'eligible_rolling_proposal',
  route_state: 'plan_candidate',
  plan_returned: true,
  adoption_required: true,
};
const invalidRoadOutcome: Road10KOutcomeResponse = {
  ...roadOutcomeCommon,
  code: 'safety_stop',
  route_state: 'plan_candidate',
  plan_returned: true,
  // @ts-expect-error Safety stop can only be a no-plan readiness outcome.
  adoption_required: true,
};
const withdrawnRoadAction: Road10KActionResponse = {
  outcome: 'withdrawn',
  rollout_status: 'withdrawn',
  plan_status: 'unchanged',
};
const invalidRoadAction: Road10KActionResponse = {
  outcome: 'withdrawn',
  rollout_status: 'withdrawn',
  // @ts-expect-error Withdrawal preserves the separate plan state.
  plan_status: 'none',
};
const currentGoalSnapshot: Road10KProposalGoalSnapshot = {
  id: 'goal-snapshot',
  version: 1,
  state: 'active',
  purpose_source: 'current_goal',
  source_goal_id: '11111111-1111-1111-1111-111111111111',
  source_goal_revision: 'a'.repeat(64),
  goal_kind: 'race',
  target: {
    distance: '10K',
    criterion: 'performance',
    setting: 'outdoor_road',
    target_time_sec: null,
    target_event_date: null,
    benchmark_date: null,
    event_state: 'confirmed_none',
    guardrail_projection: {
      contract_digest: 'sha256:2d0d25d994bc0a623e3c7fed6e538bb992f66313cefd7f8314aed2c5b1d3e496',
      source_decision_digest: 'sha256:aa420e4c8b24ca6e0ce0340cc78934edca29c4cda70876dbf46d0a0ca2bee1ad',
      taper: {
        planned_volume_reduction_fraction: 0.5,
        maintain_intensity_exposure_without_adding_quality: true,
        evidence_population: 'mixed_endurance_athletes',
        direct_recreational_road_10k_validation: false,
        single_target_taper_result: 'taper_proposal_truncated_to_event_eve',
        personal_performance_gain_claim: false,
        causal_plan_benefit_claim: 'disabled',
        personal_injury_probability: 'disabled',
      },
    },
  },
  horizon_start: '2026-08-22',
  horizon_end: '2026-09-04',
  acknowledged_at: null,
};
// @ts-expect-error Capability purpose cannot retain current-Goal provenance.
const invalidGoalSnapshot: Road10KProposalGoalSnapshot = {
  ...currentGoalSnapshot,
  purpose_source: 'capability',
};

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
  currentGoalPurpose,
  capabilityPurpose,
  invalidCurrentGoalPurpose,
  invalidCapabilityPurpose,
  roadPlanCandidate,
  invalidRoadOutcome,
  withdrawnRoadAction,
  invalidRoadAction,
  currentGoalSnapshot,
  invalidGoalSnapshot,
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
