import { useEffect, useRef, useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DFAContext, DFARun } from '@/types/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RangeSlider } from '@/components/ui/slider';
import { clampRange, originalSegments, selectWindow, zoomRange, type DFARange } from '@/lib/dfa-range';

function elapsed(ms:number,start:number) {const s=Math.max(0,Math.round((ms-start)/1000));return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;}
export default function DFAPlot({run,context,comparator,label,focusTime,verified,reason}:{run:DFARun;context:DFAContext|null;comparator:string;label:string;focusTime:number|null;verified:boolean;reason:(code:string)=>string}) {
  const {t}=useLingui();
  const nav=run.navigation!;
  const bounds:DFARange=[nav.start_ms,nav.end_ms];
  const [range,setRange]=useState<DFARange>(bounds);
  const [detailLimit,setDetailLimit]=useState(120);
  const [selection,setSelection]=useState<number|null>(null);
  const [pan,setPan]=useState(false);
  const drag=useRef<{x:number;range:DFARange}|null>(null);
  const view=clampRange(range,bounds);
  useEffect(()=>{if(focusTime===null)return;const window=selectWindow(run.windows??[],focusTime);if(window)setSelection(window.index);setRange(previous=>{const span=previous[1]-previous[0];return clampRange([focusTime-span/2,focusTime+span/2],bounds);});},[focusTime]);
  const visible=(run.windows??[]).filter(w=>w.end_ms>=view[0]&&w.end_ms<=view[1]);
  const overlay=new Map(context?.result_revision===run.result_revision?context.windows.map(w=>[w.index,w]):[]);
  const data=visible.map(w=>({...w,comparator:comparator==='hr_bpm'?w.hr_bpm:comparator==='power_watts'?overlay.get(w.index)?.power_watts??null:overlay.get(w.index)?.pace_sec_km??null}));
  const segments=originalSegments(visible);
  const selected=(run.windows??[]).find(w=>w.index===selection)??selectWindow(visible,(view[0]+view[1])/2);
  const zoom=(factor:number)=>setRange(zoomRange(view,bounds,factor,selected?.end_ms));
  const adjust=(bound:0|1,seconds:string)=>{if(!verified)return;const next:[number,number]=[...view];next[bound]=nav.start_ms+Number(seconds)*1000;setRange(clampRange(next,bounds));};
  return <div className="flex flex-col gap-4" data-dfa-plot>
    <p className="text-sm leading-relaxed text-muted-foreground"><Trans>Each point analyses the preceding 120 seconds, every 5 seconds; zoom changes only the view. One suspect interval can affect several overlapping windows. Gaps mark windows that did not pass the checks.</Trans></p>
    <div className="flex flex-wrap gap-2" onKeyDown={event=>{
      if(!verified)return;
      if(event.key==='+'||event.key==='='){event.preventDefault();zoom(.5);}
      if(event.key==='-'){event.preventDefault();zoom(2);}
      if(event.key==='Home'){event.preventDefault();setRange(bounds);}
      if(event.key==='Escape'&&pan){event.preventDefault();event.stopPropagation();setPan(false);}
      if(pan&&(event.key==='ArrowLeft'||event.key==='ArrowRight')){event.preventDefault();const shift=(view[1]-view[0])*.1*(event.key==='ArrowLeft'?-1:1);setRange(clampRange([view[0]+shift,view[1]+shift],bounds));}
    }}>
      <Button className="min-h-11" variant="outline" onClick={()=>zoom(.5)}><Trans>Zoom in</Trans></Button>
      <Button className="min-h-11" variant="outline" onClick={()=>zoom(2)}><Trans>Zoom out</Trans></Button>
      <Button className="min-h-11" variant="outline" aria-pressed={pan} onClick={()=>setPan(!pan)}><Trans>Pan</Trans></Button>
      <Button className="min-h-11" variant="outline" onClick={()=>setRange(bounds)}><Trans>Full activity</Trans></Button>
    </div>
    <div className="grid grid-cols-2 gap-3" aria-hidden={!verified||undefined}>
      <div><Label htmlFor="dfa-from"><Trans>From (seconds)</Trans></Label><Input id="dfa-from" className="min-h-11 font-data" type="number" min={0} max={verified?(nav.end_ms-nav.start_ms)/1000:undefined} value={verified?Math.round((view[0]-nav.start_ms)/1000):''} onChange={e=>adjust(0,e.target.value)}/></div>
      <div><Label htmlFor="dfa-to"><Trans>To (seconds)</Trans></Label><Input id="dfa-to" className="min-h-11 font-data" type="number" min={0} max={verified?(nav.end_ms-nav.start_ms)/1000:undefined} value={verified?Math.round((view[1]-nav.start_ms)/1000):''} onChange={e=>adjust(1,e.target.value)}/></div>
    </div>
    <div aria-hidden={!verified||undefined}><RangeSlider value={verified?[(view[0]-nav.start_ms)/1000,(view[1]-nav.start_ms)/1000]:[0,1]} min={0} max={verified?(nav.end_ms-nav.start_ms)/1000:1} minimumLabel={verified?t`View start: ${elapsed(view[0],nav.start_ms)}`:t`Checking source status…`} maximumLabel={verified?t`View end: ${elapsed(view[1],nav.start_ms)}`:t`Checking source status…`} onValueChange={next=>{if(!verified)return;setRange(clampRange([nav.start_ms+next[0]*1000,nav.start_ms+next[1]*1000],bounds));}}/></div>
    <div className="h-64 w-full touch-pan-y font-data" aria-hidden={!verified||undefined} onPointerDown={e=>{if(pan&&verified){drag.current={x:e.clientX,range:view};e.currentTarget.setPointerCapture(e.pointerId);}}} onPointerMove={e=>{if(drag.current&&pan&&verified){const shift=(drag.current.x-e.clientX)/e.currentTarget.clientWidth*(drag.current.range[1]-drag.current.range[0]);setRange(clampRange([drag.current.range[0]+shift,drag.current.range[1]+shift],bounds));}}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}>
      <ResponsiveContainer width="100%" height="100%"><LineChart data={verified?data:[]} onMouseMove={event=>{if(verified&&event.activeLabel!=null){const w=selectWindow(visible,Number(event.activeLabel));if(w)setSelection(w.index);}}} onClick={event=>{if(verified&&event.activeLabel!=null){const w=selectWindow(visible,Number(event.activeLabel));if(w)setSelection(w.index);}}} margin={{left:0,right:0,top:10,bottom:10}}>
        <CartesianGrid stroke="var(--border)" vertical={false}/><XAxis dataKey="end_ms" type="number" domain={verified?view as [number,number]:[0,1]} allowDataOverflow tickFormatter={v=>elapsed(Number(v),nav.start_ms)} tick={{fontSize:11,fill:'var(--foreground)'}}/>
        <YAxis yAxisId="alpha" tickFormatter={v=>Number(v).toFixed(2)} width={44} domain={['auto','auto']} tick={{fontSize:11,fill:'var(--foreground)'}}/>
        <YAxis yAxisId="context" orientation="right" width={45} domain={['auto','auto']} tick={{fontSize:11,fill:'var(--foreground)'}}/>
        <Tooltip labelFormatter={v=>elapsed(Number(v),nav.start_ms)} formatter={v=>typeof v==='number'?v.toFixed(2):'—'} contentStyle={{background:'var(--card)',borderColor:'var(--border)'}}/>
        {segments.map(segment=><Line key={`a-${segment[0].block}`} data={verified?data.filter(w=>w.block===segment[0].block):[]} yAxisId="alpha" dataKey="alpha1" name="DFA α1" type="linear" stroke="var(--accent-cobalt-val)" dot={{r:1.5}} connectNulls={false} isAnimationActive={false}/>)}
        {segments.map(segment=><Line key={`c-${segment[0].block}`} data={verified?data.filter(w=>w.block===segment[0].block):[]} yAxisId="context" dataKey="comparator" name={label} type="linear" stroke="var(--foreground)" dot={{r:1.5}} connectNulls={false} isAnimationActive={false}/>)}
      </LineChart></ResponsiveContainer>
    </div>
    {selected&&<div className="border-t pt-3 text-sm" aria-hidden={!verified||undefined} aria-live="polite"><p className="font-data">{verified?`${elapsed(selected.start_ms,nav.start_ms)}–${elapsed(selected.end_ms,nav.start_ms)}`:t`Checking source status…`} · DFA α1 {verified?selected.alpha1?.toFixed(2)??'—':'—'}</p><p>{[...selected.reasons,...selected.flags].map(reason).join(' ')||t`No issues detected by these checks.`}</p><p className="font-data"><Trans>Complete beats</Trans>: {verified?selected.beat_count:'—'} · <Trans>Interval coverage</Trans>: {verified?(selected.coverage_ms/1200).toFixed(1):'—'}%</p></div>}
    <details><summary className="min-h-11 cursor-pointer py-3 font-medium"><Trans>Window values and quality details</Trans></summary><div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only"><Trans>All original windows in the viewing range.</Trans></caption><thead><tr><th><Trans>Time</Trans></th><th>DFA α1</th><th>{label}</th><th><Trans>Quality</Trans></th></tr></thead><tbody aria-hidden={!verified||undefined}>{data.slice(0,detailLimit).map(w=><tr key={w.index} tabIndex={0} onFocus={()=>setSelection(w.index)} onClick={()=>setSelection(w.index)} className="border-b align-top focus-visible:outline-2 focus-visible:outline-ring"><td className="py-3 pr-2 font-data">{verified?`${elapsed(w.start_ms,nav.start_ms)}–${elapsed(w.end_ms,nav.start_ms)}`:t`Checking source status…`}</td><td className="py-3 pr-2 font-data">{verified?w.alpha1?.toFixed(2)??'—':'—'}</td><td className="py-3 pr-2 font-data">{verified?w.comparator?.toFixed(1)??'—':'—'}</td><td className="py-3"><p>{[...w.reasons,...w.flags].map(reason).join(' ')||t`No issues detected by these checks.`}</p><span className="font-data"><Trans>Complete beats</Trans>: {verified?w.beat_count:'—'} · <Trans>Interval coverage</Trans>: {verified?(w.coverage_ms/1200).toFixed(1):'—'}%</span></td></tr>)}</tbody></table></div>{detailLimit<data.length&&<Button className="min-h-11" variant="outline" onClick={()=>setDetailLimit(detailLimit+120)}><Trans>More window details</Trans></Button>}</details>
  </div>;
}
