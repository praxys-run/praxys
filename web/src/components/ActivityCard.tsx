import { lazy, Suspense, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Activity } from '@/types/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import SplitBreakdown from '@/components/SplitBreakdown';
import { Trans } from '@lingui/react/macro';
import { useLocale } from '@/contexts/LocaleContext';
import { formatStoredPace } from '@/lib/format';
import { Button } from '@/components/ui/button';

const ActivityDFA = lazy(() => import('@/components/ActivityDFA'));

interface Props {
  activity: Activity;
  activityDetailAvailable: boolean;
}

function formatDate(iso: string, locale: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatDuration(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0)
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatActivityType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function ActivityCard({ activity, activityDetailAvailable }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [dfaOpen, setDfaOpen] = useState(false);
  const { locale } = useLocale();

  const hasSplits = activity.splits.length > 0;

  return (
    <Card className={hasSplits ? 'hover:bg-muted/50 transition-colors' : ''}>
      <Collapsible open={expanded} onOpenChange={setExpanded}>
        <CardContent
          className={`pt-5 ${hasSplits ? 'cursor-pointer' : ''}`}
          onClick={() => { if (hasSplits) setExpanded((v) => !v); }}
        >
          {/* Header: date + type badge */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                {formatDate(activity.date, locale)}
              </span>
              <Badge variant="secondary">
                {formatActivityType(activity.activity_type)}
              </Badge>
            </div>
            {hasSplits && (
              <span className="text-muted-foreground">
                {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </span>
            )}
          </div>

          {/* Key metrics row */}
          <div className="flex flex-wrap gap-x-6 gap-y-2 mb-2">
            {activity.distance_km != null && (
              <div>
                <span className="text-xs text-muted-foreground uppercase tracking-wider">
                  <Trans>Distance</Trans>
                </span>
                <p className="font-data text-lg font-semibold text-foreground">
                  {activity.distance_km.toFixed(1)}{' '}
                  <span className="text-xs text-muted-foreground font-normal">km</span>
                </p>
              </div>
            )}
            {activity.duration_sec != null && (
              <div>
                <span className="text-xs text-muted-foreground uppercase tracking-wider">
                  <Trans>Duration</Trans>
                </span>
                <p className="font-data text-lg font-semibold text-foreground">
                  {formatDuration(activity.duration_sec)}
                </p>
              </div>
            )}
            {activity.avg_power != null && (
              <div>
                <span className="text-xs text-muted-foreground uppercase tracking-wider">
                  <Trans>Avg Power</Trans>
                </span>
                <p className="font-data text-lg font-semibold text-foreground">
                  {Math.round(activity.avg_power)}{' '}
                  <span className="text-xs text-muted-foreground font-normal">W</span>
                </p>
              </div>
            )}
            {activity.avg_hr != null && (
              <div>
                <span className="text-xs text-muted-foreground uppercase tracking-wider">
                  <Trans>Avg HR</Trans>
                </span>
                <p className="font-data text-lg font-semibold text-foreground">
                  {Math.round(activity.avg_hr)}{' '}
                  <span className="text-xs text-muted-foreground font-normal">bpm</span>
                </p>
              </div>
            )}
          </div>

          {/* Secondary metrics */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {activity.avg_pace_min_km != null && (
              <span>
                <Trans>Pace</Trans>{' '}
                <span className="font-data">
                  {formatStoredPace(activity.avg_pace_min_km)}
                </span>
              </span>
            )}
            {activity.elevation_gain_m != null && (
              <span>
                <Trans>Elev</Trans>{' '}
                <span className="font-data">
                  {Math.round(activity.elevation_gain_m)}
                </span>{' '}
                m
              </span>
            )}
            {activity.rss != null && (
              <span>
                RSS{' '}
                <span className="font-data">{Math.round(activity.rss)}</span>
              </span>
            )}
            {activity.cp_estimate != null && (
              <span>
                CP{' '}
                <span className="font-data">{Math.round(activity.cp_estimate)}</span>{' '}
                W
              </span>
            )}
          </div>
          {activityDetailAvailable && (
            <Link
              to={`/history/${encodeURIComponent(activity.activity_id)}`}
              className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
              onClick={(event) => event.stopPropagation()}
            >
              <Trans>View activity report</Trans>
            </Link>
          )}
        </CardContent>

        {/* Expandable splits */}
        <CollapsibleContent>
          <div className="px-6 pb-5">
            <SplitBreakdown
              splits={activity.splits}
              cpEstimate={activity.cp_estimate}
            />
          </div>
        </CollapsibleContent>
      </Collapsible>
      <div className="px-6 pb-4"><Button variant="outline" className="min-h-11" onClick={() => setDfaOpen(true)}><Trans>DFA α1</Trans></Button></div>
      {dfaOpen && <Suspense fallback={null}><ActivityDFA activityId={activity.activity_id} activityDate={activity.date} onClose={() => setDfaOpen(false)} /></Suspense>}
    </Card>
  );
}
