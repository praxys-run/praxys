import { useEffect, useMemo, useRef, useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import { CalendarDays, ChevronRight, RefreshCw, ShieldCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import ManagedPlanSettingsCard from '@/components/ManagedPlanSettingsCard';
import GoalBaselinePanel from '@/components/GoalBaselinePanel';
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
import { apiFetch, useApi } from '@/hooks/useApi';
import { useSettings } from '@/contexts/SettingsContext';
import { extractApiError } from '@/lib/api-error';
import { formatProposalDetail } from '@/lib/proposal-display';
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
  PlanGenerationCapabilitiesResponse,
  PlanGenerationPurposeSelection,
} from '@/types/api';

const DAYS: Outdoor5KWeekday[] = [0, 1, 2, 3, 4, 5, 6];
const SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_ID = 'outdoor_road_5k_constraints_v1';

type DayLimits = Partial<Record<Outdoor5KWeekday, string>>;
type LifecycleOperation = 'generate' | 'regenerate' | 'reject' | 'adopt';
type PurposeOptionSource = PlanGenerationPurposeSelection['source'];
type PlanStartWorkingState = LifecycleOperation | 'readiness' | 'refresh';

interface PlanStartErrorState {
  message: string;
  status?: number;
  code?: string;
}

interface PlanStartRequestError extends Error {
  status: number;
  code?: string;
}

const PLAN_CONTEXT_RECOVERY_CODES = new Set([
  'PLAN_PURPOSE_STALE',
  'PLAN_PURPOSE_REASSESSMENT_REQUIRED',
]);

function idempotencyKey(): string {
  return crypto.randomUUID();
}

function proposalActionHref(template: string, proposalId: string): string {
  return template.replace('{proposal_id}', encodeURIComponent(proposalId));
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

function purposeKey(source: PurposeOptionSource, capabilityId: string): string {
  return `${source}:${capabilityId}`;
}

function proposalPurposeKey(
  proposal: AdaptivePlanProposal | null,
): string | null {
  const capabilityId = proposal?.policy_version
    ? proposal.policy_version === 'outdoor-5k-plan-generation-policy-v1'
      ? 'outdoor_road_5k_v1'
      : null
    : null;
  const source = proposal?.goal?.purpose_source;
  return capabilityId && source
    ? purposeKey(source, capabilityId)
    : null;
}

async function planStartResponse<T>(
  response: Response,
  fallback: string,
): Promise<T> {
  if (!response.ok) {
    const extracted = await extractApiError(response, fallback);
    const error = new Error(extracted.message) as PlanStartRequestError;
    error.status = extracted.status;
    error.code = extracted.code;
    throw error;
  }
  return response.json() as Promise<T>;
}

function planStartError(
  error: unknown,
  fallback: string,
): PlanStartErrorState {
  if (!(error instanceof Error)) return { message: fallback };
  const requestError = error as Partial<PlanStartRequestError>;
  return {
    message: error.message,
    ...(typeof requestError.status === 'number'
      ? { status: requestError.status }
      : {}),
    ...(typeof requestError.code === 'string'
      ? { code: requestError.code }
      : {}),
  };
}

function needsPlanContextRecovery(
  error: PlanStartErrorState | null,
): boolean {
  return Boolean(
    error?.status === 409
    && error.code
    && PLAN_CONTEXT_RECOVERY_CODES.has(error.code),
  );
}

export function PlanStartGoalEntry({
  baseline,
}: {
  baseline: GoalBaselineResponse | undefined;
}) {
  const { t } = useLingui();
  const navigate = useNavigate();
  const {
    data: discovery,
    loading,
    error,
    refetch,
  } = useApi<PlanGenerationCapabilitiesResponse>(
    '/api/plan/generation/capabilities',
    { timeoutMs: 12_000 },
  );
  const capability = discovery?.selected_capability ?? null;
  const capabilitySupported = capability?.constraint_schema_id
    === SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_ID;
  const supportedCapabilities = discovery?.capabilities.filter(
    (item) => item.constraint_schema_id
      === SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_ID,
  ) ?? [];
  const capabilityUpdateRequired = capability != null && !capabilitySupported;
  const canStart = capabilitySupported
    && baseline?.readiness === 'sufficient_baseline';
  const canChoosePurpose = supportedCapabilities.some(
    (item) => item.purpose.allows_capability_goal
      || item.purpose.allows_unlinked,
  );
  const badgeVariant = error || capabilityUpdateRequired
    ? 'destructive'
    : canStart
      ? 'default'
      : 'outline';

  if (loading) {
    return (
      <Card className="mb-5">
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="mt-3 h-4 w-full max-w-xl" />
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="mb-5">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <CardTitle><Trans>Start a training plan</Trans></CardTitle>
            <CardDescription className="mt-2">
              {error ? (
                <Trans>Could not load the accepted plan-generation policies.</Trans>
              ) : capabilityUpdateRequired ? (
                <Trans>Update required for this plan policy</Trans>
              ) : capability ? (
                <Trans>
                  Praxys has an accepted <span className="font-data">{capability.horizon_days}</span>-day outdoor-road 5K policy for this goal.
                </Trans>
              ) : canChoosePurpose ? (
                <Trans>
                  The current Goal stays unchanged, and an accepted separate 5K plan purpose is available to preview.
                </Trans>
              ) : (
                <Trans>
                  Automatic generation is not available for this goal yet. Praxys will not reuse another policy outside its accepted scope.
                </Trans>
              )}
            </CardDescription>
          </div>
          <Badge variant={badgeVariant}>
            {error
              ? t`Policy check failed`
              : capabilityUpdateRequired
                ? t`Update required for this plan policy`
                : capability
                  ? baselineCopy(
                    baseline,
                    t`Baseline ready`,
                    t`Review baseline`,
                  )
                  : canChoosePurpose
                    ? t`Other plan purpose available`
                  : t`No accepted policy`}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
          {error ? (
            <Trans>
              Retry the policy check before opening a preview. Praxys will not infer availability from the current goal alone.
            </Trans>
          ) : capabilityUpdateRequired ? (
            <Trans>
              This client does not recognize the selected policy input contract and will not guess how to create a plan.
            </Trans>
          ) : capability ? (
            <Trans>
              A preview is a proposal, not yet your plan. Praxys checks the current evidence and constraints again before it creates one.
            </Trans>
          ) : canChoosePurpose ? (
            <Trans>
              Choose the accepted 5K purpose in Training. It remains independent from the current Goal unless you explicitly link it.
            </Trans>
          ) : (
            <Trans>
              You can keep this goal and manage workouts manually while separate road and trail policies go through science review.
            </Trans>
          )}
        </p>
        {error ? (
          <Button variant="outline" onClick={() => void refetch()} className="min-h-11 shrink-0">
            <Trans>Retry policy check</Trans>
          </Button>
        ) : capabilitySupported || canChoosePurpose || !capability ? (
          <Button
            variant={capabilitySupported || canChoosePurpose ? 'default' : 'outline'}
            onClick={() => navigate(
              capabilitySupported || canChoosePurpose
                ? '/training#plan-start'
                : '/training',
            )}
            className="min-h-11 shrink-0"
          >
            {capabilitySupported
              ? <Trans>Open plan preview</Trans>
              : canChoosePurpose
                ? <Trans>Choose plan purpose</Trans>
                : <Trans>Manage workouts</Trans>}
            <ChevronRight aria-hidden="true" />
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function PlanStartSkeleton() {
  return (
    <Card id="plan-start">
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

function ProposalRecoveryCard({
  proposal,
  isDemo,
  rejecting,
  onReject,
}: {
  proposal: AdaptivePlanProposal;
  isDemo: boolean;
  rejecting: boolean;
  onReject: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CardTitle><Trans>Plan proposal</Trans></CardTitle>
          <Badge variant="outline">{proposalStateLabel(proposal.state)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 border-t border-border pt-4">
        <dl className="grid gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-muted-foreground"><Trans>Policy</Trans></dt><dd className="mt-1 font-data">{proposal.policy_version ?? '—'}</dd></div>
          <div><dt className="text-muted-foreground"><Trans>Generator</Trans></dt><dd className="mt-1 font-data">{proposal.model_version ?? '—'}</dd></div>
          <div><dt className="text-muted-foreground"><Trans>Science decision</Trans></dt><dd className="mt-1 font-data">{proposal.science_version ?? '—'}</dd></div>
        </dl>
        <div className="divide-y divide-border border-y border-border">
          {proposal.workouts.map((workout) => (
            <div key={`${workout.date}-${workout.workout_type}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3 text-sm">
              <span><span className="font-data">{workout.date}</span> · {workout.workout_type.replace(/_/g, ' ')}</span>
              <span className="font-data text-muted-foreground">{workout.planned_duration_min ?? '—'} min</span>
            </div>
          ))}
        </div>
        {proposal.state === 'draft' && (
          <Button
            variant="ghost"
            disabled={isDemo || rejecting}
            onClick={onReject}
            className="min-h-11"
          >
            {rejecting ? <Trans>Rejecting…</Trans> : <Trans>Reject or defer</Trans>}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default function PlanStart() {
  const { t } = useLingui();
  const { locale } = useLocale();
  const { isDemo } = useAuth();
  const {
    config,
    error: settingsError,
    loading: settingsLoading,
    planDeliveryOptions,
    refetch: refetchSettings,
    updateSettings,
  } = useSettings();
  const navigate = useNavigate();
  const {
    data: capabilityDiscovery,
    loading: capabilityLoading,
    error: capabilityError,
    refetch: refetchCapabilities,
  } = useApi<PlanGenerationCapabilitiesResponse>(
    '/api/plan/generation/capabilities',
    { timeoutMs: 12_000 },
  );
  const supportedCapabilities = useMemo(
    () => capabilityDiscovery?.capabilities.filter(
      (item) => item.constraint_schema_id
        === SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_ID,
    ) ?? [],
    [capabilityDiscovery],
  );
  const currentCapability = capabilityDiscovery?.selected_capability?.constraint_schema_id
    === SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_ID
    ? capabilityDiscovery.selected_capability
    : null;
  const hasSelectablePurpose = Boolean(
    currentCapability && capabilityDiscovery?.current_goal,
  ) || supportedCapabilities.some(
    (item) => item.purpose.allows_capability_goal
      || item.purpose.allows_unlinked,
  );
  const [selectedPurposeKey, setSelectedPurposeKey] = useState('');
  const [selectedPurposeTouched, setSelectedPurposeTouched] = useState(false);
  const [, selectedCapabilityId = ''] = selectedPurposeKey.split(':', 2);
  const selectedPurposeSource = selectedPurposeKey.split(':', 1)[0] as PurposeOptionSource | '';
  const capability = supportedCapabilities.find(
    (item) => item.id === selectedCapabilityId,
  ) ?? null;
  const purposeSelection = useMemo<PlanGenerationPurposeSelection | null>(() => {
    if (!capability || !selectedPurposeSource) return null;
    if (selectedPurposeSource === 'current_goal') {
      const currentGoal = capabilityDiscovery?.current_goal;
      if (!currentGoal || currentCapability?.id !== capability.id) return null;
      return {
        capability_id: capability.id,
        source: 'current_goal',
        expected_goal_id: currentGoal.id,
        expected_goal_revision: currentGoal.revision,
      };
    }
    if (
      selectedPurposeSource === 'capability'
      && !capability.purpose.allows_capability_goal
    ) return null;
    if (
      selectedPurposeSource === 'unlinked'
      && !capability.purpose.allows_unlinked
    ) return null;
    return {
      capability_id: capability.id,
      source: selectedPurposeSource,
      expected_goal_id: null,
      expected_goal_revision: null,
    };
  }, [
    capability,
    capabilityDiscovery?.current_goal,
    currentCapability?.id,
    selectedPurposeSource,
  ]);
  const usesCurrentGoal = purposeSelection?.source === 'current_goal';
  const {
    data: goal,
    loading: goalLoading,
    error: goalError,
    refetch: refetchGoal,
  } = useApi<GoalResponse>(
    '/api/goal',
    { timeoutMs: 12_000, enabled: Boolean(usesCurrentGoal && capability) },
  );
  const {
    data: currentProposal,
    error: currentProposalError,
    errorCode: currentProposalErrorCode,
    refetch: refetchProposal,
  } = useApi<AdaptivePlanProposal>(
    '/api/plan/proposals/current',
    { timeoutMs: 12_000 },
  );

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
  const [working, setWorking] = useState<PlanStartWorkingState | null>(null);
  const [error, setError] = useState<PlanStartErrorState | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const idempotencyKeys = useRef<Partial<Record<LifecycleOperation, string>>>({});

  useEffect(() => {
    if (selectedPurposeTouched || !capabilityDiscovery) return;
    const existingPurposeKey = proposalPurposeKey(currentProposal ?? null);
    const [
      existingPurposeSource = '',
      existingCapabilityId = '',
    ] = (existingPurposeKey ?? '').split(':', 2);
    const existingCapability = supportedCapabilities.find(
      (item) => item.id === existingCapabilityId,
    );
    const existingPurposeSelectable = (
      existingPurposeSource === 'current_goal'
        ? Boolean(
          currentCapability?.id === existingCapabilityId
          && capabilityDiscovery.current_goal,
        )
        : existingPurposeSource === 'capability'
          ? Boolean(existingCapability?.purpose.allows_capability_goal)
          : existingPurposeSource === 'unlinked'
            ? Boolean(existingCapability?.purpose.allows_unlinked)
            : false
    );
    if (
      existingPurposeKey
      && existingPurposeSelectable
    ) {
      setSelectedPurposeKey(existingPurposeKey);
      return;
    }
    if (currentCapability && capabilityDiscovery.current_goal) {
      setSelectedPurposeKey(
        purposeKey('current_goal', currentCapability.id),
      );
    }
  }, [
    capabilityDiscovery,
    currentCapability,
    currentProposal,
    selectedPurposeTouched,
    supportedCapabilities,
  ]);

  const selectedLocalProposal = proposal;
  const noCurrentProposal = currentProposalErrorCode === 'PLAN_PROPOSAL_NOT_FOUND';
  const selectedCurrentProposal = noCurrentProposal
    ? null
    : currentProposal;
  const policyProposal = selectedLocalProposal ?? selectedCurrentProposal;
  const policyProposalPurposeKey = proposalPurposeKey(policyProposal);
  const [
    policyProposalPurposeSource = '',
    policyProposalCapabilityId = '',
  ] = (policyProposalPurposeKey ?? '').split(':', 2);
  const policyProposalCapability = supportedCapabilities.find(
    (item) => item.id === policyProposalCapabilityId,
  );
  const recognizedLegacyCurrentGoalProposal = Boolean(
    policyProposal
    && policyProposalPurposeKey == null
    && policyProposal.policy_version === 'outdoor-5k-plan-generation-policy-v1'
    && supportedCapabilities.some(
      (item) => item.policy_version === policyProposal.policy_version,
    ),
  );
  const activeProposal = (
    policyProposal
    && (
      policyProposalPurposeKey === selectedPurposeKey
      || (
        recognizedLegacyCurrentGoalProposal
        && selectedPurposeSource === 'current_goal'
      )
    )
      ? policyProposal
      : null
  );
  const conflictingProposal = policyProposal && !activeProposal
    ? policyProposal
    : null;
  const displayedProposal = activeProposal ?? conflictingProposal;
  const canSelectPolicyProposalPurpose = (
    policyProposalPurposeSource === 'current_goal'
      ? Boolean(
        currentCapability?.id === policyProposalCapabilityId
        && capabilityDiscovery?.current_goal,
      )
      : policyProposalPurposeSource === 'capability'
        ? Boolean(policyProposalCapability?.purpose.allows_capability_goal)
        : policyProposalPurposeSource === 'unlinked'
          ? Boolean(policyProposalCapability?.purpose.allows_unlinked)
          : false
  );
  const proposalPurposeConflict = Boolean(
    displayedProposal
    && (
      !activeProposal
      || (
        policyProposalPurposeKey != null
        && !canSelectPolicyProposalPurpose
      )
    ),
  );
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
  const formError = !purposeSelection
    ? t`Choose an accepted plan purpose first.`
    : !scopeComplete
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
  const selectedPurposeLabel = !purposeSelection
    ? null
    : purposeSelection.source === 'current_goal'
      ? t`Current Goal · ${capabilityDiscovery?.current_goal?.goal.distance?.toUpperCase() ?? '5K'}`
      : purposeSelection.source === 'capability'
        ? t`Separate ${capability?.purpose.distance?.toUpperCase() ?? 'running'} plan purpose`
        : t`Unlinked ${capability?.purpose.distance?.toUpperCase() ?? 'running'} base plan`;
  const preferredLongestDayLabel = preferredLongestDay === ''
    ? t`No preference`
    : dayName(Number(preferredLongestDay) as Outdoor5KWeekday);
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
  const selectPurpose = (value: string | null) => {
    if (working != null) return;
    setSelectedPurposeTouched(true);
    setSelectedPurposeKey(value ?? '');
    setReadiness(null);
    setError(null);
    setNotice(null);
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
    if (!purposeSelection || formError || sharedDuration == null) {
      setError({
        message: formError ?? t`Review the constraints and try again.`,
      });
      return null;
    }
    return {
      purpose: purposeSelection,
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
    const activeCapability = capability;
    const body = constraints();
    if (!body || !activeCapability) return null;
    setWorking('readiness');
    setError(null);
    setNotice(null);
    try {
      const response = await apiFetch(activeCapability.actions.readiness_href, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const value = await planStartResponse<Outdoor5KReadinessResponse>(
        response,
        t`Could not assess this plan start.`,
      );
      setReadiness(value);
      return value;
    } catch (requestError) {
      setError(planStartError(
        requestError,
        t`Could not assess this plan start.`,
      ));
      return null;
    } finally {
      setWorking(null);
    }
  };

  const generate = async () => {
    const activeCapability = capability;
    const checked = await requestReadiness();
    const body = constraints();
    if (
      !checked
      || !body
      || !activeCapability
      || checked.result.code !== 'ready'
    ) return;
    setWorking('generate');
    setError(null);
    try {
      const response = await apiFetch(activeCapability.actions.generate_href, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...body,
          expected_source_revision: checked.source_revision,
          idempotency_key: operationKey('generate'),
        }),
      });
      const value = await planStartResponse<Outdoor5KGenerateResponse>(
        response,
        t`Could not create the proposal.`,
      );
      if (isProposalResponse(value) && value.proposal) {
        setProposal(value.proposal);
        setNotice(t`Proposal created. It has not changed your canonical plan.`);
        void refetchProposal();
        void refetchCapabilities();
      } else {
        setReadiness(value);
      }
      clearOperationKey('generate');
    } catch (requestError) {
      setError(planStartError(
        requestError,
        t`Could not create the proposal.`,
      ));
    } finally {
      setWorking(null);
    }
  };

  const regenerate = async () => {
    const activeCapability = capability;
    if (!activeProposal || !activeCapability) return;
    const checked = await requestReadiness();
    const body = constraints();
    if (!checked || !body || checked.result.code !== 'ready') return;
    setWorking('regenerate');
    setError(null);
    try {
      const response = await apiFetch(
        proposalActionHref(
          activeCapability.actions.regenerate_href_template,
          activeProposal.id,
        ),
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
      const value = await planStartResponse<Outdoor5KRegenerateResponse>(
        response,
        t`Could not regenerate the proposal.`,
      );
      if (isProposalResponse(value) && value.proposal) {
        setProposal(value.proposal);
        setNotice(t`A successor proposal is ready. The earlier proposal is preserved as superseded.`);
        void refetchProposal();
        void refetchCapabilities();
      } else {
        setReadiness(value);
      }
      clearOperationKey('regenerate');
    } catch (requestError) {
      setError(planStartError(
        requestError,
        t`Could not regenerate the proposal.`,
      ));
    } finally {
      setWorking(null);
    }
  };

  const reject = async () => {
    if (!displayedProposal) return;
    setWorking('reject');
    setError(null);
    try {
      const response = await apiFetch(
        `/api/plan/proposals/${encodeURIComponent(displayedProposal.id)}/reject`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            expected_version: displayedProposal.version,
            idempotency_key: operationKey('reject'),
          }),
        },
      );
      await planStartResponse<AdaptivePlanProposal>(
        response,
        t`Could not reject the proposal.`,
      );
      setNotice(t`Proposal rejected. Your canonical plan was not changed.`);
      clearOperationKey('reject');
      await Promise.all([
        refetchProposal(),
        refetchCapabilities(),
      ]);
      setProposal(null);
    } catch (requestError) {
      setError(planStartError(
        requestError,
        t`Could not reject the proposal.`,
      ));
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
      const value = await planStartResponse<AdaptivePlanProposalAdoptResponse>(
        response,
        t`Could not adopt the proposal.`,
      );
      setProposal(value.proposal);
      setNotice(value.status === 'already_adopted'
        ? t`This exact proposal was already adopted. Delivery remains disabled until you explicitly enable it.`
        : t`Plan adopted. Delivery remains disabled until you explicitly enable it.`);
      clearOperationKey('adopt');
      void refetchProposal();
      void refetchCapabilities();
    } catch (requestError) {
      setError(planStartError(
        requestError,
        t`Could not adopt the proposal.`,
      ));
    } finally {
      setWorking(null);
    }
  };

  const refreshPlanContext = async () => {
    const goalIsRelevant = usesCurrentGoal
      || displayedProposal?.goal?.purpose_source === 'current_goal';
    setWorking('refresh');
    setError(null);
    setReadiness(null);
    setProposal(null);
    try {
      await Promise.all([
        refetchCapabilities(),
        refetchProposal(),
        ...(goalIsRelevant ? [refetchGoal()] : []),
      ]);
    } finally {
      setWorking(null);
    }
  };
  const proposalRecoveryCard = displayedProposal ? (
    <div className="space-y-4">
      <ProposalRecoveryCard
        proposal={displayedProposal}
        isDemo={isDemo}
        rejecting={working === 'reject'}
        onReject={() => void reject()}
      />
      {notice && <p className="text-sm text-primary" role="status">{notice}</p>}
      {error && (
        <Alert variant="destructive">
          <AlertTitle><Trans>Plan-start action did not complete</Trans></AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
    </div>
  ) : null;

  if (settingsLoading || capabilityLoading) return <PlanStartSkeleton />;

  if (settingsError || capabilityError) {
    return (
      <section className="space-y-6">
        <Alert id="plan-start" variant="destructive">
          <AlertTitle><Trans>Could not load plan-start context</Trans></AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>{settingsError ?? capabilityError}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetchSettings();
                void refetchCapabilities();
              }}
            >
              <Trans>Retry</Trans>
            </Button>
          </AlertDescription>
        </Alert>
        {proposalRecoveryCard}
      </section>
    );
  }

  if (!config) return proposalRecoveryCard ?? <PlanStartSkeleton />;

  if (!hasSelectablePurpose) {
    if (
      supportedCapabilities.length === 0
      && (capabilityDiscovery?.capabilities.length ?? 0) > 0
    ) {
      return (
        <section className="space-y-6">
          <Alert id="plan-start" variant="destructive">
            <AlertTitle><Trans>Update required for this plan policy</Trans></AlertTitle>
            <AlertDescription>
              <Trans>
                This client does not recognize the accepted policy input contract and will not guess how to create a plan.
              </Trans>
            </AlertDescription>
          </Alert>
          {proposalRecoveryCard}
        </section>
      );
    }
    return (
      <section className="space-y-6">
        <Card id="plan-start">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle><Trans>Plan generation for this goal</Trans></CardTitle>
                <CardDescription className="mt-2">
                  <Trans>
                    No accepted automatic policy matches this goal yet. Praxys keeps manual plan management available instead of repurposing the 5K policy.
                  </Trans>
                </CardDescription>
              </div>
              <Badge variant="outline"><Trans>No accepted policy</Trans></Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">
              <Trans>
                Road and trail policies are exposed here only after their population, goal, and safety boundaries are reviewed and versioned.
              </Trans>
            </p>
            <p className="text-sm text-muted-foreground">
              <Trans>Current goal:</Trans>{' '}
              <span className="font-data">
                {capabilityDiscovery?.goal.goal_kind?.replace(/_/g, ' ') ?? '—'}
                {capabilityDiscovery?.goal.distance
                  ? ` · ${capabilityDiscovery.goal.distance.toUpperCase()}`
                  : ''}
              </span>
            </p>
            <Button variant="outline" onClick={() => navigate('/goal')}>
              <Trans>Review goal</Trans>
            </Button>
          </CardContent>
        </Card>
        {proposalRecoveryCard}
      </section>
    );
  }

  if (usesCurrentGoal && goalError) {
    return (
      <section className="space-y-6">
        <Alert id="plan-start" variant="destructive">
          <AlertTitle><Trans>Could not load plan-start context</Trans></AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>{goalError}</span>
            <Button variant="outline" size="sm" onClick={() => void refetchGoal()}>
              <Trans>Retry</Trans>
            </Button>
          </AlertDescription>
        </Alert>
        {proposalRecoveryCard}
      </section>
    );
  }

  if (usesCurrentGoal && (goalLoading || !goal)) {
    return proposalRecoveryCard ?? <PlanStartSkeleton />;
  }

  if (
    usesCurrentGoal
    && goal
    && (
      !currentCapability
      || goal.goal_kind !== capabilityDiscovery?.goal.goal_kind
      || (goal.goal?.distance ?? null) !== capabilityDiscovery?.goal.distance
    )
  ) {
    return (
      <section className="space-y-6">
        <Card id="plan-start">
          <CardHeader>
            <CardTitle><Trans>Plan-start context changed</Trans></CardTitle>
            <CardDescription>
              <Trans>The goal response and capability response no longer agree. Refresh before creating a proposal.</Trans>
            </CardDescription>
          </CardHeader>
          <CardContent className="border-t border-border pt-4">
            <Button
              variant="outline"
              onClick={() => {
                void refetchGoal();
                void refetchCapabilities();
              }}
            >
              <Trans>Refresh plan context</Trans>
            </Button>
          </CardContent>
        </Card>
        {proposalRecoveryCard}
      </section>
    );
  }

  const displayCapability = capability ?? currentCapability ?? supportedCapabilities[0]!;
  const baseline = usesCurrentGoal
    ? goal?.baseline
    : readiness && 'baseline' in readiness
      ? readiness.baseline
      : undefined;
  const result = readiness?.result;
  const isDraft = displayedProposal?.state === 'draft';
  const isAdopted = displayedProposal?.state === 'adopted';
  const hasLifecycleState = displayedProposal && !isDraft && !isAdopted;
  const proposalNeedsReassessment = Boolean(
    isDraft
    && displayedProposal?.goal?.purpose_source === 'current_goal'
    && capabilityDiscovery?.active_plan_goal?.link_status
      === 'reassessment_required',
  );
  const baselineBadge = baseline
    ? baselineCopy(baseline, t`Baseline ready`, t`Baseline needs review`)
    : t`Readiness not checked`;

  return (
    <section id="plan-start" aria-labelledby="plan-start-title" className="scroll-mt-6 space-y-5">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-2xl">
              <CardTitle id="plan-start-title"><Trans>Plan preview</Trans></CardTitle>
              <CardDescription className="mt-2">
                <Trans>
                  Choose what this plan is for, then set constraints you can actually keep. Praxys returns a versioned <span className="font-data">{displayCapability.horizon_days}</span>-day proposal; it is not yet your plan.
                </Trans>
              </CardDescription>
            </div>
            <Badge variant={baseline?.readiness === 'sufficient_baseline' ? 'default' : 'outline'}>
              {baselineBadge}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 border-t border-border pt-5">
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold"><Trans>Plan purpose</Trans></h3>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                <Trans>
                  The current Goal is the default when an accepted policy matches it. A separate purpose keeps that Goal unchanged.
                </Trans>
              </p>
            </div>
            <Select
              value={selectedPurposeKey || undefined}
              onValueChange={selectPurpose}
              disabled={working != null}
            >
              <SelectTrigger aria-label={t`Plan purpose`}>
                <SelectValue placeholder={t`Choose an accepted plan purpose`}>
                  {selectedPurposeLabel}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {currentCapability && capabilityDiscovery?.current_goal && (
                  <SelectItem value={purposeKey('current_goal', currentCapability.id)}>
                    {t`Current Goal · ${capabilityDiscovery.current_goal.goal.distance?.toUpperCase() ?? '5K'}`}
                  </SelectItem>
                )}
                {supportedCapabilities.map((item) => (
                  item.purpose.allows_capability_goal ? (
                    <SelectItem
                      key={purposeKey('capability', item.id)}
                      value={purposeKey('capability', item.id)}
                    >
                      {t`Separate ${item.purpose.distance?.toUpperCase() ?? 'running'} plan purpose`}
                    </SelectItem>
                  ) : null
                ))}
                {supportedCapabilities.map((item) => (
                  item.purpose.allows_unlinked ? (
                    <SelectItem
                      key={purposeKey('unlinked', item.id)}
                      value={purposeKey('unlinked', item.id)}
                    >
                      {t`Unlinked ${item.purpose.distance?.toUpperCase() ?? 'running'} base plan`}
                    </SelectItem>
                  ) : null
                ))}
              </SelectContent>
            </Select>
          </div>

          {!currentCapability && capabilityDiscovery?.current_goal && (
            <Alert>
              <AlertTitle><Trans>Current Goal has no accepted automatic policy</Trans></AlertTitle>
              <AlertDescription>
                <Trans>
                  Keep the current {capabilityDiscovery.current_goal.goal.distance?.toUpperCase() ?? 'goal'} unchanged, or choose an accepted separate purpose above.
                </Trans>
              </AlertDescription>
            </Alert>
          )}

          {purposeSelection?.source === 'capability' && (
            <Alert>
              <AlertTitle><Trans>Separate from the current Goal</Trans></AlertTitle>
              <AlertDescription>
                <Trans>
                  This proposal uses the accepted {capability?.purpose.distance?.toUpperCase() ?? '5K'} goal contract without changing or linking to the Goal page.
                </Trans>
              </AlertDescription>
            </Alert>
          )}

          {capabilityDiscovery?.active_plan_goal?.link_status === 'reassessment_required' && (
            <Alert variant="destructive">
              <AlertTitle><Trans>Plan purpose needs reassessment</Trans></AlertTitle>
              <AlertDescription>
                <Trans>
                  The current Goal changed after this plan purpose was captured. Check readiness again and create a fresh proposal before adoption.
                </Trans>
              </AlertDescription>
            </Alert>
          )}

          {conflictingProposal && canSelectPolicyProposalPurpose && (
            <Alert>
              <AlertTitle><Trans>A draft exists for another plan purpose</Trans></AlertTitle>
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                <span>
                  <Trans>Return to that purpose to review or reject it before creating a different draft.</Trans>
                </span>
                {policyProposalPurposeKey && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => selectPurpose(policyProposalPurposeKey)}
                  >
                    <Trans>Review existing draft</Trans>
                  </Button>
                )}
              </AlertDescription>
            </Alert>
          )}

          <fieldset
            disabled={!purposeSelection}
            className="min-w-0 space-y-6 border-0 p-0 disabled:opacity-60"
          >
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
                <SelectTrigger id="outdoor-5k-long-day">
                  <SelectValue placeholder={t`No preference`}>
                    {preferredLongestDayLabel}
                  </SelectValue>
                </SelectTrigger>
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
            <Button disabled={isDemo || working != null || !purposeSelection} onClick={() => void requestReadiness()} className="min-h-11">
              {working === 'readiness' ? <Trans>Checking readiness…</Trans> : <Trans>Check readiness</Trans>}
            </Button>
            {result?.code === 'ready' && !activeProposal && !conflictingProposal && (
              <Button variant="outline" disabled={isDemo || working != null} onClick={() => void generate()} className="min-h-11">
                {working === 'generate' ? <Trans>Creating proposal…</Trans> : <Trans>Create proposal</Trans>}
              </Button>
            )}
          </div>
          </fieldset>
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

      {result?.code === 'insufficient_or_stale_baseline'
        && readiness
        && 'baseline' in readiness
        && purposeSelection && (
        <GoalBaselinePanel
          baseline={readiness.baseline}
          goal={readiness.purpose.goal}
          purpose={purposeSelection}
          isDemo={isDemo}
          onChanged={() => {
            if (usesCurrentGoal) void refetchGoal();
            void requestReadiness();
          }}
        />
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

      {displayedProposal && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle><Trans>Plan proposal</Trans></CardTitle>
                <CardDescription className="mt-2">
                  <Trans>This proposal is not yet your plan. It cannot deliver workouts until after explicit adoption and separate delivery consent.</Trans>
                </CardDescription>
              </div>
              <Badge variant={isAdopted ? 'default' : 'outline'}>{proposalStateLabel(displayedProposal.state)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 border-t border-border pt-4">
            <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-muted-foreground"><Trans>Purpose</Trans></dt>
                <dd className="mt-1">
                  {displayedProposal.goal?.purpose_source === 'current_goal'
                    ? <Trans>Linked to current Goal</Trans>
                    : displayedProposal.goal?.purpose_source === 'capability'
                      ? <Trans>Separate plan purpose</Trans>
                      : displayedProposal.goal?.purpose_source === 'unlinked'
                        ? <Trans>Unlinked plan</Trans>
                        : <Trans>Legacy purpose</Trans>}
                </dd>
              </div>
              <div><dt className="text-muted-foreground"><Trans>Policy</Trans></dt><dd className="mt-1 font-data">{displayedProposal.policy_version ?? '—'}</dd></div>
              <div><dt className="text-muted-foreground"><Trans>Generator</Trans></dt><dd className="mt-1 font-data">{displayedProposal.model_version ?? '—'}</dd></div>
              <div><dt className="text-muted-foreground"><Trans>Science decision</Trans></dt><dd className="mt-1 font-data">{displayedProposal.science_version ?? '—'}</dd></div>
            </dl>
            <div className="divide-y divide-border border-y border-border">
              {displayedProposal.workouts.map((workout) => (
                <div key={`${workout.date}-${workout.workout_type}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3 text-sm">
                  <span><span className="font-data">{workout.date}</span> · {workout.workout_type.replace(/_/g, ' ')}</span>
                  <span className="font-data text-muted-foreground">{workout.planned_duration_min ?? '—'} min</span>
                </div>
              ))}
            </div>
            {!proposalPurposeConflict && (
              <p className="text-sm text-muted-foreground">
                <Trans>
                  Workout content is view-only in this deterministic policy. Change the bounded inputs above and regenerate to create an immutable successor; Praxys never constructs replacement workouts in this client.
                </Trans>
              </p>
            )}
            {[displayedProposal.assumptions, displayedProposal.unknowns, displayedProposal.warnings, displayedProposal.alternatives]
              .filter((items) => items.length > 0)
              .map((items, index) => (
                <p key={index} className="text-sm text-muted-foreground">{items.map(formatProposalDetail).join(' · ')}</p>
              ))}
            {displayedProposal.expires_at && (
              <p className="text-sm text-muted-foreground"><Trans>Expires:</Trans> <span className="font-data">{displayedProposal.expires_at}</span></p>
            )}

            {proposalNeedsReassessment && (
              <Alert variant="destructive">
                <AlertTitle><Trans>Adoption is paused</Trans></AlertTitle>
                <AlertDescription>
                  <Trans>The linked Goal changed. Recheck readiness and regenerate this proposal before adopting it.</Trans>
                </AlertDescription>
              </Alert>
            )}

            {isDraft && (
              <div className="flex flex-wrap gap-2">
                {!proposalPurposeConflict && (
                  <>
                    <Button disabled={isDemo || working != null || proposalNeedsReassessment} onClick={() => void adopt()} className="min-h-11">
                      {working === 'adopt' ? <Trans>Adopting…</Trans> : <Trans>Adopt exact proposal</Trans>}
                    </Button>
                    <Button variant="outline" disabled={isDemo || working != null} onClick={() => void regenerate()} className="min-h-11">
                      <RefreshCw aria-hidden="true" />
                      {working === 'regenerate' ? <Trans>Regenerating…</Trans> : <Trans>Regenerate successor</Trans>}
                    </Button>
                  </>
                )}
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
                    This proposal is {proposalStateLabel(displayedProposal.state)}. It cannot mutate the canonical plan; review readiness and create a new proposal when you are ready.
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
            <span>{error.message}</span>
            {needsPlanContextRecovery(error) && (
              <Button
                size="sm"
                variant="outline"
                disabled={working != null}
                onClick={() => void refreshPlanContext()}
              >
                <Trans>Refresh plan context</Trans>
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}
    </section>
  );
}
