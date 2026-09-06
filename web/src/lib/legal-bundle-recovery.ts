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
  | 'no-replacement'
  | 'activation-failed'
  | 'activation-timeout'
  | 'control-timeout'
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

interface RecoveryWorker {
  readonly scriptURL: string;
  readonly state: string;
  addEventListener(type: 'statechange', listener: EventListener): void;
  removeEventListener(type: 'statechange', listener: EventListener): void;
}

interface RecoveryRegistration {
  readonly scope: string;
  readonly active: RecoveryWorker | null;
  readonly installing: RecoveryWorker | null;
  readonly waiting: RecoveryWorker | null;
  update(): Promise<unknown>;
  addEventListener(type: 'updatefound', listener: EventListener): void;
  removeEventListener(type: 'updatefound', listener: EventListener): void;
}

interface RecoveryServiceWorker {
  readonly controller: RecoveryWorker | null;
  getRegistration(): Promise<RecoveryRegistration | undefined | null>;
  addEventListener(type: 'controllerchange', listener: EventListener): void;
  removeEventListener(type: 'controllerchange', listener: EventListener): void;
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

function workerMatchesOrigin(
  worker: RecoveryWorker,
  origin: string,
): boolean {
  try {
    return new URL(worker.scriptURL).origin === origin;
  } catch {
    return false;
  }
}

function controllerOwnsReplacement(
  controller: RecoveryWorker | null,
  replacement: RecoveryWorker,
  previousController: RecoveryWorker | null,
): boolean {
  if (controller === replacement) return true;
  return (
    controller !== null
    && controller !== previousController
    && controller.state === 'activated'
    && replacement.state === 'activated'
    && controller.scriptURL === replacement.scriptURL
  );
}

async function updateAndAwaitReplacement(
  registration: RecoveryRegistration,
  serviceWorker: RecoveryServiceWorker,
  origin: string,
  timeoutMs: number,
): Promise<LegalBundleRecoveryResult> {
  const previousActive = registration.active;
  const previousController = serviceWorker.controller;
  let replacement: RecoveryWorker | null = null;
  let replacementStateListener: EventListener | null = null;
  let completed = false;
  let resolveHandoff: (
    value: 'ready' | 'activation-failed',
  ) => void = () => {};
  const handoff = new Promise<'ready' | 'activation-failed'>((resolve) => {
    resolveHandoff = resolve;
  });

  const complete = (value: 'ready' | 'activation-failed') => {
    if (completed) return;
    completed = true;
    resolveHandoff(value);
  };
  const checkHandoff = () => {
    if (!replacement) return;
    if (replacement.state === 'redundant') {
      complete('activation-failed');
      return;
    }
    if (
      replacement.state === 'activated'
      && controllerOwnsReplacement(
        serviceWorker.controller,
        replacement,
        previousController,
      )
    ) {
      complete('ready');
    }
  };
  const observeReplacement = (worker: RecoveryWorker | null) => {
    if (
      !worker
      || worker === previousActive
      || worker === previousController
      || !workerMatchesOrigin(worker, origin)
    ) {
      return;
    }
    if (replacement === worker) {
      checkHandoff();
      return;
    }
    if (replacement && replacementStateListener) {
      replacement.removeEventListener(
        'statechange',
        replacementStateListener,
      );
    }
    replacement = worker;
    replacementStateListener = () => checkHandoff();
    replacement.addEventListener('statechange', replacementStateListener);
    checkHandoff();
  };
  const inspectRegistration = () => {
    observeReplacement(registration.installing);
    observeReplacement(registration.waiting);
    observeReplacement(registration.active);
  };
  const updateFoundListener: EventListener = () => inspectRegistration();
  const controllerChangeListener: EventListener = () => {
    inspectRegistration();
    checkHandoff();
  };
  const cleanup = () => {
    registration.removeEventListener('updatefound', updateFoundListener);
    serviceWorker.removeEventListener(
      'controllerchange',
      controllerChangeListener,
    );
    if (replacement && replacementStateListener) {
      replacement.removeEventListener(
        'statechange',
        replacementStateListener,
      );
    }
  };

  registration.addEventListener('updatefound', updateFoundListener);
  serviceWorker.addEventListener(
    'controllerchange',
    controllerChangeListener,
  );
  inspectRegistration();
  const deadline = Date.now() + timeoutMs;
  const updateResult = await settleWithin(
    () => registration.update(),
    timeoutMs,
  );
  if (updateResult.outcome === 'timeout') {
    cleanup();
    return { action: 'fallback', reason: 'timeout' };
  }
  if (updateResult.outcome === 'failed') {
    cleanup();
    return { action: 'fallback', reason: 'update-failed' };
  }

  inspectRegistration();
  checkHandoff();
  const remainingMs = Math.max(1, deadline - Date.now());
  const handoffResult = await settleWithin(() => handoff, remainingMs);
  cleanup();
  if (handoffResult.outcome === 'completed') {
    return handoffResult.value === 'ready'
      ? { action: 'reload' }
      : { action: 'fallback', reason: 'activation-failed' };
  }
  const timedOutReplacement = replacement as RecoveryWorker | null;
  if (!timedOutReplacement) {
    return { action: 'fallback', reason: 'no-replacement' };
  }
  return timedOutReplacement.state === 'activated'
    ? { action: 'fallback', reason: 'control-timeout' }
    : { action: 'fallback', reason: 'activation-timeout' };
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

  return updateAndAwaitReplacement(
    registration,
    environment.serviceWorker,
    environment.origin,
    timeoutMs,
  );
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
