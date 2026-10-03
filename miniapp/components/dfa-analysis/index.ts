import { request, type ApiError } from '../../utils/api-client';
import type { DFACatalog, DFAContext, DFAInput, DFARun, DFASourceConfirmation } from '../../types/api';
import { t, tNamed } from '../../utils/i18n';
import { chartColors, resolveTheme } from '../../utils/theme';
import { nearestWindow, timeSupport } from '../../utils/dfa-navigation';
import type { LineSeries } from '../line-chart/index';

function copy() {
  return {
    alpha: t('DFA α1'),
    sources: 'doi:10.3390/s21030821 · doi:10.3390/s22176536',
    description: t('Post-run analysis from ECG chest-strap beat intervals.'), close: t('Close'), refresh: t('Refresh'),
    policy: t('DFA analysis is awaiting scientific activation.'), missing: t('The original recording is not available yet. Sync this activity from your connected platform.'),
    provider: t('DFA analysis is not yet available for this activity’s connected platform.'), type: t('Only a single running session can be analysed.'), processing: t('Activity processing is unavailable. You can still delete this analysis.'),
    cooldown: t('Please wait before trying again.'), recalculate: t('Recalculate analysis'), pickTime: t('Choose an activity time'), goTime: t('Go to selected time'),
    recording: t('Choose a recording'), analyse: t('Analyse DFA α1'), confirmTitle: t('Confirm the source for this activity'),
    sourceHint: t('The file records a compatible chest strap, but does not directly identify the source of its beat intervals.'),
    sourceNote: t('Requires ECG chest-strap beat intervals. Confirm that the selected strap supplied them throughout this recording, without switching to another RR sensor or optical heart rate.'),
    sourceDetails: t('Source details'), duplicates: t('This file contains multiple entries for the same model; that does not establish whether they are the same physical strap.'),
    checking: t('Checking source status…'),
    windows: t('Each point analyses the preceding 120 seconds, every 5 seconds; zoom changes only the view. One suspect interval can affect several overlapping windows. Gaps mark windows that did not pass the checks.'),
    zoomIn:t('Zoom in'),zoomOut:t('Zoom out'),pan:t('Pan'),full:t('Full activity'),from:t('From (seconds)'),to:t('To (seconds)'),moreRows:t('More window details'),previousRows:t('Previous window details'),
    inferred:t('Source inferred from recording metadata'),inferredNote:t('The recording lists compatible ECG chest straps; its beat intervals are not directly linked to a sensor.'),withdraw:t('Withdraw inferred source'),unscheduled:t('This activity is not scheduled for automatic analysis. You can analyse it manually.'),cancelled:t('Analysis was cancelled.'),paused:t('Automatic analysis is paused.'),autoScience:t('Automatic DFA analysis is awaiting scientific activation.'),
    exclusions: t('Affected windows (one window can have multiple reasons)'), completeBeats:t('Complete beats'), intervalCoverage:t('Interval coverage'),
    sensor: t('Choose the chest strap'), statement: t('Throughout this recording, the selected ECG chest strap supplied the beat intervals; I did not switch to another RR sensor or optical heart rate.'),
    confirm: t('Confirm this strap throughout and analyse'), retry: t('Retry analysis'), cancel: t('Cancel analysis'),
    continuing: t('You can close this panel. Analysis will continue.'), source: t('Source confirmed by you'), timing: t('Estimated time alignment'),
    valid: t('Valid windows'), support: t('Supported recording time'), coverage: t('Coverage describes which data could be analysed, not measurement accuracy.'),
    overview: t('Whole activity coverage'), legend: t('Cobalt: supported · dark: unsupported · pale: paused'),
    heart: t('RR heart rate (bpm)'), power: t('Power (W)'), pace: t('Pace (s/km)'), previous: t('Previous'), next: t('Next'),
    details: t('Window values and quality details'), method: t('How this is calculated'),
    science: t('DFA α1 describes correlations in beat intervals. Each trailing 120-second window uses 4–16-beat scales, without interpolation or artifact correction. At least 200 complete beats and 98% interval coverage are required. Timing and quality cutoffs are Praxys guardrails, not validated physiological thresholds. Low heart rate may leave too few beats. These results do not diagnose fatigue or determine your training thresholds.'),
    revoke: t('Revoke source confirmation'), erase: t('Delete DFA analysis'), confirmDelete: t('Confirm deletion'), keep: t('Keep data'),
  };
}
function elapsed(ms: number, start = 0): string {
  const s = Math.max(0, Math.round((ms-start)/1000));
  return `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
}
function reason(code: string): string {
  const labels: Record<string,string> = {
    rr_missing: t('This recording has no beat intervals.'), source_unsupported: t('No compatible ECG chest strap was found.'),
    source_contradiction: t('Conflicting sensor evidence prevents analysis.'), activity_type_unsupported: t('Only a single running session can be analysed.'),
    timer_invalid: t('The activity timer cannot be reconstructed.'), insufficient_beats: t('Not enough complete beats.'),
    insufficient_coverage: t('Not enough interval coverage.'), rr_suspect: t('Possible irregular or missed beats.'),
    rr_out_of_range: t('Beat intervals outside the supported range.'), qc_incomplete: t('Not enough neighbouring beats to check quality.'),
    alignment_missing: t('Time alignment is unavailable.'), alignment_inconsistent: t('Time alignment is inconsistent.'),
    alignment_uncertain: t('Time alignment is too uncertain.'), rr_discontinuity: t('Interrupted beat sequence.'),
    numerical_invalid: t('DFA cannot be estimated in this window.'), atypical_value: t('Atypical value; no physiological conclusion.'),
  };
  if (code.endsWith('limit') || code === 'fit_too_large') return t('This recording exceeds the analysis limit.');
  return labels[code] ?? t('Analysis is unavailable. Refresh the recording or try again.');
}
interface Internal { epoch: number; timer: ReturnType<typeof setTimeout> | null; tasks: WechatMiniprogram.RequestTask[]; auto: boolean; visible: boolean; whole: DFARun | null; inputBinding: string; validation: Promise<void> | null }
const internals = new WeakMap<object,Internal>();
function local(component: object): Internal {
  let v = internals.get(component);
  if (!v) { v = { epoch:0, timer:null, tasks:[], auto:true, visible:true, whole:null, inputBinding:'', validation:null }; internals.set(component,v); }
  return v;
}
function stop(component: object) {
  const v = local(component); ++v.epoch;
  if (v.timer) clearTimeout(v.timer);
  v.validation = null; v.timer = null; v.tasks.forEach(task => task.abort()); v.tasks = [];
}

const runBindingKeys = ['id','status','freshness','result_revision','source_confirmation_id','source_proof_id','source_assurance','origin','rights_generation','snapshot_id','parse_id','generation','method_version','science_contract_digest'] as const;
function sameRunBinding(a:DFARun|null,b:DFARun|null):boolean {
  return Boolean(a && b && runBindingKeys.every(key=>a[key]===b[key]));
}
function inputBinding(component:{data:{catalog:DFACatalog|null;selected:number}}):string {
  return JSON.stringify(component.data.catalog?.inputs[component.data.selected]?.input)??'';
}
function wholeFor(component:{data:{catalog:DFACatalog|null;selected:number;run:DFARun|null;proof:DFASourceConfirmation|null;checking:boolean}}):DFARun|null {
  const state=local(component);
  return state.whole&&state.inputBinding===inputBinding(component)&&sameRunBinding(state.whole,component.data.run)&&acceptedResult(component,state.whole)?state.whole:null;
}
function acceptedResult(component:{data:{catalog:DFACatalog|null;selected:number;run:DFARun|null;proof:DFASourceConfirmation|null;checking:boolean}},run:DFARun):boolean {
  const catalog=component.data.catalog,input=catalog?.inputs[component.data.selected]?.input;
  if(!local(component).visible||component.data.checking||!sameRunBinding(run,component.data.run)
      || !catalog?.policy_active || !catalog.processing_authorized || catalog.automatic?.suppressed
      || run.status!=='complete' || run.freshness!=='current' || !run.result_revision
      || run.snapshot_id!==input?.snapshot_id || run.parse_id!==input?.parse_id
      || (run.rights_generation??0)!==(catalog.automatic?.rights_generation??0))return false;
  return run.source_assurance==='metadata_inferred'?Boolean(run.source_proof_id):
    [component.data.proof,...catalog.source_confirmations].some(p=>p&&p.id===run.source_confirmation_id&&p.snapshot_id===input.snapshot_id&&p.parse_id===input.parse_id);
}

Component({
  options: { addGlobalClass: true },
  properties: { activityId: { type: String, value: '' }, activityDate: { type: String, value: '' } },
  data: {
    tr: copy(), theme: resolveTheme(), loading:true, checking:false, busy:false, cooling:false, canAnalyse:false, error:'',
    timeMax:0, cursorSeconds:0, timeStatus:'', selectedOffset:0, pageOutline:'', catalog:null as DFACatalog|null,
    run:null as DFARun|null, selected:-1, sensorIndex:-1, duplicateSensors:false, showSourceDetails:false, proof:null as DFASourceConfirmation|null,
    retainedProof:null as DFASourceConfirmation|null,
    offset:0, status:'', active:false, stale:false, hasResult:false, headline:'', valid:'', support:'',
    sourceEntries:[] as string[],rangeFrom:0, rangeTo:0, rangeDomain:[] as number[], selectedWindow:null as {time:string;alpha:string;quality:string;coverage:string}|null, panMode:false, rowTotal:0, inputLabels:[] as string[], sensorLabels:[] as string[], times:[] as number[], dates:[] as string[], series:[] as LineSeries[],
    comparatorSeries:[] as LineSeries[], comparator:0, comparators:[] as string[],
    navigation:[] as {style:string; kind:string}[], pageLabels:[] as string[], pageIndex:0, pages:0,
    rows:[] as {id:number; time:string; alpha:string; value:string; quality:string; coverage:string}[],
    exclusions:[] as string[], showDetails:false, showScience:false, deletion:'', deletionText:'', contextError:'',
  },
  lifetimes: {
    attached() { void this.refresh(); },
    detached() { local(this).visible = false; stop(this); internals.delete(this); },
  },
  pageLifetimes: {
    hide() { local(this).visible = false; stop(this); this.setData({checking:true}); },
    show() { local(this).visible = true; void this.refresh(); },
  },
  methods: {
    block() {},
    close() { local(this).visible=false; stop(this); this.triggerEvent('close'); },
    async call<T>(path: string, method: 'GET'|'POST'|'DELETE' = 'GET', body?: unknown): Promise<T> {
      const state = local(this);
      let activeTask: WechatMiniprogram.RequestTask | null = null;
      try {
        return await request<T>(`/api/activities/${encodeURIComponent(this.properties.activityId)}/dfa-alpha1${path}`, {
          method, body, timeoutMs:30000, onRequestTask: task => { activeTask=task; state.tasks.push(task); },
        });
      } catch (error) {
        const wait=(error as ApiError).retryAfterSeconds??0;
        if(wait) { this.setData({cooling:true}); setTimeout(()=>{ if(internals.get(this)===state) this.setData({cooling:false}); },wait*1000); }
        throw error;
      } finally {
        state.tasks=state.tasks.filter(task=>task!==activeTask);
      }
    },
    refresh() {
      const state = local(this);
      if (state.validation) return state.validation;
      stop(this); const ticket = state.epoch;
      const pending = this.validateCatalog(ticket);
      state.validation = pending;
      void pending.finally(() => { if (state.validation === pending) state.validation = null; });
      return pending;
    },
    async validateCatalog(ticket:number) {
      const state = local(this), previous = this.data.catalog;
      this.setData({checking:true, busy:false, error:'', tr:copy(), theme:resolveTheme()});
      try {
        const catalog = await this.call<DFACatalog>('');
        if (ticket !== state.epoch || !state.visible) return;
        state.auto = false;
        const oldInput = previous?.inputs[this.data.selected]?.input;
        const matched = oldInput ? catalog.inputs.findIndex(v => JSON.stringify(v.input) === JSON.stringify(oldInput)) : -1;
        const automaticInput = catalog.latest_run?.origin==='automatic' ? catalog.inputs.findIndex(v=>v.input.snapshot_id===catalog.latest_run?.snapshot_id&&v.input.parse_id===catalog.latest_run?.parse_id) : -1;
        const selected = matched >= 0 ? matched : automaticInput >= 0 ? automaticInput : catalog.inputs.length === 1 ? 0 : -1;
        const input = catalog.inputs[selected]?.input;
        const retainedProof = input ? catalog.source_confirmations.find(p => p.snapshot_id === input.snapshot_id && p.parse_id === input.parse_id) ?? null : null;
        const proof = this.data.proof && catalog.source_confirmations.some(p => p.id === this.data.proof?.id && p.snapshot_id === input?.snapshot_id && p.parse_id === input?.parse_id) ? this.data.proof : null;
        const cached = this.data.run, latest = catalog.latest_run;
        const sameRun = sameRunBinding(cached,latest);
        const canAnalyse = (catalog.manual_policy_active??catalog.policy_active) && catalog.processing_authorized;
        const sameInput = Boolean(oldInput && input && JSON.stringify(oldInput) === JSON.stringify(input));
        const sameProof = cached?.source_assurance==='metadata_inferred'?Boolean(cached.source_proof_id&&latest?.source_proof_id===cached.source_proof_id):!cached?.source_confirmation_id || retainedProof?.id === cached.source_confirmation_id;
        const reuse = sameInput && sameRun && sameProof && (cached?.status!=='complete'||Boolean(state.whole&&sameRunBinding(state.whole,cached)&&state.inputBinding===JSON.stringify(input)));
        this.setData({catalog, selected, retainedProof, proof, canAnalyse, loading:false,
          inputLabels:catalog.inputs.map((v,i) => `${i+1} · ${v.created_at.replace('T',' ').slice(0,19)}`),comparators:[copy().heart,copy().power,copy().pace]});
        if (previous && !sameInput) this.setData({sensorIndex:-1,proof:null,offset:0,cursorSeconds:0});
        if (reuse) {
          this.setData({checking:false});
          this.setData({hasResult:acceptedResult(this,cached!)});
          if (cached && (cached.status === 'queued' || cached.status === 'running')) this.schedule(cached);
        } else {
          this.setData({run:null,hasResult:false,active:false,stale:false,checking:false,sensorIndex:-1});
          if (latest && latest.snapshot_id === input?.snapshot_id && latest.parse_id === input?.parse_id) await this.loadRun(latest.id);

        }
        this.scheduleCatalog();
      } catch { if (ticket === state.epoch) this.setData({loading:false,checking:true,error:t('The request failed. Try again.')}); }
    },
    scheduleCatalog() {
      const state=local(this),auto=this.data.catalog?.automatic;
      if(!state.visible||!auto?.gate_enabled||!auto.receipt||!['pending','deferred','queued','running'].includes(auto.receipt.state))return;
      if(state.timer)clearTimeout(state.timer);
      state.timer=setTimeout(()=>{state.timer=null;void this.refresh();},3000);
    },
    schedule(run:DFARun) {
      const state=local(this); if (!state.visible || !['queued','running'].includes(run.status)) return;
      if (state.timer) clearTimeout(state.timer);
      const age=Date.now()-Date.parse(run.created_at.endsWith('Z')?run.created_at:run.created_at+'Z');
      state.timer=setTimeout(()=>{state.timer=null;void this.loadRun(run.id);},Math.max(age<60000?3000:10000,(run.retry_after_seconds??0)*1000));
    },
    async loadRun(id: string) {
      const state = local(this); const ticket = state.epoch, binding=inputBinding(this);
      try {
        let run = await this.call<DFARun>(`/runs/${id}?offset=0&limit=1000`);
        if(ticket!==state.epoch||!state.visible||binding!==inputBinding(this))return;
        if (run.status==='complete' && run.result_revision) {
          const windows=[...(run.windows??[])];let next=run.page?.next_offset??null;
          while(next!==null){
            const page:DFARun=await this.call<DFARun>(`/runs/${id}/overview?offset=${next}&limit=1000&result_revision=${run.result_revision}`);
            if(ticket!==state.epoch||!state.visible)return;
            if(!sameRunBinding(page,run)||page.page?.offset!==next)throw new Error('changed');
            windows.push(...(page.windows??[]));next=page.page?.next_offset??null;
          }
          run={...run,windows};
        }
        if (ticket !== state.epoch || !state.visible || binding!==inputBinding(this)) return;
        const input = this.data.catalog?.inputs[this.data.selected]?.input;
        if (run.snapshot_id !== input?.snapshot_id || run.parse_id !== input?.parse_id) return;
        const proofValid = run.status !== 'complete' || (run.source_assurance==='metadata_inferred'&&Boolean(run.source_proof_id)) || [this.data.proof,...(this.data.catalog?.source_confirmations??[])].some(p=>p && p.id===run.source_confirmation_id && p.snapshot_id===input.snapshot_id && p.parse_id===input.parse_id);
        const sensors = run.sensors ?? [];
        const sensorLabels = sensors.map(s=>{
          const duplicates=sensors.filter(v=>v.label===s.label).sort((a,b)=>a.sensor_ref.localeCompare(b.sensor_ref));
          return duplicates.length>1?tNamed('{label} · Entry {entry}',{label:s.label,entry:duplicates.findIndex(v=>v.sensor_ref===s.sensor_ref)+1}):s.label;
        });
        const active = run.status === 'queued' || run.status === 'running';
        let status = run.status === 'queued' ? t('Waiting to analyse this recording…') : run.status === 'running'
          ? run.phase === 'prepare' ? t('Checking beat intervals and chest-strap evidence…') : t('Calculating valid windows…')
          : run.status === 'cancelled' ? t('Analysis was cancelled.') : reason(run.error_code ?? '');
        if (run.freshness === 'stale') status = t('The recording or method has changed. Recalculate to see current results.');
        const {windows:_,...metadata}=run;
        this.setData({run:metadata, active, status,sourceEntries:(run.candidates??[]).map(candidate=>{
          const duplicates=run.candidates!.filter(v=>v.label===candidate.label&&v.transport===candidate.transport);
          const label=candidate.label+(candidate.transport?' · '+candidate.transport:'');
          return duplicates.length>1?tNamed('{label} · Entry {entry}',{label,entry:duplicates.findIndex(v=>v.sensor_ref===candidate.sensor_ref)+1}):label;
        }), stale:run.freshness === 'stale', hasResult:false,
          sensorLabels,duplicateSensors:sensorLabels.some((label,i)=>label!==sensors[i].label), sensorIndex:run.sensors?.length === 1 ? 0 : this.data.sensorIndex});
        if (proofValid && acceptedResult(this,run)) await this.showResult(run);
        if (active) this.schedule(run);
        else if(run.error_code==='source_qualified')this.scheduleCatalog();
      } catch { if (ticket === state.epoch) this.setData({error:t('The request failed. Try again.'),active:false,hasResult:false}); }
    },
    async launch() {
      if (this.data.busy || this.data.cooling || !this.data.canAnalyse || this.data.checking) return;
      const catalog = this.data.catalog;
      const input = catalog?.inputs[this.data.selected]?.input;
      if (!catalog || !input) return;
      const proof = this.data.proof ?? catalog.source_confirmations.find(p => p.snapshot_id === input.snapshot_id && p.parse_id === input.parse_id);
      local(this).auto = false; const ticket = local(this).epoch;
      this.setData({busy:true,error:'',offset:0,hasResult:false});
      try {
        let rights=catalog.automatic?.rights_generation??0;
        if(catalog.automatic?.suppressed){
          const authorization=await this.call<{rights_generation:number}>('/reauthorize','POST',{catalog_revision:catalog.catalog_revision,expected_rights_generation:rights});
          if(ticket!==local(this).epoch)return;
          rights=authorization.rights_generation;
        }
        const run = await this.submit(input, proof?.id,rights);
        if (ticket === local(this).epoch) await this.loadRun(run.id);
      } catch { if (ticket === local(this).epoch) this.setData({error:t('The request failed. Try again.')}); }
      finally { if (ticket === local(this).epoch) this.setData({busy:false}); }
    },
    submit(input: DFAInput, proof?: string, expectedRights?:number) {
      return this.call<DFARun>('', 'POST', {input:{provider:input.provider,snapshot_id:input.snapshot_id,parse_id:input.parse_id},
        catalog_revision:this.data.catalog?.catalog_revision,source_confirmation_id:proof,expected_rights_generation:expectedRights??this.data.catalog?.automatic?.rights_generation??0});
    },
    async onRecording(e: WechatMiniprogram.PickerChange) {
      if (this.data.checking) return;
      stop(this);
      const selected = Number(e.detail.value), input = this.data.catalog?.inputs[selected]?.input;
      const retainedProof = this.data.catalog?.source_confirmations.find(p => p.snapshot_id === input?.snapshot_id && p.parse_id === input?.parse_id) ?? null;
      this.setData({selected,retainedProof,proof:null,run:null,hasResult:false,active:false,offset:0,busy:false,rangeFrom:0,rangeTo:0});
      const latest=this.data.catalog?.latest_run;
      if(latest&&latest.snapshot_id===input?.snapshot_id&&latest.parse_id===input?.parse_id)await this.loadRun(latest.id);
    },
    onSensor(e: WechatMiniprogram.PickerChange) { if (this.data.checking) return; stop(this); this.setData({sensorIndex:Number(e.detail.value),proof:null,busy:false}); },
    sourceDetails() { this.setData({showSourceDetails:!this.data.showSourceDetails}); },
    async confirm() {
      const run = this.data.run; const input = this.data.catalog?.inputs[this.data.selected]?.input;
      const sensor = run?.sensors?.[this.data.sensorIndex];
      if (!run || !sensor || !input || this.data.busy || this.data.cooling || !this.data.canAnalyse || this.data.checking) return;
      const ticket = local(this).epoch;
      this.setData({busy:true,error:''});
      try {
        const proof = this.data.proof ?? await this.call<DFASourceConfirmation>('/source-confirmations','POST', {
          run_id:run.id,sensor_ref:sensor.sensor_ref,evidence_digest:run.evidence_digest,statement_version:run.statement_version,expected_rights_generation:this.data.catalog?.automatic?.rights_generation??0,confirmed:true});
        if (ticket !== local(this).epoch) return;
        this.setData({proof});
        const next = await this.submit(input,proof.id);
        if (ticket === local(this).epoch) await this.loadRun(next.id);
      } catch { if (ticket === local(this).epoch) this.setData({error:t('The request failed. Try again.')}); }
      finally { if (ticket === local(this).epoch) this.setData({busy:false}); }
    },
    async action(e: WechatMiniprogram.TouchEvent) {
      const run = this.data.run; if (!run || this.data.busy) return;
      const action = String(e.currentTarget.dataset.action);
      const ticket = local(this).epoch;
      this.setData({busy:true});
      try { await this.call(`/runs/${run.id}/${action}`,'POST',action==='retry'?{expected_generation:run.generation,expected_rights_generation:this.data.catalog?.automatic?.rights_generation??0}:undefined); if (ticket===local(this).epoch) await this.refresh(); }
      catch { if (ticket===local(this).epoch) this.setData({error:t('The request failed. Try again.')}); }
      finally { if (ticket===local(this).epoch) this.setData({busy:false}); }
    },
    async showResult(source: DFARun) {
      const state=local(this),run=source.windows?source:wholeFor(this);
      if(!run||!acceptedResult(this,run))return;
      const nav=run.navigation,summary=run.summary;if(!nav||!summary)return;
      const ticket=state.epoch,binding=inputBinding(this);
      const from=this.data.rangeTo>0?this.data.rangeFrom:0,to=this.data.rangeTo>0?this.data.rangeTo:Math.ceil((nav.end_ms-nav.start_ms)/1000);
      const windows=(run.windows??[]).filter(w=>w.end_ms>=nav.start_ms+from*1000&&w.end_ms<=nav.start_ms+to*1000);
      let context:DFAContext|null=null;
      this.setData({contextError:'',rows:[],comparatorSeries:[],hasResult:false});
      if(this.data.comparator!==0){
        try {
          const all:DFAContext['windows']=[];let samples:string|null=null,overlayVersion:string|null=null;
          for(let pageOffset=0;pageOffset<(run.windows?.length??0);pageOffset+=1000){
            const page:DFAContext=await this.call<DFAContext>(`/runs/${run.id}/context?offset=${pageOffset}&limit=1000&result_revision=${run.result_revision}${samples?`&expected_samples_revision=${samples}`:''}`);
            if(ticket!==state.epoch||!state.visible||binding!==inputBinding(this)||!acceptedResult(this,run))return;
            if(page.result_revision!==run.result_revision||page.offset!==pageOffset||(samples!==null&&samples!==page.samples_revision)||(overlayVersion!==null&&overlayVersion!==page.overlay_version))throw new Error('changed');
            samples=page.samples_revision;overlayVersion=page.overlay_version;all.push(...page.windows);
          }
          context={result_revision:run.result_revision!,samples_revision:samples??'0',overlay_version:overlayVersion??'held2s-support80-v1',offset:0,windows:all};
        } catch {if(ticket===state.epoch)this.setData({contextError:t('Context changed or is unavailable. Refresh to reload it.')});}
        if(ticket!==state.epoch)return;
      }
      if(ticket!==state.epoch||!state.visible||binding!==inputBinding(this)||!acceptedResult(this,run))return;
      // Commit original windows only after all result/source/input/authority and
      // context-revision fences. A late reply cannot repopulate this cache.
      state.whole=run;state.inputBinding=binding;
      const colors=chartColors(),duration=nav.end_ms-nav.start_ms;
      const values=windows.map(w=>{const overlay=context?.windows.find(v=>v.index===w.index);return this.data.comparator===0?w.hr_bpm:this.data.comparator===1?overlay?.power_watts??null:overlay?.pace_sec_km??null;});
      const blocks=[...new Set(windows.map(w=>w.block))];
      const series=blocks.map(block=>({label:'DFA α1',color:colors.reasoning,values:windows.map(w=>w.block===block?w.alpha1:null)}));
      const comparatorSeries=blocks.map(block=>({label:this.data.comparators[this.data.comparator],color:colors.tick,values:windows.map((w,i)=>w.block===block?values[i]??null:null)}));
      const rows=windows.slice(this.data.offset,this.data.offset+120).map(w=>{
        const i=windows.findIndex(v=>v.index===w.index),value=values[i];
        return {id:w.index,time:`${elapsed(w.start_ms,nav.start_ms)}–${elapsed(w.end_ms,nav.start_ms)}`,alpha:w.alpha1?.toFixed(2)??'—',value:value?.toFixed(1)??'—',quality:[...w.reasons,...w.flags].map(reason).join(' ')||t('No issues detected by these checks.'),coverage:tNamed('Complete beats: {beats} · Interval coverage: {coverage}%',{beats:w.beat_count,coverage:(w.coverage_ms/1200).toFixed(1)})};
      });
      const navigation=[...nav.timer_blocks.map(([a,b])=>({kind:'unsupported',style:`left:${100*(a-nav.start_ms)/duration}%;width:${100*(b-a)/duration}%;`})),...nav.support.map(([a,b])=>({kind:'supported',style:`left:${100*(a-nav.start_ms)/duration}%;width:${100*(b-a)/duration}%;`}))];
      this.setData({rangeFrom:from,rangeTo:to,rangeDomain:[nav.start_ms+from*1000,nav.start_ms+to*1000],timeMax:Math.ceil(duration/1000),navigation,rows,rowTotal:windows.length,dates:[],times:[],series:series.map(s=>({...s,values:[]})),comparatorSeries:comparatorSeries.map(s=>({...s,values:[]})),headline:summary.valid_windows?t('Usable windows are ready to inspect.'):t('No windows passed the analysis checks.'),valid:`${summary.valid_windows} / ${summary.scheduled_windows}`,support:`${((summary.supported_time_ratio??0)*100).toFixed(1)}%`,exclusions:Object.entries(summary.excluded_reasons).map(([code,count])=>`${reason(code)} ${count}`)});
      // Array-path patches keep each native bridge update bounded; no point is
      // dropped, averaged, interpolated or renumbered for display.
      for(let i=0;i<windows.length;i+=200){
        const patch:Record<string,unknown>={};
        for(let j=i;j<Math.min(i+200,windows.length);j++){
          patch[`times[${j}]`]=windows[j].end_ms;patch[`dates[${j}]`]=elapsed(windows[j].end_ms,nav.start_ms);
          for(let k=0;k<series.length;k++){patch[`series[${k}].values[${j}]`]=series[k].values[j];patch[`comparatorSeries[${k}].values[${j}]`]=comparatorSeries[k].values[j];}
        }
        this.setData(patch);
      }
      if(ticket===state.epoch&&acceptedResult(this,run))this.setData({hasResult:true});
      this.updateTime(this.data.cursorSeconds);
    },
    selectWindow(e:WechatMiniprogram.CustomEvent<{time:number}>){
      if(this.data.checking)return;const whole=wholeFor(this);const window=whole?.windows?.find(w=>w.end_ms===e.detail.time);if(!window||!whole?.navigation)return;
      this.setData({selectedWindow:{time:`${elapsed(window.start_ms,whole.navigation.start_ms)}–${elapsed(window.end_ms,whole.navigation.start_ms)}`,alpha:window.alpha1?.toFixed(2)??'—',quality:[...window.reasons,...window.flags].map(reason).join(' ')||t('No issues detected by these checks.'),coverage:tNamed('Complete beats: {beats} · Interval coverage: {coverage}%',{beats:window.beat_count,coverage:(window.coverage_ms/1200).toFixed(1)})}});
    },
    async changeRange(from:number,to:number){
      const whole=wholeFor(this),nav=whole?.navigation;if(!nav||this.data.checking)return;
      const max=(nav.end_ms-nav.start_ms)/1000,span=Math.min(max,Math.max(5,to-from)),start=Math.min(Math.max(0,from),max-span);
      stop(this);this.setData({rangeFrom:start,rangeTo:start+span,offset:0});if(whole)await this.showResult(whole);
    },
    onFrom(e:WechatMiniprogram.Input){void this.changeRange(Number(e.detail.value),this.data.rangeTo);},
    onTo(e:WechatMiniprogram.Input){void this.changeRange(this.data.rangeFrom,Number(e.detail.value));},
    onFromSlider(e:WechatMiniprogram.SliderChange){void this.changeRange(Number(e.detail.value),this.data.rangeTo);},
    onToSlider(e:WechatMiniprogram.SliderChange){void this.changeRange(this.data.rangeFrom,Number(e.detail.value));},
    zoom(e:WechatMiniprogram.TouchEvent){const factor=Number(e.currentTarget.dataset.factor),center=(this.data.rangeFrom+this.data.rangeTo)/2,span=(this.data.rangeTo-this.data.rangeFrom)*factor;void this.changeRange(center-span/2,center+span/2);},
    full(){void this.changeRange(0,this.data.timeMax);},
    pan(){this.setData({panMode:!this.data.panMode});},
    panTime(e:WechatMiniprogram.SliderChange){if(!this.data.panMode)return;const span=this.data.rangeTo-this.data.rangeFrom;void this.changeRange(Number(e.detail.value),Number(e.detail.value)+span);},
    async rowsPage(e:WechatMiniprogram.TouchEvent){if(this.data.checking)return;const next=this.data.offset+Number(e.currentTarget.dataset.direction)*120;if(next<0||next>=this.data.rowTotal)return;stop(this);this.setData({offset:next});const whole=wholeFor(this);if(whole)await this.showResult(whole);},
    async cancelReceipt(){const receipt=this.data.catalog?.automatic?.receipt;if(!receipt)return;stop(this);this.setData({busy:true,hasResult:false});const ticket=local(this).epoch;try{await this.call(`/receipts/${receipt.id}/cancel`,'POST');if(ticket===local(this).epoch)await this.refresh();}catch{if(ticket===local(this).epoch)this.setData({error:t('The request failed. Try again.')});}},
    async withdraw(){const proof=this.data.run?.source_proof_id;if(!proof)return;stop(this);this.setData({hasResult:false});const ticket=local(this).epoch;try{await this.call(`/metadata-proofs/${proof}`,'DELETE');if(ticket===local(this).epoch)await this.refresh();}catch{if(ticket===local(this).epoch)this.setData({error:t('The request failed. Try again.')});}},
    updateTime(seconds:number) {
      const nav=this.data.run?.navigation;if(!nav)return;
      const time=nav.start_ms+seconds*1000, point=nearestWindow(nav,time), status=timeSupport(nav,time);
      const label=status==='supported'?t('Supported'):status==='paused'?t('Paused'):t('Unsupported');
      this.setData({cursorSeconds:seconds,timeStatus:`${elapsed(time,nav.start_ms)} · ${label} · ${t('Page')} ${point?Math.floor(point.index/120)+1:0}`,selectedOffset:point?Math.floor(point.index/120)*120:0});
    },
    onTime(e:WechatMiniprogram.SliderChange) {this.updateTime(Number(e.detail.value));},
    async goTime() {if(!this.data.run || this.data.checking)return;const span=this.data.rangeTo-this.data.rangeFrom;await this.changeRange(this.data.cursorSeconds-span/2,this.data.cursorSeconds+span/2);},
    async onPage(e: WechatMiniprogram.TouchEvent) {
      if (this.data.checking) return;
      const offset = this.data.offset + Number(e.currentTarget.dataset.direction)*120;
      if (offset<0 || !this.data.run || offset>=(this.data.run.page?.total??0)) return;
      stop(this); this.setData({offset,hasResult:false}); await this.loadRun(this.data.run.id);
    },
    async onJump(e: WechatMiniprogram.PickerChange) {
      const run=this.data.run; if (!run || this.data.checking) return;
      stop(this); this.setData({offset:Number(e.detail.value)*120,hasResult:false}); await this.loadRun(run.id);
    },
    async onComparator(e: WechatMiniprogram.PickerChange) {
      if (this.data.checking) return;
      stop(this); this.setData({comparator:Number(e.detail.value),rows:[],comparatorSeries:[],contextError:''}); if (this.data.run) await this.showResult(wholeFor(this)??this.data.run);
    },
    details() { this.setData({showDetails:!this.data.showDetails}); },
    science() { this.setData({showScience:!this.data.showScience}); },
    deletePrompt(e: WechatMiniprogram.TouchEvent) {
      const deletion=String(e.currentTarget.dataset.scope);
      this.setData({deletion,deletionText:deletion==='proof'?t('Revoke this source confirmation and remove its analysis results? The original recording will remain.'):t('Delete this activity’s DFA results and source confirmations? The original FIT will remain.')});
    },
    keep() { this.setData({deletion:''}); },
    async erase() {
      stop(this); local(this).auto=false;
      const proof=this.data.proof?.id??this.data.retainedProof?.id??this.data.run?.source_confirmation_id;
      if (this.data.deletion==='proof'&&!proof) return;
      const ticket=local(this).epoch;
      this.setData({busy:true,hasResult:false});
      try {
        await this.call(this.data.deletion==='proof'?`/source-confirmations/${proof}`:'','DELETE');
        if (ticket!==local(this).epoch || !local(this).visible) return;
        this.setData({run:null,proof:null,retainedProof:null,hasResult:false,deletion:'',offset:0}); await this.refresh();
      } catch { if(ticket===local(this).epoch) this.setData({error:t('The request failed. Try again.')}); }
      finally { if(ticket===local(this).epoch) this.setData({busy:false}); }
    },
  },
});
