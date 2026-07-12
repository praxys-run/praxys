import type {
  NonDecisionProductEventName,
  ProductEventName,
  ProductEventRequest,
  ProductEventResponse,
  TodayFeedbackResponse,
} from '../types/api';
import { apiPost, TOKEN_KEY } from './api-client';
import { MINIAPP_BUILD_VERSION } from './version';

const ONCE_STORAGE_KEY = 'praxys.product-events.once'; // i18n-allow
const ONCE_RETENTION_MS = 14 * 24 * 60 * 60 * 1000;
const APP_VERSION = MINIAPP_BUILD_VERSION || 'develop'; // i18n-allow

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
    const bytes = new Uint8Array(wx.base64ToArrayBuffer(padded));
    let json = '';
    bytes.forEach((value) => { json += String.fromCharCode(value); });
    const parsed = JSON.parse(json) as { sub?: unknown };
    return typeof parsed.sub === 'string' ? parsed.sub : null;
  } catch {
    return null;
  }
}

/** Stable, local-only account scope for cadence and lifecycle sentinels. */
export function productEventStorageScope(): string {
  try {
    const token = wx.getStorageSync<string>(TOKEN_KEY) || '';
    if (!token) return 'signed-out';
    return fingerprint(jwtSubject(token) ?? token);
  } catch {
    return 'signed-out';
  }
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
      surface: 'miniapp',
      app_version: APP_VERSION,
      response,
    };
  } else {
    payload = {
      event_name: eventName,
      surface: 'miniapp',
      app_version: APP_VERSION,
      response: null,
    };
  }

  try {
    return await apiPost<ProductEventResponse>('/api/product-events', payload);
  } catch {
    // Product telemetry must never block the training experience.
    return null;
  }
}

/** Claim a short server-side window while the Decision Check renders. */
export async function claimTodayDecisionCheck(): Promise<ProductEventResponse | null> {
  try {
    return await apiPost<ProductEventResponse>(
      '/api/product-events/today-feedback-claim',
    );
  } catch {
    return null;
  }
}

/** Confirm prompt exposure, retrying lost responses within the claim lease. */
export async function confirmTodayDecisionCheck(): Promise<ProductEventResponse | null> {
  const delays = [0, 500, 1_500];
  for (const delay of delays) {
    if (delay > 0) {
      await new Promise<void>((resolve) => setTimeout(resolve, delay));
    }
    const result = await recordProductEvent('today_feedback_shown');
    if (result !== null) return result;
  }
  return null;
}

/** Emit a logical event once, pruning old sentinels from persistent storage. */
export function recordProductEventOnce(
  eventName: NonDecisionProductEventName,
  key: string,
): void {
  const now = Date.now();
  const eventKey = `${productEventStorageScope()}:${eventName}:${key}`;
  let sent: Record<string, number> = {};
  try {
    const stored = wx.getStorageSync<Record<string, number>>(ONCE_STORAGE_KEY);
    if (stored && typeof stored === 'object') sent = stored;
  } catch {
    sent = {};
  }

  if (sent[eventKey]) return;
  const cutoff = now - ONCE_RETENTION_MS;
  const pruned = Object.fromEntries(
    Object.entries(sent).filter(([, timestamp]) => timestamp >= cutoff),
  );
  pruned[eventKey] = now;
  try {
    wx.setStorageSync(ONCE_STORAGE_KEY, pruned);
  } catch {
    // The backend's short-window dedupe remains the final guard.
  }
  void recordProductEvent(eventName);
}