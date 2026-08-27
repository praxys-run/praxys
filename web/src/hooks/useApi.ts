import { useQuery } from '@tanstack/react-query';
import { KEYS, getCompatItem, removeCompatItem } from '../lib/storage-compat';
import { initialDashboardUrl } from '../lib/dashboard-prefetch';
import { tokenCacheScope } from '../lib/auth-cache-scope';
import {
  fetchWithTimeout,
  shouldRetryApiRequest,
} from '../lib/request-timeout';
import {
  ApiResponseError,
  apiResponseError,
  extractApiError,
} from '../lib/api-error';
import { canStartPersonalDataRequests } from '../lib/china-processing';
import {
  getChinaClientHeaders,
  TERMS_REQUIRED_EVENT,
} from '../lib/client-boundary';

const API_BASE = import.meta.env.VITE_API_URL || '';

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  stale: boolean;
  error: string | null;
  errorCode: string | null;
  errorStatus: number | null;
  refetch: () => Promise<void>;
}

interface UseApiOptions {
  /** Poll interval in ms (e.g. 3000 for sync status). 0 = disabled. */
  refetchInterval?: number;
  /** When false, the query is not run (e.g. admin-only endpoints for non-admins). */
  enabled?: boolean;
  /** Override the app-wide mount policy for freshness-critical queries. */
  refetchOnMount?: boolean | 'always';
  /** Override the app-wide focus policy for freshness-critical queries. */
  refetchOnWindowFocus?: boolean | 'always';
  /** Bound one request when an unfinished result would block the user. */
  timeoutMs?: number;
}

function getAuthHeaders(): HeadersInit {
  if (!canStartPersonalDataRequests()) return {};
  const headers: Record<string, string> = getChinaClientHeaders();
  const token = getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function getAuthCacheScope(): string {
  return tokenCacheScope(
    canStartPersonalDataRequests()
      ? getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy)
      : null,
  );
}

async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;
  const headers = new Headers(init.headers);
  new Headers(getAuthHeaders()).forEach((value, key) => {
    if (!headers.has(key)) headers.set(key, value);
  });
  const res = await fetch(fullUrl, { ...init, headers });
  if (res.status === 401) {
    removeCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
    window.location.href = '/login';
    // Return a never-resolving promise to prevent callers from updating stale UI
    // while the hard redirect clears the in-memory query cache.
    return new Promise<Response>(() => {});
  }
  if (res.status === 428) {
    const body = await res.clone().json().catch(() => null);
    if (body?.detail?.code === 'TERMS_ACCEPTANCE_REQUIRED') {
      window.dispatchEvent(new Event(TERMS_REQUIRED_EVENT));
    }
  }
  const requestPath = new URL(fullUrl, window.location.origin).pathname;
  if (res.status === 403 && requestPath.startsWith('/api/admin/')) {
    removeCompatItem(KEYS.authAdmin.new, KEYS.authAdmin.legacy);
    window.location.href = '/today';
    // A full reload refreshes /api/auth/me and drops all cached admin data.
    return new Promise<Response>(() => {});
  }
  return res;
}

const prefetchedResponses = new Map<string, Promise<Response | null>>();

function startInitialDashboardPrefetch(): void {
  if (typeof window === 'undefined') return;
  const token = getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
  const url = initialDashboardUrl(
    window.location.pathname,
    Boolean(token),
    canStartPersonalDataRequests(),
  );
  if (!url) return;

  // Auth verification and dashboard data are independent authenticated reads.
  // Start both during module evaluation so the page does not pay one
  // cross-border round trip before beginning the next.
  prefetchedResponses.set(url, apiFetch(url).catch(() => null));
}

async function apiFetcher<T>(
  url: string,
  signal?: AbortSignal,
  timeoutMs?: number,
): Promise<T> {
  const prefetched = prefetchedResponses.get(url);
  if (prefetched) prefetchedResponses.delete(url);
  const prefetchedResponse = prefetched ? await prefetched : null;
  if (prefetchedResponse) {
    if (!prefetchedResponse.ok) {
      throw await apiResponseError(
        prefetchedResponse,
        `HTTP ${prefetchedResponse.status}`,
      );
    }
    return prefetchedResponse.json();
  }

  return fetchWithTimeout(
    async (requestSignal) => {
      const res = await apiFetch(url, {
        signal: requestSignal,
      });
      if (!res.ok) {
        throw await apiResponseError(res, `HTTP ${res.status}`);
      }
      return res.json();
    },
    signal,
    timeoutMs,
  );
}

startInitialDashboardPrefetch();

/**
 * Pull a human-readable error message out of a non-2xx fetch Response.
 *
 * Tolerates three shapes we actually see in practice:
 *  - FastAPI handler errors: `{detail: "..."}` or `{message: "..."}`
 *  - FastAPI 422 validation: `{detail: [{msg, loc, ...}, ...]}` — the array
 *    shape used to render as "[object Object]" when passed to React.
 *  - Non-JSON bodies (proxy HTML, empty) — falls back to `fallback`.
 */
async function extractErrorMessage(res: Response, fallback: string): Promise<string> {
  return (await extractApiError(res, fallback)).message;
}

export {
  API_BASE,
  getAuthHeaders,
  getAuthCacheScope,
  apiFetch,
  apiFetcher,
  extractErrorMessage,
};

export function useApi<T>(url: string, options?: UseApiOptions): UseApiResult<T> {
  const { data, isLoading, isStale, error, refetch } = useQuery<T, Error>({
    queryKey: [url, getAuthCacheScope()],
    queryFn: ({ signal }) => apiFetcher<T>(url, signal, options?.timeoutMs),
    ...(options?.refetchInterval !== undefined
      ? { refetchInterval: options.refetchInterval }
      : {}),
    ...(options?.enabled !== undefined ? { enabled: options.enabled } : {}),
    ...(options?.refetchOnMount !== undefined
      ? { refetchOnMount: options.refetchOnMount }
      : {}),
    ...(options?.refetchOnWindowFocus !== undefined
      ? { refetchOnWindowFocus: options.refetchOnWindowFocus }
      : {}),
    ...(options?.timeoutMs ? { retry: shouldRetryApiRequest } : {}),
  });
  const responseError = error instanceof ApiResponseError ? error : null;

  return {
    data: data ?? null,
    loading: isLoading,
    stale: isStale,
    error: error?.message ?? null,
    errorCode: responseError?.code ?? null,
    errorStatus: responseError?.status ?? null,
    refetch: async () => { await refetch(); },
  };
}
