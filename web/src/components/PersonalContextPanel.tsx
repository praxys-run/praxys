import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Link } from 'react-router-dom';
import { Trans, useLingui } from '@lingui/react/macro';
import {
  Brain,
  CalendarClock,
  Check,
  ChevronRight,
  Download,
  FilePenLine,
  History,
  LoaderCircle,
  LockKeyhole,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useLocale } from '@/contexts/LocaleContext';
import {
  apiFetch,
  extractErrorMessage,
  useApi,
} from '@/hooks/useApi';
import { isRestWorkoutType } from '@/lib/plan';
import {
  PERSONAL_CONTEXT_AI_CONSENT_VERSION,
  PERSONAL_CONTEXT_PURPOSE_CONSENT_VERSION,
  SAFETY_CONTEXT_CATEGORIES,
  buildPersonalContextDraftRequest,
  createPersonalContextDraft,
  draftFromContextItem,
  personalContextDisclosedFields,
  personalContextIdempotencyKey,
  personalContextNarrativeAvailable,
  type PersonalContextDraftForm,
  type PersonalContextDraftMode,
} from '@/lib/personal-context';
import type {
  PersonalContextAiConsentResponse,
  PersonalContextCategory,
  PersonalContextDetailResponse,
  PersonalContextDraftRequest,
  PersonalContextItem,
  PersonalContextListResponse,
  PersonalContextMutationResponse,
  PersonalContextPreviewResponse,
  PlanResponse,
  PlannedWorkout,
} from '@/types/api';

const DAY_MS = 24 * 60 * 60 * 1000;

interface CategoryOption {
  value: PersonalContextCategory;
  label: string;
  group: string;
}

interface Choice {
  value: string;
  label: string;
}

function localIsoDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function contextPlanUrl(): string {
  const today = new Date();
  const start = new Date(today.getTime() - (21 * DAY_MS));
  const params = new URLSearchParams({
    start: localIsoDate(start),
    end: localIsoDate(today),
  });
  return `/api/plan?${params.toString()}`;
}

async function requestJson<T>(
  url: string,
  init: RequestInit,
  fallback: string,
): Promise<T> {
  const response = await apiFetch(url, init);
  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, fallback));
  }
  return response.json() as Promise<T>;
}

function requestErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError) return fallback;
  return error instanceof Error ? error.message : fallback;
}

function formatWorkoutLabel(
  workout: PlannedWorkout,
  locale: string,
): string {
  const date = new Date(`${workout.date}T12:00:00`);
  const dateLabel = date.toLocaleDateString(
    locale === 'zh' ? 'zh-CN' : 'en-US',
    { month: 'short', day: 'numeric' },
  );
  const type = workout.workout_type
    .split(/[\s_]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
  return `${dateLabel} · ${type}`;
}

function ChoiceChips({
  label,
  choices,
  selected,
  disabled,
  onChange,
}: {
  label: ReactNode;
  choices: Choice[];
  selected: string[];
  disabled: boolean;
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset disabled={disabled}>
      <legend className="mb-2 text-xs font-medium text-foreground">
        {label}
      </legend>
      <div className="flex flex-wrap gap-2">
        {choices.map((choice) => {
          const active = selected.includes(choice.value);
          return (
            <button
              key={choice.value}
              type="button"
              aria-pressed={active}
              disabled={disabled}
              onClick={() => onChange(
                active
                  ? selected.filter((value) => value !== choice.value)
                  : [...selected, choice.value],
              )}
              className={`min-h-9 rounded-full border px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                active
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted/60 hover:text-foreground'
              } disabled:opacity-50`}
            >
              {choice.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function PersonalContextPanel() {
  const { t } = useLingui();
  const { locale } = useLocale();
  const listUrl =
    '/api/personal-context?include_history=false&include_narrative=false';
  const {
    data,
    loading,
    error,
    refetch,
  } = useApi<PersonalContextListResponse>(listUrl);
  const recentPlanUrl = useMemo(() => contextPlanUrl(), []);
  const {
    data: recentPlan,
    loading: recentPlanLoading,
  } = useApi<PlanResponse>(recentPlanUrl);
  const [composerOpen, setComposerOpen] = useState(false);
  const [form, setForm] = useState<PersonalContextDraftForm>(
    () => createPersonalContextDraft('temporary_constraint'),
  );
  const [editingItem, setEditingItem] = useState<PersonalContextItem | null>(null);
  const [preview, setPreview] = useState<PersonalContextPreviewResponse | null>(null);
  const [previewRequest, setPreviewRequest] =
    useState<PersonalContextDraftRequest | null>(null);
  const [composerWorking, setComposerWorking] = useState(false);
  const [composerError, setComposerError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedItem, setSelectedItem] = useState<PersonalContextItem | null>(null);
  const [detail, setDetail] = useState<PersonalContextDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const detailRequestRef = useRef(0);
  const [actionWorking, setActionWorking] = useState('');
  const [actionConfirm, setActionConfirm] = useState<'expire' | 'delete' | ''>('');
  const [aiItem, setAiItem] = useState<PersonalContextItem | null>(null);
  const [aiNarrative, setAiNarrative] = useState(false);
  const [aiWorking, setAiWorking] = useState(false);
  const [aiError, setAiError] = useState('');
  const [exporting, setExporting] = useState(false);

  const categoryOptions: CategoryOption[] = [
    { value: 'less_time', label: t`Less time`, group: t`Availability` },
    { value: 'unavailable_day', label: t`Unavailable day`, group: t`Availability` },
    { value: 'schedule_conflict', label: t`Schedule conflict`, group: t`Availability` },
    { value: 'caregiving', label: t`Caregiving`, group: t`Life constraint` },
    { value: 'travel', label: t`Travel`, group: t`Life constraint` },
    { value: 'fatigue', label: t`Fatigue`, group: t`Training state` },
    { value: 'motivation', label: t`Motivation`, group: t`Training state` },
    { value: 'illness', label: t`Illness`, group: t`Safety` },
    { value: 'pain_or_injury', label: t`Pain or injury`, group: t`Safety` },
    { value: 'red_flag_symptoms', label: t`Red-flag symptoms`, group: t`Safety` },
    { value: 'weather', label: t`Weather`, group: t`Environment` },
    { value: 'equipment_access', label: t`Equipment access`, group: t`Environment` },
    { value: 'other', label: t`Other`, group: t`Disclosure choice` },
    {
      value: 'prefer_not_to_say',
      label: t`Prefer not to say`,
      group: t`Disclosure choice`,
    },
  ];
  const weekdays: Choice[] = [
    { value: 'monday', label: t`Mon` },
    { value: 'tuesday', label: t`Tue` },
    { value: 'wednesday', label: t`Wed` },
    { value: 'thursday', label: t`Thu` },
    { value: 'friday', label: t`Fri` },
    { value: 'saturday', label: t`Sat` },
    { value: 'sunday', label: t`Sun` },
  ];
  const equipment: Choice[] = [
    { value: 'none', label: t`None` },
    { value: 'treadmill', label: t`Treadmill` },
    { value: 'track', label: t`Track` },
    { value: 'gym', label: t`Gym` },
    { value: 'bike', label: t`Bike` },
    { value: 'elliptical', label: t`Elliptical` },
    { value: 'pool', label: t`Pool` },
  ];
  const terrain: Choice[] = [
    { value: 'road', label: t`Road` },
    { value: 'trail', label: t`Trail` },
    { value: 'track', label: t`Track` },
    { value: 'treadmill', label: t`Treadmill` },
    { value: 'flat', label: t`Flat` },
    { value: 'hilly', label: t`Hilly` },
  ];

  const categoryLabel = (value: PersonalContextCategory) => (
    categoryOptions.find((option) => option.value === value)?.label ?? value
  );

  const formatDate = useCallback((value: string | null) => {
    if (!value) return t`No expiry`;
    return new Date(value).toLocaleDateString(
      locale === 'zh' ? 'zh-CN' : 'en-US',
      { year: 'numeric', month: 'short', day: 'numeric' },
    );
  }, [locale, t]);

  const recentWorkouts = useMemo(() => (
    (recentPlan?.workouts ?? [])
      .filter((workout) => (
        Boolean(workout.canonical_id)
        && !isRestWorkoutType(workout.workout_type)
        && workout.date <= localIsoDate(new Date())
      ))
      .sort((left, right) => right.date.localeCompare(left.date))
  ), [recentPlan]);

  const visibleItems = useMemo(() => (
    [...(data?.items ?? [])]
      .filter((item) => item.latest_version)
      .sort((left, right) => {
        const stateRank = (state: PersonalContextItem['state']) => (
          state === 'active' ? 0 : state === 'deleting' ? 1 : 2
        );
        return stateRank(left.state) - stateRank(right.state)
          || right.created_at.localeCompare(left.created_at);
      })
  ), [data]);

  const openCreate = (mode: PersonalContextDraftMode) => {
    setEditingItem(null);
    setForm(createPersonalContextDraft(mode));
    setPreview(null);
    setPreviewRequest(null);
    setComposerError('');
    setComposerOpen(true);
  };

  const openCorrection = (item: PersonalContextItem) => {
    setSelectedItem(null);
    setDetail(null);
    setEditingItem(item);
    setForm(draftFromContextItem(item));
    setPreview(null);
    setPreviewRequest(null);
    setComposerError('');
    setComposerOpen(true);
  };

  const validateForm = (): string | null => {
    if (!form.category) return t`Choose one category to continue.`;
    if (form.narrative.length > 280) {
      return t`Keep the optional note to 280 characters or fewer.`;
    }
    if (form.mode === 'execution_explanation') {
      if (!form.workoutId) return t`Choose the workout that changed.`;
      if (!form.workoutStatus) return t`Choose whether it was missed or modified.`;
      return null;
    }
    if (!form.startDate || !form.endDate) {
      return t`Choose when this constraint starts and ends.`;
    }
    const start = new Date(`${form.startDate}T00:00:00`);
    const end = new Date(`${form.endDate}T23:59:59`);
    if (end <= start) return t`The end date must be after the start date.`;
    if (end.getTime() - start.getTime() > 90 * DAY_MS) {
      return t`Temporary context can stay active for at most 90 days.`;
    }
    if (form.maximumAvailableMinutes.trim()) {
      const minutes = Number(form.maximumAvailableMinutes);
      if (!Number.isInteger(minutes) || minutes < 1 || minutes > 1440) {
        return t`Available minutes must be a whole number from 1 to 1440.`;
      }
    }
    return null;
  };

  const reviewDraft = async () => {
    const validationError = validateForm();
    if (validationError) {
      setComposerError(validationError);
      return;
    }
    setComposerWorking(true);
    setComposerError('');
    try {
      const request = buildPersonalContextDraftRequest(form);
      const result = await requestJson<PersonalContextPreviewResponse>(
        '/api/personal-context/preview',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        },
        t`Could not review this private context.`,
      );
      setPreviewRequest(request);
      setPreview(result);
    } catch (requestError) {
      setComposerError(requestErrorMessage(
        requestError,
        t`Could not review this private context.`,
      ));
    } finally {
      setComposerWorking(false);
    }
  };

  const saveDraft = async () => {
    if (!preview || !previewRequest) return;
    setComposerWorking(true);
    setComposerError('');
    const normalized = {
      ...previewRequest,
      payload: preview.payload,
      linked_subject_type: preview.linked_subject_type,
      linked_subject_id: preview.linked_subject_id,
      starts_at: preview.starts_at,
      expires_at: preview.expires_at,
      purge_after: preview.purge_after,
      narrative_purge_at: preview.narrative_purge_at,
    };
    try {
      let result: PersonalContextMutationResponse;
      if (editingItem) {
        result = await requestJson<PersonalContextMutationResponse>(
          `/api/personal-context/${encodeURIComponent(editingItem.id)}/correct`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Idempotency-Key': personalContextIdempotencyKey(),
            },
            body: JSON.stringify({
              expected_version: editingItem.version,
              payload: normalized.payload,
              starts_at: normalized.starts_at,
              expires_at: normalized.expires_at,
              purge_after: normalized.purge_after,
              narrative_purge_at: normalized.narrative_purge_at,
              consent_text_version:
                PERSONAL_CONTEXT_PURPOSE_CONSENT_VERSION,
              client: 'web',
            }),
          },
          t`Could not save this correction.`,
        );
      } else {
        result = await requestJson<PersonalContextMutationResponse>(
          '/api/personal-context/confirm',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Idempotency-Key': personalContextIdempotencyKey(),
            },
            body: JSON.stringify({
              ...normalized,
              consent_text_version:
                PERSONAL_CONTEXT_PURPOSE_CONSENT_VERSION,
              client: 'web',
            }),
          },
          t`Could not save this private context.`,
        );
      }
      setComposerOpen(false);
      setPreview(null);
      setPreviewRequest(null);
      setEditingItem(null);
      setNotice(
        result.item.payload.category === 'prefer_not_to_say'
          ? t`Saved without guessing a reason. The cause remains unknown.`
          : t`Private context saved. AI processing remains off.`,
      );
      await refetch();
    } catch (requestError) {
      setComposerError(requestErrorMessage(
        requestError,
        editingItem
          ? t`Could not save this correction.`
          : t`Could not save this private context.`,
      ));
    } finally {
      setComposerWorking(false);
    }
  };

  const loadDetail = async (item: PersonalContextItem) => {
    const requestId = ++detailRequestRef.current;
    setSelectedItem(item);
    setDetail(null);
    setDetailError('');
    setActionConfirm('');
    setDetailLoading(true);
    try {
      const result = await requestJson<PersonalContextDetailResponse>(
        `/api/personal-context/${encodeURIComponent(item.id)}?include_narrative=true`,
        { method: 'GET' },
        t`Could not load this private context.`,
      );
      if (detailRequestRef.current === requestId) setDetail(result);
    } catch (requestError) {
      if (detailRequestRef.current === requestId) {
        setDetailError(requestErrorMessage(
          requestError,
          t`Could not load this private context.`,
        ));
      }
    } finally {
      if (detailRequestRef.current === requestId) setDetailLoading(false);
    }
  };

  const refreshAfterItemAction = async () => {
    detailRequestRef.current += 1;
    setSelectedItem(null);
    setDetail(null);
    setActionConfirm('');
    await refetch();
  };

  const expireItem = async (item: PersonalContextItem) => {
    setActionWorking('expire');
    setDetailError('');
    try {
      await requestJson<PersonalContextItem>(
        `/api/personal-context/${encodeURIComponent(item.id)}/expire`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expected_version: item.version }),
        },
        t`Could not stop using this context.`,
      );
      setNotice(t`Context excluded from future assessments.`);
      await refreshAfterItemAction();
    } catch (requestError) {
      setDetailError(requestErrorMessage(
        requestError,
        t`Could not stop using this context.`,
      ));
    } finally {
      setActionWorking('');
    }
  };

  const deleteItem = async (item: PersonalContextItem) => {
    setActionWorking('delete');
    setDetailError('');
    try {
      const response = await apiFetch(
        `/api/personal-context/${encodeURIComponent(item.id)}?expected_version=${item.version}`,
        { method: 'DELETE' },
      );
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(
            response,
            t`Could not delete this private context.`,
          ),
        );
      }
      setNotice(t`Context and dependent private traces deleted.`);
      await refreshAfterItemAction();
    } catch (requestError) {
      setDetailError(requestErrorMessage(
        requestError,
        t`Could not delete this private context.`,
      ));
    } finally {
      setActionWorking('');
    }
  };

  const openAi = (item: PersonalContextItem) => {
    if (
      SAFETY_CONTEXT_CATEGORIES.has(item.payload.category)
      && item.processing_mode !== 'ai_allowed'
    ) return;
    setSelectedItem(null);
    setDetail(null);
    setAiNarrative(false);
    setAiError('');
    setAiItem(item);
  };

  const decideAi = async (
    item: PersonalContextItem,
    decision: 'granted' | 'withdrawn',
  ) => {
    setAiWorking(true);
    setAiError('');
    try {
      const result = await requestJson<PersonalContextAiConsentResponse>(
        `/api/personal-context/${encodeURIComponent(item.id)}/ai-consent`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': personalContextIdempotencyKey(),
          },
          body: JSON.stringify({
            expected_version: item.version,
            decision,
            provider: decision === 'granted' ? 'azure_openai' : null,
            disclosed_fields:
              decision === 'granted'
                ? personalContextDisclosedFields(item)
                : [],
            narrative_disclosed:
              decision === 'granted' && aiNarrative,
            consent_text_version: PERSONAL_CONTEXT_AI_CONSENT_VERSION,
            client: 'web',
          }),
        },
        decision === 'granted'
          ? t`Could not enable AI processing.`
          : t`Could not withdraw AI processing.`,
      );
      setAiItem(null);
      setNotice(
        result.item.processing_mode === 'ai_allowed'
          ? t`AI processing enabled for this item only.`
          : t`AI processing withdrawn. No new provider requests are allowed.`,
      );
      await refetch();
    } catch (requestError) {
      setAiError(requestErrorMessage(
        requestError,
        t`Could not update AI processing.`,
      ));
    } finally {
      setAiWorking(false);
    }
  };

  const exportContext = async () => {
    setExporting(true);
    setNotice('');
    try {
      const response = await apiFetch('/api/personal-context/export');
      if (!response.ok) {
        throw new Error(
          await extractErrorMessage(response, t`Could not export private context.`),
        );
      }
      const blob = new Blob(
        [JSON.stringify(await response.json(), null, 2)],
        { type: 'application/json' },
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'praxys-personal-context-export.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice(t`Private context export downloaded.`);
    } catch (requestError) {
      setNotice(requestErrorMessage(
        requestError,
        t`Could not export private context.`,
      ));
    } finally {
      setExporting(false);
    }
  };

  const currentDetailItem = detail?.item ?? selectedItem;
  const currentDetailIsSafety = currentDetailItem
    ? SAFETY_CONTEXT_CATEGORIES.has(currentDetailItem.payload.category)
    : false;
  const safetySelected = form.category
    ? SAFETY_CONTEXT_CATEGORIES.has(form.category)
    : false;
  const groupedCategories = categoryOptions.reduce<Record<string, CategoryOption[]>>(
    (groups, option) => ({
      ...groups,
      [option.group]: [...(groups[option.group] ?? []), option],
    }),
    {},
  );

  return (
    <section id="plan-context" className="mt-10 border-t border-border pt-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <LockKeyhole className="size-4 text-muted-foreground" aria-hidden="true" />
            <h2 className="text-base font-semibold text-foreground">
              <Trans>Plan context</Trans>
            </h2>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            <Trans>
              Share only what could change your plan. Praxys keeps it private,
              never guesses why training changed, and leaves AI off unless you
              separately allow it.
            </Trans>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => openCreate('execution_explanation')}
          >
            <FilePenLine aria-hidden="true" />
            <Trans>Explain a workout</Trans>
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => openCreate('temporary_constraint')}
          >
            <CalendarClock aria-hidden="true" />
            <Trans>Add availability</Trans>
          </Button>
        </div>
      </div>

      {notice && (
        <Alert className="mt-5 border-primary/25 bg-primary/5">
          <Check className="text-primary" aria-hidden="true" />
          <AlertDescription className="text-xs text-foreground">
            {notice}
          </AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="mt-6 space-y-2" aria-label={t`Loading private context`}>
          <Skeleton className="h-16 rounded-lg" />
          <Skeleton className="h-16 rounded-lg" />
        </div>
      )}

      {!loading && error && (
        <Alert variant="destructive" className="mt-6">
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span><Trans>Private context could not be loaded.</Trans></span>
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <Trans>Retry</Trans>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {!loading && !error && visibleItems.length === 0 && (
        <div className="mt-6 rounded-xl border border-dashed border-border px-4 py-5">
          <p className="text-sm font-medium text-foreground">
            <Trans>No private context saved</Trans>
          </p>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-muted-foreground">
            <Trans>
              That is a complete state, not missing data. Praxys keeps the
              reason unknown and does not reduce your standing or invent an
              explanation.
            </Trans>
          </p>
        </div>
      )}

      {!loading && !error && visibleItems.length > 0 && (
        <div className="mt-6 divide-y divide-border border-y border-border">
          {visibleItems.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => void loadDetail(item)}
              className="group grid min-h-18 w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <span className="min-w-0">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-foreground">
                    {categoryLabel(item.payload.category)}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    item.state === 'active'
                      ? 'bg-primary/10 text-primary'
                      : item.state === 'deleting'
                        ? 'bg-accent-amber/10 text-accent-amber'
                        : 'bg-muted text-muted-foreground'
                  }`}>
                    {item.state === 'active' && <Trans>Active</Trans>}
                    {item.state === 'expired' && <Trans>Expired</Trans>}
                    {item.state === 'withdrawn' && <Trans>Withdrawn</Trans>}
                    {item.state === 'deleting' && <Trans>Deleting</Trans>}
                  </span>
                </span>
                <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                  {item.kind === 'execution_explanation'
                    ? <Trans>Workout explanation</Trans>
                    : <Trans>Temporary availability</Trans>}
                  {' · '}
                  {item.expires_at
                    ? <Trans>until {formatDate(item.expires_at)}</Trans>
                    : <Trans>no expiry</Trans>}
                  {' · '}
                  {item.processing_mode === 'ai_allowed'
                    ? <Trans>AI allowed</Trans>
                    : <Trans>rules only</Trans>}
                </span>
              </span>
              <ChevronRight
                className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </button>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>
          <Trans>Encrypted at rest · excluded from analytics and model training</Trans>
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={exporting}
          onClick={() => void exportContext()}
          className="text-muted-foreground"
        >
          {exporting
            ? <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
            : <Download aria-hidden="true" />}
          <Trans>Export context</Trans>
        </Button>
      </div>

      <Dialog
        open={composerOpen}
        onOpenChange={(open) => {
          if (composerWorking) return;
          setComposerOpen(open);
          if (!open) {
            setPreview(null);
            setPreviewRequest(null);
            setComposerError('');
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {preview
                ? <Trans>Review before saving</Trans>
                : editingItem
                  ? <Trans>Correct private context</Trans>
                  : form.mode === 'execution_explanation'
                    ? <Trans>What changed with this workout?</Trans>
                    : <Trans>What availability changed?</Trans>}
            </DialogTitle>
            <DialogDescription>
              {preview
                ? <Trans>Nothing is stored until you confirm this exact purpose and expiry.</Trans>
                : <Trans>Optional context helps Praxys avoid guessing. Share only what changes the plan.</Trans>}
            </DialogDescription>
          </DialogHeader>

          {!preview && (
            <div className="space-y-5">
              {form.mode === 'execution_explanation' && (
                <div className="space-y-2">
                  <Label htmlFor="context-workout"><Trans>Workout</Trans></Label>
                  {editingItem ? (
                    <p className="rounded-lg border border-border bg-muted/35 px-3 py-2 text-sm text-foreground">
                      {recentWorkouts.find(
                        (workout) => workout.canonical_id === form.workoutId,
                      )
                        ? formatWorkoutLabel(
                          recentWorkouts.find(
                            (workout) => workout.canonical_id === form.workoutId,
                          )!,
                          locale,
                        )
                        : t`Linked workout`}
                    </p>
                  ) : (
                    <select
                      id="context-workout"
                      value={form.workoutId}
                      disabled={composerWorking || recentPlanLoading}
                      onChange={(event) => {
                        const workout = recentWorkouts.find(
                          (candidate) => candidate.canonical_id === event.target.value,
                        );
                        setForm((current) => ({
                          ...current,
                          workoutId: event.target.value,
                          workoutDate: workout?.date ?? '',
                        }));
                      }}
                      className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <option value="">
                        {recentPlanLoading
                          ? t`Loading recent workouts…`
                          : t`Choose a recent workout`}
                      </option>
                      {recentWorkouts.map((workout) => (
                        <option
                          key={workout.canonical_id}
                          value={workout.canonical_id ?? ''}
                        >
                          {formatWorkoutLabel(workout, locale)}
                        </option>
                      ))}
                    </select>
                  )}
                  {!recentPlanLoading && recentWorkouts.length === 0 && (
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      <Trans>No recent Praxys workout is available to link.</Trans>
                    </p>
                  )}
                </div>
              )}

              {form.mode === 'execution_explanation' && (
                <fieldset disabled={composerWorking}>
                  <legend className="mb-2 text-xs font-medium text-foreground">
                    <Trans>What happened?</Trans>
                  </legend>
                  <div className="grid grid-cols-2 gap-2">
                    {([
                      ['missed', t`Missed`],
                      ['modified', t`Modified`],
                    ] as const).map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={form.workoutStatus === value}
                        onClick={() => setForm((current) => ({
                          ...current,
                          workoutStatus: value,
                        }))}
                        className={`min-h-10 rounded-lg border px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                          form.workoutStatus === value
                            ? 'border-primary/40 bg-primary/10 text-primary'
                            : 'border-border bg-background text-muted-foreground hover:bg-muted/60'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </fieldset>
              )}

              <div className="space-y-2">
                <Label htmlFor="context-category">
                  <Trans>Category</Trans>
                </Label>
                <select
                  id="context-category"
                  value={form.category}
                  disabled={composerWorking}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    category: event.target.value as PersonalContextCategory | '',
                  }))}
                  className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value=""><Trans>Choose a category</Trans></option>
                  {Object.entries(groupedCategories).map(([group, options]) => (
                    <optgroup key={group} label={group}>
                      {options.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                {form.category === 'prefer_not_to_say' && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    <Trans>
                      Praxys will preserve the reason as unknown. This never
                      counts against you.
                    </Trans>
                  </p>
                )}
              </div>

              {safetySelected && (
                <Alert className="border-accent-amber/30 bg-accent-amber/8">
                  <ShieldAlert className="text-accent-amber" aria-hidden="true" />
                  <AlertDescription className="text-xs leading-relaxed text-foreground">
                    <Trans>
                      This enters the safety path and stops ordinary performance
                      optimization. Praxys cannot diagnose, clear you to train,
                      or set a return-to-sport timeline.
                    </Trans>
                  </AlertDescription>
                </Alert>
              )}

              {form.mode === 'temporary_constraint' && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="context-start"><Trans>Starts</Trans></Label>
                      <input
                        id="context-start"
                        type="date"
                        value={form.startDate}
                        disabled={composerWorking}
                        onChange={(event) => setForm((current) => ({
                          ...current,
                          startDate: event.target.value,
                        }))}
                        className="h-10 w-full rounded-lg border border-input bg-background px-3 font-data text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="context-end"><Trans>Ends</Trans></Label>
                      <input
                        id="context-end"
                        type="date"
                        min={form.startDate}
                        value={form.endDate}
                        disabled={composerWorking}
                        onChange={(event) => setForm((current) => ({
                          ...current,
                          endDate: event.target.value,
                        }))}
                        className="h-10 w-full rounded-lg border border-input bg-background px-3 font-data text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="context-minutes">
                      <Trans>Maximum minutes available per affected day</Trans>
                      <span className="ml-1 font-normal text-muted-foreground">
                        <Trans>(optional)</Trans>
                      </span>
                    </Label>
                    <input
                      id="context-minutes"
                      type="number"
                      min="1"
                      max="1440"
                      inputMode="numeric"
                      value={form.maximumAvailableMinutes}
                      disabled={composerWorking}
                      onChange={(event) => setForm((current) => ({
                        ...current,
                        maximumAvailableMinutes: event.target.value,
                      }))}
                      className="h-10 w-full rounded-lg border border-input bg-background px-3 font-data text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>

                  <ChoiceChips
                    label={<Trans>Affected weekdays (optional)</Trans>}
                    choices={weekdays}
                    selected={form.affectedDays}
                    disabled={composerWorking}
                    onChange={(affectedDays) => setForm((current) => ({
                      ...current,
                      affectedDays,
                    }))}
                  />

                  {(form.category === 'equipment_access'
                    || form.category === 'travel') && (
                    <ChoiceChips
                      label={<Trans>Equipment still available (optional)</Trans>}
                      choices={equipment}
                      selected={form.availableEquipment}
                      disabled={composerWorking}
                      onChange={(availableEquipment) => setForm((current) => ({
                        ...current,
                        availableEquipment,
                      }))}
                    />
                  )}

                  {(form.category === 'weather'
                    || form.category === 'travel') && (
                    <ChoiceChips
                      label={<Trans>Terrain still available (optional)</Trans>}
                      choices={terrain}
                      selected={form.availableTerrain}
                      disabled={composerWorking}
                      onChange={(availableTerrain) => setForm((current) => ({
                        ...current,
                        availableTerrain,
                      }))}
                    />
                  )}
                </>
              )}

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="context-note"><Trans>Private note (optional)</Trans></Label>
                  <span className="font-data text-[11px] text-muted-foreground">
                    {form.narrative.length}/280
                  </span>
                </div>
                <textarea
                  id="context-note"
                  value={form.narrative}
                  maxLength={280}
                  rows={4}
                  disabled={composerWorking}
                  placeholder={t`Share only what changes your plan.`}
                  onChange={(event) => setForm((current) => ({
                    ...current,
                    narrative: event.target.value,
                  }))}
                  className="w-full resize-y rounded-lg border border-input bg-background px-3 py-2 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <p className="text-xs leading-relaxed text-muted-foreground">
                  <Trans>
                    Avoid names, diagnoses, precise locations, and other private
                    details. Notes are deleted after 30 days even when the
                    structured context remains.
                  </Trans>
                </p>
              </div>
            </div>
          )}

          {preview && (
            <div className="space-y-5">
              <div className="divide-y divide-border border-y border-border text-sm">
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Purpose</Trans></span>
                  <span className="font-medium text-foreground">
                    {preview.purpose === 'plan_adjustment'
                      ? <Trans>Suggest adjustments to the current plan</Trans>
                      : <Trans>Interpret this workout without guessing a cause</Trans>}
                  </span>
                </div>
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Category</Trans></span>
                  <span className="font-medium text-foreground">
                    {categoryLabel(preview.payload.category)}
                  </span>
                </div>
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Active until</Trans></span>
                  <span className="font-data text-foreground">
                    {formatDate(preview.expires_at)}
                  </span>
                </div>
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Stored until</Trans></span>
                  <span className="font-data text-foreground">
                    {formatDate(preview.purge_after)}
                  </span>
                </div>
                {preview.narrative_purge_at && (
                  <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 py-3">
                    <span className="text-muted-foreground"><Trans>Note deleted</Trans></span>
                    <span className="font-data text-foreground">
                      {formatDate(preview.narrative_purge_at)}
                    </span>
                  </div>
                )}
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Processing</Trans></span>
                  <span className="font-medium text-foreground">
                    <Trans>Rules only · nothing sent to AI</Trans>
                  </span>
                </div>
              </div>
              {Object.keys(preview.payload.fields).length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-foreground">
                    <Trans>Structured details</Trans>
                  </h3>
                  <dl className="mt-2 space-y-2 text-xs">
                    {Object.entries(preview.payload.fields).map(([key, value]) => (
                      <div key={key} className="flex items-start justify-between gap-4">
                        <dt className="text-muted-foreground">
                          {key.replaceAll('_', ' ')}
                        </dt>
                        <dd className="max-w-[60%] text-right font-data text-foreground">
                          {Array.isArray(value) ? value.join(', ') : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
              {preview.payload.narrative && (
                <div>
                  <h3 className="text-xs font-semibold text-foreground">
                    <Trans>Private note</Trans>
                  </h3>
                  <p className="mt-2 whitespace-pre-wrap rounded-lg bg-muted/40 px-3 py-2 text-sm leading-relaxed text-foreground">
                    {preview.payload.narrative}
                  </p>
                </div>
              )}
              {SAFETY_CONTEXT_CATEGORIES.has(preview.payload.category) && (
                <Alert className="border-accent-amber/30 bg-accent-amber/8">
                  <ShieldAlert className="text-accent-amber" aria-hidden="true" />
                  <AlertDescription className="text-xs leading-relaxed text-foreground">
                    <Trans>
                      This enters the safety path and stops ordinary performance
                      optimization. Praxys cannot diagnose, clear you to train,
                      or set a return-to-sport timeline.
                    </Trans>
                  </AlertDescription>
                </Alert>
              )}
              <div className="flex items-start gap-3 rounded-lg bg-accent-cobalt/6 px-3 py-3 text-xs leading-relaxed text-foreground">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-accent-cobalt" aria-hidden="true" />
                <p>
                  <Trans>
                    Saving confirms this one purpose. It does not authorize a
                    new purpose, AI processing, analytics, or model training.
                  </Trans>
                </p>
              </div>
            </div>
          )}

          {composerError && (
            <Alert variant="destructive">
              <AlertDescription>{composerError}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            {preview ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  disabled={composerWorking}
                  onClick={() => {
                    setPreview(null);
                    setPreviewRequest(null);
                    setComposerError('');
                  }}
                >
                  <Trans>Back</Trans>
                </Button>
                <Button
                  type="button"
                  disabled={composerWorking}
                  onClick={() => void saveDraft()}
                >
                  {composerWorking && (
                    <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                  )}
                  {editingItem
                    ? <Trans>Save correction</Trans>
                    : <Trans>Save private context</Trans>}
                </Button>
              </>
            ) : (
              <Button
                type="button"
                disabled={composerWorking}
                onClick={() => void reviewDraft()}
              >
                {composerWorking && (
                  <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                )}
                <Trans>Review purpose and expiry</Trans>
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={selectedItem != null}
        onOpenChange={(open) => {
          if (!open && !actionWorking) {
            detailRequestRef.current += 1;
            setSelectedItem(null);
            setDetail(null);
            setDetailError('');
            setActionConfirm('');
          }
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {currentDetailItem
                ? categoryLabel(currentDetailItem.payload.category)
                : <Trans>Private context</Trans>}
            </DialogTitle>
            <DialogDescription>
              <Trans>Inspect what is stored, where it was used, and who may process it.</Trans>
            </DialogDescription>
          </DialogHeader>

          {detailLoading && (
            <div className="space-y-2">
              <Skeleton className="h-12 rounded-lg" />
              <Skeleton className="h-24 rounded-lg" />
            </div>
          )}

          {currentDetailItem && !detailLoading && (
            <div className="space-y-5">
              <div className="divide-y divide-border border-y border-border text-sm">
                <div className="flex items-center justify-between gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Status</Trans></span>
                  <span className="font-medium text-foreground">
                    {currentDetailItem.state === 'active' && <Trans>Active</Trans>}
                    {currentDetailItem.state === 'expired' && <Trans>Expired</Trans>}
                    {currentDetailItem.state === 'withdrawn' && <Trans>Withdrawn</Trans>}
                    {currentDetailItem.state === 'deleting' && <Trans>Deleting</Trans>}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Purpose</Trans></span>
                  <span className="text-right font-medium text-foreground">
                    {currentDetailItem.purpose === 'plan_adjustment'
                      ? <Trans>Plan adjustment</Trans>
                      : <Trans>Workout interpretation</Trans>}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>Active until</Trans></span>
                  <span className="font-data text-foreground">
                    {formatDate(currentDetailItem.expires_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4 py-3">
                  <span className="text-muted-foreground"><Trans>AI processing</Trans></span>
                  <span className="font-medium text-foreground">
                    {currentDetailIsSafety
                      && currentDetailItem.processing_mode !== 'ai_allowed'
                      ? <Trans>Unavailable for safety context</Trans>
                      : currentDetailItem.processing_mode === 'ai_allowed'
                      ? <Trans>Allowed for this item</Trans>
                      : <Trans>Off</Trans>}
                  </span>
                </div>
              </div>

              {Object.keys(currentDetailItem.payload.fields).length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-foreground">
                    <Trans>Structured details</Trans>
                  </h3>
                  <dl className="mt-2 space-y-2 text-xs">
                    {Object.entries(currentDetailItem.payload.fields).map(
                      ([key, value]) => (
                        <div key={key} className="flex items-start justify-between gap-4">
                          <dt className="text-muted-foreground">
                            {key.replaceAll('_', ' ')}
                          </dt>
                          <dd className="max-w-[60%] text-right font-data text-foreground">
                            {Array.isArray(value)
                              ? value.join(', ')
                              : String(value)}
                          </dd>
                        </div>
                      ),
                    )}
                  </dl>
                </div>
              )}

              {currentDetailItem.payload.narrative && (
                <div>
                  <h3 className="text-xs font-semibold text-foreground">
                    <Trans>Private note</Trans>
                  </h3>
                  <p className="mt-2 whitespace-pre-wrap rounded-lg bg-muted/40 px-3 py-2 text-sm leading-relaxed text-foreground">
                    {currentDetailItem.payload.narrative}
                  </p>
                  <p className="mt-1 font-data text-[11px] text-muted-foreground">
                    <Trans>
                      Deletes {formatDate(currentDetailItem.narrative_purge_at)}
                    </Trans>
                  </p>
                </div>
              )}

              <div>
                <div className="flex items-center gap-2">
                  <History className="size-3.5 text-accent-cobalt" aria-hidden="true" />
                  <h3 className="text-xs font-semibold text-foreground">
                    <Trans>Context use</Trans>
                  </h3>
                </div>
                {detail && (
                  detail.use_receipts.length > 0
                  || detail.linked_revision_ids.length > 0
                  ? (
                    <div className="mt-2 space-y-2 text-xs leading-relaxed text-muted-foreground">
                      {detail.use_receipts.map((receipt) => (
                        <p key={receipt.id}>
                          <span className="font-medium text-foreground">
                            {receipt.consumer_type === 'deterministic_policy'
                              ? <Trans>Rules</Trans>
                              : <Trans>Microsoft Azure AI</Trans>}
                          </span>
                          {' · '}
                          <span className="font-data">{formatDate(receipt.used_at)}</span>
                          {' · '}
                          {receipt.disclosed_fields.join(', ')}
                        </p>
                      ))}
                      {detail.linked_revision_ids.length > 0 && (
                        <p>
                          <Trans>
                            Referenced by {detail.linked_revision_ids.length} plan
                            change record(s).
                          </Trans>
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                      <Trans>No assessment or plan change has used this context yet.</Trans>
                    </p>
                  )
                )}
              </div>

              {detailError && (
                <Alert variant="destructive">
                  <AlertDescription>{detailError}</AlertDescription>
                </Alert>
              )}

              {actionConfirm && (
                <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-3">
                  <p className="text-sm font-medium text-foreground">
                    {actionConfirm === 'expire'
                      ? <Trans>Stop using this context?</Trans>
                      : <Trans>Delete this context permanently?</Trans>}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {actionConfirm === 'expire'
                      ? <Trans>
                        It stays in your private history until its purge date,
                        but cannot influence a new assessment.
                      </Trans>
                      : <Trans>
                        Praxys also removes dependent private reasoning and use
                        receipts. Accepted workout changes remain without the
                        private reason.
                      </Trans>}
                  </p>
                  <div className="mt-3 flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={Boolean(actionWorking)}
                      onClick={() => setActionConfirm('')}
                    >
                      <Trans>Cancel</Trans>
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={Boolean(actionWorking)}
                      onClick={() => (
                        actionConfirm === 'expire'
                          ? void expireItem(currentDetailItem)
                          : void deleteItem(currentDetailItem)
                      )}
                    >
                      {actionWorking && (
                        <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                      )}
                      {actionConfirm === 'expire'
                        ? <Trans>Stop using</Trans>
                        : <Trans>Delete permanently</Trans>}
                    </Button>
                  </div>
                </div>
              )}

              {!actionConfirm && currentDetailItem.state === 'active' && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={detail == null}
                    onClick={() => openCorrection(currentDetailItem)}
                  >
                    <FilePenLine aria-hidden="true" />
                    <Trans>Correct</Trans>
                  </Button>
                  {(!currentDetailIsSafety
                    || currentDetailItem.processing_mode === 'ai_allowed') && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={detail == null}
                      onClick={() => openAi(currentDetailItem)}
                    >
                      <Brain aria-hidden="true" />
                      {currentDetailItem.processing_mode === 'ai_allowed'
                        ? <Trans>Review AI access</Trans>
                        : <Trans>AI option</Trans>}
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setActionConfirm('expire')}
                  >
                    <ShieldCheck aria-hidden="true" />
                    <Trans>Stop using</Trans>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setActionConfirm('delete')}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 aria-hidden="true" />
                    <Trans>Delete</Trans>
                  </Button>
                </div>
              )}

              {!actionConfirm
                && currentDetailItem.state !== 'active'
                && currentDetailItem.state !== 'deleting' && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActionConfirm('delete')}
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2 aria-hidden="true" />
                  <Trans>Delete retained history</Trans>
                </Button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={aiItem != null}
        onOpenChange={(open) => {
          if (!open && !aiWorking) {
            setAiItem(null);
            setAiError('');
            setAiNarrative(false);
          }
        }}
      >
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle><Trans>AI processing for one item</Trans></DialogTitle>
            <DialogDescription>
              <Trans>This decision is separate from saving context and applies only to this exact version.</Trans>
            </DialogDescription>
          </DialogHeader>

          {aiItem && (
            <div className="space-y-4">
              <div className="rounded-lg bg-accent-cobalt/6 p-3 text-xs leading-relaxed text-foreground">
                <p className="font-semibold"><Trans>AI service: Microsoft Azure</Trans></p>
                <p className="mt-1">
                  <Trans>
                    Only the fields below are sent to Microsoft Azure AI.
                    Microsoft states that inputs and outputs are not available
                    to OpenAI or used to train foundation models without
                    permission; Praxys does not grant that permission. Flagged
                    content may be reviewed for abuse monitoring under Azure
                    terms. Praxys does not log raw requests or responses.
                  </Trans>
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold text-foreground">
                  <Trans>Purpose</Trans>
                </p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {aiItem.purpose === 'plan_adjustment'
                    ? <Trans>Suggest a bounded adjustment to the current plan.</Trans>
                    : <Trans>Interpret one missed or modified workout without diagnosing a cause.</Trans>}
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold text-foreground">
                  <Trans>Structured fields sent</Trans>
                </p>
                <p className="mt-1 font-data text-xs leading-relaxed text-muted-foreground">
                  {personalContextDisclosedFields(aiItem).join(', ')}
                </p>
              </div>

              {personalContextNarrativeAvailable(aiItem) && (
                <label className="flex items-start gap-3 rounded-lg border border-border p-3 text-sm">
                  <input
                    type="checkbox"
                    checked={aiNarrative}
                    disabled={aiWorking || aiItem.processing_mode === 'ai_allowed'}
                    onChange={(event) => setAiNarrative(event.target.checked)}
                    className="mt-0.5 size-4 accent-primary"
                  />
                  <span>
                    <span className="block font-medium text-foreground">
                      <Trans>Also send my optional note</Trans>
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                      <Trans>Off by default. The note may contain more private detail than the structured fields.</Trans>
                    </span>
                  </span>
                </label>
              )}

              <Alert className="border-accent-amber/30 bg-accent-amber/8">
                <ShieldAlert className="text-accent-amber" aria-hidden="true" />
                <AlertDescription className="text-xs leading-relaxed text-foreground">
                  <Trans>
                    AI output can be wrong. It cannot diagnose, provide
                    treatment, clear you to train, or override Praxys safety,
                    science, and approval boundaries.
                  </Trans>
                </AlertDescription>
              </Alert>

              <p className="text-xs leading-relaxed text-muted-foreground">
                <Trans>
                  You can withdraw before any later request. Withdrawal cannot
                  recall a request the provider already processed. Deleting the
                  item removes local provider-use receipts and dependent private
                  explanations.
                </Trans>{' '}
                <Link
                  to="/privacy"
                  target="_blank"
                  className="font-medium text-accent-cobalt underline-offset-4 hover:underline"
                >
                  <Trans>Privacy Policy</Trans>
                </Link>
              </p>

              {aiError && (
                <Alert variant="destructive">
                  <AlertDescription>{aiError}</AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {aiItem && (
            <DialogFooter>
              {aiItem.processing_mode === 'ai_allowed' ? (
                <Button
                  type="button"
                  variant="destructive"
                  disabled={aiWorking}
                  onClick={() => void decideAi(aiItem, 'withdrawn')}
                >
                  {aiWorking && (
                    <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                  )}
                  <Trans>Withdraw AI permission</Trans>
                </Button>
              ) : (
                <Button
                  type="button"
                  disabled={aiWorking}
                  onClick={() => void decideAi(aiItem, 'granted')}
                >
                  {aiWorking && (
                    <LoaderCircle className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
                  )}
                  <Trans>Allow for this item</Trans>
                </Button>
              )}
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
