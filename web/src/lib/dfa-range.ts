import type { DFAWindow } from '@/types/api';
export type DFARange = readonly [number,number];
export function clampRange(range:DFARange, bounds:DFARange):DFARange {
  const span=Math.min(Math.max(5000,range[1]-range[0]),bounds[1]-bounds[0]);
  const from=Math.min(Math.max(bounds[0],range[0]),bounds[1]-span);
  return [from,from+span];
}
export function zoomRange(range:DFARange,bounds:DFARange,factor:number,center=(range[0]+range[1])/2):DFARange {
  const span=Math.max(5000,(range[1]-range[0])*factor);
  return clampRange([center-span/2,center+span/2],bounds);
}
export function originalSegments(windows:DFAWindow[]):DFAWindow[][] {
  const segments:DFAWindow[][]=[];
  for (const window of windows) {
    if (!segments.length || segments[segments.length-1][0].block!==window.block) segments.push([]);
    segments[segments.length-1].push(window);
  }
  return segments;
}
export function selectWindow(windows:DFAWindow[],time:number):DFAWindow|null {
  return windows.reduce<DFAWindow|null>((best,w)=>!best||Math.abs(w.end_ms-time)<Math.abs(best.end_ms-time)?w:best,null);
}
