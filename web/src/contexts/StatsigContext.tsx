import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';
import type { StatsigUser } from '@statsig/js-client';
import {
  StatsigProvider as StatsigBindingsProvider,
  useFeatureGate,
  useStatsigUser,
} from '@statsig/react-bindings';

import { useAuth } from '@/hooks/useAuth';

export type FeatureFlagName =
  | 'ai_insights_enabled'
  | 'strava_connection_visible'
  | 'coros_connection_visible'
  | 'stryd_plan_push_visible';

type FeatureFlags = Record<FeatureFlagName, boolean>;

const DISABLED_FLAGS: FeatureFlags = {
  ai_insights_enabled: false,
  strava_connection_visible: false,
  coros_connection_visible: false,
  stryd_plan_push_visible: false,
};

const FeatureFlagsContext = createContext<FeatureFlags>(DISABLED_FLAGS);
const CLIENT_KEY = import.meta.env.VITE_STATSIG_CLIENT_KEY?.trim() ?? '';
const ENVIRONMENT = import.meta.env.VITE_STATSIG_ENV?.trim() || 'development';

function sameUser(left: StatsigUser, right: StatsigUser): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function StatsigBridge({
  user,
  children,
}: {
  user: StatsigUser;
  children: ReactNode;
}) {
  const { user: currentUser, updateUserAsync } = useStatsigUser();
  const aiInsights = useFeatureGate('ai_insights_enabled').value;
  const stravaConnection = useFeatureGate('strava_connection_visible').value;
  const corosConnection = useFeatureGate('coros_connection_visible').value;
  const strydPlanPush = useFeatureGate('stryd_plan_push_visible').value;
  const identityIsCurrent = sameUser(currentUser, user);

  useEffect(() => {
    if (identityIsCurrent) return;
    void updateUserAsync(user).catch(() => {
      // Keep the application-owned values below false while the SDK still
      // holds a previous identity.
    });
  }, [identityIsCurrent, updateUserAsync, user]);

  const flags = useMemo<FeatureFlags>(() => ({
    ai_insights_enabled: identityIsCurrent && aiInsights,
    strava_connection_visible: identityIsCurrent && stravaConnection,
    coros_connection_visible: identityIsCurrent && corosConnection,
    stryd_plan_push_visible: identityIsCurrent && strydPlanPush,
  }), [
    aiInsights,
    corosConnection,
    identityIsCurrent,
    stravaConnection,
    strydPlanPush,
  ]);

  return (
    <FeatureFlagsContext.Provider value={flags}>
      {children}
    </FeatureFlagsContext.Provider>
  );
}

/**
 * Initialize Statsig only when a public client key is configured.
 *
 * This component must stay inside AuthProvider: the SDK identity is refreshed
 * whenever the authenticated account changes. Missing config is a true no-op
 * with every application-owned flag defaulted to false.
 */
export function StatsigProvider({ children }: { children: ReactNode }) {
  const { userId, email, isAdmin, isDemo, isAuthenticated } = useAuth();
  const user = useMemo<StatsigUser>(() => ({
    ...(isAuthenticated && userId ? { userID: userId } : {}),
    ...(isAuthenticated && email ? { email } : {}),
    custom: {
      is_admin: isAdmin,
      is_demo: isDemo,
    },
  }), [email, isAdmin, isAuthenticated, isDemo, userId]);

  if (!CLIENT_KEY) {
    return (
      <FeatureFlagsContext.Provider value={DISABLED_FLAGS}>
        {children}
      </FeatureFlagsContext.Provider>
    );
  }

  return (
    <StatsigBindingsProvider
      sdkKey={CLIENT_KEY}
      user={user}
      options={{ environment: { tier: ENVIRONMENT } }}
    >
      <StatsigBridge user={user}>{children}</StatsigBridge>
    </StatsigBindingsProvider>
  );
}

export function useFeatureFlag(name: FeatureFlagName): boolean {
  return useContext(FeatureFlagsContext)[name];
}
