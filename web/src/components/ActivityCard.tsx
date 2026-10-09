import { lazy, Suspense, useId, useState } from 'react';
import { Activity as ActivityGlyph, ArrowRight, Bike, ChevronDown, Footprints, Mountain, Waves } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Activity } from '@/types/api';
import { Card } from '@/components/ui/card';
import SplitBreakdown from '@/components/SplitBreakdown';
import { Trans, useLingui } from '@lingui/react/macro';
import { useLocale } from '@/contexts/LocaleContext';
import { formatStoredPace } from '@/lib/format';
import { formatElapsed } from '@/lib/activity-trace';
import { Button } from '@/components/ui/button';

const ActivityDFA = lazy(() => import('@/components/ActivityDFA'));

interface Props {
  activity: Activity;
  activityDetailAvailable: boolean;
}

export default function ActivityCard({ activity, activityDetailAvailable }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [dfaOpen, setDfaOpen] = useState(false);
  const splitId = useId();
  const { locale } = useLocale();
  const { t } = useLingui();
  const type = activity.activity_type.toLowerCase();
  const typeName = type === 'running' ? t`Running` : type === 'trail_running' ? t`Trail running`
    : type === 'walking' ? t`Walking` : type === 'hiking' ? t`Hiking`
      : type === 'cycling' ? t`Cycling` : type === 'swimming' ? t`Swimming` : type.replaceAll('_', ' ');
  const Glyph = type === 'cycling' ? Bike : type === 'swimming' ? Waves
    : type === 'hiking' || type === 'trail_running' ? Mountain
      : type === 'running' || type === 'walking' ? Footprints : ActivityGlyph;
  const date = new Date(activity.date).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
  const body = <>
    <Glyph size={22} aria-hidden="true" className="mt-1 shrink-0 text-muted-foreground" />
    <div className="min-w-0 flex-1 space-y-2">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-semibold capitalize">{typeName}</span>
        <span className="font-data text-xs text-muted-foreground dark:text-foreground">{date}</span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 font-data text-base font-semibold">
        {activity.distance_km != null && <span><span className="sr-only"><Trans>Distance</Trans> </span>{activity.distance_km.toFixed(1)} <small className="font-normal">km</small></span>}
        {activity.duration_sec != null && <span><span className="sr-only"><Trans>Duration</Trans> </span>{formatElapsed(activity.duration_sec)}<span className="sr-only"> {activity.duration_sec >= 3600 ? t`hours:minutes:seconds` : t`minutes:seconds`}</span></span>}
        {activity.avg_pace_min_km != null && <span><span className="sr-only"><Trans>Pace</Trans> </span>{formatStoredPace(activity.avg_pace_min_km)}</span>}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground dark:text-foreground">
        {activity.avg_power != null && <span><Trans>Avg Power</Trans> <span className="font-data">{Math.round(activity.avg_power)} W</span></span>}
        {activity.avg_hr != null && <span><Trans>Avg HR</Trans> <span className="font-data">{Math.round(activity.avg_hr)} bpm</span></span>}
        {activity.elevation_gain_m != null && <span><Trans>Elev</Trans> <span className="font-data">{Math.round(activity.elevation_gain_m)} m</span></span>}
        {activity.rss != null && <span>RSS <span className="font-data">{Math.round(activity.rss)}</span></span>}
        {activity.cp_estimate != null && <span>CP <span className="font-data">{Math.round(activity.cp_estimate)} W</span></span>}
      </div>
    </div>
    {activityDetailAvailable && <span className="inline-flex min-h-11 shrink-0 items-center gap-2 text-sm font-semibold text-primary max-sm:basis-full max-sm:pl-9">
      <Trans>View report</Trans><ArrowRight size={16} aria-hidden="true" />
    </span>}
  </>;
  const bodyClass = 'flex flex-wrap items-start gap-x-3 gap-y-1 rounded-md';

  return <Card className="gap-2 p-4">
    {activityDetailAvailable ? <Link to={`/history/${encodeURIComponent(activity.activity_id)}`}
      className={`${bodyClass} hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-ring`}>{body}</Link>
      : <div className={bodyClass}>{body}</div>}
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 sm:pl-9">
      {activity.splits.length > 0 && <Button variant="ghost" className="min-h-11 px-2 text-xs"
        aria-expanded={expanded} aria-controls={splitId} onClick={() => setExpanded((value) => !value)}>
        <Trans>Recorded splits</Trans> <span className="font-data">({activity.splits.length})</span>
        <ChevronDown size={14} aria-hidden="true" className={expanded ? 'rotate-180' : ''} />
      </Button>}
      <Button variant="ghost" className="min-h-11 px-2 text-xs" onClick={() => setDfaOpen(true)}><Trans>DFA α1</Trans></Button>
    </div>
    {activity.splits.length > 0 && <div id={splitId} hidden={!expanded}>
      {expanded && <SplitBreakdown splits={activity.splits} cpEstimate={activity.cp_estimate} />}
    </div>}
    {dfaOpen && <Suspense fallback={null}><ActivityDFA activityId={activity.activity_id} activityDate={activity.date} onClose={() => setDfaOpen(false)} /></Suspense>}
  </Card>;
}
