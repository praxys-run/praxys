import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const ts=require('typescript');
import {nearestWindow,windowAtIndex,timeSupport,retryAfterSeconds} from '../src/lib/dfa-navigation.ts';
function compile(relative, modules, globals={}) {
  const source=readFileSync(new URL(relative,import.meta.url),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}}).outputText;
  const module={exports:{}};
  new Function('require','module','exports',...Object.keys(globals),code)(name=>modules[name]??{},module,module.exports,...Object.values(globals));
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
