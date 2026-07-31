import { apiGet, apiPost } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { detectLocale, t, tFmt, tNamed } from '../../utils/i18n';
import {
  beginManagedPlanRequest,
  formatWorkoutType,
  invalidateManagedPlanRequests,
  isPraxysOwned,
  isLatestManagedPlanRequest,
  managedPlanState,
  planWindowUrl,
  workoutKey,
} from '../../utils/managed-plan';
import type {
  PlanReconciliation,
  PlanResolutionAction,
  PlanResolutionResponse,
  PlanResponse,
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
    return canAccept
      ? {
        label: t('Use in Praxys'),
        tone: 'positive',
        action: 'review',
        disabled: anyActionWorking,
      }
      : {
        label: t('External'),
        tone: 'neutral',
        action: '',
        disabled: true,
      };
  }

  if (workout.workout_type.toLowerCase() === 'rest') {
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

  const disabled = anyActionWorking
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
      action: 'review',
      disabled,
    };
  }
  if (reconciliationState === 'delivery_failed') {
    return {
      label: t('Retry delivery'),
      tone: 'danger',
      action: 'review',
      disabled,
    };
  }
  if (workout.sync_state === 'mismatch' && reconciliation) {
    return {
      label: t('Review conflict'),
      tone: 'warning',
      action: 'review',
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
      label: t('Deliver now'),
      tone: 'positive',
      action: 'deliver',
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
    };
  });
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
    workingKey: '',
    tr: translations(),
  },

  lifetimes: {
    attached() {
      this.setData({ tr: translations() });
      void this.refresh();
    },
    detached() {
      invalidateManagedPlanRequests(this);
    },
  },

  pageLifetimes: {
    show() {
      if (this.data.hasResponse) void this.refresh();
    },
  },

  methods: {
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
      try {
        const [settings, plan] = await Promise.all([
          apiGet<SettingsResponse>('/api/settings'),
          apiGet<PlanResponse>(planWindowUrl(days)),
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
          workingKey,
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

    onRetry() {
      void this.refresh();
    },

    onManagePlan() {
      wx.switchTab({ url: '/pages/settings/index' });
    },

    onWorkoutAction(event: WechatMiniprogram.TouchEvent) {
      if (this.data.workingKey || this.data.refreshing) return;
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
        ),
      });
    },
  },
});
