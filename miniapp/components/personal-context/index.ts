import {
  apiDelete,
  apiGet,
  apiPost,
} from '../../utils/api-client';
import type { ApiError } from '../../utils/api-client';
import { detectLocale, t, tFmt } from '../../utils/i18n';
import { formatWorkoutType } from '../../utils/managed-plan';
import {
  AI_CONSENT_VERSION,
  EXECUTION_CATEGORIES,
  PURPOSE_CONSENT_VERSION,
  TEMPORARY_CATEGORIES,
  aiFieldNames,
  addLocalDays,
  buildContextDraftRequest,
  contextIdempotencyKey,
  defaultContextDraft,
  hydrateContextDraft,
  localIsoDate,
  narrativeAvailable,
  type MiniContextDraft,
} from '../../utils/personal-context';
import type {
  PersonalContextAiConsentResponse,
  PersonalContextCategory,
  PersonalContextDetailResponse,
  PersonalContextDraftRequest,
  PersonalContextFieldValue,
  PersonalContextItem,
  PersonalContextListResponse,
  PersonalContextMutationResponse,
  PersonalContextPreviewResponse,
  PlanResponse,
  PlannedWorkout,
} from '../../types/api';
import { setTabBarHidden } from '../../utils/tabbar';

interface ContextItemView {
  id: string;
  category: string;
  kind: string;
  state: string;
  expiry: string;
  ai: string;
}

interface ContextFieldView {
  key: string;
  label: string;
  value: string;
}

interface ChoiceView {
  value: string;
  label: string;
  selected: boolean;
}

interface WorkoutView {
  id: string;
  label: string;
  date: string;
}

interface UseReceiptView {
  id: string;
  consumer: string;
  usedAt: string;
  fields: string;
}

const CATEGORY_LABELS: Record<PersonalContextCategory, () => string> = {
  less_time: () => t('Less time'),
  unavailable_day: () => t('Unavailable day'),
  schedule_conflict: () => t('Schedule conflict'),
  caregiving: () => t('Caregiving'),
  travel: () => t('Travel'),
  fatigue: () => t('Fatigue'),
  motivation: () => t('Motivation'),
  illness: () => t('Illness'),
  pain_or_injury: () => t('Pain or injury'),
  red_flag_symptoms: () => t('Red-flag symptoms'),
  weather: () => t('Weather'),
  equipment_access: () => t('Equipment access'),
  other: () => t('Other'),
  prefer_not_to_say: () => t('Prefer not to say'),
};

const SAFETY_CATEGORIES = new Set<PersonalContextCategory>([
  'illness',
  'pain_or_injury',
  'red_flag_symptoms',
]);

const WEEKDAY_CHOICES = [
  ['monday', 'Mon'],
  ['tuesday', 'Tue'],
  ['wednesday', 'Wed'],
  ['thursday', 'Thu'],
  ['friday', 'Fri'],
  ['saturday', 'Sat'],
  ['sunday', 'Sun'],
] as const;

const EQUIPMENT_CHOICES = [
  ['none', 'None'],
  ['treadmill', 'Treadmill'],
  ['track', 'Track'],
  ['gym', 'Gym'],
  ['bike', 'Bike'],
  ['elliptical', 'Elliptical'],
  ['pool', 'Pool'],
] as const;

const TERRAIN_CHOICES = [
  ['road', 'Road'],
  ['trail', 'Trail'],
  ['track', 'Track'],
  ['treadmill', 'Treadmill'],
  ['flat', 'Flat'],
  ['hilly', 'Hilly'],
] as const;

const FIELD_LABELS: Record<string, () => string> = {
  affected_dates: () => t('Affected dates'),
  affected_days: () => t('Affected weekdays'),
  maximum_available_minutes: () => t('Maximum training minutes per day'),
  available_equipment: () => t('Available equipment'),
  available_terrain: () => t('Available terrain'),
  workout_status: () => t('Workout status'),
};

const FIELD_VALUE_LABELS: Record<string, () => string> = Object.fromEntries(
  [
    ...WEEKDAY_CHOICES,
    ...EQUIPMENT_CHOICES,
    ...TERRAIN_CHOICES,
    ['missed', 'Missed'],
    ['modified', 'Modified'],
  ].map(([value, label]) => [value, () => t(label)]),
);

function setCurrentTabBarHidden(hidden: boolean): void {
  const pages = getCurrentPages();
  const page = pages[pages.length - 1] as
    | { getTabBar?: unknown }
    | undefined;
  if (page) setTabBarHidden(page, hidden);
}

function translations() {
  return {
    title: t('Plan context'),
    description: t(
      'Share only what could change your plan. Praxys keeps it private, never guesses why training changed, and leaves AI off unless you separately allow it.',
    ),
    addAvailability: t('Add availability'),
    explainWorkout: t('Explain a workout'),
    manage: t('Manage'),
    retry: t('Retry'),
    loading: t('Loading private context'),
    loadFailed: t('Private context could not be loaded.'),
    emptyTitle: t('No private context saved'),
    emptyDetail: t(
      'That is a complete state, not missing data. Praxys keeps the reason unknown and does not reduce your standing or invent an explanation.',
    ),
    privacyBoundary: t(
      'Encrypted at rest · excluded from analytics and model training',
    ),
    active: t('Active'),
    expired: t('Expired'),
    withdrawn: t('Withdrawn'),
    deleting: t('Deleting'),
    workoutExplanation: t('Workout explanation'),
    temporaryAvailability: t('Temporary availability'),
    rulesOnly: t('rules only'),
    aiAllowed: t('AI allowed'),
    noExpiry: t('no expiry'),
    close: t('Close'),
    back: t('Back'),
    chooseCategory: t('Choose a category'),
    category: t('Category'),
    workout: t('Workout'),
    chooseWorkout: t('Choose a recent workout'),
    loadingWorkouts: t('Loading recent workouts…'),
    noRecentWorkout: t('No recent Praxys workout is available to link.'),
    whatHappened: t('What happened?'),
    missed: t('Missed'),
    modified: t('Modified'),
    starts: t('Starts'),
    ends: t('Ends'),
    maximumMinutes: t('Maximum minutes available per affected day'),
    optional: t('(optional)'),
    affectedWeekdays: t('Affected weekdays (optional)'),
    equipmentAvailable: t('Equipment still available (optional)'),
    terrainAvailable: t('Terrain still available (optional)'),
    note: t('Private note (optional)'),
    notePlaceholder: t('Share only what changes your plan.'),
    noteSafety: t(
      'Avoid names, diagnoses, precise locations, and other private details. Notes are deleted after 30 days even when the structured context remains.',
    ),
    preferUnknown: t(
      'Praxys will preserve the reason as unknown. This never counts against you.',
    ),
    safety: t(
      'This enters the safety path and stops ordinary performance optimization. Praxys cannot diagnose, clear you to train, or set a return-to-sport timeline.',
    ),
    reviewPurpose: t('Review purpose and expiry'),
    reviewTitle: t('Review before saving'),
    purpose: t('Purpose'),
    planPurpose: t('Suggest adjustments to the current plan'),
    workoutPurpose: t('Interpret this workout without guessing a cause'),
    activeUntil: t('Active until'),
    storedUntil: t('Stored until'),
    noteDeleted: t('Note deleted'),
    processing: t('Processing method'),
    rulesNoAi: t('Rules only · nothing sent to AI'),
    purposeConfirmation: t(
      'Saving confirms this one purpose. It does not authorize a new purpose, AI processing, analytics, or model training.',
    ),
    confirmPurpose: t('I confirm this purpose and expiry'),
    save: t('Save private context'),
    saveCorrection: t('Save correction'),
    correctTitle: t('Correct private context'),
    contextSaved: t('Private context saved. AI processing remains off.'),
    unknownSaved: t(
      'Saved without guessing a reason. The cause remains unknown.',
    ),
    manageTitle: t('Manage private context'),
    export: t('Export context'),
    exportCopied: t('Private context JSON copied'),
    inspectTitle: t('Private context'),
    inspectDescription: t(
      'Inspect what is stored, where it was used, and who may process it.',
    ),
    status: t('Status'),
    aiProcessing: t('AI processing'),
    allowedForItem: t('Allowed for this item'),
    unavailableForSafety: t('Unavailable for safety context'),
    off: t('Off'),
    structuredDetails: t('Structured details'),
    contextUse: t('Context use'),
    unused: t('No assessment or plan change has used this context yet.'),
    rules: t('Rules'),
    azureOpenAi: t('Microsoft Azure AI'),
    correct: t('Correct'),
    aiOption: t('AI option'),
    reviewAi: t('Review AI access'),
    stopUsing: t('Stop using'),
    delete: t('Delete'),
    stopTitle: t('Stop using this context?'),
    stopDetail: t(
      'It stays in your private history until its purge date, but cannot influence a new assessment.',
    ),
    deleteTitle: t('Delete this context permanently?'),
    deleteDetail: t(
      'Praxys also removes dependent private reasoning and use receipts. Accepted workout changes remain without the private reason.',
    ),
    cancel: t('Cancel'),
    stopped: t('Context excluded from future assessments.'),
    deleted: t('Context and dependent private traces deleted.'),
    aiTitle: t('AI processing for one item'),
    aiDescription: t(
      'This decision is separate from saving context and applies only to this exact version.',
    ),
    provider: t('AI service: Microsoft Azure'),
    providerDetail: t(
      'Only the fields below are sent to Microsoft Azure AI. Microsoft states that inputs and outputs are not available to OpenAI or used to train foundation models without permission; Praxys does not grant that permission. Flagged content may be reviewed for abuse monitoring under Azure terms. Praxys does not log raw requests or responses.',
    ),
    structuredFieldsSent: t('Structured fields sent'),
    sendNote: t('Also send my optional note'),
    sendNoteDetail: t(
      'Off by default. The note may contain more private detail than the structured fields.',
    ),
    aiWarning: t(
      'AI output can be wrong. It cannot diagnose, provide treatment, clear you to train, or override Praxys safety, science, and approval boundaries.',
    ),
    aiWithdrawal: t(
      'You can withdraw before any later request. Withdrawal cannot recall a request the provider already processed.',
    ),
    allowAi: t('Allow for this item'),
    withdrawAi: t('Withdraw AI permission'),
    aiEnabled: t('AI processing enabled for this item only.'),
    aiWithdrawn: t(
      'AI processing withdrawn. No new provider requests are allowed.',
    ),
    requiredCategory: t('Choose one category to continue.'),
    requiredWorkout: t('Choose the workout that changed.'),
    requiredStatus: t('Choose whether it was missed or modified.'),
    requiredDates: t('Choose when this constraint starts and ends.'),
    invalidDates: t('The end date must be after the start date.'),
    tooLong: t('Temporary context can stay active for at most 90 days.'),
    invalidMinutes: t(
      'Available minutes must be a whole number from 1 to 1440.',
    ),
    reviewFailed: t('Could not review this private context.'),
    saveFailed: t('Could not save this private context.'),
    correctionFailed: t('Could not save this correction.'),
    detailFailed: t('Could not load this private context.'),
    stopFailed: t('Could not stop using this context.'),
    deleteFailed: t('Could not delete this private context.'),
    exportFailed: t('Could not export private context.'),
    aiFailed: t('Could not update AI processing.'),
  };
}

function categoryLabel(category: PersonalContextCategory): string {
  return CATEGORY_LABELS[category]();
}

function formatDate(value: string | null): string {
  if (!value) return t('no expiry');
  return new Date(value).toLocaleDateString(
    detectLocale() === 'zh' ? 'zh-CN' : 'en-US',
    { year: 'numeric', month: 'short', day: 'numeric' },
  );
}

function contextFieldLabel(key: string): string {
  return FIELD_LABELS[key]?.() ?? key.replace(/_/g, ' ');
}

function formatFieldValue(value: PersonalContextFieldValue): string {
  const values = Array.isArray(value) ? value : [value];
  const separator = detectLocale() === 'zh' ? '、' : ', ';
  return values.map((entry) => (
    typeof entry === 'string'
      ? FIELD_VALUE_LABELS[entry]?.() ?? entry
      : String(entry)
  )).join(separator);
}

function disclosedFieldLabel(field: string): string {
  if (field === 'category') return t('Category');
  return contextFieldLabel(field.replace(/^fields\./, ''));
}

function contextFields(item: PersonalContextItem): ContextFieldView[] {
  return Object.entries(item.payload.fields).map(([key, value]) => ({
    key,
    label: contextFieldLabel(key),
    value: formatFieldValue(value),
  }));
}

function itemViews(items: PersonalContextItem[]): ContextItemView[] {
  return items
    .filter((item) => item.latest_version)
    .sort((left, right) => (
      Number(right.state === 'active') - Number(left.state === 'active')
      || right.created_at.localeCompare(left.created_at)
    ))
    .map((item) => ({
      id: item.id,
      category: categoryLabel(item.payload.category),
      kind: item.kind === 'execution_explanation'
        ? t('Workout explanation')
        : t('Temporary availability'),
      state: item.state === 'active'
        ? t('Active')
        : item.state === 'expired'
          ? t('Expired')
          : item.state === 'withdrawn'
            ? t('Withdrawn')
            : t('Deleting'),
      expiry: item.expires_at ? formatDate(item.expires_at) : t('no expiry'),
      ai: item.processing_mode === 'ai_allowed'
        ? t('AI allowed')
        : t('rules only'),
    }));
}

function choiceViews(
  choices: ReadonlyArray<readonly [string, string]>,
  selected: string[],
): ChoiceView[] {
  return choices.map(([value, label]) => ({
    value,
    label: t(label),
    selected: selected.includes(value),
  }));
}

function workoutViews(workouts: PlannedWorkout[]): WorkoutView[] {
  const today = localIsoDate();
  return workouts
    .filter((workout) => (
      Boolean(workout.canonical_id)
      && workout.date <= today
      && workout.workout_type.toLowerCase() !== 'rest'
    ))
    .sort((left, right) => right.date.localeCompare(left.date))
    .map((workout) => ({
      id: workout.canonical_id ?? '',
      date: workout.date,
      label: `${formatDate(`${workout.date}T12:00:00`)} · ${
        t(formatWorkoutType(workout.workout_type))
      }`,
    }));
}

function apiErrorMessage(error: unknown, fallback: string): string {
  const apiError = error as Partial<ApiError>;
  if (apiError.status === 0) return fallback;
  return apiError.detail
    ?? (error instanceof Error ? error.message : fallback);
}

function confirmAction(title: string, content: string): Promise<boolean> {
  return new Promise((resolve) => {
    wx.showModal({
      title,
      content,
      confirmColor: '#b42318',
      success: (result) => resolve(result.confirm),
      fail: () => resolve(false),
    });
  });
}

Component({
  options: { addGlobalClass: true },

  data: {
    tr: translations(),
    loading: true,
    errorMessage: '',
    notice: '',
    rawItems: [] as PersonalContextItem[],
    items: [] as ContextItemView[],
    hasItems: false,
    workouts: [] as WorkoutView[],
    workoutValues: [] as string[],
    workoutLabels: [] as string[],
    workoutIndex: 0,
    sheetOpen: false,
    screen: 'home' as 'home' | 'compose' | 'preview' | 'detail' | 'ai',
    sheetTitle: '',
    working: false,
    actionError: '',
    draft: defaultContextDraft(),
    categoryValues: [...TEMPORARY_CATEGORIES] as PersonalContextCategory[],
    categoryLabels: TEMPORARY_CATEGORIES.map(categoryLabel),
    categoryIndex: 0,
    weekdays: choiceViews(WEEKDAY_CHOICES, []),
    equipment: choiceViews(EQUIPMENT_CHOICES, []),
    terrain: choiceViews(TERRAIN_CHOICES, []),
    preview: null as PersonalContextPreviewResponse | null,
    previewRequest: null as PersonalContextDraftRequest | null,
    previewFields: [] as ContextFieldView[],
    previewExpiry: '',
    previewPurge: '',
    previewNarrativePurge: '',
    purposeConfirmed: false,
    editingItem: null as PersonalContextItem | null,
    selectedItem: null as PersonalContextItem | null,
    detail: null as PersonalContextDetailResponse | null,
    detailRequestId: 0,
    detailFields: [] as ContextFieldView[],
    detailExpiry: '',
    detailNarrativePurge: '',
    useReceipts: [] as UseReceiptView[],
    hasUseReceipts: false,
    hasContextUse: false,
    linkedRevisionText: '',
    selectedSafety: false,
    selectedNarrativeAvailable: false,
    aiFields: [] as string[],
    aiFieldsText: '',
    aiPermissionConfirmed: false,
    aiNarrative: false,
    safetySelected: false,
    showEquipment: false,
    showTerrain: false,
    today: localIsoDate(),
    maximumEndDate: addLocalDays(localIsoDate(), 89),
  },

  lifetimes: {
    attached() {
      this.setData({ tr: translations() });
      void this.refresh();
    },
    detached() {
      setCurrentTabBarHidden(false);
    },
  },

  observers: {
    sheetOpen(sheetOpen: boolean) {
      setCurrentTabBarHidden(sheetOpen);
    },
  },

  pageLifetimes: {
    show() {
      if (!this.data.loading) void this.refresh();
    },
  },

  methods: {
    async refresh() {
      this.setData({ loading: true, errorMessage: '' });
      const today = localIsoDate();
      const start = addLocalDays(today, -21);
      try {
        const [context, plan] = await Promise.all([
          apiGet<PersonalContextListResponse>(
            '/api/personal-context?include_history=false&include_narrative=false', // i18n-allow
          ),
          apiGet<PlanResponse>(`/api/plan?start=${start}&end=${today}`),
        ]);
        const workouts = workoutViews(plan.workouts);
        this.setData({
          loading: false,
          rawItems: context.items,
          items: itemViews(context.items),
          hasItems: context.items.some((item) => item.latest_version),
          workouts,
          workoutValues: workouts.map((workout) => workout.id),
          workoutLabels: workouts.map((workout) => workout.label),
          workoutIndex: 0,
        });
      } catch (error) {
        const apiError = error as Partial<ApiError>;
        if (apiError.code === 'UNAUTHENTICATED') {
          this.setData({ loading: false });
          return;
        }
        this.setData({
          loading: false,
          errorMessage: apiErrorMessage(error, this.data.tr.loadFailed),
        });
      }
    },

    onRetry() {
      void this.refresh();
    },

    onOpenManage() {
      this.setData({
        sheetOpen: true,
        screen: 'home',
        sheetTitle: this.data.tr.manageTitle,
        actionError: '',
      });
    },

    onAddAvailability() {
      this.openComposer('temporary_constraint');
    },

    onExplainWorkout() {
      this.openComposer('execution_explanation');
    },

    openComposer(kind: MiniContextDraft['kind']) {
      const draft = defaultContextDraft(kind);
      if (kind === 'execution_explanation' && this.data.workouts.length > 0) {
        const workout = this.data.workouts[0] as WorkoutView;
        draft.workoutId = workout.id;
        draft.workoutDate = workout.date;
      }
      this.applyDraft(draft, null);
      this.setData({
        sheetOpen: true,
        screen: 'compose',
        sheetTitle: kind === 'execution_explanation'
          ? this.data.tr.explainWorkout
          : this.data.tr.addAvailability,
        actionError: '',
      });
    },

    applyDraft(draft: MiniContextDraft, editingItem: PersonalContextItem | null) {
      const categories = draft.kind === 'execution_explanation'
        ? EXECUTION_CATEGORIES
        : TEMPORARY_CATEGORIES;
      const workoutIndex = Math.max(
        0,
        this.data.workoutValues.indexOf(draft.workoutId),
      );
      this.setData({
        draft,
        editingItem,
        categoryValues: [...categories],
        categoryLabels: categories.map(categoryLabel),
        categoryIndex: Math.max(0, categories.indexOf(draft.category)),
        workoutIndex,
        weekdays: choiceViews(WEEKDAY_CHOICES, draft.availableDays),
        equipment: choiceViews(EQUIPMENT_CHOICES, draft.equipment),
        terrain: choiceViews(TERRAIN_CHOICES, draft.terrain),
        preview: null,
        previewRequest: null,
        purposeConfirmed: false,
        safetySelected: SAFETY_CATEGORIES.has(draft.category),
        showEquipment:
          draft.category === 'equipment_access' || draft.category === 'travel',
        showTerrain: draft.category === 'weather' || draft.category === 'travel',
        maximumEndDate: addLocalDays(draft.startDate, 89),
      });
    },

    onCloseSheet() {
      if (this.data.working) return;
      this.setData({
        sheetOpen: false,
        actionError: '',
        preview: null,
        previewRequest: null,
        selectedItem: null,
        detail: null,
        detailRequestId: this.data.detailRequestId + 1,
      });
    },

    onBack() {
      if (this.data.working) return;
      if (this.data.screen === 'preview') {
        this.setData({
          screen: 'compose',
          sheetTitle: this.data.editingItem
            ? this.data.tr.correctTitle
            : this.data.draft.kind === 'execution_explanation'
              ? this.data.tr.explainWorkout
              : this.data.tr.addAvailability,
          preview: null,
          previewRequest: null,
          purposeConfirmed: false,
          actionError: '',
        });
        return;
      }
      this.setData({
        screen: 'home',
        sheetTitle: this.data.tr.manageTitle,
        actionError: '',
        selectedItem: null,
        detail: null,
        detailRequestId: this.data.detailRequestId + 1,
      });
    },

    stopPropagation() {
      // Prevent taps inside the bottom sheet from closing the backdrop.
    },

    onCategoryChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const index = Number(event.detail.value);
      const category = this.data.categoryValues[index] as PersonalContextCategory;
      this.setData({
        categoryIndex: index,
        'draft.category': category,
        safetySelected: SAFETY_CATEGORIES.has(category),
        showEquipment:
          category === 'equipment_access' || category === 'travel',
        showTerrain: category === 'weather' || category === 'travel',
      });
    },

    onWorkoutChange(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const index = Number(event.detail.value);
      const workout = this.data.workouts[index] as WorkoutView | undefined;
      this.setData({
        workoutIndex: index,
        'draft.workoutId': workout?.id ?? '',
        'draft.workoutDate': workout?.date ?? '',
      });
    },

    onWorkoutStatus(event: WechatMiniprogram.TouchEvent) {
      const status = event.currentTarget.dataset.status as 'missed' | 'modified';
      this.setData({ 'draft.workoutStatus': status });
    },

    onStartDate(
      event: WechatMiniprogram.CustomEvent<{ value: string }>,
    ) {
      const startDate = event.detail.value;
      const maximumEndDate = addLocalDays(startDate, 89);
      this.setData({
        'draft.startDate': startDate,
        'draft.endDate': this.data.draft.endDate < startDate
          ? startDate
          : this.data.draft.endDate > maximumEndDate
            ? maximumEndDate
            : this.data.draft.endDate,
        maximumEndDate,
      });
    },

    onEndDate(event: WechatMiniprogram.CustomEvent<{ value: string }>) {
      this.setData({ 'draft.endDate': event.detail.value });
    },

    onMaximumMinutes(
      event: WechatMiniprogram.Input,
    ) {
      this.setData({ 'draft.maximumMinutes': event.detail.value });
    },

    onNarrative(event: WechatMiniprogram.TextareaInput) {
      this.setData({ 'draft.narrative': event.detail.value });
    },

    onToggleChoice(event: WechatMiniprogram.TouchEvent) {
      const group = event.currentTarget.dataset.group as
        | 'weekdays'
        | 'equipment'
        | 'terrain';
      const value = String(event.currentTarget.dataset.value ?? '');
      const draftField = group === 'weekdays'
        ? 'availableDays'
        : group;
      const current = this.data.draft[draftField] as string[];
      const next = current.includes(value)
        ? current.filter((entry) => entry !== value)
        : [...current, value];
      this.setData({
        [`draft.${draftField}`]: next,
        [group]: choiceViews(
          group === 'weekdays'
            ? WEEKDAY_CHOICES
            : group === 'equipment'
              ? EQUIPMENT_CHOICES
              : TERRAIN_CHOICES,
          next,
        ),
      });
    },

    validateDraft(): string {
      const draft = this.data.draft as MiniContextDraft;
      if (!draft.category) return this.data.tr.requiredCategory;
      if (draft.kind === 'execution_explanation') {
        if (!draft.workoutId) return this.data.tr.requiredWorkout;
        if (!draft.workoutStatus) return this.data.tr.requiredStatus;
        return '';
      }
      if (!draft.startDate || !draft.endDate) return this.data.tr.requiredDates;
      const start = new Date(`${draft.startDate}T00:00:00`);
      const end = new Date(`${draft.endDate}T23:59:59`);
      if (end <= start) return this.data.tr.invalidDates;
      if (end.getTime() - start.getTime() > 90 * 24 * 60 * 60 * 1000) {
        return this.data.tr.tooLong;
      }
      if (draft.maximumMinutes.trim()) {
        const minutes = Number(draft.maximumMinutes);
        if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
          return this.data.tr.invalidMinutes;
        }
      }
      return '';
    },

    async onReviewDraft() {
      const validation = this.validateDraft();
      if (validation) {
        this.setData({ actionError: validation });
        return;
      }
      this.setData({ working: true, actionError: '' });
      try {
        const request = buildContextDraftRequest(
          this.data.draft as MiniContextDraft,
        );
        const preview = await apiPost<PersonalContextPreviewResponse>(
          '/api/personal-context/preview',
          request,
        );
        this.setData({
          working: false,
          screen: 'preview',
          sheetTitle: this.data.tr.reviewTitle,
          preview,
          previewRequest: request,
          previewFields: Object.entries(preview.payload.fields).map(
            ([key, value]) => ({
              key,
              label: key.replace(/_/g, ' '),
              value: formatFieldValue(value),
            }),
          ),
          previewExpiry: formatDate(preview.expires_at),
          previewPurge: formatDate(preview.purge_after),
          previewNarrativePurge: formatDate(preview.narrative_purge_at),
          purposeConfirmed: false,
        });
      } catch (error) {
        this.setData({
          working: false,
          actionError: apiErrorMessage(error, this.data.tr.reviewFailed),
        });
      }
    },

    onPurposeConfirmation(
      event: WechatMiniprogram.SwitchChange,
    ) {
      this.setData({ purposeConfirmed: event.detail.value });
    },

    async onSaveDraft() {
      if (
        !this.data.purposeConfirmed
        || !this.data.preview
        || !this.data.previewRequest
      ) return;
      const preview = this.data.preview as PersonalContextPreviewResponse;
      const request = this.data.previewRequest as PersonalContextDraftRequest;
      this.setData({ working: true, actionError: '' });
      try {
        let result: PersonalContextMutationResponse;
        if (this.data.editingItem) {
          const item = this.data.editingItem as PersonalContextItem;
          result = await apiPost<PersonalContextMutationResponse>(
            `/api/personal-context/${encodeURIComponent(item.id)}/correct`,
            {
              expected_version: item.version,
              payload: preview.payload,
              starts_at: preview.starts_at,
              expires_at: preview.expires_at,
              purge_after: preview.purge_after,
              narrative_purge_at: preview.narrative_purge_at,
              consent_text_version: PURPOSE_CONSENT_VERSION,
              client: 'miniapp',
            },
            {
              headers: {
                'Idempotency-Key': contextIdempotencyKey('correct'),
              },
            },
          );
        } else {
          result = await apiPost<PersonalContextMutationResponse>(
            '/api/personal-context/confirm',
            {
              ...request,
              payload: preview.payload,
              linked_subject_type: preview.linked_subject_type,
              linked_subject_id: preview.linked_subject_id,
              starts_at: preview.starts_at,
              expires_at: preview.expires_at,
              purge_after: preview.purge_after,
              narrative_purge_at: preview.narrative_purge_at,
              consent_text_version: PURPOSE_CONSENT_VERSION,
              client: 'miniapp',
            },
            {
              headers: {
                'Idempotency-Key': contextIdempotencyKey('confirm'),
              },
            },
          );
        }
        this.setData({
          working: false,
          screen: 'home',
          sheetTitle: this.data.tr.manageTitle,
          notice: result.item.payload.category === 'prefer_not_to_say'
            ? this.data.tr.unknownSaved
            : this.data.tr.contextSaved,
          preview: null,
          previewRequest: null,
          editingItem: null,
          purposeConfirmed: false,
        });
        await this.refresh();
      } catch (error) {
        this.setData({
          working: false,
          actionError: apiErrorMessage(
            error,
            this.data.editingItem
              ? this.data.tr.correctionFailed
              : this.data.tr.saveFailed,
          ),
        });
      }
    },

    async onInspect(event: WechatMiniprogram.TouchEvent) {
      const id = String(event.currentTarget.dataset.id ?? '');
      const item = this.data.rawItems.find(
        (candidate: PersonalContextItem) => candidate.id === id,
      ) as PersonalContextItem | undefined;
      if (!item) return;
      const detailRequestId = this.data.detailRequestId + 1;
      this.setData({
        sheetOpen: true,
        screen: 'detail',
        sheetTitle: categoryLabel(item.payload.category),
        selectedItem: item,
        detail: null,
        detailRequestId,
        detailFields: contextFields(item),
        detailExpiry: formatDate(item.expires_at),
        detailNarrativePurge: formatDate(item.narrative_purge_at),
        useReceipts: [],
        hasUseReceipts: false,
        hasContextUse: false,
        linkedRevisionText: '',
        selectedSafety: SAFETY_CATEGORIES.has(item.payload.category),
        selectedNarrativeAvailable: narrativeAvailable(item),
        working: true,
        actionError: '',
      });
      try {
        const detail = await apiGet<PersonalContextDetailResponse>(
          `/api/personal-context/${encodeURIComponent(id)}?include_narrative=true`,
        );
        if (this.data.detailRequestId !== detailRequestId) return;
        this.setData({
          working: false,
          selectedItem: detail.item,
          detail,
          detailFields: contextFields(detail.item),
          detailExpiry: formatDate(detail.item.expires_at),
          detailNarrativePurge: formatDate(detail.item.narrative_purge_at),
          useReceipts: detail.use_receipts.map((receipt) => ({
            id: receipt.id,
            consumer: receipt.consumer_type === 'deterministic_policy'
              ? this.data.tr.rules
              : this.data.tr.azureOpenAi,
            usedAt: formatDate(receipt.used_at),
            fields: receipt.disclosed_fields.join(', '),
          })),
          hasUseReceipts: detail.use_receipts.length > 0,
          hasContextUse:
            detail.use_receipts.length > 0
            || detail.linked_revision_ids.length > 0,
          linkedRevisionText: detail.linked_revision_ids.length > 0
            ? tFmt(
              'Referenced by {0} plan change record(s).',
              detail.linked_revision_ids.length,
            )
            : '',
          selectedSafety:
            SAFETY_CATEGORIES.has(detail.item.payload.category),
          selectedNarrativeAvailable: narrativeAvailable(detail.item),
        });
      } catch (error) {
        if (this.data.detailRequestId !== detailRequestId) return;
        this.setData({
          working: false,
          actionError: apiErrorMessage(error, this.data.tr.detailFailed),
        });
      }
    },

    onCorrect() {
      const item = this.data.selectedItem as PersonalContextItem | null;
      if (!item || !this.data.detail) return;
      const draft = hydrateContextDraft(item);
      this.applyDraft(draft, item);
      this.setData({
        screen: 'compose',
        sheetTitle: this.data.tr.correctTitle,
        actionError: '',
      });
    },

    async onExpire() {
      const item = this.data.selectedItem as PersonalContextItem | null;
      if (!item) return;
      if (!await confirmAction(this.data.tr.stopTitle, this.data.tr.stopDetail)) {
        return;
      }
      this.setData({ working: true, actionError: '' });
      try {
        await apiPost(
          `/api/personal-context/${encodeURIComponent(item.id)}/expire`,
          { expected_version: item.version },
        );
        this.setData({
          working: false,
          screen: 'home',
          sheetTitle: this.data.tr.manageTitle,
          selectedItem: null,
          detail: null,
          notice: this.data.tr.stopped,
        });
        await this.refresh();
      } catch (error) {
        this.setData({
          working: false,
          actionError: apiErrorMessage(error, this.data.tr.stopFailed),
        });
      }
    },

    async onDelete() {
      const item = this.data.selectedItem as PersonalContextItem | null;
      if (!item) return;
      if (!await confirmAction(
        this.data.tr.deleteTitle,
        this.data.tr.deleteDetail,
      )) return;
      this.setData({ working: true, actionError: '' });
      try {
        await apiDelete<void>(
          `/api/personal-context/${encodeURIComponent(item.id)}?expected_version=${item.version}`,
        );
        this.setData({
          working: false,
          screen: 'home',
          sheetTitle: this.data.tr.manageTitle,
          selectedItem: null,
          detail: null,
          notice: this.data.tr.deleted,
        });
        await this.refresh();
      } catch (error) {
        this.setData({
          working: false,
          actionError: apiErrorMessage(error, this.data.tr.deleteFailed),
        });
      }
    },

    onOpenAi() {
      const item = this.data.selectedItem as PersonalContextItem | null;
      if (!item || !this.data.detail) return;
      if (
        SAFETY_CATEGORIES.has(item.payload.category)
        && item.processing_mode !== 'ai_allowed'
      ) return;
      this.setData({
        screen: 'ai',
        sheetTitle: this.data.tr.aiTitle,
        aiFields: aiFieldNames(item),
        aiFieldsText: aiFieldNames(item)
          .map(disclosedFieldLabel)
          .join(detectLocale() === 'zh' ? '、' : ', '),
        aiPermissionConfirmed: false,
        aiNarrative: false,
        actionError: '',
      });
    },

    onAiPermission(
      event: WechatMiniprogram.SwitchChange,
    ) {
      this.setData({ aiPermissionConfirmed: event.detail.value });
    },

    onAiNarrative(
      event: WechatMiniprogram.SwitchChange,
    ) {
      if (!this.data.selectedNarrativeAvailable) return;
      this.setData({ aiNarrative: event.detail.value });
    },

    async onDecideAi() {
      const item = this.data.selectedItem as PersonalContextItem | null;
      if (!item) return;
      const granting = item.processing_mode !== 'ai_allowed';
      if (granting && SAFETY_CATEGORIES.has(item.payload.category)) return;
      if (granting && !this.data.aiPermissionConfirmed) return;
      this.setData({ working: true, actionError: '' });
      try {
        const result = await apiPost<PersonalContextAiConsentResponse>(
          `/api/personal-context/${encodeURIComponent(item.id)}/ai-consent`,
          {
            expected_version: item.version,
            decision: granting ? 'granted' : 'withdrawn',
            provider: granting ? 'azure_openai' : null,
            disclosed_fields: granting ? aiFieldNames(item) : [],
            narrative_disclosed: granting && this.data.aiNarrative,
            consent_text_version: AI_CONSENT_VERSION,
            client: 'miniapp',
          },
          {
            headers: {
              'Idempotency-Key': contextIdempotencyKey(
                granting ? 'ai-grant' : 'ai-withdraw',
              ),
            },
          },
        );
        this.setData({
          working: false,
          screen: 'home',
          sheetTitle: this.data.tr.manageTitle,
          selectedItem: null,
          detail: null,
          notice: result.item.processing_mode === 'ai_allowed'
            ? this.data.tr.aiEnabled
            : this.data.tr.aiWithdrawn,
        });
        await this.refresh();
      } catch (error) {
        this.setData({
          working: false,
          actionError: apiErrorMessage(error, this.data.tr.aiFailed),
        });
      }
    },

    async onExport() {
      this.setData({ working: true, actionError: '' });
      try {
        const exported = await apiGet<unknown>('/api/personal-context/export');
        await new Promise<void>((resolve, reject) => {
          wx.setClipboardData({
            data: JSON.stringify(exported, null, 2),
            success: () => resolve(),
            fail: reject,
          });
        });
        this.setData({
          working: false,
          notice: this.data.tr.exportCopied,
        });
      } catch (error) {
        this.setData({
          working: false,
          actionError: apiErrorMessage(error, this.data.tr.exportFailed),
        });
      }
    },
  },
});
