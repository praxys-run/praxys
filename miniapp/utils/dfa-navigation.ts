// AUTO-SYNCED from web/src/lib/dfa-navigation.ts.
/** Shared elapsed-time navigation and cooldown parsing; no physiological meaning. */
export interface DFATiming { start_ms: number; end_ms: number; timer_blocks: [number, number][]; support: [number, number][] }
export function windowCount(nav: DFATiming): number {
  return nav.timer_blocks.reduce((sum,[a,b])=>sum+Math.max(0,Math.floor((b-a-120000)/5000)+1),0);
}
export function windowAtIndex(nav: DFATiming, requested: number): { index: number; time: number } | null {
  const index=Math.max(0,Math.min(windowCount(nav)-1,requested));
  let first=0;
  for (const [start,end] of nav.timer_blocks) {
    const count=Math.max(0,Math.floor((end-start-120000)/5000)+1);
    if (index<first+count) return {index,time:start+120000+(index-first)*5000};
    first+=count;
  }
  return null;
}
export function nearestWindow(nav: DFATiming, time: number): { index: number; time: number } | null {
  let first=0, best: {index:number;time:number}|null=null;
  for (const [start,end] of nav.timer_blocks) {
    const count=Math.max(0,Math.floor((end-start-120000)/5000)+1);
    if (count) {
      const offset=Math.max(0,Math.min(count-1,Math.round((time-start-120000)/5000)));
      const candidate={index:first+offset,time:start+120000+offset*5000};
      if (!best || Math.abs(candidate.time-time)<Math.abs(best.time-time)) best=candidate;
    }
    first+=count;
  }
  return best;
}
export function timeSupport(nav: DFATiming, time: number): 'supported'|'unsupported'|'paused' {
  if (nav.support.some(([a,b])=>time>=a&&time<=b)) return 'supported';
  return nav.timer_blocks.some(([a,b])=>time>=a&&time<=b) ? 'unsupported' : 'paused';
}
export function retryAfterSeconds(value: string | null | undefined, now=Date.now()): number {
  if (!value) return 0;
  const seconds=/^\d+(?:\.\d+)?$/.test(value.trim()) ? Number(value) : (Date.parse(value)-now)/1000;
  return Number.isFinite(seconds) ? Math.max(0,Math.ceil(seconds)) : 0;
}
