import { useMemo, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  ArrowLeft,
  Check,
  CircleAlert,
  CircleCheck,
  FlaskConical,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Plural, Trans, useLingui } from '@lingui/react/macro';
import { msg } from '@lingui/core/macro';
import type { MessageDescriptor } from '@lingui/core';

import ScienceNote from '@/components/ScienceNote';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Skeleton } from '@/components/ui/skeleton';
import { useApi, apiFetch, extractErrorMessage } from '@/hooks/useApi';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { getChartColors } from '@/lib/chart-theme';
import {
  getMarkerLabelPosition,
  getWetBulbChartDomain,
  getWetBulbPointDomain,
} from '@/lib/labs-environment-chart';
import { cn } from '@/lib/utils';
import type {
  LabsEnvironmentCurvePoint,
  LabsEnvironmentExecution,
  LabsEnvironmentMutationError,
  LabsEnvironmentCurveSupportBin,
  LabsEnvironmentPreflightResponse,
  LabsEnvironmentResponseState,
  LabsEnvironmentWorkloadSupport,
  LabsEnvironmentWetBulbResponse,
} from '@/types/api';

const EVIDENCE_URL =
  'https://github.com/praxys-run/praxys/blob/main/data/science/evidence/personal-environment-response/evidence-personal-environment-response-v1.yaml';
const WORKLOAD_SUPPORT_EVIDENCE_URL =
  'https://github.com/praxys-run/praxys/blob/main/data/science/evidence/environmental-response-workload-support/evidence-environmental-response-workload-support-v1.yaml';
const STULL_URL = 'https://doi.org/10.1175/JAMC-D-11-0143.1';

const REASON_MESSAGES: Record<string, MessageDescriptor> = {
  incomplete_export: msg`The available history could not be analyzed as one complete snapshot.`,
  stale_source_revision: msg`Your source data changed while this result was being computed.`,
  stale_model_version: msg`This result uses an earlier experiment model and needs to be run again.`,
  insufficient_activities: msg`There are not enough eligible Stryd activities yet.`,
  insufficient_segments: msg`There are not enough stable, comparable segments yet.`,
  insufficient_environmental_spread: msg`Your eligible runs do not cover enough different temperature-and-humidity conditions.`,
  insufficient_holdout: msg`There is not enough chronological history to evaluate whether the relationship holds later.`,
  insufficient_curve_bin_support: msg`Some parts of the environmental range do not have enough independent activity support.`,
  insufficient_reference_power_overlap: msg`The same comparable-power range is not represented across enough environmental conditions.`,
  missing_continuous_sample_power: msg`Continuous Stryd sample power is missing from too much of the eligible history.`,
  missing_continuous_heart_rate: msg`Continuous heart-rate samples are missing from too much of the eligible history.`,
  missing_temperature: msg`Temperature is missing from too many otherwise eligible activities.`,
  missing_relative_humidity: msg`Relative humidity is missing from too many otherwise eligible activities.`,
  missing_environment_pairing: msg`Temperature and humidity are not both present on enough of the same activities.`,
  missing_provider_aligned_critical_power: msg`A Stryd-aligned Critical Power value is required for this experiment.`,
  critical_power_provider_mismatch: msg`The available Critical Power does not match the eligible Stryd power regime.`,
  insufficient_sample_coverage: msg`The continuous sample coverage is too sparse for a stable comparison.`,
  insufficient_prerequisite_overlap: msg`Enough activities exist overall, but the required environment, power, and heart-rate data do not overlap on enough of the same runs.`,
  mixed_power_regime: msg`The eligible history crosses incompatible power-device or algorithm regimes.`,
  unsupported_power_provider: msg`This first experiment currently supports continuous Stryd power only.`,
  unverified_garmin_wrist_power: msg`Garmin wrist-power origin cannot yet be verified well enough for this experiment.`,
  bootstrap_unstable: msg`The estimated direction changes too much when activities are resampled.`,
  sensitivity_unstable: msg`Reasonable model variations do not preserve the same historical relationship.`,
  influential_activity: msg`A single activity has too much influence on the result.`,
  prediction_unavailable: msg`The chronological prediction check could not be evaluated, so Praxys withholds the fitted curve.`,
  analysis_retry_exhausted: msg`The analysis worker could not complete the model after repeated infrastructure attempts.`,
  analysis_failed: msg`The analysis did not finish successfully.`,
  provider_alignment_requires_full_analysis: msg`Your history includes enough broad sample coverage, but the full analysis must confirm that power, heart rate, and Critical Power use one compatible Stryd regime.`,
};

function SelectionCheck({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex min-h-11 w-full items-start gap-3 rounded-lg border border-border px-3 py-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <span
        className={cn(
          'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border',
          checked ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card',
        )}
      >
        {checked && <Check className="h-3.5 w-3.5" />}
      </span>
      <span className="text-sm leading-relaxed text-foreground">{children}</span>
    </button>
  );
}

function LabsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-4 w-full max-w-2xl" />
      </div>
      <Skeleton className="h-52 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(280px,0.7fr)]">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </div>
  );
}

function statusLabel(state: LabsEnvironmentResponseState): MessageDescriptor {
  if (state.execution.job_status === 'retrying') return msg`Retrying`;
  if (state.execution.job_status === 'dispatched') return msg`Queued`;
  if (state.execution.job_status === 'processing') return msg`Processing`;
  if (
    state.execution.job_status === 'failed'
    || state.execution.job_status === 'dead_lettered'
  ) {
    return msg`Needs retry`;
  }

  const labels: Record<LabsEnvironmentResponseState['status'], MessageDescriptor> = {
    not_enrolled: msg`Not enrolled`,
    queued: msg`Queued`,
    processing: msg`Processing`,
    available: msg`Available`,
    unavailable: msg`Unavailable`,
    failed: msg`Failed`,
    stale: msg`Needs recompute`,
  };
  return labels[state.status];
}

function formatLocalDateTime(value: string | null, locale: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(parsed);
}

function createIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

type LabsMutationAction = 'enroll' | 'recompute';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isLabsMutationError(
  value: unknown,
): value is LabsEnvironmentMutationError {
  if (!isRecord(value) || typeof value.code !== 'string') return false;
  if (value.code === 'adult_eligibility_not_confirmed') {
    return (
      typeof value.category === 'string'
      && typeof value.public_message_key === 'string'
      && typeof value.required_guardrail === 'string'
      && typeof value.user_actionable === 'boolean'
      && typeof value.suggested_action_key === 'string'
      && typeof value.analysis_stage === 'string'
      && typeof value.power_regime === 'string'
      && typeof value.model_version === 'string'
      && typeof value.correlation_id === 'string'
    );
  }
  if (value.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE') {
    return (
      isRecord(value.preflight)
      && typeof value.preflight.can_start_analysis === 'boolean'
      && typeof value.preflight.status === 'string'
    );
  }
  if (value.code === 'consent_version_stale') {
    return typeof value.current_consent_version === 'string';
  }
  if (value.code === 'LABS_ENVIRONMENT_NOT_ENROLLED') {
    return typeof value.message === 'string';
  }
  if (
    value.code === 'LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN'
    || value.code === 'LABS_ENVIRONMENT_RECOMPUTE_DAILY_LIMIT'
  ) {
    return (
      typeof value.message === 'string'
      && typeof value.available_at === 'string'
      && typeof value.retry_after_seconds === 'number'
    );
  }
  return false;
}

function ExecutionProgress({
  execution,
  onWithdraw,
  withdrawDisabled,
}: {
  execution: LabsEnvironmentExecution;
  onWithdraw: () => void;
  withdrawDisabled: boolean;
}) {
  const retrying = execution.job_status === 'retrying';
  const dispatched = execution.job_status === 'dispatched';
  const processing = execution.job_status === 'processing';

  return (
    <Card>
      <CardContent className="flex flex-col gap-5 py-8 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          {retrying ? (
            <RefreshCw className="mt-0.5 h-5 w-5 shrink-0 text-accent-amber motion-safe:animate-spin motion-reduce:animate-none" />
          ) : (
            <Loader2 className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-primary motion-reduce:animate-none" />
          )}
          <div aria-live="polite">
            <h2 className={cn('font-semibold', retrying && 'text-accent-amber')}>
              {retrying
                ? <Trans>Temporary service issue; retry queued</Trans>
                : processing
                  ? <Trans>Analysis worker is running</Trans>
                  : dispatched
                    ? <Trans>Queued for the analysis worker</Trans>
                    : <Trans>Analysis request saved</Trans>}
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {retrying ? (
                <Trans>A temporary infrastructure problem interrupted the previous attempt. Praxys kept the request and will retry automatically.</Trans>
              ) : processing ? (
                <Trans>The isolated worker is building the aggregate response from your eligible activity data.</Trans>
              ) : (
                <Trans>Your request is stored durably and will run separately from the app.</Trans>
              )}
            </p>
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              <Trans>You can leave this page and return later. No action is needed while the analysis runs.</Trans>
            </p>
            {execution.attempt_count > 0 && (
              <p className="font-data mt-3 text-xs text-muted-foreground">
                <Trans>Attempt</Trans> {execution.attempt_count}
              </p>
            )}
          </div>
        </div>
        <Button variant="ghost" onClick={onWithdraw} disabled={withdrawDisabled}>
          <Trans>Cancel and withdraw</Trans>
        </Button>
      </CardContent>
    </Card>
  );
}

function RecomputePolicy({ execution }: { execution: LabsEnvironmentExecution }) {
  const { i18n } = useLingui();
  const policy = execution.recompute;
  const availableAt = formatLocalDateTime(policy.available_at, i18n.locale);

  return (
    <div className="space-y-1 text-xs leading-relaxed text-muted-foreground" aria-live="polite">
      {policy.reason === 'cooldown' && (
        <>
          <p className="font-medium text-accent-amber"><Trans>Recompute cooling down</Trans></p>
          {availableAt && (
            <p>
              <Trans>Recompute available again</Trans>:{' '}
              <span className="font-data text-foreground">{availableAt}</span>
            </p>
          )}
          <p><Trans>The cooldown prevents accidental repeat analysis.</Trans></p>
        </>
      )}
      {policy.reason === 'daily_limit' && (
        <>
          <p className="font-medium text-accent-amber"><Trans>Rolling recompute limit reached</Trans></p>
          {availableAt && (
            <p>
              <Trans>Recompute available again</Trans>:{' '}
              <span className="font-data text-foreground">{availableAt}</span>
            </p>
          )}
          <p><Trans>The rolling limit protects the shared analysis capacity from repeated requests.</Trans></p>
        </>
      )}
      {policy.allowed && (
        <p>
          <span className="font-data font-medium text-foreground">{policy.remaining_requests}</span>{' '}
          <Trans>manual recomputes remaining</Trans>
          {' · '}
          <span className="font-data text-foreground">{policy.window_hours}</span>{' '}
          <Trans>hour rolling window</Trans>
        </p>
      )}
    </div>
  );
}

function PreflightSummary({
  preflight,
  loading,
  error,
  onRetry,
}: {
  preflight: LabsEnvironmentPreflightResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const { i18n } = useLingui();
  if (loading && !preflight) {
    return (
      <Alert>
        <Loader2 className="h-4 w-4 animate-spin text-primary motion-reduce:animate-none" />
        <AlertTitle><Trans>Checking data requirements</Trans></AlertTitle>
        <AlertDescription>
          <Trans>Praxys checks the required environment, Stryd power, heart-rate, and Critical Power coverage before showing enrollment consent or starting analysis.</Trans>
        </AlertDescription>
      </Alert>
    );
  }
  if (error || !preflight) {
    return (
      <Alert variant="destructive">
        <AlertTitle><Trans>Eligibility check could not load</Trans></AlertTitle>
        <AlertDescription>
          <Trans>Retry before joining. The full analysis has not started.</Trans>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={onRetry}
          >
            <RefreshCw className="h-4 w-4" />
            <Trans>Retry</Trans>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const blocked = preflight.status === 'ineligible';
  const uncertain = preflight.status === 'needs_full_analysis';
  const reason = preflight.reason_code
    ? i18n._(REASON_MESSAGES[preflight.reason_code] ?? msg`The quick check found a data requirement that needs attention.`)
    : null;
  return (
    <Alert variant={blocked ? 'destructive' : 'default'} className={uncertain ? 'border-accent-cobalt/40' : undefined}>
      {blocked
        ? <CircleAlert className="h-4 w-4" />
        : <CircleCheck className={uncertain ? 'h-4 w-4 text-accent-cobalt' : 'h-4 w-4 text-primary'} />}
      <AlertTitle>
        {blocked
          ? <Trans>Not enough suitable data to start yet</Trans>
          : uncertain
            ? <Trans>Full analysis must confirm eligibility</Trans>
            : <Trans>Enough source data to attempt the experiment</Trans>}
      </AlertTitle>
      <AlertDescription className="space-y-2">
        {reason && <p>{reason}</p>}
        <p>
          {blocked
            ? <Trans>Praxys stopped before consent or long-running analysis. Sync or collect the missing data, then retry this check.</Trans>
            : <Trans>This quick check only covers definite prerequisites. The full analysis can still return insufficient support, an unstable association, or no conclusion.</Trans>}
        </p>
        <p className="font-data text-xs">
          <Trans>Activities passing quick prerequisites</Trans>:{' '}
          {Math.min(
            preflight.observed.complete_stryd_activity_count,
            preflight.observed.provider_aligned_cp_activity_count,
          )}
          {' / '}
          <Trans>minimum</Trans>: {preflight.minimum_activity_count}
        </p>
      </AlertDescription>
    </Alert>
  );
}

function ResultChart({
  points,
  supportBins,
  calculatorWetBulb,
}: {
  points: LabsEnvironmentCurvePoint[];
  supportBins: LabsEnvironmentCurveSupportBin[];
  calculatorWetBulb: number | null;
}) {
  const { i18n } = useLingui();
  const { resolved } = useTheme();
  const colors = getChartColors(resolved === 'dark');
  const pointsByBin = new Map(
    points.map((point) => [point.support_bin_index, point]),
  );
  const data = supportBins.length
    ? supportBins.map((bin) => {
      const point = pointsByBin.get(bin.bin_index);
      return {
        wet_bulb_c:
          (bin.lower_wet_bulb_c + bin.upper_wet_bulb_c) / 2,
        relative_hr_bpm: point?.relative_hr_bpm ?? null,
        bandBase: point?.relative_lower_bpm ?? null,
        bandSize: point
          ? point.relative_upper_bpm - point.relative_lower_bpm
          : null,
      };
    })
    : points.map((point) => ({
      ...point,
      bandBase: point.relative_lower_bpm,
      bandSize: point.relative_upper_bpm - point.relative_lower_bpm,
    }));
  const chartDomain =
    getWetBulbChartDomain(supportBins) ?? getWetBulbPointDomain(points);
  const markerVisible =
    calculatorWetBulb != null &&
    (
      supportBins.length
        ? supportBins.some(
          (bin) => (
            bin.supported &&
            calculatorWetBulb >= bin.lower_wet_bulb_c &&
            calculatorWetBulb <= bin.upper_wet_bulb_c
          ),
        )
        : chartDomain != null &&
          calculatorWetBulb >= chartDomain[0] &&
          calculatorWetBulb <= chartDomain[1]
    );
  const markerLabelPosition =
    calculatorWetBulb != null && chartDomain != null
      ? getMarkerLabelPosition(calculatorWetBulb, chartDomain)
      : 'insideTopRight';

  return (
    <div
      className="h-[320px] w-full"
      role="img"
      aria-label={i18n._(msg`Historical environmental-response curve`)}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 16, right: 18, bottom: 10, left: 0 }}>
          <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="wet_bulb_c"
            type="number"
            domain={chartDomain ?? ['dataMin', 'dataMax']}
            tick={{ fill: colors.tick, fontSize: 12 }}
            tickFormatter={(value) => `${Number(value).toFixed(1)}°`}
            label={{
              value: i18n._(msg`Stull psychrometric wet-bulb proxy (°C)`),
              position: 'insideBottom',
              offset: -6,
              fill: colors.tick,
              fontSize: 11,
            }}
          />
          <YAxis
            tick={{ fill: colors.tick, fontSize: 12 }}
            tickFormatter={(value) => `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}`}
            label={{
              value: i18n._(msg`Relative modeled HR (bpm)`),
              angle: -90,
              position: 'insideLeft',
              fill: colors.tick,
              fontSize: 11,
            }}
          />
          <Tooltip
            contentStyle={{
              background: colors.tooltipBg,
              borderColor: colors.tooltipBorder,
              borderRadius: 8,
            }}
            labelFormatter={(value) => `${Number(value).toFixed(1)} °C ${i18n._(msg`wet-bulb proxy`)}`}
            formatter={(value, name) => {
              if (name === 'bandSize' || name === 'bandBase') return null;
              const numeric = Number(value);
              return [
                `${numeric > 0 ? '+' : ''}${numeric.toFixed(1)} bpm`,
                i18n._(msg`Relative modeled HR`),
              ];
            }}
          />
          <Area
            type="monotone"
            dataKey="bandBase"
            stackId="uncertainty"
            stroke="none"
            fill="transparent"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="bandSize"
            stackId="uncertainty"
            stroke="none"
            fill={colors.form}
            fillOpacity={0.14}
            isAnimationActive={false}
          />
          <ReferenceLine y={0} stroke={colors.grid} />
          {markerVisible && (
            <ReferenceLine
              x={calculatorWetBulb as number}
              stroke={colors.threshold}
              strokeDasharray="4 4"
              label={{
                value: i18n._(msg`Calculator`),
                fill: colors.threshold,
                fontSize: 11,
                position: markerLabelPosition,
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="relative_hr_bpm"
            stroke={colors.form}
            strokeWidth={2.5}
            dot={{ r: 3, fill: colors.form }}
            activeDot={{ r: 5 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function SupportLedger({
  bins,
  workloadSupport,
}: {
  bins: LabsEnvironmentCurveSupportBin[];
  workloadSupport: LabsEnvironmentWorkloadSupport | null;
}) {
  if (!bins.length) return null;
  const referenceMinimum = Math.max(
    ...bins.map((bin) => bin.required_reference_power_activity_count),
  );
  return (
    <section className="mt-5 border-t border-border pt-5" aria-labelledby="curve-support-heading">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <div>
          <h2 id="curve-support-heading" className="text-sm font-semibold">
            <Trans>Comparable-power activity support</Trans>
          </h2>
          {workloadSupport?.personal_display_pct_cp.length === 2 && (
            <p className="font-data mt-1 text-xs text-muted-foreground">
              <Trans>Your comparable range</Trans>:{' '}
              {workloadSupport.personal_display_pct_cp[0].toFixed(1)}–
              {workloadSupport.personal_display_pct_cp[1].toFixed(1)}% CP
            </p>
          )}
        </div>
        <p className="font-data text-xs text-muted-foreground">
          <Trans>minimum {referenceMinimum} per environmental range</Trans>
        </p>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {bins.map((bin) => {
          const missingReference = Math.max(
            bin.required_reference_power_activity_count
              - bin.reference_power_activity_count,
            0,
          );
          const referenceOnlyFailure =
            bin.support_failure_reasons.length === 1
            && bin.support_failure_reasons[0]
              === 'insufficient_reference_power_activities';
          return (
            <div
              key={bin.bin_index}
              className={cn(
                'rounded-lg border px-3 py-3',
                bin.supported
                  ? 'border-primary/25 bg-primary/5'
                  : 'border-accent-amber/45 bg-accent-amber/10',
              )}
            >
              <p className="font-data text-[11px] text-muted-foreground">
                {bin.lower_wet_bulb_c.toFixed(1)}–{bin.upper_wet_bulb_c.toFixed(1)} °C
              </p>
              <p className="font-data mt-2 text-sm font-semibold">
                <Plural
                  value={bin.reference_power_activity_count}
                  one="# activity"
                  other="# activities"
                />
              </p>
              <p
                className={cn(
                  'mt-1 text-xs font-medium',
                  bin.supported ? 'text-primary' : 'text-accent-amber',
                )}
              >
                {bin.supported
                  ? <Trans>Supported</Trans>
                  : referenceOnlyFailure
                    ? <Trans>Needs {missingReference} more</Trans>
                    : <Trans>Insufficient support</Trans>}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        <Trans>Each activity counts once per environmental range. The comparable-power range is centered on your typical eligible stable training workload; raw sample points alone do not count.</Trans>
      </p>
    </section>
  );
}

function CoverageSummary({ state }: { state: LabsEnvironmentResponseState }) {
  const counts = state.result?.eligibility_counts;
  const observed = counts?.observed_wet_bulb_domain_c
    ?? state.availability_reason?.observed_aggregate?.observed_wet_bulb_domain_c;
  const activityCount = counts?.eligible_activity_count
    ?? state.availability_reason?.observed_aggregate?.eligible_activity_count;
  const segmentCount = counts?.eligible_segment_count
    ?? state.availability_reason?.observed_aggregate?.eligible_segment_count;
  const workloadSupport = counts?.workload_support;

  if (activityCount == null && segmentCount == null && !observed) return null;
  return (
    <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <p className="text-xs text-muted-foreground"><Trans>Eligible activities</Trans></p>
        <p className="font-data mt-1 text-lg font-semibold">{activityCount ?? '—'}</p>
      </div>
      <div>
        <p className="text-xs text-muted-foreground"><Trans>Stable segments</Trans></p>
        <p className="font-data mt-1 text-lg font-semibold">{segmentCount ?? '—'}</p>
      </div>
      <div>
        <p className="text-xs text-muted-foreground"><Trans>Observed proxy range</Trans></p>
        <p className="font-data mt-1 text-lg font-semibold">
          {observed?.length === 2
            ? `${observed[0].toFixed(1)}–${observed[1].toFixed(1)} °C`
            : '—'}
        </p>
      </div>
      {workloadSupport?.personal_display_pct_cp.length === 2 && (
        <div>
          <p className="text-xs text-muted-foreground"><Trans>Your comparable power range</Trans></p>
          <p className="font-data mt-1 text-lg font-semibold">
            {workloadSupport.personal_display_pct_cp[0].toFixed(1)}–
            {workloadSupport.personal_display_pct_cp[1].toFixed(1)}% CP
          </p>
        </div>
      )}
    </div>
  );
}

function WetBulbCalculator({
  state,
  onResult,
}: {
  state: LabsEnvironmentResponseState;
  onResult: (value: number | null) => void;
}) {
  const { i18n } = useLingui();
  const [temperature, setTemperature] = useState('25');
  const [humidity, setHumidity] = useState('60');
  const [result, setResult] = useState<LabsEnvironmentWetBulbResponse | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState('');
  const observedDomain =
    state.result?.eligibility_counts.observed_wet_bulb_domain_c;
  const displayedDomains =
    state.result?.eligibility_counts.displayed_wet_bulb_domains_c ?? [];

  const calculate = async () => {
    const temperatureValue = Number(temperature);
    const humidityValue = Number(humidity);
    if (!Number.isFinite(temperatureValue) || !Number.isFinite(humidityValue)) {
      setError(i18n._(msg`Enter numeric temperature and humidity values.`));
      return;
    }
    setCalculating(true);
    setError('');
    try {
      const response = await apiFetch('/api/labs/environment-response/wet-bulb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          temperature_c: temperatureValue,
          relative_humidity_pct: humidityValue,
        }),
      });
      if (!response.ok) {
        setError(await extractErrorMessage(
          response,
          i18n._(msg`Could not calculate the wet-bulb proxy.`),
        ));
        return;
      }
      const payload = await response.json() as LabsEnvironmentWetBulbResponse;
      setResult(payload);
      onResult(payload.wet_bulb_c);
    } catch {
      setError(i18n._(msg`Could not calculate the wet-bulb proxy.`));
    } finally {
      setCalculating(false);
    }
  };

  const position =
    result?.wet_bulb_c != null && observedDomain?.length === 2
      ? displayedDomains.some(
        (domain) => (
          domain.length === 2 &&
          result.wet_bulb_c! >= domain[0] &&
          result.wet_bulb_c! <= domain[1]
        ),
      )
        ? 'inside'
        : result.wet_bulb_c < observedDomain[0]
        ? 'below'
        : result.wet_bulb_c > observedDomain[1]
          ? 'above'
          : 'unsupported'
      : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle><Trans>Wet-bulb proxy calculator</Trans></CardTitle>
        <p className="text-sm leading-relaxed text-muted-foreground">
          <Trans>Combine air temperature and relative humidity using the same Stull estimate as the experiment.</Trans>
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="labs-temperature"><Trans>Temperature (°C)</Trans></Label>
            <Input
              id="labs-temperature"
              inputMode="decimal"
              value={temperature}
              onChange={(event) => setTemperature(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="labs-humidity"><Trans>Humidity (%)</Trans></Label>
            <Input
              id="labs-humidity"
              inputMode="decimal"
              value={humidity}
              onChange={(event) => setHumidity(event.target.value)}
            />
          </div>
        </div>
        <Button variant="outline" className="w-full" onClick={calculate} disabled={calculating}>
          {calculating && <Loader2 className="h-4 w-4 animate-spin" />}
          <Trans>Calculate proxy</Trans>
        </Button>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {result && (
          <div className="border-t border-border pt-5">
            {result.wet_bulb_c == null ? (
              <p className="text-sm leading-relaxed text-amber-700 dark:text-amber-300">
                <Trans>This combination is outside Praxys’s conservative Stull method domain.</Trans>
              </p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground"><Trans>Estimated psychrometric wet-bulb proxy</Trans></p>
                <p className="font-data mt-1 text-3xl font-semibold">{result.wet_bulb_c.toFixed(1)} °C</p>
                {position === 'inside' && (
                  <p className="mt-2 text-sm text-muted-foreground">
                    <Trans>This sits inside your displayed historical range and is marked on the curve.</Trans>
                  </p>
                )}
                {position === 'below' && (
                  <p className="mt-2 text-sm text-muted-foreground">
                    <Trans>This is below your displayed historical range, so the curve does not extrapolate to it.</Trans>
                  </p>
                )}
                {position === 'above' && (
                  <p className="mt-2 text-sm text-muted-foreground">
                    <Trans>This is above your displayed historical range, so the curve does not extrapolate to it.</Trans>
                  </p>
                )}
                {position === 'unsupported' && (
                  <p className="mt-2 text-sm text-muted-foreground">
                    <Trans>This falls in an unsupported historical range, so it is not marked on the curve.</Trans>
                  </p>
                )}
              </>
            )}
          </div>
        )}
        <ScienceNote sourceUrl={STULL_URL} sourceLabel="Stull (2011)">
          <p>
            <Trans>This is Stull’s psychrometric estimate from air temperature and relative humidity. It is not apparent temperature, natural wet bulb, outdoor WBGT, body temperature, or a heat-safety assessment.</Trans>
          </p>
        </ScienceNote>
      </CardContent>
    </Card>
  );
}

function Enrollment({
  state,
  preflight,
  preflightLoading,
  preflightError,
  onRetryPreflight,
  isDemo,
  busy,
  onEnroll,
}: {
  state: LabsEnvironmentResponseState;
  preflight: LabsEnvironmentPreflightResponse | null;
  preflightLoading: boolean;
  preflightError: string | null;
  onRetryPreflight: () => void;
  isDemo: boolean;
  busy: boolean;
  onEnroll: (adultAttested: boolean) => void;
}) {
  const [adult, setAdult] = useState(false);
  const [consent, setConsent] = useState(false);
  return (
    <Card>
      <CardHeader>
        <CardTitle><Trans>Join this personal experiment</Trans></CardTitle>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
          <Trans>Praxys will analyze eligible past runs to see whether modeled heart rate varied with temperature-and-humidity conditions at comparable recorded Stryd power.</Trans>
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <PreflightSummary
          preflight={preflight}
          loading={preflightLoading}
          error={preflightError}
          onRetry={onRetryPreflight}
        />
        <div className="grid gap-5 md:grid-cols-3">
          <div>
            <p className="font-medium"><Trans>Personal only</Trans></p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              <Trans>Your result is not pooled with other users and is not donated to cohort research.</Trans>
            </p>
          </div>
          <div>
            <p className="font-medium"><Trans>Aggregate storage</Trans></p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              <Trans>Praxys stores curve points, uncertainty, counts, gates, versions, and timestamps—not routes, activity dates, raw samples, or per-activity research rows.</Trans>
            </p>
          </div>
          <div>
            <p className="font-medium"><Trans>Withdraw anytime</Trans></p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              <Trans>Withdrawal immediately deletes experiment consent and the derived result. Your ordinary account activities remain unchanged.</Trans>
            </p>
          </div>
        </div>
        <Alert>
          <ShieldCheck className="h-4 w-4 text-accent-cobalt" />
          <AlertTitle><Trans>What this can—and cannot—tell you</Trans></AlertTitle>
          <AlertDescription>
            <Trans>This is a retrospective historical association. It does not forecast a future run, prove that heat caused a heart-rate change, prescribe pace, measure adaptation or hydration, or assess heat safety.</Trans>
          </AlertDescription>
        </Alert>
        {!preflightLoading && !preflightError && preflight && (
          <>
            <div className="space-y-3">
              <SelectionCheck checked={adult} onChange={setAdult}>
                <Trans>I confirm that I am 18 or older. Praxys records this attestation, not my birth date.</Trans>
              </SelectionCheck>
              <SelectionCheck checked={consent} onChange={setConsent}>
                <Trans>I understand the purpose, limits, storage, and withdrawal terms above and choose to participate in this experiment.</Trans>
              </SelectionCheck>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Button
                onClick={() => onEnroll(adult)}
                disabled={
                  !adult
                  || !consent
                  || busy
                  || isDemo
                  || !preflight.can_start_analysis
                }
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                <Trans>Join and analyze my history</Trans>
              </Button>
              {isDemo && (
                <p className="text-sm text-muted-foreground">
                  <Trans>Demo accounts are read-only and cannot join Labs.</Trans>
                </p>
              )}
            </div>
          </>
        )}
        <ScienceNote
          label={<Trans>Why this remains experimental</Trans>}
          sourceUrl={EVIDENCE_URL}
          sourceLabel="Praxys evidence review"
        >
          <p>
            <Trans>The accepted Praxys evidence review found controlled support for heat-related cardiovascular drift, but no field study validating a causal or predictive personal Stull wet-bulb response curve. V1 is therefore descriptive and Stryd-only.</Trans>
          </p>
        </ScienceNote>
        <p className="font-data text-[11px] text-muted-foreground">
          <Trans>Consent text version</Trans>: {state.consent_version}
        </p>
      </CardContent>
    </Card>
  );
}

export default function LabsEnvironment() {
  const { i18n } = useLingui();
  const { isDemo } = useAuth();
  const { data: state, loading, error, refetch } = useApi<LabsEnvironmentResponseState>(
    '/api/labs/environment-response',
    { refetchInterval: 5000, refetchOnMount: 'always' },
  );
  const {
    data: preflight,
    loading: preflightLoading,
    error: preflightError,
    refetch: refetchPreflight,
  } = useApi<LabsEnvironmentPreflightResponse>(
    '/api/labs/environment-response/preflight',
    { timeoutMs: 15000 },
  );
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [calculatorWetBulb, setCalculatorWetBulb] = useState<number | null>(null);
  const idempotencyKeys = useRef<Partial<Record<LabsMutationAction, string>>>({});
  const availabilityReasonCode = state?.availability_reason?.code;

  const reason = useMemo(() => {
    if (!availabilityReasonCode) return null;
    return REASON_MESSAGES[availabilityReasonCode]
      ? i18n._(REASON_MESSAGES[availabilityReasonCode])
      : i18n._(msg`This result did not pass the experiment’s release guardrails.`);
  }, [availabilityReasonCode, i18n]);

  const actionErrorMessage = (
    detail: LabsEnvironmentMutationError | null,
  ): string | null => {
    if (!detail) return null;
    const availableAt = 'available_at' in detail
      ? formatLocalDateTime(detail.available_at, i18n.locale)
      : null;
    if (detail.code === 'LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN') {
      return availableAt
        ? i18n._(msg`Recompute is cooling down. Try again after ${availableAt}.`)
        : i18n._(msg`Recompute is cooling down. Try again later.`);
    }
    if (detail.code === 'LABS_ENVIRONMENT_RECOMPUTE_DAILY_LIMIT') {
      return availableAt
        ? i18n._(msg`The rolling recompute limit has been reached. Try again after ${availableAt}.`)
        : i18n._(msg`The rolling recompute limit has been reached. Try again later.`);
    }
    if (detail.code === 'adult_eligibility_not_confirmed') {
      return i18n._(msg`Confirm that you are 18 or older to join this experiment.`);
    }
    if (detail.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE') {
      return i18n._(msg`The quick check found a data requirement that needs attention.`);
    }
    if (detail.code === 'consent_version_stale') {
      return i18n._(msg`The consent text changed. Review and confirm the current version.`);
    }
    if (detail.code === 'LABS_ENVIRONMENT_NOT_ENROLLED') {
      return i18n._(msg`Not enrolled`);
    }
    return null;
  };

  const mutate = async (
    path: string,
    method: 'POST' | 'DELETE',
    body?: unknown,
    action?: LabsMutationAction,
  ) => {
    setBusy(true);
    setActionError('');
    const idempotencyKey = action
      ? (idempotencyKeys.current[action] ??= createIdempotencyKey())
      : null;
    try {
      const response = await apiFetch(path, {
        method,
        headers: {
          ...(body ? { 'Content-Type': 'application/json' } : {}),
          ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        const errorResponse = response.clone();
        let parsedDetail: LabsEnvironmentMutationError | null = null;
        try {
          const payload: unknown = await response.json();
          parsedDetail = (
            isRecord(payload)
            && isLabsMutationError(payload.detail)
          )
            ? payload.detail
            : null;
        } catch {
          parsedDetail = null;
        }
        setActionError(
          actionErrorMessage(parsedDetail)
          ?? await extractErrorMessage(
            errorResponse,
            i18n._(msg`Request failed. Try again.`),
          ),
        );
        if (action && response.status < 500) {
          delete idempotencyKeys.current[action];
        }
        if (response.status === 429) {
          await refetch();
        } else if (
          response.status === 409
          && (
            parsedDetail?.code === 'LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE'
            || parsedDetail?.code === 'consent_version_stale'
            || parsedDetail?.code === 'LABS_ENVIRONMENT_NOT_ENROLLED'
          )
        ) {
          await Promise.all([refetch(), refetchPreflight()]);
        }
        return false;
      }
      if (action) {
        delete idempotencyKeys.current[action];
      }
      await refetch();
      return true;
    } catch {
      setActionError(i18n._(msg`Network error. Try again.`));
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (loading || !state) {
    if (error) {
      return (
        <Alert variant="destructive">
          <AlertTitle><Trans>Labs could not load</Trans></AlertTitle>
          <AlertDescription className="mt-2">
            <p>{error}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
              <Trans>Retry</Trans>
            </Button>
          </AlertDescription>
        </Alert>
      );
    }
    return <LabsSkeleton />;
  }

  const processing = state.status === 'queued' || state.status === 'processing';
  const available = state.status === 'available' && state.result?.result_state === 'historical_association_only';
  const retryExhausted =
    state.availability_reason?.code === 'analysis_retry_exhausted';
  const points = available ? state.result?.aggregate_curve_points ?? [] : [];
  const supportBins =
    state.result?.eligibility_counts.curve_support_bins ?? [];
  const workloadSupport =
    state.result?.eligibility_counts.workload_support ?? null;
  const partialDomain = supportBins.some((bin) => !bin.supported);
  const uncertainty = state.result?.aggregate_uncertainty;

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-5 border-b border-border pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Button
            render={<Link to="/labs" />}
            nativeButton={false}
            variant="ghost"
            size="sm"
            className="-ml-3 mb-3 w-fit text-muted-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            <Trans>All experiments</Trans>
          </Button>
          <h1 className="text-3xl font-semibold tracking-tight"><Trans>Environmental response</Trans></h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            <Trans>Voluntary experiments that help you inspect your own training history without turning early research into advice.</Trans>
          </p>
        </div>
        <Badge variant="outline" className="w-fit font-data">
          {i18n._(statusLabel(state))}
        </Badge>
      </header>

      {state.status === 'not_enrolled' ? (
        <>
          <Enrollment
            key={state.consent_version}
            state={state}
            preflight={preflight}
            preflightLoading={preflightLoading}
            preflightError={preflightError}
            onRetryPreflight={() => void refetchPreflight()}
            isDemo={isDemo}
            busy={busy}
            onEnroll={(adultAttested) => void mutate(
              '/api/labs/environment-response',
              'POST',
              {
                adult_attested: adultAttested,
                consent_version: state.consent_version,
              },
              'enroll',
            )}
          />
          <WetBulbCalculator state={state} onResult={setCalculatorWetBulb} />
        </>
      ) : (
        <>
          {processing && (
            <ExecutionProgress
              execution={state.execution}
              onWithdraw={() => setWithdrawOpen(true)}
              withdrawDisabled={busy || isDemo}
            />
          )}

          {available && (
            <Alert className="border-accent-cobalt/40 bg-accent-cobalt/5">
              <FlaskConical className="h-4 w-4 text-accent-cobalt" />
              <AlertTitle>
                {state.result?.prediction_status === 'passed_research_diagnostics'
                  ? <Trans>Passed research diagnostics; not a forecast</Trans>
                  : <Trans>Historical association; not predictively validated</Trans>}
              </AlertTitle>
              <AlertDescription>
                {state.result?.prediction_status === 'passed_research_diagnostics'
                  ? <Trans>The chronological holdout and sensitivity checks passed, but this personal historical association is still not a clinical claim or future-condition forecast.</Trans>
                  : <Trans>One or more research diagnostics did not support predictive interpretation. Read the curve only as a pattern in eligible past runs.</Trans>}
              </AlertDescription>
            </Alert>
          )}

          {(state.status === 'unavailable' || state.status === 'failed' || state.status === 'stale') && (
            <Card>
              <CardHeader>
                <CardTitle>
                  {retryExhausted
                    ? <Trans>Analysis needs a manual retry</Trans>
                    : state.status === 'stale'
                    ? <Trans>Your result needs recomputing</Trans>
                    : state.status === 'failed'
                      ? <Trans>The analysis did not finish</Trans>
                      : <Trans>No curve is available yet</Trans>}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{reason}</p>
                <CoverageSummary state={state} />
                {state.availability_reason?.correlation_id && (
                  <p className="font-data text-[11px] text-muted-foreground">
                    <Trans>Support ID</Trans>: {state.availability_reason.correlation_id}
                  </p>
                )}
                <div className="flex flex-wrap gap-3">
                  <Button
                    onClick={() => void mutate(
                      '/api/labs/environment-response/recompute',
                      'POST',
                      undefined,
                      'recompute',
                    )}
                    disabled={
                      busy
                      || isDemo
                      || preflight?.can_start_analysis === false
                      || !state.execution.recompute.allowed
                    }
                  >
                    <RefreshCw className={cn('h-4 w-4', busy && 'animate-spin motion-reduce:animate-none')} />
                    <Trans>Recompute</Trans>
                  </Button>
                  <Button variant="ghost" onClick={() => setWithdrawOpen(true)} disabled={busy || isDemo}>
                    <Trans>Withdraw</Trans>
                  </Button>
                </div>
                <RecomputePolicy execution={state.execution} />
              </CardContent>
            </Card>
          )}

          {available && (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,0.7fr)]">
              <Card>
                <CardHeader>
                  <CardTitle>
                    {partialDomain
                      ? <Trans>Your partial historical environmental-response curve</Trans>
                      : <Trans>Your historical environmental-response curve</Trans>}
                  </CardTitle>
                  <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
                    {partialDomain
                      ? <Trans>Relative modeled heart rate is shown only in ranges with enough comparable-power evidence. Unsupported ranges remain blank and are never connected.</Trans>
                      : <Trans>Relative modeled heart rate across your observed wet-bulb-proxy range, holding the fitted comparison at a common recorded-power reference.</Trans>}
                  </p>
                </CardHeader>
                <CardContent>
                  <ResultChart
                    points={points}
                    supportBins={supportBins}
                    calculatorWetBulb={calculatorWetBulb}
                  />
                  <SupportLedger
                    bins={supportBins}
                    workloadSupport={workloadSupport}
                  />
                  <CoverageSummary state={state} />
                  <div className="mt-5 grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-muted-foreground"><Trans>Historical slope</Trans></p>
                      <p className="font-data mt-1 text-lg font-semibold">
                        {uncertainty?.estimate_bpm_per_c == null
                          ? '—'
                          : `${uncertainty.estimate_bpm_per_c > 0 ? '+' : ''}${uncertainty.estimate_bpm_per_c.toFixed(2)} bpm/°C`}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground"><Trans>Bootstrap interval</Trans></p>
                      <p className="font-data mt-1 text-lg font-semibold">
                        {uncertainty?.interval_bpm_per_c?.length === 2
                          ? `${Number(uncertainty.interval_bpm_per_c[0]).toFixed(2)}–${Number(uncertainty.interval_bpm_per_c[1]).toFixed(2)} bpm/°C`
                          : '—'}
                      </p>
                    </div>
                  </div>
                  <div className="mt-5 grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-muted-foreground"><Trans>Power regime</Trans></p>
                      <p className="mt-1 text-sm font-medium"><Trans>Continuous Stryd sample power</Trans></p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground"><Trans>Model version</Trans></p>
                      <p className="font-data mt-1 break-all text-xs text-foreground">{state.result?.model_version}</p>
                    </div>
                  </div>
                  <ScienceNote
                    label={<Trans>How to read this experiment</Trans>}
                    sources={[
                      { url: EVIDENCE_URL, label: 'Praxys evidence review' },
                      {
                        url: WORKLOAD_SUPPORT_EVIDENCE_URL,
                        label: i18n._(msg`Praxys workload-support review`),
                      },
                      { url: STULL_URL, label: 'Stull (2011)' },
                    ]}
                  >
                    <p>
                      <Trans>The line is a historical model inside supported ranges only. A blank range means comparable stable workload did not pass the display floor; Praxys does not estimate or connect through it. The shaded band shows aggregate uncertainty where the curve is supported. It does not identify a causal personal coefficient and never extrapolates beyond your observed domain. Wind, solar load, clothing, hydration, fatigue, and other unmeasured conditions can still differ between runs.</Trans>
                    </p>
                    <p>
                      <Trans>Your personal comparable-power range controls where the curve can be displayed. The fitted model still uses every otherwise eligible stable segment from 65–95% CP, so the display range does not discard broader model data.</Trans>
                    </p>
                  </ScienceNote>
                </CardContent>
              </Card>
              <WetBulbCalculator state={state} onResult={setCalculatorWetBulb} />
            </div>
          )}

          {!available && !processing && (
            <WetBulbCalculator state={state} onResult={setCalculatorWetBulb} />
          )}

          {state.enrolled && !processing && (
            <div className="flex flex-col gap-5 border-t border-border pt-6 sm:flex-row sm:items-end sm:justify-between">
              <div className="max-w-2xl space-y-3">
                <p className="text-sm font-medium"><Trans>You control this experiment</Trans></p>
                <p className="mt-1 text-xs text-muted-foreground">
                  <Trans>Withdrawal deletes the experiment consent and aggregate result. Rejoining later requires new consent and a new computation.</Trans>
                </p>
                {available && <RecomputePolicy execution={state.execution} />}
              </div>
              <div className="flex flex-col-reverse gap-2 sm:flex-row">
                {available && (
                  <Button
                    onClick={() => void mutate(
                      '/api/labs/environment-response/recompute',
                      'POST',
                      undefined,
                      'recompute',
                    )}
                    disabled={
                      busy
                      || isDemo
                      || preflight?.can_start_analysis === false
                      || !state.execution.recompute.allowed
                    }
                  >
                    <RefreshCw className={cn('h-4 w-4', busy && 'animate-spin motion-reduce:animate-none')} />
                    <Trans>Recompute result</Trans>
                  </Button>
                )}
                <Button variant="ghost" onClick={() => setWithdrawOpen(true)} disabled={busy || isDemo}>
                  <Trash2 className="h-4 w-4" />
                  <Trans>Withdraw and delete result</Trans>
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {actionError && (
        <Alert variant="destructive">
          <AlertTitle><Trans>Labs action failed</Trans></AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <Dialog open={withdrawOpen} onOpenChange={setWithdrawOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle><Trans>Withdraw from this experiment?</Trans></DialogTitle>
            <DialogDescription>
              <Trans>Praxys will immediately delete your Labs consent and derived aggregate result. Your underlying account activities are not deleted.</Trans>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setWithdrawOpen(false)}>
              <Trans>Keep participating</Trans>
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() => void mutate('/api/labs/environment-response', 'DELETE').then((ok) => {
                if (ok) setWithdrawOpen(false);
              })}
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              <Trans>Withdraw and delete</Trans>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
