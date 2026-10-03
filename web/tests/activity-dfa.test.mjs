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
  compile('../../miniapp/components/dfa-analysis/index.ts',{'../../utils/api-client':{request},'../../utils/i18n':{t:value=>value,tNamed:(value,params={})=>value.replace(/\{(\w+)\}/g,(_,key)=>String(params[key]??`{${key}}`))},'../../utils/theme':{resolveTheme:()=> 'light',chartColors:()=>({reasoning:'blue',tick:'black'})},'../../utils/dfa-navigation':{nearestWindow,timeSupport}},
    {Component:value=>{definition=value;},setTimeout:()=>1,clearTimeout:()=>{}});
  const component={data:structuredClone(definition.data),properties:{activityId:'activity',activityDate:'2026-09-27'},setData(patch){Object.assign(this.data,patch);},triggerEvent(){}};
  for(const [name,method] of Object.entries(definition.methods)) component[name]=method.bind(component);
  component.lifecycle=Object.fromEntries(Object.entries(definition.pageLifetimes).map(([name,method])=>[name,method.bind(component)]));
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
  c.setData({catalog:catalog({proofs:[retainedProof],run:completed}),selected:0,run:completed,comparators:['HR','Power','Pace'],comparator:0,canAnalyse:true});
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
  const slots=[],effects=[],calls=[],loads=[],timers=new Map(),events=new Map(),removed=[],urls=[];let cursor=0,timerId=0,catalogError=null,nextCatalog=catalogValue,respond=null;
  const same=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>v===b[i]);
  const hooks={
    useState(initial){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return[slots[i],value=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},
    useRef(initial){const i=cursor++;if(!(i in slots))slots[i]={current:initial};return slots[i];},
    useCallback(fn,deps){const i=cursor++;if(!same(slots[i]?.deps,deps))slots[i]={fn,deps};return slots[i].fn;},
    useEffect(fn,deps){const i=cursor++;if(!same(slots[i]?.deps,deps)){slots[i]={deps};effects.push(fn);}},
  };
  const jsx=(type,props)=>({type,props});const load=async()=>{loads.push(1);const fresh=await nextCatalog;catalogValue=fresh;catalogError=fresh?null:'failed';return fresh;};
  const client={cancelQueries:async()=>{},removeQueries(query){removed.push(query);},invalidateQueries:async()=>{}};
  const modules={react:hooks,'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'fragment'},'@tanstack/react-query':{useQueryClient:()=>client},'@lingui/react/macro':{Trans:'Trans',useLingui:()=>({t:(parts,...values)=>Array.isArray(parts)?parts.map((part,i)=>part+(values[i]??'')).join(''):parts,i18n:{locale:'en'}})},
    '@/hooks/useApi':{useApi:(url,options)=>{urls.push({url,options});return {data:url.includes('/context')?null:url.includes('/runs/')?runValue:catalogValue,error:url.includes('/runs/')?null:catalogError,refreshData:load};},apiFetch:async(url,options)=>{calls.push({url,...options});if(respond)return respond(url,options);return new Response(JSON.stringify(runValue??baseRun),{headers:{'Content-Type':'application/json'}});},extractErrorMessage:async()=> 'failed'},
    '@/lib/dfa-navigation':{nearestWindow,windowAtIndex,timeSupport,retryAfterSeconds,windowCount:()=>1}};
  const document={hidden:false,addEventListener:(name,fn)=>events.set('document:'+name,fn),removeEventListener(){}},window={addEventListener:(name,fn)=>events.set('window:'+name,fn),removeEventListener(){},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id)};
  const runtime=compile('../src/components/ActivityDFA.tsx',modules,{document,window},'\nmodule.exports.testContent = DFAContent;');
  const render=()=>{cursor=0;const tree=runtime.testContent({activityId:'activity'});while(effects.length)effects.shift()();return tree;};
  return {calls,loads,removed,urls,render,document,setCatalog(value){nextCatalog=value;},setResponse(value){respond=value;},
    dispatch(name){events.get(name)?.();},flushTimers(){const pending=[...timers.values()];timers.clear();pending.forEach(fn=>fn());},
    async ready(){let tree=render();for(let i=0;i<10;i++){await Promise.resolve();tree=render();}await new Promise(setImmediate);return render();}};
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
  c.setData({ catalog: catalog(), selected: 0, run: prepared, sensorIndex: 0, canAnalyse: true });
  await c.confirm();
  assert.equal(c.data.proof.id, 'proof');
  await c.confirm();
  assert.equal(calls.filter(v => v.path.endsWith('/source-confirmations')).length, 1);
  assert.equal(calls.filter(v => v.method === 'POST' && v.body.source_confirmation_id === 'proof').length, 2);
});


const prepared={...baseRun,phase:'prepare',status:'awaiting_source_confirmation',source_confirmation_id:null,
  sensors:[{sensor_ref:'ref-b',label:'Garmin HRM-Pro Plus',rule_fingerprint:'rule'},{sensor_ref:'ref-a',label:'Garmin HRM-Pro Plus',rule_fingerprint:'rule'}],evidence_digest:'evidence',statement_version:'dfa-source-attestation-v1'};
const button=(tree,label)=>nodes(tree).find(n=>typeof n.props?.onClick==='function'&&contents(n)===label);
const resultNode=tree=>nodes(tree).find(n=>n.props&&'data-dfa-result'in n.props);

test('duplicate source labels preserve exact refs and only deliberate web action asserts current proof',async()=>{
  const c=webComponent(catalog({run:prepared}),prepared);let tree=await c.ready();
  assert.equal(c.calls.length,0);
  assert.ok(!nodes(tree).some(n=>n.props?.onCheckedChange));
  const source=nodes(tree).find(n=>typeof n.props?.onValueChange==='function'&&n.props.value===null);
  source.props.onValueChange('ref-b');tree=c.render();
  assert.ok(contents(tree).includes('Garmin HRM-Pro Plus · Entry 2'));
  assert.ok(contents(tree).includes('Garmin HRM-Pro Plus · Entry 1'));
  assert.equal(c.calls.length,0);
  assert.ok(button(tree,'Confirm this strap throughout and analyse').props['aria-describedby'].includes('dfa-source-statement'));
  c.setResponse(async(url,options)=>new Response(JSON.stringify(url.endsWith('/source-confirmations')?{...retainedProof,sensor_ref:'ref-b'}:baseRun)));
  button(tree,'Confirm this strap throughout and analyse').props.onClick();await c.ready();
  const confirmation=c.calls.find(v=>v.url.endsWith('/source-confirmations'));
  assert.deepEqual(JSON.parse(confirmation.body),{run_id:'run',sensor_ref:'ref-b',evidence_digest:'evidence',statement_version:'dfa-source-attestation-v1',expected_rights_generation:0,confirmed:true});
});

test('web foreground coalesces metadata checks and retains concealed result frame, cursor, comparator and page',async()=>{
  const pageRun=completed;
  const c=webComponent(catalog({proofs:[retainedProof],run:pageRun}),pageRun);let tree=await c.ready();
  const selects=nodes(tree).filter(n=>typeof n.props?.onValueChange==='function');
  selects.find(n=>n.props.value==='hr_bpm').props.onValueChange('power_watts');
  nodes(tree).find(n=>n.props?.type==='range').props.onChange({target:{value:'45'}});tree=c.render();
  let resolve; c.setCatalog(new Promise(r=>{resolve=r;}));
  c.document.hidden=true;c.dispatch('document:visibilitychange');
  let pending=c.render();assert.equal(resultNode(pending).props.style.opacity,0);
  assert.ok(nodes(pending).some(n=>n.type==='dl'&&n.props['aria-hidden']===true));
  assert.equal(nodes(pending).find(n=>n.props?.type==='range').props['aria-valuetext'],'Checking source status…');
  c.document.hidden=false;c.dispatch('document:visibilitychange');c.dispatch('window:focus');c.flushTimers();await Promise.resolve();
  assert.equal(c.loads.length,2);assert.equal(c.calls.filter(v=>v.method==='POST').length,0);
  resolve(catalog({proofs:[retainedProof],run:pageRun}));tree=await c.ready();
  assert.equal(resultNode(tree).props.style,undefined);
  assert.ok(nodes(tree).some(n=>n.props.value==='power_watts'&&n.props.onValueChange));
  assert.equal(nodes(tree).find(n=>n.props?.type==='range').props.value,45);
  assert.ok(c.urls.some(v=>v.url.includes('limit=1000')));assert.equal(c.removed.length,0);
});

test('web foreground rejects same catalog revision after proof, authority, input or result changes and fails closed on error',async()=>{
  for(const change of [v=>({...v,source_confirmations:[]}),v=>({...v,policy_active:false}),v=>({...v,processing_authorized:false}),
    v=>({...v,inputs:[{input:{...input,parse_id:'changed'},created_at:'2026-10-02'}]}),
    v=>({...v,latest_run:{...completed,result_revision:'changed'}}),v=>({...v,latest_run:{...completed,freshness:'stale'}}),()=>null]){
    const c=webComponent(catalog({proofs:[retainedProof],run:completed}),completed);await c.ready();
    c.setCatalog(change(catalog({proofs:[retainedProof],run:completed})));
    c.dispatch('window:focus');c.flushTimers();const tree=await c.ready(),result=resultNode(tree);
    assert.ok(!result || result.props.style?.opacity===0);assert.equal(c.calls.length,0);
  }
});

test('web saved proof survives foreground validation and retries only compute after failed submit',async()=>{
  const one={...prepared,sensors:[{sensor_ref:'sensor',label:'Polar H10'}]};
  const c=webComponent(catalog({run:one}),one);let tree=await c.ready();let submitCount=0;
  c.setResponse(async(url)=>url.endsWith('/source-confirmations')?new Response(JSON.stringify(retainedProof)):
    new Response(JSON.stringify(baseRun),{status:++submitCount===1?503:200}));
  button(tree,'Confirm this strap throughout and analyse').props.onClick();tree=await c.ready();
  assert.ok(button(tree,'Retry analysis'));
  c.setCatalog(catalog({proofs:[retainedProof],run:one}));c.dispatch('window:focus');c.flushTimers();tree=await c.ready();
  assert.ok(button(tree,'Retry analysis'));button(tree,'Retry analysis').props.onClick();await c.ready();
  assert.equal(c.calls.filter(v=>v.url.endsWith('/source-confirmations')).length,1);
  assert.equal(c.calls.filter(v=>v.method==='POST'&&!v.url.endsWith('/source-confirmations')).length,2);
});

test('native duplicates retain refs and foreground validation preserves result and navigation without recomputation',async()=>{
  let metadata=catalog({proofs:[retainedProof],run:completed}),resolve;const calls=[];
  const c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?completed:metadata;});
  await c.refresh();c.setData({offset:120,comparator:1,cursorSeconds:45,showDetails:true});
  metadata=new Promise(r=>{resolve=r;});c.lifecycle.hide();const refresh=c.lifecycle.show();
  assert.equal(c.data.checking,true);assert.equal(c.data.loading,false);assert.equal(c.data.hasResult,true);assert.equal(c.data.run.id,'run');
  const pending=c.refresh();assert.equal(calls.filter(v=>!v.path.includes('/runs/')).length,2);
  resolve(catalog({proofs:[retainedProof],run:completed}));await pending;
  assert.equal(c.data.checking,false);assert.equal(c.data.offset,120);assert.equal(c.data.comparator,1);assert.equal(c.data.cursorSeconds,45);assert.equal(c.data.showDetails,true);
  assert.equal(calls.filter(v=>v.path.includes('/runs/')).length,1);assert.equal(calls.filter(v=>v.method==='POST').length,0);
  c.setData({catalog:catalog({run:prepared}),selected:0});
  const sensors=miniComponent(async()=>prepared);sensors.setData({catalog:catalog({run:prepared}),selected:0,canAnalyse:true});await sensors.loadRun('run');
  assert.deepEqual(sensors.data.sensorLabels,['Garmin HRM-Pro Plus · Entry 2','Garmin HRM-Pro Plus · Entry 1']);
  assert.equal(sensors.data.sensorIndex,-1);
});

test('native failed validation or revoked proof conceals numbers and close fences catalog replies',async()=>{
  for(const changed of [()=>Promise.reject(new Error('offline')),()=>catalog({run:completed}),()=>({...catalog({proofs:[retainedProof],run:completed}),policy_active:false})]){
    let metadata=catalog({proofs:[retainedProof],run:completed});const c=miniComponent(async path=>path.includes('/runs/')?completed:metadata);
    await c.refresh();metadata=changed();await c.refresh();assert.ok(!c.data.hasResult||c.data.checking);
  }
  let resolve;const c=miniComponent(()=>new Promise(r=>{resolve=r;}));const pending=c.refresh();c.close();resolve(catalog({proofs:[retainedProof],run:completed}));await pending;
  assert.equal(c.data.catalog,null);assert.equal(c.data.run,null);
});

test('web source changes from an already open picker cannot strand pending validation',async()=>{
  const metadata=catalog({run:prepared}),c=webComponent(metadata,prepared);
  let tree=await c.ready();
  const source=tree=>nodes(tree).find(n=>n.props?.onValueChange&&['ref-a','ref-b',null].includes(n.props.value));
  source(tree).props.onValueChange('ref-a');tree=c.render();
  const openPickerChange=source(tree).props.onValueChange;
  let resolve;c.setCatalog(new Promise(r=>{resolve=r;}));
  c.dispatch('window:focus');c.flushTimers();await Promise.resolve();tree=c.render();
  assert.equal(button(tree,'Confirm this strap throughout and analyse').props.disabled,true);
  openPickerChange('ref-b');source(tree).props.onValueChange('ref-b');tree=c.render();
  assert.equal(source(tree).props.value,'ref-a');
  assert.equal(c.loads.length,2);assert.equal(c.calls.length,0);
  resolve(metadata);tree=await c.ready();
  assert.equal(source(tree).props.value,'ref-a');
  assert.equal(button(tree,'Confirm this strap throughout and analyse').props.disabled,false);
  assert.ok(!contents(tree).includes('Checking source status…'));
  source(tree).props.onValueChange('ref-b');tree=c.render();
  assert.equal(source(tree).props.value,'ref-b');assert.equal(c.calls.length,0);
});

test('web recording changes from an already open picker leave current validation and selection intact',async()=>{
  const second={...input,snapshot_id:'second',parse_id:'second-parse'};
  const metadata={...catalog({run:prepared}),inputs:[{input,created_at:'2026-10-02T00:00:00'},{input:second,created_at:'2026-10-02T00:01:00'}]};
  const c=webComponent(metadata,prepared);let tree=await c.ready();
  const recording=tree=>nodes(tree).find(n=>n.props?.onValueChange&&[null,'snapshot','second'].includes(n.props.value));
  recording(tree).props.onValueChange('snapshot');tree=c.render();
  const openPickerChange=recording(tree).props.onValueChange;
  let resolve;c.setCatalog(new Promise(r=>{resolve=r;}));
  c.dispatch('window:focus');c.flushTimers();await Promise.resolve();tree=c.render();
  openPickerChange('second');recording(tree).props.onValueChange('second');tree=c.render();
  assert.equal(recording(tree).props.value,'snapshot');assert.equal(c.loads.length,2);assert.equal(c.calls.length,0);
  resolve(metadata);tree=await c.ready();
  assert.ok(!contents(tree).includes('Checking source status…'));
  assert.equal(recording(tree).props.value,'snapshot');
  recording(tree).props.onValueChange('second');tree=c.render();
  assert.equal(recording(tree).props.value,'second');assert.ok(button(tree,'Analyse DFA α1'));
  assert.equal(c.calls.length,0);
});

test('native source changes from an already open picker cannot cancel the pending catalog reply',async()=>{
  let metadata=catalog({run:prepared}),resolve;const calls=[];
  const c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?prepared:metadata;});
  await c.refresh();c.onSensor({detail:{value:'0'}});
  metadata=new Promise(r=>{resolve=r;});const pending=c.refresh();
  c.onSensor({detail:{value:'1'}});
  assert.equal(c.data.sensorIndex,0);assert.equal(c.data.checking,true);
  assert.equal(c.refresh(),pending);
  resolve(catalog({run:prepared}));await pending;
  assert.equal(c.data.checking,false);assert.equal(c.data.sensorIndex,0);
  assert.equal(calls.filter(v=>!v.path.includes('/runs/')).length,2);assert.equal(calls.filter(v=>v.method==='POST').length,0);
  c.onSensor({detail:{value:'1'}});assert.equal(c.data.sensorIndex,1);
});

test('native recording changes from an already open picker preserve validation and resume usability',async()=>{
  const second={...input,snapshot_id:'second',parse_id:'second-parse'};
  const currentMetadata={...catalog({run:prepared}),inputs:[{input,created_at:'2026-10-02T00:00:00'},{input:second,created_at:'2026-10-02T00:01:00'}]};
  let metadata=currentMetadata,resolve;const calls=[];
  const c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?prepared:metadata;});
  await c.refresh();c.onRecording({detail:{value:'0'}});await c.loadRun('run');
  metadata=new Promise(r=>{resolve=r;});const pending=c.refresh();
  c.onRecording({detail:{value:'1'}});
  assert.equal(c.data.selected,0);assert.equal(c.data.checking,true);assert.equal(c.data.run.id,'run');
  assert.equal(c.refresh(),pending);
  resolve(currentMetadata);await pending;
  assert.equal(c.data.checking,false);assert.equal(c.data.selected,0);assert.equal(c.data.run.id,'run');
  assert.equal(calls.filter(v=>!v.path.includes('/runs/')).length,2);assert.equal(calls.filter(v=>v.method==='POST').length,0);
  c.onRecording({detail:{value:'1'}});assert.equal(c.data.selected,1);assert.equal(c.data.run,null);
});

test('opening and focusing a pristine sole recording performs reads only',async()=>{
  const c=webComponent(catalog());let tree=await c.ready();
  assert.ok(button(tree,'Analyse DFA α1'));assert.equal(c.calls.filter(v=>v.method==='POST').length,0);
  c.dispatch('window:focus');c.flushTimers();tree=await c.ready();
  assert.ok(button(tree,'Analyse DFA α1'));assert.equal(c.calls.filter(v=>v.method==='POST').length,0);
  const nativeCalls=[],native=miniComponent(async(path,options)=>{nativeCalls.push({path,...options});return catalog();});
  await native.refresh();await native.refresh();assert.equal(nativeCalls.filter(v=>v.method==='POST').length,0);
});

test('completed inferred results stay readable with gate OFF and never show owner confirmation label',async()=>{
  const inferred={...completed,origin:'automatic',source_assurance:'metadata_inferred',source_proof_id:'inferred-proof',source_confirmation_id:null,rights_generation:0};
  const metadata={...catalog({run:inferred}),automatic:{gate_enabled:false,scheduled:true,suppressed:false,rights_generation:0,receipt:{id:'receipt',state:'complete',reason:null,run_id:'run',generation:1}},manual_policy_active:true,auto_policy_active:true};
  const c=webComponent(metadata,inferred),tree=await c.ready();
  assert.ok(contents(tree).includes('Source inferred from recording metadata'));
  assert.ok(!contents(tree).includes('Source confirmed by you'));
  assert.ok(!button(tree,'Revoke source confirmation'));assert.ok(button(tree,'Withdraw inferred source'));
  assert.equal(c.calls.filter(v=>v.method==='POST').length,0);
});

test('automatic waiting receipt has no redundant start and historical no receipt has explicit manual fallback',async()=>{
  const automatic={gate_enabled:true,scheduled:true,suppressed:false,rights_generation:0,receipt:{id:'receipt',state:'deferred',reason:'DFA_QUEUE_FULL',run_id:null,generation:1}};
  const c=webComponent({...catalog(),automatic});let tree=await c.ready();
  assert.ok(!button(tree,'Analyse DFA α1'));assert.ok(button(tree,'Cancel analysis'));
  assert.equal(c.calls.filter(v=>v.method==='POST').length,0);
  const old=webComponent({...catalog(),automatic:{...automatic,scheduled:false,receipt:null}});tree=await old.ready();
  assert.ok(contents(tree).includes('This activity is not scheduled for automatic analysis. You can analyse it manually.'));
  assert.ok(button(tree,'Analyse DFA α1'));assert.equal(old.calls.filter(v=>v.method==='POST').length,0);
});

function inferredRun(id, revision, alpha=.9, snapshot=input.snapshot_id, parse=input.parse_id) {
  return {...completed,id,result_revision:revision,snapshot_id:snapshot,parse_id:parse,origin:'automatic',source_assurance:'metadata_inferred',source_proof_id:'inferred-'+id,source_confirmation_id:null,rights_generation:0,windows:completed.windows.map(w=>({...w,alpha1:alpha}))};
}
function automaticCatalog(run, inputs=[{input,created_at:'2026-10-02T00:00:00'}]) {
  return {...catalog({run}),inputs,automatic:{gate_enabled:false,scheduled:true,suppressed:false,rights_generation:0,receipt:{id:'receipt',state:'complete',reason:null,run_id:run.id,generation:1}}};
}
const nextNativeTurn=()=>new Promise(setImmediate);

test('native late old run reply cannot poison original-window cache after fresh foreground result',async()=>{
  const old=inferredRun('old','old-revision',.1),fresh=inferredRun('new','new-revision',.9),calls=[];
  let current=old,resolveOld;
  const c=miniComponent(async(path,options)=>{
    calls.push({path,...options});
    if(!path.includes('/runs/'))return automaticCatalog(current);
    if(path.includes('/old?'))return new Promise(r=>{resolveOld=r;});
    return fresh;
  });
  const initial=c.refresh();await nextNativeTurn();
  c.lifecycle.hide();current=fresh;c.lifecycle.show();await c.refresh();
  assert.equal(c.data.run.id,'new');assert.equal(c.data.rows[0].alpha,'0.90');
  resolveOld(old);await initial;
  await c.changeRange(0,120);
  assert.equal(c.data.run.id,'new');assert.equal(c.data.rows[0].alpha,'0.90');assert.equal(c.data.hasResult,true);
  await c.onComparator({detail:{value:'0'}});
  assert.equal(c.data.rows[0].alpha,'0.90');
  assert.equal(calls.filter(v=>v.method==='POST').length,0);
});

test('native late old sample context cannot replace current result or comparator data',async()=>{
  const old=inferredRun('old','old-revision',.1),fresh=inferredRun('new','new-revision',.9),calls=[];
  let current=old,resolveOld;
  const context=(run,value)=>({result_revision:run.result_revision,samples_revision:'samples-'+run.id,overlay_version:'held2s-support80-v1',offset:0,windows:[{index:0,power_watts:value,pace_sec_km:300}]});
  const c=miniComponent(async(path,options)=>{
    calls.push({path,...options});
    if(!path.includes('/runs/'))return automaticCatalog(current);
    if(path.includes('/context'))return path.includes('/old/')?new Promise(r=>{resolveOld=r;}):context(fresh,290);
    return path.includes('/old?')?old:fresh;
  });
  c.setData({comparator:1});const initial=c.refresh();await nextNativeTurn();
  assert.ok(resolveOld);c.lifecycle.hide();current=fresh;c.lifecycle.show();await c.refresh();
  assert.equal(c.data.run.id,'new');assert.equal(c.data.rows[0].alpha,'0.90');assert.equal(c.data.rows[0].value,'290.0');
  resolveOld(context(old,110));await initial;await c.changeRange(0,120);
  assert.equal(c.data.rows[0].alpha,'0.90');assert.equal(c.data.rows[0].value,'290.0');
  assert.equal(calls.filter(v=>v.method==='POST').length,0);
});

test('native entry loads exact saved automatic recording and picker loads it with GET only',async()=>{
  const second={...input,snapshot_id:'second',parse_id:'second-parse'},saved=inferredRun('saved','saved-revision',.9,second.snapshot_id,second.parse_id);
  const inputs=[{input,created_at:'2026-10-02T00:00:00'},{input:second,created_at:'2026-10-02T00:00:01'}],calls=[];
  const metadata=automaticCatalog(saved,inputs);
  const c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?saved:metadata;});
  await c.refresh();assert.equal(c.data.selected,1);assert.equal(c.data.run.id,'saved');assert.equal(c.data.hasResult,true);
  assert.equal(c.data.rows[0].alpha,'0.90');
  await c.onRecording({detail:{value:'0'}});assert.equal(c.data.selected,0);assert.equal(c.data.run,null);assert.equal(c.data.hasResult,false);
  await c.refresh();assert.equal(c.data.selected,0);assert.equal(c.data.run,null); // deliberate exact choice survives latest auto
  const before=calls.length;await c.onRecording({detail:{value:'1'}});
  assert.equal(c.data.selected,1);assert.equal(c.data.run.id,'saved');assert.equal(c.data.hasResult,true);
  assert.equal(calls.slice(before).length,1);assert.ok(calls.at(-1).path.includes('/runs/saved?'));
  assert.equal(calls.filter(v=>v.method==='POST').length,0);
});

test('native refuses whole-window reuse across proof, rights, method or input binding changes',async()=>{
  const saved=inferredRun('saved','saved-revision');
  for(const changed of [{source_proof_id:'different-proof'},{rights_generation:1},{method_version:'different-method'},{science_contract_digest:'different-science'},{snapshot_id:'different-input'}]){
    const c=miniComponent(async path=>path.includes('/runs/')?saved:automaticCatalog(saved));await c.refresh();
    c.setData({run:{...c.data.run,...changed},hasResult:false,rows:[]});
    await c.changeRange(0,120);assert.deepEqual(c.data.rows,[]);assert.equal(c.data.hasResult,false);
  }
});


test('native original-window consumers reject withdrawn source or authority without fetching',async()=>{
  const saved=inferredRun('saved','saved-revision');
  for(const change of [c=>({...c,processing_authorized:false}),c=>({...c,policy_active:false}),c=>({...c,automatic:{...c.automatic,suppressed:true}})]){
    const calls=[],c=miniComponent(async(path,options)=>{calls.push({path,...options});return path.includes('/runs/')?saved:automaticCatalog(saved);});
    await c.refresh();c.setData({catalog:change(c.data.catalog),hasResult:false,rows:[],selectedWindow:null});
    const before=calls.length;await c.changeRange(0,120);c.selectWindow({detail:{time:120000}});
    assert.deepEqual(c.data.rows,[]);assert.equal(c.data.selectedWindow,null);assert.equal(calls.length,before);
  }
});
