import { useLingui } from '@lingui/react/macro';
import type { TrailDraftRequest, TrailDraftResponse } from '@/types/trail-plan';
import { useTrailCourseReviewCopy } from './copy';
import {
  TRAIL_COMPARISON_FIELDS,
  buildTrailComparison,
  trailComparisonFieldValue,
  type ComparisonFieldDefinition,
  type ComparisonFieldKey,
  type ComparisonLabels,
  type ComparisonSnapshot,
} from './comparison-model';
import {
  GRADE_KEYS,
  NUMERIC_INPUT_KEYS_BY_ENVELOPE,
  buildValidatedRequest,
  formatIsoDate,
  type NumericInputKey,
  type NumericInputs,
} from './model';

function NumericValue({ value, unit }: { value: string; unit?: string }) {
  return <span className="whitespace-pre-wrap break-all font-data">{value === '' ? '—' : value}{unit ? ` ${unit}` : ''}</span>;
}

function DurationValue({ inputs, keys, labels }: {
  inputs: NumericInputs;
  keys: readonly NumericInputKey[];
  labels: ComparisonLabels;
}) {
  return (
    <dl className="space-y-1">
      {[labels.copy.hours, labels.copy.minutes].map((label, index) => (
        <div key={label} className="flex min-w-0 flex-wrap gap-x-2">
          <dt>{label}</dt>
          <dd><NumericValue value={inputs[keys[index]]} /></dd>
        </div>
      ))}
    </dl>
  );
}

function ComparisonValue({ fieldKey, snapshot, labels, locale }: {
  fieldKey: ComparisonFieldKey;
  snapshot: ComparisonSnapshot;
  labels: ComparisonLabels;
  locale: string;
}) {
  const { copy, gradeLabels } = labels;
  const { display } = TRAIL_COMPARISON_FIELDS[fieldKey];
  const envelope = trailComparisonFieldValue(snapshot.request, fieldKey);
  const inputKeys = NUMERIC_INPUT_KEYS_BY_ENVELOPE[fieldKey] ?? [];
  const inputs = snapshot.numericInputs;
  const hasBuffer = inputKeys.some((key) => inputs[key] !== '');
  if (envelope === undefined) return copy.noPreference;
  if (!hasBuffer) {
    if (envelope.state === 'unknown') return copy.unknown;
    if (envelope.value === null) return copy.notApplicable;
  }
  // Numeric buffers are the actual editor display, even when incomplete or
  // invalid. Never substitute a validated/stored number for their raw text.
  if (display.kind === 'number') {
    return <NumericValue value={inputs[inputKeys[0]]} unit={'unit' in display ? display.unit : undefined} />;
  }
  if (display.kind === 'duration') {
    return <DurationValue inputs={inputs} keys={inputKeys} labels={labels} />;
  }
  if (display.kind === 'planning-range') {
    return (
      <dl className="space-y-3">
        {[copy.planningMinimum, copy.planningMaximum].map((label, index) => (
          <div key={label}>
            <dt className="font-medium">{label}</dt>
            <dd><DurationValue inputs={inputs} keys={inputKeys.slice(index * 2, index * 2 + 2)} labels={labels} /></dd>
          </div>
        ))}
      </dl>
    );
  }
  if (display.kind === 'grade') {
    return (
      <dl className="space-y-2">
        {GRADE_KEYS.map((key, index) => (
          <div key={key}>
            <dt>{gradeLabels[key]}</dt>
            <dd><NumericValue value={inputs[inputKeys[index]]} unit="%" /></dd>
          </div>
        ))}
      </dl>
    );
  }
  if (envelope.state === 'unknown') return copy.unknown;
  if (display.kind === 'boolean') return envelope.value ? copy.yes : copy.no;
  if (display.kind === 'date') {
    return <span className="font-data">{formatIsoDate(envelope.value as string, locale)}</span>;
  }
  if (display.kind === 'dates') {
    const dates = envelope.value as string[];
    return dates.length
      ? <span className="font-data">{dates.map((date) => formatIsoDate(date, locale)).join(', ')}</span>
      : copy.noDates;
  }
  const options = labels[display.options];
  if (display.kind === 'choice') {
    return options.find((option) => option.value === envelope.value)?.label ?? copy.fieldError;
  }
  const values = envelope.value as Array<string | number>;
  if (!values.length) return 'emptyLabel' in display ? copy[display.emptyLabel] : '—';
  return options.filter((option) => values.includes(option.value)).map((option) => option.label).join(', ');
}

export function TrailPendingComparison({ baseDraft, pendingRequest, pendingInputs, latestDraft }: {
  baseDraft: TrailDraftResponse;
  pendingRequest: TrailDraftRequest;
  pendingInputs: NumericInputs;
  latestDraft: TrailDraftResponse | null;
}) {
  const labels = useTrailCourseReviewCopy();
  const { i18n } = useLingui();
  const comparison = buildTrailComparison(baseDraft, pendingRequest, pendingInputs, latestDraft);
  if (!comparison) return null;
  const { copy } = labels;
  const sides = [
    { label: copy.latestSaved, snapshot: comparison.latest },
    { label: copy.afterRestore, snapshot: comparison.restored },
  ].map((side) => ({
    ...side,
    issues: buildValidatedRequest(side.snapshot.request, side.snapshot.numericInputs).issues,
  }));
  return (
    <div id="trail-pending-comparison" className="min-w-0 border-t border-border">
      {comparison.rows.length === 0 ? (
        <p className="pt-3 text-sm text-muted-foreground dark:text-foreground/80">{copy.noEditableChanges}</p>
      ) : comparison.rows.map((row) => {
        const field: ComparisonFieldDefinition = TRAIL_COMPARISON_FIELDS[row.key];
        return (
          <section key={row.key} className="min-w-0 space-y-2 border-b border-border py-3">
            <h3 className="break-words text-sm font-medium text-foreground">{copy[field.label]}</h3>
            <p className="flex flex-wrap gap-x-3 text-xs text-muted-foreground dark:text-foreground/80">
              {row.pending ? <span>{copy.pending}</span> : null}
              {row.changedOnServer ? <span>{copy.changedOnServer}</span> : null}
            </p>
            <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
              {sides.map((side) => (
                <div key={side.label} className="min-w-0">
                  <dt className="text-xs text-muted-foreground dark:text-foreground/80">{side.label}</dt>
                  <dd className="mt-1 break-words text-sm text-foreground">
                    <ComparisonValue fieldKey={row.key} snapshot={side.snapshot} labels={labels} locale={i18n.locale} />
                    {side.issues.some((issue) => field.issues?.includes(issue.id)) ? (
                      <p className="mt-1 break-words text-sm text-destructive dark:text-foreground">{copy.fieldError}</p>
                    ) : null}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        );
      })}
    </div>
  );
}
