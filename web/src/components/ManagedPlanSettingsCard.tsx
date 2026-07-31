import { useMemo, useState } from 'react';
import { Plural, Trans, useLingui } from '@lingui/react/macro';
import {
  CalendarSync,
  Check,
  CirclePause,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { apiFetch, extractErrorMessage, useApi } from '@/hooks/useApi';
import { useLocale } from '@/contexts/LocaleContext';
import {
  MANAGED_PLAN_WINDOW_DAYS,
  isPraxysOwned,
  managedPlanState,
  planWindowUrl,
} from '@/lib/plan';
import type {
  PlanCleanupResponse,
  PlanResponse,
  PlatformName,
  SettingsConfig,
  SettingsResponse,
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
  platformCapabilities: SettingsResponse['platform_capabilities'];
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

export default function ManagedPlanSettingsCard({
  config,
  platformCapabilities,
  updateSettings,
}: ManagedPlanSettingsCardProps) {
  const { t } = useLingui();
  const { locale } = useLocale();
  const planUrl = useMemo(() => planWindowUrl(), []);
  const {
    data: plan,
    loading: planLoading,
    error: planError,
    refetch: refetchPlan,
  } = useApi<PlanResponse>(planUrl);
  const management = config.plan_management;
  const state = managedPlanState(management);
  const connectedTargets = config.connections.filter(
    (target) => platformCapabilities[target]?.plan === true,
  );
  const configuredTarget = management.execution_target;
  const [targetChoice, setTargetChoice] = useState<PlatformName | null>(null);
  const selectedTarget = (
    targetChoice && connectedTargets.includes(targetChoice)
  )
    ? targetChoice
    : (
      configuredTarget && connectedTargets.includes(configuredTarget)
        ? configuredTarget
        : connectedTargets[0] ?? null
    );
  const [confirmMode, setConfirmMode] = useState<ConfirmMode>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [leaveChoice, setLeaveChoice] = useState<LeaveChoice>('keep');
  const [action, setAction] = useState<
    'adopt' | 'pause' | 'resume' | 'leave' | 'cleanup' | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [cleanupResult, setCleanupResult] =
    useState<PlanCleanupResponse | null>(null);

  const praxysWorkouts = plan?.workouts.filter(isPraxysOwned) ?? [];
  const externalWorkouts = plan?.workouts.filter(
    (workout) => !isPraxysOwned(workout),
  ) ?? [];
  const previewWorkouts = praxysWorkouts.slice(0, 4);
  const configuredTargetAvailable = configuredTarget != null
    && connectedTargets.includes(configuredTarget);
  const targetAvailable = state === 'external'
    ? selectedTarget != null && connectedTargets.includes(selectedTarget)
    : configuredTargetAvailable;
  const displayTarget = state === 'external'
    ? selectedTarget
    : configuredTarget;
  const targetLabel = displayTarget
    ? PLATFORM_LABELS[displayTarget] ?? displayTarget
    : t`No target selected`;

  const resetLeaveDialog = (open: boolean) => {
    setLeaveOpen(open);
    if (!open) {
      setLeaveChoice('keep');
      setActionError(null);
      setCleanupResult(null);
    }
  };

  const confirmManagedMode = async () => {
    const actionTarget = confirmMode === 'resume'
      ? configuredTarget
      : selectedTarget;
    if (!actionTarget) return;
    const nextAction = confirmMode === 'resume' ? 'resume' : 'adopt';
    setAction(nextAction);
    setActionError(null);
    try {
      await updateSettings({
        plan_management: {
          mode: 'praxys',
          execution_target: actionTarget,
          delivery_enabled: true,
          adjustment_policy: 'suggest_only',
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

  const cleanupFutureDeliveries = async (): Promise<PlanCleanupResponse> => {
    const response = await apiFetch('/api/plan/deliveries/cleanup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: 'future' }),
    });
    if (!response.ok) {
      throw new Error(
        await extractErrorMessage(response, t`Could not remove future delivered workouts`),
      );
    }
    return response.json() as Promise<PlanCleanupResponse>;
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

          {state === 'external' ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="w-full sm:max-w-xs">
                <Label className="mb-1.5 block text-xs font-medium text-foreground">
                  <Trans>Execution target</Trans>
                </Label>
                <Select
                  value={selectedTarget ?? ''}
                  onValueChange={(value) => setTargetChoice(value as PlatformName)}
                  disabled={connectedTargets.length === 0 || action != null}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t`Connect a supported platform first`} />
                  </SelectTrigger>
                  <SelectContent>
                    {connectedTargets.map((target) => (
                      <SelectItem key={target} value={target}>
                        {PLATFORM_LABELS[target] ?? target}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
                  {connectedTargets.length > 0
                    ? <Trans>Selecting a target does not enable delivery. You will confirm the managed window next.</Trans>
                    : <Trans>Connect a supported execution platform above before adopting managed delivery.</Trans>}
                </p>
              </div>
              <Button
                disabled={!targetAvailable || action != null || plan == null}
                onClick={() => {
                  setActionError(null);
                  setConfirmMode('adopt');
                }}
              >
                <Trans>Review and activate</Trans>
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs text-muted-foreground"><Trans>Execution target</Trans></p>
                <p className="mt-0.5 text-sm font-medium text-foreground">{targetLabel}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {state === 'active' ? (
                  <Button
                    variant="outline"
                    disabled={action != null}
                    onClick={pauseDelivery}
                  >
                    <CirclePause aria-hidden="true" />
                    {action === 'pause' ? <Trans>Pausing…</Trans> : <Trans>Pause delivery</Trans>}
                  </Button>
                ) : (
                  <Button
                    disabled={!targetAvailable || action != null || plan == null}
                    onClick={() => {
                      setActionError(null);
                      setConfirmMode('resume');
                    }}
                  >
                    <Trans>Review and resume</Trans>
                  </Button>
                )}
                <Button
                  variant="ghost"
                  disabled={action != null}
                  onClick={() => resetLeaveDialog(true)}
                >
                  <Trans>Leave managed mode</Trans>
                </Button>
              </div>
            </div>
          )}

          {actionError && !confirmMode && !leaveOpen && (
            <Alert variant="destructive">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}
          {state !== 'external' && !configuredTargetAvailable && (
            <Alert className="border-accent-amber/30 bg-accent-amber/8">
              <TriangleAlert className="text-accent-amber" aria-hidden="true" />
              <AlertDescription className="text-xs text-foreground">
                <Trans>
                  Reconnect {targetLabel} above before managed delivery can continue.
                </Trans>
              </AlertDescription>
            </Alert>
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
            <Button disabled={action != null} onClick={confirmManagedMode}>
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
        open={leaveOpen}
        onOpenChange={(open) => {
          if (!open && action != null) return;
          resetLeaveDialog(open);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle><Trans>Leave managed mode?</Trans></DialogTitle>
            <DialogDescription>
              <Trans>
                Praxys will stop changing the target calendar. Your canonical Praxys plan remains available for analysis.
              </Trans>
            </DialogDescription>
          </DialogHeader>

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

          {cleanupResult?.status === 'partial' && (
            <Alert className="border-accent-amber/30 bg-accent-amber/8">
              <TriangleAlert className="text-accent-amber" aria-hidden="true" />
              <AlertDescription className="text-xs text-foreground">
                <Trans>
                  Managed mode is off. <span className="font-data">{cleanupResult.removed_count}</span> workouts were removed, but <span className="font-data">{cleanupResult.remaining_count}</span> could not be removed and remain on {targetLabel}.
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
