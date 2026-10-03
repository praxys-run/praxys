import { Trans, useLingui } from '@lingui/react/macro';
import type { Activity } from '@/types/api';
import MetricDetailSheet from '@/components/MetricDetailSheet';
import { DFAContent } from '@/components/ActivityDFA';
import SplitBreakdown from '@/components/SplitBreakdown';
import { formatStoredPace } from '@/lib/format';
import { formatElapsed } from '@/lib/activity-trace';

export default function ActivityDetailSheet({activity,onClose}:{activity:Activity;onClose:()=>void}) {
  const {t,i18n}=useLingui();
  const type = activity.activity_type.toLowerCase();
  const activityType = type === 'running' ? t`Running` : type === 'trail_running' ? t`Trail running`
    : type === 'walking' ? t`Walking` : type === 'hiking' ? t`Hiking`
      : type === 'cycling' ? t`Cycling` : type === 'swimming' ? t`Swimming` : type.replaceAll('_', ' ');
  const summary=[
    {label:t`Distance`,value:activity.distance_km?.toFixed(2),unit:'km'},
    {label:t`Duration`,value:activity.duration_sec==null?undefined:formatElapsed(activity.duration_sec),unit:''},
    {label:t`Avg Power`,value:activity.avg_power==null?undefined:String(Math.round(activity.avg_power)),unit:'W'},
    {label:t`Avg HR`,value:activity.avg_hr==null?undefined:String(Math.round(activity.avg_hr)),unit:'bpm'},
    {label:t`Pace`,value:activity.avg_pace_min_km?formatStoredPace(activity.avg_pace_min_km):undefined,unit:''},
    {label:t`Elev`,value:activity.elevation_gain_m==null?undefined:String(Math.round(activity.elevation_gain_m)),unit:'m'},
    {label:'RSS',value:activity.rss==null?undefined:String(Math.round(activity.rss)),unit:''},
  ].filter(metric=>metric.value!==undefined);
  return <MetricDetailSheet open size="wide" onOpenChange={open=>{if(!open)onClose();}} title={t`Activity details`} description={<span><span className="font-data">{new Date(activity.date).toLocaleDateString(i18n.locale)}</span> · {activityType}</span>}>
    <div className="flex flex-col gap-7"><dl className="grid grid-cols-2 gap-x-5 gap-y-4 border-b pb-5">{summary.map(metric=><div key={metric.label}><dt className="text-sm text-muted-foreground">{metric.label}</dt><dd className="font-data">{metric.value} {metric.unit}</dd></div>)}</dl>
      <DFAContent activityId={activity.activity_id}/>
      <details><summary className="min-h-11 cursor-pointer py-3 font-medium"><Trans>Splits</Trans></summary>{activity.splits.length?<SplitBreakdown splits={activity.splits} cpEstimate={activity.cp_estimate}/>:<p className="text-sm text-muted-foreground"><Trans>No splits recorded.</Trans></p>}</details>
    </div>
  </MetricDetailSheet>;
}
