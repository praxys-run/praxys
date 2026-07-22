import type {
  HeatAdaptationAction,
  HeatAdaptationConfidence,
  HeatAdaptationSession,
  HeatAdaptationStage,
  HeatAdaptationStatus,
} from '../types/api';
import { detectLocale, t, tFmt } from './i18n';

export type HeatTone = 'neutral' | 'amber' | 'green' | 'red';

export interface HeatSourceRow {
  id: string;
  label: string;
  url: string;
}

export interface HeatSessionRow {
  id: string;
  date: string;
  environment: string;
  work: string;
  workloadMethod: string;
  source: string;
  powerSource: string;
  status: string;
  tone: 'counted' | 'muted';
}

export interface HeatAdaptationView {
  label: string;
  stage: string;
  tone: HeatTone;
  action: string;
  evidence: string;
  lastExposure: string;
  confidence: string;
  methodologyLabel: string;
  methodologyText: string;
  sourceActionLabel: string;
  sources: HeatSourceRow[];
  hasSessions: boolean;
  sessions: HeatSessionRow[];
}

const SOURCE_URLS: Record<string, string> = {
  'stull-2011': 'https://doi.org/10.1175/JAMC-D-11-0143.1',
  'cramer-jay-2016': 'https://doi.org/10.1016/j.autneu.2016.03.001',
  'nielsen-1993': 'https://doi.org/10.1113/jphysiol.1993.sp019482',
  'racinais-2015': 'https://doi.org/10.1136/bjsports-2015-094915',
  'tyler-2016': 'https://doi.org/10.1007/s40279-016-0538-5',
  'daanen-2018': 'https://doi.org/10.1007/s40279-017-0808-x',
  'kelly-2023': 'https://doi.org/10.1007/s40279-023-01831-2',
  'casa-2015': 'https://doi.org/10.4085/1062-6050-50.9.07',
};

function stageLabel(stage: HeatAdaptationStage): string {
  switch (stage) {
    case 'building': return t('Building');
    case 'likely_adapted': return t('Likely adapted');
    case 'maintaining': return t('Maintaining');
    case 'decaying': return t('Decaying');
    default: return t('Insufficient evidence');
  }
}

function stageTone(stage: HeatAdaptationStage): HeatTone {
  if (stage === 'likely_adapted' || stage === 'maintaining') return 'green';
  if (stage === 'building' || stage === 'decaying') return 'amber';
  return 'neutral';
}

function actionLabel(action: HeatAdaptationAction): string {
  switch (action) {
    case 'sync_training_data':
      return t('Sync training data to start a heat history.');
    case 'collect_supported_environment_data':
      return t('Temperature and humidity were not provided by your synced activities.');
    case 'set_power_threshold':
      return t('Set a current power threshold before workload can contribute.');
    case 'align_power_source':
      return t('Choose a power threshold from the same provider as your heat-session power.');
    case 'sync_power_provenance':
      return t('Re-sync training data so the power provider can be verified.');
    case 'sync_power_evidence':
      return t('Sync sample or split power so workload can contribute.');
    case 'continue_normal_training':
      return t('Follow your existing plan; do not add load or heat solely to change this tracker.');
    case 'maintain_normal_training':
      return t('Evidence remains recent. Follow normal training and recovery.');
    case 'no_additional_heat_needed':
      return t('No additional heat exposure is recommended from this tracker.');
    case 'follow_today_signal':
      return t("Follow today's training signal; do not add heat exposure today.");
  }
}

function confidenceLabel(confidence: HeatAdaptationConfidence): string {
  switch (confidence) {
    case 'high': return t('Strong data coverage');
    case 'moderate': return t('Moderate data coverage');
    default: return t('Limited data coverage');
  }
}

function sourceLabel(sourceId: string): string {
  switch (sourceId) {
    case 'stull-2011': return t('Stull wet-bulb approximation');
    case 'cramer-jay-2016': return t('Cramer and Jay heat-balance framework');
    case 'nielsen-1993': return t('Nielsen dry-heat acclimation study');
    case 'racinais-2015': return t('Racinais heat-acclimatization consensus');
    case 'tyler-2016': return t('Tyler heat-acclimation meta-analysis');
    case 'daanen-2018': return t('Daanen decay and reacclimation review');
    case 'kelly-2023': return t('Kelly female-athlete evidence review');
    case 'casa-2015': return t('Casa exertional heat-illness guidance');
    default: return sourceId;
  }
}

function providerLabel(provider: string | null): string {
  switch (provider) {
    case 'stryd': return 'Stryd'; // i18n-allow
    case 'garmin': return 'Garmin'; // i18n-allow
    case 'coros': return 'COROS'; // i18n-allow
    case 'strava': return 'Strava'; // i18n-allow
    case 'activities': return t('activity-derived');
    case 'mixed': return t('mixed');
    default: return provider || t('unknown');
  }
}

function powerSourceSummary(session: HeatAdaptationSession): string {
  return tFmt(
    'Power {0} · CP {1} · CP source {2}',
    providerLabel(session.power_provider),
    providerLabel(session.cp_power_provider),
    providerLabel(session.cp_source),
  );
}

function workloadMethodSummary(session: HeatAdaptationSession): string {
  const coverage = session.sample_coverage_ratio == null
    ? null
    : Math.round(session.sample_coverage_ratio * 100);
  switch (session.workload_source) {
    case 'samples':
      return coverage == null
        ? t('Sample power')
        : tFmt('Sample power · {0}% coverage', coverage);
    case 'splits':
      return coverage == null
        ? t('Split power')
        : tFmt('Split fallback · {0}% sample coverage', coverage);
    case 'samples_incomplete':
      return coverage == null
        ? t('Samples incomplete')
        : tFmt('Samples incomplete · {0}% coverage', coverage);
    default:
      return t('No sample or split power');
  }
}

function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number);
  if (!year || !month || !day) return value;
  return new Date(year, month - 1, day).toLocaleDateString(
    detectLocale() === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
}

export function emptyHeatAdaptationView(): HeatAdaptationView {
  return {
    label: t('Heat adaptation'),
    stage: '',
    tone: 'neutral',
    action: '',
    evidence: '',
    lastExposure: '',
    confidence: '',
    methodologyLabel: t('How this is calculated'),
    methodologyText: '',
    sourceActionLabel: t('Copy source URL'),
    sources: [],
    hasSessions: false,
    sessions: [],
  };
}

export function buildHeatAdaptationView(
  status: HeatAdaptationStatus,
): HeatAdaptationView {
  const evidence = status.contributing_sessions > 0
    ? tFmt(
        '{0} sessions across {1} days · {2} effective min',
        status.contributing_sessions,
        status.exposure_days,
        status.effective_heat_minutes,
      )
    : tFmt(
        '{0} of {1} recent activities have usable environment and power evidence',
        status.data_coverage.workload_supported_activities,
        status.data_coverage.recent_activities,
      );
  const lastExposure = status.days_since_last_exposure == null
    ? t('No contributing heat session yet')
    : status.days_since_last_exposure === 0
      ? t('Last contributing session today')
      : tFmt(
          'Last contributing session {0} days ago',
          status.days_since_last_exposure,
        );
  const sources = status.science_sources.map((source) => ({
    id: source.id,
    label: sourceLabel(source.id),
    url: source.url || SOURCE_URLS[source.id] || '',
  })).filter((source) => Boolean(source.url));
  const sessions = status.sessions.map((session) => ({
    id: `${session.activity_id}-${session.date}`,
    date: formatDate(session.date),
    environment: session.wet_bulb_c == null
      ? tFmt(
          '{0}°C · {1}% RH · wet-bulb estimate unavailable',
          session.temperature_c,
          session.relative_humidity_pct,
        )
      : tFmt(
          '{0}°C · {1}% RH · {2}°C estimated wet-bulb proxy',
          session.temperature_c,
          session.relative_humidity_pct,
          session.wet_bulb_c,
        ),
    work: tFmt(
      '{0} work min · {1} effective min',
      session.work_minutes,
      session.effective_heat_minutes,
    ),
    workloadMethod: workloadMethodSummary(session),
    source: session.environment_source === 'stryd_activity_weather'
      ? t('Stryd-provided activity weather')
      : t('Connector-provided activity summary'),
    powerSource: powerSourceSummary(session),
    status: session.workload_evaluable
      ? session.qualifies
        ? t('counted')
        : t('below threshold')
      : session.workload_source === 'samples_incomplete'
        ? t('Samples incomplete')
        : session.workload_source === 'none'
          ? t('Not evaluated')
          : session.power_source_alignment === 'mismatch'
        ? t('Power-source mismatch')
        : session.power_source_alignment === 'mixed'
          ? t('Mixed power sources')
          : session.power_source_alignment === 'unknown'
            ? t('Power source unknown')
          : t('Not evaluated'),
    tone: session.qualifies ? 'counted' as const : 'muted' as const,
  }));

  return {
    label: t('Heat adaptation'),
    stage: status.is_reacclimating
      ? `${stageLabel(status.stage)} · ${t('reacclimating')}`
      : stageLabel(status.stage),
    tone: stageTone(status.stage),
    action: actionLabel(status.next_action),
    evidence,
    lastExposure,
    confidence: confidenceLabel(status.confidence),
    methodologyLabel: t('How this is calculated'),
    methodologyText: t(
      "Heat adaptation covers acclimatization from natural heat and acclimation from controlled heat, but this tracker observes only outdoor connector weather; treadmill and indoor summary weather are discarded. It uses one activity-summary temperature/humidity pair. Environmental evidence takes the stronger of an estimated 18–26°C Stull psychrometric wet-bulb ramp at standard sea-level pressure and an estimated 30–40°C dry-bulb ramp; the ramps are never added and this is not WBGT. Outside Stull's 5–99% RH domain, only the dry-bulb ramp can contribute. Work minutes at or above 50% of a same-provider current CP are weighted by the stronger ramp, using timestamped samples when they cover at least 90% of activity duration and splits otherwise. Sample gaps over five seconds do not count toward coverage. A session counts at 30 effective minutes. Within a rolling 14-day window, 2 days and 60 effective minutes indicate Building; 7 days and 420 effective minutes indicate Likely adapted. The environmental ramps, effective minutes, stage thresholds, and the 7–28 day decay window are Praxys operational estimates; evidence labels describe data coverage, not biological certainty. Wind, solar radiation, within-session weather changes, clothing, hydration state, and measured core or skin temperature are excluded. Repeated exposure can reduce cardiovascular and thermal strain, but individual response varies and female-specific evidence remains limited. This is not medical clearance or a current heat-risk assessment: follow Today's signal, keep normal hydration and cooling available, stop immediately and begin cooling for heat-illness symptoms, and seek urgent medical help for confusion, collapse, or altered mental status.",
    ),
    sourceActionLabel: t('Copy source URL'),
    sources,
    hasSessions: sessions.length > 0,
    sessions,
  };
}
