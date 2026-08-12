import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
} from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { detectLocale, t, tFmt, tNamed } from '../../utils/i18n';
import {
  beginManagedPlanRequest,
  athletePlanDateDistance,
  formatWorkoutType,
  invalidateManagedPlanRequests,
  isPraxysOwned,
  isLatestManagedPlanRequest,
  managedPlanState,
  planWindowUrl,
  shiftAthletePlanDate,
  workoutKey,
} from '../../utils/managed-plan';
import { personalContextEvidenceIds } from '../../utils/personal-context';
import {
  PHASE_VALUES,
  TARGET_KINDS,
  createRepeat,
  createStep,
  deriveFlat,
  duplicateNode,
  insertNode,
  moveNode,
  removeNode,
  restoreNode,
  summarize,
  synthesizeFromFlat,
  targetForKind,
  targetKind,
  updateRepeat,
  updateStep,
  validate,
  type RemovedNode,
  type TargetKind,
  type WorkoutNodePath,
} from '../../utils/workout-structure';
import type {
  PlanActivityType,
  PlanAdjustment,
  PlanReconciliation,
  PlanResolutionAction,
  PlanResolutionResponse,
  PlanResponse,
  PlanWorkoutDeleteResponse,
  PlanWorkoutCompatibilityResponse,
  PlanWorkoutMutationResponse,
  PlanWorkoutUpdateRequest,
  PlanWorkoutWriteFields,
  PlannedWorkout,
  PlanTargetWorkoutSnapshot,
  SettingsResponse,
  StrydPushResult,
  WorkoutProviderCompatibility,
  WorkoutProviderCompatibilityReasonCode,
  WorkoutStructureRepeatGroup,
  WorkoutStructureStep,
  WorkoutStructureV1,
} from '../../types/api';
import type { ManagedPlanState } from '../../utils/managed-plan';

type StatusTone = 'neutral' | 'positive' | 'warning' | 'danger' | 'reasoning';
type WorkoutAction = '' | 'deliver' | 'review';
const REFRESH_WORKING_KEY = '__managed_plan_refresh__';

interface WorkoutStatus {
  label: string;
  tone: StatusTone;
  action: WorkoutAction;
  disabled: boolean;
}

interface AdjustmentNoticeView {
  id: string;
  title: string;
  detail: string;
  contextDetail: string;
  tone: 'neutral' | 'warning';
  canUndo: boolean;
}

interface WorkoutView {
  key: string;
  day: string;
  weekday: string;
  workoutType: string;
  activity: string;
  sourceOwned: boolean;
  details: string;
  description: string;
  statusLabel: string;
  statusTone: StatusTone;
  action: WorkoutAction;
  actionDisabled: boolean;
  editDisabled: boolean;
  canEdit: boolean;
  canDuplicate: boolean;
}

const WORKOUT_TYPE_VALUES = [
  'easy',
  'recovery',
  'long_run',
  'tempo',
  'threshold',
  'interval',
  'hill_repeat',
  'testing',
  'rest',
  '__custom__',
] as const;

const ACTIVITY_VALUES: PlanActivityType[] = [
  'running',
  'trail_running',
  'cycling',
  'walking',
  'hiking',
  'strength',
  'mobility',
  'cross_training',
  'rest',
  'other',
];

const TERMINATION_VALUES = ['time', 'distance', 'open', 'manual'] as const;

interface EditorStepView extends WorkoutStructureStep {
  phaseIndex: number;
  targetIndex: number;
  terminationIndex: number;
  targetDetail: string;
}

interface EditorRepeatView extends Omit<WorkoutStructureRepeatGroup, 'steps'> {
  steps: EditorStepView[];
}

interface CompatibilityView {
  target: string;
  title: string;
  status: string;
  compatible: boolean;
  tone: 'safe' | 'warning';
  detail: string;
  reasons: string[];
}

function translations() {
  return {
    upcomingPlan: t('Upcoming Plan'),
    upcomingWorkouts: t('Upcoming workouts'),
    planManagement: t('Plan management'),
    managedByPraxys: t('Managed by Praxys'),
    managedDeliveryPaused: t('Managed delivery paused'),
    externalPlanMode: t('External plan mode'),
    manageInSettings: t('Manage in Settings'),
    adoptInSettings: t('Adopt in Settings'),
    externalWorkoutsUntouched: t(
      'Praxys only changes workouts it created or you explicitly adopt. Manual workouts and workouts from another coach stay untouched. To avoid overlapping sessions, use one planner at a time.',
    ),
    noWorkouts: t('No workouts scheduled in this window.'),
    retry: t('Retry'),
    failedToLoad: t('Failed to load training plan'),
    working: t('Working…'),
    external: t('External'),
    useInPraxys: t('Use in Praxys'),
    conflictRetained: t('Conflict retained'),
    praxysOnly: t('Praxys only'),
    paused: t('Paused'),
    inSync: t('In sync'),
    verifying: t('Verifying'),
    reviewConflict: t('Review conflict'),
    retryDelivery: t('Retry delivery'),
    syncTargetToReview: t('Sync target to review'),
    deliverNow: t('Deliver now'),
    queued: t('Queued'),
    done: t('Done'),
    cancel: t('Cancel'),
    confirm: t('Confirm'),
    resolveConflict: t('Resolve workout conflict'),
    praxysVersion: t('Praxys version'),
    targetUnavailable: t('The target version is unavailable.'),
    couldNotResolve: t('Could not resolve this workout'),
    deliveryFailed: t('Delivery failed'),
    missingDeliveryResult: t('No delivery result was returned for this workout'),
    conservativeChange: t('Praxys made a conservative plan change'),
    previousWorkoutRestored: t('The previous workout was restored'),
    adjustmentSuperseded: t('An earlier automatic change was superseded'),
    currentHrvCaution: t('Current HRV crossed your personal caution band.'),
    confirmedContextUsed: t(
      'This change used confirmed private context. The private detail is not copied into the plan record.',
    ),
    restoreWorkout: t('Restore workout'),
    restoring: t('Restoring…'),
    restoreWorkoutFailed: t('Could not restore the previous workout'),
    workout: t('Workout'),
    rest: t('Rest'),
    addWorkout: t('Add workout'),
    editWorkout: t('Edit workout'),
    duplicateWorkout: t('Duplicate workout'),
    sourceOwned: t('Source-owned'),
    sourceStaysUnchanged: t('Source stays unchanged'),
    workoutType: t('Workout purpose'),
    planActivity: t('Plan activity'),
    roadRunning: t('Road running'),
    trailRunning: t('Trail running'),
    cycling: t('Cycling'),
    walking: t('Walking'),
    hiking: t('Hiking'),
    strength: t('Strength'),
    mobility: t('Mobility'),
    crossTraining: t('Cross-training'),
    other: t('Other'),
    customWording: t('Custom wording'),
    customWorkoutPurpose: t('Custom workout purpose'),
    raceRehearsal: t('e.g. Race rehearsal'),
    date: t('Date'),
    durationMinutes: t('Duration (minutes)'),
    distanceKm: t('Distance (km)'),
    powerFloor: t('Power floor (W)'),
    powerCeiling: t('Power ceiling (W)'),
    hrMinimum: t('Heart-rate minimum (bpm)'),
    hrMaximum: t('Heart-rate maximum (bpm)'),
    paceMinimum: t('Pace minimum (min/km)'),
    paceMaximum: t('Pace maximum (min/km)'),
    paceMinExample: t('e.g. 5:20'),
    paceMaxExample: t('e.g. 5:45'),
    workoutNotes: t('Workout notes'),
    optional: t('Optional'),
    saveWorkout: t('Save workout'),
    saving: t('Saving…'),
    delete: t('Delete'),
    deleteWorkout: t('Delete workout'),
    deleteThisWorkout: t('Delete this workout?'),
    deleteWorkoutDetail: t(
      'This removes the Praxys workout from the canonical plan. Any external workout stays untouched.',
    ),
    deleting: t('Deleting…'),
    convertToRest: t('Convert to rest'),
    couldNotAddWorkout: t('Could not add this workout'),
    couldNotUpdateWorkout: t('Could not update this workout'),
    couldNotDeleteWorkout: t('Could not delete this workout'),
    couldNotConvertToRest: t('Could not convert this workout to rest'),
    refreshBeforeEditing: t('Refresh the plan before editing this workout.'),
    staleWorkout: t(
      'This workout changed elsewhere. The plan was refreshed; reopen the workout to continue.',
    ),
    completedHistory: t(
      'That date is now completed history and can no longer be changed.',
    ),
    previousPlanWindow: t('Previous plan window'),
    nextPlanWindow: t('Next plan window'),
    plannerOverlapWarning: t(
      'An external planner overlaps the Praxys plan. Use one planner at a time to avoid duplicate or conflicting sessions.',
    ),
    easy: t('Easy'),
    recovery: t('Recovery'),
    longRun: t('Long run'),
    tempo: t('Tempo'),
    threshold: t('Threshold'),
    intervals: t('Intervals'),
    hillRepeats: t('Hill repeats'),
    testing: t('Testing'),
    structuredSteps: t('Structured steps'),
    legacyFlatSummary: t('Legacy flat summary'),
    convertToStructured: t('Convert to structured steps'),
    legacySummaryDetail: t(
      'This imported or older workout has no portable tree. Edit its summary as-is, or explicitly convert one flat step without guessing semantics.',
    ),
    stepSemantic: t('Step semantic'),
    warmup: t('Warm-up'),
    work: t('Work'),
    cooldown: t('Cool-down'),
    step: t('Step'),
    optionalLabel: t('Optional label'),
    uphillEffort: t('e.g. Uphill effort'),
    termination: t('Termination'),
    time: t('Time'),
    distance: t('Distance'),
    open: t('Open'),
    manual: t('Manual'),
    timeSeconds: t('Time in seconds'),
    distanceMeters: t('Distance in meters'),
    targetType: t('Target type'),
    noTarget: t('No target'),
    powerWatts: t('Power · watts'),
    powerCp: t('Power · %CP'),
    heartRateBpm: t('Heart rate · bpm'),
    heartRateLthr: t('Heart rate · %LTHR'),
    paceAbsolute: t('Pace · sec/km'),
    paceThreshold: t('Pace · threshold delta'),
    rpe: t('RPE · 0–10'),
    targetMinimum: t('Target minimum'),
    targetMaximum: t('Target maximum'),
    allowedRange: t('Allowed range'),
    stepInstructions: t('Step instructions'),
    optionalCoachingCue: t('Optional coaching cue'),
    repeatGroup: t('Repeat group'),
    repeatLabel: t('Repeat label'),
    mainSet: t('e.g. Main set'),
    repetitions: t('Repetitions'),
    repeatChildren: t('Repeat children'),
    oneLevelRepeat: t(
      'Portable v1 permits one repeat level. Add atomic steps here, not another repeat.',
    ),
    addStep: t('Add step'),
    addRepeat: t('Add repeat'),
    addRepeatStep: t('Add repeat step'),
    moveUp: t('Move up'),
    moveDown: t('Move down'),
    insertBefore: t('Insert before'),
    insertAfter: t('Insert after'),
    duplicate: t('Duplicate'),
    stepRemoved: t('Step removed. You can restore it before saving.'),
    undo: t('Undo'),
    duration: t('Duration'),
    load: t('Load'),
    deterministic: t('deterministic'),
    estimated: t('estimated'),
    unknown: t('Unknown'),
    estimatedFromTargets: t('Estimated from targets'),
    totalsDetail: t(
      'Totals are deterministic only when every repeated step has the same measurable termination. Praxys does not invent a training-load score here.',
    ),
    providerCompatibility: t('Provider compatibility'),
    compatibilityDetail: t(
      'This checks portable workout content only. It never connects to a provider or delivers a workout.',
    ),
    checkingCompatibility: t('Checking provider compatibility…'),
    compatibilityUnavailable: t(
      'Compatibility preview is unavailable. Check your connection and try again.',
    ),
    finishStepsForCompatibility: t(
      'Finish the required step fields to preview compatibility.',
    ),
    compatible: t('Compatible'),
    notSafelyRepresentable: t('Not safely representable'),
    compatibleStructure: t(
      'This portable structure can be represented without flattening.',
    ),
    compatibleLegacy: t(
      'This legacy flat workout has no portable tree to flatten.',
    ),
  };
}

function platformLabel(value: string | null): string {
  if (!value) return '';
  if (value === 'stryd') return 'Stryd';
  if (value === 'garmin') return 'Garmin';
  if (value === 'coros') return 'COROS';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function managementCopy(
  state: ManagedPlanState,
  target: string | null,
  targetConnected: boolean,
): { title: string; detail: string; tone: StatusTone; action: string } {
  const targetName = platformLabel(target);
  if (state === 'active') {
    if (targetConnected) {
      return {
        title: t('Managed by Praxys'),
        detail: tFmt('The rolling 14-day window is delivered to {0}.', targetName),
        tone: 'positive',
        action: t('Manage in Settings'),
      };
    }
    return {
      title: t('Managed by Praxys'),
      detail: targetName
        ? tNamed(
          'Reconnect {target} to continue delivery. The Praxys plan remains canonical.',
          { target: targetName },
        )
        : t('Select an execution target in Settings to continue delivery.'),
      tone: 'warning',
      action: t('Manage in Settings'),
    };
  }
  if (state === 'paused') {
    return {
      title: t('Managed delivery paused'),
      detail: t('The Praxys plan is preserved; no target workouts will change.'),
      tone: 'warning',
      action: t('Manage in Settings'),
    };
  }
  return {
    title: t('External plan mode'),
    detail: t('Praxys is read-only and leaves every target workout untouched.'),
    tone: 'neutral',
    action: t('Adopt in Settings'),
  };
}

function workoutDateParts(workout: PlannedWorkout): { day: string; weekday: string } {
  const parsed = workout.start_time
    ? new Date(workout.start_time)
    : new Date(`${workout.date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return { day: workout.date.slice(-2), weekday: '' };
  }
  const locale = detectLocale() === 'zh' ? 'zh-CN' : 'en-US';
  const weekday = parsed.toLocaleDateString(locale, { weekday: 'short' });
  return {
    day: String(parsed.getDate()).padStart(2, '0'),
    weekday: detectLocale() === 'zh' ? weekday : weekday.toUpperCase(),
  };
}

function workoutDetails(workout: PlannedWorkout): string {
  const details: string[] = [];
  if (workout.duration_min != null) {
    details.push(`${Math.round(workout.duration_min)} min`);
  }
  if (workout.distance_km != null) {
    details.push(`${workout.distance_km} km`);
  }
  if (workout.power_min != null && workout.power_max != null) {
    details.push(`${workout.power_min}–${workout.power_max} W`);
  } else if (workout.power_min != null) {
    details.push(`≥${workout.power_min} W`);
  } else if (workout.power_max != null) {
    details.push(`≤${workout.power_max} W`);
  }
  if (workout.hr_min != null && workout.hr_max != null) {
    details.push(`${workout.hr_min}–${workout.hr_max} bpm`);
  } else if (workout.hr_min != null) {
    details.push(`≥${workout.hr_min} bpm`);
  } else if (workout.hr_max != null) {
    details.push(`≤${workout.hr_max} bpm`);
  }
  if (workout.pace_min && workout.pace_max) {
    details.push(`${workout.pace_min}–${workout.pace_max}/km`);
  } else if (workout.pace_min) {
    details.push(`≥${workout.pace_min}/km`);
  } else if (workout.pace_max) {
    details.push(`≤${workout.pace_max}/km`);
  }
  return details.join(' · ');
}

function targetWorkoutDetails(workout: PlanTargetWorkoutSnapshot): string {
  const details: string[] = [t(formatWorkoutType(workout.workout_type))];
  if (workout.planned_duration_min != null) {
    details.push(`${Math.round(workout.planned_duration_min)} min`);
  }
  if (workout.planned_distance_km != null) {
    details.push(`${workout.planned_distance_km} km`);
  }
  return details.join(' · ');
}

function statusForWorkout(
  workout: PlannedWorkout,
  state: ManagedPlanState,
  target: string | null,
  targetConnected: boolean,
  working: boolean,
  anyActionWorking: boolean,
  canWrite: boolean,
): WorkoutStatus {
  if (working) {
    return {
      label: t('Working…'),
      tone: 'reasoning',
      action: '',
      disabled: true,
    };
  }

  const reconciliation = workout.reconciliation;
  const owned = isPraxysOwned(workout);
  const canAccept = reconciliation?.resolutions.includes('accept_target') ?? false;
  const hasConflict = reconciliation?.conflict === true
    || workout.sync_state === 'mismatch';
  const localResolutionAvailable = canAccept;

  if (!owned) {
    return canAccept && canWrite
      ? {
        label: t('Use in Praxys'),
        tone: 'positive',
        action: 'review',
        disabled: anyActionWorking || !canWrite,
      }
      : {
        label: t('External'),
        tone: 'neutral',
        action: '',
        disabled: true,
      };
  }

  if (isRestWorkoutType(workout.workout_type)) {
    return {
      label: state === 'external' ? t('Praxys only') : t('Rest'),
      tone: 'neutral',
      action: '',
      disabled: true,
    };
  }
  if (state !== 'active' && hasConflict) {
    return {
      label: t('Conflict retained'),
      tone: 'warning',
      action: '',
      disabled: true,
    };
  }
  if (state === 'external') {
    return {
      label: t('Praxys only'),
      tone: 'neutral',
      action: '',
      disabled: true,
    };
  }
  if (state === 'paused') {
    return {
      label: t('Paused'),
      tone: 'warning',
      action: '',
      disabled: true,
    };
  }

  const disabled = !canWrite
    || anyActionWorking
    || (!targetConnected && !localResolutionAvailable);
  const reconciliationState = reconciliation?.state;
  if (reconciliationState === 'matching' || workout.sync_state === 'synced') {
    return {
      label: t('In sync'),
      tone: 'positive',
      action: '',
      disabled: true,
    };
  }
  if (reconciliationState === 'pending_observation') {
    return {
      label: t('Verifying'),
      tone: 'reasoning',
      action: '',
      disabled: true,
    };
  }
  if (
    reconciliationState === 'target_edited'
    || reconciliationState === 'canonical_changed'
    || reconciliationState === 'target_deleted'
  ) {
    return {
      label: t('Review conflict'),
      tone: 'warning',
      action: canWrite ? 'review' : '',
      disabled,
    };
  }
  if (reconciliationState === 'delivery_failed') {
    return {
      label: t('Retry delivery'),
      tone: 'danger',
      action: canWrite ? 'review' : '',
      disabled,
    };
  }
  if (workout.sync_state === 'mismatch' && reconciliation) {
    return {
      label: t('Review conflict'),
      tone: 'warning',
      action: canWrite ? 'review' : '',
      disabled,
    };
  }
  if (workout.sync_state === 'mismatch') {
    return {
      label: t('Sync target to review'),
      tone: 'warning',
      action: '',
      disabled: true,
    };
  }
  if (target === 'stryd') {
    if (!workout.canonical_id) {
      return {
        label: t('Unavailable'),
        tone: 'warning',
        action: '',
        disabled: true,
      };
    }
    return {
      label: canWrite ? t('Deliver now') : t('Queued'),
      tone: canWrite ? 'positive' : 'reasoning',
      action: canWrite ? 'deliver' : '',
      disabled,
    };
  }
  return {
    label: t('Queued'),
    tone: 'reasoning',
    action: '',
    disabled: true,
  };
}

function buildWorkoutViews(
  workouts: PlannedWorkout[],
  state: ManagedPlanState,
  target: string | null,
  targetConnected: boolean,
  workingKey: string,
  mutationAvailable: boolean,
  canWrite: boolean,
): WorkoutView[] {
  return workouts.map((workout) => {
    const key = workoutKey(workout);
    const status = statusForWorkout(
      workout,
      state,
      target,
      targetConnected,
      key === workingKey,
      Boolean(workingKey),
      canWrite,
    );
    const date = workoutDateParts(workout);
    const activityType = workout.activity_type
      ?? (isRestWorkoutType(workout.workout_type) ? 'rest' : 'running');
    const activityLabels: Record<string, string> = {
      running: t('Road running'),
      trail_running: t('Trail running'),
      cycling: t('Cycling'),
      walking: t('Walking'),
      hiking: t('Hiking'),
      strength: t('Strength'),
      mobility: t('Mobility'),
      cross_training: t('Cross-training'),
      rest: t('Rest'),
      other: t('Other'),
    };
    return {
      key,
      day: date.day,
      weekday: date.weekday,
      workoutType: t(formatWorkoutType(workout.workout_type)),
      activity: activityLabels[activityType] ?? formatWorkoutType(activityType),
      sourceOwned: !isPraxysOwned(workout),
      details: workoutDetails(workout),
      description: workout.description ?? '',
      statusLabel: status.label,
      statusTone: status.tone,
      action: status.action,
      actionDisabled: status.disabled,
      editDisabled: !canWrite || Boolean(workingKey),
      canEdit: mutationAvailable
        && isPraxysOwned(workout)
        && workout.editable === true
        && Boolean(workout.workout_version),
      canDuplicate: mutationAvailable && !isPraxysOwned(workout),
    };
  });
}

function localIsoDate(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatWindowRange(start: string, end: string): string {
  const locale = detectLocale() === 'zh' ? 'zh-CN' : 'en-US';
  const options: Intl.DateTimeFormatOptions = {
    month: 'short',
    day: 'numeric',
  };
  const startLabel = new Date(`${start}T12:00:00`)
    .toLocaleDateString(locale, options);
  const endLabel = new Date(`${end}T12:00:00`)
    .toLocaleDateString(locale, options);
  return `${startLabel} – ${endLabel}`;
}

function isRestWorkoutType(value: string): boolean {
  return ['rest', 'off'].includes(value.trim().toLowerCase());
}

function workoutTypeOptions(
  value: string,
  tr: ReturnType<typeof translations>,
): { values: string[]; labels: string[]; index: number } {
  const values = [...WORKOUT_TYPE_VALUES] as string[];
  const labels = [
    tr.easy,
    tr.recovery,
    tr.longRun,
    tr.tempo,
    tr.threshold,
    tr.intervals,
    tr.hillRepeats,
    tr.testing,
    tr.rest,
    tr.customWording,
  ];
  const knownIndex = values.indexOf(value);
  if (knownIndex >= 0) return { values, labels, index: knownIndex };
  return {
    values,
    labels,
    index: values.indexOf('__custom__'),
  };
}

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function activityTypeOptions(
  value: PlanActivityType,
  tr: ReturnType<typeof translations>,
): { values: PlanActivityType[]; labels: string[]; index: number } {
  const labels: Record<PlanActivityType, string> = {
    running: tr.roadRunning,
    trail_running: tr.trailRunning,
    cycling: tr.cycling,
    walking: tr.walking,
    hiking: tr.hiking,
    strength: tr.strength,
    mobility: tr.mobility,
    cross_training: tr.crossTraining,
    rest: tr.rest,
    other: tr.other,
  };
  return {
    values: [...ACTIVITY_VALUES],
    labels: ACTIVITY_VALUES.map((activity) => labels[activity]),
    index: Math.max(0, ACTIVITY_VALUES.indexOf(value)),
  };
}

function defaultActivityType(workoutType: string): PlanActivityType {
  return isRestWorkoutType(workoutType) ? 'rest' : 'running';
}

function defaultStructure(workoutType: string): WorkoutStructureV1 {
  return isRestWorkoutType(workoutType)
    ? { steps: [] }
    : { steps: [createStep()] };
}

function targetDetail(
  kind: TargetKind,
): string {
  const details: Record<TargetKind, string> = {
    none: t('No unit or reference'),
    power_watts: t('Unit: watts · Reference: absolute'),
    power_cp: t('Unit: %CP · Reference: critical power'),
    heart_rate_bpm: t('Unit: bpm · Reference: absolute'),
    heart_rate_lthr: t('Unit: %LTHR · Reference: LTHR'),
    pace_absolute: t('Unit: sec/km · Reference: absolute'),
    pace_threshold: t('Unit: sec/km delta · Reference: threshold pace'),
    rpe: t('Unit: 10-point scale · Reference: perceived exertion'),
  };
  const ranges: Record<TargetKind, string> = {
    none: '',
    power_watts: targetRange(0, 5000, 'W'),
    power_cp: targetRange(0, 300, '%CP'),
    heart_rate_bpm: targetRange(0, 300, 'bpm'),
    heart_rate_lthr: targetRange(0, 200, '%LTHR'),
    pace_absolute: targetRange(0, 7200, 'sec/km'),
    pace_threshold: targetRange(-7200, 7200, 'sec/km Δ'),
    rpe: targetRange(0, 10, 'RPE'),
  };
  return ranges[kind]
    ? `${details[kind]} · ${t('Allowed range')}: ${ranges[kind]}`
    : details[kind];
}

function targetRange(minimum: number, maximum: number, unit: string): string {
  return `${minimum}–${maximum} ${unit}`;
}

function structureView(
  structure: WorkoutStructureV1,
): Array<EditorStepView | EditorRepeatView> {
  return structure.steps.map((node) => {
    if (node.type === 'step') return stepView(node);
    return {
      ...node,
      steps: node.steps.map(stepView),
    };
  });
}

function stepView(step: WorkoutStructureStep): EditorStepView {
  const kind = targetKind(step.target);
  return {
    ...step,
    phaseIndex: Math.max(0, PHASE_VALUES.indexOf(step.phase)),
    targetIndex: Math.max(0, TARGET_KINDS.indexOf(kind)),
    terminationIndex: Math.max(
      0,
      TERMINATION_VALUES.indexOf(step.termination.type),
    ),
    targetDetail: targetDetail(kind),
  };
}

function summaryLabels(
  structure: WorkoutStructureV1,
): {
  duration: string;
  distance: string;
  load: string;
  steps: number;
} {
  const summary = summarize(structure);
  return {
    duration: summary.duration.certainty === 'deterministic'
      ? `${Math.round(summary.duration.seconds / 60)} min · ${t('deterministic')}`
      : `${t('Unknown')} · ${t('unknown')}`,
    distance: summary.distance.certainty === 'deterministic'
      ? `${(summary.distance.meters / 1000).toFixed(2)} km · ${t('deterministic')}`
      : `${t('Unknown')} · ${t('unknown')}`,
    load: summary.load.certainty === 'estimated'
      ? `${t('Estimated from targets')} · ${t('estimated')}`
      : `${t('Unknown')} · ${t('unknown')}`,
    steps: summary.executableSteps,
  };
}

function compatibilityViews(
  compatibility: WorkoutProviderCompatibility[],
): CompatibilityView[] {
  const reasons: Record<WorkoutProviderCompatibilityReasonCode, string> = {
    activity_type_not_supported: t('This activity is not supported by the provider.'),
    duration_required: t('A positive duration is required by the provider.'),
    empty_structure_not_supported: t('An empty structured workout cannot be sent.'),
    flat_workout_not_lossless: t('This legacy flat workout would need a time duration and a power range to avoid provider defaults.'),
    invalid_structure: t('The workout structure is not a supported portable version.'),
    phase_not_supported: t('This step semantic cannot be represented safely.'),
    structured_workout_not_supported: t('Structured workouts are not supported by this provider.'),
    target_not_supported: t('This typed target cannot be represented safely.'),
    termination_not_supported: t('This step termination cannot be represented safely.'),
    wording_not_supported: t('Step or repeat wording cannot be preserved safely.'),
  };
  return compatibility.map((item) => ({
    target: item.target,
    title: item.target === 'garmin' ? 'Garmin' : 'Stryd',
    status: item.compatible ? t('Compatible') : t('Not safely representable'),
    compatible: item.compatible,
    tone: item.compatible ? 'safe' : 'warning',
    detail: item.compatible
      ? item.mode === 'structured'
        ? t('This portable structure can be represented without flattening.')
        : t('This legacy flat workout has no portable tree to flatten.')
      : '',
    reasons: item.reasons.map((reason) => reasons[reason.code]),
  }));
}

function adjustmentNotice(
  adjustment: PlanAdjustment | undefined,
): AdjustmentNoticeView | null {
  if (!adjustment) return null;
  const dateLabel = adjustment.workout_date
    ? new Date(`${adjustment.workout_date}T00:00:00`).toLocaleDateString(
      detectLocale() === 'zh' ? 'zh-CN' : 'en-US',
      { month: 'short', day: 'numeric' },
    )
    : '';
  const before = t(formatWorkoutType(adjustment.before.workout_type ?? t('Workout')));
  const after = t(formatWorkoutType(adjustment.after.workout_type ?? t('Rest')));
  const title = adjustment.status === 'undone'
    ? t('The previous workout was restored')
    : adjustment.status === 'superseded'
      ? t('An earlier automatic change was superseded')
      : t('Praxys made a conservative plan change');
  return {
    id: adjustment.id,
    title,
    detail: [
      dateLabel,
      `${before} \u2192 ${after}`,
      t('Current HRV crossed your personal caution band.'),
    ].filter(Boolean).join(' \u00b7 '),
    contextDetail: personalContextEvidenceIds(adjustment.evidence).length > 0
      ? t(
        'This change used confirmed private context. The private detail is not copied into the plan record.',
      )
      : '',
    tone: adjustment.status === 'active' ? 'warning' : 'neutral',
    canUndo: adjustment.can_undo,
  };
}

function resolutionLabel(
  action: PlanResolutionAction,
  reconciliation: PlanReconciliation,
): string {
  if (action === 'accept_target') {
    return tNamed(
      'Use {target} version',
      { target: platformLabel(reconciliation.target) },
    );
  }
  return reconciliation.state === 'delivery_failed'
    ? t('Retry delivery')
    : t('Restore Praxys');
}

function resolutionDescription(
  workout: PlannedWorkout,
  reconciliation: PlanReconciliation,
  action: PlanResolutionAction,
): string {
  const target = platformLabel(reconciliation.target);
  const lines: string[] = [];
  if (reconciliation.state !== 'target_only') {
    lines.push(
      `${t('Praxys version')}: ${t(formatWorkoutType(workout.workout_type))}`
      + (workoutDetails(workout) ? ` · ${workoutDetails(workout)}` : ''),
    );
  }
  lines.push(
    `${tNamed('{target} version', { target })}: ${
      reconciliation.target_workout
        ? targetWorkoutDetails(reconciliation.target_workout)
        : t('The target version is unavailable.')
    }`,
  );

  if (action === 'accept_target') {
    lines.push(
      t('copy the target workout into Praxys; future management follows that version.'),
    );
  } else {
    lines.push(
      t('keep the Praxys workout canonical and replace or recreate the target version.'),
    );
  }
  return lines.join('\n\n');
}

Component({
  options: { addGlobalClass: true },

  properties: {
    scope: {
      type: String as StringConstructor,
      value: 'window',
    },
  },

  data: {
    loading: true,
    errorMessage: '',
    actionError: '',
    hasResponse: false,
    refreshing: false,
    hasWorkouts: false,
    rawWorkouts: [] as PlannedWorkout[],
    workouts: [] as WorkoutView[],
    workoutCount: 0,
    conflictCount: 0,
    managementState: 'external' as ManagedPlanState,
    managementTitle: '',
    managementDetail: '',
    managementTone: 'neutral' as StatusTone,
    managementAction: '',
    target: '' as string,
    targetConnected: false,
    canWrite: true,
    workingKey: '',
    mutationAvailable: false,
    windowOffsetDays: 0,
    windowStart: localIsoDate(),
    windowEnd: localIsoDate(),
    windowLabel: '',
    hasExternalOverlap: false,
    overlapReviewAvailable: false,
    minimumDate: localIsoDate(),
    hasAdjustment: false,
    adjustment: null as AdjustmentNoticeView | null,
    adjustmentWorking: false,
    editorOpen: false,
    editorMode: 'create' as 'create' | 'edit',
    editorForked: false,
    editorCanonicalId: '',
    editorExpectedVersion: '',
    editorDate: localIsoDate(),
    editorWorkoutType: 'easy',
    editorCustomPurpose: '',
    editorIsRest: false,
    editorTypeIndex: 0,
    editorTypeValues: [...WORKOUT_TYPE_VALUES] as string[],
    editorTypeLabels: [] as string[],
    editorActivityType: 'running' as PlanActivityType,
    editorActivityIndex: 0,
    editorActivityValues: [...ACTIVITY_VALUES] as PlanActivityType[],
    editorActivityLabels: [] as string[],
    editorStructured: true,
    editorStructure: defaultStructure('easy'),
    editorLastNonRestStructure: defaultStructure('easy') as WorkoutStructureV1 | null,
    editorStructureView: [] as Array<EditorStepView | EditorRepeatView>,
    editorPhaseValues: [...PHASE_VALUES] as string[],
    editorPhaseLabels: [] as string[],
    editorTargetValues: [...TARGET_KINDS] as TargetKind[],
    editorTargetLabels: [] as string[],
    editorTerminationValues: [...TERMINATION_VALUES] as string[],
    editorTerminationLabels: [] as string[],
    editorSummaryDuration: '',
    editorSummaryDistance: '',
    editorSummaryLoad: '',
    editorSummarySteps: 0,
    editorUndo: null as RemovedNode | null,
    editorCompatibility: [] as CompatibilityView[],
    editorCompatibilityLoading: false,
    editorCompatibilityError: '',
    editorDuration: '',
    editorDistance: '',
    editorPowerMin: '',
    editorPowerMax: '',
    editorHrMin: '',
    editorHrMax: '',
    editorPaceMin: '',
    editorPaceMax: '',
    editorDescription: '',
    editorSaving: false,
    editorError: '',
    tr: translations(),
  },

  lifetimes: {
    attached() {
      const tr = translations();
      this.setData({
        tr,
        editorTypeValues: [...WORKOUT_TYPE_VALUES],
        editorTypeLabels: [
          tr.easy,
          tr.recovery,
          tr.longRun,
          tr.tempo,
          tr.threshold,
          tr.intervals,
          tr.hillRepeats,
          tr.testing,
          tr.rest,
          tr.customWording,
        ],
        editorActivityValues: [...ACTIVITY_VALUES],
        editorActivityLabels: activityTypeOptions('running', tr).labels,
        editorPhaseValues: [...PHASE_VALUES],
        editorPhaseLabels: [
          tr.warmup,
          tr.work,
          tr.recovery,
          tr.rest,
          tr.cooldown,
          tr.other,
        ],
        editorTargetValues: [...TARGET_KINDS],
        editorTargetLabels: [
          tr.noTarget,
          tr.powerWatts,
          tr.powerCp,
          tr.heartRateBpm,
          tr.heartRateLthr,
          tr.paceAbsolute,
          tr.paceThreshold,
          tr.rpe,
        ],
        editorTerminationValues: [...TERMINATION_VALUES],
        editorTerminationLabels: [
          tr.time,
          tr.distance,
          tr.open,
          tr.manual,
        ],
      });
      this.scheduleMidnightRefresh();
      void this.refresh();
    },
    detached() {
      this.clearMidnightRefresh();
      this.clearCompatibilityPreview();
      invalidateManagedPlanRequests(this);
    },
  },

  pageLifetimes: {
    show() {
      this.scheduleMidnightRefresh();
      if (this.data.hasResponse) void this.refresh();
    },
  },

  methods: {
    clearMidnightRefresh() {
      const componentState = this as unknown as {
        _localMidnightTimer?: number;
      };
      if (componentState._localMidnightTimer !== undefined) {
        clearTimeout(componentState._localMidnightTimer);
        componentState._localMidnightTimer = undefined;
      }
    },

    scheduleMidnightRefresh() {
      this.clearMidnightRefresh();
      const now = new Date();
      const nextMidnight = new Date(now);
      nextMidnight.setHours(24, 0, 0, 0);
      const componentState = this as unknown as {
        _localMidnightTimer?: number;
      };
      componentState._localMidnightTimer = setTimeout(() => {
        void this.refresh();
        this.scheduleMidnightRefresh();
      }, Math.max(nextMidnight.getTime() - now.getTime(), 1));
    },

    async refresh() {
      const requestGeneration = beginManagedPlanRequest(this);
      const isBackground = this.data.hasResponse;
      if (isBackground) {
        this.setData({
          errorMessage: '',
          refreshing: true,
          workouts: buildWorkoutViews(
            this.data.rawWorkouts,
            this.data.managementState,
            this.data.target || null,
            this.data.targetConnected,
            this.data.workingKey || REFRESH_WORKING_KEY,
            this.data.mutationAvailable,
            this.data.canWrite,
          ),
        });
      } else {
        this.setData({
          loading: true,
          refreshing: true,
          errorMessage: '',
        });
      }
      const days = this.data.scope === 'today' ? 1 : 14;
      const localToday = localIsoDate();
      const requestStart = this.data.scope === 'today'
        ? localToday
        : shiftAthletePlanDate(localToday, this.data.windowOffsetDays);
      try {
        const [settings, plan] = await Promise.all([
          apiGet<SettingsResponse>('/api/settings'),
          apiGet<PlanResponse>(
            planWindowUrl(days, new Date(`${requestStart}T12:00:00`)),
          ),
        ]);
        if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
        const state = managedPlanState(settings.config.plan_management);
        const target = settings.config.plan_management.execution_target
          ?? plan.sync_target
          ?? null;
        const targetConnected = target != null
          && settings.connection_statuses[target] === 'connected';
        const management = managementCopy(state, target, targetConnected);
        const rawWorkouts = plan.workouts;
        const canWrite = plan.management?.can_write !== false;
        const mutationAvailable = (
          plan.management?.mutation_api_version === 1
          && canWrite
        );
        const overlapWorkouts = rawWorkouts.filter(
          (workout) => workout.external_overlap,
        );
        const latestAdjustment = adjustmentNotice(plan.adjustments?.[0]);
        const workingKey = this.data.workingKey;
        this.setData({
          loading: false,
          refreshing: false,
          errorMessage: '',
          actionError: '',
          hasResponse: true,
          hasWorkouts: rawWorkouts.length > 0,
          rawWorkouts,
          workouts: buildWorkoutViews(
            rawWorkouts,
            state,
            target,
            targetConnected,
            workingKey,
            mutationAvailable,
            canWrite,
          ),
          workoutCount: rawWorkouts.length,
          conflictCount: rawWorkouts.filter(
            (workout) => workout.reconciliation?.conflict,
          ).length,
          managementState: state,
          managementTitle: management.title,
          managementDetail: management.detail,
          managementTone: management.tone,
          managementAction: management.action,
          target: target ?? '',
          targetConnected,
          canWrite,
          workingKey,
          mutationAvailable,
          windowStart: plan.window.start,
          windowEnd: plan.window.end,
          windowLabel: formatWindowRange(
            plan.window.start,
            plan.window.end,
          ),
          hasExternalOverlap: overlapWorkouts.length > 0,
          overlapReviewAvailable: overlapWorkouts.some(
            (workout) => (
              (workout.reconciliation?.resolutions.length ?? 0) > 0
            ),
          ),
          minimumDate: plan.management?.minimum_date ?? localIsoDate(),
          hasAdjustment: latestAdjustment != null,
          adjustment: latestAdjustment
            ? { ...latestAdjustment, canUndo: latestAdjustment.canUndo && canWrite }
            : null,
          adjustmentWorking: false,
        });
      } catch (error) {
        if (!isLatestManagedPlanRequest(this, requestGeneration)) return;
        const apiError = error as Partial<ApiError>;
        if (apiError.code === 'UNAUTHENTICATED') {
          this.setData({ loading: false, refreshing: false });
          return;
        }
        this.setData({
          loading: false,
          refreshing: false,
          errorMessage: apiError.detail ?? String(error),
        });
      }
    },

    async onUndoAdjustment() {
      const adjustment = this.data.adjustment as AdjustmentNoticeView | null;
      if (
        !adjustment?.canUndo
        || !this.data.canWrite
        || this.data.adjustmentWorking
        || this.data.workingKey
        || this.data.refreshing
      ) {
        return;
      }
      this.setData({ adjustmentWorking: true, actionError: '' });
      try {
        await apiPost(
          `/api/plan/adjustments/${encodeURIComponent(adjustment.id)}/undo`,
          {},
        );
        await this.refresh();
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        if (apiError.code === 'UNAUTHENTICATED') return;
        if (apiError.status === 409) await this.refresh();
        this.setData({
          actionError: apiError.detail
            ?? (error instanceof Error
              ? error.message
              : this.data.tr.restoreWorkoutFailed),
        });
      } finally {
        this.setData({ adjustmentWorking: false });
      }
    },

    onRetry() {
      void this.refresh();
    },

    onManagePlan() {
      wx.switchTab({ url: '/pages/settings/index' });
    },

    onReviewFirstConflict() {
      if (
        !this.data.canWrite
        || this.data.workingKey
        || this.data.refreshing
      ) return;
      const workout = this.data.rawWorkouts.find(
        (candidate) => (
          candidate.external_overlap
          && (candidate.reconciliation?.resolutions.length ?? 0) > 0
        ),
      );
      if (workout) this.reviewWorkout(workout);
    },

    onPreviousWindow() {
      if (
        this.data.scope !== 'window'
        || this.data.refreshing
        || this.data.windowOffsetDays === 0
      ) return;
      this.setData({
        windowOffsetDays: Math.max(
          0,
          this.data.windowOffsetDays - 14,
        ),
      }, () => void this.refresh());
    },

    onNextWindow() {
      if (this.data.scope !== 'window' || this.data.refreshing) return;
      this.setData({
        windowOffsetDays: this.data.windowOffsetDays + 14,
      }, () => void this.refresh());
    },

    onAddWorkout() {
      if (
        this.data.scope !== 'window'
        || !this.data.mutationAvailable
        || this.data.workingKey
        || this.data.refreshing
        || this.data.editorSaving
      ) return;
      this.openWorkoutEditor(null);
    },

    onEditWorkout(event: WechatMiniprogram.TouchEvent) {
      if (
        !this.data.mutationAvailable
        || this.data.workingKey
        || this.data.refreshing
        || this.data.editorSaving
      ) return;
      const key = String(event.currentTarget.dataset.key ?? '');
      const workout = this.data.rawWorkouts.find(
        (candidate) => workoutKey(candidate) === key,
      );
      if (
        !workout
        || !isPraxysOwned(workout)
        || workout.editable !== true
        || !workout.canonical_id
        || !workout.workout_version
      ) return;
      this.openWorkoutEditor(workout);
    },

    onDuplicateWorkout(event: WechatMiniprogram.TouchEvent) {
      if (
        !this.data.mutationAvailable
        || this.data.workingKey
        || this.data.refreshing
        || this.data.editorSaving
      ) return;
      const key = String(event.currentTarget.dataset.key ?? '');
      const workout = this.data.rawWorkouts.find(
        (candidate) => workoutKey(candidate) === key,
      );
      if (!workout || isPraxysOwned(workout)) return;
      this.openWorkoutEditor(workout, true);
    },

    openWorkoutEditor(
      workout: PlannedWorkout | null,
      forking = false,
    ) {
      const workoutType = workout?.workout_type ?? 'easy';
      const activityType = workout?.activity_type
        ?? defaultActivityType(workoutType);
      const typeOptions = workoutTypeOptions(
        workoutType,
        this.data.tr as ReturnType<typeof translations>,
      );
      const activityOptions = activityTypeOptions(
        activityType,
        this.data.tr as ReturnType<typeof translations>,
      );
      const defaultDate = this.data.windowStart > this.data.minimumDate
        ? this.data.windowStart
        : this.data.minimumDate;
      const hasStructure = (
        workout?.workout_structure_version === 'v1'
        && workout.workout_structure != null
      );
      const structured = hasStructure || workout == null;
      const structure: WorkoutStructureV1 = (
        hasStructure && workout?.workout_structure
      )
        ? workout.workout_structure
        : defaultStructure(workoutType);
      const summary = summaryLabels(structure);
      const date = workout?.date && workout.date >= this.data.minimumDate
        ? workout.date
        : defaultDate;
      this.setData({
        editorOpen: true,
        editorMode: workout && !forking ? 'edit' : 'create',
        editorForked: forking,
        editorCanonicalId: forking ? '' : workout?.canonical_id ?? '',
        editorExpectedVersion: forking ? '' : workout?.workout_version ?? '',
        editorDate: date ?? localIsoDate(),
        editorWorkoutType: typeOptions.values[typeOptions.index] === '__custom__'
          ? ''
          : workoutType,
        editorCustomPurpose: typeOptions.values[typeOptions.index] === '__custom__'
          ? workoutType
          : '',
        editorIsRest: isRestWorkoutType(workoutType),
        editorTypeIndex: typeOptions.index,
        editorTypeValues: typeOptions.values,
        editorTypeLabels: typeOptions.labels,
        editorActivityType: isRestWorkoutType(workoutType)
          ? 'rest'
          : activityType,
        editorActivityIndex: activityOptions.index,
        editorActivityValues: activityOptions.values,
        editorActivityLabels: activityOptions.labels,
        editorStructured: structured,
        editorStructure: structure,
        editorLastNonRestStructure: structured && !isRestWorkoutType(workoutType)
          ? structure
          : null,
        editorStructureView: structureView(structure),
        editorSummaryDuration: summary.duration,
        editorSummaryDistance: summary.distance,
        editorSummaryLoad: summary.load,
        editorSummarySteps: summary.steps,
        editorUndo: null,
        editorCompatibility: [],
        editorCompatibilityLoading: false,
        editorCompatibilityError: '',
        editorDuration: workout?.duration_min?.toString() ?? '',
        editorDistance: workout?.distance_km?.toString() ?? '',
        editorPowerMin: workout?.power_min?.toString() ?? '',
        editorPowerMax: workout?.power_max?.toString() ?? '',
        editorHrMin: workout?.hr_min?.toString() ?? '',
        editorHrMax: workout?.hr_max?.toString() ?? '',
        editorPaceMin: workout?.pace_min ?? '',
        editorPaceMax: workout?.pace_max ?? '',
        editorDescription: workout?.description ?? '',
        editorError: '',
      }, () => this.scheduleCompatibilityPreview());
    },

    onCloseEditor() {
      if (this.data.editorSaving) return;
      this.clearCompatibilityPreview();
      this.setData({ editorOpen: false, editorError: '' });
    },

    stopPropagation() {},

    onEditorDateChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      this.setData({ editorDate: String(event.detail.value ?? '') });
    },

    onEditorTypeChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const nextIndex = Number(event.detail.value);
      const nextType = this.data.editorTypeValues[nextIndex];
      if (!nextType) return;
      const workoutType = nextType === '__custom__' ? '' : nextType;
      const rest = isRestWorkoutType(workoutType);
      const structure = this.data.editorStructured
        ? rest
          ? { steps: [] }
          : this.data.editorStructure.steps.length === 0
            ? this.data.editorLastNonRestStructure
              ?? defaultStructure(workoutType)
            : this.data.editorStructure
        : this.data.editorStructure;
      const summary = summaryLabels(structure);
      this.setData({
        editorTypeIndex: nextIndex,
        editorWorkoutType: workoutType,
        editorIsRest: rest,
        editorActivityType: rest
          ? 'rest'
          : this.data.editorActivityType === 'rest'
            ? 'running'
            : this.data.editorActivityType,
        editorActivityIndex: rest
          ? ACTIVITY_VALUES.indexOf('rest')
          : this.data.editorActivityType === 'rest'
            ? ACTIVITY_VALUES.indexOf('running')
            : this.data.editorActivityIndex,
        editorStructure: structure,
        editorLastNonRestStructure: this.data.editorStructured && rest
          ? this.data.editorStructure.steps.length > 0
            ? this.data.editorStructure
            : this.data.editorLastNonRestStructure
          : this.data.editorLastNonRestStructure,
        editorStructureView: structureView(structure),
        editorSummaryDuration: summary.duration,
        editorSummaryDistance: summary.distance,
        editorSummaryLoad: summary.load,
        editorSummarySteps: summary.steps,
      }, () => this.scheduleCompatibilityPreview());
    },

    onEditorActivityChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const nextIndex = Number(event.detail.value);
      const activityType = this.data.editorActivityValues[nextIndex];
      if (!activityType || this.data.editorIsRest) return;
      this.setData({
        editorActivityIndex: nextIndex,
        editorActivityType: activityType,
      }, () => this.scheduleCompatibilityPreview());
    },

    onEditorCustomPurpose(event: WechatMiniprogram.Input) {
      const workoutType = String(event.detail.value ?? '');
      this.setData({
        editorCustomPurpose: workoutType,
        editorWorkoutType: workoutType,
      }, () => this.scheduleCompatibilityPreview());
    },

    onEditorInput(event: WechatMiniprogram.Input) {
      const field = String(event.currentTarget.dataset.field ?? '');
      const value = String(event.detail.value ?? '');
      let patch: Record<string, string> | null = null;
      if (field === 'editorDuration') {
        patch = { editorDuration: value };
      } else if (field === 'editorDistance') {
        patch = { editorDistance: value };
      } else if (field === 'editorPowerMin') {
        patch = { editorPowerMin: value };
      } else if (field === 'editorPowerMax') {
        patch = { editorPowerMax: value };
      } else if (field === 'editorHrMin') {
        patch = { editorHrMin: value };
      } else if (field === 'editorHrMax') {
        patch = { editorHrMax: value };
      } else if (field === 'editorPaceMin') {
        patch = { editorPaceMin: value };
      } else if (field === 'editorPaceMax') {
        patch = { editorPaceMax: value };
      } else if (field === 'editorDescription') {
        patch = { editorDescription: value };
      }
      if (patch) this.setData(patch, () => this.scheduleCompatibilityPreview());
    },

    clearCompatibilityPreview() {
      const componentState = this as unknown as {
        _compatibilityTimer?: number;
      };
      if (componentState._compatibilityTimer !== undefined) {
        clearTimeout(componentState._compatibilityTimer);
        componentState._compatibilityTimer = undefined;
      }
    },

    scheduleCompatibilityPreview() {
      this.clearCompatibilityPreview();
      if (!this.data.editorOpen) return;
      const validationError = this.editorValidationError();
      if (validationError) {
        this.setData({
          editorCompatibility: [],
          editorCompatibilityLoading: false,
          editorCompatibilityError: '',
        });
        return;
      }
      const componentState = this as unknown as {
        _compatibilityTimer?: number;
      };
      componentState._compatibilityTimer = setTimeout(() => {
        componentState._compatibilityTimer = undefined;
        void this.previewCompatibility();
      }, 250);
    },

    async previewCompatibility() {
      if (!this.data.editorOpen || this.data.editorSaving) return;
      this.setData({
        editorCompatibilityLoading: true,
        editorCompatibilityError: '',
      });
      try {
        const response = await apiPost<PlanWorkoutCompatibilityResponse>(
          '/api/plan/workouts/compatibility',
          this.editorPayload(),
        );
        if (!this.data.editorOpen) return;
        this.setData({
          editorCompatibility: compatibilityViews(response.providers),
          editorCompatibilityError: '',
        });
      } catch {
        if (!this.data.editorOpen) return;
        this.setData({
          editorCompatibility: [],
          editorCompatibilityError: this.data.tr.compatibilityUnavailable,
        });
      } finally {
        if (this.data.editorOpen) {
          this.setData({ editorCompatibilityLoading: false });
        }
      }
    },

    applyStructuredEditor(
      structure: WorkoutStructureV1,
      extra: Record<string, unknown> = {},
    ) {
      const summary = summaryLabels(structure);
      this.setData({
        editorStructure: structure,
        editorStructureView: structureView(structure),
        editorSummaryDuration: summary.duration,
        editorSummaryDistance: summary.distance,
        editorSummaryLoad: summary.load,
        editorSummarySteps: summary.steps,
        ...extra,
      }, () => this.scheduleCompatibilityPreview());
    },

    editorPath(
      event: { currentTarget: { dataset: Record<string, unknown> } },
    ): WorkoutNodePath | null {
      const root = Number(event.currentTarget.dataset.root);
      const rawChild = event.currentTarget.dataset.child;
      if (!Number.isInteger(root) || root < 0) return null;
      if (rawChild === undefined || rawChild === '') return [root];
      const child = Number(rawChild);
      return Number.isInteger(child) && child >= 0 ? [root, child] : null;
    },

    onStructuredPhaseChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const path = this.editorPath(event);
      const index = Number(event.detail.value);
      const phase = PHASE_VALUES[index];
      if (!path || !phase) return;
      this.applyStructuredEditor(updateStep(
        this.data.editorStructure,
        path,
        { phase },
      ));
    },

    onStructuredTerminationChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const path = this.editorPath(event);
      const index = Number(event.detail.value);
      const type = TERMINATION_VALUES[index];
      if (!path || !type) return;
      const rootNode = this.data.editorStructure.steps[path[0]];
      const node = path.length === 1
        ? rootNode
        : rootNode?.type === 'repeat'
          ? rootNode.steps[path[1]]
          : null;
      if (!node || node.type !== 'step') return;
      const termination = type === 'time'
        ? {
            type,
            seconds: node.termination.type === 'time'
              ? node.termination.seconds
              : 60,
          }
        : type === 'distance'
          ? {
              type,
              meters: node.termination.type === 'distance'
                ? node.termination.meters
                : 1000,
            }
          : { type };
      this.applyStructuredEditor(updateStep(
        this.data.editorStructure,
        path,
        { termination },
      ));
    },

    onStructuredTargetChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const path = this.editorPath(event);
      const index = Number(event.detail.value);
      const kind = this.data.editorTargetValues[index];
      if (!path || !kind) return;
      this.applyStructuredEditor(updateStep(
        this.data.editorStructure,
        path,
        { target: targetForKind(kind) },
      ));
    },

    onStructuredInput(event: WechatMiniprogram.Input) {
      const path = this.editorPath(event);
      const field = String(event.currentTarget.dataset.field ?? '');
      const value = String(event.detail.value ?? '');
      if (!path) return;
      if (field === 'repeatLabel' || field === 'repetitions') {
        const rootIndex = path[0];
        const repeat = this.data.editorStructure.steps[rootIndex];
        if (!repeat || repeat.type !== 'repeat') return;
        this.applyStructuredEditor(updateRepeat(
          this.data.editorStructure,
          rootIndex,
          field === 'repeatLabel'
            ? { label: value || null }
            : {
                repetitions: Number.isInteger(Number(value))
                  ? Number(value)
                  : repeat.repetitions,
              },
        ));
        return;
      }
      const rootNode = this.data.editorStructure.steps[path[0]];
      const step = path.length === 1
        ? rootNode
        : rootNode?.type === 'repeat'
          ? rootNode.steps[path[1]]
          : null;
      if (!step || step.type !== 'step') return;
      if (field === 'label' || field === 'instructions') {
        this.applyStructuredEditor(updateStep(
          this.data.editorStructure,
          path,
          { [field]: value || null },
        ));
        return;
      }
      if (field === 'seconds' && step.termination.type === 'time') {
        const seconds = Number(value);
        if (!Number.isInteger(seconds)) return;
        this.applyStructuredEditor(updateStep(
          this.data.editorStructure,
          path,
          { termination: { type: 'time', seconds } },
        ));
        return;
      }
      if (field === 'meters' && step.termination.type === 'distance') {
        const meters = Number(value);
        if (!Number.isInteger(meters)) return;
        this.applyStructuredEditor(updateStep(
          this.data.editorStructure,
          path,
          { termination: { type: 'distance', meters } },
        ));
        return;
      }
      if (field === 'targetMin' || field === 'targetMax') {
        const target = { ...step.target } as Record<string, unknown>;
        const numeric = optionalNumber(value);
        const bound = field === 'targetMin' ? 'min' : 'max';
        if (numeric === null) delete target[bound];
        else target[bound] = numeric;
        this.applyStructuredEditor(updateStep(
          this.data.editorStructure,
          path,
          { target: target as typeof step.target },
        ));
      }
    },

    onStructuredAction(event: WechatMiniprogram.TouchEvent) {
      const path = this.editorPath(event);
      const action = String(event.currentTarget.dataset.action ?? '');
      if (!path) return;
      if (action === 'add-repeat-step') {
        const repeat = this.data.editorStructure.steps[path[0]];
        if (!repeat || repeat.type !== 'repeat') return;
        this.applyStructuredEditor(updateRepeat(
          this.data.editorStructure,
          path[0],
          { steps: [...repeat.steps, createStep()] },
        ));
        return;
      }
      if (action === 'move-up' || action === 'move-down') {
        this.applyStructuredEditor(moveNode(
          this.data.editorStructure,
          path,
          action === 'move-up' ? 'up' : 'down',
        ));
        return;
      }
      if (action === 'duplicate') {
        this.applyStructuredEditor(duplicateNode(
          this.data.editorStructure,
          path,
        ));
        return;
      }
      if (action === 'insert-before' || action === 'insert-after') {
        const rootNode = this.data.editorStructure.steps[path[0]];
        const node = path.length === 1 && rootNode?.type === 'repeat'
          ? createRepeat()
          : createStep();
        this.applyStructuredEditor(insertNode(
          this.data.editorStructure,
          path,
          node,
          action === 'insert-after',
        ));
        return;
      }
      if (action === 'delete') {
        const result = removeNode(this.data.editorStructure, path);
        if (!result.removed) return;
        this.applyStructuredEditor(result.structure, {
          editorUndo: result.removed,
        });
      }
    },

    onAddStructuredStep() {
      this.applyStructuredEditor({
        steps: [...this.data.editorStructure.steps, createStep()],
      });
    },

    onAddStructuredRepeat() {
      this.applyStructuredEditor({
        steps: [...this.data.editorStructure.steps, createRepeat()],
      });
    },

    onUndoStructuredDelete() {
      const removed = this.data.editorUndo as RemovedNode | null;
      if (!removed) return;
      this.applyStructuredEditor(
        restoreNode(this.data.editorStructure, removed),
        { editorUndo: null },
      );
    },

    onConvertLegacyToStructured() {
      try {
        const structure = synthesizeFromFlat({
          workoutType: this.data.editorWorkoutType,
          duration: optionalNumber(this.data.editorDuration),
          distance: optionalNumber(this.data.editorDistance),
          powerMin: optionalNumber(this.data.editorPowerMin),
          powerMax: optionalNumber(this.data.editorPowerMax),
          hrMin: optionalNumber(this.data.editorHrMin),
          hrMax: optionalNumber(this.data.editorHrMax),
          paceMin: this.data.editorPaceMin.trim() || null,
          paceMax: this.data.editorPaceMax.trim() || null,
        });
        this.applyStructuredEditor(structure, {
          editorStructured: true,
          editorError: '',
        });
      } catch (error) {
        this.setData({
          editorError: t('Could not convert this legacy workout.'),
        });
      }
    },

    editorValidationError(): string | null {
      if (!this.data.editorDate) return this.data.tr.date;
      if (!this.data.editorWorkoutType.trim()) {
        return this.data.tr.customWorkoutPurpose;
      }
      return this.data.editorStructured
        ? (
          validate(
            this.data.editorStructure,
            this.data.editorWorkoutType,
          )
            ? t(
              'Review the highlighted step fields. Every typed target and termination must be complete.',
            )
            : null
        )
        : null;
    },

    editorPayload(): PlanWorkoutWriteFields {
      const isRest = isRestWorkoutType(this.data.editorWorkoutType);
      const flat = {
        date: this.data.editorDate,
        activity_type: isRest ? 'rest' : this.data.editorActivityType,
        workout_type: this.data.editorWorkoutType.trim(),
        planned_duration_min: isRest
          ? null
          : optionalNumber(this.data.editorDuration),
        planned_distance_km: isRest
          ? null
          : optionalNumber(this.data.editorDistance),
        target_power_min: isRest
          ? null
          : optionalNumber(this.data.editorPowerMin),
        target_power_max: isRest
          ? null
          : optionalNumber(this.data.editorPowerMax),
        target_hr_min: isRest
          ? null
          : optionalNumber(this.data.editorHrMin),
        target_hr_max: isRest
          ? null
          : optionalNumber(this.data.editorHrMax),
        target_pace_min: isRest
          ? null
          : this.data.editorPaceMin.trim() || null,
        target_pace_max: isRest
          ? null
          : this.data.editorPaceMax.trim() || null,
        workout_description: this.data.editorDescription.trim(),
      };
      if (!this.data.editorStructured) {
        return flat as PlanWorkoutWriteFields;
      }
      const projection = isRest
        ? {
            planned_duration_min: null,
            planned_distance_km: null,
            target_power_min: null,
            target_power_max: null,
            target_hr_min: null,
            target_hr_max: null,
            target_pace_min: null,
            target_pace_max: null,
          }
        : deriveFlat(this.data.editorStructure);
      return {
        ...flat,
        ...projection,
        activity_type: isRest ? 'rest' : this.data.editorActivityType,
        workout_structure_version: 'v1',
        workout_structure: this.data.editorStructure,
      } as PlanWorkoutWriteFields;
    },

    async onSaveWorkout() {
      if (
        this.data.editorSaving
        || !this.data.editorDate
        || !this.data.editorWorkoutType
      ) return;
      const validationError = this.editorValidationError();
      if (validationError) {
        this.setData({ editorError: validationError });
        return;
      }
      this.setData({ editorSaving: true, editorError: '', actionError: '' });
      try {
        const payload = this.editorPayload();
        let result: PlanWorkoutMutationResponse;
        if (this.data.editorMode === 'edit') {
          if (
            !this.data.editorCanonicalId
            || !this.data.editorExpectedVersion
          ) {
            throw new Error(this.data.tr.refreshBeforeEditing);
          }
          result = await apiPut<PlanWorkoutMutationResponse>(
            `/api/plan/workouts/${encodeURIComponent(this.data.editorCanonicalId)}`,
            {
              ...payload,
              expected_version: this.data.editorExpectedVersion,
            } satisfies PlanWorkoutUpdateRequest,
          );
        } else {
          result = await apiPost<PlanWorkoutMutationResponse>(
            '/api/plan/workouts',
            payload,
          );
        }
        await this.moveWindowToDate(result.date);
        this.setData({ editorOpen: false, editorError: '' });
        wx.showToast({
          title: this.data.tr.done,
          icon: 'success',
          duration: 1200,
        });
        await this.refresh();
      } catch (error) {
        await this.handleWorkoutMutationError(
          error,
          this.data.editorMode === 'create'
            ? this.data.tr.couldNotAddWorkout
            : this.data.tr.couldNotUpdateWorkout,
        );
      } finally {
        this.setData({ editorSaving: false });
      }
    },

    onDeleteWorkout() {
      if (this.data.editorMode !== 'edit' || this.data.editorSaving) return;
      wx.showModal({
        title: this.data.tr.deleteThisWorkout,
        content: this.data.tr.deleteWorkoutDetail,
        confirmText: this.data.tr.delete,
        cancelText: this.data.tr.cancel,
        success: (result) => {
          if (result.confirm) void this.deleteWorkout();
        },
      });
    },

    async deleteWorkout() {
      if (
        !this.data.editorCanonicalId
        || !this.data.editorExpectedVersion
        || this.data.editorSaving
      ) return;
      this.setData({ editorSaving: true, editorError: '', actionError: '' });
      try {
        const params = `expected_version=${encodeURIComponent(
          this.data.editorExpectedVersion,
        )}`;
        await apiDelete<PlanWorkoutDeleteResponse>(
          `/api/plan/workouts/${encodeURIComponent(
            this.data.editorCanonicalId,
          )}?${params}`,
        );
        this.setData({ editorOpen: false, editorError: '' });
        wx.showToast({
          title: this.data.tr.done,
          icon: 'success',
          duration: 1200,
        });
        await this.refresh();
      } catch (error) {
        await this.handleWorkoutMutationError(
          error,
          this.data.tr.couldNotDeleteWorkout,
        );
      } finally {
        this.setData({ editorSaving: false });
      }
    },

    async onConvertToRest() {
      if (
        this.data.editorMode !== 'edit'
        || !this.data.editorCanonicalId
        || !this.data.editorExpectedVersion
        || this.data.editorSaving
      ) return;
      this.setData({ editorSaving: true, editorError: '', actionError: '' });
      try {
        const restFields = {
          expected_version: this.data.editorExpectedVersion,
          date: this.data.editorDate,
          activity_type: 'rest' as const,
          workout_type: 'rest',
          planned_duration_min: null,
          planned_distance_km: null,
          target_power_min: null,
          target_power_max: null,
          target_hr_min: null,
          target_hr_max: null,
          target_pace_min: null,
          target_pace_max: null,
          workout_description: '',
        };
        const restPayload: PlanWorkoutUpdateRequest = this.data.editorStructured
          ? {
              ...restFields,
              workout_structure_version: 'v1',
              workout_structure: { steps: [] },
            }
          : restFields;
        const result = await apiPut<PlanWorkoutMutationResponse>(
          `/api/plan/workouts/${encodeURIComponent(
            this.data.editorCanonicalId,
          )}`,
          restPayload,
        );
        await this.moveWindowToDate(result.date);
        this.setData({ editorOpen: false, editorError: '' });
        wx.showToast({
          title: this.data.tr.done,
          icon: 'success',
          duration: 1200,
        });
        await this.refresh();
      } catch (error) {
        await this.handleWorkoutMutationError(
          error,
          this.data.tr.couldNotConvertToRest,
        );
      } finally {
        this.setData({ editorSaving: false });
      }
    },

    async handleWorkoutMutationError(
      error: unknown,
      fallback: string,
    ) {
      const apiError = error as Partial<ApiError>;
      if (apiError.code === 'UNAUTHENTICATED') return;
      if (apiError.code === 'PLAN_VERSION_CONFLICT') {
        this.setData({
          editorOpen: false,
          editorError: '',
        });
        await this.refresh();
        this.setData({ actionError: this.data.tr.staleWorkout });
        wx.showModal({
          title: this.data.tr.editWorkout,
          content: this.data.tr.staleWorkout,
          showCancel: false,
          confirmText: this.data.tr.done,
        });
        return;
      }
      if (apiError.code === 'PLAN_HISTORY_IMMUTABLE') {
        this.setData({
          editorOpen: false,
          editorError: '',
        });
        await this.refresh();
        this.setData({ actionError: this.data.tr.completedHistory });
        wx.showModal({
          title: this.data.tr.editWorkout,
          content: this.data.tr.completedHistory,
          showCancel: false,
          confirmText: this.data.tr.done,
        });
        return;
      }
      if (apiError.code === 'PLAN_WORKOUT_STRUCTURE_INVALID') {
        this.setData({
          editorError: t(
            'Review the highlighted step fields. Every typed target and termination must be complete.',
          ),
        });
        return;
      }
      if (apiError.code === 'PLAN_STRUCTURE_PROJECTION_CONFLICT') {
        this.setData({
          editorError: t(
            'This structure is authoritative. Edit its steps instead of changing its flat summary.',
          ),
        });
        return;
      }
      if (apiError.code === 'PLAN_WORKOUT_STRUCTURE_UNSUPPORTED') {
        this.setData({
          editorError: t(
            'This imported structure cannot be edited safely. Duplicate it into a supported Praxys workout first.',
          ),
        });
        return;
      }
      this.setData({
        editorError: apiError.detail
          ?? (error instanceof Error ? error.message : fallback),
      });
    },

    onWorkoutAction(event: WechatMiniprogram.TouchEvent) {
      if (
        !this.data.canWrite
        || this.data.workingKey
        || this.data.refreshing
        || this.data.adjustmentWorking
      ) return;
      const key = String(event.currentTarget.dataset.key ?? '');
      const action = String(event.currentTarget.dataset.action ?? '') as WorkoutAction;
      const workout = this.data.rawWorkouts.find(
        (candidate) => workoutKey(candidate) === key,
      );
      if (!workout) return;
      if (action === 'deliver') {
        void this.deliverWorkout(workout);
      } else if (action === 'review') {
        this.reviewWorkout(workout);
      }
    },

    reviewWorkout(workout: PlannedWorkout) {
      if (!this.data.canWrite) return;
      const reconciliation = workout.reconciliation;
      if (!reconciliation || reconciliation.resolutions.length === 0) return;
      const actions = reconciliation.resolutions.filter(
        (action) => (
          action === 'accept_target'
          || (action === 'restore_praxys' && this.data.targetConnected)
        ),
      );
      if (actions.length === 0) return;
      const choices = actions.map(
        (action) => resolutionLabel(action, reconciliation),
      );
      const choose = (index: number) => {
        const action = actions[index];
        if (action) this.confirmResolution(workout, reconciliation, action);
      };
      if (choices.length === 1) {
        choose(0);
        return;
      }
      wx.showActionSheet({
        itemList: choices,
        success: (result) => choose(result.tapIndex),
      });
    },

    confirmResolution(
      workout: PlannedWorkout,
      reconciliation: PlanReconciliation,
      action: PlanResolutionAction,
    ) {
      wx.showModal({
        title: resolutionLabel(action, reconciliation),
        content: resolutionDescription(workout, reconciliation, action),
        confirmText: this.data.tr.confirm,
        cancelText: this.data.tr.cancel,
        success: (result) => {
          if (result.confirm) void this.resolveWorkout(workout, action);
        },
      });
    },

    async deliverWorkout(workout: PlannedWorkout) {
      if (!workout.canonical_id) {
        this.setData({ actionError: this.data.tr.deliveryFailed });
        return;
      }
      const key = workoutKey(workout);
      this.setWorking(key);
      try {
        const body = {
          workout_dates: [workout.date],
          canonical_ids: [workout.canonical_id],
        };
        const response = await apiPost<{ results: StrydPushResult[] }>(
          '/api/plan/push-stryd',
          body,
        );
        const result = response.results.find(
          (candidate) => candidate.canonical_id === workout.canonical_id
            || (
              candidate.canonical_id == null
              && candidate.date === workout.date
            ),
        );
        if (!result) throw new Error(this.data.tr.missingDeliveryResult);
        if (result.status === 'error') throw new Error(result.error);
        await this.refresh();
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        if (apiError.code === 'UNAUTHENTICATED') return;
        this.setData({
          actionError: apiError.detail
            ?? (error instanceof Error ? error.message : this.data.tr.deliveryFailed),
        });
      } finally {
        this.setWorking('');
      }
    },

    async resolveWorkout(
      workout: PlannedWorkout,
      action: PlanResolutionAction,
    ) {
      const reconciliationId = workout.reconciliation?.id;
      if (!reconciliationId) return;
      const key = workoutKey(workout);
      this.setWorking(key);
      try {
        await apiPost<PlanResolutionResponse>(
          '/api/plan/reconciliation/resolve',
          {
            reconciliation_id: reconciliationId,
            action,
          },
        );
        wx.showToast({
          title: this.data.tr.done,
          icon: 'success',
          duration: 1200,
        });
        await this.refresh();
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        if (apiError.code === 'UNAUTHENTICATED') return;
        this.setData({
          actionError: apiError.detail
            ?? (error instanceof Error ? error.message : this.data.tr.couldNotResolve),
        });
      } finally {
        this.setWorking('');
      }
    },

    setWorking(key: string) {
      if (key) this.setData({ actionError: '' });
      this.setData({
        workingKey: key,
        workouts: buildWorkoutViews(
          this.data.rawWorkouts,
          this.data.managementState,
          this.data.target || null,
          this.data.targetConnected,
          key || (this.data.refreshing ? REFRESH_WORKING_KEY : ''),
          this.data.mutationAvailable,
          this.data.canWrite,
        ),
      });
    },

    moveWindowToDate(workoutDate: string): Promise<void> {
      if (this.data.scope !== 'window') return Promise.resolve();
      const dateOffset = Math.max(
        0,
        athletePlanDateDistance(localIsoDate(), workoutDate),
      );
      const nextOffset = Math.floor(dateOffset / 14) * 14;
      if (nextOffset === this.data.windowOffsetDays) {
        return Promise.resolve();
      }
      return new Promise((resolve) => {
        this.setData({ windowOffsetDays: nextOffset }, resolve);
      });
    },
  },
});
