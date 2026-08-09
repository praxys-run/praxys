import { useState } from 'react';
import { Plural, Trans, useLingui } from '@lingui/react/macro';
import {
  ArrowRight,
  CalendarSync,
  Check,
  CirclePause,
  HeartPulse,
  RotateCcw,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';

import ScienceNote from '@/components/ScienceNote';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { apiFetch, extractErrorMessage, useApi } from '@/hooks/useApi';
import { useLocale } from '@/contexts/LocaleContext';
import { cn } from '@/lib/utils';
import { planTargetSelection } from '@/lib/plan-delivery';
import {
  MANAGED_PLAN_WINDOW_DAYS,
  isPraxysOwned,
  managedPlanPreviewUrl,
  managedPlanWindow,
  managedPlanState,
} from '@/lib/plan';
import type {
  PlanAdjustmentHistoryResponse,
  PlanCleanupRequest,
  PlanCleanupResponse,
  PlanDeliveryOption,
  PlanResponse,
  PlatformName,
  SettingsConfig,
  SettingsUpdate,
} from '@/types/api';

const PLATFORM_LABELS: Record<PlatformName, string> = {
  garmin: 'Garmin',
  strava: 'Strava',
  stryd: 'Stryd',
  oura: 'Oura',
  coros: 'COROS',
};

type ConfirmMode = 'adopt' | 'resume' | null;
type LeaveChoice = 'keep' | 'remove';

interface ManagedPlanSettingsCardProps {
  config: SettingsConfig;
  planDeliveryOptions: PlanDeliveryOption[];
  updateSettings: (update: SettingsUpdate) => Promise<void>;
}

function formatDate(value: string, locale: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString(
    locale === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
}

function formatWorkoutType(value: string): string {
  return value
    .split(/[\s_]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function browserTimeZone(): string | null {
  try {
    const value = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return value?.trim() || null;
  } catch {
    return null;
  }
}

export default function ManagedPlanSettingsCard({
  config,
  planDeliveryOptions,
  updateSettings,
}: ManagedPlanSettingsCardProps) {
  const { t } = useLingui();
  const { locale } = useLocale();
  const planUrl = managedPlanPreviewUrl();
  const {
    data: plan,
    loading: planLoading,
    error: planError,
    refetch: refetchPlan,
  } = useApi<PlanResponse>(planUrl);
  const {
    data: adjustmentHistory,
    error: adjustmentHistoryError,
    refetch: refetchAdjustmentHistory,
  } = useApi<PlanAdjustmentHistoryResponse>(
    '/api/plan/adjustments?limit=20',
    { enabled: plan?.adjustments !== undefined },
  );
  const management = config.plan_management;
  const state = managedPlanState(management);
  const configuredTarget = management.execution_target;
  const [targetChoice, setTargetChoice] = useState<PlatformName | null>(null);
  const primaryActivitySource = config.preferences.activities ?? null;
  const selectedTarget = planTargetSelection(
    state,
    planDeliveryOptions,
    targetChoice,
    primaryActivitySource,
    configuredTarget,
  );
  const [confirmMode, setConfirmMode] = useState<ConfirmMode>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [leaveChoice, setLeaveChoice] = useState<LeaveChoice>('keep');
  const [action, setAction] = useState<
    'adopt' | 'pause' | 'resume' | 'target' | 'leave' | 'cleanup' | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [cleanupResult, setCleanupResult] =
    useState<PlanCleanupResponse | null>(null);
  const [targetSwitchOpen, setTargetSwitchOpen] = useState(false);
  const [targetSwitchResult, setTargetSwitchResult] =
    useState<PlanCleanupResponse | null>(null);
  const [targetSwitchError, setTargetSwitchError] =
    useState<string | null>(null);
  const [savedTarget, setSavedTarget] = useState<PlatformName | null>(null);
  const [adjustmentConsentOpen, setAdjustmentConsentOpen] = useState(false);
  const [adjustmentAction, setAdjustmentAction] =
    useState<'enable' | 'disable' | null>(null);
  const [undoingAdjustment, setUndoingAdjustment] = useState<string | null>(null);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);

  const praxysWorkouts = plan?.workouts.filter(isPraxysOwned) ?? [];
  const externalWorkouts = plan?.workouts.filter(
    (workout) => !isPraxysOwned(workout),
  ) ?? [];
  const previewWorkouts = praxysWorkouts.slice(0, 4);
  const adjustments = adjustmentHistory?.items ?? plan?.adjustments ?? [];
  const adjustmentSupported = plan?.adjustments !== undefined;
  const adjustmentEnabled =
    management.adjustment_policy === 'auto_conservative';
  const configuredTargetOption = configuredTarget == null
    ? null
    : planDeliveryOptions.find(
      (option) => option.platform === configuredTarget,
    ) ?? null;
  const configuredTargetAvailable =
    configuredTargetOption?.selectable === true;
  const selectedTargetAvailable = selectedTarget != null
    && planDeliveryOptions.some(
      (option) => (
        option.platform === selectedTarget && option.selectable
      ),
    );
  const targetAvailable = state === 'external'
    ? selectedTargetAvailable
    : configuredTargetAvailable;
  const targetChanged = state === 'paused'
    && selectedTarget != null
    && selectedTarget !== configuredTarget;
  const displayTarget = state === 'external'
    ? selectedTarget
    : configuredTarget;
  const targetLabel = displayTarget
    ? PLATFORM_LABELS[displayTarget] ?? displayTarget
    : t`No target selected`;
  const cleanupTargetLabel = cleanupResult?.target
    ? PLATFORM_LABELS[cleanupResult.target] ?? cleanupResult.target
    : targetLabel;
  const selectedTargetLabel = selectedTarget
    ? PLATFORM_LABELS[selectedTarget] ?? selectedTarget
    : t`No target selected`;
  const targetSwitchCleanupLabel = targetSwitchResult?.target
    ? PLATFORM_LABELS[targetSwitchResult.target]
      ?? targetSwitchResult.target
    : targetLabel;
  const confirmationTarget = confirmMode === 'resume'
    ? configuredTarget
    : selectedTarget;
  const deliveryOptionReason = (option: PlanDeliveryOption): string => (
    option.reason === 'account_not_eligible'
      ? t`Workout delivery is not available for this account.`
      : t`Workout delivery is not supported.`
  );

  const resetLeaveDialog = (open: boolean) => {
    setLeaveOpen(open);
    if (!open) {
      setLeaveChoice('keep');
      setActionError(null);
      setCleanupResult(null);
    }
  };

  const openCleanupRecovery = () => {
    setLeaveChoice('remove');
    setCleanupResult(null);
    setActionError(null);
    setLeaveOpen(true);
  };

  const confirmManagedMode = async () => {
    const actionTarget = confirmMode === 'resume'
      ? configuredTarget
      : selectedTarget;
    if (!actionTarget) return;
    const expectedWindow = managedPlanWindow();
    if (
      plan == null
      || plan.window.start !== expectedWindow.start
      || plan.window.end !== expectedWindow.end
    ) {
      setActionError(t`The managed window changed. Review the refreshed preview before enabling delivery.`);
      return;
    }
    const nextAction = confirmMode === 'resume' ? 'resume' : 'adopt';
    const athleteTimezone = browserTimeZone();
    setAction(nextAction);
    setActionError(null);
    try {
      await updateSettings({
        managed_plan_preview_start: expectedWindow.start,
        ...(athleteTimezone
          ? { source_options: { athlete_timezone: athleteTimezone } }
          : {}),
        plan_management: {
          mode: 'praxys',
          execution_target: actionTarget,
          delivery_enabled: true,
          ...(confirmMode === 'adopt'
            ? { adjustment_policy: 'suggest_only' as const }
            : {}),
        },
      });
      await refetchPlan();
      setConfirmMode(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : t`Could not enable managed delivery`);
    } finally {
      setAction(null);
    }
  };

  const pauseDelivery = async () => {
    setAction('pause');
    setActionError(null);
    try {
      await updateSettings({
        plan_management: { delivery_enabled: false },
      });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : t`Could not pause delivery`);
    } finally {
      setAction(null);
    }
  };

  const cleanupFutureDeliveries = async (
    intent: 'leave_managed_mode' | 'switch_execution_target' =
      'leave_managed_mode',
  ): Promise<PlanCleanupResponse> => {
    const cleanupRequest: PlanCleanupRequest = { scope: 'future', intent };
    const response = await apiFetch('/api/plan/deliveries/cleanup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cleanupRequest),
    });
    if (!response.ok) {
      throw new Error(
        await extractErrorMessage(response, t`Could not remove future delivered workouts`),
      );
    }
    return response.json() as Promise<PlanCleanupResponse>;
  };

  const needsTargetCleanup = (error: unknown): boolean => (
    error instanceof Error
    && error.message.includes('Remove future Praxys deliveries from')
  );

  const savePausedTarget = async () => {
    if (!targetChanged || !selectedTargetAvailable || !selectedTarget) return;
    setAction('target');
    setActionError(null);
    setSavedTarget(null);
    try {
      await updateSettings({
        plan_management: {
          execution_target: selectedTarget,
          delivery_enabled: false,
        },
      });
      setTargetChoice(null);
      setSavedTarget(selectedTarget);
      await refetchPlan();
    } catch (error) {
      if (needsTargetCleanup(error)) {
        setTargetSwitchResult(null);
        setTargetSwitchError(null);
        setTargetSwitchOpen(true);
      } else {
        setActionError(
          error instanceof Error
            ? error.message
            : t`Could not change the execution target`,
        );
      }
    } finally {
      setAction(null);
    }
  };

  const cleanupAndSwitchTarget = async () => {
    if (!targetChanged || !selectedTargetAvailable || !selectedTarget) return;
    const nextTarget = selectedTarget;
    setAction('cleanup');
    setTargetSwitchError(null);
    try {
      const result = await cleanupFutureDeliveries(
        'switch_execution_target',
      );
      setTargetSwitchResult(result);
      await refetchPlan();
      if (result.status === 'partial') return;
      await updateSettings({
        plan_management: {
          execution_target: nextTarget,
          delivery_enabled: false,
        },
      });
      setTargetChoice(null);
      setSavedTarget(nextTarget);
      setTargetSwitchOpen(false);
      setTargetSwitchResult(null);
      await refetchPlan();
    } catch (error) {
      setTargetSwitchError(
        error instanceof Error
          ? error.message
          : t`Could not change the execution target`,
      );
    } finally {
      setAction(null);
    }
  };

  const leaveManagedMode = async () => {
    setAction('leave');
    setActionError(null);
    setCleanupResult(null);
    try {
      await updateSettings({
        plan_management: {
          mode: 'external',
          delivery_enabled: false,
        },
      });
      if (leaveChoice === 'remove') {
        setAction('cleanup');
        const result = await cleanupFutureDeliveries();
        setCleanupResult(result);
        await refetchPlan();
        if (result.status === 'partial') {
          return;
        }
      }
      resetLeaveDialog(false);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : t`Could not leave managed mode`);
    } finally {
      setAction(null);
    }
  };

  const retryCleanup = async () => {
    setAction('cleanup');
    setActionError(null);
    try {
      const result = await cleanupFutureDeliveries();
      setCleanupResult(result);
      await refetchPlan();
      if (result.status === 'complete') {
        resetLeaveDialog(false);
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : t`Could not remove future delivered workouts`);
    } finally {
      setAction(null);
    }
  };

  const saveAdjustmentPolicy = async (
    policy: 'suggest_only' | 'auto_conservative',
  ) => {
    if (!adjustmentSupported) return;
    const athleteTimezone = (
      policy === 'auto_conservative' ? browserTimeZone() : null
    );
    if (policy === 'auto_conservative' && !athleteTimezone) {
      setAdjustmentError(t`Praxys could not determine your time zone. Check your device settings and try again.`);
      return;
    }
    const nextAction = policy === 'auto_conservative' ? 'enable' : 'disable';
    setAdjustmentAction(nextAction);
    setAdjustmentError(null);
    try {
      await updateSettings({
        ...(athleteTimezone
          ? { source_options: { athlete_timezone: athleteTimezone } }
          : {}),
        plan_management: { adjustment_policy: policy },
      });
      await Promise.all([
        refetchPlan(),
        ...(adjustmentSupported ? [refetchAdjustmentHistory()] : []),
      ]);
      if (policy === 'auto_conservative') setAdjustmentConsentOpen(false);
    } catch (error) {
      setAdjustmentError(
        error instanceof Error
          ? error.message
          : t`Could not update automatic plan changes`,
      );
    } finally {
      setAdjustmentAction(null);
    }
  };

  const undoAdjustment = async (revisionId: string) => {
    if (!adjustmentSupported) return;
    setUndoingAdjustment(revisionId);
    setAdjustmentError(null);
    try {
      const response = await apiFetch(
        `/api/plan/adjustments/${encodeURIComponent(revisionId)}/undo`,
        { method: 'POST' },
      );
      if (!response.ok) {
        const message = await extractErrorMessage(
          response,
          t`Could not restore the previous workout`,
        );
        if (response.status === 409) {
          await Promise.all([
            refetchPlan(),
            refetchAdjustmentHistory(),
          ]);
        }
        throw new Error(message);
      }
      await Promise.all([
        refetchPlan(),
        ...(adjustmentSupported ? [refetchAdjustmentHistory()] : []),
      ]);
    } catch (error) {
      setAdjustmentError(
        error instanceof Error
          ? error.message
          : t`Could not restore the previous workout`,
      );
    } finally {
      setUndoingAdjustment(null);
    }
  };

  const stateBadge = state === 'active'
    ? (
      <Badge className="bg-primary/12 text-primary hover:bg-primary/12">
        <Trans>Active</Trans>
      </Badge>
    )
    : state === 'paused'
      ? (
        <Badge className="bg-accent-amber/12 text-accent-amber hover:bg-accent-amber/12">
          <Trans>Paused</Trans>
        </Badge>
      )
      : <Badge variant="secondary"><Trans>External</Trans></Badge>;
  const leaveOptionsDisabled = action != null || cleanupResult != null;

  return (
    <>
      <Card className="mb-8">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <CalendarSync className="h-4 w-4" aria-hidden="true" />
              </div>
              <div>
                <CardTitle className="text-sm font-semibold text-foreground">
                  <Trans>Plan management</Trans>
                </CardTitle>
                <CardDescription className="text-xs">
                  <Trans>Choose who controls the plan and where Praxys delivers it</Trans>
                </CardDescription>
              </div>
            </div>
            {stateBadge}
          </div>
        </CardHeader>

        <CardContent className="space-y-5">
          <div>
            <p className="text-sm font-medium text-foreground">
              {state === 'active' && <Trans>Praxys is your active planner.</Trans>}
              {state === 'paused' && <Trans>Praxys owns the plan; delivery is paused.</Trans>}
              {state === 'external' && <Trans>Your external planner remains in control.</Trans>}
            </p>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted-foreground">
              {state === 'active' && (
                <Trans>
                  Praxys automatically keeps its workouts in the next 14 days aligned with {targetLabel}.
                </Trans>
              )}
              {state === 'paused' && (
                <Trans>
                  The canonical Praxys plan is preserved. Existing target workouts stay in place until you resume or leave.
                </Trans>
              )}
              {state === 'external' && (
                <Trans>
                  Praxys can analyze this schedule, but it will not create, replace, or remove target workouts.
                </Trans>
              )}
            </p>
          </div>

          <Alert className="border-accent-cobalt/25 bg-accent-cobalt/5 text-foreground">
            <ShieldCheck className="text-accent-cobalt" aria-hidden="true" />
            <AlertDescription className="text-xs leading-relaxed text-foreground">
              <Trans>
                Praxys only changes workouts it created or you explicitly adopt. Manual workouts and workouts from another coach stay untouched. To avoid overlapping sessions, use one planner at a time.
              </Trans>
            </AlertDescription>
          </Alert>

          <div className="border-y border-border py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-foreground">
                  <Trans>14-day managed window</Trans>
                </p>
                {plan ? (
                  <p className="mt-1 font-data text-[11px] text-muted-foreground">
                    {formatDate(plan.window.start, locale)}
                    {' \u2013 '}
                    {formatDate(plan.window.end, locale)}
                  </p>
                ) : (
                  <Skeleton className="mt-2 h-3 w-28" />
                )}
              </div>
              {plan && (
                <div className="text-right text-xs text-muted-foreground">
                  <p>
                    <span className="font-data font-semibold text-foreground">
                      {praxysWorkouts.length}
                    </span>{' '}
                    <Plural
                      value={praxysWorkouts.length}
                      one="Praxys workout"
                      other="Praxys workouts"
                    />
                  </p>
                  {externalWorkouts.length > 0 && (
                    <p className="mt-1">
                      <Trans>
                        <span className="font-data">{externalWorkouts.length}</span> external left untouched
                      </Trans>
                    </p>
                  )}
                </div>
              )}
            </div>

            {planLoading && (
              <div className="mt-4 space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            )}

            {planError && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-destructive">
                  <Trans>Could not load the managed-window preview.</Trans>
                </p>
                <Button variant="outline" size="sm" onClick={() => refetchPlan()}>
                  <Trans>Retry</Trans>
                </Button>
              </div>
            )}

            {plan && previewWorkouts.length > 0 && (
              <div className="mt-4 divide-y divide-border">
                {previewWorkouts.map((workout) => (
                  <div
                    key={workout.canonical_id ?? `${workout.date}-${workout.workout_type}`}
                    className="flex items-center justify-between gap-4 py-2 text-xs"
                  >
                    <span className="font-data text-muted-foreground">
                      {formatDate(workout.date, locale)}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-medium text-foreground">
                      {formatWorkoutType(workout.workout_type)}
                    </span>
                    {workout.duration_min != null && (
                      <span className="font-data text-muted-foreground">
                        {Math.round(workout.duration_min)} <Trans>min</Trans>
                      </span>
                    )}
                  </div>
                ))}
                {praxysWorkouts.length > previewWorkouts.length && (
                  <p className="pt-2 text-[11px] text-muted-foreground">
                    <Trans>
                      And <span className="font-data">{praxysWorkouts.length - previewWorkouts.length}</span> more in this window
                    </Trans>
                  </p>
                )}
              </div>
            )}

            {plan && praxysWorkouts.length === 0 && (
              <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                <Trans>
                  No Praxys workouts are scheduled in this window. Future Praxys-created workouts will enter the rolling window automatically.
                </Trans>
              </p>
            )}
          </div>

          <div className="space-y-4">
            {state !== 'active' ? (
              <fieldset
                className="w-full max-w-2xl"
                disabled={action != null}
              >
                <legend className="mb-1.5 text-xs font-medium text-foreground">
                  <Trans>Execution target</Trans>
                </legend>
                {planDeliveryOptions.length > 0 ? (
                  <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
                    {planDeliveryOptions.map((option) => {
                      const selected = selectedTarget === option.platform;
                      return (
                        <label
                          key={option.platform}
                          className={cn(
                            'block',
                            option.selectable
                              ? 'cursor-pointer'
                              : 'cursor-not-allowed',
                          )}
                        >
                          <input
                            type="radio"
                            className="peer sr-only"
                            name="plan-delivery-target"
                            value={option.platform}
                            checked={selected}
                            disabled={!option.selectable}
                            onChange={() => {
                              setTargetChoice(option.platform);
                              setActionError(null);
                              setSavedTarget(null);
                            }}
                          />
                          <span
                            className={cn(
                              'flex min-h-11 items-center justify-between gap-3 px-3 py-2 text-left transition-colors peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-inset peer-focus-visible:ring-primary',
                              selected && 'bg-primary/8',
                              option.selectable
                                ? 'hover:bg-muted/50'
                                : 'bg-muted/25 text-muted-foreground',
                            )}
                          >
                            <span className="min-w-0">
                              <span className="block text-sm font-medium text-foreground">
                                {PLATFORM_LABELS[option.platform]}
                              </span>
                              {!option.selectable && (
                                <span className="mt-0.5 block text-[11px] leading-relaxed text-muted-foreground">
                                  {deliveryOptionReason(option)}
                                </span>
                              )}
                            </span>
                            {selected && (
                              <Check
                                className="h-4 w-4 shrink-0 text-primary"
                                aria-hidden="true"
                              />
                            )}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-border px-3 py-3 text-xs text-muted-foreground">
                    <Trans>Connect an activity platform above to choose where workouts are delivered.</Trans>
                  </p>
                )}
                <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
                  <p className="max-w-xl text-[11px] leading-relaxed text-muted-foreground">
                    {planDeliveryOptions.length > 0
                      ? state === 'paused'
                        ? (
                          <Trans>
                            Change the target while delivery is paused. The new target takes effect only after you resume.
                          </Trans>
                        )
                        : (
                          <Trans>
                            Selecting a target does not enable delivery. You will confirm the managed window next.
                          </Trans>
                        )
                      : <Trans>Only supported and eligible platforms can receive workouts.</Trans>}
                  </p>
                  {state === 'paused' && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="min-h-11 sm:min-h-0"
                      disabled={
                        !targetChanged
                        || !selectedTargetAvailable
                        || action != null
                      }
                      onClick={() => void savePausedTarget()}
                    >
                      {action === 'target'
                        ? <Trans>Saving target…</Trans>
                        : <Trans>Save target</Trans>}
                    </Button>
                  )}
                </div>
              </fieldset>
            ) : (
              <div>
                <p className="text-xs font-medium text-foreground">
                  <Trans>Execution target</Trans>
                </p>
                <div className="mt-1 flex min-h-11 max-w-2xl items-center justify-between gap-3 border-b border-border py-2">
                  <p className="text-sm font-medium text-foreground">{targetLabel}</p>
                  <p className="text-[11px] text-muted-foreground">
                    <Trans>Pause delivery to change the target.</Trans>
                  </p>
                </div>
              </div>
            )}

            {savedTarget && state === 'paused' && (
              <p
                className="flex items-center gap-2 text-xs text-primary"
                role="status"
              >
                <Check className="h-4 w-4" aria-hidden="true" />
                <Trans>
                  Execution target changed. Delivery remains paused.
                </Trans>
              </p>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
              <div className="flex flex-wrap items-center gap-2">
                {state === 'external' ? (
                  <>
                    <Button
                      className="min-h-11 sm:min-h-0"
                      disabled={
                        !targetAvailable
                        || action != null
                        || plan == null
                      }
                      onClick={() => {
                        setActionError(null);
                        setConfirmMode('adopt');
                      }}
                    >
                      <Trans>Review and activate</Trans>
                    </Button>
                    <Button
                      variant="outline"
                      className="min-h-11 sm:min-h-0"
                      disabled={action != null}
                      onClick={openCleanupRecovery}
                    >
                      <Trans>Remove future Praxys deliveries</Trans>
                    </Button>
                  </>
                ) : state === 'active' ? (
                  <Button
                    variant="outline"
                    className="min-h-11 sm:min-h-0"
                    disabled={action != null}
                    onClick={pauseDelivery}
                  >
                    <CirclePause aria-hidden="true" />
                    {action === 'pause' ? <Trans>Pausing…</Trans> : <Trans>Pause delivery</Trans>}
                  </Button>
                ) : (
                  <Button
                    className="min-h-11 sm:min-h-0"
                    disabled={
                      !targetAvailable
                      || targetChanged
                      || action != null
                      || plan == null
                    }
                    onClick={() => {
                      setActionError(null);
                      setConfirmMode('resume');
                    }}
                  >
                    <Trans>Review and resume</Trans>
                  </Button>
                )}
              </div>
              {state !== 'external' && (
                <Button
                  variant="ghost"
                  className="min-h-11 text-destructive hover:bg-destructive/8 hover:text-destructive sm:min-h-0"
                  disabled={action != null}
                  onClick={() => resetLeaveDialog(true)}
                >
                  <Trans>Leave managed mode</Trans>
                </Button>
              )}
            </div>
          </div>

          {actionError && !confirmMode && !leaveOpen && !targetSwitchOpen && (
            <Alert variant="destructive">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}
          {state !== 'external' && !configuredTargetAvailable && (
            <Alert className="border-accent-amber/30 bg-accent-amber/8">
              <TriangleAlert className="text-accent-amber" aria-hidden="true" />
              <AlertDescription className="text-xs text-foreground">
                {configuredTargetOption ? (
                  deliveryOptionReason(configuredTargetOption)
                ) : (
                  <Trans>
                    Reconnect {targetLabel} above before managed delivery can continue.
                  </Trans>
                )}
              </AlertDescription>
            </Alert>
          )}

          {adjustmentSupported && (
            <div className="border-t border-border pt-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex max-w-2xl items-start gap-3">
                <HeartPulse
                  className="mt-0.5 h-4 w-4 shrink-0 text-primary"
                  aria-hidden="true"
                />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-foreground">
                      <Trans>Automatic recovery guardrail</Trans>
                    </p>
                    <Badge
                      variant="secondary"
                      className={
                        adjustmentEnabled
                          ? 'bg-primary/12 text-primary hover:bg-primary/12'
                          : undefined
                      }
                    >
                      {adjustmentEnabled ? <Trans>On</Trans> : <Trans>Off</Trans>}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {state === 'external' ? (
                      <Trans>
                        Adopt Praxys as your planner before enabling automatic changes. Coaching remains suggestion-only.
                      </Trans>
                    ) : adjustmentEnabled ? (
                      <Trans>
                        After a sync, Praxys may replace today's single Praxys-generated hard workout with rest only when same-day HRV crosses your personal caution band.
                      </Trans>
                    ) : (
                      <Trans>
                        Coaching is suggestion-only. Praxys will not change a workout from recovery signals.
                      </Trans>
                    )}
                  </p>
                </div>
              </div>
              {state !== 'external' && (
                adjustmentEnabled ? (
                  <Button
                    variant="outline"
                    disabled={adjustmentAction != null}
                    onClick={() => void saveAdjustmentPolicy('suggest_only')}
                  >
                    {adjustmentAction === 'disable'
                      ? <Trans>Turning off…</Trans>
                      : <Trans>Turn off</Trans>}
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    disabled={adjustmentAction != null}
                    onClick={() => {
                      setAdjustmentError(null);
                      setAdjustmentConsentOpen(true);
                    }}
                  >
                    <Trans>Review and turn on</Trans>
                  </Button>
                )
              )}
            </div>

            <ScienceNote
              label={<Trans>Why this is conservative</Trans>}
              sources={[
                {
                  label: 'Plews et al. (2012)',
                  url: 'https://doi.org/10.1007/s00421-012-2354-4',
                },
                {
                  label: 'Kiviniemi et al. (2007)',
                  url: 'https://doi.org/10.1007/s00421-007-0552-2',
                },
              ]}
            >
              <p>
                <Trans>
                  This guardrail uses individualized HRV guidance and never loads activity intensity. The exact caution band and rest-day action are conservative product estimates, not diagnoses or clinically validated prescriptions. Prior-day, missing, or inconsistent recovery; a completed activity; multiple Praxys workouts; or an uncertain target calendar keeps the plan unchanged. Load, sleep, and other caution signals remain suggestions.
                </Trans>
              </p>
            </ScienceNote>

            {adjustments.length > 0 && (
              <div className="mt-5 border-t border-border pt-4">
                <p className="text-xs font-semibold text-foreground">
                  <Trans>Recent automatic changes</Trans>
                </p>
                <div className="mt-2 divide-y divide-border">
                  {adjustments.slice(0, 5).map((adjustment) => (
                    <div
                      key={adjustment.id}
                      className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-data text-muted-foreground">
                            {adjustment.workout_date
                              ? formatDate(adjustment.workout_date, locale)
                              : <Trans>Unknown date</Trans>}
                          </span>
                          <span className="font-medium text-foreground">
                            {formatWorkoutType(
                              adjustment.before.workout_type ?? t`Workout`,
                            )}
                            {' \u2192 '}
                            {formatWorkoutType(
                              adjustment.after.workout_type ?? t`Rest`,
                            )}
                          </span>
                          <span className="text-muted-foreground">
                            {adjustment.status === 'active' && <Trans>Applied</Trans>}
                            {adjustment.status === 'undone' && <Trans>Restored</Trans>}
                            {adjustment.status === 'superseded' && <Trans>Changed later</Trans>}
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                          <Trans>Current HRV crossed your personal caution band.</Trans>
                        </p>
                      </div>
                      {adjustment.can_undo && (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={undoingAdjustment != null}
                          onClick={() => void undoAdjustment(adjustment.id)}
                        >
                          <RotateCcw aria-hidden="true" />
                          {undoingAdjustment === adjustment.id
                            ? <Trans>Restoring…</Trans>
                            : <Trans>Restore workout</Trans>}
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

              {adjustmentHistoryError && (
                <Alert variant="destructive" className="mt-4">
                  <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                    <span className="text-xs">
                      <Trans>Could not load automatic change history.</Trans>
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => refetchAdjustmentHistory()}
                    >
                      <Trans>Retry</Trans>
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              {adjustmentError && (
                <Alert variant="destructive" className="mt-4">
                  <AlertDescription>{adjustmentError}</AlertDescription>
                </Alert>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={confirmMode != null}
        onOpenChange={(open) => {
          if (!open && action == null) {
            setConfirmMode(null);
            setActionError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {confirmMode === 'resume'
                ? <Trans>Resume managed delivery?</Trans>
                : <Trans>Let Praxys manage this plan?</Trans>}
            </DialogTitle>
            <DialogDescription>
              <Trans>
                Confirm the boundary before Praxys writes to {targetLabel}.
              </Trans>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 text-sm">
            <div className="flex gap-3">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
              <p>
                <Trans>
                  Praxys becomes canonical for its own and explicitly adopted workouts.
                </Trans>
              </p>
            </div>
            <div className="flex gap-3">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
              <p>
                <Trans>
                  The next {MANAGED_PLAN_WINDOW_DAYS} days roll forward automatically; <span className="font-data">{praxysWorkouts.length}</span> workouts are currently in scope.
                </Trans>
              </p>
            </div>
            <div className="flex gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent-cobalt" aria-hidden="true" />
              <p>
                <Trans>
                  Manual and other-coach workouts remain external and will not be edited or deleted.
                </Trans>
              </p>
            </div>
            <Alert className="border-accent-amber/30 bg-accent-amber/8">
              <TriangleAlert className="text-accent-amber" aria-hidden="true" />
              <AlertDescription className="text-xs text-foreground">
                <Trans>
                  Disable delivery from any other planner first. Two planners can create overlapping sessions.
                </Trans>
              </AlertDescription>
            </Alert>
            {confirmationTarget === 'garmin' && (
              <Alert className="border-accent-amber/30 bg-accent-amber/8">
                <TriangleAlert className="text-accent-amber" aria-hidden="true" />
                <AlertDescription className="text-xs text-foreground">
                  <Trans>
                    Garmin workout delivery is duration-only. Workouts with power, pace, or heart-rate targets will stay blocked rather than lose their intended intensity.
                  </Trans>
                </AlertDescription>
              </Alert>
            )}
            {actionError && (
              <Alert variant="destructive">
                <AlertDescription>{actionError}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              disabled={action != null}
              onClick={() => setConfirmMode(null)}
            >
              <Trans>Cancel</Trans>
            </Button>
            <Button
              disabled={action != null || planLoading || plan == null}
              onClick={confirmManagedMode}
            >
              {action === 'adopt' || action === 'resume'
                ? <Trans>Enabling…</Trans>
                : confirmMode === 'resume'
                  ? <Trans>Resume delivery</Trans>
                  : <Trans>Activate managed plan</Trans>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={targetSwitchOpen}
        onOpenChange={(open) => {
          if (action != null) return;
          setTargetSwitchOpen(open);
          if (!open) {
            setTargetSwitchResult(null);
            setTargetSwitchError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              <Trans>Remove old deliveries before switching?</Trans>
            </DialogTitle>
            <DialogDescription>
              <Trans>
                Praxys found future deliveries on the current target. Remove only Praxys-delivered workouts before switching.
              </Trans>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4 border-b border-border pb-3 font-medium">
              <span>{targetSwitchCleanupLabel}</span>
              <ArrowRight
                className="h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
              <span>{selectedTargetLabel}</span>
            </div>
            <div className="flex gap-3">
              <ShieldCheck
                className="mt-0.5 h-4 w-4 shrink-0 text-accent-cobalt"
                aria-hidden="true"
              />
              <p>
                <Trans>
                  Manual and other-coach workouts stay untouched. Delivery remains paused throughout.
                </Trans>
              </p>
            </div>

            {targetSwitchResult?.status === 'partial' && (
              <Alert className="border-accent-amber/30 bg-accent-amber/8">
                <TriangleAlert
                  className="text-accent-amber"
                  aria-hidden="true"
                />
                <AlertDescription className="text-xs text-foreground">
                  <Trans>
                    <span className="font-data">{targetSwitchResult.removed_count}</span> deliveries are clear; <span className="font-data">{targetSwitchResult.remaining_count}</span> still need review before the target can change.
                  </Trans>
                </AlertDescription>
              </Alert>
            )}

            {targetSwitchError && (
              <Alert variant="destructive">
                <AlertDescription>{targetSwitchError}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              disabled={action != null}
              onClick={() => setTargetSwitchOpen(false)}
            >
              {targetSwitchResult?.status === 'partial'
                ? <Trans>Done</Trans>
                : <Trans>Cancel</Trans>}
            </Button>
            <Button
              variant="destructive"
              disabled={action != null}
              onClick={() => void cleanupAndSwitchTarget()}
            >
              {action === 'cleanup'
                ? <Trans>Removing…</Trans>
                : targetSwitchResult?.status === 'partial'
                  ? <Trans>Retry cleanup</Trans>
                  : <Trans>Remove and switch</Trans>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={adjustmentConsentOpen}
        onOpenChange={(open) => {
          if (adjustmentAction == null) {
            setAdjustmentConsentOpen(open);
            if (!open) setAdjustmentError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle><Trans>Turn on conservative plan changes?</Trans></DialogTitle>
            <DialogDescription>
              <Trans>
                This permission is separate from managed delivery. Review the exact boundary before opting in.
              </Trans>
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 text-sm">
            <div className="flex gap-3">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
              <p>
                <Trans>
                  Only today's single Praxys-generated hard workout can become rest, and only for same-day individualized HRV below the caution band.
                </Trans>
              </p>
            </div>
            <div className="flex gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-accent-cobalt" aria-hidden="true" />
              <p>
                <Trans>
                  External, manual, and other-coach workouts are never changed. Uncertain or stale evidence makes no change.
                </Trans>
              </p>
            </div>
            <div className="flex gap-3">
              <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
              <p>
                <Trans>
                  Every change is recorded here and can be restored while that exact workout version is still current.
                </Trans>
              </p>
            </div>
            {adjustmentError && (
              <Alert variant="destructive">
                <AlertDescription>{adjustmentError}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              disabled={adjustmentAction != null}
              onClick={() => setAdjustmentConsentOpen(false)}
            >
              <Trans>Keep suggestion-only</Trans>
            </Button>
            <Button
              disabled={adjustmentAction != null}
              onClick={() => void saveAdjustmentPolicy('auto_conservative')}
            >
              {adjustmentAction === 'enable'
                ? <Trans>Turning on…</Trans>
                : <Trans>Turn on guardrail</Trans>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={leaveOpen}
        onOpenChange={(open) => {
          if (!open && action != null) return;
          resetLeaveDialog(open);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {state === 'external'
                ? <Trans>Remove future Praxys deliveries</Trans>
                : <Trans>Leave managed mode?</Trans>}
            </DialogTitle>
            <DialogDescription>
              {state === 'external'
                ? (
                  <Trans>
                    Only workouts recorded in Praxys's delivery ledger are removed. Manual and other-coach workouts stay untouched.
                  </Trans>
                )
                : (
                  <Trans>
                    Praxys will stop changing the target calendar. Your canonical Praxys plan remains available for analysis.
                  </Trans>
                )}
            </DialogDescription>
          </DialogHeader>

          {state !== 'external' && (
            <fieldset
              disabled={leaveOptionsDisabled}
              className="space-y-2"
            >
            <legend className="sr-only">
              {t`Future delivered workouts`}
            </legend>
            <label
              className={`block w-full rounded-lg border p-3 text-left transition-colors focus-within:outline-none focus-within:ring-2 focus-within:ring-ring ${
                leaveChoice === 'keep'
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:bg-muted/50'
              } ${leaveOptionsDisabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
            >
              <input
                type="radio"
                name="leave-delivered-workouts"
                value="keep"
                checked={leaveChoice === 'keep'}
                onChange={() => setLeaveChoice('keep')}
                className="sr-only"
              />
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-foreground">
                  <Trans>Keep future workouts on {targetLabel}</Trans>
                </span>
                {leaveChoice === 'keep' && (
                  <Check className="h-4 w-4 text-primary" aria-hidden="true" />
                )}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                <Trans>
                  Recommended. Delivered workouts stay on the calendar; Praxys simply stops managing them.
                </Trans>
              </span>
            </label>

            <label
              className={`block w-full rounded-lg border p-3 text-left transition-colors focus-within:outline-none focus-within:ring-2 focus-within:ring-ring ${
                leaveChoice === 'remove'
                  ? 'border-destructive bg-destructive/5'
                  : 'border-border hover:bg-muted/50'
              } ${leaveOptionsDisabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
            >
              <input
                type="radio"
                name="leave-delivered-workouts"
                value="remove"
                checked={leaveChoice === 'remove'}
                onChange={() => setLeaveChoice('remove')}
                className="sr-only"
              />
              <span className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-foreground">
                  <Trans>Remove future Praxys deliveries</Trans>
                </span>
                {leaveChoice === 'remove' && (
                  <Check className="h-4 w-4 text-destructive" aria-hidden="true" />
                )}
              </span>
              <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                <Trans>
                  Only workouts recorded in Praxys's delivery ledger are removed. Manual and other-coach workouts stay untouched.
                </Trans>
              </span>
            </label>
            </fieldset>
          )}

          {cleanupResult?.status === 'partial' && (
            <Alert className="border-accent-amber/30 bg-accent-amber/8">
              <TriangleAlert className="text-accent-amber" aria-hidden="true" />
              <AlertDescription className="text-xs text-foreground">
                <Trans>
                  Managed mode is off. <span className="font-data">{cleanupResult.removed_count}</span> deliveries are clear; <span className="font-data">{cleanupResult.remaining_count}</span> still need review for {cleanupTargetLabel}.
                </Trans>
              </AlertDescription>
            </Alert>
          )}

          {actionError && (
            <Alert variant="destructive">
              <AlertDescription>
                {state === 'external'
                  ? <Trans>Managed mode is off, but cleanup did not finish. {actionError}</Trans>
                  : actionError}
              </AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            {cleanupResult?.status === 'partial' ? (
              <>
                <Button variant="outline" disabled={action != null} onClick={() => resetLeaveDialog(false)}>
                  <Trans>Done</Trans>
                </Button>
                <Button variant="destructive" disabled={action != null} onClick={retryCleanup}>
                  {action === 'cleanup' ? <Trans>Removing…</Trans> : <Trans>Retry cleanup</Trans>}
                </Button>
              </>
            ) : state === 'external' ? (
              <>
                <Button
                  variant="outline"
                  disabled={action != null}
                  onClick={() => resetLeaveDialog(false)}
                >
                  <Trans>Cancel</Trans>
                </Button>
                <Button
                  variant="destructive"
                  disabled={action != null}
                  onClick={retryCleanup}
                >
                  {action === 'cleanup'
                    ? <Trans>Removing…</Trans>
                    : <Trans>Retry cleanup</Trans>}
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  disabled={action != null}
                  onClick={() => resetLeaveDialog(false)}
                >
                  <Trans>Cancel</Trans>
                </Button>
                <Button
                  variant={leaveChoice === 'remove' ? 'destructive' : 'default'}
                  disabled={action != null}
                  onClick={leaveManagedMode}
                >
                  {action === 'leave' || action === 'cleanup'
                    ? <Trans>Leaving…</Trans>
                    : <Trans>Leave managed mode</Trans>}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
