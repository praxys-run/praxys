import { useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
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
  GoalBaselineResponse,
  PlanGenerationPurposeSelection,
  Road10KAssistanceStatus,
  Road10KBaselineCandidate,
  Road10KBaselineMutationResponse,
  Road10KBaselineResponse,
  Road10KHistoryConfirmationRequest,
  Road10KSurfaceOrProtocol,
} from '@/types/api';

interface GoalBaselinePanelProps {
  baseline: GoalBaselineResponse | Road10KBaselineResponse;
  goal: { distance?: string | null; target_time_sec?: number | null; eligible?: boolean } | undefined;
  purpose?: PlanGenerationPurposeSelection;
  isDemo: boolean;
  onChanged: () => void;
}

type ConfirmResponse = 'race' | 'intentional_all_out' | 'not_all_out' | 'unset';
type DialogMode = 'confirm' | 'offer' | 'schedule' | 'complete' | 'stop' | null;
type SurfaceOrProtocolValue = Road10KSurfaceOrProtocol | 'unset';
type AssistanceStatusValue = Road10KAssistanceStatus | 'unset';

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

function isRoad10KBaseline(
  baseline: GoalBaselineResponse | Road10KBaselineResponse,
): baseline is Road10KBaselineResponse {
  return 'contract_digest' in baseline;
}

function Road10KBaselinePanel({
  baseline,
  goal,
  purpose,
  isDemo,
  onChanged,
}: {
  baseline: Road10KBaselineResponse;
  goal: GoalBaselinePanelProps['goal'];
  purpose?: PlanGenerationPurposeSelection;
  isDemo: boolean;
  onChanged: () => void;
}) {
  const { t } = useLingui();
  const { locale } = useLocale();
  const copy = {
    sectionLabel: t`10K direct baseline`,
    status: {
      current: t`Current`,
      stale: t`Stale`,
      incomparable: t`Needs review`,
      missing: t`Missing evidence`,
      not_required: t`Not required`,
    },
    headline: {
      current: t`You already have usable current 10K evidence.`,
      stale: t`You have older 10K evidence. Praxys keeps it visible, but new planning stays readiness-only until you refresh it.`,
      incomparable: t`Praxys found candidate 10K efforts, but they are not qualified yet.`,
      missing: t`Praxys has not found qualified 10K history yet.`,
      not_required: t`The current goal is outside this direct 10K baseline flow.`,
    },
    readiness: {
      sufficient_baseline: t`Direct 10K baseline evidence is currently sufficient.`,
      insufficient_evidence: t`This is not a failure; it means current direct 10K evidence is still missing or stale.`,
    },
    target: t`Goal`,
    evidence: t`Current evidence`,
    age: t`Evidence age`,
    protocol: t`Accepted surface or protocol`,
    routeOrVenue: t`Route or venue`,
    assistance: t`Assistance status`,
    candidateTitle: t`History candidates`,
    candidateHint: t`Retrieval is never qualification; only a full activity with explicit distance, timing, accepted protocol, route or venue, and all-out or race confirmation can become a direct 10K baseline.`,
    reviewCandidate: t`Review this effort`,
    changeCandidate: t`Change confirmation`,
    fullActivityOnly: t`Full activity only`,
    segmentRule: t`Passive fastest 10K splits, best laps, or hard sections inside longer runs never count as direct 10K baseline evidence.`,
    cutoff: t`The 56-day rule is a reviewed guardrail, not a physiological cutoff.`,
    benchmarkTitle: t`Optional 10K benchmark`,
    benchmarkHint: t`Choose and date an optional benchmark in the Training plan preview if you want one. Praxys never auto-schedules it.`,
    scienceDescription: t`Only current direct 10K race or explicit all-out 10K history can qualify. Qualification keeps the accepted protocol, route or venue, assistance status, provider, and authoritative completion time attached to the evidence. The 56-day freshness guardrail and the optional benchmark path are reviewed product boundaries, not published universal cutoffs.`,
    options: {
      race: t`Measured 10K race`,
      intentional_all_out: t`Intentional all-out complete 10K`,
      not_all_out: t`Not a direct 10K baseline`,
      organized_outdoor_road_10k_race: t`Organized outdoor road 10K race`,
      standardized_outdoor_road_10k_time_trial: t`Standardized outdoor road 10K time trial`,
      standardized_track_10k_time_trial: t`Standardized track 10K time trial`,
      unassisted: t`Unassisted`,
      assisted: t`Assisted`,
      unknown_or_unreported: t`Unknown or unreported`,
      yes: t`Yes`,
      no: t`No`,
    },
    reviewState: {
      needs_confirmation: t`Needs confirmation`,
      qualified: t`Qualified`,
      excluded: t`Excluded`,
      distance_unverified: t`Distance not verified`,
      timing_unresolved: t`Timing needs review`,
    },
    alternatives: {
      optional_10k_benchmark: t`Choose an optional 10K benchmark date`,
      manual_training: t`Keep training manually for now`,
    },
    dialog: {
      confirmTitle: t`Review this activity`,
      confirmDescription: t`Only explicit distance, timing, protocol, route or venue, and intent confirmation can turn history into a direct 10K baseline.`,
      effortLabel: t`What was this full activity?`,
      measuredLabel: t`Was the full effort a measured 10K?`,
      timingLabel: t`Did the recorded time reflect elapsed timing with no unresolved pauses?`,
      protocolLabel: t`Which accepted surface or protocol matched this effort?`,
      routeLabel: t`Route or venue identifier`,
      assistanceLabel: t`Assistance status`,
      save: t`Save`,
      cancel: t`Cancel`,
    },
    choose: t`Choose one`,
    mutationSuccess: t`Updated the 10K baseline.`,
    requestFailed: t`Request failed`,
  };
  const alternatives = baseline.alternatives.map((alternative) => (
    alternative === 'optional_10k_benchmark'
      ? copy.alternatives.optional_10k_benchmark
      : alternative === 'manual_training'
        ? copy.alternatives.manual_training
        : alternative
  ));
  const [activeCandidate, setActiveCandidate] = useState<Road10KBaselineCandidate | null>(null);
  const [response, setResponse] = useState<ConfirmResponse>('unset');
  const [measured, setMeasured] = useState<'yes' | 'no' | 'unset'>('unset');
  const [timing, setTiming] = useState<'yes' | 'no' | 'unset'>('unset');
  const [surfaceOrProtocol, setSurfaceOrProtocol] = useState<SurfaceOrProtocolValue>('unset');
  const [routeOrVenue, setRouteOrVenue] = useState('');
  const [assistanceStatus, setAssistanceStatus] = useState<AssistanceStatusValue>('unset');
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutate = async (body: Road10KHistoryConfirmationRequest) => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await apiFetch('/api/plan/road-10k/baseline/history/confirm', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID(),
        },
        body: JSON.stringify(purpose ? { ...body, purpose } : body),
      });
      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, copy.requestFailed));
      }
      await res.json() as Promise<Road10KBaselineMutationResponse>;
      setNotice(copy.mutationSuccess);
      setOpen(false);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.requestFailed);
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (!activeCandidate) return;
    const directQualificationClaim = response === 'race' || response === 'intentional_all_out';
    if (
      response === 'unset'
      || measured === 'unset'
      || timing === 'unset'
      || assistanceStatus === 'unset'
      || (
        directQualificationClaim
        && (
          surfaceOrProtocol === 'unset'
          || routeOrVenue.trim().length === 0
        )
      )
    ) {
      setError(copy.choose);
      return;
    }
    const body: Road10KHistoryConfirmationRequest = {
      activity_id: activeCandidate.activity_id,
      response,
      measured_10k: measured === 'yes',
      elapsed_timing_confirmed: timing === 'yes',
      assistance_status: assistanceStatus,
    };
    if (directQualificationClaim) {
      body.surface_or_protocol = surfaceOrProtocol as Road10KSurfaceOrProtocol;
      body.route_or_venue_identifier = routeOrVenue.trim();
    }
    await mutate(body);
  };
  const requiresDirectQualificationMetadata = response === 'race' || response === 'intentional_all_out';

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
              <p className="mt-1 text-sm text-foreground">{goal?.distance?.toUpperCase() ?? '10K'} {goal?.target_time_sec ? <span className="font-data">· {formatTime(goal.target_time_sec)}</span> : null}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.evidence}</p>
              <p className="mt-1 text-sm text-foreground">{baseline.evidence ? `${copy.status.current} · ${baseline.evidence.provenance}` : '—'}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.age}</p>
              <p className="mt-1 text-sm text-foreground font-data">{baseline.evidence ? t`${baseline.evidence.age_days} days` : '—'}</p>
            </div>
          </div>
          {baseline.evidence && (
            <div className="rounded-lg border border-border p-4">
              <p className="text-sm text-foreground">
                <span className="font-medium">{formatDate(baseline.evidence.observed_date, locale)}</span>
                <span className="font-data"> · {baseline.evidence.distance_km?.toFixed(2)} km · {baseline.evidence.elapsed_time_sec ? formatTime(Math.round(baseline.evidence.elapsed_time_sec)) : '—'}</span>
              </p>
              <div className="mt-3 grid gap-3 text-sm text-muted-foreground sm:grid-cols-2">
                <p>
                  <span className="font-medium text-foreground">{copy.protocol}:</span>{' '}
                  {baseline.evidence.surface_or_protocol
                    ? copy.options[baseline.evidence.surface_or_protocol]
                    : '—'}
                </p>
                <p>
                  <span className="font-medium text-foreground">{copy.assistance}:</span>{' '}
                  {baseline.evidence.assistance_status
                    ? copy.options[baseline.evidence.assistance_status]
                    : '—'}
                </p>
                <p>
                  <span className="font-medium text-foreground">{copy.routeOrVenue}:</span>{' '}
                  {baseline.evidence.route_or_venue_identifier ?? '—'}
                </p>
                <p>
                  <span className="font-medium text-foreground"><Trans>Provider</Trans>:</span>{' '}
                  {baseline.evidence.source_provider ?? '—'}
                </p>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{copy.cutoff}</p>
            </div>
          )}
          <Alert>
            <AlertTitle>{copy.fullActivityOnly}</AlertTitle>
            <AlertDescription>{copy.segmentRule}</AlertDescription>
          </Alert>
          {notice && <p className="text-sm text-primary">{notice}</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}
          <ScienceNote text={copy.scienceDescription} sources={baseline.science_note.citations} />
          {alternatives.length > 0 && (
            <p className="text-sm text-muted-foreground">{alternatives.join(' · ')}</p>
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
                <p className="text-sm text-muted-foreground">{copy.reviewState[candidate.review_state]}</p>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  setActiveCandidate(candidate);
                  setResponse((candidate.confirmation_response ?? 'unset') as ConfirmResponse);
                  setMeasured(candidate.measured_10k_confirmed == null ? 'unset' : candidate.measured_10k_confirmed ? 'yes' : 'no');
                  setTiming(candidate.elapsed_timing_confirmed == null ? 'unset' : candidate.elapsed_timing_confirmed ? 'yes' : 'no');
                  setSurfaceOrProtocol((candidate.surface_or_protocol ?? 'unset') as SurfaceOrProtocolValue);
                  setRouteOrVenue(candidate.route_or_venue_identifier ?? '');
                  setAssistanceStatus((candidate.assistance_status ?? 'unset') as AssistanceStatusValue);
                  setOpen(true);
                  setError(null);
                }}
                disabled={isDemo || saving}
              >
                {candidate.confirmation_response ? copy.changeCandidate : copy.reviewCandidate}
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.benchmarkTitle}</CardTitle>
          <CardDescription>{copy.benchmarkHint}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            <Trans>Use the Training plan preview to add, date, or decline an optional benchmark. Praxys keeps it off the calendar until you explicitly choose it.</Trans>
          </p>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.confirmTitle}</DialogTitle>
            <DialogDescription>{copy.dialog.confirmDescription}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="road-10k-confirm-effort">{copy.dialog.effortLabel}</Label>
              <Select value={response === 'unset' ? null : response} onValueChange={(value) => setResponse((value ?? 'unset') as ConfirmResponse)}>
                <SelectTrigger id="road-10k-confirm-effort" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="race">{copy.options.race}</SelectItem>
                  <SelectItem value="intentional_all_out">{copy.options.intentional_all_out}</SelectItem>
                  <SelectItem value="not_all_out">{copy.options.not_all_out}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="road-10k-confirm-measured">{copy.dialog.measuredLabel}</Label>
              <Select value={measured === 'unset' ? null : measured} onValueChange={(value) => setMeasured((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="road-10k-confirm-measured" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="road-10k-confirm-timing">{copy.dialog.timingLabel}</Label>
              <Select value={timing === 'unset' ? null : timing} onValueChange={(value) => setTiming((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="road-10k-confirm-timing" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {requiresDirectQualificationMetadata && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="road-10k-confirm-protocol">{copy.dialog.protocolLabel}</Label>
                  <Select
                    value={surfaceOrProtocol === 'unset' ? null : surfaceOrProtocol}
                    onValueChange={(value) => setSurfaceOrProtocol((value ?? 'unset') as SurfaceOrProtocolValue)}
                  >
                    <SelectTrigger id="road-10k-confirm-protocol" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="organized_outdoor_road_10k_race">{copy.options.organized_outdoor_road_10k_race}</SelectItem>
                      <SelectItem value="standardized_outdoor_road_10k_time_trial">{copy.options.standardized_outdoor_road_10k_time_trial}</SelectItem>
                      <SelectItem value="standardized_track_10k_time_trial">{copy.options.standardized_track_10k_time_trial}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="road-10k-route-venue">{copy.dialog.routeLabel}</Label>
                  <Input
                    id="road-10k-route-venue"
                    value={routeOrVenue}
                    onChange={(event) => setRouteOrVenue(event.target.value)}
                    maxLength={200}
                  />
                </div>
              </>
            )}
            <div className="space-y-2">
              <Label htmlFor="road-10k-assistance-status">{copy.dialog.assistanceLabel}</Label>
              <Select
                value={assistanceStatus === 'unset' ? null : assistanceStatus}
                onValueChange={(value) => setAssistanceStatus((value ?? 'unset') as AssistanceStatusValue)}
              >
                <SelectTrigger id="road-10k-assistance-status" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="unassisted">{copy.options.unassisted}</SelectItem>
                  <SelectItem value="assisted">{copy.options.assisted}</SelectItem>
                  <SelectItem value="unknown_or_unreported">{copy.options.unknown_or_unreported}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>{copy.dialog.cancel}</Button>
            <Button onClick={handleConfirm} disabled={saving}>{copy.dialog.save}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function GoalBaselinePanel({
  baseline,
  goal,
  purpose,
  isDemo,
  onChanged,
}: GoalBaselinePanelProps) {
  if (isRoad10KBaseline(baseline)) {
    return (
      <Road10KBaselinePanel
        baseline={baseline}
        goal={goal}
        purpose={purpose}
        isDemo={isDemo}
        onChanged={onChanged}
      />
    );
  }
  const { t } = useLingui();
  const { locale } = useLocale();
  const copy = {
    sectionLabel: t`5K baseline pilot`,
    status: {
      current: t`Current`,
      stale: t`Stale`,
      incomparable: t`Needs review`,
      missing: t`Missing evidence`,
      not_required: t`Not required`,
      pending_test: t`Test pending`,
    },
    headline: {
      current: t`History first: you already have usable current 5K evidence.`,
      stale: t`You have older 5K evidence. Praxys keeps it visible and can optionally offer a new pilot test.`,
      incomparable: t`Praxys found candidate 5K efforts, but they are not qualified yet.`,
      missing: t`Praxys has not found qualified 5K history yet.`,
      not_required: t`The current goal is outside this 5K baseline pilot.`,
      pending_test: t`The optional 5K pilot test is in progress.`,
    },
    readiness: {
      sufficient_baseline: t`Baseline evidence is currently sufficient.`,
      insufficient_evidence: t`This is not a failure; it means the evidence is still insufficient.`,
      non_diagnostic_safety_stop: t`A non-diagnostic safety stop is active; Praxys does not diagnose, treat, or clear return to running.`,
    },
    target: t`Goal`,
    evidence: t`Current evidence`,
    age: t`Evidence age`,
    candidateTitle: t`History candidates`,
    candidateHint: t`Retrieval is never qualification; only a full activity with explicit distance, timing, and purpose confirmation can become a baseline.`,
    reviewCandidate: t`Review this effort`,
    changeCandidate: t`Change confirmation`,
    fullActivityOnly: t`Full activity only`,
    segmentRule: t`Arbitrary 5K segments, best splits, or fast sections inside easy, long, or mixed runs never count as baseline evidence.`,
    noMeaningfulChange: t`There is no meaningful-change threshold yet.`,
    pilotGuardrail: t`The 42-day rule is a Praxys pilot guardrail, not a physiological cutoff.`,
    pilotScope: t`This pilot is only for adults who already can complete 5 km.`,
    scienceDescription: t`Qualified 5 km history comes first. The 42-day freshness rule, the optional maximal-effort outdoor 5 km test, and the no-meaningful-change warning are Praxys pilot guardrails, not published universal cutoffs.`,
    testTitle: t`Optional 5K pilot test`,
    testHint: t`This is a maximal-effort test, and the no-test path always stays available.`,
    reviewOptionalTest: t`Review optional test`,
    scheduleOptionalTest: t`Schedule optional test`,
    completeOptionalTest: t`Record test result`,
    stopOptionalTest: t`Stop this test`,
    declineOptionalTest: t`Stay on the no-test path`,
    pendingDate: t`Scheduled date`,
    dialog: {
      confirmTitle: t`Review this activity`,
      confirmDescription: t`Only explicit confirmation of distance, timing, and purpose can turn history into a 5K baseline.`,
      effortLabel: t`What was this full activity?`,
      measuredLabel: t`Was the full effort a measured 5K?`,
      timingLabel: t`Did the recorded time reflect elapsed timing with no unresolved pauses?`,
      protocolLabel: t`Did you follow the exact protocol?`,
      stopReasonLabel: t`Stop reason`,
      offerTitle: t`Review the optional test`,
      offerDescription: t`This appears only when history is missing, stale, or still needs review. It is a maximal-effort outdoor 5K pilot.`,
      scheduleTitle: t`Schedule the optional test`,
      scheduleDescription: t`Scheduling writes through the canonical workout, revision, and delivery lane. Nothing changes silently.`,
      completeTitle: t`Record the test result`,
      completeDescription: t`A synced activity never becomes a completed test automatically; you must confirm the protocol, distance, and timing again.`,
      stopTitle: t`Stop this test`,
      stopDescription: t`Stopping or declining preserves your account and the no-test path.`,
      save: t`Save`,
      cancel: t`Cancel`,
    },
    choose: t`Choose one`,
    options: {
      race: t`Measured 5K race`,
      intentional_all_out: t`Intentional all-out complete 5K`,
      not_all_out: t`Not an all-out 5K effort`,
      yes: t`Yes`,
      no: t`No`,
    },
    provenance: {
      race: t`Measured race`,
      intentional_all_out: t`Confirmed all-out effort`,
      pilot_test: t`Optional pilot test`,
    },
    reviewState: {
      needs_confirmation: t`Needs confirmation`,
      qualified: t`Qualified`,
      excluded: t`Excluded`,
      distance_unverified: t`Distance not verified`,
      timing_unresolved: t`Timing needs review`,
    },
    alternatives: {
      noTestPath: t`Continue without a test`,
      completionGoal: t`Use a completion or consistency goal`,
    },
    stopReasons: {
      acute_illness: t`Acute illness`,
      injury_or_pain_altering_running: t`Pain or injury altered the run`,
      chest_pain_or_pressure: t`Chest pain or pressure`,
      fainting_or_near_fainting: t`Fainting or near-fainting`,
      unusual_severe_breathlessness: t`Unusually severe breathlessness`,
      confusion_or_loss_of_coordination: t`Confusion or loss of coordination`,
      other_red_flag_symptom: t`Another red-flag symptom`,
      known_medical_restriction_or_reported_clinician_advice_against_vigorous_testing: t`A clinician or restriction already rules out vigorous testing`,
      self_reported_inadequate_recovery_or_unresolved_substantial_fatigue: t`Recovery was inadequate or fatigue stayed unresolved`,
      unsafe_heat_cold_lightning_air_quality_visibility_traffic_footing_or_course: t`Weather, air, traffic, visibility, or footing was unsafe`,
    },
    mutationSuccess: t`Updated the 5K baseline.`,
    requestFailed: t`Request failed`,
  };
  const alternatives = baseline.alternatives.map((alternative) => (
    alternative === 'no_test_path'
      ? copy.alternatives.noTestPath
      : alternative === 'completion_or_consistency_goal'
        ? copy.alternatives.completionGoal
        : alternative
  ));
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
        body: JSON.stringify(purpose ? { ...body, purpose } : body),
      });
      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, copy.requestFailed));
      }
      await res.json();
      setNotice(copy.mutationSuccess);
      setDialogMode(null);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.requestFailed);
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
              <p className="mt-1 text-sm text-foreground">{baseline.evidence ? `${copy.status.current} · ${copy.provenance[baseline.evidence.provenance]}` : '—'}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{copy.age}</p>
              <p className="mt-1 text-sm text-foreground font-data">{baseline.evidence ? t`${baseline.evidence.age_days} days` : '—'}</p>
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
            text={copy.scienceDescription}
            sources={baseline.science_note.citations}
          />
          {alternatives.length > 0 && (
            <p className="text-sm text-muted-foreground">{alternatives.join(' · ')}</p>
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
                <p className="text-sm text-muted-foreground">{copy.status.incomparable} · {copy.reviewState[candidate.review_state]}</p>
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
          <p className="text-sm text-muted-foreground">{copy.pilotScope}</p>
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
              <Label htmlFor="goal-baseline-confirm-effort">{copy.dialog.effortLabel}</Label>
              <Select value={response === 'unset' ? null : response} onValueChange={(value) => setResponse((value ?? 'unset') as ConfirmResponse)}>
                <SelectTrigger id="goal-baseline-confirm-effort" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="race">{copy.options.race}</SelectItem>
                  <SelectItem value="intentional_all_out">{copy.options.intentional_all_out}</SelectItem>
                  <SelectItem value="not_all_out">{copy.options.not_all_out}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-baseline-confirm-measured">{copy.dialog.measuredLabel}</Label>
              <Select value={measured === 'unset' ? null : measured} onValueChange={(value) => setMeasured((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="goal-baseline-confirm-measured" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-baseline-confirm-timing">{copy.dialog.timingLabel}</Label>
              <Select value={timing === 'unset' ? null : timing} onValueChange={(value) => setTiming((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="goal-baseline-confirm-timing" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
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
              <Label htmlFor="goal-baseline-complete-activity">{copy.candidateTitle}</Label>
              <Select value={selectedActivityId || null} onValueChange={(value) => setSelectedActivityId(value ?? '')}>
                <SelectTrigger id="goal-baseline-complete-activity" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  {baseline.candidates.map((candidate) => (
                    <SelectItem key={candidate.activity_id} value={candidate.activity_id}>{formatDate(candidate.observed_date, locale)} · {candidate.distance_km?.toFixed(2)} km</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-baseline-complete-measured">{copy.dialog.measuredLabel}</Label>
              <Select value={measured === 'unset' ? null : measured} onValueChange={(value) => setMeasured((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="goal-baseline-complete-measured" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-baseline-complete-timing">{copy.dialog.timingLabel}</Label>
              <Select value={timing === 'unset' ? null : timing} onValueChange={(value) => setTiming((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="goal-baseline-complete-timing" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="yes">{copy.options.yes}</SelectItem>
                  <SelectItem value="no">{copy.options.no}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-baseline-complete-protocol">{copy.dialog.protocolLabel}</Label>
              <Select value={protocolFollowed === 'unset' ? null : protocolFollowed} onValueChange={(value) => setProtocolFollowed((value ?? 'unset') as 'yes' | 'no' | 'unset')}>
                <SelectTrigger id="goal-baseline-complete-protocol" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
                <SelectContent>
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
            <Label htmlFor="goal-baseline-stop-reason">{copy.dialog.stopReasonLabel}</Label>
            <Select value={stopReason === 'unset' ? null : stopReason} onValueChange={(value) => setStopReason((value ?? 'unset') as (typeof SAFETY_REASONS)[number] | 'unset')}>
              <SelectTrigger id="goal-baseline-stop-reason" className="w-full"><SelectValue placeholder={copy.choose} /></SelectTrigger>
              <SelectContent>
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
