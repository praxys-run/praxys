/** Field Lab extension: qualification first, then a gap-preserving window view. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Trans, useLingui } from '@lingui/react/macro';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DFACatalog, DFAContext, DFAInput, DFARun, DFASourceConfirmation } from '@/types/api';
import { apiFetch, extractErrorMessage, useApi } from '@/hooks/useApi';
import MetricDetailSheet from '@/components/MetricDetailSheet';
import ScienceNote from '@/components/ScienceNote';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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
    title="DFA α1" description={<>{t`Post-run analysis from ECG chest-strap beat intervals.`}{activityDate && <span className="mt-1 block font-data">{new Date(activityDate).toLocaleDateString(i18n.locale)}</span>}</>}>
    <DFAContent activityId={activityId} />
  </MetricDetailSheet>;
}

function DFAContent({ activityId }: { activityId: string }) {
  const { t } = useLingui();
  const base = `/api/activities/${encodeURIComponent(activityId)}/dfa-alpha1`;
  const client = useQueryClient();
  const [verified, setVerified] = useState(false);
  const [visible, setVisible] = useState(!document.hidden);
  const [selected, setSelected] = useState('');
  const [requestedRun, setRunId] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState('');
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [cursorTime, setCursorTime] = useState<number | null>(null);
  const [sensor, setSensor] = useState('');
  const [checked, setChecked] = useState(false);
  const [savedProof, setSavedProof] = useState<DFASourceConfirmation | null>(null);
  const [comparator, setComparator] = useState('hr_bpm');
  const [deleting, setDeleting] = useState<'all' | 'proof' | null>(null);
  const [samplesRevision, setSamplesRevision] = useState<string | null>(null);
  const epoch = useRef(0);
  const auto = useRef(true);
  const mutation = useRef<AbortController | null>(null);
  const catalog = useApi<DFACatalog>(base, { enabled: false, retry: () => false,
    refetchOnWindowFocus: false, timeoutMs: 30000 });
  const chosenSnapshot = selected || (catalog.data?.inputs.length === 1 ? catalog.data.inputs[0].input.snapshot_id : '');
  const runId = requestedRun || (catalog.data?.inputs.length === 1 ? catalog.data.latest_run?.id ?? '' : '');
  const run = useApi<DFARun>(`${base}/runs/${runId}?offset=${offset}&limit=120`, {
    enabled: verified && !catalog.error && visible && Boolean(runId) && Boolean(chosenSnapshot),
    refetchInterval: query => {
      const value = query.state.data as DFARun | undefined;
      if (!verified || !visible || catalog.error || query.state.error || !value || !['queued','running'].includes(value.status)) return false;
      const normal = Date.now()-Date.parse(value.created_at.endsWith('Z') ? value.created_at : value.created_at+'Z') < 60000 ? 3000 : 10000;
      return Math.max(normal, (value.retry_after_seconds ?? 0)*1000);
    },
    refetchOnWindowFocus: false, refetchOnMount: 'always', retry: () => false, timeoutMs: 30000,
  });
  const mayAnalyse = catalog.data?.policy_active === true && catalog.data?.processing_authorized === true;
  const current = mayAnalyse && !catalog.error && verified && run.data?.id === runId && run.data.snapshot_id === chosenSnapshot && run.data.freshness === 'current' ? run.data : null;
  const context = useApi<DFAContext>(`${base}/runs/${runId}/context?offset=${offset}&limit=120&result_revision=${current?.result_revision ?? ''}${samplesRevision ? `&expected_samples_revision=${samplesRevision}` : ''}`, {
    enabled: verified && visible && current?.status === 'complete' && comparator !== 'hr_bpm',
    refetchOnWindowFocus: false, retry: () => false, timeoutMs: 30000,
  });

  const loadCatalog = catalog.refreshData;
  const acceptCatalog = useCallback(async (fresh: DFACatalog | null, ticket: number) => {
    if (ticket !== epoch.current || document.hidden) return;
    setVerified(true);
    const initialEntry = auto.current; auto.current = false;
    if (!fresh) { setRunId(''); return; }
    if (initialEntry && !fresh.latest_run && fresh.inputs.length === 1 && fresh.policy_active && fresh.processing_authorized) {
      const input = fresh.inputs[0].input;
      const proof = fresh.source_confirmations.find(p => p.snapshot_id === input.snapshot_id && p.parse_id === input.parse_id);
      setBusy(true);
      try {
        const response = await apiFetch(base, {method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({input:{provider:input.provider,snapshot_id:input.snapshot_id,parse_id:input.parse_id},
            catalog_revision:fresh.catalog_revision,source_confirmation_id:proof?.id})});
        const wait = retryAfterSeconds(response.headers.get('Retry-After'));
        if (wait) setCooldownUntil(Date.now()+wait*1000);
        if (!response.ok) throw new Error('request_failed');
        const value = await response.json() as DFARun;
        if (ticket === epoch.current) { setRunId(value.id); setOffset(0); }
      } catch { if (ticket === epoch.current) setFailure('request_failed'); }
      finally { if (ticket === epoch.current) setBusy(false); }
    }
  }, [base]);
  const refresh = useCallback(async () => {
    const ticket = ++epoch.current;
    mutation.current?.abort();
    setVerified(false); setFailure(''); setBusy(false); setSavedProof(null); setChecked(false); setSensor('');
    await client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
    if (ticket !== epoch.current) return;
    client.removeQueries({ predicate: q => String(q.queryKey[0]).startsWith(`${base}/runs/`) });
    await acceptCatalog(await loadCatalog(), ticket);
  }, [base, client, loadCatalog, acceptCatalog]);

  useEffect(() => {
    const ticket = ++epoch.current;
    void loadCatalog().then(fresh => acceptCatalog(fresh, ticket));
    const focus = () => { setVisible(!document.hidden); setVerified(false); if (!document.hidden) void refresh(); else { ++epoch.current; setVerified(false); } };
    window.addEventListener('focus', focus);
    document.addEventListener('visibilitychange', focus);
    const invalidate = () => { epoch.current += 1; mutation.current?.abort(); };
    return () => { invalidate(); window.removeEventListener('focus', focus);
      document.removeEventListener('visibilitychange', focus);
      void client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
      client.removeQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
    };
  }, [refresh, client, base, loadCatalog, acceptCatalog]);

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
      const value = await request<DFARun>('', { input: { provider: input.provider, snapshot_id: input.snapshot_id, parse_id: input.parse_id },
        catalog_revision: catalog.data.catalog_revision, source_confirmation_id: proof });
      if (ticket !== epoch.current) return;
      setRunId(value.id); setOffset(0);
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
  const selectedSensor = sensor || (current?.sensors?.length === 1 ? current.sensors[0].sensor_ref : '');
  const proof = savedProof ?? catalog.data?.source_confirmations.find(p => p.snapshot_id === chosen?.snapshot_id && p.parse_id === chosen?.parse_id);
  const active = current && ['queued','running'].includes(current.status);
  const runAction = async (action: 'retry' | 'cancel') => {
    if (!current) return;
    setBusy(true);
    try { await request(`/runs/${current.id}/${action}`, action === 'retry' ? { expected_generation: current.generation } : undefined); await refresh(); }
    catch { setFailure(t`The request failed. Try again.`); } finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!current || !chosen || !checked || !selectedSensor) return;
    setBusy(true); setFailure('');
    const ticket = epoch.current;
    try {
      const p = savedProof ?? await request<DFASourceConfirmation>('/source-confirmations', { run_id: current.id, sensor_ref: selectedSensor,
        evidence_digest: current.evidence_digest, statement_version: current.statement_version, confirmed: true });
      if (ticket !== epoch.current) return;
      setSavedProof(p);
      const next = await request<DFARun>('', { input: { provider: chosen.provider, snapshot_id: chosen.snapshot_id, parse_id: chosen.parse_id },
        catalog_revision: catalog.data?.catalog_revision, source_confirmation_id: p.id });
      if (ticket === epoch.current) { setRunId(next.id); }
    } catch { if (ticket === epoch.current) setFailure(t`The request failed. Try again.`); }
    finally { if (ticket === epoch.current) setBusy(false); }
  };
  const remove = async () => {
    const id = proof?.id ?? current?.source_confirmation_id;
    if (deleting === 'proof' && !id) return;
    setBusy(true); auto.current = false;
    const ticket = ++epoch.current;
    await client.cancelQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
    mutation.current?.abort();
    try {
      await request(deleting === 'proof' ? `/source-confirmations/${id}` : '', undefined, 'DELETE');
      if (ticket !== epoch.current) return;
      client.removeQueries({ predicate: q => String(q.queryKey[0]).startsWith(base) });
      setRunId(''); setSavedProof(null); setChecked(false); setDeleting(null); await refresh();
    } catch { setFailure(t`The request failed. Try again.`); } finally { setBusy(false); }
  };

  if (!verified) return <div className="space-y-4" aria-busy="true"><Skeleton className="h-20 w-full" /><Skeleton className="h-64 w-full" /></div>;
  const data = catalog.data;
  const failureText = failure || catalog.error || run.error ? t`The request failed. Try again.` : '';
  const nav = current?.navigation;
  const start = nav?.start_ms ?? 0;
  const cursor = cursorTime ?? current?.windows?.[0]?.end_ms ?? start;
  const point = nav ? nearestWindow(nav,cursor) : null;
  const coverageState = nav ? timeSupport(nav,cursor) : 'unsupported';
  const coverageLabel = coverageState === 'supported' ? t`Supported` : coverageState === 'paused' ? t`Paused` : t`Unsupported`;
  const targetPage = point ? Math.floor(point.index/120)+1 : 0;
  const staleResult = run.data?.freshness === 'stale' && run.data.snapshot_id === chosenSnapshot;
  const contextMatches = context.data?.result_revision === current?.result_revision && context.data?.offset === offset;
  const chart = (current?.windows ?? []).flatMap((w,i,rows) => {
    const c = contextMatches ? context.data?.windows.find(v => v.index === w.index) : undefined;
    const value = { ...w, comparator: comparator === 'hr_bpm' ? w.hr_bpm : comparator === 'power_watts' ? c?.power_watts ?? null : c?.pace_sec_km ?? null };
    return i && rows[i-1].block !== w.block ? [{ ...value, end_ms: w.start_ms, alpha1: null, comparator: null }, value] : [value];
  });
  const comparatorLabel = comparator === 'hr_bpm' ? t`RR heart rate (bpm)` : comparator === 'power_watts' ? t`Power (W)` : t`Pace (s/km)`;

  return <div className="space-y-6 pb-3 dark:[&_.text-muted-foreground]:text-foreground">
    {failureText && <Alert variant="destructive"><AlertDescription>{failureText}<Button className="min-h-11" variant="outline" onClick={() => void refresh()}><Trans>Refresh</Trans></Button></AlertDescription></Alert>}
    {!data?.policy_active && <p role="status"><Trans>DFA analysis is awaiting scientific activation.</Trans></p>}
    {data?.availability === 'original_unavailable' && <p><Trans>The original recording is not available yet. Sync this activity from your connected platform.</Trans></p>}
    {data?.availability === 'provider_unsupported' && <p><Trans>DFA analysis is not yet available for this activity’s connected platform.</Trans></p>}
    {data?.availability === 'activity_type_unsupported' && <p>{reason('activity_type_unsupported')}</p>}
    {data && !data.processing_authorized && <p><Trans>Activity processing is unavailable. You can still delete this analysis.</Trans></p>}
    {cooling && <p role="status"><Trans>Please wait before trying again.</Trans></p>}
    {data && data.inputs.length > 1 && <div className="space-y-2"><Label htmlFor="dfa-recording"><Trans>Recording version</Trans></Label>
      <Select value={selected || null} onValueChange={v => { setSelected(v ?? ''); setSavedProof(null); setChecked(false); setSensor(''); setOffset(0); setRunId(data.latest_run?.snapshot_id === v ? data.latest_run.id : ''); }}>
        <SelectTrigger id="dfa-recording" aria-label={t`Recording version`} className="min-h-11 w-full"><SelectValue>{data.inputs.find(v => v.input.snapshot_id === selected)?.created_at.replace('T',' ').slice(0,19) ?? t`Choose a recording`}</SelectValue></SelectTrigger><SelectContent>
          {data.inputs.map((v,i) => <SelectItem key={v.input.snapshot_id} value={v.input.snapshot_id}><span className="font-data">{i+1} · {new Date(v.created_at+'Z').toLocaleString()}</span></SelectItem>)}
        </SelectContent></Select></div>}
    {chosen && !catalog.error && !active && (!current || staleResult) &&
      <Button className="min-h-11" disabled={busy || cooling || !mayAnalyse} onClick={() => void launch(chosen, proof?.id)}>{staleResult ? t`Recalculate analysis` : t`Analyse recording`}</Button>}
    {run.data?.freshness === 'stale' && <p><Trans>The recording or method has changed. Recalculate to see current results.</Trans></p>}
    {active && <div role="status" className="space-y-3"><p>{current.status === 'queued' ? t`Waiting to analyse this recording…` : current.phase === 'prepare' ? t`Checking beat intervals and chest-strap evidence…` : t`Calculating valid windows…`}</p>
      <p className="text-sm text-muted-foreground"><Trans>You can close this panel. Analysis will continue.</Trans></p>
      <Button className="min-h-11" variant="outline" disabled={busy} onClick={() => void runAction('cancel')}><Trans>Cancel analysis</Trans></Button></div>}
    {current?.status === 'awaiting_source_confirmation' && <div className="space-y-4">
      <h3 className="font-semibold"><Trans>Confirm the source for this activity</Trans></h3>
      <p className="text-sm text-muted-foreground"><Trans>The file records a compatible chest strap, but does not directly identify the source of its beat intervals.</Trans></p>
      <Select value={selectedSensor || null} onValueChange={v => { setSensor(v ?? ''); setChecked(false); setSavedProof(null); }}>
        <SelectTrigger aria-label={t`Choose the chest strap`} className="min-h-11 w-full"><SelectValue>{current.sensors?.find(s => s.sensor_ref === selectedSensor)?.label ?? t`Choose the chest strap`}</SelectValue></SelectTrigger><SelectContent>
          {current.sensors?.map(s => <SelectItem key={s.sensor_ref} value={s.sensor_ref}>{s.label}</SelectItem>)}
        </SelectContent></Select>
      <Label className="flex min-h-11 items-start gap-3 leading-relaxed" htmlFor="dfa-source-confirm">
        <Checkbox id="dfa-source-confirm" checked={checked} onCheckedChange={setChecked} className="mt-1 shrink-0" />
        <Trans>Throughout this recording, the selected ECG chest strap supplied the beat intervals; I did not switch to another RR sensor or optical heart rate.</Trans>
      </Label>
      <Button className="min-h-11" disabled={!checked || !selectedSensor || !chosen || busy || cooling || !mayAnalyse} onClick={() => void confirm()}>{savedProof ? t`Retry analysis` : t`Confirm and analyse`}</Button>
    </div>}
    {current && ['failed','unavailable','cancelled'].includes(current.status) && <div className="space-y-3"><p role="status">{current.status === 'cancelled' ? t`Analysis was cancelled.` : reason(current.error_code ?? '')}</p>
      {current.status !== 'unavailable' && <Button className="min-h-11" variant="outline" disabled={busy || cooling || !mayAnalyse} onClick={() => void runAction('retry')}><Trans>Retry analysis</Trans></Button>}</div>}
    {current?.status === 'complete' && current.summary && nav && <>
      <div className="space-y-2"><h3 className="text-lg font-semibold">{current.summary.valid_windows ? t`Usable windows are ready to inspect.` : t`No windows passed the analysis checks.`}</h3>
        <p className="text-sm"><Trans>Source confirmed by you</Trans> · <Trans>Estimated time alignment</Trans></p>
        <dl className="grid grid-cols-2 gap-x-5 gap-y-3 border-y py-4"><div><dt className="text-sm text-muted-foreground"><Trans>Valid windows</Trans></dt><dd className="font-data">{current.summary.valid_windows} / {current.summary.scheduled_windows}</dd></div>
          <div><dt className="text-sm text-muted-foreground"><Trans>Supported recording time</Trans></dt><dd className="font-data">{((current.summary.supported_time_ratio ?? 0)*100).toFixed(1)}%</dd></div></dl>
        <p className="text-sm text-muted-foreground"><Trans>Coverage describes which data could be analysed, not measurement accuracy.</Trans></p>
      </div>
      <div><p className="mb-2 text-sm"><Trans>Whole activity coverage</Trans></p>
        <div className="relative flex h-11 w-full items-center rounded-sm focus-within:ring-2 focus-within:ring-ring">
          <svg viewBox={`0 0 ${nav.end_ms-start} 20`} preserveAspectRatio="none" className="pointer-events-none h-5 w-full" aria-hidden="true">
            <rect width={nav.end_ms-start} height="20" fill="var(--border)" />
            {nav.timer_blocks.map(([a,b]) => <rect key={a} x={a-start} width={b-a} height="20" fill="var(--muted-foreground)" />)}
            {nav.support.map(([a,b]) => <rect key={a} x={a-start} width={b-a} height="20" fill="var(--accent-cobalt-val)" />)}
            {current.windows?.length ? <rect x={current.windows[0].start_ms-start} y="1" width={current.windows[current.windows.length-1].end_ms-current.windows[0].start_ms} height="18" fill="none" stroke="var(--foreground)" strokeWidth="2" vectorEffect="non-scaling-stroke" /> : null}
            <line x1={cursor-start} x2={cursor-start} y1="0" y2="20" stroke="var(--foreground)" strokeWidth="3" vectorEffect="non-scaling-stroke" />
          </svg>
          <Input type="range" className="absolute inset-0 h-11 w-full cursor-pointer opacity-0" min={0} max={(nav.end_ms-start)/1000} step={1} value={(cursor-start)/1000}
            aria-label={t`Choose an activity time`} aria-describedby="dfa-time-help" aria-valuetext={`${elapsed(cursor,start)} · ${coverageLabel}`}
            onChange={event => setCursorTime(start+Number(event.target.value)*1000)}
            onKeyDown={event => {
              if (event.key === 'Enter') { event.preventDefault(); if (point) setOffset(Math.floor(point.index/120)*120); return; }
              const keys: Record<string,number> = {ArrowLeft:-1,ArrowRight:1,ArrowDown:-1,ArrowUp:1,PageUp:-120,PageDown:120};
              if (event.key in keys || event.key==='Home' || event.key==='End') {
                event.preventDefault();
                const index=event.key==='Home'?0:event.key==='End'?windowCount(nav)-1:(point?.index??0)+(keys[event.key]??0);
                const selectedPoint=windowAtIndex(nav,index); if(selectedPoint) setCursorTime(selectedPoint.time);
              }
            }} />
        </div>
        <p id="dfa-time-help" className="mt-2 text-sm text-muted-foreground"><Trans>Use arrow keys for one window, Page Up or Down for a page, then Enter to jump.</Trans></p>
        <p className="mt-2 text-sm" role="status"><span className="font-data">{elapsed(cursor,start)}</span> · {coverageLabel} · <Trans>Page</Trans> <span className="font-data">{targetPage}</span></p>
        <Button variant="outline" className="mt-2 min-h-11" disabled={!point} onClick={() => { if(point) setOffset(Math.floor(point.index/120)*120); }}><Trans>Go to selected time</Trans></Button>
        <p className="mt-2 text-xs text-muted-foreground"><Trans>Cobalt: supported · dark: unsupported · pale: paused</Trans></p>
      </div>
      <div className="flex flex-wrap gap-3"><Select value={String(offset)} onValueChange={v => { setOffset(Number(v)); setSamplesRevision(null); }}>
        <SelectTrigger aria-label={t`Jump to time`} className="min-h-11"><SelectValue>{elapsed(nav.page_anchors.find(p => p.offset === offset)?.time_ms ?? start,start)}</SelectValue></SelectTrigger><SelectContent>
          {nav.page_anchors.map(p => <SelectItem key={p.offset} value={String(p.offset)}><span className="font-data">{elapsed(p.time_ms,start)}</span></SelectItem>)}
        </SelectContent></Select><Select value={comparator} onValueChange={v => { setComparator(v ?? 'hr_bpm'); setSamplesRevision(null); }}>
        <SelectTrigger aria-label={t`Compare with`} className="min-h-11"><SelectValue>{comparatorLabel}</SelectValue></SelectTrigger><SelectContent>
          <SelectItem value="hr_bpm"><Trans>RR heart rate (bpm)</Trans></SelectItem><SelectItem value="power_watts"><Trans>Power (W)</Trans></SelectItem><SelectItem value="pace_sec_km"><Trans>Pace (s/km)</Trans></SelectItem>
        </SelectContent></Select></div>
      {context.error && comparator !== 'hr_bpm' && <p role="status"><Trans>Context changed or is unavailable. Refresh to reload it.</Trans></p>}
      <div className="flex flex-wrap gap-5 text-sm" aria-hidden="true"><span className="text-accent-cobalt">DFA α1</span><span className="text-muted-foreground">{comparatorLabel}</span></div>
      <div className="h-64 w-full font-data" aria-label={t`DFA α1 by window end time`}>
        <ResponsiveContainer width="100%" height="100%"><LineChart data={chart} margin={{left:0,right:0,top:10,bottom:10}}>
          <CartesianGrid stroke="var(--border)" vertical={false}/><XAxis dataKey="end_ms" type="number" domain={['dataMin','dataMax']} tickFormatter={v => elapsed(Number(v),start)} tick={{fontSize:11,fill:'var(--foreground)'}}/>
          <YAxis yAxisId="alpha" tickFormatter={v => Number(v).toFixed(2)} width={44} domain={['auto','auto']} tick={{fontSize:11,fill:'var(--foreground)'}}/>
          <YAxis yAxisId="context" orientation="right" width={45} domain={['auto','auto']} tick={{fontSize:11,fill:'var(--foreground)'}}/>
          <Tooltip labelFormatter={v => elapsed(Number(v),start)} formatter={v => typeof v === 'number' ? v.toFixed(2) : '—'} contentStyle={{background:'var(--card)',borderColor:'var(--border)'}}/>
          <Line yAxisId="alpha" dataKey="alpha1" name="DFA α1" type="linear" stroke="var(--accent-cobalt-val)" dot={false} connectNulls={false} isAnimationActive={false}/>
          <Line yAxisId="context" dataKey="comparator" name={comparatorLabel} type="linear" stroke="var(--foreground)" dot={false} connectNulls={false} isAnimationActive={false}/>
        </LineChart></ResponsiveContainer>
      </div>
      <div className="flex items-center justify-between gap-3"><Button className="min-h-11" variant="outline" disabled={offset===0} onClick={() => setOffset(Math.max(0,offset-120))}><Trans>Previous</Trans></Button>
        <span className="font-data text-sm">{Math.floor(offset/120)+1} / {Math.max(1,nav.page_anchors.length)}</span>
        <Button className="min-h-11" variant="outline" disabled={current.page?.next_offset == null} onClick={() => setOffset(current.page?.next_offset ?? offset)}><Trans>Next</Trans></Button></div>
      <details><summary className="min-h-11 cursor-pointer py-3 font-medium"><Trans>Window values and quality details</Trans></summary>
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only"><Trans>Each row represents a 120-second window.</Trans></caption>
          <thead><tr className="border-b"><th className="py-2"><Trans>Time</Trans></th><th>DFA α1</th><th>{comparatorLabel}</th><th><Trans>Quality</Trans></th></tr></thead>
          <tbody>{(current.windows ?? []).map(w => <tr key={w.index} className="border-b align-top"><td className="py-3 pr-2 font-data">{elapsed(w.start_ms,start)}–{elapsed(w.end_ms,start)}</td>
            <td className="py-3 pr-2 font-data">{w.alpha1?.toFixed(2) ?? '—'}</td><td className="py-3 pr-2 font-data">{chart.find(v => v.index===w.index && v.alpha1===w.alpha1)?.comparator?.toFixed(1) ?? '—'}</td>
            <td className="py-3"><p>{[...w.reasons,...w.flags].map(reason).join(' ') || t`No issues detected by these checks.`}</p><span className="font-data text-xs">{w.beat_count} · {(w.coverage_ms/1200).toFixed(1)}%</span></td></tr>)}</tbody></table></div>
      </details>
      {Object.entries(current.summary.excluded_reasons).map(([code,count]) => <p className="text-sm text-muted-foreground" key={code}>{reason(code)} <span className="font-data">{count}</span></p>)}
    </>}
    <ScienceNote sources={[{url:'https://doi.org/10.3390/s21030821',label:t`Artefacts and recording devices`},{url:'https://doi.org/10.3390/s22176536',label:t`ECG chest-strap validation`}]}
      text={t`DFA α1 describes correlations in beat intervals. Each trailing 120-second window uses 4–16-beat scales, without interpolation or artifact correction. At least 200 complete beats and 98% interval coverage are required. Timing and quality cutoffs are Praxys guardrails, not validated physiological thresholds. Low heart rate may leave too few beats. These results do not diagnose fatigue or determine your training thresholds.`}/>
    {(runId || proof) && <div className="border-t pt-4"><div className="flex flex-wrap gap-2">
      {(proof || current?.source_confirmation_id) && <Button className="min-h-11" variant="outline" onClick={() => setDeleting('proof')}><Trans>Revoke source confirmation</Trans></Button>}
      <Button className="min-h-11" variant="outline" onClick={() => setDeleting('all')}><Trans>Delete DFA analysis</Trans></Button></div>
      {deleting && <div className="mt-4 space-y-3" role="group" aria-label={t`Confirm deletion`}><p>{deleting === 'proof' ? t`Revoke this source confirmation and remove its analysis results? The original recording will remain.` : t`Delete this activity’s DFA results and source confirmations? The original FIT will remain.`}</p>
        <Button className="min-h-11 mr-3" variant="destructive" disabled={busy} onClick={() => void remove()}><Trans>Confirm deletion</Trans></Button>
        <Button className="min-h-11" variant="outline" onClick={() => setDeleting(null)}><Trans>Keep data</Trans></Button></div>}
    </div>}
  </div>;
}
