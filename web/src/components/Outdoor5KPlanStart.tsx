import { useMemo, useRef, useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import { CalendarDays, ChevronRight, RefreshCw, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import ManagedPlanSettingsCard from '@/components/ManagedPlanSettingsCard';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useLocale } from '@/contexts/LocaleContext';
import { useAuth } from '@/hooks/useAuth';
import { apiFetch, extractErrorMessage, useApi } from '@/hooks/useApi';
import { useSettings } from '@/contexts/SettingsContext';
import type {
  AdaptivePlanProposal,
  AdaptivePlanProposalAdoptResponse,
  GoalBaselineResponse,
  GoalResponse,
  Outdoor5KConstraintsRequest,
  Outdoor5KGenerateResponse,
  Outdoor5KOutcomeResponse,
  Outdoor5KReadinessResponse,
  Outdoor5KRegenerateResponse,
  Outdoor5KWeekday,
} from '@/types/api';

const DAYS: Outdoor5KWeekday[] = [0, 1, 2, 3, 4, 5, 6];

type DayLimits = Partial<Record<Outdoor5KWeekday, string>>;
type LifecycleOperation = 'generate' | 'regenerate' | 'reject' | 'adopt';

function idempotencyKey(): string {
  return crypto.randomUUID();
}

function isProposalResponse(
  value: Outdoor5KGenerateResponse | Outdoor5KRegenerateResponse,
): value is Extract<Outdoor5KGenerateResponse, { proposal: AdaptivePlanProposal | null }> {
  return 'proposal' in value;
}

function outcomeCopy(
  result: Outdoor5KOutcomeResponse,
  fallback: string,
): string {
  if (result.observed_or_stated_reason) return result.observed_or_stated_reason;
  if (result.uncertainty_or_missing_field) return result.uncertainty_or_missing_field;
  return fallback;
}

function proposalStateLabel(state: AdaptivePlanProposal['state']): string {
  return state.replace(/_/g, ' ');
}

function baselineCopy(
  baseline: GoalBaselineResponse | undefined,
  ready: string,
  pending: string,
): string {
  if (!baseline) return pending;
  return baseline.readiness === 'sufficient_baseline' ? ready : pending;
}

export function Outdoor5KGoalEntry({
  baseline,
}: {
  baseline: GoalBaselineResponse | undefined;
}) {
  const { t } = useLingui();
  const navigate = useNavigate();
  const canStart = baseline?.readiness === 'sufficient_baseline';

  return (
    <Card className="mb-5">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <CardTitle><Trans>Outdoor road 5K plan</Trans></CardTitle>
            <CardDescription className="mt-2">
              <Trans>
                This pilot is for adult, self-coached recreational runners preparing for an outdoor road 5K.
              </Trans>
            </CardDescription>
          </div>
          <Badge variant={canStart ? 'default' : 'outline'}>
            {baselineCopy(
              baseline,
              t`Baseline ready`,
              t`Review baseline`,
            )}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
          <Trans>
            A preview is a proposal, not yet your plan. Praxys checks the current evidence and constraints again before it creates one.
          </Trans>
        </p>
        <Button onClick={() => navigate('/training#outdoor-5k-plan')} className="min-h-11 shrink-0">
          <Trans>Open plan preview</Trans>
          <ChevronRight aria-hidden="true" />
        </Button>
      </CardContent>
    </Card>
  );
}

function PlanStartSkeleton() {
  return (
    <Card id="outdoor-5k-plan">
      <CardHeader>
        <Skeleton className="h-6 w-52" />
        <Skeleton className="mt-3 h-4 w-full max-w-xl" />
      </CardHeader>
      <CardContent className="space-y-3">
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-24 w-full" />
      </CardContent>
    </Card>
  );
}

export default function Outdoor5KPlanStart() {
  const { t } = useLingui();
  const { locale } = useLocale();
  const { isDemo } = useAuth();
  const { config, planDeliveryOptions, updateSettings } = useSettings();
  const navigate = useNavigate();
  const {
    data: goal,
    loading: goalLoading,
    error: goalError,
    refetch: refetchGoal,
  } = useApi<GoalResponse>('/api/goal', { timeoutMs: 12_000 });
  const {
    data: currentProposal,
    error: currentProposalError,
    refetch: refetchProposal,
  } = useApi<AdaptivePlanProposal>('/api/plan/proposals/current', { timeoutMs: 12_000 });

  const [availableDays, setAvailableDays] = useState<Outdoor5KWeekday[]>([]);
  const [dayLimits, setDayLimits] = useState<DayLimits>({});
  const [preferredLongestDay, setPreferredLongestDay] = useState<string>('');
  const [adult, setAdult] = useState(false);
  const [selfCoached, setSelfCoached] = useState(false);
  const [canComplete, setCanComplete] = useState(false);
  const [outdoorRoad, setOutdoorRoad] = useState(false);
  const [safetyStop, setSafetyStop] = useState(false);
  const [readiness, setReadiness] = useState<
    Outdoor5KReadinessResponse | Outdoor5KGenerateResponse | Outdoor5KRegenerateResponse | null
  >(null);
  const [proposal, setProposal] = useState<AdaptivePlanProposal | null>(null);
  const [working, setWorking] = useState<'readiness' | 'generate' | 'regenerate' | 'reject' | 'adopt' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const idempotencyKeys = useRef<Partial<Record<LifecycleOperation, string>>>({});

  const activeProposal = proposal ?? currentProposal;
  const noCurrentProposal = currentProposalError === 'HTTP 404';
  const proposalLoadError = currentProposalError && !noCurrentProposal
    ? currentProposalError
    : null;
  const sharedDuration = useMemo(() => {
    if (availableDays.length === 0) return null;
    const values = availableDays.map((day) => dayLimits[day]?.trim() ?? '');
    if (values.some((value) => !value)) return null;
    if (new Set(values).size !== 1) return null;
    const parsed = Number(values[0]);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [availableDays, dayLimits]);
  const perDayLimitsUnsupported = availableDays.length > 1
    && new Set(availableDays.map((day) => dayLimits[day]?.trim() ?? '')).size > 1;
  const scopeComplete = adult && selfCoached && canComplete && outdoorRoad;
  const formError = !scopeComplete
    ? t`Confirm the supported athlete and goal scope first.`
    : availableDays.length === 0
      ? t`Choose the days you are available to run.`
      : sharedDuration == null
        ? perDayLimitsUnsupported
          ? t`Per-day limits are unsupported by this policy. Use one shared limit for all selected days.`
          : t`Enter one whole-minute limit for every selected day.`
        : null;
  const dayName = (day: Outdoor5KWeekday, short = false): string => (
    new Intl.DateTimeFormat(locale === 'zh' ? 'zh-CN' : 'en-US', { weekday: short ? 'short' : 'long' })
      .format(new Date(Date.UTC(2024, 0, day + 1)))
  );
  const operationKey = (operation: LifecycleOperation): string => {
    const existing = idempotencyKeys.current[operation];
    if (existing) return existing;
    const next = idempotencyKey();
    idempotencyKeys.current[operation] = next;
    return next;
  };
  const clearOperationKey = (operation: LifecycleOperation) => {
    delete idempotencyKeys.current[operation];
  };

  const toggleDay = (day: Outdoor5KWeekday) => {
    setAvailableDays((current) => {
      if (current.includes(day)) {
        setDayLimits((limits) => {
          const next = { ...limits };
          delete next[day];
          return next;
        });
        if (preferredLongestDay === String(day)) setPreferredLongestDay('');
        return current.filter((value) => value !== day);
      }
      return [...current, day].sort((a, b) => a - b);
    });
    setReadiness(null);
    setError(null);
  };

  const setDayLimit = (day: Outdoor5KWeekday, value: string) => {
    setDayLimits((current) => ({ ...current, [day]: value }));
    setReadiness(null);
    setError(null);
  };

  const constraints = (): Outdoor5KConstraintsRequest | null => {
    if (formError || sharedDuration == null) {
      setError(formError ?? t`Review the constraints and try again.`);
      return null;
    }
    return {
      age_18_or_older: adult,
      self_coached_recreational_road_runner: selfCoached,
      can_complete_5k: canComplete,
      safety_stop: safetyStop,
      outdoor_road_goal_confirmed: outdoorRoad,
      available_weekdays: availableDays,
      maximum_session_duration_min: sharedDuration,
      preferred_longest_run_weekday: preferredLongestDay === ''
        ? null
        : Number(preferredLongestDay) as Outdoor5KWeekday,
    };
  };

  const requestReadiness = async (): Promise<Outdoor5KReadinessResponse | null> => {
    const body = constraints();
    if (!body) return null;
    setWorking('readiness');
    setError(null);
    setNotice(null);
    try {
      const response = await apiFetch('/api/plan/outdoor-5k/readiness', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await extractErrorMessage(response, t`Could not assess this plan start.`));
      const value = await response.json() as Outdoor5KReadinessResponse;
      setReadiness(value);
      return value;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t`Could not assess this plan start.`);
      return null;
    } finally {
      setWorking(null);
    }
  };

  const generate = async () => {
    const checked = await requestReadiness();
    const body = constraints();
    if (!checked || !body || checked.result.code !== 'ready') return;
    setWorking('generate');
    setError(null);
    try {
      const response = await apiFetch('/api/plan/outdoor-5k/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...body,
          expected_source_revision: checked.source_revision,
          idempotency_key: operationKey('generate'),
        }),
      });
      if (!response.ok) throw new Error(await extractErrorMessage(response, t`Could not create the proposal.`));
      const value = await response.json() as Outdoor5KGenerateResponse;
      if (isProposalResponse(value) && value.proposal) {
        setProposal(value.proposal);
        setNotice(t`Proposal created. It has not changed your canonical plan.`);
        void refetchProposal();
      } else {
        setReadiness(value);
      }
      clearOperationKey('generate');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t`Could not create the proposal.`);
    } finally {
      setWorking(null);
    }
  };

  const regenerate = async () => {
    if (!activeProposal) return;
    const checked = await requestReadiness();
    const body = constraints();
    if (!checked || !body || checked.result.code !== 'ready') return;
    setWorking('regenerate');
    setError(null);
    try {
      const response = await apiFetch(
        `/api/plan/outdoor-5k/proposals/${encodeURIComponent(activeProposal.id)}/regenerate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...body,
            expected_source_revision: checked.source_revision,
            expected_proposal_version: activeProposal.version,
            idempotency_key: operationKey('regenerate'),
          }),
        },
      );
      if (!response.ok) throw new Error(await extractErrorMessage(response, t`Could not regenerate the proposal.`));
      const value = await response.json() as Outdoor5KRegenerateResponse;
      if (isProposalResponse(value) && value.proposal) {
        setProposal(value.proposal);
        setNotice(t`A successor proposal is ready. The earlier proposal is preserved as superseded.`);
        void refetchProposal();
      } else {
        setReadiness(value);
      }
      clearOperationKey('regenerate');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t`Could not regenerate the proposal.`);
    } finally {
      setWorking(null);
    }
  };

  const reject = async () => {
    if (!activeProposal) return;
    setWorking('reject');
    setError(null);
    try {
      const response = await apiFetch(
        `/api/plan/proposals/${encodeURIComponent(activeProposal.id)}/reject`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expected_version: activeProposal.version,
            idempotency_key: operationKey('reject'),
          }),
        },
      );
      if (!response.ok) throw new Error(await extractErrorMessage(response, t`Could not reject the proposal.`));
      setProposal(await response.json() as AdaptivePlanProposal);
      setNotice(t`Proposal rejected. Your canonical plan was not changed.`);
      clearOperationKey('reject');
      void refetchProposal();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t`Could not reject the proposal.`);
    } finally {
      setWorking(null);
    }
  };

  const adopt = async () => {
    if (!activeProposal) return;
    setWorking('adopt');
    setError(null);
    try {
      const response = await apiFetch(
        `/api/plan/proposals/${encodeURIComponent(activeProposal.id)}/adopt`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expected_proposal_version: activeProposal.version,
            expected_plan_version: activeProposal.adaptive_plan?.version ?? activeProposal.base_plan_version,
            idempotency_key: operationKey('adopt'),
          }),
        },
      );
      if (!response.ok) throw new Error(await extractErrorMessage(response, t`Could not adopt the proposal.`));
      const value = await response.json() as AdaptivePlanProposalAdoptResponse;
      setProposal(value.proposal);
      setNotice(value.status === 'already_adopted'
        ? t`This exact proposal was already adopted. Delivery remains disabled until you explicitly enable it.`
        : t`Plan adopted. Delivery remains disabled until you explicitly enable it.`);
      clearOperationKey('adopt');
      void refetchProposal();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t`Could not adopt the proposal.`);
    } finally {
      setWorking(null);
    }
  };

  if (goalLoading) return <PlanStartSkeleton />;

  if (goalError) {
    return (
      <Alert id="outdoor-5k-plan" variant="destructive">
        <AlertTitle><Trans>Could not load plan-start context</Trans></AlertTitle>
        <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
          <span>{goalError}</span>
          <Button variant="outline" size="sm" onClick={() => void refetchGoal()}><Trans>Retry</Trans></Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (goal?.goal_kind !== 'performance_5k') {
    return (
      <Card id="outdoor-5k-plan">
        <CardHeader>
          <CardTitle><Trans>Outdoor road 5K plans</Trans></CardTitle>
          <CardDescription>
            <Trans>This plan-start pilot is available only for the supported outdoor road 5K performance goal.</Trans>
          </CardDescription>
        </CardHeader>
        <CardContent className="border-t border-border pt-4">
          <Button onClick={() => navigate('/goal')}><Trans>Review goal</Trans></Button>
        </CardContent>
      </Card>
    );
  }

  const baseline = goal.baseline;
  const result = readiness?.result;
  const isDraft = activeProposal?.state === 'draft';
  const isAdopted = activeProposal?.state === 'adopted';
  const hasLifecycleState = activeProposal && !isDraft && !isAdopted;

  return (
    <section id="outdoor-5k-plan" aria-labelledby="outdoor-5k-plan-title" className="scroll-mt-6 space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-2xl">
              <CardTitle id="outdoor-5k-plan-title"><Trans>Plan preview</Trans></CardTitle>
              <CardDescription className="mt-2">
                <Trans>
                  Set the constraints you can actually keep. Praxys returns a deterministic proposal; it is not yet your plan.
                </Trans>
              </CardDescription>
            </div>
            <Badge variant={baseline?.readiness === 'sufficient_baseline' ? 'default' : 'outline'}>
              {baselineCopy(baseline, t`Baseline ready`, t`Baseline needs review`)}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 border-t border-border pt-5">
          <Alert>
            <ShieldCheck className="size-4" aria-hidden="true" />
            <AlertTitle><Trans>Scope and guardrails</Trans></AlertTitle>
            <AlertDescription>
              <Trans>
                This is a pilot for adult, self-coached recreational outdoor-road 5K runners. It does not diagnose, clear, or guarantee a performance outcome.
              </Trans>
            </AlertDescription>
          </Alert>

          <div className="grid gap-2 sm:grid-cols-2">
            {[
              { value: adult, set: setAdult, label: t`I am 18 or older.` },
              { value: selfCoached, set: setSelfCoached, label: t`I am self-coached for recreational road running.` },
              { value: canComplete, set: setCanComplete, label: t`I can currently complete 5 km.` },
              { value: outdoorRoad, set: setOutdoorRoad, label: t`My goal is an outdoor road 5K.` },
            ].map((item) => (
              <Button
                key={item.label}
                type="button"
                variant="outline"
                aria-pressed={item.value}
                onClick={() => {
                  item.set((value) => !value);
                  setReadiness(null);
                }}
                className={`min-h-12 justify-start whitespace-normal text-left ${item.value ? 'border-primary text-primary' : ''}`}
              >
                {item.label}
              </Button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-y border-border py-4">
            <div>
              <h3 className="text-sm font-semibold"><Trans>Safety stop</Trans></h3>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                <Trans>Tell Praxys if a safety stop applies. It will stop this plan path and show policy-bounded alternatives.</Trans>
              </p>
            </div>
            <Button
              type="button"
              variant={safetyStop ? 'destructive' : 'outline'}
              aria-pressed={safetyStop}
              onClick={() => {
                setSafetyStop((value) => !value);
                setReadiness(null);
              }}
            >
              {safetyStop ? <Trans>Safety stop applies</Trans> : <Trans>No safety stop</Trans>}
            </Button>
          </div>

          <div>
            <h3 className="text-sm font-semibold"><Trans>Available run days</Trans></h3>
            <p className="mt-1 text-sm text-muted-foreground">
              <Trans>Select availability, then give the same supported session limit for each selected day.</Trans>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {DAYS.map((day) => {
                const selected = availableDays.includes(day);
                return (
                  <Button
                    key={day}
                    type="button"
                    variant="outline"
                    aria-pressed={selected}
                    aria-label={dayName(day)}
                    onClick={() => toggleDay(day)}
                    className={`min-h-11 min-w-12 ${selected ? 'border-primary text-primary' : ''}`}
                  >
                    {dayName(day, true)}
                  </Button>
                );
              })}
            </div>
          </div>

          {availableDays.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2">
              {availableDays.map((day) => {
                const dayLabel = dayName(day);
                return (
                  <div key={day} className="space-y-2">
                    <Label htmlFor={`outdoor-5k-day-${day}`}><Trans>{dayLabel} time limit (minutes)</Trans></Label>
                    <Input
                      id={`outdoor-5k-day-${day}`}
                      type="number"
                      min="1"
                      inputMode="numeric"
                      value={dayLimits[day] ?? ''}
                      onChange={(event) => setDayLimit(day, event.target.value)}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {perDayLimitsUnsupported && (
            <Alert>
              <AlertTitle><Trans>Per-day limits are unsupported</Trans></AlertTitle>
              <AlertDescription>
                <Trans>
                  The accepted deterministic policy has one shared maximum-session field. Praxys will not invent a per-day rule or silently reduce your schedule; use one limit for all selected days.
                </Trans>
              </AlertDescription>
            </Alert>
          )}

          <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="outdoor-5k-long-day"><Trans>Preferred longest-run day</Trans></Label>
              <Select
                value={preferredLongestDay === '' ? 'none' : preferredLongestDay}
                onValueChange={(value) => setPreferredLongestDay(value === 'none' || value == null ? '' : value)}
              >
                <SelectTrigger id="outdoor-5k-long-day"><SelectValue placeholder={t`No preference`} /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none"><Trans>No preference</Trans></SelectItem>
                  {availableDays.map((day) => (
                    <SelectItem key={day} value={String(day)}>
                      {dayName(day)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Alert>
              <CalendarDays className="size-4" aria-hidden="true" />
              <AlertTitle><Trans>Terrain and equipment</Trans></AlertTitle>
              <AlertDescription>
                <Trans>
                  This policy supports outdoor road running only. Terrain, treadmill, trail, and equipment preferences are unsupported inputs and are not inferred.
                </Trans>
              </AlertDescription>
            </Alert>
          </div>

          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <div className="flex flex-wrap gap-2">
            <Button disabled={isDemo || working != null} onClick={() => void requestReadiness()} className="min-h-11">
              {working === 'readiness' ? <Trans>Checking readiness…</Trans> : <Trans>Check readiness</Trans>}
            </Button>
            {result?.code === 'ready' && !activeProposal && (
              <Button variant="outline" disabled={isDemo || working != null} onClick={() => void generate()} className="min-h-11">
                {working === 'generate' ? <Trans>Creating proposal…</Trans> : <Trans>Create proposal</Trans>}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle><Trans>Readiness result</Trans></CardTitle>
              <Badge variant={result.code === 'ready' ? 'default' : 'outline'}>{result.code.replace(/_/g, ' ')}</Badge>
            </div>
            <CardDescription>{outcomeCopy(result, t`The deterministic policy returned no additional explanation.`)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
              <Trans>History used:</Trans>{' '}
              <span className="font-data">{result.history_statistics.usable_completed_weeks}</span>{' '}
              <Trans>complete weeks; latest run</Trans>{' '}
              <span className="font-data">{result.history_statistics.latest_run_date ?? '—'}</span>.
            </p>
            {result.alternatives.length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {result.alternatives.map((alternative) => <li key={alternative}>{alternative}</li>)}
              </ul>
            )}
            <p className="text-sm text-muted-foreground">
              <Trans>
                This deterministic result uses the published and pilot guardrails named by the policy response. It is not AI coaching and does not make an injury, readiness, or goal guarantee.
              </Trans>
            </p>
          </CardContent>
        </Card>
      )}

      {proposalLoadError && (
        <Alert variant="destructive">
          <AlertTitle><Trans>Could not refresh proposal state</Trans></AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>{proposalLoadError}</span>
            <Button size="sm" variant="outline" onClick={() => void refetchProposal()}><Trans>Retry</Trans></Button>
          </AlertDescription>
        </Alert>
      )}

      {activeProposal && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle><Trans>Plan proposal</Trans></CardTitle>
                <CardDescription className="mt-2">
                  <Trans>This proposal is not yet your plan. It cannot deliver workouts until after explicit adoption and separate delivery consent.</Trans>
                </CardDescription>
              </div>
              <Badge variant={isAdopted ? 'default' : 'outline'}>{proposalStateLabel(activeProposal.state)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 border-t border-border pt-4">
            <dl className="grid gap-3 text-sm sm:grid-cols-3">
              <div><dt className="text-muted-foreground"><Trans>Policy</Trans></dt><dd className="mt-1 font-data">{activeProposal.policy_version ?? '—'}</dd></div>
              <div><dt className="text-muted-foreground"><Trans>Generator</Trans></dt><dd className="mt-1 font-data">{activeProposal.model_version ?? '—'}</dd></div>
              <div><dt className="text-muted-foreground"><Trans>Science decision</Trans></dt><dd className="mt-1 font-data">{activeProposal.science_version ?? '—'}</dd></div>
            </dl>
            <div className="divide-y divide-border border-y border-border">
              {activeProposal.workouts.map((workout) => (
                <div key={`${workout.date}-${workout.workout_type}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3 text-sm">
                  <span><span className="font-data">{workout.date}</span> · {workout.workout_type.replace(/_/g, ' ')}</span>
                  <span className="font-data text-muted-foreground">{workout.planned_duration_min ?? '—'} min</span>
                </div>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">
              <Trans>
                Workout content is view-only in this deterministic policy. Change the bounded inputs above and regenerate to create an immutable successor; Praxys never constructs replacement workouts in this client.
              </Trans>
            </p>
            {[activeProposal.assumptions, activeProposal.unknowns, activeProposal.warnings, activeProposal.alternatives]
              .filter((items) => items.length > 0)
              .map((items, index) => (
                <p key={index} className="text-sm text-muted-foreground">{items.map(String).join(' · ')}</p>
              ))}
            {activeProposal.expires_at && (
              <p className="text-sm text-muted-foreground"><Trans>Expires:</Trans> <span className="font-data">{activeProposal.expires_at}</span></p>
            )}

            {isDraft && (
              <div className="flex flex-wrap gap-2">
                <Button disabled={isDemo || working != null} onClick={() => void adopt()} className="min-h-11">
                  {working === 'adopt' ? <Trans>Adopting…</Trans> : <Trans>Adopt exact proposal</Trans>}
                </Button>
                <Button variant="outline" disabled={isDemo || working != null} onClick={() => void regenerate()} className="min-h-11">
                  <RefreshCw aria-hidden="true" />
                  {working === 'regenerate' ? <Trans>Regenerating…</Trans> : <Trans>Regenerate successor</Trans>}
                </Button>
                <Button variant="ghost" disabled={isDemo || working != null} onClick={() => void reject()} className="min-h-11">
                  {working === 'reject' ? <Trans>Rejecting…</Trans> : <Trans>Reject or defer</Trans>}
                </Button>
              </div>
            )}

            {hasLifecycleState && (
              <Alert>
                <AlertTitle><Trans>Proposal state needs a fresh preview</Trans></AlertTitle>
                <AlertDescription>
                  <Trans>
                    This proposal is {proposalStateLabel(activeProposal.state)}. It cannot mutate the canonical plan; review readiness and create a new proposal when you are ready.
                  </Trans>
                </AlertDescription>
              </Alert>
            )}
            {isAdopted && (
              <Alert>
                <AlertTitle><Trans>Plan adopted</Trans></AlertTitle>
                <AlertDescription>
                  <Trans>Delivery remains disabled. Review the existing 14-day managed-delivery preview and explicitly consent only if you want Praxys to deliver this canonical plan.</Trans>
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {isAdopted && config && (
        <ManagedPlanSettingsCard
          config={config}
          planDeliveryOptions={planDeliveryOptions}
          updateSettings={updateSettings}
        />
      )}

      {notice && <p className="text-sm text-primary" role="status">{notice}</p>}
      {error && (
        <Alert variant="destructive">
          <AlertTitle><Trans>Plan-start action did not complete</Trans></AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>{error}</span>
            {(error.includes('STALE') || error.includes('CONFLICT') || error.includes('409')) && (
              <Button size="sm" variant="outline" onClick={() => void refetchProposal()}><Trans>Refresh proposal</Trans></Button>
            )}
          </AlertDescription>
        </Alert>
      )}
    </section>
  );
}
