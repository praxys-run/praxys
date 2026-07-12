import { API_BASE, getAuthHeaders } from '@/hooks/useApi';
import type {
  NonDecisionProductEventName,
  ProductEventName,
  ProductEventRequest,
  ProductEventResponse,
  TodayFeedbackResponse,
} from '@/types/api';
import { WEB_VERSION } from '@/lib/version';
import { KEYS, getCompatItem } from '@/lib/storage-compat';

const sentThisSession = new Set<string>();
const decisionCheckClaims = new Map<
  string,
  Promise<ProductEventResponse | null>
>();

function fingerprint(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function jwtSubject(token: string): string | null {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    const parsed = JSON.parse(window.atob(padded)) as { sub?: unknown };
    return typeof parsed.sub === 'string' ? parsed.sub : null;
  } catch {
    return null;
  }
}

/** Stable, local-only account scope for cadence and lifecycle sentinels. */
export function productEventStorageScope(): string {
  const token = getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
  if (!token) return 'signed-out';
  return fingerprint(jwtSubject(token) ?? token);
}

export function recordProductEvent(
  eventName: NonDecisionProductEventName,
): Promise<ProductEventResponse | null>;
export function recordProductEvent(
  eventName: 'today_feedback_submitted',
  response: TodayFeedbackResponse,
): Promise<ProductEventResponse | null>;
/** Emit a best-effort authenticated product event through the backend. */
export async function recordProductEvent(
  eventName: ProductEventName,
  response?: TodayFeedbackResponse,
): Promise<ProductEventResponse | null> {
  let payload: ProductEventRequest;
  if (eventName === 'today_feedback_submitted') {
    if (!response) return null;
    payload = {
      event_name: eventName,
      surface: 'web',
      app_version: WEB_VERSION,
      response,
    };
  } else {
    payload = {
      event_name: eventName,
      surface: 'web',
      app_version: WEB_VERSION,
      response: null,
    };
  }

  try {
    const result = await fetch(`${API_BASE}/api/product-events`, {
      method: 'POST',
      headers: {
        ...(getAuthHeaders() as Record<string, string>),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!result.ok) return null;
    return await result.json() as ProductEventResponse;
  } catch {
    // Product telemetry must never block the training experience.
    return null;
  }
}

/** Claim the account-wide Decision Check cadence before rendering the prompt. */
export function claimTodayDecisionCheck(): Promise<ProductEventResponse | null> {
  const scope = productEventStorageScope();
  const existing = decisionCheckClaims.get(scope);
  if (existing) return existing;

  const promise = (async () => {
    try {
      const result = await fetch(
        `${API_BASE}/api/product-events/today-feedback-claim`,
        { method: 'POST', headers: getAuthHeaders() as Record<string, string> },
      );
      if (!result.ok) return null;
      return await result.json() as ProductEventResponse;
    } catch {
      return null;
    }
  })();
  decisionCheckClaims.set(scope, promise);
  void promise.finally(() => {
    if (decisionCheckClaims.get(scope) === promise) {
      decisionCheckClaims.delete(scope);
    }
  });
  return promise;
}

/** Confirm prompt exposure, retrying lost responses within the claim lease. */
export async function confirmTodayDecisionCheck(): Promise<ProductEventResponse | null> {
  const delays = [0, 500, 1_500];
  for (const delay of delays) {
    if (delay > 0) {
      await new Promise<void>((resolve) => window.setTimeout(resolve, delay));
    }
    const result = await recordProductEvent('today_feedback_shown');
    if (result !== null) return result;
  }
  return null;
}

/** Emit an event once per browser-tab session for the supplied logical key. */
export function recordProductEventOnce(
  eventName: NonDecisionProductEventName,
  key: string,
): void {
  const storageKey = `praxys:product-event:${productEventStorageScope()}:${eventName}:${key}`;
  if (sentThisSession.has(storageKey)) return;

  try {
    if (window.sessionStorage.getItem(storageKey)) return;
    window.sessionStorage.setItem(storageKey, '1');
  } catch {
    // The in-memory guard still prevents same-render duplicates.
  }

  sentThisSession.add(storageKey);
  void recordProductEvent(eventName);
}