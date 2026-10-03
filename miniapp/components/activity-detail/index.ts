import type { Activity } from '../../types/api';
import { formatDistance,formatTime } from '../../utils/format';
import { t } from '../../utils/i18n';
Component({
  options:{addGlobalClass:true},
  properties:{activity:{type:Object,value:null}},
  data:{tr:{title:t('Activity details'),back:t('Back to activities'),splits:t('Splits'),none:t('No splits recorded.')},metrics:[] as {label:string;value:string}[],splits:[] as {id:number;values:string}[],showSplits:false},
  observers:{activity(value:Activity|null){if(!value)return;const metrics=[];
    if(value.distance_km!=null)metrics.push({label:t('Distance'),value:formatDistance(value.distance_km)+' km'});
    if(value.duration_sec!=null)metrics.push({label:t('Duration'),value:formatTime(value.duration_sec)});
    if(value.avg_power!=null)metrics.push({label:t('Avg Power'),value:Math.round(value.avg_power)+' W'});
    if(value.avg_hr!=null)metrics.push({label:t('Avg HR'),value:Math.round(value.avg_hr)+' bpm'});
    if(value.avg_pace_min_km!=null)metrics.push({label:t('Pace'),value:value.avg_pace_min_km});
    if(value.elevation_gain_m!=null)metrics.push({label:t('Elev'),value:Math.round(value.elevation_gain_m)+' m'});
    if(value.rss!=null)metrics.push({label:'RSS',value:String(Math.round(value.rss))});
    this.setData({metrics,splits:(value.splits??[]).map(s=>({id:s.split_num,values:[s.distance_km==null?null:formatDistance(s.distance_km)+' km',s.duration_sec==null?null:formatTime(s.duration_sec),s.avg_power==null?null:Math.round(s.avg_power)+' W',s.avg_hr==null?null:Math.round(s.avg_hr)+' bpm',s.avg_pace_min_km].filter(v=>v!=null).join(' · ')}))});
  }},
  methods:{close(){this.triggerEvent('close');},splits(){this.setData({showSplits:!this.data.showSplits});}},
});
