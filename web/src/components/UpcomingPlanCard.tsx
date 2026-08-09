import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Link } from 'react-router-dom';
import { Plural, Trans, useLingui } from '@lingui/react/macro';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CloudUpload,
  LoaderCircle,
  Pause,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import WorkoutPlanEditor from '@/components/WorkoutPlanEditor';
import { useSettings } from '@/contexts/SettingsContext';
import { useLocale } from '@/contexts/LocaleContext';
import {
  apiFetch,
  extractErrorMessage,
  useApi,
} from '@/hooks/useApi';
import {
  athletePlanWindow,
  athletePlanDateDistance,
  isPraxysOwned,
  isRestWorkoutType,
  managedPlanState,
  planWindowUrl,
  shiftAthletePlanDate,
  type ManagedPlanState,
} from '@/lib/plan';
import { personalContextEvidenceIds } from '@/lib/personal-context';
import type {
  PlanReconciliation,
  PlanMutationErrorCode,
  PlanResolutionAction,
  PlanResolutionResponse,
  PlanResponse,
  PlanWorkoutDeleteResponse,
  PlanWorkoutMutationResponse,
  PlanWorkoutUpdateRequest,
  PlanWorkoutWriteFields,
  PlannedWorkout,
  StrydPushResult,
} from '@/types/api';

const WINDOW_OPTIONS = [
  { id: '1wk', days: 7 },
  { id: '2wk', days: 14 },
  { id: '4wk', days: 28 },
] as const;
type WindowId = typeof WINDOW_OPTIONS[number]['id'];
const WINDOW_STORAGE_KEY = 'praxys.plan_window';

const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  easy: { bg: 'bg-primary/15', text: 'text-primary' },
  recovery: { bg: 'bg-primary/15', text: 'text-primary' },
  long: { bg: 'bg-muted', text: 'text-foreground' },
  tempo: { bg: 'bg-accent-amber/15', text: 'text-accent-amber' },
  threshold: { bg: 'bg-accent-amber/15', text: 'text-accent-amber' },
  interval: { bg: 'bg-destructive/15', text: 'text-destructive' },
  repetition: { bg: 'bg-destructive/15', text: 'text-destructive' },
};
const DEFAULT_COLOR = { bg: 'bg-muted', text: 'text-muted-foreground' };
const STATUS_BASE =
  'inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-medium';

function planTargetLabel(target: string | null): string | null {
  if (target === 'stryd') return 'Stryd';
  if (target === 'garmin') return 'Garmin';
  return target;
}

function getTypeColor(type: string) {
  const key = type.toLowerCase().replace(/\s+/g, ' ');
  if (TYPE_COLORS[key]) return TYPE_COLORS[key];
  for (const [candidate, color] of Object.entries(TYPE_COLORS)) {
    if (key.includes(candidate)) return color;
  }
  return DEFAULT_COLOR;
}

function formatType(type: string): string {
  return type
    .split(/[\s_]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatDate(
  dateStr: string,
  locale: string,
  startTime?: string | null,
): { day: string; weekday: string; isToday: boolean } {
  const date = startTime
    ? new Date(startTime)
    : new Date(`${dateStr}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const workoutDay = new Date(date);
  workoutDay.setHours(0, 0, 0, 0);
  return {
    day: date.getDate().toString().padStart(2, '0'),
    weekday: date.toLocaleDateString(
      locale === 'zh' ? 'zh-CN' : 'en-US',
      { weekday: 'short' },
    ).toUpperCase(),
    isToday: workoutDay.getTime() === today.getTime(),
  };
}

function formatNoticeDate(dateStr: string, locale: string): string {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(
    locale === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
}

function formatWindowRange(
  start: string,
  end: string,
  locale: string,
): string {
  const formatter = new Intl.DateTimeFormat(
    locale === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
  return `${formatter.format(new Date(`${start}T12:00:00`))} – ${
    formatter.format(new Date(`${end}T12:00:00`))
  }`;
}

function workoutKey(workout: PlannedWorkout): string {
  return workout.canonical_id
    ?? workout.reconciliation?.id
    ?? `${workout.source}-${workout.date}-${workout.workout_type}`;
}

function WindowPills({
  active,
  onChange,
}: {
  active: WindowId;
  onChange: (next: WindowId) => void;
}) {
  const { t } = useLingui();
  const labels: Record<WindowId, string> = {
    '1wk': t`1 wk`,
    '2wk': t`2 wk`,
    '4wk': t`4 wk`,
  };
  return (
    <div
      role="group"
      aria-label={t`Plan window`}
      className="inline-flex items-center gap-1 rounded-full bg-muted/60 p-1"
    >
      {WINDOW_OPTIONS.map((option) => {
        const selected = option.id === active;
        return (
          <Button
            key={option.id}
            type="button"
            aria-pressed={selected}
            variant="ghost"
            size="xs"
            onClick={() => onChange(option.id)}
            className={`rounded-full px-3 ${
              selected
                ? 'bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground'
                : 'text-muted-foreground'
            }`}
          >
            {labels[option.id]}
          </Button>
        );
      })}
    </div>
  );
}

function ManagementStrip({
  state,
  target,
  targetConnected,
}: {
  state: ManagedPlanState;
  target: string | null;
  targetConnected: boolean;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-y border-border py-3">
      <div className="flex min-w-0 items-start gap-2.5">
        {state === 'active' && targetConnected && (
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        )}
        {state === 'active' && !targetConnected && (
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" aria-hidden="true" />
        )}
        {state === 'paused' && (
          <Pause className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" aria-hidden="true" />
        )}
        {state === 'external' && (
          <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
        <div>
          <p className="text-xs font-medium text-foreground">
            {state === 'active' && <Trans>Managed by Praxys</Trans>}
            {state === 'paused' && <Trans>Managed delivery paused</Trans>}
            {state === 'external' && <Trans>External plan mode</Trans>}
          </p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
            {state === 'active' && targetConnected && (
              <Trans>The rolling 14-day window is delivered to {target ?? 'your target'}.</Trans>
            )}
            {state === 'active' && !targetConnected && target && (
              <Trans>Reconnect {target} to continue delivery. The Praxys plan remains canonical.</Trans>
            )}
            {state === 'active' && !targetConnected && !target && (
              <Trans>Select an execution target in Settings to continue delivery.</Trans>
            )}
            {state === 'paused' && (
              <Trans>The Praxys plan is preserved; no target workouts will change.</Trans>
            )}
            {state === 'external' && (
              <Trans>Praxys is read-only and leaves every target workout untouched.</Trans>
            )}
          </p>
        </div>
      </div>
      <Link
        to="/settings"
        className="text-xs font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {state === 'external' ? <Trans>Adopt in Settings</Trans> : <Trans>Manage in Settings</Trans>}
      </Link>
    </div>
  );
}

function StaticStatus({
  tone,
  icon,
  children,
}: {
  tone: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <span className={`${STATUS_BASE} ${tone}`}>
      {icon}
      {children}
    </span>
  );
}

function DeliveryStatus({
  workout,
  managementState,
  target,
  writeAccess,
  working,
  actionsDisabled,
  error,
  onDeliver,
  onReview,
}: {
  workout: PlannedWorkout;
  managementState: ManagedPlanState;
  target: string | null;
  writeAccess: boolean;
  working: boolean;
  actionsDisabled: boolean;
  error?: string;
  onDeliver: () => void;
  onReview: () => void;
}) {
  const { t } = useLingui();
  const reconciliation = workout.reconciliation;
  const isOwned = isPraxysOwned(workout);
  const isRest = isRestWorkoutType(workout.workout_type);
  const canAccept = reconciliation?.resolutions.includes('accept_target');
  const hasConflict = reconciliation?.conflict === true
    || workout.sync_state === 'mismatch';

  if (isRest) return null;
  if (working) {
    return (
      <StaticStatus
        tone="bg-accent-cobalt/10 text-accent-cobalt"
        icon={(
          <LoaderCircle
            className="h-3 w-3 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
        )}
      >
        <Trans>Working…</Trans>
      </StaticStatus>
    );
  }
  if (error) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={actionsDisabled}
        title={error}
        aria-label={t`Retry workout action`}
        onClick={reconciliation ? onReview : onDeliver}
        className={`${STATUS_BASE} bg-destructive/10 text-destructive hover:bg-destructive/15 hover:text-destructive`}
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        <Trans>Retry</Trans>
      </Button>
    );
  }

  if (!isOwned) {
    if (canAccept && writeAccess) {
      return (
        <Button
          type="button"
          variant="ghost"
          size="xs"
          disabled={actionsDisabled}
          onClick={onReview}
          className={`${STATUS_BASE} bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary`}
        >
          <Trans>Use in Praxys</Trans>
        </Button>
      );
    }
    return (
      <StaticStatus tone="bg-muted text-muted-foreground">
        <Trans>External</Trans>
      </StaticStatus>
    );
  }

  if (managementState !== 'active' && hasConflict) {
    return (
      <StaticStatus
        tone="bg-accent-amber/10 text-accent-amber"
        icon={<TriangleAlert className="h-3 w-3" aria-hidden="true" />}
      >
        <Trans>Conflict retained</Trans>
      </StaticStatus>
    );
  }
  if (managementState === 'external') {
    return (
      <StaticStatus tone="bg-muted text-muted-foreground">
        <Trans>Praxys only</Trans>
      </StaticStatus>
    );
  }
  if (managementState === 'paused') {
    return (
      <StaticStatus
        tone="bg-accent-amber/10 text-accent-amber"
        icon={<Pause className="h-3 w-3" aria-hidden="true" />}
      >
        <Trans>Paused</Trans>
      </StaticStatus>
    );
  }

  const state = reconciliation?.state;
  if (state === 'matching' || workout.sync_state === 'synced') {
    return (
      <StaticStatus
        tone="bg-primary/10 text-primary"
        icon={<Check className="h-3 w-3" aria-hidden="true" />}
      >
        <Trans>In sync</Trans>
      </StaticStatus>
    );
  }
  if (state === 'pending_observation') {
    return (
      <StaticStatus
        tone="bg-accent-cobalt/10 text-accent-cobalt"
        icon={<LoaderCircle className="h-3 w-3" aria-hidden="true" />}
      >
        <Trans>Verifying</Trans>
      </StaticStatus>
    );
  }
  if (
    state === 'target_edited'
    || state === 'canonical_changed'
    || state === 'target_deleted'
  ) {
    if (!writeAccess) {
      return (
        <StaticStatus tone="bg-accent-amber/10 text-accent-amber">
          <Trans>Review conflict</Trans>
        </StaticStatus>
      );
    }
    return (
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={actionsDisabled}
        onClick={onReview}
        className={`${STATUS_BASE} bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/15 hover:text-accent-amber`}
      >
        <TriangleAlert className="h-3 w-3" aria-hidden="true" />
        <Trans>Review conflict</Trans>
      </Button>
    );
  }
  if (state === 'delivery_failed') {
    if (!writeAccess) {
      return (
        <StaticStatus tone="bg-destructive/10 text-destructive">
          <Trans>Delivery failed</Trans>
        </StaticStatus>
      );
    }
    return (
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={actionsDisabled}
        onClick={onReview}
        className={`${STATUS_BASE} bg-destructive/10 text-destructive hover:bg-destructive/15 hover:text-destructive`}
      >
        <RefreshCw className="h-3 w-3" aria-hidden="true" />
        <Trans>Retry delivery</Trans>
      </Button>
    );
  }
  if (workout.sync_state === 'mismatch' && reconciliation) {
    if (!writeAccess) {
      return (
        <StaticStatus tone="bg-accent-amber/10 text-accent-amber">
          <Trans>Review conflict</Trans>
        </StaticStatus>
      );
    }
    return (
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={actionsDisabled}
        onClick={onReview}
        className={`${STATUS_BASE} bg-accent-amber/10 text-accent-amber hover:bg-accent-amber/15 hover:text-accent-amber`}
      >
        <TriangleAlert className="h-3 w-3" aria-hidden="true" />
        <Trans>Review conflict</Trans>
      </Button>
    );
  }
  if (workout.sync_state === 'mismatch') {
    return (
      <StaticStatus
        tone="bg-accent-amber/10 text-accent-amber"
        icon={<TriangleAlert className="h-3 w-3" aria-hidden="true" />}
      >
        <Trans>Sync target to review</Trans>
      </StaticStatus>
    );
  }
  if (target === 'stryd') {
    if (!writeAccess) {
      return (
        <StaticStatus tone="bg-accent-cobalt/10 text-accent-cobalt">
          <Trans>Queued</Trans>
        </StaticStatus>
      );
    }
    return (
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={actionsDisabled}
        onClick={onDeliver}
        className={`${STATUS_BASE} bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary`}
      >
        <CloudUpload className="h-3 w-3" aria-hidden="true" />
        <Trans>Deliver now</Trans>
      </Button>
    );
  }
  return (
    <StaticStatus tone="bg-accent-cobalt/10 text-accent-cobalt">
      <Trans>Queued</Trans>
    </StaticStatus>
  );
}

function WorkoutRow({
  workout,
  managementState,
  target,
  writeAccess,
  working,
  actionsDisabled,
  editDisabled,
  error,
  onDeliver,
  onEdit,
  onReview,
}: {
  workout: PlannedWorkout;
  managementState: ManagedPlanState;
  target: string | null;
  writeAccess: boolean;
  working: boolean;
  actionsDisabled: boolean;
  editDisabled: boolean;
  error?: string;
  onDeliver: () => void;
  onEdit?: () => void;
  onReview: () => void;
}) {
  const { t } = useLingui();
  const { locale } = useLocale();
  const { day, weekday, isToday } = formatDate(
    workout.date,
    locale,
    workout.start_time,
  );
  const color = getTypeColor(workout.workout_type);
  const details: string[] = [];
  if (workout.duration_min != null) details.push(`${Math.round(workout.duration_min)}m`);
  if (workout.distance_km != null) details.push(`${workout.distance_km}km`);
  if (workout.power_min != null && workout.power_max != null) {
    details.push(`${workout.power_min}\u2013${workout.power_max}W`);
  } else if (workout.power_min != null) {
    details.push(`\u2265${workout.power_min}W`);
  } else if (workout.power_max != null) {
    details.push(`\u2264${workout.power_max}W`);
  }
  if (workout.hr_min != null && workout.hr_max != null) {
    details.push(`${workout.hr_min}\u2013${workout.hr_max} bpm`);
  } else if (workout.hr_min != null) {
    details.push(`\u2265${workout.hr_min} bpm`);
  } else if (workout.hr_max != null) {
    details.push(`\u2264${workout.hr_max} bpm`);
  }
  if (workout.pace_min && workout.pace_max) {
    details.push(`${workout.pace_min}\u2013${workout.pace_max}/km`);
  } else if (workout.pace_min) {
    details.push(`\u2265${workout.pace_min}/km`);
  } else if (workout.pace_max) {
    details.push(`\u2264${workout.pace_max}/km`);
  }

  return (
    <div
      className={`grid grid-cols-[2.5rem_1px_minmax(0,1fr)] items-center gap-x-3 gap-y-2 rounded-lg px-3 py-2.5 transition-colors sm:grid-cols-[2.5rem_1px_minmax(0,1fr)_auto] ${
        isToday
          ? 'bg-primary/5 ring-1 ring-primary/30'
          : 'hover:bg-muted/50'
      }`}
    >
      <div className="flex flex-col items-center">
        <span className={`text-[10px] font-semibold tracking-wider ${
          isToday ? 'text-primary' : 'text-muted-foreground'
        }`}>
          {isToday ? t`TODAY` : weekday}
        </span>
        <span className={`font-data text-lg leading-tight ${
          isToday ? 'font-bold text-primary' : 'text-muted-foreground'
        }`}>
          {day}
        </span>
      </div>

      <div className={`h-8 w-px ${isToday ? 'bg-primary/30' : 'bg-border'}`} />

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={`inline-flex rounded px-2 py-0.5 text-xs font-semibold ${color.bg} ${color.text}`}>
            {formatType(workout.workout_type)}
          </span>
          {details.length > 0 && (
            <span className="truncate font-data text-xs text-muted-foreground">
              {details.join(' · ')}
            </span>
          )}
        </div>
        {workout.description && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {workout.description}
          </p>
        )}
        {error && (
          <p className="mt-1 text-[11px] leading-relaxed text-destructive" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="col-start-3 flex flex-wrap items-center gap-2 justify-self-start sm:col-start-4 sm:row-start-1 sm:justify-self-end">
        <DeliveryStatus
          workout={workout}
          managementState={managementState}
          target={target}
          writeAccess={writeAccess}
          working={working}
          actionsDisabled={actionsDisabled}
          error={error}
          onDeliver={onDeliver}
          onReview={onReview}
        />
        {onEdit && (
          <Button
            type="button"
            variant="ghost"
            size="xs"
            disabled={editDisabled}
            onClick={onEdit}
            className="rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <Pencil className="h-3 w-3" aria-hidden="true" />
            <Trans>Edit</Trans>
          </Button>
        )}
      </div>
    </div>
  );
}

function ConflictDialog({
  workout,
  open,
  targetConnected,
  actionsDisabled,
  working,
  error,
  onOpenChange,
  onResolve,
}: {
  workout: PlannedWorkout | null;
  open: boolean;
  targetConnected: boolean;
  actionsDisabled: boolean;
  working: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onResolve: (action: PlanResolutionAction) => void;
}) {
  const reconciliation = workout?.reconciliation;
  if (!workout || !reconciliation) return null;
  const target = planTargetLabel(reconciliation.target);
  const canRestore = reconciliation.resolutions.includes('restore_praxys');
  const canAccept = reconciliation.resolutions.includes('accept_target');
  const targetWorkout = reconciliation.target_workout;
  const targetOnly = reconciliation.state === 'target_only';
  const targetDeleted = reconciliation.state === 'target_deleted';
  const deliveryFailed = reconciliation.state === 'delivery_failed';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {targetOnly && <Trans>Use this {target} workout in Praxys?</Trans>}
            {deliveryFailed && <Trans>Retry this delivery?</Trans>}
            {!targetOnly && !deliveryFailed && <Trans>Resolve workout conflict</Trans>}
          </DialogTitle>
          <DialogDescription>
            {targetOnly ? (
              <Trans>This workout stays external unless you explicitly make it canonical in Praxys.</Trans>
            ) : targetDeleted ? (
              <Trans>The Praxys workout is missing from {target}. Restoring it keeps the Praxys version canonical.</Trans>
            ) : deliveryFailed ? (
              <Trans>Praxys could not finish delivery. Retrying keeps the Praxys version canonical.</Trans>
            ) : (
              <Trans>Praxys and {target} have different versions. Choose which one becomes canonical.</Trans>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="divide-y divide-border border-y border-border">
          {!targetOnly && (
            <div className="py-3">
              <p className="text-[11px] font-data uppercase tracking-wider text-muted-foreground">
                <Trans>Praxys version</Trans>
              </p>
              <p className="mt-1 text-sm font-medium text-foreground">
                {formatType(workout.workout_type)}
                {workout.duration_min != null && (
                  <span className="ml-2 font-data text-xs font-normal text-muted-foreground">
                    {Math.round(workout.duration_min)} <Trans>min</Trans>
                  </span>
                )}
              </p>
              {workout.description && (
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {workout.description}
                </p>
              )}
            </div>
          )}

          <div className="py-3">
            <p className="text-[11px] font-data uppercase tracking-wider text-muted-foreground">
              <Trans>{target} version</Trans>
            </p>
            {targetWorkout ? (
              <>
                <p className="mt-1 text-sm font-medium text-foreground">
                  {formatType(targetWorkout.workout_type)}
                  {targetWorkout.planned_duration_min != null && (
                    <span className="ml-2 font-data text-xs font-normal text-muted-foreground">
                      {Math.round(targetWorkout.planned_duration_min)} <Trans>min</Trans>
                    </span>
                  )}
                </p>
                {targetWorkout.workout_description && (
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {targetWorkout.workout_description}
                  </p>
                )}
              </>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">
                {targetDeleted
                  ? <Trans>No workout is present on {target}.</Trans>
                  : <Trans>The target version is unavailable.</Trans>}
              </p>
            )}
          </div>
        </div>

        {reconciliation.last_error && (
          <Alert variant="destructive">
            <AlertDescription>{reconciliation.last_error}</AlertDescription>
          </Alert>
        )}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-2 text-xs leading-relaxed text-muted-foreground">
          {canRestore && (
            <p>
              <strong className="font-medium text-foreground"><Trans>Restore Praxys:</Trans></strong>{' '}
              <Trans>keep the Praxys workout canonical and replace or recreate the target version.</Trans>
            </p>
          )}
          {canAccept && (
            <p>
              <strong className="font-medium text-foreground"><Trans>Use {target}:</Trans></strong>{' '}
              <Trans>copy the target workout into Praxys; future management follows that version.</Trans>
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" disabled={working} onClick={() => onOpenChange(false)}>
            <Trans>Cancel</Trans>
          </Button>
          {canAccept && (
            <Button
              variant={canRestore ? 'outline' : 'default'}
              disabled={working || actionsDisabled}
              onClick={() => onResolve('accept_target')}
            >
              {working ? <Trans>Applying…</Trans> : <Trans>Use {target} version</Trans>}
            </Button>
          )}
          {canRestore && (
            <Button
              disabled={working || actionsDisabled || !targetConnected}
              onClick={() => onResolve('restore_praxys')}
            >
              {working
                ? <Trans>Restoring…</Trans>
                : deliveryFailed
                  ? <Trans>Retry delivery</Trans>
                  : <Trans>Restore Praxys</Trans>}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

async function pushWorkout(
  workout: PlannedWorkout,
  fallbackError: string,
  missingResultError: string,
): Promise<void> {
  const request: {
    workout_dates: string[];
    canonical_ids?: string[];
  } = {
    workout_dates: [workout.date],
  };
  if (workout.canonical_id) {
    request.canonical_ids = [workout.canonical_id];
  }
  const response = await apiFetch('/api/plan/push-stryd', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, fallbackError),
    );
  }
  const body = await response.json() as { results: StrydPushResult[] };
  const result = body.results.find(
    (candidate) =>
      candidate.canonical_id === workout.canonical_id
      || (
        candidate.canonical_id == null
        && candidate.date === workout.date
      ),
  );
  if (!result) throw new Error(missingResultError);
  if (result.status === 'error') throw new Error(result.error);
}

async function resolveWorkout(
  reconciliation: PlanReconciliation,
  action: PlanResolutionAction,
  fallbackError: string,
): Promise<PlanResolutionResponse> {
  const response = await apiFetch('/api/plan/reconciliation/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reconciliation_id: reconciliation.id,
      action,
    }),
  });
  if (!response.ok) {
    throw new Error(
      await extractErrorMessage(response, fallbackError),
    );
  }
  return response.json() as Promise<PlanResolutionResponse>;
}

interface PlanMutationHttpError extends Error {
  status: number;
  code?: PlanMutationErrorCode;
}

async function requestPlanMutation<T>(
  url: string,
  init: RequestInit,
  fallbackError: string,
): Promise<T> {
  const response = await apiFetch(url, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {
      detail?:
        | string
        | { code?: string; message?: string }
        | { msg?: string }[];
      message?: string;
    } | null;
    const detail = payload?.detail;
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail[0]?.msg ?? fallbackError
        : detail?.message ?? payload?.message ?? fallbackError;
    const error = new Error(message) as PlanMutationHttpError;
    error.status = response.status;
    if (detail && !Array.isArray(detail) && typeof detail === 'object') {
      error.code = detail.code as PlanMutationErrorCode | undefined;
    }
    throw error;
  }
  return response.json() as Promise<T>;
}

export default function UpcomingPlanCard() {
  const { t } = useLingui();
  const { locale } = useLocale();
  const { config: settings, connectionStatuses } = useSettings();
  const [windowId, setWindowId] = useState<WindowId>(() => {
    if (typeof window === 'undefined') return '2wk';
    const stored = window.localStorage.getItem(WINDOW_STORAGE_KEY) as WindowId | null;
    return stored && WINDOW_OPTIONS.some((option) => option.id === stored)
      ? stored
      : '2wk';
  });
  const windowDays =
    WINDOW_OPTIONS.find((option) => option.id === windowId)?.days ?? 14;
  const [localDay, setLocalDay] = useState(
    () => athletePlanWindow(1).start,
  );
  const [windowOffsetDays, setWindowOffsetDays] = useState(0);
  useEffect(() => {
    let timer: number | undefined;
    const refreshLocalDay = () => {
      setLocalDay(athletePlanWindow(1).start);
    };
    const scheduleMidnightRefresh = () => {
      const now = new Date();
      const nextMidnight = new Date(now);
      nextMidnight.setHours(24, 0, 0, 0);
      timer = window.setTimeout(() => {
        refreshLocalDay();
        scheduleMidnightRefresh();
      }, Math.max(nextMidnight.getTime() - now.getTime(), 1));
    };
    window.addEventListener('focus', refreshLocalDay);
    scheduleMidnightRefresh();
    return () => {
      window.removeEventListener('focus', refreshLocalDay);
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);
  const windowStart = shiftAthletePlanDate(localDay, windowOffsetDays);
  const planUrl = useMemo(
    () => planWindowUrl(
      windowDays,
      new Date(`${windowStart}T12:00:00`),
    ),
    [windowDays, windowStart],
  );
  const { data, loading, error, refetch } = useApi<PlanResponse>(planUrl);
  const [workingKey, setWorkingKey] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [reviewWorkout, setReviewWorkout] = useState<PlannedWorkout | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [undoingAdjustment, setUndoingAdjustment] = useState<string | null>(null);
  const [adjustmentError, setAdjustmentError] = useState<string | null>(null);
  const [editor, setEditor] = useState<
    { mode: 'create' } | { mode: 'edit'; workout: PlannedWorkout } | null
  >(null);
  const [editorWorking, setEditorWorking] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [mutationNotice, setMutationNotice] = useState<string | null>(null);

  const clearRowError = useCallback((key: string) => {
    setRowErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, []);

  const planManagement = settings?.plan_management ?? {
    mode: 'external' as const,
    execution_target: null,
    delivery_enabled: false,
    adjustment_policy: 'suggest_only' as const,
  };
  const managementState = managedPlanState(planManagement);
  const executionTarget = planManagement.execution_target ?? data?.sync_target ?? null;
  const targetConnected = executionTarget != null
    && connectionStatuses[executionTarget] === 'connected';
  const targetLabel = planTargetLabel(executionTarget);
  const canWrite = data?.management?.can_write !== false;
  const mutationAvailable = (
    data?.management?.mutation_api_version === 1
    && canWrite
  );

  const handleWindowChange = useCallback((next: WindowId) => {
    setWindowId(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(WINDOW_STORAGE_KEY, next);
    }
  }, []);

  const navigateWindow = useCallback((direction: -1 | 1) => {
    setWindowOffsetDays((current) => Math.max(
      0,
      current + (direction * windowDays),
    ));
  }, [windowDays]);

  const refreshDateWindow = async (workoutDate: string) => {
    const dateOffset = Math.max(
      0,
      athletePlanDateDistance(localDay, workoutDate),
    );
    const nextOffset = Math.floor(dateOffset / windowDays) * windowDays;
    if (nextOffset === windowOffsetDays) {
      await refetch();
    } else {
      setWindowOffsetDays(nextOffset);
    }
  };

  const deliverWorkout = async (workout: PlannedWorkout) => {
    const key = workoutKey(workout);
    setWorkingKey(key);
    setRowErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    try {
      await pushWorkout(
        workout,
        t`Delivery failed`,
        t`No delivery result was returned for this workout`,
      );
      await refetch();
    } catch (actionError) {
      setRowErrors((current) => ({
        ...current,
        [key]: actionError instanceof Error ? actionError.message : t`Delivery failed`,
      }));
    } finally {
      setWorkingKey(null);
    }
  };

  const review = (workout: PlannedWorkout) => {
    setDialogError(null);
    setReviewWorkout(workout);
  };

  const resolve = async (action: PlanResolutionAction) => {
    const reconciliation = reviewWorkout?.reconciliation;
    if (!reviewWorkout || !reconciliation) return;
    const key = workoutKey(reviewWorkout);
    setWorkingKey(key);
    setDialogError(null);
    try {
      await resolveWorkout(
        reconciliation,
        action,
        t`Could not resolve this workout`,
      );
      setReviewWorkout(null);
      setRowErrors((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      await refetch();
    } catch (actionError) {
      setDialogError(
        actionError instanceof Error ? actionError.message : t`Could not resolve this workout`,
      );
    } finally {
      setWorkingKey(null);
    }
  };

  const undoAdjustment = async (revisionId: string) => {
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
        if (response.status === 409) await refetch();
        throw new Error(message);
      }
      await refetch();
    } catch (actionError) {
      setAdjustmentError(
        actionError instanceof Error
          ? actionError.message
          : t`Could not restore the previous workout`,
      );
    } finally {
      setUndoingAdjustment(null);
    }
  };

  const handleMutationError = async (actionError: unknown) => {
    const mutationError = actionError as Partial<PlanMutationHttpError>;
    if (mutationError.code === 'PLAN_VERSION_CONFLICT') {
      await refetch();
      setEditor(null);
      setMutationNotice(
        t`This workout changed elsewhere. The plan was refreshed; reopen the workout to continue.`,
      );
      return;
    }
    if (mutationError.code === 'PLAN_HISTORY_IMMUTABLE') {
      await refetch();
      setEditor(null);
      setMutationNotice(
        t`That date is now completed history and can no longer be changed.`,
      );
      return;
    }
    setEditorError(
      actionError instanceof Error
        ? actionError.message
        : t`Could not update this workout`,
    );
  };

  const saveWorkout = async (fields: PlanWorkoutWriteFields) => {
    setEditorWorking(true);
    setEditorError(null);
    setMutationNotice(null);
    try {
      if (editor?.mode === 'edit') {
        const { workout } = editor;
        if (!workout.canonical_id || !workout.workout_version) {
          throw new Error(t`Refresh the plan before editing this workout.`);
        }
        const payload: PlanWorkoutUpdateRequest = {
          ...fields,
          expected_version: workout.workout_version,
        };
        const result = await requestPlanMutation<PlanWorkoutMutationResponse>(
          `/api/plan/workouts/${encodeURIComponent(workout.canonical_id)}`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          },
          t`Could not update this workout`,
        );
        clearRowError(workoutKey(workout));
        setEditor(null);
        await refreshDateWindow(result.date);
      } else {
        const result = await requestPlanMutation<PlanWorkoutMutationResponse>(
          '/api/plan/workouts',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(fields),
          },
          t`Could not add this workout`,
        );
        setEditor(null);
        await refreshDateWindow(result.date);
      }
    } catch (actionError) {
      await handleMutationError(actionError);
    } finally {
      setEditorWorking(false);
    }
  };

  const convertWorkoutToRest = async (workoutDate: string) => {
    if (editor?.mode !== 'edit') return;
    const { workout } = editor;
    if (!workout.canonical_id || !workout.workout_version) {
      setEditorError(t`Refresh the plan before editing this workout.`);
      return;
    }
    setEditorWorking(true);
    setEditorError(null);
    setMutationNotice(null);
    try {
      const result = await requestPlanMutation<PlanWorkoutMutationResponse>(
        `/api/plan/workouts/${encodeURIComponent(workout.canonical_id)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expected_version: workout.workout_version,
            date: workoutDate,
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
          } satisfies PlanWorkoutUpdateRequest),
        },
        t`Could not convert this workout to rest`,
      );
      clearRowError(workoutKey(workout));
      setEditor(null);
      await refreshDateWindow(result.date);
    } catch (actionError) {
      await handleMutationError(actionError);
    } finally {
      setEditorWorking(false);
    }
  };

  const deleteWorkout = async () => {
    if (editor?.mode !== 'edit') return;
    const { workout } = editor;
    if (!workout.canonical_id || !workout.workout_version) {
      setEditorError(t`Refresh the plan before deleting this workout.`);
      return;
    }
    setEditorWorking(true);
    setEditorError(null);
    setMutationNotice(null);
    try {
      const params = new URLSearchParams({
        expected_version: workout.workout_version,
      });
      await requestPlanMutation<PlanWorkoutDeleteResponse>(
        `/api/plan/workouts/${encodeURIComponent(workout.canonical_id)}?${params}`,
        { method: 'DELETE' },
        t`Could not delete this workout`,
      );
      clearRowError(workoutKey(workout));
      setEditor(null);
      await refetch();
    } catch (actionError) {
      await handleMutationError(actionError);
    } finally {
      setEditorWorking(false);
    }
  };

  if (loading) {
    return (
      <section>
        <Skeleton className="mb-5 h-3 w-32" />
        <Skeleton className="mb-5 h-12 w-full" />
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-14 rounded-lg" />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-destructive"><Trans>Failed to load training plan</Trans></p>
          <p className="text-xs text-muted-foreground">{error}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <Trans>Retry</Trans>
        </Button>
      </section>
    );
  }

  if (!data) return null;

  const praxysCount = data.workouts.filter(isPraxysOwned).length;
  const conflictCount = data.workouts.filter(
    (workout) => workout.reconciliation?.conflict,
  ).length;
  const firstExternalOverlap = data.workouts.find(
    (workout) => (
      workout.external_overlap
      && (workout.reconciliation?.resolutions.length ?? 0) > 0
    ),
  ) ?? data.workouts.find((workout) => workout.external_overlap);
  const latestAdjustment = data.adjustments?.[0];
  const latestAdjustmentContextIds = latestAdjustment
    ? personalContextEvidenceIds(latestAdjustment.evidence)
    : [];
  const editorWorkout = editor?.mode === 'edit' ? editor.workout : null;
  const minimumDate = data.management?.minimum_date ?? localDay;
  const defaultEditorDate = data.window.start < minimumDate
    ? minimumDate
    : data.window.start;
  const editorDialog = (
    <WorkoutPlanEditor
      open={editor != null}
      workout={editorWorkout}
      minimumDate={minimumDate}
      defaultDate={defaultEditorDate}
      working={editorWorking}
      error={editorError}
      onOpenChange={(open) => {
        if (!open) {
          setEditor(null);
          setEditorError(null);
        }
      }}
      onSave={(fields) => void saveWorkout(fields)}
      onConvertToRest={(date) => void convertWorkoutToRest(date)}
      onDelete={() => void deleteWorkout()}
    />
  );
  const header = (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-[10px] font-data uppercase tracking-[0.14em] text-muted-foreground">
            <Trans>Upcoming Plan</Trans>
          </p>
          <WindowPills active={windowId} onChange={handleWindowChange} />
          <div
            className="inline-flex items-center rounded-full border border-border"
            role="group"
            aria-label={t`Browse plan dates`}
          >
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="rounded-full"
              disabled={windowOffsetDays === 0}
              aria-label={t`Previous plan window`}
              onClick={() => navigateWindow(-1)}
            >
              <ChevronLeft aria-hidden="true" />
            </Button>
            <span className="min-w-32 px-1 text-center font-data text-[11px] text-muted-foreground">
              {formatWindowRange(data.window.start, data.window.end, locale)}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              className="rounded-full"
              aria-label={t`Next plan window`}
              onClick={() => navigateWindow(1)}
            >
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-3 font-data text-[11px] text-muted-foreground">
            {conflictCount > 0 && (
              <span className="text-accent-amber">
                <Plural
                  value={conflictCount}
                  one="# needs review"
                  other="# need review"
                />
              </span>
            )}
            <Plural value={data.workouts.length} one="# workout" other="# workouts" />
          </div>
          {mutationAvailable && (
            <Button
              type="button"
              size="sm"
              onClick={() => {
                setEditorError(null);
                setMutationNotice(null);
                setEditor({ mode: 'create' });
              }}
            >
              <Plus aria-hidden="true" />
              <Trans>Add workout</Trans>
            </Button>
          )}
        </div>
      </div>
      <ManagementStrip
        state={managementState}
        target={targetLabel}
        targetConnected={targetConnected}
      />
      {mutationNotice && (
        <Alert className="mb-4 border-accent-cobalt/25 bg-accent-cobalt/5">
          <RefreshCw className="text-accent-cobalt" aria-hidden="true" />
          <AlertDescription className="text-xs text-foreground">
            {mutationNotice}
          </AlertDescription>
        </Alert>
      )}
      {firstExternalOverlap && (
        <Alert className="mb-4 border-accent-amber/30 bg-accent-amber/8">
          <TriangleAlert className="text-accent-amber" aria-hidden="true" />
          <AlertDescription>
            <div className="flex flex-col gap-2 text-xs sm:flex-row sm:items-center sm:justify-between">
              <span>
                <Trans>
                  An external planner overlaps the Praxys plan. Use one planner at a time to avoid duplicate or conflicting sessions.
                </Trans>
              </span>
              {canWrite
                && firstExternalOverlap.reconciliation
                && firstExternalOverlap.reconciliation.resolutions.length > 0
                && (
                  <Button
                    type="button"
                    variant="link"
                    size="sm"
                    onClick={() => review(firstExternalOverlap)}
                    className="h-auto self-start px-0 text-accent-amber sm:self-auto"
                  >
                    <Trans>Review conflict</Trans>
                  </Button>
                )}
            </div>
          </AlertDescription>
        </Alert>
      )}
      {latestAdjustment && (
        <Alert
          className={`mb-5 ${
            latestAdjustment.status === 'active'
              ? 'border-accent-amber/30 bg-accent-amber/8'
              : 'border-border bg-muted/35'
          }`}
        >
          <ShieldCheck
            className={
              latestAdjustment.status === 'active'
                ? 'text-accent-amber'
                : 'text-muted-foreground'
            }
            aria-hidden="true"
          />
          <AlertDescription>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-semibold text-foreground">
                  {latestAdjustment.status === 'active' && (
                    <Trans>Praxys made a conservative plan change</Trans>
                  )}
                  {latestAdjustment.status === 'undone' && (
                    <Trans>The previous workout was restored</Trans>
                  )}
                  {latestAdjustment.status === 'superseded' && (
                    <Trans>An earlier automatic change was superseded</Trans>
                  )}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  {latestAdjustment.workout_date && (
                    <span className="font-data">
                      {formatNoticeDate(latestAdjustment.workout_date, locale)}
                      {' \u00b7 '}
                    </span>
                  )}
                  <span className="font-medium text-foreground">
                    {formatType(latestAdjustment.before.workout_type ?? t`Workout`)}
                    {' \u2192 '}
                    {formatType(latestAdjustment.after.workout_type ?? t`Rest`)}
                  </span>
                  {' \u00b7 '}
                  <Trans>Current HRV crossed your personal caution band.</Trans>
                </p>
                {latestAdjustmentContextIds.length > 0 && (
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    <Trans>
                      This change used confirmed private context. The private
                      detail is not copied into the plan record.
                    </Trans>{' '}
                    <a
                      href="#plan-context"
                      className="font-medium text-accent-cobalt underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Trans>Inspect context</Trans>
                    </a>
                  </p>
                )}
              </div>
              {latestAdjustment.can_undo && canWrite && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={undoingAdjustment != null}
                  onClick={() => void undoAdjustment(latestAdjustment.id)}
                >
                  <RotateCcw aria-hidden="true" />
                  {undoingAdjustment === latestAdjustment.id
                    ? <Trans>Restoring…</Trans>
                    : <Trans>Restore workout</Trans>}
                </Button>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}
      {adjustmentError && (
        <Alert variant="destructive" className="mt-2">
          <AlertDescription>{adjustmentError}</AlertDescription>
        </Alert>
      )}
    </>
  );

  if (data.workouts.length === 0) {
    return (
      <section>
        {header}
        <div className="flex flex-col items-start gap-3 py-3">
          <p className="text-sm text-muted-foreground">
            <Trans>No workouts scheduled in this window.</Trans>
            {windowId !== '4wk' && (
              <span className="ml-1"><Trans>Try a longer window above.</Trans></span>
            )}
          </p>
          {mutationAvailable && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setEditorError(null);
                setMutationNotice(null);
                setEditor({ mode: 'create' });
              }}
            >
              <Plus aria-hidden="true" />
              <Trans>Add the first workout</Trans>
            </Button>
          )}
        </div>
        <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
          <Trans>
            Praxys only changes workouts it created or you explicitly adopt. Manual workouts and workouts from another coach stay untouched.
          </Trans>
        </p>
        {editorDialog}
      </section>
    );
  }

  return (
    <section>
      {header}
      {managementState === 'active' && praxysCount === 0 && (
        <Alert className="mb-4 border-accent-cobalt/25 bg-accent-cobalt/5">
          <AlertDescription className="text-xs text-foreground">
            <Trans>
              Managed delivery is active, but this window contains no Praxys-owned workouts. External workouts remain untouched.
            </Trans>
          </AlertDescription>
        </Alert>
      )}
      <div className="space-y-1">
        {data.workouts.map((workout) => {
          const key = workoutKey(workout);
          const canResolveLocally = (
            workout.reconciliation?.resolutions.includes('accept_target')
            ?? false
          );
          return (
            <WorkoutRow
              key={key}
              workout={workout}
              managementState={managementState}
              target={executionTarget}
              writeAccess={canWrite}
              working={workingKey === key}
              actionsDisabled={
                workingKey != null
                || editorWorking
                || !canWrite
                || (
                  managementState === 'active'
                  && !targetConnected
                  && !canResolveLocally
                )
              }
              editDisabled={
                workingKey != null
                || editorWorking
                || !canWrite
              }
              error={rowErrors[key]}
              onDeliver={() => deliverWorkout(workout)}
              onEdit={
                mutationAvailable
                && isPraxysOwned(workout)
                && workout.editable === true
                && Boolean(workout.workout_version)
                ? () => {
                    setEditorError(null);
                    setMutationNotice(null);
                    setEditor({ mode: 'edit', workout });
                  }
                : undefined
              }
              onReview={() => review(workout)}
            />
          );
        })}
      </div>
      <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
        <Trans>
          Praxys only changes workouts it created or you explicitly adopt. Manual workouts and workouts from another coach stay untouched.
        </Trans>
      </p>

      <ConflictDialog
        workout={reviewWorkout}
        open={reviewWorkout != null}
        targetConnected={targetConnected}
        actionsDisabled={!canWrite}
        working={reviewWorkout != null && workingKey === workoutKey(reviewWorkout)}
        error={dialogError}
        onOpenChange={(open) => {
          if (!open && workingKey == null) {
            setReviewWorkout(null);
            setDialogError(null);
          }
        }}
        onResolve={resolve}
      />
      {editorDialog}
    </section>
  );
}
