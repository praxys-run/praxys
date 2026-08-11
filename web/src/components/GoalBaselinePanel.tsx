import { useMemo, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import ScienceNote from '@/components/ScienceNote';
import { useLocale } from '@/contexts/LocaleContext';
import { apiFetch, extractErrorMessage } from '@/hooks/useApi';
import { formatTime } from '@/lib/format';
import type {
  GoalBaselineCandidate,
  GoalBaselineMutationResponse,
  GoalBaselineResponse,
} from '@/types/api';

interface GoalBaselinePanelProps {
  baseline: GoalBaselineResponse;
  goal: { distance?: string | null; target_time_sec?: number | null; eligible?: boolean } | undefined;
  isDemo: boolean;
  onChanged: () => void;
}

type ConfirmResponse = 'race' | 'intentional_all_out' | 'not_all_out' | 'unset';
type DialogMode = 'confirm' | 'offer' | 'schedule' | 'complete' | 'stop' | null;

const SAFETY_REASONS = [
  'acute_illness',
  'injury_or_pain_altering_running',
  'chest_pain_or_pressure',
  'fainting_or_near_fainting',
  'unusual_severe_breathlessness',
  'confusion_or_loss_of_coordination',
  'other_red_flag_symptom',
  'known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing',
  'self_reported_inadequate_recovery_or_unresolved_substantial_fatigue',
  'unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course',
] as const;

function formatDate(value: string, locale: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function buildCopy(locale: string) {
  const zh = locale === 'zh';
  return {
    sectionLabel: zh ? '5 公里基线试点' : '5K baseline pilot',
    status: {
      current: zh ? '当前' : 'Current',
      stale: zh ? '已过期' : 'Stale',
      incomparable: zh ? '待确认' : 'Needs review',
      missing: zh ? '缺少证据' : 'Missing evidence',
      not_required: zh ? '当前目标不需要' : 'Not required',
      pending_test: zh ? '测试待完成' : 'Test pending',
    },
    headline: {
      current: zh ? '先看历史：你已经有可用的 5 公里当前能力证据。' : 'History first: you already have usable current 5K evidence.',
      stale: zh ? '你有更早的 5 公里证据。Praxys 会保留它，并可选择新的试点测试。' : 'You have older 5K evidence. Praxys keeps it visible and can optionally offer a new pilot test.',
      incomparable: zh ? 'Praxys 找到了候选 5 公里活动，但它们还没有被合格确认。' : 'Praxys found candidate 5K efforts, but they are not qualified yet.',
      missing: zh ? 'Praxys 还没有找到合格的 5 公里历史证据。' : 'Praxys has not found qualified 5K history yet.',
      not_required: zh ? '当前目标不在这个 5 公里基线试点范围内。' : 'The current goal is outside this 5K baseline pilot.',
      pending_test: zh ? '可选 5 公里试点测试已进入待办。' : 'The optional 5K pilot test is in progress.',
    },
    readiness: {
      sufficient_baseline: zh ? '当前基线足够。' : 'Baseline evidence is currently sufficient.',
      insufficient_evidence: zh ? '这不是失败；它只是说明证据还不够。' : 'This is not failure; it means the evidence is still insufficient.',
      non_diagnostic_safety_stop: zh ? '已触发非诊断安全停止；Praxys 不会给出诊断、治疗或复出建议。' : 'A non-diagnostic safety stop is active; Praxys does not diagnose, treat, or clear return to running.',
    },
    target: zh ? '目标' : 'Goal',
    evidence: zh ? '当前证据' : 'Current evidence',
    age: zh ? '证据年龄' : 'Evidence age',
    candidateTitle: zh ? '历史候选活动' : 'History candidates',
    candidateHint: zh ? '候选检索永远不等于资格认定；只有完整活动、明确确认的测距与计时才可能成为基线。' : 'Retrieval is never qualification; only a full activity with explicit distance, timing, and purpose confirmation can become a baseline.',
    reviewCandidate: zh ? '确认这次活动' : 'Review this effort',
    changeCandidate: zh ? '更改确认' : 'Change confirmation',
    fullActivityOnly: zh ? '仅完整活动' : 'Full activity only',
    segmentRule: zh ? '任意 5 公里片段、最佳分段、轻松跑或长跑中的快速段都不会成为基线。' : 'Arbitrary 5K segments, best splits, or fast sections inside easy, long, or mixed runs never count as baseline evidence.',
    noMeaningfulChange: zh ? '目前还没有可用的“有意义变化”阈值。' : 'There is no meaningful-change threshold yet.',
    pilotGuardrail: zh ? '42 天规则是 Praxys 试点护栏，不是生理学定论。' : 'The 42-day rule is a Praxys pilot guardrail, not a physiological cutoff.',
    testTitle: zh ? '可选 5 公里试点测试' : 'Optional 5K pilot test',
    testHint: zh ? '这是一次最大努力测试，而且始终保留“不测试也可以”的路径。' : 'This is a maximal-effort test, and the no-test path always stays available.',
    reviewOptionalTest: zh ? '查看可选测试' : 'Review optional test',
    scheduleOptionalTest: zh ? '安排可选测试' : 'Schedule optional test',
    completeOptionalTest: zh ? '记录测试结果' : 'Record test result',
    stopOptionalTest: zh ? '停止这次测试' : 'Stop this test',
    declineOptionalTest: zh ? '先不做测试' : 'Stay on the no-test path',
    pendingDate: zh ? '已安排日期' : 'Scheduled date',
    dialog: {
      confirmTitle: zh ? '确认这次活动' : 'Review this activity',
      confirmDescription: zh ? '只有明确确认的测距、计时和用途才可能把历史活动变成 5 公里基线。' : 'Only explicit confirmation of distance, timing, and purpose can turn history into a 5K baseline.',
      effortLabel: zh ? '这次完整活动是什么？' : 'What was this full activity?',
      measuredLabel: zh ? '是否是测量好的完整 5 公里？' : 'Was the full effort a measured 5K?',
      timingLabel: zh ? '记录时间是否反映了无未解决暂停的耗时？' : 'Did the recorded time reflect elapsed timing with no unresolved pauses?',
      offerTitle: zh ? '查看可选测试' : 'Review the optional test',
      offerDescription: zh ? '只在历史证据缺失、过期或待确认时提供。它是一次最大努力的户外 5 公里试点。' : 'This appears only when history is missing, stale, or still needs review. It is a maximal-effort outdoor 5K pilot.',
      scheduleTitle: zh ? '安排可选测试' : 'Schedule the optional test',
      scheduleDescription: zh ? '安排会通过 Praxys 的规范训练/修订/投递通道写入计划，不会静默修改。' : 'Scheduling writes through the canonical workout, revision, and delivery lane. Nothing changes silently.',
      completeTitle: zh ? '记录测试结果' : 'Record the test result',
      completeDescription: zh ? '同步活动永远不会自动变成已完成测试；你需要再次确认协议、测距和计时。' : 'A synced activity never becomes a completed test automatically; you must confirm the protocol, distance, and timing again.',
      stopTitle: zh ? '停止这次测试' : 'Stop this test',
      stopDescription: zh ? '停止或放弃会保留账户和“不测试”路径。' : 'Stopping or declining preserves your account and the no-test path.',
      save: zh ? '保存' : 'Save',
      cancel: zh ? '取消' : 'Cancel',
    },
    choose: zh ? '请选择' : 'Choose one',
    options: {
      race: zh ? '测量好的 5 公里比赛' : 'Measured 5K race',
      intentional_all_out: zh ? '明确的 5 公里全力完成' : 'Intentional all-out complete 5K',
      not_all_out: zh ? '不是全力 5 公里' : 'Not an all-out 5K effort',
      yes: zh ? '是' : 'Yes',
      no: zh ? '否' : 'No',
    },
    stopReasons: {
      acute_illness: zh ? '急性疾病' : 'Acute illness',
      injury_or_pain_altering_running: zh ? '疼痛或伤病改变了跑步方式' : 'Pain or injury altered the run',
      chest_pain_or_pressure: zh ? '胸痛或压迫感' : 'Chest pain or pressure',
      fainting_or_near_fainting: zh ? '晕厥或接近晕厥' : 'Fainting or near-fainting',
      unusual_severe_breathlessness: zh ? '异常严重气短' : 'Unusually severe breathlessness',
      confusion_or_loss_of_coordination: zh ? '意识混乱或失去协调' : 'Confusion or loss of coordination',
      other_red_flag_symptom: zh ? '其他红旗症状' : 'Another red-flag symptom',
      known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing: zh ? '已有医疗限制或临床建议不要做高强度测试' : 'A clinician or restriction already rules out vigorous testing',
      self_reported_inadequate_recovery_or_unresolved_substantial_fatigue: zh ? '恢复不足或显著疲劳未解决' : 'Recovery was inadequate or fatigue stayed unresolved',
      unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course: zh ? '天气、空气、交通、能见度或路面不安全' : 'Weather, air, traffic, visibility, or footing was unsafe',
    },
    mutationSuccess: zh ? '已更新 5 公里基线。' : 'Updated the 5K baseline.',
  };
}

export default function GoalBaselinePanel({ baseline, goal, isDemo, onChanged }: GoalBaselinePanelProps) {
  const { locale } = useLocale();
  const copy = useMemo(() => buildCopy(locale), [locale]);
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [activeCandidate, setActiveCandidate] = useState<GoalBaselineCandidate | null>(null);
  const [response, setResponse] = useState<ConfirmResponse>('unset');
  const [measured, setMeasured] = useState<'yes' | 'no' | 'unset'>('unset');
  const [timing, setTiming] = useState<'yes' | 'no' | 'unset'>('unset');
  const [scheduleDate, setScheduleDate] = useState('');
  const [selectedActivityId, setSelectedActivityId] = useState('');
  const [protocolFollowed, setProtocolFollowed] = useState<'yes' | 'no' | 'unset'>('unset');
  const [stopReason, setStopReason] = useState<(typeof SAFETY_REASONS)[number] | 'unset'>('unset');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openCandidateDialog = (candidate: GoalBaselineCandidate) => {
    setActiveCandidate(candidate);
    setResponse((candidate.confirmation_response ?? 'unset') as ConfirmResponse);
    setMeasured(candidate.measured_5k_confirmed == null ? 'unset' : candidate.measured_5k_confirmed ? 'yes' : 'no');
    setTiming(candidate.elapsed_timing_confirmed == null ? 'unset' : candidate.elapsed_timing_confirmed ? 'yes' : 'no');
    setDialogMode('confirm');
    setError(null);
  };

  const mutate = async (url: string, body: Record<string, unknown>) => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, 'Request failed'));
      }
      const _payload = await res.json() as GoalBaselineMutationResponse;
      setNotice(copy.mutationSuccess);
      setDialogMode(null);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (!activeCandidate) return;
    if (response === 'unset' || measured === 'unset' || timing === 'unset') {
      setError(copy.choose);
      return;
    }
    await mutate('/api/goal/baseline/history/confirm', {
      activity_id: activeCandidate.activity_id,
      response,
      measured_5k: measured === 'yes',
      elapsed_timing_confirmed: timing === 'yes',
    });
  };

  const handleOffer = async () => {
    await mutate('/api/goal/baseline/test', { action: 'offer' });
  };

  const handleSchedule = async () => {
    await mutate('/api/goal/baseline/test', { action: 'schedule', scheduled_date: scheduleDate });
  };

  const handleComplete = async () => {
    if (!selectedActivityId || measured === 'unset' || timing === 'unset' || protocolFollowed === 'unset') {
      setError(copy.choose);
      return;
    }
    await mutate('/api/goal/baseline/test', {
      action: 'complete',
      activity_id: selectedActivityId,
      measured_5k: measured === 'yes',
      elapsed_timing_confirmed: timing === 'yes',
      protocol_followed: protocolFollowed === 'yes',
    });
  };

  const handleStop = async () => {
    if (stopReason === 'unset') {
      setError(copy.choose);
      return;
    }
    await mutate('/api/goal/baseline/test', { action: 'stop', reason_code: stopReason });
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.sectionLabel}</p>
              <CardTitle className="mt-2 text-2xl leading-tight">{copy.headline[baseline.status]}</CardTitle>
              <CardDescription className="mt-2">{copy.readiness[baseline.readiness]}</CardDescription>
            </div>
            <Badge variant="outline" className="uppercase tracking-wider">{copy.status[baseline.status]}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.target}</p>
              <p className="mt-1 text-sm text-foreground">{goal?.distance?.toUpperCase() ?? '5K'} {goal?.target_time_sec ? <span className="font-data">· {formatTime(goal.target_time_sec)}</span> : null}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.evidence}</p>
              <p className="mt-1 text-sm text-foreground">{baseline.evidence ? `${copy.status.current} · ${baseline.evidence.provenance.replace(/_/g, ' ')}` : '—'}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.age}</p>
              <p className="mt-1 text-sm text-foreground font-data">{baseline.evidence ? `${baseline.evidence.age_days} d` : '—'}</p>
            </div>
          </div>
          {baseline.evidence && (
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-foreground">
                <span className="font-medium">{formatDate(baseline.evidence.observed_date, locale)}</span>
                <span className="font-data"> · {baseline.evidence.distance_km?.toFixed(2)} km · {baseline.evidence.elapsed_time_sec ? formatTime(Math.round(baseline.evidence.elapsed_time_sec)) : '—'}</span>
              </p>
              <p className="mt-2 text-sm text-muted-foreground">{copy.pilotGuardrail} {copy.noMeaningfulChange}</p>
            </div>
          )}
          <Alert>
            <AlertTitle>{copy.fullActivityOnly}</AlertTitle>
            <AlertDescription>{copy.segmentRule}</AlertDescription>
          </Alert>
          {notice && <p className="text-sm text-primary">{notice}</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <ScienceNote
            text={baseline.science_note.description}
            sources={baseline.science_note.citations}
          />
          {baseline.alternatives.length > 0 && (
            <p className="text-sm text-muted-foreground">{baseline.alternatives.join(' · ')}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.candidateTitle}</CardTitle>
          <CardDescription>{copy.candidateHint}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {baseline.candidates.length === 0 ? (
            <p className="text-sm text-muted-foreground">—</p>
          ) : baseline.candidates.map((candidate) => (
            <div key={candidate.activity_id} className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground font-data">{formatDate(candidate.observed_date, locale)} · {candidate.distance_km?.toFixed(2)} km · {candidate.duration_sec ? formatTime(Math.round(candidate.duration_sec)) : '—'}</p>
                <p className="text-sm text-muted-foreground">{copy.status.incomparable} · {candidate.review_state.replace(/_/g, ' ')}</p>
              </div>
              <Button variant="outline" onClick={() => openCandidateDialog(candidate)} disabled={isDemo || saving}>
                {candidate.confirmation_response ? copy.changeCandidate : copy.reviewCandidate}
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.testTitle}</CardTitle>
          <CardDescription>{copy.testHint}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">{copy.pilotGuardrail}</p>
          <p className="text-sm text-muted-foreground">{baseline.pilot_scope_note}</p>
          {baseline.test.scheduled_workout && (
            <p className="text-sm text-foreground"><span className="font-medium">{copy.pendingDate}</span> <span className="font-data">{baseline.test.scheduled_workout.date}</span></p>
          )}
          <div className="flex flex-wrap gap-2">
            {baseline.test.state === 'not_offered' && baseline.test.can_schedule && (
              <Button onClick={() => setDialogMode('offer')} disabled={isDemo || saving}>{copy.reviewOptionalTest}</Button>
            )}
            {baseline.test.can_schedule && baseline.test.state !== 'not_offered' && baseline.test.state !== 'scheduled' && (
              <Button onClick={() => setDialogMode('schedule')} disabled={isDemo || saving}>{copy.scheduleOptionalTest}</Button>
            )}
            {(baseline.test.state === 'offered' || baseline.test.state === 'scheduled') && (
              <>
                <Button variant="outline" onClick={() => mutate('/api/goal/baseline/test', { action: 'decline' })} disabled={isDemo || saving}>{copy.declineOptionalTest}</Button>
                <Button variant="outline" onClick={() => { setSelectedActivityId(''); setMeasured('unset'); setTiming('unset'); setProtocolFollowed('unset'); setDialogMode('complete'); }} disabled={isDemo || saving || baseline.candidates.length === 0}>{copy.completeOptionalTest}</Button>
                <Button variant="outline" onClick={() => { setStopReason('unset'); setDialogMode('stop'); }} disabled={isDemo || saving}>{copy.stopOptionalTest}</Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogMode === 'confirm'} onOpenChange={(open) => !open && setDialogMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.confirmTitle}</DialogTitle>
            <DialogDescription>{copy.dialog.confirmDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{copy.dialog.effortLabel}</Label>
              <Select value={response} onValueChange={(value) => setResponse(value as ConfirmResponse)}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">{copy.choose}</SelectItem>
                  <SelectItem value="race">{copy.options.race}</SelectItem>
                  <SelectItem value="intentional_all_out">{copy.options.intentional_all_out}</SelectItem>
                  <SelectItem value="not_all_out">{copy.options.not_all_out}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{copy.dialog.measuredLabel}</Label>
              <Select value={measured} onValueChange={(value) => setMeasured(value as 'yes' | 'no' | 'unset')}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">{copy.choose}</SelectItem>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{copy.dialog.timingLabel}</Label>
              <Select value={timing} onValueChange={(value) => setTiming(value as 'yes' | 'no' | 'unset')}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">{copy.choose}</SelectItem>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogMode(null)}>{copy.dialog.cancel}</Button>
            <Button onClick={handleConfirm} disabled={saving}>{copy.dialog.save}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogMode === 'offer'} onOpenChange={(open) => !open && setDialogMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.offerTitle}</DialogTitle>
            <DialogDescription>{copy.dialog.offerDescription}</DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{copy.testHint}</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogMode(null)}>{copy.dialog.cancel}</Button>
            <Button variant="outline" onClick={() => mutate('/api/goal/baseline/test', { action: 'decline' })} disabled={saving}>{copy.declineOptionalTest}</Button>
            <Button onClick={handleOffer} disabled={saving}>{copy.reviewOptionalTest}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogMode === 'schedule'} onOpenChange={(open) => !open && setDialogMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.scheduleTitle}</DialogTitle>
            <DialogDescription>{copy.dialog.scheduleDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="goal-baseline-date">{copy.pendingDate}</Label>
            <Input id="goal-baseline-date" type="date" value={scheduleDate} onChange={(event) => setScheduleDate(event.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogMode(null)}>{copy.dialog.cancel}</Button>
            <Button onClick={handleSchedule} disabled={saving || !scheduleDate}>{copy.scheduleOptionalTest}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogMode === 'complete'} onOpenChange={(open) => !open && setDialogMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.completeTitle}</DialogTitle>
            <DialogDescription>{copy.dialog.completeDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{copy.candidateTitle}</Label>
              <Select value={selectedActivityId} onValueChange={setSelectedActivityId}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  {baseline.candidates.map((candidate) => (
                    <SelectItem key={candidate.activity_id} value={candidate.activity_id}>{formatDate(candidate.observed_date, locale)} · {candidate.distance_km?.toFixed(2)} km</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{copy.dialog.measuredLabel}</Label>
              <Select value={measured} onValueChange={(value) => setMeasured(value as 'yes' | 'no' | 'unset')}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">{copy.choose}</SelectItem>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{copy.dialog.timingLabel}</Label>
              <Select value={timing} onValueChange={(value) => setTiming(value as 'yes' | 'no' | 'unset')}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">{copy.choose}</SelectItem>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{copy.testHint}</Label>
              <Select value={protocolFollowed} onValueChange={(value) => setProtocolFollowed(value as 'yes' | 'no' | 'unset')}>
                <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unset">{copy.choose}</SelectItem>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogMode(null)}>{copy.dialog.cancel}</Button>
            <Button onClick={handleComplete} disabled={saving || !selectedActivityId}>{copy.dialog.save}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogMode === 'stop'} onOpenChange={(open) => !open && setDialogMode(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.stopTitle}</DialogTitle>
            <DialogDescription>{copy.dialog.stopDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>{copy.stopOptionalTest}</Label>
            <Select value={stopReason} onValueChange={(value) => setStopReason(value as (typeof SAFETY_REASONS)[number] | 'unset')}>
              <SelectTrigger><SelectValue placeholder={copy.choose} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="unset">{copy.choose}</SelectItem>
                {SAFETY_REASONS.map((reason) => (
                  <SelectItem key={reason} value={reason}>{copy.stopReasons[reason]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogMode(null)}>{copy.dialog.cancel}</Button>
            <Button onClick={handleStop} disabled={saving}>{copy.dialog.save}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
