import { useState } from 'react';
import { useLingui } from '@lingui/react/macro';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type { GoalKind } from '@/types/api';
import { formatTime, parseTimeToSeconds } from '@/lib/format';

type DistanceKey = '5k' | '10k' | 'half' | 'marathon' | '50k' | '50mi' | '100k' | '100mi';

interface GoalEditorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialType: GoalKind;
  initialRaceDate: string;
  initialDistance: string;
  initialTargetTime: number | null;
  onSave: (goal: { goal_kind: GoalKind; race_date: string; distance: string; target_time_sec: number }) => Promise<void>;
}

export default function GoalEditor({
  open,
  onOpenChange,
  initialType,
  initialRaceDate,
  initialDistance,
  initialTargetTime,
  onSave,
}: GoalEditorProps) {
  const { t } = useLingui();
  const copy = {
    title: t`Set your goal`,
    description: t`Choose a race target, track continuous progress, or use the 5K baseline pilot.`,
    goalType: t`Goal type`,
    race: t`Race goal`,
    raceDesc: t`Train toward a specific race date`,
    continuous: t`Continuous`,
    continuousDesc: t`Track trend over time`,
    performance: t`5K performance`,
    performanceDesc: t`Use history first, then decide whether the optional pilot test is needed`,
    distance: t`Distance`,
    raceDate: t`Race date`,
    targetTime: t`Target time`,
    optional: t`optional`,
    pickDate: t`Pick a date`,
    cancel: t`Cancel`,
    save: t`Save goal`,
    saving: t`Saving…`,
    raceDateRequired: t`Race date is required`,
    invalidTime: t`Invalid time format. Use H:MM:SS or H:MM`,
    failedToSave: t`Failed to save goal`,
    raceTargetHint: t`Leave blank to track predicted time only`,
    continuousHint: t`Leave blank to track trend only`,
    performanceHint: t`This pilot currently supports only outdoor road 5K elapsed-time goals.`,
  };
  const [goalType, setGoalType] = useState<GoalKind>(initialType);
  const [raceDate, setRaceDate] = useState(initialRaceDate);
  const [distance, setDistance] = useState(initialDistance || 'marathon');
  const [targetTimeInput, setTargetTimeInput] = useState(initialTargetTime ? formatTime(initialTargetTime) : '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const distances: { value: DistanceKey; label: string; placeholder: string }[] = [
    { value: '5k', label: '5K', placeholder: '20:00' },
    { value: '10k', label: '10K', placeholder: '42:00' },
    { value: 'half', label: t`Half`, placeholder: '1:30:00' },
    { value: 'marathon', label: t`Marathon`, placeholder: '3:00:00' },
    { value: '50k', label: '50K', placeholder: '4:30:00' },
    { value: '50mi', label: t`50 Mi`, placeholder: '8:00:00' },
    { value: '100k', label: '100K', placeholder: '12:00:00' },
    { value: '100mi', label: t`100 Mi`, placeholder: '24:00:00' },
  ];

  const effectiveDistance = goalType === 'performance_5k' ? '5k' : distance;
  const selected = distances.find((item) => item.value === effectiveDistance);

  const handleSave = async () => {
    setError('');
    if (goalType === 'race' && !raceDate) {
      setError(copy.raceDateRequired);
      return;
    }
    const targetTimeSec = parseTimeToSeconds(targetTimeInput);
    if (targetTimeInput.trim() && targetTimeSec === null) {
      setError(copy.invalidTime);
      return;
    }
    setSaving(true);
    try {
      await onSave({
        goal_kind: goalType,
        race_date: goalType === 'race' ? raceDate : '',
        distance: effectiveDistance,
        target_time_sec: targetTimeSec || 0,
      });
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.failedToSave);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          <div className="space-y-2">
            <Label>{copy.goalType}</Label>
            <ToggleGroup
              value={[goalType]}
              onValueChange={(values) => { if (values.length > 0) setGoalType(values[values.length - 1] as GoalKind); }}
              className="grid grid-cols-1 gap-2 sm:grid-cols-3"
            >
              <ToggleGroupItem value="race" className="flex-col items-start gap-1 h-auto py-3 px-4 data-[pressed]:border-primary data-[pressed]:bg-primary/10">
                <span className="font-semibold text-sm">{copy.race}</span>
                <span className="text-xs text-muted-foreground text-left">{copy.raceDesc}</span>
              </ToggleGroupItem>
              <ToggleGroupItem value="continuous" className="flex-col items-start gap-1 h-auto py-3 px-4 data-[pressed]:border-primary data-[pressed]:bg-primary/10">
                <span className="font-semibold text-sm">{copy.continuous}</span>
                <span className="text-xs text-muted-foreground text-left">{copy.continuousDesc}</span>
              </ToggleGroupItem>
              <ToggleGroupItem value="performance_5k" className="flex-col items-start gap-1 h-auto py-3 px-4 data-[pressed]:border-primary data-[pressed]:bg-primary/10">
                <span className="font-semibold text-sm">{copy.performance}</span>
                <span className="text-xs text-muted-foreground text-left">{copy.performanceDesc}</span>
              </ToggleGroupItem>
            </ToggleGroup>
          </div>

          <div className="space-y-2">
            <Label>{copy.distance}</Label>
            <ToggleGroup
              value={[effectiveDistance]}
              onValueChange={(values) => { if (values.length > 0) setDistance(values[values.length - 1]); }}
              className="grid grid-cols-4 gap-1.5"
              disabled={goalType === 'performance_5k'}
            >
              {distances.map((item) => (
                <ToggleGroupItem key={item.value} value={item.value} className="text-xs data-[pressed]:border-primary data-[pressed]:bg-primary/10 data-[pressed]:text-primary">
                  {item.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          {goalType === 'race' && (
            <div className="space-y-2">
              <Label htmlFor="goal-race-date">{copy.raceDate}</Label>
              <Input id="goal-race-date" type="date" value={raceDate} onChange={(event) => setRaceDate(event.target.value)} placeholder={copy.pickDate} />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="goal-target-time">{copy.targetTime} <span className="text-muted-foreground">({copy.optional})</span></Label>
            <Input id="goal-target-time" type="text" value={targetTimeInput} onChange={(event) => setTargetTimeInput(event.target.value)} placeholder={selected?.placeholder ?? 'H:MM:SS'} className="font-data" />
            <p className="text-[11px] text-muted-foreground">
              {goalType === 'race' ? copy.raceTargetHint : goalType === 'performance_5k' ? copy.performanceHint : copy.continuousHint}
            </p>
          </div>

          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{copy.cancel}</Button>
          <Button onClick={handleSave} disabled={saving}>{saving ? copy.saving : copy.save}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
