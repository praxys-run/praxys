import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import { Maximize2, Plus, Minus } from 'lucide-react';
import { Trans, useLingui } from '@lingui/react/macro';
import { Button } from '@/components/ui/button';
import { useChartColors } from '@/hooks/useChartColors';
import { formatStoredPace } from '@/lib/format';
import {
  closestRecordedSample,
  formatElapsed,
  traceColor,
  traceDomain,
  traceSegments,
  traceUnit,
  zoomTraceViewport,
  type TraceKey,
} from '@/lib/activity-trace';
import type { ActivityDetailSample, ActivityDetailResponse } from '@/types/api';

interface Props {
  detail: ActivityDetailResponse;
  primary: TraceKey;
  secondary: TraceKey | null;
  viewport: [number, number];
  cursor: number;
  selectedLabel: string | null;
  onViewportChange: (range: [number, number]) => void;
  onCursorChange: (offset: number) => void;
}

const CHART_HEIGHT = 262;
const TOP = 33;
const BOTTOM = 219;
const MIN_VIEW_SEC = 30;

function formatValue(point: ActivityDetailSample | null, metric: TraceKey): string {
  const value = point?.[metric];
  if (value == null) return '—';
  if (metric === 'pace_sec_km') return formatStoredPace(value);
  return `${Number(value.toFixed(metric === 'speed_ms' || metric === 'leg_spring_kn_m' ? 2 : 0))} ${traceUnit(metric)}`;
}

export default function ActivityTraceChart({
  detail, primary, secondary, viewport, cursor, selectedLabel,
  onViewportChange, onCursorChange,
}: Props) {
  const { t } = useLingui();
  const colors = useChartColors();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gestureRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);
  const [width, setWidth] = useState(740);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      setWidth(Math.max(230, Math.round(entries[0].contentRect.width)));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const plotLeft = width < 450 ? 44 : 55;
  const plotRight = width < 450 ? 44 : 55;
  const plotWidth = width - plotLeft - plotRight;
  const [viewportStart, viewportEnd] = viewport;
  const allStart = detail.samples[0].offset_sec;
  const allEnd = detail.samples[detail.samples.length - 1].offset_sec;
  const duration = Math.max(1, viewport[1] - viewport[0]);
  const atX = (time: number) => plotLeft + (time - viewport[0]) / duration * plotWidth;
  const atTime = (clientX: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return viewport[0];
    const position = (clientX - rect.left) / rect.width * width;
    return Math.max(viewport[0], Math.min(viewport[1], viewport[0] + (position - plotLeft) / plotWidth * duration));
  };
  const nearestPoint = closestRecordedSample(detail.samples, cursor, primary);
  const cursorPoint = nearestPoint && nearestPoint.offset_sec >= viewport[0] && nearestPoint.offset_sec <= viewport[1]
    ? nearestPoint : null;
  const primarySegments = useMemo(() => traceSegments(detail.samples, primary, viewportStart, viewportEnd),
    [detail.samples, primary, viewportStart, viewportEnd]);
  const secondarySegments = useMemo(() => secondary ? traceSegments(detail.samples, secondary, viewportStart, viewportEnd) : [],
    [detail.samples, secondary, viewportStart, viewportEnd]);
  const primaryDomain = useMemo(() => traceDomain(primarySegments, primary), [primarySegments, primary]);
  const secondaryDomain = useMemo(() => secondary ? traceDomain(secondarySegments, secondary) : null,
    [secondarySegments, secondary]);
  const metricColor = (metric: TraceKey) => traceColor(metric, colors);
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
  const metricUnit = (metric: TraceKey) => traceUnit(metric);
  const axisValue = (value: number, metric: TraceKey) => metric === 'pace_sec_km'
    ? formatStoredPace(value).split(' ')[0] : String(Number(value.toFixed(metric === 'speed_ms' || metric === 'leg_spring_kn_m' ? 1 : 0)));
  const atY = (value: number, domain: [number, number], metric: TraceKey) => {
    const proportion = (value - domain[0]) / (domain[1] - domain[0]);
    return metric === 'pace_sec_km'
      ? TOP + proportion * (BOTTOM - TOP)
      : BOTTOM - proportion * (BOTTOM - TOP);
  };
  const paths = (segments: ActivityDetailSample[][], metric: TraceKey, domain: [number, number]) =>
    segments.map((segment) => segment.map((point, index) => {
      const ordinate = atY(point[metric]!, domain, metric);
      return `${index ? 'L' : 'M'}${atX(point.offset_sec).toFixed(1)},${ordinate.toFixed(1)}`;
    }).join(' '));

  const canZoom = duration >= MIN_VIEW_SEC * 2;
  const isFull = viewport[0] === allStart && viewport[1] === allEnd;
  function zoom(factor: number) {
    onViewportChange(zoomTraceViewport(viewport, cursor, [allStart, allEnd], factor, MIN_VIEW_SEC));
  }
  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    gestureRef.current = { x: event.clientX, y: event.clientY, time: atTime(event.clientX) };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragStart(null);
    setDragEnd(null);
  }
  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current;
    if (gesture && event.buttons) {
      const dx = event.clientX - gesture.x;
      if (Math.abs(dx) > 15 && Math.abs(dx) > Math.abs(event.clientY - gesture.y)) {
        setDragStart(gesture.time);
        setDragEnd(atTime(event.clientX));
        return;
      }
    }
    if (event.pointerType === 'mouse' && !gesture) onCursorChange(Math.round(atTime(event.clientX)));
  }
  function onPointerUp(event: PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current;
    if (gesture) {
      const end = atTime(event.clientX);
      if (Math.abs(event.clientX - gesture.x) > 20 && Math.abs(end - gesture.time) >= MIN_VIEW_SEC) {
        onViewportChange([Math.floor(Math.min(end, gesture.time)), Math.ceil(Math.max(end, gesture.time))]);
      } else if (Math.abs(event.clientY - gesture.y) < 20) {
        onCursorChange(Math.round(end));
      }
    }
    gestureRef.current = null;
    setDragStart(null);
    setDragEnd(null);
  }
  function onKeyboard(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      onCursorChange(Math.max(viewport[0], Math.min(viewport[1], cursor + (event.key === 'ArrowRight' ? 1 : -1))));
      event.preventDefault();
    } else if (event.key === 'Home' || event.key === 'End') {
      onCursorChange(event.key === 'Home' ? viewport[0] : viewport[1]);
      event.preventDefault();
    }
  }

  const zoomControls = (
    <div className="activity-trace__zoom" aria-label={t`Chart zoom controls`}>
      <Button variant="outline" size="sm" disabled={!canZoom} title={!canZoom ? t`Minimum readable interval reached` : undefined} onClick={() => zoom(.5)}>
        <Plus aria-hidden="true" /><Trans>Zoom in</Trans>
      </Button>
      <Button variant="outline" size="sm" disabled={isFull} onClick={() => zoom(2)}>
        <Minus aria-hidden="true" /><Trans>Zoom out</Trans>
      </Button>
      <Button variant="outline" size="sm" disabled={isFull} onClick={() => onViewportChange([allStart, allEnd])}>
        <Maximize2 aria-hidden="true" /><Trans>Full run</Trans>
      </Button>
    </div>
  );

  return (
    <div className="activity-trace-card" ref={containerRef}>
      <div className="activity-trace-card__header">
        <div>
          <h3>{metricName(primary)}{secondary && <> × {metricName(secondary)}</>}</h3>
          <p className="activity-trace__subline">
            {selectedLabel ?? <Trans>Recorded time · two independent axes</Trans>}
          </p>
        </div>
        <div className="activity-trace__desktop-zoom">{zoomControls}</div>
      </div>

      <div className="activity-trace__readouts" aria-live="off">
        {[primary, secondary].filter((metric): metric is TraceKey => metric !== null).map((metric, index) => (
          <div className="activity-trace__readout" key={metric}>
            <div className="activity-trace__legend" style={{ color: metricColor(metric) }}>
              <span className={index ? 'activity-trace__swatch activity-trace__swatch--dash' : 'activity-trace__swatch'} />
              <span>{index ? <Trans>Right axis</Trans> : <Trans>Left axis</Trans>} · {metricName(metric)} ({metricUnit(metric)})</span>
            </div>
            <strong className="font-data">{formatValue(cursorPoint, metric)}</strong>
          </div>
        ))}
      </div>

      <div
        className="activity-trace__plot"
        tabIndex={0}
        onKeyDown={onKeyboard}
        aria-label={t`Recorded chart. Arrow keys move the time cursor; drag to select a time range.`}
      >
        <svg ref={svgRef} width="100%" height={CHART_HEIGHT} viewBox={`0 0 ${width} ${CHART_HEIGHT}`}
          onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
          onPointerCancel={() => { gestureRef.current = null; setDragStart(null); setDragEnd(null); }}
          className="activity-trace__svg" aria-hidden="true">
          {[TOP, (TOP + BOTTOM) / 2, BOTTOM].map((y) => (
            <line key={y} x1={plotLeft} x2={width - plotRight} y1={y} y2={y} stroke={colors.grid} />
          ))}
          {primarySegments.length > 0 && (
            <>
              <text x={plotLeft} y="19" textAnchor="start" fill={metricColor(primary)} className="activity-trace__axis">
                {axisValue(primary === 'pace_sec_km' ? primaryDomain[0] : primaryDomain[1], primary)} {metricUnit(primary)}
              </text>
              <text x={plotLeft - 6} y={BOTTOM + 5} textAnchor="end" fill={colors.tickLight} className="activity-trace__axis">
                {axisValue(primary === 'pace_sec_km' ? primaryDomain[1] : primaryDomain[0], primary)}
              </text>
            </>
          )}
          {secondary && secondaryDomain && secondarySegments.length > 0 && (
            <>
              <text x={width - plotRight} y="19" textAnchor="end" fill={metricColor(secondary)} className="activity-trace__axis">
                {axisValue(secondary === 'pace_sec_km' ? secondaryDomain[0] : secondaryDomain[1], secondary)} {metricUnit(secondary)}
              </text>
              <text x={width - plotRight + 6} y={BOTTOM + 5} textAnchor="start" fill={colors.tickLight} className="activity-trace__axis">
                {axisValue(secondary === 'pace_sec_km' ? secondaryDomain[1] : secondaryDomain[0], secondary)}
              </text>
            </>
          )}
          {paths(primarySegments, primary, primaryDomain).map((path, index) => (
            <path key={`primary-${index}`} d={path} stroke={metricColor(primary)} className="activity-trace__line" />
          ))}
          {primarySegments.filter((segment) => segment.length === 1).map(([point]) => (
            <circle key={`primary-single-${point.offset_sec}`} cx={atX(point.offset_sec)}
              cy={atY(point[primary]!, primaryDomain, primary)} r="3" fill={metricColor(primary)} />
          ))}
          {secondary && secondaryDomain && paths(secondarySegments, secondary, secondaryDomain).map((path, index) => (
            <path key={`secondary-${index}`} d={path} stroke={metricColor(secondary)} className="activity-trace__line" strokeDasharray="7 5" />
          ))}
          {secondary && secondaryDomain && secondarySegments.filter((segment) => segment.length === 1).map(([point]) => (
            <circle key={`secondary-single-${point.offset_sec}`} cx={atX(point.offset_sec)}
              cy={atY(point[secondary]!, secondaryDomain, secondary)} r="3" fill={metricColor(secondary)} />
          ))}
          {dragStart != null && dragEnd != null && (
            <rect x={atX(Math.min(dragStart, dragEnd))} y={TOP} width={Math.abs(atX(dragEnd) - atX(dragStart))}
              height={BOTTOM - TOP} fill="var(--primary)" fillOpacity="0.14" />
          )}
          {cursor >= viewport[0] && cursor <= viewport[1] && (
            <line x1={atX(cursor)} x2={atX(cursor)} y1={TOP} y2={BOTTOM} stroke={colors.tickLight} />
          )}
          {[primary, secondary].filter((metric): metric is TraceKey => metric !== null).map((metric) => {
            const value = cursorPoint?.[metric];
            const domain = metric === primary ? primaryDomain : secondaryDomain;
            if (value == null || !domain) return null;
            return <circle key={metric} cx={atX(cursorPoint!.offset_sec)} cy={atY(value, domain, metric)} r="4"
              stroke="var(--card)" strokeWidth="2" fill={metricColor(metric)} />;
          })}
        </svg>
        <div className="activity-trace__ends font-data">
          <span>{formatElapsed(viewport[0])}</span>
          <span>{formatElapsed(viewport[1])}</span>
        </div>
        {!primarySegments.length && !secondarySegments.length && (
          <p className="activity-trace__no-data"><Trans>No displayed readings in this interval; zoom out for context.</Trans></p>
        )}
      </div>
      <div className="activity-trace__mobile-zoom">{zoomControls}</div>
      <div className="activity-trace__scrub" style={{ paddingInline: plotLeft }}>
        <div className="activity-trace__scrub-label">
          <label htmlFor="activity-time-scrub"><Trans>Time cursor · recorded readings</Trans></label>
          <output htmlFor="activity-time-scrub" className="font-data">
            {cursorPoint ? formatElapsed(cursorPoint.offset_sec) : <Trans>Not sampled</Trans>}
          </output>
        </div>
        <input id="activity-time-scrub" type="range" min={viewport[0]} max={viewport[1]}
          step="1" value={Math.max(viewport[0], Math.min(viewport[1], cursor))}
          disabled={viewport[0] === viewport[1]}
          onChange={(event) => onCursorChange(Number(event.target.value))}
          aria-valuetext={`${formatElapsed(cursor)} · ${metricName(primary)} ${formatValue(cursorPoint, primary)}${secondary ? ` · ${metricName(secondary)} ${formatValue(cursorPoint, secondary)}` : ''}`}
        />
      </div>
      <div className="activity-trace__foot">
        <p><Trans>Axes show separate units; pace rises as seconds per km fall. Position compares shape, not magnitude.</Trans></p>
        <p>
          <Trans>Recorded sample rows</Trans>: <span className="font-data">{detail.sample_count}</span>
          {detail.sample_count > detail.samples.length && <><span> · </span><Trans>Extrema shown; omitted points are not interpolated.</Trans></>}
          {detail.activity.sample_coverage.state === 'partial' && <><span> · </span><Trans>Some intervals were not sampled; lines stop at gaps.</Trans></>}
        </p>
        <p><Trans>Missing metric readings and time gaps are shown as breaks, never filled in.</Trans></p>
        <p><Trans>Stream record source (not guaranteed per field)</Trans>: {detail.sample_sources.join(', ') || '—'}</p>
        {detail.time_origin === 'sample_start' && <p><Trans>Time is measured from the first stored sample; activity start time is unverified.</Trans></p>}
      </div>
    </div>
  );
}
