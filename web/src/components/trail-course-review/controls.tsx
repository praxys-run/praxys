import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import type {
  TrailClientEnvelope,
  TrailEditableSectionKey,
  TrailSectionKey,
} from '@/types/trail-plan';
import {
  SECTION_ELEMENT_IDS,
  type Option,
} from './model';
import {
  applyUnknownIntent,
  known,
  toggleEnvelopeMember,
  unknown,
} from './transitions';

interface FieldShellProps {
  id: string;
  /** Supply only when the heading labels one real input or Select trigger. */
  htmlFor?: string;
  label: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  invalidMessage?: ReactNode;
  children: ReactNode;
}
interface SectionShellProps {
  sectionKey: TrailSectionKey;
  title: ReactNode;
  description?: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  status?: ReactNode;
  children: ReactNode;
}

interface UnknownButtonProps {
  unknown: boolean;
  label: string;
  onChange: (unknown: boolean) => void;
  disabled?: boolean;
}

interface EnumEditorProps<T extends string> {
  id: string;
  envelope: TrailClientEnvelope<T>;
  options: readonly Option<T>[];
  unknownLabel: string;
  placeholder: string;
  onChange: (value: TrailClientEnvelope<T>) => void;
  disabled?: boolean;
}

interface TriStateEditorProps {
  id: string;
  envelope: TrailClientEnvelope<boolean>;
  yesLabel: string;
  noLabel: string;
  unknownLabel: string;
  onChange: (value: TrailClientEnvelope<boolean>) => void;
  disabled?: boolean;
}

interface MultiSelectEditorProps<T extends string | number> {
  id: string;
  envelope: TrailClientEnvelope<T[]>;
  options: readonly Option<T>[];
  unknownLabel: string;
  emptyLabel?: string;
  allowKnownEmpty?: boolean;
  onChange: (value: TrailClientEnvelope<T[]>) => void;
  disabled?: boolean;
}

interface DurationEditorProps {
  id: string;
  unknown: boolean;
  hours: string;
  minutes: string;
  hoursLabel: string;
  minutesLabel: string;
  unknownLabel: string;
  onUnknownChange: (unknown: boolean) => void;
  onHoursChange: (value: string) => void;
  onMinutesChange: (value: string) => void;
  disabled?: boolean;
}

interface NumberEditorProps {
  id: string;
  value: string;
  unknown: boolean;
  unknownLabel: string;
  inputLabel: string;
  suffix?: string;
  onValueChange: (value: string) => void;
  onUnknownChange: (unknown: boolean) => void;
  disabled?: boolean;
}

interface ConfirmBarProps {
  sectionKey: TrailEditableSectionKey;
  currentRevision: string | null;
  confirmedRevision: string | null;
  dirty: boolean;
  canConfirm: boolean;
  busy: boolean;
  confirmLabel: string;
  confirmedLabel: string;
  changedLabel: string;
  saveFirstLabel: string;
  onConfirm: (key: TrailEditableSectionKey) => void;
}


export function FieldShell({
  id,
  htmlFor,
  label,
  description,
  meta,
  invalidMessage,
  children,
}: FieldShellProps) {
  const describedBy = [
    description ? `${id}-description` : undefined,
    invalidMessage ? `${id}-error` : undefined,
  ].filter(Boolean).join(' ') || undefined;
  return (
    <div className="min-w-0 space-y-2 border-t border-border/70 pt-4 first:border-t-0 first:pt-0">
      {htmlFor ? (
        <Label id={`${id}-label`} htmlFor={htmlFor} className="block whitespace-normal text-sm leading-5">
          {label}
        </Label>
      ) : (
        <h3 id={`${id}-label`} className="whitespace-normal text-sm font-medium leading-5">
          {label}
        </h3>
      )}
      {description ? (
        <p id={`${id}-description`} className="max-w-[72ch] break-words text-xs leading-5 text-muted-foreground dark:text-foreground/80">
          {description}
        </p>
      ) : null}
      <div
        className="min-w-0"
        role="group"
        aria-labelledby={`${id}-label`}
        aria-describedby={describedBy}
        aria-invalid={invalidMessage ? true : undefined}
      >
        {children}
      </div>
      {invalidMessage ? (
        <p id={`${id}-error`} className="text-sm leading-5 text-destructive dark:text-foreground">
          {invalidMessage}
        </p>
      ) : null}
      {meta ? <div className="text-xs leading-5 text-muted-foreground dark:text-foreground/80">{meta}</div> : null}
    </div>
  );
}

export function SectionShell({
  sectionKey,
  title,
  description,
  open,
  onOpenChange,
  status,
  children,
}: SectionShellProps) {
  const contentId = `${SECTION_ELEMENT_IDS[sectionKey]}-content`;
  return (
    <Collapsible
      open={open}
      onOpenChange={onOpenChange}
      className="border-b border-border motion-reduce:transition-none"
    >
      <CollapsibleTrigger
        id={SECTION_ELEMENT_IDS[sectionKey]}
        aria-controls={contentId}
        className="flex min-h-11 w-full min-w-0 items-center justify-between gap-3 py-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <span className="min-w-0 break-words text-base font-semibold leading-6">
          {title}
        </span>
        <span className="shrink-0 text-xs text-muted-foreground dark:text-foreground/80">
          {status ?? (open ? '−' : '+')}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent
        id={contentId}
        className="pb-6 motion-reduce:transition-none"
      >
        {description ? (
          <p className="mb-5 max-w-[72ch] break-words text-sm leading-6 text-muted-foreground dark:text-foreground/80">
            {description}
          </p>
        ) : null}
        <div className="space-y-5">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function UnknownButton({
  unknown: isUnknown,
  label,
  onChange,
  disabled = false,
}: UnknownButtonProps) {
  return (
    <Button
      type="button"
      variant={isUnknown ? 'secondary' : 'outline'}
      aria-pressed={isUnknown}
      disabled={disabled}
      onClick={() => onChange(!isUnknown)}
      className="min-h-11 max-w-full whitespace-normal text-left motion-reduce:transition-none"
    >
      {label}
    </Button>
  );
}

export function EnumEditor<T extends string>({
  id,
  envelope,
  options,
  unknownLabel,
  placeholder,
  onChange,
  disabled = false,
}: EnumEditorProps<T>) {
  return (
    <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start">
      <Select
        value={envelope.state === 'known' ? envelope.value : null}
        onValueChange={(value) => {
          if (typeof value === 'string') onChange(known(value as T));
        }}
        disabled={disabled}
      >
        <SelectTrigger
          id={id}
          aria-labelledby={`${id}-label`}
          className="min-h-11 w-full min-w-0 whitespace-normal sm:max-w-sm motion-reduce:transition-none dark:data-placeholder:text-foreground/80"
        >
          <SelectValue placeholder={placeholder}>
            {envelope.state === 'known'
              ? options.find((option) => option.value === envelope.value)?.label
              : placeholder}
          </SelectValue>
        </SelectTrigger>
        <SelectContent className="motion-reduce:animate-none">
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value} className="min-h-11 whitespace-normal">
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <UnknownButton
        unknown={envelope.state === 'unknown'}
        label={unknownLabel}
        disabled={disabled}
        onChange={(value) => {
          const next = applyUnknownIntent(envelope, value);
          if (next !== envelope) onChange(next);
        }}
      />
    </div>
  );
}

export function TriStateEditor({
  id,
  envelope,
  yesLabel,
  noLabel,
  unknownLabel,
  onChange,
  disabled = false,
}: TriStateEditorProps) {
  const value = envelope.state === 'unknown'
    ? 'unknown'
    : envelope.value
      ? 'yes'
      : 'no';
  return (
    <ToggleGroup
      value={[value]}
      onValueChange={(values) => {
        const selected = values.at(-1);
        if (selected === 'yes') onChange(known(true));
        if (selected === 'no') onChange(known(false));
        if (selected === 'unknown') onChange(unknown<boolean>());
      }}
      aria-labelledby={`${id}-label`}
      disabled={disabled}
      variant="outline"
      spacing={2}
      className="flex w-full min-w-0 flex-wrap gap-2"
    >
      <ToggleGroupItem id={id} value="yes" className="min-h-11 min-w-16 whitespace-normal px-3">
        {yesLabel}
      </ToggleGroupItem>
      <ToggleGroupItem value="no" className="min-h-11 min-w-16 whitespace-normal px-3">
        {noLabel}
      </ToggleGroupItem>
      <ToggleGroupItem value="unknown" className="min-h-11 whitespace-normal px-3">
        {unknownLabel}
      </ToggleGroupItem>
    </ToggleGroup>
  );
}

export function MultiSelectEditor<T extends string | number>({
  id,
  envelope,
  options,
  unknownLabel,
  emptyLabel,
  allowKnownEmpty = false,
  onChange,
  disabled = false,
}: MultiSelectEditorProps<T>) {
  const toggle = (value: T) => {
    const next = toggleEnvelopeMember(envelope, value, allowKnownEmpty);
    if (next !== envelope) onChange(next);
  };
  const values = envelope.state === 'known' ? envelope.value : [];
  return (
    <div className="space-y-2">
      <div role="group" aria-labelledby={`${id}-label`} className="flex min-w-0 flex-wrap gap-2">
        {options.map((option, index) => {
          const selected = values.includes(option.value);
          return (
            <Button
              key={String(option.value)}
              id={index === 0 ? id : undefined}
              type="button"
              variant={selected ? 'secondary' : 'outline'}
              aria-pressed={selected}
              disabled={disabled}
              onClick={() => toggle(option.value)}
              className="min-h-11 max-w-full whitespace-normal text-left motion-reduce:transition-none"
            >
              {option.label}
            </Button>
          );
        })}
        {allowKnownEmpty && emptyLabel ? (
          <Button
            type="button"
            variant={envelope.state === 'known' && values.length === 0 ? 'secondary' : 'outline'}
            aria-pressed={envelope.state === 'known' && values.length === 0}
            disabled={disabled}
            onClick={() => onChange(known([]))}
            className="min-h-11 max-w-full whitespace-normal text-left"
          >
            {emptyLabel}
          </Button>
        ) : null}
      </div>
      <UnknownButton
        unknown={envelope.state === 'unknown'}
        label={unknownLabel}
        disabled={disabled}
        onChange={(value) => {
          const next = applyUnknownIntent(envelope, value);
          if (next !== envelope) onChange(next);
        }}
      />
    </div>
  );
}

export function DurationEditor({
  id,
  unknown: isUnknown,
  hours,
  minutes,
  hoursLabel,
  minutesLabel,
  unknownLabel,
  onUnknownChange,
  onHoursChange,
  onMinutesChange,
  disabled = false,
}: DurationEditorProps) {
  const visuallyUnknown = isUnknown && hours === '' && minutes === '';
  return (
    <div className="space-y-2">
      <div className="grid min-w-0 grid-cols-2 gap-2 sm:max-w-sm">
        <div className="space-y-1.5">
          <Label htmlFor={id} className="text-xs text-muted-foreground dark:text-foreground/80">{hoursLabel}</Label>
          <Input
            id={id}
            inputMode="numeric"
            value={hours}
            disabled={disabled}
            onChange={(event) => onHoursChange(event.target.value)}
            className="h-11 font-data"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-minutes`} className="text-xs text-muted-foreground dark:text-foreground/80">{minutesLabel}</Label>
          <Input
            id={`${id}-minutes`}
            inputMode="numeric"
            value={minutes}
            disabled={disabled}
            onChange={(event) => onMinutesChange(event.target.value)}
            className="h-11 font-data"
          />
        </div>
      </div>
      <UnknownButton
        unknown={visuallyUnknown}
        label={unknownLabel}
        disabled={disabled}
        onChange={(value) => {
          if (value) {
            onHoursChange('');
            onMinutesChange('');
            onUnknownChange(true);
          }
        }}
      />
    </div>
  );
}

export function NumberEditor({
  id,
  value,
  unknown: isUnknown,
  unknownLabel,
  inputLabel,
  suffix,
  onValueChange,
  onUnknownChange,
  disabled = false,
}: NumberEditorProps) {
  const visuallyUnknown = isUnknown && value === '';
  return (
    <div className="space-y-2">
      <div className="flex max-w-sm items-center gap-2">
        <Input
          id={id}
          inputMode="decimal"
          value={value}
          disabled={disabled}
          aria-label={inputLabel}
          onChange={(event) => onValueChange(event.target.value)}
          className="h-11 font-data"
        />
        {suffix ? <span className="shrink-0 font-data text-sm text-muted-foreground dark:text-foreground/80">{suffix}</span> : null}
      </div>
      <UnknownButton
        unknown={visuallyUnknown}
        label={unknownLabel}
        disabled={disabled}
        onChange={(value) => {
          if (value) {
            onValueChange('');
            onUnknownChange(true);
          }
        }}
      />
    </div>
  );
}

export function ConfirmBar({
  sectionKey,
  currentRevision,
  confirmedRevision,
  dirty,
  canConfirm,
  busy,
  confirmLabel,
  confirmedLabel,
  changedLabel,
  saveFirstLabel,
  onConfirm,
}: ConfirmBarProps) {
  const confirmed = !dirty
    && currentRevision !== null
    && confirmedRevision === currentRevision;
  return (
    <div className="flex min-w-0 flex-col gap-2 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="min-w-0 break-all text-xs text-muted-foreground dark:text-foreground/80" aria-live="polite">
        {dirty
          ? changedLabel
          : confirmed
            ? `${confirmedLabel} ${currentRevision}`
            : canConfirm
              ? confirmLabel
              : saveFirstLabel}
      </p>
      <Button
        type="button"
        variant="outline"
        disabled={!canConfirm || busy || confirmed}
        onClick={() => onConfirm(sectionKey)}
        className="min-h-11 whitespace-normal"
      >
        {confirmLabel}
      </Button>
    </div>
  );
}
