/** Check for a new app bundle when a suspended mobile tab returns. */
export const SERVICE_WORKER_UPDATE_INTERVAL_MS = 60_000;

interface UpdateEnvironment {
  document: Pick<Document, 'visibilityState' | 'addEventListener' | 'removeEventListener'>;
  window: Pick<Window, 'addEventListener' | 'removeEventListener'>;
  navigator: Pick<Navigator, 'onLine'>;
  now: () => number;
}

/** Preserve the current app on update failure and retry on a later resume. */
export function watchServiceWorkerUpdates(
  registration: Pick<ServiceWorkerRegistration, 'update'>,
  environment: UpdateEnvironment = {
    document,
    window,
    navigator,
    now: () => performance.now(),
  },
): () => void {
  let lastAttempt = -Infinity;
  let pending = false;
  let stopped = false;
  const check = () => {
    if (stopped || pending || !environment.navigator.onLine
      || environment.document.visibilityState !== 'visible') return;
    const now = environment.now();
    if (now - lastAttempt < SERVICE_WORKER_UPDATE_INTERVAL_MS) return;
    lastAttempt = now;
    pending = true;
    // Registration's existing autoUpdate handler owns activation and reload.
    // A failed/offline check must not clear the app cache or the user's session.
    void Promise.resolve().then(() => registration.update()).catch(() => undefined)
      .finally(() => { pending = false; });
  };
  environment.document.addEventListener('visibilitychange', check);
  environment.window.addEventListener('pageshow', check);
  environment.window.addEventListener('online', check);
  return () => {
    stopped = true;
    environment.document.removeEventListener('visibilitychange', check);
    environment.window.removeEventListener('pageshow', check);
    environment.window.removeEventListener('online', check);
  };
}
