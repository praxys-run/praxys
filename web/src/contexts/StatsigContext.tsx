import {
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';
import type { StatsigUser } from '@statsig/js-client';
import {
  StatsigProvider as StatsigBindingsProvider,
  useStatsigUser,
} from '@statsig/react-bindings';

import { useAuth } from '@/hooks/useAuth';
import { isBrowserTelemetryAllowed } from '@/lib/runtime-region';

const CLIENT_KEY = import.meta.env.VITE_STATSIG_CLIENT_KEY?.trim() ?? '';
const ENVIRONMENT = import.meta.env.VITE_STATSIG_ENV?.trim() || 'development';

function sameUser(left: StatsigUser, right: StatsigUser): boolean {
  return (
    left.userID === right.userID
    && left.email === right.email
    && left.custom?.is_admin === right.custom?.is_admin
    && left.custom?.is_demo === right.custom?.is_demo
  );
}

function StatsigIdentitySync({
  user,
  children,
}: {
  user: StatsigUser;
  children: ReactNode;
}) {
  const { user: currentUser, updateUserAsync } = useStatsigUser();
  const identityIsCurrent = sameUser(currentUser, user);

  useEffect(() => {
    if (identityIsCurrent) return;
    void updateUserAsync(user).catch(() => {
      // Server-side rollout enforcement remains authoritative. A failed
      // browser identity refresh must not affect existing product behavior.
    });
  }, [identityIsCurrent, updateUserAsync, user]);

  return children;
}

/**
 * Initialize Statsig only when a public client key is configured and the
 * artifact is not the privacy-gated China deployment.
 *
 * This component must stay inside AuthProvider: the SDK identity is refreshed
 * whenever the authenticated account changes. Missing config is a true no-op.
 * The first rollout gate is enforced by the backend and mirrored through its
 * existing settings response, so this provider does not evaluate a gate yet.
 */
export function StatsigProvider({ children }: { children: ReactNode }) {
  const {
    userId,
    email,
    isAdmin,
    isDemo,
    isAuthenticated,
    isLoading,
  } = useAuth();
  const targetingEmail = email?.toLowerCase().startsWith('wechat:')
    ? null
    : email;
  const user = useMemo<StatsigUser>(() => ({
    ...(isAuthenticated && userId ? { userID: userId } : {}),
    ...(isAuthenticated && targetingEmail ? { email: targetingEmail } : {}),
    custom: {
      is_admin: isAdmin,
      is_demo: isDemo,
    },
  }), [isAdmin, isAuthenticated, isDemo, targetingEmail, userId]);

  if (
    !isBrowserTelemetryAllowed(Boolean(CLIENT_KEY))
    || isLoading
    || !isAuthenticated
    || !userId
  ) {
    return children;
  }

  return (
    <StatsigBindingsProvider
      sdkKey={CLIENT_KEY}
      user={user}
      options={{ environment: { tier: ENVIRONMENT } }}
    >
      <StatsigIdentitySync user={user}>{children}</StatsigIdentitySync>
    </StatsigBindingsProvider>
  );
}
