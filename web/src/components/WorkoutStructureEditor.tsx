import { useMemo, useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import {
  ArrowDown,
  ArrowUp,
  Copy,
  ListPlus,
  Plus,
  Repeat2,
  RotateCcw,
  Trash2,
} from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  commitWorkoutEditorTargetInput,
  createWorkoutEditorRepeat,
  createWorkoutEditorStep,
  createRepeatGroup,
  createStructuredStep,
  duplicateWorkoutEditorNode,
  formatDeterministicDistance,
  formatDeterministicDuration,
  insertWorkoutEditorNode,
  moveWorkoutEditorNode,
  removeWorkoutEditorNode,
  restoreRemovedWorkoutEditorNode,
  setWorkoutEditorTargetInput,
  summarizeWorkoutStructure,
  targetForKind,
  targetKind,
  updateWorkoutEditorRepeat,
  updateWorkoutEditorStep,
  validateWorkoutEditorStructure,
  type RemovedWorkoutEditorNode,
  type WorkoutEditorRepeat,
  type WorkoutEditorStep,
  type WorkoutEditorStructureV1,
  type WorkoutTargetKind,
} from '@/lib/workout-structure';
import type {
  WorkoutProviderCompatibility,
  WorkoutProviderCompatibilityReasonCode,
  WorkoutStructureStep,
  WorkoutTermination,
} from '@/types/api';

const PHASES = [
  'warmup',
  'work',
  'recovery',
  'rest',
  'cooldown',
  'other',
] as const;

const TARGET_KINDS: WorkoutTargetKind[] = [
  'none',
  'power_watts',
  'power_cp',
  'heart_rate_bpm',
  'heart_rate_lthr',
  'pace_absolute',
  'pace_threshold',
  'rpe',
];

const TARGET_BOUNDS: Record<
  Exclude<WorkoutTargetKind, 'none'>,
  { min: number; max: number; label: string }
> = {
  power_watts: { min: 0, max: 5000, label: 'W' },
  power_cp: { min: 0, max: 300, label: '%CP' },
  heart_rate_bpm: { min: 0, max: 300, label: 'bpm' },
  heart_rate_lthr: { min: 0, max: 200, label: '%LTHR' },
  pace_absolute: { min: 0, max: 7200, label: 'sec/km' },
  pace_threshold: { min: -7200, max: 7200, label: 'sec/km Δ' },
  rpe: { min: 0, max: 10, label: 'RPE' },
};

function terminationForType(
  termination: WorkoutTermination,
  type: WorkoutTermination['type'],
): WorkoutTermination {
  if (type === 'time') {
    return {
      type,
      seconds: termination.type === 'time'
        ? termination.seconds
        : 60,
    };
  }
  if (type === 'distance') {
    return {
      type,
      meters: termination.type === 'distance'
        ? termination.meters
        : 1000,
    };
  }
  return { type };
}

export default function WorkoutStructureEditor({
  structure,
  workoutType,
  disabled,
  compatibility,
  compatibilityLoading,
  compatibilityError,
  onChange,
}: {
  structure: WorkoutEditorStructureV1;
  workoutType: string;
  disabled: boolean;
  compatibility: WorkoutProviderCompatibility[] | null;
  compatibilityLoading: boolean;
  compatibilityError: string | null;
  onChange: (structure: WorkoutEditorStructureV1) => void;
}) {
  const { t } = useLingui();
  const [lastRemoved, setLastRemoved] = useState<
    RemovedWorkoutEditorNode | null
  >(
    null,
  );
  const summary = useMemo(
    () => summarizeWorkoutStructure(structure),
    [structure],
  );
  const validationErrors = useMemo(
    () => validateWorkoutEditorStructure(structure, workoutType),
    [structure, workoutType],
  );
  const validationMessage = validationErrors.length > 0
    ? t`Review the highlighted step fields. Every typed target and termination must be complete.`
    : null;
  const phaseLabels: Record<WorkoutStructureStep['phase'], string> = {
    warmup: t`Warm-up`,
    work: t`Work`,
    recovery: t`Recovery`,
    rest: t`Rest`,
    cooldown: t`Cool-down`,
    other: t`Other`,
  };
  const targetLabels: Record<WorkoutTargetKind, string> = {
    none: t`No target`,
    power_watts: t`Power · watts`,
    power_cp: t`Power · %CP`,
    heart_rate_bpm: t`Heart rate · bpm`,
    heart_rate_lthr: t`Heart rate · %LTHR`,
    pace_absolute: t`Pace · sec/km`,
    pace_threshold: t`Pace · threshold delta`,
    rpe: t`RPE · 0–10`,
  };
  const targetDetailLabels: Record<WorkoutTargetKind, string> = {
    none: t`No unit or reference`,
    power_watts: t`Unit: watts · Reference: absolute`,
    power_cp: t`Unit: %CP · Reference: critical power`,
    heart_rate_bpm: t`Unit: bpm · Reference: absolute`,
    heart_rate_lthr: t`Unit: %LTHR · Reference: LTHR`,
    pace_absolute: t`Unit: sec/km · Reference: absolute`,
    pace_threshold: t`Unit: sec/km delta · Reference: threshold pace`,
    rpe: t`Unit: 10-point scale · Reference: perceived exertion`,
  };
  const reasonLabels: Record<
    WorkoutProviderCompatibilityReasonCode,
    string
  > = {
    activity_type_not_supported: t`This activity is not supported by the provider.`,
    duration_required: t`A positive duration is required by the provider.`,
    empty_structure_not_supported: t`An empty structured workout cannot be sent.`,
    flat_workout_not_lossless: t`This legacy flat workout would need a time duration and a power range to avoid provider defaults.`,
    invalid_structure: t`The workout structure is not a supported portable version.`,
    phase_not_supported: t`This step semantic cannot be represented safely.`,
    structured_workout_not_supported: t`Structured workouts are not supported by this provider.`,
    target_not_supported: t`This typed target cannot be represented safely.`,
    target_precision_not_supported: t`Stryd accepts only whole-number %CP bounds; fractional values would be rounded.`,
    termination_not_supported: t`This step termination cannot be represented safely.`,
    wording_not_supported: t`Step or repeat wording cannot be preserved safely.`,
  };

  const commitStructure = (next: WorkoutEditorStructureV1) => {
    setLastRemoved(null);
    onChange(next);
  };

  const updateStep = (
    editorId: string,
    update: Partial<WorkoutStructureStep>,
  ) => commitStructure(updateWorkoutEditorStep(structure, editorId, update));

  const updateRepeat = (
    editorId: string,
    update: Partial<Omit<WorkoutEditorRepeat, 'editorId'>>,
  ) => commitStructure(updateWorkoutEditorRepeat(structure, editorId, update));

  const removeNode = (editorId: string) => {
    const result = removeWorkoutEditorNode(structure, editorId);
    if (!result.removed) return;
    onChange(result.structure);
    setLastRemoved(result.removed);
  };

  const restoreNode = () => {
    if (!lastRemoved) return;
    onChange(restoreRemovedWorkoutEditorNode(structure, lastRemoved));
    setLastRemoved(null);
  };

  const addRoot = (kind: 'step' | 'repeat') => {
    commitStructure({
      steps: [
        ...structure.steps,
        kind === 'step'
          ? createWorkoutEditorStep()
          : createWorkoutEditorRepeat(),
      ],
    });
  };

  const addRepeatChild = (editorId: string) => {
    const repeat = structure.steps.find((node) => node.editorId === editorId);
    if (!repeat || repeat.type !== 'repeat') return;
    updateRepeat(editorId, {
      steps: [...repeat.steps, createWorkoutEditorStep()],
    });
  };

  const updateTargetInput = (
    editorId: string,
    bound: 'min' | 'max',
    value: string,
  ) => commitStructure(setWorkoutEditorTargetInput(
    structure,
    editorId,
    bound,
    value,
  ));

  const commitTargetInput = (
    editorId: string,
    bound: 'min' | 'max',
  ) => commitStructure(commitWorkoutEditorTargetInput(
    structure,
    editorId,
    bound,
  ).structure);

  return (
    <section className="border-y border-border py-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            <Trans>Structured steps</Trans>
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted-foreground">
            <Trans>
              Semantics describe the portable step. Labels and instructions
              preserve your own wording; Praxys never infers a warm-up,
              cool-down, or repeat from it.
            </Trans>
          </p>
        </div>
        <span className="font-data text-xs text-muted-foreground">
          {summary.executableSteps} {summary.executableSteps === 1
            ? t`step`
            : t`steps`}
        </span>
      </div>

      <div className="mt-4 grid gap-2 border-y border-border py-3 sm:grid-cols-3">
        <ProfileItem
          label={t`Duration`}
          value={summary.duration.certainty === 'deterministic'
            ? formatDeterministicDuration(summary.duration.seconds)
            : t`Unknown`}
          certainty={summary.duration.certainty}
        />
        <ProfileItem
          label={t`Distance`}
          value={summary.distance.certainty === 'deterministic'
            ? formatDeterministicDistance(summary.distance.meters)
            : t`Unknown`}
          certainty={summary.distance.certainty}
        />
        <ProfileItem
          label={t`Load`}
          value={summary.load.certainty === 'estimated'
            ? t`Estimated from targets`
            : t`Unknown`}
          certainty={summary.load.certainty}
        />
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
        <Trans>
          Totals are deterministic only when every repeated step has the same
          measurable termination. Praxys does not invent a training-load score
          here.
        </Trans>
      </p>

      {validationMessage && (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription className="text-xs">
            {validationMessage}
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-5 space-y-3" role="tree" aria-label={t`Workout steps`}>
        {structure.steps.map((node, rootIndex) => (
          node.type === 'step' ? (
            <StepEditor
              key={node.editorId}
              step={node}
              index={rootIndex}
              siblingCount={structure.steps.length}
              disabled={disabled}
              phaseLabels={phaseLabels}
              targetLabels={targetLabels}
              targetDetailLabels={targetDetailLabels}
              onUpdate={updateStep}
              onMove={(direction) => commitStructure(
                moveWorkoutEditorNode(structure, node.editorId, direction),
              )}
              onInsert={(position) => commitStructure(
                insertWorkoutEditorNode(
                  structure,
                  node.editorId,
                  createStructuredStep(),
                  position,
                ),
              )}
              onDuplicate={() => commitStructure(
                duplicateWorkoutEditorNode(structure, node.editorId),
              )}
              onDelete={() => removeNode(node.editorId)}
              onTargetInput={updateTargetInput}
              onTargetBlur={commitTargetInput}
            />
          ) : (
            <RepeatEditor
              key={node.editorId}
              repeat={node}
              rootIndex={rootIndex}
              rootCount={structure.steps.length}
              disabled={disabled}
              phaseLabels={phaseLabels}
              targetLabels={targetLabels}
              targetDetailLabels={targetDetailLabels}
              onUpdate={(update) => updateRepeat(node.editorId, update)}
              onMove={(direction) => commitStructure(
                moveWorkoutEditorNode(structure, node.editorId, direction),
              )}
              onInsert={(position) => commitStructure(
                insertWorkoutEditorNode(
                  structure,
                  node.editorId,
                  createRepeatGroup(),
                  position,
                ),
              )}
              onDuplicate={() => commitStructure(
                duplicateWorkoutEditorNode(structure, node.editorId),
              )}
              onDelete={() => removeNode(node.editorId)}
              onAddChild={() => addRepeatChild(node.editorId)}
              onUpdateChild={updateStep}
              onMoveChild={(childEditorId, direction) => commitStructure(
                moveWorkoutEditorNode(
                  structure,
                  childEditorId,
                  direction,
                ),
              )}
              onInsertChild={(childEditorId, position) => commitStructure(
                insertWorkoutEditorNode(
                  structure,
                  childEditorId,
                  createStructuredStep(),
                  position,
                ),
              )}
              onDuplicateChild={(childEditorId) => commitStructure(
                duplicateWorkoutEditorNode(structure, childEditorId),
              )}
              onDeleteChild={removeNode}
              onTargetInput={updateTargetInput}
              onTargetBlur={commitTargetInput}
            />
          )
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => addRoot('step')}
        >
          <Plus aria-hidden="true" />
          <Trans>Add step</Trans>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => addRoot('repeat')}
        >
          <Repeat2 aria-hidden="true" />
          <Trans>Add repeat</Trans>
        </Button>
      </div>

      {lastRemoved && (
        <Alert className="mt-4 border-accent-cobalt/25 bg-accent-cobalt/5">
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-xs text-foreground">
            <span><Trans>Step removed. You can restore it before saving.</Trans></span>
            <Button
              type="button"
              variant="link"
              size="sm"
              disabled={disabled}
              onClick={restoreNode}
              className="h-auto px-0 text-accent-cobalt"
            >
              <RotateCcw aria-hidden="true" />
              <Trans>Undo</Trans>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <ProviderCompatibilitySummary
        compatibility={compatibility}
        loading={compatibilityLoading}
        error={compatibilityError}
        reasonLabels={reasonLabels}
      />
    </section>
  );
}

function ProfileItem({
  label,
  value,
  certainty,
}: {
  label: string;
  value: string;
  certainty: 'deterministic' | 'estimated' | 'unknown';
}) {
  const { t } = useLingui();
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-2">
      <span className="text-[11px] font-medium text-muted-foreground">
        {label}
      </span>
      <span className="text-right text-xs text-foreground">
        <span className="font-data">{value}</span>
        <span className="ml-1 text-[10px] text-muted-foreground">
          {certainty === 'deterministic'
            ? t`deterministic`
            : certainty === 'estimated'
              ? t`estimated`
              : t`unknown`}
        </span>
      </span>
    </div>
  );
}

function StepEditor({
  step,
  index,
  siblingCount,
  disabled,
  phaseLabels,
  targetLabels,
  targetDetailLabels,
  onUpdate,
  onMove,
  onInsert,
  onDuplicate,
  onDelete,
  onTargetInput,
  onTargetBlur,
}: {
  step: WorkoutEditorStep;
  index: number;
  siblingCount: number;
  disabled: boolean;
  phaseLabels: Record<WorkoutStructureStep['phase'], string>;
  targetLabels: Record<WorkoutTargetKind, string>;
  targetDetailLabels: Record<WorkoutTargetKind, string>;
  onUpdate: (
    editorId: string,
    update: Partial<WorkoutStructureStep>,
  ) => void;
  onMove: (direction: 'up' | 'down') => void;
  onInsert: (position: 'before' | 'after') => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onTargetInput: (
    editorId: string,
    bound: 'min' | 'max',
    value: string,
  ) => void;
  onTargetBlur: (
    editorId: string,
    bound: 'min' | 'max',
  ) => void;
}) {
  const { t } = useLingui();
  const kind = targetKind(step.target);
  const prefix = `workout-step-${step.editorId}`;
  const bounds = kind === 'none' ? null : TARGET_BOUNDS[kind];
  return (
    <div className="border-y border-border py-4" role="treeitem">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-foreground">
          <Trans>Step</Trans> <span className="font-data">{index + 1}</span>
        </p>
        <NodeActions
          disabled={disabled}
          canMoveUp={index > 0}
          canMoveDown={index < siblingCount - 1}
          onMove={onMove}
          onInsert={onInsert}
          onDuplicate={onDuplicate}
          onDelete={onDelete}
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-phase`}><Trans>Step semantic</Trans></Label>
          <Select
            value={step.phase}
            disabled={disabled}
            onValueChange={(value) => {
              if (!value) return;
              onUpdate(step.editorId, {
                phase: value as WorkoutStructureStep['phase'],
              });
            }}
          >
            <SelectTrigger id={`${prefix}-phase`} className="w-full"><SelectValue>{phaseLabels[step.phase]}</SelectValue></SelectTrigger>
            <SelectContent>
              {PHASES.map((phase) => (
                <SelectItem key={phase} value={phase}>
                  {phaseLabels[phase]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-label`}><Trans>Optional label</Trans></Label>
          <Input
            id={`${prefix}-label`}
            value={step.label ?? ''}
            maxLength={80}
            disabled={disabled}
            onChange={(event) => onUpdate(step.editorId, {
              label: event.target.value || null,
            })}
            placeholder={t`e.g. Uphill effort`}
          />
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <TerminationFields
          idPrefix={prefix}
          termination={step.termination}
          disabled={disabled}
          onChange={(termination) => onUpdate(step.editorId, { termination })}
        />
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-target`}><Trans>Target type</Trans></Label>
          <Select
            value={kind}
            disabled={disabled}
            onValueChange={(value) => {
              if (!value) return;
              onUpdate(step.editorId, {
                target: targetForKind(value as WorkoutTargetKind),
              });
            }}
          >
            <SelectTrigger id={`${prefix}-target`} className="w-full"><SelectValue>{targetLabels[kind]}</SelectValue></SelectTrigger>
            <SelectContent>
              {TARGET_KINDS.map((targetKindValue) => (
                <SelectItem key={targetKindValue} value={targetKindValue}>
                  {targetLabels[targetKindValue]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {targetDetailLabels[kind]}
            {bounds && (
              <>
                {' · '}
                <Trans>Allowed range</Trans>: <span className="font-data">{bounds.min}–{bounds.max} {bounds.label}</span>
              </>
            )}
          </p>
        </div>
      </div>

      {step.target.metric !== 'none' && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={`${prefix}-target-min`}><Trans>Target minimum</Trans></Label>
            <Input
              id={`${prefix}-target-min`}
              type="text"
              inputMode={bounds && bounds.min < 0 ? 'text' : 'decimal'}
              min={bounds?.min}
              max={bounds?.max}
              value={step.targetInputs.min}
              disabled={disabled}
              aria-invalid={step.targetInputs.minInvalid || undefined}
              onChange={(event) => onTargetInput(
                step.editorId,
                'min',
                event.target.value,
              )}
              onBlur={() => onTargetBlur(step.editorId, 'min')}
              className="font-data"
              placeholder={t`Optional`}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`${prefix}-target-max`}><Trans>Target maximum</Trans></Label>
            <Input
              id={`${prefix}-target-max`}
              type="text"
              inputMode={bounds && bounds.min < 0 ? 'text' : 'decimal'}
              min={bounds?.min}
              max={bounds?.max}
              value={step.targetInputs.max}
              disabled={disabled}
              aria-invalid={step.targetInputs.maxInvalid || undefined}
              onChange={(event) => onTargetInput(
                step.editorId,
                'max',
                event.target.value,
              )}
              onBlur={() => onTargetBlur(step.editorId, 'max')}
              className="font-data"
              placeholder={t`Optional`}
            />
          </div>
        </div>
      )}

      <div className="mt-3 space-y-1.5">
        <Label htmlFor={`${prefix}-instructions`}><Trans>Step instructions</Trans></Label>
        <textarea
          id={`${prefix}-instructions`}
          value={step.instructions ?? ''}
          disabled={disabled}
          maxLength={1000}
          rows={2}
          onChange={(event) => onUpdate(step.editorId, {
            instructions: event.target.value || null,
          })}
          className="flex w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50"
          placeholder={t`Optional coaching cue`}
        />
      </div>
    </div>
  );
}

function RepeatEditor({
  repeat,
  rootIndex,
  rootCount,
  disabled,
  phaseLabels,
  targetLabels,
  targetDetailLabels,
  onUpdate,
  onMove,
  onInsert,
  onDuplicate,
  onDelete,
  onAddChild,
  onUpdateChild,
  onMoveChild,
  onInsertChild,
  onDuplicateChild,
  onDeleteChild,
  onTargetInput,
  onTargetBlur,
}: {
  repeat: WorkoutEditorRepeat;
  rootIndex: number;
  rootCount: number;
  disabled: boolean;
  phaseLabels: Record<WorkoutStructureStep['phase'], string>;
  targetLabels: Record<WorkoutTargetKind, string>;
  targetDetailLabels: Record<WorkoutTargetKind, string>;
  onUpdate: (
    update: Partial<Omit<WorkoutEditorRepeat, 'editorId'>>
  ) => void;
  onMove: (direction: 'up' | 'down') => void;
  onInsert: (position: 'before' | 'after') => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onAddChild: () => void;
  onUpdateChild: (
    childEditorId: string,
    update: Partial<WorkoutStructureStep>,
  ) => void;
  onMoveChild: (childEditorId: string, direction: 'up' | 'down') => void;
  onInsertChild: (
    childEditorId: string,
    position: 'before' | 'after',
  ) => void;
  onDuplicateChild: (childEditorId: string) => void;
  onDeleteChild: (childEditorId: string) => void;
  onTargetInput: (
    editorId: string,
    bound: 'min' | 'max',
    value: string,
  ) => void;
  onTargetBlur: (
    editorId: string,
    bound: 'min' | 'max',
  ) => void;
}) {
  const { t } = useLingui();
  const prefix = `workout-repeat-${repeat.editorId}`;
  return (
    <div className="border-y border-border bg-muted/25 py-4 pl-3" role="treeitem">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
          <Repeat2 className="h-3.5 w-3.5 text-accent-cobalt" aria-hidden="true" />
          <Trans>Repeat group</Trans>
        </p>
        <NodeActions
          disabled={disabled}
          canMoveUp={rootIndex > 0}
          canMoveDown={rootIndex < rootCount - 1}
          onMove={onMove}
          onInsert={onInsert}
          onDuplicate={onDuplicate}
          onDelete={onDelete}
        />
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-label`}><Trans>Repeat label</Trans></Label>
          <Input
            id={`${prefix}-label`}
            value={repeat.label ?? ''}
            disabled={disabled}
            maxLength={80}
            onChange={(event) => onUpdate({
              label: event.target.value || null,
            })}
            placeholder={t`e.g. Main set`}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-repetitions`}><Trans>Repetitions</Trans></Label>
          <Input
            id={`${prefix}-repetitions`}
            type="number"
            inputMode="numeric"
            min="1"
            max="100"
            value={repeat.repetitions}
            disabled={disabled}
            onChange={(event) => {
              const repetitions = Number(event.target.value);
              onUpdate({
                repetitions: Number.isInteger(repetitions)
                  ? repetitions
                  : repeat.repetitions,
              });
            }}
            className="font-data"
          />
        </div>
      </div>

      <div className="mt-4 border-l border-border pl-3">
        <p className="text-[11px] font-medium text-muted-foreground">
          <Trans>Repeat children</Trans>
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          <Trans>
            Portable v1 permits one repeat level. Add atomic steps here, not
            another repeat.
          </Trans>
        </p>
        <div className="mt-2 space-y-3">
          {repeat.steps.map((step, childIndex) => (
            <StepEditor
              key={step.editorId}
              step={step}
              index={childIndex}
              siblingCount={repeat.steps.length}
              disabled={disabled}
              phaseLabels={phaseLabels}
              targetLabels={targetLabels}
              targetDetailLabels={targetDetailLabels}
              onUpdate={onUpdateChild}
              onMove={(direction) => onMoveChild(step.editorId, direction)}
              onInsert={(position) => onInsertChild(step.editorId, position)}
              onDuplicate={() => onDuplicateChild(step.editorId)}
              onDelete={() => onDeleteChild(step.editorId)}
              onTargetInput={onTargetInput}
              onTargetBlur={onTargetBlur}
            />
          ))}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={onAddChild}
          className="mt-3"
        >
          <Plus aria-hidden="true" />
          <Trans>Add repeat step</Trans>
        </Button>
      </div>
    </div>
  );
}

function TerminationFields({
  idPrefix,
  termination,
  disabled,
  onChange,
}: {
  idPrefix: string;
  termination: WorkoutTermination;
  disabled: boolean;
  onChange: (termination: WorkoutTermination) => void;
}) {
  const { t } = useLingui();
  const terminationLabels: Record<WorkoutTermination['type'], string> = {
    time: t`Time`,
    distance: t`Distance`,
    open: t`Open`,
    manual: t`Manual`,
  };
  return (
    <div className="space-y-1.5">
      <Label htmlFor={`${idPrefix}-termination`}><Trans>Termination</Trans></Label>
      <Select
        value={termination.type}
        disabled={disabled}
        onValueChange={(value) => {
          if (!value) return;
          onChange(terminationForType(
            termination,
            value as WorkoutTermination['type'],
          ));
        }}
      >
        <SelectTrigger id={`${idPrefix}-termination`} className="w-full"><SelectValue>{terminationLabels[termination.type]}</SelectValue></SelectTrigger>
        <SelectContent>
          <SelectItem value="time"><Trans>Time</Trans></SelectItem>
          <SelectItem value="distance"><Trans>Distance</Trans></SelectItem>
          <SelectItem value="open"><Trans>Open</Trans></SelectItem>
          <SelectItem value="manual"><Trans>Manual</Trans></SelectItem>
        </SelectContent>
      </Select>
      {termination.type === 'time' && (
        <Input
          id={`${idPrefix}-seconds`}
          className="font-data"
          type="number"
          min="1"
          max="86400"
          inputMode="numeric"
          value={termination.seconds}
          disabled={disabled}
          aria-label={t`Time in seconds`}
          onChange={(event) => {
            const seconds = Number(event.target.value);
            if (!Number.isInteger(seconds)) return;
            onChange({ type: 'time', seconds });
          }}
        />
      )}
      {termination.type === 'distance' && (
        <Input
          id={`${idPrefix}-meters`}
          className="font-data"
          type="number"
          min="1"
          max="1000000"
          inputMode="numeric"
          value={termination.meters}
          disabled={disabled}
          aria-label={t`Distance in meters`}
          onChange={(event) => {
            const meters = Number(event.target.value);
            if (!Number.isInteger(meters)) return;
            onChange({ type: 'distance', meters });
          }}
        />
      )}
    </div>
  );
}

function NodeActions({
  disabled,
  canMoveUp,
  canMoveDown,
  onMove,
  onInsert,
  onDuplicate,
  onDelete,
}: {
  disabled: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMove: (direction: 'up' | 'down') => void;
  onInsert: (position: 'before' | 'after') => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const { t } = useLingui();
  return (
    <div className="flex flex-wrap items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={disabled || !canMoveUp}
        onClick={() => onMove('up')}
        aria-label={t`Move step up`}
      >
        <ArrowUp aria-hidden="true" />
        <span className="sr-only"><Trans>Move up</Trans></span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={disabled || !canMoveDown}
        onClick={() => onMove('down')}
        aria-label={t`Move step down`}
      >
        <ArrowDown aria-hidden="true" />
        <span className="sr-only"><Trans>Move down</Trans></span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={disabled}
        onClick={() => onInsert('before')}
      >
        <ListPlus aria-hidden="true" />
        <span className="sr-only"><Trans>Insert before</Trans></span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={disabled}
        onClick={() => onInsert('after')}
      >
        <Plus aria-hidden="true" />
        <span className="sr-only"><Trans>Insert after</Trans></span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={disabled}
        onClick={onDuplicate}
      >
        <Copy aria-hidden="true" />
        <span className="sr-only"><Trans>Duplicate</Trans></span>
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="xs"
        disabled={disabled}
        onClick={onDelete}
        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
      >
        <Trash2 aria-hidden="true" />
        <span className="sr-only"><Trans>Delete</Trans></span>
      </Button>
    </div>
  );
}

function ProviderCompatibilitySummary({
  compatibility,
  loading,
  error,
  reasonLabels,
}: {
  compatibility: WorkoutProviderCompatibility[] | null;
  loading: boolean;
  error: string | null;
  reasonLabels: Record<WorkoutProviderCompatibilityReasonCode, string>;
}) {
  const { t } = useLingui();
  return (
    <div className="mt-5 border-t border-border pt-4">
      <h3 className="text-sm font-semibold text-foreground">
        <Trans>Provider compatibility</Trans>
      </h3>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        <Trans>
          This checks portable workout content only. It never connects to a
          provider or delivers a workout.
        </Trans>
      </p>
      {loading && (
        <p className="mt-3 text-xs text-accent-cobalt">
          <Trans>Checking provider compatibility…</Trans>
        </p>
      )}
      {error && (
        <Alert className="mt-3 border-accent-amber/30 bg-accent-amber/8">
          <AlertDescription className="text-xs text-foreground">
            {error}
          </AlertDescription>
        </Alert>
      )}
      {!loading && !error && !compatibility && (
        <p className="mt-3 text-xs text-muted-foreground">
          <Trans>Finish the required step fields to preview compatibility.</Trans>
        </p>
      )}
      {compatibility && (
        <div className="mt-3 divide-y divide-border border-y border-border">
          {compatibility.map((provider) => (
            <div key={provider.target} className="py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-xs font-semibold text-foreground">
                  {provider.target === 'garmin' ? 'Garmin' : 'Stryd'}
                </p>
                <span className={
                  provider.compatible
                    ? 'text-xs font-medium text-primary'
                    : 'text-xs font-medium text-accent-amber'
                }
                >
                  {provider.compatible
                    ? t`Compatible`
                    : t`Not safely representable`}
                </span>
              </div>
              {provider.compatible ? (
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  {provider.mode === 'structured'
                    ? t`This portable structure can be represented without flattening.`
                    : t`This legacy flat workout has no portable tree to flatten.`}
                </p>
              ) : (
                <ul className="mt-1 space-y-1 text-[11px] leading-relaxed text-muted-foreground">
                  {provider.reasons.map((reason) => (
                    <li key={`${reason.code}-${reason.path ?? ''}`}>
                      {reasonLabels[reason.code]}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
