import { useState, useCallback, useEffect, createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { KEYS, getCompatItem, setCompatItem, removeCompatItem } from '../lib/storage-compat';
import { prefetchedMe } from '../lib/auth-prefetch';
import type { PrefetchedMe } from '../lib/auth-prefetch';
import { setAppInsightsUser, clearAppInsightsUser } from '../lib/appinsights';
import { recordProductEventOnce } from '@/lib/product-events';
import { resolveRestoredSession } from '@/lib/auth-session';
import { canStartPersonalDataRequests } from '@/lib/china-processing';
import {
  getChinaClientHeaders,
  TERMS_REQUIRED_EVENT,
} from '@/lib/client-boundary';
import {
  TERMS_CONTENT_DIGEST,
  TERMS_VERSION,
} from '@/lib/legal';
import { extractApiError } from '@/lib/api-error';
import { apiFetch } from '@/hooks/useApi';
import { removeRecentFeedbackId } from '@/lib/feedback';
import {
  clearLegalBundleRecoveryMarker,
  isTermsBundleMismatch,
  prepareLegalBundleRecovery,
  TERMS_BUNDLE_MISMATCH_CODE,
  type TermsAcceptanceStatus,
} from '@/lib/legal-bundle-recovery';
import type {
  CurrentUserProfile,
  TermsAcceptanceResponse,
} from '@/types/api';

interface AuthState {
  token: string | null;
  userId: string | null;
  email: string | null;
  isAdmin: boolean;
  isDemo: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  restoreStatus: 'restoring' | 'retryable' | 'idle';
  termsCurrent: boolean;
  termsAcceptanceStatus: TermsAcceptanceStatus;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  register: (email: string, password: string, invitationCode?: string, acceptedTerms?: boolean, honeypot?: string) => Promise<{ ok: boolean; error?: string; verificationRequired?: boolean }>;
  logout: () => void;
  acceptTerms: (onBundleMismatch?: () => void) => Promise<TermsAcceptanceStatus>;
}

// The API base URL may be empty (same origin via SWA linked backend)
// or set via import.meta.env.VITE_API_URL for development/non-SWA deployments.
const API_BASE = import.meta.env.VITE_API_URL || '';

const AuthContext = createContext<AuthContextType>({
  token: null,
  userId: null,
  email: null,
  isAdmin: false,
  isDemo: false,
  isAuthenticated: false,
  isLoading: true,
  restoreStatus: 'restoring',
  termsCurrent: false,
  termsAcceptanceStatus: 'ready',
  login: async () => ({ ok: false }),
  register: async () => ({ ok: false }),
  logout: () => {},
  acceptTerms: async () => 'submit_error',
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isDemo, setIsDemo] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [restoreStatus, setRestoreStatus] = useState<
    'restoring' | 'retryable' | 'idle'
  >('restoring');
  // Fail closed until /api/auth/me confirms the current legal bundle.
  const [termsCurrent, setTermsCurrent] = useState(false);
  const [termsAcceptanceStatus, setTermsAcceptanceStatus] =
    useState<TermsAcceptanceStatus>('ready');

  useEffect(() => {
    const requireTerms = () => {
      setTermsCurrent(false);
      setTermsAcceptanceStatus('ready');
    };
    window.addEventListener(TERMS_REQUIRED_EVENT, requireTerms);
    return () => {
      window.removeEventListener(TERMS_REQUIRED_EVENT, requireTerms);
    };
  }, []);

  // On mount, restore token from localStorage and verify it with the server.
  useEffect(() => {
    const stored = getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
    const storedEmail = getCompatItem(KEYS.authEmail.new, KEYS.authEmail.legacy);
    if (storedEmail) setEmail(storedEmail);

    if (!canStartPersonalDataRequests()) {
      setRestoreStatus('idle');
      setIsLoading(false);
      return;
    }

    if (!stored) {
      setRestoreStatus('idle');
      setIsLoading(false);
      return;
    }
    // The credential remains the session identity while verification is in
    // flight. Only an authoritative 401 may clear it.
    setToken(stored);

    const clearRestoredSession = () => {
      removeRecentFeedbackId();
      removeCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
      removeCompatItem(KEYS.authEmail.new, KEYS.authEmail.legacy);
      removeCompatItem(KEYS.authAdmin.new, KEYS.authAdmin.legacy);
      setToken(null);
      setUserId(null);
      setEmail(null);
      setIsAdmin(false);
      setIsDemo(false);
      setTermsCurrent(false);
      setRestoreStatus('idle');
    };

    // Use the pre-parsed result from auth-prefetch (started at module
    // evaluation time, before React mounted) to avoid one extra render-
    // cycle of latency on cold load. The result is already parsed so it
    // is idempotent to consume — StrictMode double-fires are safe.
    const mePromise: Promise<PrefetchedMe> = prefetchedMe ??
      fetch(`${API_BASE}/api/auth/me`, {
        headers: {
          ...getChinaClientHeaders(),
          Authorization: `Bearer ${stored}`,
        },
      })
        .then(async (r): Promise<PrefetchedMe> => ({
          status: r.status,
          data: r.ok ? await r.json() as CurrentUserProfile : null,
        }))
        .catch((): PrefetchedMe => ({ status: 0, data: null }));

    mePromise
      .then(({ status, data }) => {
        const { disposition, token: restoredToken } = resolveRestoredSession(
          stored,
          status,
          data !== null,
        );
        if (disposition === 'invalid') {
          clearRestoredSession();
          return;
        }
        if (disposition !== 'authenticated' || !data) {
          setToken(restoredToken);
          setTermsCurrent(false);
          setRestoreStatus('retryable');
          return;
        }
        setUserId(data.id);
        setIsAdmin(data.is_superuser);
        setIsDemo(data.is_demo ?? false);
        setTermsCurrent(data.terms_current === true);
        setTermsAcceptanceStatus('ready');
        setCompatItem(KEYS.authAdmin.new, KEYS.authAdmin.legacy, String(data.is_superuser));
        setToken(stored);
        setRestoreStatus('idle');
        if (data.terms_current === true) {
          clearLegalBundleRecoveryMarker();
          void setAppInsightsUser(data.id);
          const recordWhenVisible = () => {
            if (document.visibilityState !== 'visible') return;
            recordProductEventOnce('app_opened', 'authenticated-session');
            document.removeEventListener('visibilitychange', recordWhenVisible);
          };
          document.addEventListener('visibilitychange', recordWhenVisible);
          recordWhenVisible();
        }
      })
      .catch(() => {
        setToken(stored);
        setTermsCurrent(false);
        setRestoreStatus('retryable');
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<{ ok: boolean; error?: string }> => {
    if (!canStartPersonalDataRequests()) {
      return {
        ok: false,
        error: 'Read the processing notice before continuing.',
      };
    }
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: {
          ...getChinaClientHeaders(),
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ username: email, password }),
      });

      if (!res.ok) {
        const apiError = await extractApiError(res, `Login failed (HTTP ${res.status}).`);
        const errorCode = apiError.code ?? apiError.message;
        if (errorCode === 'LOGIN_BAD_CREDENTIALS') {
          return { ok: false, error: 'Invalid email or password.' };
        }
        return { ok: false, error: apiError.message };
      }

      const data: unknown = await res.json().catch(() => null);
      const accessToken = (
        data != null
        && typeof data === 'object'
        && !Array.isArray(data)
      )
        ? (data as Record<string, unknown>).access_token
        : null;
      if (typeof accessToken !== 'string' || accessToken.length === 0) {
        return {
          ok: false,
          error: 'Sign-in response was incomplete. Please try again.',
        };
      }

      const meResponse = await fetch(`${API_BASE}/api/auth/me`, {
        headers: {
          ...getChinaClientHeaders(),
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!meResponse.ok) {
        const apiError = await extractApiError(
          meResponse,
          `Could not finish sign-in (HTTP ${meResponse.status}).`,
        );
        return { ok: false, error: apiError.message };
      }
      const me = await meResponse.json() as CurrentUserProfile;

      removeRecentFeedbackId();
      setCompatItem(KEYS.authToken.new, KEYS.authToken.legacy, accessToken);
      setCompatItem(KEYS.authEmail.new, KEYS.authEmail.legacy, email);
      setCompatItem(KEYS.authAdmin.new, KEYS.authAdmin.legacy, String(me.is_superuser));
      setEmail(email);
      setUserId(me.id);
      setIsAdmin(me.is_superuser);
      setIsDemo(me.is_demo ?? false);
      setTermsCurrent(me.terms_current === true);
      setTermsAcceptanceStatus('ready');
      setToken(accessToken);
      if (me.terms_current === true) {
        clearLegalBundleRecoveryMarker();
        void setAppInsightsUser(me.id);
        recordProductEventOnce('app_opened', 'authenticated-session');
      }
      return { ok: true };
    } catch {
      return { ok: false, error: 'Network error. Is the server running?' };
    }
  }, []);

  const register = useCallback(async (email: string, password: string, invitationCode?: string, acceptedTerms?: boolean, honeypot?: string): Promise<{ ok: boolean; error?: string; verificationRequired?: boolean }> => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: {
          ...getChinaClientHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          invitation_code: invitationCode || '',
          accepted_terms: !!acceptedTerms,
          terms_version: TERMS_VERSION,
          terms_digest: TERMS_CONTENT_DIGEST,
          terms_locale: document.documentElement.lang || navigator.language,
          website: honeypot || '',
        }),
      });

      if (!res.ok) {
        const apiError = await extractApiError(res, `Registration failed (HTTP ${res.status}).`);
        const errorCode = apiError.code ?? apiError.message;
        if (errorCode === 'REGISTER_USER_ALREADY_EXISTS') {
          return { ok: false, error: 'An account with this email already exists.' };
        }
        if (errorCode === 'REGISTER_INVITATION_REQUIRED') {
          return { ok: false, error: 'An invitation code is required to register.' };
        }
        if (errorCode === 'REGISTER_INVALID_INVITATION') {
          return { ok: false, error: 'Invalid or already used invitation code.' };
        }
        if (errorCode === 'REGISTER_TERMS_NOT_ACCEPTED') {
          return { ok: false, error: 'You must accept the Terms of Service to register.' };
        }
        if (errorCode === 'REGISTER_CLOSED') {
          return { ok: false, error: 'Registration is currently closed. Join the waitlist and we will invite you soon.' };
        }
        if (errorCode === 'REGISTER_FAILED') {
          return { ok: false, error: 'Registration could not be completed. Please try again.' };
        }
        return { ok: false, error: apiError.message };
      }

      const data = await res.json().catch(() => null);
      // Open, code-less signups must verify their email before logging in —
      // do NOT auto-login; the caller shows a "check your email" state.
      if (data?.verification_required) {
        return { ok: true, verificationRequired: true };
      }

      // Auto-login after successful (already-verified) registration.
      return login(email, password);
    } catch {
      return { ok: false, error: 'Network error. Is the server running?' };
    }
  }, [login]);

  const logout = useCallback(() => {
    removeRecentFeedbackId();
    removeCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
    removeCompatItem(KEYS.authEmail.new, KEYS.authEmail.legacy);
    removeCompatItem(KEYS.authAdmin.new, KEYS.authAdmin.legacy);
    setToken(null);
    setUserId(null);
    setEmail(null);
    setIsAdmin(false);
    setIsDemo(false);
    setTermsCurrent(false);
    setTermsAcceptanceStatus('ready');
    setRestoreStatus('idle');
    clearAppInsightsUser();
  }, []);

  const acceptTerms = useCallback(async (
    onBundleMismatch?: () => void,
  ): Promise<TermsAcceptanceStatus> => {
    const tk = getCompatItem(KEYS.authToken.new, KEYS.authToken.legacy);
    if (!tk) {
      setTermsAcceptanceStatus('submit_error');
      return 'submit_error';
    }
    setTermsAcceptanceStatus('submitting');
    try {
      const res = await apiFetch('/api/me/accept-terms', {
        method: 'POST',
        headers: {
          ...getChinaClientHeaders(),
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tk}`,
        },
        body: JSON.stringify({
          terms_version: TERMS_VERSION,
          terms_digest: TERMS_CONTENT_DIGEST,
          locale: document.documentElement.lang || navigator.language,
        }),
      });
      if (!res.ok) {
        const apiError = await extractApiError(
          res,
          `Could not accept Terms (HTTP ${res.status}).`,
        );
        if (
          res.status === 409
          && apiError.code === TERMS_BUNDLE_MISMATCH_CODE
          && isTermsBundleMismatch(res.status, apiError.code)
        ) {
          // Keep the gate closed while this exact stale-bundle response tries
          // one bounded, same-origin service-worker refresh. Server-reported
          // policy metadata is diagnostic only and never enters a resubmit.
          setTermsCurrent(false);
          setTermsAcceptanceStatus('updating');
          onBundleMismatch?.();
          const recovery = await prepareLegalBundleRecovery();
          if (recovery.action === 'reload') {
            setTermsAcceptanceStatus('reloading');
            window.setTimeout(() => window.location.reload(), 0);
            return 'reloading';
          }
          setTermsAcceptanceStatus('fallback');
          return 'fallback';
        }
        setTermsAcceptanceStatus('submit_error');
        return 'submit_error';
      }
      await res.json() as TermsAcceptanceResponse;
      clearLegalBundleRecoveryMarker();
      setTermsAcceptanceStatus('accepted');
      setTermsCurrent(true);
      if (userId) void setAppInsightsUser(userId);
      recordProductEventOnce('app_opened', 'authenticated-session');
      void queryClient.invalidateQueries();
      return 'accepted';
    } catch {
      setTermsAcceptanceStatus('submit_error');
      return 'submit_error';
    }
  }, [queryClient, userId]);

  const isAuthenticated = token !== null;

  return (
    <AuthContext.Provider
      value={{ token, userId, email, isAdmin, isDemo, isAuthenticated, isLoading, restoreStatus, termsCurrent, termsAcceptanceStatus, login, register, logout, acceptTerms }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
