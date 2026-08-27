// Start the /api/auth/me fetch at module evaluation time — before React
// mounts or any useEffect runs. AuthProvider consumes this parsed result
// instead of starting a new fetch, shaving one React render cycle off the
// auth round-trip on every cold load.
//
// The response body is parsed eagerly so the promise is safe to consume
// multiple times (e.g. React StrictMode double-fires effects in dev).
import { KEYS, getCompatItem } from './storage-compat';
import { canStartPersonalDataRequests } from './china-processing';
import { getChinaClientHeaders } from './client-boundary';
import type { CurrentUserProfile } from '../types/api';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

const token = (() => {
  try {
    return getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
  } catch {
    return null;
  }
})();

export interface PrefetchedMe {
  status: number;
  data: CurrentUserProfile | null;
}

export const prefetchedMe: Promise<PrefetchedMe> | null = token &&
  canStartPersonalDataRequests()
  ? fetch(`${API_BASE}/api/auth/me`, {
      headers: {
        ...getChinaClientHeaders(),
        Authorization: `Bearer ${token}`,
      },
    })
      .then(async (r): Promise<PrefetchedMe> => ({
        status: r.status,
        data: r.ok ? await r.json() : null,
      }))
      .catch((): PrefetchedMe => ({ status: 0, data: null }))
  : null;
