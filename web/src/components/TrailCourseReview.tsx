import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useLingui } from '@lingui/react/macro';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  apiFetch,
  extractErrorMessage,
  getAuthCacheScope,
  getAuthHeaders,
} from '@/hooks/useApi';
import {
  TRAIL_API_ENDPOINTS,
  TRAIL_EDITABLE_SECTION_KEYS,
  TRAIL_MODULE_KEYS,
  type TrailClientEnvelope,
  type TrailCurrentDraft,
  type TrailDraftResponse,
  type TrailEditableSectionKey,
  type TrailFixedFieldTarget,
  type TrailFocusTarget,
  type TrailModuleAvailability,
  type TrailModuleKey,
  type TrailReadinessReceipt,
  type TrailSectionKey,
  type TrailServerEnvelope,
} from '@/types/trail-plan';
import {
  ConfirmBar,
  DurationEditor,
  EnumEditor,
  FieldShell,
  MultiSelectEditor,
  NumberEditor,
  SectionShell,
  TriStateEditor,
  UnknownButton,
} from './trail-course-review/controls';
import { useTrailCourseReviewCopy } from './trail-course-review/copy';
import { TrailPendingComparison } from './trail-course-review/comparison';
import {
  FIELD_ELEMENT_IDS,
  FIELD_TARGET_SECTIONS,
  GRADE_KEYS,
  MODULE_LIMIT_TARGETS,
  EMPTY_NUMERIC_INPUTS,
  REVISION_PATTERN,
  SECTION_ELEMENT_IDS,
  buildValidatedRequest,
  clearOptionalGroupNumericInputs,
  clearPlanningDurationNumericInputs,
  currentDraftFromResponse,
  emptyDraftRequest,
  formatIsoDate,
  known,
  localIsoDate,
  numericInputsFromDraft,
  parseGradeBasisPoints,
  provenanceMeta,
  reasonCodeOf,
  reapplyPendingTrailEdits,
  replaceConstraintField,
  replaceCourseField,
  replaceOptionalField,
  requestFromDraft,
  sectionConfirmation,
  setOptionalGroupUnknown,
  unknown,
  type ConstraintEnvelopeKey,
  type ConstraintFields,
  type CourseEnvelopeKey,
  type CourseFields,
  type NumericInputKey,
  type OpenSections,
  type OptionalGroup,
  type ValidationIssue,
} from './trail-course-review/model';
import {
  TrailCourseReviewLoadError,
  TrailCourseReviewSkeleton,
  TrailUnknownVersion,
} from './trail-course-review/states';
import {
  TrailOperationCancelledError,
  TrailMutationResponseError,
  TrailTransportError,
  classifyTrailMutationFailure,
  requestTrailMutation,
} from './trail-course-review/mutation-error';
import {
  bindTrailOwnerScopeInvalidation,
  isCurrentTrailOperation,
  runTrailConfirmationCallback,
  type TrailOperationStamp,
} from './trail-course-review/operation-fence';
import { usePrivateTrailDraft } from './trail-course-review/use-private-draft';
import {
  createTrailOwnerExportAction,
  type TrailOwnerExportStatus,
} from './trail-course-review/owner-export';
import {
  parseTrailDeleteResponse,
  parseTrailReadinessResponse,
} from './trail-course-review/validation';

interface ActiveTrailOperation extends TrailOperationStamp {
  action: string;
  controller: AbortController;
  slowTimer: number;
}

export default function TrailCourseReview() {
  const {
    data,
    loading,
    error,
    errorStatus,
    refetch,
    fetchLatest,
    replaceData,
    clearData,
    rejectData,
  } = usePrivateTrailDraft();

  if (loading || (!data && !error)) return <TrailCourseReviewSkeleton />;
  if (!data) {
    return <TrailCourseReviewLoadError status={errorStatus} onRetry={refetch} />;
  }
  if (data.state === 'unknown_schema') {
    return (
      <TrailUnknownVersion
        draft={data}
        onReload={refetch}
        onClearData={clearData}
        onRejectData={rejectData}
      />
    );
  }
  return (
    <TrailCourseReviewWorkbench
      remoteDraft={data}
      onRefetch={refetch}
      onFetchLatest={fetchLatest}
      onReplaceRemote={replaceData}
      onClearRemote={clearData}
      onRejectRemote={rejectData}
    />
  );
}

function TrailCourseReviewWorkbench({
  remoteDraft,
  onRefetch,
  onFetchLatest,
  onReplaceRemote,
  onClearRemote,
  onRejectRemote,
}: {
  remoteDraft: TrailCurrentDraft | Extract<TrailDraftResponse, { state: 'absent' }>;
  onRefetch: () => Promise<void>;
  onFetchLatest: () => Promise<TrailDraftResponse>;
  onReplaceRemote: (value: TrailDraftResponse) => void;
  onClearRemote: () => void;
  onRejectRemote: (message: string) => void;
}) {
  const { i18n, t } = useLingui();
  const isZh = i18n.locale.toLowerCase().startsWith('zh');
  const l = useCallback(
    (english: string, chinese: string) => isZh ? chinese : english,
    [isZh],
  );
  const errorSummaryRef = useRef<HTMLHeadingElement>(null);
  const receiptErrorRef = useRef<HTMLDivElement>(null);
  const remoteRevisionRef = useRef(remoteDraft.composite_revision);
  const ownerScopeRef = useRef(getAuthCacheScope());
  const pendingRef = useRef(false);
  const lifetimeRef = useRef(1);
  const operationSequenceRef = useRef(0);
  const editGenerationRef = useRef(0);
  const activeOperationRef = useRef<ActiveTrailOperation | null>(null);
  const [serverDraft, setServerDraft] = useState(remoteDraft);
  const [request, setRequest] = useState(() => requestFromDraft(remoteDraft));
  const [numericInputs, setNumericInputs] = useState(() => numericInputsFromDraft(remoteDraft));
  const [dirtySections, setDirtySections] = useState<Set<TrailEditableSectionKey>>(
    () => new Set(),
  );
  const [openSections, setOpenSections] = useState<OpenSections>({
    'section.event-duration': true,
    'section.grade-footing': true,
    'section.training-access': true,
    'section.recent-experience': true,
    'section.optional-context': false,
    'section.policy-receipt': true,
  });
  const [optionalOpened, setOptionalOpened] = useState(false);
  const [readiness, setReadiness] = useState<TrailReadinessReceipt | null>(null);
  const [historyComparisonVisible, setHistoryComparisonVisible] = useState(false);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [receiptTargetError, setReceiptTargetError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [slowAction, setSlowAction] = useState(false);
  const [dialogAction, setDialogAction] = useState<'reset' | 'delete' | null>(null);
  const [latestDraft, setLatestDraft] = useState<TrailDraftResponse | null>(null);
  const [staleConflict, setStaleConflict] = useState(false);
  const [online, setOnline] = useState(
    () => typeof navigator === 'undefined' || navigator.onLine,
  );
  const [unavailableDateInput, setUnavailableDateInput] = useState('');
  const moreActionsRef = useRef<HTMLButtonElement>(null);
  const [moreActionsOpen, setMoreActionsOpen] = useState(false);
  const [exportMenuClosing, setExportMenuClosing] = useState(false);
  const [exportStatus, setExportStatus] = useState<TrailOwnerExportStatus>('idle');
  const [ownerExport] = useState(() => createTrailOwnerExportAction({
    getAuthHeaders,
    onStatusChange: setExportStatus,
    closeMenuAndFocus: () => {
      // Keep the popup mounted for Base UI's close lifecycle so its focus
      // manager can restore the trigger after removing the menu item.
      setExportMenuClosing(true);
      setMoreActionsOpen(false);
    },
  }));
  useEffect(() => () => ownerExport.cancel(), [ownerExport]);
  const handleMoreActionsOpenChange = useCallback((open: boolean) => {
    if (open) setExportMenuClosing(false);
    setMoreActionsOpen(open);
  }, []);

  const pending = dirtySections.size > 0;

  const invalidatePrivateLifetime = useCallback(() => {
    lifetimeRef.current += 1;
    operationSequenceRef.current += 1;
    editGenerationRef.current += 1;
    remoteRevisionRef.current = '';
    const active = activeOperationRef.current;
    if (active) {
      window.clearTimeout(active.slowTimer);
      active.controller.abort();
    }
    activeOperationRef.current = null;
    ownerExport.cancel();
    pendingRef.current = false;
    setRequest(emptyDraftRequest());
    setNumericInputs({ ...EMPTY_NUMERIC_INPUTS });
    setDirtySections(new Set());
    setReadiness(null);
    setHistoryComparisonVisible(false);
    setValidationIssues([]);
    setOperationError(null);
    setReceiptTargetError(null);
    setNotice(null);
    setBusyAction(null);
    setSlowAction(false);
    setDialogAction(null);
    setLatestDraft(null);
    setStaleConflict(false);
    setUnavailableDateInput('');
    setMoreActionsOpen(false);
    setExportMenuClosing(false);
    setExportStatus('idle');
    onClearRemote();
  }, [onClearRemote, ownerExport]);

  useEffect(() => bindTrailOwnerScopeInvalidation(
    window,
    ownerScopeRef.current,
    getAuthCacheScope,
    invalidatePrivateLifetime,
  ), [invalidatePrivateLifetime]);

  useEffect(() => () => {
    lifetimeRef.current += 1;
    const active = activeOperationRef.current;
    if (active) {
      window.clearTimeout(active.slowTimer);
      active.controller.abort();
    }
    activeOperationRef.current = null;
  }, []);

  useEffect(() => {
    pendingRef.current = pending;
  }, [pending]);

  const replaceWithServer = useCallback((draft: TrailDraftResponse) => {
    if (draft.state === 'unknown_schema') return;
    setServerDraft(draft);
    setRequest(requestFromDraft(draft));
    setNumericInputs(numericInputsFromDraft(draft));
    setDirtySections(new Set());
    setValidationIssues([]);
    setReadiness(null);
    setLatestDraft(null);
    setStaleConflict(false);
    setUnavailableDateInput('');
    pendingRef.current = false;
    editGenerationRef.current += 1;
    remoteRevisionRef.current = draft.composite_revision;
  }, []);

  useEffect(() => {
    if (remoteDraft.composite_revision === remoteRevisionRef.current) return;
    activeOperationRef.current?.controller.abort();
    if (pendingRef.current) {
      setLatestDraft(remoteDraft);
      setStaleConflict(true);
      return;
    }
    replaceWithServer(remoteDraft);
  }, [remoteDraft, replaceWithServer]);

  useEffect(() => {
    if (!pending) return undefined;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!pendingRef.current) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [pending]);

  useEffect(() => {
    const handleOnline = () => {
      setOnline(true);
      if (pendingRef.current) {
        setNotice(l(
          t`Connection restored. Review the current server version before restoring pending changes.`,
          t`连接已恢复。请先查看当前服务端版本，再恢复待保存更改。`,
        ));
      }
    };
    const handleOffline = () => setOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [l, t]);

  const beginBusy = useCallback((
    action: string,
    revision: string,
  ): ActiveTrailOperation | null => {
    if (activeOperationRef.current) return null;
    const operation: ActiveTrailOperation = {
      action,
      controller: new AbortController(),
      lifetime: lifetimeRef.current,
      ownerScope: getAuthCacheScope(),
      requestId: operationSequenceRef.current + 1,
      revision,
      editGeneration: editGenerationRef.current,
      slowTimer: 0,
    };
    operationSequenceRef.current = operation.requestId;
    activeOperationRef.current = operation;
    setBusyAction(action);
    setSlowAction(false);
    operation.slowTimer = window.setTimeout(() => {
      if (activeOperationRef.current?.requestId === operation.requestId) {
        setSlowAction(true);
      }
    }, 8_000);
    return operation;
  }, []);

  const operationIsCurrent = useCallback((operation: ActiveTrailOperation) => {
    const active = activeOperationRef.current;
    if (!active || active.requestId !== operation.requestId) return false;
    if (operation.lifetime !== lifetimeRef.current) return false;
    if (operation.ownerScope !== getAuthCacheScope()) {
      invalidatePrivateLifetime();
      return false;
    }
    return isCurrentTrailOperation(operation, {
      lifetime: lifetimeRef.current,
      ownerScope: getAuthCacheScope(),
      requestId: active.requestId,
      revision: remoteRevisionRef.current,
      editGeneration: editGenerationRef.current,
    });
  }, [invalidatePrivateLifetime]);

  const endBusy = useCallback((operation: ActiveTrailOperation) => {
    const active = activeOperationRef.current;
    if (!active || active.requestId !== operation.requestId) return;
    window.clearTimeout(active.slowTimer);
    activeOperationRef.current = null;
    setBusyAction(null);
    setSlowAction(false);
  }, []);

  const invalidateReadiness = useCallback((section: TrailEditableSectionKey) => {
    if (activeOperationRef.current) return;
    editGenerationRef.current += 1;
    pendingRef.current = true;
    setDirtySections((current) => {
      const next = new Set(current);
      next.add(section);
      return next;
    });
    setReadiness(null);
    setValidationIssues([]);
    setNotice(l(
      t`Changed—confirm this section again after saving.`,
      t`已更改，保存后请重新确认本节。`,
    ));
  }, [l, t]);

  const updateNumeric = useCallback((
    key: NumericInputKey,
    value: string,
    section: TrailEditableSectionKey,
  ) => {
    if (activeOperationRef.current) return;
    setNumericInputs((current) => ({ ...current, [key]: value }));
    invalidateReadiness(section);
  }, [invalidateReadiness]);

  const updateCourse = useCallback(<K extends CourseEnvelopeKey,>(
    key: K,
    value: CourseFields[K],
    section: TrailEditableSectionKey,
  ) => {
    if (activeOperationRef.current) return;
    setRequest((current) => replaceCourseField(current, key, value));
    invalidateReadiness(section);
  }, [invalidateReadiness]);

  const updateConstraint = useCallback(<K extends ConstraintEnvelopeKey,>(
    key: K,
    value: ConstraintFields[K],
  ) => {
    if (activeOperationRef.current) return;
    setRequest((current) => replaceConstraintField(current, key, value));
    invalidateReadiness('section.training-access');
  }, [invalidateReadiness]);

  const updateOptional = useCallback((
    group: OptionalGroup,
    key: string,
    value: TrailClientEnvelope<unknown>,
  ) => {
    if (activeOperationRef.current) return;
    setRequest((current) => replaceOptionalField(current, group, key, value));
    invalidateReadiness('section.optional-context');
  }, [invalidateReadiness]);

  const openSection = useCallback((sectionKey: TrailSectionKey) => {
    setOpenSections((current) => ({ ...current, [sectionKey]: true }));
  }, []);

  const focusClosedTarget = useCallback((target: TrailFocusTarget) => {
    setReceiptTargetError(null);
    const failClosed = () => {
      setReceiptTargetError(l(
        t`Praxys did not provide a safe destination for this action. Review the receipt and retry after reloading.`,
        t`Praxys 未提供可安全跳转的目标。请查看回执并重新加载后重试。`,
      ));
      requestAnimationFrame(() => receiptErrorRef.current?.focus());
    };

    if (target.startsWith('section.')) {
      if (!(target in SECTION_ELEMENT_IDS)) {
        failClosed();
        return;
      }
      const section = target as TrailSectionKey;
      openSection(section);
      requestAnimationFrame(() => {
        document.getElementById(SECTION_ELEMENT_IDS[section])?.focus();
      });
      return;
    }
    if (target.startsWith('field.')) {
      if (!(target in FIELD_ELEMENT_IDS)) {
        failClosed();
        return;
      }
      const field = target as TrailFixedFieldTarget;
      openSection(FIELD_TARGET_SECTIONS[field]);
      requestAnimationFrame(() => {
        document.getElementById(FIELD_ELEMENT_IDS[field])?.focus();
      });
      return;
    }
    failClosed();
  }, [l, openSection, t]);

  const reviewLatest = useCallback(async () => {
    const operation = beginBusy('reload', serverDraft.composite_revision);
    if (!operation) return;
    setOperationError(null);
    try {
      const latest = await onFetchLatest();
      if (!operationIsCurrent(operation)) return;
      if (latest.state === 'unknown_schema') {
        onReplaceRemote(latest);
        return;
      }
      setLatestDraft(latest);
      setStaleConflict(true);
      setNotice(l(
        t`The latest server version is ready to compare. Pending changes were not overwritten.`,
        t`最新服务端版本已可对照。待保存更改未被覆盖。`,
      ));
    } catch (error) {
      if (!operationIsCurrent(operation)) return;
      const disposition = classifyTrailMutationFailure(error);
      if (disposition === 'cancelled') return;
      const failure = error instanceof TrailTransportError
        ? l(
          t`The server could not be reached. Your pending changes remain only on this page.`,
          t`无法连接服务器。待保存更改仍仅保留在本页面。`,
        )
        : error instanceof Error ? error.message : l(
          t`The latest version could not be loaded.`,
          t`无法加载最新版本。`,
        );
      if (disposition === 'retryable' || disposition === 'stale') {
        setOperationError(failure);
      } else {
        pendingRef.current = false;
        onRejectRemote(failure);
      }
    } finally {
      endBusy(operation);
    }
  }, [
    beginBusy,
    endBusy,
    l,
    onFetchLatest,
    onRejectRemote,
    onReplaceRemote,
    operationIsCurrent,
    serverDraft.composite_revision,
    t,
  ]);

  const handleSpecialTarget = useCallback(async (target: TrailFocusTarget) => {
    if (target === 'action.reload-supported-version') {
      await reviewLatest();
      openSection('section.policy-receipt');
      requestAnimationFrame(() => {
        document.getElementById(SECTION_ELEMENT_IDS['section.policy-receipt'])?.focus();
      });
      return;
    }
    if (target === 'action.retry-readiness') {
      if (pendingRef.current) {
        setReceiptTargetError(l(
          t`Save and confirm the current revision before retrying readiness.`,
          t`请先保存并确认当前版本，再重新检查准备情况。`,
        ));
        requestAnimationFrame(() => receiptErrorRef.current?.focus());
        return;
      }
      const readinessAction = document.getElementById(
        window.matchMedia('(min-width: 1024px)').matches
          ? 'trail-readiness-action-desktop'
          : 'trail-readiness-action-mobile',
      );
      readinessAction?.focus();
      readinessAction?.click();
      return;
    }
    if (target === 'action.review-history-envelope') {
      setHistoryComparisonVisible(true);
      focusClosedTarget('section.recent-experience');
      return;
    }
    focusClosedTarget(target);
  }, [focusClosedTarget, l, openSection, reviewLatest, t]);

  const handleResponseError = useCallback(async (
    response: Response,
    fallback: string,
    operation: ActiveTrailOperation,
  ) => {
    const status = response.status;
    const message = await extractErrorMessage(response, fallback);
    if (!operationIsCurrent(operation)) {
      throw new TrailOperationCancelledError();
    }
    if (status === 412) {
      setStaleConflict(true);
      setNotice(l(
        t`The server revision changed. Review the latest version before choosing whether to reapply pending changes.`,
        t`服务端版本已更改。请查看最新版本，再决定是否重新应用待保存更改。`,
      ));
    }
    throw new TrailMutationResponseError(message, status);
  }, [l, operationIsCurrent, t]);

  const saveDraft = useCallback(async (leaveAfterSave = false) => {
    if (activeOperationRef.current) return;
    if (!online) {
      setOperationError(l(
        t`Offline. Changes are kept only on this page and have not been saved.`,
        t`当前离线。更改仅保留在此页面，尚未保存。`,
      ));
      return;
    }
    const validated = buildValidatedRequest(request, numericInputs);
    setValidationIssues(validated.issues);
    if (validated.issues.length > 0) {
      setOperationError(l(
        t`Review the linked fields before saving.`,
        t`保存前请检查已链接的字段。`,
      ));
      requestAnimationFrame(() => errorSummaryRef.current?.focus());
      return;
    }
    const operation = beginBusy('save', serverDraft.composite_revision);
    if (!operation) return;
    setOperationError(null);
    try {
      const response = await requestTrailMutation(apiFetch, TRAIL_API_ENDPOINTS.draft, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': serverDraft.composite_revision,
        },
        body: JSON.stringify(validated.request),
      }, operation.controller.signal);
      if (!operationIsCurrent(operation)) return;
      if (!response.ok) {
        await handleResponseError(response, l(
          t`The Trail course review could not be saved.`,
          t`无法保存越野赛道核对。`,
        ), operation);
      }
      const payload = await response.json() as unknown;
      if (!operationIsCurrent(operation)) return;
      const next = currentDraftFromResponse(payload);
      if (!next) throw new Error(l(
        t`The server returned an unsupported Trail draft.`,
        t`服务端返回了不受支持的越野草稿。`,
      ));
      if (!operationIsCurrent(operation)) return;
      onReplaceRemote(next);
      replaceWithServer(next);
      setNotice(l(
        t`Course review saved. Confirm each reviewed section at this revision.`,
        t`赛道核对已保存。请按当前版本逐节确认。`,
      ));
      if (leaveAfterSave) window.location.assign('/training');
    } catch (error) {
      if (!operationIsCurrent(operation)) return;
      const failure = error instanceof TrailTransportError
        ? l(
          t`The server could not be reached. Your pending changes remain only on this page.`,
          t`无法连接服务器。待保存更改仍仅保留在本页面。`,
        )
        : error instanceof Error ? error.message : l(
          t`The Trail course review could not be saved.`,
          t`无法保存越野赛道核对。`,
        );
      const disposition = classifyTrailMutationFailure(error);
      if (disposition === 'cancelled') return;
      if (disposition === 'stale') {
        setOperationError(null);
      } else if (disposition === 'retryable') {
        setLatestDraft(null);
        setStaleConflict(true);
        setOperationError(failure);
        setNotice(l(
          t`The save result is uncertain. Review the latest server version before restoring pending changes.`,
          t`保存结果尚不确定。恢复待保存更改前，请先查看最新服务端版本。`,
        ));
      } else {
        pendingRef.current = false;
        setOperationError(failure);
        onRejectRemote(failure);
      }
    } finally {
      endBusy(operation);
    }
  }, [
    beginBusy,
    endBusy,
    handleResponseError,
    l,
    numericInputs,
    online,
    operationIsCurrent,
    onReplaceRemote,
    onRejectRemote,
    replaceWithServer,
    request,
    serverDraft.composite_revision,
    t,
  ]);

  const confirmSection = useCallback(async (sectionKey: TrailEditableSectionKey) => {
    if (activeOperationRef.current) return;
    if (
      serverDraft.state !== 'current'
      || pendingRef.current
      || dirtySections.size > 0
    ) return;
    const confirmation = sectionConfirmation(serverDraft, sectionKey);
    if (!confirmation || !REVISION_PATTERN.test(confirmation.current_revision)) {
      const failure = l(
        t`This section has no safe revision to confirm. Reload and review it again.`,
        t`本节没有可安全确认的版本。请重新加载并再次核对。`,
      );
      setOperationError(failure);
      onRejectRemote(failure);
      return;
    }
    const operation = beginBusy(
      `confirm:${sectionKey}`,
      serverDraft.composite_revision,
    );
    if (!operation) return;
    setOperationError(null);
    try {
      const response = await requestTrailMutation(apiFetch, TRAIL_API_ENDPOINTS.confirm, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': serverDraft.composite_revision,
        },
        body: JSON.stringify({
          section_key: sectionKey,
          section_revision: confirmation.current_revision,
        }),
      }, operation.controller.signal);
      if (!operationIsCurrent(operation)) return;
      if (!response.ok) {
        await handleResponseError(response, l(
          t`This section could not be confirmed.`,
          t`无法确认本节。`,
        ), operation);
      }
      const payload = await response.json() as unknown;
      if (!operationIsCurrent(operation)) return;
      const next = currentDraftFromResponse(payload);
      if (!next) throw new Error(l(
        t`The server returned an unsupported confirmation response.`,
        t`服务端返回了不受支持的确认响应。`,
      ));
      if (!operationIsCurrent(operation)) return;
      onReplaceRemote(next);
      replaceWithServer(next);
      setNotice(l(
        t`This exact section revision is confirmed. Confirmation does not attest safety or eligibility.`,
        t`已确认本节的确切版本。确认不代表安全或符合生成条件。`,
      ));
    } catch (error) {
      if (!operationIsCurrent(operation)) return;
      const failure = error instanceof TrailTransportError
        ? l(
          t`The server could not be reached. No confirmation was applied.`,
          t`无法连接服务器。未应用任何确认。`,
        )
        : error instanceof Error ? error.message : l(
          t`This section could not be confirmed.`,
          t`无法确认本节。`,
        );
      const disposition = classifyTrailMutationFailure(error);
      if (disposition === 'cancelled') return;
      if (disposition === 'stale') {
        setOperationError(null);
      } else if (disposition === 'retryable') {
        setLatestDraft(null);
        setStaleConflict(true);
        setOperationError(failure);
        setNotice(l(
          t`The confirmation result is uncertain. Review the latest server version before trying again.`,
          t`确认结果尚不确定。再次操作前，请先查看最新服务端版本。`,
        ));
      } else {
        pendingRef.current = false;
        setOperationError(failure);
        onRejectRemote(failure);
      }
    } finally {
      endBusy(operation);
    }
  }, [
    beginBusy,
    dirtySections,
    endBusy,
    handleResponseError,
    l,
    onReplaceRemote,
    onRejectRemote,
    replaceWithServer,
    serverDraft,
    operationIsCurrent,
    t,
  ]);

  const handleConfirmSection = useCallback((sectionKey: TrailEditableSectionKey) => {
    void runTrailConfirmationCallback(
      sectionKey,
      () => activeOperationRef.current !== null,
      () => pendingRef.current,
      confirmSection,
    );
  }, [confirmSection]);

  const allConfirmed = serverDraft.state === 'current'
    && TRAIL_EDITABLE_SECTION_KEYS.every((sectionKey) => {
      const item = sectionConfirmation(serverDraft, sectionKey);
      return item !== null
        && item.confirmed_revision === item.current_revision
        && !dirtySections.has(sectionKey);
    });

  const checkReadiness = useCallback(async () => {
    if (!allConfirmed || pending || busyAction || activeOperationRef.current) return;
    const operation = beginBusy('readiness', serverDraft.composite_revision);
    if (!operation) return;
    setOperationError(null);
    setReceiptTargetError(null);
    setReadiness(null);
    try {
      const response = await requestTrailMutation(apiFetch, TRAIL_API_ENDPOINTS.readiness, {
        method: 'POST',
      }, operation.controller.signal);
      if (!operationIsCurrent(operation)) return;
      if (!response.ok) {
        await handleResponseError(response, l(
          t`Readiness could not be checked.`,
          t`暂时无法检查准备情况。`,
        ), operation);
      }
      const raw = await response.json() as unknown;
      if (!operationIsCurrent(operation)) return;
      const payload = parseTrailReadinessResponse(
        raw,
        serverDraft.composite_revision,
      );
      if (!payload) {
        throw new Error(l(
          t`The readiness response did not match the accepted inactive Trail contract. No result was applied.`,
          t`准备情况响应与已接受的未启用越野合同不一致。未应用任何结果。`,
        ));
      }
      if (!operationIsCurrent(operation)) return;
      setReadiness(payload.readiness);
      setNotice(l(
        t`Readiness updated for the current confirmed revision.`,
        t`已按当前确认版本更新准备情况。`,
      ));
    } catch (error) {
      if (!operationIsCurrent(operation)) return;
      const failure = error instanceof TrailTransportError
        ? l(
          t`The server could not be reached. No readiness result was applied.`,
          t`无法连接服务器。未应用任何准备情况结果。`,
        )
        : error instanceof Error ? error.message : l(
          t`Readiness could not be checked.`,
          t`暂时无法检查准备情况。`,
        );
      const disposition = classifyTrailMutationFailure(error);
      if (disposition === 'cancelled') return;
      if (disposition === 'retryable' || disposition === 'stale') {
        setOperationError(failure);
      } else {
        pendingRef.current = false;
        onRejectRemote(failure);
      }
    } finally {
      endBusy(operation);
    }
  }, [
    allConfirmed,
    beginBusy,
    busyAction,
    endBusy,
    handleResponseError,
    l,
    pending,
    onRejectRemote,
    operationIsCurrent,
    serverDraft.composite_revision,
    t,
  ]);

  const resetOrDelete = useCallback(async (kind: 'reset' | 'delete') => {
    const operation = beginBusy(kind, serverDraft.composite_revision);
    if (!operation) return;
    setOperationError(null);
    try {
      const response = await requestTrailMutation(
        apiFetch,
        kind === 'reset' ? TRAIL_API_ENDPOINTS.reset : TRAIL_API_ENDPOINTS.draft,
        {
          method: kind === 'reset' ? 'POST' : 'DELETE',
          headers: { 'If-Match': serverDraft.composite_revision },
        },
        operation.controller.signal,
      );
      if (!operationIsCurrent(operation)) return;
      if (!response.ok) {
        await handleResponseError(response, l(
          t`The requested Trail data action did not complete.`,
          t`请求的越野数据操作未完成。`,
        ), operation);
      }
      const payload = await response.json() as unknown;
      if (!operationIsCurrent(operation)) return;
      if (kind === 'reset') {
        const next = currentDraftFromResponse(payload);
        if (!next || next.reset_is_erasure !== false) throw new Error(l(
          t`The reset response was not recognized.`,
          t`无法识别重置响应。`,
        ));
        if (!operationIsCurrent(operation)) return;
        onReplaceRemote(next);
        replaceWithServer(next);
        setNotice(l(
          t`The server reset editable answers to unknown and invalidated confirmations. Source activities and retained proposals were not erased.`,
          t`服务端已把可编辑回答重置为未知并使确认失效。来源活动和已保留提案未被删除。`,
        ));
      } else {
        const deletion = parseTrailDeleteResponse(payload);
        if (!deletion) {
          throw new Error(l(
            t`The deletion response was not recognized.`,
            t`无法识别删除响应。`,
          ));
        }
        if (!operationIsCurrent(operation)) return;
        setNotice(deletion.status === 'deleted'
          ? l(
            t`The inactive Trail API reported the Trail draft deleted. Your Praxys account was not deleted.`,
            t`未启用的越野 API 已报告删除越野草稿。你的 Praxys 账号未被删除。`,
          )
          : l(
            t`The inactive Trail API reported no Trail draft to delete. Your Praxys account was not deleted.`,
            t`未启用的越野 API 报告没有可删除的越野草稿。你的 Praxys 账号未被删除。`,
          ));
        pendingRef.current = false;
        setDirtySections(new Set());
        setReadiness(null);
        onClearRemote();
        await onRefetch();
      }
      setDialogAction(null);
    } catch (error) {
      if (!operationIsCurrent(operation)) return;
      const failure = error instanceof TrailTransportError
        ? l(
          t`The server could not be reached. No Trail data action was repeated.`,
          t`无法连接服务器。未重复执行越野数据操作。`,
        )
        : error instanceof Error ? error.message : l(
          t`The requested Trail data action did not complete.`,
          t`请求的越野数据操作未完成。`,
        );
      const disposition = classifyTrailMutationFailure(error);
      if (disposition === 'cancelled') return;
      if (disposition === 'stale') {
        setOperationError(null);
      } else if (disposition === 'retryable') {
        setLatestDraft(null);
        setStaleConflict(true);
        setOperationError(failure);
        setNotice(l(
          t`The data action result is uncertain. Review the latest server version before trying another action.`,
          t`数据操作结果尚不确定。再次操作前，请先查看最新服务端版本。`,
        ));
      } else {
        pendingRef.current = false;
        setOperationError(failure);
        onRejectRemote(failure);
      }
    } finally {
      endBusy(operation);
    }
  }, [
    beginBusy,
    endBusy,
    handleResponseError,
    l,
    onRefetch,
    onReplaceRemote,
    onClearRemote,
    onRejectRemote,
    operationIsCurrent,
    replaceWithServer,
    serverDraft.composite_revision,
    t,
  ]);

  const restoreAgainstLatest = useCallback(() => {
    if (
      activeOperationRef.current
      || !latestDraft
      || latestDraft.state === 'unknown_schema'
    ) return;
    const restored = reapplyPendingTrailEdits(
      serverDraft,
      request,
      numericInputs,
      latestDraft,
    );
    onReplaceRemote(latestDraft);
    setServerDraft(latestDraft);
    setRequest(restored.request);
    setNumericInputs(restored.numericInputs);
    setDirtySections(restored.dirtySections);
    setValidationIssues([]);
    remoteRevisionRef.current = latestDraft.composite_revision;
    editGenerationRef.current += 1;
    pendingRef.current = restored.dirtySections.size > 0;
    setLatestDraft(null);
    setStaleConflict(false);
    setReadiness(null);
    setNotice(l(
      t`Pending values were reapplied in memory to the latest revision. They have not been saved or confirmed.`,
      t`待保存值已在页面内存中重新应用到最新版本；尚未保存或确认。`,
    ));
  }, [
    l,
    latestDraft,
    numericInputs,
    onReplaceRemote,
    request,
    serverDraft,
    t,
  ]);

  const discardPending = useCallback(() => {
    if (
      activeOperationRef.current
      || !latestDraft
      || latestDraft.state === 'unknown_schema'
    ) return;
    onReplaceRemote(latestDraft);
    replaceWithServer(latestDraft);
    setNotice(l(
      t`Pending changes were discarded.`,
      t`已放弃待保存更改。`,
    ));
  }, [l, latestDraft, onReplaceRemote, replaceWithServer, t]);


  const {
    copy,
    provenanceLabels,
    eventFormatOptions,
    distanceFamilyOptions,
    planningIntentOptions,
    footingOptions,
    weekdayOptions,
    sunOptions,
    windOptions,
    conditionsOptions,
    supportOptions,
    availabilityOptions,
    gearOptions,
    intakeOptions,
    gutOptions,
    gradeLabels,
    reasonCatalog,
    moduleLabels,
  } = useTrailCourseReviewCopy();

  const readinessHeadline = readiness?.status === 'validation_failed'
    ? l(t`We couldn't check this information`, t`暂时无法检查这些信息`)
    : readiness?.status === 'policy_unavailable'
      ? l(t`Trail planning isn't available for this case`, t`此情况暂不支持越野计划`)
      : readiness?.status === 'readiness_blocked'
        ? l(
          t`Your symptoms, schedule, history, or terrain access blocks a proposal for now`,
          t`当前症状、时间安排、训练历史或场地条件暂时阻止生成计划`,
        )
        : readiness?.status === 'clarification_required'
          ? l(
            t`A few answers are needed before Praxys can check readiness`,
            t`还需补充少量信息，Praxys 才能检查准备情况`,
          )
          : readiness?.status === 'eligible_proposal'
            ? l(t`Ready to review a 14-day proposal`, t`可以查看 14 天计划提案`)
            : copy.noReceipt;
  const matchingReasons = readiness?.matching_reasons ?? [];
  const recognizedReasons = matchingReasons.flatMap((reason) => {
    const code = reasonCodeOf(reason.status, reason.detail_reason);
    return code ? [{ code, copy: reasonCatalog[code] }] : [];
  });
  const hasUnknownReason = Boolean(readiness)
    && recognizedReasons.length !== matchingReasons.length;
  const moduleByKey = new Map<TrailModuleKey, TrailModuleAvailability>(
    (readiness?.module_availability ?? []).flatMap((module) =>
      TRAIL_MODULE_KEYS.includes(module.module) ? [[module.module, module]] : []),
  );
  const currentFields = serverDraft.state === 'current'
    ? serverDraft.course_demand.fields
    : null;
  const currentConstraints = serverDraft.state === 'current'
    ? serverDraft.constraints
    : null;
  const history = readiness?.history_statistics ?? null;
  const historyRevision = readiness?.revision_bindings?.history_revision
    ?? (serverDraft.state === 'current'
      ? serverDraft.revision_bindings.history_revision
      : null);
  const gradeRawValues = [
    numericInputs.gradeBelowNeg10,
    numericInputs.gradeNeg10ToNeg3,
    numericInputs.gradeNearLevel,
    numericInputs.gradePos3ToPos10,
    numericInputs.gradePos10AndAbove,
  ].map(parseGradeBasisPoints);
  const gradeTotal = gradeRawValues.some((value) => value === null)
    ? null
    : gradeRawValues.reduce<number>((sum, value) => sum + (value ?? 0), 0) / 100;
  const gradeInputsAreBlank = [
    numericInputs.gradeBelowNeg10,
    numericInputs.gradeNeg10ToNeg3,
    numericInputs.gradeNearLevel,
    numericInputs.gradePos3ToPos10,
    numericInputs.gradePos10AndAbove,
  ].every((value) => value === '');
  const sectionTitle: Record<TrailEditableSectionKey, string> = {
    'section.event-duration': copy.eventSection,
    'section.grade-footing': copy.gradeSection,
    'section.training-access': copy.trainingSection,
    'section.optional-context': copy.optionalSection,
  };
  const validationLabel = (issue: ValidationIssue) => {
    const names: Record<string, string> = {
      'event-date': copy.eventDate,
      distance: copy.raceDistance,
      ascent: copy.totalAscent,
      descent: copy.totalDescent,
      'planning-duration': copy.planningMinimum,
      'grade-distribution': copy.gradeDistribution,
      'course-footing': copy.footing,
      'weekly-time': copy.weeklyTime,
      'session-time': copy.longestSession,
      'available-days': copy.availableDays,
      'accessible-footing': copy.trainingFooting,
      'preferred-day': copy.preferredDay,
      'maximum-altitude': copy.maximumAltitude,
      temperature_min_c: copy.temperatureRange,
      temperature_max_c: copy.temperatureRange,
      'temperature-range': copy.temperatureRange,
      humidity_min_pct: copy.humidityRange,
      humidity_max_pct: copy.humidityRange,
      'humidity-range': copy.humidityRange,
      'aid-count': copy.aidCount,
      'aid-gap': copy.aidGap,
      'fueling-duration': copy.fuelingDuration,
      'fueling-sessions': copy.fuelingSessions,
    };
    return names[issue.id] ?? sectionTitle[issue.section];
  };
  const validationMessageFor = (controlId: string) => (
    validationIssues.some((issue) => issue.controlId === controlId)
      ? copy.fieldError
      : undefined
  );
  const focusValidationIssue = (issue: ValidationIssue) => {
    openSection(issue.section);
    requestAnimationFrame(() => {
      document.getElementById(issue.controlId)?.focus();
    });
  };
  const confirmationProps = (sectionKey: TrailEditableSectionKey) => {
    const confirmation = sectionConfirmation(serverDraft, sectionKey);
    return {
      currentRevision: confirmation?.current_revision ?? null,
      confirmedRevision: confirmation?.confirmed_revision ?? null,
      dirty: dirtySections.has(sectionKey),
      canConfirm: serverDraft.state === 'current'
        && dirtySections.size === 0
        && !dirtySections.has(sectionKey)
        && confirmation !== null
        && (sectionKey !== 'section.optional-context' || optionalOpened),
    };
  };
  const readinessSummary = (
    suffix: 'mobile' | 'desktop',
    className: string,
  ) => (
    <section
      aria-labelledby={`trail-readiness-heading-${suffix}`}
      className={className}
    >
      <h2
        id={`trail-readiness-heading-${suffix}`}
        className="text-base font-semibold text-accent-cobalt"
      >
        {copy.readinessTitle}
      </h2>
      <p className="mt-2 break-words text-sm font-semibold leading-6" aria-live="polite">
        {readinessHeadline}
      </p>
      <Button
        id={`trail-readiness-action-${suffix}`}
        type="button"
        className="mt-4 min-h-11 w-full whitespace-normal motion-reduce:transition-none"
        disabled={!allConfirmed || pending || busyAction !== null}
        onClick={() => { void checkReadiness(); }}
      >
        {copy.checkReadiness}
      </Button>
    </section>
  );

  return (
    <main
      data-state={pending
        ? 'memory-only-unsaved'
        : !online
          ? 'offline'
          : serverDraft.state === 'absent'
            ? 'absent'
            : 'online-saved'}
      className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8"
    >
      <header className="mb-6 flex min-w-0 flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-semibold tracking-tight">{copy.title}</h1>
          <p className="mt-2 max-w-[72ch] break-words text-sm leading-6 text-muted-foreground dark:text-foreground/80">
            {copy.support}
          </p>
        </div>
        <div className="max-w-xs sm:text-right">
          <DropdownMenu open={moreActionsOpen} onOpenChange={handleMoreActionsOpenChange}>
            <DropdownMenuTrigger
              ref={moreActionsRef}
              render={
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11 whitespace-normal motion-reduce:transition-none"
                />
              }
            >
              {copy.moreActions}
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              finalFocus={exportMenuClosing ? moreActionsRef : undefined}
              className="w-80 min-w-64 max-w-[calc(100vw-2rem)] motion-reduce:animate-none"
            >
              <DropdownMenuItem className="min-h-11 whitespace-normal" onClick={() => setDialogAction('reset')}>
                {copy.reset}
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={exportStatus === 'preparing'}
                aria-busy={exportStatus === 'preparing'}
                closeOnClick={false}
                className="min-h-11 whitespace-normal"
                onClick={() => { void ownerExport.run(); }}
              >
                <span className="flex min-w-0 flex-col gap-0.5 text-left">
                  <span>{exportStatus === 'preparing' ? copy.exportBusy : copy.export}</span>
                  <span className="break-words text-xs text-muted-foreground dark:text-foreground/80">
                    {copy.exportSupport}
                  </span>
                </span>
              </DropdownMenuItem>
              <DropdownMenuItem variant="destructive" className="min-h-11 whitespace-normal" onClick={() => setDialogAction('delete')}>
                {copy.delete}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <div className="mb-5 min-h-6 space-y-1" aria-live="polite" aria-atomic="true">
        <p className="break-words text-sm text-muted-foreground dark:text-foreground/80">
          {!online
            ? copy.offline
            : slowAction
              ? copy.slow
              : pending
                ? copy.pending
                : notice ?? (serverDraft.state === 'absent' ? copy.notSaved : copy.onlineSaved)}
        </p>
        {!online && pending ? (
          <p className="break-words text-sm font-semibold">{copy.pending}</p>
        ) : null}
      </div>

      <div role="status" aria-live="polite" aria-atomic="true">
        {exportStatus === 'preparing' || exportStatus === 'success' ? (
          <p className="mb-5 break-words text-sm text-muted-foreground dark:text-foreground/80">
            {exportStatus === 'preparing' ? copy.exportBusy : copy.exportSuccess}
          </p>
        ) : null}
      </div>
      {exportStatus === 'error' ? (
        <Alert role="alert" variant="destructive" className="mb-5 dark:*:data-[slot=alert-title]:text-foreground dark:*:data-[slot=alert-description]:text-foreground">
          <AlertDescription className="break-words">{copy.exportError}</AlertDescription>
        </Alert>
      ) : null}

      {operationError ? (
        <Alert variant="destructive" className="mb-5 dark:*:data-[slot=alert-title]:text-foreground dark:*:data-[slot=alert-description]:text-foreground">
          <AlertTitle>{l(t`Trail action did not complete`, t`越野操作未完成`)}</AlertTitle>
          <AlertDescription className="space-y-3">
            <p className="break-words">{operationError}</p>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              onClick={() => {
                if (pendingRef.current || staleConflict) {
                  void reviewLatest();
                } else {
                  void onRefetch().catch(() => undefined);
                }
              }}
            >
              {pending || staleConflict ? copy.reviewLatest : copy.retry}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {validationIssues.length > 0 ? (
        <Alert variant="destructive" className="mb-5 dark:*:data-[slot=alert-title]:text-foreground dark:*:data-[slot=alert-description]:text-foreground">
          <AlertTitle>
            <h2 ref={errorSummaryRef} tabIndex={-1}>{copy.errorSummary}</h2>
          </AlertTitle>
          <AlertDescription>
            <ul className="space-y-2">
              {validationIssues.map((issue) => (
                <li key={issue.id}>
                  <Button
                    type="button"
                    variant="link"
                    className="h-auto min-h-11 max-w-full justify-start whitespace-normal px-0 text-left text-destructive dark:text-foreground"
                    onClick={() => focusValidationIssue(issue)}
                  >
                    {validationLabel(issue)} — {copy.fieldError}
                  </Button>
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      {staleConflict ? (
        <Alert className="mb-5 border-accent-amber/60">
          <AlertTitle>{copy.staleTitle}</AlertTitle>
          <AlertDescription className="space-y-3 dark:text-foreground/80">
            <p>{copy.staleExplanation}</p>
            <TrailPendingComparison
              baseDraft={serverDraft}
              pendingRequest={request}
              pendingInputs={numericInputs}
              latestDraft={latestDraft}
            />
            <div className="flex flex-wrap gap-2">
              {!latestDraft ? (
                <Button type="button" variant="outline" className="min-h-11" onClick={() => { void reviewLatest(); }}>
                  {copy.reviewLatest}
                </Button>
              ) : (
                <>
                  <Button type="button" variant="outline" className="min-h-11 whitespace-normal" onClick={restoreAgainstLatest}>
                    {copy.restorePending}
                  </Button>
                  <Button type="button" variant="outline" className="min-h-11 whitespace-normal" onClick={discardPending}>
                    {copy.discardPending}
                  </Button>
                </>
              )}
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)] lg:items-start">
        {readinessSummary(
          'mobile',
          'min-w-0 border border-border bg-card p-4 lg:hidden',
        )}
        <div className="min-w-0">
          <fieldset
            disabled={busyAction !== null}
            aria-busy={busyAction !== null}
            className="contents"
          >
          <SectionShell
            sectionKey="section.event-duration"
            title={copy.eventSection}
            open={openSections['section.event-duration']}
            onOpenChange={(open) => setOpenSections((current) => ({
              ...current,
              'section.event-duration': open,
            }))}
          >
            <FieldShell id="trail-event-identity" label={copy.event}>
              <div className="flex min-w-0 flex-wrap items-center gap-3">
                <span className="break-words text-sm">{copy.currentEvent}</span>
                <a
                  href="/goal"
                  className="inline-flex min-h-11 items-center rounded-lg px-2 text-sm text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {copy.editGoal}
                </a>
              </div>
            </FieldShell>
            <FieldShell
              id="trail-event-date"
              htmlFor="trail-event-date"
              label={copy.eventDate}
              invalidMessage={validationMessageFor('trail-event-date')}
              meta={provenanceMeta(
                currentFields?.event_date as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <div className="space-y-2">
                <Input
                  id="trail-event-date"
                  type="date"
                  value={request.course_demand.fields.event_date.state === 'known'
                    ? request.course_demand.fields.event_date.value
                    : ''}
                  onChange={(event) => updateCourse(
                    'event_date',
                    known(event.target.value),
                    'section.event-duration',
                  )}
                  className="h-11 max-w-sm font-data"
                />
                <UnknownButton
                  unknown={request.course_demand.fields.event_date.state === 'unknown'}
                  label={copy.unknown}
                  onChange={(value) => {
                    if (value) updateCourse('event_date', unknown(), 'section.event-duration');
                  }}
                />
              </div>
            </FieldShell>
            <FieldShell
              id="trail-race-distance"
              htmlFor="trail-race-distance"
              label={copy.raceDistance}
              invalidMessage={validationMessageFor('trail-race-distance')}
              meta={provenanceMeta(
                currentFields?.distance_meters as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <NumberEditor
                id="trail-race-distance"
                value={numericInputs.distanceKm}
                unknown={request.course_demand.fields.distance_meters.state === 'unknown'}
                unknownLabel={copy.unknown}
                inputLabel={copy.raceDistance}
                suffix="km"
                onValueChange={(value) => updateNumeric('distanceKm', value, 'section.event-duration')}
                onUnknownChange={(value) => {
                  if (value) updateCourse('distance_meters', unknown(), 'section.event-duration');
                }}
              />
            </FieldShell>
            <div className="grid min-w-0 gap-5 sm:grid-cols-2">
              <FieldShell
                id="trail-total-ascent"
                htmlFor="trail-total-ascent"
                label={copy.totalAscent}
                invalidMessage={validationMessageFor('trail-total-ascent')}
                meta={provenanceMeta(
                  currentFields?.total_ascent_m as TrailServerEnvelope<unknown> | null,
                  provenanceLabels,
                  copy.modelVersion,
                )}
              >
                <NumberEditor
                  id="trail-total-ascent"
                  value={numericInputs.totalAscentM}
                  unknown={request.course_demand.fields.total_ascent_m.state === 'unknown'}
                  unknownLabel={copy.unknown}
                  inputLabel={copy.totalAscent}
                  suffix="m"
                  onValueChange={(value) => updateNumeric('totalAscentM', value, 'section.event-duration')}
                  onUnknownChange={(value) => {
                    if (value) updateCourse('total_ascent_m', unknown(), 'section.event-duration');
                  }}
                />
              </FieldShell>
              <FieldShell
                id="trail-total-descent"
                htmlFor="trail-total-descent"
                label={copy.totalDescent}
                invalidMessage={validationMessageFor('trail-total-descent')}
                meta={provenanceMeta(
                  currentFields?.total_descent_m as TrailServerEnvelope<unknown> | null,
                  provenanceLabels,
                  copy.modelVersion,
                )}
              >
                <NumberEditor
                  id="trail-total-descent"
                  value={numericInputs.totalDescentM}
                  unknown={request.course_demand.fields.total_descent_m.state === 'unknown'}
                  unknownLabel={copy.unknown}
                  inputLabel={copy.totalDescent}
                  suffix="m"
                  onValueChange={(value) => updateNumeric('totalDescentM', value, 'section.event-duration')}
                  onUnknownChange={(value) => {
                    if (value) updateCourse('total_descent_m', unknown(), 'section.event-duration');
                  }}
                />
              </FieldShell>
            </div>
            <FieldShell
              id="trail-planning-minimum"
              label={copy.planningMinimum}
              invalidMessage={validationMessageFor('trail-planning-minimum')}
              description={copy.planningHelp}
              meta={provenanceMeta(
                currentFields?.planning_duration_range as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <DurationEditor
                id="trail-planning-minimum"
                unknown={request.course_demand.fields.planning_duration_range.state === 'unknown'}
                hours={numericInputs.planningMinimumHours}
                minutes={numericInputs.planningMinimumMinutes}
                hoursLabel={`${copy.planningMinimum} · ${copy.hours}`}
                minutesLabel={`${copy.planningMinimum} · ${copy.minutes}`}
                unknownLabel={copy.unknown}
                onHoursChange={(value) => updateNumeric('planningMinimumHours', value, 'section.event-duration')}
                onMinutesChange={(value) => updateNumeric('planningMinimumMinutes', value, 'section.event-duration')}
                onUnknownChange={(value) => {
                  if (!value || activeOperationRef.current) return;
                  setNumericInputs(clearPlanningDurationNumericInputs);
                  setRequest((current) => replaceCourseField(
                    current,
                    'planning_duration_range',
                    unknown(),
                  ));
                  invalidateReadiness('section.event-duration');
                }}
              />
            </FieldShell>
            <FieldShell id="trail-planning-maximum" label={copy.planningMaximum}>
              <DurationEditor
                id="trail-planning-maximum"
                unknown={request.course_demand.fields.planning_duration_range.state === 'unknown'}
                hours={numericInputs.planningMaximumHours}
                minutes={numericInputs.planningMaximumMinutes}
                hoursLabel={`${copy.planningMaximum} · ${copy.hours}`}
                minutesLabel={`${copy.planningMaximum} · ${copy.minutes}`}
                unknownLabel={copy.unknown}
                onHoursChange={(value) => updateNumeric('planningMaximumHours', value, 'section.event-duration')}
                onMinutesChange={(value) => updateNumeric('planningMaximumMinutes', value, 'section.event-duration')}
                onUnknownChange={(value) => {
                  if (!value || activeOperationRef.current) return;
                  setNumericInputs(clearPlanningDurationNumericInputs);
                  setRequest((current) => replaceCourseField(
                    current,
                    'planning_duration_range',
                    unknown(),
                  ));
                  invalidateReadiness('section.event-duration');
                }}
              />
            </FieldShell>
            <FieldShell
              id="trail-event-format"
              htmlFor="trail-event-format"
              label={copy.eventFormat}
              meta={provenanceMeta(
                currentFields?.event_format as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <EnumEditor
                id="trail-event-format"
                envelope={request.course_demand.fields.event_format}
                options={eventFormatOptions}
                unknownLabel={copy.unknown}
                placeholder={copy.choose}
                onChange={(value) => updateCourse('event_format', value, 'section.event-duration')}
              />
            </FieldShell>
            <FieldShell id="trail-distance-category" htmlFor="trail-distance-category" label={copy.distanceCategory}>
              <EnumEditor
                id="trail-distance-category"
                envelope={request.course_demand.fields.distance_family}
                options={distanceFamilyOptions}
                unknownLabel={copy.unknown}
                placeholder={copy.choose}
                onChange={(value) => updateCourse('distance_family', value, 'section.event-duration')}
              />
            </FieldShell>
            <FieldShell id="trail-planning-goal" htmlFor="trail-planning-goal" label={copy.planningGoal}>
              <EnumEditor
                id="trail-planning-goal"
                envelope={request.course_demand.fields.planning_intent}
                options={planningIntentOptions}
                unknownLabel={copy.unknown}
                placeholder={copy.choose}
                onChange={(value) => updateCourse('planning_intent', value, 'section.event-duration')}
              />
            </FieldShell>
            <ConfirmBar
              sectionKey="section.event-duration"
              {...confirmationProps('section.event-duration')}
              busy={busyAction !== null}
              confirmLabel={copy.confirmSection}
              confirmedLabel={copy.confirmedRevision}
              changedLabel={copy.changedConfirmAgain}
              saveFirstLabel={copy.saveBeforeConfirming}
              onConfirm={handleConfirmSection}
            />
          </SectionShell>
          <SectionShell
            sectionKey="section.grade-footing"
            title={copy.gradeSection}
            open={openSections['section.grade-footing']}
            onOpenChange={(open) => setOpenSections((current) => ({
              ...current,
              'section.grade-footing': open,
            }))}
          >
            <FieldShell
              id="trail-grade-below-neg-10"
              label={copy.gradeDistribution}
              invalidMessage={validationMessageFor('trail-grade-below_neg_10')}
              description={copy.gradeExplanation}
              meta={provenanceMeta(
                currentFields?.grade_distribution as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <div className="space-y-3">
                {GRADE_KEYS.map((key, index) => {
                  const inputKeys: readonly NumericInputKey[] = [
                    'gradeBelowNeg10',
                    'gradeNeg10ToNeg3',
                    'gradeNearLevel',
                    'gradePos3ToPos10',
                    'gradePos10AndAbove',
                  ];
                  const inputKey = inputKeys[index];
                  return (
                    <div key={key} className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_9rem] sm:items-center">
                      <Label htmlFor={`trail-grade-${key}`} className="whitespace-normal leading-5">
                        {gradeLabels[key]}
                      </Label>
                      <div className="flex items-center gap-2">
                        <Input
                          id={`trail-grade-${key}`}
                          inputMode="decimal"
                          value={numericInputs[inputKey]}
                          onChange={(event) => updateNumeric(
                            inputKey,
                            event.target.value,
                            'section.grade-footing',
                          )}
                          className="h-11 font-data"
                        />
                        <span className="font-data text-sm text-muted-foreground dark:text-foreground/80">%</span>
                      </div>
                    </div>
                  );
                })}
                <div className="flex min-h-11 items-center justify-between border-t border-border pt-2 text-sm font-semibold">
                  <span>{copy.total}</span>
                  <span className="font-data">{gradeTotal === null ? '—' : gradeTotal.toFixed(2)}%</span>
                </div>
                <UnknownButton
                  unknown={request.course_demand.fields.grade_distribution.state === 'unknown'
                    && gradeInputsAreBlank}
                  label={copy.unknown}
                  onChange={(value) => {
                    if (value) {
                      setNumericInputs((current) => ({
                        ...current,
                        gradeBelowNeg10: '',
                        gradeNeg10ToNeg3: '',
                        gradeNearLevel: '',
                        gradePos3ToPos10: '',
                        gradePos10AndAbove: '',
                      }));
                      updateCourse(
                        'grade_distribution',
                        unknown(),
                        'section.grade-footing',
                      );
                    }
                  }}
                />
              </div>
            </FieldShell>
            <FieldShell
              id="trail-course-footing"
              label={copy.footing}
              invalidMessage={validationMessageFor('trail-course-footing')}
              meta={provenanceMeta(
                currentFields?.course_footing as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <MultiSelectEditor
                id="trail-course-footing"
                envelope={request.course_demand.fields.course_footing}
                options={footingOptions}
                unknownLabel={copy.unknown}
                onChange={(value) => updateCourse('course_footing', value, 'section.grade-footing')}
              />
            </FieldShell>
            <FieldShell id="trail-hands-assist" label={copy.hands}>
              <TriStateEditor
                id="trail-hands-assist"
                envelope={request.course_demand.fields.hands_assist}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateCourse('hands_assist', value, 'section.grade-footing')}
              />
            </FieldShell>
            <FieldShell id="trail-fixed-rope" label={copy.rope}>
              <TriStateEditor
                id="trail-fixed-rope"
                envelope={request.course_demand.fields.fixed_rope}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateCourse('fixed_rope', value, 'section.grade-footing')}
              />
            </FieldShell>
            <ConfirmBar
              sectionKey="section.grade-footing"
              {...confirmationProps('section.grade-footing')}
              busy={busyAction !== null}
              confirmLabel={copy.confirmSection}
              confirmedLabel={copy.confirmedRevision}
              changedLabel={copy.changedConfirmAgain}
              saveFirstLabel={copy.saveBeforeConfirming}
              onConfirm={handleConfirmSection}
            />
          </SectionShell>
          <SectionShell
            sectionKey="section.training-access"
            title={copy.trainingSection}
            open={openSections['section.training-access']}
            onOpenChange={(open) => setOpenSections((current) => ({
              ...current,
              'section.training-access': open,
            }))}
          >
            <FieldShell
              id="trail-available-days"
              label={copy.availableDays}
              invalidMessage={validationMessageFor('trail-available-days')}
              meta={provenanceMeta(
                currentConstraints?.available_weekdays as TrailServerEnvelope<unknown> | null,
                provenanceLabels,
                copy.modelVersion,
              )}
            >
              <MultiSelectEditor
                id="trail-available-days"
                envelope={request.constraints.available_weekdays}
                options={weekdayOptions}
                unknownLabel={copy.unknown}
                onChange={(value) => updateConstraint('available_weekdays', value)}
              />
            </FieldShell>
            <FieldShell
              id="trail-weekly-time"
              label={copy.weeklyTime}
              invalidMessage={validationMessageFor('trail-weekly-time')}
            >
              <DurationEditor
                id="trail-weekly-time"
                unknown={request.constraints.weekly_time_limit_min.state === 'unknown'}
                hours={numericInputs.weeklyHours}
                minutes={numericInputs.weeklyMinutes}
                hoursLabel={`${copy.weeklyTime} · ${copy.hours}`}
                minutesLabel={`${copy.weeklyTime} · ${copy.minutes}`}
                unknownLabel={copy.unknown}
                onHoursChange={(value) => updateNumeric('weeklyHours', value, 'section.training-access')}
                onMinutesChange={(value) => updateNumeric('weeklyMinutes', value, 'section.training-access')}
                onUnknownChange={(value) => {
                  if (value) updateConstraint('weekly_time_limit_min', unknown());
                }}
              />
            </FieldShell>
            <FieldShell
              id="trail-session-time"
              label={copy.longestSession}
              invalidMessage={validationMessageFor('trail-session-time')}
            >
              <DurationEditor
                id="trail-session-time"
                unknown={request.constraints.maximum_session_duration_min.state === 'unknown'}
                hours={numericInputs.sessionHours}
                minutes={numericInputs.sessionMinutes}
                hoursLabel={`${copy.longestSession} · ${copy.hours}`}
                minutesLabel={`${copy.longestSession} · ${copy.minutes}`}
                unknownLabel={copy.unknown}
                onHoursChange={(value) => updateNumeric('sessionHours', value, 'section.training-access')}
                onMinutesChange={(value) => updateNumeric('sessionMinutes', value, 'section.training-access')}
                onUnknownChange={(value) => {
                  if (value) updateConstraint('maximum_session_duration_min', unknown());
                }}
              />
            </FieldShell>
            <FieldShell
              id="trail-unavailable-date"
              label={copy.unavailableDates}
              description={l(
                t`Choose at most 14 dates inside the displayed 14-day horizon.`,
                t`最多选择显示的 14 天范围内的 14 个日期。`,
              )}
            >
              <div className="space-y-3">
                <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
                  <Input
                    id="trail-unavailable-date"
                    aria-label={copy.unavailableDates}
                    type="date"
                    min={localIsoDate()}
                    max={localIsoDate(13)}
                    value={unavailableDateInput}
                    onChange={(event) => setUnavailableDateInput(event.target.value)}
                    className="h-11 max-w-sm font-data"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-11"
                    disabled={!unavailableDateInput}
                    onClick={() => {
                      const current = request.constraints.unavailable_dates.state === 'known'
                        ? request.constraints.unavailable_dates.value
                        : [];
                      if (
                        unavailableDateInput >= localIsoDate()
                        && unavailableDateInput <= localIsoDate(13)
                        && current.length < 14
                        && !current.includes(unavailableDateInput)
                      ) {
                        updateConstraint(
                          'unavailable_dates',
                          known([...current, unavailableDateInput].sort()),
                        );
                        setUnavailableDateInput('');
                      }
                    }}
                  >
                    {copy.addDate}
                  </Button>
                </div>
                {request.constraints.unavailable_dates.state === 'known' ? (
                  request.constraints.unavailable_dates.value.length > 0 ? (
                    <ul className="flex flex-wrap gap-2">
                      {request.constraints.unavailable_dates.value.map((date) => (
                        <li key={date}>
                          <Button
                            type="button"
                            variant="outline"
                            className="min-h-11 whitespace-normal font-data"
                            aria-label={`${copy.removeDate}: ${formatIsoDate(date, i18n.locale)}`}
                            onClick={() => updateConstraint(
                              'unavailable_dates',
                              known(request.constraints.unavailable_dates.state === 'known'
                                ? request.constraints.unavailable_dates.value.filter((item) => item !== date)
                                : []),
                            )}
                          >
                            {formatIsoDate(date, i18n.locale)}
                          </Button>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="text-sm text-muted-foreground dark:text-foreground/80">{copy.noDates}</p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant={request.constraints.unavailable_dates.state === 'known'
                      && request.constraints.unavailable_dates.value.length === 0
                      ? 'secondary'
                      : 'outline'}
                    aria-pressed={request.constraints.unavailable_dates.state === 'known'
                      && request.constraints.unavailable_dates.value.length === 0}
                    className="min-h-11 min-w-11"
                    onClick={() => updateConstraint('unavailable_dates', known([]))}
                  >
                    {copy.noDates}
                  </Button>
                  <UnknownButton
                    unknown={request.constraints.unavailable_dates.state === 'unknown'}
                    label={copy.unknown}
                    onChange={(value) => {
                      if (value) {
                        setUnavailableDateInput('');
                        updateConstraint('unavailable_dates', unknown());
                      }
                    }}
                  />
                </div>
              </div>
            </FieldShell>
            <FieldShell
              id="trail-preferred-day"
              htmlFor="trail-preferred-day"
              label={copy.preferredDay}
              invalidMessage={validationMessageFor('trail-preferred-day')}
            >
              <Select
                value={request.constraints.preferred_longest_weekday === undefined
                  ? 'none'
                  : String(request.constraints.preferred_longest_weekday)}
                onValueChange={(value) => {
                  if (activeOperationRef.current) return;
                  setRequest((current) => {
                    const next = { ...current, constraints: { ...current.constraints } };
                    if (value === 'none' || value === null) {
                      delete next.constraints.preferred_longest_weekday;
                    } else {
                      next.constraints.preferred_longest_weekday = Number(value);
                    }
                    return next;
                  });
                  invalidateReadiness('section.training-access');
                }}
              >
                <SelectTrigger id="trail-preferred-day" className="min-h-11 w-full max-w-sm">
                  <SelectValue>
                    {request.constraints.preferred_longest_weekday === undefined
                      ? copy.noPreference
                      : weekdayOptions.find((option) =>
                        option.value === request.constraints.preferred_longest_weekday)?.label}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent className="motion-reduce:animate-none">
                  <SelectItem value="none" className="min-h-11">{copy.noPreference}</SelectItem>
                  {weekdayOptions.map((option) => (
                    <SelectItem key={option.value} value={String(option.value)} className="min-h-11">
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FieldShell>
            <FieldShell id="trail-uphill-access" label={copy.uphillAccess}>
              <TriStateEditor
                id="trail-uphill-access"
                envelope={request.constraints.nontechnical_three_minute_uphill_access}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateConstraint('nontechnical_three_minute_uphill_access', value)}
              />
            </FieldShell>
            <FieldShell id="trail-downhill-access" label={copy.downhillAccess}>
              <TriStateEditor
                id="trail-downhill-access"
                envelope={request.constraints.controlled_downhill_access}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateConstraint('controlled_downhill_access', value)}
              />
            </FieldShell>
            <FieldShell
              id="trail-training-footing"
              label={copy.trainingFooting}
              invalidMessage={validationMessageFor('trail-training-footing')}
            >
              <MultiSelectEditor
                id="trail-training-footing"
                envelope={request.constraints.accessible_footing}
                options={footingOptions}
                unknownLabel={copy.unknown}
                onChange={(value) => updateConstraint('accessible_footing', value)}
              />
            </FieldShell>
            <FieldShell id="trail-adult-scope" label={copy.adultScope}>
              <TriStateEditor
                id="trail-adult-scope"
                envelope={request.constraints.adult_nonclinical_scope_confirmed}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateConstraint('adult_nonclinical_scope_confirmed', value)}
              />
            </FieldShell>
            <FieldShell id="trail-performance-scope" label={copy.performanceScope}>
              <TriStateEditor
                id="trail-performance-scope"
                envelope={request.constraints.performance_intent_confirmed}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateConstraint('performance_intent_confirmed', value)}
              />
            </FieldShell>
            <FieldShell id="trail-symptom-stop" label={copy.symptoms}>
              <TriStateEditor
                id="trail-symptom-stop"
                envelope={request.constraints.current_symptom_stop}
                yesLabel={copy.yes}
                noLabel={copy.no}
                unknownLabel={copy.notSure}
                onChange={(value) => updateConstraint('current_symptom_stop', value)}
              />
            </FieldShell>
            <ConfirmBar
              sectionKey="section.training-access"
              {...confirmationProps('section.training-access')}
              busy={busyAction !== null}
              confirmLabel={copy.confirmSection}
              confirmedLabel={copy.confirmedRevision}
              changedLabel={copy.changedConfirmAgain}
              saveFirstLabel={copy.saveBeforeConfirming}
              onConfirm={handleConfirmSection}
            />
          </SectionShell>
          <SectionShell
            sectionKey="section.recent-experience"
            title={copy.recentSection}
            description={l(
              t`This server-derived receipt is read-only. Correct source activities from Activities; plan start does not accept replacement attestations.`,
              t`此服务端推导回执为只读。请在活动记录中更正来源活动；计划开始流程不接受替代证明。`,
            )}
            open={openSections['section.recent-experience']}
            onOpenChange={(open) => setOpenSections((current) => ({
              ...current,
              'section.recent-experience': open,
            }))}
          >
            {[
              {
                id: 'trail-history-running',
                label: copy.continuity,
                value: history
                  ? l(
                    t`${history.usable_completed_weeks} completed weeks · ${history.recent_modal_running_frequency} runs per week`,
                    t`${history.usable_completed_weeks} 个完整周 · 每周 ${history.recent_modal_running_frequency} 次跑步`,
                  )
                  : copy.notEvaluated,
                freshness: history?.latest_run_date ?? null,
              },
              {
                id: 'trail-history-ascent',
                label: copy.ascentExposure,
                value: history
                  ? l(
                    t`${history.comparable_ascent_sessions_within_window} comparable sessions · ${history.recent_maximum_session_ascent_meters} m maximum observed ascent`,
                    t`${history.comparable_ascent_sessions_within_window} 次可比训练 · 单次已观察最大爬升 ${history.recent_maximum_session_ascent_meters} 米`,
                  )
                  : copy.notEvaluated,
                freshness: history?.latest_comparable_ascent_session_date ?? null,
              },
              {
                id: 'trail-history-descent',
                label: copy.descentExposure,
                value: history
                  ? l(
                    t`${history.comparable_descent_sessions_within_window} comparable sessions · ${history.recent_maximum_session_descent_meters} m maximum observed descent`,
                    t`${history.comparable_descent_sessions_within_window} 次可比训练 · 单次已观察最大下降 ${history.recent_maximum_session_descent_meters} 米`,
                  )
                  : copy.notEvaluated,
                freshness: history?.latest_comparable_descent_session_date ?? null,
              },
              {
                id: 'trail-history-footing',
                label: copy.observedFooting,
                value: history
                  ? history.recently_observed_footing.length > 0
                    ? history.recently_observed_footing.map((value) => footingOptions.find((item) => item.value === value)?.label ?? '').filter(Boolean).join(', ')
                    : l(t`No qualifying footing observed`, t`未观察到符合条件的路面`)
                  : copy.notEvaluated,
                freshness: history?.observation_window_end ?? null,
              },
            ].map((row) => (
              <article key={row.id} id={row.id} tabIndex={-1} className="min-w-0 border-t border-border pt-4 first:border-t-0 first:pt-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <h3 className="break-words text-sm font-semibold">{row.label}</h3>
                <p className="mt-1 break-words font-data text-sm">{row.value}</p>
                <dl className="mt-3 grid min-w-0 gap-2 text-xs text-muted-foreground dark:text-foreground/80 sm:grid-cols-2">
                  <div>
                    <dt>{copy.observationWindow}</dt>
                    <dd className="mt-1 break-words font-data">
                      {history
                        ? `${formatIsoDate(history.observation_window_start, i18n.locale)} – ${formatIsoDate(history.observation_window_end, i18n.locale)}`
                        : copy.notEvaluated}
                    </dd>
                  </div>
                  <div>
                    <dt>{copy.freshness}</dt>
                    <dd className="mt-1 font-data">{row.freshness ? formatIsoDate(row.freshness, i18n.locale) : copy.notEvaluated}</dd>
                  </div>
                  <div>
                    <dt>{copy.serverSource}</dt>
                    <dd className="mt-1">{copy.fromHistory}</dd>
                  </div>
                  <div>
                    <dt>{copy.sourceRevision}</dt>
                    <dd className="mt-1 break-all font-data">{historyRevision ?? '—'}</dd>
                  </div>
                </dl>
              </article>
            ))}
            {historyComparisonVisible ? (
              <div className="border-t border-border pt-4">
                <h3 className="text-sm font-semibold text-accent-cobalt">{copy.compareHistory}</h3>
                <p className="mt-2 break-words text-sm leading-6 text-muted-foreground dark:text-foreground/80">{copy.historyComparisonHelp}</p>
                <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-muted-foreground dark:text-foreground/80">
                      {copy.requested}: {copy.weeklyTime}
                    </dt>
                    <dd className="font-data text-sm">
                      {request.constraints.weekly_time_limit_min.state === 'known'
                        ? `${numericInputs.weeklyHours} h ${numericInputs.weeklyMinutes} min`
                        : copy.unknown}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground dark:text-foreground/80">
                      {copy.fromHistory}: {copy.weeklyTime}
                    </dt>
                    <dd className="font-data text-sm">
                      {history
                        ? `${history.recent_median_usable_weekly_minutes}–${history.recent_maximum_usable_weekly_minutes} min`
                        : copy.notEvaluated}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground dark:text-foreground/80">
                      {copy.requested}: {copy.longestSession}
                    </dt>
                    <dd className="font-data text-sm">
                      {request.constraints.maximum_session_duration_min.state === 'known'
                        ? `${numericInputs.sessionHours} h ${numericInputs.sessionMinutes} min`
                        : copy.unknown}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground dark:text-foreground/80">
                      {copy.fromHistory}: {copy.longestSession}
                    </dt>
                    <dd className="font-data text-sm">
                      {history
                        ? `${history.recent_maximum_session_minutes} min`
                        : copy.notEvaluated}
                    </dd>
                  </div>
                </dl>
              </div>
            ) : null}
          </SectionShell>
          <SectionShell
            sectionKey="section.optional-context"
            title={copy.optionalSection}
            description={l(
              t`Open and review this section before confirming it. Each group can be set to unknown without inventing defaults.`,
              t`确认前请打开并核对本节。每组都可设为未知，不会虚构默认值。`,
            )}
            open={openSections['section.optional-context']}
            onOpenChange={(open) => {
              setOpenSections((current) => ({
                ...current,
                'section.optional-context': open,
              }));
              if (open) setOptionalOpened(true);
            }}
          >
            <section aria-labelledby="trail-environment-heading" className="space-y-5 border-t border-border pt-5 first:border-t-0 first:pt-0">
              <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h3 id="trail-environment-heading" className="text-base font-semibold">{copy.environment}</h3>
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11 whitespace-normal"
                  onClick={() => {
                    if (activeOperationRef.current) return;
                    setRequest((current) => setOptionalGroupUnknown(current, 'environment'));
                    setNumericInputs((current) => clearOptionalGroupNumericInputs(
                      current,
                      'environment',
                    ));
                    invalidateReadiness('section.optional-context');
                  }}
                >
                  {copy.setGroupUnknown}
                </Button>
              </div>
              <FieldShell
                id="trail-maximum-altitude"
                htmlFor="trail-maximum-altitude"
                label={copy.maximumAltitude}
                invalidMessage={validationMessageFor('trail-maximum-altitude')}
              >
                <NumberEditor
                  id="trail-maximum-altitude"
                  value={numericInputs.maximumAltitudeM}
                  unknown={request.course_demand.fields.optional_context.environment.maximum_altitude_m.state === 'unknown'}
                  unknownLabel={copy.unknown}
                  inputLabel={copy.maximumAltitude}
                  suffix="m"
                  onValueChange={(value) => updateNumeric('maximumAltitudeM', value, 'section.optional-context')}
                  onUnknownChange={(value) => {
                    if (value) updateOptional('environment', 'maximum_altitude_m', unknown());
                  }}
                />
              </FieldShell>
              <FieldShell
                id="trail-temperature-minimum"
                label={copy.temperatureRange}
                invalidMessage={
                  validationMessageFor('trail-temperature-minimum')
                  ?? validationMessageFor('trail-temperature-maximum')
                }
              >
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="trail-temperature-minimum">{copy.minimumTemperature}</Label>
                    <NumberEditor
                      id="trail-temperature-minimum"
                      value={numericInputs.temperatureMinimumC}
                      unknown={request.course_demand.fields.optional_context.environment.temperature_min_c.state === 'unknown'}
                      unknownLabel={copy.unknown}
                      inputLabel={copy.minimumTemperature}
                      suffix="°C"
                      onValueChange={(value) => updateNumeric('temperatureMinimumC', value, 'section.optional-context')}
                      onUnknownChange={(value) => {
                        if (value) updateOptional('environment', 'temperature_min_c', unknown());
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="trail-temperature-maximum">{copy.maximumTemperature}</Label>
                    <NumberEditor
                      id="trail-temperature-maximum"
                      value={numericInputs.temperatureMaximumC}
                      unknown={request.course_demand.fields.optional_context.environment.temperature_max_c.state === 'unknown'}
                      unknownLabel={copy.unknown}
                      inputLabel={copy.maximumTemperature}
                      suffix="°C"
                      onValueChange={(value) => updateNumeric('temperatureMaximumC', value, 'section.optional-context')}
                      onUnknownChange={(value) => {
                        if (value) updateOptional('environment', 'temperature_max_c', unknown());
                      }}
                    />
                  </div>
                </div>
              </FieldShell>
              <FieldShell
                id="trail-humidity-minimum"
                label={copy.humidityRange}
                invalidMessage={
                  validationMessageFor('trail-humidity-minimum')
                  ?? validationMessageFor('trail-humidity-maximum')
                }
              >
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="trail-humidity-minimum">{copy.minimumHumidity}</Label>
                    <NumberEditor
                      id="trail-humidity-minimum"
                      value={numericInputs.humidityMinimumPct}
                      unknown={request.course_demand.fields.optional_context.environment.humidity_min_pct.state === 'unknown'}
                      unknownLabel={copy.unknown}
                      inputLabel={copy.minimumHumidity}
                      suffix="%"
                      onValueChange={(value) => updateNumeric('humidityMinimumPct', value, 'section.optional-context')}
                      onUnknownChange={(value) => {
                        if (value) updateOptional('environment', 'humidity_min_pct', unknown());
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="trail-humidity-maximum">{copy.maximumHumidity}</Label>
                    <NumberEditor
                      id="trail-humidity-maximum"
                      value={numericInputs.humidityMaximumPct}
                      unknown={request.course_demand.fields.optional_context.environment.humidity_max_pct.state === 'unknown'}
                      unknownLabel={copy.unknown}
                      inputLabel={copy.maximumHumidity}
                      suffix="%"
                      onValueChange={(value) => updateNumeric('humidityMaximumPct', value, 'section.optional-context')}
                      onUnknownChange={(value) => {
                        if (value) updateOptional('environment', 'humidity_max_pct', unknown());
                      }}
                    />
                  </div>
                </div>
              </FieldShell>
              <FieldShell id="trail-sun-exposure" htmlFor="trail-sun-exposure" label={copy.sunExposure}>
                <EnumEditor
                  id="trail-sun-exposure"
                  envelope={request.course_demand.fields.optional_context.environment.sun_exposure}
                  options={sunOptions}
                  unknownLabel={copy.unknown}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('environment', 'sun_exposure', value)}
                />
              </FieldShell>
              <FieldShell id="trail-wind-exposure" htmlFor="trail-wind-exposure" label={copy.windExposure}>
                <EnumEditor
                  id="trail-wind-exposure"
                  envelope={request.course_demand.fields.optional_context.environment.wind_exposure}
                  options={windOptions}
                  unknownLabel={copy.unknown}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('environment', 'wind_exposure', value)}
                />
              </FieldShell>
              <FieldShell
                id="trail-conditions-basis"
                htmlFor="trail-conditions-basis"
                label={copy.conditionsBasis}
                description={request.course_demand.fields.optional_context.environment.conditions_basis.state === 'known'
                  && request.course_demand.fields.optional_context.environment.conditions_basis.value === 'athlete_assumption'
                  ? copy.assumptionHelp
                  : undefined}
              >
                <EnumEditor
                  id="trail-conditions-basis"
                  envelope={request.course_demand.fields.optional_context.environment.conditions_basis}
                  options={conditionsOptions}
                  unknownLabel={copy.unknown}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('environment', 'conditions_basis', value)}
                />
              </FieldShell>
            </section>

            <section aria-labelledby="trail-support-heading" className="space-y-5 border-t border-border pt-5">
              <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h3 id="trail-support-heading" className="text-base font-semibold">{copy.supportGroup}</h3>
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11 whitespace-normal"
                  onClick={() => {
                    if (activeOperationRef.current) return;
                    setRequest((current) => setOptionalGroupUnknown(current, 'support'));
                    setNumericInputs((current) => clearOptionalGroupNumericInputs(
                      current,
                      'support',
                    ));
                    invalidateReadiness('section.optional-context');
                  }}
                >
                  {copy.setGroupUnknown}
                </Button>
              </div>
              <FieldShell id="trail-support-setup" htmlFor="trail-support-setup" label={copy.supportSetup}>
                <EnumEditor
                  id="trail-support-setup"
                  envelope={request.course_demand.fields.optional_context.support.aid_support_mode}
                  options={supportOptions}
                  unknownLabel={copy.unknown}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('support', 'aid_support_mode', value)}
                />
              </FieldShell>
              <FieldShell
                id="trail-aid-count"
                htmlFor="trail-aid-count"
                label={copy.aidCount}
                invalidMessage={validationMessageFor('trail-aid-count')}
              >
                <NumberEditor
                  id="trail-aid-count"
                  value={numericInputs.aidStationCount}
                  unknown={request.course_demand.fields.optional_context.support.aid_station_count.state === 'unknown'}
                  unknownLabel={copy.unknown}
                  inputLabel={copy.aidCount}
                  onValueChange={(value) => updateNumeric('aidStationCount', value, 'section.optional-context')}
                  onUnknownChange={(value) => {
                    if (value) updateOptional('support', 'aid_station_count', unknown());
                  }}
                />
              </FieldShell>
              <FieldShell
                id="trail-aid-gap"
                htmlFor="trail-aid-gap"
                label={copy.aidGap}
                invalidMessage={validationMessageFor('trail-aid-gap')}
              >
                <div className="space-y-2">
                  <div className="flex max-w-sm items-center gap-2">
                    <Input
                      id="trail-aid-gap"
                      inputMode="decimal"
                      value={numericInputs.aidStationGapKm}
                      onChange={(event) => updateNumeric('aidStationGapKm', event.target.value, 'section.optional-context')}
                      className="h-11 font-data"
                    />
                    <span className="font-data text-sm text-muted-foreground dark:text-foreground/80">km</span>
                  </div>
                  <ToggleGroup
                    aria-labelledby="trail-aid-gap-label"
                    value={[
                      numericInputs.aidStationGapKm !== ''
                        ? 'value'
                        : request.course_demand.fields.optional_context.support.max_aid_station_gap_m.state === 'unknown'
                          ? 'unknown'
                          : request.course_demand.fields.optional_context.support.max_aid_station_gap_m.value === null
                            ? 'not-applicable'
                            : 'value',
                    ]}
                    onValueChange={(values) => {
                      const value = values.at(-1);
                      if (value === 'unknown') {
                        updateNumeric('aidStationGapKm', '', 'section.optional-context');
                        updateOptional('support', 'max_aid_station_gap_m', unknown<number | null>());
                      }
                      if (value === 'not-applicable') {
                        updateNumeric('aidStationGapKm', '', 'section.optional-context');
                        updateOptional('support', 'max_aid_station_gap_m', known(null));
                      }
                      if (value === 'value') {
                        document.getElementById('trail-aid-gap')?.focus();
                      }
                    }}
                    variant="outline"
                    spacing={2}
                    className="flex w-full flex-wrap gap-2"
                  >
                    <ToggleGroupItem value="value" className="min-h-11 whitespace-normal px-3">{copy.enterDistance}</ToggleGroupItem>
                    <ToggleGroupItem value="not-applicable" className="min-h-11 whitespace-normal px-3">{copy.notApplicable}</ToggleGroupItem>
                    <ToggleGroupItem value="unknown" className="min-h-11 whitespace-normal px-3">{copy.notSure}</ToggleGroupItem>
                  </ToggleGroup>
                </div>
              </FieldShell>
              <FieldShell id="trail-water" htmlFor="trail-water" label={copy.water}>
                <EnumEditor
                  id="trail-water"
                  envelope={request.course_demand.fields.optional_context.support.water_availability}
                  options={availabilityOptions}
                  unknownLabel={copy.notSure}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('support', 'water_availability', value)}
                />
              </FieldShell>
              <FieldShell id="trail-food" htmlFor="trail-food" label={copy.food}>
                <EnumEditor
                  id="trail-food"
                  envelope={request.course_demand.fields.optional_context.support.food_availability}
                  options={availabilityOptions}
                  unknownLabel={copy.notSure}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('support', 'food_availability', value)}
                />
              </FieldShell>
              <FieldShell id="trail-required-equipment" label={copy.requiredEquipment}>
                <MultiSelectEditor
                  id="trail-required-equipment"
                  envelope={request.course_demand.fields.optional_context.support.mandatory_gear}
                  options={gearOptions}
                  unknownLabel={copy.unknown}
                  emptyLabel={copy.noEquipment}
                  allowKnownEmpty
                  onChange={(value) => updateOptional('support', 'mandatory_gear', value)}
                />
              </FieldShell>
            </section>

            <section aria-labelledby="trail-fueling-heading" className="space-y-5 border-t border-border pt-5">
              <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <h3 id="trail-fueling-heading" className="text-base font-semibold">{copy.fueling}</h3>
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11 whitespace-normal"
                  onClick={() => {
                    if (activeOperationRef.current) return;
                    setRequest((current) => setOptionalGroupUnknown(current, 'fueling'));
                    setNumericInputs((current) => clearOptionalGroupNumericInputs(
                      current,
                      'fueling',
                    ));
                    invalidateReadiness('section.optional-context');
                  }}
                >
                  {copy.setGroupUnknown}
                </Button>
              </div>
              <FieldShell
                id="trail-fueling-duration"
                label={copy.fuelingDuration}
                invalidMessage={validationMessageFor('trail-fueling-duration')}
              >
                <DurationEditor
                  id="trail-fueling-duration"
                  unknown={request.course_demand.fields.optional_context.fueling.longest_practiced_duration_min.state === 'unknown'}
                  hours={numericInputs.fuelingHours}
                  minutes={numericInputs.fuelingMinutes}
                  hoursLabel={`${copy.fuelingDuration} · ${copy.hours}`}
                  minutesLabel={`${copy.fuelingDuration} · ${copy.minutes}`}
                  unknownLabel={copy.unknown}
                  onHoursChange={(value) => updateNumeric('fuelingHours', value, 'section.optional-context')}
                  onMinutesChange={(value) => updateNumeric('fuelingMinutes', value, 'section.optional-context')}
                  onUnknownChange={(value) => {
                    if (value) updateOptional('fueling', 'longest_practiced_duration_min', unknown());
                  }}
                />
              </FieldShell>
              <FieldShell
                id="trail-fueling-sessions"
                htmlFor="trail-fueling-sessions"
                label={copy.fuelingSessions}
                invalidMessage={validationMessageFor('trail-fueling-sessions')}
              >
                <NumberEditor
                  id="trail-fueling-sessions"
                  value={numericInputs.fuelingSessions}
                  unknown={request.course_demand.fields.optional_context.fueling.practice_sessions_last_42_days.state === 'unknown'}
                  unknownLabel={copy.unknown}
                  inputLabel={copy.fuelingSessions}
                  onValueChange={(value) => updateNumeric('fuelingSessions', value, 'section.optional-context')}
                  onUnknownChange={(value) => {
                    if (value) updateOptional('fueling', 'practice_sessions_last_42_days', unknown());
                  }}
                />
              </FieldShell>
              <FieldShell id="trail-intake" htmlFor="trail-intake" label={copy.intake}>
                <EnumEditor
                  id="trail-intake"
                  envelope={request.course_demand.fields.optional_context.fueling.intake_form}
                  options={intakeOptions}
                  unknownLabel={copy.unknown}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('fueling', 'intake_form', value)}
                />
              </FieldShell>
              <FieldShell
                id="trail-gut-issue"
                htmlFor="trail-gut-issue"
                label={copy.gutIssue}
                description={l(
                  t`This answer is non-diagnostic and does not prescribe an intake quantity.`,
                  t`此回答不用于诊断，也不提供摄入量处方。`,
                )}
              >
                <EnumEditor
                  id="trail-gut-issue"
                  envelope={request.course_demand.fields.optional_context.fueling.gastrointestinal_experience}
                  options={gutOptions}
                  unknownLabel={copy.notSure}
                  placeholder={copy.choose}
                  onChange={(value) => updateOptional('fueling', 'gastrointestinal_experience', value)}
                />
              </FieldShell>
            </section>
            <ConfirmBar
              sectionKey="section.optional-context"
              {...confirmationProps('section.optional-context')}
              busy={busyAction !== null}
              confirmLabel={copy.confirmSection}
              confirmedLabel={copy.confirmedRevision}
              changedLabel={copy.changedConfirmAgain}
              saveFirstLabel={optionalOpened ? copy.saveBeforeConfirming : l(
                t`Open this section before confirming`,
                t`确认前请先打开本节`,
              )}
              onConfirm={handleConfirmSection}
            />
          </SectionShell>
          <div className="flex min-w-0 flex-col gap-2 border-t border-border pt-6 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              className="min-h-11 whitespace-normal"
              disabled={busyAction !== null || !pending}
              onClick={() => { void saveDraft(false); }}
            >
              {copy.save}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="min-h-11 whitespace-normal"
              disabled={busyAction !== null}
              onClick={() => { void saveDraft(true); }}
            >
              {copy.saveLeave}
            </Button>
          </div>
          </fieldset>
        </div>

        <aside
          id="trail-policy-receipt"
          tabIndex={-1}
          aria-label={copy.readinessTitle}
          className="min-w-0 border border-border bg-card p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring lg:sticky lg:top-6 lg:self-start"
        >
          {readinessSummary(
            'desktop',
            'hidden border-b border-border pb-4 lg:block',
          )}

          <section aria-labelledby="trail-modules-heading" className="border-b border-border py-4">
            <h3 id="trail-modules-heading" className="text-sm font-semibold text-accent-cobalt">
              {copy.modules}
            </h3>
            <ul className="mt-3 space-y-3">
              {TRAIL_MODULE_KEYS.map((moduleKey) => {
                const module = moduleByKey.get(moduleKey) ?? {
                  module: moduleKey,
                  state: 'not_evaluated' as const,
                  reason_target: null,
                };
                const stateLabel = module.state === 'available'
                  ? copy.available
                  : module.state === 'limited'
                    ? copy.limited
                    : copy.notEvaluated;
                const explanation = module.state === 'available'
                  ? copy.moduleAvailableHelp
                  : module.state === 'limited'
                    ? copy.moduleLimitedHelp
                    : copy.moduleNotEvaluatedHelp;
                const safeTarget = module.reason_target
                  ? MODULE_LIMIT_TARGETS[module.reason_target] ?? null
                  : null;
                return (
                  <li key={moduleKey} className="min-w-0 border-t border-border/70 pt-3 first:border-t-0 first:pt-0">
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <span className="break-words text-sm font-medium">{moduleLabels[moduleKey]}</span>
                      <span className="shrink-0 text-xs font-semibold">{stateLabel}</span>
                    </div>
                    <p className="mt-1 break-words text-xs leading-5 text-muted-foreground dark:text-foreground/80">{explanation}</p>
                    {module.state === 'limited' ? (
                      <Button
                        type="button"
                        variant="link"
                        className="mt-1 h-auto min-h-11 max-w-full justify-start whitespace-normal px-0 text-left text-accent-cobalt"
                        onClick={() => {
                          if (safeTarget) void handleSpecialTarget(safeTarget);
                          else focusClosedTarget('action.first-conflicting-field');
                        }}
                      >
                        {copy.nextAction}
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>

          <section aria-labelledby="trail-reasons-heading" className="pt-4">
            <h3 id="trail-reasons-heading" className="text-sm font-semibold text-accent-cobalt">
              {copy.finding}
            </h3>
            {recognizedReasons.length > 0 ? (
              <ol className="mt-3 space-y-4">
                {recognizedReasons.map((reason, index) => (
                  <li key={`${reason.code}-${index}`} className="min-w-0 border-t border-border/70 pt-4 first:border-t-0 first:pt-0">
                    <dl className="space-y-2 text-sm">
                      <div>
                        <dt className="text-xs font-semibold text-accent-cobalt">{copy.finding}</dt>
                        <dd className="mt-1 break-words leading-5">{reason.copy.finding}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-semibold text-accent-cobalt">{copy.effect}</dt>
                        <dd className="mt-1 break-words leading-5 text-muted-foreground dark:text-foreground/80">{reason.copy.effect}</dd>
                      </div>
                    </dl>
                    <Button
                      type="button"
                      variant="link"
                      className="mt-2 h-auto min-h-11 max-w-full justify-start whitespace-normal px-0 text-left text-accent-cobalt"
                      onClick={() => { void handleSpecialTarget(reason.copy.target); }}
                    >
                      {copy.nextAction}: {reason.copy.action}
                    </Button>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-2 break-words text-xs leading-5 text-muted-foreground dark:text-foreground/80">
                {copy.noReceipt}
              </p>
            )}
            <div
              ref={receiptErrorRef}
              id="trail-receipt-error"
              tabIndex={-1}
              role={receiptTargetError || hasUnknownReason ? 'alert' : undefined}
              className="mt-3 break-words text-xs leading-5 text-destructive dark:text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {receiptTargetError
                ?? (hasUnknownReason
                  ? l(
                    t`The receipt contained an unsupported reason. Praxys will not guess its meaning or destination.`,
                    t`回执包含不受支持的原因。Praxys 不会猜测其含义或跳转目标。`,
                  )
                  : null)}
            </div>
          </section>
        </aside>
      </div>

      <Dialog
        open={dialogAction !== null}
        onOpenChange={(open) => { if (!open) setDialogAction(null); }}
      >
        <DialogContent
          closeLabel={isZh ? t`关闭` : t`Close`}
          className="motion-reduce:animate-none sm:max-w-lg"
        >
          <DialogHeader>
            <DialogTitle>
              {dialogAction === 'reset' ? copy.resetTitle : copy.deleteTitle}
            </DialogTitle>
            <DialogDescription className="break-words leading-6 dark:text-foreground/80">
              {dialogAction === 'reset' ? copy.resetExplanation : copy.deleteExplanation}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="min-h-11"
              onClick={() => setDialogAction(null)}
            >
              {copy.cancel}
            </Button>
            <Button
              type="button"
              variant={dialogAction === 'delete' ? 'destructive' : 'outline'}
              className="min-h-11 whitespace-normal"
              disabled={dialogAction === null || busyAction !== null}
              onClick={() => { if (dialogAction) void resetOrDelete(dialogAction); }}
            >
              {dialogAction === 'reset' ? copy.confirmReset : copy.confirmDelete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
