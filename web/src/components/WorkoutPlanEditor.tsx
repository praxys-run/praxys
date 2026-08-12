import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import { CalendarDays, GitFork, Moon, Sparkles, Trash2 } from 'lucide-react';

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
import WorkoutStructureEditor from '@/components/WorkoutStructureEditor';
import { apiFetch } from '@/hooks/useApi';
import { isRestWorkoutType } from '@/lib/plan';
import {
  commitAllWorkoutEditorTargetInputs,
  createWorkoutEditorStructure,
  createStructuredStep,
  deriveFlatFieldsFromStructure,
  serializeWorkoutEditorStructure,
  synthesizeStructureFromFlat,
  validateWorkoutEditorStructure,
  type WorkoutEditorStructureV1,
} from '@/lib/workout-structure';
import type {
  PlanActivityType,
  PlannedWorkout,
  PlanWorkoutCompatibilityRequest,
  PlanWorkoutCompatibilityResponse,
  PlanWorkoutUpdateRequest,
  PlanWorkoutWriteFields,
  WorkoutStructureV1,
} from '@/types/api';

const PURPOSES = [
  'easy',
  'recovery',
  'long_run',
  'tempo',
  'threshold',
  'interval',
  'hill_repeat',
  'testing',
  'rest',
] as const;
const CUSTOM_PURPOSE = '__custom__';

const ACTIVITIES: PlanActivityType[] = [
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

type EditorMode = 'legacy' | 'structured' | 'unsupported';
type WorkoutEditorSaveFields =
  | PlanWorkoutWriteFields
  | Omit<PlanWorkoutUpdateRequest, 'expected_version'>;

interface WorkoutDraft {
  date: string;
  activityType: PlanActivityType;
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
  mode: EditorMode;
  structure: WorkoutEditorStructureV1;
  /** Preserve a tree while the athlete temporarily picks Rest in the form. */
  previousNonRestStructure: WorkoutEditorStructureV1 | null;
}

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function defaultActivity(workoutType: string): PlanActivityType {
  return isRestWorkoutType(workoutType) ? 'rest' : 'running';
}

function portableActivity(
  value: unknown,
  workoutType: string,
): PlanActivityType {
  if (isRestWorkoutType(workoutType)) return 'rest';
  if (
    typeof value === 'string'
    && value !== 'rest'
    && ACTIVITIES.includes(value as PlanActivityType)
  ) {
    return value as PlanActivityType;
  }
  return value == null ? defaultActivity(workoutType) : 'other';
}

function structuredDefault(workoutType: string): WorkoutEditorStructureV1 {
  return createWorkoutEditorStructure(isRestWorkoutType(workoutType)
    ? { steps: [] }
    : { steps: [createStructuredStep()] });
}

function supportedStructure(
  workout: PlannedWorkout | null,
): WorkoutStructureV1 | null {
  if (
    workout?.workout_structure_version !== 'v1'
    || workout.workout_structure == null
    || (
      workout.workout_structure_status != null
      && workout.workout_structure_status !== 'supported'
    )
  ) return null;
  const candidate = workout.workout_structure;
  if (
    typeof candidate !== 'object'
    || !Array.isArray((candidate as { steps?: unknown }).steps)
  ) return null;
  return candidate as WorkoutStructureV1;
}

function initialDraft(
  workout: PlannedWorkout | null,
  seedWorkout: PlannedWorkout | null,
  defaultDate: string,
  minimumDate: string,
): WorkoutDraft {
  const source = workout ?? seedWorkout;
  const workoutType = source?.workout_type ?? 'easy';
  const activityType = portableActivity(source?.activity_type, workoutType);
  const structureFromSource = supportedStructure(source);
  const hasStructure = structureFromSource != null;
  const hasUnsupportedStructure = (
    source != null
    && (
      (
        source.workout_structure_status != null
        && source.workout_structure_status !== 'absent'
        && source.workout_structure_status !== 'supported'
      )
      ||
      source.workout_structure_version != null
      || source.workout_structure != null
    )
    && !hasStructure
  );
  const sourceDate = source?.date ?? defaultDate;
  const structure: WorkoutEditorStructureV1 = structureFromSource
    ? createWorkoutEditorStructure(structureFromSource)
    : structuredDefault(workoutType);
  return {
    date: sourceDate >= minimumDate ? sourceDate : defaultDate,
    activityType,
    workoutType,
    duration: source?.duration_min?.toString() ?? '',
    distance: source?.distance_km?.toString() ?? '',
    powerMin: source?.power_min?.toString() ?? '',
    powerMax: source?.power_max?.toString() ?? '',
    hrMin: source?.hr_min?.toString() ?? '',
    hrMax: source?.hr_max?.toString() ?? '',
    paceMin: source?.pace_min ?? '',
    paceMax: source?.pace_max ?? '',
    description: source?.description ?? '',
    // Existing legacy rows stay flat until the athlete explicitly converts
    // them. New Praxys authoring starts from the portable rich structure.
    mode: hasUnsupportedStructure
      ? 'unsupported'
      : hasStructure || source == null
        ? 'structured'
        : 'legacy',
    structure,
    previousNonRestStructure: !isRestWorkoutType(workoutType)
      ? structure
      : null,
  };
}

function flatWriteFields(draft: WorkoutDraft): Omit<
  PlanWorkoutWriteFields,
  'workout_structure_version' | 'workout_structure'
> {
  const isRest = isRestWorkoutType(draft.workoutType);
  return {
    date: draft.date,
    activity_type: isRest ? 'rest' : draft.activityType,
    workout_type: draft.workoutType.trim(),
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

function writeFields(draft: WorkoutDraft): WorkoutEditorSaveFields {
  if (draft.mode === 'unsupported') {
    return {
      date: draft.date,
      workout_description: draft.description.trim(),
    };
  }
  const flat = flatWriteFields(draft);
  if (draft.mode === 'legacy') return flat;
  const isRest = isRestWorkoutType(draft.workoutType);
  const canonicalStructure = serializeWorkoutEditorStructure(draft.structure);
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
    : deriveFlatFieldsFromStructure(canonicalStructure);
  return {
    ...flat,
    ...projection,
    activity_type: isRest ? 'rest' : draft.activityType,
    workout_structure_version: 'v1',
    workout_structure: canonicalStructure,
  };
}

function validationErrors(draft: WorkoutDraft): string[] {
  const errors: string[] = [];
  if (!draft.date) errors.push('Choose a date for this workout.');
  if (!draft.workoutType.trim()) errors.push('Enter a workout purpose.');
  if (draft.mode === 'structured') {
    errors.push(...validateWorkoutEditorStructure(
      draft.structure,
      draft.workoutType,
    ));
  }
  return errors;
}

function errorMessage(
  payload: PlanWorkoutCompatibilityRequest,
): string | null {
  if (!payload.workout_type.trim()) return 'Enter a workout purpose first.';
  return null;
}

export default function WorkoutPlanEditor({
  open,
  workout,
  seedWorkout = null,
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
  /** A source-owned row can be forked without ever editing its source copy. */
  seedWorkout?: PlannedWorkout | null;
  minimumDate: string;
  defaultDate: string;
  working: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onSave: (fields: WorkoutEditorSaveFields) => void;
  onConvertToRest: (date: string) => void;
  onDelete: () => void;
}) {
  const { t } = useLingui();
  const [draft, setDraft] = useState<WorkoutDraft>(
    () => initialDraft(workout, seedWorkout, defaultDate, minimumDate),
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [compatibility, setCompatibility] = useState<
    PlanWorkoutCompatibilityResponse['providers'] | null
  >(workout?.provider_compatibility ?? null);
  const [compatibilityLoading, setCompatibilityLoading] = useState(false);
  const [compatibilityError, setCompatibilityError] = useState<string | null>(
    null,
  );
  const editing = workout != null;
  const forking = !editing && seedWorkout != null;
  const unsupportedFork = forking && draft.mode === 'unsupported';
  const restSelected = isRestWorkoutType(draft.workoutType);
  const selectedPurpose = PURPOSES.includes(
    draft.workoutType as typeof PURPOSES[number],
  )
    ? draft.workoutType
    : CUSTOM_PURPOSE;
  const draftErrors = useMemo(() => validationErrors(draft), [draft]);
  const compatibilityPayload = useMemo(
    () => draft.mode === 'unsupported'
      ? null
      : writeFields(draft) as PlanWorkoutCompatibilityRequest,
    [draft],
  );
  const previewIssue = draft.mode === 'unsupported'
    ? null
    : draftErrors[0] ?? errorMessage(
        compatibilityPayload as PlanWorkoutCompatibilityRequest,
      );

  useEffect(() => {
    if (!open) return;
    const next = initialDraft(
      workout,
      seedWorkout,
      defaultDate,
      minimumDate,
    );
    setDraft(next);
    setConfirmDelete(false);
    setLocalError(null);
    setCompatibility(workout?.provider_compatibility ?? null);
    setCompatibilityError(null);
  }, [defaultDate, minimumDate, open, seedWorkout, workout]);

  useEffect(() => {
    if (!open) return undefined;
    if (draft.mode === 'unsupported') {
      setCompatibilityLoading(false);
      setCompatibility(workout?.provider_compatibility ?? null);
      setCompatibilityError(null);
      return undefined;
    }
    if (previewIssue) {
      setCompatibilityLoading(false);
      setCompatibility(null);
      setCompatibilityError(null);
      return undefined;
    }
    let active = true;
    const timeout = window.setTimeout(async () => {
      setCompatibilityLoading(true);
      setCompatibilityError(null);
      try {
        const response = await apiFetch('/api/plan/workouts/compatibility', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(
            compatibilityPayload as PlanWorkoutCompatibilityRequest,
          ),
        });
        if (!response.ok) throw new Error('preview failed');
        const preview = await response.json() as PlanWorkoutCompatibilityResponse;
        if (active) setCompatibility(preview.providers);
      } catch {
        if (active) {
          setCompatibility(null);
          setCompatibilityError(
            t`Compatibility preview is unavailable. Check your connection and try again.`,
          );
        }
      } finally {
        if (active) setCompatibilityLoading(false);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [compatibilityPayload, draft.mode, open, previewIssue, t, workout]);

  const purposeLabels: Record<string, string> = {
    easy: t`Easy`,
    recovery: t`Recovery`,
    long_run: t`Long run`,
    tempo: t`Tempo`,
    threshold: t`Threshold`,
    interval: t`Intervals`,
    hill_repeat: t`Hill repeats`,
    testing: t`Testing`,
    rest: t`Rest`,
  };
  const activityLabels: Record<PlanActivityType, string> = {
    running: t`Road running`,
    trail_running: t`Trail running`,
    cycling: t`Cycling`,
    walking: t`Walking`,
    hiking: t`Hiking`,
    strength: t`Strength`,
    mobility: t`Mobility`,
    cross_training: t`Cross-training`,
    rest: t`Rest`,
    other: t`Other`,
  };
  const selectedActivityLabel = activityLabels[
    restSelected ? 'rest' : draft.activityType
  ];
  const selectedPurposeLabel = selectedPurpose === CUSTOM_PURPOSE
    ? t`Custom wording`
    : purposeLabels[draft.workoutType];

  const setPurpose = (value: string) => {
    setLocalError(null);
    setDraft((current) => {
      const nextType = value === CUSTOM_PURPOSE ? '' : value;
      const isRest = isRestWorkoutType(nextType);
      const nextStructure = current.mode === 'structured'
        ? isRest
          ? { steps: [] }
          : current.structure.steps.length === 0
            ? current.previousNonRestStructure ?? structuredDefault(nextType)
            : current.structure
        : current.structure;
      return {
        ...current,
        workoutType: nextType,
        activityType: isRest
          ? 'rest'
          : current.activityType === 'rest'
            ? 'running'
            : current.activityType,
        structure: nextStructure,
        previousNonRestStructure: current.mode === 'structured' && isRest
          ? current.structure.steps.length > 0
            ? current.structure
            : current.previousNonRestStructure
          : current.previousNonRestStructure,
      };
    });
  };

  const convertLegacy = () => {
    try {
      const structure = synthesizeStructureFromFlat({
        workoutType: draft.workoutType,
        durationMinutes: numberOrNull(draft.duration),
        distanceKm: numberOrNull(draft.distance),
        powerMin: numberOrNull(draft.powerMin),
        powerMax: numberOrNull(draft.powerMax),
        hrMin: numberOrNull(draft.hrMin),
        hrMax: numberOrNull(draft.hrMax),
        paceMin: draft.paceMin.trim() || null,
        paceMax: draft.paceMax.trim() || null,
      });
      setDraft((current) => ({
        ...current,
        mode: 'structured',
        structure: createWorkoutEditorStructure(structure),
      }));
      setLocalError(null);
    } catch {
      setLocalError(
        t`Could not convert this legacy workout.`,
      );
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (unsupportedFork) {
      setLocalError(
        t`This source uses a newer workout structure and cannot be duplicated without losing details.`,
      );
      return;
    }
    const committed = draft.mode === 'structured'
      ? commitAllWorkoutEditorTargetInputs(draft.structure)
      : { structure: draft.structure, valid: true };
    const nextDraft = {
      ...draft,
      structure: committed.structure,
    };
    if (draft.mode === 'structured') {
      setDraft(nextDraft);
    }
    const errors = validationErrors(nextDraft);
    if (!committed.valid || errors.length > 0) {
      setLocalError(
        draft.mode === 'structured'
          ? t`Review the highlighted step fields. Every typed target and termination must be complete.`
          : errors[0],
      );
      return;
    }
    setLocalError(null);
    onSave(writeFields(nextDraft));
  };

  const convertToRest = () => {
    if (!editing || draft.mode === 'unsupported') return;
    if (draft.mode === 'legacy') {
      onConvertToRest(draft.date);
      return;
    }
    onSave({
      ...writeFields({
        ...draft,
        activityType: 'rest',
        workoutType: 'rest',
        structure: createWorkoutEditorStructure({ steps: [] }),
      }),
      workout_type: 'rest',
      activity_type: 'rest',
      workout_structure_version: 'v1',
      workout_structure: { steps: [] },
    });
  };

  const dialogError = localError ?? error;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!working) onOpenChange(next);
      }}
    >
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        {confirmDelete && workout ? (
          <>
            <DialogHeader>
              <DialogTitle><Trans>Delete this workout?</Trans></DialogTitle>
              <DialogDescription>
                <Trans>
                  This removes the Praxys workout from the canonical plan. Any
                  external workout stays untouched.
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
            {dialogError && (
              <Alert variant="destructive">
                <AlertDescription>{dialogError}</AlertDescription>
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
                {forking
                  ? <Trans>Duplicate into Praxys</Trans>
                  : editing
                    ? <Trans>Edit workout</Trans>
                    : <Trans>Add workout</Trans>}
              </DialogTitle>
              <DialogDescription>
                {forking ? (
                  <Trans>
                    The source workout stays locked. Save this copy as a new
                    Praxys-owned workout before changing it.
                  </Trans>
                ) : editing ? (
                  <Trans>
                    Update the canonical plan here. Connector delivery changes
                    only when managed delivery is active.
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
                <Label htmlFor="plan-workout-activity">
                  <Trans>Plan activity</Trans>
                </Label>
                <Select
                  value={restSelected ? 'rest' : draft.activityType}
                  disabled={
                    working || restSelected || draft.mode === 'unsupported'
                  }
                  onValueChange={(value) => setDraft((current) => ({
                    ...current,
                    activityType: (value ?? current.activityType) as PlanActivityType,
                  }))}
                >
                  <SelectTrigger id="plan-workout-activity" className="w-full">
                    <SelectValue>{selectedActivityLabel}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {ACTIVITIES.map((activity) => (
                      <SelectItem key={activity} value={activity}>
                        {activityLabels[activity]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] leading-relaxed text-muted-foreground">
                  <Trans>
                    Activity is the schedule lane (for example road or trail),
                    not the session purpose.
                  </Trans>
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="plan-workout-purpose">
                  <Trans>Workout purpose</Trans>
                </Label>
                <Select
                  value={selectedPurpose}
                  disabled={working || draft.mode === 'unsupported'}
                  onValueChange={(value) => {
                    if (value) setPurpose(value);
                  }}
                >
                  <SelectTrigger id="plan-workout-purpose" className="w-full">
                    <SelectValue>{selectedPurposeLabel}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {PURPOSES.map((purpose) => (
                      <SelectItem key={purpose} value={purpose}>
                        {purposeLabels[purpose]}
                      </SelectItem>
                    ))}
                    <SelectItem value={CUSTOM_PURPOSE}>
                      <Trans>Custom wording</Trans>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {selectedPurpose === CUSTOM_PURPOSE && (
                <div className="space-y-1.5">
                  <Label htmlFor="plan-workout-custom-purpose">
                    <Trans>Custom workout purpose</Trans>
                  </Label>
                  <Input
                    id="plan-workout-custom-purpose"
                    value={draft.workoutType}
                    disabled={working || draft.mode === 'unsupported'}
                    maxLength={50}
                    onChange={(event) => setDraft((current) => ({
                      ...current,
                      workoutType: event.target.value,
                    }))}
                    placeholder={t`e.g. Race rehearsal`}
                    required
                  />
                </div>
              )}
            </div>

            {draft.mode === 'unsupported' ? (
              <section className="border-y border-border py-5">
                <h3 className="mb-2 text-sm font-semibold text-foreground">
                  <Trans>Newer workout structure</Trans>
                </h3>
                <Alert>
                  <AlertDescription className="text-xs leading-relaxed">
                    {unsupportedFork ? (
                      <Trans>
                        This source uses a newer workout structure and cannot
                        be duplicated without losing details.
                      </Trans>
                    ) : (
                      <Trans>
                        This workout uses a newer portable structure that this
                        editor cannot change safely. Date and notes remain
                        editable; Praxys preserves the structure byte-for-byte.
                      </Trans>
                    )}
                  </AlertDescription>
                </Alert>
              </section>
            ) : draft.mode === 'legacy' ? (
              <section className="border-y border-border py-5">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      <Trans>Legacy flat summary</Trans>
                    </h3>
                    <p className="mt-1 max-w-xl text-xs leading-relaxed text-muted-foreground">
                      <Trans>
                        This imported or older workout has no portable tree.
                        Edit its summary as-is, or explicitly convert one
                        flat step without guessing semantics.
                      </Trans>
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={working}
                    onClick={convertLegacy}
                  >
                    <Sparkles aria-hidden="true" />
                    <Trans>Convert to structured steps</Trans>
                  </Button>
                </div>
                <LegacyFields
                  draft={draft}
                  disabled={working || restSelected}
                  onChange={setDraft}
                />
              </section>
            ) : (
              <WorkoutStructureEditor
                structure={draft.structure}
                workoutType={draft.workoutType}
                disabled={working}
                compatibility={compatibility}
                compatibilityLoading={compatibilityLoading}
                compatibilityError={compatibilityError}
                onChange={(structure) => {
                  setLocalError(null);
                  setDraft((current) => ({ ...current, structure }));
                }}
              />
            )}

            <div className="py-5">
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
                className="mt-1.5 flex w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50"
                placeholder={t`Optional session-level notes`}
              />
            </div>

            {dialogError && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{dialogError}</AlertDescription>
              </Alert>
            )}

            <div className="sticky bottom-0 flex flex-col-reverse gap-3 border-t border-border bg-background py-4 sm:flex-row sm:items-center sm:justify-between">
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
                {editing
                  && draft.mode !== 'unsupported'
                  && !isRestWorkoutType(workout.workout_type)
                  && (
                  <Button
                    type="button"
                    variant="outline"
                    disabled={working}
                    onClick={convertToRest}
                  >
                    <Moon aria-hidden="true" />
                    <Trans>Convert to rest</Trans>
                  </Button>
                  )}
                {forking && (
                  <span className="inline-flex items-center gap-1.5 self-center text-xs text-muted-foreground">
                    <GitFork className="h-3.5 w-3.5 text-accent-cobalt" aria-hidden="true" />
                    <Trans>Source stays unchanged</Trans>
                  </span>
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
                <Button
                  type="submit"
                  disabled={
                    working || draftErrors.length > 0 || unsupportedFork
                  }
                >
                  {working
                    ? <Trans>Saving…</Trans>
                    : forking
                      ? <Trans>Duplicate workout</Trans>
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

function LegacyFields({
  draft,
  disabled,
  onChange,
}: {
  draft: WorkoutDraft;
  disabled: boolean;
  onChange: React.Dispatch<React.SetStateAction<WorkoutDraft>>;
}) {
  const { t } = useLingui();
  const numberFields: Array<{
    id: string;
    label: string;
    field: keyof Pick<
      WorkoutDraft,
      'duration' | 'distance' | 'powerMin' | 'powerMax' | 'hrMin' | 'hrMax'
    >;
    min: string;
    max: string;
    step?: string;
  }> = [
    {
      id: 'plan-workout-duration',
      label: t`Duration (minutes)`,
      field: 'duration',
      min: '0',
      max: '1440',
      step: 'any',
    },
    {
      id: 'plan-workout-distance',
      label: t`Distance (km)`,
      field: 'distance',
      min: '0',
      max: '1000',
      step: '0.1',
    },
    {
      id: 'plan-workout-power-min',
      label: t`Power floor (W)`,
      field: 'powerMin',
      min: '0',
      max: '5000',
    },
    {
      id: 'plan-workout-power-max',
      label: t`Power ceiling (W)`,
      field: 'powerMax',
      min: '0',
      max: '5000',
    },
    {
      id: 'plan-workout-hr-min',
      label: t`Heart-rate minimum (bpm)`,
      field: 'hrMin',
      min: '0',
      max: '300',
    },
    {
      id: 'plan-workout-hr-max',
      label: t`Heart-rate maximum (bpm)`,
      field: 'hrMax',
      min: '0',
      max: '300',
    },
  ];
  return (
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      {numberFields.map((field) => (
        <div key={field.id} className="space-y-1.5">
          <Label htmlFor={field.id}>{field.label}</Label>
          <Input
            id={field.id}
            type="number"
            min={field.min}
            max={field.max}
            step={field.step}
            inputMode="decimal"
            value={draft[field.field]}
            disabled={disabled}
            onChange={(event) => onChange((current) => ({
              ...current,
              [field.field]: event.target.value,
            }))}
            className="font-data"
            placeholder={t`Optional`}
          />
        </div>
      ))}
      <div className="space-y-1.5">
        <Label htmlFor="plan-workout-pace-min">
          <Trans>Pace minimum (min/km)</Trans>
        </Label>
        <Input
          id="plan-workout-pace-min"
          maxLength={20}
          value={draft.paceMin}
          disabled={disabled}
          onChange={(event) => onChange((current) => ({
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
          disabled={disabled}
          onChange={(event) => onChange((current) => ({
            ...current,
            paceMax: event.target.value,
          }))}
          className="font-data"
          placeholder={t`e.g. 5:45`}
        />
      </div>
    </div>
  );
}
