export class ApiTimeoutError extends Error {
  constructor() {
    super('The eligibility check took too long. Please retry.');
    this.name = 'ApiTimeoutError';
  }
}

export function shouldRetryApiRequest(
  failureCount: number,
  error: Error,
): boolean {
  return !(error instanceof ApiTimeoutError) && failureCount < 2;
}

export async function fetchWithTimeout<T>(
  request: (signal?: AbortSignal) => Promise<T>,
  signal?: AbortSignal,
  timeoutMs?: number,
): Promise<T> {
  const controller = timeoutMs ? new AbortController() : null;
  let timedOut = false;
  const timeout = timeoutMs
    ? window.setTimeout(() => {
      timedOut = true;
      controller?.abort();
    }, timeoutMs)
    : null;
  const abort = () => controller?.abort();
  signal?.addEventListener('abort', abort, { once: true });
  try {
    return await request(controller?.signal ?? signal);
  } catch (error) {
    if (timedOut) throw new ApiTimeoutError();
    throw error;
  } finally {
    if (timeout !== null) window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
