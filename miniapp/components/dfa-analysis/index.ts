import { request, type ApiError } from '../../utils/api-client';
import type { DFACatalog, DFAContext, DFAInput, DFARun, DFASourceConfirmation } from '../../types/api';
import { t } from '../../utils/i18n';
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
    recording: t('Choose a recording'), analyse: t('Analyse recording'), confirmTitle: t('Confirm the source for this activity'),
    sourceHint: t('The file records a compatible chest strap, but does not directly identify the source of its beat intervals.'),
    sensor: t('Choose the chest strap'), statement: t('Throughout this recording, the selected ECG chest strap supplied the beat intervals; I did not switch to another RR sensor or optical heart rate.'),
    confirm: t('Confirm and analyse'), retry: t('Retry analysis'), cancel: t('Cancel analysis'),
    continuing: t('You can close this panel. Analysis will continue.'), source: t('Source confirmed by you'), timing: t('Estimated time alignment'),
    valid: t('Valid windows'), support: t('Supported recording time'), coverage: t('Coverage describes which data could be analysed, not measurement accuracy.'),
    overview: t('Whole activity coverage'), legend: t('Cobalt: supported · dark: unsupported · pale: paused'), jump: t('Jump to time'),
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
interface Internal { epoch: number; timer: ReturnType<typeof setTimeout> | null; tasks: WechatMiniprogram.RequestTask[]; auto: boolean; visible: boolean }
const internals = new WeakMap<object,Internal>();
function local(component: object): Internal {
  let v = internals.get(component);
  if (!v) { v = { epoch:0, timer:null, tasks:[], auto:true, visible:true }; internals.set(component,v); }
  return v;
}
function stop(component: object) {
  const v = local(component); ++v.epoch;
  if (v.timer) clearTimeout(v.timer);
  v.timer = null; v.tasks.forEach(task => task.abort()); v.tasks = [];
}

Component({
  options: { addGlobalClass: true },
  properties: { activityId: { type: String, value: '' }, activityDate: { type: String, value: '' } },
  data: {
    tr: copy(), theme: resolveTheme(), loading:true, busy:false, cooling:false, canAnalyse:false, error:'',
    timeMax:0, cursorSeconds:0, timeStatus:'', selectedOffset:0, pageOutline:'', catalog:null as DFACatalog|null,
    run:null as DFARun|null, selected:-1, sensorIndex:-1, checked:false, proof:null as DFASourceConfirmation|null,
    offset:0, status:'', active:false, stale:false, hasResult:false, headline:'', valid:'', support:'',
    inputLabels:[] as string[], sensorLabels:[] as string[], times:[] as number[], dates:[] as string[], series:[] as LineSeries[],
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
    hide() { local(this).visible = false; stop(this); this.setData({loading:true, run:null}); },
    show() { local(this).visible = true; void this.refresh(); },
  },
  methods: {
    block() {},
    close() { stop(this); this.triggerEvent('close'); },
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
    async refresh() {
      stop(this); const state = local(this); const ticket = state.epoch;
      this.setData({loading:true, busy:false, error:'', run:null, active:false, stale:false, hasResult:false, rows:[], comparatorSeries:[], proof:null, checked:false, sensorIndex:-1, tr:copy(), theme:resolveTheme()});
      try {
        const catalog = await this.call<DFACatalog>('');
        if (ticket !== state.epoch || !state.visible) return;
        const initialEntry = state.auto; state.auto = false;
        const selected = catalog.inputs.length === 1 ? 0 : -1;
        this.setData({catalog, selected, canAnalyse:catalog.policy_active && catalog.processing_authorized, loading:false, inputLabels:catalog.inputs.map((v,i) => `${i+1} · ${v.created_at.replace('T',' ').slice(0,19)}`),
          comparators:[copy().heart,copy().power,copy().pace]});
        if (catalog.latest_run && catalog.inputs.length === 1) await this.loadRun(catalog.latest_run.id);
        else if (initialEntry && catalog.policy_active && catalog.processing_authorized && catalog.inputs.length === 1 && !catalog.source_confirmations.some(p => p.snapshot_id === catalog.inputs[0].input.snapshot_id && p.parse_id === catalog.inputs[0].input.parse_id)) { await this.launch(); }
      } catch { if (ticket === state.epoch) this.setData({loading:false,error:t('The request failed. Try again.')}); }
    },
    async loadRun(id: string) {
      const state = local(this); const ticket = state.epoch;
      try {
        const run = await this.call<DFARun>(`/runs/${id}?offset=${this.data.offset}&limit=120`);
        if (ticket !== state.epoch || !state.visible) return;
        const active = run.status === 'queued' || run.status === 'running';
        let status = run.status === 'queued' ? t('Waiting to analyse this recording…') : run.status === 'running'
          ? run.phase === 'prepare' ? t('Checking beat intervals and chest-strap evidence…') : t('Calculating valid windows…')
          : run.status === 'cancelled' ? t('Analysis was cancelled.') : reason(run.error_code ?? '');
        if (run.freshness === 'stale') status = t('The recording or method has changed. Recalculate to see current results.');
        this.setData({run, active, status, stale:run.freshness === 'stale', hasResult:this.data.canAnalyse && run.status === 'complete' && run.freshness === 'current',
          sensorLabels:run.sensors?.map(s => s.label) ?? [], sensorIndex:run.sensors?.length === 1 ? 0 : this.data.sensorIndex});
        if (this.data.canAnalyse && run.status === 'complete' && run.freshness === 'current') await this.showResult(run);
        if (active) {
          const age = Date.now()-Date.parse(run.created_at.endsWith('Z') ? run.created_at : run.created_at+'Z');
          state.timer = setTimeout(() => { void this.loadRun(id); }, Math.max(age < 60000 ? 3000 : 10000, (run.retry_after_seconds??0)*1000));
        }
      } catch { if (ticket === state.epoch) this.setData({error:t('The request failed. Try again.'),active:false}); }
    },
    async launch() {
      if (this.data.busy || this.data.cooling || !this.data.canAnalyse) return;
      const catalog = this.data.catalog;
      const input = catalog?.inputs[this.data.selected]?.input;
      if (!catalog || !input) return;
      const proof = this.data.proof ?? catalog.source_confirmations.find(p => p.snapshot_id === input.snapshot_id && p.parse_id === input.parse_id);
      local(this).auto = false; const ticket = local(this).epoch;
      this.setData({busy:true,error:'',offset:0,hasResult:false});
      try {
        const run = await this.submit(input, proof?.id);
        if (ticket === local(this).epoch) await this.loadRun(run.id);
      } catch { if (ticket === local(this).epoch) this.setData({error:t('The request failed. Try again.')}); }
      finally { if (ticket === local(this).epoch) this.setData({busy:false}); }
    },
    submit(input: DFAInput, proof?: string) {
      return this.call<DFARun>('', 'POST', {input:{provider:input.provider,snapshot_id:input.snapshot_id,parse_id:input.parse_id},
        catalog_revision:this.data.catalog?.catalog_revision,source_confirmation_id:proof});
    },
    onRecording(e: WechatMiniprogram.PickerChange) { stop(this); this.setData({selected:Number(e.detail.value),proof:null,checked:false,run:null,hasResult:false,active:false,offset:0,busy:false}); },
    onSensor(e: WechatMiniprogram.PickerChange) { this.setData({sensorIndex:Number(e.detail.value),proof:null,checked:false}); },
    onCheck(e: WechatMiniprogram.CheckboxGroupChange) { this.setData({checked:e.detail.value.includes('confirmed')}); },
    async confirm() {
      const run = this.data.run; const input = this.data.catalog?.inputs[this.data.selected]?.input;
      const sensor = run?.sensors?.[this.data.sensorIndex];
      if (!run || !sensor || !input || !this.data.checked || this.data.busy || this.data.cooling || !this.data.canAnalyse) return;
      const ticket = local(this).epoch;
      this.setData({busy:true,error:''});
      try {
        const proof = this.data.proof ?? await this.call<DFASourceConfirmation>('/source-confirmations','POST', {
          run_id:run.id,sensor_ref:sensor.sensor_ref,evidence_digest:run.evidence_digest,statement_version:run.statement_version,confirmed:true});
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
      this.setData({busy:true});
      try { await this.call(`/runs/${run.id}/${action}`,'POST',action==='retry'?{expected_generation:run.generation}:undefined); await this.refresh(); }
      catch { this.setData({error:t('The request failed. Try again.')}); }
      finally { this.setData({busy:false}); }
    },
    async showResult(run: DFARun) {
      const nav = run.navigation; const summary = run.summary; if (!nav || !summary) return;
      const ticket = local(this).epoch;
      const colors = chartColors(); const duration = nav.end_ms-nav.start_ms;
      const navigation = [
        ...nav.timer_blocks.map(([a,b]) => ({kind:'unsupported',style:`left:${100*(a-nav.start_ms)/duration}%;width:${100*(b-a)/duration}%;`})),
        ...nav.support.map(([a,b]) => ({kind:'supported',style:`left:${100*(a-nav.start_ms)/duration}%;width:${100*(b-a)/duration}%;`})),
      ];
      let context: DFAContext|null = null;
      this.setData({contextError:'', rows:[], comparatorSeries:[]});
      if (this.data.comparator !== 0) {
        try { context = await this.call<DFAContext>(`/runs/${run.id}/context?offset=${this.data.offset}&limit=120&result_revision=${run.result_revision}`); }
        catch { if (ticket===local(this).epoch) this.setData({contextError:t('Context changed or is unavailable. Refresh to reload it.')}); }
        if (ticket!==local(this).epoch) return;
      }
      const windows = run.windows ?? [];
      const times:number[] = []; const dates:string[] = [], alpha:(number|null)[] = [], comp:(number|null)[] = [];
      const rows = windows.map((w,i) => {
        const overlay = context?.result_revision===run.result_revision && context.offset===this.data.offset ? context.windows.find(v=>v.index===w.index):undefined;
        const value = this.data.comparator===0 ? w.hr_bpm : this.data.comparator===1 ? overlay?.power_watts : overlay?.pace_sec_km;
        if (i && windows[i-1].block!==w.block) { times.push(w.start_ms); dates.push(elapsed(w.start_ms,nav.start_ms)); alpha.push(null); comp.push(null); }
        times.push(w.end_ms); dates.push(elapsed(w.end_ms,nav.start_ms)); alpha.push(w.alpha1); comp.push(value ?? null);
        return {id:w.index,time:`${elapsed(w.start_ms,nav.start_ms)}–${elapsed(w.end_ms,nav.start_ms)}`,alpha:w.alpha1?.toFixed(2)??'—',
          value:value?.toFixed(1)??'—',quality:[...w.reasons,...w.flags].map(reason).join(' ')||t('No issues detected by these checks.'),coverage:`${w.beat_count} · ${(w.coverage_ms/1200).toFixed(1)}%`};
      });
      this.setData({timeMax:Math.ceil(duration/1000),cursorSeconds:Math.round(((windows[0]?.end_ms??nav.start_ms)-nav.start_ms)/1000),
        pageOutline:windows.length?`left:${100*(windows[0].start_ms-nav.start_ms)/duration}%;width:${100*(windows[windows.length-1].end_ms-windows[0].start_ms)/duration}%;`:'',navigation,rows,dates,times,series:[{label:'DFA α1',color:colors.reasoning,values:alpha}],
        comparatorSeries:[{label:this.data.comparators[this.data.comparator],color:colors.tick,values:comp}],
        pageLabels:nav.page_anchors.map(p=>elapsed(p.time_ms,nav.start_ms)),pageIndex:Math.floor(this.data.offset/120),pages:nav.page_anchors.length,
        headline:summary.valid_windows?t('Usable windows are ready to inspect.'):t('No windows passed the analysis checks.'),
        valid:`${summary.valid_windows} / ${summary.scheduled_windows}`,support:`${((summary.supported_time_ratio??0)*100).toFixed(1)}%`,
        exclusions:Object.entries(summary.excluded_reasons).map(([code,count])=>`${reason(code)} ${count}`)});
      this.updateTime(this.data.cursorSeconds);
    },
    updateTime(seconds:number) {
      const nav=this.data.run?.navigation;if(!nav)return;
      const time=nav.start_ms+seconds*1000, point=nearestWindow(nav,time), status=timeSupport(nav,time);
      const label=status==='supported'?t('Supported'):status==='paused'?t('Paused'):t('Unsupported');
      this.setData({cursorSeconds:seconds,timeStatus:`${elapsed(time,nav.start_ms)} · ${label} · ${t('Page')} ${point?Math.floor(point.index/120)+1:0}`,selectedOffset:point?Math.floor(point.index/120)*120:0});
    },
    onTime(e:WechatMiniprogram.SliderChange) {this.updateTime(Number(e.detail.value));},
    async goTime() {if(!this.data.run)return;stop(this);this.setData({offset:this.data.selectedOffset,hasResult:false});await this.loadRun(this.data.run.id);},
    async onPage(e: WechatMiniprogram.TouchEvent) {
      const offset = this.data.offset + Number(e.currentTarget.dataset.direction)*120;
      if (offset<0 || !this.data.run || offset>=(this.data.run.page?.total??0)) return;
      stop(this); this.setData({offset,hasResult:false}); await this.loadRun(this.data.run.id);
    },
    async onJump(e: WechatMiniprogram.PickerChange) {
      const run=this.data.run; if (!run) return;
      stop(this); this.setData({offset:Number(e.detail.value)*120,hasResult:false}); await this.loadRun(run.id);
    },
    async onComparator(e: WechatMiniprogram.PickerChange) {
      stop(this); this.setData({comparator:Number(e.detail.value),rows:[],comparatorSeries:[],contextError:''}); if (this.data.run) await this.showResult(this.data.run);
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
      const proof=this.data.proof?.id??this.data.run?.source_confirmation_id;
      if (this.data.deletion==='proof'&&!proof) return;
      this.setData({busy:true});
      try {
        await this.call(this.data.deletion==='proof'?`/source-confirmations/${proof}`:'','DELETE');
        this.setData({run:null,proof:null,checked:false,hasResult:false,deletion:'',offset:0}); await this.refresh();
      } catch { this.setData({error:t('The request failed. Try again.')}); }
      finally { this.setData({busy:false}); }
    },
  },
});
