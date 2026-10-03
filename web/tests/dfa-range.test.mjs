import test from 'node:test';
import assert from 'node:assert/strict';
import {clampRange,zoomRange,originalSegments,selectWindow} from '../src/lib/dfa-range.ts';

test('view changes clamp actual elapsed bounds without changing any original window',()=>{
  const windows=Array.from({length:446},(_,index)=>({index,block:index<200?0:1,start_ms:index*5000,end_ms:120000+index*5000,alpha1:index%3===0?.9:null,reasons:index%3===0?[]:['rr_suspect']}));
  const before=structuredClone(windows),bounds=[0,2345000],zoom=zoomRange(bounds,bounds,.5,120000);
  assert.deepEqual(zoom,[0,1172500]);assert.deepEqual(zoomRange(zoom,bounds,2),bounds);
  assert.deepEqual(clampRange([-1000,49000],bounds),[0,50000]);
  const segments=originalSegments(windows);assert.equal(segments.length,2);assert.deepEqual(segments.flat(),windows);
  assert.equal(selectWindow(windows,windows[445].end_ms).index,445);
  assert.equal(segments.flat().filter(w=>w.alpha1===null).length,windows.filter(w=>w.alpha1===null).length);
  assert.deepEqual(windows,before);
});
