import { useEffect, useMemo, useRef, useState } from 'react';
import { Trans, useLingui } from '@lingui/react/macro';
import { CalendarDays, ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import ManagedPlanSettingsCard from '@/components/ManagedPlanSettingsCard';
import AdoptedPlanDetails from '@/components/AdoptedPlanDetails';
import GoalBaselinePanel from '@/components/GoalBaselinePanel';
import ScienceNote from '@/components/ScienceNote';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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
import {
  ToggleGroup,
  ToggleGroupItem,
} from '@/components/ui/toggle-group';
import { useLocale } from '@/contexts/LocaleContext';
import { useAuth } from '@/hooks/useAuth';
import { apiFetch, useApi } from '@/hooks/useApi';
import { useSettings } from '@/contexts/SettingsContext';
import { extractApiError } from '@/lib/api-error';
import { tDisplay } from '@/lib/display-labels';
import { formatProposalDetail } from '@/lib/proposal-display';
import { shouldRetryCurrentPlanProposal } from '@/lib/plan-proposal-query';
import type {
  AdaptivePlanProposal,
  AdaptivePlanProposalAdoptResponse,
  GoalBaselineResponse,
  GoalResponse,
  Outdoor5KConstraintsRequest,
  Outdoor5KGenerateResponse,
  Outdoor5KOutcomeResponse,
  Outdoor5KProposalResponse,
  Outdoor5KReadinessResponse,
  Outdoor5KRegenerateResponse,
  Outdoor5KWeekday,
  PlanGenerationCapabilitiesResponse,
  PlanGenerationCapability,
  PlanIntent,
  PlanGenerationPurposeSelection,
  PlanRoutingOption,
  Road10KBaselineResponse,
  Road10KConstraintsRequest,
  Road10KGenerateResponse,
  Road10KOutcomeResponse,
  Road10KProposalResponse,
  Road10KReadinessResponse,
  Road10KRegenerateResponse,
} from '@/types/api';

const DAYS: Outdoor5KWeekday[] = [0, 1, 2, 3, 4, 5, 6];
const SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_IDS = new Set([
  'outdoor_road_5k_constraints_v1',
  'outdoor_road_10k_constraints_v1',
]);

type LifecycleOperation = 'generate' | 'regenerate' | 'reject' | 'adopt';
type PurposeOptionSource = PlanGenerationPurposeSelection['source'];
type PlanStartWorkingState = LifecycleOperation | 'readiness' | 'refresh';
type SetupStep = 'intent' | 'purpose' | 'constraints';

interface PlanStartErrorState {
  message: string;
  status?: number;
  code?: string;
}

interface PlanStartRequestError extends Error {
  status: number;
  code?: string;
}

export interface PlanStartNavigationState {
  planPurpose: PlanGenerationPurposeSelection;
}

interface PlanStartProps {
  initialPurpose?: PlanGenerationPurposeSelection | null;
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
  value:
    | Outdoor5KGenerateResponse
    | Outdoor5KRegenerateResponse
    | Road10KGenerateResponse
    | Road10KRegenerateResponse,
): value is Outdoor5KProposalResponse | Road10KProposalResponse {
  return 'proposal' in value;
}

function outcomeCopy(
  result: Outdoor5KOutcomeResponse | Road10KOutcomeResponse,
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
  baseline: GoalBaselineResponse | Road10KBaselineResponse | undefined,
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
  const capabilityId = proposal?.goal?.goal_kind === 'performance_5k'
    ? 'outdoor_road_5k_v1'
    : proposal?.goal?.goal_kind === 'performance_10k'
      ? 'outdoor_road_10k_performance_v1'
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

function isRoad10KCapabilitySchema(schemaId: string | null | undefined): boolean {
  return schemaId === 'outdoor_road_10k_constraints_v1';
}

function isPlanReadyResult(
  result: Outdoor5KOutcomeResponse | Road10KOutcomeResponse,
): boolean {
  if ('plan_returned' in result) {
    return result.route_state === 'plan_candidate' && result.plan_returned;
  }
  return result.code === 'ready';
}

function needsBaselineReview(
  result: Outdoor5KOutcomeResponse | Road10KOutcomeResponse,
): boolean {
  return result.code === 'insufficient_or_stale_baseline'
    || result.code === 'missing_or_stale_direct_baseline';
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

export function PlanStartGoalEntry() {
  return (
    <section id="plan-routing" className="mt-8 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="text-sm font-semibold"><Trans>Training plan</Trans></h2>
        <p className="mt-1 text-sm text-muted-foreground">
          <Trans>Plan setup and management are in Training.</Trans>
        </p>
      </div>
      <Button
        variant="ghost"
        className="min-h-11 self-start sm:self-auto"
        nativeButton={false}
        render={<Link to="/training#plan-start" />}
      >
        <Trans>Open Training</Trans>
        <ChevronRight aria-hidden="true" />
      </Button>
    </section>
  );
}

function PlanIntentChooser({
  onSelect,
  onChoosePurpose,
}: {
  onSelect: (purpose: PlanGenerationPurposeSelection) => void;
  onChoosePurpose: () => void;
}) {
  const { t } = useLingui();
  const [intentSelection, setIntentSelection] = useState<{
    goalRevision: string | null;
    intent: PlanIntent;
  } | null>(null);
  const {
    data: discovery,
    loading,
    error,
    refetch,
  } = useApi<PlanGenerationCapabilitiesResponse>(
    '/api/plan/generation/capabilities',
    { timeoutMs: 12_000 },
  );
  const routing = discovery?.routing ?? null;
  const currentGoalRevision = discovery?.current_goal?.revision ?? null;
  const selectedIntent = intentSelection?.goalRevision === currentGoalRevision
    ? intentSelection.intent
    : null;
  const effectiveIntent = selectedIntent ?? routing?.intent ?? null;
  const selectedRoute = useMemo<
    PlanRoutingOption | PlanGenerationCapabilitiesResponse['routing'] | null
  >(() => {
    if (!routing) return null;
    if (!selectedIntent) return routing;
    return routing.options.find(
      (option) => option.intent === selectedIntent,
    ) ?? null;
  }, [routing, selectedIntent]);
  const routedCapability = discovery?.capabilities.find(
    (item) => item.id === selectedRoute?.capability_id,
  ) ?? null;
  const routedPurpose = useMemo<PlanGenerationPurposeSelection | null>(() => {
    if (!selectedRoute?.capability_id || !selectedRoute.purpose_source) {
      return null;
    }
    if (
      selectedRoute.purpose_source === 'current_goal'
      && !discovery?.current_goal
    ) {
      return null;
    }
    return {
      capability_id: selectedRoute.capability_id,
      source: selectedRoute.purpose_source,
      expected_goal_id: selectedRoute.purpose_source === 'current_goal'
        ? discovery?.current_goal?.id ?? null
        : null,
      expected_goal_revision: selectedRoute.purpose_source === 'current_goal'
        ? discovery?.current_goal?.revision ?? null
        : null,
    };
  }, [discovery?.current_goal, selectedRoute]);
  const capabilityUpdateRequired = routedCapability != null
    && !SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_IDS.has(
      routedCapability.constraint_schema_id,
    );
  const intentOptions: Array<{
    intent: PlanIntent;
    label: string;
    description: string;
  }> = [
    {
      intent: 'first_completion',
      label: t`Finish this distance`,
      description: t`Prepare to complete the selected distance.`,
    },
    {
      intent: 'performance',
      label: t`Improve performance`,
      description: t`Use current evidence to work toward a faster result.`,
    },
    {
      intent: 'return_to_consistency',
      label: t`Rebuild consistency`,
      description: t`Return to regular training without guessing what missing records mean.`,
    },
  ];
  const routeCopy = (() => {
    if (error) {
      return {
        badge: t`Could not load plans`,
        description: t`Available training plans could not be loaded.`,
        detail: t`Retry before choosing a training plan.`,
      };
    }
    if (capabilityUpdateRequired) {
      return {
        badge: t`Update required`,
        description: t`This training plan needs a newer version of Praxys.`,
        detail: t`Update Praxys before continuing with this plan.`,
      };
    }
    switch (selectedRoute?.state) {
      case 'plan_candidate':
        return {
          badge: t`Available`,
          description: t`A training plan is available for this direction and distance.`,
          detail: selectedRoute.purpose_source !== 'current_goal'
            ? discovery?.current_goal
              ? t`Your current Goal stays unchanged. Confirm applicability and availability before generating a proposal.`
              : t`Confirm applicability and availability before generating a proposal.`
            : t`Continue with your current Goal, then confirm applicability and availability.`,
        };
      case 'readiness_only':
        return {
          badge: t`Readiness first`,
          description: t`This direction is supported, but the available training evidence needs review first.`,
          detail: selectedRoute.purpose_source !== 'current_goal'
            ? discovery?.current_goal
              ? t`Review readiness without changing your current Goal.`
              : t`Review readiness before generating a proposal.`
            : t`Review readiness for your current Goal before generating a proposal.`,
        };
      case 'policy_unavailable':
        return {
          badge: t`Not supported yet`,
          description: t`Automatic plans are not yet available for this training direction and distance.`,
          detail: t`You can view the available training plans or keep managing your current workouts.`,
        };
      case 'clarification_required':
      default:
        return {
          badge: t`Choose a direction`,
          description: t`Choose what you want to work toward.`,
          detail: t`This selects a training direction, not a plan. Praxys will show whether it is supported.`,
        };
    }
  })();
  const badgeVariant = error || capabilityUpdateRequired
    ? 'destructive'
    : selectedRoute?.state === 'plan_candidate'
      ? 'default'
      : 'outline';
  const openSelectedRoute = () => {
    if (!routedPurpose) return;
    onSelect(routedPurpose);
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="mt-3 h-4 w-full max-w-xl" />
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card id="plan-intent-choice">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <CardTitle id="plan-intent-title" tabIndex={-1}><Trans>What should this plan help you do?</Trans></CardTitle>
            <CardDescription className="mt-2">
              {routeCopy.description}
            </CardDescription>
          </div>
          <Badge variant={badgeVariant}>
            {routeCopy.badge}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 border-t border-border pt-4">
        {!error && routing && (
          <div className="space-y-3">
            <ToggleGroup
              spacing={2}
              value={effectiveIntent ? [effectiveIntent] : []}
              onValueChange={(values) => {
                if (values.length > 0) {
                  setIntentSelection({
                    goalRevision: currentGoalRevision,
                    intent: values[values.length - 1] as PlanIntent,
                  });
                }
              }}
              className="grid grid-cols-1 gap-2 sm:grid-cols-3"
              aria-label={t`Plan intent`}
            >
              {intentOptions.map((option) => (
                <ToggleGroupItem
                  key={option.intent}
                  value={option.intent}
                  className="h-auto min-h-20 min-w-0 w-full whitespace-normal border border-border flex-col items-start gap-1 px-4 py-3 text-left aria-pressed:border-primary aria-pressed:bg-primary/10"
                >
                  <span className="w-full text-sm font-semibold">{option.label}</span>
                  <span className="w-full text-xs leading-relaxed text-muted-foreground">
                  {option.description}
                  </span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
        )}

        <div className="border-t border-border pt-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
              {routeCopy.detail}
            </p>
            {error ? (
              <Button variant="outline" onClick={() => void refetch()} className="min-h-11 shrink-0">
                <Trans>Retry</Trans>
              </Button>
            ) : capabilityUpdateRequired ? null : selectedRoute?.state === 'plan_candidate' && routedPurpose ? (
              <Button
                onClick={openSelectedRoute}
                className="min-h-11 shrink-0"
              >
                <Trans>Continue setup</Trans>
                <ChevronRight aria-hidden="true" />
              </Button>
            ) : selectedRoute?.state === 'readiness_only' && routedPurpose ? (
              <Button
                onClick={openSelectedRoute}
                className="min-h-11 shrink-0"
              >
                <Trans>Review readiness</Trans>
                <ChevronRight aria-hidden="true" />
              </Button>
            ) : null}
          </div>
          {!error && routing && (
            <ScienceNote label={<Trans>Applicability and evidence</Trans>}>
              <p>
                <Trans>
                  First completion, performance improvement, and return to regular running have different evidence. Sparse records do not establish that someone stopped training or lost fitness; existing evidence does not establish one beginner or return-to-running schedule for everyone. This concerns nonclinical training for adults, not fixed labels for runners.
                </Trans>
              </p>
              <details className="mt-2">
                <summary className="min-h-11 cursor-pointer py-3 font-medium">
                  <Trans>References</Trans>
                </summary>
                <dl className="space-y-3">
                  {[
                    {
                      claim: t`Evidence differs between running populations`,
                      sources: [
                        ['Videbaek et al. (2015)', '10.1007/s40279-015-0333-8'],
                        ['Fredette et al. (2022)', '10.4085/1062-6050-0195.21'],
                      ],
                    },
                    {
                      claim: t`Limits of a universal beginner schedule`,
                      sources: [
                        ['Fredette et al. (2022)', '10.4085/1062-6050-0195.21'],
                        ['Buist et al. (2008)', '10.1177/0363546507307505'],
                        ['Ramskov et al. (2018)', '10.1136/bmjsem-2017-000333'],
                        ['Relph et al. (2023)', '10.3390/ijerph20176682'],
                      ],
                    },
                    {
                      claim: t`Limits of inferring a return to training from sparse records`,
                      sources: [
                        ['Zheng et al. (2022)', '10.1155/2022/2130993'],
                        ['Barbieri et al. (2023)', '10.3389/fphys.2023.1334766'],
                      ],
                    },
                  ].map(({ claim, sources }) => (
                    <div key={claim}>
                      <dt className="font-medium">{claim}</dt>
                      <dd className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                        {sources.map(([label, doi]) => (
                          <a key={doi} href={`https://doi.org/${doi}`} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                            {label}
                          </a>
                        ))}
                      </dd>
                    </div>
                  ))}
                </dl>
              </details>
            </ScienceNote>
          )}
        </div>
        <Button variant="ghost" onClick={onChoosePurpose} className="min-h-11">
          <Trans>View available training plans</Trans>
          <ChevronRight aria-hidden="true" />
        </Button>
      </CardContent>
    </Card>
  );
}

function PlanStartSkeleton() {
  return (
    <div id="plan-start" aria-busy="true" className="flex flex-wrap items-center justify-between gap-4 border-y border-border py-5">
      <div className="w-full max-w-xl space-y-3">
        <Skeleton className="h-5 w-44" />
        <Skeleton className="h-4 w-full" />
      </div>
      <Skeleton className="h-11 w-32" />
    </div>
  );
}

function ProposalRecoveryCard({
  proposal,
  distanceLabel,
  isDemo,
  rejecting,
  onReject,
}: {
  proposal: AdaptivePlanProposal;
  distanceLabel?: string;
  isDemo: boolean;
  rejecting: boolean;
  onReject: () => void;
}) {
  if (proposal.state === 'adopted') {
    return <AdoptedPlanDetails proposal={proposal} distanceLabel={distanceLabel} />;
  }
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <CardTitle><Trans>Plan proposal</Trans></CardTitle>
          <Badge variant="outline">{proposalStateLabel(proposal.state)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 border-t border-border pt-4">
        <details>
          <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium"><Trans>Technical details</Trans></summary>
        <dl className="grid gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-muted-foreground"><Trans>Policy</Trans></dt><dd className="mt-1 font-data">{proposal.policy_version ?? '—'}</dd></div>
          <div><dt className="text-muted-foreground"><Trans>Generator</Trans></dt><dd className="mt-1 font-data">{proposal.model_version ?? '—'}</dd></div>
          <div><dt className="text-muted-foreground"><Trans>Science decision</Trans></dt><dd className="mt-1 font-data">{proposal.science_version ?? '—'}</dd></div>
        </dl>
        </details>
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

export default function PlanStart({
  initialPurpose = null,
}: PlanStartProps) {
  const { t, i18n } = useLingui();
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
  const planStartRegion = useRef<HTMLElement>(null);
  const [setupOpen, setSetupOpen] = useState(Boolean(initialPurpose));
  const [setupStarted, setSetupStarted] = useState(Boolean(initialPurpose));
  const [setupStep, setSetupStep] = useState<SetupStep>(initialPurpose ? 'constraints' : 'intent');
  const [confirmedPurpose, setConfirmedPurpose] = useState(initialPurpose);
  const [expandedProposalId, setExpandedProposalId] = useState<string | null>(null);
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
      (item) => SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_IDS.has(
        item.constraint_schema_id,
      ),
    ) ?? [],
    [capabilityDiscovery],
  );
  const currentCapability = SUPPORTED_PLAN_START_CONSTRAINT_SCHEMA_IDS.has(
    capabilityDiscovery?.selected_capability?.constraint_schema_id ?? '',
  )
    ? capabilityDiscovery?.selected_capability ?? null
    : null;
  const hasSelectablePurpose = Boolean(
    currentCapability && capabilityDiscovery?.current_goal,
  ) || supportedCapabilities.some(
    (item) => item.purpose.allows_capability_goal
      || item.purpose.allows_unlinked,
  );
  const [selectedPurposeKey, setSelectedPurposeKey] = useState(
    () => initialPurpose
      ? purposeKey(initialPurpose.source, initialPurpose.capability_id)
      : '',
  );
  const [selectedPurposeTouched, setSelectedPurposeTouched] = useState(
    Boolean(initialPurpose),
  );
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
  const purposeConfirmed = Boolean(
    purposeSelection
    && confirmedPurpose
    && purposeSelection.capability_id === confirmedPurpose.capability_id
    && purposeSelection.source === confirmedPurpose.source
    && purposeSelection.expected_goal_id === confirmedPurpose.expected_goal_id
    && purposeSelection.expected_goal_revision === confirmedPurpose.expected_goal_revision,
  );
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
    loading: currentProposalLoading,
    error: currentProposalError,
    errorCode: currentProposalErrorCode,
    refetch: refetchProposal,
  } = useApi<AdaptivePlanProposal>(
    '/api/plan/proposals/current',
    { timeoutMs: 12_000, retry: shouldRetryCurrentPlanProposal },
  );
  const activeSchemaId = capability?.constraint_schema_id
    ?? currentCapability?.constraint_schema_id
    ?? supportedCapabilities[0]?.constraint_schema_id
    ?? null;
  const road10kMode = isRoad10KCapabilitySchema(activeSchemaId);

  const [availableDays, setAvailableDays] = useState<Outdoor5KWeekday[]>([]);
  const [maximumSessionDuration, setMaximumSessionDuration] = useState('');
  const [preferredLongestDay, setPreferredLongestDay] = useState<string>('');
  const [adult, setAdult] = useState(false);
  const [selfCoached, setSelfCoached] = useState(false);
  const [canComplete, setCanComplete] = useState(false);
  const [outdoorRoad, setOutdoorRoad] = useState(false);
  const [safetyStop, setSafetyStop] = useState(false);
  const [safetyEdited, setSafetyEdited] = useState(false);
  const [safetyRequestState, setSafetyRequestState] = useState<'none' | 'submitted' | 'failed' | 'changed'>('none');
  const scopeCheckbox = useRef<HTMLElement>(null);
  const adultCheckbox = useRef<HTMLElement>(null);
  const [weeklyTimeLimit, setWeeklyTimeLimit] = useState('');
  const [singleSessionLimit, setSingleSessionLimit] = useState('');
  const [benchmarkDate, setBenchmarkDate] = useState('');
  const [readiness, setReadiness] = useState<
    | Outdoor5KReadinessResponse
    | Outdoor5KGenerateResponse
    | Outdoor5KRegenerateResponse
    | Road10KReadinessResponse
    | Road10KGenerateResponse
    | Road10KRegenerateResponse
    | null
  >(null);
  const [proposal, setProposal] = useState<AdaptivePlanProposal | null>(null);
  const [working, setWorking] = useState<PlanStartWorkingState | null>(null);
  const [error, setError] = useState<PlanStartErrorState | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const idempotencyKeys = useRef<Partial<Record<LifecycleOperation, string>>>({});
  const invalidateReadiness = (nextState: 'none' | 'changed' = 'changed') => {
    setReadiness(null);
    setSafetyRequestState((current) => current === 'none' ? 'none' : nextState);
    setError(null);
  };
  const focusSection = (id: string) => {
    requestAnimationFrame(() => document.getElementById(id)?.focus());
  };
  const openSetup = (step: SetupStep = setupStep) => {
    setSetupStarted(true);
    setSetupStep(step);
    setSetupOpen(true);
    focusSection(step === 'intent' ? 'plan-intent-title' : 'plan-start-intake-title');
  };
  const closeSetup = () => {
    setSetupOpen(false);
    focusSection('plan-start-configure');
  };

  useEffect(() => {
    if (selectedPurposeTouched || !capabilityDiscovery) return;
    let cancelled = false;
    const applyDefaultPurpose = (value: string) => {
      queueMicrotask(() => {
        if (!cancelled) setSelectedPurposeKey(value);
      });
    };
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
      applyDefaultPurpose(existingPurposeKey);
    } else if (currentCapability && capabilityDiscovery.current_goal) {
      applyDefaultPurpose(
        purposeKey('current_goal', currentCapability.id),
      );
    }
    return () => {
      cancelled = true;
    };
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
  const sharedDuration = Number(maximumSessionDuration);
  const durationValid = Number.isInteger(sharedDuration) && sharedDuration > 0;
  const scopeComplete = adult && selfCoached && canComplete && outdoorRoad;
  const confirmScope = (checked: boolean) => {
    setAdult(checked);
    setSelfCoached(checked);
    setCanComplete(checked);
    setOutdoorRoad(checked);
    invalidateReadiness();
  };
  const weeklyTimeLimitNumber = Number(weeklyTimeLimit);
  const singleSessionLimitNumber = Number(singleSessionLimit);
  const road10kFormError = !purposeSelection
    ? t`Choose a training plan first.`
    : !adult
      ? t`Confirm the reviewed adult scope first.`
      : availableDays.length === 0
        ? t`Choose the days you are available to run.`
        : !Number.isInteger(weeklyTimeLimitNumber) || weeklyTimeLimitNumber <= 0
          ? t`Enter a whole-number weekly time limit.`
          : !Number.isInteger(singleSessionLimitNumber) || singleSessionLimitNumber <= 0
            ? t`Enter a whole-number single-session limit.`
            : null;
  const formError = road10kMode
    ? road10kFormError
    : !purposeSelection
    ? t`Choose a training plan first.`
    : !scopeComplete
    ? t`Confirm that all four statements apply to you.`
    : availableDays.length === 0
      ? t`Choose the days you are available to run.`
      : !durationValid
        ? t`Enter a whole-number time limit of at least 1 minute.`
        : null;
  const focusFirstInvalidConstraint = () => {
    setSetupOpen(true);
    setSetupStep(purposeConfirmed ? 'constraints' : 'purpose');
    let targetId = 'plan-start-purpose';
    if (purposeSelection && purposeConfirmed) {
      if (road10kMode) {
        targetId = !adult
          ? 'plan-start-road-10k-adult'
          : availableDays.length === 0
            ? 'plan-start-day-0'
            : !Number.isInteger(weeklyTimeLimitNumber) || weeklyTimeLimitNumber <= 0
              ? 'road-10k-weekly-limit'
              : 'road-10k-session-limit';
      } else if (!scopeComplete) {
        targetId = 'plan-start-scope-confirmation';
      } else if (availableDays.length === 0) {
        targetId = 'plan-start-day-0';
      } else {
        targetId = 'outdoor-5k-session-limit';
      }
    }
    requestAnimationFrame(() => {
      const target = targetId === 'plan-start-scope-confirmation'
        ? scopeCheckbox.current
        : targetId === 'plan-start-road-10k-adult'
          ? adultCheckbox.current
          : document.getElementById(targetId);
      target?.focus();
    });
  };
  const dayName = (day: Outdoor5KWeekday, short = false): string => (
    new Intl.DateTimeFormat(locale === 'zh' ? 'zh-CN' : 'en-US', { weekday: short ? 'short' : 'long' })
      .format(new Date(Date.UTC(2024, 0, day + 1)))
  );
  const distanceName = (distance: string | null | undefined): string => {
    if (!distance) return t`Running`;
    const names: Record<string, string> = {
      marathon: 'Marathon',
      half: 'Half Marathon',
      '50mi': '50 Mile',
      '100mi': '100 Mile',
    };
    return tDisplay(names[distance] ?? distance.toUpperCase(), i18n);
  };
  const planOptionLabel = (item: PlanGenerationCapability, source: PurposeOptionSource): string => {
    const distance = item.purpose.distance ? distanceName(item.purpose.distance) : null;
    const label = source === 'unlinked'
      ? distance ? t`${distance} base training plan` : t`Base training plan`
      : distance ? t`${distance} training plan` : t`Training plan`;
    const hasLinkedAlternative = currentCapability?.id === item.id
      && capabilityDiscovery?.current_goal
      && item.purpose.allows_capability_goal;
    if (hasLinkedAlternative && source === 'current_goal') return t`${label} · linked to current Goal`;
    if (hasLinkedAlternative && source === 'capability') return t`${label} · not linked to current Goal`;
    return label;
  };
  const selectedPurposeLabel = purposeSelection && capability
    ? planOptionLabel(capability, purposeSelection.source)
    : null;
  const currentGoalDistance = capabilityDiscovery?.current_goal?.goal.distance
    ? distanceName(capabilityDiscovery.current_goal.goal.distance)
    : null;
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
    setConfirmedPurpose(null);
    setSetupStep('purpose');
    invalidateReadiness();
    setNotice(null);
  };
  const confirmPurpose = (selection: PlanGenerationPurposeSelection) => {
    selectPurpose(purposeKey(selection.source, selection.capability_id));
    setConfirmedPurpose(selection);
    openSetup('constraints');
  };

  const toggleDay = (day: Outdoor5KWeekday) => {
    setAvailableDays((current) => {
      if (current.includes(day)) {
        if (preferredLongestDay === String(day)) setPreferredLongestDay('');
        return current.filter((value) => value !== day);
      }
      return [...current, day].sort((a, b) => a - b);
    });
    invalidateReadiness();
  };

  const changeSafetyStop = (checked: boolean) => {
    setSafetyStop(checked);
    setSafetyEdited(true);
    invalidateReadiness('none');
  };

  const constraints = (): Outdoor5KConstraintsRequest | Road10KConstraintsRequest | null => {
    if (!purposeConfirmed) {
      setError({ message: t`Choose and confirm a plan purpose before continuing.` });
      focusFirstInvalidConstraint();
      return null;
    }
    if (!purposeSelection || formError) {
      setError({
        message: formError ?? t`Review the constraints and try again.`,
      });
      focusFirstInvalidConstraint();
      return null;
    }
    if (road10kMode) {
      return {
        purpose: purposeSelection,
        adult_confirmed: adult,
        current_symptom_stop: safetyStop,
        available_weekdays: availableDays,
        weekly_time_limit_min: weeklyTimeLimitNumber,
        maximum_session_duration_min: singleSessionLimitNumber,
        unavailable_dates: [],
        preferred_longest_easy_weekday: preferredLongestDay === ''
          ? null
          : Number(preferredLongestDay) as Outdoor5KWeekday,
        benchmark_date: benchmarkDate || null,
      };
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

  const requestReadiness = async (): Promise<Outdoor5KReadinessResponse | Road10KReadinessResponse | null> => {
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
      const value = await planStartResponse<Outdoor5KReadinessResponse | Road10KReadinessResponse>(
        response,
        t`Could not assess this plan start.`,
      );
      setReadiness(value);
      setSafetyRequestState('submitted');
      return value;
    } catch (requestError) {
      setReadiness(null);
      setSafetyRequestState('failed');
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
      || !isPlanReadyResult(checked.result)
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
      const value = await planStartResponse<
        Outdoor5KGenerateResponse | Road10KGenerateResponse
      >(
        response,
        t`Could not create the proposal.`,
      );
      if (isProposalResponse(value) && value.proposal) {
        setProposal(value.proposal);
        setSetupOpen(false);
        setExpandedProposalId(value.proposal.id);
        focusSection('plan-proposal-title');
        setNotice(t`Proposal created. It has not changed your canonical plan.`);
        void refetchProposal();
        void refetchCapabilities();
      }
      setReadiness(value);
      clearOperationKey('generate');
      setSafetyRequestState('submitted');
    } catch (requestError) {
      setReadiness(null);
      setSafetyRequestState('failed');
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
    if (!checked || !body || !isPlanReadyResult(checked.result)) return;
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
      const value = await planStartResponse<
        Outdoor5KRegenerateResponse | Road10KRegenerateResponse
      >(
        response,
        t`Could not regenerate the proposal.`,
      );
      if (isProposalResponse(value) && value.proposal) {
        setProposal(value.proposal);
        setSetupOpen(false);
        setExpandedProposalId(value.proposal.id);
        focusSection('plan-proposal-title');
        setNotice(t`A successor proposal is ready. The earlier proposal is preserved as superseded.`);
        void refetchProposal();
        void refetchCapabilities();
      }
      setReadiness(value);
      clearOperationKey('regenerate');
      setSafetyRequestState('submitted');
    } catch (requestError) {
      setReadiness(null);
      setSafetyRequestState('failed');
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
      setExpandedProposalId(null);
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
      setSetupOpen(false);
      setExpandedProposalId(null);
      setNotice(value.status === 'already_adopted'
        ? t`This exact proposal was already adopted. Delivery remains disabled until you explicitly enable it.`
        : t`Plan adopted. Delivery remains disabled until you explicitly enable it.`);
      clearOperationKey('adopt');
      void refetchProposal();
      void refetchCapabilities();
      refetchSettings();
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
    invalidateReadiness();
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
        distanceLabel={typeof displayedProposal.goal?.target?.distance === 'string'
          ? distanceName(displayedProposal.goal.target.distance)
          : undefined}
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

  if (settingsLoading || capabilityLoading || (currentProposalLoading && !displayedProposal)) {
    return proposalRecoveryCard ?? <PlanStartSkeleton />;
  }

  if (proposalLoadError && !displayedProposal) {
    return (
      <Alert id="plan-start" variant="destructive">
        <AlertTitle><Trans>Could not refresh proposal state</Trans></AlertTitle>
        <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
          <span>{proposalLoadError}</span>
          <Button size="sm" variant="outline" onClick={() => void refetchProposal()}><Trans>Retry</Trans></Button>
        </AlertDescription>
      </Alert>
    );
  }

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
  const road10KGuardrails = (
    road10kMode
    && readiness
    && 'guardrails' in readiness
  )
    ? readiness.guardrails
    : null;
  const showRoad10KScheduleGuardrails = Boolean(
    road10KGuardrails
    && result
    && 'plan_returned' in result
    && result.plan_returned
    && (
      result.code === 'eligible_rolling_proposal'
      || result.code === 'eligible_taper_proposal'
    ),
  );
  const isDraft = displayedProposal?.state === 'draft';
  const isAdopted = displayedProposal?.state === 'adopted';
  const hasManagedPlan = isAdopted
    || config.plan_management.mode === 'praxys'
    || capabilityDiscovery?.active_plan_goal?.lifecycle === 'active';
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
  const proposalDistance = displayedProposal?.goal?.target?.distance;
  const safetyRequestPending = working === 'readiness' || working === 'generate' || working === 'regenerate';
  const safetyFeedback = safetyRequestPending
    ? t`Submitting this check…`
    : safetyRequestState === 'failed'
      ? t`The last new-proposal check did not complete. No safety-stop outcome was confirmed.`
      : result?.code === 'safety_stop'
        ? t`No new proposal was generated: you reported a safety stop.`
        : result
          ? t`This check was submitted. Its result is shown below.`
          : (safetyRequestState === 'submitted' || safetyRequestState === 'changed')
            ? t`Check the current inputs again before generating a new proposal.`
            : safetyEdited
              ? safetyStop
                ? t`Marked on this page, not yet submitted. The next valid check will include this flag; if the safety rule evaluates it, no new proposal will be generated in that check.`
                : t`Unmarked on this page, not yet submitted. A new proposal still needs another check. This is not medical clearance and has not resumed training or workout delivery.`
              : null;
  const safetyConfirmation = (
    <div className="space-y-2 border-y border-border py-4">
      <Label htmlFor="plan-start-safety-stop" className="flex min-h-11 cursor-pointer items-center gap-3 text-sm">
        <Checkbox
          id="plan-start-safety-stop"
          checked={safetyStop}
          disabled={working != null}
          aria-describedby={safetyFeedback ? 'plan-start-safety-scope plan-start-safety-status' : 'plan-start-safety-scope'}
          onCheckedChange={changeSafetyStop}
        />
        {road10kMode
          ? <Trans>Symptom stop flag for this new proposal check</Trans>
          : <Trans>Safety stop flag for this new proposal check</Trans>}
      </Label>
      <p id="plan-start-safety-scope" className="text-sm leading-relaxed text-muted-foreground">
        <Trans>This flag does not pause your current plan or workout delivery.</Trans>
      </p>
      {safetyFeedback && (
        <p id="plan-start-safety-status" role="status" className="text-sm leading-relaxed text-foreground">
          {safetyFeedback}
        </p>
      )}
    </div>
  );

  return (
    <section id="plan-start" aria-label={t`Training plan`} tabIndex={-1} ref={planStartRegion} className="scroll-mt-6 space-y-5">
      <ManagedPlanSettingsCard
        compact
        showSummary={hasManagedPlan}
        cleanupReturnFocusRef={planStartRegion}
        config={config}
        planDeliveryOptions={planDeliveryOptions}
        updateSettings={updateSettings}
      >
        {isAdopted && (
          <AdoptedPlanDetails
            proposal={displayedProposal}
            distanceLabel={typeof proposalDistance === 'string' ? distanceName(proposalDistance) : undefined}
            onReviewInputs={!proposalPurposeConflict ? () => {
              if (purposeSelection) confirmPurpose(purposeSelection);
              else openSetup('purpose');
            } : undefined}
          />
        )}
      </ManagedPlanSettingsCard>

      {!setupOpen && !displayedProposal && (
        <div className="flex flex-col gap-4 border-y border-border py-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-2xl">
            <h2 className="text-base font-semibold">
              {setupStarted ? <Trans>Continue your plan setup</Trans> : <Trans>Explore training plans</Trans>}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              {setupStarted
                ? <Trans>Your setup is kept while you stay on this page.</Trans>
                : <Trans>See the supported plans before deciding whether to adopt one.</Trans>}
            </p>
          </div>
            <Button id="plan-start-configure" variant="outline" onClick={() => openSetup(setupStarted ? setupStep : 'purpose')} aria-expanded={false} aria-controls="plan-start-setup" className="min-h-11 self-start sm:self-auto">
              {setupStarted ? <Trans>Continue setup</Trans> : <Trans>View available training plans</Trans>}
              <ChevronRight aria-hidden="true" />
            </Button>
        </div>
      )}

      {!setupOpen && (safetyEdited || (result && !isPlanReadyResult(result))) && (
        <Alert variant={result?.code === 'safety_stop' ? 'destructive' : 'default'}>
          <AlertTitle>
            <Trans>New proposal check</Trans>
          </AlertTitle>
          <AlertDescription>
            <p>{safetyRequestState === 'failed'
              ? safetyFeedback
              : result
                ? outcomeCopy(result, t`The deterministic policy returned no additional explanation.`)
                : safetyFeedback}</p>
            <p><Trans>This flag does not pause your current plan or workout delivery.</Trans></p>
          </AlertDescription>
        </Alert>
      )}

      {isDraft && safetyEdited && (
        <Alert>
          <AlertTitle><Trans>The existing draft uses its saved inputs</Trans></AlertTitle>
          <AlertDescription>
            <Trans>Adoption still rechecks the existing draft's saved inputs. This flag does not update those inputs or independently block adoption; the other adoption checks still apply.</Trans>
          </AlertDescription>
        </Alert>
      )}

      {capabilityDiscovery?.active_plan_goal?.link_status === 'reassessment_required' && (
        <Alert variant="destructive">
          <AlertTitle><Trans>Plan purpose needs reassessment</Trans></AlertTitle>
          <AlertDescription>
            <Trans>The current Goal changed after this plan purpose was captured. Check readiness again and create a fresh proposal before adoption.</Trans>
          </AlertDescription>
        </Alert>
      )}

      {conflictingProposal && (
        <Alert>
          <AlertTitle><Trans>A draft exists for another plan purpose</Trans></AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span><Trans>Return to that purpose to review or reject it before creating a different draft.</Trans></span>
            {canSelectPolicyProposalPurpose && policyProposalPurposeKey && (
              <Button type="button" size="sm" variant="outline" disabled={working != null} onClick={() => {
                selectPurpose(policyProposalPurposeKey);
                setExpandedProposalId(conflictingProposal.id);
                focusSection('plan-proposal-title');
              }}>
                <Trans>Review existing draft</Trans>
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      <div id="plan-start-setup" hidden={!setupOpen} className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground"><Trans>Your setup is kept while you stay on this page.</Trans></p>
        <Button variant="ghost" disabled={working != null} onClick={closeSetup} className="min-h-11">
          <Trans>Close setup</Trans>
        </Button>
      </div>
      {setupStep === 'intent' && (
        <PlanIntentChooser
          onSelect={confirmPurpose}
          onChoosePurpose={() => openSetup('purpose')}
        />
      )}
      <Card hidden={setupStep === 'intent'}>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-2xl">
              <CardTitle id="plan-start-intake-title" tabIndex={-1}>
                {purposeConfirmed ? <Trans>Set your training availability</Trans> : <Trans>Choose a training plan</Trans>}
              </CardTitle>
              <CardDescription className="mt-2">
                <Trans>
                  Review the <span className="font-data">{displayCapability.horizon_days}</span>-day proposal before deciding whether to adopt it.
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
              <Label htmlFor="plan-start-purpose"><Trans>Training plan</Trans></Label>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                <Trans>Choose the distance you want to train for.</Trans>
              </p>
            </div>
            <Select
              value={selectedPurposeKey}
              onValueChange={selectPurpose}
              disabled={working != null}
            >
              <SelectTrigger id="plan-start-purpose" aria-label={t`Training plan`}>
                <SelectValue placeholder={t`Choose a training plan`}>
                  {selectedPurposeLabel}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {currentCapability && capabilityDiscovery?.current_goal && (
                  <SelectItem value={purposeKey('current_goal', currentCapability.id)}>
                    {planOptionLabel(currentCapability, 'current_goal')}
                  </SelectItem>
                )}
                {supportedCapabilities.map((item) => (
                  item.purpose.allows_capability_goal ? (
                    <SelectItem
                      key={purposeKey('capability', item.id)}
                      value={purposeKey('capability', item.id)}
                    >
                      {planOptionLabel(item, 'capability')}
                    </SelectItem>
                  ) : null
                ))}
                {supportedCapabilities.map((item) => (
                  item.purpose.allows_unlinked ? (
                    <SelectItem
                      key={purposeKey('unlinked', item.id)}
                      value={purposeKey('unlinked', item.id)}
                    >
                      {planOptionLabel(item, 'unlinked')}
                    </SelectItem>
                  ) : null
                ))}
              </SelectContent>
            </Select>
          </div>

          {!currentCapability && capabilityDiscovery?.current_goal && !purposeSelection && (
            <p className="text-sm leading-relaxed text-muted-foreground">
              <Trans>Automatic plans for your current Goal are not available yet. You can choose another training plan without changing that Goal.</Trans>
            </p>
          )}

          {purposeSelection && !usesCurrentGoal && capabilityDiscovery?.current_goal && (
            <p className="text-sm leading-relaxed text-muted-foreground">
              {currentGoalDistance
                ? <Trans>This plan will not change your current {currentGoalDistance} Goal.</Trans>
                : <Trans>This plan will not change your current Goal.</Trans>}
            </p>
          )}

          {!purposeConfirmed && (
            <div className="flex flex-wrap gap-2">
              <Button disabled={!purposeSelection || working != null} onClick={() => { if (purposeSelection) confirmPurpose(purposeSelection); }} className="min-h-11">
                <Trans>Continue setup</Trans>
                <ChevronRight aria-hidden="true" />
              </Button>
              <Button variant="ghost" onClick={() => openSetup('intent')} className="min-h-11">
                <Trans>Choose by training intent</Trans>
              </Button>
            </div>
          )}
          {confirmedPurpose && !purposeConfirmed && (
            <Alert>
              <AlertTitle><Trans>Plan-start context changed</Trans></AlertTitle>
              <AlertDescription><Trans>Choose and confirm a plan purpose before continuing.</Trans></AlertDescription>
            </Alert>
          )}

          {purposeConfirmed && (
          <fieldset disabled={working != null} className="min-w-0 space-y-6 border-0 p-0">
          {road10kMode ? (
            <>
              <div>
                <h3 className="text-sm font-semibold"><Trans>Before you start</Trans></h3>
                <Label htmlFor="plan-start-road-10k-adult" className="mt-2 flex min-h-11 cursor-pointer items-center gap-3 text-sm">
                  <Checkbox
                    ref={adultCheckbox}
                    id="plan-start-road-10k-adult"
                    checked={adult}
                    disabled={working != null}
                    onCheckedChange={(checked) => {
                      setAdult(checked);
                      invalidateReadiness();
                    }}
                  />
                  <Trans>I am <span className="font-data">18</span> or older.</Trans>
                </Label>
                <ScienceNote label={<Trans>About this plan</Trans>}>
                  <p>
                  <Trans>
                    This reviewed 10K performance capability uses adult confirmation, direct 10K evidence, and history-anchored load caps. It does not diagnose, clear, or guarantee a performance outcome.
                  </Trans>
                  </p>
                </ScienceNote>
              </div>

              {safetyConfirmation}

              <div>
                <h3 className="text-sm font-semibold"><Trans>Available run days</Trans></h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  <Trans>Choose three to six days you can actually keep. Praxys anchors load to your recent median rather than your target-time gap.</Trans>
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {DAYS.map((day) => {
                    const selected = availableDays.includes(day);
                    return (
                      <Button
                        id={`plan-start-day-${day}`}
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

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="road-10k-weekly-limit"><Trans>Weekly time limit (minutes)</Trans></Label>
                  <Input
                    id="road-10k-weekly-limit"
                    type="number"
                    min="1"
                    inputMode="numeric"
                    value={weeklyTimeLimit}
                    onChange={(event) => {
                      setWeeklyTimeLimit(event.target.value);
                      invalidateReadiness();
                    }}
                    className="font-data"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="road-10k-session-limit"><Trans>Single-session limit (minutes)</Trans></Label>
                  <Input
                    id="road-10k-session-limit"
                    type="number"
                    min="1"
                    inputMode="numeric"
                    value={singleSessionLimit}
                    onChange={(event) => {
                      setSingleSessionLimit(event.target.value);
                      invalidateReadiness();
                    }}
                    className="font-data"
                  />
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="road-10k-long-day"><Trans>Preferred longest-easy day</Trans></Label>
                  <Select
                    value={preferredLongestDay === '' ? 'none' : preferredLongestDay}
                    onValueChange={(value) => {
                      setPreferredLongestDay(value === 'none' || value == null ? '' : value);
                      invalidateReadiness();
                    }}
                  >
                    <SelectTrigger id="road-10k-long-day">
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
                <div className="space-y-2">
                  <Label htmlFor="road-10k-benchmark-date"><Trans>Optional benchmark date</Trans></Label>
                  <Input
                    id="road-10k-benchmark-date"
                    type="date"
                    value={benchmarkDate}
                    onChange={(event) => {
                      setBenchmarkDate(event.target.value);
                      invalidateReadiness();
                    }}
                    className="font-data"
                  />
                  <p className="text-sm text-muted-foreground">
                    <Trans>Choose and date an optional benchmark only if you want one. Praxys never auto-schedules it, and a target-time gap never raises load on its own.</Trans>
                  </p>
                </div>
              </div>
            </>
          ) : (
            <>
              <fieldset className="min-w-0">
                <legend className="text-sm font-semibold"><Trans>Before you start</Trans></legend>
                <ul id="plan-start-scope-facts" className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-foreground">
                  <li><Trans>I am <span className="font-data">18</span> or older.</Trans></li>
                  <li><Trans>I am self-coached for recreational road running.</Trans></li>
                  <li><Trans>I can currently complete <span className="font-data">5</span> km.</Trans></li>
                  <li><Trans>This plan is for an outdoor road <span className="font-data">5K</span>.</Trans></li>
                </ul>
                <Label htmlFor="plan-start-scope-confirmation" className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 text-sm">
                  <Checkbox
                    ref={scopeCheckbox}
                    id="plan-start-scope-confirmation"
                    aria-describedby={!scopeComplete ? 'plan-start-scope-facts plan-start-validation' : 'plan-start-scope-facts'}
                    aria-invalid={!scopeComplete && error?.message === formError}
                    checked={scopeComplete}
                    disabled={working != null}
                    onCheckedChange={confirmScope}
                  />
                  <Trans>All four statements apply to me.</Trans>
                </Label>
                <ScienceNote label={<Trans>About this plan</Trans>}>
                  <p>
                  <Trans>
                    This is a pilot for adult, self-coached recreational outdoor-road 5K runners. It does not diagnose, clear, or guarantee a performance outcome.
                  </Trans>
                  </p>
                </ScienceNote>
              </fieldset>

              {safetyConfirmation}

              <div>
                <h3 className="text-sm font-semibold"><Trans>Available run days</Trans></h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  <Trans>Select the days you can usually run.</Trans>
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {DAYS.map((day) => {
                    const selected = availableDays.includes(day);
                    return (
                      <Button
                        id={`plan-start-day-${day}`}
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

              <div className="max-w-2xl space-y-2">
                <Label htmlFor="outdoor-5k-session-limit"><Trans>Time available per run (maximum minutes)</Trans></Label>
                <Input
                  id="outdoor-5k-session-limit"
                  type="number"
                  min="1"
                  inputMode="numeric"
                  value={maximumSessionDuration}
                  aria-describedby="outdoor-5k-session-help"
                  aria-invalid={!durationValid && error?.message === formError}
                  onChange={(event) => {
                    setMaximumSessionDuration(event.target.value);
                    invalidateReadiness();
                  }}
                  className="max-w-xs font-data"
                />
                <p id="outdoor-5k-session-help" className="text-sm leading-relaxed text-muted-foreground">
                  <Trans>This maximum applies to every selected day. Runs need not fill it, and not every available day will necessarily have a workout; recent training and other rules still shape the plan.</Trans>
                </p>
              </div>

              <div className="grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="outdoor-5k-long-day"><Trans>Preferred longest-run day</Trans></Label>
                  <Select
                    value={preferredLongestDay === '' ? 'none' : preferredLongestDay}
                    onValueChange={(value) => {
                      setPreferredLongestDay(value === 'none' || value == null ? '' : value);
                      invalidateReadiness();
                    }}
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
            </>
          )}

          {formError && (
            <p id="plan-start-validation" className="text-sm text-destructive" aria-live="polite">
              {formError}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button disabled={isDemo || working != null || !purposeSelection} onClick={() => void requestReadiness()} className="min-h-11">
              {working === 'readiness' ? <Trans>Checking readiness…</Trans> : <Trans>Check readiness</Trans>}
            </Button>
            {result && isPlanReadyResult(result) && !activeProposal && !conflictingProposal && (
              <Button variant="outline" disabled={isDemo || working != null} onClick={() => void generate()} className="min-h-11">
                {working === 'generate' ? <Trans>Creating proposal…</Trans> : <Trans>Create proposal</Trans>}
              </Button>
            )}
            {isDraft && !proposalPurposeConflict && (
              <Button variant="outline" disabled={isDemo || working != null || Boolean(proposalLoadError)} onClick={() => void regenerate()} className="min-h-11">
                <RefreshCw aria-hidden="true" />
                {working === 'regenerate' ? <Trans>Regenerating…</Trans> : <Trans>Regenerate successor</Trans>}
              </Button>
            )}
          </div>
          </fieldset>
          )}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle><Trans>Readiness result</Trans></CardTitle>
              <Badge variant={isPlanReadyResult(result) ? 'default' : 'outline'}>{result.code.replace(/_/g, ' ')}</Badge>
            </div>
            <CardDescription>{outcomeCopy(result, t`The deterministic policy returned no additional explanation.`)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 border-t border-border pt-4">
            {road10kMode ? (
              <>
                <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <dt className="text-muted-foreground"><Trans>Baseline source</Trans></dt>
                    <dd className="mt-1 font-data">{baseline && 'evidence' in baseline ? baseline.evidence?.provenance ?? '—' : '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground"><Trans>History cutoff</Trans></dt>
                    <dd className="mt-1 font-data">{readiness && 'history_cutoff_completed_days' in readiness ? readiness.history_cutoff_completed_days : '—'}d</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground"><Trans>Event state</Trans></dt>
                    <dd className="mt-1">{readiness && 'event_context' in readiness ? readiness.event_context.state.replace(/_/g, ' ') : '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground"><Trans>Templates</Trans></dt>
                    <dd className="mt-1 font-data">{readiness && 'template_ids' in readiness ? readiness.template_ids.join(', ') : '—'}</dd>
                  </div>
                </dl>
                <p className="text-sm text-muted-foreground">
                  <Trans>History used:</Trans>{' '}
                  <span className="font-data">{result.history_statistics.usable_completed_weeks}</span>{' '}
                  <Trans>usable completed weeks; latest run</Trans>{' '}
                  <span className="font-data">{result.history_statistics.latest_run_date ?? '—'}</span>.
                </p>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                <Trans>History used:</Trans>{' '}
                <span className="font-data">{result.history_statistics.usable_completed_weeks}</span>{' '}
                <Trans>complete weeks; latest run</Trans>{' '}
                <span className="font-data">{result.history_statistics.latest_run_date ?? '—'}</span>.
              </p>
            )}
            {showRoad10KScheduleGuardrails && road10KGuardrails && (
              <ScienceNote
                label={<Trans>Road 10K schedule guardrails</Trans>}
                sourceUrl="https://github.com/praxys-run/praxys/blob/main/data/science/decisions/sdr-road-10k-plan-generation-policy-v2.yaml"
                sourceLabel={t`Accepted road 10K plan-generation policy`}
              >
                <p>
                  <Trans>
                    The accepted <span className="font-data">{road10KGuardrails.committed_proposal_days}</span>-day proposal and <span className="font-data">{road10KGuardrails.advisory_reassessment_after_completed_days}</span>-day reassessment, one quality session per week, at least <span className="font-data">{new Intl.NumberFormat(locale === 'zh' ? 'zh-CN' : 'en-US', { style: 'percent', maximumFractionDigits: 0 }).format(road10KGuardrails.minimum_planned_low_intensity_running_minutes_fraction)}</span> planned low-intensity running minutes, history- and constraint-capped schedule, and the exact two quality templates are Praxys guardrails. They are not published optima or promises of efficacy or safety.
                  </Trans>
                </p>
              </ScienceNote>
            )}
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

      {result && needsBaselineReview(result)
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
      </div>

      {proposalLoadError && (
        <Alert variant="destructive" role="alert">
          <AlertTitle><Trans>Could not refresh proposal state</Trans></AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>{proposalLoadError}</span>
            <Button size="sm" variant="outline" onClick={() => void refetchProposal()}><Trans>Retry</Trans></Button>
          </AlertDescription>
        </Alert>
      )}

      {displayedProposal && !isAdopted && (
        <Collapsible
          open={expandedProposalId === displayedProposal.id}
          onOpenChange={(open) => setExpandedProposalId(open ? displayedProposal.id : null)}
        >
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle id="plan-proposal-title" tabIndex={-1}>
                  {hasManagedPlan && isDraft
                      ? <Trans>New proposal to review</Trans>
                      : <Trans>Plan proposal</Trans>}
                </CardTitle>
                <CardDescription className="mt-2">
                  <Trans>This proposal is not yet your plan. It cannot deliver workouts until after explicit adoption and separate delivery consent.</Trans>
                </CardDescription>
              </div>
              <Badge variant="outline">{proposalStateLabel(displayedProposal.state)}</Badge>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
              {typeof proposalDistance === 'string' && (
                <span className="font-data">{distanceName(proposalDistance)}</span>
              )}
              {(displayedProposal.goal?.purpose_source === 'current_goal' || capabilityDiscovery?.current_goal) && <span>
                {displayedProposal.goal?.purpose_source === 'current_goal'
                  ? <Trans>Linked to current Goal</Trans>
                  : displayedProposal.goal?.purpose_source === 'capability'
                    ? <Trans>Not linked to current Goal</Trans>
                    : displayedProposal.goal?.purpose_source === 'unlinked'
                      ? <Trans>Unlinked plan</Trans>
                      : <Trans>Legacy purpose</Trans>}
              </span>}
              <span><Trans>Version</Trans> <span className="font-data">{displayedProposal.version}</span></span>
              {displayedProposal.workouts.length > 0 && (
                <span className="font-data">
                  {displayedProposal.workouts[0].date} – {displayedProposal.workouts[displayedProposal.workouts.length - 1].date}
                </span>
              )}
            </div>
            {displayedProposal.expires_at && (
              <p className="mt-2 text-sm text-muted-foreground"><Trans>Expires:</Trans> <span className="font-data">{displayedProposal.expires_at}</span></p>
            )}
            {displayedProposal.warnings.length > 0 && (
              <p className="mt-2 text-sm text-muted-foreground">{displayedProposal.warnings.map(formatProposalDetail).join(' · ')}</p>
            )}
            {proposalNeedsReassessment && (
              <Alert variant="destructive" className="mt-3">
                <AlertTitle><Trans>Adoption is paused</Trans></AlertTitle>
                <AlertDescription><Trans>The linked Goal changed. Recheck readiness and regenerate this proposal before adopting it.</Trans></AlertDescription>
              </Alert>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <CollapsibleTrigger
                disabled={working != null}
                render={<Button variant={isDraft ? 'outline' : 'ghost'} className="min-h-11" />}
              >
                {expandedProposalId === displayedProposal.id
                  ? <Trans>Hide proposal</Trans>
                  : isDraft ? <Trans>Continue review</Trans> : <Trans>View proposal</Trans>}
                <ChevronDown aria-hidden="true" className={expandedProposalId === displayedProposal.id ? 'rotate-180' : ''} />
              </CollapsibleTrigger>
              {!proposalPurposeConflict && !setupOpen && (
                <Button id="plan-start-configure" variant="ghost" disabled={working != null} onClick={() => {
                  if (purposeSelection) confirmPurpose(purposeSelection);
                  else openSetup('purpose');
                }} className="min-h-11">
                  {isDraft ? <Trans>Edit constraints</Trans> : <Trans>Review plan inputs</Trans>}
                </Button>
              )}
            </div>
          </CardHeader>
          <CollapsibleContent keepMounted>
          <CardContent className="space-y-5 border-t border-border pt-4">
            <details>
              <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium"><Trans>Technical details</Trans></summary>
            <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-muted-foreground"><Trans>Goal link</Trans></dt>
                <dd className="mt-1">
                  {displayedProposal.goal?.purpose_source === 'current_goal'
                    ? <Trans>Linked to current Goal</Trans>
                    : displayedProposal.goal?.purpose_source === 'capability'
                      ? <Trans>Not linked to current Goal</Trans>
                      : displayedProposal.goal?.purpose_source === 'unlinked'
                        ? <Trans>Unlinked plan</Trans>
                        : <Trans>Legacy purpose</Trans>}
                </dd>
              </div>
              <div><dt className="text-muted-foreground"><Trans>Policy</Trans></dt><dd className="mt-1 break-all font-data">{displayedProposal.policy_version ?? '—'}</dd></div>
              <div><dt className="text-muted-foreground"><Trans>Generator</Trans></dt><dd className="mt-1 break-all font-data">{displayedProposal.model_version ?? '—'}</dd></div>
              <div><dt className="text-muted-foreground"><Trans>Science decision</Trans></dt><dd className="mt-1 break-all font-data">{displayedProposal.science_version ?? '—'}</dd></div>
            </dl>
            </details>
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
            {isDraft && (
              <div className="flex flex-wrap gap-2">
                {!proposalPurposeConflict && (
                  <Button disabled={isDemo || working != null || proposalNeedsReassessment || Boolean(proposalLoadError)} onClick={() => void adopt()} className="min-h-11">
                    {working === 'adopt' ? <Trans>Adopting…</Trans> : <Trans>Adopt exact proposal</Trans>}
                  </Button>
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
          </CardContent>
          </CollapsibleContent>
        </Card>
        </Collapsible>
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
