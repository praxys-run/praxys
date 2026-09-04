import { useCallback, useEffect, useMemo, useRef, useState, type ClipboardEvent } from 'react';
import { useLocation } from 'react-router-dom';
import { apiFetch } from '@/hooks/useApi';
import { WEB_VERSION } from '@/lib/version';
import { useLocale } from '@/contexts/LocaleContext';
import type {
  FeedbackKind,
  FeedbackPublicationReadiness,
  FeedbackPublicationResult,
  FeedbackPublicationStatus,
  FeedbackRequest,
  FeedbackResponse,
  FeedbackStatusResponse,
} from '@/types/api';
import {
  applyFeedbackStatusLookup,
  FeedbackReadinessRequestFence,
  feedbackPublicationConsent,
  feedbackPublicationCanCheck,
  feedbackPublicationShouldRefresh,
  getRecentFeedbackId,
  normalizeFeedbackPublicationResult,
  parseRecentFeedbackId,
  setRecentFeedbackId,
} from '@/lib/feedback';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button, buttonVariants } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Check, ImagePlus, X } from 'lucide-react';
import { Trans, useLingui } from '@lingui/react/macro';
import { msg } from '@lingui/core/macro';
import type { MessageDescriptor } from '@lingui/core';
import { cn } from '@/lib/utils';

const MESSAGE_MAX = 5000;
const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // 5 MB
const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const PUBLICATION_REFRESH_DELAY_MS = 2_000;

function PublicationResultCopy({ status }: { status: FeedbackPublicationStatus }) {
  switch (status) {
    case 'private':
      return <Trans>Your feedback was saved privately. No public GitHub issue will be created from this submission.</Trans>;
    case 'queued':
      return (
        <Trans>
          Your feedback was saved. Its scrubbed text summary is queued for review. No public GitHub issue has been
          created yet, and publication is not guaranteed. Screenshots remain private.
        </Trans>
      );
    case 'manual_required':
      return <Trans>Your feedback was saved privately and needs manual review. No public GitHub issue has been created yet.</Trans>;
    case 'published':
      return <Trans>A scrubbed text summary was published to public GitHub. Anyone can view it. Screenshots remain private.</Trans>;
    case 'unknown':
      return (
        <Trans>
          Your feedback was received, but Praxys cannot confirm whether a public GitHub issue was created. Do not
          submit it again yet. Check again later.
        </Trans>
      );
    case 'unavailable':
      return (
        <Trans>
          Your feedback was saved privately. Public GitHub publishing is currently unavailable, so no public issue
          was created.
        </Trans>
      );
  }
}

/** Read a File as a base64 data-URL (`data:image/png;base64,…`) for the API. */
function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

const KIND_OPTIONS: { value: FeedbackKind; label: MessageDescriptor }[] = [
  { value: 'bug', label: msg`Bug report` },
  { value: 'feature', label: msg`Feature request` },
  { value: 'other', label: msg`General feedback` },
];

interface FeedbackDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Preselected category when the dialog opens. Defaults to a bug report. */
  defaultKind?: FeedbackKind;
}

/**
 * Reusable "Send feedback" dialog. Captures the user's report plus basic,
 * non-PII diagnostics (current route, app version, browser, viewport, locale)
 * so the backend triage step has context without the user having to describe
 * their environment. The server keeps submissions private unless the user
 * separately authorizes publishing a scrubbed text summary.
 */
export default function FeedbackDialog({ open, onOpenChange, defaultKind = 'bug' }: FeedbackDialogProps) {
  const { t, i18n } = useLingui();
  const { locale } = useLocale();
  const location = useLocation();
  const [kind, setKind] = useState<FeedbackKind>(defaultKind);
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<FeedbackPublicationResult | null>(null);
  const [resultOrigin, setResultOrigin] = useState<'submitted' | 'status'>('submitted');
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [feedbackId, setFeedbackId] = useState<number | null>(null);
  const [recentFeedbackId, setRecentFeedbackIdState] = useState<number | null>(null);
  const [statusChecking, setStatusChecking] = useState(false);
  const [statusCheckError, setStatusCheckError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [images, setImages] = useState<File[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);
  const [publishExternally, setPublishExternally] = useState(false);
  const [publicationAvailable, setPublicationAvailable] = useState<boolean | null>(null);
  const [transportUnknown, setTransportUnknown] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const submittingRef = useRef(false);
  const publicationRefreshCountRef = useRef(0);
  const resultHeadingRef = useRef<HTMLParagraphElement | null>(null);
  const resultRefreshButtonRef = useRef<HTMLButtonElement | null>(null);
  const readinessFenceRef = useRef(new FeedbackReadinessRequestFence());
  const statusCheckControllerRef = useRef<AbortController | null>(null);
  const statusCheckGenerationRef = useRef(0);
  const resultVisible = result !== null || resultMessage !== null;
  const resultStatus = result?.status;
  const kindItems = KIND_OPTIONS.map((option) => ({
    label: i18n._(option.label),
    value: option.value,
  }));

  // Object URLs for thumbnail previews, derived from the selected files and
  // revoked when the set changes or the dialog unmounts so we don't leak them.
  const previews = useMemo(() => images.map((f) => URL.createObjectURL(f)), [images]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const abortStatusCheck = () => {
    statusCheckGenerationRef.current += 1;
    statusCheckControllerRef.current?.abort();
    statusCheckControllerRef.current = null;
    setStatusChecking(false);
  };

  const abortPublicationReadiness = useCallback(() => {
    readinessFenceRef.current.cancel();
  }, []);

  const reset = () => {
    abortPublicationReadiness();
    abortStatusCheck();
    setMessage('');
    setKind(defaultKind);
    setResult(null);
    setResultOrigin('submitted');
    setResultMessage(null);
    setFeedbackId(null);
    setStatusCheckError(null);
    setError(null);
    setImages([]);
    setImageError(null);
    setPublishExternally(false);
    setPublicationAvailable(null);
    setTransportUnknown(false);
    setSubmitting(false);
    submittingRef.current = false;
    publicationRefreshCountRef.current = 0;
  };

  const handleOpenChange = (next: boolean) => {
    if (!next && submittingRef.current) return;
    if (!next) {
      reset();
    }
    onOpenChange(next);
  };

  useEffect(() => {
    if (!open) {
      abortPublicationReadiness();
      return;
    }
    const readinessFence = readinessFenceRef.current;
    const controller = new AbortController();
    const generation = readinessFence.begin();
    let readinessActive = true;
    readinessFence.attach(generation, controller);
    const isCurrent = () => readinessFence.canApply(
      generation,
      readinessActive,
      controller.signal.aborted,
    );
    queueMicrotask(() => {
      if (!isCurrent()) return;
      setPublishExternally(false);
      setPublicationAvailable(null);
      setTransportUnknown(false);
      setRecentFeedbackIdState(getRecentFeedbackId());
      setStatusCheckError(null);
    });
    void apiFetch('/api/feedback/publication-readiness', {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then(async (response) => {
        if (!isCurrent()) return null;
        if (!response.ok) return { available: false };
        const readiness = (await response.json()) as FeedbackPublicationReadiness;
        return isCurrent() ? readiness : null;
      })
      .then((readiness) => {
        if (readiness == null || !isCurrent()) return;
        setPublicationAvailable(readiness.available === true);
        if (readiness.available !== true) setPublishExternally(false);
      })
      .catch((reason: unknown) => {
        if (!isCurrent()) return;
        if (reason instanceof DOMException && reason.name === 'AbortError') return;
        setPublicationAvailable(false);
        setPublishExternally(false);
      })
      .finally(() => {
        readinessFence.finish(generation, controller);
      });
    return () => {
      readinessActive = false;
      readinessFence.cancel(generation);
    };
  }, [abortPublicationReadiness, open]);

  useEffect(() => {
    if (resultVisible) resultHeadingRef.current?.focus();
  }, [resultVisible]);

  useEffect(() => {
    if (
      !open
      || feedbackId == null
      || resultStatus == null
      || !feedbackPublicationShouldRefresh(
        resultStatus,
        publicationRefreshCountRef.current,
      )
    ) {
      return;
    }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | null = null;

    const schedule = () => {
      if (
        controller.signal.aborted
        || document.visibilityState === 'hidden'
        || !feedbackPublicationShouldRefresh(
          resultStatus,
          publicationRefreshCountRef.current,
        )
      ) {
        return;
      }
      timer = setTimeout(() => {
        timer = null;
        if (document.visibilityState === 'hidden') return;
        publicationRefreshCountRef.current += 1;
        void apiFetch('/api/me/feedback/status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback_id: feedbackId }),
          signal: controller.signal,
          cache: 'no-store',
        })
          .then(async (response) => {
            if (controller.signal.aborted) return null;
            if (!response.ok) {
              const disposition = applyFeedbackStatusLookup(
                response.status,
                feedbackId,
                null,
              );
              if (disposition !== 'gone') return null;
              setRecentFeedbackIdState(null);
              setFeedbackId(null);
              setResult(null);
              setResultOrigin('status');
              setResultMessage(t`The most recent feedback status is no longer available.`);
              return null;
            }
            return (await response.json()) as FeedbackStatusResponse;
          })
          .then((response) => {
            if (response == null || controller.signal.aborted) return;
            if (
              applyFeedbackStatusLookup(200, feedbackId, response.id)
              !== 'success'
            ) {
              setRecentFeedbackIdState(null);
              setFeedbackId(null);
              setResult(null);
              setResultOrigin('status');
              setResultMessage(t`The most recent feedback status is no longer available.`);
              return;
            }
            setResult(
              normalizeFeedbackPublicationResult(response.publication),
            );
          })
          .catch(() => undefined)
          .finally(schedule);
      }, PUBLICATION_REFRESH_DELAY_MS);
    };
    const resumeWhenVisible = () => {
      if (document.visibilityState === 'visible' && timer == null) schedule();
    };

    document.addEventListener('visibilitychange', resumeWhenVisible);
    schedule();
    return () => {
      controller.abort();
      if (timer != null) clearTimeout(timer);
      document.removeEventListener('visibilitychange', resumeWhenVisible);
    };
  }, [feedbackId, open, resultStatus, t]);

  const captureContext = (): Record<string, string | number> => ({
    page: location.pathname,
    app_version: WEB_VERSION,
    user_agent: navigator.userAgent,
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    locale,
  });

  const addFiles = (incoming: FileList | File[]) => {
    const next = [...images];
    let err: string | null = null;
    for (const file of Array.from(incoming)) {
      if (next.length >= MAX_IMAGES) {
        err = t`You can attach up to 3 images.`;
        break;
      }
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        err = t`Only PNG, JPG, or WebP images are supported.`;
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        err = t`Each image must be under 5 MB.`;
        continue;
      }
      next.push(file);
    }
    setImages(next);
    setImageError(err);
  };

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
    setImageError(null);
  };

  // Paste-from-clipboard: grab any image files pasted into the message box.
  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const pasted: File[] = [];
    for (const item of Array.from(items)) {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) pasted.push(file);
      }
    }
    if (pasted.length) {
      e.preventDefault();
      addFiles(pasted);
    }
  };

  const checkRecentFeedbackStatus = async () => {
    const expectedId = getRecentFeedbackId();
    if (expectedId == null) {
      setRecentFeedbackIdState(null);
      return;
    }
    const refreshingResult = resultVisible;
    abortStatusCheck();
    setFeedbackId(null);
    publicationRefreshCountRef.current = 0;
    const controller = new AbortController();
    statusCheckControllerRef.current = controller;
    const generation = statusCheckGenerationRef.current;
    setStatusChecking(true);
    setStatusCheckError(null);
    try {
      const response = await apiFetch('/api/me/feedback/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback_id: expectedId }),
        signal: controller.signal,
        cache: 'no-store',
      });
      if (controller.signal.aborted || generation !== statusCheckGenerationRef.current) return;

      let payload: FeedbackStatusResponse | null = null;
      if (response.ok) {
        const parsed: unknown = await response.json();
        if (
          parsed == null
          || typeof parsed !== 'object'
          || Array.isArray(parsed)
          || !('publication' in parsed)
        ) {
          throw new Error('invalid feedback status response');
        }
        payload = parsed as FeedbackStatusResponse;
      }
      if (controller.signal.aborted || generation !== statusCheckGenerationRef.current) return;

      const disposition = applyFeedbackStatusLookup(
        response.status,
        expectedId,
        payload?.id,
      );
      if (disposition === 'gone') {
        setRecentFeedbackIdState(null);
        setResult(null);
        setResultOrigin('status');
        setResultMessage(t`The most recent feedback status is no longer available.`);
        if (refreshingResult) {
          requestAnimationFrame(() => resultHeadingRef.current?.focus());
        }
        return;
      }
      if (disposition !== 'success' || payload == null) {
        setStatusCheckError(t`Couldn't check feedback status. Try again.`);
        return;
      }

      const nextResult = normalizeFeedbackPublicationResult(payload.publication);
      setResult(nextResult);
      setResultOrigin('status');
      setResultMessage(null);
      setStatusCheckError(null);
      if (refreshingResult) {
        requestAnimationFrame(() => {
          if (feedbackPublicationCanCheck(nextResult.status)) {
            resultRefreshButtonRef.current?.focus();
          } else {
            resultHeadingRef.current?.focus();
          }
        });
      }
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return;
      if (generation === statusCheckGenerationRef.current) {
        setStatusCheckError(t`Couldn't check feedback status. Try again.`);
      }
    } finally {
      if (generation === statusCheckGenerationRef.current) {
        statusCheckControllerRef.current = null;
        setStatusChecking(false);
      }
    }
  };

  const submit = async () => {
    if (submittingRef.current || transportUnknown) return;
    const trimmed = message.trim();
    if (!trimmed) return;
    abortPublicationReadiness();
    abortStatusCheck();
    submittingRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const imagePayload = images.length ? await Promise.all(images.map(fileToDataUrl)) : undefined;
      const body: FeedbackRequest = {
        kind,
        message: trimmed.slice(0, MESSAGE_MAX),
        context: captureContext(),
        locale,
        images: imagePayload,
        ...feedbackPublicationConsent(publishExternally),
      };
      const res = await apiFetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.status === 429) {
        setError(t`You've sent several reports recently — please wait a few minutes before sending more.`);
        return;
      }
      if (res.status >= 500) {
        setTransportUnknown(true);
        setError(t`Praxys could not confirm whether your feedback was received. It may already have been saved. Do not submit it again yet; reconnect and check its status.`);
        return;
      }
      if (!res.ok) {
        setError(t`Couldn't send your feedback. Please try again.`);
        return;
      }
      const response = (await res.json()) as FeedbackResponse;
      const acknowledgedId = parseRecentFeedbackId(response.id);
      if (acknowledgedId == null) {
        setTransportUnknown(true);
        setError(t`Praxys could not confirm whether your feedback was received. It may already have been saved. Do not submit it again yet; reconnect and check its status.`);
        return;
      }
      const acknowledgedResult = normalizeFeedbackPublicationResult(
        response.publication,
      );
      const storedId = setRecentFeedbackId(acknowledgedId)
        ? getRecentFeedbackId()
        : null;
      setRecentFeedbackIdState(storedId);
      publicationRefreshCountRef.current = 0;
      setFeedbackId(acknowledgedId);
      setResultOrigin('submitted');
      setResultMessage(null);
      setStatusCheckError(null);
      setResult(acknowledgedResult);
    } catch {
      setTransportUnknown(true);
      setError(t`Praxys could not confirm whether your feedback was received. It may already have been saved. Do not submit it again yet; reconnect and check its status.`);
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] overflow-y-auto"
        closeLabel={t`Close`}
      >
        <DialogHeader>
          <DialogTitle>
            <Trans>Send feedback</Trans>
          </DialogTitle>
          <DialogDescription>
            <Trans>Found a bug or have an idea? Tell us — reports are reviewed and triaged automatically.</Trans>
          </DialogDescription>
        </DialogHeader>

        {resultVisible ? (
          <div
            className="flex flex-col items-center gap-3 py-6 text-center"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            {result ? (
              <div className="flex size-10 items-center justify-center rounded-full bg-primary/15 text-primary">
                <Check className="size-5" aria-hidden="true" />
              </div>
            ) : null}
            <p ref={resultHeadingRef} tabIndex={-1} className="text-sm font-medium outline-none">
              {resultOrigin === 'submitted' ? <Trans>Feedback sent</Trans> : <Trans>Feedback status</Trans>}
            </p>
            <p className="max-w-[65ch] text-sm text-muted-foreground">
              {resultMessage ?? (result ? <PublicationResultCopy status={result.status} /> : null)}
            </p>
            {statusCheckError ? (
              <Alert variant="destructive">
                <AlertDescription>{statusCheckError}</AlertDescription>
              </Alert>
            ) : null}
            <div className="mt-2 flex flex-wrap justify-center gap-2">
              {result?.status === 'published' && result.issue_url ? (
                <a
                  href={result.issue_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className={cn(buttonVariants({ variant: 'outline' }), 'min-h-11')}
                >
                  <Trans>View public GitHub issue</Trans>
                </a>
              ) : null}
              {result && recentFeedbackId != null && feedbackPublicationCanCheck(result.status) ? (
                <Button
                  ref={resultRefreshButtonRef}
                  type="button"
                  variant="outline"
                  className="min-h-11"
                  disabled={statusChecking}
                  onClick={() => void checkRecentFeedbackStatus()}
                >
                  {statusChecking ? <Trans>Checking status…</Trans> : <Trans>Check status</Trans>}
                </Button>
              ) : null}
              <Button className="min-h-11" onClick={() => handleOpenChange(false)}>
                <Trans>Close</Trans>
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4" aria-busy={submitting}>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="feedback-kind">
                <Trans>Feedback Type</Trans>
              </Label>
              <Select
                items={kindItems}
                value={kind}
                disabled={submitting}
                onValueChange={(v) => v && setKind(v as FeedbackKind)}
              >
                <SelectTrigger id="feedback-kind" className="min-h-11 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {KIND_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {i18n._(opt.label)}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="feedback-message">
                <Trans>Details</Trans>
              </Label>
              <textarea
                id="feedback-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onPaste={onPaste}
                maxLength={MESSAGE_MAX}
                rows={5}
                placeholder={t`What happened, or what would you like to see?`}
                className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30"
                disabled={submitting}
              />
              <p className="text-right text-xs text-muted-foreground font-data">
                {message.length}/{MESSAGE_MAX}
              </p>
            </div>

            <p className="text-xs text-muted-foreground">
              <Trans>
                We attach basic diagnostics (page, app version, browser) for private handling and remove personal
                details from any text you choose to publish.
              </Trans>
            </p>

            <label className="flex min-h-11 items-start gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={publishExternally}
                onChange={(event) => setPublishExternally(event.target.checked)}
                disabled={submitting || publicationAvailable !== true}
                aria-describedby="feedback-publication-helper"
                className="mt-0.5 flex-none"
              />
              <span className="flex flex-col gap-1">
                <span className="block text-foreground">
                  <Trans>Allow Praxys to publish a scrubbed text summary of this feedback as a public GitHub issue</Trans>
                </span>
                <span id="feedback-publication-helper" className="block text-xs leading-relaxed">
                  <Trans>
                    Optional and off by default. If published to praxys-run/praxys, anyone can view the text summary.
                    GitHub is outside mainland China, and public issues may be retained long term. Screenshots are
                    never published. Leave this unchecked to send your feedback privately.
                  </Trans>
                </span>
              </span>
            </label>

            {publicationAvailable === false ? (
              <Alert>
                <AlertDescription>
                  <Trans>Public GitHub publishing is currently turned off. You can still send this feedback privately.</Trans>
                </AlertDescription>
              </Alert>
            ) : null}
            {publicationAvailable === null ? (
              <p className="text-xs text-muted-foreground" role="status">
                <Trans>Checking public publishing availability…</Trans>
              </p>
            ) : null}

            <div className="flex flex-col gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) addFiles(e.target.files);
                  e.target.value = '';
                }}
              />
              {previews.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {previews.map((src, i) => (
                    <div key={i} className="relative">
                      <img
                        src={src}
                        alt=""
                        className="h-16 w-16 rounded-md border border-border object-cover"
                      />
                      <Button
                        type="button"
                        aria-label={t`Remove image`}
                        onClick={() => removeImage(i)}
                        disabled={submitting}
                        variant="outline"
                        size="icon"
                        className="absolute -right-2 -top-2 size-11"
                      >
                        <X />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-h-11"
                onClick={() => fileInputRef.current?.click()}
                disabled={submitting || images.length >= MAX_IMAGES}
              >
                <ImagePlus data-icon="inline-start" />
                <Trans>Add screenshot</Trans>
              </Button>
              <p className="text-xs text-muted-foreground">
                <Trans>
                  Optional — PNG, JPG, or WebP, up to 3 images. Screenshots are kept private; we read them only to
                  help investigate your feedback.
                </Trans>
              </p>
              {imageError ? <p className="text-xs text-destructive" role="alert">{imageError}</p> : null}
            </div>

            {error ? (
              <Alert variant="destructive" role="alert" aria-live="assertive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {statusCheckError ? (
              <Alert variant="destructive" role="alert">
                <AlertDescription>{statusCheckError}</AlertDescription>
              </Alert>
            ) : null}

            <DialogFooter>
              {recentFeedbackId != null ? (
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11"
                  disabled={submitting || statusChecking}
                  onClick={() => void checkRecentFeedbackStatus()}
                >
                  {statusChecking ? <Trans>Checking status…</Trans> : <Trans>Check most recent feedback status</Trans>}
                </Button>
              ) : null}
              <Button
                variant="outline"
                className="min-h-11"
                onClick={() => handleOpenChange(false)}
                disabled={submitting}
              >
                <Trans>Cancel</Trans>
              </Button>
              <Button
                className="min-h-11"
                onClick={submit}
                disabled={submitting || transportUnknown || !message.trim()}
              >
                {submitting ? <Trans>Sending…</Trans> : <Trans>Send feedback</Trans>}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
