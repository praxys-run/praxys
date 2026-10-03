/** Field Lab extension: qualification first, then a gap-preserving window view. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Trans, useLingui } from '@lingui/react/macro';
import type { DFACatalog, DFAContext, DFAInput, DFAOverview, DFARun, DFASourceConfirmation } from '@/types/api';
import { apiFetch, extractErrorMessage, useApi } from '@/hooks/useApi';
import MetricDetailSheet from '@/components/MetricDetailSheet';
import ScienceNote from '@/components/ScienceNote';
import DFAPlot from '@/components/DFAPlot';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { nearestWindow, windowAtIndex, windowCount, timeSupport, retryAfterSeconds } from '@/lib/dfa-navigation';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

function elapsed(ms: number, start = 0): string {
  const seconds = Math.max(0, Math.round((ms-start)/1000));
  return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
}

export default function ActivityDFA({ activityId, activityDate, onClose }: { activityId: string; activityDate?: string; onClose: () => void }) {
  const { t, i18n } = useLingui();
  return <MetricDetailSheet open onOpenChange={(open) => { if (!open) onClose(); }} size="wide"
    title="DFA α1" description={<span className="dark:text-foreground">{t`Post-run analysis from ECG chest-strap beat intervals.`}{activityDate && <span className="mt-1 block font-data">{new Date(activityDate).toLocaleDateString(i18n.locale)}</span>}</span>}>
    <DFAContent activityId={activityId} />
  </MetricDetailSheet>;
}

export function DFAContent({ activityId }: { activityId: string }) {
  const { t } = useLingui();
  const base = `/api/activities/${encodeURIComponent(activityId)}/dfa-alpha1`;
  const client = useQueryClient();
  const [verified, setVerified] = useState(false);
  const [visible, setVisible] = useState(!document.hidden);
  const [selected, setSelected] = useState('');
  const [requestedRun, setRunId] = useState('');
  const [focusTime,setFocusTime] = useState<number|null>(null);
  const [whole, setWhole] = useState<DFARun|null>(null);
  const [wholeContext, setWholeContext] = useState<DFAContext|null>(null);
  const [detailLoading,setDetailLoading]=useState(false);
  const [detailError,setDetailError]=useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState('');
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [cursorTime, setCursorTime] = useState<number | null>(null);
  const [sensor, setSensor] = useState('');
  const [savedProof, setSavedProof] = useState<DFASourceConfirmation | null>(null);
  const [comparator, setComparator] = useState('hr_bpm');
  const [deleting, setDeleting] = useState<'all' | 'proof' | null>(null);
  const [, setSamplesRevision] = useState<string | null>(null);
  const epoch = useRef(0);
  const auto = useRef(true);
  const hasLayout = useRef(false);
  const validation = useRef<Promise<void> | null>(null);
  const accepted = useRef<{catalog: DFACatalog | null; run: DFARun | null; snapshot: string}>({catalog:null,run:null,snapshot:''});
  const validatedRun = useRef<DFARun | null>(null);
  const retainedResult = useRef<DFARun | null>(null);
  const mutation = useRef<AbortController | null>(null);
  const catalog = useApi<DFACatalog>(base, { enabled: false, retry: () => false,
    refetchOnWindowFocus: false, timeoutMs: 30000 });
  const chosenSnapshot = selected || (catalog.data?.latest_run?.origin==='automatic'?catalog.data.latest_run.snapshot_id:'') || (catalog.data?.inputs.length === 1 ? catalog.data.inputs[0].input.snapshot_id : '');
  const runId = requestedRun || (catalog.data?.inputs.length === 1 || catalog.data?.latest_run?.origin==='automatic' ? catalog.data.latest_run?.id ?? '' : '');
  const run = useApi<DFARun>(`${base}/runs/${runId}?offset=0&limit=1000`, {
    enabled: verified && !catalog.error && visible && Boolean(runId) && Boolean(chosenSnapshot),
    refetchInterval: query => {
      const value = query.state.data as DFARun | undefined;
      if (!verified || !visible || catalog.error || query.state.error || !value || !['queued','running'].includes(value.status)) return false;
      const normal = Date.now()-Date.parse(value.created_at.endsWith('Z') ? value.created_at : value.created_at+'Z') < 60000 ? 3000 : 10000;
      return Math.max(normal, (value.retry_after_seconds ?? 0)*1000);
    },
    refetchOnWindowFocus: false, refetchOnMount: false, retry: () => false, timeoutMs: 30000,
  });
  const mayAnalyse = (catalog.data?.manual_policy_active ?? catalog.data?.policy_active) === true && catalog.data?.processing_authorized === true;
  const chosenInput = catalog.data?.inputs.find(v => v.input.snapshot_id === chosenSnapshot)?.input;
  const ownedRun = !catalog.error && verified && run.data?.id === runId && run.data.snapshot_id === chosenSnapshot && run.data.parse_id === chosenInput?.parse_id ? run.data : null;
  const validProof = ownedRun?.status !== 'complete' || (ownedRun.source_assurance==='metadata_inferred' && Boolean(ownedRun.source_proof_id)) || [savedProof, ...(catalog.data?.source_confirmations ?? [])].some(p => p && p.id === ownedRun.source_confirmation_id && p.snapshot_id === chosenInput?.snapshot_id && p.parse_id === chosenInput?.parse_id);
  const runValidated = ownedRun?.status !== 'complete' || Boolean(validatedRun.current?.id === ownedRun.id && validatedRun.current.freshness === 'current' && (['queued','running'].includes(validatedRun.current.status) || validatedRun.current.result_revision === ownedRun.result_revision));
  const current = runValidated && catalog.data?.policy_active && catalog.data.processing_authorized && !run.error && validProof && ownedRun?.freshness === 'current' ? ownedRun : null;
  if (verified && !catalog.error) {
    accepted.current = {catalog:catalog.data,run:ownedRun,snapshot:chosenSnapshot};
    retainedResult.current = current;
  }
  const result = verified ? current : retainedResult.current;


  const loadCatalog = catalog.refreshData;
  const acceptCatalog = useCallback(async (fresh: DFACatalog | null, ticket: number) => {
    if (ticket !== epoch.current || document.hidden) return;
    if (!fresh) { hasLayout.current = true; setFailure('request_failed'); return; }
    const previous = accepted.current;
    const previousInput = previous.catalog?.inputs.find(v => v.input.snapshot_id === previous.snapshot)?.input;
    const freshInput = fresh.inputs.find(v => v.input.snapshot_id === previous.snapshot)?.input;
    const sameInput = Boolean(previousInput && freshInput && JSON.stringify(previousInput) === JSON.stringify(freshInput));
    const latest = fresh.latest_run; validatedRun.current = latest;
    const cached = previous.run;
    const sameRun = cached && latest && ['id','status','freshness','result_revision','source_confirmation_id','snapshot_id','parse_id','generation'].every(key => cached[key as keyof DFARun] === latest[key as keyof DFARun]);
    const proofStillValid = !cached?.source_confirmation_id || fresh.source_confirmations.some(p => p.id === cached.source_confirmation_id && p.snapshot_id === freshInput?.snapshot_id && p.parse_id === freshInput?.parse_id);
    if (previous.catalog && (!sameInput || !sameRun || !proofStillValid || !fresh.policy_active || !fresh.processing_authorized)) {
      retainedResult.current = null;
      client.removeQueries({ predicate: q => String(q.queryKey[0]).startsWith(`${base}/runs/`) });
      setRunId(latest && latest.snapshot_id === freshInput?.snapshot_id && latest.parse_id === freshInput?.parse_id ? latest.id : '');
      if (!sameInput) { setSelected(''); setSensor(''); setFocusTime(null); setCursorTime(null); setSavedProof(null); }
    }
    if (savedProof && (!sameInput || !fresh.source_confirmations.some(p => p.id === savedProof.id))) setSavedProof(null);
    hasLayout.current = true;
    setVerified(true);
    auto.current = false;
  }, [base, client, savedProof]);
  const refresh = useCallback(() => {
    if (validation.current) return validation.current;
    const ticket = ++epoch.current;
    mutation.current?.abort();
    setVerified(false); setFailure(''); setBusy(false);
    const pending = (async () => {
      await client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
      if (ticket !== epoch.current) return;
      await acceptCatalog(await loadCatalog(), ticket);
    })();
    validation.current = pending;
    void pending.finally(() => { if (validation.current === pending) validation.current = null; });
    return pending;
  }, [base, client, loadCatalog, acceptCatalog]);
  const refreshRef = useRef(refresh); refreshRef.current = refresh;

  useEffect(() => {
    void refreshRef.current();
    let foregroundTimer: ReturnType<typeof window.setTimeout> | null = null;
    const focus = () => {
      setVisible(!document.hidden); setVerified(false);
      if (document.hidden) {
        ++epoch.current; mutation.current?.abort(); validation.current = null;
        if (foregroundTimer !== null) window.clearTimeout(foregroundTimer);
        foregroundTimer = null;
        void client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
      } else if (foregroundTimer === null) {
        foregroundTimer = window.setTimeout(() => { foregroundTimer = null; void refreshRef.current(); }, 0);
      }
    };
    window.addEventListener('focus', focus);
    document.addEventListener('visibilitychange', focus);
    return () => {
      epoch.current += 1; mutation.current?.abort();
      if (foregroundTimer !== null) window.clearTimeout(foregroundTimer);
      window.removeEventListener('focus', focus); document.removeEventListener('visibilitychange', focus);
      void client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
      client.removeQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
    };
  }, [client, base]);

  useEffect(()=>{
    const receipt=catalog.data?.automatic?.receipt;
    if(!verified||!visible||catalog.error||!catalog.data?.automatic?.gate_enabled||!receipt||!['pending','deferred','queued','running'].includes(receipt.state))return;
    const timer=window.setTimeout(()=>void refreshRef.current(),3000);
    return ()=>window.clearTimeout(timer);
  },[verified,visible,catalog.error,catalog.data?.automatic?.gate_enabled,catalog.data?.automatic?.receipt?.state,catalog.data?.automatic?.receipt?.generation]);

  useEffect(()=>{
    if(!verified||!visible||current?.status!=='complete'||!current.result_revision)return;
    const first=current;
    if(whole?.id===first.id&&whole.result_revision===first.result_revision&&whole.windows?.length===first.page?.total)return;
    const ticket=epoch.current,controller=new AbortController();
    setDetailLoading(true);setDetailError(false);
    void (async()=>{
      const windows=[...(first.windows??[])];let next=first.page?.next_offset??null;
      while(next!==null){
        const response=await apiFetch(`${base}/runs/${first.id}/overview?offset=${next}&limit=1000&result_revision=${first.result_revision}`,{signal:controller.signal,cache:'no-store'});
        if(!response.ok)throw new Error('changed');
        const page=await response.json() as DFAOverview;
        if(ticket!==epoch.current||page.id!==first.id||page.result_revision!==first.result_revision||page.snapshot_id!==first.snapshot_id||page.parse_id!==first.parse_id||page.science_contract_digest!==first.science_contract_digest||page.method_version!==first.method_version||page.rights_generation!==first.rights_generation||page.source_proof_id!==first.source_proof_id||page.page?.offset!==next)throw new Error('changed');
        windows.push(...(page.windows??[]));next=page.page?.next_offset??null;
      }
      if(ticket===epoch.current){setWhole({...first,windows});setDetailLoading(false);}
    })().catch(()=>{if(ticket===epoch.current&&!controller.signal.aborted){setDetailError(true);setDetailLoading(false);setWhole(null);}});
    return ()=>controller.abort();
  },[verified,visible,current?.id,current?.result_revision,base]);

  useEffect(()=>{
    if(!verified||!visible||current?.status!=='complete'||comparator==='hr_bpm'){return;}
    const first=current,ticket=epoch.current,controller=new AbortController();
    setWholeContext(null);
    void(async()=>{
      const windows:DFAContext['windows']=[];let samples:string|null=null,overlayVersion:string|null=null;
      for(let pageOffset=0;pageOffset<(first.page?.total??0);pageOffset+=1000){
        const response=await apiFetch(`${base}/runs/${first.id}/context?offset=${pageOffset}&limit=1000&result_revision=${first.result_revision}${samples?`&expected_samples_revision=${samples}`:''}`,{signal:controller.signal,cache:'no-store'});
        if(!response.ok)throw new Error('changed');
        const page=await response.json() as DFAContext;
        if(ticket!==epoch.current||page.result_revision!==first.result_revision||page.offset!==pageOffset||(samples!==null&&page.samples_revision!==samples)||(overlayVersion!==null&&page.overlay_version!==overlayVersion))throw new Error('changed');
        samples=page.samples_revision;overlayVersion=page.overlay_version;windows.push(...page.windows);
      }
      if(ticket===epoch.current)setWholeContext({result_revision:first.result_revision!,samples_revision:samples??'0',overlay_version:overlayVersion??'held2s-support80-v1',offset:0,windows});
    })().catch(()=>{if(ticket===epoch.current&&!controller.signal.aborted)setDetailError(true);});
    return()=>controller.abort();
  },[verified,visible,current?.id,current?.result_revision,comparator,base]);

  const request = async <T,>(path: string, body?: unknown, method = 'POST'): Promise<T> => {
    const controller = new AbortController(); mutation.current = controller;
    const response = await apiFetch(base+path, { method, signal: controller.signal, cache: 'no-store',
      headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    const wait = retryAfterSeconds(response.headers.get('Retry-After'));
    if (wait) setCooldownUntil(Date.now()+wait*1000);
    if (!response.ok) throw new Error(await extractErrorMessage(response, t`The request failed. Try again.`));
    return response.json() as Promise<T>;
  };
  const cooling = cooldownUntil > 0;
  useEffect(() => {
    if (!cooldownUntil) return;
    const timer = window.setTimeout(() => setCooldownUntil(0), Math.max(0,cooldownUntil-Date.now()));
    return () => window.clearTimeout(timer);
  }, [cooldownUntil]);
  const launch = async (input: DFAInput, proof?: string) => {
    if (!catalog.data || busy || cooling || !mayAnalyse) return;
    auto.current = false;
    const ticket = epoch.current;
    setBusy(true); setFailure('');
    try {
      let rights=catalog.data.automatic?.rights_generation??0;
      if(catalog.data.automatic?.suppressed){
        const authorization=await request<{rights_generation:number}>('/reauthorize',{catalog_revision:catalog.data.catalog_revision,expected_rights_generation:rights});
        if(ticket!==epoch.current)return;
        rights=authorization.rights_generation;
      }
      const value = await request<DFARun>('', { input: { provider: input.provider, snapshot_id: input.snapshot_id, parse_id: input.parse_id },
        catalog_revision: catalog.data.catalog_revision, source_confirmation_id: proof, expected_rights_generation:rights });
      if (ticket !== epoch.current) return;
      validatedRun.current = value; setRunId(value.id); setFocusTime(null);
      await client.invalidateQueries({ predicate: q => String(q.queryKey[0]).startsWith(`${base}/runs/`) });
    } catch { if (ticket === epoch.current) setFailure(t`The request failed. Try again.`); }
    finally { if (ticket === epoch.current) setBusy(false); }
  };

  const reason = (code: string): string => {
    const labels: Record<string,string> = {
      rr_missing: t`This recording has no beat intervals.`, source_unsupported: t`No compatible ECG chest strap was found.`,
      source_contradiction: t`Conflicting sensor evidence prevents analysis.`, activity_type_unsupported: t`Only a single running session can be analysed.`,
      timer_invalid: t`The activity timer cannot be reconstructed.`, insufficient_beats: t`Not enough complete beats.`,
      insufficient_coverage: t`Not enough interval coverage.`, rr_suspect: t`Possible irregular or missed beats.`,
      rr_out_of_range: t`Beat intervals outside the supported range.`, qc_incomplete: t`Not enough neighbouring beats to check quality.`,
      alignment_missing: t`Time alignment is unavailable.`, alignment_inconsistent: t`Time alignment is inconsistent.`,
      alignment_uncertain: t`Time alignment is too uncertain.`, rr_discontinuity: t`Interrupted beat sequence.`,
      numerical_invalid: t`DFA cannot be estimated in this window.`, atypical_value: t`Atypical value; no physiological conclusion.`,
    };
    if (code.endsWith('limit') || code === 'fit_too_large') return t`This recording exceeds the analysis limit.`;
    return labels[code] ?? t`Analysis is unavailable. Refresh the recording or try again.`;
  };
  const chosen = catalog.data?.inputs.find(v => v.input.snapshot_id === chosenSnapshot)?.input;
  const selectedSensor = sensor || (result?.sensors?.length === 1 ? result.sensors[0].sensor_ref : '');
  const proof = savedProof ?? catalog.data?.source_confirmations.find(p => p.snapshot_id === chosen?.snapshot_id && p.parse_id === chosen?.parse_id);
  const sensorLabels = (result?.sensors ?? []).map(s => {
    const duplicates = result?.sensors?.filter(v => v.label === s.label).sort((a,b) => a.sensor_ref.localeCompare(b.sensor_ref)) ?? [];
    const entry = duplicates.findIndex(v => v.sensor_ref === s.sensor_ref)+1;
    const label = s.label;
    return {...s, displayLabel:duplicates.length > 1 ? t`${label} · Entry ${entry}` : label};
  });
  const duplicateSensors = sensorLabels.some(s => s.displayLabel !== s.label);
  const statusRun = verified ? ownedRun : accepted.current.run;
  const active = statusRun && ['queued','running'].includes(statusRun.status) ? statusRun : null;
  const runAction = async (action: 'retry' | 'cancel') => {
    const actionable = action === 'cancel' ? ownedRun : current;
    if (!actionable) return;
    const ticket = epoch.current;
    setBusy(true);
    try { await request(`/runs/${actionable.id}/${action}`, action === 'retry' ? { expected_generation: actionable.generation, expected_rights_generation:catalog.data?.automatic?.rights_generation??0 } : undefined); if (ticket === epoch.current) await refresh(); }
    catch { if (ticket === epoch.current) setFailure(t`The request failed. Try again.`); } finally { if (ticket === epoch.current) setBusy(false); }
  };
  const confirm = async () => {
    if (!current || !chosen || !selectedSensor || busy || cooling || !verified) return;
    setBusy(true); setFailure('');
    const ticket = epoch.current;
    try {
      const p = savedProof ?? (proof?.sensor_ref === selectedSensor ? proof : null) ?? await request<DFASourceConfirmation>('/source-confirmations', { run_id: current.id, sensor_ref: selectedSensor,
        evidence_digest: current.evidence_digest, statement_version: current.statement_version, expected_rights_generation:catalog.data?.automatic?.rights_generation??0, confirmed: true });
      if (ticket !== epoch.current) return;
      setSavedProof(p);
      const next = await request<DFARun>('', { input: { provider: chosen.provider, snapshot_id: chosen.snapshot_id, parse_id: chosen.parse_id },
        catalog_revision: catalog.data?.catalog_revision, source_confirmation_id: p.id, expected_rights_generation:catalog.data?.automatic?.rights_generation??0 });
      if (ticket === epoch.current) { validatedRun.current = next; setRunId(next.id); }
    } catch { if (ticket === epoch.current) setFailure(t`The request failed. Try again.`); }
    finally { if (ticket === epoch.current) setBusy(false); }
  };
  const cancelReceipt = async()=>{
    const id=catalog.data?.automatic?.receipt?.id;if(!id||busy)return;
    const ticket=++epoch.current;validation.current=null;mutation.current?.abort();setVerified(false);retainedResult.current=null;setWhole(null);setWholeContext(null);setBusy(true);
    try {await request(`/receipts/${id}/cancel`);if(ticket===epoch.current)await refresh();}
    catch {if(ticket===epoch.current)setFailure(t`The request failed. Try again.`);}
    finally {if(ticket===epoch.current)setBusy(false);}
  };
  const remove = async () => {
    const id = proof?.id ?? current?.source_confirmation_id;
    if (deleting === 'proof' && !id) return;
    setBusy(true); auto.current = false;
    const ticket = ++epoch.current; validation.current = null;
    setVerified(false); retainedResult.current = null;setWhole(null);setWholeContext(null);
    await client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
    mutation.current?.abort();
    try {
      await request(deleting === 'proof' ? `/source-confirmations/${id}` : '', undefined, 'DELETE');
      if (ticket !== epoch.current) return;
      client.removeQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
      setRunId(''); setSavedProof(null); setDeleting(null); await refresh();
    } catch { setFailure(t`The request failed. Try again.`); } finally { setBusy(false); }
  };

  if (!verified && !hasLayout.current) return <div className="space-y-4" aria-busy="true"><Skeleton className="h-20 w-full" /><Skeleton className="h-64 w-full" /></div>;
  const data = catalog.data;
  const failureText = failure || catalog.error || run.error ? t`The request failed. Try again.` : '';
  const nav = result?.navigation;
  const start = nav?.start_ms ?? 0;
  const cursor = cursorTime ?? result?.windows?.[0]?.end_ms ?? start;
  const point = nav ? nearestWindow(nav,cursor) : null;
  const coverageState = nav ? timeSupport(nav,cursor) : 'unsupported';
  const coverageLabel = coverageState === 'supported' ? t`Supported` : coverageState === 'paused' ? t`Paused` : t`Unsupported`;
  const targetPage = point ? Math.floor(point.index/120)+1 : 0;
  const staleResult = run.data?.freshness === 'stale' && run.data.snapshot_id === chosenSnapshot;
  const contextMatches = wholeContext?.result_revision === result?.result_revision;
  const comparatorLabel = comparator === 'hr_bpm' ? t`RR heart rate (bpm)` : comparator === 'power_watts' ? t`Power (W)` : t`Pace (s/km)`;

  return <div className="space-y-6 pb-3 dark:[&_.text-muted-foreground]:text-foreground">
    <h3 className="text-lg font-semibold"><Trans>DFA α1</Trans></h3>
    <div id="dfa-checking" role="status" className="min-h-6 text-sm leading-6 text-muted-foreground">{!verified && !failureText && <Trans>Checking source status…</Trans>}</div>
    {failureText && <Alert variant="destructive"><AlertDescription>{failureText}<Button className="min-h-11" variant="outline" onClick={() => void refresh()}><Trans>Refresh</Trans></Button></AlertDescription></Alert>}
    {!data?.policy_active && <p role="status"><Trans>DFA analysis is awaiting scientific activation.</Trans></p>}
    {data?.availability === 'original_unavailable' && <p><Trans>The original recording is not available yet. Sync this activity from your connected platform.</Trans></p>}
    {data?.availability === 'provider_unsupported' && <p><Trans>DFA analysis is not yet available for this activity’s connected platform.</Trans></p>}
    {data?.availability === 'activity_type_unsupported' && <p>{reason('activity_type_unsupported')}</p>}
    {data && !data.processing_authorized && <p><Trans>Activity processing is unavailable. You can still delete this analysis.</Trans></p>}
    {cooling && <p role="status"><Trans>Please wait before trying again.</Trans></p>}
    {data && data.inputs.length > 1 && <div className="space-y-2"><Label htmlFor="dfa-recording"><Trans>Recording version</Trans></Label>
      <Select value={selected || null} onValueChange={v => { if (!verified || validation.current) return; ++epoch.current; validation.current = null; mutation.current?.abort(); retainedResult.current = null; setSelected(v ?? ''); setSavedProof(null); setSensor(''); setFocusTime(null); setRunId(data.latest_run?.snapshot_id === v ? data.latest_run.id : ''); }}>
        <SelectTrigger id="dfa-recording" aria-disabled={!verified} aria-label={t`Recording version`} className="min-h-11 w-full"><SelectValue>{data.inputs.find(v => v.input.snapshot_id === selected)?.created_at.replace('T',' ').slice(0,19) ?? t`Choose a recording`}</SelectValue></SelectTrigger><SelectContent>
          {data.inputs.map((v,i) => <SelectItem className="min-h-11" key={v.input.snapshot_id} value={v.input.snapshot_id}><span className="font-data">{i+1} · {new Date(v.created_at+'Z').toLocaleString()}</span></SelectItem>)}
        </SelectContent></Select></div>}
    {chosen && !catalog.error && !active && !(data?.automatic?.gate_enabled && data.automatic.receipt && ['pending','deferred','queued','running'].includes(data.automatic.receipt.state)) &&
      <Button className="min-h-11" disabled={busy || cooling || !mayAnalyse || !verified} onClick={() => void launch(chosen, proof?.id)}>{result?.status==='complete' || staleResult || proof ? t`Recalculate analysis` : t`Analyse DFA α1`}</Button>}
    {data?.automatic?.gate_enabled&&!data.automatic.scheduled&&<p className="text-sm text-muted-foreground"><Trans>This activity is not scheduled for automatic analysis. You can analyse it manually.</Trans></p>}
    {data?.automatic?.suppressed&&!active&&<p role="status"><Trans>Analysis was cancelled.</Trans></p>}
    {data?.automatic?.receipt&&!data.automatic.suppressed&&['pending','deferred','queued','running','gate_paused','science_inactive','processing_unavailable','suppressed','stale','unavailable'].includes(data.automatic.receipt.state)&&!active&&<div className="flex flex-col gap-2"><p role="status">{data.automatic.suppressed?t`Analysis was cancelled.`:data.automatic.receipt.state==='gate_paused'?t`Automatic analysis is paused.`:data.automatic.receipt.state==='science_inactive'?t`Automatic DFA analysis is awaiting scientific activation.`:data.automatic.receipt.state==='unavailable'?reason(data.automatic.receipt.reason??''):t`Waiting to analyse this recording…`}</p>{['pending','deferred','gate_paused'].includes(data.automatic.receipt.state)&&!data.automatic.suppressed&&<Button className="min-h-11" variant="outline" onClick={()=>void cancelReceipt()}><Trans>Cancel analysis</Trans></Button>}</div>}
    {run.data?.freshness === 'stale' && <p><Trans>The recording or method has changed. Recalculate to see current results.</Trans></p>}
    {active && <div role="status" className="space-y-3"><p>{active.status === 'queued' ? t`Waiting to analyse this recording…` : active.phase === 'prepare' ? t`Checking beat intervals and chest-strap evidence…` : t`Calculating valid windows…`}</p>
      <p className="text-sm text-muted-foreground"><Trans>You can close this panel. Analysis will continue.</Trans></p>
      <Button className="min-h-11" variant="outline" disabled={busy} onClick={() => void runAction('cancel')}><Trans>Cancel analysis</Trans></Button></div>}
    {result?.status === 'awaiting_source_confirmation' && <div className="space-y-4">
      <h3 className="font-semibold"><Trans>Confirm the source for this activity</Trans></h3>
      <p className="text-sm text-muted-foreground"><Trans>The file records a compatible chest strap, but does not directly identify the source of its beat intervals.</Trans></p>
      <Select value={selectedSensor || null} onValueChange={v => { if (!verified || validation.current) return; ++epoch.current; validation.current = null; mutation.current?.abort(); setBusy(false); setSensor(v ?? ''); setSavedProof(null); }}>
        <SelectTrigger aria-label={t`Choose the chest strap`} aria-disabled={!verified} className="min-h-11 w-full whitespace-normal data-[size=default]:h-auto *:data-[slot=select-value]:line-clamp-none *:data-[slot=select-value]:block"><SelectValue className="min-w-0 whitespace-normal break-words font-data">{sensorLabels.find(s => s.sensor_ref === selectedSensor)?.displayLabel ?? t`Choose the chest strap`}</SelectValue></SelectTrigger><SelectContent>
          {sensorLabels.map(s => <SelectItem className="min-h-11" key={s.sensor_ref} value={s.sensor_ref}><span className="whitespace-normal break-words font-data">{s.displayLabel}</span></SelectItem>)}
        </SelectContent></Select>
      {duplicateSensors && <p className="text-sm text-muted-foreground"><Trans>This file contains multiple entries for the same model; that does not establish whether they are the same physical strap.</Trans></p>}
      <p id="dfa-source-note" className="text-sm leading-relaxed text-muted-foreground"><Trans>Requires ECG chest-strap beat intervals. Confirm that the selected strap supplied them throughout this recording, without switching to another RR sensor or optical heart rate.</Trans></p>
      <details><summary className="min-h-11 cursor-pointer py-3 text-sm text-accent-cobalt"><Trans>Source details</Trans></summary>
        <p id="dfa-source-statement" className="text-sm leading-relaxed text-muted-foreground"><Trans>Throughout this recording, the selected ECG chest strap supplied the beat intervals; I did not switch to another RR sensor or optical heart rate.</Trans></p>
      </details>
      <Button className="min-h-11 h-auto whitespace-normal" aria-describedby="dfa-source-note dfa-source-statement" disabled={!selectedSensor || !chosen || busy || cooling || !mayAnalyse || !verified} onClick={() => void confirm()}>{(savedProof || proof?.sensor_ref === selectedSensor) ? t`Retry analysis` : t`Confirm this strap throughout and analyse`}</Button>
    </div>}
    {current && ['failed','unavailable','cancelled'].includes(current.status) && <div className="space-y-3"><p role="status">{current.status === 'cancelled' ? t`Analysis was cancelled.` : reason(current.error_code ?? '')}</p>
      {current.status !== 'unavailable' && <Button className="min-h-11" variant="outline" disabled={busy || cooling || !mayAnalyse || !verified} onClick={() => void runAction('retry')}><Trans>Retry analysis</Trans></Button>}</div>}
    {result?.status === 'complete' && result.summary && nav && <div data-dfa-result aria-busy={!verified} className="flex flex-col gap-6" style={!verified ? {opacity:0,pointerEvents:'none'} : undefined}
      onClickCapture={event => { if (!verified) { event.preventDefault(); event.stopPropagation(); } }}
      onKeyDownCapture={event => { if (!verified) event.preventDefault(); }}>
      <div className="space-y-2"><h3 className="text-lg font-semibold">{result.summary.valid_windows ? t`Usable windows are ready to inspect.` : t`No windows passed the analysis checks.`}</h3>
        <p className="text-sm">{result.source_assurance==='metadata_inferred'?t`Source inferred from recording metadata`:t`Source confirmed by you`} · <Trans>Estimated time alignment</Trans></p>
        {result.source_assurance==='metadata_inferred'&&<div><p className="text-sm text-muted-foreground"><Trans>The recording lists compatible ECG chest straps; its beat intervals are not directly linked to a sensor.</Trans></p>{result.candidates?.map(candidate=><p className="font-data text-sm" key={candidate.sensor_ref}>{candidate.label}{candidate.transport?` · ${candidate.transport}`:''}{result.candidates!.filter(c=>c.label===candidate.label&&c.transport===candidate.transport).length>1?` · ${t`Entry`} ${result.candidates!.filter(c=>c.label===candidate.label&&c.transport===candidate.transport).findIndex(c=>c.sensor_ref===candidate.sensor_ref)+1}`:''}</p>)}</div>}
        <dl aria-hidden={!verified || undefined} className="grid grid-cols-2 gap-x-5 gap-y-3 border-y py-4"><div><dt className="text-sm text-muted-foreground"><Trans>Valid windows</Trans></dt><dd className="font-data">{result.summary.valid_windows} / {result.summary.scheduled_windows}</dd></div>
          <div><dt className="text-sm text-muted-foreground"><Trans>Supported recording time</Trans></dt><dd className="font-data">{((result.summary.supported_time_ratio ?? 0)*100).toFixed(1)}%</dd></div></dl>
        <p className="text-sm text-muted-foreground"><Trans>Coverage describes which data could be analysed, not measurement accuracy.</Trans></p><p className="text-sm text-muted-foreground"><Trans>Supported time combines the time covered by valid windows, so it differs from the proportion of valid windows.</Trans></p>
      </div>
      <div><p className="mb-2 text-sm"><Trans>Whole activity coverage</Trans></p>
        <div className="relative flex h-11 w-full items-center rounded-sm focus-within:ring-2 focus-within:ring-ring">
          <svg viewBox={`0 0 ${nav.end_ms-start} 20`} preserveAspectRatio="none" className="pointer-events-none h-5 w-full" aria-hidden="true">
            <rect width={nav.end_ms-start} height="20" fill="var(--border)" />
            {nav.timer_blocks.map(([a,b]) => <rect key={a} x={a-start} width={b-a} height="20" fill="var(--muted-foreground)" />)}
            {nav.support.map(([a,b]) => <rect key={a} x={a-start} width={b-a} height="20" fill="var(--accent-cobalt-val)" />)}
            {result.windows?.length ? <rect x={result.windows[0].start_ms-start} y="1" width={result.windows[result.windows.length-1].end_ms-result.windows[0].start_ms} height="18" fill="none" stroke="var(--foreground)" strokeWidth="2" vectorEffect="non-scaling-stroke" /> : null}
            <line x1={cursor-start} x2={cursor-start} y1="0" y2="20" stroke="var(--foreground)" strokeWidth="3" vectorEffect="non-scaling-stroke" />
          </svg>
          <Input type="range" className="absolute inset-0 h-11 w-full cursor-pointer opacity-0" min={0} max={verified ? (nav.end_ms-start)/1000 : 100} step={1} value={verified ? (cursor-start)/1000 : 0}
            aria-label={t`Choose an activity time`} aria-describedby="dfa-time-help" aria-valuetext={verified ? `${elapsed(cursor,start)} · ${coverageLabel}` : t`Checking source status…`}
            onChange={event => setCursorTime(start+Number(event.target.value)*1000)}
            onKeyDown={event => {
              if (event.key === 'Enter') { event.preventDefault(); if (point) setFocusTime(point.time); return; }
              const keys: Record<string,number> = {ArrowLeft:-1,ArrowRight:1,ArrowDown:-1,ArrowUp:1,PageUp:-120,PageDown:120};
              if (event.key in keys || event.key==='Home' || event.key==='End') {
                event.preventDefault();
                const index=event.key==='Home'?0:event.key==='End'?windowCount(nav)-1:(point?.index??0)+(keys[event.key]??0);
                const selectedPoint=windowAtIndex(nav,index); if(selectedPoint) setCursorTime(selectedPoint.time);
              }
            }} />
        </div>
        <p id="dfa-time-help" className="mt-2 text-sm text-muted-foreground"><Trans>Use arrow keys for one window, Page Up or Down for a page, then Enter to jump.</Trans></p>
        <p className="mt-2 text-sm" role="status"><span aria-hidden={!verified || undefined}><span className="font-data">{elapsed(cursor,start)}</span> · {coverageLabel} · <Trans>Page</Trans> <span className="font-data">{targetPage}</span></span></p>
        <Button variant="outline" className="mt-2 min-h-11" disabled={!point} onClick={() => { if(point) setFocusTime(point.time); }}><Trans>Go to selected time</Trans></Button>
        <p className="mt-2 text-xs text-muted-foreground"><Trans>Cobalt: supported · dark: unsupported · pale: paused</Trans></p>
      </div>
      <Select value={comparator} onValueChange={v=>{if(!verified)return;setComparator(v??'hr_bpm');setSamplesRevision(null);}}><SelectTrigger aria-label={t`Compare with`} className="min-h-11"><SelectValue>{comparatorLabel}</SelectValue></SelectTrigger><SelectContent><SelectItem className="min-h-11" value="hr_bpm"><Trans>RR heart rate (bpm)</Trans></SelectItem><SelectItem className="min-h-11" value="power_watts"><Trans>Power (W)</Trans></SelectItem><SelectItem className="min-h-11" value="pace_sec_km"><Trans>Pace (s/km)</Trans></SelectItem></SelectContent></Select>
      {detailLoading&&<p role="status" className="text-sm text-muted-foreground"><Trans>Loading original windows…</Trans></p>}
      {detailError&&<p role="status"><Trans>Context changed or is unavailable. Refresh to reload it.</Trans></p>}
      {whole?.id===result.id&&whole.result_revision===result.result_revision?<DFAPlot run={whole} context={contextMatches?wholeContext:null} comparator={comparator} label={comparatorLabel} focusTime={focusTime} verified={verified} reason={reason}/>:<Skeleton className="h-64 w-full"/>}
      <p className="text-sm font-medium"><Trans>Affected windows (one window can have multiple reasons)</Trans></p>
      {Object.entries(result.summary.excluded_reasons).map(([code,count]) => <p className="text-sm text-muted-foreground" key={code}>{reason(code)} <span aria-hidden={!verified || undefined} className="font-data">{count}</span></p>)}
    </div>}
    {!result&&<Skeleton className="h-64 w-full"/>}
    <ScienceNote sources={[{url:'https://doi.org/10.3390/s21030821',label:t`Artefacts and recording devices`},{url:'https://doi.org/10.3390/s22176536',label:t`ECG chest-strap validation`}]}
      text={t`DFA α1 describes correlations in beat intervals. Each trailing 120-second window uses 4–16-beat scales, without interpolation or artifact correction. At least 200 complete beats and 98% interval coverage are required. Timing and quality cutoffs are Praxys guardrails, not validated physiological thresholds. Low heart rate may leave too few beats. These results do not diagnose fatigue or determine your training thresholds.`}/>
    {(runId || proof) && <div className="border-t pt-4"><div className="flex flex-wrap gap-2">
      {(proof || current?.source_confirmation_id) && <Button className="min-h-11" variant="outline" onClick={() => setDeleting('proof')}><Trans>Revoke source confirmation</Trans></Button>}
      {current?.source_assurance==='metadata_inferred'&&current.source_proof_id&&<Button className="min-h-11" variant="outline" onClick={()=>{
        const proofId=current.source_proof_id;const ticket=++epoch.current;validation.current=null;mutation.current?.abort();setVerified(false);retainedResult.current=null;setWhole(null);setWholeContext(null);
        void request(`/metadata-proofs/${proofId}`,undefined,'DELETE').then(()=>{if(ticket===epoch.current)void refresh();}).catch(()=>{if(ticket===epoch.current)setFailure(t`The request failed. Try again.`);});
      }}><Trans>Withdraw inferred source</Trans></Button>}
      <Button className="min-h-11" variant="outline" onClick={() => setDeleting('all')}><Trans>Delete DFA analysis</Trans></Button></div>
      {deleting && <div className="mt-4 space-y-3" role="group" aria-label={t`Confirm deletion`}><p>{deleting === 'proof' ? t`Revoke this source confirmation and remove its analysis results? The original recording will remain.` : t`Delete this activity’s DFA results and source confirmations? The original FIT will remain.`}</p>
        <Button className="min-h-11 mr-3" variant="destructive" disabled={busy} onClick={() => void remove()}><Trans>Confirm deletion</Trans></Button>
        <Button className="min-h-11" variant="outline" onClick={() => setDeleting(null)}><Trans>Keep data</Trans></Button></div>}
    </div>}
  </div>;
}
