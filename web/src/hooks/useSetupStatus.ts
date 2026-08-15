import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSettings } from '@/contexts/SettingsContext';
import {
  API_BASE,
  apiFetch,
  getAuthCacheScope,
} from '@/hooks/useApi';
import type { SyncStatusResponse } from '@/types/api';

const SETUP_DONE_KEY = 'praxys-setup-done';
const SETUP_SKIPPED_PREFIX = 'praxys-setup-skipped';

function setupSkippedKey(email: string | null): string | null {
  const normalized = email?.trim().toLowerCase();
  return normalized ? `${SETUP_SKIPPED_PREFIX}:${normalized}` : null;
}

/** True when this account skipped onboarding in the current browser session. */
export function hasSkippedSetupForSession(email: string | null): boolean {
  const key = setupSkippedKey(email);
  if (!key) return false;
  try { return sessionStorage.getItem(key) === 'true'; } catch { return false; }
}

/** Let this account use the app without completing onboarding until the tab closes. */
export function skipSetupForSession(email: string | null): void {
  const key = setupSkippedKey(email);
  if (!key) return;
  try { sessionStorage.setItem(key, 'true'); } catch { /* sessionStorage unavailable */ }
}

function getCachedSetupDone(): boolean {
  try { return localStorage.getItem(SETUP_DONE_KEY) === 'true'; } catch { return false; }
}

function setCachedSetupDone(): void {
  try { localStorage.setItem(SETUP_DONE_KEY, 'true'); } catch { /* localStorage unavailable */ }
}

function clearCachedSetupDone(): void {
  try { localStorage.removeItem(SETUP_DONE_KEY); } catch { /* localStorage unavailable */ }
}

export interface SetupStep {
  key: string;
  label: string;
  description: string;
  done: boolean;
}

export interface SetupStatus {
  loading: boolean;
  steps: SetupStep[];
  completed: number;
  total: number;
  allDone: boolean;
  /** At least one platform has stored credentials. */
  hasConnection: boolean;
  /** At least one successful sync has occurred. */
  hasSyncedData: boolean;
  /** Which platforms have real connections (credentials stored). */
  connectedPlatforms: string[];
  /** Current sync status per platform. */
  syncStatus: SyncStatusResponse;
  /** Refresh connections + sync status. */
  refetch: () => void;
}

interface ConnectionsResponse {
  connections?: Record<string, unknown>;
}

async function fetchConnections(): Promise<ConnectionsResponse> {
  const response = await apiFetch(`${API_BASE}/api/settings/connections`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function fetchSyncStatus(): Promise<SyncStatusResponse> {
  const response = await apiFetch(`${API_BASE}/api/sync/status`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

/**
 * Derives onboarding setup status from SettingsContext + connections API.
 * Used by the Setup page, nav badge, and redirect logic.
 */
export function useSetupStatus(): SetupStatus {
  const { config, loading: settingsLoading } = useSettings();
  // Cached flag: if setup was fully complete on a prior load, skip the
  // blocking API calls so TodayOrSetup renders Today immediately.
  const [cachedDone] = useState(() => getCachedSetupDone());
  const authScope = getAuthCacheScope();
  const connectionsQuery = useQuery({
    queryKey: ['setup', 'connections', authScope],
    queryFn: fetchConnections,
  });
  const syncStatusQuery = useQuery({
    queryKey: ['setup', 'sync-status', authScope],
    queryFn: fetchSyncStatus,
  });
  const connectedPlatforms = Object.keys(
    connectionsQuery.data?.connections ?? {},
  );
  const syncStatus = syncStatusQuery.data ?? {};

  // When the cache says setup was complete and this is the initial load,
  // skip the blocking wait so TodayOrSetup renders Today immediately.
  const loading = cachedDone
    ? false
    : settingsLoading || connectionsQuery.isLoading || syncStatusQuery.isLoading;

  // Derive step completion
  const hasConnection = connectedPlatforms.length > 0;

  const hasSyncedData = Object.values(syncStatus).some(
    (s) => s.last_sync != null || s.status === 'done'
  );

  const goalConfigured = config?.goal
    ? (config.goal.race_date && config.goal.race_date !== '') ||
      (config.goal.target_time_sec && Number(config.goal.target_time_sec) > 0)
    : false;

  const steps: SetupStep[] = [
    {
      key: 'connect',
      label: 'Connect a platform',
      description: hasConnection
        ? `Connected: ${connectedPlatforms.join(', ')}`
        : 'Link a supported platform to pull your training data',
      done: hasConnection,
    },
    {
      key: 'sync',
      label: 'Sync your data',
      description: hasSyncedData
        ? 'Data synced successfully'
        : 'Pull your latest activities, power data, and recovery metrics',
      done: hasSyncedData,
    },
    {
      key: 'base',
      label: 'Choose training base',
      description: hasConnection
        ? `Set to ${config?.training_base || 'power'}-based training`
        : 'Connect a platform first to choose your training base',
      // Done when user has a connection (making the choice meaningful)
      // and has explicitly selected a base (tracked by having a config row)
      done: hasConnection,
    },
    {
      key: 'goal',
      label: 'Set a goal',
      description: goalConfigured
        ? 'Goal configured'
        : 'Target a race or track continuous improvement',
      done: !!goalConfigured,
    },
  ];

  const completed = steps.filter((s) => s.done).length;
  const isActuallyDone = completed === steps.length;
  const liveStatusValidated = (
    !settingsLoading
    && connectionsQuery.isSuccess
    && syncStatusQuery.isSuccess
  );

  // Keep the cache in sync with live state: set on completion, clear when
  // a platform is disconnected or setup regresses (e.g. after logout on a
  // shared browser or account switch).
  useEffect(() => {
    if (
      settingsLoading
      || !connectionsQuery.isSuccess
      || !syncStatusQuery.isSuccess
    ) {
      return;
    }
    if (isActuallyDone) {
      setCachedSetupDone();
    } else {
      clearCachedSetupDone();
    }
  }, [
    connectionsQuery.isSuccess,
    isActuallyDone,
    settingsLoading,
    syncStatusQuery.isSuccess,
  ]);

  return {
    loading,
    steps,
    completed,
    total: steps.length,
    allDone: (cachedDone && !liveStatusValidated) || isActuallyDone,
    hasConnection,
    hasSyncedData,
    connectedPlatforms,
    syncStatus,
    // Clear cache on manual refetch (e.g. after disconnecting a platform)
    // so the next render re-checks live state instead of using stale cache.
    refetch: () => {
      clearCachedSetupDone();
      void connectionsQuery.refetch();
      void syncStatusQuery.refetch();
    },
  };
}
