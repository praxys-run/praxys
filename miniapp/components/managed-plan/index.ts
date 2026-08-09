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
import type {
  PlanAdjustment,
  PlanReconciliation,
  PlanResolutionAction,
  PlanResolutionResponse,
  PlanResponse,
  PlanWorkoutDeleteResponse,
  PlanWorkoutMutationResponse,
  PlanWorkoutUpdateRequest,
  PlanWorkoutWriteFields,
  PlannedWorkout,
  PlanTargetWorkoutSnapshot,
  SettingsResponse,
  StrydPushResult,
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
  details: string;
  description: string;
  statusLabel: string;
  statusTone: StatusTone;
  action: WorkoutAction;
  actionDisabled: boolean;
  editDisabled: boolean;
  canEdit: boolean;
}

const WORKOUT_TYPE_VALUES = [
  'easy',
  'recovery',
  'long_run',
  'tempo',
  'threshold',
  'interval',
  'rest',
] as const;

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
    workoutType: t('Workout type'),
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
    return {
      key,
      day: date.day,
      weekday: date.weekday,
      workoutType: t(formatWorkoutType(workout.workout_type)),
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
    tr.rest,
  ];
  const knownIndex = values.indexOf(value);
  if (knownIndex >= 0) return { values, labels, index: knownIndex };
  return {
    values: [value, ...values],
    labels: [formatWorkoutType(value), ...labels],
    index: 0,
  };
}

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
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
    editorCanonicalId: '',
    editorExpectedVersion: '',
    editorDate: localIsoDate(),
    editorWorkoutType: 'easy',
    editorIsRest: false,
    editorTypeIndex: 0,
    editorTypeValues: [...WORKOUT_TYPE_VALUES] as string[],
    editorTypeLabels: [] as string[],
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
          tr.rest,
        ],
      });
      this.scheduleMidnightRefresh();
      void this.refresh();
    },
    detached() {
      this.clearMidnightRefresh();
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

    openWorkoutEditor(workout: PlannedWorkout | null) {
      const workoutType = workout?.workout_type ?? 'easy';
      const typeOptions = workoutTypeOptions(
        workoutType,
        this.data.tr as ReturnType<typeof translations>,
      );
      const defaultDate = this.data.windowStart > this.data.minimumDate
        ? this.data.windowStart
        : this.data.minimumDate;
      this.setData({
        editorOpen: true,
        editorMode: workout ? 'edit' : 'create',
        editorCanonicalId: workout?.canonical_id ?? '',
        editorExpectedVersion: workout?.workout_version ?? '',
        editorDate: workout?.date ?? defaultDate ?? localIsoDate(),
        editorWorkoutType: workoutType,
        editorIsRest: isRestWorkoutType(workoutType),
        editorTypeIndex: typeOptions.index,
        editorTypeValues: typeOptions.values,
        editorTypeLabels: typeOptions.labels,
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
      });
    },

    onCloseEditor() {
      if (this.data.editorSaving) return;
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
      this.setData({
        editorTypeIndex: nextIndex,
        editorWorkoutType: nextType,
        editorIsRest: isRestWorkoutType(nextType),
      });
    },

    onEditorInput(event: WechatMiniprogram.Input) {
      const field = String(event.currentTarget.dataset.field ?? '');
      const value = String(event.detail.value ?? '');
      if (field === 'editorDuration') {
        this.setData({ editorDuration: value });
      } else if (field === 'editorDistance') {
        this.setData({ editorDistance: value });
      } else if (field === 'editorPowerMin') {
        this.setData({ editorPowerMin: value });
      } else if (field === 'editorPowerMax') {
        this.setData({ editorPowerMax: value });
      } else if (field === 'editorHrMin') {
        this.setData({ editorHrMin: value });
      } else if (field === 'editorHrMax') {
        this.setData({ editorHrMax: value });
      } else if (field === 'editorPaceMin') {
        this.setData({ editorPaceMin: value });
      } else if (field === 'editorPaceMax') {
        this.setData({ editorPaceMax: value });
      } else if (field === 'editorDescription') {
        this.setData({ editorDescription: value });
      }
    },

    editorPayload(): PlanWorkoutWriteFields {
      const isRest = isRestWorkoutType(this.data.editorWorkoutType);
      return {
        date: this.data.editorDate,
        workout_type: this.data.editorWorkoutType,
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
    },

    async onSaveWorkout() {
      if (
        this.data.editorSaving
        || !this.data.editorDate
        || !this.data.editorWorkoutType
      ) return;
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
        const result = await apiPut<PlanWorkoutMutationResponse>(
          `/api/plan/workouts/${encodeURIComponent(
            this.data.editorCanonicalId,
          )}`,
          {
            expected_version: this.data.editorExpectedVersion,
            date: this.data.editorDate,
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
          } satisfies PlanWorkoutUpdateRequest,
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
