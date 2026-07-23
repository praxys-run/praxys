import { useMemo, useState } from 'react';
import { msg } from '@lingui/core/macro';
import { Trans, useLingui } from '@lingui/react/macro';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { Link } from 'react-router-dom';

import ScienceNote from '@/components/ScienceNote';
import type {
  HeatAdaptationAction,
  HeatAdaptationConfidence,
  HeatAdaptationSession,
  HeatAdaptationStage,
  HeatAdaptationStatus,
} from '@/types/api';

const STAGE_LABELS: Record<HeatAdaptationStage, ReturnType<typeof msg>> = {
  insufficient_evidence: msg`Insufficient evidence`,
  building: msg`Building`,
  likely_adapted: msg`Likely adapted`,
  maintaining: msg`Maintaining`,
  decaying: msg`Fading`,
};

const CONFIDENCE_LABELS: Record<HeatAdaptationConfidence, ReturnType<typeof msg>> = {
  low: msg`Low coverage`,
  moderate: msg`Moderate coverage`,
  high: msg`High coverage`,
};

const ACTION_GUIDANCE: Partial<Record<HeatAdaptationAction, ReturnType<typeof msg>>> = {
  sync_training_data: msg`Sync recent training to start estimating the conditions represented in your heat evidence.`,
  collect_supported_environment_data: msg`Recent activities need supported temperature and humidity data before a condition range can be estimated.`,
  set_power_threshold: msg`Set a power threshold so Praxys can identify sustained work without using diluted activity-average power.`,
  align_power_source: msg`Align the activity and threshold power sources before Praxys uses these sessions in the estimate.`,
  sync_power_provenance: msg`Sync power-source metadata so Praxys can verify that activity and threshold power are comparable.`,
  sync_power_evidence: msg`Sync split or sample power evidence so Praxys can identify sustained work.`,
};

function localDate(value: string): Date {
  return new Date(`${value.slice(0, 10)}T12:00:00`);
}

function formatDate(value: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }).format(localDate(value));
}

function formatRange(
  min: number,
  max: number,
  suffix: string,
  locale: string,
): string {
  const formatter = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const low = formatter.format(min);
  const high = formatter.format(max);
  return low === high ? `${low}${suffix}` : `${low}–${high}${suffix}`;
}

function sourceLabel(session: HeatAdaptationSession): ReturnType<typeof msg> {
  if (session.workload_source === 'samples') return msg`Power samples`;
  if (session.workload_source === 'splits') return msg`Activity splits`;
  if (session.workload_source === 'samples_incomplete') return msg`Incomplete power samples`;
  return msg`No supported workload evidence`;
}

function environmentLabel(source: string): ReturnType<typeof msg> {
  if (source === 'split_weighted') return msg`Split-weighted weather`;
  if (source === 'activity_summary' || source.endsWith('_activity_weather')) {
    return msg`Activity-summary weather`;
  }
  return msg`No supported weather evidence`;
}

function powerAlignmentLabel(
  alignment: HeatAdaptationSession['power_source_alignment'],
): ReturnType<typeof msg> {
  if (alignment === 'matched') return msg`Matched`;
  if (alignment === 'mismatch') return msg`Mismatch`;
  if (alignment === 'mixed') return msg`Mixed providers`;
  return msg`Unverified`;
}

function effectiveMinutesLabel(minutes: number): ReturnType<typeof msg> {
  return msg`${minutes} effective min`;
}

function evidenceTotalsLabel(days: number, minutes: number): ReturnType<typeof msg> {
  return msg`${days} days · ${minutes} effective min`;
}

function stageLabel(status: HeatAdaptationStatus): ReturnType<typeof msg> {
  return status.is_reacclimating ? msg`Reacclimating` : STAGE_LABELS[status.stage];
}

function lastExposureLabel(days: number | null): ReturnType<typeof msg> {
  if (days == null) return msg`None in the active window`;
  if (days === 0) return msg`Today`;
  if (days === 1) return msg`1 day ago`;
  return msg`${days} days ago`;
}

function stageInterpretation(status: HeatAdaptationStatus): ReturnType<typeof msg> {
  if (status.is_reacclimating) {
    return msg`Reacclimatization to similar conditions may be developing.`;
  }
  if (status.stage === 'likely_adapted') {
    return msg`Recent training makes acclimatization to similar conditions plausible.`;
  }
  if (status.stage === 'maintaining') {
    return status.recent_conditions
      ? msg`A prior qualifying block may still be retained. The range above describes only current qualifying training.`
      : msg`Evidence from a prior qualifying block may still be retained.`;
  }
  if (status.stage === 'building') {
    return msg`Acclimatization to similar conditions may be developing, but the evidence is still limited.`;
  }
  if (status.stage === 'decaying') {
    return status.recent_conditions
      ? msg`Evidence from a prior qualifying block is fading. The range above describes only current qualifying training.`
      : msg`Evidence from a prior qualifying block is fading.`;
  }
  return msg`There is not enough repeated qualifying exposure to estimate acclimatization to similar conditions.`;
}

function exclusionReason(
  session: HeatAdaptationSession,
  thresholdMinutes: number,
): ReturnType<typeof msg> {
  if (session.qualifies) {
    return msg`Included because supported weather and workload evidence reached the session threshold.`;
  }
  if (session.workload_evaluable) {
    return msg`Observed, but not included because it stayed below ${thresholdMinutes} effective heat minutes.`;
  }
  if (session.workload_source === 'samples_incomplete') {
    return msg`Observed, but not included because power-sample coverage was incomplete.`;
  }
  if (session.power_source_alignment === 'mismatch') {
    return msg`Observed, but not included because the activity and threshold power sources did not match.`;
  }
  if (session.power_source_alignment === 'unknown') {
    return msg`Observed, but not included because the power-source match could not be verified.`;
  }
  if (session.power_source_alignment === 'mixed') {
    return msg`Observed, but not included because workload evidence mixed power providers.`;
  }
  return msg`Observed, but not included because supported workload evidence was unavailable.`;
}

function HeatCadence({ status }: { status: HeatAdaptationStatus }) {
  const { i18n } = useLingui();
  const locale = i18n.locale || 'en';
  const defaultDay = useMemo(
    () =>
      [...status.cadence].reverse().find((day) => day.session_count > 0)
      ?? status.cadence.at(-1)
      ?? null,
    [status.cadence],
  );
  const [selectedDate, setSelectedDate] = useState<string | null>(defaultDay?.date ?? null);
  const selected = status.cadence.find((day) => day.date === selectedDate) ?? defaultDay;
  const peak = Math.max(...status.cadence.map((day) => day.effective_heat_minutes), 1);

  return (
    <section className="border-t border-border/60 pt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            <Trans>Fourteen-day activity record</Trans>
          </h3>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted-foreground">
            <Trans>Days with recorded sessions are shown below. Select a day to inspect what entered the estimate.</Trans>
          </p>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-sm bg-primary" aria-hidden="true" />
            <Trans>Included</Trans>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-sm border border-dashed border-muted-foreground/70" aria-hidden="true" />
            <Trans>Observed, not included</Trans>
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-7 gap-1.5 sm:grid-cols-[repeat(14,minmax(0,1fr))]">
        {status.cadence.map((day) => {
          const isSelected = selected?.date === day.date;
          const hasIncluded = day.counted_session_count > 0;
          const hasObserved = day.session_count > 0;
          const intensity = hasIncluded
            ? Math.max(0.28, Math.min(0.92, day.effective_heat_minutes / peak))
            : 0;
          const label = i18n._(
            msg`${formatDate(day.date, locale)}: ${day.counted_session_count} included, ${day.session_count - day.counted_session_count} observed but not included`,
          );

          return (
            <button
              key={day.date}
              type="button"
              aria-label={label}
              aria-pressed={isSelected}
              onClick={() => setSelectedDate(day.date)}
              className={`h-9 rounded-md transition-[box-shadow,background-color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                hasObserved && !hasIncluded ? 'border border-dashed border-muted-foreground/45' : ''
              } ${isSelected ? 'ring-2 ring-foreground/75 ring-offset-2 ring-offset-background' : ''}`}
              style={hasIncluded ? { backgroundColor: `color-mix(in srgb, var(--primary) ${Math.round(intensity * 100)}%, transparent)` } : undefined}
            />
          );
        })}
      </div>

      {selected && (
        <p className="mt-3 font-data text-xs text-muted-foreground" aria-live="polite">
          <span className="font-medium text-foreground">{formatDate(selected.date, locale)}</span>
          {' · '}
          <Trans>
            {selected.counted_session_count} included, {selected.session_count - selected.counted_session_count} observed but not included, {Math.round(selected.effective_heat_minutes)} effective min
          </Trans>
        </p>
      )}
    </section>
  );
}

function HeatEvidenceLedger({ status }: { status: HeatAdaptationStatus }) {
  const { i18n } = useLingui();
  const locale = i18n.locale || 'en';
  const threshold = status.evidence_thresholds.qualifying_effective_minutes;
  const sessions = (status.cadence ?? []).flatMap((day) =>
    status.sessions.filter((session) => session.date === day.date),
  ).reverse();

  return (
    <section className="border-t border-border/60 pt-6">
      <h3 className="text-sm font-semibold text-foreground">
        <Trans>Latest observed activities</Trans>
      </h3>
      <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted-foreground">
        <Trans>Open an activity to see why it was included or left out. Exclusion only describes this estimate, not whether the session had training value.</Trans>
      </p>

      {sessions.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">
          <Trans>No recent activities are available to inspect.</Trans>
        </p>
      ) : (
        <div className="mt-4 divide-y divide-border/60">
          {sessions.map((session) => (
            <details key={`${session.date}-${session.activity_id}`} className="group/session">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-3 marker:hidden">
                <span className="min-w-0">
                  <span className="block font-data text-sm font-medium text-foreground">
                    {formatDate(session.date, locale)}
                  </span>
                  <span className="mt-0.5 block font-data text-xs text-muted-foreground">
                    {Math.round(session.temperature_c)}°C · {Math.round(session.relative_humidity_pct)}%
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className={`text-xs font-medium ${session.qualifies ? 'text-primary' : 'text-muted-foreground'}`}>
                    {session.qualifies
                      ? i18n._(msg`Included in estimate`)
                      : i18n._(msg`Observed, not included`)}
                  </span>
                  <ChevronDown
                    className="size-4 text-muted-foreground transition-transform group-open/session:rotate-180"
                    aria-hidden="true"
                  />
                </span>
              </summary>
              <div className="pb-4">
                <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
                  {i18n._(exclusionReason(session, threshold))}
                </p>
                <dl className="mt-3 grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground"><Trans>Workload evidence</Trans></dt>
                    <dd className="text-right text-foreground">{i18n._(sourceLabel(session))}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground"><Trans>Weather evidence</Trans></dt>
                    <dd className="text-right text-foreground">{i18n._(environmentLabel(session.environment_source))}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground"><Trans>Effective heat time</Trans></dt>
                    <dd className="font-data text-foreground">
                      {i18n._(effectiveMinutesLabel(Math.round(session.effective_heat_minutes)))}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground"><Trans>Power-source match</Trans></dt>
                    <dd className="text-right text-foreground">
                      {i18n._(powerAlignmentLabel(session.power_source_alignment))}
                    </dd>
                  </div>
                </dl>
              </div>
            </details>
          ))}
        </div>
      )}
    </section>
  );
}

export default function HeatAdaptationPanel({ status }: { status: HeatAdaptationStatus }) {
  const { i18n } = useLingui();
  const locale = i18n.locale || 'en';
  const conditions = status.recent_conditions;
  const included = status.cadence.reduce((sum, day) => sum + day.counted_session_count, 0);
  const observed = status.cadence.reduce((sum, day) => sum + day.session_count, 0);
  const excluded = Math.max(0, observed - included);
  const actionGuidance = ACTION_GUIDANCE[status.next_action];
  const temperatureRange = conditions
    ? formatRange(conditions.temperature_c.min, conditions.temperature_c.max, '°C', locale)
    : null;
  const humidityPercentRange = conditions
    ? formatRange(conditions.relative_humidity_pct.min, conditions.relative_humidity_pct.max, '%', locale)
    : null;
  const humidityRange = humidityPercentRange
    ? i18n._(msg`${humidityPercentRange} humidity`)
    : null;

  return (
    <section
      id="heat-adaptation"
      className="scroll-mt-24 border-y border-border/70 py-7 sm:py-9"
      aria-labelledby="heat-adaptation-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <p className="text-sm font-medium text-muted-foreground">
            <Trans>Recent qualifying training range</Trans>
          </p>
          <h2 id="heat-adaptation-title" className="mt-2 text-balance text-2xl font-semibold tracking-[-0.025em] text-foreground sm:text-3xl">
            {conditions ? (
              <span className="font-data">
                {temperatureRange} <span className="text-muted-foreground">·</span> {humidityRange}
              </span>
            ) : (
              <Trans>No qualifying condition range yet</Trans>
            )}
          </h2>
          <p className="mt-3 max-w-2xl text-pretty text-sm leading-relaxed text-foreground/85">
            {i18n._(stageInterpretation(status))}
          </p>
        </div>
        <span className="rounded-full bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground">
          {i18n._(stageLabel(status))}
        </span>
      </div>

      <div className="mt-5 max-w-3xl">
        {conditions ? (
          <p className="font-data text-xs leading-relaxed text-muted-foreground">
            <Trans>
              Based on {conditions.qualifying_session_count} included sessions across {status.exposure_days} days in the last {status.evidence_thresholds.active_window_days} days.
            </Trans>
          </p>
        ) : actionGuidance ? (
          <p className="font-data text-sm leading-relaxed text-muted-foreground">
            {i18n._(actionGuidance)}
          </p>
        ) : (
          <p className="text-sm leading-relaxed text-muted-foreground">
            <Trans>
              No recent activity reached the model's {status.evidence_thresholds.qualifying_effective_minutes}-minute inclusion threshold.
            </Trans>
          </p>
        )}
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          <Trans>Past training only. This does not assess today's weather, guarantee adaptation, or replace medical guidance.</Trans>
        </p>
      </div>

      <details className="group mt-7 border-t border-border/70">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 marker:hidden">
          <span>
            <span className="block text-sm font-medium text-foreground">
              <Trans>How this estimate was built</Trans>
            </span>
            <span className="mt-0.5 block font-data text-xs text-muted-foreground">
              <Trans>{included} included · {excluded} observed, not included</Trans>
            </span>
          </span>
          <ChevronDown
            className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
            aria-hidden="true"
          />
        </summary>

        <div className="space-y-6 border-t border-border/60 pt-6">
          <dl className="grid gap-x-8 gap-y-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted-foreground"><Trans>Current evidence</Trans></dt>
              <dd className="mt-1 font-data text-foreground">
                {i18n._(evidenceTotalsLabel(
                  status.exposure_days,
                  Math.round(status.effective_heat_minutes),
                ))}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground"><Trans>Data coverage</Trans></dt>
              <dd className="mt-1 text-foreground">{i18n._(CONFIDENCE_LABELS[status.confidence])}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground"><Trans>Likely-adapted threshold</Trans></dt>
              <dd className="mt-1 font-data text-foreground">
                {i18n._(evidenceTotalsLabel(
                  status.evidence_thresholds.likely_adapted_days,
                  status.evidence_thresholds.likely_adapted_effective_minutes,
                ))}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground"><Trans>Last included session</Trans></dt>
              <dd className="mt-1 font-data text-foreground">
                {i18n._(lastExposureLabel(status.days_since_last_exposure))}
              </dd>
            </div>
          </dl>

          <HeatCadence status={status} />
          <HeatEvidenceLedger status={status} />

          <div className="border-t border-border/60 pt-5">
            <ScienceNote embedded>
              <p>
                <Trans>
                  The thresholds are Praxys operational estimates grounded in heat-acclimatization research, not a direct physiological measurement.
                </Trans>
              </p>
              <Link
                to="/science#heat"
                className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-[var(--accent-cobalt-val)] hover:underline hover:underline-offset-4"
              >
                <Trans>Read the active heat model</Trans>
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </ScienceNote>
          </div>
        </div>
      </details>
    </section>
  );
}
