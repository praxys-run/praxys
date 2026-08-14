import { apiGet, apiPost } from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { t } from '../../utils/i18n';
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
} from '../../types/api';

interface DayOption {
  value: Outdoor5KWeekday;
  label: string;
  selected: boolean;
  duration: string;
}

type LifecycleOperation = 'generate' | 'regenerate' | 'reject' | 'adopt';

function copy() {
  return {
    title: t('Plan preview'),
    unsupportedTitle: t('Plan generation for this goal'),
    supportedGoal: t('No accepted automatic policy matches this goal yet. Praxys keeps manual plan management available instead of repurposing the 5K policy.'),
    updateRequired: t('This client does not recognize the selected policy input contract and will not guess how to create a plan.'),
    scope: t('Scope and guardrails'),
    scopeDetail: t('For adult, self-coached recreational outdoor-road 5K runners. This is not a diagnosis, clearance, or performance guarantee.'),
    adult: t('I am 18 or older.'),
    selfCoached: t('I am self-coached for recreational road running.'),
    canComplete: t('I can currently complete 5 km.'),
    outdoorRoad: t('My goal is an outdoor road 5K.'),
    safety: t('Safety stop'),
    safetyDetail: t('Tell Praxys if a safety stop applies. The policy will stop this path and show its bounded alternatives.'),
    safetyOff: t('No safety stop'),
    safetyOn: t('Safety stop applies'),
    days: t('Available run days'),
    dayDetail: t('Select availability, then give the same supported session limit for every selected day.'),
    timeLimit: t('Time limit (minutes)'),
    perDayUnsupported: t('Per-day limits are unsupported'),
    perDayUnsupportedDetail: t('The accepted deterministic policy has one shared maximum-session field. Praxys will not invent a per-day rule or silently reduce your schedule; use one limit for all selected days.'),
    longDay: t('Preferred longest-run day'),
    noPreference: t('No preference'),
    terrain: t('Terrain and equipment'),
    terrainDetail: t('This policy supports outdoor road running only. Terrain, treadmill, trail, and equipment preferences are unsupported inputs and are not inferred.'),
    check: t('Check readiness'),
    checking: t('Checking readiness…'),
    create: t('Create proposal'),
    creating: t('Creating proposal…'),
    result: t('Readiness result'),
    proposal: t('Plan proposal'),
    policy: t('Policy'),
    generator: t('Generator'),
    science: t('Science'),
    proposalNotPlan: t('This proposal is not yet your plan. It cannot deliver workouts until after explicit adoption and separate delivery consent.'),
    inputsOnly: t('Workout content is view-only in this deterministic policy. Change the bounded inputs above and regenerate to create an immutable successor; Praxys never constructs replacement workouts in this client.'),
    regenerate: t('Regenerate successor'),
    regenerating: t('Regenerating…'),
    adopt: t('Adopt exact proposal'),
    adopting: t('Adopting…'),
    reject: t('Reject or defer'),
    rejecting: t('Rejecting…'),
    deliveryDisabled: t('Delivery remains disabled. Review the existing 14-day managed-delivery preview and explicitly consent only if you want Praxys to deliver this canonical plan.'),
    refresh: t('Refresh proposal'),
    retry: t('Retry'),
    ready: t('ready'),
    failed: t('Plan-start action did not complete'),
    scopeRequired: t('Confirm the supported athlete and goal scope first.'),
    daysRequired: t('Choose the days you are available to run.'),
    durationRequired: t('Enter one whole-minute limit for every selected day.'),
    requestFailed: t('Could not assess this plan start.'),
    noExplanation: t('The deterministic policy returned no additional explanation.'),
    noProposal: t('Proposal created. It has not changed your canonical plan.'),
    successor: t('A successor proposal is ready. The earlier proposal is preserved as superseded.'),
    rejected: t('Proposal rejected. Your canonical plan was not changed.'),
    adopted: t('Plan adopted. Delivery remains disabled until you explicitly enable it.'),
    alreadyAdopted: t('This exact proposal was already adopted. Delivery remains disabled until you explicitly enable it.'),
    lifecycle: t('Proposal state needs a fresh preview'),
    lifecycleDetail: t('This proposal cannot mutate the canonical plan. Review readiness and create a new proposal when you are ready.'),
  };
}

function uuid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function proposalResponse(
  response: Outdoor5KGenerateResponse | Outdoor5KRegenerateResponse,
): response is Extract<Outdoor5KGenerateResponse, { proposal: AdaptivePlanProposal | null }> {
  return 'proposal' in response;
}

function reason(result: Outdoor5KOutcomeResponse, fallback: string): string {
  return result.observed_or_stated_reason
    ?? result.uncertainty_or_missing_field
    ?? fallback;
}

function dayOptions(): DayOption[] {
  return [
    { value: 0, label: t('Mon'), selected: false, duration: '' },
    { value: 1, label: t('Tue'), selected: false, duration: '' },
    { value: 2, label: t('Wed'), selected: false, duration: '' },
    { value: 3, label: t('Thu'), selected: false, duration: '' },
    { value: 4, label: t('Fri'), selected: false, duration: '' },
    { value: 5, label: t('Sat'), selected: false, duration: '' },
    { value: 6, label: t('Sun'), selected: false, duration: '' },
  ];
}

Component({
  data: {
    tr: copy(),
    loading: true,
    capabilityAvailable: false,
    capability: null as PlanGenerationCapability | null,
    capabilityMessage: copy().supportedGoal,
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
    readiness: null as Outdoor5KReadinessResponse | Outdoor5KGenerateResponse | Outdoor5KRegenerateResponse | null,
    readinessReason: '',
    proposal: null as AdaptivePlanProposal | null,
    working: '',
    operationKeys: {} as Partial<Record<LifecycleOperation, string>>,
    errorMessage: '',
    notice: '',
  },
  lifetimes: {
    attached() {
      void this.load();
    },
  },
  methods: {
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
    async refresh(): Promise<void> {
      await this.load();
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
        capability: null,
        capabilityAvailable: false,
        capabilityMessage: this.data.tr.supportedGoal,
        proposal: null,
        readiness: null,
        readinessReason: '',
        errorMessage: '',
        notice: '',
      });
      try {
        const discovery = await apiGet<PlanGenerationCapabilitiesResponse>(
          '/api/plan/generation/capabilities',
        );
        if (componentState._loadRequestId !== requestId) return;
        const capability = discovery.selected_capability;
        const capabilityAvailable = capability?.constraint_schema_id
          === 'outdoor_road_5k_constraints_v1';
        let proposal: AdaptivePlanProposal | null = null;
        let proposalError = '';
        if (capabilityAvailable) {
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
        }
        if (componentState._loadRequestId !== requestId) return;
        this.setData({
          loading: false,
          capability,
          capabilityAvailable,
          capabilityMessage: capability && !capabilityAvailable
            ? this.data.tr.updateRequired
            : this.data.tr.supportedGoal,
          proposal: proposal?.policy_version === capability?.policy_version
            ? proposal
            : null,
          errorMessage: proposalError,
        });
      } catch (error) {
        if (componentState._loadRequestId !== requestId) return;
        const apiError = error as Partial<ApiError>;
        this.setData({
          loading: false,
          capability: null,
          capabilityAvailable: false,
          proposal: null,
          capabilityMessage: this.data.tr.requestFailed,
          errorMessage: apiError.detail ?? this.data.tr.requestFailed,
        });
      }
    },
    onToggleScope(e: WechatMiniprogram.TouchEvent) {
      const field = String(e.currentTarget.dataset.field);
      if (!['adult', 'selfCoached', 'canComplete', 'outdoorRoad'].includes(field)) return;
      this.setData({ [field]: !this.data[field as keyof typeof this.data] } as WechatMiniprogram.IAnyObject);
      this.setData({ readiness: null, errorMessage: '' });
    },
    onToggleSafety() {
      this.setData({ safetyStop: !this.data.safetyStop, readiness: null, errorMessage: '' });
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
        errorMessage: '',
      });
    },
    onLongDayChange(e: WechatMiniprogram.PickerChange) {
      this.setData({ longDayIndex: Number(e.detail.value), readiness: null, errorMessage: '' });
    },
    constraints(): Outdoor5KConstraintsRequest | null {
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
    async checkReadiness(): Promise<Outdoor5KReadinessResponse | null> {
      const constraints = this.constraints();
      const capability = this.data.capability;
      if (!constraints || !capability) return null;
      this.setData({ working: 'readiness', errorMessage: '', notice: '' });
      try {
        const readiness = await apiPost<Outdoor5KReadinessResponse>(
          capability.actions.readiness_href,
          constraints,
        );
        this.setData({
          readiness,
          readinessReason: reason(readiness.result, this.data.tr.noExplanation),
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
    async onGenerate() {
      if (this.data.working) return;
      const readiness = await this.checkReadiness();
      const constraints = this.constraints();
      const capability = this.data.capability;
      if (!readiness || !constraints || !capability || readiness.result.code !== 'ready') return;
      this.setData({ working: 'generate', errorMessage: '' });
      try {
        const response = await apiPost<Outdoor5KGenerateResponse>(capability.actions.generate_href, {
          ...constraints,
          expected_source_revision: readiness.source_revision,
          idempotency_key: this.operationKey('generate'),
        });
        if (proposalResponse(response) && response.proposal) {
          this.setData({ proposal: response.proposal, notice: this.data.tr.noProposal });
        } else {
          this.setData({ readiness: response, readinessReason: reason(response.result, this.data.tr.noExplanation) });
        }
        this.clearOperationKey('generate');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    async onRegenerate() {
      if (this.data.working) return;
      const proposal = this.data.proposal;
      const readiness = await this.checkReadiness();
      const constraints = this.constraints();
      const capability = this.data.capability;
      if (!proposal || !readiness || !constraints || !capability || readiness.result.code !== 'ready') return;
      this.setData({ working: 'regenerate', errorMessage: '' });
      try {
        const response = await apiPost<Outdoor5KRegenerateResponse>(
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
          this.setData({ proposal: response.proposal, notice: this.data.tr.successor });
        } else {
          this.setData({ readiness: response, readinessReason: reason(response.result, this.data.tr.noExplanation) });
        }
        this.clearOperationKey('regenerate');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    async onReject() {
      if (this.data.working) return;
      const proposal = this.data.proposal;
      if (!proposal) return;
      this.setData({ working: 'reject', errorMessage: '' });
      try {
        const result = await apiPost<AdaptivePlanProposal>(
          `/api/plan/proposals/${proposal.id}/reject`,
          { expected_version: proposal.version, idempotency_key: this.operationKey('reject') },
        );
        this.setData({ proposal: result, notice: this.data.tr.rejected });
        this.clearOperationKey('reject');
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        this.setData({ errorMessage: apiError.detail ?? this.data.tr.requestFailed });
      } finally {
        this.setData({ working: '' });
      }
    },
    async onAdopt() {
      if (this.data.working) return;
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
          notice: result.status === 'already_adopted'
            ? this.data.tr.alreadyAdopted
            : this.data.tr.adopted,
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
