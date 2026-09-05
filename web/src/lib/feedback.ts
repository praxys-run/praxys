import type {
  FeedbackPublicationResult,
  FeedbackPublicationStatus,
} from '@/types/api';

export const FEEDBACK_PUBLICATION_CONSENT_VERSION =
  "feedback-publication-v2-public-github" as const;
export const FEEDBACK_PUBLICATION_REFRESH_LIMIT = 6;
export const RECENT_FEEDBACK_ID_KEY = 'praxys-most-recent-feedback-id';

const PUBLIC_FEEDBACK_ISSUE =
  /^https:\/\/github\.com\/praxys-run\/praxys\/issues\/[1-9]\d*$/;
const PUBLICATION_STATUSES: readonly FeedbackPublicationStatus[] = [
  'private',
  'queued',
  'published',
  'manual_required',
  'unknown',
  'unavailable',
];

export type FeedbackPublicationConsent =
  | {
      external_publication_consent: true;
      external_publication_consent_version:
        typeof FEEDBACK_PUBLICATION_CONSENT_VERSION;
    }
  | {
      external_publication_consent: false;
    };

export type FeedbackStatusLookupDisposition =
  | 'success'
  | 'gone'
  | 'unauthenticated'
  | 'retry';

/** Accept only the canonical decimal form of a positive JS-safe integer. */
export function parseRecentFeedbackId(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  }
  if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && String(parsed) === value
    ? parsed
    : null;
}

export function getRecentFeedbackId(): number | null {
  try {
    const value = localStorage.getItem(RECENT_FEEDBACK_ID_KEY);
    const parsed = parseRecentFeedbackId(value);
    if (value !== null && parsed === null) {
      localStorage.removeItem(RECENT_FEEDBACK_ID_KEY);
    }
    return parsed;
  } catch {
    return null;
  }
}

export function setRecentFeedbackId(value: unknown): boolean {
  const parsed = parseRecentFeedbackId(value);
  if (parsed === null) return false;
  try {
    localStorage.setItem(RECENT_FEEDBACK_ID_KEY, String(parsed));
    return true;
  } catch {
    // Status recovery is best-effort; feedback submission remains successful.
    return false;
  }
}

export function removeRecentFeedbackId(): void {
  try {
    localStorage.removeItem(RECENT_FEEDBACK_ID_KEY);
  } catch {
    // Storage may be blocked or unavailable.
  }
}

export function feedbackPublicationCanCheck(
  status: FeedbackPublicationStatus,
): boolean {
  return status === 'queued' || status === 'unknown' || status === 'manual_required';
}

export function feedbackStatusLookupDisposition(
  httpStatus: number,
  expectedId: number,
  responseId: unknown,
): FeedbackStatusLookupDisposition {
  if (httpStatus === 401) return 'unauthenticated';
  if (httpStatus === 403 || httpStatus === 404) return 'gone';
  if (
    httpStatus >= 200
    && httpStatus < 300
    && parseRecentFeedbackId(responseId) === expectedId
  ) {
    return 'success';
  }
  if (httpStatus >= 200 && httpStatus < 300) return 'gone';
  return 'retry';
}

/** Apply the owner-status storage contract without clearing retryable state. */
export function applyFeedbackStatusLookup(
  httpStatus: number,
  expectedId: number,
  responseId: unknown,
): FeedbackStatusLookupDisposition {
  const disposition = feedbackStatusLookupDisposition(
    httpStatus,
    expectedId,
    responseId,
  );
  if (disposition === 'gone' || disposition === 'unauthenticated') {
    removeRecentFeedbackId();
  }
  return disposition;
}

/** Reject readiness results from closed, superseded, or aborted requests. */
export function feedbackReadinessRequestCanApply(
  requestGeneration: number,
  currentGeneration: number,
  formOpen: boolean,
  aborted: boolean,
): boolean {
  return (
    requestGeneration === currentGeneration
    && formOpen
    && !aborted
  );
}

export interface FeedbackAbortableRequest {
  abort(): void;
}

/** Own one readiness request and invalidate every older generation. */
export class FeedbackReadinessRequestFence {
  private generation = 0;
  private request: FeedbackAbortableRequest | null = null;

  begin(): number {
    this.cancel();
    return this.generation;
  }

  attach(
    generation: number,
    request: FeedbackAbortableRequest,
  ): boolean {
    if (generation !== this.generation) {
      request.abort();
      return false;
    }
    this.request?.abort();
    this.request = request;
    return true;
  }

  canApply(
    generation: number,
    formOpen: boolean,
    aborted = false,
  ): boolean {
    return feedbackReadinessRequestCanApply(
      generation,
      this.generation,
      formOpen,
      aborted,
    );
  }

  finish(
    generation: number,
    request?: FeedbackAbortableRequest,
  ): void {
    if (
      generation === this.generation
      && (request === undefined || this.request === request)
    ) {
      this.request = null;
    }
  }

  cancel(generation?: number): void {
    if (generation !== undefined && generation !== this.generation) return;
    this.generation += 1;
    this.request?.abort();
    this.request = null;
  }
}

/** Build the exact per-submission publication contract; false stays private. */
export function feedbackPublicationConsent(
  publishExternally: boolean,
): FeedbackPublicationConsent {
  if (!publishExternally) {
    return { external_publication_consent: false };
  }
  return {
    external_publication_consent: true,
    external_publication_consent_version:
      FEEDBACK_PUBLICATION_CONSENT_VERSION,
  };
}

export function normalizeFeedbackPublicationResult(
  value: Partial<FeedbackPublicationResult>,
): FeedbackPublicationResult {
  const status = PUBLICATION_STATUSES.includes(
    value.status as FeedbackPublicationStatus,
  )
    ? value.status as FeedbackPublicationStatus
    : 'unknown';
  if (status !== 'published') return { status, issue_url: null };
  if (!PUBLIC_FEEDBACK_ISSUE.test(value.issue_url ?? '')) {
    return { status: 'unknown', issue_url: null };
  }
  return { status, issue_url: value.issue_url ?? null };
}

export function feedbackPublicationShouldRefresh(
  status: FeedbackPublicationStatus,
  refreshCount: number,
): boolean {
  return (
    (status === 'queued' || status === 'unknown')
    && refreshCount < FEEDBACK_PUBLICATION_REFRESH_LIMIT
  );
}
