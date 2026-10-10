import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
function runtime() {
 let definition,response,deny=false,id=0,contextPending,releaseContext;const timers=new Map(),requests=[];
 const modules={
 '../../utils/api-client':{request:async path=>{requests.push(path);if(path.includes('/context')){if(contextPending)return contextPending;if(deny)throw {status:403};return {result_revision:'r',offset:0,windows:[]};}return structuredClone(response);}},
 '../../utils/i18n':{t:v=>v},'../../utils/theme':{resolveTheme:()=> 'dark',chartColors:()=>({reasoning:'cobalt',tick:'gray'})},
 '../../utils/dfa-navigation':{nearestWindow:()=>null,timeSupport:()=> 'unsupported'}};
 const source=readFileSync(new URL('../../miniapp/components/dfa-analysis/index.ts',import.meta.url),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
 const module={exports:{}};
 new Function('require','module','exports','Component','setTimeout','clearTimeout',code)(name=>modules[name]??{},module,module.exports,v=>{definition=v;},fn=>{timers.set(++id,fn);return id;},n=>timers.delete(n));
 const c={data:structuredClone(definition.data),properties:{activityId:'synthetic',activityStartMs:0,rangeStart:0,rangeEnd:0},setData(v){Object.assign(this.data,v);},triggerEvent(){}};
 for(const [name,method] of Object.entries(definition.methods))c[name]=method.bind(c);
 const run={id:'auto',origin:'automatic',status:'complete',phase:'compute',freshness:'current',created_at:new Date().toISOString(),source_assurance:'metadata_inferred',result_revision:'r',
 windows:[{index:0,start_ms:0,end_ms:120000,alpha1:.8,hr_bpm:140,beat_count:240,coverage_ms:120000,block:0,reasons:[],flags:[]}],
 navigation:{start_ms:0,end_ms:120000,timer_blocks:[[0,120000]],support:[[0,120000]],page_anchors:[{offset:0,time_ms:120000}]},summary:{valid_windows:1,scheduled_windows:1,short_blocks:0,supported_time_ratio:1,excluded_reasons:{}}};
 response=run;c.data.canAnalyse=true;c.data.comparators=['HR','Power','Pace'];
 return {c,timers,requests,run,set:v=>{response=v;},deny:()=>{deny=true;},hold:()=>{contextPending=new Promise(resolve=>{releaseContext=resolve;});},release:()=>releaseContext({result_revision:'r',offset:0,windows:[]})};
}
test('native comparator revalidates, retains polling and clears later unauthorized values',async()=>{
 const r=runtime();await r.c.loadRun('auto');assert.equal(r.timers.size,1);
 await r.c.onComparator({detail:{value:1}});assert.equal(r.timers.size,1);
 assert.equal(r.requests.filter(v=>v.includes('/runs/auto?')).length,2);
 r.set({...r.run,freshness:'stale',windows:undefined,navigation:undefined,summary:undefined});
 await [...r.timers.values()][0]();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(r.c.data.hasResult,false);assert.equal(r.c.data.rows.length,0);assert.equal(r.c.data.series.length,0);assert.equal(r.c.data.comparatorSeries.length,0);
});
test('denied native context clears cached alpha and overlays while polling continues',async()=>{
 const r=runtime();await r.c.loadRun('auto');r.deny();await r.c.onComparator({detail:{value:1}});
 assert.equal(r.c.data.hasResult,false);assert.equal(r.c.data.run,null);assert.equal(r.c.data.rows.length,0);assert.equal(r.c.data.series.length,0);assert.equal(r.c.data.comparatorSeries.length,0);assert.equal(r.timers.size,1);
});
test('native automatic-only report supplies both canonical limitations in EN/zh',()=>{
 const r=runtime(),w=readFileSync(new URL('../../miniapp/components/dfa-analysis/index.wxml',import.meta.url),'utf8');
 assert(w.includes('{{tr.sourceLimit}}')&&w.includes('{{tr.manualPreference}}'));
 assert.equal(r.c.data.tr.sourceLimit,'Neither recording metadata nor your confirmation verifies the source of every beat interval.');
 const zh=readFileSync(new URL('../src/locales/zh/messages.po',import.meta.url),'utf8');
 assert(zh.includes('记录元数据和你的确认均不能验证每个逐搏间期的来源。'));assert(zh.includes('这一偏好不代表准确性更高。'));
});

test('late native context cannot restore numbers after a newer run read denies authority',async()=>{
 const r=runtime();await r.c.loadRun('auto');r.c.data.comparator=1;r.hold();
 const old=r.c.showResult(r.c.data.run);
 r.set({...r.run,freshness:'stale',windows:undefined,navigation:undefined,summary:undefined});
 await r.c.loadRun('auto');r.release();await old;
 assert.equal(r.c.data.hasResult,false);assert.equal(r.c.data.rows.length,0);assert.equal(r.c.data.series.length,0);
});
