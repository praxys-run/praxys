import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const ts=require('typescript');
import {nearestWindow,windowAtIndex,timeSupport,retryAfterSeconds} from '../src/lib/dfa-navigation.ts';
function compile(relative, modules, globals={}, suffix="") {
  const source=readFileSync(new URL(relative,import.meta.url),'utf8');
  const code=ts.transpileModule(source,{fileName:relative,compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const module={exports:{}};
  new Function('require','module','exports',...Object.keys(globals),code+suffix)(name=>modules[name]??{},module,module.exports,...Object.values(globals));
  return module.exports;
}

test('DFA rights transport remains authenticated without opening computation before notice',async()=>{
  const calls=[];
  const wx={getStorageSync:()=> 'synthetic-token',reLaunch:()=>{},showToast:()=>{},
    request:options=>{calls.push(options);queueMicrotask(()=>options.success({statusCode:200,data:{deleted:true},header:{}}));return {abort(){}}}};
  const api=compile('../../miniapp/utils/api-client.ts',{
    './china-processing':{hasAcknowledgedChinaProcessingNotice:()=>false,CHINA_PROCESSING_NOTICE_VERSION:'synthetic'},
    './version':{MINIAPP_BUILD_VERSION:'synthetic'},'./legal':{TERMS_CONTENT_DIGEST:'synthetic'},
    './feedback':{removeRecentFeedbackId:()=>{}}, './dfa-navigation':{retryAfterSeconds},
  },{wx,getCurrentPages:()=>[]});
  const base='/api/activities/123/dfa-alpha1';
  for(const [method,path] of [['DELETE',base],['DELETE',base+'/source-confirmations/proof'],['POST',base+'/runs/run/cancel']]){
    assert.equal((await api.request(path,{method})).deleted,true);
    assert.equal(calls.at(-1).header.Authorization,'Bearer synthetic-token');
  }
  const previous=calls.length;
  for(const [method,path] of [['GET',base],['POST',base],['POST',base+'/source-confirmations'],['POST',base+'/runs/run/retry'],['DELETE',base+'/other']]){
    await assert.rejects(api.request(path,{method}),e=>e.code==='PROCESSING_NOTICE_REQUIRED');
  }
  assert.equal(calls.length,previous);
});

test('numeric miniapp chart positions preserve pause width and incumbent ordinal consumers',()=>{
  const {xPositions}=compile('../../miniapp/components/line-chart/index.ts',{
    '../../utils/theme':{chartColors:()=>({})},'../../utils/i18n':{t:s=>s},
  },{Component:()=>{}});
  const times=[0,5,10,120];
  assert.deepEqual(xPositions(times,4),[0,5/120,10/120,1]);
  assert.deepEqual(times,[0,5,10,120]);
  assert.deepEqual(xPositions([],4),[0,1/3,2/3,1]);
  assert.deepEqual(xPositions([0,5,4,10],4),[0,1/3,2/3,1]);
});

 test('elapsed navigator retains real pauses and picks scheduled windows only',()=>{
  const nav={start_ms:0,end_ms:780000,timer_blocks:[[0,360000],[600000,780000]],support:[[1000,300000],[720000,779000]]};
  assert.deepEqual(windowAtIndex(nav,48),{index:48,time:360000});
  assert.deepEqual(windowAtIndex(nav,49),{index:49,time:720000});
  assert.deepEqual(nearestWindow(nav,450000),{index:48,time:360000});
  assert.equal(timeSupport(nav,450000),'paused');
  assert.equal(timeSupport(nav,350000),'unsupported');
  assert.equal(timeSupport(nav,200000),'supported');
  assert.equal(retryAfterSeconds('7'),7);
  assert.equal(retryAfterSeconds('Wed, 01 Jan 2025 00:00:30 GMT',Date.parse('2025-01-01T00:00:00Z')),30);
  assert.equal(retryAfterSeconds('invalid'),0);
});

const input={provider:'garmin',user_id:'synthetic',account_id:'account',activity_id:'activity',snapshot_id:'snapshot',parse_id:'parse',sha256:'a'.repeat(64),parser_version:'fitdecode-0.11.0/praxys-1'};
const retainedProof={id:'proof',snapshot_id:'snapshot',parse_id:'parse',sensor_ref:'sensor',sensor_label:'Polar H10',statement_version:'dfa-source-attestation-v1',created_at:'2026-09-27T00:00:00',source_assurance:'user_confirmed'};
const baseRun={id:'run',phase:'compute',status:'complete',generation:1,freshness:'current',progress:'complete',error_code:null,created_at:'2026-09-27T00:00:00',completed_at:'2026-09-27T00:00:01',expires_at:'2026-10-27T00:00:01',method_version:'dfa-alpha1-raw120-v1',science_contract_digest:'sha256:'+'a'.repeat(64),snapshot_id:'snapshot',parse_id:'parse',source_confirmation_id:'proof',result_revision:'revision'};
const completed={...baseRun,summary:{valid_windows:1,scheduled_windows:1,window_success_rate:1,supported_time_ratio:.99,short_blocks:0,excluded_reasons:{}},navigation:{start_ms:0,end_ms:120000,timer_blocks:[[0,120000]],support:[[0,119900]],page_size:120,page_anchors:[{offset:0,time_ms:120000}]},page:{offset:0,limit:120,total:1,next_offset:null},windows:[{index:0,block:0,start_ms:0,end_ms:120000,alpha1:.9,hr_bpm:120,r2:.95,reasons:[],flags:[],beat_count:240,coverage_ms:119900,offset_ms:0,offset_width_ms:2000,rr_index_start:0,rr_index_end:239}]};
function catalog({proofs=[],run=null,processing=true}={}) {return {activity_id:'activity',inputs:[{input,created_at:'2026-09-27T00:00:00'}],catalog_revision:'c'.repeat(64),source_confirmations:proofs,latest_run:run,availability:'ready',policy_active:true,processing_authorized:processing,statement_version:'dfa-source-attestation-v1'};}
function miniComponent(request) {
  let definition;
  compile('../../miniapp/components/dfa-analysis/index.ts',{'../../utils/api-client':{request},'../../utils/i18n':{t:value=>value},'../../utils/theme':{resolveTheme:()=> 'light',chartColors:()=>({reasoning:'blue',tick:'black'})},'../../utils/dfa-navigation':{nearestWindow,timeSupport}},
    {Component:value=>{definition=value;},setTimeout:()=>1,clearTimeout:()=>{}});
  const component={data:structuredClone(definition.data),properties:{activityId:'activity',activityDate:'2026-09-27'},setData(patch){Object.assign(this.data,patch);},triggerEvent(){}};
  for(const [name,method] of Object.entries(definition.methods)) component[name]=method.bind(component);
  return component;
}
test('actual miniapp refresh never recomputes an expired cache with a retained proof',async()=>{
  const calls=[];
  const c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?baseRun:options.method==='POST'?baseRun:catalog({proofs:[retainedProof]});});
  c.setData({active:true,stale:true});
  await c.refresh();assert.equal(c.data.selected,0);assert.equal(c.data.active,false);assert.equal(c.data.stale,false);assert.equal(calls.filter(v=>v.method==='POST').length,0);
  await c.launch();assert.equal(calls.find(v=>v.method==='POST').body.source_confirmation_id,'proof');
});
test('actual miniapp clears HR values before an asynchronous power comparator response',async()=>{
  let resolveContext;const c=miniComponent(()=>new Promise(resolve=>{resolveContext=resolve;}));
  c.setData({run:completed,comparators:['HR','Power','Pace'],comparator:0,canAnalyse:true});
  await c.showResult(completed);assert.equal(c.data.rows[0].value,'120.0');
  const change=c.onComparator({detail:{value:'1'}});
  assert.equal(c.data.comparator,1);assert.deepEqual(c.data.rows,[]);assert.deepEqual(c.data.comparatorSeries,[]);
  resolveContext({result_revision:'revision',samples_revision:'1',offset:0,windows:[{index:0,power_watts:250,pace_sec_km:300}]});
  await change;assert.equal(c.data.rows[0].value,'250.0');assert.equal(c.data.comparatorSeries[0].label,'Power');
});
test('actual miniapp retains owner cancellation while processing is withdrawn',async()=>{
  const calls=[],running={...baseRun,status:'running',freshness:'stale'};
  const c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?running:catalog({run:running,processing:false});});
  await c.refresh();assert.equal(c.data.canAnalyse,false);assert.equal(c.data.hasResult,false);assert.equal(c.data.active,true);
  await c.action({currentTarget:{dataset:{action:'cancel'}}});
  assert.deepEqual(calls.filter(v=>v.method==='POST').map(v=>v.path),['/api/activities/activity/dfa-alpha1/runs/run/cancel']);
});
function webComponent(catalogValue,runValue=null) {
  const slots=[],effects=[],calls=[];let cursor=0;
  const same=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>v===b[i]);
  const hooks={
    useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return[slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},
    useRef(initial){const i=cursor++;if(!(i in slots))slots[i]={current:initial};return slots[i];},
    useCallback(fn,deps){const i=cursor++;if(!same(slots[i]?.deps,deps))slots[i]={fn,deps};return slots[i].fn;},
    useEffect(fn,deps){const i=cursor++;if(!same(slots[i]?.deps,deps)){slots[i]={deps};effects.push(fn);}},
  };
  const jsx=(type,props)=>({type,props});const load=async()=>catalogValue;
  const client={cancelQueries:async()=>{},removeQueries(){},invalidateQueries:async()=>{}};
  const modules={react:hooks,'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'fragment'},'@tanstack/react-query':{useQueryClient:()=>client},'@lingui/react/macro':{Trans:'Trans',useLingui:()=>({t:parts=>Array.isArray(parts)?parts.join(''):parts,i18n:{locale:'en'}})},
    '@/hooks/useApi':{useApi:url=>({data:url.includes('/context')?null:url.includes('/runs/')?runValue:catalogValue,error:null,refreshData:load}),apiFetch:async(url,options)=>{calls.push({url,...options});return new Response(JSON.stringify(runValue??baseRun),{headers:{'Content-Type':'application/json'}});},extractErrorMessage:async()=> 'failed'},
    '@/lib/dfa-navigation':{nearestWindow,windowAtIndex,timeSupport,retryAfterSeconds,windowCount:()=>1}};
  const runtime=compile('../src/components/ActivityDFA.tsx',modules,{document:{hidden:false,addEventListener(){},removeEventListener(){}},window:{addEventListener(){},removeEventListener(){},setTimeout:()=>1,clearTimeout(){}}},'\nmodule.exports.testContent = DFAContent;');
  const render=()=>{cursor=0;const tree=runtime.testContent({activityId:'activity'});while(effects.length)effects.shift()();return tree;};
  return {calls,render,async ready(){let tree=render();for(let i=0;i<5;i++){await Promise.resolve();tree=render();}return tree;}};
}
function nodes(node){if(!node||typeof node!=='object')return[];return[node,...[node.props?.children].flat(Infinity).flatMap(nodes)];}
function contents(node){if(typeof node==='string')return node;if(typeof node==='number')return String(node);if(!node)return '';return[node.props?.children].flat(Infinity).map(contents).join('');}
test('actual web content shows explicit recalculation without posting for retained proof',async()=>{
  const c=webComponent(catalog({proofs:[retainedProof]}));const tree=await c.ready();assert.equal(c.calls.length,0);
  assert.ok(nodes(tree).some(n=>typeof n.props?.onClick==='function'&&contents(n)==='Recalculate analysis'));
});
test('actual web content hides numbers but preserves Cancel after processing withdrawal',async()=>{
  const running={...completed,status:'running',freshness:'stale'};const c=webComponent(catalog({run:running,processing:false}),running);const tree=await c.ready();
  assert.ok(!contents(tree).includes('120.0'));const cancel=nodes(tree).find(n=>typeof n.props?.onClick==='function'&&contents(n)==='Cancel analysis');assert.ok(cancel);
  cancel.props.onClick();await Promise.resolve();assert.deepEqual(c.calls.filter(v=>v.method==='POST').map(v=>v.url),['/api/activities/activity/dfa-alpha1/runs/run/cancel']);
});

test('registered native fixture is synthetic, fails closed, and follows the actual page flow',()=>{
  const app={globalData:{}};
  const fixture=name=>new Function('getApp','return ('+readFileSync(new URL('../../tests/fixtures/dfa/'+name,import.meta.url),'utf8')+');')(()=>app);
  const setup=fixture('native-setup.js'),request=fixture('native-request-mock.js'),storage=fixture('native-storage-mock.js');
  setup('expired','zh','light');
  assert.equal(storage('praxys-auth-token'),'');
  assert.equal(request({url:'https://example.invalid/api/settings',method:'POST',header:{Authorization:'never-forward'}}).statusCode,503);
  const url='https://example.invalid/api/activities/dfa-synthetic-running/dfa-alpha1';
  let c=request({url}).data;
  assert.equal(c.latest_run,null);assert.equal(c.source_confirmations.length,1);
  setup('prepare','en','dark');
  c=request({url}).data;assert.equal(c.latest_run,null);assert.deepEqual(c.source_confirmations,[]);
  const queued=request({url,method:'POST',data:{input:c.inputs[0].input}}).data;
  const runUrl=url+'/runs/'+queued.id;
  assert.equal(request({url:runUrl}).data.status,'running');
  const prepared=request({url:runUrl}).data;assert.equal(prepared.status,'awaiting_source_confirmation');
  const proof=request({url:url+'/source-confirmations',method:'POST'}).data;
  request({url,method:'POST',data:{input:c.inputs[0].input,source_confirmation_id:proof.id}});
  request({url:runUrl});const complete=request({url:runUrl}).data;
  assert.equal(complete.status,'complete');assert.equal(complete.windows.length,120);
  assert.equal(complete.navigation.page_anchors[1].offset,120);
  request({url,method:'DELETE'});assert.equal(request({url}).data.latest_run,null);
  assert.ok(!JSON.stringify(app.__dfaVerification).includes('never-forward'));
});

test('expired miniapp proof remains revocable with science or processing inactive', async () => {
  for (const disabled of ['policy_active', 'processing_authorized']) {
    const calls = [];
    let proofs = [retainedProof];
    const c = miniComponent(async (path, options) => {
      calls.push({ path, ...options });
      if (options.method === 'DELETE') { proofs = []; return { deleted: true }; }
      return { ...catalog({ proofs }), [disabled]: false };
    });
    await c.refresh();
    assert.equal(c.data.proof, null); // successful confirmation awaiting compute is separate
    assert.equal(c.data.retainedProof.id, 'proof');
    assert.equal(c.data.run, null);
    assert.equal(c.data.canAnalyse, false);
    c.deletePrompt({ currentTarget: { dataset: { scope: 'proof' } } });
    await c.erase();
    assert.deepEqual(calls.filter(v => v.method === 'DELETE').map(v => v.path), ['/api/activities/activity/dfa-alpha1/source-confirmations/proof']);
    assert.equal(c.data.retainedProof, null);
    assert.equal(calls.filter(v => v.method === 'POST').length, 0);
  }
});

test('multiple miniapp recordings require explicit choice for retained proof rights', async () => {
  const secondInput = { ...input, snapshot_id: 'second', parse_id: 'second-parse' };
  const secondProof = { ...retainedProof, id: 'second-proof', snapshot_id: 'second', parse_id: 'second-parse' };
  const calls = [];
  const c = miniComponent(async (path, options) => {
    calls.push({ path, ...options });
    return { ...catalog({ proofs: [retainedProof, secondProof], processing: false }), inputs: [
      { input, created_at: '2026-09-27T00:00:00' }, { input: secondInput, created_at: '2026-09-27T00:00:01' },
    ] };
  });
  await c.refresh();
  assert.equal(c.data.selected, -1);
  assert.equal(c.data.retainedProof, null);
  c.onRecording({ detail: { value: '1' } });
  assert.equal(c.data.retainedProof.id, 'second-proof');
  c.deletePrompt({ currentTarget: { dataset: { scope: 'proof' } } });
  await c.erase();
  assert.ok(calls.some(v => v.method === 'DELETE' && v.path.endsWith('/source-confirmations/second-proof')));
  c.deletePrompt({ currentTarget: { dataset: { scope: 'all' } } });
  await c.erase();
  assert.ok(calls.some(v => v.method === 'DELETE' && v.path === '/api/activities/activity/dfa-alpha1'));
  assert.equal(calls.filter(v => v.method === 'POST').length, 0);
});

test('miniapp failed compute submission retries saved confirmation without another attestation', async () => {
  const prepared = { ...baseRun, phase: 'prepare', status: 'awaiting_source_confirmation', source_confirmation_id: null,
    sensors: [{ sensor_ref: 'sensor', label: 'Polar H10' }], evidence_digest: 'evidence', statement_version: 'dfa-source-attestation-v1' };
  const calls = [];
  let fail = true;
  const c = miniComponent(async (path, options) => {
    calls.push({ path, ...options });
    if (path.endsWith('/source-confirmations')) return retainedProof;
    if (options.method === 'POST' && fail) { fail = false; throw new Error('temporary submission failure'); }
    return baseRun;
  });
  c.setData({ catalog: catalog(), selected: 0, run: prepared, checked: true, sensorIndex: 0, canAnalyse: true });
  await c.confirm();
  assert.equal(c.data.proof.id, 'proof');
  await c.confirm();
  assert.equal(calls.filter(v => v.path.endsWith('/source-confirmations')).length, 1);
  assert.equal(calls.filter(v => v.method === 'POST' && v.body.source_confirmation_id === 'proof').length, 2);
});
