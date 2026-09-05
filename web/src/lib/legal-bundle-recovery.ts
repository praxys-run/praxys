export const TERMS_BUNDLE_MISMATCH_CODE = 'TERMS_BUNDLE_MISMATCH';
export const LEGAL_BUNDLE_RECOVERY_MARKER_KEY = 'praxys-legal-bundle-recovery';
// A fixed value proves only that this browser tab attempted recovery. It
// deliberately contains no account, policy-version, route, or server data.
export const LEGAL_BUNDLE_RECOVERY_MARKER_VALUE = 'attempted-v1';
export const LEGAL_BUNDLE_UPDATE_TIMEOUT_MS = 8_000;

export type TermsAcceptanceStatus =
  | 'ready'
  | 'submitting'
  | 'accepted'
  | 'updating'
  | 'reloading'
  | 'submit_error'
  | 'fallback';

export type LegalBundleRecoveryFallbackReason =
  | 'already-attempted'
  | 'offline'
  | 'marker-unavailable'
  | 'no-registration'
  | 'registration-failed'
  | 'cross-origin-registration'
  | 'update-failed'
  | 'timeout';

export type LegalBundleRecoveryResult =
  | { action: 'reload' }
  | { action: 'fallback'; reason: LegalBundleRecoveryFallbackReason };

export type TermsBundleMismatchRecoveryResult =
  | { matched: false }
  | { matched: true; recovery: LegalBundleRecoveryResult };

interface RecoveryStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface RecoveryRegistration {
  readonly scope: string;
  update(): Promise<unknown>;
}

interface RecoveryServiceWorker {
  getRegistration(): Promise<RecoveryRegistration | undefined | null>;
}

export interface LegalBundleRecoveryEnvironment {
  online: boolean;
  origin: string;
  storage: RecoveryStorage | null;
  serviceWorker: RecoveryServiceWorker | null;
  timeoutMs?: number;
}

interface TermsBundleMismatchRecoveryOptions {
  environment?: LegalBundleRecoveryEnvironment;
  onMismatch?: () => void;
}

type BoundedResult<T> =
  | { outcome: 'completed'; value: T }
  | { outcome: 'failed' }
  | { outcome: 'timeout' };

async function settleWithin<T>(
  operation: () => Promise<T>,
  timeoutMs: number,
): Promise<BoundedResult<T>> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<BoundedResult<T>>((resolve) => {
    timeoutId = globalThis.setTimeout(
      () => resolve({ outcome: 'timeout' }),
      timeoutMs,
    );
  });
  const pending = Promise.resolve()
    .then(operation)
    .then(
      (value): BoundedResult<T> => ({ outcome: 'completed', value }),
      (): BoundedResult<T> => ({ outcome: 'failed' }),
    );

  try {
    return await Promise.race([pending, timeout]);
  } finally {
    if (timeoutId !== undefined) globalThis.clearTimeout(timeoutId);
  }
}

function browserEnvironment(): LegalBundleRecoveryEnvironment {
  let storage: Storage | null = null;
  try {
    storage = window.sessionStorage;
  } catch {
    // Storage can be denied by browser privacy settings. Recovery must then
    // remain fail-closed because it cannot prove that the reload is bounded.
  }

  return {
    online: navigator.onLine,
    origin: window.location.origin,
    storage,
    serviceWorker: 'serviceWorker' in navigator
      ? navigator.serviceWorker
      : null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

export async function prepareLegalBundleRecovery(
  environment: LegalBundleRecoveryEnvironment = browserEnvironment(),
): Promise<LegalBundleRecoveryResult> {
  if (!environment.online) {
    return { action: 'fallback', reason: 'offline' };
  }

  const storage = environment.storage;
  if (!storage) {
    return { action: 'fallback', reason: 'marker-unavailable' };
  }

  try {
    if (storage.getItem(LEGAL_BUNDLE_RECOVERY_MARKER_KEY) !== null) {
      return { action: 'fallback', reason: 'already-attempted' };
    }
    storage.setItem(
      LEGAL_BUNDLE_RECOVERY_MARKER_KEY,
      LEGAL_BUNDLE_RECOVERY_MARKER_VALUE,
    );
    if (
      storage.getItem(LEGAL_BUNDLE_RECOVERY_MARKER_KEY)
      !== LEGAL_BUNDLE_RECOVERY_MARKER_VALUE
    ) {
      return { action: 'fallback', reason: 'marker-unavailable' };
    }
  } catch {
    return { action: 'fallback', reason: 'marker-unavailable' };
  }

  if (!environment.serviceWorker) {
    return { action: 'fallback', reason: 'no-registration' };
  }

  const timeoutMs = environment.timeoutMs ?? LEGAL_BUNDLE_UPDATE_TIMEOUT_MS;
  const registrationResult = await settleWithin(
    () => environment.serviceWorker!.getRegistration(),
    timeoutMs,
  );
  if (registrationResult.outcome === 'timeout') {
    return { action: 'fallback', reason: 'timeout' };
  }
  if (registrationResult.outcome === 'failed') {
    return { action: 'fallback', reason: 'registration-failed' };
  }

  const registration = registrationResult.value;
  if (!registration) {
    return { action: 'fallback', reason: 'no-registration' };
  }

  try {
    if (new URL(registration.scope).origin !== environment.origin) {
      return { action: 'fallback', reason: 'cross-origin-registration' };
    }
  } catch {
    return { action: 'fallback', reason: 'cross-origin-registration' };
  }

  const updateResult = await settleWithin(
    () => registration.update(),
    timeoutMs,
  );
  if (updateResult.outcome === 'timeout') {
    return { action: 'fallback', reason: 'timeout' };
  }
  if (updateResult.outcome === 'failed') {
    return { action: 'fallback', reason: 'update-failed' };
  }
  return { action: 'reload' };
}

export async function recoverTermsBundleMismatchResponse(
  response: Response,
  options: TermsBundleMismatchRecoveryOptions = {},
): Promise<TermsBundleMismatchRecoveryResult> {
  if (response.status !== 409) return { matched: false };

  let payload: unknown;
  try {
    payload = await response.clone().json();
  } catch {
    return { matched: false };
  }
  if (!isRecord(payload) || !isRecord(payload.detail)) {
    return { matched: false };
  }
  if (payload.detail.code !== TERMS_BUNDLE_MISMATCH_CODE) {
    return { matched: false };
  }

  options.onMismatch?.();
  return {
    matched: true,
    recovery: await prepareLegalBundleRecovery(options.environment),
  };
}

export function clearLegalBundleRecoveryMarker(
  storage?: RecoveryStorage | null,
): void {
  let target = storage;
  if (target === undefined) {
    try {
      target = window.sessionStorage;
    } catch {
      target = null;
    }
  }
  try {
    target?.removeItem(LEGAL_BUNDLE_RECOVERY_MARKER_KEY);
  } catch {
    // A completed server-side acceptance remains valid even when local
    // privacy controls prevent clearing this best-effort recovery marker.
  }
}
