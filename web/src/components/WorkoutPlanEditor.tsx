import { useEffect, useState, type FormEvent } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import { CalendarDays, Moon, Trash2 } from 'lucide-react';

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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { isRestWorkoutType } from '@/lib/plan';
import type {
  PlannedWorkout,
  PlanWorkoutWriteFields,
} from '@/types/api';

const WORKOUT_TYPES = [
  'easy',
  'recovery',
  'long_run',
  'tempo',
  'threshold',
  'interval',
  'rest',
] as const;

interface WorkoutDraft {
  date: string;
  workoutType: string;
  duration: string;
  distance: string;
  powerMin: string;
  powerMax: string;
  hrMin: string;
  hrMax: string;
  paceMin: string;
  paceMax: string;
  description: string;
}

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function initialDraft(
  workout: PlannedWorkout | null,
  defaultDate: string,
): WorkoutDraft {
  return {
    date: workout?.date ?? defaultDate,
    workoutType: workout?.workout_type ?? 'easy',
    duration: workout?.duration_min?.toString() ?? '',
    distance: workout?.distance_km?.toString() ?? '',
    powerMin: workout?.power_min?.toString() ?? '',
    powerMax: workout?.power_max?.toString() ?? '',
    hrMin: workout?.hr_min?.toString() ?? '',
    hrMax: workout?.hr_max?.toString() ?? '',
    paceMin: workout?.pace_min ?? '',
    paceMax: workout?.pace_max ?? '',
    description: workout?.description ?? '',
  };
}

function writeFields(draft: WorkoutDraft): PlanWorkoutWriteFields {
  const isRest = isRestWorkoutType(draft.workoutType);
  return {
    date: draft.date,
    workout_type: draft.workoutType,
    planned_duration_min: isRest ? null : numberOrNull(draft.duration),
    planned_distance_km: isRest ? null : numberOrNull(draft.distance),
    target_power_min: isRest ? null : numberOrNull(draft.powerMin),
    target_power_max: isRest ? null : numberOrNull(draft.powerMax),
    target_hr_min: isRest ? null : numberOrNull(draft.hrMin),
    target_hr_max: isRest ? null : numberOrNull(draft.hrMax),
    target_pace_min: isRest ? null : draft.paceMin.trim() || null,
    target_pace_max: isRest ? null : draft.paceMax.trim() || null,
    workout_description: draft.description.trim(),
  };
}

export default function WorkoutPlanEditor({
  open,
  workout,
  minimumDate,
  defaultDate,
  working,
  error,
  onOpenChange,
  onSave,
  onConvertToRest,
  onDelete,
}: {
  open: boolean;
  workout: PlannedWorkout | null;
  minimumDate: string;
  defaultDate: string;
  working: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onSave: (fields: PlanWorkoutWriteFields) => void;
  onConvertToRest: (date: string) => void;
  onDelete: () => void;
}) {
  const { t } = useLingui();
  const [draft, setDraft] = useState<WorkoutDraft>(
    () => initialDraft(workout, defaultDate),
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const editing = workout != null;

  useEffect(() => {
    if (!open) return;
    setDraft(initialDraft(workout, defaultDate));
    setConfirmDelete(false);
  }, [defaultDate, open, workout]);
  const unknownWorkoutType = WORKOUT_TYPES.includes(
    draft.workoutType as typeof WORKOUT_TYPES[number],
  )
    ? null
    : draft.workoutType;
  const restSelected = isRestWorkoutType(draft.workoutType);
  const workoutTypeLabels: Record<string, string> = {
    easy: t`Easy`,
    recovery: t`Recovery`,
    long_run: t`Long run`,
    tempo: t`Tempo`,
    threshold: t`Threshold`,
    interval: t`Intervals`,
    rest: t`Rest`,
  };
  const selectedWorkoutTypeLabel = (
    workoutTypeLabels[draft.workoutType]
    ?? draft.workoutType
      .split(/[\s_]+/)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  );

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSave(writeFields(draft));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!working) onOpenChange(next);
      }}
    >
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        {confirmDelete && workout ? (
          <>
            <DialogHeader>
              <DialogTitle><Trans>Delete this workout?</Trans></DialogTitle>
              <DialogDescription>
                <Trans>
                  This removes the Praxys workout from the canonical plan. Any external workout stays untouched.
                </Trans>
              </DialogDescription>
            </DialogHeader>
            <div className="border-y border-border py-4">
              <p className="text-sm font-medium text-foreground">
                {workout.workout_type.replaceAll('_', ' ')}
              </p>
              <p className="mt-1 font-data text-xs text-muted-foreground">
                {workout.date}
              </p>
            </div>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={working}
                onClick={() => setConfirmDelete(false)}
              >
                <Trans>Keep workout</Trans>
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={working}
                onClick={onDelete}
              >
                <Trash2 aria-hidden="true" />
                {working ? <Trans>Deleting…</Trans> : <Trans>Delete workout</Trans>}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={submit}>
            <DialogHeader>
              <DialogTitle>
                {editing ? <Trans>Edit workout</Trans> : <Trans>Add workout</Trans>}
              </DialogTitle>
              <DialogDescription>
                {editing ? (
                  <Trans>
                    Update the canonical plan here. Connector delivery changes only when managed delivery is active.
                  </Trans>
                ) : (
                  <Trans>
                    Add one future workout to the Praxys canonical plan.
                  </Trans>
                )}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-5 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-date"><Trans>Date</Trans></Label>
                <div className="relative">
                  <CalendarDays
                    className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    id="plan-workout-date"
                    type="date"
                    min={minimumDate}
                    value={draft.date}
                    disabled={working}
                    onChange={(event) => setDraft((current) => ({
                      ...current,
                      date: event.target.value,
                    }))}
                    className="pl-8 font-data"
                    required
                  />
                </div>
                {editing && draft.date !== workout.date && (
                  <p className="text-[11px] text-muted-foreground">
                    <Trans>Saving will reschedule this workout.</Trans>
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-type"><Trans>Workout type</Trans></Label>
                <Select
                  value={draft.workoutType}
                  onValueChange={(value) => setDraft((current) => ({
                    ...current,
                    workoutType: value ?? current.workoutType,
                  }))}
                  disabled={working}
                >
                  <SelectTrigger id="plan-workout-type" className="w-full">
                    <SelectValue>{selectedWorkoutTypeLabel}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {unknownWorkoutType && (
                      <SelectItem value={unknownWorkoutType}>
                        {selectedWorkoutTypeLabel}
                      </SelectItem>
                    )}
                    {WORKOUT_TYPES.map((workoutType) => (
                      <SelectItem key={workoutType} value={workoutType}>
                        {workoutTypeLabels[workoutType]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-duration">
                  <Trans>Duration (minutes)</Trans>
                </Label>
                <Input
                  id="plan-workout-duration"
                  type="number"
                  min="0"
                  max="1440"
                  step="1"
                  inputMode="decimal"
                  value={draft.duration}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    duration: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`Optional`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-distance">
                  <Trans>Distance (km)</Trans>
                </Label>
                <Input
                  id="plan-workout-distance"
                  type="number"
                  min="0"
                  max="1000"
                  step="0.1"
                  inputMode="decimal"
                  value={draft.distance}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    distance: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`Optional`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-power-min">
                  <Trans>Power floor (W)</Trans>
                </Label>
                <Input
                  id="plan-workout-power-min"
                  type="number"
                  min="0"
                  max="5000"
                  step="1"
                  inputMode="decimal"
                  value={draft.powerMin}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    powerMin: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`Optional`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-power-max">
                  <Trans>Power ceiling (W)</Trans>
                </Label>
                <Input
                  id="plan-workout-power-max"
                  type="number"
                  min="0"
                  max="5000"
                  step="1"
                  inputMode="decimal"
                  value={draft.powerMax}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    powerMax: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`Optional`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-hr-min">
                  <Trans>Heart-rate minimum (bpm)</Trans>
                </Label>
                <Input
                  id="plan-workout-hr-min"
                  type="number"
                  min="0"
                  max="300"
                  step="1"
                  inputMode="decimal"
                  value={draft.hrMin}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    hrMin: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`Optional`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-hr-max">
                  <Trans>Heart-rate maximum (bpm)</Trans>
                </Label>
                <Input
                  id="plan-workout-hr-max"
                  type="number"
                  min="0"
                  max="300"
                  step="1"
                  inputMode="decimal"
                  value={draft.hrMax}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    hrMax: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`Optional`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-pace-min">
                  <Trans>Pace minimum (min/km)</Trans>
                </Label>
                <Input
                  id="plan-workout-pace-min"
                  maxLength={20}
                  value={draft.paceMin}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    paceMin: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`e.g. 5:20`}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-pace-max">
                  <Trans>Pace maximum (min/km)</Trans>
                </Label>
                <Input
                  id="plan-workout-pace-max"
                  maxLength={20}
                  value={draft.paceMax}
                  disabled={working || restSelected}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    paceMax: event.target.value,
                  }))}
                  className="font-data"
                  placeholder={t`e.g. 5:45`}
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="plan-workout-description">
                  <Trans>Workout notes</Trans>
                </Label>
                <textarea
                  id="plan-workout-description"
                  value={draft.description}
                  disabled={working}
                  maxLength={4000}
                  rows={3}
                  onChange={(event) => setDraft((current) => ({
                    ...current,
                    description: event.target.value,
                  }))}
                  className="flex w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50"
                  placeholder={t`Optional structure, terrain, or intent`}
                />
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col-reverse gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-2">
                {editing && (
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={working}
                    onClick={() => setConfirmDelete(true)}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 aria-hidden="true" />
                    <Trans>Delete</Trans>
                  </Button>
                )}
                {editing && !isRestWorkoutType(workout.workout_type) && (
                  <Button
                    type="button"
                    variant="outline"
                    disabled={working}
                    onClick={() => onConvertToRest(draft.date)}
                  >
                    <Moon aria-hidden="true" />
                    <Trans>Convert to rest</Trans>
                  </Button>
                )}
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={working}
                  onClick={() => onOpenChange(false)}
                >
                  <Trans>Cancel</Trans>
                </Button>
                <Button type="submit" disabled={working}>
                  {working
                    ? <Trans>Saving…</Trans>
                    : editing
                      ? <Trans>Save workout</Trans>
                      : <Trans>Add workout</Trans>}
                </Button>
              </div>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
