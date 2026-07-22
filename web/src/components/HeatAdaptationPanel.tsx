import { msg } from '@lingui/core/macro';
import type { MessageDescriptor } from '@lingui/core';
import { Trans, useLingui } from '@lingui/react/macro';

import ScienceNote from '@/components/ScienceNote';
import type {
  HeatAdaptationAction,
  HeatAdaptationConfidence,
  HeatAdaptationSession,
  HeatAdaptationStage,
  HeatAdaptationStatus,
} from '@/types/api';

const STAGE_LABELS: Record<HeatAdaptationStage, MessageDescriptor> = {
  insufficient_evidence: msg`Insufficient evidence`,
  building: msg`Building`,
  likely_adapted: msg`Likely adapted`,
  maintaining: msg`Maintaining`,
  decaying: msg`Decaying`,
};

const STAGE_TONES: Record<HeatAdaptationStage, { dot: string; text: string }> = {
  insufficient_evidence: {
    dot: 'bg-muted-foreground',
    text: 'text-muted-foreground',
  },
  building: {
    dot: 'bg-accent-amber',
    text: 'text-accent-amber',
  },
  likely_adapted: {
    dot: 'bg-primary',
    text: 'text-primary',
  },
  maintaining: {
    dot: 'bg-primary',
    text: 'text-primary',
  },
  decaying: {
    dot: 'bg-accent-amber',
    text: 'text-accent-amber',
  },
};

const CONFIDENCE_LABELS: Record<HeatAdaptationConfidence, MessageDescriptor> = {
  low: msg`Limited data coverage`,
  moderate: msg`Moderate data coverage`,
  high: msg`Strong data coverage`,
};

const ACTION_LABELS: Record<HeatAdaptationAction, MessageDescriptor> = {
  sync_training_data: msg`Sync training data to start a heat history.`,
  collect_supported_environment_data: msg`Temperature and humidity were not provided by your synced activities.`,
  set_power_threshold: msg`Set a current power threshold before workload can contribute.`,
  align_power_source: msg`Choose a power threshold from the same provider as your heat-session power.`,
  sync_power_provenance: msg`Re-sync training data so the power provider can be verified.`,
  sync_power_evidence: msg`Sync sample or split power so workload can contribute.`,
  continue_normal_training: msg`Follow your existing plan; do not add load or heat solely to change this tracker.`,
  maintain_normal_training: msg`Evidence remains recent. Follow normal training and recovery.`,
  no_additional_heat_needed: msg`No additional heat exposure is recommended from this tracker.`,
  follow_today_signal: msg`Follow today's training signal; do not add heat exposure today.`,
};

const SOURCE_LABELS: Record<string, MessageDescriptor> = {
  'stull-2011': msg`Stull wet-bulb approximation`,
  'cramer-jay-2016': msg`Cramer and Jay heat-balance framework`,
  'nielsen-1993': msg`Nielsen dry-heat acclimation study`,
  'racinais-2015': msg`Racinais heat-acclimatization consensus`,
  'tyler-2016': msg`Tyler heat-acclimation meta-analysis`,
  'daanen-2018': msg`Daanen decay and reacclimation review`,
  'kelly-2023': msg`Kelly female-athlete evidence review`,
  'casa-2015': msg`Casa exertional heat-illness guidance`,
};

function environmentSourceLabel(source: string): MessageDescriptor {
  if (source === 'stryd_activity_weather') {
    return msg`Stryd-provided activity weather`;
  }
  return msg`Connector-provided activity summary`;
}

function formatSessionDate(value: string, locale: string): string {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Date(year, month - 1, day).toLocaleDateString(
    locale === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
}

interface HeatAdaptationPanelProps {
  status: HeatAdaptationStatus;
  variant: 'today' | 'training';
}

export default function HeatAdaptationPanel({
  status,
  variant,
}: HeatAdaptationPanelProps) {
  const { i18n, t } = useLingui();
  const tone = STAGE_TONES[status.stage];
  const stageLabel = i18n._(STAGE_LABELS[status.stage]);
  const action = i18n._(ACTION_LABELS[status.next_action]);
  const confidence = i18n._(CONFIDENCE_LABELS[status.confidence]);
  const evidence = status.contributing_sessions > 0
    ? t`${status.contributing_sessions} sessions across ${status.exposure_days} days · ${status.effective_heat_minutes} effective min`
    : t`${status.data_coverage.workload_supported_activities} of ${status.data_coverage.recent_activities} recent activities have usable environment and power evidence`;
  const lastExposure = status.days_since_last_exposure == null
    ? t`No contributing heat session yet`
    : status.days_since_last_exposure === 0
      ? t`Last contributing session today`
      : t`Last contributing session ${status.days_since_last_exposure} days ago`;
  const sources = status.science_sources.map((source) => ({
    url: source.url,
    label: SOURCE_LABELS[source.id]
      ? i18n._(SOURCE_LABELS[source.id])
      : source.id,
  }));
  const layoutClass = variant === 'today'
    ? 'col-span-full border-b border-border py-5'
    : 'mb-8 border-y border-border py-5';

  return (
    <section aria-label={t`Heat adaptation`} className={layoutClass}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-8">
        <div className="min-w-0">
          <p className="text-[11px] font-data font-semibold uppercase tracking-[0.1em] text-muted-foreground">
            <Trans>Heat adaptation</Trans>
          </p>
          <div className={`mt-2 inline-flex items-center gap-2 text-[15px] font-semibold sm:text-sm ${tone.text}`}>
            <span className={`h-2 w-2 rounded-full ${tone.dot}`} aria-hidden="true" />
            <span>{stageLabel}</span>
            {status.is_reacclimating && (
              <span className="font-normal text-muted-foreground">
                · <Trans>reacclimating</Trans>
              </span>
            )}
          </div>
        </div>
        <p className="max-w-[62ch] text-pretty text-[15px] leading-relaxed text-foreground sm:text-right sm:text-sm">
          {action}
        </p>
      </div>
      <div className="mt-3 grid gap-1 text-sm leading-relaxed text-muted-foreground sm:flex sm:flex-wrap sm:gap-x-6 sm:text-[11px]">
        <span className="font-data tabular-nums">{evidence}</span>
        <span className="font-data tabular-nums">{lastExposure}</span>
        <span>{confidence}</span>
      </div>
      <div className="[&_button]:min-h-11 [&_button]:text-sm [&_a]:inline-flex [&_a]:min-h-11 [&_a]:items-center [&_p]:text-sm sm:[&_button]:min-h-0 sm:[&_button]:text-xs sm:[&_a]:min-h-0 sm:[&_p]:text-[13px]">
        <ScienceNote
          text={t`Heat adaptation covers acclimatization from natural heat and acclimation from controlled heat, but this tracker observes only outdoor connector weather; treadmill and indoor summary weather are discarded. It uses one activity-summary temperature/humidity pair. Environmental evidence takes the stronger of an estimated 18–26°C Stull psychrometric wet-bulb ramp at standard sea-level pressure and an estimated 30–40°C dry-bulb ramp; the ramps are never added and this is not WBGT. Outside Stull's 5–99% RH domain, only the dry-bulb ramp can contribute. Work minutes at or above 50% of a same-provider current CP are weighted by the stronger ramp, using timestamped samples when they cover at least 90% of activity duration and splits otherwise. Sample gaps over five seconds do not count toward coverage. A session counts at 30 effective minutes. Within a rolling 14-day window, 2 days and 60 effective minutes indicate Building; 7 days and 420 effective minutes indicate Likely adapted. The environmental ramps, effective minutes, stage thresholds, and the 7–28 day decay window are Praxys operational estimates; evidence labels describe data coverage, not biological certainty. Wind, solar radiation, within-session weather changes, clothing, hydration state, and measured core or skin temperature are excluded. Repeated exposure can reduce cardiovascular and thermal strain, but individual response varies and female-specific evidence remains limited. This is not medical clearance or a current heat-risk assessment: follow Today's signal, keep normal hydration and cooling available, stop immediately and begin cooling for heat-illness symptoms, and seek urgent medical help for confusion, collapse, or altered mental status.`}
          sources={sources}
        />
      </div>
    </section>
  );
}

export function HeatExposureTimeline({ status }: { status: HeatAdaptationStatus }) {
  const { i18n, t } = useLingui();
  const providerLabel = (provider: string | null): string => {
    if (!provider) return i18n._(msg`unknown`);
    if (provider === 'activities') return i18n._(msg`activity-derived`);
    if (provider === 'mixed') return i18n._(msg`mixed`);
    if (provider === 'stryd') return 'Stryd';
    if (provider === 'garmin') return 'Garmin';
    if (provider === 'coros') return 'COROS';
    if (provider === 'strava') return 'Strava';
    return provider;
  };
  const workloadMethodLabel = (session: HeatAdaptationSession): string => {
    const coverage = session.sample_coverage_ratio == null
      ? null
      : Math.round(session.sample_coverage_ratio * 100);
    switch (session.workload_source) {
      case 'samples':
        return coverage == null
          ? t`Sample power`
          : t`Sample power · ${coverage}% coverage`;
      case 'splits':
        return coverage == null
          ? t`Split power`
          : t`Split fallback · ${coverage}% sample coverage`;
      case 'samples_incomplete':
        return coverage == null
          ? t`Samples incomplete`
          : t`Samples incomplete · ${coverage}% coverage`;
      default:
        return t`No sample or split power`;
    }
  };

  return (
    <section aria-label={t`Heat evidence timeline`}>
      <div className="mb-5">
        <p className="text-xs font-data font-semibold uppercase tracking-[0.1em] text-muted-foreground sm:text-[11px]">
          <Trans>Heat evidence timeline</Trans>
        </p>
        <p className="mt-1 max-w-[70ch] text-pretty text-sm leading-relaxed text-muted-foreground">
          <Trans>Recent connector readings and sample-first power workload used by the qualitative stage.</Trans>
        </p>
      </div>
      {status.sessions.length === 0 ? (
        <p className="border-t border-border py-6 text-sm text-muted-foreground">
          <Trans>No recent activity has both supported temperature/humidity and sample or split-power evidence.</Trans>
        </p>
      ) : (
        <ol className="border-t border-border">
          {status.sessions.map((session) => (
            <li
              key={`${session.activity_id}-${session.date}`}
              className="grid gap-3 border-b border-border py-5 sm:grid-cols-[90px_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-start sm:gap-5 sm:py-4"
            >
              <div className="flex items-center justify-between gap-4 sm:contents">
                <time className="font-data text-sm text-muted-foreground sm:col-start-1 sm:row-start-1 sm:text-xs">
                  {formatSessionDate(session.date, i18n.locale)}
                </time>
                <span className={`text-sm font-semibold sm:col-start-4 sm:row-start-1 sm:text-xs ${
                  session.qualifies ? 'text-primary' : 'text-muted-foreground'
                }`}>
                  {session.workload_evaluable
                    ? session.qualifies
                      ? <Trans>counted</Trans>
                      : <Trans>below threshold</Trans>
                    : session.workload_source === 'samples_incomplete'
                      ? <Trans>Samples incomplete</Trans>
                      : session.workload_source === 'none'
                        ? <Trans>Not evaluated</Trans>
                        : session.power_source_alignment === 'mismatch'
                          ? <Trans>Power-source mismatch</Trans>
                          : session.power_source_alignment === 'mixed'
                            ? <Trans>Mixed power sources</Trans>
                            : session.power_source_alignment === 'unknown'
                              ? <Trans>Power source unknown</Trans>
                              : <Trans>Not evaluated</Trans>}
                </span>
              </div>
              <span className="text-sm text-foreground sm:col-start-2 sm:row-start-1 sm:text-xs">
                <span className="font-data">
                  {session.wet_bulb_c == null
                    ? t`${session.temperature_c}°C · ${session.relative_humidity_pct}% RH · wet-bulb estimate unavailable`
                    : t`${session.temperature_c}°C · ${session.relative_humidity_pct}% RH · ${session.wet_bulb_c}°C estimated wet-bulb proxy`}
                </span>
                <span className="mt-1 block text-muted-foreground">
                  {i18n._(environmentSourceLabel(session.environment_source))}
                </span>
              </span>
              <span className="text-sm text-muted-foreground sm:col-start-3 sm:row-start-1 sm:text-xs">
                <span className="block font-data text-foreground">
                  {t`${session.work_minutes} work min · ${session.effective_heat_minutes} effective min`}
                </span>
                <span className="mt-1 block font-data">
                  {workloadMethodLabel(session)}
                </span>
                <span className="mt-1 block">
                  {t`Power ${providerLabel(session.power_provider)} · CP ${providerLabel(session.cp_power_provider)} · CP source ${providerLabel(session.cp_source)}`}
                </span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
