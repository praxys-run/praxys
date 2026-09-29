import { useMemo, useRef, useState } from 'react';
import { ArrowLeft, ArrowUpRight, ChevronDown } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { Trans, useLingui } from '@lingui/react/macro';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import ActivityTraceChart from '@/components/ActivityTraceChart';
import { useApi } from '@/hooks/useApi';
import { useLocale } from '@/contexts/LocaleContext';
import { availableTraces, formatElapsed, type TraceKey } from '@/lib/activity-trace';
import { formatStoredPace } from '@/lib/format';
import type {
  ActivityDetailResponse, ActivityKilometerSplit,
  KilometerUnavailableReason, SplitData,
} from '@/types/api';
import './ActivityDetail.css';

function recordedPace(pace: string | number | null | undefined): string {
  return pace == null ? '—' : formatStoredPace(pace);
}

function observed(value: number | null | undefined, unit = ''): string {
  return value != null && Number.isFinite(value) && value > 0 ? `${Math.round(value)}${unit}` : '—';
}

function Report({ detail }: { detail: ActivityDetailResponse }) {
  const { t } = useLingui();
  const { locale } = useLocale();
  const { activity } = detail;
  const metrics = useMemo(() => availableTraces(detail.samples), [detail.samples]);
  const preferred = detail.training_base === 'hr' ? 'hr_bpm' : detail.training_base === 'pace' ? 'pace_sec_km' : 'power_watts';
  const [chosenPrimary, setChosenPrimary] = useState<TraceKey | null>(null);
  const [chosenSecondary, setChosenSecondary] = useState<TraceKey | null | undefined>(undefined);
  const [metricsExpanded, setMetricsExpanded] = useState(false);
  const primary = chosenPrimary && metrics.includes(chosenPrimary) ? chosenPrimary : (
    metrics.includes(preferred) ? preferred : metrics[0]
  );
  const secondary = chosenSecondary === undefined
    ? metrics.find((metric) => metric !== primary) ?? null
    : chosenSecondary && chosenSecondary !== primary && metrics.includes(chosenSecondary) ? chosenSecondary : null;
  const commonMetrics = metrics.filter((metric) => ['power_watts', 'hr_bpm', 'pace_sec_km'].includes(metric));
  const featuredMetrics = commonMetrics.length ? commonMetrics : metrics.slice(0, 3);
  const extraMetrics = metrics.filter((metric) => !featuredMetrics.includes(metric));
  const activeExtra = extraMetrics.includes(primary) ? primary : null;
  const fullRange: [number, number] = detail.samples.length
    ? [detail.samples[0].offset_sec, detail.samples[detail.samples.length - 1].offset_sec]
    : [0, 0];
  const [requestedRange, setRequestedRange] = useState<[number, number] | null>(null);
  const viewport = requestedRange ?? fullRange;
  const [requestedCursor, setRequestedCursor] = useState<number | null>(null);
  const cursor = requestedCursor == null
    ? fullRange[0]
    : Math.max(viewport[0], Math.min(viewport[1], requestedCursor));
  const [splitMode, setSplitMode] = useState<'recorded' | 'kilometers'>(
    activity.splits.length ? 'recorded' : 'kilometers',
  );
  const [selectedSplit, setSelectedSplit] = useState<ActivityKilometerSplit | null>(null);
  const graphRef = useRef<HTMLDivElement>(null);
  const splitRefs = useRef(new Map<number, HTMLButtonElement>());
  const recordsRef = useRef<HTMLDetailsElement>(null);

  const date = new Date(`${activity.date}T12:00:00`).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const typeName = (() => {
    switch (activity.activity_type.toLowerCase()) {
      case 'running': return t`Running`;
      case 'trail_running': return t`Trail running`;
      case 'walking': return t`Walking`;
      case 'hiking': return t`Hiking`;
      case 'cycling': return t`Cycling`;
      case 'swimming': return t`Swimming`;
      default: return activity.activity_type.replaceAll('_', ' ');
    }
  })();
  const metricName = (metric: TraceKey) => (
    metric === 'power_watts' ? t`Power` :
      metric === 'hr_bpm' ? t`Heart rate` :
        metric === 'pace_sec_km' ? t`Pace` :
          metric === 'cadence_spm' ? t`Cadence` :
            metric === 'speed_ms' ? t`Speed` :
              metric === 'altitude_m' ? t`Altitude` :
                metric === 'grade_pct' ? t`Grade` :
                  metric === 'temperature_c' ? t`Temperature` :
                    metric === 'ground_time_ms' ? t`Ground contact time` :
                      metric === 'oscillation_mm' ? t`Vertical oscillation` :
                        metric === 'vertical_ratio' ? t`Vertical ratio` :
                          metric === 'leg_spring_kn_m' ? t`Leg spring stiffness` :
                            metric === 'form_power_watts' ? t`Form power` : t`Respiration rate`
  );
  const kilometerReason = (reason: KilometerUnavailableReason | null) => {
    switch (reason) {
      case 'samples_unavailable': return t`No time-series samples are stored.`;
      case 'distance_trace_unavailable': return t`No recorded distance trace is stored.`;
      case 'distance_trace_incomplete': return t`The recorded distance trace has missing intervals.`;
      case 'distance_trace_non_monotonic': return t`The recorded distance moves backward.`;
      case 'distance_below_display_precision': return t`The activity is shorter than the table's 0.01 km resolution.`;
      case 'start_time_unverified': return t`The activity start time cannot be verified.`;
      case 'duration_alignment_unverified': return t`Recorded time and activity duration do not align.`;
      case 'activity_distance_mismatch': return t`Recorded and summary distances do not match.`;
      default: return '';
    }
  };
  const firstLap = activity.splits[0];
  const lastLap = activity.splits[activity.splits.length - 1];
  const hasLapComparison = activity.splits.length > 1 && firstLap?.avg_pace_min_km
    && lastLap?.avg_pace_min_km && recordedPace(firstLap.avg_pace_min_km) !== '—'
    && recordedPace(lastLap.avg_pace_min_km) !== '—';
  const summary = [
    { label: t`Distance`, value: activity.distance_km != null && activity.distance_km > 0 ? activity.distance_km.toFixed(2) : '—', unit: 'km' },
    { label: t`Duration`, value: activity.duration_sec != null && activity.duration_sec > 0 ? formatElapsed(activity.duration_sec) : '—', unit: '' },
    { label: t`Average pace`, value: recordedPace(activity.avg_pace_min_km).split(' ')[0], unit: '/km' },
    activity.avg_power != null && activity.avg_power > 0
      ? { label: t`Average power`, value: observed(activity.avg_power), unit: 'W' }
      : { label: t`Average heart rate`, value: observed(activity.avg_hr), unit: 'bpm' },
  ];
  const saved = [
    { label: t`Average power`, value: observed(activity.avg_power, ' W') },
    { label: t`Average heart rate`, value: observed(activity.avg_hr, ' bpm') },
    { label: t`Average pace`, value: recordedPace(activity.avg_pace_min_km) },
    { label: t`Maximum power`, value: observed(activity.max_power, ' W') },
    { label: t`Maximum heart rate`, value: observed(activity.max_hr, ' bpm') },
    { label: t`Elevation gain`, value: observed(activity.elevation_gain_m, ' m') },
    { label: t`Temperature`, value: activity.temperature_c == null ? '—' : `${activity.temperature_c} °C` },
    { label: t`Relative humidity`, value: activity.relative_humidity_pct == null ? '—' : `${activity.relative_humidity_pct}%` },
    { label: 'RSS', value: observed(activity.rss) },
    { label: t`Source CP estimate`, value: observed(activity.cp_estimate, ' W') },
  ].filter((record) => record.value !== '—');

  const showGraph = metrics.length > 0 && Boolean(primary);
  const shownSplits = splitMode === 'recorded' ? activity.splits : detail.kilometer_splits;
  function onChooseSplit(split: ActivityKilometerSplit) {
    setSelectedSplit(split);
    setRequestedRange([split.start_offset_sec, split.end_offset_sec]);
    setRequestedCursor(split.start_offset_sec);
    window.requestAnimationFrame(() => {
      graphRef.current?.scrollIntoView({ block: 'start' });
      graphRef.current?.focus({ preventScroll: true });
    });
  }
  function returnToSplit() {
    if (!selectedSplit) return;
    setSplitMode('kilometers');
    window.requestAnimationFrame(() => {
      splitRefs.current.get(selectedSplit.split_num)?.scrollIntoView({ block: 'center' });
      splitRefs.current.get(selectedSplit.split_num)?.focus({ preventScroll: true });
    });
  }
  function recordJump(metric: TraceKey) {
    setChosenPrimary(metric);
    setChosenSecondary(null);
    setMetricsExpanded(true);
    window.requestAnimationFrame(() => {
      graphRef.current?.scrollIntoView({ block: 'start' });
      graphRef.current?.focus({ preventScroll: true });
    });
  }

  return (
    <article className="activity-report">
      <nav className="activity-report__back" aria-label={t`Activity navigation`}>
        <Link to="/history"><ArrowLeft size={16} aria-hidden="true" /> <Trans>All activities</Trans></Link>
        <span><Trans>Analysis / Activity record</Trans></span>
      </nav>
      <header className="activity-report__head">
        <h1>{typeName}</h1>
        <p className="font-data">{date} · {activity.source || t`Source unavailable`}</p>
      </header>

      <div className="activity-report__observation">
        <p>
          {hasLapComparison ? <span className="activity-report__lap-pair">
            <span className="activity-report__lap"><Trans>First lap</Trans> <strong className="font-data">{recordedPace(firstLap.avg_pace_min_km)}</strong></span>
            <span className="activity-report__lap"><Trans>Last lap</Trans> <strong className="font-data">{recordedPace(lastLap.avg_pace_min_km)}</strong></span>
          </span> : <Trans>This activity's saved record is ready to inspect.</Trans>}
        </p>
        <span>{hasLapComparison
          ? <Trans>Source laps only · not an overall trend</Trans>
          : <Trans>Recorded activity · no lap comparison available</Trans>}
          {' · '}{activity.source || t`Source unavailable`}</span>
      </div>

      <dl className="activity-report__overview">
        {summary.map((metric) => (
          <div key={metric.label}>
            <dt>{metric.label}</dt>
            <dd className="font-data">{metric.value}<small>{metric.value === '—' ? t`Not recorded` : metric.unit}</small></dd>
          </div>
        ))}
      </dl>

      <section className="activity-report__section activity-report__timeline" aria-labelledby="activity-timeline-title">
        <h2 id="activity-timeline-title"><Trans>Read the run over time</Trans></h2>
        {showGraph ? <>
          <div className="activity-report__metric-controls">
            <div className="activity-report__metric-tabs" role="group" aria-label={t`Primary recorded metric`}>
              {featuredMetrics.map((metric) => (
                <Button key={metric} variant={metric === primary ? 'default' : 'outline'} size="lg"
                  aria-pressed={metric === primary} onClick={() => {
                    setChosenPrimary(metric);
                    if (secondary === metric) setChosenSecondary(null);
                  }}>{metricName(metric)}</Button>
              ))}
              {!metricsExpanded && activeExtra && <Button variant="default" size="lg" aria-pressed="true"
                onClick={() => setMetricsExpanded(true)}>{metricName(activeExtra)}</Button>}
              {extraMetrics.length > 0 && <Button variant="outline" size="lg" aria-expanded={metricsExpanded}
                aria-controls="activity-extra-metrics" onClick={() => setMetricsExpanded((expanded) => !expanded)}>
                <Trans>More curves</Trans> <span className="font-data">{extraMetrics.length}</span>
                <ChevronDown aria-hidden="true" size={16} className={metricsExpanded ? 'activity-report__more-open' : ''} />
              </Button>}
            </div>
            {extraMetrics.length > 0 && <div id="activity-extra-metrics" hidden={!metricsExpanded}
              className="activity-report__extra-metrics" role="group" aria-label={t`Other recorded metrics`}>
              {extraMetrics.map((metric) => <Button key={metric} size="lg"
                variant={metric === primary ? 'default' : 'outline'} aria-pressed={metric === primary}
                onClick={() => {
                  setChosenPrimary(metric);
                  if (secondary === metric) setChosenSecondary(null);
                }}>{metricName(metric)}</Button>)}
            </div>}
            {metrics.length > 1 ? <label className="activity-report__overlay">
              <Trans>Overlay</Trans>
              <select value={secondary ?? ''} onChange={(event) => setChosenSecondary(event.target.value as TraceKey || null)}
                aria-label={t`Overlay recorded metric`}>
                <option value="">{t`No overlay`}</option>
                {metrics.filter((metric) => metric !== primary).map((metric) => (
                  <option key={metric} value={metric}>{metricName(metric)}</option>
                ))}
              </select>
            </label> : <p className="activity-report__aside"><Trans>Only one recorded metric; overlay unavailable.</Trans></p>}
          </div>
          <div className="activity-report__graph-focus" ref={graphRef} tabIndex={-1}
            aria-label={selectedSplit ? `${t`Selected kilometer`} ${selectedSplit.split_num}` : t`Recorded chart`}>
            <ActivityTraceChart detail={detail} primary={primary} secondary={secondary}
              viewport={viewport} cursor={cursor}
              selectedLabel={selectedSplit ? `${t`Kilometer`} ${selectedSplit.split_num}` : null}
              onViewportChange={(range) => { setRequestedRange(range); setRequestedCursor(Math.min(range[1], Math.max(range[0], cursor))); }}
              onCursorChange={setRequestedCursor} />
          </div>
          {selectedSplit && <div className="activity-report__selection" aria-live="polite">
            <strong><Trans>Kilometer</Trans> <span className="font-data">{selectedSplit.split_num}</span></strong>
            <span className="font-data">{selectedSplit.distance_km.toFixed(2)} km · {formatElapsed(selectedSplit.duration_sec)} · {selectedSplit.pace_sec_km == null ? '—' : formatStoredPace(selectedSplit.pace_sec_km)}</span>
            <Button variant="link" onClick={returnToSplit}><ArrowLeft aria-hidden="true" /><Trans>Back to split table</Trans></Button>
          </div>}
        </> : <div className="activity-report__unavailable">
          <strong><Trans>No recorded metric curves</Trans></strong>
          <p>{detail.sample_count === 0
            ? <Trans>No time-series samples were stored. Any available summaries and laps are shown below.</Trans>
            : <Trans>This stream has no saved metric readings. Any available summaries and laps are shown below.</Trans>}</p>
          {saved.length > 0 && <a href="#activity-records" onClick={() => { recordsRef.current!.open = true; }}>
            <Trans>View saved values</Trans> <ArrowUpRight size={16} aria-hidden="true" />
          </a>}
        </div>}
      </section>

      {(activity.splits.length > 0 || detail.kilometer_splits.length > 0) && (
        <section className="activity-report__section activity-report__splits" aria-labelledby="activity-splits-title">
          <h2 id="activity-splits-title"><Trans>Review by split</Trans></h2>
          <div className="activity-report__split-switch" role="group" aria-label={t`Split source`}>
            {activity.splits.length > 0 && <Button variant={splitMode === 'recorded' ? 'default' : 'outline'} size="lg"
              aria-pressed={splitMode === 'recorded'} onClick={() => setSplitMode('recorded')}><Trans>Recorded laps</Trans></Button>}
            <Button variant={splitMode === 'kilometers' ? 'default' : 'outline'} size="lg"
              aria-pressed={splitMode === 'kilometers'} disabled={!detail.kilometer_splits.length}
              title={kilometerReason(detail.kilometer_unavailable_reason)}
              onClick={() => setSplitMode('kilometers')}><Trans>Each kilometer</Trans></Button>
          </div>
          <p className="activity-report__aside">{splitMode === 'recorded'
            ? <Trans>Source-recorded laps may be manual or automatic. No reliable timeline boundaries were saved, so these rows cannot jump to the chart.</Trans>
            : <Trans>Derived from continuous recorded distance. Boundaries use the first sample to reach each kilometer; not device laps.</Trans>}
            {splitMode === 'kilometers' && !showGraph && <> <Trans>No sampled metric curves are available; these kilometer rows are for summary comparison only.</Trans></>}
            {detail.kilometer_unavailable_reason && <> <Trans>Each kilometer unavailable:</Trans> {kilometerReason(detail.kilometer_unavailable_reason)}</>}
          </p>
          <div className="activity-report__table-wrap">
            <table className="activity-report__table">
              <thead><tr>
                <th scope="col"><Trans>Split</Trans></th>
                <th scope="col"><Trans>Distance</Trans></th>
                <th scope="col"><Trans>Duration</Trans></th>
                <th scope="col"><Trans>Pace</Trans></th>
                {splitMode === 'recorded' && <><th scope="col" className="activity-report__optional-column"><Trans>Power</Trans></th>
                  <th scope="col" className="activity-report__optional-column"><Trans>Heart rate</Trans></th></>}
              </tr></thead>
              <tbody>{shownSplits.map((split: SplitData | ActivityKilometerSplit) => {
                const kilometer = splitMode === 'kilometers' ? split as ActivityKilometerSplit : null;
                const recorded = splitMode === 'recorded' ? split as SplitData : null;
                return <tr key={split.split_num} className={selectedSplit?.split_num === split.split_num && kilometer ? 'activity-report__row--selected' : ''}>
                  <th scope="row">{kilometer && showGraph ? <button type="button"
                    ref={(node) => { if (node) splitRefs.current.set(split.split_num, node); else splitRefs.current.delete(split.split_num); }}
                    onClick={() => onChooseSplit(kilometer)} aria-label={`${t`View kilometer`} ${split.split_num}`}>
                    <span className="font-data">{String(split.split_num).padStart(2, '0')}</span>
                    <ArrowUpRight size={14} aria-hidden="true" />
                  </button> : <span className="font-data">{String(split.split_num).padStart(2, '0')}</span>}
                    {recorded && <span className="activity-report__mobile-detail font-data">{observed(recorded.avg_power, ' W')} · {observed(recorded.avg_hr, ' bpm')}</span>}
                  </th>
                  <td className="font-data">{split.distance_km != null
                    ? <>{split.distance_km.toFixed(2)}<small>km</small></> : '—'}</td>
                  <td className="font-data">{split.duration_sec != null ? formatElapsed(split.duration_sec) : '—'}</td>
                  <td className="font-data">{recorded ? recordedPace(recorded.avg_pace_min_km) : kilometer?.pace_sec_km != null ? formatStoredPace(kilometer.pace_sec_km) : '—'}</td>
                  {recorded && <><td className="activity-report__optional-column font-data">{observed(recorded.avg_power, ' W')}</td>
                    <td className="activity-report__optional-column font-data">{observed(recorded.avg_hr, ' bpm')}</td></>}
                </tr>;
              })}</tbody>
            </table>
          </div>
        </section>
      )}

      <details id="activity-records" className="activity-report__records" ref={recordsRef}>
        <summary><span><Trans>Other saved values</Trans> <span className="font-data">{saved.length + metrics.length}</span></span><ChevronDown size={18} aria-hidden="true" /></summary>
        <div className="activity-report__record-list">
          {metrics.length > 0 && <section className="activity-report__record-group">
            <h3><Trans>Recorded curves</Trans></h3>
            <div className="activity-report__record-grid">
              {metrics.map((metric) => <button type="button" key={metric} className="activity-report__record-row"
                onClick={() => recordJump(metric)}>
                <span>{metricName(metric)}<small><Trans>Recorded stream · view chart</Trans></small></span>
                <ArrowUpRight size={17} aria-hidden="true" />
              </button>)}
            </div>
          </section>}
          {saved.length > 0 && <section className="activity-report__record-group">
            <h3><Trans>Whole-activity values</Trans></h3>
            <div className="activity-report__record-grid">
              {saved.map((record) => <div className="activity-report__record-row" key={record.label}>
                <span>{record.label}<small><Trans>Whole-activity summary</Trans></small></span>
                <strong className="font-data">{record.value}</strong>
              </div>)}
            </div>
          </section>}
          {!saved.length && !metrics.length && <p><Trans>No additional saved values are available.</Trans></p>}
        </div>
        {saved.length > 0 && <p className="activity-report__record-foot">
          <Trans>Activity record source</Trans>: {activity.source || t`Source unavailable`}
          {activity.environment_source && <> · <Trans>Environment record source</Trans>: {activity.environment_source}</>}
          {' · '}<Trans>Field sources for summary values are not independently verified.</Trans>
        </p>}
        {(activity.rss != null || activity.cp_estimate != null) && <p className="activity-report__record-foot">
          <Trans>RSS and the source CP estimate are activity-level references, not sampled curves or a Praxys training verdict.</Trans>
        </p>}
      </details>
    </article>
  );
}

export default function ActivityDetail() {
  const { activityId } = useParams<{ activityId: string }>();
  const { data, loading, error, errorStatus, refetch } = useApi<ActivityDetailResponse>(
    `/api/history/${encodeURIComponent(activityId || '')}/detail`, { enabled: Boolean(activityId), retry: () => false },
  );
  if (loading) return <div className="activity-report activity-report__loading" aria-busy="true">
    <Skeleton className="h-6 w-36" /><Skeleton className="h-12 w-64 mt-9" />
    <Skeleton className="h-16 mt-8" /><Skeleton className="h-24 mt-5" />
    <Skeleton className="h-72 mt-12" />
  </div>;
  if (error || !data) return <div className="activity-report">
    <Link className="activity-report__back-link" to="/history"><ArrowLeft size={16} aria-hidden="true" /> <Trans>All activities</Trans></Link>
    <Alert variant="destructive" className="mt-8">
      <AlertTitle>{errorStatus === 404 ? <Trans>Activity unavailable</Trans> : <Trans>Could not load this activity</Trans>}</AlertTitle>
      <AlertDescription><p>{errorStatus === 404
        ? <Trans>This record is not available to this account.</Trans>
        : <Trans>Check your connection and retry. No stale record is shown.</Trans>}</p>
        {errorStatus !== 404 && <Button variant="outline" className="mt-3" onClick={() => refetch()}><Trans>Retry</Trans></Button>}
      </AlertDescription>
    </Alert>
  </div>;
  return <Report key={data.activity.activity_id} detail={data} />;
}
