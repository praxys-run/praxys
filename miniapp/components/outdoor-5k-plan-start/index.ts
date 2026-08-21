import { apiGet, apiPost } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import type { IAppOption } from '../../app';
import { detectLocale, t } from '../../utils/i18n';
import {
  road10kCopy,
  type Road10KCopyKey,
} from '../../utils/road-10k-control';
import type {
  AdaptivePlanProposal,
  AdaptivePlanProposalAdoptResponse,
  Outdoor5KConstraintsRequest,
  Outdoor5KGenerateResponse,
  Outdoor5KOutcomeResponse,
  Outdoor5KReadinessResponse,
  Outdoor5KRegenerateResponse,
  Outdoor5KWeekday,
  PlanGenerationCapabilitiesResponse,
  PlanGenerationCapability,
  PlanGenerationPurposeSelection,
  Road10KConstraintsRequest,
  Road10KGenerateResponse,
  Road10KOutcomeResponse,
  Road10KReadinessResponse,
  Road10KRegenerateResponse,
} from '../../types/api';

interface DayOption {
  value: Outdoor5KWeekday;
  label: string;
  selected: boolean;
  duration: string;
}

interface PurposeOption {
  value: string;
  label: string;
  capabilityId: string;
  source: PlanGenerationPurposeSelection['source'] | '';
}

type LifecycleOperation = 'generate' | 'regenerate' | 'reject' | 'adopt';

function roadCopy(key: Road10KCopyKey): string {
  return road10kCopy(key, detectLocale() === 'zh' ? 'zh-CN' : 'en');
}

function purposeValue(
  source: PlanGenerationPurposeSelection['source'],
  capabilityId: string,
): string {
  return `${source}:${capabilityId}`;
}

function samePurposeSelection(
  left: PlanGenerationPurposeSelection | null | undefined,
  right: PlanGenerationPurposeSelection | null | undefined,
): boolean {
  return Boolean(
    left
    && right
    && left.capability_id === right.capability_id
    && left.source === right.source
    && left.expected_goal_id === right.expected_goal_id
    && left.expected_goal_revision === right.expected_goal_revision,
  );
}

function copy() {
  return {
    title: t('Plan preview'),
    road10kTitle: roadCopy('inputs.title'),
    road10kInputBody: roadCopy('inputs.body'),
    unsupportedTitle: t('Plan generation for this goal'),
    supportedGoal: t('No accepted automatic policy matches this goal yet. Praxys keeps manual plan management available instead of repurposing the 5K policy.'),
    purpose: t('Plan purpose'),
    purposeDetail: t('The current Goal is the default when an accepted policy matches it. A separate purpose keeps that Goal unchanged.'),
    choosePurpose: t('Choose an accepted plan purpose'),
    purposeRequired: t('Choose an accepted plan purpose first.'),
    currentGoalPurpose: t('Current Goal'),
    separatePurpose: t('Separate plan purpose'),
    unlinkedPurpose: t('Unlinked base plan'),
    currentGoalUnavailable: t('The current Goal has no accepted automatic policy. Keep it unchanged, or choose an accepted separate purpose.'),
    separatePurposeDetail: t('This proposal uses an accepted goal contract without changing or linking to the Goal page.'),
    reassessmentTitle: t('Plan purpose needs reassessment'),
    reassessmentDetail: t('The current Goal changed after this plan purpose was captured. Check readiness again and create a fresh proposal before adoption.'),
    conflictingPurpose: t('A draft exists for another plan purpose. Return to that purpose to review or reject it first.'),
    updateRequired: t('This client does not recognize the selected policy input contract and will not guess how to create a plan.'),
    scope: t('Scope and guardrails'),
    scopeDetail: t('For adult, self-coached recreational outdoor-road 5K runners. This is not a diagnosis, clearance, or performance guarantee.'),
    road10kScopeDetail: t('This reviewed 10K performance capability uses adult confirmation, direct 10K evidence, and history-anchored load caps. It does not diagnose, clear, or guarantee a performance outcome.'),
    adult: t('I am 18 or older.'),
    selfCoached: t('I am self-coached for recreational road running.'),
    canComplete: t('I can currently complete 5 km.'),
    outdoorRoad: t('My goal is an outdoor road 5K.'),
    safety: t('Safety stop'),
    safetyDetail: t('Tell Praxys if a safety stop applies. The policy will stop this path and show its bounded alternatives.'),
    road10kSafetyDetail: t('Tell Praxys if a current symptom stop applies. The policy will stop this plan path and return only bounded guidance.'),
    safetyOff: t('No safety stop'),
    safetyOn: t('Safety stop applies'),
    road10kSafetyOff: t('No symptom stop'),
    road10kSafetyOn: t('Symptom stop applies'),
    days: t('Available run days'),
    dayDetail: t('Select availability, then give the same supported session limit for every selected day.'),
    road10kDayDetail: t('Choose three to six days you can actually keep. Praxys anchors load to your recent median rather than your target-time gap.'),
    timeLimit: t('Time limit (minutes)'),
    weeklyTimeLimit: t('Weekly time limit (minutes)'),
    singleSessionLimit: t('Single-session limit (minutes)'),
    perDayUnsupported: t('Per-day limits are unsupported'),
    perDayUnsupportedDetail: t('The accepted deterministic policy has one shared maximum-session field. Praxys will not invent a per-day rule or silently reduce your schedule; use one limit for all selected days.'),
    longDay: t('Preferred longest-run day'),
    road10kLongDay: t('Preferred longest-easy day'),
    noPreference: t('No preference'),
    terrain: t('Terrain and equipment'),
    terrainDetail: t('This policy supports outdoor road running only. Terrain, treadmill, trail, and equipment preferences are unsupported inputs and are not inferred.'),
    benchmark: t('Optional benchmark'),
    benchmarkDetail: t('Choose and date an optional benchmark only if you want one. Praxys never auto-schedules it.'),
    check: t('Check readiness'),
    checking: t('Checking readiness…'),
    create: t('Create proposal'),
    creating: t('Creating proposal…'),
    roadCheck: roadCopy('action.check'),
    roadChecking: roadCopy('progress.checking'),
    roadCreate: roadCopy('action.generate'),
    roadCreating: roadCopy('progress.generating'),
    result: t('Readiness result'),
    planCandidate: t('Plan candidate'),
    readinessOnly: t('Readiness first'),
    clarificationRequired: t('Needs clarification'),
    policyUnavailable: t('Policy unavailable'),
    ready: t('Ready'),
    draft: t('Draft'),
    superseded: t('Superseded'),
    rejectedState: t('Rejected'),
    adoptedState: t('Adopted'),
    expired: t('Expired'),
    baselineSource: t('Baseline source'),
    historyCutoff: t('History cutoff'),
    eventState: t('Event state'),
    templates: t('Templates'),
    noEvent: t('No event selected'),
    singleTarget: t('Single target'),
    eventConflict: t('Event conflict'),
    controlledThreshold: t('Controlled threshold quality'),
    specificIntervals: t('10K-specific interval quality'),
    usableWeeks: t('usable completed weeks; latest run'),
    daysUnit: t('days'),
    alternativeAccepted5k: t('Use the accepted outdoor 5K policy'),
    alternativeBaselineGuidance: t('Use baseline or consistency guidance'),
    alternativeDefer: t('Defer plan generation'),
    alternativeSafetyGuidance: t('Use non-medical safety guidance'),
    alternativeRefresh5kBaseline: t('Refresh the qualified 5K baseline'),
    alternativeReviseTarget: t('Revise the target time or date'),
    alternativeBuildConsistency: t('Build more consistent running first'),
    alternativeReviseAvailability: t('Revise stated availability'),
    alternativeReviewAnchoredBlock: t('Review the history-anchored block'),
    alternativeRefreshPolicy: t('Refresh policy metadata'),
    alternativeManualTraining: t('Keep training manually'),
    alternativeConfirmAdult: t('Confirm adult scope'),
    alternativeConfirm10kHistory: t('Confirm direct 10K history'),
    alternativeBenchmark: t('Choose an optional 10K benchmark'),
    alternativeKeepOneTarget: t('Keep one target date'),
    alternativeDeclineBenchmark: t('Decline the optional benchmark'),
    alternativeWaitReassessment: t('Wait for post-target reassessment'),
    alternativeReviseConstraints: t('Revise the constraints'),
    alternativeReviewBeforeAdopting: t('Review before adopting'),
    alternativeKeepCurrentPlan: t('Keep the current plan until adoption'),
    proposal: t('Plan proposal'),
    roadProposal: roadCopy('proposal.title'),
    roadProposalBadge: roadCopy('proposal.badge'),
    roadProposalBody: roadCopy('proposal.body'),
    purposeLabel: t('Purpose'),
    policy: t('Policy'),
    roadPolicy: roadCopy('proposal.policy'),
    generator: t('Generator'),
    roadGenerator: roadCopy('proposal.generator'),
    science: t('Science'),
    roadScience: roadCopy('proposal.science'),
    proposalNotPlan: t('This proposal is not yet your plan. It cannot deliver workouts until after explicit adoption and separate delivery consent.'),
    inputsOnly: t('Workout content is view-only in this deterministic policy. Change the bounded inputs above and regenerate to create an immutable successor; Praxys never constructs replacement workouts in this client.'),
    regenerate: t('Regenerate successor'),
    regenerating: t('Regenerating…'),
    roadRegenerate: roadCopy('action.regenerate'),
    roadRegenerating: roadCopy('progress.regenerating'),
    adopt: t('Adopt exact proposal'),
    adopting: t('Adopting…'),
    roadAdopt: roadCopy('action.adopt'),
    roadAdopting: roadCopy('progress.adopting'),
    reject: t('Reject or defer'),
    rejecting: t('Rejecting…'),
    roadReject: roadCopy('action.reject'),
    roadRejecting: roadCopy('progress.rejecting'),
    roadReviewLater: roadCopy('action.review_later'),
    roadPlanActive: roadCopy('plan.active_body'),
    deliveryDisabled: t('Delivery remains disabled. Review the existing 14-day managed-delivery preview and explicitly consent only if you want Praxys to deliver this canonical plan.'),
    refresh: t('Refresh proposal'),
    retry: t('Retry'),
    failed: t('Plan-start action did not complete'),
    scopeRequired: t('Confirm the supported athlete and goal scope first.'),
    road10kScopeRequired: t('Confirm the reviewed adult scope first.'),
    daysRequired: t('Choose the days you are available to run.'),
    durationRequired: t('Enter one whole-minute limit for every selected day.'),
    weeklyLimitRequired: t('Enter a whole-number weekly time limit.'),
    singleSessionRequired: t('Enter a whole-number single-session limit.'),
    requestFailed: t('Could not assess this plan start.'),
    noExplanation: t('The deterministic policy returned no additional explanation.'),
    noProposal: t('Proposal created. It has not changed your canonical plan.'),
    successor: t('A successor proposal is ready. The earlier proposal is preserved as superseded.'),
    rejected: t('Proposal rejected. Your canonical plan was not changed.'),
    adopted: t('Plan adopted. Delivery remains disabled until you explicitly enable it.'),
    alreadyAdopted: t('This exact proposal was already adopted. Delivery remains disabled until you explicitly enable it.'),
    lifecycle: t('Proposal state needs a fresh preview'),
    lifecycleDetail: t('This proposal cannot mutate the canonical plan. Review readiness and create a new proposal when you are ready.'),
    adoptionPaused: t('Adoption is paused until the linked Goal is reassessed.'),
  };
}

function uuid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function proposalResponse(
  response:
    | Outdoor5KGenerateResponse
    | Outdoor5KRegenerateResponse
    | Road10KGenerateResponse
    | Road10KRegenerateResponse,
): response is Extract<
  Outdoor5KGenerateResponse | Road10KGenerateResponse,
  { proposal: AdaptivePlanProposal | null }
> {
  return 'proposal' in response;
}

function reason(
  result: Outdoor5KOutcomeResponse | Road10KOutcomeResponse,
  fallback: string,
): string {
  if ('route_state' in result) {
    return roadCopy(roadOutcomeCopyKeys(result.code)[1]);
  }
  return result.observed_or_stated_reason
    ?? result.uncertainty_or_missing_field
    ?? fallback;
}

function roadOutcomeCopyKeys(
  code: Road10KOutcomeResponse['code'],
): readonly [Road10KCopyKey, Road10KCopyKey] {
  const mapping: Record<
    Road10KOutcomeResponse['code'],
    readonly [Road10KCopyKey, Road10KCopyKey]
  > = {
    eligible_rolling_proposal: [
      'eligibility.ready_title',
      'eligibility.ready_body',
    ],
    eligible_taper_proposal: [
      'eligibility.ready_title',
      'eligibility.ready_body',
    ],
    missing_or_stale_direct_baseline: [
      'eligibility.baseline_title',
      'eligibility.baseline_body',
    ],
    insufficient_recent_history: [
      'eligibility.history_title',
      'eligibility.history_body',
    ],
    limited_guidance_event_conflict: [
      'eligibility.limited_title',
      'eligibility.event_body',
    ],
    limited_near_term_guidance: [
      'eligibility.limited_title',
      'eligibility.near_body',
    ],
    safety_stop: [
      'eligibility.safety_title',
      'eligibility.safety_body',
    ],
    adult_scope_or_constraints_unconfirmed: [
      'eligibility.confirm_title',
      'eligibility.confirm_body',
    ],
    contradictory_input: [
      'eligibility.conflict_title',
      'eligibility.conflict_body',
    ],
    unsupported_intent_distance_surface_or_population: [
      'eligibility.unsupported_title',
      'eligibility.unsupported_body',
    ],
    no_schedule_within_envelope: [
      'eligibility.schedule_title',
      'eligibility.schedule_body',
    ],
    validation_failed: [
      'eligibility.unavailable_title',
      'eligibility.unavailable_body',
    ],
  };
  return mapping[code];
}

type ReadinessResponse =
  | Outdoor5KReadinessResponse
  | Outdoor5KGenerateResponse
  | Outdoor5KRegenerateResponse
  | Road10KReadinessResponse
  | Road10KGenerateResponse
  | Road10KRegenerateResponse;

function readinessBadge(
  result: Outdoor5KOutcomeResponse | Road10KOutcomeResponse,
  tr: ReturnType<typeof copy>,
): string {
  if ('route_state' in result) {
    return roadCopy(roadOutcomeCopyKeys(result.code)[0]);
  }
  return result.code === 'ready' ? tr.ready : tr.readinessOnly;
}

function proposalStateLabel(
  proposal: AdaptivePlanProposal | null,
  tr: ReturnType<typeof copy>,
): string {
  if (!proposal) return '';
  return {
    draft: tr.draft,
    superseded: tr.superseded,
    rejected: tr.rejectedState,
    adopted: tr.adoptedState,
    expired: tr.expired,
  }[proposal.state] ?? tr.draft;
}

function road10kReadinessContext(
  response: ReadinessResponse,
  tr: ReturnType<typeof copy>,
): {
  rows: Array<{ label: string; value: string }>;
  history: string;
} {
  if (!('event_context' in response)) return { rows: [], history: '' };
  const evidence = 'baseline' in response
    ? response.baseline?.evidence
    : undefined;
  const provenance = evidence?.provenance === 'race'
    ? t('Measured 10K race')
    : evidence?.provenance === 'intentional_all_out'
      ? t('Intentional all-out complete 10K')
      : '—';
  const eventState = {
    confirmed_none: tr.noEvent,
    single_target: tr.singleTarget,
    race_dense: tr.eventConflict,
  }[response.event_context.state] ?? tr.noEvent;
  const templateLabels = response.template_ids.map((templateId) => ({
    'road-10k-controlled-threshold-quality-v1': tr.controlledThreshold,
    'road-10k-specific-interval-quality-v1': tr.specificIntervals,
  }[templateId])).filter((label): label is string => Boolean(label));
  return {
    rows: [
      { label: tr.baselineSource, value: provenance },
      {
        label: tr.historyCutoff,
        value: `${response.history_cutoff_completed_days} ${tr.daysUnit}`,
      },
      { label: tr.eventState, value: eventState },
      { label: tr.templates, value: templateLabels.join(' · ') || '—' },
    ],
    history: `${response.result.history_statistics.usable_completed_weeks} ${tr.usableWeeks} ${response.result.history_statistics.latest_run_date ?? '—'}`,
  };
}

function readinessAlternatives(
  result: Outdoor5KOutcomeResponse | Road10KOutcomeResponse,
  tr: ReturnType<typeof copy>,
): string[] {
  const labels: Record<string, string> = {
    use_accepted_outdoor_5k_policy: tr.alternativeAccepted5k,
    use_baseline_or_consistency_guidance: tr.alternativeBaselineGuidance,
    defer_plan_generation: tr.alternativeDefer,
    use_non_medical_safety_guidance: tr.alternativeSafetyGuidance,
    refresh_qualified_5k_baseline: tr.alternativeRefresh5kBaseline,
    revise_target_time_or_date: tr.alternativeReviseTarget,
    future_consistency_or_base_policy: tr.alternativeBuildConsistency,
    revise_stated_availability: tr.alternativeReviseAvailability,
    accept_history_anchored_block_with_feasibility_unknown:
      tr.alternativeReviewAnchoredBlock,
    refresh_policy_metadata: tr.alternativeRefreshPolicy,
    keep_manual_training: tr.alternativeManualTraining,
    confirm_adult_scope: tr.alternativeConfirmAdult,
    confirm_direct_10k_history: tr.alternativeConfirm10kHistory,
    choose_optional_10k_benchmark: tr.alternativeBenchmark,
    accumulate_more_consistent_running: tr.alternativeBuildConsistency,
    keep_one_target_date: tr.alternativeKeepOneTarget,
    decline_optional_benchmark: tr.alternativeDeclineBenchmark,
    wait_for_post_target_reassessment: tr.alternativeWaitReassessment,
    revise_constraints: tr.alternativeReviseConstraints,
    review_before_adopting: tr.alternativeReviewBeforeAdopting,
    keep_current_plan_until_adoption: tr.alternativeKeepCurrentPlan,
  };
  return result.alternatives
    .map((alternative) => labels[alternative])
    .filter((label): label is string => Boolean(label));
}

function isRoad10KCapability(
  capability: PlanGenerationCapability | null | undefined,
): boolean {
  return capability?.constraint_schema_id === 'outdoor_road_10k_constraints_v1';
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
  return (
    result.code === 'insufficient_or_stale_baseline'
    || result.code === 'missing_or_stale_direct_baseline'
  );
}

function dayOptions(existing: DayOption[] = []): DayOption[] {
  const previous = new Map(existing.map((option) => [option.value, option]));
  const defaults: DayOption[] = [
    { value: 0, label: t('Mon'), selected: false, duration: '' },
    { value: 1, label: t('Tue'), selected: false, duration: '' },
    { value: 2, label: t('Wed'), selected: false, duration: '' },
    { value: 3, label: t('Thu'), selected: false, duration: '' },
    { value: 4, label: t('Fri'), selected: false, duration: '' },
    { value: 5, label: t('Sat'), selected: false, duration: '' },
    { value: 6, label: t('Sun'), selected: false, duration: '' },
  ];
  return defaults.map((option) => ({
    ...option,
    selected: previous.get(option.value)?.selected ?? option.selected,
    duration: previous.get(option.value)?.duration ?? option.duration,
  }));
}

Component({
  data: {
    tr: copy(),
    loading: true,
    capabilityAvailable: false,
    capabilities: [] as PlanGenerationCapability[],
    capability: null as PlanGenerationCapability | null,
    road10kMode: false,
    capabilityMessage: copy().supportedGoal,
    purposeOptions: [] as PurposeOption[],
    purposeIndex: 0,
    selectedPurpose: null as PlanGenerationPurposeSelection | null,
    currentGoalId: '',
    currentGoalRevision: '',
    currentGoalUnavailable: false,
    purposeIsSeparate: false,
    activePlanNeedsReassessment: false,
    proposalMatchesPurpose: true,
    proposalPurposeLabel: '',
    adult: false,
    selfCoached: false,
    canComplete: false,
    outdoorRoad: false,
    safetyStop: false,
    dayOptions: dayOptions(),
    selectedDayRows: [] as DayOption[],
    perDayLimitConflict: false,
    longDayOptions: [copy().noPreference],
    longDayIndex: 0,
    weeklyTimeLimit: '',
    singleSessionLimit: '',
    benchmarkDate: '',
    readiness: null as (
      | Outdoor5KReadinessResponse
      | Outdoor5KGenerateResponse
      | Outdoor5KRegenerateResponse
      | Road10KReadinessResponse
      | Road10KGenerateResponse
      | Road10KRegenerateResponse
      | null
    ),
    readinessReason: '',
    readinessBadge: '',
    readinessContextRows: [] as Array<{ label: string; value: string }>,
    readinessHistory: '',
    readinessAlternatives: [] as string[],
    readinessIsPlanReady: false,
    showBaselineRefreshPanel: false,
    proposal: null as AdaptivePlanProposal | null,
    proposalStateLabel: '',
    working: '',
    operationKeys: {} as Partial<Record<LifecycleOperation, string>>,
    errorMessage: '',
    notice: '',
  },
  lifetimes: {
    attached() {
      void this.refresh();
    },
  },
  methods: {
    async refresh() {
      const tr = copy();
      const options = dayOptions(this.data.dayOptions);
      const selectedDayRows = options.filter((option) => option.selected);
      this.setData({
        tr,
        dayOptions: options,
        selectedDayRows,
        longDayOptions: [tr.noPreference, ...selectedDayRows.map((option) => option.label)],
        longDayIndex: Math.min(this.data.longDayIndex, selectedDayRows.length),
      });
      await this.load();
    },
    operationKey(operation: LifecycleOperation): string {
      const existing = this.data.operationKeys[operation];
      if (existing) return existing;
      const next = uuid();
      this.setData({ operationKeys: { ...this.data.operationKeys, [operation]: next } });
      return next;
    },
    clearOperationKey(operation: LifecycleOperation) {
      const operationKeys = { ...this.data.operationKeys };
      delete operationKeys[operation];
      this.setData({ operationKeys });
    },
    async load(): Promise<void> {
      const componentState = this as unknown as Record<string, unknown>;
      const previousRequestId = typeof componentState._loadRequestId === 'number'
        ? componentState._loadRequestId
        : 0;
      const requestId = previousRequestId + 1;
      componentState._loadRequestId = requestId;
      this.setData({
        loading: true,
        capabilities: [],
        capability: null,
        road10kMode: false,
        capabilityAvailable: false,
        capabilityMessage: this.data.tr.supportedGoal,
        purposeOptions: [],
        purposeIndex: 0,
        selectedPurpose: null,
        currentGoalId: '',
        currentGoalRevision: '',
        currentGoalUnavailable: false,
        purposeIsSeparate: false,
        activePlanNeedsReassessment: false,
        proposalMatchesPurpose: true,
        proposalPurposeLabel: '',
        proposal: null,
        proposalStateLabel: '',
        readiness: null,
        readinessReason: '',
        readinessBadge: '',
        readinessContextRows: [],
        readinessHistory: '',
        readinessAlternatives: [],
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
        notice: '',
      });
      let proposal: AdaptivePlanProposal | null = null;
      let proposalError = '';
      try {
        proposal = await apiGet<AdaptivePlanProposal>(
          '/api/plan/proposals/current',
        );
      } catch (error) {
        const apiError = error as ApiError;
        if (apiError.status !== 404) {
          proposalError = apiError.detail ?? this.data.tr.requestFailed;
        }
      }
      if (componentState._loadRequestId !== requestId) return;
      try {
        const discovery = await apiGet<PlanGenerationCapabilitiesResponse>(
          '/api/plan/generation/capabilities',
        );
        if (componentState._loadRequestId !== requestId) return;
        const capabilities = discovery.capabilities.filter(
          (item) => [
            'outdoor_road_5k_constraints_v1',
            'outdoor_road_10k_constraints_v1',
          ].includes(item.constraint_schema_id),
        );
        const currentCapability = [
          'outdoor_road_5k_constraints_v1',
          'outdoor_road_10k_constraints_v1',
        ].includes(discovery.selected_capability?.constraint_schema_id ?? '')
          ? discovery.selected_capability
          : null;
        const capabilityAvailable = Boolean(
          currentCapability && discovery.current_goal,
        ) || capabilities.some(
          (item) => item.purpose.allows_capability_goal
            || item.purpose.allows_unlinked,
        );
        const purposeOptions: PurposeOption[] = [{
          value: '',
          label: this.data.tr.choosePurpose,
          capabilityId: '',
          source: '',
        }];
        if (currentCapability && discovery.current_goal) {
          purposeOptions.push({
            value: purposeValue('current_goal', currentCapability.id),
            label: `${this.data.tr.currentGoalPurpose} · ${
              discovery.current_goal.goal.distance?.toUpperCase() ?? '5K'
            }`,
            capabilityId: currentCapability.id,
            source: 'current_goal',
          });
        }
        for (const item of capabilities) {
          const distance = item.purpose.distance?.toUpperCase() ?? '5K';
          if (item.purpose.allows_capability_goal) {
            purposeOptions.push({
              value: purposeValue('capability', item.id),
              label: `${this.data.tr.separatePurpose} · ${distance}`,
              capabilityId: item.id,
              source: 'capability',
            });
          }
          if (item.purpose.allows_unlinked) {
            purposeOptions.push({
              value: purposeValue('unlinked', item.id),
              label: `${this.data.tr.unlinkedPurpose} · ${distance}`,
              capabilityId: item.id,
              source: 'unlinked',
            });
          }
        }
        const proposalCapability = capabilities.find(
          (item) => item.policy_version === proposal?.policy_version,
        ) ?? null;
        const proposalSource = proposal?.goal?.purpose_source
          ?? (proposalCapability && currentCapability?.id === proposalCapability.id
            ? 'current_goal'
            : null);
        const proposalValue = proposalCapability && proposalSource
          ? purposeValue(proposalSource, proposalCapability.id)
          : '';
        const pendingPurpose = getApp<IAppOption>().globalData
          .pendingPlanStartPurpose;
        const pendingValue = pendingPurpose
          ? purposeValue(
            pendingPurpose.source,
            pendingPurpose.capability_id,
          )
          : '';
        const pendingPurposeIndex = pendingValue
          && (
            pendingPurpose?.source !== 'current_goal'
            || (
              pendingPurpose.expected_goal_id === discovery.current_goal?.id
              && pendingPurpose.expected_goal_revision
                === discovery.current_goal?.revision
            )
          )
          ? purposeOptions.findIndex(
            (option) => option.value === pendingValue,
          )
          : -1;
        let purposeIndex = proposalValue
          ? purposeOptions.findIndex((option) => option.value === proposalValue)
          : pendingPurposeIndex >= 0
            ? pendingPurposeIndex
            : currentCapability
              ? purposeOptions.findIndex(
                (option) => option.value
                  === purposeValue('current_goal', currentCapability.id),
              )
              : 0;
        if (purposeIndex < 0) purposeIndex = 0;
        if (pendingPurpose) {
          getApp<IAppOption>().globalData.pendingPlanStartPurpose = null;
        }
        const selectedOption = purposeOptions[purposeIndex];
        const capability = capabilities.find(
          (item) => item.id === selectedOption?.capabilityId,
        ) ?? null;
        const selectedPurpose = selectedOption?.source && capability
          ? {
            capability_id: capability.id,
            source: selectedOption.source,
            expected_goal_id: selectedOption.source === 'current_goal'
              ? discovery.current_goal?.id ?? null
              : null,
            expected_goal_revision: selectedOption.source === 'current_goal'
              ? discovery.current_goal?.revision ?? null
              : null,
          } as PlanGenerationPurposeSelection
          : null;
        const road10kMode = isRoad10KCapability(capability);
        const proposalMatchesPurpose = !proposal || Boolean(
          proposalCapability
          && proposalValue
          && proposalValue === selectedOption?.value,
        );
        this.setData({
          loading: false,
          capabilities,
          capability,
          road10kMode,
          capabilityAvailable,
          capabilityMessage: discovery.capabilities.length > 0
            && !capabilityAvailable
            ? this.data.tr.updateRequired
            : this.data.tr.supportedGoal,
          purposeOptions,
          purposeIndex,
          selectedPurpose,
          currentGoalId: discovery.current_goal?.id ?? '',
          currentGoalRevision: discovery.current_goal?.revision ?? '',
          currentGoalUnavailable: Boolean(
            discovery.current_goal && !currentCapability,
          ),
          purposeIsSeparate: Boolean(
            selectedPurpose
            && selectedPurpose.source !== 'current_goal',
          ),
          activePlanNeedsReassessment:
            discovery.active_plan_goal?.link_status
              === 'reassessment_required',
          proposal,
          proposalMatchesPurpose,
          proposalStateLabel: proposalStateLabel(proposal, this.data.tr),
          proposalPurposeLabel: proposalSource === 'current_goal'
            ? this.data.tr.currentGoalPurpose
            : proposalSource === 'capability'
              ? this.data.tr.separatePurpose
              : proposalSource === 'unlinked'
                ? this.data.tr.unlinkedPurpose
                : '',
          errorMessage: proposalError,
          benchmarkDate: road10kMode ? this.data.benchmarkDate : '',
        });
      } catch (error) {
        if (componentState._loadRequestId !== requestId) return;
        const apiError = error as Partial<ApiError>;
        this.setData({
          loading: false,
          capabilities: [],
          capability: null,
          road10kMode: false,
          capabilityAvailable: false,
          purposeOptions: [],
          selectedPurpose: null,
          proposal,
          proposalMatchesPurpose: !proposal,
          proposalStateLabel: proposalStateLabel(proposal, this.data.tr),
          proposalPurposeLabel: proposal?.goal?.purpose_source === 'current_goal'
            ? this.data.tr.currentGoalPurpose
            : proposal?.goal?.purpose_source === 'capability'
              ? this.data.tr.separatePurpose
              : proposal?.goal?.purpose_source === 'unlinked'
                ? this.data.tr.unlinkedPurpose
                : '',
          capabilityMessage: this.data.tr.requestFailed,
          errorMessage: apiError.detail
            ?? (proposalError || this.data.tr.requestFailed),
        });
      }
    },
    onPurposeChange(e: WechatMiniprogram.PickerChange) {
      if (this.data.working) return;
      const purposeIndex = Number(e.detail.value);
      const option = this.data.purposeOptions[purposeIndex];
      const capability = this.data.capabilities.find(
        (item) => item.id === option?.capabilityId,
      ) ?? null;
      const selectedPurpose = option?.source && capability
        ? {
          capability_id: capability.id,
          source: option.source,
          expected_goal_id: option.source === 'current_goal'
            ? this.data.currentGoalId || null
            : null,
          expected_goal_revision: option.source === 'current_goal'
            ? this.data.currentGoalRevision || null
            : null,
        } as PlanGenerationPurposeSelection
        : null;
      const road10kMode = isRoad10KCapability(capability);
      const proposal = this.data.proposal;
      const proposalCapability = this.data.capabilities.find(
        (item) => item.policy_version === proposal?.policy_version,
      );
      const proposalSource = proposal?.goal?.purpose_source
        ?? (proposalCapability ? 'current_goal' : null);
      const proposalValue = proposalCapability && proposalSource
        ? purposeValue(proposalSource, proposalCapability.id)
        : '';
      this.setData({
        purposeIndex,
        selectedPurpose,
        capability,
        road10kMode,
        purposeIsSeparate: Boolean(
          selectedPurpose
          && selectedPurpose.source !== 'current_goal',
        ),
        proposalMatchesPurpose: !proposal || Boolean(
          proposalCapability
          && proposalValue
          && proposalValue === option?.value,
        ),
        readiness: null,
        readinessReason: '',
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
        notice: '',
      });
    },
    onToggleScope(e: WechatMiniprogram.TouchEvent) {
      const field = String(e.currentTarget.dataset.field);
      if (!['adult', 'selfCoached', 'canComplete', 'outdoorRoad'].includes(field)) return;
      this.setData({ [field]: !this.data[field as keyof typeof this.data] } as WechatMiniprogram.IAnyObject);
      this.setData({ readiness: null, readinessIsPlanReady: false, showBaselineRefreshPanel: false, errorMessage: '' });
    },
    onToggleSafety() {
      this.setData({ safetyStop: !this.data.safetyStop, readiness: null, readinessIsPlanReady: false, showBaselineRefreshPanel: false, errorMessage: '' });
    },
    onToggleDay(e: WechatMiniprogram.TouchEvent) {
      const day = Number(e.currentTarget.dataset.day);
      const options = this.data.dayOptions.map((option) => (
        option.value === day
          ? { ...option, selected: !option.selected, duration: option.selected ? '' : option.duration }
          : option
      ));
      const selectedDayRows = options.filter((option) => option.selected);
      this.setData({
        dayOptions: options,
        selectedDayRows,
        perDayLimitConflict: new Set(
          selectedDayRows.map((option) => option.duration.trim()).filter(Boolean),
        ).size > 1,
        longDayOptions: [this.data.tr.noPreference, ...selectedDayRows.map((option) => option.label)],
        longDayIndex: 0,
        readiness: null,
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
      });
    },
    onDurationInput(e: WechatMiniprogram.Input) {
      const day = Number(e.currentTarget.dataset.day);
      const duration = String(e.detail.value ?? '');
      const dayOptions = this.data.dayOptions.map((option) => (
        option.value === day ? { ...option, duration } : option
      ));
      this.setData({
        dayOptions,
        selectedDayRows: dayOptions.filter((option) => option.selected),
        perDayLimitConflict: new Set(
          dayOptions
            .filter((option) => option.selected)
            .map((option) => option.duration.trim())
            .filter(Boolean),
        ).size > 1,
        readiness: null,
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
      });
    },
    onLongDayChange(e: WechatMiniprogram.PickerChange) {
      this.setData({ longDayIndex: Number(e.detail.value), readiness: null, readinessIsPlanReady: false, showBaselineRefreshPanel: false, errorMessage: '' });
    },
    onWeeklyTimeLimitInput(e: WechatMiniprogram.Input) {
      this.setData({
        weeklyTimeLimit: String(e.detail.value ?? ''),
        readiness: null,
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
      });
    },
    onSingleSessionLimitInput(e: WechatMiniprogram.Input) {
      this.setData({
        singleSessionLimit: String(e.detail.value ?? ''),
        readiness: null,
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
      });
    },
    onBenchmarkDateChange(e: WechatMiniprogram.PickerChange) {
      this.setData({
        benchmarkDate: String(e.detail.value ?? ''),
        readiness: null,
        readinessIsPlanReady: false,
        showBaselineRefreshPanel: false,
        errorMessage: '',
      });
    },
    constraints(): Outdoor5KConstraintsRequest | Road10KConstraintsRequest | null {
      const purpose = this.data.selectedPurpose;
      if (!purpose) {
        this.setData({ errorMessage: this.data.tr.purposeRequired });
        return null;
      }
      const road10kMode = this.data.road10kMode;
      if (road10kMode) {
        const days = this.data.dayOptions.filter((option) => option.selected);
        const weeklyTimeLimit = Number(this.data.weeklyTimeLimit);
        const singleSessionLimit = Number(this.data.singleSessionLimit);
        if (!this.data.adult) {
          this.setData({ errorMessage: this.data.tr.road10kScopeRequired });
          return null;
        }
        if (days.length === 0) {
          this.setData({ errorMessage: this.data.tr.daysRequired });
          return null;
        }
        if (!Number.isInteger(weeklyTimeLimit) || weeklyTimeLimit <= 0) {
          this.setData({ errorMessage: this.data.tr.weeklyLimitRequired });
          return null;
        }
        if (!Number.isInteger(singleSessionLimit) || singleSessionLimit <= 0) {
          this.setData({ errorMessage: this.data.tr.singleSessionRequired });
          return null;
        }
        return {
          purpose,
          adult_confirmed: this.data.adult,
          current_symptom_stop: this.data.safetyStop,
          available_weekdays: days.map((option) => option.value),
          weekly_time_limit_min: weeklyTimeLimit,
          maximum_session_duration_min: singleSessionLimit,
          unavailable_dates: [],
          preferred_longest_easy_weekday: this.data.longDayIndex === 0
            ? null
            : days[this.data.longDayIndex - 1]?.value ?? null,
          benchmark_date: this.data.benchmarkDate || null,
        };
      }
      const scopeComplete = this.data.adult
        && this.data.selfCoached
        && this.data.canComplete
        && this.data.outdoorRoad;
      if (!scopeComplete) {
        this.setData({ errorMessage: this.data.tr.scopeRequired });
        return null;
      }
      const days = this.data.dayOptions.filter((option) => option.selected);
      if (days.length === 0) {
        this.setData({ errorMessage: this.data.tr.daysRequired });
        return null;
      }
      const values = days.map((option) => option.duration.trim());
      const limit = Number(values[0]);
      if (
        values.some((value) => value === '')
        || new Set(values).size !== 1
        || !Number.isInteger(limit)
        || limit < 1
      ) {
        this.setData({
          errorMessage: new Set(values).size > 1
            ? this.data.tr.perDayUnsupportedDetail
            : this.data.tr.durationRequired,
        });
        return null;
      }
      const preferredIndex = this.data.longDayIndex;
      return {
        purpose,
        age_18_or_older: this.data.adult,
        self_coached_recreational_road_runner: this.data.selfCoached,
        can_complete_5k: this.data.canComplete,
        safety_stop: this.data.safetyStop,
        outdoor_road_goal_confirmed: this.data.outdoorRoad,
        available_weekdays: days.map((option) => option.value),
        maximum_session_duration_min: limit,
        preferred_longest_run_weekday: preferredIndex === 0 ? null : days[preferredIndex - 1]?.value ?? null,
      };
    },
    async checkReadiness(): Promise<Outdoor5KReadinessResponse | Road10KReadinessResponse | null> {
      const constraints = this.constraints();
      const capability = this.data.capability;
      if (!constraints || !capability) return null;
      this.setData({ working: 'readiness', errorMessage: '', notice: '' });
      try {
        const readiness = await apiPost<Outdoor5KReadinessResponse | Road10KReadinessResponse>(
          capability.actions.readiness_href,
          constraints,
        );
        const context = road10kReadinessContext(readiness, this.data.tr);
        this.setData({
          readiness,
          readinessReason: reason(readiness.result, this.data.tr.noExplanation),
          readinessBadge: readinessBadge(readiness.result, this.data.tr),
          readinessContextRows: context.rows,
          readinessHistory: context.history,
          readinessAlternatives: readinessAlternatives(
            readiness.result,
            this.data.tr,
          ),
          readinessIsPlanReady: isPlanReadyResult(readiness.result),
          showBaselineRefreshPanel: needsBaselineReview(readiness.result),
          working: '',
        });
        return readiness;
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ working: '', errorMessage: apiError.detail ?? this.data.tr.requestFailed });
        return null;
      }
    },
    async onCheckReadiness() {
      if (this.data.working) return;
      await this.checkReadiness();
    },
    async onBaselineRefresh() {
      if (this.data.working) return;
      await this.checkReadiness();
    },
    async onGenerate() {
      if (this.data.working) return;
      if (this.data.proposal && !this.data.proposalMatchesPurpose) {
        this.setData({ errorMessage: this.data.tr.conflictingPurpose });
        return;
      }
      const readiness = await this.checkReadiness();
      const constraints = this.constraints();
      const capability = this.data.capability;
      if (!readiness || !constraints || !capability || !isPlanReadyResult(readiness.result)) return;
      const requestPurpose = constraints.purpose;
      this.setData({ working: 'generate', errorMessage: '' });
      try {
        const response = await apiPost<Outdoor5KGenerateResponse | Road10KGenerateResponse>(capability.actions.generate_href, {
          ...constraints,
          expected_source_revision: readiness.source_revision,
          idempotency_key: this.operationKey('generate'),
        });
        if (proposalResponse(response) && response.proposal) {
          const proposalMatchesPurpose = samePurposeSelection(
            response.purpose,
            requestPurpose,
          ) && samePurposeSelection(
            requestPurpose,
            this.data.selectedPurpose,
          );
          this.setData({
            proposal: response.proposal,
            proposalStateLabel: proposalStateLabel(
              response.proposal,
              this.data.tr,
            ),
            proposalMatchesPurpose,
            proposalPurposeLabel: requestPurpose?.source === 'current_goal'
              ? this.data.tr.currentGoalPurpose
              : requestPurpose?.source === 'capability'
                ? this.data.tr.separatePurpose
                : requestPurpose?.source === 'unlinked'
                  ? this.data.tr.unlinkedPurpose
                  : '',
            notice: this.data.tr.noProposal,
          });
        } else {
          const context = road10kReadinessContext(response, this.data.tr);
          this.setData({
            readiness: response,
            readinessReason: reason(response.result, this.data.tr.noExplanation),
            readinessBadge: readinessBadge(response.result, this.data.tr),
            readinessContextRows: context.rows,
            readinessHistory: context.history,
            readinessAlternatives: readinessAlternatives(
              response.result,
              this.data.tr,
            ),
            readinessIsPlanReady: isPlanReadyResult(response.result),
            showBaselineRefreshPanel: needsBaselineReview(response.result),
          });
        }
        this.clearOperationKey('generate');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    onRegenerate() {
      if (!this.data.road10kMode) {
        void this.performRegenerate();
        return;
      }
      wx.showModal({
        title: roadCopy('proposal.regen_title'),
        content: roadCopy('proposal.regen_body'),
        confirmText: roadCopy('action.regenerate'),
        cancelText: roadCopy('action.cancel'),
        success: (result) => {
          if (result.confirm) void this.performRegenerate();
        },
      });
    },
    async performRegenerate() {
      if (this.data.working) return;
      if (!this.data.proposalMatchesPurpose) {
        this.setData({ errorMessage: this.data.tr.conflictingPurpose });
        return;
      }
      const proposal = this.data.proposal;
      const readiness = await this.checkReadiness();
      const constraints = this.constraints();
      const capability = this.data.capability;
      if (!proposal || !readiness || !constraints || !capability || !isPlanReadyResult(readiness.result)) return;
      const requestPurpose = constraints.purpose;
      this.setData({ working: 'regenerate', errorMessage: '' });
      try {
        const response = await apiPost<Outdoor5KRegenerateResponse | Road10KRegenerateResponse>(
          capability.actions.regenerate_href_template.replace(
            '{proposal_id}',
            encodeURIComponent(proposal.id),
          ),
          {
            ...constraints,
            expected_source_revision: readiness.source_revision,
            expected_proposal_version: proposal.version,
            idempotency_key: this.operationKey('regenerate'),
          },
        );
        if (proposalResponse(response) && response.proposal) {
          const proposalMatchesPurpose = samePurposeSelection(
            response.purpose,
            requestPurpose,
          ) && samePurposeSelection(
            requestPurpose,
            this.data.selectedPurpose,
          );
          this.setData({
            proposal: response.proposal,
            proposalStateLabel: proposalStateLabel(
              response.proposal,
              this.data.tr,
            ),
            proposalMatchesPurpose,
            proposalPurposeLabel: requestPurpose?.source === 'current_goal'
              ? this.data.tr.currentGoalPurpose
              : requestPurpose?.source === 'capability'
                ? this.data.tr.separatePurpose
                : requestPurpose?.source === 'unlinked'
                  ? this.data.tr.unlinkedPurpose
                  : '',
            activePlanNeedsReassessment: proposalMatchesPurpose
              ? false
              : this.data.activePlanNeedsReassessment,
            notice: this.data.tr.successor,
          });
        } else {
          const context = road10kReadinessContext(response, this.data.tr);
          this.setData({
            readiness: response,
            readinessReason: reason(response.result, this.data.tr.noExplanation),
            readinessBadge: readinessBadge(response.result, this.data.tr),
            readinessContextRows: context.rows,
            readinessHistory: context.history,
            readinessAlternatives: readinessAlternatives(
              response.result,
              this.data.tr,
            ),
            readinessIsPlanReady: isPlanReadyResult(response.result),
            showBaselineRefreshPanel: needsBaselineReview(response.result),
          });
        }
        this.clearOperationKey('regenerate');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    onReject() {
      if (!this.data.road10kMode) {
        void this.performReject();
        return;
      }
      wx.showModal({
        title: roadCopy('proposal.reject_title'),
        content: roadCopy('proposal.reject_body'),
        confirmText: roadCopy('action.reject'),
        cancelText: roadCopy('action.cancel'),
        success: (result) => {
          if (result.confirm) void this.performReject();
        },
      });
    },
    async performReject() {
      if (this.data.working) return;
      const proposal = this.data.proposal;
      if (!proposal) return;
      this.setData({ working: 'reject', errorMessage: '' });
      try {
        await apiPost<AdaptivePlanProposal>(
          `/api/plan/proposals/${proposal.id}/reject`,
          { expected_version: proposal.version, idempotency_key: this.operationKey('reject') },
        );
        this.setData({
          proposal: null,
          proposalMatchesPurpose: true,
          proposalPurposeLabel: '',
          notice: this.data.tr.rejected,
          proposalStateLabel: '',
        });
        this.clearOperationKey('reject');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    onReviewLater() {
      this.setData({
        notice: roadCopy('success.later'),
        errorMessage: '',
      });
    },
    onAdopt() {
      if (!this.data.road10kMode) {
        void this.performAdopt();
        return;
      }
      const version = String(this.data.proposal?.version ?? '');
      wx.showModal({
        title: roadCopy('proposal.adopt_title'),
        content: roadCopy('proposal.adopt_body').replace(
          '{version}',
          version,
        ),
        confirmText: roadCopy('action.adopt'),
        cancelText: roadCopy('action.cancel'),
        success: (result) => {
          if (result.confirm) void this.performAdopt();
        },
      });
    },
    async performAdopt() {
      if (this.data.working) return;
      if (!this.data.proposalMatchesPurpose) {
        this.setData({ errorMessage: this.data.tr.conflictingPurpose });
        return;
      }
      if (
        this.data.activePlanNeedsReassessment
        && this.data.proposal?.goal?.purpose_source === 'current_goal'
      ) {
        this.setData({ errorMessage: this.data.tr.adoptionPaused });
        return;
      }
      const proposal = this.data.proposal;
      if (!proposal) return;
      this.setData({ working: 'adopt', errorMessage: '' });
      try {
        const result = await apiPost<AdaptivePlanProposalAdoptResponse>(
          `/api/plan/proposals/${proposal.id}/adopt`,
          {
            expected_proposal_version: proposal.version,
            expected_plan_version: proposal.adaptive_plan?.version ?? proposal.base_plan_version,
            idempotency_key: this.operationKey('adopt'),
          },
        );
        this.setData({
          proposal: result.proposal,
          proposalStateLabel: proposalStateLabel(
            result.proposal,
            this.data.tr,
          ),
          notice: result.status === 'already_adopted'
            ? (
              this.data.road10kMode
                ? roadCopy('success.adopted').replace(
                  '{version}',
                  String(result.proposal.version),
                )
                : this.data.tr.alreadyAdopted
            )
            : (
              this.data.road10kMode
                ? roadCopy('success.adopted').replace(
                  '{version}',
                  String(result.proposal.version),
                )
                : this.data.tr.adopted
            ),
        });
        this.clearOperationKey('adopt');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    onRefreshProposal() {
      void this.load();
    },
  },
});
