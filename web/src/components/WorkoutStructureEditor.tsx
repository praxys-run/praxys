import { useMemo, useState, type ComponentType } from 'react';
import { msg } from '@lingui/core/macro';
import type { I18n, MessageDescriptor } from '@lingui/core';
import { Trans, useLingui } from '@lingui/react/macro';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Check,
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
import { RangeSlider } from '@/components/ui/slider';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  commitWorkoutEditorTargetInput,
  createWorkoutEditorRepeat,
  createWorkoutEditorStep,
  createRepeatGroup,
  createStructuredStep,
  duplicateWorkoutEditorNode,
  formatDeterministicDistance,
  formatDeterministicDuration,
  formatWorkoutDistanceInput,
  insertWorkoutEditorNode,
  moveWorkoutEditorNode,
  parseWorkoutDistanceInput,
  parseWorkoutPaceInput,
  removeWorkoutEditorNode,
  restoreRemovedWorkoutEditorNode,
  setWorkoutEditorTargetInput,
  summarizeWorkoutStructure,
  targetForKind,
  targetKind,
  updateWorkoutEditorRepeat,
  updateWorkoutEditorStep,
  validateWorkoutEditorStructure,
  workoutEditorIdForCompatibilityPath,
  workoutEditorNodePath,
  type RemovedWorkoutEditorNode,
  type WorkoutEditorNode,
  type WorkoutEditorRepeat,
  type WorkoutEditorStep,
  type WorkoutEditorStructureV1,
  type WorkoutTargetKind,
} from '@/lib/workout-structure';
import { cn } from '@/lib/utils';
import type {
  UnitSystem,
  WorkoutProviderCompatibility,
  WorkoutProviderCompatibilityReason,
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

const SLIDER_TARGETS: Partial<Record<
  WorkoutTargetKind,
  { min: number; max: number; step: number }
>> = {
  power_cp: { min: 0, max: 300, step: 1 },
  heart_rate_lthr: { min: 0, max: 200, step: 1 },
  rpe: { min: 0, max: 10, step: 0.5 },
};

const TARGET_DESCRIPTION_MESSAGES: Record<
  Exclude<WorkoutTargetKind, 'pace_absolute' | 'pace_threshold'>,
  MessageDescriptor
> = {
  none: msg`No unit or reference`,
  power_watts: msg`Absolute running power in watts.`,
  power_cp: msg`Percentage of the athlete's current critical power.`,
  heart_rate_bpm: msg`Absolute heart rate in beats per minute.`,
  heart_rate_lthr: msg`Percentage of the athlete's lactate-threshold heart rate.`,
  rpe: msg`Perceived exertion on a 0–10 scale.`,
};

const PACE_DESCRIPTION_MESSAGES = {
  absolute: {
    metric: msg`Enter pace as minutes:seconds per kilometre.`,
    imperial: msg`Enter pace as minutes:seconds per mile.`,
  },
  threshold: {
    metric: msg`Seconds per kilometre faster or slower than threshold pace.`,
    imperial: msg`Seconds per mile faster or slower than threshold pace.`,
  },
} satisfies Record<
  'absolute' | 'threshold',
  Record<UnitSystem, MessageDescriptor>
>;

const COMPATIBILITY_FIELD_MESSAGES = {
  semantic: msg`semantic`,
  termination: msg`termination`,
  target: msg`target`,
  label: msg`label`,
  instructions: msg`instructions`,
} satisfies Record<string, MessageDescriptor>;

interface OutlineItem {
  editorId: string;
  order: string;
  title: string;
  detail: string;
  depth: 0 | 1;
  type: 'step' | 'repeat';
  phase: WorkoutStructureStep['phase'] | null;
  invalid: boolean;
}

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

function editorNode(
  structure: WorkoutEditorStructureV1,
  editorId: string | null,
): WorkoutEditorNode | null {
  if (!editorId) return null;
  const path = workoutEditorNodePath(structure, editorId);
  if (!path) return null;
  const root = structure.steps[path[0]];
  return path.length === 1
    ? root ?? null
    : root?.type === 'repeat'
      ? root.steps[path[1]] ?? null
      : null;
}

function editorIds(structure: WorkoutEditorStructureV1): string[] {
  return structure.steps.flatMap((node) => (
    node.type === 'step'
      ? [node.editorId]
      : [node.editorId, ...node.steps.map((step) => step.editorId)]
  ));
}

function addedEditorId(
  before: WorkoutEditorStructureV1,
  after: WorkoutEditorStructureV1,
): string | null {
  const existing = new Set(editorIds(before));
  return editorIds(after).find((editorId) => !existing.has(editorId)) ?? null;
}

function parsedTargetDraft(
  raw: string,
  kind: WorkoutTargetKind,
  unitSystem: UnitSystem,
): number | undefined | null {
  const value = raw.trim();
  if (!value) return undefined;
  if (kind === 'pace_absolute') {
    return parseWorkoutPaceInput(value, unitSystem);
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  if (kind === 'pace_threshold' && unitSystem === 'imperial') {
    return parsed / 1.609344;
  }
  return parsed;
}

function stepIsInvalid(
  step: WorkoutEditorStep,
  unitSystem: UnitSystem,
): boolean {
  if (step.targetInputs.minInvalid || step.targetInputs.maxInvalid) return true;
  if (
    step.termination.type === 'time'
    && (!Number.isInteger(step.termination.seconds)
      || step.termination.seconds < 1
      || step.termination.seconds > 86_400)
  ) return true;
  if (
    step.termination.type === 'distance'
    && (!Number.isInteger(step.termination.meters)
      || step.termination.meters < 1
      || step.termination.meters > 1_000_000)
  ) return true;
  const kind = targetKind(step.target);
  if (kind === 'none') return false;
  const minimum = parsedTargetDraft(step.targetInputs.min, kind, unitSystem);
  const maximum = parsedTargetDraft(step.targetInputs.max, kind, unitSystem);
  if (minimum === null || maximum === null) return true;
  if (minimum === undefined && maximum === undefined) return true;
  if (
    minimum !== undefined
    && maximum !== undefined
    && minimum > maximum
  ) return true;
  const bounds = TARGET_BOUNDS[kind];
  return [minimum, maximum].some((value) => (
    value !== undefined && (value < bounds.min || value > bounds.max)
  ));
}

function phaseTone(phase: WorkoutStructureStep['phase']): string {
  if (phase === 'warmup' || phase === 'cooldown') {
    return 'border-border bg-muted/35';
  }
  if (phase === 'work') {
    return 'border-primary/40 bg-primary/8';
  }
  if (phase === 'rest') {
    return 'border-dashed border-border bg-card';
  }
  if (phase === 'recovery') {
    return 'border-border bg-muted/60';
  }
  return 'border-border bg-card';
}

export default function WorkoutStructureEditor({
  structure,
  workoutType,
  disabled,
  unitSystem,
  deliveryTarget,
  compatibility,
  compatibilityLoading,
  compatibilityError,
  onChange,
}: {
  structure: WorkoutEditorStructureV1;
  workoutType: string;
  disabled: boolean;
  unitSystem: UnitSystem;
  deliveryTarget: string | null;
  compatibility: WorkoutProviderCompatibility[] | null;
  compatibilityLoading: boolean;
  compatibilityError: string | null;
  onChange: (structure: WorkoutEditorStructureV1) => void;
}) {
  const { t } = useLingui();
  const [lastRemoved, setLastRemoved] = useState<
    RemovedWorkoutEditorNode | null
  >(null);
  const [selectedId, setSelectedId] = useState<string | null>(
    () => editorIds(structure)[0] ?? null,
  );
  const summary = useMemo(
    () => summarizeWorkoutStructure(structure),
    [structure],
  );
  const validationErrors = useMemo(
    () => validateWorkoutEditorStructure(structure, workoutType),
    [structure, workoutType],
  );
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
    pace_absolute: unitSystem === 'imperial'
      ? t`Pace · min/mi`
      : t`Pace · min/km`,
    pace_threshold: unitSystem === 'imperial'
      ? t`Pace · threshold delta in sec/mi`
      : t`Pace · threshold delta in sec/km`,
    rpe: t`RPE · 0–10`,
  };
  const reasonLabels: Record<
    WorkoutProviderCompatibilityReasonCode,
    string
  > = {
    activity_type_not_supported: t`The provider does not support this activity type.`,
    duration_required: t`The provider needs a positive workout duration.`,
    empty_structure_not_supported: t`The provider cannot receive an empty structured workout.`,
    flat_workout_not_lossless: t`The legacy summary needs a duration and power range before it can be delivered without provider defaults.`,
    invalid_structure: t`The portable workout structure is invalid.`,
    phase_not_supported: t`The provider cannot preserve this step semantic.`,
    structured_workout_not_supported: t`The provider does not support structured-workout delivery yet.`,
    target_not_supported: t`The provider cannot preserve this target type.`,
    target_precision_not_supported: t`Stryd requires whole-number %CP bounds; a fractional value would be rounded.`,
    termination_not_supported: t`The provider cannot preserve this termination type.`,
    wording_not_supported: t`The provider cannot preserve this label or coaching instruction.`,
  };

  const invalidIds = useMemo(() => {
    const result = new Set<string>();
    for (const node of structure.steps) {
      if (node.type === 'step') {
        if (stepIsInvalid(node, unitSystem)) result.add(node.editorId);
        continue;
      }
      if (
        !node.steps.length
        || !Number.isInteger(node.repetitions)
        || node.repetitions < 1
        || node.repetitions > 100
      ) {
        result.add(node.editorId);
      }
      for (const step of node.steps) {
        if (stepIsInvalid(step, unitSystem)) {
          result.add(step.editorId);
          result.add(node.editorId);
        }
      }
    }
    return result;
  }, [structure, unitSystem]);

  const stepDetail = (step: WorkoutEditorStep): string => {
    const termination = step.termination.type === 'time'
      ? formatDeterministicDuration(step.termination.seconds)
      : step.termination.type === 'distance'
        ? formatDeterministicDistance(
            step.termination.meters,
            unitSystem,
          )
        : step.termination.type === 'manual'
          ? t`Manual lap`
          : t`Open`;
    const kind = targetKind(step.target);
    if (kind === 'none') return termination;
    const unit = targetUnit(kind, unitSystem);
    const range = [step.targetInputs.min, step.targetInputs.max]
      .filter(Boolean)
      .join('–');
    return range ? `${termination} · ${range} ${unit}` : termination;
  };

  const outline = structure.steps.flatMap((node, rootIndex) => {
    if (node.type === 'step') {
      return [{
        editorId: node.editorId,
        order: String(rootIndex + 1),
        title: node.label?.trim() || phaseLabels[node.phase],
        detail: stepDetail(node),
        depth: 0,
        type: 'step',
        phase: node.phase,
        invalid: invalidIds.has(node.editorId),
      } satisfies OutlineItem];
    }
    const repeatTitle = node.label?.trim() || t`Repeat group`;
    const root: OutlineItem = {
      editorId: node.editorId,
      order: String(rootIndex + 1),
      title: repeatTitle,
      detail: t`${node.repetitions} rounds · ${node.steps.length} steps`,
      depth: 0,
      type: 'repeat',
      phase: null,
      invalid: invalidIds.has(node.editorId),
    };
    return [
      root,
      ...node.steps.map((step, childIndex) => ({
        editorId: step.editorId,
        order: `${rootIndex + 1}.${childIndex + 1}`,
        title: step.label?.trim() || phaseLabels[step.phase],
        detail: stepDetail(step),
        depth: 1 as const,
        type: 'step' as const,
        phase: step.phase,
        invalid: invalidIds.has(step.editorId),
      })),
    ];
  });
  const effectiveSelectedId = selectedId && editorNode(structure, selectedId)
    ? selectedId
    : outline[0]?.editorId ?? null;
  const selectedNode = editorNode(structure, effectiveSelectedId);
  const selectedItem = outline.find((item) => (
    item.editorId === effectiveSelectedId
  )) ?? null;
  const selectedPath = effectiveSelectedId
    ? workoutEditorNodePath(structure, effectiveSelectedId)
    : null;
  const selectedRoot = selectedPath
    ? structure.steps[selectedPath[0]] ?? null
    : null;
  const siblingCount = selectedPath?.length === 2
    ? selectedRoot?.type === 'repeat'
      ? selectedRoot.steps.length
      : 0
    : structure.steps.length;
  const selectedIndex = selectedPath?.[selectedPath.length - 1] ?? 0;

  const commitStructure = (
    next: WorkoutEditorStructureV1,
    nextSelectedId: string | null = effectiveSelectedId,
  ) => {
    setLastRemoved(null);
    onChange(next);
    setSelectedId(nextSelectedId);
  };

  const updateStep = (
    editorId: string,
    update: Partial<WorkoutStructureStep>,
  ) => commitStructure(
    updateWorkoutEditorStep(
      structure,
      editorId,
      update,
      unitSystem,
    ),
    editorId,
  );

  const updateRepeat = (
    editorId: string,
    update: Partial<Omit<WorkoutEditorRepeat, 'editorId'>>,
  ) => commitStructure(
    updateWorkoutEditorRepeat(structure, editorId, update),
    editorId,
  );

  const removeNode = (editorId: string) => {
    const beforeIds = outline.map((item) => item.editorId);
    const result = removeWorkoutEditorNode(structure, editorId);
    if (!result.removed) return;
    const remaining = new Set(editorIds(result.structure));
    const removedIndex = beforeIds.indexOf(editorId);
    const candidates = [
      ...beforeIds.slice(removedIndex + 1),
      ...beforeIds.slice(0, removedIndex).reverse(),
    ];
    onChange(result.structure);
    setSelectedId(
      candidates.find((candidate) => remaining.has(candidate)) ?? null,
    );
    setLastRemoved(result.removed);
  };

  const restoreNode = () => {
    if (!lastRemoved) return;
    onChange(restoreRemovedWorkoutEditorNode(structure, lastRemoved));
    setSelectedId(lastRemoved.node.editorId);
    setLastRemoved(null);
  };

  const addRoot = (kind: 'step' | 'repeat') => {
    const node = kind === 'step'
      ? createWorkoutEditorStep({}, unitSystem)
      : createWorkoutEditorRepeat({}, unitSystem);
    commitStructure({ steps: [...structure.steps, node] }, node.editorId);
  };

  const addRepeatChild = (editorId: string) => {
    const repeat = structure.steps.find((node) => node.editorId === editorId);
    if (!repeat || repeat.type !== 'repeat') return;
    const child = createWorkoutEditorStep({}, unitSystem);
    commitStructure(
      updateWorkoutEditorRepeat(structure, editorId, {
        steps: [...repeat.steps, child],
      }),
      child.editorId,
    );
  };

  const insertNode = (
    editorId: string,
    position: 'before' | 'after',
  ) => {
    const current = editorNode(structure, editorId);
    const canonical = current?.type === 'repeat'
      ? createRepeatGroup()
      : createStructuredStep();
    const next = insertWorkoutEditorNode(
      structure,
      editorId,
      canonical,
      position,
      unitSystem,
    );
    commitStructure(next, addedEditorId(structure, next) ?? editorId);
  };

  const duplicateNode = (editorId: string) => {
    const next = duplicateWorkoutEditorNode(
      structure,
      editorId,
      unitSystem,
    );
    commitStructure(next, addedEditorId(structure, next) ?? editorId);
  };

  const updateTargetInput = (
    editorId: string,
    bound: 'min' | 'max',
    value: string,
  ) => commitStructure(
    setWorkoutEditorTargetInput(structure, editorId, bound, value),
    editorId,
  );

  const commitTargetInput = (
    editorId: string,
    bound: 'min' | 'max',
  ) => commitStructure(
    commitWorkoutEditorTargetInput(
      structure,
      editorId,
      bound,
      unitSystem,
    ).structure,
    editorId,
  );

  const updateTargetRange = (
    editorId: string,
    bound: 'min' | 'max',
    value: number,
  ) => {
    let next = setWorkoutEditorTargetInput(
      structure,
      editorId,
      bound,
      String(value),
    );
    next = commitWorkoutEditorTargetInput(
      next,
      editorId,
      bound,
      unitSystem,
    ).structure;
    commitStructure(next, editorId);
  };

  return (
    <section className="min-w-0 border-y border-border py-5">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            <Trans>Workout structure</Trans>
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted-foreground">
            <Trans>
              Build the canonical workout once. Select a step in the profile
              or order list to edit it; Praxys keeps richer details even when a
              delivery platform cannot represent them.
            </Trans>
          </p>
        </div>
        <span className="font-data text-xs text-muted-foreground">
          {summary.executableSteps} {summary.executableSteps === 1
            ? t`step`
            : t`steps`}
        </span>
      </div>

      <WorkoutProfile
        structure={structure}
        outline={outline}
        selectedId={effectiveSelectedId}
        summary={summary}
        unitSystem={unitSystem}
        phaseLabels={phaseLabels}
        onSelect={setSelectedId}
      />

      {validationErrors.length > 0 && (
        <Alert variant="destructive" className="mt-4">
          <AlertCircle aria-hidden="true" />
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span>
              <Trans>
                Fix the marked step before saving. Every target and
                termination must be complete.
              </Trans>
            </span>
            {outline.find((item) => item.invalid) && (
              <Button
                type="button"
                variant="link"
                size="sm"
                className="h-auto px-0 text-destructive"
                onClick={() => setSelectedId(
                  outline.find((item) => item.invalid)?.editorId ?? null,
                )}
              >
                <Trans>Review first issue</Trans>
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <WorkoutOutline
          items={outline}
          selectedId={effectiveSelectedId}
          disabled={disabled}
          onSelect={setSelectedId}
          onAddStep={() => addRoot('step')}
          onAddRepeat={() => addRoot('repeat')}
        />

        <div className="min-w-0 border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
          {!selectedNode || !selectedItem ? (
            <div className="py-8 text-center">
              <p className="text-sm font-medium text-foreground">
                <Trans>No step selected</Trans>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                <Trans>Add a step or repeat group to begin.</Trans>
              </p>
            </div>
          ) : selectedNode.type === 'step' ? (
            <StepInspector
              step={selectedNode}
              item={selectedItem}
              disabled={disabled}
              unitSystem={unitSystem}
              phaseLabels={phaseLabels}
              targetLabels={targetLabels}
              canMoveUp={selectedIndex > 0}
              canMoveDown={selectedIndex < siblingCount - 1}
              onUpdate={updateStep}
              onMove={(direction) => commitStructure(
                moveWorkoutEditorNode(
                  structure,
                  selectedNode.editorId,
                  direction,
                ),
                selectedNode.editorId,
              )}
              onInsert={(position) => insertNode(
                selectedNode.editorId,
                position,
              )}
              onDuplicate={() => duplicateNode(selectedNode.editorId)}
              onDelete={() => removeNode(selectedNode.editorId)}
              onTargetInput={updateTargetInput}
              onTargetBlur={commitTargetInput}
              onTargetRange={updateTargetRange}
            />
          ) : (
            <RepeatInspector
              repeat={selectedNode}
              item={selectedItem}
              disabled={disabled}
              childItems={outline.filter((item) => {
                const path = workoutEditorNodePath(
                  structure,
                  item.editorId,
                );
                return path?.length === 2
                  && structure.steps[path[0]]?.editorId === selectedNode.editorId;
              })}
              canMoveUp={selectedIndex > 0}
              canMoveDown={selectedIndex < siblingCount - 1}
              onUpdate={(update) => updateRepeat(
                selectedNode.editorId,
                update,
              )}
              onMove={(direction) => commitStructure(
                moveWorkoutEditorNode(
                  structure,
                  selectedNode.editorId,
                  direction,
                ),
                selectedNode.editorId,
              )}
              onInsert={(position) => insertNode(
                selectedNode.editorId,
                position,
              )}
              onDuplicate={() => duplicateNode(selectedNode.editorId)}
              onDelete={() => removeNode(selectedNode.editorId)}
              onAddChild={() => addRepeatChild(selectedNode.editorId)}
              onSelectChild={setSelectedId}
            />
          )}
        </div>
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
        deliveryTarget={deliveryTarget}
        structure={structure}
        outline={outline}
        reasonLabels={reasonLabels}
        onSelect={setSelectedId}
      />
    </section>
  );
}

function WorkoutProfile({
  structure,
  outline,
  selectedId,
  summary,
  unitSystem,
  phaseLabels,
  onSelect,
}: {
  structure: WorkoutEditorStructureV1;
  outline: OutlineItem[];
  selectedId: string | null;
  summary: ReturnType<typeof summarizeWorkoutStructure>;
  unitSystem: UnitSystem;
  phaseLabels: Record<WorkoutStructureStep['phase'], string>;
  onSelect: (editorId: string) => void;
}) {
  const { t } = useLingui();
  const itemById = new Map(outline.map((item) => [item.editorId, item]));
  return (
    <div className="min-w-0 border-y border-border py-4">
      <div className="grid gap-2 sm:grid-cols-3">
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
            ? formatDeterministicDistance(
                summary.distance.meters,
                unitSystem,
              )
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

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold text-foreground">
            <Trans>Workout profile</Trans>
          </p>
          <p className="text-[10px] text-muted-foreground">
            <Trans>Sequence, not invented training load</Trans>
          </p>
        </div>
        {structure.steps.length === 0 ? (
          <div className="border-y border-dashed border-border py-5 text-center text-xs text-muted-foreground">
            <Trans>No executable steps yet.</Trans>
          </div>
        ) : (
          <div
            className="flex min-h-20 gap-1 overflow-x-auto pb-1"
            role="group"
            aria-label={t`Workout profile`}
          >
            {structure.steps.map((node) => {
              const item = itemById.get(node.editorId);
              if (node.type === 'step') {
                return (
                  <Button
                    key={node.editorId}
                    type="button"
                    variant="ghost"
                    onClick={() => onSelect(node.editorId)}
                    className={cn(
                      'h-auto min-w-24 flex-1 flex-col items-start justify-between overflow-hidden rounded-md border px-3 py-2 text-left',
                      phaseTone(node.phase),
                      selectedId === node.editorId
                        && 'border-primary ring-2 ring-primary/25',
                      item?.invalid && 'border-destructive',
                    )}
                  >
                    <span className="font-data text-[10px] text-muted-foreground">
                      {item?.order}
                    </span>
                    <span className="mt-2 line-clamp-2 w-full whitespace-normal text-xs font-semibold text-foreground">
                      {item?.title ?? phaseLabels[node.phase]}
                    </span>
                    <span className="mt-1 w-full truncate font-data text-[10px] text-muted-foreground">
                      {item?.detail}
                    </span>
                  </Button>
                );
              }
              return (
                <div
                  key={node.editorId}
                  role="group"
                  aria-label={[
                    item?.order,
                    item?.title ?? t`Repeat group`,
                  ].filter(Boolean).join(' ')}
                  className={cn(
                    'min-w-52 flex-[1.6] rounded-md border border-border p-1.5',
                    selectedId === node.editorId
                      && 'border-primary ring-2 ring-primary/25',
                    item?.invalid && 'border-destructive',
                  )}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => onSelect(node.editorId)}
                    className="h-7 w-full justify-between px-1.5 text-xs"
                  >
                    <span className="truncate">
                      <span className="font-data">{item?.order}</span>
                      {' · '}
                      {item?.title ?? t`Repeat group`}
                    </span>
                    <span className="font-data text-muted-foreground">
                      ×{node.repetitions}
                    </span>
                  </Button>
                  <div className="mt-1 flex gap-1">
                    {node.steps.map((step) => {
                      const child = itemById.get(step.editorId);
                      return (
                        <Button
                          key={step.editorId}
                          type="button"
                          variant="ghost"
                          onClick={() => onSelect(step.editorId)}
                          aria-label={`${child?.order} ${child?.title}`}
                          className={cn(
                            'h-9 min-w-10 flex-1 rounded-sm border px-1',
                            phaseTone(step.phase),
                            selectedId === step.editorId
                              && 'border-primary ring-2 ring-primary/25',
                            child?.invalid && 'border-destructive',
                          )}
                        >
                          <span className="font-data text-[10px]">
                            {child?.order}
                          </span>
                        </Button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
        <Trans>
          Totals are deterministic only when every repeated step has the same
          measurable termination. Praxys does not invent a training-load score
          here.
        </Trans>
      </p>
    </div>
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
        {certainty !== 'unknown' && (
          <span className="ml-1 text-[10px] text-muted-foreground">
            {certainty === 'deterministic'
              ? t`deterministic`
              : t`estimated`}
          </span>
        )}
      </span>
    </div>
  );
}

function WorkoutOutline({
  items,
  selectedId,
  disabled,
  onSelect,
  onAddStep,
  onAddRepeat,
}: {
  items: OutlineItem[];
  selectedId: string | null;
  disabled: boolean;
  onSelect: (editorId: string) => void;
  onAddStep: () => void;
  onAddRepeat: () => void;
}) {
  const { t } = useLingui();
  return (
    <aside className="lg:sticky lg:top-0 lg:self-start">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold text-foreground">
          <Trans>Workout order</Trans>
        </h4>
        <span className="font-data text-[10px] text-muted-foreground">
          {items.length}
        </span>
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        <Trans>Select one item to edit. Repeat children stay visibly nested.</Trans>
      </p>
      <nav
        className="mt-3 max-h-72 space-y-1 overflow-y-auto pr-1 lg:max-h-[34rem]"
        aria-label={t`Workout order`}
      >
        {items.map((item) => (
          <Button
            key={item.editorId}
            type="button"
            variant="ghost"
            aria-pressed={selectedId === item.editorId}
            onClick={() => onSelect(item.editorId)}
            className={cn(
              'h-auto w-full justify-start gap-2 rounded-md border border-transparent px-2 py-2 text-left',
              item.depth === 1 && 'ml-3 w-[calc(100%-0.75rem)] border-l-border',
              selectedId === item.editorId
                && 'border-primary/30 bg-primary/8 text-foreground',
              item.invalid && 'border-destructive/40',
            )}
          >
            <span className="w-8 shrink-0 font-data text-[10px] text-muted-foreground">
              {item.order}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-xs font-medium">
                {item.title}
              </span>
              <span className="mt-0.5 block truncate font-data text-[10px] font-normal text-muted-foreground">
                {item.detail}
              </span>
            </span>
            {item.type === 'repeat' && (
              <Repeat2 className="size-3.5 shrink-0 text-accent-cobalt" aria-hidden="true" />
            )}
            {item.invalid && (
              <AlertCircle className="size-3.5 shrink-0 text-destructive" aria-hidden="true" />
            )}
          </Button>
        ))}
      </nav>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={onAddStep}
        >
          <Plus aria-hidden="true" />
          <Trans>Step</Trans>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={onAddRepeat}
        >
          <Repeat2 aria-hidden="true" />
          <Trans>Repeat</Trans>
        </Button>
      </div>
    </aside>
  );
}

function StepInspector({
  step,
  item,
  disabled,
  unitSystem,
  phaseLabels,
  targetLabels,
  canMoveUp,
  canMoveDown,
  onUpdate,
  onMove,
  onInsert,
  onDuplicate,
  onDelete,
  onTargetInput,
  onTargetBlur,
  onTargetRange,
}: {
  step: WorkoutEditorStep;
  item: OutlineItem;
  disabled: boolean;
  unitSystem: UnitSystem;
  phaseLabels: Record<WorkoutStructureStep['phase'], string>;
  targetLabels: Record<WorkoutTargetKind, string>;
  canMoveUp: boolean;
  canMoveDown: boolean;
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
  onTargetBlur: (editorId: string, bound: 'min' | 'max') => void;
  onTargetRange: (
    editorId: string,
    bound: 'min' | 'max',
    value: number,
  ) => void;
}) {
  const { i18n, t } = useLingui();
  const kind = targetKind(step.target);
  const prefix = `workout-step-${step.editorId}`;
  return (
    <div>
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="font-data text-[10px] text-muted-foreground">
            <Trans>Step</Trans> {item.order}
          </p>
          <h4 className="mt-1 text-base font-semibold text-foreground">
            {item.title}
          </h4>
          <p className="mt-1 font-data text-[11px] text-muted-foreground">
            {item.detail}
          </p>
        </div>
        <NodeActions
          disabled={disabled}
          canMoveUp={canMoveUp}
          canMoveDown={canMoveDown}
          onMove={onMove}
          onInsert={onInsert}
          onDuplicate={onDuplicate}
          onDelete={onDelete}
        />
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
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
            <SelectTrigger id={`${prefix}-phase`} className="w-full">
              <SelectValue>{phaseLabels[step.phase]}</SelectValue>
            </SelectTrigger>
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

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <TerminationFields
          key={`${step.editorId}:${step.termination.type}:${unitSystem}`}
          idPrefix={prefix}
          termination={step.termination}
          disabled={disabled}
          unitSystem={unitSystem}
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
            <SelectTrigger id={`${prefix}-target`} className="w-full">
              <SelectValue>{targetLabels[kind]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {TARGET_KINDS.map((targetKindValue) => (
                <SelectItem key={targetKindValue} value={targetKindValue}>
                  {targetLabels[targetKindValue]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            {targetDescription(kind, unitSystem, i18n)}
          </p>
        </div>
      </div>

      {kind !== 'none' && (
        <TargetRangeFields
          idPrefix={prefix}
          step={step}
          kind={kind}
          disabled={disabled}
          unitSystem={unitSystem}
          onInput={onTargetInput}
          onBlur={onTargetBlur}
          onRange={onTargetRange}
        />
      )}

      <div className="mt-4 space-y-1.5">
        <Label htmlFor={`${prefix}-instructions`}>
          <Trans>Step instructions</Trans>
        </Label>
        <textarea
          id={`${prefix}-instructions`}
          value={step.instructions ?? ''}
          disabled={disabled}
          maxLength={1000}
          rows={3}
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

function RepeatInspector({
  repeat,
  item,
  disabled,
  childItems,
  canMoveUp,
  canMoveDown,
  onUpdate,
  onMove,
  onInsert,
  onDuplicate,
  onDelete,
  onAddChild,
  onSelectChild,
}: {
  repeat: WorkoutEditorRepeat;
  item: OutlineItem;
  disabled: boolean;
  childItems: OutlineItem[];
  canMoveUp: boolean;
  canMoveDown: boolean;
  onUpdate: (
    update: Partial<Omit<WorkoutEditorRepeat, 'editorId'>>,
  ) => void;
  onMove: (direction: 'up' | 'down') => void;
  onInsert: (position: 'before' | 'after') => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onAddChild: () => void;
  onSelectChild: (editorId: string) => void;
}) {
  const { t } = useLingui();
  const prefix = `workout-repeat-${repeat.editorId}`;
  return (
    <div>
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="flex items-center gap-1.5 font-data text-[10px] text-accent-cobalt">
            <Repeat2 className="size-3.5" aria-hidden="true" />
            <Trans>Repeat group</Trans> {item.order}
          </p>
          <h4 className="mt-1 text-base font-semibold text-foreground">
            {item.title}
          </h4>
          <p className="mt-1 font-data text-[11px] text-muted-foreground">
            {item.detail}
          </p>
        </div>
        <NodeActions
          disabled={disabled}
          canMoveUp={canMoveUp}
          canMoveDown={canMoveDown}
          onMove={onMove}
          onInsert={onInsert}
          onDuplicate={onDuplicate}
          onDelete={onDelete}
        />
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
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
          <Label htmlFor={`${prefix}-repetitions`}>
            <Trans>Repetitions</Trans>
          </Label>
          <Input
            id={`${prefix}-repetitions`}
            type="number"
            inputMode="numeric"
            min="1"
            max="100"
            value={repeat.repetitions}
            disabled={disabled}
            aria-invalid={
              repeat.repetitions < 1 || repeat.repetitions > 100 || undefined
            }
            onChange={(event) => {
              const repetitions = Number(event.target.value);
              if (Number.isInteger(repetitions)) onUpdate({ repetitions });
            }}
            className="font-data"
          />
        </div>
      </div>

      <div className="mt-5 border-y border-border py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-foreground">
              <Trans>Repeat steps</Trans>
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              <Trans>
                Select a child to edit it. Portable v1 permits one repeat
                level.
              </Trans>
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={onAddChild}
          >
            <Plus aria-hidden="true" />
            <Trans>Add repeat step</Trans>
          </Button>
        </div>
        <div className="mt-3 divide-y divide-border border-y border-border">
          {childItems.map((child) => (
            <Button
              key={child.editorId}
              type="button"
              variant="ghost"
              className="h-auto w-full justify-start gap-3 rounded-none px-1 py-3 text-left"
              onClick={() => onSelectChild(child.editorId)}
            >
              <span className="w-10 font-data text-[10px] text-muted-foreground">
                {child.order}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium">
                  {child.title}
                </span>
                <span className="mt-0.5 block truncate font-data text-[10px] font-normal text-muted-foreground">
                  {child.detail}
                </span>
              </span>
              {child.invalid && (
                <AlertCircle className="size-3.5 text-destructive" aria-hidden="true" />
              )}
            </Button>
          ))}
          {childItems.length === 0 && (
            <p className="py-4 text-center text-xs text-destructive">
              <Trans>Add at least one step to this repeat.</Trans>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function TerminationFields({
  idPrefix,
  termination,
  disabled,
  unitSystem,
  onChange,
}: {
  idPrefix: string;
  termination: WorkoutTermination;
  disabled: boolean;
  unitSystem: UnitSystem;
  onChange: (termination: WorkoutTermination) => void;
}) {
  const { t } = useLingui();
  const terminationLabels: Record<WorkoutTermination['type'], string> = {
    time: t`Time`,
    distance: t`Distance`,
    open: t`Open`,
    manual: t`Manual`,
  };
  const updateDuration = (
    part: 'hours' | 'minutes' | 'seconds',
    raw: string,
  ) => {
    if (termination.type !== 'time') return;
    const value = Number(raw);
    if (!Number.isInteger(value) || value < 0) return;
    const hours = Math.floor(termination.seconds / 3600);
    const minutes = Math.floor((termination.seconds % 3600) / 60);
    const seconds = termination.seconds % 60;
    const next = {
      hours: part === 'hours' ? value : hours,
      minutes: part === 'minutes' ? Math.min(value, 59) : minutes,
      seconds: part === 'seconds' ? Math.min(value, 59) : seconds,
    };
    onChange({
      type: 'time',
      seconds: next.hours * 3600 + next.minutes * 60 + next.seconds,
    });
  };
  const distance = termination.type === 'distance'
    ? formatWorkoutDistanceInput(termination.meters, unitSystem)
    : null;
  const [distanceInput, setDistanceInput] = useState(
    () => distance?.value ?? '',
  );
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
        <SelectTrigger id={`${idPrefix}-termination`} className="w-full">
          <SelectValue>{terminationLabels[termination.type]}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="time"><Trans>Time</Trans></SelectItem>
          <SelectItem value="distance"><Trans>Distance</Trans></SelectItem>
          <SelectItem value="open"><Trans>Open</Trans></SelectItem>
          <SelectItem value="manual"><Trans>Manual</Trans></SelectItem>
        </SelectContent>
      </Select>
      {termination.type === 'time' && (
        <div className="grid grid-cols-3 gap-2">
          {([
            ['hours', Math.floor(termination.seconds / 3600), t`hr`],
            [
              'minutes',
              Math.floor((termination.seconds % 3600) / 60),
              t`min`,
            ],
            ['seconds', termination.seconds % 60, t`sec`],
          ] as const).map(([part, value, unit]) => (
            <div key={part} className="relative">
              <Input
                type="number"
                inputMode="numeric"
                min="0"
                max={part === 'hours' ? 24 : 59}
                value={value}
                disabled={disabled}
                aria-label={`${terminationLabels.time} ${unit}`}
                onChange={(event) => updateDuration(part, event.target.value)}
                className="pr-10 font-data"
              />
              <span className="pointer-events-none absolute right-2.5 top-2 text-[10px] text-muted-foreground">
                {unit}
              </span>
            </div>
          ))}
        </div>
      )}
      {termination.type === 'distance' && distance && (
        <div className="relative">
          <Input
            id={`${idPrefix}-distance`}
            className="pr-12 font-data"
            type="text"
            inputMode="decimal"
            value={distanceInput}
            disabled={disabled}
            aria-label={t`Distance in ${distance.unit}`}
            onChange={(event) => {
              setDistanceInput(event.target.value);
              const meters = parseWorkoutDistanceInput(
                event.target.value,
                unitSystem,
              );
              if (meters != null) onChange({ type: 'distance', meters });
            }}
            onBlur={() => {
              const meters = parseWorkoutDistanceInput(
                distanceInput,
                unitSystem,
              );
              if (meters == null) {
                setDistanceInput(distance.value);
                return;
              }
              onChange({ type: 'distance', meters });
              setDistanceInput(
                formatWorkoutDistanceInput(meters, unitSystem).value,
              );
            }}
          />
          <span className="pointer-events-none absolute right-3 top-2 text-xs text-muted-foreground">
            {distance.unit}
          </span>
        </div>
      )}
      {(termination.type === 'open' || termination.type === 'manual') && (
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {termination.type === 'open'
            ? t`The athlete ends this step when ready.`
            : t`The athlete ends this step with a manual lap action.`}
        </p>
      )}
    </div>
  );
}

function TargetRangeFields({
  idPrefix,
  step,
  kind,
  disabled,
  unitSystem,
  onInput,
  onBlur,
  onRange,
}: {
  idPrefix: string;
  step: WorkoutEditorStep;
  kind: Exclude<WorkoutTargetKind, 'none'>;
  disabled: boolean;
  unitSystem: UnitSystem;
  onInput: (
    editorId: string,
    bound: 'min' | 'max',
    value: string,
  ) => void;
  onBlur: (editorId: string, bound: 'min' | 'max') => void;
  onRange: (
    editorId: string,
    bound: 'min' | 'max',
    value: number,
  ) => void;
}) {
  const { t } = useLingui();
  const slider = SLIDER_TARGETS[kind];
  const minimumPresent = step.targetInputs.min.trim() !== '';
  const maximumPresent = step.targetInputs.max.trim() !== '';
  const rawMinimum = Number(step.targetInputs.min);
  const rawMaximum = Number(step.targetInputs.max);
  let sliderMinimum = 0;
  let sliderMaximum = 0;
  if (slider) {
    const clampedMinimum = clamp(
      minimumPresent && Number.isFinite(rawMinimum)
        ? rawMinimum
        : slider.min,
      slider.min,
      slider.max,
    );
    const clampedMaximum = clamp(
      maximumPresent && Number.isFinite(rawMaximum)
        ? rawMaximum
        : slider.max,
      slider.min,
      slider.max,
    );
    if (minimumPresent && maximumPresent) {
      sliderMinimum = clampedMinimum;
      sliderMaximum = clamp(clampedMaximum, sliderMinimum, slider.max);
    } else if (minimumPresent) {
      sliderMinimum = clampedMinimum;
      sliderMaximum = Math.min(
        slider.max,
        sliderMinimum + slider.step * 10,
      );
    } else if (maximumPresent) {
      sliderMaximum = clampedMaximum;
      sliderMinimum = Math.max(
        slider.min,
        sliderMaximum - slider.step * 10,
      );
    } else {
      sliderMinimum = slider.min;
      sliderMaximum = Math.min(
        slider.max,
        slider.min + slider.step * 10,
      );
    }
  }
  const unit = targetUnit(kind, unitSystem);
  const placeholder = kind === 'pace_absolute' ? t`e.g. 5:20` : t`Optional`;
  return (
    <div className="mt-4 border-y border-border py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold text-foreground">
            <Trans>Target range</Trans>
          </p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {slider
              ? t`Drag the range or type exact values.`
              : t`Type precise bounds in the visible unit.`}
          </p>
        </div>
        <span className="font-data text-[10px] text-muted-foreground">
          {unit}
        </span>
      </div>

      {slider && (
        <div className="mt-4 px-1">
          <RangeSlider
            value={[sliderMinimum, sliderMaximum]}
            min={slider.min}
            max={slider.max}
            step={slider.step}
            disabled={disabled}
            minimumLabel={t`Target minimum`}
            maximumLabel={t`Target maximum`}
            onValueChange={(values, bound) => onRange(
              step.editorId,
              bound,
              values[bound === 'min' ? 0 : 1],
            )}
          />
          <div className="mt-1 flex justify-between font-data text-[10px] text-muted-foreground">
            <span>{slider.min}</span>
            <span>{slider.max}</span>
          </div>
        </div>
      )}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {(['min', 'max'] as const).map((bound) => {
          const invalid = bound === 'min'
            ? step.targetInputs.minInvalid
            : step.targetInputs.maxInvalid;
          return (
            <div key={bound} className="space-y-1.5">
              <Label htmlFor={`${idPrefix}-target-${bound}`}>
                {bound === 'min' ? t`Target minimum` : t`Target maximum`}
              </Label>
              <div className="relative">
                <Input
                  id={`${idPrefix}-target-${bound}`}
                  type="text"
                  inputMode={
                    kind === 'pace_absolute' || TARGET_BOUNDS[kind].min < 0
                      ? 'text'
                      : 'decimal'
                  }
                  value={step.targetInputs[bound]}
                  disabled={disabled}
                  aria-invalid={invalid || undefined}
                  onChange={(event) => onInput(
                    step.editorId,
                    bound,
                    event.target.value,
                  )}
                  onBlur={() => onBlur(step.editorId, bound)}
                  className="pr-20 font-data"
                  placeholder={placeholder}
                />
                <span className="pointer-events-none absolute right-2.5 top-2 max-w-16 truncate text-[10px] text-muted-foreground">
                  {unit}
                </span>
              </div>
              {invalid && (
                <p className="text-[11px] text-destructive">
                  <Trans>Enter a complete value in this unit.</Trans>
                </p>
              )}
            </div>
          );
        })}
      </div>
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
      <ActionButton
        label={t`Move up`}
        icon={ArrowUp}
        disabled={disabled || !canMoveUp}
        onClick={() => onMove('up')}
      />
      <ActionButton
        label={t`Move down`}
        icon={ArrowDown}
        disabled={disabled || !canMoveDown}
        onClick={() => onMove('down')}
      />
      <ActionButton
        label={t`Insert before`}
        icon={ListPlus}
        disabled={disabled}
        onClick={() => onInsert('before')}
      />
      <ActionButton
        label={t`Insert after`}
        icon={Plus}
        disabled={disabled}
        onClick={() => onInsert('after')}
      />
      <ActionButton
        label={t`Duplicate`}
        icon={Copy}
        disabled={disabled}
        onClick={onDuplicate}
      />
      <ActionButton
        label={t`Delete`}
        icon={Trash2}
        disabled={disabled}
        destructive
        onClick={onDelete}
      />
    </div>
  );
}

function ActionButton({
  label,
  icon: Icon,
  disabled,
  destructive = false,
  onClick,
}: {
  label: string;
  icon: ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' }>;
  disabled: boolean;
  destructive?: boolean;
  onClick: () => void;
}) {
  const button = (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      className={cn(
        'h-8 px-2 text-[11px]',
        destructive
          && 'text-destructive hover:bg-destructive/10 hover:text-destructive',
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      <span>{label}</span>
    </Button>
  );
  return (
    <Tooltip>
      <TooltipTrigger render={button} />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function ProviderCompatibilitySummary({
  compatibility,
  loading,
  error,
  deliveryTarget,
  structure,
  outline,
  reasonLabels,
  onSelect,
}: {
  compatibility: WorkoutProviderCompatibility[] | null;
  loading: boolean;
  error: string | null;
  deliveryTarget: string | null;
  structure: WorkoutEditorStructureV1;
  outline: OutlineItem[];
  reasonLabels: Record<WorkoutProviderCompatibilityReasonCode, string>;
  onSelect: (editorId: string) => void;
}) {
  const { t } = useLingui();
  const [showOthers, setShowOthers] = useState(false);
  const selectedTarget = deliveryTarget === 'garmin'
    || deliveryTarget === 'stryd'
    ? deliveryTarget
    : null;
  const primary = selectedTarget
    ? compatibility?.find((provider) => provider.target === selectedTarget)
      ?? null
    : null;
  const others = compatibility?.filter((provider) => (
    provider.target !== selectedTarget
  )) ?? [];
  return (
    <div className="mt-5 border-t border-border pt-4">
      <h3 className="text-sm font-semibold text-foreground">
        <Trans>Delivery preview</Trans>
      </h3>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        <Trans>
          Praxys keeps the canonical workout. This preview explains what the
          selected platform can receive without losing meaning.
        </Trans>
      </p>

      {loading && (
        <p className="mt-3 text-xs text-accent-cobalt">
          <Trans>Checking delivery compatibility…</Trans>
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
          <Trans>Finish the required step fields to preview delivery.</Trans>
        </p>
      )}

      {!selectedTarget && !loading && !error && compatibility && (
        <Alert className="mt-3">
          <AlertDescription className="text-xs">
            <Trans>
              No Garmin or Stryd execution target is selected. Compatibility
              remains informational until plan delivery is configured.
            </Trans>
          </AlertDescription>
        </Alert>
      )}

      {primary && (
        <ProviderResult
          provider={primary}
          primary
          structure={structure}
          outline={outline}
          reasonLabels={reasonLabels}
          onSelect={onSelect}
        />
      )}

      {others.length > 0 && (
        <div className="mt-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="px-0 text-xs text-muted-foreground"
            onClick={() => setShowOthers((current) => !current)}
          >
            {showOthers
              ? t`Hide other providers`
              : t`Compare other providers (${others.length})`}
          </Button>
          {showOthers && (
            <div className="mt-1 divide-y divide-border border-y border-border">
              {others.map((provider) => (
                <ProviderResult
                  key={provider.target}
                  provider={provider}
                  primary={false}
                  structure={structure}
                  outline={outline}
                  reasonLabels={reasonLabels}
                  onSelect={onSelect}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProviderResult({
  provider,
  primary,
  structure,
  outline,
  reasonLabels,
  onSelect,
}: {
  provider: WorkoutProviderCompatibility;
  primary: boolean;
  structure: WorkoutEditorStructureV1;
  outline: OutlineItem[];
  reasonLabels: Record<WorkoutProviderCompatibilityReasonCode, string>;
  onSelect: (editorId: string) => void;
}) {
  const { t } = useLingui();
  const providerName = provider.target === 'garmin' ? 'Garmin' : 'Stryd';
  if (primary && !provider.compatible) {
    return (
      <Alert variant="destructive" className="mt-3">
        <AlertCircle aria-hidden="true" />
        <AlertDescription>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-xs font-semibold">
              <Trans>Delivery to {providerName} is blocked</Trans>
            </p>
            <span className="font-data text-[10px]">
              <Trans>Canonical workout remains safe</Trans>
            </span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed">
            <Trans>
              You can still save this workout in Praxys, but managed delivery
              cannot preserve it until the marked details are changed.
            </Trans>
          </p>
          <ProviderReasons
            provider={provider}
            structure={structure}
            outline={outline}
            reasonLabels={reasonLabels}
            onSelect={onSelect}
            destructive
          />
        </AlertDescription>
      </Alert>
    );
  }
  return (
    <div className={primary ? 'mt-3 border-y border-border py-3' : 'py-3'}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-semibold text-foreground">{providerName}</p>
        <span className={cn(
          'text-xs font-medium',
          provider.compatible
            ? 'text-primary'
            : primary
              ? 'text-destructive'
              : 'text-accent-amber',
        )}
        >
          {provider.compatible ? t`Ready to deliver` : t`Not safely representable`}
        </span>
      </div>
      {provider.compatible ? (
        <p className="mt-1 flex items-start gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
          <Check className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
          <span>
            {provider.mode === 'structured'
              ? t`The ordered steps and target ranges can be delivered without flattening.`
              : t`This legacy workout has no structured tree to deliver.`}
          </span>
        </p>
      ) : (
        <ProviderReasons
          provider={provider}
          structure={structure}
          outline={outline}
          reasonLabels={reasonLabels}
          onSelect={onSelect}
          destructive={false}
        />
      )}
    </div>
  );
}

function ProviderReasons({
  provider,
  structure,
  outline,
  reasonLabels,
  onSelect,
  destructive,
}: {
  provider: WorkoutProviderCompatibility;
  structure: WorkoutEditorStructureV1;
  outline: OutlineItem[];
  reasonLabels: Record<WorkoutProviderCompatibilityReasonCode, string>;
  onSelect: (editorId: string) => void;
  destructive: boolean;
}) {
  const { i18n } = useLingui();
  return (
    <ul className={cn(
      'mt-2 space-y-1.5 text-[11px] leading-relaxed',
      destructive ? 'text-destructive' : 'text-muted-foreground',
    )}
    >
      {provider.reasons.map((reason) => {
        const editorId = workoutEditorIdForCompatibilityPath(
          structure,
          reason.path,
        );
        const item = outline.find((candidate) => (
          candidate.editorId === editorId
        ));
        const field = compatibilityField(reason, i18n);
        const copy = reasonLabels[reason.code];
        const content = (
          <>
            {item && (
              <span className="font-semibold">
                {item.order} · {item.title}
                {field ? ` · ${field}` : ''}: {' '}
              </span>
            )}
            {copy}
          </>
        );
        return (
          <li key={`${reason.code}-${reason.path ?? ''}`}>
            {editorId ? (
              <Button
                type="button"
                variant="link"
                className={cn(
                  'h-auto whitespace-normal px-0 py-0 text-left text-[11px] leading-relaxed',
                  destructive
                    ? 'text-destructive'
                    : 'text-muted-foreground',
                )}
                onClick={() => onSelect(editorId)}
              >
                {content}
              </Button>
            ) : content}
          </li>
        );
      })}
    </ul>
  );
}

function compatibilityField(
  reason: WorkoutProviderCompatibilityReason,
  i18n: I18n,
): string {
  const path = reason.path ?? '';
  if (path.endsWith('.phase')) {
    return i18n._(COMPATIBILITY_FIELD_MESSAGES.semantic);
  }
  if (path.endsWith('.termination')) {
    return i18n._(COMPATIBILITY_FIELD_MESSAGES.termination);
  }
  if (path.endsWith('.target')) {
    return i18n._(COMPATIBILITY_FIELD_MESSAGES.target);
  }
  if (path.endsWith('.label')) {
    return i18n._(COMPATIBILITY_FIELD_MESSAGES.label);
  }
  if (path.endsWith('.instructions')) {
    return i18n._(COMPATIBILITY_FIELD_MESSAGES.instructions);
  }
  return '';
}

function targetUnit(
  kind: WorkoutTargetKind,
  unitSystem: UnitSystem,
): string {
  const units: Record<WorkoutTargetKind, string> = {
    none: '',
    power_watts: 'W',
    power_cp: '%CP',
    heart_rate_bpm: 'bpm',
    heart_rate_lthr: '%LTHR',
    pace_absolute: unitSystem === 'imperial' ? 'min/mi' : 'min/km',
    pace_threshold: unitSystem === 'imperial' ? 'sec/mi Δ' : 'sec/km Δ',
    rpe: 'RPE',
  };
  return units[kind];
}

function targetDescription(
  kind: WorkoutTargetKind,
  unitSystem: UnitSystem,
  i18n: I18n,
): string {
  if (kind === 'pace_absolute') {
    return i18n._(PACE_DESCRIPTION_MESSAGES.absolute[unitSystem]);
  }
  if (kind === 'pace_threshold') {
    return i18n._(PACE_DESCRIPTION_MESSAGES.threshold[unitSystem]);
  }
  return i18n._(TARGET_DESCRIPTION_MESSAGES[kind]);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}
